"""Score judge runs against the frozen ruling set (ruling-set.json).

    python -m tools.ruling_bench.score <run.jsonl> [<run.jsonl> ...] [--lines]

Per arm and per split, over the majority ruling of its runs per line:
* VERDICT agreement (say_yes / roll / refuse) with a bootstrap 95% interval;
* the error kinds, each as a share of the lines it could happen on:
  LENIENT  the key refuses, the judge allows (CoC-Seduce's measured failure);
  STRICT   the key allows, the judge refuses;
  MISSED   the key rolls, the judge says yes;
  NEEDLESS the key says yes, the judge rolls;
  REASON   both refuse, for a different reason;
* agreement by the line's hidden kind and by who wrote the key's ruling;
* the oracle (shot in the dark) caught; median model and wall seconds per line.
--lines prints every disagreement, for reading.
--recombine re-derives each checklist ruling from the model's stored answers with the
CURRENT closed.combine, so a change to the combiner is measured on the very same answers
without asking the model again.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

SET = Path(__file__).resolve().parent / "ruling-set.json"


def majority(rulings: list[dict]) -> dict:
    top = Counter(r.get("verdict") for r in rulings).most_common(1)[0][0]
    pool = [r for r in rulings if r.get("verdict") == top]
    forms = Counter(json.dumps({k: v for k, v in r.items() if k != "why"}, sort_keys=True)
                    for r in pool)
    return json.loads(forms.most_common(1)[0][0])


def ci(hits: list[int], n_boot: int = 2000, seed: int = 7) -> tuple[float, float]:
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(hits) for _ in hits) / len(hits) for _ in range(n_boot))
    return means[int(0.025 * n_boot)], means[int(0.975 * n_boot)]


def pct(hits: list[int]) -> str:
    if not hits:
        return "  n/a"
    lo, hi = ci(hits)
    return f"{100 * sum(hits) / len(hits):5.1f}% [{100 * lo:.0f}-{100 * hi:.0f}] n={len(hits)}"


def score(lines: dict, rows: list[dict], show: bool = False) -> str:
    by_line, secs, wall, broken = defaultdict(list), [], [], 0
    for r in rows:
        if r["id"] not in lines:
            continue
        if not (r.get("ruling") or {}).get("verdict"):
            broken += 1
            continue
        by_line[r["id"]].append(r["ruling"])
        secs.append(r.get("seconds", 0))
        wall.append(r.get("wall", r.get("seconds", 0)))
    out = []
    for split in sorted({lines[i]["split"] for i in by_line}):
        agree, lenient, strict, missed, needless, reason, oracle = [], [], [], [], [], [], []
        by_kind, by_author, bad = defaultdict(list), defaultdict(list), []
        for lid, rulings in by_line.items():
            k = lines[lid]
            if k["split"] != split:
                continue
            j = majority(rulings)
            kv, jv = k["verdict"], j.get("verdict")
            hit = int(kv == jv)
            agree.append(hit)
            by_kind[k["kind"]].append(hit)
            by_author[k["author"]].append(hit)
            if kv == "refuse":
                lenient.append(int(jv != "refuse"))
            else:
                strict.append(int(jv == "refuse"))
            if kv == "roll":
                missed.append(int(jv == "say_yes"))
            if kv == "say_yes":
                needless.append(int(jv == "roll"))
            if kv == jv == "refuse":
                reason.append(int(k["refuse"] != j.get("refuse")))
            if (k.get("roll") or {}).get("what") == "oracle":
                oracle.append(int(j.get("what") == "oracle"))
            if not hit:
                bad.append(f"    {lid:6s} key {kv:7s} {k.get('refuse') or (k.get('roll') or {}).get('what') or '':16s}"
                           f" judge {jv:7s} {j.get('refuse') or ''}  | {k['text'][:90]}")
        out += [f"  [{split}] VERDICT {pct(agree)}",
                f"    lenient {pct(lenient)}   strict {pct(strict)}",
                f"    missed roll {pct(missed)}   needless roll {pct(needless)}",
                f"    refuse reason differs {pct(reason)}   oracle caught {pct(oracle)}",
                "    by kind: " + ", ".join(f"{kd} {100 * sum(h) / len(h):.0f}% ({len(h)})"
                                            for kd, h in sorted(by_kind.items())),
                "    by author: " + ", ".join(f"{au} {100 * sum(h) / len(h):.0f}% ({len(h)})"
                                              for au, h in sorted(by_author.items()))]
        if show:
            out += bad
    head = (f"  lines {len(by_line)}, broken {broken}, median model s "
            f"{statistics.median(secs):.1f}, median wall s {statistics.median(wall):.1f}, "
            f"total wall min {sum(wall) / 60:.1f}" if secs else "  no rulings")
    return "\n".join([head] + out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--lines", action="store_true")
    ap.add_argument("--recombine", action="store_true")
    a = ap.parse_args(argv)
    lines = {l["id"]: l for l in json.loads(SET.read_text(encoding="utf-8"))["lines"]}
    for path in a.runs:
        rows = [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines()
                if x.strip()]
        if a.recombine:
            from . import closed
            for r in rows:
                if r.get("arm") == "checklist" and r.get("raw"):
                    r["ruling"] = closed.combine(r["raw"])
        print(f"=== {Path(path).name}")
        print(score(lines, rows, a.lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
