#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Окно торговли v5 (inv10: FM2 исправлен — sprintf писал в запись предмета; высота содержимого из кэша; дебаунс вкладок; надето = экипировка без быстрых слотов; сортировка рюкзака Ctrl+S) = v4 (кэш порядка плиток, культивация невидимых, метка «надето» из таблицы строк RU/EN) = v3 (CTradePlate 0x533330 / CBMCFlatInventoryViewer::Draw 0x531580), div.exe v1.0.0.62.
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
import sys, os, struct, hashlib
from keystone import Ks, KS_ARCH_X86, KS_MODE_32
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sort_ranks
TEXT_VA = 0x401000; TEXT_RAW = 0x400
BASE = 0x755000; SECSIZE = 0x8000
G = BASE + 0x7E00   # глобалы + кэш: после таблицы рангов (она кончается на 0x7DE0); код .cave+0x200..0x1000
GK, GX, GC2, GB, GCOLS, GCUR = G, G + 4, G + 8, G + 12, G + 16, G + 20
GH, GLAST = G + 24, G + 28
SLOT = G + 0x100                    # 4 слота кэша по 32 байта: viewer, hash, gsel, n, cols; +0x80 счётчик замещения
GSEL = G + 32                      # [2]
GRP = G + 48                       # [8] ранг группы по категории
RPIDX, RPAGE, RANK_N = BASE + 0x7000, BASE + 0x7200, 7208
assert BASE + 0x7200 + 0xBE0 <= BASE + 0x7E00   # таблица рангов сортировки (sort_ranks.py): страницы по 16 слов; свободно 0x7000..0x8000 (TILE0 кончается на 0x7000)
KEY, ORD, TILE0 = BASE + 0x1000, BASE + 0x2000, BASE + 0x3000   # TILE0: 4 слота по 4 КБ   # по 1024 dword
# ---- таблица строк по языку/версии (ВСЕ вшиваемые тексты только здесь) ----
STRINGS = {'ru': {'worn': b'\xed\xe0\xe4\xe5\xf2\xee'},   # 'надето' = cp1251 (проверено 07.11: text.cmp RU и все fonts\font*.fnt однобайтные cp1251; в fontN*.fnt есть коды 0x21..0x7E и 0xC0..0xFF, 0xC0 ЕСТЬ - прежняя запись про "нет C0" была ошибкой разбора). Без %-спецификаторов
          'en': {'worn': b'worn'}}                        # EN: латиница (ASCII-глифы в шрифтах есть)
# ---- версии exe: размер + набор хуков (проверка исходных байт — в hooks); для английского exe адреса другие — добавить сюда новую запись
VERSIONS = {'ru-1.0.0.62': {'size': 2461696}}
LABELS = {}
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
    S('BagBox', 'Tradeplate Bag Box'); S('Fmt1', STRINGS[a['lang']]['worn'].decode('latin-1')); S('Fmt2', STRINGS[a['lang']]['worn'].decode('latin-1'))
    names = BASE + 0x100   # 10 имён по 8 байт: tabL0..4, tabR0..4
    for s_, side in enumerate('LR'):
        for k in range(5): blobs.append((names + (s_ * 5 + k) * 8, ('tab%s%d' % (side, k)).encode() + b'\0'))
    blobs.append((GRP, struct.pack('<8I', 1, 0, 3, 2, 4, 5, 5, 7)))
    blobs.append((GSEL, struct.pack('<ii', -1, -1)))
    rk = sort_ranks.load(); assert len(rk) >= 0x220 and len(rk) - 0x200 <= 0x7E00 - 0x7200, len(rk)
    blobs.append((RPIDX, rk[:0x200])); blobs.append((RPAGE, rk[0x200:]))
    cur = BASE + 0x200
    def put(src):
        nonlocal cur
        b = asm(src, cur); blobs.append((cur, b)); r = cur; cur = (cur + len(b) + 15) & ~15; assert cur < BASE + 0x1000, hex(cur); return r
    group = not a['no_group']
    sortbody = f"""
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
 je Ne
 test dword ptr [eax+0x14], 0x40000000
 jnz Ne
 mov ecx, 1
Ne:
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
 mov edi, [esp+0x28]
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
 mov [edi+eax*4], ecx
 inc ecx
 inc ebx
 jmp P3
Done:
"""

    R = put(f"""
 mov [esp+0x1c], ebp
 mov [esp+0x38], ebp
 pushad
 sub esp, 0x40
 mov ebp, ebx
 cmp ebp, 1000
 jle Nok
 mov ebp, 1000
Nok:
 mov [esp+0x30], ebp
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
 mov ecx, [edi+0x58]
 mov ecx, [ecx*4+{GSEL}]
 mov eax, [edi+0x60]
 cmp dword ptr [eax+0x20], 0
 je Gk
 mov ecx, -1
Gk:
 mov [esp+0x20], ecx
 mov ecx, [eax+0x24]
 mov [esp], ecx
 mov ecx, [eax+4]
 mov [esp+4], ecx
 mov dword ptr [esp+8], 0
 mov dword ptr [esp+0x10], 0
 mov ecx, [eax+0x14]
 test ecx, ecx
 jz Hprep
 mov edx, [ecx+0xc]
 mov ecx, [ecx+4]
 test ecx, ecx
 jz Hprep
 cmp edx, [ecx+4]
 jle Lm
 mov edx, [ecx+4]
Lm:
 mov [esp+0x10], edx
 mov edx, [ecx+8]
 mov [esp+0xc], edx
 mov edx, [ecx]
 mov [esp+8], edx
Hprep:
 mov esi, ebp
 add esi, [esp+0x20]
 xor ebx, ebx
H1:
 cmp ebx, ebp
 jge H1e
 imul esi, esi, 33
 mov eax, [esp]
 add esi, [eax+ebx*4]
 mov eax, [esp+4]
 add esi, [eax+ebx*4]
 cmp ebx, [esp+0x10]
 jge H1n
 mov eax, [esp+0xc]
 imul eax, ebx
 add eax, [esp+8]
 imul esi, esi, 33
 add esi, [eax+0x14]
 movzx ecx, word ptr [eax+0x10]
 imul esi, esi, 33
 add esi, ecx
 movzx ecx, word ptr [eax+0xc]
 imul esi, esi, 33
 add esi, ecx
H1n:
 inc ebx
 jmp H1
H1e:
 mov [esp+0x2c], esi
 xor ebx, ebx
 mov edx, -1
S1:
 cmp ebx, 4
 jge S1e
 mov eax, ebx
 shl eax, 5
 add eax, {SLOT}
 cmp [eax], edi
 je Found
 cmp dword ptr [eax], 0
 jne S1n
 cmp edx, -1
 jne S1n
 mov edx, ebx
S1n:
 inc ebx
 jmp S1
S1e:
 cmp edx, -1
 jne Hs
 mov edx, [{SLOT}+0x80]
 inc dword ptr [{SLOT}+0x80]
 and edx, 3
Hs:
 mov ebx, edx
 mov eax, ebx
 shl eax, 5
 add eax, {SLOT}
 mov [eax], edi
 mov dword ptr [eax+4], 0
 mov dword ptr [eax+8], -2
 jmp Rebuild
Found:
 mov ecx, [esp+0x2c]
 cmp [eax+4], ecx
 jne Rebuild
 mov ecx, [esp+0x20]
 cmp [eax+8], ecx
 jne Rebuild
 mov ecx, [esp+0x30]
 cmp [eax+12], ecx
 jne Rebuild
 mov ecx, [{GCOLS}]
 cmp [eax+16], ecx
 jne Rebuild
 jmp SetCur
Rebuild:
 mov [esp+0x24], eax
 mov [esp+0x34], ebx
 shl ebx, 12
 add ebx, {TILE0}
 mov [esp+0x28], ebx
 xor eax, eax
 mov ebp, [esp+0x30]
Ini:
 cmp eax, ebp
 jge Inie
 mov dword ptr [ebx+eax*4], -1
 inc eax
 jmp Ini
Inie:
 mov edx, [esp+0x20]
 mov [esp+0x20], edx
 xor ebx, ebx
 xor esi, esi
{sortbody}
 mov [esp+0x38], ecx
 mov eax, [esp+0x24]
 mov ecx, [esp+0x38]
 mov [eax+20], ecx
 mov ecx, [esp+0x2c]
 mov [eax+4], ecx
 mov ecx, [esp+0x20]
 mov [eax+8], ecx
 mov ecx, [esp+0x30]
 mov [eax+12], ecx
 mov ecx, [{GCOLS}]
 mov [eax+16], ecx
 mov ebx, [esp+0x34]
SetCur:
 mov eax, ebx
 shl eax, 12
 add eax, {TILE0}
 mov [{GCUR}], eax
 mov eax, ebx
 shl eax, 5
 add eax, {SLOT}
 mov ecx, [eax+20]
 add ecx, [{GCOLS}]
 dec ecx
 mov eax, ecx
 xor edx, edx
 div dword ptr [{GCOLS}]
 imul eax, eax, {ch}
 inc eax
 mov [{GH}], eax
 add esp, 0x40
 popad
 mov eax, [{GH}]
 mov [edi+0x3c], eax
 jmp 0x531600""")
    kexpr = f"mov eax, [{GCUR}]\n mov eax, [eax+ebp*4]"
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
 call dword ptr [0x60612c]
 mov ecx, [{GLAST}]
 mov edx, eax
 sub edx, ecx
 cmp edx, 250
 jae Gdb
 ret 0xc
Gdb:
 mov [{GLAST}], eax
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
 test dword ptr [edx+0x14], 0x40000000
 jnz L
 mov eax, {strs['Fmt1']}
L:
 push eax
 jmp 0x5319a8""")
    FM2 = put(f"""
 mov ecx, [esp+0x2c]
 mov eax, 0x619f2c
 test ecx, ecx
 jz L
 cmp word ptr [ecx+0xc], -1
 je L
 test dword ptr [ecx+0x14], 0x40000000
 jnz L
 mov eax, {strs['Fmt2']}
L:
 push eax
 jmp 0x53198f""")
    BLK = put("""
 mov edi, eax
 test eax, eax
 jz Cont
 cmp word ptr [eax+0xc], -1
 je Cont
 test dword ptr [eax+0x14], 0x40000000
 jz Blocked
Cont:
 mov ecx, edi
 call 0x4af960
 jmp 0x5329e3
Blocked:
 jmp 0x532f13""")
    GETSZ = put(f"""
 sub esp, 8
 lea eax, [esp+4]
 push eax
 lea eax, [esp+4]
 push eax
 push 0
 push edx
 mov ecx, [0x658bd8]
 call 0x4e8f20
 mov eax, [esp]
 mov ecx, [esp+4]
 add esp, 8
 ret""")
    SORT = put(f"""
 pushad
 sub esp, 0x80
 mov esi, ecx
 mov ebp, [esi+0xc]
 cmp ebp, 1000
 jle Sa
 mov ebp, 1000
Sa:
 mov eax, [esi+4]
 test eax, eax
 jz SEnd
 mov ecx, [eax+4]
 cmp ebp, ecx
 jle Sb
 mov ebp, ecx
Sb:
 mov [esp+8], eax
 xor ebx, ebx
 xor edi, edi
S1:
 cmp ebx, ebp
 jge S1e
 mov eax, [esp+8]
 mov ecx, [eax+8]
 imul ecx, ebx
 add ecx, [eax]
 cmp word ptr [ecx+0xc], -1
 jne S1n
 mov edx, [ecx+8]
 mov eax, 4
 cmp edx, {RANK_N}
 jae Stb
 imul ecx, edx, 0x94
 mov eax, [0x658bdc]
 mov eax, [eax+0x1c]
 mov eax, [eax+ecx+0x34]
 test eax, eax
 jnz Stc
 mov eax, 5
Stc:
 dec eax
 cmp eax, 4
 jbe Stb
 mov eax, 4
Stb:
 mov [esp+0x1c], eax
 cmp edx, {RANK_N}
 jae Sdf
 mov ecx, edx
 shr ecx, 4
 movzx ecx, byte ptr [ecx+{RPIDX}]
 shl ecx, 4
 mov eax, edx
 and eax, 15
 add ecx, eax
 movzx ecx, word ptr [ecx*2+{RPAGE}]
 test ecx, ecx
 jnz Sk
Sdf:
 mov ecx, 0xff00
Sk:
 shl ecx, 13
 and edx, 0x1fff
 or ecx, edx
 mov eax, [esp+0x1c]
 shl eax, 29
 or ecx, eax
 mov eax, edi
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
 mov [ebx*4+{KEY}], ecx
 mov [eax*4+{ORD}], ebx
 inc edi
S1n:
 inc ebx
 jmp S1
S1e:
 xor ebx, ebx
 mov dword ptr [esp+0x24], 0
P0:
 cmp ebx, edi
 jge P0e
 mov eax, [ebx*4+{ORD}]
 mov edx, [eax*4+{KEY}]
 mov ecx, edx
 shr ecx, 21
 and ecx, 0xff
 sub ecx, 0x30
 cmp ecx, 8
 ja P0n
 and edx, 0x1fff
 call {GETSZ}
 cmp eax, [esp+0x24]
 jle P0n
 mov [esp+0x24], eax
P0n:
 inc ebx
 jmp P0
P0e:
 cmp dword ptr [esp+0x24], 0
 je P0z
 add dword ptr [esp+0x24], 2
P0z:
 xor ebx, ebx
 mov dword ptr [esp+0x18], -1
 mov dword ptr [esp+0x1c], -1
 mov dword ptr [esp+0xc], 2
 mov dword ptr [esp+0x10], 2
 mov dword ptr [esp+0x14], 0
 mov dword ptr [esp+0x20], 0
S2:
 cmp ebx, edi
 jge S2e
 mov eax, [ebx*4+{ORD}]
 mov [esp+0x28], eax
 mov edx, [eax*4+{KEY}]
 mov ecx, edx
 shr ecx, 29
 cmp ecx, [esp+0x1c]
 je Stsm
 mov [esp+0x1c], ecx
 mov dword ptr [esp+0x18], -1
 mov dword ptr [esp+0xc], 2
 mov dword ptr [esp+0x10], 2
 mov dword ptr [esp+0x14], 0
 mov dword ptr [esp+0x20], 0
Stsm:
 mov ecx, edx
 shr ecx, 21
 cmp ecx, [esp+0x18]
 je Szd
 mov [esp+0x18], ecx
 cmp dword ptr [esp+0xc], 2
 jg Nrw
 cmp dword ptr [esp+0x14], 0
 jle Szd
Nrw:
 mov eax, [esp+0x14]
 add [esp+0x10], eax
 mov dword ptr [esp+0xc], 2
 mov dword ptr [esp+0x14], 0
 inc dword ptr [esp+0x20]
Szd:
 mov eax, [esp+0x28]
 mov edx, [eax*4+{KEY}]
 and edx, 0x1fff
 call {GETSZ}
 mov [esp], eax
 mov [esp+4], ecx
 mov edx, [esp+0x18]
 and edx, 0xff
 sub edx, 0x30
 cmp edx, 8
 ja Nocol
 mov eax, [esp+0x28]
 mov eax, [eax*4+{KEY}]
 shr eax, 13
 and eax, 0xff
 dec eax
 jl Nocol
 imul eax, [esp+0x24]
 add eax, 2
 cmp eax, [esp+0xc]
 jle Nocol
 mov [esp+0xc], eax
Nocol:
 mov ecx, [esp]
 mov edx, [esp+0xc]
 lea eax, [edx+ecx]
 cmp eax, {a['bagw']}
 jle Fit
 cmp edx, 2
 jle Fit
 mov eax, [esp+0x14]
 add [esp+0x10], eax
 mov dword ptr [esp+0xc], 2
 mov dword ptr [esp+0x14], 0
 inc dword ptr [esp+0x20]
Fit:
 mov eax, [esp+0x28]
 mov ecx, [esp+8]
 mov edx, [ecx+8]
 imul edx, eax
 add edx, [ecx]
 mov ecx, [esp+0xc]
 mov [edx], ecx
 mov ecx, [esp+0x10]
 mov [edx+4], ecx
 mov ecx, [esp]
 add ecx, 2
 add [esp+0xc], ecx
 mov ecx, [esp+4]
 cmp ecx, [esp+0x14]
 jle Nr
 mov [esp+0x14], ecx
Nr:
 mov ecx, [esp+0x1c]
 mov edx, ecx
 shl edx, 16
 or edx, [esp+0x20]
 mov [eax*4+{KEY}], edx
 mov edx, [esp+0x20]
 inc edx
 mov [esp+ecx*4+0x30], edx
 mov edx, [esp+0x10]
 add edx, [esp+0x14]
 mov [esp+ecx*4+0x44], edx
 inc ebx
 jmp S2
S2e:
 xor ecx, ecx
G0:
 cmp ecx, 5
 jge G0e
 mov esi, [esp+ecx*4+0x30]
 mov ebp, 4
 cmp esi, 1
 jle Gst
 mov eax, [esp+ecx*4+0x44]
 sub eax, 2
 mov edx, {a['bagh'] - 2}
 sub edx, eax
 jle Gst
 mov ebx, eax
 mov eax, edx
 xor edx, edx
 lea ebp, [esi-1]
 div ebp
 mov ebp, eax
 lea eax, [ebx+ebx*2]
 xor edx, edx
 div esi
 cmp ebp, eax
 jbe Gc1
 mov ebp, eax
Gc1:
 cmp ebp, 4
 jae Gst
 mov ebp, 4
Gst:
 mov [esp+ecx*4+0x44], ebp
 inc ecx
 jmp G0
G0e:
 xor ebx, ebx
Y0:
 cmp ebx, edi
 jge SEnd
 mov eax, [ebx*4+{ORD}]
 mov edx, [eax*4+{KEY}]
 mov ecx, edx
 shr ecx, 16
 and edx, 0xffff
 imul edx, [esp+ecx*4+0x44]
 mov ecx, [esp+8]
 imul eax, [ecx+8]
 add eax, [ecx]
 add [eax+4], edx
 inc ebx
 jmp Y0
SEnd:
 add esp, 0x80
 popad
 ret""")
    LABELS['SORT'] = SORT
    BTNH = put(f"""
 pushad
 mov eax, [0x658c04]
 test eax, eax
 jz Bd
 mov eax, [eax+0x4b4]
 test eax, eax
 jz Bd
 mov eax, [eax+0x10]
 mov ecx, [0x658d50]
 test ecx, ecx
 jz Bd
 mov ecx, [ecx+0xc]
 test ecx, ecx
 jz Bd
 mov edx, [ecx+eax*4]
 test edx, edx
 jz Bd
 mov edx, [edx+0x240]
 mov eax, [0x658c0c]
 test eax, eax
 jz Bd
 mov ecx, [eax]
 push edx
 call 0x4afb70
 test eax, eax
 jz Bd
 mov esi, eax
 mov ecx, esi
 call {SORT}
 push 1
 mov ecx, esi
 call 0x4aee90
 test eax, eax
 je Bd
 mov ecx, esi
 call 0x4af2a0
 push esi
 call 0x4fa540
 add esp, 4
Bd:
 popad
 ret""")
    BTNR = put(f"""
 call 0x45be90
 mov ecx, [0x6592c0]
 push 0
 push esi
 push {BTNH}
 push 60
 call 0x45be90
 jmp 0x522ad9""")
    HK = put(f"""
 cmp dword ptr [esp+0xc], 0x03
 jne Orig
 cmp dword ptr [esp+8], 0x102
 jne Orig
 pushad
 mov eax, [0x658c04]
 test eax, eax
 jz Done
 mov eax, [eax+0x4b4]
 test eax, eax
 jz Done
 mov eax, [eax+0x10]
 mov ecx, [0x658d50]
 test ecx, ecx
 jz Done
 mov ecx, [ecx+0xc]
 test ecx, ecx
 jz Done
 mov edx, [ecx+eax*4]
 test edx, edx
 jz Done
 mov edx, [edx+0x240]
 mov eax, [0x658c0c]
 test eax, eax
 jz Done
 mov ecx, [eax]
 push edx
 call 0x4afb70
 test eax, eax
 jz Done
 mov esi, eax
 mov ecx, esi
 call {SORT}
 push 1
 mov ecx, esi
 call 0x4aee90
 test eax, eax
 je Done
 mov ecx, esi
 call 0x4af2a0
 push esi
 call 0x4fa540
 add esp, 4
Done:
 popad
Orig:
 cmp dword ptr [0x658ce0], 0
 jmp 0x40c637""")
    E = put(f"""
 mov eax, [{GCUR}]
 mov eax, [eax+ebp*4]
 cmp eax, -1
 je Skp
 xor edx, edx
 div dword ptr [{GCOLS}]
 imul eax, eax, {ch}
 add eax, [edi+0x7c]
 sub eax, [esi+8]
 lea edx, [eax+{ch}]
 test edx, edx
 jle Skp
 mov edx, [esi+0x10]
 sub edx, [esi+8]
 cmp eax, edx
 jge Skp
 mov ecx, [edi+0x60]
 mov edx, [ecx]
 mov edx, [edx+0xc]
 jmp 0x531610
Skp:
 jmp 0x531a71""")
    jmp = lambda frm, to, n: asm('jmp %d' % to, frm) + b'\x90' * (n - 5)
    h_ = lambda s: bytes.fromhex(s)
    hooks = [
        (0x5315f8, h_('896c241c896c2438'), jmp(0x5315f8, R, 8)),
        (0x531608, h_('8b4f608b118b520c'), jmp(0x531608, E, 8)),
        (0x5316dd, h_('8b4c24100fbf51088b460c2bc22b4604992bc28bd88b44241cd1fb895c24288944242c'), jmp(0x5316dd, A, 35)),
        (0x531710, h_('0fbf510a8b477483c21401573c3b44241c0f8c540100000fbf490a034c241c3bc10f8d44010000'), jmp(0x531710, B, 39)),
        (0x531a13, h_('8bc12b44241c'), jmp(0x531a13, C, 6)),
        (0x531a66, h_('8d4c1014'), h_('8b4c243c')),
        (0x5316c6, h_('8b4424246683780cff'), jmp(0x5316c6, F, 9)),
        (0x533ca1, h_('68d8256100'), jmp(0x533ca1, T, 5)),
        (0x5329da, h_('8bf88bcfe87dcff7ff'), jmp(0x5329da, BLK, 9)), (0x5319a3, h_('68e8ce6000'), jmp(0x5319a3, FM1, 5)), (0x53198a, h_('68' + '2c9f6100'), jmp(0x53198a, FM2, 5)),
        (0x5337ba, h_('f09f6100'), struct.pack('<I', strs['BagBox'])), (0x533b5d, h_('f09f6100'), struct.pack('<I', strs['BagBox'])),
    ]
    if a['sort']: hooks.append((0x522ad4, h_('e8b793f3ff'), jmp(0x522ad4, BTNR, 5)))
    if a['sort']: hooks.append((0x40c630, h_('833de08c650000'), jmp(0x40c630, HK, 7)))
    if not a['no_tabs']: hooks.append((0x533bd6, h_('8b0dc0926500' + '53'), jmp(0x533bd6, H, 7)))
    if not a['keep_hover']: hooks.append((0x531875, h_('74'), h_('eb')))
    if a['pos']:
        # Start positions (07.11.2026): equipment and character-stats windows (DIVINITYTogglePlate 0x41cbf0, modes 0/1) at the top left, the backpack (0x41ca70) at the top right;
        # before, all of them opened at (100,100) on top of each other. The skills window (mode 2) and every position the player has already saved (Persist) stay as they are.
        # Screen size = [0x64d9b8] x [0x64d9bc] (logical px, as in the hotbar code 0x520e30). Bag: x = W - bagW - margin (>= margin), y = margin (or H - bagH - margin when the screen is low).
        mg, bw, bh = a['margin'], a['bag_size'][0], a['bag_size'][1]
        POSB = put(f"""
 mov eax, [0x64d9b8]
 sub eax, {bw + mg}
 cmp eax, {mg}
 jge Xok
 mov eax, {mg}
Xok:
 mov [esp+0x1c], eax
 mov eax, [0x64d9bc]
 sub eax, {bh + mg}
 cmp eax, {mg}
 jl Ylow
 mov eax, {mg}
 jmp Yst
Ylow:
 test eax, eax
 jge Yst
 xor eax, eax
Yst:
 mov [esp+0x20], eax
 ret""")
        POST = put(f"""
 mov eax, 100
 cmp ebx, 2
 jae Pst
 mov eax, {mg}
Pst:
 mov [esp+0x18], eax
 mov [esp+0x2c], eax
 ret""")
        hooks += [(0x41cb4d, h_('b864000000'), asm('call %d' % POSB, 0x41cb4d)), (0x41cb72, h_('89442420'), b'\x90' * 4), (0x41cb76, h_('89442424'), b'\x90' * 4),
                  (0x41cebe, h_('b864000000') + h_('89442414') + h_('89442428'), asm('call %d' % POST, 0x41cebe) + b'\x90' * 8)]
    x1 = 13 + wb + 4; x2 = x1 + wo + 4; x3 = x2 + wo + 4; width = x3 + wb + 13; shift = width - 454
    imms = [(0x5334bc, x1), (0x5334c6, x2), (0x5334d0, x3), (0x533453, 0x177 + shift), (0x53349f, 105 + tab)]
    return blobs, hooks, imms, cur, (x1, x2, x3, width)

def add_section(d):
    """Section .cave: reuse the one that the frame (tools/make_exe_patches.py) already put in the file; otherwise (old workflow: plain source exe) add it at BASE."""
    import pefile
    pe = pefile.PE(data=bytes(d), fast_load=True); fh = pe.NT_HEADERS.FILE_HEADER; oh = pe.OPTIONAL_HEADER
    for s in pe.sections:
        if s.Name.rstrip(b'\0') == b'.cave':
            if oh.ImageBase + s.VirtualAddress != BASE or s.SizeOfRawData < SECSIZE: raise SystemExit('.cave is not at the expected place')
            return s.PointerToRawData
    raw = (len(d) + 0x1ff) & ~0x1ff
    hdr_off = pe.sections[-1].get_file_offset() + 0x28
    d[hdr_off:hdr_off + 0x28] = struct.pack('<8sIIIIIIHHI', b'.cave', SECSIZE, BASE - oh.ImageBase, SECSIZE, raw, 0, 0, 0, 0, 0xE0000060)
    struct.pack_into('<H', d, fh.get_file_offset() + 2, fh.NumberOfSections + 1)
    struct.pack_into('<I', d, oh.get_file_offset() + 56, (BASE - oh.ImageBase) + SECSIZE)
    d += b'\0' * (raw - len(d)); d += b'\0' * SECSIZE
    return raw

def main(av):
    a = dict(wb=334, wo=154, tab=40, cw=60, ch=100, icon=84, no_tabs=False, no_group=False, keep_hover=False, lang='ru', sort=True, bagw=0x16e, bagh=369, pos=True, margin=16, bag_size=(422, 480)); pos = []; i = 0
    while i < len(av):
        k = av[i]
        if k in ('--wb', '--wo', '--tab', '--cw', '--ch', '--icon'): a[k[2:]] = int(av[i + 1], 0); i += 2
        elif k == '--no-sort': a['sort'] = False; i += 1
        elif k == '--no-pos': a['pos'] = False; i += 1
        elif k == '--margin': a['margin'] = int(av[i + 1], 0); i += 2
        elif k == '--bag-size': a['bag_size'] = (int(av[i + 1], 0), int(av[i + 2], 0)); i += 3
        elif k == '--bag-w': a['bagw'] = int(av[i + 1], 0); i += 2
        elif k == '--bag-h': a['bagh'] = int(av[i + 1], 0); i += 2
        elif k == '--lang': a['lang'] = av[i + 1]; i += 2
        elif k in ('--no-tabs', '--no-group', '--keep-hover'): a[k[2:].replace('-', '_')] = True; i += 1
        else: pos.append(k); i += 1
    if len(pos) != 2: print(__doc__); return 2
    d = bytearray(open(pos[0], 'rb').read())
    if len(d) < 2461696: print('unknown exe (1.0.0.62 expected)'); return 3
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
