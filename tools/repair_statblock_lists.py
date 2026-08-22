"""Cut the spilled page text out of the shipped bestiary's comma-split fields.

`rules/statblock.py` holds the rule and says why. This applies it to a file, in place, and
prints what it removed so the removal can be argued with.

The extractor is fixed as well, but it cannot be re-run: the parse needs the six Bestiary
PDFs and only the extracted index of them is in the repository. So the shipped file is
repaired directly, and `tools/extract_bestiary_pdfs.py` calls the same function so a future
run against the PDFs produces the repaired shape rather than this one again.

Run:  python tools/repair_statblock_lists.py content/bestiary/core.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rules.statblock import RESISTANCE, scrub, trim  # noqa: E402

# Only the three fields that split on commas. Every other stat-block field is capped by a
# slice at the point of extraction, so a runaway there is one long wrong string — visible.
# These three turned the same runaway into a list of short plausible ones, which is not.
FIELDS = {"immune": None, "resist": RESISTANCE, "languages": None}


def repair(rows) -> dict:
    counts = {f: {"before": 0, "after": 0, "emptied": 0, "rows": 0} for f in FIELDS}
    counts["watermark"] = {"before": 0, "after": 0, "emptied": 0, "rows": 0}
    for row in rows:
        # Every string field, not the three below: a capped field cannot run away but the
        # watermark still lands inside the cap, and it turned up in `treasure` after the
        # three list fields were clean.
        for key, value in list(row.items()):
            if isinstance(value, str) and (cleaned := scrub(value)) != value:
                row[key] = cleaned
                counts["watermark"]["before"] += 1
        for field, shape in FIELDS.items():
            was = row.get(field) or []
            if not was:
                continue
            now = trim(was, shape=shape)
            c = counts[field]
            c["before"] += len(was)
            c["after"] += len(now)
            c["rows"] += 1
            if not now:
                c["emptied"] += 1
            row[field] = now
    return counts


def main() -> int:
    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("creatures") if isinstance(data, dict) else data
    if isinstance(rows, dict):
        rows = list(rows.values())

    counts = repair(rows)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

    for field, c in counts.items():
        if field == "watermark":
            print(f"  {field:<10} {c['before']} prose fields had the store stamp "
                  f"(and a purchaser's email address) cut out")
            continue
        print(f"  {field:<10} {c['before']:>5} -> {c['after']:>5} terms across "
              f"{c['rows']} creatures; {c['emptied']} left with nothing")
    # Named separately because it is the uncomfortable half: a list that becomes empty was
    # not carrying a damaged fact, it was carrying no fact at all. Those creatures never had
    # their immunities extracted — the parser matched the word "immune" in their flavour
    # text — and the file looked populated for them. Empty is the honest state, and it is
    # also a gap somebody has to fill from the book.
    print("  (an emptied list means that creature's real line was never captured, "
          "not that it was captured and thrown away)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
