"""Every caster, 1 to 20, through the real endpoints, with every choice made — and the
Spells tab's numbers held to the book's tables at every level.

The class audit (docs/class-audit.md §2-3) climbed 36 characters and checked feats and
points; lane 1 re-ran it with choices and skill ranks. Neither checked what a CHOICE does
to casting, because nothing did anything: a domain slot was a number nothing could fill,
a specialist had no school slot, a bloodline's nine spells were never known, and a
paladin with Cha 18 had no slot at 4th, 7th's 2nd or 10th's 3rd (D9). This walks the
seven casters up through `/api/level-up` and the Class tab's own endpoints, makes every
pick the levels owe, and at every level compares `/api/sheet`'s `spells` against:

  * slots per day — the book's base table plus the bonus spells of the casting score as
    it stands that level (points placed raise it). The full, sorcerer and bard tables
    are `rules/casting.py`'s, checked cell by cell against d20pfsrd by the audit; the
    paladin/ranger table is typed again below, because the code's copy was the wrong one.
  * the domain slot (cleric, the Air druid) and the specialist's school slot: one per
    spell level castable, from 1st.
  * spells known (sorcerer, bard): the Spells Known table exactly, after the owed picks,
    with the bloodline's spells on top — one at 3rd and every odd level after.
  * the wizard's book: two a level.
  * the granted powers: a bloodline's at 1, 3, 9, 15 and 20; a school's at 1 and 8.
"""
from __future__ import annotations

import json

import pytest

from rules import casting, creation, grantedpowers, leveling
from rules import xp as xp_mod

from tests.test_class_choices_and_levelup import _settle

BOOK_FOUR = {4: [0], 5: [1], 6: [1], 7: [1, 0], 8: [1, 1], 9: [2, 1], 10: [2, 1, 0],
             11: [2, 1, 1], 12: [2, 2, 1], 13: [3, 2, 1, 0], 14: [3, 2, 1, 1],
             15: [3, 2, 2, 1], 16: [3, 3, 2, 1], 17: [4, 3, 2, 1], 18: [4, 3, 2, 2],
             19: [4, 3, 3, 2], 20: [4, 4, 3, 3]}

ABILITY = {"cleric": "wis", "druid": "wis", "ranger": "wis", "wizard": "int",
           "sorcerer": "cha", "bard": "cha", "paladin": "cha"}

CHOICES = {
    "cleric": {"domains": ["Animal", "Sun"]},
    "druid": {"domains": ["Air"], "class_choices": {"nature bond": {"option": "domain"}}},
    "sorcerer": {"class_choices": {"bloodline": {"pick": "draconic", "variant": "red"}}},
    "wizard": {"class_choices": {"arcane school": {"pick": "evocation"},
                                 "opposition schools": {"picks": ["necromancy",
                                                                  "enchantment"]},
                                 "arcane bond": {"pick": "familiar", "variant": "cat"}}},
    "bard": {}, "paladin": {}, "ranger": {},
}


def _post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


@pytest.fixture
def isolated(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    return tmp_path


def _book_slots(cls: str, level: int, score: int) -> dict[int, int]:
    data = casting.CASTERS[cls]
    mod = (score - 10) // 2
    if data["progression"] == "four_level":
        row = {i: n for i, n in enumerate(BOOK_FOUR.get(level, []), start=1)}
    else:
        table = casting.PROGRESSIONS[data["progression"]][level - 1]
        row = {i: n for i, n in enumerate(table) if n > 0}
    out = {}
    for lvl, base in row.items():
        if score < 10 + lvl:
            continue
        n = base + casting.bonus_slots(mod, lvl)
        if n > 0:
            out[lvl] = n
    return out


@pytest.mark.parametrize("cls", sorted(CHOICES))
def test_a_caster_climbs_one_to_twenty_with_the_books_slots_at_every_level(
        client, isolated, cls):
    from play import campaign as campaign_mod

    ability = ABILITY[cls]
    body = {"name": f"Climb {cls}", "race": "human", "class": cls, "gender": "woman",
            "abilities": {"str": 10, "dex": 14, "con": 12, "int": 12, "wis": 12, "cha": 12,
                          ability: 15},
            "choices": [ability], "skills": ["perception"], "feats": [],
            "domains": creation.starter_domains(cls),
            "spellbook": creation.starter_spells(cls, 1), "begin": True}
    body.update(CHOICES[cls])
    res = _post(client, "/api/character/create", body)
    assert res.status_code == 200, res.json()
    _settle(client)
    seen_powers = []
    for level in range(1, 21):
        if level > 1:
            c = campaign_mod.current()
            pc = c.scene.pc()
            pc.xp = xp_mod.total_for(level)
            c.save()
            res = client.post("/api/level-up")
            assert res.status_code == 200, res.json()
        sheet = _settle(client)
        pc = campaign_mod.current().scene.pc()
        sp = sheet["spells"] or {}
        score = pc.ability_score(ability)
        got = {row["level"]: row["max"] for row in sp.get("slots") or []}
        want = _book_slots(cls, level, score)
        if casting.CASTERS[cls]["kind"] == "prepared" and want:
            want.setdefault(0, 0)
            got.setdefault(0, 0)
            want[0] = casting.PROGRESSIONS[casting.CASTERS[cls]["progression"]][level - 1][0]
            got[0] = {row["level"]: row["max"] for row in sp.get("slots") or []}.get(0, 0)
        if casting.CASTERS[cls]["kind"] != "prepared" and 0 in got:
            want[0] = got[0]               # a spontaneous caster's cantrips are at will
        assert {k: v for k, v in got.items() if v} == {k: v for k, v in want.items() if v}, \
            (cls, level, score, got, want)
        castable = sorted(lvl for lvl in want if lvl > 0)
        special = {(r["kind"], r["level"]) for r in sp.get("special_slots") or []}
        if cls in ("cleric", "druid"):
            assert special == {("domain", lvl) for lvl in castable}, (cls, level, special)
            assert all(r["choices"] for r in sp["special_slots"]), (cls, level)
        elif cls == "wizard":
            assert special == {("school", lvl) for lvl in castable}, (level, special)
            assert sp["school"] == {"specialist": "evocation",
                                    "opposition": ["enchantment", "necromancy"]}
        else:
            assert not special
        if cls in ("sorcerer", "bard"):
            # "To learn or cast a spell, a sorcerer must have a Charisma score equal to at
            # least 10 + the spell level" (CRB): the harness places its points in Int, so
            # a Cha 17 sorcerer at 16th knows no 8th-level spell, as the book says.
            table = {lvl: n for lvl, n in casting.known_row(casting.CASTERS[cls],
                                                            level).items()
                     if score >= 10 + lvl}
            have: dict[int, int] = {}
            for sid in pc.spellbook:
                lvl = casting.level_on_list(__import__("rules.spells", fromlist=["x"])
                                            .all_spells().get(sid), cls)
                have[lvl] = have.get(lvl, 0) + 1
            assert {k: v for k, v in have.items() if v} == table, (cls, level, have, table)
            if cls == "sorcerer":
                assert len(sp["granted"]) == len([n for n in range(3, level + 1, 2)]), \
                    (level, sp["granted"])
                assert sp["swaps"]["open"] == list(range(4, level + 1, 2))
            else:
                assert sp["swaps"]["open"] == list(range(5, level + 1, 3))
        if cls == "wizard":
            assert pc.level_spells_taken == 2 * (level - 1)
        powers = [p["name"] for p in sheet.get("domain_powers") or []]
        seen_powers.append(len(powers))
    if cls == "sorcerer":
        # Claws at 1, Dragon Resistances at 3, Breath Weapon at 9, Wings at 15, Power of
        # Wyrms at 20.
        assert [seen_powers[n - 1] for n in (1, 3, 9, 15, 20)] == [1, 2, 3, 4, 5]
        assert pc.resistance("fire") == 10 and pc.immune_to("fire")
    if cls == "wizard":
        assert [seen_powers[n - 1] for n in (1, 8)] == [3, 4]   # two school powers + bond
    if cls == "cleric":
        # Animal and Sun at 1 (Speak with Animals, Sun's Blessing); Animal Companion at 4;
        # Nimbus of Light at 8 — and the companion was chosen through the Class tab.
        assert [seen_powers[n - 1] for n in (1, 4, 8)] == [2, 3, 4]
        assert pc.class_choices.get("domain companion")
    assert leveling.owed(pc)["outstanding"] == 0
    assert grantedpowers.validate() == []
