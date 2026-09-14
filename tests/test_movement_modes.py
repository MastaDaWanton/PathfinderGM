"""Fly, climb, swim and burrow speeds, and which of them the engine can act on.

Written at stage 1 (2026-09-14), when the answer was "none of them", and rewritten at
stage 3, when fly and climb became real. Both states are worth keeping here because the
defect was never the gap — it was the **disagreement**.

The same tag arrives by two doors. A world that describes a winged people reaches
`races.CUES`, which said "a fly speed: the engine moves on the ground only". A player who
picked Flight on the races bench reached the evolution, which said nothing. One door
admitted the engine could not fly and the other quietly implied it could, and a player
learned different things about one tag depending which way they came in.

So these tests are about the two doors agreeing, in whichever direction the truth points.
At stage 1 both had to admit the gap. Now both must stop claiming it: the engine moves a
climber and a flier between levels and refuses anything else, so a `not_yet` left on
flight would be the same lie pointing the other way.

**And one of these is a rewrite because the stage-1 guard failed to fire.** It watched
`rules/engine.py` for the words "elevation", "fly_speed" and "airborne", so that the
caveats would break the day the engine learned to fly. The engine learned, and said
`can_move_vertically` instead — none of the guessed words appeared, and the guard passed
through the very change it existed to catch. It asks about behaviour now. A test written
against the words its author expects to type is a coincidence, not a guard.

Swim and burrow keep their caveats: the grid has no water and no earth to move through.
"""
from __future__ import annotations

import re
from rules import races
from rules.bestiary import instantiate

MODES = ("fly", "climb", "swim", "burrow")


def _movement_evolutions() -> dict[str, dict]:
    """Every evolution that grants a `move.<mode>.*` tag, found by the tag rather than
    by a hand-kept list of four ids — a fifth added tomorrow is caught the same day."""
    out = {}
    for eid, ev in races.evolutions().items():
        if any(re.match(r"^move\.(fly|climb|swim|burrow)\.", str(t))
               for t in (ev.get("tags") or [])):
            out[eid] = ev
    return out


def test_the_catalogue_still_offers_all_four_modes():
    """If this shrinks, the test below is guarding nothing."""
    found = _movement_evolutions()
    assert len(found) >= 4, found
    granted = {re.match(r"^move\.([a-z]+)\.", t).group(1)
               for ev in found.values() for t in ev["tags"]
               if re.match(r"^move\.([a-z]+)\.", t)}
    assert set(MODES) <= granted, granted


# The modes the engine can actually act on. `fly` and `climb` move a creature between
# levels and are refused to anything without them; `swim` and `burrow` have no medium to
# move through, because the grid has water and earth nowhere in it.
LIVE = ("fly", "climb")
INERT = ("swim", "burrow")


def _modes_of(ev: dict) -> set[str]:
    return {m.group(1) for t in ev["tags"]
            if (m := re.match(r"^move\.([a-z]+)\.", str(t)))}


def test_a_mode_the_engine_can_use_carries_no_caveat():
    """The stage-1 apology comes off the day the promise is kept, and not before.

    Flight and climb move a creature now: `_cannot_leave_the_ground` refuses the level
    change to anything without one, and `_move_cost` charges for it. A `not_yet` left on
    a working feature is worse than none — it tells a player something works less well
    than it does, and it trains everyone to stop reading them.
    """
    stale = {eid: ev["not_yet"] for eid, ev in _movement_evolutions().items()
             if _modes_of(ev) & set(LIVE) and str(ev.get("not_yet") or "").strip()}
    assert not stale, (
        f"the engine moves these now and they still apologise for it: {stale}")


def test_a_mode_the_engine_cannot_use_still_says_so():
    """The other half. Swimming and burrowing are still nowhere — the grid has no water
    and no earth — so the two doors to those tags must go on agreeing that they are
    decoration. When one becomes real, this fails and names it."""
    missing = [eid for eid, ev in _movement_evolutions().items()
               if _modes_of(ev) & set(INERT) and not str(ev.get("not_yet") or "").strip()]
    assert not missing, (
        f"{missing} grant a mode the engine cannot use and do not say so. "
        f"`races.CUES` says so on the world-derived path; both doors have to agree.")


def test_the_engine_reads_the_modes_it_says_it_reads():
    """Behaviour, not vocabulary — and this test is a rewrite for that reason.

    Stage 1 guarded this by grepping `rules/engine.py` for "elevation", "fly_speed" and
    "airborne", so that the caveats would fail the day the engine learned about movement.
    Stage 3 arrived, the engine learned, and **the guard did not fire**: the words it
    ended up using were `can_move_vertically` and `_cannot_leave_the_ground`, and none of
    the guessed ones appeared. A test written against the words its author expects to
    type is not a guard, it is a coincidence.

    So the question is now asked of the engine's behaviour: can a creature that climbs
    get off the ground, and is a creature that cannot refused? Those two facts are what
    "the engine reads a movement mode" means, and no rename can slip past them.
    """
    spider = instantiate("giant-spider")
    bear = instantiate("black-bear")

    assert spider.movement_modes().get("climb"), "the spider lost its climb speed"
    assert spider.can_move_vertically() == "climb"
    assert bear.can_move_vertically() == "", "a bear should have no way up"


def test_the_two_doors_to_every_mode_agree():
    """A winged people from World Bible and a Flight evolution are the same tag, and a
    player must not learn different things about it depending which door they came in by.
    That is the defect stage 1 was written about, and it points the other way now: the
    engine flies, so NEITHER door may claim it does not.

    Asked of all four modes, not just flight. The first version of this test asked only
    about `move.fly.` and passed while `CUES` still told a climbing people "the engine
    has no walls" and the evolution said nothing — the very disagreement the file is
    named for, surviving inside its own guard because the guard was too narrow.
    """
    for mode in LIVE + INERT:
        expect_caveat = mode in INERT
        world_side = [waits for _pat, granted, _line, waits in races.CUES
                      if any(t.startswith(f"move.{mode}.") for t in granted)]
        bench_side = [ev.get("not_yet") or "" for ev in _movement_evolutions().values()
                      if any(t.startswith(f"move.{mode}.") for t in ev["tags"])]
        assert world_side and bench_side, f"{mode} is no longer offered by both doors"
        assert bool(any(world_side)) is expect_caveat, (mode, world_side)
        assert bool(any(bench_side)) is expect_caveat, (mode, bench_side)


def test_a_race_that_takes_flight_gets_a_fly_speed_and_no_apology():
    """End to end through the real path. `expand()` turns `move.fly.base` into a real
    speed and collects `not_yet`, so a document built the way the bench builds one shows
    exactly what stage 3 changed: the speed is there, the caveat is gone."""
    built = races.derive({"id": "x", "name": "X", "speed": 30, "size": "medium",
                          "evolutions": [{"id": "flight"}]})

    assert races.speeds(built)["fly"] == 30, "the fly speed stopped reaching the sheet"
    assert not [n for n in built["not_yet"] if "fly speed" in n], built["not_yet"]
    # Still honestly priced — that never was the complaint.
    assert races.price_tag("move.fly.30") == (4, "fly 30 ft (clumsy)", "exact")


# --- what the engine does with a mode, once it can read one ---------------------------

def _scene_with_a_map():
    """A grid, a man on it, and a spider beside him — the smallest table that can ask
    whether somebody may leave the floor."""
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.grid import Grid

    s = Scene(location_id="t")
    man = instantiate("guildhand", scene=s, name="the man")
    s.add(man, at=(5, 5))
    spider = instantiate("giant-spider", scene=s, name="the spider")
    s.add(spider, at=(6, 5))
    s.grid = Grid()
    return s, Engine(s, Dice(seed=2), world=None), man, spider


def _move(engine, ref, square):
    raw = {"op": "move", "actor": ref, "because": "t",
           "params": {"who": ref, "square": list(square)}}
    return engine.run(engine.validate([raw], origin="author:test"))


def test_a_climber_may_take_to_the_wall_and_a_man_may_not():
    """The whole point of stage 3, as a table can see it. The spider has climb 30 off its
    own stat block prose; the man has nothing, and is refused with the reason rather than
    quietly left on the floor or quietly allowed up."""
    s, e, man, spider = _scene_with_a_map()

    _move(e, spider.ref, (6, 5, 4))
    assert s.positions[spider.ref] == (6, 5, 4), "the climber did not get up"

    res = _move(e, man.ref, (5, 5, 4))
    assert s.positions[man.ref] == (5, 5), "the man left the ground"
    assert "no way up" in " ".join(o.tell for o in res.outcomes).lower()


def test_coming_down_needs_no_permission():
    """Everybody can fall. A refusal to descend would strand anything that lost its
    flight, and there is no rule anywhere that says you may not go down."""
    s, e, man, _spider = _scene_with_a_map()
    s.positions[man.ref] = (5, 5, 3)
    _move(e, man.ref, (5, 5, 0))
    # The level, not the shape of the tuple: a position on the ground is written as a
    # two-tuple, because that is what a two-tuple has meant since the third axis was
    # added and it is what every save on disk is written in.
    landed = s.positions[man.ref]
    assert (landed[0], landed[1]) == (5, 5)
    assert (landed[2] if len(landed) > 2 else 0) == 0


def test_the_climb_is_charged_for():
    """`_move_cost` adds the vertical to the route it found on the floor, so going up
    four squares costs twenty feet more than standing still."""
    s, e, _man, spider = _scene_with_a_map()
    assert e._move_cost(spider.ref, (6, 5, 0), (6, 5, 4)) == 20
    assert e._move_cost(spider.ref, (6, 5, 0), (6, 5, 0)) == 0


def test_a_creature_overhead_does_not_block_the_floor():
    """Measured as a real defect while building this: `occupied` collected every body's
    footprint with no notion of height, so a spider on a ceiling twenty feet up held the
    square beneath it against everybody walking underneath."""
    s, _e, _man, spider = _scene_with_a_map()
    s.positions[spider.ref] = (6, 5, 4)

    assert (6, 5) not in s.occupied(level=0), "the ceiling spider still blocks the floor"
    assert (6, 5) in s.occupied(level=4), "and it has to block where it actually is"
