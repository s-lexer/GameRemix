# -*- coding: utf-8 -*-
"""tick80_patch.py (v3) - "такт 80 Гц" для Divine Divinity (div.exe 1.0.0.62): камера/пол/агенты ходят по НАТУРАЛЬНЫМ позициям
80 раз/с без интерполяции, а ЛОГИКА (мировой тик 0x505BC0: ИИ, пути, бой, анимации, магия, Osiris, таймеры) остаётся ровно 40 Гц и
видит ТОЛЬКО оригинальные позиции агентов.
Исследование и аудит: docs/recon/2026-11-07_tick80.md.

Схема "откат/возврат" (v2 с половинным шагом внутри тика ломала ИИ: логика видела p+v/2; v3 этого не делает):
  - мировой тик выполняется БЕЗ изменений: агент делает полный шаг v (оригинальная позиция p_N);
  - сразу после тика (чётный полутакт) позиции помеченных агентов (тех, кто шагнул в этом тике) откатываются на p_N - v/2:
    ИГРА РИСУЕТ ЭТО в кадре между тиками;
  - на нечётном полутакте (или перед следующим тиком) позиции возвращаются ровно к p_N (из сохранённых float/int значений).
  Возврат выполняется только если позиция агента не менялась с момента отката (иначе - телепорт, загрузка, смерть, команда:
  запись отбрасывается и чужая позиция не трогается).
Патчи (новая секция .t80 RWX):
  P  0x505A20  пейсер -> свой (полутакты 12,5 мс, busy-wait как в оригинале, исключение "герой стоит" сохранено; clock[4]++ на чётных)
  W  0x4AB51E  call 0x505BC0 -> обёртка (возврат перед тиком, откат после тика, возврат на нечётном полутакте)
  S  0x4AB74B  хвостовой jmp 0x4A9FB0 (отложенное СОХРАНЕНИЕ) -> если сохранение запрошено, сначала возврат позиций (сейв пишет истинные позиции)
  M  11 мест применения шага (fld/fadd [reg+0x22C]): пометка агента + запись v: 0x40EF95, 0x40F1EC, 0x40F402, 0x40F4FE, 0x411584,
     0x411E41, 0x42A1D2, 0x441BF6, 0x427D90, 0x428168, 0x441FEE (сам шаг не меняется). Последние три (v3.5: шаг по пути 0x427D30 и второй
     шаг 0x441A40) раньше пропускались: горожане, идущие по пути, стояли на позициях тика (40 Гц) при камере 80 Гц -> «ореол» при ходьбе.
Вместе с позицией сдвигаются vis+0x21C/0x220 (узел спрайта) и запись спрайта (DAT_006592dc +0x10/+0x12).
  F  0x582E04  (v3.6) анимации объектов мира (огонь, факелы, фонари, мерцание предметов, двери/сундуки; 0x582CC0, кадр +0x44) -
     1 кадр за 2 мировых тика (20 к/с при 40 тиках/с, как в режиме smooth 0, под который нарисованы клипы), если config smooth != 0.
     Фаза - свой счётчик: переключается при каждом НОВОМ номере тика clock[0] (не по чётности clock[4]: пейсер может добавить сразу 2+ тика,
     а мир делает один проход). Повторный вызов в том же тике видит ту же фазу. Эффекты заклинаний (0x4ED1B0...) не трогаются.
     Отчёт: docs/recon/2026-11-07_anim_speed.md §8.
  L  0x582F2A  (v3.7) зацикленные клипы объектов (ветка (f+1)%n в 0x582CC0): при smooth != 0 кадр = (S + h(экземпляр)) % n, S - номер шага
     анимации (PAR / FIRE_DIV), h = n * frac(адрес * K / 2^32), K = золотое сечение * 2^32 / 0x6C (соседние экземпляры на ~0,62 цикла врозь): у каждой свечи своя фаза, скорость прежняя, без признака/памяти, сейвы не
     затрагиваются (кадр пересчитывается из S и h). Мерцание (арх. 0x200), однократные и прочие ветки не трогаются; smooth 0 - оригинал. §10. Пейсер P остаток времени не теряет (REF2 += n*период) - мир ровно 40/с и стоя.
Использование: python tick80_patch.py in.exe out.exe [--test]. Конфиг игры: smooth 1. Не комбинировать с interp_patch.py.

РАСКЛАДКА "frame" (--frame; патч `tick80` программы GameRemix, games/divine-divinity/tools/make_exe_patches.py): вход - exe с "frame" (секции .cave/.glow/.interp
фиксированных адресов, +40960 байт). Своя секция НЕ добавляется (заголовок и длина exe не меняются, frame остаётся как выпущен): код и данные лежат в первых 4096 байтах
секции .interp (RVA 0x365000, raw 0x1000; та же область, что занимает interp - поэтому interp и такт 80 взаимно исключают друг друга), таблица агентов и список - в хвосте
виртуальной области .interp (VirtualSize 0x141000, загрузчик обнуляет). Таблица рассчитана на id агентов < NMAX (0x4000, 64 байта на запись = 1 МБ вместо 4 МБ); агент с id >= NMAX
в местах применения шага не помечается и идёт на позициях тика (без плавности, остальное не затронуто). Логика, хуки и содержимое кода те же, что в обычной раскладке.
"""
import sys, struct, argparse
import pefile
from keystone import Ks, KS_ARCH_X86, KS_MODE_32

IMG = 0x400000
HOOK_P, HOOK_W, HOOK_S = 0x505A20, 0x4AB51E, 0x4AB74B
HOOK_F, F_OLD, F_SKIP, F_CONT = 0x582E04, bytes.fromhex('8b464883f8ff0f8490020000'), 0x5830A0, 0x582E10   # mov eax,[esi+48]; cmp eax,-1; je 5830A0
# v3.7: looping-clip branch of 0x582CC0 right after n = 0x44D920(clip,1): mov ecx,eax; lea eax,[edi+1]; cdq; idiv ecx; movzx dx,dl; mov [esi+44],dx; jmp 582F62
HOOK_L, L_OLD, L_CONT = 0x582F2A, bytes.fromhex('8bc88d470199f7f9660fb6d266895644eb26'), 0x582F62
CFG, CLOCKP = 0x65B3D0, 0x658C44
T_SAVE = 0x4A9FB0
P_OLD = bytes.fromhex('568bf1c705')
T_WORLD = 0x505BC0
FTOL = 0x5E5D40
SEC_NAME = b'.t80'
OFF_DATA, OFF_TAB = 0x1200, 0x2000
STRIDE = 64            # запись на агента: +0 состояние(0/1 шагнул/2 откачен) +4 vx +8 vy +0C sx +10 sy +14 rx +18 ry +1C sIx +20 sIy +24 rIx +28 rIy +2C объект, который шагнул
# Откат/возврат трогают объект из ячейки списка, только если это ТОТ ЖЕ объект, что шагнул (+2C), и он агентского класса (vtable 0x60982C/0x6098CC): в тике игра может
# заменить объект агента в ячейке объектом другого класса (42C6C0), у которого в +0x2E4 не визуализатор - v3.5 1.0.27 падал на этом в setints (дамп 07.11.2026).
OFF_LIST = OFF_TAB + 65536 * STRIDE     # список id шагнувших агентов (ushort), счётчик CNT в секции данных +0x10
SEC_VSIZE = (OFF_LIST + 65536 * 2 + 0xFFF) & ~0xFFF
SEC_RAWSIZE = 0x2000
SEC_CHAR = 0xE0000060
# (va, 'fld'|'fadd', регистр агента)
SITES = [(0x40EF95, 'fld', 'ebx'), (0x40F1EC, 'fld', 'esi'), (0x40F402, 'fld', 'esi'), (0x40F4FE, 'fld', 'esi'),
         (0x411584, 'fld', 'edi'), (0x411E41, 'fld', 'edi'), (0x42A1D2, 'fadd', 'esi'), (0x441BF6, 'fld', 'esi'),
         (0x427D90, 'fld', 'esi'), (0x428168, 'fld', 'esi'), (0x441FEE, 'fld', 'esi')]
MODRM = {'ebx': 0x83, 'esi': 0x86, 'edi': 0x87}
NMAX = None           # None: таблица на все 65536 id; число: id >= NMAX не помечаются (раскладка frame)
SITE0, SITE_STEP = 0xC00, 0x80


def use_frame_layout():
    """код/данные внутри первых 0x1000 байт секции .interp frame, таблица и список - в её виртуальном хвосте (см. docstring)"""
    global OFFS, OFF_DATA, OFF_TAB, OFF_LIST, SEC_VSIZE, SEC_NAME, NMAX, SITE0, SITE_STEP
    SEC_NAME = b'.interp'; OFF_DATA = 0xF00; OFF_TAB = 0x1000; NMAX = 0x4000
    OFF_LIST = OFF_TAB + NMAX * STRIDE; SEC_VSIZE = OFF_LIST + 65536 * 2
    OFFS = dict(pacer=0, rollback=0x140, restore=0x240, setints=0x300, wrap=0x380, savehook=0x400, fire=0xC00, loop=0xC80)   # места 0x480..0xB60
    SITE0, SITE_STEP = 0x480, 0xA0


def site_old(kind, reg):
    return bytes([0xD9 if kind == 'fld' else 0xD8, MODRM[reg]]) + struct.pack('<I', 0x22C)


def rel(src, dst): return struct.pack('<i', dst - (src + 5))


PACER = """
pacer:
 push esi
 mov esi, ecx
 mov dword ptr [0x74478c], 0
 cmp dword ptr [esi+0x18], 0
 jne pret
 push ebx
 push edi
 mov edi, dword ptr [0x6064a0]
 call edi
 cmp dword ptr [0x658c14], 0
 mov ebx, eax
 je pdone
 mov eax, dword ptr [esi+0x20]
 cmp eax, dword ptr [{SEEN}]
 je psynced
 mov dword ptr [{SEEN}], eax
 add eax, eax
 mov dword ptr [{REF2}], eax
psynced:
 lea eax, [ebx+ebx]
 sub eax, dword ptr [{REF2}]
 cmp eax, dword ptr [esi+8]
 jae pgrant
 mov eax, dword ptr [0x6e0100]
 cmp dword ptr [eax+8], 0
 jne pwait
 mov ecx, dword ptr [0x658c04]
 mov edx, dword ptr [ecx+0x4b4]
 mov eax, dword ptr [edx+0x10]
 cmp dword ptr [ecx+0x4c0], eax
 jne pwait
 cmp eax, -1
 je pdone
 mov ecx, dword ptr [0x658d50]
 fldz
 mov edx, dword ptr [ecx+0xc]
 mov ecx, dword ptr [edx+eax*4]
 fcom dword ptr [ecx+0x22c]
 fnstsw ax
 test ah, 0x44
 jp pfp1
 fcomp dword ptr [ecx+0x230]
 fnstsw ax
 test ah, 0x44
 jnp pdone
 jmp pwait
pfp1:
 fstp st(0)
pwait:
 mov dword ptr [0x74478c], 1
pspin:
 call edi
 mov ebx, eax
 lea eax, [ebx+ebx]
 sub eax, dword ptr [{REF2}]
 cmp eax, dword ptr [esi+8]
 jb pspin
pgrant:
 call edi
 mov ebx, eax
 lea eax, [ebx+ebx]
 sub eax, dword ptr [{REF2}]
 xor edx, edx
 div dword ptr [esi+8]
 mov ecx, eax
 cmp ecx, 64
 ja preset
 imul eax, dword ptr [esi+8]
 add dword ptr [{REF2}], eax
 jmp pstore
preset:
 mov ecx, 2
 lea eax, [ebx+ebx]
 mov dword ptr [{REF2}], eax
pstore:
 mov eax, dword ptr [{REF2}]
 shr eax, 1
 mov dword ptr [esi+0x20], eax
 mov dword ptr [{SEEN}], eax
ploop:
 test ecx, ecx
 jz pdone
 inc dword ptr [{H}]
 test dword ptr [{H}], 1
 jnz pnext
 inc dword ptr [esi+4]
pnext:
 dec ecx
 jmp ploop
pdone:
 pop edi
 pop ebx
pret:
 pop esi
 ret

"""

LOOP_HEAD = """
 push ebx
 push esi
 push edi
 mov ecx, dword ptr [0x658d50]
 test ecx, ecx
 jz out
 mov ebx, dword ptr [ecx+0x10]
 mov edi, dword ptr [ecx+0xc]
 test edi, edi
 jz out
 xor esi, esi
loop:
 cmp esi, dword ptr [{CNT}]
 jge out
 movzx ecx, word ptr [esi*2+{LIST}]
 inc esi
 mov edx, ecx
 shl edx, 6
 add edx, {TAB}
"""
LOOP_TAIL = """
out:
 pop edi
 pop esi
 pop ebx
 ret
"""
ROLLBACK_BODY = """
 cmp ecx, ebx
 jge loop
 cmp dword ptr [edx], 1
 jne loop
 mov eax, dword ptr [edi+ecx*4]
 test eax, eax
 jz loop
 cmp eax, dword ptr [edx+0x2c]
 jne loop
 cmp dword ptr [eax], 0x60982C
 je rbok
 cmp dword ptr [eax], 0x6098CC
 jne loop
rbok:
 mov dword ptr [edx], 2
 push edx
 push eax
 mov ecx, dword ptr [eax+0xc]
 mov dword ptr [edx+0xc], ecx
 mov ecx, dword ptr [eax+0x10]
 mov dword ptr [edx+0x10], ecx
 mov ecx, dword ptr [eax+4]
 mov dword ptr [edx+0x1c], ecx
 mov ecx, dword ptr [eax+8]
 mov dword ptr [edx+0x20], ecx
 fld dword ptr [eax+0xc]
 fld dword ptr [edx+4]
 fmul dword ptr [{QUART}]
 frndint
 fadd st(0), st(0)
 fsubp st(1), st(0)
 fst dword ptr [eax+0xc]
 fstp dword ptr [edx+0x14]
 fld dword ptr [eax+0xc]
 call {FTOL}
 push eax
 mov eax, dword ptr [esp+4]
 mov edx, dword ptr [esp+8]
 fld dword ptr [eax+0x10]
 fld dword ptr [edx+8]
 fmul dword ptr [{QUART}]
 frndint
 fadd st(0), st(0)
 fsubp st(1), st(0)
 fst dword ptr [eax+0x10]
 fstp dword ptr [edx+0x18]
 fld dword ptr [eax+0x10]
 call {FTOL}
 mov edx, dword ptr [esp+8]
 mov dword ptr [edx+0x28], eax
 mov ecx, dword ptr [esp]
 mov dword ptr [edx+0x24], ecx
 mov edx, eax
 mov eax, dword ptr [esp+4]
 call {SETINTS}
 add esp, 12
 jmp loop
"""
# the restore does NOT ask for the same object (+0x2C): the message queue (50a290 -> 422750 -> 42C6C0) can clone the agent BETWEEN ticks, the clone carries the rolled-back p-d
# and would keep it for good (review 07.11.2026). The agent class + the exact rolled-back position are enough: a foreign-class object or a reloaded agent is not touched.
RESTORE_BODY = """
 push dword ptr [edx]
 mov dword ptr [edx], 0
 cmp ecx, ebx
 jge skip
 mov eax, dword ptr [edi+ecx*4]
 test eax, eax
 jz skip
 cmp dword ptr [eax], 0x60982C
 je rsok
 cmp dword ptr [eax], 0x6098CC
 jne skip
rsok:
 cmp dword ptr [esp], 2
 jne skip
 mov ecx, dword ptr [eax+0xc]
 cmp ecx, dword ptr [edx+0x14]
 jne skip
 mov ecx, dword ptr [eax+0x10]
 cmp ecx, dword ptr [edx+0x18]
 jne skip
 mov ecx, dword ptr [eax+4]
 cmp ecx, dword ptr [edx+0x24]
 jne skip
 mov ecx, dword ptr [eax+8]
 cmp ecx, dword ptr [edx+0x28]
 jne skip
 mov ecx, dword ptr [edx+0xc]
 mov dword ptr [eax+0xc], ecx
 mov ecx, dword ptr [edx+0x10]
 mov dword ptr [eax+0x10], ecx
 mov ecx, dword ptr [edx+0x1c]
 mov edx, dword ptr [edx+0x20]
 call {SETINTS}
skip:
 add esp, 4
 jmp loop
"""
RESTORE_TAIL = """
out:
 mov dword ptr [{CNT}], 0
 pop edi
 pop esi
 pop ebx
 ret
"""
SETINTS = """
 push ebx
 push esi
 mov ebx, eax
 mov esi, ecx
 sub esi, dword ptr [ebx+4]
 mov dword ptr [ebx+4], ecx
 mov ecx, edx
 sub ecx, dword ptr [ebx+8]
 mov dword ptr [ebx+8], edx
 mov edx, dword ptr [ebx+0x2e4]
 test edx, edx
 jz sdone
 add dword ptr [edx+0x21c], esi
 add dword ptr [edx+0x220], ecx
 cmp dword ptr [{RECSHIFT}], 0
 je sdone
 mov eax, dword ptr [edx+0x228]
 test eax, eax
 jl sdone
 mov edx, dword ptr [0x6592dc]
 mov edx, dword ptr [edx]
 cmp eax, dword ptr [edx+4]
 jge sdone
 imul eax, dword ptr [edx+8]
 add eax, dword ptr [edx]
 add word ptr [eax+0x10], si
 add word ptr [eax+0x12], cx
sdone:
 pop esi
 pop ebx
 ret
"""
WRAP = """
wrap:
 push esi
 push ebx
 mov esi, ecx
 xor ebx, ebx
 cmp dword ptr [esi+0x18], 0
 jne wcall
 mov eax, dword ptr [esi]
 cmp eax, dword ptr [esi+4]
 je wcall
 mov ebx, 1
 call {RESTORE}
wcall:
 mov ecx, esi
 call {T_WORLD}
 cmp dword ptr [esi+0x18], 0
 jne wout
 test ebx, ebx
 jz wnotick
 test dword ptr [{H}], 1
 jnz wout
 call {ROLLBACK}
 jmp wout
wnotick:
 test dword ptr [{H}], 1
 jz wout
 call {RESTORE}
wout:
 pop ebx
 pop esi
 ret
"""
SAVEHOOK = """
savehook:
 mov ecx, dword ptr [0x658c04]
 cmp dword ptr [ecx+0x46c], 0
 jne sv
 cmp dword ptr [ecx+0x468], 0
 jne sv
 mov edx, dword ptr [0x65b3d0]
 cmp dword ptr [edx+0xbc], 0
 jne sv
 jmp {T_SAVE}
sv:
 call {RESTORE}
 jmp {T_SAVE}
"""
OFFS = dict(pacer=0, rollback=0x300, restore=0x600, setints=0x900, wrap=0xA00, loop=0xA80, savehook=0xB00, fire=0x1180)   # места 0xC00..0x1180
FIRE_DIV = 4   # object clips advance once per FIRE_DIV world ticks: 4 = 10 fps (owner's choice 07.11.2026 after a 20/10 test); 2 = 20 fps
FIRE = """
fire:
 mov eax, dword ptr [{CLOCKP}]
 mov eax, dword ptr [eax]
 cmp eax, dword ptr [{LAST}]
 je fsame
 mov dword ptr [{LAST}], eax
 inc dword ptr [{PAR}]
fsame:
 mov eax, dword ptr [{CFG}]
 cmp dword ptr [eax+0x74], 0
 je forig
 test dword ptr [{PAR}], {FMASK}
 jnz {F_SKIP}
forig:
 mov eax, dword ptr [esi+0x48]
 cmp eax, -1
 je {F_SKIP}
 jmp {F_CONT}
"""
# v3.7 random phase of looping clips (owner 07.11.2026: identical candles in a row blinked in sync). Entry: eax = n (frames of the clip),
# edi = old frame, esi = instance, [esp+0x14] = archetype (0x94). Original: (f+1) % n. Ours at smooth != 0: (S + h) % n, S = PAR >> log2(FIRE_DIV)
# (+1 per animation step, the hook F lets the block run only when PAR % FIRE_DIV == 0), h = hi32(lo32(esi * 0x177083C) * n) = floor(n * frac(esi*K/2^32)),
# K = golden*2^32/0x6C: neighbouring instances (stride 0x6C) are ~0.618 of a cycle apart (a Weyl sequence, no two neighbours equal for n >= 3). Same speed (+1 per step),
# stateless (a frame from a save or a fresh instance just snaps to its phase on the first step). Twinkle mid-flash (arch 0x200) keeps +1.
LOOP = """
lphase:
 mov ecx, eax
 mov eax, dword ptr [{CFG}]
 cmp dword ptr [eax+0x74], 0
 je lorig
 mov eax, dword ptr [esp+0x14]
 test dword ptr [eax+0x1c], 0x200
 jnz lorig
 test ecx, ecx
 jle lorig
 imul eax, esi, 0x177083C
 mul ecx
 mov eax, dword ptr [{PAR}]
 shr eax, {FSHIFT}
 add eax, edx
 xor edx, edx
 div ecx
 jmp lstore
lorig:
 lea eax, [edi+1]
 cdq
 idiv ecx
lstore:
 movzx dx, dl
 mov word ptr [esi+0x44], dx
 jmp {L_CONT}
"""


def build(base, hero_only=False, rec_shift=True):
    D = base + OFF_DATA
    A = dict(H=D, REF2=D + 4, SEEN=D + 8, HALF=D + 12, CNT=D + 16, HEROONLY=D + 20, RECSHIFT=D + 24, QUART=D + 28, LAST=D + 32, PAR=D + 36, FMASK=FIRE_DIV - 1, FSHIFT=FIRE_DIV.bit_length() - 1, L_CONT=L_CONT, CLOCKP=CLOCKP, CFG=CFG, F_SKIP=F_SKIP, F_CONT=F_CONT, LIST=base + OFF_LIST, TAB=base + OFF_TAB, FTOL=FTOL, T_WORLD=T_WORLD,
             SETINTS=base + OFFS['setints'], ROLLBACK=base + OFFS['rollback'], RESTORE=base + OFFS['restore'])
    SRC = {'pacer': PACER.format(**A),
           'rollback': 'rollback:' + (LOOP_HEAD + ROLLBACK_BODY + LOOP_TAIL).format(**A),
           'restore': 'restore:' + (LOOP_HEAD + RESTORE_BODY + RESTORE_TAIL).format(**A),
           'setints': 'setints:' + SETINTS.format(**A), 'wrap': WRAP.format(**A), 'savehook': SAVEHOOK.format(T_SAVE=T_SAVE, **A), 'fire': FIRE.format(**A), 'loop': LOOP.format(**A)}
    offs = dict(OFFS)
    for i, (va, kind, reg) in enumerate(SITES):
        SRC['site%d' % i] = (' push eax\n push ecx\n@VT@ movzx ecx, word ptr [%s+0x214]\n@LIM@ cmp dword ptr [%d], 0\n je mk\n mov eax, dword ptr [0x658c04]\n cmp ecx, dword ptr [eax+0x4c0]\n jne done\nmk:\n'
                             ' mov eax, ecx\n shl eax, 6\n add eax, %d\n cmp dword ptr [eax], 1\n je upd\n'
                             ' mov dword ptr [eax], 1\n push edx\n mov edx, dword ptr [%d]\n mov word ptr [edx*2+%d], cx\n inc edx\n mov dword ptr [%d], edx\n pop edx\nupd:\n'
                             ' mov ecx, dword ptr [%s+0x22c]\n mov dword ptr [eax+4], ecx\n mov ecx, dword ptr [%s+0x230]\n mov dword ptr [eax+8], ecx\n mov dword ptr [eax+0x2c], %s\ndone:\n'
                             ' pop ecx\n pop eax\n .byte %s\n jmp %d\n') % (reg, A['HEROONLY'], A['TAB'], A['CNT'], A['LIST'], A['CNT'], reg, reg, reg, ','.join(str(b) for b in site_old(kind, reg)), va + 6)
        SRC['site%d' % i] = SRC['site%d' % i].replace('@LIM@', (' cmp ecx, %d\n jae done\n' % NMAX) if NMAX else '')
        # only the two agent classes (vtables 0x60982C agent.cpp, 0x6098CC agentnpc.cpp: vis at +0x2E4); the manager also holds objects of another class (vtable 0x609A5C)
        # with the same position fields but other data at +0x2E4 - marking them crashed the game in setints (v3.5 dump, 07.11.2026)
        SRC['site%d' % i] = SRC['site%d' % i].replace('@VT@', ' cmp dword ptr [{r}], 0x60982C\n je vt\n cmp dword ptr [{r}], 0x6098CC\n jne done\nvt:\n'.format(r=reg))
        offs['site%d' % i] = SITE0 + i * SITE_STEP
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    code = bytearray(OFF_DATA); labels = {}
    for name, text in SRC.items():
        enc, _ = ks.asm(text, addr=base + offs[name])
        e = bytes(enc)
        lim = min([o for o in offs.values() if o > offs[name]] + [OFF_DATA]) - offs[name]   # до следующего куска (или до данных)
        assert len(e) <= lim, (name, len(e), lim)
        code[offs[name]:offs[name] + len(e)] = e
        labels[name] = base + offs[name]
    data = struct.pack('<IIIfIIIfII', 0, 0, 0, 0.5, 0, 1 if hero_only else 0, 1 if rec_shift else 0, 0.25, 0xFFFFFFFF, 0)   # +20 LAST (номер тика, 'не было'), +24 PAR (фаза огня)
    return bytes(code), data, labels


def apply(d, hero_only=False, rec_shift=True, frame=False):
    if frame: use_frame_layout()
    d = bytearray(d)
    pe = pefile.PE(data=bytes(d), fast_load=True); fh = pe.NT_HEADERS.FILE_HEADER; oh = pe.OPTIONAL_HEADER
    off = lambda va: pe.get_offset_from_rva(va - IMG)
    sec = None
    for s in pe.sections:
        if s.Name.rstrip(b'\0') == SEC_NAME: sec = s
    if frame and (sec is None or sec.Misc_VirtualSize < SEC_VSIZE or sec.SizeOfRawData < OFF_DATA + 40): raise SystemExit('frame: no .interp section of the needed size')
    if sec is None:
        va = (max(x.VirtualAddress + max(x.Misc_VirtualSize, x.SizeOfRawData) for x in pe.sections) + 0xFFF) & ~0xFFF
        raw = (len(d) + 0x1FF) & ~0x1FF
        hdr = pe.sections[-1].get_file_offset() + 0x28
        if hdr + 0x28 > pe.sections[0].PointerToRawData or any(d[hdr:hdr + 0x28]): raise SystemExit('no room for section header')
        d[hdr:hdr + 0x28] = struct.pack('<8sIIIIIIHHI', SEC_NAME, SEC_VSIZE, va, SEC_RAWSIZE, raw, 0, 0, 0, 0, SEC_CHAR)
        struct.pack_into('<H', d, fh.get_file_offset() + 2, fh.NumberOfSections + 1)
        struct.pack_into('<I', d, oh.get_file_offset() + 56, va + SEC_VSIZE)
        d += b'\0' * (raw - len(d)); d += b'\0' * SEC_RAWSIZE
        base, fraw = IMG + va, raw
    else:
        base, fraw = IMG + sec.VirtualAddress, sec.PointerToRawData
    code, data, labels = build(base, hero_only, rec_shift)
    hooks = [(HOOK_P, P_OLD, b'\xe9' + rel(HOOK_P, labels['pacer'])),
             (HOOK_W, b'\xe8' + rel(HOOK_W, T_WORLD), b'\xe8' + rel(HOOK_W, labels['wrap'])),
             (HOOK_S, b'\xe9' + rel(HOOK_S, T_SAVE), b'\xe9' + rel(HOOK_S, labels['savehook'])),
             (HOOK_F, F_OLD, b'\xe9' + rel(HOOK_F, labels['fire']) + b'\x90' * 7),
             (HOOK_L, L_OLD, b'\xe9' + rel(HOOK_L, labels['loop']) + b'\x90' * 13)]
    for i, (va, kind, reg) in enumerate(SITES):
        hooks.append((va, site_old(kind, reg), b'\xe9' + rel(va, labels['site%d' % i]) + b'\x90'))
    for va, old, new in hooks:
        cur = bytes(d[off(va):off(va) + len(new)])
        if cur != new and cur[:len(old)] != old:
            raise SystemExit('unexpected bytes at %X: %s (ожидалось %s)' % (va, cur.hex(), old.hex()))
    if frame and any(d[fraw:fraw + sec.SizeOfRawData]) and bytes(d[fraw:fraw + len(code)]) != code: raise SystemExit('frame: the .interp raw data is not empty (another patch)')
    d[fraw:fraw + len(code)] = code
    d[fraw + OFF_DATA:fraw + OFF_DATA + len(data)] = data
    for va, old, new in hooks:
        d[off(va):off(va) + len(new)] = new
    return bytes(d), labels, base


# ---------------------------------------------------------------- Unicorn
def selftest(path):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ECX, UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP
    pe = pefile.PE(path); img = pe.get_memory_mapped_image()
    base = [IMG + s.VirtualAddress for s in pe.sections if s.Name.rstrip(b'\0') == SEC_NAME][0]
    code, data, labels = build(base)
    D = base + OFF_DATA; TAB = base + OFF_TAB
    out = []
    H = 0x20000000
    def mk():
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        top = max((len(img) + 0xFFF) & ~0xFFF, base - IMG + SEC_VSIZE)
        mu.mem_map(IMG, top); mu.mem_write(IMG, img)
        mu.mem_map(H, 0x100000)
        return mu
    r32 = lambda mu, a: struct.unpack('<I', bytes(mu.mem_read(a, 4)))[0]
    w32 = lambda mu, a, v: mu.mem_write(a, struct.pack('<I', v & 0xFFFFFFFF))
    f32 = lambda mu, a: struct.unpack('<f', bytes(mu.mem_read(a, 4)))[0]
    wf = lambda mu, a, v: mu.mem_write(a, struct.pack('<f', v))
    s32 = lambda mu, a: struct.unpack('<i', bytes(mu.mem_read(a, 4)))[0]
    STK = H + 0xF0000; STUB = H + 0x80000; AGENT_VT = 0x6098CC
    ok_all = []
    def line(text, ok):
        out.append(text + ' -> ' + ('OK' if ok else 'FAIL'))

    # ---- 1. пейсер
    mu = mk(); CLOCK = H + 0x2000; PLAYER = H + 0x1000; MGR = H + 0x4000; SRV = H + 0x3000
    mu.mem_write(STUB, b'\xc3'); w32(mu, 0x6064A0, STUB)
    w32(mu, 0x658C04, PLAYER); w32(mu, 0x658C44, CLOCK); w32(mu, 0x658C14, SRV); w32(mu, 0x658D50, MGR)
    w32(mu, 0x6E0100, H + 0x6000); w32(mu, H + 0x6000 + 8, 1)
    mu.mem_write(CLOCK, struct.pack('<9I', 0, 0, 25, 0, 1000, 0, 0, 0, 5000))
    st = {'t': 5000, 'n': 0}
    def hook(uc, addr, size, ud):
        if addr == STUB:
            st['n'] += 1
            if st['n'] % 40 == 0: st['t'] += 1
            uc.reg_write(1, 0) if False else None
            from unicorn.x86_const import UC_X86_REG_EAX
            uc.reg_write(UC_X86_REG_EAX, st['t'])
    mu.hook_add(UC_HOOK_CODE, hook)
    hs = []
    for _ in range(400):
        mu.reg_write(UC_X86_REG_ESP, STK); mu.mem_write(STK, struct.pack('<I', STUB + 0x100)); mu.mem_write(STUB + 0x100, b'\xf4')
        mu.reg_write(UC_X86_REG_ECX, CLOCK)
        mu.emu_start(labels['pacer'], STUB + 0x100)
        st['t'] += 1
        hs.append((r32(mu, D), r32(mu, CLOCK + 4)))
    ms = st['t'] - 5000; hh, tk = hs[-1]
    line('пейсер: %d полутактов (%.2f/с), мировых тиков %d (%.2f/с) за %d мс' % (hh, hh * 1000.0 / ms, tk, tk * 1000.0 / ms, ms), abs(hh * 1000.0 / ms - 80) < 0.8 and abs(tk * 1000.0 / ms - 40) < 0.5)
    steps = [hs[i + 1][0] - hs[i][0] for i in range(len(hs) - 1)]
    line('полутактов на кадр: min=%d max=%d (ожидалось 1); тик только на чётных: %s' % (min(steps), max(steps), all((hs[i + 1][1] - hs[i][1]) == (1 if hs[i + 1][0] % 2 == 0 else 0) for i in range(len(hs) - 1))),
         min(steps) == 1 and max(steps) == 1 and all((hs[i + 1][1] - hs[i][1]) == (1 if hs[i + 1][0] % 2 == 0 else 0) for i in range(len(hs) - 1)))

    # ---- мини-мир: "мировой тик" = лог позиции + шаг 42A1A0 + clock[0]=clock[4]
    mu = mk(); AG = H + 0x5000; MGR = H + 0x4000; ARR = H + 0x20000; CL = H + 0x2000; LOG = H + 0x9000
    VIS = H + 0x7000; TOBJ = H + 0x7400; TPTR = H + 0x7500; TAB2 = H + 0x7800
    w32(mu, 0x7520B4, 1); w32(mu, 0x658D50, MGR); w32(mu, 0x658C44, CL)
    PLY = H + 0x1000; w32(mu, 0x658C04, PLY); w32(mu, PLY + 0x4c0, 0x1234); w32(mu, D + 20, 0); w32(mu, D + 24, 1)     # герой = агент 0x1234, режим 'все агенты' (основной)
    w32(mu, 0x6592dc, TPTR); w32(mu, TPTR, TOBJ); w32(mu, TOBJ, TAB2); w32(mu, TOBJ + 4, 5); w32(mu, TOBJ + 8, 0x20)
    mu.mem_write(MGR + 0xC, struct.pack('<I', ARR)); w32(mu, MGR + 0x10, 0x4000)
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    stub, _ = ks.asm('cmp dword ptr [%d], 0\n jne stop\n mov eax, dword ptr [%d]\n cmp eax, dword ptr [%d]\n jne go\nstop:\n ret\ngo:\n mov eax, dword ptr [%d]\n mov dword ptr [%d], eax\n mov eax, dword ptr [%d]\n mov dword ptr [%d], eax\n mov ecx, %d\n call %d\n mov eax, dword ptr [%d]\n add eax, 1000\n mov dword ptr [%d], eax\n mov eax, dword ptr [%d]\n sub eax, 5\n mov word ptr [%d], ax\n mov eax, dword ptr [%d]\n mov dword ptr [%d], eax\n ret'
                     % (CL + 0x18, CL, CL + 4, AG + 0xC, LOG, AG + 4, LOG + 4, AG, 0x42A1A0, AG + 4, VIS + 0x21c, AG + 4, TAB2 + 2 * 0x20 + 0x10, CL + 4, CL), addr=T_WORLD)
    mu.mem_write(T_WORLD, bytes(stub))
    def agent(x, y, vx, vy, cnt, idv=0x1234, vis=True):
        mu.mem_write(AG, b'\0' * 0x400)
        wf(mu, AG + 0xC, x); wf(mu, AG + 0x10, y); w32(mu, AG + 4, int(x)); w32(mu, AG + 8, int(y))
        wf(mu, AG + 0x22C, vx); wf(mu, AG + 0x230, vy); w32(mu, AG + 0x278, cnt)
        mu.mem_write(AG + 0x214, struct.pack('<H', idv)); w32(mu, AG, AGENT_VT)
        if idv < (NMAX or 65536): mu.mem_write(TAB + idv * STRIDE, b'\0' * STRIDE)
        w32(mu, D + 16, 0)
        mu.mem_write(ARR, b'\0' * 0x8000); mu.mem_write(ARR + idv * 4, struct.pack('<I', AG))
        if vis:
            w32(mu, AG + 0x2e4, VIS); w32(mu, VIS + 0x21c, 1000 + int(x)); w32(mu, VIS + 0x220, 2000 + int(y)); w32(mu, VIS + 0x228, 2)
            mu.mem_write(TAB2 + 2 * 0x20 + 0x10, struct.pack('<hh', int(x) - 5, int(y) - 7))
    def wrap(h, tick, paused=False):
        """один кадр: полутакт h, tick - назначен мировой тик (clock[4]=clock[0]+1)"""
        w32(mu, D, h)
        mu.mem_write(CL, struct.pack('<9I', r32(mu, CL + 4), r32(mu, CL + 4) + (1 if tick else 0), 25, 0, 1000, 0, 1 if paused else 0, 0, 0))
        mu.reg_write(UC_X86_REG_ESP, STK); mu.mem_write(STK, struct.pack('<I', STUB + 0x100)); mu.mem_write(STUB + 0x100, b'\xf4')
        mu.reg_write(UC_X86_REG_ECX, CL); mu.reg_write(UC_X86_REG_EBX, 0x11111111); mu.reg_write(UC_X86_REG_ESI, 0x22222222); mu.reg_write(UC_X86_REG_EDI, 0x33333333)
        try: mu.emu_start(labels['wrap'], STUB + 0x100)
        except Exception as e:
            from unicorn.x86_const import UC_X86_REG_EIP
            raise RuntimeError('wrap(h=%d,tick=%s): eip=%X cl=%s %s' % (h, tick, mu.reg_read(UC_X86_REG_EIP), struct.unpack('<9I', bytes(mu.mem_read(CL, 36))), e))
    pos = lambda: (f32(mu, AG + 0xC), f32(mu, AG + 0x10), s32(mu, AG + 4), s32(mu, AG + 8))
    vispos = lambda: (r32(mu, VIS + 0x21c), r32(mu, VIS + 0x220), struct.unpack('<hh', bytes(mu.mem_read(TAB2 + 2 * 0x20 + 0x10, 4))))

    # ---- 2. агент идёт 3 тика и "доходит до цели"
    agent(100.0, 200.0, 4.0, -2.0, 3)
    shown = []; true = []; logic = []
    for k in range(1, 4):
        wrap(0, True); shown.append(pos()); logic.append((f32(mu, LOG), s32(mu, LOG + 4)))
        wrap(1, False); true.append(pos())
    exp_true = [(100.0 + 4 * k, 200.0 - 2 * k, 100 + 4 * k, 200 - 2 * k) for k in range(1, 4)]
    exp_shown = [(x - 2.0, y, int(x - 2.0), int(y)) for x, y, _, _ in exp_true]   # v=(4,-2): d=(2,0) (чётные сдвиги)
    exp_logic = [(100.0 + 4 * (k - 1), 100 + 4 * (k - 1)) for k in range(1, 4)]
    line('агент прошёл 3 тика: после тика (кадр между тиками) %s, после нечётного полутакта (истинная) %s; логика в начале тиков видит %s; счётчик шагов %d (ожидалось 0)' % (shown, true, logic, r32(mu, AG + 0x278)),
         shown == exp_shown and true == exp_true and logic == exp_logic and r32(mu, AG + 0x278) == 0)
    vp = vispos()
    line('визуализатор и запись спрайта после полного цикла равны исходным: %s (ожидалось 1100,2200,(95,193))' % (vp,), vp[0] == 1112 and vp[2] == (107, 193))
    agent(100.0, 200.0, 4.0, -2.0, 3); wrap(0, True); vp = vispos()
    line('визуализатор и запись спрайта в кадре между тиками сдвинуты на -v/2: %s (ожидалось 1102 = 1000 + 104 - 2, запись (97,193); сдвиг чётный: dy=0)' % (vp,), vp[0] == 1102 and vp[2] == (97, 193))

    # ---- 3. остановлен командой на полушаге (v=0, счётчик 0) до нечётного полутакта
    agent(100.0, 200.0, 4.0, -2.0, 3)
    wrap(0, True); a = pos()
    wf(mu, AG + 0x22C, 0.0); wf(mu, AG + 0x230, 0.0); w32(mu, AG + 0x278, 0)
    wrap(1, False); b = pos()
    line('остановка командой на полушаге: показано %s, после нечётного %s (ожидалось точка оригинала 104,198)' % (a[:2], b), b == (104.0, 198.0, 104, 198))

    # ---- 4. телепорт между тиками
    agent(100.0, 200.0, 4.0, -2.0, 3)
    wrap(0, True)
    wf(mu, AG + 0xC, 500.0); wf(mu, AG + 0x10, 600.0); w32(mu, AG + 4, 500); w32(mu, AG + 8, 600)
    wrap(1, False); b = pos()
    st0 = r32(mu, TAB + 0x1234 * STRIDE)
    line('телепорт на полушаге: после нечётного %s, запись откачена-состояние=%d (ожидалось 500,600 и 0)' % (b, st0), b == (500.0, 600.0, 500, 600) and st0 == 0)

    # ---- 5. загрузка сейва на нечётном полутакте: агент пересоздан (другой объект того же id)
    agent(100.0, 200.0, 4.0, -2.0, 3)
    wrap(0, True)
    agent(321.5, 222.25, 0.0, 0.0, 0)
    wrap(1, False); b = pos()
    line('загрузка на нечётном полутакте: позиция загруженного агента %s не тронута, запись=%d' % (b, r32(mu, TAB + 0x1234 * STRIDE)), b == (321.5, 222.25, 321, 222) and r32(mu, TAB + 0x1234 * STRIDE) == 0)

    # ---- 6. диалог / пауза: тика нет или пауза -> позиции не меняются ни на каком полутакте
    agent(100.0, 200.0, 4.0, -2.0, 3)
    p0 = pos()
    r = []
    for h in (0, 1, 0, 1): wrap(h, False); r.append(pos())
    wrap(0, True, paused=True); r.append(pos()); wrap(1, False, paused=True); r.append(pos())
    line('диалог (тика нет) и пауза: позиции неизменны %s' % (all(x == p0 for x in r),), all(x == p0 for x in r))

    # ---- 7. смерть/исчезновение агента с откатом, затем id занят новым агентом
    agent(100.0, 200.0, 4.0, -2.0, 3)
    wrap(0, True)
    mu.mem_write(ARR + 0x1234 * 4, struct.pack('<I', 0))            # агент удалён из списка
    wrap(1, False)
    stale = r32(mu, TAB + 0x1234 * STRIDE)
    agent(50.0, 60.0, 4.0, 0.0, 3)                               # новый агент с тем же id
    wrap(0, True); a = pos(); wrap(1, False); b = pos()
    line('исчезновение с откатом: запись после возврата=%d (сброшена); новый агент с тем же id: показано %s, истинная %s (ожидалось 52,60 и 54,60)' % (stale, a[:2], b[:2]),
         a[:2] == (52.0, 60.0) and b[:2] == (54.0, 60.0))

    # ---- 7a. в тике объект агента заменён в ячейке объектом другого класса (42C6C0; дамп вылета 1.0.27): откат и возврат его не трогают
    OTH = H + 0xA000
    agent(100.0, 200.0, 4.0, -2.0, 3)
    mu.mem_write(OTH, b'\0' * 0x400); w32(mu, OTH, 0x609A5C); mu.mem_write(OTH + 0x214, struct.pack('<H', 0x1234)); wf(mu, OTH + 0xC, 500.0); wf(mu, OTH + 0x10, 600.0)
    w32(mu, OTH + 4, 500); w32(mu, OTH + 8, 600); w32(mu, OTH + 0x2e4, 0x88007400)
    def swap(uc, addr, size, ud): uc.mem_write(ARR + 0x1234 * 4, struct.pack('<I', OTH))   # после тика, до отката: ячейку занял другой объект
    hs_ = mu.hook_add(UC_HOOK_CODE, swap, begin=labels['rollback'], end=labels['rollback'])
    ok_ = True
    try: wrap(0, True); wrap(1, False)
    except Exception as e: ok_ = str(e)
    mu.hook_del(hs_)
    oth = (f32(mu, OTH + 0xC), f32(mu, OTH + 0x10), s32(mu, OTH + 4), s32(mu, OTH + 8))
    line('объект агента заменён в тике объектом другого класса: откат/возврат его не трогают, без сбоя: %s, позиция %s (ожидалось 500,600)' % (ok_, oth), ok_ is True and oth == (500.0, 600.0, 500, 600))

    # ---- 7c. между тиками (очередь сообщений, 42C6C0) агент клонирован: клон с откатанной позицией p-d возвращается в p
    CLN = H + 0xB000; VIS2 = H + 0x7200
    agent(100.0, 200.0, 4.0, -2.0, 3); wrap(0, True)
    mu.mem_write(CLN, bytes(mu.mem_read(AG, 0xB7 * 4)) + b'\0' * 0x200); w32(mu, CLN + 0x2e4, VIS2); w32(mu, VIS2 + 0x21c, 1102); w32(mu, VIS2 + 0x220, 2198); w32(mu, VIS2 + 0x228, -1)
    mu.mem_write(ARR + 0x1234 * 4, struct.pack('<I', CLN))
    wrap(1, False)
    cl = (f32(mu, CLN + 0xC), f32(mu, CLN + 0x10), s32(mu, CLN + 4), s32(mu, CLN + 8), r32(mu, VIS2 + 0x21c))
    line('клон агента между тиками (откат в нём): после нечётного %s (ожидалось 104,198 и визуализатор 1104)' % (cl,), cl == (104.0, 198.0, 104, 198, 1104))

    # ---- 7b. отложенное сохранение на полушаге: позиции возвращаются до записи сейва
    PL = H + 0x1000; w32(mu, 0x658C04, PL); w32(mu, 0x65B3D0, H + 0x1800)
    def savecase(flag):
        agent(100.0, 200.0, 4.0, -2.0, 3); wrap(0, True)
        mu.mem_write(PL, b'\0' * 0x600); w32(mu, PL + 0x4c0, 0x1234); w32(mu, H + 0x1800 + 0xbc, 0)
        if flag: w32(mu, PL + 0x46c, 1)
        mu.reg_write(UC_X86_REG_ESP, STK); mu.mem_write(STK, struct.pack('<I', STUB + 0x100)); mu.mem_write(STUB + 0x100, b'\xf4')
        mu.mem_write(T_SAVE, b'\xf4')
        try: mu.emu_start(labels['savehook'], T_SAVE)
        except Exception as e: raise RuntimeError('savehook %s' % e)
        return pos()
    a, b = savecase(True), savecase(False)
    line('сохранение запрошено: позиция %s (ожидалось истинная 104,198); не запрошено: %s (откат остаётся, 102,198)' % (a[:2], b[:2]), a == (104.0, 198.0, 104, 198) and b[:2] == (102.0, 198.0))

    # ---- 10. монотонность и ровность показанных позиций по кадрам (hero и камера), случайные длительности кадров
    import random
    rnd = random.Random(7)
    def model(pattern, label, tick_prob=1.0, pause_at=None):
        agent(1000.0, 200.0, 4.0, -2.0, 100000)
        w32(mu, base + OFF_DATA + 16, 0)
        Hh = 1; w32(mu, CL + 4, 0)
        wrap_h = lambda h, tick: wrap(h, tick)
        # состояние: Hh - текущий полутакт после прошлого кадра; начинаем с нечётного (истинная позиция), тик 0 уже был
        shown = []; hs = []; cam = []; spr = []
        for n in pattern:
            ticks = sum(1 for k in range(1, n + 1) if (Hh + k) % 2 == 0)
            Hh += n
            wrap(Hh, ticks > 0)
            sx, sy, ix, iy = pos(); shown.append(ix); hs.append(Hh); cam.append(ix + 17)
            rx_ = struct.unpack('<hh', bytes(mu.mem_read(TAB2 + 2 * 0x20 + 0x10, 4)))[0]
            spr.append((r32(mu, VIS + 0x21c) - ix, rx_ - ix, (ix + 17) - cam[-1] + 17 - 17))
        ideal = [1000 + 2 * h - 2 - 2 for h in hs]       # H=1 -> 1000 (нет откатов до первого тика); нормировка ниже
        base0 = shown[0] - (2 * hs[0])
        dev = [shown[i] - (base0 + 2 * hs[i]) for i in range(len(shown))]
        steps = [shown[i + 1] - shown[i] for i in range(len(shown) - 1)]
        want = [2 * (hs[i + 1] - hs[i]) for i in range(len(hs) - 1)]
        mono = all(st >= 0 for st in steps)
        line('%s: кадров %d, макс. отклонение от линейной последовательности %d пикс., монотонно=%s, шаги == 2*полутактов=%s, спрайт-минус-камера постоянен=%s'
             % (label, len(shown), max(abs(d) for d in dev), mono, steps == want, len(set(spr)) == 1),
             max(abs(d) for d in dev) == 0 and mono and steps == want and len(set(spr)) == 1)
    wrap(1, False) if False else None
    model([1] * 200, 'кадры == полутакты (80 кадров/с)')
    model([rnd.choice([1, 1, 1, 2]) for _ in range(300)], 'нерегулярные кадры (1-2 полутакта, ~25% по 2)')
    model([rnd.choice([1, 2]) for _ in range(300)], 'тяжёлые кадры (50% по 2 полутакта, тик и нечётный в одном кадре)')
    model([2] * 100, 'каждый кадр по 2 полутакта (40 кадров/с, тик в каждом кадре)')
    model([1, 1, 0, 0, 1, 0, 1, 1, 0, 1] * 20, 'кадры без полутакта между ними (свободный ход, 179 Гц)')

    # ---- 11. устаревшая метка: тик и нечётный в одном кадре, затем тик без движения агента -> нет ложного отката
    agent(100.0, 200.0, 4.0, -2.0, 100000)
    wrap(1, False); w32(mu, CL + 4, 0)
    wrap(3, True)                      # тик + нечётный в одном кадре: метка есть, отката нет
    wf(mu, AG + 0x22C, 0.0); wf(mu, AG + 0x230, 0.0); w32(mu, AG + 0x278, 1000)
    a0 = pos()
    wrap(4, True)                      # тик, агент стоит: метки нет (остановка)
    a1 = pos(); wrap(5, False); a2 = pos()
    line('устаревшая метка (тик+нечётный в одном кадре, потом агент встал): позиции %s -> %s -> %s (ожидалось без дёрганья)' % (a0[:2], a1[:2], a2[:2]), a0 == a1 == a2)

    # ---- 11b. раскладка frame: id агента >= NMAX не помечается (без плавности, без записи вне таблицы)
    if NMAX:
        agent(100.0, 200.0, 4.0, -2.0, 3, idv=NMAX + 0x1000)
        wrap(0, True); a = pos(); wrap(1, False); b = pos()
        line('id агента вне таблицы (0x%X >= NMAX 0x%X): позиции тика %s -> %s, список пуст (%d), состояние сброшено' % (NMAX + 0x1000, NMAX, a[:2], b[:2], r32(mu, D + 16)),
             a == b == (104.0, 198.0, 104, 198) and r32(mu, D + 16) == 0)
    # ---- 12. стоимость: 5000 агентов в списке, 20 шагают; число выполненных инструкций обёртки (чётный и нечётный кадр)
    cnt = {'n': 0}
    def hk(uc, addr, size, ud): cnt['n'] += 1
    mu.mem_write(ARR, b'\0' * 0x8000)
    mu.mem_map(0x30000000, 0x600000)
    for i in range(5000):
        a_ = 0x30000000 + i * 0x400
        mu.mem_write(a_, b'\0' * 0x400); w32(mu, a_, AGENT_VT); mu.mem_write(a_ + 0x214, struct.pack('<H', 100 + i)); mu.mem_write(ARR + (100 + i) * 4, struct.pack('<I', a_))
        wf(mu, a_ + 0xC, 50.0); wf(mu, a_ + 0x10, 60.0)
    w32(mu, 0x658D50, MGR); w32(mu, MGR + 0x10, 0x4000)
    # 20 из них помечены как шагнувшие (имитация маркёров)
    for i in range(20):
        e = TAB + (100 + i) * STRIDE
        mu.mem_write(e, struct.pack('<I', 1)); wf(mu, e + 4, 4.0); wf(mu, e + 8, 0.0); w32(mu, e + 0x2c, 0x30000000 + i * 0x400)
        mu.mem_write(base + OFF_LIST + i * 2, struct.pack('<H', 100 + i))
    w32(mu, base + OFF_DATA + 16, 20)
    hh = mu.hook_add(UC_HOOK_CODE, hk)
    try: mu.ctl_flush_tb()
    except Exception: pass
    a_first = 0x30000000
    def direct(lbl):
        mu.reg_write(UC_X86_REG_ESP, STK); mu.mem_write(STK, struct.pack('<I', STUB + 0x100)); mu.mem_write(STUB + 0x100, b'\xf4')
        mu.emu_start(labels[lbl], STUB + 0x100)
    direct('rollback'); n_even = cnt['n']; mid = f32(mu, a_first + 0xC), f32(mu, a_first + 0x10 + 0x400 * 4999); cnt['n'] = 0
    direct('restore'); n_odd = cnt['n']; end = f32(mu, a_first + 0xC)
    mu.hook_del(hh)
    line('стоимость при 5000 агентах (20 шагают): откат %d, возврат %d инструкций (старая схема с обходом всех агентов: ~70-100 тыс. на проход)' % (n_even, n_odd), n_even < 3000 and n_odd < 3000 and mid[0] == 48.0 and end == 50.0 and mid[1] == 60.0)
    out[-1] = out[-1].replace('инструкций', 'инструкций (агент #0: откат %.0f, возврат %.0f; не шагавшие не тронуты: %.0f)' % (mid[0], end, mid[1]))
    mu.mem_write(T_WORLD, bytes(stub)); mu.mem_write(ARR, b'\0' * 0x8000)
    # ---- 13. производные объекты: тело (vis+0x21C), тень/запись спрайта, свет и узел сортировщика (строятся при рисовании из живой позиции)
    #          идут по горизонтали; рассогласование между слоями на каждом кадре должно быть 0
    def layers(pattern, hero=True):
        idv = 0x1234 if hero else 0x2222
        agent(1000.0, 200.0, 4.0, 0.0, 100000, idv=idv)
        Hh = 1; w32(mu, CL + 4, 0); mism = 0; xs = []
        for n in pattern:
            ticks = sum(1 for k in range(1, n + 1) if (Hh + k) % 2 == 0)
            Hh += n; wrap(Hh, ticks > 0)
            sx, sy, ix, iy = pos()
            body = r32(mu, VIS + 0x21c) - 1000                      # экранная x тела (в координатах агента)
            shadow = struct.unpack('<hh', bytes(mu.mem_read(TAB2 + 2 * 0x20 + 0x10, 4)))[0] + 5   # запись спрайта (тень/Cube)
            light = ix                                             # свет 448250: из живой позиции при рисовании
            world = ix                                             # узел сортировщика +0x50: из живой позиции при рисовании
            mism = max(mism, abs(body - ix), abs(shadow - ix), abs(light - ix), abs(world - ix)); xs.append(ix)
        return mism, xs
    m_h, xs_h = layers([1] * 120)
    m_a, xs_a = layers([rnd.choice([1, 1, 2]) for _ in range(200)])
    line('слои агента (тело, тень, свет, узел) идут по горизонтали, герой: макс. рассогласование %d (80 к/с) и %d (нерегулярные кадры)' % (m_h, m_a), m_h == 0 and m_a == 0)
    # режим 'только герой': NPC не откатывается (позиции == оригинал в каждом кадре), герой откатывается
    w32(mu, D + 20, 1)
    m_n, xs_n = layers([1] * 60, hero=False)
    line('NPC в режиме "только герой": позиции в кадрах == оригинальные позиции тика (шаг 4 пикс. за тик, 2 кадра на тик): %s' % (xs_n[:6],), xs_n[:6] == [1004, 1004, 1008, 1008, 1012, 1012])
    w32(mu, D + 20, 0)
    m_n2, xs_n2 = layers([1] * 60, hero=False)
    line('NPC в режиме "все агенты": 80 различных позиций за секунду, слои согласованы (%d): %s' % (m_n2, xs_n2[:6]), m_n2 == 0 and xs_n2[:6] == [1002, 1004, 1006, 1008, 1010, 1012])
    w32(mu, D + 20, 0)
    # ---- 14. все агенты: настоящая камера 0x4A4BC0 (по герою) и каждый агент, v = 3,4,5,6,8, нерегулярные кадры
    mu.mem_write(0x51B980, b'\xc2\x08\x00')                    # FUN_0051b980 (позиция слушателя звука) - заглушка stdcall ret 8
    PLY = H + 0x1000; C54 = H + 0x1400; W75 = H + 0x1600
    mu.mem_write(PLY, b'\0' * 0x600); w32(mu, 0x658C04, PLY); w32(mu, PLY + 0x4c0, 0x1234); w32(mu, PLY + 0x4c4, 1); w32(mu, PLY + 0x4a8, 1)
    mu.mem_write(C54, b'\0' * 0x20); w32(mu, 0x658C54, C54)
    mu.mem_write(W75, b'\0' * 0x80); w32(mu, 0x75182C, W75); w32(mu, W75 + 4, 0x200); w32(mu, W75 + 8, 0x200)
    w32(mu, 0x64D9B8, 1280); w32(mu, 0x64D9BC, 720)
    AGTAB = H + 0x1700; NAGENTS = 8
    ks2 = Ks(KS_ARCH_X86, KS_MODE_32)
    stub2, _ = ks2.asm("""
 cmp dword ptr [%d], 0
 jne stop
 mov eax, dword ptr [%d]
 cmp eax, dword ptr [%d]
 jne go
stop:
 ret
go:
 push ebx
 push esi
 xor esi, esi
nxt:
 cmp esi, dword ptr [%d]
 jge fin
 mov ebx, dword ptr [esi*4+%d]
 mov ecx, ebx
 call %d
 mov eax, dword ptr [ebx+4]
 mov ecx, dword ptr [ebx+0x2e4]
 add eax, 1000
 mov dword ptr [ecx+0x21c], eax
 inc esi
 jmp nxt
fin:
 mov eax, dword ptr [%d]
 mov dword ptr [%d], eax
 pop esi
 pop ebx
 ret
""" % (CL + 0x18, CL, CL + 4, AGTAB - 4, AGTAB, 0x42A1A0, CL + 4, CL), addr=T_WORLD)
    mu.mem_write(T_WORLD, bytes(stub2)); mu.ctl_flush_tb()
    def multi(speeds, pattern, label):
        mu.mem_write(ARR, b'\0' * 0x8000); mu.mem_write(TAB, b'\0' * (STRIDE * 0x1300)); w32(mu, D + 16, 0)
        w32(mu, AGTAB - 4, len(speeds))
        ags = []
        for i, sp in enumerate(speeds):
            a_ = H + 0x40000 + i * 0x400; v_ = H + 0x60000 + i * 0x400; idv = 0x1234 + i
            mu.mem_write(a_, b'\0' * 0x400); mu.mem_write(v_, b'\0' * 0x400)
            x0 = 1000.0 + 50 * i
            wf(mu, a_ + 0xC, x0); wf(mu, a_ + 0x10, 300.0 + 40 * i); w32(mu, a_ + 4, int(x0)); w32(mu, a_ + 8, 300 + 40 * i)
            wf(mu, a_ + 0x22C, float(sp)); wf(mu, a_ + 0x230, 0.0); w32(mu, a_ + 0x278, 100000)
            w32(mu, a_ + 0x1c, 10); w32(mu, a_ + 0x20, 20)
            mu.mem_write(a_ + 0x214, struct.pack('<H', idv)); w32(mu, a_, AGENT_VT); w32(mu, a_ + 0x2e4, v_); w32(mu, v_ + 0x21c, 1000 + int(x0)); w32(mu, v_ + 0x228, 0xFFFFFFFF)
            mu.mem_write(ARR + idv * 4, struct.pack('<I', a_)); w32(mu, AGTAB + i * 4, a_); ags.append(a_)
        w32(mu, MGR + 0xC, ARR)
        Hh = 1; w32(mu, CL + 4, 0)
        seq = [[] for _ in speeds]; cams = []
        for n in pattern:
            ticks = sum(1 for k in range(1, n + 1) if (Hh + k) % 2 == 0)
            Hh += n; wrap(Hh, ticks > 0)
            mu.reg_write(UC_X86_REG_ESP, STK); mu.mem_write(STK, struct.pack('<I', STUB + 0x100)); mu.mem_write(STUB + 0x100, b'\xf4')
            mu.reg_write(UC_X86_REG_ECX, PLY); mu.emu_start(0x4A4BC0, STUB + 0x100)
            cams.append(s32(mu, PLY + 0x4a0))
            for i, a_ in enumerate(ags): seq[i].append((s32(mu, a_ + 4), r32(mu, r32(mu, a_ + 0x2e4) + 0x21c) - 1000))
        res = []
        okm = True
        cam_steps = [cams[i + 1] - cams[i] for i in range(len(cams) - 1)]
        want_step = lambda sp, n: sp * n / 2.0
        hero_sp = speeds[0]
        ideal_dev = 0.0
        for i, sp in enumerate(speeds):
            xs = [q[0] for q in seq[i]]; vs = [q[1] for q in seq[i]]
            mono = all(xs[j + 1] >= xs[j] for j in range(len(xs) - 1))
            dev = max(abs(xs[j] - (xs[0] + sp * (j + 1 + 0) / 2.0 * 1.0 * 0)) for j in range(0)) if False else 0
            # отклонение от идеальной линейной (по числу полутактов) последовательности
            hs_ = []; Hh2 = 1
            for n in pattern: Hh2 += n; hs_.append(Hh2)
            ideal = [(1000.0 + 50 * i) + sp * (h / 2.0 - 0.5) if h % 2 == 0 else (1000.0 + 50 * i) + sp * (h - 1) / 2.0 for h in hs_]
            d = max(abs(xs[j] - int(ideal[j])) for j in range(len(xs)))
            const = len(set(v - x for x, v in seq[i])) == 1
            res.append((sp, mono, d, const))
            okm = okm and mono and const and d <= 1
        cam_const = len(set(cams[j] - seq[0][j][0] for j in range(len(cams)))) == 1
        line('%s: камера и агенты v=%s: монотонно=%s; макс. отклонение от линейной идеальной (пикс.) %s; тело-минус-живая позиция постоянно=%s; камера-минус-герой постоянно=%s; шаги камеры за кадр %s'
             % (label, speeds, all(r[1] for r in res), [r[2] for r in res], all(r[3] for r in res), cam_const, sorted(set(cam_steps))), okm and cam_const)
        return cam_steps
    rnd2 = random.Random(11)
    multi([4, 3, 5, 6, 8], [1] * 200, 'камера по реальному 0x4A4BC0, 80 к/с')
    multi([3, 4, 5, 6, 8], [1] * 200, 'герой v=3')
    multi([5, 4, 3, 6, 8], [rnd2.choice([1, 1, 2]) for _ in range(300)], 'герой v=5, нерегулярные кадры')
    multi([8, 4, 3, 5, 6], [rnd2.choice([1, 2]) for _ in range(300)], 'герой v=8 (бег), тяжёлые кадры')
    mu.mem_write(T_WORLD, bytes(stub)); mu.ctl_flush_tb()
    # ---- 15. 16 направлений движка x скорости 2, 4, 8: показанные смещения и паритет (смещение от настоящей позиции - ЧЁТНОЕ по обеим осям)
    DIRV = [(0, -1), (-0.5, -1), (-1, -1), (-1, -0.5), (-1, 0), (-1, 0.5), (-1, 1), (-0.5, 1), (0, 1), (0.5, 1), (1, 1), (1, 0.5), (1, 0), (1, -0.5), (1, -1), (0.5, -1)]
    rows = []; allok = True
    for sp in (4, 2, 8):
        for di, (ux, uy) in enumerate(DIRV):
            vx, vy = ux * sp, uy * sp
            agent(1000.0, 300.0, vx, vy, 100000)
            Hh = 1; w32(mu, CL + 4, 0); ok = True
            fr = []; T = 0; prev = (1000, 300)
            for f in range(16):
                Hh += 1; ticked = Hh % 2 == 0
                T += 1 if ticked else 0
                wrap(Hh, ticked)
                _, _, ix, iy = pos()
                nx, ny = int(1000.0 + T * vx), int(300.0 + T * vy)       # настоящая позиция тика (int)
                dxs, dys = nx - ix, ny - iy
                ok = ok and dxs % 2 == 0 and dys % 2 == 0
                # монотонность вдоль движения
                if vx: ok = ok and (ix - prev[0]) * (1 if vx > 0 else -1) >= 0
                if vy: ok = ok and (iy - prev[1]) * (1 if vy > 0 else -1) >= 0
                prev = (ix, iy); fr.append((dxs, dys))
            first = fr[2]                                              # кадр после тика (чётный полутакт)
            second = fr[3]                                             # кадр после возврата
            allok = allok and ok and second == (0, 0)
            rows.append((sp, di, (vx, vy), first, second, ok))
    line('16 направлений x скорости 2,4,8: смещение показанной позиции от настоящей чётное по обеим осям и монотонно во всех кадрах (проверено %d случаев)' % len(rows), allok)
    out.append('ТАБЛИЦА направлений (скорость 4): напр | v | смещение 1-го полутакта (настоящая-показанная) | 2-й полутакт | паритет')
    for sp, di, v, f1, f2, ok in rows:
        if sp == 4: out.append('  dir %2d | v=(%+g,%+g) | d=%s | %s | чётное=%s' % (di, v[0], v[1], f1, f2, ok))
    out.append('ТАБЛИЦА направлений (скорости 2 и 8, только узлы 4 осевых/диагональных и 2:1): ')
    for sp, di, v, f1, f2, ok in rows:
        if sp in (2, 8) and di in (0, 2, 12, 13, 15): out.append('  v=%d dir %2d | v=(%+g,%+g) | d=%s | %s | чётное=%s' % (sp, di, v[0], v[1], f1, f2, ok))
    # ---- 8. регистры вызывающего сохраняются
    ok = True
    wrap(0, True); 
    from unicorn.x86_const import UC_X86_REG_EBX as RB, UC_X86_REG_ESI as RS, UC_X86_REG_EDI as RD
    ok = (mu.reg_read(RB), mu.reg_read(RS), mu.reg_read(RD)) == (0x11111111, 0x22222222, 0x33333333)
    line('обёртка сохраняет ebx/esi/edi', ok)

    # ---- 9. скорость в пикс./с за 1 с (40 тиков, 80 кадров), speed 4/3/8, и число различных позиций камеры
    res = []
    for sp in (4.0, 3.0, 8.0):
        agent(100.0, 200.0, sp, 0.0, 1000)
        seen = set()
        for k in range(40):
            wrap(0, True); seen.add(pos()[0]); wrap(1, False); seen.add(pos()[0])
        res.append((sp, f32(mu, AG + 0xC) - 100.0, len(seen)))
    line('скорость за 1 с: ' + '; '.join('speed %g -> %.0f пикс./с (оригинал %.0f), %d различных позиций за 80 кадров' % (sp, d, 40 * sp, n) for sp, d, n in res),
         all(abs(d - 40 * sp) < 1e-3 and n == 80 for sp, d, n in res))

    # ---- 10. каждое место применения шага помечает агента (NPC, не герой) и запоминает его v; исходная инструкция выполняется
    from unicorn.x86_const import UC_X86_REG_EBX as RB, UC_X86_REG_ESI as RS, UC_X86_REG_EDI as RD
    REG = {'ebx': RB, 'esi': RS, 'edi': RD}
    bad = []
    for va, kind, reg in SITES:
        agent(100.0, 200.0, -4.0, 4.0, 3, idv=0x0777)
        mu.reg_write(REG[reg], AG); mu.reg_write(UC_X86_REG_ESP, STK)
        mu.ctl_flush_tb()   # блок после места мог быть оттранслирован раньше без точки остановки
        try: mu.emu_start(va, va + 6)
        except Exception as e: bad.append("%X:%s" % (va, e)); continue
        rec = TAB + 0x0777 * STRIDE
        if not (r32(mu, rec) == 1 and (f32(mu, rec + 4), f32(mu, rec + 8)) == (-4.0, 4.0) and r32(mu, D + 16) == 1
                and struct.unpack('<H', bytes(mu.mem_read(base + OFF_LIST, 2)))[0] == 0x0777): bad.append('%X' % va)
    agent(100.0, 200.0, -4.0, 4.0, 3, idv=0x0777); w32(mu, AG, 0x609A5C); mu.reg_write(RS, AG); mu.reg_write(UC_X86_REG_ESP, STK); mu.ctl_flush_tb(); mu.emu_start(0x427D90, 0x427D96)
    other = (r32(mu, TAB + 0x0777 * STRIDE), r32(mu, D + 16))
    line('объект другого класса (vtable 0x609A5C, без визуализатора в +0x2E4) на месте шага не помечается (состояние, длина списка): %s' % (other,), other == (0, 0))
    line('места применения шага (%d, в т.ч. путь 0x427D30 и 0x441FEE): NPC помечен, v записан, в списке; сбои: %s' % (len(SITES), bad or 'нет'), not bad)

    # ---- 14. пейсер при стоящем герое (выход без ожидания): остаток не теряется -> ровно 40 тиков/с при 60..179 к/с и нерегулярных кадрах
    from unicorn.x86_const import UC_X86_REG_EAX
    def pacer_run(frame_ms, seconds=20.0, jitter=0.0, seed=1):
        mu = mk(); CLK = H + 0x2000; PLY = H + 0x1000; MG = H + 0x4000; AGA = H + 0x5000; ARRA = H + 0x6000; GS = H + 0x6800; X = H + 0x6900
        mu.mem_write(STUB, b'\xc3'); w32(mu, 0x6064A0, STUB)
        w32(mu, 0x658C04, PLY); w32(mu, 0x658C44, CLK); w32(mu, 0x658C14, H + 0x3000); w32(mu, 0x658D50, MG)
        w32(mu, 0x6E0100, GS); w32(mu, GS + 8, 0)                                     # [0x6E0100+8] == 0: герой не в "ходьбе по клику"
        w32(mu, PLY + 0x4b4, X); w32(mu, X + 0x10, 7); w32(mu, PLY + 0x4c0, 7)      # лидер = активный герой id 7
        w32(mu, MG + 0xc, ARRA); w32(mu, ARRA + 7 * 4, AGA); wf(mu, AGA + 0x22c, 0.0); wf(mu, AGA + 0x230, 0.0)   # стоит
        mu.mem_write(CLK, struct.pack('<9I', 0, 0, 25, 0, 1000, 0, 0, 0, 5000))
        t = {'v': 5000.0}; rr = random.Random(seed)
        def hk(uc, addr, size, ud):
            if addr == STUB: uc.reg_write(UC_X86_REG_EAX, int(t['v']))
        mu.hook_add(UC_HOOK_CODE, hk, begin=STUB, end=STUB)
        while t['v'] - 5000.0 < seconds * 1000.0:
            mu.reg_write(UC_X86_REG_ESP, STK); mu.mem_write(STK, struct.pack('<I', STUB + 0x100)); mu.mem_write(STUB + 0x100, b'\xf4')
            mu.reg_write(UC_X86_REG_ECX, CLK); mu.emu_start(labels['pacer'], STUB + 0x100)
            t['v'] += frame_ms * (1.0 + rr.uniform(-jitter, jitter))
        return r32(mu, CLK + 4) * 1000.0 / (t['v'] - 5000.0)
    res = [(fms, j, pacer_run(fms, jitter=j)) for fms, j in ((1000.0 / 60, 0), (1000.0 / 144, 0), (1000.0 / 179, 0), (1000.0 / 60, 0.5), (1000.0 / 100, 0.9))]
    line('пейсер, герой стоит (без ожидания): тиков/с при ' + ', '.join('%.0f к/с%s -> %.2f' % (1000.0 / f, ' (разброс %d%%)' % (j * 100) if j else '', v) for f, j, v in res) + ' (оригинал при 60 к/с: 30)',
         all(abs(v - 40.0) <= 0.5 for _, _, v in res))

    # ---- 15. огонь/объекты (реальный 0x582CC0): 1 кадр за 2 мировых тика при smooth 1, 1 за тик при smooth 0; мерцание - бросок rand через тик
    def fire_run(ticks, smooth=1, twinkle=False, calls=1, frame0=0, ninst=1, iflags=0, rand_val=0, reset_twinkle=True):
        mu = mk(); mu.mem_map(0, 0x10000)                                              # нулевые указатели таблиц (Collide-слот вне диапазона) пишут в страницу 0
        M = H + 0x100; INST = H + 0x10000; ARCH = H + 0x600; P44 = H + 0x700; Q = H + 0x720; CT = H + 0x740; CLIPS = H + 0x780; CD = H + 0x800
        FR = H + 0x900; P40 = H + 0xA00; T40 = H + 0xA20; Z = H + 0xA40; CFGA = H + 0xB00; CLK = H + 0xC00
        w32(mu, CFG, CFGA); w32(mu, CFGA + 0x74, smooth); w32(mu, CLOCKP, CLK)
        w32(mu, M + 0x28, ninst); w32(mu, M + 0x20, INST); w32(mu, M + 0x1c, ARCH); w32(mu, M + 0x44, P44); w32(mu, M + 0x40, P40)
        w32(mu, P44, Q); w32(mu, Q + 4, CT); w32(mu, CT, CLIPS); w32(mu, CT + 4, 1); w32(mu, CT + 8, 0x20); w32(mu, CLIPS + 0xc, CD); w32(mu, CD + 4, 10); w32(mu, CD + 0xc, FR)
        w32(mu, P40, T40); w32(mu, P40 + 4, Z)
        for i in range(ninst):
            I = INST + i * 0x6C
            w32(mu, I + 0x48, 0); mu.mem_write(I + 0x44, struct.pack('<h', frame0)); w32(mu, I + 0x28, -1); w32(mu, I + 0x30, iflags)
        w32(mu, ARCH + 0x1c, 0x200 if twinkle else 0)
        RAND = 0x5E5DEC; nr = {'n': 0}
        mu.mem_write(RAND, b'\xb8' + struct.pack('<I', rand_val) + b'\xc3')          # rand() = 0 (шанс 4 %% всегда выпадает), счёт вызовов
        def hk(uc, addr, size, ud): nr['n'] += 1
        mu.hook_add(UC_HOOK_CODE, hk, begin=RAND, end=RAND)
        changes = 0; prev = frame0; seen = []; all_seen = [[] for _ in range(ninst)]
        for k in ticks:
            w32(mu, CLK, k)
            for _ in range(calls):
                mu.reg_write(UC_X86_REG_ESP, STK); mu.mem_write(STK, struct.pack('<I', STUB + 0x100)); mu.mem_write(STUB + 0x100, b'\xf4')
                mu.reg_write(UC_X86_REG_ECX, M); mu.reg_write(UC_X86_REG_EBX, 0x11111111); mu.reg_write(UC_X86_REG_ESI, 0x22222222); mu.reg_write(UC_X86_REG_EDI, 0x33333333)
                mu.emu_start(0x582CC0, STUB + 0x100)
                f = struct.unpack('<h', bytes(mu.mem_read(INST + 0x44, 2)))[0]
                if f != prev: changes += 1
                prev = f; seen.append(f)
                for i in range(ninst): all_seen[i].append(struct.unpack('<h', bytes(mu.mem_read(INST + i * 0x6C + 0x44, 2)))[0])
                if twinkle and reset_twinkle: mu.mem_write(INST + 0x44, struct.pack('<h', 0)); prev = 0
        regs = (mu.reg_read(RB), mu.reg_read(RS), mu.reg_read(RD))
        if ninst > 1: return all_seen
        return changes, nr['n'], seen, regs
    c40, _, seen, regs = fire_run(range(1000, 1040))
    c0, _, _, _ = fire_run(range(1000, 1040), smooth=0)
    step1 = lambda sq: all((b - a) % 10 in (0, 1) for a, b in zip(sq, sq[1:]))   # кадр стоит или +1 по кругу (v3.7: фаза экземпляра, скорость та же)
    line('огонь (клип 10 кадров, реальный 0x582CC0): за 40 тиков (1 с) смен кадра %d при smooth 1 (ожидалось %d: первый шаг ставит фазу экземпляра, дальше +1), %d при smooth 0 (40, без изменений); кадры %s; ebx/esi/edi сохранены %s'
         % (c40, 40 // FIRE_DIV, c0, seen[:12], regs == (0x11111111, 0x22222222, 0x33333333)), c40 in (40 // FIRE_DIV, 40 // FIRE_DIV - 1) and c0 == 40 and step1(seen[FIRE_DIV - 1:]) and regs == (0x11111111, 0x22222222, 0x33333333))
    cj, _, _, _ = fire_run([1000 + 2 * i for i in range(20)] + [1040 + 3 * i for i in range(20)])
    c2, _, _, _ = fire_run(range(1000, 1040), calls=2)
    c2s0, _, _, _ = fire_run(range(1000, 1040), calls=2, smooth=0)
    # v3.7: у зацикленного клипа кадр = (шаг + фаза) % n, второй вызов в том же тике кадр не двигает (раньше двигал: 2 смены за шаг); smooth 0 - оригинал (80)
    line('огонь: номер тика прыгает на 2-3 (пейсер добавил несколько тиков, мир сделал один проход): %d смен за 40 проходов (ожидалось %d); два вызова в одном тике: %d (v3.7: %d, кадр от шага, не от числа вызовов), smooth 0: %d (80, оригинал)'
         % (cj, 40 // FIRE_DIV, c2, 40 // FIRE_DIV, c2s0), cj == 40 // FIRE_DIV and c2 == 40 // FIRE_DIV and c2s0 == 80)
    _, nt, _, _ = fire_run(range(1000, 1040), twinkle=True); _, nt0, _, _ = fire_run(range(1000, 1040), smooth=0, twinkle=True)
    line('мерцание предмета (арх. флаг 0x200, кадр 0): бросков rand за 40 тиков %d (ожидалось 20 = шанс 4%% за 20-Гц шаг, как в smooth 0), при smooth 0: %d (40)' % (nt, nt0), nt == 40 // FIRE_DIV and nt0 == 40)

    # ---- 16. v3.7 случайная фаза зацикленных клипов: N одинаковых свечей (один клип, 10 кадров), реальный 0x582CC0
    N = 12; T = range(1000, 1000 + 4 * 40)
    sq = fire_run(T, ninst=N)
    starts = [x[FIRE_DIV - 1] for x in sq]   # кадр после первого шага анимации (фаза экземпляра)
    ok_rng = all(0 <= f < 10 for x in sq for f in x)
    ok_spd = all(sum(1 for a, b in zip(x[FIRE_DIV - 1:], x[FIRE_DIV:]) if a != b) == len(T) // FIRE_DIV - 1 and step1(x[FIRE_DIV - 1:]) for x in sq)
    ok_adj = all(a != b for a, b in zip(starts, starts[1:]))
    line('фаза свечей (smooth 1, %d экземпляров одного зацикленного клипа): стартовые кадры %s - разных %d (ожидалось >= %d), соседние различны %s, все в 0..9 %s, после первого шага у каждого %d смен за %d тиков, шаг +1 по кругу %s'
         % (N, starts, len(set(starts)), 6, ok_adj, ok_rng, len(T) // FIRE_DIV - 1, len(T) - FIRE_DIV, ok_spd), len(set(starts)) >= 6 and ok_adj and ok_rng and ok_spd)
    sq0 = fire_run(range(1000, 1040), ninst=N, smooth=0)
    line('фаза свечей при smooth 0: все %d экземпляров идут синхронно с 0 (оригинал: %s) - %s' % (N, sq0[0][:6], all(x == [(k + 1) % 10 for k in range(40)] for x in sq0)),
         all(x == [(k + 1) % 10 for k in range(40)] for x in sq0))
    sq1 = fire_run(T, ninst=N, iflags=0x20)
    sq4 = fire_run(T, ninst=N, iflags=0x400)
    exp1 = [min(9, (k + 1) // FIRE_DIV) for k in range(len(T))]
    line('однократные клипы (флаги 0x20 / 0x400, двери/сундуки): все %d экземпляров с 0 до конца синхронно %s / %s' % (N, sq1[0][:12], sq4[0][:12]),
         all(x == exp1 for x in sq1) and all(x == exp1 for x in sq4))
    sqt = fire_run(T, ninst=N, twinkle=True, rand_val=0, reset_twinkle=False)
    sqt_rest = fire_run(T, ninst=N, twinkle=True, rand_val=50, reset_twinkle=False)
    expt = [((k + 1) // FIRE_DIV) % 10 for k in range(len(T))]
    line('мерцание (арх. 0x200): покой - все %d в кадре 0 (rand без вспышки) %s; вспышка - все с 0 и +1 до возврата в 0 синхронно, фаза не применяется %s' % (N, all(set(x) == {0} for x in sqt_rest), sqt[0][:12]),
         all(set(x) == {0} for x in sqt_rest) and all(x == expt for x in sqt))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('--test', action='store_true'); ap.add_argument('--hero-only', action='store_true', help='откатывать только активного героя (NPC на позициях тика, 40 Гц); по умолчанию - все агенты')
    ap.add_argument('--frame', action='store_true', help='раскладка frame: вход = exe с секциями frame, код/данные в .interp (патч tick80 программы)')
    ap.add_argument('--fire-div', type=int, default=4, help='огонь/объекты: 1 кадр за N тиков (2 = 20 к/с, 4 = 10 к/с; степень двойки)')
    ap.add_argument('--no-rec', action='store_true', help='диагностика: не сдвигать запись спрайта (Collide, DAT_006592dc)')
    a = ap.parse_args(); FIRE_DIV = a.fire_div; assert FIRE_DIV in (1, 2, 4, 8)
    new, labels, base = apply(open(a.src, 'rb').read(), a.hero_only, not a.no_rec, a.frame)
    open(a.dst, 'wb').write(new); print(a.dst, len(new), {k: hex(v) for k, v in labels.items() if k in ('pacer', 'rollback', 'restore', 'wrap')})
    if a.test:
        for l in selftest(a.dst): print(l)

