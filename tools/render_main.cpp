// Offline tool: renders the Semitones editor to PNG files and runs a quick
// audio sanity check through the real processor. Linux only (CI / dev box).
#include <JuceHeader.h>
#include "PluginProcessor.h"
#include "PluginEditor.h"
#include <thread>

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
    // ---------------------------------------------------------------- presets
    {
        int okHost = 0, okBox = 0;
        const auto& list = SemitonesProcessor::factoryPresets();
        auto matches = [&] (const FactoryPreset& p)
        {
            return (int) std::lround (proc.apvts.getRawParameterValue (ParamID::semitones)->load()) == p.semis
                && (proc.apvts.getRawParameterValue (ParamID::mixOn)->load() > 0.5f) == p.mixOn
                && (! p.mixOn || std::abs (proc.apvts.getRawParameterValue (ParamID::mix)->load() - p.mix) < 0.5f)
                && proc.apvts.getRawParameterValue (ParamID::fav)->load() < 0.5f;
        };
        for (int i = 0; i < (int) list.size(); ++i)
        {
            std::thread th ([&] { proc.setCurrentProgram (i); });     // host thread
            th.join();
            proc.flushMidiQueue();
            okHost += matches (list[(size_t) i]) ? 1 : 0;
        }
        juce::ComboBox* box = nullptr;
        for (auto* c : e->getChildren())
            if (auto* cb = dynamic_cast<juce::ComboBox*> (c)) box = cb;
        for (int i = (int) list.size() - 1; i >= 0; --i)
        {
            setP (proc, ParamID::fav, 1.0f);                         // even from FAV
            dynamic_cast<PresetBox*> (box)->pick (i + 1);
            okBox += matches (list[(size_t) i]) ? 1 : 0;
            e->settleForSnapshot();                                  // display sync keeps the choice
            if (box->getSelectedId() != i + 1) printf ("preset %d: box shows %d\n", i + 1, box->getSelectedId());
        }
        // real mouse path: the popup result is delivered asynchronously by JUCE,
        // while the editor timer keeps running
        {
            int okAsync = 0;
            for (int i = 0; i < (int) list.size(); ++i)
            {
                const int start = (i + 7) % (int) list.size();
                proc.applyPreset (start);
                e->settleForSnapshot();
                // what the menu does when it closes on item i (callback of showPopup)
                e->settleForSnapshot();
                dynamic_cast<PresetBox*> (box)->pick (i + 1);
                e->settleForSnapshot();                                     // editor timer ticks
                juce::MessageManager::getInstance()->runDispatchLoopUntil (30);
                if (box->getSelectedId() != i + 1) printf ("  box shows %d instead of %d\n", box->getSelectedId(), i + 1);
                okAsync += matches (list[(size_t) i]) ? 1 : 0;
            }
            printf ("presets (mouse path): %d/%d\n", okAsync, (int) list.size());
        }
        int headings = 0;
        auto* menu = box->getRootMenu();
        for (juce::PopupMenu::MenuItemIterator it (*menu); it.next();)
            if (it.getItem().isSectionHeader) ++headings;
        // picture of the preset menu, drawn with the plug-in's own look and feel
        {
            auto& lf = e->getLookAndFeel();
            const int w = 300, itemH = 24, headH = 26;
            int h = 8;
            for (juce::PopupMenu::MenuItemIterator it (*menu); it.next();)
                h += it.getItem().isSectionHeader ? headH : itemH;
            juce::Image img (juce::Image::ARGB, w * 2, h * 2, true);
            juce::Graphics g (img);
            g.addTransform (juce::AffineTransform::scale (2.0f));
            lf.drawPopupMenuBackground (g, w, h);
            int y = 4;
            const int sel = 10;
            for (juce::PopupMenu::MenuItemIterator it (*menu); it.next();)
            {
                const auto& item = it.getItem();
                if (item.isSectionHeader)
                {
                    lf.drawPopupMenuSectionHeader (g, { 0, y, w, headH }, item.text);
                    y += headH;
                }
                else
                {
                    lf.drawPopupMenuItem (g, { 0, y, w, itemH }, false, true, item.itemID == sel + 2, item.itemID == sel,
                                          false, item.text, {}, nullptr, nullptr);
                    y += itemH;
                }
            }
            juce::File f = outDir.getChildFile ("ui_preset_menu.png");
            f.deleteFile();
            juce::FileOutputStream os (f);
            juce::PNGImageFormat().writeImageToStream (img, os);
            printf ("menu picture %dx%d\n", img.getWidth(), img.getHeight());
        }
        printf ("presets: host %d/%d  menu %d/%d  headings %d  editable %d\n", okHost, (int) list.size(), okBox, (int) list.size(),
                headings, (int) box->isTextEditable());
    }
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
