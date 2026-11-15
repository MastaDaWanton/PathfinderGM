"""How often a spoken hire reaches the plan as `company do: hire` (docs/hired-swords.md).

Not a pytest: it needs a live Ollama and minutes. Plans only — nothing resolves, nothing
is saved. The scene is a save with a sword for hire standing beside the PC (a `guard` by
the population's roll, `hirelings.HIRES_OUT`) and in nobody's pay.

    set PATHFINDER_GM_DATA=<scratch data>
    python tools/hire_bench.py <save.json> <ref> [--json out.json] [--only 3,7]

Each line is planned once. A HIRE line counts as caught when the plan holds
`company do: hire` for the ref; a CONTROL line (a question, a refusal) counts as a false
hire when it does.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

# The fixed set. Spoken the many ways a player hires a sword: an order, an offer taken,
# coin in hand, a contract, terse, long, in and out of quotes.
HIRES = (
    'I hire the guard.',
    'I hire the guard to come with me.',
    '"You\'re hired. Come with me."',
    '"I\'ll pay your wage. Walk with me and keep me alive."',
    'I pay the guard a week\'s wages in advance and tell them to follow me.',
    '"Here is your coin. You work for me now."',
    'I take the guard on as my bodyguard.',
    '"I need a sword at my back. Name your price and you\'re hired."',
    '"Fine, your terms are fair. You\'re hired."',
    'I offer the guard work as my bodyguard for the week, and pay them.',
    '"Sign on with me as a guard for my caravan. I pay by the week."',
    'I hire the guard to guard my cargo.',
    '"Come work for me. I\'ll cover your wages."',
    'I engage the guard\'s services for a week.',
    '"You. I\'m hiring you. Let\'s go."',
    'I recruit the guard as a hired sword.',
    '"Will you take my coin and travel with me? Good, then you\'re hired."',
    'I put the guard on my payroll and we head out together.',
    '"I\'ll take you on. Same pay as the watch gives you, a week up front."',
    'I tell the guard I am hiring them as my escort and hand over their pay.',
    '"Pack your things, you work for me from today."',
    'I strike a deal with the guard: they come with me as my sellsword, I pay their wage.',
)
CONTROLS = (
    '"How much would you charge to guard me for a week?"',
    '"I don\'t need a guard. Good day."',
    'I ask the guard where the nearest inn is.',
    '"Do you know anyone here who hires out as a sellsword?"',
)


def run(save: Path, ref: str, only=None) -> list[dict]:
    from gm.agent import GMAgent
    from play import campaign as cm
    from play import views

    rows = []
    lines = [("hire", t) for t in HIRES] + [("control", t) for t in CONTROLS]
    for n, (kind, text) in enumerate(lines):
        if only and n not in only:
            continue
        c = cm.Campaign.load(save)
        who = c.scene.actors[ref]
        who.remove_effects(source=f"company:{ref}")
        agent = GMAgent(c.world, c.engine())
        views._arm_cards(agent, c)
        t0 = time.monotonic()
        try:
            plan = agent.plan_turn(text, list(c.history), location=c.location)
            ops = [(i.op, dict(i.params or {})) for i in plan.intents]
            err = ""
        except Exception as exc:  # noqa: BLE001 - a bench row, not a crash
            ops, err = [], f"{type(exc).__name__}: {exc}"
        hired = any(op == "company" and str(p.get("who")) == ref
                    and str(p.get("do") or "") == "hire" for op, p in ops)
        reading = getattr(agent, "reading", None) or {}
        rows.append({"n": n, "kind": kind, "text": text, "hired": hired, "error": err,
                     "ops": [op for op, _p in ops],
                     "acts": [(a.get("act"), a.get("target")) for a in
                              reading.get("actions") or [] if isinstance(a, dict)],
                     "seconds": round(time.monotonic() - t0, 1)})
        print(json.dumps(rows[-1]), flush=True)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("save")
    ap.add_argument("ref")
    ap.add_argument("--json")
    ap.add_argument("--only")
    a = ap.parse_args()
    only = {int(x) for x in a.only.split(",")} if a.only else None
    rows = run(Path(a.save), a.ref, only)
    hires = [r for r in rows if r["kind"] == "hire"]
    ctrl = [r for r in rows if r["kind"] == "control"]
    print(f"hires caught {sum(r['hired'] for r in hires)}/{len(hires)}; "
          f"false hires {sum(r['hired'] for r in ctrl)}/{len(ctrl)}")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
