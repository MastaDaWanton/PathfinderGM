"""THE HOUSE'S BEDS AND BOARD: what an inn's or a tavern's keeper lets and serves, when the
party stands in it.

Playtest 2026-11-17b #9/#10 (T443-T445): asked for "a room for the night, and a hot meal",
the one behind the bar answered "I can get you a seat and a plate, but the bed stays
separate", then "you can pay for them now" when nothing could be paid for. The engine now
sells a house's rooms, meals and drink at its counter (rules/lodging.py, `Engine._buy_stay`,
`goods.stocked_at`), and bills a night slept there (`Engine._room_bill`). The temple's
shape (gm/brief/temple.py): a narrator not told what is sold invents the terms.

And the room the player already holds here (owner's save 2026-11-17, frag T109-T114): a good
room bought, the night narrated on the hearth floor, and "go to the room i paid for"
answered "only the communal spaces". The hold was a tag the brief never stated.
"""
from __future__ import annotations

ORDER = 47
SLOT = "people"
SCAFFOLD = (
    "THE HOUSE'S BEDS AND BOARD (fact):",
    "lets rooms by the night:",
    "and serves meals and drink:",
    "The player pays at the counter (the Trade panel), or for the room by sleeping here; "
    "nothing is handed over and no coin changes hands in the prose.",
    "holds a room in this house, paid for today:",
    "where it is:",
)

# Where each stay is (the book's words for it, rules/lodging.py `ABOUT`): the good stay is a
# private room, which is upstairs where the house has an upper floor.
_WHERE = {"poor": "the floor by the hearth", "common": "the raised, heated floor"}


def _held_line(scene, at: str, known=()) -> tuple[str, dict]:
    """The room the player holds in this house (`lodging.room_held`) and where it is, or
    ("", {}) when they hold none here."""
    from rules import lodging
    from rules import places as places_mod

    pc = scene.pc() if hasattr(scene, "pc") else None
    held = lodging.room_held(pc) if pc is not None and at else None
    house = places_mod.base_of(at)
    if held is None or places_mod.base_of(held[0]) != house:
        return "", {}
    stay = held[1]
    if stay != "good":
        where = _WHERE[stay]
    elif any(getattr(p, "id", "") == places_mod.storey_id(house, 1) for p in known or ()):
        where = "a private room upstairs, on the upper floor"
    else:
        where = "a private room off the common room"
    return (f"\n  {pc.name} {SCAFFOLD[4]} the {stay} stay ({lodging.ABOUT[stay]}); "
            f"{SCAFFOLD[5]} {where}."), {"room_held": stay}


def section(ctx) -> tuple[str, dict]:
    from rules import goods, keepers, lodging, pricing

    scene = ctx.scene
    at = str(getattr(scene, "at", "") or "")
    held_text, held_facts = _held_line(scene, at, getattr(ctx, "known", ()))
    keeper = keepers.keeper_in(scene, at) if at else None
    if keeper is None or getattr(keeper, "is_down", False) \
            or getattr(keeper, "at", "") != at or not lodging.lets_beds(scene, at) \
            or not keepers.keeps_a_counter(keeper):
        return held_text, held_facts
    rooms = "; ".join(f"{r['quality']}, {lodging.ABOUT[r['quality']]} "
                      f"({pricing.as_text(r['gp'])})" for r in lodging.menu())
    board = "; ".join(f"{g.name} ({pricing.as_text(g.price_gp)})"
                      for g in goods.goods_at("tavern")
                      if goods._category(g.key) == "food")
    text = (f"\n  {SCAFFOLD[0]} {keeper.name} {SCAFFOLD[1]} {rooms}; {SCAFFOLD[2]} "
            f"{board}. {SCAFFOLD[3]}")
    return text + held_text, {"inn_keeper": keeper.ref, **held_facts}
