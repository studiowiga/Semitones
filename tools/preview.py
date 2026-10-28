#!/usr/bin/env python3
"""Composite a static preview of the editor art (what paint() draws).
usage: preview.py out.png [value] [led colour|off] [mix] [fav] [pressed...]"""
import json, os, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, 'assets')
L = json.load(open(os.path.join(A, 'layout.json')))
S = L['sprites']

DIG = {'0': 'abcdef', '1': 'bc', '2': 'abdeg', '3': 'abcdg', '4': 'bcfg', '5': 'acdfg',
       '6': 'acdefg', '7': 'abc', '8': 'abcdefg', '9': 'abcdfg', ' ': ''}


def segs_for(v):
    out = []
    if isinstance(v, str) and v.endswith('%'):
        n = int(v[:-1])
        s = '%3d' % n
        if s[0] == '1':
            out += ['s_u', 's_d']
        t, u = s[1], s[2]
    else:
        n = int(v)
        if n > 0:
            out += ['s_l', 's_r', 's_u', 's_d']
        elif n < 0:
            out += ['s_l', 's_r']
        a = abs(n)
        t = str(a // 10) if a >= 10 else ' '
        u = str(a % 10)
    out += ['t_' + c for c in DIG[t]] + ['u_' + c for c in DIG[u]]
    return out


def paste(bg, name):
    x, y, w, h = S[name]
    im = Image.open(os.path.join(A, name + '.png')).convert('RGBA')
    bg.alpha_composite(im, (int(round(x * 2)), int(round(y * 2))))


def main():
    out = sys.argv[1]
    val = sys.argv[2] if len(sys.argv) > 2 else '+4'
    led = sys.argv[3] if len(sys.argv) > 3 else 'red'
    rest = sys.argv[4:]
    bg = Image.open(os.path.join(A, 'background.jpg')).convert('RGBA')
    if led != 'off':
        paste(bg, 'ringlight')
        paste(bg, 'ring_lit')
    for s in segs_for(val):
        paste(bg, 'seg_' + s)
    if 'mix' in rest:
        paste(bg, 'dot_mix')
    if 'fav' in rest:
        paste(bg, 'dot_fav')
    for p in ('left', 'right', 'mix', 'fav', 'foot'):
        if 'p_' + p in rest:
            paste(bg, 'press_' + p)
    bg.convert('RGB').save(out)


main()
