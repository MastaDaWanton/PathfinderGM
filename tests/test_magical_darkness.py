"""Magical darkness lowers the light (feat loop b6-rules; CRB, Vision and Light, darkness,
deeper darkness, light, daylight).

Measured on integrate/feats-b5 3520f6a8: darkness, deeper darkness, light and daylight were
four narrative lines ("Light levels have no spec type"), so a darkness spell cast in a lit
room left `Scene.light_at` at "normal" and every blow inside it met no miss chance; Umbral
Spell and Shadow Grasp had nothing to build on.
"""
from __future__ import annotations

from rules.activeeffect import ActiveEffect
from tests.test_feats_b4_moves import _board, _pc, _run, _tells
from tests.test_readied_action import _caster


def _lit_room(*prepared, feats=()):
    pc = _caster("pc", prepared=prepared, feats=feats)
    s, e = _board(pc, ("thug", (8, 5)))
    s.ambient_light = lambda: "normal"
    return s, e, pc


def _cast(e, spell, at="pc", **params):
    return _run(e, {"op": "cast", "actor": "pc", "target": at, "visibility": "hidden",
                    "params": {"spell": spell, "at": at, **params}})


def _torch(who, s):
    who.apply_effect(ActiveEffect(name="torch", kind="effect", key="light.carried",
                                  source="torch", origin="item:torch", tags=("light.carried",),
                                  payload={"light": {"radius_ft": 20, "raised_ft": 40}}))


def test_darkness_drops_the_light_a_step_within_twenty_feet():
    """CRB darkness: "This darkness causes the illumination level in the area to drop one
    step, from bright light to normal light, from normal light to dim light". Cast in a lit
    room the caster's square is dim, 15 feet off dim, 30 feet off still normal; and a dim
    square is a 20% miss chance for a blow."""
    s, e, pc = _lit_room("darkness")
    res = _cast(e, "darkness")
    assert "Darkness spreads" in _tells(res), _tells(res)
    assert s.light_at((5, 5)) == "dim"
    assert s.light_at((8, 5)) == "dim"
    assert s.light_at((12, 5)) == "normal"
    thug = s.actors["c1"]
    assert e._concealment_of(thug, pc)[0] == 20


def test_a_torch_does_not_raise_magical_darkness_and_a_higher_light_spell_does():
    """CRB: "Nonmagical sources of light, such as torches and lanterns, do not increase the
    light level in an area of darkness. Magical light sources only increase the light level
    in an area if they are of a higher spell level than darkness." A torch carried by the
    thug in the darkness leaves it dim; a light spell (0th) leaves it dim; a 3rd-level
    light raises it."""
    s, e, pc = _lit_room("darkness")
    s.ambient_light = lambda: "dark"
    _cast(e, "darkness")
    thug = s.actors["c1"]
    _torch(thug, s)
    assert s.light_at((8, 5)) == "dark"
    low = ActiveEffect(name="Light", kind="effect", key="light.carried", source="Light",
                       origin="spell:light", tags=("light.carried",),
                       payload={"light": {"radius_ft": 20, "raised_ft": 40},
                                "cast": {"level": 0}})
    thug.apply_effect(low)
    assert s.light_at((8, 5)) == "dark"
    low.payload["cast"]["level"] = 3
    assert s.light_at((8, 5)) == "normal"


def test_deeper_darkness_is_two_steps_and_blinds_darkvision_where_it_was_dim():
    """CRB deeper darkness: "the light level is lowered by two steps ... Areas of dim light
    and darkness become supernaturally dark. This functions like darkness, but even creatures
    with darkvision cannot see within it." In a lit room two steps is darkness; underground
    it is supernatural, and a dwarf's darkvision no longer reaches the thug."""
    s, e, pc = _lit_room()
    ctx = {"caster": "pc", "targets": ["pc"], "source": "Deeper Darkness",
           "origin": "spell:deeper-darkness", "rounds": 100, "vars": {"spell_level": 3}}
    e._cast_light({"type": "darkness", "radius_ft": 60, "steps": 2}, ctx)
    assert s.light_at((8, 5)) == "dark" and not s.supernatural_dark((8, 5))
    s.ambient_light = lambda: "dim"
    assert s.supernatural_dark((8, 5))
    dwarf = _pc("fighter", race="dwarf")
    dwarf.ref = "d1"
    assert dwarf.eyes().get("darkvision")
    s.add(dwarf, at=(6, 5))
    assert s.sees_nothing(dwarf, s.actors["c1"])


def test_daylight_cast_into_darkness_dispels_it():
    """CRB daylight: it "counters or dispels any darkness spell of equal or lower level";
    darkness is 2nd, daylight 3rd. Laid where the darkness reaches, both are spent and the
    room is lit as before."""
    s, e, pc = _lit_room("darkness", "daylight")
    _cast(e, "darkness")
    assert s.light_at((5, 5)) == "dim"
    s.standard_spent.pop("pc", None)
    res = _cast(e, "daylight")
    assert "dispelled" in _tells(res), _tells(res)
    assert s.light_at((5, 5)) == "normal"
    assert not any((x.payload or {}).get("darkness") for x in pc.effects)


def test_daylight_alone_is_bright():
    s, e, pc = _lit_room("daylight")
    _cast(e, "daylight")
    assert s.light_at((5, 5)) == "bright"
    assert s.light_at((15, 5)) == "bright"


# --- Umbral Spell, Shadow Grasp ------------------------------------------------------------

def test_an_umbral_spell_makes_its_target_radiate_darkness():
    """Umbral Spell (ISM): "the creature or object affected radiates darkness in a 10-foot
    radius". An umbral mage armor on the caster: dim around him, normal 15 feet off, for the
    armor's hours; the copy carries the darkness descriptor."""
    s, e, pc = _lit_room("mage-armor", feats=("Tenebrous Spell", "Umbral Spell"))
    from rules import casting

    casting.prepare(pc, casting.metamagic_key("mage-armor", ["umbral-spell"]), 1)
    res = _cast(e, "mage-armor", metamagic=["umbral-spell"])
    said = _tells(res)
    assert "Darkness spreads" in said, said
    assert s.light_at((5, 5)) == "dim" and s.light_at((8, 5)) == "normal"


def test_umbral_spell_refuses_an_instantaneous_spell():
    from rules import metamagic, spells

    pc = _caster("pc", prepared=(), feats=("Tenebrous Spell", "Umbral Spell"))
    why = metamagic.refusal(pc, spells.get("magic-missile"), ["umbral-spell"],
                            spontaneous=False)
    assert "instantaneous" in why


def test_shadow_grasp_entangles_those_in_the_darkness_who_fail_the_reflex_save():
    """Shadow Grasp (ISM): "creatures in the area are entangled ... If the spell does not
    normally allow a save, a creature can make a Reflex save (DC = the spell's DC if it had
    a saving throw)". The thug in the darkness rolls a 1 and is entangled; the caster is
    "never impeded"."""
    s, e, pc = _lit_room("darkness")
    e.dice.faces["the thug 1's Reflex save"] = 1
    ctx = {"caster": "pc", "targets": ["pc"], "source": "Darkness", "origin": "spell:darkness",
           "rounds": 70, "dc": 15, "metamagic": ("shadow_grasp",), "vars": {"spell_level": 2}}
    got, said = e._cast_light({"type": "darkness", "radius_ft": 20, "steps": 1}, ctx)
    assert s.actors["c1"].has_state("state.held.entangled") or \
        any(c.key == "entangled" for c in s.actors["c1"].conditions), said
    assert not any(c.key == "entangled" for c in pc.conditions)
    assert "Shadow Grasp" in " ".join(said)


# --- Bouncing Spell (a metamagic of the same lane, tested with the casts above) -----------------

def test_a_bouncing_hold_person_saved_against_goes_to_the_next_foe():
    """APG Bouncing Spell: "Whenever a bouncing spell targeting a single creature has no
    effect on its intended target (whether due to spell resistance or a successful saving
    throw) you may, as a swift action, redirect it". Before: no document. The first thug
    shrugs off hold person (Will +30); the spell goes to the second, who is held, and the
    caster's swift action is spent."""
    from rules import casting

    pc = _caster("pc", prepared=(), feats=("Bouncing Spell",))
    pc.spellbook = list(pc.spellbook or ()) + ["hold-person"]
    casting.prepare(pc, casting.metamagic_key("hold-person", ["bouncing-spell"]), 1)
    s, e = _board(pc, ("thug", (8, 5)), ("thug", (9, 6)))
    s.actors["c1"].add_buff("save_mod", "will", 30, source="test", rounds=10)
    s.actors["c2"].add_buff("save_mod", "will", -30, source="test", rounds=10)
    res = _cast(e, "hold-person", at="c1", metamagic=["bouncing-spell"])
    said = _tells(res)
    assert "bounces to the thug 2" in said, said
    assert s.actors["c2"].has_state("state.held"), said
    assert not s.actors["c1"].has_state("state.held")
    assert s.swift_spent.get("pc") == s.round


def test_darkness_in_a_scene_with_no_map_darkens_the_one_room():
    """Measured on a copy of the owner's campaign (2026-11-27): a scene with no board, a
    darkness cast, and `light_at` still "normal" — the darkness had no square to be
    measured from. With no map the scene is one room: the darkness lowers it."""
    from rules.engine import Engine, Scene

    pc = _caster("pc", prepared=("darkness",))
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    s.ambient_light = lambda: "normal"
    e = Engine(s)
    _run(e, {"op": "cast", "actor": "pc", "visibility": "hidden",
             "params": {"spell": "darkness"}})
    assert not s.has_grid and s.light_at(None) == "dim"
