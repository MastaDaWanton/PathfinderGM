"""Non-lethal damage, and the class that spends it.

Non-lethal was a gap nothing had asked for until Blood Bending arrived. The class buys
every ability it has with self-inflicted damage — "for every +1 to a modifier take 2d6
non-lethal damage" — and before this the engine had one number for damage, so a Blood
Bender paying 2d6 for a bonus and a Blood Bender taking 2d6 from a sword ended the round
in identical trouble. They are not in identical trouble. One of them is winning.

The specific 1e behaviours recorded here, each of which was wrong or absent:

  - it accumulates on its own rather than coming off hit points;
  - at your current hit points you are staggered, past them unconscious — and unconscious,
    *not* dying, so nothing rolls stabilisation checks for a bruise;
  - curing hit point damage removes an equal amount of non-lethal;
  - a night clears it.

The class half of the file exists because a class file the engine never reads is the
failure `docs/homebrew-rules.md` section 1 is about. Every number here was checked against
the author's PDF, which is the trustworthy source: the .docx table arrived with its columns
shuffled row by row, and by 8th level the iterative-attack notation had migrated into the
Fortitude column.
"""
from __future__ import annotations

import pytest

from rules import classes
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import IllegalSheet, from_dict, load_pc, to_dict, validate

# The author's PDF table, typed once so the tests below compare against the source rather
# than against whatever the code currently produces.
PDF_FORT = [3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13]
PDF_REF = [2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12]
PDF_WILL = [1, 2, 2, 3, 4, 5, 5, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11]
# Was the PDF's own three-quarter column ([0, 1, 2, 3, 3, …]); superseded 2026-08-24 by
# the user's chart, which is the standard full progression. test_leveling holds the
# twenty-row iterative check against that chart.
PDF_BAB = list(range(1, 21))


@pytest.fixture
def pc():
    a = load_pc("fixtures/pc-kesst.json")
    a.hp_max, a.hp = 40, 40
    return a


def bender(level: int = 6, con: int = 16):
    """A Blood Bender built the way the app builds one — through `from_dict`, so the
    class actually applies rather than being poked onto the sheet by the test."""
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"], d["level"] = "blood bending", level
    d["abilities"]["con"] = con
    d["hp_max"] = d["hp"] = 40
    # Kesst's own ranks are a 3rd-level character's and `validate` rightly refuses them on
    # a 1st-level sheet. Skills are not what any test in this file is about.
    d["ranks"] = {}
    return from_dict(d, ref="pc")


# --- non-lethal damage is its own number ---------------------------------------------------

def test_nonlethal_does_not_come_off_hit_points(pc):
    """The defect this whole file exists for: subtracting non-lethal from `hp` made
    paying for an ability and being stabbed the same event."""
    pc.take_nonlethal(12)
    assert pc.hp == 40
    assert pc.nonlethal == 12


def test_damage_declared_nonlethal_lands_as_nonlethal(pc):
    hit = pc.take_damage(9, lethality="nonlethal")
    assert hit["lethality"] == "nonlethal"
    assert pc.hp == 40 and pc.nonlethal == 9


def test_lethal_is_still_the_default(pc):
    """Nothing that already called `take_damage` should have changed meaning."""
    pc.take_damage(9)
    assert pc.hp == 31 and pc.nonlethal == 0


def test_the_two_accumulate_side_by_side(pc):
    pc.take_damage(10)
    pc.take_damage(10, lethality="nonlethal")
    assert (pc.hp, pc.nonlethal) == (30, 10)


# --- the threshold ---------------------------------------------------------------------------

def test_staggered_when_it_equals_current_hit_points(pc):
    """1e: "you are staggered" at exactly your current hit points — not unconscious."""
    pc.hp = 12
    pc.take_nonlethal(12)
    pc.apply_nonlethal_state()
    assert pc.has_condition("staggered")
    assert not pc.has_condition("unconscious")


def test_unconscious_when_it_passes_them(pc):
    pc.hp = 12
    pc.take_nonlethal(13)
    pc.apply_nonlethal_state()
    assert pc.has_condition("unconscious")
    assert not pc.has_condition("staggered")


def test_beaten_senseless_is_not_dying(pc):
    """Somebody knocked out with a sap is not bleeding out. Treating the two alike had the
    engine rolling a stabilisation check every round for a bruise."""
    pc.hp = 12
    pc.take_nonlethal(30)
    pc.apply_nonlethal_state()
    assert pc.has_condition("unconscious")
    assert not pc.has_condition("dying")
    assert pc.hp == 12


def test_the_threshold_follows_hit_points_down(pc):
    """Non-lethal that was survivable stops being survivable when you get wounded — the
    threshold is *current* hit points, not maximum."""
    pc.take_nonlethal(20)
    pc.apply_nonlethal_state()
    assert not pc.has_condition("unconscious")

    pc.take_damage(25)                                  # 40 -> 15, under the 20 already taken
    pc.apply_nonlethal_state()
    assert pc.has_condition("unconscious")


def test_healing_lifts_the_condition_it_caused(pc):
    pc.hp = 12
    pc.take_nonlethal(20)
    pc.apply_nonlethal_state()
    assert pc.has_condition("unconscious")

    pc.heal_nonlethal(20)
    pc.apply_nonlethal_state()
    assert not pc.has_condition("unconscious")


def test_healing_does_not_lift_an_unconsciousness_it_did_not_cause(pc):
    """Only the condition non-lethal damage put there. Clearing a sleep spell because a
    potion cured a bruise would be a cure for anything."""
    pc.add_condition("unconscious", source="sleep")
    pc.take_nonlethal(5)
    pc.heal_nonlethal(5)
    pc.apply_nonlethal_state()
    assert pc.has_condition("unconscious")


# --- healing and rest -------------------------------------------------------------------------

def test_curing_hit_points_removes_equal_nonlethal(pc):
    """1e, and easy to miss: a character healed to full otherwise still lies there
    unconscious from the beating."""
    pc.hp = 30
    pc.take_nonlethal(8)
    pc.heal(6)
    assert pc.hp == 36 and pc.nonlethal == 2


def test_healing_cannot_drive_nonlethal_below_zero(pc):
    pc.hp = 39
    pc.take_nonlethal(2)
    pc.heal(20)
    assert pc.nonlethal == 0


def test_a_night_clears_it(pc):
    """"1 hit point per hour per character level" — eight hours clears anything a
    character could still be standing under, so a night wipes it rather than pretending
    to count."""
    pc.take_nonlethal(25)
    out = pc.rest("night")
    assert pc.nonlethal == 0
    assert out["nonlethal_healed"] == 25


def test_it_survives_a_save(pc):
    pc.take_nonlethal(7)
    assert from_dict(to_dict(pc)).nonlethal == 7


def test_the_sheet_shows_it_with_the_line_it_is_measured_against(pc):
    """The number alone tells the player nothing. 12 non-lethal is fine at 40 hit points
    and is a knockout at 11."""
    pc.hp = 20
    pc.take_nonlethal(12)
    shown = pc.summary()
    assert shown["nonlethal"] == 12
    assert shown["nonlethal_threshold"] == 20


def test_the_defense_tab_carries_the_threshold_too():
    """The Defense tab used to print "Unconscious at 0" and nothing else, which is the
    wrong line for non-lethal and badly wrong for a Blood Bender — this one is knocked out
    at 58, eighteen points of it wards."""
    from rules.sheet import full_sheet

    b = bender()
    b.gain_temp_hp(10, source="blood sponge")
    b.gain_temp_hp(8, source="crimson guard")
    b.take_nonlethal(31)

    hp = full_sheet(b)["defense"]["hp"]
    assert hp["nonlethal"] == 31
    assert hp["nonlethal_threshold"] == 58                # 40 hp + 18 stacked temp


def test_the_side_panel_carries_the_pools():
    """A spendable resource nobody can see is a resource that does not exist. Rage and ki
    were computed correctly and rendered nowhere for as long as pools have existed."""
    shown = {p["id"]: p for p in bender().summary()["pools"]}
    assert shown["rage"]["max"] == 17
    assert shown["ki"]["max"] == 6
    assert set(shown["ki"]) >= {"id", "current", "max", "ready", "cooldown_left"}


# --- through the engine -------------------------------------------------------------------------

def test_the_engine_can_declare_a_packet_nonlethal():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    e = Engine(s, Dice(seed=42))
    thug = s.actors["c1"]
    before = thug.hp

    res = e.run(e.validate([
        {"op": "damage", "actor": "pc", "because": "the pommel, not the edge",
         "params": {"to": "c1", "amount": 4, "type": "bludgeoning",
                    "lethality": "nonlethal"}},
    ]))
    assert thug.hp == before
    assert thug.nonlethal == 4
    assert "non-lethal" in res.outcomes[0].tell


# --- Blood Bond: the two rules the class is exempted from -----------------------------------------

def test_blood_bond_makes_temp_hit_points_stack():
    """1e says the best applies and adding them is wrong. Blood Bending is the exception,
    from 1st level, because hit points are its currency — a Coagulator layering Blood
    Sponge over a ward is the path working as written."""
    b = bender()
    b.gain_temp_hp(10, source="blood sponge")
    b.gain_temp_hp(8, source="crimson guard")
    assert b.temp_hp == 18


def test_everybody_else_still_takes_the_best_one(pc):
    """The exemption has to be the class's, not a rule change. If this test ever passes
    with 18 the override has leaked onto every character in the game."""
    pc.gain_temp_hp(10, source="aid")
    pc.gain_temp_hp(8, source="a potion")
    assert pc.temp_hp == 10


def test_blood_bond_counts_temp_hit_points_before_dropping_you():
    """"Non-Lethal damage does not knock you unconscious until it is equal to your current
    health + your temporary health." The other half of the same idea: without it the class
    knocks itself out paying for its own abilities."""
    b = bender()
    b.hp = 20
    b.gain_temp_hp(15, source="blood sponge")
    assert b.nonlethal_threshold == 35

    b.take_nonlethal(30)
    b.apply_nonlethal_state()
    assert not b.has_condition("unconscious")


def test_without_the_exemption_temp_hit_points_do_not_raise_the_line(pc):
    pc.hp = 20
    pc.gain_temp_hp(15, source="aid")
    assert pc.nonlethal_threshold == 20


def test_an_override_naming_a_rule_that_does_not_exist_is_reported():
    """The reason `ACTOR_RULES` is a list at all. A class file saying `temp_hp_stacks`
    where it meant `temp_hp.stacks` would otherwise grant a feature that silently never
    happens, and the only symptom would be a Coagulator whose wards quietly stop adding
    up nine levels in."""
    a = load_pc("fixtures/pc-kesst.json")
    a.char_class = "wobbler"
    classes.all_classes()["wobbler"] = {
        "name": "Wobbler", "bab": "half",
        "overrides": [{"rule": "temp_hp_stacks", "from_level": 1}],
    }
    try:
        out = classes.apply(a)
        assert out["unknown_rules"] == ["temp_hp_stacks"]
        assert "temp_hp_stacks" not in a.overrides
    finally:
        classes.all_classes().pop("wobbler", None)


# --- the class table -------------------------------------------------------------------------------

def test_blood_bending_is_a_legal_class_to_build():
    validate(bender(level=1))


def test_two_hit_dice_per_level():
    """The author's, and unique in 1e — every other class has one, so "per Hit Die" and
    "per level" are the same number everywhere else and are not here. Mighty Blood Rage
    grants temporary hit points per Hit Die, and reading this as level halves the class."""
    b = bender(level=6)
    assert b.hit_dice_per_level == 2
    assert b.hit_dice == 12
    assert classes.get("blood bending")["hit_die"] == "2d8"


def test_the_bab_column_is_the_pdfs():
    b = bender()
    for level in range(1, 21):
        b.level = level
        assert b.bab == PDF_BAB[level - 1], f"BAB wrong at level {level}"


def test_every_save_at_every_level_matches_the_pdf():
    """60 numbers. Typed out because the source table is what is being tested — a test
    that recomputed them from the same code would agree with any bug."""
    cls = classes.get("blood bending")
    for level in range(1, 21):
        assert classes.save_base(cls, "fort", level) == PDF_FORT[level - 1]
        assert classes.save_base(cls, "ref", level) == PDF_REF[level - 1]
        assert classes.save_base(cls, "will", level) == PDF_WILL[level - 1]


def test_the_will_column_is_stored_and_not_derived():
    """It matches good-1 at levels 1-4 and from 8 up, but the PDF prints 4, 5, 5 at 5th,
    6th and 7th where good-1 gives 3, 4, 4. Deriving this column would mean inventing
    three of its numbers, so it is typed. This test is what fails if somebody later
    "tidies" it into a named track."""
    cls = classes.get("blood bending")
    assert isinstance(cls["saves"]["will"], (list, tuple))
    assert [classes.save_base(cls, "will", lv) for lv in (5, 6, 7)] == [4, 5, 5]


def test_fortitude_is_derived_because_it_actually_is_regular():
    assert classes.get("blood bending")["saves"]["fort"] == "good_plus_1"


def test_the_core_four_still_use_good_saves():
    """The new per-save spec is additive. A fighter has no `saves` map and must keep
    working off `good_saves` exactly as before."""
    f = load_pc("fixtures/pc-kesst.json")
    f.char_class, f.level = "fighter", 6
    assert classes.save_base(classes.get("fighter"), "fort", 6) is None
    assert sum(m.value for m in f.save_modifiers("fort")) >= 5


def test_the_level_table_row_carries_both_damage_columns():
    """Fist and blood damage scale on their own tracks and diverge — 2d6 and 4d10 at 13th."""
    assert classes.table_at("blood bending", 13)["fist"] == "2d6"
    assert classes.table_at("blood bending", 13)["blood"] == "4d10"


def test_features_accumulate_rather_than_replace():
    got = classes.features_at("blood bending", 4)
    assert "blood bond" in got                          # granted at 1st, still there at 4th
    assert "rapid coagulation" in got                   # granted at 4th
    assert "improved evasion" not in got                # not until 12th


# --- what the class grants on load ------------------------------------------------------------------

def test_a_bender_arrives_with_their_pools_filled():
    """Rage is "4 + Con modifier rounds per day, +2 for each level after 1st"."""
    b = bender(level=6, con=16)
    assert b.pool("rage").maximum == 17                 # 4 + 3 + 2*5
    assert b.pool("ki").maximum == 6                    # floor(6/2) + 3
    assert b.pool("unbalancing strike").maximum == 4    # floor(6/4) + 3


def test_a_pool_not_yet_earned_is_not_there():
    """Stunning Strike arrives at 13th. A 6th-level character holding it is an ability the
    player will try to use."""
    assert bender(level=6).pool("stunning strike") is None
    assert bender(level=13).pool("stunning strike") is not None


def test_reloading_does_not_refill_a_spent_pool():
    """`apply` runs on every load so a corrected formula reaches a character already in
    play. That is only safe if it recomputes the maximum and leaves the current value
    alone — otherwise saving and loading is a free night's rest."""
    b = bender()
    b.spend_pool("rage", 10)
    back = from_dict(to_dict(b), ref="pc")
    assert back.pool("rage").current == 7
    assert back.pool("rage").maximum == 17


def test_a_level_up_recomputes_the_maximum():
    assert bender(level=6).pool("rage").maximum == 17
    assert bender(level=10).pool("rage").maximum == 25   # 4 + 3 + 2*9


def test_the_overrides_arrive_with_the_class_and_not_by_hand():
    """Nothing in the app pokes these onto a sheet. If the class file stops being read,
    this is what says so."""
    b = bender(level=1)
    assert b.allows("temp_hp.stacks")
    assert b.allows("nonlethal.counts_temp_hp")


def test_an_unknown_class_is_still_refused():
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = "blud bending"
    with pytest.raises(IllegalSheet, match="unknown class"):
        from_dict(d, ref="pc")
