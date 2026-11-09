# "Large windows" (patch=windows + data edits) on the Steam English copy: what exactly ends up in the files, and that the revert is byte-exact.
#   python tools/en_check_windows.py [GAMEDIR]      (default C:/ARM/WORK/MODDING/GAMES/DivineDivinity/steam_en_test; a COPY - never the Steam folder)
import os, sys, io, re, struct, hashlib, subprocess
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
G = next((a for a in sys.argv[1:] if not a.startswith('--')), os.path.join(r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity', 'steam_en_test'))
sys.path.insert(0, os.path.join(ROOT, 'games', 'divine-divinity', 'tools')); sys.path.insert(0, os.path.join(ROOT, 'games', 'divine-divinity', 'analysis'))
import textcmp, voicecmp
E = os.path.join(ROOT, 'scratch', 'en_env'); EXE = os.path.join(ROOT, 'dist', 'build', 'GameRemix.exe')
import importlib.util
spec = importlib.util.spec_from_file_location('st', os.path.join(ROOT, 'tools', 'selftest.py')); st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)
srv = st.make_srv_class(os.path.join(ROOT, 'dist'))()
ENV = dict(os.environ, OGF_ASSETS_URL='http://127.0.0.1:%d/assets/divine-divinity/' % srv.port, OGF_DATA=os.path.join(E, 'data'), OGF_DESKTOP=os.path.join(E, 'desk'), OGF_CACHE=os.path.join(E, 'cache'), OGF_LOCAL=os.path.join(E, 'local'), OGF_TEST_NOGUARD='1')
def cli(*a):
    log = os.path.join(E, 'cw.log')
    if os.path.exists(log): os.remove(log)
    r = subprocess.run([EXE, '--game', G] + list(a) + ['--log', log], env=ENV, cwd=E, capture_output=True, timeout=600)
    return r.returncode, open(log, encoding='utf-8-sig').read() if os.path.exists(log) else ''
def md5(p): return hashlib.md5(open(p, 'rb').read()).hexdigest()
FILES = ['div.exe', 'dat/global.cmp', 'dat/statuspl.cmp', 'dat/flat.cmp', 'localizations/english/text.cmp', 'static/imagelists/CPackedb.8c', 'static/imagelists/CPackedi.8c']
before = {f: md5(os.path.join(G, f)) for f in FILES}
out = []
def say(s): print(s); out.append(s)
# the windows kit alone has no sprites (sets are separate); the exe + data edits are what the Gfx page switches via the patch table
rc, txt = cli('--gfx', 'apply', 'bag=big')
say('apply bag=big (windows-orig set + exe patch + data edits): rc=%d' % rc)
for l in txt.splitlines():
    if l.startswith(('GFX-PLAN', 'GFX-PROBLEM', 'GFX-RESULT', 'ERROR', 'GFX-WINPACK')): say('  ' + l[:300])
exe = open(os.path.join(G, 'div.exe'), 'rb').read(); say('div.exe length %d' % len(exe))
if len(exe) > 0x259000:
    say('  label @0x259000 (worn): %r' % exe[0x259000:0x259000 + 26])
    say('  tab names @0x259100: %r' % exe[0x259100:0x259100 + 18])
g = os.path.join(G, 'dat', 'global.cmp'); idx = voicecmp.read_index(g); ent = [(s, o, z) for s, o, z in idx if 'statuspl' in s]
data = open(g, 'rb').read(); say('global.cmp entry %s: %s' % (ent, hashlib.sha256(data[ent[0][1]:ent[0][1] + ent[0][2]]).hexdigest()[:12]))
say('global.cmp size unchanged: %s' % (os.path.getsize(g) == 1810801))
sa = open(os.path.join(G, 'dat', 'statuspl.cmp'), 'rb').read(); say('standalone dat/statuspl.cmp untouched (sha %s): the game takes the entry inside global.cmp (see docs/recon/2026-11-07_stats_window.md)' % hashlib.sha256(sa).hexdigest()[:12])
t = dict(((tid, k), s1) for tid, recs in textcmp.read(os.path.join(G, 'localizations', 'english', 'text.cmp')) for k, s1, s2 in recs)
say('text.cmp 10000/772 = %r' % t.get((10000, 772)))
rc, txt = cli('--gfx', 'apply', 'bag=orig')
after = {f: md5(os.path.join(G, f)) for f in FILES}
say('revert rc=%d, files identical to the Steam originals: %s' % (rc, {f: before[f] == after[f] for f in FILES}))
open(os.path.join(E, 'check_windows.txt'), 'w', encoding='utf-8').write('\n'.join(out))
