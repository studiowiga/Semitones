// Offline checks of the pitch shifter: pitch accuracy, latency, smoothness.
// g++ -O2 -std=c++17 -I.. dsp_test.cpp -o dsp_test && ./dsp_test
#define SW_DEBUG 1
#include "../PitchShifter.h"
#include <cstdio>
#include <random>
#include <string>
#include <vector>

static std::mt19937 rng (1);

// Karplus-Strong string (guitar-like pluck)
static void pluck (std::vector<float>& out, double fs, double f0, int start, int len, float amp, float bright = 0.5f)
{
    const int N = (int) std::round (fs / f0);
    std::vector<float> d ((size_t) N);
    std::uniform_real_distribution<float> u (-1, 1);
    float lp = 0;
    for (auto& v : d) { lp = lp * bright + u (rng) * (1 - bright); v = lp; }
    int idx = 0;
    float prev = 0;
    for (int i = 0; i < len && start + i < (int) out.size(); ++i)
    {
        const float x = d[(size_t) idx];
        const float y = 0.4985f * (x + prev);
        prev = x;
        d[(size_t) idx] = y;
        idx = (idx + 1) % N;
        out[(size_t) (start + i)] += amp * x;
    }
}

static double acfPitch (const float* x, int n, double fs, double fmin, double fmax)
{
    int lmin = (int) (fs / fmax), lmax = (int) (fs / fmin);
    double best = -1; int bl = lmin;
    double e0 = 0; for (int i = 0; i < n - lmax; ++i) e0 += x[i] * x[i];
    for (int l = lmin; l <= lmax; ++l)
    {
        double s = 0, e1 = 0;
        for (int i = 0; i < n - lmax; ++i) { s += x[i] * x[i + l]; e1 += x[i + l] * x[i + l]; }
        double c = s / std::sqrt (e0 * e1 + 1e-12);
        if (c > best) { best = c; bl = l; }
    }
    // smallest lag reaching 92 % of the best peak (avoid sub-harmonics)
    for (int l = lmin; l <= lmax; ++l)
    {
        double s = 0, e1 = 0;
        for (int i = 0; i < n - lmax; ++i) { s += x[i] * x[i + l]; e1 += x[i + l] * x[i + l]; }
        double c = s / std::sqrt (e0 * e1 + 1e-12);
        if (c > 0.92 * best)
        {
            // walk to the local max
            double cc = c; int ll = l;
            for (int l2 = l + 1; l2 <= lmax; ++l2)
            {
                double s2 = 0, e2 = 0;
                for (int i = 0; i < n - lmax; ++i) { s2 += x[i] * x[i + l2]; e2 += x[i + l2] * x[i + l2]; }
                double c2 = s2 / std::sqrt (e0 * e2 + 1e-12);
                if (c2 < cc) break; cc = c2; ll = l2;
            }
            return fs / ll;
        }
    }
    return fs / bl;
}

// smoothness: ratio of energy of the second difference of the per-ms RMS envelope
static double envRoughness (const std::vector<float>& x, double fs, int from, int to, double frameMs = 1.0)
{
    const int hop = (int) (fs * 0.001 * frameMs);
    std::vector<double> env;
    for (int i = from; i + hop < to; i += hop)
    {
        double s = 0; for (int k = 0; k < hop; ++k) s += x[(size_t) (i + k)] * x[(size_t) (i + k)];
        env.push_back (std::sqrt (s / hop));
    }
    double r = 0, m = 0;
    for (size_t i = 2; i < env.size(); ++i) { double d2 = env[i] - 2 * env[i - 1] + env[i - 2]; r += d2 * d2; m += env[i] * env[i]; }
    return std::sqrt (r / (m + 1e-12));
}

static void writeWav (const std::string& path, const std::vector<float>& x, int fs)
{
    FILE* f = fopen (path.c_str(), "wb");
    if (! f) return;
    int n = (int) x.size(), bytes = n * 2;
    auto w32 = [&] (int v) { fwrite (&v, 4, 1, f); };
    auto w16 = [&] (short v) { fwrite (&v, 2, 1, f); };
    fwrite ("RIFF", 1, 4, f); w32 (36 + bytes); fwrite ("WAVEfmt ", 1, 8, f);
    w32 (16); w16 (1); w16 (1); w32 (fs); w32 (fs * 2); w16 (2); w16 (16);
    fwrite ("data", 1, 4, f); w32 (bytes);
    for (float v : x) { float c = std::max (-1.0f, std::min (1.0f, v)); w16 ((short) (c * 32000)); }
    fclose (f);
}

int main (int argc, char** argv)
{
    const double fs = argc > 1 ? atof (argv[1]) : 48000.0;
    const int len = (int) (fs * 4);
    struct Case { const char* name; std::vector<double> notes; };
    std::vector<Case> cases = {
        { "lowE", { 82.41 } }, { "G1_7str", { 49.0 } }, { "A2", { 110.0 } }, { "E4", { 329.6 } },
        { "chordE5", { 82.41, 123.47, 164.81 } }, { "chordOpenG", { 98.0, 123.47, 146.8, 196.0, 246.9, 392.0 } },
    };
    int sts[] = { -12, -7, -5, -2, -1, 1, 2, 5, 7, 12 };
    printf ("fs=%.0f\n", fs);
    printf ("%-11s %4s %9s %9s %8s %8s %8s %7s\n", "case", "st", "f_in", "f_out", "err_ct", "lat_ms", "max_ms", "rough");
    for (auto& c : cases)
    {
        std::vector<float> in ((size_t) len, 0.0f);
        // re-pick every 500 ms (palm-muted chugs on the second half)
        for (int k = 0; k < 8; ++k)
            for (double f : c.notes)
                pluck (in, fs, f, (int) (k * 0.5 * fs), (int) (0.5 * fs), 0.25f / (float) c.notes.size() * 2, k < 4 ? 0.5f : 0.3f);
        for (int st : sts)
        {
            sw::PitchShifter ps;
            ps.prepare (fs, 1);
            ps.setRatio (std::pow (2.0, st / 12.0));
            std::vector<float> out = in;
            double latSum = 0, latMax = 0, perSum = 0, attSum = 0; int latN = 0, attN = 0;
            const int blk = 128;
            for (int i = 0; i < len; i += blk)
            {
                float* p = out.data() + i;
                ps.process (&p, 1, std::min (blk, len - i));
                const double d = ps.getCurrentDelayMs();
                { const double tm = std::fmod ((double) i / fs, 0.5); if (i > fs * 0.4 && tm > 0.006 && tm < 0.012) { attSum += d; attN++; } }
                if (i > fs * 0.2) { latSum += d; latN++; latMax = std::max (latMax, d); perSum += ps.getPeriodMs(); }
            }
            const int a = (int) (fs * 0.62), n = (int) (fs * 0.25);
            const double fin = acfPitch (in.data() + a, n, fs, 25, 800);
            const double fout = acfPitch (out.data() + a, n, fs, 20, 1700);
            const double expected = c.notes[0] * std::pow (2.0, st / 12.0);
            const double err = 1200.0 * std::log2 (fout / expected);
            const double frm = std::max (4.0, 2000.0 / expected);
            const double rough = envRoughness (out, fs, (int) (0.55 * fs), (int) (0.95 * fs), frm) / (envRoughness (in, fs, (int) (0.55 * fs), (int) (0.95 * fs), std::max (4.0, 2000.0 / c.notes[0])) + 1e-9);
            printf ("%-11s %4d %9.2f %9.2f %8.1f %8.2f %8.2f %7.3f  att=%.2f P=%.2fms spl=%d corr=%.3f bad=%d\n", c.name, st, fin, fout, err, latSum / latN, latMax, rough, attSum / std::max (1, attN), perSum / latN, ps.dbgSplices, ps.dbgCorr / std::max (1, ps.dbgSplices), ps.dbgBad);
            if (argc > 2) writeWav (std::string (argv[2]) + "/" + c.name + "_" + std::to_string (st) + ".wav", out, (int) fs);
        }
        printf ("%-11s  dry rough %.3f\n", c.name, envRoughness (in, fs, (int) (0.55 * fs), (int) (0.95 * fs)));
    }
}
