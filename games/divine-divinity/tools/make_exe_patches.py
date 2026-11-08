#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Byte-patch tables of div.exe 1.0.0.62 for the "Graphics" page of GameRemix: frame + windows + glow + interp + tick80  ->  games/divine-divinity/gfx/gfx.txt.

WHY A FRAME. Three of our patches add code to the exe (windows = trade/sort/positions in .cave, glow = item halo in .glow, interp = frame interpolation in .interp). Each one used to
add its own PE section at the end of the file, so they could not be switched on and off independently (two sections at the same address, shared header fields).
Now the "frame" (patch=frame) puts ALL THREE sections in the file once, at FIXED addresses (RVA .cave 0x355000, .glow 0x35d000, .interp 0x365000; zero-filled), and every
patch below only writes its own bytes inside its section plus its hooks in .text. The tables therefore do not depend on each other: any subset in any order gives the same exe
(verified here for all subsets x all orders, and against the scripts run one after another). The program (Core.SetBytePatch) puts the frame in before the first of them and
takes it out (file back to the original length, headers back) after the last one is off.

Tables:  patch=frame   header fields + the zero tail (append0:N), `needs` nothing
         patch=windows needs=frame: inv_patch.py --big 90 170 --max-y 0x2c5 (big backpack, wheel, free-place search) + trade_patch5.py (trade tiles/tabs/grouping/"worn" label, sort
                       button id 60 + Ctrl+C, start positions of equipment/status/backpack windows); the label "worn" is language dependent: point alternatives `pat~alt` (ru~en)
         patch=glow    needs=frame: glow_patch.py (halo of rank 3/4/5 items in the backpack + coloured Alt labels, names keep the original colours)
         patch=interp  needs=frame: interp_patch.py (frame interpolation)
         patch=tick80  needs=frame: tick80_patch.py --frame (80 Hz step + world objects at 20 fps: hooks in .text + code/data in the first 4096 bytes of .interp + the agent table in the virtual tail of .interp; the frame
                       is NOT changed: no own section, no header points). It lives in the same 4096 raw bytes as interp, so the two exclude each other by their own bytes (each sees the other as foreign).
Point format in gfx.txt: <hex file offset>:<original>:<patched>[~<patched alternative>]; points at offsets >= 2461696 lie in the tail added by the frame (their original is zeros).

usage: python make_exe_patches.py [--orig scratch/re/div.exe] [--work scratch/wp] [--write] [--no-verify]
   without --write the tables are only built and verified. Needs pefile, keystone-engine (the patch scripts); unicorn only for interp --test (not used here)."""
import os, sys, re, struct, hashlib, subprocess, itertools, argparse, shutil

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PR = os.path.join(ROOT, 'games', 'divine-divinity', 'patch_research')
sys.path.insert(0, PR)
SIZE = 2461696; REF_SHA = 'cd9f7a07c7a605c21052b3517346c7a63083063fb491276a3e4c9836c9b42a67'
IMG = 0x400000
# (name, RVA, virtual size, raw size)  - the raw data follows the original file in this order
SECTIONS = [(b'.cave', 0x355000, 0x8000, 0x8000), (b'.glow', 0x35D000, 0x8000, 0x1000), (b'.interp', 0x365000, 0x141000, 0x1000)]
TAIL = sum(s[3] for s in SECTIONS)   # 0xA000 = 40960
CHAR = 0xE0000060

def frame_exe(o):
    """original exe -> exe with the three sections (zero filled)"""
    d = bytearray(o); pe = struct.unpack_from('<I', d, 0x3c)[0]; nsec = struct.unpack_from('<H', d, pe + 6)[0]; opt = struct.unpack_from('<H', d, pe + 20)[0]
    assert nsec == 4, nsec
    tab = pe + 24 + opt; hdr = tab + nsec * 40
    assert not any(d[hdr:hdr + 40 * len(SECTIONS)]) and hdr + 40 * len(SECTIONS) <= struct.unpack_from('<I', d, tab + 20)[0], 'no room for the section headers'
    raw = SIZE; assert raw % 0x200 == 0
    for i, (nm, rva, vs, rs) in enumerate(SECTIONS):
        d[hdr + 40 * i:hdr + 40 * i + 40] = struct.pack('<8sIIIIIIHHI', nm, vs, rva, rs, raw, 0, 0, 0, 0, CHAR); raw += rs
    struct.pack_into('<H', d, pe + 6, nsec + len(SECTIONS))
    last = SECTIONS[-1]; struct.pack_into('<I', d, pe + 24 + 56, last[1] + last[2])
    d += b'\0' * TAIL
    return bytes(d)

def run(script, *args):
    r = subprocess.run([sys.executable, os.path.join(PR, script)] + [str(a) for a in args], capture_output=True, text=True)
    if r.returncode != 0: sys.exit('%s failed (%d):\n%s\n%s' % (script, r.returncode, r.stdout, r.stderr))
    return r.stdout.strip().splitlines()[-1:] or ['']

def runs(a, b, gap, lo=0):
    """changed runs [s,e) between a and b (gap = unchanged bytes tolerated inside a run)"""
    out = []
    for i in range(lo, len(a)):
        if a[i] != b[i]:
            if out and i - out[-1][1] <= gap: out[-1][1] = i + 1
            else: out.append([i, i + 1])
    return out

def table(a, b):
    pts = []
    for s, e in runs(a, b, 8, 0):
        if s >= SIZE: continue
        pts.append((s, a[s:e], b[s:e]))
    # the tail: sparse code, merge across zero gaps
    for s, e in runs(a, b, 24, SIZE): pts.append((s, a[s:e], b[s:e]))
    return pts

def overlap(p, q):
    return any(s1 < s2 + len(o2) and s2 < s1 + len(o1) for s1, o1, _ in p for s2, o2, _ in q)

def point_state(d, pts):
    """what Core's BytePatch.State says about exe bytes d for a table: 0 original, 1 patched, 2 mixed, -1 foreign bytes"""
    o = p = 0
    for s, a, b in pts:
        cur = bytes(d[s:s + len(a)]) if s + len(a) <= len(d) else bytes(len(a))   # beyond the end = the frame is not in yet = zeros
        if cur == a: o += 1
        elif cur == b: p += 1
        else: return -1
    return 0 if p == 0 else (1 if o == 0 else 2)

def excl(p1, p2):
    """the file with p2 written is foreign to the table p1 (and p1 does not recognise it)"""
    d = bytearray(SIZE + TAIL)
    for s, a, b in p2: d[s:s + len(b)] = b
    return point_state(d, p1) == -1

def fmt(pts, alts=None):
    out = []
    for s, o, n in pts:
        k = '%x:%s:%s' % (s, o.hex(), n.hex())
        if alts and s in alts: k += '~' + alts[s].hex()
        out.append(k)
    return out

def apply_pts(d, pts, on, alt=False, alts=None):
    for s, o, n in pts:
        v = n
        if alt and alts and s in alts: v = alts[s]
        d[s:s + len(o)] = v if on else o

def build(a):
    orig = open(a.orig, 'rb').read()
    if len(orig) != SIZE or hashlib.sha256(orig).hexdigest() != REF_SHA: sys.exit('--orig is not the reference div.exe 1.0.0.62 (sha256 %s)' % REF_SHA)
    w = a.work; os.makedirs(w, exist_ok=True)
    F = frame_exe(orig); fp = os.path.join(w, 'frame.exe'); open(fp, 'wb').write(F)
    # windows: inv_patch (big backpack + search + wheel) then trade_patch5 (russian label), and the english label
    print(run('inv_patch.py', fp, os.path.join(w, 'win_inv.exe'), '--big', 90, 170, '--max-y', '0x2c5'))
    print(run('trade_patch5.py', os.path.join(w, 'win_inv.exe'), os.path.join(w, 'win_ru.exe'), '--lang', 'ru'))
    print(run('trade_patch5.py', os.path.join(w, 'win_inv.exe'), os.path.join(w, 'win_en.exe'), '--lang', 'en'))
    print(run('glow_patch.py', fp, os.path.join(w, 'glow.exe')))
    print(run('interp_patch.py', fp, os.path.join(w, 'interp.exe')))
    import tick80_patch as T80   # tick80: code/data in the .interp section of the frame (no section of its own), same bytes as the script's --frame output
    T = T80.apply(F, frame=True)[0]; open(os.path.join(w, 'tick80.exe'), 'wb').write(T)
    rd = lambda n: open(os.path.join(w, n), 'rb').read()
    WR, WE, G, I = rd('win_ru.exe'), rd('win_en.exe'), rd('glow.exe'), rd('interp.exe')
    for n, x in (('win_ru', WR), ('win_en', WE), ('glow', G), ('interp', I)): assert len(x) == len(F), (n, len(x), len(F))
    assert len(T) == len(F), 'tick80 must not change the length'
    pw, pg, pi, ptk = table(F, WR), table(F, G), table(F, I), table(F, T)
    # the english label: the places where win_en differs from win_ru (must lie inside points of the windows table)
    # (merge: several label runs inside one point)
    alts = {}
    for p in pw:
        alt = bytearray(p[2]); ch = False
        for s, e in runs(WR, WE, 0):
            if p[0] <= s and e <= p[0] + len(p[1]): alt[s - p[0]:e - p[0]] = WE[s:e]; ch = True
        if ch: alts[p[0]] = bytes(alt)
    print('points: windows %d (%d bytes, %d with alt), glow %d, interp %d, tick80 %d (%d bytes)' % (len(pw), sum(len(p[1]) for p in pw), len(alts), len(pg), len(pi), len(ptk), sum(len(p[1]) for p in ptk)))
    for (n1, p1), (n2, p2) in itertools.combinations((('windows', pw), ('glow', pg), ('interp', pi), ('tick80', ptk)), 2):
        if {n1, n2} == {'interp', 'tick80'}:   # on purpose: the same 4096 bytes of .interp -> each patch sees the other one as foreign bytes (state n/a), so they exclude each other
            assert excl(p1, p2) and excl(p2, p1), 'interp and tick80 must exclude each other'; continue
        if overlap(p1, p2): sys.exit('ERROR: points of %s and %s overlap' % (n1, n2))
    # and with the patches that live outside the frame: automap (gfx.txt), voice 0x71acc..+7, dusk 0x196b73
    other = [(0x71acc, bytes(7), bytes(7)), (0x196b73, bytes(1), bytes(1))]
    gt = open(a.gfx, encoding='utf-8').read()
    for m in re.finditer(r'(?m)^patch=(automap)\|[^|]+\|\d+\|(.+)$', gt):
        for pt in m.group(2).split('|'):
            o, x, _ = pt.split(':'); other.append((int(o, 16), bytes.fromhex(x), bytes.fromhex(x)))
    for n, p in (('windows', pw), ('glow', pg), ('interp', pi), ('tick80', ptk)):
        if overlap(p, other): sys.exit('ERROR: %s overlaps automap/voice/dusk' % n)
    # frame table
    fr = []
    for s, e in runs(orig + b'\0' * TAIL, F, 8, 0):
        if s >= SIZE: continue
        fr.append((s, (orig + b'\0' * TAIL)[s:e], F[s:e]))
    return orig, F, dict(frame=fr, windows=pw, glow=pg, interp=pi, tick80=ptk), alts, dict(WR=WR, WE=WE, G=G, I=I, T=T)

def verify(orig, F, tabs, alts, built):
    """all subsets x all orders on the original file == the sequential scripts; each switch-off puts the bytes back; alt label"""
    fr = tabs['frame']
    def on_(d, nm, alt=False):
        if len(d) == SIZE: d += b'\0' * TAIL; apply_pts(d, fr, True)
        apply_pts(d, tabs[nm], True, alt, alts if nm == 'windows' else None)
    def off_(d, nm):
        apply_pts(d, tabs[nm], False)
    exp = {'windows': built['WR'], 'glow': built['G'], 'interp': built['I'], 'tick80': built['T']}
    # expected result of a subset: apply the diffs of the scripts on F
    names = ['windows', 'glow', 'interp', 'tick80']; n = 0
    for k in range(1, 4):
        for sub in itertools.combinations(names, k):
            if 'interp' in sub and 'tick80' in sub: continue   # exclusive (checked in build)
            ref = bytearray(F)
            for nm in sub:   # the scripts' diffs are disjoint: composing = copying their changed runs
                for s, e in runs(F, exp[nm], 0): ref[s:e] = exp[nm][s:e]
            for order in itertools.permutations(sub):
                d = bytearray(orig)
                for nm in order: on_(d, nm)
                assert bytes(d) == bytes(ref), ('order mismatch', sub, order); n += 1
                for nm in reversed(order): off_(d, nm)   # off in reverse order, then the frame goes
                apply_pts(d, fr, False); del d[SIZE:]
                assert bytes(d) == orig, ('revert mismatch', sub, order)
    # the same on top of an exe that already has the older patches (automap/voice/dusk bytes changed) - points do not touch them (checked above)
    d = bytearray(built['WE']); apply_pts(d, tabs['windows'], False); apply_pts(d, tabs['windows'], True, True, alts); assert bytes(d) == built['WE'], 'english label table'
    d = bytearray(built['WR']); apply_pts(d, tabs['windows'], True, False, alts); assert bytes(d) == built['WR']
    # one-after-another scripts: windows -> glow -> interp built by the scripts themselves must equal the composed result
    # tick80 by the SCRIPT on top of windows+glow built by their scripts (not the composed diff): must equal the table result
    import tick80_patch as T80
    wg = bytearray(F)
    for nm in ('windows', 'glow'):
        for s, e in runs(F, exp[nm], 0): wg[s:e] = exp[nm][s:e]
    chain = T80.apply(bytes(wg), frame=True)[0]; d = bytearray(orig)
    for nm in ('windows', 'glow', 'tick80'): on_(d, nm)
    assert bytes(d) == chain, 'tick80 script on top of windows+glow != tables'
    # interp and tick80 are exclusive: with one of them in the exe the other one is "foreign" (state -1), nothing could be written over it
    assert point_state(built['I'], tabs['tick80']) == -1 and point_state(built['T'], tabs['interp']) == -1
    assert point_state(F, tabs['tick80']) == 0 and point_state(built['T'], tabs['tick80']) == 1 and point_state(bytes(orig), tabs['tick80']) == 0
    # tick80 does not touch a single byte of the frame itself (header, section table, sizes) - old exes with the frame stay recognised
    assert all(F[i] == built['T'][i] for s, e in ((0, 0x400),) for i in range(s, e)), 'tick80 changed the headers'
    print('verified: %d subset x order combinations on the original (all equal; tick80 also == the script on top of windows+glow), reverts exact, ru/en label' % n)

def lines_of(tabs, alts):
    L = []
    L.append('# Frame (PE sections .cave/.glow/.interp at fixed addresses, zero filled; generated by games/divine-divinity/tools/make_exe_patches.py). Taken in before the first of windows/glow/interp is switched on and out after the last is off.')
    L.append('patch=frame|div.exe|%d|%s|append0:%d' % (SIZE, '|'.join(fmt(tabs['frame'])), TAIL))
    L.append('# "Large windows" = big backpack (inv_patch.py --big 90 170 --max-y 0x2c5: wheel, free-place search) + trade tiles/tabs/grouping/"worn" label + sort button (id 60) and Ctrl+C + start positions of equipment/status/backpack windows (trade_patch5.py). pat~alt = russian~english label. Report docs/recon/2026-11-07_big_windows_pack.md')
    L.append('patch=windows|div.exe|%d|needs:frame|%s' % (SIZE, '|'.join(fmt(tabs['windows'], alts))))
    L.append('# Item halo: rank 3/4/5 in the backpack + coloured Alt labels (glow_patch.py; names keep the colours of the original game). Report docs/recon/2026-11-07_glow_patch.md')
    L.append('patch=glow|div.exe|%d|needs:frame|%s' % (SIZE, '|'.join(fmt(tabs['glow']))))
    L.append('# FROZEN 07.11.2026 (owner): no user path reaches patch=interp (Core.FpsEnabled = false, src/Fps.cs); kept for the lab and for taking out a test build. Camera interpolation shows artifacts, tick 80 glitches on isometric diagonals.')
    L.append('# Frame interpolation (interp_patch.py; report docs/recon/2026-11-07_interp.md): hooks in 7 places; needs gr-draw for >60 FPS')
    L.append('patch=interp|div.exe|%d|needs:frame|%s' % (SIZE, '|'.join(fmt(tabs['interp']))))
    L.append('# Tick 80 (tick80_patch.py --frame; report docs/recon/2026-11-07_tick80.md section 5 and docs/RESEARCH_LOG.md): the world still steps 40 times a second, agents and the camera are shown at 80. Code/data in the first 4096 bytes of .interp (the same bytes as interp: the two exclude each other), agent table (ids < 16384) in the virtual tail of .interp. Since v3.6 also world objects (fire, torches, lamps, item twinkle, doors) at 20 fps = 1 frame per 2 world ticks (hook 0x582E04), as in smooth 0 the clips were drawn for. Needs gr-draw (maxgameticks=-1) and config.div smooth 1. Switched by Core.SetFps80')
    L.append('patch=tick80|div.exe|%d|needs:frame|%s' % (SIZE, '|'.join(fmt(tabs['tick80']))))
    return L

def check_gfx(tabs, alts, gfx):
    """the patch= lines of gfx.txt must be exactly what the scripts produce now (guards against a changed script and an old table)"""
    t = open(gfx, encoding='utf-8').read().replace('\r\n', '\n'); bad = 0
    for ln in lines_of(tabs, alts):
        if ln.startswith('patch='):
            if ln not in t.split('\n'): print('MISMATCH:', ln[:60]); bad += 1
    print('gfx.txt patch tables %s the scripts' % ('DIFFER from' if bad else 'match'))
    return 1 if bad else 0

def write_gfx(tabs, alts, gfx, orig, F, built):
    raw = open(gfx, encoding='utf-8', newline='').read(); crlf = '\r\n' in raw; text = raw.replace('\r\n', '\n')
    text = re.sub(r'(?m)^# (Frame \(PE sections|"Big backpack"|"Large windows"|Frame interpolation|Item halo|Frame of|Tick 80|FROZEN 07\.11\.2026).*\n', '', text)
    text = re.sub(r'(?m)^patch=(bag|interp|frame|windows|glow|tick80)\|.*\n', '', text)
    text = text.rstrip('\n') + '\n'
    L = lines_of(tabs, alts)
    # keep the legacy line and the data lines (written by make_windows_sets.py / make_interp_patch.py) after ours
    text += '\n' + '\n'.join(L) + '\n'
    open(gfx, 'w', encoding='utf-8', newline='').write(text.replace('\n', '\r\n') if crlf else text)
    print('gfx.txt updated:', gfx)
    for nm, key in (('windows(ru)', 'WR'), ('glow', 'G'), ('interp', 'I'), ('tick80', 'T')): print('  full exe sha256 %-12s %s' % (nm, hashlib.sha256(built[key]).hexdigest()))

def main(av):
    ap = argparse.ArgumentParser()
    ap.add_argument('--orig', default=os.path.join(ROOT, 'scratch', 're', 'div.exe')); ap.add_argument('--work', default=os.path.join(ROOT, 'scratch', 'wp'))
    ap.add_argument('--gfx', default=os.path.join(ROOT, 'games', 'divine-divinity', 'gfx', 'gfx.txt'))
    ap.add_argument('--write', action='store_true'); ap.add_argument('--no-verify', action='store_true'); ap.add_argument('--unicorn', action='store_true', help='also run the Unicorn self-test of tick80_patch.py on the frame variant'); ap.add_argument('--check', action='store_true', help='fail if gfx.txt differs from what the scripts produce')
    a = ap.parse_args(av)
    orig, F, tabs, alts, built = build(a)
    if not a.no_verify: verify(orig, F, tabs, alts, built)
    if a.unicorn:
        import tick80_patch as T80
        res = T80.selftest(os.path.join(a.work, 'tick80.exe')); ok = sum(1 for l in res if l.endswith('-> OK')); bad = [l for l in res if l.endswith('-> FAIL')]
        print('tick80 Unicorn self-test (frame layout): %d OK, %d FAIL' % (ok, len(bad)))
        if bad: sys.exit('FAILED: ' + bad[0])
    if a.write: write_gfx(tabs, alts, a.gfx, orig, F, built)
    if a.check: return check_gfx(tabs, alts, a.gfx)
    return 0

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
