# Regression test for "the game quits when dgVoodoo is switched on" (found 07.11.2026, docs/recon/2026-11-07_steam_en_check.md).
# Divine Divinity compares config.div width/height with the modes the DirectDraw wrapper enumerates; a size that is not in the list ->
# "reset configuration?" and, after "No", a silent exit. dgVoodoo's stock list has no 2048x1152 (the 125% interface size), 3840x2160, 2752x1152, 1707x960;
# [DirectXExt] ExtraEnumeratedResolutions adds them. No game is started: scratch/ddfx_test/ddenum.exe (source: games/divine-divinity/fx_shader/ddfx_src/fx/ddenum.c)
# enumerates the modes of the DDraw.dll that sits in the same folder.   python tools/test_dgv_modes.py
import os, sys, shutil, subprocess, tempfile, re
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
DGV = os.path.join(ROOT, 'games', 'divine-divinity', 'payload', 'dgv'); ENUM = os.path.join(ROOT, 'scratch', 'ddfx_test', 'ddenum.exe')
SIZES = [(1920, 1080), (2560, 1440), (2048, 1152), (3840, 2160), (2752, 1152), (1707, 960)]
def found(folder, w, h): return subprocess.run([os.path.join(folder, 'ddenum.exe'), str(w), str(h)], cwd=folder, capture_output=True, timeout=60).stdout.decode('latin1').strip().endswith('FOUND')
d = tempfile.mkdtemp(prefix='dgvmodes_')
try:
    shutil.copy(ENUM, d); shutil.copy(os.path.join(DGV, 'DDraw.dll'), d); conf = open(os.path.join(DGV, 'dgVoodoo.conf'), 'rb').read(); fails = 0
    open(os.path.join(d, 'dgVoodoo.conf'), 'wb').write(conf)
    stock = {s: found(d, *s) for s in SIZES}
    print('stock list (bundled dgVoodoo.conf):', {'%dx%d' % s: v for s, v in stock.items()})
    # facts the fix relies on
    assert stock[(1920, 1080)] and stock[(2560, 1440)], 'HD and 2K presets must be in the stock list'
    assert not stock[(2048, 1152)], 'expected: 2048x1152 is NOT in dgVoodoo\'s stock list (this is the bug)'
    extra = ', '.join('%dx%d' % s for s in SIZES if not stock[s])
    conf2 = re.sub(rb'(?m)^(ExtraEnumeratedResolutions\s*=).*$', lambda m: m.group(1) + b' ' + extra.encode(), conf)
    assert conf2 != conf, 'ExtraEnumeratedResolutions key not found in the bundled conf'
    open(os.path.join(d, 'dgVoodoo.conf'), 'wb').write(conf2)
    with_extra = {s: found(d, *s) for s in SIZES}
    print('with ExtraEnumeratedResolutions =', extra, '->', {'%dx%d' % s: v for s, v in with_extra.items() if not stock[s]})
    for s in SIZES:
        if not stock[s] and not with_extra[s]: print('FAIL', s); fails += 1
    print('PASS' if not fails else 'FAIL'); sys.exit(1 if fails else 0)
finally: shutil.rmtree(d, ignore_errors=True)
