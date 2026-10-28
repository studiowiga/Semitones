#!/usr/bin/env python3
"""Builds every image used by the Semitones editor from the design picture.

Run:  python3 -I tools/build_art.py   (from the repository root)

Outputs (assets/):
  background.jpg            whole editor background, 2x (1520 x 1916)
  seg_<id>.png              lit 7-segment elements (glow included)
  dot_mix.png / dot_fav.png lit indicator dots
  ring_lit.png              footswitch light ring, lit (light pipe + optical halo)
  ringlight.png             light the ring throws on the faceplate (alpha layer)
  press_<id>.png            pressed state of arrows, MIX, FAV, footswitch
Layout.h                    positions of every sprite (logical coordinates)
"""
import json, os, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from art_common import *  # noqa

OUT = os.path.join(ROOT, 'assets')
DESIGN = os.path.join(ROOT, 'design')
os.makedirs(OUT, exist_ok=True)
RNG = np.random.default_rng(7)


def to_img(a, mode='RGBA'):
    return Image.fromarray(np.clip(a * 255.0 + 0.5, 0, 255).astype(np.uint8), mode)


def srgb2lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin2srgb(c):
    c = np.clip(c, 0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def disc(h, w, cx, cy, r, soft=1.0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    return np.clip((r - d) / soft + 0.5, 0, 1)


def poly_mask(h, w, poly, ss=8):
    im = Image.new('L', (w * ss, h * ss), 0)
    ImageDraw.Draw(im).polygon([(x * ss, y * ss) for x, y in poly], fill=255)
    im = im.resize((w, h), Image.BOX)
    return np.asarray(im).astype(np.float32) / 255.0


def gblur(a, s):
    if s <= 0:
        return a
    k = int(s * 3) * 2 + 1
    return cv2.GaussianBlur(a, (k, k), s, borderType=cv2.BORDER_REFLECT)


# ===================================================== 1. load + cut out the pedal
src = Image.open(os.path.join(DESIGN, 'source_design.jpg')).convert('RGB')
rgb = np.asarray(src).astype(np.float32) / 255.0
H0, W0 = rgb.shape[:2]
lum = rgb.mean(2)
# background = dark area connected to the border
dark = (lum < 0.13).astype(np.uint8)
dark[PEDAL_MAX_Y:, :] = 1
ff = dark.copy() * 255
mask_ff = np.zeros((H0 + 2, W0 + 2), np.uint8)
bg = np.zeros((H0, W0), np.uint8)
for seed in [(0, 0), (W0 - 1, 0), (0, H0 - 1), (W0 - 1, H0 - 1)]:
    tmp = ff.copy()
    cv2.floodFill(tmp, mask_ff, seed, 128)
bg = (mask_ff[1:-1, 1:-1] > 0).astype(np.uint8)
ped = (1 - bg).astype(np.uint8)
ped[PEDAL_MAX_Y:, :] = 0
n, lab, stats, _ = cv2.connectedComponentsWithStats(ped)
big = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
ped = (lab == big).astype(np.uint8)
ped = cv2.morphologyEx(ped, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
ped = cv2.erode(ped, np.ones((2, 2), np.uint8))
alpha = gblur(ped.astype(np.float32), 0.8)

# ===================================================== 2. display: remove the digits
gx0, gy0, gx1, gy1 = [int(v) for v in GLASS_INNER]
blue_excess = rgb[..., 2] - 0.5 * (rgb[..., 0] + rgb[..., 1])
m = np.zeros((H0, W0), np.uint8)
m[gy0:gy1, gx0:gx1] = ((blue_excess[gy0:gy1, gx0:gx1] > 0.035) | (lum[gy0:gy1, gx0:gx1] > 0.10)).astype(np.uint8) * 255
m = cv2.dilate(m, np.ones((5, 5), np.uint8), iterations=2)
inner = np.zeros_like(m)
cv2.rectangle(inner, (gx0 + 3, gy0 + 3), (gx1 - 3, gy1 - 3), 255, -1)
m = cv2.bitwise_and(m, inner)
u8 = (rgb * 255).astype(np.uint8)
fixed = cv2.cvtColor(cv2.inpaint(cv2.cvtColor(u8, cv2.COLOR_RGB2BGR), m, 9, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
clean = rgb[gy0 + 10:gy0 + 40, gx0 + 10:gx1 - 10].reshape(-1, 3)
glass_col = np.median(clean, 0)
mm = gblur(m.astype(np.float32) / 255.0, 2.0)[..., None]
grain = RNG.normal(0, 1, (H0, W0, 1)).astype(np.float32) * clean.std(0) * 0.8
target = 0.5 * gblur(fixed, 6.0) + 0.5 * glass_col
rgb = rgb * (1 - mm) + (target + grain) * mm
rgb = np.clip(rgb, 0, 1)
Image.fromarray((rgb * 255).astype(np.uint8)).save(os.path.join(DESIGN, 'clean_preview.png'))

# ===================================================== 3. canvas
ys_, xs_ = np.nonzero(alpha > 0.02)
bx0, by0, bx1, by1 = xs_.min(), ys_.min(), xs_.max() + 1, ys_.max() + 1
avail_h = (LOGICAL_H - TOP_BAR - BOTTOM_BAR) * HIDPI
K = avail_h / float(by1 - by0)
CW, CH = LOGICAL_W * HIDPI, LOGICAL_H * HIDPI
pw = int(round((bx1 - bx0) * K)); ph = int(round((by1 - by0) * K))
ox = float(int(round((CW - pw) / 2.0))); oy = float(TOP_BAR * HIDPI)
print('scale K =', K, 'pedal box', pw, ph, 'offset', ox, oy)


def P2C(x, y):
    return ox + (x - bx0) * K, oy + (y - by0) * K


def P2L(x, y):
    cx, cy = P2C(x, y)
    return cx / HIDPI, cy / HIDPI


crop_rgb = rgb[by0:by1, bx0:bx1]
crop_a = alpha[by0:by1, bx0:bx1]
pm = np.concatenate([crop_rgb * crop_a[..., None], crop_a[..., None]], -1)
bigi = np.clip(cv2.resize(pm, (pw, ph), interpolation=cv2.INTER_LANCZOS4), 0, 1)
ba = bigi[..., 3:4]
brgb = np.clip(np.where(ba > 1e-4, bigi[..., :3] / np.maximum(ba, 1e-4), 0), 0, 1)

# crisp vertical brushing (the design picture is soft once enlarged)
lumb = brgb.mean(2)
sat = brgb.max(2) - brgb.min(2)
gph = crop_rgb.mean(2)
hp = np.abs(gph - cv2.blur(gph, (7, 1)))
en = cv2.GaussianBlur(hp, (0, 0), 3)
brushed = cv2.resize(np.clip((en - 0.010) / 0.012, 0, 1), (pw, ph), interpolation=cv2.INTER_LINEAR)
metal = ((lumb > 0.30) & (sat < 0.08) & (ba[..., 0] > 0.99)).astype(np.float32) * brushed
# keep the turned parts (footswitch, buttons, screws) out: they are not brushed
fcx, fcy = (FOOT[0] - bx0) * K, (FOOT[1] - by0) * K
yyb, xxb = np.mgrid[0:ph, 0:pw].astype(np.float32)
keep_out = np.hypot(xxb - fcx, yyb - fcy) < (FOOT_BEZEL_R + 3) * K
for (bxp, byp, br) in (MIX_BTN, FAV_BTN):
    keep_out |= np.hypot(xxb - (bxp - bx0) * K, yyb - (byp - by0) * K) < (br + 4) * K
metal *= (~keep_out).astype(np.float32)
metal = gblur(metal, 1.2)
streak = cv2.GaussianBlur(RNG.normal(0, 1, (ph, pw)).astype(np.float32), (3, 241), sigmaX=0.55, sigmaY=40.0)
streak /= streak.std() + 1e-6
fine = cv2.GaussianBlur(RNG.normal(0, 1, (ph, pw)).astype(np.float32), (3, 31), sigmaX=0.45, sigmaY=5.0)
fine /= fine.std() + 1e-6
amp = (0.016 + 0.014 * np.clip((lumb - 0.4) / 0.4, 0, 1)) * metal
blur = gblur(brgb, 1.4)
sharp_w = np.clip(metal + 0.6 * keep_out.astype(np.float32), 0, 1)
brgb = np.clip(brgb + 0.6 * (brgb - blur) * sharp_w[..., None], 0, 1)
brgb = np.clip(brgb + ((0.75 * streak + 0.45 * fine) * amp)[..., None], 0, 1)

canvas_rgb = np.zeros((CH, CW, 3), np.float32)
canvas_a = np.zeros((CH, CW), np.float32)
ix, iy = int(ox), int(oy)
canvas_rgb[iy:iy + ph, ix:ix + pw] = brgb
canvas_a[iy:iy + ph, ix:ix + pw] = ba[..., 0]

# ===================================================== 4. display art
def poly_c(poly):
    return [P2C(x, y) for x, y in poly]


GHOST = np.array([3.0, 20.0, 46.0]) / 255.0
LIT = np.array([40.0, 168.0, 255.0]) / 255.0
LIT_CORE = np.array([140.0, 220.0, 255.0]) / 255.0

layers = all_layers()
seg_masks = {name: poly_mask(CH, CW, poly_c(poly)) for name, poly in layers}
dot_masks = {
    'dot_mix': disc(CH, CW, *P2C(DOT_MIX[0], DOT_MIX[1]), DOT_MIX[2] * K, 1.0),
    'dot_fav': disc(CH, CW, *P2C(DOT_FAV[0], DOT_FAV[1]), DOT_FAV[2] * K, 1.0),
}
ghost_all = np.zeros((CH, CW), np.float32)
for v in list(seg_masks.values()) + list(dot_masks.values()):
    ghost_all = np.maximum(ghost_all, v)
gtex = 0.82 + 0.18 * gblur(RNG.normal(0, 1, (CH, CW)).astype(np.float32), 6) * 3
gcol = GHOST[None, None, :] * np.clip(gtex, 0.6, 1.25)[..., None]
canvas_rgb = canvas_rgb * (1 - ghost_all[..., None] * 0.45) + gcol * ghost_all[..., None] * 0.45


def lit_sprite(mask, name):
    lin_glow = gblur(mask, 3.2 * HIDPI) * 0.55 + gblur(mask, 9.0 * HIDPI) * 0.28
    er = cv2.erode(mask, np.ones((5, 5), np.uint8), iterations=2)
    inner = gblur(er, 2.5)
    col = LIT[None, None, :] * mask[..., None] * 0.92 + LIT_CORE[None, None, :] * (inner * 0.35)[..., None]
    rgb_ = col + LIT[None, None, :] * lin_glow[..., None] * (1 - mask[..., None])
    a_ = np.clip(np.maximum(mask, np.clip(rgb_.max(2) * 1.15, 0, 1)), 0, 1)
    out = np.clip(np.where(a_[..., None] > 1e-4, rgb_ / np.maximum(a_[..., None], 1e-4), 0), 0, 1)
    ys, xs = np.nonzero(a_ > 0.004)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    to_img(np.concatenate([out[y0:y1, x0:x1], a_[y0:y1, x0:x1, None]], -1)).save(os.path.join(OUT, name + '.png'))
    return (x0 / HIDPI, y0 / HIDPI, (x1 - x0) / HIDPI, (y1 - y0) / HIDPI)


sprites = {}
for name, _ in layers:
    sprites['seg_' + name] = lit_sprite(seg_masks[name], 'seg_' + name)
for name, mk in dot_masks.items():
    sprites[name] = lit_sprite(mk, name)

# ===================================================== 5. footswitch light ring (off state baked)
FC = P2C(*FOOT)
yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32)
dx, dy = xx - FC[0], yy - FC[1]
dd = np.sqrt(dx * dx + dy * dy)
ang_l = (-dx - dy) / (np.sqrt(2) * np.maximum(dd, 1e-3))      # light from top-left
R = RING_R * K
RW = RING_W * K
band = np.clip(RW / 2 - np.abs(dd - R) + 0.6, 0, 1)            # light pipe
groove = np.clip(RW / 2 + 1.4 * HIDPI - np.abs(dd - R) + 0.6, 0, 1)
# groove: thin dark channel cut between nut and bezel
canvas_rgb *= (1 - 0.55 * (groove - band)[..., None])
# unlit light pipe: frosted, slightly cool translucent plastic, lit by the room light
pipe_off = np.array([0.56, 0.58, 0.62])
shade = 0.78 + 0.22 * ang_l * np.sign(dd - R + 1e-3)
rel = np.clip((dd - (R - RW / 2)) / RW, 0, 1)
dome = 0.82 + 0.25 * np.sin(rel * np.pi)
canvas_rgb = canvas_rgb * (1 - band[..., None]) + (pipe_off * (dome * shade)[..., None]) * band[..., None]

# ===================================================== 6. backdrop + shadow
bgc = np.zeros((CH, CW, 3), np.float32)
top = np.array([0.105, 0.105, 0.115]); bot = np.array([0.055, 0.055, 0.062])
t = (yy / CH)[..., None]
bgc[:] = top * (1 - t) + bot * t
vig = 1 - 0.35 * (((xx - CW / 2) / (CW / 2)) ** 2 + ((yy - CH / 2) / (CH / 2)) ** 2) * 0.5
bgc *= vig[..., None]
bgc += gblur(RNG.normal(0, 1, (CH, CW)).astype(np.float32), 0.7)[..., None] * 0.004
shm = np.zeros((CH, CW), np.float32)
sdx, sdy = int(9 * HIDPI), int(12 * HIDPI)
shm[sdy:, sdx:] = canvas_a[:-sdy, :-sdx]
shadow = gblur(shm, 14 * HIDPI) * 0.75 + gblur(canvas_a, 3 * HIDPI) * 0.35
bgc *= (1 - np.clip(shadow, 0, 0.9))[..., None]
final = bgc * (1 - canvas_a[..., None]) + canvas_rgb * canvas_a[..., None]
FINAL = final.copy()
fu8 = np.clip(final * 255 + 0.5, 0, 255).astype(np.uint8)
Image.fromarray(fu8, 'RGB').save(os.path.join(OUT, 'background.jpg'), quality=94, subsampling=0, optimize=True)
Image.fromarray(fu8, 'RGB').save(os.path.join(DESIGN, 'background_preview.png'))

# ===================================================== 7. ring lit + faceplate light
COL = srgb2lin(LIT)                          # exactly the display blue (linear)
CORE = srgb2lin(np.array([70.0, 185.0, 255.0]) / 255.0)   # hot centre, barely lighter
# light emitted by the ring: falls with the distance to the ring circle
dr = np.abs(dd - R)
src_h = 6.0 * HIDPI
E = (src_h ** 2 / (dr ** 2 + src_h ** 2)) ** 1.5
E_wide = np.exp(-dr / (26 * HIDPI)) * 0.35
illum = np.clip(E * 1.6 + E_wide, 0, 3) * (1 - band)
lin = srgb2lin(FINAL)
add = lin * illum[..., None] * COL[None, None, :] * 2.6 + illum[..., None] * COL * 0.02
target = lin2srgb(lin + add)
diff = np.clip(target - FINAL, 0, 1)
a_ = np.clip(diff.max(2) / np.maximum(1 - FINAL.max(2), 0.02), 0, 1)
a_ = np.clip(np.maximum(a_, np.clip(diff.max(2) * 3.0, 0, 1)), 0, 1)
colr = np.clip(np.where(a_[..., None] > 1e-4, (target - FINAL * (1 - a_[..., None])) / np.maximum(a_[..., None], 1e-4), 0), 0, 1)
box_r = int((FOOT_BEZEL_R + 30) * K)
bx_, by_ = int(FC[0]) - box_r, int(FC[1]) - box_r
to_img(np.concatenate([colr, a_[..., None]], -1)[by_:by_ + 2 * box_r, bx_:bx_ + 2 * box_r]).save(os.path.join(OUT, 'ringlight.png'), optimize=True)
sprites['ringlight'] = (bx_ / HIDPI, by_ / HIDPI, 2 * box_r / HIDPI, 2 * box_r / HIDPI)
# the pipe itself: hot core, saturated edges, faint optical bloom
relc = 1 - np.clip(np.abs(dd - R) / (RW / 2), 0, 1)
pipe_lin = CORE[None, None, :] * (relc ** 1.5)[..., None] * 0.55 + COL[None, None, :] * (0.55 + 0.35 * (1 - relc))[..., None]
pipe_s = lin2srgb(pipe_lin)
bloom = gblur(band, 2.5 * HIDPI) * 0.55 + gblur(band, 7 * HIDPI) * 0.30
halo_rgb = lin2srgb(COL[None, None, :] * np.ones((CH, CW, 1)))
a_h = np.clip(bloom * (1 - band), 0, 1)
out_rgb = pipe_s * band[..., None] + halo_rgb * a_h[..., None]
out_a = np.clip(band + a_h, 0, 1)
out_rgb = np.clip(np.where(out_a[..., None] > 1e-4, out_rgb / np.maximum(out_a[..., None], 1e-4), 0), 0, 1)
to_img(np.concatenate([out_rgb, out_a[..., None]], -1)[by_:by_ + 2 * box_r, bx_:bx_ + 2 * box_r]).save(os.path.join(OUT, 'ring_lit.png'), optimize=True)
sprites['ring_lit'] = sprites['ringlight']

# rotating light: no steady ring, a soft glowing head with a long blurred
# trail and a wide halo, drawn rotated around the ring centre by the editor
half = int(np.ceil(R + RW + 70 * HIDPI))
cxi, cyi = FC
cs = 2 * half
yy2, xx2 = np.mgrid[0:cs, 0:cs].astype(np.float32)
ddx, ddy = xx2 - half, yy2 - half          # sprite centred exactly on the ring centre
d2 = np.sqrt(ddx * ddx + ddy * ddy)
ang = np.arctan2(ddy, ddx)                  # y down: increasing angle = clockwise
phi = np.mod(0.0 - ang, 2 * np.pi)          # angle behind the head (head at angle 0)
prof = np.exp(-phi / 3.4) * np.clip(1 - phi / (1.9 * np.pi), 0, 1) ** 1.15   # very long trail (almost a full turn), fading out
head = np.exp(-(phi / 0.38) ** 2) + np.exp(-((2 * np.pi - phi) / 0.14) ** 2) * 0.8
band2 = np.clip(RW / 2 - np.abs(d2 - R) + 0.6, 0, 1)
src_ = band2 * np.clip(prof + 0.8 * head, 0, 1.6)


def nblur(a, sg):
    # blur normalised so a full lit ring keeps its level whatever the radius
    return gblur(a, sg) / (gblur(band2, sg).max() + 1e-6)


core = nblur(src_, 1.8 * HIDPI)                                         # soft light pipe
halo = (nblur(src_, 5 * HIDPI) * 0.85 + nblur(src_, 12 * HIDPI) * 0.65 +
        nblur(src_, 24 * HIDPI) * 0.45 + nblur(band2 * head, 16 * HIDPI) * 0.6)
hot = nblur(band2 * head, 2.2 * HIDPI)                                 # whiter head
blue_s = lin2srgb(COL * 1.15)                                           # glow colour (display blue)
pipe_s = lin2srgb(COL * 1.6 + CORE * 0.35)
hot_s = lin2srgb(CORE * 1.6)
wc, wh, wt = np.clip(core * 1.05, 0, 1), np.clip(halo * 0.80, 0, 0.92), np.clip(hot * 0.9, 0, 1)
ca = np.clip(1 - (1 - wc) * (1 - wh), 0, 1)
crgb = (pipe_s[None, None, :] * wc[..., None] + blue_s[None, None, :] * (wh * (1 - wc))[..., None])
crgb = crgb / np.maximum(ca[..., None], 1e-4)
crgb = crgb * (1 - wt[..., None]) + hot_s[None, None, :] * wt[..., None]
crgb = np.clip(crgb, 0, 1)
to_img(np.concatenate([crgb, ca[..., None]], -1)).save(os.path.join(OUT, 'ring_comet.png'), optimize=True)
sprites['ring_comet'] = ((cxi - half) / HIDPI, (cyi - half) / HIDPI, cs / HIDPI, cs / HIDPI)

# ===================================================== 8. pressed states
def crop_box(x0, y0, x1, y1):
    a0 = P2C(x0, y0); a1 = P2C(x1, y1)
    return int(a0[0]), int(a0[1]), int(np.ceil(a1[0])), int(np.ceil(a1[1]))


def save_pressed(name, box, mask_fn, push=1.2, dark=0.82):
    X0, Y0, X1, Y1 = box
    reg = FINAL[Y0:Y1, X0:X1].copy()
    h, w = reg.shape[:2]
    mk = mask_fn(h, w, X0, Y0)
    M = np.float32([[1, 0, push * HIDPI * 0.6], [0, 1, push * HIDPI]])
    moved = cv2.warpAffine(reg, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    edge = np.clip(mk - cv2.erode(mk, np.ones((5, 5), np.uint8)), 0, 1)
    out = reg * (1 - mk[..., None]) + moved * dark * mk[..., None]
    out = out * (1 - 0.25 * gblur(edge, 1.5)[..., None])
    a = np.clip(gblur(mk, 1.0) * 1.15, 0, 1)
    to_img(np.concatenate([out, a[..., None]], -1)).save(os.path.join(OUT, 'press_' + name + '.png'), optimize=True)
    sprites['press_' + name] = (X0 / HIDPI, Y0 / HIDPI, w / HIDPI, h / HIDPI)


def circ_mask(cx, cy, r):
    def f(h, w, X0, Y0):
        c = P2C(cx, cy)
        return disc(h, w, c[0] - X0, c[1] - Y0, r * K + 1.0 * HIDPI, 1.2)
    return f


def tri_mask(pts):
    def f(h, w, X0, Y0):
        cx = sum(p[0] for p in pts) / 3; cy = sum(p[1] for p in pts) / 3
        pp = [P2C(cx + (x - cx) * 1.10, cy + (y - cy) * 1.10) for x, y in pts]
        m_ = poly_mask(h, w, [(x - X0, y - Y0) for x, y in pp], 4)
        return gblur(cv2.dilate(m_, np.ones((3, 3), np.uint8)), 1.5)
    return f


mx, my, mr = MIX_BTN
save_pressed('mix', crop_box(mx - mr - 6, my - mr - 6, mx + mr + 6, my + mr + 6), circ_mask(mx, my, mr))
fx, fy, fr = FAV_BTN
save_pressed('fav', crop_box(fx - fr - 6, fy - fr - 6, fx + fr + 6, fy + fr + 6), circ_mask(fx, fy, fr))
save_pressed('left', crop_box(*ARROW_L_BOX), tri_mask(ARROW_L), push=1.0, dark=0.82)
save_pressed('right', crop_box(*ARROW_R_BOX), tri_mask(ARROW_R), push=1.0, dark=0.82)

# footswitch: button sinks inside the nut, dark disc while pressed (Echoflex behaviour)
FX, FY = FOOT
X0, Y0, X1, Y1 = crop_box(FX - FOOT_NUT_R, FY - FOOT_NUT_R, FX + FOOT_NUT_R, FY + FOOT_NUT_R)
reg = FINAL[Y0:Y1, X0:X1].copy()
h, w = reg.shape[:2]
c = P2C(FX, FY)
cxl, cyl = c[0] - X0, c[1] - Y0
M = cv2.getRotationMatrix2D((cxl, cyl), 0, 0.97)
M[1, 2] += 1.2 * HIDPI
sunk = cv2.warpAffine(reg, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
chm = disc(h, w, cxl, cyl, (FOOT_NUT_R - 18) * K, 1.5)
out = reg * (1 - chm[..., None]) + sunk * chm[..., None]
darkd = disc(h, w, cxl, cyl + 0.6 * HIDPI, FOOT_CAP_R * K * 1.02, 2.0)
out = out * (1 - 0.25 * darkd[..., None])
to_img(np.concatenate([out, chm[..., None]], -1)).save(os.path.join(OUT, 'press_foot.png'), optimize=True)
sprites['press_foot'] = (X0 / HIDPI, Y0 / HIDPI, w / HIDPI, h / HIDPI)

# ===================================================== 9. hit areas + Layout.h
hit = {
    'left': (*P2L(ARROW_L_BOX[0], ARROW_L_BOX[1]), *P2L(ARROW_L_BOX[2], ARROW_L_BOX[3])),
    'right': (*P2L(ARROW_R_BOX[0], ARROW_R_BOX[1]), *P2L(ARROW_R_BOX[2], ARROW_R_BOX[3])),
    'mix': (*P2L(mx, my), mr * K / HIDPI + 4),
    'fav': (*P2L(fx, fy), fr * K / HIDPI + 4),
    'foot': (*P2L(FX, FY), FOOT_NUT_R * K / HIDPI),
    'display': (*P2L(GLASS[0], GLASS[1]), *P2L(GLASS[2], GLASS[3])),
    'pedal': (ox / HIDPI, oy / HIDPI, pw / HIDPI, ph / HIDPI),
}
with open(os.path.join(OUT, 'layout.json'), 'w') as f:
    json.dump({'sprites': sprites, 'hit': hit}, f, indent=1)


def rect_of(b):
    return (b[0], b[1], b[2] - b[0], b[3] - b[1])


lines = ['// generated by tools/build_art.py - do not edit', '#pragma once', 'namespace Layout {',
         'struct R { float x, y, w, h; };', 'struct Sprite { const char* name; R r; };',
         'constexpr float W = %d.0f, H = %d.0f, topBar = %d.0f, bottomBar = %d.0f;' % (LOGICAL_W, LOGICAL_H, TOP_BAR, BOTTOM_BAR),
         'constexpr Sprite sprites[] = {']
for k, v in sprites.items():
    lines.append('    { "%s", { %.2ff, %.2ff, %.2ff, %.2ff } },' % (k, *v))
lines.append('};')
lines.append('constexpr R hitLeft { %.2ff, %.2ff, %.2ff, %.2ff };' % rect_of(hit['left']))
lines.append('constexpr R hitRight { %.2ff, %.2ff, %.2ff, %.2ff };' % rect_of(hit['right']))
lines.append('constexpr R hitDisplay { %.2ff, %.2ff, %.2ff, %.2ff };' % rect_of(hit['display']))
for k in ('mix', 'fav', 'foot'):
    lines.append('constexpr float %sX = %.2ff, %sY = %.2ff, %sR = %.2ff;' % (k, hit[k][0], k, hit[k][1], k, hit[k][2]))
lines.append('constexpr R pedal { %.2ff, %.2ff, %.2ff, %.2ff };' % hit['pedal'])
lines.append('constexpr float ringX = %.3ff, ringY = %.3ff;  // light ring centre' % (FC[0] / HIDPI, FC[1] / HIDPI))
lines.append('}')
with open(os.path.join(ROOT, 'Layout.h'), 'w') as f:
    f.write('\n'.join(lines) + '\n')
print('done:', len(sprites), 'sprites')
