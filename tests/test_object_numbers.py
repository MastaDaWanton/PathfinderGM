"""An object's hardness and hit points: the book's Table 7-12 row, then its materials.

The owner, 2026-10-07: "use the book but only as a base — the materials used when smithing
should change that if they say so." Measured before the change (this branch's first run):

  * every steel weapon, suit and buckler had 30 hit points — one inch of steel, Table 7-13
    — so a longsword (the book: 5) took 15 hours to mend from just broken, 16 from worse;
  * a +1 longsword had hardness 10 and 30 hit points: the enhancement added nothing;
  * a forged adamantine longsword read hardness 29 and 51 hit points, the book's 20 and 6:
    the old branch took Table 7-13's adamantine (20, 40 an inch) and then added the
    material document's +10 / +10, which is already the step from steel — counted twice;
    a forged mithral one read 19 for the book's 15;
  * a heavy steel shield read as wood (hardness 5, 10 hit points; the book: 10 and 20),
    because the name hint "shield" said wood.

Every row below was read from the Core Rulebook PDF on 2026-10-07: Table 7-12 (p.175),
Table 7-13 (p.175), "Magic Armor, Shields, and Weapons" (p.174), Special Materials
(pp.154-155).
"""
from __future__ import annotations

import re

import pytest

from rules import forge_items, object_numbers, tradecraft
from rules.object_numbers import numbers
from rules.sheet import from_dict, load_pc, to_dict

from tests.test_trade_uses import _run, _table


# --- the book's base ---------------------------------------------------------------------

@pytest.mark.parametrize("name,hardness,hp", [
    ("dagger", 10, 2),                    # light blade
    ("longsword", 10, 5),                 # one-handed blade
    ("greatsword", 10, 10),               # two-handed blade
    ("spiked gauntlet", 10, 10),          # light metal-hafted (all metal, no wooden haft)
    ("light mace", 5, 2),                 # light hafted: an ash haft (base-pieces.json)
    ("battleaxe", 5, 5),                  # one-handed hafted
    ("quarterstaff", 5, 10),              # two-handed hafted
    ("longbow", 5, 5),                    # projectile weapon
    ("light crossbow", 5, 5),
    ("chain shirt", 10, 20),              # armour: bonus 4 x 5, steel's hardness
    ("full plate", 10, 45),
    ("leather armour", 2, 10),            # leather's hardness 2 (Table 7-13)
    ("buckler", 10, 5),
    ("light wooden shield", 5, 7),
    ("heavy wooden shield", 5, 15),
    ("light steel shield", 10, 10),
    ("heavy steel shield", 10, 20),       # was wood, 5 and 10
    ("tower shield", 5, 20),
])
def test_weapons_armour_and_shields_take_table_7_12(name, hardness, hp):
    got = numbers(name)
    assert (got.hardness, got.hp_max) == (hardness, hp), got.why


def test_what_the_table_has_no_row_for_keeps_an_inch_of_its_material():
    """Table 7-13, as before: a cloak is cloth, a whip leather, a ring iron."""
    assert (numbers("silk cloak").hardness, numbers("silk cloak").hp_max) == (0, 2)
    assert (numbers("whip").hardness, numbers("whip").hp_max) == (2, 5)


# --- what it is made of, when its documents say so ----------------------------------------

def test_an_adamantine_longsword_is_hardness_20_and_a_third_more_hit_points():
    """CRB p.154: 'Weapons and armor normally made of steel that are made of adamantine
    have one-third more hit points than normal ... hardness 20.' 5 x 4/3 = 6.67, rounded
    toward zero as every forge number is: 6. Full plate's 45 becomes 60."""
    got = numbers("adamantine longsword")
    assert (got.hardness, got.hp_max, got.material) == (20, 6, "adamantine")
    assert numbers("adamantine full plate").hp_max == 60


def test_mithral_is_hardness_15_and_cold_iron_and_darkwood_are_the_book_unchanged():
    """CRB pp.154-155: mithral hardness 15, 30 an inch; cold iron 10 and 30 (steel's);
    darkwood 5 and 10 (wood's). Only mithral's document carries a book hardness."""
    assert (numbers("mithral longsword").hardness, numbers("mithral longsword").hp_max) \
        == (15, 5)
    assert (numbers("cold iron longsword").hardness, numbers("cold iron longsword").hp_max) \
        == (10, 5)
    assert (numbers("darkwood quarterstaff").hardness,
            numbers("darkwood quarterstaff").hp_max) == (5, 10)


def test_each_plus_one_adds_two_hardness_and_ten_hit_points():
    """CRB p.174. Before: a +1 longsword was 10 and 30, the same as a plain one."""
    assert (numbers("+1 longsword").hardness, numbers("+1 longsword").hp_max) == (12, 15)
    assert (numbers("+2 heavy steel shield").hardness,
            numbers("+2 heavy steel shield").hp_max) == (14, 40)
    assert (numbers("+1 adamantine longsword").hardness,
            numbers("+1 adamantine longsword").hp_max) == (22, 16)


def _forged(head, *, flaws=(), magic=None, gear="weapon", base="longsword"):
    rec = {"id": f"forged-{head}", "name": f"forged {head} {base}", "gear": gear,
           "base": base, "pieces": {("head" if gear == "weapon" else "body"): head},
           "quality_index": 2, "smith": {"level": 1, "perks": {}}, "flaws": list(flaws)}
    if magic:
        rec["magic"] = magic
    return rec


def test_a_forged_adamantine_longsword_is_no_longer_counted_twice():
    """Was hardness 29, 51 hit points: Table 7-13's adamantine plus the document's step
    from steel. The head alone carries only its book numbers: 20 and 6."""
    got = numbers("forged adamantine longsword", _forged("adamantine"))
    assert (got.hardness, got.hp_max) == (20, 6)


def test_the_forge_moves_the_book_when_its_documents_say_so():
    """A brittle flaw is −1 hardness (forge_items.FLAWS); steel's house +2 hardness and
    −2 an inch reach the blade; a +1 layer adds the book's +2 and +10."""
    assert numbers("x", _forged("adamantine", flaws=["brittle"])).hardness == 19
    steel = numbers("x", _forged("steel"))
    assert (steel.hardness, steel.hp_max) == (12, 5)     # −2/30 of 5 rounds to 0
    magic = numbers("x", _forged("steel", magic={"enhancement": 1}))
    assert (magic.hardness, magic.hp_max) == (14, 15)
    plate = numbers("x", _forged("mithral", gear="armour", base="chain shirt"))
    assert plate.hardness == 15                          # steel 10, mithral's +5, once


def test_the_documents_are_written_as_steps_from_steel():
    """`DOCUMENT_BASE_HP_PER_INCH` is steel's 30 because every document that states an
    absolute figure in its note gets there from steel: inubrix −20 is '10 hit points per
    inch', singing steel −10 '20', gold −5 'hardness 5', bronze armour −1 'hardness 9'."""
    import json
    from pathlib import Path

    from django.conf import settings

    path = Path(settings.BASE_DIR) / "content" / "materials" / "blacksmith-materials.json"
    checked = 0
    for doc in json.loads(path.read_text(encoding="utf-8"))["materials"]:
        for gear in ("weapon", "armour", "shield"):
            for eff in doc.get(gear) or ():
                note = str(eff.get("note") or "")
                if eff.get("type") != "gear_mod":
                    continue
                said = (re.search(r"hardness (\d+)", note) if eff["target"] == "hardness"
                        else re.search(r"(\d+) hit points per inch", note))
                if not said:
                    continue
                base = 10 if eff["target"] == "hardness" else \
                    object_numbers.DOCUMENT_BASE_HP_PER_INCH
                assert base + int(eff["amount"]) == int(said.group(1)), (doc["id"], eff)
                checked += 1
    assert checked >= 5


# --- the doors that use it ---------------------------------------------------------------

def test_a_broken_longsword_mends_in_three_hours_not_sixteen():
    """Hardness 10, 5 hit points: 13 damage leaves 2 (broken). An hour a point is 3
    hours. Under the inch-of-steel rule the same sword was 30 hit points and 15-16 hours."""
    s, e, pc = _table()
    pc.weapons.append("longsword")
    res = pc.damage_item("longsword", 13, "slashing")
    assert (res["hp"], res["hp_max"], pc.gear["longsword"].broken) == (2, 5, True)
    before = s.clock_minutes
    out = _run(e, {"op": "mend", "params": {"item": "longsword"}}, 15)
    assert s.clock_minutes - before == 3 * 60
    assert "whole again — 5 of 5 hit points, no longer broken" in out.tell


def test_judging_a_longsword_names_its_row():
    s, e, pc = _table()
    pc.weapons.append("longsword")
    out = _run(e, {"op": "judge", "params": {"item": "longsword"}}, 18)
    assert ("Hardness 10, 5 of 5 hit points; sound — a one-handed blade "
            "(CRB Table 7-12).") in out.tell
    assert "longsword" not in pc.gear, "a look mints no record"


def test_an_old_save_is_re_read_with_its_state_kept():
    """A save from the inch-of-steel rule: a longsword at 14 of 30 (broken), a dagger at
    29 of 30 (scratched), a greatsword ruined, a buckler whole. Proportion, rounded down,
    with broken kept broken and sound kept sound where the new maximum has room."""
    pc = load_pc("fixtures/pc-thessaly.json")
    data = to_dict(pc)
    data["gear"] = {
        "longsword": {"name": "longsword", "material": "steel", "hardness": 10,
                      "hp": 14, "hp_max": 30},
        "greatsword": {"name": "greatsword", "material": "steel", "hardness": 10,
                       "hp": 22, "hp_max": 30},
        "dagger": {"name": "dagger", "material": "steel", "hardness": 10,
                   "hp": 29, "hp_max": 30},
        "full plate": {"name": "full plate", "material": "steel", "hardness": 10,
                       "hp": 0, "hp_max": 30},
        "buckler": {"name": "buckler", "material": "steel", "hardness": 10,
                    "hp": 30, "hp_max": 30},
    }
    back = from_dict(data)
    g = back.gear
    assert (g["longsword"].hp, g["longsword"].hp_max, g["longsword"].broken) == (2, 5, True)
    assert (g["greatsword"].hp, g["greatsword"].hp_max, g["greatsword"].broken) \
        == (7, 10, False)
    # 2 hit points have no 'scratched but sound': 1 is broken, so it comes back whole.
    assert (g["dagger"].hp, g["dagger"].hp_max) == (2, 2)
    assert (g["full plate"].hp, g["full plate"].hp_max, g["full plate"].destroyed) \
        == (0, 45, True)
    assert (g["buckler"].hp, g["buckler"].hp_max) == (5, 5)
    # And it is stable: a second load moves nothing.
    again = from_dict(to_dict(back)).gear
    assert {k: (v.hp, v.hp_max) for k, v in again.items()} == \
        {k: (v.hp, v.hp_max) for k, v in g.items()}


def test_a_sunder_meets_the_books_numbers():
    """The sunder op asks `Actor.item`, so a club blow of 13 against a longsword takes 3
    off its 5 (hardness 10) and breaks it, where it used to leave 27 of 30 sound."""
    pc = load_pc("fixtures/pc-thessaly.json")
    res = pc.damage_item("longsword", 13, "bludgeoning")
    assert (res["taken"], res["hp"], res["hp_max"], res["broken"]) == (3, 2, 5, True)


def test_the_judge_and_mend_doors_and_sunder_all_read_the_one_reader(monkeypatch):
    """No second table: `Actor.item` (sunder, acid, mend) and `tradecraft.damage_of` (the
    judge, the Equipment chip) both take whatever `object_numbers` answers, and the old
    forged branch is gone. Asked by behaviour: the reader is replaced, and both follow."""
    from rules import sheet

    odd = object_numbers.Numbers(hardness=7, hp_max=13, material="bone", row="test")
    monkeypatch.setattr(object_numbers, "numbers", lambda name, record=None: odd)
    pc = load_pc("fixtures/pc-thessaly.json")
    made = pc.item("longsword")
    assert (made.hardness, made.hp_max, made.material) == (7, 13, "bone")
    made.hp_max, made.hp = 99, 50                    # a stale record...
    again = tradecraft.damage_of(pc, "longsword")
    assert (again.hardness, again.hp_max) == (7, 13)  # ...is re-read, not trusted
    assert not hasattr(sheet.Actor, "_forged_item")
    assert forge_items.build(_forged("steel"))["gear"]["hardness"] != 0   # the input is live
