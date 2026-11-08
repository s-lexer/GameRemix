"""Trade window v2 data: TWO BAGS + deal zone. Base: scratch/sr_lab/set_bigbag2 (big backpack) + bak_E; output: set_trade2 (tabs) or set_trade2_notabs.
Columns [bag WB | offer WO | offer WO | bag WB], bag boxes lowered by TAB px (tab buttons row = same 5 category tabs as in the backpack, sprites 8/7..21, tooltips 299..303),
window bg 8/5 recomposed (per row-band horizontal cuts, widened column sprites 8/88..91 pasted), tradepl.bmg: new block 'Tradeplate Bag Box', tab controls 'TabL'/'TabR', shifted buttons.
usage: python make_trade2.py [out=set_trade2] [TAB=40] [WB=334] [WO=154] [DYT=270] [base=e|c|orig]  (needs scratch/sr_lab/set_bigbag_<base> from make_bag_sets.py)   (TAB=0 -> no tabs)"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'gfx_pilot', 'tools'))
import numpy as np, cpacked as C, cmpfile
from make_big_inventory import pack_resized
import sortbtn
sys.path.insert(0, os.path.join(HERE, '..'))
R = r'D:\ARM\OldGameFixer\scratch\sr_lab'
OUT = R + '\\' + (sys.argv[1] if len(sys.argv) > 1 else 'set_trade2'); TAB = int(sys.argv[2]) if len(sys.argv) > 2 else 40
WB = int(sys.argv[3]) if len(sys.argv) > 3 else 334; WO = int(sys.argv[4]) if len(sys.argv) > 4 else 154; DYT = int(sys.argv[5]) if len(sys.argv) > 5 else 270
BASE_ID = (sys.argv[6] if len(sys.argv) > 6 else 'e').lower()     # skin the window is built on: orig | c | e
BASES = {'orig': r'D:\ARM\OldGameFixer\scratch\gfx_sets\orig', 'c': r'D:\ARM\OldGameFixer\scratch\ui_skins\C\static\imagelists', 'e': r'D:\ARM\OldGameFixer\scratch\ui_skins\E\static\imagelists', 'a': r'D:\ARM\OldGameFixer\scratch\ui_skins\A\static\imagelists', 'b': r'D:\ARM\OldGameFixer\scratch\ui_skins\B\static\imagelists', 'd': r'D:\ARM\OldGameFixer\scratch\ui_skins\D\static\imagelists', 'orig-v2': r'D:\ARM\OldGameFixer\scratch\gfx_sets\v2_1'}
DPS = [WB - 104, WO - 104, WO - 104, WB - 104]

import cv2
def _edge(a, px):
    m = (a > 0).astype(np.uint8)
    n, lab = cv2.connectedComponents(1 - m, connectivity=4)      # fill 1-3 px alpha holes (herb tab 8/16 has three): otherwise every hole grew into a bright 7x7 "square" in the pressed look (07.11, owner screens 48/52)
    for i in range(1, n):
        if not (lab == i)[0, :].any() and not (lab == i)[-1, :].any() and not (lab == i)[:, 0].any() and not (lab == i)[:, -1].any(): m[lab == i] = 1
    er = cv2.erode(m, np.ones((2 * px + 1, 2 * px + 1), np.uint8)); return (m > 0) & (er == 0)
def look_pressed(im):
    """selected tab: darkened, pressed-in look + bright 2 px gold frame"""
    o = im.copy(); rgb = o[..., :3].astype(np.float32) * 0.38; e = _edge(o[..., 3], 3); rgb[e] = (60, 200, 255)   # BGR-ish order is irrelevant: gold-ish in RGBA decode order (R,G,B)=(255,200,60)
    rgb[e] = (255, 228, 80); o[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8); return o
def look_highlight(im):
    o = im.copy(); rgb = np.clip(o[..., :3].astype(np.float32) * 1.25 + 12, 0, 255); e = _edge(o[..., 3], 1); rgb[e] = (255, 235, 150); o[..., :3] = rgb.astype(np.uint8); return o

def tile(a, n, axis):
    reps = -(-n // a.shape[axis]); return np.concatenate([a] * reps, axis).take(range(n), axis)
def vband(im, y0, y1, yi, n): return np.concatenate([im[:yi], tile(im[y0:y1], n, 0), im[yi:]], 0)
def hcut(im, cuts):
    out = []; prev = 0
    for c in sorted(cuts):
        x, n = c[0], c[1]; sx = c[2] if len(c) > 2 else x - 15
        if n <= 0: continue
        out.append(im[:, prev:x]); out.append(tile(im[:, sx:sx + 30], n, 1)); prev = x
    out.append(im[:, prev:]); return np.concatenate(out, 1)

def trade_bg(orig, sprites):
    d0, d1, d2, d3 = DPS; V = vband(orig, 150, 250, 250, DYT); H = V.shape[0]
    Ah = [(118, d0 + d1 // 2, 95), (232, d1 // 2 + d2 // 2, 95), (345, d2 // 2 + d3, 95)]
    Af = [(125, d0 + d1 // 2, 200), (232, d1 // 2 + d2 // 2, 200), (328, d2 // 2 + d3, 200)]
    Bc = [(118, d0, 150), (170, d1, 150), (282, d2, 260), (335, d3, 260)]
    Cc = [(60, d0), (170, d1), (282, d2), (390, d3)]
    N = np.concatenate([hcut(V[a:b], c) for a, b, c in ((0, 49, Ah), (49, 76, Bc), (76, 322 + DYT, Cc), (322 + DYT, H, Af))], 0)
    xs = [13]
    for k in range(3): xs.append(xs[-1] + 104 + DPS[k] + 4)
    ys = (105 + TAB, 76, 76, 105 + TAB)
    for k in (0, 3):                                   # plain filler above the lowered bag boxes
        if TAB: N[105:105 + TAB, xs[k]:xs[k] + 104 + DPS[k]] = N[200:200 + TAB, xs[k]:xs[k] + 104 + DPS[k]]
    Nb = N.copy()
    for k, spr in enumerate(sprites): N[ys[k]:ys[k] + spr.shape[0], xs[k]:xs[k] + spr.shape[1]] = spr
    h2, w2 = N.shape[:2]                                  # the outer boxes overlap the bottom corner ornaments of the frame: put the ornaments back
    N[h2 - 48:, :46] = Nb[h2 - 48:, :46]; N[h2 - 48:, w2 - 46:] = Nb[h2 - 48:, w2 - 46:]
    return N

def tab_block(side, x):
    """Plain buttons (an empty 'tab' page is a BMGui syntax error). Per tab TWO buttons at the same place:
    S (below): always enabled, always draws the PRESSED picture, callback toggles;  U (above): name tab<side><k>, normal look, disabledlook = pressed picture.
    The callback (40..44 L / 50..54 R, trade_patch*.py) selects k (or clears the filter if k is already active) and DISABLES U_k of the active tab (shows pressed) and enables the rest.
    If the engine lets clicks pass through a disabled U, the click lands on S -> filter off; otherwise (worst case) behaviour = v8."""
    out = []
    for i in range(5):
        cb = (40 if side == 'L' else 50) + i; n, p, h = 7 + 3 * i, 8 + 3 * i, 9 + 3 * i
        out.append(f'''  begin button
    normal image list 8 index {p}
    pressed image list 8 index {p}
    highlight image list 8 index {p}
    mouseclick callback id {cb}
    tooltip {299 + i}
    clicksound (2, 6, 0, {1 + i})
  end button
  position ({x + 62 * i}, 105)

  begin button
    name "tab{side}{i}"
    normal image list 8 index {n}
    pressed image list 8 index {p}
    highlight image list 8 index {h}
    disabledlook image list 8 index {p}
    mouseclick callback id {cb}
    tooltip {299 + i}
    clicksound (2, 6, 0, {1 + i})
  end button
  position ({x + 62 * i}, 105)
''')
    return '\n'.join(out)

def edit_trade(t, geo):
    d0, d1, d2, d3 = DPS; tot = sum(DPS); s1 = d0 + d1 // 2; s2 = d0 + d1 + d2 // 2
    a = t.index('name "Tradeplate Trade Interface"'); head, rest = t[:a], t[a:]
    for old, new in (('position (135, 324)', 'position (%d, %d)' % (135 + s1, 324 + DYT)), ('position (257, 324)', 'position (%d, %d)' % (257 + s2, 324 + DYT)), ('position (375, 15)', 'position (%d, 15)' % (375 + tot))):
        assert old in head; head = head.replace(old, new)
    if TAB:
        i = head.rindex('end form'); head = head[:i] + tab_block('L', 13 + (WB - 306) // 2) + tab_block('R', geo[3] + (WB - 306) // 2) + head[i:]
    for old, new in (('position (141, 15)', 'position (%d, 15)' % (141 + s1)), ('position (250, 15)', 'position (%d, 15)' % (250 + s2)), ('position (337, 49)', 'position (%d, 49)' % (337 + tot))):
        assert old in head + rest; head = head.replace(old, new); rest = rest.replace(old, new)
    i = rest.index('name "Tradeplate Box"'); j = rest.index('name "Identify Overlay"'); box = rest[i:j]
    def dims(b, dp, hh):
        for o, n in (('content area (8, 8) - (78, 230)', 'content area (8, 8) - (%d, %d)' % (78 + dp, 230 + hh)), ('content area (2, 2) - (103, 242)', 'content area (2, 2) - (%d, %d)' % (103 + dp, 242 + hh))):
            assert o in b; b = b.replace(o, n)
        return b
    bag = dims(box, d0, DYT - TAB).replace('name "Tradeplate Box"', 'name "Tradeplate Bag Box"'); off = dims(box, d1, DYT)
    return head + rest[:i] + off + bag + rest[j:]

def overlay(bg, xs):
    """control-position overlay for checking seams: boxes (green), content areas (cyan), scroll arrows 19x26 (red), buttons (yellow), portrait slots / trader plates (magenta), tabs (white)"""
    im = cv2.cvtColor(bg, cv2.COLOR_RGBA2BGR).copy(); tot = sum(DPS); s1 = DPS[0] + DPS[1] // 2; s2 = DPS[0] + DPS[1] + DPS[2] // 2
    rc = lambda x0, y0, x1, y1, col: cv2.rectangle(im, (int(x0), int(y0)), (int(x1) - 1, int(y1) - 1), col, 1)
    ys = (105 + TAB, 76, 76, 105 + TAB)
    for k in range(4):
        bag = k in (0, 3); hh = (DYT - TAB) if bag else DYT; wd = 104 + DPS[k]
        rc(xs[k], ys[k], xs[k] + wd, ys[k] + 244 + hh, (0, 200, 0))
        cx0, cy0, cx1, cy1 = xs[k] + 2, ys[k] + 2, xs[k] + 103 + DPS[k], ys[k] + 242 + hh
        rc(cx0, cy0, cx1, cy1, (255, 255, 0))
        rc(cx1 - 19, cy0, cx1, cy0 + 26, (0, 0, 255)); rc(cx1 - 19, cy1 - 26, cx1, cy1, (0, 0, 255))
    for x, y, w, h in ((135 + s1, 324 + DYT, 61, 30), (257 + s2, 324 + DYT, 61, 30), (141 + s1, 15, 61, 30), (250 + s2, 15, 61, 30), (87, 49, 30, 23), (337 + tot, 49, 30, 23)): rc(x, y, x + w, y + h, (0, 255, 255))
    rc(20, 15, 80, 75, (255, 0, 255)); rc(375 + tot, 15, 435 + tot, 75, (255, 0, 255))
    if TAB:
        for x0 in (13 + (WB - 306) // 2, xs[3] + (WB - 306) // 2):
            for i in range(5): rc(x0 + 62 * i, 105, x0 + 62 * i + 58, 141, (255, 255, 255))
    return im

def main():
    il = OUT + r'\static\imagelists'; os.makedirs(il, exist_ok=True); os.makedirs(OUT + r'\dat', exist_ok=True)
    O = BASES[BASE_ID]; ents = C.read_index(O + r'\CPackedi.8c'); blob = open(O + r'\CPackedb.8c', 'rb').read()
    bb = R + r'\set_bigbag_' + BASE_ID + r'\static\imagelists'; e2 = C.read_index(bb + r'\CPackedi.8c'); b2 = open(bb + r'\CPackedb.8c', 'rb').read()
    rep = {4: C.decode(b2, e2, 4)}
    sp = {}
    for k, i in enumerate((88, 89, 90, 91)):
        bag = k in (0, 3); im = vband(C.decode(blob, ents, i), 100, 160, 160, DYT - (TAB if bag else 0))
        sp[k] = rep[i] = hcut(im, [(40, DPS[k])])
    for k in range(5):                                   # tabs: contrasting pressed / highlight looks (shared with the backpack tabs)
        base = C.decode(blob, ents, 7 + 3 * k); rep[8 + 3 * k] = look_pressed(base); rep[9 + 3 * k] = look_highlight(base)
    for k, sp_ in enumerate(sortbtn.make([C.decode(blob, ents, i) for i in (197, 198, 199)])): rep[len(ents) + k] = sp_
    rep[5] = trade_bg(C.decode(blob, ents, 5), [sp[k] for k in range(4)])
    pack_resized(ents, blob, rep, il + r'\CPackedi.8c', il + r'\CPackedb.8c')
    es = cmpfile.read(R + r'\set_bigbag_' + BASE_ID + r'\dat\flat.cmp'); pr = cmpfile.read(R + r'\flat_before_bigbag.cmp')
    t0 = cmpfile.find(pr, 'bmg\\Tradepl.bmg').data.decode('latin-1')
    xs = [13]
    for k in range(3): xs.append(xs[-1] + 104 + DPS[k] + 4)
    cmpfile.find(es, 'bmg\\Tradepl.bmg').data = edit_trade(t0, xs).encode('latin-1')
    cmpfile.write(OUT + r'\dat\flat.cmp', es)
    cv2.imwrite(OUT + r'\trade_bg_preview.png', cv2.cvtColor(rep[5], cv2.COLOR_RGBA2BGRA)); cv2.imwrite(OUT + r'\trade_bg_overlay.png', overlay(rep[5], xs))
    import make_sort_tooltip as mst                       # texts of the Sort button tooltip (tooltip 772): ready text.cmp per language, NOT part of include= (the language folder differs per install; installed by tools/make_sort_tooltip.py / the test bat)
    for lang, src, dst in (('ru', r'X:\GAMES\Divine Divinity\localizations\german\text.cmp', OUT + r'\localizations_ru\german\text.cmp'),
                           ('en', r'C:\Program Files (x86)\Steam\steamapps\common\divine_divinity\localizations\english\text.cmp', OUT + r'\localizations_en\english\text.cmp')):
        if os.path.exists(src): os.makedirs(os.path.dirname(dst), exist_ok=True); mst.make(src, dst, lang)
    print('ok', rep[5].shape[1], 'x', rep[5].shape[0], 'xs', xs)
main()
