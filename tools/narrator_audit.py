"""Play a scripted session and count what the narrator got wrong.

Every narration bug this project has ever fixed was found by a person playing until
something looked wrong. That works, and it does not scale, and it cannot answer the
question the product actually has to answer before it ships: *how often does the GM mess
up?* "Rarely, I think" is not a shippable answer.

This drives the real HTTP loop — the same endpoints the browser calls, the same agent,
the same model — through a fixed script, and scores every reply with the same
`gm.narration.review` the app already repairs against, plus the things review cannot see:

  * a combat turn that proposed no action at all (the failure that cost the tavern fight
    its dice, and the one grammar-constrained decoding is meant to make impossible);
  * an intent the engine rejected;
  * a turn that took more than one model call to survive.

The output is a rate per hundred turns, per fault kind. Run it before and after a change
to the prompt, the model or the detectors, and the difference is the evidence.

Deliberately not a pytest: it needs a live Ollama and takes minutes, and a test that
sometimes needs a GPU is a test people learn to skip. `docs/playtest-*.md` is where the
numbers go.

    python tools/narrator_audit.py --turns 20
    python tools/narrator_audit.py --script fight --turns 12 --model qwen3:8b
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from django.test import Client, override_settings  # noqa: E402

from gm import narration as narration_mod  # noqa: E402
from play import campaign as cm  # noqa: E402
from rules.sheet import load_pc  # noqa: E402

# Two scripts, because the failures differ. Ordinary play is where names get invented;
# a fight is where the engine stops being told anything.
SCRIPTS = {
    "town": [
        "I look around and take stock of the street.",
        "I ask the nearest stallholder what work there is.",
        "I ask them who runs this quarter.",
        "I head for the smith to see what he has on the rack.",
        "I ask the smith about the ore he uses.",
        "I leave the shop and walk out towards the gate.",
        "I ask the gate guard what lies north.",
        "I walk out into the grassland beyond the wall.",
        "I look for tracks in the grass.",
        "I make camp and sleep until dawn.",
    ],
    "fight": [
        "I walk into the worst tavern on the street.",
        "I pick a fight with the biggest man in the room.",
        "I punch him in the face.",
        "I punch him again.",
        "I keep hitting him.",
        "I grab him and throw him over a table.",
        "I stand over him and tell him to stay down.",
        "I take what he was carrying.",
        "I walk out before anyone else decides to try me.",
        "I find somewhere quiet and sit down.",
    ],
}


def audit(turns: int, script: str, world: str, character: str) -> dict:
    tally: collections.Counter = collections.Counter()
    rows: list[dict] = []
    lines = SCRIPTS[script]

    with override_settings(CAMPAIGN_DIR=Path(os.environ.get("TEMP", "/tmp"))
                           / f"narrator-audit-{int(time.time())}"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc(character))
        c.save()
        client = Client()

        for n in range(turns):
            said = lines[n % len(lines)]
            before = cm.current()
            fighting = before.scene.in_encounter
            started = time.monotonic()
            # Answer anything the engine is waiting on first. A fight suspends for the
            # player's d20, and `/api/say` correctly refuses while a roll is pending —
            # so a harness that cannot roll cannot audit a fight at all, which is the
            # half of the game most worth auditing. Rolled by the engine (no `face`),
            # which is what the popup's "roll for me" does.
            for _ in range(12):
                if not cm.current().scene.awaiting:
                    break
                client.post("/api/roll", data="{}",
                            content_type="application/json")
                tally["rolls-answered"] += 1

            r = client.post("/api/say", data=json.dumps({"text": said}),
                            content_type="application/json")
            seconds = time.monotonic() - started
            if r.status_code != 200:
                tally["turn-failed"] += 1
                rows.append({"n": n, "said": said, "faults": ["turn-failed"],
                             "seconds": round(seconds, 1)})
                continue

            c = cm.current()
            body = r.json()
            text = str(body.get("narration") or "")
            faults: list[str] = []

            # What the app's own reviewer would say, run against the same world names the
            # agent grounds on.
            agent_names = _known_names(c)
            alone = not [a for ref, a in c.scene.actors.items()
                         if not a.is_pc and a.hp > 0]
            review = narration_mod.review(text, pc_name=c.scene.pc().name,
                                          known_names=agent_names, alone=alone)
            faults += [f.kind for f in review.findings]

            # And the things review cannot see, because they are about the *engine*.
            turn_log = getattr(c, "turn_log", None) or []
            outcomes = (turn_log[-1].get("outcomes") if turn_log else None) or []
            if fighting and not outcomes:
                faults.append("combat-turn-did-nothing")
            if body.get("rejections"):
                faults.append("intent-rejected")
            if len(body.get("attempts") or []) > 1:
                faults.append("needed-a-retry")

            for f in faults:
                tally[f] += 1
            rows.append({"n": n, "said": said, "faults": faults,
                         "seconds": round(seconds, 1),
                         "narration": text[:120]})
            print(f"  turn {n + 1:3d}  {seconds:5.1f}s  "
                  f"{', '.join(faults) if faults else 'clean'}")
        cm._LIVE.clear()

    clean = sum(1 for r in rows if not r["faults"])
    return {"turns": len(rows), "clean": clean, "tally": dict(tally), "rows": rows}


def _known_names(c) -> set[str]:
    names = {a.name for a in c.scene.actors.values()}
    try:
        w = c.world
        names |= {e.name for e in w.entities.values()}
        names |= {f["name"] for ch in w.chronology for f in ch.figures}
        names.add(w.name)
    except Exception:
        pass
    return {n for n in names if n}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--turns", type=int, default=10)
    ap.add_argument("--script", choices=sorted(SCRIPTS), default="town")
    ap.add_argument("--world", default="")
    ap.add_argument("--character", default="fixtures/pc-kesst.json")
    ap.add_argument("--json", default="", help="write the full run here")
    args = ap.parse_args()

    print(f"narrator audit: {args.turns} turns of '{args.script}'\n")
    result = audit(args.turns, args.script, args.world, args.character)

    turns = result["turns"] or 1
    print(f"\n{result['clean']}/{turns} turns clean "
          f"({100 * result['clean'] // turns}%)")
    if result["tally"]:
        print("\nfaults per 100 turns:")
        for kind, n in sorted(result["tally"].items(), key=lambda kv: -kv[1]):
            if kind == "rolls-answered":
                continue
            print(f"  {kind:28s} {n:4d}   {100 * n / turns:6.1f}")
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(f"\nwritten to {args.json}")


if __name__ == "__main__":
    main()
