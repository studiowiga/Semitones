#pragma once
#include <JuceHeader.h>
#include "PitchShifter.h"
#include <atomic>
#include <array>

// ============================================================================
// Semitones (Studio Wiga) - replica of the Solar CHUG Capo pitch pedal
// ============================================================================
namespace ParamID
{
    static constexpr const char* on        = "on";
    static constexpr const char* semitones = "semitones";
    static constexpr const char* mixOn     = "mixOn";
    static constexpr const char* mix       = "mix";
    static constexpr const char* fav       = "fav";
}

/** Things a MIDI controller can be learned to. */
enum class MidiTarget : int
{
    footswitch = 0,  // effect on / bypass
    fav,             // FAV mode (FAV jack)
    mixOn,           // MIX mode on / off
    up,              // right arrow (+1 semitone)
    down,            // left arrow (-1 semitone)
    semitones,       // expression pedal -> -12 .. +12
    mix,             // expression pedal -> mix 0 .. 100 %
    count
};

struct FactoryPreset
{
    const char* name;
    int semis;
    bool mixOn;
    float mix;
};

class SemitonesProcessor : public juce::AudioProcessor,
                           private juce::Timer
{
public:
    SemitonesProcessor();
    ~SemitonesProcessor() override;

    void prepareToPlay (double sampleRate, int samplesPerBlock) override;
    void releaseResources() override {}
    bool isBusesLayoutSupported (const BusesLayout&) const override;
    void processBlock (juce::AudioBuffer<float>&, juce::MidiBuffer&) override;
    using AudioProcessor::processBlock;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }

    const juce::String getName() const override { return "Semitones"; }
    bool acceptsMidi() const override { return true; }
    bool producesMidi() const override { return false; }
    bool isMidiEffect() const override { return false; }
    double getTailLengthSeconds() const override { return 0.05; }

    int getNumPrograms() override;
    int getCurrentProgram() override { return currentPreset; }
    void setCurrentProgram (int) override;
    const juce::String getProgramName (int) override;
    void changeProgramName (int, const juce::String&) override {}

    void getStateInformation (juce::MemoryBlock&) override;
    void setStateInformation (const void*, int) override;

    juce::AudioProcessorValueTreeState apvts;
    static juce::AudioProcessorValueTreeState::ParameterLayout createLayout();

    // ------------------------------------------------ message-thread actions
    // (used by the editor and by the MIDI queue; never call from audio)
    void stepSemitone (int delta);
    void stepMix (float deltaPercent);
    void toggleParam (const char* id);
    void setParam (const char* id, float plainValue);
    void saveFav();                       // store the current sound as FAV and engage FAV
    void exitFavKeeping();                // leave FAV, keeping the FAV sound as current
    void applyPreset (int index);

    struct Effective { int semis; bool mixOn; float mix; bool fav; bool on; };
    Effective getEffective() const;

    // FAV memory (one slot, like the pedal)
    std::atomic<int>   favSemis { -2 };
    std::atomic<bool>  favMixOn { false };
    std::atomic<float> favMix   { 50.0f };

    // --------------------------------------------------------------- MIDI map
    std::atomic<int> learnTarget { -1 };
    std::array<std::atomic<int>, (size_t) MidiTarget::count> midiCC;
    std::array<std::atomic<bool>, (size_t) MidiTarget::count> momentary; // toggles: true = momentary
    std::array<std::atomic<float>, (size_t) MidiTarget::count> courseMin, courseMax;
    void clearMidi (MidiTarget t);
    static juce::String targetName (MidiTarget t);
    static bool isToggle (MidiTarget t) { return t == MidiTarget::footswitch || t == MidiTarget::fav || t == MidiTarget::mixOn; }
    static bool isContinuous (MidiTarget t) { return t == MidiTarget::semitones || t == MidiTarget::mix; }

    static const std::vector<FactoryPreset>& factoryPresets();
    int currentPreset = 0;

    // read-outs for the editor
    std::atomic<float> headDelayMs { 0.0f };
    std::atomic<int> midiActivity { 0 };
    void flushMidiQueue() { timerCallback(); }   // message thread

private:
    void timerCallback() override;             // flushes the MIDI -> parameter queue
    void handleMidi (const juce::MidiMessage& m, int samplePos);
    void applyContinuous (MidiTarget t, float raw01, int samplePos);
    void queueSet (int idx, float plain);
    float queuedOrCurrent (int idx) const;

    sw::PitchShifter shifter;
    double sr = 48000.0;
    int maxBlock = 512;
    juce::AudioBuffer<float> dryBuf, wetBuf;

    // raw parameter pointers (no string look-up in the audio thread)
    std::atomic<float>* pOn = nullptr;
    std::atomic<float>* pSemis = nullptr;
    std::atomic<float>* pMixOn = nullptr;
    std::atomic<float>* pMix = nullptr;
    std::atomic<float>* pFav = nullptr;
    juce::RangedAudioParameter* params[5] {};

    // audio -> message thread queue
    std::atomic<float> pendingValue[5];
    std::atomic<bool>  pendingSet[5];
    std::atomic<int>   pendingSemiDelta { 0 };
    std::atomic<bool>  pendingFavExit { false };

    // smoothing state (audio thread)
    float gOn = 1.0f, gPass = 1.0f, gMixOn = 0.0f;
    float mixLin = 0.5f, mixRampStep = 0.0f, mix1 = 0.5f, mix2 = 0.5f;
    int mixRampLeft = 0;
    float lastParamMix = -1.0f;
    int64_t sampleClock = 0, lastMixCC = -1000000;
    int lastSemisRatio = 9999;
    std::array<int, 128> lastCCValue {};
    std::array<int, 32> ccMsb {};

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (SemitonesProcessor)
};
