"""The surprise round (CRB, Combat, "Surprise"; rules/surprise.py).

Measured 2026-11-22 on integrate/0.5.1-impl b30999c3, before it was built: there was no
surprise round at all (docs/implementation-audit-2026-11-22.md, skills gap 4, and the
Perception card's own `not_yet`). A player hidden by a won Stealth check who stabbed a thug
that had never found them got the same opening as a brawl begun face to face; and every
creature that came on the party from the road, the wild, the water or a lair handed the
PLAYER the first turn (`_ensure_encounter(pc.ref, ...)` at eleven arrival doors), so an
ambush never caught anybody.

Every test drives the engine's own doors and reads the states and the tells.
"""
from __future__ import annotations

from rules import awareness, states, surprise
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


class _Faces(Dice):
    """Every d20 whose label holds a key lands on that key's face; the rest on `rest`."""

    def __init__(self, faces: dict | None = None, rest: int = 10):
        super().__init__(seed=20261122)
        self.faces, self.rest = dict(faces or {}), rest

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if str(notation).lstrip("1").startswith("d20"):
            face = next((f for k, f in self.faces.items() if k in (label or "")), self.rest)
            return self.given(face, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _room(faces=None, rest: int = 10):
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    return scene, Engine(scene, _Faces(faces, rest)), scene.get("pc"), scene.get("c1")


def _run(engine, *raws):
    return engine.run(engine.validate([dict(r, visibility="hidden") for r in raws]))


class _Total:
    def __init__(self, total):
        self.total = total


def _hide(engine, who, result=40):
    """A Stealth check won and held, through the engine's own door for it."""
    engine._stealth_lands(who, _Total(result), None, True)
    assert who.has_state(awareness.HIDDEN)


def test_a_hidden_player_who_strikes_an_unaware_thug_gets_the_surprise_round():
    """The player ambushes a thug: hidden by Stealth, the thug never found them. The fight
    opens with the thug surprised (no action, flat-footed) and the player holding the
    surprise round's one action — told to the narrator, laid as two conditions."""
    scene, engine, pc, thug = _room({"Kesst": 15, "initiative": 10})
    _hide(engine, pc)
    res = _run(engine, {"op": "attack", "actor": "pc", "target": "c1", "because": "ambush"})
    assert thug.has_state(states.SURPRISED) and not thug.can_act()
    assert pc.has_state(states.ONE_ACTION_TURN) and pc.can_act()
    told = [o for o in res.outcomes if o.op == "surprise"]
    assert told and "Surprise round" in told[0].tell and thug.name in told[0].tell
    # Said in the batch, right behind the outcome that opened the fight. The first cut held
    # it for the batch's end, and live (2026-11-22) the player's blow suspended for their
    # die, resumed on a new Engine, and the surprise round was never told at all.
    at = res.outcomes.index(told[0])
    assert any(e.get("kind") == "battle_joined" for e in res.outcomes[at - 1].effects)
    assert engine._flat_footed(thug)


def test_both_aware_means_no_surprise_round():
    """Face to face, nobody hidden: "If no one or everyone starts the battle aware, there is
    no surprise round." Nothing is laid and nothing is said of one."""
    scene, engine, pc, thug = _room()
    res = _run(engine, {"op": "attack", "actor": "pc", "target": "c1", "because": "brawl"})
    assert scene.in_encounter
    assert not any(a.has_state(states.SURPRISED) or a.has_state(states.ONE_ACTION_TURN)
                   for a in scene.actors.values())
    assert not any(o.op == "surprise" for o in res.outcomes)


def test_a_thug_who_had_found_the_hider_is_not_surprised():
    """Awareness is the hidden-state machinery's answer: a pinpoint (`knows.where`) on the
    hider means the thug saw it coming."""
    scene, engine, pc, thug = _room()
    scene.positions["pc"], scene.positions["c1"] = (6, 10), (7, 10)
    _hide(engine, pc)
    awareness.pinpoint(scene, thug, pc, "noticed")
    _run(engine, {"op": "attack", "actor": "pc", "target": "c1", "because": "ambush"})
    assert scene.in_encounter and not surprise.running(scene)


def test_the_surprise_round_allows_one_action_and_refuses_a_full_attack_with_the_reason():
    """CRB: the aware "each take a standard or move action during the surprise round". The
    player's full attack is refused in words; a second act after the first is refused."""
    scene, engine, pc, thug = _room()
    engine._ensure_encounter("pc", "c1")
    thug.add_condition(surprise.SURPRISED_KEY, rounds=1, source=surprise.ORIGIN)
    pc.add_condition(surprise.ROUND_KEY, rounds=1, source=surprise.ORIGIN)
    assert surprise.running(scene)
    full = _run(engine, {"op": "attack", "actor": "pc", "target": "c1", "because": "all in",
                         "params": {"full_attack": True}})
    refused = [o for o in full.outcomes if o.status == "refused"]
    assert refused and "Surprise round" in refused[0].tell and "full attack" in refused[0].tell
    scene.standard_spent["pc"] = scene.round
    again = _run(engine, {"op": "attack", "actor": "pc", "target": "c1", "because": "more"})
    assert any(o.status == "refused" and "spent" in o.tell for o in again.outcomes)


def test_a_creatures_full_attack_in_the_surprise_round_is_one_blow():
    """A creature's turn is the model's choice; a refusal would waste the round it ambushed
    for. Its full attack is made one blow (`_one_action_refusal`)."""
    scene, engine, pc, thug = _room()
    engine._ensure_encounter("c1", "pc")
    thug.add_condition(surprise.ROUND_KEY, rounds=1, source=surprise.ORIGIN)
    raw = {"op": "attack", "actor": "c1", "target": "pc", "params": {"full_attack": True}}
    assert engine._one_action_refusal(raw) is None
    assert raw["params"]["full_attack"] is False


def test_the_unaware_are_walked_past_and_the_round_ends_at_the_top_of_the_order():
    """The surprised do not act in the surprise round; at the wrap the one ticker ends both
    states, and the first regular round is everybody's."""
    scene, engine, pc, thug = _room()
    engine._ensure_encounter("pc", "c1")
    scene.initiative = [("pc", 20), ("c1", 5)]
    scene.turn = 0
    thug.add_condition(surprise.SURPRISED_KEY, rounds=1, source=surprise.ORIGIN)
    pc.add_condition(surprise.ROUND_KEY, rounds=1, source=surprise.ORIGIN)
    start = scene.round
    assert scene.advance_turn() == "pc"            # the thug's slot is passed over
    assert scene.round == start + 1
    assert not surprise.running(scene)
    assert scene.advance_turn() == "c1"


def test_an_ambush_that_beats_the_partys_perception_takes_the_turn_from_the_player():
    """The road ambush: the waiting side's Stealth against the player's Perception, both the
    engine's secret dice. Beaten, the player is surprised and the turn goes to the first
    aware combatant with nobody's turn yet taken, so the creature loop lands ON them."""
    scene, engine, pc, thug = _room({"Stealth, lying in wait": 20,
                                     "Perception, against an ambush": 1})
    engine._ensure_encounter("pc", target="c1", ambush=True)
    assert pc.has_state(states.SURPRISED) and thug.has_state(states.ONE_ACTION_TURN)
    assert scene.current_ref() == "c1" and scene.turn_is_next
    assert "pc" not in scene.acted
    assert scene.advance_turn() == "c1"


def test_an_ambush_the_player_spots_is_no_surprise():
    scene, engine, pc, thug = _room({"Stealth, lying in wait": 1,
                                     "Perception, against an ambush": 20})
    engine._ensure_encounter("pc", target="c1", ambush=True)
    assert scene.in_encounter and not surprise.running(scene)
    assert scene.current_ref() == "pc"


def test_a_fight_ended_inside_the_surprise_round_leaves_nobody_surprised():
    """Out of a fight nothing ticks rounds, so `end_encounter` lifts both states: the thug
    would otherwise stand unable to act in the street."""
    scene, engine, pc, thug = _room({"Stealth, lying in wait": 20,
                                     "Perception, against an ambush": 1})
    engine._ensure_encounter("pc", target="c1", ambush=True)
    scene.end_encounter()
    assert not pc.has_state(states.SURPRISED) and not thug.has_state(states.ONE_ACTION_TURN)


def test_a_declared_fight_asks_the_same_question():
    """`begin_encounter` (a GM-declared or staged fight) goes through `surprise.begin` too:
    one decision for every door a fight opens by."""
    scene, engine, pc, thug = _room()
    _hide(engine, pc)
    res = _run(engine, {"op": "begin_encounter", "because": "it starts",
                        "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}})
    assert thug.has_state(states.SURPRISED)
    assert scene.current_ref() == "pc"
    assert any("Surprise round" in o.tell for o in res.outcomes)
