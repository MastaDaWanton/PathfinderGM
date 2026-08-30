"""Ability score damage, breakable objects, and stacking temporary hit points.

The last three base-engine gaps that block Blood Bending. Each is core 1e that the app
did not have:

- Blood Boil deals Constitution damage, twice, and nothing could reduce a score.
- Caustic Blood damages "them and all their equipment", and objects had no hit points —
  an item was a string in a slot, which is enough to wear something and not enough for
  anything to happen to it.
- The class needs temporary hit points to stack, which 1e forbids, so the rule had to
  become something an actor can be exempted from rather than a constant.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import IllegalSheet, Item, from_dict, load_pc, to_dict
from rules.tables import material_for


@pytest.fixture
def pc():
    return load_pc("fixtures/pc-kesst.json")


@pytest.fixture
def scene(pc):
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    s.add(instantiate("thug", scene=s, name="the thug"))
    return s


@pytest.fixture
def engine(scene):
    return Engine(scene, Dice(seed=42))


# --- ability damage ----------------------------------------------------------------------

def test_damage_lowers_the_score_and_everything_derived_from_it(pc):
    before = pc.ability_mod("dex")
    pc.damage_ability("dex", 4)
    assert pc.ability_score("dex") == pc.base_ability_score("dex") - 4
    assert pc.ability_mod("dex") < before


def test_constitution_damage_takes_hit_points_with_it(pc):
    """1e: hit points change by your Hit Dice times the change in Constitution modifier.

    Skipping it is the easiest way for Con damage to look like it worked while doing
    nothing — the score drops, the Fortitude save drops, and the hit points sit there
    unchanged as though the poison had never landed."""
    pc.level = 4
    # Constitution BEFORE the hit points: `hp_max` is derived from the score now, so
    # "the maximum is 30" only means anything once the score it is derived from is
    # settled. Written the other way round it used to work by accident, because the
    # maximum was a stored number that Con changes then edited — the very mutation
    # that let a buff-damage-expire-heal sequence mint hit points nobody granted.
    pc.abilities["con"] = 14
    pc.hp_max = 30
    pc.hp = 30                     # +2
    pc.damage_ability("con", 4)                  # -> 10, +0: two modifier points, 4 HD
    assert pc.hp_max == 22
    assert pc.hp == 22


def test_a_wounded_character_keeps_their_wound(pc):
    pc.level = 4
    # Constitution BEFORE the hit points: `hp_max` is derived from the score now, so
    # "the maximum is 30" only means anything once the score it is derived from is
    # settled. Written the other way round it used to work by accident, because the
    # maximum was a stored number that Con changes then edited — the very mutation
    # that let a buff-damage-expire-heal sequence mint hit points nobody granted.
    pc.abilities["con"] = 14
    pc.hp_max = 30
    pc.hp = 12
    pc.damage_ability("con", 4)
    assert pc.hp_max == 22 and pc.hp == 4


def test_healing_constitution_gives_the_hit_points_back(pc):
    pc.level = 4
    # Constitution BEFORE the hit points: `hp_max` is derived from the score now, so
    # "the maximum is 30" only means anything once the score it is derived from is
    # settled. Written the other way round it used to work by accident, because the
    # maximum was a stored number that Con changes then edited — the very mutation
    # that let a buff-damage-expire-heal sequence mint hit points nobody granted.
    pc.abilities["con"] = 14
    pc.hp_max = 30
    pc.hp = 30
    pc.damage_ability("con", 4)
    pc.heal_ability("con", 4)
    assert pc.hp_max == 30 and pc.ability_score("con") == 14


def test_drain_does_not_heal_back(pc):
    """Damage and drain are stored apart because they are undone apart. Folded into one
    number, "you got better" is impossible to compute."""
    pc.damage_ability("str", 2, drain=True)
    pc.damage_ability("str", 3)
    assert pc.heal_ability("str", 99) == 3
    assert pc.ability_score("str") == pc.base_ability_score("str") - 2


def test_a_score_never_goes_negative(pc):
    pc.damage_ability("int", 99)
    assert pc.ability_score("int") == 0


def test_constitution_at_zero_is_death_even_at_full_health(pc):
    """Death by a route `apply_hp_state` cannot see: the character is on full hit points
    when it happens, so nothing in the hit-point machinery would ever notice."""
    pc.hp = pc.hp_max
    pc.damage_ability("con", 99)
    assert "dead" in pc.ability_zero_effects()
    assert pc.has_condition("dead")
    assert pc.hp > 0


@pytest.mark.parametrize("ability,condition", [
    ("str", "helpless"), ("dex", "paralyzed"),
    ("int", "unconscious"), ("wis", "unconscious"), ("cha", "unconscious"),
])
def test_each_score_at_zero_has_its_own_consequence(pc, ability, condition):
    pc.damage_ability(ability, 99)
    pc.ability_zero_effects()
    assert pc.has_condition(condition)


def test_a_night_returns_one_point_per_ability(pc):
    """"1 point per day, or 2 per day of complete bed rest, for each affected ability" —
    per ability, not shared, so a poison that hit two scores heals both at once rather
    than taking twice as long."""
    pc.damage_ability("str", 3)
    pc.damage_ability("dex", 3)
    result = pc.rest("night")
    assert result["ability"] == {"str": 1, "dex": 1}

    assert pc.rest("bed rest")["ability"] == {"str": 2, "dex": 2}


def test_the_engine_resolves_ability_damage(engine, scene):
    pc = scene.pc()
    res = engine.run(engine.validate([
        {"op": "ability_damage", "target": "pc", "because": "the blood boils in her arm",
         "params": {"ability": "con", "amount": 2}},
    ]))
    assert pc.ability_score("con") == pc.base_ability_score("con") - 2
    assert "Constitution damage" in res.outcomes[0].tell


def test_an_invented_ability_is_refused(engine):
    from rules.intents import IntentError

    with pytest.raises(IntentError):
        engine.run(engine.validate([
            {"op": "ability_damage", "target": "pc",
             "params": {"ability": "luck", "amount": 2}}]))


# --- objects -----------------------------------------------------------------------------

def test_hardness_comes_off_before_the_object_is_hurt():
    """CRB p.173: hardness subtracts from every hit before the object's own hit points
    are touched. An iron ring is not scratched by a knife."""
    ring = Item("iron ring")
    d = ring.take_damage(8, "slashing")
    assert ring.hardness == 10
    assert d["reduced"] == 8 and d["taken"] == 0
    assert ring.hp == ring.hp_max


def test_a_soft_thing_is_ruined_by_what_a_hard_thing_shrugs_off():
    cloak, blade = Item("silk cloak"), Item("longsword")
    cloak.take_damage(9, "slashing")
    blade.take_damage(9, "slashing")
    assert cloak.destroyed
    assert blade.hp == blade.hp_max


def test_half_hit_points_is_broken_and_not_destroyed():
    shield = Item("wooden shield")
    shield.take_damage(shield.hardness + shield.hp_max // 2, "bludgeoning")
    assert shield.broken and not shield.destroyed


def test_energy_is_halved_against_objects_but_acid_is_not():
    """CRB p.174 halves energy against objects. Acid is the exception this app needs
    first: Blood Bending's Caustic Blood exists to ruin equipment, and halving it would
    make a defining ability read as a rounding error."""
    burned, dissolved = Item("wooden staff"), Item("wooden staff")
    assert burned.take_damage(20, "fire")["taken"] == 5        # 10 after halving, less 5
    assert dissolved.take_damage(20, "acid")["taken"] == 15


@pytest.mark.parametrize("name,material", [
    ("silk cloak", "cloth"), ("leather boots", "leather"), ("oak staff", "wood"),
    ("glass vial", "glass"), ("adamantine blade", "adamantine"), ("longsword", "steel"),
    ("padded", "cloth"), ("chain shirt", "steel"), ("full plate", "steel"),
])
def test_material_is_guessed_from_the_name(name, material):
    """The alternative is asking the GM, and a GM asked for a material will invent one."""
    assert material_for(name) == material


@pytest.mark.parametrize("name", list(__import__("rules.tables", fromlist=["MATERIALS"]).MATERIALS))
def test_a_thing_named_for_its_material_is_made_of_it(name):
    """Found in the app: `leather` armour came back *steel, hardness 10*. The hints knew
    about leather boots and leather belts, and nothing knew that "leather" is leather —
    so acid ran off a jerkin the way it runs off a breastplate."""
    assert material_for(name) == name


def test_acid_takes_everything_a_character_is_carrying(pc):
    """"an enemy in a blood pool takes 1d4 + 4 acid dmg to them and all their equipment"
    — acid in a pool does not pick a target."""
    results = pc.damage_all_gear(12, "acid")
    assert len(results) == len(pc.carried()) > 1
    assert any(r["taken"] for r in results)


def test_the_engine_damages_one_named_item(engine, scene):
    res = engine.run(engine.validate([
        {"op": "item_damage", "target": "pc", "because": "the acid finds her sleeve",
         "params": {"item": "silk cloak", "amount": 9, "type": "acid"}},
    ]))
    assert "silk cloak" in res.outcomes[0].tell
    assert scene.pc().item("silk cloak").destroyed


def test_gear_that_shrugs_it_off_is_not_narrated_one_by_one(engine, scene):
    """A list of eleven items that all took nothing buries the one that did not."""
    res = engine.run(engine.validate([
        {"op": "item_damage", "target": "pc", "params": {"amount": 1, "type": "acid"}}]))
    assert "Nothing" in res.outcomes[0].tell


# --- temporary hit points that stack ------------------------------------------------------

def test_stacking_is_off_unless_a_class_turns_it_on(pc):
    pc.gain_temp_hp(10, "a ward")
    pc.gain_temp_hp(6, "another ward")
    assert pc.temp_hp == 10


def test_a_blood_bender_stacks_them(pc):
    """The class's whole economy is hit points as a resource, and a Coagulator layering
    Blood Sponge over a ward is the path working as written. A global toggle would have
    changed the rule for every NPC in the world, so it is an override on the actor."""
    pc.overrides["temp_hp.stacks"] = True
    pc.gain_temp_hp(10, "blood sponge")
    pc.gain_temp_hp(6, "siphon pool")
    assert pc.temp_hp == 16

    pc.take_damage(20, "slashing")
    assert pc.temp_hp == 0 and pc.hp == pc.hp_max - 4


def test_the_shortest_lived_pool_is_spent_first(pc):
    """Spending the long-lasting pool to soak a hit the expiring one could have taken
    throws away protection, and does it invisibly."""
    pc.overrides["temp_hp.stacks"] = True
    pc.gain_temp_hp(5, "blood sponge", rounds=10)
    pc.gain_temp_hp(5, "a standing ward")
    pc.take_damage(5, "slashing")
    assert [p.source for p in pc.temp_pools] == ["a standing ward"]


def test_pools_expire_on_their_own_clocks(pc):
    pc.overrides["temp_hp.stacks"] = True
    pc.gain_temp_hp(4, "blood sponge", rounds=10)
    pc.gain_temp_hp(6, "a longer ward", rounds=100)
    ended = pc.tick_conditions(10)
    assert any("blood sponge" in e for e in ended)
    assert pc.temp_hp == 6


def test_a_misspelled_override_is_caught_at_load():
    """A feature that silently never happens, with nothing anywhere saying why, is the
    failure mode this exists to prevent."""
    with pytest.raises(IllegalSheet, match="no such rule"):
        from_dict({"name": "x", "kind": "npc", "hp": 5, "hp_max": 5,
                   "abilities": {a: 10 for a in
                                 ("str", "dex", "con", "int", "wis", "cha")},
                   "overrides": {"temp_hp.stack": True}})


def test_everything_new_survives_a_save(pc):
    pc.overrides["temp_hp.stacks"] = True
    pc.hit_dice_per_level = 2
    pc.gain_temp_hp(5, "blood sponge", rounds=10)
    pc.gain_temp_hp(3, "siphon pool")
    pc.damage_ability("con", 2)
    pc.damage_ability("str", 1, drain=True)
    pc.damage_item("longsword", 14, "acid")

    back = from_dict(to_dict(pc))
    assert back.temp_hp == 8 and len(back.temp_pools) == 2
    assert back.ability_damage["con"] == 2 and back.ability_drain["str"] == 1
    assert back.hit_dice_per_level == 2
    assert back.gear["longsword"].hp == pc.gear["longsword"].hp


def test_an_older_save_with_a_bare_temp_hp_still_loads():
    a = from_dict({"name": "x", "kind": "npc", "hp": 5, "hp_max": 5,
                   "abilities": {ab: 10 for ab in
                                 ("str", "dex", "con", "int", "wis", "cha")},
                   "temp_hp": 7, "temp_hp_source": "a ward"})
    assert a.temp_hp == 7 and a.temp_pools[0].source == "a ward"


def test_hit_dice_is_not_always_level(pc):
    """Every class in the book has one die per level, so nothing has ever had to tell
    them apart. Blood Bending has two, and anything counted per Hit Die is wrong by a
    factor of two without this."""
    pc.level = 5
    assert pc.hit_dice == 5
    pc.hit_dice_per_level = 2
    assert pc.hit_dice == 10
