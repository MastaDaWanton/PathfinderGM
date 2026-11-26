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
           feats=(), ally=None, cls=None, level=None, bab=None):
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
