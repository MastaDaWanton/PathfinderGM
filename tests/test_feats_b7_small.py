"""Feat loop batch 7, lane b7-small (2026-11-27): the partial feats whose missing clause
is one small book rule of its own (docs/feats-partial-ledger.md, groups 13-49 this lane
holds). Each test names what the engine did before the clause was built.
"""
from __future__ import annotations

from rules.dice import Dice
from tests.test_feats_b4_moves import _attack, _board, _pc, _tells


def _bleeds(actor):
    return [e for e in actor.effects if e.key == "bleed"]


def test_tiger_style_bleeds_a_slashing_critical_for_two_turns_only():
    """UC, Tiger Style: "Whenever you score a critical hit with your slashing unarmed
    strike, your opponent also takes 1d4 points of bleed damage at the start of his next
    two turns." Measured before: no bleed was laid at all (a bleed here ran until healed,
    so the document could not say "two turns"). Now the crit lays a 1d4 bleed that fires
    twice and ends by itself."""
    pc = _pc("monk", feats=["Improved Unarmed Strike", "Tiger Style"], equipped="unarmed")
    s, e = _board(pc, ("ogre", (6, 5)), faces={"Attack with": 20, "Confirm": 20})
    res = _attack(e, weapon="unarmed")
    foe = s.actors["c1"]
    assert "for 2 rounds" in _tells(res), _tells(res)
    assert len(_bleeds(foe)) == 1
    hp = foe.hp
    fired = [foe.run_periodic("round", 1, Dice(seed=1)) for _ in range(3)]
    hits = [r for rnd in fired for r in rnd if r["kind"] == "damage"]
    assert len(hits) == 2 and foe.hp < hp
    assert not _bleeds(foe)


def test_tiger_style_lays_no_bleed_on_an_ordinary_hit():
    """The bleed is the critical's only: a plain hit (no confirmation) bleeds nobody."""
    pc = _pc("monk", feats=["Improved Unarmed Strike", "Tiger Style"], equipped="unarmed")
    s, e = _board(pc, ("ogre", (6, 5)), faces={"Attack with": 15, "Confirm": 1})
    _attack(e, weapon="unarmed")
    assert not _bleeds(s.actors["c1"])


def _halfling(*feats):
    return _pc("fighter", feats=["Cautious Fighter", *feats], race="halfling")


def _aoo(e, faces=None):
    from rules.intents import Intent
    from tests.test_feats_b4_moves import _settle

    raw = Intent(op="attack", actor="pc", target="c1", visibility="hidden", because="test",
                 params={"reaction": "attack_of_opportunity", "provoked_by": "movement"})
    return _settle(e, e.run([raw]))


def _in_total_defense(e):
    from tests.test_feats_b4_moves import _run

    res = _run(e, {"op": "total_defense", "actor": "pc"})
    assert res.outcomes[-1].status == "resolved", _tells(res)


def test_desperate_swing_lets_one_attack_of_opportunity_through_total_defense():
    """ARG, Desperate Swing: "Once per day, you can make a single melee attack while
    taking the total defense action. You take a -4 penalty". Measured before: total
    defense's `reactions.none` refused every attack of opportunity, the feat's included.
    Now the first is offered at -4 and the day is spent; the second is refused again."""
    from rules import reactions
    from tests.test_feats_b4_moves import _named, _rolls

    pc = _halfling("Desperate Swing")
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 12})
    _in_total_defense(e)
    assert reactions.reactions_for(pc)
    roll = _rolls(_aoo(e), "Attack with")[0]
    assert _named(roll, "Desperate Swing") == -4
    assert not reactions.reactions_for(pc)

    plain = _halfling()
    s2, e2 = _board(plain, ("thug", (6, 5)))
    _in_total_defense(e2)
    assert not reactions.reactions_for(plain)


def test_desperate_swing_confirms_at_plus_four_while_fighting_defensively():
    """"+4 bonus on critical confirmation rolls made while fighting defensively".
    Measured before: the confirmation carried only the swing's own terms."""
    from tests.test_feats_b4_moves import _named, _rolls

    def confirm(feats):
        pc = _halfling(*feats)
        s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 20, "Confirm": 10})
        return _rolls(_attack(e, fighting_defensively=True), "Confirm")[0]

    assert _named(confirm(["Desperate Swing"]), "Desperate Swing") == 4
    assert _named(confirm([]), "Desperate Swing") == 0


def test_surprise_strike_waives_the_desperate_swing_penalty_once_a_day():
    """ARG, Surprise Strike: "Once per day, when fighting defensively or making an attack
    of opportunity while taking the total defense action with the Desperate Swing feat,
    you take no penalty on the attack roll." Measured before: Desperate Swing did not run,
    so there was no penalty to waive. Now the desperate swing carries no -4; and a
    fighting-defensively attack the same day keeps its -4, the day being spent."""
    from tests.test_feats_b4_moves import _named, _rolls
    from tests._board import new_turn

    pc = _halfling("Desperate Swing", "Surprise Strike")
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 12})
    _in_total_defense(e)
    roll = _rolls(_aoo(e), "Attack with")[0]
    assert _named(roll, "Desperate Swing") == 0
    new_turn(s)
    roll = _rolls(_attack(e, fighting_defensively=True), "Attack with")[0]
    assert _named(roll, "Surprise Strike") == 0 and _named(roll, "Fighting defensively") == -4


def test_surprise_strike_waives_fighting_defensively_s_penalty_on_one_roll():
    """The waiver's other half: the first fighting-defensively attack of the day takes
    no -4 (+4 against the stance's -4), and the next day's is spent."""
    from tests.test_feats_b4_moves import _named, _rolls
    from tests._board import new_turn

    pc = _halfling("Desperate Swing", "Surprise Strike")
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 12})
    roll = _rolls(_attack(e, fighting_defensively=True), "Attack with")[0]
    assert _named(roll, "Surprise Strike") == 4
    new_turn(s)
    roll = _rolls(_attack(e, fighting_defensively=True), "Attack with")[0]
    assert _named(roll, "Surprise Strike") == 0


def test_blind_fight_takes_an_invisible_attacker_s_melee_edge_away():
    """CRB, Blind-Fight: "An invisible attacker gets no advantages related to hitting you
    in melee. That is, you don't lose your Dexterity bonus to Armor Class, and the
    attacker doesn't get the usual +2 bonus for being invisible. The invisible attacker's
    bonuses do still apply for ranged attacks." Measured before: nothing read the clause,
    so an invisible thug denied the fighter his Dexterity and swung at +2 regardless."""
    from tests.test_feats_b4_moves import _named, _rolls

    def swing(feats):
        pc = _pc("fighter", feats=feats)
        s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 12})
        thug = s.actors["c1"]
        thug.add_condition("invisible", 10)
        roll = _rolls(_attack(e, by="c1", target="pc"), "Attack with")[0]
        return e._unseen_attacker(pc, thug, melee=True), \
            e._unseen_attacker(pc, thug, melee=False), _named(roll, "no invisible edge")

    assert swing([]) == (True, True, 0)
    assert swing(["Blind-Fight"]) == (False, True, -2)


def test_extra_channel_gives_a_paladin_four_lay_on_hands_only_for_channelling():
    """CRB, Extra Channel (Special): "If a paladin with the ability to channel positive
    energy takes this feat, she can use lay on hands four additional times a day, but
    only to channel positive energy." Measured before: nothing was added (her uses were
    one pool). Now two channels are paid from the four extra uses, lay on hands itself
    never touches them, and the third channel is paid from lay on hands."""
    from tests._board import new_turn
    from tests.test_feats_b4_moves import _use

    pc = _pc("paladin", level=6, feats=["Extra Channel"])
    pc.rebuild_pools()
    s, e = _board(pc, ("thug", (8, 5)))
    hands = pc.pool("lay on hands").current
    assert pc.pool("extra channel").current == 4
    for _ in range(2):
        _use(e, "Channel Positive Energy")
        new_turn(s)
    assert pc.pool("extra channel").current == 0 and pc.pool("lay on hands").current == hands
    _use(e, "Channel Positive Energy")
    assert pc.pool("lay on hands").current == hands - 2

    plain = _pc("paladin", level=6)
    plain.rebuild_pools()
    assert plain.pool("extra channel").maximum == 0
    assert all(p["id"] != "extra channel" for p in plain.summary()["pools"])
