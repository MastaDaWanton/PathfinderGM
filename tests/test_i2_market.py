"""I2: the market is its counters, and its master sells nothing.

Two defects, both measured, both the owner's (docs/playtest-2026-09-28.md items 9–10,
docs/fix-interfaces.md §3.4):

  * **The one market keeper who was both authority and only seller.** `places.STAFFED
    ["the market"]` stood "the stallholder who runs the pitch" behind the market; the trade
    panel could open across nobody else there, and — minted on arrival because the panel
    needed a body — she was the first person every player met at every market.
  * **The outfit page's items were unreachable in play.** Lane C closed the outfit page
    once a campaign has begun (the roster and the running sheet had drifted apart). The
    page sells 413 things; a market counter sold GEAR less its food and drink — 40 of them
    — so 356 weapons, 7 armours and 3 shields, 366 of the 413, were on no counter anywhere
    in any world, and the 7 food rows only where a town happened to have a tavern.

The owner's split (2026-09-29): a village has a general goods store and market stalls; a
town or a city has a general goods store, an armorer, a weaponsmith and an alchemist, and
stalls; everything the shops do not carry is spread over the stalls by lot, seeded so a
town keeps its stalls. Mounts are bought, never hired.
"""
from __future__ import annotations

import json

import pytest

from rules import audience, goods, journey, keepers, market, places, schemes, states
from rules.activeeffect import ActiveEffect
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

WORK_HOUR = 10 * 60
SETTLEMENT_KINDS = ("CITY", "TOWN", "SETTLEMENT", "VILLAGE")


def _settlements(world, scales=("village", "town", "city")):
    out = []
    for e in sorted(world.entities.values(), key=lambda e: str(e.id)):
        if not (e.kind in SETTLEMENT_KINDS
                or (e.scale or "").lower() in places.PLACES_BY_SCALE):
            continue
        if places.scale_of(e) in scales:
            out.append(e)
    return out


def _market_of(e) -> str:
    return next(p.id for p in places.home_set(e) if market.is_market(p.id))


def _at_market(world, e, pc="fixtures/pc-kesst.json"):
    s = Scene(location_id=e.id)
    s.add(load_pc(pc))
    s.clock_minutes = WORK_HOUR
    eng = Engine(s, Dice(seed=5), world=world)
    eng.place_party(_market_of(e))
    return s, eng


def _campaign(world, s):
    from play import campaign as cm

    return cm.Campaign(id="i2-test", world_source=str(world.source), scene=s)


# --- every item has a counter -------------------------------------------------------------

def test_every_outfit_item_is_on_sale_in_every_town_and_city(worlds):
    """366 of the outfit page's 413 items were on no counter once a campaign had begun
    (the module docstring). Now every one of them is on one of the market's counters in
    every town and city of every world, on any day — the shops' tills are sized so no
    staple is dropped for being dearer than the till."""
    want = goods.catalogue_ids()
    assert len(want) >= 400, len(want)
    towns = _settlements(worlds, ("town", "city"))
    assert towns, "a world with no town proves nothing"
    for e in towns:
        _market_of(e)                        # every town and city has a market to go to
        for day in (0, 1, 7):
            have = set()
            for c in market.counters(e):
                have |= {str(g.id) for g in market.on_sale(e.id, c.kind, day, {},
                                                           counter_kind=c.kind)}
            missing = sorted(want - have)
            assert not missing, (e.name, day, missing[:10], len(missing))


def test_the_weapons_on_sale_are_the_weapons_the_outfit_page_sold():
    """The outfit page's weapon rule is written twice — `play/outfit_views.catalogue` and
    `goods.outfit_weapons`, because a rules module may not import a view. CLAUDE.md: when
    you fix a rule, grep for every copy. This holds the two copies to one answer."""
    from play.outfit_views import catalogue

    page = catalogue()
    assert {w["key"] for w in page["weapons"]} == set(goods.outfit_weapons())
    assert {f"armour:{a['key']}" for a in page["armour"]} \
        == {g.id for g in goods.table_goods("armour")}
    assert {f"shield:{s['key']}" for s in page["shields"]} \
        == {g.id for g in goods.table_goods("shields")}
    assert {f"gear:{g['key']}" for g in page["gear"]} == {f"gear:{k}" for k in goods.GEAR}


# --- which shops a settlement has ----------------------------------------------------------

def test_a_village_has_exactly_a_general_store_and_stalls(worlds):
    """The owner, 2026-09-29: "villages get a general store and stalls". No armorer, no
    weaponsmith, no alchemist; the horse lines stand at the market only where a village has
    no stables of its own.

    And a leatherworker, everywhere: the owner, 2026-10-08 (leatherworking plan open point
    9), "every town has a leatherworker and that person does not necessarily have a
    tannery", read as every settlement, village up (tests/test_leather_places.py)."""
    villages = _settlements(worlds, ("village",))
    for e in villages:
        cs = market.counters(e)
        shops = [c.id for c in cs if c.sort == "shop"]
        assert shops == ["general", "leatherworker"], (e.name, shops)
        assert {c.sort for c in cs} <= {"shop", "stall", "horses"}
        assert sum(c.sort == "stall" for c in cs) >= 1
    for e in _settlements(worlds, ("town", "city")):
        shops = [c.id for c in market.counters(e) if c.sort == "shop"]
        assert shops == ["general", "armorer", "weaponsmith", "alchemist",
                         "leatherworker"], (e.name, shops)


def test_a_town_keeps_its_stalls_and_two_towns_differ():
    """Chosen by lot, seeded on the settlement: the same stalls every session (nothing is
    stored, so the seed is the record), and not the same stalls in every town — a lot
    that came out the same everywhere would be a table, not a lot."""
    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    towns = _settlements(world, ("town",))
    first = [market.stall_lines(e) for e in towns]
    assert first == [market.stall_lines(e) for e in towns]
    assert len({json.dumps(x) for x in first}) > 1, "every town has the same stalls"
    for hands in first:
        dealt = [line for hand in hands for line in hand]
        assert sorted(dealt) == sorted(s["id"] for s in market.lines_doc()["stalls"])


# --- the counter the player reaches --------------------------------------------------------

def test_a_coil_of_rope_reaches_a_seller_and_never_the_master(worlds):
    """Item 10: the market's one person was its only seller. "I buy a coil of rope" now
    opens the counter that sells rope — the general store's hemp, the cheapest rope that
    is rope (a "rope dart" is a weapon, measured the day the weaponsmith joined) — and
    its keeper, never the master, in every world's first town market and first village."""
    from play import views

    picked = []
    for e in (_settlements(worlds, ("town", "city"))[:1] + _settlements(worlds, ("village",))[:1]):
        s, eng = _at_market(worlds, e)
        c = _campaign(worlds, s)
        offer = views._trade_offer(c, "I try to buy a coil of rope.")
        assert offer is not None and offer["line"], (e.name, offer)
        cs = {x.id: x for x in market.counters(e)}
        assert cs[offer["line"]].sort in ("shop", "stall"), offer
        counter, seller, at, _ = views._counter_pick(c, want="a coil of rope")
        master = keepers.master_here(s)
        assert seller is not None and seller is not master
        assert keepers.keeps_a_counter(seller)
        assert views._merchant_here(s) is not master or master is None
        found, _ = goods.match_want("a coil of rope",
                                    market.on_sale(e.id, counter.kind, 0, {},
                                                   counter_kind=counter.kind))
        assert found.name == "hemp rope", found
        picked.append(offer["line"])
    assert picked


def test_a_town_market_has_a_master_and_a_village_market_does_not(worlds):
    """Q28 (the owner): a master at town scale and up; a village's market is kept by its
    stallholders. The master keeps no counter."""
    for e in _settlements(worlds, ("town", "city"))[:1]:
        s, _ = _at_market(worlds, e)
        master = keepers.master_here(s)
        assert master is not None, e.name
        assert not keepers.keeps_a_counter(master)
        assert "sell nothing" in master.notes
    for e in _settlements(worlds, ("village",))[:1]:
        s, _ = _at_market(worlds, e)
        assert keepers.master_here(s) is None, e.name
        assert any(keepers.keeps_a_counter(a) for a in s.actors.values())


def test_the_panel_opens_on_the_counter_and_lists_the_market(tmp_path):
    """The path the player clicks: /api/trade names the counter, lists every counter, and
    names the seller; asking for another counter opens that one; buying there pays its
    keeper (docs/fix-interfaces.md §2.10)."""
    from django.test import Client, override_settings

    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.location_id = "5bbd0c40345f"                 # Pangrella, a town
        c.scene.clock_minutes = WORK_HOUR
        c.engine().place_party("5bbd0c40345f~urban:the-market")
        c.scene.pc().purse = {"gp": 50}
        c.save()
        post = lambda url, body: Client().post(url, data=json.dumps(body),
                                               content_type="application/json")
        got = post("/api/trade", {"want": "a coil of rope"}).json()
        assert got["line"] == "general" and got["pick"] == "gear:rope"
        ids = [x["id"] for x in got["lines"]]
        assert ids[:4] == ["general", "armorer", "weaponsmith", "alchemist"], ids
        master = keepers.master_here(cm.current().scene)
        assert got["seller"]["ref"] != master.ref
        armour = post("/api/trade", {"line": "armorer"}).json()
        assert armour["line"] == "armorer" and armour["seller"]["ref"] != master.ref
        assert any(r["id"] == "armour:chain shirt" for r in armour["theirs"])
        done = post("/api/trade/do", {"op": "buy", "item": "armour:padded",
                                      "line": "armorer"}).json()
        assert done.get("ok"), done
        assert armour["seller"]["name"] in done["tell"] and master.name not in done["tell"]
        assert cm.current().scene.pc().goods.get("padded") == 1
        cm._LIVE.clear()


# --- the master's hearing ------------------------------------------------------------------

def _tied(pc, background_id="stallholder"):
    pc.apply_effect(ActiveEffect(
        name=background_id, kind="background", key=f"background:{background_id}",
        source=f"background:{background_id}", origin=f"background:{background_id}",
        duration="until-dismissed"))
    return pc


def test_the_master_brushes_off_a_stranger_and_hears_a_market_background(worlds):
    """Design D §4.8: the master is busy and hears only on a ground — regard, a background
    tie to the market, their own business, or the evening count. A stranger asking for them
    at mid-morning is brushed off with a named time and sent to a counter, and it costs no
    regard (Q29); a stallholder by background is heard."""
    from rules import attitude

    e = _settlements(worlds, ("town", "city"))[0]
    s, _ = _at_market(worlds, e)
    master = keepers.master_here(s)
    pc = s.pc()
    asked = "I ask to speak to the master of the market."
    assert audience.addressed(s, master, asked)
    before = attitude.regard_of(master)
    off = audience.hearing(s, master, pc, asked, nearest="the general store")
    assert not off["granted"] and "evening" in off["line"]
    assert "general store" in off["line"]
    assert attitude.regard_of(master) == before, "a brush-off cost regard"
    heard = audience.hearing(s, master, _tied(pc), asked)
    assert heard["granted"] and heard["why"] == "tie"


def test_the_masters_own_business_and_the_evening_count_earn_a_hearing(worlds):
    e = _settlements(worlds, ("town", "city"))[0]
    s, _ = _at_market(worlds, e)
    master = keepers.master_here(s)
    pc = s.pc()
    assert audience.matter_of("That fishwife gave me short weight on her scales.") \
        == "measure"
    assert audience.matter_of("Someone stole my purse at the stalls!") == "theft"
    assert audience.matter_of("I'd like to rent a pitch to sell my own wares.") == "pitch"
    assert audience.matter_of("I buy a coil of rope from a stall.") == ""
    assert audience.hearing(s, master, pc, "Someone stole my purse!")["why"] \
        == "their_business"
    s.clock_minutes = keepers.COUNT_SLOT * 180 + 30
    assert audience.hearing(s, master, pc, "I ask for the master.")["why"] == "the_count"


def test_the_brief_says_the_master_is_busy_and_what_the_hearing_came_to(worlds):
    from gm import prompts

    e = _settlements(worlds, ("town", "city"))[0]
    s, eng = _at_market(worlds, e)
    master = keepers.master_here(s)
    brief = prompts.scene_brief(worlds, s, worlds.get(s.location_id), here=eng.here(),
                                known=eng.places(),
                                player_text="I ask to speak to the master of the market.")
    assert f"THE MASTER OF THE MARKET (fact): {master.name} ({master.ref})" in brief
    assert "they sell nothing" in brief and "do not seek the player out" in brief
    assert "HEARING (fact)" in brief and "does not change for it" in brief
    assert "THE MARKET'S COUNTERS (fact): the general store" in brief


def test_the_master_speaking_first_is_flagged(worlds):
    """The check that holds the page to the brief: the master speaking to a player who did
    not turn to them, with no ground to be heard, is `master-approaches`."""
    from gm.checks import BeatContext, master_unprompted

    e = _settlements(worlds, ("town", "city"))[0]
    s, eng = _at_market(worlds, e)
    master = keepers.master_here(s)
    said = [{"who": master.ref, "to": "you", "line": "You there! What brings you here?"}]

    def ctx(player_text):
        # The line stands on the page: since item 12 of 2026-09-30 the check counts only
        # lines still there, so a cut is seen to have held.
        return BeatContext(door="turn", text=f"'{said[0]['line']}'",
                           player_text=player_text, engine=eng,
                           scene=s, world=worlds, location=worlds.get(s.location_id),
                           reading=None, outcomes=(), tells=(), said=tuple(said),
                           attribution=None, brief="", brief_facts={}, pull=None,
                           was_at=s.at, acting="", turn=3)

    found = master_unprompted.find(ctx("I look over the stalls."))
    assert [f.kind for f in found] == ["master-approaches"]
    assert not master_unprompted.find(ctx("I ask to speak to the master of the market."))
    _tied(s.pc())
    assert not master_unprompted.find(ctx("I look over the stalls."))


# --- a mount, bought and ridden ------------------------------------------------------------

def test_buying_a_light_horse_spends_75_gp_and_the_journey_rides_it(worlds):
    """"no renting just buy one" (the owner, 2026-09-29), at d20pfsrd's price: a light
    horse is 75 gp. Bought, it is a creature in the party — a `journey.MOUNTS` template
    that travels with you — which is exactly what Lane B's journey asks a mount to be, so
    a journey at the riding pace goes at half the walking time with nothing in the journey
    changed. Before this no op could give a party a horse at all."""
    e = _settlements(worlds, ("town", "city"))[0]
    s, eng = _at_market(worlds, e)
    pc = s.pc()
    pc.purse = {"gp": 100}
    has_stables = market.has_stables(e)
    if has_stables:
        eng.place_party(next(p.id for p in places.home_set(e) if p.name == "the stables"))
        stall = "stables"
    else:
        stall = "market:horses"
    out = eng.run(eng.validate([{"op": "buy", "actor": "pc", "because": "t",
                                 "params": {"item": "light horse", "stall": stall}}],
                               origin="author:test")).outcomes[0]
    assert out.status == "resolved", out.tell
    assert goods.in_copper(pc.purse) == 25 * 100
    horse = [a for a in s.actors.values()
             if not a.is_pc and a.from_template in journey.MOUNTS
             and a.has_state(states.TRAVELS_WITH_YOU)]
    assert len(horse) == 1 and horse[0].name == "light horse", out.tell
    assert "light horse" not in {st.base for st in pc.stock.values()}, "a horse in the pack"

    # The journey reads it: riding is half the walking time, with the horse along.
    # A road the journey walks (a sea leg is sailed, and a horse does not speed a ship).
    # Set out from where the horse was bought: `place_party` is placement, not a walk, and
    # would leave the horse standing at the stables.
    legs = journey.legs_from(worlds, e.id)
    road = next((leg for leg in legs if journey.hours_for(leg, 30)[2] != "sea"), None)
    if road is None:
        pytest.skip(f"{e.name} has no road out to ride")
    run = eng.run(eng.validate([{"op": "journey", "actor": "pc", "because": "t",
                                 "params": {"to": road.to_name, "pace": "ride"}}],
                               origin="author:test")).outcomes[0]
    # Arrived or turned back on the road, it rode: the refusal is the only failure here.
    assert run.status != "refused", run.tell
    assert "Nobody in the party has a horse" not in run.tell
    effect = next((x for x in run.effects if x.get("kind") == "journey"), None) or {}
    assert effect.get("pace") == "ride", run.effects
    assert horse[0].ref in (effect.get("mounts") or []), effect


def test_the_stables_sell_every_animal_the_owner_priced():
    """The owner's source, d20pfsrd "Animals & Animal Gear": each animal at its price, and
    each one a creature the bestiary can make. A donkey or a mule has the pony's numbers
    ("Donkeys and mules have the same statistics as ponies")."""
    from rules import bestiary

    priced = {g.key: g for g in goods.stables_goods()}
    assert {k: g.price_gp for k, g in priced.items() if g.kind == "mount"} == {
        "light horse": 75, "light horse (combat-trained)": 110, "heavy horse": 200,
        "heavy horse (combat-trained)": 300, "pony": 30, "pony (combat-trained)": 45,
        "camel": 150, "riding dog": 150, "donkey": 8, "mule": 8}
    for g in priced.values():
        if g.kind == "mount":
            assert bestiary.lookup(g.template) is not None, g.template
    assert priced["riding saddle"].price_gp == 10 and priced["military saddle"].price_gp == 20
    assert priced["pack saddle"].price_gp == 5 and priced["bit and bridle"].price_gp == 2
    assert priced["saddlebags"].price_gp == 4 and priced["animal feed"].price_gp == 0.05
    assert bestiary.lookup("mule")["hp"] == bestiary.lookup("pony")["hp"]
