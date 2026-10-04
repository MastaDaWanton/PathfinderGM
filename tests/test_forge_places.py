"""Where the smith works: the town smithy, the owned smithy, the field kit, and the rent.

Blacksmithing plan §10 and contracts §8 (lane G). The forge has two benches: the field kit
goes wherever the smith stands and does common and uncommon work; a SMITHY adds the
furnace (Smelt, Alloy, Fold, Strengthen, rare-and-above material) and is either the
town's, paid by the hour, or the player's own, founded through the `found` door and held
as `holds.place.<slug>`.

Measured before any of this, 2026-10-03, which is what these tests hold:

  * a smithy was in 5 of Aurvantis's 64 settlements, 0 of Pangrella's 12 and 1 of the
    synthetic world's 6 — and the generator gave one to **0 of 200** generated villages,
    0 of 200 towns and 0 of 200 cities, because the guarantees and the four essentials
    spend a small settlement's budget first and a city's fill reaches for city things;
  * the obvious word cue, "forge", fired only as a metaphor: "forged" twice and
    "forging" six times across the three exports' settlement words ("alliances forged in
    ancient traditions", "the great forging's aftermath"), and never once for a smithy;
  * nothing anywhere could say whether the party stood at a forge, and the field kit
    was in no goods table.

World-agnostic where the machinery is (the standing instruction of 2026-09-28): the
`worlds` fixture runs the founding test once per export.
"""
from __future__ import annotations

import pytest

from rules import keepers, market, places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.goods import Good, deliver
from rules.sheet import load_pc
from world import loader

PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")
SYNTHETIC = loader.load_cached("fixtures/synthetic-world.json")
VYRAKON = "5bbd0c40345f"            # Pangrella: a town whose author listed no smithy


def _town(scale: str, ident: str = "aaaabbbbcccc", facts=None, prose=""):
    class Loc:
        id = ident
        name = "Testville"
        kind = "CITY"
        places = []
    Loc.scale = scale
    Loc.facts = facts or {}
    Loc.prose = prose
    return Loc()


def _names(loc) -> set[str]:
    return {p.name for p in places.home_set(loc)}


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


def _has_smithy(world, entity) -> bool:
    return any(places.has_place_tag(p, places.SMITHY) for p in places.home_set(entity))


# --- a settlement can have one --------------------------------------------------------------

def test_a_generated_city_always_has_a_smithy():
    """0 of 200 generated cities had one before: the fill takes the biggest thing a city
    is entitled to first, and the smithy is a village-floor row, so a city of fifty
    thousand had an arena and a counting house and nowhere to shoe a horse."""
    for i in range(20):
        assert "the smithy" in _names(_town("city", f"c{i:08x}")), i


def test_a_settlement_whose_words_name_its_smiths_has_a_smithy():
    """The synthetic world's Kestwick says "the smiths and the wool merchants both want
    the market"; the cue table had no smithy row, so 0 of 200 generated towns had one
    whatever their words said."""
    worded = _town("town", facts={"Urban Life": "The smiths and the wool merchants "
                                                "both want the market moved."})
    assert "the smithy" in [spot for spot, _a in places.implied_spots(worded)]
    assert "the smithy" in _names(worded)
    assert "the smithy" not in _names(_town("town"))


@pytest.mark.parametrize("said", [
    "Its rulers perpetuate their interests through alliances forged in ancient traditions.",
    "Established during the great forging's aftermath, by clans seeking balance.",
    "The council forges ahead with its plans for the harbour wall.",
])
def test_a_metaphor_about_forging_earns_no_smithy(said):
    """Measured across the three exports: "forged" fired 2 times and "forging" 6, every
    one of them a metaphor. "forge" is a phrase cue ("a forge", "the forge") and its verb
    forms are not cues, so none of these earns a building."""
    assert "the smithy" not in [s for s, _a in places.implied_spots(_town("town", prose=said))]


def test_the_smithy_cue_never_pushes_out_what_a_town_already_earned():
    """Earned spots are taken in table order up to MOST_IMPLIED (4). The smithy row is
    last, so a port town whose words also name its smiths keeps its docks, its bridge,
    its guildhall and its library — a row at the top would have dropped the library."""
    words = ("A port on the river, run by its guilds, its scribes keeping the archives; "
             "the smiths work by the quay.")
    earned = [s for s, _a in places.implied_spots(_town("town", prose=words))]
    assert earned[:4] == ["the docks", "the bridge", "the guildhall", "the library"], earned
    assert earned[-1] == "the smithy"


def test_a_founded_smithy_in_a_settlement_whose_author_listed_none(worlds):
    """Every shipped export authors its places (schema 1.3) and an authored list is never
    argued with — so Pangrella had a smithy in 0 of 12 settlements and Aurvantis in 5 of
    64. "Places must be creatable" (ruled 2026-10-03): the `found` door makes one, the
    smith is stood up behind it, and the party is at a town smithy."""
    target = None
    for row in worlds.play.get("settlements") or []:
        entity = worlds.get(row["id"])
        if entity is not None and places._settled(entity, "") \
                and not _has_smithy(worlds, entity):
            target = entity
            break
    assert target is not None, "every settlement in this export already has a smithy"
    scene, engine = _table(worlds, target.id)
    made = _run(engine, "found", {"name": "the smithy"})
    assert made.effects and made.effects[0]["is"] == "smithy", made.tell
    went = _run(engine, "travel", {"place": "the smithy"})
    assert scene.at == made.effects[0]["id"], went.tell
    here = places.smithy_here(scene, engine.places())
    assert here is not None and here["kind"] == "town", here
    assert here["place"] == scene.at
    assert here["rate_cp_per_hour"] == market.FORGE_RENT_CP_PER_HOUR
    keeper = keepers.keeper_in(scene, scene.at)
    assert keeper is not None and here["keeper"] == keeper.ref


def test_the_words_people_use_for_a_forge_found_a_smithy():
    """A plan writes `kind="forge"` as readily as "smithy"; before this, "There is no
    such kind of place as 'forge'" refused the player's own smithy outright."""
    for word in ("forge", "the forge", "blacksmith's", "ironworks", "foundry"):
        assert places.kind_named(word) == "smithy", word
        assert places.known_kind(word), word
    # "smith" is the person, and these words are read as naming a PLACE.
    assert places.kind_named("smith") != "smithy"


# --- which smithy the party is at -----------------------------------------------------------

def test_a_generated_city_smithy_is_the_towns_with_a_smith_behind_it():
    """The synthetic world's Caddonbury, a generated city, had no smithy at all. Standing
    in the one it has now, a smith is behind the counter and the forge is rented."""
    city = next(SYNTHETIC.get(r["id"]) for r in SYNTHETIC.play["settlements"]
                if SYNTHETIC.get(r["id"]).name == "Caddonbury")
    smithy = next(p for p in places.home_set(city) if p.name == "the smithy")
    scene, engine = _table(SYNTHETIC, city.id)
    engine.place_party(smithy.id)
    here = places.smithy_here(scene)
    assert here == {"kind": "town", "place": smithy.id,
                    "keeper": keepers.keeper_in(scene, smithy.id).ref,
                    "rate_cp_per_hour": 10}


def test_a_place_that_is_not_a_forge_is_not_a_smithy():
    """The market, a tavern and the workshops are kept by a master, a barkeep and an
    artisan; only a keeper whose occupation carries the `forge` tag makes a smithy."""
    assert places.kind_works_forge("smithy")
    for kind in ("market", "tavern", "workshops", "tannery", "well"):
        assert not places.kind_works_forge(kind), kind
    scene, _engine = _table(PANGRELLA, VYRAKON)
    assert places.smithy_here(scene) is None, scene.at


def test_the_players_words_never_make_a_smithy():
    """Contracts §8: "never read from the player's words". A place founded as "my forge"
    with no kind is a name the player chose; reading the name would open the furnace in
    any room the player cared to call a forge."""
    scene, engine = _table(PANGRELLA, VYRAKON)
    made = _run(engine, "found", {"name": "my forge", "owner": "pc"})
    _run(engine, "travel", {"place": "my forge"})
    assert scene.at == made.effects[0]["id"]
    assert places.smithy_here(scene, engine.places()) is None


def test_an_owned_smithy_is_read_off_the_holders_effect():
    """The owner field on a founded place is the claim; the holder's `holds.place.<slug>`
    effect is the fact. Take the effect away — the forge sold or seized — and the same
    building stops being theirs with nothing else to update (law 2: remove the effect
    and its contribution evaporates)."""
    scene, engine = _table(PANGRELLA, VYRAKON)
    made = _run(engine, "found", {"name": "my own forge", "kind": "forge", "owner": "pc"})
    _run(engine, "travel", {"place": "my own forge"})
    pid = made.effects[0]["id"]
    assert scene.at == pid
    here = places.smithy_here(scene, engine.places())
    assert here["kind"] == "owned" and here["place"] == pid
    assert here["rate_cp_per_hour"] == 0
    assert market.forge_rent(scene, 8) == 0, "the party pays itself rent"
    pc = scene.pc()
    pc.remove_effects(source=f"place:{pid}")
    assert not pc.has_state("holds.place")
    after = places.smithy_here(scene, engine.places())
    assert after is None or after["kind"] == "town", after


def test_a_friends_smithy_is_theirs_and_rented_from_them():
    """A founded smithy held by somebody else is an owned smithy — theirs. The party
    pays the town's rate, to the holder, and does not get it free for standing in it."""
    from rules.activeeffect import ActiveEffect

    scene, engine = _table(PANGRELLA, VYRAKON)
    made = _run(engine, "found", {"name": "the smithy"})
    _run(engine, "travel", {"place": "the smithy"})
    smith = keepers.keeper_in(scene, scene.at)
    pid = made.effects[0]["id"]
    # Held by the smith: as the `found` door grants it, through the one applicator.
    for raw in scene.founded:
        if raw["id"] == pid:
            raw["owner"] = smith.ref
    smith.apply_effect(ActiveEffect(
        name="holds the smithy", kind="situation", key=f"holds:{pid}",
        source=f"place:{pid}", origin="found", duration="until-dismissed",
        tags=(f"holds.place.{pid.rsplit('/', 1)[-1]}",)))
    here = places.smithy_here(scene, engine.places())
    assert here["kind"] == "owned" and here["keeper"] == smith.ref
    assert here["rate_cp_per_hour"] == market.FORGE_RENT_CP_PER_HOUR


def test_the_floor_above_the_smithy_is_not_the_forge():
    """A smithy has an upstairs (its floor plan rises two). The anvil is where you walk
    in; the smith's bedroom does not open the furnace."""
    city = next(SYNTHETIC.get(r["id"]) for r in SYNTHETIC.play["settlements"]
                if SYNTHETIC.get(r["id"]).name == "Caddonbury")
    smithy = next(p for p in places.home_set(city) if p.name == "the smithy")
    scene = Scene(location_id=city.id)
    scene.at = places.storey_id(smithy.id, 1)
    assert places.smithy_here(scene) is None


# --- the field kit --------------------------------------------------------------------------

def _pc():
    return load_pc("fixtures/pc-kesst.json")


def test_a_bought_field_kit_is_carried():
    """Bought gear lands in `stock` under its name (`goods.deliver`); the kit is found
    there exactly as `gear.carried` finds a bedroll."""
    pc = _pc()
    assert not places.has_field_kit(pc)
    deliver(None, pc, Good(id="gear:smith's field kit", name="smith's field kit",
                           price_gp=15.0))
    assert places.has_field_kit(pc)


def test_a_field_kit_handed_over_in_the_fiction_is_carried_until_it_is_gone():
    """The fiction's handovers are in `goods`, and a row can sit at zero there; an empty
    entry is not a kit."""
    pc = _pc()
    pc.goods["Smith’s Field Kit"] = 1
    assert places.has_field_kit(pc)
    pc.goods["Smith’s Field Kit"] = 0
    assert not places.has_field_kit(pc)


@pytest.mark.parametrize("name", ["healer's kit", "field kit", "kit", "climber's kit",
                                  "hammer"])
def test_another_kit_is_not_the_smiths(name):
    """A healer carries a kit into the field too. A bare "kit" opening the forge would be
    a word deciding the bench."""
    pc = _pc()
    pc.goods[name] = 1
    assert not places.has_field_kit(pc)


# --- the rent -------------------------------------------------------------------------------

def _at_a_town_smithy():
    city = next(SYNTHETIC.get(r["id"]) for r in SYNTHETIC.play["settlements"]
                if SYNTHETIC.get(r["id"]).name == "Caddonbury")
    smithy = next(p for p in places.home_set(city) if p.name == "the smithy")
    scene, engine = _table(SYNTHETIC, city.id)
    engine.place_party(smithy.id)
    return scene


def test_an_hour_at_the_town_forge_is_a_silver():
    """The plan's rate (1 sp an hour), in copper because the purse spends copper."""
    scene = _at_a_town_smithy()
    assert market.forge_rent(scene, 1) == 10
    assert market.forge_rent(scene, 8) == 80


def test_a_tenth_of_an_hour_is_one_copper_and_not_two():
    """10 × 0.1 is 1.0000000000000002 in floating point, and a bare ceiling charged two
    coppers for one copper's worth of time."""
    scene = _at_a_town_smithy()
    assert market.forge_rent(scene, 0.1) == 1
    assert market.forge_rent(scene, 0.3) == 3


def test_ten_minutes_is_charged_as_a_coin_begun():
    """Ten minutes is 1.67 coppers of time; the smith does not split a coin."""
    scene = _at_a_town_smithy()
    assert market.forge_rent(scene, 10 / 60) == 2


@pytest.mark.parametrize("hours", [0, -2, float("nan"), float("inf"), None, "an hour"])
def test_no_time_or_nonsense_time_costs_nothing(hours):
    scene = _at_a_town_smithy()
    assert market.forge_rent(scene, hours) == 0


def test_no_rent_where_there_is_no_smithy():
    """Rent is read off where the party is standing, never passed a rate: in the market
    there is no forge to rent."""
    scene, _engine = _table(PANGRELLA, VYRAKON)
    assert market.forge_rent(scene, 3) == 0
