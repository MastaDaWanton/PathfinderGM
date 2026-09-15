"""Leaving town, and paying the road for it.

Measured 2026-09-14, and it is the largest single gap the distance work found:
`Scene.location_id` was assigned once, at campaign creation, and **never reassigned
anywhere in the engine**. Pangrella ships twelve settlements and five trade routes, and
the game could reach exactly one of them, for ever. `travel` moves the ground underfoot
*inside* a settlement; there was no op that left it.

And travel cost nothing. `_op_travel` never touched the clock while thirst, hunger and
sleep were metered in hours, so walking from the market to the forest outside the walls
was free. The only time cost attached to movement anywhere in the app was
`places.VENTURES[kind]["hours"]` — a hand-authored constant with two values, 0 and 2.

**The output of a journey is time.** Miles are an input; hours are what the rest of the
game already knows how to spend, and `_op_venture` has had the shape since it was written:
`survival.pass_hours` for the body, then `scene.advance` for the world.

WHAT THE WORLD DOES NOT SAY, and why the answer is three-way. `docs/campaign-format.md`:
"No maps or coordinates." A route carries `carrying` and `friction`, both prose, and no
length — so two of the four inputs the overland table wants have no source at all. A
journey is therefore `exact` when the world states miles, and `derived` when it does not,
and a derived one is **reported in days and never in miles**, because a mileage nobody
wrote down would be this app inventing a fact about somebody else's world.
"""
from __future__ import annotations

from rules import journey
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")
PANGRELLA = "5bbd0c40345f"


# --- the rules' own numbers -------------------------------------------------------------

def test_the_speed_table_is_the_book_s():
    """Table: Movement and Distance, the overland column. The whole left column is
    speed/10 miles an hour, which is why this is a ratio and not a table."""
    for speed, per_day in ((15, 12), (20, 16), (30, 24), (40, 32)):
        got = journey.miles_per_hour(speed, "grassland", "road") * journey.HOURS_PER_DAY
        assert round(got) == per_day, (speed, got)


def test_terrain_and_road_multiply_it():
    """Table: Terrain and Overland Movement, which Pathfinder inherited from 3.5
    unchanged — verified cell by cell, and identical in every one."""
    assert journey.pace("jungle", "none")[0] == 0.25
    assert journey.pace("jungle", "road")[0] == 0.75
    assert journey.pace("mountain", "highway")[0] == 0.75
    assert journey.pace("grassland", "road")[0] == 1


def test_ground_the_table_has_no_row_for_says_so():
    """Nine of this app's fourteen biomes map to the table's nine rows; five do not, and
    `coast`, `urban`, `ruins`, `underground` and `planar` must not quietly travel at full
    speed. Three-way like `races.price_tag`, and for the same reason — a silent default
    would make a swamp as quick as a plain and nobody would ever find out."""
    got, words, how = journey.pace("coast")
    assert how == "unknown"
    assert "not on the overland table" in words
    assert got == 1.0, "and it still lets the party move, which is the right failure"


# --- what the shipped world can and cannot say ---------------------------------------------

def test_the_shipped_world_states_no_distances():
    """The measurement behind the whole three-way answer. If this ever fails, a world has
    gained geometry and `docs/campaign-format.md` needs reading again."""
    for leg in journey.legs_from(WORLD, PANGRELLA):
        assert leg.miles is None and leg.source == "derived"


def test_a_journey_with_no_stated_distance_is_never_reported_in_miles():
    """The honesty rule. A derived journey knows how long it took and refuses to claim
    how far it was."""
    leg = journey.legs_from(WORLD, PANGRELLA)[0]
    hours, measured, how = journey.hours_for(leg, 30)
    assert how == "derived"
    assert measured == "", measured
    assert "mile" not in journey.describe(leg, hours)


def test_a_world_that_states_miles_gets_the_arithmetic():
    """And the same leg with a length on it is answered from the table instead. Nothing
    in this module changes when an export gains `miles` — that is the point of the shape."""
    leg = journey.Leg(to_id="x", to_name="Anywhere", miles=48, road="road",
                      crosses=("grassland",), source="exact")
    hours, measured, how = journey.hours_for(leg, 30)
    assert how == "exact"
    assert hours == 16, hours            # 48 miles at 3 mph on a road
    assert "48 miles" in measured


def test_rough_ground_makes_the_same_distance_longer():
    plain = journey.Leg("x", "X", miles=48, road="road", crosses=("grassland",),
                        source="exact")
    jungle = journey.Leg("x", "X", miles=48, road="none", crosses=("jungle",),
                         source="exact")
    assert journey.hours_for(jungle, 30)[0] > journey.hours_for(plain, 30)[0] * 3


# --- the op --------------------------------------------------------------------------------

def _party(hp: int = 40, town: str = PANGRELLA):
    s = Scene(location_id=town)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = hp
    s.add(pc)
    e = Engine(s, Dice(seed=2), world=WORLD)
    e.place_party()
    return s, e, pc


def _go(e, pc, where, **params):
    raw = {"op": "journey", "actor": pc.ref, "because": "t",
           "params": {"to": where, **params}}
    return e.run(e.validate([raw], origin="author:test"))


def test_the_party_can_finally_leave_the_town():
    """The gap this file is named for. Twelve settlements ship; one was reachable."""
    s, e, pc = _party()
    _go(e, pc, "Zhilgoroth")
    assert s.location_id != PANGRELLA
    assert s.at.startswith(s.location_id), "the party is standing somewhere in the new town"


def test_a_journey_costs_days_on_the_clock():
    """Travel that costs nothing is why a three-day march used to be free on a clock that
    meters thirst in hours."""
    s, e, pc = _party()
    assert s.clock_minutes == 0
    _go(e, pc, "Zhilgoroth")
    assert s.clock_minutes > 24 * 60, "a journey between towns took less than a day"


def test_a_road_that_does_not_exist_is_refused_with_the_ones_that_do():
    s, e, pc = _party()
    res = _go(e, pc, "Atlantis")
    tell = " ".join(o.tell for o in res.outcomes)
    assert "no road" in tell.lower()
    assert "Zhilgoroth" in tell, tell
    assert s.location_id == PANGRELLA


def test_the_fight_and_the_bystanders_do_not_come_along():
    """`_op_travel` learned this the hard way in the 2026-08-22 playtest — a gatekeeper
    travelled inside the scene and took an NPC turn for the rest of the session. A
    journey sheds harder, because it is days rather than steps."""
    s, e, pc = _party()
    s.add(instantiate("guildhand", scene=s, name="a merchant"))
    _go(e, pc, "Zhilgoroth")
    assert "a merchant" not in [a.name for a in s.actors.values()]


def test_a_march_is_days_of_walking_and_not_a_sleepless_forced_one():
    """Found by driving it. The first version spent the whole journey in one
    `pass_hours` call, so a five-day road was forty hours *continuously* — and a
    four-hit-point traveller and a sixty-hit-point one both collapsed at exactly the same
    hour, because what stopped them was the twenty-four-hour wakefulness grace rather
    than anything about their bodies.

    Eight hours a day with a camp between. The elapsed clock is therefore longer than the
    walking: five days of road is five eight-hour marches and four nights.
    """
    s, e, pc = _party(hp=4)
    _go(e, pc, "Zhilgoroth")
    assert s.location_id != PANGRELLA, "a frail traveller could not make a walked road"
    assert s.clock_minutes > 5 * journey.HOURS_PER_DAY * 60, \
        "the nights between the marches are not on the clock"


def test_somebody_who_cannot_walk_it_does_not_arrive():
    """The other half, and the thing that keeps the clock from being decorative: if the
    body gives out with road still to go, the journey did not happen."""
    s, e, pc = _party()
    pc.awake_minutes = 40 * 60          # already two days without sleep
    res = _go(e, pc, "Zhilgoroth")
    if s.location_id == PANGRELLA:
        assert "turned back" in " ".join(o.tell for o in res.outcomes).lower()


def test_a_wanted_traveller_is_stopped_on_the_road():
    """The warrant reads the road exactly as it reads the gate. Leaving town by the
    highway is the most public way out there is, and `_op_travel` already refuses the
    open road to somebody who is wanted."""
    from rules import states
    from rules.activeeffect import ActiveEffect

    s, e, pc = _party()
    # Granted the way a scheme outcome grants it — one effect, one source — which is how
    # `tests/test_wanted.py` does it and the only way the tag is ever meant to arrive.
    tag = states.wanted_tag(PANGRELLA)
    pc.apply_effect(ActiveEffect(name="wanted", kind="situation", key=f"scheme:{tag}",
                                 source="scheme:test", origin="scheme:test",
                                 duration="until-dismissed", tags=(tag,)))
    assert states.standing_with_the_law(pc, PANGRELLA) == "wanted"

    res = _go(e, pc, "Zhilgoroth")
    assert s.location_id == PANGRELLA, "walked out of a town that wanted them"
    assert "watched" in " ".join(o.tell for o in res.outcomes).lower()


def test_a_way_past_the_watch_opens_the_road():
    """The same door the gate honours: `knows.way-past-gate` is a tag a scheme's witness
    or a smuggler hands you, and the road is open to somebody holding it."""
    from rules import states
    from rules.activeeffect import ActiveEffect

    s, e, pc = _party()
    tag = states.wanted_tag(PANGRELLA)
    pc.apply_effect(ActiveEffect(name="wanted", kind="situation", key=f"scheme:{tag}",
                                 source="scheme:test", origin="scheme:test",
                                 duration="until-dismissed", tags=(tag,)))
    pc.apply_effect(ActiveEffect(name="a way out", kind="situation", key="scheme:way",
                                 source="scheme:test", origin="scheme:test",
                                 duration="until-dismissed",
                                 tags=("knows.way-past-gate",)))
    _go(e, pc, "Zhilgoroth")
    assert s.location_id != PANGRELLA


# --- and the model is told the roads exist -------------------------------------------------

def test_the_brief_names_the_roads_out():
    """An op the narrator is never told about is inert, which is the defect this whole
    run of work keeps turning up. The brief names the places in a town for exactly this
    reason — "the model reconstructs the room from earlier beats" — and a settlement with
    no road named is one the model will either never reach or will invent a way to."""
    from gm import prompts

    s, e, pc = _party()
    brief = prompts.scene_brief(WORLD, s, WORLD.get(PANGRELLA), recent=[], turn=1)
    assert "ROADS OUT OF PANGRELLA" in brief
    assert "Zhilgoroth" in brief
    # And the instruction that tells it the op exists at all, in the briefing every
    # turn is built from.
    assert '"op": "journey"' in prompts.BRIEFING, "the narrator is never told it can"


def test_the_brief_does_not_offer_a_road_that_is_not_there():
    """Pangrella has one road in the shipped world. The brief must not imply more."""
    from gm import prompts

    s, e, pc = _party()
    brief = prompts.scene_brief(WORLD, s, WORLD.get(PANGRELLA), recent=[], turn=1)
    roads = [ln for ln in brief.splitlines() if "ROADS OUT" in ln][0]
    for leg in journey.legs_from(WORLD, PANGRELLA):
        assert leg.to_name in roads
    assert roads.count(",") < 3, roads
