r"""Lossless Divine Divinity EN dialogtxt.dat / dialogs.div codec and JSONL exporter.

Reads ONLY localizations/english in a supplied *test game copy*. Writes exactly
two new JSONL catalogs in its _GameRemix_Korean_Work directory with exclusive
creation; never writes the game's binary resources. Python 3.9+.
Usage:
  python korean_dialog_codec.py C:\path\steam_en_test --check
  python korean_dialog_codec.py C:\path\steam_en_test --export
  python korean_dialog_codec.py C:\path\steam_en_test --verify-catalogs
"""
import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path

TEXT_SHA = "6d7d1ec92cb540cfaca4fe2bed124a2cf1290a1dffeb723c52bce1b02caee83e"
GRAPH_SHA = "30d8f64b34bad481307191b90e4f1d21a06c6d49da52bc86ca5d19ccff5de196"
TEXT_NAME = "dialogtxt_en_catalog.jsonl"
GRAPH_NAME = "dialogs_en_graph.jsonl"


def sha256(blob):
    return hashlib.sha256(blob).hexdigest()


def u32(value):
    return struct.pack("<I", value)


def decode_units(encoded_le):
    """Stored little-endian 16-bit code units equal (original unit + 1) mod 65536.

    Do not use the old cp1251 + '?' fallback: U+2019 and U+2026 occur in EN.
    This returns each original UTF-16 code unit individually (no normalization).
    """
    if len(encoded_le) % 2:
        raise ValueError("Odd number of bytes in encoded dialog text")
    units = struct.unpack("<%dH" % (len(encoded_le) // 2), encoded_le)
    return "".join(chr((unit - 1) & 0xFFFF) for unit in units)


def encode_units(text):
    """Encode Unicode through UTF-16LE units, retaining unpaired surrogates."""
    raw = text.encode("utf-16-le", errors="surrogatepass")
    units = struct.unpack("<%dH" % (len(raw) // 2), raw)
    return struct.pack("<%dH" % len(units), *(((v + 1) & 0xFFFF) for v in units))


def parse_dialogtxt(data):
    if len(data) < 12:
        raise ValueError("Truncated dialogtxt.dat header")
    ver1, ver2, count = struct.unpack_from("<3I", data)
    base = 12 + 8 * count
    if base > len(data):
        raise ValueError("Dialog text index exceeds file")
    entries = []
    previous_end = 0
    for index in range(count):
        off, length = struct.unpack_from("<2I", data, 12 + 8 * index)
        if off != previous_end or length % 2 or base + off + length > len(data):
            raise ValueError("Noncontiguous, odd or out-of-bounds text entry %d" % index)
        raw = data[base + off:base + off + length]
        entries.append({"offset": off, "raw": raw, "source_en": decode_units(raw)})
        previous_end = off + length
    if base + previous_end != len(data):
        raise ValueError("Unaccounted trailing dialog text bytes")
    return {"versions": [ver1, ver2], "entries": entries}


def build_dialogtxt(table):
    entries = table["entries"]
    data = bytearray(struct.pack("<3I", *table["versions"], len(entries)))
    body = bytearray()
    for entry in entries:
        raw = entry["raw"]
        if len(raw) % 2:
            raise ValueError("Text payload must contain complete u16 units")
        data.extend(struct.pack("<2I", len(body), len(raw)))
        body.extend(raw)
    return bytes(data + body)


def text_catalog_rows(table):
    for index, entry in enumerate(table["entries"]):
        raw = entry["raw"]
        yield {
            "index": index,
            "file_versions": table["versions"],
            "original_offset_bytes": entry["offset"],
            "original_length_bytes": len(raw),
            "source_en": entry["source_en"],
            "source_encoded_le_hex": raw.hex(),
            "source_sha256": sha256(raw),
            "target_ko": "",
        }


def text_table_from_rows(rows):
    if not rows:
        raise ValueError("Empty dialog text catalog")
    version = rows[0]["file_versions"]
    entries = []
    original_cursor = 0
    for index, row in enumerate(rows):
        if row["index"] != index or row["file_versions"] != version:
            raise ValueError("Text catalog indices/versions differ at %d" % index)
        original = bytes.fromhex(row["source_encoded_le_hex"])
        if (sha256(original) != row["source_sha256"]
                or decode_units(original) != row["source_en"]
                or len(original) != row["original_length_bytes"]):
            raise ValueError("Original text integrity lost at %d" % index)
        if row["original_offset_bytes"] != original_cursor:
            raise ValueError("Source text offset changed at %d" % index)
        original_cursor += len(original)
        translation = row.get("target_ko", "")
        if not isinstance(translation, str):
            raise ValueError("Non-string translation at %d" % index)
        raw = encode_units(translation) if translation else original
        entries.append({"offset": row["original_offset_bytes"], "raw": raw,
                        "source_en": row["source_en"]})
    return {"versions": version, "entries": entries}


def parse_dialogs(data):
    """Keep every scalar/array as unsigned u32, and every sound-name byte."""
    if len(data) < 16:
        raise ValueError("Truncated dialogs.div header")
    header = list(struct.unpack_from("<4I", data))
    pos = 16

    def read_u32():
        nonlocal pos
        if pos + 4 > len(data):
            raise ValueError("Truncated dialogs.div u32 at offset %d" % pos)
        value = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        return value

    def read_array():
        length = read_u32()
        if length > (len(data) - pos) // 4:
            raise ValueError("Truncated dialogs.div u32 array")
        return [read_u32() for _ in range(length)]

    dialogs = []
    for _ in range(header[3]):
        dialog_id = read_u32()
        count = read_u32()
        nodes = []
        for _ in range(count):
            node_id, text_idx, start_flag = read_u32(), read_u32(), read_u32()
            sound_len = read_u32()
            if sound_len > len(data) - pos:
                raise ValueError("Truncated sound name")
            sound = data[pos:pos + sound_len]
            pos += sound_len
            pre = [read_u32() for _ in range(2)]
            lists = [read_array() for _ in range(4)]
            post = [read_u32() for _ in range(5)]
            edge_count = read_u32()
            if edge_count > (len(data) - pos) // 8:
                raise ValueError("Truncated edges array")
            edges = [[read_u32(), read_u32()] for _ in range(edge_count)]
            nodes.append({
                "id": node_id, "text_index": text_idx, "start_flag": start_flag,
                "sound_name": sound.decode("latin1"),
                "sound_name_raw_hex": sound.hex(),
                "pre_fields": pre, "lists": lists, "post_fields": post,
                "edges": edges,
            })
        dialogs.append({"dialog_id": dialog_id, "nodes": nodes})
    if pos != len(data):
        raise ValueError("Unaccounted graph bytes at offset %d" % pos)
    return {"header": header, "dialogs": dialogs}


def build_dialogs(graph):
    header = graph["header"]
    dialogs = graph["dialogs"]
    if len(header) != 4 or header[3] != len(dialogs):
        raise ValueError("Graph header/dialog count mismatch")
    out = bytearray(struct.pack("<4I", *header))
    for dialog in dialogs:
        nodes = dialog["nodes"]
        out.extend(struct.pack("<2I", dialog["dialog_id"], len(nodes)))
        for n in nodes:
            out.extend(struct.pack("<3I", n["id"], n["text_index"], n["start_flag"]))
            sound = bytes.fromhex(n["sound_name_raw_hex"])
            if sound.decode("latin1") != n["sound_name"]:
                raise ValueError("Sound name and raw bytes disagree")
            out.extend(u32(len(sound)))
            out.extend(sound)
            if len(n["pre_fields"]) != 2 or len(n["lists"]) != 4 or len(n["post_fields"]) != 5:
                raise ValueError("A node has missing service fields")
            for value in n["pre_fields"]:
                out.extend(u32(value))
            for values in n["lists"]:
                out.extend(u32(len(values)))
                for value in values:
                    out.extend(u32(value))
            for value in n["post_fields"]:
                out.extend(u32(value))
            out.extend(u32(len(n["edges"])))
            for edge in n["edges"]:
                if len(edge) != 2:
                    raise ValueError("Bad edge")
                out.extend(struct.pack("<2I", *edge))
    return bytes(out)


def graph_catalog_rows(graph):
    for index, dialog in enumerate(graph["dialogs"]):
        yield {"dialog_index": index, "file_header": graph["header"],
               "dialog_id": dialog["dialog_id"], "nodes": dialog["nodes"]}


def graph_from_rows(rows):
    if not rows:
        raise ValueError("Empty graph catalog")
    header = rows[0]["file_header"]
    dialogs = []
    for index, row in enumerate(rows):
        if row["dialog_index"] != index or row["file_header"] != header:
            raise ValueError("Graph catalog indices/header differ at %d" % index)
        dialogs.append({"dialog_id": row["dialog_id"], "nodes": row["nodes"]})
    return {"header": header, "dialogs": dialogs}


def read_jsonl(path):
    with path.open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl_exclusive(path, rows):
    # Mode x creates a file only if it does NOT already exist.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def check_content(table, graph):
    texts = table["entries"]
    dialogs = graph["dialogs"]
    counts = collections.Counter(
        ord(c) for entry in texts for c in entry["source_en"]
        if ord(c) in (0x2019, 0x2026))
    node_count = sum(len(d["nodes"]) for d in dialogs)
    edge_count = sum(len(n["edges"]) for d in dialogs for n in d["nodes"])
    indices = [n["text_index"] for d in dialogs for n in d["nodes"]]
    if table["versions"] != [1, 1] or graph["header"] != [1, 6, 11, 490]:
        raise ValueError("Unexpected Steam EN file versions")
    if len(texts) != 7583 or len(dialogs) != 490 or node_count != 7583:
        raise ValueError("Wrong number of text rows, dialogs or graph nodes")
    if edge_count != 15446 or sorted(indices) != list(range(len(texts))):
        raise ValueError("Edges count or text index coverage differs")
    if counts != {0x2019: 5, 0x2026: 2}:
        raise ValueError("Expected U+2019 x5 and U+2026 x2, found %r" % counts)
    probe = "It’s … 한글"
    if decode_units(encode_units(probe)) != probe:
        raise ValueError("Synthetic Unicode encode/decode test failed")
    return node_count, edge_count, counts


def run(game, export=False, verify_catalogs=False):
    game = game.resolve(strict=True)
    loc = game / "localizations" / "english"
    ptext, pgraph = loc / "dialogtxt.dat", loc / "dialogs.div"
    if not (game / "div.exe").is_file():
        raise ValueError("Expected a test game directory containing div.exe")
    before_text, before_graph = ptext.read_bytes(), pgraph.read_bytes()
    if sha256(before_text) != TEXT_SHA or sha256(before_graph) != GRAPH_SHA:
        raise ValueError("Source SHA-256 mismatch; expected exact Steam EN test copy")
    text_table = parse_dialogtxt(before_text)
    graph = parse_dialogs(before_graph)
    nodes, edges, high = check_content(text_table, graph)
    if build_dialogtxt(text_table) != before_text:
        raise AssertionError("FAIL binary dialogtxt round-trip")
    if build_dialogs(graph) != before_graph:
        raise AssertionError("FAIL binary dialogs round-trip")
    print("PASS: dialogtxt.dat in-memory byte-for-byte round-trip, SHA256=" + TEXT_SHA)
    print("PASS: dialogs.div in-memory byte-for-byte round-trip, SHA256=" + GRAPH_SHA)
    print("PASS: %d text rows; %d graphs; %d nodes; %d edges; unique text indices=%d" %
          (len(text_table["entries"]), len(graph["dialogs"]), nodes, edges, nodes))
    print("PASS: U+2019=%d U+2026=%d; synthetic Hangul encoder round-trip" %
          (high[0x2019], high[0x2026]))
    work = game / "_GameRemix_Korean_Work"
    target_text, target_graph = work / TEXT_NAME, work / GRAPH_NAME
    if export:
        if target_text.exists() or target_graph.exists():
            raise FileExistsError("Refusing overwrite: %s or %s already exists" %
                                  (target_text, target_graph))
        work.mkdir(exist_ok=True)
        # Validate the proposed catalog records *before* any disk writes.
        text_rows = list(text_catalog_rows(text_table))
        graph_rows = list(graph_catalog_rows(graph))
        if build_dialogtxt(text_table_from_rows(text_rows)) != before_text:
            raise AssertionError("Text JSONL projection not reversible")
        if build_dialogs(graph_from_rows(graph_rows)) != before_graph:
            raise AssertionError("Graph JSONL projection not reversible")
        write_jsonl_exclusive(target_text, text_rows)
        write_jsonl_exclusive(target_graph, graph_rows)
        print("PASS: exclusively created %s (%d JSONL records)" %
              (target_text, len(text_rows)))
        print("PASS: exclusively created %s (%d JSONL records)" %
              (target_graph, len(graph_rows)))
        verify_catalogs = True
    if verify_catalogs:
        actual_text = build_dialogtxt(text_table_from_rows(read_jsonl(target_text)))
        actual_graph = build_dialogs(graph_from_rows(read_jsonl(target_graph)))
        if actual_text != before_text or actual_graph != before_graph:
            raise AssertionError("JSONL reload does not reconstruct exact binaries")
        print("PASS: both JSONL catalogs reloaded; binary reconstruction exact")
    after_text, after_graph = ptext.read_bytes(), pgraph.read_bytes()
    if (after_text != before_text or after_graph != before_graph or
            sha256(after_text) != TEXT_SHA or sha256(after_graph) != GRAPH_SHA):
        raise AssertionError("Source files changed during run")
    print("PASS: SHA256 source files unchanged after execution (both originals read-only)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("test_game_copy", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Read-only verification (default)")
    group.add_argument("--export", action="store_true", help="Create two new JSONL catalogs")
    group.add_argument("--verify-catalogs", action="store_true", help="Read-only check of JSONL exports")
    args = parser.parse_args()
    run(args.test_game_copy, export=args.export, verify_catalogs=args.verify_catalogs)


if __name__ == "__main__":
    main()
