"""Compile every shipped printed stat block into content/bestiary/compiled.json.

docs/compiled-bestiary-plan.md: the parser runs here, once, when content comes in — never
at play. Play reads the record (`compile_block.record_for`) and falls back to reading the
print live only for what has none: a homebrew creature, a templated one, one of the app's
own rules-built people (whose numbers are a sheet, not a print).

Run after anything that changes a printed block's attack or gear lines (the PDF re-read,
tools/ship_rulebook_line.py, the list repair):

    python tools/compile_bestiary.py            # write the records and print the counts
    python tools/compile_bestiary.py --check    # exit 1 if a record is missing or stale

tests/test_compiled_bestiary.py refuses a stale or missing record and holds the unread
counts as a ratchet.
"""
from __future__ import annotations

import collections
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from rules import bestiary, compile_block  # noqa: E402

OUT = ROOT / "content" / "bestiary" / "compiled.json"


def shipped() -> dict[str, dict]:
    """Every printed block the app ships: the two bestiary files, read and merged, with
    no homebrew, no templated creatures and no built people."""
    return bestiary._build_imported(printed_only=True)


def build() -> dict:
    records = {bid: compile_block.compile_block(b) for bid, b in sorted(shipped().items())}
    return {
        "compiler": compile_block.COMPILER,
        "note": ("Each shipped stat block's attacks and possessions, compiled once by "
                 "tools/compile_bestiary.py (rules/compile_block.py). A record whose "
                 "source_hash no longer matches its block's lines is never read."),
        "creatures": records,
    }


def counts(doc: dict) -> dict:
    c = collections.Counter()
    for rec in doc["creatures"].values():
        for cat in ("melee", "ranged"):
            for option in rec["attacks"][cat]:
                for a in option:
                    c[f"attack.{a['class']}"] += 1
                    if a["class"] == "item":
                        c["item.linked" if a.get("item") is not None else "item.unlinked"] += 1
        for it in rec["carries"]:
            c[f"carried.{it['table'] or 'unresolved'}"] += 1
        for u in rec["unread"]:
            c[f"unread.{u.split(':', 1)[0]}"] += 1
    return dict(sorted(c.items()))


def main(argv: list[str]) -> int:
    doc = build()
    if "--check" in argv:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        stale = sorted(k for k, v in doc["creatures"].items()
                       if (old.get("creatures") or {}).get(k) != v)
        if stale or old.get("compiler") != doc["compiler"]:
            print(f"{len(stale)} records stale or missing: {stale[:10]}")
            return 1
        return 0
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(doc['creatures'])} records -> {OUT.relative_to(ROOT)}")
    for k, v in counts(doc).items():
        print(f"  {k:24} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
