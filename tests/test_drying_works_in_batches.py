"""Drying works in batches (the owner's ruling, 2026-11-01).

Measured on Ansel's save: Dry was timed at 480 minutes a dose, so his 24 Ground Caranator,
dried into 12 doses, took 96 hours, and the two Dry steps of his session 8 days. The ruling:
one batch takes its 8 hours however many doses, up to what the racks hold, and more than
that takes another batch. The racks hold 6 doses per Herbalist level
(`batch_doses_per_level` in content/rules/herbal-methods.json, after Ultimate Wilderness
p.152, where an herbalist prepares as many doses at once as she has ranks in Profession
(herbalist)), so a Herbalist 2 dries 12 doses in one batch.
"""
from __future__ import annotations

from rules import crafting
from tests.test_bench_api import _carry, _craft, _key, _level, _post, bench  # noqa: F401


def _ground_mint(client, n: int):
    _carry(mint=n)
    _craft(client, "grind", [{"key": _key(client, "Mint"), "count": n}], score=0.5)
    return _key(client, "Ground Mint")


def test_drying_twelve_doses_is_one_eight_hour_batch_not_ninety_six_hours(bench):
    """24 ground in, 12 dried doses out: was 12 x 480 = 5,760 minutes (96 hours, Ansel's
    measured case), now one batch of 480."""
    _level(2)
    key = _ground_mint(bench, 24)
    got = _post(bench, "/api/bench/check", {"method": "dry",
                                             "items": [{"key": key, "count": 24}]})
    assert got["doses"] == 12
    assert got["batch_capacity"] == 12 and got["batches"] == 1
    assert got["minutes"] == 480, got["minutes"]


def test_twenty_four_doses_take_two_batches_at_herbalist_2_and_one_at_herbalist_4(bench):
    """24 doses (48 ground) were 24 x 480 = 11,520 minutes (8 days). At Herbalist 2 the
    racks hold 12, so it is two batches (960 minutes); at Herbalist 4 they hold 24 and it
    is one (480)."""
    _level(2)
    key = _ground_mint(bench, 48)
    body = {"method": "dry", "items": [{"key": key, "count": 48}]}
    two = _post(bench, "/api/bench/check", body)
    assert (two["doses"], two["batches"], two["minutes"]) == (24, 2, 960)
    _level(4)
    one = _post(bench, "/api/bench/check", body)
    assert (one["batch_capacity"], one["batches"], one["minutes"]) == (24, 1, 480)


def test_the_roll_passes_one_batch_of_time_on_the_clock(bench):
    """The time the check shows is the time the roll passes: 480 minutes for one batch,
    landed or not."""
    _level(2)
    key = _ground_mint(bench, 24)
    from play import campaign as cm

    before = cm.current().scene.clock_minutes
    r = _post(bench, "/api/bench/roll", {"method": "dry", "face": 1,
                                         "items": [{"key": key, "count": 24}]})
    assert r["minutes"] == 480
    assert cm.current().scene.clock_minutes == before + 480


def test_no_copy_of_the_per_dose_drying_rule_survives():
    """Dry carries `minutes_per_batch`, not `minutes_per_dose`: a row with both would let
    a second reader time it the old way. Reduce, the other concentration step, stays per
    dose (the ruling named drying only)."""
    dry = crafting.method_row("dry")
    assert "minutes_per_dose" not in dry
    assert dry["minutes_per_batch"] == 480 and dry["batch_doses_per_level"] == 6
    assert crafting.method_row("reduce")["minutes_per_dose"] == 60
