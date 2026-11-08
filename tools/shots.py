# Renders every window of the program (RU and EN) from a COPY of the game into docs/test-results/shots_<date>/ ; read-only (--shot never saves anything).
#   python tools/shots.py [outdir]
import os, sys, subprocess, shutil, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest as T
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(T.ROOT, 'docs', 'test-results', 'shots_' + datetime.date.today().strftime('%Y-%m-%d'))
os.makedirs(out, exist_ok=True)
G = os.path.join(T.ROOT, 'scratch', 'shotgame')
for d in (T.DATA, T.DESK, T.CACHE): os.makedirs(d, exist_ok=True)
T.mkgame(G)
subprocess.run([T.EXE, '--game', G, '--voice', 'on', '--dusk', 'on', '--cnc', 'on', '--launcher', 'on', '--log', os.path.join(out, 'prep.log')], env=T.ENV)
screens = ['fix', 'sec', 'tools', 'req', 'picker', 'about', 'changelog', 'choose', 'quick', 'cnc', 'fonts', 'feedback', 'version', 'dgvq', 'help', 'helpc', 'article']
for lang in ('ru', 'en'):
    for sc in screens:
        f = os.path.join(out, '%s_%s.png' % (sc, lang))
        args = [T.EXE, '--shot', sc, f, G] + (['--en'] if lang == 'en' else [])
        subprocess.run(args, env=T.ENV, timeout=60)
        print(sc, lang, os.path.exists(f))
# a low screen: the main window scrolls instead of being cut
env = dict(T.ENV, OGF_WORKAREA='1366x728')
subprocess.run([T.EXE, '--shot', 'fix', os.path.join(out, 'fix_lowscreen_ru.png'), G], env=env, timeout=60)
# folder not available (saved path of an unplugged drive): ask for a missing path through --open
subprocess.run([T.EXE, '--shot', 'fix', os.path.join(out, 'fix_missing_ru.png'), r'Q:\GAMES\Divine Divinity'], env=T.ENV, timeout=60)
subprocess.run([T.EXE, '--shot', 'fix', os.path.join(out, 'fix_missing_en.png'), r'Q:\GAMES\Divine Divinity', '--en'], env=T.ENV, timeout=60)
