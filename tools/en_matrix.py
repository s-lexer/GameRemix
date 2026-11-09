# Matrix check of every GameRemix variant on a COPY of the Steam (English) Divine Divinity. Never touches the Steam folder or the owner's copies.
#   python tools/en_matrix.py [GAMEDIR] [--run]   (--run: also start the game for ~20 s per exe variant and watch error.txt)
# Needs: dist/build/GameRemix.exe, dist/assets/divine-divinity (sets are served from a local loopback server, like tools/selftest.py).
# Result: scratch/en_env/matrix.json + a table on stdout. Report: docs/recon/2026-11-07_steam_en_check.md
import os, sys, io, json, time, hashlib, shutil, subprocess, importlib.util, re, concurrent.futures as cf
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
GAME = next((a for a in sys.argv[1:] if not a.startswith('--')), os.path.join(r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity', 'steam_en_test'))
RUN = '--run' in sys.argv
STEAM = r'C:\Program Files (x86)\Steam\steamapps\common\divine_divinity'
EXE = os.path.join(ROOT, 'dist', 'build', 'GameRemix.exe')
E = os.path.join(ROOT, 'scratch', 'en_env')
spec = importlib.util.spec_from_file_location('st', os.path.join(ROOT, 'tools', 'selftest.py')); st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)
srv = st.make_srv_class(os.path.join(ROOT, 'dist'))()
ENV = dict(os.environ, OGF_DATA=os.path.join(E, 'data'), OGF_DESKTOP=os.path.join(E, 'desk'), OGF_CACHE=os.path.join(E, 'cache'), OGF_LOCAL=os.path.join(E, 'local'),
           OGF_ASSETS_URL='http://127.0.0.1:%d/assets/divine-divinity/' % srv.port, OGF_TEST_NOGUARD='1')
for k in ('data', 'desk', 'cache', 'local'): os.makedirs(os.path.join(E, k), exist_ok=True)
VOLATILE = ('init.cfg', 'sinfo.000', 'error.txt', 'mapids.000', 'dynamic' + os.sep)   # the game rewrites these on every start

def cli(*args):
    log = os.path.join(E, 'cli.log')
    if os.path.exists(log): os.remove(log)
    r = subprocess.run([EXE, '--game', GAME] + list(args) + ['--log', log], env=ENV, cwd=E, capture_output=True, timeout=1500)
    return r.returncode, (open(log, encoding='utf-8-sig').read() if os.path.exists(log) else '')

def sha(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
def snap():
    fs = []
    for dp, _, ns in os.walk(GAME):
        for n in ns:
            p = os.path.join(dp, n); r = os.path.relpath(p, GAME)
            if r.startswith(VOLATILE): continue
            fs.append((r, p))
    with cf.ThreadPoolExecutor(8) as ex: return {r: (os.path.getsize(p), h) for (r, p), h in zip(fs, ex.map(lambda t: sha(t[1]), fs))}
def diff(a, b):
    ch = sorted(k for k in a if k in b and a[k] != b[k]); new = sorted(k for k in b if k not in a); gone = sorted(k for k in a if k not in b)
    return ch, new, gone
def status_lines(txt, keys=('GFX-WINPACK', 'GFX-FIX', 'STATUS')): return [l for l in txt.splitlines() if l.startswith(keys)]

def play(secs=20):
    r = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'tools', 'run_game_probe.py'), GAME, str(secs)], capture_output=True, timeout=secs + 60)
    return r.stdout.decode('utf-8', 'replace').strip()

RES = []
def record(name, **kw): kw['name'] = name; RES.append(kw); print(json.dumps(kw, ensure_ascii=False)[:900], flush=True)

base = snap(); print('baseline files:', len(base), flush=True)
exe0 = open(os.path.join(GAME, 'div.exe'), 'rb').read()
def exe_diff(): 
    e = open(os.path.join(GAME, 'div.exe'), 'rb').read()
    return len(e), (sum(1 for i in range(min(len(e), len(exe0))) if e[i] != exe0[i]) if len(e) else -1)

def variant(name, apply_args, revert_args, run=False, expect_fail=False, pre=None):
    t0 = time.time(); outs = []; rc_all = 0
    if pre: pre()
    for a in apply_args:
        rc, txt = cli(*a); rc_all |= rc; outs.append(txt)
    last = outs[-1] if outs else ''
    st_ = status_lines(cli('--gfx', 'status')[1])
    ch, new, gone = diff(base, snap())
    elen, ebytes = exe_diff()
    game = play() if (run and RUN) else None
    rb_rc = 0
    for a in revert_args:
        rc, txt = cli(*a); rb_rc |= rc
    ch2, new2, gone2 = diff(base, snap())
    errs = [l for t in outs for l in t.splitlines() if l.startswith(('ERROR', 'GFX-PROBLEM', 'GFX-FAILED', 'WARN'))]
    record(name, apply_rc=rc_all, errors=errs[:4], changed=[(c, base[c][0]) for c in ch][:12], new=new[:8], exe_len=elen, exe_bytes_changed=ebytes,
           status=[s[:260] for s in st_ if s.startswith(('GFX-WINPACK', 'GFX-FIX id=glow', 'GFX-FIX id=automap', 'STATUS'))][:4], game=game,
           revert_rc=rb_rc, revert_identical=(not ch2 and not new2 and not gone2), revert_left=(ch2[:6], new2[:6], gone2[:6]), sec=round(time.time() - t0))

REV_ALL = [('--gfx', 'revert'), ('--voice', 'off', '--dusk', 'off')]
if __name__ == '__main__':
    only = [a[7:] for a in sys.argv if a.startswith('--only=')]
    V = [
        ('list+status (read only)', [('--gfx', 'list')], [], False),
        ('voice+music', [('--voice', 'on')], [('--voice', 'off')], True),
        ('dusk', [('--dusk', 'on')], [('--dusk', 'off')], True),
        ('automap', [('--gfx', 'apply', 'automap=on')], [('--gfx', 'apply', 'automap=off')], True),
        ('glow', [('--gfx', 'apply', 'glow=on')], [('--gfx', 'apply', 'glow=off')], True),
        ('windows ui=orig', [('--gfx', 'apply', 'bag=big')], [('--gfx', 'apply', 'bag=orig')], True),
        ('windows+glow', [('--gfx', 'apply', 'bag=big,glow=on')], [('--gfx', 'revert')], True),
        ('ui=c', [('--gfx', 'apply', 'ui=c')], [('--gfx', 'revert')], False),
        ('ui=e', [('--gfx', 'apply', 'ui=e')], [('--gfx', 'revert')], False),
        ('ui=a', [('--gfx', 'apply', 'ui=a')], [('--gfx', 'revert')], False),
        ('items=hd', [('--gfx', 'apply', 'items=hd')], [('--gfx', 'revert')], False),
        ('items=redrawn', [('--gfx', 'apply', 'items=redrawn')], [('--gfx', 'revert')], False),
        ('ui=c + bag=big', [('--gfx', 'apply', 'ui=c,bag=big')], [('--gfx', 'revert')], True),
        ('ui=e + bag=big', [('--gfx', 'apply', 'ui=e,bag=big')], [('--gfx', 'revert')], True),
        ('pic=v2', [('--gfx', 'apply', 'pic=v2')], [('--gfx', 'revert')], False),
    ]
    for n, ap, rv, run in V:
        if only and not any(o in n for o in only): continue
        variant(n, ap, rv, run)
    json.dump(RES, open(os.path.join(E, 'matrix.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
