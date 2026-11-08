"""Мини-драйвер окна игры (Windows, ctypes): запуск копии игры через планировщик, поиск окна по ТОЧНОМУ пути exe,
синтетический ввод (SendInput: мышь/клавиши по скан-кодам), снимок кадра хоткеем cnc-ddraw (PrintScreen -> <игра>\\Screenshots),
закрытие игры ТОЛЬКО по точному PID. Не знает про Divine Divinity: путь к игре и exe — параметры.
Использование как библиотека: import gr_drive as G; g = G.Game(r'D:\\...\\preview_game'); g.launch(); g.click(960, 540); g.shot('x.png'); g.kill()"""
import os, sys, time, ctypes, ctypes.wintypes as W, subprocess, glob, shutil

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try: user32.SetProcessDPIAware()
    except Exception: pass

VK = dict(esc=0x1B, enter=0x0D, space=0x20, f5=0x74, f8=0x77, i=0x49, c=0x43, printscreen=0x2C, tab=0x09)
EXT = {0x2C}  # PrintScreen — extended


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', W.LONG), ('dy', W.LONG), ('mouseData', W.DWORD), ('dwFlags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', W.WORD), ('wScan', W.WORD), ('dwFlags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', W.DWORD), ('u', _U)]


def _send(inp): user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def exe_of(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not h: return ''
    try:
        buf = ctypes.create_unicode_buffer(1024); n = W.DWORD(1024)
        return buf.value if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ''
    finally: kernel32.CloseHandle(h)


def windows_of(pid):
    res = []
    CB = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

    def cb(h, _):
        p = W.DWORD(); user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(h): res.append(h)
        return True
    user32.EnumWindows(CB(cb), 0); return res


def pids_by_exe(path):
    """PID всех процессов, чей полный путь exe == path (без широких фильтров по имени)"""
    out = subprocess.run(['tasklist', '/fo', 'csv', '/nh', '/fi', 'imagename eq ' + os.path.basename(path)], capture_output=True, text=True).stdout
    pids = []
    for ln in out.splitlines():
        parts = [x.strip('"') for x in ln.split('","')]
        if len(parts) > 1 and parts[1].isdigit() and os.path.normcase(exe_of(int(parts[1]))) == os.path.normcase(path): pids.append(int(parts[1]))
    return pids


class Game:
    def __init__(s, game_dir, exe='div.exe', gw=1920, gh=1080, task='GRPreviewLaunch'):
        s.dir = os.path.abspath(game_dir); s.exe = os.path.join(s.dir, exe); s.gw, s.gh = gw, gh; s.task = task
        s.pid = None; s.hwnd = None; s.shotdir = os.path.join(s.dir, 'Screenshots')

    # ---- запуск/закрытие ----
    def launch(s, timeout=60):
        if pids_by_exe(s.exe): raise RuntimeError('игра из этой папки уже запущена: %s' % pids_by_exe(s.exe))
        # дочерние процессы Bash убиваются по завершении вызова -> стартуем через задачу планировщика (как DDFxLaunch)
        tr = 'cmd /c start "" /D "%s" "%s"' % (s.dir, s.exe)
        subprocess.run(['schtasks', '/create', '/tn', s.task, '/tr', tr, '/sc', 'once', '/st', '00:00', '/f'], check=True, capture_output=True)
        subprocess.run(['schtasks', '/run', '/tn', s.task], check=True, capture_output=True)
        t0 = time.time()
        while time.time() - t0 < timeout:
            for p in pids_by_exe(s.exe):
                ws = windows_of(p)
                if ws: s.pid, s.hwnd = p, ws[0]; return p
            time.sleep(0.5)
        raise RuntimeError('окно игры не появилось')

    def kill(s):
        if s.pid:
            subprocess.run(['taskkill', '/PID', str(s.pid), '/F'], capture_output=True); s.pid = None
        subprocess.run(['schtasks', '/delete', '/tn', s.task, '/f'], capture_output=True)

    def alive(s): return s.pid is not None and s.pid in pids_by_exe(s.exe)

    # ---- окно ----
    def focus(s):
        ws = windows_of(s.pid)
        if ws: s.hwnd = ws[0]
        user32.ShowWindow(s.hwnd, 9); user32.SetForegroundWindow(s.hwnd)

    def client(s):
        pt = W.POINT(0, 0); user32.ClientToScreen(s.hwnd, ctypes.byref(pt)); r = W.RECT(); user32.GetClientRect(s.hwnd, ctypes.byref(r))
        return pt.x, pt.y, r.right, r.bottom

    # ---- ввод ----
    def rect(s):
        r = W.RECT(); user32.GetWindowRect(s.hwnd, ctypes.byref(r)); return r.left, r.top, r.right - r.left, r.bottom - r.top

    def move_px(s, sx, sy):
        vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77); vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
        _send(INPUT(0, _U(mi=MOUSEINPUT(int((sx - vx) * 65535 / (vw - 1)), int((sy - vy) * 65535 / (vh - 1)), 0, 0x8000 | 0x4000 | 1, 0, 0))))

    def click_px(s, sx, sy, right=False):
        s.move_px(sx, sy); time.sleep(0.2)
        dn, up = (0x8, 0x10) if right else (0x2, 0x4)
        _send(INPUT(0, _U(mi=MOUSEINPUT(0, 0, 0, dn, 0, 0)))); time.sleep(0.08)
        _send(INPUT(0, _U(mi=MOUSEINPUT(0, 0, 0, up, 0, 0)))); time.sleep(0.2)

    def move(s, gx, gy):
        """gx,gy в координатах кадра игры (gw x gh)"""
        cx, cy, cw, ch = s.rect()
        sx = cx + gx * cw / s.gw; sy = cy + gy * ch / s.gh
        vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77); vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
        i = INPUT(0, _U(mi=MOUSEINPUT(int((sx - vx) * 65535 / (vw - 1)), int((sy - vy) * 65535 / (vh - 1)), 0, 0x8000 | 0x4000 | 1, 0, 0)))
        _send(i)

    def click(s, gx, gy, right=False, double=False):
        s.move(gx, gy); time.sleep(0.15)
        dn, up = (0x8, 0x10) if right else (0x2, 0x4)
        for _ in range(2 if double else 1):
            _send(INPUT(0, _U(mi=MOUSEINPUT(0, 0, 0, dn, 0, 0)))); time.sleep(0.06)
            _send(INPUT(0, _U(mi=MOUSEINPUT(0, 0, 0, up, 0, 0)))); time.sleep(0.12)

    def key(s, name, hold=0.08, scan=True):
        """scan=True: скан-коды (DirectInput-ввод игры); scan=False: чистый VK (так cnc-ddraw ловит хоткей снимка)"""
        vk = VK[name] if isinstance(name, str) else name
        sc = user32.MapVirtualKeyW(vk, 0) if scan else 0; fl = (8 if scan else 0) | (1 if vk in EXT else 0)
        _send(INPUT(1, _U(ki=KEYBDINPUT(vk, sc, fl, 0, 0)))); time.sleep(hold)
        _send(INPUT(1, _U(ki=KEYBDINPUT(vk, sc, fl | 2, 0, 0)))); time.sleep(0.1)

    # ---- снимок ----
    def shot(s, out_png, wait=8):
        """PrintScreen -> cnc-ddraw пишет PNG в Screenshots; берём новый файл и переименовываем"""
        os.makedirs(s.shotdir, exist_ok=True)
        before = set(glob.glob(os.path.join(s.shotdir, '*.png')))
        s.focus(); time.sleep(0.2); s.key('printscreen', scan=False); t0 = time.time()
        while time.time() - t0 < wait:
            new = set(glob.glob(os.path.join(s.shotdir, '*.png'))) - before
            if new:
                f = sorted(new)[-1]; time.sleep(0.4); shutil.move(f, out_png); return out_png
            time.sleep(0.2)
        raise RuntimeError('снимок не появился (хоткей cnc-ddraw?)')
