"""The settlement vocabulary, and the ledger of what still has no rule behind it.

Rebuilt 2026-09-15:

> "there is no town or city that has 2 places. 2 places is a rest stop... cities and towns
> have businesses and entertainment and leisure/recreation and religious establishments/
> cultural buildings...the list goes on and on"

The table before that was six rows handed to a hamlet and a capital alike, and it never
read the `scale` the export has carried on every settlement since 1.0 — Aurvantis ships
16 villages, 32 towns and 16 cities, and all 64 got the same six places.

`docs/settlement-places.md` is the ledger: every kind of place, what reads it, and the
ones nothing does. These hold that file to the table, because a ledger that has gone stale
is worse than none — it is a promise somebody stopped keeping and nobody noticed.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings

from rules import floorplan, places

LEDGER = Path(settings.BASE_DIR, "docs", "settlement-places.md")


def _doc() -> str:
    return LEDGER.read_text(encoding="utf-8")


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


JUNCTIONS = {"the great square", *places._QUARTERS}


# --- the shape of a settlement ------------------------------------------------------------

def test_a_settlement_is_the_size_its_own_scale_says():
    """The defect, as an assertion. One number for every settlement is what made a capital
    a hamlet with a different name."""
    rooms = {}
    for scale in places.SCALES:
        got = places.home_set(_town(scale))
        rooms[scale] = len([p for p in got if p.name not in JUNCTIONS])
    assert rooms == places.PLACES_BY_SCALE, rooms
    assert rooms["village"] < rooms["town"] < rooms["city"]


def test_a_city_is_quartered_and_a_town_is_not():
    """Eighteen rooms flat is seventeen exits in one prompt. A village and a town are
    small enough to stay flat, which is what a settlement you can walk across means."""
    city = places.home_set(_town("city"))
    assert any(p.within for p in city), "a city has no quarters"
    assert max(len(p.exits) for p in city) <= 6, "a city prompt is wider than six"
    for small in ("village", "town"):
        assert not any(p.within for p in places.home_set(_town(small))), small


def test_every_room_in_a_city_is_reachable_from_the_square():
    """Quarters are a shape, not a maze: two or three hops from anywhere to anywhere, and
    nothing stranded behind a crossing that leads nowhere."""
    city = places.home_set(_town("city"))
    by_id = {p.id: p for p in city}
    start = next(p for p in city if not p.within)
    seen, queue = {start.id}, [start.id]
    while queue:
        for nxt in by_id[queue.pop()].exits:
            if nxt in by_id and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    assert seen == set(by_id), sorted(set(by_id) - seen)


def test_a_within_always_names_a_room_in_the_same_settlement():
    """`within` is room-to-room where `parent` is the world entity. A `within` naming
    something that is not a place here would put a room in a quarter that does not
    exist."""
    city = places.home_set(_town("city"))
    ids = {p.id for p in city}
    for p in city:
        if p.within:
            assert p.within in ids, f"{p.id} hangs off {p.within}, which is not here"
            assert places.location_of(p.within) == places.location_of(p.id)


def test_nothing_hangs_off_itself_or_goes_round_in_a_circle():
    city = places.home_set(_town("city"))
    within = {p.id: p.within for p in city}
    for start in within:
        seen, at = set(), start
        while at:
            assert at not in seen, f"{start} is in a within-cycle"
            seen.add(at)
            at = within.get(at, "")


# --- what every settlement has --------------------------------------------------------------

def test_a_town_and_a_city_always_have_somewhere_the_watch_is():
    """"every town/city should have a guardhouse/barracks where a large number of guards
    are stationed at any time". A settlement with nobody keeping order is one the wanted
    state has nowhere to come from, and the player has nowhere to be arrested to."""
    for scale in ("town", "city"):
        names = {p.name for p in places.home_set(_town(scale))}
        assert "the guardhouse" in names, f"a {scale} with no watch: {sorted(names)}"
    # A village does not, on purpose: four hundred people have a reeve and a horn.
    assert "the guardhouse" not in {p.name for p in places.home_set(_town("village"))}


def test_what_a_scale_always_has_is_there_whatever_the_seed():
    """Ten settlements of each size, because "the seed did not pick one" is not a reason
    a player can act on."""
    for scale, always in places.ALWAYS_BY_SCALE.items():
        for i in range(10):
            names = {p.name for p in places.home_set(_town(scale, f"seed{i:08x}"))}
            for label in always:
                assert label in names, f"{scale} {i}: no {label}"


def test_every_settlement_has_the_four_a_player_reaches_for():
    """Somewhere to buy, to sleep, to be quiet, and where nobody is watching — whatever
    the scale and whatever the seed."""
    cats = {label: cat for label, _a, _s, cat, _e in places.SETTLEMENT_PLACES}
    for scale in places.SCALES:
        for i in range(6):
            got = {cats[p.name] for p in places.home_set(_town(scale, f"s{i:08x}"))
                   if p.name in cats}
            for essential in places.ESSENTIAL_CATEGORIES:
                assert essential in got, f"{scale} {i} has no {essential}"


def test_two_settlements_of_a_size_are_not_the_same_settlement():
    """The first version had no seed anywhere: all sixteen of Aurvantis's cities came out
    with the same eighteen rooms in the same order."""
    seen = [frozenset(p.name for p in places.home_set(_town("city", f"c{i:08x}")))
            for i in range(6)]
    assert len(set(seen)) > 1, "every city in the world is the same city"


def test_a_city_is_not_a_village_repeated():
    """It reaches for what only a city has. A city that fills its leisure slot with the
    inn and its hidden slot with the lane is a village eighteen times over, which is what
    the first version produced."""
    only_city = {label for label, _a, floor, _c, _e in places.SETTLEMENT_PLACES
                 if floor == "city"}
    names = {p.name for p in places.home_set(_town("city"))}
    assert len(names & only_city) >= 4, sorted(names)


def test_a_village_is_never_given_what_only_a_city_has():
    """The floor is a floor. A hamlet with an arena in it is the same failure pointed the
    other way."""
    too_big = {label for label, _a, floor, _c, _e in places.SETTLEMENT_PLACES
               if floor == "city"}
    for i in range(8):
        names = {p.name for p in places.home_set(_town("village", f"v{i:08x}"))}
        assert not (names & too_big), sorted(names & too_big)


# --- the ledger -----------------------------------------------------------------------------

def test_every_place_is_in_the_ledger():
    doc = _doc()
    for label, *_rest in places.SETTLEMENT_PLACES:
        assert f"| {label} |" in doc, f"{label!r} is not in {LEDGER.name}"


def test_the_ledger_counts_what_has_no_rule_and_gets_it_right():
    unread = sum(1 for r in places.SETTLEMENT_PLACES if not r[4])
    assert f"{unread} of {len(places.SETTLEMENT_PLACES)} have no rule" in _doc(), (
        f"the ledger does not say {unread} of {len(places.SETTLEMENT_PLACES)}")


def test_the_places_that_want_somebody_in_them_have_somebody_in_them():
    """"any place that offers services or merchandise needs an NPC to man it" — the table
    says who ought to be standing in each, and since 2026-09-16 `rules/keepers.py` stands
    them up. The ledger carried the gap as a written promise while it was open; now it
    has to carry the delivery, or it is a promise somebody stopped keeping."""
    buildable = {label for label, *_r in places.SETTLEMENT_PLACES}
    staffed = [l for l in places.STAFFED if l in buildable]
    assert len(staffed) >= 20
    doc = _doc()
    assert "Nothing generates them" not in doc, "the ledger still says nobody builds them"
    assert "rules/keepers.py" in doc
    assert f"{len(staffed)} of these places sell something" in doc
    # And every one of them names a person and the words that find them.
    for label in staffed:
        title, words = places.keeper_of(label)
        assert title and words, label


def test_the_population_bands_are_words_and_never_a_figure():
    """The third law: no model is handed a number to do arithmetic on. "fifty thousand"
    in a brief is a figure the narrator will start counting with."""
    for scale in places.SCALES:
        said = places.population(scale)
        assert not any(ch.isdigit() for ch in said), said
    assert places.POPULATION_BY_SCALE["city"][0] >= 50_000, "a city is 50,000 up"


def test_every_place_has_a_room_to_happen_in():
    """A place with no tuned shape falls through to plain `urban`: a workable room, and
    the same room every time. A bathhouse that fights like a gaol is half a place."""
    for label, *_rest in places.SETTLEMENT_PLACES:
        slug = label.strip().lower().replace(" ", "-")
        assert slug in floorplan.BY_SPOT, f"{label!r} has nowhere to happen"
    for quarter in (*places._QUARTERS, "the great square"):
        slug = quarter.strip().lower().replace(" ", "-")
        assert slug in floorplan.BY_SPOT, f"{quarter!r} has nowhere to happen"
