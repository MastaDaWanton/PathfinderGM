"""Counts as magic (docs/enchanting-revamp-plan.md §9, contracts §4, lane C).

The glossary: "Any weapon with at least a +1 magical enhancement bonus ... overcomes" DR/magic;
+3 counts as cold iron and silver, +4 adamantine, +5 every alignment; ammunition "fired from a
projectile weapon with an enhancement bonus of +1 or higher is treated as a magic weapon".
The owner, Q8: bane's +2 counts toward those thresholds. Incorporeal creatures are "immune to
all nonmagical attack forms" (Bestiary). Before lane C the layer's `strikes_as` reached the
damage path for the record's own +N only, bane's raise reached nothing, and a plain sword
halved a ghost.
"""
from __future__ import annotations

from rules import forge_items
from tests.test_enchant_engine import (_armed, _fight, _foe, _hits, _record, _swing,
                                       _table, _wear)


def _dr(who, bypass: str, amount: int = 5):
    who.grant_defence("damage_reduction", "", amount=amount, bypass=bypass, source="hide")


def _blow(s, e, target, params=None):
    out, _ = _swing(s, e, target, _hits, params)
    hit = next(x for x in out.effects if x.get("kind") == "damage")
    return out, hit


def test_a_plus_one_blade_passes_dr_magic_and_a_masterwork_one_does_not():
    """Plan §21.1 (C): "a +1 sword passes DR 5/magic". Measured before: the masterwork
    sword and the +1 sword met DR 5/magic alike, because the only `magic` trait in the app
    was a forged material's."""
    s, e, pc = _armed(enhancement=1)
    thug = _foe(s)
    _dr(thug, "magic")
    _fight(s, e, thug)
    out, hit = _blow(s, e, thug)
    assert hit["reduced"] == 0 and "magic bites past" in out.tell

    s, e, pc = _armed(enhancement=0)
    thug = _foe(s)
    _dr(thug, "magic")
    _fight(s, e, thug)
    out, hit = _blow(s, e, thug)
    assert hit["reduced"] == min(5, hit["rolled"])


def test_a_plus_three_blade_passes_silver_and_cold_iron_and_a_plus_two_does_not():
    """Plan §21.1 (C): "a +3 sword DR 5/silver". The glossary's threshold: "+3 ... cold
    iron or silver"."""
    for bypass in ("silver", "cold iron"):
        s, e, pc = _armed(enhancement=3)
        thug = _foe(s)
        _dr(thug, bypass)
        _fight(s, e, thug)
        assert _blow(s, e, thug)[1]["reduced"] == 0, bypass
    s, e, pc = _armed(enhancement=2)
    thug = _foe(s)
    _dr(thug, "silver")
    _fight(s, e, thug)
    assert _blow(s, e, thug)[1]["reduced"] > 0


def test_bane_counts_toward_the_threshold_against_its_foe_only():
    """Owner, Q8: bane's +2 counts toward +3/+4/+5. A +1 bane (undead) blade strikes an
    undead creature as a +3 weapon — silver — and anybody else as its own +1."""
    s, e, pc = _armed({"id": "bane", "choice": {"foe": "undead"}}, enhancement=1)
    skel, thug = _foe(s, "skeleton", "the skeleton"), _foe(s)
    skel.reductions = []                                    # only the DR under test
    _dr(skel, "silver")
    _dr(thug, "silver")
    _fight(s, e, skel, thug)
    assert _blow(s, e, skel)[1]["reduced"] == 0
    assert _blow(s, e, thug)[1]["reduced"] > 0


def test_holy_strikes_as_good_at_any_enhancement_and_plus_five_as_every_alignment():
    """The glossary's +5 row, and holy's own `strikes_as: good` at +1."""
    s, e, pc = _armed("holy", enhancement=1)
    thug = _foe(s)
    _dr(thug, "good")
    _fight(s, e, thug)
    assert _blow(s, e, thug)[1]["reduced"] == 0
    for bypass in ("evil", "lawful", "chaotic", "good"):
        s, e, pc = _armed(enhancement=5)
        thug = _foe(s)
        _dr(thug, bypass)
        _fight(s, e, thug)
        assert _blow(s, e, thug)[1]["reduced"] == 0, bypass


def test_arrows_from_a_plus_one_bow_count_as_magic():
    """CRB glossary: "Ammunition fired from a projectile weapon with an enhancement bonus of
    +1 or higher is treated as a magic weapon for the purpose of overcoming damage
    reduction". The shot carries the bow's traits."""
    s, e = _table()
    pc = s.pc()
    pc.goods["arrows"] = 20
    pc.add_stock(forge_items.stock_item(_record("bow", "longbow", enhancement=1)))
    _wear(e, "bow")
    thug = _foe(s)
    _dr(thug, "magic")
    _fight(s, e, thug)
    assert _blow(s, e, thug, {"weapon": "bow"})[1]["reduced"] == 0


def test_a_nonmagical_blade_does_nothing_to_a_ghost_a_magic_one_half_ghost_touch_all():
    """Plan §21.1 (C): "a nonmagical sword deals nothing to a ghost". The engine's own
    comment said it: "Not done: the book's 'immune to all nonmagical attack forms' — the
    app has no magic-weapon channel to ask yet". It has one now (the `magic` trait)."""
    s, e, pc = _armed(enhancement=0)
    ghost = _foe(s, "ghost", "the ghost", hp=500)
    _fight(s, e, ghost)
    out, _ = _swing(s, e, ghost, _hits)
    assert "it is not magic" in out.tell and ghost.hp == 500
    assert not any(x.get("kind") == "damage" for x in out.effects)

    s, e, pc = _armed(enhancement=1)
    ghost = _foe(s, "ghost", "the ghost", hp=500)
    _fight(s, e, ghost)
    out, hit = _blow(s, e, ghost)
    assert "insubstantial form" in out.tell and hit["amount"] == max(1, hit["rolled"] // 2)

    s, e, pc = _armed("ghost-touch", enhancement=1)
    ghost = _foe(s, "ghost", "the ghost", hp=500)
    _fight(s, e, ghost)
    out, hit = _blow(s, e, ghost)
    assert "as if it were flesh" in out.tell and hit["amount"] == hit["rolled"]
