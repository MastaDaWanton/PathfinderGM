"""One journey a turn: a plan may name a route, and the party walks the first leg of it.

Item 35 of the 2026-09-19 play-test (`docs/playtest-2026-09-18.md`), found by a live run
rather than reported. "I find the mayor and grab him by the collar" came back as a plan
of FIVE `travel` ops and the engine ran them in order:

    travel {"place": "the guildhall"}                     -> resolved
    travel {"place": "the market"}                        -> resolved
    travel {"place": "the lane"}                          -> resolved
    travel {"place": "the green"}                         -> resolved
    travel {"place": "the upper floor of the guildhall"}  -> refused: the stairs to it
                                                            are inside the guildhall

The party ended standing on **the green** — a place it had merely passed through — while
the prose described the market, because the beat was written about a place in the middle
of the list. Nothing capped movement per turn: each `travel` was legal on its own.

The measurement that sized it, taken 2026-09-20 over every save in the scratchpad,
deduplicated by campaign and turn so copies of one save could not count twice: of 222
unique planned turns, **2 carried a travel at all, and neither carried exactly one**. So
this is rare — and has never once happened correctly.

The first leg is kept and the rest refused, rather than collapsing to the last, because
that turn is the argument: the destination the model meant (the upper floor) was reachable
only from a place earlier in its own list, and the engine has no route-finder to walk it
there. Prior art agrees from the other side — Inform's Misadventure and Safari Guide take
ONE named room and derive the route; Angband and DCSS travel toward one destination with
the path computed and the walk interruptible. In every tradition the traveller names a
destination and the system finds the way. Here the model was handing over the way itself.
"""
from __future__ import annotations

from rules import journey
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")


def _a_town_with_places() -> str:
    """A settlement the engine lays more than one place in, so a route can be named."""
    for settlement in WORLD.play["settlements"]:
        s = Scene(location_id=settlement["id"])
        pc = instantiate("guildhand", scene=s, name="PC")
        pc.kind = "pc"
        s.add(pc)
        e = Engine(s, Dice(seed=1), world=WORLD)
        e.place_party()
        if len(e.places()) >= 3:
            return settlement["id"]
    raise AssertionError("no settlement in the shipped world has three places")


TOWN = _a_town_with_places()


def _party():
    s = Scene(location_id=TOWN)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 40
    s.add(pc)
    e = Engine(s, Dice(seed=2), world=WORLD)
    e.place_party()
    return s, e, pc


def _travels(e, pc, *places):
    raw = [{"op": "travel", "actor": pc.ref, "because": "t", "params": {"place": p}}
           for p in places]
    return e.run(e.validate(raw, origin="author:test"))


def _elsewhere(e, n=3):
    """Names of places in this town that are not where the party stands, reachable."""
    here = e.here()
    out = [p.name for p in e.places()
           if p.id != here.id and not p.described_only]
    assert len(out) >= 2, out
    return out[:n]


def test_a_plan_of_five_travels_moves_the_party_once():
    """The measured turn, in the shape it arrived: the party walks the first leg and
    stands there, rather than ending four places along its own route."""
    s, e, pc = _party()
    route = _elsewhere(e, 3)
    was = s.at
    res = _travels(e, pc, *route)
    assert s.at != was, "the first leg still happens"
    first = [p for p in e.places() if p.name == route[0]][0]
    assert s.at == first.id, "the party is at the FIRST place named, not the last"
    tells = [o.tell for o in res.outcomes]
    assert "already travelled this turn" in " ".join(tells[1:])


def test_the_refusal_names_where_the_party_now_stands():
    """So the next turn can carry on from it — the roguelike's "repeat the command to
    resume", which is the only reason a refusal here is not a dead end."""
    s, e, pc = _party()
    route = _elsewhere(e, 2)
    res = _travels(e, pc, *route)
    refused = " ".join(o.tell for o in res.outcomes[1:])
    assert route[0] in refused, refused
    assert "One journey a turn" in refused


def test_one_travel_is_untouched():
    """The rule must cost the ordinary turn nothing: 220 of the 222 turns measured
    carried no travel, and the two that did are what this is for."""
    s, e, pc = _party()
    where = _elsewhere(e, 1)[0]
    was = s.at
    res = _travels(e, pc, where)
    assert s.at != was
    assert "already travelled" not in " ".join(o.tell for o in res.outcomes)


def test_a_fresh_batch_is_a_fresh_journey():
    """One journey a TURN, not one a campaign. Same reasoning as `_battle_joined`, and
    the bug it would cause is worse: a party that may never travel again."""
    s, e, pc = _party()
    route = _elsewhere(e, 2)
    _travels(e, pc, route[0])
    at_first = s.at
    _travels(e, pc, route[1])
    assert s.at != at_first, "the second turn's journey was refused as if it were the first's"


def test_a_travel_that_moves_nobody_does_not_spend_the_turn_s_journey():
    """A travel to the ground already underfoot answers "You are already there" and
    moves no one, so the real journey behind it must still run — otherwise a plan that
    opens by restating where the party stands strands it for a turn.

    (A place that does not exist at all cannot reach this rule: `validate` refuses the
    whole plan by name before `run` ever sees it, which is where the 2026-09-06 fix put
    it so the model could repair the plan rather than meet a 502.)
    """
    s, e, pc = _party()
    here_name = e.here().name
    where = _elsewhere(e, 1)[0]
    was = s.at
    res = e.run(e.validate(
        [{"op": "travel", "actor": pc.ref, "because": "t", "params": {"place": here_name}},
         {"op": "travel", "actor": pc.ref, "because": "t", "params": {"place": where}}],
        origin="author:test"))
    assert s.at != was, "the real journey behind a standing-still travel was barred"
    assert "already travelled" not in " ".join(o.tell for o in res.outcomes)


def test_the_road_out_is_the_next_turn_s_too():
    """The same defect in a longer coat, and this one costs days rather than minutes:
    a plan that walks across town and then takes the road out."""
    legs = journey.legs_from(WORLD, TOWN)
    if not legs:
        import pytest

        pytest.skip("this town has no road out to test with")
    s, e, pc = _party()
    where = _elsewhere(e, 1)[0]
    res = e.run(e.validate(
        [{"op": "travel", "actor": pc.ref, "because": "t", "params": {"place": where}},
         {"op": "journey", "actor": pc.ref, "because": "t",
          "params": {"to": legs[0].to_name}}],
        origin="author:test"))
    assert s.location_id == TOWN, "the party left town on a turn it had already walked"
    assert "next turn" in " ".join(o.tell for o in res.outcomes)
