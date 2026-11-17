"""People who come along, stay put, or stand in the way: playtest 2026-11-17 (Vesna Kroll,
0.4.0, the overnight round-3 save, transcript T329-T424).

Each test names the item and what was measured on the save.
"""
from __future__ import annotations

from gm import acts_to_ops, interpret, judgement
from rules import attitude, ontheway, population, states
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

MIRABALOS = "7ef5e373c993"
WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


class _Dice:
    """Every d100 answers `d100` (100: nothing is met, nothing lives anywhere)."""

    def __init__(self, real, d100=100):
        self.real, self.d100 = real, d100

    def __getattr__(self, name):
        return getattr(self.real, name)

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation == "1d100":
            return self.real.given(self.d100, modifiers, label, notation)
        return self.real.roll(notation, modifiers, label, visibility)


def _city():
    s = Scene(location_id=MIRABALOS)
    s.add(load_pc("fixtures/pc-kesst.json"))
    dice = _Dice(Dice(seed=3))
    e = Engine(s, dice, world=WORLD)
    e.place_party()
    return s, e, dice


def _run(e, *raws):
    intents = e.validate([{"actor": "pc", "because": "t", "visibility": "hidden", **r}
                          for r in raws], origin="author:test")
    return e.run(intents).outcomes


def _place(e, name):
    return next(p for p in e.places() if p.name == name)


def _friend(e, name="the starving smuggler"):
    ref = e._bring_in("commoner-level-1", count=1, name=name)[0]["ref"]
    a = e.scene.actors[ref]
    e._set_attitude(a, attitude.COMES_ALONG, None, "rule:test")
    return a


def _sewers():
    s, e, dice = _city()
    e.place_party(_place(e, "the gardens").id)
    _run(e, {"op": "venture", "params": {"kind": "sewers"}})
    assert s.at.endswith("the-gardens/the-sewers")
    return s, e, dice


# --- #34 / #50: somebody who agrees to come along comes along, and stays with the party --

def test_a_friend_taken_along_by_name_stays_with_the_party():
    """#34/#50: "I go to the broken pen, and the smuggler comes with me" walked the
    friendly smuggler there with `with: [c28]`, unbonded; the next walk left him behind in
    the pen, and back in the cells he was "nowhere to be found"."""
    s, e, _ = _city()
    friend = _friend(e)
    square, market = _place(e, "the great square"), _place(e, "the market")
    told = _run(e, {"op": "travel", "params": {"place": square.name, "with": [friend.ref]}})
    assert friend.at == square.id and "comes with you" in told[0].tell
    assert friend.has_state(states.TRAVELS_WITH_YOU)
    _run(e, {"op": "travel", "params": {"place": market.name}})
    assert friend.at == market.id, "the second walk left him behind"


def test_an_unfriendly_escort_is_carried_but_not_bonded():
    """The bond is the `company` op's own rule: friendly or better comes along."""
    s, e, _ = _city()
    sour = _friend(e, "the sour drover")
    e._set_attitude(sour, attitude.DEFAULT, None, "rule:test")
    _run(e, {"op": "travel", "params": {"place": "the great square", "with": [sour.ref]}})
    assert not sour.has_state(states.TRAVELS_WITH_YOU)


def test_a_person_the_walk_leads_goes_in_its_with():
    """#34: "I lead the smuggler on into the broken pen" — read `go` with the smuggler as
    the walk's object — was refused twice as a travel leaving him behind."""
    s, e, _ = _city()
    friend = _friend(e)
    frame = {"actions": [{"act": "go", "place": "the broken pen", "object": "the smuggler",
                          "span": "lead the smuggler on into the broken pen"}]}
    raw = acts_to_ops.led_along([{"op": "travel", "params": {"place": "the broken pen"}}],
                                frame, s)
    assert raw[0]["params"]["with"] == [friend.ref]


def test_the_reader_is_shown_a_led_walk():
    """#34: the reader's demonstrations carry a person led as the walk's object."""
    shown = repr(interpret.reader_messages("x")) if hasattr(interpret, "reader_messages")         else open("gm/interpret.py", encoding="utf-8").read()
    assert "lead the tinker on through the archway" in shown


# --- #33: an offer that names the rat is no insult -------------------------------------

def test_talk_about_the_rat_is_not_calling_anybody_one():
    """#33: "The rat's dealt with. … Come with me and you'll have your cargo back" built a
    provoke on the word "rat" (the dire rat just fought): the smuggler's regard fell 61 to
    51 for an offer in his interest. "You rat" still provokes."""
    s, e, _ = _city()
    friend = _friend(e)
    rat = e._bring_in("dire-rat", count=1, name="dire rat")[0]["ref"]
    assert rat
    line = ("\"The rat's dealt with. Come with me and you'll have your cargo "
            "back.\" I tell the smuggler.")
    say = [{"op": "say", "actor": "pc", "params": {"words": "x", "to": friend.ref}}]
    assert not any(r.get("op") == "provoke"
                   for r in judgement.inject_provoke(list(say), line, s))
    assert any(r.get("op") == "provoke" for r in judgement.inject_provoke(
        list(say), '"You rat," I tell the smuggler.', s))


# --- #20 / #21 / #22 / #24: the toll ----------------------------------------------------

def test_no_road_meeting_under_the_ground():
    """#20: walking the gardens' sewers toward the culvert met the road table's
    "Toll-Keeper" in the main channel. With every d100 a hit, the walk meets nobody."""
    s, e, dice = _sewers()
    dice.d100 = 1
    out = _run(e, {"op": "travel", "params": {"place": "the main channel"}})
    eff = next(x for x in out[0].effects if x.get("kind") == "biome")
    assert eff.get("met") == "", out[0].tell


def _next_door(e, here, not_toward=""):
    """The place one hop from `here` (where a walk that met the toll came from), not the
    first hop toward `not_toward`."""
    from rules import places
    known = e.places()
    ahead = (places.route(known, here, not_toward) or (None,))[0] if not_toward else None
    return next(p.id for p in known if p.id not in (here, ahead)
                and (places.route(known, here, p.id) or (None,))[0] == p.id)


def _toll(e, came_from, cp=30):
    met = ontheway.Meeting(kind="toll", roll=95, words=("toll-keeper", "warden"), count=1,
                           template="commoner-level-1", price_cp=cp)
    made = e._meet_on_the_way(met, zone="near")
    return e.scene.actors[made[0]["ref"]], e._ask_toll(met, made, came_from=came_from)


def test_a_toll_has_a_price_bars_the_way_on_and_is_paid_with_a_give():
    """#21: "How much?" got "a few silver pieces"; #22: "I pay the toll-keeper his toll"
    moved no coin; #24: she then walked on past him with no reaction."""
    s, e, _ = _city()
    square = _place(e, "the great square")
    e.place_party(square.id)
    came = _next_door(e, square.id, _place(e, "the market").id)
    from rules import goods as _g
    s.pc().purse = _g.credit(s.pc().purse, 500)
    keeper, said = _toll(e, came)
    assert "copper" in said or "cp" in said or "silver" in said, said
    onward = _place(e, "the market")
    refused = _run(e, {"op": "travel", "params": {"place": onward.name}})
    assert refused[0].status == "refused" and "wants" in refused[0].tell
    assert s.at == square.id
    from rules import goods
    had = goods.in_copper(s.pc().purse)
    paid = _run(e, {"op": "give", "params": {"item": "the toll", "from_": "pc",
                                             "to": keeper.ref}})
    assert paid[0].status == "resolved", paid[0].tell
    assert goods.in_copper(s.pc().purse) == had - 30
    assert not keeper.has_state(states.ASKS_A_TOLL)
    went = _run(e, {"op": "travel", "params": {"place": onward.name}})
    assert went[0].status == "resolved" and s.at == onward.id


def test_turning_back_from_a_toll_is_free():
    """"Pay them or find another way": the way back is never barred."""
    s, e, _ = _city()
    square = _place(e, "the great square").id
    e.place_party(square)
    came = _next_door(e, square)
    _toll(e, came)
    back = _run(e, {"op": "travel", "params": {"place": came}})
    assert back[0].status == "resolved" and s.at == came


def test_the_table_builds_the_toll_from_words_naming_no_sum():
    """#22: the reading was `give target: the toll-keeper, object: his toll`."""
    s, e, _ = _city()
    keeper, _said = _toll(e, "")
    frame = {"actions": [{"act": "give", "target": keeper.name, "object": "his toll",
                          "span": "pay the toll-keeper his toll"}]}
    rows = acts_to_ops.table(frame, s)
    built = [i for r in rows for i in r.intents if i["op"] == "give"]
    assert built and built[0]["params"]["to"] == keeper.ref


# --- #1 / #25: lie in wait --------------------------------------------------------------

def _beast(e, place_id):
    ref = e._bring_in("dire-rat", count=1, name="dire rat")[0]["ref"]
    a = e.scene.people[ref]
    e.scene.move(ref, place_id)
    return a


def test_a_grudge_from_a_fight_walked_out_of_settles_after_a_day():
    """#1: a penguin left on the Red Gull's deck "comes at you" 44 hours after the fight."""
    s, e, _ = _city()
    square = _place(e, "the great square").id
    rat = _beast(e, square)
    e._set_attitude(rat, "hostile", None, "rule:fight-left",
                    payload={"at": s.clock_minutes})
    assert e._lies_in_wait(square) == [rat.ref]
    s.advance(e.GRUDGE_MINUTES + 60)
    assert e._lies_in_wait(square) == []


def test_a_beast_fought_before_the_stamp_still_lies_in_wait():
    """#25: the dire rat fought and fled on T272 (an older save: no `rule:fight-left`,
    only its morale test) sat in the turnkey's room in torchlight and did nothing."""
    s, e, _ = _city()
    square = _place(e, "the great square").id
    rat = _beast(e, square)
    from rules import morale
    rat.add_condition(morale.TESTED_KEY, None, source="rule:morale")
    assert e._lies_in_wait(square) == [rat.ref]


def test_a_walk_stopped_by_somebody_in_wait_goes_no_further():
    """#1: "comes at you" on the deck, and the same plan's next travel walked on ashore —
    "The fight is left behind"."""
    s, e, _ = _city()
    square, market = _place(e, "the great square"), _place(e, "the market")
    rat = _beast(e, square.id)
    e._set_attitude(rat, "hostile", None, "rule:test")
    _run(e, {"op": "travel", "params": {"place": square.name}},
         {"op": "travel", "params": {"place": market.name}})
    assert s.at == square.id and s.in_encounter


# --- #5: a buyer sought for the party's cargo ------------------------------------------

def test_a_buyer_sought_for_cargo_is_answered_from_the_market(monkeypatch):
    """#5: "find a cloth merchant who'll buy a hold full of Khy'vyr silk" was a population
    miss on the whole phrase, and nothing was said."""
    from rules import trade
    s, e, _ = _city()
    trade.add_lot(s, "silk", 20, "pc", 100, s.location_id, "")
    line = "I find a cloth merchant who'll buy my silk."
    monkeypatch.setattr(interpret, "reading_of", lambda text: {"actions": [
        {"act": "seek", "target": "a cloth merchant who'll buy my silk"}]})
    said = judgement.buyers_for_cargo(s, WORLD, line)
    assert "silk" in said and ("buy" in said or "Nobody" in said), said
