# -*- coding: utf-8 -*-
"""fps_patch.py - такт логики Divine Divinity (div.exe 1.0.0.62) 40 -> N (по умолчанию 60).
Работает на оригинале и на любом нашем exe (inv*, glow*), идемпотентно, с проверкой исходных байт.
Три места (см. docs/recon/2026-11-07_fps.md):
  A  0x48D2F2  ключ `smooth #`: 83 E0 14 83 C0 14 -> B8 <fps> 00 00 00 90   (cfg+0x40 = fps)
  B  0x48D90A  умолчание cfg+0x40 (imm у `mov [esi+0x40],imm`)             (cfg+0x40 = fps)
  C  0x505BA4  загрузка сейва (блок Gameclock) затирает период часов clock+8 значением из сейва
               (25 мс при 40) -> после загрузки пишем clock+8 = 1000//fps. Функция 0x505B90
               перекроена внутри себя (28 байт вместе с выравниванием до 0x505BC0).
Использование: python fps_patch.py in.exe out.exe [--fps 60] [--test]
"""
import sys, struct, argparse
import pefile

A_VA, B_VA, C_VA = 0x48D2F2, 0x48D90A, 0x505BA4
A_ORIG = bytes.fromhex('83e01483c014')
B_ORIG = 0x28
C_ORIG = bytes.fromhex('897e1cff15a0646000897e14897e1c5f89462089460c5ec3cccccccc')  # 28 байт

def c_new(fps):
    period = 1000 // fps
    return (bytes.fromhex('ff15a0646000')      # call [timeGetTime]
            + bytes.fromhex('897e14')          # mov [esi+14],edi
            + bytes.fromhex('897e1c')          # mov [esi+1c],edi
            + b'\x5f'                          # pop edi
            + bytes.fromhex('894620')          # mov [esi+20],eax
            + bytes.fromhex('89460c')          # mov [esi+0c],eax
            + bytes.fromhex('c74608') + struct.pack('<I', period)  # mov [esi+8],period
            + b'\x5e\xc3')                     # pop esi; ret
def a_new(fps): return b'\xb8' + struct.pack('<I', fps) + b'\x90'

def patch(data, fps=60):
    pe = pefile.PE(data=bytes(data))
    o = lambda va: pe.get_offset_from_rva(va - 0x400000)
    b = bytearray(data); log = []
    # A
    oa = o(A_VA); cur = bytes(b[oa:oa+6])
    if cur == A_ORIG or (cur[0] == 0xB8 and cur[5] == 0x90 and cur[2:5] == b'\0\0\0'):
        b[oa:oa+6] = a_new(fps); log.append('A ok')
    else: raise SystemExit('A: неожиданные байты %s' % cur.hex())
    # B
    ob = o(B_VA)
    if bytes(b[ob-3:ob]) != bytes.fromhex('c74640') or b[ob+1:ob+4] != b'\0\0\0' or b[ob] not in (B_ORIG, 0x3c, fps) and not (10 <= b[ob] <= 200):
        raise SystemExit('B: неожиданные байты %s' % bytes(b[ob-3:ob+4]).hex())
    b[ob] = fps; log.append('B ok')
    # C
    oc = o(C_VA); cur = bytes(b[oc:oc+28])
    if cur == C_ORIG or (cur[:19] == c_new(fps)[:19] and cur[19:22] == bytes.fromhex('c74608') and cur[26:] == b'\x5e\xc3'):
        b[oc:oc+28] = c_new(fps); log.append('C ok')
    else: raise SystemExit('C: неожиданные байты %s' % cur.hex())
    return bytes(b), log

def selftest(path, fps):
    """Unicorn: 1) загрузка сейва с периодом 25 -> clock+8 == 1000//fps; 2) пейсер даёт ~fps тиков/с при mock timeGetTime."""
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EIP, UC_X86_REG_ESP, UC_X86_REG_ECX, UC_X86_REG_EAX, UC_X86_REG_EDI, UC_X86_REG_ESI
    pe = pefile.PE(path); img = pe.get_memory_mapped_image()
    def mk():
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (len(img) + 0xFFF) & ~0xFFF); mu.mem_write(0x400000, img)
        mu.mem_map(0x6000000, 0x10000)  # стек/данные
        mu.mem_map(0x7000000, 0x1000); mu.mem_write(0x7000000, b'\xc3')  # timeGetTime stub
        mu.mem_write(0x6064a0, struct.pack('<I', 0x7000000))
        return mu
    out = []
    # --- 1: загрузка сейва
    mu = mk(); S = 0x6001000; mu.mem_write(S, b'\0' * 0x24)
    saved = struct.pack('<9I', 0, 777, 25, 55, 1000, 9, 0, 66, 88)  # period=25 как в старом сейве
    state = {'t': 5000}
    def hook(uc, addr, size, ud):
        if addr == 0x7000000:
            state['t'] += 1; uc.reg_write(UC_X86_REG_EAX, state['t'])
        if addr == 0x4F4C70:  # fread-обёртка (ret 8): заполняем структуру из «сейва»
            esp = uc.reg_read(UC_X86_REG_ESP); dst = struct.unpack('<I', uc.mem_read(esp+4, 4))[0]
            uc.mem_write(dst, saved)
            ret = struct.unpack('<I', uc.mem_read(esp, 4))[0]
            uc.reg_write(UC_X86_REG_ESP, esp + 12); uc.reg_write(UC_X86_REG_EIP, ret)
    mu.hook_add(UC_HOOK_CODE, hook)
    mu.reg_write(UC_X86_REG_ESP, 0x6008000); mu.mem_write(0x6008000, struct.pack('<I', 0x6005000))
    mu.mem_write(0x6005000, b'\xf4')
    mu.reg_write(UC_X86_REG_ECX, S); mu.reg_write(UC_X86_REG_ESI, 0x1234); mu.reg_write(UC_X86_REG_EDI, 0xABCD)
    mu.mem_write(S + 0x1c, struct.pack('<I', 42))
    mu.emu_start(0x505B90, 0x6005000)
    r = struct.unpack('<9I', mu.mem_read(S, 0x24))
    ok1 = (r[2] == 1000 // fps and r[5] == 42 and r[1] == 777 and mu.reg_read(UC_X86_REG_EDI) == 0xABCD and mu.reg_read(UC_X86_REG_ESI) == 0x1234)
    out.append('сейв: period после загрузки=%d (ожидалось %d), edi/esi сохранены=%s -> %s' % (r[2], 1000//fps, ok1, 'OK' if ok1 else 'FAIL'))
    # --- 2: пейсер 0x505A20, герой «движется» (ветка ожидания через [0x6e0100]+8 != 0)
    mu = mk(); C = 0x6001000; D = 0x6002000
    mu.mem_write(C, struct.pack('<9I', 0, 0, 1000 // fps, 0, 1000, 0, 0, 0, 5000))  # +8 период, +0x20 метка
    mu.mem_write(0x6e0100, struct.pack('<I', D)); mu.mem_write(D + 8, struct.pack('<I', 1))
    mu.mem_write(0x658c14, struct.pack('<I', 1))
    state = {'t': 5000, 'calls': 0}
    def hook2(uc, addr, size, ud):
        if addr == 0x7000000:
            state['calls'] += 1
            if state['calls'] % 50 == 0: state['t'] += 1   # 1 мс на 50 опросов
            uc.reg_write(UC_X86_REG_EAX, state['t'])
    mu.hook_add(UC_HOOK_CODE, hook2)
    ticks = 0
    for _ in range(200):
        esp = 0x6008000; mu.mem_write(esp, struct.pack('<I', 0x6005000)); mu.mem_write(0x6005000, b'\xf4')
        mu.reg_write(UC_X86_REG_ESP, esp); mu.reg_write(UC_X86_REG_ECX, C)
        mu.emu_start(0x505A20, 0x6005000)
        # игра «рисует кадр» 1 мс
        state['t'] += 1
    ticks = struct.unpack('<I', mu.mem_read(C + 4, 4))[0]; ms = state['t'] - 5000
    out.append('пейсер: %d тиков за %d мс = %.1f тик/с (цель %d, период %d мс)' % (ticks, ms, ticks * 1000.0 / ms, fps, 1000 // fps))
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('--fps', type=int, default=60); ap.add_argument('--test', action='store_true')
    a = ap.parse_args()
    new, log = patch(open(a.src, 'rb').read(), a.fps)
    open(a.dst, 'wb').write(new); print(a.dst, len(new), log)
    if a.test:
        for l in selftest(a.dst, a.fps): print(l)
