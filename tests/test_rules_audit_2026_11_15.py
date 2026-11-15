"""The rules audit of 2026-11-15 (docs/rules-audit-2026-11-15.md): each test names the
wrong number or outcome the engine produced before its fix, measured on master 0b5e5be0.
"""
from __future__ import annotations

import pytest

from rules import spells as spells_mod
from tests.test_effectspec_extensions import caster, cast, override, restore_spells, table  # noqa: F401


# --- summoning ----------------------------------------------------------------------------

def test_a_summoned_creature_leaves_when_the_spell_ends():
    """CRB, Conjuration (Summoning): "When the spell ends or is dispelled, a summoned
    creature is instantly sent back to where it came from".
    Measured: a celestial dog summoned for 3 rounds (CL 3, 1 round/level) was still on the
    board after 100 rounds — `_summon` gave it no lifetime at all."""
    override("summon-monster-1", [{"type": "summon", "creature": "celestial dog"}])
    pc = caster(level=3, book=("summon-monster-1",))
    scene, engine = table(pc)
    out = cast(engine, "summon-monster-1")
    made = next(e for e in out.effects if e.get("kind") == "summon")
    ref = made["actors"][0]["ref"]
    assert made["rounds"] == 3
    assert ref in scene.actors
    scene.tick_effects(2)
    assert ref in scene.actors, "gone a round early"
    ended = scene.tick_effects(1)
    assert ref not in scene.actors
    assert any(e["kind"] == "summon_ended" for e in ended)


def test_a_summoned_creature_goes_with_the_fight():
    """The things a fight conjured go with it (`Scene.end_encounter`). Measured: the
    fight ended and the summoned dog stayed in the scene for good."""
    override("summon-monster-1", [{"type": "summon", "creature": "celestial dog"}])
    pc = caster(level=3, book=("summon-monster-1",))
    scene, engine = table(pc)
    engine._ensure_encounter("pc")
    out = cast(engine, "summon-monster-1")
    ref = next(e for e in out.effects if e.get("kind") == "summon")["actors"][0]["ref"]
    assert ref in scene.sides.get("pc", [])
    scene.end_encounter()
    assert ref not in scene.actors


def test_a_summoned_creature_dropped_to_0_hp_goes_away():
    """"A summoned creature also goes away if it is killed or if its hit points drop to
    0 or lower" — measured: a dog at -2 hp stayed on the board, dying."""
    override("summon-monster-1", [{"type": "summon", "creature": "celestial dog"}])
    pc = caster(level=3, book=("summon-monster-1",))
    scene, engine = table(pc)
    out = cast(engine, "summon-monster-1")
    ref = next(e for e in out.effects if e.get("kind") == "summon")["actors"][0]["ref"]
    scene.actors[ref].hp = -2
    scene.tick_effects(1)
    assert ref not in scene.actors


# --- concealment and wards ----------------------------------------------------------------

@pytest.mark.parametrize("spell_id, want", [("blur", 20), ("displacement", 50)])
def test_blur_and_displacement_give_the_miss_chance_they_print(spell_id, want):
    """CRB: blur grants concealment (20%), displacement 50%. Measured: both were prose
    and the caster's miss chance stayed 0 — the `concealment` type existed and the
    two spells it was written for were never moved onto it."""
    pc = caster(level=10, book=(spell_id,))
    scene, engine = table(pc)
    cast(engine, spell_id, at="pc")
    assert pc.concealment()[0] == want


def test_shield_negates_magic_missile():
    """CRB, Shield: "negates magic missile attacks directed at you". Measured: a
    shielded caster took all five missiles at CL 10 and dropped to -7 hp, because the
    spell's `immunity` spec was rendered and never granted."""
    pc = caster(level=10, book=("shield", "magic-missile"))
    scene, engine = table(pc)
    cast(engine, "shield", at="pc")
    before = pc.hp
    out = cast(engine, "magic-missile", at="pc")
    assert pc.hp == before, out.tell
    assert "immune to magic missile" in out.tell


def test_an_immunity_to_magic_is_not_an_immunity_to_magic_missile():
    """The by-name match is whole-name: `states.immunity_blocks`'s five-letter stem
    would have let "magic" answer for "magic missile"."""
    from rules.engine import Engine

    pc = caster(level=10, book=("magic-missile",))
    pc.grant_defence("immunity", "magic", source="test")
    assert Engine._immune_to_spell(pc, spells_mod.get("magic-missile")) == ""


# --- item powers --------------------------------------------------------------------------

def test_an_item_power_with_no_caster_level_casts_at_the_spells_minimum(monkeypatch):
    """CRB, Magic Item Creation: an item's caster level is at least the lowest that can
    cast its spell — 5 for a 3rd-level spell. Measured: a homebrew power naming fireball
    with its caster level left empty (the bench's "Empty: the item's own") cast at caster
    level 1 and rolled 1d6."""
    import copy

    from rules import effectspec as es
    from tests.test_enchant_engine import _table
    from tests.test_item_powers import _layered, _use

    real = es.property
    blast = copy.deepcopy(real("etherealness"))
    blast.update(id="test-blast", name="Blast", cl=None,
                 documents=[{"type": "item_power", "spell": "fireball",
                             "uses": "per_day", "uses_count": 1}])
    monkeypatch.setattr(es, "property",
                        lambda pid: blast if pid == "test-blast" else real(pid))
    s, e = _table()
    pc = s.pc()
    pc.wear(_layered("ring-fire", "ring", ["test-blast"]), 0)
    out = _use(e, "fireball", "ring-fire")
    cast_fx = next(x for x in out.effects if x.get("kind") == "cast")
    assert cast_fx["caster_level"] == 5, out.tell


# --- effect validation --------------------------------------------------------------------

@pytest.mark.parametrize("duration", [
    {"amount": "2d", "unit": "hour"}, "banana", {"amount": -3, "unit": "round"},
    {"amount": 2, "unit": "weeks"}])
def test_a_malformed_duration_is_refused_by_name(duration):
    """Measured 2026-11-15: all four validated with no problem, and `_duration_rounds`
    then read "2d" and "banana" as PERMANENT, -3 as 1 round and "weeks" as rounds — a
    typo'd two-hour buff that never wore off."""
    from rules import effectspec as es

    spec = {"type": "combat_mod", "amount": 2, "bonus_type": "morale", "target": "attack",
            "duration": duration}
    assert es.validate(spec), duration


def test_a_well_formed_duration_still_passes():
    from rules import effectspec as es

    for d in ({"amount": 3, "unit": "round"}, {"amount": "1d4", "unit": "hour"},
              {"unit": "permanent"}):
        assert not es.validate({"type": "combat_mod", "amount": 2, "bonus_type": "morale",
                                "target": "attack", "duration": d}), d


# --- combat manoeuvres --------------------------------------------------------------------

def test_agile_maneuvers_puts_dex_on_the_cmb():
    """CRB, Agile Maneuvers: "You add your Dexterity bonus ... instead of your Strength
    bonus." Measured: the feat had no document and no reader, and a Str 8 / Dex 18 PC
    who took it kept a CMB built on her -1, not her +4."""
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    pc.abilities["str"], pc.abilities["dex"] = 8, 18
    before = sum(m.value for m in pc.cmb_modifiers())
    pc.feats = list(pc.feats) + ["Agile Maneuvers"]
    after = sum(m.value for m in pc.cmb_modifiers())
    assert after - before == 5


def _trip(scene, engine):
    return engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                             "visibility": "hidden", "params": {"manoeuvre": "trip"}}])


def test_an_ooze_cannot_be_tripped():
    """CRB, Trip: "Some creatures—such as oozes, creatures without legs, and flying
    creatures—cannot be tripped." Measured: a trip at a gray ooze was validated and,
    on a hit, laid prone on it."""
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.intents import IntentError
    from rules.sheet import load_pc

    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("gray ooze", scene=scene))
    engine = Engine(scene, Dice(seed=1))
    with pytest.raises(IntentError, match="cannot be tripped"):
        _trip(scene, engine)


def test_a_creature_in_the_air_cannot_be_tripped():
    """The flying clause: a creature a level above the ground under it."""
    from tests.test_maneuver_outcomes import _fight
    from rules.intents import IntentError

    scene, engine, pc, thug = _fight()
    _trip(scene, engine)                              # on the ground: allowed
    scene.positions["c1"] = (7, 10, 2)
    with pytest.raises(IntentError, match="in the air"):
        _trip(scene, engine)


def test_a_feat_scoped_to_a_misspelt_manoeuvre_is_refused():
    """Measured: `scope: {"maneuver": "tripp"}` validated with no problem, so a typo'd
    Improved Trip loaded and never added its +2 or waived its attack of opportunity."""
    from rules.classbuilder import validate_feat_document

    doc = {"modifiers": [{"type": "combat_mod", "target": "cmb", "amount": 2,
                          "bonus_type": "untyped", "scope": {"maneuver": "tripp"}}]}
    assert any("tripp" in p for p in validate_feat_document("improved-trip", doc))
    doc["modifiers"][0]["scope"] = {"maneuver": "trip"}
    assert validate_feat_document("improved-trip", doc) == []
