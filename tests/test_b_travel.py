"""Travel between the gate and the road (Lane B): leaving, minutes, absent ground, the
warrant at the way out, a road stopped on, walking back, and a horse.

Every test names the measurement it guards. Most are Bobby's session of 2026-09-28
(docs/playtest-2026-09-28.md, items 16, 17, 20), replayed against the engine where the
corpus is on this disk (it is kept out of the repository — `tests/replays/`).
"""
from __future__ import annotations

import pytest

import replays
from gm import interpret
from rules import biomes, geography, journey, ontheway, outskirts, places, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

AURVANTIS = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = "bde94b038cba"


class _Quiet:
    """Dice that never meet anything on the way: every d100 check misses."""

    def __init__(self, real):
        self.real = real

    def __getattr__(self, name):
        return getattr(self.real, name)

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation == "1d100":
            return self.real.given(100, modifiers, label, notation)
        return self.real.roll(notation, modifiers, label, visibility)


def _party(world=AURVANTIS, town=VORMOOR, at="", quiet=True, seed=3):
    s = Scene(location_id=town)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 60
    s.add(pc)
    e = Engine(s, Dice(seed=seed), world=world)
    e.place_party(at)
    if quiet:
        e.dice = _Quiet(e.dice)
    return s, e, pc


def _run(e, pc, op, **params):
    e._journeyed = ""
    return e.run(e.validate([{"op": op, "actor": pc.ref, "because": "t",
                              "params": params}], origin="author:test")).outcomes


def _vormoor_place(name):
    return next(p for p in places.home_set(AURVANTIS.get(VORMOOR)) if p.name == name).id


def _settled(world):
    for row in world.play.get("settlements") or []:
        e = world.get(row["id"])
        if e is not None and places._settled(e, ""):
            yield e


# --- leaving is a move -----------------------------------------------------------------

def test_leave_is_a_travel_and_the_plan_may_only_choose_outside():
    """Bobby's turn 5 (16.1): the reading was `leave: outside it`, `ops_for` mapped
    `leave` to nothing, and the plan walked to the nearest listed place — the way in,
    INSIDE the village. Now `leave` owes a travel and the `travel.place` enum holds the
    ring's names only, which the sampler enforces (6 of 6, `ollama-schema-enforcement`)."""
    s, e, pc = _party(at=_vormoor_place("the market"))
    frame = {"actions": [{"act": "leave", "place": "outside it"},
                         {"act": "look", "object": "a bearing of where I am"}]}
    known = e.places()
    assert "travel" in interpret.ops_for(frame, s, known)
    choices = interpret.travel_choices(frame, s, known, AURVANTIS.get(VORMOOR))
    assert "the outskirts" in choices
    assert "the way in" not in choices and "the market" not in choices
    assert all(places.is_ring(p.id) for p in known if p.name in choices)


def test_the_crossroads_and_the_path_away_are_travels_now():
    """Turns 6 and 7 (17.3): "I walk to the nearest crossroads" read as `go: the nearest
    crossroads`, a phrase no place here was called; the plan tried `found kind=crossroads`
    and was refused. A go to a phrase that names the ground outside owes a travel, held to
    the ring — where Vormoor, with three roads out, has a real crossroads."""
    s, e, pc = _party(at=_vormoor_place("the way in"))
    frame = {"actions": [{"act": "go", "place": "the nearest crossroads"}]}
    known = e.places()
    assert "travel" in interpret.ops_for(frame, s, known)
    choices = interpret.travel_choices(frame, s, known, AURVANTIS.get(VORMOOR))
    assert "the crossroads" in choices
    out = _run(e, pc, "travel", place="the crossroads")[0]
    assert out.status != "refused", out.tell
    assert places.setting_of(s.at) == "outside"


def test_leaving_a_building_offers_its_street():
    """The other half of `leave`: out of a room onto the street it opens on, not out of
    the settlement."""
    s, e, pc = _party(at=_vormoor_place("the guildhall"))
    frame = {"actions": [{"act": "leave", "place": "the guildhall"}]}
    known = e.places()
    choices = interpret.travel_choices(frame, s, known, AURVANTIS.get(VORMOOR))
    assert choices and not any(places.is_ring(p.id) for p in known if p.name in choices)
    here = e.here()
    assert set(choices) <= {p.name for p in known if p.id in here.exits}


def test_walking_out_says_out_and_names_the_land(worlds):
    """16.4: the prose had Bobby leaving by "the gates of Vormoor open to receive you",
    because the tell named a place and never a direction. A step from inside to outside
    is told as leaving, and the land the world describes is said in its own words."""
    e0 = next(e for e in _settled(worlds)
              if geography.land_around(worlds, e).near)
    s, e, pc = _party(world=worlds, town=e0.id)
    before = s.clock_minutes
    out = _run(e, pc, "travel", place="the outskirts")[0]
    eff = out.effects[0]
    assert eff["setting"] == "outside" and eff["was_setting"] == "in"
    assert eff["direction"] == "out"
    assert f"You leave {e0.name} behind." in out.tell
    assert "Past the last house the land opens:" in out.tell
    assert 0 < s.clock_minutes - before == eff["minutes"]
    assert geography.where(worlds, s, e.here()) == geography.Where(
        "outside", f"near {e0.name}", places.terrain_of(s.at))


# --- a walk costs minutes, and says where it went ------------------------------------------

def test_crossing_the_village_costs_minutes_and_walks_its_places():
    """16.5 and 16.2: "still 08:00 after two crossings of town", and the tell for the walk
    was "The way there ran through the well" — half a line of prose. Vormoor's market to
    its way in is two hops at the village band (Q10): four minutes, and each place passed
    carries its own line."""
    s, e, pc = _party(at=_vormoor_place("the market"))
    out = _run(e, pc, "travel", place="the way in")[0]
    eff = out.effects[0]
    assert eff["minutes"] == 4 and s.clock_minutes == 4
    assert eff["went_by"] == ["the well"]
    assert eff["went_by_about"] and eff["went_by_about"][0]["name"] == "the well"
    assert "the well (" in out.tell and "It takes a few minutes' walk." in out.tell


def test_a_stop_names_who_and_why():
    """Bobby's turn 5: the patrol's "You get no further" came back as "the watchmen are
    making their rounds" — scenery. The tell now names the people brought in and why
    they stopped you."""
    m = ontheway.Meeting(kind="patrol", roll=80, count=2)
    said = ontheway.describe(m, "the way in", who=["Guard", "second Guard"])
    assert "You get no further." in said
    assert "Stopped by Guard and second Guard: they are looking at faces" in said


# --- ground the world has, and ground it does not ------------------------------------------

def _absent(world, e):
    land = geography.land_around(world, e)
    if land.source == "unknown":
        return None
    for b in ("forest", "jungle", "tundra", "swamp", "desert", "hills"):
        if geography.grounded(land, b)[0] == "absent":
            return b
    return None


def test_a_move_onto_ground_that_is_not_there_is_refused_and_shown(worlds):
    """20.2: Bobby walked "west into the gnarled dense trees" around Vormoor, a forest the
    previous beat invented, and the engine accepted `biome: forest` unchecked. The
    refusal is player-fixable (`absent_ground`), names the ground that IS there in the
    world's words, carries a `go` fix, and nothing moves and no time passes."""
    e0, biome = next((e, _absent(worlds, e)) for e in _settled(worlds) if _absent(worlds, e))
    s, e, pc = _party(world=worlds, town=e0.id)
    at, clock = s.at, s.clock_minutes
    out = _run(e, pc, "travel", biome=biome)[0]
    assert out.status == "refused" and out.code == "absent_ground"
    assert out.for_a_person and e0.name in out.for_a_person
    land = geography.land_around(worlds, e0)
    assert all(g in out.tell for g in land.near)
    assert out.fix and out.fix["kind"] == "go" and out.fix["place"]
    assert out.effects == [{"kind": "refused-ground", "biome": biome,
                            "near": list(land.near), "beyond": list(land.beyond)}]
    assert s.at == at and s.clock_minutes == clock
    from rules.intents import PLAYER_FIXABLE

    assert "absent_ground" in PLAYER_FIXABLE


def test_vormoor_has_no_forest_and_says_what_it_has():
    """The measured case, word for word the ground the world gives: farmland close by,
    mountain further out, and the continent's ash-fields."""
    s, e, pc = _party()
    out = _run(e, pc, "travel", biome="forest")[0]
    assert out.tell.startswith("There is no woodland near Vormoor.")
    assert "farmland" in out.tell and "mountain" in out.tell and "ash-fields" in out.tell
    assert out.fix == {"kind": "go", "place": "the fields"}


def test_ground_beyond_is_hours_at_the_journey_s_pace():
    """Q13: "Ground beyond the near land follows the same pace rule rather than a flat
    4-hour band." Vormoor's roads cross farmland then mountain, so the mountain is half
    of a 72-mile road out — 36 miles on the road column at 0.75: sixteen hours, marched
    in days with a camp between."""
    assert outskirts.beyond_miles(AURVANTIS, AURVANTIS.get(VORMOOR), "mountain") == 36
    assert outskirts.beyond_hours(AURVANTIS, AURVANTIS.get(VORMOOR), "mountain") == 16
    s, e, pc = _party()
    out = _run(e, pc, "travel", biome="mountain")[0]
    eff = out.effects[0]
    assert eff["grounded"] == "beyond" and places.terrain_of(s.at) == "mountain"
    assert s.clock_minutes >= 16 * 60


def test_the_fields_are_farmland_not_a_wilderness_beside_them():
    """"Into the fields" is the fields: a farmland `_WILD` region minted beside them would
    put "the heart of it" next to the ploughland."""
    s, e, pc = _party()
    _run(e, pc, "travel", biome="farmland")
    assert e.here().name == "the fields" and places.is_ring(s.at)


# --- the warrant at the way out ------------------------------------------------------------

def test_a_wanted_character_cannot_walk_out_by_naming_a_place():
    """§1.3 B3: the watch read the gate by name and the open road only for a travel by
    BIOME, so a travel by PLACE to ground outside — which is how the outskirts are
    entered — walked past it. Any travel from inside to outside is watched."""
    s, e, pc = _party(at=_vormoor_place("the market"))
    tag = states.wanted_tag(VORMOOR)
    pc.apply_effect(ActiveEffect(name="wanted", kind="situation", key=f"t:{tag}",
                                 source="t", origin="t", duration="until-dismissed",
                                 tags=(tag,)))
    out = _run(e, pc, "travel", place="the outskirts")[0]
    # Refused outright when the first step is the way out; since the watch is asked at
    # every hop (item 9 (e), 2026-09-30), a market further in than the way out is walked
    # as far as the last street before it, and stopped there with the same sentence.
    assert "wanted" in out.tell, out.tell
    assert out.status == "refused" or out.effects[0].get("watch_stopped"), out.tell
    assert places.setting_of(s.at) == "in"


# --- the road, stopped on and walked back ----------------------------------------------------

def test_the_road_column_prices_a_road(worlds):
    """Q12: `legs_from` read `row["road"]`, which no export ships — 0 of Aurvantis's 132
    travel rows — while every row says `by: "road"`, so every road was trackless.
    Vormoor to Dustgate was 38 hours; on the road column it is 27."""
    for e in list(_settled(worlds))[:20]:
        for leg in journey.legs_from(worlds, e.id):
            if leg.by == "road":
                assert leg.road == "road", (e.name, leg.to_name)
    if worlds is AURVANTIS:
        leg = journey.find(journey.legs_from(AURVANTIS, VORMOOR), "Dustgate")
        assert journey.hours_for(leg, 30)[0] == 27


class _StopOnWatch(_Quiet):
    """The first road check of a march hits, and the band is travellers."""

    def __init__(self, real):
        super().__init__(real)
        self.n = 0

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation == "1d100" and label == "the road":
            self.n += 1
            return self.real.given(1 if self.n == 1 else 100, modifiers, label, notation)
        if notation == "1d100" and label == "what is on the road":
            return self.real.given(60, modifiers, label, notation)   # travellers
        return super().roll(notation, modifiers, label, visibility)


def test_a_journey_stopped_short_stands_on_its_own_road():
    """§1 of design B: a stopped journey stood the party at `region_set(origin)[0]` —
    "the approach", beside the town it had left, hours out — and every panel read the
    village. It stands on that road now, `@along-the-road-to-{to_id}`, labelled as such,
    with the road's facts on every branch of the effect."""
    s, e, pc = _party()
    e.dice = _StopOnWatch(e.dice.real)
    out = _run(e, pc, "journey", to="Scrapden")[0]
    eff = out.effects[0]
    assert eff.get("stopped_short"), out.tell
    assert outskirts.is_along(s.at) and places.location_of(s.at) == VORMOOR
    assert eff["from_id"] == VORMOOR and eff["setting"] == "outside"
    assert eff["direction"] == "out" and eff["place"] == s.at
    assert eff["went_by"] == ["the outskirts", "the crossroads", "the road to Scrapden"]
    assert e.here().name == "on the road to Scrapden"
    where = geography.where(AURVANTIS, s, e.here())
    assert where.setting == "road" and where.label == "on the road to Scrapden"
    assert "out of Vormoor" in where.detail


def test_walking_back_along_a_stopped_road_costs_the_hours_walked():
    """Q15: the road forgot itself for free the moment the party was back inside the
    walls, so a party stopped six hours out was home in minutes."""
    s, e, pc = _party()
    e.dice = _StopOnWatch(e.dice.real)
    _run(e, pc, "journey", to="Scrapden")
    walked = int(s.road["walked"])
    assert walked > 0
    e.dice = _Quiet(e.dice.real)
    clock = s.clock_minutes
    out = _run(e, pc, "travel", place="the market")[0]
    assert places.setting_of(s.at) == "in" and s.road == {}
    assert s.clock_minutes - clock >= walked * 60, out.tell
    assert out.effects[0]["direction"] == "in"


def test_a_journey_passes_through_the_crossroads():
    """Q11: "journeys along those roads pass through it". Said in the tell and carried
    in the effect, so the page walks the real way out."""
    s, e, pc = _party()
    out = _run(e, pc, "journey", to="Dustgate")[0]
    assert out.tell.startswith("Out by the outskirts, the crossroads and the road to "
                               "Dustgate."), out.tell


# --- founding the road's own kinds ---------------------------------------------------------

def test_a_crossroads_is_founded_out_on_the_road_not_in_the_market():
    """Turns 6 and 7 (17.3): `found kind=crossroads` and `found kind=road` were refused
    as "no such kind of place" — the kinds were the settlement table's. Off a town room
    they are refused with the fix to walk out first; off outside ground they are made."""
    s, e, pc = _party(at=_vormoor_place("the way in"))
    out = _run(e, pc, "found", name="the old milestone", kind="milestone")[0]
    assert out.status == "refused" and "go to the outskirts first" in out.tell
    assert out.fix == {"kind": "go", "place": "the outskirts"}
    _run(e, pc, "travel", place="the outskirts")
    made = _run(e, pc, "found", name="the old milestone", kind="milestone")[0]
    assert made.status != "refused", made.tell
    assert made.effects[0]["setting"] == "outside"


def test_fits_here_knows_the_road_s_kinds(worlds):
    for e in list(_settled(worlds))[:6]:
        ring = outskirts.ring(worlds, e)
        out = next(p for p in ring if p.name == "the outskirts")
        town = places.home_set(e)[0]
        for kind in ("road", "crossroads", "milestone"):
            assert places.fits_here(kind, e, out) == ""
            assert "go to the outskirts first" in places.fits_here(kind, e, town)
        assert "no such kind" in places.fits_here("volcano", e, town)


# --- a horse changes it (Q13) ---------------------------------------------------------------

def test_the_owner_s_multipliers_and_the_hustle_rule():
    """"travel between settlement[s] should take days without a horse, half the time with
    a horse and a third … if you gallop … [horse fatigue should kick in if the journey is
    too far]." A gallop is a hustle (AoN Rules ID=50): one hour a day free, the second
    hurts the mount and tires it, the rest of the day is ridden."""
    assert journey.mounted_hours(27, "walk") == (27, 0)
    assert journey.mounted_hours(27, "ride") == (14, 0)
    assert journey.mounted_hours(6, "gallop") == (2, 1)       # a third, and blown once
    assert journey.mounted_hours(3, "gallop") == (1, 0)       # the free hour
    hours, hurt = journey.mounted_hours(27, "gallop")
    assert 27 / 3 < hours < 14 and hurt == 2                  # too far: tires, rides on
    assert journey.pace_of("on horseback") == "ride" and journey.pace_of("hustle") == "gallop"


def _horse(s):
    horse = instantiate("horse", scene=s, name="Bess")
    s.add(horse)
    horse.apply_effect(ActiveEffect(name="travels with you", kind="situation",
                                    key="company", source="company:t",
                                    duration="until-dismissed",
                                    tags=(states.TRAVELS_WITH_YOU,)))
    return horse


def test_riding_needs_a_horse():
    s, e, pc = _party()
    out = _run(e, pc, "journey", to="Dustgate", pace="ride")[0]
    assert out.status == "refused" and "horse" in out.tell
    assert s.location_id == VORMOOR


def test_a_gallop_too_far_tires_the_horse_through_the_applicator():
    """Fatigue is an ActiveEffect (law 2), timed at the book's eight hours of rest so the
    clock expires it; the damage is the mount's own lethal damage. Two galloping days to
    Dustgate: two points, and blown."""
    s, e, pc = _party()
    horse = _horse(s)
    hp = horse.hp
    out = _run(e, pc, "journey", to="Dustgate", pace="gallop")[0]
    assert s.location_id != VORMOOR, out.tell
    eff = out.effects[0]
    assert eff["pace"] == "gallop" and eff["mounts"] == [horse.ref]
    assert eff["hours"] < eff["on_foot"] / 2
    assert horse.hp == hp - 2
    tired = [x for x in horse.effects if x.key == journey.MOUNT_FATIGUE]
    assert tired and tired[0].source == "hustle" and tired[0].rounds_left
    s.advance(9 * 60)
    assert not any(x.key == journey.MOUNT_FATIGUE for x in horse.effects)


def test_riding_halves_the_road():
    s, e, pc = _party()
    _horse(s)
    out = _run(e, pc, "journey", to="Dustgate", pace="ride")[0]
    assert out.effects[0]["hours"] == 14


# --- the settled predicate ---------------------------------------------------------------

def test_a_village_is_urban_to_every_reader(worlds):
    """R0-1: `biomes.from_world` gave `urban` only to `kind == "CITY"`, so the synthetic
    world's VILLAGE and TOWN read as open ground to that one reader and as settlements to
    the other three."""
    for e in _settled(worlds):
        assert biomes.from_world(worlds, e)[0] == "urban", (e.name, e.kind)


# --- the replay corpus ---------------------------------------------------------------------

needs_bobby = pytest.mark.skipif(not replays.available(),
                                 reason="the Bobby corpus is not on this disk")


@needs_bobby
def test_bobby_turn_5_leave_now_reaches_outside():
    """The recorded reading of turn 5, through the fixed interpreter and engine: the
    travel it owes can only name the ring, and walking there leaves the village."""
    rec = replays.turn(5)
    reading = rec["plan"]["reading"]
    s, e, pc = _party(at=_vormoor_place("the market"))
    known = e.places()
    assert "travel" in interpret.ops_for(reading, s, known)
    choices = interpret.travel_choices(reading, s, known, AURVANTIS.get(VORMOOR))
    assert set(choices) <= {p.name for p in known if places.is_ring(p.id)}
    out = _run(e, pc, "travel", place=choices[0])[0]
    assert out.effects[0]["direction"] == "out"


@needs_bobby
@pytest.mark.parametrize("n", [6, 7])
def test_bobby_s_refused_road_kinds_now_have_a_road_outside(n):
    """Turns 6 and 7: the plan's `found` of a crossroads / a road off the way in was
    refused as "no such kind of place", then its `travel` to "the crossroads" was refused
    as no such place. Vormoor, with three roads out, has a crossroads now: the same
    `found` is refused with the fix to GO there, and the same travel arrives."""
    rec = replays.turn(n)
    intents = rec["plan"]["intents"]
    found = next(i for i in intents if i["op"] == "found")
    travel = next(i for i in intents if i["op"] == "travel")
    s, e, pc = _party(at=_vormoor_place("the way in"))
    out = _run(e, pc, "found", **found["params"])[0]
    assert out.status == "refused"
    assert out.fix == {"kind": "go", "place": "the crossroads"}, out.tell
    went = _run(e, pc, "travel", **travel["params"])[0]
    assert went.status != "refused", went.tell
    assert e.here().name == "the crossroads" and places.setting_of(s.at) == "outside"
    # And a road's own kind founded out there is made, which no kind of the town's was.
    made = _run(e, pc, "found", name="the old milestone", kind="milestone")[0]
    assert made.status != "refused", made.tell


@needs_bobby
def test_bobby_s_forest_loads_as_outside_vormoor():
    """Q14: his save stands at `…~forest:the-approach`, a forest the world does not have.
    It loads as it is, labelled "near Vormoor · forest", with no heal."""
    save = replays.save("bobby.json")
    at = save.get("at") or f"{VORMOOR}~forest:the-approach"
    s = Scene(location_id=save["location_id"], at=at)
    assert geography.where(AURVANTIS, s).label == "near Vormoor"
    assert places.setting_of(at) == "outside"
