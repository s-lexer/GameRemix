"""Export text.cmp to a lossless EN→KO work catalog beside a game copy.

The original game file is only read. No translation is applied to the game.
Usage: python korean_catalog.py <path-to-EN-game-copy>
"""

import argparse
import hashlib
import json
from pathlib import Path

import textcmp


def export(game):
    game = game.resolve(strict=True)
    source = game / "localizations" / "english" / "text.cmp"
    if not (game / "div.exe").is_file() or not source.is_file():
        raise ValueError("Expected an English game copy with div.exe and text.cmp")
    source_bytes = source.read_bytes()
    tables = textcmp.read(str(source))
    work = game / "_GameRemix_Korean_Work"
    work.mkdir(exist_ok=True)
    target = work / "text_cmp_catalog.jsonl"
    if target.exists():
        raise FileExistsError("Catalog already exists; refusing to overwrite translation work: " + str(target))
    rows = []
    for table_id, records in tables:
        for record_id, first, second in records:
            for field, raw in (("text", first), ("description", second)):
                if not raw:
                    continue
                if any(byte >= 128 for byte in raw):
                    raise ValueError("Non-ASCII source needs an explicit decoder: table %d record %d" %
                                     (table_id, record_id))
                rows.append({
                    "id": "%d:%d:%s" % (table_id, record_id, field),
                    "source_en": raw.decode("ascii"),
                    "target_ko": "",
                    "source_sha256": hashlib.sha256(raw).hexdigest(),
                })
    temporary = target.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(target)
    manifest = {
        "source": str(source.relative_to(game)),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "catalog": target.name,
        "entries": len(rows),
        "status": "extracted; Korean translation and game patch not applied",
    }
    (work / "text_cmp_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target, len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_copy", type=Path)
    args = parser.parse_args()
    path, count = export(args.game_copy)
    print("Extracted %d strings to %s" % (count, path))


if __name__ == "__main__":
    main()
