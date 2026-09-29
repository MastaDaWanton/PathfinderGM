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
    # Every line asks for somebody who is not in the scene yet. The first live run with
    # the planner's `introduce` op (2026-09-25, the town script, 12 turns) used it zero
    # times — but the town script mostly addresses people already standing there, so it
    # could not tell under-use of the op from a script that never needed it.
    "strangers": [
        "I look along the street for someone who knows the roads north, and ask them.",
        "I find somebody selling bread and ask what a loaf costs.",
        "I ask around for a healer.",
        "I look for whoever keeps the inn and ask for a room.",
        "I wave down a passing carter and ask where he is headed.",
        "I look for a child who might run a message for a coin.",
        "I find someone who looks like they know the city's gossip and buy them a drink.",
        "I ask around for a guide who knows the grassland.",
        "I look for a scribe who can read a letter for me.",
        "I find the oldest person on the street and ask what this quarter was like once.",
    ],
    # Every line gives one man a reason to strike first, in words only — nothing the
    # player does is itself an attack, so the first blow has to be his. The blows door
    # (docs/declared-not-guessed.md): does the PLAN declare it, or does it only appear in
    # the prose, where `attacked_by` has had to read it out? No journey: a walk to a
    # tavern was ambushed on the way once (2026-09-26) and every insult after it landed
    # mid-fight, where provocation is off by design. The first version knocked a
    # drink from his hand, which the planner read as the player attacking, and every turn
    # after was already a fight (2026-09-25).
    "provoke": [
        "I look around at the people standing nearest me.",
        "I tell the biggest man here that I have seen better fighters in a nursery.",
        "I laugh in his face and tell him to do something about it.",
        "I call him a coward in front of his friends.",
        "I tell his friends he cried when the last man stood up to him.",
        "I lean in and tell him his wife is a better fighter than he is.",
        "I turn my back on him and tell the barkeep he smells.",
        "I tell the whole room he is all talk.",
        "I stay where I am and smile at him.",
        "I tell him I am still waiting.",
    ],
    # Every line goes looking for a place the settlement may not list yet: the places
    # door (docs/declared-not-guessed.md). Does the PLAN found it and go there, does the
    # prose door found it afterwards, or does nothing get made? The user's ruling: the
    # mechanism is free, but places must keep being created for travel, questing and
    # discovery (2026-09-25).
    "discover": [
        "I ask where the dockhands drink, and go there.",
        "I look for somewhere that sells rope and lamp oil.",
        "I find a quiet shrine and sit a while.",
        "I head for the stables to ask about a horse.",
        "I look for a pawnbroker who asks no questions.",
        "I ask around for the best cook in town and go to where they work.",
        "I go looking for the bathhouse.",
        "I look for a bookseller.",
        "I find a back alley where nobody will see me count my coin.",
        "I head out of town to wherever the charcoal burners work.",
    ],
    # Residency (docs/the-population.md §4): somebody met, walked away from, come back to
    # at night (gone home), asked after, found again in the morning, and then the road out
    # of town and back. Before 2026-09-27 the road destroyed everybody left behind, so
    # the bread seller of the last lines would have been a stranger with a new name.
    "return": [
        "I find somebody selling bread in the market and ask what a loaf costs.",
        "I ask her name.",
        "I walk over to the well.",
        "I sit by the well until well after dark.",
        "I go back to the market.",
        "I ask around for the woman who sold me bread.",
        "I find somewhere to sleep until morning.",
        "I go to the market and look for the bread seller.",
        "I take the road to the nearest town.",
        "I take the road back to the town I just left.",
        "I go to the market and look for the bread seller.",
        "I greet her by name.",
    ],
    # Shop hours and calling on people (docs/the-population.md): a counter shut at night,
    # a person gone home, asked after, and knocked on.
    "calling": [
        "I find somebody selling bread and ask what a loaf costs.",
        "I buy a loaf from her and ask her name.",
        "I walk over to the well.",
        "I wait at the well until ten at night.",
        "I ask around where the bread seller lives.",
        "I go to her house.",
        "I thank her, say goodnight and leave.",
        "I go to the market.",
        "I try to buy a coil of rope.",
        "I find somewhere to sleep until morning.",
        "I go to the market and buy a coil of rope.",
    ],
    # The still-not-built list (docs/the-population.md): a knock in the small hours, a
    # lock picked, a door forced, a shut counter, and a purchase opening the counter.
    "homes": [
        "I find somebody selling bread and ask what a loaf costs.",
        "I ask her name.",
        "I walk over to the well.",
        "I wait at the well until two in the morning.",
        "I ask around where the bread seller lives.",
        "I go to her house.",
        "I pick the lock on her door.",
        "I kick in her door.",
        "I go to the market.",
        "I try to buy a coil of rope.",
        "I find somewhere to sleep until morning.",
        "I go to the market and buy a coil of rope.",
    ],
    # Buying: the counter opens for a purchase, a walk to a named place is planned, and
    # the prose settles nothing the screen is for.
    "buying": [
        "I find somewhere to sleep until morning.",
        "I walk over to the well.",
        "I go to the market and buy a coil of rope.",
        "I try to buy a loaf of bread.",
        "I want to buy some torches.",
        "I buy a dragon's egg.",
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
    # --- the 2026-09-28 fix pass (docs/fix-plan-2026-09-28.md, gate G2) ----------------
    #
    # Each line is the playtest's own sentence or the nearest thing to it, so the live run
    # meets the defect the way the player did (docs/playtest-2026-09-28.md). A fourth,
    # `starts`, needs thirty fresh campaigns rather than thirty turns of one, so it is its
    # own mode rather than a script: `--starts 30 [--world …] [--offline]` (`starts()`).
    #
    # Out of the gate and into the land (items 16, 17, 19, 20). The Bobby session: `leave`
    # became a walk to the way in, the crossroads and the road away were refused and
    # narrated as reached, the bearing was never answered, and the forest the model
    # invented was accepted and filed under the village.
    "leave-town": [
        "I leave the town and stand outside it on the road.",
        "I look around to get a bearing on where I am and where the nearest larger town lies.",
        "I walk to the nearest crossroads and read the signposts.",
        "I take the road away from town until I can no longer see the walls.",
        "I take in the land around me: the ground, what grows here, the sky.",
        "I head into the nearest trees.",
        "I turn round and walk back to the gate.",
        "I speak to the watchman at the gate again.",
        "I walk across town to the market.",
        "I leave by the road and keep walking until nightfall.",
    ],
    # Asking after somebody who is elsewhere, then going to find them (items 5, 9). The
    # Bobby session: "I ask him about the girl in the market" spawned a girl at the gate,
    # the market had nobody of the kind, and the quest's giver walked up instead.
    "market-seek": [
        "I ask the nearest person about the girl who sells herbs in the market.",
        "I head to the market and look for the girl who sells herbs.",
        "I ask her what she is selling today.",
        "I ask her name.",
        "I ask a stallholder about the old man who mends nets down by the water.",
        "I go down to the water and look for the old man who mends nets.",
        "I ask him how long he has worked here.",
        "I go back to the market and look for whoever runs it.",
    ],
    # Area magic on people and on things (items 21, 22). Needs a caster whose book holds
    # Burning Hands and Sleep: the shipped pregens have empty books, so pass `--character`
    # a prepared wizard (docs/fix-baseline-2026-09-28.md). The Sleep line is the unprepared
    # cast — one refusal shown to the player, not seven retries — when Sleep is in the
    # book but not prepared.
    "cast-area": [
        # A wizard 1 has two level-1 slots, filled on the first morning in book order
        # (Burning Hands, Magic Missile): the first cast is the one that proves an area
        # catching a person, the second spends the other slot, and the rest are the
        # refusals a spent caster should get (measured 2026-09-28: the old order spent
        # Burning Hands on empty air and never tested a victim).
        "I look around at who is standing near me.",
        "I cast burning hands at the man standing nearest me.",
        "I cast magic missile at him.",
        "I cast burning hands into the empty air above my head.",
        "I cast sleep on the whole crowd.",
        "I stand my ground and watch what they do.",
    ],
}


# --- the replay corpus ---------------------------------------------------------------------
#
# `--record FILE` writes one JSON line per turn: the save as it stood BEFORE the turn
# (trimmed to what a detector needs — the scene, the recent beats), every model call the
# turn made with its full raw reply, and what the turn added to the transcript and the
# turn log. tests/test_replay_corpus.py runs the detectors over those raw replies, so real
# model prose is measured on every suite run without a model (2026-09-25). Recorded here,
# in the harness, rather than by a hook in the shipped app: nothing in the player's build
# can write a corpus.

RECORD_VERSION = 1

# The agent methods a model call can come from, innermost first; the first found on the
# stack names the call's role.
_ROLES = ("_rewrite", "polish", "narrate_turn", "narrate_outcome", "npc_turn",
          "plan_cheat", "plan_turn", "write", "answer")


def _role_of_caller() -> str:
    import inspect

    names = [f.function for f in inspect.stack()[2:40]]
    return next((r for r in _ROLES if r in names), names[0] if names else "?")


class _Recorder:
    def __init__(self, path: Path, script: str, model: str):
        import hashlib
        import subprocess

        self.path = path
        self.calls: list[dict] = []
        self.hashlib = hashlib
        try:
            sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                 text=True, cwd=Path(__file__).resolve().parents[1]).stdout.strip()
        except OSError:
            sha = ""
        self.head = {"v": RECORD_VERSION, "git": sha, "script": script, "model": model}

    def wrap(self, chat):
        def recorded(messages, model, *a, **kw):
            started = time.monotonic()
            reply = chat(messages, model, *a, **kw)
            self.calls.append({
                "role": _role_of_caller(), "model": model,
                "prompt_sha256": self.hashlib.sha256(
                    json.dumps(messages, sort_keys=True).encode("utf-8")).hexdigest()[:16],
                "schema": bool(kw.get("schema")), "json": bool(kw.get("as_json")),
                "seconds": round(time.monotonic() - started, 2),
                "raw": getattr(reply, "text", ""),
            })
            return reply
        return recorded

    @staticmethod
    def trimmed(save_text: str) -> dict:
        """The save a detector needs: the scene whole, the recent beats, no history."""
        d = json.loads(save_text)
        d["transcript"] = (d.get("transcript") or [])[-8:]
        d["history"] = (d.get("history") or [])[-6:]
        d["turn_log"] = []
        return d

    def write(self, n: int, said: str, before: dict, c, was: int, log_was: int):
        row = dict(self.head, turn=n, player=said, save_before=before, calls=self.calls,
                   added_transcript=c.transcript[was:],
                   added_turn_log=(getattr(c, "turn_log", None) or [])[log_was:])
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.calls = []


def audit(turns: int, script: str, world: str, character: str,
          model: str = "", record: str = "") -> dict:
    tally: collections.Counter = collections.Counter()
    rows: list[dict] = []
    lines = SCRIPTS[script]

    recorder = None
    real_chat = None
    if record:
        from gm import client as gm_client

        recorder = _Recorder(Path(record), script, model)
        real_chat = gm_client.chat
        gm_client.chat = recorder.wrap(real_chat)

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
        # `--world` was parsed and handed here since the flag existed, and then dropped:
        # every run started in the shipped default whatever was asked for, so a
        # "Pangrella" audit measured Aurvantis (docs/fix-interfaces.md, R0-5). The fix
        # pass's three-world queue needs the flag to mean what it says. "" keeps the old
        # behaviour — `new_campaign` fills a missing source with the shipped default.
        c = cm.begin_with(load_pc(character), world_source=world or None)
        c.save()
        client = Client()

        unreachable = 0
        stopped_early = ""
        for n in range(turns):
            said = lines[n % len(lines)]
            before = cm.current()
            fighting = before.scene.in_encounter
            # Where the transcript and the turn log stood before this turn, so what the
            # turn actually wrote can be recovered afterwards.
            was = len(before.transcript)
            log_was = len(getattr(before, "turn_log", None) or [])
            snapshot = (recorder.trimmed(before.path().read_text(encoding="utf-8"))
                        if recorder else None)
            started = time.monotonic()
            # Answer anything the engine is waiting on first. A fight suspends for the
            # player's d20, and `/api/say` correctly refuses while a roll is pending —
            # so a harness that cannot roll cannot audit a fight at all, which is the
            # half of the game most worth auditing. Rolled by the engine (no `face`),
            # which is what the popup's "roll for me" does.
            #
            # And nothing the server does may take the run down. Measured 2026-09-17:
            # Ollama restarted under turn 59 of 60, the view raised, Django's test
            # client re-raised it here, and fifty-eight turns of measurement went
            # unwritten. A turn that raises is a `turn-failed` row like any other; a
            # run that cannot reach the model three turns running stops and says so,
            # rather than burning the script against a server that is not there.
            try:
                for _ in range(12):
                    if not cm.current().scene.awaiting:
                        break
                    client.post("/api/roll", data="{}",
                                content_type="application/json")
                    tally["rolls-answered"] += 1
                r = client.post("/api/say", data=json.dumps({"text": said}),
                                content_type="application/json")
            except Exception as exc:  # noqa: BLE001 — the whole point is to survive it
                seconds = time.monotonic() - started
                why = f"{type(exc).__name__}: {str(exc)[:160]}"
                tally["turn-failed"] += 1
                rows.append({"n": n, "said": said, "faults": ["turn-failed"],
                             "status": 0, "why": why, "seconds": round(seconds, 1)})
                print(f"  turn {n + 1:3d}  {seconds:5.1f}s  turn-failed ({why})")
                unreachable += 1
                if unreachable >= 3:
                    stopped_early = f"three turns running failed to reach the model: {why}"
                    print(f"\nstopping early: {stopped_early}")
                    break
                continue
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
                # A 422 is the player-fixable refusal (docs/fix-interfaces.md §2.6):
                # no turn was spent and the reason came back in plain words, which is
                # the refusal working, not the narrator failing. Counted apart so a run
                # full of "prepare it first" does not read as a broken table.
                fault = "refused" if r.status_code == 422 else "turn-failed"
                tally[fault] += 1
                rows.append({"n": n, "said": said, "faults": [fault],
                             "status": r.status_code, "why": why,
                             "seconds": round(seconds, 1)})
                print(f"  turn {n + 1:3d}  {seconds:5.1f}s  {fault} "
                      f"({r.status_code} {why[:80]})")
                if _unreachable(r.status_code, why):
                    unreachable += 1
                    if unreachable >= 3:
                        stopped_early = f"three turns running failed to reach the model: {why[:120]}"
                        print(f"\nstopping early: {stopped_early}")
                        break
                continue
            unreachable = 0

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
            # The narrator's OWN prose apart from the engine's lines, for the texture
            # and drift reports. Measured 2026-09-17: the watcher's award line ("You
            # gain 200 XP for moving a matter along: …") sat in seven beats of a run
            # and was the run's single most repeated phrase — an engine template, not
            # the model's, and the two have to be told apart or the number says
            # nothing about the narrator.
            prose_this_turn = " ".join(b["text"] for b in c.transcript[was:]
                                       if b.get("who") == "gm" and b.get("text")
                                       and b.get("kind") == "setup")
            new_log = (getattr(c, "turn_log", None) or [])[log_was:]
            pull = next((str(t.get("pull") or "") for t in new_log
                         if t.get("kind") == "prose"), "")
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
            # The turn's own row, not the log's last row: since Phase 2 the beat is
            # followed by prose, mention, speech-tag and after-the-beat rows, so the last
            # row carries no outcomes and every fighting turn read as "did nothing"
            # (measured 2026-09-29: a Magic Missile that dealt 4 and turned its target
            # hostile was scored as a combat turn that did nothing).
            own = next((row for row in reversed(turn_log)
                        if row.get("kind") in ("turn", "resolution")), None)
            outcomes = (own.get("outcomes") if own else None) or []
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
                         # The counter the turn opened, if a purchase opened one.
                         "trade": body.get("trade"),
                         # Whole, not truncated to 120 — the length of the prose is the
                         # thing being asked about now, and a clipped sample cannot
                         # answer it.
                         "narration": text,
                         "prose": prose_this_turn,
                         "pull": pull,
                         # What the grooming did to each creature's turn this turn: a
                         # `wrong-actor` rewrite or backstop is a creature's turn the
                         # model told the wrong way round, which the page — mended —
                         # no longer shows (docs/wrong-actor.md).
                         "npc_repairs": [r for t in new_log if t.get("kind") == "npc-turn"
                                         for r in (t.get("repairs") or [])]})
            print(f"  turn {n + 1:3d}  {seconds:5.1f}s  "
                  f"{', '.join(faults) if faults else 'clean'}")
            if recorder:
                recorder.write(n, said, snapshot, c, was, log_was)
        cm._LIVE.clear()
    modelcfg.for_role = real_for_role
    if recorder:
        from gm import client as gm_client

        gm_client.chat = real_chat

    clean = sum(1 for r in rows if not r["faults"])
    pulls = [r["pull"] for r in rows if r.get("pull")]
    npc_repairs = collections.Counter(
        ("wrong actor: rewritten" if "rewritten" in r else "wrong actor: backstop")
        if r.startswith("wrong actor") else r.split(":")[0]
        for row in rows for r in row.get("npc_repairs") or [])
    return {"turns": len(rows), "clean": clean, "tally": dict(tally), "rows": rows,
            "texture": _texture_report(rows), "drift": _drift_report(rows),
            "npc_repairs": dict(npc_repairs),
            "pulls": {"sent": len(pulls), "distinct": len(set(pulls)),
                      "commonest": collections.Counter(pulls).most_common(3)},
            "stopped_early": stopped_early}


def _own(row: dict) -> str:
    """The narrator's own prose for a row. Rows written since 2026-09-17 carry it as
    `prose` (empty when the prose call whiffed and the page was the engine's tells —
    which is then correctly NOT the narrator's); older runs' rows have only the whole
    page, which is what they measured."""
    return str(row["prose"] if "prose" in row else row.get("narration") or "")


def _unreachable(status: int, why: str) -> bool:
    """Whether a failed turn was the model being absent rather than the turn being
    bad. A 503 carrying the client's own "cannot reach" or "did not answer" is the
    server saying so; a 410 (the character died) or a 502 (no legal turn) is not."""
    low = (why or "").lower()
    return status in (0, 503) and ("cannot reach" in low or "did not answer" in low
                                   or "remotedisconnected" in low
                                   or "connection" in low)


def _texture_report(rows: list[dict]) -> dict:
    """What the prose was like, over the whole run.

    Reported rather than judged. See `gm.narration.texture` on why most of what "good"
    means is not measurable here and why these particular numbers are.
    """
    # The narrator's own beats (`prose`), not the whole page: the engine's award and
    # tell lines are templates by design and belong to a different measurement.
    said = [_own(r) for r in rows if _own(r)]
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
    said = [r for r in rows if _own(r)]
    if len(said) < parts * 3:
        return []
    size = len(said) // parts
    out = []
    for i in range(parts):
        chunk = said[i * size:(i + 1) * size] if i < parts - 1 else said[i * size:]
        texts = [_own(r) for r in chunk]
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


def starts(n: int, world: str = "", character: str = "fixtures/pc-kesst.json",
           written: bool = True, model: str = "", first_seed: int = 1000) -> dict:
    """The `starts` mode: `n` fresh campaigns, one per story seed, and what each opened on.

    Lane C's live gate (docs/design-c-starts.md §8, fix plan G2): thirty seeds reach at
    least five towns and eight kinds of start; no village or town is called a city; the
    lead is described on first sight; nothing is narrated past the hand-off; no invented
    names; the template-fallback rate recorded as the baseline. The character's
    background cycles through every background and none, because a start is drawn FOR
    a background. `written=False` measures the engine side alone, with no model — the
    town and kind criteria can be checked offline before any Ollama time is spent.
    """
    from gm.narration import invented_names
    from play import opening, opening_prose
    from rules import backgrounds, openings

    real_for_role = None
    if model:
        from play import modelcfg

        real_for_role = modelcfg.for_role

        def _override(role: str) -> dict:
            cfg = dict(real_for_role(role))
            if role in ("narrator", "prose"):
                cfg["model"] = model
            return cfg
        modelcfg.for_role = _override
    bgs = [""] + sorted(backgrounds.all_backgrounds())
    rows: list[dict] = []
    try:
        with override_settings(CAMPAIGN_DIR=Path(os.environ.get("TEMP", "/tmp"))
                               / f"narrator-audit-starts-{int(time.time())}"):
            cm._LIVE.clear()
            for i in range(n):
                pc = load_pc(character)
                pc.background = bgs[i % len(bgs)]
                started = time.monotonic()
                c = cm.new_campaign(f"starts-{i}", seed=first_seed + i, character=pc,
                                    world_source=world or None)
                cm.open_the_story(c, written=written)
                beat = c.transcript[-1]
                text = str(beat.get("text") or "")
                here = opening.situation_for(c)
                skeleton = opening.compose(c, cm._standing(c.world, c.scene.pc()))
                _material, allowed = opening_prose.material(c, here, skeleton)
                scale = opening_prose.stated_scale(c.location)
                lead = opening.lead_of(c)
                rows.append({
                    "seed": first_seed + i, "background": pc.background,
                    "town": c.location.name if c.location is not None else "",
                    "scale": scale, "start": c.start_id,
                    "kind": str((c.scene.start or {}).get("kind") or ""),
                    "lead": lead.name if lead is not None else "",
                    "floor": bool((beat.get("opening") or {}).get("floor", not written)),
                    "problems": list((beat.get("opening") or {}).get("problems") or []),
                    "size_words": opening_prose.too_big(text, scale, allowed),
                    "face_given": (lead is None or not lead.appearance
                                   or opening_prose.face_given(text, here.who,
                                                               lead.appearance)),
                    "crossed": openings.crossed(text, c.scene.start or {}),
                    "invented": sorted(invented_names(text, allowed)),
                    "seconds": round(time.monotonic() - started, 1),
                })
                cm._LIVE.clear()
    finally:
        if real_for_role is not None:
            from play import modelcfg

            modelcfg.for_role = real_for_role
    towns = sorted({r["town"] for r in rows})
    kinds = sorted({r["kind"] for r in rows if r["kind"]})
    return {
        "rows": rows, "towns": towns, "kinds": kinds,
        "called_bigger": [r for r in rows if r["size_words"]],
        "faceless": [r for r in rows if not r["face_given"]],
        "crossed": [r for r in rows if r["crossed"]],
        "invented": [r for r in rows if r["invented"]],
        "floor": sum(1 for r in rows if r["floor"]),
        "passes": {"towns >= 5": len(towns) >= 5, "kinds >= 8": len(kinds) >= 8,
                   "no place called bigger": not any(r["size_words"] for r in rows),
                   "faces on first sight": all(r["face_given"] for r in rows),
                   "no hand-off crossed": not any(r["crossed"] for r in rows),
                   "no invented names": not any(r["invented"] for r in rows)},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--turns", type=int, default=10)
    ap.add_argument("--script", choices=sorted(SCRIPTS), default="town")
    ap.add_argument("--world", default="")
    ap.add_argument("--character", default="fixtures/pc-kesst.json")
    ap.add_argument("--model", default="",
                    help="narrate with this model instead of the configured one")
    ap.add_argument("--json", default="", help="write the full run here")
    ap.add_argument("--record", default="",
                    help="append each turn to this JSONL replay-corpus file")
    ap.add_argument("--starts", type=int, default=0,
                    help="the starts mode: this many fresh campaigns, one per seed")
    ap.add_argument("--offline", action="store_true",
                    help="with --starts: the engine side only, no prose model")
    args = ap.parse_args()

    if args.starts:
        result = starts(args.starts, args.world, args.character,
                        written=not args.offline, model=args.model)
        print(f"starts: {len(result['rows'])} campaigns, {len(result['towns'])} towns, "
              f"{len(result['kinds'])} kinds ({', '.join(result['kinds'])})")
        for r in result["rows"]:
            print(f"  {r['seed']:5d} {r['background'] or '-':18s} {r['town'][:18]:18s} "
                  f"{r['scale']:8s} {r['start']:24s} {r['lead'][:22]:22s}"
                  f"{' FLOOR' if r['floor'] else ''}"
                  f"{' SIZE:' + ','.join(r['size_words']) if r['size_words'] else ''}"
                  f"{' FACELESS' if not r['face_given'] else ''}"
                  f"{' CROSSED:' + ','.join(r['crossed']) if r['crossed'] else ''}"
                  f"{' INVENTED:' + ','.join(r['invented']) if r['invented'] else ''}")
        print(f"template floor: {result['floor']}/{len(result['rows'])}")
        for name, ok in result["passes"].items():
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if args.json:
            Path(args.json).write_text(json.dumps(result, indent=1, default=str),
                                       encoding="utf-8")
        return

    print(f"narrator audit: {args.turns} turns of '{args.script}'\n")
    result = audit(args.turns, args.script, args.world, args.character,
                   args.model, record=args.record)

    turns = result["turns"] or 1
    print(f"\n{result['clean']}/{turns} turns clean "
          f"({100 * result['clean'] // turns}%)")
    if result["tally"]:
        print("\nfaults per 100 turns:")
        for kind, n in sorted(result["tally"].items(), key=lambda kv: -kv[1]):
            if kind == "rolls-answered":
                continue
            print(f"  {kind:28s} {n:4d}   {100 * n / turns:6.1f}")
    if result.get("npc_repairs"):
        print("\nwhat grooming did to the creatures' turns:")
        for kind, n in sorted(result["npc_repairs"].items(), key=lambda kv: -kv[1]):
            print(f"  {kind[:60]:60s} {n:4d}")
    if result.get("stopped_early"):
        print(f"\nSTOPPED EARLY: {result['stopped_early']}")
    pulls = result.get("pulls") or {}
    if pulls.get("sent"):
        print(f"\nthreads pulled: {pulls['sent']} of {turns} turns carried one, "
              f"{pulls['distinct']} distinct; commonest "
              + ", ".join(f"{t[:50]!r} x{n}" for t, n in pulls.get("commonest") or []))
    tex = result.get("texture") or {}
    if tex:
        print("\nthe narrator's own prose (the engine's lines set aside):")
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
