"""Spell items: the item creation feats out of the game, scrolls and wands at the circle.

Owner ruling 2026-11-22: "Remove item creation feats they are unnecessary, instead build the
magic items like wands and scrolls and constructs into the enchanting world class."
The design record is docs/item-creation-feats-study.md (options A for scrolls and wands).

What was measured before this lane, on integrate/0.5.1-impl 0eee57ff:
- all nine item creation feats were takeable and did nothing (the audit's "item-creation"
  NARRATED reason); every wizard was handed Scribe Scroll at 1st level, and so was every
  Rune cleric;
- there was no scroll, no wand and no maker of either; Use Magic Device's honesty line
  read "There are no wands or scrolls to find or buy yet ... so nothing calls for it";
- three readers waited for a scroll that could not exist: the alchemy formula route
  "copied from a scroll", the enchanter's carried-scroll-stands-in rule, and the wizard
  text "copied into the book from a scroll".
"""
from __future__ import annotations

import json

import pytest

from rules import creation, feats, leveling
from rules.sheet import from_dict, to_dict

ABILITIES = {"str": 10, "dex": 14, "con": 12, "int": 16, "wis": 12, "cha": 10}


def _wizard(**over):
    body = {"name": "Scroll Test", "race": "human", "class": "wizard", "gender": "woman",
            "abilities": dict(ABILITIES), "choices": ["int"], "skills": ["spellcraft"],
            "feats": [], "domains": creation.starter_domains("wizard"),
            "spellbook": creation.starter_spells("wizard", 1)}
    body.update(over)
    built, problems = creation.build(body)
    assert problems == [], problems
    return from_dict(built["sheet"], ref="pc")


# --- the feats leave -----------------------------------------------------------------------

def test_the_item_creation_feats_are_out_of_the_catalogue_and_the_picker():
    """Before: `feats.search(kind="item creation")` offered Brew Potion, Scribe Scroll,
    Craft Wand, Craft Staff, Craft Rod, Craft Wondrous Item, Craft Magic Arms and Armor,
    Forge Ring and Craft Construct, nine feats with no effect."""
    for fid in feats.RETIRED:
        assert fid not in feats.all_feats()
        with pytest.raises(KeyError):
            feats.get(fid)
    offered = {f.id for f in feats.search(kind="item creation")}
    assert not offered & feats.RETIRED
    # Master Craftsman keeps its own +2 and stays.
    assert "master-craftsman" in feats.all_feats()


def test_a_saved_wizard_holding_scribe_scroll_loads_with_a_free_pick_back():
    """The owner's saves hold Scribe Scroll (the study counted two). A load must not fail
    and must not keep a dead feat: the line goes, and one feat pick comes back, owed on the
    Class card until it is spent, and saved as a count so the next load still owes it."""
    pc = _wizard()
    d = to_dict(pc)
    d["feats"] = list(d.get("feats") or []) + ["scribe scroll"]
    before = leveling.owed(from_dict(json.loads(json.dumps({**d, "feats": d["feats"][:-1]})),
                                     ref="pc"))["feats"]["owed"]
    back = from_dict(d, ref="pc")
    assert "scribe scroll" not in back.feats
    assert back.feats_refunded == 1
    due = leveling.owed(back)["feats"]
    assert due["owed"] == before + 1
    assert {"for_level": 1, "source": "refund"} in due["picks"]
    again = from_dict(json.loads(json.dumps(to_dict(back))), ref="pc")
    assert again.feats_refunded == 1 and "scribe scroll" not in again.feats
    # Spent like any general pick.
    again.level_feats_taken = 1
    assert leveling.owed(again)["feats"]["owed"] == before


def test_a_printed_creature_sheds_the_feat_with_no_pick_and_no_note():
    """A bestiary block lists Craft Wondrous Item (a lich, a hag): the creature loads
    without the line, and owes nothing, because a printed creature takes no picks."""
    pc = _wizard()
    d = to_dict(pc)
    d.update(kind="npc", feats=["craft wondrous item", "Craft Magic Arms and Armor",
                                "combat casting"])
    npc = from_dict(d, ref="c1")
    assert npc.feats == ["combat casting"]
    assert npc.feats_refunded == 0


def test_the_wizard_takes_a_bonus_feat_at_first_level_in_scribe_scrolls_place():
    """By the book a wizard's 1st-level Scribe Scroll; with it gone, the least surprising
    replacement is one more wizard bonus feat (a metamagic feat or Spell Mastery). An
    owner call (lane report)."""
    assert leveling.class_bonus_feats_at("wizard", 1) == 1
    pc = _wizard(feats=["toughness", "extend-spell"])
    assert "extend spell" in pc.feats
    body = {"name": "Scroll Test", "race": "human", "class": "wizard", "gender": "woman",
            "abilities": dict(ABILITIES), "choices": ["int"], "skills": ["spellcraft"],
            "feats": ["toughness", "iron-will", "alertness"],
            "domains": creation.starter_domains("wizard"),
            "spellbook": creation.starter_spells("wizard", 1)}
    _built, problems = creation.build(body)
    assert any("metamagic feat or Spell Mastery" in p for p in problems), problems
