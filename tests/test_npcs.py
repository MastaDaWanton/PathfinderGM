"""The codex chooser and the NPC codex store (docs/npc-codex.md; quest schemes §6.3).

Before this, every person a scheme put on the board was a guildhand, or a watchman if
the role said "guard officer": two stat blocks for every role in every world, with
seven thousand blocks already in the bestiary. The chooser turns role words and a
level into one of those blocks; the store pins the block to the world character so
next week's numbers are this week's.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import bestiary, npcs, schemes


# --- the index -------------------------------------------------------------------------------

def test_the_index_is_people_only_and_tiers_are_one_person():
    """Measured on the shipped bestiary: 7,136 blocks, 3,747 typed humanoid, 3,518 of
    those small or medium; 207 ids carry a Society "-tier-N-M" suffix (four of them
    spelt "-teir-") and 93 a "-level-N" one, each a separate block for the same
    person. Collapsed, the index holds 3,063 people over 3,515 rungs."""
    ix = npcs.index()
    assert 2900 <= len(ix) <= 3300, len(ix)
    rungs = sum(len(e["ladder"]) for e in ix.values())
    assert rungs > len(ix) + 300, "the tiers did not collapse"
    assert not any(npcs._TIER.search(k) for k in ix)
    for e in ix.values():
        for _, bid in e["ladder"]:
            block = bestiary.imported()[bid]
            assert block["creature_type"] == "humanoid"
            assert block.get("size") in ("small", "medium", None, "")


def test_tiers_collapse_and_the_nearest_rung_is_picked():
    """`bandit-archer` (CR 1) and `bandit-archer-tier-8-9` (CR 5) are one Society
    archer at two subtiers. Asked at 2nd level the low rung answers, at 6th the high
    one; the first draft indexed them as two people and offered the CR 5 archer to a
    2nd-level party because its id sorted first."""
    assert npcs.ladder("bandit-archer") == [(1.0, "bandit-archer"), (5.0, "bandit-archer-tier-8-9")]
    assert npcs.ladder("bandit-archer-tier-8-9") == npcs.ladder("bandit-archer")
    low = npcs.choose("bandit archer", 2, prefer_named=True)
    high = npcs.choose("bandit archer", 6, prefer_named=True)
    assert low["id"] == "bandit-archer" and high["id"] == "bandit-archer-tier-8-9"
    assert low["role"] == high["role"] == "bandit archer"


# --- choosing ----------------------------------------------------------------------------------

def test_the_generic_galleries_beat_an_adventure_path_for_a_guard_captain():
    """Both "guard" and "captain" appear in Rappan Athuk's `trillok-captain-of-the-guard`
    and in nothing the NPC Codex prints; sorted by words matched alone, a 5th-level
    party's guard captain was a named dungeon lieutenant at CR 7. The galleries come
    first because their numbers were built to be anybody's: the NPC Codex Border Guard
    (CR 3) is the answer, and only `prefer_named` reaches for the story block."""
    got = npcs.choose("guard captain", 5)
    assert got["source"] in npcs._GENERIC, got
    assert not got["floor"]
    assert "trillok-captain-of-the-guard" in npcs.index(), "the rival candidate is real"
    named = npcs.choose("guard captain", 8, prefer_named=True)
    assert npcs.source_rank(named["source"]) == 2
    assert named["role"] == "captain of the guard"


def test_a_proper_name_is_stripped_and_the_block_is_usable_as_a_role():
    """`jevana-drow-noble-priestess` is a Society villain with a name and a job. The
    name is the one token nothing else shares (measured: "jevana" is in 2 of 7,136 ids,
    "drow" in 17, "noble" in 11, "priestess" in 5), so it goes and the job stays. Asked
    for a noble priestess near 10th level with story blocks preferred, she is the
    pick — as a drow noble priestess, never as Jevana."""
    assert npcs.strip_name("jevana-drow-noble-priestess") == "drow noble priestess"
    assert npcs.strip_name("captain-gortus-svard") == "captain"
    assert npcs.strip_name("abra-lopati") == "", "a name and nothing else is nobody's role"
    got = npcs.choose("noble priestess", 10, prefer_named=True)
    assert got["id"] == "jevana-drow-noble-priestess"
    assert got["role"] == "drow noble priestess"
    assert "jevana" not in got["role"]


def test_the_joining_words_do_not_survive_the_name_they_joined():
    """`caleb-voltiaro-vicar-of-the-indomitable-sea` stripped to "of the sea": "of" and
    "the" are common enough to clear the count and the vicar was not. Trimmed."""
    assert npcs.strip_name("caleb-voltiaro-vicar-of-the-indomitable-sea") == "sea"
    assert npcs.strip_name("trillok-captain-of-the-guard") == "captain of the guard"


def test_unknown_words_fall_to_the_townsfolk_floor_by_shape():
    """A role nobody wrote a block for still has numbers: the hand-written watchman for
    guard-shaped words, the thug for thug-shaped ones, the guildhand for the rest. The
    display role is the words that were asked, so the fill reads as what the scheme
    wanted rather than as "guildhand"."""
    got = npcs.choose("xyzzy plugh", 3)
    assert got["floor"] and got["id"] == "guildhand" and got["role"] == "xyzzy plugh"
    assert npcs.floor_for("gate sergeant") == "watchman"
    assert npcs.floor_for("hired ruffian") == "thug"
    assert npcs.floor_for("companion") == "guildhand"
    assert npcs.choose("", 1)["id"] == "guildhand"


def test_a_match_too_far_from_the_level_is_not_near_the_level():
    """Measured before the cap: a 1st-level party's "someone of standing" was the CR 6
    Village Elder and their guard officer the CR 6 Watch Captain — the right words and
    a fight nobody at the table could have. Past three CR from level-1 the townsfolk
    floor is nearer than any block, so it is what they get; at 6th the elder is back."""
    assert npcs.choose("elder", 1)["floor"]
    assert npcs.choose("elder", 6)["id"] == "village-elder"
    for role, words in schemes._ROLE_WORDS.items():
        got = npcs.choose(words, 1)
        assert got["floor"] or abs(got["cr_value"] - npcs.target_cr(1)) <= npcs.MAX_DISTANCE, (role, got)


def test_the_same_words_and_level_choose_the_same_block():
    """Determinism is what lets the store be a cache rather than a lie: `remember` is
    only ever asked once per person, and a rebuilt index must answer as the old one did."""
    words = [("guard officer", 1), ("merchant", 4), ("noble priestess", 10),
             ("bandit archer", 6), ("kin", 3)]
    first = [npcs.choose(w, lvl)["id"] for w, lvl in words]
    npcs._BUILT = ()
    second = [npcs.choose(w, lvl)["id"] for w, lvl in words]
    assert first == second
    assert first == [npcs.choose(w, lvl, prefer_named=False)["id"] for w, lvl in words]


def test_every_chosen_block_instantiates():
    """The chooser's answer has to be something `bestiary.instantiate` can build, or the
    scheme opening dies with the slot half-filled. Every role the shipped vocabulary
    names, at every level band."""
    for words in schemes._ROLE_WORDS.values():
        for level in (1, 5, 10, 15):
            got = npcs.choose(words, level)
            actor = bestiary.instantiate(got["id"], name="x")
            assert actor.hp_max > 0, (words, level, got)


# --- the store -----------------------------------------------------------------------------------

def test_remember_and_recall_round_trip_and_the_file_is_the_benchs(tmp_path):
    """One JSON per world entity under homebrew/npcs, keyed by the entity id, in the
    registry's own shape so it is a row on the NPCs bench and opens in its editor."""
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        assert npcs.recall("05b7a28595a3") is None
        path = npcs.remember("05b7a28595a3", "border-guard", "Ariniel Thorne", role="border guard")
        assert path.name == "05b7a28595a3.json" and path.parent.name == "npcs"
        got = npcs.recall("05b7a28595a3")
        assert got["creature"] == "border-guard" and got["name"] == "Ariniel Thorne"
        assert got["world_entity_id"] == "05b7a28595a3" and got["role"] == "border guard"
        from rules import registry

        assert registry.find("npcs", "05b7a28595a3")["creature"] == "border-guard"
        # The bench's editor writes the same file; a corrected creature wins next time.
        data = json.loads(path.read_text(encoding="utf-8"))
        data["creature"] = "watchman"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert npcs.block_for("05b7a28595a3", ("guard",), 1, "Ariniel Thorne") == "watchman"
        assert npcs.forget("05b7a28595a3") and npcs.recall("05b7a28595a3") is None


def test_a_remembered_block_that_no_longer_exists_is_chosen_again(tmp_path):
    """A homebrew creature can be deleted out from under a codex entry. `block_for`
    must not hand `instantiate` an id it will refuse; it chooses again and rewrites."""
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        npcs.remember("e1", "no-such-creature-anywhere", "Someone")
        got = npcs.block_for("e1", ("guard", "captain"), 5, "Someone")
        assert bestiary.lookup(got) is not None
        assert npcs.recall("e1")["creature"] == got


def test_an_unreadable_codex_file_does_not_stop_a_scheme(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        path = npcs.remember("e2", "guard", "Someone")
        path.write_text("{not json", encoding="utf-8")
        assert npcs.recall("e2") is None
        assert bestiary.lookup(npcs.block_for("e2", ("guard",), 1, "Someone")) is not None


# --- the bench ------------------------------------------------------------------------------------

def test_the_npcs_bench_is_ready_and_lists_the_codex(tmp_path):
    """The bench shipped `ready=False` with a shipped count of 0 while the app held
    3,063 people to choose from. Now it says how many, and a remembered person is a
    row that names the block, the role and the world entity."""
    from play import campaign as cm
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        npcs.remember("05b7a28595a3", "border-guard", "Ariniel Thorne", role="border guard")
        d = Client().get("/api/bench/npcs").json()
        cm._LIVE.clear()
    assert d["bench"]["ready"] is True
    assert d["bench"]["shipped"] == npcs.humanoid_count() > 2900
    # The border guard remembered above, plus a keeper only if the room the opening
    # stands the party in is one somebody keeps. At schema 1.5 that room is a city's
    # great square — a junction, not a shop — so it is one.
    assert d["bench"]["yours"] >= 1
    row = next(r for r in d["rows"] if r["id"] == "05b7a28595a3")
    assert row["name"] == "Ariniel Thorne" and row["kind"] == "codex"
    assert "border-guard" in row["note"] and "border guard" in row["note"] and "05b7a28595a3" in row["note"]


# --- through the scheme skeleton -----------------------------------------------------------------

def test_the_scheme_skeleton_fills_a_giver_through_the_chooser(tmp_path, monkeypatch):
    """`_role_for` hard-coded guildhand-or-watchman. Now the giver of "The lost thing"
    — a trader from the world's cast — wears a codex block chosen for trader words near
    the party's level, keeps their own name and world id, and is written to the codex
    so the next opening finds the same block. tests/test_schemes.py still passes
    unchanged, which is the other half of this."""
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc
    from world import loader

    monkeypatch.setattr(schemes, "ENABLED", True)
    world = loader.load_cached("fixtures/pangrella-campaign.json")
    town = "5bbd0c40345f"
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        s = Scene(location_id=town)
        pc = load_pc("fixtures/pc-kesst.json")
        s.add(pc)
        e = Engine(s, Dice(seed=3), world=world)
        e.place_party(f"{town}~urban:the-market")
        intents = e.validate([{"op": "advance_time", "actor": "pc", "because": "t",
                               "params": {"amount": 1, "unit": "minutes"}}], origin="author:test")
        e.run(intents)
        inst = next(i for i in s.schemes if i["scheme"] == "the-lost-thing")
        giver = s.people[inst["slots"]["giver"]["ref"]]
        assert giver.world_entity_id and giver.name not in ("guildhand", "watchman", "thug")
        expect = npcs.choose(schemes._ROLE_WORDS["trader"], pc.level)
        assert giver.from_template == expect["id"], (giver.from_template, expect)
        assert not expect["floor"], "a trader is in the codex; the floor was the old answer"
        kept = npcs.recall(giver.world_entity_id)
        assert kept["creature"] == expect["id"] and kept["name"] == giver.name
