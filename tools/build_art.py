#!/usr/bin/env python3
"""Builds every image used by the Semitones editor from the reference photo.

Run:  python3 -I tools/build_art.py   (from the repository root)

Outputs (assets/):
  background.png            whole editor background, 2x (1520 x 1916)
  seg_<id>.png              lit 7-segment elements (glow included)
  dot_mix.png / dot_fav.png lit indicator dots
  led_<col>.png             lit LED lens + optical halo  (red / blue / green)
  ledlight_<col>.png        light received by the faceplate (alpha layer)
  press_<id>.png            pressed state of arrows, MIX, FAV, footswitch
  layout.h                  positions of every sprite (logical coordinates)
"""
import json, os, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from art_common import *  # noqa

OUT = os.path.join(ROOT, 'assets')
DESIGN = os.path.join(ROOT, 'design')
os.makedirs(OUT, exist_ok=True)
RNG = np.random.default_rng(7)

FONT_BOLD = os.path.join(ROOT, 'assets', 'Poppins-Bold.ttf')

# ----------------------------------------------------------------- helpers
def to_f(im):
    return np.asarray(im).astype(np.float32) / 255.0


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


# ===================================================== 1. clean the photo
src = Image.open(os.path.join(DESIGN, 'source_photo.png')).convert('RGBA')
P = to_f(src)
H0, W0 = P.shape[:2]
rgb = P[..., :3].copy()
alpha = P[..., 3].copy()

# ---- 1a. display: remove every lit / ghost segment, keep the glass texture
gx0, gy0, gx1, gy1 = [int(v) for v in GLASS_INNER]
u8 = (rgb * 255).astype(np.uint8)
blue_excess = rgb[..., 2] - 0.5 * (rgb[..., 0] + rgb[..., 1])
m = np.zeros((H0, W0), np.uint8)
win = blue_excess[gy0:gy1, gx0:gx1]
m[gy0:gy1, gx0:gx1] = (win > 0.055).astype(np.uint8) * 255
m = cv2.dilate(m, np.ones((5, 5), np.uint8), iterations=2)
# also the halos (the glass is lighter around lit segments)
lum = rgb.mean(2)
halo = np.zeros_like(m)
halo[gy0:gy1, gx0:gx1] = (lum[gy0:gy1, gx0:gx1] > 0.075).astype(np.uint8) * 255
m = np.maximum(m, cv2.dilate(halo, np.ones((3, 3), np.uint8)))
# keep the bezel edge out of the mask
inner = np.zeros_like(m)
cv2.rectangle(inner, (gx0 + 4, gy0 + 4), (gx1 - 4, gy1 - 4), 255, -1)
m = cv2.bitwise_and(m, inner)
bgr = cv2.cvtColor(u8, cv2.COLOR_RGB2BGR)
bgr = cv2.inpaint(bgr, m, 9, cv2.INPAINT_TELEA)
fixed = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
# the glass: very dark, slightly blue, fine grain
glass_col = np.array([11.3, 11.2, 19.8]) / 255.0
mm = gblur(m.astype(np.float32) / 255.0, 2.0)[..., None]
grain = RNG.normal(0, 1, (H0, W0, 1)).astype(np.float32) * np.array([2.6, 2.6, 4.2]) / 255.0
lowf = gblur(fixed, 6.0)
# pull the inpainted area towards the clean glass level (no blotches)
target = 0.55 * lowf + 0.45 * glass_col
fixed = fixed * (1 - mm) + (target + grain) * mm
rgb[gy0:gy1, gx0:gx1] = fixed[gy0:gy1, gx0:gx1]

# ---- 1b. LED: remove the red light from the faceplate
lx, ly = LED_C
yy, xx = np.mgrid[0:H0, 0:W0].astype(np.float32)
dist = np.sqrt((xx - lx) ** 2 + (yy - ly) ** 2)
redness = rgb[..., 0] - 0.5 * (rgb[..., 1] + rgb[..., 2])
zone = (dist < 95).astype(np.float32)
# the faceplate is neutral grey: rebuild luminance from the least lit channels
gb = 0.5 * (rgb[..., 1] + rgb[..., 2])
neutral = np.stack([gb, gb, gb], -1)
w_led = np.clip(redness / 0.04, 0, 1) * zone
w_led = gblur(w_led, 1.0)[..., None]
rgb = rgb * (1 - w_led) + neutral * w_led
# remaining additive glow in G/B: estimate as a smooth radial excess
# measured against the same materials far from the LED
ring = (dist > 60) & (dist < 95)
for _ in range(1):
    pass
excess = np.zeros((H0, W0), np.float32)
# radial profile of luminance relative to a heavily blurred version that
# excludes the LED area -> the glow is the smooth positive difference
lum = rgb.mean(2)
base_est = lum.copy()
far = (dist > 42).astype(np.float32)
num = gblur(lum * far, 22.0)
den = gblur(far, 22.0) + 1e-4
smooth_far = num / den
smooth_all = gblur(lum, 22.0)
glow = np.clip(smooth_all - smooth_far, 0, None) * np.clip((70 - dist) / 30, 0, 1)
rgb = rgb - glow[..., None] * 0.9
# disc under the LED: rebuild the channel (flat grey + grain); the LED art
# drawn later covers the centre anyway
ch_x0, ch_x1 = 302, 346
chan = (xx >= ch_x0 - 0.5) & (xx <= ch_x1 + 0.5) & (dist < LED_RECESS_R + 6)
ref = rgb[432:446, ch_x0 + 3:ch_x1 - 3].reshape(-1, 3)
ref2 = rgb[528:540, ch_x0 + 3:ch_x1 - 3].reshape(-1, 3)
cref = np.concatenate([ref, ref2]).mean(0)
cstd = np.concatenate([ref, ref2]).std(0).mean()
noise = gblur(RNG.normal(0, 1, (H0, W0)).astype(np.float32), 0.6)
noise = noise / noise.std() * cstd * 0.8
chan_fill = cref[None, None, :] + noise[..., None]
cw = gblur(chan.astype(np.float32), 0.8)[..., None]
rgb = rgb * (1 - cw) + chan_fill * cw
# metal strips left/right of the channel inside the disc: inpaint
side = ((dist < LED_RECESS_R + 5) & ~chan).astype(np.uint8) * 255
u8 = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
bgr = cv2.inpaint(cv2.cvtColor(u8, cv2.COLOR_RGB2BGR), side, 5, cv2.INPAINT_TELEA)
rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
rgb = np.clip(rgb, 0, 1)

Image.fromarray((rgb * 255).astype(np.uint8)).save(os.path.join(DESIGN, 'clean_preview.png'))

# ===================================================== 2. upscale to canvas
ys_, xs_ = np.nonzero(alpha > 0.02)
bx0, by0, bx1, by1 = xs_.min(), ys_.min(), xs_.max() + 1, ys_.max() + 1
avail_h = (LOGICAL_H - TOP_BAR - BOTTOM_BAR) * HIDPI
K = avail_h / float(by1 - by0)            # photo px -> canvas px
CW, CH = LOGICAL_W * HIDPI, LOGICAL_H * HIDPI
pw = int(round((bx1 - bx0) * K))
ph = int(round((by1 - by0) * K))
ox = (CW - pw) / 2.0
oy = TOP_BAR * HIDPI
print('scale K =', K, 'pedal box', pw, ph, 'offset', ox, oy)


def P2C(x, y):
    """photo coords -> canvas px (2x)"""
    return ox + (x - bx0) * K, oy + (y - by0) * K


def P2L(x, y):
    cx, cy = P2C(x, y)
    return cx / HIDPI, cy / HIDPI


crop_rgb = rgb[by0:by1, bx0:bx1]
crop_a = alpha[by0:by1, bx0:bx1]
# premultiply before resampling to avoid fringes
pm = np.concatenate([crop_rgb * crop_a[..., None], crop_a[..., None]], -1)
big = cv2.resize(pm, (pw, ph), interpolation=cv2.INTER_LANCZOS4)
big = np.clip(big, 0, 1)
ba = big[..., 3:4]
brgb = np.where(ba > 1e-4, big[..., :3] / np.maximum(ba, 1e-4), 0)
brgb = np.clip(brgb, 0, 1)

# ---- 2b. restore crisp vertical brushing on the aluminium
lumb = brgb.mean(2)
sat = brgb.max(2) - brgb.min(2)
# brushed areas only (the recessed grey shapes are bead-blasted, not brushed)
gph = crop_rgb.mean(2)
hp = np.abs(gph - cv2.blur(gph, (7, 1)))
en = cv2.GaussianBlur(hp, (0, 0), 3)
brushed = np.clip((en - 0.052) / 0.014, 0, 1)
brushed = cv2.resize(brushed, (pw, ph), interpolation=cv2.INTER_LINEAR)
metal = ((lumb > 0.33) & (sat < 0.08) & (ba[..., 0] > 0.99)).astype(np.float32) * brushed
metal = gblur(metal, 1.2)
streak = RNG.normal(0, 1, (ph, pw)).astype(np.float32)
streak = cv2.GaussianBlur(streak, (1, 0), sigmaX=0.6, sigmaY=34.0) if False else \
    cv2.GaussianBlur(streak, (3, 241), sigmaX=0.55, sigmaY=40.0)
streak /= streak.std() + 1e-6
fine = cv2.GaussianBlur(RNG.normal(0, 1, (ph, pw)).astype(np.float32), (3, 31), sigmaX=0.45, sigmaY=5.0)
fine /= fine.std() + 1e-6
amp = (0.022 + 0.020 * np.clip((lumb - 0.4) / 0.4, 0, 1)) * metal
# unsharp the photo detail a little (Lanczos softens the brushing)
blur = gblur(brgb, 1.4)
brgb = np.clip(brgb + 0.55 * (brgb - blur) * metal[..., None], 0, 1)
brgb = np.clip(brgb + ((0.75 * streak + 0.45 * fine) * amp)[..., None], 0, 1)

canvas_rgb = np.zeros((CH, CW, 3), np.float32)
canvas_a = np.zeros((CH, CW), np.float32)
ix, iy = int(round(ox)), int(round(oy))
canvas_rgb[iy:iy + ph, ix:ix + pw] = brgb
canvas_a[iy:iy + ph, ix:ix + pw] = ba[..., 0]
ox, oy = float(ix), float(iy)   # exact integer placement


# ===================================================== 3. display art
def poly_c(poly):
    return [P2C(x, y) for x, y in poly]


GHOST = np.array([3.0, 22.0, 52.0]) / 255.0
LIT = np.array([38.0, 158.0, 250.0]) / 255.0
LIT_CORE = np.array([120.0, 212.0, 255.0]) / 255.0

layers = all_layers()
seg_masks = {}
for name, poly in layers:
    seg_masks[name] = poly_mask(CH, CW, poly_c(poly))
dot_masks = {
    'dot_mix': disc(CH, CW, *P2C(DOT_MIX[0], DOT_MIX[1]), DOT_MIX[2] * K, 1.0),
    'dot_fav': disc(CH, CW, *P2C(DOT_FAV[0], DOT_FAV[1]), DOT_FAV[2] * K, 1.0),
}
ghost_all = np.zeros((CH, CW), np.float32)
for v in list(seg_masks.values()) + list(dot_masks.values()):
    ghost_all = np.maximum(ghost_all, v)
# ghost segments: dim blue, a bit of internal unevenness like the photo
gtex = 0.82 + 0.18 * gblur(RNG.normal(0, 1, (CH, CW)).astype(np.float32), 6) * 3
gcol = GHOST[None, None, :] * np.clip(gtex, 0.6, 1.25)[..., None]
canvas_rgb = canvas_rgb * (1 - ghost_all[..., None] * 0.50) + gcol * ghost_all[..., None] * 0.50


def lit_sprite(mask, name):
    """lit element = segment colour + bloom, written as straight RGBA."""
    lin_glow = gblur(mask, 3.2 * HIDPI) * 0.55 + gblur(mask, 9.0 * HIDPI) * 0.28
    core = gblur(mask, 1.2) ** 1.5
    # inner gradient: brighter centre line
    er = cv2.erode(mask, np.ones((5, 5), np.uint8), iterations=2)
    inner = gblur(er, 2.5)
    col = (LIT[None, None, :] * mask[..., None] * 0.92 +
           LIT_CORE[None, None, :] * (inner * 0.35)[..., None])
    glow_rgb = LIT[None, None, :] * lin_glow[..., None]
    rgb_ = col + glow_rgb * (1 - mask[..., None])
    a_ = np.clip(np.maximum(mask, np.clip(rgb_.max(2) * 1.15, 0, 1)), 0, 1)
    out = np.where(a_[..., None] > 1e-4, rgb_ / np.maximum(a_[..., None], 1e-4), 0)
    out = np.clip(out, 0, 1)
    ys, xs = np.nonzero(a_ > 0.004)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    rgba = np.concatenate([out[y0:y1, x0:x1], a_[y0:y1, x0:x1, None]], -1)
    to_img(rgba).save(os.path.join(OUT, name + '.png'))
    return (x0 / HIDPI, y0 / HIDPI, (x1 - x0) / HIDPI, (y1 - y0) / HIDPI)


sprites = {}
for name, _ in layers:
    sprites['seg_' + name] = lit_sprite(seg_masks[name], 'seg_' + name)
for name, mk in dot_masks.items():
    sprites[name] = lit_sprite(mk, name)

# ===================================================== 4. LED (off art)
LC = P2C(*LED_C)
rec_r = LED_RECESS_R * K
bez_r = LED_BEZEL_R * K
lens_r = LED_LENS_R * K
yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32)
dx, dy = xx - LC[0], yy - LC[1]
dd = np.sqrt(dx * dx + dy * dy)
ang_l = (-dx - dy) / (np.sqrt(2) * np.maximum(dd, 1e-3))     # +1 facing light (top-left)

# recess (counterbore) : same grey as the channel, darker on the lit side wall
recess = np.clip(rec_r - dd + 0.5, 0, 1)
chan_c = canvas_rgb[int(LC[1] - rec_r - 10 * HIDPI), int(LC[0])].copy()
wall = np.clip((dd - (rec_r - 3.2 * HIDPI)) / (3.2 * HIDPI), 0, 1) * recess
floor = chan_c * 0.80
rc = floor[None, None, :] * (1 + 0.04 * gblur(RNG.normal(0, 1, (CH, CW)).astype(np.float32), 1.0)[..., None])
# wall: the side facing the light is in shadow (it is a hole)
wall_shade = 0.75 + 0.25 * np.clip(-ang_l, 0, 1)
rc = rc * (1 - wall[..., None]) + (floor * wall_shade[..., None]) * wall[..., None]
# outer lip highlight on the far (bottom-right) edge
lip = np.clip(1 - np.abs(dd - rec_r) / (1.2 * HIDPI), 0, 1) * np.clip(-ang_l, 0, 1)
canvas_rgb = canvas_rgb * (1 - recess[..., None]) + rc * recess[..., None]
canvas_rgb = np.clip(canvas_rgb + lip[..., None] * 0.12, 0, 1)
# bezel: smoky translucent plastic ring, soft shadow cast towards bottom-right
sh = gblur(np.clip(bez_r - np.sqrt((dx - 1.6 * HIDPI) ** 2 + (dy - 1.8 * HIDPI) ** 2) + 0.5, 0, 1), 1.6 * HIDPI)
canvas_rgb *= (1 - 0.35 * sh * recess)[..., None]
bez = np.clip(bez_r - dd + 0.5, 0, 1)
ring = bez * np.clip(dd - lens_r + 0.5, 0, 1)
bez_col = np.array([0.30, 0.285, 0.29])
bshade = 0.85 + 0.35 * ang_l
canvas_rgb = canvas_rgb * (1 - bez[..., None]) + (bez_col[None, None, :] * bshade[..., None]) * bez[..., None]
# bezel top-left specular arc
spec = np.clip(1 - np.abs(dd - (bez_r - 2.0 * HIDPI)) / (1.4 * HIDPI), 0, 1) * np.clip(ang_l - 0.35, 0, 1) * ring
canvas_rgb = np.clip(canvas_rgb + spec[..., None] * 0.30, 0, 1)
# lens (off): frosted, slightly warm milky plastic with dome shading
lens = np.clip(lens_r - dd + 0.5, 0, 1)
rr = np.clip(dd / lens_r, 0, 1)
dome = 0.55 + 0.25 * ang_l * rr + 0.12 * (1 - rr ** 2)
lens_col = np.array([0.66, 0.635, 0.60])
lc_ = lens_col[None, None, :] * dome[..., None]
canvas_rgb = canvas_rgb * (1 - lens[..., None]) + lc_ * lens[..., None]
# small fixed reflection on the dome
hl = disc(CH, CW, LC[0] - 0.38 * lens_r, LC[1] - 0.42 * lens_r, 0.28 * lens_r, 2.0 * HIDPI)
canvas_rgb = np.clip(canvas_rgb + hl[..., None] * 0.30, 0, 1)
led_off_rgb = canvas_rgb.copy()

# ===================================================== 5. Studio Wiga logo
def draw_logo(h_px):
    """Black Studio Wiga logo (two interlaced rings + STUDIO WIGA)."""
    ss = 4
    H = int(h_px * ss)
    r_out = H * 0.47
    th = H * 0.15
    font = ImageFont.truetype(FONT_BOLD, int(H * 0.78))
    text = 'STUDIO WIGA'
    tmp = Image.new('L', (10, 10))
    tb = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=font)
    tw = tb[2] - tb[0]
    rings_w = r_out * 2 * 1.62
    gap = H * 0.42
    W = int(rings_w + gap + tw + H * 0.2)
    im = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(im)
    c1 = (r_out + 2, H / 2)
    c2 = (r_out + 2 + r_out * 1.24, H / 2)

    def ring(c, fill):
        d.ellipse([c[0] - r_out, c[1] - r_out, c[0] + r_out, c[1] + r_out], fill=fill)
        ri = r_out - th
        d.ellipse([c[0] - ri, c[1] - ri, c[0] + ri, c[1] + ri], fill=0)

    # ring 1 then ring 2 with a cut-out so the rings interlace
    a1 = Image.new('L', (W, H), 0); d1 = ImageDraw.Draw(a1)
    a2 = Image.new('L', (W, H), 0); d2 = ImageDraw.Draw(a2)
    for dd_, c in ((d1, c1), (d2, c2)):
        dd_.ellipse([c[0] - r_out, c[1] - r_out, c[0] + r_out, c[1] + r_out], fill=255)
        ri = r_out - th
        dd_.ellipse([c[0] - ri, c[1] - ri, c[0] + ri, c[1] + ri], fill=0)
    A1 = np.asarray(a1).astype(np.float32) / 255
    A2 = np.asarray(a2).astype(np.float32) / 255
    # gaps where ring2 passes over ring1 (upper crossing) and ring1 over ring2 (lower)
    yy_, xx_ = np.mgrid[0:H, 0:W].astype(np.float32)
    gapw = th * 0.55
    over2 = (yy_ < H / 2)      # upper crossing: ring2 on top
    A2d = cv2.dilate(A2, np.ones((int(gapw), int(gapw)), np.uint8))
    A1d = cv2.dilate(A1, np.ones((int(gapw), int(gapw)), np.uint8))
    R1 = A1 * np.where(over2, 1 - A2d, 1)
    R2 = A2 * np.where(over2, 1, 1 - A1d)
    rings = np.maximum(R1, R2)
    txt = Image.new('L', (W, H), 0)
    ImageDraw.Draw(txt).text((rings_w + gap - tb[0], (H - (tb[3] - tb[1])) / 2 - tb[1]), text, font=font, fill=255)
    T = np.asarray(txt).astype(np.float32) / 255
    A = np.maximum(rings, T)
    im = Image.fromarray((A * 255).astype(np.uint8)).resize((W // ss, H // ss), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255


logo = draw_logo(LOGO_H * K)
lh, lw = logo.shape
lcx, lcy = P2C(*LOGO_C)
lx0, ly0 = int(round(lcx - lw / 2)), int(round(lcy - lh / 2))
reg = canvas_rgb[ly0:ly0 + lh, lx0:lx0 + lw]
# silkscreen black ink: very dark, faint satin sheen following the brushing
ink = np.array([0.035, 0.035, 0.04])
sheen = 0.02 * (reg.mean(2, keepdims=True) - 0.55)
canvas_rgb[ly0:ly0 + lh, lx0:lx0 + lw] = reg * (1 - logo[..., None] * 0.96) + (ink + sheen) * logo[..., None] * 0.96

# ===================================================== 6. backdrop + shadow
bg = np.zeros((CH, CW, 3), np.float32)
top = np.array([0.105, 0.105, 0.115]); bot = np.array([0.055, 0.055, 0.062])
t = (yy / CH)[..., None]
bg[:] = top * (1 - t) + bot * t
vig = 1 - 0.35 * (((xx - CW / 2) / (CW / 2)) ** 2 + ((yy - CH / 2) / (CH / 2)) ** 2) * 0.5
bg *= vig[..., None]
bg += gblur(RNG.normal(0, 1, (CH, CW)).astype(np.float32), 0.7)[..., None] * 0.004
# soft shadow of the pedal (light top-left)
shm = np.zeros((CH, CW), np.float32)
sh_dx, sh_dy = int(9 * HIDPI), int(12 * HIDPI)
shm[sh_dy:, sh_dx:] = canvas_a[:-sh_dy, :-sh_dx]
shadow = gblur(shm, 14 * HIDPI) * 0.75 + gblur(canvas_a, 3 * HIDPI) * 0.35
bg *= (1 - np.clip(shadow, 0, 0.9))[..., None]
final = bg * (1 - canvas_a[..., None]) + canvas_rgb * canvas_a[..., None]
final_u8 = np.clip(final * 255 + 0.5, 0, 255).astype(np.uint8)
Image.fromarray(final_u8, 'RGB').save(os.path.join(OUT, 'background.jpg'), quality=94, subsampling=0, optimize=True)
Image.fromarray(final_u8, 'RGB').save(os.path.join(DESIGN, 'background_preview.png'))
FINAL = final.copy()

# ===================================================== 7. LED lit sprites + faceplate light
LED_COLS = {
    'red':   (np.array([1.00, 0.10, 0.12]), np.array([1.0, 0.93, 0.70])),
    'blue':  (np.array([0.10, 0.42, 1.00]), np.array([0.80, 0.93, 1.0])),
    'green': (np.array([0.12, 1.00, 0.30]), np.array([0.85, 1.0, 0.80])),
}
# light reaching the faceplate from a small source just above the lens
hsrc = 15.0 * HIDPI
E = hsrc / np.power(dd ** 2 + hsrc ** 2, 1.5) * (hsrc ** 2)        # cos/d^2
E = E / E.max()
E_wide = gblur(np.exp(-dd / (30 * HIDPI)), 2) * 0.45
illum = np.clip(E * 2.4 + E_wide * 1.3, 0, 4)
# the recess walls block part of the light: only what leaves the hole
illum *= np.clip((dd - lens_r) / (2 * HIDPI), 0, 1)
inside = np.clip(bez_r - dd + 0.5, 0, 1)
lin = srgb2lin(FINAL)
box_r = int(110 * HIDPI)
bx_, by_ = int(LC[0]) - box_r, int(LC[1]) - box_r
for nm, (col, core) in LED_COLS.items():
    # ---- faceplate light layer (exact over-compositing onto the background)
    add = lin * illum[..., None] * col[None, None, :] * 3.2 + illum[..., None] * col * 0.030
    target = lin2srgb(lin + add)
    diff = np.clip(target - FINAL, 0, 1)
    a_ = np.clip(diff.max(2) / np.maximum(1 - FINAL.max(2), 0.02), 0, 1)
    a_ = np.maximum(a_, np.clip(diff.max(2) * 3.0, 0, 1))
    a_ = np.clip(a_, 0, 1)
    colr = np.where(a_[..., None] > 1e-4, (target - FINAL * (1 - a_[..., None])) / np.maximum(a_[..., None], 1e-4), 0)
    colr = np.clip(colr, 0, 1)
    a_ *= (1 - inside)
    rgba = np.concatenate([colr, a_[..., None]], -1)[by_:by_ + 2 * box_r, bx_:bx_ + 2 * box_r]
    to_img(rgba).save(os.path.join(OUT, 'ledlight_' + nm + '.png'), optimize=True)
    sprites['ledlight_' + nm] = (bx_ / HIDPI, by_ / HIDPI, 2 * box_r / HIDPI, 2 * box_r / HIDPI)
    # ---- lens + bezel lit (drawn over the light layer)
    rr2 = np.clip(dd / lens_r, 0, 1)
    cw_ = np.clip(1 - rr2 ** 3.5, 0, 1)
    lens_lin = (core[None, None, :] * (cw_ * 1.25)[..., None] +
                col[None, None, :] * (0.65 + 0.9 * rr2 ** 2)[..., None])
    lens_lin *= (0.9 + 0.12 * ang_l * rr2)[..., None]
    edge = np.clip((rr2 - 0.82) / 0.18, 0, 1)
    lens_lin = lens_lin * (1 - 0.35 * edge[..., None])
    lens_s = lin2srgb(lens_lin)
    # bezel ring glows with the colour (light pipe)
    ring_glow = col[None, None, :] * (0.75 + 0.6 * np.clip(1 - (dd - lens_r) / (bez_r - lens_r), 0, 1))[..., None]
    ring_s = lin2srgb(srgb2lin(led_off_rgb) * 0.12 + ring_glow)
    optic = gblur(lens, 4 * HIDPI) * 0.5 + gblur(lens, 10 * HIDPI) * 0.25
    # light spilling in the counterbore around the bezel
    rec_ring = recess * np.clip(dd - bez_r + 0.5, 0, 1)
    fall = np.clip(1 - (dd - bez_r) / (rec_r - bez_r), 0, 1)
    rec_lin = srgb2lin(led_off_rgb) * (1 + fall[..., None] * col * 3.0) + col * (0.35 * fall ** 1.5)[..., None]
    rec_s = lin2srgb(rec_lin)
    lit = ring_s * ring[..., None] + lens_s * lens[..., None] + rec_s * rec_ring[..., None]
    a_l = np.clip(ring + lens + rec_ring, 0, 1)
    # optical halo around the lens (very light)
    halo_rgb = lin2srgb(col[None, None, :] * 0.9)
    a_h = np.clip(optic * 0.85 * (1 - a_l), 0, 1)
    out_rgb = (lit * a_l[..., None] + halo_rgb * a_h[..., None])
    out_a = np.clip(a_l + a_h, 0, 1)
    out_rgb = np.where(out_a[..., None] > 1e-4, out_rgb / np.maximum(out_a[..., None], 1e-4), 0)
    # fixed specular on the dome
    spec_ = hl * 0.18
    out_rgb = np.clip(out_rgb + spec_[..., None], 0, 1)
    r2 = int(40 * HIDPI)
    sx, sy = int(LC[0]) - r2, int(LC[1]) - r2
    rgba = np.concatenate([out_rgb, out_a[..., None]], -1)[sy:sy + 2 * r2, sx:sx + 2 * r2]
    to_img(rgba).save(os.path.join(OUT, 'led_' + nm + '.png'), optimize=True)
    sprites['led_' + nm] = (sx / HIDPI, sy / HIDPI, 2 * r2 / HIDPI, 2 * r2 / HIDPI)

# ===================================================== 8. pressed states
def crop_box(x0, y0, x1, y1):
    a0 = P2C(x0, y0); a1 = P2C(x1, y1)
    return int(a0[0]), int(a0[1]), int(np.ceil(a1[0])), int(np.ceil(a1[1]))


def save_pressed(name, box, mask_fn, push=1.2, dark=0.80):
    X0, Y0, X1, Y1 = box
    reg = FINAL[Y0:Y1, X0:X1].copy()
    h, w = reg.shape[:2]
    mk = mask_fn(h, w, X0, Y0)
    # the cap moves down/right a little and loses some light
    M = np.float32([[1, 0, push * HIDPI * 0.6], [0, 1, push * HIDPI]])
    moved = cv2.warpAffine(reg, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    capd = moved * dark
    # contact shadow reduced on bottom-right, gap appears top-left
    edge = np.clip(mk - cv2.erode(mk, np.ones((5, 5), np.uint8)), 0, 1)
    out = reg * (1 - mk[..., None]) + capd * mk[..., None]
    out = out * (1 - 0.25 * gblur(edge, 1.5)[..., None])
    a = np.clip(gblur(mk, 1.0) * 1.15, 0, 1)
    rgba = np.concatenate([out, a[..., None]], -1)
    to_img(rgba).save(os.path.join(OUT, 'press_' + name + '.png'), optimize=True)
    sprites['press_' + name] = (X0 / HIDPI, Y0 / HIDPI, w / HIDPI, h / HIDPI)


def circ_mask(cx, cy, r):
    def f(h, w, X0, Y0):
        c = P2C(cx, cy)
        return disc(h, w, c[0] - X0, c[1] - Y0, r * K + 1.5 * HIDPI, 1.2)
    return f


def tri_mask(pts, grow=3.0):
    def f(h, w, X0, Y0):
        cx = sum(p[0] for p in pts) / 3; cy = sum(p[1] for p in pts) / 3
        pp = [P2C(cx + (x - cx) * 1.12, cy + (y - cy) * 1.12) for x, y in pts]
        m_ = poly_mask(h, w, [(x - X0, y - Y0) for x, y in pp], 4)
        return gblur(cv2.dilate(m_, np.ones((3, 3), np.uint8)), 1.5)
    return f


mx, my, mr = MIX_BTN
save_pressed('mix', crop_box(mx - mr - 6, my - mr - 6, mx + mr + 6, my + mr + 6), circ_mask(mx, my, mr))
fx, fy, fr = FAV_BTN
save_pressed('fav', crop_box(fx - fr - 6, fy - fr - 6, fx + fr + 6, fy + fr + 6), circ_mask(fx, fy, fr))
save_pressed('left', crop_box(*ARROW_L_BOX), tri_mask(ARROW_L), push=1.0, dark=0.78)
save_pressed('right', crop_box(*ARROW_R_BOX), tri_mask(ARROW_R), push=1.0, dark=0.78)

# footswitch (Echoflex behaviour: knob pushed + dark disc on the button)
FX, FY = FOOT
X0, Y0, X1, Y1 = crop_box(FX - FOOT_CHROME_R - 4, FY - FOOT_CHROME_R - 4, FX + FOOT_CHROME_R + 4, FY + FOOT_CHROME_R + 4)
reg = FINAL[Y0:Y1, X0:X1].copy()
h, w = reg.shape[:2]
c = P2C(FX, FY)
cxl, cyl = c[0] - X0, c[1] - Y0
capm = disc(h, w, cxl, cyl, FOOT_CAP_R * K, 1.2)
# knob sinks: scale 0.97 about centre + 1 px down
M = cv2.getRotationMatrix2D((cxl, cyl), 0, 0.97)
M[1, 2] += 1.2 * HIDPI
sunk = cv2.warpAffine(reg, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
chm = disc(h, w, cxl, cyl, (FOOT_CHROME_R - 6) * K, 1.5)
out = reg * (1 - chm[..., None]) + sunk * chm[..., None]
dark = disc(h, w, cxl, cyl + 0.6 * HIDPI, FOOT_CAP_R * K * 1.02, 2.0)
out = out * (1 - 0.25 * dark[..., None])
rgba = np.concatenate([out, chm[..., None]], -1)
to_img(rgba).save(os.path.join(OUT, 'press_foot.png'), optimize=True)
sprites['press_foot'] = (X0 / HIDPI, Y0 / HIDPI, w / HIDPI, h / HIDPI)

# ===================================================== 9. hit areas + layout.h
hit = {}
hit['left'] = tuple(v for v in [*P2L(ARROW_L_BOX[0], ARROW_L_BOX[1]), *P2L(ARROW_L_BOX[2], ARROW_L_BOX[3])])
hit['right'] = tuple(v for v in [*P2L(ARROW_R_BOX[0], ARROW_R_BOX[1]), *P2L(ARROW_R_BOX[2], ARROW_R_BOX[3])])
hit['mix'] = (*P2L(mx, my), mr * K / HIDPI + 4)
hit['fav'] = (*P2L(fx, fy), fr * K / HIDPI + 4)
hit['foot'] = (*P2L(FX, FY), FOOT_CHROME_R * K / HIDPI)
hit['display'] = tuple([*P2L(GLASS[0], GLASS[1]), *P2L(GLASS[2], GLASS[3])])
hit['led'] = (*P2L(*LED_C), LED_LENS_R * K / HIDPI)
hit['pedal'] = (ox / HIDPI, oy / HIDPI, pw / HIDPI, ph / HIDPI)

with open(os.path.join(OUT, 'layout.json'), 'w') as f:
    json.dump({'sprites': sprites, 'hit': hit}, f, indent=1)

lines = ['// generated by tools/build_art.py - do not edit', '#pragma once',
         'namespace Layout {',
         'struct R { float x, y, w, h; };',
         'struct Sprite { const char* name; R r; };',
         'constexpr float W = %d.0f, H = %d.0f, topBar = %d.0f, bottomBar = %d.0f;' %
         (LOGICAL_W, LOGICAL_H, TOP_BAR, BOTTOM_BAR),
         'constexpr Sprite sprites[] = {']
for k, v in sprites.items():
    lines.append('    { "%s", { %.2ff, %.2ff, %.2ff, %.2ff } },' % (k, *v))
lines.append('};')
def rect_of(b):
    return (b[0], b[1], b[2] - b[0], b[3] - b[1])
lines.append('constexpr R hitLeft { %.2ff, %.2ff, %.2ff, %.2ff };' % rect_of(hit['left']))
lines.append('constexpr R hitRight { %.2ff, %.2ff, %.2ff, %.2ff };' % rect_of(hit['right']))
lines.append('constexpr R hitDisplay { %.2ff, %.2ff, %.2ff, %.2ff };' % rect_of(hit['display']))
for k in ('mix', 'fav', 'foot', 'led'):
    lines.append('constexpr float %sX = %.2ff, %sY = %.2ff, %sR = %.2ff;' % (k, hit[k][0], k, hit[k][1], k, hit[k][2]))
lines.append('constexpr R pedal { %.2ff, %.2ff, %.2ff, %.2ff };' % hit['pedal'])
lines.append('}')
with open(os.path.join(ROOT, 'Layout.h'), 'w') as f:
    f.write('\n'.join(lines) + '\n')
print('done:', len(sprites), 'sprites')
