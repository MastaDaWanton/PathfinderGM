"""The /gm door knows the five crafts (owner's bug list 2026-11-17, item 19).

The owner asked: "Give the GM access to info on crafting mechanics so I can ask it
questions about the systems." Measured on 0.4.2 before this: the door could see places,
people, the sheet, spells and creatures and none of the benches, so "how does drying
work" reached the model with no crafting fact at all, and the in-app manual covered only
herbalism. These pin that a crafting question is grounded on the engine's own track and
the benches' own rule rows, and that nothing the character has not discovered rides
along (owner default, 2026-11-18).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from play import gm_answers
from rules import ingredients as ing_mod
from rules import knowledge, worldclass
from rules.engine import Scene
from rules.sheet import load_pc


def _campaign():
    s = Scene(location_id="here")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    return SimpleNamespace(scene=s), pc


def test_how_does_drying_work_is_grounded_on_the_dry_row():
    """The owner's own question. The model must be handed Dry's real row, read from
    content/rules/herbal-methods.json, with the time already in hours."""
    c, _pc = _campaign()
    row = gm_answers._bench_row("herbalist", "dry")
    facts = "\n".join(gm_answers.craft_facts(c, None, "how does drying work"))
    assert gm_answers.answer(c, None, "how does drying work")[0] == "gm"
    assert "STEP dry (level 2)" in facts
    assert f"minutes per batch: {row['minutes_per_batch']} " \
           f"({row['minutes_per_batch'] / 60:g} hours)" in facts
    # Only the method asked after, not every herbalism method.
    assert "STEP grind" not in facts


def test_the_next_level_is_read_off_the_engine_not_written_here():
    """The next level's price comes from `Track.to_next`, so feat/owner-crafting's new XP
    numbers reach the answer with no edit to this file."""
    c, pc = _campaign()
    track = worldclass.get("herbalist")
    progress = pc.track("herbalist")
    progress.mp = 7
    need = track.to_next(progress.level)
    facts = "\n".join(gm_answers.craft_facts(
        c, None, "what do I need for the next herbalism level"))
    assert f"costs {need} mastery: {need - 7} more to go" in facts
    assert "HOW EVERY CRAFT LEVELS" in facts


def test_the_forge_is_the_craft_not_only_its_forge_step():
    """"what does the forge do" names the craft; the method also called Forge must not
    narrow the answer to that one step."""
    c, _pc = _campaign()
    facts = "\n".join(gm_answers.craft_facts(c, None, "what does the forge do"))
    assert "CRAFT: Blacksmith" in facts
    # Measured live twice: handed every step's row, the model answered about the Forge
    # step. The craft's manual leads and the steps are named, never described one by one.
    assert facts.index("THE MANUAL ON BLACKSMITH") < facts.index("its steps, by level:")
    assert "smelt" in facts and "quench" in facts
    assert "STEP forge" not in facts
    assert "not the one step also called Forge" in facts


@pytest.mark.parametrize("section", ["herbalism", "forge", "alchemy", "leatherworking",
                                     "enchanting", "craft-levels"])
def test_every_craft_has_a_manual_section(section):
    """The manual covered only herbalism (item 19); the GM reads the same sections."""
    text = gm_answers.manual_section(section)
    assert text and "Homebrew" not in text


@pytest.mark.parametrize("question", ["who is here", "can I read the sign",
                                      "where can I buy rope", "what time is it"])
def test_ordinary_questions_are_not_about_crafting(question):
    """"read", "cut" and "mix" are bench methods and ordinary verbs; a question that is
    not about crafting must not get crafting facts."""
    assert not gm_answers.asks_about_crafts(question)


def test_a_herb_is_told_only_as_far_as_the_character_knows_it():
    """A met herb is named with its known lines only; a hidden property is counted, never
    told. An unmet herb is not named back at all."""
    c, pc = _campaign()
    herbs = [i for i in ing_mod.all_ingredients().values()
             if len(knowledge.property_keys(i)) >= 2 and " " not in i.name]
    met, unmet = herbs[0], herbs[1]
    keys = knowledge.property_keys(met)
    knowledge.reveal(pc, met.id, keys[:1], "test")
    lines, _spec = zip(*met.pairs)
    q = f"what can I craft with {met.name} and {unmet.name}"
    facts = "\n".join(gm_answers.craft_facts(c, None, q))
    assert lines[0] in facts
    assert all(line not in facts for line in lines[1:] if line != lines[0])
    assert f"{len(keys) - 1} more properties you have not learned" in facts
    assert f"HERB: {unmet.name}" not in facts
