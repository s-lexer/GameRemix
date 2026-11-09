#!/usr/bin/env python3
"""Read-only JSONL catalog QA for localization workflows.

Validates identifiers, source hashes, protected tokens, UTF-8/Korean Unicode,
and configurable display-size budgets. No game formats or paths are hard-coded.
Output reports contain IDs and issue codes, never source/translated strings.

Examples:
  python catalog_qa.py path/to/catalog.jsonl --report qa.json
  python catalog_qa.py catalog.jsonl --baseline frozen.jsonl --id-pattern "..."
  python catalog_qa.py --self-test
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

HEX256 = re.compile(r"[0-9a-f]{64}\Z")
DEFAULT_ID_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._:/-]*"
CONTROL_PATTERN = r"\\(?:[nrvt](?:[0-9]+)?|x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4})|[\x00-\x1f\x7f]"
PRINTF_PATTERN = (
    r"%(?:%|(?:\([A-Za-z_]\w*\))?(?:[1-9]\d*\$)?"
    r"[-+#0]*[0-9]*(?:\.[0-9]+)?(?:hh|ll|[hlLzjt])?"
    r"[diuoxXfFeEgGaAcCsSp])"
)
BRACE_PATTERN = r"\{(?:[A-Za-z_][\w.-]*|[0-9]+)(?:![rsa])?(?::[^{}]*)?\}|\$\{[A-Za-z_]\w*\}"
TOKENS = re.compile(
    r"(?P<control>" + CONTROL_PATTERN + r")|"
    r"(?P<placeholder>" + PRINTF_PATTERN + r"|" + BRACE_PATTERN + r")"
)
UNKNOWN_ESCAPE = re.compile(r"(?<!\\)\\[A-Za-z]")
UNKNOWN_PRINTF = re.compile(r"%(?:\([A-Za-z_]\w*\))?(?:[1-9]\d*\$)?[-+#0]*\d*(?:\.\d+)?[A-Za-z]")
SUSPICIOUS_BRACE = re.compile(r"\{(?:[A-Za-z_][\w.-]*|\d+)(?:![rsa])?(?::[^{}]*)?(?!\})")
UNSAFE_FORMAT = frozenset({"\ufeff", "\ufffd"})
ISSUE_LIMIT = 100


def hangul(char: str) -> bool:
    code = ord(char)
    return (0xAC00 <= code <= 0xD7A3 or 0x1100 <= code <= 0x11FF
            or 0x3130 <= code <= 0x318F or 0xA960 <= code <= 0xA97F
            or 0xD7B0 <= code <= 0xD7FF)


def tokenize(value: str):
    """Opaque, lossless control/placeholder tokens with their categories."""
    return [(m.lastgroup, m.group()) for m in TOKENS.finditer(value)]


def unprotected(value: str) -> str:
    return TOKENS.sub(lambda m: " " * len(m.group()), value)


def line_count(value: str) -> int:
    # Both actual newlines and game-style literal backslash-n count as breaks.
    return 1 + value.count("\n") + len(re.findall(r"(?<!\\)\\n", value))


def bad_unicode(value: str) -> bool:
    for ch in value:
        cp = ord(ch)
        if (ch in UNSAFE_FORMAT or 0xD800 <= cp <= 0xDFFF
                or 0xFDD0 <= cp <= 0xFDEF or cp & 0xFFFF in (0xFFFE, 0xFFFF)
                or unicodedata.category(ch) == "Cf"
                or (unicodedata.category(ch) == "Cc" and ch not in "\r\n\t")):
            return True
    return False


def validate_lines(lines, *, id_pattern=DEFAULT_ID_PATTERN,
                   source_field="source_en", target_field="target_ko",
                   hash_field="source_sha256", id_field="id",
                   source_encoding="utf-8", max_chars=None, max_bytes=None,
                   max_lines=None, require_hangul=False, baseline=None,
                   allow_added=False, allow_removed=False,
                   no_hangul_exceptions=None):
    """Validate iterable of bytes/str JSONL records; returns safe metadata.

    Optional baseline is a dict of ID -> source_sha256 for cross-run ID stability.
    Same English text under different structural IDs is legitimate and counted,
    not rejected. An empty target means pending, never a translated PASS.
    """
    id_re = re.compile(id_pattern + r"\Z")
    seen = {}
    source_frequency = Counter()
    error_codes, warning_codes = Counter(), Counter()
    issues = []
    count = translated = untranslated = 0
    max_target_chars = max_target_bytes = max_target_lines = 0
    no_hangul_exceptions = no_hangul_exceptions or {}
    used_exceptions = set()

    def issue(level, code, line, item_id=None):
        bucket = error_codes if level == "FAIL" else warning_codes
        bucket[code] += 1
        if len(issues) < ISSUE_LIMIT:
            item = {"level": level, "code": code, "line": line}
            if item_id is not None:
                item["id"] = item_id
            issues.append(item)

    for number, raw in enumerate(lines, 1):
        if isinstance(raw, bytes):
            if number == 1 and raw.startswith(b"\xef\xbb\xbf"):
                issue("FAIL", "UTF8_BOM", number)
                raw = raw[3:]
            try:
                raw = raw.decode("utf-8", "strict")
            except UnicodeDecodeError:
                issue("FAIL", "INVALID_UTF8", number)
                continue
        if not raw.strip():
            issue("FAIL", "EMPTY_LINE", number)
            continue
        try:
            row = json.loads(raw)
        except (ValueError, TypeError):
            issue("FAIL", "INVALID_JSON", number)
            continue
        count += 1
        if not isinstance(row, dict):
            issue("FAIL", "NOT_OBJECT", number)
            continue
        item_id = row.get(id_field)
        if not isinstance(item_id, str) or not item_id or not id_re.fullmatch(item_id):
            issue("FAIL", "INVALID_ID", number)
            item_id = None
        elif item_id in seen:
            issue("FAIL", "DUPLICATE_ID", number, item_id)
        source = row.get(source_field)
        target = row.get(target_field)
        digest = row.get(hash_field)
        if not isinstance(source, str):
            issue("FAIL", "INVALID_SOURCE", number, item_id)
        if not isinstance(target, str):
            issue("FAIL", "INVALID_TARGET", number, item_id)
        if not isinstance(digest, str) or not HEX256.fullmatch(digest):
            issue("FAIL", "INVALID_SOURCE_SHA256", number, item_id)
            digest = None
        if isinstance(source, str):
            try:
                expected = hashlib.sha256(source.encode(source_encoding, "strict")).hexdigest()
            except (UnicodeError, LookupError):
                issue("FAIL", "SOURCE_NOT_ENCODABLE", number, item_id)
            else:
                if digest and expected != digest:
                    issue("FAIL", "SOURCE_HASH_MISMATCH", number, item_id)
                source_frequency[expected] += 1
        if item_id is not None and item_id not in seen:
            seen[item_id] = digest
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        if not target:
            untranslated += 1
            continue
        translated += 1
        chars, size, lines_used = len(target), len(target.encode("utf-8", "surrogatepass")), line_count(target)
        max_target_chars = max(max_target_chars, chars)
        max_target_bytes = max(max_target_bytes, size)
        max_target_lines = max(max_target_lines, lines_used)
        if max_chars is not None and chars > max_chars:
            issue("FAIL", "CHAR_LIMIT", number, item_id)
        if max_bytes is not None and size > max_bytes:
            issue("FAIL", "UTF8_BYTE_LIMIT", number, item_id)
        if max_lines is not None and lines_used > max_lines:
            issue("FAIL", "LINE_LIMIT", number, item_id)
        if bad_unicode(target):
            issue("FAIL", "INVALID_UNICODE", number, item_id)
        if unicodedata.normalize("NFC", target) != target:
            issue("FAIL", "NOT_NFC", number, item_id)
        plain = unprotected(target)
        if UNKNOWN_ESCAPE.search(plain):
            issue("FAIL", "UNKNOWN_ESCAPE", number, item_id)
        if UNKNOWN_PRINTF.search(plain):
            issue("FAIL", "UNKNOWN_PRINTF", number, item_id)
        if SUSPICIOUS_BRACE.search(plain):
            issue("FAIL", "UNBALANCED_PLACEHOLDER", number, item_id)
        if any(ch.isalpha() for ch in plain) and not any(hangul(ch) for ch in plain):
            exception = no_hangul_exceptions.get(item_id)
            if (exception is not None and digest == exception["source_sha256"]
                    and target == exception["target"]):
                used_exceptions.add(item_id)
                issue("WARN", "EXEMPT_NO_HANGUL", number, item_id)
            elif require_hangul:
                issue("FAIL", "NO_HANGUL", number, item_id)
            else:
                issue("WARN", "NO_HANGUL", number, item_id)
        src_tokens, dst_tokens = tokenize(source), tokenize(target)
        for category in ("placeholder", "control"):
            a = [word for kind, word in src_tokens if kind == category]
            b = [word for kind, word in dst_tokens if kind == category]
            if Counter(a) != Counter(b):
                issue("FAIL", category.upper() + "_MISMATCH", number, item_id)
            elif category == "control" and a != b:
                issue("FAIL", "CONTROL_ORDER", number, item_id)

    for exception_id in no_hangul_exceptions.keys() - used_exceptions:
        issue("FAIL", "UNUSED_NO_HANGUL_EXCEPTION", 0, exception_id)

    if baseline is not None:
        for item_id, digest in seen.items():
            if item_id not in baseline:
                if not allow_added:
                    issue("FAIL", "BASELINE_ADDED_ID", 0, item_id)
            elif baseline[item_id] != digest:
                issue("FAIL", "BASELINE_SOURCE_CHANGED", 0, item_id)
        if not allow_removed:
            for item_id in baseline.keys() - seen.keys():
                issue("FAIL", "BASELINE_REMOVED_ID", 0, item_id)

    return {
        "status": "FAIL" if error_codes else "PASS",
        "rows": count,
        "ids_unique": len(seen),
        "translated": translated,
        "untranslated": untranslated,
        "duplicate_source_occurrences": sum(v - 1 for v in source_frequency.values()),
        "max_target_chars": max_target_chars,
        "max_target_utf8_bytes": max_target_bytes,
        "max_target_lines": max_target_lines,
        "id_stability": "checked_against_baseline" if baseline is not None else "not_verified_no_baseline",
        "errors": sum(error_codes.values()),
        "warnings": sum(warning_codes.values()),
        "no_hangul_exceptions_used": len(used_exceptions),
        "error_codes": dict(sorted(error_codes.items())),
        "warning_codes": dict(sorted(warning_codes.items())),
        "issues": issues,
        "issues_truncated": max(0, sum(error_codes.values()) + sum(warning_codes.values()) - len(issues)),
    }



def read_baseline(path: Path, *, id_field="id", hash_field="source_sha256"):
    """Read an immutable comparison snapshot; refuse duplicates and invalid IDs."""
    result = {}
    with path.open("rb") as stream:
        for number, raw in enumerate(stream, 1):
            try:
                row = json.loads(raw.decode("utf-8", "strict"))
            except (UnicodeError, ValueError, TypeError) as exc:
                raise ValueError("Invalid baseline JSONL at line %d" % number) from exc
            if not isinstance(row, dict):
                raise ValueError("Non-object baseline record at line %d" % number)
            item_id, digest = row.get(id_field), row.get(hash_field)
            if not isinstance(item_id, str) or not item_id or not isinstance(digest, str) or not HEX256.fullmatch(digest):
                raise ValueError("Invalid baseline ID/hash at line %d" % number)
            if item_id in result:
                raise ValueError("Duplicate baseline ID at line %d" % number)
            result[item_id] = digest
    return result


def read_no_hangul_exceptions(path: Path):
    """Load narrowly scoped, source-hash-bound editorial exceptions from JSONL."""
    result = {}
    with path.open("rb") as stream:
        for number, raw in enumerate(stream, 1):
            try:
                row = json.loads(raw.decode("utf-8", "strict"))
            except (UnicodeError, ValueError, TypeError) as exc:
                raise ValueError("Invalid no-Hangul exception JSONL at line %d" % number) from exc
            if not isinstance(row, dict):
                raise ValueError("Non-object no-Hangul exception at line %d" % number)
            item_id = row.get("id")
            digest = row.get("source_sha256")
            target = row.get("target")
            reason = row.get("reason")
            if (not isinstance(item_id, str) or not re.fullmatch(DEFAULT_ID_PATTERN, item_id)
                    or not isinstance(digest, str) or not HEX256.fullmatch(digest)
                    or not isinstance(target, str) or not target.strip()
                    or not isinstance(reason, str) or len(reason.strip()) < 10):
                raise ValueError("Invalid no-Hangul exception fields at line %d" % number)
            if item_id in result:
                raise ValueError("Duplicate no-Hangul exception at line %d" % number)
            result[item_id] = row
    return result


def run_self_tests():
    """In-memory positive and deliberately failing tests, no game data."""
    src = r"Hello {name}!\n %d"
    ko = r"안녕하세요 {name}!\n %d"
    digest = hashlib.sha256(src.encode("utf-8")).hexdigest()

    def record(**changes):
        row = {"id": "demo:1:text", "source_en": src,
               "target_ko": ko, "source_sha256": digest}
        row.update(changes)
        return row

    results = []

    def check(name, rows, expected, code=None, options=None):
        payload = [x if isinstance(x, bytes) else
                   (json.dumps(x, ensure_ascii=True) if not isinstance(x, str) else x).encode("utf-8")
                   for x in rows]
        outcome = validate_lines(payload, **(options or {}))
        okay = outcome["status"] == expected and (code is None or code in outcome["error_codes"])
        results.append({"name": name, "status": "PASS" if okay else "FAIL",
                        "expected": expected, "actual": outcome["status"],
                        "expected_error": code,
                        "actual_error_codes": sorted(outcome["error_codes"])})
        
    check("valid_hangul_and_tokens", [record()], "PASS", options={"require_hangul": True})
    check("untranslated_allowed", [record(target_ko="")], "PASS")
    check("duplicate_source_separate_ids", [record(), record(id="demo:2:text")], "PASS")
    check("matching_baseline", [record()], "PASS", options={"baseline": {"demo:1:text": digest}})
    check("bad_source_sha256", [record(source_sha256="0" * 64)], "FAIL", "SOURCE_HASH_MISMATCH")
    check("bad_sha256_syntax", [record(source_sha256="BAD")], "FAIL", "INVALID_SOURCE_SHA256")
    check("duplicate_id", [record(), record()], "FAIL", "DUPLICATE_ID")
    check("invalid_id", [record(id="spaces invalid")], "FAIL", "INVALID_ID")
    check("missing_field", [{"id": "demo:1:text", "target_ko": ko,
                             "source_sha256": digest}], "FAIL", "INVALID_SOURCE")
    check("missing_placeholder", [record(target_ko=r"안녕하세요!\n %d")], "FAIL", "PLACEHOLDER_MISMATCH")
    check("changed_placeholder", [record(target_ko=r"안녕하세요 {other}!\n %d")],
          "FAIL", "PLACEHOLDER_MISMATCH")
    check("extra_placeholder", [record(target_ko=r"안녕하세요 {name}!\n %d %s")],
          "FAIL", "PLACEHOLDER_MISMATCH")
    check("missing_control", [record(target_ko=r"안녕하세요 {name}! %d")],
          "FAIL", "CONTROL_MISMATCH")
    check("control_order", [record(source_en=r"Hello\n\t",
                                   target_ko=r"안녕\t\n",
                                   source_sha256=hashlib.sha256(b"Hello\\n\\t").hexdigest())],
          "FAIL", "CONTROL_ORDER")
    check("unknown_escape", [record(target_ko=r"안녕하세요 {name}!\n %d\q")],
          "FAIL", "UNKNOWN_ESCAPE")
    check("unknown_printf", [record(target_ko=r"안녕하세요 {name}!\n %d %q")],
          "FAIL", "UNKNOWN_PRINTF")
    check("unbalanced_brace", [record(target_ko=r"안녕하세요 {name}!\n %d {broken")],
          "FAIL", "UNBALANCED_PLACEHOLDER")
    check("nul_code_point", [record(target_ko=ko + "\x00")],
          "FAIL", "INVALID_UNICODE")
    check("surrogate_code_point", [record(target_ko=ko + "\ud800")],
          "FAIL", "INVALID_UNICODE")
    check("replacement_character", [record(target_ko=ko + "\ufffd")],
          "FAIL", "INVALID_UNICODE")
    check("decomposed_hangul", [record(target_ko=ko + "\u1100\u1161")],
          "FAIL", "NOT_NFC")
    check("latin_only_strict", [record(target_ko=r"Welcome {name}!\n %d")],
          "FAIL", "NO_HANGUL", {"require_hangul": True})
    latin = r"Welcome {name}!\n %d"
    exception = {"demo:1:text": {"source_sha256": digest, "target": latin}}
    check("explicit_latin_exception", [record(target_ko=latin)],
          "PASS", options={"require_hangul": True, "no_hangul_exceptions": exception})
    check("exception_wrong_source_hash", [record(target_ko=latin)], "FAIL", "NO_HANGUL",
          {"require_hangul": True, "no_hangul_exceptions":
           {"demo:1:text": {"source_sha256": "0" * 64, "target": latin}}})
    check("exception_wrong_target", [record(target_ko=latin + "X")], "FAIL", "NO_HANGUL",
          {"require_hangul": True, "no_hangul_exceptions": exception})
    check("stale_exception", [record()], "FAIL", "UNUSED_NO_HANGUL_EXCEPTION",
          {"require_hangul": True, "no_hangul_exceptions": exception})
    check("character_budget", [record()], "FAIL", "CHAR_LIMIT", {"max_chars": 5})
    check("byte_budget", [record()], "FAIL", "UTF8_BYTE_LIMIT", {"max_bytes": 8})
    check("line_budget", [record()], "FAIL", "LINE_LIMIT", {"max_lines": 1})
    check("baseline_changed_source", [record()],
          "FAIL", "BASELINE_SOURCE_CHANGED", {"baseline": {"demo:1:text": "f" * 64}})
    check("baseline_added_id", [record()],
          "FAIL", "BASELINE_ADDED_ID", {"baseline": {}})
    check("baseline_removed_id", [record()],
          "FAIL", "BASELINE_REMOVED_ID", {"baseline": {"other:1": digest}})
    check("malformed_json", [b"{invalid json\n"], "FAIL", "INVALID_JSON")
    check("invalid_utf8", [b"\xff\n"], "FAIL", "INVALID_UTF8")
    check("utf8_bom", [b"\xef\xbb\xbf" + json.dumps(record()).encode("utf-8")],
          "FAIL", "UTF8_BOM")
    failed = [c for c in results if c["status"] == "FAIL"]
    return {"status": "FAIL" if failed else "PASS", "tests": len(results),
            "passed": len(results) - len(failed), "failed": len(failed), "cases": results}


def save_report(path: Path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", nargs="?", type=Path, help="UTF-8 JSONL (read only)")
    parser.add_argument("--baseline", type=Path, help="Reference JSONL for ID/source stability (read only)")
    parser.add_argument("--report", type=Path, help="Write diagnostics JSON, no game strings")
    parser.add_argument("--id-pattern", default=DEFAULT_ID_PATTERN, help="Full-match regex for stable ID")
    parser.add_argument("--id-field", default="id")
    parser.add_argument("--source-field", default="source_en")
    parser.add_argument("--target-field", default="target_ko")
    parser.add_argument("--hash-field", default="source_sha256")
    parser.add_argument("--source-encoding", default="utf-8", help="Codec for source hash (ASCII works with UTF-8)")
    parser.add_argument("--max-chars", type=int, help="Target Unicode code-point limit")
    parser.add_argument("--max-bytes", type=int, help="Target encoded UTF-8 byte limit")
    parser.add_argument("--max-lines", type=int, help="Target line budget, literal and real newline")
    parser.add_argument("--require-hangul", action="store_true",
                        help="Fail alphabetic targets with no Hangul (not suitable for pure English UI labels)")
    parser.add_argument("--no-hangul-exceptions", type=Path,
                        help="JSONL of reviewed exceptions (ID, source_sha256, exact target, reason)")
    parser.add_argument("--allow-added", action="store_true", help="Allow IDs absent from baseline")
    parser.add_argument("--allow-removed", action="store_true", help="Allow IDs removed since baseline")
    parser.add_argument("--self-test", action="store_true", help="Run synthetic regression tests instead of a catalog")
    args = parser.parse_args(argv)
    for key in ("max_chars", "max_bytes", "max_lines"):
        if getattr(args, key) is not None and getattr(args, key) < 1:
            parser.error("--" + key.replace("_", "-") + " must be positive")
    try:
        if args.self_test:
            report = run_self_tests()
        else:
            if args.catalog is None:
                parser.error("catalog is required unless --self-test is used")
            baseline = (read_baseline(args.baseline, id_field=args.id_field, hash_field=args.hash_field)
                        if args.baseline else None)
            exceptions = (read_no_hangul_exceptions(args.no_hangul_exceptions)
                          if args.no_hangul_exceptions else None)
            with args.catalog.open("rb") as stream:
                report = validate_lines(
                    stream, id_pattern=args.id_pattern,
                    id_field=args.id_field, source_field=args.source_field,
                    target_field=args.target_field, hash_field=args.hash_field,
                    source_encoding=args.source_encoding,
                    max_chars=args.max_chars, max_bytes=args.max_bytes,
                    max_lines=args.max_lines, require_hangul=args.require_hangul,
                    baseline=baseline, allow_added=args.allow_added,
                    allow_removed=args.allow_removed,
                    no_hangul_exceptions=exceptions)
            report["catalog_path"] = str(args.catalog.resolve())
            report["baseline_path"] = str(args.baseline.resolve()) if args.baseline else None
            report["no_hangul_exceptions_path"] = (str(args.no_hangul_exceptions.resolve())
                                                   if args.no_hangul_exceptions else None)
            report["limits"] = {"max_chars": args.max_chars, "max_bytes": args.max_bytes,
                                "max_lines": args.max_lines, "require_hangul": args.require_hangul}
        if args.report is not None:
            save_report(args.report, report)
    except (OSError, UnicodeError, ValueError, re.error) as exc:
        print("FAIL setup/io: %s" % (type(exc).__name__,), file=sys.stderr)
        return 2
    if args.self_test:
        print("%s synthetic: %d/%d passed" %
              (report["status"], report["passed"], report["tests"]))
        for item in report["cases"]:
            print("  %s %s" % (item["status"], item["name"]))
    else:
        print("%s catalog: rows=%d translated=%d untranslated=%d errors=%d warnings=%d" %
              (report["status"], report["rows"], report["translated"],
               report["untranslated"], report["errors"], report["warnings"]))
        for code, count in report["error_codes"].items():
            print("  FAIL %s=%d" % (code, count))
        for code, count in report["warning_codes"].items():
            print("  WARN %s=%d" % (code, count))
        print("  ID stability: %s" % report["id_stability"])
    if args.report:
        print("  Report: %s" % args.report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
