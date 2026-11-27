"""A ranged attack in a threatened square provokes, and so does a whip (feat loop b5-core,
rules/shooting.py).

CRB Table 8-2: "Attack (ranged) ... attack of opportunity: yes". Measured before this lane:
an archer standing beside a thug loosed arrow after arrow and the thug never swung, because
`Engine._reactions_before` asked manoeuvres, casting, drinking and pick-ups and nothing else
— and Sword and Pistol and Whip Mastery, which waive the provocation, waived nothing.
"""
from __future__ import annotations

from rules import shooting
from tests.test_feats_b4_moves import _board, _pc, _run, _tells


def _shoot(e, weapon, **params):
    return _run(e, {"op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
                    "params": {"weapon": weapon, **params}})


def _swung_first(res) -> bool:
    ops = [(o.op, o.actor) for o in res.outcomes]
    return ("attack", "c1") in ops and ops.index(("attack", "c1")) < ops.index(("attack", "pc"))


def test_an_archer_beside_a_thug_draws_its_swing_and_one_away_does_not():
    """Point-blank in a threatened square, the thug swings first; from 20 feet nobody does."""
    pc = _pc("fighter", weapons=("shortbow",))
    pc.equipped = "shortbow"
    s, e = _board(pc, ("thug", (6, 5)))
    assert _swung_first(_shoot(e, "shortbow"))
    pc2 = _pc("fighter", weapons=("shortbow",))
    pc2.equipped = "shortbow"
    s, e = _board(pc2, ("thug", (9, 5)))
    res = _shoot(e, "shortbow")
    assert not any(o.actor == "c1" for o in res.outcomes), _tells(res)


def test_a_thrown_dagger_provokes_and_a_stabbed_one_does_not():
    """A thrown weapon makes a ranged attack; the same dagger in the hand does not."""
    pc = _pc("fighter", weapons=("dagger",))
    pc.equipped = "dagger"
    s, e = _board(pc, ("thug", (6, 5)))
    assert shooting.provoking_weapon(pc, {"weapon": "dagger", "thrown": True}) == "dagger"
    assert shooting.provoking_weapon(pc, {"weapon": "dagger"}) == ""


def test_a_whip_provokes_as_a_ranged_weapon_until_whip_mastery():
    """Whip Mastery (UC), Normal: "Attacking with a whip provokes attacks of opportunity as
    if you used a ranged weapon." Benefit: "You no longer provoke"."""
    for feats, provokes in (((), True), (("Weapon Focus", "Whip Mastery"), False)):
        pc = _pc("fighter", feats=feats, weapons=("whip",))
        pc.equipped = "whip"
        s, e = _board(pc, ("thug", (6, 5)))
        assert bool(shooting.provoked(e, {"op": "attack", "actor": "pc", "target": "c1",
                                          "params": {"weapon": "whip"}})) is provokes, feats


def test_sword_and_pistol_spares_the_foe_the_blade_threatens():
    """Sword and Pistol (UC): two-weapon fighting with a melee weapon and a crossbow, "your
    attacks with the crossbow ... provoke no attacks of opportunity from foes that you
    threaten with your melee weapon"."""
    for feats, provokes in (((), True), (("Sword and Pistol",), False)):
        pc = _pc("fighter", level=8, feats=feats, weapons=("longsword", "hand crossbow"))
        pc.equipped = "hand-crossbow"
        s, e = _board(pc, ("thug", (6, 5)))
        raw = {"op": "attack", "actor": "pc", "target": "c1",
               "params": {"weapon": "hand-crossbow", "off_hand": "longsword",
                          "full_attack": True}}
        assert bool(shooting.provoked(e, raw)) is provokes, feats
