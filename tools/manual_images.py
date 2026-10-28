#!/usr/bin/env python3
"""Illustrations of the manual from the real editor renders (tools/render output dir)."""
import json, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = sys.argv[1]
M = os.path.join(ROOT, 'design', 'manual')
os.makedirs(M, exist_ok=True)
L = json.load(open(os.path.join(ROOT, 'assets', 'layout.json')))
H_ = L['hit']
px, py, pw, ph = H_['pedal']

# ---------------------------------------------------------------- cover
ui = Image.open(os.path.join(SHOTS, 'ui_plus4.png')).convert('RGBA')
box = (int(px * 2) - 40, int(py * 2), int((px + pw) * 2) + 40, int((py + ph) * 2) + 2)
ped = ui.crop(box)
a = np.asarray(ped.convert('L')).astype(np.uint8)
dark = (a < 38).astype(np.uint8)
mask = np.zeros((dark.shape[0] + 2, dark.shape[1] + 2), np.uint8)
for seed in [(0, 0), (dark.shape[1] - 1, 0), (0, dark.shape[0] - 1), (dark.shape[1] - 1, dark.shape[0] - 1)]:
    cv2.floodFill(dark.copy() * 255, mask, seed, 128)
alpha = 1 - mask[1:-1, 1:-1]
alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
alpha = cv2.GaussianBlur(alpha.astype(np.float32), (0, 0), 0.8)
ped.putalpha(Image.fromarray((alpha * 255).astype(np.uint8)))
W, H = ped.width + 300, int(ped.height * 1.42)
cov = Image.new('RGBA', (W, H), (0, 0, 0, 255))
halo = Image.new('L', (W, H), 0)
ImageDraw.Draw(halo).ellipse([W * 0.12, H * 0.05, W * 0.88, H * 0.72], fill=55)
halo = halo.filter(ImageFilter.GaussianBlur(120))
cov.alpha_composite(Image.merge('RGBA', [Image.new('L', (W, H), 57), Image.new('L', (W, H), 160), Image.new('L', (W, H), 255), halo]))
ox, oy = (W - ped.width) // 2, 40
cov.alpha_composite(ped, (ox, oy))
refl = ped.transpose(Image.FLIP_TOP_BOTTOM).crop((0, 0, ped.width, int(ped.height * 0.35)))
g = np.linspace(0.28, 0, refl.height)[:, None]
refl.putalpha(Image.fromarray((np.asarray(refl)[..., 3] * g).astype(np.uint8)))
cov.alpha_composite(refl, (ox, oy + ped.height + 6))
cov.convert('RGB').save(os.path.join(M, 'cover_pedal.jpg'), quality=92)

# ---------------------------------------------------------------- annotated overview
im = Image.open(os.path.join(SHOTS, 'ui_minus12_mix.png')).convert('RGB')
d = ImageDraw.Draw(im)
f = ImageFont.truetype(os.path.join(ROOT, 'assets', 'Poppins-Bold.ttf'), 34)


def tag(n, x, y):
    r = 26
    d.ellipse([x - r, y - r, x + r, y + r], fill=(57, 160, 255), outline=(255, 255, 255), width=3)
    tb = d.textbbox((0, 0), str(n), font=f)
    d.text((x - (tb[2] - tb[0]) / 2 - tb[0], y - (tb[3] - tb[1]) / 2 - tb[1]), str(n), font=f, fill=(255, 255, 255))


s = 2
hd = H_['display']; tag(1, hd[2] * s + 4, hd[1] * s + 24)
hl = H_['left']; tag(2, hl[0] * s - 34, (hl[1] + hl[3]) / 2 * s)
hr = H_['right']; tag(3, hr[2] * s + 34, (hr[1] + hr[3]) / 2 * s)
tag(4, H_['mix'][0] * s - 80, H_['mix'][1] * s + 26)
tag(5, H_['fav'][0] * s + 80, H_['fav'][1] * s + 26)
fx, fy, fr = H_['foot']
tag(6, fx * s + 150, fy * s - 120)       # light ring
tag(7, fx * s, fy * s)                   # footswitch
tag(8, 575 * s, 20 * s)
tag(9, 120 * s, 939 * s)
tag(10, (px + pw) * s + 40, (py + 436) * s)
tag(11, px * s - 40, (py + 436) * s)
im.save(os.path.join(M, 'overview.jpg'), quality=90)
print('ok')
