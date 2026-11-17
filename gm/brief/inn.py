"""THE HOUSE'S BEDS AND BOARD: what an inn's or a tavern's keeper lets and serves, when the
party stands in it.

Playtest 2026-11-17b #9/#10 (T443-T445): asked for "a room for the night, and a hot meal",
the one behind the bar answered "I can get you a seat and a plate, but the bed stays
separate", then "you can pay for them now" when nothing could be paid for. The engine now
sells a house's rooms, meals and drink at its counter (rules/lodging.py, `Engine._buy_stay`,
`goods.stocked_at`), and bills a night slept there (`Engine._room_bill`). The temple's
shape (gm/brief/temple.py): a narrator not told what is sold invents the terms.
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
)


def section(ctx) -> tuple[str, dict]:
    from rules import goods, keepers, lodging, pricing

    scene = ctx.scene
    at = str(getattr(scene, "at", "") or "")
    keeper = keepers.keeper_in(scene, at) if at else None
    if keeper is None or getattr(keeper, "is_down", False) \
            or getattr(keeper, "at", "") != at or not lodging.lets_beds(scene, at) \
            or not keepers.keeps_a_counter(keeper):
        return "", {}
    rooms = "; ".join(f"{r['quality']}, {lodging.ABOUT[r['quality']]} "
                      f"({pricing.as_text(r['gp'])})" for r in lodging.menu())
    board = "; ".join(f"{g.name} ({pricing.as_text(g.price_gp)})"
                      for g in goods.goods_at("tavern")
                      if goods._category(g.key) == "food")
    text = (f"\n  {SCAFFOLD[0]} {keeper.name} {SCAFFOLD[1]} {rooms}; {SCAFFOLD[2]} "
            f"{board}. {SCAFFOLD[3]}")
    return text, {"inn_keeper": keeper.ref}
