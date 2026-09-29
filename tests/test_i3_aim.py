"""I3: casting with an aim, end to end — the words, the reading, the plan's schema, the engine.

Measured 2026-09-28 (docs/playtest-2026-09-28.md 21.2, Bobby's turn 12): "I cast burning
hands into the tree tops" was read `cast, object: burning hands, target: the tree tops` —
the treetops a *target*, as though a creature — and nothing turned the phrase into
anything a spell could be pointed at. And on the fix pass's G2 cast-area run (2026-09-29),
"I cast burning hands into the empty air above my head" was answered "Where do you aim
Burning Hands?" — asked of a sentence that said where.
"""
from __future__ import annotations

import pytest

import replays
from gm import interpret, prompts
from rules import areas, casting, grid as gridmod, spells as spells_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import from_dict, load_pc, to_dict
from tests._places import stand_on

BOBBY_READING = {"question": False, "claims": [], "actions": [
    {"act": "cast", "object": "burning hands", "target": "the tree tops"}]}


def caster(prepared=None, int_score=18):
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d["abilities"]["int"] = int_score
    d["prepared"] = {"burning-hands": 2} if prepared is None else prepared
    return from_dict(d, ref="pc")


def board(worlds, ground="forest", prepared=None, int_score=18, seed=4):
    row = (worlds.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    s.add(caster(prepared, int_score))
    man = s.add(instantiate("guildhand", scene=s, name="the man in a stained jerkin"))
    stand_on(s, ground)
    s.grid = gridmod.Grid(20, 20)
    s.positions["pc"], s.positions[man.ref] = (4, 7), (1, 8)
    return s, Engine(s, Dice(seed=seed), world=worlds), man.ref


def cast(e, **params):
    return e.run(e.validate([{"op": "cast", "actor": "pc", "because": "t",
                              "params": {"spell": "burning-hands", **params}}])).outcomes[0]


# --- the words -----------------------------------------------------------------------------------

@pytest.mark.parametrize("said, aim", [
    ("I cast burning hands into the empty air above my head", "dir:up"),
    ("I cast burning hands above my head", "dir:up"),
    ("burning hands into the air", "dir:up"),
    ("I send it up at the sky", "dir:up"),
    ("I cast burning hands at the ground", "dir:down"),
    ("I cast burning hands to the west", "dir:w"),
    ("burning hands north-east", "dir:ne"),
    ("I cast burning hands down the lane", None),
])
def test_i3_the_words_for_a_direction(worlds, said, aim):
    """Only "up", "overhead", "into the sky", "skyward" and "aloft" were read: "above my
    head" and "into the empty air" grounded to nothing (G2, the cast-area run). A road
    ("down the lane") is not an aim."""
    s, _e, _man = board(worlds, ground="grassland")
    spell = spells_mod.get("burning-hands")
    assert areas.aim_from_words(s, "pc", said, spell) == aim


def test_i3_a_burst_is_not_offered_a_direction(worlds):
    """A fireball "into the air" names no point to burst at, and `_check_aim` refuses a
    direction to a burst (`wrong_aim`): the reader does not make that refusal out of the
    player's clear words. The people and the things are still found first."""
    s, _e, man = board(worlds, ground="grassland")
    fireball = spells_mod.get("fireball")
    assert areas.aim_from_words(s, "pc", "a fireball into the air", fireball) is None
    assert areas.aim_from_words(s, "pc", "a fireball at the man in a stained jerkin",
                                fireball) == f"ref:{man}"
    assert "dir:w" not in areas.legal_aims(s, "pc", fireball)
    assert "dir:w" in areas.legal_aims(s, "pc", spells_mod.get("burning-hands"))


# --- the reading ---------------------------------------------------------------------------------

def test_i3_bobby_s_tree_tops_become_an_aim(worlds):
    """Bobby's reading, turn 12: the treetops as a `target`. A cast act's target, place or
    object that is not the spell's own name is grounded as an aim: the canopy of the forest
    he stood in — a terrain word, so every world's forest has one."""
    s, _e, _man = board(worlds)
    frame = {"actions": [dict(a) for a in BOBBY_READING["actions"]]}
    assert interpret.cast_aim(frame, s) == "object:canopy"
    interpret.ops_for(frame, s, ())
    assert frame["actions"][0]["aim"] == "object:canopy"
    assert "aim: object:canopy" in interpret.brief_lines(frame)


def test_i3_the_reading_is_bobby_s(worlds):
    """The frame above is the corpus's own, when the corpus is on this disk (it is kept out
    of the repository — owner, Q2)."""
    if not replays.available():
        pytest.skip("the Bobby corpus is not on this disk")
    reading = replays.turn(12)["plan"]["reading"]
    assert reading["actions"] == BOBBY_READING["actions"]


def test_i3_a_place_shaped_aim_survives_the_reading():
    """`cast` took object and target only, so a reading that put "into the empty air above
    my head" in `place` lost it in `ground` before the aim reader could see it."""
    sentence = "I cast burning hands into the empty air above my head"
    frame, dropped = interpret.ground({"actions": [
        {"act": "cast", "object": "burning hands",
         "place": "into the empty air above my head"}]}, sentence)
    assert frame["actions"][0].get("place") == "into the empty air above my head"
    assert not dropped


def test_i3_the_spell_s_own_name_is_never_the_aim(worlds):
    """The reading puts the spell in `object` ("burning hands"); it is not somewhere to
    aim, whatever words it shares with the place."""
    s, _e, _man = board(worlds)
    frame = {"actions": [{"act": "cast", "object": "burning hands"}]}
    assert interpret.cast_aim(frame, s) is None
    assert interpret.spell_named(s, "burning hands").id == "burning-hands"


# --- the engine, end to end ----------------------------------------------------------------------

def test_i3_into_the_tree_tops_burns_the_canopy_and_nobody(worlds):
    """21.2 end to end: the aim the reading grounds, cast. Nobody is up there, so nothing is
    rolled (22.4), and the canopy the flames reach burns."""
    s, e, _man = board(worlds)
    s.initiative = [("pc", 20), (_man, 10)]
    s.sides = {"pc": ["pc"], "them": [_man]}
    s.round, s.turn = 1, 0
    out = cast(e, aim=interpret.cast_aim(BOBBY_READING, s))
    eff = out.effects[0]
    assert eff.get("no_victim") and not out.rolls
    assert {"kind": "feature", "name": "canopy", "burns": True} in eff["caught_objects"]
    assert "It is aimed up into the canopy." in out.tell and "The flames reach nobody." \
        in out.tell


def test_i3_a_spent_spell_says_not_prepared_before_where(worlds):
    """The refusal order, verified: a spell already spent is "not prepared" before any
    question of where it goes. Measured on G2 "Where do you aim Burning Hands?" — and it
    was NOT a spent spell: the first cast at the man was deferred by the battle gate
    (nothing spent, owner Q31), so Burning Hands was still prepared, and the words "into
    the empty air above my head" grounded to nothing. Both halves are pinned."""
    s, e, man = board(worlds, prepared={}, int_score=17)
    pc = s.actors["pc"]
    casting.ensure_prepared(pc, reason="start")
    assert casting.prepared_count(pc, "burning-hands") == 1
    first = cast(e, aim=f"ref:{man}")
    assert first.effects[0]["kind"] == "battle_joined"
    assert casting.prepared_count(pc, "burning-hands") == 1, "the gate spent the spell"
    # The G2 line, grounded now: straight up, nobody caught.
    aim = areas.aim_from_words(s, "pc", "I cast burning hands into the empty air above "
                               "my head", spells_mod.get("burning-hands"))
    up = cast(e, aim=aim)
    assert up.effects[0].get("no_victim"), up.tell
    assert casting.prepared_count(pc, "burning-hands") == 0
    # Spent now: the next is refused as unprepared, never asked where it goes.
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "pc", "because": "t",
                     "params": {"spell": "burning-hands"}}])
    assert err.value.code == "unprepared" and "Where do you aim" not in str(err.value)


# --- the plan's schema ---------------------------------------------------------------------------

def _declared(**kw):
    schema = prompts.turn_schema(must_contain=("cast", "journey", "travel"), **kw)
    return schema["properties"]["declared"]["properties"]


def test_i3_the_declared_cast_chooses_its_aim_from_an_enum():
    """G2, 2026-09-28: a free-string aim came back `at=new2` — a placeholder for nobody —
    and the page burned an invented man. The declared cast's aim is an enum of aims that
    exist, so the model chooses one and cannot invent one; it is not required, because the
    chip or the words may already have aimed it."""
    cast_shape = _declared(refs=("pc", "c1"))["cast"]["properties"]["params"]
    enum = cast_shape["properties"]["aim"]["enum"]
    assert "ref:c1" in enum and "self" in enum and "dir:up" in enum
    assert all(areas.valid(a) for a in enum)
    assert "aim" not in cast_shape["required"]
    given = prompts._declared_op("cast", ("pc", "c1"), (), aims=("object:canopy", "bad aim"))
    assert given["properties"]["params"]["properties"]["aim"]["enum"] == ["object:canopy"]


def test_i3_the_declared_pace_is_the_journey_s_closed_word():
    for op in ("journey", "travel"):
        pace = _declared(refs=("pc",))[op]["properties"]["params"]["properties"]["pace"]
        assert pace == {"type": "string", "enum": ["walk", "ride", "gallop"]}
