"""Sifting mechanics out of ingredient prose.

The herb document is written for a person. A crafted item's card printed the whole
paragraph — flavour, folklore, unrelated uses and all — with the chain's potency stamped
on the end of every line. What the card has to say is *+2 Heal checks to staunch
bleeding*.

Every test here names a real entry from the corpus, because the corpus is the only thing
that decides whether an extractor works.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from rules import effects


def only(text: str) -> list[str]:
    return effects.summarise(text)


# --- the file itself ------------------------------------------------------------------

def test_no_control_characters_survive_in_the_module():
    """`\\b` in `_condition_pattern` was once written through a shell heredoc and arrived
    as a literal backspace byte. The pattern then matched nothing at all, silently, and
    every condition in the corpus went unextracted — no error, no traceback, just an
    empty list. It is the trap CLAUDE.md records, and this is the check that catches it."""
    raw = Path("rules/effects.py").read_bytes()
    for bad in (0x08, 0x07, 0x0b, 0x0c):
        assert bytes([bad]) not in raw, f"control byte {bad:#x} in rules/effects.py"


# --- bonuses and penalties -------------------------------------------------------------

def test_two_bonuses_in_one_sentence_are_both_kept():
    """Leechwort: "grants a +1 alchemical bonus on all Heal checks and a +2 alchemical
    bonus on Heal checks to staunch bleeding." The first match swallowed the second."""
    got = only("When applied to a wound, leechwort grants a +1 alchemical bonus on all "
               "Heal checks and a +2 alchemical bonus on Heal checks to staunch bleeding.")
    assert got == ["+1 Heal checks", "+2 Heal checks to staunch bleeding"]


def test_the_bonus_type_is_dropped_not_the_target():
    """The full stop in "vs." used to end the target, so the label came out "+2 saves vs".
    Normalised away before matching, which also loses the period — fine on a card."""
    assert only("gain a +2 alchemical bonus on saves vs. fear") == ["+2 saves vs fear"]


def test_a_penalty_reads_as_negative_however_it_is_written():
    assert only("they suffer a –2 penalty on all skill checks") == ["-2 skill checks"]
    assert only("imposing a -4 penalty to attack rolls") == ["-4 attack rolls"]


def test_a_label_is_cut_at_a_clause_not_mid_word():
    """Measured: "+2 Constitution checks made to resist subdual damage from making a
    forced" — the raw character cap stopped mid-phrase, which reads as a bug."""
    got = only("provides a +2 alchemical bonus to Constitution checks made to resist "
               "subdual damage from making a forced march")
    assert got == ["+2 Constitution checks"]


def test_a_trailing_pointer_back_into_the_prose_is_dropped():
    got = only("imposing a -4 penalty on intelligence-based checks during this time")
    assert got == ["-4 intelligence-based checks"]


# --- healing, damage, and the named mechanics --------------------------------------------

def test_healing_however_the_verb_is_spelled():
    assert "Heals 1d4 hit points" in only("Restores 1d4 hit points")
    assert "Heals 2 hit points" in only("granting fast healing 2 (regain 2 HP per round)")


def test_healing_stated_as_an_instruction_to_roll():
    """Comfrey and St John's-Wort state their healing as "roll 1-4 to see how many hit
    points were never done in the first place" and say nothing else mechanical."""
    assert "Heals 1-4 hit points" in only(
        "If root is applied immediately to a wound, roll 1-4 to see how many hit points "
        "\"were never done in the first place\" and subtract from damage taken.")


def test_temporary_hit_points_and_fast_healing_are_named_mechanics():
    got = only("granting 10 temporary hit points for 8 hours")
    assert got == ["10 temporary hit points for 8 hours"]
    assert "Fast healing 2 for 10 minutes" in only(
        "grants fast healing 2 for 10 minutes")


def test_ability_damage_does_not_read_as_hit_points():
    assert "1d6 Constitution damage" in only("or take 1d6 Con damage")
    assert "1d4 Intelligence damage (permanent)" in only(
        "primary damage 1d4 permanent Int damage")


def test_resistance_and_immunity():
    assert "Resist fire 10" in only("grants resistance to fire damage (10 points)")
    assert "Resist slashing 3 for 8 hours" in only(
        "granting 3 points of resistance against slashing damage for 8 hours")
    assert "Immune to fire damage for 2 hours" in only(
        "grants immunity to fire damage for 2 hours")


def test_percentages_are_kept_because_this_document_uses_them():
    """1e has none; the herb document has plenty."""
    assert "Bleeding damage 20% less" in only(
        "Bleeding damage is considered 20% less, reflecting damage that never took place")


def test_a_save_and_its_dc():
    assert "Fortitude DC 15" in only("must make a Fortitude save DC 15 or sleep")
    assert "DC 18" in only("These mushrooms are an ingested poison, DC 18")


def test_an_extra_save_granted_is_an_effect():
    """Easy to miss and worth a card line: Caranator's whole use is one extra save."""
    got = only("Chew a piece of root to clear the mind (gain a Will save vs. any charms "
               "or enchantments immediately.)")
    assert got and got[0].startswith("Another Will save")


# --- conditions ---------------------------------------------------------------------------

def test_the_documents_nouns_find_the_engines_adjectives():
    """Mad Cap says "confusion spell" and "unconsciousness"; the engine's conditions are
    `confused` and `unconscious`. Matching the exact key found neither, so a mushroom
    whose entire effect is a rage and then a coma extracted only its DC."""
    got = only("suffer from the effects of a confusion spell. A secondary effect is "
               "unconsciousness.")
    assert "Causes confused" in got
    assert "Causes unconscious" in got


def test_deadly_is_not_death():
    """"deadly nightshade" matched the `dead` condition through a loose stem — the worst
    kind of wrong, a mechanic on a card that the source never claimed."""
    assert not any("dead" in e.lower()
                   for e in only("A trained Herbalist can make the poison deadly "
                                 "nightshade using extracts of the plant"))


def test_an_effect_wearing_off_is_not_a_cure():
    """Allnight: "It eliminates the effects of fatigue for the next 8 hours; when the
    drug's effect ends, the user is exhausted." Reading "ends ... exhausted" as a cure
    inverted the herb: it *causes* exhaustion."""
    got = only("It eliminates the effects of fatigue for the next 8 hours; when the "
               "drug's effect ends, the user is exhausted.")
    assert "Ends fatigued" in got
    assert "Causes exhausted" in got
    assert "Ends exhausted" not in got


def test_a_duration_is_not_borrowed_from_another_clause():
    """Hydra Gall heals "1d4 HP per round for 5 rounds" and sickens "for 1 hour" in one
    sentence. Attaching the first duration to the condition was a confidently wrong
    number; saying nothing is the honest answer."""
    got = only("Hydra Gall heals 1d4 HP per round for 5 rounds, but causes nausea, "
               "imposing a -3 penalty to constitution-based checks for 1 hour.")
    assert "Causes nauseated" in got


# --- against the real corpus ---------------------------------------------------------------

@pytest.fixture
def shelf(db=None):
    from rules import ingredients

    return ingredients.all_ingredients()


def test_two_thirds_of_the_corpus_yields_a_mechanic(shelf):
    """The rest genuinely state none — "Root pulverized into a poultice that heals
    wounds" has no number in it — and those keep their prose instead."""
    with_mechanics = [i for i in shelf.values() if effects.extract(i.text)]
    assert len(with_mechanics) / len(shelf) > 0.6


def test_no_extracted_line_is_a_paragraph(shelf):
    """The whole point. A card line is a label, not a sentence."""
    for ing in shelf.values():
        for e in effects.extract(ing.text):
            assert len(e.text) <= effects.CARD_CHARS + 1, (ing.name, e.text)


def test_nothing_extracted_still_leaves_the_prose(shelf):
    from rules import crafting

    silent = next(i for i in shelf.values()
                  if i.forageable and not effects.extract(i.text))
    described = crafting.descriptions([silent])
    assert described and described[0]["text"] == silent.text


def test_the_potency_multiplier_is_not_stamped_on_every_line(shelf):
    """It is one property of the result, stated once beside the rarity and the DC.
    Repeating "[x0.80 from the chain]" on each effect was noise on every card."""
    from rules import crafting
    from rules.crafting import Chain

    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["mix"], ["leechwort", "comfrey"]))
    assert r.potency == pytest.approx(0.80)
    assert not any("from the chain" in e for e in r.effects)


def test_an_effect_says_which_ingredient_it_came_from(shelf):
    from rules import crafting
    from rules.crafting import Chain

    r = crafting.preview("herbalist", 1,
                         Chain("herbalist", ["grind"], ["leechwort"]))
    assert all(e.startswith("Leechwort: ") for e in r.effects)
