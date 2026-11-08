#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Эмуляция Unicorn для glow_patch.py: РЕАЛЬНЫЕ байты exe (FUN_005226e0 участок 0x522907..0x522953 с хуком, FUN_0057a970, FUN_005918b0,
FUN_00556a80 + memcpy-обёртки). Сравнение с независимой реализацией на Python (поэлементное расширение маски, одно смешивание на пиксель).
usage: python glow_test.py <patched.exe> <original_or_unpatched.exe>"""
import sys, struct, random
import pefile
from unicorn import *
from unicorn.x86_const import *

IMG = 0x400000
def load(path):
    pe = pefile.PE(path, fast_load=True); d = open(path, 'rb').read()
    secs = []
    for s in pe.sections:
        va = IMG + s.VirtualAddress; vs = (max(s.Misc_VirtualSize, s.SizeOfRawData) + 0xfff) & ~0xfff
        secs.append((va, vs, d[s.PointerToRawData:s.PointerToRawData + s.SizeOfRawData]))
    return secs

def mk(secs):
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    for va, vs, raw in secs:
        mu.mem_map(va, vs); mu.mem_write(va, raw)
    mu.mem_map(0x10000000, 0x100000)       # стек
    mu.mem_map(0x20000000, 0x400000)       # куча
    mu.mem_write(0x20000000, b'\0' * 0x400000)
    return mu

# ---------------- построение сцены ----------------
TBL = 0x655a98
def rd(mu, a, n): return bytes(mu.mem_read(a, n))
def u32(mu, a): return struct.unpack('<I', rd(mu, a, 4))[0]

class Scene:
    def __init__(s, mu, rnd, rank, idx_ok=True, mode565=True, spr=None, cw=200, ch=150, x=30, y=40, i=1, flags=0x180000):
        s.mu = mu; s.rnd = rnd
        H = 0x20000000
        # поверхность 400x300 RGB565/555, случайные пиксели
        s.SURF = H; s.SW_, s.SH_ = 400, 300
        px = bytes(rnd.getrandbits(8) for _ in range(s.SW_ * s.SH_ * 2))
        mu.mem_write(H, px)
        # clip struct
        s.CLIP = H + 0x50000
        s.cx0, s.cy0 = 10, 20
        mu.mem_write(s.CLIP, struct.pack('<6I', s.SURF, s.cx0, s.cy0, s.cx0 + cw, s.cy0 + ch, s.SW_ * 2))
        s.cw, s.ch = cw, ch
        # спрайт
        s.sprite = H + 0x100000
        s.spr = spr
        s.build_sprite(spr)
        # viewer / model / inv / vector / entries
        s.VIEWER = H + 0x60000; s.MODEL = H + 0x60100; s.INV = H + 0x60200; s.VEC = H + 0x60300; s.ENT = H + 0x61000
        mu.mem_write(s.VIEWER + 0x58, struct.pack('<I', s.MODEL))
        mu.mem_write(s.MODEL + 0x14, struct.pack('<I', s.INV))
        mu.mem_write(s.INV + 4, struct.pack('<I', s.VEC)); mu.mem_write(s.INV + 0xc, struct.pack('<I', 4))
        mu.mem_write(s.VEC, struct.pack('<III', s.ENT, 4, 0x28))
        # запись i: arch=77, flags
        e = s.ENT + i * 0x28
        mu.mem_write(e + 8, struct.pack('<I', 77)); mu.mem_write(e + 0x14, struct.pack('<I', flags))
        # битовое поле [e+0x18..]: для flags=0x180000 индекс ссылки лежит по смещению sum(tbl[k], k<0x14 установлены)
        tb = [u32(mu, TBL + 4 * k) for k in range(32)]
        offb = sum(tb[k] for k in range(0x14) if flags & (1 << k))
        lidx = 3
        if tb[0x14] == 2: mu.mem_write(e + 0x18 + offb, bytes([lidx >> 8, lidx & 0xff]))
        else: mu.mem_write(e + 0x18 + offb, bytes([lidx]))
        s.tb = (tb[0x13], tb[0x14], offb)
        # менеджер ссылок 0x750cfc: [+0x24]=массив, [+0x28]=число
        ARR = H + 0x62000; LINK = H + 0x62100; RK = H + 0x62200
        mu.mem_write(0x750cfc + 0x24, struct.pack('<II', ARR, 8))
        mu.mem_write(ARR + lidx * 4, struct.pack('<I', LINK))
        mu.mem_write(LINK + 0x84, struct.pack('<I', RK)); mu.mem_write(RK + 0x90, struct.pack('<I', rank))
        G = H + 0x63000                       # цепочка [0x658d50]->+0xc->[0]->+0x2c->+0x1c (аргумент генерации, значение не важно)
        mu.mem_write(0x658d50, struct.pack('<I', G)); mu.mem_write(G + 0xc, struct.pack('<I', G + 0x100))
        mu.mem_write(G + 0x100, struct.pack('<I', G + 0x200)); mu.mem_write(G + 0x200 + 0x2c, struct.pack('<I', G + 0x300))
        mu.mem_write(0x64d4c8, struct.pack('<I', 1 if mode565 else 0))
        s.flags = flags; s.rank = rank; s.mode565 = mode565; s.i = i; s.x, s.y = x, y

    def build_sprite(s, spr):
        mu = s.mu; H = s.sprite
        w, h, rows = spr   # rows: list of list of (x,len)
        mu.mem_write(H + 8, struct.pack('<hh', w, h))
        p = H + 0xc; pix = H + 0x8000
        s.pixmap = {}
        for r, spans in enumerate(rows):
            n = len(spans)
            mu.mem_write(p, struct.pack('<hI', n, pix))
            q = p + 6
            for (sx, ln) in spans:
                mu.mem_write(q, struct.pack('<hh', sx, ln)); q += 4
                for k in range(ln):
                    v = (s.rnd.getrandbits(16) | 1)
                    mu.mem_write(pix, struct.pack('<H', v)); s.pixmap[(sx + k, r)] = v; pix += 2
            mu.mem_write(q, b'\0\0'); p = q + 2

# ---------------- запуск участка 0x522907..0x522953 ----------------
def run_site(mu, sc, capture):
    S0 = 0x10080000
    mu.mem_write(S0, bytes(0x100))
    mu.mem_write(S0 + 0x10, struct.pack('<I', 1))          # qty
    mu.mem_write(S0 + 0x14, struct.pack('<i', sc.y))
    mu.mem_write(S0 + 0x18, struct.pack('<i', sc.x))
    mu.mem_write(S0 + 0x1c, struct.pack('<I', sc.i))
    mu.mem_write(S0 + 0x50, struct.pack('<I', sc.sprite))
    mu.mem_write(S0 + 0x54, struct.pack('<i', 3)); mu.mem_write(S0 + 0x58, struct.pack('<i', 5)); mu.mem_write(S0 + 0x5c, struct.pack('<i', 2))
    mu.reg_write(UC_X86_REG_ESP, S0)
    mu.reg_write(UC_X86_REG_ESI, sc.CLIP); mu.reg_write(UC_X86_REG_EDI, sc.VIEWER)
    for r in (UC_X86_REG_EBX, UC_X86_REG_EBP, UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX): mu.reg_write(r, 0x1234)
    mu.reg_write(UC_X86_REG_EBX, sc.i)
    regs_before = {r: mu.reg_read(r) for r in (UC_X86_REG_ESI, UC_X86_REG_EDI)}
    def hk(uc, addr, size, ud):
        if addr == 0x556a80:
            esp = uc.reg_read(UC_X86_REG_ESP)
            capture['args'] = struct.unpack('<7i', rd(uc, esp + 4, 28))
            capture['blit_calls'] = capture.get('blit_calls', 0) + 1
    h1 = mu.hook_add(UC_HOOK_CODE, hk, begin=0x556a80, end=0x556a80)
    # CRT memcpy 0x5e5eaa: реализуем сами (cdecl dst,src,n)
    def mc(uc, addr, size, ud):
        if addr == 0x5e5eaa:
            esp = uc.reg_read(UC_X86_REG_ESP)
            d, s_, n = struct.unpack('<3I', rd(uc, esp + 4, 12))
            uc.mem_write(d, rd(uc, s_, n))
            uc.reg_write(UC_X86_REG_EAX, d)
            uc.reg_write(UC_X86_REG_EIP, u32(uc, esp)); uc.reg_write(UC_X86_REG_ESP, esp + 4)
    h2 = mu.hook_add(UC_HOOK_CODE, mc, begin=0x5e5eaa, end=0x5e5eaa)
    # заглушка генерации ссылки 0x57a5e0 (create=1): ставит бит 0x100000 (как настоящая через 0x5919e0), индекс уже записан сценой
    def gen(uc, addr, size, ud):
        if addr == 0x57a5e0:
            esp = uc.reg_read(UC_X86_REG_ESP)
            fp = u32(uc, esp + 4)
            uc.mem_write(fp, struct.pack('<I', u32(uc, fp) | 0x100000))
            capture['gen'] = capture.get('gen', 0) + 1
            uc.reg_write(UC_X86_REG_EAX, 0x20000000 + 0x62100)
            uc.reg_write(UC_X86_REG_EIP, u32(uc, esp)); uc.reg_write(UC_X86_REG_ESP, esp + 0x24)
    h5 = mu.hook_add(UC_HOOK_CODE, gen, begin=0x57a5e0, end=0x57a5e0)
    # стоп на 0x522953
    mu.mem_write(0x522953 - 0x401000 + 0x400 + IMG - IMG, b'') if False else None
    last = [0]
    h3 = mu.hook_add(UC_HOOK_CODE, lambda uc, a, sz, ud: last.__setitem__(0, a))
    def bad(uc, t, a, sz, v, ud): print('UNMAPPED', t, hex(a), 'pc', hex(last[0])); return False
    h4 = mu.hook_add(UC_HOOK_MEM_READ_UNMAPPED | UC_HOOK_MEM_WRITE_UNMAPPED, bad)
    try:
        mu.emu_start(0x522907, 0x522953, count=2000000)
    finally:
        mu.hook_del(h1); mu.hook_del(h2)
    esp = mu.reg_read(UC_X86_REG_ESP)
    assert esp == S0, 'stack unbalanced %x vs %x' % (esp, S0)
    for r, v in regs_before.items(): assert mu.reg_read(r) == v, 'esi/edi changed'
    return rd(mu, sc.SURF, sc.SW_ * sc.SH_ * 2)

# ---------------- эталон ----------------
COLORS = [0x9CF3, 0x337F, 0x3EE7, 0xFF25, 0xFD40]
def blit_ref(surf, args, spr, pixmap):
    dst, sprp, W, H, x, y, extra = args
    return surf   # (настоящий блит делает сам exe; эталон ниже сравнивает ТОЛЬКО ореол + реальный блит из unpatched)

def halo_ref(surf, sc, args):
    """surf: bytearray поверхности; применяет ореол по определению (дилатация по элементу, 1 смешивание на пиксель)."""
    dst, sprp, W, H, x, y, extra = args
    w, h, rows = sc.spr
    if sc.i >= 4 or not (sc.flags & 0x80000) or ((sc.flags & 0x20000) and not (sc.flags & 0x100000)): return
    if sc.rank not in (3, 4, 5) or w < 1 or h < 1 or w > 160 or h > 160: return
    c = COLORS[sc.rank - 1]
    if sc.mode565: m = 0xF7DE
    else: m = 0x7BDE; c = ((c & 0xFFC0) >> 1) | (c & 0x1F)
    ch = (c & m) >> 1
    mask = set()
    for r, spans in enumerate(rows):
        for (sx, ln) in spans:
            if ln <= 0: continue
            for k in range(ln):
                for dy in range(-2, 3):
                    ext = 2 if abs(dy) <= 1 else 1
                    for dx in range(-ext, ext + 1): mask.add((sx + k + dx, r + dy))
    stride = (W + extra) * 2
    base = dst - sc.SURF
    for (mx, my) in mask:
        px, py = x + mx, y + my
        if 0 <= px < W and 0 <= py < H:
            o = base + py * stride + px * 2
            d = struct.unpack_from('<H', surf, o)[0]
            struct.pack_into('<H', surf, o, (((d & m) >> 1) + ch) & 0xFFFF)

def rand_sprite(rnd, w, h, density=0.7):
    rows = []
    for r in range(h):
        spans = []; x = rnd.randint(0, 3)
        while x < w and rnd.random() < density:
            ln = rnd.randint(1, max(1, min(12, w - x)))
            spans.append((x, ln)); x += ln + rnd.randint(1, 5)
        rows.append(spans)
    return (w, h, rows)

def one(secs_p, secs_o, seed, rank, spr, mode565=True, x=30, y=40, i=1, flags=0x180000, cw=200, ch=150):
    rnd = random.Random(seed)
    res = []
    for secs in (secs_o, secs_p):
        mu = mk(secs); sc = Scene(mu, random.Random(seed), rank, mode565=mode565, spr=spr, x=x, y=y, i=i, flags=flags, cw=cw, ch=ch)
        cap = {}
        surf = run_site(mu, sc, cap)
        res.append((surf, cap, sc))
    (s0, c0, sc0), (s1, c1, sc1) = res
    assert c0.get('blit_calls', 0) <= 1 and c1.get('blit_calls', 0) == c0.get('blit_calls', 0), (c0, c1)
    if 'args' not in c0: return 'noblit', True
    assert c0['args'] == c1['args'], (c0['args'], c1['args'])
    exp = bytearray(random.Random(seed) and b'')
    # ожидаемый = ореол по эталону на ИСХОДНОЙ поверхности + затем блит; блит даёт unpatched => воспроизведём через второй прогон: поверхность до блита
    mu = mk(secs_o); sc = Scene(mu, random.Random(seed), rank, mode565=mode565, spr=spr, x=x, y=y, i=i, flags=flags, cw=cw, ch=ch)
    pre = bytearray(rd(mu, sc.SURF, sc.SW_ * sc.SH_ * 2))
    # применить эталонный ореол к pre, записать pre в память, запустить unpatched (только блит)
    halo_ref(pre, sc, c0['args'])
    mu.mem_write(sc.SURF, bytes(pre))
    exp = run_site(mu, sc, {})
    return ('rank%d' % rank), exp == s1, s0 != s1

if __name__ == '__main__':
    P, O = load(sys.argv[1]), load(sys.argv[2])
    rnd = random.Random(1)
    fails = 0; n = 0
    cases = []
    for rank in (0, 1, 2, 3, 4, 5, 9):
        cases.append(dict(rank=rank, spr=rand_sprite(rnd, 32, 32), x=30, y=40))
    for k in range(25):                      # случайные размеры/позиции/клипы (включая частично за границей и отрицательные)
        w = rnd.randint(1, 60); h = rnd.randint(1, 60)
        cases.append(dict(rank=rnd.choice([1, 2, 3, 3, 4, 4, 5]), spr=rand_sprite(rnd, w, h, rnd.choice([0.3, 0.7, 0.95])), x=rnd.randint(-40, 220), y=rnd.randint(-40, 170), mode565=rnd.random() < 0.7))
    cases.append(dict(rank=3, spr=rand_sprite(rnd, 160, 160), x=5, y=5))       # предел GMAX
    cases.append(dict(rank=3, spr=rand_sprite(rnd, 161, 20), x=5, y=5))        # больше GMAX -> без ореола
    cases.append(dict(rank=2, spr=rand_sprite(rnd, 40, 40), x=0, y=0, cw=40, ch=40))
    cases.append(dict(rank=2, spr=rand_sprite(rnd, 40, 40), x=-2, y=-2, cw=1, ch=1))
    cases.append(dict(rank=4, spr=rand_sprite(rnd, 20, 20), x=30, y=40, i=7))               # индекс вне границ -> оригинал
    cases.append(dict(rank=4, spr=rand_sprite(rnd, 20, 20), x=30, y=40, flags=0x80000))     # ссылка не создана -> создаётся как при hover -> ореол
    cases.append(dict(rank=4, spr=rand_sprite(rnd, 20, 20), x=30, y=40, flags=0xA0000))     # особый случай 0x20000 -> без создания, оригинал
    cases.append(dict(rank=3, spr=rand_sprite(rnd, 24, 24), x=30, y=40, flags=0x80000))
    cases.append(dict(rank=4, spr=rand_sprite(rnd, 20, 20), x=30, y=40, flags=0))
    for k, c in enumerate(cases):
        r = one(P, O, 100 + k, **c); n += 1
        ok = r[1]
        tag = 'OK ' if ok else 'FAIL'
        info = ''
        if len(r) > 2: info = 'changed=%s' % r[2]
        if not ok: fails += 1
        exp_noeff = c.get('flags', 0x180000) == 0xA0000 or c.get('rank', 0) in (0, 1, 2, 9) or c.get('i', 1) == 7 or c.get('flags', 0x180000) not in (0x180000, 0x80000) or c['spr'][0] > 160
        if len(r) > 2 and exp_noeff and r[2]: tag = 'FAIL(effect expected none)'; fails += 1
        print(tag, k, r[0], 'rank', c['rank'], 'spr %dx%d' % (c['spr'][0], c['spr'][1]), 'pos', c.get('x'), c.get('y'), info)
    print('cases', n, 'fails', fails)
    sys.exit(1 if fails else 0)
