"""Shared geometry for the Semitones artwork (design v2: brushed steel, ring light).

All coordinates are in pixels of the source design (design/source_design.jpg,
941 x 1136). The build script maps them to the plugin canvas (760 x 958
logical, rendered at 2x).
"""

# ---------------------------------------------------------------- layout
LOGICAL_W, LOGICAL_H = 760, 958        # design units; the window opens at half this (380 x 479, Echoflex size)
HIDPI = 2                               # art rendered at 2x
TOP_BAR = 56                            # preset menu strip (design units)
BOTTOM_BAR = 44                         # status line strip (design units)
PEDAL_MAX_Y = 1113                      # ignore anything below (old status text)

# --------------------------------------------------------------- controls
MIX_BTN = (350.0, 494.0, 30.0)
FAV_BTN = (592.5, 494.0, 30.0)
FOOT = (472.0, 931.0)
FOOT_CAP_R = 54.0          # turned metal button
FOOT_NUT_R = 94.0          # outer edge of the nut / inner ring
FOOT_BEZEL_R = 119.0       # outer edge of the bezel
RING_R = 97.0              # light ring radius (between nut and bezel)
RING_W = 5.2               # light pipe width

ARROW_L = [(201.0, 290.0), (269.0, 249.0), (269.0, 330.0)]
ARROW_R = [(739.0, 290.0), (671.0, 249.0), (671.0, 330.0)]
ARROW_L_BOX = (190, 238, 282, 342)
ARROW_R_BOX = (658, 238, 750, 342)

GLASS = (299.0, 142.0, 641.0, 435.0)       # display glass (outer)
GLASS_INNER = (305.0, 148.0, 635.0, 429.0)

# ------------------------------------------------------- 7-segment display
SEG_T = 15.5
SEG_GAP = 1.8
SLANT = 0.05
YT, YM, YB = 249.5, 287.0, 324.5
UNITS_X = (532.5, 585.5)
TENS_X = (UNITS_X[0] - 84.0, UNITS_X[1] - 84.0)
SIGN_C = (382.5, 287.0)
SIGN_H, SIGN_V = 41.5, 38.0                # half extents of the +/- glyph
DOT_MIX = (338.0, 397.0, 5.0)
DOT_FAV = (602.0, 397.0, 5.0)


def _hseg(x1, x2, y, t=SEG_T, g=SEG_GAP):
    h = t / 2
    return [(x1 + g, y), (x1 + g + h, y - h), (x2 - g - h, y - h),
            (x2 - g, y), (x2 - g - h, y + h), (x1 + g + h, y + h)]


def _vseg(x, y1, y2, t=SEG_T, g=SEG_GAP):
    h = t / 2
    return [(x, y1 + g), (x + h, y1 + g + h), (x + h, y2 - g - h),
            (x, y2 - g), (x - h, y2 - g - h), (x - h, y1 + g + h)]


def _slant(poly, ym=YM, s=SLANT):
    return [(x - s * (y - ym), y) for x, y in poly]


def digit_segments(xl, xr):
    segs = {
        'a': _hseg(xl, xr, YT), 'b': _vseg(xr, YT, YM), 'c': _vseg(xr, YM, YB),
        'd': _hseg(xl, xr, YB), 'e': _vseg(xl, YM, YB), 'f': _vseg(xl, YT, YM),
        'g': _hseg(xl, xr, YM),
    }
    return {k: _slant(v) for k, v in segs.items()}


def sign_segments():
    cx, cy = SIGN_C
    segs = {
        'l': _hseg(cx - SIGN_H, cx + 1.0, cy, SEG_T, 1.6),
        'r': _hseg(cx - 1.0, cx + SIGN_H, cy, SEG_T, 1.6),
        'u': _vseg(cx, cy - SIGN_V, cy + 1.0, SEG_T, 1.6),
        'd': _vseg(cx, cy - 1.0, cy + SIGN_V, SEG_T, 1.6),
    }
    return {k: _slant(v) for k, v in segs.items()}


def all_layers():
    out = []
    for k, p in sign_segments().items():
        out.append(('s_' + k, p))
    for k, p in digit_segments(*TENS_X).items():
        out.append(('t_' + k, p))
    for k, p in digit_segments(*UNITS_X).items():
        out.append(('u_' + k, p))
    return out
