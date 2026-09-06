"""Travel is the scene transition, and a transition sheds its cast.

The ghost this prevents, from the 2026-08-22 playtest: a gatekeeper wounded in the guild
yard travelled inside the scene to the forest — still in an initiative order that never
ended — and took a "holds back" NPC turn after every player turn for the rest of the
session. When the fiction then aimed attacks at forest strangers, every one landed on
him, because he was the only body the engine had.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from tests._places import stand_on


@pytest.fixture
def yard():
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the gatekeeper"))
    s.add(instantiate("thug", scene=s, name="the bravo"))
    return s, Engine(s, Dice(seed=11))


def travel(engine, biome="forest", **params):
    return engine.run(engine.validate([
        {"op": "travel", "because": "she makes for the treeline",
         "params": {"biome": biome, **params}}]))


# --- who counts as fallen ---------------------------------------------------------------

def test_a_petrified_enemy_is_not_swept_up_as_a_corpse(yard):
    """`state.down` means two things at once — "beyond objecting, therefore lootable"
    (six conditions) and "a body on the floor whose story resolves" (four) — and the
    three sites that DELETE a creature asked the wide one.

    So a petrified enemy at full hit points, and a Strength-drained helpless one, aged
    out of the scene over a grace of two turns and were handed to `Scene.depart`, which
    strips an actor from actors, initiative, sides, zones, guards and the reaction
    ledger. The statue and whatever it was carrying simply stopped existing. Walking out
    of a room does not delete a statue either, so `leave_behind` asked wrongly too.

    `state.down.fallen` is the narrow half; the loot gate keeps asking the family.
    """
    s, engine = yard
    statue = s.actors["c1"]
    statue.add_condition("petrified", source="a basilisk")
    assert statue.hp > 0

    for _ in range(4):
        engine.tidy_the_fallen()
    assert "c1" in s.actors, "a petrified enemy was tidied away as a body"

    # Still lootable, which is the whole reason the family stays wide.
    assert statue.has_state("state.down")

    # But walking out leaves it: the two doors ask different questions, and the first
    # version of this test asserted the wrong half. `tidy_the_fallen` is bodies ageing
    # out of a room the party is STILL IN, so a statue standing there is not a body to
    # clear away. Walking out is a `travel`, and a petrified enemy cannot follow —
    # measured before this was split, the statue travelled to the next biome with the
    # party and stood in the scene panel there for the rest of the campaign. Under
    # containment it does not have to be shed at all: it stays where it stands.
    stall = s.at
    travel(engine)
    assert "c1" not in s.actors, "the statue followed the party out of the room"
    assert s.people["c1"].at == stall, "the statue stopped existing instead of staying"


def test_a_real_body_still_ages_out(yard):
    """The other side of the same line: narrowing it must not leave corpses standing
    around forever, which is the ghost this module exists to prevent."""
    s, engine = yard
    body = s.actors["c1"]
    body.hp = -9
    body.apply_hp_state()
    assert body.has_state("state.down.fallen")

    for _ in range(4):
        engine.tidy_the_fallen()
    assert "c1" not in s.actors, "a corpse stayed in the scene"


def test_a_stabilised_body_does_not_walk_to_the_next_biome(yard):
    """Travel named four literal keys — dead, dying, unconscious — and forgot `stable`,
    so a body that had stopped bleeding came along to the forest."""
    s, engine = yard
    body = s.actors["c1"]
    body.hp = -2
    body.apply_hp_state()
    body.remove_condition("dying")
    body.add_condition("stable", source="a stabilisation check")

    travel(engine)
    assert "c1" not in s.actors, "a stabilised body travelled with the party"


# --- changing room without changing ground ------------------------------------------------

def test_leaving_a_room_is_a_scene_change_even_on_the_same_ground(yard):
    """Found by playing. The player left a merchant's building for the square, the GM
    narrated the square and four men in it, and the next beat was back inside by the
    fire with somebody several turns dead.

    `travel` modelled the GROUND, and a stall and the square outside it are both urban —
    so the move reached the engine as nothing at all. The merchant stayed in the scene,
    the brief went on describing his stall, and the world had no way to be told the room
    was over. The op takes a `place` now, and a change of room sheds its cast exactly as
    a change of biome always did.
    """
    s, engine = yard
    start = engine.here()
    other = next(p for p in engine.places() if p.id != start.id)
    got = engine.run(engine.validate([
        {"op": "travel", "because": "she walks out",
         "params": {"place": other.name}}]))

    assert engine.here().id == other.id
    assert s.biome == "urban", "changing room must not change the ground underfoot"
    assert list(s.actors) == ["pc"], "the people of the old room followed her out"
    assert other.name in got.outcomes[0].tell


def test_an_escort_still_comes_along_between_rooms(yard):
    s, engine = yard
    engine.run(engine.validate([
        {"op": "travel", "because": "they walk out together",
         "params": {"place": next(p.name for p in engine.places()
                                   if p.id != engine.here().id),
                    "with": ["c1"]}}]))
    assert set(s.actors) == {"pc", "c1"}


def test_new_ground_is_a_place_of_its_own(yard):
    """A stale room name would anchor the prose to a building a day's walk behind — and
    a blank one left the party nowhere. New ground is that region's first place, with
    the ground inside the id, and the room they left keeps its people."""
    from rules import places

    s, engine = yard
    was = engine.here().id
    travel(engine)
    assert s.biome == "forest"
    assert places.terrain_of(s.at) == "forest" and s.at != was
    assert engine.here().id == s.at
    assert {a.at for a in s.people.values() if not a.is_pc} == {was}


def test_travel_with_neither_ground_nor_room_says_what_to_type(yard):
    """The contract's rule: a validator names the fix. Measured across the twelve real
    campaigns, `travel: missing required param(s) biome` fired 13 times and the next
    attempt resolved it 38% of the time — the model wanted a place and the op only
    offered ground."""
    s, engine = yard
    with pytest.raises(IntentError) as e:
        engine.run(engine.validate(
            [{"op": "travel", "because": "she goes", "params": {}}]))
    assert '"biome"' in str(e.value) and '"place"' in str(e.value)


# --- departing --------------------------------------------------------------------------

def test_depart_removes_every_trace(yard):
    """Five structures name an actor — actors, zones, initiative, sides, the reaction
    ledger — and a removal that missed one would leave a ghost acting from it."""
    s, engine = yard
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"pc": ["pc"],
                                                      "them": ["c1", "c2"]}}}]))
    s.reacted["c1:aoo"] = 1
    gone = s.depart("c1")
    assert gone.name == "the gatekeeper"
    assert "c1" not in s.actors and "c1" not in s.zones
    assert all(r != "c1" for r, _ in s.initiative)
    assert "c1" not in s.sides["them"]
    assert not any(k.startswith("c1:") for k in s.reacted)


def test_depart_keeps_the_turn_on_the_same_creature(yard):
    """The turn pointer is an index into a list that just got shorter; without the fix a
    removal handed somebody else's turn to the wrong side of the fight."""
    s, engine = yard
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"pc": ["pc"],
                                                      "them": ["c1", "c2"]}}}]))
    order = [r for r, _ in s.initiative]
    current = s.current_ref()
    other = next(r for r in order if r not in ("pc", current))
    s.depart(other)
    assert s.current_ref() == current


def test_the_pc_cannot_be_departed(yard):
    s, _ = yard
    assert s.depart("pc") is None
    assert "pc" in s.actors


# --- travelling -------------------------------------------------------------------------

def test_travel_leaves_the_cast_behind(yard):
    """The gatekeeper does not follow you to the forest."""
    s, engine = yard
    r = travel(engine)
    assert list(s.actors) == ["pc"]
    assert s.biome == "forest"
    assert "Left behind: the gatekeeper, the bravo." in r.outcomes[0].tell


def test_travel_ends_the_fight_it_walks_away_from(yard):
    """The playtest's encounter never ended: the initiative order crossed a biome and the
    ghost in it acted every turn thereafter."""
    s, engine = yard
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"pc": ["pc"],
                                                      "them": ["c1", "c2"]}}}]))
    assert s.in_encounter
    r = travel(engine)
    assert not s.in_encounter
    assert s.initiative == [] and s.sides == {}
    assert "The fight is left behind." in r.outcomes[0].tell


def test_an_escort_named_in_with_comes_along(yard):
    """How the GM says somebody travels with the party — by ref or by name."""
    s, engine = yard
    travel(engine, **{"with": ["c2"]})
    assert set(s.actors) == {"pc", "c2"}


def test_the_dying_stay_where_they_fell_even_when_named(yard):
    """A dying escort is not an escort. They stay, whatever the intent says.

    Set to a real dying state rather than to exactly 0 hit points, which is
    *disabled* — conscious and walking, and a perfectly good escort.
    """
    s, engine = yard
    s.actors["c2"].hp = -3
    s.actors["c2"].apply_hp_state()
    travel(engine, **{"with": ["c2"]})
    assert set(s.actors) == {"pc"}


def test_travel_within_the_same_biome_sheds_nobody(yard):
    """Crossing town is not leaving it: the cast of an urban scene survives urban
    travel, and only a change of ground is a transition."""
    s, engine = yard
    travel(engine, biome="urban")
    assert set(s.actors) == {"pc", "c1", "c2"}


# --- an invented destination is a repair, then a printed refusal, never a 502 --------------

def test_the_gms_dressing_of_a_real_place_finds_the_place():
    """Measured at the table, 2026-09-06: the plan wrote `travel` to "the merchant's
    gate" for a scene whose places were the market, the gate, the tavern, the temple,
    the back streets and the workshops; the exact match failed and the page said 502.
    The last word decides, and only when exactly one place ends in it."""
    from dataclasses import dataclass

    from rules import places

    @dataclass
    class P:
        id: str
        name: str

    known = [P("a", "the market"), P("b", "the gate"), P("c", "the back streets"),
             P("d", "the street"), P("e", "the workshops")]
    assert places.find(known, "the merchant's gate").id == "b"
    assert places.find(known, "the old market").id == "a"
    assert places.find(known, "the workshop").id == "e"
    assert places.find(known, "the north street") is None     # two end in "street"
    assert places.find(known, "the harbour") is None


def test_an_unknown_destination_is_refused_at_validate_with_the_places_named(yard):
    """Where the plan's repair loop can read it. The raise used to live in `run`, so
    the first sight of the bad place was after planning was over — a 502."""
    from rules.intents import IntentError

    _, engine = yard
    try:
        engine.validate([{"op": "travel", "actor": "pc", "because": "t",
                          "params": {"place": "the crystal palace"}}], origin="author:test")
    except IntentError as exc:
        assert "there is no 'the crystal palace' here" in str(exc)
        assert "Name one of:" in str(exc)
    else:
        raise AssertionError("an invented destination validated")


def test_a_bad_place_that_reaches_run_is_a_printed_refusal_not_a_raise(yard):
    """The floor under the floor: `validate` skipped (a save, a test), the op runs,
    and the player reads a sentence instead of a gateway error."""
    from rules.intents import Intent

    _, engine = yard
    intent = Intent(op="travel", actor="pc", because="t",
                    params={"place": "the crystal palace"}, visibility="player", id="i1")
    res = engine.run([intent])
    out = res.outcomes[0]
    assert "There is no the crystal palace here to go to" in out.tell
    assert "From here you can reach" in out.tell
