"""Where the prose puts a person is where the map puts them.

Reported at the table, 2026-09-06, with the map open: a servant "beside you", a
hooded man "at the far end of the corridor", a merchant and two guards — all five
promoted to the same zone and laid out as one column three squares off. "This is
not how the people should be lined up according to the prose."
"""
from __future__ import annotations

from gm import judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import SQUARES_BY_ZONE, Engine, Scene
from rules.sheet import load_pc


def _mentions(beat: str) -> dict[str, str]:
    return {m.group(1): judgement.zone_of_mention(beat, *m.span())
            for m in judgement._CAST_INTRO.finditer(beat)}


def test_the_words_around_a_person_say_which_zone_they_stand_in():
    """The engine's three words — engaged, near, far — read off the phrases the
    prose actually uses, on either side of the person, and never across a full
    stop: the far end belongs to the man, not to the servant in the next sentence."""
    beat = ("He stands at the far end of the corridor, a hooded man with a chain. "
            "Beside you, the servant carrying jugs has stopped. "
            "A merchant watches from across the square. "
            "A guard grabs your arm.")
    zones = _mentions(beat)
    assert zones["hooded man"] == "far"
    assert zones["servant"] == "engaged"
    assert zones["merchant"] == "far"
    assert zones["guard"] == "engaged"
    # Nothing said means the engine's own default.
    assert _mentions("A woman is there.")["woman"] == "near"


def test_a_noted_person_is_promoted_into_the_zone_the_prose_gave_them():
    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    beat = ("A hooded man waits at the far end of the hall. "
            "Beside you, a servant has stopped with two jugs.")
    added = judgement.note_cast(s, beat, turn=2)
    made = judgement.promote_cast(s, added)
    assert len(made) == 2
    by_name = {s.actors[e["ref"]].name: s.zones[e["ref"]]
               for e in s.cast if e.get("ref")}
    assert by_name["hooded man"] == "far"
    assert by_name["servant"] == "engaged"


def test_the_battlefield_lays_each_person_at_their_own_zone_and_not_in_one_column():
    """Before: everyone not on the player's side went in one column at one distance,
    rows counting downward — five in a line. Now the servant who was beside you is
    one square off, the man at the far end is eight, and the rows fan out from the
    player's own row."""
    s = Scene()
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    near = s.add(instantiate("guildhand", scene=s, name="the merchant"), zone="near")
    close = s.add(instantiate("guildhand", scene=s, name="the servant"), zone="engaged")
    away = s.add(instantiate("watchman", scene=s, name="the hooded man"), zone="far")
    engine = Engine(s, Dice(seed=1))
    engine._lay_battlefield({"a": [pc.ref], "b": [near.ref, close.ref, away.ref]})
    px, py = s.positions[pc.ref]
    dx = {r: s.positions[r][0] - px for r in (near.ref, close.ref, away.ref)}
    assert dx[close.ref] == SQUARES_BY_ZONE["engaged"] == 1
    assert dx[near.ref] == SQUARES_BY_ZONE["near"] == 3
    assert dx[away.ref] == SQUARES_BY_ZONE["far"] == 8
    rows = sorted(s.positions[r][1] - py for r in (near.ref, close.ref, away.ref))
    assert rows == [-1, 0, 1], rows


def test_a_fight_is_with_the_one_you_swung_at_and_the_rest_are_bystanders():
    """"fix the sides so bystanders aren't put on the enemy side." A servant standing
    beside the player was laid out on the enemy side of a fight the player picked
    with a hooded man: every standing non-player went on "them". The fight is with
    the target; the others are on the map, off the initiative, on no side."""
    s = Scene()
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    servant = s.add(instantiate("guildhand", scene=s, name="the servant"), zone="engaged")
    merchant = s.add(instantiate("guildhand", scene=s, name="the merchant"), zone="near")
    hooded = s.add(instantiate("watchman", scene=s, name="the hooded man"), zone="far")
    engine = Engine(s, Dice(seed=2))
    assert engine._ensure_encounter(pc.ref, target=hooded.ref)
    assert s.sides == {"pc": [pc.ref], "them": [hooded.ref]}
    fighting = {r for r, _ in s.initiative}
    assert fighting == {pc.ref, hooded.ref}
    # Bystanders are still on the board, at their own zones, on no side.
    for r in (servant.ref, merchant.ref):
        assert r in s.positions, r
        assert not any(r in refs for refs in s.sides.values())
    px = s.positions[pc.ref][0]
    assert s.positions[servant.ref][0] - px == 1
    assert s.positions[hooded.ref][0] - px == 8


def test_a_foes_own_kind_come_in_with_them_and_civilians_stay_out():
    """"make bystanders join the fight when they should." The pair of guards the
    prose promoted together fight together: strike one and the other is on the
    initiative. The merchant across the yard is not a third guard."""
    s = Scene()
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    g1 = s.add(instantiate("watchman", scene=s, name="guards"), zone="near")
    g2 = s.add(instantiate("watchman", scene=s, name="guard"), zone="far")
    merchant = s.add(instantiate("guildhand", scene=s, name="the merchant"), zone="near")
    engine = Engine(s, Dice(seed=3))
    assert engine._ensure_encounter(pc.ref, target=g1.ref)
    assert set(s.sides["them"]) == {g1.ref, g2.ref}
    assert merchant.ref not in s.sides["them"]
    assert {r for r, _ in s.initiative} == {pc.ref, g1.ref, g2.ref}


def test_swinging_at_a_bystander_brings_them_in():
    s = Scene()
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    thug = s.add(instantiate("thug", scene=s, name="the thug"), zone="engaged")
    merchant = s.add(instantiate("guildhand", scene=s, name="the merchant"), zone="near")
    engine = Engine(s, Dice(seed=4))
    assert engine._ensure_encounter(pc.ref, target=thug.ref)
    assert merchant.ref not in s.sides["them"]
    intents = engine.validate([{"op": "attack", "actor": "pc", "target": merchant.ref,
                                "because": "test"}], origin="author:test")
    engine.run(intents)
    assert merchant.ref in s.sides["them"]
    assert merchant.ref in {r for r, _ in s.initiative}


def test_the_prose_can_put_a_bystander_into_the_fight():
    """"The second guard draws and comes at you" is a second guard on the initiative;
    "the merchant flinches as the guard draws" is not a merchant in the fight."""
    s = Scene()
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    thug = s.add(instantiate("thug", scene=s, name="the thug"), zone="engaged")
    guard = s.add(instantiate("watchman", scene=s, name="the hooded guard"), zone="far")
    merchant = s.add(instantiate("guildhand", scene=s, name="the merchant"), zone="near")
    engine = Engine(s, Dice(seed=5))
    engine._ensure_encounter(pc.ref, target=thug.ref)
    beat = ("The merchant flinches as the hooded guard draws a cudgel and comes at you. "
            "The thug grins.")
    assert judgement.joiners(s, beat) == [guard.ref]
    assert engine.join_fight(guard.ref)
    assert guard.ref in s.sides["them"] and merchant.ref not in s.sides["them"]
    # Already in: nothing to join twice.
    assert judgement.joiners(s, beat) == []
