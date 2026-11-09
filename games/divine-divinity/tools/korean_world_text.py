"""Lossless, read-only world-text cataloger for the Divine Divinity Steam EN TEST COPY.

Only writes four new JSONL catalogs below _GameRemix_Korean_Work, never game
resources. The binary gaps, string length fields and every original byte are
retained so a catalog can reconstruct its original binary resource exactly.

Usage:
    python korean_world_text.py verify <game_copy>
    python korean_world_text.py export <game_copy>
    python korean_world_text.py check  <game_copy>

verify: prove round-trip entirely in memory, without writing any file.
export: run both round-trip checks BEFORE creating catalog files; refuse overwrite.
check: load exported JSONL and reconstruct every source in memory, byte for byte.

The scanner identifies conservative length-prefixed text fields in mono/itemgen;
it does NOT claim to understand every field in those two record schemas.
"""

import argparse
import base64
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path


TEST_COPY = Path("C:/ARM/WORK/MODDING/GAMES/DivineDivinity/steam_en_test")
GLOBAL_REL = Path("dat/global.cmp")
MONO_REL = Path("localizations/english/mono.cmp")
ITEM_REL = Path("dat/English/itemgen.cmp")
WORK_DIR = "_GameRemix_Korean_Work"
OUTPUTS = {
    "books": "world_books_en_catalog.jsonl",
    "diary": "world_diary_en_catalog.jsonl",
    "mono": "world_mono_en_catalog.jsonl",
    "itemgen": "world_itemgen_en_catalog.jsonl",
}
# Known XOR key fragment from the existing cmpfile.py (which is never modified).
KEY23 = bytes((0xF3, 0xBF, 0xAA, 0xF3, 0xD2, 0xBE, 0x9D, 0xD2,
               0xFC, 0xF9, 0xB7, 0xE1, 0xFA, 0xB7, 0xEB, 0xFA,
               0xCF, 0xCD, 0xCC, 0xCB, 0x9C, 0x9C, 0xB9))
KNOWN_LONG_NAME = b"dat\\english\\diary_monsterlog.txt"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def b64(data):
    return base64.b64encode(data).decode("ascii")


def unb64(text):
    return base64.b64decode(text, validate=True)


def u32(buf, pos):
    if pos < 0 or pos + 4 > len(buf):
        raise ValueError("u32 out of bounds at " + str(pos))
    return struct.unpack_from("<I", buf, pos)[0]


def decode_display(raw):
    # The original EN data is an 8-bit Western encoding, NOT UTF-8.
    # Invalid Windows-1252 positions are shown as \xNN, never silently lost.
    return raw.decode("cp1252", errors="backslashreplace")


@dataclass
class CmpEntry:
    raw_name: bytes
    terminator: int
    offset: int
    z: int
    data: bytes
    name: str = ""


def read_global(data):
    count = u32(data, 0)
    if not 1 <= count <= 10000:
        raise ValueError("Unexpected global.cmp entry count")
    entries = []
    pos = 4
    for _ in range(count):
        length = u32(data, pos)
        pos += 4
        if length > 1024 or pos + length + 13 > len(data):
            raise ValueError("Corrupt global.cmp name/index")
        name = data[pos:pos + length]
        pos += length
        terminator = data[pos]
        pos += 1
        off, size, z = struct.unpack_from("<III", data, pos)
        pos += 12
        if off < pos or off + size > len(data) or terminator != 0:
            raise ValueError("Corrupt global.cmp data index")
        entries.append(CmpEntry(name, terminator, off, z, data[off:off + size]))
    # The source archive has no padding. Reject other layouts rather than lose it.
    cursor = pos
    for entry in entries:
        if entry.offset != cursor:
            raise ValueError("Unexpected global.cmp gap/overlap at " + str(cursor))
        cursor += len(entry.data)
    if cursor != len(data):
        raise ValueError("Unexpected global.cmp trailing data")

    # Recover full key from a documented 32-byte name (longer than cmpfile.py's
    # 23-byte decoder); validate known key bytes rather than guessing suffixes.
    matches = [e for e in entries if len(e.raw_name) == len(KNOWN_LONG_NAME)
               and all((e.raw_name[i] ^ KNOWN_LONG_NAME[i]) == KEY23[i]
                       for i in range(len(KEY23)))]
    if len(matches) != 1:
        raise ValueError("Cannot determine unique full archive name XOR key")
    key = bytes(a ^ b for a, b in zip(matches[0].raw_name, KNOWN_LONG_NAME))
    for entry in entries:
        if len(entry.raw_name) > len(key):
            raise ValueError("Archive name longer than verified XOR key")
        entry.name = bytes(c ^ key[i] for i, c in enumerate(entry.raw_name)).decode("ascii")
    if len({e.name.lower() for e in entries}) != len(entries):
        raise ValueError("Duplicate decoded global.cmp names")
    required = {"dat\\books.txt", "dat\\english\\books.txt",
                "dat\\english\\diary_quests.txt",
                "dat\\english\\diary_monsterlog.txt"}
    if not required.issubset({e.name.lower() for e in entries}):
        raise ValueError("Missing expected books or diary resources")
    return entries


def write_global(entries):
    size_header = 4 + sum(4 + len(e.raw_name) + 1 + 12 for e in entries)
    header = bytearray(struct.pack("<I", len(entries)))
    body = bytearray()
    offset = size_header
    for entry in entries:
        header.extend(struct.pack("<I", len(entry.raw_name)))
        header.extend(entry.raw_name)
        header.append(entry.terminator)
        header.extend(struct.pack("<III", offset, len(entry.data), entry.z))
        body.extend(entry.data)
        offset += len(entry.data)
    return bytes(header + body)


def split_raw_lines(data):
    # Splitting only on LF avoids treating high cp1252 bytes as line delimiters.
    # A final empty segment, if any, is retained to ensure perfect inversion.
    pieces = data.split(b"\n")
    return [piece + (b"\n" if i + 1 < len(pieces) else b"")
            for i, piece in enumerate(pieces)]


def is_book(name):
    return name.lower() in {"dat\\books.txt", "dat\\english\\books.txt"}


def is_diary(name):
    n = name.lower()
    return n.startswith(("dat\\diary_", "dat\\english\\diary_")) and n.endswith(".txt")


def text_catalog(entries, group, archive_sha):
    rows = [{"kind": "catalog", "format": "global-lines-v1",
             "source": GLOBAL_REL.as_posix(), "source_sha256": archive_sha,
             "group": group, "encoding": "cp1252"}]
    for index, entry in enumerate(entries):
        if not (is_book(entry.name) if group == "books" else is_diary(entry.name)):
            continue
        lines = split_raw_lines(entry.data)
        rows.append({"kind": "resource", "resource": entry.name, "entry_index": index,
                     "byte_length": len(entry.data), "source_sha256": sha(entry.data),
                     "line_count": len(lines)})
        offset = 0
        for line_index, raw in enumerate(lines):
            body = raw[:-2] if raw.endswith(b"\r\n") else (
                   raw[:-1] if raw.endswith(b"\n") else raw)
            rows.append({
                "kind": "line",
                "id": f"{index}:{line_index}",
                "resource": entry.name,
                "line_index": line_index,
                "source_offset": offset,
                "source_en": decode_display(body),
                "source_raw_b64": b64(raw),
                "source_sha256": sha(raw),
                "target_ko": "",
            })
            offset += len(raw)
        assert offset == len(entry.data)
    return rows


def restore_text_catalog(rows, entries, expected_group):
    if not rows or rows[0].get("kind") != "catalog":
        raise ValueError("Missing global catalog metadata")
    head = rows[0]
    if head.get("format") != "global-lines-v1" or head.get("group") != expected_group:
        raise ValueError("Mismatched global catalog version/group")
    expected_indexes = [i for i, e in enumerate(entries)
                        if (is_book(e.name) if expected_group == "books" else is_diary(e.name))]
    changes = {}
    pos = 1
    for index in expected_indexes:
        if pos >= len(rows):
            raise ValueError("Missing catalog resource")
        meta = rows[pos]
        pos += 1
        entry = entries[index]
        if (meta.get("kind") != "resource" or meta.get("entry_index") != index
                or meta.get("resource") != entry.name):
            raise ValueError("Wrong global resource order/name")
        chunks = []
        offset = 0
        for line_index in range(meta["line_count"]):
            if pos >= len(rows):
                raise ValueError("Missing catalog line")
            row = rows[pos]
            pos += 1
            if (row.get("kind") != "line" or row.get("resource") != entry.name
                    or row.get("line_index") != line_index
                    or row.get("source_offset") != offset):
                raise ValueError("Wrong catalog line order/offset")
            raw = unb64(row["source_raw_b64"])
            if sha(raw) != row["source_sha256"]:
                raise ValueError("Altered raw line")
            chunks.append(raw)
            offset += len(raw)
        payload = b"".join(chunks)
        if len(payload) != meta["byte_length"] or sha(payload) != meta["source_sha256"]:
            raise ValueError("Global embedded file did not round-trip")
        changes[index] = payload
    if pos != len(rows):
        raise ValueError("Unexpected extra global catalog rows")
    return changes


def scan_lp_fields(data, skip_header=False):
    """Conservative scanner: u32 byte count followed by printable 8-bit NUL text.

    All uninterpreted binary bytes are kept as exact gaps. The scanner deliberately
    does NOT reinterpret record pointers, flags, numeric fields or unknown fields.
    """
    out = []
    pos = 0
    prev_end = 0
    while pos + 7 <= len(data):
        n = u32(data, pos)
        if 3 <= n <= 4096 and pos + 4 + n <= len(data):
            raw = data[pos + 4:pos + 4 + n]
            is_printable = (raw[-1] == 0 and b"\0" not in raw[:-1]
                            and all(c >= 32 and c != 127 for c in raw[:-1])
                            and sum((65 <= c <= 90) or (97 <= c <= 122)
                                    for c in raw[:-1]) >= 2)
            if is_printable:
                if not (skip_header and pos == 0
                        and raw == b"Divinity Monologues V1.0\0"):
                    out.append((pos, data[prev_end:pos], raw))
                    prev_end = pos + 4 + n
                pos += 4 + n
                continue
        pos += 1
    return out, data[prev_end:]


def lp_catalog(data, source, skip_header=False):
    fields, tail = scan_lp_fields(data, skip_header)
    rows = [{"kind": "catalog", "format": "length-prefixed-v1",
             "source": source.as_posix(), "source_sha256": sha(data),
             "byte_length": len(data), "field_count": len(fields),
             "encoding": "cp1252"}]
    for field_index, (offset, before, raw) in enumerate(fields):
        rows.append({
            "kind": "text", "id": f"{field_index}",
            "field_index": field_index, "source_offset": offset,
            "before_b64": b64(before),
            "source_raw_b64": b64(raw),
            "length_u32": len(raw),
            "source_en": decode_display(raw[:-1]),
            "source_sha256": sha(raw),
            "target_ko": "",
        })
    rows.append({"kind": "tail", "source_raw_b64": b64(tail)})
    return rows


def restore_lp_catalog(rows, expected_source):
    if len(rows) < 2 or rows[0].get("kind") != "catalog":
        raise ValueError("Missing length-prefixed catalog header")
    header = rows[0]
    if (header.get("format") != "length-prefixed-v1"
            or header.get("source") != expected_source.as_posix()
            or header.get("field_count") != len(rows) - 2
            or rows[-1].get("kind") != "tail"):
        raise ValueError("Mismatched length-prefixed catalog metadata")
    output = bytearray()
    for i, row in enumerate(rows[1:-1]):
        if row.get("kind") != "text" or row.get("field_index") != i:
            raise ValueError("Wrong text field sequence")
        before = unb64(row["before_b64"])
        raw = unb64(row["source_raw_b64"])
        if len(output) + len(before) != row["source_offset"]:
            raise ValueError("Wrong text field byte offset")
        if (len(raw) != row["length_u32"] or not raw.endswith(b"\0")
                or sha(raw) != row["source_sha256"]):
            raise ValueError("Altered original text field")
        output.extend(before)
        output.extend(struct.pack("<I", len(raw)))
        output.extend(raw)
    output.extend(unb64(rows[-1]["source_raw_b64"]))
    data = bytes(output)
    if len(data) != header["byte_length"] or sha(data) != header["source_sha256"]:
        raise ValueError("Whole binary round-trip failed")
    return data


def make_catalogs(game):
    original = (game / GLOBAL_REL).read_bytes()
    mono = (game / MONO_REL).read_bytes()
    itemgen = (game / ITEM_REL).read_bytes()

    entries = read_global(original)
    rebuilt = write_global(entries)
    if rebuilt != original:
        raise ValueError("FAIL: global.cmp byte-level round-trip")
    books = text_catalog(entries, "books", sha(original))
    diary = text_catalog(entries, "diary", sha(original))
    changes = restore_text_catalog(books, entries, "books")
    changes.update(restore_text_catalog(diary, entries, "diary"))
    original_data = [entry.data for entry in entries]
    try:
        for i, payload in changes.items():
            entries[i].data = payload
        if write_global(entries) != original:
            raise ValueError("FAIL: global.cmp catalog reconstruction")
    finally:
        for entry, payload in zip(entries, original_data):
            entry.data = payload

    mono_rows = lp_catalog(mono, MONO_REL, skip_header=True)
    item_rows = lp_catalog(itemgen, ITEM_REL)
    if restore_lp_catalog(mono_rows, MONO_REL) != mono:
        raise ValueError("FAIL: mono.cmp catalog reconstruction")
    if restore_lp_catalog(item_rows, ITEM_REL) != itemgen:
        raise ValueError("FAIL: itemgen.cmp catalog reconstruction")

    rows = {"books": books, "diary": diary, "mono": mono_rows, "itemgen": item_rows}
    details = {
        "global.cmp": {"sha256": sha(original), "bytes": len(original),
                       "entries": len(entries), "pass": True},
        "mono.cmp": {"sha256": sha(mono), "bytes": len(mono),
                     "fields": len(mono_rows) - 2, "pass": True},
        "itemgen.cmp": {"sha256": sha(itemgen), "bytes": len(itemgen),
                        "fields": len(item_rows) - 2, "pass": True},
        "books": {"resources": sum(r["kind"] == "resource" for r in books),
                  "lines": sum(r["kind"] == "line" for r in books)},
        "diary": {"resources": sum(r["kind"] == "resource" for r in diary),
                  "lines": sum(r["kind"] == "line" for r in diary)},
    }
    return rows, details


def read_jsonl(path):
    with path.open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def verify_saved_catalogs(game):
    work = game / WORK_DIR
    rows = {group: read_jsonl(work / path) for group, path in OUTPUTS.items()}
    orig = (game / GLOBAL_REL).read_bytes()
    entries = read_global(orig)
    if rows["books"][0]["source_sha256"] != sha(orig) or (
            rows["diary"][0]["source_sha256"] != sha(orig)):
        raise ValueError("global.cmp changed since catalogs were created")
    updates = restore_text_catalog(rows["books"], entries, "books")
    updates.update(restore_text_catalog(rows["diary"], entries, "diary"))
    for i, payload in updates.items():
        entries[i].data = payload
    if write_global(entries) != orig:
        raise ValueError("FAIL: reassembly from saved global JSONL")
    for group, path in (("mono", MONO_REL), ("itemgen", ITEM_REL)):
        if restore_lp_catalog(rows[group], path) != (game / path).read_bytes():
            raise ValueError("FAIL: reassembly from saved " + group + " JSONL")
    return {group: len(lines) for group, lines in rows.items()}


def safe_game_dir(path):
    game = path.resolve(strict=True)
    if game != TEST_COPY.resolve(strict=True):
        raise ValueError("Only the designated steam_en_test game copy is allowed")
    if not (game / "div.exe").is_file():
        raise ValueError("div.exe missing from expected game copy")
    return game


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("verify", "export", "check"))
    parser.add_argument("game_copy", type=Path)
    args = parser.parse_args()
    game = safe_game_dir(args.game_copy)
    if args.mode == "check":
        result = verify_saved_catalogs(game)
        print("PASS saved JSONL -> original binary (in memory): "
              + json.dumps(result, ensure_ascii=False))
        return

    rows, details = make_catalogs(game)
    print("PASS original binary -> parsed -> original binary (in memory)")
    print(json.dumps(details, indent=2, ensure_ascii=False))
    if args.mode == "verify":
        return
    work = game / WORK_DIR
    # Preflight ALL target names before the first write. Never overwrite a
    # translator's existing catalog, even if only one of four files exists.
    existing = [work / name for name in OUTPUTS.values() if (work / name).exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite existing catalogs: "
                              + ", ".join(str(p) for p in existing))
    work.mkdir(parents=True, exist_ok=True)
    for group, filename in OUTPUTS.items():
        target = work / filename
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            for row in rows[group]:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"EXPORTED {group}: {target} ({len(rows[group])} JSONL records)")
    result = verify_saved_catalogs(game)
    print("PASS saved catalogs -> original binary (in memory): "
          + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
