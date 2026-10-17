"""A room paid for at an inn appears on the page, in the engine's own words.

Live 2026-10-17 (integration branch, free narrator, gemma-4-12B): "I pay for a room for
the night and go to bed". The tell: "Kesst Vayr pays the one behind the bar 5 Saltmakers'
silver pieces for a room at the inn for the night. Kesst Vayr rests for 16 hours." The beat
showed the sleep and never the coin — "You find a small, secluded room at the back of the
inn, where the timbers groan in the wind and the cot is firm. You lay down…" — and the
same turn on another save ("I ask the one behind the bar for a room for the night") showed
neither. The purse was 5 sp lighter and the page never said why.

Nothing owed it: the deed reader owes a purchase to the screen and a rest to the clock
(`deed_reader.OWED_ACTS`), and the read back's omission category read sales only. Worse, a
page that DID say "You pay for the room" was a settled trade on a turn with no sale — a
contradiction to the read back, cut. Now a resolved rest whose `lodging` record moved coin
carries the payment's own sentence, the read back owes it, and the backstop puts it first
(paid before slept) — no model call.
"""
from __future__ import annotations

from gm import beat_verify as bv
from gm.checks import BeatContext, beat_verified

from test_inn_stay import _inn, _rest

# The live beat as shipped (coin-data, 2026-10-17), without its opening goodbyes.
SHIPPED = ("You find a small, secluded room at the back of the inn, where the timbers groan "
           "in the wind and the cot is firm. You lay down, and the exhaustion of the day's "
           "flight settles heavily upon you. What do you do?")


def _paid_facts():
    _s, _pc, _keeper, engine = _inn()
    out = _rest(engine)
    return bv.Facts(start="the inn", end="the inn", places=("the inn",),
                    people=(bv.Person(ref="pc", name="Sam", pc=True),),
                    outcomes=(out.as_dict(),)), out


def test_the_engine_records_the_payments_own_sentence():
    _facts, out = _paid_facts()
    line = next(e["line"] for e in out.effects if e.get("kind") == "lodging")
    assert line.startswith("Sam pays the innkeeper 5 silver pieces for a room at")
    assert line.endswith("for the night.") and out.tell.startswith(line)


def test_a_page_with_the_sleep_and_no_coin_owes_the_payment():
    facts, out = _paid_facts()
    found = bv.diff([], facts, SHIPPED)
    assert [(d.kind, d.category) for d in found] == [("omission", "lodging")]
    assert found[0].line.startswith("Sam pays the innkeeper 5 silver pieces")


def test_a_page_that_shows_the_payment_owes_nothing_and_is_not_a_phantom_sale():
    facts, _out = _paid_facts()
    paying = "You count five silver coins onto the bar and the innkeeper slides you a key. " \
             + SHIPPED
    claim = bv.Claim("trade", {"item": bv.OTHER_THING, "seller": bv.NEW_PERSON,
                               "buyer": "pc", "settled": True},
                     "You count five silver coins onto the bar",
                     "You count five silver coins onto the bar and the innkeeper slides you "
                     "a key.", True)
    assert bv.diff([claim], facts, paying) == []


def test_an_unpaid_night_owes_nothing():
    """A room already paid for today, or a bed nobody lets, moves no coin: nothing owed."""
    s, _pc, _keeper, engine = _inn()
    _rest(engine)
    again = _rest(engine)
    facts = bv.Facts(start="", end="", places=(), outcomes=(again.as_dict(),))
    assert bv.diff([], facts, SHIPPED) == []


def test_the_backstop_puts_the_payment_first(monkeypatch):
    facts, _out = _paid_facts()
    d = bv.diff([], facts, SHIPPED)[0]
    monkeypatch.setattr(beat_verified, "discrepancies", lambda ctx: [d])
    ctx = BeatContext(door="turn", text=SHIPPED, player_text="", engine=None, scene=None,
                      world=None, location=None, reading=None, outcomes=(), tells=(),
                      said=(), attribution=None, brief="", brief_facts={}, pull=None,
                      was_at="", acting="", turn=0)
    out, notes = beat_verified.backstop(ctx, SHIPPED, [])
    assert out.startswith(d.line + " You find a small, secluded room")
    assert out.endswith("What do you do?") and notes
