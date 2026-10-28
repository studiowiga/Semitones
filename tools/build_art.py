#!/usr/bin/env python3
"""Builds every image used by the Semitones editor from the design picture (v3).

Run:  python3 -I tools/build_art.py   (from the repository root)

Outputs (assets/):
  background.jpg      whole editor background, 2x (1520 x 1916): design with the
                      display digits, the ring light and the status text removed,
                      ghost dot-matrix segments and the engraved name added
  seg_<id>.png        lit dot-matrix segments (glow included)
  ringlight.png       light the footswitch ring throws on the faceplate
  ring_lit.png        the lit light pipe
  ring_comet.png      rotating light with long trail and halo (rotated by the editor)
  press_<id>.png      pressed state of arrows, MIX, FAV, footswitch
Layout.h              positions of every sprite (design units)
"""
import json, os, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

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
    return np.clip((r - np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)) / soft + 0.5, 0, 1)


def poly_mask(h, w, poly, ss=8):
    im = Image.new('L', (w * ss, h * ss), 0)
    ImageDraw.Draw(im).polygon([(x * ss, y * ss) for x, y in poly], fill=255)
    return np.asarray(im.resize((w, h), Image.BOX)).astype(np.float32) / 255.0


def gblur(a, s):
    if s <= 0:
        return a
    k = int(s * 3) * 2 + 1
    return cv2.GaussianBlur(a, (k, k), s, borderType=cv2.BORDER_REFLECT)


def shift(a, dx, dy):
    M_ = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(a, M_, (a.shape[1], a.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


# ===================================================== 1. clean the design (source resolution)
src = np.asarray(Image.open(os.path.join(DESIGN, 'source_design.jpg')).convert('RGB')).astype(np.float32) / 255.0
H0, W0 = src.shape[:2]
rgb = src.copy()
bx = rgb[..., 2] - 0.5 * (rgb[..., 0] + rgb[..., 1])
yy0, xx0 = np.mgrid[0:H0, 0:W0].astype(np.float32)


def inpaint(img, mask_u8, r=5):
    u8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    out = cv2.inpaint(cv2.cvtColor(u8, cv2.COLOR_RGB2BGR), mask_u8, r, cv2.INPAINT_TELEA)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0


# ---- 1a. display: remove every blue element (lit, ghost, MIX/FAV ticks), then a
#          smooth glass (keeps the diagonal reflection) with a fresh faint dot grid
gx0, gy0, gx1, gy1 = [int(v) for v in GLASS_INNER]
m = np.zeros((H0, W0), np.uint8)
m[gy0:gy1, gx0:gx1] = (bx[gy0:gy1, gx0:gx1] > 0.03).astype(np.uint8) * 255
m = cv2.dilate(m, np.ones((5, 5), np.uint8), iterations=2)
inner = np.zeros_like(m)
cv2.rectangle(inner, (gx0 + 2, gy0 + 2), (gx1 - 2, gy1 - 2), 255, -1)
m = cv2.bitwise_and(m, inner)
cleaned = inpaint(rgb, m, 7)
glass = np.zeros((H0, W0), np.float32)
cv2.rectangle(glass, (gx0 + 1, gy0 + 1), (gx1 - 1, gy1 - 1), 1.0, -1)
glass = gblur(glass, 1.0)
smooth = gblur(cleaned, 2.2)
rgb = rgb * (1 - glass[..., None]) + smooth * glass[..., None]

# ---- 1b. footswitch: remove the ring light (the metal is neutral grey: rebuild
#          it from the red channel, which the blue light barely touches)
fx, fy = FOOT
dfo = np.sqrt((xx0 - fx) ** 2 + (yy0 - fy) ** 2)
zone = np.clip((190 - dfo) / 30, 0, 1)
w_blue = np.clip(bx / 0.035, 0, 1) * zone
w_blue = gblur(w_blue, 1.0)[..., None]
r_ = rgb[..., 0:1]
neutral = np.concatenate([r_ * 1.0, r_ * 1.01, r_ * 1.02], -1)
rgb = rgb * (1 - w_blue) + neutral * w_blue
# the unlit light pipe / frosted collar: darker, matte, cool grey
band_off = np.clip(1 - np.abs(dfo - RING_R) / (RING_W * 0.9), 0, 1) ** 1.2
rgb = rgb * (1 - 0.40 * band_off[..., None])
collar = np.clip((FOOT_COLLAR_R - dfo) / 2, 0, 1) * np.clip((dfo - (RING_R - RING_W)) / 2, 0, 1)
rgb = rgb * (1 - 0.12 * collar[..., None])

# ---- 1c. status pill: erase the baked text
px0, py0, px1, py1 = [int(v) for v in STATUS_PILL]
lum = rgb.mean(2)
pill = np.zeros((H0, W0), np.uint8)
inner_p = (slice(py0 + 4, py1 - 4), slice(px0 + 10, px1 - 10))
loc = lum[inner_p]
pill[inner_p] = (loc > np.median(loc) + 0.03).astype(np.uint8) * 255
pill = cv2.dilate(pill, np.ones((3, 3), np.uint8), iterations=2)
rgb = inpaint(rgb, pill, 4)
pm_ = np.zeros((H0, W0), np.float32)
pm_[py0 + 3:py1 - 3, px0 + 8:px1 - 8] = 1
pm_ = gblur(pm_, 1.5)
pill_col = np.median(rgb[py0 + 6:py1 - 6, px0 + 14:px1 - 14].reshape(-1, 3), 0)
rgb = rgb * (1 - pm_[..., None]) + (0.5 * rgb + 0.5 * pill_col) * pm_[..., None]
rgb = np.clip(rgb, 0, 1)
Image.fromarray((rgb * 255).astype(np.uint8)).save(os.path.join(DESIGN, 'clean_preview.png'))

# ===================================================== 2. canvas (2x)
CW, CH = LOGICAL_W * HIDPI, LOGICAL_H * HIDPI
KX, KY = CW / W0, CH / H0
K = 0.5 * (KX + KY)
big = cv2.resize(rgb, (CW, CH), interpolation=cv2.INTER_LANCZOS4)
big = np.clip(big + 0.55 * (big - gblur(big, 1.6)), 0, 1)
canvas = big


def P2C(x, y):
    return x * KX, y * KY


def P2L(x, y):
    cx, cy = P2C(x, y)
    return cx / HIDPI, cy / HIDPI


yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32)

# ===================================================== 3. engraved name
def text_mask(text, width_px, track, ss=4):
    fpath = os.path.join(ROOT, 'assets', 'Poppins-Bold.ttf')
    size = 200 * ss
    font = ImageFont.truetype(fpath, size)
    tmp = ImageDraw.Draw(Image.new('L', (8, 8)))
    adv = [tmp.textlength(ch, font=font) for ch in text]
    total = sum(adv) + track * size * (len(text) - 1)
    bb = tmp.textbbox((0, 0), text, font=font)
    Hh = int((bb[3] - bb[1]) * 1.8) + 40
    Ww = int(total) + 80
    im = Image.new('L', (Ww, Hh), 0)
    d = ImageDraw.Draw(im)
    x = 40
    for ch, a in zip(text, adv):
        d.text((x, Hh / 2 - (bb[1] + bb[3]) / 2), ch, font=font, fill=255)
        x += a + track * size
    mm = np.asarray(im).astype(np.float32) / 255.0
    ys, xs = np.nonzero(mm > 0.01)
    mm = mm[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    sc = width_px / mm.shape[1]
    return np.clip(cv2.resize(mm, (max(1, int(round(mm.shape[1] * sc))), max(1, int(round(mm.shape[0] * sc)))),
                              interpolation=cv2.INTER_AREA), 0, 1)


tm = text_mask(ENGRAVE_TEXT, ENGRAVE_W * K, ENGRAVE_TRACK)
th_, tw_ = tm.shape
ecx, ecy = P2C(*ENGRAVE_C)
pad = int(10 * HIDPI)
EM = np.zeros((th_ + 2 * pad, tw_ + 2 * pad), np.float32)
EM[pad:pad + th_, pad:pad + tw_] = tm
X0e, Y0e = int(round(ecx - tw_ / 2)) - pad, int(round(ecy - th_ / 2)) - pad
reg = canvas[Y0e:Y0e + EM.shape[0], X0e:X0e + EM.shape[1]].copy()
# height field of a CNC cut with slightly bevelled walls
depth = 1.5 * HIDPI
hmask = gblur(EM, 0.45 * HIDPI)
hgt = -depth * hmask
gyh, gxh = np.gradient(hgt)
nrm = np.stack([-gxh, -gyh, np.ones_like(hgt)], -1)
nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
Ld = np.array([-0.55, -0.62, 0.56]); Ld /= np.linalg.norm(Ld)
lam = np.clip((nrm * Ld).sum(-1), 0, 1)
lam_flat = Ld[2]
shade = lam / lam_flat                                     # 1 on flat areas
Hv = Ld + np.array([0, 0, 1.0]); Hv /= np.linalg.norm(Hv)
spec = np.clip((nrm * Hv).sum(-1), 0, 1) ** 40
spec_flat = Hv[2] ** 40
# cast shadow of the top-left walls on the floor
shadow = np.clip(EM - shift(EM, 1.1 * HIDPI, 1.3 * HIDPI), 0, 1)
shadow = gblur(shadow, 0.5 * HIDPI) * EM
# ambient occlusion in the corners of the floor
ao = 1 - 0.25 * np.clip(EM - gblur(EM, 1.8 * HIDPI), 0, 1) * 2
# floor: bead-blasted, darker than the brushed surface, fine grain
grain = gblur(RNG.normal(0, 1, EM.shape).astype(np.float32), 0.6)
floor_l = (0.7 * gblur(reg, 2.5).mean(2) + 0.3 * reg.mean(2)) * 0.78 + grain * 0.010
floor = np.stack([floor_l * 0.98, floor_l * 0.99, floor_l * 1.02], -1)
inside = np.clip(EM * 1.2, 0, 1)
base = reg * (1 - inside[..., None]) + floor * inside[..., None]
lit = base * (shade * ao * (1 - 0.55 * shadow))[..., None]
lit = lit + 0.35 * np.clip(spec - spec_flat, 0, 1)[..., None]
lit = np.clip(lit, 0, 1)
canvas[Y0e:Y0e + EM.shape[0], X0e:X0e + EM.shape[1]] = lit

# ===================================================== 4. dot-matrix display
P = DOT_PITCH * K
ox_g, oy_g = P2C(GLASS_INNER[0], GLASS_INNER[1])
fxg = np.mod(xx - ox_g, P) - P / 2
fyg = np.mod(yy - oy_g, P) - P / 2
dots = np.clip((0.40 * P - np.sqrt(fxg ** 2 + fyg ** 2)) / 0.8 + 0.5, 0, 1)      # round LCD dots
gmask = np.zeros((CH, CW), np.float32)
gx0c, gy0c = P2C(GLASS_INNER[0] + 3, GLASS_INNER[1] + 3)
gx1c, gy1c = P2C(GLASS_INNER[2] - 3, GLASS_INNER[3] - 3)
gmask[int(gy0c):int(gy1c), int(gx0c):int(gx1c)] = 1
gmask = gblur(gmask, 1.0)
# empty dot grid, very faint
canvas = canvas + (dots * gmask * 0.016)[..., None] * np.array([0.6, 0.8, 1.0])

LIT = np.array([40.0, 168.0, 255.0]) / 255.0
LIT_CORE = np.array([170.0, 235.0, 255.0]) / 255.0
GHOST = np.array([20.0, 52.0, 120.0]) / 255.0


def poly_c(poly):
    return [P2C(x, y) for x, y in poly]


layers = all_layers()
seg_masks = {name: poly_mask(CH, CW, poly_c(poly)) for name, poly in layers}
ghost_all = np.zeros((CH, CW), np.float32)
for v in seg_masks.values():
    ghost_all = np.maximum(ghost_all, v)
gd = ghost_all * dots
canvas = canvas * (1 - gd[..., None] * 0.42) + GHOST * gd[..., None] * 0.42
canvas = np.clip(canvas, 0, 1)


def lit_sprite(mask, name):
    md = mask * dots
    er = cv2.erode(mask, np.ones((5, 5), np.uint8), iterations=2)
    inner_c = gblur(er, 2.0)
    col_l = srgb2lin(LIT)[None, None, :] * md[..., None] * 1.25 + srgb2lin(LIT_CORE)[None, None, :] * (md * inner_c * 0.9)[..., None]
    soft = gblur(mask, 0.8 * HIDPI) * 0.35                      # light leaking between the dots
    glow = soft + gblur(mask, 2.5 * HIDPI) * 0.75 + gblur(mask, 7.0 * HIDPI) * 0.45 + gblur(mask, 16 * HIDPI) * 0.22
    glow_l = srgb2lin(LIT)[None, None, :] * glow[..., None] * 0.75
    tot = col_l + glow_l
    a_ = np.clip(md + glow * 0.85, 0, 1)
    out = np.clip(lin2srgb(tot / np.maximum(a_[..., None], 1e-4)), 0, 1)
    ys, xs = np.nonzero(a_ > 0.004)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    to_img(np.concatenate([out[y0:y1, x0:x1], a_[y0:y1, x0:x1, None]], -1)).save(os.path.join(OUT, name + '.png'))
    return (x0 / HIDPI, y0 / HIDPI, (x1 - x0) / HIDPI, (y1 - y0) / HIDPI)


sprites = {}
for name, _ in layers:
    sprites['seg_' + name] = lit_sprite(seg_masks[name], 'seg_' + name)

FINAL = canvas.copy()
fu8 = np.clip(FINAL * 255 + 0.5, 0, 255).astype(np.uint8)
Image.fromarray(fu8, 'RGB').save(os.path.join(OUT, 'background.jpg'), quality=94, subsampling=0, optimize=True)
Image.fromarray(fu8, 'RGB').save(os.path.join(DESIGN, 'background_preview.png'))

# ===================================================== 5. ring light sprites
COL = srgb2lin(LIT)
CORE = srgb2lin(np.array([70.0, 185.0, 255.0]) / 255.0)
FC = P2C(*FOOT)
dx, dy = xx - FC[0], yy - FC[1]
dd = np.sqrt(dx * dx + dy * dy)
R = RING_R * K
RW = RING_W * K
band = np.clip(RW / 2 - np.abs(dd - R) + 0.6, 0, 1)
dr = np.abs(dd - R)
src_h = 8.0 * HIDPI
E = (src_h ** 2 / (dr ** 2 + src_h ** 2)) ** 1.5
E_wide = np.exp(-dr / (34 * HIDPI)) * 0.40
illum = np.clip(E * 1.6 + E_wide, 0, 3) * (1 - band)
lin = srgb2lin(FINAL)
add = lin * illum[..., None] * COL[None, None, :] * 2.6 + illum[..., None] * COL * 0.03
target = lin2srgb(lin + add)
diff = np.clip(target - FINAL, 0, 1)
a_ = np.clip(diff.max(2) / np.maximum(1 - FINAL.max(2), 0.02), 0, 1)
a_ = np.clip(np.maximum(a_, np.clip(diff.max(2) * 3.0, 0, 1)), 0, 1)
colr = np.clip(np.where(a_[..., None] > 1e-4, (target - FINAL * (1 - a_[..., None])) / np.maximum(a_[..., None], 1e-4), 0), 0, 1)
box_r = int((FOOT_COLLAR_R + 60) * K)
bx_, by_ = int(FC[0]) - box_r, int(FC[1]) - box_r
to_img(np.concatenate([colr, a_[..., None]], -1)[by_:by_ + 2 * box_r, bx_:bx_ + 2 * box_r]).save(os.path.join(OUT, 'ringlight.png'), optimize=True)
sprites['ringlight'] = (bx_ / HIDPI, by_ / HIDPI, 2 * box_r / HIDPI, 2 * box_r / HIDPI)
relc = 1 - np.clip(np.abs(dd - R) / (RW / 2), 0, 1)
pipe_lin = CORE[None, None, :] * (relc ** 1.5)[..., None] * 0.55 + COL[None, None, :] * (0.55 + 0.35 * (1 - relc))[..., None]
pipe_s = lin2srgb(pipe_lin)
bloom = gblur(band, 3.0 * HIDPI) * 0.55 + gblur(band, 8 * HIDPI) * 0.30
halo_rgb = lin2srgb(COL[None, None, :] * np.ones((CH, CW, 1)))
a_h = np.clip(bloom * (1 - band), 0, 1)
out_rgb = pipe_s * band[..., None] + halo_rgb * a_h[..., None]
out_a = np.clip(band + a_h, 0, 1)
out_rgb = np.clip(np.where(out_a[..., None] > 1e-4, out_rgb / np.maximum(out_a[..., None], 1e-4), 0), 0, 1)
to_img(np.concatenate([out_rgb, out_a[..., None]], -1)[by_:by_ + 2 * box_r, bx_:bx_ + 2 * box_r]).save(os.path.join(OUT, 'ring_lit.png'), optimize=True)
sprites['ring_lit'] = sprites['ringlight']

# rotating light: soft glowing head, very long blurred trail, halo
half = int(np.ceil(R + RW + 70 * HIDPI))
cs = 2 * half
yy2, xx2 = np.mgrid[0:cs, 0:cs].astype(np.float32)
ddx, ddy = xx2 - half, yy2 - half
d2 = np.sqrt(ddx * ddx + ddy * ddy)
ang = np.arctan2(ddy, ddx)
phi = np.mod(0.0 - ang, 2 * np.pi)
prof = np.exp(-phi / 3.4) * np.clip(1 - phi / (1.9 * np.pi), 0, 1) ** 1.15
head = np.exp(-(phi / 0.38) ** 2) + np.exp(-((2 * np.pi - phi) / 0.14) ** 2) * 0.8
band2 = np.clip(RW / 2 - np.abs(d2 - R) + 0.6, 0, 1)
src_ = band2 * np.clip(prof + 0.8 * head, 0, 1.6)


def nblur(a, sg):
    return gblur(a, sg) / (gblur(band2, sg).max() + 1e-6)


core = nblur(src_, 1.8 * HIDPI)
halo = (nblur(src_, 5 * HIDPI) * 0.85 + nblur(src_, 12 * HIDPI) * 0.65 +
        nblur(src_, 24 * HIDPI) * 0.45 + nblur(band2 * head, 16 * HIDPI) * 0.6)
hot = nblur(band2 * head, 2.2 * HIDPI)
blue_s = lin2srgb(COL * 1.15)
pipe_c = lin2srgb(COL * 1.6 + CORE * 0.35)
hot_s = lin2srgb(CORE * 1.6)
wc, wh, wt = np.clip(core * 1.05, 0, 1), np.clip(halo * 0.80, 0, 0.92), np.clip(hot * 0.9, 0, 1)
ca = np.clip(1 - (1 - wc) * (1 - wh), 0, 1)
crgb = (pipe_c[None, None, :] * wc[..., None] + blue_s[None, None, :] * (wh * (1 - wc))[..., None])
crgb = crgb / np.maximum(ca[..., None], 1e-4)
crgb = np.clip(crgb * (1 - wt[..., None]) + hot_s[None, None, :] * wt[..., None], 0, 1)
to_img(np.concatenate([crgb, ca[..., None]], -1)).save(os.path.join(OUT, 'ring_comet.png'), optimize=True)
sprites['ring_comet'] = ((FC[0] - half) / HIDPI, (FC[1] - half) / HIDPI, cs / HIDPI, cs / HIDPI)

# ===================================================== 6. pressed states
def crop_box(x0, y0, x1, y1):
    a0 = P2C(x0, y0); a1 = P2C(x1, y1)
    return int(a0[0]), int(a0[1]), int(np.ceil(a1[0])), int(np.ceil(a1[1]))


def save_pressed(name, box, mask_fn, push=1.2, dark=0.80):
    X0, Y0, X1, Y1 = box
    reg_ = FINAL[Y0:Y1, X0:X1].copy()
    h, w = reg_.shape[:2]
    mk = mask_fn(h, w, X0, Y0)
    Mt = np.float32([[1, 0, push * HIDPI * 0.6], [0, 1, push * HIDPI]])
    moved = cv2.warpAffine(reg_, Mt, (w, h), borderMode=cv2.BORDER_REPLICATE)
    edge = np.clip(mk - cv2.erode(mk, np.ones((5, 5), np.uint8)), 0, 1)
    o = reg_ * (1 - mk[..., None]) + moved * dark * mk[..., None]
    o = o * (1 - 0.25 * gblur(edge, 1.5)[..., None])
    a = np.clip(gblur(mk, 1.0) * 1.15, 0, 1)
    to_img(np.concatenate([o, a[..., None]], -1)).save(os.path.join(OUT, 'press_' + name + '.png'), optimize=True)
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
fvx, fvy, fvr = FAV_BTN
save_pressed('fav', crop_box(fvx - fvr - 6, fvy - fvr - 6, fvx + fvr + 6, fvy + fvr + 6), circ_mask(fvx, fvy, fvr))
save_pressed('left', crop_box(*ARROW_L_BOX), tri_mask(ARROW_L), push=1.0)
save_pressed('right', crop_box(*ARROW_R_BOX), tri_mask(ARROW_R), push=1.0)

X0, Y0, X1, Y1 = crop_box(fx - FOOT_NUT_R, fy - FOOT_NUT_R, fx + FOOT_NUT_R, fy + FOOT_NUT_R)
reg_ = FINAL[Y0:Y1, X0:X1].copy()
h, w = reg_.shape[:2]
c = P2C(fx, fy)
cxl, cyl = c[0] - X0, c[1] - Y0
Mr = cv2.getRotationMatrix2D((cxl, cyl), 0, 0.97)
Mr[1, 2] += 1.2 * HIDPI
sunk = cv2.warpAffine(reg_, Mr, (w, h), borderMode=cv2.BORDER_REPLICATE)
chm = disc(h, w, cxl, cyl, (FOOT_NUT_R - 6) * K, 1.5)
o = reg_ * (1 - chm[..., None]) + sunk * chm[..., None]
darkd = disc(h, w, cxl, cyl + 0.6 * HIDPI, FOOT_CAP_R * K * 1.02, 2.0)
o = o * (1 - 0.25 * darkd[..., None])
to_img(np.concatenate([o, chm[..., None]], -1)).save(os.path.join(OUT, 'press_foot.png'), optimize=True)
sprites['press_foot'] = (X0 / HIDPI, Y0 / HIDPI, w / HIDPI, h / HIDPI)

# ===================================================== 7. hit areas + Layout.h
hit = {
    'left': (*P2L(ARROW_L_BOX[0], ARROW_L_BOX[1]), *P2L(ARROW_L_BOX[2], ARROW_L_BOX[3])),
    'right': (*P2L(ARROW_R_BOX[0], ARROW_R_BOX[1]), *P2L(ARROW_R_BOX[2], ARROW_R_BOX[3])),
    'mix': (*P2L(mx, my), mr * K / HIDPI + 4),
    'fav': (*P2L(fvx, fvy), fvr * K / HIDPI + 4),
    'foot': (*P2L(fx, fy), FOOT_COLLAR_R * K / HIDPI),
    'display': (*P2L(GLASS[0], GLASS[1]), *P2L(GLASS[2], GLASS[3])),
    'status': (*P2L(STATUS_PILL[0], STATUS_PILL[1]), *P2L(STATUS_PILL[2], STATUS_PILL[3])),
}
with open(os.path.join(OUT, 'layout.json'), 'w') as f:
    json.dump({'sprites': sprites, 'hit': hit}, f, indent=1)


def rect_of(b):
    return (b[0], b[1], b[2] - b[0], b[3] - b[1])


lines = ['// generated by tools/build_art.py - do not edit', '#pragma once', 'namespace Layout {',
         'struct R { float x, y, w, h; };', 'struct Sprite { const char* name; R r; };',
         'constexpr float W = %d.0f, H = %d.0f;' % (LOGICAL_W, LOGICAL_H),
         'constexpr Sprite sprites[] = {']
for k, v in sprites.items():
    lines.append('    { "%s", { %.2ff, %.2ff, %.2ff, %.2ff } },' % (k, *v))
lines.append('};')
lines.append('constexpr R hitLeft { %.2ff, %.2ff, %.2ff, %.2ff };' % rect_of(hit['left']))
lines.append('constexpr R hitRight { %.2ff, %.2ff, %.2ff, %.2ff };' % rect_of(hit['right']))
lines.append('constexpr R hitDisplay { %.2ff, %.2ff, %.2ff, %.2ff };' % rect_of(hit['display']))
lines.append('constexpr R statusBox { %.2ff, %.2ff, %.2ff, %.2ff };   // status pill' % rect_of(hit['status']))
lines.append('constexpr R presetBox { %.2ff, %.2ff, %.2ff, %.2ff };   // preset menu (top strip)' % PRESET_BOX)
for k in ('mix', 'fav', 'foot'):
    lines.append('constexpr float %sX = %.2ff, %sY = %.2ff, %sR = %.2ff;' % (k, hit[k][0], k, hit[k][1], k, hit[k][2]))
lines.append('constexpr float defaultScale = 0.5f;   // default window = 380 x 479 (simple pedal format, like Echoflex / Holyverb)')
lines.append('constexpr float ringX = %.3ff, ringY = %.3ff;  // light ring centre' % (FC[0] / HIDPI, FC[1] / HIDPI))
lines.append('}')
with open(os.path.join(ROOT, 'Layout.h'), 'w') as f:
    f.write('\n'.join(lines) + '\n')
print('done:', len(sprites), 'sprites')
