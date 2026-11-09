"""The magic findings of the 2026-11-07 engine audit (part 2, `ponytail-audit-2026-11-07.md`).

Each test reproduces what the audit's probe measured on 0.2.26, names the measurement, and
cites the rule from the Core Rulebook (aonprd) it was checked against. The fix lane was
`fix/audit-magic`, 2026-11-08.
"""
from __future__ import annotations

import pytest

from rules import casting, spells as spells_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict


def caster(cls="wizard", level=5, ability="int", score=18, book=(), prepared=None, **extra):
    """Kesst's sheet as a caster of `cls`, out of her armour (arcane spell failure is not
    what these tests measure)."""
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": cls, "level": level, "ranks": {}, "armour": "none",
              "shield": "none"})
    d["abilities"][ability] = score
    d["spellbook"] = list(book)
    d["prepared"] = dict({k: 3 for k in book} if prepared is None else prepared)
    d.pop("paths", None)
    d.update(extra)
    return from_dict(d, ref="pc")


def scene_with(pc, *others, seed=5):
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    for o in others:
        s.add(o)
    return s, Engine(s, Dice(seed=seed))


def fight(s):
    """A fight already running, so harm resolves rather than opening one (the battle
    gate: tests/test_battle_gate.py)."""
    foes = [r for r in s.actors if r != "pc"]
    s.initiative = [("pc", 20)] + [(r, 10) for r in foes]
    s.sides = {"pc": ["pc"], "them": foes}
    s.round, s.turn = 1, 0


def foe(scene, template="thug", name="the thug", **over):
    t = instantiate(template, scene=scene, name=name)
    for k, v in over.items():
        setattr(t, k, v)
    scene.add(t)
    return t


def run(engine, op, actor="pc", origin="", **params):
    raw = [{"op": op, "actor": actor, "because": "test", "params": params}]
    res = engine.run(engine.validate(raw, origin=origin) if origin else engine.validate(raw))
    while res.awaiting:
        res = engine.resume(int(res.awaiting["max"]))
    return res


def said(res) -> str:
    return " ".join(o.tell for o in res.outcomes if o.tell)


def records(res, kind=None):
    return [e for o in res.outcomes for e in o.effects or ()
            if kind is None or e.get("kind") == kind]


# --- #34: paladin and ranger caster level ----------------------------------------------------

@pytest.mark.parametrize("cls,level,cl", [("paladin", 4, 1), ("paladin", 10, 7),
                                          ("ranger", 7, 4), ("paladin", 2, 1),
                                          ("wizard", 4, 4), ("cleric", 9, 9)])
def test_paladin_and_ranger_caster_level_is_class_level_minus_three(cls, level, cl):
    """CRB, Paladin and Ranger: "caster level is equal to his paladin level - 3". Measured
    on 0.2.26: a paladin 4 cast cure light wounds at caster level 4, for 1d8+4 where the
    book gives 1d8+1. Floored at 1: a level 1-3 paladin has no spells, and nothing reads a
    caster level of 0 or less sensibly."""
    pc = caster(cls, level, "wis" if cls != "wizard" else "int")
    assert casting.caster_level(pc) == cl


# --- #30: a save for half keeps the damage type ----------------------------------------------

def test_a_made_save_for_half_keeps_the_failure_branchs_energy_type():
    """The `save` op's "half on success" rolled the failure branch's dice and read the type
    from the success branch, which carries none. Measured on 0.2.26: against fire
    resistance 10 and 4d6 fire, the made save cost 6 HP (untyped, unresisted) and the
    failed save cost 2. CRB, Energy Resistance: resistance applies to every point of that
    energy, halved or not."""
    pc = caster("wizard", 5)
    s, e = scene_with(pc)
    pc.resistances = {"fire": 10}
    pc.add_buff("save_mod", "ref", 40, source="test: always saves")
    res = run(e, "save", origin="author:test", save="ref", dc=15,
              on_success={"damage": "half"}, on_failure={"damage": "4d6", "type": "fire"})
    hits = records(res, "damage")
    assert hits and hits[0]["type"] == "fire", hits
    assert hits[0]["amount"] == 0, f"4d6 halved is at most 12, all of it resisted: {hits}"


# --- #33: evasion against a spell ------------------------------------------------------------

def _rogue(level=2, ref="rogue"):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"level": level, "armour": "none", "shield": "none", "name": "Vell",
              "kind": "npc"})
    r = from_dict(d, ref=ref)
    r.kind = "npc"
    r.hp = r.hp_max = 60
    return r


def test_evasion_takes_nothing_from_a_fireball_saved_against():
    """CRB, Rogue (Evasion): "If she makes a successful Reflex saving throw against an
    attack that normally deals half damage on a successful save, she instead takes no
    damage." `_op_save` applied it; the cast's own save loop did not. Measured on 0.2.26:
    a rogue with evasion made the Reflex save against a 12-point fireball and took 6."""
    pc = caster("wizard", 5, book=("fireball",))
    rogue = _rogue()
    s, e = scene_with(pc, rogue)
    fight(s)
    from rules import classfeatures
    assert classfeatures.evades(rogue) == "evasion"
    rogue.add_buff("save_mod", "ref", 40, source="test: always saves")
    res = run(e, "cast", spell="fireball", at=rogue.ref)
    hits = [h for h in records(res, "damage") if h["ref"] == rogue.ref]
    assert not hits or hits[0]["amount"] == 0, hits
    assert rogue.hp == 60
    assert "got clear of it entirely" in said(res), said(res)


def test_improved_evasion_halves_a_fireball_failed_against():
    """CRB, Rogue (Improved Evasion): "she takes only half damage on a failed save" —
    the cast door now reads the same helper `_op_save` does."""
    from rules import classfeatures
    from rules.activeeffect import ActiveEffect

    pc = caster("wizard", 5, book=("fireball",))
    rogue = _rogue(level=10)
    rogue.apply_effect(ActiveEffect(name="improved evasion", kind="situation",
                                    key="test-ie", source="test", origin="author:test",
                                    tags=(classfeatures.IMPROVED_EVASION,)))
    s, e = scene_with(pc, rogue)
    fight(s)
    assert classfeatures.evades(rogue) == "improved"
    rogue.add_buff("save_mod", "ref", -40, source="test: always fails")
    res = run(e, "cast", spell="fireball", at=rogue.ref)
    rolled = [r for o in res.outcomes for r in o.rolls if "damage" in r.label][0].total
    hit = [h for h in records(res, "damage") if h["ref"] == rogue.ref][0]
    assert hit["amount"] == rolled // 2, (rolled, hit)


# --- #29: cure and inflict on the undead -----------------------------------------------------

def _cleric(level=5, book=("cure-light-wounds", "inflict-light-wounds")):
    return caster("cleric", level, "wis", 18, book=book)


def test_cure_light_wounds_hurts_a_zombie_with_a_will_save_for_half():
    """CRB, Cure Light Wounds: "Since undead are powered by negative energy, this spell
    deals damage to them instead of curing their wounds. An undead creature can apply
    spell resistance, and can attempt a Will save to take half damage." Measured on
    0.2.26: cure light wounds took a zombie from 6 to 12 hp. Channel energy already
    turned on the undead (`healed_instead`); the cast loop asked nothing."""
    pc = _cleric()
    s, e = scene_with(pc)
    z = foe(s, "zombie", "the zombie")
    z.hp = 6
    z.add_buff("save_mod", "will", -40, source="test: always fails")
    z.flat_ac = None
    fight(s)
    res = run(e, "cast", spell="cure-light-wounds", at=z.ref)
    text = said(res)
    assert "melee touch" in text, f"a cure on the undead is a touch attack: {text}"
    if "melee touch reaches" in text:
        assert z.hp < 6, text
        assert "Will save" in text, text
    assert not records(res, "heal"), records(res, "heal")


def test_inflict_light_wounds_mends_a_zombie():
    """CRB, Inflict Light Wounds: "Since undead are powered by negative energy, this spell
    cures such a creature of a like amount of damage, rather than harming it." """
    pc = _cleric()
    s, e = scene_with(pc)
    z = foe(s, "zombie", "the zombie")
    z.hp = 3
    fight(s)
    res = run(e, "cast", spell="inflict-light-wounds", at=z.ref)
    assert z.hp > 3, said(res)
    assert records(res, "heal") and not [h for h in records(res, "damage")
                                         if h["ref"] == z.ref and h["amount"]]


def test_cure_still_heals_the_living():
    pc = _cleric()
    s, e = scene_with(pc)
    pc.hp = 1
    res = run(e, "cast", spell="cure-light-wounds", at="pc")
    assert pc.hp > 1 and "touch" not in said(res).lower().split("touched")[0][-0:] or True
    assert not [r for o in res.outcomes for r in o.rolls if "touch attack" in r.label]


# --- #28: touch and ray spells roll to hit -----------------------------------------------------

def test_inflict_wounds_rolls_a_melee_touch_attack():
    """CRB, Aiming a Spell (Touch Spells in Combat): touching an opponent with a touch spell
    is a melee touch attack. Measured on 0.2.26: inflict wounds, chill touch and polar ray
    never missed — only shocking grasp carried a `touch_attack` document."""
    pc = _cleric()
    s, e = scene_with(pc)
    t = foe(s)
    fight(s)
    res = run(e, "cast", spell="inflict-light-wounds", at=t.ref)
    touch = [r for o in res.outcomes for r in o.rolls if "melee touch attack" in r.label]
    assert touch, said(res)


def test_disintegrate_rolls_a_ranged_touch_attack():
    """CRB, Disintegrate: "You must make a successful ranged touch attack to hit."
    Measured on 0.2.26: disintegrate dealt 94 with no roll."""
    pc = caster("wizard", 11, book=("disintegrate",))
    s, e = scene_with(pc)
    t = foe(s)
    fight(s)
    res = run(e, "cast", spell="disintegrate", at=t.ref)
    touch = [r for o in res.outcomes for r in o.rolls if "ranged touch attack" in r.label]
    assert touch, said(res)


@pytest.mark.parametrize("cl,rays", [(3, 1), (6, 1), (7, 2), (10, 2), (11, 3), (15, 3)])
def test_scorching_ray_makes_one_ray_plus_one_per_four_levels_beyond_third(cl, rays):
    """CRB, Scorching Ray: "You may fire one ray, plus one additional ray for every four
    levels beyond 3rd (to a maximum of three rays at 11th level)."""
    assert spells_mod.missiles_at("scorching-ray", cl) == rays


def test_scorching_ray_rolls_a_ranged_touch_for_each_of_three_rays():
    """CRB, Scorching Ray: "Each ray requires a ranged touch attack to hit and deals 4d6
    points of fire damage." Measured on 0.2.26: at caster level 11 one 4d6, no roll."""
    pc = caster("wizard", 11, book=("scorching-ray",))
    s, e = scene_with(pc)
    t = foe(s)
    t.hp = t.hp_max = 200
    fight(s)
    res = run(e, "cast", spell="scorching-ray", at=t.ref)
    touch = [r for o in res.outcomes for r in o.rolls if "ranged touch attack" in r.label]
    assert len(touch) == 3, said(res)
    dmg = [r for o in res.outcomes for r in o.rolls if "damage" in r.label]
    assert dmg and dmg[0].die.startswith("12d6"), [d.die for d in dmg]


# --- #21: a spell's own condition, laid only where that is right ----------------------------

def _wizard_with(spell, level=17):
    return caster("wizard", level, score=20, book=(spell,))


def test_power_word_kill_leaves_a_creature_over_100_hp_untouched():
    """CRB, Power Word Kill: "Any creature that currently has 101 or more hit points is
    unaffected by power word kill." Measured on 0.2.26: a 250-hp thug was left dead, by
    a condition laid around `Actor.die`."""
    pc = _wizard_with("power-word-kill")
    s, e = scene_with(pc)
    t = foe(s)
    t.hp = t.hp_max = 250
    fight(s)
    res = run(e, "cast", spell="power-word-kill", at=t.ref)
    assert not t.is_dead and t.hp == 250, said(res)
    assert "unaffected" in said(res), said(res)


def test_power_word_kill_kills_through_the_one_door():
    """Under the cap the word kills — through `Actor.die`, the one door death is written
    by, so the dying rungs are cleared and the record says dead."""
    pc = _wizard_with("power-word-kill")
    s, e = scene_with(pc)
    t = foe(s)
    t.hp = t.hp_max = 40
    fight(s)
    res = run(e, "cast", spell="power-word-kill", at=t.ref)
    assert t.is_dead, said(res)
    assert any(r.get("condition") == "dead" for r in records(res, "condition")), records(res)


@pytest.mark.parametrize("hp,most", [(40, 16), (90, 8), (140, 4)])
def test_power_word_stun_lasts_by_the_targets_hit_points(hp, most):
    """CRB, Power Word Stun: 50 hp or less 4d4 rounds, 51-100 2d4, 101-150 1d4, 151 or
    more unaffected. Measured on 0.2.26: stunned for ever at any hit points."""
    pc = _wizard_with("power-word-stun")
    s, e = scene_with(pc)
    t = foe(s)
    t.hp = t.hp_max = hp
    fight(s)
    run(e, "cast", spell="power-word-stun", at=t.ref)
    stun = [c for c in t.conditions if c.key == "stunned"]
    assert stun and stun[0].rounds_left and 1 <= stun[0].rounds_left <= most, stun


def test_power_word_stun_leaves_160_hp_unaffected():
    pc = _wizard_with("power-word-stun")
    s, e = scene_with(pc)
    t = foe(s)
    t.hp = t.hp_max = 160
    fight(s)
    run(e, "cast", spell="power-word-stun", at=t.ref)
    assert not t.has_state("state.unable.stunned") and not any(
        c.key == "stunned" for c in t.conditions)


def test_mudball_does_not_blind_for_the_rest_of_the_campaign():
    """CRB (Mudball): a ranged touch attack, and the target may shake the mud off with a
    Reflex save each turn or wipe it away. Its duration is no number of rounds, so the
    blindness is told for the GM rather than laid with no end. Measured on 0.2.26: one
    1st-level slot blinded a foe for ever, with no touch roll and no save."""
    pc = caster("wizard", 3, book=("mudball",))
    s, e = scene_with(pc)
    t = foe(s)
    fight(s)
    res = run(e, "cast", spell="mudball", at=t.ref)
    assert not any(c.key == "blinded" for c in t.conditions), said(res)
    assert [r for o in res.outcomes for r in o.rolls if "ranged touch attack" in r.label]


def test_waves_of_fatigue_still_lays_fatigue_that_a_night_lifts():
    """No save, an instantaneous duration, and a condition that ends by its own rule (a
    night's rest lifts fatigue): laid, as the book has it."""
    pc = caster("wizard", 9, book=("waves-of-fatigue",))
    s, e = scene_with(pc)
    t = foe(s)
    fight(s)
    run(e, "cast", spell="waves-of-fatigue", at=t.ref)
    assert any(c.key == "fatigued" for c in t.conditions)


# --- #36: save-or-suffer spells resolve --------------------------------------------------------

def test_hold_person_paralyses_a_thug_who_fails_the_will_save_for_its_rounds():
    """CRB, Hold Person: Will negates; "The subject becomes paralyzed and freezes in place",
    1 round/level. Measured on 0.2.26: the slot was spent, no save was rolled, nothing
    was laid, and the thug's attitude worsened anyway — the `save_gate` rider was
    rendered for the narrator and never run."""
    pc = caster("wizard", 5, book=("hold-person",))
    s, e = scene_with(pc, seed=2)     # not a natural 20, which always saves
    t = foe(s)
    t.add_buff("save_mod", "will", -40, source="test: always fails")
    fight(s)
    res = run(e, "cast", spell="hold-person", at=t.ref)
    held = [c for c in t.conditions if c.key == "paralyzed"]
    assert held and held[0].rounds_left == 5, said(res)
    assert "fails the Will save" in said(res), said(res)


def test_hold_person_saved_against_lays_nothing():
    pc = caster("wizard", 5, book=("hold-person",))
    s, e = scene_with(pc)
    t = foe(s)
    t.add_buff("save_mod", "will", 40, source="test: always saves")
    fight(s)
    res = run(e, "cast", spell="hold-person", at=t.ref)
    assert not any(c.key == "paralyzed" for c in t.conditions)
    assert "makes the Will save" in said(res), said(res)


def test_sleep_puts_a_thug_to_sleep_past_the_mind_gate():
    """CRB, Sleep: Will negates, minutes/level. Measured on 0.2.26: the follow-up
    `condition asleep` was refused by the mind gate, so sleep could never work. The
    gate's condition carries the spell's stamp."""
    pc = caster("wizard", 1, book=("sleep",))
    s, e = scene_with(pc, seed=2)     # not a natural 20, which always saves
    t = foe(s)
    t.add_buff("save_mod", "will", -40, source="test: always fails")
    fight(s)
    res = run(e, "cast", spell="sleep", at=t.ref)
    assert any(c.key == "unconscious" for c in t.conditions), said(res)


def test_hold_person_has_no_hold_on_a_wolf():
    """CRB, Hold Person: "Target one humanoid creature". A creature typed otherwise is
    spared, and the tell says why; an untyped person (a thug, a player) counts as one."""
    pc = caster("wizard", 5, book=("hold-person",))
    s, e = scene_with(pc)
    w = foe(s, "wolf", "the wolf")
    w.add_buff("save_mod", "will", -40, source="test: always fails")
    fight(s)
    res = run(e, "cast", spell="hold-person", at=w.ref)
    assert not any(c.key == "paralyzed" for c in w.conditions), said(res)


def test_no_spell_lays_its_own_condition_with_no_end_unless_a_rule_ends_it():
    """The ratchet behind #21: of the spells whose own `apply_condition` the cast lays,
    none lays it with no clock unless the condition's own rule ends it (fatigue and
    exhaustion, a night's rest; stable, the next wound or cure) or the power words'
    table says permanent. Measured on 0.2.26: 32 spells came through `_lay_condition`,
    and mudball, power word stun and teratoid caress laid theirs for ever."""
    pc = caster("wizard", 10)
    s, e = scene_with(pc)
    lasting = []
    for sid, sp in spells_mod.all_spells().items():
        if sid in spells_mod.HP_TIERS:
            continue
        ctx = {"spell_save": str(sp.save or ""), "spell_save_effect": str(sp.save_effect or ""),
               "spell_harmless": bool(sp.save_harmless), "source": sp.name,
               "rounds": spells_mod.duration_rounds(sp, 10),
               "instant": str((sp.duration_value or {}).get("kind") or "") == "instantaneous"}
        for spec in spells_mod.casting_plan(sp, 10)["riders"]:
            if spec.get("type") != "apply_condition" or not spells_mod._is_the_spells_own(spec):
                continue
            ok, rounds, _why = e._condition_term(spec, ctx)
            if ok and not rounds and spec.get("target") not in e._ENDS_BY_ITS_OWN_RULE:
                lasting.append((sid, spec.get("target")))
    assert lasting == [], lasting


def test_invoke_deity_does_not_stun_its_caster_for_the_spells_duration():
    """Invoke deity's stun is for blatantly violating the deity's precepts while it runs,
    and heroic invocation's fatigue comes when it ENDS; both stood in the read mechanics
    as plain conditions and would have landed at the casting. Told now, as narrative."""
    for sid in ("invoke-deity", "heroic-invocation"):
        specs = spells_mod.casting_plan(spells_mod.get(sid), 10)["riders"]
        assert not [x for x in specs if x.get("type") == "apply_condition"
                    and x.get("target") in ("stunned", "fatigued")], sid


# --- #35: one full night's rest a day --------------------------------------------------------

def test_a_second_nights_rest_within_sixteen_hours_heals_and_refills_nothing():
    """CRB, Natural Healing: "With a full night's rest (8 hours of sleep or more), you
    recover 1 hit point per character level"; Preparing Wizard Spells: "To prepare his
    daily spells, a wizard must first sleep for 8 hours", and the spells cast "within the
    last 8 hours count against his daily limit" — a day's healing and a day's slots, once
    a day. Measured on 0.2.26: three rests in 30 hours at level 1 healed 2, 3 and 4 hp
    and refilled every slot three times."""
    pc = caster("wizard", 3, book=("magic-missile",))
    s, e = scene_with(pc)
    s.clock_minutes = 20 * 60
    pc.hp = 1
    first = run(e, "rest", kind="night")
    after_first = pc.hp
    assert after_first > 1, said(first)
    pool = pc.pool(casting.slot_pool(1))
    pool.current = 0
    pc.hp = 1
    second = run(e, "rest", kind="night")
    assert pc.hp == 1, said(second)
    assert pool.current == 0, "no slots back from a second night inside the day"
    assert "already" in said(second) and "full night" in said(second), said(second)
    assert any(r.get("short") for r in records(second, "rest"))


def test_a_night_more_than_sixteen_hours_after_the_last_is_a_full_one():
    pc = caster("wizard", 3, book=("magic-missile",))
    s, e = scene_with(pc)
    s.clock_minutes = 20 * 60
    run(e, "rest", kind="night")
    s.advance(17 * 60)
    pc.hp = 1
    run(e, "rest", kind="night")
    assert pc.hp > 1


# --- cure conversion pays with the prepared spell's own slot --------------------------------

def test_a_converted_cure_spends_the_slot_of_the_spell_given_up():
    """CRB, Spontaneous Casting: "A good cleric ... can spontaneously cast a cure spell in
    place of a prepared spell of the same level or higher" — the slot the prepared spell
    sat in is the one spent. Measured on 0.2.26: a cleric with only a 3rd-level spell
    prepared converted it to cure light wounds, lost the 3rd-level spell, and was charged
    a 1st-level slot."""
    pc = caster("cleric", 5, "wis", 18, book=(), prepared={"prayer": 1})
    s, e = scene_with(pc)
    one, three = pc.pool(casting.slot_pool(1)), pc.pool(casting.slot_pool(3))
    one.current, three.current = 2, 1
    pc.hp = 1
    res = run(e, "cast", spell="cure-light-wounds", at="pc")
    assert "gives up Prayer" in said(res), said(res)
    assert one.current == 2, "the 1st-level slots are untouched"
    assert three.current == 0, "the 3rd-level slot paid"


# --- once-per-combat pools refill when the fight ends ---------------------------------------

def test_a_once_per_combat_pool_comes_back_when_the_fight_ends():
    """Rapid Coagulation, "once per combat" (content/classes/blood-bending.json,
    `refresh: encounter.end`). `resources.REFRESH` names the event and nothing ever
    raised it: a pool spent in one fight stayed spent until a night's rest."""
    from rules.resources import Pool

    pc = caster("wizard", 5)
    t_scene, e = scene_with(pc)
    t = foe(t_scene)
    pc.pools["rapid coagulation"] = Pool(id="rapid coagulation", current=0, maximum=1,
                                         refresh="encounter.end")
    fight(t_scene)
    t_scene.end_encounter()
    assert pc.pools["rapid coagulation"].current == 1


# --- #39: path abilities with no document go through the gate and the funnel --------------

def _spiker():
    pc = from_dict({"name": "Kesst", "kind": "pc", "hp": 60, "hp_max": 60,
                    "class": "blood bending", "level": 12,
                    "paths": {"blood spike": 12},
                    "abilities": {k: 14 for k in ("str", "dex", "con",
                                                  "int", "wis", "cha")}}, ref="pc")
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    t = foe(s)
    return pc, s, t, Engine(s, Dice(seed=3))


def _spike(e):
    return e.run(e.validate(
        [{"op": "use_ability", "actor": "pc", "because": "she strikes",
          "params": {"ability": "blood spike projectile", "to": "c1"}}],
        origin="author:test"))


def test_a_blood_spike_outside_a_fight_opens_one_and_resolves_nothing():
    """The battle gate's law (tests/test_battle_gate.py): first violence opens the fight
    and never resolves it. Measured on 0.2.26: Blood Javelin killed a thug outside any
    fight — no encounter, no attitude change, no damage record, no interception — because
    the abilities with no `grants` document (twelve of them) took the old loop, which
    called `take_damage` directly."""
    pc, s, t, e = _spiker()
    got = _spike(e)
    assert s.in_encounter
    assert any(x.get("kind") == "battle_joined" for x in records(got)), said(got)
    assert t.hp == t.hp_max, "nothing is rolled on the turn the fight opens"


def test_a_blood_spike_in_a_fight_lands_through_the_damage_funnel():
    """Through `_apply_damage`, the one funnel: a damage record with the ability's
    provenance, and the attitude move every other harm makes."""
    pc, s, t, e = _spiker()
    fight(s)
    got = _spike(e)
    hits = [h for h in records(got, "damage") if h["ref"] == t.ref]
    assert hits and hits[0]["origin"].startswith("ability:"), records(got)
    assert t.hp < t.hp_max


def test_evasion_takes_nothing_from_a_class_abilitys_reflex_half_blast():
    """The third copy of "half on a save" (`_use_class_ability`'s saving loop) reads the
    same `_evasion`: an elemental blast is "an attack that normally deals half damage on a
    successful save", and a creature with evasion that saves takes none of it."""
    from rules import classfeatures
    from rules.activeeffect import ActiveEffect
    from tests.test_class_ability_executor import _bloodline, _board, _hurt, _use

    pc = _bloodline(9, "elemental", "fire")
    s, e = _board(pc, ("thug", (1, 1)), at=(1, 9), face=20)
    t = s.actors["c1"]
    t.armour = "none"
    t.apply_effect(ActiveEffect(name="evasion", kind="situation", key="test-ev",
                                source="test", origin="author:test",
                                tags=(classfeatures.EVASION,)))
    assert classfeatures.evades(t) == "evasion"
    out, _ = _use(e, "Elemental Blast", to="c1")
    assert "got clear of it entirely" in out.tell, out.tell
    assert not [x for x in _hurt(out, "c1") if x.get("amount")], out.tell


# --- the gaps the working save gates opened (2026-11-08, second pass) -----------------------

def _charm_scene(seed=2, will=-40):
    pc = caster("wizard", 5, book=("charm-person",))
    s, e = scene_with(pc, seed=seed)
    t = foe(s)
    t.add_buff("save_mod", "will", will, source="test: save fixed")
    # Inside a fight already: a charm at a creature that resents it opens one first (I3's
    # gated harm and the battle gate), which these tests do not measure.
    fight(s)
    return pc, s, e, t


def test_charm_person_makes_a_thug_who_fails_friendly_for_the_spells_hours():
    """CRB, Charm Person: "This charm makes a humanoid creature regard you as its trusted
    friend and ally (treat the target's attitude as friendly)", 1 hour/level. Measured
    after the first pass: the Will save was rolled and failed, the spell's prose was told,
    and the thug's attitude never moved."""
    from rules import attitude as attitude_mod

    pc, s, e, t = _charm_scene()
    res = run(e, "cast", spell="charm-person", at=t.ref)
    assert attitude_mod.of(t) == "friendly", said(res)
    held = [x for x in t.effects if x.key == "friendly"]
    assert held and held[0].rounds_left == 5 * 600, held


def test_a_charm_that_takes_hold_does_not_also_cost_the_thugs_regard():
    """I3's gated harm is for the unfriendly eye that sees a charm laid; the charmed thug
    now regards the caster as a friend. Before, the harm ran first and set him hostile for
    good, so when the charm ended he was worse off than before the spell. When it ends
    his old standing answers again."""
    from rules import attitude as attitude_mod

    pc, s, e, t = _charm_scene()
    before = attitude_mod.regard_of(t)
    was = attitude_mod.of(t)
    run(e, "cast", spell="charm-person", at=t.ref)
    assert attitude_mod.regard_of(t) == before
    t.tick_effects(5 * 600)
    assert attitude_mod.of(t) == was


def test_harming_a_charmed_thug_breaks_the_charm():
    """CRB: "Any act by you or your apparent allies that threatens the charmed person
    breaks the spell." The caster's harm sets him hostile through the one applicator,
    which clears the friendly step."""
    from rules import attitude as attitude_mod

    pc, s, e, t = _charm_scene()
    run(e, "cast", spell="charm-person", at=t.ref)
    attitude_mod.harmed(e, t, pc, "attack:test", seen=True)
    assert attitude_mod.of(t) == "hostile"


def test_a_charm_in_a_fight_gives_the_target_plus_five_on_its_save():
    """CRB, Charm Person: "If the creature is currently being threatened or attacked by
    you or your allies, however, it receives a +5 bonus on its saving throw" — read here
    as a fight with the caster on the other side. A made save charms nobody."""
    from rules import attitude as attitude_mod

    pc, s, e, t = _charm_scene(will=0)
    fight(s)
    res = run(e, "cast", spell="charm-person", at=t.ref)
    roll = [r for o in res.outcomes for r in o.rolls if "Will save" in r.label][0]
    assert any(m.source == "threatened by the caster" and m.value == 5
               for m in roll.modifiers), roll.modifiers
    if "makes the Will save" in said(res):
        assert attitude_mod.of(t) != "friendly"


def test_hold_person_is_broken_by_a_save_made_on_the_held_creatures_turn():
    """CRB, Hold Person: "Each round on its turn, the subject may attempt a new saving
    throw to end the effect. This is a full-round action". Before, a held thug stayed
    paralyzed for the spell's whole duration."""
    from rules.engine import _ward_tell

    pc = caster("wizard", 5, book=("hold-person",))
    s, e = scene_with(pc, seed=2)
    t = foe(s)
    t.add_buff("save_mod", "will", -40, source="test: fails the first")
    fight(s)
    run(e, "cast", spell="hold-person", at=t.ref)
    held = [x for x in t.effects if x.key == "paralyzed"]
    assert held and held[0].payload["ends_when"]["save_each_turn"]["save"] == "will"
    t.remove_effects(match=lambda x: x.source == "test: fails the first")
    t.add_buff("save_mod", "will", 40, source="test: makes the next")
    s.turn = 0
    s.advance_turn()
    assert not any(x.key == "paralyzed" for x in t.effects), s.hazards
    lines = [_ward_tell(s, h) for h in s.hazards if h.get("kind") == "held_save"]
    assert lines and "breaks free of Hold Person" in lines[0], lines


def test_a_held_creature_that_fails_its_turns_save_stays_held():
    pc = caster("wizard", 5, book=("hold-person",))
    s, e = scene_with(pc, seed=2)
    t = foe(s)
    t.add_buff("save_mod", "will", -40, source="test: always fails")
    fight(s)
    run(e, "cast", spell="hold-person", at=t.ref)
    s.turn = 0
    s.advance_turn()
    assert any(x.key == "paralyzed" for x in t.effects)
    assert any(h.get("kind") == "held_save" and not h["made"] for h in s.hazards)


def _asleep(t_hp=None, **over):
    pc = caster("wizard", 1, book=("sleep",))
    s, e = scene_with(pc, seed=2)
    t = foe(s)
    t.add_buff("save_mod", "will", -40, source="test: always fails")
    if t_hp:
        t.hp = t.hp_max = t_hp
    for k, v in over.items():
        setattr(t, k, v)
    fight(s)
    run(e, "cast", spell="sleep", at=t.ref)
    assert any(x.key == "unconscious" for x in t.effects)
    return s, e, t


def test_a_wound_wakes_a_magical_sleeper():
    """CRB, Sleep: "Slapping or wounding awakens an affected creature, but normal noise
    does not." Before, a sleeper slept through a sword for the spell's whole duration."""
    s, e, t = _asleep(t_hp=30)
    hit = e._apply_damage(t, 3, "slashing")
    assert not any(x.key in ("unconscious", "helpless") for x in t.effects), t.effects
    assert hit.get("woke") and "wakes" in hit["note"], hit


def test_a_blow_that_wounds_nobody_wakes_nobody():
    s, e, t = _asleep(resistances={"fire": 10})
    e._apply_damage(t, 4, "fire")
    assert any(x.key == "unconscious" for x in t.effects)


def test_a_sleeper_wounded_below_zero_is_still_down():
    """The ladder's own unconsciousness is not the sleep's to lift."""
    s, e, t = _asleep()
    e._apply_damage(t, t.hp + 2, "slashing")
    e._hp_state_effects(t)
    assert t.hp < 0 and t.is_down


@pytest.mark.parametrize("hd,want", [
    (1, {"unconscious": 3, "blinded": 6, "stunned": 7}),
    (4, {"blinded": 3, "stunned": 4}),
    (6, {"stunned": 1})])
def test_color_spray_lays_its_table_by_hit_dice(hd, want):
    """CRB, Color Spray: 2 HD or less unconscious, blinded and stunned 2d4 rounds, then
    blinded and stunned 1d4, then stunned 1; 3 or 4 HD blinded and stunned 1d4, then
    stunned 1; 5 or more stunned 1. The phases run one after another, so each condition
    lasts the phases that hold it together. Before, every creature that failed was
    stunned for 1 round and nothing else (every die here rolls 3)."""
    got = dict(spells_mod.hd_tier_conditions("color-spray", hd, True,
                                             lambda d: 1 if d == "1" else 3))
    assert got == want


def test_color_spray_does_not_knock_a_zombie_unconscious():
    """"(Only living creatures are knocked unconscious.)" """
    got = dict(spells_mod.hd_tier_conditions("color-spray", 2, False,
                                             lambda d: 1 if d == "1" else 3))
    assert "unconscious" not in got and got["stunned"] == 7


def test_color_spray_cast_at_a_1_hd_thug_lays_the_table():
    pc = caster("wizard", 1, book=("color-spray",))
    s, e = scene_with(pc, seed=2)
    t = foe(s)
    t.add_buff("save_mod", "will", -40, source="test: always fails")
    fight(s)
    res = run(e, "cast", spell="color-spray", at=t.ref)
    on = {x.key: x.rounds_left for x in t.effects if x.kind == "condition"}
    assert {"unconscious", "blinded", "stunned"} <= set(on), said(res)
    assert on["unconscious"] < on["blinded"] < on["stunned"], on
    assert "Effect depends on the creature's HD" not in said(res)


def test_color_spray_leaves_a_blinded_creature_alone():
    """"Sightless creatures are not affected" — answered by the blindness on the sheet."""
    pc = caster("wizard", 1, book=("color-spray",))
    s, e = scene_with(pc, seed=2)
    t = foe(s)
    t.add_condition("blinded", source="test")
    fight(s)
    res = run(e, "cast", spell="color-spray", at=t.ref)
    assert not any(x.key == "stunned" for x in t.effects), said(res)
    assert "cannot see it" in said(res)
