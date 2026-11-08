"""Verify a built skin against its base set: sizes/anchors/flags identical, transparency masks identical, count of changed sprites, SHA-256 vs manifest.
usage: python verify_skin.py <skin_dir> [--base-set DIR]"""
import os, sys, json, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', '..', 'gfx_pilot', 'tools'))
import numpy as np, cpacked as C
d = sys.argv[1]; man = json.load(open(os.path.join(d, 'manifest.json'), encoding='utf-8'))
base = sys.argv[3] if len(sys.argv) > 3 else r'D:\ARM\OldGameFixer\scratch\gfx_sets\%s' % man['base_set']
ok = True
for f in man['files']:
    p = os.path.join(d, f['path']); h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    if h != f['sha256']: print('HASH MISMATCH', f['path']); ok = False
for n in man['compat']['sprite_counts']:
    ni, nb = 'CPackedi.%sc' % n, 'CPackedb.%sc' % n
    a = C.read_index(os.path.join(base, ni)); ba = open(os.path.join(base, nb), 'rb').read()
    b = C.read_index(os.path.join(d, 'static', 'imagelists', ni)); bb = open(os.path.join(d, 'static', 'imagelists', nb), 'rb').read()
    assert len(a) == len(b), 'count differs'
    chg = 0; bad = 0
    for i, (x, y) in enumerate(zip(a, b)):
        if (x.w, x.h, x.flags, x.ax, x.ay, x.wi, x.hi, x.pd) != (y.w, y.h, y.flags, y.ax, y.ay, y.wi, y.hi, y.pd): bad += 1; print(' META differs', n, i); continue
        if C.raw_block(ba, a, i) == C.raw_block(bb, b, i): continue
        chg += 1
        pa, pb = C.payload_of(ba, a, i), C.payload_of(bb, b, i)
        if len(pa) != len(pb) or pa[:12 + 0] != pb[:12]: bad += 1; print(' LAYOUT differs', n, i); continue
        ia, ib = C.decode(ba, a, i), C.decode(bb, b, i)
        if not np.array_equal(ia[..., 3], ib[..., 3]): bad += 1; print(' MASK differs', n, i)
    print('archive', n, ':', len(a), 'sprites,', chg, 'changed,', bad, 'problems'); ok &= bad == 0
print('RESULT', 'OK' if ok else 'FAIL', man['id'])
