"""A creature's printed defences, converted into specs and honoured by the engine.

The defect this closes, measured before the change: `rules/bestiary._NOT_ON_THE_SHEET`
dropped `immune`, `resist`, `weaknesses` and `senses` when a stat block became an `Actor`,
and `Actor` had no field for any of them. So 4,673 immunity terms, 2,074 resistances and
402 vulnerabilities sat in `content/bestiary/` being read by nothing, and:

- a frost giant took 20 damage from a 20-point cold attack;
- a salamander took full fire damage;
- an abominable snowman took 20 from fire rather than 30.

`reductions` is deliberately *not* part of this. It has been structured, loaded and applied
since the beginning, and converting it too would put the same fact in two places — which
CLAUDE.md names as the reason a fix ships from the copy nobody looked at.
"""
from __future__ import annotations

import pytest

from rules import bestiary, creature_effects as ce, effectspec
from rules.sheet import from_dict, to_dict


# --- reading the stat block ------------------------------------------------------------

def test_an_immunity_becomes_an_immunity():
    specs = ce.from_creature({"immune": ["cold", "undead traits"]})
    assert specs == [{"type": "immunity", "target": "cold"},
                     {"type": "immunity", "target": "undead traits"}]


def test_a_resistance_carries_its_number():
    specs = ce.from_creature({"resist": ["fire 10", "acid 5"]})
    assert specs == [{"type": "resistance", "target": "fire", "amount": 10},
                     {"type": "resistance", "target": "acid", "amount": 5}]


def test_the_bestiary_spells_negative_energy_out_and_the_schema_does_not():
    assert ce.from_creature({"resist": ["negative energy 30"]}) == [
        {"type": "resistance", "target": "negative", "amount": 30}]


def test_a_vulnerability_is_read_off_either_spelling():
    """The two sources write it both ways — "vulnerable to fire" on 88 creatures and
    "vulnerability to cold" on 40 — and a rule that reads one spelling silently makes a
    third of the vulnerable creatures ordinary."""
    for text in ("vulnerable to fire", "vulnerability to fire", "Vulnerable to fire"):
        assert ce.from_creature({"weaknesses": text})[0] == {
            "type": "vulnerability", "target": "fire"}


def test_a_weakness_that_is_not_a_damage_type_is_kept_as_prose():
    """"vulnerable to critical hits" and "light sensitivity" are real and are not energy.
    Dropping them because the schema has no slot would quietly make the creature tougher."""
    specs = ce.from_creature({"weaknesses": "vulnerable to critical hits, light sensitivity"})
    assert {s["type"] for s in specs} == {"narrative"}
    assert any("critical hits" in s["target"] for s in specs)
    assert any("light sensitivity" in s["target"] for s in specs)


def test_senses_are_read_with_their_range():
    specs = ce.from_creature({"senses": "darkvision 60 ft., low-light vision; Perception +10"})
    assert {"type": "sense", "target": "darkvision", "range": 60} in specs
    assert {"type": "sense", "target": "low_light"} in specs


def test_a_sense_the_schema_cannot_hold_is_not_bent_into_the_nearest_one():
    """Blindsight is not blindsense — one needs no other sense and the other still misses
    a silent motionless target — and 157 creatures have it. Filing it as blindsense would
    make every one of them harder to hide from than the book says."""
    specs = ce.from_creature({"senses": "blindsight 60 ft."})
    assert specs == [{"type": "narrative", "target": "blindsight 60 ft."}]


def test_every_spec_the_converter_makes_passes_the_schema():
    """A run over the whole bestiary rather than a sample: 18,000 specs across 7,133
    creatures, and a converter that produces one the editor cannot open is a conversion
    nobody can undo."""
    bad = []
    for creature in bestiary.imported().values():
        for spec in ce.from_creature(creature):
            bad += effectspec.validate(spec)
    assert bad == []


def test_damage_reduction_is_left_where_it_already_works():
    """It is structured at the source, loaded onto `Actor.reductions` and applied in
    `take_damage` already. A second copy inside `effects` would disagree with the first the
    moment either was edited, and nothing would say so."""
    specs = ce.from_creature({"reductions": [{"amount": 10, "bypass": "silver"}]})
    assert not any(s["type"] == "damage_reduction" for s in specs)


# --- the engine ---------------------------------------------------------------------------

@pytest.fixture
def giant():
    return bestiary.instantiate("giant-frost")


def test_a_frost_giant_no_longer_takes_damage_from_cold(giant):
    """It took the full 20 before this. `Immune cold` was in the file and was dropped on
    the way to the sheet."""
    assert giant.immunities == ["cold"]
    assert giant.take_damage(20, "cold")["taken"] == 0
    assert giant.take_damage(20, "fire")["taken"] == 20


def test_vulnerability_is_half_again_and_rounds_down():
    snowman = bestiary.instantiate("abominable-snowman")
    assert snowman.vulnerabilities == ["fire"]
    assert snowman.take_damage(20, "fire")["taken"] == 30
    assert snowman.take_damage(15, "fire")["taken"] == 22        # 22.5, rounded down


def test_vulnerability_is_applied_before_resistance():
    """1e multiplies the damage dealt and then subtracts. Twenty fire against vulnerable
    plus resist 10 is 30 - 10 = 20, not (20 - 10) x 1.5 = 15 — and doing it the other way
    round makes a resistance a better deal than not being vulnerable at all."""
    a = from_dict({"name": "test", "hp": 100, "hp_max": 100,
                   "vulnerabilities": ["fire"], "resistances": {"fire": 10}})
    assert a.take_damage(20, "fire")["taken"] == 20


def test_immunity_beats_vulnerability_rather_than_arguing_with_it():
    a = from_dict({"name": "test", "hp": 50, "hp_max": 50,
                   "immunities": ["fire"], "vulnerabilities": ["fire"]})
    r = a.take_damage(20, "fire")
    assert r["taken"] == 0 and r["immune"] and not r["vulnerable"]


def test_resistance_reduces_to_zero_and_never_heals():
    a = from_dict({"name": "test", "hp": 50, "hp_max": 50, "resistances": {"cold": 30}})
    assert a.take_damage(10, "cold")["taken"] == 0
    assert a.hp == 50


def test_resistance_and_reduction_do_not_both_bite():
    """DR is physical only and energy resistance is energy only, so no attack meets both.
    Asserted because the order they are applied in would matter if one ever did."""
    a = from_dict({"name": "test", "hp": 60, "hp_max": 60,
                   "resistances": {"fire": 5}, "reductions": [{"amount": 5}]})
    assert a.take_damage(20, "fire")["taken"] == 15       # resistance, no DR
    assert a.take_damage(20, "slashing")["taken"] == 15   # DR, no resistance


def test_reduction_still_comes_off_before_temporary_hit_points():
    """The rule that was already here and must survive the two new stages in front of it:
    a DR 5 creature must not lose 5 temporary hit points to an attack that never hurt it."""
    a = from_dict({"name": "test", "hp": 40, "hp_max": 40,
                   "reductions": [{"amount": 10}],
                   "temp_pools": [{"amount": 8, "source": "test", "rounds_left": 10}]})
    r = a.take_damage(6, "slashing")
    assert r["taken"] == 0 and r["absorbed"] == 0 and a.temp_hp == 8


def test_the_breakdown_says_what_happened_at_every_stage(giant):
    """The proposition of the app is that the bookkeeping is visible, so a zero has to be
    explainable: "20 cold, immune" rather than "20 cold, 0"."""
    r = giant.take_damage(20, "cold")
    assert r["immune"] is True and r["rolled"] == 20 and r["taken"] == 0


# --- surviving a save -----------------------------------------------------------------------

def test_defences_round_trip_through_a_save(giant):
    back = from_dict(to_dict(giant))
    assert back.immunities == giant.immunities
    assert back.resistances == giant.resistances
    assert back.take_damage(20, "cold")["taken"] == 0


def test_an_empty_list_is_written_rather_than_omitted():
    """Empty is not the same as absent. A save that omits the empty list cannot tell "this
    creature has no immunities" from "this save predates immunities", and the second sends
    `from_dict` back to the stat block to re-derive them — undoing an edit made since."""
    saved = to_dict(from_dict({"name": "test", "hp": 5, "hp_max": 5}))
    assert saved["immunities"] == [] and saved["resistances"] == {}
    assert saved["vulnerabilities"] == []


# --- the editor -------------------------------------------------------------------------

def test_a_shipped_creature_opens_with_its_effects_filled_in(client):
    d = client.get("/api/bench/creatures/open/giant-frost").json()
    assert {"type": "immunity", "target": "cold"} in d["effects"]
    # And it says the machine wrote them, because nobody has read these.
    assert d["converted"] is True


def test_the_derived_effects_are_not_stored_beside_the_line_they_came_from():
    """`immune` is the field the editor shows and the one a person corrects. A copy inside
    `effects` in the same file would be a second answer, disagreeing the moment the first
    is edited, with nothing to report it."""
    raw = bestiary.imported()["giant-frost"]
    assert "effects" not in raw
    assert raw["immune"] == ["cold"]


def test_an_authored_effects_list_is_not_overwritten_by_the_parse():
    """How a homebrew creature says something the prose cannot. A person's answer outranks
    a re-reading of the sentence it was derived from."""
    mine = {"id": "x", "immune": ["cold"],
            "effects": [{"type": "immunity", "target": "everything"}]}
    assert ce.derive(mine)["effects"] == [{"type": "immunity", "target": "everything"}]


def test_the_kind_declares_the_derivation_rather_than_the_view_doing_it():
    """A creature-shaped `if` in `open_thing` is what rules/registry.py was written to
    delete — seven benches could create and never correct because of one."""
    from rules import registry

    assert registry.get("creatures").derive == "rules.creature_effects:derive"
    assert registry.get("ingredients").derive == ""


# --- what the builder promises -----------------------------------------------------------

def test_an_effect_type_that_a_potion_cannot_run_says_so():
    """Six types claimed `engine=True` and produced no intents at all from
    `consumables._spec_to_intents`: immunity, resistance, damage_reduction, vulnerability,
    sense and speed. A potion of fire resistance was drunk and did nothing, silently, which
    is the failure this app keeps naming — not a wrong answer, no answer and no error.

    Four of them are now live *on a creature*, so their flag stays true and a note says
    where the line is. Two were never run anywhere and now say that instead."""
    from rules import consumables

    # Five of the six run now. This test used to assert `== []` for all of them —
    # naming the silent failure in its own docstring and then pinning it in place,
    # which is how a defect gets protected by its own coverage. The four defences
    # became effect kinds with a clock in stage 3, and speed joined the funnel in
    # stage 2, so each produces an intent that does something.
    for tid in ("immunity", "resistance", "damage_reduction", "vulnerability", "speed"):
        spec = {"type": tid, "target": "fire", "amount": 10}
        got = consumables._spec_to_intents(spec, "c1", "a potion", 1.0)
        assert got, f"{tid} still produces no intents — the dose would vanish"

    # Sense is the one that genuinely runs nowhere: nothing in the engine asks what a
    # creature can see, so light and concealment are still narrated.
    _, sense = effectspec.find("sense")
    assert sense.blocked and sense.engine is False
    assert consumables._spec_to_intents(
        {"type": "sense", "target": "darkvision"}, "c1", "a potion", 1.0) == []


def test_the_builder_shows_the_note_even_when_the_engine_flag_is_true():
    """It rendered `blocked` only for `engine === false`, so a caveat on a type the engine
    partly runs could not be written down at all."""
    from pathlib import Path

    page = Path("play/templates/play/home.html").read_text(encoding="utf-8")
    assert "type && type.blocked" in page
    assert "!type.engine" not in page
