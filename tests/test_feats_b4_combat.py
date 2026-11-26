"""Feat loop batch 4, lane b4-combat: each feat's numbers measured through the engine.

Before this batch none of these 61 feats had a mechanics document (worklist 2026-11-26,
b4-combat.tsv): a Stunning Critical confirmed on a thug left it standing unstunned, a Far
Shot archer paid -2 a range increment like anyone, a Gang Up rogue three allies deep got
no flank. The tests roll the real attack and read the conditions it laid, the terms it
rolled with and the tells it said.
"""
from __future__ import annotations

import re

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

FOE = "the foe"


class _Faces(Dice):
    """Each roll whose label starts with a key lands on that key's face; the rest roll
    seeded."""

    def __init__(self, faces: dict | None = None):
        super().__init__(seed=20261126)
        self.faces = dict(faces or {})

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        for prefix, face in self.faces.items():
            if (label or "").startswith(prefix):
                if notation == "1d20":
                    return self.given(face, modifiers, label)
                m = re.fullmatch(r"(\d*)d(\d+)([+-]\d+)?", str(notation).strip())
                if m:
                    n = int(m.group(1) or 1)
                    face = max(n, min(face, n * int(m.group(2))))
                return self.given_total(face, notation, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _fight(pc_file="fixtures/pc-borin.json", foe="thug", faces=None, at=((6, 10), (7, 10)),
           feats=(), ally=None, cls=None, level=None, bab=None, second=None):
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc(pc_file)
    if cls:
        pc.char_class = cls
    if level:
        pc.level = level
    if bab is not None:
        pc.level = bab                       # Borin is a fighter: BAB is his level
    pc.feats = list(pc.feats) + list(feats)
    pc.weapons = list(pc.weapons) + ["sling"]
    pc.goods.update({"arrows": 40, "sling bullets": 40, "stool": 3})
    scene.add(pc)
    scene.add(instantiate(foe, scene=scene, name=FOE))
    engine = Engine(scene, _Faces(faces))
    engine._ensure_encounter("pc")
    scene.positions["pc"], scene.positions["c1"] = at
    sides = {"pc": ["pc"], "them": ["c1"]}
    for template, square in second or ():
        other = instantiate(template, scene=scene, name=f"the {template} {len(sides['them'])}")
        scene.add(other)
        scene.positions[other.ref] = square
        sides["them"].append(other.ref)
    for i, (square, extra) in enumerate(ally or ()):
        friend = load_pc("fixtures/pc-kesst.json")
        friend.ref, friend.kind = f"ally{i}", "npc"
        friend.feats = list(friend.feats) + list(extra)
        scene.add(friend)
        scene.positions[friend.ref] = square
        sides["pc"].append(friend.ref)
    scene.sides = sides
    scene.resync_zones()
    for ref in scene.actors:
        scene.acted.add(ref) if isinstance(scene.acted, set) else scene.acted.append(ref)
    return scene, engine, scene.get("pc"), scene.get("c1")


def _settle(engine, res):
    while res.awaiting:
        ask = res.awaiting
        label = str(ask.get("label") or "")
        face = next((f for k, f in engine.dice.faces.items() if label.startswith(k)), 10)
        res = engine.resume(max(int(ask.get("min") or 1), min(face, int(ask.get("max") or 20))))
    return res


def _attack(engine, by="pc", target="c1", **params):
    actor = engine.scene.get(by)
    if params.get("weapon") and actor.is_pc and params["weapon"] != "improvised":
        actor.shield = "none"                # Borin's heavy shield leaves no hand for a bow
        actor.equipped = params["weapon"]
    return _settle(engine, engine.run(engine.validate([{
        "op": "attack", "actor": by, "target": target, "visibility": "hidden",
        "params": params}])))


def _named(roll: dict, name: str) -> int:
    return sum(int(m["value"]) for m in roll.get("modifiers") or ()
               if str(m.get("source") or m.get("label") or "").startswith(name))


def _rolls(res, prefix: str) -> list[dict]:
    return [r.as_dict() for o in res.outcomes for r in o.rolls
            if (r.label or "").startswith(prefix)]


def _tells(res) -> str:
    return " ".join(o.tell or "" for o in res.outcomes)


def _cond(actor, key):
    return next((e for e in actor.effects if e.kind == "condition" and e.key == key), None)


CRIT = {"Attack with": 20, "Confirm": 20, "Damage": 1}


# --- the critical feats -------------------------------------------------------------------

@pytest.mark.parametrize("feat,save,want,rounds", [
    ("Blinding Critical", 1, "blinded", None),
    ("Blinding Critical", 20, "dazzled", 3),
    ("Deafening Critical", 1, "deafened", None),
    ("Deafening Critical", 20, "deafened", 1),
    ("Exhausting Critical", 20, "exhausted", None),
    ("Tiring Critical", 20, "fatigued", None),
    ("Sickening Critical", 20, "sickened", 10),
    ("Staggering Critical", 1, "staggered", 4),
    ("Staggering Critical", 20, "staggered", 1),
    ("Stunning Critical", 1, "stunned", 3),
    ("Stunning Critical", 20, "staggered", 3),
])
def test_a_critical_feat_lays_its_condition_on_a_confirmed_critical(feat, save, want, rounds):
    """CRB critical feats: before this batch a confirmed critical by a Stunning Critical
    fighter left the thug standing with no condition at all. Fortitude DC 10 + BAB."""
    faces = dict(CRIT, **{"Fortitude save": save, f"{feat} (rounds)": 3})
    scene, engine, pc, thug = _fight(feats=[feat], faces=faces, bab=15)
    thug.hp = thug.hp_max = 400
    res = _attack(engine)
    got = _cond(thug, want)
    assert got is not None, _tells(res)
    assert got.rounds_left == rounds
    assert feat in _tells(res)


def test_only_one_critical_feat_rides_a_critical_without_critical_mastery():
    """"You can only apply the effects of one critical feat to a given critical hit unless
    you possess Critical Mastery": the first on the sheet."""
    faces = dict(CRIT, **{"Fortitude save": 1})
    scene, engine, pc, thug = _fight(feats=["Sickening Critical", "Tiring Critical"],
                                     faces=faces, bab=15)
    thug.hp = thug.hp_max = 400
    _attack(engine)
    assert _cond(thug, "sickened") is not None and _cond(thug, "fatigued") is None


def test_sickening_and_staggering_criticals_add_to_the_duration():
    """"The effects of this feat do not stack. Additional hits instead add to the
    duration": two criticals, 20 rounds of sickened, one condition."""
    scene, engine, pc, thug = _fight(feats=["Sickening Critical"], faces=CRIT, bab=15)
    thug.hp = thug.hp_max = 400
    _attack(engine)
    _attack(engine)
    sick = [e for e in thug.effects if e.key == "sickened"]
    assert len(sick) == 1 and sick[0].rounds_left == 20


def test_tiring_does_nothing_more_to_the_fatigued_and_exhausting_steps_it_up():
    scene, engine, pc, thug = _fight(feats=["Tiring Critical"], faces=CRIT, bab=15)
    thug.hp = thug.hp_max = 400
    thug.add_condition("fatigued")
    res = _attack(engine)
    assert "adds nothing" in _tells(res)
    scene, engine, pc, thug = _fight(feats=["Exhausting Critical"], faces=CRIT, bab=15)
    thug.hp = thug.hp_max = 400
    thug.add_condition("fatigued")
    _attack(engine)
    assert _cond(thug, "exhausted") is not None and _cond(thug, "fatigued") is None


def test_a_creature_immune_to_stunning_is_not_stunned_by_stunning_critical():
    scene, engine, pc, skel = _fight(feats=["Stunning Critical"], foe="human-skeleton",
                                     faces=dict(CRIT, **{"Fortitude save": 1}), bab=17)
    skel.hp = skel.hp_max = 400
    res = _attack(engine)
    assert _cond(skel, "stunned") is None
    assert "immune" in _tells(res)


def test_flaying_critical_strips_natural_armour_one_a_critical_and_no_lower_than_zero():
    """Flaying Critical (Dragonslayer's Handbook): -1 natural armour a critical, cumulative,
    never below 0, for the encounter; the fight's end takes it away."""
    scene, engine, pc, foe = _fight(feats=["Flaying Critical"], foe="ogre", faces=CRIT,
                                    bab=11)
    foe.hp = foe.hp_max = 900
    natural = sum(m.value for m in foe.ac_modifiers() if m.type == "natural armour")
    assert natural > 0
    before = foe.ac()
    for _ in range(natural + 2):
        _attack(engine)
    assert foe.ac() == before - natural
    scene.end_encounter()
    assert foe.ac() == before


# --- range, cover, concealment ------------------------------------------------------------

def _shot(feats=(), gap=26, weapon="shortbow", **params):
    scene, engine, pc, thug = _fight(feats=feats, faces={"Attack with": 10, "Damage": 1},
                                     at=((2, 10), (2 + gap, 10)))
    thug.hp = thug.hp_max = 400
    res = _attack(engine, weapon=weapon, **params)
    return _rolls(res, "Attack with")[0]


def test_far_shot_halves_the_range_penalty():
    """Far Shot (CRB): -1 per full range increment, not -2. A shortbow (60 ft) at 130 ft
    is two increments past the first: -4 for anyone, -2 with the feat."""
    assert _named(_shot(), "range") == -4
    assert _named(_shot(["Far Shot"]), "range") == -2


def test_distance_thrower_takes_two_off_a_thrown_weapon_s_range_penalty():
    """Distance Thrower (UC): a dagger (10 ft) thrown 25 ft is -4; with the feat -2, and a
    bow is untouched."""
    assert _named(_shot(gap=5, weapon="dagger", thrown=True), "range") == -4
    assert _named(_shot(["Distance Thrower"], gap=5, weapon="dagger", thrown=True),
                  "range") == -2
    assert _named(_shot(["Distance Thrower"]), "range") == -4


def _blurred(actor, pct=20):
    from rules.activeeffect import ActiveEffect

    actor.apply_effect(ActiveEffect(name="blur", kind="buff", source="blur",
                                    modifiers=[{"kind": "concealment", "target": "miss_chance",
                                                "amount": pct, "bonus_type": "untyped"}]))


def test_improved_precise_shot_ignores_partial_concealment_and_soft_cover():
    """Improved Precise Shot (CRB): no miss chance short of total concealment, no AC from
    anything short of total cover. Measured: a blurred thug at 20% cost a shot rolled 1 on
    the percentile; with the feat no percentile is rolled."""
    for feats, rolled in (((), True), (["Improved Precise Shot"], False)):
        scene, engine, pc, thug = _fight(feats=feats, at=((2, 10), (8, 10)),
                                         faces={"Attack with": 15, "miss chance": 1,
                                                "Damage": 1})
        thug.hp = thug.hp_max = 400
        _blurred(thug)
        res = _attack(engine, weapon="shortbow")
        assert bool(_rolls(res, "miss chance")) is rolled
    # Soft cover: a body in the line gives +4 AC, unless the shooter has the feat.
    for feats, cover in (((), True), (["Improved Precise Shot"], False)):
        scene, engine, pc, thug = _fight(feats=feats, at=((2, 10), (8, 10)),
                                         ally=[((5, 10), ())], faces={"Attack with": 10})
        res = _attack(engine, weapon="shortbow")
        assert ("cover" in _tells(res)) is cover, _tells(res)


def test_elven_accuracy_rerolls_a_bow_s_miss_chance_once():
    """Elven Accuracy (APG): a longbow or shortbow that misses for concealment rerolls the
    percentile once; a thrown dagger does not."""
    scene, engine, pc, thug = _fight(feats=["Elven Accuracy"], at=((2, 10), (8, 10)),
                                     faces={"Attack with": 15, "miss chance (blur), rerolled": 90,
                                            "miss chance": 1, "Damage": 1})
    thug.hp = thug.hp_max = 400
    _blurred(thug)
    res = _attack(engine, weapon="shortbow")
    assert len(_rolls(res, "miss chance")) == 2
    assert any(e.get("kind") == "damage" for o in res.outcomes for e in o.effects) \
        or "finds nothing" not in _tells(res)


def test_halfling_slinger_is_plus_one_racial_with_a_sling_only():
    roll = _shot(["Halfling Slinger"], gap=4, weapon="sling")
    assert _named(roll, "Halfling Slinger") == 1
    assert _named(_shot(["Halfling Slinger"], gap=4), "Halfling Slinger") == 0


def test_catch_off_guard_and_throw_anything_waive_the_improvised_penalty():
    """CRB: an improvised weapon is -4 (nonproficient). Catch Off-Guard waives it in melee
    and makes an unarmed foe flat-footed; Throw Anything waives it thrown."""
    def swing(feats, **params):
        scene, engine, pc, thug = _fight(feats=feats, faces={"Attack with": 10, "Damage": 1},
                                         at=((6, 10), (7, 10) if not params.get("thrown")
                                             else (9, 10)))
        thug.hp = thug.hp_max = 400
        return _attack(engine, weapon="improvised", item="stool", **params)
    plain = swing([])
    roll = _rolls(plain, "Attack with")
    assert roll and _named(roll[0], "not proficient") == -4, _tells(plain)
    caught = swing(["Catch Off-Guard"])
    assert _named(_rolls(caught, "Attack with")[0], "not proficient") == 0
    assert _named(_rolls(swing(["Catch Off-Guard"], thrown=True), "Attack with")[0],
                  "not proficient") == -4                    # melee only
    thrown = swing(["Throw Anything"], thrown=True)
    assert _named(_rolls(thrown, "Attack with")[0], "not proficient") == 0


def test_catch_off_guard_leaves_an_unarmed_foe_flat_footed():
    """"Unarmed opponents are flat-footed against any attacks you make with an improvised
    melee weapon": Kesst with empty hands loses her Dex against Borin's stool; armed, not."""
    from rules import strike_feats

    scene, engine, pc, thug = _fight(feats=["Catch Off-Guard"], ally=[((5, 10), ())])
    kesst = scene.get("ally0")
    stool = pc.weapon("improvised")
    kesst.equipped = ""
    assert strike_feats.caught_off_guard(pc, kesst, "improvised", stool)
    kesst.equipped = "rapier"
    assert not strike_feats.caught_off_guard(pc, kesst, "improvised", stool)
    assert not strike_feats.caught_off_guard(pc, thug, "improvised", stool)   # club in hand
    pc.feats = [f for f in pc.feats if f != "Catch Off-Guard"]
    kesst.equipped = ""
    assert not strike_feats.caught_off_guard(pc, kesst, "improvised", stool)


def test_throw_anything_is_plus_one_circumstance_on_a_thrown_splash_weapon():
    scene, engine, pc, thug = _fight(feats=["Throw Anything"])
    assert sum(m.value for m in pc.splash_attack_modifiers(thug)
               if m.source.startswith("Throw Anything")) == 1
    assert _named(_rolls(_attack(engine), "Attack with")[0], "Throw Anything") == 0


# --- flanking by feat, the lone fighter, the chain's guard ------------------------------

def _flanking(res) -> int:
    return _named(_rolls(res, "Attack with")[0], "flanking")


def test_gang_up_flanks_when_two_allies_threaten_the_foe_wherever_the_bearer_stands():
    """Gang Up (APG): two allies threatening the foe flank it for the bearer, "regardless
    of your actual positioning". Borin at the thug's west side, the allies north and
    south: no flank by the map, a flank by the feat; one ally is not enough."""
    allies = [((7, 9), ()), ((7, 11), ())]
    for feats, want in (((), 0), (["Gang Up"], 2)):
        scene, engine, pc, thug = _fight(feats=feats, ally=allies, faces={"Attack with": 10})
        assert _flanking(_attack(engine)) == want
    scene, engine, pc, thug = _fight(feats=["Gang Up"], ally=allies[:1],
                                     faces={"Attack with": 10})
    assert _flanking(_attack(engine)) == 0


def test_overwhelm_flanks_a_foe_two_sizes_larger_with_an_ally_who_holds_it():
    """Overwhelm (Dragonslayer's Handbook): an ally with the feat threatening, the foe two
    or more sizes larger than either of you."""
    for size, ally_feats, want in (("huge", ["Overwhelm"], 2), ("large", ["Overwhelm"], 0),
                                   ("huge", [], 0)):
        scene, engine, pc, thug = _fight(feats=["Overwhelm"], ally=[((7, 9), ally_feats)],
                                         faces={"Attack with": 10})
        thug.size = size
        assert _flanking(_attack(engine)) == want, size


def test_desperate_battler_is_plus_one_morale_with_no_ally_within_ten_feet():
    """Desperate Battler (ISWG): +1 morale on melee attack and damage with no ally within
    10 feet and no aid another; Kesst 5 feet away takes it off."""
    scene, engine, pc, thug = _fight(feats=["Desperate Battler"],
                                     faces={"Attack with": 15, "Damage": 1})
    thug.hp = thug.hp_max = 400
    res = _attack(engine)
    assert _named(_rolls(res, "Attack with")[0], "Desperate Battler") == 1
    assert _named(_rolls(res, "Damage")[0], "Desperate Battler") == 1
    scene, engine, pc, thug = _fight(feats=["Desperate Battler"], ally=[((6, 11), ())],
                                     faces={"Attack with": 15})
    assert _named(_rolls(_attack(engine), "Attack with")[0], "Desperate Battler") == 0
    scene, engine, pc, thug = _fight(feats=["Desperate Battler"], ally=[((6, 14), ())],
                                     faces={"Attack with": 15})
    assert _named(_rolls(_attack(engine), "Attack with")[0], "Desperate Battler") == 1


def test_cornugon_shield_is_a_shield_bonus_with_a_spiked_chain():
    """Cornugon Shield: +1 shield bonus to AC wielding a spiked chain, +2 fighting
    defensively or in total defense; nothing with a longsword."""
    from rules.activeeffect import ActiveEffect
    from rules import states

    scene, engine, pc, thug = _fight(feats=["Cornugon Shield"])
    pc.shield = "none"
    pc.weapons = list(pc.weapons) + ["spiked chain"]
    base = pc.ac()
    pc.equipped = "spiked chain"
    assert pc.ac() == base + 1
    pc.apply_effect(ActiveEffect(name="fighting defensively", kind="buff",
                                 key="fighting defensively",
                                 tags=states.tags_for("fighting defensively")))
    with_stance = pc.ac()
    pc.equipped = "longsword"
    assert with_stance - pc.ac() == 2


def test_improved_cleaving_finish_carries_on_more_than_once_a_round():
    """Improved Cleaving Finish (UC): "any number of times per round". Cleaving Finish
    alone swings once a round: two dropped foes, one carry-on."""
    for feats, carries in ((["Cleave", "Cleaving Finish"], 1),
                           (["Cleave", "Cleaving Finish", "Improved Cleaving Finish"], 2)):
        scene, engine, pc, thug = _fight(feats=feats, second=[("thug", (7, 11)),
                                                              ("thug", (6, 11))],
                                         faces={"Attack with": 18, "Damage": 30})
        thug.hp = 1
        refs = [r for r in scene.sides["them"] if r != "c1"]
        scene.get(refs[0]).hp = 1
        scene.get(refs[1]).hp = scene.get(refs[1]).hp_max = 400
        res = _attack(engine)
        assert _tells(res).count("(Cleaving Finish)") == carries, _tells(res)


# --- damage reduction, threat range, the guard against a group ---------------------------

def test_greater_penetrating_strike_passes_ten_of_a_typed_dr_and_five_of_dr_dash():
    """Greater Penetrating Strike (CRB): with a Weapon Focus weapon, 10 points of DR pass,
    5 of a DR without a type: DR 12/silver leaves 2, DR 12/- leaves 7."""
    from rules.activeeffect import ActiveEffect
    from rules import strike_feats

    scene, engine, pc, thug = _fight(feats=["Greater Penetrating Strike"])
    traits = strike_feats.dr_traits(pc, thug, "longsword")
    for bypass, left in (("silver", 2), ("", 7)):
        thug.effects = [e for e in thug.effects if e.kind != "damage_reduction"]
        thug.apply_effect(ActiveEffect(name="DR", kind="damage_reduction",
                                       payload={"amount": 12, "bypass": bypass}))
        assert thug.damage_reduction("slashing", traits=traits).amount == left
    assert strike_feats.dr_traits(pc, thug, "dagger") == ()       # no Weapon Focus in it


def test_slayers_knack_doubles_the_threat_against_the_picked_enemy_only():
    """Slayer's Knack (UC): against the picked favoured enemy type the threat range is
    doubled; a weapon already widened (Improved Critical) is not widened again."""
    from rules import strike_feats

    scene, engine, pc, skel = _fight(feats=["Slayer's Knack (undead)"], foe="human-skeleton")
    sword = pc.weapon("longsword")
    assert strike_feats.threat_from(pc, skel, sword) == 17
    ogre = instantiate("ogre", scene=scene)
    assert strike_feats.threat_from(pc, ogre, sword) == 19
    pc.feats.append("Improved Critical (longsword)")
    assert strike_feats.threat_from(pc, skel, pc.weapon("longsword")) == 17


def test_defensive_weapon_training_is_dodge_against_the_picked_group():
    """Defensive Weapon Training (UC): +2 dodge AC against a weapon of the group, +3 with
    weapon training in it; nothing flat-footed, nothing against another group."""
    from rules import strike_feats

    scene, engine, pc, thug = _fight(feats=["Defensive Weapon Training (heavy blades)"])
    sword = pc.weapon("longsword")
    got = strike_feats.guard_against(pc, thug, sword, "longsword", False)
    assert [m.value for m in got] == [2] and got[0].type == "dodge"
    assert strike_feats.guard_against(pc, thug, sword, "longsword", True) == []
    assert strike_feats.guard_against(pc, thug, pc.weapon("dagger"), "dagger", False) == []
    pc.level = 5
    pc.class_choices = {"weapon training": ["heavy blades"]}
    assert [m.value for m in strike_feats.guard_against(pc, thug, sword, "longsword",
                                                        False)] == [3]


def test_martial_versatility_carries_weapon_focus_across_the_group():
    """Martial Versatility (ARG): the picked feat works with every weapon of the group -
    Borin's Weapon Focus (longsword) on a scimitar, not on a dagger. Martial Mastery does
    it for every such feat."""
    for feats, want in (((), 0), (["Martial Versatility (Weapon Focus)"], 1),
                        (["Martial Mastery"], 1)):
        scene, engine, pc, thug = _fight(feats=feats)
        pc.weapons = list(pc.weapons) + ["scimitar"]
        mods = pc.attack_modifiers("scimitar", 0, defender=thug)
        assert sum(m.value for m in mods if m.source.startswith("Weapon Focus")) == want
        mods = pc.attack_modifiers("dagger", 0, defender=thug)
        assert sum(m.value for m in mods if m.source.startswith("Weapon Focus")) == 0


def test_spear_dancer_dazzles_on_a_hit_with_a_focused_two_handed_reach_weapon():
    scene, engine, pc, thug = _fight(feats=["Spear Dancer", "Weapon Focus (longspear)"],
                                     at=((6, 10), (8, 10)),
                                     faces={"Attack with": 18, "Damage": 1})
    thug.hp = thug.hp_max = 400
    pc.weapons = list(pc.weapons) + ["longspear"]
    res = _attack(engine, weapon="longspear")
    assert _cond(thug, "dazzled") is not None and "Spear Dancer" in _tells(res)
    scene, engine, pc, thug = _fight(feats=["Spear Dancer"], faces={"Attack with": 18})
    thug.hp = thug.hp_max = 400
    _attack(engine)
    assert _cond(thug, "dazzled") is None


def test_opening_volley_gives_plus_four_on_the_next_melee_attack_and_is_spent():
    """Opening Volley (UC): a ranged hit that deals damage gives +4 circumstance on the
    next melee attack roll against that foe; the swing spends it."""
    scene, engine, pc, thug = _fight(feats=["Opening Volley"], at=((6, 10), (7, 10)),
                                     faces={"Attack with": 18, "Damage": 2})
    thug.hp = thug.hp_max = 400
    _attack(engine, weapon="shortbow")
    first = _rolls(_attack(engine, weapon="longsword"), "Attack with")[0]
    assert _named(first, "Opening Volley") == 4
    second = _rolls(_attack(engine, weapon="longsword"), "Attack with")[0]
    assert _named(second, "Opening Volley") == 0


# --- the declared one-blow options --------------------------------------------------------

def _owed(res, by):
    return [e for o in res.outcomes for e in o.effects
            if e.get("kind") == "owed_swing" and e.get("ref") == by]


def test_death_or_glory_is_plus_four_and_the_large_foe_answers_with_the_same():
    """Death or Glory (UC): against a Large or larger creature one melee attack as a
    full-round action at +4 attack, damage and confirmation (+1 at BAB 11); then the foe
    may spend an immediate action on one melee attack back with the same bonuses."""
    scene, engine, pc, ogre = _fight(feats=["Death or Glory"], foe="ogre", level=11,
                                     at=((6, 10), (7, 10)),
                                     faces={"Attack with": 15, "Damage": 1})
    ogre.hp = ogre.hp_max = 900
    res = _attack(engine, death_or_glory=True)
    roll = _rolls(res, "Attack with Death") or _rolls(res, "Attack with")
    assert _named(roll[0], "Death or Glory") == 5
    assert _named(_rolls(res, "Damage")[0], "Death or Glory") == 5
    swings = [o for o in res.outcomes if o.op == "attack"]
    assert any(o.actor == "c1" for o in swings), _tells(res)
    back = next(o for o in swings if o.actor == "c1")
    assert _named(back.rolls[0].as_dict(), "Death or Glory") == 5
    assert "Death or Glory" in _tells(res)


def test_death_or_glory_is_refused_against_a_medium_foe_and_in_a_full_attack():
    from rules.intents import IntentError

    scene, engine, pc, thug = _fight(feats=["Death or Glory"], level=6)
    with pytest.raises(IntentError, match="Large or larger"):
        engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                          "params": {"death_or_glory": True}}])
    scene, engine, pc, ogre = _fight(feats=["Death or Glory"], foe="ogre", level=6)
    with pytest.raises(IntentError, match="full-round"):
        engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                          "params": {"death_or_glory": True, "full_attack": True}}])


def test_deadly_finish_kills_a_foe_left_below_zero_who_fails_fortitude():
    """Deadly Finish (UC): a melee hit leaving the foe at -1 or fewer: Fortitude DC 15 +
    the damage or die. Before this feat the thug lay dying; now it is dead."""
    scene, engine, pc, thug = _fight(feats=["Deadly Finish"], level=11,
                                     faces={"Attack with": 18, "Damage": 20,
                                            "Fortitude save": 2})
    thug.hp = 5
    res = _attack(engine, deadly_finish=True)
    assert thug.is_dead and "Deadly Finish" in _tells(res)
    scene, engine, pc, thug = _fight(feats=["Deadly Finish"], level=11,
                                     faces={"Attack with": 18, "Damage": 20})
    thug.hp = 5
    _attack(engine)                                     # not declared: it lies dying
    assert not thug.is_dead


def test_punch_through_opens_the_foe_s_typed_dr_to_the_bearer_s_allies():
    """Punch Through (Demon Hunter's Handbook): the bearer's damaging hit lets allies who
    hold the feat pass 5 of the foe's typed DR for a round; not the bearer himself."""
    from rules import strike_feats

    scene, engine, pc, thug = _fight(feats=["Punch Through"], level=6,
                                     ally=[((7, 9), ["Punch Through"])],
                                     faces={"Attack with": 18, "Damage": 3})
    thug.hp = thug.hp_max = 400
    from rules.sheet import situated

    kesst = scene.get("ally0")
    with situated(scene):
        assert "ignores_typed_dr:5" not in strike_feats.dr_traits(kesst, thug, "rapier")
    res = _attack(engine, punch_through=True)
    assert "Punch Through" in _tells(res)
    with situated(scene):
        assert "ignores_typed_dr:5" in strike_feats.dr_traits(kesst, thug, "rapier")
        assert "ignores_typed_dr:5" not in strike_feats.dr_traits(pc, thug, "longsword")


def test_reckless_aim_trades_one_ac_for_plus_two_and_a_natural_one_hits_a_neighbour():
    """Reckless Aim (Blood of Fiends): at a foe engaged in melee, +2 competence on the
    shot and -1 AC; a natural 1 automatically hits a random adjacent creature that
    threatens the target - here Kesst, fighting it."""
    scene, engine, pc, thug = _fight(feats=["Point-Blank Shot", "Precise Shot", "Reckless Aim"], at=((2, 10), (8, 10)),
                                     ally=[((8, 11), ())],
                                     faces={"Attack with": 15, "Damage": 3})
    thug.hp = thug.hp_max = 400
    pc.shield = "none"
    ac = pc.ac()
    res = _attack(engine, weapon="shortbow", reckless_aim=True)
    assert _named(_rolls(res, "Attack with")[0], "Reckless Aim") == 2
    assert pc.ac() == ac - 1
    scene, engine, pc, thug = _fight(feats=["Point-Blank Shot", "Precise Shot", "Reckless Aim"], at=((2, 10), (8, 10)),
                                     ally=[((8, 11), ())],
                                     faces={"Attack with": 1, "Damage": 3})
    kesst = scene.get("ally0")
    before = kesst.hp
    res = _attack(engine, weapon="shortbow", reckless_aim=True)
    assert kesst.hp == before - 3 and "Reckless Aim, natural 1" in _tells(res)


def test_reckless_aim_needs_a_foe_engaged_in_melee():
    from rules.intents import IntentError

    scene, engine, pc, thug = _fight(feats=["Point-Blank Shot", "Precise Shot", "Reckless Aim"], at=((2, 10), (8, 10)))
    with pytest.raises(IntentError, match="engaged in melee"):
        engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                          "params": {"weapon": "shortbow", "reckless_aim": True}}])


def test_butterfly_s_sting_gives_the_critical_to_the_next_ally_s_melee_hit():
    """Butterfly's Sting (Faiths of Purity): the bearer forgoes a confirmed critical (the
    blow deals normal damage) and the next ally's melee hit on the creature is a critical
    without a confirmation roll."""
    scene, engine, pc, thug = _fight(feats=["Combat Expertise", "Butterfly's Sting"],
                                     ally=[((7, 9), ())],
                                     faces={"Attack with": 20, "Confirm": 20, "Damage": 4})
    pc.abilities["int"] = 13
    thug.hp = thug.hp_max = 400
    res = _attack(engine, butterfly_sting=True)
    assert "Butterfly's Sting" in _tells(res)
    assert not any("critical" in str(b.get("critical")) and b.get("critical")
                   for o in res.outcomes for b in (o.blows or []))
    engine.dice.faces = {"Attack with": 15, "Damage": 4}
    res = _attack(engine, by="ally0", target="c1")
    assert "a critical (Butterfly's Sting)" in _tells(res)
    assert not _rolls(res, "Confirm")


def test_two_handed_thrower_adds_half_again_strength_to_a_two_handed_throw():
    """Two-Handed Thrower (UC): a one-handed weapon thrown with both hands deals 1-1/2
    times the Strength bonus: Borin's +3 becomes +4 on a thrown dagger."""
    scene, engine, pc, thug = _fight(feats=["Two-Handed Thrower"], at=((6, 10), (8, 10)),
                                     faces={"Attack with": 18, "Damage": 2})
    thug.hp = thug.hp_max = 400
    res = _attack(engine, weapon="dagger", thrown=True, two_handed_throw=True)
    assert _named(_rolls(res, "Damage")[0], "Two-Handed Thrower") == 1, _tells(res)


def test_two_handed_throw_needs_the_hands_free():
    from rules.intents import IntentError

    scene, engine, pc, thug = _fight(feats=["Two-Handed Thrower"], at=((6, 10), (8, 10)))
    with pytest.raises(IntentError, match="both hands"):
        engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                          "params": {"weapon": "dagger", "thrown": True,
                                     "two_handed_throw": True}}])     # heavy shield on


def test_hamatulatsu_pierces_and_a_piercing_critical_sickens_then_staggers():
    """Hamatulatsu (ISWG): the unarmed strike may pierce; a piercing critical leaves the
    foe sickened for a round, or staggered for a round if it is already sickened."""
    feats = ["Improved Unarmed Strike", "Weapon Focus (unarmed strike)", "Hamatulatsu"]
    scene, engine, pc, thug = _fight(feats=feats, faces=CRIT)
    thug.hp = thug.hp_max = 400
    res = _attack(engine, weapon="unarmed", hamatulatsu=True)
    assert any(e.get("type") == "piercing" for o in res.outcomes for e in o.effects
               if e.get("kind") == "damage")
    assert _cond(thug, "sickened").rounds_left == 1
    _attack(engine, weapon="unarmed", hamatulatsu=True)
    assert _cond(thug, "staggered") is not None


def test_cockatrice_strike_petrifies_a_stunned_foe_on_a_failed_fortitude():
    """Cockatrice Strike (APG): one unarmed strike as a full-round action against a dazed,
    flat-footed, paralyzed, staggered, stunned or unconscious foe; a critical petrifies
    it unless it makes Fortitude DC 10 + half level + Wis."""
    feats = ["Improved Unarmed Strike", "Gorgon's Fist", "Medusa's Wrath",
             "Cockatrice Strike"]
    scene, engine, pc, thug = _fight(feats=feats, level=14,
                                     faces=dict(CRIT, **{"Fortitude save": 2}))
    thug.hp = thug.hp_max = 400
    thug.add_condition("stunned", rounds=2)
    res = _attack(engine, weapon="unarmed", cockatrice_strike=True)
    assert _cond(thug, "petrified") is not None, _tells(res)


def test_cockatrice_strike_is_refused_against_a_foe_on_guard():
    from rules.intents import IntentError

    feats = ["Improved Unarmed Strike", "Gorgon's Fist", "Medusa's Wrath",
             "Cockatrice Strike"]
    scene, engine, pc, thug = _fight(feats=feats, level=14)
    scene.acted.add("c1") if isinstance(scene.acted, set) else None
    engine._flat_footed = lambda d: False
    with pytest.raises(IntentError, match="stunned or unconscious"):
        engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                          "params": {"weapon": "unarmed", "cockatrice_strike": True}}])


# --- the monk's strike feats ------------------------------------------------------------

def _use(engine, name, to=None, actor="pc"):
    raw = {"op": "use_ability", "actor": actor, "because": "test",
           "params": {"ability": name}}
    if to:
        raw["params"]["to"] = to
    return _settle(engine, engine.run(engine.validate([raw]))).outcomes[-1]


def _monk(feats, level=8, **kw):
    scene, engine, pc, thug = _fight(feats=feats, cls="monk", level=level, **kw)
    pc.shield = "none"
    pc.equipped = ""
    thug.hp = thug.hp_max = 400
    return scene, engine, pc, thug


def test_elemental_fist_adds_a_d6_of_the_chosen_energy_once_a_round():
    """Elemental Fist (APG): declared before the roll, the unarmed hit adds 1d6 of acid,
    cold, electricity or fire; a monk has his level in uses a day, no more than once a
    round."""
    scene, engine, pc, thug = _monk(["Improved Unarmed Strike", "Elemental Fist"],
                                    faces={"Attack with": 18, "Damage": 2,
                                           "Elemental Fist": 4})
    used = _use(engine, "elemental fist (cold)")
    assert used.status == "resolved", used.tell
    assert pc.pool("elemental fist").current == 7
    again = _use(engine, "elemental fist (cold)")
    assert again.status != "resolved"                        # once a round
    res = _attack(engine, weapon="unarmed")
    cold = [e for o in res.outcomes for e in o.effects
            if e.get("kind") == "damage" and e.get("type") == "cold"]
    assert cold and cold[0]["amount"] == 4, _tells(res)


def test_perfect_strike_keeps_the_better_of_two_dice_and_the_twin_confirms_a_threat():
    """Perfect Strike (APG): two attack dice, the higher kept; a threat on one has the
    other for its confirmation - no third die. With a quarterstaff, not the fist."""
    scene, engine, pc, thug = _monk(["Improved Unarmed Strike", "Perfect Strike"],
                                    faces={"Attack with quarterstaff (Perfect": 20,
                                           "Attack with": 3, "Damage": 1})
    pc.weapons = list(pc.weapons) + ["quarterstaff"]
    pc.equipped = "quarterstaff"
    assert _use(engine, "perfect strike").status == "resolved"
    res = _attack(engine, weapon="quarterstaff")
    attack = _rolls(res, "Attack with")
    assert len(attack) == 2 and "Perfect Strike" in _tells(res)
    confirm = _rolls(res, "Confirm")
    assert len(confirm) == 1 and confirm[0]["natural"] == 3
    assert "hits" in _tells(res)


def test_disorienting_blow_confuses_and_each_blow_adds_a_round():
    """Disorienting Blow (Dragon Empires Primer): a Stunning Fist use that confuses for a
    round on a failed Fortitude save; another adds to the confusion's duration."""
    scene, engine, pc, thug = _monk(["Improved Unarmed Strike", "Stunning Fist",
                                     "Disorienting Blow"],
                                    level=12, faces={"Attack with": 18, "Damage": 1,
                                                     "Fortitude": 2})
    left = None
    for want in (1, 2):
        assert _use(engine, "disorienting blow", to="c1").status == "resolved"
        scene.swung = {}
        _attack(engine, weapon="unarmed")
        got = _cond(thug, "confused")
        assert got is not None and got.rounds_left == want
        left = pc.pool("stunning fist").current
    assert left == 12 - 2


def test_stunning_fist_adept_adds_one_to_the_dc_but_not_beside_mantis_style():
    """Stunning Fist Adept (Dragon Empires Primer): +1 to the Stunning Fist DC; "does not
    stack with feats that grant you bonuses to the DC ... such as Mantis Style"."""
    from rules.activeeffect import ActiveEffect

    scene, engine, pc, thug = _monk(["Improved Unarmed Strike", "Stunning Fist",
                                     "Stunning Fist Adept"])
    plain = sum(m.value for m in pc._buff_mods("combat_mod", "stunning-fist.dc"))
    assert plain == 1
    pc.feats.append("Mantis Style")
    pc.apply_effect(ActiveEffect(name="Mantis Style", kind="buff", key="mantis style",
                                 tags=("style.mantis-style",)))
    assert sum(m.value for m in pc._buff_mods("combat_mod", "stunning-fist.dc")) == 2


def test_cornugon_stun_carries_stunning_fist_through_a_monk_weapon():
    """Cornugon Stun (Cheliax): Stunning Fist with special monk weapons as well as the
    fist. A kama hit stuns; without the feat the charge waits for the fist."""
    for feats, stunned in ((["Improved Unarmed Strike", "Stunning Fist"], False),
                           (["Improved Unarmed Strike", "Stunning Fist", "Cornugon Stun"],
                            True)):
        scene, engine, pc, thug = _monk(feats, faces={"Attack with": 18, "Damage": 1,
                                                      "Fortitude": 2})
        pc.weapons = list(pc.weapons) + ["kama"]
        pc.equipped = "kama"
        assert _use(engine, "stunning fist", to="c1").status == "resolved"
        _attack(engine, weapon="kama")
        assert (_cond(thug, "stunned") is not None) is stunned


def test_bullseye_shot_is_plus_four_on_the_next_ranged_attack_and_spent_by_it():
    scene, engine, pc, thug = _fight(feats=["Point-Blank Shot", "Precise Shot",
                                            "Bullseye Shot"], level=5,
                                     at=((2, 10), (8, 10)), faces={"Attack with": 10})
    thug.hp = thug.hp_max = 400
    pc.shield = "none"
    pc.equipped = "shortbow"
    assert _use(engine, "bullseye shot").status == "resolved"
    first = _rolls(_attack(engine, weapon="shortbow"), "Attack with")[0]
    assert _named(first, "Bullseye Shot") == 4
    scene.swung = {}
    second = _rolls(_attack(engine, weapon="shortbow"), "Attack with")[0]
    assert _named(second, "Bullseye Shot") == 0


def test_stunning_pin_spends_a_swift_stunning_fist_on_the_foe_just_pinned():
    """Stunning Pin (UC): "Whenever you pin an opponent, you can spend a swift action to
    make a Stunning Fist attempt against that opponent." The pin, then Fortitude or
    stunned, a use of Stunning Fist gone."""
    from rules.engine import _held_by

    scene, engine, pc, thug = _monk(["Improved Unarmed Strike", "Improved Grapple",
                                     "Stunning Fist", "Stunning Pin"],
                                    faces={"Combat manoeuvre": 19, "grapple": 19,
                                           "Fortitude": 2}, at=((6, 10), (7, 10)))
    pc.add_condition("grappled", source="test")
    thug.add_condition("grappled", source="test")
    _held_by(thug, "grappled", "pc", grappler="pc")
    _held_by(pc, "grappled", "c1", grappler="pc")
    from rules import class_abilities as ca

    ca.ensure_pool(pc, ca.find(pc, "stunning fist")[0])
    before = pc.pool("stunning fist").current
    res = _attack(engine, manoeuvre="grapple", pin=True)
    assert thug.has_state("state.held.pinned"), _tells(res)
    assert _cond(thug, "stunned") is not None, _tells(res)
    assert pc.pool("stunning fist").current == before - 1
    assert "Stunning Pin" in _tells(res)


# --- shields, prone shooting, the teamwork shot ------------------------------------------

def test_shield_master_takes_no_two_weapon_penalty_with_the_shield_and_adds_its_plus():
    """Shield Master (CRB): no attack penalty with the shield while wielding another
    weapon, and the shield's enhancement bonus on the bash's attack and damage."""
    scene, engine, pc, thug = _fight(feats=["Improved Shield Bash", "Two-Weapon Fighting"])
    plain = sum(m.value for m in pc.attack_modifiers("shield", 0, hand="off",
                                                     off_light=False, defender=thug)
                if m.source.startswith("two-weapon"))
    assert plain < 0
    pc.feats.append("Shield Master")
    assert sum(m.value for m in pc.attack_modifiers("shield", 0, hand="off",
                                                    off_light=False, defender=thug)
               if m.source.startswith("two-weapon")) == 0
    main = pc.attack_modifiers("longsword", 0, hand="primary", off_light=False,
                               defender=thug)
    assert sum(m.value for m in main if m.source.startswith("two-weapon")) < 0


def test_shield_master_lays_a_magic_shield_s_plus_on_the_bash(monkeypatch):
    from rules import strike_feats

    scene, engine, pc, thug = _fight(feats=["Shield Master"])
    monkeypatch.setattr(strike_feats, "shield_enhancement",
                        lambda actor, rec: 3 if actor.has_state("shield.bash.master") else 0)
    row = pc.weapon("shield")
    assert row["bash_plus"] == 3 and "magic" in row["strikes_as"]


def test_a_prone_archer_is_refused_and_a_prone_slinger_may_sling():
    """CRB, Prone: "cannot use a ranged weapon (except for a crossbow)". Nothing refused a
    prone bow before this; Prone Slinger lets the sling through."""
    from rules.intents import IntentError

    scene, engine, pc, thug = _fight(at=((2, 10), (8, 10)))
    pc.shield = "none"
    pc.add_condition("prone")
    for weapon in ("shortbow", "sling"):
        with pytest.raises(IntentError, match="prone"):
            engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                              "params": {"weapon": weapon}}])
    pc.feats.append("Prone Slinger")
    engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                      "params": {"weapon": "sling"}}])
    pc.weapons = list(pc.weapons) + ["light crossbow"]
    pc.feats.remove("Prone Slinger")
    engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                      "params": {"weapon": "light crossbow"}}])


def test_prone_shooter_softens_prone_s_ac_both_ways():
    """Prone Shooter (UC): prone's -4 AC against melee becomes -2, its +4 against ranged
    becomes +6."""
    scene, engine, pc, thug = _fight(feats=["Prone Shooter"])
    standing_melee, standing_ranged = pc.ac("melee"), pc.ac("ranged")
    pc.add_condition("prone")
    assert pc.ac("melee") == standing_melee - 2
    assert pc.ac("ranged") == standing_ranged + 6


def test_target_of_opportunity_answers_an_ally_s_ranged_hit_with_a_shot():
    """Target of Opportunity (UC): an ally with the feat hits with a ranged attack a foe
    within 30 feet of you; your immediate action buys one ranged attack at it."""
    scene, engine, pc, thug = _fight(feats=["Point-Blank Shot", "Target of Opportunity"],
                                     at=((2, 10), (6, 10)), level=6,
                                     ally=[((3, 12), ["Point-Blank Shot",
                                                      "Target of Opportunity"])],
                                     faces={"Attack with": 18, "Damage": 1})
    thug.hp = thug.hp_max = 400
    kesst = scene.get("ally0")
    kesst.weapons = list(kesst.weapons) + ["shortbow"]
    kesst.equipped = "shortbow"
    kesst.goods["arrows"] = 20
    res = _attack(engine, weapon="shortbow")
    swings = [o for o in res.outcomes if o.op == "attack"]
    assert any(o.actor == "ally0" for o in swings), _tells(res)
    assert "Target of Opportunity" in _tells(res)
