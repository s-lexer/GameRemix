"""Bigger CHARACTER STATS window (CStatusPlate, statuspl.cpp; background sprite 8/186, 224x367) for any font. DATA ONLY, no exe patch.
usage: python make_big_stats.py <base=e> [--profile wide] [--dx N] [--dy N] [--pairs auto|0|1] [--src DIR] [--flat FILE] [--global FILE] [--out DIR]
       (legacy form: python make_big_stats.py DX DY base ...)
  base     orig | c | e : skin whose 8/186 is stretched (scratch/gfx_sets/orig, scratch/ui_skins/C|E/static/imagelists); or a directory with CPackedi.8c/CPackedb.8c
  profile  font the layout is sized for (width of the widest line, RU and EN, measured with mlfont, see docs/recon/2026-11-07_stats_window.md):
             small = original fonts fontn3-  (H13, widest 206 px)      -> window 260
             big   = project 'large' set fontn3 (H16, widest 253 px)   -> window 308
             wide  = widest known (redrawn set, H22, widest 355 px)    -> window 408  (DEFAULT: also fits the two smaller ones, only airier)
           window width = widest line + 52 px; row pitch = original pitch + (H-13); height follows from the rows.
  --pairs  auto: keep the two-column rows (Offense|Damage, Defense|Armor, Weight|Gold) only if both columns fit with the widest strings of the profile, otherwise one row each
  --dx/--dy  override the automatic width / height (extra height is spread over the row gaps)
  --src    archive-8 dir to take as the base INSTEAD of the skin (to chain onto set_bigbag_*/set_trade_*: their 8c holds the sort-button sprites etc.)
  --flat   flat.cmp to take as the base (default scratch/sr_lab/flat_before_bigbag.cmp = pristine; chain: scratch/sr_lab/set_trade_e/dat/flat.cmp)
  --global global.cmp of the game (default C:/ARM/WORK/MODDING/GAMES/DivineDivinity/gfx_pilot_game/dat/global.cmp)
Output (<out> default scratch/sr_lab/set_bigstats_<base>[_<profile>]): static/imagelists/CPackedi.8c,CPackedb.8c (sprite 186 replaced), dat/flat.cmp (bmg\\statuspl.bmg buttons + bmg\\statuspl.dat),
  dat/global.cmp (entry dat\\statuspl.cmp REPLACED: this is the file the game really reads), dat/statuspl.cmp (loose copy), bg186_preview.png, layout_preview_{ru,en}.png.
WHY global.cmp: CStatusPlate ctor 0x52e7b0 reads "dat\\statuspl.cmp" through the virtual file system when dat\\global.cmp is open (DAT_006ddd24 != 0; always in the shipped game),
  the loose file dat\\statuspl.cmp is used only without global.cmp; bmg\\statuspl.dat is parsed only if the file is absent from both.
The equipment page (sprite 8/2, doll slots are exe constants) is NOT enlarged; 'Show StatusPlate Button' (15,304) and 'Show Statistics Button' are left alone."""
import os, sys, re, struct, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'gfx_pilot', 'tools')); sys.path.insert(0, os.path.join(HERE, '..', '..', 'analysis'))
import numpy as np, cv2, cpacked as C, cmpfile
from make_big_inventory import pack_resized
R = r'D:\ARM\OldGameFixer'
BASES = {'orig': R + r'\scratch\gfx_sets\orig', 'c': R + r'\scratch\ui_skins\C\static\imagelists', 'e': R + r'\scratch\ui_skins\E\static\imagelists', 'a': R + r'\scratch\ui_skins\A\static\imagelists', 'b': R + r'\scratch\ui_skins\B\static\imagelists', 'd': R + r'\scratch\ui_skins\D\static\imagelists', 'orig-v2': R + r'\scratch\gfx_sets\v2_1'}
CMP0 = r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity\gfx_pilot_game\dat\statuspl.cmp'    # stock file (sha256 9c4d1353..., identical in the Steam copy; also inside global.cmp)
GLOBAL0 = r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity\gfx_pilot_game\dat\global.cmp'
W0, H0, SPR = 224, 367, 186
TOP, BOT = 16, 309            # rows [0,TOP) = garland, [TOP,BOT) = interior + side borders, [BOT,H0) = lattice strip with snakes and the (baked) close button
YI, XC = 190, 112             # vertical insertion row / centre column
# width (px, mlfont advances, worst of RU/EN, values 999/9999/12345678) of the widest line T and of the pair strings, per profile; H = glyph height of the font
PROFILES = {'small': dict(H=13, T=206, off=105, dmg=110, dfn=81, arm=71, wt=119, gold=110, font='fontn3-'),
            'big':   dict(H=16, T=253, off=132, dmg=135, dfn=100, arm=89, wt=149, gold=137, font='fontn3'),
            'wide':  dict(H=22, T=355, off=184, dmg=188, dfn=140, arm=124, wt=208, gold=192, font='rd_en_g_n')}
MARGIN = 26                   # text margin: window width = widest line + 52 px (frame inner edge x=14 + 12 px air each side)

def opt(args, name, default):
    if name in args:
        i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
    return default

def _parts(m, mx):
    k = -(-m // mx); q, r = divmod(m, k); return [q + (1 if i < r else 0) for i in range(k)]

def ins_x(im, xi, n, mx=50):
    """insert n columns (n even) at xi: mirror excursions [flip(S), S], S = L<=mx columns left of xi (sum of L = n/2) -> continuous everywhere, and never reaches the dark frame vignette"""
    if n <= 0: return im
    assert n % 2 == 0; fill = []
    for L in _parts(n // 2, mx): S = im[:, xi - L:xi]; fill += [S[:, ::-1], S]
    return np.concatenate([im[:, :xi]] + fill + [im[:, xi:]], 1)

def ins_y(im, yi, n, mx=50):
    if n <= 0: return im
    assert n % 2 == 0; fill = []
    for L in _parts(n // 2, mx): S = im[yi - L:yi]; fill += [S[::-1], S]
    return np.concatenate([im[:yi]] + fill + [im[yi:]], 0)

def pingpong(a, n):
    """n columns of a, a reversed, a, ... (a starts the sequence)"""
    w = a.shape[1]; cols = []
    for i in range(n):
        p = i % (2 * w); cols.append(a[:, p if p < w else 2 * w - 1 - p])
    return np.stack(cols, 1)

def widen_gap(strip, a, b, n):
    """lattice gap [a,b) of the bottom strip grows by n: the gap is stretched x2 and ping-pong tiled (stretching alone smears for big n)"""
    g = strip[:, a:b]; g2 = cv2.resize(g, (g.shape[1] * 2, g.shape[0]), interpolation=cv2.INTER_CUBIC)
    return np.concatenate([strip[:, :a], pingpong(g2, (b - a) + n), strip[:, b:]], 1)

def build_bg(im, DX, DY):
    assert im.shape[:2] == (H0, W0), im.shape
    h = DX // 2; q = h // 2 * 2
    top = ins_x(ins_x(im[:TOP], 136, q, 30), 88, q, 30) if q else im[:TOP]               # garland: two joints, the centre notch stays centred
    if h % 2: raise SystemExit('DX must be a multiple of 4')
    mid = ins_x(im[TOP:BOT], XC, DX)                                              # interior texture; borders at the sides untouched
    bot = im[BOT:]
    if h: bot = widen_gap(widen_gap(bot, 143, 152, h), 72, 81, h)                 # lattice strip: only the two small gaps beside the button grow
    out = np.concatenate([top, mid, bot], 0); assert out.shape[1] == W0 + DX, (out.shape, DX)
    return ins_y(out, YI, DY)

# ---- layout of the stat lines (records of statuspl.cmp / bmg\statuspl.dat; order = dat) --------------------------------------------------
BTN = (1, 2, 4, 5, 7, 8, 10, 11)                                          # '+' '-' buttons (align l): move with the right edge
# (records, original gap to the previous row); a row's records are listed with their ORIGINAL y so that offsets (buttons y-4) are kept
FIX = [([28], 0), ([14], 12), ([15], 17), ([20], 12), ([12], 16), ([13], 12), ([0, 1, 2], 20), ([3, 4, 5], 18), ([6, 7, 8], 18), ([9, 10, 11], 18)]
TAIL = [([23], 19), ([24], 12), ([25], 12), ([26], 12), ([27], 14)]
ORIG_Y = [112, 110, 106]  # unused placeholder

class Layout:
    def __init__(s, prof, DX=None, DY=None, pairs='auto'):
        P = PROFILES[prof]; s.P = P; s.prof = prof; s.H = P['H']
        s.DX = DX if DX is not None else max(0, -(-(P['T'] + 2 * MARGIN - (W0 - 2 * 0)) // 4) * 4)
        s.W = W0 + s.DX; s.cx = XC + s.DX // 2
        def fits(wl, wr, gap=12):                                           # two columns centred on cx +-D/2, text kept >=16 px from the frame edge
            D = math.ceil((wl + wr) / 2) + gap
            ok = s.W / 2 - D / 2 - wl / 2 >= 16 and s.W / 2 - D / 2 - wr / 2 >= 16
            return D, ok
        s.pairs = {}
        for nm, (a, b) in {'p1': ('off', 'dmg'), 'p2': ('dfn', 'arm'), 'p3': ('wt', 'gold')}.items():
            D, ok = fits(P[a], P[b]); s.pairs[nm] = (D, ok if pairs == 'auto' else pairs == '1')
        rows = list(FIX)
        if s.pairs['p1'][1]: rows.append(([16, 21], 18))
        else: rows += [([16], 18), ([21], 13)]
        if s.pairs['p2'][1]: rows.append(([17, 22], 13))
        else: rows += [([17], 13), ([22], 13)]
        rows += TAIL
        if s.pairs['p3'][1]: rows.append(([18, 19], 15))
        else: rows += [([18], 15), ([19], 13)]
        rows.append(([29], 13)); s.rows = rows
        s.ys = s.chain(P['H'] - 13)
        need = s.ys[-1] - 292                                               # DY so that the points row sits where it was relative to the bottom group
        need += need % 2
        if DY is not None and DY > need:
            extra = (DY - need) / (len(rows) - 1); s.ys = s.chain(P['H'] - 13 + extra); need = DY
        s.DY = need if DY is None or DY <= need else DY
        s.ys[-1] = 292 + s.DY                                               # points row on its backdrop
    def chain(s, b):
        ys = []; y = 21.0
        for i, (rs, gap) in enumerate(s.rows):
            if i: y += gap + b
            ys.append(int(round(y)))
        return ys
    def table(s):
        """rec -> (x, y)"""
        T = {}; PRIM = {(16, 21): 'p1', (17, 22): 'p2', (18, 19): 'p3'}
        ORIGY = {0: 110, 1: 106, 2: 106, 3: 128, 4: 124, 5: 124, 6: 146, 7: 142, 8: 142, 9: 164, 10: 160, 11: 160, 12: 78, 13: 90, 14: 33, 15: 50, 16: 182, 17: 195, 18: 279, 19: 279, 20: 62, 21: 182, 22: 195,
                 23: 214, 24: 226, 25: 238, 26: 250, 27: 264, 28: 21, 29: 292}
        for (rs, gap), y in zip(s.rows, s.ys):
            base = ORIGY[rs[0]]
            for r in rs:
                ny = y + ORIGY[r] - base
                if r in BTN: nx = {1: 169, 2: 188, 4: 169, 5: 188, 7: 169, 8: 188, 10: 169, 11: 188}[r] + s.DX
                elif len(rs) == 2:
                    D = s.pairs[PRIM[tuple(rs)]][0]; nx = s.cx - D // 2 if r == rs[0] else s.cx + (D - D // 2)
                else: nx = s.cx
                T[r] = (nx, ny)
        return T
    def report(s):
        L = ['profile %s (H=%d, widest line %d px): window %dx%d (DX=%d DY=%d)' % (s.prof, s.H, s.P['T'], s.W, H0 + s.DY, s.DX, s.DY)]
        L.append('rows: %d, pairs kept: %s' % (len(s.rows), {k: v[1] for k, v in s.pairs.items()}))
        return '\n'.join(L)

def edit_cmp(raw, L):
    assert len(raw) == 360; out = bytearray(raw); T = L.table()
    for k in range(30):
        x, y, a = struct.unpack_from('<3i', raw, k * 12); nx, ny = T[k]; struct.pack_into('<3i', out, k * 12, nx, ny, a)
    return bytes(out)

def edit_dat(t, L):
    k = [0]; out = []; T = L.table()
    def sub(m):
        i = k[0]; k[0] += 1; nx, ny = T[i]; return '%s%s%d%s%d' % (m.group(1), m.group(2), nx, m.group(4), ny)
    for ln in t.split('\n'):
        out.append(ln if ln.lstrip().startswith('#') else re.sub(r'([clrCLR])(\s+)(\d+)(\s+)(\d+)', sub, ln))
    assert k[0] == 30, k[0]; return '\n'.join(out)

def edit_bmg(t, L):
    """buttons: bottom group +DY; right-hand button +DX; centred ones +DX/2. 'Show StatusPlate Button' (shown on the EQUIPMENT page, size unchanged) and 'Show Statistics Button' are left alone."""
    DX, DY = L.DX, L.DY
    todo = {'StatusPlate Commit Button': (DX // 2, DY), 'StatusPlate Points Backdrop': (DX // 2, DY), 'StatusPlate Close Button': (DX // 2, DY),
            'Show ShieldPlate Button': (0, DY), 'Show Research Button': (DX, DY)}
    parts = re.split(r'(?m)^(?=name\s+")', t); out = []; n = 0
    for p in parts:
        m = re.match(r'name\s+"([^"]*)"', p)
        if m and m.group(1) in todo:
            dx, dy = todo[m.group(1)]
            p, c = re.subn(r'position \((\d+), ?(\d+)\)', lambda q: 'position (%d, %d)' % (int(q.group(1)) + dx, int(q.group(2)) + dy), p); assert c == 1, m.group(1); n += 1
        out.append(p)
    assert n == len(todo), n; return ''.join(out)

def load_font(name):
    import mlfont as M, gzip
    for d in (r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity\gfx_pilot_game\fonts', ):
        p = d + '\\' + name + '.fnt'
        if os.path.exists(p): return M.parse(open(p, 'rb').read())
    p = R + r'\games\divine-divinity\fonts_research\experiment_redrawn\%s.fnt.gz' % name
    if os.path.exists(p): return M.parse(gzip.decompress(open(p, 'rb').read()))
    return None

def strings(lang):
    try:
        import stats_text; return (stats_text.ru if lang == 'ru' else stats_text.en)
    except Exception as e: print('no strings', e); return None

def preview(bg, L, path, lang):
    """schematic only (not a game screenshot): background + stat lines at the new record positions with the profile font; reports lines nearer than 12 px to the frame"""
    try: import mlfont as M; from PIL import Image
    except Exception as e: print('no preview:', e); return
    f = load_font(L.P['font']); T = strings(lang)
    if f is None or T is None: print('no font/strings for preview'); return
    ids = {28: None, 14: 0xe4, 15: 0xe7, 20: 0xe8, 12: 0xe2, 13: 0xe3, 0: 0xde, 3: 0xdf, 6: 0xe0, 9: 0xe1, 16: 0xe9, 21: 0xeb, 17: 0xea, 22: 0xec, 23: 0xf0, 24: 0xf1, 25: 0xf2, 26: 0xf3, 27: 0xf4, 18: 0xed, 19: 0xef, 29: 0xf5}
    VAL = {0xde: ('150',), 0xdf: ('150',), 0xe0: ('150',), 0xe1: ('150',), 0xe2: ('9999', '9999'), 0xe3: ('9999', '9999'), 0xe4: ('99',), 0xe7: ('12345678',), 0xe8: ('12345678',), 0xe9: ('999',), 0xea: ('999',), 0xeb: ('999', '999'),
           0xec: ('999',), 0xed: ('9999', '9999'), 0xef: ('9999999',), 0xf0: ('999',), 0xf1: ('999',), 0xf2: ('999',), 0xf3: ('999',), 0xf4: ('999',), 0xf5: ('99',)}
    tab = L.table(); im = Image.fromarray(bg[..., :3].copy()); px = im.load(); W = im.width; bad = 0; maxx = 0
    for k, i in ids.items():
        t = 'Nina' if i is None else T[i]
        for v in VAL.get(i, ()): t = t.replace('%d', v, 1)
        x, y = tab[k]; w, h, pp = M.render(f, t); w -= 4; x0 = x - w // 2 - 2
        if x0 < 14 + 4 or x0 + w > W - 14 - 4: bad += 1; print('  NEAR/OVER frame:', lang, k, repr(t), 'x=%d..%d of %d' % (x0, x0 + w, W))
        for (xx, yy), c in pp.items():
            X, Y = x0 + xx, y + yy
            if 0 <= X < im.width and 0 <= Y < im.height: px[X, Y] = c
    for k in BTN:
        x, y = tab[k]
        for X in range(x, x + 18):
            for Y in (y, y + 17):
                if X < im.width and Y < im.height: px[X, Y] = (255, 255, 0)
    im.save(path); print('preview', lang, '->', path, '| lines at/over frame:', bad)

def main():
    args = sys.argv[1:]
    prof = opt(args, '--profile', 'wide'); pairs = opt(args, '--pairs', 'auto'); dx = opt(args, '--dx', None); dy = opt(args, '--dy', None)
    src = opt(args, '--src', None); flat = opt(args, '--flat', R + r'\scratch\sr_lab\flat_before_bigbag.cmp'); gl = opt(args, '--global', GLOBAL0); out = opt(args, '--out', None)
    if args and args[0].isdigit():                                       # legacy: DX DY base
        dx = dx or args[0]; dy = dy or (args[1] if len(args) > 1 else None); args = args[2:]
    base = args[0] if args else 'e'
    L = Layout(prof, int(dx) if dx else None, int(dy) if dy else None, pairs); print(L.report())
    d8 = src or BASES.get(base.lower(), base); bn = base.lower() if base.lower() in BASES else os.path.basename(os.path.normpath(base))
    out = out or R + r'\scratch\sr_lab\set_bigstats_' + bn + ('' if prof == 'wide' else '_' + prof)
    il = out + r'\static\imagelists'; os.makedirs(il, exist_ok=True); os.makedirs(out + r'\dat', exist_ok=True)
    ents = C.read_index(d8 + r'\CPackedi.8c'); blob = open(d8 + r'\CPackedb.8c', 'rb').read()
    bg = C.decode(blob, ents, SPR); new = build_bg(bg, L.DX, L.DY); assert new.shape[:2] == (H0 + L.DY, W0 + L.DX)
    pack_resized(ents, blob, {SPR: new}, il + r'\CPackedi.8c', il + r'\CPackedb.8c')
    es = cmpfile.read(flat)
    e = cmpfile.find(es, 'bmg\\statuspl.bmg'); e.data = edit_bmg(e.data.decode('latin-1'), L).encode('latin-1')
    e = cmpfile.find(es, 'bmg\\statuspl.dat'); e.data = edit_dat(e.data.decode('latin-1'), L).encode('latin-1')
    cmpfile.write(out + r'\dat\flat.cmp', es)
    raw = edit_cmp(open(CMP0, 'rb').read(), L); open(out + r'\dat\statuspl.cmp', 'wb').write(raw)
    gs = cmpfile.read(gl); ge = cmpfile.find(gs, 'dat\\statuspl.cmp'); assert len(ge.data) == 360; ge.data = raw; cmpfile.write(out + r'\dat\global.cmp', gs)
    cv2.imwrite(out + r'\bg186_preview.png', cv2.cvtColor(new, cv2.COLOR_RGBA2BGRA))
    for lang in ('ru', 'en'): preview(new, L, out + r'\layout_preview_%s.png' % lang, lang)
    print('ok: window %dx%d, out=%s' % (L.W, H0 + L.DY, out))

main()
