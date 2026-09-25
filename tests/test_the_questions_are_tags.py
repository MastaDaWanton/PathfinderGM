"""Law 1 where the grep ratchet could not see: the questions are tags.

Measured 2026-09-25 by the engine review: losing Dex to AC was answered from the
`lose_dex_to_ac` flag on the condition rows in three places — a second authority beside
the tags, the shape the three laws forbid for `can_act` — and the speed rule named
`("entangled", "exhausted")` in a tuple the AST ratchet cannot see because the loop
variable is a name, not a literal. Both are tag families now.
"""
from __future__ import annotations

from rules import states
from rules.sheet import load_pc
from rules.tables import CONDITIONS


def test_exposed_covers_exactly_the_rows_the_flag_covered():
    flagged = {k for k, row in CONDITIONS.items() if row.get("lose_dex_to_ac")}
    tagged = {k for k in CONDITIONS if "state.exposed" in states.tags_for(k)}
    assert flagged == tagged


def test_a_blinded_character_loses_dex_by_the_tag():
    pc = load_pc("fixtures/pc-kesst.json")
    before = pc.ac()
    pc.add_condition("blinded", source="test")
    assert pc.loses_dex_to_ac
    assert pc.ac() < before


def test_a_homebrew_state_can_expose_without_a_row():
    from rules.activeeffect import ActiveEffect

    pc = load_pc("fixtures/pc-kesst.json")
    pc.apply_effect(ActiveEffect(name="caught in the net of stars", kind="condition",
                                 key="net-of-stars", source="homebrew",
                                 tags=("state.exposed",)))
    assert pc.loses_dex_to_ac


def test_slowed_halves_speed():
    pc = load_pc("fixtures/pc-kesst.json")
    full = pc.speed_feet
    pc.add_condition("entangled", source="test")
    assert pc.speed_feet == (full // 2 // 5) * 5
