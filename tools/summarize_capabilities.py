#!/usr/bin/env python3
"""Summarize Kidde capability combinations from node server logs.

Parses log lines emitted by nodes.py:
  Discovered Kidde device_id=... model=... caps=... -> smoke=... co=... iaq=... nodedef=...

Usage:
  python tools/summarize_capabilities.py path/to/logfile.log
  python tools/summarize_capabilities.py path/to/logfile.log --tail 2000
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

DISCOVERY_RE = re.compile(
    r"Discovered Kidde device_id=(?P<device_id>\d+) "
    r"model=(?P<model>.*?) "
    r"caps=(?P<caps>.*?) -> "
    r"smoke=(?P<smoke>True|False) "
    r"co=(?P<co>True|False) "
    r"iaq=(?P<iaq>True|False) "
    r"nodedef=(?P<nodedef>[A-Za-z0-9_\-]+)"
)


def _to_bool(text: str) -> bool:
    return str(text).strip() == "True"


def parse_lines(lines: list[str]) -> tuple[Counter, Counter, Counter, Counter]:
    by_combo = Counter()
    by_nodedef = Counter()
    by_model = Counter()
    by_caps_raw = Counter()

    for line in lines:
        match = DISCOVERY_RE.search(line)
        if not match:
            continue

        smoke = _to_bool(match.group("smoke"))
        co = _to_bool(match.group("co"))
        iaq = _to_bool(match.group("iaq"))
        nodedef = match.group("nodedef")
        model = (match.group("model") or "").strip() or "<unknown>"
        caps_raw = (match.group("caps") or "").strip() or "<empty>"

        combo = f"smoke={int(smoke)} co={int(co)} iaq={int(iaq)}"
        by_combo[combo] += 1
        by_nodedef[nodedef] += 1
        by_model[model] += 1
        by_caps_raw[caps_raw] += 1

    return by_combo, by_nodedef, by_model, by_caps_raw


def _print_counter(title: str, counter: Counter) -> None:
    print(f"\n{title}")
    if not counter:
        print("  (no matches)")
        return

    width = max(len(key) for key in counter)
    for key, count in counter.most_common():
        print(f"  {key.ljust(width)}  {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Kidde capability combinations from logs")
    parser.add_argument("logfile", help="Path to PG3/node server log file")
    parser.add_argument(
        "--tail",
        type=int,
        default=0,
        help="Only parse the last N lines (0 = parse entire file)",
    )
    args = parser.parse_args()

    log_path = Path(args.logfile)
    if not log_path.exists() or not log_path.is_file():
        print(f"Log file not found: {log_path}")
        return 2

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if args.tail and args.tail > 0:
        lines = lines[-args.tail :]

    by_combo, by_nodedef, by_model, by_caps_raw = parse_lines(lines)

    print(f"Parsed {len(lines)} line(s) from {log_path}")
    _print_counter("Capability combos", by_combo)
    _print_counter("Nodedef usage", by_nodedef)
    _print_counter("Model usage", by_model)
    _print_counter("Raw capabilities values", by_caps_raw)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
