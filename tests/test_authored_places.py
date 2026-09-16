"""The town is the world's town now, not one this app invented for it.

`rules/places.py` has promised since the day it was written:

    "When World Bible ships towns and the places in them, an authored list replaces a
    generated one at `home_set` and nothing else changes."

World Bible shipped them at schema 1.3 — 72 places across Pangrella's twelve settlements,
384 across Aurvantis's sixty-four — and for one commit this app ignored every one of them,
which is the same shape as every other defect this project keeps finding: a feature
described and not delivered. This is the delivery, and these tests are the two halves of
that sentence: **an authored list replaces a generated one**, and **nothing else changes**.

Where the authored list is read from is worth recording. `home_set` is handed a LOCATION
and never a world — a Scene holds no world by design, which is the same reason the ground
lives inside a place id rather than beside it — so the loader files each place under the
settlement it names as its parent, and `home_set` asks the location it already has.
"""
from __future__ import annotations

from rules import places
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
PANGRELLA = "5bbd0c40345f"


def _ent(**over):
    """A settlement carrying whatever places a test wants."""
    class Loc:
        id = over.get("id", "aaaabbbbcccc")
        name = over.get("name", "Testville")
        kind = "CITY"
        facts = over.get("facts", {})
        prose = over.get("prose", "")
        scale = "town"
        places = over.get("places", [])
    return Loc()


def _place(**over) -> dict:
    base = {"id": "aaaabbbbcccc~urban:the-market", "name": "the market",
            "about": "Stalls.", "parent": "aaaabbbbcccc", "terrain": "urban",
            "exits": ["aaaabbbbcccc~urban:the-gate"], "described_only": False,
            "origin": "world"}
    base.update(over)
    return base


# --- an authored list replaces a generated one ------------------------------------------

def test_the_world_s_own_rooms_are_the_ones_the_party_stands_in():
    """The headline. Pangrella's rooms come from its export, not from the table of generic
    settlement spots — and two of them (`the guildhall`, `the mine head`) are places the
    generator would only have reached by cue words.

    Six at schema 1.3 and nine at 1.5, because the supplier now sizes a settlement by its
    own scale against this app's published table: a town holds nine."""
    got = places.home_set(WORLD.get(PANGRELLA))
    names = [p.name for p in got]
    assert len(got) == 9, names
    assert "the mine head" in names and "the guildhall" in names, names
    assert all(p.origin == "world" for p in got)
    assert all(p.id.startswith(f"{PANGRELLA}~urban:") for p in got), names


def test_the_ground_still_comes_out_of_the_id():
    """Authored or generated, the one spatial authority is unchanged: `terrain` is parsed
    off the id and never read from the field beside it."""
    got = places.home_set(WORLD.get(PANGRELLA))
    assert {p.terrain for p in got} == {"urban"}


def test_a_world_that_ships_no_places_still_gets_a_generated_town():
    """Backward compatibility, and it is not theoretical: every export at 1.2 or below
    has no `play.places[]` at all, and so does every world whose author wrote none."""
    got = places.home_set(_ent(places=[]))
    assert len(got) >= 3
    assert all(p.origin == "" for p in got), "a generated place claims a provenance"
    assert all("~urban:" in p.id for p in got)


def test_the_implied_table_is_not_consulted_when_the_world_has_spoken():
    """Door one is replaced, not supplemented. A port town that authored six rooms and no
    docks has said what it has; minting a seventh because its prose says "port" would be
    the generator arguing with the author."""
    port = _ent(facts={"Trade": "A port town, and the quay is its living."},
                places=[_place(), _place(id="aaaabbbbcccc~urban:the-gate",
                                         name="the gate", exits=[])])
    got = places.home_set(port)
    assert [p.name for p in got] == ["the market", "the gate"]
    # And the cue table would genuinely have fired, so this is testing the branch and not
    # a town whose words imply nothing.
    assert "the docks" in [s for s, _a in places.implied_spots(port)]


# --- nothing else changes ------------------------------------------------------------------

def test_a_place_the_player_founds_still_joins_an_authored_town():
    """Door two. The player declares a base and the engine mints it against wherever they
    stand — that is unchanged, and it has to keep working beside an authored list or a
    world that ships places takes the player's own away."""
    home = places.home_set(WORLD.get(PANGRELLA))
    minted = places.mint(home[0], "Marra's house", "A shutter that does not close.",
                         owner="Marra", origin="found")
    assert minted.origin == "found" and minted.owner == "Marra"
    assert minted.parent == home[0].id
    assert places.terrain_of(minted.id) == "urban", minted.id


def test_ground_gone_into_is_unchanged():
    """Door three. The sewers are still generated from a seed, because no world authors
    the inside of its own sewers."""
    assert "sewers" in places.VENTURES
    from_here = places.home_set(WORLD.get(PANGRELLA))[0]
    got = places.venture_set(from_here, "sewers")
    assert got and all(places.terrain_of(p.id) == "underground" for p in got), got
    assert all(p.origin == "venture" for p in got), got


def test_an_authored_building_still_gets_its_floors():
    """Storeys are derived from the place id, so they work the same on an authored place
    as on a generated one — an authored tavern has an upstairs without the export saying
    so, and reaching it still costs the stairs."""
    tavern = f"{PANGRELLA}~urban:the-tavern"
    assert places.is_indoors(tavern, "urban")
    floors = places.storeys(tavern, "urban")
    assert 0 in floors
    for other in floors:
        if other:
            assert places.storey_id(tavern, other) in places.stairs_from(tavern, "urban") \
                or abs(other) > 1


# --- what it refuses to do with a bad list --------------------------------------------------

def test_a_place_whose_id_carries_no_ground_is_dropped_rather_than_stood_on():
    """`terrain_of` parses the id, so a place without its `~terrain` segment describes
    ground that does not exist and would be handed an empty twenty-by-twenty field to
    fight in — the blank battlefield that a fortnight of work removed.

    `tools/check_places.py` reports this before an export ships. This is what happens if
    one gets through anyway: one room is lost, rather than one room being a lie."""
    got = places.home_set(_ent(places=[
        _place(),
        _place(id="aaaabbbbcccc:no-ground-in-this-one", name="the yard"),
    ]))
    assert [p.name for p in got] == ["the market"]


def test_an_entirely_unusable_list_falls_back_to_generating():
    """Fail soft, the way the rest of this module does. A town with no readable places is
    still a town the party can stand in."""
    got = places.home_set(_ent(places=[_place(id="nonsense"), {"not": "a place"}]))
    assert len(got) >= 3
    assert all(p.origin == "" for p in got), "it did not fall back to generating"


def test_the_export_does_not_get_to_claim_the_player_built_something():
    """`origin` is provenance. An export saying `found` would hand the party a place the
    engine believes they made themselves, with the owner rules that implies."""
    got = places.home_set(_ent(places=[_place(origin="found", owner="somebody")]))
    assert got[0].origin == "world" and got[0].owner == ""


def test_a_place_parented_on_nothing_never_reaches_a_town():
    """Filed by the loader under the settlement it names. One that names a settlement the
    export does not contain is dropped there — keeping it would be holding a room in a
    town that does not exist, and `check_places.py` calls that a problem."""
    every = [p for e in WORLD.entities.values() for p in (e.places or [])]
    assert every, "the fixture ships no places; this test is checking nothing"
    for place in every:
        assert place.get("parent") in WORLD.entities, place.get("id")


def test_both_shipped_worlds_are_read_the_same_way():
    """Aurvantis is the second world, added because every place bug so far was invisible
    in a world with one people and twelve towns."""
    aurvantis = loader.load_cached("fixtures/aurvantis-campaign.json")
    towns = [e for e in aurvantis.entities.values() if e.places]
    assert len(towns) >= 60, len(towns)
    for ent in towns[:12]:
        got = places.home_set(ent)
        assert got and all(p.origin == "world" for p in got), ent.name
        assert all(places.terrain_of(p.id) for p in got), ent.name
