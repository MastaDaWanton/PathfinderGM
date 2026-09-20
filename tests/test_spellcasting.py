"""Group 12 of the 2026-09-19 fix pass: spellcasting, and the cleric's own table.

Reported (docs/playtest-2026-09-18.md items 25, 26, and the cleric half of 27):
*"Spellcasting is broken in general. A lvl 1 cleric can cast wall of flame at 6th level."*
*"This spells panel should show a list of all known spells as well."* *"oh i had forgotten
domains those need chosen at creation as well."*

**The engine's gate was never the fault.** `_check_cast` makes nine checks including caster
level and refuses live — "Flame Strike is a level 5 spell and Ted is a level 1 cleric". The
proof it was never reached is on the player's own screen: after the wall of flame the panel
still read Spell Slot 0: 3 of 3, Spell Slot 1: 4 of 4. Nothing was cast.

The chain: the prepared check fired only for `prepare_from == "spellbook"`, so a cleric,
druid, paladin or ranger prepared nothing ever; `inject_cast` built its vocabulary from
`spellbook + prepared`, which are empty for all of them, so no `cast` op was ever emitted;
and the brief told the model nothing about spells at all, so there was nothing to hold it
to. Three links, each of which had to be fixed for any of it to work.
"""
from __future__ import annotations

import pytest

from gm import judgement, narration, prompts
from rules import casting, creation, domains
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import from_dict, full_sheet
from world import loader

WORLD = loader.load_cached("fixtures/aurvantis-campaign.json")
TOWN = WORLD.by_name("Vormoor", kind="CITY").id


def _make(cid: str, **over):
    payload = {"name": "Ted", "race": "human", "bonus_ability": "wis", "class": cid,
               "pronouns": "he/him", "skills": [], "feats": [],
               # Inside the 20-point budget the forge enforces.
               "abilities": {"str": 10, "dex": 12, "con": 12, "int": 10, "wis": 16,
                             "cha": 10},
               "spellbook": creation.starter_spells(cid, int_mod=2),
               "domains": creation.starter_domains(cid)}
    payload.update(over)
    built, problems = creation.build(payload)
    assert problems == [], problems
    return from_dict(built["sheet"], ref="pc")


@pytest.fixture
def cleric():
    pc = _make("cleric")
    scene = Scene(location_id=TOWN)
    scene.add(pc)
    return pc, scene, Engine(scene, Dice(seed=1), world=WORLD)


# --- 25: the declaration reaches the engine ------------------------------------------------

def test_a_cleric_has_a_vocabulary_at_all(cleric):
    """`inject_cast` read `spellbook + prepared`, and both are empty for the life of a
    cleric — so "I cast X" was never an intent and fell through to prose."""
    pc, scene, _ = cleric
    assert pc.spellbook == [] and pc.prepared == {}, "a cleric carries no book"
    raw = judgement.inject_cast([], "I cast cure light wounds on myself", scene)
    assert raw and raw[0]["op"] == "cast"
    assert raw[0]["params"]["spell"] == "cure-light-wounds"


def test_the_gate_refuses_what_was_not_prepared_and_says_so(cleric):
    """The check fired for `prepare_from == "spellbook"` — wizards — and for nobody else."""
    pc, scene, engine = cleric
    with pytest.raises(IntentError) as caught:
        engine.validate([{"op": "cast", "actor": "pc",
                          "params": {"spell": "cure-light-wounds", "at": "pc"}}])
    assert "did not prepare" in str(caught.value)


def test_the_caster_level_refusal_is_finally_reachable(cleric):
    """The reported bug, in one line: a level 1 cleric and a level 5 spell. The engine has
    always refused this; nothing ever knocked on the door."""
    pc, scene, engine = cleric
    with pytest.raises(IntentError) as caught:
        engine.validate([{"op": "cast", "actor": "pc",
                          "params": {"spell": "flame-strike", "at": "pc"}}])
    said = str(caught.value)
    assert "level 5" in said and "level 1" in said


def test_a_prepared_spell_casts_and_spends_both_the_slot_and_the_copy(cleric):
    pc, scene, engine = cleric
    casting.prepare(pc, "bless", 1)
    before = casting.slots_left(pc, 1)
    engine.run(engine.validate([{"op": "cast", "actor": "pc",
                                 "params": {"spell": "bless", "at": "pc"}}]))
    assert casting.prepared_count(pc, "bless") == 0, "the prepared copy is spent"
    assert casting.slots_left(pc, 1) == before - 1


def test_a_cure_may_be_cast_in_place_of_a_prepared_spell(cleric):
    """The Core Rulebook's exception, and the player's own rule: "may use a slot at any
    time for a healing spell of that slot level". Alignment is deliberately not consulted
    — "don't worry about the gods or the alignment"."""
    pc, scene, engine = cleric
    casting.prepare(pc, "bless", 1)
    pc.hp = 3
    assert casting.converts_spontaneously(pc, __import__("rules.spells", fromlist=["x"]).get("cure-light-wounds"))
    assert casting.sacrifice_for(pc, 1) == "bless"
    res = engine.run(engine.validate([{"op": "cast", "actor": "pc",
                                       "params": {"spell": "cure-light-wounds", "at": "pc"}}]))
    assert pc.hp > 3, "the wound closed"
    assert casting.prepared_count(pc, "bless") == 0, "bless paid for it"
    assert any("gives up Bless" in o.tell for o in res.outcomes), "and the page says so"


def test_a_wizards_book_opens_with_every_cantrip(cleric):
    """"A wizard begins play with a spellbook containing all 0-level wizard spells… plus
    three 1st-level spells of her choice… for each point of Intelligence bonus." Measured
    2026-09-19: a new wizard's book held one orison and five first-level spells."""
    from rules import spells as spells_mod

    # The book is built for an Intelligence bonus of 2, which is what the forge passes:
    # three plus the bonus is five first-level spells, and every cantrip beside them.
    pc = _make("wizard", bonus_ability="int",
               abilities={"str": 10, "dex": 12, "con": 12, "int": 16, "wis": 12, "cha": 10})
    at = {}
    for sid in pc.spellbook:
        at.setdefault(spells_mod.get(sid).lists.get("wizard"), []).append(sid)
    assert len(at[0]) > 20, "every 0-level wizard spell in the corpus"
    assert len(at[1]) == 5, "three plus the Intelligence bonus of 2"
    # And the cap counts the first-level ones only, which is what the book says: a legal
    # opening book was refused as "38 spells against 4 known" before 2026-09-19.
    assert len(pc.spellbook) > 30


def test_the_brief_says_what_can_be_cast(cleric):
    """It said nothing at all about spells — not the slots, not the prepared list, not even
    that the character is a caster. With no spell facts there was nothing to hold the model
    to, which is how "wall of flame" got written over full slots."""
    pc, scene, _ = cleric
    casting.prepare(pc, "bless", 1)
    brief = prompts.scene_brief(WORLD, scene, WORLD.get(TOWN), [])
    assert "CAN CAST" in brief
    assert "Prepared today: Bless" in brief
    assert "Slots left: level 0:" in brief


def test_prose_claiming_a_spell_nobody_cast_is_cut():
    """The deterministic backstop, the same shape as `wrong-hands`: the engine is the only
    thing that casts a spell, so prose asserting one it did not cast is asserting an
    outcome that never happened."""
    beat = ("Ted raises his holy symbol and casts wall of flame, and the raiders recoil. "
            "The market goes quiet around him.")
    text, cut = narration.cut_uncast_spells(beat, [])
    assert len(cut) == 1 and "wall of flame" in cut[0]
    assert text == "The market goes quiet around him."
    # A spell the engine DID cast is left alone, and so is one merely mentioned.
    kept = "Ted casts cure light wounds, and the wound closes."
    assert narration.cut_uncast_spells(kept, ["Cure Light Wounds"]) == (kept, [])
    asked = "He asks whether you know magic missile."
    assert narration.cut_uncast_spells(asked, []) == (asked, [])


# --- 26: the panel shows what can be chosen --------------------------------------------

def test_the_panel_lists_what_a_list_caster_may_prepare(cleric):
    """The panel offered a `+` only on rows already in the book, so a cleric saw a wizard's
    empty-book message for the life of the character. The numbers were always right — three
    orisons, four first-level slots, DC 21 — there was simply no door."""
    pc, scene, _ = cleric
    sheet = full_sheet(pc)["spells"]
    groups = {g["level"]: g for g in sheet["choose_from"]}
    assert groups[0]["total"] == 20, "the orisons on the cleric list"
    assert groups[1]["total"] == 159, "and the first-level spells"
    assert groups[0]["castable"] and groups[1]["castable"]
    assert len(groups[1]["spells"]) < groups[1]["total"], "a page of them, and a search"


def test_known_spells_answers_for_every_kind_of_caster():
    cleric_pc = _make("cleric")
    wizard = _make("wizard", bonus_ability="int",
                   abilities={"str": 10, "dex": 12, "con": 12, "int": 15, "wis": 12,
                              "cha": 10})
    theirs = casting.known_spells(cleric_pc, up_to=1)
    assert len(theirs[1]) > 100, "a cleric's god is the book"
    book = casting.known_spells(wizard, up_to=1)
    assert {s.id for lv in book.values() for s in lv} <= set(wizard.spellbook), \
        "a wizard's book is the book, and nothing else"


# --- 27's cleric half: domains, and a real class table -----------------------------------

def test_the_domains_are_derived_from_the_corpus_not_authored():
    """153 distinct domain names across 452 spells, carried on the spell as "Luck (2)" —
    so every domain's list is a query and nothing needed transcribing."""
    assert len(domains.names()) == 153
    assert domains.spells_of("Healing", 1) == ["cure-light-wounds"]
    assert len(domains.spells_of("War")) >= 9


def test_a_cleric_takes_two_domains_and_is_refused_without_them():
    """Refused the way a wizard with an empty book is refused, which is the precedent."""
    _, problems = creation.build({
        "name": "No domains", "race": "human", "bonus_ability": "wis", "class": "cleric",
        "pronouns": "she/her", "skills": [], "feats": [],
        "abilities": {"str": 10, "dex": 12, "con": 12, "int": 10, "wis": 16, "cha": 10}})
    assert any("takes 2 domains" in p for p in problems)
    assert domains.problems(["Healing", "Healing"], "cleric") == \
        ["The two domains must be different."]
    assert domains.problems(["Healing", "War"], "fighter") == ["A fighter takes no domains."]
    # No deity and no alignment anywhere in it. The ruling, 2026-09-19: "grab whatever the
    # belief system of the world is and let that be enough."
    src = open("rules/domains.py", encoding="utf-8").read()
    assert "deity" not in src.lower().split("no deity")[0]


def test_the_domain_slot_is_its_own_row(cleric):
    """"A cleric also gets one domain spell slot for each level of cleric spell she can
    cast, from 1st on up." Held apart from the ordinary slots because only a domain spell
    goes in it — a cleric shown "4 of 4" who can use three of them has been told a lie."""
    pc, scene, _ = cleric
    assert domains.of(pc) == creation.starter_domains("cleric")
    extra = casting.domain_slots_for(pc)
    assert extra == {1: 1}, "one at every castable level above orisons"
    sheet = full_sheet(pc)["spells"]
    assert sheet["domain_slots"] == [{"level": 1, "max": 1}]
    assert [d["name"] for d in sheet["domains"]] == domains.of(pc)


def test_a_domain_slot_is_never_spent_on_a_conversion(cleric):
    """The book's own exception to the exception: spontaneous conversion may not spend a
    domain slot, and a domain spell is the one thing a cleric prepared for a reason."""
    pc, scene, _ = cleric
    pc.prepared = {"domain:bless": 1}
    assert casting.sacrifice_for(pc, 1) == "", "the domain slot is not on offer"


def test_the_cleric_has_a_class_table_at_last():
    """The Class tab printed twenty rows of "—": cleric, fighter, wizard and rogue lived in
    `tables.CLASSES` with no `levels` table at all, so no channel energy, no domains, no
    spontaneous casting (item 27)."""
    from rules import classes

    doc = classes.all_classes()["cleric"]
    assert len(doc.get("levels") or []) == 20
    first = classes.features_at("cleric", 1)
    assert "channel energy 1d6" in first and "domains" in first
    assert "spontaneous casting" in first
    assert "channel energy 2d6" in classes.features_at("cleric", 3)
    # And the armour a cleric actually has: the stub said "simple" and nothing else.
    assert "medium armor" in doc["proficiencies"] and "shields" in doc["proficiencies"]
