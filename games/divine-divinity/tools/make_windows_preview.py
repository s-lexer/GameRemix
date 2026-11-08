#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mock-up pictures for the "Large windows" step of the quick-setup wizard, composed from the REAL sprites of archive 8 (not game screenshots):
  gfx/previews/winkit_orig.jpg  - what the windows look like now: character-stats window (8/186) and backpack (8/4) both open at (100,100), on top of each other
  gfx/previews/winkit_big.jpg   - the kit: stats window left (16,16), backpack right (W-422-16,16) with the centred pair [Close | Sort] (8/197, 8/663), logical screen 800x520
Both are 800x520 (the logical screen; resources gfxprev_winkit_orig / _big). Skin C (Original HD) archive 8 from scratch/ui_skins/C, the kit from scratch/sr_lab/set_win_c (tools/make_windows_sets.py).
usage: python games/divine-divinity/tools/make_windows_preview.py"""
import os, sys, io
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(R, 'games', 'divine-divinity', 'gfx_pilot', 'tools'))
import numpy as np, cpacked as C
from PIL import Image
OUT = os.path.join(R, 'games', 'divine-divinity', 'gfx', 'previews'); W, H = 800, 520
def sprites(d):
    ents = C.read_index(os.path.join(d, 'CPackedi.8c')); blob = open(os.path.join(d, 'CPackedb.8c'), 'rb').read(); return lambda i: Image.fromarray(C.decode(blob, ents, i)).convert('RGBA')
def canvas():
    im = Image.new('RGBA', (W, H), (38, 33, 27, 255)); px = im.load()
    for y in range(H):
        for x in range(0, W, 1):
            if (x // 40 + y // 40) % 2 == 0: px[x, y] = (41, 36, 30, 255)
    return im
def paste(im, spr, x, y): im.alpha_composite(spr, (x, y))
def save(im, name):
    im = im.convert('RGB')
    for q in range(90, 40, -4):
        b = io.BytesIO(); im.save(b, 'JPEG', quality=q, optimize=True)
        if len(b.getvalue()) < 90 * 1024: break
    open(os.path.join(OUT, name), 'wb').write(b.getvalue()); print(name, q, len(b.getvalue()) // 1024, 'KB')
o = sprites(os.path.join(R, 'scratch', 'ui_skins', 'C', 'static', 'imagelists')); b = sprites(os.path.join(R, 'scratch', 'sr_lab', 'set_win_c', 'static', 'imagelists'))
im = canvas(); paste(im, o(186), 100, 100); paste(im, o(4), 100, 100); save(im, 'winkit_orig.jpg')
im = canvas(); paste(im, b(186), 16, 16); bx = W - 422 - 16; paste(im, b(4), bx, 16)
paste(im, b(197), bx + 145, 16 + 435); paste(im, b(663), bx + 216, 16 + 435); save(im, 'winkit_big.jpg')
