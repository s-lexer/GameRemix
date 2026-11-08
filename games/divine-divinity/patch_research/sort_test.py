#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка SORT (trade_patch5.py) эмуляцией Unicorn на РЕАЛЬНЫХ байтах пропатченного exe против эталона на Python (sort_ranks.ref_layout).
Синтетический инвентарь: записи 0x28 байт (x,y,+8 архетип,+0xc слот), размеры спрайтов подменены хуком на 0x4e8f20 (w,h по архетипу), надетые записи не трогаются.
usage: python sort_test.py <patched.exe> [--n 150] [--seed 1] [--bag-w 366]"""
import sys, struct, random, os
import pefile
from unicorn import *
from unicorn.x86_const import *
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sort_ranks, trade_patch5

IMG = 0x400000
def load(path):
    pe = pefile.PE(path, fast_load=True); d = open(path, 'rb').read(); secs = []
    for s in pe.sections:
        va = IMG + s.VirtualAddress; vs = (max(s.Misc_VirtualSize, s.SizeOfRawData) + 0xfff) & ~0xfff
        secs.append((va, vs, d[s.PointerToRawData:s.PointerToRawData + s.SizeOfRawData]))
    return secs

def sizes_for(a): r = random.Random(a * 7919 + 13); return (r.choice((30, 30, 60, 90)), r.choice((30, 60, 60, 90, 120)))

def run(exe, n, seed, bagw):
    trade_patch5.build(dict(wb=334, wo=154, tab=40, cw=60, ch=100, icon=84, no_tabs=False, no_group=False, keep_hover=False, lang='ru', sort=True, bagw=bagw, bagh=369, pos=True, margin=16, bag_size=(422, 480)))
    SORT = trade_patch5.LABELS['SORT']
    tab = sort_ranks.unpack(sort_ranks.load()); rnd = random.Random(seed)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    for va, vs, raw in load(exe): mu.mem_map(va, vs); mu.mem_write(va, raw)
    STK, H = 0x10000000, 0x20000000
    mu.mem_map(STK, 0x100000); mu.mem_map(H, 0x100000)
    pool = list(tab) + [a for a in range(7208) if a not in tab][:6] + [7300, 99999]   # + неизвестные и вне диапазона
    items = []
    for i in range(n):
        a = rnd.choice(pool); items.append(a)
    worn = set(rnd.sample(range(n), 5))
    ENT, VEC, INV = H + 0x1000, H + 0x100, H + 0x200
    for i, a in enumerate(items):
        e = ENT + i * 0x28
        mu.mem_write(e, struct.pack('<ii', 1000 + i, 2000 + i)); mu.mem_write(e + 8, struct.pack('<I', a))
        mu.mem_write(e + 0xc, struct.pack('<h', 3 if i in worn else -1))
    mu.mem_write(VEC, struct.pack('<III', ENT, n, 0x28)); mu.mem_write(INV + 4, struct.pack('<I', VEC)); mu.mem_write(INV + 0xc, struct.pack('<I', n))
    def hook(mu, addr, size, ud):
        esp = mu.reg_read(UC_X86_REG_ESP); ret, arch, _z, pw, ph = struct.unpack('<5I', bytes(mu.mem_read(esp, 20)))
        w, h = sizes_for(arch); mu.mem_write(pw, struct.pack('<I', w)); mu.mem_write(ph, struct.pack('<I', h))
        mu.reg_write(UC_X86_REG_ESP, esp + 20); mu.reg_write(UC_X86_REG_EIP, ret)
    mu.hook_add(UC_HOOK_CODE, hook, begin=0x4e8f20, end=0x4e8f20)
    mu.mem_write(0x658bd8, struct.pack('<I', H + 0x500))
    # таблица архетипов [[0x658bdc]+0x1c] + arch*0x94 + 0x34 = категория (реальная objects.000, если есть)
    OBJ = os.path.join(r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity', 'preview_game', 'static', 'objects.000')
    if os.path.exists(OBJ):
        od = open(OBJ, 'rb').read(); cats = {a: struct.unpack_from('<I', od, a * 0x94 + 0x34)[0] for a in range(7208)}
    else: cats = {a: random.Random(a).choice((0, 0, 1, 2, 3, 4)) for a in range(7208)}
    MG, TB = H + 0x300, 0x40000000
    mu.mem_map(TB, 0x120000)
    for a in range(7208): mu.mem_write(TB + a * 0x94 + 0x34, struct.pack('<I', cats[a]))
    mu.mem_write(MG + 0x1c, struct.pack('<I', TB)); mu.mem_write(0x658bdc, struct.pack('<I', MG))
    sp = STK + 0x80000; mu.mem_write(sp, struct.pack('<I', 0x30000000)); mu.mem_map(0x30000000, 0x1000); mu.mem_write(0x30000000, b'\xf4')
    mu.reg_write(UC_X86_REG_ESP, sp); mu.reg_write(UC_X86_REG_ECX, INV)
    mu.emu_start(SORT, 0x30000000, count=5_000_000)
    got = {}
    for i in range(n):
        e = ENT + i * 0x28; got[i] = struct.unpack('<ii', bytes(mu.mem_read(e, 8)))
    ref = sort_ranks.ref_layout([(i, a) for i, a in enumerate(items) if i not in worn], {a: sizes_for(a) for a in items}, tab, bagw, cats)
    bad = 0
    for i in range(n):
        exp = (1000 + i, 2000 + i) if i in worn else ref[i]
        if got[i] != exp: bad += 1; print('MISMATCH', i, items[i], got[i], exp) if bad < 10 else None
    # независимые проверки: наложения - только внутри одной вкладки; первая группа каждой вкладки начинается с y=2
    tb = lambda i: sort_ranks.tab_of(cats[items[i]]) if items[i] < 7208 else 4
    live = [i for i in range(n) if i not in worn]
    for t in set(tb(i) for i in live):
        if min(got[i][1] for i in live if tb(i) == t) != 2: bad += 1; print('вкладка', t, 'не начинается с y=2')
    rects = [(got[i][0], got[i][1], *sizes_for(items[i]), tb(i)) for i in live]
    ov = sum(1 for p in range(len(rects)) for q in range(p) if rects[p][4] == rects[q][4] and rects[p][0] < rects[q][0] + rects[q][2] and rects[q][0] < rects[p][0] + rects[p][2] and rects[p][1] < rects[q][1] + rects[q][3] and rects[q][1] < rects[p][1] + rects[p][3])
    print('n=%d worn=%d  расхождений с эталоном: %d  наложений: %d' % (n, len(worn), bad, ov))
    return bad + ov

if __name__ == '__main__':
    av = sys.argv[1:]
    if not av: print(__doc__); sys.exit(2)
    n = int(av[av.index('--n') + 1]) if '--n' in av else 150; seed = int(av[av.index('--seed') + 1]) if '--seed' in av else 1
    bw = int(av[av.index('--bag-w') + 1], 0) if '--bag-w' in av else 0x16e
    sys.exit(1 if run(av[0], n, seed, bw) else 0)
