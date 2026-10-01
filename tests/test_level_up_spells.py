"""A new level owes a wizard's book two spells, and the player chooses them.

The owner, 2026-10-01: "leveled up as a wizard and did not choose new spells". The Core
Rulebook (Wizard, "Spells Gained at a New Level"): "Each time a character attains a new
wizard level, he gains two spells of his choice to add to his spellbook. The two free
spells must be of spell levels he can cast."

Measured on the owner's own save before the fix: Sam, a wizard with 2,600 XP, 35
cantrips and 13 first-level spells (3 + Int +10) — and nothing anywhere in the level-up
path (play/views.py `level_up`, rules/leveling.py `level_up`, the rest path in
rules/engine.py) that asked for, offered or counted a spell. The book stayed at its
forge size for every level the game could give.

What is pinned here: the owed count (two a level, from the class's casting data, never
from its name), the castable-level rule judged at the level each pick was earned, the
server's refusals with the fix named, the count surviving a save, an older save being
offered what it is owed, and the endpoints the Spells tab's picker uses.
"""
from __future__ import annotations

import json

import pytest

from rules import casting, creation, leveling, spells as spells_mod
from rules import xp as xp_mod
from rules.sheet import from_dict, full_sheet, to_dict


def forge_wizard():
    """A wizard as the forge builds one: every cantrip, and 3 + Int 5 = 8 first-level."""
    built, problems = creation.build({
        "name": "Sam Test", "race": "elf", "class": "wizard", "pronouns": "he/him",
        "abilities": {"str": 10, "dex": 10, "con": 10, "int": 18, "wis": 10, "cha": 10},
        "skills": ["appraise", "craft", "fly", "knowledge (arcana)",
                   "linguistics", "perception", "spellcraft"],
        "feats": ["toughness"],
        "spellbook": ["mage-armor", "magic-missile", "shield", "sleep",
                      "burning-hands", "charm-person", "grease", "enlarge-person"],
    })
    assert problems == [], problems
    return from_dict(built["sheet"], ref="pc")


def levelled(actor, to: int):
    while actor.level < to:
        actor.xp = xp_mod.total_for(actor.level + 1)
        got = leveling.level_up(actor)
        assert got["ok"], got
    return actor


def ids_at(level: int, n: int, actor) -> list[str]:
    """The first n wizard spells of a spell level not already in this book."""
    book = set(actor.spellbook)
    found = sorted(s.id for s in spells_mod.all_spells().values()
                   if s.lists.get("wizard") == level and s.id not in book)
    return found[:n]


# --- what a level owes ------------------------------------------------------------------

def test_a_new_wizard_owes_nothing_and_a_second_level_owes_two():
    """Before the fix the level-up record carried no spells at all: Sam went from 1 to 2
    and the book stayed 48 long. Two a level after the first, and each of a spell level
    castable then — at wizard 2 that is 1st level or lower."""
    w = forge_wizard()
    assert casting.learning(w)["owed"] == 0, "creation's picks are the forge's, not owed"
    w.xp = xp_mod.total_for(2)
    got = leveling.level_up(w)
    assert got["spells_owed"] == 2
    assert any("spellbook" in g for g in got["grants"]), got["grants"]
    owed = casting.learning(w)
    assert owed["kind"] == "book" and owed["owed"] == 2
    assert owed["picks"] == [{"for_level": 2, "max_level": 1}] * 2


def test_each_pick_is_judged_at_the_level_that_earned_it():
    """A wizard who reaches 3rd before choosing is owed four: two from 2nd that must be
    1st level or lower, two from 3rd that may be 2nd. Hero Lab's plan for the same
    allotment counts it "for the spell levels you would have had access to at the time"
    (forums.wolflair.com t=50834), and so does this: four 2nd-level spells are refused,
    two 1st and two 2nd are not."""
    w = levelled(forge_wizard(), 3)
    owed = casting.learning(w)
    assert [p["max_level"] for p in owed["picks"]] == [1, 1, 2, 2]

    seconds = ids_at(2, 4, w)
    problems = casting.learn_problems(w, seconds)
    assert any("owed for reaching level 2 must be level 1 or lower" in p
               for p in problems), problems

    added, problems = casting.learn(w, ids_at(1, 2, w) + ids_at(2, 2, w))
    assert problems == [] and len(added) == 4
    assert casting.learning(w)["owed"] == 0
    assert w.level_spells_taken == 4


def test_a_spell_above_what_the_level_can_cast_is_refused_with_the_fix():
    """"The two free spells must be of spell levels he can cast": fireball at wizard 2
    is refused, and the refusal says which level would be accepted."""
    w = levelled(forge_wizard(), 2)
    problems = casting.learn_problems(w, ["fireball"])
    assert problems == ["Fireball is a level 3 spell; the spell owed for reaching level 2 "
                        "must be level 1 or lower."]


def test_every_refusal_is_said_at_once_and_nothing_is_written():
    w = levelled(forge_wizard(), 2)
    before = list(w.spellbook)
    added, problems = casting.learn(
        w, ["magic-missile", "cure-light-wounds", "no-such-spell", "color-spray",
            "color-spray"])
    assert added == []
    joined = " ".join(problems)
    assert "chosen twice" in joined
    assert "5 spells against 2 owed" in joined
    assert "Magic Missile is already in the book" in joined
    assert "Cure Light Wounds is not on the wizard list" in joined
    assert "No spell called 'no-such-spell'" in joined
    assert w.spellbook == before and w.level_spells_taken == 0


def test_nothing_owed_is_refused_as_nothing_owed():
    w = forge_wizard()
    assert "no spells owed" in casting.learn_problems(w, ["color-spray"])[0]


def test_the_count_is_read_from_the_casting_data_not_the_class_name(monkeypatch):
    """Law 1: the engine names no class. Three a level, declared in the data, is three."""
    monkeypatch.setitem(casting.CASTERS["wizard"], "learns_per_level", 3)
    w = levelled(forge_wizard(), 2)
    assert casting.learning(w)["owed"] == 3


# --- what a save remembers ----------------------------------------------------------------

def test_the_count_survives_a_save():
    w = levelled(forge_wizard(), 3)
    casting.learn(w, ids_at(1, 2, w))
    again = from_dict(to_dict(w), ref="pc")
    assert again.level_spells_taken == 2
    assert casting.learning(again)["owed"] == 2


def test_a_save_from_before_the_count_is_offered_what_it_is_owed():
    """The owner had ALREADY levelled when this was reported, so an older save must be
    offered its picks. It cannot say which spells were free; the rule (documented on
    `casting.infer_level_spells_taken`) is the chosen book less the forge's allowance.
    A wizard 2 with the forge's eight first-level spells is owed two; one who somehow
    already holds ten is owed none."""
    w = levelled(forge_wizard(), 2)
    d = to_dict(w)
    # Absent at zero (written only when some were taken), which is exactly how a save
    # from before the count looks.
    d.pop("level_spells_taken", None)
    assert casting.learning(from_dict(dict(d), ref="pc"))["owed"] == 2

    d["spellbook"] = list(d["spellbook"]) + ids_at(1, 2, w)
    assert casting.learning(from_dict(dict(d), ref="pc"))["owed"] == 0


def test_a_repertoire_is_owed_what_its_spells_known_table_adds():
    """The same picker, generalised where the data already says it: a sorcerer's Spells
    Known table is 4 cantrips / 2 first at 1st and 5 / 2 at 2nd, so reaching 2nd owes
    one cantrip — and the tab's old Learn button, which took any castable spell with no
    count at all, now stops at the table."""
    built, problems = creation.build({
        "name": "Sorc Test", "race": "human", "class": "sorcerer", "pronouns": "she/her",
        "bonus_ability": "cha",
        "abilities": {"str": 10, "dex": 14, "con": 12, "int": 10, "wis": 10, "cha": 16},
        "skills": ["bluff"], "feats": ["toughness", "dodge"],
        "spellbook": ["acid-splash", "detect-magic", "light", "prestidigitation",
                      "magic-missile", "shield"],
    })
    assert problems == [], problems
    s = levelled(from_dict(built["sheet"], ref="pc"), 2)
    owed = casting.learning(s)
    assert owed["kind"] == "known" and owed["by_level"] == {0: 1}
    problems = casting.learn_problems(s, ["sleep"])
    assert problems == ["Sleep: the repertoire already holds every level 1 spell it may "
                        "at this level."], problems
    added, problems = casting.learn(s, ["ray-of-frost"])
    assert problems == [] and added == ["ray-of-frost"]
    assert casting.learning(s)["owed"] == 0


# --- over the wire, the way the Spells tab asks ----------------------------------------

@pytest.fixture
def wizard_table(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path)
    from play import campaign as campaign_mod

    w = forge_wizard()
    w.xp = xp_mod.total_for(2)
    return campaign_mod.begin_with(w)


def _post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def test_level_up_then_choose_two_on_the_spells_tab(client, wizard_table):
    """The path the player clicks: Take level 2 on the Class card, then the Spells tab's
    card — the count from /api/sheet, the list from /api/spells/learnable, the choice
    to /api/spells/learn — and the book grows by exactly two."""
    before = len(client.get("/api/sheet").json()["spells"]["known"])
    assert _post(client, "/api/level-up", {}).status_code == 200
    due = client.get("/api/sheet").json()["spells"]["to_learn"]
    assert due["owed"] == 2

    offered = client.get("/api/spells/learnable").json()["spells"]
    assert offered and all(s["level"] <= 1 for s in offered)
    book = {s["id"] for s in client.get("/api/sheet").json()["spells"]["known"]}
    assert not book & {s["id"] for s in offered}, "a spell already in the book was offered"

    firsts = [s["id"] for s in offered if s["level"] == 1][:2]
    res = _post(client, "/api/spells/learn", {"spells": firsts})
    assert res.status_code == 200, res.json()
    sheet = res.json()
    assert sheet["learned"] == firsts
    assert len(sheet["spells"]["known"]) == before + 2
    assert sheet["spells"]["to_learn"]["owed"] == 0

    again = _post(client, "/api/spells/learn", {"spells": [offered[-1]["id"]]})
    assert again.status_code == 400
    assert "no spells owed" in again.json()["error"]


def test_the_endpoint_refuses_with_the_fix_named(client, wizard_table):
    _post(client, "/api/level-up", {})
    res = _post(client, "/api/spells/learn", {"spells": ["fireball"]})
    assert res.status_code == 400
    assert "must be level 1 or lower" in res.json()["error"]
    res = _post(client, "/api/spells/learn", {"spells": "fireball"})
    assert res.status_code == 400 and "list of ids" in res.json()["error"]


def test_the_page_asks_where_the_server_answers():
    """The picker is wired to the two endpoints, and a guest on the LAN may post the
    choice the same as preparing."""
    from pagesource import table_source
    from pathfindergm import lan

    page = table_source()
    assert "/api/spells/learnable" in page and "/api/spells/learn" in page
    assert "learnCard(sp)" in page and "learnOwedLine(s)" in page
    assert lan.guest_may("POST", "/api/spells/learn")
