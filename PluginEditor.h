#pragma once
#include <JuceHeader.h>
#include "PluginProcessor.h"
#include "Layout.h"
#include <unordered_map>
#include <string>

class SemitonesLook : public juce::LookAndFeel_V4
{
public:
    SemitonesLook();
    void setTypeface (juce::Typeface::Ptr t) { face = t; }
    juce::Font uiFont (float h) const;
    void drawComboBox (juce::Graphics&, int w, int h, bool down, int, int, int, int, juce::ComboBox&) override;
    juce::Font getComboBoxFont (juce::ComboBox&) override;
    void positionComboBoxText (juce::ComboBox&, juce::Label&) override;
    juce::Font getPopupMenuFont() override;
    void drawPopupMenuBackground (juce::Graphics&, int w, int h) override;
    void drawPopupMenuItem (juce::Graphics&, const juce::Rectangle<int>&, bool isSeparator, bool isActive,
                            bool isHighlighted, bool isTicked, bool hasSubMenu, const juce::String& text,
                            const juce::String& shortcutKeyText, const juce::Drawable* icon,
                            const juce::Colour* textColour) override;
    void drawPopupMenuSectionHeader (juce::Graphics&, const juce::Rectangle<int>&, const juce::String&) override;
private:
    juce::Typeface::Ptr face;
};

/** Preset menu: the chosen preset is applied immediately (synchronously) when
    the menu closes. The stock ComboBox reports the choice later through an
    async notification, which could be overwritten by the display refresh. */
class PresetBox : public juce::ComboBox
{
public:
    std::function<void (int)> onPick;
    void showPopup() override;
    void pick (int itemId);
};

class SemitonesEditor : public juce::AudioProcessorEditor,
                        private juce::Timer
{
public:
    explicit SemitonesEditor (SemitonesProcessor&);
    ~SemitonesEditor() override;

    void paint (juce::Graphics&) override;
    void resized() override;
    void parentHierarchyChanged() override;
    void visibilityChanged() override;

    void mouseDown (const juce::MouseEvent&) override;
    void mouseUp (const juce::MouseEvent&) override;
    void mouseDrag (const juce::MouseEvent&) override;
    void mouseMove (const juce::MouseEvent&) override;
    void mouseExit (const juce::MouseEvent&) override;
    void mouseWheelMove (const juce::MouseEvent&, const juce::MouseWheelDetails&) override;

    /** Offline rendering helper (tools/render): force a visual state. */
    void setPreviewState (bool leftDown, bool rightDown, bool mixDown, bool favDown, bool footDown, bool adjustMix);
    void settleForSnapshot();

private:
    enum class Hit { none, left, right, mix, fav, foot, display, background };

    struct Sprite { juce::Image img; juce::Rectangle<float> r; };

    void timerCallback() override;
    Hit hitTest (juce::Point<float> logical) const;
    juce::Point<float> toLogical (juce::Point<float> p) const { return p / scale(); }
    float scale() const { return (float) getWidth() / Layout::W; }
    juce::Rectangle<int> toScreen (juce::Rectangle<float> r, float grow = 2.0f) const;
    const Sprite* sprite (const std::string& name) const;
    void drawSprite (juce::Graphics&, const std::string& name, float opacity = 1.0f) const;

    uint32_t computeSegments() const;
    void stepAction (int dir);
    void showMenu (Hit h);
    juce::String statusText() const;
    juce::String hintFor (Hit h) const;
    void askRepaint (juce::Rectangle<int> r);
    void useSoftwareRenderer();
    void rebuildCache();
    void syncPresetBox();

    SemitonesProcessor& proc;
    SemitonesLook look;
    juce::Typeface::Ptr face;
    PresetBox presetBox;
    double lastPresetPickMs = 0;

    juce::Image bgImage, bgCache;
    float cacheScale = 0.0f;
    std::unordered_map<std::string, Sprite> sprites;
    std::vector<std::string> segNames;              // bit order of the display mask

    // interaction state
    bool downLeft = false, downRight = false, downMix = false, downFav = false, downFoot = false;
    double tDown = 0, nextRepeat = 0;
    bool longDone = false;
    bool mixAdjust = false;
    double mixAdjustLast = 0;
    double favBlinkUntil = 0;
    float dragAccum = 0;
    Hit hover = Hit::none;
    double hoverSince = 0;

    // drawn state (redraw only what changed)
    uint32_t segMask = 0, drawnSegMask = 0xffffffffu;
    float led[1] { 0 }, drawnLed[1] { -1 };   // footswitch light ring
    float ringAngle = 0.0f;                  // rotating light (radians)
    int drawnPressed = -1;
    juce::String drawnStatus;
    double blinkPhase = 0;

    // anti-freeze v2
    void* lastPeer = nullptr;
    double lastPaintMs = 0, pendingSince = 0, lastRendererCheck = 0, lastScaleCheck = 0;
    int resizeSettle = 0;
    float lastDisplayScale = 0.0f;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (SemitonesEditor)
};
