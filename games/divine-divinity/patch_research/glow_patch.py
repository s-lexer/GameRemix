#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Подсветка предметов по rank (редкость 1-5) в окне рюкзака/сундука/торговца-списка (CBMCInventoryViewer FUN_005226e0),
Divine Divinity div.exe v1.0.0.62 (RU, 2461696 байт). Идемпотентный патч, накладывается на ЛЮБОЙ из: оригинал, inv-патчи (есть .cave), уже с .glow.

Что делает:
 * новая секция .glow (RWX; код + таблица цветов + буфер маски, 0x8000 байт в памяти, 0x1000 в файле); секцию .cave патч НЕ трогает;
 * хук: 0x52294b `call 0x556a80` (блит спрайта предмета в 16-бит поверхность окна) -> `call GLOW`;
 * GLOW: rank = *(*(link+0x84)+0x90), link = FUN_0057a970(arch,&flags,0,0) (create=0, без побочных эффектов);
   rank 0 / нет ссылки / нет модели / индекс вне границ -> ранний `jmp 0x556a80` (оригинальный путь без изменений);
   иначе ПОД спрайтом рисуется ореол: маска = спаны спрайта, расширенные на 2 px (по краям 1 px - «скруглённый» квадрат),
   пиксели маски смешиваются с фоном 50% с цветом rank ((d&m)>>1 + (c&m)>>1, m=0xF7DE для RGB565 / 0x7BDE для RGB555 по [0x64d4c8]);
   маска во временном буфере -> каждый пиксель смешивается РОВНО один раз; клип по W,H окна (как в 0x556a80), спрайт > 160 px и W/H вне 1..0x2000 - без ореола;
   затем `jmp 0x556a80` рисует сам предмет поверх.
 * цветные Alt-подписи на земле (alt_color_patch.py) накладываются тем же запуском (--no-alt отключает).
 * кукла (0x529d87/0x529dd5) НЕ делается: там рисует Slashed-DLL (vt+0x28), а не CPU-поверхность - см. docs/recon/2026-11-07_glow_patch.md.
usage: python glow_patch.py <src div.exe> <dst div.exe> [--no-alt]
       python glow_patch.py --check <exe>     (none / glow / unknown)"""
import sys, struct, hashlib, os
from keystone import Ks, KS_ARCH_X86, KS_MODE_32
TEXT_VA = 0x401000; TEXT_RAW = 0x400; IMGBASE = 0x400000
HOOK_VA = 0x52294b; HOOK_OLD = bytes.fromhex('e830410300')       # call 0x556a80
BLIT = 0x556a80
SEC_VSIZE = 0x8000; SEC_RAWSIZE = 0x1000
OFF_TAB = 0x400; OFF_MASK = 0x1000; MASK_MAX = SEC_VSIZE - OFF_MASK
GMAX = 160                                              # макс. ширина/высота спрайта (маска (GMAX+4)^2 <= MASK_MAX)
assert (GMAX + 4) ** 2 <= MASK_MAX
# цвета rank 3/4/5 (RGB565; 1 и 2 не подсвечиваются, ореол только у зелёных, жёлтых и золотых): серый, синий, зелёный, жёлтый, золотой/оранжевый (оттенки шрифтов игры fontgra/fontb/fontgr/fontyel/fontgo, ярче для ореола)
COLORS = [0x3EE7, 0xFF25, 0xFD40, 0x07FF, 0xF81F, 0xFFFF]   # [0]=rank3 зелёный, [1]=rank4 жёлтый, [2]=rank5 золотой; [3..5] только диагностический режим
ks = Ks(KS_ARCH_X86, KS_MODE_32)

def off(va): return va - TEXT_VA + TEXT_RAW

def build(base, diag=False, create=True):
    TAB = base + OFF_TAB; MASK = base + OFF_MASK
    LOC = 0x30; S = 0x10 + LOC
    DST, SPR, W, H, X, Y, EXT = [S + 4 + 4 * k for k in range(7)]
    SW, SH, BW, BH, CH, M, STR, N, DY, S0, E0 = [4 * k for k in range(11)]
    src = f"""
GLOW:
 cld
 mov eax, [edi+0x58]
 test eax, eax
 jz BYP
 mov ecx, [eax+0x14]
 test ecx, ecx
 jz BYP
 mov edx, [esp+0x3c]
 test edx, edx
 jl BYP
 cmp edx, [ecx+0xc]
 jge BYP
 mov ecx, [ecx+4]
 test ecx, ecx
 jz BYP
 cmp edx, [ecx+4]
 jge BYP
 mov eax, [ecx+8]
 imul eax, edx
 add eax, [ecx]
{{DIAGF}}
 mov edx, [eax+0x14]
 test edx, 0x80000
 jz NOFLAG
 test edx, 0x100000
 jnz HAVE
{{CREATE}}
HAVE:
 lea ecx, [eax+0x14]
 push 0
 push 0
 push ecx
 push dword ptr [eax+8]
 mov ecx, 0x750cfc
 call 0x57a970
 test eax, eax
 jz NOLINK
 mov eax, [eax+0x84]
 test eax, eax
 jz NOLINK
 mov eax, [eax+0x90]
 sub eax, 3
 cmp eax, 2
 ja NORANK
 jmp GO
NOFLAG:
 {{J2}}
NOLINK100:
 {{J3}}
NOLINK:
 {{J4}}
NORANK:
 {{J5}}
GO:
 push ebx
 push ebp
 push esi
 push edi
 sub esp, {LOC}
 mov ebx, [eax*4+{TAB}]
 mov ecx, 0xF7DE
 cmp dword ptr [0x64d4c8], 0
 jne C565
 mov ecx, 0x7BDE
 mov edx, ebx
 and edx, 0xFFC0
 shr edx, 1
 and ebx, 0x1F
 or ebx, edx
C565:
 mov [esp+{M}], ecx
 and ebx, ecx
 shr ebx, 1
 mov [esp+{CH}], ebx
 mov ebx, [esp+{SPR}]
 test ebx, ebx
 jz DONE
 movsx eax, word ptr [ebx+8]
 movsx ecx, word ptr [ebx+0xa]
 cmp eax, 1
 jl DONE
 cmp eax, {GMAX}
 jg DONE
 cmp ecx, 1
 jl DONE
 cmp ecx, {GMAX}
 jg DONE
 mov [esp+{SW}], eax
 mov [esp+{SH}], ecx
 mov edx, [esp+{W}]
 cmp edx, 1
 jl DONE
 cmp edx, 0x2000
 jg DONE
 mov edx, [esp+{H}]
 cmp edx, 1
 jl DONE
 cmp edx, 0x2000
 jg DONE
 mov edx, [esp+{W}]
 add edx, [esp+{EXT}]
 add edx, edx
 mov [esp+{STR}], edx
 add eax, 4
 add ecx, 4
 mov [esp+{BW}], eax
 mov [esp+{BH}], ecx
 imul eax, ecx
 add eax, 3
 shr eax, 2
 mov ecx, eax
 mov edi, {MASK}
 xor eax, eax
 rep stosd
 lea esi, [ebx+0xc]
 xor ebp, ebp
RowLoop:
 cmp ebp, [esp+{SH}]
 jge StepC
 movsx ecx, word ptr [esi]
 test ecx, ecx
 jl DONE
 cmp ecx, [esp+{SW}]
 jg DONE
 lea ebx, [esi+6]
 lea esi, [esi+ecx*4+8]
 mov [esp+{N}], ecx
SpanLoop:
 cmp dword ptr [esp+{N}], 0
 jle RowNext
 dec dword ptr [esp+{N}]
 movsx eax, word ptr [ebx]
 movsx edx, word ptr [ebx+2]
 add ebx, 4
 test edx, edx
 jle SpanLoop
 add eax, 2
 mov [esp+{S0}], eax
 add eax, edx
 mov [esp+{E0}], eax
 mov dword ptr [esp+{DY}], -2
DyLoop:
 mov ecx, [esp+{DY}]
 mov edi, 2
 cmp ecx, -2
 je E1
 cmp ecx, 2
 jne E2
E1:
 mov edi, 1
E2:
 add ecx, ebp
 add ecx, 2
 imul ecx, [esp+{BW}]
 add ecx, {MASK}
 mov eax, [esp+{S0}]
 sub eax, edi
 mov edx, [esp+{E0}]
 add edx, edi
 test eax, eax
 jge S_ok
 xor eax, eax
S_ok:
 cmp edx, [esp+{BW}]
 jle E_ok
 mov edx, [esp+{BW}]
E_ok:
 sub edx, eax
 jle DyNext
 lea edi, [ecx+eax]
 mov ecx, edx
 mov al, 1
 rep stosb
DyNext:
 inc dword ptr [esp+{DY}]
 cmp dword ptr [esp+{DY}], 2
 jle DyLoop
 jmp SpanLoop
RowNext:
 inc ebp
 jmp RowLoop
StepC:
 xor ebp, ebp
CRow:
 cmp ebp, [esp+{BH}]
 jge DONE
 mov eax, [esp+{Y}]
 lea eax, [eax+ebp-2]
 test eax, eax
 jl CNext
 cmp eax, [esp+{H}]
 jge CNext
 mov ecx, 2
 sub ecx, [esp+{X}]
 jge L1
 xor ecx, ecx
L1:
 mov edx, [esp+{W}]
 sub edx, [esp+{X}]
 add edx, 2
 cmp edx, [esp+{BW}]
 jle H1
 mov edx, [esp+{BW}]
H1:
 sub edx, ecx
 jle CNext
 imul eax, [esp+{STR}]
 add eax, [esp+{DST}]
 mov ebx, [esp+{X}]
 lea ebx, [ebx+ecx-2]
 lea edi, [eax+ebx*2]
 mov esi, [esp+{BW}]
 imul esi, ebp
 add esi, ecx
 add esi, {MASK}
 mov ecx, [esp+{M}]
 mov ebx, [esp+{CH}]
CPix:
 cmp byte ptr [esi], 0
 je CSkip
 movzx eax, word ptr [edi]
 and eax, ecx
 shr eax, 1
 add eax, ebx
 mov [edi], ax
CSkip:
 inc esi
 add edi, 2
 dec edx
 jnz CPix
CNext:
 inc ebp
 jmp CRow
DONE:
 add esp, {LOC}
 pop edi
 pop esi
 pop ebp
 pop ebx
BYP:
 jmp {BLIT}
"""
    byp = 'jmp BYP'
    jd = lambda n: ('mov eax, %d\n jmp GO' % n) if diag else byp
    create_src = '''
 test edx, 0x20000
 jnz NOLINK100
 push eax
 lea ecx, [eax+0x14]
 push 0
 push 1
 push ecx
 push dword ptr [eax+8]
 mov ecx, 0x750cfc
 call 0x57a970
 pop eax
 test dword ptr [eax+0x14], 0x100000
 jz NOLINK100''' if create else ' jmp NOLINK100'
    src = src.replace('{DIAGF}', '').replace('{CREATE}', create_src).replace('{J2}', jd(2)).replace('{J3}', jd(3)).replace('{J4}', jd(4)).replace('{J5}', jd(5))
    code = bytes(ks.asm(src, base)[0])
    assert len(code) < OFF_TAB, hex(len(code))
    tab = b''.join(struct.pack('<I', c) for c in COLORS)
    return code, tab

# только rank 3 (зелёный) и 4 (жёлтый) выделяются: в таблице кодов цвета названия FUN_0058a720 rank 1,2,5 -> код 2 (белый, как у обычных).
# Затрагивает и подсказки (общая функция), не только Alt-подписи.
NAME_PATCHES = [(0x58aa88, b'\x07', b'\x02'), (0x58aa8f, b'\x11', b'\x02'), (0x58aaa4, b'\x16', b'\x02')]

def hook_new(base):
    return b'\xe8' + struct.pack('<i', base - (HOOK_VA + 5))

def find_glow(pe):
    for s in pe.sections:
        if s.Name.rstrip(b'\0') == b'.glow': return s
    return None

def classify(d):
    import pefile
    pe = pefile.PE(data=bytes(d), fast_load=True)
    cur = bytes(d[off(HOOK_VA):off(HOOK_VA) + 5])
    s = find_glow(pe)
    if cur == HOOK_OLD and not s: return 'none'
    if s and cur == hook_new(IMGBASE + s.VirtualAddress): return 'glow'
    return 'unknown'

def apply_glow(d, diag=False, create=True):
    """d: bytearray (изменяется на месте, может вырасти). Возвращает базу секции."""
    import pefile
    pe = pefile.PE(data=bytes(d), fast_load=True); fh = pe.NT_HEADERS.FILE_HEADER; oh = pe.OPTIONAL_HEADER
    s = find_glow(pe)
    cur = bytes(d[off(HOOK_VA):off(HOOK_VA) + 5])
    if s is None:
        if cur != HOOK_OLD: raise SystemExit('unexpected bytes at hook %x: %s' % (HOOK_VA, cur.hex()))
        va = (oh.SizeOfImage + 0xfff) & ~0xfff
        base = IMGBASE + va
        raw = (len(d) + 0x1ff) & ~0x1ff
        hdr = pe.sections[-1].get_file_offset() + 0x28
        if hdr + 0x28 > pe.sections[0].PointerToRawData or any(d[hdr:hdr + 0x28]): raise SystemExit('no room for section header')
        d[hdr:hdr + 0x28] = struct.pack('<8sIIIIIIHHI', b'.glow', SEC_VSIZE, va, SEC_RAWSIZE, raw, 0, 0, 0, 0, 0xE0000060)
        struct.pack_into('<H', d, fh.get_file_offset() + 2, fh.NumberOfSections + 1)
        struct.pack_into('<I', d, oh.get_file_offset() + 56, va + SEC_VSIZE)
        d += b'\0' * (raw - len(d)); d += b'\0' * SEC_RAWSIZE
    else:
        base = IMGBASE + s.VirtualAddress; raw = s.PointerToRawData
        if cur != hook_new(base) and cur != HOOK_OLD: raise SystemExit('unexpected hook bytes: %s' % cur.hex())
    code, tab = build(base, diag, create)
    d[raw:raw + len(code)] = code
    d[raw + OFF_TAB:raw + OFF_TAB + len(tab)] = tab
    d[off(HOOK_VA):off(HOOK_VA) + 5] = hook_new(base)
    return base

def main(a):
    if a and a[0] == '--check':
        print(classify(open(a[1], 'rb').read())); return 0
    no_alt = '--no-alt' in a; a = [x for x in a if x not in ('--no-alt', '--name-colors-34', '--diag', '--no-create')]
    if len(a) != 2: print(__doc__); return 2
    d = bytearray(open(a[0], 'rb').read())
    if d[:2] != b'MZ' or len(d) < 2461696: print('unexpected file (div.exe v1.0.0.62 expected)'); return 3
    # проверка: «ядро» .text (хук) должно быть оригинальным или нашим
    base = apply_glow(d, '--diag' in sys.argv, '--no-create' not in sys.argv)
    if not no_alt:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import alt_color_patch as alt
        for va, o, n in alt.PATCHES:
            cur = bytes(d[off(va):off(va) + len(o)])
            if cur == n: continue
            if cur != o: print('alt: unexpected bytes at %x' % va); return 4
            d[off(va):off(va) + len(n)] = n
    if '--name-colors-34' in sys.argv:
        for va, o, n in NAME_PATCHES:
            cur = bytes(d[off(va):off(va) + 1])
            if cur == n: continue
            if cur != o: print('name table: unexpected byte at %x' % va); return 4
            d[off(va):off(va) + 1] = n
    open(a[1], 'wb').write(d)
    print('ok', a[1], 'glow base %x' % base, hashlib.sha256(d).hexdigest()); return 0

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
