"""Where the leatherworker works and shops: the leatherworker's counter in every settlement,
the tannery where the settlement's words put one, the field kit, and the rent.

Leatherworking plan §10 and §8.2, contracts §8 (lane G), and the owner's answer 9 of
2026-10-08, which changed the plan: "every town has a leatherworker and that person does
not necessarily have a tannery but every town should have access to leatherworking
supplies and the things needed to use the craft" (read as every settlement, village up).

Measured before any of this, 2026-10-08, which is what these tests hold:

  * across the three shipped exports' 82 settlements, no counter was kept by a
    leatherworker: the market's shops were the general store, the armorer, the
    weaponsmith and the alchemist, and the `tanner` occupation kept only a tannery, which
    12 of the 82 had (11 in Aurvantis, 1 in Pangrella, every one an authored room);
  * the leatherworker's salt, bark, oils, waxes and threads were sold only at whichever
    stall the curio line was dealt to; no counter carried a field kit, and none of the 14
    common hides or 5 common dyes in the catalogue had a price, so none was on any counter;
  * nothing could say whether the party stood in a tannery, or what a vat cost.
"""
from __future__ import annotations

import copy
import dataclasses

import pytest

from rules import inprogress, keepers, lives, market, outskirts, places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.goods import Good, deliver
from rules.sheet import load_pc
from world import loader

AURVANTIS = loader.load_cached("fixtures/aurvantis-campaign.json")
PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")
SYNTHETIC = loader.load_cached("fixtures/synthetic-world.json")
VYRAKON = "5bbd0c40345f"            # Pangrella: a town whose author listed no tannery
TANNERS = "The tanners work the hides of the upland herds below the town."


def _settlements(world):
    for row in world.play.get("settlements") or []:
        e = world.get(row["id"])
        if e is not None and places._settled(e, ""):
            yield e


def _named(world, name):
    return next(e for e in _settlements(world) if e.name == name)


def _saying(world, entity, words: str):
    """A copy of `world` in which `entity`'s own facts say `words` — what an export
    whose settlement names its tanners would carry."""
    facts = dict(entity.facts)
    facts["Trade"] = words
    said = dataclasses.replace(entity, facts=facts)
    out = copy.copy(world)
    out.entities = dict(world.entities)
    out.entities[said.id] = said
    return out, said


def _table(world, location_id: str, seed: int = 3):
    scene = Scene(location_id=location_id)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=seed), world=world)
    engine.place_party()
    return scene, engine


def _run(engine, op, params):
    intents = engine.validate([{"op": op, "actor": "pc", "because": "t", "params": params}],
                              origin="author:test")
    return engine.run(intents).outcomes[-1]


def _at_the_tannery():
    """Kestwick (the synthetic world's town), its words naming its tanners, the party
    standing in the tannery on its outskirts."""
    world, town = _saying(SYNTHETIC, _named(SYNTHETIC, "Kestwick"), TANNERS)
    scene, engine = _table(world, town.id)
    tannery = next(p for p in engine.places() if p.name == "the tannery")
    engine.place_party(tannery.id)
    return world, town, scene, engine, tannery


# --- the leatherworker's counter, in every settlement ---------------------------------------

def test_every_settlement_has_a_leatherworker_at_its_market(worlds):
    """The owner's ruling, 2026-10-08. Before: 0 of 82 settlements had a counter kept by a
    leatherworker. Now every settlement's market has one, village up, and its keeper's
    title reads through the occupation table as the leather-tagged `tanner` — the person
    who sells the craft's supplies, with or without a tannery."""
    seen = 0
    for e in _settlements(worlds):
        home = places.home_set(e)
        assert any(p.name == "the market" for p in home), f"{e.name} has no market"
        counter = market.counter(e, "leatherworker")
        assert counter is not None, f"{e.name} ({places.scale_of(e)}) has no leatherworker"
        work = lives.occupation_for(counter.title)
        assert work and places.LEATHER_WORK in work["tags"], (counter.title, work)
        seen += 1
    assert seen


@pytest.mark.parametrize("scale", ["village", "town", "city"])
def test_the_leatherworker_sells_the_crafts_supplies(scale):
    """Salt, bark, oils, waxes, threads and sinew: every priced common consumable of the
    leatherworker's catalogue, read by kind (never named here), on the counter every day
    and never sold out. Before, they were on whichever stall the curio line was dealt to,
    and a village's two stallholders split nine lines between them."""
    kind = "market:leatherworker"
    want = {str(m.id) for m in market.consumables_of(("leatherworker",))}
    assert {"curing-salt", "oak-bark", "neatsfoot-oil", "thread-wax",
            "sinew-thread"} <= want, "the catalogue lost a staple the owner named"
    for day in (0, 7, 30):
        shelf = market.on_sale("loc~urban:the-market", kind, day, {}, counter_kind=kind,
                               scale=scale)
        have = {str(g.id) for g in shelf}
        assert want <= have, (scale, day, sorted(want - have))
    # Never sold out: a staple is not marked sold.
    taken: dict = {}
    market.mark_sold(taken, "curing-salt", "loc~urban:the-market", kind, 0)
    again = market.on_sale("loc~urban:the-market", kind, 0, taken, counter_kind=kind,
                           scale=scale)
    assert "curing-salt" in {str(g.id) for g in again}


def test_the_counters_stock_scales_with_the_settlement():
    """The owner's 2026-10-07 ruling holds here too: nothing on a village's leatherworker
    dearer than its 500 gp base value, a city's up to 8,000 gp."""
    from rules import pricing

    kind = "market:leatherworker"
    for scale, cap in (("village", 500), ("town", 2_000), ("city", 8_000)):
        for day in range(10):
            shelf = market.on_sale("loc~urban:the-market", kind, day, {},
                                   counter_kind=kind, scale=scale)
            assert max(pricing.worth(g) for g in shelf) <= cap, (scale, day)


def test_common_hides_and_dyes_are_staples_once_the_catalogue_prices_them(monkeypatch):
    """The owner named common hides and dyes. Both are `made_from` (worked, not burnt), so
    the consumables could not carry them, and 0 of the 14 common hides and 0 of the 5
    common dyes had a price. The counter's `staple_kinds` carries every PRICED common row
    of those kinds; pricing one puts it on the counter with nothing else changed."""
    assert market.staple_kinds_at("market:leatherworker") == {
        "leatherworker": ("hide", "dye")}
    rows = [dict(r) for r in market._catalogue_rows("leatherworker")]
    for r in rows:
        # Lane D priced every common hide and dye (2026-10-08); strip them to replay the
        # unpriced catalogue this test was written against.
        r.pop("price_gp", None)
        if r["id"] in ("deer-hide", "madder-red"):
            r["price_gp"] = 2
    monkeypatch.setattr(market, "_catalogue_rows",
                        lambda craft: rows if craft == "leatherworker" else [])
    monkeypatch.setattr(market, "_KIND_STAPLES", None)
    got = {g.id: g for g in market.kind_staple_goods("market:leatherworker")}
    assert set(got) == {"deer-hide", "madder-red"}, sorted(got)
    assert got["deer-hide"].price_gp == 2 and got["deer-hide"].kind == "material"
    assert "deer-hide" not in market.unpriced_staples("leatherworker", ["hide"])
    assert "boar-hide" in market.unpriced_staples("leatherworker", ["hide"])


def test_a_misspelt_staple_kind_is_refused_on_load():
    """A kind no row has would shelve nothing, silently — the curing salt that was on 0
    of 60 days' counters was exactly that shape of mistake."""
    doc = {"shops": [{"id": "leatherworker", "staple_kinds": {"leatherworker": ["hides"]}}]}
    problems = market.staple_kind_problems(doc)
    assert problems and "'hides'" in problems[0] and "fix the spelling" in problems[0]
    assert market.staple_kind_problems(
        {"shops": [{"id": "x", "staple_kinds": {"leatherworker": ["hide", "dye"]}}]}) == []


def test_the_field_kit_is_named_on_the_counter():
    """The leatherworker's field kit is sold where the craft's supplies are. Its goods row
    is another lane's (rules/goods.py GEAR); the counter names it now, so it is on the
    shelf the day the row exists — and not before, because `gear_of` sells only rows the
    goods table has."""
    from rules import goods

    row = next(s for s in market._shops() if s["id"] == "leatherworker")
    assert places.LEATHER_KIT in row["gear"]
    sold = market.gear_of("market:leatherworker")
    assert (places.LEATHER_KIT in sold) == (places.LEATHER_KIT in goods.GEAR)


def test_the_leatherworkers_counter_is_not_a_tannery():
    """The owner: that person "does not necessarily have a tannery". Standing at the market
    with its leatherworker is not standing in a tannery."""
    scene, engine = _table(PANGRELLA, VYRAKON)
    market_place = next(p for p in engine.places() if p.name == "the market")
    engine.place_party(market_place.id)
    assert places.tannery_here(scene, engine.places()) is None
    assert market.tannery_rent(scene, 8) == 0 and market.vat_rent(scene, 28, 1) == 0


# --- a tannery, where the settlement's words put one ----------------------------------------

def test_a_town_whose_words_name_its_tanners_has_a_tannery_on_its_outskirts():
    """Plan §23.1, lane G: "a town with a tanner keeper offers a tannery on its outskirts".
    Out past the last houses, as medieval towns sent the trade for the smell and the
    runoff; not a room of the town. Kestwick without the words has none."""
    world, town = _saying(SYNTHETIC, _named(SYNTHETIC, "Kestwick"), TANNERS)
    ring = outskirts.ring(world, town)
    tannery = next(p for p in ring if p.name == "the tannery")
    assert places.setting_of(tannery.id) == "outside" and places.is_ring(tannery.id)
    assert places.terrain_of(tannery.id) != places.URBAN
    assert places.has_place_tag(tannery, places.TANNERY)
    out = next(p for p in ring if p.name == "the outskirts")
    assert tannery.id in out.exits and out.id in tannery.exits
    assert not any(p.name == "the tannery" for p in places.home_set(town))
    plain = _named(SYNTHETIC, "Kestwick")
    assert not any(p.name == "the tannery" for p in outskirts.ring(SYNTHETIC, plain))


@pytest.mark.parametrize("said", [
    "Its watch walk the walls in leather-clad pairs.",
    "He wore iron-studded leather armor showcasing his blacksmithing skills.",
    "They herd river otters and sell their pelts to the local market.",
    "Hides and wool go down the river every spring.",
])
def test_words_about_what_people_wear_or_trap_earn_no_tannery(said):
    """"leather" alone describes clothes (Pangrella's people wear "iron-studded leather
    armor"), and Aurvantis's otter-herders sell "their pelts to the local market" —
    trapping, not tanning. Only the trade's own nouns are cues."""
    world, town = _saying(SYNTHETIC, _named(SYNTHETIC, "Kestwick"), said)
    assert not places.tannery_implied(town)
    assert not any(p.name == "the tannery" for p in outskirts.ring(world, town))


def test_no_shipped_settlement_earns_a_tannery_from_its_words(worlds):
    """Measured 2026-10-08: the cues fire in none of the 82 settlements' own words, so the
    ring adds nothing to a shipped world; its tanneries are its authors' rooms."""
    for e in _settlements(worlds):
        assert not places.tannery_implied(e), e.name


def test_an_authored_tannery_stands_where_its_author_put_it():
    """Aurvantis authors "the tannery" as a room of 11 settlements. It is the town's
    tannery, kept by a tanner, in the street where the author put it — and the ring adds
    no second one even when the settlement's words name its tanners."""
    town = next(e for e in _settlements(AURVANTIS)
                if any(p.name == "the tannery" for p in places.home_set(e)))
    world, said = _saying(AURVANTIS, town, TANNERS)
    assert places.tannery_implied(said)
    assert not any(p.name == "the tannery" for p in outskirts.ring(world, said))
    scene, engine = _table(world, said.id)
    room = next(p for p in engine.places() if p.name == "the tannery")
    assert places.terrain_of(room.id) == places.URBAN
    engine.place_party(room.id)
    here = places.tannery_here(scene, engine.places())
    assert here is not None and here["kind"] == "town" and here["place"] == room.id
    assert here["keeper"] == keepers.keeper_in(scene, room.id).ref


def test_a_town_tannery_is_kept_by_a_tanner_and_rented():
    """The shape lane E reads (contracts §8), every number from the rule rows: the yard at
    the forge's silver an hour, each vat at two silver a day, four vats of four hide
    units each."""
    _w, _t, scene, engine, tannery = _at_the_tannery()
    keeper = keepers.keeper_in(scene, tannery.id)
    assert keeper is not None and keeper.name == "the tanner"
    assert places.tannery_here(scene, engine.places()) == {
        "kind": "town", "place": tannery.id, "keeper": keeper.ref,
        "rate_cp_per_hour": 10, "vat_rate_cp_per_day": 20,
        "vats": 4, "vats_free": 4, "vat_units": 4}
    # Read from the coordinate alone too: the id spells the ring place's name.
    assert places.tannery_here(scene)["place"] == tannery.id


def test_a_vat_holds_four_hide_units():
    """Plan §23.1, lane G: "the vat holds 4 units". A batch fills a vat per four units
    begun: an elk (2 units) one vat, a dire bear (6) two."""
    assert places.VAT_UNITS == 4
    assert [places.vats_for(u) for u in (0, 0.5, 2, 4, 4.5, 6, 8, 9)] == \
        [0, 1, 1, 1, 2, 2, 2, 3]


def _put_in_vat(scene, actor, place_id, *, vats=None, vat=None, minutes=40_320, craft=None):
    from rules.crafting import Stock

    key = f"hide-{len(actor.stock)}"
    actor.stock[key] = Stock(base="Elk Hide", count=1, craft="leatherworker")
    result = {}
    if vats is not None:
        result["vats"] = vats
    if vat is not None:
        result["vat"] = vat
    block = inprogress.block(craft=craft or places.LEATHER_CRAFT, label="Elk hide in oak bark",
                             started=int(scene.clock_minutes), minutes=minutes,
                             where=f"place:{place_id}", doing="tanning")
    if result:
        block["result"] = result
    actor.stock[key].work = block
    return key


def test_the_partys_tannages_fill_the_vats_until_they_are_collected():
    """`vats_free` is read off the one In-progress store, never a list of its own: two
    vats of one batch and one of another leave one free; a hide that is READY still sits
    in its vat; work at another place, another craft's work, and a hide on the drying rack
    (`vat: False`) fill none here."""
    _w, _t, scene, engine, tannery = _at_the_tannery()
    pc = scene.pc()
    _put_in_vat(scene, pc, tannery.id, vats=2)
    first = _put_in_vat(scene, pc, tannery.id, minutes=60)
    _put_in_vat(scene, pc, "elsewhere~urban:the-tannery", vats=3)
    _put_in_vat(scene, pc, tannery.id, vat=False)
    _put_in_vat(scene, pc, tannery.id, craft="herbalist")
    assert places.vats_in_use(scene, tannery.id) == 3
    assert places.tannery_here(scene, engine.places())["vats_free"] == 1
    scene.clock_minutes = int(scene.clock_minutes) + 120
    assert inprogress.state_of(pc.stock[first], scene.clock_minutes) == "ready"
    assert places.vats_in_use(scene, tannery.id) == 3, "a ready hide is still in the vat"
    inprogress._lift(pc.stock[first])
    assert places.tannery_here(scene, engine.places())["vats_free"] == 2
    _put_in_vat(scene, pc, tannery.id, vats=5)
    assert places.tannery_here(scene, engine.places())["vats_free"] == 0, "never below 0"


def test_the_rent_is_read_off_where_the_party_stands():
    """No caller names a rate (the forge's reason: a second answer to what the tanner
    charges). Three hours in the yard is 3 sp; two vats for a four-week bark tannage is
    11 gp 2 sp; a day begun is a day paid; nothing out of the tannery."""
    _w, _t, scene, engine, _tannery = _at_the_tannery()
    known = engine.places()
    assert market.tannery_rent(scene, 3, known) == 30
    assert market.vat_rent(scene, 28, 2, known) == 1_120
    assert market.vat_rent(scene, 0.1, 1, known) == 20
    assert market.vat_rent(scene, 0, 3, known) == 0 and market.vat_rent(scene, 5, 0) == 0
    engine.place_party()
    assert market.tannery_rent(scene, 3) == 0 and market.vat_rent(scene, 28, 2) == 0


def test_a_tannery_line_never_claims_one_the_town_lacks():
    """The bench's sentence for where to tan: the ring's tannery named as outside the
    town; a town with none says so, and what still works."""
    world, town, scene, engine, _tannery = _at_the_tannery()
    assert places.tannery_line(scene, engine.places(), town) == ""
    engine.place_party()
    line = places.tannery_line(scene, engine.places(), town)
    assert line.startswith("There is a tannery to rent here: the tannery outside Kestwick")
    plain = _named(SYNTHETIC, "Kestwick")
    scene2, engine2 = _table(SYNTHETIC, plain.id)
    line = places.tannery_line(scene2, engine2.places(), plain)
    assert line.startswith("Kestwick has no tannery.") and "field kit" in line


# --- your own tannery -----------------------------------------------------------------------

def test_an_owned_tannery_is_founded_and_read_off_the_holders_effect():
    """The `found` door with kind `tannery` (plan §10: "this retires the 'fixed tools
    deliberately unread' note"). Free to its holder, yard and vats; take the holder's
    effect away and the same building is no longer theirs."""
    scene, engine = _table(PANGRELLA, VYRAKON)
    made = _run(engine, "found", {"name": "my own tannery", "kind": "tannery", "owner": "pc"})
    pid = made.effects[0]["id"]
    _run(engine, "travel", {"place": "my own tannery"})
    assert scene.at == pid
    here = places.tannery_here(scene, engine.places())
    assert here["kind"] == "owned" and here["place"] == pid
    assert here["rate_cp_per_hour"] == 0 and here["vat_rate_cp_per_day"] == 0
    assert here["vats"] == places.OWNED_TANNERY_VATS
    assert market.vat_rent(scene, 28, 4, engine.places()) == 0
    scene.pc().remove_effects(source=f"place:{pid}")
    after = places.tannery_here(scene, engine.places())
    assert after is None or after["kind"] == "town", after


def test_the_players_words_never_make_a_tannery():
    """Contracts §8: "never read from the player's words". A place founded as "my
    tannery" with no kind is a name the player chose."""
    scene, engine = _table(PANGRELLA, VYRAKON)
    made = _run(engine, "found", {"name": "my tannery", "owner": "pc"})
    _run(engine, "travel", {"place": "my tannery"})
    assert scene.at == made.effects[0]["id"]
    assert places.tannery_here(scene, engine.places()) is None


def test_only_a_tanner_keeps_a_tannery():
    """The occupation decides (`content/people/occupations.json`, the `leather` tag): the
    tannery's keeper is a tanner; the smithy's, the market's and the laboratory's are not."""
    assert places.kind_works_leather("tannery")
    for kind in ("smithy", "market", "laboratory", "workshops", "tavern"):
        assert not places.kind_works_leather(kind), kind


# --- the field kit --------------------------------------------------------------------------

def test_the_leatherworkers_field_kit_is_carried():
    """Found in the pack by its names, as the smith's and the alchemist's are; "field
    kit" alone opens nothing (a healer carries a kit into the field too), and the smith's
    kit is not the leatherworker's."""
    pc = load_pc("fixtures/pc-kesst.json")
    assert not places.has_leather_kit(pc)
    deliver(None, pc, Good(id="gear:smith's field kit", name="smith's field kit",
                           price_gp=15.0))
    assert places.has_field_kit(pc) and not places.has_leather_kit(pc)
    assert not places.has_field_kit(pc, "leatherworker")
    pc.goods["field kit"] = 1
    assert not places.has_leather_kit(pc)
    pc.goods["leatherworker's field kit"] = 1
    assert places.has_leather_kit(pc) and places.has_field_kit(pc, craft="leatherworker")
    assert not places.has_field_kit(pc, "weaver")


def test_the_field_kit_reaches_common_and_uncommon_and_hardens_them():
    """The owner's 2026-10-08 answer 3, "add a small kettle to the field kit": the kit
    Hardens what it works, common and uncommon; rare and up wait for a tannery, whose
    kettle and vats reach every tier."""
    assert places.kit_reaches("common") and places.kit_reaches("uncommon")
    assert not places.kit_reaches("rare") and not places.kit_reaches("legendary")
    scene, engine = _table(PANGRELLA, VYRAKON)
    pc = scene.pc()
    bare = places.leather_bench_here(scene, pc, engine.places())
    assert bare["at"] is None and bare["tiers"] == () and not bare["vats"]
    pc.goods["leatherworker's field kit"] = 1
    field = places.leather_bench_here(scene, pc, engine.places())
    assert field["at"] == "field" and field["tiers"] == ("common", "uncommon")
    assert field["tannery"] is None and not field["vats"]
    _w, _t, scene2, engine2, _tannery = _at_the_tannery()
    there = places.leather_bench_here(scene2, scene2.pc(), engine2.places())
    assert there["at"] == "tannery" and there["vats"]
    assert there["tiers"][-1] == "legendary" and there["tannery"]["kind"] == "town"


def test_an_outskirts_place_reads_its_name_without_the_ring_mark():
    """Measured 2026-10-08 by lane G: `keepers.label_of("…~forest:@the-tannery")` read
    "@the tannery", no trade place, so the tanner at an outskirts tannery kept no counter.
    The ring's "@" is part of the id, never the name."""
    from rules import keepers

    assert keepers.label_of("abc123~forest:@the-tannery") == "the tannery"
    assert keepers.label_of("abc123~urban:the-market") == "the market"


def test_the_shipped_catalogue_leaves_no_common_hide_or_dye_unsold():
    """Lane G measured 0 of 14 common hides and 0 of 5 common dyes priced, so none could
    be on a counter; lane D priced them. None may slip back to unpriced. The six generic
    hides are the exception by design: each is only ever a particular beast's, read from
    its stat block at the harvest, so no counter sells one."""
    unpriced = list(market.unpriced_staples("leatherworker", ["hide", "dye"]))
    assert all(m.startswith("generic-") for m in unpriced), unpriced
