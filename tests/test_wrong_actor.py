"""A creature's turn may not be told as somebody else's.

Measured 2026-09-27 with `python tools/narrator_audit.py --script fight --turns 12` on
gemma-4-12B: with the new player-intent interpreter on, 8 of 12 turns flagged
`third-person-pc`; with it off (the control), 2 of 12. Every flagged sentence sat in the
beat written for the ENEMY's turn — "Kesst Vayr with the marked knuckles lets out a low,
guttural growl" (the enemy is Borin; Kesst Vayr is the player), "Kesst Vayr's frantic
movements fail to break its hold, leaving it pinned firmly beneath your grasp".

Not the interpreter's doing. Its reading is consumed by `plan_turn` alone and never
reaches `npc_turn` or the consequence call, and a rerun with it on gave 2 of 12. Read
back from the recordings, the enemy-turn beats held three shapes:

  * the enemy made "you" — the consequence call opened "The player said: Borin Lyraxys
    acts" and its only worked example taught that the tell's subject is "you": "You
    weave through the panicked crowd … close the distance to the heavy door" for "Borin
    Lyraxys moves". 8 of the 100 enemy-turn beats in the recordings;
  * the player's name put on the enemy by OUR backstop: the model wrote "the beast's
    momentum carries it past you" about Borin, and `creature_nouns_for_pc` — sure that a
    creature noun among people can only mean the player — wrote "Kesst Vayr's momentum";
  * the player's first name alone ("Kesst’s temple") never swapped to "you", because the
    swap's guard asked for the whole name.

docs/wrong-actor.md is the record.
"""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import pytest

from gm import narration, prompts

PC = "Kesst Vayr"
BORIN = "Borin Lyraxys"


# --- the check --------------------------------------------------------------------------

# Real beats, each the consequence the model wrote for a creature's own turn, with the
# tell it was given. From tests/replay/ and the 2026-09-27 live run.
TURNED = [
    # "Borin Lyraxys moves from near to near." — the grappled man's own turn.
    (BORIN, "With a sudden, violent surge of effort, you wrench your body sideways, "
            "shifting your weight to break the hold. The grip loosens just enough for you "
            "to twist away, finding your footing as you scramble back from the grasping "
            "hands."),
    (BORIN, "You weave through the panicked crowd, moving with purpose as the initial "
            "shock of the violence creates a frantic opening. You push past a pair of "
            "shoving guards and close the distance to the heavy door."),
    # "Borin Lyraxys hits Kesst Vayr for 1 bludgeoning."
    (BORIN, "The heavy stool connects with a dull thud against Kesst’s temple, sending "
            "a jarring jolt through his skull. He reels back from the blow, his eyes "
            "glazing for a fleeting moment as the impact buys you the opening you need."),
    # "Borin Lyraxys's attack misses Kesst Vayr."
    (BORIN, "Your blade whistles through the air, aimed with lethal intent, but the strike "
            "falls wide as Kesst Vayr twists just out of reach."),
    # "Commoner moves from near to near."
    ("Commoner", "You lunge forward, your boots skidding on the wet cobblestones as you "
                 "close the distance toward the nearest guard."),
    # What our own creature-noun swap made of "the beast" and "the brute".
    (BORIN, "The strike misses, and Kesst Vayr's momentum carries it past you, slamming "
            "into the heavy wood of the table behind you."),
    ("man with the marked knuckles",
     "Kesst Vayr with the marked knuckles lets out a low, guttural growl, his grip "
     "tightening on the tankard."),
]

SOUND = [
    (BORIN, "Borin lunges with desperate speed, its claws whistling through the air just "
            "inches from your face. The strike misses, and the beast's momentum carries "
            "it past you."),
    ("man with a thick beard",
     "The man's heavy arm swings wide, connecting with your ribs in a dull thud of solid "
     "muscle. The impact knocks the wind from your lungs."),
    ("Commoner", "The commoner lunges forward, slamming their weight into the intruder. "
                 "The blow catches Kesst Vayr squarely in the chest."),
    # Named by a creature noun on its own turn — the 2026-09-27 control run, before our
    # swap made both of these "Kesst Vayr".
    (BORIN, "The creature lunges with a desperate, frantic energy, but its claws scrape "
            "uselessly against the ground as it overextends. It misses your position "
            "entirely, its momentum carrying it past you."),
    (BORIN, "The beast's momentum carries it forward, but its strike misses your guard "
            "entirely, swinging harmlessly into the empty air."),
    # Somebody may shout the name; dialogue is theirs.
    (BORIN, "Borin spits on the boards. 'Kesst Vayr, you are finished,' he growls, and "
            "comes at you."),
]


@pytest.mark.parametrize("acting,text", TURNED)
def test_a_creature_turn_told_the_wrong_way_round_is_caught(acting, text):
    assert narration.wrong_actor(text, acting, PC), text


@pytest.mark.parametrize("acting,text", SOUND)
def test_a_creature_turn_told_the_right_way_round_passes(acting, text):
    assert narration.wrong_actor(text, acting, PC) == [], text


def test_the_players_own_turn_is_not_this_check():
    """"You weave through the crowd" is exactly right when the player moved."""
    text = "You weave through the panicked crowd toward the door."
    assert narration.wrong_actor(text, "", PC) == []
    assert narration.wrong_actor(text, PC, PC) == []


def test_review_names_the_actor_in_its_fix():
    r = narration.review(TURNED[1][1], pc_name=PC, acting=BORIN)
    found = [f for f in r.findings if f.kind == "wrong-actor"]
    assert found and BORIN in found[0].fix_hint and found[0].weight == 3


# --- the backstop -----------------------------------------------------------------------

def test_a_beat_turned_round_whole_is_replaced_by_the_tells():
    """The actor never named: no sentence of it can be trusted, so the tell stands."""
    out, cut = narration.right_actor(TURNED[1][1], BORIN, PC,
                                     ["Borin Lyraxys moves from near to near."])
    assert out == "Borin Lyraxys moves from near to near." and len(cut) == 2


def test_a_beat_with_one_wrong_sentence_loses_only_that_sentence():
    text = ("Borin roars and swings. The strike misses, and Kesst Vayr's momentum "
            "carries it past you.")
    out, cut = narration.right_actor(text, BORIN, PC, ["Borin's attack misses you."])
    assert out == "Borin roars and swings." and len(cut) == 1


# --- the source of the second and third shapes: our own backstops -------------------------

def test_the_enemy_called_a_beast_keeps_the_noun_on_his_own_turn():
    """Measured live 2026-09-27: "the beast's momentum carries it past you" about Borin
    shipped as "Kesst Vayr's momentum carries it past you"."""
    text = ("Borin lunges with desperate speed, its claws whistling through the air just "
            "inches from your face. The strike misses, and the beast's momentum carries "
            "it past you, slamming into the heavy wood of the table behind you.")
    for acting in (BORIN, ""):
        out, swapped = narration.creature_nouns_for_pc(text, PC, True, acting=acting)
        assert out == text and swapped == [], "a sentence saying 'you' has the player in it"
    brute = "The brute with the marked knuckles lets out a low, guttural growl."
    out, swapped = narration.creature_nouns_for_pc(brute, PC, True,
                                                   acting="man with the marked knuckles")
    assert out == brute and swapped == [], "on his turn, the brute opening a clause is him"


def test_the_player_on_the_receiving_end_is_still_not_a_beast():
    """The 2026-09-18 case the swap was written for, on a creature's turn: the thug's
    swing at "the beast" is a swing at the player."""
    out, swapped = narration.creature_nouns_for_pc(
        "The thug's swing misses the beast by a hair.", "Masta", True, acting="thug")
    assert out == "The thug's swing misses Masta by a hair." and swapped == ["beast"]


def test_the_first_name_alone_becomes_you():
    """"against Kesst’s temple" reached the page: the swap's guard asked for the whole
    name, so a beat that said only "Kesst" was never looked at."""
    out, n = narration.pc_to_second_person(
        "The stool connects against Kesst’s temple. Kesst reels.", PC)
    assert out == "The stool connects against your temple. You reel." and n == 2


# --- the prompt ---------------------------------------------------------------------------

def test_a_creature_turn_is_framed_as_its_turn_with_the_player_as_you():
    msgs = prompts.call_two_messages(
        "Borin comes at you.", ["Borin Lyraxys's attack misses Kesst Vayr (9 against AC 15)."],
        [], "Borin Lyraxys acts", acting=BORIN, pc_name=PC)
    body = msgs[-1]["content"]
    assert "It is Borin Lyraxys's turn, not the player's" in body
    assert "The player said" not in body
    assert "Kesst" not in json.dumps(msgs), "no name to copy onto anybody"
    assert msgs[1]["content"] == prompts.CONSEQUENCE_NPC_EXAMPLE["user"]
    # The demonstration has the creature acting and the player on the receiving end.
    assert prompts.CONSEQUENCE_NPC_EXAMPLE["assistant"].startswith("The ferryman")


def test_the_players_turn_prompt_is_unchanged():
    msgs = prompts.call_two_messages("", ["Kesst Vayr hits Borin."], [], "I punch him")
    assert msgs[-1]["content"].startswith("The player said: I punch him")
    assert msgs[1]["content"] == prompts.CONSEQUENCE_EXAMPLE["user"]


def test_the_frame_line_echoed_back_is_cut():
    echoed = ("It is Borin Lyraxys's turn, not the player's. Borin acted.\n"
              "Borin swings at you and misses.")
    assert "not the player's" not in narration.clean_consequence(echoed)


# --- the repair, through the real door -----------------------------------------------------

class _World:
    name, secret, premise, entities = "Testholme", "", {}, {}
    unwritten, chronology, factions = [], [], []

    def ancestors(self, _):
        return []


def _agent():
    from gm import agent as agent_mod
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    borin = instantiate("thug", scene=s, name=BORIN)
    s.add(borin)
    return agent_mod, agent_mod.GMAgent(_World(), Engine(s, Dice(seed=1)))


def _outcome(tell):
    from rules.engine import Outcome

    return [Outcome(intent_id="i1", op="move", tell=tell)]


def test_the_repair_is_one_targeted_call_and_is_kept_when_it_holds(monkeypatch):
    from gm import client

    agent_mod, gm = _agent()
    calls = []

    def chat(messages, model, *a, **kw):
        calls.append(messages)
        if len(calls) == 1:
            return client.Reply(TURNED[1][1], 0.1, model)
        return client.Reply(json.dumps({"narration":
            "Borin shoves through the panicked crowd towards the heavy door, putting "
            "the room between himself and you."}), 0.1, model)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    text, attempt = gm.narrate_outcome("", _outcome("Borin Lyraxys moves from near to near."),
                                       "Borin Lyraxys acts", rewrite=False, acting=BORIN)
    assert len(calls) == 2
    assert "It was Borin Lyraxys's turn" in calls[1][-1]["content"]
    assert text.startswith("Borin shoves through")
    assert "wrong actor" in attempt.note and "rewritten" in attempt.note


def test_a_repair_that_is_still_wrong_leaves_the_tells(monkeypatch):
    from gm import client

    agent_mod, gm = _agent()
    monkeypatch.setattr(agent_mod.client, "chat", lambda m, model, *a, **k: client.Reply(
        TURNED[1][1] if "narration" not in json.dumps(k.get("schema") or {})
        else json.dumps({"narration": TURNED[1][1]}), 0.1, model))
    text, attempt = gm.narrate_outcome("", _outcome("Borin Lyraxys moves from near to near."),
                                       "Borin Lyraxys acts", rewrite=False, acting=BORIN)
    assert text == "Borin Lyraxys moves from near to near."
    assert "the tells stand" in attempt.note


def test_a_sound_creature_turn_still_costs_one_call(monkeypatch):
    """The repair is paid for only when the check fires: `npc_turn`'s price stands."""
    from gm import client

    agent_mod, gm = _agent()
    calls = []

    def chat(messages, model, *a, **kw):
        calls.append(model)
        # No outcome in the words: the claim repair's own call is not this test's.
        return client.Reply("Borin swings a heavy fist at your jaw.", 0.1, model)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    gm.narrate_outcome("", _outcome("Borin Lyraxys's attack misses Kesst Vayr."),
                       "Borin Lyraxys acts", rewrite=False, acting=BORIN)
    assert len(calls) == 1


@pytest.mark.parametrize("raw", [
    # The five creature-turn beats of the two 2026-09-27 runs that reached the page with
    # the player's name in them, as the model wrote them. Every one was put there by our
    # own grooming: the creature-noun swap (the first four) or the first-name guard
    # (the last two).
    "The creature lunges with a desperate, frantic energy, but its claws scrape uselessly "
    "against the ground as it overextends. It misses your position entirely, its momentum "
    "carrying it past you and into a clumsy, heavy sprawl.",
    "The beast's momentum carries it forward, but its strike misses your guard entirely, "
    "swinging harmlessly into the empty air.",
    "Borin lunges with desperate speed, its claws whistling through the air just inches "
    "from your face. The strike misses, and the beast's momentum carries it past you, "
    "slamming into the heavy wood of the table behind you.",
    "The creature's claws collide with Kesst's chest, the impact heavy and jarring enough "
    "to knock the breath from his lungs.",
    "With a desperate roar, Borin lunges forward and brings his weapon down in a punishing "
    "blow against Kesst.",
])
def test_the_measured_beats_leave_the_grooming_without_the_players_name(raw):
    """The measured outcome, through the real door: `third-person-pc` fired on each of
    these after `_groom`, and on none of them now. No model call is made — each is sound
    or mended by the deterministic steps alone."""
    _, gm = _agent()
    out, repairs, attempts = gm._groom(raw, hand_back=False, claims=False, rewrite=False,
                                       acting=BORIN)
    assert not attempts, repairs
    assert not any(f.kind == "third-person-pc"
                   for f in narration.review(out, pc_name=PC).findings), out


# --- the fallback the page shows when no prose was written ----------------------------------

def test_a_creature_turns_raw_tells_reach_the_page_as_you():
    from play.views import _plain_tells
    from rules.engine import Outcome

    class C:
        class scene:
            @staticmethod
            def pc():
                class P:
                    name = PC
                return P

    out = _plain_tells(C, [Outcome(intent_id="i1", op="attack",
                                   tell="Borin Lyraxys hits Kesst Vayr for 1 bludgeoning.")])
    assert out == "Borin Lyraxys hits you for 1 bludgeoning."


# --- the measurement, on real recorded prose ------------------------------------------------

REPLAY = Path(__file__).resolve().parent / "replay"


def _creature_beats():
    """Every consequence the model wrote for a creature's own turn in the recordings, with
    the creature's name: the call after an `npc_turn`, whose intent names the actor.

    Two quirks of the recorder, both read around: a claim repair made inside a call is
    recorded under that call's role (a `{"sentence": …}` reply, no intents), and a
    creature that walked on during the turn is missing from the save taken before it —
    its name is read off the start of its own tell in the turn log."""
    for f in sorted(REPLAY.glob("*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                people = rec["save_before"]["scene"].get("people") or {}
                pc = next((p["name"] for p in people.values() if p.get("kind") == "pc"), PC)
                others = tuple(p["name"] for p in people.values() if p.get("kind") != "pc")
                names = {ref: p.get("name", "") for ref, p in people.items()}
                for row in rec["added_turn_log"]:
                    for o in row.get("outcomes") or []:
                        tell = str(o.get("tell") or "")
                        if row.get("kind") == "npc-turn" and tell and row["ref"] not in names:
                            names[row["ref"]] = re.split(r"'s | moves | hits | misses ",
                                                         tell)[0]
                actor = ""
                for call in rec["calls"]:
                    if call["role"] == "npc_turn":
                        try:
                            reply = json.loads(call["raw"])
                        except ValueError:
                            continue
                        if not isinstance(reply, dict) or "intents" not in reply:
                            continue
                        first = (reply.get("intents") or [{}])[0]
                        actor = names.get(first.get("actor") or "", "")
                    elif call["role"] == "narrate_outcome" and actor:
                        if not str(call["raw"] or "").lstrip().startswith("{"):
                            yield f.name, rec["turn"], actor, pc, others, call["raw"] or ""
                    elif call["role"] in ("plan_turn", "narrate_turn"):
                        actor = ""


def test_the_recorded_corpus_measures_what_the_check_was_built_on():
    """38 creature-turn consequences in the committed recordings. Six are flagged: five
    turned round (three from the grappled man's own turns, a commoner's and a desperate
    stranger's) and one sound beat that says only "He" ("He shifts his weight…"), which
    costs a repair and no more. Exact, so a change to the check that moves either number
    is seen. The 2026-09-27 live run, not committed, added three more turned beats and no
    false alarm: 8 of 100 creature-turn beats across both, measured before this check."""
    beats = list(_creature_beats())
    flagged = [b for b in beats if narration.wrong_actor(b[5], b[2], b[3], b[4])]
    assert len(beats) == 38
    assert len(flagged) == 6, [(b[0], b[1], b[5][:60]) for b in flagged]
