"""Feat loop, batch 1, lane b1-modifiers (owner 2026-11-22: "every single feat working").

Measured on the lane's base (4c45e496) before it: none of these feats had a document, so
each was "not computed" on the sheet and moved no roll. Also measured, and fixed as the
machinery the feats needed:

- `FEAT_TARGET_RE` was `[^)]+`, so "skill focus (knowledge (arcana))" matched nothing and
  Skill Focus could never land on a Knowledge; a feat that picks two skills had no shape.
- A feat term with a `when` on the AC line was always dropped: the AC read had no context.
- No Demoralize charged the book's +/-4 per size category, so Taunt had nothing to waive.
- A shield bash cost nothing ("loses the shield's shield bonus to AC until his next
  turn" was never charged), so Improved Shield Bash had nothing to keep.

Each test quotes the benefit and reads the number off the engine or the sheet.
"""
from __future__ import annotations

from rules import classbuilder, feats, position, spells
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.effectspec import spell_against
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.sheet import from_dict, situated

FILE = "content/feats/mechanics/batch1-modifiers.json"


def _tot(mods) -> int:
    return sum(m.value for m in mods)


def _of(mods, name) -> list[int]:
    return [m.value for m in mods if m.source == name]


def _pc(feats=(), level=6, ranks=None, **extra):
    data = {"name": "Wren", "kind": "pc", "class": "fighter", "level": level,
            "abilities": {"str": 14, "dex": 14, "con": 12, "int": 12, "wis": 12, "cha": 12},
            "hp": 60, "weapons": ["longsword"], "equipped": "longsword",
            "feats": list(feats), "ranks": dict(ranks or {})}
    data.update(extra)
    return from_dict(data)


class _Rng:
    """Every d20 comes off the list; every other die rolls its lowest face."""

    def __init__(self, d20s):
        self.d20s = list(d20s)

    def randint(self, a, b):
        return self.d20s.pop(0) if b == 20 and self.d20s else a


class Loaded(Dice):
    def __init__(self, *d20s):
        super().__init__(0)
        self._rng = _Rng(d20s)


def _board(*actors, foes=(), dice=None):
    """A 20x20 board with `actors` on it and a fresh creature per template in `foes`,
    minted against the scene so each has its own ref."""
    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
    for a in actors:
        s.add(a)
    made = [s.add(instantiate(t, scene=s, name=f"{t} {i + 1}")) for i, t in enumerate(foes)]
    return (s, Engine(s, dice or Dice(seed=3)), *made)


def _run(e, raw):
    for r in raw:
        r.setdefault("visibility", "hidden")
        r.setdefault("because", "test")
    return e.run(e.validate(raw, origin="author:test"))


# --- the documents ---------------------------------------------------------------------------

def test_the_lane_documents_load_and_validate():
    """Every document in the lane's file is a feat and validates with the fix named."""
    import json
    from pathlib import Path

    from django.conf import settings

    mine = json.loads((Path(settings.BASE_DIR) / FILE).read_text(encoding="utf-8"))
    ids = [k for k in mine if not k.startswith("_")]
    assert len(ids) >= 24
    assert classbuilder.validate_feat_documents({k: mine[k] for k in ids}) == []
    for fid in ids:
        assert feats.documents()[fid] == mine[fid]


# --- plain skill terms ---------------------------------------------------------------------

def test_nature_soul_and_sea_legs_and_the_ten_rank_rung():
    """Nature Soul: "+2 on all Knowledge (nature) checks and Survival checks. If you have 10
    or more ranks in one of these skills, the bonus increases to +4 for that skill." Sea
    Legs: "+2 bonus on Acrobatics, Climb, and Swim checks." """
    a = _pc(["Nature Soul", "Sea Legs"], level=10, ranks={"knowledge (nature)": 10, "survival": 2})
    assert _of(a.skill_modifiers("knowledge (nature)"), "Nature Soul") == [4]
    assert _of(a.skill_modifiers("survival"), "Nature Soul") == [2]
    for skill in ("acrobatics", "climb", "swim"):
        assert _of(a.skill_modifiers(skill), "Sea Legs") == [2]
    assert _of(a.skill_modifiers("perception"), "Sea Legs") == []


def test_scholar_and_prodigy_bind_to_both_picks_and_skill_focus_reaches_a_knowledge():
    """Scholar: "Pick any two Knowledge skills. You gain a +2 bonus on these two skills"
    (+4 at 10 ranks). Before: a parenthetical with parentheses in it matched nothing, so
    neither this nor Skill Focus (knowledge (arcana)) bound to anything."""
    a = _pc(["Scholar (knowledge (history), knowledge (local))", "Prodigy (craft, perform)",
             "Skill Focus (knowledge (arcana))"], level=10,
            ranks={"knowledge (history)": 10, "knowledge (local)": 1, "knowledge (arcana)": 1,
                   "craft": 1, "perform": 1, "profession": 1})
    assert _of(a.skill_modifiers("knowledge (history)"), "Scholar") == [4]
    assert _of(a.skill_modifiers("knowledge (local)"), "Scholar") == [2]
    assert _of(a.skill_modifiers("knowledge (arcana)"), "Scholar") == []
    assert _of(a.skill_modifiers("knowledge (arcana)"), "Skill Focus") == [3]
    assert _of(a.skill_modifiers("craft"), "Prodigy") == [2]
    assert _of(a.skill_modifiers("perform"), "Prodigy") == [2]
    assert _of(a.skill_modifiers("profession"), "Prodigy") == []


def test_cosmopolitan_makes_its_two_picks_class_skills():
    """Cosmopolitan: "choose two Intelligence-, Wisdom-, or Charisma-based skills. Those
    skills always count as class skills for you." A fighter's Diplomacy is not one; with
    a rank in it the +3 arrives."""
    plain = _pc(ranks={"diplomacy": 1, "linguistics": 1})
    a = _pc(["Cosmopolitan (diplomacy, linguistics)"], ranks={"diplomacy": 1, "linguistics": 1})
    assert "diplomacy" not in plain.class_skills
    assert {"diplomacy", "linguistics"} <= set(a.class_skills)
    assert _of(a.skill_modifiers("diplomacy"), "class skill") == [3]
    assert _of(plain.skill_modifiers("diplomacy"), "class skill") == []


def test_uncanny_alertness_perception_and_saves_against_sleep_and_charm():
    """Uncanny Alertness: "an additional +1 bonus on Perception and Sense Motive checks,
    and ... a +2 bonus on saving throws against sleep and charm effects." A sleep spell is
    known by its own effect (it lands magical slumber), a charm by its subschool."""
    a = _pc(["Alertness", "Uncanny Alertness"])
    assert _of(a.skill_modifiers("perception"), "Uncanny Alertness") == [1]
    assert "sleep" in spell_against(spells.get("sleep"))
    assert "sleep" not in spell_against(spells.get("fireball"))
    for spell in ("sleep", "charm-person"):
        mods = a.save_modifiers("will", {"against": spell_against(spells.get(spell))})
        assert _of(mods, "Uncanny Alertness") == [2], spell
    assert _of(a.save_modifiers("will", {"against": spell_against(spells.get("fear"))}),
               "Uncanny Alertness") == []


def test_storm_lashed_fearless_curiosity_harrowed_answer_the_spells_descriptors():
    """Storm-Lashed: "+2 bonus on all saving throws against electrical effects"; Fearless
    Curiosity: "+1 bonus on saving throws against effects with the emotion descriptor";
    Harrowed: "+1 bonus on all Will saves made to resist enchantment effects"."""
    a = _pc(["Storm-Lashed", "Fearless Curiosity", "Harrowed"])
    bolt = {"against": spell_against(spells.get("lightning-bolt"))}
    rage = {"against": spell_against(spells.get("rage"))}
    assert _of(a.save_modifiers("ref", bolt), "Storm-Lashed") == [2]
    assert _of(a.save_modifiers("will", rage), "Fearless Curiosity") == [1]
    assert _of(a.save_modifiers("will", rage), "Harrowed") == [1]    # rage is enchantment
    assert _of(a.save_modifiers("ref", {"against": spell_against(spells.get("fireball"))}),
               "Storm-Lashed") == []


def test_improvisation_opens_trained_skills_and_adds_two_only_without_ranks():
    """Improvisation: "+2 bonus on all skill checks for skills you have no ranks in.
    Furthermore, you can use all trained skills untrained." """
    import pytest

    from rules.sheet import IllegalSheet

    with pytest.raises(IllegalSheet):
        _pc().skill_modifiers("disable device")
    a = _pc(["Improvisation"], ranks={"climb": 3})
    assert _of(a.skill_modifiers("disable device"), "Improvisation") == [2]
    assert _of(a.skill_modifiers("climb"), "Improvisation") == []


def test_stone_read_underground_or_mountain_scaling_on_dungeoneering():
    """Stone Read: "While within a primarily underground or mountainous environment, you
    gain a +2 bonus on Perception checks. If you have 10 or more ranks in Knowledge
    (dungeoneering), the bonus increases to +4." The rung is on another skill's ranks."""
    a = _pc(["Stone Read"], ranks={"knowledge (dungeoneering)": 4})
    a.at = "town~urban"
    assert _of(a.skill_modifiers("perception"), "Stone Read") == []
    a.at = "deep~underground"
    assert _of(a.skill_modifiers("perception"), "Stone Read") == [2]
    a.level = 10
    a.ranks["knowledge (dungeoneering)"] = 10
    a.at = "peak~mountain"
    assert _of(a.skill_modifiers("perception"), "Stone Read") == [4]


def test_desert_dweller_feels_no_very_hot_weather_and_resists_thirst():
    """Desert Dweller: "You are not impacted at all by very hot conditions ... +4 bonus on
    all Constitution checks made to resist the effects of starvation or thirst." The
    engine's heat row is very hot (above 90 F): no save is rolled for her."""
    a = _pc(["Desert Dweller"])
    plain = _pc()
    s, e = _board(a, plain)[:2]
    rolls, fx, said = e._exposure(a, "heat", 3)
    assert rolls == [] and fx == [] and "none of it" in said
    assert len(e._exposure(plain, "heat", 3)[0]) >= 3
    assert _of(a.ability_check_modifiers("con", {"against": "thirst"}), "Desert Dweller") == [4]


# --- armour class ----------------------------------------------------------------------------

def test_cautious_fighter_adds_two_dodge_to_fighting_defensively():
    """Cautious Fighter: "When fighting defensively or using total defense, your dodge
    bonus to AC increases by 2." Driven through the attack op's declared option."""
    a = _pc(["Cautious Fighter"])
    s, e, thug = _board(a, foes=["thug"])
    e._ensure_encounter(a.ref, thug.ref)
    s.positions[a.ref], s.positions[thug.ref] = (5, 5), (6, 5)
    before = a.ac()
    _run(e, [{"op": "attack", "actor": a.ref, "target": thug.ref,
              "params": {"fighting_defensively": True}}])
    assert a.ac() == before + 2 + 2
    a.tick_effects()
    assert a.ac() == before


def test_low_profile_dodges_arrows_not_blades_and_gives_no_soft_cover():
    """Low Profile: "+1 dodge bonus to AC against ranged attacks. In addition, you do not
    provide soft cover to creatures when ranged attacks pass through your square." """
    a = _pc(["Low Profile"], size="small")
    thug = instantiate("thug", name="thug")
    assert a.ac(against="ranged", attacker=thug) == a.ac(against="melee", attacker=thug) + 1
    target = _pc(name="Target")
    s, e, archer = _board(a, target, foes=["thug"])
    s.positions.update({archer.ref: (2, 5), a.ref: (4, 5), target.ref: (6, 5)})
    assert position.cover_of(s, archer, target) == ""
    a.feats = []
    assert position.cover_of(s, archer, target) == "soft"


def test_back_to_back_against_a_flanker_beside_an_ally_with_the_feat():
    """Back to Back: "While you are flanked and adjacent to an ally with this feat, you
    receive a +2 circumstance bonus to AC against attacks from opponents flanking you." """
    a, ally = _pc(["Back to Back"]), _pc(["Back to Back"], name="Ally")
    s, e, t1, t2 = _board(a, ally, foes=["thug", "thug"])
    s.sides = {"us": [a.ref, ally.ref], "them": [t1.ref, t2.ref]}
    s.positions.update({a.ref: (5, 5), ally.ref: (5, 6), t1.ref: (4, 5), t2.ref: (6, 5)})
    with situated(s):
        flanked = a.ac(attacker=t1)
        assert _of(a.ac_modifiers(attacker=t1), "Back to Back") == [2]
        s.positions[t2.ref] = (9, 9)                   # no longer flanked
        assert a.ac(attacker=t1) == flanked - 2
        s.positions[t2.ref] = (6, 5)
        ally.feats = []                                # the ally lacks the feat
        assert a.ac(attacker=t1) == flanked - 2


def test_shake_it_off_and_swarm_scatter_count_adjacent_allies_with_the_feat():
    """Shake It Off: "+1 bonus on saving throws per such ally (maximum +4)". Swarm Scatter:
    "For each ally who has this feat and is adjacent to you, you gain a +1 circumstance
    bonus to AC." A foe holding the feat helps nobody; outside a moment nobody is beside."""
    a = _pc(["Shake It Off", "Swarm Scatter"])
    b, c = (_pc(["Shake It Off", "Swarm Scatter"], name=n) for n in ("B", "C"))
    foe = _pc(["Shake It Off"], name="Foe")
    s, e = _board(a, b, c, foe)[:2]
    s.sides = {"us": [a.ref, b.ref, c.ref], "them": [foe.ref]}
    s.positions.update({a.ref: (5, 5), b.ref: (5, 6), c.ref: (6, 5), foe.ref: (4, 5)})
    assert _of(a.save_modifiers("fort"), "Shake It Off") == []
    with situated(s):
        assert _of(a.save_modifiers("fort"), "Shake It Off") == [2]
        assert _of(a.ac_modifiers(), "Swarm Scatter") == [2]
        s.positions[c.ref] = (12, 12)
        assert _of(a.save_modifiers("will"), "Shake It Off") == [1]


def test_swarm_scatter_turns_a_rat_swarm_away_beside_an_ally():
    """Swarm Scatter: "As long as you have this bonus, you are immune to the swarm attack
    and distraction ability of rat swarms." The swarm's automatic damage does not land."""
    a, ally = _pc(["Swarm Scatter"]), _pc(["Swarm Scatter"], name="Ally")
    s, e, rats = _board(a, ally, foes=["rat-swarm"])
    e._ensure_encounter(rats.ref, a.ref)
    s.sides = {"us": [a.ref, ally.ref], "them": [rats.ref]}
    s.positions.update({a.ref: (5, 5), ally.ref: (5, 6), rats.ref: (5, 5)})
    hp = a.hp
    res = _run(e, [{"op": "attack", "actor": rats.ref, "target": a.ref}])
    assert a.hp == hp and "Swarm Scatter" in res.outcomes[0].tell
    ally.feats = []
    _run(e, [{"op": "attack", "actor": rats.ref, "target": a.ref}])
    assert a.hp < hp


# --- the attack loop --------------------------------------------------------------------------

def _blurred(defender):
    defender.add_buff("concealment", "miss_chance", 20, source="blur", rounds=10)


def test_improved_blind_fight_rolls_no_miss_chance_through_partial_concealment():
    """Improved Blind-Fight: "Your melee attacks ignore the miss chance for less than total
    concealment." A blurred thug: no percentile is rolled for the swing."""
    a = _pc(["Blind-Fight", "Improved Blind-Fight"])
    s, e, thug = _board(a, foes=["thug"])
    e._ensure_encounter(a.ref, thug.ref)
    e.dice = Loaded(19)
    s.positions.update({a.ref: (5, 5), thug.ref: (6, 5)})
    _blurred(thug)
    res = _run(e, [{"op": "attack", "actor": a.ref, "target": thug.ref}])
    labels = [r.label for r in res.outcomes[0].rolls]
    assert not any("miss chance" in str(lab) for lab in labels)
    assert "strikes true" in res.outcomes[0].tell
    # Without it, Blind-Fight alone still rolls the percentile (and may reroll it).
    a.feats = ["Blind-Fight"]
    e.dice = Loaded(19)
    res = _run(e, [{"op": "attack", "actor": a.ref, "target": thug.ref}])
    assert any("miss chance" in str(r.label) for r in res.outcomes[0].rolls)


def test_a_shield_bash_lowers_the_guard_unless_improved():
    """CRB, Combat: "a character that performs a shield bash loses the shield's shield
    bonus to AC until his next turn"; Improved Shield Bash: "you may still apply the
    shield's shield bonus to your AC." Heavy shield: +2."""
    for held, drop in (([], 2), (["Improved Shield Bash"], 0)):
        a = _pc(held, shield="heavy shield")
        s, e, thug = _board(a, foes=["thug"])
        e._ensure_encounter(a.ref, thug.ref)
        e.dice = Loaded(15)
        s.positions.update({a.ref: (5, 5), thug.ref: (6, 5)})
        before = a.ac()
        _run(e, [{"op": "attack", "actor": a.ref, "target": thug.ref,
                  "params": {"weapon": "shield bash"}}])
        assert a.ac() == before - drop, held
        a.tick_effects()
        assert a.ac() == before


def test_bleeding_critical_bleeds_two_d6_and_stacks():
    """Bleeding Critical: "Whenever you score a critical hit with a slashing or piercing
    weapon, your opponent takes 2d6 points of bleed damage ... The effects of this feat
    stack." Two confirmed crits: 4d6 a round."""
    a = _pc(["Critical Focus", "Bleeding Critical"], level=12)
    s, e, thug = _board(a, foes=["thug"])
    thug.hp = thug.hp_max = 500
    e._ensure_encounter(a.ref, thug.ref)
    e.dice = Loaded(20, 20, 20, 20, 20, 20)
    s.positions.update({a.ref: (5, 5), thug.ref: (6, 5)})
    res = _run(e, [{"op": "attack", "actor": a.ref, "target": thug.ref}])
    bleeds = [x for x in thug.effects if x.origin == "rule:feat-bleeding-critical"]
    assert len(bleeds) == 1 and bleeds[0].periodic[0]["damage"] == "2d6"
    assert "2d6 bleed" in res.outcomes[0].tell
    _run(e, [{"op": "attack", "actor": a.ref, "target": thug.ref}])
    bleeds = [x for x in thug.effects if x.origin == "rule:feat-bleeding-critical"]
    assert len(bleeds) == 1 and bleeds[0].periodic[0]["damage"] == "4d6"


def test_crippling_critical_halves_speed_for_a_minute_on_a_failed_save():
    """Crippling Critical: "its speed is halved for 1 minute. A successful Fortitude save
    reduces this duration to 1d4 rounds. The DC of this save is equal to 10 + your base
    attack bonus." Natural 1 on the save: ten rounds at half speed."""
    a = _pc(["Critical Focus", "Crippling Critical"], level=13)
    s, e, thug = _board(a, foes=["thug"])
    thug.hp = thug.hp_max = 500
    speed = thug.speed_feet
    e._ensure_encounter(a.ref, thug.ref)
    e.dice = Loaded(20, 20, 1)
    s.positions.update({a.ref: (5, 5), thug.ref: (6, 5)})
    res = _run(e, [{"op": "attack", "actor": a.ref, "target": thug.ref}])
    crippled = [x for x in thug.effects if x.origin == "rule:feat-crippling-critical"]
    assert crippled and crippled[0].rounds_left == 10
    assert thug.speed_feet == (speed // 2 // 5) * 5
    assert "half speed for 10 rounds" in res.outcomes[0].tell


# --- Demoralize -----------------------------------------------------------------------------

def test_demoralize_charges_size_and_taunt_waives_it_with_bluff():
    """Intimidate (CRB p.99): "-4 penalty for every size category you are smaller" than the
    target. Taunt: "You can demoralize opponents using Bluff rather than Intimidate ... and
    take no skill check penalty for being smaller than your target." Boar Ferocity: "+2
    bonus on Intimidate checks to demoralize opponents" — on Demoralize alone."""
    small = _pc(size="small", ranks={"intimidate": 2, "bluff": 6})
    ogre = instantiate("ogre", name="ogre")
    base = small.skill_modifiers("intimidate")
    mods = Engine._demoralize_mods(small, ogre, base)
    assert _tot(mods) == _tot(base) - 8                      # small against large
    taunting = _pc(["Taunt"], size="small", ranks={"intimidate": 2, "bluff": 6})
    mods = Engine._demoralize_mods(taunting, ogre, taunting.skill_modifiers("intimidate"))
    assert _tot(mods) == _tot(taunting.skill_modifiers("bluff"))
    assert all("Bluff" in m.source for m in mods)
    boar = _pc(["Boar Ferocity"], ranks={"intimidate": 2})
    assert _of(boar.skill_modifiers("intimidate"), "Boar Ferocity") == []
    thug = instantiate("thug", name="thug")
    assert _of(Engine._demoralize_mods(boar, thug, []), "Boar Ferocity") == [2]
