#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Окно торговли v3 (CTradePlate 0x533330 / CBMCFlatInventoryViewer::Draw 0x531580), div.exe v1.0.0.62.
Накладывается на div_patched_inv4.exe (или оригинал); добавляет секцию .cave (VA 0x755000, 0x4000, RWX).
Что делает:
 * сетка плиток (число колонок = ширина списка/CW), иконка по низу плитки, подпись под иконкой, хит-тест по плитке;
 * АВТОГРУППИРОВКА: при каждой отрисовке (хук R 0x5315f8) строится порядок плиток — предметы, видимые в списке (spr!=0, count>0, прошли фильтр вкладки),
   сортируются (вставками, устойчиво) по ключу (ранг группы<<20 | архетип item+8), группа = категория записи архетипа `[[0x658bdc+0x1c]+arch*0x94+0x34]`:
   порядок групп: 1 оружие(cat1), 2 броня(cat0), 3 зелья/травы(cat3), 4 заклинания/книги(cat2), 5 прочее(cat4), 6 остальные; между группами ряд добивается до конца (новая группа с новой строки);
   позиция плитки i = TILE[i] (глобальный массив 0x756000+), вектор модели не трогается, хит-тест и блит используют ту же позицию (хук A).
 * вкладки-кнопки (в bmg обычные кнопки с name tabL0..4/tabR0..4, callback id 40..44/50..54, disabledlook = «нажатая» картинка): клик = выбрать категорию (повторный клик - снять фильтр),
   выбранная вкладка визуально «выключена» (vtable[0x5c](0/1) на кнопке); фильтр применяется только к спискам «рюкзак» (`[model+0x20]==0`), сторона `[viewer+0x58]` (0 игрок, 1 торговец).
 * наведение мыши не меняет вид (0x531875 je->jmp), ширина колонок/положения (imm в ctor).
usage: python trade_patch3.py <src> <dst> [--wb 334] [--wo 154] [--tab 40] [--cw 60] [--ch 100] [--icon 84] [--no-tabs] [--no-group] [--keep-hover]"""
import sys, struct, hashlib
from keystone import Ks, KS_ARCH_X86, KS_MODE_32
TEXT_VA = 0x401000; TEXT_RAW = 0x400
BASE = 0x755000; SECSIZE = 0x4000
G = BASE + 0x800
GK, GX, GC2, GB, GCOLS = G, G + 4, G + 8, G + 12, G + 16
GSEL = G + 32                      # [2]
GRP = G + 48                       # [8] ранг группы по категории
KEY, ORD, TILE = BASE + 0x1000, BASE + 0x2000, BASE + 0x3000   # по 1024 dword
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
    S('BagBox', 'Tradeplate Bag Box'); S('Fmt1', '* %d'); S('Fmt2', '* %d x %d')
    names = BASE + 0x100   # 10 имён по 8 байт: tabL0..4, tabR0..4
    for s_, side in enumerate('LR'):
        for k in range(5): blobs.append((names + (s_ * 5 + k) * 8, ('tab%s%d' % (side, k)).encode() + b'\0'))
    blobs.append((GRP, struct.pack('<8I', 1, 0, 3, 2, 4, 5, 5, 7)))
    blobs.append((GSEL, struct.pack('<ii', -1, -1)))
    cur = BASE + 0x200
    def put(src):
        nonlocal cur
        b = asm(src, cur); blobs.append((cur, b)); r = cur; cur = (cur + len(b) + 15) & ~15; assert cur < BASE + 0x800, hex(cur); return r
    group = not a['no_group']
    sortsrc = f"""
 sub esp, 0x20
 mov ebp, ebx
 cmp ebp, 1000
 jle Nok
 mov ebp, 1000
Nok:
 mov eax, [esi+0xc]
 sub eax, [esi+4]
 xor edx, edx
 mov ecx, {cw}
 div ecx
 test eax, eax
 jnz Cok
 mov eax, 1
Cok:
 mov [{GCOLS}], eax
 xor ebx, ebx
 xor esi, esi
P1:
 cmp ebx, ebp
 jge P1end
 mov dword ptr [ebx*4+{KEY}], -1
 lea eax, [esp+0x10]
 push eax
 lea eax, [esp+0xc+4]
 push eax
 lea eax, [esp+8+8]
 push eax
 lea eax, [esp+4+12]
 push eax
 lea eax, [esp+0+16]
 push eax
 push ebx
 mov ecx, [edi+0x60]
 mov edx, [ecx]
 call dword ptr [edx+0xc]
 cmp dword ptr [esp], 0
 je Pnext
 cmp dword ptr [esp+0x10], 1
 jl Pnext
 mov ecx, [edi+0x60]
 mov eax, [ecx+0x14]
 test eax, eax
 jz Pnext
 cmp ebx, [eax+0xc]
 jge Pnext
 mov ecx, [eax+4]
 cmp ebx, [ecx+4]
 jge Pnext
 mov eax, [ecx+8]
 imul eax, ebx
 add eax, [ecx]
 mov edx, [eax+8]
 xor ecx, ecx
 cmp word ptr [eax+0xc], -1
 setne cl
 mov [esp+0x14], ecx
 imul ecx, edx, 0x94
 mov eax, [0x658bdc]
 mov eax, [eax+0x1c]
 mov ecx, [eax+ecx+0x34]
 test ecx, ecx
 jnz Tnz
 mov ecx, 5
Tnz:
 dec ecx
 mov eax, [edi+0x60]
 cmp dword ptr [eax+0x20], 0
 jne NoF
 mov eax, [edi+0x58]
 mov eax, [eax*4+{GSEL}]
 test eax, eax
 js NoF
 cmp eax, ecx
 jne Pnext
NoF:
 cmp ecx, 4
 jbe Gin
 mov ecx, 5
Gin:
 cmp dword ptr [esp+0x14], 0
 je Gnorm
 mov ecx, 7
Gnorm:
 mov ecx, [ecx*4+{GRP}]
 shl ecx, 20
 and edx, 0xfffff
 or ecx, edx
 mov [ebx*4+{KEY}], ecx
 mov eax, esi
Ins:
 test eax, eax
 jz InsD
 mov edx, [eax*4+{ORD}-4]
 cmp [edx*4+{KEY}], ecx
 jbe InsD
 mov [eax*4+{ORD}], edx
 dec eax
 jmp Ins
InsD:
 mov [eax*4+{ORD}], ebx
 inc esi
Pnext:
 inc ebx
 jmp P1
P1end:
 xor ebx, ebx
 xor ecx, ecx
 mov edx, -1
P3:
 cmp ebx, esi
 jge Done
 mov eax, [ebx*4+{ORD}]
 mov ebp, [eax*4+{KEY}]
 shr ebp, 20
 cmp ebp, edx
 je Same
 cmp edx, -1
 je SetG
 push eax
 mov eax, ecx
 add eax, [{GCOLS}]
 dec eax
 xor edx, edx
 div dword ptr [{GCOLS}]
 imul ecx, eax, 1
 imul ecx, [{GCOLS}]
 pop eax
SetG:
 mov edx, ebp
Same:
 mov [eax*4+{TILE}], ecx
 inc ecx
 inc ebx
 jmp P3
Done:
 add esp, 0x20
""" if group else ""
    R = put(f"""
 mov [esp+0x1c], ebp
 mov [esp+0x38], ebp
 mov dword ptr [{GK}], 0
 pushad
{sortsrc}
 popad
 jmp 0x531600""")
    kexpr = f"mov eax, [ebp*4+{TILE}]" if group else f"mov eax, [{GK}]\n inc dword ptr [{GK}]"
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
 {kexpr}
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
 cmp edx, [edi+0x3c]
 jle K
 mov [edi+0x3c], edx
K:
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
 mov ecx, [edx*4+{GSEL}]
 test ecx, ecx
 js Fok
 mov edx, [eax+8]
 imul edx, edx, 0x94
 push eax
 mov eax, [0x658bdc]
 mov eax, [eax+0x1c]
 mov eax, [eax+edx+0x34]
 test eax, eax
 jnz Fnz
 mov eax, 5
Fnz:
 dec eax
 cmp eax, ecx
 pop eax
 je Fok
 pop edx
 jmp 0x531a71
Fok:
 pop edx
 cmp word ptr [eax+0xc], -1
 jmp 0x5316cf""")
    T = put(f"""
 mov dword ptr [{GSEL}], -1
 mov dword ptr [{GSEL+4}], -1
 push 0x6125d8
 jmp 0x533ca6""")
    common = put(f"""
 push esi
 push edi
 push ebx
 push ebp
 mov esi, [esp+0x14]
 mov edi, [esp+0x18]
 mov ebx, [esp+0x1c]
 cmp [edi*4+{GSEL}], ebx
 jne Setn
 mov ebx, -1
Setn:
 mov [edi*4+{GSEL}], ebx
 xor ebp, ebp
Lk:
 mov ecx, [esi+0x30]
 test ecx, ecx
 jz Lend
 mov eax, [ecx]
 lea edx, [edi+edi*4]
 add edx, ebp
 lea edx, [edx*8+{names}]
 push edx
 call dword ptr [eax+0x14]
 test eax, eax
 jz Ln
 mov ecx, eax
 mov edx, [eax]
 mov eax, [edx+0x5c]
 xor edx, edx
 cmp ebp, ebx
 setne dl
 push edx
 call eax
Ln:
 inc ebp
 cmp ebp, 5
 jl Lk
Lend:
 pop ebp
 pop ebx
 pop edi
 pop esi
 ret 0xc""")
    handlers = []
    for side in (0, 1):
        for k in range(5):
            handlers.append(((40 if side == 0 else 50) + k, put(f"""
 mov eax, [esp+4]
 push {k}
 push {side}
 push eax
 call {common}
 ret""")))
    regs = ''.join(f"""
 mov ecx, [0x6592c0]
 push ebx
 push esi
 push {h}
 push {i}
 call 0x45be90""" for i, h in handlers)
    H = put(regs + """
 mov ecx, [0x6592c0]
 push ebx
 jmp 0x533bdd""")
    FM1 = put(f"""
 mov edx, [esp+0x28]
 mov eax, 0x60cee8
 test edx, edx
 jz L
 cmp word ptr [edx+0xc], -1
 je L
 mov eax, {strs['Fmt1']}
L:
 push eax
 jmp 0x5319a8""")
    FM2 = put(f"""
 mov edx, [esp+0x2c]
 mov eax, 0x619f2c
 test edx, edx
 jz L
 cmp word ptr [edx+0xc], -1
 je L
 mov eax, {strs['Fmt2']}
L:
 push eax
 jmp 0x53198f""")
    BLK = put("""
 mov edi, eax
 test eax, eax
 jz Cont
 cmp word ptr [eax+0xc], -1
 jne Blocked
Cont:
 mov ecx, edi
 call 0x4af960
 jmp 0x5329e3
Blocked:
 jmp 0x532f13""")
    jmp = lambda frm, to, n: asm('jmp %d' % to, frm) + b'\x90' * (n - 5)
    h_ = lambda s: bytes.fromhex(s)
    hooks = [
        (0x5315f8, h_('896c241c896c2438'), jmp(0x5315f8, R, 8)),
        (0x5316dd, h_('8b4c24100fbf51088b460c2bc22b4604992bc28bd88b44241cd1fb895c24288944242c'), jmp(0x5316dd, A, 35)),
        (0x531710, h_('0fbf510a8b477483c21401573c3b44241c0f8c540100000fbf490a034c241c3bc10f8d44010000'), jmp(0x531710, B, 39)),
        (0x531a13, h_('8bc12b44241c'), jmp(0x531a13, C, 6)),
        (0x531a66, h_('8d4c1014'), h_('8b4c243c')),
        (0x5316c6, h_('8b4424246683780cff'), jmp(0x5316c6, F, 9)),
        (0x533ca1, h_('68d8256100'), jmp(0x533ca1, T, 5)),
        (0x5329da, h_('8bf88bcfe87dcff7ff'), jmp(0x5329da, BLK, 9)), (0x5319a3, h_('68e8ce6000'), jmp(0x5319a3, FM1, 5)), (0x53198a, h_('68' + '2c9f6100'), jmp(0x53198a, FM2, 5)),
        (0x5337ba, h_('f09f6100'), struct.pack('<I', strs['BagBox'])), (0x533b5d, h_('f09f6100'), struct.pack('<I', strs['BagBox'])),
    ]
    if not a['no_tabs']: hooks.append((0x533bd6, h_('8b0dc0926500' + '53'), jmp(0x533bd6, H, 7)))
    if not a['keep_hover']: hooks.append((0x531875, h_('74'), h_('eb')))
    x1 = 13 + wb + 4; x2 = x1 + wo + 4; x3 = x2 + wo + 4; width = x3 + wb + 13; shift = width - 454
    imms = [(0x5334bc, x1), (0x5334c6, x2), (0x5334d0, x3), (0x533453, 0x177 + shift), (0x53349f, 105 + tab)]
    return blobs, hooks, imms, cur, (x1, x2, x3, width)

def add_section(d):
    import pefile
    pe = pefile.PE(data=bytes(d), fast_load=True); fh = pe.NT_HEADERS.FILE_HEADER; oh = pe.OPTIONAL_HEADER
    if any(s.Name.rstrip(b'\0') == b'.cave' for s in pe.sections): raise SystemExit('source already has .cave - use inv4 as source')
    raw = (len(d) + 0x1ff) & ~0x1ff
    hdr_off = pe.sections[-1].get_file_offset() + 0x28
    d[hdr_off:hdr_off + 0x28] = struct.pack('<8sIIIIIIHHI', b'.cave', SECSIZE, BASE - oh.ImageBase, SECSIZE, raw, 0, 0, 0, 0, 0xE0000060)
    struct.pack_into('<H', d, fh.get_file_offset() + 2, fh.NumberOfSections + 1)
    struct.pack_into('<I', d, oh.get_file_offset() + 56, (BASE - oh.ImageBase) + SECSIZE)
    d += b'\0' * (raw - len(d)); d += b'\0' * SECSIZE
    return raw

def main(av):
    a = dict(wb=334, wo=154, tab=40, cw=60, ch=100, icon=84, no_tabs=False, no_group=False, keep_hover=False); pos = []; i = 0
    while i < len(av):
        k = av[i]
        if k in ('--wb', '--wo', '--tab', '--cw', '--ch', '--icon'): a[k[2:]] = int(av[i + 1], 0); i += 2
        elif k in ('--no-tabs', '--no-group', '--keep-hover'): a[k[2:].replace('-', '_')] = True; i += 1
        else: pos.append(k); i += 1
    if len(pos) != 2: print(__doc__); return 2
    d = bytearray(open(pos[0], 'rb').read())
    blobs, hooks, imms, end, geo = build(a)
    raw = add_section(d)
    for va, b in blobs: d[raw + (va - BASE):raw + (va - BASE) + len(b)] = b
    for va, o_, n in hooks:
        cur = bytes(d[off(va):off(va) + len(n)])
        if cur == n: continue
        if cur != o_: print('unexpected bytes at %x: %s' % (va, cur.hex())); return 4
        d[off(va):off(va) + len(n)] = n
    for va, n in imms: d[off(va):off(va) + 4] = struct.pack('<I', n)
    open(pos[1], 'wb').write(d)
    print('ok', pos[1], 'code end %x' % end, 'x1,x2,x3,width =', geo); print(hashlib.sha256(d).hexdigest()); return 0
if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
