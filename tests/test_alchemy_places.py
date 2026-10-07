"""Where the alchemist works: the town laboratory, the owned one, the field kit, the rent.

Alchemy plan §14 and contracts §9 (lane G), the forge's kit-and-smithy rule mirrored. The
field kit goes wherever the alchemist stands and does common and uncommon work; a
LABORATORY adds Distill, Sublime, Transmute, rare-and-above reagents, +2 circumstance and
a fume hood, and is either the town's, rented by the hour, or the player's own, founded
through the `found` door and held as `holds.place.<slug>`.

The owner's ruling of 2026-10-06 (plan §21 open point 7): **every city has a laboratory to
rent**. Towns and villages have one only when their own words name their alchemists, or
play founds one.

Measured before any of this, 2026-10-06, which is what these tests hold:

  * a laboratory was in **0 of the 82 settlements** of the three shipped exports (0 of
    Aurvantis's 16 cities, 0 of Pangrella's 6, 0 of the synthetic world's 1), and the
    settlement table had no laboratory row, so 0 of 200 generated cities had one;
  * there was no alchemist occupation at all: "the alchemist" read through the
    occupation table named nobody, so a laboratory could have had no keeper and the
    teacher route no teacher;
  * the settlement words name alchemists in 11 Aurvantis settlements — "a black-market
    alchemist collective" in nine, "alchemical explosives" and "alchemical curiosities"
    in two — and bare "alchemy" in none;
  * an authored place's `kind` was read by nothing, though the World Bible document had
    promised since 2026-10-04 that "the Anvil" with `"kind": "smithy"` was a smithy.

World-agnostic where the machinery is (the standing instruction of 2026-09-28): the
`worlds` fixture runs the per-export tests once per shipped export.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import keepers, lives, market, places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.goods import Good, deliver
from rules.sheet import load_pc
from world import loader

PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")
SYNTHETIC = loader.load_cached("fixtures/synthetic-world.json")
VYRAKON = "5bbd0c40345f"            # Pangrella: a town whose author listed no laboratory


def _town(scale: str, ident: str = "aaaabbbbcccc", facts=None, prose="", authored=()):
    class Loc:
        id = ident
        name = "Testville"
        kind = "CITY"
    Loc.scale = scale
    Loc.facts = facts or {}
    Loc.prose = prose
    Loc.places = list(authored)
    return Loc()


def _names(loc) -> set[str]:
    return {p.name for p in places.home_set(loc)}


def _has_lab(entity) -> bool:
    return any(places.has_place_tag(p, places.LAB) for p in places.home_set(entity))


def _earned(prose: str, scale: str = "town") -> list[str]:
    return [s for s, _a in places.implied_spots(_town(scale, prose=prose))]


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


def _caddonbury():
    return next(SYNTHETIC.get(r["id"]) for r in SYNTHETIC.play["settlements"]
                if SYNTHETIC.get(r["id"]).name == "Caddonbury")


def _at_the_city_lab():
    """The synthetic world's Caddonbury, a generated city, standing in its laboratory with
    its keeper stood up — the way `Engine` does it on arrival."""
    city = _caddonbury()
    lab = next(p for p in places.home_set(city) if p.name == "the laboratory")
    scene, engine = _table(SYNTHETIC, city.id)
    engine.place_party(lab.id)
    keepers.staff(engine)
    return scene, engine, lab


# --- every city has one ----------------------------------------------------------------------

def test_a_generated_city_always_has_a_laboratory():
    """0 of 200 generated cities had one before: the settlement table had no laboratory
    row. The owner: "every city has a laboratory to rent"."""
    for i in range(40):
        assert "the laboratory" in _names(_town("city", f"c{i:08x}")), i


def test_every_city_in_every_shipped_world_has_a_laboratory(worlds):
    """Measured 2026-10-06: 0 of 82 settlements in the three exports had a laboratory, so
    the alchemist had nowhere to Distill in any city of any shipped world. Every one is
    authored except the synthetic world's generated three, and an authored city gets one
    appended exactly as it gets its smithy."""
    cities = [worlds.get(r["id"]) for r in worlds.play.get("settlements") or []]
    cities = [c for c in cities if c is not None and places.scale_of(c) == "city"]
    assert cities, "this export ships no city; the test is checking nothing"
    for city in cities:
        assert _has_lab(city), city.name


def test_no_town_or_village_in_a_shipped_world_is_given_one_unasked(worlds):
    """The plan's other half: a town or village has a laboratory only when its own words
    say so, and an AUTHORED one never has one appended — "an author who listed six rooms
    has said what the town has". Aurvantis's eleven alchemist-worded settlements are all
    authored, so `tools/check_places.py` notes them for the author instead."""
    for row in worlds.play.get("settlements") or []:
        ent = worlds.get(row["id"])
        if ent is None or places.scale_of(ent) == "city":
            continue
        assert not _has_lab(ent), ent.name


def test_a_generated_town_or_village_is_never_drawn_a_laboratory():
    """`ONLY_WHEN_NAMED`: the fill never draws the laboratory, so a town gets one from its
    words and not from its seed. Kept out of the rotation too, which is why adding the row
    changed 0 of 200 generated village sets and 0 of 200 town sets (measured 2026-10-06)."""
    for scale in ("village", "town"):
        for i in range(60):
            assert "the laboratory" not in _names(_town(scale, f"{scale[0]}{i:08x}")), (scale, i)


def test_the_laboratory_is_appended_beside_the_smithy_to_an_authored_city():
    """Both rows of `APPENDED_TO_AUTHORED["city"]`, reachable from the first place (an
    exit is adjacency, and adjacency runs both ways)."""
    market_place = {"id": "aaaabbbbcccc~urban:the-market", "name": "the market",
                    "about": "Stalls.", "parent": "aaaabbbbcccc", "terrain": "urban",
                    "exits": [], "origin": "world"}
    got = places.home_set(_town("city", authored=[market_place]))
    lab = next(p for p in got if p.name == "the laboratory")
    assert lab.origin == "generated" and lab.exits == (got[0].id,)
    assert lab.id in got[0].exits
    assert "the smithy" in {p.name for p in got}


# --- the world's own words --------------------------------------------------------------------

@pytest.mark.parametrize("said", [
    "Beneath the formal government, a black-market alchemist collective exercises real "
    "influence in Dustgate.",
    "A town on the strength of its trade in alchemical explosives.",
    "The chymists of the lower town keep their stills burning all night.",
    "It is known across the coast as a school of alchemy.",
])
def test_a_settlement_whose_words_name_its_alchemists_has_a_laboratory(said):
    """Aurvantis's own sentences (Dustgate, Pilfnook) and two more ways prose says it. In a
    generated town or village the earned laboratory is a room the party can walk into."""
    assert "the laboratory" in _earned(said)
    assert "the laboratory" in _names(_town("town", prose=said))
    assert "the laboratory" in _names(_town("village", prose=said))


@pytest.mark.parametrize("said", [
    "Trade there works by the strange alchemy of debt and favour.",
    "The apothecary on the corner sells feverfew and willow bark.",
    "Its labours are many and its laborers are poor.",
])
def test_a_metaphor_or_a_herbalists_shop_earns_no_laboratory(said):
    """Bare "alchemy" is how prose makes a metaphor, and an apothecary is the herbal
    healer's shop (occupations.json `healer`): herbalism's, not alchemy's. Neither earns
    a laboratory; "labour" and "laborers" never match half of "laboratory"."""
    assert "the laboratory" not in _earned(said)


def test_the_laboratory_cue_never_pushes_out_what_a_town_already_earned():
    """Earned spots are taken in table order up to MOST_IMPLIED (4). The laboratory row is
    last, after the smithy, so a port town whose words also name its alchemists keeps its
    docks, its bridge, its guildhall and its library."""
    words = ("A port on the river, run by its guilds, its scribes keeping the archives; "
             "the smiths work by the quay and the alchemists above them.")
    earned = _earned(words)
    assert earned[:4] == ["the docks", "the bridge", "the guildhall", "the library"], earned
    assert earned[-2:] == ["the smithy", "the laboratory"], earned


# --- an author's own laboratory, by any name -----------------------------------------------

def _authored_city(**lab_over):
    base = {"id": "aaaabbbbcccc~urban:the-glasshouse", "name": "the glasshouse",
            "about": "Stills and smoke.", "parent": "aaaabbbbcccc", "terrain": "urban",
            "exits": [], "origin": "world"}
    base.update(lab_over)
    return _town("city", authored=[base])


def test_an_authored_kind_makes_the_worlds_own_laboratory():
    """`"kind": "laboratory"` on "the Glasshouse" makes it the city's laboratory, so no
    second one is appended. Before 2026-10-06 an authored place's kind was read by
    nothing: the World Bible document promised it for the smithy and the code did not."""
    got = places.home_set(_authored_city(kind="laboratory"))
    labs = [p for p in got if places.has_place_tag(p, places.LAB)]
    assert [p.name for p in labs] == ["the glasshouse"], [p.name for p in got]
    assert places.keeper_of(f"the {labs[0].kind}")[0] == "the alchemist"


def test_the_anvil_with_kind_smithy_is_the_smithy_the_document_promised():
    """docs/places-and-races-for-world-bible.md: "the Anvil" with `"kind": "smithy"`.
    Measured before the reader: the city got "the smithy" appended beside it."""
    city = _town("city", authored=[{
        "id": "aaaabbbbcccc~urban:the-anvil", "name": "the anvil", "about": "Iron.",
        "parent": "aaaabbbbcccc", "terrain": "urban", "exits": [], "origin": "world",
        "kind": "forge"}])
    got = places.home_set(city)
    assert "the smithy" not in {p.name for p in got}
    assert places.has_place_tag(got[0], places.SMITHY)


def test_an_unknown_authored_kind_is_dropped_not_guessed():
    """A kind the app has no row for reads as nothing, and the name reads as it always
    did; the city then gets its appended laboratory, because nothing said it had one."""
    got = places.home_set(_authored_city(kind="observatory"))
    assert got[0].kind == ""
    assert "the laboratory" in {p.name for p in got}


# --- the people -------------------------------------------------------------------------------

def test_an_alchemist_is_an_occupation_carrying_the_alchemy_tag():
    """There was none: "the alchemist" read through the occupation table named nobody,
    so a laboratory could have no keeper and alchemy no teacher. Not "apothecary" — that
    stays the herbal healer's word."""
    occ = lives.occupation_for("the alchemist")
    assert occ is not None and occ["id"] == "alchemist"
    assert places.ALCHEMY_WORK in occ["tags"]
    assert lives.occupation_for("the chymist")["id"] == "alchemist"
    assert lives.occupation_for("the apothecary")["id"] == "healer"


def test_the_alchemist_is_the_last_occupation_row():
    """Appended, never inserted: an unnamed person's work is `rng.choice(pool)`, and a row
    added in the middle would shift every later row's index and re-roll the work of every
    person met from now on whose seed lands past it. Last, it changes only the draws that
    land on the new index."""
    rows = json.loads(Path("content/people/occupations.json").read_text(
        encoding="utf-8"))["occupations"]
    assert rows[-1]["id"] == "alchemist"


def test_only_a_laboratory_is_kept_by_an_alchemist():
    """The market, a tavern, the smithy and the workshops are kept by a master, a barkeep,
    a smith and an artisan. The market's alchemist COUNTER is kept by an alchemist, and
    that does not make the market a laboratory — the place's own kind decides."""
    assert places.kind_works_alchemy("laboratory")
    assert not places.kind_works_forge("laboratory")
    for kind in ("market", "tavern", "smithy", "workshops", "temple", "well"):
        assert not places.kind_works_alchemy(kind), kind
    scene, _engine = _table(PANGRELLA, VYRAKON)
    assert places.laboratory_here(scene) is None, scene.at


def test_the_city_laboratory_is_the_towns_with_an_alchemist_behind_it():
    """The contract's shape (contracts §9), at the synthetic world's Caddonbury."""
    scene, engine, lab = _at_the_city_lab()
    keeper = keepers.keeper_in(scene, lab.id)
    assert keeper is not None
    assert places.laboratory_here(scene, engine.places()) == {
        "kind": "town", "place": lab.id, "keeper": keeper.ref,
        "rate_cp_per_hour": market.LAB_RENT_CP_PER_HOUR, "fume_hood": True}
    # What the teacher route reads when no population record names the work: the
    # keeper's own words say what they are.
    assert "alchemist" in (keeper.notes or "").lower()


def test_a_laboratory_is_not_a_smithy_and_a_smithy_is_not_a_laboratory():
    """Two benches, two tags: standing at the city's laboratory opens no furnace, and the
    smithy opens no still."""
    scene, engine, lab = _at_the_city_lab()
    assert places.smithy_here(scene, engine.places()) is None
    smithy = next(p for p in places.home_set(_caddonbury()) if p.name == "the smithy")
    engine.place_party(smithy.id)
    assert places.laboratory_here(scene, engine.places()) is None
    assert places.smithy_here(scene, engine.places()) is not None


def test_the_floor_above_the_laboratory_is_not_the_laboratory():
    """The hood is where you walk in; the alchemist's bedroom upstairs is not."""
    lab = next(p for p in places.home_set(_caddonbury()) if p.name == "the laboratory")
    scene = Scene(location_id=_caddonbury().id)
    scene.at = places.storey_id(lab.id, 1)
    assert places.laboratory_here(scene) is None


# --- founded --------------------------------------------------------------------------------

def test_a_founded_laboratory_in_a_settlement_without_one(worlds):
    """"Places must be creatable" (ruled 2026-10-03): in a settlement whose author listed
    no laboratory — every non-city in every shipped export — the `found` door makes one,
    an alchemist is stood up behind it, and the party is at a town laboratory."""
    target = None
    for row in worlds.play.get("settlements") or []:
        entity = worlds.get(row["id"])
        if entity is not None and places._settled(entity, "") and not _has_lab(entity):
            target = entity
            break
    assert target is not None, "every settlement in this export already has a laboratory"
    scene, engine = _table(worlds, target.id)
    made = _run(engine, "found", {"name": "the laboratory"})
    assert made.effects and made.effects[0]["is"] == "laboratory", made.tell
    went = _run(engine, "travel", {"place": "the laboratory"})
    assert scene.at == made.effects[0]["id"], went.tell
    keepers.staff(engine)
    here = places.laboratory_here(scene, engine.places())
    assert here is not None and here["kind"] == "town", here
    assert here["rate_cp_per_hour"] == market.LAB_RENT_CP_PER_HOUR and here["fume_hood"]
    keeper = keepers.keeper_in(scene, scene.at)
    assert keeper is not None and here["keeper"] == keeper.ref


def test_the_words_people_use_for_a_laboratory_found_one():
    """A plan writes `kind="lab"` as readily as "laboratory". Not "alchemist" (the person,
    and the market's counter) and not "apothecary" (the herbalist's shop)."""
    for word in ("lab", "the lab", "alchemy lab", "alchemist's lab", "alchemical laboratory"):
        assert places.kind_named(word) == "laboratory", word
        assert places.known_kind(word), word
    for word in ("alchemist", "apothecary", "alchemist's"):
        assert places.kind_named(word) != "laboratory", word


def test_the_players_words_never_make_a_laboratory():
    """Contracts §9: "never read from the player's words". A place founded as "my
    laboratory" with no kind is a name the player chose."""
    scene, engine = _table(PANGRELLA, VYRAKON)
    made = _run(engine, "found", {"name": "my laboratory", "owner": "pc"})
    _run(engine, "travel", {"place": "my laboratory"})
    assert scene.at == made.effects[0]["id"]
    assert places.laboratory_here(scene, engine.places()) is None


def test_an_owned_laboratory_is_read_off_the_holders_effect():
    """The owner field is the claim; `holds.place.<slug>` is the fact. Free to its owner;
    take the effect away and the same room stops being theirs (law 2)."""
    scene, engine = _table(PANGRELLA, VYRAKON)
    made = _run(engine, "found", {"name": "my workroom", "kind": "lab", "owner": "pc"})
    _run(engine, "travel", {"place": "my workroom"})
    pid = made.effects[0]["id"]
    assert scene.at == pid
    here = places.laboratory_here(scene, engine.places())
    assert here["kind"] == "owned" and here["place"] == pid and here["fume_hood"]
    assert here["rate_cp_per_hour"] == 0
    assert market.lab_rent(scene, 8, engine.places()) == 0, "the party pays itself rent"
    scene.pc().remove_effects(source=f"place:{pid}")
    after = places.laboratory_here(scene, engine.places())
    assert after is None or after["kind"] == "town", after


def test_a_friends_laboratory_is_rented_from_them():
    """A founded laboratory held by somebody else is theirs: the party pays the town's
    rate, to the holder."""
    from rules.activeeffect import ActiveEffect

    scene, engine = _table(PANGRELLA, VYRAKON)
    made = _run(engine, "found", {"name": "the laboratory"})
    _run(engine, "travel", {"place": "the laboratory"})
    keepers.staff(engine)
    alchemist = keepers.keeper_in(scene, scene.at)
    pid = made.effects[0]["id"]
    for raw in scene.founded:
        if raw["id"] == pid:
            raw["owner"] = alchemist.ref
    alchemist.apply_effect(ActiveEffect(
        name="holds the laboratory", kind="situation", key=f"holds:{pid}",
        source=f"place:{pid}", origin="found", duration="until-dismissed",
        tags=(f"holds.place.{pid.rsplit('/', 1)[-1]}",)))
    here = places.laboratory_here(scene, engine.places())
    assert here["kind"] == "owned" and here["keeper"] == alchemist.ref
    assert market.lab_rent(scene, 1, engine.places()) == market.LAB_RENT_CP_PER_HOUR


# --- the field kit --------------------------------------------------------------------------

def _pc():
    return load_pc("fixtures/pc-kesst.json")


def test_a_bought_alchemy_kit_is_carried():
    """Bought gear lands in `stock` under its name (`goods.deliver`)."""
    pc = _pc()
    assert not places.has_alchemy_kit(pc)
    deliver(None, pc, Good(id="gear:alchemist's field kit", name="alchemist's field kit",
                           price_gp=25.0))
    assert places.has_alchemy_kit(pc)


def test_the_alchemist_classes_own_kit_and_the_books_portable_lab_are_kits():
    """content/world-classes/alchemist.json names "travelling alchemy kit" as the level-1
    tool, and the Core Rulebook's 40 lb alchemist's lab in a pack does at least what the
    kit does. The fiction's handovers are in `goods`, and a row at zero is not a kit."""
    for name in ("Travelling Alchemy Kit", "alchemist’s lab", "alchemy crafting kit"):
        pc = _pc()
        pc.goods[name] = 1
        assert places.has_alchemy_kit(pc), name
        pc.goods[name] = 0
        assert not places.has_alchemy_kit(pc), name


@pytest.mark.parametrize("name", ["smith's field kit", "healer's kit", "field kit", "kit",
                                  "herbalism kit", "glass vial"])
def test_another_kit_is_not_the_alchemists(name):
    """A bare "kit" opening the bench would be a word deciding it; the smith's kit is the
    forge's, and the two benches never answer for each other."""
    pc = _pc()
    pc.goods[name] = 1
    assert not places.has_alchemy_kit(pc)
    if name == "smith's field kit":
        assert places.has_field_kit(pc)


# --- the rent -------------------------------------------------------------------------------

def test_an_hour_in_the_town_laboratory_is_two_silver():
    """The plan's rate (2 sp an hour: the forge's 1 sp doubled for the glassware), in
    copper because the purse spends copper."""
    scene, engine, _lab = _at_the_city_lab()
    assert market.lab_rent(scene, 1, engine.places()) == 20
    assert market.lab_rent(scene, 8, engine.places()) == 160


def test_ten_minutes_in_the_laboratory_is_charged_as_coins_begun():
    """Ten minutes is 3.33 coppers of time; the alchemist does not split a coin, and
    floating point never charges one for nothing (20 × 0.05 is exactly one copper)."""
    scene, engine, _lab = _at_the_city_lab()
    assert market.lab_rent(scene, 10 / 60, engine.places()) == 4
    assert market.lab_rent(scene, 0.05, engine.places()) == 1


@pytest.mark.parametrize("hours", [0, -2, float("nan"), float("inf"), None, "an hour"])
def test_no_time_or_nonsense_time_costs_nothing_in_the_laboratory(hours):
    scene, engine, _lab = _at_the_city_lab()
    assert market.lab_rent(scene, hours, engine.places()) == 0


def test_the_forge_and_the_laboratory_never_charge_each_others_rent():
    """Rent is read off where the party stands: no laboratory rent in the smithy, no forge
    rent in the laboratory, nothing in the market."""
    scene, engine, _lab = _at_the_city_lab()
    assert market.forge_rent(scene, 3, engine.places()) == 0
    smithy = next(p for p in places.home_set(_caddonbury()) if p.name == "the smithy")
    engine.place_party(smithy.id)
    assert market.lab_rent(scene, 3, engine.places()) == 0
    assert market.forge_rent(scene, 1, engine.places()) == market.FORGE_RENT_CP_PER_HOUR
    town, _e = _table(PANGRELLA, VYRAKON)
    assert market.lab_rent(town, 3) == 0


def test_the_rent_is_paid_for_the_minutes_the_clock_door_moves():
    """The bench charges `lab_rent` for the step's minutes and moves the clock through the
    one door (`Scene.advance`), as the forge's roll does with `forge_rent`: three hours
    at the hood is 60 cp off the purse and three hours on the clock."""
    from rules import goods

    scene, engine, _lab = _at_the_city_lab()
    pc = scene.pc()
    pc.purse = goods.coins_for(500)
    clock = scene.clock_minutes
    minutes = 180
    rent = market.lab_rent(scene, minutes / 60, engine.places())
    purse, ok = goods.spend(pc.purse, rent)
    assert ok and rent == 60
    pc.purse = purse
    scene.advance(minutes)
    assert scene.clock_minutes == clock + minutes
    assert goods.in_copper(pc.purse) == 440


# --- saying where to go ---------------------------------------------------------------------

def test_a_city_names_its_laboratory():
    """The bench's one line about where the alchemist can work: a city's laboratory by
    name, before the party has walked there."""
    city = _caddonbury()
    scene, engine = _table(SYNTHETIC, city.id)
    line = places.laboratory_line(scene, engine.places(), city)
    assert "the laboratory" in line and "Caddonbury" in line, line


def test_a_town_without_one_says_so():
    """A town with no laboratory says it has none, by name, and what still works — the
    field kit, and one of your own. Never silence, which reads as "the bench is broken"."""
    town = PANGRELLA.get(VYRAKON)
    scene, engine = _table(PANGRELLA, VYRAKON)
    line = places.laboratory_line(scene, engine.places(), town)
    assert line.startswith(f"{town.name} has no laboratory to rent"), line
    assert "field kit" in line


def test_standing_in_one_needs_no_line():
    scene, engine, _lab = _at_the_city_lab()
    assert places.laboratory_line(scene, engine.places(), _caddonbury()) == ""


# --- what a settlement's shops may hold: the book's base values (owner, 2026-10-07) ---------

def _dearest(kind: str, scale: str, days: int = 30) -> float:
    from rules import pricing

    worst = 0.0
    for day in range(days):
        shelf = market.on_sale("aaaabbbbcccc", kind, day, {}, counter_kind=kind, scale=scale)
        worst = max([worst, *(pricing.worth(g) for g in shelf)])
    return worst


def test_the_base_values_are_the_books():
    """GameMastery Guide p.204 (aonprd Rules ID 844): thorp 50, hamlet 200, village 500,
    small town 1,000, large town 2,000, small city 4,000, large city 8,000, metropolis
    16,000 gp. The app's three scales are the owner's three numbers (village 500, town
    2,000, city 8,000); a world's finer word keeps the book's own value."""
    assert [market.base_value(s) for s in ("village", "town", "city")] == [500, 2000, 8000]
    assert market.base_value("hamlet") == 200 and market.base_value("metropolis") == 16000
    assert market.base_value("outpost") == 500, "an outpost folds to a village"
    assert market.base_value("") is None, "no settlement known: nothing capped"


def test_a_village_shelf_never_holds_what_a_village_could_not_have():
    """Lane H measured it: `on_sale` was never told the settlement, so a counter's shelf
    was bounded by its till alone. The armorer's 1,500 gp full plate is a staple, and on
    30 days of a village shelf it is never there; a town's and a city's carry it daily."""
    assert _dearest("market:armorer", "village") <= 500
    assert _dearest("market:armorer", "town") >= 1500
    assert _dearest("market:armorer", "city") >= 1500


def test_a_city_shelf_reaches_past_the_till_and_a_village_one_never_does():
    """The base value is the shelf's ceiling where the settlement is known, the till only
    what the counter pays (the book's purchase limit is a separate number). Measured
    2026-10-07: the alchemist's uncommon till (150-400 gp) held its shelf to 350 gp on
    30 days in a city as in a village; with the ruling, 500, 2,000 and 8,000 gp."""
    till_bound = _dearest("market:alchemist", "")
    assert till_bound <= 400
    assert _dearest("market:alchemist", "village") <= 500
    assert till_bound < _dearest("market:alchemist", "town") <= 2000
    assert 2000 < _dearest("market:alchemist", "city") <= 8000


def test_the_scale_comes_from_the_settlement():
    """Every caller with a world passes `scale_here`; a world's own word wins when the book
    has it, else the app's three."""
    city = _caddonbury()
    assert market.scale_here(SYNTHETIC, city.id) == "city"
    assert market.scale_here(PANGRELLA, VYRAKON) == "town"
    assert market.scale_here(None, VYRAKON) == ""


def test_a_village_alchemist_never_offers_a_750_gp_potion_and_a_city_one_does():
    """The owner's own test (2026-10-07). While the till bounded the shelf, no potion dearer
    than the alchemist's uncommon till (at most 400 gp) was on any counter in any city;
    with the base value as the shelf's ceiling a city's alchemist shelves the 750 gp
    potions on the days the draw brings them, and a village's never does."""
    if not hasattr(market, "POTION_DRAW"):
        pytest.skip("lane H's spell potions (market.POTION_DRAW) are not on this branch")
    from rules import pricing

    def potions(scale: str) -> list[float]:
        seen = []
        for day in range(60):
            shelf = market.on_sale("aaaabbbbcccc", "market:alchemist", day, {},
                                   counter_kind="market:alchemist", scale=scale)
            seen += [pricing.worth(g) for g in shelf if "potion" in str(g.name).lower()]
        return seen

    assert not [p for p in potions("village") if p >= 750]
    assert [p for p in potions("city") if p >= 750]
