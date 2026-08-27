"""The eleven Core Rulebook classes, all of them playable data.

The class table shipped four for months — rogue, fighter, wizard, cleric — while the
character sheet, the caster machinery and the pools engine were all general. What was
missing was only ever the data, and "only" is why it kept not happening: seven classes,
twenty levels each, three new slot progressions, none of it derivable. This file is the
proof they arrived whole.
"""
from __future__ import annotations

import pytest

from rules import casting, classes
from rules.sheet import from_dict

CORE = ["barbarian", "bard", "cleric", "druid", "fighter", "monk", "paladin",
        "ranger", "rogue", "sorcerer", "wizard"]


def actor(cid, level=1, **abilities):
    scores = {"str": 14, "dex": 14, "con": 14, "int": 14, "wis": 14, "cha": 14}
    scores.update(abilities)
    return from_dict({"name": f"test {cid}", "kind": "pc", "class": cid,
                      "level": level, "abilities": scores, "hp": 30, "hp_max": 30})


def test_all_eleven_are_present_and_deep():
    have = classes.all_classes()
    for cid in CORE:
        assert cid in have, cid
        cls = have[cid]
        assert cls["hit_die"] in (6, 8, 10, 12)
        assert cls["bab"] in ("full", "three_quarter", "half")
        assert cls["good_saves"], cid
        assert len(cls["class_skills"]) >= 9, cid
    # And the seven new ones carry their whole advancement, not a level-1 stub.
    for cid in ("barbarian", "bard", "druid", "monk", "paladin", "ranger", "sorcerer"):
        assert len(have[cid]["levels"]) == 20, cid


@pytest.mark.parametrize("cid,die", [
    ("barbarian", 12), ("paladin", 10), ("ranger", 10),
    ("bard", 8), ("druid", 8), ("monk", 8), ("sorcerer", 6),
])
def test_hit_dice_match_the_book(cid, die):
    assert classes.get(cid)["hit_die"] == die


def test_the_monk_is_good_at_all_three_saves():
    assert set(classes.get("monk")["good_saves"]) == {"fort", "ref", "will"}


# --- casting -------------------------------------------------------------------------------

def test_the_sorcerer_casts_more_and_later_than_the_wizard():
    """Core Table 3-14 against 3-18: at 5th a sorcerer has six 1st-level slots to the
    wizard's three (before bonus), and no 3rd-level slots at all where the wizard has
    one. The tables are different tables, not one table shifted."""
    sorc, wiz = actor("sorcerer", 5), actor("wizard", 5)
    s, w = casting.slots_for(sorc), casting.slots_for(wiz)
    assert s[1] > w[1]
    assert 3 in w and 3 not in s


def test_the_sorcerer_needs_no_preparation():
    """`prepare_from: "known"` — the spellbook field holds the repertoire, any slot
    casts any of it, and the wizard's did-you-prepare-it check never fires."""
    sorc = actor("sorcerer", 1)
    sorc.spellbook = ["magic-missile"]
    from rules import spells
    assert casting.knows(sorc, spells.get("magic-missile"))
    assert not casting.knows(sorc, spells.get("mage-armor")), "not in the repertoire"


def test_the_bard_stops_at_six_spell_levels():
    """Cha 18, because the ability gate is also real: a Cha 14 bard cannot cast 6th-level
    spells at all, and the first version of this test discovered that by failing."""
    bard = actor("bard", 20, cha=18)
    assert max(casting.slots_for(bard)) == 6


def test_the_paladin_gets_nothing_before_fifth_and_something_after():
    """The book gives 4th level a bonus-slots-only row; the engine skips a zero base, so
    the modelled paladin starts casting at 5. Stated in the table's comment, asserted
    here so the compromise is a decision and not a drift."""
    assert casting.slots_for(actor("paladin", 4)) == {}
    assert casting.slots_for(actor("paladin", 5)) == {1: 2}   # 1 base + 1 Cha bonus


def test_the_druid_is_a_full_prepared_caster_off_wisdom():
    druid = actor("druid", 5)
    assert casting.casting_ability(druid) == "wis"
    assert casting.slots_for(druid)[3] >= 1


# --- the countable things ------------------------------------------------------------------

@pytest.mark.parametrize("cid,pool,level,expect", [
    ("barbarian", "rage", 1, "4 + con_mod + 2*(level - 1)"),
    ("bard", "bardic performance", 1, "4 + cha_mod + 2*(level - 1)"),
    ("monk", "ki", 4, "floor(level / 2) + wis_mod"),
    ("paladin", "lay on hands", 2, "floor(level / 2) + cha_mod"),
    ("druid", "wild shape", 4, "1 + floor((level - 4) / 2)"),
])
def test_the_pools_arrive_at_the_level_the_book_grants_them(cid, pool, level, expect):
    before = {p["id"] for p in classes.pools_for(cid, level - 1)}
    after = {p["id"]: p for p in classes.pools_for(cid, level)}
    assert pool not in before or level == 1
    assert pool in after
    assert after[pool]["max"] == expect


def test_features_read_from_the_level_table():
    assert "rage" in classes.features_at("barbarian", 1)
    assert "greater rage" in classes.features_at("barbarian", 11)
    assert "ki pool" in classes.features_at("monk", 4)
    assert "smite evil 1/day" in classes.features_at("paladin", 1)


def test_a_homebrew_path_overlay_cannot_erase_shipped_ability_documents(tmp_path, settings, monkeypatch):
    """The overlay's `base.update` replaced `paths` wholesale: a homebrew copy of
    blood bending saved by the in-app editor before `grants`/`toggles` existed
    silently erased every ability document the shipped file gained afterwards.
    Measured live: Blood Rage fell back to the old effectspec branch — the tell said
    '+4 ac' and no number moved. Paths must layer per path and per field."""
    import json
    from rules import classes as classes_mod

    home = tmp_path / "homebrew" / "classes"
    home.mkdir(parents=True)
    stale = {"id": "blood bending",
             "paths": {"battle blood": {"summary": "my tweaked summary"}}}
    (home / "blood bending.json").write_text(json.dumps(stale), encoding="utf-8")
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    monkeypatch.setattr(classes_mod, "_ALL", None)
    try:
        got = classes_mod.get("blood bending")["paths"]["battle blood"]
        assert got["summary"] == "my tweaked summary"
        assert "Blood Rage" in (got.get("grants") or {})
        assert (got.get("toggles") or {}).get("Blood Rage")
    finally:
        monkeypatch.setattr(classes_mod, "_ALL", None)
