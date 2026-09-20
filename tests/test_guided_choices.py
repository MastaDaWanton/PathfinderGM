"""The forge guides the two choices nobody can make from memory.

Reported 2026-09-20, with a screenshot of the forge showing "Search all 1,474 feats" and
"Spells known — level 0-1 wizard spells 0 / 28" over a box wanting comma-separated ids:

    "not only is the spells known broken, You should move these to a page of their own and
     show a list of feats that only includes feats they meet the prerequisites for. People
     do not usually know the feats without looking through them so the process needs
     guiding. same for spells... if its a wizard only spells from the wizard spell list
     should pop up and even that should be limited to whatever level spells need chosen."

What was measured before any of it was built:

* `feats.available` and parsed prerequisites already existed — 1,237 of the 1,474 feats
  carry structured conditions — and the forge called none of it.
* A 1st-level fighter qualifies for **145 of 1,474**. Ten to one, and a list a person can
  read.
* Wizard spells by level: **35** at 0 and **245** at 1, off `spell.lists`, so "only what
  this class can take, only at the levels it can cast" was already a query.
* The "0 / 28" was arithmetically right for that character's Intelligence (3 + Int mod)
  and wrong in kind: it is the FIRST-level allowance, and the 35 cantrips a wizard is
  granted were neither counted nor mentioned.

Prior art for the shape: Pathbuilder shows what you qualify for; D&D Beyond's builder is
the cautionary case, and its forums' two standing complaints are exactly the two reported
here — every spell level offered at 1st level, and no sight of your slots while choosing.
"""
from __future__ import annotations

import pytest

from rules import creation, feats as feats_mod


def draft(**over) -> dict:
    base = {"name": "Vess", "race": "human", "choices": ["int"], "class": "wizard",
            "gender": "woman", "pronouns": "she/her",
            "abilities": {"str": 10, "dex": 14, "con": 12,
                          "int": 16, "wis": 10, "cha": 10},
            "skills": ["spellcraft"], "feats": [], "spellbook": []}
    base.update(over)
    return base


FIGHTER = draft(**{"class": "fighter", "choices": ["str"],
                   "abilities": {"str": 15, "dex": 14, "con": 14,
                                 "int": 10, "wis": 12, "cha": 8}})


# --- feats -------------------------------------------------------------------------------

def test_the_open_list_is_a_fraction_of_the_whole():
    """145 of 1,474 for a first-level fighter, measured 2026-09-20. The forge offered all
    of them by name search, which is the wrong question asked of the wrong person."""
    got = creation.feat_choices(FIGHTER)
    assert got["ready"]
    assert 50 < len(got["open"]) < 400, len(got["open"])
    assert len(got["open"]) + len(got["shut"]) == len(feats_mod.all_feats())


def test_every_shut_feat_says_what_it_needs():
    """A list that only shows what you can have today hides the ladder you are climbing,
    so the rest stays reachable with the missing prerequisite named."""
    got = creation.feat_choices(FIGHTER)
    for row in got["shut"]:
        assert row["unmet"] or row["unknown"], row["name"]


def test_a_prerequisite_that_is_met_opens_the_feat_and_one_that_is_not_shuts_it():
    """Power Attack wants Strength 13, read AFTER the race is applied — which is the
    whole reason this is asked of an embodied draft rather than of the form."""
    strong = creation.feat_choices(FIGHTER)
    assert any(r["id"] == "power-attack" for r in strong["open"])
    weak = creation.feat_choices(draft(**{
        "class": "fighter", "choices": ["cha"],
        "abilities": {"str": 8, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 12}}))
    shut = next(r for r in weak["shut"] if r["id"] == "power-attack")
    assert any("str" in u.lower() or "strength" in u.lower() for u in shut["unmet"]), shut


def test_mythic_feats_are_never_offered():
    """Three of the 158 state no prerequisite at all — Extra Mythic Power, Mythic Paragon,
    Potent Surge — and were being offered to a first-level character in a game with no
    mythic tiers to spend. `feats.NOT_YET` already shuts the other 155 by treating a
    `mythic_tier` condition as uncheckable; this closes the gap those three walked
    through. Found 2026-09-20 while building the page."""
    got = creation.feat_choices(FIGHTER)
    assert not [r for r in got["open"] if "mythic" in [t.lower() for t in r["types"]]]
    myth = next(r for r in got["shut"] if r["id"] == "extra-mythic-power")
    assert any("mythic" in u.lower() for u in myth["unmet"]), myth


def test_a_draft_with_no_class_yet_says_so_rather_than_guessing():
    """The answer moves with the race, the class and the scores, so an incomplete draft
    gets an honest "not yet" instead of a list that would change under the player."""
    assert creation.feat_choices({"race": "human"})["ready"] is False
    assert creation.feat_choices({})["open"] == []


# --- spells ------------------------------------------------------------------------------

def test_only_this_class_at_only_the_levels_it_can_cast():
    """"if its a wizard only spells from the wizard spell list should pop up and even that
    should be limited to whatever level spells need chosen [lvl0-1 at first level]"."""
    from rules import spells as spells_lib

    got = creation.spell_choices(draft())
    assert got["casts"] and got["ready"]
    assert got["choose"], "nothing offered to a wizard"
    for row in got["choose"]:
        sp = spells_lib.get(row["id"])
        assert sp.lists.get("wizard") == 1, row["name"]
    assert all(spells_lib.get(r["id"]).lists.get("wizard") == 0 for r in got["granted"])


def test_the_cantrips_are_granted_and_the_cap_is_the_first_level_allowance():
    """The "0 / 28" that was reported. The number is 3 + Int mod and it counts FIRST-level
    spells; the 35 cantrips arrive free and the page says which is which."""
    got = creation.spell_choices(draft())
    assert len(got["granted"]) == 35, len(got["granted"])
    # Int 16 + 2 human = 18, mod +4, so 3 + 4.
    assert got["cap"] == 7


def test_the_slots_come_from_the_same_place_the_table_reads():
    """D&D Beyond's forums, on their own builder: the slots are not shown while you
    choose, so you pick blind. These are `casting.slots_for`, the function the play table
    uses, so the number here is the number there."""
    got = creation.spell_choices(draft())
    assert got["slots"].get("0") and got["slots"].get("1"), got["slots"]


def test_a_fighter_is_not_asked_for_spells():
    assert creation.spell_choices(FIGHTER)["casts"] is False


def test_a_wizard_who_chooses_nothing_is_still_refused():
    """The grant must not swallow the choice: cantrips arrive free, first-level spells do
    not, and `build` counts the ones that were chosen."""
    _, problems = creation.build(draft(spellbook=[], feats=["toughness"]))
    assert any("begins knowing spells" in p for p in problems), problems


def test_what_the_page_offers_is_what_the_build_accepts():
    """The end-to-end guard, and the disagreement this whole page exists to remove: every
    spell offered must be one the server will take, and a full pick must build."""
    got = creation.spell_choices(draft())
    picked = [r["id"] for r in got["choose"][:got["cap"]]]
    built, problems = creation.build(draft(spellbook=picked, feats=["toughness"]))
    assert problems == [], problems
    book = built["sheet"]["spellbook"]
    assert set(picked) <= set(book)
    assert len(book) == len(picked) + 35, "the granted cantrips did not arrive"


def test_one_more_than_the_cap_is_refused():
    got = creation.spell_choices(draft())
    picked = [r["id"] for r in got["choose"][:got["cap"] + 1]]
    _, problems = creation.build(draft(spellbook=picked, feats=["toughness"]))
    assert any("against" in p and "known" in p for p in problems), problems


# --- the endpoint ------------------------------------------------------------------------

def test_the_choices_endpoint_answers_both_halves():
    import json

    from django.test import Client

    r = Client().post("/api/character/choices", data=json.dumps(draft()),
                    content_type="application/json")
    assert r.status_code == 200
    d = r.json()
    assert d["feats"]["ready"] and d["spells"]["casts"]
    assert d["spells"]["cap"] == 7 and len(d["spells"]["granted"]) == 35


def test_the_endpoint_answers_a_draft_that_build_would_refuse():
    """The page has to work while the character is still illegal — no name, no skills —
    or it would be no help at all during the only moment it is needed."""
    import json

    from django.test import Client

    half = {"race": "human", "choices": ["str"], "class": "fighter",
            "abilities": {"str": 15, "dex": 12, "con": 12,
                          "int": 10, "wis": 10, "cha": 10}}
    assert creation.build(half)[1], "this draft should not build"
    r = Client().post("/api/character/choices", data=json.dumps(half),
                    content_type="application/json")
    assert r.status_code == 200 and r.json()["feats"]["ready"]


def test_a_prepared_caster_is_told_their_slots_even_though_they_choose_nothing():
    """A cleric declares no `spells_known` cap — she prepares from the whole class list —
    so the first build of this page showed her no spell section at all, which looks like a
    page that is broken rather than a rule that is being kept. Found in the browser
    2026-09-20. Half of what was asked for was "filling spell slots for the first session
    should be easy and intuitive", and that half applies to her too."""
    cleric = draft(**{"class": "cleric", "choices": ["wis"],
                      "abilities": {"str": 12, "dex": 10, "con": 12,
                                    "int": 10, "wis": 16, "cha": 12},
                      "skills": ["heal"]})
    got = creation.spell_choices(cleric)
    assert got["casts"] is False, "a cleric chooses no spells known at the forge"
    assert got["prepares"] is True
    assert got["slots"].get("0") and got["slots"].get("1"), got["slots"]
    assert got["choose"] == [] and got["granted"] == []


def test_a_non_caster_is_told_nothing_about_spells():
    """The other side of the same branch: a fighter has no slots, so `prepares` stays
    false and the page shows no spell section at all."""
    got = creation.spell_choices(FIGHTER)
    assert got["casts"] is False and got["prepares"] is False
    assert not got["slots"]


# --- browsing without typing -------------------------------------------------------------

def _page() -> str:
    from pathlib import Path

    return Path("play/templates/play/home.html").read_text(encoding="utf-8")


def test_the_lists_can_be_browsed_without_typing_a_word():
    """Reported 2026-09-20, after the first version of this page shipped: "because a
    player wont necessarily know the names of feats and spell they need to be able to find
    it without typing anything. keep the typing as an option but make a better way."

    The first cut capped the list at 60 rows and said "narrow the search", which is the
    one instruction a player who does not know the names cannot follow.

    Nielsen Norman settles the shape, and it is not infinite scroll: that "is less suited
    to support specific tasks such as finding a particular item" and "results in a lack of
    landmarks to help users orient themselves, whereas with pagination, users may remember
    the page that an item was on". What makes a long list findable in the same research is
    filters and a visible count — so the chips do the real work and the pages carry the
    browsing, and the search box stays as one way in among three.
    """
    page = _page()
    assert "function pager(" in page and "function chips(" in page
    assert "data-crchip" in page and "data-crpagemove" in page
    assert "PAGE_ROWS = 40" in page, "NN/g's ceiling for a filtered listing page"
    # The typing stays.
    assert 'id="featsearch"' in page and 'id="spellsearch"' in page


def test_changing_the_filter_returns_to_the_first_page():
    """Page four of a list that just became eleven items long is an empty screen, which
    reads as a broken page rather than an emptied filter."""
    page = _page()
    for line in ("FORGE.featType = FORGE.featType === key ? \"\" : key;",
                 "FORGE.spellSchool = FORGE.spellSchool === key ? \"\" : key;"):
        assert line in page
    assert page.count("FORGE.featPage = 1") >= 3, "chip, search and the shut-list toggle"
    assert page.count("FORGE.spellPage = 1") >= 2


def test_the_counts_the_chips_show_come_from_the_whole_reachable_list():
    """A count that moves as you type is not a landmark. The chips are counted over
    everything the character could reach, before the search narrows anything."""
    page = _page()
    assert "// Counted over everything this character could reach" in page


def test_the_everything_chip_is_a_headcount_and_not_a_sum_of_the_others():
    """A feat can carry two types and is counted under both, so adding the per-type chips
    up is not how many feats there are: with the shut list showing, the "everything" chip
    read **1476** where 1,474 feats exist. Measured in the browser 2026-09-20. The
    per-type numbers were right; only their sum was not a headcount."""
    page = _page()
    assert "function chips(counts, active, kind, total)" in page
    assert "const all = total;" in page
    assert 'chips(counts, kind, "feat", pool.length)' in page
    assert 'chips(counts, kind, "spell", pool.length)' in page


def test_a_mythic_feat_says_so_in_its_name():
    """148 feats share a display name with their mythic namesake — `feats.by_name` already
    has to prefer the ordinary one for exactly this reason. With the shut list showing,
    that put two rows called "Acrobatic" on screen, which reads as a glitch even though the
    second says what it needs. Seen in the browser 2026-09-20; 148 duplicate names down to
    9, and the nine that remain are the corpus's own."""
    got = creation.feat_choices(FIGHTER)
    names = [r["name"] for r in got["open"] + got["shut"]]
    assert "Acrobatic (mythic)" in names and "Acrobatic" in names
    import collections

    dupes = [n for n, c in collections.Counter(names).items() if c > 1]
    assert len(dupes) < 20, dupes
