"""Measure the read-back's `unseen` question on hand-labelled beats.

    python tools/unseen_bench.py --model igorls/gemma-4-12B-it-heretic-GGUF:latest --runs 2
    python tools/unseen_bench.py --record unseen.json

The question (gm/beat_verify.py, `unseen_messages`) shipped in feat/hidden-state and never
fired live, so its precision and recall were unknown. For each beat in
tests/beat_verify/unseen_gold.py it is asked exactly as `beat_verify.read` asks it (same
messages, schema, temperature and length), the answer is validated (`validate`) and
diffed (`diff`), and each alarm is then put to the second read (`confirm`), the path a
real beat takes. Scored twice:

  reader   the validated `unseen` claims against the labels;
  alarms   what survives the second read — the sentences the game would actually cut.

A claim matches a label when the ref is the same and its sentence holds the label's
phrase. A sentence labelled `opt` is neither rewarded nor punished. Precision is matched
claims over claims, recall matched labels over labels; the clean-beat false-alarm rate is
the share of beats labelled with no flag that raised one anyway — the number that costs a
good sentence.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gm import beat_verify as bv  # noqa: E402
from tests.beat_verify import unseen_gold as G  # noqa: E402


def _norm(s: str) -> str:
    return " ".join(str(s or "").lower().split())


def _hits(label, ref: str, sentence: str) -> bool:
    return label[0] == ref and _norm(label[1]) in _norm(sentence)


def score(beat, pairs: list[tuple[str, str]], tally: dict, stage: str) -> list[str]:
    """`pairs` are (ref, sentence) the stage reported. Returns notes on the misses."""
    notes = []
    flags, opts = list(beat["flag"]), list(beat.get("opt") or ())
    used: set[int] = set()
    counted = 0
    for ref, sentence in pairs:
        k = next((i for i, f in enumerate(flags) if i not in used and _hits(f, ref, sentence)),
                 None)
        if k is not None:
            used.add(k)
            tally[stage]["tp"] += 1
            counted += 1
        elif any(_hits(o, ref, sentence) for o in opts):
            continue
        else:
            tally[stage]["fp"] += 1
            counted += 1
            notes.append(f"{stage} FP {ref}: {sentence!r}")
    for i, f in enumerate(flags):
        if i not in used:
            tally[stage]["fn"] += 1
            notes.append(f"{stage} FN {f[0]}: {f[1]!r}")
    if not flags:
        tally[stage]["clean"] += 1
        if counted:
            tally[stage]["clean_alarmed"] += 1
    return notes


def ask(text, facts, chat, model, host):
    """The unseen call alone, as `beat_verify.read` makes it."""
    msgs = bv.unseen_messages(text, facts)
    if bv.bare_template(model):
        msgs = bv._raw_prompt(msgs)
    reply = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                 num_predict=300, provider="ollama", api_key="",
                 schema=bv.unseen_schema(facts))
    return reply.text, {"unseen_at_you": (reply.json() or {}).get("unseen_at_you") or []}


def run(model: str, runs: int, host: str, record: dict, verbose: bool) -> dict:
    from gm import client

    tallies = []
    for n in range(runs):
        tally = {s: {"tp": 0, "fp": 0, "fn": 0, "clean": 0, "clean_alarmed": 0}
                 for s in ("reader", "alarms")}
        seconds = []
        for beat in G.BEATS:
            facts = G.facts(beat)
            started = time.monotonic()
            raw, answer = ask(beat["text"], facts, client.chat, model, host)
            claims, _dropped = bv.validate(bv.claims_of(answer, facts), beat["text"], facts)
            claims = [c for c in claims if c.category == "unseen"]
            found = [d for d in bv.diff(claims, facts, beat["text"]) if d.category == "unseen"]
            kept, _refuted, _s = bv.confirm(found, beat["text"], facts, model=model, host=host)
            seconds.append(time.monotonic() - started)
            notes = score(beat, [(str(c.slots.get("who")), c.sentence) for c in claims],
                          tally, "reader")
            notes += score(beat, [(str(d.ref), d.sentence) for d in kept], tally, "alarms")
            record.setdefault(model, {}).setdefault(beat["id"], []).append(
                {"run": n, "raw": raw, "kept": [d.sentence for d in kept]})
            if verbose or notes:
                print(f"  run {n + 1} {beat['id']}: " + (" | ".join(notes) or "ok"))
        tally["seconds"] = round(sum(seconds) / len(seconds), 2)
        tallies.append(tally)
        report(f"{model} run {n + 1}", tally)
    return {"runs": tallies}


def _ratio(a: int, b: int) -> str:
    return f"{a}/{b} = {a / b:.2f}" if b else f"{a}/0"


def report(title: str, tally: dict) -> None:
    print(f"== {title} (mean {tally['seconds']} s per beat)")
    for stage in ("reader", "alarms"):
        t = tally[stage]
        print(f"   {stage:7s} precision {_ratio(t['tp'], t['tp'] + t['fp'])}, "
              f"recall {_ratio(t['tp'], t['tp'] + t['fn'])}, clean beats alarmed "
              f"{_ratio(t['clean_alarmed'], t['clean'])}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="igorls/gemma-4-12B-it-heretic-GGUF:latest")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--record", default="")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")
    import django

    django.setup()
    record: dict = {}
    print(f"{len(G.BEATS)} beats, {sum(len(b['flag']) for b in G.BEATS)} labelled "
          f"sentences, {sum(1 for b in G.BEATS if not b['flag'])} clean beats")
    run(args.model, args.runs, args.host, record, args.verbose)
    if args.record:
        Path(args.record).write_text(json.dumps(record, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
