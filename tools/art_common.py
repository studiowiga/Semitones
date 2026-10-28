"""Shared geometry for the Semitones artwork (design v3: dark brushed steel on
concrete, dot-matrix display, light ring around the footswitch).

All coordinates are in pixels of the source design (design/source_design.jpg,
812 x 1024). The whole picture is the editor background; it is mapped to the
editor design space (760 x 958 units, rendered at 2x = 1520 x 1916). The window
opens at half the design space (380 x 479), the Studio Wiga single-pedal size.
"""

# ---------------------------------------------------------------- layout
LOGICAL_W, LOGICAL_H = 760, 958        # design units
HIDPI = 2                               # art rendered at 2x

SRC_CROP = (22.0, 50.0, 791.0, 1019.0)       # source area shown in the window (pedal enlarged)
PRESET_BOX = (262.0, 93.0, 552.0, 131.0)    # source px: preset menu on the pedal, above the display
DEFAULT_W, DEFAULT_H = 391, 493              # default (= minimum) window size
STATUS_PILL = (231.0, 988.0, 586.0, 1017.0)  # source px: original status pill (erased)
STATUS_BIG = (196.0, 980.0, 620.0, 1018.0)   # source px: bigger status pill drawn in its place
MIX_DOT = (302.0, 383.0, 7.5)                # x, y, r: MIX indicator dot, above the MIX button

# ------------------------------------------------------- relight (light from the left)
PLATE = (142.0, 65.0, 673.0, 977.0)           # pedal plate edges in the source
PLATE_CX = 407.5                              # vertical mirror axis of the plate
SCREWS = [(174.2, 99.0), (635.0, 96.6), (175.4, 939.0), (637.4, 939.0)]
SCREW_R = 27.0
CHANNEL_BR = (520.0, 847.0, 0.81, 16.0, 4.0)  # groove under the bottom-right screw: point on its bright edge, slope, width above / below
RENDER_SCREWS = False                         # screws removed from the design
SCREW_HEAD_R = 20.5                            # rendered head radius (source px)
FOOT_MIRROR = (407.0, 825.0, 106.0)           # footswitch centre / radius for the local mirror
JACK_L = (100.0, 456.0, 142.0, 574.0)         # left jack box (x0, y0, x1, y1)
JACK_R = (673.0, 456.0, 715.0, 574.0)         # right jack box

# --------------------------------------------------------------- controls
MIX_BTN = (301.8, 455.4, 25.0)
FAV_BTN = (510.6, 455.0, 25.0)
FOOT = (408.0, 826.0)
FOOT_CAP_R = 40.0          # turned metal button
FOOT_NUT_R = 66.0          # nut / bezel edge
FOOT_COLLAR_R = 101.0      # outer edge of the frosted collar
RING_R = 82.0              # light ring radius
RING_W = 13.0              # light pipe width

ARROW_L = [(179.0, 284.0), (237.0, 252.0), (237.0, 316.0)]
ARROW_R = [(633.0, 284.0), (574.0, 252.0), (574.0, 316.0)]
ARROW_L_BOX = (170, 244, 246, 324)
ARROW_R_BOX = (565, 244, 642, 324)

GLASS = (262.0, 160.0, 552.0, 407.0)       # display glass (outer)
GLASS_INNER = (268.0, 166.0, 546.0, 401.0)

# ------------------------------------------------------- dot-matrix display
DOT_PITCH = 3.4
SEG_T = 12.5
SEG_GAP = 1.6
YT, YM, YB = 248.5, 280.5, 312.5
TENS_X = (387.5, 434.5)
UNITS_X = (457.5, 504.5)
SIGN_C = (332.0, 281.0)
SIGN_H, SIGN_V = 33.0, 30.0

# ------------------------------------------------------- engraved name
ENGRAVE_TEXT = 'Semitones'
ENGRAVE_C = (398.0, 607.0)
ENGRAVE_W = 190.0
ENGRAVE_TRACK = 0.035


def _hseg(x1, x2, y, t=SEG_T, g=SEG_GAP):
    h = t / 2
    return [(x1 + g, y), (x1 + g + h, y - h), (x2 - g - h, y - h),
            (x2 - g, y), (x2 - g - h, y + h), (x1 + g + h, y + h)]


def _vseg(x, y1, y2, t=SEG_T, g=SEG_GAP):
    h = t / 2
    return [(x, y1 + g), (x + h, y1 + g + h), (x + h, y2 - g - h),
            (x, y2 - g), (x - h, y2 - g - h), (x - h, y1 + g + h)]


def digit_segments(xl, xr):
    return {
        'a': _hseg(xl, xr, YT), 'b': _vseg(xr, YT, YM), 'c': _vseg(xr, YM, YB),
        'd': _hseg(xl, xr, YB), 'e': _vseg(xl, YM, YB), 'f': _vseg(xl, YT, YM),
        'g': _hseg(xl, xr, YM),
    }


def sign_segments():
    cx, cy = SIGN_C
    return {
        'l': _hseg(cx - SIGN_H, cx + 1.0, cy, SEG_T, 1.4),
        'r': _hseg(cx - 1.0, cx + SIGN_H, cy, SEG_T, 1.4),
        'u': _vseg(cx, cy - SIGN_V, cy + 1.0, SEG_T, 1.4),
        'd': _vseg(cx, cy - 1.0, cy + SIGN_V, SEG_T, 1.4),
    }


def all_layers():
    out = []
    for k, p in sign_segments().items():
        out.append(('s_' + k, p))
    for k, p in digit_segments(*TENS_X).items():
        out.append(('t_' + k, p))
    for k, p in digit_segments(*UNITS_X).items():
        out.append(('u_' + k, p))
    return out
