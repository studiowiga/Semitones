#include "PluginEditor.h"
#include "BinaryData.h"

namespace
{
    double nowMs() { return juce::Time::getMillisecondCounterHiRes(); }

    const juce::Colour kInk     { 0xffd9dadc };
    const juce::Colour kInkDim  { 0xff8d8f94 };
    const juce::Colour kAccent  { 0xff39a0ff };    // display blue
    const juce::Colour kBar     { 0xff141416 };

    juce::Image loadPng (const char* resource)
    {
        int size = 0;
        if (auto* data = BinaryData::getNamedResource (resource, size))
            return juce::ImageCache::getFromMemory (data, size);
        return {};
    }

    constexpr const char* kDigits[10] = { "abcdef", "bc", "abdeg", "abcdg", "bcfg", "acdfg", "acdefg", "abc", "abcdefg", "abcdfg" };
    constexpr float kMixHoldMs = 600.0f, kFavHoldMs = 900.0f;
}

// ============================================================================
// Look and feel (preset menu / pop-up menus)
SemitonesLook::SemitonesLook()
{
    setColour (juce::PopupMenu::backgroundColourId, juce::Colour (0xff1b1c1f));
    setColour (juce::PopupMenu::textColourId, kInk);
    setColour (juce::PopupMenu::highlightedBackgroundColourId, juce::Colour (0xff23415f));
    setColour (juce::PopupMenu::highlightedTextColourId, juce::Colours::white);
    setColour (juce::ComboBox::textColourId, kInk);
    setColour (juce::ComboBox::backgroundColourId, juce::Colour (0xff1c1d20));
    setColour (juce::ComboBox::outlineColourId, juce::Colour (0xff34363b));
    setColour (juce::ComboBox::arrowColourId, kInkDim);
}

juce::Font SemitonesLook::uiFont (float h) const
{
    if (face != nullptr) return juce::Font (juce::FontOptions (face).withHeight (h));
    return juce::Font (juce::FontOptions (h));
}

void SemitonesLook::drawComboBox (juce::Graphics& g, int w, int h, bool down, int, int, int, int, juce::ComboBox& box)
{
    // sits in the slot milled in the pedal (baked in the background): translucent
    // smoked panel, so the recess and its shadow stay visible around the text
    auto r = juce::Rectangle<float> (0.5f, 0.5f, (float) w - 1.0f, (float) h - 1.0f);
    const float rad = r.getHeight() * 0.5f;
    juce::ColourGradient grad (juce::Colour (0xc0141518), 0, 0, juce::Colour (0xd00c0d0f), 0, (float) h, false);
    g.setGradientFill (grad);
    g.fillRoundedRectangle (r.reduced (1.0f), rad);
    g.setColour (box.isMouseOver (true) || down ? juce::Colour (0xff3f86c8) : juce::Colour (0x40ffffff));
    g.drawRoundedRectangle (r.reduced (1.0f), rad, 1.0f);
    // chevron
    const float cs = (float) h * 0.16f;
    const float cx = (float) w - rad - 2.0f, cy = (float) h * 0.5f;
    juce::Path p;
    p.startNewSubPath (cx - cs, cy - cs * 0.5f);
    p.lineTo (cx, cy + cs * 0.6f);
    p.lineTo (cx + cs, cy - cs * 0.5f);
    g.setColour (kInk.withAlpha (0.75f));
    g.strokePath (p, juce::PathStrokeType (juce::jmax (1.5f, (float) h * 0.06f), juce::PathStrokeType::curved, juce::PathStrokeType::rounded));
}

juce::Font SemitonesLook::getComboBoxFont (juce::ComboBox& b) { return uiFont (juce::jlimit (11.0f, 30.0f, (float) b.getHeight() * 0.62f)); }

void SemitonesLook::positionComboBoxText (juce::ComboBox& box, juce::Label& label)
{
    label.setBounds (box.getHeight() / 2, 1, box.getWidth() - box.getHeight() * 2, box.getHeight() - 2);
    label.setInterceptsMouseClicks (false, false);
    label.setEditable (false, false, false);
    label.setFont (getComboBoxFont (box));
    label.setJustificationType (juce::Justification::centred);
    label.setMinimumHorizontalScale (0.72f);   // long names squeeze slightly instead of being cut
}

juce::Font SemitonesLook::getPopupMenuFont() { return uiFont (18.0f); }

void SemitonesLook::drawPopupMenuBackground (juce::Graphics& g, int w, int h)
{
    g.fillAll (findColour (juce::PopupMenu::backgroundColourId));
    g.setColour (juce::Colour (0xff34363b));
    g.drawRect (0, 0, w, h);
}

void SemitonesLook::drawPopupMenuItem (juce::Graphics& g, const juce::Rectangle<int>& area, bool isSeparator, bool isActive,
                                       bool isHighlighted, bool isTicked, bool hasSubMenu, const juce::String& text,
                                       const juce::String& shortcut, const juce::Drawable* icon, const juce::Colour* tc)
{
    if (isSeparator)
    {
        g.setColour (juce::Colour (0xff34363b));
        g.fillRect (area.reduced (8, 0).withHeight (1).withY (area.getCentreY()));
        return;
    }
    LookAndFeel_V4::drawPopupMenuItem (g, area, false, isActive, isHighlighted, isTicked, hasSubMenu, text, shortcut, icon, tc);
}

void SemitonesLook::drawPopupMenuSectionHeader (juce::Graphics& g, const juce::Rectangle<int>& area, const juce::String& name)
{
    g.setFont (uiFont (14.0f));
    g.setColour (kAccent.withAlpha (0.9f));
    g.drawFittedText (name.toUpperCase(), area.reduced (12, 0).withTrimmedTop (4), juce::Justification::bottomLeft, 1);
}

// ============================================================================
void PresetBox::showPopup()
{
    if (! isEnabled())
        return;
    auto menu = *getRootMenu();
    const int sel = getSelectedId();
    for (juce::PopupMenu::MenuItemIterator it (menu, true); it.next();)
    {
        auto& item = it.getItem();
        if (item.itemID != 0)
            item.isTicked = (item.itemID == sel);
    }
    auto& lf = getLookAndFeel();
    menu.setLookAndFeel (&lf);
    // always open at the same place, right under the box, whatever the current
    // preset (the stock combo box shifts the menu so the selected item sits on
    // the box, which pushes it off screen for presets at the bottom of the list)
    auto options = juce::PopupMenu::Options().withTargetComponent (this)
                                             .withMinimumWidth (getWidth())
                                             .withMaximumNumColumns (1)
                                             .withPreferredPopupDirection (juce::PopupMenu::Options::PopupDirection::downwards)
                                             .withStandardItemHeight (juce::jlimit (22, 30, juce::roundToInt ((float) getHeight() * 0.75f)));
    juce::Component::SafePointer<PresetBox> safe (this);
    menu.showMenuAsync (options, [safe] (int result)
    {
        if (safe == nullptr)
            return;
        safe->hidePopup();
        if (result > 0)
            safe->pick (result);
    });
}

void PresetBox::pick (int itemId)
{
    setSelectedId (itemId, juce::dontSendNotification);
    if (onPick != nullptr)
        onPick (itemId);
}

// ============================================================================
SemitonesEditor::SemitonesEditor (SemitonesProcessor& p)
    : AudioProcessorEditor (p), proc (p)
{
    setOpaque (true);
    face = juce::Typeface::createSystemTypefaceFor (BinaryData::PoppinsMedium_ttf, BinaryData::PoppinsMedium_ttfSize);
    look.setTypeface (face);
    setLookAndFeel (&look);

    bgImage = loadPng ("background_jpg");
    for (const auto& s : Layout::sprites)
    {
        Sprite sp;
        sp.img = loadPng ((juce::String (s.name) + "_png").toRawUTF8());
        sp.r = { s.r.x, s.r.y, s.r.w, s.r.h };
        sprites[s.name] = sp;
    }
    for (auto n : { "s_l", "s_r", "s_u", "s_d" }) segNames.push_back (std::string ("seg_") + n);
    for (char c = 'a'; c <= 'g'; ++c) segNames.push_back (std::string ("seg_t_") + c);
    for (char c = 'a'; c <= 'g'; ++c) segNames.push_back (std::string ("seg_u_") + c);
    segNames.push_back ("seg_mix");   // MIX indicator dash, above the MIX button

    // preset menu
    // grouped list: section headers are titles only (not selectable), every
    // preset item is selectable; the box itself is never an editable text field
    const auto& presets = SemitonesProcessor::factoryPresets();
    for (int i = 0; i < (int) presets.size(); ++i)
    {
        const auto& p = presets[(size_t) i];
        const auto& prev = presets[(size_t) juce::jmax (0, i - 1)];
        auto group = [] (const FactoryPreset& fp)
        {
            if (fp.semis == 0) return 0;
            if (fp.semis < 0 && ! fp.mixOn) return 1;
            if (fp.semis < 0) return 2;
            if (! fp.mixOn && fp.semis < 12) return 3;
            return 4;
        };
        static const char* titles[] = { "Standard", "Tune down", "Blend below (MIX)", "Capo up", "Harmonies / octave up" };
        if (i == 0 || group (p) != group (prev))
            presetBox.addSectionHeading (titles[group (p)]);
        presetBox.addItem (p.name, i + 1);
    }
    presetBox.setEditableText (false);
    presetBox.setTextWhenNothingSelected ("Custom");
    presetBox.setTextWhenNoChoicesAvailable ("Custom");
    presetBox.setWantsKeyboardFocus (false);
    presetBox.setMouseClickGrabsKeyboardFocus (false);
    presetBox.setScrollWheelEnabled (false);
    presetBox.setTooltip ("Factory presets");
    presetBox.onPick = [this] (int id)
    {
        lastPresetPickMs = nowMs();
        proc.applyPreset (id - 1);         // immediate: parameters are set right now
        syncPresetBox();
        timerCallback();                   // display / status / ring follow at once
    };
    addAndMakeVisible (presetBox);
    syncPresetBox();

    setResizable (true, true);
    // default size = minimum size (simple pedal format, like Echoflex / Holyverb)
    const int defW = Layout::defaultW;   // 391 x 493
    const int defH = Layout::defaultH;
    setResizeLimits (defW, defH, defW * 2, defH * 2);
    if (auto* c = getConstrainer())
        c->setFixedAspectRatio ((double) defW / (double) defH);
    setSize (defW, defH);

    const auto e = proc.getEffective();
    if (e.on) led[0] = 1.0f;
    segMask = computeSegments();
    startTimerHz (30);
}

SemitonesEditor::~SemitonesEditor()
{
    stopTimer();
    setLookAndFeel (nullptr);
}

// ---------------------------------------------------------------- helpers
juce::Rectangle<int> SemitonesEditor::toScreen (juce::Rectangle<float> r, float grow) const
{
    const float s = scale();
    return (r * s).expanded (grow * s).getSmallestIntegerContainer();
}

const SemitonesEditor::Sprite* SemitonesEditor::sprite (const std::string& name) const
{
    auto it = sprites.find (name);
    return it == sprites.end() ? nullptr : &it->second;
}

void SemitonesEditor::drawSprite (juce::Graphics& g, const std::string& name, float opacity) const
{
    if (opacity <= 0.002f) return;
    if (auto* sp = sprite (name))
    {
        if (! sp->img.isValid()) return;
        g.setOpacity (juce::jlimit (0.0f, 1.0f, opacity));
        g.drawImage (sp->img, sp->r * scale(), juce::RectanglePlacement::stretchToFit);
    }
}

SemitonesEditor::Hit SemitonesEditor::hitTest (juce::Point<float> p) const
{
    auto inCircle = [&] (float x, float y, float r) { return p.getDistanceFrom ({ x, y }) <= r; };
    auto inRect = [&] (const Layout::R& r) { return juce::Rectangle<float> (r.x, r.y, r.w, r.h).contains (p); };
    if (inCircle (Layout::footX, Layout::footY, Layout::footR)) return Hit::foot;
    if (inCircle (Layout::mixX, Layout::mixY, Layout::mixR)) return Hit::mix;
    if (inCircle (Layout::favX, Layout::favY, Layout::favR)) return Hit::fav;
    if (inRect (Layout::hitLeft)) return Hit::left;
    if (inRect (Layout::hitRight)) return Hit::right;
    if (inRect (Layout::hitDisplay)) return Hit::display;
    return Hit::background;
}

uint32_t SemitonesEditor::computeSegments() const
{
    const auto e = proc.getEffective();
    const double t = nowMs();
    uint32_t m = 0;
    auto set = [&] (const std::string& n)
    {
        for (size_t i = 0; i < segNames.size(); ++i)
            if (segNames[i] == n) { m |= (1u << i); return; }
    };
    auto digit = [&] (char pos, int d)
    {
        if (d < 0 || d > 9) return;
        for (const char* c = kDigits[d]; *c; ++c) set (std::string ("seg_") + pos + "_" + *c);
    };
    const bool blinkOn = std::fmod (blinkPhase, 1.0) < 0.5;

    bool showValue = true;
    if (t < favBlinkUntil) showValue = std::fmod ((favBlinkUntil - t) / 180.0, 1.0) > 0.45;

    if (showValue)
    {
        if (mixAdjust)
        {
            const int n = juce::jlimit (0, 100, (int) std::lround (e.mix));
            if (n == 100) { set ("seg_s_u"); set ("seg_s_d"); digit ('t', 0); digit ('u', 0); }
            else
            {
                if (n >= 10) digit ('t', n / 10);
                digit ('u', n % 10);
            }
        }
        else
        {
            const int s = e.semis;
            if (s != 0) { set ("seg_s_l"); set ("seg_s_r"); }
            if (s > 0) { set ("seg_s_u"); set ("seg_s_d"); }
            const int a = std::abs (s);
            if (a >= 10) digit ('t', a / 10);
            digit ('u', a % 10);
        }
    }
    // MIX indicator: blue dash above the MIX button while MIX mode is on
    // (flashes while the mix is being adjusted)
    if ((e.mixOn && ! mixAdjust) || (mixAdjust && blinkOn))
        set ("seg_mix");
    return m;
}

// ---------------------------------------------------------------- painting
void SemitonesEditor::paint (juce::Graphics& g)
{
    lastPaintMs = nowMs();
    pendingSince = 0;
    g.fillAll (kBar);
    const auto bounds = getLocalBounds().toFloat();
    g.setImageResamplingQuality (juce::Graphics::highResamplingQuality);
    if (bgCache.isValid())
        g.drawImage (bgCache, bounds, juce::RectanglePlacement::stretchToFit);
    else if (bgImage.isValid())
        g.drawImage (bgImage, bounds, juce::RectanglePlacement::stretchToFit);

    // footswitch light: blue ring with a glowing light turning around it
    if (led[0] > 0.003f)
    {
        // steady blue ring + its light on the faceplate, then the rotating light and its halo
        drawSprite (g, "ringlight", led[0]);
        drawSprite (g, "ring_lit", led[0]);
        if (auto* sp = sprite ("ring_comet"))
            if (sp->img.isValid())
            {
                const float s = scale();
                const auto t = juce::AffineTransform::scale (sp->r.getWidth() * s / (float) sp->img.getWidth(),
                                                             sp->r.getHeight() * s / (float) sp->img.getHeight())
                                   .translated (sp->r.getX() * s, sp->r.getY() * s)
                                   .rotated (ringAngle, Layout::ringX * s, Layout::ringY * s);
                g.setOpacity (juce::jlimit (0.0f, 1.0f, led[0]));
                g.drawImageTransformed (sp->img, t);
            }
    }

    // pressed controls
    if (downLeft)  drawSprite (g, "press_left");
    if (downRight) drawSprite (g, "press_right");
    if (downMix)   drawSprite (g, "press_mix");
    if (downFav)   drawSprite (g, "press_fav");
    if (downFoot)  drawSprite (g, "press_foot");

    // display
    for (size_t i = 0; i < segNames.size(); ++i)
        if (segMask & (1u << i))
            drawSprite (g, segNames[i]);
    g.setOpacity (1.0f);

    // preset label + status line (inside the pill of the design)
    const float s = scale();
    const auto status = statusText();
    const auto st = Layout::statusBox;
    auto sr = juce::Rectangle<float> (st.x * s, st.y * s, st.w * s, st.h * s);
    g.setFont (look.uiFont (st.h * 0.74f * s));
    g.setColour (juce::Colour (0xffa4a7ac));
    g.drawFittedText (status, sr.reduced (12.0f * s, 0).toNearestInt(), juce::Justification::centred, 1, 0.6f);
}

juce::String SemitonesEditor::statusText() const
{
    const int lt = proc.learnTarget.load();
    if (lt >= 0)
        return "MIDI LEARN  -  move a controller for: " + SemitonesProcessor::targetName ((MidiTarget) lt);
    if (hover != Hit::none && hover != Hit::background && nowMs() - hoverSince < 2500.0)
        return hintFor (hover);
    const auto e = proc.getEffective();
    juce::String st = e.semis > 0 ? "+" + juce::String (e.semis) : juce::String (e.semis);
    st = st.replace ("-", juce::String::fromUTF8 ("\xe2\x88\x92"));
    juce::String txt;
    txt << "PITCH  " << st << " st     MIX  " << juce::String ((int) std::lround (e.mix)) << " %"
        << (e.mixOn ? "  ON" : "  OFF")
        << "     FAV  " << (e.fav ? "ON" : "OFF");
    if (! e.on) txt << "     BYPASS";
    return txt;
}

juce::String SemitonesEditor::hintFor (Hit h) const
{
    switch (h)
    {
        case Hit::left:    return mixAdjust ? "Lower the mix" : "Lower the pitch one semitone (hold to repeat)";
        case Hit::right:   return mixAdjust ? "Raise the mix" : "Raise the pitch one semitone (hold to repeat)";
        case Hit::mix:     return "MIX: click = mix mode on/off   -   hold = adjust the mix with the arrows";
        case Hit::fav:     return "FAV: click = recall / leave FAV   -   hold = save the current sound as FAV";
        case Hit::foot:    return "Footswitch: effect on / bypass (blue ring = on)   -   right click: MIDI";
        case Hit::display: return "Drag or scroll to change the pitch   -   right click: MIDI";
        default: break;
    }
    return {};
}

void SemitonesEditor::resized()
{
    // never setSize() here (Windows scaling loops) - the constrainer does the job
    const float s = scale();
    presetBox.setBounds (juce::Rectangle<float> (Layout::presetBox.x * s, Layout::presetBox.y * s, Layout::presetBox.w * s, Layout::presetBox.h * s).toNearestInt());
    resizeSettle = 4;
}

void SemitonesEditor::rebuildCache()
{
    if (! bgImage.isValid() || getWidth() <= 0) return;
    const float ds = juce::Component::getApproximateScaleFactorForComponent (this);
    const int pw = juce::jmax (1, juce::roundToInt ((float) getWidth() * ds));
    const int ph = juce::jmax (1, juce::roundToInt ((float) getHeight() * ds));
    if (bgCache.isValid() && bgCache.getWidth() == pw && bgCache.getHeight() == ph) return;
    if (pw == bgImage.getWidth() && ph == bgImage.getHeight())
        bgCache = bgImage;
    else
        bgCache = bgImage.rescaled (pw, ph, juce::Graphics::highResamplingQuality);
    cacheScale = ds;
    repaint();
}

// ---------------------------------------------------------------- anti-freeze
void SemitonesEditor::useSoftwareRenderer()
{
   #if JUCE_WINDOWS
    if (auto* peer = getPeer())
    {
        const auto engines = peer->getAvailableRenderingEngines();
        int idx = engines.indexOf ("Software Renderer");
        if (idx < 0) idx = 0;
        if (peer->getCurrentRenderingEngine() != idx)
            peer->setCurrentRenderingEngine (idx);
        if ((void*) peer != lastPeer)
        {
            lastPeer = (void*) peer;
            repaint();
        }
    }
   #else
    lastPeer = (void*) getPeer();
   #endif
}

void SemitonesEditor::parentHierarchyChanged() { useSoftwareRenderer(); }

void SemitonesEditor::visibilityChanged()
{
    useSoftwareRenderer();
    if (isShowing()) repaint();
}

void SemitonesEditor::askRepaint (juce::Rectangle<int> r)
{
    if (pendingSince == 0) pendingSince = nowMs();
    repaint (r);
}

void SemitonesEditor::syncPresetBox()
{
    if (presetBox.isPopupActive())
        return;                            // never touch the box while its menu is open
    const auto e = proc.getEffective();
    const auto& list = SemitonesProcessor::factoryPresets();
    int id = 0;
    const int cur = proc.currentPreset;
    auto matches = [&] (const FactoryPreset& p)
    {
        return ! e.fav && p.semis == e.semis && p.mixOn == e.mixOn && (! p.mixOn || std::abs (p.mix - e.mix) < 0.5f);
    };
    if (cur >= 0 && cur < (int) list.size() && matches (list[(size_t) cur])) id = cur + 1;
    else
        for (int i = 0; i < (int) list.size(); ++i)
            if (matches (list[(size_t) i])) { id = i + 1; break; }
    if (presetBox.getSelectedId() != id)
        presetBox.setSelectedId (id, juce::dontSendNotification);
}

// ---------------------------------------------------------------- timer (30 Hz)
void SemitonesEditor::timerCallback()
{
    const double t = nowMs();
    blinkPhase = t / 250.0;          // 4 Hz flashing

    // anti-freeze: renderer + watchdog
    if (getPeer() != lastPeer || t - lastRendererCheck > 1000.0)
    {
        lastRendererCheck = t;
        useSoftwareRenderer();
    }
    if (pendingSince > 0 && t - pendingSince > 1500.0 && isShowing())
    {
        lastPeer = nullptr;
        useSoftwareRenderer();
        repaint();
        pendingSince = t;
    }
    // caches: rebuilt only from here, after a resize has settled or the scale changed
    if (resizeSettle > 0 && --resizeSettle == 0) rebuildCache();
    if (t - lastScaleCheck > 250.0)
    {
        lastScaleCheck = t;
        const float ds = juce::Component::getApproximateScaleFactorForComponent (this);
        if (std::abs (ds - lastDisplayScale) > 0.001f) { lastDisplayScale = ds; rebuildCache(); }
    }

    // long presses
    if (downMix && ! longDone && t - tDown >= kMixHoldMs)
    {
        longDone = true;
        mixAdjust = true;
        mixAdjustLast = t;
        if (proc.getEffective().fav) proc.exitFavKeeping();
        proc.setParam (ParamID::mixOn, 1.0f);
    }
    if (downFav && ! longDone && t - tDown >= kFavHoldMs)
    {
        longDone = true;
        proc.saveFav();
        favBlinkUntil = t + 900.0;
    }
    // arrow auto-repeat
    if ((downLeft || downRight) && t >= nextRepeat)
    {
        stepAction (downRight ? 1 : -1);
        nextRepeat = t + (mixAdjust ? 45.0 : 150.0);
    }
    if (mixAdjust && ! downMix && ! downLeft && ! downRight && t - mixAdjustLast > 4000.0)
        mixAdjust = false;

    // footswitch ring = effect on (Echoflex fades: 0.45 on / 0.28 off per frame),
    // flashing while the mix is being adjusted
    const auto e = proc.getEffective();
    bool lit = e.on;
    if (mixAdjust) lit = e.on && std::fmod (blinkPhase, 1.0) < 0.5;
    {
        const float target = lit ? 1.0f : 0.0f;
        led[0] += (target - led[0]) * (target > led[0] ? 0.45f : 0.28f);
        if (std::abs (led[0] - target) < 0.004f) led[0] = target;
    }
    // rotating light: one turn every 1.6 s while the ring is lit
    ringAngle = (float) std::fmod (t / 1600.0 * juce::MathConstants<double>::twoPi, juce::MathConstants<double>::twoPi);
    if (std::abs (led[0] - drawnLed[0]) > 0.002f || led[0] > 0.003f)
    {
        drawnLed[0] = led[0];
        if (auto* sp = sprite ("ring_comet")) askRepaint (toScreen (sp->r, 4.0f));
    }

    segMask = computeSegments();
    if (segMask != drawnSegMask)
    {
        drawnSegMask = segMask;
        askRepaint (toScreen ({ Layout::hitDisplay.x, Layout::hitDisplay.y, Layout::hitDisplay.w, Layout::hitDisplay.h }, 4.0f));
    }
    const int pressed = (downLeft ? 1 : 0) | (downRight ? 2 : 0) | (downMix ? 4 : 0) | (downFav ? 8 : 0) | (downFoot ? 16 : 0);
    if (pressed != drawnPressed)
    {
        const int changed = pressed ^ (drawnPressed < 0 ? 31 : drawnPressed);
        drawnPressed = pressed;
        const char* names[5] = { "press_left", "press_right", "press_mix", "press_fav", "press_foot" };
        for (int b = 0; b < 5; ++b)
            if (changed & (1 << b))
                if (auto* sp = sprite (names[b])) askRepaint (toScreen (sp->r, 3.0f));
    }
    const auto status = statusText();
    if (status != drawnStatus)
    {
        drawnStatus = status;
        askRepaint (toScreen ({ Layout::statusBox.x, Layout::statusBox.y, Layout::statusBox.w, Layout::statusBox.h }, 2.0f));
    }
    syncPresetBox();
}

// ---------------------------------------------------------------- actions
void SemitonesEditor::stepAction (int dir)
{
    if (mixAdjust)
    {
        proc.stepMix ((float) dir);
        mixAdjustLast = nowMs();
    }
    else
        proc.stepSemitone (dir);
}

void SemitonesEditor::mouseDown (const juce::MouseEvent& ev)
{
    const auto p = toLogical (ev.position);
    const Hit h = hitTest (p);
    if (ev.mods.isPopupMenu())
    {
        showMenu (h);
        return;
    }
    const double t = nowMs();
    tDown = t;
    longDone = false;
    dragAccum = 0;
    switch (h)
    {
        case Hit::left:  downLeft = true;  stepAction (-1); nextRepeat = t + 450.0; break;
        case Hit::right: downRight = true; stepAction (+1); nextRepeat = t + 450.0; break;
        case Hit::mix:   downMix = true; break;
        case Hit::fav:   downFav = true; break;
        case Hit::foot:  downFoot = true; proc.toggleParam (ParamID::on); break;   // toggles on press, like Echoflex
        default: break;
    }
    timerCallback();
}

void SemitonesEditor::mouseUp (const juce::MouseEvent&)
{
    const double held = nowMs() - tDown;
    if (downMix && ! longDone)
    {
        if (mixAdjust) mixAdjust = false;                         // leave mix adjust
        else
        {
            if (proc.getEffective().fav) proc.exitFavKeeping();
            proc.toggleParam (ParamID::mixOn);
        }
    }
    if (downFav && ! longDone && held < kFavHoldMs)
    {
        mixAdjust = false;
        proc.toggleParam (ParamID::fav);
    }
    downLeft = downRight = downMix = downFav = downFoot = false;
    longDone = false;
    timerCallback();
}

void SemitonesEditor::mouseDrag (const juce::MouseEvent& ev)
{
    if (hitTest (toLogical (ev.mouseDownPosition)) != Hit::display) return;
    const float dy = (float) ev.getDistanceFromDragStartY() / scale();
    const float stepPx = mixAdjust ? 3.0f : 16.0f;
    const int target = (int) (-dy / stepPx);
    const int done = (int) dragAccum;
    if (target != done)
    {
        stepAction (target > done ? 1 : -1);
        dragAccum = (float) (done + (target > done ? 1 : -1));
    }
}

void SemitonesEditor::mouseMove (const juce::MouseEvent& ev)
{
    const Hit h = hitTest (toLogical (ev.position));
    if (h != hover)
    {
        hover = h;
        hoverSince = nowMs();
    }
    setMouseCursor (h == Hit::background || h == Hit::none ? juce::MouseCursor::NormalCursor
                                                                             : juce::MouseCursor::PointingHandCursor);
}

void SemitonesEditor::mouseExit (const juce::MouseEvent&) { hover = Hit::none; }

void SemitonesEditor::mouseWheelMove (const juce::MouseEvent& ev, const juce::MouseWheelDetails& w)
{
    const Hit h = hitTest (toLogical (ev.position));
    if (h == Hit::display || h == Hit::left || h == Hit::right)
    {
        const float d = w.deltaY != 0 ? w.deltaY : -w.deltaX;
        if (d != 0) stepAction (d > 0 ? 1 : -1);
    }
}

void SemitonesEditor::showMenu (Hit h)
{
    juce::PopupMenu m;
    m.setLookAndFeel (&look);
    std::vector<MidiTarget> targets;
    switch (h)
    {
        case Hit::foot:    targets = { MidiTarget::footswitch }; break;
        case Hit::left:    targets = { MidiTarget::down }; break;
        case Hit::right:   targets = { MidiTarget::up }; break;
        case Hit::mix:     targets = { MidiTarget::mixOn, MidiTarget::mix }; break;
        case Hit::fav:     targets = { MidiTarget::fav }; break;
        case Hit::display: targets = { MidiTarget::semitones, MidiTarget::up, MidiTarget::down }; break;
        default: break;
    }
    int id = 1;
    struct Act { int kind; MidiTarget t; float size; };
    std::map<int, Act> acts;
    for (auto t : targets)
    {
        m.addSectionHeader ("MIDI  -  " + SemitonesProcessor::targetName (t));
        const int cc = proc.midiCC[(size_t) t].load();
        acts[id] = { 0, t, 0 };
        m.addItem (id++, cc >= 0 ? "MIDI Learn (now CC " + juce::String (cc) + ")" : "MIDI Learn", true,
                   proc.learnTarget.load() == (int) t);
        if (SemitonesProcessor::isToggle (t))
        {
            const bool mom = proc.momentary[(size_t) t].load();
            acts[id] = { 1, t, 0 };
            m.addItem (id++, "Latching switch (CC >= 64 = on)", true, ! mom);
            acts[id] = { 2, t, 0 };
            m.addItem (id++, "Momentary switch (each press toggles)", true, mom);
        }
        if (SemitonesProcessor::isContinuous (t))
        {
            acts[id] = { 4, t, 0 };
            m.addItem (id++, "Reset expression pedal travel", cc >= 0);
        }
        acts[id] = { 3, t, 0 };
        m.addItem (id++, "Clear", cc >= 0);
    }
    if (proc.learnTarget.load() >= 0)
    {
        m.addSeparator();
        acts[id] = { 5, MidiTarget::count, 0 };
        m.addItem (id++, "Cancel MIDI Learn");
    }
    m.addSectionHeader ("Window size");
    for (float sz : { 1.0f, 1.25f, 1.5f, 2.0f })
    {
        acts[id] = { 6, MidiTarget::count, sz };
        const int w = juce::roundToInt (Layout::defaultW * sz);
        const bool cur = std::abs (getWidth() - w) < 2;
        m.addItem (id++, sz == 1.0f ? "Default (" + juce::String (w) + " x " + juce::String (Layout::defaultH) + ")"
                                    : juce::String ((int) (sz * 100)) + " %", true, cur);
    }

    juce::Component::SafePointer<SemitonesEditor> safe (this);
    m.showMenuAsync (juce::PopupMenu::Options().withTargetComponent (this).withMousePosition(),
        [safe, acts] (int r)
        {
            if (safe == nullptr || r <= 0) return;
            auto it = acts.find (r);
            if (it == acts.end()) return;
            auto& pr = safe->proc;
            const auto a = it->second;
            const size_t ti = (size_t) a.t;
            switch (a.kind)
            {
                case 0: pr.learnTarget.store ((int) a.t); break;
                case 1: pr.momentary[ti].store (false); break;
                case 2: pr.momentary[ti].store (true); break;
                case 3: pr.clearMidi (a.t); break;
                case 4: pr.courseMin[ti].store (1.0f); pr.courseMax[ti].store (0.0f); break;
                case 5: pr.learnTarget.store (-1); break;
                case 6: safe->setSize (juce::roundToInt (Layout::defaultW * a.size), juce::roundToInt (Layout::defaultH * a.size)); break;
                default: break;
            }
        });
}

// ---------------------------------------------------------------- offline rendering
void SemitonesEditor::setPreviewState (bool l, bool r, bool mx, bool fv, bool ft, bool adjustMix)
{
    downLeft = l; downRight = r; downMix = mx; downFav = fv; downFoot = ft;
    mixAdjust = adjustMix;
    longDone = true;
    tDown = nowMs();
    nextRepeat = 1e300;
}

void SemitonesEditor::settleForSnapshot()
{
    resizeSettle = 1;
    for (int i = 0; i < 40; ++i) timerCallback();
    bgCache = bgImage;            // full resolution art for 2x snapshots
}
