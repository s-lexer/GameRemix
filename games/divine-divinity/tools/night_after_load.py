"""Divine Divinity (div.exe 1.0.0.62 and our patched builds): makes it night N seconds after a save is loaded. Test aid for the shaders.
Time manager (docs/re: init.cpp "Loading time manager"): pointer at 0x658C1C -> 24 bytes: +0 world ticks, +4 ticks left in the hour,
+8 day, +0xC hour 0..23, +0x10 ticks per hour, +0x14 frozen. Shown hour = (+0xC + [0x650F88]) % 24; night = hour < 6 or > 21 (twilight call before FUN_00597740 in the frame code).
"Loaded" = the world tick counter starts moving (it stands still in the main menu).
usage: night_after_load.py <exe name> [delay_s=20] [hour=22]"""
import sys, time, ctypes, subprocess
k32 = ctypes.windll.kernel32
TIME_PTR, HOUR_OFS = 0x658C1C, 0x650F88

def pid_of(name):
    out = subprocess.run(['tasklist', '/fo', 'csv', '/nh', '/fi', 'imagename eq ' + name], capture_output=True, text=True).stdout
    for line in out.splitlines():
        f = line.strip('"').split('","')
        if len(f) > 1 and f[0].lower() == name.lower(): return int(f[1])
    return 0

def rd(h, a):
    v = ctypes.c_int32(); n = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), ctypes.byref(v), 4, ctypes.byref(n)): raise OSError('read %x' % a)
    return v.value

def wr(h, a, val):
    v = ctypes.c_int32(val); n = ctypes.c_size_t()
    if not k32.WriteProcessMemory(h, ctypes.c_void_p(a), ctypes.byref(v), 4, ctypes.byref(n)): raise OSError('write %x' % a)

if __name__ == '__main__':
    exe = sys.argv[1]; delay = float(sys.argv[2]) if len(sys.argv) > 2 else 20; hour = int(sys.argv[3]) if len(sys.argv) > 3 else 22
    pid = 0
    for _ in range(120):
        pid = pid_of(exe)
        if pid: break
        time.sleep(1)
    if not pid: sys.exit('game not found: ' + exe)
    h = k32.OpenProcess(0x0010 | 0x0020 | 0x0008 | 0x0400, False, pid)   # VM_READ | VM_WRITE | VM_OPERATION | QUERY_INFORMATION
    if not h: sys.exit('cannot open pid %d' % pid)
    print('pid', pid, flush=True)
    last, moving = None, 0
    while True:   # wait for the save to load: the tick counter moves for 3 s in a row
        if not pid_of(exe): sys.exit('game closed')
        try:
            t = rd(h, TIME_PTR); ticks = rd(h, t) if t else None
        except OSError: ticks = None
        moving = moving + 1 if (ticks is not None and last is not None and ticks > last) else 0
        last = ticks
        if moving >= 3: break
        time.sleep(1)
    print('loaded, ticks', last, '- night in', delay, 's', flush=True)
    time.sleep(delay)
    t = rd(h, TIME_PTR); off = rd(h, HOUR_OFS)
    print('hour was', (rd(h, t + 0xC) + off) % 24, flush=True)
    wr(h, t + 0xC, (hour - off) % 24); wr(h, t + 4, rd(h, t + 0x10))
    print('hour now', (rd(h, t + 0xC) + off) % 24, flush=True)
