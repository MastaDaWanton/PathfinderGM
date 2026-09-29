"""I3: `travel` takes a pace — a horse outside the walls goes faster, by Lane B's own rules.

Lane B built riding and galloping for journeys (owner, Q13: half the time riding, a third
at a gallop, the mount tiring by the hustle rule) and could not give `travel` the param —
rules/intents.py was not theirs — so their design doc recorded: "Travel by biome to beyond
ground rides no horse". A party with a horse walked to the fields and walked the sixteen
hours to the mountain beyond Vormoor. The mount is the one Lane B's journey reads: a
bestiary horse (`journey.MOUNTS`) who travels with you.
"""
from __future__ import annotations

import pytest

from rules import geography, journey, places, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
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


def _party(world=AURVANTIS, town=VORMOOR, horse=False, at=""):
    s = Scene(location_id=town)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 60
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party(at)
    e.dice = _Quiet(e.dice)
    mount = None
    if horse:
        mount = instantiate("horse", scene=s, name="Bess")
        s.add(mount)
        mount.apply_effect(ActiveEffect(name="travels with you", kind="situation",
                                        key="company", source="company:t",
                                        duration="until-dismissed",
                                        tags=(states.TRAVELS_WITH_YOU,)))
    return s, e, pc, mount


def _travel(e, pc, **params):
    e._journeyed = ""
    return e.run(e.validate([{"op": "travel", "actor": pc.ref, "because": "t",
                              "params": params}], origin="author:test")).outcomes[0]


def _settled(world):
    for row in world.play.get("settlements") or []:
        loc = world.get(row["id"])
        if loc is not None and places._settled(loc, "") \
                and geography.land_around(world, loc).near:
            yield loc


def test_i3_pace_is_a_closed_word():
    """A "canter" quietly walked would be a horse the player paid for and never rode."""
    s, e, pc, _ = _party()
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "travel", "actor": pc.ref, "because": "t",
                     "params": {"place": "the outskirts", "pace": "canter"}}])
    assert "walk, ride, gallop" in str(err.value)
    got = e.validate([{"op": "travel", "actor": pc.ref, "because": "t",
                       "params": {"place": "the outskirts", "pace": "on horseback"}}])
    assert got[0].params["pace"] == "ride"


def test_i3_riding_out_halves_the_minutes_outside(worlds):
    """Out to the outskirts: the step outside the walls ridden at half its minutes; the
    lanes of the town are a crowd's pace whatever carries you."""
    loc = next(_settled(worlds))
    s, e, pc, _ = _party(world=worlds, town=loc.id)
    walked = _travel(e, pc, place="the outskirts").effects[0]["minutes"]
    s2, e2, pc2, horse = _party(world=worlds, town=loc.id, horse=True)
    out = _travel(e2, pc2, place="the outskirts", pace="ride")
    eff = out.effects[0]
    assert eff["pace"] == "ride" and eff["mounts"] == [horse.ref]
    assert eff["minutes"] < walked, (eff["minutes"], walked)
    assert horse.at == s2.at, "the horse was left at the gate"
    assert "Mounted" in out.tell


def test_i3_riding_needs_a_horse(worlds):
    loc = next(_settled(worlds))
    s, e, pc, _ = _party(world=worlds, town=loc.id)
    was = s.at
    out = _travel(e, pc, place="the outskirts", pace="gallop")
    assert out.status == "refused" and "horse" in out.tell
    assert s.at == was and s.clock_minutes == 0


def test_i3_in_town_a_horse_changes_nothing():
    """Vormoor's market to its way in: four minutes at the village band (Q10), ridden or
    not."""
    at = next(p for p in places.home_set(AURVANTIS.get(VORMOOR)) if p.name == "the market").id
    s, e, pc, _ = _party(horse=True, at=at)
    out = _travel(e, pc, place="the way in", pace="ride")
    assert out.effects[0]["minutes"] == 4 and "pace" not in out.effects[0]


def test_i3_a_gallop_to_far_ground_blows_the_horse():
    """The mountain beyond Vormoor is sixteen hours on foot (Lane B's measurement); before
    this, sixteen hours with a horse standing by. At a gallop it is the journey's
    arithmetic, seven hours — and the second galloping hour is past the hustle rule's free
    one, so the horse is hurt and fatigued through the one applicator, on an eight-hour
    clock. The horse used to "not come with you any more" at the gate: a mount is owned,
    not befriended, and the loyalty question is no longer asked of it."""
    s, e, pc, horse = _party(horse=True)
    hp = horse.hp
    hours, hurt = journey.mounted_hours(16, "gallop")
    out = _travel(e, pc, biome="mountain", pace="gallop")
    eff = out.effects[0]
    assert eff["grounded"] == "beyond" and eff["pace"] == "gallop"
    assert eff["on_foot_hours"] == 16 and s.clock_minutes >= hours * 60
    assert s.clock_minutes < 16 * 60, "galloped at a walk"
    assert eff["tired"] == [horse.name] and horse.hp == hp - hurt
    tired = [x for x in horse.effects if x.key == journey.MOUNT_FATIGUE]
    assert tired and tired[0].source == "hustle"
    assert "The gallop has blown Bess" in out.tell
