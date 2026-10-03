"""Measure the round-trip check (gm/beat_verify.py) on the labelled beats, against the
regex checks it would replace.

    python tools/beat_verify_bench.py --model igorls/gemma-4-12B-it-heretic-GGUF:latest
    python tools/beat_verify_bench.py --model Osmosis/Osmosis-Structure-0.6B:latest --runs 3
    python tools/beat_verify_bench.py --regex-only

For each beat in tests/beat_verify/gold.py: the reader's validated claims are scored per
category against the hand labels (precision, recall), the code diff's alarms against the
labelled alarms (precision, recall, and the beat-level false-alarm rate on the clean beats
— the number that matters most, because a false alarm cuts a good sentence), and the
regex checks are run over the same beat for the same categories. Latency is per call and
includes whatever else the shared Ollama was doing (docs/beat-verify.md notes the lanes
running beside this one).

`--record out.json` keeps every raw reply, so tests/test_beat_verify.py can replay the
model's actual answers without a model.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gm import beat_verify as bv  # noqa: E402
from tests.beat_verify import gold as G  # noqa: E402

CATS = ("move", "hands", "trade", "harm", "arrived", "left", "hour")
ALARM_CATS = ("move", "hands", "trade", "harm", "presence", "hour", "omission")


# --- the engine's side, as the game builds it ---------------------------------------------

def _places(beat) -> tuple[str, ...]:
    return G.places_of(beat)


def facts_of(beat) -> bv.Facts:
    return G.facts(beat)


# --- scoring --------------------------------------------------------------------------------

def _fits(want, got) -> bool:
    if isinstance(want, list):
        return any(_fits(w, got) for w in want)
    return want == got


def _match(gold: dict, claim: bv.Claim) -> bool:
    if gold["cat"] != claim.category:
        return False
    for k, v in gold.items():
        if k in ("cat", "opt"):
            continue
        if not _fits(v, claim.slots.get(k)):
            return False
    return True


def score_claims(beat, claims: list[bv.Claim], tally) -> list[str]:
    """Greedy one-to-one matching; returns notes on the misses."""
    notes = []
    golds = list(beat["claims"])
    used = set()
    for c in claims:
        hit = next((i for i, g in enumerate(golds) if i not in used and _match(g, c)), None)
        if hit is None:
            tally[c.category]["fp"] += 1
            notes.append(f"FP {c.category} {c.slots} {c.quote[:60]!r}")
            continue
        used.add(hit)
        if not golds[hit].get("opt"):
            tally[c.category]["tp"] += 1
    for i, g in enumerate(golds):
        if i not in used and not g.get("opt"):
            tally[g["cat"]]["fn"] += 1
            notes.append(f"FN {g}")
    return notes


def alarms_of(found: list[bv.Discrepancy]) -> set[str]:
    return {("omission" if d.kind == "omission" else d.category) for d in found}


def score_alarms(beat, got: set[str], tally, beats) -> list[str]:
    want = set(beat["alarms"])
    may = set(beat["may_alarm"])
    notes = []
    for a in got:
        if a in want:
            tally[a]["tp"] += 1
        elif a not in may:
            tally[a]["fp"] += 1
            notes.append(f"FALSE ALARM {a}")
    for a in want - got:
        tally[a]["fn"] += 1
        notes.append(f"MISSED ALARM {a}")
    clean = not want
    beats["clean" if clean else "bad"] += 1
    if clean and (got - may):
        beats["clean_alarmed"] += 1
    if not clean and want <= got:
        beats["bad_all_caught"] += 1
    return notes


def prf(t) -> str:
    tp, fp, fn = t["tp"], t["fp"], t["fn"]
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    return f"P {p:.2f} R {r:.2f} (tp {tp} fp {fp} fn {fn})"


# --- the regex checks on the same beats ------------------------------------------------------

REGEX = {"refused_move": "move", "road_claimed": "move", "thing_kept": "hands",
         "trade_claimed": "trade", "time_of_day": "hour", "empty_roll": "harm",
         "absent_person": "presence"}


class _Actor(SimpleNamespace):
    def has_state(self, tag: str) -> bool:
        return False


def regex_ctx(beat):
    from gm.checks import BeatContext
    from rules.places import Place

    world = "v" if beat["world"] == "VM" else "x"
    kinds = G.ZH_KINDS if beat["world"] == "ZH" else {}

    def slug(name):
        return name.removeprefix("the ").replace(" ", "-")

    places = []
    by_name = {}
    for n in _places(beat):
        kind, parent = kinds.get(n, ("", ""))
        pid = f"{world}~urban:{slug(parent)}/{slug(n)}" if parent else f"{world}~urban:{slug(n)}"
        p = Place(id=pid, name=n, kind=kind)
        places.append(p)
        by_name[n] = p
    end, start = by_name[beat["end"]], by_name[beat["start"]]
    actors = {}
    for p in beat["people"]:
        pc = bool(p[3]) if len(p) > 3 else False
        actors[p[0]] = _Actor(ref=p[0], name=p[1], is_pc=pc, from_template="", race=p[2],
                              true_name="", hp=10, hp_max=10,
                              is_down=len(p) > 4 and p[4] in ("down", "dead"),
                              world_entity_id="", abilities={},
                              goods={g: 1 for g in beat["pack"]} if pc else {},
                              at=end.id)
    pc = next((a for a in actors.values() if a.is_pc), None)
    scene = SimpleNamespace(
        at=end.id, actors=actors, people=actors, pc=lambda: pc,
        clock_minutes=beat["clock"], in_encounter=False, said=[], props=[],
        props_here=lambda: [{"name": n} for n in beat["props"]], founded=[])
    engine = SimpleNamespace(here=lambda: end, places=lambda: tuple(places),
                             open_ground=lambda: (), talking_to=lambda: [], scene=scene)
    return BeatContext(
        door="turn", text=beat["text"], player_text=beat["player"], engine=engine,
        scene=scene, world=None, location=None, reading=beat["reading"] or None,
        outcomes=tuple(beat["outcomes"]), tells=tuple(o.get("tell", "") for o in beat["outcomes"]),
        said=(), attribution=None, brief="", brief_facts={}, pull=None, was_at=start.id,
        acting="", turn=1)


def regex_alarms(beat) -> tuple[set[str], list[str]]:
    import importlib

    ctx = regex_ctx(beat)
    got, errors = set(), []
    for name, cat in REGEX.items():
        try:
            mod = importlib.import_module(f"gm.checks.{name}")
        except ImportError:
            continue                  # retired
        try:
            if mod.find(ctx):
                got.add(cat)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    # And the review's state reader, `contradicts-the-engine` (not a registry member; it
    # runs inside `polish`) — the reader that took "The clerk's eyes drop to the floor"
    # for a man down.
    from gm.narration import contradicts_state

    # As `GMAgent._live_state` builds it: alive is conscious, hurt is below full.
    harmed = {e.get("ref") for o in beat["outcomes"] for e in o.get("effects") or ()
              if e.get("kind") in ("damage", "condition")}
    state = {}
    for p in beat["people"]:
        if len(p) > 3 and p[3]:
            continue
        down = len(p) > 4 and p[4] in ("down", "dead")
        state[p[1]] = {"alive": not down, "hurt": down or p[0] in harmed}
    try:
        if contradicts_state(beat["text"], state):
            got.add("harm(review)")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"contradicts_state: {exc}")
    return got, errors


# --- the run ----------------------------------------------------------------------------------

def beats_of(subset: str) -> list[dict]:
    """"tuned": the beats the prompt, the quote rules and the questions were shaped on;
    "held": the beats labelled before any run and never looked at while shaping."""
    held = [b for b in G.GOLD if "held out" in b["source"]]
    if subset == "held":
        return held
    if subset == "tuned":
        return [b for b in G.GOLD if b not in held]
    return list(G.GOLD)


def run_model(model: str, runs: int, host: str, record: dict, verbose: bool,
              confirm: bool = True, subset: str = "all", replay: dict | None = None) -> dict:
    from gm import client

    claim_t = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    raw_t = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    alarm_t = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    beats = defaultdict(int)
    first_t = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    first_beats = defaultdict(int)
    confirm_secs: list[float] = []
    secs, errors, dropped = [], 0, 0
    gold = beats_of(subset)
    for r in range(runs):
        for beat in gold:
            facts = facts_of(beat)
            chat = client.chat
            if replay is not None:
                kept = (replay.get(beat["id"]) or [{}])[r % max(1, len(replay.get(beat["id"]) or [1]))]

                def chat(*a, _raw=kept.get("raw", ""), **k):
                    return SimpleNamespace(text=_raw, seconds=0.0, model="replay",
                                           json=lambda: json.loads(_raw))
            reading = bv.read(beat["text"], facts, model=model, host=host, chat=chat)
            record.setdefault(beat["id"], []).append(
                {"model": model, "raw": reading.raw, "seconds": reading.seconds,
                 "error": reading.error})
            if reading.error:
                errors += 1
                print(f"[{model[:20]}] {beat['id']}: ERROR {reading.error}")
                continue
            secs.append(reading.seconds)
            dropped += len(reading.dropped)
            notes = score_claims(beat, reading.claims, claim_t)
            # What the quote check bought: the same scoring over every claim, unvalidated.
            score_claims(beat, [c for c in reading.claims + reading.dropped
                                if not c.why.startswith("not the engine")], raw_t)
            found = bv.diff(reading.claims, facts, beat["text"])
            # Before the second read: what the extraction and the diff alone would raise.
            score_alarms(beat, alarms_of(found), first_t, first_beats)
            if confirm:
                found, refuted, s2 = bv.confirm(found, beat["text"], facts, model=model,
                                                host=host, chat=client.chat)
                confirm_secs.append(s2)
                for d in refuted:
                    notes.append(f"refuted {d.category}: {d.sentence[:60]!r}")
            notes += score_alarms(beat, alarms_of(found), alarm_t, beats)
            if verbose and notes:
                print(f"[{model[:20]}] {beat['id']}: " + " | ".join(notes))
                for d in reading.dropped:
                    print(f"      dropped {d.category} {d.slots} {d.quote[:70]!r}: {d.why}")
    return {"claims": claim_t, "raw": raw_t, "alarms": alarm_t, "beats": dict(beats),
            "first": {"alarms": first_t, "beats": dict(first_beats)},
            "confirm_seconds": confirm_secs,
            "seconds": secs, "errors": errors, "dropped": dropped,
            "calls": runs * len(gold)}


def run_regex(verbose: bool, subset: str = "all") -> dict:
    alarm_t = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    beats = defaultdict(int)
    errs = []
    for beat in beats_of(subset):
        got, errors = regex_alarms(beat)
        errs += [f"{beat['id']}: {e}" for e in errors]
        mapped = {("harm" if a == "harm(review)" else a) for a in got}
        notes = score_alarms(beat, mapped, alarm_t, beats)
        if verbose and (notes or got):
            print(f"[regex] {beat['id']}: got {sorted(got)} " + " | ".join(notes))
    return {"alarms": alarm_t, "beats": dict(beats), "errors": errs}


def report(name: str, out: dict) -> None:
    print(f"\n=== {name}")
    if "claims" in out:
        print("claims (validated), per category:")
        for c in CATS:
            if any(out["claims"][c].values()):
                print(f"  {c:8} {prf(out['claims'][c])}   unvalidated: {prf(out['raw'][c])}")
        tot = {k: sum(out["claims"][c][k] for c in CATS) for k in ("tp", "fp", "fn")}
        print(f"  {'all':8} {prf(tot)}")
        s = out["seconds"]
        if s:
            print(f"latency: median {statistics.median(s):.1f}s, p90 "
                  f"{sorted(s)[int(len(s) * .9) - 1]:.1f}s, max {max(s):.1f}s over {len(s)} "
                  f"calls; errors {out['errors']}/{out['calls']}; dropped by validation "
                  f"{out['dropped']}")
    if "first" in out:
        print("alarms BEFORE the second read:")
        report_alarms(out["first"])
        cs = [x for x in out.get("confirm_seconds", []) if x]
        if cs:
            print(f"second read: {len(cs)} beats asked, median {statistics.median(cs):.1f}s, "
                  f"max {max(cs):.1f}s")
        print("AFTER the second read:")
    report_alarms(out)
    if out.get("errors") and isinstance(out["errors"], list):
        print("regex check errors:", out["errors"][:6])


def report_alarms(out: dict) -> None:
    print("alarms, per category:")
    for c in ALARM_CATS:
        if any(out["alarms"][c].values()):
            print(f"  {c:9} {prf(out['alarms'][c])}")
    tot = {k: sum(out["alarms"][c][k] for c in ALARM_CATS) for k in ("tp", "fp", "fn")}
    print(f"  {'all':9} {prf(tot)}")
    b = out["beats"]
    print(f"beats: clean {b.get('clean', 0)}, falsely alarmed {b.get('clean_alarmed', 0)}; "
          f"bad {b.get('bad', 0)}, every alarm caught {b.get('bad_all_caught', 0)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", default=[])
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--regex-only", action="store_true")
    ap.add_argument("--record", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--no-confirm", action="store_true")
    ap.add_argument("--subset", choices=("all", "tuned", "held"), default="all")
    ap.add_argument("--replay", default="", help="score a --record file's extractions "
                    "instead of calling the model to read (the second read still calls it)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    results = {"regex": run_regex(args.verbose, args.subset)}
    report("regex checks", results["regex"])
    record: dict = {}
    if not args.regex_only:
        for model in args.model or ["igorls/gemma-4-12B-it-heretic-GGUF:latest"]:
            started = time.time()
            replay = (json.loads(Path(args.replay).read_text(encoding="utf-8"))
                      if args.replay else None)
            results[model] = run_model(model, args.runs, args.host, record, args.verbose,
                                       confirm=not args.no_confirm, subset=args.subset,
                                       replay=replay)
            report(f"{model} x{args.runs} ({time.time() - started:.0f}s)", results[model])
    if args.record:
        Path(args.record).write_text(json.dumps(record, indent=1), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1, default=dict),
                                   encoding="utf-8")


if __name__ == "__main__":
    main()
