"""Lane C — who the world casts (playtest 2026-09-28 item 8: Drenn Ironvale first in every
game), keepers named from the town's own families, and the pregens' backgrounds.
"""
from __future__ import annotations

import collections
import json

import pytest

from rules import backgrounds, geography, keepers, names, openings, schemes
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

AURVANTIS = "fixtures/aurvantis-campaign.json"
PANGRELLA = "fixtures/pangrella-campaign.json"


def _bound(world, pc_path: str, seed: int, background: str | None = None):
    """The character's past bound in the town their story seed draws — no opening, no
    model: what `new_campaign` does before it stages the start."""
    pc = load_pc(pc_path)
    if background is not None:
        pc.background = background
    town, _doc = openings.choose(world, pc, openings.rng_for(seed, "start"))
    scene = Scene(location_id=town.id)
    scene.story_seed = seed
    scene.add(pc)
    engine = Engine(scene, Dice(1), world=world)
    return engine, backgrounds.bind(engine, scene.pc())


def test_ties_find_people_by_their_own_role():
    """Item 8.1, measured: every one of Aurvantis's 256 cast rows says `role: "Person"`,
    so a tie matched nobody and fell to `cast[len(taken) % len(cast)]` — cast[0], Drenn
    Ironvale, whatever the tie asked for. Roles are read off each person's own entity
    now: over 200 bonesetter seeds the teacher is always somebody whose role is a healer's
    and at least eight different people are named (measured at this commit: 11)."""
    world = load_cached(AURVANTIS)
    cast = {r["id"]: r for r in world.play["cast"]}
    people, roles = collections.Counter(), collections.Counter()
    for seed in range(200):
        _e, bound = _bound(world, "fixtures/pc-thessaly.json", seed)
        assert bound, seed
        people[bound[0]["who"]] += 1
        roles[geography.role_of(world, cast[bound[0]["entity"]])] += 1
    healer_words = schemes.role_words("healer")
    assert all(any(w in r.lower() for w in healer_words) for r in roles), roles
    assert len(people) >= 8, people


def test_nobody_is_first_in_every_game():
    """Item 8, measured: Drenn Ironvale was the first named person in 100% of games —
    the first tie, the first quest giver and the market's family all took the town's
    first cast member, and every game started in the same town. Across 200 seeds and
    the backgrounds whose ties name a person, nobody is named first in more than one
    game in ten (measured at this commit: 72 different people, the busiest 13 of 200)."""
    world = load_cached(AURVANTIS)
    with_people = ["apprenticed", "gate-watch", "thief-taker", "pilgrim", "household",
                   "guild-clerk", "bonesetter", "pit-fighter"]
    first = collections.Counter()
    for seed in range(200):
        _e, bound = _bound(world, "fixtures/pc-kesst.json", seed,
                           background=with_people[seed % len(with_people)])
        named = [b["who"] for b in bound if b.get("who")]
        if named:
            first[named[0]] += 1
    assert sum(first.values()) >= 150
    name, most = first.most_common(1)[0]
    assert most <= 20, (name, most, first.most_common(5))


def test_your_past_and_your_first_quest_giver_are_not_the_same_by_accident():
    """Item 8.3: binding and schemes each kept their own `taken` set, so the man who
    taught you and the man who hands you the first quest were the same man by accident.
    One `Scene.spoken_for` is shared now: over 200 seeds, never the same person."""
    world = load_cached(AURVANTIS)
    scheme = schemes.all_schemes()["the-lost-thing"]
    for seed in range(200):
        engine, bound = _bound(world, "fixtures/pc-thessaly.json", seed)
        tied = {b["entity"] for b in bound if b.get("entity")}
        filled = schemes.fill_slots(engine, scheme)
        givers = {s.get("entity") for s in filled.values()
                  if isinstance(s, dict) and s.get("entity")}
        assert not (tied & givers), (seed, tied, givers)


def test_everyone_a_tie_names_knows_you_when_they_arrive():
    """§4.8.4: `acquaint` only ever touched the one person beside the character at the
    opening, so a tied teacher who walked in on day three was a stranger. Every tie's
    person is recorded in `scene.acquainted`, and the arrival door greets them."""
    world = load_cached(AURVANTIS)
    engine, bound = _bound(world, "fixtures/pc-thessaly.json", 7)
    entity = bound[0]["entity"]
    assert engine.scene.acquainted == [entity]
    teacher = instantiate("guildhand", scene=engine.scene, name=bound[0]["who"],
                          world_entity_id=entity)
    engine.scene.add(teacher)
    assert teacher.has_state("bond.knows-you")
    assert [e.origin for e in teacher.effects if "bond.knows-you" in e.tags] == \
        ["background:bonesetter"]


# --- keepers -------------------------------------------------------------------------------------

def _keeper_name(world, town_id: str, salt):
    place = next(p for p in _places(world, town_id) if p.name == "the market")
    return keepers.name_for(place, world, salt=salt)


def _places(world, town_id):
    from rules import places

    return places.spots_for(world.get(town_id))


def test_keepers_take_the_towns_own_families():
    """Item 8.4, measured: the market was kept by an Ironvale in every game — a keeper's
    family came only from the town's four cast members, while Vormoor's own sixteen
    `play.names` families (Grimstone, Fellhaven, …) were read by nothing. The town's pool
    comes first now, and the owner's Q18: a keeper is the same person all campaign and a
    different person in the next (salted by the story seed)."""
    world = load_cached(AURVANTIS)
    vormoor = next(e for e in world.entities.values() if e.name == "Vormoor")
    pool = names.town_pool(world, vormoor.id)
    assert pool and len(pool["family"]) >= 8
    cast_families = {r["name"].split()[-1] for r in world.play["cast"]
                     if r.get("home_id") == vormoor.id}
    allowed = set(pool["family"]) | cast_families
    got = [_keeper_name(world, vormoor.id, salt) for salt in range(1, 41)]
    assert all(n.split()[-1] in allowed for n in got), got
    assert len({n.split()[-1] for n in got}) >= 5, got
    assert _keeper_name(world, vormoor.id, 17) == _keeper_name(world, vormoor.id, 17)
    # Given names from the people who live here (R0), not the whole world's cast.
    given = set(pool["given"])
    assert all(n.split()[0] in given for n in got), got


def test_a_world_without_town_pools_falls_back_to_its_cast():
    """Pangrella ships no name pools: its keepers still come from its cast's families."""
    world = load_cached(PANGRELLA)
    town = next(e for e in world.entities.values()
                if e.name == "Pangrella" and e.kind == "CITY")
    assert names.town_pool(world, town.id) is None
    families = {r["name"].split()[-1] for r in world.play["cast"]
                if r.get("home_id") == town.id and len(r["name"].split()) > 1}
    got = _keeper_name(world, town.id, 5)
    assert got.split()[-1] in families, (got, families)


# --- the pregens ---------------------------------------------------------------------------------

@pytest.mark.parametrize("path,background", [
    ("fixtures/pc-kesst.json", "thief-taker"),
    ("fixtures/pc-borin.json", "caravan-hand"),
    ("fixtures/pc-thessaly.json", "bonesetter"),
])
def test_the_pregens_have_a_past(path, background):
    """The owner, 2026-09-28: "give them backgrounds or its not an accurate test of the
    new origin/start" — all three pregens shipped `background: ""`, so no
    background-shaped start could ever be exercised by them."""
    raw = json.loads(open(path, encoding="utf-8").read())
    assert raw["background"] == background
    assert backgrounds.get(background) is not None
    assert load_pc(path).background == background
