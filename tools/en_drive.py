# Drives a COPY of the game with mouse/keys and takes full-screen shots (the game switches the desktop to its own mode, so a screen grab = the game).
# python tools/en_drive.py GAMEDIR OUTPREFIX  w10 c510,384 w4 sNAME kI w2 sNAME2 ...   w<sec> wait | c<x>,<y> click | d<x>,<y> double | r<x>,<y> right click | k<char> key press | K<vk hex> key | s<name> shot | m<x>,<y> move
# Kills ONLY its own game process at the end; resets init.cfg/sinfo.000/mapids.000/dynamic first.
import sys, os, time, subprocess, shutil, ctypes
from PIL import ImageGrab
G = sys.argv[1]; OUT = sys.argv[2]; STEAM = r'C:\Program Files (x86)\Steam\steamapps\common\divine_divinity'
u = ctypes.windll.user32; u.SetProcessDPIAware()
shutil.copy2(os.path.join(STEAM, 'mapids.000'), os.path.join(G, 'mapids.000'))
for n in ('init.cfg', 'sinfo.000'):
    try: os.remove(os.path.join(G, n))
    except OSError: pass
shutil.rmtree(os.path.join(G, 'dynamic'), ignore_errors=True)
err = os.path.join(G, 'error.txt'); e0 = os.path.getsize(err) if os.path.exists(err) else 0
pr = subprocess.Popen([os.path.join(G, 'div.exe')], cwd=G, creationflags=0x208)
def mouse(x, y, flags):
    u.SetCursorPos(x, y); time.sleep(0.15); u.mouse_event(flags, 0, 0, 0, 0)
def click(x, y, dbl=False, right=False):
    d, up = (0x08, 0x10) if right else (0x02, 0x04)
    u.SetCursorPos(x, y); time.sleep(0.2); u.mouse_event(d, 0, 0, 0, 0); time.sleep(0.08); u.mouse_event(up, 0, 0, 0, 0)
    if dbl: time.sleep(0.1); u.mouse_event(d, 0, 0, 0, 0); time.sleep(0.08); u.mouse_event(up, 0, 0, 0, 0)
import ctypes.wintypes as wt
def fg_pid():
    p = wt.DWORD(); u.GetWindowThreadProcessId(u.GetForegroundWindow(), ctypes.byref(p)); return p.value
def game_hwnd():
    r = []
    cb = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def f(h, l):
        p = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pr.pid and u.IsWindowVisible(h): r.append(h)
        return True
    u.EnumWindows(cb(f), 0); return r[0] if r else None
def focus_ok():
    # NEVER send input unless the foreground window is OUR game (once keys landed in the owner's terminal): try to take focus, else skip the action
    for _ in range(3):
        if fg_pid() == pr.pid: return True
        h = game_hwnd()
        if h: u.keybd_event(0x12, 0, 0, 0); u.SetForegroundWindow(h); u.keybd_event(0x12, 0, 2, 0)
        time.sleep(0.5)
    return fg_pid() == pr.pid
try:
    for a in sys.argv[3:]:
        if pr.poll() is not None: print('GAME EXITED rc=%s before action %s' % (pr.returncode, a)); break
        t, v = a[0], a[1:]
        if t in 'cdrmkK' and not focus_ok(): print('SKIPPED %s: the game is not the foreground window' % a); continue
        if t == 'w': time.sleep(float(v))
        elif t in 'cdrm': x, y = map(int, v.split(',')); (u.SetCursorPos(x, y) if t == 'm' else click(x, y, t == 'd', t == 'r'))
        elif t == 'k': vk = u.VkKeyScanW(ord(v[0])) & 0xff; u.keybd_event(vk, 0, 0, 0); time.sleep(0.08); u.keybd_event(vk, 0, 2, 0)
        elif t == 'K': vk = int(v, 16); u.keybd_event(vk, 0, 0, 0); time.sleep(0.08); u.keybd_event(vk, 0, 2, 0)
        elif t == 's' and fg_pid() != pr.pid: print('shot %s SKIPPED: the game is not the foreground window (screen not captured)' % v)
        elif t == 's': ImageGrab.grab().save('%s_%s.png' % (OUT, v)); print('shot', v)
    print('alive at end:', pr.poll() is None)
finally:
    if pr.poll() is None: pr.kill()
    s = open(err, 'rb').read()[e0:].decode('cp1251', 'replace') if os.path.exists(err) else ''
    print('error.txt new:', s.strip()[:600] or '(none)')
