#!/usr/bin/env python3
"""Propose exact-source translation-memory matches without changing game files.

An English source can be reused only if all known Korean targets are identical.
The output contains suggestions, NOT an edited source or a release catalog.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import unicodedata


def load(path):
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def propose(source, draft):
    if len(draft) > len(source):
        raise ValueError("Draft longer than baseline")
    for i, row in enumerate(draft):
        original = source[i]
        if any(row.get(key) != original.get(key)
               for key in ("id", "source_en", "source_sha256")):
            raise ValueError("Draft source mismatch at row %d" % (i + 1))
    memory = defaultdict(set)
    origins = defaultdict(list)
    for row in draft:
        target = row.get("target_ko", "")
        if target:
            text = row["source_en"]
            memory[text].add(target)
            origins[(text, target)].append(row["id"])

    accepted = {text: next(iter(targets)) for text, targets in memory.items()
                if len(targets) == 1}
    ambiguous = {text: len(targets) for text, targets in memory.items()
                 if len(targets) > 1}
    suggestions = []
    for row in source[len(draft):]:
        text = row["source_en"]
        target = accepted.get(text)
        # Pure ASCII terms may be intentional; do not silently extend exemptions.
        if not target or not any("\uac00" <= char <= "\ud7a3" for char in target):
            continue
        if unicodedata.normalize("NFC", target) != target:
            raise ValueError("Memory contains non-NFC text")
        candidate = dict(row)
        candidate["target_ko"] = target
        candidate["translation_status"] = "TM_SUGGESTION_NOT_REVIEWED"
        candidate["origin_id"] = origins[(text, target)][0]
        suggestions.append(candidate)
    return suggestions, {
        "baseline_rows": len(source),
        "draft_rows": len(draft),
        "memory_unique": len(accepted),
        "memory_ambiguous": len(ambiguous),
        "suggestions": len(suggestions),
        "conflicts": [
            {"source_en": key, "variants": sorted(memory[key]),
             "origin_ids": [x["id"] for x in draft if x["source_en"] == key]}
            for key in sorted(ambiguous)
        ],
    }


def self_test():
    def r(i, text, ko=""):
        return {"id": str(i), "source_en": text, "source_sha256": str(i),
                "target_ko": ko}
    source = [r(1, "Tree"), r(2, "Hero"), r(3, "Tree"),
              r(4, "Hero"), r(5, "Ghost"), r(6, "Ghost")]
    draft = [r(1, "Tree", "나무"), r(2, "Hero", "영웅")]
    out, info = propose(source, draft)
    assert len(out) == 2 and info["suggestions"] == 2
    draft2 = draft + [r(3, "Tree", "수목")]
    out2, info2 = propose(source, draft2)
    assert len(out2) == 1 and info2["memory_ambiguous"] == 1
    try:
        propose(source, [r(99, "Tree", "나무")])
    except ValueError:
        pass
    else:
        raise AssertionError("Mismatched IDs not rejected")
    print("PASS translation memory: 3/3")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not all((args.baseline, args.draft, args.out, args.report)):
        parser.error("Specify --baseline --draft --out --report")
    if args.out.exists() or args.report.exists():
        parser.error("Refusing to overwrite an existing report/output")
    suggestions, report = propose(load(args.baseline), load(args.draft))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as stream:
        for row in suggestions:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print("PASS exact memory: %d candidates, %d conflicting terms" %
          (report["suggestions"], report["memory_ambiguous"]))


if __name__ == "__main__":
    main()
