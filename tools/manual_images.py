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
px, py, pw, ph = 118.0, 8.0, 545.0, 935.0   # pedal body in design units (design v3, enlarged)

# ---------------------------------------------------------------- cover
ui = Image.open(os.path.join(SHOTS, 'ui_plus4.png')).convert('RGB')
# design v3: the pedal sits on concrete; crop away the preset / status strips and
# fade the edges to black so it merges with the black cover page
crop = ui.crop((int(px * 2) - 120, int(py * 2) - 30, int((px + pw) * 2) + 120, int((py + ph) * 2) + 30))
a = np.asarray(crop).astype(np.float32) / 255.0
hh, ww = a.shape[:2]
yv, xv = np.mgrid[0:hh, 0:ww].astype(np.float32)
fx_ = np.clip(np.minimum(xv, ww - 1 - xv) / 110.0, 0, 1)
fy_ = np.clip(np.minimum(yv, hh - 1 - yv) / 110.0, 0, 1)
fade = (fx_ * fy_) ** 1.3
cov = Image.fromarray((a * fade[..., None] * 255).astype(np.uint8))
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
tag(8, (L['hit']['display'][2] + 6) * s, 76 * s)
tag(9, 190 * s, 942 * s)
tag(10, (px + pw) * s + 40, (py + 475) * s)
tag(11, px * s - 40, (py + 475) * s)
im.save(os.path.join(M, 'overview.jpg'), quality=90)
print('ok')
