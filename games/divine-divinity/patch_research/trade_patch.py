#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Патч окна торговли (CTradePlate, div.exe v1.0.0.62): ширина колонок + сетка плиток вместо вертикального списка. Накладывается на любой exe (идемпотентно, размер не меняется).
  ширина  : конструктор 0x533330: x колонок 0x79,0xe5,0x151 (121,229,337) -> +1*dp,+2*dp,+3*dp; x правой плашки трейдера 0x177 -> +4*dp (imm по 0x5334bc/c6/d0, 0x533453).
  сетка   : CBMCFlatInventoryViewer::Draw 0x531580 (vtable 0x619ebc[17]): ряд i -> плитка (i%C, i/C): x=BASEX+(i%C)*CW, y=(i/C)*CH; иконка по центру плитки, подпись («N x цена») под иконкой по центру плитки,
            хит-тест — прямоугольник плитки, высота содержимого = (ряд+1)*CH. Пещеры в мёртвом хвосте 004af320 (0x4af4e0..0x4af5af); глобалы (BSS) 0x751ff4 (счётчик), 0x751ff8 (x плитки), 0x751ffc (2*центр).
usage: python trade_patch.py <src> <dst> [--dp 128] [--cw 64] [--ch 100] [--icon 84] [--no-grid]"""
import sys, struct, hashlib
from keystone import Ks, KS_ARCH_X86, KS_MODE_32
SIZE = 2461696; TEXT_VA = 0x401000; TEXT_RAW = 0x400
def off(va): return va - TEXT_VA + TEXT_RAW
CAVE = 0x4af4e0; CAVE_END = 0x4af5b0
GK, GX, GC2 = 0x751ff4, 0x751ff8, 0x751ffc

def asm(src, addr):
    return bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(src, addr)[0])

def build(dp, cw, ch, icon):
    lw = 70 + dp; cols = max(1, lw // cw); basex = (lw - cols * cw) // 2
    parts = {}   # name -> (cave source builder)
    cave = CAVE; patches = []
    def put(name, src):
        nonlocal cave
        b = asm(src, cave); parts[name] = cave; cave += len(b) + 0; patches.append((cave - len(b), b)); cave = (cave + 3) & ~3
        return parts[name]
    # заранее известные адреса возврата
    R = put('R', f"""
 mov [esp+0x1c], ebp
 mov [esp+0x38], ebp
 mov dword ptr [{GK}], 0
 jmp 0x531600""")
    A = put('A', f"""
 mov eax, [{GK}]
 inc dword ptr [{GK}]
 xor edx, edx
 mov ebx, {cols}
 div ebx
 imul eax, eax, {ch}
 mov [esp+0x1c], eax
 imul edx, edx, {cw}
 add edx, {basex}
 mov [{GX}], edx
 lea ebx, [edx+edx+{cw}]
 mov [{GC2}], ebx
 mov ecx, [esp+0x10]
 movsx ebx, word ptr [ecx+8]
 neg ebx
 add ebx, {cw}
 sar ebx, 1
 jns L1
 xor ebx, ebx
L1:
 add ebx, edx
 mov [esp+0x28], ebx
 movsx ebx, word ptr [ecx+0xa]
 neg ebx
 add ebx, {icon}
 sar ebx, 1
 jns L2
 xor ebx, ebx
L2:
 add ebx, [esp+0x1c]
 mov [esp+0x2c], ebx
 jmp 0x531700""")
    B = put('B', f"""
 mov ecx, [esp+0x1c]
 lea edx, [ecx+{ch+1}]
 mov [edi+0x3c], edx
 mov eax, [edi+0x74]
 cmp eax, ecx
 jl S
 add ecx, {ch}
 cmp eax, ecx
 jge S
 mov eax, [edi+0x70]
 mov edx, [{GX}]
 cmp eax, edx
 jl S
 add edx, {cw}
 cmp eax, edx
 jge S
 jmp 0x531737
S:
 jmp 0x53187b""")
    C = put('C', f"""
 mov eax, [{GC2}]
 sub eax, [esp+0x1c]
 jmp 0x531a19""")
    assert cave <= CAVE_END, hex(cave)
    jmp = lambda frm, to, n: asm('jmp %d' % to, frm) + b'\x90' * (n - 5)
    hooks = [  # (va, orig, new)
        (0x5315f8, '896c241c896c2438', jmp(0x5315f8, R, 8)),
        (0x5316dd, None, jmp(0x5316dd, A, 35)),
        (0x531710, None, jmp(0x531710, B, 39)),
        (0x531a13, '8bc12b44241c', jmp(0x531a13, C, 6)),
        (0x531a66, '8d4c1014', bytes.fromhex('8b4c243c')),
    ]
    return patches, hooks, cols

ORIG_A = None
def main(a):
    opt = {'--dp': 128, '--cw': 64, '--ch': 100, '--icon': 84}; pos = []; grid = True; i = 0
    while i < len(a):
        if a[i] in opt: opt[a[i]] = int(a[i + 1], 0); i += 2
        elif a[i] == '--no-grid': grid = False; i += 1
        else: pos.append(a[i]); i += 1
    if len(pos) != 2: print(__doc__); return 2
    d = bytearray(open(pos[0], 'rb').read())
    if len(d) != SIZE: print('wrong file size'); return 3
    dp = opt['--dp']
    imm = [(0x5334bc, 0x79, 121 + dp), (0x5334c6, 0xe5, 229 + 2 * dp), (0x5334d0, 0x151, 337 + 3 * dp), (0x533453, 0x177, 0x177 + 4 * dp)]
    for va, o, n in imm:
        cur = struct.unpack('<I', d[off(va):off(va) + 4])[0]
        if cur not in (o, n): print('unexpected imm at %x: %x' % (va, cur)); return 4
        d[off(va):off(va) + 4] = struct.pack('<I', n)
    if grid:
        patches, hooks, cols = build(dp, opt['--cw'], opt['--ch'], opt['--icon'])
        for va, b in patches:
            cur = bytes(d[off(va):off(va) + len(b)])
            if cur != b and cur.strip(b'\x00\xcc\x90') and not _dead(d, va, len(b)): print('cave area busy %x' % va); return 5
            d[off(va):off(va) + len(b)] = b
        for va, o, n in hooks:
            cur = bytes(d[off(va):off(va) + len(n)])
            if cur == n: continue
            if o and cur[:len(o) // 2] != bytes.fromhex(o)[:len(o) // 2]: print('unexpected bytes at %x: %s' % (va, cur.hex())); return 4
            d[off(va):off(va) + len(n)] = n
        print('grid: %d columns, tile %dx%d' % (cols, opt['--cw'], opt['--ch']))
    open(pos[1], 'wb').write(d); print('ok', pos[1], hashlib.sha256(d).hexdigest()); return 0

def _dead(d, va, n):   # область 0x4af4e0.. - мёртвый хвост старого 004af320 (после заглушки); разрешаем перезапись
    return CAVE <= va < CAVE_END

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
