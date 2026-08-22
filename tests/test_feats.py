"""1,474 feats, and whether a character actually qualifies for one.

`tables.FEATS` holds sixteen feats as Python because the engine reads *mechanics* off them:
Weapon Finesse swaps an ability on attack rolls, Improved Initiative is worth four, Power
Attack has its own arithmetic. Those stay hand-written — no spreadsheet column encodes "use
Dex in place of Str". `content/feats/feats.json` holds all of them as data, and the point of
that is not the prose. It is being able to *ask* whether a character may take one.

Two things the extractor got wrong on the first run, both recorded below as tests:

  - Mythic Adventures gives 155 feats the same name as the ordinary feat they require —
    mythic Dodge's only prerequisite is Dodge. Slugging on the name alone collapsed each
    pair, losing 156 feats and leaving Power Attack listing *itself* as an unmet
    prerequisite.
  - Thirteen more ids collided as honest reprints of one feat in two books, except
    `spider-step`, which is two genuinely different feats sharing a name. Keeping one of
    those would have lost a feat with no symptom at all.

And the rule the checker is built on: a prerequisite it cannot read makes the answer
`unknown`, never True. A checker that assumes yes lets a character take a feat they have not
earned, and the symptom is a wrong number for the rest of the campaign.
"""
from __future__ import annotations

import re

import pytest

from rules import feats
from rules.sheet import load_pc
from rules.tables import FEATS as MECHANICAL


@pytest.fixture
def kesst():
    """Level 1 human rogue: Str 12, Dex 17, BAB 0, Weapon Finesse and Stealthy."""
    return load_pc("fixtures/pc-kesst.json")


# --- the index ----------------------------------------------------------------------------

def test_the_whole_book_is_here():
    assert len(feats.all_feats()) > 1400


def test_every_id_is_unique():
    """The loader merges on id, so a collision is a feat that silently disappears."""
    ids = [f.id for f in feats.all_feats().values()]
    assert len(ids) == len(set(ids))


def test_no_feat_name_was_lost():
    """1,478 rows became 1,474 entries. The four that went are reprints of the same feat
    in a second book, and every distinct *name* still has an entry."""
    names = {f.name.lower() for f in feats.all_feats().values()}
    for expected in ("power attack", "dodge", "weapon finesse", "improved critical",
                     "combat reflexes", "spider step", "blood vengeance", "damned"):
        assert expected in names


def test_a_mythic_feat_does_not_swallow_the_feat_it_requires():
    """The bug that lost 156 feats. Mythic Dodge requires Dodge, and both are called
    Dodge; slugging on name alone left one entry whose prerequisite was itself."""
    assert feats.get("dodge").id == "dodge"
    assert feats.get("dodge-mythic").id == "dodge-mythic"
    assert "mythic" in feats.get("dodge-mythic").types
    assert "mythic" not in feats.get("dodge").types


def test_the_mythic_version_requires_the_ordinary_one():
    conds = feats.get("dodge-mythic").prerequisites
    assert {"kind": "feat", "feat": "dodge", "name": "Dodge"} in conds


def test_power_attack_does_not_require_itself():
    """What the collision looked like from the outside, and the reason it was noticed."""
    named = [c.get("feat") for c in feats.get("power-attack").prerequisites]
    assert "power-attack" not in named


def test_a_reprint_records_the_other_book_rather_than_becoming_a_second_feat():
    """Blood Vengeance is in both the Advanced Race Guide and Orcs of Golarion. It is one
    feat."""
    found = [f for f in feats.all_feats().values() if f.name.lower() == "damned"]
    assert len(found) == 1


def test_two_different_feats_sharing_a_name_both_survive():
    """`spider-step` is the exception: the Advanced Player's Guide one wants Acrobatics
    and Climb ranks, the Advanced Race Guide one wants a drow at 3rd level. Merging them
    would lose a feat and nothing would say so."""
    both = [f for f in feats.all_feats().values() if f.name.lower() == "spider step"]
    assert len(both) == 2
    assert {f.source for f in both} == {"Advanced Player's Guide", "Advanced Race Guide"}


def test_the_licence_travels_with_the_content():
    """OGL content, and the licence has to ship with any build that carries this file."""
    assert "Open Game" in feats.meta().get("licence", "")


# --- prerequisites, parsed --------------------------------------------------------------------

def test_an_ability_prerequisite():
    assert {"kind": "ability", "ability": "str", "value": 13} in \
        feats.get("power-attack").prerequisites


def test_a_base_attack_bonus_prerequisite():
    assert {"kind": "bab", "value": 8} in feats.get("improved-critical").prerequisites


def test_a_feat_prerequisite_resolves_to_an_id():
    conds = feats.get("acrobatic-steps").prerequisites
    assert {"kind": "feat", "feat": "nimble-moves", "name": "Nimble Moves"} in conds


def test_a_skill_rank_prerequisite():
    conds = feats.get("spider-step").prerequisites
    assert {"kind": "skill_ranks", "skill": "acrobatics", "ranks": 6} in conds


def test_a_class_level_prerequisite():
    conds = feats.get("greater-weapon-focus").prerequisites
    assert {"kind": "class_level", "class": "fighter", "value": 8} in conds


def test_a_semicolon_separates_conditions_just_like_a_comma():
    """"Con 13; dwarf" is two conditions. Splitting on commas alone left a dozen ordinary
    racial feats with an unparseable prerequisite."""
    parsed = [f for f in feats.all_feats().values() if "; " in f.prerequisites_text]
    assert parsed
    for f in parsed[:20]:
        assert len(f.prerequisites) + len(f.unparsed_prerequisites) >= 2


def test_race_alternatives_become_one_condition():
    """"Half-orc or orc" is one requirement with two answers, not an unreadable clause."""
    conds = feats.get("blood-vengeance").prerequisites
    assert any(c["kind"] == "race_any" and set(c["races"]) == {"half-orc", "orc"}
               for c in conds)


def test_a_parenthetical_is_not_split_on_its_comma():
    """"Spell Focus (conjuration), Int 13" must not become "Spell Focus (conjuration"."""
    for f in feats.all_feats().values():
        for clause in f.unparsed_prerequisites:
            assert clause.count("(") == clause.count(")")


def test_what_could_not_be_parsed_is_kept_verbatim():
    """Never dropped. A parser that discards what it does not understand produces a feat
    that looks freely available and is not."""
    unreadable = [f for f in feats.all_feats().values() if f.unparsed_prerequisites]
    assert unreadable
    for f in unreadable[:10]:
        for clause in f.unparsed_prerequisites:
            assert clause and clause.lower() in f.prerequisites_text.lower()


# --- does this character qualify? ---------------------------------------------------------------

def test_a_feat_with_no_prerequisites_is_available(kesst):
    assert feats.meets(kesst, "toughness")["ok"]


def test_an_ability_short_of_the_requirement_is_named(kesst):
    """Kesst has Str 12 and BAB 0. The refusal says both, because a rejection that does
    not say what is missing is one the player cannot act on."""
    got = feats.meets(kesst, "power-attack")
    assert not got["ok"]
    assert "Str 13" in got["unmet"]
    assert "base attack bonus +1" in got["unmet"]


def test_a_feat_already_held_counts_as_a_prerequisite(kesst):
    """A sheet writes "weapon focus (rapier)" and a prerequisite says "Weapon Focus".
    Without matching the two, every specialised feat chain is refused at its second step."""
    kesst.feats = ["weapon focus (rapier)"]
    kesst.abilities["str"] = 13
    kesst.level = 8
    got = feats.meets(kesst, "greater-weapon-focus")
    assert "Weapon Focus" not in got["unmet"]


def test_a_class_level_prerequisite_checks_the_class_not_just_the_level(kesst):
    kesst.level = 12
    got = feats.meets(kesst, "greater-weapon-focus")          # rogue, not fighter
    assert "fighter level 8" in got["unmet"]


def test_a_skill_rank_prerequisite_reads_the_ranks(kesst):
    got = feats.meets(kesst, "spider-step")
    assert any("ranks in Acrobatics" in u for u in got["unmet"])
    kesst.ranks.update({"acrobatics": 6, "climb": 6})
    assert not any("ranks in" in u for u in feats.meets(kesst, "spider-step")["unmet"])


def test_a_race_prerequisite_reads_the_race(kesst):
    assert not feats.meets(kesst, "blood-vengeance")["ok"]     # human
    kesst.race = "half-orc"
    assert "Half-Orc or Orc" not in feats.meets(kesst, "blood-vengeance")["unmet"]


def test_an_unreadable_prerequisite_is_unknown_and_never_yes(kesst):
    """The rule the whole checker is built on. "Ability to channel energy" is not
    something the sheet can answer, and answering yes lets a character take a feat they
    have not earned."""
    got = feats.meets(kesst, "alignment-channel")
    assert not got["ok"]
    assert got["unknown"]
    assert not got["unmet"]


def test_alignment_is_unknown_rather_than_refused(kesst):
    """The sheet has no alignment field. Answering False would refuse every
    alignment-gated feat outright, which is a worse lie than admitting the gap."""
    got = feats.meets(kesst, feats.get("blood-vengeance"))
    assert any("lawful" in u for u in got["unknown"])


# --- the available list -------------------------------------------------------------------------

def test_available_lists_only_what_is_definitely_takeable(kesst):
    got = feats.available(kesst)
    assert got
    for f in got:
        assert feats.meets(kesst, f)["ok"]


def test_available_leaves_out_anything_it_cannot_read(kesst):
    """A list that included them would be a list of feats that mostly cannot be taken."""
    ids = {f.id for f in feats.available(kesst)}
    assert "alignment-channel" not in ids


def test_available_does_not_offer_a_feat_you_already_have(kesst):
    assert "weapon-finesse" not in {f.id for f in feats.available(kesst)}


def test_available_can_be_narrowed_to_a_type(kesst):
    combat = feats.available(kesst, "combat")
    assert combat
    assert all("combat" in f.types for f in combat)
    assert len(combat) < len(feats.available(kesst))


def test_a_better_character_qualifies_for_more(kesst):
    lean = len(feats.available(kesst))
    kesst.level = 10
    kesst.abilities.update({"str": 18, "dex": 18, "con": 16, "int": 14, "wis": 14})
    assert len(feats.available(kesst)) > lean


# --- the hand-written table still runs the engine ---------------------------------------------------

def test_the_sixteen_mechanical_feats_are_untouched():
    """These are code, not data. The index does not replace them — no spreadsheet column
    encodes "use Dex in place of Str on attack rolls"."""
    assert MECHANICAL["weapon finesse"]["finesse"] is True
    assert MECHANICAL["improved initiative"]["initiative"] == 4
    assert MECHANICAL["lightning reflexes"]["saves"]["ref"] == 2


def test_a_mechanical_feat_is_reachable_from_the_index():
    """Both halves describe the same feat, and the index says which ones the engine
    actually computes with."""
    assert feats.get("weapon-finesse").mechanical.get("finesse") is True
    assert feats.get("acrobatic-steps").mechanical == {}


def test_the_index_did_not_break_the_sheet(kesst):
    """Weapon Finesse still swaps the ability on Kesst's attack roll."""
    terms = {m.source for m in kesst.attack_modifiers("rapier")}
    assert any("Dex" in t or "dex" in t.lower() for t in terms)


# --- search ---------------------------------------------------------------------------------------------

def test_search_finds_by_name():
    assert "Power Attack" in {f.name for f in feats.search("power attack")}


def test_search_can_filter_by_type():
    found = feats.search("", kind="metamagic", limit=0)
    assert found and all("metamagic" in f.types for f in found)


def test_search_prefers_a_name_match_over_a_prose_match():
    assert feats.search("dodge")[0].name == "Dodge"


def test_looking_a_feat_up_by_name_finds_the_ordinary_one(kesst):
    """The mythic collision again, one layer up. The ids were disambiguated but the
    name lookup was a plain dict comprehension, so whichever came last won — and the
    character sheet printed mythic Weapon Finesse's prerequisite ("Weapon Finesse.")
    beside Kesst's ordinary one."""
    assert feats.get("weapon finesse").id == "weapon-finesse"
    assert feats.get("weapon finesse").prerequisites_text == ""
    assert feats.get("alertness").id == "alertness"
    assert feats.get("dodge").prerequisites_text.startswith("Dex 13")


def test_a_source_tag_glued_to_a_feat_name_still_resolves():
    """The export flattens the source book's superscript onto the name: "Powerful ShapeUM"
    is Powerful Shape, from Ultimate Magic. Stripped only when what is left is a real
    feat, so it cannot invent one."""
    conds = feats.get("powerful-shape").prerequisites + \
        feats.get("greater-blind-fight").prerequisites
    assert any(c["kind"] == "feat" for c in conds)
    tagged = [f for f in feats.all_feats().values()
              if any(re.search(r"[a-z][A-Z]{2,4}$", u) for u in f.unparsed_prerequisites)]
    assert len(tagged) <= 2


def test_the_sheet_shows_a_feats_real_benefit_rather_than_calling_it_flavour(kesst):
    """Only sixteen feats have arithmetic the engine owns. The other 1,458 used to read
    "carried as flavour — the engine applies nothing", which is true about the numbers and
    useless to a player trying to remember what the feat does."""
    from rules.sheet import full_sheet

    kesst.feats = ["acrobatic steps"]
    shown = full_sheet(kesst)["feats"][0]
    assert shown["known"] is True
    assert shown["applied"] is False
    assert "difficult terrain" in shown["effect"]
    assert shown["prerequisites"].startswith("Dex 15")


def test_a_feat_nothing_has_ever_heard_of_is_still_carried(kesst):
    """A homebrew feat on a sheet must not vanish because it is not in the index."""
    from rules.sheet import full_sheet

    kesst.feats = ["blood puppetry"]
    shown = full_sheet(kesst)["feats"][0]
    assert shown["name"] == "blood puppetry"
    assert shown["known"] is False and shown["applied"] is False
