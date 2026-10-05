"""The martial classes' passive numbers reach the sheet, the roll and the damage path.

Measured 2026-10-05 by the class audit (docs/class-audit.md, §1 and §6), every class built
through `/api/character/create` and levelled 1 -> 20 through `/api/level-up`:

- "The barbarian moves at 30 ft with no damage reduction" at 20th level — the book gives
  40 ft from 1st and DR 5/— at 19th.
- "The paladin has no Charisma on any save" at any level (divine grace, 2nd), no immunity
  to fear or disease (3rd), and `dr=[]` at 20th (5/evil at 17th, 10/evil at 20th).
- "The monk punches at -4 'not proficient with unarmed strike', for 1d3, at every level
  1-20, with no Wisdom in his AC" — and moved at 30 ft at 20th (the book: +60 ft).
- Armour training, bravery, weapon training, favoured enemy and terrain: printed on the
  Class tab, read by nothing.
- And the slug split every ladder into unrelated tags: smite evil 1/day … 7/day were
  SEVEN tags, wild shape ten, slow fall nine, so a reader asking `class.smite-evil` found
  nothing.

Every number below is the Core Rulebook's, checked against d20pfsrd and Archives of Nethys
on 2026-10-05; the source is quoted in each `content/class-features/*.json` document.
"""
from __future__ import annotations

import json

import pytest

from rules import classes, classfeatures, states, weapons as weapons_mod
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, full_sheet, load_pc, to_dict
from tests._board import face_to_face

# CRB, Table: Monk — the unarmed die by level, Medium / Small / Large.
MONK_FIST = {1: ("1d6", "1d4", "1d8"), 4: ("1d8", "1d6", "2d6"), 8: ("1d10", "1d8", "2d8"),
             12: ("2d6", "1d10", "3d6"), 16: ("2d8", "2d6", "3d8"), 20: ("2d10", "2d8", "4d8")}
# CRB, Table: Monk — fast movement by level.
MONK_SPEED = {1: 0, 2: 0, 3: 10, 5: 10, 6: 20, 8: 20, 9: 30, 11: 30, 12: 40, 14: 40,
              15: 50, 17: 50, 18: 60, 20: 60}
# CRB, Table: Monk — the AC bonus column (+ Wis on top).
MONK_AC = {1: 0, 3: 0, 4: 1, 7: 1, 8: 2, 11: 2, 12: 3, 15: 3, 16: 4, 19: 4, 20: 5}


def _pc(cls: str, level: int = 1, **changes):
    """Kesst's sheet as another class at another level, stripped to the bone so the only
    terms left are the class's: no armour, no feats, nothing worn."""
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": cls, "level": level, "armour": "none", "shield": "none",
              "feats": [], "ranks": {}, "weapons": ["longsword", "unarmed"],
              "equipped": "longsword", "speed": 30})
    d.update(changes)
    return from_dict(d, ref="pc")


def _total(mods) -> int:
    return sum(m.value for m in mods)


def _named(mods, needle: str) -> list:
    return [m for m in mods if needle.lower() in m.source.lower()]


def _body(*tags: str):
    """A target that is, by tag, what the test needs it to be (law 1: types are tags)."""
    who = instantiate("thug", name="the target")
    who.apply_effect(ActiveEffect(name="probe body", kind="bond", key="probe-body",
                                  source="test", origin="author:test",
                                  duration="until-dismissed", tags=tuple(tags)))
    return who


# --- the ladder is one tag -----------------------------------------------------------

class TestALadderIsOneFeature:
    def test_smite_evil_was_seven_tags_and_is_one(self):
        """"smite evil 1/day" … "7/day" became class.smite-evil-1-day … -7-day: seven
        unrelated tags, none answering `class.smite-evil`."""
        tags = classfeatures.tags_for("paladin", 19)
        assert [t for t in tags if "smite" in t] == ["class.smite-evil"]
        assert classfeatures.number("paladin", 19, "smite-evil") == 7
        assert classfeatures.number("paladin", 7, "class.smite-evil") == 3

    @pytest.mark.parametrize("cid,level,leaf,count", [
        ("druid", 20, "wild-shape", 1), ("monk", 20, "slow-fall", 1),
        ("barbarian", 19, "damage-reduction", 1), ("monk", 20, "fast-movement", 1),
        ("bard", 17, "lore-master", 1), ("blood bending", 13, "fast-movement", 1),
    ])
    def test_every_ladder_the_audit_named_is_one_tag(self, cid, level, leaf, count):
        tags = classfeatures.tags_for(cid, level)
        assert [t for t in tags if t.startswith(f"class.{leaf}")] == [f"class.{leaf}"]

    @pytest.mark.parametrize("grant,leaf,number,bypass", [
        ("smite evil 7/day", "smite-evil", 7, ""),
        ("fast movement +10 ft", "fast-movement", 10, ""),
        ("fast movement 20ft", "fast-movement", 20, ""),
        ("damage reduction 1/-", "damage-reduction", 1, ""),
        ("damage reduction 5/evil", "damage-reduction", 5, "evil"),
        ("slow fall any distance", "slow-fall", None, ""),
        ("wild shape at will", "wild-shape", None, ""),
        ("AC bonus (Wis)", "ac-bonus", None, ""),
        ("AC bonus +3", "ac-bonus", 3, ""),
        ("sneak attack 3d6", "sneak-attack", None, ""),
        ("favored enemy (2nd)", "favored-enemy", None, ""),
        # The parenthetical's "10" is the take-10 rule, not the rung's number.
        ("jack-of-all-trades (take 10 on any skill)", "jack-of-all-trades", None, ""),
        ("control blood 1a", "control-blood-1a", None, ""),
    ])
    def test_the_rung_says_its_number_and_the_name_stays_the_name(self, grant, leaf, number,
                                                                    bypass):
        assert classfeatures.slug(grant) == leaf
        assert classfeatures.rung_number(grant) == number
        assert classfeatures.rung_bypass(grant) == bypass


# --- barbarian ------------------------------------------------------------------------

class TestBarbarian:
    def test_a_level_20_barbarians_speed_stayed_30_ft(self):
        """Measured: 30 ft at every level 1-20. CRB: "+10 feet", from 1st."""
        for level in (1, 20):
            assert _pc("barbarian", level).speed_feet == 40

    def test_fast_movement_comes_before_armour_and_not_in_heavy(self):
        """"Apply this bonus before modifying the barbarian's speed because of any load
        carried or armor worn" — 30 + 10 = 40 in a breastplate is 30, not 20 + 10; and
        "only when wearing no armor, light armor, or medium armor"."""
        assert _pc("barbarian", 5, armour="breastplate").speed_feet == 30
        assert _pc("barbarian", 5, armour="full plate").speed_feet == 20
        assert _pc("cleric", 5, armour="breastplate").speed_feet == 20

    def test_boots_do_not_swallow_fast_movement(self):
        """It is untyped and "stacks with any other bonuses to the barbarian's land
        speed" — routed through the enhancement channel it would have lost to boots."""
        b = _pc("barbarian", 5)
        b.add_buff("speed", "land", 10, source="boots of striding")
        assert b.speed_feet == 50

    @pytest.mark.parametrize("level,dr", [(6, 0), (7, 1), (9, 1), (10, 2), (13, 3),
                                          (16, 4), (19, 5), (20, 5)])
    def test_damage_reduction_1_at_7th_and_1_more_every_three_levels(self, level, dr):
        """Measured: `dr=[]` at 20th. CRB: 1/— at 7th, +1 at 10th, 13th, 16th and 19th."""
        got = _pc("barbarian", level).damage_reduction("slashing")
        assert (got.amount if got else 0) == dr
        if dr:
            assert got.bypass == "" and got.label == f"DR {dr}/—"

    def test_the_dr_soaks_a_real_blow_and_is_on_the_sheet(self):
        b = _pc("barbarian", 10)
        before = b.hp
        b.take_damage(7, "slashing")
        assert before - b.hp == 5, "DR 2/— takes 2 off a 7-point cut"
        assert {"label": "DR 2/—", "amount": 2, "bypass": "",
                "source": "Damage reduction"} in full_sheet(b)["defense"]["dr"]
        assert b.damage_reduction("fire") is None, "DR never touches energy"


# --- paladin --------------------------------------------------------------------------

class TestPaladin:
    def test_the_paladin_had_no_charisma_on_any_save(self):
        """Measured: no Charisma term on any save at any level. CRB: "a bonus equal to
        her Charisma bonus (if any) on all Saving Throws", from 2nd."""
        cha16 = {"str": 14, "dex": 10, "con": 14, "int": 8, "wis": 10, "cha": 16}
        for save in ("fort", "ref", "will"):
            assert not _named(_pc("paladin", 1, abilities=cha16).save_modifiers(save),
                              "divine grace")
            grace = _named(_pc("paladin", 2, abilities=cha16).save_modifiers(save),
                           "divine grace")
            assert [m.value for m in grace] == [3]
        low = dict(cha16, cha=6)
        assert not _named(_pc("paladin", 5, abilities=low).save_modifiers("will"),
                          "divine grace"), "a Charisma penalty is not a bonus (if any)"

    def test_immune_to_fear_and_disease_at_third_and_charm_at_eighth(self):
        p2, p3, p8 = _pc("paladin", 2), _pc("paladin", 3), _pc("paladin", 8)
        assert not states.immunity_blocks(p2.immunities, "shaken")
        assert states.immunity_blocks(p3.immunities, "shaken") == "fear"
        assert states.immunity_blocks(p3.immunities, "frightened") == "fear"
        assert p3.has_state("immune.disease")
        assert "charm" not in p3.immunities and "charm" in p8.immunities

    def test_the_engine_refuses_fear_on_her(self):
        """The condition op's immunity gate reads `immunities` — the same view."""
        scene = Scene()
        pal = _pc("paladin", 3)
        scene.add(pal)
        engine = Engine(scene, Dice(seed=1))
        out = engine.run(engine.validate(
            [{"op": "condition", "target": "pc", "params": {"condition": "frightened"},
              "because": "a spell"}], origin="spell:cause-fear")).outcomes[-1]
        assert "immune to fear" in out.tell
        assert not pal.has_condition("frightened")

    def test_a_class_immunity_is_read_live_and_never_saved(self):
        """A level lost is an immunity lost: `to_dict` writes the innate half only."""
        p = _pc("paladin", 3)
        assert "disease" in p.immunities
        assert "disease" not in to_dict(p)["immunities"]
        p.level = 2
        assert "disease" not in p.immunities

    @pytest.mark.parametrize("level,amount", [(16, 0), (17, 5), (19, 5), (20, 10)])
    def test_dr_5_evil_at_17th_and_10_evil_at_20th(self, level, amount):
        """Measured: `dr=[]` at 20th. Best-only: the 10/evil does not add to the 5."""
        got = _pc("paladin", level).damage_reduction("slashing")
        assert (got.amount if got else 0) == amount
        if amount:
            assert got.bypass == "evil"
            assert _pc("paladin", level).damage_reduction("slashing", ("evil",)) is None

    def test_aura_of_faith_makes_her_sword_good(self):
        assert "good" in (_pc("paladin", 14).weapon("longsword").get("strikes_as") or [])
        assert "good" not in (_pc("paladin", 13).weapon("longsword").get("strikes_as")
                              or [])


# --- monk -----------------------------------------------------------------------------

def _monk(level: int, **changes):
    changes.setdefault("abilities", {"str": 14, "dex": 14, "con": 12, "int": 10,
                                     "wis": 16, "cha": 8})
    changes.setdefault("weapons", ["unarmed"])
    changes.setdefault("equipped", "unarmed")
    return _pc("monk", level, **changes)


class TestMonk:
    def test_the_monk_punched_at_minus_4_for_1d3_at_every_level(self):
        """Measured at every level 1-20: damage 1d3, "not proficient with unarmed strike
        -4". CRB p.141: "All characters are proficient with unarmed strikes", and the
        monk's die is the table's."""
        for level in range(1, 21):
            m = _monk(level)
            assert not _named(m.attack_modifiers("unarmed"), "not proficient"), level
            want = MONK_FIST[max(k for k in MONK_FIST if k <= level)][0]
            assert m.damage_dice("unarmed") == want, (level, m.damage_dice("unarmed"))

    @pytest.mark.parametrize("level", sorted(MONK_FIST))
    def test_a_small_or_large_monks_fist_is_the_books(self, level):
        _medium, small, large = MONK_FIST[level]
        assert _monk(level, size="small").damage_dice("unarmed") == small
        assert _monk(level, size="large").damage_dice("unarmed") == large

    def test_anybody_can_punch_without_the_penalty_but_only_a_monk_hits_hard(self):
        wizard = _pc("wizard", 5)
        assert not _named(wizard.attack_modifiers("unarmed"), "not proficient")
        assert wizard.damage_dice("unarmed") == "1d3"

    @pytest.mark.parametrize("level", sorted(MONK_AC))
    def test_wisdom_and_the_ladder_reach_ac_and_cmd(self, level):
        """Measured at 20th: AC terms "base 10, Dex". CRB: Wis bonus + 1 at 4th … +5."""
        m = _monk(level)                                  # Wis 16: +3
        want = 3 + MONK_AC[level]
        for mods in (m.ac_modifiers(), m.ac_modifiers(flat_footed=True),
                     m.touch_ac_modifiers(), m.cmd_modifiers()):
            assert [x.value for x in _named(mods, "AC bonus")] == [want], level

    def test_the_ac_bonus_is_lost_in_armour_with_a_shield_or_helpless(self):
        assert not _named(_monk(8, armour="leather").ac_modifiers(), "AC bonus")
        assert not _named(_monk(8, shield="light wooden shield").ac_modifiers(), "AC bonus")
        m = _monk(8)
        m.add_condition("paralyzed", source="test")
        assert not _named(m.ac_modifiers(), "AC bonus")

    def test_a_low_wisdom_monk_keeps_only_the_ladder(self):
        """"his Wisdom bonus (if any)" — a penalty is not added."""
        m = _monk(4, abilities={"str": 14, "dex": 14, "con": 12, "int": 10, "wis": 8,
                                "cha": 8})
        assert [x.value for x in _named(m.ac_modifiers(), "AC bonus")] == [1]

    @pytest.mark.parametrize("level", sorted(MONK_SPEED))
    def test_a_level_20_monks_speed_stayed_30_ft(self, level):
        assert _monk(level).speed_feet == 30 + MONK_SPEED[level]

    def test_fast_movement_is_lost_in_armour(self):
        assert _monk(18, armour="leather").speed_feet == 30

    def test_maneuver_training_puts_monk_level_in_place_of_bab(self):
        m = _monk(10)
        assert _total(m.cmb_modifiers()) == 10 + m.ability_mod("str")

    def test_purity_of_body_and_diamond_body(self):
        assert "disease" not in _monk(4).immunities
        assert "disease" in _monk(5).immunities
        assert "poison" not in _monk(10).immunities and "poison" in _monk(11).immunities

    def test_ki_strike_needs_ki_and_climbs_the_table(self):
        m = _monk(10)
        m.rebuild_pools()
        assert m.pool("ki") and m.pool("ki").current >= 1
        assert set(m.weapon("unarmed")["strikes_as"]) == {"magic", "cold_iron", "silver",
                                                          "lawful"}
        m.pool("ki").current = 0
        assert not m.weapon("unarmed").get("strikes_as"), "no ki, no ki strike"

    def test_perfect_self(self):
        got = _monk(20).damage_reduction("bludgeoning")
        assert got.amount == 10 and got.bypass == "chaotic"

    def test_the_table_carries_the_rows_the_audit_found_missing(self):
        """"The class table also omits the 1d10 at 8th", the AC and speed ladders, and ki
        strike."""
        assert "unarmed strike 1d10" in classes.features_at("monk", 8)
        assert [classfeatures.number("monk", lv, "ac-bonus") for lv in (4, 8, 12, 16, 20)] \
            == [1, 2, 3, 4, 5]
        assert classfeatures.rank("monk", 16, "ki-strike") == 4

    def test_a_real_punch_through_the_attack_op(self):
        """Through `Engine.run`, the path the table clicks: no -4 on the roll, the
        table's die on the damage."""
        monk = _monk(8)
        scene = Scene(location_id="5bbd0c40345f")
        scene.add(monk)
        scene.add(instantiate("thug", scene=scene, name="the thug"))
        engine = Engine(scene, Dice(seed=5))
        engine.run(engine.validate([{"op": "begin_encounter",
                                     "params": {"sides": {"you": ["pc"], "them": ["c1"]}}}]))
        face_to_face(scene)
        for _ in range(12):
            scene.turn = [r for r, _ in scene.initiative].index("pc")
            out = engine.run(engine.validate([{
                "op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
                "params": {"weapon": "unarmed"}, "because": "test"}])).outcomes[-1]
            if any(e.get("kind") == "damage" for e in out.effects):
                break
        else:
            pytest.fail("the monk never landed a punch in 12 swings")
        attack = out.rolls[0]
        assert attack.die == "1d20"
        assert not [m for m in attack.modifiers if "proficient" in m.source]
        assert any(r.die.startswith("1d10") for r in out.rolls[1:]), \
            [r.die for r in out.rolls]


# --- fighter --------------------------------------------------------------------------

class TestFighter:
    def test_armour_training_lifts_max_dex_and_lightens_the_penalty(self):
        """Full plate: max Dex +1, check penalty -6. CRB: "reduces the armor check
        penalty by 1 (to a minimum of 0) and increases the maximum Dexterity bonus
        allowed by his armor by 1", every four levels from 3rd."""
        dex18 = {"str": 16, "dex": 18, "con": 14, "int": 10, "wis": 10, "cha": 8}
        for level, dex, acp in ((2, 1, -6), (3, 2, -5), (7, 3, -4), (15, 4, -2)):
            f = _pc("fighter", level, armour="full plate", abilities=dex18)
            got = [m.value for m in f.ac_modifiers() if m.source == "Dex"]
            assert got == [dex], (level, got)
            assert f.armour_check_penalty == acp, level
        assert _pc("fighter", 15, armour="leather").armour_check_penalty == 0, \
            "to a minimum of 0, never a bonus"

    def test_armour_training_moves_at_full_speed(self):
        """Medium at 3rd, heavy at 7th."""
        assert _pc("fighter", 2, armour="breastplate").speed_feet == 20
        assert _pc("fighter", 3, armour="breastplate").speed_feet == 30
        assert _pc("fighter", 6, armour="full plate").speed_feet == 20
        assert _pc("fighter", 7, armour="full plate").speed_feet == 30

    def test_weapon_training_by_group_and_order(self):
        """First group +1 at 5th; at 9th a second at +1 and the first at +2. Read through
        `classfeatures.chosen` from `class_choices` — lane 1 writes it."""
        picks = {"weapon training": ["heavy blades", "bows"]}
        f5 = _pc("fighter", 5, class_choices=picks, weapons=["longsword", "longbow", "dagger"])
        f9 = _pc("fighter", 9, class_choices=picks, weapons=["longsword", "longbow", "dagger"])
        assert [m.value for m in _named(f5.attack_modifiers("longsword"), "weapon training")] \
            == [1]
        assert not _named(f5.attack_modifiers("longbow"), "weapon training"), \
            "the second pick is not paid for until 9th"
        assert [m.value for m in _named(f9.attack_modifiers("longsword"), "weapon training")] \
            == [2]
        assert [m.value for m in _named(f9.damage_modifiers("longsword"), "weapon training")] \
            == [2]
        assert [m.value for m in _named(f9.attack_modifiers("longbow"), "weapon training")] \
            == [1]
        assert not _named(f9.attack_modifiers("dagger"), "weapon training")
        assert not _named(_pc("fighter", 9).attack_modifiers("longsword"), "weapon training"), \
            "no pick, no bonus"

    def test_armour_mastery_only_in_armour(self):
        assert _pc("fighter", 19, armour="breastplate").damage_reduction("slashing").amount == 5
        assert _pc("fighter", 19).damage_reduction("slashing") is None
        assert _pc("fighter", 18, armour="breastplate").damage_reduction("slashing") is None

    def test_bravery_lands_only_on_a_save_that_says_fear(self):
        """A term whose condition the roll cannot evaluate is dropped, never applied."""
        f = _pc("fighter", 6)
        assert not _named(f.save_modifiers("will"), "bravery")
        assert [m.value for m in _named(f.save_modifiers("will", {"against": "fear"}),
                                        "bravery")] == [2]


# --- ranger and rogue -----------------------------------------------------------------

class TestRanger:
    def test_favoured_enemy_against_its_type_and_no_other(self):
        picks = {"favored enemy": [{"pick": "humanoid (orc)", "bonus": 4},
                                   {"pick": "undead"}]}
        r = _pc("ranger", 5, class_choices=picks)
        orc = _body("type.humanoid", "subtype.orc")
        dead = _body("type.undead")
        man = _body("type.humanoid", "subtype.human")
        assert _total(_named(r.attack_modifiers("longsword", defender=orc), "favored")) == 4
        assert _total(_named(r.damage_modifiers("longsword", defender=orc), "favored")) == 4
        assert _total(_named(r.attack_modifiers("longsword", defender=dead), "favored")) == 2
        assert not _named(r.attack_modifiers("longsword", defender=man), "favored")
        assert not _named(r.attack_modifiers("longsword"), "favored"), \
            "no target in the roll: the term is dropped"
        # At 1st only the first pick is paid for.
        r1 = _pc("ranger", 1, class_choices=picks)
        assert not _named(r1.attack_modifiers("longsword", defender=dead), "favored")

    def test_favoured_terrain_where_she_stands(self):
        r = _pc("ranger", 3, class_choices={"favoured terrain": ["forest"]})
        r.at = "5bbd0c40345f~forest:the-old-wood"
        assert [m.value for m in _named(r.initiative_modifiers(), "favored terrain")] == [2]
        r.at = "5bbd0c40345f~urban:the-square"
        assert not _named(r.initiative_modifiers(), "favored terrain")

    def test_a_rangers_evasion_works_in_medium_armour_and_a_rogues_does_not(self):
        assert classfeatures.evades(_pc("ranger", 9, armour="breastplate")) == "evasion"
        assert classfeatures.evades(_pc("rogue", 9, armour="breastplate")) == ""
        assert classfeatures.evades(_pc("rogue", 9, armour="leather")) == "evasion"


def test_trapfinding_on_disable_device():
    """"A rogue adds 1/2 her level ... to Disable Device skill checks (minimum +1)"."""
    for level, bonus in ((1, 1), (2, 1), (9, 4)):
        r = _pc("rogue", level, ranks={"disable device": 1})
        assert [m.value for m in _named(r.skill_modifiers("disable device"),
                                        "trapfinding")] == [bonus]


def test_a_blood_benders_fist_reads_its_own_column():
    """The class file printed a `fist` die from 1d6 to 2d10 and nothing read it: the
    bare fist was the table's 1d3 at every level."""
    assert _pc("blood bending", 8).damage_dice("unarmed") == "1d10"
    assert _pc("blood bending", 13).speed_feet == 50


# --- documents, sheet and API ---------------------------------------------------------

def test_every_shipped_class_feature_document_validates():
    """A document keyed by a slug the table never grants would be read by nothing — the
    exact defect this lane closes — so the validator refuses it with the fix named."""
    for cid in classes.all_classes():
        assert classfeatures.validate(cid) == [], cid
    bad = classfeatures.validate("barbarian", {"fast-movment": {"source": "x"}})
    assert bad and "grants nothing called 'fast-movment'" in bad[0]
    bad = classfeatures.validate("monk", {"ac-bonus": {
        "source": "x", "modifiers": [{"type": "combat_mod", "target": "ac",
                                      "formula": "wisdom + 1"}]}})
    assert bad and "nothing called 'wisdom'" in " ".join(bad)


def test_every_weapon_group_name_resolves_but_the_ones_the_table_lacks():
    """Group members are written by name and resolved through `key_for`; a name the
    weapon table does not carry is skipped, never matched to the nearest weapon."""
    missing = {n for names in weapons_mod.GROUPS.values() for n in names
               if not weapons_mod.key_for(n)}
    assert missing == {"katar"}, missing
    assert "heavy blades" in weapons_mod.groups_of("longsword")
    assert "monk" in weapons_mod.groups_of("unarmed")


def test_the_real_sheet_api_shows_the_numbers(client, tmp_path, settings):
    """`/api/sheet` — what the Sheet tab draws — for a level-10 monk."""
    settings.CAMPAIGN_DIR = str(tmp_path)
    from play import campaign as campaign_mod

    campaign_mod.begin_with(_monk(10))
    sheet = client.get("/api/sheet").json()
    d = sheet["defense"]
    assert d["speed"]["current"] == 60
    assert any("AC bonus" in t["source"] and t["value"] == 5 for t in d["ac"]["terms"])
    fist = next(a for a in sheet["offense"]["attacks"] if a["key"] == "unarmed")
    assert fist["damage_dice"] == "1d10" and fist["proficient"] is True
    assert not [t for t in fist["attack"]["terms"] if "proficient" in t["source"]]
    assert sheet["offense"]["cmb"]["total"] == 10 + 2


def test_nothing_is_stored_on_the_sheet():
    """Read live, never saved: the saved sheet of a level-20 monk carries no class
    number, so dropping a level drops the numbers."""
    m = _monk(20)
    saved = json.dumps(to_dict(m))
    assert "AC bonus" not in saved and "Perfect self" not in saved
    m.level = 3
    assert m.speed_feet == 40
    assert m.damage_reduction("bludgeoning") is None
