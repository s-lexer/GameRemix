# -*- coding: utf-8 -*-
"""interp_patch.py - интерполяция кадров для Divine Divinity (div.exe 1.0.0.62, x86): больше FPS БЕЗ ускорения игры.
Логика остаётся на такте 40 (cfg+0x40), между тактами рисуются дополнительные кадры, где камера и агенты сдвинуты
на долю такта (рисуем между ПРЕДЫДУЩИМ и ТЕКУЩИМ состоянием тика: задержка один такт, 25 мс; без экстраполяции).
Исследование и обоснование: docs/recon/2026-11-07_interp.md.

Четыре хука + новая секция .interp (RWX; код, данные, таблица 65536 x 20 байт для агентов):
  P  0x505A20  пейсер часов: заменён своим (БЕЗ busy-wait; тики по накопленному времени ref += n*период; кадры идут
               по vsync/maxfps обёртки; необязательный свой предел кадров --maxfps; timeBeginPeriod(1) один раз).
  C  0x4AB534  `call 0x4A4bc0` (камера игрока за героем) -> наша обёртка: настоящая камера запоминается, в Player+0x4A0/4A4
               пишется интерполированная (true + (prev-cur)*(1-alpha)).
  A  0x44A7CD  узел агента (CAgentVisualizer::Draw 0x44A180): x,y узла сдвигаются на (prev-cur)*(1-alpha) по id агента.
  E  0x4AB74B  `jmp 0x4A9FB0` в конце кадра -> восстановить настоящую камеру в Player+0x4A0/4A4, затем прежний переход.
Кадр 0x4AB4A0 не имеет ранних выходов; игровая логика (тик 0x505BC0) идёт ДО хука C и в начале следующего кадра видит
настоящую камеру. Не интерполируются: снаряды/эффекты (рисуются в мировых координатах такта, стоят на месте относительно
плавной камеры), подписи над головами, UI.

Использование: python interp_patch.py in.exe out.exe [--maxfps N] [--jump PX] [--test]
  in.exe: оригинал или любой наш exe (inv*, glow*, fps*: проверяются только байты хуков). Идемпотентно.
  --maxfps N: свой предел кадров (0 = выкл, по умолчанию: полагаться на vsync/maxfps cnc-ddraw)
  --jump PX : порог «телепорта» на тик для камеры/агента (по умолчанию 40 пикс.), больше - без интерполяции
  --only PCAEI: диагностика/бисекция: ставить только перечисленные хуки (P пейсер, C камера, A агенты, E конец кадра, I ввод); без --only все
  --quant N : сдвиг камеры и агентов кратен N пикс. (1/2/4/8/16), по умолчанию 2 (финал: при 1 мир «светлеет» при ходьбе, см. docs/recon/2026-11-07_interp.md)
  --agents-only: вариант F: камера и пол ступенями такта (сдвига камеры нет), плавно ходят только агенты кроме героя
  --test    : эмуляция Unicorn на реальных байтах итогового exe
"""
import sys, struct, hashlib
import pefile
from keystone import Ks, KS_ARCH_X86, KS_MODE_32

IMG = 0x400000
HOOK_P, HOOK_C, HOOK_A, HOOK_E, HOOK_I = 0x505A20, 0x4AB534, 0x44A7CD, 0x4AB74B, 0x4AB55C
HOOK_W, HOOK_F = 0x4A9E5C, 0x4AB561   # W: call 4a3fd0 (мир: пол, объекты, агенты) в 4a9df0; F: call 4a9df0 (весь блок мира+эффектов) в 4ab4a0
T_CAM, T_END, T_INP, T_WORLD, T_FRAME = 0x4A4BC0, 0x4A9FB0, 0x4A70E0, 0x4A3FD0, 0x4A9DF0
HOOKS = (HOOK_P, HOOK_C, HOOK_A, HOOK_E, HOOK_I, HOOK_W, HOOK_F)
DEFAULT_HOOKS = (HOOK_P, HOOK_C, HOOK_A, HOOK_E, HOOK_I, HOOK_W)   # F - только для бисекции (--only), вместе с W не ставится
P_OLD = bytes.fromhex('568bf1c705')
A_OLD = bytes.fromhex('8b4c24108b44241c')
OFF_DATA, OFF_TAB = 0x800, 0x1000
ENTRIES, ESIZE = 65536, 20
SEC_VSIZE = (OFF_TAB + ENTRIES * ESIZE + 0xFFF) & ~0xFFF
SEC_RAWSIZE = 0x1000
SEC_CHAR = 0xE0000060

def rel(src, dst): return struct.pack('<i', dst - (src + 5))

def offmap(pe):
    return lambda va: pe.get_offset_from_rva(va - IMG)

def build(base, maxfps=0, jump=40, quant=2, agents_only=False):
    D = base + OFF_DATA
    S = dict(STAMP=D, ALPHA=D + 4, ACTIVE=D + 8, TRUE_X=D + 0xC, TRUE_Y=D + 0x10, LAST_X=D + 0x14, LAST_Y=D + 0x18,
             DCAM_X=D + 0x1C, DCAM_Y=D + 0x20, LASTVALID=D + 0x24, LASTFRAME=D + 0x28, CAPMS=D + 0x2C,
             OVR_X=D + 0x30, OVR_Y=D + 0x34, TIMERINIT=D + 0x38, NOWP=D + 0x3C, T_INP=T_INP, STR_WINMM=D + 0x40, STR_TBP=D + 0x50,
             TABLE=base + OFF_TAB, TH=jump, TH2=2 * jump, T_CAM=T_CAM, T_END=T_END, T_WORLD=T_WORLD, T_FRAME=T_FRAME)
    k = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4}[quant]
    qa = (' add eax, %d\n sar eax, %d\n shl eax, %d\n' % (quant // 2, k, k)) if quant > 1 else ''
    herocalc = (''' mov eax, dword ptr [0x658c04]
 mov eax, dword ptr [eax+0x4c0]
 cmp eax, -1
 je hnone
 mov ecx, dword ptr [0x658d50]
 mov ecx, dword ptr [ecx+0xc]
 mov ecx, dword ptr [ecx+eax*4]
 xor eax, eax
 cmp ecx, edx
 sete al
 jmp hstore
hnone:
 xor eax, eax
hstore:
 mov dword ptr [%d], eax
''' % (D + 0x70)) if agents_only else ''
    S.update(HEROCALC=herocalc, QA=qa, QC=(' xor eax, eax\n' if agents_only else qa), HF=D + 0x70,
             HEROX=(' cmp dword ptr [%d], 0\n je hxok\n xor eax, eax\nhxok:\n' % (D + 0x70)) if agents_only else '',
             HEROY=(' cmp dword ptr [%d], 0\n je hyok\n xor eax, eax\nhyok:\n' % (D + 0x70)) if agents_only else '')
    src = """
pacer:
 push esi
 push ebx
 mov esi, ecx
 mov dword ptr [0x74478c], 0
 mov dword ptr [{NOWP}], 0
 cmp dword ptr [esi+0x18], 0
 jne pdone
 cmp dword ptr [0x658c14], 0
 je pdone
 cmp dword ptr [{TIMERINIT}], 0
 jne pagain
 mov dword ptr [{TIMERINIT}], 1
 push {STR_WINMM}
 call dword ptr [0x6060ac]
 test eax, eax
 jz pagain
 push {STR_TBP}
 push eax
 call dword ptr [0x6060a8]
 test eax, eax
 jz pagain
 push 1
 call eax
pagain:
 call dword ptr [0x6064a0]
 mov ebx, eax
 mov ecx, dword ptr [{CAPMS}]
 test ecx, ecx
 jz pnocap
 mov eax, ebx
 sub eax, dword ptr [{LASTFRAME}]
 cmp eax, ecx
 jae pnocap
 mov eax, ebx
 sub eax, dword ptr [esi+0x20]
 cmp eax, dword ptr [esi+8]
 jae pnocap
 pause
 jmp pagain
pnocap:
 mov dword ptr [{LASTFRAME}], ebx
 mov dword ptr [{NOWP}], ebx
 mov eax, ebx
 sub eax, dword ptr [esi+0x20]
 mov ecx, dword ptr [esi+8]
 cmp eax, ecx
 jb pdone
 xor edx, edx
 div ecx
 add dword ptr [esi+4], eax
 cmp eax, 8
 ja pnow
 imul eax, ecx
 add dword ptr [esi+0x20], eax
 jmp pdone
pnow:
 mov dword ptr [esi+0x20], ebx
pdone:
 pop ebx
 pop esi
 ret

camhook:
 call {T_CAM}
 push ebx
 push edi
 mov ebx, dword ptr [0x658c04]
 mov eax, dword ptr [ebx+0x4a0]
 mov edx, dword ptr [ebx+0x4a4]
 mov dword ptr [{TRUE_X}], eax
 mov dword ptr [{TRUE_Y}], edx
 mov ecx, dword ptr [0x658c44]
 mov edi, dword ptr [ecx+4]
 cmp edi, dword ptr [{STAMP}]
 je ctsame
 mov ebx, edi
 sub ebx, dword ptr [{STAMP}]
 mov dword ptr [{STAMP}], edi
 cmp dword ptr [{LASTVALID}], 0
 je cfirst
 cmp ebx, 3
 ja cfirst
 mov ebx, dword ptr [{LAST_X}]
 sub ebx, eax
 mov edi, dword ptr [{LAST_Y}]
 sub edi, edx
 mov dword ptr [{LAST_X}], eax
 mov dword ptr [{LAST_Y}], edx
 lea ecx, [ebx+{TH}]
 cmp ecx, {TH2}
 ja czero
 lea ecx, [edi+{TH}]
 cmp ecx, {TH2}
 ja czero
 mov dword ptr [{DCAM_X}], ebx
 mov dword ptr [{DCAM_Y}], edi
 jmp ctsame
cfirst:
 mov dword ptr [{LAST_X}], eax
 mov dword ptr [{LAST_Y}], edx
 mov dword ptr [{LASTVALID}], 1
czero:
 xor ecx, ecx
 mov dword ptr [{DCAM_X}], ecx
 mov dword ptr [{DCAM_Y}], ecx
ctsame:
 mov eax, dword ptr [{NOWP}]
 test eax, eax
 jnz chavenow
 call dword ptr [0x6064a0]
chavenow:
 mov ecx, dword ptr [0x658c44]
 sub eax, dword ptr [ecx+0x20]
 js calpha0
 cmp eax, dword ptr [ecx+8]
 jae calpha256
 shl eax, 8
 xor edx, edx
 div dword ptr [ecx+8]
 jmp calphaset
calpha0:
 xor eax, eax
 jmp calphaset
calpha256:
 mov eax, 256
calphaset:
 mov dword ptr [{ALPHA}], eax
 mov ecx, 256
 sub ecx, eax
 mov ebx, dword ptr [0x658c04]
 mov eax, dword ptr [{DCAM_X}]
 imul eax, ecx
 add eax, 128
 sar eax, 8
{QC} add eax, dword ptr [{TRUE_X}]
 mov dword ptr [ebx+0x4a0], eax
 mov dword ptr [{OVR_X}], eax
 mov eax, dword ptr [{DCAM_Y}]
 imul eax, ecx
 add eax, 128
 sar eax, 8
{QC} add eax, dword ptr [{TRUE_Y}]
 mov dword ptr [ebx+0x4a4], eax
 mov dword ptr [{OVR_Y}], eax
 mov dword ptr [{ACTIVE}], 1
 pop edi
 pop ebx
 ret

agenthook:
 cmp dword ptr [{ACTIVE}], 0
 je atail
 push ebx
 mov edx, dword ptr [esi+0x23c]
{HEROCALC} movzx eax, word ptr [edx+0x214]
 lea eax, [eax+eax*4]
 mov ebx, {TABLE}
 lea ebx, [ebx+eax*4]
 mov ecx, dword ptr [edx+4]
 add ecx, dword ptr [edx+0x1c]
 mov eax, dword ptr [edx+8]
 add eax, dword ptr [edx+0x20]
 sub eax, dword ptr [edx+0x14]
 mov edx, eax
 mov eax, dword ptr [{STAMP}]
 inc eax
 cmp dword ptr [ebx], eax
 je aapply
 push edi
 mov edi, dword ptr [ebx]
 mov dword ptr [ebx], eax
 test edi, edi
 jz areset
 sub eax, edi
 cmp eax, 3
 ja areset
 mov eax, dword ptr [ebx+4]
 sub eax, ecx
 mov dword ptr [ebx+4], ecx
 mov edi, dword ptr [ebx+8]
 sub edi, edx
 mov dword ptr [ebx+8], edx
 lea ecx, [eax+{TH}]
 cmp ecx, {TH2}
 ja azero
 lea edx, [edi+{TH}]
 cmp edx, {TH2}
 ja azero
 mov dword ptr [ebx+0xc], eax
 mov dword ptr [ebx+0x10], edi
 jmp apop
areset:
 mov dword ptr [ebx+4], ecx
 mov dword ptr [ebx+8], edx
azero:
 xor eax, eax
 mov dword ptr [ebx+0xc], eax
 mov dword ptr [ebx+0x10], eax
apop:
 pop edi
aapply:
 mov ecx, 256
 sub ecx, dword ptr [{ALPHA}]
 mov eax, dword ptr [ebx+0xc]
 imul eax, ecx
 add eax, 128
 sar eax, 8
{QA}{HEROX} add dword ptr [esp+0x24], eax
 mov eax, dword ptr [ebx+0x10]
 imul eax, ecx
 add eax, 128
 sar eax, 8
{QA}{HEROY} add dword ptr [esp+0x20], eax
 pop ebx
atail:
 mov ecx, dword ptr [esp+0x14]
 mov eax, dword ptr [esp+0x20]
 ret

inputhook:
 cmp dword ptr [{ACTIVE}], 0
 je ihdirect
 push ebx
 mov ebx, ecx
 mov eax, dword ptr [{TRUE_X}]
 mov dword ptr [ebx+0x4a0], eax
 mov eax, dword ptr [{TRUE_Y}]
 mov dword ptr [ebx+0x4a4], eax
 call {T_INP}
 mov eax, dword ptr [{TRUE_X}]
 cmp dword ptr [ebx+0x4a0], eax
 jne ihabort
 mov eax, dword ptr [{TRUE_Y}]
 cmp dword ptr [ebx+0x4a4], eax
 jne ihabort
 pop ebx
 ret
ihabort:
 mov dword ptr [{ACTIVE}], 0
 pop ebx
 ret
ihdirect:
 jmp {T_INP}

worldwrap:
 cmp dword ptr [{ACTIVE}], 0
 je wwdirect
 mov eax, dword ptr [0x658c04]
 mov edx, dword ptr [{OVR_X}]
 mov dword ptr [eax+0x4a0], edx
 mov edx, dword ptr [{OVR_Y}]
 mov dword ptr [eax+0x4a4], edx
 call {T_WORLD}
 mov eax, dword ptr [0x658c04]
 mov edx, dword ptr [{TRUE_X}]
 mov dword ptr [eax+0x4a0], edx
 mov edx, dword ptr [{TRUE_Y}]
 mov dword ptr [eax+0x4a4], edx
 ret
wwdirect:
 jmp {T_WORLD}

framewrap:
 cmp dword ptr [{ACTIVE}], 0
 je fwdirect
 mov eax, dword ptr [0x658c04]
 mov edx, dword ptr [{OVR_X}]
 mov dword ptr [eax+0x4a0], edx
 mov edx, dword ptr [{OVR_Y}]
 mov dword ptr [eax+0x4a4], edx
 call {T_FRAME}
 mov eax, dword ptr [0x658c04]
 mov edx, dword ptr [{TRUE_X}]
 mov dword ptr [eax+0x4a0], edx
 mov edx, dword ptr [{TRUE_Y}]
 mov dword ptr [eax+0x4a4], edx
 ret
fwdirect:
 jmp {T_FRAME}

endhook:
 cmp dword ptr [{ACTIVE}], 0
 je edone
 push eax
 push ecx
 mov dword ptr [{ACTIVE}], 0
 mov eax, dword ptr [0x658c04]
 mov ecx, dword ptr [{OVR_X}]
 cmp dword ptr [eax+0x4a0], ecx
 jne enox
 mov ecx, dword ptr [{TRUE_X}]
 mov dword ptr [eax+0x4a0], ecx
enox:
 mov ecx, dword ptr [{OVR_Y}]
 cmp dword ptr [eax+0x4a4], ecx
 jne enoy
 mov ecx, dword ptr [{TRUE_Y}]
 mov dword ptr [eax+0x4a4], ecx
enoy:
 pop ecx
 pop eax
edone:
 jmp {T_END}
""".format(**S)
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    # метки: ассемблируем целиком, адреса меток берём отдельной сборкой (ks не отдаёт таблицу символов)
    code = bytes(ks.asm(src, base)[0])
    labels = {}
    for name in ('pacer', 'camhook', 'agenthook', 'inputhook', 'worldwrap', 'framewrap', 'endhook'):
        head = src[:src.index(name + ':')]
        labels[name] = base + len(bytes(ks.asm(head, base)[0])) if head.strip() else base
    assert len(code) < OFF_DATA, hex(len(code))
    data = bytearray(0x100)
    struct.pack_into('<I', data, 0x2C, (1000 // maxfps) if maxfps else 0)
    data[0x40:0x40 + 10] = b'winmm.dll\0'
    data[0x50:0x50 + 16] = b'timeBeginPeriod\0'
    return code, bytes(data), labels

def find_sec(pe):
    for s in pe.sections:
        if s.Name.rstrip(b'\0') == b'.interp': return s
    return None

def hooks_for(labels):
    return [(HOOK_P, b'\xe9' + rel(HOOK_P, labels['pacer'])),
            (HOOK_C, b'\xe8' + rel(HOOK_C, labels['camhook'])),
            (HOOK_A, b'\xe8' + rel(HOOK_A, labels['agenthook']) + b'\x90\x90\x90'),
            (HOOK_E, b'\xe9' + rel(HOOK_E, labels['endhook'])),
            (HOOK_I, b'\xe8' + rel(HOOK_I, labels['inputhook'])),
            (HOOK_W, b'\xe8' + rel(HOOK_W, labels['worldwrap'])),
            (HOOK_F, b'\xe8' + rel(HOOK_F, labels['framewrap']))]

def originals():
    return {HOOK_P: P_OLD, HOOK_C: b'\xe8' + rel(HOOK_C, T_CAM), HOOK_A: A_OLD, HOOK_E: b'\xe9' + rel(HOOK_E, T_END), HOOK_I: b'\xe8' + rel(HOOK_I, T_INP),
            HOOK_W: b'\xe8' + rel(HOOK_W, T_WORLD), HOOK_F: b'\xe8' + rel(HOOK_F, T_FRAME)}

def apply(d, maxfps=0, jump=40, only=None, quant=2, agents_only=False):
    pe = pefile.PE(data=bytes(d), fast_load=True); fh = pe.NT_HEADERS.FILE_HEADER; oh = pe.OPTIONAL_HEADER
    off = offmap(pe)
    s = find_sec(pe)
    if s is None:
        va = (max(x.VirtualAddress + max(x.Misc_VirtualSize, x.SizeOfRawData) for x in pe.sections) + 0xFFF) & ~0xFFF
        raw = (len(d) + 0x1FF) & ~0x1FF
        hdr = pe.sections[-1].get_file_offset() + 0x28
        if hdr + 0x28 > pe.sections[0].PointerToRawData or any(d[hdr:hdr + 0x28]): raise SystemExit('no room for section header')
        d[hdr:hdr + 0x28] = struct.pack('<8sIIIIIIHHI', b'.interp', SEC_VSIZE, va, SEC_RAWSIZE, raw, 0, 0, 0, 0, SEC_CHAR)
        struct.pack_into('<H', d, fh.get_file_offset() + 2, fh.NumberOfSections + 1)
        struct.pack_into('<I', d, oh.get_file_offset() + 56, va + SEC_VSIZE)
        d += b'\0' * (raw - len(d)); d += b'\0' * SEC_RAWSIZE
        base, fraw = IMG + va, raw
    else:
        base, fraw = IMG + s.VirtualAddress, s.PointerToRawData
    code, data, labels = build(base, maxfps, jump, quant, agents_only)
    orig = originals(); new = dict(hooks_for(labels))
    use = [va for va in HOOKS if (va in DEFAULT_HOOKS if only is None else va in only)]
    for va in HOOKS:
        cur = bytes(d[off(va):off(va) + len(new[va])])
        if cur != new[va] and cur[:len(orig[va])] != orig[va]:
            raise SystemExit('unexpected bytes at hook %x: %s' % (va, cur.hex()))
    d[fraw:fraw + len(code)] = code
    d[fraw + OFF_DATA:fraw + OFF_DATA + len(data)] = data
    for va in use:
        d[off(va):off(va) + len(new[va])] = new[va]
    return base, labels

# ---------------------------------------------------------------- Unicorn
def selftest(path, maxfps_cap=0):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import (UC_X86_REG_EIP, UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX,
                                   UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP)
    pe = pefile.PE(path); img = pe.get_memory_mapped_image()
    s = find_sec(pe); base = IMG + s.VirtualAddress
    _, _, labels = build(base)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    top = max((len(img) + 0xFFF) & ~0xFFF, base - IMG + SEC_VSIZE)
    mu.mem_map(IMG, top); mu.mem_write(IMG, img)
    H = 0x20000000; mu.mem_map(H, 0x100000); STK = H + 0xF0000
    r32 = lambda a: struct.unpack('<I', bytes(mu.mem_read(a, 4)))[0]
    s32 = lambda a: struct.unpack('<i', bytes(mu.mem_read(a, 4)))[0]
    w32 = lambda a, v: mu.mem_write(a, struct.pack('<I', v & 0xFFFFFFFF))
    st = {'t': 0.0, 'tick_per_call': 0.0, 'tbp': 0, 'ret_hit': 0}
    STUB = H + 0x80000     # заглушки импортов: по адресу ret
    TGT, LLA, GPA, TBP = STUB, STUB + 0x10, STUB + 0x20, STUB + 0x30
    mu.mem_write(TGT, b'\xc3'); mu.mem_write(LLA, b'\xc2\x04\x00'); mu.mem_write(GPA, b'\xc2\x08\x00'); mu.mem_write(TBP, b'\xc2\x04\x00')
    w32(0x6064A0, TGT); w32(0x6060AC, LLA); w32(0x6060A8, GPA)
    PLAYER, CLOCK, SERVER = H + 0x1000, H + 0x2000, H + 0x3000
    w32(0x658C04, PLAYER); w32(0x658C44, CLOCK); w32(0x658C14, SERVER)
    cam = {'target': 0}
    def hook(uc, addr, size, ud):
        if addr == TGT:
            st['t'] += st['tick_per_call']
            uc.reg_write(UC_X86_REG_EAX, int(st['t']) & 0xFFFFFFFF)
        elif addr == LLA: uc.reg_write(UC_X86_REG_EAX, 0x1234)
        elif addr == GPA: uc.reg_write(UC_X86_REG_EAX, TBP)
        elif addr == TBP: st['tbp'] += 1
        elif addr == T_CAM:       # модель FUN_004a4bc0 -> 4a3d20 (в т.ч. ранний выход при неизменной цели)
            tx, ty = cam['target']
            if not (r32(PLAYER + 0x510) == tx and r32(PLAYER + 0x514) == ty):
                w32(PLAYER + 0x510, tx); w32(PLAYER + 0x514, ty); w32(PLAYER + 0x4A0, tx); w32(PLAYER + 0x4A4, ty)
        elif addr == T_END: st['ret_hit'] += 1
        elif addr == T_INP: st['inp_cam'] = s32(PLAYER + 0x4A0)
        elif addr == T_FRAME: st['fcam'] = (s32(PLAYER + 0x4A0), s32(PLAYER + 0x4A4))
        elif addr == T_WORLD: st['wcam'] = (s32(PLAYER + 0x4A0), s32(PLAYER + 0x4A4))
    mu.hook_add(UC_HOOK_CODE, hook)
    # T_CAM и T_END: при выполнении по их адресу - просто ret (хук исполняется до инструкции; подменим EIP на ret-стаб)
    def stub_ret(uc, addr, size, ud):
        if addr in (T_CAM, T_END, T_INP, T_WORLD, T_FRAME):
            esp = uc.reg_read(UC_X86_REG_ESP); ret = r32(esp)
            uc.reg_write(UC_X86_REG_ESP, esp + 4); uc.reg_write(UC_X86_REG_EIP, ret)
    mu.hook_add(UC_HOOK_CODE, stub_ret, begin=T_CAM, end=T_CAM)
    mu.hook_add(UC_HOOK_CODE, stub_ret, begin=T_END, end=T_END)
    mu.hook_add(UC_HOOK_CODE, stub_ret, begin=T_INP, end=T_INP)
    mu.hook_add(UC_HOOK_CODE, stub_ret, begin=T_WORLD, end=T_WORLD)
    mu.hook_add(UC_HOOK_CODE, stub_ret, begin=T_FRAME, end=T_FRAME)
    DONE = H + 0x80100; mu.mem_write(DONE, b'\xf4')

    def call(fn, ecx=None, esi=None, stack_setup=None, nstack=0x100):
        sp = STK - nstack
        mu.mem_write(sp, b'\0' * nstack)
        if stack_setup: stack_setup(sp)
        sp -= 4; w32(sp, DONE)
        mu.reg_write(UC_X86_REG_ESP, sp)
        if ecx is not None: mu.reg_write(UC_X86_REG_ECX, ecx)
        if esi is not None: mu.reg_write(UC_X86_REG_ESI, esi)
        for rg in (UC_X86_REG_EBX, UC_X86_REG_EDI, UC_X86_REG_EBP):
            mu.reg_write(rg, 0x11111111)
        mu.emu_start(fn, DONE, count=100000)
        assert mu.reg_read(UC_X86_REG_EBX) == 0x11111111 and mu.reg_read(UC_X86_REG_EDI) == 0x11111111 and mu.reg_read(UC_X86_REG_EBP) == 0x11111111, 'regs clobbered'

    DT = base + OFF_DATA
    def world_enter():      # модель блока мира 4a3fd0 внутри обёртки: Player+0x4A0/4A4 = интерполированная только внутри
        call(labels['worldwrap'], ecx=PLAYER)
        assert (s32(PLAYER + 0x4A0), s32(PLAYER + 0x4A4)) == (s32(DT + 0xC), s32(DT + 0x10)), 'camera not true after world wrap'
        wx, wy = st['wcam']; w32(PLAYER + 0x4A0, wx); w32(PLAYER + 0x4A4, wy)
        return wx, wy
    def world_exit():
        w32(PLAYER + 0x4A0, s32(DT + 0xC)); w32(PLAYER + 0x4A4, s32(DT + 0x10))
    res = []
    # ---------- модель мира
    PERIOD = 25
    def new_world(fps_frame_ms, maxfps=0):
        st['t'] = 100000.0; st['tick_per_call'] = 0.0
        w32(CLOCK + 0, 0); w32(CLOCK + 4, 0); w32(CLOCK + 8, PERIOD); w32(CLOCK + 0x18, 0); w32(CLOCK + 0x20, int(st['t']))
        for a in range(PLAYER, PLAYER + 0x600, 4): w32(a, 0)
        d0 = base + OFF_DATA
        mu.mem_write(d0, b'\0' * 0x40)
        w32(d0 + 0x2C, (1000 // maxfps) if maxfps else 0)
        mu.mem_write(base + OFF_TAB, b'\0' * (ENTRIES * ESIZE))
    # агенты: id -> (world x, y); node экранный x = vx - cam
    VIS, AG, NODE = H + 0x4000, H + 0x5000, H + 0x6000
    extra = [0, 0]
    def draw_agent(aid, wx, wy):
        w32(AG + 0x214, aid); w32(VIS + 0x23C, AG)
        camx, camy = s32(PLAYER + 0x4A0), s32(PLAYER + 0x4A4)
        w32(AG + 4, wx); w32(AG + 8, wy); w32(AG + 0x1C, 0); w32(AG + 0x20, 0); w32(AG + 0x14, 0)
        sx, sy = wx + extra[0] - camx, wy + extra[1] - camy
        def ss(sp):
            w32(sp + 0x10 + 4, NODE); w32(sp + 0x18 + 4, sy); w32(sp + 0x1C + 4, sx)   # +4 учтён call'ом (return-адрес кладёт call())
        # call() кладёт return-адрес ПОСЛЕ stack_setup, смещения оригинала [esp+0x10] -> внутри функции [esp+0x14]; setup задаёт область под ним
        call(labels['agenthook'], esi=VIS, stack_setup=lambda sp: (w32(sp + 0x10, NODE), w32(sp + 0x18, sy), w32(sp + 0x1C, sx)))
        # результат: eax = x, ecx = node, y в [sp+0x18]
        sp = STK - 0x100
        nx = mu.reg_read(UC_X86_REG_EAX); nx = nx - (1 << 32) if nx >= 1 << 31 else nx
        ny = s32(sp + 0x18)
        assert mu.reg_read(UC_X86_REG_ECX) == NODE
        return nx + camx, ny + camy, nx, ny
    def run(frame_ms, seconds, maxfps=0, hero_v=3, npc_v=2, jump_at=None):
        new_world(frame_ms, maxfps)
        hero = [2000, 3000]; npc = [2500, 3100]; static = (2300, 3050); tp = [2600, 2900]
        cam_off = (400, 300)
        log = {'hero': [], 'static': [], 'npc': [], 'tp': [], 'camx': [], 'ticks': 0, 'frames': 0, 'dec': []}
        t = 100000.0; end = t + seconds * 1000
        d0 = base + OFF_DATA
        prev_true = None
        while t < end:
            st['t'] = t
            call(labels['pacer'], ecx=CLOCK)
            # логика: тики
            n = r32(CLOCK + 4) - r32(CLOCK + 0)
            for _ in range(n):
                hero[0] += hero_v; npc[0] += npc_v; npc[1] += 1
                if jump_at is not None and log['ticks'] == jump_at: tp[0] += 500
                log['ticks'] += 1
            w32(CLOCK + 0, r32(CLOCK + 4))
            cam['target'] = (hero[0] - cam_off[0], hero[1] - cam_off[1])
            call(labels['camhook'], ecx=PLAYER)
            ov = s32(PLAYER + 0x4A0)
            call(labels['inputhook'], ecx=PLAYER)
            assert st['inp_cam'] == cam['target'][0], 'input sees interpolated camera'
            assert s32(PLAYER + 0x4A0) == cam['target'][0], 'camera must stay true after input (D)'
            wc = world_enter(); assert wc[0] == ov, 'world sees other camera than override'
            res_h = draw_agent(1, hero[0], hero[1]); res_s = draw_agent(2, *static)
            res_n = draw_agent(3, npc[0], npc[1]); res_t = draw_agent(4, tp[0], tp[1])
            camx = s32(PLAYER + 0x4A0)
            log['camx'].append(camx); log['hero'].append(res_h[2]); log['static'].append(res_s[2])
            log['npc'].append(res_n[2]); log['tp'].append(res_t[2]); log['frames'] += 1
            world_exit()
            call(labels['endhook'])
            assert s32(PLAYER + 0x4A0) == cam['target'][0], 'camera not restored: %d vs %d' % (s32(PLAYER + 0x4A0), cam['target'][0])
            t += frame_ms
        return log
    # 1) 60 Гц, движение 3 пикс/тик
    lg = run(1000 / 60.0, 3.0)
    ticks_s = lg['ticks'] / 3.0
    res.append('1) 60 Гц: тиков/с %.2f (ожид. 40), кадров/с %.1f' % (ticks_s, lg['frames'] / 3.0))
    assert 39 <= ticks_s <= 41
    sk = lambda a: [a[i + 1] - a[i] for i in range(len(a) - 1)]
    camd = sk(lg['camx'][30:]); stat = sk(lg['static'][30:])
    res.append('   камера: приращения за кадр min %d max %d (ожид. 1..3 вокруг 2.0), средн. %.3f, первые: %s' % (min(camd), max(camd), sum(camd) / len(camd), camd[:24]))
    hs = set(lg['hero'][30:]); res.append('   герой на экране: x в {%s} (должен быть ПОСТОЯНЕН ±1)' % sorted(hs))
    assert max(hs) - min(hs) <= 1
    res.append('   статичный NPC (экран.x, смещение за кадр): множество приращений %s' % sorted(set(stat)))
    assert min(camd) >= 0 and max(camd) <= 3 and all(-3 <= v <= 0 for v in stat)
    nd = sk(lg['npc'][30:]); res.append('   NPC 2 пикс/тик относительно экрана: приращения %s' % sorted(set(nd)))
    # 2) 144 Гц
    lg = run(1000 / 144.0, 2.0)
    res.append('2) 144 Гц: тиков/с %.2f, кадров/с %.1f; приращения камеры %s' % (lg['ticks'] / 2.0, lg['frames'] / 2.0, sorted(set(sk(lg['camx'][50:])))))
    assert 39 <= lg['ticks'] / 2.0 <= 41 and max(set(lg['hero'][50:])) - min(set(lg['hero'][50:])) <= 1
    # 3) 30 Гц (медленный): ничего не ломается, тики догоняются
    lg = run(1000 / 30.0, 2.0)
    res.append('3) 30 Гц: тиков/с %.2f; кадров/с %.1f; герой x множество %s' % (lg['ticks'] / 2.0, lg['frames'] / 2.0, sorted(set(lg['hero'][20:]))))
    assert 39 <= lg['ticks'] / 2.0 <= 41
    # 4) телепорт
    lg = run(1000 / 60.0, 1.5, jump_at=20)
    d = sk(lg['tp']); res.append('4) телепорт (+500 за тик): макс. скачок экранного x %d (должен остаться ~ скачку, без «размазывания»)' % max(abs(v) for v in d))
    assert sum(1 for v in d if abs(v) > 100) == 1
    # 5) предел кадров
    st['tbp'] = 0
    new_world(0, 100); st['t'] = 100000.0; st['tick_per_call'] = 0.5
    w32(CLOCK + 0x20, int(st['t']))
    frames = 0; t0 = st['t']
    ts = []
    while st['t'] < t0 + 1000:
        call(labels['pacer'], ecx=CLOCK); ts.append(st['t']); frames += 1
        n = r32(CLOCK + 4) - r32(CLOCK + 0); w32(CLOCK + 0, r32(CLOCK + 4))
    res.append('5) maxfps=100 (тик моделью 0.5 мс на вызов): кадров за 1 с модельного времени: %d, тиков %d, timeBeginPeriod вызван %d раз' % (frames, r32(CLOCK + 4), st['tbp']))
    assert st['tbp'] == 1 and r32(CLOCK + 4) >= 38
    # 6) герой стоит, анимация удара меняет смещение спрайта (vis+0x21c) на +-8 каждый тик: узел должен идти ступенью такта, камера стоит
    new_world(0)
    st['t'] = 100000.0; w32(CLOCK + 0x20, 100000)
    hero = (2000, 3000); xs = []; cams = []; t = 100000.0
    for k in range(120):
        st['t'] = t
        call(labels['pacer'], ecx=CLOCK)
        n = r32(CLOCK + 4) - r32(CLOCK + 0); w32(CLOCK + 0, r32(CLOCK + 4))
        extra[0] = 8 if (r32(CLOCK + 4) % 2) else -8
        cam['target'] = (hero[0] - 400, hero[1] - 300)
        call(labels['camhook'], ecx=PLAYER); call(labels['inputhook'], ecx=PLAYER)
        world_enter(); r = draw_agent(1, hero[0], hero[1]); xs.append(r[2]); cams.append(s32(PLAYER + 0x4A0)); world_exit()
        call(labels['endhook']); t += 1000 / 60.0
    exp = sorted(set(xs[10:]))
    res.append('6) герой стоит, смещение спрайта +-8 по тикам: x узла на экране принимает только %s, камера %s' % (exp, sorted(set(cams))))
    assert set(exp) <= {392, 408} and len(set(cams)) == 1
    # 7) отбрасывание героя на 6 пикс. за тик (малое, < порога): герой и камера двигаются согласованно
    new_world(0); t = 100000.0; w32(CLOCK + 0x20, 100000); extra[0] = 0; hx = 2000; xs = []
    for k in range(120):
        st['t'] = t
        call(labels['pacer'], ecx=CLOCK)
        n = r32(CLOCK + 4) - r32(CLOCK + 0); w32(CLOCK + 0, r32(CLOCK + 4))
        hx += 6 * n if 20 <= k <= 40 else 0
        cam['target'] = (hx - 400, 2700)
        call(labels['camhook'], ecx=PLAYER); call(labels['inputhook'], ecx=PLAYER)
        world_enter(); xs.append(draw_agent(1, hx, 3000)[2]); world_exit(); call(labels['endhook']); t += 1000 / 60.0
    res.append('7) отбрасывание 6 пикс./тик: x героя на экране %s (ожид. постоянен)' % sorted(set(xs[10:])))
    assert max(xs[10:]) - min(xs[10:]) <= 1
    # 8) случайные интервалы кадров 3..25 мс, стоимость тика 4 мс внутри кадра (между пейсером и камерой): отклонение показанной камеры от идеала
    import random
    for name, steps in (('3 пикс./тик', (3,)), ('1,5 пикс./тик (1,2,1,2)', (1, 2))):
        rnd = random.Random(7)
        new_world(0); t = 100000.0; w32(CLOCK + 0x20, 100000); extra[0] = 0
        hx = 0; k = 0; errs = []; incs = []; prev_cam = None; hxs = []
        T0 = 100000
        tick_pos = {0: 0}
        while t < T0 + 6000:
            st['t'] = t
            call(labels['pacer'], ecx=CLOCK)
            ts = int(t)
            n = r32(CLOCK + 4) - r32(CLOCK + 0); w32(CLOCK + 0, r32(CLOCK + 4))
            for _ in range(n):
                k += 1; hx += steps[k % len(steps)]; tick_pos[k] = hx
            if n: st['t'] = t + 4          # тик «дорогой»: время кадра уходит вперёд до камеры
            cam['target'] = (hx + 2000, 2700)
            call(labels['camhook'], ecx=PLAYER)
            call(labels['inputhook'], ecx=PLAYER)
            world_enter()
            r = draw_agent(1, hx + 2400, 3000)
            camx = s32(PLAYER + 0x4A0) - 2000; world_exit()
            # идеал: линейная интерполяция по позициям тиков в момент ts-25 мс (идеальная сетка тиков 25 мс)
            u = (ts - T0) / 25.0 - 1.0
            if u >= 2 and int(u) + 1 in tick_pos:
                i = int(u); ideal = tick_pos[i] + (tick_pos[i + 1] - tick_pos[i]) * (u - i)
                errs.append(camx - ideal)
                if prev_cam is not None: incs.append(camx - prev_cam)
                assert abs(r[2] - 400) <= 1, 'hero moved on screen: %d' % r[2]
            prev_cam = camx
            call(labels['endhook']); t += rnd.uniform(3, 25)
        res.append('8) %s, интервалы кадров 3..25 мс: ошибка камеры от идеала min %.2f max %.2f (кадров %d), герой на экране постоянен' % (name, min(errs), max(errs), len(errs)))
        assert max(abs(e) for e in errs) <= 1.5
    # 9) обёртка блока 4a9df0 (вариант F/R2): внутри интерполированная камера (кратный 2 сдвиг), снаружи настоящая; ввод видит настоящую
    new_world(0); t = 100000.0; w32(CLOCK + 0x20, 100000); hx = 2000; seen = set(); okq = True
    for k in range(200):
        st['t'] = t
        call(labels['pacer'], ecx=CLOCK)
        n = r32(CLOCK + 4) - r32(CLOCK + 0); w32(CLOCK + 0, r32(CLOCK + 4)); hx += 3 * n
        cam['target'] = (hx - 400, 2700)
        call(labels['camhook'], ecx=PLAYER); call(labels['inputhook'], ecx=PLAYER)
        call(labels['framewrap'], ecx=PLAYER)
        assert s32(PLAYER + 0x4A0) == cam['target'][0], 'camera not true after frame wrap'
        if k > 20: seen.add(st['fcam'][0] - cam['target'][0]); okq = okq and ((st['fcam'][0] - cam['target'][0]) % 2 == 0)
        call(labels['endhook']); t += 1000 / 60.0
    res.append('9) обёртка блока 4a9df0: сдвиг камеры внутри %s (кратен 2: %s), снаружи настоящая' % (sorted(seen), okq))
    assert okq
    return res

def main(a):
    maxfps, jump, test, only, quant, agents_only = 0, 40, False, None, 2, False
    args = []
    i = 0
    while i < len(a):
        if a[i] == '--maxfps': maxfps = int(a[i + 1]); i += 2
        elif a[i] == '--jump': jump = int(a[i + 1]); i += 2
        elif a[i] == '--test': test = True; i += 1
        elif a[i] == '--quant': quant = int(a[i + 1]); i += 2
        elif a[i] == '--agents-only': agents_only = True; i += 1
        elif a[i] == '--only': only = {dict(P=HOOK_P, C=HOOK_C, A=HOOK_A, E=HOOK_E, I=HOOK_I, W=HOOK_W, F=HOOK_F)[c] for c in a[i + 1].upper()}; i += 2
        else: args.append(a[i]); i += 1
    if len(args) != 2: print(__doc__); return 2
    d = bytearray(open(args[0], 'rb').read())
    if d[:2] != b'MZ' or len(d) < 2461696: print('unexpected file (div.exe v1.0.0.62 expected)'); return 3
    base, labels = apply(d, maxfps, jump, only, quant, agents_only)
    open(args[1], 'wb').write(d)
    print('ok', args[1], '.interp base %x' % base, {k: hex(v) for k, v in labels.items()}, hashlib.sha256(d).hexdigest())
    if test:
        for line in selftest(args[1]): print(line)
        print('TEST OK')
    return 0

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
