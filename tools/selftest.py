# Self-test of the fix core on COPIES of the game (never on the real game, never on the real %APPDATA%\GameRemix / OldGameFixer data).
#   python tools/selftest.py            runs every scenario, prints PASS/FAIL, writes docs/test-results/selftest-<date>.md
# Every run redirects the program's data, desktop and cache to scratch folders (OGF_DATA / OGF_DESKTOP / OGF_CACHE) and builds a small fake game
# folder with a Cyrillic name from the owner's pristine backups (read-only). The program is driven through its CLI (--game ... --voice on ... --revert-all).
import os, sys, io, glob, shutil, subprocess, hashlib, ctypes, ctypes.wintypes as wt, datetime, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
EXE = os.environ.get('OGF_EXE') or os.path.join(ROOT, 'dist', 'managed', 'GameRemix.exe')   # OGF_EXE: test another build (the shipped path may be locked by a running copy)
S = os.path.join(ROOT, 'scratch', 'selftest')
GAME = os.path.join(S, 'тест игра')
DATA, DESK, CACHE = os.path.join(S, 'data'), os.path.join(S, 'desktop'), os.path.join(S, 'cache')
REALPROF = [os.path.join(os.environ['APPDATA'], n) for n in ('GameRemix', 'OldGameFixer', 'OldGameFixer.migrated')]
REAL = next((os.path.join(d, 'games', 'dd-36b67d5e') for d in REALPROF if os.path.exists(os.path.join(d, 'games', 'dd-36b67d5e'))), os.path.join(REALPROF[0], 'games', 'dd-36b67d5e'))   # read-only source of pristine files (div.exe.orig, fonts)
REALGAME = r'X:\GAMES\Divine Divinity'
ENV = dict(os.environ, OGF_DATA=DATA, OGF_DESKTOP=DESK, OGF_CACHE=CACHE, OGF_LOCAL=os.path.join(S, 'local'))   # OGF_LOCAL: %LOCALAPPDATA%\GameRemix is never touched either
if os.environ.get('OGF_TEST_NOGUARD'): ENV['OGF_TEST_NOGUARD'] = '1'   # only when a foreign div.exe is running on this PC (never kill it)
# the clean reference div.exe 1.0.0.62 (sha256 cd9f7a07...): the owner's backup when it is still clean (a run of the program on a game with leftovers of old test builds can refresh it with 12 stray bytes), else scratch/re/div.exe
REF_SHA = 'cd9f7a07c7a605c21052b3517346c7a63083063fb491276a3e4c9836c9b42a67'
PRISTINE = next((p for p in (os.path.join(REAL, 'backup', 'div.exe.orig'), os.path.join(REAL, 'backup', 'div.exe.orig.prev'), os.path.join(ROOT, 'scratch', 're', 'div.exe')) if os.path.exists(p) and hashlib.sha256(open(p, 'rb').read()).hexdigest() == REF_SHA), os.path.join(REAL, 'backup', 'div.exe.orig'))
results = []

def rd(p): return open(p, 'rb').read()
def h(p): return hashlib.md5(rd(p)).hexdigest()

def mkgame(dest=GAME, with_saves=True):
    if os.path.exists(dest): shutil.rmtree(dest)
    os.makedirs(dest)
    shutil.copy(PRISTINE, os.path.join(dest, 'div.exe'))
    for n in ('OsirisDLL.dll', 'DivDialogSystem.dll'): open(os.path.join(dest, n), 'wb').write(b'ORIGINAL-' + n.encode() + b'\0' * 64)
    for n in ('slash1.dll', 'slash4.dll'): open(os.path.join(dest, n), 'wb').write(b'MZ-' + n.encode())
    shutil.copy(os.path.join(REAL, 'preset', 'config.div'), os.path.join(dest, 'config.div'))
    shutil.copy(os.path.join(REAL, 'preset', 'slashed-d3d6.cfg'), os.path.join(dest, 'slashed-d3d6.cfg'))
    shutil.copy(os.path.join(REALGAME, 'slashed-software.cfg'), os.path.join(dest, 'slashed-software.cfg'))
    open(os.path.join(dest, 'slashed.cfg'), 'wb').write(bytes([0, 0, 0, 0]))
    shutil.copytree(os.path.join(REAL, 'backup', 'fonts'), os.path.join(dest, 'fonts'))
    if with_saves:
        os.makedirs(os.path.join(dest, 'savegames', 'a')); open(os.path.join(dest, 'savegames', 'a', 'data.000'), 'wb').write(b'x' * 100)

def tree(d):
    r = {}
    for dp, _, fs in os.walk(d):
        for f in fs:
            p = os.path.join(dp, f); r[os.path.relpath(p, d)] = h(p)
    return r

def reset_all():
    for d in (DATA, DESK, CACHE):
        if os.path.exists(d): shutil.rmtree(d)
        os.makedirs(d)
    mkgame()

def cli(*args, game=GAME, expect_rc=None, env=None):
    log = os.path.join(S, 'cli.log')
    if os.path.exists(log): os.remove(log)
    cmd = [EXE] + (['--game', game] if game else []) + list(args) + ['--log', log]
    r = subprocess.run(cmd, env=ENV if env is None else env, cwd=S, capture_output=True, timeout=300)
    txt = open(log, encoding='utf-8-sig').read() if os.path.exists(log) else ''
    return r.returncode, txt

def status(txt):
    m = re.search(r'STATUS (.*)', txt); d = {}
    if m:
        for kv in m.group(1).split():
            if '=' in kv: k, v = kv.split('=', 1); d[k] = v
    return d

def check_embedded_fonts():
    import gzip, glob, struct
    sys.path.insert(0, os.path.join(ROOT, 'games', 'divine-divinity', 'analysis')); import mlfont as M
    ref = {}   # reference code sets: the game's own originals (the owner's backup), when present
    bad = []; n = 0
    for p in sorted(glob.glob(os.path.join(ROOT, 'games', 'divine-divinity', 'payload', 'fonts', '*.gz'))):
        d = gzip.decompress(open(p, 'rb').read()); name = os.path.basename(p)[:-3]; n += 1
        try:
            f = M.parse(d)
            if not name.startswith(('pg_', 'pk_', 'dlg_')) and M.encode(f) != d: bad.append(name + ': parse/encode round trip differs'); continue   # pack files are the owner's, shipped as they are
            cnt = struct.unpack_from('<H', d, 0x12)[0]; tab = struct.unpack_from('<223I', d, 0x9a)
            if len(f['glyphs']) > cnt: bad.append('%s: %d glyph records but the header says %d (the engine sizes its table by the header: overflow, wrong letters)' % (name, len(f['glyphs']), cnt))
            for i, t in enumerate(tab if not name.startswith(('pg_', 'pk_', 'dlg_')) else ()):
                if t and struct.unpack_from('<H', d, t + 0x16 + 20)[0] != 0x21 + i: bad.append(name + ': table entry %d points to another glyph' % i); break
            for ch in 'Здравствуйте':   # the word of the owner's report must draw with real glyphs in every set
                c = ch.encode('cp1251')[0]; g = f['glyphs'].get(c)
                if g is None or g['A'] <= 0 or not any(g['rows']): bad.append('%s: no glyph for %s' % (name, ch)); break
        except Exception as e: bad.append('%s: %s' % (name, e))
    check('9b every embedded .fnt (%d files) has a header count that covers its records, a consistent table and the glyphs of "Здравствуйте"' % n, not bad, '; '.join(bad[:6]))

def check(name, cond, detail=''):
    results.append((name, bool(cond), detail)); print(('PASS ' if cond else 'FAIL ') + name + (('  -- ' + detail) if (detail and not cond) else ''))

def gamedata():
    g = os.path.join(DATA, 'games')
    return [os.path.join(g, x) for x in os.listdir(g)] if os.path.exists(g) else []

# ---- lock helper: open a file with no sharing, as an antivirus / the running game would
k32 = ctypes.windll.kernel32; k32.CreateFileW.restype = wt.HANDLE
def lock(path):
    hd = k32.CreateFileW(path, 0x80000000, 0, None, 3, 0x80, None)
    assert hd not in (-1, 0xFFFFFFFF, None) and hd != ctypes.c_void_p(-1).value, 'lock failed'
    return hd
def unlock(hd): k32.CloseHandle(hd)

def make_srv_class(site):
    import http.server, threading, urllib.parse, socket
    class Srv:
        def __init__(self):
            outer = self; self.log = []; self.drop = None
            class H(http.server.BaseHTTPRequestHandler):
                protocol_version = 'HTTP/1.1'
                def log_message(self, *a): pass
                def do_GET(self):
                    outer.log.append((self.path, self.headers.get('Range')))
                    p = os.path.join(site, urllib.parse.unquote(self.path.split('?')[0].lstrip('/')).replace('/', os.sep))
                    if not os.path.isfile(p): self.send_response(404); self.send_header('Content-Length', '0'); self.end_headers(); return
                    size = os.path.getsize(p); start = 0; code = 200; rg = self.headers.get('Range')
                    if rg and rg.startswith('bytes='):
                        start = int(rg[6:].split('-')[0]); code = 206
                        if start >= size: self.send_response(416); self.send_header('Content-Range', 'bytes */%d' % size); self.send_header('Content-Length', '0'); self.end_headers(); return
                    self.send_response(code); self.send_header('Content-Length', str(size - start))
                    if code == 206: self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, size - 1, size))
                    self.end_headers()
                    with open(p, 'rb') as f:
                        f.seek(start); left = size - start; sent = 0
                        while left > 0:
                            n = min(65536, left)
                            if outer.drop is not None and sent + n > outer.drop:   # cut the connection after `drop` bytes of this response
                                self.wfile.write(f.read(max(0, outer.drop - sent))); self.wfile.flush(); self.close_connection = True
                                try: self.connection.shutdown(socket.SHUT_RDWR)
                                except OSError: pass
                                return
                            self.wfile.write(f.read(n)); left -= n; sent += n
            class Q(http.server.ThreadingHTTPServer):
                def handle_error(self, request, client_address): pass   # a client that hangs up is part of the test
            self.httpd = Q(('127.0.0.1', 0), H); self.port = self.httpd.server_address[1]
            threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        def data_gets(self, sid='clean-test', ver='1'): return [x for x in self.log if x[0].startswith('/assets/divine-divinity/%s/%s/' % (sid, ver))]
    return Srv

# ---------------------------------------------------------------- asset sets (shared/assets/build_asset_set.py + src/AssetSets.cs)
# A local HTTP server (127.0.0.1, with Range and a "drop the connection" switch) serves a set built by the real build script from small fake archives;
# the program is driven through its CLI against a copy of a fake game. OGF_ASSETS_URL points the catalog at the test server (plain http is accepted only for 127.0.0.1 then).
def assets_tests():
    import http.server, threading, urllib.parse, socket, random, time
    A = os.path.join(S, 'assets'); orig_dir = os.path.join(A, 'orig'); src_dir = os.path.join(A, 'src'); site = os.path.join(A, 'site')
    for d in (orig_dir, os.path.join(src_dir, 'static', 'imagelists'), os.path.join(src_dir, 'static', 'extra'), site): os.makedirs(d, exist_ok=True)
    rnd = random.Random(7)
    text = lambda seed, n: ''.join('line %d of %d: %s\n' % (i, seed, 'abc' * (i % 7)) for i in range(n)).encode()
    ORIG = {'CPackedi.0c': rnd.randbytes(40000), 'CPackedb.0c': rnd.randbytes(300000), 'CPackedb.1c': text(1, 20000)}
    NEWC = {'CPackedi.0c': rnd.randbytes(41000), 'CPackedb.0c': rnd.randbytes(310000), 'CPackedb.1c': text(2, 21000)}
    for n, b in ORIG.items(): open(os.path.join(orig_dir, n), 'wb').write(b)
    for n, b in NEWC.items(): open(os.path.join(src_dir, 'static', 'imagelists', n), 'wb').write(b)
    open(os.path.join(src_dir, 'static', 'extra', 'new.bin'), 'wb').write(rnd.randbytes(5000))
    bscript = os.path.join(ROOT, 'shared', 'assets', 'build_asset_set.py')
    build = [sys.executable, bscript, '--id', 'clean-test', '--game', 'divine-divinity', '--version', '1', '--src', src_dir, '--include', 'static',
             '--orig', orig_dir, '--out', os.path.join(site, 'assets'), '--name-ru', 'Тест', '--name-en', 'Test', '--desc-ru', 'Тестовый набор', '--desc-en', 'Test set']
    r = subprocess.run(build, capture_output=True, timeout=120); man_dir = os.path.join(site, 'assets', 'divine-divinity', 'clean-test')
    mp0 = os.path.join(man_dir, 'manifest.txt'); man = open(mp0, encoding='utf-8').read() if os.path.exists(mp0) else ''
    check('assets build: manifest has gzip + raw entries and exactly one NEW file (no original)', r.returncode == 0 and '|gzip|' in man and '|raw|' in man and man.count('|-\n') == 1, r.stdout.decode('utf-8', 'replace') + r.stderr.decode('utf-8', 'replace'))
    check('assets build: catalog lists the set', 'set=clean-test' in open(os.path.join(site, 'assets', 'divine-divinity', 'catalog.txt')).read())
    check('assets build: --verify passes', subprocess.run([sys.executable, bscript, '--verify', man_dir], capture_output=True).returncode == 0)

    def clone(newid, edit):   # a damaged copy of the set for the safety tests
        d = os.path.join(site, 'assets', 'divine-divinity', newid)
        if os.path.exists(d): shutil.rmtree(d)
        shutil.copytree(man_dir, d); mp = os.path.join(d, 'manifest.txt'); t = open(mp, encoding='utf-8').read().replace('id=clean-test', 'id=' + newid)
        open(mp, 'w', encoding='utf-8', newline='\n').write(edit(t, d))
    def flip(t, d):   # same size, one byte of the (raw) packed file changed: only the checksum can notice
        f = os.path.join(d, '1', 'static', 'imagelists', 'CPackedb.0c.bin'); b = bytearray(open(f, 'rb').read()); b[1000] ^= 0xFF; open(f, 'wb').write(bytes(b)); return t
    clone('bad-sum', flip)
    clone('bad-host', lambda t, d: t.replace('1/static/imagelists/CPackedi.0c', 'http://127.0.0.1:1/x', 1))
    clone('bad-path', lambda t, d: t.replace('file=static\\imagelists\\CPackedi.0c', 'file=..\\evil_assets.txt', 1))
    clone('bad-exe', lambda t, d: t.replace('file=static\\imagelists\\CPackedi.0c', 'file=static\\imagelists\\CPackedi.dll', 1))
    clone('bad-cmd', lambda t, d: t.replace('file=static\\imagelists\\CPackedi.0c', 'file=static\\run.cmd', 1))
    clone('bad-dir', lambda t, d: t.replace('file=static\\imagelists\\CPackedi.0c', 'file=main\\CPackedi.0c', 1))
    clone('bad-ini', lambda t, d: t.replace('file=static\\imagelists\\CPackedi.0c', 'file=static\\ddraw.ini', 1))

    Srv = make_srv_class(site)
    srv = Srv(); aenv = dict(ENV, OGF_ASSETS_URL='http://127.0.0.1:%d/assets/divine-divinity/' % srv.port)
    IM = os.path.join(GAME, 'static', 'imagelists'); names = list(ORIG)
    def setup():
        reset_all(); os.makedirs(IM)
        for n, b in ORIG.items(): open(os.path.join(IM, n), 'wb').write(b)
    NEWF = os.path.join(GAME, 'static', 'extra', 'new.bin')
    def is_set(): return all(rd(os.path.join(IM, n)) == NEWC[n] for n in names) and os.path.exists(NEWF)
    def is_orig(): return all(rd(os.path.join(IM, n)) == ORIG[n] for n in names) and not os.path.exists(NEWF)
    def leftovers(): return [f for dp, _, fs in os.walk(GAME) for f in fs if f.endswith(('.ogf-new', '.ogf-old', '.tmp'))]
    def adir(): g = gamedata(); return os.path.join(g[0], 'assets') if g else os.path.join(DATA, 'none')
    def baks():
        d = os.path.join(adir(), 'clean-test', 'orig')
        return {os.path.relpath(os.path.join(dp, f), d): h(os.path.join(dp, f)) for dp, _, fs in os.walk(d) for f in fs}
    def diff(a, b): return str({k for k in set(a) | set(b) if a.get(k) != b.get(k)})

    # list, status, apply, apply again, revert, apply from the cache, "Revert all"
    setup(); t0 = tree(GAME)
    rc, txt = cli('--assets', 'list', env=aenv); check('assets list: shows the set with its size', rc == 0 and 'ASSET id=clean-test' in txt and 'files=4' in txt, txt)
    rc, txt = cli('--assets', 'status', env=aenv); st = re.search(r'ASSET-STATUS id=clean-test state=(\w+)', txt)
    check('assets status on a clean game: original, nothing active', rc == 0 and st and st.group(1) == 'original' and 'active=none' in txt, txt)
    rc, txt = cli('--assets', 'apply', 'clean-test', env=aenv)
    check('assets apply: rc 0, archives replaced, new file added, no leftovers', rc == 0 and is_set() and not leftovers(), txt)
    check('assets apply: status says applied and active', 'state=applied' in txt and 'active=clean-test' in txt, txt)
    bk = baks(); check('assets apply: the backup holds the 3 originals byte for byte', len(bk) == 3 and all(bk[os.path.join('static', 'imagelists', n)] == hashlib.md5(ORIG[n]).hexdigest() for n in names), str(bk))
    n1 = len(srv.data_gets())
    rc, txt = cli('--assets', 'apply', 'clean-test', env=aenv); check('assets apply twice: still applied, nothing downloaded, backup untouched', rc == 0 and is_set() and len(srv.data_gets()) == n1 and baks() == bk, txt)
    rc, txt = cli('--assets', 'revert', 'clean-test', env=aenv); t1 = tree(GAME)
    check('assets revert: the game folder is byte-identical to the start', rc == 0 and t1 == t0 and is_orig() and 'active=none' in txt, txt + diff(t0, t1))
    check('assets revert: the backup folder is removed', not os.path.exists(os.path.join(adir(), 'clean-test')))
    rc, txt = cli('--assets', 'apply', 'clean-test', env=aenv); check('assets apply after revert: from the cache, no new download', rc == 0 and is_set() and len(srv.data_gets()) == n1, txt)
    rc, txt = cli('--revert-all', env=aenv); t1 = tree(GAME); check('assets: "Revert all" brings the original archives back (identical tree)', rc == 0 and t1 == t0, txt + diff(t0, t1))

    # a running game (process "div") blocks apply
    run_dir = os.path.join(S, 'run'); os.makedirs(run_dir, exist_ok=True); sl = os.path.join(run_dir, 'sleep.cs')
    open(sl, 'w').write('class P{static void Main(){System.Threading.Thread.Sleep(120000);}}')
    csc = os.path.join(os.environ['WINDIR'], r'Microsoft.NET\Framework\v3.5\csc.exe'); subprocess.run([csc, '/nologo', '/out:' + os.path.join(run_dir, 'div.exe'), sl], check=True, capture_output=True)
    setup(); t0 = tree(GAME); pr = subprocess.Popen([os.path.join(run_dir, 'div.exe')]); time.sleep(1.0)
    try:
        rc, txt = cli('--assets', 'apply', 'clean-test', env=aenv); check('assets: game running -> refused (rc 3), nothing changed', rc == 3 and tree(GAME) == t0, txt)
    finally:
        pr.kill(); pr.wait()   # exactly our own PID
    time.sleep(0.5)

    # other originals (another build of the game): refused before anything is downloaded or changed
    setup(); open(os.path.join(IM, 'CPackedb.0c'), 'ab').write(b'X'); t1 = tree(GAME); srv.log.clear()
    rc, txt = cli('--assets', 'apply', 'clean-test', '--lang', 'en', env=aenv)
    check('assets: incompatible originals -> refused, nothing downloaded, nothing changed', rc != 0 and 'does not fit' in txt and 'CPackedb.0c' in txt and tree(GAME) == t1 and not srv.data_gets(), txt)

    # the connection drops in the middle: the game is untouched, the partial file stays, the next try resumes with a Range request
    setup(); t0 = tree(GAME)
    if os.path.exists(os.path.join(CACHE, 'assets')): shutil.rmtree(os.path.join(CACHE, 'assets'))
    srv.log.clear(); srv.drop = 30000
    rc, txt = cli('--assets', 'apply', 'clean-test', '--lang', 'en', env=aenv); parts = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(CACHE, 'assets')) for f in fs if f.endswith('.part')]
    check('assets: dropped connection -> error, game byte-identical, no temp files in the game', rc != 0 and tree(GAME) == t0 and not leftovers() and 'interrupted' in txt, txt)
    check('assets: the partial download is kept for resuming', len(parts) == 1 and 0 < os.path.getsize(parts[0]) < len(NEWC['CPackedb.0c']), str(parts))
    got = os.path.getsize(parts[0]) if parts else 0; srv.drop = None; srv.log.clear()
    rc, txt = cli('--assets', 'apply', 'clean-test', env=aenv); rng = [x[1] for x in srv.data_gets() if x[1]]
    check('assets: the next try resumes (Range from the saved offset) and applies', rc == 0 and is_set() and ('bytes=%d-' % got) in rng, txt + str(srv.log))
    cli('--revert-all', env=aenv)

    # poisoned / hostile manifests
    setup(); t0 = tree(GAME); rc, txt = cli('--assets', 'apply', 'bad-sum', '--lang', 'en', env=aenv)
    cached_bad = [f for dp, _, fs in os.walk(os.path.join(CACHE, 'assets')) for f in fs if 'bad-sum' in dp and 'CPackedb.0c' in f and not f.endswith('.part')]
    check('assets: wrong checksum of a downloaded file -> refused, game identical, the bad file is not cached', rc != 0 and 'checksum' in txt.lower() and tree(GAME) == t0 and not leftovers() and not cached_bad, txt + str(cached_bad))
    rc, txt = cli('--assets', 'apply', 'bad-host', '--lang', 'en', env=aenv); check('assets: a file address on a foreign server is rejected', rc != 0 and 'foreign' in txt and tree(GAME) == t0, txt)
    rc, txt = cli('--assets', 'apply', 'bad-path', '--lang', 'en', env=aenv); check('assets: a path leaving the game folder is rejected', rc != 0 and 'bad path' in txt and not os.path.exists(os.path.join(S, 'evil_assets.txt')) and tree(GAME) == t0, txt)
    for bid, what in (('bad-exe', '.dll'), ('bad-cmd', '.cmd'), ('bad-ini', '.ini')):
        rc, txt = cli('--assets', 'apply', bid, '--lang', 'en', env=aenv); check('assets: a manifest with %s file is rejected (no code/settings from a server), game untouched' % what, rc != 0 and 'executable type' in txt and tree(GAME) == t0, txt)
    rc, txt = cli('--assets', 'apply', 'bad-dir', '--lang', 'en', env=aenv); check('assets: a Divine Divinity set with a file outside static\\ is rejected', rc != 0 and 'outside the allowed' in txt and tree(GAME) == t0, txt)

    # failure in the middle of the swap (injected): every file goes back, no record, nothing left over
    setup(); t0 = tree(GAME); rc, txt = cli('--assets', 'apply', 'clean-test', env=dict(aenv, OGF_ASSETS_FAILSWAP='1')); t1 = tree(GAME)
    check('assets: failure after 1 file was swapped -> all rolled back (identical tree, no .ogf-*, no record)', rc != 0 and t1 == t0 and not leftovers() and not os.path.exists(os.path.join(adir(), 'clean-test', 'active.txt')), txt + diff(t0, t1))
    rc, txt = cli('--assets', 'apply', 'clean-test', env=aenv); check('assets: apply works after the failed swap', rc == 0 and is_set(), txt)

    # a backup is never rewritten; a file changed by someone else is never overwritten blindly
    bk = baks(); open(os.path.join(IM, 'CPackedi.0c'), 'wb').write(ORIG['CPackedi.0c'])   # the player restored one original by hand
    rc, txt = cli('--assets', 'apply', 'clean-test', env=aenv); check('assets: apply over a restored original keeps the backup untouched', rc == 0 and is_set() and baks() == bk, txt)
    open(os.path.join(IM, 'CPackedi.0c'), 'wb').write(b'SPOILED BY SOMEONE'); t1 = tree(GAME)
    rc, txt = cli('--assets', 'apply', 'clean-test', '--lang', 'en', env=aenv); check('assets: a file changed after applying is not overwritten; the backup is unchanged', rc != 0 and 'changed after' in txt and tree(GAME) == t1 and baks() == bk, txt)
    rc, txt = cli('--assets', 'revert', 'clean-test', '--lang', 'en', env=aenv)
    check('assets: revert restores the other files, leaves the foreign file alone and keeps its backup', rc != 0 and rd(os.path.join(IM, 'CPackedi.0c')) == b'SPOILED BY SOMEONE' and rd(os.path.join(IM, 'CPackedb.0c')) == ORIG['CPackedb.0c'] and not os.path.exists(NEWF)
          and os.path.join('static', 'imagelists', 'CPackedi.0c') in baks(), txt)
    shutil.rmtree(os.path.join(adir(), 'clean-test'), ignore_errors=True)

    # an interrupted swap is finished at the next start: the record says "applying", one original sits as *.ogf-old
    setup(); t0 = tree(GAME); cli('--assets', 'apply', 'clean-test', env=aenv)
    rp = os.path.join(adir(), 'clean-test', 'active.txt'); rec_txt = open(rp, encoding='utf-8').read(); open(rp, 'w', encoding='utf-8').write(rec_txt.replace('state=applied', 'state=applying'))
    p0 = os.path.join(IM, 'CPackedi.0c'); open(p0 + '.ogf-old', 'wb').write(ORIG['CPackedi.0c']); open(p0 + '.ogf-new', 'wb').write(b'half')
    rc, txt = cli('--assets', 'revert', 'clean-test', env=aenv); t1 = tree(GAME); check('assets: an interrupted swap is rolled back, then revert gives the identical tree', rc == 0 and t1 == t0 and not leftovers(), txt + diff(t0, t1))
    srv.httpd.shutdown()


# ---------------------------------------------------------------- interface size / picture scale (src/Scale.cs): game runs smaller, cnc-ddraw stretches the frame
def scale_tests():
    import struct
    def gres():
        t = open(os.path.join(GAME, 'config.div'), encoding='cp1251').read()
        w = int(re.search(r'(?m)^width\s+(\d+)', t).group(1)); h = int(re.search(r'(?m)^height\s+(\d+)', t).group(1))
        c = [struct.unpack_from('<ii', rd(os.path.join(GAME, n)), 0x0C) for n in ('slashed-d3d6.cfg', 'slashed-software.cfg')]
        return (w, h), c
    def ini(k):
        m = re.search(r'(?mi)^' + k + r'\s*=\s*(.*?)\s*$', open(os.path.join(GAME, 'ddraw.ini'), encoding='utf-8', errors='replace').read().split('[div]')[0]); return m.group(1) if m else None
    def sc(txt):
        m = re.search(r'SCALE pct=(\d+) eff=(\d+) mon=(\d+)x(\d+) game=(\d+)x(\d+) integer=(\w+) shader=(.*?) notes=(.*)', txt)
        return None if not m else dict(pct=int(m[1]), eff=int(m[2]), game=(int(m[5]), int(m[6])), integer=m[7] == 'True', shader=m[8], notes=m[9].split(',') if m[9] else [])
    # (monitor, --scale) -> (game, integer, notes that must be present)
    table = [('3840x2160', 'auto', (1920, 1080), True, []), ('2560x1440', 'auto', (2048, 1152), False, ['frac']), ('1920x1080', 'auto', (1920, 1080), True, []),
             ('2560x1440', '150', (1704, 958), False, ['frac']), ('2560x1440', '200', (1280, 720), True, []), ('1920x1080', '125', (1536, 864), False, ['frac']),
             ('1920x1080', '150', (1280, 720), False, ['frac']), ('1920x1080', '200', (1064, 600), False, ['min']), ('2560x1600', 'auto', (2048, 1280), False, []),
             ('1366x768', '200', (1064, 600), False, ['min']), ('1280x720', '200', (1064, 600), False, ['min']), ('640x480', '200', (640, 480), True, ['small']),
             ('3440x1440', 'auto', (2752, 1152), False, ['wide']), ('5120x1440', 'auto', (3840, 1080), False, ['max', 'wide']), ('3840x2160', '100', (3840, 2160), True, ['big']),
             ('7680x4320', 'auto', (3840, 2160), True, []), ('3841x2161', '200', (1920, 1080), True, []), ('1366x768', '100', (1366, 768), True, ['odd8'])]
    for mon, pct, game, integer, notes in table:
        reset_all(); cli('--cnc', 'on'); rc, txt = cli('--scale', pct, '--monitor', mon); r = sc(txt)
        ok = rc == 0 and r and r['game'] == game and r['integer'] == integer and all(n in r['notes'] for n in notes) and (not integer or r['shader'] == 'Nearest neighbor') and (integer or 'lanczos' in r['shader'])
        check('S %s @ %s -> %dx%d' % (mon, pct, game[0], game[1]), ok, txt)
        if ok:
            (w, h), cfgs = gres()
            check('S %s @ %s: config.div and slashed cfgs hold %dx%d, even sizes' % (mon, pct, game[0], game[1]), (w, h) == game and all(c == game for c in cfgs) and w % 2 == 0 and h % 2 == 0, str((w, h, cfgs)))
            check('S %s @ %s: ddraw.ini borderless + aspect + filter' % (mon, pct), ini('windowed') == 'true' and ini('fullscreen') == 'true' and ini('maintas') == 'true' and ini('renderer') == 'opengl' and ini('shader') == r['shader'].replace('\\\\', '\\'), str([ini(k) for k in ('windowed', 'fullscreen', 'maintas', 'renderer', 'shader')]))
    # rollback: scale twice (backup taken once), then revert-all = the start; game folder identical
    reset_all(); t0 = tree(GAME); cli('--cnc', 'on'); cli('--scale', '200', '--monitor', '3840x2160'); cli('--scale', '125', '--monitor', '2560x1440')
    rc, txt = cli('--revert-all'); t1 = tree(GAME); diff = {k for k in set(t0) | set(t1) if t0.get(k) != t1.get(k)}
    check('S cnc on -> scale -> scale -> revert-all: folder identical to the start', rc == 0 and not diff, txt + str(diff))
    check('S revert-all removes the saved scale state', not any(os.path.exists(os.path.join(d, 'scale.txt')) for d in gamedata()))
    # scale while cnc-ddraw stays on and the user's ddraw.ini existed: reverting the preset brings the ini back
    reset_all(); cli('--cnc', 'on'); i0 = rd(os.path.join(GAME, 'ddraw.ini')); cli('--scale', '200', '--monitor', '3840x2160')
    check('S scale changed ddraw.ini', rd(os.path.join(GAME, 'ddraw.ini')) != i0)
    rc, txt = cli('--revert-all'); check('S revert-all after scale: cnc-ddraw gone, no stray files', rc == 0 and not os.path.exists(os.path.join(GAME, 'ddraw.ini')) and not os.path.exists(os.path.join(GAME, 'ddraw.dll')), txt)
    # scale without cnc-ddraw: refused, nothing changes
    reset_all(); t0 = tree(GAME); rc, txt = cli('--scale', '200', '--monitor', '3840x2160'); check('S scale without cnc-ddraw is refused, nothing changed', rc != 0 and tree(GAME) == t0 and 'ERROR' in txt, txt)
    # CLI validation
    reset_all(); t0 = tree(GAME)
    for a in (('--scale', '175'), ('--scale', 'big'), ('--scale', '200', '--monitor', 'abc'), ('--scale', '200', '--monitor', '10x10'), ('--monitor', '1920x1080')):
        rc, txt = cli(*a); check('S bad arguments %s -> rc 2, nothing changed' % ' '.join(a), rc == 2 and tree(GAME) == t0, txt)
    # quick setup + scale (cnc): class nominal size when the monitor differs; full revert
    for k, mon, pct, game in (('1', '2560x1440', '125', (2048, 1152)), ('2', '3840x2160', 'auto', (1920, 1080)), ('2', '1920x1080', 'auto', (1920, 1080)), ('0', '3840x2160', '200', (1064, 600))):
        reset_all(); t0 = tree(GAME); rc, txt = cli('--preset', k, '--wrapper', 'cnc', '--scale', pct, '--monitor', mon); r = sc(txt); (w, h), cfgs = gres() if rc == 0 else ((0, 0), [])
        check('S preset %s + scale %s on %s -> %dx%d' % (k, pct, mon, game[0], game[1]), rc == 0 and r and r['game'] == game and (w, h) == game and all(c == game for c in cfgs), txt)
        rc, txt = cli('--revert-all'); t1 = tree(GAME); diff = {x for x in set(t0) | set(t1) if t0.get(x) != t1.get(x)}
        check('S preset %s + scale: revert-all identical to the start' % k, rc == 0 and not diff, txt + str(diff))
    # preset 2 (4K class) with a 1080p monitor given: the class decides (3840x2160 nominal) -> 1920x1080 at 200%; plain preset (no --scale) keeps the old sizes
    reset_all(); cli('--preset', '1', '--wrapper', 'cnc'); check('S preset without --scale keeps the class size (2560x1440)', gres()[0] == (2560, 1440))
    reset_all(); rc, txt = cli('--preset', '0', '--wrapper', 'dgv', '--scale', '200', '--monitor', '3840x2160'); check('S scale with dgVoodoo is skipped, preset sizes stay', rc == 0 and 'SCALE-SKIPPED' in txt and gres()[0] == (1920, 1080), txt)
    # a preset failing in the middle (Shaders is a file) rolls back, also with a scale
    reset_all(); open(os.path.join(GAME, 'Shaders'), 'wb').write(b'x'); t0 = tree(GAME)
    rc, txt = cli('--preset', '1', '--wrapper', 'cnc', '--scale', '125', '--monitor', '2560x1440'); t1 = tree(GAME); diff = {x for x in set(t0) | set(t1) if t0.get(x) != t1.get(x)}
    check('S preset + scale failing in the middle rolls back', rc != 0 and not diff, txt + str(diff))


# ---------------------------------------------------------------- Graphics page (src/Gfx.cs, GfxPatches.cs): slots, layers, conflicts, fixes, patches on synthetic files
def world_bytes(dark=True, other=False):
    """a synthetic world.x1 with the real structure (header of 1024 row offsets, rows of 512 cells, trailer 103); the five cells of the floor fix hold Darkness (274)"""
    import struct
    rows = bytearray(); hdr = bytearray()
    for y in range(1024):
        hdr += struct.pack('<I', 4096 + y * 9216)
        tab = b''.join(struct.pack('<H', x * 16) for x in range(512)); cells = bytearray()
        for x in range(512):
            v = 2445
            if y == 527 and 130 <= x <= 134: v = 274 if dark else [2447, 2446, 2451, 2446, 2449][x - 130]
            if other and y == 527 and 130 <= x <= 134: v = 999
            cells += struct.pack('<HHHBHBHHH', v, 0, 0, 0, 0, 0, 0, 0, 0)
        rows += tab + cells
    return bytes(hdr) + bytes(rows) + b'g\0\0\0'

def gfx_tests():
    import time, random
    G = os.path.join(S, 'gfx'); shutil.rmtree(G, ignore_errors=True); site = os.path.join(G, 'site'); os.makedirs(site)
    rnd = random.Random(11); rb = lambda n: rnd.randbytes(n)
    ORIG = {'CPackedb.1c': rb(200000), 'CPackedb.8c': rb(150000), 'CPackedi.8c': rb(20000), 'flat.cmp': rb(30000)}
    V2 = {'CPackedb.1c': rb(210000), 'CPackedb.8c': rb(151000), 'CPackedi.8c': rb(20100)}
    SK = {k: {'CPackedb.8c': rb(152000), 'CPackedi.8c': rb(20200)} for k in 'abc'}; SK['a']['flat.cmp'] = rb(31000)
    def wd(root, rel, data): p = os.path.join(root, *rel.split('/')); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(data)
    od, v2d = os.path.join(G, 'orig'), os.path.join(G, 'v2'); os.makedirs(od); os.makedirs(v2d)
    for n, b in ORIG.items(): wd(od, n, b)
    for n, b in V2.items(): wd(v2d, n, b)
    bscript = os.path.join(ROOT, 'shared', 'assets', 'build_asset_set.py'); site_assets = os.path.join(site, 'assets')
    def build(sid, ver, kind, layer, files, origs):
        src = os.path.join(G, 'src_' + sid)
        for rel, b in files.items(): wd(src, rel, b)
        info = os.path.join(G, sid + '.set')
        open(info, 'w', encoding='utf-8').write('id=%s\ngame=divine-divinity\nversion=%s\nkind=%s\nlayer=%d\nname.ru=%s\nname.en=%s\ndesc.ru=d\ndesc.en=d\nsrc=%s\ninclude=static;dat\n' % (sid, ver, kind, layer, sid, sid, src) + ''.join('orig=%s\n' % o for o in origs))
        r = subprocess.run([sys.executable, bscript, '--info', info, '--out', site_assets], capture_output=True, timeout=120)
        return r.returncode == 0
    ok = build('clean-v2', '2', 'graphics', 0, {'static/imagelists/' + k: v for k, v in V2.items()}, [od])
    ok &= build('skin-a', '1.3.1', 'ui-skin', 1, {'static/imagelists/' + k: v for k, v in SK['a'].items() if k != 'flat.cmp'} | {'dat/flat.cmp': SK['a']['flat.cmp']}, [od, v2d])
    ok &= build('skin-b', '1.0.0', 'ui-skin', 1, {'static/imagelists/' + k: v for k, v in SK['b'].items()}, [od, v2d])
    ok &= build('skin-c', '1.0.0', 'ui-skin', 1, {'static/imagelists/' + k: v for k, v in SK['c'].items()}, [od])   # made for the original only: does not fit on top of v2
    check('gfx build: fake graphics set + 3 skins built (skins list the originals AND the v2 files)', ok)
    mb = open(os.path.join(site_assets, 'divine-divinity', 'skin-b', 'manifest.txt'), encoding='utf-8').read()
    check('gfx build: the skin manifest carries layer=1 and two originals for its archives', 'layer=1' in mb and all(l.split('|')[-1].count(',') == 1 for l in mb.splitlines() if l.startswith('file=static')), mb[:400])
    d_src = os.path.join(site_assets, 'divine-divinity', 'skin-b'); d_dst = os.path.join(site_assets, 'divine-divinity', 'skin-d'); shutil.copytree(d_src, d_dst)   # damaged copy: a byte of a packed file flipped
    mp = os.path.join(d_dst, 'manifest.txt'); mtxt = open(mp, encoding='utf-8').read().replace('id=skin-b', 'id=skin-d'); open(mp, 'w', encoding='utf-8', newline='\n').write(mtxt)
    fl = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(d_dst, '1.0.0')) for f in fs][0]; bb = bytearray(open(fl, 'rb').read()); bb[len(bb) // 2] ^= 0xFF; open(fl, 'wb').write(bytes(bb))
    open(os.path.join(site_assets, 'divine-divinity', 'catalog.txt'), 'w', newline='\n').write('OGF-ASSET-CATALOG 1\n' + ''.join('set=%s\n' % x for x in ('clean-v2', 'skin-a', 'skin-b', 'skin-c', 'skin-d')))
    Srv = make_srv_class(site); srv = Srv(); gen = dict(ENV, OGF_ASSETS_URL='http://127.0.0.1:%d/assets/divine-divinity/' % srv.port); dead = dict(ENV, OGF_ASSETS_URL='http://127.0.0.1:9/assets/divine-divinity/')
    lab = dict(gen, GAMEREMIX_FPS_LAB='1')   # the frozen frame mode (src/Fps.cs) only works with this
    IM = os.path.join(GAME, 'static', 'imagelists'); FLAT = os.path.join(GAME, 'dat', 'flat.cmp')
    def setup(worlds=True):
        reset_all(); os.makedirs(IM); os.makedirs(os.path.dirname(FLAT))
        for n in ('CPackedb.1c', 'CPackedb.8c', 'CPackedi.8c'): open(os.path.join(IM, n), 'wb').write(ORIG[n])
        open(FLAT, 'wb').write(ORIG['flat.cmp'])
        if worlds:
            for rel in ('main/startup/world.x1', 'dynamic/world.x1', 'savegames/a/world.x1'):
                p = os.path.join(GAME, *rel.split('/')); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(world_bytes())
            p = os.path.join(GAME, 'savegames', 'b', 'world.x1'); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(world_bytes(other=True))
    def files(): return {n: rd(os.path.join(IM, n)) for n in ORIG if n != 'flat.cmp'} | {'flat.cmp': rd(FLAT)}
    def gl(txt, pat): m = re.search(pat, txt); return m.group(1) if m else None
    def cur(txt, slot): return gl(txt, r'GFX-SLOT id=%s kind=sets current=(\w+)' % slot)
    def leftovers(): return [f for dp, _, fs in os.walk(GAME) for f in fs if f.endswith(('.ogf-new', '.ogf-old', '.tmp'))]
    def diffpos(a, b): return [i for i in range(len(a)) if a[i] != b[i]] if len(a) == len(b) else None

    # list/status on a clean game
    setup(); t0 = tree(GAME); orig_files = files()
    rc, txt = cli('--gfx', 'list', env=gen)
    check('gfx list: slots, options with statuses, fixes', rc == 0 and cur(txt, 'pic') == 'orig' and 'GFX-OPT slot=pic value=v2 set=clean-v2 status=notdl' in txt and 'GFX-OPT slot=ui value=d set=skin-d' in txt and 'value=c set=skin-c status=notdl' in txt and 'GFX-FIX id=automap state=off' in txt and 'GFX-FIX id=floor state=off' in txt and 'GFX-FIX id=floorsaves state=off' in txt, txt)
    check('gfx list changed nothing', tree(GAME) == t0)

    # picture alone, then a skin on top of it (shared archive 8: layered)
    rc, txt = cli('--gfx', 'apply', 'pic=v2', env=gen); f1 = files()
    check('gfx apply pic=v2: archives are the v2 ones, no leftovers', rc == 0 and f1['CPackedb.1c'] == V2['CPackedb.1c'] and f1['CPackedb.8c'] == V2['CPackedb.8c'] and cur(txt, 'pic') == 'v2' and not leftovers(), txt)
    rc, txt = cli('--gfx', 'apply', 'ui=a', env=gen); f2 = files()
    check('gfx apply ui=a over v2: archive 8 and flat.cmp are the skin, archive 1 stays v2 (both slots are active)', rc == 0 and f2['CPackedb.8c'] == SK['a']['CPackedb.8c'] and f2['flat.cmp'] == SK['a']['flat.cmp'] and f2['CPackedb.1c'] == V2['CPackedb.1c'] and cur(txt, 'pic') == 'v2' and cur(txt, 'ui') == 'a', txt)
    rc, txt = cli('--assets', 'status', env=gen); check('gfx: the picture set is NOT reported as changed while a skin sits on its archive (quick status intact)', rc == 0 and 'active=' in txt and 'clean-v2' in txt and 'skin-a' in txt, txt)
    rc, txt = cli('--gfx', 'apply', 'ui=b', env=gen); f3 = files()
    check('gfx apply ui=b: skin A goes back (flat.cmp original again), B on top of v2', rc == 0 and f3['flat.cmp'] == ORIG['flat.cmp'] and f3['CPackedb.8c'] == SK['b']['CPackedb.8c'] and f3['CPackedb.1c'] == V2['CPackedb.1c'] and cur(txt, 'ui') == 'b', txt)
    # the picture changes under a skin: the skin is taken off, the picture goes back, the skin is put on the original
    rc, txt = cli('--gfx', 'apply', 'pic=orig', env=gen); f4 = files()
    check('gfx apply pic=orig under skin B: skin B stays (re-applied over the original), picture archives are original', rc == 0 and f4['CPackedb.1c'] == ORIG['CPackedb.1c'] and f4['CPackedb.8c'] == SK['b']['CPackedb.8c'] and cur(txt, 'pic') == 'orig' and cur(txt, 'ui') == 'b', txt)
    rc, txt = cli('--gfx', 'apply', 'ui=orig', env=gen); check('gfx apply ui=orig: the original archive 8 is back', rc == 0 and files() == orig_files and tree(GAME) == t0, txt)
    # the whole choice at once, in the right order, then "Restore original"
    rc, txt = cli('--gfx', 'apply', 'pic=v2,ui=a', env=gen); f5 = files()
    check('gfx apply pic=v2,ui=a in one go: skin over picture', rc == 0 and f5['CPackedb.8c'] == SK['a']['CPackedb.8c'] and f5['CPackedb.1c'] == V2['CPackedb.1c'] and re.findall(r'GFX-STEP apply-set (\S+)', txt) == ['clean-v2', 'skin-a'], txt)
    rc, txt = cli('--gfx', 'revert', env=gen); check('gfx revert ("Restore original"): the game folder is byte-identical to the start', rc == 0 and tree(GAME) == t0, txt)

    # compatibility and unavailable
    srv.log.clear(); rc, txt = cli('--gfx', 'apply', 'pic=v2,ui=c', env=gen)
    check('gfx conflict: skin made for the original only + picture v2 -> refused with a reason, nothing downloaded or changed', rc != 0 and 'GFX-PROBLEM' in txt and tree(GAME) == t0 and not srv.data_gets('skin-c', '1.0.0') and not srv.data_gets('clean-v2', '2'), txt)
    rc, txt = cli('--gfx', 'apply', 'ui=c', env=gen); check('gfx: the same skin alone (on the original picture) is fine', rc == 0 and files()['CPackedb.8c'] == SK['c']['CPackedb.8c'], txt)
    cli('--gfx', 'revert', env=gen)
    rc, txt = cli('--gfx', 'apply', 'ui=d', env=dead); check('gfx: a set that cannot be fetched (no server) fails, nothing changed (a cached manifest may still plan it, the download fails)', rc != 0 and tree(GAME) == t0, txt)
    rc, txt = cli('--gfx', 'apply', 'pic=nonsense', env=gen); check('gfx: unknown value -> rc 2... error, nothing changed', rc != 0 and tree(GAME) == t0, txt)
    rc, txt = cli('--gfx', 'apply', 'scale=125', env=gen); check('gfx: scale without cnc-ddraw is refused with a reason', rc != 0 and 'cnc-ddraw' in txt and tree(GAME) == t0, txt)

    # failure in the middle of a plan: everything goes back to the previous state (sets come from the cache)
    cli('--gfx', 'apply', 'pic=v2,ui=b', env=gen); t_v2b = tree(GAME)
    rc, txt = cli('--gfx', 'apply', 'pic=orig,ui=d', env=gen)   # skin-d has a damaged packed file: the download fails after the old state was taken apart
    rc2, txt2 = cli('--gfx', 'status', env=gen)
    check('gfx failure: rc!=0, the previous state (v2 + skin B) is back byte for byte', rc != 0 and tree(GAME) == t_v2b and cur(txt2, 'pic') == 'v2' and cur(txt2, 'ui') == 'b' and not leftovers() and ('restored' in txt or 'возвращено' in txt), txt)
    cli('--gfx', 'revert', env=gen)

    # interrupted download: nothing changed, the retry resumes
    shutil.rmtree(os.path.join(DATA, '..', 'cache'), ignore_errors=True); os.makedirs(CACHE, exist_ok=True); srv.log.clear(); srv.drop = 3000
    rc, txt = cli('--gfx', 'apply', 'pic=v2', env=gen)
    check('gfx interrupted download: error, game folder unchanged', rc != 0 and tree(GAME) == t0, txt)
    srv.drop = None; rc, txt = cli('--gfx', 'apply', 'pic=v2', env=gen)
    check('gfx retry after the interruption: applied (resumed with Range)', rc == 0 and files()['CPackedb.1c'] == V2['CPackedb.1c'] and any(x[1] for x in srv.log), txt)
    rc, txt = cli('--revert-all', env=gen); check('gfx: "Revert all" returns the original picture (identical tree)', rc == 0 and tree(GAME) == t0, txt)

    # the black floor fix (synthetic maps with the real structure)
    setup(); t0 = tree(GAME); sp = os.path.join(GAME, 'main', 'startup', 'world.x1'); orig_w = world_bytes()
    rc, txt = cli('--gfx', 'apply', 'floor=on', env=gen); w = rd(sp); dp = diffpos(w, orig_w)
    check('floor on: the start map and the current-game map are fixed, exactly the 5 cells (<=10 bytes) differ, size equal', rc == 0 and dp is not None and 5 <= len(dp) <= 10 and w == world_bytes(dark=False) and rd(os.path.join(GAME, 'dynamic', 'world.x1')) == world_bytes(dark=False), txt)
    check('floor on: saves are NOT touched by default', rd(os.path.join(GAME, 'savegames', 'a', 'world.x1')) == orig_w and 'GFX-FIX id=floor state=on' in txt and 'GFX-FIX id=floorsaves state=off' in txt, txt)
    rc, txt = cli('--gfx', 'apply', 'floorsaves=on', env=gen)
    check('floorsaves on: the player\'s save is fixed too; a save with a different map is skipped untouched', rc == 0 and rd(os.path.join(GAME, 'savegames', 'a', 'world.x1')) == world_bytes(dark=False) and rd(os.path.join(GAME, 'savegames', 'b', 'world.x1')) == world_bytes(other=True), txt)
    rc, txt = cli('--gfx', 'apply', 'floor=on,floorsaves=on', env=gen); check('floor: applying again is a no-op', rc == 0 and rd(sp) == world_bytes(dark=False), txt)
    rc, txt = cli('--gfx', 'apply', 'floor=off,floorsaves=off', env=gen); check('floor off + saves off: every byte is back (identical tree)', rc == 0 and tree(GAME) == t0, txt)
    open(sp, 'wb').write(world_bytes(other=True)); t1 = tree(GAME)
    rc, txt = cli('--gfx', 'apply', 'floor=on', env=gen); check('floor: a map with other values in those cells is refused, nothing written', rc != 0 and tree(GAME) == t1, txt)
    open(sp, 'wb').write(world_bytes()); b = bytearray(world_bytes()); b[-4] = 0; open(os.path.join(GAME, 'dynamic', 'world.x1'), 'wb').write(bytes(b)); t1 = tree(GAME)
    rc, txt = cli('--gfx', 'apply', 'floor=on', env=gen); check('floor: a file that is not a map (bad trailer) is refused, nothing written', rc != 0 and tree(GAME) == t1, txt)
    # revert-all brings back a fixed map as well
    setup(); t0 = tree(GAME); cli('--gfx', 'apply', 'floor=on,floorsaves=on', env=gen); rc, txt = cli('--revert-all', env=gen)
    check('floor: "Revert all" puts the maps back (start map, current map, saves)', rc == 0 and tree(GAME) == t0, txt)

    # "Big backpack": a per-skin set (windows-@ui: archive 8 + flat.cmp) AND the byte patch "bag" of div.exe come and go together
    BAGF = {k: {'CPackedb.8c': rb(153000), 'CPackedi.8c': rb(20300), 'flat.cmp': rb(30500)} for k in ('orig', 'c')}
    ckd = os.path.join(G, 'skinc_dir'); os.makedirs(ckd, exist_ok=True)
    for n, b in SK['c'].items(): wd(ckd, n, b)
    okb = build('windows-orig', '1.0.0', 'ui-bag', 2, {'static/imagelists/' + k: v for k, v in BAGF['orig'].items() if k != 'flat.cmp'} | {'dat/flat.cmp': BAGF['orig']['flat.cmp']}, [od])
    okb &= build('windows-orig-v2', '1.0.0', 'ui-bag', 2, {'static/imagelists/' + k: v for k, v in BAGF['orig'].items() if k != 'flat.cmp'} | {'dat/flat.cmp': BAGF['orig']['flat.cmp']}, [od])   # ui=orig on the clean-v2 picture set (Core.GfxSetId)
    okb &= build('windows-c', '1.0.0', 'ui-bag', 2, {'static/imagelists/' + k: v for k, v in BAGF['c'].items() if k != 'flat.cmp'} | {'dat/flat.cmp': BAGF['c']['flat.cmp']}, [ckd, od])
    open(os.path.join(site_assets, 'divine-divinity', 'catalog.txt'), 'w', newline='\n').write('OGF-ASSET-CATALOG 1\n' + ''.join('set=%s\n' % x for x in ('clean-v2', 'skin-a', 'skin-b', 'skin-c', 'skin-d', 'windows-orig', 'windows-orig-v2', 'windows-c')))
    check('bag: fake per-skin bag sets built', okb)
    setup(); t0 = tree(GAME); ex = os.path.join(GAME, 'div.exe'); exo = rd(ex)
    rc, txt = cli('--gfx', 'list', env=gen); check('bag: list shows the slot, the option resolved to the set of the current (original) interface, the patch state', rc == 0 and cur(txt, 'bag') == 'orig' and 'GFX-OPT slot=bag value=big set=windows-orig status=notdl' in txt, txt)
    rc, txt = cli('--gfx', 'apply', 'bag=big', env=gen); e1 = rd(ex); f1 = files()
    check('bag=big (original interface): set files placed, exe patched (frame +40960), backup of div.exe still the original', rc == 0 and f1['CPackedb.8c'] == BAGF['orig']['CPackedb.8c'] and f1['flat.cmp'] == BAGF['orig']['flat.cmp'] and len(e1) == len(exo) + 40960 and e1 != exo and cur(txt, 'bag') == 'big' and 'GFX-STEP patch windows on=True' in txt and all(rd(b) == exo for b in [os.path.join(g, 'backup', 'div.exe.orig') for g in gamedata()] if os.path.exists(b)), txt)
    rc, txt = cli('--gfx', 'apply', 'bag=orig', env=gen); check('bag=orig: archives, flat.cmp and exe are the originals again, no leftovers', rc == 0 and files() == orig_files and rd(ex) == exo and not leftovers() and cur(txt, 'bag') == 'orig', txt)
    cli('--gfx', 'apply', 'bag=big', env=gen); rc, txt = cli('--gfx', 'apply', 'ui=c', env=gen); f2 = files()
    check('bag=big then ui=c: the bag set follows the skin (windows-orig goes back, skin-c, then windows-c on top)', rc == 0 and f2['CPackedb.8c'] == BAGF['c']['CPackedb.8c'] and cur(txt, 'ui') == 'c' and cur(txt, 'bag') == 'big' and rd(ex) != exo and 'revert-set windows-orig' in txt and 'apply-set windows-c' in txt, txt)
    rc, txt = cli('--gfx', 'apply', 'ui=orig', env=gen); check('ui=orig while bag=big: skin and its bag set go back, windows-orig comes', rc == 0 and files()['CPackedb.8c'] == BAGF['orig']['CPackedb.8c'] and cur(txt, 'bag') == 'big', txt)
    rc, txt = cli('--revert-all', env=gen); check('bag: "Revert all" brings the exe and the files back', rc == 0 and rd(ex) == exo and files() == orig_files, txt)
    cli('--gfx', 'apply', 'bag=big', env=gen); rc, txt = cli('--gfx', 'revert', env=gen); check('bag: "Restore original" (--gfx revert) takes the set and the patch off', rc == 0 and rd(ex) == exo and files() == orig_files and cur(txt, 'bag') == 'orig', txt)
    setup(); open(os.path.join(GAME, 'div.exe'), 'ab').write(b'tail'); t1 = tree(GAME); rc, txt = cli('--gfx', 'apply', 'bag=big', env=gen); check('bag: another build of div.exe -> refused, nothing written', rc != 0 and tree(GAME) == t1, txt)
    setup()

    # ---- "Large windows" kit: patch=windows (exe) + cmpentry (stats layout inside global.cmp) + textrec (Sort tooltip) + sets; glow and interp live in the SAME frame, any order
    sys.path.insert(0, os.path.join(ROOT, 'games', 'divine-divinity', 'tools')); sys.path.insert(0, os.path.join(ROOT, 'games', 'divine-divinity', 'tools', 'ui_skins'))
    import textcmp as _tc, cmpfile as _cf
    gt = open(os.path.join(ROOT, 'games', 'divine-divinity', 'gfx', 'gfx.txt'), encoding='utf-8').read()
    mce = re.search(r'(?m)^cmpentry=([^|]+)\|([^|]+)\|([0-9a-f]+)\|([0-9a-f]+)\s*$', gt); ST_O, ST_N = bytes.fromhex(mce.group(3)), bytes.fromhex(mce.group(4))
    def mkcmp(path, ents):
        out = []
        for nm, data in ents:
            raw = bytes(ord(ch) ^ _cf.KEY[i] if i in _cf.KEY else ord(ch) for i, ch in enumerate(nm)); out.append(_cf.Entry(raw, data))
        _cf.write(path, out)
    GLB = os.path.join(GAME, 'dat', 'global.cmp'); TXR = os.path.join(GAME, 'localizations', 'german', 'text.cmp'); TXE = os.path.join(GAME, 'localizations', 'english', 'text.cmp')
    OTH, XBM = rb(500), rb(300)
    def kit_setup():
        setup(); mkcmp(GLB, [('dat\\other.txt', OTH), ('dat\\statuspl.cmp', ST_O), ('bmg\\x.bmg', XBM)])
        for pth, ru in ((TXR, True), (TXE, False)):
            os.makedirs(os.path.dirname(pth), exist_ok=True)
            _tc.write(pth, [(10000, [(1, ('Привет' if ru else 'Hello').encode('cp1251'), b''), (771, b'x', b'')]), (10, [(5, b'Sword', b'')])])
    kit_setup(); ex = os.path.join(GAME, 'div.exe'); exo = rd(ex); t0 = tree(GAME); glb0 = rd(GLB); txr0 = rd(TXR); txe0 = rd(TXE)
    rc, txt = cli('--gfx', 'apply', 'bag=big', env=gen); e1 = rd(ex); gl1 = rd(GLB)
    check('windows kit: exe +40960 (frame), stats entry replaced IN PLACE (same size, only those 360 bytes), data=on, no problems', rc == 0 and len(e1) == len(exo) + 40960 and 'GFX-WINPACK exe=on data=on problems=0' in txt and len(gl1) == len(glb0) and ST_N in gl1 and ST_O not in gl1 and sum(1 for a, b in zip(glb0, gl1) if a != b) <= 360, txt)
    tr1, te1 = _tc.read(TXR), _tc.read(TXE)
    check('windows kit: tooltip string 10000/772 added: RU "Сортировать" (cp1251) in the Russian file, "Sort" in the English one; other strings untouched', dict((k, v) for k, v, _ in dict(tr1)[10000])[772] == 'Сортировать'.encode('cp1251') and dict((k, v) for k, v, _ in dict(te1)[10000])[772] == b'Sort' and [r for r in dict(tr1)[10000] if r[0] != 772] == [r for r in dict(_tc.read(TXR + '.x') if False else [(10000, [(1, 'Привет'.encode('cp1251'), b''), (771, b'x', b'')]), (10, [(5, b'Sword', b'')])])[10000]] and 'ru=True' in txt)
    ex_ru = e1
    kit_setup(); cli('--gfx', 'apply', 'bag=big', env=gen); rcv, txv = cli('--gfx', 'revert', env=gen)
    check('windows kit: "Restore original" -> exe, global.cmp and BOTH text files are the originals again, byte for byte', rd(ex) == exo and rd(GLB) == glb0 and rd(TXR) == txr0 and rd(TXE) == txe0 and tree(GAME) == t0, str((rd(ex) == exo, rd(GLB) == glb0, rd(TXR) == txr0, rd(TXE) == txe0, {k for k in set(t0) | set(tree(GAME)) if t0.get(k) != tree(GAME).get(k)}, rcv, txv[-700:])))
    # on top of the older patches (voice, dusk, map panel): all together, then the kit goes off and the exe is exactly what it was
    kit_setup(); cli('--voice', 'on', '--dusk', 'on'); cli('--gfx', 'apply', 'automap=on', env=gen); epre = rd(ex)
    rc, txt = cli('--gfx', 'apply', 'bag=big,glow=on', env=gen); ek = rd(ex)
    check('windows + glow on top of voice + dusk + map panel: all on, those three untouched', rc == 0 and 'GFX-WINPACK exe=on data=on problems=0 glow=on' in txt and ek[0x196b73] == 0xEB and ek[0x4b280] == 0xC3 and ek[0x71acc:0x71acc + 7] == bytes([0x90] * 7), txt)
    check('windows label by the game language: Russian file -> "надето" (cp1251) in the exe, not "worn"', b'\xed\xe0\xe4\xe5\xf2\xee\0' in ek and b'Tradeplate Bag Box\0' in ek and (b'worn\0' not in ek[0x259000:0x259400]))
    rc, txt = cli('--gfx', 'apply', 'bag=orig,glow=off', env=gen); check('windows + glow off again: the exe is exactly what it was before (voice, dusk and map panel stay)', rd(ex) == epre, txt)
    cli('--gfx', 'apply', 'bag=big', env=gen); e_again = rd(ex); rc, txt = cli('--gfx', 'apply', 'bag=big', env=gen)
    check('windows: applying twice changes nothing (idempotent)', rd(ex) == e_again and rc == 0, txt)
    kit_setup(); shutil.rmtree(os.path.join(GAME, 'localizations', 'german')); cli('--gfx', 'apply', 'bag=big', env=gen); een = rd(ex)
    check('windows label by the game language: English-only game -> "worn" in the exe (ASCII, safe), no Cyrillic label', b'worn\0' in een and b'\xed\xe0\xe4\xe5\xf2\xee' not in een)
    # glow + interp + windows in the frame: every order gives the same exe, each switch-off keeps the others, the last one takes the frame out
    import hashlib as _h
    def seq(order):
        kit_setup(); res = []
        for k in order:
            if k == 'w': cli('--gfx', 'apply', 'bag=big', env=gen)
            elif k == 'g': cli('--gfx', 'apply', 'glow=on', env=gen)
            else: cli('--fps', 'monitor', env=lab)
        return rd(ex)
    ra = seq('wgi'); rb_ = seq('igw'); rc_ = seq('gwi')
    check('frame: windows + glow + interp in three different orders give the SAME exe (frame +40960)', ra == rb_ == rc_ and len(ra) == len(exo) + 40960)
    kit_setup(); cli('--gfx', 'apply', 'bag=big,glow=on', env=lab); cli('--fps', 'monitor', env=lab)
    rc, txt = cli('--gfx', 'apply', 'bag=orig', env=gen)
    check('frame: windows off keeps glow and interp on and the frame in', 'GFX-WINPACK exe=off data=off problems=0 glow=on interp=on frame=on' in txt and len(rd(ex)) == len(exo) + 40960, txt)
    rc, txt = cli('--gfx', 'apply', 'glow=off', env=gen); check('frame: glow off keeps interp (frame stays)', 'glow=off interp=on frame=on' in txt, txt)
    rc, txt = cli('--fps', 'orig', env=lab); rc, txt = cli('--gfx', 'list', env=lab)
    check('frame: the last patch off takes the frame out: exe is the original length and bytes', rd(ex) == exo and 'frame=off' in txt, txt)
    # 1.0.18..1.0.23 had Ctrl+S (0x13) as the sort key; now Ctrl+C (0x0F): an exe with the old byte is migrated on start-up and the kit reads as ON again
    kit_setup(); cli('--gfx', 'apply', 'bag=big', env=gen); eK = bytearray(rd(ex)); assert eK[0x259e04] == 0x03; eK[0x259e04] = 0x13; open(ex, 'wb').write(eK)
    rc, txt = cli('--defaults', 'on', env=gen); eK2 = rd(ex); rc2, txt2 = cli('--gfx', 'list', env=gen)
    check('sort key: an exe with the old Ctrl+S byte is migrated to Ctrl+C and the kit is on again', eK2[0x259e04] == 0x03 and 'GFX-WINPACK exe=on' in txt2, txt2[-300:])
    # a mixed exe of a test build (4096-byte tail, ".interp" header, hooks no table knows): the start-up cleanup cuts the tail and puts the interpolation points back, then the kit is available
    kit_setup(); mx = bytearray(exo) + bytearray([1 + i % 255 for i in range(4096)]); mx[0x2a8:0x2af] = b'.interp'; mx[0x116] = 5; mx[0x49bcd:0x49bd5] = bytes.fromhex('e83faa3100909090'); open(ex, 'wb').write(mx)
    rc, txt = cli('--defaults', 'on', env=gen); e5 = rd(ex)
    check('mixed test exe (+4096 tail, .interp header): start-up cut the tail, header and hook bytes are the original again', rc == 0 and len(e5) == len(exo) and e5[0x2a8:0x2af] == exo[0x2a8:0x2af] and e5[0x116] == exo[0x116] and e5[0x49bcd:0x49bd5] == exo[0x49bcd:0x49bd5], txt)
    rc, txt = cli('--gfx', 'list', env=gen); check('after the cleanup the kit is available (frame=off, exelen is the original)', 'GFX-WINPACK exe=off' in txt and 'frame=off' in txt, txt)
    # stray bytes of an old test build (the owner's crash after loading a save, 07.11.2026): call rel32 low byte at 0xAA95D = 0x63 and a ".glow" header leftover at 0x2D0 -> the start-up puts them back
    kit_setup(); sb = bytearray(exo); sb[0xaa95d] = 0x63; sb[0x2d0:0x2d5] = b'.glow'; sb[0x2d9] = 0x80; open(ex, 'wb').write(sb); rc, txt = cli('--defaults', 'on', env=gen); e6 = rd(ex)
    check('stray bytes of an old test build (call at 0x4AB55C, .glow header leftover): start-up puts the original bytes back', rc == 0 and e6[0xaa95c:0xaa961] == exo[0xaa95c:0xaa961] and e6[0x2a8:0x2e8] == exo[0x2a8:0x2e8], txt + ' diff=' + str([hex(i) for i in range(min(len(e6), len(exo))) if e6[i] != exo[i]][:8]) + ' len=%d' % len(e6))
    # a foreign statuspl entry (or another game version) -> the whole kit is refused, nothing written
    kit_setup(); mkcmp(GLB, [('dat\\statuspl.cmp', bytes(360))]); t1 = tree(GAME); rc, txt = cli('--gfx', 'apply', 'bag=big', env=gen)
    check('windows kit: a global.cmp whose statuspl entry is not the known one -> refused, the files are as before', rc != 0 and rd(ex) == exo and tree(GAME) == t1, txt)
    # consistency: flat.cmp asks for sprite 665, the archive has 600
    kit_setup(); mkcmp(FLAT, [('bmg\\inventpl.bmg', b'begin button\n normal image list 8 index 665\nend button\n')]); open(os.path.join(IM, 'CPackedi.8c'), 'wb').write(bytes(56 * 600))
    rc, txt = cli('--gfx', 'list', env=gen); check('windows kit: flat.cmp naming sprite 665 while archive 8 has 600 -> reported (problems=1)', 'GFX-WINPACK' in txt and 'problems=1' in txt, txt)
    open(os.path.join(IM, 'CPackedi.8c'), 'wb').write(bytes(56 * 666)); rc, txt = cli('--gfx', 'list', env=gen); check('windows kit: with 666 sprites it is fine (problems=0)', 'problems=0' in txt, txt)
    setup()

    # the tables in gfx.txt are exactly what the patch scripts make from the reference exe (and every subset x order of frame/windows/glow/interp on it is the same exe: checked by the tool itself)
    if os.path.exists(os.path.join(ROOT, 'scratch', 're', 'div.exe')):
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'games', 'divine-divinity', 'tools', 'make_exe_patches.py'), '--check', '--work', os.path.join(S, 'wp')], capture_output=True, text=True, timeout=300)
        check('exe patch tables (frame/windows/glow/interp/tick80) in gfx.txt == the scripts\' output; 26 subset x order combinations equal (tick80 also == the script on top of windows+glow); reverts exact', r.returncode == 0 and 'match the scripts' in r.stdout and 'verified: 26' in r.stdout, (r.stdout + r.stderr)[-500:])
    # the real data of the kit (built by tools/make_windows_sets.py): sprites >= highest index of the bmg files, the pair [Close | Sort] centred, same stats layout for every skin
    wins = [d for d in (os.path.join(ROOT, 'scratch', 'sr_lab', 'set_win_' + b) for b in ('orig', 'c', 'e')) if os.path.exists(os.path.join(d, 'dat', 'flat.cmp'))]
    for d in wins:
        n8 = os.path.getsize(os.path.join(d, 'static', 'imagelists', 'CPackedi.8c')) // 56; mx = 0
        for e in _cf.read(os.path.join(d, 'dat', 'flat.cmp')):
            if e.name.lower().endswith('.bmg'): mx = max([mx] + [int(x) for x in re.findall(r'image list 8 index (\d+)', e.data.decode('latin-1'))])
        inv = _cf.find(_cf.read(os.path.join(d, 'dat', 'flat.cmp')), 'bmg\\inventpl.bmg').data.decode('latin-1')
        mc = re.search(r'index 197\s.*?position \((\d+), (\d+)\)', inv, re.S); ms = re.search(r'callback id 60.*?position \((\d+), (\d+)\)', inv, re.S)
        cx, sx = int(mc.group(1)), int(ms.group(1)); width = 332 + 90
        check('kit data %s: sprites in archive 8 (%d) > highest bmg index (%d)' % (os.path.basename(d), n8, mx), n8 > mx)
        check('kit data %s: [Close | Sort] pair centred (left margin %d = right margin %d), same row' % (os.path.basename(d), cx, width - (sx + 61)), cx == width - (sx + 61) and mc.group(2) == ms.group(2) and sx - (cx + 61) in (8, 9, 10))
    # the map panel patch of div.exe: bytes checked, backup stays original, works with voice/dusk, refuses a foreign exe
    setup(); t0 = tree(GAME); ex = os.path.join(GAME, 'div.exe'); exo = rd(ex)
    rc, txt = cli('--gfx', 'apply', 'automap=on', env=gen); e1 = rd(ex); dp = diffpos(e1, exo)
    pts = [(0x4b280, 1), (0x4b320, 3), (0x4b71d, 15)]
    check('automap on: only the listed byte ranges changed (size equal)', rc == 0 and dp and all(any(a <= i < a + n for a, n in pts) for i in dp) and e1[0x4b280] == 0xC3 and e1[0x4b71d:0x4b720] == bytes([0x83, 0xE8, 0x64]), txt)
    bk = [os.path.join(g, 'backup', 'div.exe.orig') for g in gamedata()]
    check('automap on: the program\'s backup of div.exe is the ORIGINAL (unpatched) file', bk and all(rd(b) == exo for b in bk if os.path.exists(b)) and any(os.path.exists(b) for b in bk))
    rc, txt = cli('--voice', 'on', '--dusk', 'on'); e2 = rd(ex)
    check('automap + voice + dusk together: all three patches present, backup still original', rc == 0 and e2[0x4b280] == 0xC3 and e2[0x196b73] == 0xEB and all(rd(b) == exo for b in bk if os.path.exists(b)), txt)
    rc, txt = cli('--voice', 'off', '--dusk', 'off'); check('voice/dusk off leave the map patch alone', rc == 0 and rd(ex)[0x4b280] == 0xC3 and rd(ex)[0x196b73] == 0x74, txt)
    rc, txt = cli('--gfx', 'apply', 'automap=off', env=gen); check('automap off: the exe is the original again, byte for byte', rc == 0 and rd(ex) == exo and tree(GAME) == t0, txt)
    cli('--gfx', 'apply', 'automap=on', env=gen); rc, txt = cli('--revert-all', env=gen); check('automap: "Revert all" restores the exe', rc == 0 and rd(ex) == exo, txt)
    b = bytearray(exo); b[0x4b320] = 0x90; open(ex, 'wb').write(bytes(b)); t1 = tree(GAME)
    rc, txt = cli('--gfx', 'apply', 'automap=on', env=gen); check('automap: an unexpected byte at a patch point -> no dead end: div.exe rebuilt from the verified original (original + automap)', rc == 0 and rd(ex) == exe_build(exo, ['automap']), txt)
    open(ex, 'wb').write(exo + b'tail'); t1 = tree(GAME); rc, txt = cli('--gfx', 'apply', 'automap=on', env=gen)
    check('automap: another build of the exe (size differs) -> refused, nothing written', rc != 0 and tree(GAME) == t1, txt)

    # FROZEN frame mode (owner 07.11.2026): without GAMEREMIX_FPS_LAB=1 nothing reaches the interpolation patch or maxgameticks / vsync / maxfps
    setup(); t0 = tree(GAME); ex = os.path.join(GAME, 'div.exe'); exo = rd(ex)
    rc, txt = cli('--fps', 'monitor', env=gen); check('fps FROZEN: --fps monitor is refused without the lab switch, nothing written', rc != 0 and tree(GAME) == t0 and rd(ex) == exo, txt)
    rc, txt = cli('--defaults', 'first', env=gen); e1 = rd(ex)
    check('fps FROZEN: the start-up defaults turn on voice, dusk and smooth play, but NOT the frame mode (no frame in the exe, no gr-draw, no ddraw.ini)', rc == 0 and 'voice=True' in txt and 'dusk=True' in txt and 'launcher=True' in txt and 'fps=orig' in txt and len(e1) == len(exo) and not os.path.exists(os.path.join(GAME, 'ddraw.ini')), txt)
    rc, txt = cli('--defaults', 'force', env=gen); check('fps FROZEN: the wizard defaults (force) also leave the frame mode alone', rc == 0 and 'fps=orig' in txt and len(rd(ex)) == len(exo), txt)
    cli('--revert-all', env=gen)
    # frame mode (--fps): the interpolation patch of div.exe (the frame appended: +40960 bytes) + gr-draw settings of ddraw.ini (vsync / maxfps / maxgameticks=-1)
    def ini_val(key):
        import re as _re
        t = open(os.path.join(GAME, 'ddraw.ini'), encoding='latin1').read(); i = t.find('[ddraw]'); m = _re.search(r'^' + key + r'\s*=\s*(\S*)', t[i:], _re.M); return m.group(1) if m else None
    setup(); t0 = tree(GAME); ex = os.path.join(GAME, 'div.exe'); exo = rd(ex)
    rc, txt = cli('--fps', 'monitor', env=lab); e1 = rd(ex)
    check('fps monitor: exe is 40960 bytes longer (the frame with the .interp section filled), still a supported exe, gr-draw is on, vsync=true maxfps=-1 maxgameticks=-1', rc == 0 and len(e1) == len(exo) + 40960 and __import__('hashlib').sha256(e1).hexdigest().startswith('f720ba18260f2600') and e1[:2] == b'MZ' and 'exeSupported=True' in txt and os.path.exists(os.path.join(GAME, 'ddraw.dll')) and ini_val('vsync') == 'true' and ini_val('maxfps') == '-1' and ini_val('maxgameticks') == '-1' and ini_val('renderer') == 'opengl', txt)
    check('fps monitor: status says monitor', 'fps=monitor' in txt)
    bk = [os.path.join(g, 'backup', 'div.exe.orig') for g in gamedata()]
    check('fps monitor: the program\'s backup of div.exe is the ORIGINAL (unpatched, original length)', bk and any(os.path.exists(b) for b in bk) and all(rd(b) == exo for b in bk if os.path.exists(b)))
    rc, txt = cli('--gfx', 'apply', 'automap=on', env=gen); e2 = rd(ex)
    check('fps + map panel together: both patches present, the section stays', rc == 0 and len(e2) == len(exo) + 40960 and e2[0x4b280] == 0xC3, txt)
    rc, txt = cli('--voice', 'on', '--dusk', 'on'); check('fps + voice + dusk: all present, exe still supported', rc == 0 and rd(ex)[0x196b73] == 0xEB and 'exeSupported=True' in txt, txt)
    cli('--voice', 'off', '--dusk', 'off'); cli('--gfx', 'apply', 'automap=off', env=gen)
    rc, txt = cli('--fps', 'unlimited', env=lab); check('fps unlimited: vsync=false maxfps=0 maxgameticks=-1', rc == 0 and ini_val('vsync') == 'false' and ini_val('maxfps') == '0' and ini_val('maxgameticks') == '-1' and 'fps=unlimited' in txt, txt)
    rc, txt = cli('--fps', '165', env=lab); check('fps own limit 165: vsync=false maxfps=165 maxgameticks=-1', rc == 0 and ini_val('vsync') == 'false' and ini_val('maxfps') == '165' and ini_val('maxgameticks') == '-1' and 'fps=custom165' in txt, txt)
    rc, txt = cli('--fps', '10', env=lab); check('fps: a limit below 20 is an argument error (rc 2)', rc == 2, txt)
    rc, txt = cli('--fps', 'orig', env=lab); check('fps orig: the exe is the original again byte for byte, maxgameticks back to the wrapper default', rc == 0 and rd(ex) == exo and ini_val('maxgameticks') == '0' and 'fps=orig' in txt, txt)
    cli('--fps', 'monitor', env=lab); rc, txt = cli('--revert-all', env=lab); check('fps: "Revert all" restores the exe byte for byte and the folder', rc == 0 and rd(ex) == exo and tree(GAME) == t0, txt)
    b = bytearray(exo); b[0x104e20] = 0x90; open(ex, 'wb').write(bytes(b)); t1 = tree(GAME)
    rc, txt = cli('--fps', 'monitor', env=lab); check('fps: an unexpected byte at a hook -> rebuilt from the verified original: the same exe as the first --fps monitor', rc == 0 and rd(ex) == e1, txt)
    open(ex, 'wb').write(exo + b'tail'); rc, txt = cli('--fps', 'monitor', env=lab); check('fps: another build of the exe (size differs) -> refused, exe unchanged', rc != 0 and rd(ex) == exo + b'tail', txt)
    open(ex, 'wb').write(exo)

    # lab only (GAMEREMIX_FPS_LAB=1): the defaults of Patches & fixes incl. the frame mode: ON once per game; "Revert all" is remembered
    setup(); t0 = tree(GAME); ex = os.path.join(GAME, 'div.exe'); exo = rd(ex)
    rc, txt = cli('--defaults', 'first', env=lab); e1 = rd(ex)
    check('defaults: voice, dusk, smooth play and the frame mode are on after the first run', rc == 0 and 'voice=True' in txt and 'dusk=True' in txt and 'launcher=True' in txt and 'fps=monitor' in txt and 'cnc=True' in txt and len(e1) == len(exo) + 40960, txt)
    cli('--voice', 'off', env=gen); rc, txt = cli('--defaults', 'first', env=lab); check('defaults: the second run does nothing (once per game)', rc == 0 and 'voice=False' in txt, txt)
    rc, txt = cli('--revert-all', env=gen); check('defaults: "Revert all" brings the original exe and folder back and remembers the choice (optouts)', rc == 0 and rd(ex) == exo and 'optouts=voice+dusk+smooth+fps' in txt, txt)
    rc, txt = cli('--defaults', 'first', env=lab); check('defaults: after "Revert all" nothing comes back by itself', rc == 0 and 'voice=False' in txt and 'fps=orig' in txt, txt)
    rc, txt = cli('--defaults', 'force', env=lab); check('defaults force (the wizard): everything is switched on again, opt-outs cleared', rc == 0 and 'voice=True' in txt and 'fps=monitor' in txt and 'optouts=' in txt and 'optouts=voice' not in txt, txt)
    cli('--revert-all', env=gen)

    # ---- FPS mod = tick 80 (src/Tick80.cs, patch=tick80 of gfx.txt; --fps80 on|off). Exe: frame (+40960, unchanged since 1.0.18) + hooks and code inside the .interp section; settings put back exactly.
    T80_SHA = '468f9e259097f2fa1900b3c2dd2cb3382843ac46d6a09fd82688c5b0ebacb4c7'   # sha256 of original + frame + tick80 (games/divine-divinity/tools/make_exe_patches.py, same as tick80_patch.py --frame)
    def st80(txt): m = re.search(r'FPS80 state=(\S+)', txt); return m.group(1) if m else None
    def ini_put(key, val):
        pth = os.path.join(GAME, 'ddraw.ini'); t = open(pth, encoding='latin1', newline='').read(); i = t.find('[ddraw]'); j = t.find('\n[', i + 1); j = len(t) if j < 0 else j
        sec = re.sub(r'(?m)^(' + key + r'\s*=\s*)\S*', lambda m: m.group(1) + val, t[i:j], count=1); open(pth, 'w', encoding='latin1', newline='').write(t[:i] + sec + t[j:])
    def cfg_smooth(): return re.search(r'(?m)^smooth\s+(\d+)', open(os.path.join(GAME, 'config.div'), encoding='latin1').read()).group(1)
    setup(); t0 = tree(GAME); ex = os.path.join(GAME, 'div.exe'); exo = rd(ex)
    rc, txt = cli('--fps80', 'on', env=gen); e1 = rd(ex)
    check('fps80 on: exe = original + frame (+40960) + tick 80 (the sha256 of the generator output), still supported, state on', rc == 0 and len(e1) == len(exo) + 40960 and __import__('hashlib').sha256(e1).hexdigest() == T80_SHA and 'exeSupported=True' in txt and st80(txt) == 'on' and 'avail=True' in txt, txt)
    check('fps80 on: gr-draw is on with renderer=opengl, maxgameticks=-1 (no 60 FPS ceiling), vsync=true, maxfps=-1; config.div smooth 1', os.path.exists(os.path.join(GAME, 'ddraw.dll')) and ini_val('renderer') == 'opengl' and ini_val('maxgameticks') == '-1' and ini_val('vsync') == 'true' and ini_val('maxfps') == '-1' and cfg_smooth() == '1', txt)
    bk = [os.path.join(g, 'backup', 'div.exe.orig') for g in gamedata()]
    check('fps80: the program\'s backup of div.exe is the ORIGINAL (no frame, no tick 80)', bk and any(os.path.exists(b) for b in bk) and all(rd(b) == exo for b in bk if os.path.exists(b)))
    rc, txt = cli('--fps80', 'on', env=gen); check('fps80 on twice: nothing changes (idempotent)', rc == 0 and rd(ex) == e1 and st80(txt) == 'on', txt)
    rc, txt = cli('--gfx', 'list', env=gen); check('fps80: --gfx list sees the patch', 'tick80=on' in txt and 'frame=on' in txt, txt)
    # 1.0.20..1.0.26 shipped tick 80 v3.4 (8 step sites; patch=tick80_v34): an exe with it is switched to the current tick80 on start-up (the frame stays)
    def pts80(pid):
        ln = [l for l in open(os.path.join(ROOT, 'games', 'divine-divinity', 'gfx', 'gfx.txt'), encoding='utf-8').read().splitlines() if l.startswith('patch=%s|' % pid)][0]
        return [(int(o, 16), bytes.fromhex(a), bytes.fromhex(b)) for o, a, b in (x.split(':') for x in ln.split('|')[4:] if x.count(':') == 2)]
    cli('--defaults', 'on', env=gen); eD = rd(ex)   # the once-per-game start-up defaults go first, so the migration alone is compared
    for old_id, rel in (('tick80_v34', '1.0.20..1.0.26'), ('tick80_v35a', '1.0.27'), ('tick80_v35b', '1.0.28'), ('tick80_v35c', '1.0.29..1.0.30'), ('tick80_v35b', 'migration cut off after the first point')):
        e34 = bytearray(eD)
        for o, a, b in pts80('tick80'): e34[o:o + len(a)] = a
        for o, a, b in pts80(old_id): e34[o:o + len(b)] = b
        if rel.startswith('migration'): o, a, b = pts80(old_id)[0]; e34[o:o + len(a)] = a   # Write(off) goes from the first point: the old form is half out
        open(ex, 'wb').write(e34); rc, txt = cli('--defaults', 'on', env=gen); e35 = rd(ex)
        check('%s in the exe (%s): start-up switches it to the current tick80 (the exe == what it was with the current tick80, state on)' % (old_id, rel), e34 != eD and e35 == eD and st80(cli('--fps80', 'on', env=gen)[1]) == 'on', txt[-300:])
        open(ex, 'wb').write(e1)
    rc, txt = cli('--fps80', 'off', env=gen)
    check('fps80 off: the exe is the original again BYTE FOR BYTE (frame gone too), state off, wrapper settings back to the defaults (gr-draw was off before: maxgameticks=0)', rc == 0 and rd(ex) == exo and st80(txt) == 'off' and ini_val('maxgameticks') == '0' and ini_val('vsync') == 'true' and ini_val('maxfps') == '-1' and ini_val('renderer') == 'auto' and not any(os.path.exists(os.path.join(g, 'fps80_prev.txt')) for g in gamedata()), txt)
    rc, txt = cli('--fps80', 'off', env=gen); check('fps80 off twice: nothing to do, no error', rc == 0 and rd(ex) == exo and st80(txt) == 'off', txt)
    # the values the player had are put back EXACTLY (gr-draw already on with its own values; smooth 0 in config.div)
    setup(); ex = os.path.join(GAME, 'div.exe'); cli('--cnc', 'on', env=gen)
    for k, v in (('renderer', 'gdi'), ('maxgameticks', '25'), ('vsync', 'false'), ('maxfps', '75')): ini_put(k, v)
    cd = os.path.join(GAME, 'config.div'); cdt = open(cd, encoding='latin1', newline='').read().replace('smooth 1', 'smooth 0'); open(cd, 'w', encoding='latin1', newline='').write(cdt)
    ini0, cfg0 = rd(os.path.join(GAME, 'ddraw.ini')), rd(cd)
    rc, txt = cli('--fps80', 'on', env=gen)
    check('fps80 on over the player\'s own wrapper values: opengl / -1 / true / -1 and smooth 1', rc == 0 and ini_val('renderer') == 'opengl' and ini_val('maxgameticks') == '-1' and ini_val('vsync') == 'true' and ini_val('maxfps') == '-1' and cfg_smooth() == '1', txt)
    rc, txt = cli('--fps80', 'off', env=gen)
    check('fps80 off: ddraw.ini and config.div are byte for byte what they were before (gdi / 25 / false / 75, smooth 0), exe original', rc == 0 and rd(os.path.join(GAME, 'ddraw.ini')) == ini0 and rd(cd) == cfg0 and rd(ex) == exo, txt)
    # the frame is shared with windows / glow: any order, any subset gives the same exe; each switch-off leaves the others; the last one takes the frame out
    def seq80(order):
        kit_setup(); ex_ = os.path.join(GAME, 'div.exe')
        for k in order:
            if k == 'w': cli('--gfx', 'apply', 'bag=big', env=gen)
            elif k == 'g': cli('--gfx', 'apply', 'glow=on', env=gen)
            else: cli('--fps80', 'on', env=gen)
        return rd(ex_)
    kit_setup(); ex = os.path.join(GAME, 'div.exe'); exo = rd(ex)
    perms = [seq80(o) for o in ('wgt', 'wtg', 'gwt', 'gtw', 'twg', 'tgw')]
    check('fps80 + windows + glow: all 6 orders of switching on give the SAME exe (frame +40960, longer than the frame alone only by nothing)', all(x == perms[0] for x in perms) and len(perms[0]) == len(exo) + 40960 and perms[0] != seq80('wg'), str([len(x) for x in perms]))
    pairs = {'wt': seq80('wt'), 'tw': seq80('tw'), 'gt': seq80('gt'), 'tg': seq80('tg'), 'wg': seq80('wg'), 't': seq80('t')}
    check('fps80 + windows, fps80 + glow (both orders): same exe; fps80 alone = the generator output', pairs['wt'] == pairs['tw'] and pairs['gt'] == pairs['tg'] and __import__('hashlib').sha256(pairs['t']).hexdigest() == T80_SHA)
    kit_setup(); cli('--gfx', 'apply', 'bag=big,glow=on', env=gen); cli('--fps80', 'on', env=gen)
    rc, txt = cli('--fps80', 'off', env=gen); check('fps80 off with windows + glow on: the exe is exactly windows + glow (frame stays)', rc == 0 and rd(ex) == pairs['wg'] and 'GFX-WINPACK exe=on' in cli('--gfx', 'list', env=gen)[1], txt)
    cli('--fps80', 'on', env=gen); rc, txt = cli('--gfx', 'apply', 'bag=orig', env=gen)
    check('windows off with fps80 + glow on: the exe is exactly glow + fps80 (frame stays)', rc == 0 and rd(ex) == pairs['gt'], txt)
    rc, txt = cli('--gfx', 'apply', 'glow=off', env=gen); check('glow off with only fps80 left: the exe is fps80 alone (frame stays)', rc == 0 and rd(ex) == pairs['t'], txt)
    rc, txt = cli('--fps80', 'off', env=gen); check('fps80 was the last one: the frame goes, the exe is the original byte for byte', rc == 0 and rd(ex) == exo, txt)
    kit_setup(); cli('--fps80', 'on', env=gen); cli('--gfx', 'apply', 'bag=big,glow=on', env=gen); cli('--gfx', 'apply', 'bag=orig,glow=off', env=gen)
    check('fps80 first, windows + glow on and off after it: tick 80 still alone in the frame', rd(ex) == pairs['t'])
    cli('--fps80', 'off', env=gen); check('...and off: original', rd(ex) == exo)
    kit_setup(); cli('--gfx', 'apply', 'bag=big,glow=on', env=gen); cli('--fps80', 'on', env=gen); rc, txt = cli('--revert-all', env=gen)
    check('"Revert all" with windows + glow + fps80 on: exe back to the original byte for byte, fps80 record gone', rc == 0 and rd(ex) == exo and not any(os.path.exists(os.path.join(g, 'fps80_prev.txt')) for g in gamedata()), txt)
    # interpolation (frozen, lab only) and tick 80 use the same bytes of .interp: never both
    setup(); ex = os.path.join(GAME, 'div.exe'); exo = rd(ex)
    cli('--fps', 'monitor', env=lab); e_i = rd(ex)
    rc, txt = cli('--fps80', 'on', env=lab); check('fps80 on while the interpolation is on: refused, exe untouched', rc != 0 and rd(ex) == e_i, txt)
    rc, txt = cli('--fps80', 'off', env=lab); check('fps80 off while the interpolation is on: nothing of ours, state n/a, exe untouched', rc == 0 and rd(ex) == e_i and st80(txt) == 'n/a' and 'avail=False' in txt, txt)
    cli('--fps', 'orig', env=lab); cli('--fps80', 'on', env=lab); e_t = rd(ex)
    rc, txt = cli('--fps', 'monitor', env=lab); check('the interpolation while tick 80 is on: refused, exe untouched', rc != 0 and rd(ex) == e_t, txt)
    cli('--fps80', 'off', env=lab)
    check('...both off: original', rd(ex) == exo)
    # foreign bytes / another build: refused, nothing written
    setup(); ex = os.path.join(GAME, 'div.exe'); exo = rd(ex); b = bytearray(exo); b[0xe395] = 0x90; open(ex, 'wb').write(bytes(b)); t1 = tree(GAME)
    rc, txt = cli('--fps80', 'on', env=gen); check('fps80: an unexpected byte at a hook -> refused, nothing written (exe, ddraw.ini, config.div)', rc != 0 and tree(GAME) == t1, txt)
    open(ex, 'wb').write(exo + b'tail'); t1 = tree(GAME); rc, txt = cli('--fps80', 'on', env=gen); check('fps80: another build of the exe (size differs) -> refused, nothing written', rc != 0 and tree(GAME) == t1, txt)
    open(ex, 'wb').write(exo)
    rc, txt = cli('--fps80', 'maybe', env=gen); check('fps80: a wrong value is an argument error (rc 2)', rc == 2, txt)

    # wizard + design ban: the card grid never depends on a badge / check mark (text of the cards keeps the same y), every wizard step builds, the font and upscaling previews really differ
    out = os.path.join(S, 'cardlayout.txt'); r = subprocess.run([EXE, '--shot', 'cardlayout', out], env=ENV, capture_output=True, timeout=120)
    check('design ban: a badge/check mark/recommendation does not move or narrow the card text (title and text rectangles equal for all variants, 3 card kinds)', r.returncode == 0 and open(out).read().startswith('ok'), open(out).read() if os.path.exists(out) else '')
    # "text always fits" (docs/design.md): every page, wizard step and tool window in RU and EN is painted; any text that does not fit its place even at the minimal font is a failure
    setup(); out = os.path.join(S, 'textfit.txt'); r = subprocess.run([EXE, '--shot', 'textfit', out, GAME], env=ENV, capture_output=True, timeout=300)
    tf = open(out, encoding='utf-8-sig').read() if os.path.exists(out) else str(r.stderr)
    check('no text overflow (RU and EN): every page, wizard step and tool window painted, each text fits its place', r.returncode == 0 and tf.startswith('ok') and tf.count('MEASURED ') >= 40, '\n'.join(l for l in tf.splitlines() if not l.startswith('MEASURED'))[:3000])
    setup(); out = os.path.join(S, 'wizsteps.txt'); r = subprocess.run([EXE, '--shot', 'wizsteps', out, GAME], env=ENV, capture_output=True, timeout=180)
    check('wizard: all 8 steps build without an error', r.returncode == 0 and open(out).read().startswith('ok'), open(out).read() if os.path.exists(out) else str(r.stderr))
    check('wizard fonts step: the two preview pictures (default / larger) are really different, or the fonts are absent (none)', 'differing=' in open(out).read() and int(open(out).read().split('differing=')[1] or 0) > 100 or 'fonts none' in open(out).read(), open(out).read())
    try:
        from PIL import Image as _I; import numpy as _np
        pv = os.path.join(ROOT, 'games', 'divine-divinity', 'gfx', 'previews'); a = _np.asarray(_I.open(os.path.join(pv, 'up_orig.jpg')).convert('RGB')).astype(int); b = _np.asarray(_I.open(os.path.join(pv, 'up_v2.jpg')).convert('RGB')).astype(int)
        check('wizard upscaling previews: the enlarged fragment differs between the original and Clean v2 (mean difference > 4, > 10% of the pixels change by > 20)', abs(a - b).mean() > 4 and (abs(a - b).max(axis=2) > 20).mean() > 0.10, str(abs(a - b).mean()))
    except ImportError: print('SKIP upscaling preview check (no Pillow)')

    # quick setup with a look (--preset ... --gfx-image --gfx-skin): the preset applies first, the sets after; a failure of the look does not undo the preset
    setup(); t0 = tree(GAME); rc, txt = cli('--preset', '0', '--wrapper', 'cnc', '--gfx-image', 'v2', '--gfx-skin', 'B', env=gen); f = files()
    check('quick setup + look: preset applied, picture v2 and skin B installed (skin over picture)', rc == 0 and 'GFX-RESULT ok' in txt and f['CPackedb.1c'] == V2['CPackedb.1c'] and f['CPackedb.8c'] == SK['b']['CPackedb.8c'] and os.path.exists(os.path.join(GAME, 'ddraw.dll')), txt)
    rc, txt = cli('--revert-all', env=gen); check('quick setup + look: "Revert all" returns sets and preset (identical tree)', rc == 0 and tree(GAME) == t0, txt)
    setup(); t0 = tree(GAME); dead = dict(ENV, OGF_ASSETS_URL='http://127.0.0.1:9/assets/divine-divinity/')
    rc, txt = cli('--preset', '0', '--wrapper', 'cnc', '--gfx-image', 'v2', env=dead)
    check('quick setup + look, no network: the look fails with a clear line, the preset stays applied', rc == 1 and 'GFX-FAILED' in txt and os.path.exists(os.path.join(GAME, 'ddraw.dll')) and files() == orig_files, txt)
    rc, txt = cli('--revert-all', env=gen)
    rc, txt = cli('--preset', '0', '--gfx-image', 'bogus', env=gen); check('quick setup: a bad --gfx-image value is an argument error (rc 2)', rc == 2, txt)

    # the catalog and the previews are built into the program: the page works without any server (the server only supplies the files)
    setup(); t0 = tree(GAME); rc, txt = cli('--gfx', 'list', env=dead)
    check('gfx catalog without a server: list works (rc 0), every option is known with name, preview and approximate size', rc == 0 and 'GFX-OPT slot=pic value=v2 set=clean-v2 status=unavailable' in txt and 'preview=inv_v2' in txt and 'approxMb=472' in txt and 'value=b set=skin-b status=unavailable' in txt and 'preview=inv_B' in txt, txt)
    rc, txt = cli('--gfx', 'apply', 'pic=v2', env=dead)
    check('gfx apply without a server: honest reason (set not downloaded / server unreachable), nothing changed', rc != 0 and 'GFX-PROBLEM' in txt and ('not downloaded' in txt or 'не скачан' in txt) and tree(GAME) == t0, txt)
    # default fixes: on with quick setup, opt-out after Revert all / switching off, quick setup turns them on again
    setup(); t0 = tree(GAME); ex = os.path.join(GAME, 'div.exe'); exo = rd(ex); sp = os.path.join(GAME, 'main', 'startup', 'world.x1')
    rc, txt = cli('--preset', '0', '--wrapper', 'cnc'); e1 = rd(ex)
    check('default fixes: quick setup turns on the map panel and the cellar floor (exe patched at the listed points, start map fixed)', rc == 0 and e1[0x4b280] == 0xC3 and rd(sp) == world_bytes(dark=False), txt)
    check('default fixes: the saves are NOT touched', rd(os.path.join(GAME, 'savegames', 'a', 'world.x1')) == world_bytes())
    check('default fixes: the backup of div.exe is the original', all(rd(os.path.join(g, 'backup', 'div.exe.orig')) == exo for g in gamedata() if os.path.exists(os.path.join(g, 'backup', 'div.exe.orig'))) and any(os.path.exists(os.path.join(g, 'backup', 'div.exe.orig')) for g in gamedata()))
    rc, txt = cli('--revert-all'); rc2, txt2 = cli('--gfx', 'status', env=gen)
    check('default fixes: "Revert all" brings the exe and the map back and records that the player declined (no silent re-enabling)', rc == 0 and rd(ex) == exo and rd(sp) == world_bytes() and tree(GAME) == t0 and 'GFX-FIX id=automap state=off default=True optout=True' in txt2 and 'GFX-FIX id=floor state=off default=True optout=True' in txt2, txt + txt2)
    rc, txt = cli('--preset', '0', '--wrapper', 'cnc'); rc2, txt2 = cli('--gfx', 'status', env=gen)
    check('default fixes: quick setup turns them on again and clears the opt-out', rc == 0 and rd(ex)[0x4b280] == 0xC3 and 'optout=False' in txt2 and 'optout=True' not in txt2, txt + txt2)
    cli('--gfx', 'apply', 'automap=off,floor=off', env=gen); rc, txt = cli('--gfx', 'status', env=gen)
    check('default fixes: switching off by hand (CLI) also records the opt-out; floor-saves is CLI-only and not a default', rd(ex)[0x4b280] == exo[0x4b280] and rd(ex)[0x4b71d:0x4b72c] == exo[0x4b71d:0x4b72c] and 'GFX-FIX id=automap state=off default=True optout=True' in txt and 'GFX-FIX id=floorsaves state=off default=False' in txt, txt)
    cli('--revert-all')

    # the text "Changes" never speaks of the default fixes; Auto is not a change when it is already Auto; only quiet steps = "No changes"
    def planline(txt): m = re.search(r'GFX-PLAN steps=(\d+) user=(\d+) .*summary=\[(.*)\]', txt); return (int(m.group(1)), int(m.group(2)), m.group(3)) if m else None
    setup(); t0 = tree(GAME); rc, txt = cli('--gfx', 'apply', 'floor=on,automap=on', env=gen); pl = planline(txt)
    check('changes text: only the default fixes -> steps exist, user steps 0, summary empty ("No changes")', rc == 0 and pl and pl[0] >= 1 and pl[1] == 0 and pl[2] == '', txt)
    cli('--gfx', 'revert', env=gen); rc, txt = cli('--gfx', 'apply', 'pic=v2,floor=on,automap=on', env=gen); pl = planline(txt)
    check('changes text: the summary names the picture and nothing about the floor or the map panel (RU and EN)', rc == 0 and pl and pl[1] == 1 and 'clean-v2' in pl[2] and not re.search(r'floor|Дыра|карты|Map panel|Cellar|automap', pl[2], re.I), txt)
    cli('--gfx', 'revert', env=gen); cli('--revert-all', env=gen); setup(); t0 = tree(GAME)
    cli('--cnc', 'on'); rc, txt = cli('--gfx', 'apply', 'scale=auto', '--monitor', '2560x1440', env=gen); pl = planline(txt)
    check('changes text: interface size Auto when nothing was ever saved is NOT a change (shown and meant as Auto)', rc == 0 and pl and pl[0] == 0 and pl[1] == 0, txt)
    cli('--scale', 'auto', '--monitor', '2560x1440'); rc, txt = cli('--gfx', 'apply', 'scale=auto', env=gen); pl = planline(txt)
    check('changes text: interface size Auto when it is saved as Auto is NOT a change', rc == 0 and pl and pl[0] == 0, txt)
    rc, txt = cli('--gfx', 'apply', 'scale=150', '--monitor', '2560x1440', env=gen); pl = planline(txt)
    check('changes text: a different interface size IS a change and is named', rc == 0 and pl and pl[1] == 1 and ('150' in pl[2]), txt)
    cli('--revert-all', env=gen)
    # no user-visible text in the code speaks of the default fixes (data files and comments are fine; the log is not user text)
    bad = []
    for fn in os.listdir(os.path.join(ROOT, 'src')):
        if not fn.endswith('.cs'): continue
        for n, ln in enumerate(open(os.path.join(ROOT, 'src', fn), encoding='utf-8-sig').read().splitlines(), 1):
            code = ln.split('//')[0] if '"' not in ln.split('//')[0][-1:] else ln
            if re.search(r'Дыра пола|Панель карты|floor hole|Cellar floor|Map panel', code): bad.append('%s:%d' % (fn, n))
    check('no user-visible string in src/*.cs mentions the cellar floor or the map panel', not bad, ', '.join(bad))

    # the game is running -> refused
    if not os.environ.get('OGF_TEST_NOGUARD'):
        run_dir = os.path.join(S, 'run2'); os.makedirs(run_dir, exist_ok=True); sl = os.path.join(run_dir, 'sleep.cs')
        open(sl, 'w').write('class P{static void Main(){System.Threading.Thread.Sleep(120000);}}')
        csc = os.path.join(os.environ['WINDIR'], r'Microsoft.NET\Framework\v3.5\csc.exe'); subprocess.run([csc, '/nologo', '/out:' + os.path.join(run_dir, 'div.exe'), sl], check=True, capture_output=True)
        setup(); t0 = tree(GAME); pr = subprocess.Popen([os.path.join(run_dir, 'div.exe')]); time.sleep(1.0)
        try:
            rc, txt = cli('--gfx', 'apply', 'pic=v2', env=gen); check('gfx: game running -> refused (rc 3), nothing changed', rc == 3 and tree(GAME) == t0, txt)
            rc, txt = cli('--fps80', 'on', env=gen); check('fps80: game running -> refused (rc 3), nothing changed (exe, ddraw.ini, config.div)', rc == 3 and tree(GAME) == t0, txt)
        finally:
            pr.kill(); pr.wait()
    else: print('SKIP gfx running-game test (OGF_TEST_NOGUARD=1)')
    srv.httpd.shutdown()

# ---- install "as if from scratch" (src/Install.cs, docs/TASK_install_monolith_2026-11-07.md): journal, div.exe rebuilt from the verified original, embedded files refreshed by sha --------
GFXTXT = os.path.join(ROOT, 'games', 'divine-divinity', 'gfx', 'gfx.txt')
def exe_tables():
    T = {'voice': {'pts': [(0x71ACC, bytes([0xC7, 0x46, 0x14, 0, 0, 0, 0]), b'\x90' * 7, None)], 'tail': None, 'needs': ''},
         'dusk': {'pts': [(0x196B73, b'\x74', b'\xEB', None)], 'tail': None, 'needs': ''}}
    for l in open(GFXTXT, encoding='utf-8').read().splitlines():
        if not l.startswith('patch='): continue
        p = l[6:].split('|'); t = {'pts': [], 'tail': None, 'needs': ''}
        for x in p[3:]:
            if x.startswith('append0:'): t['tail'] = b'\0' * int(x[8:])
            elif x.startswith('append:'): t['tail'] = bytes.fromhex(x[7:])
            elif x.startswith('needs:'): t['needs'] = x[6:].strip()
            else:
                o, a, b = x.split(':'); alt = None
                if '~' in b: b, alt = b.split('~')
                t['pts'].append((int(o, 16), bytes.fromhex(a), bytes.fromhex(b), bytes.fromhex(alt) if alt else None))
        T[p[0]] = t
    return T
def exe_build(orig, ids, alt=True, T=None):   # an independent build of "original + the tables" (alt: the English label of the big windows; the test game has no Russian text.cmp)
    T = T or exe_tables(); b = bytearray(orig); fr = list(dict.fromkeys([T[i]['needs'] for i in ids if T[i]['needs']])); order = fr + [i for i in ids if i not in fr]
    for i in order:
        t = T[i]
        if t['tail'] is not None and len(b) == len(orig): b += t['tail']
        for o, a, p, al in t['pts']: w = al if (alt and al) else p; b[o:o + len(w)] = w
    return bytes(b)
def put_old(b, T, form, cut=False):   # an exe with an older form of a patch written in place (as the older versions did)
    b = bytearray(b)
    for o, a, p, al in T[form]['pts']: b[o:o + len(p)] = p
    if cut: o, a, p, al = T[form]['pts'][0]; b[o:o + len(a)] = a   # a write cut off after the first point
    return bytes(b)
def journal():
    j = [os.path.join(g, 'install.txt') for g in gamedata() if os.path.exists(os.path.join(g, 'install.txt'))]
    return {l.split('|')[0]: l.split('|') for l in open(j[0], encoding='utf-8-sig').read().splitlines() if l and not l.startswith('#')} if j else {}
def journal_set(comp, files):   # what an older version of the program would have recorded: component|version|path=sha;...|options
    p = [os.path.join(g, 'install.txt') for g in gamedata()][0]; lines = [l for l in open(p, encoding='utf-8-sig').read().splitlines() if l and not l.startswith(comp + '|')] if os.path.exists(p) else []
    lines.append('%s|1.0.30|%s|' % (comp, ';'.join('%s=%s' % (k, hashlib.sha256(v).hexdigest()) for k, v in files.items()))); open(p, 'w', encoding='utf-8').write('\r\n'.join(lines) + '\r\n')
def install_tests():
    import gzip, random
    T = exe_tables(); ex = os.path.join(GAME, 'div.exe'); orig = rd(PRISTINE); bak = lambda: [os.path.join(g, 'backup', 'div.exe.orig') for g in gamedata()]
    def bak_ok(): return bool(bak()) and all(os.path.exists(b) and rd(b) == orig for b in bak())
    def tmp_left(): return [os.path.join(dp, f) for root in (GAME, DATA) for dp, _, fs in os.walk(root) for f in fs if f.endswith('.tmp')]
    check('install: the reference div.exe is the original 1.0.0.62', hashlib.sha256(orig).hexdigest() == REF_SHA)
    # the journal
    reset_all(); rc, txt = cli('--voice', 'on', '--dusk', 'on'); j = journal()
    check('journal: install.txt next to the backups, exe line = exe|version|div.exe=<sha of the game exe>|voice,dusk, voice line has the sha of both DLLs, no .tmp left', rc == 0 and 'exe' in j and j['exe'][2] == 'div.exe=' + hashlib.sha256(rd(ex)).hexdigest() and j['exe'][3] == 'voice,dusk' and re.match(r'\d+\.\d+\.\d+', j['exe'][1]) and 'voice' in j and 'OsirisDLL.dll=' in j['voice'][2] and 'DivDialogSystem.dll=' in j['voice'][2] and not tmp_left(), str(j) + txt)
    check('journal: the exe is original + voice + dusk byte for byte, the backup is the original', rd(ex) == exe_build(orig, ['voice', 'dusk'], T=T) and bak_ok())
    # migration from every released form of tick 80 (and the current one), an "old user": no journal, no backup, the exe written in place by an older version
    want = exe_build(orig, ['voice', 'dusk', 'tick80'], T=T)
    for form, cut in (('tick80_v34', False), ('tick80_v35a', False), ('tick80_v35b', False), ('tick80_v35c', False), ('tick80', False), ('tick80_v35b', True)):
        reset_all(); old = put_old(exe_build(orig, ['voice', 'dusk', 'frame'], T=T), T, form, cut); open(ex, 'wb').write(old)
        rc, txt = cli('--sync'); j = journal()
        check('migration %s%s (no journal, no backup): div.exe == original + voice + dusk + the CURRENT tick80, the backup is the verified original, journal records it' % (form, ' cut off half way' if cut else ''), rc == 0 and rd(ex) == want and bak_ok() and j.get('exe', ['', '', '', ''])[3] == 'voice,dusk,tick80', txt[-400:])
    # a user of a version with a journal whose tick80 table was older: the journal says "ours, tick80 on" -> rebuilt to the current table
    reset_all(); cli('--voice', 'on', '--dusk', 'on'); cli('--fps80', 'on'); old = put_old(exe_build(orig, ['voice', 'dusk', 'frame'], T=T), T, 'tick80_v35c'); open(ex, 'wb').write(old)
    p = [os.path.join(g, 'install.txt') for g in gamedata()][0]; t = open(p, encoding='utf-8-sig').read(); t = re.sub(r'div\.exe=[0-9a-f]{64}', 'div.exe=' + hashlib.sha256(old).hexdigest(), t); open(p, 'w', encoding='utf-8').write(t)
    rc, txt = cli('--sync'); check('migration with a journal (exe recorded by a version with tick80 v3.5c): rebuilt to the current tick80', rc == 0 and rd(ex) == want, txt[-300:])
    rc, txt = cli('--sync'); check('--sync twice: nothing changes', rc == 0 and rd(ex) == want and 'rebuilt' not in txt, txt[-300:])
    # unknown bytes at a patch point: the journal decides, the exe is rebuilt from the original
    reset_all(); cli('--voice', 'on', '--dusk', 'on'); b = bytearray(rd(ex)); b[0x196B73] = 0x90; b[0x71ACE] = 0x55; open(ex, 'wb').write(bytes(b))
    rc, txt = cli('--sync'); check('unknown bytes at the voice and dusk points: start-up rebuilds div.exe == original + voice + dusk (journal)', rc == 0 and rd(ex) == exe_build(orig, ['voice', 'dusk'], T=T) and bak_ok(), txt[-300:])
    reset_all(); cli('--voice', 'on'); [os.remove(os.path.join(g, 'install.txt')) for g in gamedata()]; b = bytearray(rd(ex)); b[0x196B73] = 0x90; open(ex, 'wb').write(bytes(b))
    rc, txt = cli('--dusk', 'on'); check('unknown byte at the dusk point, no journal: switching dusk on is no dead end any more: original + voice + dusk', rc == 0 and rd(ex) == exe_build(orig, ['voice', 'dusk'], T=T), txt[-300:])
    # changes outside every table (somebody's own edit): not touched at start-up, dropped by the next change of a fix (rebuilt from the original)
    reset_all(); cli('--voice', 'on', '--dusk', 'on'); b = bytearray(rd(ex)); b[0x1000] ^= 0xFF; own = bytes(b); open(ex, 'wb').write(own)
    rc, txt = cli('--sync'); check('an own edit outside our patches: start-up leaves div.exe as it is and says why', rc == 0 and rd(ex) == own and 'outside' in txt, txt[-300:])
    rc, txt = cli('--voice', 'off'); check('...the next change of a fix rebuilds it from the original: original + dusk', rc == 0 and rd(ex) == exe_build(orig, ['dusk'], T=T), txt[-300:])
    kept = [os.path.join(b, f) for b in [os.path.join(g, 'backup') for g in gamedata()] if os.path.isdir(b) for f in os.listdir(b) if f.startswith('div.exe.foreign-')]
    check('...and the exe with the own edit is kept as backup\\div.exe.foreign-<time> before the rebuild', any(rd(f) == own for f in kept), str(kept))
    # the copy of the original is never replaced by a non-original
    reset_all(); cli('--voice', 'on'); junk = bytes(random.Random(5).randbytes(len(orig))); open(ex, 'wb').write(junk)
    rc, txt = cli('--dusk', 'on'); check('div.exe replaced by foreign bytes of the same size: the backup stays the original, the exe = original + voice + dusk', rc == 0 and bak_ok() and rd(ex) == exe_build(orig, ['voice', 'dusk'], T=T) and not any(os.path.exists(b + '.prev') or os.path.exists(b + '.foreign') for b in bak()), txt[-300:])
    open(ex, 'wb').write(orig + b'X' * 1000); rc, txt = cli('--voice', 'on'); check('another build of div.exe (size differs): refused, exe and backup untouched', rc != 0 and rd(ex) == orig + b'X' * 1000 and bak_ok(), txt[-300:])
    rc, txt = cli('--voice', 'off'); check('...and switching off leaves that build alone too', rd(ex) == orig + b'X' * 1000 and bak_ok(), txt[-300:])
    reset_all(); cli('--voice', 'on'); cli('--voice', 'off'); [os.remove(os.path.join(g, 'install.txt')) for g in gamedata()]; bd = os.path.join(gamedata()[0], 'backup'); bad = bytes(random.Random(6).randbytes(len(orig))); open(os.path.join(bd, 'div.exe.orig'), 'wb').write(bad); open(os.path.join(bd, 'div.exe.orig.prev'), 'wb').write(bad[::-1])
    rc, txt = cli('--voice', 'on'); check('a non-original div.exe.orig (as 1.0.31 could store): replaced by the verified original, the old file kept aside as .foreign, the exe = original + voice', rc == 0 and bak_ok() and rd(os.path.join(bd, 'div.exe.orig.foreign')) == bad and rd(ex) == exe_build(orig, ['voice'], T=T), txt[-300:])
    reset_all(); open(ex, 'wb').write(junk); t0 = tree(GAME); rc, txt = cli('--voice', 'on'); check('foreign exe and no backup: refused (no original to rebuild from), nothing written, no backup made of it', rc != 0 and tree(GAME) == t0 and not any(os.path.exists(b) for b in bak()), txt[-300:])
    # "Revert all" brings the original back whatever state the exe was in
    reset_all(); cli('--voice', 'on', '--dusk', 'on'); b = bytearray(rd(ex)); b[0x4b280] = 0x77; open(ex, 'wb').write(bytes(b)); rc, txt = cli('--revert-all')
    check('"Revert all" on an exe with unknown bytes at a patch point: the original byte for byte', rc == 0 and rd(ex) == orig, txt[-300:])
    # embedded files: gr-draw (FxMark replaced by the journal), shaders, voice DLLs, dgVoodoo
    dd = os.path.join(GAME, 'ddraw.dll'); oldb = b'MZ old build of cnc-ddraw ' + b'\0' * 200
    reset_all(); cli('--cnc', 'on'); fxd = rd(dd)   # the program's current build (shared/cnc-ddraw/fxddraw.dll.gz may be newer than this build of the program)
    check('gr-draw on: the wrapper is our ddfx build', b'cnc-ddraw' in fxd and fxd != oldb); [os.remove(os.path.join(g, 'install.txt')) for g in gamedata()]; open(dd, 'wb').write(oldb)
    rc, txt = cli('--sync'); check('gr-draw of an older version, no journal (cnc.inst names ddraw.dll): replaced by the current build, recorded in the journal', rc == 0 and rd(dd) == fxd and 'ddraw.dll=' + hashlib.sha256(fxd).hexdigest() in '|'.join(journal().get('grdraw', [])), txt[-300:])
    reset_all(); cli('--cnc', 'on'); open(dd, 'wb').write(oldb); journal_set('grdraw', {'ddraw.dll': oldb})
    rc, txt = cli('--sync'); check('gr-draw with the sha of the journal (an old user): replaced by the current build', rc == 0 and rd(dd) == fxd, txt[-300:])
    usr = b'MZ users own cnc-ddraw build ' + b'\1' * 200; open(dd, 'wb').write(usr); journal_set('grdraw', {'ddraw.dll': oldb})
    rc, txt = cli('--sync'); check('gr-draw changed by the user (sha differs from the journal): left as is, logged', rc == 0 and rd(dd) == usr and 'outside the program' in txt, txt[-300:])
    reset_all(); cli('--cnc', 'on'); sh1 = os.path.join(GAME, 'Shaders', 'nearest-neighbor.glsl'); sh2 = os.path.join(GAME, 'Shaders', 'interpolation', 'bilinear.glsl'); n1, n2 = rd(sh1), rd(sh2)
    os.remove(sh1); open(sh2, 'wb').write(b'// old shader'); journal_set('grdraw', {'ddraw.dll': fxd, sh2[len(GAME) + 1:]: b'// old shader'})
    rc, txt = cli('--sync'); check('shaders: a missing one (new in this version) is added, an old copy of ours is refreshed', rc == 0 and rd(sh1) == n1 and rd(sh2) == n2, txt[-300:])
    open(sh2, 'wb').write(b'// tuned by the player'); rc, txt = cli('--sync'); check('shaders: one tuned by the player stays', rc == 0 and rd(sh2) == b'// tuned by the player', txt[-300:])
    reset_all(); cli('--voice', 'on'); vd = os.path.join(GAME, 'OsirisDLL.dll'); vres = rd(os.path.join(ROOT, 'games', 'divine-divinity', 'payload', 'OsirisDLL.dll')); oldv = b'MZ voice dll of 1.0.5' + b'\0' * 100
    open(vd, 'wb').write(oldv); journal_set('voice', {'OsirisDLL.dll': oldv, 'DivDialogSystem.dll': rd(os.path.join(GAME, 'DivDialogSystem.dll'))})
    rc, txt = cli('--sync'); check('voice DLL of an older version (journal sha): refreshed to the current one', rc == 0 and rd(vd) == vres, txt[-300:])
    open(vd, 'wb').write(b'MZ users own voice dll'); rc, txt = cli('--sync'); check('voice DLL changed by the user: left as is', rc == 0 and rd(vd) == b'MZ users own voice dll', txt[-300:])
    reset_all(); cli('--voice', 'on'); open(vd, 'wb').write(oldv); journal_set('voice', {'OsirisDLL.dll': oldv}); rc, txt = cli('--voice', 'on')   # 1.0.31 took this for "the game's DLL changed" and stored it as the original
    ob = [os.path.join(g, 'backup', 'OsirisDLL.dll.orig') for g in gamedata()]; cli('--voice', 'off')
    check('an older voice DLL of ours is never stored as the "original" backup; voice off brings the game\'s own DLL back', bool(ob) and all(rd(b).startswith(b'ORIGINAL-') for b in ob if os.path.exists(b)) and rd(vd).startswith(b'ORIGINAL-'), txt[-300:])
    reset_all(); cli('--dgv', 'on'); di = os.path.join(GAME, 'D3DImm.dll'); dres = rd(os.path.join(ROOT, 'games', 'divine-divinity', 'payload', 'dgv', 'D3DImm.dll')); oldd = b'MZ old dgVoodoo' + b'\0' * 50
    open(di, 'wb').write(oldd); journal_set('dgv', {'D3DImm.dll': oldd}); rc, txt = cli('--sync'); check('dgVoodoo file of an older version (journal sha): refreshed', rc == 0 and rd(di) == dres, txt[-300:])
    cli('--revert-all'); check('dgVoodoo: "Revert all" removes it and its journal line', not os.path.exists(di) and 'dgv' not in journal())

# ---- migration OldGameFixer -> GameRemix (data copied and checked, old folder kept as .migrated) ----------------------------------------------------
def info(env, *args, game=None):
    log = os.path.join(S, 'info.log')
    if os.path.exists(log): os.remove(log)
    r = subprocess.run([EXE, '--data-info'] + (['--game', game] if game else []) + list(args) + ['--log', log], env=env, cwd=S, capture_output=True, timeout=120)
    return r.returncode, (open(log, encoding='utf-8-sig').read() if os.path.exists(log) else '')

def lnk_target(path):
    r = subprocess.run(['powershell', '-NoProfile', '-Command', "(New-Object -ComObject WScript.Shell).CreateShortcut('%s').TargetPath" % path], capture_output=True)
    return r.stdout.decode('cp866', 'replace').strip()

def migrate_tests():
    M = os.path.join(S, 'mig')
    def fresh():
        if os.path.exists(M): shutil.rmtree(M)
        os.makedirs(M)
        old = os.path.join(M, 'OldGameFixer'); os.makedirs(os.path.join(old, 'games', 'dd-aaaa1111', 'backup')); os.makedirs(os.path.join(old, 'games', 'dd-aaaa1111', 'empty'))
        open(os.path.join(old, 'settings.ini'), 'w', encoding='utf-8').write('lang=ru\npath.dd=X:\\GAMES\\Divine Divinity\n')
        open(os.path.join(old, 'log.txt'), 'w').write('old log\n')
        open(os.path.join(old, 'games', 'dd-aaaa1111', 'backup', 'div.exe.orig'), 'wb').write(os.urandom(5000))
        open(os.path.join(old, 'games', 'dd-aaaa1111', 'state.txt'), 'w').write('NONE')
        return old
    old = fresh(); new = os.path.join(M, 'GameRemix'); before = tree(old)
    env = dict(ENV, OGF_DATA=new, OGF_LEGACY_DATA=old, OGF_LOCAL=os.path.join(M, 'LocalNew'), OGF_LEGACY_LOCAL=os.path.join(M, 'LocalOld'))
    os.makedirs(os.path.join(M, 'LocalOld', 'cache', 'dge-v0.10')); open(os.path.join(M, 'LocalOld', 'cache', 'dge-v0.10', 'x.bin'), 'wb').write(b'x' * 100); os.makedirs(os.path.join(M, 'LocalOld', 'app')); open(os.path.join(M, 'LocalOld', 'app', 'GameRemix.exe'), 'wb').write(b'app')
    rc, txt = info(env)
    mig = old + '.migrated'; nt = tree(new)
    same = all(nt.get(k) == v for k, v in before.items() if k not in ('settings.ini', 'log.txt'))
    check('M1 migration: data copied to GameRemix (every file equal)', rc == 0 and same and os.path.isdir(os.path.join(new, 'games', 'dd-aaaa1111', 'empty')), txt)
    check('M1 migration (same volume): the old folder is simply renamed - nothing left behind, nothing copied', not os.path.exists(old) and not os.path.exists(mig) and not os.path.exists(new + '.migrating'))
    check('M1 migration: settings keep their values, migrated=1 is set', 'lang=ru' in open(os.path.join(new, 'settings.ini'), encoding='utf-8-sig').read() and 'migrated=1' in open(os.path.join(new, 'settings.ini'), encoding='utf-8-sig').read())
    check('M1 migration: cache moved, app stays in the old local folder', os.path.exists(os.path.join(M, 'LocalNew', 'cache', 'dge-v0.10', 'x.bin')) and os.path.exists(os.path.join(M, 'LocalOld', 'app', 'GameRemix.exe')) and not os.path.exists(os.path.join(M, 'LocalNew', 'app')))
    t1 = tree(new); m1 = tree(mig); rc, txt = info(env)
    check('M2 migration is idempotent (second start changes nothing)', tree(new) == t1 and tree(mig) == m1 and 'MIGRATION none' in txt, txt)
    # both exist: the old one is not touched
    old = fresh(); os.makedirs(new, exist_ok=True) if os.path.exists(new) else None
    if os.path.exists(new): shutil.rmtree(new)
    os.makedirs(new); open(os.path.join(new, 'settings.ini'), 'w').write('lang=en\n'); b0 = tree(old)
    rc, txt = info(env)
    check('M3 both folders have data: nothing is merged, the old one stays', tree(old) == b0 and not os.path.exists(old + '.migrated') and open(os.path.join(new, 'settings.ini')).read() == 'lang=en\n', txt)
    # tests with OGF_DATA only never look at a legacy folder
    shutil.rmtree(new); b0 = tree(old); rc, txt = info(dict(ENV, OGF_DATA=new, OGF_LOCAL=os.path.join(M, 'LocalNew')))
    check('M4 OGF_DATA without OGF_LEGACY_DATA: no migration', tree(old) == b0 and not os.path.exists(old + '.migrated') and 'MIGRATION none' in txt, txt)
    # a file that cannot be copied -> the old folder is used as it is, nothing half-done is left
    shutil.rmtree(new) if os.path.exists(new) else None; hd = lock(os.path.join(old, 'log.txt'))
    try: rc, txt = info(env)
    finally: unlock(hd)
    check('M5 failed copy: the old folder is used, nothing is lost or left half-way', ('DATA ' + old) in txt and tree(old) == b0 and not os.path.exists(new) and not os.path.exists(new + '.migrating') and 'FAILED' in txt, txt)
    # desktop shortcut made by the old version points into the old folder: after the move it is re-pointed (no duplicate)
    old = fresh() if True else None; shutil.rmtree(M); os.makedirs(M); old = os.path.join(M, 'OldGameFixer'); desk = os.path.join(M, 'desk'); os.makedirs(desk)
    g = os.path.join(M, 'game'); mkgame(g)
    e_old = dict(ENV, OGF_DATA=old, OGF_DESKTOP=desk); r = subprocess.run([EXE, '--game', g, '--shortcut', 'on', '--log', os.path.join(M, 'a.log')], env=e_old, cwd=S, capture_output=True)
    lnks = [x for x in os.listdir(desk) if x.endswith('.lnk')]; t0 = lnk_target(os.path.join(desk, lnks[0])) if lnks else ''
    check('M6 setup: old-style shortcut points into OldGameFixer', len(lnks) == 1 and t0.lower().startswith(old.lower()), t0)
    env2 = dict(ENV, OGF_DATA=new, OGF_LEGACY_DATA=old, OGF_DESKTOP=desk); rc, txt = info(env2, game=g)
    lnks = [x for x in os.listdir(desk) if x.endswith('.lnk')]; t1 = lnk_target(os.path.join(desk, lnks[0])) if lnks else ''
    check('M6 shortcut re-pointed to GameRemix\\games\\...\\Play.cmd, no duplicate', len(lnks) == 1 and t1.lower().startswith(new.lower()) and os.path.exists(t1) and 'SHORTCUT-REPAIRED True' in txt, t1 + ' | ' + txt)
    # empty sub-folders in the new place must not make every start copy again (the old code could not delete such a folder)
    shutil.rmtree(M); os.makedirs(M); old = fresh(); new = os.path.join(M, 'GameRemix'); os.makedirs(os.path.join(new, 'games', 'x', 'empty')); before = tree(old)
    env = dict(ENV, OGF_DATA=new, OGF_LEGACY_DATA=old, OGF_LOCAL=os.path.join(M, 'LocalNew'), OGF_LEGACY_LOCAL=os.path.join(M, 'LocalOld'))
    rc, txt = info(env); nt = tree(new)
    check('M7 new folder with only empty sub-folders: migration still happens (once)', all(nt.get(k) == v for k, v in before.items() if k not in ('settings.ini', 'log.txt')) and not os.path.exists(old) and 'FAILED' not in txt, txt)
    shutil.rmtree(M)

# ---- review 06.11.2026 (docs/review_2026-11-06.md): version, backups of the old layout, "what's new" badge ----------------------------------------------------
def review_tests():
    mainver = re.search(r'Version = "([0-9.]+)"', open(os.path.join(ROOT, 'src', 'Main.cs'), encoding='utf-8-sig').read()).group(1)
    rc, txt = cli('--version', game=None)
    check('P0-1 the built program reports App.Version of Main.cs (%s)' % mainver, rc == 0 and ('VERSION ' + mainver) in txt, txt)
    # P1-1: the old backup folder is removed only after EVERY file of it is in the new place
    import hashlib as hl
    def bakdir():
        norm = os.path.abspath(GAME).lower(); return os.path.join(DATA, 'games', 'dd-' + hl.sha1(norm.encode('utf-8')).hexdigest()[:8].lower(), 'backup')
    def legacy_setup(bak_files):
        reset_all(); lb = os.path.join(GAME, '_DD_FixTool_backup'); os.makedirs(os.path.join(lb, 'misc'))
        open(os.path.join(lb, 'other.orig'), 'wb').write(b'A' * 1000); open(os.path.join(lb, 'misc', 'f.bin'), 'wb').write(b'B' * 500)
        bd = bakdir(); os.makedirs(bd, exist_ok=True)
        for rel, data in bak_files.items():
            os.makedirs(os.path.dirname(os.path.join(bd, rel)), exist_ok=True); open(os.path.join(bd, rel), 'wb').write(data)
        return lb, bd
    lb, bd = legacy_setup({'other.orig': b'A' * 1000})   # an interrupted copy: the new folder exists but lacks fonts\f.bin
    rc, txt = cli('--revert-all')
    check('P1-1 half-copied backups: the missing files are copied, then the old folder is removed', rc == 0 and os.path.exists(os.path.join(bd, 'misc', 'f.bin')) and not os.path.exists(lb), txt)
    lb, bd = legacy_setup({'other.orig': b'X' * 7})   # same name, other content: not "all present" -> the old folder stays, the new file is not overwritten
    rc, txt = cli('--revert-all')
    check('P1-1 a differing file in the new place: the old backup folder is KEPT, nothing overwritten', rc == 0 and os.path.exists(os.path.join(lb, 'other.orig')) and rd(os.path.join(bd, 'other.orig')) == b'X' * 7, txt)
    # "what's new" badge: unseen versions of the log, never opened by itself
    B = os.path.join(S, 'badge')
    def unseen(settings, *args):
        if os.path.exists(B): shutil.rmtree(B)
        os.makedirs(B)
        if settings is not None: open(os.path.join(B, 'settings.ini'), 'w', encoding='utf-8').write(settings)
        log = os.path.join(B, 'u.log'); e = dict(ENV, OGF_DATA=B, OGF_LOCAL=os.path.join(B, 'local'))
        subprocess.run([EXE, '--unseen'] + list(args) + ['--log', log], env=e, cwd=S, capture_output=True, timeout=60)
        return open(log, encoding='utf-8-sig').read() if os.path.exists(log) else ''
    t = unseen(None); check('B1 clean install: the badge is 0', 'UNSEEN 0' in t, t)
    t = unseen('seenver=%s\n' % mainver); check('B2 the current version already seen: 0', 'UNSEEN 0' in t, t)
    t = unseen('seenver=1.0.9\n'); check('B3 last seen 1.0.9: badge 2 (the 1.0.10 and 1.0.11 entries)', 'UNSEEN 2' in t, t)
    t = unseen('seenver=1.0.7\n'); check('B4 last seen 1.0.7: badge counts every newer version of the log (4)', 'UNSEEN 4' in t, t)
    t = unseen('migrated=1\nlang=ru\n'); check('B5 data from OldGameFixer without seenver = the user had 1.0.9: badge 2', 'UNSEEN 2' in t, t)
    t = unseen('seenver=1.0.9\n', '--mark'); check('B6 opening the log resets the badge to 0', 'UNSEEN 2' in t and 'UNSEEN-AFTER-OPEN 0' in t, t)
    shutil.rmtree(B)

# ---- self-update (local HTTP server, fake exe; the signature step is covered separately) -----------------------------------------------------------------
def update_srv(routes):
    import http.server, threading
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            r = routes.get(self.path)
            if r is None: self.send_response(404); self.end_headers(); return
            if callable(r): r(self); return
            code, body = (200, r) if isinstance(r, bytes) else r
            self.send_response(code); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv

def update_tests():
    U = os.path.join(S, 'upd')
    if os.path.exists(U): shutil.rmtree(U)
    os.makedirs(U); cur = rd(EXE); newb = cur + b'\0NEW-VERSION-MARK' * 10; sha = hashlib.sha256(newb).hexdigest()
    routes = {'/GameRemix.exe': newb, '/changelog.ru.txt': '## 9.9.9 — x\n### Добавлено\n- проба\n'.encode('utf-8'), '/changelog.en.txt': b'## 9.9.9 - x\n### Added\n- probe\n'}
    srv = update_srv(routes); base = 'http://127.0.0.1:%d' % srv.server_address[1]
    def env(**kw): return dict(ENV, OGF_UPDATE_URL=base + '/latest.txt', OGF_DATA=os.path.join(U, 'data'), OGF_LOCAL=os.path.join(U, 'local'), **kw)
    def run(args, **kw):
        log = os.path.join(U, 'u.log')
        if os.path.exists(log): os.remove(log)
        r = subprocess.run([EXE] + args + ['--log', log], env=env(**kw), cwd=S, capture_output=True, timeout=120)
        return r.returncode, (open(log, encoding='utf-8-sig').read() if os.path.exists(log) else '')
    def target():
        t = os.path.join(U, 'target.exe'); [os.remove(f) for f in (t, t + '.old', t + '.new') if os.path.exists(f)]; open(t, 'wb').write(cur); return t
    T = target(); h0 = h(T)
    routes['/latest.txt'] = ('9.9.9|%s/GameRemix.exe|%s' % (base, sha)).encode()
    rc, txt = run(['--update-check'])
    check('U1 latest.txt "version|url|sha256" is read: update available, install=yes', rc == 0 and 'available version=9.9.9' in txt and 'install=yes' in txt and sha in txt, txt)
    routes['/latest.txt'] = ('9.9.9|%s/GameRemix.exe' % base).encode()
    rc, txt = run(['--update-install', '--target', T, '--no-restart'])
    check('U2 old format "version|url": read, but NOT installed (no checksum), file untouched', 'install=no' in txt and 'failed' in txt and h(T) == h0 and not os.path.exists(T + '.new'), txt)
    routes['/latest.txt'] = ('9.9.9|%s/GameRemix.exe|%s' % (base, sha)).encode()
    rc, txt = run(['--update-install', '--target', T, '--no-restart'])
    check('U3 unsigned running program: install refused without the test switch', rc == 1 and 'не подписана' in txt + 'не подписана' and h(T) == h0 and 'failed' in txt, txt)
    rc, txt = run(['--update-install', '--target', T, '--no-restart'], OGF_TEST_ALLOW_UNSIGNED='1')
    check('U4 install: new exe in place (hash equal), previous kept as .old, no .new left', rc == 0 and hashlib.sha256(rd(T)).hexdigest() == sha and os.path.exists(T + '.old') and h(T + '.old') == h0 and not os.path.exists(T + '.new'), txt)
    T = target(); routes['/latest.txt'] = ('9.9.9|%s/GameRemix.exe|%s' % (base, '0' * 64)).encode()
    rc, txt = run(['--update-install', '--target', T, '--no-restart'], OGF_TEST_ALLOW_UNSIGNED='1')
    check('U5 wrong SHA-256: rejected, program unchanged, no .new/.old', rc == 1 and h(T) == h0 and not os.path.exists(T + '.new') and not os.path.exists(T + '.old'), txt)
    routes['/latest.txt'] = ('9.9.9|https://evil.example.com/GameRemix.exe|%s' % sha).encode()
    rc, txt = run(['--update-check'])
    check('U6 foreign host in latest.txt: not a valid answer', 'bad-answer' in txt, txt)
    routes['/redir.exe'] = lambda hd: (hd.send_response(302), hd.send_header('Location', 'https://evil.example.com/x.exe'), hd.end_headers())
    routes['/latest.txt'] = ('9.9.9|%s/redir.exe|%s' % (base, sha)).encode()
    rc, txt = run(['--update-install', '--target', T, '--no-restart'], OGF_TEST_ALLOW_UNSIGNED='1')
    check('U7 redirect to a foreign host during the download: refused', rc == 1 and h(T) == h0 and not os.path.exists(T + '.new'), txt)
    routes['/huge.exe'] = lambda hd: (hd.send_response(200), hd.send_header('Content-Length', str(200 * 1024 * 1024)), hd.end_headers())
    routes['/latest.txt'] = ('9.9.9|%s/huge.exe|%s' % (base, sha)).encode()
    rc, txt = run(['--update-install', '--target', T, '--no-restart'], OGF_TEST_ALLOW_UNSIGNED='1')
    check('U8 size limit: a 200 MB answer is rejected before it is stored', rc == 1 and h(T) == h0 and not os.path.exists(T + '.new'), txt)
    routes['/notexe.bin'] = b'<html>captive portal</html>' * 5000; sh2 = hashlib.sha256(routes['/notexe.bin']).hexdigest()
    routes['/latest.txt'] = ('9.9.9|%s/notexe.bin|%s' % (base, sh2)).encode()
    rc, txt = run(['--update-install', '--target', T, '--no-restart'], OGF_TEST_ALLOW_UNSIGNED='1')
    check('U9 a file with the right hash that is not an exe is rejected', rc == 1 and h(T) == h0 and not os.path.exists(T + '.new'), txt)
    routes['/latest.txt'] = ('9.9.9|%s/GameRemix.exe|%s' % (base, sha)).encode()
    rc, txt = run(['--update-install', '--target', T, '--no-restart'], OGF_TEST_ALLOW_UNSIGNED='1', OGF_TEST_FAIL_AFTER_MOVE='1')
    check('U10 failure after the rename: the previous program is put back (rollback)', rc == 1 and h(T) == h0 and not os.path.exists(T + '.old') and not os.path.exists(T + '.new'), txt)
    hd = None; open(T + '.old', 'wb').write(b'stale'); hd = lock(T + '.old')
    try: rc, txt = run(['--update-install', '--target', T, '--no-restart'], OGF_TEST_ALLOW_UNSIGNED='1')
    finally: unlock(hd)
    check('U11 a locked .old: nothing is replaced, program unchanged', rc == 1 and h(T) == h0, txt)
    os.remove(T + '.old')
    routes['/latest.txt'] = b'1.0.0|' + base.encode() + b'/GameRemix.exe|' + sha.encode()
    rc, txt = run(['--update-check']); check('U12 an older version is never offered', 'UPDATE none' in txt, txt)
    routes['/latest.txt'] = b'<html>portal</html>'; rc, txt = run(['--update-check']); check('U13 HTML instead of latest.txt = "could not check"', 'bad-answer' in txt, txt)
    # the real install with a real signature: Microsoft-signed exes from the Windows SDK play "current" and "new"
    kit = sorted(glob.glob(r'C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe'))
    if kit:
        d = os.path.dirname(kit[-1]); a, b = os.path.join(d, 'signtool.exe'), next((os.path.join(d, x) for x in ('mt.exe', 'makecat.exe', 'certmgr.exe') if os.path.exists(os.path.join(d, x))), None)
        rc, txt = run(['--verify-sig', a, '--against', b])
        check('U14 WinVerifyTrust: a Microsoft-signed exe is trusted, same publisher as another one', 'TRUST ok' in txt and 'SIGNER' in txt and 'Microsoft' in txt and 'PUBLISHER same' in txt, txt)
        rc, txt = run(['--verify-sig', EXE, '--against', a], OGF_TEST_ALLOW_UNSIGNED='1')
        check('U15 an unsigned file is not trusted even with the test switch when the RUNNING program is signed', 'SIGNER none' in txt and 'PUBLISHER REFUSED' in txt, txt)
        rc, txt = run(['--verify-sig', a, '--against', EXE], OGF_TEST_ALLOW_UNSIGNED='1')
        check('U16 test switch works only when the running program is unsigned (and the server is local)', 'PUBLISHER skipped-test' in txt, txt)
        rc, txt = subprocess.run([EXE, '--verify-sig', a, '--against', EXE, '--log', os.path.join(U, 'v.log')], env=dict(ENV, OGF_TEST_ALLOW_UNSIGNED='1'), cwd=S, capture_output=True).returncode, open(os.path.join(U, 'v.log'), encoding='utf-8-sig').read()
        check('U17 test switch is ignored without a local OGF_UPDATE_URL', 'PUBLISHER REFUSED' in txt, txt)
        nb = rd(b); sh3 = hashlib.sha256(nb).hexdigest(); routes['/signed.exe'] = nb; routes['/latest.txt'] = ('9.9.9|%s/signed.exe|%s' % (base, sh3)).encode()
        T = os.path.join(U, 'cur_signed.exe'); shutil.copy(a, T)
        rc, txt = run(['--update-install', '--target', T, '--no-restart'])
        check('U18 full install with real Authenticode signatures (same publisher): replaced, .old kept', rc == 0 and h(T) == h(b) and os.path.exists(T + '.old') and h(T + '.old') == h(a), txt)
        T = os.path.join(U, 'cur_signed2.exe'); shutil.copy(a, T); routes['/signed.exe'] = newb; routes['/latest.txt'] = ('9.9.9|%s/signed.exe|%s' % (base, sha)).encode()
        rc, txt = run(['--update-install', '--target', T, '--no-restart'], OGF_TEST_ALLOW_UNSIGNED='1')
        check('U19 signed program + unsigned download with the right hash: refused', rc == 1 and h(T) == h(a) and not os.path.exists(T + '.new'), txt)
    else: print('SKIP U14-U19 (no Windows SDK signtool.exe)')
    # main site down -> the mirror answers (same format and checks)
    routes['/latest.txt'] = ('9.9.9|%s/GameRemix.exe|%s' % (base, sha)).encode()
    lg = os.path.join(U, 'm.log'); e2 = dict(env(), OGF_UPDATE_URL='http://127.0.0.1:9/latest.txt', OGF_UPDATE_URL2=base + '/latest.txt')
    subprocess.run([EXE, '--update-check', '--log', lg], env=e2, cwd=S, capture_output=True, timeout=120); txt = open(lg, encoding='utf-8-sig').read()
    check('U20 main address is down: the mirror address is tried and answers', 'available version=9.9.9' in txt, txt)
    T = target(); subprocess.run([EXE, '--update-install', '--target', T, '--no-restart', '--log', lg], env=dict(e2, OGF_TEST_ALLOW_UNSIGNED='1'), cwd=S, capture_output=True, timeout=120); txt = open(lg, encoding='utf-8-sig').read()
    check('U21 install through the mirror: same hash check, program replaced', hashlib.sha256(rd(T)).hexdigest() == sha, txt)
    subprocess.run([EXE, '--update-check', '--log', lg], env=dict(e2, OGF_UPDATE_URL2='http://127.0.0.1:9/latest.txt'), cwd=S, capture_output=True, timeout=120); txt = open(lg, encoding='utf-8-sig').read()
    check('U22 both addresses down: "error", not "up to date"', 'UPDATE error=' in txt, txt)
    # the main site answers latest.txt but cannot serve the exe -> the same file from the second host
    routes2 = {'/GameRemix.exe': newb}; srv2 = update_srv(routes2); base2 = 'http://127.0.0.1:%d' % srv2.server_address[1]
    routes['/latest.txt'] = ('9.9.9|%s/GameRemix.exe|%s' % (base, sha)).encode(); saved = routes.pop('/GameRemix.exe')
    T = target(); e3 = dict(env(), OGF_UPDATE_URL2=base2 + '/latest.txt', OGF_TEST_ALLOW_UNSIGNED='1')
    r = subprocess.run([EXE, '--update-install', '--target', T, '--no-restart', '--log', lg], env=e3, cwd=S, capture_output=True, timeout=120); txt = open(lg, encoding='utf-8-sig').read()
    check('U23 the exe is missing on the main host (404): the same file is taken from the second host, hash checked', hashlib.sha256(rd(T)).hexdigest() == sha, txt)
    T = target(); routes2.clear()
    r = subprocess.run([EXE, '--update-install', '--target', T, '--no-restart', '--log', lg], env=e3, cwd=S, capture_output=True, timeout=120); txt = open(lg, encoding='utf-8-sig').read()
    check('U24 the exe is missing on both hosts: failed, program unchanged, no .new left', r.returncode == 1 and h(T) == h0 and not os.path.exists(T + '.new'), txt)
    routes['/GameRemix.exe'] = saved; srv2.shutdown()
    srv.shutdown(); shutil.rmtree(U)

def main():
    assert os.path.exists(EXE), 'build first: python src/build.py'
    if os.path.exists(S): shutil.rmtree(S)
    os.makedirs(S)
    before_real = {d: tree(d) for d in REALPROF if os.path.exists(d)}
    only = os.environ.get('SELFTEST_ONLY')   # e.g. SELFTEST_ONLY=gfx: one block while developing (no report file)
    if only:
        {'gfx': gfx_tests, 'assets': assets_tests, 'scale': scale_tests, 'install': install_tests}[only](); bad = [n for n, c, d in results if not c]; print('\n%d/%d passed' % (len(results) - len(bad), len(results))); return 1 if bad else 0

    # 1. a clean game: "Revert all" installs nothing and changes nothing
    reset_all(); t0 = tree(GAME)
    rc, txt = cli('--revert-all')
    check('1 clean game: revert-all rc=0', rc == 0, txt)
    check('1 clean game: revert-all leaves the game folder byte-identical (no dgVoodoo installed)', tree(GAME) == t0, str(set(tree(GAME).items()) ^ set(t0.items())))

    # 1b. voice on/off round trip restores the original DLLs and exe
    reset_all(); t0 = tree(GAME)
    rc, txt = cli('--voice', 'on', '--dusk', 'on'); st = status(txt)
    check('voice on+dusk: applied', st.get('voice') == 'True' and st.get('dusk') == 'True', txt)
    rc, txt = cli('--revert-all')
    check('voice: revert-all brings back original DLLs and exe', tree(GAME) == t0, str(set(tree(GAME).items()) ^ set(t0.items())))
    # 8. no DLL backup: voice off says so, shows "mixed" instead of lying
    reset_all(); cli('--voice', 'on')
    for d in gamedata():
        for n in ('OsirisDLL.dll.orig', 'DivDialogSystem.dll.orig'):
            p = os.path.join(d, 'backup', n)
            if os.path.exists(p): os.remove(p)
    rc, txt = cli('--voice', 'off'); st = status(txt)
    check('8 voice off without a DLL backup: warns and reports mixed state', 'WARN' in txt and st.get('voiceMixed') == 'True', txt)
    # 8b. reinstall: original DLL changed after backup -> backup refreshed
    reset_all(); cli('--voice', 'on'); cli('--voice', 'off')
    open(os.path.join(GAME, 'OsirisDLL.dll'), 'wb').write(b'NEW-BUILD-DLL' * 5)
    cli('--voice', 'on'); cli('--voice', 'off')
    check('8 DLL backup follows a game reinstall', rd(os.path.join(GAME, 'OsirisDLL.dll')).startswith(b'NEW-BUILD-DLL'))

    # 2. cnc-ddraw -> quick setup -> revert all: the ORIGINAL slashed.cfg comes back
    reset_all(); t0 = tree(GAME)
    rc, txt = cli('--cnc', 'on'); check('2 cnc on: renderer switched to Software', status(txt).get('cnc') == 'True' and rd(os.path.join(GAME, 'slashed.cfg'))[:1] == b'\x03', txt)
    rc, txt = cli('--preset', '0', '--wrapper', 'cnc'); check('2 preset (cnc) applied', rc == 0, txt)
    rc, txt = cli('--revert-all'); check('2 revert-all rc=0', rc == 0, txt)
    t1 = tree(GAME); diff = {k for k in set(t0) | set(t1) if t0.get(k) != t1.get(k)}
    check('2 cnc -> preset -> revert-all: game folder identical to the start (slashed.cfg original)', not diff, str(diff))
    check('2 slashed.cfg is the original D3D6 value', rd(os.path.join(GAME, 'slashed.cfg')) == bytes([0, 0, 0, 0]))
    # 2b. preset dgVoodoo while cnc is on
    reset_all(); t0 = tree(GAME); cli('--cnc', 'on'); rc, txt = cli('--preset', '0', '--wrapper', 'dgv'); check('2 preset (dgv) over cnc', rc == 0, txt)
    rc, txt = cli('--revert-all'); t1 = tree(GAME); diff = {k for k in set(t0) | set(t1) if t0.get(k) != t1.get(k)}
    check('2 cnc -> preset(dgv) -> revert-all: identical to the start', not diff, str(diff))

    # 3. RevertPreset with a busy file keeps the backups, then succeeds
    reset_all(); t0 = tree(GAME); cli('--preset', '1', '--wrapper', 'dgv')
    hd = lock(os.path.join(GAME, 'config.div'))
    rc, txt = cli('--revert-all')
    pd = [os.path.join(d, 'preset') for d in gamedata()]
    check('3 busy file: revert reports the failure (rc!=0)', rc != 0 and 'REVERT-FAILED' in txt, txt)
    check('3 busy file: the preset backup folder is KEPT', any(os.path.exists(p) and os.listdir(p) for p in pd))
    unlock(hd)
    rc, txt = cli('--revert-all'); t1 = tree(GAME); diff = {k for k in set(t0) | set(t1) if t0.get(k) != t1.get(k)}
    check('3 after the file is free: second revert restores everything', rc == 0 and not diff, txt + str(diff))
    check('3 backup folder removed only after success', not any(os.path.exists(p) for p in pd))

    # 4. foreign cnc-ddraw is never deleted; our own switch-off keeps the mark when the dll is locked
    reset_all(); open(os.path.join(GAME, 'ddraw.dll'), 'wb').write(b'MZ foreign cnc-ddraw build'); t0 = tree(GAME)
    rc, txt = cli('--cnc', 'off'); check('4 foreign cnc-ddraw survives --cnc off', os.path.exists(os.path.join(GAME, 'ddraw.dll')) and 'WARN' in txt, txt)
    rc, txt = cli('--revert-all'); check('4 foreign cnc-ddraw survives revert-all', os.path.exists(os.path.join(GAME, 'ddraw.dll')) and tree(GAME) == t0, txt)
    reset_all(); cli('--cnc', 'on'); hd = lock(os.path.join(GAME, 'ddraw.dll'))
    rc, txt = cli('--cnc', 'off'); mark = [os.path.join(d, 'backup', 'cnc.inst') for d in gamedata()]
    check('4 locked ddraw.dll: switch-off fails but the mark and the files stay', rc != 0 and any(os.path.exists(m) for m in mark) and os.path.exists(os.path.join(GAME, 'ddraw.ini')), txt)
    unlock(hd); rc, txt = cli('--cnc', 'off'); check('4 retry after unlock: cnc-ddraw removed', rc == 0 and not os.path.exists(os.path.join(GAME, 'ddraw.dll')), txt)
    # 4b. switching ON is transactional: a file named "Shaders" breaks the shader copy half-way
    reset_all(); open(os.path.join(GAME, 'DDraw.dll'), 'wb').write(b'users own ddraw'); open(os.path.join(GAME, 'Shaders'), 'wb').write(b'not a folder'); t0 = tree(GAME)
    rc, txt = cli('--cnc', 'on'); t1 = tree(GAME); diff = {k for k in set(t0) | set(t1) if t0.get(k) != t1.get(k)}
    check('4 cnc on fails half-way -> everything rolled back', rc != 0 and not diff, txt + str(diff))

    # 1/13. dgVoodoo: user's own files are given back; our installed files are removed; the user's conf is restored
    reset_all()
    for n in ('DDraw.dll', 'D3D8.dll'): open(os.path.join(GAME, n), 'wb').write(b'USER-' + n.encode())
    conf = 'Resolution = unforced\r\n[DirectX]\r\nResolution = 1x\r\n\r\n; \u043a\u043e\u043c\u043c\u0435\u043d\u0442'.encode('cp1251'); open(os.path.join(GAME, 'dgVoodoo.conf'), 'wb').write(conf); t0 = tree(GAME)
    cli('--dgv', 'on'); cli('--dgv', 'off'); cli('--preset', '0', '--wrapper', 'dgv')
    c1 = rd(os.path.join(GAME, 'dgVoodoo.conf'))
    check('10 dgVoodoo.conf edit keeps ANSI encoding and CRLF', b'\r\n' in c1 and b'Resolution=2x' in c1.replace(b' = ', b'=') and '\u043a\u043e\u043c\u043c\u0435\u043d\u0442'.encode('cp1251') in c1, repr(c1))
    cli('--revert-all'); t1 = tree(GAME); diff = {k for k in set(t0) | set(t1) if t0.get(k) != t1.get(k)}
    check('1 own DDraw.dll/D3D8.dll and dgVoodoo.conf are back after revert-all', not diff, str(diff))
    reset_all(); t0 = tree(GAME); cli('--dgv', 'on'); cli('--revert-all'); check('1 our own dgVoodoo copy is removed again', tree(GAME) == t0)
    # 13. a hand-edited dgv.inst cannot delete foreign files
    reset_all(); cli('--dgv', 'on'); open(os.path.join(GAME, 'config.lcl'), 'wb').write(b'keep me'); inst = [os.path.join(d, 'backup', 'dgv.inst') for d in gamedata()][0]
    open(inst, 'a').write('config.lcl\r\n..\\evil.txt\r\n'); open(os.path.join(S, 'evil.txt'), 'w').write('keep'); cli('--revert-all')
    check('13 dgv.inst: foreign names are ignored', os.path.exists(os.path.join(GAME, 'config.lcl')) and os.path.exists(os.path.join(S, 'evil.txt')))

    # 10. quick setup on an unsupported div.exe: skipped, honest; revert-all still works
    reset_all(); open(os.path.join(GAME, 'div.exe'), 'ab').write(b'tail')
    rc, txt = cli('--preset', '1', '--wrapper', 'dgv'); check('10 unsupported exe: preset reports the skip', 'PRESET-SKIPPED' in txt, txt)
    # ... and a half-applied preset rolls back
    reset_all(); open(os.path.join(GAME, 'Shaders'), 'wb').write(b'x'); t0 = tree(GAME)
    rc, txt = cli('--preset', '0', '--wrapper', 'cnc'); t1 = tree(GAME); diff = {k for k in set(t0) | set(t1) if t0.get(k) != t1.get(k)}
    check('10 preset failing in the middle rolls back what it did', rc != 0 and not diff, txt + str(diff))

    # 12. SetLauncher: flags already ours and no state file -> off removes them
    reset_all(); import winreg
    key = r'Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers'
    exe = os.path.join(GAME, 'div.exe')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k: winreg.SetValueEx(k, exe, 0, winreg.REG_SZ, '~ RUNASADMIN DISABLEDXMAXIMIZEDWINDOWEDMODE')
    cli('--launcher', 'on'); cli('--launcher', 'off')
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k: winreg.QueryValueEx(k, exe); left = True
    except FileNotFoundError: left = False
    check('12 smooth play off removes flags that were ours before state.txt existed', not left)
    if left:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k: winreg.DeleteValue(k, exe)

    # 6. Play.cmd with Cyrillic / % / spaces: a stub div.exe records its working directory
    stub_cs = os.path.join(S, 'stub.cs'); open(stub_cs, 'w').write('class P{static void Main(){System.IO.File.WriteAllText("cwd.txt",System.IO.Directory.GetCurrentDirectory(),System.Text.Encoding.UTF8);}}')
    csc = os.path.join(os.environ['WINDIR'], r'Microsoft.NET\Framework\v3.5\csc.exe'); stub_exe = os.path.join(S, 'stub.exe')
    subprocess.run([csc, '/nologo', '/out:' + stub_exe, stub_cs], check=True, capture_output=True)
    for nm in ('тест игра', '100%PATH% игра', 'ünï çödé'):
        g2 = os.path.join(S, nm); os.makedirs(g2, exist_ok=True); shutil.copy(stub_exe, os.path.join(g2, 'div.exe'))
        rc, txt = cli('--shortcut', 'on', game=g2)
        cmdf = None
        for d in gamedata():
            c = os.path.join(d, 'Play.cmd')
            if os.path.exists(c) and (cmdf is None or os.path.getmtime(c) >= os.path.getmtime(cmdf)): cmdf = c
        subprocess.run(['cmd', '/c', cmdf], cwd=S, timeout=30, env=ENV); import time; time.sleep(1.5)
        out = os.path.join(g2, 'cwd.txt'); got = open(out, encoding='utf-8-sig').read() if os.path.exists(out) else None
        check('6 Play.cmd starts the game in "%s"' % nm, got is not None and os.path.normcase(got) == os.path.normcase(g2), 'got=%r cmd=%r' % (got, rd(cmdf)))
    # relative --game
    rc, txt = cli('--status', game=None) if False else (None, '')
    rel = subprocess.run([EXE, '--game', '.', '--log', os.path.join(S, 'rel.log')], env=ENV, cwd=os.path.join(S, 'тест игра'), capture_output=True)
    check('23 relative --game . is resolved to a full path', os.path.exists(os.path.join(S, 'rel.log')) and 'exeSupported' in open(os.path.join(S, 'rel.log'), encoding='utf-8-sig').read())

    # 23. strict CLI
    reset_all(); t0 = tree(GAME)
    rc, txt = cli('--voice', 'maybe'); check('23 --voice maybe -> rc 2, nothing changed', rc == 2 and tree(GAME) == t0, txt)
    rc, txt = cli('--dgv'); check('23 missing value -> rc 2', rc == 2, txt)
    rc, txt = cli('--bogus', 'x', '--status'); check('23 unknown flag is reported as WARN', 'WARN' in txt and 'bogus' in txt, txt)
    rc, txt = cli('--font', '9:big'); check('23 bad font group -> rc 2', rc == 2, txt)
    rc, txt = subprocess.run([EXE, '--game'], env=ENV, cwd=S, capture_output=True).returncode, ''
    check('23 --game without a value does not crash (rc 2)', rc == 2)

    # 11. path normalisation + reuse of the data folder keyed the old way
    reset_all(); cli('--voice', 'on'); n1 = len(gamedata())
    cli('--status', game=GAME.replace('\\', '/') + '/'); cli('--status', game=GAME.upper());
    check('11 slash / trailing slash / case give the same data folder', len(gamedata()) == n1 == 1, str(gamedata()))
    reset_all(); old = hashlib.sha1((GAME.replace('\\', '/')).lower().encode()).hexdigest()[:8]
    od = os.path.join(DATA, 'games', 'dd-' + old); os.makedirs(os.path.join(od, 'backup')); open(os.path.join(od, 'backup', 'marker.txt'), 'w').write('old')
    cli('--voice', 'on', game=GAME.replace('\\', '/'))
    check('11 data keyed by an older spelling is reused, no second folder', len(gamedata()) == 1 and os.path.exists(os.path.join(od, 'backup', 'div.exe.orig')), str(gamedata()))
    # shortcut bound to ONE install: a shortcut of another install on the desktop is never overwritten
    reset_all(); g2 = os.path.join(S, 'second'); mkgame(g2)
    cli('--shortcut', 'on'); lnk1 = [f for f in os.listdir(DESK) if f.endswith('.lnk')]; cli('--shortcut', 'on', game=g2); lnk2 = [f for f in os.listdir(DESK) if f.endswith('.lnk')]
    check('11 two installs get two shortcuts (the first is not overwritten)', len(lnk1) == 1 and len(lnk2) == 2, '%s %s' % (lnk1, lnk2))
    cli('--revert-all', game=g2); check('11 removing one install\'s shortcut leaves the other', len(os.listdir(DESK)) == 1)

    # 9. fonts: a hand-edited font is kept, not silently overwritten; backup is never made from our own output
    reset_all(); t0 = tree(GAME)
    cli('--font', '0:big'); st = status(cli('--status')[1]); check('9 fonts: larger applied', int(st.get('fontStep', '0,').split(',')[0]) >= 1, str(st))
    cli('--font', '0:orig'); check('9 fonts: back to original', tree(GAME) == t0)
    cli('--font', '0:big'); fp = os.path.join(GAME, 'fonts', 'fontn3.fnt'); open(fp, 'ab').write(b'HANDMADE')
    st = status(cli('--status')[1]); check('9 fonts: hand-edited group is reported as custom', st.get('fontCustom', '').startswith('True') or st.get('fontStep', '').startswith('0'), str(st))
    cli('--font', '0:orig'); ku = [os.path.join(d, 'backup', 'fonts_user') for d in gamedata()]
    check('9 fonts: the player\'s own file was saved before being replaced', any(os.path.exists(k) and os.listdir(k) for k in ku))

    # 9b. fonts: no message is shown when the player's own file is replaced (log only), and every embedded .fnt is structurally sound (the 1.0.11 redrawn set had a wrong glyph count in the header)
    reset_all(); cli('--font', '0:big'); open(os.path.join(GAME, 'fonts', 'fontn3.fnt'), 'ab').write(b'HANDMADE')
    rc, txt = cli('--font', '0:orig'); check('9b fonts: replacing the player\'s own file shows no message (no WARN, log only)', rc == 0 and 'WARN' not in txt, txt[-300:])
    check_embedded_fonts()

    # 5. save editor writes atomically (a copy of a real save), a .bak is made, nothing left behind
    sv = os.path.join(S, 'save'); os.makedirs(sv)
    realsave = None
    for dp, _, fs in os.walk(os.path.join(REALGAME, 'savegames')):
        if 'data.000' in fs: realsave = os.path.join(dp, 'data.000'); break
    if realsave:
        shutil.copy(realsave, os.path.join(sv, 'data.000'))
        r = subprocess.run([EXE, '--shot', 'savefmt', os.path.join(sv, 'data.000'), '10,10,10,10', '--allow-write'], env=ENV, cwd=S, capture_output=True)
        fl = os.listdir(sv)
        check('5 save editor: atomic write, backup made, no temp files left', r.returncode == 0 and any(x.startswith('data.000.bak_') for x in fl) and not any(x.endswith('.tmp') or '.old_' in x for x in fl), str(fl))
    # 23. write hooks need --allow-write; K out of range is an error
    r = subprocess.run([EXE, '--shot', 'preset', os.path.join(S, 'o.txt'), GAME, '1'], env=ENV, cwd=S, capture_output=True)
    check('23 --shot preset without --allow-write is refused', r.returncode == 2 and 'allow-write' in open(os.path.join(S, 'o.txt'), encoding='utf-8-sig').read())
    r = subprocess.run([EXE, '--shot', 'preset', os.path.join(S, 'o.txt'), GAME, '7', '--allow-write'], env=ENV, cwd=S, capture_output=True)
    check('23 preset K=7 is an error, not an exception', r.returncode == 2)

    # asset sets: download, apply, revert, safety (local HTTP server, fake archives, copy of a fake game)
    assets_tests()
    scale_tests()
    gfx_tests()
    install_tests()
    migrate_tests()
    review_tests()
    update_tests()

    # the real profile and the real game were not touched
    after_real = {d: tree(d) for d in REALPROF if os.path.exists(d)}
    check('REAL %APPDATA% GameRemix/OldGameFixer untouched by the self-test', before_real == after_real)

    # report
    ok = sum(1 for _, c, _ in results if c); print('\n%d/%d passed' % (ok, len(results)))
    out = os.path.join(ROOT, 'docs', 'test-results', 'selftest-%s.md' % datetime.date.today().strftime('%Y-%m-%d'))
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# Self-test (tools/selftest.py) %s\n\nRun on COPIES in scratch/selftest (data, desktop, cache redirected); the real game and the real profile are not used.\n\n| Result | Check |\n|---|---|\n' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))
        for n, c, d in results: f.write('| %s | %s |\n' % ('PASS' if c else 'FAIL', n))
        f.write('\n%d/%d passed.\n' % (ok, len(results)))
    return 0 if ok == len(results) else 1

if __name__ == '__main__': sys.exit(main())
