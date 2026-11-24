"""Scores parser output against the labelled answers in eval/expected.

    python -m parser.eval <syllabi_dir> --term-start 2026-09-08 --term-end 2026-12-19 --save runs/latest
    python -m parser.eval <syllabi_dir> --from-saved runs/latest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ..__main__ import add_common_args, term_from_args
from ..syllabus_parser import ParserError, SyllabusInput, SyllabusParser, check_result
from ..models import ParseResult, parse_iso_date
from ..providers import ProviderError, get_provider

EXPECTED_DIR = Path(__file__).parent / "expected"


@dataclass
class Score:
    course: str
    expected: int = 0
    found: int = 0
    date_ok: int = 0
    kind_ok: int = 0
    extra_rows: int = 0
    warning_ok: bool | None = None
    misses: list[str] = field(default_factory=list)


def _date_matches(item: dict, due: date | None, needs_review: bool) -> bool:
    if "due_range" in item:
        lo, hi = (date.fromisoformat(x) for x in item["due_range"])
        return (due is not None and lo <= due <= hi) or (due is None and needs_review)
    want = parse_iso_date(item.get("due_date"))
    return want == due


def _distance(item: dict, due: date | None) -> int:
    target = item.get("due_date") or (item.get("due_range") or [None])[0]
    want = parse_iso_date(target)
    if want is None or due is None:
        return 0 if (want is None and due is None) else 10_000
    return abs((want - due).days)


def score(result: ParseResult, spec: dict) -> Score:
    s = Score(course=spec.get("course_code") or result.course.code or "?")
    unused = list(range(len(result.deadlines)))
    for item in spec["items"]:
        s.expected += 1
        pattern = re.compile(item["match"], re.IGNORECASE)
        candidates = [
            i for i in unused
            if pattern.search(f"{result.deadlines[i].title} {result.deadlines[i].raw_label}")
        ]
        if not candidates:
            s.misses.append(f"missing: {item['title']}")
            continue
        best = min(candidates, key=lambda i: _distance(item, parse_iso_date(result.deadlines[i].due_date)))
        unused.remove(best)
        d = result.deadlines[best]
        s.found += 1
        if _date_matches(item, parse_iso_date(d.due_date), d.needs_review):
            s.date_ok += 1
        else:
            want = item.get("due_date") or item.get("due_range")
            s.misses.append(f"date: {item['title']} expected {want}, got {d.due_date}")
        if d.kind in item["kind"]:
            s.kind_ok += 1
        else:
            s.misses.append(f"type: {item['title']} expected {item['kind']}, got {d.kind}")
    s.extra_rows = len(unused)
    if spec.get("expect_warning_about"):
        text = " ".join(result.warnings).lower()
        s.warning_ok = all(word in text for word in spec["expect_warning_about"])
    return s


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "n/a"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m parser.eval", description="Score the parser on labelled syllabi.")
    ap.add_argument("syllabi_dir", type=Path)
    ap.add_argument("--expected", type=Path, default=EXPECTED_DIR)
    ap.add_argument("--save", type=Path, help="write each ParseResult here as JSON")
    ap.add_argument("--from-saved", type=Path, help="score JSON saved by --save instead of calling the API")
    add_common_args(ap)
    args = ap.parse_args(argv)
    term = term_from_args(args)

    specs = [json.loads(p.read_text(encoding="utf-8")) | {"_name": p.stem}
             for p in sorted(args.expected.glob("*.json"))]
    files = [p for p in args.syllabi_dir.iterdir() if p.is_file()]

    parser = None
    if not args.from_saved:
        try:
            parser = SyllabusParser(get_provider(args.provider, args.model))
        except (ProviderError, ParserError) as err:
            print(err, file=sys.stderr)
            return 2
        print(f"provider: {parser.provider.name} / {parser.provider.model}\n")
    if args.save:
        args.save.mkdir(parents=True, exist_ok=True)

    scores: list[Score] = []
    for spec in specs:
        if args.from_saved:
            saved = args.from_saved / f"{spec['_name']}.json"
            if not saved.exists():
                print(f"{spec['_name']}: no saved output", file=sys.stderr)
                continue
            result = check_result(ParseResult.model_validate_json(saved.read_text(encoding="utf-8")), term)
        else:
            match = next((p for p in files if spec["file_contains"].lower() in p.name.lower()), None)
            if match is None:
                print(f"{spec['_name']}: no file containing '{spec['file_contains']}'", file=sys.stderr)
                continue
            try:
                result = parser.parse(SyllabusInput(match.read_bytes(), filename=match.name), term)
            except ParserError as err:
                print(f"{match.name}: {err}", file=sys.stderr)
                scores.append(Score(course=spec.get("course_code", "?"), expected=len(spec["items"]),
                                    misses=[f"parse failed: {err}"]))
                continue
            if args.save:
                (args.save / f"{spec['_name']}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        scores.append(score(result, spec))

    print(f"{'course':<12} {'found':>9} {'date':>9} {'type':>9} {'extra':>6}  warning")
    for s in scores:
        warn = "" if s.warning_ok is None else ("ok" if s.warning_ok else "MISSED")
        print(f"{s.course:<12} {s.found:>3}/{s.expected:<5} {s.date_ok:>3}/{s.found:<5} {s.kind_ok:>3}/{s.found:<5}"
              f" {s.extra_rows:>6}  {warn}")
        for m in s.misses:
            print(f"    - {m}")

    exp = sum(s.expected for s in scores)
    found = sum(s.found for s in scores)
    print("\n| Measure | Result |\n|---------|--------|")
    print(f"| Deadlines found | {pct(found, exp)} ({found}/{exp}) |")
    print(f"| Correct date | {pct(sum(s.date_ok for s in scores), found)} |")
    print(f"| Correct type | {pct(sum(s.kind_ok for s in scores), found)} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
