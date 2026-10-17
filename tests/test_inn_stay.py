"""A room at an inn or a tavern costs the house's price, once a day.

Known since 0.2.13 and on the 2026-10-09 playtest list: "I pay for a room" took no coin.
The requests lane (2026-10-16) routed "ask for a room" at an inn to `rest` and wrote
down the gap — "what the bed costs is the rest door's (not charged yet)". The price was
always there (`cards.BED_PRICE_CP`, the Core Rulebook's common inn stay, 5 sp a day) and
nothing charged it: a night at the inn healed, refilled and levelled for nothing, and the
only coin that ever moved for a room was a `give` at whatever figure the plan wrote,
which held no room at all.
"""
from __future__ import annotations

from gm import acts_to_ops
from rules import cards, goods, keepers, lodging
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict

from test_a_take_is_not_a_boast import SAM

LOC = "5bbd0c40345f"


def _inn(spot: str = "the-inn", purse=None, keeper_name: str = "the innkeeper"):
    at = f"{LOC}~urban:{spot}"
    s = Scene(location_id=LOC)
    s.at = at
    pc = from_dict(dict(SAM, purse=dict(purse if purse is not None else {"sp": 7})),
                   ref="pc")
    s.add(pc)
    keeper = instantiate("thug", scene=s, name=keeper_name)
    keeper.world_entity_id = keepers.entity_id(at)
    s.add(keeper)
    return s, pc, keeper, Engine(s, Dice(seed=3))


def _rest(engine):
    return engine.run(engine.validate([
        {"op": "rest", "actor": "pc", "because": "a bed for the night",
         "params": {"kind": "night"}}])).outcomes[-1]


def test_a_night_at_the_inn_costs_the_house_price_and_holds_the_room():
    """The common stay, 5 sp, out of the purse through `goods.spend`, named in the tell
    with who took it; the room held as an effect on the clock (law 2)."""
    s, pc, keeper, engine = _inn()
    assert lodging.lets_beds(s)
    out = _rest(engine)
    assert out.status != "refused", out.tell
    assert goods.in_copper(pc.purse) == 70 - 50
    assert out.tell.startswith("Sam pays the innkeeper 5 silver pieces for a room at")
    assert any(e.get("kind") == "lodging" and e.get("paid") == 50
               and e.get("origin") == "rule:inn-stay" for e in out.effects)
    assert pc.has_state("holds.room") and lodging.held(pc, s.at)
    assert "rests for" in out.tell                       # and the night was slept


def test_a_room_paid_for_today_is_not_paid_for_twice():
    """Paid once a day (the book prices an inn stay per day): a second sleep while the
    room is held costs nothing and says so; once the day has run out, it is paid again."""
    s, pc, _keeper, engine = _inn(purse={"sp": 15})
    _rest(engine)
    left = goods.in_copper(pc.purse)
    assert left == 100
    again = _rest(engine)
    assert goods.in_copper(pc.purse) == left
    assert "already paid for today" in again.tell
    s.advance(24 * 60)
    assert not lodging.held(pc, s.at)
    _rest(engine)
    assert goods.in_copper(pc.purse) == left - 50


def test_an_empty_purse_is_refused_in_plain_words_and_nobody_sleeps():
    s, pc, _keeper, engine = _inn(purse={"cp": 3})
    hp, clock = pc.hp, s.clock_minutes
    pc.hp = max(1, pc.hp - 2)
    hp = pc.hp
    out = _rest(engine)
    assert out.status == "refused"
    assert "5 silver pieces a night" in out.tell and "3 copper pieces" in out.tell
    assert "not enough" in out.tell
    assert goods.in_copper(pc.purse) == 3
    assert pc.hp == hp and s.clock_minutes == clock
    assert not pc.has_state("holds.room")


def test_a_tavern_lets_beds_too_and_the_street_charges_nothing():
    s, pc, _keeper, engine = _inn("the-tavern", keeper_name="the barkeep")
    out = _rest(engine)
    assert goods.in_copper(pc.purse) == 20 and "the barkeep" in out.tell

    s, pc, _keeper, engine = _inn("the-market", keeper_name="the master of the market")
    assert not lodging.lets_beds(s)
    out = _rest(engine)
    assert goods.in_copper(pc.purse) == 70
    assert not any(e.get("kind") == "lodging" for e in out.effects)


def test_a_place_the_sleeper_holds_is_their_own_bed():
    """A tavern the player founded and holds (`holds.place.<slug>`) is theirs: free."""
    from rules.activeeffect import ActiveEffect

    s, pc, _keeper, engine = _inn()
    pc.apply_effect(ActiveEffect(name="holds the inn", kind="situation",
                                 key=f"holds:{s.at}", source=f"place:{s.at}",
                                 tags=(f"holds.place.{s.at.rsplit('/', 1)[-1]}",)))
    out = _rest(engine)
    assert goods.in_copper(pc.purse) == 70 and "costs nothing" in out.tell


def test_the_cards_price_and_the_bill_are_one_figure():
    """`cards.cannot_pay` quoted 5 sp while nothing charged it; now both read
    `lodging.STAY_CP`, so the card and the bill can never disagree."""
    assert cards.BED_PRICE_CP == lodging.price_cp(None) == 50
    assert lodging.STAY_CP == {"poor": 20, "common": 50, "good": 200}


def _frame(*acts):
    return {"question": False, "claims": [], "actions": [dict(a) for a in acts]}


def test_coin_handed_to_the_keeper_beside_a_rest_is_not_a_second_payment():
    """`rest` was a paying act, so the plan's `give sp 5 pc -> keeper` beside "I pay for
    a room" stood — a figure the model wrote, holding no room. The rest bills the room
    now; the plan's coin, and the reading's own give to the same keeper, are dropped."""
    s, pc, keeper, _engine = _inn()
    give = {"op": "give", "actor": "pc", "target": keeper.ref, "because": "the room",
            "params": {"item": "sp", "count": 5, "to": keeper.ref, "from_": "pc"}}
    rest = {"op": "rest", "actor": "pc", "because": "a bed", "params": {"kind": "night"}}
    frame = _frame({"act": "rest", "span": "pay for a room"})
    rows = acts_to_ops.table(frame, s, sentence="")
    notes: list = []
    out = acts_to_ops.apply([give, rest], rows, frame, s, notes=notes)
    assert [o["op"] for o in out] == ["rest"], notes
    assert any("the rest's to charge" in n for n in notes)

    frame = _frame({"act": "give", "target": "the innkeeper", "object": "5 silver"},
                   {"act": "rest", "span": "take a room"})
    rows = acts_to_ops.table(frame, s, sentence="")
    out = acts_to_ops.apply([give, rest], rows, frame, s, notes=[])
    assert not [o for o in out if o.get("op") == "give"
                and acts_to_ops._is_coin((o.get("params") or {}).get("item"))]

    # Without a rest, paying the keeper is just paying them.
    frame = _frame({"act": "give", "target": "the innkeeper", "object": "5 silver"})
    rows = acts_to_ops.table(frame, s, sentence="")
    out = acts_to_ops.apply([give], rows, frame, s, notes=[])
    assert [o["op"] for o in out] == ["give"]
