"""A town waters the people waiting in it, and its keepers keep their hours on the clock.

Two rulings of the owner's, 2026-10-09, from the leather final pass's playthrough
(docs/leatherworking-questions.md):

1. "yes they should drink from the well". A character "waited in the market overnight
   without drinking — she died of thirst standing in a market with a well". Nothing knew
   a settlement had water: a wait of a day or more drew on the pack and stopped where it
   ran out, and a shorter one rolled thirst. Now a settlement's well or cistern
   (`places.water_in`, read off the settlement's own place set) waters a body living
   through time anywhere inside it (`Engine.water_at_hand`, `survival._provide`), said
   as "drinks at the well". Food is not free: a town feeds nobody.

2. Keepers come back on the clock. "The general store stayed shut next morning with her
   standing at it": a stallholder sent home at dusk came back only when the party
   ARRIVED somewhere (`Engine.settle_people`, once per arrival), so after a wait in place
   the scene listed nobody at the counter, the trade panel refused, and the narrator's
   brief — which states who is here — had an empty stall in daylight. Now the clock's one
   door (`Scene.advance`) settles whoever keeps hours each time it crosses one of
   residency's three-hour slots (`Engine.settle_on_clock`), and who came or went is told.
"""
from __future__ import annotations

from types import SimpleNamespace

from rules import keepers, places, population, residency, states, survival
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id
HOUR = 60
DAY = 24 * HOUR


def _pc(**kw):
    pc = from_dict(to_dict(load_pc("fixtures/pc-kesst.json")), ref="pc")
    pc.kind = "pc"
    pc.goods.clear()                                   # nothing to eat or drink
    for k, v in kw.items():
        setattr(pc, k, v)
    return pc


def _in_vormoor(clock, place="the market", pc=None, seed=3, water=0):
    s = Scene(location_id=VORMOOR)
    s.add(pc or _pc())
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party()
    there = next(p for p in (*e.places(), *e.open_ground()) if p.name == place)
    if s.at != there.id:
        e.run(e.validate([{"op": "travel", "params": {"place": there.name}}],
                         origin="author:test"))
    assert s.at == there.id, (s.at, there.id)
    # The walk there spent minutes; the body starts the test where the test says.
    me = s.pc()
    me.watered_minutes, me.fed_minutes, me.awake_minutes = water, 0, 0
    return s, e, there


def _checks(passed, kinds=("Thirst", "Hunger")):
    return [c for r in passed["body"] for c in r.get("checks") or () if c["kind"] in kinds]


def _wait(e, hours):
    return e.run(e.validate([{"op": "advance_time", "actor": "pc", "because": "I wait",
                              "params": {"amount": hours, "unit": "hour"}}],
                            origin="author:test"))


# --- 1. the town's water ------------------------------------------------------------------

def test_the_owners_night_in_the_market_is_survived_at_the_well():
    """The playthrough's death: a night's wait in the market, nothing to drink, already
    a day and more since the last drink. A wait shorter than a day is not lived from the
    pack, so before the ruling it rolled thirst hour after hour. 30 hours since the last
    drink plus 8 waited is past Kesst's 36 hours of grace: outside the walls that is
    Thirst checks; in the market it is a drink at the well and no check at all."""
    pc = _pc()
    s, e, _ = _in_vormoor(22 * HOUR, pc=pc, water=30 * HOUR)
    res = _wait(e, 8)
    body = " ".join(o.tell for o in res.outcomes if o.op == "body")
    assert "Kesst Vayr drinks at the well." in body, [o.tell for o in res.outcomes]
    assert "Thirst" not in body and "thirst" not in body, body
    assert pc.watered_minutes < 8 * HOUR and not pc.nonlethal

    # The same night on open ground outside the walls has no well, and rolls as before.
    s2, e2, approach = _in_vormoor(22 * HOUR, place="the approach", water=30 * HOUR)
    assert e2.water_at_hand() == ""
    passed = s2.advance(8 * HOUR)
    assert _checks(passed, ("Thirst",)), "no well out here: thirst is rolled"


def test_an_empty_pack_waits_two_days_in_the_market_and_lives():
    """The ruling's case at length: "I wait two days" in the market with nothing in the
    pack stopped at 36 hours for want of water. Now the well waters each day's mark, the
    wait runs whole (hunger's 72 hours are not reached), no check is rolled, and the
    party was standing in the market, not at the well."""
    s, e, market = _in_vormoor(10 * HOUR)
    assert market.name == "the market" and e.water_at_hand() == "the well"
    passed = s.wait(2 * DAY)
    assert passed["minutes"] == 2 * DAY and not passed["stopped"], passed["stopped"]
    assert _checks(passed) == []
    said = " ".join(survival.wait_lines(passed, "pc"))
    assert "Kesst Vayr drinks at the well, twice through the wait." in said, said
    assert not s.pc().has_state("state.down")


def test_the_pack_comes_first_and_the_well_when_it_runs_dry():
    """"when their pack runs dry": two waterskins are a gallon, a day's water, drunk at
    the first day's mark; the second and third days are drunk at the well."""
    pc = _pc()
    pc.goods.update({"waterskin": 2, "trail rations": 3})
    s, e, _ = _in_vormoor(10 * HOUR, pc=pc)
    passed = s.wait(3 * DAY)
    assert not passed["stopped"] and _checks(passed) == []
    said = " ".join(survival.wait_lines(passed, "pc"))
    assert "drinks 1 gallon of water (2 of their waterskins)" in said, said
    assert "drinks at the well, twice through the wait" in said, said
    assert pc.goods.get("empty waterskin") == 2


def test_the_town_feeds_nobody():
    """Water is free at a well; food is not. An empty pack's week-long wait in the market
    stops where hunger's grace runs out (72 hours), before a single Hunger check, and
    says the pack is out of food — not water."""
    s, e, _ = _in_vormoor(10 * HOUR)
    passed = s.wait(7 * DAY)
    assert passed["stopped"] == "food" and passed["minutes"] == 72 * HOUR
    assert _checks(passed) == []
    said = " ".join(survival.wait_lines(passed, "pc"))
    assert "no food in the pack" in said and "drinks at the well" in said, said


def test_off_the_settlements_own_ground_there_is_no_well():
    """The ring and open ground are not the settlement: out there a wait on an empty pack
    still stops at 36 hours for want of water, as it did."""
    s, e, _ = _in_vormoor(10 * HOUR, place="the approach")
    passed = s.wait(3 * DAY)
    assert passed["stopped"] == "water" and passed["minutes"] == 36 * HOUR


def test_a_settlement_drinks_from_what_its_places_hold():
    """Read off the place set, never off words: a well and a cistern are water
    (`place.water`); the docks, which stand ON water, are not. An authored settlement
    whose author listed no water has none — nothing is appended — and one that lists a
    cistern drinks there."""
    tag = places.WATER
    assert places.has_place_tag(places.Place(name="the well"), tag)
    assert places.has_place_tag(places.Place(name="the cistern"), tag)
    assert places.has_place_tag(places.Place(name="the Old Pump", kind="well"), tag)
    assert not places.has_place_tag(places.Place(name="the docks"), tag)

    def town(*names):
        rows = [{"id": f"t1~urban:{places._slug(n)}", "name": n,
                 "exits": [f"t1~urban:{places._slug(m)}" for m in names if m != n]}
                for n in names]
        return SimpleNamespace(id="t1", name="Dryhollow", kind="CITY", scale="town",
                               places=rows)

    assert places.water_in(places.home_set(town("the market", "the inn"))) is None
    got = places.water_in(places.home_set(town("the market", "the cistern")))
    assert got is not None and got.name == "the cistern"


def test_every_authored_settlement_shipped_lists_its_water():
    """Measured 2026-10-09 before deciding not to append a well to authored lists: all 64
    of Aurvantis's and all 12 of Pangrella's authored settlements list a well or a
    cistern. A world that ships one without water has none (and `check_places` notes it);
    these two do not."""
    for path, want in (("fixtures/aurvantis-campaign.json", 64),
                       ("fixtures/pangrella-campaign.json", 12)):
        world = load_cached(path)
        towns = [e for e in world.entities.values() if e.kind == "CITY"]
        assert len(towns) == want, (path, len(towns))
        dry = [e.name for e in towns if places.water_in(places.home_set(e)) is None]
        assert dry == [], (path, dry)


# --- 2. keepers on the clock ---------------------------------------------------------------

def test_the_general_store_is_open_at_first_light_with_the_party_still_standing_there():
    """The playthrough: at the market at ten at night the general store's keeper goes
    home; she waits nine hours where she stands. Before, the keeper stayed home — the
    scene listed nobody, the counter answered shut — because only an arrival settled
    anybody. Now the clock brings the keeper back, the batch says so, the counter is open,
    and the narrator's brief lists the keeper and no shut counter."""
    from gm import prompts

    s, e, market = _in_vormoor(22 * HOUR)
    keeper = keepers.seller_in(s, market.id)
    assert keeper is not None and keeper.ref not in s.actors
    assert residency.is_offstage(keeper.at)
    res = _wait(e, 9)
    assert (s.clock_minutes % DAY) // HOUR == 7
    assert keeper.ref in s.actors and keeper.at == market.id
    assert keepers.shut_here(s) == ""
    came = [o for o in res.outcomes if o.op == "comings"]
    assert came and "comes to the market and opens the counter" in came[0].tell, \
        [o.tell for o in res.outcomes]
    brief = prompts.scene_brief(WORLD, s, WORLD.get(VORMOOR), here=market, known=e.places())
    assert "COUNTER SHUT" not in brief
    who = brief.split("WHO IS HERE", 1)[1]
    assert str(keeper.name) in who, who[:600]


def test_the_trade_panel_opens_across_the_counter_after_the_wait():
    """The panel's half of the same morning: `_counter_pick` answered "Nobody is at the
    general store just now". After the wait in place its keeper is there, behind it."""
    from play import campaign as cm
    from play import views

    s, e, market = _in_vormoor(22 * HOUR)
    _wait(e, 9)
    c = cm.Campaign(id="water-and-hours", world_source=str(WORLD.source), scene=s)
    counter, seller, at, choices = views._counter_pick(c)
    assert choices and counter.id == "general"
    assert seller is not None and seller.ref in s.actors
    assert keepers.shut_here(s, seller) == ""


def test_the_stall_packs_up_at_dusk_while_the_party_stands_at_it():
    """And the other way: at the market by day, waiting into the night, the general
    store's keeper shuts up and goes home, and the batch says so."""
    s, e, market = _in_vormoor(10 * HOUR)
    keeper = keepers.seller_in(s, market.id)
    assert keeper is not None and keeper.ref in s.actors
    res = _wait(e, 11)                                   # 21:00, the curfew slot
    assert keeper.ref not in s.actors and residency.is_offstage(keeper.at)
    went = [o for o in res.outcomes if o.op == "comings"]
    assert went and "shuts the counter and leaves the market" in went[0].tell


def test_a_keeper_coming_back_gets_a_square_and_nobody_else_moves():
    """People keep their square (ruling 2026-09-28): the returning keeper is given one
    on arrival (`Scene.move`'s rule); the player's own square does not change."""
    s, e, market = _in_vormoor(22 * HOUR)
    keeper = keepers.seller_in(s, market.id)
    before = dict(s.positions)
    _wait(e, 9)
    assert keeper.ref in s.actors
    if s.grid is not None:
        assert keeper.ref in s.positions
        assert s.positions.get("pc") == before.get("pc")


def _stallholder(s, *, talking=False):
    """A resident met in the market, whose day (`residency`'s day-work key: home 21:00 to
    6:00, at the market from 6:00, company or home from 18:00) is the market's."""
    from gm import judgement

    rec = population.note(s, "a stallholder with a ledger")
    rec["life"].update(work="stallholder", work_name="stallholder", mobility="resident",
                       sociability=0)
    ref = judgement.embody_sought(s, "I talk to the stallholder with a ledger.", WORLD)
    s.people[ref].remove_effects(source="talk")
    if talking:
        s._engine.join_talk(s.people[ref])
    return ref


def _comings(res):
    return " ".join(o.tell for o in res.outcomes if o.op == "comings")


# --- 3. a wait the player chose: people go about their day ---------------------------------
#
# The owner, 2026-10-09: "if I wait then people should go about their day. if its a shop
# owner and the store isnt closed they shouldnt go home just because i waited in their
# shop". Until then the doorway ruling (2026-09-25, the woman in the doorway "should stay
# there until i leave or something moves them") held through every stretch of clock, a
# chosen wait included: measured on master 095c5095, a stallholder met at the market at
# 17:00 was still standing beside the party at 01:00 after an eight-hour wait, in the
# scene, the panel and the brief, though her own day had her at home from 21:00.

def test_a_wait_sends_the_stallholder_with_the_party_about_her_day():
    """Re-pinned with the owner's words: the same eight hours from 17:00 to 01:00 that
    `test_somebody_standing_with_the_party_who_keeps_no_counter_still_stays` used to pin
    her in place now send her home (offstage), told "goes about their day", and the scene,
    the conversation panel and the narrator's brief agree she is gone."""
    from gm import prompts

    s, e, market = _in_vormoor(17 * HOUR)
    ref = _stallholder(s, talking=True)
    name = s.people[ref].name
    assert e.talking_to() and ref in s.actors
    res = _wait(e, 8)                                       # 01:00, home time for her day
    assert ref not in s.actors and residency.is_offstage(s.people[ref].at)
    said = _comings(res)
    assert "goes about their day and leaves the market" in said, \
        [o.tell for o in res.outcomes]
    # She held the conversation; her leaving is its third exit (ruling 2026-09-24), said in
    # the same tell, and the talk panel (`talking_to`) is empty at once.
    assert "The conversation with them is over." in said
    assert e.talking_to() == [] and not s.people[ref].has_state(states.TALKING)
    brief = prompts.scene_brief(WORLD, s, WORLD.get(VORMOOR), here=market, known=e.places())
    assert str(name) not in brief.split("WHO IS HERE", 1)[1].split("\n\n", 1)[0]


def test_any_other_stretch_of_clock_still_keeps_her_where_she_stands():
    """The doorway ruling stands for clock the player did not spend waiting — a craft's
    hours, a walk, a minute's op across 6:00 — because nothing in those says the party
    stood about long enough for the town to move on. The same eight hours through
    `Scene.advance` (no `waited`) leave her beside the party."""
    s, e, market = _in_vormoor(17 * HOUR)
    ref = _stallholder(s)
    out = s.advance(8 * HOUR)
    assert ref in s.actors and ref not in out["moved"]


def test_an_open_keeper_stays_behind_the_counter_through_a_two_hour_wait():
    """The owner's second clause: "if its a shop owner and the store isnt closed they
    shouldnt go home just because i waited in their shop". At the market at 10:00, two
    hours waited across the noon slot, in conversation with the general store's keeper:
    she is still at her counter, the counter is open, nothing is told of her coming or
    going, and the conversation is still open (a wait is not an exit)."""
    s, e, market = _in_vormoor(10 * HOUR)
    keeper = keepers.seller_in(s, market.id)
    assert keeper is not None and keeper.ref in s.actors
    e.join_talk(keeper)
    square = s.positions.get(keeper.ref)
    res = _wait(e, 2)
    assert (s.clock_minutes % DAY) // HOUR == 12
    assert keeper.ref in s.actors and keepers.shut_here(s) == ""
    assert str(keeper.name) not in _comings(res)
    assert keeper in e.talking_to()
    assert s.positions.get(keeper.ref) == square, "people keep their square"


def test_the_open_keeper_still_shuts_up_at_the_counters_hour_in_a_wait():
    """And leaves only when the counter shuts, on its own hours: the same keeper, a wait
    from 10:00 to 21:00, packs up — in conversation or not."""
    s, e, market = _in_vormoor(10 * HOUR)
    keeper = keepers.seller_in(s, market.id)
    e.join_talk(keeper)
    res = _wait(e, 11)
    assert keeper.ref not in s.actors
    said = _comings(res)
    assert "shuts the counter and leaves the market" in said
    assert "The conversation with them is over." in said and e.talking_to() == []


def test_a_companion_never_goes_about_their_day():
    """A companion travels with the party (`bond.travels-with-you`): no wait sends them
    off, though their own day would."""
    from rules.activeeffect import ActiveEffect
    from rules import states

    s, e, market = _in_vormoor(17 * HOUR)
    ref = _stallholder(s)
    s.people[ref].apply_effect(ActiveEffect(
        name="travelling with you", kind="bond", key="company", source="company",
        origin="author:test", duration="until-dismissed",
        tags=(states.TRAVELS_WITH_YOU,)))
    _wait(e, 8)
    assert ref in s.actors


def test_a_talker_whose_day_keeps_them_here_stays_in_the_conversation():
    """A wait is not itself an exit (Everweave's implicit exits are the conversation
    ruling's warning): at 10:00, two hours waited, the stallholder's day keeps her at the
    market, so she stays, on her square, and the conversation is still open."""
    s, e, market = _in_vormoor(10 * HOUR)
    ref = _stallholder(s, talking=True)
    square = s.positions.get(ref)
    res = _wait(e, 2)
    assert ref in s.actors and s.people[ref] in e.talking_to()
    assert s.people[ref].name not in _comings(res)
    assert s.positions.get(ref) == square


def test_a_night_waited_out_at_her_stall_is_told_as_a_night_she_went_home():
    """The stretch is settled once, at its end (Exult's teleport to the current slot), so
    a wait from 17:00 to 07:00 found her at the market at both ends — her day has her there
    from 6:00 — and the narrator would have been handed the same face in the same place and
    nothing else: the woman who stood all night beside the party, which is what the ruling
    is against. She went home at 21:00 and came back at first light, and is told so."""
    s, e, market = _in_vormoor(17 * HOUR)
    ref = _stallholder(s, talking=True)
    res = _wait(e, 14)
    assert (s.clock_minutes % DAY) // HOUR == 7
    assert ref in s.actors
    said = _comings(res)
    assert "goes about their day and is back at the market" in said, said
    assert "The conversation with them is over." in said and e.talking_to() == []


def test_a_nights_rest_is_a_wait_too():
    """A night's sleep is a wait the player chose: resting at the market from 17:00 (to
    the dawn, 6:00) sends the stallholder home for the night and back, told."""
    s, e, market = _in_vormoor(17 * HOUR)
    ref = _stallholder(s)
    res = e.run(e.validate([{"op": "rest", "actor": "pc", "because": "I sleep",
                             "params": {"kind": "night"}}], origin="author:test"))
    assert (s.clock_minutes % DAY) // HOUR == 6, [o.tell for o in res.outcomes]
    assert "goes about their day and is back at the market" in _comings(res)


def test_a_slot_crossed_in_a_fight_is_settled_once_the_fight_is_over():
    """Nothing moves while initiative runs (`settle_on_clock` refuses mid-fight), but the
    slot is owed, not lost: the first batch after the fight brings the keeper back."""
    s, e, market = _in_vormoor(22 * HOUR)
    keeper = keepers.seller_in(s, market.id)
    s.initiative, s.turn = [("pc", 10)], 0
    s.advance(9 * HOUR)
    assert keeper.ref not in s.actors and s._hours_due
    s.initiative, s.turn = [], -1
    e.run(e.validate([{"op": "narrate_only", "because": "after the fight"}],
                     origin="author:test"))
    assert keeper.ref in s.actors and not s._hours_due


def test_a_scene_with_no_engine_moves_its_clock_as_before():
    """The keepers' pass needs the world, which only an engine holds; a bare scene's clock
    is exactly what it was."""
    s = Scene(location_id=VORMOOR)
    s.add(_pc())
    out = s.advance(9 * HOUR)
    assert out["moved"] == [] and s._comings_said == []
