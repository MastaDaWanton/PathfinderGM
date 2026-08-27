"""The effect vocabulary's second half: the things twenty readers could not say.

Twenty agents read all 3,040 spells one at a time and converted them. 6,476 specs came out
validating, and 3,134 of them were `narrative` — an honest refusal, with a reason attached.
The reasons converged on a short list, and this file is that list turned into measurements.

What each test is here to record:

* **Nothing that validated stops validating.** Every field added here is optional with a
  default that means what an absent value has always meant, and the whole corpus is run
  through `validate` to prove it rather than argued about. 6,476 in, 0 problems out.
* **A recipient, because every spec landed on "the target".** Measured, on the first run of
  the executor before this existed: thorn body — 1d6 piercing to *whoever strikes you* —
  produced the tell "Kesst Vayr takes 5 piercing", setting fire to the druid it was
  protecting. Eruptive pustules, holy aura, cape of wasps, water shield, life shield and
  kinetic reverberation are the same shape.
* **A trigger, because damage that repeats was flattened to one hit.** Incendiary cloud is
  6d6 fire, Reflex half, *every round*; as a plain save gate it fires once at casting and
  never again, understating the spell by however many rounds the cloud stands.
* **A formula for `amount`.** Divine favor is "+1 luck per three caster levels, maximum +3"
  and `amount` was an int, so it is stored as a flat +1 with the real rule in a note that
  nothing reads — a spell that stops scaling at caster level 3.
* **`manifest`, the user's own "temp-spawning".** Backed by `Grid.obscuring` / `blocked` /
  `difficult`, which the map already draws and `Grid.reachable` and `line_of_sight` already
  route around. A fog cloud is 61 squares of obscuring, measured.
* **`spell_operation`, the user's own "permanency".** Acts on the real lifetimes the engine
  keeps: a buff's `rounds_left`, a condition's, a manifestation's.
* **A type that is `narrative` wearing a costume is not allowed.** Every type declared
  `engine=True` here is executed by a test in this file; every type declared `engine=False`
  carries a `blocked` sentence saying what is recorded instead.
"""
from __future__ import annotations

import copy

import pytest

from rules import effectspec as fx
from rules import spells as spells_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Manifestation, Scene, Ward
from rules.grid import Grid
from rules.sheet import from_dict, load_pc, to_dict


# --- fixtures a spell needs to actually be cast ----------------------------------------------

def caster(klass="wizard", level=10, book=(), ability=18, ref="pc"):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": klass, "level": level, "ranks": {}})
    d["abilities"]["int" if klass == "wizard" else "wis"] = ability
    d["spellbook"] = list(book)
    d["prepared"] = {k: 3 for k in book}
    return from_dict(d, ref=ref)


def override(spell_id, effects):
    """Give a shipped spell an authored effects list, for this test only.

    Not written into `content/spells/mechanics/*.json`: the shipped conversion of thorn
    body deliberately carries no damage spec, and `tests/test_casting_executes.py` pins
    that it does not. These are what a *user* would author now that the vocabulary can
    hold it, which is the half the ask calls "user created".
    """
    clone = copy.deepcopy(spells_mod.get(spell_id))
    clone.effects = effects
    spells_mod.all_spells()[spell_id] = clone
    return clone


@pytest.fixture(autouse=True)
def restore_spells():
    """Put the spell list back, so an override cannot leak into another test."""
    before = dict(spells_mod.all_spells())
    yield
    spells_mod._ALL.clear()
    spells_mod._ALL.update(before)


def table(pc, grid=True, seed=5, enemy="thug"):
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc, at=(5, 5) if grid else None)
    s.add(instantiate(enemy, scene=s), at=(6, 5) if grid else None)
    if grid:
        s.grid = Grid(width=20, height=20)
    return s, Engine(s, Dice(seed=seed))


def cast(engine, spell_id, **params):
    return engine.run(engine.validate([
        {"op": "cast", "actor": "pc", "params": {"spell": spell_id, **params}}
    ])).outcomes[0]


# --- the promise the whole change is made under ---------------------------------------------

def test_every_spec_in_the_corpus_still_validates():
    """3,040 spells and 6,476 specs validated before any of this; all of them still do.

    The additions are fields with defaults that mean what absence has always meant, and
    this is the check that says so rather than the argument that it should be true.
    """
    problems = []
    total = 0

    def walk(specs):
        nonlocal total
        for spec in specs:
            total += 1
            problems.extend(fx.validate(spec, "corpus"))
            for branch in ("on_failure", "on_success"):
                if isinstance(spec.get(branch), list):
                    walk(spec[branch])

    for spell in spells_mod.all_spells().values():
        walk(spell.effects or [])

    assert total > 6000, f"only {total} specs — the corpus did not load"
    assert problems == [], problems[:10]


def test_an_absent_recipient_and_trigger_mean_what_they_always_meant():
    """The default for both is the behaviour every existing spec has: the target, now."""
    plain = {"type": "damage", "dice": "1d6", "damage_type": "fire",
             "lethality": "lethal"}
    assert fx.validate(plain) == []
    assert fx.render(plain) == "1d6 fire damage"
    assert spells_mod._is_the_spells_own(plain) is True


# --- the recipient ------------------------------------------------------------------------------

def test_thorn_body_burns_the_attacker_and_not_the_druid_who_cast_it():
    """The measurement this whole field exists for.

    Before a recipient existed, thorn body's "1d6 piercing to any creature striking you"
    could only be written as a plain `damage` spec, and `_op_cast` rolled it against the
    spell's target — which for a personal spell is the caster. The tell read
    "Kesst Vayr takes 5 piercing": the spell set fire to the druid it was protecting.
    """
    override("thorn-body", [{
        "type": "damage", "dice": "1d6", "damage_type": "piercing",
        "lethality": "lethal", "recipient": "attacker", "trigger": "when_struck",
        "duration": {"amount": 1, "unit": "round"},
    }])
    druid = caster("druid", 10, ("thorn-body",))
    scene, engine = table(druid)

    out = cast(engine, "thorn-body", at="pc")
    assert "takes" not in out.tell, f"the caster was hurt by their own thorns: {out.tell}"
    assert len(scene.wards) == 1
    ward = scene.wards[0]
    assert (ward.owner, ward.recipient, ward.trigger) == ("pc", "attacker", "when_struck")

    druid_hp, thug_hp = scene.actors["pc"].hp, scene.actors["c1"].hp
    engine._ensure_encounter("c1")         # the gate defers a swing that opens a fight
    hit = engine.run(engine.validate([
        {"op": "attack", "actor": "c1", "target": "pc", "params": {"weapon": "sap"}}
    ])).outcomes[0]

    assert scene.actors["c1"].hp < thug_hp, f"the thorns did not bite: {hit.tell}"
    assert scene.actors["pc"].hp <= druid_hp        # they still took the sap
    assert "thug takes" in hit.tell and "Thorn Body" in hit.tell


def test_a_ranged_attacker_is_not_spiked():
    """1e: creatures using reach weapons are unaffected, and so is anyone shooting.

    Retribution is owed to a melee attack, not to every point of damage — a fireball does
    not get spiked either, which is why this fires in `_op_attack` rather than inside
    `_apply_damage`.
    """
    override("thorn-body", [{
        "type": "damage", "dice": "1d6", "damage_type": "piercing",
        "lethality": "lethal", "recipient": "attacker", "trigger": "when_struck",
        "duration": {"amount": 1, "unit": "round"},
    }])
    scene, engine = table(caster("druid", 10, ("thorn-body",)), enemy="watchman")
    cast(engine, "thorn-body", at="pc")
    scene.actors["c1"].weapons = list(scene.actors["c1"].weapons) + ["shortbow"]

    before = scene.actors["c1"].hp
    engine.run(engine.validate([
        {"op": "attack", "actor": "c1", "target": "pc", "params": {"weapon": "shortbow"}}
    ]))
    assert scene.actors["c1"].hp == before


def test_the_planner_refuses_to_treat_a_redirected_spec_as_the_spells_own_dice():
    """`casting_plan` used to claim any top-level `damage` spec as the dice the caster
    rolls now. A spec aimed at somebody who is not the target, or waiting on a trigger, is
    neither — and claiming it is how the thorns landed on the wrong creature."""
    retributive = {"type": "damage", "dice": "1d6", "damage_type": "piercing",
                   "recipient": "attacker", "trigger": "when_struck",
                   "duration": {"amount": 1, "unit": "round"}}
    spell = override("thorn-body", [retributive])
    plan = spells_mod.casting_plan(spell, 10)
    assert plan["dice"] == ""
    assert plan["riders"] == [retributive]


# --- the trigger --------------------------------------------------------------------------------

def test_a_trigger_that_is_not_immediate_needs_a_window_to_fire_in():
    """Without a duration `every round` has no rounds and `when struck` has no window, so
    the effect would be authored, accepted, and never happen once."""
    problems = fx.validate({"type": "damage", "dice": "1d6", "damage_type": "fire",
                            "lethality": "lethal", "trigger": "each_round"})
    assert any("needs a duration" in p for p in problems), problems


def test_incendiary_cloud_burns_every_round_rather_than_once():
    """6d6 fire, Reflex half, **every round**. As a save gate it fires at casting and
    never again; over a five-round cloud that is one fifth of the spell."""
    override("incendiary-cloud", [{
        "type": "manifest", "what": "a cloud of white-hot embers",
        "terrain": "obscuring", "shape": "radius", "size": 20,
        "duration": {"amount": 1, "unit": "round"},
        "on_enter": [{
            "type": "save_gate", "target": "ref", "dc": spells_mod.SAVE_DC_FORMULA,
            "recipient": "area", "trigger": "each_round",
            "on_failure": [{"type": "damage", "dice": "6d6", "damage_type": "fire",
                            "lethality": "lethal"}],
            "on_success": [{"type": "damage", "dice": "3d6", "damage_type": "fire",
                            "lethality": "lethal"}],
        }],
    }])
    scene, engine = table(caster(level=15, book=("incendiary-cloud",)))
    engine.run(engine.validate([{
        "op": "begin_encounter", "actor": "pc",
        "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    cast(engine, "incendiary-cloud", at="c1")

    standing = [w for w in scene.wards if w.trigger == "each_round"]
    assert len(standing) == 1 and standing[0].recipient == "area"

    before = scene.actors["c1"].hp
    scene.advance_turn()
    scene.advance_turn()
    burned = [h for h in scene.hazards if h["kind"] == "damage"]
    assert burned, "the cloud stood there and did nothing"
    assert scene.actors["c1"].hp < before
    assert all(h["source"] == "Incendiary Cloud" for h in burned)


def test_the_per_round_save_is_rolled_against_the_casters_own_dc():
    """The stored gate carries `spells.SAVE_DC_FORMULA`, a placeholder string. A ward that
    compared a roll against it would be a crash or, worse, a silent one — so the DC is
    computed at cast time and kept on the ward as a number."""
    override("incendiary-cloud", [{
        "type": "manifest", "what": "embers", "terrain": "obscuring",
        "shape": "radius", "size": 20, "duration": {"amount": 1, "unit": "round"},
        "on_enter": [{"type": "save_gate", "target": "ref",
                      "dc": spells_mod.SAVE_DC_FORMULA, "recipient": "area",
                      "trigger": "each_round",
                      "on_failure": [{"type": "damage", "dice": "6d6",
                                      "damage_type": "fire", "lethality": "lethal"}]}],
    }])
    scene, engine = table(caster(level=15, book=("incendiary-cloud",)))
    cast(engine, "incendiary-cloud", at="c1")
    assert isinstance(scene.wards[0].dc, int) and scene.wards[0].dc > 10


def test_a_hazard_inside_a_manifestation_inherits_its_lifetime():
    """The cloud's duration governs the burning inside it. Asking the inner effect to
    restate it would put the same fact in two places for the two to then disagree."""
    inner = {"type": "damage", "dice": "6d6", "damage_type": "fire",
             "lethality": "lethal", "recipient": "area", "trigger": "each_round"}
    assert fx.validate(inner) != []                  # on its own it needs a duration
    assert fx.validate({"type": "manifest", "what": "embers", "terrain": "obscuring",
                        "size": 20, "duration": {"amount": 5, "unit": "round"},
                        "on_enter": [inner]}) == []


# --- formulas ------------------------------------------------------------------------------------

@pytest.mark.parametrize("expr, cl, want", [
    ("caster_level", 7, 7),
    # Divine favor: "+1 luck per three caster levels, at least +1, maximum +3".
    ("min(1 + caster_level/3, 3)", 1, 1),
    ("min(1 + caster_level/3, 3)", 9, 3),
    ("min(1 + caster_level/3, 3)", 20, 3),
    # 1e floors every division. 5/2 is 2, never 2.5 and never 3.
    ("caster_level/2", 5, 2),
    ("max(caster_level - 4, 1)", 2, 1),
])
def test_a_formula_amount_is_the_number_the_book_prints(expr, cl, want):
    assert fx.evaluate(expr, {"caster_level": cl}) == want


def test_a_misspelled_variable_is_refused_rather_than_quietly_zero():
    """`caster_lvl` evaluates to 0 if nothing checks it — a +0 bonus, which looks exactly
    like a spell that did nothing and reports nothing at all."""
    problems = fx.validate({"type": "combat_mod", "amount": "caster_lvl",
                            "bonus_type": "luck", "target": "attack"})
    assert any("caster_lvl" in p and "caster_level" in p for p in problems), problems


def test_a_formula_cannot_reach_outside_arithmetic():
    """The evaluator runs an authored string. Attribute access, subscripts, comparisons
    and every call except min and max are refused by the parse, not by a blocklist."""
    for bad in ("__import__('os')", "open('x')", "a.b", "[1][0]", "1 if x else 2"):
        assert not fx.is_formula(bad), bad


def test_an_integer_amount_is_not_sent_through_the_evaluator():
    """A bare number is a number. `is_formula` answering True for "7" — or for `None` —
    would have the engine rewriting every absent amount as zero."""
    assert fx.is_formula(2) is False
    assert fx.is_formula("2") is False
    assert fx.is_formula(None) is False


@pytest.mark.parametrize("notation, cl, want", [
    # Harm: a flat 10 points per caster level, maximum 150. `dice: "10"` is wrong at every
    # caster level above 1st.
    ("10/level, max 150", 15, "150"),
    ("10/level, max 150", 8, "80"),
    ("10/level, max 150", 20, "150"),
    ("1d6/2 levels", 7, "3d6"),
    # At least one die: the smallest the effect can be, not nothing at all.
    ("1d8/2 levels", 1, "1d8"),
    ("2d4", 9, "2d4"),                              # plain dice pass straight through
])
def test_dice_can_scale_per_level(notation, cl, want):
    assert fx.validate({"type": "damage", "dice": notation, "damage_type": "negative",
                        "lethality": "lethal"}) == []
    assert fx.resolve_dice(notation, cl) == want


# --- manifest: the user's "temp-spawning" ---------------------------------------------------------

def test_fog_cloud_writes_real_squares_onto_the_map():
    """The user's own example. `Grid.obscuring` is a set the map already draws and that
    `line_of_sight` already reads, so a bank of fog is 61 squares of it — not a sentence."""
    override("fog-cloud", [{
        "type": "manifest", "what": "a bank of fog", "terrain": "obscuring",
        "shape": "radius", "size": 20, "duration": {"amount": 10, "unit": "minute"},
    }])
    scene, engine = table(caster(book=("fog-cloud",)))
    assert scene.grid.line_of_sight((5, 5), (12, 5)) is True

    out = cast(engine, "fog-cloud")

    assert len(scene.manifests) == 1
    made = scene.manifests[0]
    assert made.terrain == "obscuring" and len(made.squares) == 61
    assert scene.grid.obscuring, "the fog never reached the map"
    assert scene.grid.line_of_sight((5, 5), (12, 5)) is False, "sight went through the fog"
    assert "bank of fog" in out.tell
    # minutes/level (10) at caster level 10 is 100 minutes, which is 1,000 rounds.
    assert made.rounds_left == 1000


def test_the_fog_lifts_and_takes_only_its_own_squares_with_it():
    """Clearing on expiry removes what this thing *added*, never what was already there.
    A fog cloud rolled over a stone pillar covers the pillar's square and did not make it
    opaque; taking the fog off must not take the pillar's opacity with it."""
    scene = Scene(location_id="x", grid=Grid(width=10, height=10))
    scene.grid.obscuring.add((1, 1))                # a pillar that was always there
    made = scene.place(Manifestation(what="fog", terrain="obscuring",
                                     squares=[(1, 1), (1, 2), (2, 2)], rounds_left=1))
    assert scene.grid.obscuring == {(1, 1), (1, 2), (2, 2)}
    assert made.added == [(1, 2), (2, 2)]

    scene.lift(made)
    assert scene.grid.obscuring == {(1, 1)}
    assert scene.manifests == []


def test_a_wall_blocks_movement_because_blocked_is_a_real_square_set():
    scene = Scene(location_id="x", grid=Grid(width=12, height=12))
    scene.place(Manifestation(what="a wall of stone", terrain="blocked",
                              squares=[(3, y) for y in range(12)]))
    assert scene.grid.passable((3, 4)) is False
    assert (6, 4) not in scene.grid.reachable((1, 4), 60)


def test_a_manifestation_with_no_map_is_recorded_rather_than_refused():
    """Most scenes have no grid — a conversation in a tavern has no squares — and a spell
    that refuses to work outside a fight is worse than one placed in the fiction."""
    override("fog-cloud", [{
        "type": "manifest", "what": "a bank of fog", "terrain": "obscuring",
        "shape": "radius", "size": 20, "duration": {"amount": 10, "unit": "minute"},
    }])
    scene, engine = table(caster(book=("fog-cloud",)), grid=False)
    out = cast(engine, "fog-cloud")
    assert len(scene.manifests) == 1
    assert scene.manifests[0].squares == []
    assert "no map" in out.tell


def test_a_shape_that_changes_its_squares_must_say_how_big_it_is():
    problems = fx.validate({"type": "manifest", "what": "fog", "terrain": "obscuring"})
    assert any("size in feet" in p for p in problems), problems
    # A thing that occupies no squares — a light, a sound, an image — needs no size.
    assert fx.validate({"type": "manifest", "what": "four dancing lights",
                        "terrain": "none"}) == []


# --- summon --------------------------------------------------------------------------------------

def test_a_summon_arrives_through_the_same_door_a_spawn_does():
    """Routed to `bestiary.instantiate` rather than given a creature system of its own: a
    summoning spell and a GM saying "two bravos step out of the dark" are one event."""
    override("summon-monster-1", [{
        "type": "summon", "creature": "guard dog", "count": 1, "side": "caster",
        "duration": {"amount": 5, "unit": "round"},
    }])
    scene, engine = table(caster(book=("summon-monster-1",)))
    out = cast(engine, "summon-monster-1")

    arrived = [e for e in out.effects if e.get("kind") == "summon"]
    assert arrived and len(arrived[0]["actors"]) == 1
    assert arrived[0]["actors"][0]["ref"] in scene.actors


def test_an_unknown_creature_is_refused_by_name_rather_than_invented():
    """A summon that quietly produces nothing is a spell the player paid a slot for and
    cannot tell did not work."""
    override("summon-monster-1", [{
        "type": "summon", "creature": "hemispherical grue", "count": 1,
        "duration": {"amount": 5, "unit": "round"},
    }])
    scene, engine = table(caster(book=("summon-monster-1",)))
    out = cast(engine, "summon-monster-1")
    assert len(scene.actors) == 2, "something arrived that does not exist"
    assert "Nothing arrives" in out.tell and "grue" in out.tell


def test_a_summoned_creature_fights_for_the_caster():
    """Every arrival used to join "them", so a wizard's own dog counted against them and
    the fight could not end while it was standing."""
    override("summon-monster-1", [{
        "type": "summon", "creature": "guard dog", "count": 1, "side": "caster",
        "duration": {"amount": 5, "unit": "round"},
    }])
    scene, engine = table(caster(book=("summon-monster-1",)))
    engine.run(engine.validate([{
        "op": "begin_encounter", "actor": "pc",
        "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    cast(engine, "summon-monster-1")
    assert "c2" in scene.sides["pc"]


# --- spell_operation: the user's "permanency" ------------------------------------------------------

def test_permanency_makes_the_fog_it_follows_permanent():
    """The user's own example, and the reason `spell_operation` exists.

    It acts on a real lifetime — the manifestation's `rounds_left` — rather than on a
    sentence. Before this the whole family (permanency, dispel magic, break enchantment,
    counterspelling) was a `narrative` spec in 184 places.
    """
    override("fog-cloud", [{
        "type": "manifest", "what": "a bank of fog", "terrain": "obscuring",
        "shape": "radius", "size": 20, "duration": {"amount": 10, "unit": "minute"},
    }])
    override("permanency", [{
        "type": "spell_operation", "operation": "make_permanent", "target": "fog cloud",
    }])
    scene, engine = table(caster(level=11, book=("fog-cloud", "permanency")))

    cast(engine, "fog-cloud")
    assert scene.manifests[0].rounds_left == 1100        # 110 minutes at caster level 11

    out = cast(engine, "permanency")
    assert scene.manifests[0].rounds_left is None, "it still has a clock on it"
    assert "will not expire" in out.tell

    # And a permanent thing does not tick away.
    scene.tick_standing(5000)
    assert scene.manifests and scene.manifests[0].rounds_left is None


def test_dispel_magic_rolls_the_caster_level_check_the_book_calls_for():
    """A DC on the spec means a d20 + caster level against it, and a failed check leaves
    the magic standing rather than half-ending it."""
    override("fog-cloud", [{
        "type": "manifest", "what": "a bank of fog", "terrain": "obscuring",
        "shape": "radius", "size": 20, "duration": {"amount": 10, "unit": "minute"},
    }])
    override("dispel-magic", [{
        "type": "spell_operation", "operation": "dispel", "target": "fog cloud",
        "check_dc": "11 + caster_level",
    }])
    scene, engine = table(caster(level=11, book=("fog-cloud", "dispel-magic")))
    cast(engine, "fog-cloud")
    out = cast(engine, "dispel-magic")

    checks = [e for e in out.effects if e.get("kind") == "caster_level_check"]
    assert checks and checks[0]["dc"] == 22
    if checks[0]["beat"]:
        assert scene.manifests == [] and scene.grid.obscuring == set()
    else:
        assert scene.manifests, "it was dispelled on a failed check"


def test_countering_is_reported_rather_than_pretended():
    """It resolves during another creature's casting and there is no readied-action step
    to hang it on. Said out loud, not answered with a shrug."""
    override("dispel-magic", [{
        "type": "spell_operation", "operation": "counter", "target": "the spell being cast",
    }])
    scene, engine = table(caster(level=11, book=("dispel-magic",)))
    out = cast(engine, "dispel-magic")
    assert "GM adjudicates" in out.tell


# --- concealment ------------------------------------------------------------------------------------

def test_displacement_is_a_miss_chance_and_not_an_armour_bonus():
    """Displacement, blur, entropic shield and blurred movement are *entirely* this and
    were entirely inert. Writing 50% as an AC bonus would change which attacks land
    rather than how many, which is a different spell."""
    override("displacement", [{
        "type": "concealment", "miss_chance": 50, "recipient": "target",
        "duration": {"amount": 1, "unit": "round"},
    }])
    scene, engine = table(caster(book=("displacement",)))
    ac_before = scene.actors["pc"].ac()

    cast(engine, "displacement", at="pc")
    assert scene.actors["pc"].concealment() == (50, "Displacement")
    assert scene.actors["pc"].ac() == ac_before, "concealment moved the AC"

    # And it is actually rolled: over twenty swings from twenty seeds, some are lost to
    # the miss chance and say so.
    lost = 0
    for seed in range(20):
        e = Engine(scene, Dice(seed=seed))
        got = e.run(e.validate([{"op": "attack", "actor": "c1", "target": "pc",
                                 "params": {"weapon": "sap"}}])).outcomes[0]
        lost += "finds nothing there" in got.tell
    assert lost, "the miss chance was never rolled"


def test_concealment_does_not_stack_with_concealment():
    """Two 20% miss chances are not 40% in 1e, and they are not 36% either. The best
    source wins."""
    pc = caster()
    pc.add_buff("concealment", "miss_chance", 20, source="blur")
    pc.add_buff("concealment", "miss_chance", 50, source="displacement")
    assert pc.concealment()[0] == 50


def test_invisibility_finally_means_something():
    """`invisible` sat on the unimplemented-condition ledger in tests/test_reference.py
    for want of a miss chance. It carries one now, and the +2 to hit the book gives it."""
    from rules.tables import CONDITIONS

    assert CONDITIONS["invisible"]["concealment"] == 50
    pc = caster()
    pc.add_condition("invisible")
    assert pc.concealment() == (50, "invisible")
    assert any(m.value == 2 for m in pc.attack_modifiers())


# --- one of several ------------------------------------------------------------------------------

def test_a_choice_applies_one_option_and_never_all_of_them():
    """Every polymorph spell — beast shape, elemental body, plant shape, monstrous
    physique, vermin shape — plus blindness/deafness, ego whip, joyful rapture and wish's
    nine. Emitted as separate specs they all apply at once, which is a druid becoming
    five animals simultaneously."""
    spec = {"type": "choose_one", "options": [
        {"type": "apply_condition", "target": "blinded"},
        {"type": "apply_condition", "target": "deafened"},
    ]}
    assert fx.validate(spec) == []
    assert fx.render(spec) == "One of: Causes blinded / Causes deafened"

    chosen = dict(spec, chosen=2)
    assert fx.render(chosen) == "Chosen: Causes deafened"


def test_one_option_is_not_a_choice():
    problems = fx.validate({"type": "choose_one", "options": [
        {"type": "apply_condition", "target": "blinded"}]})
    assert any("at least two options" in p for p in problems), problems


def test_an_unchosen_choice_applies_nothing_and_says_the_options():
    """Applying all of them is the failure this type exists to stop, so the honest answer
    to "which one?" being unanswered is none of them, out loud."""
    override("beast-shape-i", [{
        "type": "choose_one", "duration": {"amount": 1, "unit": "minute"},
        "options": [
            {"type": "bundle", "label": "Small animal", "effects": [
                {"type": "ability_mod", "amount": 2, "bonus_type": "size",
                 "target": "dex"}]},
            {"type": "bundle", "label": "Medium animal", "effects": [
                {"type": "ability_mod", "amount": 2, "bonus_type": "size",
                 "target": "str"}]},
        ],
        "trigger": "on_cast", "recipient": "self",
    }])
    scene, engine = table(caster(book=("beast-shape-i",)))
    out = cast(engine, "beast-shape-i", at="pc")
    assert "until one is chosen" in out.tell
    assert "Small animal" in out.tell and "Medium animal" in out.tell

    out = cast(engine, "beast-shape-i", at="pc", choose=1)
    assert "Small animal" in out.tell and "until one is chosen" not in out.tell


# --- objects ----------------------------------------------------------------------------------------

def test_damage_to_gear_goes_through_hardness():
    """`rules/sheet.py` gives every Item a hardness and hit points; this is the missing
    way for an authored effect to reach them."""
    pc = caster()
    scene, engine = table(pc)
    got, tells = engine._object_damage(
        {"type": "object_damage", "dice": "30", "damage_type": "acid",
         "recipient": "target"},
        {"caster": "pc", "targets": ["c1"], "caster_level": 10})
    assert got and all(e["kind"] == "item_damage" for e in got)
    assert any(e["hardness"] for e in got), "hardness was not applied"


# --- honesty ------------------------------------------------------------------------------------------

def test_every_executable_type_has_something_that_executes_it():
    """The ask's own rule: no type may be `narrative` wearing a costume.

    Anything the catalogue claims the engine runs is either resolved by `_run_one`, rolled
    by the cast path, or applied by an existing op. This is the list, checked against the
    engine rather than believed.
    """
    from rules.engine import Engine as E

    runs = set(E._EXECUTES)
    # The ones that were executable before any of this, resolved through `casting_plan`,
    # `_op_buff`, `_op_condition` and their neighbours rather than through `_run_one`.
    already = {
        "ability_mod", "skill_mod", "save_mod", "combat_mod", "heal", "damage", "temp_hp",
        "fast_healing", "bleed", "ability_damage", "ability_drain", "ability_restore",
        "apply_condition", "remove_condition", "suppress_condition", "resistance",
        "damage_reduction", "immunity", "vulnerability", "save_gate", "object_damage",
    }
    claimed = {t.id for c in fx.CATEGORIES for t in c.types if t.engine}
    assert claimed - runs - already == set(), \
        "a type claims the engine runs it and nothing does"


def test_every_declarative_type_says_what_is_recorded_instead():
    """A type the engine cannot run is allowed and marked, never silently accepted."""
    for cat in fx.CATEGORIES:
        for t in cat.types:
            if not t.engine:
                assert len(t.blocked) > 40, f"{t.id} is not executed and does not say why"


def test_the_new_types_all_render_a_readable_line():
    """The card is read by a player. A type whose `render` falls through to the default
    prints its own name, which tells nobody anything."""
    samples = [
        ({"type": "manifest", "what": "a bank of fog", "terrain": "obscuring",
          "shape": "radius", "size": 20}, "20-foot radius spread"),
        ({"type": "summon", "creature": "celestial dog", "count": 2}, "Summons 2"),
        ({"type": "spell_operation", "operation": "dispel", "target": "one effect"},
         "End it"),
        ({"type": "concealment", "miss_chance": 20}, "20% miss chance"),
        ({"type": "spell_resistance", "amount": "12 + caster_level"},
         "Spell resistance 12 + caster_level"),
        ({"type": "negative_level", "amount": 2}, "2 negative levels"),
        ({"type": "attitude", "target": "friendly"}, "friendly"),
        ({"type": "object_damage", "dice": "2d6", "damage_type": "acid"},
         "everything carried"),
        ({"type": "bundle", "label": "bear", "effects": [
            {"type": "ability_mod", "amount": 2, "bonus_type": "size", "target": "str"}]},
         "bear: +2 Strength"),
    ]
    for spec, wanted in samples:
        line = fx.render(spec)
        assert wanted in line, f"{spec['type']}: {line!r} does not contain {wanted!r}"
        assert line != spec["type"], f"{spec['type']} rendered as its own id"


def test_a_formula_amount_survives_being_rendered():
    """`int(amount)` on a formula was a crash on the card, and the card is drawn on every
    keystroke in the builder."""
    assert fx.render({"type": "combat_mod", "amount": "min(1 + caster_level/3, 3)",
                      "bonus_type": "luck", "target": "attack"}) == \
        "min(1 + caster_level/3, 3) Attack rolls"


# --- durations --------------------------------------------------------------------------------------

@pytest.mark.parametrize("line, want", [
    # Sixteen spells state a rolled length and every one was refused: `amount` is an
    # integer everywhere else in the dict, so the shape had nowhere to go.
    ("rounds (2d4)", {"kind": "rolled", "dice": "2d4", "unit": "round"}),
    ("hours (4d12) (see text)", {"kind": "rolled", "dice": "4d12", "unit": "hour"}),
    # Three lines were refused for want of two dictionary entries.
    ("weeks/level (1)", {"kind": "per_level", "amount": 1, "unit": "week"}),
    ("months (1)", {"kind": "fixed", "amount": 1, "unit": "month"}),
])
def test_durations_the_parser_used_to_refuse(line, want):
    got = spells_mod.parse_duration(line)
    for key, value in want.items():
        assert got.get(key) == value, f"{line!r} -> {got}"


def test_a_fixed_base_with_a_per_level_tail_keeps_its_base():
    """"rounds (1) + rounds/3 levels (1)" — the per-level search found the tail and
    returned, so the guaranteed first round simply was not there."""
    got = spells_mod.parse_duration("rounds (1) + rounds/3 levels (1)")
    assert got["kind"] == "per_level" and got["per_levels"] == 3
    assert got["base"] == 1 and got["base_unit"] == "round"

    class Fake:
        duration_value = got
    assert spells_mod.duration_rounds(Fake, 9) == 1 + 3        # 1 + (9//3)


def test_concentration_plus_a_tail_is_not_concentration_capped_at_it():
    """"concentration + rounds/level (1)" runs while you concentrate *and then* the tail;
    "concentration, up to rounds/level (1)" ends at the tail either way. Both were being
    flattened into the same dict, and a card that says "up to 5 rounds" about the first is
    telling the player the wrong thing."""
    plus = spells_mod.parse_duration("concentration + rounds/level (1)")
    capped = spells_mod.parse_duration("concentration, up to rounds/level (1)")
    assert plus.get("concentration_plus") is True
    assert "concentration_plus" not in capped
    assert plus["concentration"] is capped["concentration"] is True


def test_a_rolled_duration_is_rolled_once_by_the_engine_and_not_by_a_card():
    """`duration_rounds` stays deterministic — it is called by every card, tooltip and
    preview, and one that re-rendered a shorter number each time it was drawn would be
    worse than one that says "2d4 rounds"."""
    class Fake:
        duration_value = {"kind": "rolled", "dice": "2d4", "unit": "round"}

    assert spells_mod.duration_rounds(Fake, 10) is None
    got = spells_mod.roll_duration(Fake, 10, Dice(seed=3))
    assert 2 <= got <= 8


# --- the scene keeps its own house in order -----------------------------------------------------------

def test_a_ward_leaves_with_the_creature_it_names():
    """`Scene.depart`'s own docstring: a ref left behind in one structure is one more
    place for a ghost to keep acting from — and this one would fire every round."""
    scene, engine = table(caster())
    scene.wards.append(Ward(owner="c1", trigger="each_round", source="a curse",
                            spec={"type": "damage", "dice": "1d6"}))
    scene.depart("c1")
    assert scene.wards == []


def test_the_fog_goes_with_the_map_it_was_drawn_on():
    """`end_encounter` drops the grid. A manifestation kept past it is a bank of fog with
    no location, and the next fight lays a fresh grid without its squares."""
    scene, engine = table(caster())
    scene.place(Manifestation(what="fog", terrain="obscuring", squares=[(1, 1)]))
    scene.wards.append(Ward(owner="pc", trigger="each_round", source="fog"))
    scene.end_encounter()
    assert scene.manifests == [] and scene.wards == [] and scene.hazards == []


def test_a_hazard_that_drops_the_last_creature_standing_is_still_narrated():
    """One `advance_turn` rolls the round over as many times as it takes to find somebody
    up, so a cloud that drops the last conscious NPC ticks again on the way out. An
    assignment there lost the tick that did the dropping: measured, an incendiary cloud
    took a thug from 13 hit points to -6 and `scene.hazards` came back empty."""
    scene, engine = table(caster())
    scene.initiative = [("pc", 20), ("c1", 10)]
    scene.turn = 0
    scene.wards.append(Ward(
        owner="c1", trigger="each_round", recipient="target", source="a burning cloud",
        spec={"type": "damage", "dice": "100", "damage_type": "fire",
              "lethality": "lethal"}))

    for _ in range(3):
        scene.advance_turn()
    assert scene.actors["c1"].hp < 0
    assert any(h["kind"] == "damage" for h in scene.hazards), \
        "the thing that dropped them was not reported"
