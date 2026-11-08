# python tools/en_apply.py GAMEDIR <GameRemix CLI args...>   - runs the CLI on a COPY with sets served from dist/assets over loopback (like en_matrix.py)
import os, sys, subprocess, importlib.util
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); E = os.path.join(ROOT, 'scratch', 'en_env')
spec = importlib.util.spec_from_file_location('st', os.path.join(ROOT, 'tools', 'selftest.py')); st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)
srv = st.make_srv_class(os.path.join(ROOT, 'dist'))()
env = dict(os.environ, OGF_ASSETS_URL='http://127.0.0.1:%d/assets/divine-divinity/' % srv.port, OGF_DATA=os.path.join(E, 'data'), OGF_DESKTOP=os.path.join(E, 'desk'), OGF_CACHE=os.path.join(E, 'cache'), OGF_LOCAL=os.path.join(E, 'local'), OGF_TEST_NOGUARD='1')
log = os.path.join(E, 'apply.log')
r = subprocess.run([os.path.join(ROOT, 'dist', 'managed', 'GameRemix.exe'), '--game', sys.argv[1]] + sys.argv[2:] + ['--log', log], env=env, cwd=E)
print('rc', r.returncode); print(open(log, encoding='utf-8-sig').read()[:3000])
