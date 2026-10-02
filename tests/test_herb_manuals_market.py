"""Herbalism manuals are sold, and a bought one is a book the reader can open.

Lane C (2026-10-02) wrote six manuals and the reading door, but the market's goods are a
file it did not own: the manuals existed and nobody could buy one. Measured before this
hook: 0 of 6 manuals on any counter.
"""
from rules import goods, herbknowledge, market
from rules.sheet import Actor


def test_the_alchemists_counter_always_carries_every_manual():
    """Six manuals, and the alchemist's shop (where herbs are already sold) lists all six as
    staples, so a player who wants to learn by reading always finds them in a town."""
    on_counter = {g.key for g in market.staples_of(market.COUNTER_PREFIX + "alchemist")}
    manuals = set(herbknowledge.manuals())
    assert len(manuals) >= 4
    assert manuals <= on_counter


def test_a_bought_manual_is_one_the_reader_holds():
    """`deliver` shelves a bought book under its name, and `holds_manual` must recognise
    exactly that shelf entry, or the book is paid for and can never be read."""
    manual = next(iter(herbknowledge.manuals().values()))
    good = next(g for g in goods.table_goods("herbal-manuals") if g.key == manual["id"])
    reader = Actor(name="Reader", ref="pc")
    assert not herbknowledge.holds_manual(reader, manual)
    goods.deliver(None, reader, good, 1)
    assert herbknowledge.holds_manual(reader, manual)
