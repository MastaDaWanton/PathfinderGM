"""A cache keyed on id() holds the object it was built from (review 2026-11-11, finding 13).

`id()` is an address, and CPython hands a freed object's address to the next object of
the same size — which is exactly what a rebuilt table or a re-imported world is. Seven
caches were keyed on a bare id(): the narrator's vocabulary, the world search index, the
opening's name words, residency's places and roads, the weapon group and spelling
indexes, the stat-block parses, and the formula table. Each answered a new object with
what it had worked out for the dead one.

Address reuse cannot be forced, so each test forces the collision instead: the module's
`id` is replaced with one that gives every object the same address. Measured on 7f63ab60
with that in place: all eight tests below failed, each serving the first object's answer
for the second.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest


def _same_address(monkeypatch, module):
    monkeypatch.setattr(module, "id", lambda _obj: 7, raising=False)


def _world(word):
    return SimpleNamespace(
        name=word, secret="", premise={}, play={}, factions=[], chronology=[],
        entities={"e1": SimpleNamespace(
            id="e1", name=word, kind="settlement", summary="", prose="", facts={},
            sections=[], parent_id=None, places=[])})


@pytest.fixture
def boomstick(monkeypatch):
    """The weapon table rebuilt with one homebrew firearm in it, as the bench leaves it
    — the new table standing at the old one's address."""
    from rules import statblock_attacks, weapons

    _same_address(monkeypatch, weapons)
    _same_address(monkeypatch, statblock_attacks)
    old = weapons.all_weapons()
    assert weapons.groups_of("longsword") == {"heavy blades"}       # index built on `old`
    assert statblock_attacks.parse("boomstick +5 (1d8+3)")[0][0]["base"] == ""
    new = dict(old, boomstick=dict(old["longsword"], id="boomstick", name="Boomstick",
                                   section="Firearms"))
    monkeypatch.setattr(weapons, "_ALL", new)
    yield weapons, statblock_attacks
    statblock_attacks._parse_cached.cache_clear()
    monkeypatch.setattr(weapons, "_INDEX", None)
    monkeypatch.setattr(weapons, "_GROUP_INDEX", None)


def test_a_rebuilt_weapon_table_is_indexed_again(boomstick):
    weapons, _ = boomstick
    assert weapons.key_for("Boomstick") == "boomstick", "spellings read from the old table"
    assert weapons.groups_of("boomstick") == {"firearms"}, "groups read from the old table"


def test_a_rebuilt_weapon_table_is_parsed_against(boomstick):
    _, statblock_attacks = boomstick
    assert statblock_attacks.parse("boomstick +5 (1d8+3)")[0][0]["base"] == "boomstick", \
        "the parse made against the old table answered for the new one"


def test_forget_drops_the_group_index(monkeypatch):
    """`forget()` cleared `_ALL` and `_INDEX` and left `_GROUP_INDEX` standing, resting
    on the id() comparison alone to notice the new table."""
    from rules import weapons

    weapons.groups_of("longsword")
    assert weapons._GROUP_INDEX is not None
    weapons.forget()
    assert weapons._GROUP_INDEX is None and weapons._INDEX is None


def test_a_rebuilt_spell_corpus_rebuilds_the_formulae(monkeypatch):
    from rules import formulae, spells

    _same_address(monkeypatch, formulae)
    first = formulae._rows()
    monkeypatch.setattr(spells, "_ALL", dict(spells.all_spells()))
    assert formulae._rows() is not first, "the table derived from the old corpus was kept"
    formulae.refresh()


def test_the_search_index_is_the_world_asked_about(monkeypatch):
    from play import gm_search

    _same_address(monkeypatch, gm_search)
    gm_search.forget()
    con_a, _ = gm_search.index_for(_world("Ashford"))
    con_b, _ = gm_search.index_for(_world("Brackwater"))
    assert con_b is not con_a
    names = [r[0] for r in con_b.execute("SELECT name FROM docs")]
    assert names == ["Brackwater"]
    gm_search.forget()


def test_the_opening_reads_the_name_words_of_the_world_it_is_given(monkeypatch):
    from play import opening

    _same_address(monkeypatch, opening)
    monkeypatch.setattr(opening, "_NAME_WORDS", {})
    assert "Ashford" in opening._name_words(_world("Ashford"))
    assert opening._name_words(_world("Brackwater")) == {"Brackwater"}


def test_residency_derives_the_places_of_the_world_it_is_given(monkeypatch):
    from rules import residency

    _same_address(monkeypatch, residency)
    monkeypatch.setattr(residency, "_PLACES", {})
    monkeypatch.setattr(residency, "_ROADS", {})
    monkeypatch.setattr(residency, "_derive_places", lambda loc, world, founded: (world.name,))
    monkeypatch.setattr(residency, "_find_partners", lambda world, loc: {world.name})
    a, b = _world("Ashford"), _world("Brackwater")
    assert residency._places_of("town", a, []) == ("Ashford",)
    assert residency._places_of("town", b, []) == ("Brackwater",)
    assert residency._trade_partners(a, "town") == {"Ashford"}
    assert residency._trade_partners(b, "town") == {"Brackwater"}


def test_the_narrator_knows_the_words_of_the_world_and_the_shelf_it_has_now(monkeypatch):
    """The vocabulary decides which capitalised words the narrator invented. Besides the
    world, it folds in every ingredient's name — and kept them for the life of the
    process, so a herb added to the table was struck from the prose as an invented name
    however the table itself was refreshed."""
    from gm import agent as agent_mod
    from rules import ingredients

    _same_address(monkeypatch, agent_mod)
    monkeypatch.setattr(agent_mod.GMAgent, "_VOCAB", {})
    gm = object.__new__(agent_mod.GMAgent)
    gm.world = _world("Ashford")
    assert "Ashford" in gm._world_vocabulary()
    gm.world = _world("Brackwater")
    words = gm._world_vocabulary()
    assert "Brackwater" in words and "Ashford" not in words

    shelf = dict(ingredients.all_ingredients())
    shelf["zzyzxwort"] = SimpleNamespace(name="Zzyzxwort")
    monkeypatch.setattr(ingredients, "_ALL", shelf)
    assert "Zzyzxwort" in gm._world_vocabulary()
