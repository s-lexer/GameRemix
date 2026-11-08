"""EXPERIMENT (stage 2): scaled inventory window. Makes overlay sets in scratch/ui_skins/_big_inventory_test/<variant>/ (game-relative layout + manifest.json):
  dat/flat.cmp (bmg/inventpl.bmg with scaled coordinates), static/imagelists/CPackedi/b.8c (scaled window/button sprites, NEW sizes),
  optionally CPackedi/b.3c (item icons scaled too).
usage: python make_big_inventory.py   (variants: x15, x20, x20_icons)"""
import os, sys, re, json, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'gfx_pilot', 'tools'))
import numpy as np, cv2, cpacked as C, cmpfile, copy, struct

R = r'D:\ARM\OldGameFixer'; BASE = R + r'\scratch\gfx_sets\v2full'; FLAT = r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity\gfx_pilot_game\dat\flat.cmp'; OUT = R + r'\scratch\ui_skins\_big_inventory_test'
BLOCKS = ['NPC Inventory Plate', 'NPC Inventory Items', 'Object Inventory Plate', 'Object Inventory Items']


def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def upscale(rgba, k):
    h, w = rgba.shape[:2]; nw, nh = int(round(w * k)), int(round(h * k))
    a = (rgba[..., 3] > 0).astype(np.float32); rgb = rgba[..., :3].astype(np.float32)
    num = cv2.GaussianBlur(rgb * a[..., None], (0, 0), 2); den = cv2.GaussianBlur(a, (0, 0), 2)[..., None] + 1e-4
    rgb = np.where(a[..., None] > 0, rgb, num / den)  # fill transparent area with neighbour colours: no dark halos
    up = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    b = cv2.GaussianBlur(up, (0, 0), 1.0); up = np.clip(up + .45 * (up - b), 0, 255)
    am = cv2.resize(a, (nw, nh), interpolation=cv2.INTER_LINEAR) > .5
    return np.dstack([up.astype(np.uint8), (am * 255).astype(np.uint8)])


def pack_resized(ents, blob, repl, out_idx, out_blob):
    """repl: {i: RGBA of ANY size}; entry geometry is updated (w,h,w-1,h-1), pd/res stay 0 as in the originals"""
    ne = []; off = 0
    with open(out_blob, 'wb') as fb:
        for i, e in enumerate(ents):
            e2 = copy.copy(e)
            if i in repl:
                im = repl[i]; h, w = im.shape[:2]
                pl = C.encode(im, 1); raw = struct.pack('<I', len(pl)) + C.lzo_compress(pl, True)
                e2.w, e2.h, e2.wi, e2.hi = w, h, w - 1, h - 1
            else: raw = C.raw_block(blob, ents, i)
            e2.off = off; fb.write(raw); off += len(raw); ne.append(e2)
        for i in sorted(k for k in repl if k >= len(ents)):          # новые спрайты в конец архива (индекс = len(ents)+n, без пропусков)
            assert i == len(ne), (i, len(ne)); im = repl[i]; h, w = im.shape[:2]; e2 = copy.copy(ents[0])
            pl = C.encode(im, 1); raw = struct.pack('<I', len(pl)) + C.lzo_compress(pl, True)
            e2.w, e2.h, e2.wi, e2.hi, e2.ax, e2.ay, e2.pd = w, h, w - 1, h - 1, 0, 0, 0; e2.off = off; fb.write(raw); off += len(raw); ne.append(e2)
    C.write_index(out_idx, ne)


def split_blocks(t):
    parts = re.split(r'(?m)^(?=name\s+")', t)
    return parts


def scale_nums(line, k):
    f = lambda m: str(int(round(int(m.group(0)) * k)))
    return re.sub(r'-?\d+', f, line)


def scale_block(txt, k):
    out = []
    for ln in txt.split('\n'):
        s = ln.strip()
        if re.match(r'(position|content area|hotarea)\b', s) and 'image list' not in s:
            ln = re.sub(r'(\([^)]*\))', lambda m: scale_nums(m.group(1), k), ln)
        elif re.match(r'normal image list \d+ index \d+ hotarea', s):
            ln = re.sub(r'hotarea.*$', lambda m: re.sub(r'(\([^)]*\))', lambda mm: scale_nums(mm.group(1), k), m.group(0)), ln)
        elif re.match(r'(row|column|size)\b|.*xspacing', s) and 'xspacing' in s:
            ln = re.sub(r'(xspacing|yspacing|interx|intery)\s+(\d+)', lambda m: '%s %d' % (m.group(1), round(int(m.group(2)) * k)), ln)
        out.append(ln)
    return '\n'.join(out)


def make(name, k, icons):
    d = os.path.join(OUT, name); il = os.path.join(d, 'static', 'imagelists'); os.makedirs(il, exist_ok=True); os.makedirs(os.path.join(d, 'dat'), exist_ok=True)
    es = cmpfile.read(FLAT); e = cmpfile.find(es, 'bmg\\inventpl.bmg'); t = e.data.decode('latin-1')
    parts = split_blocks(t); used = set(); res = []
    for p in parts:
        m = re.match(r'name\s+"([^"]*)"', p)
        if m and m.group(1) in BLOCKS:
            used |= {int(x) for x in re.findall(r'image list 8 index (\d+)', p)}; p = scale_block(p, k)
        res.append(p)
    e.data = ''.join(res).encode('latin-1'); cmpfile.write(os.path.join(d, 'dat', 'flat.cmp'), es)
    ents = C.read_index(BASE + r'\CPackedi.8c'); blob = open(BASE + r'\CPackedb.8c', 'rb').read()
    pack_resized(ents, blob, {i: upscale(C.decode(blob, ents, i), k) for i in sorted(used)}, il + r'\CPackedi.8c', il + r'\CPackedb.8c')
    arch = [8]
    if icons:
        e3 = C.read_index(BASE + r'\CPackedi.3c'); b3 = open(BASE + r'\CPackedb.3c', 'rb').read()
        rep = {}
        for i, en in enumerate(e3):
            im = C.decode(b3, e3, i)
            if im is not None and en.w <= 60 and en.h <= 60: rep[i] = upscale(im, k)
        pack_resized(e3, b3, rep, il + r'\CPackedi.3c', il + r'\CPackedb.3c'); arch.append(3)
    files = ['dat/flat.cmp'] + ['static/imagelists/CPacked%s.%dc' % (x, n) for n in arch for x in 'ib']
    man = dict(manifest_version=1, id='bigtest_' + name, version='0.1', name=dict(ru='ПРОБА: инвентарь x%.1f' % k, en='TEST: inventory x%.1f' % k), description=dict(ru='Экспериментальный набор: масштаб окон инвентаря (NPC + объектов), правка inventpl.bmg в flat.cmp.', en='Experimental: scaled inventory windows + patched inventpl.bmg'),
               game='divine-divinity', kind='experiment', scale=k, scaled_sprites_arch8=sorted(used), icons_scaled=icons,
               files=[dict(path=f, size=os.path.getsize(os.path.join(d, f)), sha256=sha(os.path.join(d, f))) for f in files])
    json.dump(man, open(os.path.join(d, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(name, 'sprites', len(used), 'icons' if icons else '', [f['size'] // 1024 for f in man['files']])


if __name__ == '__main__':
    make('x15', 1.5, False); make('x20', 2.0, False); make('x20_icons', 2.0, True)
