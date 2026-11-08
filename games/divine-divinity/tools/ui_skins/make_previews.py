"""Previews 'as it will look in the game': real sprites decoded from the BUILT skin archives (not drawings) composited 1:1 onto a game scene.
usage: python make_previews.py [ids...]   (default: orig A B C D)   output: games/divine-divinity/ui_skins/previews/"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'gfx_pilot', 'tools')); sys.path.insert(0, os.path.join(HERE, '..', '..', 'ui_mockups', 'src'))
import numpy as np, cpacked as C
from PIL import Image, ImageDraw, ImageFont
R = r'D:\ARM\OldGameFixer'; OUT = os.path.join(HERE, '..', '..', 'ui_skins', 'previews'); os.makedirs(OUT, exist_ok=True)
ICONS = R + r'\scratch\gfx_sets\v2full'
ITEMS = [183, 196, 178, 214, 205, 213, 262, 180, 56, 57, 58, 59, 86, 87, 88, 89, 0, 3, 8, 41, 43, 10, 9, 2]
HOTBAR = [56, 59, 183, 214, 0, 51]
from common import scene_native
SCENE = scene_native().resize((1920, 1080), Image.LANCZOS).convert('RGBA')


class Set:
    def __init__(s, sid):
        s.sid = sid; s.cache = {}
        s.dirs = {'orig': [R + r'\scratch\gfx_sets\orig'], 'orig_v2': [R + r'\scratch\gfx_sets\v2full']}.get(sid, [R + r'\scratch\ui_skins\%s\static\imagelists' % sid, ICONS])

    def arch(s, n):
        if n not in s.cache:
            for d in s.dirs:
                p = os.path.join(d, 'CPackedi.%dc' % n)
                if os.path.exists(p):
                    s.cache[n] = (C.read_index(p), open(os.path.join(d, 'CPackedb.%dc' % n), 'rb').read()); break
        return s.cache[n]

    def spr(s, n, i):
        ix, bl = s.arch(n); return Image.fromarray(C.decode(bl, ix, i))


def put(img, spr, xy): img.alpha_composite(spr, xy)


def scene_for(S, big=False):
    im = SCENE.copy()
    hb = S.spr(8, 121); put(im, hb, ((1920 - hb.width) // 2, 1080 - hb.height))
    for k, ic in enumerate(HOTBAR):
        pass
    inv = S.spr(8, 4); ix, iy = 1920 - inv.width - 30, 250; put(im, inv, (ix, iy))
    for k, ic in enumerate(ITEMS):
        sp = Image.open(R + r'\scratch\gfx_full_v2\stage\3\%d.png' % ic).convert('RGBA'); put(im, sp, (ix + 14 + (k % 6) * 50 + 1, iy + 55 + (k // 6) * 50 + 1))
    eq = S.spr(8, 2); put(im, eq, (ix - eq.width - 20, iy - 57))
    inv2 = S.spr(8, 101); put(im, inv2, (ix - eq.width - inv2.width - 40, iy + 40))
    return im


def sheet(S):
    ids = [(8, 5), (8, 189), (8, 106), (8, 1)]
    W = 1500; sh = Image.new('RGBA', (W, 900), (54, 54, 60, 255)); x = y = 0; rh = 0
    seq = [(8, 5), (8, 189), (8, 1), (8, 106), (8, 3), (8, 450)] + [(8, i) for i in (55, 61, 64, 85, 86, 197, 198, 199, 209, 213, 7, 8, 9, 10, 217, 300, 303, 43, 46)] + [(8, 137), (8, 138), (8, 187), (8, 190), (8, 191), (8, 192), (8, 193)]
    for n, i in seq:
        sp = S.spr(n, i)
        if x + sp.width > W: x = 0; y += rh + 6; rh = 0
        sh.alpha_composite(sp, (x, y)); x += sp.width + 6; rh = max(rh, sp.height)
    return sh.crop((0, 0, W, y + rh + 6))


ids = sys.argv[1:] or ['orig', 'A', 'B', 'C', 'D']
fnt = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 28)
crops = {}
for sid in ids:
    S = Set(sid); im = scene_for(S)
    im.convert('RGB').save(os.path.join(OUT, '%s_inventory.png' % sid))
    sheet(S).convert('RGB').save(os.path.join(OUT, '%s_sheet.png' % sid))
    crops[sid] = im.crop((1920 - 1180, 150, 1920, 700)).convert('RGB')
    hb = im.crop((480, 940, 1440, 1080)).convert('RGB'); crops[sid + '_hb'] = hb
    print(sid, 'ok')
if len(ids) > 1:
    names = {'orig': 'Оригинал', 'A': 'A Пергамент', 'B': 'B Тёмный металл', 'C': 'C Оригинал HD', 'D': 'D Тёмное стекло'}
    cw, ch = 1180, 550 + 140 + 44
    W = 2 * cw + 10; H = ((len(ids) + 1) // 2) * (ch + 10)
    cmp_ = Image.new('RGB', (W, H), (20, 20, 20)); d = ImageDraw.Draw(cmp_)
    for k, sid in enumerate(ids):
        x = (k % 2) * (cw + 10); y = (k // 2) * (ch + 10)
        cmp_.paste(crops[sid], (x, y + 44)); cmp_.paste(crops[sid + '_hb'], (x + 100, y + 44 + 550))
        d.text((x + 10, y + 6), names.get(sid, sid), font=fnt, fill=(240, 220, 160))
    cmp_.save(os.path.join(OUT, 'compare_skins.png'))
