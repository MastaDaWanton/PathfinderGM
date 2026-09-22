"""A spontaneous caster's two allowances are two numbers.

Item 42 of the 2026-09-19 play-test, found while building the forge's picker:

> "`creation.SPELLS_KNOWN` gives a sorcerer `2` and a bard `4` as a single cap covering
> levels 0 and 1 together, so the forge offers 279 spells across both levels against two
> picks — and a player can spend both on cantrips and begin play with **no first-level
> spell at all**."

The book gives two separate allowances, and both classes the same ones:

  "A sorcerer begins play knowing four 0-level spells and two 1st-level spells of her
   choice."  (d20pfsrd, Sorcerer)
  "A bard begins play knowing four 0-level spells and two 1st-level spells of the bard's
   choice."  (d20pfsrd, Bard)

Both full tables were fetched from the SRD rather than recalled, because CLAUDE.md's own
warning is that a table like this is "90% right from memory" — and the 90% is the part
nobody notices.
"""
from __future__ import annotations

import pytest

from rules import casting, creation
from rules.bestiary import instantiate
from rules.engine import Scene


def _spec(**over):
    payload = {"name": "Test", "class": "sorcerer", "race": "human",
               "abilities": {"str": 10, "dex": 12, "con": 12,
                             "int": 12, "wis": 10, "cha": 16},
               "bonus_ability": "cha", "skills": ["bluff"],
               "feats": ["toughness", "skill focus"], "spellbook": [], "domains": [],
               "gender": "woman"}
    payload.update(over)
    return payload


class TestTheTable:
    def test_a_first_level_sorcerer_knows_four_cantrips_and_two_spells(self):
        assert creation.allowance("sorcerer", 1) == {0: 4, 1: 2}

    def test_a_first_level_bard_does_too(self):
        assert creation.allowance("bard", 1) == {0: 4, 1: 2}

    def test_the_wizards_cap_is_the_first_level_allowance_alone(self):
        """Its cantrips are a GRANT — "a spellbook containing all 0-level wizard
        spells" — and a grant is not a budget. Item 25's rule, kept."""
        assert creation.allowance("wizard", 1, int_mod=2) == {1: 5}
        assert 0 not in creation.allowance("wizard", 1, int_mod=2)

    def test_a_prepared_caster_chooses_nothing_here(self):
        assert creation.allowance("cleric") == {}
        assert creation.allowance("druid") == {}

    def test_both_tables_run_to_twenty_levels(self):
        for name, table in casting.KNOWN_TABLES.items():
            assert len(table) == 20, name
            assert all(len(row) == 10 for row in table), name

    def test_a_table_never_goes_backwards(self):
        """A spells-known ladder is monotonic in the book, and a transcription slip is
        exactly the kind of thing that reads fine and is wrong."""
        for name, table in casting.KNOWN_TABLES.items():
            for level in range(1, len(table)):
                for spell_level in range(10):
                    assert table[level][spell_level] >= table[level - 1][spell_level], \
                        f"{name} level {level + 1}, spell level {spell_level}"

    def test_the_table_is_read_by_class_level(self):
        assert creation.allowance("bard", 5) == {0: 6, 1: 4, 2: 3}
        assert creation.allowance("sorcerer", 4) == {0: 6, 1: 3, 2: 1}

    def test_an_actor_gets_the_same_answer_as_the_forge(self):
        """Two doors, one table: `casting.spells_known` for a character in play and
        `creation.allowance` for a draft that has no actor yet."""
        s = Scene()
        a = instantiate("guildhand", scene=s, name="S")
        a.char_class, a.level = "sorcerer", 5
        assert casting.spells_known(a) == creation.allowance("sorcerer", 5)


class TestTheForgeRefuses:
    def test_both_picks_on_cantrips_no_longer_builds(self):
        """The defect, exactly: a sorcerer who spent their allowance on cantrips passed
        every check and began play unable to cast a single first-level spell."""
        from rules import spells as spells_lib

        cantrips = [s.id for s in spells_lib.all_spells().values()
                    if isinstance(s.lists, dict) and s.lists.get("sorcerer") == 0]
        _, problems = creation.build(_spec(spellbook=sorted(cantrips)[:2]))
        assert any("level 1 spells" in p for p in problems), problems

    def test_too_many_cantrips_is_its_own_complaint(self):
        from rules import spells as spells_lib

        cantrips = sorted(s.id for s in spells_lib.all_spells().values()
                          if isinstance(s.lists, dict) and s.lists.get("sorcerer") == 0)
        firsts = sorted(s.id for s in spells_lib.all_spells().values()
                        if isinstance(s.lists, dict) and s.lists.get("sorcerer") == 1)
        _, problems = creation.build(_spec(spellbook=cantrips[:5] + firsts[:2]))
        assert any("cantrips against 4" in p for p in problems), problems

    def test_a_legal_book_builds(self):
        built, problems = creation.build(
            _spec(spellbook=creation.starter_spells("sorcerer")))
        assert problems == [], problems
        assert built is not None

    @pytest.mark.parametrize("cid", ["sorcerer", "bard"])
    def test_the_opening_book_fills_every_allowance(self, cid):
        from rules import spells as spells_lib

        book = creation.starter_spells(cid)
        every = spells_lib.all_spells()
        by_level: dict[int, int] = {}
        for sid in book:
            by_level.setdefault(every[sid].lists.get(cid), 0)
            by_level[every[sid].lists.get(cid)] += 1
        assert by_level == creation.allowance(cid, 1)

    def test_a_short_book_is_still_a_legal_shape(self):
        """`count` trims the book for callers that want a small one — and it fills the
        levels in order, so what comes back is never two cantrips and nothing to cast."""
        from rules import spells as spells_lib

        book = creation.starter_spells("sorcerer", count=5)
        every = spells_lib.all_spells()
        assert len(book) == 5
        assert sum(1 for s in book if every[s].lists.get("sorcerer") == 0) == 4


class TestTheForgeShowsIt:
    def _choices(self, cid="sorcerer"):
        return creation.spell_choices(_spec(**{"class": cid}))

    def test_one_budget_per_level_reaches_the_page(self):
        got = self._choices()
        assert got["caps"] == {"0": 4, "1": 2}

    def test_and_what_has_been_spent_of_each(self):
        from rules import spells as spells_lib

        cantrips = sorted(s.id for s in spells_lib.all_spells().values()
                          if isinstance(s.lists, dict) and s.lists.get("sorcerer") == 0)
        got = creation.spell_choices(
            _spec(**{"class": "sorcerer"}, spellbook=cantrips[:3]))
        assert got["chosen_by_level"] == {"0": 3}
        assert got["chosen"] == 3

    def test_the_wizard_still_shows_its_grant_apart_from_its_budget(self):
        got = self._choices("wizard")
        assert got["granted"] and got["caps"] == {"1": 4}
        assert all(r["level"] == 1 for r in got["choose"])

    def test_a_prepared_caster_says_so_rather_than_showing_an_empty_list(self):
        got = self._choices("cleric")
        assert got["prepares"] and not got["casts"]


class TestTheCountIsLive:
    """Reported 2026-09-22 with a screenshot: thirteen spells chosen and the budget
    reading **0 / 28**.

    The server's answer was right — measured on that draft, `chosen_by_level` came back
    `{"1": 13}` — and it was STALE. `loadChoices` refetches when the class or the
    abilities change, not when a spell is picked, so a budget that reads a server number
    is frozen at the moment of the last fetch while the chips beside it render from the
    form. The line this replaced counted `f.spellbook` locally and was live; making it
    read a server number is what broke it.
    """

    def _page(self) -> str:
        from pathlib import Path

        return Path("play/templates/play/home.html").read_text(encoding="utf-8")

    def test_the_budget_counts_the_form_and_not_the_last_fetch(self):
        page = self._page()
        assert "takenAt[lvl] = (takenAt[lvl] || 0) + 1" in page
        assert "for (const id of chosen)" in page

    def test_nothing_on_the_page_reads_the_servers_running_total(self):
        """The whole class of bug, pinned: any reader of `chosen_by_level` in the page
        is a number that stops updating the moment the player picks something."""
        assert "chosen_by_level" not in self._page()

    def test_the_server_still_answers_it_for_anybody_who_asks_once(self):
        """It is not wrong, it is just not live — and `build` and the tests above read
        it at a moment when it is exactly right."""
        from rules import spells as spells_lib

        firsts = sorted(s.id for s in spells_lib.all_spells().values()
                        if isinstance(s.lists, dict) and s.lists.get("sorcerer") == 1)
        got = creation.spell_choices(
            _spec(**{"class": "sorcerer"}, spellbook=firsts[:2]))
        assert got["chosen_by_level"] == {"1": 2}
