"""Stage 8b: a feat's number comes from a document, through the funnel a ring uses.

What the recon measured (docs/stage-8-plan.md, "What the maps corrected"): the
hand-written table in rules/tables.py held sixteen feats; fourteen were applied by bare
`Modifier`s appended inside the sheet's builders — untyped (Dodge's `dodge` sat in the
table and was dropped at the append), never through `_buff_mods`, never removable by
removing an effect — and two (Toughness, Point-Blank Shot) were read by nothing while the
sheet page printed "bonus hit points" for a feat that added none.

Now content/feats/mechanics/*.json carries the documents, `rules.feats.document`
resolves a sheet string to one, and `Actor._feat_mods` reads them live inside
`_buff_mods` the way worn gear is read off the slots. Nothing is saved; the feat list is
the store.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from rules import classbuilder, feats
from rules.sheet import from_dict, load_pc, to_dict, validate
from rules.tables import CONDITIONS


def _kesst(*held: str):
    pc = load_pc("fixtures/pc-kesst.json")
    pc.feats = list(held)
    return pc


def _sources(mods) -> list[str]:
    return [m.source for m in mods]


# --- the file -----------------------------------------------------------------------------

def test_the_shipped_documents_load_and_validate():
    docs = feats.documents()
    assert {"stealthy", "alertness", "acrobatic", "deceitful", "persuasive",
            "improved-initiative", "lightning-reflexes", "iron-will", "great-fortitude",
            "dodge", "toughness", "point-blank-shot"} <= set(docs)
    assert classbuilder.validate_feat_documents(docs) == []


def test_a_document_is_reached_by_name_id_or_targeted_string():
    """Four normalisers used to disagree; sheets store lower-cased names, feats.json is
    keyed by id, and "Weapon Focus (rapier)" has to reach the same feat as
    "weapon-focus"."""
    for raw in ("Iron Will", "iron will", "iron-will", "IRON WILL (anything)"):
        doc = feats.document(raw)
        assert doc and doc["id"] == "iron-will" and doc["name"] == "Iron Will", raw
    assert feats.document("iron will (anything)")["target"] == "anything"
    assert feats.document("no such feat") is None
    assert feats.document("weapon focus") is None          # 8c's business, not yet


def test_the_validator_names_the_fix():
    """Unknown keys are refused rather than ignored: `effectspec.validate` never
    rejected one, and a silently ignored field is a feat that quietly does less."""
    bad = classbuilder.validate_feat_document(
        "dodge", {"modifiers": [{"type": "combat_mod", "target": "ac", "amount": 1,
                                 "frobnicate": 2}], "colour": "blue"})
    text = " ".join(bad)
    assert "unknown key(s) frobnicate" in text and "unknown field(s) colour" in text
    assert "A modifier carries:" in text
    assert classbuilder.validate_feat_document(
        "toughness", {"modifiers": [{"type": "combat_mod", "target": "hp_maxx",
                                     "amount": 3}]})
    assert classbuilder.validate_feat_document(
        "toughness", {"modifiers": [{"type": "combat_mod", "target": "hp_max"}]})
    wrong_id = classbuilder.validate_feat_documents({"not-a-feat": {"modifiers": []}})
    assert wrong_id and "keyed by id" in wrong_id[0]


# --- through the funnel -------------------------------------------------------------------

def test_a_feat_term_names_the_feat_and_arrives_through_the_funnel():
    """Before: a bare Modifier appended in `skill_modifiers` from the Python table.
    After: the same label, from the document, through `_buff_mods` — so removing the
    feat removes the term (law 2), the way taking a ring off does."""
    pc = _kesst("stealthy")
    assert "Stealthy" in _sources(pc.skill_modifiers("stealth"))
    assert "Stealthy" in _sources(pc._buff_mods("skill_mod", "stealth"))
    before = sum(m.value for m in pc.skill_modifiers("stealth"))
    pc.feats = []
    assert "Stealthy" not in _sources(pc.skill_modifiers("stealth"))
    assert sum(m.value for m in pc.skill_modifiers("stealth")) == before - 2


def test_saves_initiative_and_ac_read_their_documents():
    pc = _kesst("iron will", "lightning reflexes", "great fortitude",
                "improved initiative", "dodge")
    assert "Iron Will" in _sources(pc.save_modifiers("will"))
    assert "Lightning Reflexes" in _sources(pc.save_modifiers("ref"))
    assert "Great Fortitude" in _sources(pc.save_modifiers("fort"))
    init = next(m for m in pc.initiative_modifiers() if m.source == "Improved Initiative")
    assert init.value == 4
    dodge = next(m for m in pc.ac_modifiers() if m.source == "Dodge")
    assert dodge.value == 1 and dodge.type == "dodge"       # typed at last


def test_a_dodge_bonus_is_lost_with_dex_to_ac():
    """1e: "A condition that makes you lose your Dex bonus to AC also makes you lose
    the benefits of this feat." Twenty-four shipped dodge feats had no reader for it."""
    pc = _kesst("dodge")
    assert "Dodge" in _sources(pc.ac_modifiers())
    key = next(k for k, row in CONDITIONS.items() if row.get("lose_dex_to_ac"))
    pc.add_condition(key)
    assert pc.loses_dex_to_ac
    assert "Dodge" not in _sources(pc.ac_modifiers())


def test_toughness_lands_on_hp_max_and_round_trips_twice():
    """Toughness sat in the table with `hp_bonus: True` and no reader; the sheet page
    printed "bonus hit points" for a feat adding none. Now `hp_max` carries the
    document's `3 + max(0, hit_dice - 3)` — and `set_hp_max` subtracts it, because
    every one-round-trip test in this codebase passed while a total that was read but
    not subtracted grew by +3 per reload (Thor 23 → 37)."""
    pc = _kesst()
    plain = pc.hp_max
    pc.feats = ["toughness"]
    assert pc.hp_max == plain + 3
    once = from_dict(to_dict(pc))
    twice = from_dict(to_dict(once))
    assert once.hp_max == plain + 3 and twice.hp_max == plain + 3
    assert twice.hp_base == pc.hp_base
    pc.feats = []
    assert pc.hp_max == plain


def test_a_formula_over_the_sheet_does_not_recurse():
    """`resources.variables` was eager and read `hp_max` before any formula was walked:
    `hp_max → _feat_mods → evaluate → variables → hp_max …` on every hit-point read."""
    pc = _kesst("toughness")
    assert isinstance(pc.hp_max, int) and isinstance(pc.ability_mod("con"), int)
    assert isinstance(pc.hp, int)


def test_a_printed_stat_block_keeps_its_number():
    """A flat-stat creature's printed total already includes its feats; every feat
    loop this replaced sat under the `else` of the flat branch."""
    pc = _kesst("iron will", "improved initiative")
    pc.flat_saves = {"will": 0}
    pc.flat_initiative = 0
    assert sum(m.value for m in pc.save_modifiers("will")) == 0
    assert sum(m.value for m in pc.initiative_modifiers()) == 0


def test_a_conditional_term_is_dropped_never_applied():
    """Point-Blank Shot's +1 is "at ranges of up to 30 feet"; the funnel carries no
    range yet, so the term is dropped — applying it to a longsword would be the bug.
    The document says so under `not_yet`."""
    pc = _kesst("point-blank shot")
    assert "Point-Blank Shot" not in _sources(pc.attack_modifiers("rapier"))
    assert "Point-Blank Shot" not in _sources(pc.damage_modifiers("rapier"))
    assert feats.document("point-blank shot")["not_yet"]


def test_validate_no_longer_calls_a_documented_feat_flavour():
    """`validate()` wrote "carried as flavour; engine applies nothing" onto 1,458 feats,
    three families of which the engine applied. A feat with a document is applied."""
    pc = _kesst("toughness", "dodge", "not a real feat")
    validate(pc)
    assert "feat 'toughness'" not in pc.notes and "feat 'dodge'" not in pc.notes
    assert "feat 'not a real feat' is carried as flavour" in pc.notes


def test_the_sheet_page_says_what_a_documented_feat_applies():
    """The page printed "bonus hit points" for Toughness while the engine added none.
    The text is generated from the document now, so it cannot drift from the read."""
    from rules.sheet import full_sheet

    pc = _kesst("toughness", "stealthy", "point-blank shot", "not a real feat")
    rows = {row["name"]: row for row in full_sheet(pc)["feats"]}
    assert rows["Toughness"]["applied"] and "hit_dice" in rows["Toughness"]["effect"]
    assert rows["Stealthy"]["applied"] and "+2 stealth" in rows["Stealthy"]["effect"]
    pbs = rows["Point-Blank Shot"]
    assert pbs["applied"] and "Not yet:" in pbs["effect"] and "when" in pbs["effect"]
    assert not rows["not a real feat"]["applied"]


# --- the ratchet --------------------------------------------------------------------------

def test_the_four_table_loops_are_gone_from_the_sheet():
    """The sixth channel: `for feat in self.feats: bonus = FEATS.get(...)` appended
    inside four builders. Zero now; the remaining `FEATS` reads are display and the
    8c branches, listed by name."""
    src = Path("rules/sheet.py").read_text(encoding="utf-8")
    assert not re.search(r"FEATS\.get\(self\._feat_name\(feat\)", src)
    assert src.count("for feat in self.feats") == 0
