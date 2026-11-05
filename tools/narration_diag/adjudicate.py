"""A third scorer for the beats two blind scorers disagree on.

    python tools/narration_diag/adjudicate.py sheet <sheets_dir> <out_dir> <size> \\
        <scoreA,...> <scoreB,...>
    python tools/narration_diag/adjudicate.py merge <scoreA,...> <scoreB,...> \\
        <scoreC,...> <final.txt>

`sheet` finds every item whose error count (E codes) differs between A and B and writes
those items, as the scorers saw them and under the same ids, to new sheets for a third
scorer, who is shown neither A's nor B's answer. `merge` writes one score file: the third
scorer's lines for a disputed item, scorer A's for every other (A and B agreed on its
count). The prose rating is A's and B's mean, rounded.

Why: on the first rerun the two scorers agreed on 572 of 602 beats (kappa 0.77) and their
counts differed by about 12%; reported side by side, a reader cannot tell which to
believe on the beats that decide the verdict. A third read of only those beats settles
each one the same way a panel would, at a fraction of a third full pass."""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path


def _lines(paths: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for p in paths.split(","):
        for line in open(p, encoding="utf-8"):
            line = line.strip().strip("`")
            m = re.match(r"(D\d{4})\s*\|", line)
            if m:
                out[m.group(1)].append(line)
    return out


def _errors(lines: list[str]) -> int:
    return sum(1 for x in lines if re.match(r"D\d{4}\s*\|\s*E\d", x))


def disputed(a: dict, b: dict) -> list[str]:
    return sorted(d for d in set(a) | set(b) if _errors(a.get(d, [])) != _errors(b.get(d, [])))


def sheet(argv: list[str]) -> None:
    sheets, out, size = Path(argv[0]), Path(argv[1]), int(argv[2])
    a, b = _lines(argv[3]), _lines(argv[4])
    want = set(disputed(a, b))
    items = []
    for f in sorted(sheets.glob("chunk-*.txt")):
        for block in re.split(r"(?m)^(?===================== D\d{4})",
                              f.read_text(encoding="utf-8")):
            m = re.match(r"==================== (D\d{4})", block)
            if m and m.group(1) in want:
                items.append(block.strip())
    out.mkdir(parents=True, exist_ok=True)
    for k in range(0, len(items), size):
        (out / f"chunk-{k // size + 1:02d}.txt").write_text("\n\n".join(items[k:k + size])
                                                           + "\n", encoding="utf-8")
    rubric = sheets / "rubric.md"
    if rubric.exists():
        (out / "rubric.md").write_text(rubric.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"{len(want)} disputed items, {len(items)} written in "
          f"{(len(items) + size - 1) // size} sheets")


def merge(argv: list[str]) -> None:
    a, b, c, final = _lines(argv[0]), _lines(argv[1]), _lines(argv[2]), argv[3]
    dis = set(disputed(a, b))
    missing = [d for d in dis if d not in c]
    out = []
    for d in sorted(set(a) | set(b)):
        src = c[d] if d in dis and d in c else a.get(d) or b.get(d) or []
        lines = [x for x in src if not re.match(r"D\d{4}\s*\|\s*P\s*\|", x)]
        out += lines or [f"{d} | none"]
        rates = []
        for s in (a, b):
            for x in s.get(d, []):
                m = re.match(r"D\d{4}\s*\|\s*P\s*\|\s*(\d)", x)
                if m:
                    rates.append(int(m.group(1)))
        if rates:
            out.append(f"{d} | P | {round(sum(rates) / len(rates))} | mean of A and B")
    Path(final).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(dis)} disputed, {len(dis) - len(missing)} adjudicated"
          + (f"; NOT adjudicated (A's lines kept): {missing}" if missing else ""))


if __name__ == "__main__":
    {"sheet": sheet, "merge": merge}[sys.argv[1]](sys.argv[2:])
