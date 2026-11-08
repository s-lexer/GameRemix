#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Окно торговли v2 (CTradePlate 0x533330 / CBMCFlatInventoryViewer::Draw 0x531580), div.exe v1.0.0.62: ДВА РЮКЗАКА + СДЕЛКА.
Берёт div_patched_inv4.exe (или оригинал), ДОБАВЛЯЕТ секцию .cave (VA 0x755000, RWX) и кладёт туда весь новый код (размер файла растёт).
 1. Сетка плиток в вьюере (хуки 0x5315f8/0x5316dd/0x531710/0x531a13/0x531a66): число колонок = ширина списка / CW, иконка по низу плитки, подпись под иконкой по центру плитки,
    хит-тест = прямоугольник плитки, высота содержимого = (ряд+1)*CH. (В v1 после хука А в ebx оставалась Y вместо X — иконки не рисовались; исправлено.)
 2. Вкладки (фильтр по категории) только для «рюкзачных» списков (модель [+0x20]==0): хук 0x5316c6 — пропуск предмета, если категория `[[0x658bdc+0x1c]+arch*0x94+0x34]`
    != выбранной вкладки (индекс `[tab+0x64]` элемента 'TabL'/'TabR' формы tradepl.bmg, левый/правый рюкзак по `[viewer+0x58]`); начальная вкладка = как в инвентаре `[0x745434]` (хук 0x533ca1).
 3. Положения колонок (imm в ctor): box0 (13,105+TAB) рюкзак, box1 (x1,76), box2 (x2,76) сделка, box3 (x3,105+TAB) рюкзак торговца; правый трейдер 0x177 -> +сдвиг;
    «Tradeplate Bag Box» (новый блок bmg) для боксов рюкзаков — строки в .cave, push-ы 0x5337b9/0x533b5c.
 4. Наведение мыши не меняет вид (--no-hover-fx: 0x531875 je -> jmp: отключена подмена спрайта пульсирующим кольцом).
usage: python trade_patch2.py <src> <dst> [--wb 334] [--wo 154] [--tab 40] [--cw 60] [--ch 100] [--icon 84] [--no-tabs] [--keep-hover]"""
import sys, struct, hashlib
from keystone import Ks, KS_ARCH_X86, KS_MODE_32
TEXT_VA = 0x401000; TEXT_RAW = 0x400
BASE = 0x755000; DATA = BASE + 0xC00
GK, GX, GC2, GB, GSEL = DATA, DATA + 4, DATA + 8, DATA + 12, DATA + 16   # GSEL[0], GSEL[1]
def off(va): return va - TEXT_VA + TEXT_RAW
ks = Ks(KS_ARCH_X86, KS_MODE_32)
def asm(src, addr): return bytes(ks.asm(src, addr)[0])

def build(a):
    wb, wo, tab, cw, ch, icon = a['wb'], a['wo'], a['tab'], a['cw'], a['ch'], a['icon']
    cur = BASE; blobs = []
    strs = {}
    def S(name, text):
        nonlocal cur
        strs[name] = cur; b = text.encode('latin-1') + b'\0'; blobs.append((cur, b)); cur += (len(b) + 3) & ~3
    S('TabL', 'TabL'); S('TabR', 'TabR'); S('TabLc', 'TabL control'); S('TabRc', 'TabR control'); S('BagBox', 'Tradeplate Bag Box')
    cur = (cur + 15) & ~15
    def put(src):
        nonlocal cur
        b = asm(src, cur); blobs.append((cur, b)); r = cur; cur = (cur + len(b) + 15) & ~15; return r
    # --- R: начало отрисовки вьюера: сброс счётчика + выбранная вкладка этого списка
    R_next = None
    Rsrc = lambda: f"""
 mov [esp+0x1c], ebp
 mov [esp+0x38], ebp
 mov dword ptr [{GK}], 0
 mov dword ptr [{GSEL}], -1
 mov dword ptr [{GSEL+4}], -1
 mov ecx, [edi+0x60]
 cmp dword ptr [ecx+0x20], 0
 jne Rend
 mov eax, [edi+0x5c]
 test eax, eax
 jz Rend
 mov ecx, [eax+0x30]
 test ecx, ecx
 jz Rend
 mov eax, [edi+0x58]
 mov edx, {strs['TabL']}
 test eax, eax
 jz Rnm
 mov edx, {strs['TabR']}
Rnm:
 mov eax, [ecx]
 push edx
 call dword ptr [eax+0x14]
 test eax, eax
 jz Rend
 mov eax, [eax+0x64]
 mov ecx, [edi+0x58]
 mov [{GSEL}+ecx*4], eax
Rend:
 jmp 0x531600"""
    R = put(Rsrc())
    A = put(f"""
 mov eax, [esi+0xc]
 sub eax, [esi+4]
 xor edx, edx
 mov ecx, {cw}
 div ecx
 shr edx, 1
 mov [{GB}], edx
 test eax, eax
 jnz Lc
 mov eax, 1
Lc:
 mov ebx, eax
 mov eax, [{GK}]
 inc dword ptr [{GK}]
 xor edx, edx
 div ebx
 imul eax, eax, {ch}
 mov [esp+0x1c], eax
 imul edx, edx, {cw}
 add edx, [{GB}]
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
 jns L2
 xor ebx, ebx
L2:
 add ebx, [esp+0x1c]
 mov [esp+0x2c], ebx
 mov ebx, [esp+0x28]
 jmp 0x531700""")
    B = put(f"""
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
    C = put(f"""
 mov eax, [{GC2}]
 sub eax, [esp+0x1c]
 jmp 0x531a19""")
    F = put(f"""
 mov eax, [esp+0x24]
 push edx
 mov ecx, [edi+0x60]
 cmp dword ptr [ecx+0x20], 0
 jne Fok
 mov edx, [edi+0x58]
 mov ecx, [{GSEL}+edx*4]
 test ecx, ecx
 js Fok
 mov edx, [eax+8]
 imul edx, edx, 0x94
 push eax
 mov eax, [0x658bdc]
 mov eax, [eax+0x1c]
 cmp [eax+edx+0x34], ecx
 pop eax
 je Fok
 pop edx
 jmp 0x531a71
Fok:
 pop edx
 cmp word ptr [eax+0xc], -1
 jmp 0x5316cf""")
    def initname(n, k):
        return f"""
 mov ecx, [esi+0x30]
 mov eax, [ecx]
 push {strs[n]}
 call dword ptr [eax+0x14]
 test eax, eax
 jz I{k}
 mov edx, [0x745434]
 test edx, edx
 js I{k}
{'' if k % 2 else ' cmp edx, [eax+0x60]' + chr(10) + ' jge I%d' % k}
 mov [eax+{0x64 if k % 2 == 0 else 0x80}], edx
I{k}:"""
    T = put("""
 mov ecx, [esi+0x30]
 test ecx, ecx
 jz Tend""" + ''.join(initname(n, k) for k, n in enumerate(['TabL', 'TabLc', 'TabR', 'TabRc'])) + """
Tend:
 push 0x6125d8
 jmp 0x533ca6""")
    jmp = lambda frm, to, n: asm('jmp %d' % to, frm) + b'\x90' * (n - 5)
    h = lambda s: bytes.fromhex(s)
    hooks = [
        (0x5315f8, h('896c241c896c2438'), jmp(0x5315f8, R, 8)),
        (0x5316dd, h('8b4c24100fbf51088b460c2bc22b4604992bc28bd88b44241cd1fb895c24288944242c'), jmp(0x5316dd, A, 35)),
        (0x531710, h('0fbf510a8b477483c21401573c3b44241c0f8c540100000fbf490a034c241c3bc10f8d44010000'), jmp(0x531710, B, 39)),
        (0x531a13, h('8bc12b44241c'), jmp(0x531a13, C, 6)),
        (0x531a66, h('8d4c1014'), h('8b4c243c')),
    ]
    if not a['no_tabs']:
        hooks += [(0x5316c6, h('8b4424246683780cff'), jmp(0x5316c6, F, 9)), (0x533ca1, h('68d8256100'), jmp(0x533ca1, T, 5))]
    hooks += [(0x5337ba, h('f09f6100'), struct.pack('<I', strs['BagBox'])), (0x533b5d, h('f09f6100'), struct.pack('<I', strs['BagBox']))]
    if not a['keep_hover']: hooks.append((0x531875, h('74'), h('eb')))
    x1 = 13 + wb + 4; x2 = x1 + wo + 4; x3 = x2 + wo + 4; width = x3 + wb + 13; shift = width - 454
    imms = [(0x5334bc, 0x79, x1), (0x5334c6, 0xe5, x2), (0x5334d0, 0x151, x3), (0x533453, 0x177, 0x177 + shift), (0x53349f, 0x69, 105 + tab)]
    return blobs, hooks, imms, cur, (x1, x2, x3, width)

def add_section(d, blobs, size):
    import pefile
    nsec = struct.unpack_from('<H', d, 0x80 + 6)[0] if False else None
    pe = pefile.PE(data=bytes(d), fast_load=True)
    fh = pe.NT_HEADERS.FILE_HEADER; oh = pe.OPTIONAL_HEADER
    if any(s.Name.rstrip(b'\0') == b'.cave' for s in pe.sections): return d, False
    raw = (len(d) + 0x1ff) & ~0x1ff; vsz = 0x1000
    hdr_off = pe.sections[-1].get_file_offset() + 0x28
    sec = struct.pack('<8sIIIIIIHHI', b'.cave', vsz, BASE - oh.ImageBase, 0x1000, raw, 0, 0, 0, 0, 0xE0000060)
    d[hdr_off:hdr_off + 0x28] = sec
    struct.pack_into('<H', d, pe.NT_HEADERS.FILE_HEADER.get_file_offset() + 2, fh.NumberOfSections + 1)
    struct.pack_into('<I', d, oh.get_file_offset() + 56, (BASE - oh.ImageBase) + 0x1000)   # SizeOfImage
    d += b'\0' * (raw - len(d)); d += b'\0' * 0x1000
    return d, True

def main(av):
    a = dict(wb=334, wo=154, tab=40, cw=60, ch=100, icon=84, no_tabs=False, keep_hover=False); pos = []; i = 0
    while i < len(av):
        k = av[i]
        if k in ('--wb', '--wo', '--tab', '--cw', '--ch', '--icon'): a[k[2:]] = int(av[i + 1], 0); i += 2
        elif k == '--no-tabs': a['no_tabs'] = True; i += 1
        elif k == '--keep-hover': a['keep_hover'] = True; i += 1
        else: pos.append(k); i += 1
    if len(pos) != 2: print(__doc__); return 2
    d = bytearray(open(pos[0], 'rb').read())
    blobs, hooks, imms, end, geo = build(a)
    d, added = add_section(d, blobs, end)
    rawbase = len(d) - 0x1000 if added else None
    import pefile
    pe = pefile.PE(data=bytes(d), fast_load=True); sec = [s for s in pe.sections if s.Name.rstrip(b'\0') == b'.cave'][0]
    for va, b in blobs:
        o = sec.PointerToRawData + (va - BASE); d[o:o + len(b)] = b
    for va, o_, n in hooks:
        cur = bytes(d[off(va):off(va) + len(n)])
        if cur == n: continue
        if cur != o_: print('unexpected bytes at %x: %s' % (va, cur.hex())); return 4
        d[off(va):off(va) + len(n)] = n
    for va, o_, n in imms:
        c = struct.unpack('<I', d[off(va):off(va) + 4])[0]
        if c not in (o_, n) and c != 0x79 and True:
            # допускаем значения от прежнего trade_patch (dp=128)
            pass
        d[off(va):off(va) + 4] = struct.pack('<I', n)
    open(pos[1], 'wb').write(d)
    print('ok', pos[1], 'bytes', len(d), 'code end %x' % end, 'geometry x1,x2,x3,width =', geo, 'shift', geo[3] - 454)
    print(hashlib.sha256(d).hexdigest()); return 0
if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
