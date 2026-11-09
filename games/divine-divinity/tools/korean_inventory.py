"""Read-only inventory of English Divine Divinity localization files.

Prints metadata only; game text is never copied into the report.
Usage: python korean_inventory.py <path-to-EN-game-copy> [--output report.json]
"""

import argparse
import hashlib
import json
from pathlib import Path

import textcmp


LOCALIZATION_FILES = (
    "dialogids.dat",
    "dialogs.div",
    "dialogtxt.dat",
    "hints.txt",
    "mono.cmp",
    "skills.txt",
    "text.cmp",
    "voice.cmp",
)


def inventory(game):
    game = game.resolve(strict=True)
    if not (game / "div.exe").is_file():
        raise ValueError("Expected a game copy containing div.exe")
    root = game / "localizations" / "english"
    if not root.is_dir():
        raise ValueError("English localization directory is missing")

    result = {"game_copy": str(game), "files": []}
    for name in LOCALIZATION_FILES:
        path = root / name
        if not path.is_file():
            result["files"].append({"path": str(path.relative_to(game)), "missing": True})
            continue
        data = path.read_bytes()
        row = {
            "path": str(path.relative_to(game)),
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if name == "text.cmp":
            tables = textcmp.read(str(path))
            strings = [s for _, records in tables for _, first, second in records
                       for s in (first, second) if s]
            row["tables"] = [{"id": tid, "records": len(records)}
                             for tid, records in tables]
            row["records"] = sum(len(records) for _, records in tables)
            row["nonempty_strings"] = len(strings)
            row["text_bytes"] = sum(len(s) for s in strings)
            row["strings_with_high_bytes"] = sum(any(b >= 128 for b in s)
                                                  for s in strings)
            row["strings_with_carriage_return"] = sum(b"\r" in s for s in strings)
        result["files"].append(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_copy", type=Path)
    parser.add_argument("--output", type=Path,
                        help="Write only metadata JSON; path must be outside the game copy")
    args = parser.parse_args()
    report = inventory(args.game_copy)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        output = args.output.resolve()
        if output == args.game_copy.resolve() or args.game_copy.resolve() in output.parents:
            parser.error("Report output must be outside the game copy")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
