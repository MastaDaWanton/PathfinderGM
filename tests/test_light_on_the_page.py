"""Poor light reaches the narrator and is held to the page (owner's ruling, 2026-10-06).

"keep the book rule but make sure that it naturally makes it into prose that you can
barely see and that it making it hard to hit your target."

Measured before (build/alchemy c4e86f5): the light model decided the miss chance (dim 20%,
dark 50%), and the narrator heard of the light only through a tell on a swing the miss
chance happened to decide — "the thug finds nothing there — dim light, 20% miss chance
(14)". `prompts.scene_now` said nothing of it, and no check read the page for it: a night
fight could be written as a sunny brawl. The detector's family was measured on the 191
recorded gm beats in tests/replay (all lit scenes): the first, generous word list found
"poor sight" in 51 of them ("a shadow crosses his face", a faint smell, the pitch of a
voice); the shipped one in 7, every one a dim room.
"""
from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from gm import prompts
from gm.checks import light_shown as L
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

ROAD = "5bbd0c40345f~road"
CAVE = "5bbd0c40345f~underground:the-cave"
NOON, MIDNIGHT = 12 * 60, 0


def _night(at=ROAD, clock=MIDNIGHT, fight=True):
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    e = Engine(s, Dice(seed=5))
    if fight:
        e._ensure_encounter("pc")
    for a in list(s.actors.values()):
        a.at = at
    s.at = at
    s.clock_minutes = clock
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (6, 10)
    s.resync_zones()
    s.said = {}
    return s, e, pc


def _ctx(s, text, *, tells=(), door="turn", outcomes=()):
    return SimpleNamespace(scene=s, text=text, tells=tuple(tells), door=door,
                           outcomes=tuple(outcomes))


def _kinds(found):
    return {f.kind for f in found}


# --- the one derivation ------------------------------------------------------------------

def test_sight_is_the_light_model_at_the_players_square():
    s, e, pc = _night()
    assert L.sight(s)["level"] == "dim"
    s.clock_minutes = NOON
    assert L.sight(s) is None                       # day: nothing owed
    s, e, pc = _night(at=CAVE)
    seen = L.sight(s)
    assert seen["level"] == "dark" and "underground" in seen["why"]


def test_a_lit_sunrod_or_darkvision_means_the_player_is_not_in_poor_light():
    s, e, pc = _night()
    pc.apply_effect(ActiveEffect(name="Sunrod", kind="effect", key="light.carried",
                                 source="a sunrod", tags=("light.carried",),
                                 payload={"light": {"radius_ft": 30, "raised_ft": 60}}))
    assert L.sight(s) is None
    s, e, pc = _night(at=CAVE)
    pc.apply_effect(ActiveEffect(name="Darkvision", kind="effect",
                                 key="sense.darkvision.60", source="a draught",
                                 tags=("sense.darkvision.60",)))
    assert L.sight(s) is None


# --- the brief -----------------------------------------------------------------------------

def test_the_light_reaches_the_brief_in_a_night_fight_in_words_never_numbers():
    s, e, pc = _night()
    line = prompts.light_now(s)
    assert line.startswith("THE LIGHT (engine fact")
    assert "barely make out" in line and not re.search(r"\d", line)
    assert line in prompts.scene_now(s)
    s, e, pc = _night(at=CAVE)
    assert "pitch dark" in prompts.light_now(s)


def test_a_quiet_night_or_a_daylit_fight_is_not_told_about_the_light():
    """A line that is always there is a formula (`hour_now`'s reasoning): only a fight or
    a search in poor light carries it."""
    s, e, pc = _night(fight=False)
    assert prompts.light_now(s) == ""
    s, e, pc = _night(clock=NOON)
    assert prompts.light_now(s) == ""


def test_a_search_in_the_dark_is_told_too():
    s, e, pc = _night(fight=False)
    looked = SimpleNamespace(op="check", tell="Kesst Vayr's Perception check: 12.")
    assert "barely make out" in prompts.light_now(s, [looked])


def test_a_lit_player_in_the_night_is_told_where_the_light_ends():
    s, e, pc = _night()
    pc.apply_effect(ActiveEffect(name="Sunrod", kind="effect", key="light.carried",
                                 source="a sunrod", tags=("light.carried",),
                                 payload={"light": {"radius_ft": 30, "raised_ft": 60}}))
    line = prompts.light_now(s)
    # Never the effect's own name: live, a struck sunrod's was "Normal light 30 ft, one
    # step brighter out to 60 ft" — numbers in the author's-note slot.
    assert "the light in the player's hand lights the ground close around it" in line
    assert "past its edge is the night" in line and not re.search(r"\d", line)


# --- the check -----------------------------------------------------------------------------

def test_a_night_fight_beat_with_no_poor_sight_on_it_is_a_finding():
    s, e, pc = _night()
    text = ("You close on the thug and drive your rapier at his ribs. He twists aside and "
            "snarls. What do you do?")
    found = L.find(_ctx(s, text))
    assert _kinds(found) == {"light-left-off-the-page"}
    assert found[0].sentences == ("You close on the thug and drive your rapier at his ribs.",)
    shown = ("You close on the thug, a dark shape you can barely make out, and drive your "
             "rapier at his ribs. What do you do?")
    assert L.find(_ctx(s, shown)) == []


def test_a_blow_the_light_swallowed_must_be_shown_lost_in_the_light():
    """The tell's own words decide it: "finds nothing there — dim light". A plain miss is
    not enough; the blow and the gloom together are."""
    s, e, pc = _night()
    tell = "Kesst Vayr finds nothing there — dim light, 20% miss chance (14)."
    plain = "Your rapier misses the thug. He grins at you. What do you do?"
    found = L.find(_ctx(s, plain, tells=[tell]))
    assert _kinds(found) == {"light-miss-unshown"}
    assert found[0].sentences == ("Your rapier misses the thug.",)
    good = ("Your rapier stabs at a shape in the gloom and finds only empty air. "
            "What do you do?")
    assert L.find(_ctx(s, good, tells=[tell])) == []


def test_the_live_miss_whose_gloom_sat_in_another_sentence_is_a_finding():
    """Live, 2026-10-06, the great square at night, the player's swing lost to the dim
    light: the miss sentence had no gloom, and a later sentence's "dim light" beside a
    "strike" passed it. The miss has to be shown lost in the light, in its own sentence."""
    s, e, pc = _night()
    tell = "Kesst Vayr finds nothing there — dim light, 20% miss chance (8)."
    text = ("The rapier's tip whistles through the air, missing his ribs by a hair's "
            "breadth as he ducks. The man is coming on you now, his eyes narrowed in the "
            "dim light, the heavy sap held ready for a second strike. What do you do?")
    found = L.find(_ctx(s, text, tells=[tell]))
    assert _kinds(found) == {"light-miss-unshown"}
    assert found[0].sentences[0].startswith("The rapier's tip whistles")


def test_somebody_elses_blow_lost_in_the_dark_is_held_on_their_outcome_line_too():
    s, e, pc = _night(at=CAVE)
    tell = "the thug finds nothing there — darkness, 50% miss chance (31)."
    text = "The thug lunges at you with his sap and misses."
    found = L.find(_ctx(s, text, tells=[tell], door="outcome"))
    assert _kinds(found) == {"light-miss-unshown"}
    fixed, notes = L.backstop(_ctx(s, text, tells=[tell], door="outcome"), text, found)
    added = L.authored_in(fixed)
    assert added and added[0] in L.POOL["theirs:dark"], fixed
    assert L.find(_ctx(s, fixed, tells=[tell], door="outcome")) == []


def test_through_the_real_door_a_thugs_blow_lost_in_the_dim_reaches_the_page(monkeypatch):
    """`narrate_outcome`, the NPC loop's call for a creature's consequence beat. Live,
    2026-10-06: the truth pass wrote the thug's miss into the gloom, then the wrong-actor
    rewrite later in the groom rewrote the passage without it and the beat shipped as
    "passes harmlessly through the space where you would have been". The beat is held to
    the light once more as it ships; with every repair call down, the backstop writes it."""
    from gm import agent as agent_mod
    from gm import client

    from test_wrong_actor import _World

    res = None
    for seed in range(1, 80):
        s, e, pc = _night()
        e.dice = Dice(seed=seed)
        res = e.run(e.validate([{"op": "attack", "actor": "c1", "target": "pc",
                                 "because": "he swings"}]))
        if L.light_misses([o.tell for o in res.outcomes]):
            break
    gm = agent_mod.GMAgent(_World(), e)
    calls = []

    def chat(messages, model, *a, **kw):
        calls.append(messages)
        if len(calls) == 1:
            return client.Reply("The thug swings his sap at you, and the blow misses.",
                                0.1, model)
        raise client.ModelUnavailable("down")

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    text, attempt = gm.narrate_outcome("", res.outcomes, "the thug acts",
                                       rewrite=False, acting="the thug")
    assert any(line in text for line in L.POOL["theirs:dim"]), text
    assert L.find(_ctx(s, text, tells=[o.tell for o in res.outcomes],
                       door="outcome")) == []
    assert any(line in gm.last_added for line in L.POOL["theirs:dim"])


def test_a_sunlit_sentence_or_the_rule_printed_in_a_dark_fight_is_a_contradiction():
    s, e, pc = _night()
    for bad in ("The midday sun beats down as you circle the thug.",
                "Daylight glints off his blade as you circle.",
                "You lunge, but the 20% miss chance of the dim light saves him."):
        text = f"{bad} What do you do?"
        found = L.find(_ctx(s, text))
        assert "light-contradicted" in _kinds(found), bad
    # A torch's glare is the torch's, not the sun's.
    ok = "The torch's glare throws your shadow long; beyond it is only darkness."
    assert "light-contradicted" not in _kinds(L.find(_ctx(s, ok)))


def test_every_authored_line_is_recognised_by_the_detector_that_writes_it():
    """The backstop must never be flagged by its own check, the shape `body_shown` holds
    (an authored line the detector cannot read would be written twice)."""
    for cell, pool in L.POOL.items():
        for line in pool:
            assert L.SIGHT.search(line), (cell, line)
            if not cell.startswith("gloom"):
                assert L._miss_shown(line), (cell, line)
            assert not re.search(r"\d", line)


def test_the_backstop_writes_once_least_recently_used_and_the_page_then_passes():
    s, e, pc = _night()
    text = "You close on the thug and drive your rapier at his ribs. What do you do?"
    seen = []
    for _ in range(3):
        fixed, notes = L.backstop(_ctx(s, text), text, L.find(_ctx(s, text)))
        assert L.find(_ctx(s, fixed)) == [], fixed
        assert fixed.rstrip().endswith("What do you do?")
        seen.append(L.authored_in(fixed)[0])
    assert len(set(seen)) == 3                          # never the same line twice running


def test_the_tell_the_check_reads_is_the_one_the_engine_writes():
    """The detector keys on "finds nothing there — dim light|darkness": read off a swing
    the engine really rolled at night (behaviour, not the source text — the suite's
    getsource ceiling), the thug swinging at the player until the light decides one."""
    found = []
    for seed in range(1, 80):
        s, e, pc = _night()
        e.dice = Dice(seed=seed)
        res = e.run(e.validate([{"op": "attack", "actor": "c1", "target": "pc",
                                 "because": "he swings"}]))
        found = L.light_misses([o.tell for o in res.outcomes])
        if found:
            break
    assert found and found[0]["why"] == "dim light", "no swing was lost to the light"
    assert found[0]["who"].lower().endswith("the thug")
    assert L.light_misses(["The Alchemist's Fire finds nothing there — dim light, 20% "
                           "miss chance (3)."])[0]["why"] == "dim light"


# --- the doors lane C left open --------------------------------------------------------------

def test_extinguish_and_break_free_have_doors_in_a_fight():
    """Lane C built both ops and left them out of every fight list: a creature on fire or
    glued could not be sampled putting itself out, and the bar had no button."""
    from play.views import _COMBAT_OPS

    assert {"extinguish", "break_free"} <= set(prompts._FIGHT_OPS)
    assert {"extinguish", "break_free"} <= set(prompts._CREATURE_OPS)
    assert {"extinguish", "break_free"} <= _COMBAT_OPS
    schema = prompts.turn_schema(fighting=True, refs=("pc", "c1"))
    ops = schema["properties"]["intents"]["items"]["properties"]["op"]["enum"]
    assert "extinguish" in ops and "break_free" in ops


def test_a_burning_or_glued_creatures_turn_says_so_with_the_op_that_answers_it():
    """`burning` is an effect, not a condition: the turn prompt's "conditions: none" line
    never said a creature was on fire."""
    s, e, pc = _night()
    thug = s.actors["c1"]
    assert prompts.stuck_note(thug) == ""
    e.run(e.validate([{"op": "burn", "actor": "c1", "params": {"to": "c1", "dice": "1d6"}}],
                     origin="author:test"))
    note = prompts.stuck_note(thug)
    assert "ON FIRE" in note and '"op": "extinguish", "actor": "c1"' in note
    msgs = prompts.npc_turn_messages("brief", [], "c1", thug, 2)
    assert "ON FIRE" in msgs[-1]["content"]


def test_all_skills_is_a_skill_target_and_heroism_is_one_line():
    """Lane D wrote heroism's "+2 morale bonus on ... skill checks" as 35 skill_mod lines
    because the vocabulary refused `all`, which `Actor.skill_modifiers` has always read."""
    import json

    from rules import effectspec

    assert "all" in {v["id"] for v in effectspec.VOCAB["skill"]}
    rows = json.load(open("content/materials/alchemist-spell-potions.json",
                          encoding="utf-8"))
    rows = rows.get("potions", rows) if isinstance(rows, dict) else rows
    hero = next(r for r in rows if r["id"] == "potion-of-heroism")
    skills = [x for x in hero["effects"] if x["type"] == "skill_mod"]
    assert skills == [{"type": "skill_mod", "target": "all", "amount": 2,
                       "bonus_type": "morale",
                       "duration": {"amount": 50, "unit": "minute"}}]
