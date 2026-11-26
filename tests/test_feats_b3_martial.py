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
