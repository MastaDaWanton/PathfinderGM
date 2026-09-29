"""Lane D, "The lost thing" (docs/playtest-2026-09-28.md items 8 and 12; the owner's Q22):
it opens on day two at the market, and the giver's tell is not granted before they meet.

What was measured on the Bobby playtest: the scheme opened at the market from hour zero in
every campaign — Drenn Ironvale was the first named person in every playthrough (item 8) —
and its `grants_on_open` put "Drenn Ironvale looked away when asked how the Power leaf was
lost" on Bobby's sheet at hour 0, before he had met Drenn. That sentence reached the brief
through `Actor.noticed()` and came back in Drenn's pitch as "lost not through
carelessness" (fix-interfaces §1.5 D2: the open grant, not the secret card, was the leak).
"""
from __future__ import annotations

import pytest

from rules import cards, schemes
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

DAY_ONE = 9 * 60
DAY_TWO = 24 * 60 + 9 * 60


@pytest.fixture(autouse=True)
def schemes_on(monkeypatch):
    monkeypatch.setattr(schemes, "ENABLED", True)


def _at_market(world, clock):
    row = (world.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party(schemes._place_for(e, "market", {})["id"])
    return s, e, pc


def _wait(e, minutes=1):
    return e.run(e.validate([{"op": "advance_time", "actor": "pc", "because": "t",
                              "params": {"amount": minutes, "unit": "minutes"}}],
                            origin="author:test"))


def _talk(e, giver):
    """The player speaks to the giver: `noticed` keys on `event:talk($giver)` since
    Phase 3 (I4), so the tell is seen in an exchange, never by walking past."""
    return e.run(e.validate([{"op": "say", "actor": "pc", "because": "t",
                              "params": {"words": "Good morning.", "to": giver.ref}}],
                            origin="author:test"))


def _opened(s):
    return next((i for i in s.schemes if i["scheme"] == "the-lost-thing"), None)


def test_the_shipped_scheme_still_validates_and_grants_nothing_at_open():
    doc = schemes.shipped()["the-lost-thing"]
    assert schemes.validate(doc) == []
    assert not doc.get("grants_on_open")
    assert doc["opens"] == ["at($market)", "since(campaign) >= 1d"]
    hook = next(c for c in doc["cards"] if c["key"] == "errand")["hook"]
    assert set(hook) == {"motive", "doing", "withholds"}


def test_it_does_not_open_at_the_market_on_day_one(worlds):
    """Every campaign opened on Drenn at the market in the first hour. The first market
    visit is now the player's own."""
    s, e, pc = _at_market(worlds, DAY_ONE)
    _wait(e)
    assert _opened(s) is None and not cards.quests(s)


def test_it_opens_on_day_two_and_the_tell_comes_with_the_giver(worlds):
    s, e, pc = _at_market(worlds, DAY_TWO)
    _wait(e)
    inst = _opened(s)
    assert inst is not None
    giver = s.people[inst["slots"]["giver"]["ref"]]
    assert giver.at == s.at
    assert "noticed" not in inst["fired"], "present alone is not an exchange (I4)"
    _talk(e, giver)
    assert "noticed" in inst["fired"] and inst["fired"]["noticed"]["silent"]
    assert pc.has_state("knows.giver-hides-something")
    noticed = " ".join(pc.noticed())
    assert giver.name in noticed and "looked away when asked" not in noticed


def test_no_noticed_line_before_the_giver_is_present(worlds):
    """Bobby "noticed" Drenn at hour 0, before they met. Opened with the giver away from
    the party's place, nothing is granted; the grant comes when they are present."""
    s, e, pc = _at_market(worlds, DAY_TWO)
    inst = schemes.open_scheme(e, schemes.shipped()["the-lost-thing"], turn=1)
    giver = s.people[inst["slots"]["giver"]["ref"]]
    elsewhere = next(p.id for p in e.places() if p.id != s.at)
    s.move(giver.ref, elsewhere)
    assert not pc.has_state("knows.giver-hides-something")
    assert not pc.noticed()
    _wait(e)
    assert not pc.has_state("knows.giver-hides-something")
    s.move(giver.ref, s.at)
    _wait(e)
    assert not pc.has_state("knows.giver-hides-something"), "present, not yet spoken to"
    _talk(e, giver)
    assert pc.has_state("knows.giver-hides-something")
