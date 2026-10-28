"""Shared geometry for the Semitones (Chug Capo replica) artwork.

All coordinates below are in pixels of the original reference photo
(design/source_photo.png, 649 x 950). The build script maps them to the
plugin canvas (760 x 958 logical, rendered at 2x).
"""
import numpy as np

# ---------------------------------------------------------------- layout
LOGICAL_W, LOGICAL_H = 760, 958        # default editor size (simple format)
HIDPI = 2                               # art rendered at 2x
TOP_BAR = 40                            # preset menu strip (logical px)
BOTTOM_BAR = 38                         # status line strip (logical px)

# pedal crop inside the photo (alpha bounding box is computed at build time)
# --------------------------------------------------------------- controls
LED_C = (322.8, 491.9)
LED_LENS_R = 15.5          # lens radius
LED_BEZEL_R = 21.0         # translucent bezel ring
LED_RECESS_R = 27.5        # circular cut into the channel

MIX_BTN = (224.0, 412.0, 25.5)
FAV_BTN = (424.5, 412.0, 25.5)
FOOT = (325.0, 772.5)
FOOT_CAP_R = 37.0
FOOT_CHROME_R = 69.0
FOOT_RING_R = 100.0

ARROW_L = [(103.0, 243.0), (160.0, 209.0), (160.0, 277.0)]   # approx triangle
ARROW_R = [(545.0, 243.0), (488.0, 209.0), (488.0, 277.0)]
ARROW_L_BOX = (96, 200, 168, 286)
ARROW_R_BOX = (480, 200, 553, 286)

GLASS = (184.0, 123.0, 466.0, 366.0)      # display glass (outer)
GLASS_INNER = (189.0, 128.0, 461.0, 361.0)

LOGO_C = (325.0, 897.5)
LOGO_H = 21.0

# ------------------------------------------------------- 7-segment display
SEG_T = 14.5
SEG_GAP = 1.7
SLANT = 0.055
YT, YM, YB = 202.0, 242.5, 283.0
UNITS_X = (373.5, 416.5)
TENS_X = (UNITS_X[0] - 71.0, UNITS_X[1] - 71.0)
SIGN_C = (250.5, 242.5)
DOT_MIX = (217.5, 321.0, 4.6)
DOT_FAV = (421.5, 321.0, 4.6)


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
    """Return dict a..g -> polygon (photo coords)."""
    segs = {
        'a': _hseg(xl, xr, YT),
        'b': _vseg(xr, YT, YM),
        'c': _vseg(xr, YM, YB),
        'd': _hseg(xl, xr, YB),
        'e': _vseg(xl, YM, YB),
        'f': _vseg(xl, YT, YM),
        'g': _hseg(xl, xr, YM),
    }
    return {k: _slant(v) for k, v in segs.items()}


def sign_segments():
    cx, cy = SIGN_C
    t = SEG_T
    segs = {
        'l': _hseg(cx - 36.0, cx + 1.0, cy, t, 1.6),
        'r': _hseg(cx - 1.0, cx + 36.0, cy, t, 1.6),
        'u': _vseg(cx, cy - 34.0, cy + 1.0, t, 1.6),
        'd': _vseg(cx, cy - 1.0, cy + 34.0, t, 1.6),
    }
    return {k: _slant(v) for k, v in segs.items()}


def all_layers():
    """Ordered list of (name, polygon or circle) for every display element."""
    out = []
    for k, p in sign_segments().items():
        out.append(('s_' + k, p))
    for k, p in digit_segments(*TENS_X).items():
        out.append(('t_' + k, p))
    for k, p in digit_segments(*UNITS_X).items():
        out.append(('u_' + k, p))
    return out
