"""Every sourcebook the shipped content draws on, counted.

Section 6 of the Open Game Licence requires the COPYRIGHT NOTICE in section 15 to carry
"the exact text of the COPYRIGHT NOTICE of any Open Game Content You are copying, modifying
or distributing". That is a per-book obligation, and this app's content came in as bulk
spreadsheet and PDF imports that each span dozens of books — so the list cannot be written
from memory and cannot be checked by eye.

    python tools/ogl_sources.py            # summary
    python tools/ogl_sources.py --full     # every source, for pasting into the notice

Run it after any content import. A source that appears here and not in `OGL-NOTICE.md` is
an attribution the build owes and does not have.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Where content lives, and which key holds the list of records. Kept explicit rather than
# discovered, so a new content file has to be added here deliberately — silently missing
# one is exactly the failure this tool exists to prevent.
FILES = [
    ("content/spells/spells.json", "spells"),
    ("content/bestiary/creatures.json", "creatures"),
    ("content/bestiary/core.json", "creatures"),
    ("content/feats/feats.json", "feats"),
    ("content/weapons/weapons.json", "weapons"),
    ("content/ingredients/herbs-and-parts.json", "ingredients"),
]


def sources() -> dict[str, collections.Counter]:
    out: dict[str, collections.Counter] = {}
    for rel, key in FILES:
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  ! {rel}: unreadable ({exc})")
            continue
        rows = data.get(key) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            rows = []
        tally = collections.Counter()
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("source") or "").strip()
            tally[name or "(no source recorded)"] += 1
        out[rel] = tally
    return out


def main() -> int:
    full = "--full" in sys.argv
    per_file = sources()

    everything: collections.Counter = collections.Counter()
    print("Open Game Content by file:\n")
    for rel, tally in per_file.items():
        total = sum(tally.values())
        print(f"  {rel:44} {total:6} entries, {len(tally):4} sources")
        everything.update(tally)

    print(f"\n  {'TOTAL':44} {sum(everything.values()):6} entries, "
          f"{len(everything):4} distinct sources")

    missing = everything.get("(no source recorded)", 0)
    if missing:
        print(f"\n  {missing} entries record no source at all — those cannot be attributed "
              f"and should not ship.")

    print("\nTop sources:")
    for name, n in everything.most_common(15 if not full else len(everything)):
        print(f"  {n:6}  {name}")

    if not full:
        print(f"\n  ({len(everything) - 15} more; run with --full for all of them.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
