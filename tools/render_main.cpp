// Offline tool: renders the Semitones editor to PNG files and runs a quick
// audio sanity check through the real processor. Linux only (CI / dev box).
#include <JuceHeader.h>
#include "PluginProcessor.h"
#include "PluginEditor.h"

struct Shot
{
    const char* file; int semis; bool mixOn; float mix; bool fav; bool on;
    bool l, r, mx, fv, ft, adjust;
};

static void setP (SemitonesProcessor& p, const char* id, float v) { p.setParam (id, v); }

int main (int argc, char** argv)
{
    juce::ScopedJuceInitialiser_GUI gui;
    const juce::File outDir (argc > 1 ? juce::String (argv[1]) : juce::File::getCurrentWorkingDirectory().getFullPathName());
    outDir.createDirectory();

    SemitonesProcessor proc;
    proc.setPlayConfigDetails (2, 2, 48000.0, 256);
    proc.prepareToPlay (48000.0, 256);

    // ---------------------------------------------------------------- audio
    {
        juce::AudioBuffer<float> buf (2, 256);
        juce::MidiBuffer midi;
        juce::Random rnd (3);
        std::vector<float> line ((size_t) std::lround (48000.0 / 82.41));
        for (auto& v : line) v = rnd.nextFloat() * 2.0f - 1.0f;
        size_t idx = 0; float prev = 0;
        auto run = [&] (int blocks, double& rmsIn, double& rmsOut)
        {
            rmsIn = rmsOut = 0;
            const auto t0 = juce::Time::getMillisecondCounterHiRes();
            for (int b = 0; b < blocks; ++b)
            {
                for (int i = 0; i < 256; ++i)
                {
                    const float x = line[idx];
                    const float y = 0.4993f * (x + prev);
                    prev = x; line[idx] = y; idx = (idx + 1) % line.size();
                    buf.setSample (0, i, 0.3f * x); buf.setSample (1, i, 0.3f * x);
                    rmsIn += 0.09 * x * x;
                }
                proc.processBlock (buf, midi);
                for (int i = 0; i < 256; ++i) rmsOut += buf.getSample (0, i) * buf.getSample (0, i);
            }
            rmsIn = std::sqrt (rmsIn / (blocks * 256.0)); rmsOut = std::sqrt (rmsOut / (blocks * 256.0));
            return juce::Time::getMillisecondCounterHiRes() - t0;
        };
        struct T { const char* name; int s; bool mo; float m; bool on; };
        for (auto t : { T { "bypass", -12, false, 50, false }, T { "0 st", 0, false, 50, true }, T { "-12 st", -12, false, 50, true },
                        T { "-12 mix50", -12, true, 50, true }, T { "+7 st", 7, false, 50, true }, T { "+12 mix30", 12, true, 30, true } })
        {
            setP (proc, ParamID::on, t.on ? 1.0f : 0.0f);
            setP (proc, ParamID::semitones, (float) t.s);
            setP (proc, ParamID::mixOn, t.mo ? 1.0f : 0.0f);
            setP (proc, ParamID::mix, t.m);
            double a, b;
            run (40, a, b);                       // settle
            const double ms = run (375, a, b);    // 2 s of audio
            printf ("audio %-10s in %.4f out %.4f  (%.1f x real time, head %.2f ms)\n", t.name, a, b, 2000.0 / ms, proc.headDelayMs.load());
        }
        // MIDI: learn CC 11 as mix expression, then sweep
        proc.learnTarget.store ((int) MidiTarget::mix);
        midi.addEvent (juce::MidiMessage::controllerEvent (1, 11, 10), 0);
        proc.processBlock (buf, midi); midi.clear();
        for (int v = 2; v <= 116; v += 6) { midi.addEvent (juce::MidiMessage::controllerEvent (1, 11, v), 10); proc.processBlock (buf, midi); midi.clear(); }
        proc.flushMidiQueue();
        printf ("midi: mix CC=%d  mix param=%.1f  mixOn=%.0f\n", proc.midiCC[(size_t) MidiTarget::mix].load(),
                proc.apvts.getRawParameterValue (ParamID::mix)->load(), proc.apvts.getRawParameterValue (ParamID::mixOn)->load());
    }

    // ---------------------------------------------------------------- pictures
    std::unique_ptr<juce::AudioProcessorEditor> ed (proc.createEditor());
    auto* e = dynamic_cast<SemitonesEditor*> (ed.get());
    const Shot shots[] = {
        { "ui_default.png",        0, false, 50, false, true,  false, false, false, false, false, false },
        { "ui_plus4.png",          4, false, 50, false, true,  false, false, false, false, false, false },
        { "ui_minus12_mix.png",  -12, true,  50, false, true,  false, false, false, false, false, false },
        { "ui_mix_adjust.png",    -5, true, 100, false, true,  false, false, true,  false, false, true  },
        { "ui_fav.png",           -2, false, 50, true,  true,  false, false, false, false, false, false },
        { "ui_bypass_press.png",   7, false, 50, false, false, true,  false, false, false, true,  false },
    };
    for (const auto& s : shots)
    {
        setP (proc, ParamID::fav, 0.0f);
        setP (proc, ParamID::semitones, (float) s.semis);
        setP (proc, ParamID::mixOn, s.mixOn ? 1.0f : 0.0f);
        setP (proc, ParamID::mix, s.mix);
        setP (proc, ParamID::on, s.on ? 1.0f : 0.0f);
        if (s.fav) { proc.favSemis.store (s.semis); proc.favMixOn.store (s.mixOn); proc.favMix.store (s.mix); setP (proc, ParamID::fav, 1.0f); }
        e->setPreviewState (s.l, s.r, s.mx, s.fv, s.ft, s.adjust);
        e->settleForSnapshot();
        auto img = e->createComponentSnapshot (e->getLocalBounds(), true, 4.0f);
        juce::File f = outDir.getChildFile (s.file);
        f.deleteFile();
        juce::FileOutputStream os (f);
        juce::PNGImageFormat().writeImageToStream (img, os);
        printf ("wrote %s (%dx%d)\n", f.getFullPathName().toRawUTF8(), img.getWidth(), img.getHeight());
    }
    ed.reset();
    return 0;
}
