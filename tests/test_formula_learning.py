"""Copying a formula: the writing is paid for when it is written, and only a spell the
character casts is one they can write down (owner report 2026-11-01, Ansel, 0.2.25).

Measured on Ansel's save: two failed copies ("cannot make out the formula") took 50 gp
between them and nothing on the page said a coin had moved; and Ansel, a level-3 paladin
— no spell slot until level 4 — was offered and allowed both copies "from your
spellbook", because `casting.knows` answers "on the class list" for a list caster
whatever the level. CRB, Arcane Magical Writings: on a failed check the spell is not
understood and nothing is written; the cost is the writing's.
"""
from __future__ import annotations

from play import campaign as cm
from rules import casting, classes, formulae, spells
from rules.crafting import Stock
from rules.sheet import from_dict, load_pc, to_dict
from tests.test_alchemy_api import bench, post, where  # noqa: F401


def _paladin(level):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "paladin", "level": level, "ranks": {}, "armour": "none"})
    d.pop("paths", None)
    actor = from_dict(d, ref="pc")
    classes.apply(actor)
    return actor


def test_a_level_three_paladin_casts_nothing_yet_and_a_level_four_casts_bless():
    bless, bulls = spells.get("bless"), spells.get("bull-s-strength")
    three = _paladin(3)
    assert casting.knows(three, bless), "the list is still the paladin's"
    assert not casting.castable_now(three, bless)
    assert not casting.castable_now(three, bulls)
    four = _paladin(4)
    assert casting.castable_now(four, bless)
    assert not casting.castable_now(four, bulls), "2nd-level spells come at level 7"


def _scroll(spell="haste"):
    pc = cm.current().scene.pc()
    pc.add_stock(Stock(base=f"Scroll of {spell.title()}", craft="enchanter",
                       holds_spell=spell, count=1, kind="scroll"), 1)
    cm.current().save()
    return pc


def _scroll_item(client):
    rows = client.get("/api/alchemy/formulary").json()["writings"]
    return next(w for w in rows if w["route"] == "scroll")


def test_a_failed_copy_costs_nothing_and_says_so(bench):
    """Haste, 3rd level: DC 18 and 90 gp of writing. A natural 1 writes nothing, and the
    purse is untouched — and the line says the writing was not spent."""
    pc = _scroll()
    row = _scroll_item(bench)
    assert row["plan"]["cost_gp"] == 90
    r = post(bench, "/api/alchemy/learn", {"from": "scroll", "item": row["item"],
                                           "face": 1}).json()
    assert not r["result"]["learned"]
    assert cm.current().scene.pc().purse == {"gp": 200}, cm.current().scene.pc().purse
    assert r["paid"] == ""
    assert "not spent" in r["said"], r["said"]


def test_a_copy_that_succeeds_is_charged_once_and_the_cost_is_said(bench):
    _scroll()
    row = _scroll_item(bench)
    r = post(bench, "/api/alchemy/learn", {"from": "scroll", "item": row["item"],
                                           "face": 20}).json()
    assert r["result"]["learned"], r
    from rules import goods

    assert goods.in_copper(cm.current().scene.pc().purse) == 200 * 100 - 90 * 100
    assert "costs" in r["said"] and "90" in r["said"], r["said"]


def test_a_purse_that_could_not_pay_the_writing_is_refused_before_the_roll(bench):
    _scroll()
    cm.current().scene.pc().purse = {"gp": 10}
    cm.current().save()
    row = _scroll_item(bench)
    r = post(bench, "/api/alchemy/learn", {"from": "scroll", "item": row["item"], "face": 20})
    assert r.status_code == 409 and "cannot pay" in r.json()["error"]


def test_the_spellbook_route_is_closed_to_a_caster_with_no_slot_for_the_spell(bench):
    """Ansel's route: the formulary offered "your spellbook" rows for spells a level-3
    paladin cannot cast, and the learn door took them. Neither now."""
    c = cm.current()
    pc = c.scene.pc()
    pc.char_class = "paladin"
    pc.level = 3
    classes.apply(pc)
    c.save()
    rows = bench.get("/api/alchemy/formulary").json()["writings"]
    assert not [w for w in rows if w["route"] == "spellbook"], rows
    r = post(bench, "/api/alchemy/learn", {"from": "spellbook",
                                           "fid": "potion-of-bull-s-strength", "face": 20})
    assert r.status_code == 409, r.content
    assert "cannot cast that spell yet" in r.json()["error"]
    assert "potion-of-bull-s-strength" not in formulae.known(cm.current().scene.pc())
