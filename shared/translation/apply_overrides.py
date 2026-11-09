#!/usr/bin/env python3
"""Apply reviewed exact-source terminology choices to a standalone draft.

Never modifies baseline, existing drafts, game assets or executables.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(x) for x in stream if x.strip()]


def override(source, draft, editorial):
    if len(draft) > len(source):
        raise ValueError("Draft length beyond baseline")
    rules = {}
    for row in editorial:
        key = row.get("source_en")
        if (not isinstance(key, str) or not key
                or not isinstance(row.get("target_ko"), str)
                or not row["target_ko"].strip()
                or not isinstance(row.get("reason"), str)
                or len(row["reason"].strip()) < 8 or key in rules):
            raise ValueError("Invalid or duplicate editorial rule")
        rules[key] = row["target_ko"]

    changed = 0
    hits = set()
    updated = []
    for i, row in enumerate(draft):
        src = source[i]
        if any(row.get(k) != src.get(k)
               for k in ("id", "source_en", "source_sha256")):
            raise ValueError("Source drift at index %d" % i)
        out = dict(row)
        key = out["source_en"]
        if key in rules:
            hits.add(key)
            if out["target_ko"] != rules[key]:
                changed += 1
                out["target_ko"] = rules[key]
        updated.append(out)
    if hits != set(rules):
        raise ValueError("Unmatched editorial rule(s): %s" %
                         sorted(set(rules) - hits))
    return updated, {"rows": len(updated), "rules": len(rules),
                     "affected_rows": changed}


def test():
    src = [{"id": "1", "source_en": "Bee", "source_sha256": "x"},
           {"id": "2", "source_en": "Bee", "source_sha256": "y"}]
    draft = [dict(src[0], target_ko="꿀벌"),
             dict(src[1], target_ko="벌")]
    rules = [{"source_en": "Bee", "target_ko": "벌",
              "reason": "consistent generic insect label"}]
    out, report = override(src, draft, rules)
    assert [r["target_ko"] for r in out] == ["벌", "벌"]
    assert report["affected_rows"] == 1
    try:
        override(src, [dict(draft[0], id="changed")], rules)
    except ValueError:
        pass
    else:
        raise AssertionError("Missing source guard")
    print("PASS editorial override 2/2")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path)
    p.add_argument("--draft", type=Path)
    p.add_argument("--rules", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--report", type=Path)
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        test()
        return
    if not all((args.baseline, args.draft, args.rules, args.out, args.report)):
        p.error("Specify baseline, draft, rules, out and report")
    if args.out.exists() or args.report.exists():
        p.error("Refusing to overwrite an existing result")
    updated, stats = override(load_jsonl(args.baseline), load_jsonl(args.draft),
                              json.loads(args.rules.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as stream:
        for row in updated:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    args.report.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print("PASS editorial: %d rules, %d modified rows" %
          (stats["rules"], stats["affected_rows"]))


if __name__ == "__main__":
    main()
