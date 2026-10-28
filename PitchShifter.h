// Semitones (Studio Wiga) - low latency pitch shifter
// --------------------------------------------------------------------------
// Time-domain, pitch-synchronous splicing shifter in the spirit of the
// "digital capo" pedals: a read head runs through a short history buffer at
// the transposition ratio; when it drifts out of its window it is replaced by
// a new head whose position is chosen so that both read the same phase of the
// waveform (normalised cross-correlation, coarse search on a decimated copy,
// fine search at full rate with sub-sample refinement), with a short
// correlation-dependent crossfade.
//
// The window adapts to the period of the note being played (YIN tracker on a
// decimated copy, down to ~32 Hz for 7/8-string and bass drop tunings) so the
// latency stays as small as the pitch allows: a few ms on high notes, around
// 8 to 12 ms on the lowest strings. A note onset makes the head jump back
// to the newest audio so attacks stay tight ("chugging" feel).
//
// No allocation, lock or system call in process(). JUCE independent.
#pragma once
#include <vector>
#include <cmath>
#include <cstdint>
#include <algorithm>
#include <cstring>
#ifdef SW_DEBUG
#include <cstdio>
#endif

namespace sw
{

struct Biquad
{
    float b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0;
    float z1 = 0, z2 = 0;
    inline float process (float x) noexcept
    {
        const float y = b0 * x + z1;
        z1 = b1 * x - a1 * y + z2;
        z2 = b2 * x - a2 * y;
        return y;
    }
    void reset() noexcept { z1 = z2 = 0; }
    void setLowpass (double fs, double fc, double q) noexcept
    {
        const double w0 = 2.0 * 3.14159265358979323846 * fc / fs;
        const double c = std::cos (w0), s = std::sin (w0);
        const double alpha = s / (2.0 * q);
        const double a0 = 1.0 + alpha;
        b0 = (float) ((1.0 - c) * 0.5 / a0);
        b1 = (float) ((1.0 - c) / a0);
        b2 = b0;
        a1 = (float) (-2.0 * c / a0);
        a2 = (float) ((1.0 - alpha) / a0);
    }
    void setHighpass (double fs, double fc, double q) noexcept
    {
        const double w0 = 2.0 * 3.14159265358979323846 * fc / fs;
        const double c = std::cos (w0), s = std::sin (w0);
        const double alpha = s / (2.0 * q);
        const double a0 = 1.0 + alpha;
        b0 = (float) ((1.0 + c) * 0.5 / a0);
        b1 = (float) (-(1.0 + c) / a0);
        b2 = b0;
        a1 = (float) (-2.0 * c / a0);
        a2 = (float) ((1.0 - alpha) / a0);
    }
};

class PitchShifter
{
public:
    static constexpr int kBits = 16;
    static constexpr int kSize = 1 << kBits;     // 65536 samples (> 340 ms at 192 kHz)
    static constexpr int kMask = kSize - 1;
    static constexpr int kMaxCh = 2;

    void prepare (double sampleRate, int numChannels)
    {
        fs = sampleRate;
        chans = std::clamp (numChannels, 1, kMaxCh);
        for (auto& b : buf) b.assign (kSize, 0.0f);
        mono.assign (kSize, 0.0f);
        decim = std::max (1, (int) std::lround (fs / 12000.0));
        fsd = fs / decim;
        dec.assign (kDecSize, 0.0f);
        // analysis anti alias (for the decimated copy): 4th order at 0.38 fsd
        for (auto& f : decLp) f.setLowpass (fs, std::min (0.38 * fsd, 0.45 * fs), 0.70710678);
        decLp[0].setLowpass (fs, std::min (0.38 * fsd, 0.45 * fs), 0.5411961);
        decLp[1].setLowpass (fs, std::min (0.38 * fsd, 0.45 * fs), 1.3065630);
        // analysis high pass (removes DC / rumble from the tracker)
        anaHp.setHighpass (fs, 25.0, 0.70710678);

        minLagD = std::max (4, (int) (fsd / 1100.0));
        maxLagD = std::min (kDecSize / 4, (int) (fsd / 31.0));
        yinWin = maxLagD;
        yinD.assign ((size_t) maxLagD + 2, 0.0f);

        dMinHard = 3.0;
        reset();
        setRatio (1.0);
    }

    void reset()
    {
        for (auto& b : buf) std::fill (b.begin(), b.end(), 0.0f);
        std::fill (mono.begin(), mono.end(), 0.0f);
        std::fill (dec.begin(), dec.end(), 0.0f);
        for (auto& c : aa) for (auto& f : c) f.reset();
        for (auto& f : decLp) f.reset();
        anaHp.reset();
        w = 0; wd = 0; decPhase = 0; hopCount = 0;
        dA = dMinHard + 0.002 * fs; dB = dA;
        fading = false; fadePos = 0; fadeLen = 1;
        period = 0.008 * fs; periodTrust = 0; unvoicedSamples = 0;
        envFast = envSlow = envMid = 0; onsetHold = 0; onsetArmed = true; corrAvg = 1.0f;
    }

    void setRatio (double r)
    {
        if (std::abs (r - ratio) < 1e-9 && aaReady) return;
        ratio = r;
        // input anti-alias for upward shifts: the head reads faster than real
        // time, so everything above fs / (2 r) would fold back.
        const double fc = r > 1.0001 ? std::min (0.455 * fs, 0.47 * fs / r) : std::min (0.47 * fs, 21000.0);
        for (auto& c : aa)
        {
            c[0].setLowpass (fs, fc, 0.5411961);
            c[1].setLowpass (fs, fc, 1.3065630);
        }
        aaReady = true;
    }

    double getRatio() const noexcept { return ratio; }
    /** current delay of the audible head in ms (for the latency read-out) */
    double getCurrentDelayMs() const noexcept { return 1000.0 * dA / fs; }
    double getPeriodMs() const noexcept { return 1000.0 * period / fs; }
   #ifdef SW_DEBUG
    int dbgSplices = 0, dbgBad = 0; double dbgCorr = 0; bool dbgPrint = false;
   #endif

    /** in/out may alias. ch = number of channels in the arrays */
    void process (float* const* io, int numCh, int n) noexcept
    {
        numCh = std::min (numCh, chans);
        const double step = 1.0 - ratio;          // head delay increment per sample
        for (int i = 0; i < n; ++i)
        {
            // ---------------------------------------------------- write
            float m = 0.0f;
            const int wi = (int) (w & kMask);
            for (int c = 0; c < numCh; ++c)
            {
                float x = io[c][i];
                x = aa[c][1].process (aa[c][0].process (x));
                buf[c][(size_t) wi] = x;
                m += io[c][i];
            }
            m /= (float) numCh;
            const float mh = anaHp.process (m);
            mono[(size_t) wi] = mh;
            // decimated copy for the tracker and the coarse search
            const float md = decLp[1].process (decLp[0].process (mh));
            if (++decPhase >= decim)
            {
                decPhase = 0;
                dec[(size_t) (wd & kDecMask)] = md;
                ++wd;
                if (++hopCount >= kHop) { hopCount = 0; trackPitch(); }
            }
            // onset detector (fast / slow envelope)
            const float am = std::abs (mh);
            envFast += (am - envFast) * (am > envFast ? kFastAtk : kFastRel);
            envMid += (envFast - envMid) * kMidCoef;
            envSlow += (am - envSlow) * kSlowCoef;
            ++w;

            // ---------------------------------------------------- read
            dA += step;
            if (dA < dMinHard) dA = dMinHard;
            float outS[kMaxCh];
            for (int c = 0; c < numCh; ++c) outS[c] = read (c, dA);

            if (fading)
            {
                dB += step;
                if (dB < dMinHard) dB = dMinHard;
                const float t = (float) (fadePos + 1) / (float) fadeLen;
                const float f = 0.5f - 0.5f * std::cos (3.14159265f * t);
                const float gB = fadeP >= 0.999f ? f : std::pow (f, fadeP);
                const float gA = fadeP >= 0.999f ? 1.0f - f : std::pow (1.0f - f, fadeP);
                for (int c = 0; c < numCh; ++c)
                    outS[c] = gA * outS[c] + gB * read (c, dB);
                if (++fadePos >= fadeLen)
                {
                    fading = false;
                    dA = dB;
                }
            }
            for (int c = 0; c < numCh; ++c) io[c][i] = outS[c];

            // ---------------------------------------------------- splice logic
            if (onsetHold > 0) --onsetHold;
            if (! fading && std::abs (step) > 1e-7)
                checkSplice();
        }
    }

private:
    static constexpr int kDecBits = 13;
    static constexpr int kDecSize = 1 << kDecBits;   // decimated history (~680 ms)
    static constexpr int kDecMask = kDecSize - 1;
    static constexpr int kHop = 48;                  // tracker hop (decimated samples, ~4 ms)
    static constexpr float kFastAtk = 0.25f, kFastRel = 0.0025f, kSlowCoef = 0.00035f, kMidCoef = 0.0016f;

    double fs = 48000, fsd = 12000;
    int chans = 2, decim = 4;
    std::vector<float> buf[kMaxCh];
    std::vector<float> mono, dec;
    Biquad aa[kMaxCh][2];
    Biquad decLp[2];
    Biquad anaHp;
    bool aaReady = false;
    int64_t w = 0, wd = 0;
    int decPhase = 0, hopCount = 0;

    double ratio = 1.0;
    double dA = 100, dB = 100, dMinHard = 3;
    bool fading = false;
    int fadePos = 0, fadeLen = 1;
    float fadeP = 1.0f;

    // tracker
    int minLagD = 10, maxLagD = 380, yinWin = 380;
    std::vector<float> yinD;
    double period = 384;          // full rate samples
    float periodTrust = 0;
    int unvoicedSamples = 0;
    float envFast = 0, envSlow = 0, envMid = 0;
    bool onsetArmed = true;
    int onsetHold = 0;
    float corrAvg = 1.0f;

    inline float read (int c, double d) const noexcept
    {
        // position of the sample 'd' samples before the newest one
        const double pos = (double) (w - 1) - d;
        const double fl = std::floor (pos);
        const float fr = (float) (pos - fl);
        const int64_t i = (int64_t) fl;
        const auto& b = buf[c];
        const float xm1 = b[(size_t) ((i - 1) & kMask)];
        const float x0  = b[(size_t) (i & kMask)];
        const float x1  = b[(size_t) ((i + 1) & kMask)];
        const float x2  = b[(size_t) ((i + 2) & kMask)];
        // 4 point, 3rd order Hermite
        const float c1 = 0.5f * (x1 - xm1);
        const float c2 = xm1 - 2.5f * x0 + 2.0f * x1 - 0.5f * x2;
        const float c3 = 0.5f * (x2 - xm1) + 1.5f * (x0 - x1);
        return ((c3 * fr + c2) * fr + c1) * fr + x0;
    }

    // ------------------------------------------------------------------ YIN
    void trackPitch() noexcept
    {
        const int W = yinWin;
        const int L = maxLagD;
        if (wd < (int64_t) (W + L + 2)) return;
        const int64_t end = wd - 1;               // newest decimated sample
        // energy gate
        double e = 0;
        for (int k = 0; k < W; ++k) { const float x = dec[(size_t) ((end - k) & kDecMask)]; e += x * x; }
        if (e / W < 1.0e-8)
        {
            markUnvoiced();
            return;
        }
        // difference function d(tau) and cumulative mean normalised d'(tau)
        float runSum = 0;
        int best = -1;
        float bestVal = 1e9f;
        for (int tau = 1; tau <= L; ++tau)
        {
            float s = 0;
            const int64_t a0 = end, b0 = end - tau;
            for (int k = 0; k < W; ++k)
            {
                const float df = dec[(size_t) ((a0 - k) & kDecMask)] - dec[(size_t) ((b0 - k) & kDecMask)];
                s += df * df;
            }
            runSum += s;
            const float dn = runSum > 0 ? s * (float) tau / runSum : 1.0f;
            yinD[(size_t) tau] = dn;
            if (tau >= minLagD + 1 && best < 0)
            {
                // first dip under the absolute threshold, then follow it down
                const float prev = yinD[(size_t) tau - 1];
                if (prev < 0.16f && dn > prev) { best = tau - 1; bestVal = prev; break; }
            }
        }
        if (best < 0)
        {
            // no clear dip: take the global minimum if it is good enough
            for (int tau = minLagD; tau <= L; ++tau)
                if (yinD[(size_t) tau] < bestVal) { bestVal = yinD[(size_t) tau]; best = tau; }
            if (bestVal > 0.35f) { markUnvoiced(); return; }
        }
        // parabolic refinement
        double tauR = best;
        if (best > 1 && best < L)
        {
            const double y0 = yinD[(size_t) best - 1], y1 = yinD[(size_t) best], y2 = yinD[(size_t) best + 1];
            const double den = y0 - 2 * y1 + y2;
            if (std::abs (den) > 1e-12) tauR += 0.5 * (y0 - y2) / den;
        }
        const double pNew = tauR * decim;
        const float trust = std::clamp (1.0f - bestVal * 2.5f, 0.0f, 1.0f);
        if (periodTrust < 0.3f || std::abs (pNew - period) > 0.12 * period)
            period = pNew;                                       // new note: jump
        else
            period += (pNew - period) * 0.35;                    // same note: glide
        periodTrust = trust;
        unvoicedSamples = 0;
    }

    void markUnvoiced() noexcept
    {
        unvoicedSamples += kHop * decim;
        periodTrust *= 0.8f;
        if (unvoicedSamples > (int) (0.12 * fs))
            period += (0.008 * fs - period) * 0.2;               // drift back to a neutral window
    }

    // ------------------------------------------------------------ splicing
    // 0 = clean single notes, 1 = dense chords (splices correlate poorly):
    // wider search, longer windows and smoother constant-power fades.
    float poly() const noexcept { return std::clamp ((0.80f - corrAvg) / 0.30f, 0.0f, 1.0f); }

    double spanSamples() const noexcept
    {
        // one period gives at least one phase-aligned candidate
        double p = periodTrust > 0.25f ? period * 1.02 : 0.009 * fs;
        p = std::max (p, (double) poly() * 0.022 * fs);
        return std::clamp (p, 0.0016 * fs, 0.034 * fs);
    }

    int fadeSamples() const noexcept
    {
        const double p = periodTrust > 0.25f ? period : 0.008 * fs;
        double lx;
        if (ratio < 1.0) lx = std::clamp (p / ratio * 0.9, 0.0018 * fs, 0.0095 * fs);
        else             lx = std::clamp (p / ratio * 0.75, 0.0014 * fs, 0.0060 * fs);
        const double lxPoly = (ratio < 1.0 ? 0.011 : 0.0075) * fs;
        lx += (std::max (lx, lxPoly) - lx) * poly();
        return (int) lx;
    }

    void checkSplice() noexcept
    {
        const double span = spanSamples();
        // onset: jump back to the newest audio so the attack is not delayed.
        // Hysteresis: re-armed only once the fast envelope has come back
        // close to the medium one (one trigger per pick).
        bool onset = false;
        if (onsetArmed && onsetHold == 0 && envFast > 1.9f * envMid + 3.0e-4f && envFast > 0.25f * envSlow)
        {
            onset = true;
            onsetArmed = false;
            onsetHold = (int) (0.045 * fs);
        }
        else if (! onsetArmed && envFast < 1.15f * envMid)
            onsetArmed = true;
        // candidates closer than half a period to the current head are
        // excluded (they would trivially match and re-trigger at once)
        const double excl = 0.5 * span;
        if (ratio < 1.0)
        {
            const double lo = dMinHard + 1.0;
            if (dA >= lo + span)
                startSplice (lo, std::max (lo + 1.0, std::min (lo + span, dA - excl)), false);
            else if (onset && dA > lo + 0.0025 * fs)
                startSplice (lo, std::max (lo + 1.0, std::min (lo + span, dA - 0.0015 * fs)), true);
        }
        else
        {
            const int lx = fadeSamples();
            const double trig = dMinHard + 1.0 + lx * (ratio - 1.0);
            const double lo = trig + lx * (ratio - 1.0) + 1.0;
            if (dA <= trig)
                startSplice (std::max (lo, dA + excl), std::max (lo, dA + excl) + span, false);
            else if (onset && dA > lo + span * 0.5 + 0.002 * fs)
                startSplice (lo, std::max (lo + 1.0, std::min (lo + span, dA - 0.001 * fs)), true);
        }
    }

    // normalised cross correlation of two backward windows (decimated)
    float nccDec (int64_t a, int64_t b, int len) const noexcept
    {
        float sab = 0, saa = 0, sbb = 0;
        for (int k = 0; k < len; ++k)
        {
            const float x = dec[(size_t) ((a - k) & kDecMask)];
            const float y = dec[(size_t) ((b - k) & kDecMask)];
            sab += x * y; saa += x * x; sbb += y * y;
        }
        const float den = std::sqrt (saa * sbb);
        return den > 1e-12f ? sab / den : 0.0f;
    }

    float nccFull (int64_t a, int64_t b, int len, int stride) const noexcept
    {
        float sab = 0, saa = 0, sbb = 0;
        for (int k = 0; k < len; k += stride)
        {
            const float x = mono[(size_t) ((a - k) & kMask)];
            const float y = mono[(size_t) ((b - k) & kMask)];
            sab += x * y; saa += x * x; sbb += y * y;
        }
        const float den = std::sqrt (saa * sbb);
        return den > 1e-12f ? sab / den : 0.0f;
    }

    void startSplice (double lo, double hi, bool fromOnset) noexcept
    {
        hi = std::max (hi, lo + 1.0);
        const int64_t newest = w - 1;
        const double posA = (double) newest - dA;            // where the current head reads
        const double fracA = posA - std::floor (posA);
        // correlation window: about one period (min 2 ms, max 16 ms)
        const double p = periodTrust > 0.25f ? period : 0.008 * fs;
        int lenFull = (int) std::clamp (p * 1.2, 0.002 * fs, 0.016 * fs);
        lenFull = std::max (lenFull, (int) (poly() * 0.020 * fs));
        const int lenDec = std::max (8, lenFull / decim);

        // ---- coarse search on the decimated copy
        const int64_t wdNewest = wd - 1;
        auto toDec = [&] (double fullPos) { return (int64_t) std::floor ((fullPos - (double) newest) / decim) + wdNewest; };
        const int64_t aD = toDec (posA);
        const int64_t bHiD = toDec ((double) newest - lo);    // smallest delay = most recent
        const int64_t bLoD = toDec ((double) newest - hi);
        float bestC = -2.0f;
        int64_t bestD = bHiD;
        const double spanD = std::max<double> (1.0, (double) (bHiD - bLoD));
        for (int64_t b = bLoD; b <= bHiD; ++b)
        {
            float c = nccDec (aD, b, lenDec);
            // light preference for the lowest latency (most recent) candidate
            c += 0.035f * (float) ((double) (b - bLoD) / spanD);
            if (c > bestC) { bestC = c; bestD = b; }
        }
        // ---- fine search at full rate around the coarse winner
        const int64_t aF = (int64_t) std::floor (posA);
        const int64_t centre = newest - (wdNewest - bestD) * decim;
        int64_t bestF = centre;
        float bestFC = -2.0f;
        float cm1 = 0, c0 = 0, cp1 = 0;
        const int stride = lenFull > 1200 ? 3 : (lenFull > 600 ? 2 : 1);
        const int64_t fLo = std::max<int64_t> (centre - decim - 1, (int64_t) std::ceil ((double) newest - hi));
        const int64_t fHi = std::min<int64_t> (centre + decim + 1, (int64_t) std::floor ((double) newest - lo));
        float cs[64];
        int cnt = 0;
        for (int64_t b = fLo; b <= fHi && cnt < 64; ++b, ++cnt)
        {
            cs[cnt] = nccFull (aF, b, lenFull, stride);
            if (cs[cnt] > bestFC) { bestFC = cs[cnt]; bestF = b; }
        }
        double sub = 0;
        const int bi = (int) (bestF - fLo);
        if (cnt >= 3 && bi > 0 && bi < cnt - 1)
        {
            cm1 = cs[bi - 1]; c0 = cs[bi]; cp1 = cs[bi + 1];
            const double den = cm1 - 2.0 * c0 + cp1;
            if (std::abs (den) > 1e-9) sub = std::clamp (0.5 * (cm1 - cp1) / den, -0.5, 0.5);
        }
        if (cnt == 0) { bestF = (int64_t) std::floor ((double) newest - lo); bestFC = 0; }
        const double posB = (double) bestF + sub + fracA;
        double newD = (double) newest - posB;
        newD = std::clamp (newD, lo, hi);

        // crossfade: linear (constant amplitude) for well correlated
        // material, towards constant power when it is not (chords, noise)
        const float c = std::clamp (bestFC, 0.0f, 1.0f);
        fadeP = c > 0.9f ? 1.0f : (c < 0.35f ? 0.5f : 0.5f + 0.5f * (c - 0.35f) / 0.55f);
        fadeLen = std::max (16, fadeSamples());
        if (fromOnset) fadeLen = std::max (16, std::min (fadeLen, (int) (0.003 * fs)));
        // up-shift: never let the outgoing head reach the write position
        if (ratio > 1.0)
        {
            const int maxLen = (int) ((dA - dMinHard) / (ratio - 1.0));
            fadeLen = std::max (8, std::min (fadeLen, maxLen));
        }
        dB = newD;
        fadePos = 0;
        fading = true;
        if (! fromOnset) corrAvg += (std::max (0.0f, bestFC) - corrAvg) * 0.3f;
       #ifdef SW_DEBUG
        if (dbgPrint) printf ("t=%.3f onset=%d dA=%.2fms lo=%.2f hi=%.2f -> dB=%.2f corr=%.3f coarse=%.3f P=%.2f trust=%.2f fade=%.2fms\n",
                              (double) w / fs, (int) fromOnset, 1000 * dA / fs, 1000 * lo / fs, 1000 * hi / fs, 1000 * newD / fs, bestFC, bestC, 1000 * period / fs, periodTrust, 1000.0 * fadeLen / fs);
        ++dbgSplices; dbgCorr += bestFC; if (bestFC < 0.8f) ++dbgBad;
       #endif
    }
};

} // namespace sw
