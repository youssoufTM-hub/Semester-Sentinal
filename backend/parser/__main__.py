"""CLI: python -m parser file.pdf [file2.docx ...] --term-start YYYY-MM-DD --term-end YYYY-MM-DD"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .syllabus_parser import ParserError, SyllabusInput, SyllabusParser
from .convert import to_event_inputs, to_review_rows
from .models import TermBreak, TermContext
from .providers import PROVIDERS, ProviderError, get_provider


def term_from_args(args) -> TermContext | None:
    breaks = []
    for raw in args.breaks:
        name, start, end = raw.rsplit(":", 2)
        breaks.append(TermBreak(name=name, start=start, end=end))
    if args.term_start or args.term_end or args.term_name or breaks:
        return TermContext(term_name=args.term_name, start=args.term_start, end=args.term_end, breaks=breaks)
    return None


def add_common_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--provider", choices=PROVIDERS, help="default: $PARSER_PROVIDER or gemini")
    ap.add_argument("--model", help="default: $PARSER_MODEL or the provider's default")
    ap.add_argument("--term-name")
    ap.add_argument("--term-start", help="YYYY-MM-DD first day of classes")
    ap.add_argument("--term-end", help="YYYY-MM-DD last day of exams")
    ap.add_argument("--break", dest="breaks", action="append", default=[],
                    help="NAME:YYYY-MM-DD:YYYY-MM-DD (repeatable)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m parser", description="Parse syllabi and print JSON.")
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--name", action="append", default=[], help="course name per file, in order")
    ap.add_argument("--events", action="store_true", help="also print heatmap events")
    add_common_args(ap)
    args = ap.parse_args(argv)

    try:
        parser = SyllabusParser(get_provider(args.provider, args.model))
    except (ProviderError, ParserError) as err:
        print(err, file=sys.stderr)
        return 2
    term = term_from_args(args)

    inputs = [
        SyllabusInput(data=path.read_bytes(), filename=path.name,
                      course_hint=args.name[i] if i < len(args.name) else None)
        for i, path in enumerate(args.files)
    ]
    outcomes = parser.parse_many(inputs, term)
    parsed, failed = [], False
    for path, outcome in zip(args.files, outcomes):
        if isinstance(outcome, ParserError):
            print(f"{path.name}: {outcome}", file=sys.stderr)
            failed = True
        else:
            parsed.append(outcome)

    out = {"courses": [r.model_dump() for r in parsed], "review_rows": to_review_rows(parsed)}
    if args.events:
        out["events"] = to_event_inputs(parsed, term)
    json.dump(out, sys.stdout, indent=2)
    print()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
