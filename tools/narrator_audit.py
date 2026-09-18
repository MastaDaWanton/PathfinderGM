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
import statistics
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
    # Kills, as many as the dice allow. The death line is the one piece of prose this
    # project has measured as byte-identical across a session (docs/narrator-guards.md),
    # and neither script above kills more than once. A level-one fixture cannot be
    # relied on to kill in one blow, so this measures what it can: how the deaths that
    # DO happen read against each other. Read `recurring` in the report for the rest.
    "kills": [
        "I walk into the worst tavern on the street.",
        "I pick a fight with the biggest man in the room.",
        "I punch him in the face as hard as I can.",
        "I hit him again and do not stop until he goes down.",
        "I finish him.",
        "I turn on the nearest of his friends and hit him.",
        "I hit him again, harder.",
        "I put him down for good.",
        "I look for anyone else who wants to try me.",
        "I go for the next one who steps up.",
        "I keep hitting him until he stops moving.",
        "I stand over the bodies and look around the room.",
        "I walk out before anyone else decides to try me.",
        "I find somewhere quiet and sit down.",
    ],
    # --- the long horizon ---------------------------------------------------------------
    #
    # Both scripts above are ten lines and loop, which measures a narrator's first ten
    # turns over and over. It cannot show drift, and drift is the failure a long session
    # actually has: the prose narrowing, the same opening returning, a name invented in
    # turn 12 becoming settled fact by turn 40.
    #
    # Sixty distinct lines, no repeats, and deliberately wandering — town, road, wild,
    # ruin, back to town — because a session that stays in one square is the looping
    # problem with extra steps. Run it with `--turns 60` and read the per-third report.
    "long": [
        "I look around and take stock of the street.",
        "I ask the nearest stallholder what work there is.",
        "I ask what they are selling today.",
        "I count what coin I have.",
        "I ask who I should speak to about work outside the walls.",
        "I walk down towards the water.",
        "I watch the boats for a while.",
        "I ask a boatman where the river goes.",
        "I ask him what he carries downstream.",
        "I buy something to eat from a stall.",
        "I eat it while I walk.",
        "I head for the smith to see what he has on the rack.",
        "I ask the smith about the ore he uses.",
        "I ask him what he would charge to mend a blade.",
        "I look at what else is on the rack.",
        "I leave the shop and walk out towards the gate.",
        "I ask the gate guard what lies north.",
        "I ask him whether the road is safe.",
        "I ask when the gate closes.",
        "I walk out into the grassland beyond the wall.",
        "I look for tracks in the grass.",
        "I follow the tracks a while.",
        "I stop and listen.",
        "I climb the nearest rise to see further.",
        "I look back the way I came.",
        "I keep walking north until the light starts to go.",
        "I make camp and sleep until dawn.",
        "I check my things before I set off.",
        "I look for water.",
        "I drink and fill what I can carry.",
        "I forage for anything worth taking.",
        "I look at what I have gathered.",
        "I walk on towards the treeline.",
        "I step in under the trees.",
        "I listen for anything moving.",
        "I look for a way through.",
        "I follow the ground where it falls away.",
        "I come out the other side and look around.",
        "I find the ruin the guard mentioned.",
        "I walk the outside of it first.",
        "I look for a way in.",
        "I step inside.",
        "I let my eyes adjust.",
        "I look at the walls.",
        "I search the floor.",
        "I take whatever is worth carrying.",
        "I go back out into the light.",
        "I sit down and rest a while.",
        "I look at how far the sun has moved.",
        "I start back the way I came.",
        "I walk until I can see the walls again.",
        "I come in through the gate.",
        "I tell the guard what I found.",
        "I ask him who would want to hear about it.",
        "I go and find that person.",
        "I tell them what is out there.",
        "I ask what it is worth to them.",
        "I take what they offer.",
        "I go and find somewhere to sleep.",
        "I lie down and let the day go.",
    ],
}


def audit(turns: int, script: str, world: str, character: str,
          model: str = "") -> dict:
    tally: collections.Counter = collections.Counter()
    rows: list[dict] = []
    lines = SCRIPTS[script]

    # Swap the narrator for this run only, in memory. The user's own models.json is not
    # touched: an audit that rewrites the player's settings is an audit nobody runs twice.
    from play import modelcfg

    real_for_role = modelcfg.for_role
    if model:
        def _override(role: str) -> dict:
            cfg = dict(real_for_role(role))
            if role in ("narrator", "prose"):
                cfg["model"] = model
            return cfg
        modelcfg.for_role = _override

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
            # Where the transcript stood before this turn, so what the turn actually
            # wrote can be recovered afterwards.
            was = len(before.transcript)
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
                # WHY it failed, not just that it did. Four instant failures in a
                # heretic run read as model faults until the status turned out to
                # be 410 — the PC had died and the campaign was over, which is the
                # harness outliving its character rather than the narrator failing.
                why = ""
                try:
                    why = json.dumps(r.json())[:200]
                except Exception:
                    why = (r.content or b"")[:200].decode("utf-8", "replace")
                tally["turn-failed"] += 1
                rows.append({"n": n, "said": said, "faults": ["turn-failed"],
                             "status": r.status_code, "why": why,
                             "seconds": round(seconds, 1)})
                continue

            c = cm.current()
            body = r.json()
            # Off the transcript, not off the response. `/api/say` returns `_state(c)`,
            # which has never had a `narration` key — so this read "" on every turn of
            # every run this harness has ever done, and `narration.review` was scoring an
            # empty string. The 196/200 baseline's proudest line, "no invented names, no
            # third-person slips, no echoed examples", was measuring nothing at all.
            #
            # Both beats this turn: the setup narration and the consequence. The player
            # reads both, so both are reviewed.
            said_this_turn = [b["text"] for b in c.transcript[was:]
                              if b.get("who") == "gm" and b.get("text")]
            text = " ".join(said_this_turn)
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
            # A turn that suspended for the player's d20 has done plenty — the attack
            # exists, the engine is waiting on a die. Scored as "did nothing" at first,
            # which reported three faults in fifty on llama3.1 that were all a punch
            # waiting to be rolled. The measurement was wrong, not the app.
            pending = bool(cm.current().scene.awaiting)
            if fighting and not outcomes and not pending:
                faults.append("combat-turn-did-nothing")
            if body.get("rejections"):
                faults.append("intent-rejected")
            if len(body.get("attempts") or []) > 1:
                faults.append("needed-a-retry")

            for f in faults:
                tally[f] += 1
            rows.append({"n": n, "said": said, "faults": faults,
                         "seconds": round(seconds, 1),
                         # Whole, not truncated to 120 — the length of the prose is the
                         # thing being asked about now, and a clipped sample cannot
                         # answer it.
                         "narration": text})
            print(f"  turn {n + 1:3d}  {seconds:5.1f}s  "
                  f"{', '.join(faults) if faults else 'clean'}")
        cm._LIVE.clear()
    modelcfg.for_role = real_for_role

    clean = sum(1 for r in rows if not r["faults"])
    return {"turns": len(rows), "clean": clean, "tally": dict(tally), "rows": rows,
            "texture": _texture_report(rows), "drift": _drift_report(rows)}


def _texture_report(rows: list[dict]) -> dict:
    """What the prose was like, over the whole run.

    Reported rather than judged. See `gm.narration.texture` on why most of what "good"
    means is not measurable here and why these particular numbers are.
    """
    said = [r["narration"] for r in rows if r.get("narration")]
    if not said:
        return {}
    lengths = sorted(len(t) for t in said)
    per_turn = [narration_mod.texture(t) for t in said]
    share, opener = narration_mod.formulaic(said)
    spoke = sum(1 for t in per_turn if t["has_speech"])
    # The narrator against itself. Measured 2026-09-17 on the shipped narrator, a run
    # this report called clean at 96% with openings at 7%: "the transition from the" in
    # 12 of 53 beats. Self-repetition (Salkar et al.) and the gzip ratio (Shaib et al.)
    # are the two numbers that see it; docs/narrator-guards.md.
    same = narration_mod.self_repetition(said)
    return {
        "turns_with_prose": len(said),
        "self_repetition": same["score"],
        "recurring": same["top"][:8],
        "compression_ratio": narration_mod.compression_ratio(said),
        "chars_mean": round(statistics.mean(lengths)),
        "chars_median": lengths[len(lengths) // 2],
        "chars_min": lengths[0], "chars_max": lengths[-1],
        "sentences_mean": round(statistics.mean(t["sentences"] for t in per_turn), 1),
        "words_per_sentence": round(statistics.mean(t["words_mean"] for t in per_turn), 1),
        "words_spread": round(statistics.mean(t["words_spread"] for t in per_turn), 1),
        "turns_with_speech": spoke,
        # The one number with a threshold on it, and it is generous — see FORMULA_SHARE.
        "same_opening_share": round(share, 2),
        "same_opening": opener,
        "formulaic": share > narration_mod.FORMULA_SHARE,
    }


def _drift_report(rows: list[dict], parts: int = 3) -> list[dict]:
    """The same numbers, by third of the run.

    The whole reason the `long` script exists. A ten-line looping script measures a
    narrator's first ten turns repeatedly and cannot show the thing a long session
    actually does — narrow. Comparing the first third against the last is the cheapest
    honest way to see it: if the prose is shortening, the openings converging or the
    faults piling up, the columns say so.
    """
    said = [r for r in rows if r.get("narration")]
    if len(said) < parts * 3:
        return []
    size = len(said) // parts
    out = []
    for i in range(parts):
        chunk = said[i * size:(i + 1) * size] if i < parts - 1 else said[i * size:]
        texts = [r["narration"] for r in chunk]
        share, opener = narration_mod.formulaic(texts)
        per = [narration_mod.texture(t) for t in texts]
        out.append({
            "part": f"{i + 1}/{parts}",
            "turns": len(chunk),
            "chars_mean": round(statistics.mean(len(t) for t in texts)),
            "words_spread": round(statistics.mean(p["words_spread"] for p in per), 1),
            "same_opening_share": round(share, 2),
            "same_opening": opener,
            "self_repetition": narration_mod.self_repetition(texts)["score"],
            "compression_ratio": narration_mod.compression_ratio(texts),
            "faults": sum(len(r["faults"]) for r in chunk),
        })
    return out


def _known_names(c) -> set[str]:
    """The agent's own list, asked for rather than reimplemented.

    This was a second copy, and it drifted exactly the way CLAUDE.md says a duplicated
    rule drifts. When the agent's vocabulary was widened to the world's prose — taking
    `invented-name` from 16% of turns to 4% when the saved runs were re-scored — the live
    harness went on reporting 15%, because it was still scoring against its own narrower
    set. The app was fixed and the instrument said it was not.

    An audit that grades the app against a different rulebook than the app uses is not
    measuring the app.
    """
    from gm.agent import GMAgent

    try:
        return GMAgent(c.world, c.engine())._known_names()
    except Exception:
        return {a.name for a in c.scene.actors.values() if a.name}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--turns", type=int, default=10)
    ap.add_argument("--script", choices=sorted(SCRIPTS), default="town")
    ap.add_argument("--world", default="")
    ap.add_argument("--character", default="fixtures/pc-kesst.json")
    ap.add_argument("--model", default="",
                    help="narrate with this model instead of the configured one")
    ap.add_argument("--json", default="", help="write the full run here")
    args = ap.parse_args()

    print(f"narrator audit: {args.turns} turns of '{args.script}'\n")
    result = audit(args.turns, args.script, args.world, args.character,
                   args.model)

    turns = result["turns"] or 1
    print(f"\n{result['clean']}/{turns} turns clean "
          f"({100 * result['clean'] // turns}%)")
    if result["tally"]:
        print("\nfaults per 100 turns:")
        for kind, n in sorted(result["tally"].items(), key=lambda kv: -kv[1]):
            if kind == "rolls-answered":
                continue
            print(f"  {kind:28s} {n:4d}   {100 * n / turns:6.1f}")
    tex = result.get("texture") or {}
    if tex:
        print("\nthe prose itself:")
        print(f"  length          mean {tex['chars_mean']} chars, "
              f"median {tex['chars_median']}, "
              f"range {tex['chars_min']}-{tex['chars_max']}")
        print(f"  sentences       {tex['sentences_mean']} per turn, "
              f"{tex['words_per_sentence']} words each, spread {tex['words_spread']}")
        print(f"  speech          {tex['turns_with_speech']}/{tex['turns_with_prose']} "
              f"turns contain somebody speaking")
        print(f"  openings        {int(100 * tex['same_opening_share'])}% share the "
              f"commonest ({tex['same_opening']!r})"
              + ("  ** FORMULAIC **" if tex["formulaic"] else ""))
        print(f"  self-repeat     {tex['self_repetition']} of each beat's four-word "
              f"phrases appear in another beat; gzip ratio {tex['compression_ratio']}")
        for phrase, n in tex.get("recurring") or []:
            print(f"                  {n:3d} beats  {phrase!r}")

    drift = result.get("drift") or []
    if drift:
        print("\ndrift, by third of the run:")
        print(f"  {'part':6} {'turns':>5} {'chars':>6} {'spread':>7} {'self-rep':>8} "
              f"{'gzip':>6} {'faults':>7}   commonest opening")
        for d in drift:
            print(f"  {d['part']:6} {d['turns']:5d} {d['chars_mean']:6d} "
                  f"{d['words_spread']:7.1f} {d['self_repetition']:8.3f} "
                  f"{d['compression_ratio']:6.2f} {d['faults']:7d}   "
                  f"{int(100 * d['same_opening_share'])}% {d['same_opening']!r}")

    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(f"\nwritten to {args.json}")


if __name__ == "__main__":
    main()
