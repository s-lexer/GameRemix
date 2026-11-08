"""EXPERIMENT: bigger player backpack window (NPC Inventory Plate 332x310 -> (332+DX)x(310+DY)).
Makes an overlay set (game-relative layout): static/imagelists/CPackedi/b.8c (sprite 8/4 background enlarged by tiling plain bands, corners/borders kept),
dat/flat.cmp (inventpl.bmg: close button, items content area, scroll content area). The window size itself is hardcoded in div.exe (0x522ce5/0x522cec) - patched by
games/divine-divinity/patch_research/inv_patch.py --big DX DY.
usage: python make_big_bag.py [DX=90] [DY=170] [src_8c_dir=scratch/sr_lab/bak_E] [out=scratch/sr_lab/set_bigbag2] [DYT=120]
v2 (set_bigbag2): tabs re-spread over the new width (pitch=xspacing+interx), trade window taller by DYT (bg 8/5, column sprites 8/88..91, tradepl.bmg)   (DX, DY: multiples of 10 - dot pattern period)"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'gfx_pilot', 'tools'))
import numpy as np, cpacked as C, cmpfile
from make_big_inventory import pack_resized
import sortbtn
R = r'D:\ARM\OldGameFixer'
DX = int(sys.argv[1]) if len(sys.argv) > 1 else 90; DY = int(sys.argv[2]) if len(sys.argv) > 2 else 170
SRC = sys.argv[3] if len(sys.argv) > 3 else R + r'\scratch\sr_lab\bak_E'; OUT = sys.argv[4] if len(sys.argv) > 4 else R + r'\scratch\sr_lab\set_bigbag2'
DYT = int(sys.argv[5]) if len(sys.argv) > 5 else 120
DP = int(sys.argv[6]) if len(sys.argv) > 6 else 0       # trade window: extra width per column (4*DP total); needs trade_patch.py --dp DP; DP>0 -> grid-ready wide boxes   # trade window (CTradePlate, sprite 8/5 454x362): extra height only (box/button x positions are code constants)
FLAT = os.environ.get('GR_FLAT0') or R + r'\scratch\sr_lab\flat_before_bigbag.cmp'   # pristine copy of the game's dat\flat.cmp
W0, H0 = 332, 310; BTN_X, BTN_W = 135, 61          # baked close button (same place as the real sprite 8/197)
BTN_GAP = 10                                        # gap between 'Close' and 'Sort' (owner 07.11: the pair is centred in the window, symmetric)
HX0, HX1, HXI = 200, 290, 290                       # horizontal band tiled, inserted at x=HXI (before the scroll track)
VY0, VY1, VYI = 140, 220, 220                       # vertical band, inserted at y=VYI (before the down arrow)

def tile(a, n, axis):
    reps = -(-n // a.shape[axis]); t = np.concatenate([a] * reps, axis)
    return t.take(range(n), axis)

TAB_Y0, TAB_Y1, TAB_X0, TAB_X1 = 12, 50, 14, 320   # baked tab plates of the original background (5 x 58 px, pitch 62); the real tab buttons are drawn over them
SEAM_M = 16                                         # crossfade width of the repeated band (hides the seam of the plain panel texture)

def clean_tabs(im):
    """skins bake the 5 tab plates into 8/4; with tabs re-spread (and the band tiled) they would show twice -> repaint the strip with a plain rail"""
    im = im.copy(); gx = [13 + 58 + 62 * k + o for k in range(4) for o in range(1, 3)]
    gm = np.mean([im[16:46, x, :3].astype(np.float32).mean(0) for x in gx], 0)                   # colour of the gaps between the plates
    src = im[100:142, 24:276, :3].astype(np.float32); src = np.concatenate([src, src[:, ::-1]], 1)  # plain panel texture, mirrored to cover the strip
    w = TAB_X1 - TAB_X0; fill = np.clip(src[:, :w] - src.mean((0, 1)) + gm, 0, 255)
    reg = im[TAB_Y0:TAB_Y1, TAB_X0:TAB_X1, :3].astype(np.float32); a = np.ones((TAB_Y1 - TAB_Y0, w, 1), np.float32)
    for k in range(3): a[k, :] = a[-1 - k, :] = (k + 1) / 4; a[:, k] = np.minimum(a[:, k], (k + 1) / 4); a[:, -1 - k] = np.minimum(a[:, -1 - k], (k + 1) / 4)   # feathered edge
    im[TAB_Y0:TAB_Y1, TAB_X0:TAB_X1, :3] = (reg * (1 - a) + fill[:TAB_Y1 - TAB_Y0] * a).astype(np.uint8)
    return im

def quilt(band, n, axis, m=SEAM_M):
    """band repeated to length n; copies overlap by m and are crossfaded (no hard seam)"""
    b = np.moveaxis(band, axis, 1).astype(np.float32); P = b.shape[1]; out = b.copy(); t = ((np.arange(m) + 1) / (m + 1))[None, :, None]
    while out.shape[1] < n:
        out = np.concatenate([out[:, :-m], out[:, -m:] * (1 - t) + b[:, :m] * t, b[:, m:]], 1)
    return np.moveaxis(out[:, :n], 1, axis)

def extend(im, a, b, xi, n, axis, lo, hi, m=SEAM_M):
    """insert n columns (axis 1) / rows (axis 0) at xi: plain tile of band [a,b) on rows/cols outside [lo,hi) (frames: keeps the dot pattern), crossfaded quilt inside (plain panel texture)"""
    A = np.moveaxis(im, axis, 1); T = np.moveaxis(tile(im.take(range(a, b), axis), n, axis), axis, 1)
    plain = np.concatenate([A[:, :xi], T, A[:, xi:]], 1)
    F = np.moveaxis(quilt(im.take(range(a, b), axis), n + 2 * m, axis), axis, 1)
    t = ((np.arange(m) + 1) / (m + 1))[None, :, None]; Af = A.astype(np.float32)
    mid = np.concatenate([Af[:, :xi - m], Af[:, xi - m:xi] * (1 - t) + F[:, :m] * t, F[:, m:m + n], F[:, m + n:] * (1 - t) + Af[:, xi:xi + m] * t, Af[:, xi + m:]], 1)
    plain[lo:hi] = np.clip(mid[lo:hi], 0, 255).astype(np.uint8)
    return np.moveaxis(plain, 1, axis)

def build_bg(im):
    im = clean_tabs(im)
    im[262:296, BTN_X:BTN_X + BTN_W] = im[262:296, BTN_X - 60:BTN_X - 60 + BTN_W].copy()   # erase baked close button (real one is drawn centred)
    im = extend(im, HX0, HX1, HXI, DX, 1, 60, 250)                    # rows of the plain panel only
    im = extend(im, VY0, VY1, VYI, DY, 0, 20, 278 + DX)               # columns of the plain panel only
    return im

def tabs(p):
    pitch = (W0 + DX - 26 - 58) // 4; start = (W0 + DX - (4 * pitch + 58)) // 2     # original: pitch 62 = xspacing 58 + interx 4, margins 13
    a, b = 'position primary (13, 13)', 'interx 4 '
    assert a in p and b in p
    return p.replace(a, 'position primary (%d, 13)' % start).replace(b, 'interx %d ' % (pitch - 58))

def vband(im, y0, y1, yi, n):
    return np.concatenate([im[:yi], tile(im[y0:y1], n, 0), im[yi:]], 0)

def edit_trade(t):
    a = t.index('name "Tradeplate Trade Interface"'); head, rest = t[:a], t[a:]
    for old, new in (('position (135, 324)', 'position (135, %d)' % (324 + DYT)), ('position (257, 324)', 'position (%d, %d)' % (257 + 4 * DP, 324 + DYT))):
        assert old in head; head = head.replace(old, new)
    for old, new in (('content area (8, 8) - (78, 230)', 'content area (8, 8) - (%d, %d)' % (78 + DP, 230 + DYT)), ('content area (2, 2) - (103, 242)', 'content area (2, 2) - (%d, %d)' % (103 + DP, 242 + DYT))):
        assert old in rest; rest = rest.replace(old, new)
    if DP:   # right half of the window shifts by 4*DP (right trader plate, balance button, mode buttons at x=250)
        t2 = head + rest
        for old, new in (('position (375, 15)', 'position (%d, 15)' % (375 + 4 * DP)), ('position (337, 49)', 'position (%d, 49)' % (337 + 4 * DP)), ('position (250, 15)', 'position (%d, 15)' % (250 + 4 * DP))):
            assert old in t2; t2 = t2.replace(old, new)
        return t2
    return head + rest

def hcut(im, cuts):
    """insert filler columns: cuts = [(x, amount)] in ORIGINAL coordinates, filler = tiled band im[:, x-15:x+15]"""
    out = []; prev = 0
    for c in sorted(cuts):
        x, n = c[0], c[1]; sx = c[2] if len(c) > 2 else x - 15
        out.append(im[:, prev:x]); out.append(tile(im[:, sx:sx + 30], n, 1)); prev = x
    out.append(im[:, prev:]); return np.concatenate(out, 1)

def trade_bg(orig, sprites):
    """orig 454x362 -> (454+4DP)x(362+DYT): vertical band + per-row-band horizontal cuts (header/footer plates re-centred over columns), then widened column sprites pasted"""
    V = vband(orig, 150, 250, 250, DYT); H = V.shape[0]; d = DP
    Ah = [(118, d * 3 // 2, 95), (232, d, 95), (345, d * 3 // 2, 95)]                                   # header: plain floral pattern x 95..125
    Af = [(118, d * 3 // 2, 200), (232, d, 200), (345, d * 3 // 2, 200)]                                # footer: pattern between the plates
    Bc = [(118, d, 150), (170, d, 150), (282, d, 260), (335, d, 260)]                                   # bars
    Cc = [(60, d), (170, d), (282, d), (390, d)]
    bands = [(0, 49, Ah), (49, 76, Bc), (76, 322 + DYT, Cc), (322 + DYT, H, Af)]
    N = np.concatenate([hcut(V[a:b], c) for a, b, c in bands], 0)
    ys = (105, 76, 76, 105)
    for k, spr in enumerate(sprites):
        x = 13 + k * (108 + DP); N[ys[k]:ys[k] + spr.shape[0], x:x + spr.shape[1]] = spr
    return N

def edit_bmg(t):
    parts = re.split(r'(?m)^(?=name\s+")', t); out = []; n = 0
    for p in parts:
        if p.startswith('name "NPC Inventory Plate"'):
            p = tabs(p)
            cx = (W0 + DX - (2 * BTN_W + BTN_GAP)) // 2      # the PAIR [Close | Sort] is centred: left margin = right margin (422: 145 | 145; the original window 332: 100 | 100)
            p2 = p.replace('position (135, 265)', 'position (%d, %d)' % (cx, 265 + DY)); assert p2 != p; p = p2; n += 1
            i = p.rindex('end form'); p = p[:i] + sortbtn.bmg_block(NSPR, cx + BTN_W + BTN_GAP, 265 + DY) + p[i:]
        elif p.startswith('name "NPC Inventory Items"'):
            a = 'content area (2, 0) - (280, 199)'; b = 'content area (14, 55) - (318, 255)'; assert a in p and b in p
            p = p.replace(a, 'content area (2, 0) - (%d, %d)' % (280 + DX, 199 + DY)).replace(b, 'content area (14, 55) - (%d, %d)' % (318 + DX, 255 + DY)); n += 1
        out.append(p)
    assert n == 2
    return ''.join(out)

def main():
    il = OUT + r'\static\imagelists'; os.makedirs(il, exist_ok=True); os.makedirs(OUT + r'\dat', exist_ok=True)
    ents = C.read_index(SRC + r'\CPackedi.8c'); blob = open(SRC + r'\CPackedb.8c', 'rb').read()
    bg = C.decode(blob, ents, 4); assert bg.shape[:2] == (H0, W0), bg.shape
    new = build_bg(bg); assert new.shape[:2] == (H0 + DY, W0 + DX)
    global NSPR; NSPR = len(ents)
    rep = {4: new, 5: vband(C.decode(blob, ents, 5), 150, 250, 250, DYT)}
    for k, sp in enumerate(sortbtn.make([C.decode(blob, ents, i) for i in (197, 198, 199)])): rep[NSPR + k] = sp
    for i in (88, 89, 90, 91): rep[i] = vband(C.decode(blob, ents, i), 100, 160, 160, DYT)
    if DP:
        for i in (88, 89, 90, 91): rep[i] = hcut(rep[i], [(40, DP)])
        rep[5] = trade_bg(C.decode(blob, ents, 5), [rep[i] for i in (88, 89, 90, 91)])
    pack_resized(ents, blob, rep, il + r'\CPackedi.8c', il + r'\CPackedb.8c')
    es = cmpfile.read(FLAT); e = cmpfile.find(es, 'bmg\\inventpl.bmg'); e.data = edit_bmg(e.data.decode('latin-1')).encode('latin-1')
    for p in ('Tradepl.bmg', 'tradepl.bmg'):
        et = cmpfile.find(es, 'bmg\\' + p)
        if et: break
    et.data = edit_trade(et.data.decode('latin-1')).encode('latin-1')
    cmpfile.write(OUT + r'\dat\flat.cmp', es)
    import cv2; cv2.imwrite(OUT + r'\bg4_big_preview.png', cv2.cvtColor(new, cv2.COLOR_RGBA2BGRA))
    print('ok', new.shape[1], 'x', new.shape[0])
main()
