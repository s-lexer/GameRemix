#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Патч рюкзака и списков Divine Divinity (div.exe v1.0.0.62, 2461696 байт). Идемпотентный, на месте (размер файла не меняется).
Исследование и адреса: docs/RESEARCH_LOG.md (раздел 2026-11-06 «Рюкзак»).
Режимы (по умолчанию включены оба):
  search  - поиск места предмета в рюкзаке/сундуке/торговле: FUN_004aebf0 + заглушка FUN_004af320 + код в 0x4af340 (ближайшее свободное место во все стороны;
            отступ слева/сверху --min-x/--min-y (2), предел справа/снизу --max-x/--max-y (0x114/0xc5)).
  wheel   - колесо мыши для списков класса CBMVerticalScrollControl (рюкзак, сундук, торговля...): перехват WM_MOUSEWHEEL в обоих циклах сообщений
            (0x40d3d3, 0x40df6a), запоминание «списка под мышью» в 0x751ff0 (BSS), шаг --wheel-step (40 px); код в 0x4af400..0x4af4d7.
usage: python inv_patch.py <src div.exe> <dst div.exe> [--big DX DY] [--no-search] [--no-wheel] [--min-x N] [--min-y N] [--max-x N] [--max-y N] [--wheel-step N]
       python inv_patch.py --check <exe>   (original / patched / partial / unknown)
  --big DX DY - БОЛЬШОЕ окно рюкзака игрока: размер окна 332x310 -> (332+DX)x(310+DY) (+ пределы области предметов); нужен набор set_bigbag (tools/ui_skins/make_big_bag.py).
Высокий рюкзак: --max-y 0x2c5 (прокрутка колесом и ползунком)."""
import sys, struct, hashlib
SIZE = 2461696; TEXT_VA = 0x401000; TEXT_RAW = 0x400
SEARCH = [(4910077, '10', '02'), (4910086, '10000000', '02000000'), (4910097, '10', '02'), (4910103, '10000000', '02000000'), (4910139, '11010000', '14010000'), (4910148, 'be000000', 'c5000000'), (4910400, '8b54243c8b', 'e9fb050000'), (4911904, '83ec28538b5c2430558b690c568b742440578b7c2440894c24108d44', '8b442404c700020000008b442408c70002000000b801000000c20c00'), (4911936, '4c242051c703100000006a00c707100000008b0dd88b650056896c2444e8be9b0300b8110100002b44241cb9be0000002b4c2418390389442420894c24247e028903390f7e02890f33ff3bef0f84dc01000033c98bc5ba10000000f7e20f90c1683b0800006804306100f7d90bc851e8fcb0040069f6940000008b0ddc8b65008b511c8b4c323483c40c89442414897c2444894c242885ed0f8e800000008bd88b5424108b420485ff7c0f3b78047d0a8b70080faff70330eb0233f68b4608', '8b5424388b0289442428894424308b54243c8b028944242c8944244483e00183c00289c7834c2424ff8b74243083e60183c60289f02b4424300fafc089fa2b5424440fafd201d03b442424733b8b5c24208b6c24404d78243b73087f1a89f1034c24143b0b7c103b7b0c7f0b89f9034c24103b4b047d1183c310ebd98944242489742428897c242c83c6023b7424187ea283c7023b7c241c7e8f8b5424388b44242889028b54243c8b44242c8902ff742420e849b1040083c404e9d1f9ffff')]
WHEEL = [(4912128, '15dc8b65008b521c8b6c24288bc869c994000000396c113475398d4c2430518b0dd88b65008d542430526a0050e8ee9a03008b0eff4424448bc389088b5604034c242c83c3108950040354243089480889500c473b7c24347c868b5c243c837c244400c7442410000000007e628b4424408b388b4c24188b7424148b1b8d2c0f83c6088b56048b068b4c241c528b56fc50558d040b508b46f852505753e8ee21fcff83c42085c0751c8b4424104083c6103b442444894424107cc88b54241452e9a10000008b4c24103b4c24447c0a8b54241452e98d00', '8b4424048178040a0200000f85810000000fbf500a85d27479a1f01f750085c07470565789c689d78b86f40000003b868c0000007c5a3b86940000007d528b86f80000003b86900000007c443b86980000007d3c8b4e648b01ff50380386900000002b8698000000790231c08b8ea400000085ff7f0583c128eb0383e92839c17e0289c185c9790231c9898ea40000005f5eff25386460008935f01f75008b4e648bb6a4000000c33935f01f7500750ac705f01f7500000000008b4e648b11c33935f01f7500750ac705f01f750000000000e9294afbff'), (4248531, 'ff1538646000', 'e828200a0090'), (4251498, 'ff1538646000', 'e891140a0090'), (4606168, '8b4e648bb6a4000000', 'e8bbab040090909090'), (4606201, '8b4e648b11', 'e8aaab0400'), (4616819, 'e888ccffff', 'e848820400')]
# смещения imm8 внутри нового кода поиска (запись по 0x4af340): miny, minx
CAVE_MINY_OFF, CAVE_MINX_OFF = 33, 50
# вспомогательное: шаг колеса - imm32 в коде колеса; ищем две вхождения add/sub ecx,imm (83 c1 28 / 83 e9 28)
# --- исходный текст кода (keystone, x86-32) для справки ---
CAVE_ASM = '\n mov edx,[esp+0x38]\n mov eax,[edx]\n mov [esp+0x28],eax\n mov [esp+0x30],eax\n mov edx,[esp+0x3c]\n mov eax,[edx]\n mov [esp+0x2c],eax\n mov [esp+0x44],eax\n and eax,1\n add eax,2\n mov edi,eax\n or dword ptr [esp+0x24],-1\nLy:\n mov esi,[esp+0x30]\n and esi,1\n add esi,2\nLx:\n mov eax,esi\n sub eax,[esp+0x30]\n imul eax,eax\n mov edx,edi\n sub edx,[esp+0x44]\n imul edx,edx\n add eax,edx\n cmp eax,[esp+0x24]\n jae Nx\n mov ebx,[esp+0x20]\n mov ebp,[esp+0x40]\nLr:\n dec ebp\n js Free\n cmp esi,[ebx+8]\n jg Nr\n mov ecx,esi\n add ecx,[esp+0x14]\n cmp ecx,[ebx]\n jl Nr\n cmp edi,[ebx+0xc]\n jg Nr\n mov ecx,edi\n add ecx,[esp+0x10]\n cmp ecx,[ebx+4]\n jge Nx\nNr:\n add ebx,0x10\n jmp Lr\nFree:\n mov [esp+0x24],eax\n mov [esp+0x28],esi\n mov [esp+0x2c],edi\nNx:\n add esi,2\n cmp esi,[esp+0x18]\n jle Lx\n add edi,2\n cmp edi,[esp+0x1c]\n jle Ly\n mov edx,[esp+0x38]\n mov eax,[esp+0x28]\n mov [edx],eax\n mov edx,[esp+0x3c]\n mov eax,[esp+0x2c]\n mov [edx],eax\n push dword ptr [esp+0x20]\n call 0x4fa540\n add esp,4\n jmp 0x4aedd0\n'
STUB_ASM = '\n mov eax,[esp+4]\n mov dword ptr [eax],2\n mov eax,[esp+8]\n mov dword ptr [eax],2\n mov eax,1\n ret 0xc\n'
WHEEL_ASM = '\nW:\n mov eax,[esp+4]\n cmp dword ptr [eax+4],0x20a\n jne L_G\n movsx edx,word ptr [eax+0xa]\n test edx,edx\n je L_G\n mov eax,[7675888]\n test eax,eax\n je L_G\n push esi\n push edi\n mov esi,eax\n mov edi,edx\n mov eax,[esi+0xf4]\n cmp eax,[esi+0x8c]\n jl L_D\n cmp eax,[esi+0x94]\n jge L_D\n mov eax,[esi+0xf8]\n cmp eax,[esi+0x90]\n jl L_D\n cmp eax,[esi+0x98]\n jge L_D\n mov ecx,[esi+0x64]\n mov eax,[ecx]\n call dword ptr [eax+0x38]\n add eax,[esi+0x90]\n sub eax,[esi+0x98]\n jns L_M\n xor eax,eax\nL_M:\n mov ecx,[esi+0xa4]\n test edi,edi\n jg L_U\n add ecx,40\n jmp L_Cl\nL_U:\n sub ecx,40\nL_Cl:\n cmp ecx,eax\n jle L_A\n mov ecx,eax\nL_A:\n test ecx,ecx\n jns L_B\n xor ecx,ecx\nL_B:\n mov [esi+0xa4],ecx\nL_D:\n pop edi\n pop esi\nL_G:\n jmp dword ptr [0x606438]\nC3:\n mov [7675888],esi\n mov ecx,[esi+0x64]\n mov esi,[esi+0xa4]\n ret\nC4:\n cmp [7675888],esi\n jne L_N4\n mov dword ptr [7675888],0\nL_N4:\n mov ecx,[esi+0x64]\n mov edx,[ecx]\n ret\nC5:\n cmp [7675888],esi\n jne L_N5\n mov dword ptr [7675888],0\nL_N5:\n jmp 0x463f00\n'

def off(va): return va - TEXT_VA + TEXT_RAW

def build_search(minx, miny, maxx, maxy):
    out = []
    for va, o, n in SEARCH:
        n = bytearray.fromhex(n)
        if va == 0x4aebfd: n[0] = minx
        elif va == 0x4aec06: n[0:4] = struct.pack('<I', minx)
        elif va == 0x4aec11: n[0] = miny
        elif va == 0x4aec17: n[0:4] = struct.pack('<I', miny)
        elif va == 0x4aec3b: n[0:4] = struct.pack('<I', maxx)
        elif va == 0x4aec44: n[0:4] = struct.pack('<I', maxy)
        elif va == 0x4af320: n[6] = minx; n[0x10] = miny  # заглушка: два mov [eax],imm32
        elif va == 0x4af340: n[CAVE_MINY_OFF] = miny; n[CAVE_MINX_OFF] = minx
        out.append((va, bytes.fromhex(o), bytes(n)))
    return out

def build_wheel(step):
    out = []
    for va, o, n in WHEEL:
        n = bytearray.fromhex(n)
        if va == 0x4af400:
            for i in range(len(n) - 2):
                if n[i] == 0x83 and n[i + 1] in (0xc1, 0xe9) and n[i + 2] == 40: n[i + 2] = step
        out.append((va, bytes.fromhex(o), bytes(n)))
    return out

def classify(d, groups):
    res = []
    for g in groups:
        s = set()
        for va, o, n in g:
            cur = d[off(va):off(va) + len(o)]
            s.add('o' if cur == o else 'n' if cur == n else 'b')
        res.append('orig' if s == {'o'} else 'new' if s == {'n'} else 'bad')
    return res

def main(a):
    if a and a[0] == '--check':
        d = open(a[1], 'rb').read()
        r = classify(d, [build_search(2, 2, 0x114, 0xc5), build_wheel(40)])
        print('search=%s wheel=%s' % tuple(r)); return 0
    opt = {'--min-x': 2, '--min-y': 2, '--max-x': 0x114, '--max-y': 0xc5, '--wheel-step': 40}; flags = set(); pos = []
    i = 0; big = None
    given = {x for x in a if x in opt}
    while i < len(a):
        if a[i] in opt: opt[a[i]] = int(a[i + 1], 0); i += 2
        elif a[i] == '--big': big = (int(a[i + 1], 0), int(a[i + 2], 0)); i += 3
        elif a[i] in ('--no-search', '--no-wheel'): flags.add(a[i]); i += 1
        else: pos.append(a[i]); i += 1
    if len(pos) != 2: print(__doc__); return 2
    d = bytearray(open(pos[0], 'rb').read())
    if len(d) < SIZE: print('wrong file size (need v1.0.0.62)'); return 3   # >= SIZE: an exe with the appended sections of make_exe_patches.py (frame) is fine
    groups = []
    if big:   # окно рюкзака игрока (NPC Inventory Plate) 332x310 -> (332+DX)x(310+DY): imm в конструкторе 0x522cdc (mov [esi+8],0x14c / mov [esi+0xc],0x136); область предметов растёт так же
        groups += [(0x522ce8, struct.pack('<I', 0x14c), struct.pack('<I', 0x14c + big[0])), (0x522cef, struct.pack('<I', 0x136), struct.pack('<I', 0x136 + big[1]))]
        if '--max-x' not in given: opt['--max-x'] += big[0]
        if '--max-y' not in given: opt['--max-y'] += big[1]
    if '--no-search' not in flags: groups += build_search(opt['--min-x'], opt['--min-y'], opt['--max-x'], opt['--max-y'])
    if '--no-wheel' not in flags: groups += build_wheel(opt['--wheel-step'])
    for va, o, n in groups:
        cur = bytes(d[off(va):off(va) + len(o)])
        if cur == n: continue                      # уже наложено (идемпотентность)
        if cur != o: print('unexpected bytes at %x' % va); return 4
        d[off(va):off(va) + len(n)] = n
    open(pos[1], 'wb').write(d)
    print('ok', pos[1], hashlib.sha256(d).hexdigest()); return 0

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
