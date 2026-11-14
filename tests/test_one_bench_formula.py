"""Each bench rule written once: the check, and the rent (audit 2026-11-07, "Crafts").

The check. d20 + track level + half character level + the craft's ability, plus half the
Craft ranks, was written out in five modules (crafting, blacksmith, leatherworker,
alchemist, enchanter) and a sixth (magicitem, deleted with the chain bench). The copies had
begun to differ: two read `if actor`, three `if actor is not None`; two carried the
half-level comment and three did not. `tradecraft.bench_check_terms` is the one list now.

The rent. Three copies of "copper for the hours at a rented bench" stood beside
`market._rent`: the forge's fallback (the smithy's rate, ownership never asked), the
laboratory's (the lab's rate or the rule row's 2 sp an hour, and any error in
`market.lab_rent` swallowed into it), and the old chain forge route, which charged nothing
at all. The live benches always reached `market`: the forge 10 cp an hour, the laboratory
20, the tannery yard 10 and a vat 20 cp a day, nothing at the party's own, a coin begun a
coin paid. Those are the only answers left.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from rules import alchemist, blacksmith, crafting, enchanter, leatherworker, market, tradecraft
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parent.parent

BENCHES = [(crafting, "herbalist", "Herbalist", "wis"),
           (blacksmith, "blacksmith", "Blacksmith", "int"),
           (leatherworker, "leatherworker", "Leatherworker", "int"),
           (alchemist, "alchemist", "Alchemist", "int"),
           (enchanter, "enchanter", "Enchanter", "int")]


@pytest.mark.parametrize("module,track,name,ability", BENCHES,
                         ids=[b[1] for b in BENCHES])
def test_every_bench_check_is_the_one_formula(module, track, name, ability):
    pc = load_pc("fixtures/pc-thessaly.json")
    pc.ranks = dict(pc.ranks, craft=4)
    got = module.check_terms(pc, 3)
    want = tradecraft.bench_check_terms(pc, 3, track=track, name=name, ability=ability,
                                        ability_mod=got[2]["value"])
    assert got[:len(want)] == want
    assert got[0] == {"label": f"{name} 3", "value": 3}
    assert got[1]["label"].startswith("half character level")
    # With no actor, the same three terms at their floors and no ranks term.
    assert [t["value"] for t in module.check_terms(None, 2)] == [2, 0, 0]


def test_the_half_level_term_is_written_in_one_place():
    """Five copies of the label meant five places to correct; one is left."""
    copies = [p.name for p in (ROOT / "rules").glob("*.py")
              if '"half character level (' in p.read_text(encoding="utf-8")
              or "f\"half character level (" in p.read_text(encoding="utf-8")]
    assert copies == ["tradecraft.py"], copies


def test_the_rent_arithmetic_is_written_in_one_place():
    """`math.ceil(round(rate * hours, 6))` lived in market.py, blacksmith.py and
    alchemist.py; only market's answer was ever charged. The rate times the hours is
    market's still; the coin-begun rounding is `pricing.moved_cp`'s since the keeper's own
    terms move the rent (2026-11-14), which is one place too."""
    pattern = re.compile(r"rate_cp_per_hour\"\]\)\s*\*\s*h(?![a-z_])")
    copies = [p.name for p in (ROOT / "rules").glob("*.py")
              if pattern.search(p.read_text(encoding="utf-8"))]
    assert copies == ["market.py"], copies


def test_the_rates_the_live_benches_charge():
    assert market.forge_rate() == 10 and market.forge_rate(owned_by_party=True) == 0
    assert market.lab_rate() == 20 and market.lab_rate(owned_by_party=True) == 0
    assert market.tannery_rate() == 10 and market.vat_rate() == 20
    # A coin begun is a coin paid: ten minutes at the forge is 2 cp, not 1.67.
    assert market._rent(10 / 60, lambda: {"rate_cp_per_hour": 10}) == 2
    assert market._rent(1, lambda: {"rate_cp_per_hour": 10}) == 10


@pytest.mark.parametrize("bench,fn,place", [
    (blacksmith, "forge_rent", {"kind": "town", "rate_cp_per_hour": 10}),
    (alchemist, "lab_rent", {"kind": "town", "rate_cp_per_hour": 20}),
], ids=["forge", "laboratory"])
def test_a_bench_charges_what_market_charges_and_nothing_else(monkeypatch, bench, fn, place):
    """Measured before: with `market` asked and its answer refused, the forge fell back
    to the smithy's own rate and the laboratory to its rate or 20 cp, a second answer to
    what a bench costs. Now the bench's rent is market's, whatever market says."""
    seen = []
    monkeypatch.setattr(market, fn, lambda scene, hours, known=(): seen.append(hours) or 7)
    assert bench.rent_cp(object(), place, 90) == 7
    assert seen == [1.5]
    assert bench.rent_cp(object(), None, 90) == 0
