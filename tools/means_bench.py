"""Measure the means gate (gm/means.py) against the means corpus, and the regex doors
beside it (docs/means-gate.md).

Not a pytest: it needs a live Ollama and takes minutes. Every line is read once by the
real reader (`interpret.interpret`) and judged against the shipped fixture sheets, with
`means.which_power` asked live where no held name was found. The regex doors —
`refuse_unnamed_power`, `refuse_unknown_ability`, `refuse_declared_creation` — are scored
on the same lines, given nothing but `narrate_only` to work on, as
tests/test_psychic_powers.py scores them.

    python tools/means_bench.py                     # the dev corpus
    python tools/means_bench.py --set held          # held-out: counts only, no lines
    python tools/means_bench.py --set psychic       # the regex gate's own 32 + 40
    python tools/means_bench.py --readings r.json   # reuse readings saved by a run
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

SHEETS = {"kesst": "fixtures/pc-kesst.json", "ysolde": "fixtures/pc-caster.json"}


def scene_for(sheet: str):
    from rules.bestiary import instantiate
    from rules.engine import Scene
    from rules.sheet import load_pc
    from tests._places import stand_on

    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    s.add(load_pc(SHEETS[sheet]))
    s.add(instantiate("guildhand", scene=s, name="the merchant"))
    return s


def regex_refuses(line: str, scene) -> bool:
    from gm import judgement

    raw = [{"op": "narrate_only", "because": "x"}]
    for door in (judgement.refuse_unnamed_power, judgement.refuse_unknown_ability,
                 judgement.refuse_declared_creation):
        if door(list(raw), line, scene) != raw:
            return True
    return False


def rows_for(which: str):
    from tests.means import gold

    if which == "dev":
        return gold.DEV
    if which == "held":
        return gold.HELD_OUT
    if which == "psychic":
        from tests import test_psychic_powers as t

        return ([(x, "kesst", gold.REFUSE) for x in t.REACHES_A_MIND]
                + [(x, "kesst", gold.PASS) for x in t.ORDINARY])
    raise SystemExit(f"no set {which!r}")


def main() -> None:
    from gm import interpret, means
    from tests.means.gold import CLAIM, REFUSE

    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev")
    ap.add_argument("--readings", default="")
    ap.add_argument("--save", default="")
    ap.add_argument("--no-ask", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="counts only, no lines")
    args = ap.parse_args()

    rows = rows_for(args.set)
    quiet = args.quiet or args.set == "held"
    cache = {}
    if args.readings and Path(args.readings).exists():
        cache = json.loads(Path(args.readings).read_text(encoding="utf-8"))
    scenes = {k: scene_for(k) for k in SHEETS}
    tally = {"refuse": [0, 0], "pass": [0, 0], "claim": [0, 0], "claim_read": [0, 0]}
    regex = {"refuse": [0, 0], "pass": [0, 0], "claim": [0, 0]}
    both = {"refuse": [0, 0], "pass": [0, 0], "claim": [0, 0]}
    seconds, asks = [], 0
    misses = []
    for line, sheet, expect in rows:
        if line not in cache:
            t0 = time.monotonic()
            cache[line] = interpret.interpret(line)
            seconds.append(time.monotonic() - t0)
        frame = cache[line]
        scene = scenes[sheet]
        ask = None
        if not args.no_ask:
            def ask(sc, deed):
                nonlocal asks
                asks += 1
                return means.which_power(sc, deed)
        judged = means.judge(frame, scene, ask=ask,
                             claim_ask=None if args.no_ask else means.claim_kind)
        refused = any(j.get("refused_name") for j in judged)
        want_refused = expect == REFUSE
        ok = refused == want_refused
        tally[expect][0] += ok
        tally[expect][1] += 1
        by_regex = regex_refuses(line, scene)
        r_ok = by_regex == want_refused
        regex[expect][0] += r_ok
        regex[expect][1] += 1
        # Both doors as the turn runs them: the regex still sits on the path
        # (`refuse_unnamed_power`), so a line either refuses is refused.
        both[expect][0] += (refused or by_regex) == want_refused
        both[expect][1] += 1
        if expect == CLAIM:
            got = bool(frame.get("claims"))
            tally["claim_read"][0] += got
            tally["claim_read"][1] += 1
        if not ok:
            acts = [(a.get("act"), a.get("means", "ordinary"), a.get("power"),
                     a.get("commit", "done")) for a in frame.get("actions") or []]
            misses.append((expect, sheet, line, acts,
                           [j.get("held") or j.get("refused_name") for j in judged]))
    if args.save:
        Path(args.save).write_text(json.dumps(cache, indent=1, ensure_ascii=False),
                                   encoding="utf-8")

    def rate(pair):
        return f"{pair[0]}/{pair[1]}" + (f" ({pair[0] / pair[1]:.3f})" if pair[1] else "")

    print(f"set={args.set} lines={len(rows)} readings this run={len(seconds)} "
          f"which_power asks={asks}")
    if seconds:
        print(f"reader median {statistics.median(seconds):.2f}s max {max(seconds):.2f}s")
    print("means gate: refused when it should  ", rate(tally["refuse"]))
    print("            spared when it should    ", rate(tally["pass"]))
    print("            declared result spared   ", rate(tally["claim"]))
    print("            declared result as claim ", rate(tally["claim_read"]))
    print("regex doors: refused when it should ", rate(regex["refuse"]))
    print("             spared when it should   ", rate(regex["pass"]))
    print("             declared result spared  ", rate(regex["claim"]))
    print("both, as the turn runs them: refused ", rate(both["refuse"]))
    print("             spared when it should   ", rate(both["pass"]))
    print("             declared result spared  ", rate(both["claim"]))
    if misses and not quiet:
        print("\nmisses:")
        for m in misses:
            print("  ", m)


if __name__ == "__main__":
    main()
