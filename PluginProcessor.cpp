#include "PluginProcessor.h"
#include "PluginEditor.h"

namespace
{
    enum { kOn = 0, kSemis, kMixOn, kMix, kFav, kNumParams };
    const char* const kIds[kNumParams] = { ParamID::on, ParamID::semitones, ParamID::mixOn, ParamID::mix, ParamID::fav };
}

// ============================================================================
juce::AudioProcessorValueTreeState::ParameterLayout SemitonesProcessor::createLayout()
{
    using namespace juce;
    std::vector<std::unique_ptr<RangedAudioParameter>> p;
    p.push_back (std::make_unique<AudioParameterBool> (ParameterID { ParamID::on, 1 }, "Effect On", true));
    p.push_back (std::make_unique<AudioParameterInt> (ParameterID { ParamID::semitones, 1 }, "Pitch", -12, 12, 0,
        AudioParameterIntAttributes().withLabel ("st").withStringFromValueFunction ([] (int v, int)
        {
            return v > 0 ? "+" + String (v) : String (v);
        })));
    p.push_back (std::make_unique<AudioParameterBool> (ParameterID { ParamID::mixOn, 1 }, "Mix Mode", false));
    p.push_back (std::make_unique<AudioParameterFloat> (ParameterID { ParamID::mix, 1 }, "Mix",
        NormalisableRange<float> (0.0f, 100.0f, 1.0f), 50.0f,
        AudioParameterFloatAttributes().withLabel ("%")));
    p.push_back (std::make_unique<AudioParameterBool> (ParameterID { ParamID::fav, 1 }, "FAV", false));
    return { p.begin(), p.end() };
}

const std::vector<FactoryPreset>& SemitonesProcessor::factoryPresets()
{
    static const std::vector<FactoryPreset> list = {
        { "Standard (0)",                       0, false, 50.0f },
        { "Eb Standard / Half step down (-1)", -1, false, 50.0f },
        { "D Standard / Whole step down (-2)", -2, false, 50.0f },
        { "C# Standard (-3)",                  -3, false, 50.0f },
        { "C Standard (-4)",                   -4, false, 50.0f },
        { "B Standard (-5)",                   -5, false, 50.0f },
        { "Bb Standard (-6)",                  -6, false, 50.0f },
        { "Baritone A (-7)",                   -7, false, 50.0f },
        { "Octave down (-12)",                -12, false, 50.0f },
        { "Octave doubler down (-12 + dry)",  -12, true,  50.0f },
        { "Sub octave blend (-12 + dry 30 %)",-12, true,  30.0f },
        { "Power fifth below (-7 + dry)",      -7, true,  45.0f },
        { "Capo 1 (+1)",                        1, false, 50.0f },
        { "Capo 2 (+2)",                        2, false, 50.0f },
        { "Capo 3 (+3)",                        3, false, 50.0f },
        { "Capo 5 (+5)",                        5, false, 50.0f },
        { "Capo 7 (+7)",                        7, false, 50.0f },
        { "Fourth up harmony (+5 + dry)",       5, true,  40.0f },
        { "Fifth up harmony (+7 + dry)",        7, true,  40.0f },
        { "Octave up (+12)",                   12, false, 50.0f },
        { "12-string (+12 + dry 30 %)",        12, true,  30.0f },
    };
    return list;
}

// ============================================================================
SemitonesProcessor::SemitonesProcessor()
    : AudioProcessor (BusesProperties()
                          .withInput  ("Input",  juce::AudioChannelSet::stereo(), true)
                          .withOutput ("Output", juce::AudioChannelSet::stereo(), true)),
      apvts (*this, nullptr, "SEMITONES", createLayout())
{
    pOn    = apvts.getRawParameterValue (ParamID::on);
    pSemis = apvts.getRawParameterValue (ParamID::semitones);
    pMixOn = apvts.getRawParameterValue (ParamID::mixOn);
    pMix   = apvts.getRawParameterValue (ParamID::mix);
    pFav   = apvts.getRawParameterValue (ParamID::fav);
    for (int i = 0; i < kNumParams; ++i)
    {
        params[i] = apvts.getParameter (kIds[i]);
        pendingValue[i].store (0.0f);
        pendingSet[i].store (false);
    }
    for (size_t i = 0; i < (size_t) MidiTarget::count; ++i)
    {
        midiCC[i].store (-1);
        courseMin[i].store (1.0f);
        courseMax[i].store (0.0f);
        momentary[i].store (false);
    }
    momentary[(size_t) MidiTarget::fav].store (true);   // the FAV jack takes a non latching switch
    lastCCValue.fill (0);
    ccMsb.fill (0);
    startTimerHz (60);
}

SemitonesProcessor::~SemitonesProcessor() { stopTimer(); }

bool SemitonesProcessor::isBusesLayoutSupported (const BusesLayout& layouts) const
{
    const auto in = layouts.getMainInputChannelSet();
    const auto out = layouts.getMainOutputChannelSet();
    if (out != juce::AudioChannelSet::mono() && out != juce::AudioChannelSet::stereo()) return false;
    if (in != juce::AudioChannelSet::mono() && in != juce::AudioChannelSet::stereo()) return false;
    return in.size() <= out.size();
}

void SemitonesProcessor::prepareToPlay (double sampleRate, int samplesPerBlock)
{
    sr = sampleRate;
    maxBlock = juce::jmax (64, samplesPerBlock);
    const int ch = juce::jmax (1, getTotalNumOutputChannels());
    shifter.prepare (sr, juce::jmin (2, ch));
    dryBuf.setSize (2, maxBlock * 2, false, true, false);
    wetBuf.setSize (2, maxBlock * 2, false, true, false);
    const auto e = getEffective();
    gOn = e.on ? 1.0f : 0.0f;
    gPass = e.semis == 0 ? 1.0f : 0.0f;
    gMixOn = e.mixOn ? 1.0f : 0.0f;
    mixLin = mix1 = mix2 = e.mix * 0.01f;
    lastParamMix = e.mix;
    mixRampLeft = 0;
    lastSemisRatio = 9999;
    setLatencySamples (0);          // like the pedal: the shifted signal is heard live
}

SemitonesProcessor::Effective SemitonesProcessor::getEffective() const
{
    Effective e;
    e.fav = pFav->load (std::memory_order_relaxed) > 0.5f;
    e.on = pOn->load (std::memory_order_relaxed) > 0.5f;
    if (e.fav)
    {
        e.semis = favSemis.load (std::memory_order_relaxed);
        e.mixOn = favMixOn.load (std::memory_order_relaxed);
        e.mix = favMix.load (std::memory_order_relaxed);
    }
    else
    {
        e.semis = (int) std::lround (pSemis->load (std::memory_order_relaxed));
        e.mixOn = pMixOn->load (std::memory_order_relaxed) > 0.5f;
        e.mix = pMix->load (std::memory_order_relaxed);
    }
    e.semis = juce::jlimit (-12, 12, e.semis);
    return e;
}

// ============================================================================
void SemitonesProcessor::processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midi)
{
    juce::ScopedNoDenormals noDenormals;
    const int n = buffer.getNumSamples();
    const int numIn = getTotalNumInputChannels();
    const int numOut = getTotalNumOutputChannels();
    for (int c = numIn; c < numOut; ++c)
        buffer.copyFrom (c, 0, buffer, 0, 0, n);      // mono in -> both outputs
    const int ch = juce::jmin (2, numOut);

    auto render = [&] (int start, int len)
    {
        while (len > 0)
        {
            const int m = juce::jmin (len, dryBuf.getNumSamples());
            const auto e = getEffective();
            if (e.semis != lastSemisRatio)
            {
                shifter.setRatio (std::pow (2.0, e.semis / 12.0));
                lastSemisRatio = e.semis;
            }
            // mix target from host / editor (MIDI ramps set lastParamMix themselves)
            if (std::abs (e.mix - lastParamMix) > 1.0e-3f)
            {
                lastParamMix = e.mix;
                const int rl = juce::jmax (1, (int) (0.015 * sr));
                mixRampStep = (e.mix * 0.01f - mixLin) / (float) rl;
                mixRampLeft = rl;
            }
            for (int c = 0; c < ch; ++c)
            {
                dryBuf.copyFrom (c, 0, buffer, c, start, m);
                wetBuf.copyFrom (c, 0, buffer, c, start, m);
            }
            float* wp[2] = { wetBuf.getWritePointer (0), wetBuf.getWritePointer (ch > 1 ? 1 : 0) };
            shifter.process (wp, ch, m);

            const float tOn = e.on ? 1.0f : 0.0f;
            const float tPass = e.semis == 0 ? 1.0f : 0.0f;
            const float tMixOn = e.mixOn ? 1.0f : 0.0f;
            const float kOnC = 1.0f - std::exp (-1.0f / (0.006f * (float) sr));
            const float kSm = 1.0f - std::exp (-1.0f / (0.012f * (float) sr));
            const float kMixLp = 1.0f - std::exp (-2.0f * 3.14159265f * 28.0f / (float) sr);
            for (int i = 0; i < m; ++i)
            {
                gOn += (tOn - gOn) * kOnC;
                gPass += (tPass - gPass) * kSm;
                gMixOn += (tMixOn - gMixOn) * kSm;
                if (mixRampLeft > 0) { mixLin += mixRampStep; --mixRampLeft; }
                mix1 += (mixLin - mix1) * kMixLp;
                mix2 += (mix1 - mix2) * kMixLp;
                const float mm = juce::jlimit (0.0f, 1.0f, mix2) * 1.5707963f;
                const float dryG = gMixOn * std::cos (mm);
                const float wetG = (1.0f - gMixOn) + gMixOn * std::sin (mm);
                for (int c = 0; c < ch; ++c)
                {
                    const float d = dryBuf.getSample (c, i);
                    const float w = gPass * d + (1.0f - gPass) * wetBuf.getSample (c, i);
                    const float y = dryG * d + wetG * w;
                    buffer.setSample (c, start + i, gOn * y + (1.0f - gOn) * d);
                }
            }
            sampleClock += m;
            start += m;
            len -= m;
        }
    };

    int pos = 0;
    for (const auto meta : midi)
    {
        const int ev = juce::jlimit (0, n, meta.samplePosition);
        if (ev > pos) { render (pos, ev - pos); pos = ev; }
        handleMidi (meta.getMessage(), 0);
    }
    if (pos < n) render (pos, n - pos);
    midi.clear();
    headDelayMs.store ((float) shifter.getCurrentDelayMs(), std::memory_order_relaxed);
}

// ============================================================================
// MIDI (audio thread: atomics only, parameters are set by the timer)
void SemitonesProcessor::queueSet (int idx, float plain)
{
    pendingValue[idx].store (plain, std::memory_order_relaxed);
    pendingSet[idx].store (true, std::memory_order_release);
}

float SemitonesProcessor::queuedOrCurrent (int idx) const
{
    if (pendingSet[idx].load (std::memory_order_acquire))
        return pendingValue[idx].load (std::memory_order_relaxed);
    const std::atomic<float>* raw[] = { pOn, pSemis, pMixOn, pMix, pFav };
    return raw[idx]->load (std::memory_order_relaxed);
}

void SemitonesProcessor::applyContinuous (MidiTarget t, float raw, int)
{
    const size_t ti = (size_t) t;
    // learn the travel of the expression pedal (0 / 100 % even on a 2..116 pedal)
    float lo = courseMin[ti].load (std::memory_order_relaxed);
    float hi = courseMax[ti].load (std::memory_order_relaxed);
    if (raw < lo) { lo = raw; courseMin[ti].store (lo, std::memory_order_relaxed); }
    if (raw > hi) { hi = raw; courseMax[ti].store (hi, std::memory_order_relaxed); }
    float x = (hi - lo) > 0.2f ? (raw - lo) / (hi - lo) : raw;
    x = juce::jlimit (0.0f, 1.0f, (x - 0.015f) / 0.97f);       // dead zones at the ends

    if (t == MidiTarget::semitones)
    {
        queueSet (kSemis, (float) juce::jlimit (-12, 12, (int) std::lround (-12.0f + 24.0f * x)));
        pendingFavExit.store (true, std::memory_order_release);
    }
    else
    {
        // ramp over the measured interval between two CCs, then 2-pole smoothing
        const int64_t now = sampleClock;
        const int64_t gap = now - lastMixCC;
        lastMixCC = now;
        int rl = gap > (int64_t) (0.25 * sr) ? (int) (0.010 * sr)
                                             : (int) juce::jlimit<int64_t> ((int64_t) (0.002 * sr), (int64_t) (0.080 * sr), gap);
        rl = juce::jmax (1, rl);
        mixRampStep = (x - mixLin) / (float) rl;
        mixRampLeft = rl;
        lastParamMix = x * 100.0f;
        queueSet (kMix, x * 100.0f);
        if (queuedOrCurrent (kMixOn) < 0.5f) queueSet (kMixOn, 1.0f);
        pendingFavExit.store (true, std::memory_order_release);
    }
}

void SemitonesProcessor::handleMidi (const juce::MidiMessage& m, int samplePos)
{
    if (! m.isController()) return;
    const int cc = m.getControllerNumber();
    const int v = m.getControllerValue();
    midiActivity.fetch_add (1, std::memory_order_relaxed);

    const int lt = learnTarget.load (std::memory_order_acquire);
    if (lt >= 0 && lt < (int) MidiTarget::count && ! (cc >= 32 && cc < 64))
    {
        midiCC[(size_t) lt].store (cc);
        courseMin[(size_t) lt].store (1.0f);
        courseMax[(size_t) lt].store (0.0f);
        learnTarget.store (-1);
        lastCCValue[(size_t) cc] = v;
        if (cc < 32) ccMsb[(size_t) cc] = v;
        return;
    }

    // 14 bit: LSB on CC n + 32 refines a continuous target mapped on CC n
    if (cc >= 32 && cc < 64)
    {
        bool used = false;
        for (auto t : { MidiTarget::semitones, MidiTarget::mix })
            if (midiCC[(size_t) t].load (std::memory_order_relaxed) == cc - 32)
            {
                applyContinuous (t, (float) (ccMsb[(size_t) (cc - 32)] * 128 + v) / 16383.0f, samplePos);
                used = true;
            }
        if (used) { lastCCValue[(size_t) cc] = v; return; }
    }
    if (cc < 32) ccMsb[(size_t) cc] = v;

    const int prev = lastCCValue[(size_t) cc];
    const bool rising = v >= 64 && prev < 64;
    for (int ti = 0; ti < (int) MidiTarget::count; ++ti)
    {
        if (midiCC[(size_t) ti].load (std::memory_order_relaxed) != cc) continue;
        const auto t = (MidiTarget) ti;
        if (isToggle (t))
        {
            const int idx = t == MidiTarget::footswitch ? kOn : (t == MidiTarget::fav ? kFav : kMixOn);
            if (momentary[(size_t) ti].load (std::memory_order_relaxed))
            {
                if (rising) queueSet (idx, queuedOrCurrent (idx) > 0.5f ? 0.0f : 1.0f);
            }
            else
                queueSet (idx, v >= 64 ? 1.0f : 0.0f);
        }
        else if (t == MidiTarget::up || t == MidiTarget::down)
        {
            if (rising) pendingSemiDelta.fetch_add (t == MidiTarget::up ? 1 : -1);
        }
        else
            applyContinuous (t, (float) v / 127.0f, samplePos);
    }
    lastCCValue[(size_t) cc] = v;
}

// ============================================================================
// message thread
void SemitonesProcessor::timerCallback()
{
    const int pp = pendingPreset.exchange (-1);
    if (pp >= 0) applyPreset (pp);
    if (pendingFavExit.exchange (false) && pFav->load() > 0.5f)
        exitFavKeeping();
    const int d = pendingSemiDelta.exchange (0);
    if (d != 0) stepSemitone (d);
    for (int i = 0; i < kNumParams; ++i)
        if (pendingSet[i].exchange (false, std::memory_order_acq_rel))
            setParam (kIds[i], pendingValue[i].load (std::memory_order_relaxed));
}

void SemitonesProcessor::setParam (const char* id, float plain)
{
    if (auto* p = apvts.getParameter (id))
    {
        const float v01 = p->convertTo0to1 (plain);
        if (std::abs (p->getValue() - v01) < 1.0e-6f) return;
        p->beginChangeGesture();
        p->setValueNotifyingHost (v01);
        p->endChangeGesture();
    }
}

void SemitonesProcessor::toggleParam (const char* id)
{
    if (auto* p = apvts.getParameter (id))
        setParam (id, p->getValue() > 0.5f ? 0.0f : 1.0f);
}

void SemitonesProcessor::exitFavKeeping()
{
    // leaving FAV by editing: start from the FAV sound
    setParam (ParamID::semitones, (float) favSemis.load());
    setParam (ParamID::mixOn, favMixOn.load() ? 1.0f : 0.0f);
    setParam (ParamID::mix, favMix.load());
    setParam (ParamID::fav, 0.0f);
}

void SemitonesProcessor::stepSemitone (int delta)
{
    if (pFav->load() > 0.5f) exitFavKeeping();
    const int s = juce::jlimit (-12, 12, (int) std::lround (pSemis->load()) + delta);
    setParam (ParamID::semitones, (float) s);
}

void SemitonesProcessor::stepMix (float delta)
{
    if (pFav->load() > 0.5f) exitFavKeeping();
    if (pMixOn->load() < 0.5f) setParam (ParamID::mixOn, 1.0f);
    setParam (ParamID::mix, juce::jlimit (0.0f, 100.0f, pMix->load() + delta));
}

void SemitonesProcessor::saveFav()
{
    const auto e = getEffective();
    favSemis.store (e.semis);
    favMixOn.store (e.mixOn);
    favMix.store (e.mix);
    setParam (ParamID::fav, 1.0f);
}

void SemitonesProcessor::applyPreset (int index)
{
    const auto& list = factoryPresets();
    if (index < 0 || index >= (int) list.size()) return;
    currentPreset = index;
    const auto& p = list[(size_t) index];
    setParam (ParamID::fav, 0.0f);
    setParam (ParamID::semitones, (float) p.semis);
    setParam (ParamID::mixOn, p.mixOn ? 1.0f : 0.0f);
    setParam (ParamID::mix, p.mix);
}

int SemitonesProcessor::getNumPrograms() { return (int) factoryPresets().size(); }

void SemitonesProcessor::setCurrentProgram (int index)
{
    // hosts may call this from any thread: the preset is applied by the
    // message-thread timer (never a parameter change from another thread)
    if (index < 0 || index >= (int) factoryPresets().size()) return;
    currentPreset = index;
    pendingPreset.store (index, std::memory_order_release);
}

const juce::String SemitonesProcessor::getProgramName (int index)
{
    const auto& list = factoryPresets();
    return index >= 0 && index < (int) list.size() ? juce::String (list[(size_t) index].name) : juce::String();
}

void SemitonesProcessor::clearMidi (MidiTarget t)
{
    midiCC[(size_t) t].store (-1);
    courseMin[(size_t) t].store (1.0f);
    courseMax[(size_t) t].store (0.0f);
}

juce::String SemitonesProcessor::targetName (MidiTarget t)
{
    switch (t)
    {
        case MidiTarget::footswitch: return "Footswitch (on / bypass)";
        case MidiTarget::fav:        return "FAV";
        case MidiTarget::mixOn:      return "MIX mode";
        case MidiTarget::up:         return "Right arrow (+1 st)";
        case MidiTarget::down:       return "Left arrow (-1 st)";
        case MidiTarget::semitones:  return "Pitch (expression)";
        case MidiTarget::mix:        return "Mix (expression)";
        default: break;
    }
    return {};
}

// ============================================================================
void SemitonesProcessor::getStateInformation (juce::MemoryBlock& dest)
{
    auto state = apvts.copyState();
    juce::ValueTree extra ("EXTRA");
    extra.setProperty ("favSemis", favSemis.load(), nullptr);
    extra.setProperty ("favMixOn", favMixOn.load(), nullptr);
    extra.setProperty ("favMix", favMix.load(), nullptr);
    extra.setProperty ("preset", currentPreset, nullptr);
    for (int i = 0; i < (int) MidiTarget::count; ++i)
    {
        extra.setProperty ("cc" + juce::String (i), midiCC[(size_t) i].load(), nullptr);
        extra.setProperty ("mom" + juce::String (i), momentary[(size_t) i].load(), nullptr);
        extra.setProperty ("cmin" + juce::String (i), courseMin[(size_t) i].load(), nullptr);
        extra.setProperty ("cmax" + juce::String (i), courseMax[(size_t) i].load(), nullptr);
    }
    state.removeChild (state.getChildWithName ("EXTRA"), nullptr);
    state.appendChild (extra, nullptr);
    if (auto xml = state.createXml())
        copyXmlToBinary (*xml, dest);
}

void SemitonesProcessor::setStateInformation (const void* data, int size)
{
    auto xml = getXmlFromBinary (data, size);
    if (xml == nullptr) return;
    auto tree = juce::ValueTree::fromXml (*xml);
    if (! tree.hasType (apvts.state.getType())) return;
    const auto extra = tree.getChildWithName ("EXTRA");
    if (extra.isValid())
    {
        favSemis.store ((int) extra.getProperty ("favSemis", -2));
        favMixOn.store ((bool) extra.getProperty ("favMixOn", false));
        favMix.store ((float) extra.getProperty ("favMix", 50.0f));
        currentPreset = (int) extra.getProperty ("preset", 0);
        for (int i = 0; i < (int) MidiTarget::count; ++i)
        {
            midiCC[(size_t) i].store ((int) extra.getProperty ("cc" + juce::String (i), -1));
            momentary[(size_t) i].store ((bool) extra.getProperty ("mom" + juce::String (i), i == (int) MidiTarget::fav));
            courseMin[(size_t) i].store ((float) extra.getProperty ("cmin" + juce::String (i), 1.0f));
            courseMax[(size_t) i].store ((float) extra.getProperty ("cmax" + juce::String (i), 0.0f));
        }
    }
    tree.removeChild (extra, nullptr);
    apvts.replaceState (tree);
}

juce::AudioProcessorEditor* SemitonesProcessor::createEditor() { return new SemitonesEditor (*this); }

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter() { return new SemitonesProcessor(); }
