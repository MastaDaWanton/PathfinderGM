"""Hired swords (rules/hirelings.py): a sellsword comes along for a wage.

The owner, 2026-11-14: "am i able to hire mercenaries/guardsmen to sail with and help guard
me and or my wares" — measured the same day on 0.3.3: no door took coin for company at
all. An indifferent caravan guard asked to come was refused ("Talk them round first") and
there was nothing to pay; the only way along was friendship.
"""
from __future__ import annotations

from rules import encounter_budget, goods, hirelings, jobs, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene

DAY = 24 * 60


def _party(work="caravan-guard", gp=100, thrift=50):
    s = Scene(location_id="nowhere")
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.purse = {"gp": gp}
    s.add(pc)
    sword = instantiate("guildhand", scene=s, name="Hesk")
    s.add(sword)
    s.population = {"p1": {"id": "p1", "ref": sword.ref, "home": "nowhere",
                           "life": {"work": work, "axes": {"thrift": thrift}}}}
    return s, Engine(s, Dice(seed=1)), pc, sword


def _company(e, pc, who, **params):
    return e.run(e.validate([{"op": "company", "actor": pc.ref, "because": "t",
                              "params": {"who": who.ref, **params}}],
                            origin="author:test")).outcomes


def test_a_caravan_guard_is_hired_for_the_books_wage_a_week_up_front():
    """0.3.3: the indifferent caravan guard could not be paid to come. Now `hire` takes
    C&C's road wage (6 sp x level squared) for a week in advance, and grants the companion
    bond and the wage through the applicator, under one source."""
    s, e, pc, sword = _party()
    level = encounter_budget.companion_level(sword)
    day = jobs.per_day_cp("escort", level, jobs.risk_of("escort"))
    assert day == 60 * level ** 2
    before = goods.in_copper(pc.purse)
    out = _company(e, pc, sword, do="hire")
    assert sword.has_state(states.TRAVELS_WITH_YOU) and sword.has_state(states.HIRED)
    assert before - goods.in_copper(pc.purse) == day * 7
    assert "a week's wages in advance" in out[0].tell
    # A companion like any other: a head in the fare, a member of the APL.
    assert sword.ref in e._passage_party(type("I", (), {"params": {}})())
    assert len(encounter_budget.party_levels(s)) == 2


def test_dismissal_ends_the_bond_and_the_wage_together():
    """Second law: one source, `company:<ref>`, so `leave` leaves no wage behind."""
    s, e, pc, sword = _party()
    _company(e, pc, sword, do="hire")
    _company(e, pc, sword, do="guard", what="cargo")
    assert hirelings.guarding(sword) == "cargo"
    _company(e, pc, sword, do="leave")
    assert not sword.has_state("bond")


def test_only_swords_hire_out_and_hostile_ones_do_not():
    """A baker is no mercenary warrior (CRB); a hostile sellsword deals as a hostile
    keeper does — not at all."""
    s, e, pc, baker = _party(work="baker")
    out = _company(e, pc, baker, do="hire")
    assert not baker.has_state(states.HIRED) and "does not hire out a sword" in out[0].tell
    s, e, pc, sword = _party()
    e._set_attitude(sword, "hostile", None, "test")
    _company(e, pc, sword, do="hire")
    assert not sword.has_state(states.HIRED)


def test_a_short_purse_is_refused_with_the_figure():
    s, e, pc, sword = _party(gp=0)
    pc.purse = {"cp": 5}
    out = _company(e, pc, sword, do="hire")
    assert not sword.has_state(states.HIRED)
    assert "a week in advance" in out[0].tell and "carries" in out[0].tell


def test_the_wage_moves_by_the_hirelings_own_terms():
    """Every price since 0.3.2 moves by the seller's attitude and thrift; a wage too."""
    _s, _e, _pc, plain = _party(thrift=50)
    s, _e, _pc, tight = _party(thrift=95)
    assert hirelings.day_cp(s, tight) > hirelings.day_cp(_s, plain)


def test_the_refused_join_names_the_hire():
    """Before: "Talk them round first" and nothing else, to a sellsword."""
    s, e, pc, sword = _party()
    out = _company(e, pc, sword)
    assert not sword.has_state(states.TRAVELS_WITH_YOU)
    assert "Or hire them" in out[0].tell


def test_the_week_renews_from_the_purse_and_an_unpaid_sword_walks():
    """C&C: pay up front; failure to pay, and Trust goes. A week renews while the purse
    holds; an empty purse and the hireling goes, thinking less of the player."""
    s, e, pc, sword = _party()
    _company(e, pc, sword, do="hire")
    week = hirelings.wage(sword).payload["per_day_cp"] * 7
    s.clock_minutes += 7 * DAY
    left = goods.in_copper(pc.purse)
    out = hirelings.settle(e)
    assert goods.in_copper(pc.purse) == left - week and "another week" in out[0].tell
    assert sword.has_state(states.HIRED)
    pc.purse = {}
    s.clock_minutes += 7 * DAY
    out = hirelings.settle(e)
    assert not sword.has_state(states.TRAVELS_WITH_YOU)
    assert not sword.has_state(states.HIRED)
    assert "goes their own way" in out[0].tell


def test_an_indifferent_hireling_walks_with_the_party():
    """Measured live 2026-11-14: a sellsword hired at the tavern "does not come with you
    any more" at the first walk — travel's loyalty question (below friendly falls away)
    was asked of somebody who comes for pay, and the wage went with the bond."""
    from world.loader import load_cached

    s = Scene(location_id="bde94b038cba")
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.purse = {"gp": 100}
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=load_cached("fixtures/aurvantis-campaign.json"))
    e.place_party("")
    sword = instantiate("guildhand", scene=s, name="Hesk")
    s.add(sword)
    s.move(sword.ref, s.at)
    s.population = {"p1": {"id": "p1", "ref": sword.ref, "home": "bde94b038cba",
                           "life": {"work": "caravan-guard", "axes": {"thrift": 50}}}}
    _company(e, pc, sword, do="hire")
    e.run(e.validate([{"op": "travel", "actor": pc.ref, "because": "t",
                       "params": {"place": "the market"}}], origin="author:test"))
    assert sword.has_state(states.TRAVELS_WITH_YOU) and sword.has_state(states.HIRED)
    assert sword.at == pc.at


def test_guard_needs_a_companion_and_a_known_thing():
    s, e, pc, sword = _party()
    _company(e, pc, sword, do="guard", what="cargo")
    assert not sword.has_state(states.GUARDING)
    _company(e, pc, sword, do="hire")
    _company(e, pc, sword, do="guard", what="the moon")
    assert not sword.has_state(states.GUARDING)
    _company(e, pc, sword, do="guard", what="cargo")
    assert sword.has_state(states.GUARDING)


def test_a_hire_the_plan_left_out_is_added_from_the_words():
    """Measured live 2026-11-14: "I will hire you after all, sellsword. Come with me." was
    planned as a say and a greet, no company, and the sellsword stayed unpaid. A say to
    somebody who hires out, confirmed by the company question, adds `company do: hire`;
    with no question nothing is added (coin is never spent on a guess)."""
    from gm import acts_to_ops

    s, e, pc, sword = _party()
    frame = {"actions": [{"act": "talk", "target": "Hesk", "commit": "done",
                          "says": "I will hire you", "span": "I will hire you. Come with me."}]}
    plan = [{"op": "say", "params": {"to": sword.ref, "words": "I will hire you."}}]
    assert acts_to_ops.orders_spoken(plan, frame, s, ask=None) == plan
    got = acts_to_ops.orders_spoken(plan, frame, s, ask=lambda span, who: "something else")
    assert [r["op"] for r in got] == ["say"]
    got = acts_to_ops.orders_spoken(plan, frame, s, ask=lambda span, who: "has them come along")
    assert got[-1]["params"] == {"who": sword.ref, "do": "hire"}
    _s, _e, _pc, baker = _party(work="baker")
    plan = [{"op": "say", "params": {"to": baker.ref, "words": "Come with me."}}]
    got = acts_to_ops.orders_spoken(plan, frame, _s, ask=lambda span, who: "has them come along")
    assert [r["op"] for r in got] == ["say"]


def test_a_guard_order_the_plan_left_out_is_added_from_the_words():
    """Measured live 2026-11-14: "Your first job: stand over my wares in the hold and let
    nobody near them." was planned as a say alone; the sellsword promised to keep the wares
    safe and held no guard. A say to a companion the company question reads as an order to
    guard adds `company do: guard`, with what is guarded asked in one more closed
    question; and the engine then grants `bond.guarding` over the cargo."""
    from gm import acts_to_ops

    s, e, pc, sword = _party()
    _company(e, pc, sword, do="hire")
    span = "stand over my wares in the hold and let nobody near them"
    frame = {"actions": [{"act": "talk", "target": "Hesk", "commit": "done",
                          "says": span, "span": span}]}
    plan = [{"op": "say", "params": {"to": sword.ref, "words": span}}]
    got = acts_to_ops.orders_spoken(plan, frame, s, ask=lambda *a: "something else",
                                    ask_what=lambda *a: "cargo")
    assert [r["op"] for r in got] == ["say"]
    got = acts_to_ops.orders_spoken(plan, frame, s, ask=lambda *a: "sets them to guard",
                                    ask_what=lambda *a: "cargo")
    assert got[-1]["params"] == {"who": sword.ref, "do": "guard", "what": "cargo"}
    # Live, the line had no addressee (a say with no `to`): with one companion along,
    # it is theirs — for a guard order only.
    unnamed = [{"op": "say", "params": {"words": span}}]
    got = acts_to_ops.orders_spoken(unnamed, frame, s, ask=lambda *a: "sets them to guard",
                                    ask_what=lambda *a: "cargo")
    assert got[-1]["params"] == {"who": sword.ref, "do": "guard", "what": "cargo"}
    e.run(e.validate([dict(got[-1], actor=pc.ref)], origin="author:test"))
    assert hirelings.guarding(sword) == "cargo"
    # Nobody with the party is set to guard by words to them: they must come along first.
    _s, _e, _pc, stranger = _party(work="baker")
    plan = [{"op": "say", "params": {"to": stranger.ref, "words": span}}]
    got = acts_to_ops.orders_spoken(plan, frame, _s, ask=lambda *a: "sets them to guard")
    assert [r["op"] for r in got] == ["say"]


def test_a_coin_given_beside_a_hire_is_not_paid_twice():
    """Measured live 2026-11-14: "Here is your coin, sellsword. You are hired; come with
    me." was planned as `company do: hire` and `give gp 1 to c10`; the purse paid the
    week's wage (4 gp 4 sp 1 cp) and a gold piece more. The engine's wage is the payment:
    only the week leaves the purse."""
    from gm import acts_to_ops

    s, e, pc, sword = _party()
    plan = [{"op": "say", "actor": pc.ref, "params": {"to": sword.ref, "words": "Here."}},
            {"op": "company", "actor": pc.ref, "because": "t",
             "params": {"who": sword.ref, "do": "hire"}},
            {"op": "give", "actor": pc.ref, "because": "t",
             "params": {"item": "gp", "count": 1, "from_": pc.ref, "to": sword.ref}}]
    notes = []
    got = acts_to_ops.wage_not_tipped(plan, s, notes=notes)
    assert [r["op"] for r in got] == ["say", "company"] and notes
    before = goods.in_copper(pc.purse)
    e.run(e.validate([r for r in got if r["op"] == "company"], origin="author:test"))
    assert before - goods.in_copper(pc.purse) == hirelings.wage(sword).payload["per_day_cp"] * 7
    # A give with no hire beside it is the player's own and stands.
    alone = [plan[2]]
    assert acts_to_ops.wage_not_tipped(alone, s) == alone
