"""The material tag (enchanting plan §16, contracts §3.3, lane B), on the real tables and
material documents.

Before it, metal was two name lists in rules/armour.py (`METAL_ARMOUR`, `METAL_SHIELDS`):
a forged shield was metal by its base's name whatever it was made of, a forged noqual
breastplate was metal only because "breastplate" was listed, and no weapon could say what it
was made of at all.
"""
from __future__ import annotations

import pytest

from rules import armour as armour_mod
from rules import forge_items, item_tags, materials, states
from rules import weapons as weapons_mod
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.tables import ARMOUR, SHIELDS

METAL = states.METAL


def worn_by(armour="none", shield="none", suit=None, arm=None):
    """A thug wearing the table keys, with the records in the armour and shield slots."""
    s = Scene(location_id=None)
    who = instantiate("thug", scene=s, name="who")
    who.flat_ac = None
    who.armour, who.shield = armour, shield
    for slot, rec in (("armor", suit), ("shield", arm)):
        if rec is not None:
            who.worn[rec["id"]] = rec
            who.slots[slot] = [rec["id"]]
    return who


def test_the_name_lists_are_gone_and_the_question_is_the_tag():
    """`wears_metal` is asked of `item_tags`, never of a list of names; a second copy of
    "which suits are metal" is the copy nobody updates."""
    assert not hasattr(armour_mod, "METAL_ARMOUR") and not hasattr(armour_mod, "METAL_SHIELDS")


def test_a_darkwood_shield_is_not_metal_and_a_forged_noqual_breastplate_is():
    """Plan §21.1's pin. A wooden shield's body is wood whoever made it; a forged noqual
    breastplate is metal because noqual's `kind` is metal, not because "breastplate" was on
    a list."""
    darkwood = forge_items.record_for_base("heavy wooden shield", gear="shield",
                                           pieces={"body": "darkwood"}, item_id="dw")
    noqual = {"id": "nq", "name": "Noqual breastplate", "gear": "armour",
              "base": "breastplate", "slot": "armor", "quality_index": 3,
              "pieces": {"body": {"material": "noqual", "passes": 0}}}
    assert not item_tags.has_material(darkwood, METAL)
    assert item_tags.has_material(noqual, METAL)
    assert item_tags.main_material(noqual) == "noqual"
    assert not armour_mod.wears_metal(worn_by(shield="heavy wooden shield", arm=darkwood))
    assert armour_mod.wears_metal(worn_by(armour="breastplate", suit=noqual))


def test_a_forged_shield_is_what_it_was_made_of_not_what_its_base_is_called():
    """The old list called every "heavy shield" metal. A forged one is: its body is steel
    or mithral. The wooden base with a forged darkwood body is not."""
    mithral = {"id": "ms", "name": "Mithral shield", "gear": "shield", "base": "heavy shield",
               "slot": "shield", "quality_index": 3,
               "pieces": {"body": {"material": "mithral", "passes": 0}}}
    assert armour_mod.wears_metal(worn_by(shield="heavy shield", arm=mithral))
    assert "material.metal.mithral" in item_tags.material_tags(mithral)


@pytest.mark.parametrize("key,metal", [
    ("chainmail", True), ("studded leather", True), ("full plate", True),
    ("padded", False), ("leather", False), ("hide armour", False),
])
def test_the_tables_suits_answer_as_the_book_makes_them(key, metal):
    """CRB Table 6-6 and the druid's "padded, leather, or hide": the same answers the name
    list gave, now from what each suit is made of (studded leather by its steel studs)."""
    assert armour_mod.wears_metal(worn_by(armour=key)) is metal


@pytest.mark.parametrize("key,metal", [
    ("buckler", True), ("light shield", True), ("heavy shield", True),
    ("light wooden shield", False), ("heavy wooden shield", False), ("tower shield", False),
])
def test_the_tables_shields_answer_as_the_book_makes_them(key, metal):
    assert armour_mod.wears_metal(worn_by(shield=key)) is metal


def test_a_tanners_studded_leather_is_metal_by_its_studs_and_plain_leather_is_not():
    """Leatherworking: studded leather's studs are a metal fitting, so the druid's rule
    reads the studs (`steel-studs` -> steel), never the word "studded"."""
    studded = {"id": "sl", "name": "Wolf studded leather", "armour": "studded leather",
               "from_materials": ["wolf-pelt", "steel-studs", "sinew-thread"]}
    plain = {"id": "pl", "name": "Wolf leather", "armour": "leather",
             "from_materials": ["wolf-pelt", "sinew-thread"]}
    assert item_tags.has_material(studded, METAL)
    assert "material.metal.steel" in item_tags.material_tags(studded)
    assert item_tags.main_material(studded) == "wolf-pelt"
    assert not item_tags.has_material(plain, METAL)
    assert armour_mod.wears_metal(worn_by(armour="studded leather", suit=studded))
    assert not armour_mod.wears_metal(worn_by(armour="leather", suit=plain))


def test_weapons_say_what_they_are_made_of():
    """Shocking grasp and heat metal ask a WEAPON too ("carrying a metal weapon"); before
    this no weapon could answer. A club and a longbow are wood, a longsword steel, a fist
    nothing at all."""
    assert not item_tags.has_material("club", METAL)
    assert item_tags.has_material("club", "material.wood")
    assert not item_tags.has_material("longbow", METAL)
    assert item_tags.has_material("longsword", "material.metal.steel")
    assert item_tags.material_tags("unarmed") == ()


def test_ironwood_is_wood_and_silver_clasps_are_metal_whatever_the_names_say():
    """Never from a name: ironwood is the druid's wooden metal, and a name rule would
    have called it iron."""
    assert item_tags.substance_of("ironwood-haft") == "wood"
    assert item_tags.substance_of("silver-clasps") == "metal"
    assert item_tags.root_material("silver-clasps") == "silver"


def test_a_prefix_is_a_dot_boundary_never_a_substring():
    """Law 1's `matches`: "material.metal.cold" must not answer for cold iron."""
    rec = {"id": "x", "gear": "weapon", "base": "longsword",
           "pieces": {"head": {"material": "cold-iron"}}}
    assert item_tags.has_material(rec, "material.metal.cold-iron")
    assert not item_tags.has_material(rec, "material.metal.cold")
    assert item_tags.has_material(rec, "material.main.cold-iron")


def test_something_that_cannot_say_is_never_guessed_metal():
    """A catalogue ring by name, an unknown word: no tags, so a clause asking "metal?"
    is answered no, as every unevaluable clause is dropped."""
    assert item_tags.material_tags("Ring of Protection +1") == ()
    assert item_tags.material_tags("a stern look") == ()
    assert item_tags.material_tags({"id": "tea", "name": "Tea"}) == ()


def test_a_stat_block_with_a_printed_ac_wears_nothing_this_can_read():
    s = Scene(location_id=None)
    who = instantiate("thug", scene=s, name="who")
    who.flat_ac = 15
    who.armour = "chainmail"
    assert not armour_mod.wears_metal(who)


# --- the data file is whole ---------------------------------------------------------------------

def test_every_table_weapon_suit_and_shield_has_pieces():
    """A weapon added to the table with no row and no group would answer nothing to "is
    it metal". Every one resolves (a row, a group, a section or the default), and every
    suit and shield of Table 6-6 has its own row."""
    missing = [k for k in weapons_mod.all_weapons() if item_tags.default_pieces(k, "weapon")
               is None]
    assert missing == []
    data = item_tags.table()
    assert set(data["armour"]) == set(ARMOUR) - {"none"}
    assert set(data["shields"]) == set(SHIELDS) - {"none"}


def test_every_material_the_data_names_has_a_substance():
    """Each id in base-pieces.json is a catalogue material or a `substances` row; a typo
    would silently tag nothing. The fix: add the id to `substances` with what it is."""
    data = item_tags.table()
    rows = list(data["armour"].values()) + list(data["shields"].values())
    w = data["weapons"]
    rows += [w["default"]] + [r for _, r in w["by_group"]] + list(w["by_section"].values())
    rows += list(w["rows"].values())
    bad = sorted({mid for row in rows for mid in row.values()
                  if not item_tags.substance_of(mid)})
    assert bad == [], f"no substance for {bad}: add them to base-pieces.json `substances`"
    subs = {r["substance"] for r in data["substances"].values()} | set(data["kinds"].values())
    assert subs <= set(states.SUBSTANCES)


def test_every_piece_a_smith_or_tanner_can_fit_has_a_substance():
    """Every metal, alloy and fitting the forge offers for a piece, and every hide and
    fitting at the tannery, answers what it is — a new fitting with no `material` link and
    no `substances` row fails here with the fix named, not silently in a druid's armour."""
    shelf = materials.all()
    pieceable = [mid for mid, d in shelf.items()
                 if d["kind"] in ("metal", "alloy", "fitting", "hide")
                 and (d["kind"] == "hide" or any(d["pieces"].get(g) for g in d["pieces"])
                      or d["kind"] == "fitting")]
    bad = sorted(mid for mid in pieceable if not item_tags.substance_of(mid))
    assert bad == [], f"no substance for {bad}: give it a `material` link or a `substances` row"
