"""Measure the player-intent interpreter against the labelled set, and the word-detectors
beside it (docs/the-interpreter.md).

Not a pytest: it needs a live Ollama and takes minutes. The integrity of the labels is
tests/test_interpreter_gold.py.

    python tools/interpreter_bench.py                   # the interpreter and the detectors
    python tools/interpreter_bench.py --detectors-only  # no model, seconds
    python tools/interpreter_bench.py --model qwen3:8b --json out.json
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

from tests.interpreter.gold import GOLD  # noqa: E402
from tests.interpreter.score import score  # noqa: E402

# What each op the detectors declare means as an act of the frame.
_OP_ACT = {
    "travel": "go", "venture": "go", "journey": "journey", "buy": "buy", "sell": "sell",
    "give": "give", "loot": "take", "attack": "attack", "begin_encounter": "attack",
    "cast": "cast", "use_ability": "use", "use_item": "consume", "drink": "consume",
    "eat": "consume", "advance_time": "wait", "rest": "rest", "forage": "gather",
    "prospect": "gather", "provoke": "insult", "say": "talk", "introduce": "seek",
    "call_on": "call_on", "break_in": "break_in", "found": "search",
}


def _scene():
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc
    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    town = world.by_name("Vormoor", kind="CITY").id
    s = Scene(location_id=town)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = 10 * 60
    Engine(s, Dice(seed=1), world=world).place_party()
    return s, world


def detectors(text: str, scene, world) -> dict:
    """The acts today's code reads out of the sentence: the declarers the schema is
    built from, and the readers the chain asks directly."""
    from gm import judgement

    acts: list[str] = []

    def add(a):
        if a and a not in acts:
            acts.append(a)

    for op in judgement.declared_ops(text, scene, world):
        add(_OP_ACT.get(op))
    if judgement.purchase_sought(text):
        add("buy")
    if judgement.called_on(text)[0]:
        add("call_on")
    if judgement.breaks_in(text)[1]:
        add("break_in")
    if judgement.person_sought(text) and "seek" not in acts and "talk" not in acts:
        add("seek")
    return {"question": "?" in text and not acts, "actions": [{"act": a} for a in acts]}


def _acts_only(frames):
    return [{"text": f.get("text", ""), "question": f.get("question"),
             "actions": [{"act": a["act"]}
                                                          for a in f.get("actions") or []]}
            for f in frames]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--detectors-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    gold = GOLD[:args.limit] if args.limit else GOLD
    scene, world = _scene()

    det = [detectors(g["text"], scene, world) for g in gold]
    det_score = score(_acts_only(gold), det)
    out = {"detectors": {k: v for k, v in det_score.items() if k != "misses"}}
    print("detectors (acts only):", json.dumps(out["detectors"]))

    if not args.detectors_only:
        from gm import interpret

        got, seconds, dropped = [], [], 0
        interpret.interpret("I look around.", model=args.model or None)   # warm the model
        for i, g in enumerate(gold):
            try:
                f = interpret.interpret(g["text"], model=args.model or None)
            except Exception as exc:  # noqa: BLE001 — a failed call is a miss, not a crash
                f = {"question": False, "actions": [], "claims": [], "dropped": [],
                     "seconds": 0.0, "error": str(exc)[:200]}
            got.append(f)
            seconds.append(f.get("seconds", 0.0))
            dropped += len(f.get("dropped") or [])
            if (i + 1) % 20 == 0:
                print(f"  {i + 1}/{len(gold)}", flush=True)
        full = score(gold, got)
        acts = score(_acts_only(gold), _acts_only(got))
        out["interpreter"] = {k: v for k, v in full.items() if k != "misses"}
        out["interpreter"]["acts_only"] = {k: v for k, v in acts.items() if k != "misses"}
        out["interpreter"]["seconds"] = {
            "median": round(statistics.median(seconds), 2),
            "p90": round(sorted(seconds)[int(len(seconds) * 0.9) - 1], 2),
            "max": round(max(seconds), 2)}
        out["interpreter"]["slots_dropped_as_not_the_players_words"] = dropped
        out["misses"] = full["misses"]
        out["frames"] = [{"text": g["text"], "got": f} for g, f in zip(gold, got)]
        print("interpreter:", json.dumps(out["interpreter"]))
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1, ensure_ascii=False),
                                   encoding="utf-8")
        print("written to", args.json)


if __name__ == "__main__":
    main()
