"""Every price a person takes from the player moves with how they feel about them (owner
ruling 2026-11-13: "keep the rulebook's base price augmented by the relationship and the
personality of the seller").

0.3.2 moved counters and berths (`tests/test_shop_attitude_prices.py`). Measured on
0.3.2 before this lane: a smith with regard 80 rented the forge at 80 cp for eight hours,
the same 80 cp as a stranger; an innkeeper who could not stand the player let a bed at the
book's 5 sp; a jailer's bribe, a teacher's fee and a tannery's vats were the same coin
whoever asked. Now each reads `pricing.seller_percent` (attitude and thrift, capped at the
haggle's 25%), with the person who takes the money as the seller, and a hostile one will
not deal at all. The book's base prices are unchanged.
"""
from __future__ import annotations

import pytest

from rules import attitude, goods, knowledge, market, places, pricing, trial

from test_forge_places import _at_a_town_smithy
from test_inn_stay import _inn, _rest
from test_leather_places import _at_the_tannery
from test_trial import _condemned, _run as _trial_run, _tells


def _middling(scene, person, regard):
    """`person` at `regard`, with a thrift of 50 so the attitude alone moves the price."""
    rec = next((r for r in (scene.population or {}).values() if r.get("ref") == person.ref),
               None)
    if rec is None:
        scene.population = dict(scene.population or {})
        rec = scene.population[f"t-{person.ref}"] = {"id": f"t-{person.ref}",
                                                    "ref": person.ref}
    rec.setdefault("life", {}).setdefault("axes", {})["thrift"] = 50
    attitude.set_regard(person, regard, "test")


# Regard band -> step: 20 unfriendly (-10%), 40 indifferent, 60 friendly (+5%), 80 helpful.
@pytest.mark.parametrize("regard,cp", [(40, 80), (60, 76), (80, 72), (20, 88)])
def test_the_forge_rent_moves_with_the_smiths_regard(regard, cp):
    """Eight hours at the town forge is the book's 80 cp to a stranger; a smith who likes
    you takes 5% off (76), one who does not wants 10% over (88). Before: 80 every time."""
    scene = _at_a_town_smithy()
    smith = places._actor(scene, places.smithy_here(scene)["keeper"])
    _middling(scene, smith, regard)
    assert market.forge_rent(scene, 8) == cp


def test_a_hostile_smith_will_not_let_the_party_at_the_forge():
    """Hostile refuses, as at a counter: no smithy on the bench, no rent, and the bench's
    footer says why instead of "No forge here"."""
    from rules import blacksmith as bs
    from play import forge_views

    scene = _at_a_town_smithy()
    smith = places._actor(scene, places.smithy_here(scene)["keeper"])
    _middling(scene, smith, 0)
    where = bs.where_here(scene, scene.pc())
    assert where["smithy"] is None and "will not let you work here" in where["refused"]
    assert bs.rent_cp(scene, where["smithy"], 60) == 0
    assert forge_views._place_line(None, where).startswith(where["refused"])


def test_the_tannery_yard_and_its_vats_move_with_the_tanners_regard():
    """Three hours in the yard (30 cp) and two vats for 28 days (1,120 cp) at the book's
    rates; a helpful tanner takes 10% off both (27 and 1,008)."""
    _world, _town, scene, engine, _tannery = _at_the_tannery()
    known = engine.places()
    tanner = places._actor(scene, places.tannery_here(scene, known)["keeper"])
    _middling(scene, tanner, 80)
    assert market.tannery_rent(scene, 3, known) == 27
    assert market.vat_rent(scene, 28, 2, known) == 1_008


def test_the_inn_lets_a_bed_dearer_to_somebody_it_does_not_like():
    """The book's common stay is 5 sp; an unfriendly innkeeper asks 10% over (55 cp) and
    the tell says why."""
    s, pc, keeper, engine = _inn(purse={"sp": 7})
    _middling(s, keeper, 20)
    res = engine.run(engine.validate([
        {"op": "rest", "actor": "pc", "because": "a bed for the night",
         "params": {"kind": "night"}}]))
    out = next(o for o in res.outcomes if o.op == "rest")
    assert out.status != "refused", out.tell
    assert goods.in_copper(pc.purse) == 70 - 55
    assert "does not like you: 10% over" in out.tell, out.tell


def test_a_hostile_innkeeper_lets_no_bed():
    s, pc, keeper, engine = _inn(purse={"sp": 7})
    _middling(s, keeper, 0)
    out = _rest(engine)
    assert out.status == "refused" and "will not deal with you" in out.tell, out.tell
    assert goods.in_copper(pc.purse) == 70 and not pc.has_state("holds.room")


def test_a_teachers_fee_moves_with_their_regard():
    """A lesson is the table's fee to a stranger and 10% off from somebody helpful."""
    s, _pc, keeper, _engine = _inn()
    book = int(knowledge.lore(knowledge.HERBALIST)["teacher"]["price_cp"])
    _middling(s, keeper, 40)
    assert knowledge.lesson_price_cp(s, keeper) == book
    _middling(s, keeper, 80)
    assert knowledge.lesson_price_cp(s, keeper) == pricing.moved_cp(book, 10)


def test_the_bribe_a_guard_asks_moves_with_their_regard():
    """Ultimate Intrigue's quarter of the guard's gear is the book's sum (unchanged without
    a scene); a guard who does not like you wants 10% more, in whole gold."""
    s, e, pc, g, _ = _condemned()
    book = trial.bribe_price_cp(g)
    _middling(s, g, 20)
    assert attitude.of(g) == "unfriendly"
    assert trial.bribe_price_cp(g, s) == -(-book * 110 // 10_000) * 100
    _middling(s, g, 40)
    assert trial.bribe_price_cp(g, s) == book


def test_a_hostile_guard_takes_no_bribe_at_any_price():
    s, e, pc, g, _ = _condemned()
    _middling(s, g, 0)
    pc.purse = {"gp": 4 * trial.bribe_price_cp(g) // 100}
    before = goods.in_copper(pc.purse)
    res = _trial_run(e, [{"op": "give", "actor": "pc", "target": g.ref, "because": "t",
                          "params": {"item": "gp", "count": before // 100, "to": g.ref}}])
    t = _tells(res)
    assert "pushes it back" in t and "will not deal with you" in t, t
    assert goods.in_copper(pc.purse) == before and trial.custody(pc) is not None


def test_a_commission_moves_the_smiths_hours_once_not_twice():
    """The keeper's own forge hours inside a commission are billed at the book's rent and
    the whole bill moved once by their terms: with the rent moved too, a friendly smith's
    hours were discounted twice."""
    from world.loader import load_cached
    from test_commission import _blank, _commission, _engine, _smith

    world = load_cached("fixtures/pangrella-campaign.json")
    listed = []
    for regard in (40, 80):
        e, pc = _engine(world, carry=(("iron", 1), ("charcoal", 1), ("ash-haft", 2)))
        _blank(e, pc)
        smith, _ = _smith(e)
        _middling(e.scene, smith, regard)
        eff = _commission(e, smith).effects[0]
        listed.append(eff["listed_cp"])
        if regard == 80:
            assert eff["cp"] == pricing.moved_cp(eff["listed_cp"], 10), eff
    assert listed[0] == listed[1], listed
