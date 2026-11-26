"""Feat loop batch 3, lane b3-martial: each feat's numbers measured through the engine.

Before this batch none of these feats had a mechanics document: each was a name on the
sheet that changed no roll (worklist 2026-11-26, b3-martial.tsv, 51 feats). Many answer an
EVENT the roll context cannot carry — a critical confirmed on you (Gore Fiend, Survivor,
Resilient Brute), a foe felled (Thrill of the Kill, Raging Deathblow, Cleaving Finish) — so
they are `triggers` and tags read at the attack loop's moments (rules/feat_events.py). The
tests roll the real attack and read the terms it rolled with, the pools it moved and the
swings it queued.
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
                m = re.fullmatch(r"(\d*)d(\d+)", str(notation).strip())
                if m:
                    n = int(m.group(1) or 1)
                    face = max(n, min(face, n * int(m.group(2))))
                return self.given_total(face, notation, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _fight(pc_file="fixtures/pc-borin.json", foe="thug", faces=None, at=((6, 10), (7, 10)),
           feats=(), ally=None, cls=None, level=None, second=None):
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc(pc_file)
    if cls:
        pc.char_class = cls
    if level:
        pc.level = level
    pc.feats = list(pc.feats) + list(feats)
    scene.add(pc)
    scene.add(instantiate(foe, scene=scene, name=FOE))
    if second:
        scene.add(instantiate(second[0], scene=scene, name="the second"))
    engine = Engine(scene, _Faces(faces))
    engine._ensure_encounter("pc")
    scene.positions["pc"], scene.positions["c1"] = at
    if second:
        scene.positions["c2"] = second[1]
        scene.sides = {"pc": ["pc"], "them": ["c1", "c2"]}
    if ally is not None:
        friend = load_pc("fixtures/pc-kesst.json")
        friend.ref, friend.kind = "ally", "npc"
        friend.feats = list(friend.feats) + list(ally[1])
        scene.add(friend)
        scene.positions["ally"] = ally[0]
        scene.sides = {"pc": ["pc", "ally"], "them": ["c1"] + (["c2"] if second else [])}
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
    return _settle(engine, engine.run(engine.validate([{
        "op": "attack", "actor": by, "target": target, "visibility": "hidden",
        "params": params}])))


def _named(roll: dict, name: str) -> int:
    return sum(int(m["value"]) for m in roll.get("modifiers") or ()
               if str(m.get("source") or m.get("label") or "").startswith(name))


def _rolls(res, prefix: str) -> list[dict]:
    return [r.as_dict() for o in res.outcomes for r in o.rolls
            if (r.label or "").startswith(prefix)]


def _effects(res, kind: str) -> list[dict]:
    return [e for o in res.outcomes for e in o.effects if e.get("kind") == kind]


def _tells(res) -> str:
    return " ".join(o.tell or "" for o in res.outcomes)


def _rage(pc, spent: int = 3):
    """A raging barbarian with `spent` rounds already gone from the pool."""
    from rules import class_abilities as ca, resources

    for spec in ca.pool_specs(pc) if hasattr(ca, "pool_specs") else ():
        resources.define(pc, spec)
    from rules import classes

    for p in classes.get("barbarian").get("pools") or ():
        resources.define(pc, p)
    pc.pools["rage"].current -= spent
    from rules.activeeffect import ActiveEffect

    pc.apply_effect(ActiveEffect(name="rage", kind="buff", key="rage", source="test",
                                 tags=("buff.stance.rage",)))


# --- precision: Shadow Strike, Bludgeoner, Flanking Foil, Knockout Artist, Precise Strike --

def test_shadow_strike_lets_sneak_dice_through_partial_concealment_only(monkeypatch):
    """Shadow Strike (APG): "precision damage ... against targets with concealment (but not
    total concealment)". Measured before: a 20% blur refused Kesst's sneak dice with or
    without the feat."""
    for feats, chance, want in (([], 20, False), (["Shadow Strike"], 20, True),
                                (["Shadow Strike"], 50, False)):
        scene, engine, pc, thug = _fight("fixtures/pc-kesst.json", feats=feats)
        monkeypatch.setattr(engine, "_concealment_of", lambda a, d, c=chance: (c, "blur"))
        dice, _why = engine._sneak_for(pc, thug, pc.weapon("rapier"), flat_footed=True)
        assert bool(dice) is want, (feats, chance)


def test_bludgeoner_pulls_a_club_without_the_minus_four_and_keeps_the_sneak_dice():
    """Bludgeoner (UC): no -4 for a lethal bludgeoning weapon dealing nonlethal, and (its
    Special) a rogue may sneak attack with it. A sword pulled is still -4."""
    for feats, want in (([], 0), (["Bludgeoner"], 1)):
        scene, engine, pc, thug = _fight("fixtures/pc-kesst.json", feats=feats,
                                         faces={"Attack with": 18, "Damage": 1})
        pc.weapons = list(pc.weapons) + ["club"]
        thug.hp = thug.hp_max = 200
        thug.add_condition("flat-footed", 1, source="test")
        assert bool(pc.lethality_swap("club", "nonlethal")) is not bool(want)
        assert pc.lethality_swap("rapier", "nonlethal")
        res = _attack(engine, weapon="club", lethality="nonlethal")
        assert len(_rolls(res, "Sneak attack")) == want, feats


def test_shrewd_tactician_denies_the_flank_bonus_and_reads_feints():
    """Shrewd Tactician (ISWG): "Opponents do not gain a +2 bonus on attack rolls for
    flanking you, although they can still sneak attack you", and +3 Sense Motive against a
    feint. Borin and Kesst flank the thug; the thug's feat takes the +2 away."""
    from rules import position

    scene, engine, pc, thug = _fight(ally=((8, 10), []))
    assert any("flanking" in m.source for m in position.attack_mods(scene, pc, thug))
    thug.feats = list(thug.feats or ()) + ["Shrewd Tactician"]
    assert not any("flanking" in m.source for m in position.attack_mods(scene, pc, thug))
    assert position.flanking_with(scene, pc, thug)        # the flank itself stands

    def sm(ctx):
        return sum(m.value for m in thug.skill_modifiers("sense motive", ctx=ctx))
    assert sm({"against": "feint"}) == sm(None) + 3


def test_flanking_foil_marks_the_one_struck_and_takes_its_flank_and_dice():
    """Flanking Foil (UC): an adjacent foe hit in melee gets no flanking bonus against the
    bearer and no sneak dice on them until the bearer's next turn."""
    from rules import position, precision

    scene, engine, pc, thug = _fight(feats=["Flanking Foil"],
                                     faces={"Attack with": 18, "Damage": 1})
    thug.hp = thug.hp_max = 200
    _attack(engine)
    assert precision.foiled(thug, pc)
    friend = load_pc("fixtures/pc-kesst.json")
    friend.ref, friend.kind = "rogue2", "npc"
    scene.add(friend)
    scene.positions["rogue2"] = (5, 10)
    scene.sides = {"pc": ["pc"], "them": ["c1", "rogue2"]}
    assert not any("flanking" in m.source for m in position.attack_mods(scene, thug, pc))
    thug.tick_effects(1)
    assert not precision.foiled(thug, pc)


def test_knockout_artist_adds_one_a_sneak_die_to_a_pulled_fist():
    """Knockout Artist (UC): +1 damage per sneak attack die on a nonlethal unarmed strike
    at a foe denied Dexterity."""
    for feats, want in (([], 0), (["Improved Unarmed Strike", "Knockout Artist"], 1)):
        scene, engine, pc, thug = _fight("fixtures/pc-kesst.json", feats=feats,
                                         faces={"Attack with": 18, "Damage": 1,
                                                "Sneak": 1})
        thug.hp = thug.hp_max = 200
        thug.add_condition("flat-footed", 1, source="test")
        res = _attack(engine, weapon="unarmed", lethality="nonlethal")
        dmg = [r for r in _rolls(res, "Damage")]
        assert dmg and _named(dmg[0], "Knockout Artist") == want, (feats, dmg)


def test_precise_strike_rolls_its_d6_only_beside_a_flanker_who_holds_it():
    """Precise Strike (APG, teamwork): +1d6 precision on each melee hit while flanking a
    creature with an ally who also has the feat."""
    for theirs, want in (([], 0), (["Precise Strike"], 1)):
        scene, engine, pc, thug = _fight(feats=["Precise Strike"],
                                         ally=((8, 10), theirs),
                                         faces={"Attack with": 18, "Damage": 1})
        thug.hp = thug.hp_max = 200
        res = _attack(engine)
        assert len(_rolls(res, "Precise Strike")) == want


# --- the blow's own terms: Hammer the Gap, Devastating Strike, Belier's Bite -------------

def test_hammer_the_gap_adds_the_run_of_earlier_hits_on_one_foe():
    """Hammer the Gap (UC): each consecutive hit on the same foe in a full attack deals
    extra damage equal to the hits before it. Borin at BAB +11 swings three times."""
    scene, engine, pc, thug = _fight(feats=["Hammer the Gap"], level=11,
                                     faces={"Attack with": 18, "Damage": 1})
    thug.hp = thug.hp_max = 400
    res = _attack(engine, full_attack=True)
    dmg = _rolls(res, "Damage")
    assert [_named(r, "Hammer the Gap") for r in dmg] == [0, 1, 2]


def test_devastating_strike_adds_two_per_extra_vital_die():
    """Devastating Strike (UC): +2 on each extra weapon die Vital Strike grants (+6
    maximum). Vital Strike alone: +2; with Improved Vital Strike: +4."""
    for feats, want in ((["Vital Strike", "Devastating Strike"], 2),
                        (["Vital Strike", "Improved Vital Strike", "Devastating Strike"], 4)):
        scene, engine, pc, thug = _fight(feats=feats, level=11,
                                         faces={"Attack with": 18, "Damage": 1})
        thug.hp = thug.hp_max = 400
        dmg = _rolls(_attack(engine, vital_strike=True), "Damage")
        assert _named(dmg[0], "Devastating Strike") == want


def test_belier_s_bite_bleeds_an_unarmed_hit_and_not_a_sword():
    """Belier's Bite (Cheliax): "When you damage an opponent with an unarmed strike, you
    deal an extra 1d4 bleed damage"."""
    for weapon, want in (("unarmed", True), ("longsword", False)):
        scene, engine, pc, thug = _fight(feats=["Improved Unarmed Strike", "Belier's Bite"],
                                         faces={"Attack with": 18, "Damage": 1})
        thug.hp = thug.hp_max = 200
        res = _attack(engine, weapon=weapon)
        assert any(e.get("condition") == "bleed"
                   for e in _effects(res, "condition")) is want, weapon


# --- the defender's guards: Survivor, Resilient Brute ------------------------------------

def test_survivor_stabilises_at_plus_five_and_turns_one_critical_a_day():
    """Survivor (ISWG): +5 on Constitution checks to stabilize; once a day a critical
    against you lands as an ordinary hit. The thug's second critical lands in full."""
    scene, engine, pc, thug = _fight(feats=["Diehard", "Endurance", "Survivor"],
                                     faces={"Attack with": 20, "Confirm": 20, "Damage": 1})
    plain = sum(m.value for m in pc.ability_check_modifiers("con"))
    assert sum(m.value for m in pc.ability_check_modifiers(
        "con", {"against": "stabilize"})) == plain + 5
    pc.hp = pc.hp_max = 200
    first = _attack(engine, by="c1", target="pc")
    assert "no critical (Survivor)" in _tells(first)
    assert pc.pool("survivor").current == 0
    second = _attack(engine, by="c1", target="pc")
    assert "critically" in _tells(second)


def test_resilient_brute_takes_half_a_critical_as_nonlethal():
    """Resilient Brute (ARG): once a day (twice from BAB +10), half a confirmed critical's
    damage is nonlethal."""
    scene, engine, pc, thug = _fight(feats=["Resilient Brute"],
                                     faces={"Attack with": 20, "Confirm": 20, "Damage": 10})
    pc.hp = pc.hp_max = 200
    res = _attack(engine, by="c1", target="pc")
    assert pc.nonlethal > 0
    assert "Resilient Brute" in _tells(res)
    assert pc.pool("resilient-brute").maximum == 1


# --- rage's events: Gore Fiend, Thrill of the Kill, Raging Deathblow ---------------------

def test_gore_fiend_wins_a_round_of_rage_back_on_a_critical_once_a_round():
    """Gore Fiend (ARG): raging, a melee critical you confirm gives back a round of rage, up
    to the day's maximum, once a round."""
    scene, engine, pc, thug = _fight(feats=["Gore Fiend"], cls="barbarian", level=6,
                                     faces={"Attack with": 20, "Confirm": 20, "Damage": 1})
    thug.hp = thug.hp_max = 400
    _rage(pc, spent=3)
    left = pc.pool("rage").current
    _attack(engine)
    assert pc.pool("rage").current == left + 1
    _attack(engine)                                       # same round: no second round
    assert pc.pool("rage").current == left + 1


def test_gore_fiend_counts_a_critical_taken_too():
    scene, engine, pc, thug = _fight(feats=["Gore Fiend"], cls="barbarian", level=6,
                                     faces={"Attack with": 20, "Confirm": 20, "Damage": 1})
    pc.hp = pc.hp_max = 400
    _rage(pc, spent=3)
    left = pc.pool("rage").current
    _attack(engine, by="c1", target="pc")
    assert pc.pool("rage").current == left + 1


def test_thrill_of_the_kill_needs_a_foe_of_at_least_the_bearer_s_hit_dice():
    """Thrill of the Kill (ARG): a round of rage back for a foe taken below 0 hit points,
    only if it had at least as many Hit Dice as the bearer."""
    for level, want in ((1, 1), (12, 0)):
        scene, engine, pc, thug = _fight(feats=["Thrill of the Kill"], cls="barbarian",
                                         level=level, faces={"Attack with": 18,
                                                             "Damage": 30})
        _rage(pc, spent=2)
        left = pc.pool("rage").current
        thug.hp = 2
        _attack(engine)
        assert thug.hp < 0
        assert pc.pool("rage").current == left + want, level


def test_raging_deathblow_banks_rounds_past_the_maximum_until_the_rest():
    """Raging Deathblow (UC): raging, a foe of CR at least the bearer's level taken to -1 or
    fewer gives an extra round of rage for the day — two on a critical — and a rest takes
    the extra back."""
    scene, engine, pc, giant = _fight(feats=["Raging Deathblow"], cls="barbarian", level=11,
                                      foe="storm-giant",
                                      faces={"Attack with": 20, "Confirm": 20, "Damage": 30})
    _rage(pc, spent=0)
    top = pc.pool("rage").maximum
    giant.hp = 1
    _attack(engine)
    assert pc.pool("rage").current == top + 2 and pc.pool("rage").maximum == top + 2
    pc.rest()
    from rules import resources, classes

    resources.define(pc, classes.get("barbarian")["pools"][0])
    assert pc.pool("rage").maximum == top


# --- the fall: Cleaving Finish -------------------------------------------------------------

def test_cleaving_finish_carries_into_the_next_foe_once_a_round():
    """Cleaving Finish (UC): a foe dropped by the melee blow lets the bearer swing at
    another foe in reach at the highest base attack bonus, once a round."""
    scene, engine, pc, thug = _fight(feats=["Cleave", "Cleaving Finish"],
                                     second=("thug", (7, 11)),
                                     faces={"Attack with": 18, "Damage": 30})
    thug.hp = 1
    scene.get("c2").hp = scene.get("c2").hp_max = 400
    res = _attack(engine)
    swings = [o for o in res.outcomes if o.op == "attack"]
    assert len(swings) == 2 and any(e.get("ref") == "c2" for e in swings[1].effects)
    assert "Cleaving Finish" in _tells(res)


# --- Witchbreaker ---------------------------------------------------------------------------

def test_witchbreaker_adds_two_to_saves_against_a_hag_only():
    """Witchbreaker (People of the North): +2 on saves against the spells and abilities of
    witches and hags. A green hag's spell is against `hag_or_witch`; an ogre's is not."""
    from rules import feat_events

    scene, engine, pc, hag = _fight(feats=["Iron Will", "Witchbreaker"], foe="green-hag")
    assert feat_events.is_hag_or_witch(hag)
    assert not feat_events.is_hag_or_witch(instantiate("ogre", scene=scene))
    plain = sum(m.value for m in pc.save_modifiers("will"))
    against = sum(m.value for m in pc.save_modifiers(
        "will", {"against": ("spell", "hag_or_witch")}))
    assert against == plain + 2


# --- declared options: Furious Finish, Pushing Assault, Dragonslayer, Wingclipper --------

def test_furious_finish_maximises_vital_strike_and_ends_the_rage_in_fatigue():
    """Furious Finish (UC): raging, a Vital Strike's dice at their maximum (a longsword's
    2d8: 16), the rage ended at once and the barbarian fatigued."""
    scene, engine, pc, thug = _fight(feats=["Vital Strike", "Furious Finish"],
                                     cls="barbarian", level=8,
                                     faces={"Attack with": 18, "Damage": 1})
    thug.hp = thug.hp_max = 400
    _rage(pc, spent=1)
    assert engine._attack_choice_refusal(pc, "longsword", {"furious_finish": True})
    res = _attack(engine, vital_strike=True, furious_finish=True)
    dmg = _rolls(res, "Damage")[0]
    assert "maximised" in dmg["label"] and dmg["raw"] == 16
    assert not pc.has_state("buff.stance.rage")
    assert pc.has_state("state.impaired.fatigued")


def test_pushing_assault_trades_the_power_attack_damage_for_a_push():
    """Pushing Assault (APG): a two-handed Power Attack hit pushes a foe no larger than you
    5 feet away instead of the extra damage; its -1 to hit stands."""
    scene, engine, pc, thug = _fight(feats=["Pushing Assault"], level=4,
                                     faces={"Attack with": 18, "Damage": 1})
    pc.weapons = list(pc.weapons) + ["greatsword"]
    pc.shield = ""
    thug.hp = thug.hp_max = 400
    assert engine._attack_choice_refusal(pc, "longsword", {"pushing_assault": True,
                                                           "power_attack": True})
    res = _attack(engine, weapon="greatsword", power_attack=True, pushing_assault=True)
    dmg = _rolls(res, "Damage")[0]
    assert not _named(dmg, "Power Attack")
    assert _named(_rolls(res, "Attack with")[0], "Power Attack") < 0
    assert tuple(scene.positions["c1"][:2]) == (8, 10)


def test_wingclipper_grounds_a_flier_and_keeps_none_of_the_critical_damage():
    """Wingclipper (Dragonslayer's Handbook): the extra critical damage is traded for no
    flight for twice the multiplier in rounds."""
    scene, engine, pc, bird = _fight(feats=["Wingclipper"], level=9, foe="griffon",
                                     faces={"Attack with": 20, "Confirm": 20, "Damage": 1})
    bird.hp = bird.hp_max = 400
    res = _attack(engine, wingclipper=True)
    assert "CRITICAL" not in _rolls(res, "Damage")[0]["label"]
    assert "fly" not in bird.movement_modes()
    bird.tick_effects(4)                                   # longsword x2: four rounds
    assert "fly" in bird.movement_modes()


def test_dragonslayer_bars_the_breath_and_only_against_a_breather():
    scene, engine, pc, wyrm = _fight(feats=["Dragonslayer"], level=4,
                                     foe="young-red-dragon",
                                     faces={"Attack with": 20, "Confirm": 20, "Damage": 1})
    wyrm.hp = wyrm.hp_max = 400
    pc.ranks["knowledge (arcana)"] = 4
    _attack(engine, dragonslayer=True)
    assert wyrm.has_state("state.breath-barred")
    scene, engine, pc, thug = _fight(feats=["Dragonslayer"], level=4,
                                     faces={"Attack with": 20, "Confirm": 20, "Damage": 1})
    thug.hp = thug.hp_max = 400
    pc.ranks["knowledge (arcana)"] = 4
    res = _attack(engine, dragonslayer=True)
    assert "CRITICAL" in _rolls(res, "Damage")[0]["label"]


# --- what a landed blow sets off: Violent Display, Betraying Blow, Hold the Blade ---------

def test_violent_display_demoralizes_on_a_critical_with_the_focused_weapon():
    """Violent Display (Blood of the Moon): a critical with a Weapon Focus weapon opens
    Dazzling Display as an immediate action — Intimidate against every foe who sees you."""
    for weapon, want in (("longsword", True), ("dagger", False)):
        scene, engine, pc, thug = _fight(feats=["Dazzling Display", "Violent Display"],
                                         level=6, faces={"Attack with": 20, "Confirm": 20,
                                                         "Damage": 1})
        thug.hp = thug.hp_max = 400
        res = _attack(engine, weapon=weapon)
        assert ("Violent Display: Intimidate" in _tells(res)) is want, weapon


def test_betraying_blow_adds_half_the_bluff_margin_as_nonlethal_capped_at_hit_dice():
    """Betraying Blow (Bastards of Golarion): a nonlethal melee hit on a foe only you
    threaten; Bluff against Sense Motive, half the difference more nonlethal, at most the
    bearer's Hit Dice (8)."""
    scene, engine, pc, thug = _fight(feats=["Solo Maneuvers", "Betraying Blow"], level=8,
                                     faces={"Attack with": 18, "Damage": 1, "Bluff": 20,
                                            "the foe's Sense": 1})
    thug.hp = thug.hp_max = 400
    res = _attack(engine, lethality="nonlethal")
    extra = [e for o in res.outcomes for e in o.effects
             if e.get("origin") == "rule:feat-betraying-blow"]
    assert extra and 0 < int(extra[0]["amount"]) <= 8
    assert "Betraying Blow" in _tells(res)


def test_hold_the_blade_disarms_back_at_a_flanker_and_drops_the_guard(monkeypatch):
    """Hold the Blade (Dragon Empires Primer): a flanking blow that wounds you lets you try
    a disarm as an immediate action, at -4 AC until your next turn, once a round."""
    from rules import feat_events

    monkeypatch.setattr(feat_events, "_hand_free", lambda a: True)
    scene, engine, pc, thug = _fight(feats=["Improved Disarm", "Hold the Blade"], level=10,
                                     second=("thug", (5, 10)),
                                     faces={"Attack with": 18, "Damage": 1})
    pc.hp = pc.hp_max = 400
    ac = pc.ac()
    res = _attack(engine, by="c1", target="pc")
    assert any(e.get("maneuver") == "disarm" for e in _effects(res, "rider"))
    assert pc.ac() == ac - 4
    again = _attack(engine, by="c2", target="pc")
    assert not any(e.get("maneuver") == "disarm" for e in _effects(again, "rider"))


# --- rage's own feats: Raging Vitality, Extra Rage Power, Sympathetic Rage, Warleader's
# Rage, Raging Brutality, Raging Throw --------------------------------------------------

def _use(engine, name, actor="pc", to=None):
    raw = {"op": "use_ability", "actor": actor, "because": "test", "params": {"ability": name}}
    if to:
        raw["params"]["to"] = to
    return engine.run(engine.validate([raw])).outcomes[-1]


def _barbarian(feats=(), level=4, **kw):
    scene, engine, pc, thug = _fight(feats=feats, cls="barbarian", level=level, **kw)
    from rules import classes, resources

    for p in classes.get("barbarian").get("pools") or ():
        resources.define(pc, p)
    return scene, engine, pc, thug


def test_raging_vitality_raises_rage_s_constitution_and_outlasts_unconsciousness():
    """Raging Vitality (APG): the rage's morale Constitution +4 becomes +6, and the rage
    does not end when she falls unconscious (only death ends it)."""
    for feats, con, stays in (([], 4, False), (["Raging Vitality"], 6, True)):
        scene, engine, pc, thug = _barbarian(feats)
        base = pc.ability_score("con") if hasattr(pc, "ability_score") else None
        before = pc.ability_mod("con")
        out = _use(engine, "Rage")
        assert out.status != "refused", out.tell
        assert pc.ability_mod("con") - before == con // 2, feats
        pc.add_condition("unconscious", None, source="test")
        engine._ability_ends_settle()
        assert pc.has_state("buff.stance.rage") is stays, feats
        del base


def test_extra_rage_power_owes_one_more_pick_each_time_it_is_taken():
    """Extra Rage Power (APG): "You gain one additional rage power", taken more than once.
    A 4th-level barbarian is owed two by her levels; one copy makes three, two make four."""
    from rules import classes

    for copies, want in ((0, 2), (1, 3), (2, 4)):
        scene, engine, pc, thug = _barbarian(["Extra Rage Power"] * copies)
        rows = [r for r in classes.owed_rows("barbarian", 4, {}, (),
                                             classes.feat_slots(pc))
                if r["choice"] == "rage power"]
        assert len(rows) == want, copies


def _rager(scene, at):
    friend = load_pc("fixtures/pc-kesst.json")
    friend.ref, friend.kind = "ally", "npc"
    scene.add(friend)
    scene.positions["ally"] = at
    scene.sides = {"pc": ["pc", "ally"], "them": ["c1"]}
    from rules.activeeffect import ActiveEffect

    friend.apply_effect(ActiveEffect(name="rage", kind="buff", key="rage", source="test",
                                     tags=("buff.stance.rage",)))
    return friend


def test_sympathetic_rage_needs_a_raging_ally_beside_you_and_ends_when_they_go():
    """Sympathetic Rage (ARG): a free action beside a raging ally: +2 morale Str and Con,
    rage's Will and AC; it lasts while they stay adjacent and leaves you fatigued."""
    scene, engine, pc, thug = _fight(feats=["Sympathetic Rage"], level=3)
    pc.race = "half-orc"
    assert _use(engine, "Sympathetic Rage").status == "refused"
    friend = _rager(scene, (6, 11))
    strength = pc.ability_mod("str")
    out = _use(engine, "Sympathetic Rage")
    assert out.status != "refused", out.tell
    assert pc.ability_mod("str") == strength + 1 and pc.has_state("buff.stance.rage")
    scene.positions["ally"] = (12, 10)                     # thirty feet off
    engine._ability_ends_settle()
    assert not pc.has_state("buff.stance.rage")
    assert pc.has_state("state.impaired.fatigued")
    del friend


def test_warleader_s_rage_holds_a_sympathetic_rage_at_thirty_feet_in_sight():
    """Warleader's Rage (Orcs of Golarion): a rage begun beside the warleader persists
    while she is within 30 feet and seen."""
    scene, engine, pc, thug = _fight(feats=["Sympathetic Rage"], level=3)
    friend = _rager(scene, (6, 11))
    friend.feats = list(friend.feats) + ["Warleader's Rage"]
    assert _use(engine, "Sympathetic Rage").status != "refused"
    scene.positions["ally"] = (11, 10)                     # twenty-five feet
    engine._ability_ends_settle()
    assert pc.has_state("buff.stance.rage")
    scene.positions["ally"] = (14, 10)                     # forty feet
    engine._ability_ends_settle()
    assert not pc.has_state("buff.stance.rage")


def test_raging_brutality_adds_unmultiplied_constitution_to_power_attack_damage():
    """Raging Brutality (UC): swift, three rounds of rage: + Con on Power Attack damage
    this turn (1-1/2 two-handed), never multiplied on a critical."""
    scene, engine, pc, thug = _barbarian(["Raging Brutality"], level=12,
                                         faces={"Attack with": 20, "Confirm": 20,
                                                "Damage": 1})
    thug.hp = thug.hp_max = 400
    scene.turn = [r for r, _ in scene.initiative].index("pc")       # the bearer's turn
    assert _use(engine, "Raging Brutality").status == "refused"     # not raging
    assert _use(engine, "Rage").status != "refused"
    left = pc.pool("rage").current
    assert _use(engine, "Raging Brutality").status != "refused"
    assert pc.pool("rage").current == left - 3
    con = pc.ability_mod("con")
    dmg = _rolls(_attack(engine, power_attack=True), "Damage")[0]
    assert "CRITICAL" in dmg["label"]
    assert _named(dmg, "Raging Brutality") == con
    plain = _rolls(_attack(engine), "Damage")[0]
    assert not _named(plain, "Raging Brutality")
    # Off the bearer's turn (an attack of opportunity, say) it adds nothing: "attacks you
    # make on your turn". Measured before the fix: `own_turn` compared the Scene's method
    # to a ref and was never true, so the term held for nobody in a real fight.
    scene.turn = [r for r, _ in scene.initiative].index("c1")
    off = _rolls(_attack(engine, power_attack=True), "Damage")[0]
    assert not _named(off, "Raging Brutality")


def test_raging_throw_adds_constitution_to_the_bull_rush_only():
    scene, engine, pc, thug = _barbarian(["Raging Throw"], level=6)
    assert _use(engine, "Rage").status != "refused"
    rush = sum(m.value for m in pc.cmb_modifiers("bull rush", defender=thug))
    trip = sum(m.value for m in pc.cmb_modifiers("trip", defender=thug))
    assert _use(engine, "Raging Throw").status != "refused"
    con = pc.ability_mod("con")
    assert sum(m.value for m in pc.cmb_modifiers("bull rush", defender=thug)) == rush + con
    assert sum(m.value for m in pc.cmb_modifiers("trip", defender=thug)) == trip


# --- the druid in a shape: Natural Spell, Wild Speech, Powerful Shape, Quick Wild Shape ----

def _druid(feats=(), level=8):
    from rules.sheet import from_dict, to_dict

    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "druid", "level": level, "ranks": {}, "armour": "none"})
    d["abilities"]["wis"] = 18
    d["spellbook"] = ["cure-light-wounds"]
    d["prepared"] = {"cure-light-wounds": 3}
    d["feats"] = list(d.get("feats") or ()) + list(feats)
    pc = from_dict(d, ref="pc")
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(pc)
    scene.add(instantiate("thug", scene=scene, name=FOE))
    scene.initiative = [("pc", 20), ("c1", 10)]
    scene.sides = {"pc": ["pc"], "them": ["c1"]}
    scene.round, scene.turn = 1, 0
    return scene, Engine(scene, Dice(seed=5)), pc


def _cast(engine, spell="cure-light-wounds", at="pc"):
    return engine.run(engine.validate([{"op": "cast", "actor": "pc", "because": "test",
                                        "params": {"spell": spell, "at": at}}])).outcomes[-1]


def test_a_druid_in_a_wolf_s_shape_casts_only_with_natural_spell():
    """CRB, wild shape: no speech in an animal's form; Natural Spell (CRB) completes the
    verbal and somatic components; Wild Speech (UM) the verbal alone. Measured before: a
    druid shaped as a wolf cast cure light wounds (V, S) with nothing asked."""
    for feats, refused, why in (([], True, "throat"), (["Wild Speech"], True, "paws"),
                                (["Natural Spell"], False, "")):
        scene, engine, pc = _druid(feats)
        assert _use(engine, "Wild Shape (wolf)").status != "refused"
        out = _cast(engine)
        assert (out.status == "refused") is refused, (feats, out.tell)
        assert why in out.tell, (feats, out.tell)
        assert _use(engine, "Wild Shape").status != "refused"       # back to herself
        assert _cast(engine).status != "refused"


def test_wild_speech_speaks_with_animals_a_minute_a_use_in_a_shape_only():
    """Wild Speech (UM): speak with animals as a spell-like ability, druid level minutes a
    day, in an animal's shape."""
    from rules import animals

    scene, engine, pc = _druid(["Wild Speech"], level=6)
    assert _use(engine, "Wild Speech").status == "refused"
    assert _use(engine, "Wild Shape (wolf)").status != "refused"
    assert _use(engine, "Wild Speech").status != "refused"
    assert animals.speaks_with_animals(pc) if hasattr(animals, "speaks_with_animals") \
        else pc.has_state("permission.speak_with_animals")
    assert pc.pool("wild speech").current == 5


def test_powerful_shape_fights_one_size_larger_in_cmb_and_cmd_only_while_shaped():
    scene, engine, pc = _druid(["Powerful Shape"])
    cmb = sum(m.value for m in pc.cmb_modifiers("trip"))
    assert _use(engine, "Wild Shape (wolf)").status != "refused"
    shaped = sum(m.value for m in pc.cmb_modifiers("trip"))
    pc.feats = [f for f in pc.feats if f != "Powerful Shape"]
    plain_shaped = sum(m.value for m in pc.cmb_modifiers("trip"))
    assert shaped == plain_shaped + 1
    del cmb


def test_quick_wild_shape_changes_as_a_move_or_swift_action_with_lower_forms():
    """Quick Wild Shape (UM): a move action (forms of two druid levels lower) or a swift
    action (four lower). At 8th: Large as a move action (6th's forms), not as a swift
    action (4th's: Small and Medium)."""
    from rules import class_abilities as ca

    scene, engine, pc = _druid(["Quick Wild Shape"], level=8)
    quick, _ = ca.find(pc, "quick wild shape (wolf)")
    swift, _ = ca.find(pc, "swift wild shape (wolf)")
    assert ca.action_of(quick, pc) == "move" and ca.action_of(swift, pc) == "swift"
    assert "large" in {v["size"] for v in ca.forms_for(pc, quick).values()}
    assert "large" not in {v["size"] for v in ca.forms_for(pc, swift).values()}
    assert _use(engine, "Swift Wild Shape (wolf)").status != "refused"
    assert pc.has_state("form.animal")
    assert _use(engine, "Wild Shape").status != "refused"          # the one stance ends
    assert not pc.has_state("form.animal")


# --- companions: Boon Companion, Falconer's Art ---------------------------------------------

def test_boon_companion_raises_a_ranger_s_companion_four_levels_to_his_own():
    """Boon Companion (Animal Archive): the companion figured as though the class were 4
    levels higher, never past the character level. A 6th-level ranger's companion is at
    3rd (level - 3); with the feat, 6th — not 7th."""
    from rules import animal_companion

    scene, engine, pc, thug = _fight(cls="ranger", level=6)
    assert animal_companion.effective_level(pc, -3) == 3
    pc.feats = list(pc.feats) + ["Boon Companion"]
    assert animal_companion.effective_level(pc, -3) == 6
    assert animal_companion.effective_level(pc, 0) == 6


def test_falconer_s_art_gives_the_bird_its_chosen_bonus_and_the_handler_two():
    """Falconer's Art (ISWG): a bird of prey companion gains the bonus chosen with it (+1
    dodge AC here); the handler +2 on Handle Animal with birds of prey, not with a wolf."""
    from rules import animal_companion, animals

    scene, engine, pc, thug = _fight(cls="druid", level=4,
                                     feats=["Animal Affinity", "Falconer's Art (dodge)"])
    pc.ranks["handle animal"] = 4
    bird = animal_companion.make(scene, pc, "eagle")
    wolf = animal_companion.make(scene, pc, "wolf")
    assert any(m.get("target") == "ac" and m.get("bonus_type") == "dodge"
               for e in bird.effects for m in e.modifiers)
    assert not any(m.get("note") == "Falconer's Art" for e in wolf.effects
                   for m in e.modifiers)

    def bonus(animal):
        mods, _label, _why = animals._mods(pc, animal, untrained_ok=False)
        return sum(m.value for m in mods if m.source.startswith("Falconer"))
    assert bonus(bird) == 2 and bonus(wolf) == 0


def test_invoke_primal_instinct_spends_a_wild_shape_and_frightens_on_a_bluff_dc():
    """Invoke Primal Instinct (Gnomes of Golarion): a standard action and a use of wild
    shape; the Bluff check is the Will DC of everyone within 30 feet, frightened a round a
    druid level on a failure."""
    scene, engine, pc, thug = _fight(feats=["Invoke Primal Instinct"], cls="druid", level=6,
                                     faces={"Invoke Primal Instinct: Bluff": 20,
                                            "Will save": 1})
    from rules import classes, resources

    for p in classes.get("druid").get("pools") or ():
        resources.define(pc, p)
    pc.ranks["bluff"] = 1
    pc.armour, pc.shield = "none", ""     # a druid in metal loses her powers (CRB)
    left = pc.pool("wild shape").current
    out = _use(engine, "Invoke Primal Instinct")
    assert out.status != "refused", out.tell
    assert pc.pool("wild shape").current == left - 1
    assert thug.has_state("state.fear.frightened")
    assert "sets the DC" in out.tell


def test_planar_wild_shape_spends_two_uses_for_the_template_s_resistances():
    """Planar Wild Shape (UC): an extra daily use of wild shape adds the celestial (or
    fiendish) template: at 8 Hit Dice, resist acid, cold and electricity 10, darkvision;
    +2 to confirm a critical against an evil creature."""
    scene, engine, pc = _druid(["Planar Wild Shape"], level=8)
    pc.ranks["knowledge (planes)"] = 5
    from rules import classes, resources

    for p in classes.get("druid").get("pools") or ():
        resources.define(pc, p)
    left = pc.pool("wild shape").current
    assert _use(engine, "Celestial Wild Shape (wolf)").status != "refused"
    assert pc.pool("wild shape").current == left - 2
    assert pc.resistance("acid") == 10 and pc.resistance("fire") == 0
    assert pc.has_state("sense.darkvision")
    assert _use(engine, "Wild Shape").status != "refused"
    assert pc.resistance("acid") == 0
