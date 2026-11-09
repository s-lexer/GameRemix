# -*- coding: utf-8 -*-
r"""Experimental 20-syllable CP949 -> UTF-16 / GetGlyphOutlineW patch, Divine Divinity 1.0.0.62.

No game execution. Only the exact Steam EN reference exe is accepted. Without
--out, all work is in memory; --out creates a NEW exe strictly inside
steam_en_test/_GameRemix_Korean_Work (never overwrites). Requires pefile,
keystone-engine, capstone, unicorn. Run with: py -3 -B hangul_patch.py --check
or: py -3 -B hangul_patch.py --check --out C:\ARM\WORK\MODDING\GAMES\DivineDivinity\steam_en_test\_GameRemix_Korean_Work\div_hangul20_proto.exe

This is NOT a full localization. A 20-entry CP949 lookup maps each two-byte
syllable to a private 8-bit token (0x80..0x93); existing 256-entry glyph cache
and GDI widths still operate on tokens. The glyph-creation hook resolves the
token to Unicode before both GetGlyphOutlineW calls. All other CP949 pairs,
other render/measure paths, dialogs, control handling and token collisions are
unsupported. A running-game proof needs a locked lab VM.
"""
from __future__ import annotations

import argparse
import ctypes as ct
import hashlib
import struct
import sys
from pathlib import Path

import pefile
from keystone import Ks, KS_ARCH_X86, KS_MODE_32

ROOT = Path(r"C:\ARM\WORK\MODDING\GAMES\DivineDivinity\steam_en_test")
SOURCE = ROOT / "div.exe"
WORK = ROOT / "_GameRemix_Korean_Work"
ORIGINAL_SHA256 = "cd9f7a07c7a605c21052b3517346c7a63083063fb491276a3e4c9836c9b42a67"
ORIGINAL_SIZE = 2461696
IMAGE = 0x400000
SYLLABLES = tuple("가각간강나다라마바사아자차카타파하한글힘")
assert len(SYLLABLES) == len(set(SYLLABLES)) == 20
FIRST_TOKEN = 0x80
CODE_VA = (0x494F82, 0x4950B7, 0x494013)
ORIGINAL_HOOKS = {
    0x494F82: bytes.fromhex("8a013c207438"),
    0x4950B7: bytes.fromhex("0fb6068b8c242c080000"),
    0x494013: bytes.fromhex("0fbeea8d54245c"),
    0x494353: bytes.fromhex("6a026a006a006a006a00"),  # quality, clip, output, charset, italic
}
FONT_CHARSET_VA = 0x49435A
IMPORT_A_OFFSET = 0x2469B9  # The final byte in "GetGlyphOutlineA", not the IAT.
OFF_DECODER, OFF_WIDTH, OFF_DRAW, OFF_GLYPH, OFF_FONT, OFF_TABLE = 0, 0x100, 0x200, 0x300, 0x400, 0x600
SECTION_NAME = b".khgl"
SECTION_SIZE = 0x1000
SECTION_CHARACTERISTICS = 0x60000020  # executable, readable, non-writable


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def align(n: int, step: int) -> int:
    return (n + step - 1) // step * step


def reference(data: bytes) -> pefile.PE:
    if len(data) != ORIGINAL_SIZE or sha(data) != ORIGINAL_SHA256:
        raise ValueError("Unknown div.exe: size/hash mismatch; no patch applied")
    p = pefile.PE(data=data)
    if p.OPTIONAL_HEADER.ImageBase != IMAGE or p.FILE_HEADER.Machine != 0x14C:
        raise ValueError("Expected a fixed-base PE32 x86 div.exe")
    if p.OPTIONAL_HEADER.DllCharacteristics & 0x40:
        raise ValueError("ASLR/DYNAMIC_BASE not supported by absolute VA references")
    if p.get_overlay_data_start_offset() is not None:
        raise ValueError("Unknown executable overlay; refusing section append")
    for va, expect in ORIGINAL_HOOKS.items():
        off = p.get_offset_from_rva(va - IMAGE)
        if data[off:off + len(expect)] != expect:
            raise ValueError(f"Hook mismatch VA {va:#x}")
    charoff = p.get_offset_from_rva(FONT_CHARSET_VA - IMAGE)
    if data[charoff] != 0:
        raise ValueError("Unexpected CreateFontA charset immediate")
    if data[IMPORT_A_OFFSET - 15:IMPORT_A_OFFSET + 1] != b"GetGlyphOutlineA":
        raise ValueError("GetGlyphOutlineA import name not at expected offset")
    if len(p.sections) != 4 or p.sections[-1].Name.rstrip(b"\0") != b".rsrc":
        raise ValueError("Unexpected PE section layout")
    return p


def entries() -> list[tuple[str, bytes, int]]:
    rows = [(c, c.encode("cp949"), ord(c)) for c in SYLLABLES]
    for c, src, uni in rows:
        assert len(src) == 2 and 0x81 <= src[0] <= 0xFE
        assert src.decode("cp949") == c and 0xAC00 <= uni <= 0xD7A3
    assert len({s for _, s, _ in rows}) == 20
    return rows


def asm(source: str, va: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, va)
    return bytes(encoded)


def reljmp(from_va: int, to_va: int, count: int) -> bytes:
    assert count >= 5
    return b"\xe9" + struct.pack("<i", to_va - (from_va + 5)) + b"\x90" * (count - 5)


def machine_code(base: int) -> tuple[bytes, dict[str, int]]:
    addr = {
        "decoder": base + OFF_DECODER,
        "width": base + OFF_WIDTH,
        "draw": base + OFF_DRAW,
        "glyph": base + OFF_GLYPH,
        "font": base + OFF_FONT,
        "table": base + OFF_TABLE,
    }
    a = addr
    decoder = asm(f"""
    movzx eax, byte ptr [ecx]
    mov edx, 1
    cmp al, 0x81
    jb done
    cmp al, 0xfe
    ja done
    push ebx
    movzx ebx, word ptr [ecx]
    xor eax, eax
    loop_start:
    cmp bx, word ptr [{a['table']}+eax*4]
    je matched
    inc eax
    cmp eax, 20
    jb loop_start
    movzx eax, byte ptr [ecx]
    pop ebx
    ret
    matched:
    add eax, {FIRST_TOKEN}
    mov edx, 2
    pop ebx
    ret
    done:
    ret
    """, a["decoder"])
    # In 494F50 the caller increments [esi] once at 494FB3; add one only for a
    # matched CP949 pair. Original space branch from 494F86 is reproduced.
    width = asm(f"""
    call {a['decoder']}
    cmp edx, 2
    jne single
    inc dword ptr [esi]
    single:
    cmp al, 0x20
    je 0x494fc0
    jmp 0x494f88
    """, a["width"])
    # In 494FF0 the original loop increments ESI once at 4950DE.
    draw = asm(f"""
    mov ecx, esi
    call {a['decoder']}
    cmp edx, 2
    jne single
    inc esi
    single:
    movzx eax, al
    mov ecx, dword ptr [esp+0x82c]
    jmp 0x4950c1
    """, a["draw"])
    # Preserve the old LEA after 494013, and resume just before PUSH EDX.
    # EBP is used by BOTH GetGlyphOutline calls (metrics then bitmap).
    glyph = asm(f"""
    cmp dl, {FIRST_TOKEN}
    jb other
    cmp dl, {FIRST_TOKEN+19}
    ja other
    movzx ebp, dl
    sub ebp, {FIRST_TOKEN}
    movzx ebp, word ptr [{a['table']}+ebp*4+2]
    jmp finish
    other:
    movsx ebp, dl
    finish:
    lea edx, [esp+0x5c]
    jmp 0x49401a
    """, a["glyph"])
    # Original charset is PUSH imm8, where 0x81 would sign-extend to -127.
    # Move five full pushes into a trampoline and use positive PUSH imm32 129.
    font = asm("""
    push 2
    push 0
    push 0
    push 129
    push 0
    jmp 0x49435d
    """, a["font"])
    assert bytes.fromhex("6881000000") in font, "charset must be PUSH imm32 +129"

    sec = bytearray(SECTION_SIZE)
    for off, limit, fragment in [
        (OFF_DECODER, OFF_WIDTH, decoder),
        (OFF_WIDTH, OFF_DRAW, width),
        (OFF_DRAW, OFF_GLYPH, draw),
        (OFF_GLYPH, OFF_FONT, glyph),
        (OFF_FONT, OFF_TABLE, font),
    ]:
        if off + len(fragment) > limit:
            raise ValueError("Machine code overlaps next routine")
        sec[off:off + len(fragment)] = fragment
    for i, (_, raw, uni) in enumerate(entries()):
        struct.pack_into("<HH", sec, OFF_TABLE + 4*i,
                         struct.unpack("<H", raw)[0], uni)
    return bytes(sec), addr


def build(data: bytes) -> tuple[bytes, dict[str, int]]:
    pe = reference(data)
    sa, fa = pe.OPTIONAL_HEADER.SectionAlignment, pe.OPTIONAL_HEADER.FileAlignment
    if sa != 0x1000 or fa != 0x200:
        raise ValueError("Unexpected PE alignment")
    sec_rva = align(max(s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData)
                        for s in pe.sections), sa)
    raw = align(len(data), fa)
    if raw != len(data):
        raise ValueError("Expected no raw alignment gap")
    header = pe.sections[-1].get_file_offset() + 0x28
    if header + 0x28 > pe.sections[0].PointerToRawData or any(data[header:header+0x28]):
        raise ValueError("No clean space for a PE section header")
    base = IMAGE + sec_rva
    sec, addr = machine_code(base)
    result = bytearray(data)
    result[header:header+0x28] = struct.pack(
        "<8sIIIIIIHHI", SECTION_NAME, SECTION_SIZE, sec_rva,
        SECTION_SIZE, raw, 0, 0, 0, 0, SECTION_CHARACTERISTICS)
    struct.pack_into("<H", result, pe.FILE_HEADER.get_field_absolute_offset("NumberOfSections"),
                     pe.FILE_HEADER.NumberOfSections + 1)
    struct.pack_into("<I", result, pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfImage"),
                     sec_rva + SECTION_SIZE)
    result.extend(sec)
    for va, name in [(0x494F82, "width"), (0x4950B7, "draw"), (0x494013, "glyph"), (0x494353, "font")]:
        off = pe.get_offset_from_rva(va - IMAGE)
        result[off:off + len(ORIGINAL_HOOKS[va])] = reljmp(
            va, addr[name], len(ORIGINAL_HOOKS[va]))
    result[IMPORT_A_OFFSET] = ord("W")
    # Recompute PE checksum to keep static validation deterministic.
    testpe = pefile.PE(data=bytes(result))
    checkoff = testpe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    struct.pack_into("<I", result, checkoff, testpe.generate_checksum())
    return bytes(result), addr


def inspect_patched(result: bytes, addr: dict[str, int]) -> None:
    p = pefile.PE(data=result)
    new = next((s for s in p.sections if s.Name.rstrip(b"\0") == SECTION_NAME), None)
    assert new is not None and p.FILE_HEADER.NumberOfSections == 5
    assert new.Characteristics == SECTION_CHARACTERISTICS
    assert p.OPTIONAL_HEADER.SizeOfImage >= new.VirtualAddress + SECTION_SIZE
    assert result[IMPORT_A_OFFSET - 15:IMPORT_A_OFFSET + 1] == b"GetGlyphOutlineW"
    assert bytes.fromhex("6881000000") in result[new.PointerToRawData+OFF_FONT:new.PointerToRawData+OFF_TABLE]
    for va, name in [(0x494F82, "width"), (0x4950B7, "draw"), (0x494013, "glyph"), (0x494353, "font")]:
        off = p.get_offset_from_rva(va - IMAGE)
        b = result[off:off + len(ORIGINAL_HOOKS[va])]
        assert b == reljmp(va, addr[name], len(ORIGINAL_HOOKS[va]))
    for i, (_, cp, uni) in enumerate(entries()):
        at = new.PointerToRawData + OFF_TABLE + 4*i
        assert result[at:at+4] == struct.pack("<HH", int.from_bytes(cp, "little"), uni)


def cpu_selftest(sec: bytes, addr: dict[str, int]) -> tuple[int, int, int]:
    """Execute real injected x86 code without starting/loading the game process."""
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP,
                                   UC_X86_REG_ECX, UC_X86_REG_EDX,
                                   UC_X86_REG_ESI, UC_X86_REG_ESP)
    token_tests = width_tests = glyph_tests = 0
    base = addr["decoder"]
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, 0x400000)
    mu.mem_map(0x10000000, 0x20000)
    mu.mem_write(base, sec)
    buf, ref, esp = 0x10001000, 0x10002000, 0x1001e000
    def w32(a, v):
        mu.mem_write(a, struct.pack("<I", v))
    def r32(a):
        return struct.unpack("<I", bytes(mu.mem_read(a, 4)))[0]
    def run(start, stop):
        mu.emu_start(start, stop, count=500)
    for i, (ch, raw, uni) in enumerate(entries()):
        token = FIRST_TOKEN + i
        mu.mem_write(buf, raw+b"\0")
        # Decoder consumes only supported CP949 pairs.
        mu.reg_write(UC_X86_REG_ECX, buf)
        mu.reg_write(UC_X86_REG_ESP, esp)
        w32(esp, 0x400800)
        run(addr["decoder"], 0x400800)
        assert mu.reg_read(UC_X86_REG_EAX) == token
        assert mu.reg_read(UC_X86_REG_EDX) == 2
        token_tests += 1
        # 494F82 -> 494F88: one extra advance; normal loop advances another.
        w32(ref, buf)
        mu.reg_write(UC_X86_REG_ECX, buf)
        mu.reg_write(UC_X86_REG_ESI, ref)
        mu.reg_write(UC_X86_REG_ESP, esp)
        run(addr["width"], 0x494F88)
        assert r32(ref) == buf+1 and (mu.reg_read(UC_X86_REG_EAX) & 0xff) == token
        # 4950B7 -> 4950C1: ESI advances one before the original INC ESI.
        mu.reg_write(UC_X86_REG_ESI, buf)
        mu.reg_write(UC_X86_REG_ESP, esp)
        w32(esp+0x82c, 0x12345678)
        run(addr["draw"], 0x4950C1)
        assert mu.reg_read(UC_X86_REG_ESI) == buf+1
        assert mu.reg_read(UC_X86_REG_EAX) == token
        assert mu.reg_read(UC_X86_REG_ECX) == 0x12345678
        width_tests += 1
        mu.reg_write(UC_X86_REG_EDX, token)
        mu.reg_write(UC_X86_REG_ESP, esp)
        run(addr["glyph"], 0x49401a)
        assert mu.reg_read(UC_X86_REG_EBP) == uni, ch
        assert mu.reg_read(UC_X86_REG_EDX) == esp+0x5c
        glyph_tests += 1
    # ASCII must stay one byte and not consume the next byte.
    mu.mem_write(buf, b"A\0")
    mu.reg_write(UC_X86_REG_ECX, buf)
    mu.reg_write(UC_X86_REG_ESP, esp)
    w32(esp, 0x400800)
    run(addr["decoder"], 0x400800)
    assert mu.reg_read(UC_X86_REG_EAX) == ord("A")
    assert mu.reg_read(UC_X86_REG_EDX) == 1
    w32(ref, buf)
    mu.reg_write(UC_X86_REG_ECX, buf)
    mu.reg_write(UC_X86_REG_ESI, ref)
    mu.reg_write(UC_X86_REG_ESP, esp)
    run(addr["width"], 0x494F88)
    assert r32(ref) == buf
    mu.reg_write(UC_X86_REG_EDX, ord("A"))
    mu.reg_write(UC_X86_REG_ESP, esp)
    run(addr["glyph"], 0x49401a)
    assert mu.reg_read(UC_X86_REG_EBP) == ord("A")
    # Verify the five original CreateFontA arguments with signed-extension-safe
    # 32-bit HANGUL_CHARSET=129; stack top is italic, charset, output, clip, quality.
    mu.reg_write(UC_X86_REG_ESP, esp)
    run(addr["font"], 0x49435d)
    assert mu.reg_read(UC_X86_REG_ESP) == esp-20
    assert [r32(esp-20+i*4) for i in range(5)] == [0, 129, 0, 0, 2]
    return token_tests, width_tests, glyph_tests


def gdi_width_selftest() -> list[int]:
    """Real Windows GDI glyph metrics, independent of game execution."""
    if sys.platform != "win32":
        raise RuntimeError("GDI width test requires Windows")
    from ctypes import wintypes as wt
    class FIXED(ct.Structure):
        _fields_ = [("fract", ct.c_ushort), ("value", ct.c_short)]
    class POINT(ct.Structure):
        _fields_ = [("x", wt.LONG), ("y", wt.LONG)]
    class GLYPHMETRICS(ct.Structure):
        _fields_ = [("gmBlackBoxX", wt.DWORD), ("gmBlackBoxY", wt.DWORD),
                    ("gmptGlyphOrigin", POINT), ("gmCellIncX", ct.c_short),
                    ("gmCellIncY", ct.c_short)]
    class MAT2(ct.Structure):
        _fields_ = [(f"eM{i}{j}", FIXED) for i in (1, 2) for j in (1, 2)]
    g = ct.WinDLL("gdi32", use_last_error=True)
    g.CreateCompatibleDC.argtypes = [ct.c_void_p]
    g.CreateCompatibleDC.restype = ct.c_void_p
    g.CreateFontW.argtypes = [ct.c_int]*13 + [ct.c_wchar_p]
    g.CreateFontW.restype = ct.c_void_p
    g.SelectObject.argtypes = [ct.c_void_p, ct.c_void_p]
    g.SelectObject.restype = ct.c_void_p
    g.GetGlyphOutlineW.argtypes = [ct.c_void_p, ct.c_uint, ct.c_uint,
                                   ct.POINTER(GLYPHMETRICS), ct.c_uint,
                                   ct.c_void_p, ct.POINTER(MAT2)]
    g.GetGlyphOutlineW.restype = ct.c_uint
    g.GetGlyphIndicesW.argtypes = [ct.c_void_p, ct.c_wchar_p, ct.c_int,
                                   ct.POINTER(ct.c_ushort), ct.c_uint]
    g.GetGlyphIndicesW.restype = ct.c_uint
    g.DeleteObject.argtypes = [ct.c_void_p]
    g.DeleteDC.argtypes = [ct.c_void_p]
    dc = g.CreateCompatibleDC(None)
    if not dc:
        raise RuntimeError("CreateCompatibleDC failed")
    font = g.CreateFontW(24, 0, 0, 0, 400, 0, 0, 0, 129, 0, 0, 0, 0, "Malgun Gothic")
    if not font:
        g.DeleteDC(dc)
        raise RuntimeError("CreateFontW failed")
    old = g.SelectObject(dc, font)
    matrix = MAT2(FIXED(0, 1), FIXED(0, 0), FIXED(0, 0), FIXED(0, 1))
    widths = []
    try:
        for char in SYLLABLES:
            glyph_index = ct.c_ushort(0xffff)
            found = g.GetGlyphIndicesW(dc, char, 1, ct.byref(glyph_index), 1)
            if found != 1 or glyph_index.value == 0xffff:
                raise AssertionError(f"missing real Hangul glyph index U+{ord(char):04X}")
            gm = GLYPHMETRICS()
            value = g.GetGlyphOutlineW(dc, ord(char), 6, ct.byref(gm),
                                       0, None, ct.byref(matrix))
            if value == 0xffffffff or gm.gmCellIncX <= 0 or gm.gmBlackBoxX == 0:
                raise AssertionError(f"GDI glyph missing/invalid: {char!r}, status={value:#x}")
            widths.append(gm.gmCellIncX)
    finally:
        g.SelectObject(dc, old)
        g.DeleteObject(font)
        g.DeleteDC(dc)
    return widths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="run byte, PE, x86 emulator, CP949, and WinGDI width tests")
    parser.add_argument("--out", type=Path,
                        help="create new patched exe ONLY below steam_en_test/_GameRemix_Korean_Work")
    args = parser.parse_args()
    if not args.check and args.out is None:
        parser.error("choose --check and/or --out; default does not write")
    src = SOURCE.read_bytes()
    built, addr = build(src)
    inspect_patched(built, addr)
    section = built[pefile.PE(data=built).sections[-1].PointerToRawData:]
    print("PASS source reference:", SOURCE, len(src), sha(src))
    print("PASS PE section:", hex(addr["decoder"]), SECTION_NAME.decode(),
          "new image", len(built), sha(built))
    print("PASS hooks:", ", ".join(f"{va:#x}->{addr[lab]:#x}"
                                   for va, lab in ((0x494F82, "width"),
                                                   (0x4950B7, "draw"),
                                                   (0x494013, "glyph"),
                                                   (0x494353, "font"))))
    print("PASS import GetGlyphOutlineW; CreateFontA HANGUL_CHARSET=129 via push imm32")
    if args.check:
        t, w, g = cpu_selftest(section, addr)
        print(f"PASS x86 Unicorn decoder={t}/20, width-token={w}/20, glyph-UTF16={g}/20, font-stack=PASS, ASCII=PASS")
        widths = gdi_width_selftest()
        print("PASS Windows GDI GetGlyphOutlineW widths (px):",
              " ".join(f"U+{ord(c):04X}:{v}" for c, v in zip(SYLLABLES, widths)))
        print("PASS width glyphs=20/20; sum_width_px=", sum(widths))
    if args.out:
        dest = args.out.resolve(strict=False)
        if (dest.suffix.lower() != ".exe" or not dest.is_relative_to(WORK.resolve())
                or dest == SOURCE.resolve()):
            raise ValueError("--out must be a new .exe inside the Korean work copy")
        if not WORK.is_dir():
            raise ValueError("Korean work directory does not exist")
        # Exclusive creation: original div.exe and other concurrent work stay untouched.
        with dest.open("xb") as f:
            f.write(built)
        assert dest.read_bytes() == built
        assert sha(SOURCE.read_bytes()) == ORIGINAL_SHA256
        print("PASS created new exe:", dest, len(built), sha(built))
        print("PASS source div.exe unchanged")
    print("LIMITATION no game launch/VM lock; other UI text routes and full CP949 unsupported")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
