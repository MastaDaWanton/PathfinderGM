"""Playtest 2026-11-16, items 1, 2, 3, 4, 32 and 37: threats, talk and the planner.

Beat 179 (marked): "I level my dagger at the bleeding captain and tell him to yield the
Red Gull to me or die." planned Blood Pool Manifestation (#1), told the say as "to the
effect that tell him to yield…" (#2), and read as two threats — the second an Intimidate
11 vs 11 at a deckhand (#3) whose demand was hand_over, "has no coin on them" (#4).

Beat 214 (marked): "I climb back out of the crypt and go down into the city's sewers" rolled
Stealth "18 vs 8", the DC lowered "for a favourable circumstance: favorable" (#32).

Beat 223 (turn_log row 811): "I climb out of the sewers and walk to the gardens" planned a
Stealth (refused, "the gardener is watching") and a way down (refused, "not at the great
square"), and both refusals reached the page (#37).
"""
from __future__ import annotations

import json

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene, reported_speech
from rules.intents import parse
from rules.sheet import from_dict, load_pc, to_dict


def _reading(*acts):
    return {"question": False, "claims": [], "actions": [dict(a, span=a.get("span", "x"))
                                                         for a in acts]}


# --- #32: a deed's check is backed by that deed ------------------------------------------

def test_a_climb_the_reading_called_a_walk_declares_no_check():
    """#32: "climb back out of the crypt" read `go`; the check detector read "climb" and the
    walk backed it, so the plan filled a check nobody asked for (it chose Stealth)."""
    from gm import interpret

    walk = _reading({"act": "go", "place": "the crypt", "within_place": True})
    assert interpret.supported(["check"], walk, check_skill="climb") == ([], ["check"])
    climb = _reading({"act": "athletics", "place": "the bell tower"})
    assert interpret.supported(["check"], climb, check_skill="climb") == (["check"], [])
    sneak = _reading({"act": "stealth", "place": "the docks"})
    assert interpret.supported(["check"], sneak, check_skill="stealth") == (["check"], [])


def test_the_declared_check_is_held_to_the_skill_the_words_declared():
    """#32: the declared check's skill was a free choice of every skill, and the model chose
    Stealth for a climb. Its circumstance was a bare string, so it could only ever come
    back as the band word ("favorable"), never a reason."""
    from gm import prompts

    schema = prompts.turn_schema(must_contain=("check",), skill="climb")
    body = schema["properties"]["declared"]["properties"]["check"]["properties"]["params"]
    assert body["properties"]["skill"]["enum"] == ["climb"]
    circ = body["properties"]["circumstance"]
    assert circ["type"] == "object" and set(circ["required"]) == {"value", "why"}
    free = prompts.turn_schema(must_contain=("check",))
    body = free["properties"]["declared"]["properties"]["check"]["properties"]["params"]
    assert "stealth" in body["properties"]["skill"]["enum"]


def test_a_plan_check_of_another_skill_does_not_stand_in_for_the_declared_one():
    """#37: the plan's own Stealth satisfied the declared check (detector: climb), so the
    climb was never merged and the sneak was."""
    from gm.agent import GMAgent

    raw = [{"op": "check", "actor": "pc", "params": {"skill": "stealth"}}]
    merged = GMAgent._merge_declared(
        raw, {"check": {"params": {"skill": "climb", "dc": "average"}}}, actor="pc")
    assert [r["params"]["skill"] for r in merged] == ["stealth", "climb"]
    same = GMAgent._merge_declared(
        [{"op": "check", "actor": "pc", "params": {"skill": "climb"}}],
        {"check": {"params": {"skill": "climb"}}}, actor="pc")
    assert len(same) == 1


def test_a_plan_walk_to_nowhere_takes_the_declared_place():
    """#37's live replay (snapshot of beat 228): "climb out of the sewers and walk to the
    great square" planned a bare `travel` beside a declared one naming the square, the bare
    one stood, and the engine refused "Nobody moves: where to?"."""
    from gm.agent import GMAgent

    merged = GMAgent._merge_declared(
        [{"op": "travel", "params": {}}],
        {"travel": {"params": {"place": "the great square"}}}, actor="pc")
    assert merged == [{"op": "travel", "params": {"place": "the great square"}}]


def test_a_circumstance_with_no_reason_is_dropped_and_recorded():
    """#32: "DC lowered by 2 to 8 for a favourable circumstance: favorable". A +2/-2 is for
    a named condition that helps or hinders; a reason that is the band word names none."""
    bare = parse({"op": "check", "actor": "pc", "params": {
        "skill": "climb", "dc": "average", "circumstance": {"value": "favorable"}}})
    assert "circumstance" not in bare.params and "circumstance" in bare.ignored_params
    word = parse({"op": "check", "actor": "pc", "params": {
        "skill": "climb", "dc": "average",
        "circumstance": {"value": "favorable", "why": "a favourable circumstance"}}})
    assert "circumstance" not in word.params
    told = parse({"op": "check", "actor": "pc", "params": {
        "skill": "climb", "dc": "average",
        "circumstance": {"value": "favorable", "why": "a knotted rope hangs down"}}})
    assert told.params["circumstance"]["value"] == "favorable"


# --- #37: an old intent is not renewed ---------------------------------------------------

def test_a_sneak_the_turn_does_not_name_is_dropped():
    """#37: "I climb out of the sewers and walk to the gardens" (athletics + go) carried a
    Stealth from earlier turns, refused "the gardener is watching" onto the page."""
    from gm import interpret

    reading = _reading({"act": "athletics", "place": "the sewers"},
                       {"act": "go", "place": "the gardens"})
    raw = [{"op": "travel", "params": {"place": "the gardens"}},
           {"op": "check", "actor": "pc", "params": {"skill": "stealth"}},
           {"op": "check", "actor": "pc", "params": {"skill": "climb"}},
           {"op": "check", "actor": "c3", "params": {"skill": "stealth"}}]
    kept, dropped = interpret.drop_unchosen_checks(raw, reading)
    assert dropped == ["stealth"]
    assert [r["params"].get("skill") for r in kept] == [None, "climb", "stealth"]
    sneaking = _reading({"act": "stealth", "place": "the gardens"})
    assert interpret.drop_unchosen_checks(raw, sneaking)[1] == []


def test_a_walk_to_known_places_ventures_nowhere():
    """#37: in the sewers, "climb out of the sewers and walk to the gardens" had the venture
    detector read "sewers" and plan a way down. Every move named a place already known."""
    from gm import interpret
    from rules.places import Place

    places = [Place(id="t~urban:the-gardens", name="the gardens", kind="urban"),
              Place(id="t~underground:the-great-square/the-sewers", name="the sewers",
                    kind="underground")]
    out = _reading({"act": "athletics", "place": "the sewers"},
                   {"act": "go", "place": "the gardens"})
    assert not interpret.ventures_somewhere_new(out, places)
    down = _reading({"act": "go", "place": "the old cistern"})
    assert interpret.ventures_somewhere_new(down, places)
    looking = _reading({"act": "search", "place": "the gardens"})
    assert interpret.ventures_somewhere_new(looking, places)


# --- #1: a passive is never planned as a use ---------------------------------------------

def _bender():
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "blood bending", "level": 1, "ranks": {}, "paths": ["battle blood"]})
    return from_dict(d, ref="pc")


def test_a_passive_the_words_never_used_is_struck_from_the_plan():
    """#1: a threat planned Blood Pool Manifestation's use; its tell said the character
    "attacks", and the page opened "As you strike". Swift Strikes is Battle Blood's
    passive in the shipped class file."""
    from gm import judgement

    scene = Scene()
    scene.add(_bender())
    raw = [{"op": "use_ability", "actor": "pc", "params": {"ability": "Swift Strikes"}},
           {"op": "say", "params": {"words": "yield"}}]
    assert [r["op"] for r in judgement.drop_unasked_passives(raw, ["say"], scene)] == ["say"]
    assert judgement.drop_unasked_passives(raw, ["use_ability"], scene) == raw


def test_a_passive_used_on_purpose_claims_no_blow():
    """#1: the tell "… attacks, and it does its work on the attack" said a blow was struck
    on a turn where nobody struck."""
    scene = Scene()
    scene.add(_bender())
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    e = Engine(scene, dice=Dice(seed=7))
    out = e.run(e.validate([{"op": "use_ability", "actor": "pc",
                             "params": {"ability": "swift strikes"},
                             "because": "test"}])).outcomes[-1]
    assert "always active" in out.tell and "attacks" not in out.tell


# --- #2: reported orders lose their frame ------------------------------------------------

def test_an_order_reported_is_told_as_what_they_are_to_do():
    """#2: "Vesna Kroll speaks, to the effect that tell him to yield the Red Gull to me or
    die". 0.3.8 dropped "tell X that", not "tell X to"."""
    said = reported_speech("Vesna Kroll", "", "tell him to yield the Red Gull to me or die.")
    assert said == "Vesna Kroll speaks, to the effect that he yield the Red Gull to me or die."
    named = reported_speech("Vesna Kroll", " to the captain",
                            "tell the captain to lower the sails.", "the captain")
    assert named.endswith("to the effect that the captain lower the sails.")
    # Not an order: "to" past the one spoken to is the words' own.
    assert reported_speech("Vesna Kroll", " to the guard", "tell the guard I go to the "
                           "market.", "the guard").endswith("that I go to the market.")


# --- #3, #4: one threat, one check -------------------------------------------------------

def test_one_threat_read_as_two_is_one_check_at_the_one_named():
    """#3/#4: the gesture and the words of one threat came back as two `threaten` acts; the
    second's "him" went to a deckhand, rolled a second Intimidate (11 vs 11), and its
    hand_over answered a demand to yield the ship with "has no coin on them". The live
    replay after the reader's example still split it (demand now yield), so the table
    holds it: one check per person threatened in a sentence."""
    from gm import acts_to_ops

    scene = Scene()
    scene.add(load_pc("fixtures/pc-kesst.json"))
    captain = scene.add(instantiate("thug", scene=scene, name="the captain"))
    deckhand = scene.add(instantiate("thug", scene=scene, name="a deckhand"))
    # As on the Red Gull: the captain held as "they", the deckhand as "he", so the finder
    # alone answers "him" with the deckhand.
    captain.pronouns, deckhand.pronouns = "they/them", "he/him"
    frame = _reading(
        {"act": "threaten", "target": "the captain", "demand": "yield",
         "span": "level my dagger at the captain"},
        {"act": "threaten", "target": "him", "says": "yield the Red Gull to me or die",
         "demand": "hand_over", "span": "tell him to yield the Red Gull to me or die"})
    built = [i for r in acts_to_ops.table(frame, scene) for i in r.intents]
    assert built == [{"op": "check", "actor": "pc", "target": captain.ref,
                      "params": {"skill": "intimidate", "demand": "yield"},
                      "because": "the player threatens the captain"}]


# --- the whole planner path ---------------------------------------------------------------

SNEAK = {"skill": "stealth", "circumstance": {"value": "favorable"}, "dc": "average"}

@pytest.mark.parametrize("declared", [{"check": {"params": SNEAK}}, {}])
def test_through_the_plan_a_climb_read_as_a_walk_rolls_nothing(monkeypatch, declared):
    """#32, end to end through `plan_turn` with the model answering as it did at beat 214:
    a declared Stealth "favorable" with no reason. Live replay after the first fix still
    rolled a Climb ("the player declared it; the dice decide it"): `inject_checks` read the
    same words the reading had already overruled."""
    from _a_truth import MARKET, scene_at
    from gm import agent as agent_mod
    from gm import interpret

    agent, _ = scene_at(MARKET, [("the gardener", "guildhand")])
    line = "I climb back out of the cellar."
    reading = {"question": False, "claims": [], "actions": [
        {"act": "go", "place": "the cellar", "within_place": True,
         "span": "climb back out of the cellar"}]}

    class _Reply:
        text = json.dumps({"narration": "", "declared": declared,
                           "intents": [{"op": "narrate_only"}]})
        seconds, model = 0.0, "fake"

        def json(self):
            return json.loads(self.text)

    monkeypatch.setattr(interpret, "ENABLED", True)
    monkeypatch.setattr(interpret, "interpret", lambda text, **kw: dict(reading))
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **kw: _Reply())
    try:
        plan = agent.plan_turn(line, history=[])
    finally:
        interpret._READINGS.clear()
    assert [i.op for i in plan.intents if i.op == "check"] == [], plan.intents


def test_through_the_plan_a_walk_out_to_a_known_place_ventures_nowhere(monkeypatch):
    """#37, end to end: "I climb out of the sewers and walk to …" read athletics + go, both
    to places already known. The live replay after the first fix (snapshot of beat 228) had
    the venture overruled and then put back by `inject_venture`, which also dropped the
    walk as "the same intent": the turn made a second "sewers" off the sewers."""
    from _a_truth import MARKET, scene_at
    from gm import agent as agent_mod
    from gm import interpret

    agent, _ = scene_at(MARKET)
    e = agent.engine
    here = next(p for p in e.places() if p.id == e.scene.at)
    other = next(p for p in e.places() if p.id != e.scene.at and not p.described_only)
    line = f"I climb out of the sewers and walk to {other.name}."
    reading = {"question": False, "claims": [], "actions": [
        {"act": "athletics", "place": here.name, "span": "climb out of the sewers"},
        {"act": "go", "place": other.name, "span": f"walk to {other.name}"}]}

    class _Reply:
        text = json.dumps({"narration": "", "declared": {
            "travel": {"params": {"place": other.name}},
            "venture": {"params": {"kind": "sewers"}}},
            "intents": [{"op": "travel", "params": {"place": other.name}}]})
        seconds, model = 0.0, "fake"

        def json(self):
            return json.loads(self.text)

    monkeypatch.setattr(interpret, "ENABLED", True)
    monkeypatch.setattr(interpret, "interpret", lambda text, **kw: dict(reading))
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **kw: _Reply())
    try:
        plan = agent.plan_turn(line, history=[])
    finally:
        interpret._READINGS.clear()
    ops = [i.op for i in plan.intents]
    assert "venture" not in ops and "travel" in ops, plan.intents
