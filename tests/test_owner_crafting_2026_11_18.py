"""The owner's crafting rulings of 2026-11-18 (docs: pgm-work owner-bugs-plan items 14-16).

14. Any crafting step of an hour or more goes In progress, at the herb bench and the forge.
    Measured on frag's save: a Dry held the herbalist at the bench 8 hours, a Reduce of
    24 doses 24 hours.
15. Craft XP: 1->2 costs 100, 2->3 260, then a flat 400 a level, every craft but
    enchanting. Measured: all five crafts were 25 / 65 then 50, 60, 70..., so frag reached
    Herbalist 10 on 657 mastery.
16. Beating the check by 5 or more gives more yield, less time and a quality floor, capped;
    a natural 20 breaks through the quality cap. Measured: frag had Herbalism +12 against
    DC 3, and the benches rewarded only `margin >= 0`.
"""
from __future__ import annotations

import pytest

from rules import crafting, worldclass
from tests.test_bench_api import _carry, _craft, _key, _level, _pc, _post, bench  # noqa: F401


# --- 15: the XP curve --------------------------------------------------------------------

@pytest.mark.parametrize("track", ["herbalist", "blacksmith", "alchemist", "leatherworker"])
def test_crafts_cost_100_then_260_then_a_flat_400(track):
    """Was 25, 65, 50, 60, 70 (frag: Herbalist 10 on 657 mastery). Now 100, 260, 400, 400."""
    t = worldclass.get(track)
    assert [t.to_next(n) for n in (1, 2, 3, 4, 10, 40)] == [100, 260, 400, 400, 400, 400]


def test_enchanting_keeps_its_own_curve():
    """The ruling excepted enchanting."""
    t = worldclass.get("enchanter")
    assert [t.to_next(n) for n in (1, 2)] == [25, 65]


# --- 16: the margin bands ----------------------------------------------------------------

def test_bands_start_at_five_over_and_stop_at_the_cap():
    """frag's +12 against DC 3 beat it by 5 on nearly any face; the cap keeps a margin of 30
    worth what 15 is, so the bands still mean something."""
    assert crafting.margin_bonus(4)["bands"] == 0
    assert crafting.margin_bonus(5)["bands"] == 1
    assert crafting.margin_bonus(14)["bands"] == 2
    assert crafting.margin_bonus(30)["bands"] == crafting.margin_rules()["max_bands"] == 3
    miss = crafting.margin_bonus(-6, 20)
    assert miss["bands"] == 0 and miss["breakthrough"] == 0, "a natural 20 never saves a miss"


def test_more_yield_and_less_time_per_band():
    b = crafting.margin_bonus(15)
    assert crafting.bonus_minutes(480, b) == 336                 # x0.7
    assert crafting.bonus_units(1, b) == 1 and crafting.bonus_units(24, b) == 8
    assert crafting.bonus_units(24, crafting.margin_bonus(3)) == 0
    assert crafting.bonus_minutes(1, b) == 1, "never below a minute"


def test_the_floor_never_takes_the_top_rung_from_the_minigame():
    """A floor of 3 at a ceiling of 2 (Herbalist 1: Fine) still leaves Fine to the hands:
    the always-play ruling (2026-11-11)."""
    b = crafting.margin_bonus(15)
    assert crafting.tier_from_score(0.0, 2, b)[0] == 1
    assert crafting.tier_from_score(1.0, 2, b)[0] == 2
    assert crafting.tier_from_score(0.0, 4, b)[0] == 3
    assert crafting.tier_from_score(0.0, 4, None)[0] == 0


def test_a_natural_20_breaks_through_the_ceiling_by_one():
    """Herbalist 3 tops out at Flawless (4); a perfect game on a natural 20 lands
    Flawless +1, and a poor one is still the game's."""
    nat = crafting.margin_bonus(0, 20)
    assert crafting.tier_from_score(1.0, 4, nat)[0] == 5
    assert crafting.quality_name(5) == "Flawless +1"
    assert crafting.tier_from_score(1.0, 4, crafting.margin_bonus(0, 19))[0] == 4
    assert crafting.tier_from_score(0.0, 4, nat)[0] == 0


# --- 14 + 16 at the herb bench, through the routes the player clicks ----------------------

def _ground_mint(client, n: int):
    _carry(mint=n)
    _craft(client, "grind", [{"key": _key(client, "Mint"), "count": n}])
    return _key(client, "Ground Mint")


def test_a_dry_waits_in_progress_and_the_clock_moves_only_its_hands_on_minutes(bench):
    """frag's Dry held the bench 8 hours. Now the roll passes 10 minutes and the batch
    dries In progress for the other 470, carried."""
    from play import campaign as cm

    _level(2)
    key = _ground_mint(bench, 24)
    body = {"method": "dry", "items": [{"key": key, "count": 24}]}
    check = _post(bench, "/api/bench/check", body)
    assert check["minutes"] == 10 and check["product"]["ready_minutes"] == 470
    before = cm.current().scene.clock_minutes
    # A face that beats the DC by under 5: no margin bonus, so the times are the plan's.
    dc, plus = check["dc"], check["bonus"]
    face = max(1, min(20, dc - plus + 1))
    assert 0 <= face + plus - dc < 5, (face, plus, dc)
    rolled = _post(bench, "/api/bench/roll", dict(body, face=face))
    assert cm.current().scene.clock_minutes == before + 10
    done = _post(bench, "/api/bench/finish", {"token": rolled["token"], "score": 0.5})
    assert done["next"] is None and "is still drying; it is ready in" in done["waiting"]
    from rules import inprogress

    st = next(s for s in _pc().stock.values() if inprogress.work_of(s) is not None)
    block = inprogress.work_of(st)
    assert block["doing"] == "drying" and block["minutes"] == 470
    assert block["where"] == "carried", "drying racks travel with the herbalist"
    assert inprogress.held_back(st, cm.current().scene.clock_minutes).startswith(
        "still drying")


def test_a_short_step_does_not_wait(bench):
    """Grinding 3 doses is 30 minutes: under the hour, done on the spot."""
    _carry(mint=3)
    check = _post(bench, "/api/bench/check", {"method": "grind",
                                              "items": [{"key": _key(bench, "Mint"),
                                                         "count": 3}]})
    assert check["minutes"] == 30 and not check["product"].get("ready_minutes")


def test_beating_the_dc_by_10_makes_more_doses_less_time_and_a_floor(bench):
    """Kesst's +3 on a natural 20 against DC 10 beats it by 13: two bands. 5 doses ground
    (50 minutes) take 40 and come out 6, and a score of 0 lands no lower than tier 2."""
    _level(3)
    _carry(mint=5)
    body = {"method": "grind", "items": [{"key": _key(bench, "Mint"), "count": 5}],
            "face": 20}
    rolled = _post(bench, "/api/bench/roll", body)
    assert rolled["roll"]["margin"] == 13, rolled["roll"]
    assert rolled["roll"]["margin_bonus"]["bands"] == 2
    assert rolled["minutes"] == 40, "50 minutes x0.8"
    done = _post(bench, "/api/bench/finish", {"token": rolled["token"], "score": 0.0})
    assert done["count"] == 6 and done["tier"] == 2
    assert any("Beat the DC by 10 or more: 1 more dose" in x["why"]
               for x in done["mastery"]["lines"])


def test_a_natural_20_and_a_perfect_game_land_past_the_ceiling(bench):
    """Herbalist 3's ceiling is Flawless; a natural 20 and a perfect score make Flawless +1."""
    _level(3)
    _carry(mint=1)
    body = {"method": "grind", "items": [{"key": _key(bench, "Mint"), "count": 1}],
            "face": 20}
    rolled = _post(bench, "/api/bench/roll", body)
    done = _post(bench, "/api/bench/finish", {"token": rolled["token"], "score": 1.0})
    assert done["tier_name"] == "Flawless +1"


def test_the_strip_shows_the_ladder_the_finish_lands_with_a_margin_bonus(bench):
    """The page's live word must agree with the finish (the strip test's rule). Herbalist 1
    on a natural 20 beating DC 10 by 13: the floor is Fine and the breakthrough Superior,
    so the strip names only those two, and each band's lowest score lands its own name."""
    _carry(mint=4)
    items = [{"key": _key(bench, "Mint"), "count": 1}]
    tuning = _post(bench, "/api/bench/roll", {"method": "grind", "items": items,
                                              "face": 20})["tuning"]
    assert tuning["names"] == ["Fine", "Superior"] and tuning["bands"][0] == 0
    for name, low in zip(tuning["names"], tuning["bands"]):
        rolled = _post(bench, "/api/bench/roll", {"method": "grind", "items": items,
                                                  "face": 20})
        done = _post(bench, "/api/bench/finish", {"token": rolled["token"], "score": low})
        assert done["tier_name"] == name, (low, done["tier_name"])


# --- 14 at the forge ------------------------------------------------------------------------

from tests.test_forge_api import forge, post, rack_key, where  # noqa: E402,F401
from tests.test_forge_api import _carry as _forge_carry, _level as _forge_level  # noqa: E402
from tests.test_forge_bench import TOWN  # noqa: E402


def _forge_once(client, body):
    chk = post(client, "/api/forge/check", body).json()
    face = max(1, min(20, int(chk["dc"]) - int(chk["bonus"])))
    rolled = post(client, "/api/forge/roll", {**body, "face": face}).json()
    assert rolled["roll"]["success"], rolled
    return chk, rolled, post(client, "/api/forge/finish",
                             {"token": rolled["token"], "score": 1.0}).json()


def test_a_forging_of_90_minutes_waits_in_progress_carried_from_the_field_kit(forge):
    """The forge had no In progress at all: Forge's 90 minutes held the smith at the
    anvil. Now the roll passes 10 hands-on minutes, the blank forges In progress for 80,
    carried, and the rack does not offer it until it is collected."""
    from play import campaign as cm
    from rules import inprogress

    _forge_level(2)
    _forge_carry(iron=1, charcoal=1)
    body = {"method": "forge", "shape": "longsword",
            "slots": {"metal": "inv:iron", "fuel": "inv:charcoal"}}
    before = cm.current().scene.clock_minutes
    chk, rolled, done = _forge_once(forge, body)
    assert chk["info"].startswith("1 blank. 1h 30m."), "the info line is the whole step"
    assert rolled["minutes"] == 10 and cm.current().scene.clock_minutes == before + 10
    key = done["products"][0]["key"].split(":", 1)[1]
    block = inprogress.work_of(cm.current().scene.pc().stock[key])
    assert (block["craft"], block["minutes"], block["where"]) == ("blacksmith", 80, "carried")
    assert block["doing"] == "forging"
    assert done["products"][0]["next"] is None, "no Next for a blank not on the rack yet"
    assert "is still forging; it is ready in" in done["products"][0]["waiting"]
    rack = forge.get("/api/forge/state").json()["rack"]
    assert not any(x["key"] == f"stock:{key}" for x in rack)


def test_work_at_a_town_smithy_is_left_there_and_rented_for_the_whole_step(forge, where):
    """Smelting two ingots (120 minutes) at a town smithy: the smith is paid for both
    hours, the clock moves 10, and the ingots wait at the smithy to be collected there."""
    from play import campaign as cm
    from rules import inprogress

    where["smithy"] = TOWN["smithy"]
    _forge_carry(iron_ore=4, charcoal=4)
    body = {"method": "smelt", "batch": 2,
            "slots": {"ore": "inv:iron-ore", "fuel": "inv:charcoal"}}
    chk, rolled, done = _forge_once(forge, body)
    assert chk["rent_cp"] == 20 and rolled["minutes"] == 10
    key = done["products"][0]["key"].split(":", 1)[1]
    pc = cm.current().scene.pc()
    block = inprogress.work_of(pc.stock[key])
    assert block["where"] == "place:the-forge" and block["minutes"] == 110
    now = cm.current().scene.clock_minutes + 110
    assert not inprogress.collect(pc, key, now=now, here="elsewhere")["ok"]
    assert inprogress.collect(pc, key, now=now, here="the-forge")["ok"]
