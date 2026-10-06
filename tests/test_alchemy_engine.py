"""The alchemist's effect types, read by the engine (alchemy lane C, plan §16.3-§16.9).

Lane B gave the vocabulary `sense`, `permission`, `light` and `burning` and marked each
"not run yet" (`effectspec.AWAITING_READER`), with climb, swim, fly and burrow speeds
waiting per spec. Measured on build/alchemy (3bbd361), drinking each did nothing: a potion
of darkvision's spec was narrated, a potion holding a spell with no documents of its own
landed nothing at all, "+2 against undead" applied against everyone (`when` was never
forwarded), and a fly potion left the drinker on the ground. Each test below drinks or
throws the real thing through `use_item` and reads the reader that should now see it.
"""
from __future__ import annotations

from rules import effectspec as es
from rules import water
from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc


def _scene(*specs_by_item, seed=4):
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    for i, (name, specs) in enumerate(specs_by_item):
        pc.stock[f"item{i}#1"] = Stock(base=name, count=2, specs=[dict(x) for x in specs])
    return s, Engine(s, Dice(seed=seed)), pc


def _use(e, item, how="drink", **params):
    res = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "she uses it",
                             "params": {"item": item, "how": how, **params}}]))
    if res.status != "complete":
        res = e.resume(face=20)
    return res


def _told(res):
    return " ".join(o.tell for o in res.outcomes)


HOUR = {"amount": 1, "unit": "hour"}


# --- senses -----------------------------------------------------------------------------------

def test_a_potion_of_darkvision_grants_the_sense_for_its_duration():
    s, e, pc = _scene(("Potion of Darkvision",
                       [{"type": "sense", "target": "darkvision", "range": 60,
                         "duration": HOUR}]))
    assert pc.eyes()["darkvision"] == 0
    res = _use(e, "item0#1")
    assert pc.has_state("sense.darkvision")
    assert pc.eyes()["darkvision"] == 60
    assert any(x.get("kind") == "grant" and x.get("origin") == "item:item0#1"
               for o in res.outcomes for x in o.effects)
    pc.tick_effects(600)
    assert not pc.has_state("sense.darkvision")


def test_see_invisibility_ignores_invisibilitys_miss_chance():
    s, e, pc = _scene(("Potion of See Invisibility",
                       [{"type": "sense", "target": "see_invisible", "duration": HOUR}]))
    thug = s.actors["c1"]
    thug.add_condition("invisible", source="a ring")
    assert e._concealment_of(pc, thug)[0] == 50
    _use(e, "item0#1")
    assert e._concealment_of(pc, thug)[0] == 0


def test_a_worn_low_light_sense_is_spelled_as_a_race_spells_it(monkeypatch):
    """Lane B's measurement: the worn reader wrote `sense.low_light`, and a race writes
    `sense.low-light`, so goggles of low-light vision answered nobody's question."""
    s, e, pc = _scene()
    monkeypatch.setattr(pc, "worn_specs_of", lambda kind, ctx=None, ask_when=True,
                        walk=None: [({"type": "sense", "target": "low_light"}, "goggles",
                                     "item:goggles")] if kind == "sense" else [])
    assert "sense.low-light" in pc._worn_tags()
    assert "sense.low_light" not in pc._worn_tags()


# --- permissions ------------------------------------------------------------------------------

def test_a_permission_is_granted_as_its_tag_and_the_drowning_rule_reads_it():
    s, e, pc = _scene(("Potion of Water Breathing",
                       [{"type": "permission", "target": "Breathe water freely.",
                         "tag": "breathe_water", "duration": HOUR}]),
                      ("A vague draught", [{"type": "permission",
                                            "target": "Feels lucky."}]))
    assert not water.breathes_water(pc)
    _use(e, "item0#1")
    assert pc.has_state("breathes.water")
    assert water.breathes_water(pc)
    # A permission with no tag grants nothing and is told to the GM, never dropped.
    res = _use(e, "item1#1")
    assert "Feels lucky" in _told(res)


# --- speed --------------------------------------------------------------------------------------

def test_a_potion_of_haste_moves_the_drinker_thirty_feet_faster():
    """The plan's test: "a potion of haste moves the drinker 30 ft faster (it narrated)"."""
    s, e, pc = _scene(("Potion of Haste", [{"type": "speed", "target": "land",
                                            "amount": 30, "duration": HOUR}]))
    before = pc.speed_feet
    _use(e, "item0#1")
    assert pc.speed_feet == before + 30


def test_a_fly_potion_lets_the_drinker_leave_the_ground_and_a_swim_one_swim():
    s, e, pc = _scene(("Potion of Fly", [{"type": "speed", "target": "fly", "amount": 60,
                                          "duration": HOUR}]),
                      ("Potion of the Eel", [{"type": "speed", "target": "swim",
                                              "amount": 30, "duration": HOUR}]),
                      ("Potion of the Mole", [{"type": "speed", "target": "burrow",
                                               "amount": 20, "duration": HOUR}]))
    assert pc.can_move_vertically() == ""
    _use(e, "item0#1")
    assert pc.movement_modes()["fly"] == 60
    assert pc.can_move_vertically() == "fly"
    assert water.swim_speed(pc) == 0
    _use(e, "item1#1")
    assert water.swim_speed(pc) == 30
    # Burrow has no reader in movement: told to the GM, never pretended.
    res = _use(e, "item2#1")
    assert "burrow" not in pc.movement_modes()
    assert "Burrow" in _told(res) or "burrow" in _told(res)


# --- spell potions -------------------------------------------------------------------------------

def test_a_spell_potion_with_no_documents_resolves_through_the_spells_own():
    """Plan §11.3: `spells.effects_at` at the potion's caster level, the drinker the
    target. Measured before: a stock with `holds_spell` and no specs drank as nothing.
    Bull's strength's +4 lands as the spell's own enhancement bonus — which the cast door
    itself only tells (`casting_plan` riders), so the potion does not go through it."""
    s, e, pc = _scene()
    pc.stock["bull#1"] = Stock(base="Potion of Bull's Strength", count=1,
                               holds_spell="bull-s-strength", caster_level=3)
    pc.stock["clw#1"] = Stock(base="Potion of Cure Light Wounds", count=1,
                              holds_spell="cure-light-wounds", caster_level=1)
    strength = pc.ability_score("str")
    res = _use(e, "bull#1")
    assert pc.ability_score("str") == strength + 4, _told(res)
    pc.hp = 1
    _use(e, "clw#1")
    assert pc.hp > 1
    assert "bull#1" not in pc.stock and "clw#1" not in pc.stock


# --- "against X only" ---------------------------------------------------------------------------

SUNMETAL = [{"type": "damage", "dice": "2d6", "damage_type": "fire", "route": "struck",
             "when": {"target": {"type": "undead"}}}]


def test_sunmetal_does_nothing_to_the_living_and_burns_the_dead():
    """Plan §16.7: sunmetal filings and saint's tallow hurt the living, their "undead
    only" in an unread note. The damage op now asks the clause of the struck creature."""
    s, e, pc = _scene(("Sunmetal Flask", SUNMETAL))
    e._ensure_encounter("pc")
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (4, 10)
    thug = s.actors["c1"]
    res = _use(e, "item0#1", how="throw", to="c1")
    assert thug.hp == thug.hp_max
    assert "does nothing to the thug" in _told(res)
    bones = s.add(instantiate("human-skeleton", scene=s, name="the skeleton"))
    s.positions[bones.ref] = (4, 12)
    e.join_fight(bones.ref)
    _use(e, "item0#1", how="throw", to=bones.ref)
    assert bones.hp < bones.hp_max or bones.is_down


def test_a_timed_bonus_against_undead_counts_against_undead_only():
    s, e, pc = _scene(("Draught of the Pyre", [
        {"type": "combat_mod", "target": "attack", "amount": 2, "bonus_type": "sacred",
         "when": {"target": {"type": "undead"}}, "duration": HOUR}]))
    bones = s.add(instantiate("human-skeleton", scene=s, name="the skeleton"))
    thug = s.actors["c1"]
    before_thug = sum(m.value for m in pc.attack_modifiers(defender=thug))
    before_bones = sum(m.value for m in pc.attack_modifiers(defender=bones))
    _use(e, "item0#1")
    assert sum(m.value for m in pc.attack_modifiers(defender=thug)) == before_thug
    assert sum(m.value for m in pc.attack_modifiers(defender=bones)) == before_bones + 2


# --- metal --------------------------------------------------------------------------------------

def test_aqua_regia_eats_the_struck_creatures_metal_and_nothing_else():
    """Plan §16.11: gray ooze core and aqua regia damage the struck creature's METAL armour
    and weapon, asked of the material tag (`item_tags`), never of a name."""
    s, e, pc = _scene(("Aqua Regia", [
        {"type": "object_damage", "dice": "3d6", "damage_type": "acid", "item": "metal",
         "route": "struck"}]))
    s.remove("c1")
    guard = s.add(from_dict({"name": "the guard", "kind": "npc", "hp": 12, "hp_max": 12,
                             "armour": "chainmail", "weapons": ["longsword", "club"],
                             "equipped": "longsword",
                             "abilities": {k: 10 for k in ("str", "dex", "con", "int",
                                                           "wis", "cha")}}, ref="c1"))
    e._ensure_encounter("pc")
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (4, 10)
    res = _use(e, "item0#1", how="throw", to="c1")
    hit = {x.get("item") for o in res.outcomes for x in o.effects
           if x.get("kind") == "item_damage"}
    assert hit == {"chainmail", "longsword"}, _told(res)


# --- conditions the bag needs ---------------------------------------------------------------------

def test_entangleds_minus_two_and_minus_four_are_read():
    """The plan's first measurement for §16.8: are entangled's −2 attack and −4 Dex read?
    Yes — `_condition_mods("attack")` and the ability penalty both — and speed halves
    through `state.slowed`."""
    s, e, pc = _scene()
    attack = sum(m.value for m in pc.attack_modifiers())
    dex = pc.ability_score("dex")
    speed = pc.speed_feet
    pc.add_condition("entangled", source="a tanglefoot bag")
    assert sum(m.value for m in pc.attack_modifiers()) <= attack - 2
    assert pc.ability_score("dex") == dex - 4
    assert pc.speed_feet == (speed // 2 // 5) * 5


def test_glued_is_a_held_state_with_no_speed_and_no_way_off_the_ground():
    s, e, pc = _scene(("Potion of Fly", [{"type": "speed", "target": "fly", "amount": 60,
                                          "duration": HOUR}]))
    _use(e, "item0#1")
    pc.add_condition("glued", 3, source="a tanglefoot bag")
    assert pc.has_state("state.held.glued") and pc.has_state("state.held")
    assert pc.speed_feet == 0
    assert pc.can_move_vertically() == ""


# --- lane D's measurement: engine-ready types with no branch at the use door ----------------------

def test_blur_troll_marrow_and_demon_ichor_land():
    """Lane D measured through `consumables.plan` (2026-10-06): concealment, fast healing,
    bleed and a chosen form produced no intent — the potion of blur, troll marrow and demon
    ichor did nothing when used."""
    s, e, pc = _scene(("Potion of Blur", [{"type": "concealment", "miss_chance": 20,
                                           "duration": {"amount": 3, "unit": "minute"}}]),
                      ("Troll Marrow", [{"type": "fast_healing", "amount": 1,
                                         "duration": {"amount": 5, "unit": "round"}}]),
                      ("Demon Ichor", [{"type": "bleed", "amount": 1}]))
    thug = s.actors["c1"]
    _use(e, "item0#1")
    assert e._concealment_of(thug, pc) == (20, "Potion of Blur")
    pc.hp = 3
    _use(e, "item1#1")
    assert pc.has_state("buff.fast-healing")
    assert any(r.get("kind") == "heal" for r in pc.run_periodic("round", 1, e.dice))
    assert pc.hp == 4
    _use(e, "item2#1")
    assert pc.has_condition("bleed")
    hp = pc.hp
    pc.run_periodic("round", 1, e.dice)
    assert pc.hp == hp - 1 + 1          # one bleed, one fast healing, the same round


def test_a_chosen_form_lands_and_an_unchosen_one_is_told():
    lesser = {"type": "choose_one", "options": [
        {"type": "ability_mod", "target": "str", "amount": 2, "bonus_type": "alchemical"},
        {"type": "ability_mod", "target": "dex", "amount": 2, "bonus_type": "alchemical"}]}
    s, e, pc = _scene(("Picked", [dict(lesser, chosen=2)]), ("Unpicked", [dict(lesser)]))
    dex = pc.ability_score("dex")
    _use(e, "item0#1")
    assert pc.ability_score("dex") == dex + 2
    res = _use(e, "item1#1")
    assert "whichever you choose" in _told(res).lower() or "one of" in _told(res).lower() \
        or "(" in _told(res)


def test_thrown_itching_powder_rolls_its_fortitude_save():
    s, e, pc = _scene(("Itching Powder", [
        {"type": "save_gate", "target": "fort", "dc": 12, "route": "struck",
         "on_failure": [{"type": "apply_condition", "target": "sickened",
                         "duration": {"amount": 10, "unit": "minute"}}]}]))
    e._ensure_encounter("pc")
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (4, 10)
    res = _use(e, "item0#1", how="throw", to="c1")
    assert "Fortitude save" in _told(res)


# --- the ledger -----------------------------------------------------------------------------------

def test_the_four_waiting_types_are_executable_now():
    assert es.AWAITING_READER == {}
    for spec in ({"type": "sense", "target": "darkvision"},
                 {"type": "permission", "target": "x", "tag": "breathe_water"},
                 {"type": "light", "radius_ft": 30, "raised_ft": 60},
                 {"type": "burning", "dice": "1d6"}):
        assert es.executable(spec), spec
    assert not es.executable({"type": "speed", "target": "burrow", "amount": 10})


def test_the_hazard_row_says_the_per_creature_fire_exists_and_what_still_waits():
    from rules import hazards

    row = hazards.get("burning-brush")
    assert "state.burning" in row["not_yet"] and "extinguish" in row["not_yet"]
