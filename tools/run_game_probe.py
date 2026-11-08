# Starts GAMEDIR\div.exe detached, watches it N seconds, prints ALIVE/EXITED + visible windows (+ texts of dialogs) + new error.txt lines, kills ONLY its own pid. Resets init.cfg/sinfo.000/mapids.000/dynamic first (the game asks "reset configuration?" after an unclean exit).
# usage: run_game_probe.py GAMEDIR [seconds] [exe]
import sys, os, time, subprocess, ctypes, ctypes.wintypes as wt
d = sys.argv[1]; secs = float(sys.argv[2]) if len(sys.argv) > 2 else 20; exe = sys.argv[3] if len(sys.argv) > 3 else 'div.exe'
u = ctypes.windll.user32
def wins(pid):
    r = []
    cb = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def f(h, l):
        p = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid:
            b = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, b, 256); c = ctypes.create_unicode_buffer(128); u.GetClassNameW(h, c, 128)
            txt=[]
            ccb = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
            def g(hc, l2):
                t = ctypes.create_unicode_buffer(512); u.GetWindowTextW(hc, t, 512)
                if t.value: txt.append(t.value)
                return True
            u.EnumChildWindows(h, ccb(g), 0)
            r.append((b.value, c.value, bool(u.IsWindowVisible(h)), txt))
        return True
    u.EnumWindows(cb(f), 0); return r
import shutil
STEAM = r'C:\Program Files (x86)\Steam\steamapps\common\divine_divinity'
shutil.copy2(os.path.join(STEAM, 'mapids.000'), os.path.join(d, 'mapids.000'))
for n in ('init.cfg', 'sinfo.000'):
    try: os.remove(os.path.join(d, n))
    except OSError: pass
shutil.rmtree(os.path.join(d, 'dynamic'), ignore_errors=True)
err = os.path.join(d, 'error.txt'); e0 = os.path.getsize(err) if os.path.exists(err) else 0
pr = subprocess.Popen([os.path.join(d, exe)], cwd=d, creationflags=0x00000008 | 0x00000200)
t0 = time.time(); last = None
while time.time() - t0 < secs:
    rc = pr.poll()
    if rc is not None: print('EXITED rc=%s after %.1fs' % (rc, time.time() - t0)); break
    time.sleep(1)
else:
    print('ALIVE after %.0fs' % secs)
    w = wins(pr.pid); print('WINDOWS', [x for x in w if x[2]][:6])
    pr.kill(); time.sleep(1)
if os.path.exists(err):
    s = open(err, 'rb').read()[e0:].decode('cp1251', 'replace'); print('error.txt new:', s.strip()[:500] or '(none)')
else: print('error.txt: absent')
