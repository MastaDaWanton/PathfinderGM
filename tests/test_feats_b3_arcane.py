"""Feat loop batch 3, lane b3-arcane (2026-11-26): the arcane class-feature hooks a playable
character can use, and the spell-hook and metamagic leftovers, proved through the engine.

Before this lane, measured on master 8258614b (0.5.2): none of the lane's 91 feats had a
document. Eldritch Heritage could not even be taken — its "Skill Focus with the class skill
of bloodline selected" was unparsed, so `feats.meets` answered "unknown" for everyone — and
a fighter holding it would have had no bloodline power to use: the granted-powers reader
asked only the class's own choice.
"""
from __future__ import annotations

import pytest

from rules import class_abilities, classbuilder, feats, grantedpowers
from tests.test_class_active_abilities import _fight, _pc, _use

HERITAGE = ["Skill Focus (perception)", "Eldritch Heritage (draconic red)"]


def test_the_lane_file_validates():
    import json
    from pathlib import Path

    doc = json.loads(Path("content/feats/mechanics/b3-arcane.json").read_text("utf-8"))
    assert classbuilder.validate_feat_documents(
        {k: v for k, v in doc.items() if not k.startswith("_")}) == []


# --- Eldritch Heritage ------------------------------------------------------------------

def test_eldritch_heritage_can_be_taken_with_the_skill_focus_it_asks():
    """Measured 0.5.2: `meets` returned ok False, unknown ["Skill Focus with the class skill
    of bloodline selected for this feat (see below)"] for every character, so the feat and
    the two after it were untakeable."""
    pc = _pc("fighter", 3, feats=["Skill Focus (perception)"])
    pc.abilities["cha"] = 13
    assert feats.meets(pc, "eldritch-heritage")["ok"]
    bare = _pc("fighter", 3, feats=[])
    bare.abilities["cha"] = 13
    assert not feats.meets(bare, "eldritch-heritage")["ok"]


def test_a_fighter_with_eldritch_heritage_has_the_first_power_at_level_minus_two():
    """UM: the bloodline's 1st-level power, "using your character level - 2 as your
    effective sorcerer level". A 7th-level fighter with aberrant heritage spits Acidic
    Ray at sorcerer level 5: 1d6 + floor(5/2) = 1d6+2, never 1d6+3."""
    pc = _pc("fighter", 7, feats=["Skill Focus (knowledge (dungeoneering))",
                                  "Eldritch Heritage (aberrant)"])
    rows = grantedpowers.had(pc)
    assert [(r["power"]["key"], r["level"]) for r in rows] == [("acidic ray", 5)]
    ray = next(d for d in class_abilities._docs_for(pc) if d.get("key") == "acidic ray")
    assert ray["roll"]["bonus"] == "floor((level - 2) / 2)"


def test_no_power_without_the_bloodlines_own_skill_focus():
    """The pick's skill is asked when the power is read: Skill Focus (perception) is the
    draconic bloodline's, not the aberrant's."""
    pc = _pc("fighter", 7, feats=["Skill Focus (perception)", "Eldritch Heritage (aberrant)"])
    assert grantedpowers.had(pc) == []


def test_improved_heritage_breathes_at_character_level_minus_two_through_the_engine():
    """Improved Eldritch Heritage (breath weapon) on an 11th-level fighter, Cha 16: the
    draconic breath at sorcerer level 9 — 9d6 fire, Reflex DC 10 + 4 + 3 = 17 — spent
    from its own once-a-day pool and stamped with the bloodline power's origin."""
    pc = _pc("fighter", 11, feats=HERITAGE + ["Improved Eldritch Heritage (breath weapon)"])
    pc.abilities["cha"] = 16
    _scene, e = _fight(pc, "thug")
    out = _use(e, "Breath Weapon", to="c1")
    save = next(f for f in out.effects if f.get("kind") == "save")
    assert save["dc"] == 17
    assert "9d6" in out.tell
    spent = next(f for f in out.effects if f.get("kind") == "resource")
    assert (spent["pool"], spent["left"]) == ("breath weapon", 0)


def test_greater_heritage_lifts_every_heritage_power_to_character_level():
    """Greater: "treat your character level as your sorcerer level for all your sorcerer
    bloodline powers granted by this feat, Eldritch Heritage, and Improved"."""
    pc = _pc("fighter", 17, feats=HERITAGE + ["Improved Eldritch Heritage (breath weapon)",
                                              "Greater Eldritch Heritage (wings)"])
    got = {r["power"]["key"]: r["level"] for r in grantedpowers.had(pc)}
    assert got == {"claws": 17, "breath weapon": 17, "wings": 17}


def test_a_sorcerer_cannot_take_her_own_bloodline_again():
    """"Select one sorcerer bloodline. ... a bloodline you do not already have" — a
    draconic sorcerer naming draconic gets nothing twice."""
    pc = _pc("sorcerer", 5, feats=HERITAGE,
             class_choices={"bloodline": {"picks": [{"pick": "draconic", "variant": "red"}]}})
    assert [r["label"] for r in grantedpowers.had(pc)
            if "Eldritch" in r["label"]] == []
