"""A batch pays the mastery its steps would have paid one at a time.

The owner, 2026-10-05: "batch crafting does not give equivalent experience." Measured on
master a77f5f9 through the real APIs, a batch of N at the herb bench or the forge paid
one step whatever N was, and moved the anti-grind counter by one:

  grind Mint at Herbalist 1          N = 1   3   5   10
    batch, step MP                       1   1   1   1
    N single grinds, step MP             1   3   3   3
  grind Mint at Herbalist 2 (Superior)   2   2   2   2   batch
                                         2   6   6   6   singles
  smelt iron ore at the forge            1   1   1   1   batch
                                         1   3   3   3   singles

(Singles stopped at 3 because `REPEAT_LIMIT` was 3 per (method, ingredient), the plans'
anti-grind rule, §4.4 and §4.5.) The ruling the fix follows: a batch of N counts as N
successive steps for the per-step MP, the rarity bands, the quality bonus and the repeat
counter. A batch must never pay less than the singles. Firsts count once.

The owner's second ruling the same day: "batch of 10 should pay 10". The repeat limit no
longer caps a success, for singles or batches, so a batch of 10 pays what ten singles
pay and both pay for all ten. The mishap limit stays.
"""
from __future__ import annotations

import pytest

from rules import worldclass as wc
from tests.test_bench_api import _carry as herb_carry, _craft, _key, _post, bench  # noqa: F401
from tests.test_bench_api import _pc as herb_pc
from tests.test_forge_api import _carry as forge_carry, do_step, forge, post, where  # noqa: F401
from tests.test_forge_api import _pc as forge_pc
from tests.test_forge_bench import TOWN


def _at(level: int = 1) -> wc.Progress:
    return wc.Progress(track="herbalist", level=level, schema=wc.HERBALISM_SCHEMA)


def _steps(lines) -> int:
    """The step MP in a finish's lines: everything but the firsts and the discoveries,
    which are paid once per finish however big the batch."""
    return sum(l["mp"] for l in lines
               if not str(l["why"]).startswith(("first", "learned", "Yield")))


# --- the rule ------------------------------------------------------------------------------

@pytest.mark.parametrize("n", [1, 2, 3, 5, 10])
@pytest.mark.parametrize("rank,quality", [(1, 2), (3, 3), (5, 6)])
def test_a_batch_of_n_pays_what_n_single_steps_pay(n, rank, quality):
    """`award_step(count=N)` against N calls of `count=1`, on two fresh progresses: the
    same MP, the same repeat counter. Measured before the fix: a batch of 5 rare,
    Superior grinds paid 4 (1 + 2 rare + 1 Superior) where five singles paid 12."""
    herbalist = wc.get("herbalist")
    one, many = _at(), _at()
    singles = sum(wc.award_step(herbalist, one, method="grind", ingredient_id="comfrey",
                                rarity_rank=rank, quality_index=quality)["mp"]
                  for _ in range(n))
    batch = wc.award_step(herbalist, many, method="grind", ingredient_id="comfrey",
                          rarity_rank=rank, quality_index=quality, count=n, noun="dose")
    assert batch["mp"] == singles
    assert many.crafted == one.crafted == {"grind:comfrey": n}


@pytest.mark.parametrize("n", [1, 2, 3, 5])
def test_a_failed_batch_is_that_many_failures(n):
    """One roll fails the whole stack, so it is N failed steps against `MISHAP_LIMIT`:
    the same MP as N single failures and the same mishap counter, never more."""
    herbalist = wc.get("herbalist")
    one, many = _at(), _at()
    singles = sum(wc.award_step(herbalist, one, method="grind", ingredient_id="comfrey",
                                rarity_rank=1, quality_index=0, success=False)["mp"]
                  for _ in range(n))
    batch = wc.award_step(herbalist, many, method="grind", ingredient_id="comfrey",
                          rarity_rank=1, quality_index=0, success=False, count=n)
    assert batch["mp"] == singles == min(n, wc.MISHAP_LIMIT)
    assert many.mishaps == one.mishaps == {"grind:comfrey": n}


def test_a_batch_of_10_pays_10():
    """Owner, 2026-10-05: "batch of 10 should pay 10". Under the repeat limit a batch of
    ten Mint paid 3 step MP; now every dose pays, the counter says ten, and the next
    single pays too."""
    herbalist = wc.get("herbalist")
    p = _at()
    got = wc.award_step(herbalist, p, method="grind", ingredient_id="mint", rarity_rank=1,
                        quality_index=0, count=10, noun="dose")
    assert got["mp"] == 10
    assert p.crafted["grind:mint"] == 10
    after = wc.award_step(herbalist, p, method="grind", ingredient_id="mint",
                          rarity_rank=1, quality_index=0)
    assert after["mp"] == 1


def test_a_batch_itemises_its_doses():
    """The lines the page already shows: "Grind, Comfrey: 5 doses +5", and the bands and
    the quality bonus for the same five. (Before the second ruling the repeat limit paid
    three and a fourth line said the other two taught nothing.)"""
    herbalist = wc.get("herbalist")
    got = wc.award_step(herbalist, _at(), method="grind", ingredient_id="comfrey",
                        rarity_rank=3, quality_index=3, name="Comfrey", count=5,
                        noun="dose")
    assert got["reasons"] == [
        {"why": "Grind, Comfrey: 5 doses", "mp": 5},
        {"why": "rare material: 5 doses", "mp": 10},
        {"why": "Superior work: 5 doses", "mp": 5},
    ]
    assert got["mp"] == 20


def test_a_single_step_reads_as_it_always_did():
    """One step keeps its old lines word for word: "Grind, Comfrey" with no count."""
    herbalist = wc.get("herbalist")
    got = wc.award_step(herbalist, _at(), method="grind", ingredient_id="comfrey",
                        rarity_rank=1, quality_index=0, name="Comfrey")
    assert got["reasons"] == [{"why": "Grind, Comfrey", "mp": 1}]


# --- the herb bench, through the API ---------------------------------------------------------

def _fresh_herbalist(level: int = 1) -> None:
    from play import campaign as cm

    pc = herb_pc()
    pc.world_classes.pop("herbalist", None)
    pc.herb_known.clear()
    pc.track("herbalist").level = level
    cm.current().save()


def test_a_batch_of_5_ground_mint_pays_what_five_grinds_pay(bench):
    """Measured on master a77f5f9 at Herbalist 2 with Superior hands: a batch of 5
    Ground Mint paid 2 step MP (1 grind, 1 Superior); five single grinds paid 6 (the
    repeat limit stopped the singles at three). Now both pay 10, every dose paying since
    the owner's "batch of 10 should pay 10", and the firsts (first powder, first work
    with Mint, two properties learned) are paid once either way."""
    _fresh_herbalist(2)
    herb_carry(mint=5)
    done = _craft(bench, "grind", [{"key": _key(bench, "Mint"), "count": 1}], batch=5,
                  score=1.0)
    assert done["count"] == 5
    batch_lines = done["mastery"]["lines"]

    _fresh_herbalist(2)
    herb_carry(mint=5)
    singles = []
    for _ in range(5):
        one = _craft(bench, "grind", [{"key": _key(bench, "Mint"), "count": 1}],
                     batch=1, score=1.0)
        singles += one["mastery"]["lines"]

    assert _steps(batch_lines) == _steps(singles) == 10
    firsts = lambda ls: sum(l["mp"] for l in ls if l["why"].startswith(("first", "learned")))
    assert firsts(batch_lines) == firsts(singles)
    whys = [l["why"] for l in batch_lines]
    assert "Grind, Mint: 5 doses" in whys and "Superior work: 5 doses" in whys
    assert not any("repeat limit" in w for w in whys)
    assert herb_pc().track("herbalist").crafted["grind:mint"] == 5


def test_doses_count_however_the_mortar_was_filled(bench):
    """Three Mint on the mortar at batch 1 is three grinds as surely as one Mint at batch
    3: the bench counts doses, the smallest craft a method allows, not the stepper."""
    _fresh_herbalist(1)
    herb_carry(mint=3)
    done = _craft(bench, "grind", [{"key": _key(bench, "Mint"), "count": 3}], batch=1,
                  score=1.0)
    assert done["count"] == 3
    assert _steps(done["mastery"]["lines"]) == 3


def test_a_spoiled_batch_is_that_many_lessons_up_to_the_limit(bench):
    """A miss spoils the whole stack on one roll, so it teaches what that many failures
    would: `MISHAP_LIMIT` (2) for a batch of four Hardroot, not 1."""
    _fresh_herbalist(1)
    herb_carry(hardroot=4)
    rolled = _post(bench, "/api/bench/roll", {
        "method": "grind", "items": [{"key": _key(bench, "Hardroot"), "count": 1}],
        "batch": 4, "face": 1})
    assert not rolled["roll"]["success"]
    lines = rolled["mastery"]["lines"]
    assert sum(l["mp"] for l in lines) == wc.MISHAP_LIMIT
    assert herb_pc().track("herbalist").mishaps["grind:hardroot"] == 4


# --- the forge, through the API --------------------------------------------------------------

def _fresh_smith() -> None:
    from play import campaign as cm

    pc = forge_pc()
    pc.world_classes.pop("blacksmith", None)
    pc.herb_known.clear()
    pc.purse = {"gp": 50}
    cm.current().save()


SMELT = {"method": "smelt", "slots": {"ore": "inv:iron-ore", "fuel": "inv:charcoal"}}


def test_a_smelt_of_3_ingots_pays_what_three_smelts_pay(forge, where):
    """Measured on master a77f5f9 at a town smithy: a smelt of 3 iron ingots paid 1 step
    MP; three single smelts paid 3. Now both pay 3, itemised "Smelt, Iron Ore: 3
    ingots", and the firsts are paid once either way."""
    where["smithy"] = TOWN["smithy"]
    _fresh_smith()
    forge_carry(iron_ore=6, charcoal=6)
    done = do_step(forge, {**SMELT, "batch": 3}, score=0.5)
    assert done["products"][0]["count"] == 3
    batch_lines = done["mastery"]["lines"]

    _fresh_smith()
    forge_carry(iron_ore=6, charcoal=6)
    singles = []
    for _ in range(3):
        singles += do_step(forge, {**SMELT, "batch": 1}, score=0.5)["mastery"]["lines"]

    assert _steps(batch_lines) == _steps(singles) == 3
    assert {"why": "Smelt, Iron Ore: 3 ingots", "mp": 3} in batch_lines
    firsts = lambda ls: sum(l["mp"] for l in ls if l["why"].startswith(("first", "learned")))
    assert firsts(batch_lines) == firsts(singles)
    assert forge_pc().track("blacksmith").crafted["smelt:iron-ore"] == 3


def test_a_forge_batch_of_five_pays_five(forge, where):
    """Under the repeat limit a smelt of five paid three and said the other two ingots
    taught nothing new; since the owner's "batch of 10 should pay 10" all five pay."""
    where["smithy"] = TOWN["smithy"]
    _fresh_smith()
    forge_carry(iron_ore=10, charcoal=10)
    lines = do_step(forge, {**SMELT, "batch": 5}, score=0.5)["mastery"]["lines"]
    assert _steps(lines) == 5
    assert {"why": "Smelt, Iron Ore: 5 ingots", "mp": 5} in lines


def test_the_forge_counts_a_batch_by_its_units():
    """`_step_units`: the batch's units for the bulk rows, in the unit's own noun; pours
    for Alloy, whose one pour makes as many bars as the charge holds; 1 for a step that
    works one piece at a time."""
    from types import SimpleNamespace as NS

    from play.forge_views import _step_units

    assert _step_units(NS(method="smelt", units=4, noun="ingot")) == (4, "ingot")
    assert _step_units(NS(method="alloy", units=2, noun="bar")) == (2, "pour")
    assert _step_units(NS(method="quench", units=1, noun="blank")) == (1, "blank")
    assert _step_units(NS(method="assemble", units=0, noun="")) == (1, "piece")
