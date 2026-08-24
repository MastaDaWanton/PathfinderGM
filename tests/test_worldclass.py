"""World classes: progression that runs alongside a character class.

An Herbalist is not a Fighter's alternative — a Fighter *is* an Herbalist, if they forage.
The track grants no BAB, saves, hit dice or class skills, and levels on what the character
does rather than on their experience total, which is why none of it lives in
`tables.CLASSES`.

The mastery numbers are the author's, with the bottom two thresholds raised. Their own
pacing targets and their own award table disagreed: a qualifying level-1 craft is worth
about 5 MP, so 10 MP to reach level 2 is two crafts against a stated target of 3-5, and
25 MP to reach level 3 is under three against a target of 6-8. The top two were already
right and are untouched.
"""
from __future__ import annotations

import pytest

from rules import worldclass as wc
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import from_dict, load_pc, to_dict


@pytest.fixture
def herbalist():
    return wc.get("herbalist")


@pytest.fixture
def pc():
    return load_pc("fixtures/pc-kesst.json")


@pytest.fixture
def engine(pc):
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    s.add(instantiate("thug", scene=s, name="the thug"))
    return Engine(s, Dice(seed=42))


# --- the track ---------------------------------------------------------------------------

def test_the_herbalist_loads(herbalist):
    assert herbalist.max_level == 5
    assert herbalist.at(1).methods == ["grind", "mix", "brew"]
    assert "alchemical still" in herbalist.at(3).tools


def test_methods_accumulate_rather_than_being_replaced(herbalist):
    """You do not forget how to grind when you learn to distil."""
    assert set(herbalist.unlocked_methods(3)) == {
        "grind", "mix", "brew", "preserve", "extract", "distill", "purify"}
    assert herbalist.unlocked_methods(1) == ["grind", "mix", "brew"]


@pytest.mark.parametrize("written,rank", [
    ("Common / Mundane", 1), ("Uncommon / Volatile", 2), ("Rare / Magical", 3),
    ("Exotic / Planar", 4), ("Legendary / Mythic", 5), ("rare", 3), ("mythic", 5),
])
def test_either_half_of_a_tier_name_is_understood(written, rank):
    """The source writes both halves and a recipe will cite whichever reads better."""
    assert wc.tier_rank(written) == rank


# --- earning mastery ---------------------------------------------------------------------

def test_a_first_craft_pays_more_than_a_repeat(herbalist):
    p = wc.Progress(track="herbalist")
    first = wc.award(herbalist, p, recipe_id="woundwort styptic", tier="common")
    again = wc.award(herbalist, p, recipe_id="woundwort styptic", tier="common")
    assert first["mp"] == 3 and again["mp"] == 1


def test_a_chain_pays_per_stage_beyond_the_first(herbalist):
    """"Multi-Stage Crafting Chain" — a single grind is not a chain. Counting the first
    stage would hand +2 to every craft in the game and re-inflate the whole curve."""
    p = wc.Progress(track="herbalist")
    assert wc.award(herbalist, p, recipe_id="a", tier="common", stages=1)["mp"] == 3
    assert wc.award(herbalist, p, recipe_id="b", tier="common", stages=3)["mp"] == 3 + 4


def test_a_risky_harvest_is_worth_two(herbalist):
    p = wc.Progress(track="herbalist", level=2)
    got = wc.award(herbalist, p, recipe_id="trollheart tonic", tier="uncommon",
                   risky=True, stages=2)
    assert got["mp"] == 3 + 2 + 2


def test_the_stated_pacing_is_what_the_thresholds_produce(herbalist):
    """The check that decided the numbers. A qualifying craft at each tier, repeated
    until the level turns over, must land inside the author's own stated craft counts."""
    p = wc.Progress(track="herbalist")
    crafts = 0
    while p.level == 1:
        crafts += 1
        wc.award(herbalist, p, recipe_id=f"tea-{crafts}", tier="common", stages=2)
    assert 3 <= crafts <= 5                       # author's target for level 2

    crafts = 0
    while p.level == 2:
        crafts += 1
        wc.award(herbalist, p, recipe_id=f"tincture-{crafts}", tier="uncommon",
                 risky=True, stages=3)
    assert 6 <= crafts <= 8                       # author's target for level 3

    crafts = 0
    while p.level == 3:
        crafts += 1
        wc.award(herbalist, p, recipe_id=f"elixir-{crafts}", tier="rare",
                 risky=True, stages=4)
    assert 4 <= crafts <= 5                       # author's target for level 4


def test_trivial_recipes_stop_paying(herbalist):
    """"Once an Herbalist reaches Level 3, Level 1 recipes no longer grant Mastery
    Points." Generalised to a gap so it keeps working at 4 and 5 without a new special
    case at each level."""
    p = wc.Progress(track="herbalist", level=3)
    assert wc.award(herbalist, p, recipe_id="basic tea", tier="common")["mp"] == 0

    p2 = wc.Progress(track="herbalist", level=2)
    assert wc.award(herbalist, p2, recipe_id="basic tea", tier="common")["mp"] == 3


def test_a_trivial_craft_still_counts_as_known(herbalist):
    """It earns nothing and is still something you have made — otherwise it would pay the
    first-time bonus again later."""
    p = wc.Progress(track="herbalist", level=3)
    wc.award(herbalist, p, recipe_id="basic tea", tier="common")
    assert p.knows("basic tea")


def test_a_factory_line_stops_paying(herbalist):
    """The stated purpose of the award table is to stop players "spamming 100 basic
    health potions". Diminishing returns alone do not, because they only begin at level 3
    — at level 1 a production run of twenty-five teas is still a level."""
    p = wc.Progress(track="herbalist")
    earned = [wc.award(herbalist, p, recipe_id="same tea", tier="common")["mp"]
              for _ in range(20)]
    assert earned[:5] == [3, 1, 1, 0, 0]
    assert sum(earned) < herbalist.to_next(1)
    assert p.level == 1


def test_failure_teaches_something_the_first_time_and_not_the_fifth(herbalist):
    """"Ensures failure still feels like learning." Without a limit, deliberate failure
    on cheap ingredients is free progress."""
    p = wc.Progress(track="herbalist")
    got = [wc.award(herbalist, p, recipe_id="hard one", tier="common",
                    success=False)["mp"] for _ in range(5)]
    assert got == [1, 1, 0, 0, 0]


def test_a_failed_craft_is_not_a_recipe_you_know(herbalist):
    p = wc.Progress(track="herbalist")
    wc.award(herbalist, p, recipe_id="hard one", tier="common", success=False)
    assert not p.knows("hard one")
    assert wc.award(herbalist, p, recipe_id="hard one", tier="common")["mp"] == 3


# --- levelling ----------------------------------------------------------------------------

def test_mastery_is_spent_on_the_level_not_kept(herbalist):
    p = wc.Progress(track="herbalist", mp=24)
    got = wc.award(herbalist, p, recipe_id="one more", tier="common", stages=2)
    assert got["levelled"] == [2]
    assert p.mp == 24 + 5 - 25


def test_the_top_level_waits_on_a_deed_as_well_as_points(herbalist):
    """"Milestone-locked (Requires crafting a legendary catalyst)." The points are kept
    rather than burned, so the level lands the moment the deed is done."""
    p = wc.Progress(track="herbalist", level=4, mp=500)
    wc.award(herbalist, p, recipe_id="something", tier="exotic")
    assert p.level == 4
    assert p.mp >= 100

    wc.award(herbalist, p, recipe_id="xian tao brew", tier="legendary",
             milestone="legendary-catalyst")
    # At least 5: the deed opens the gate, and banked points now carry on past it
    # rather than piling up against a ceiling. The gate itself is the assertion above.
    assert p.level >= 5


def test_the_track_goes_on_past_its_written_table(herbalist):
    """Reversed on request: "uncap the level and dont increase the points required to
    level beyond 100". The unlocks stop at 5 because that is where the track's own
    table stops; the level does not, and everything scaling with it goes on scaling.
    """
    p = wc.Progress(track="herbalist", level=5, mp=9999)
    wc.award(herbalist, p, recipe_id="another", tier="legendary")
    assert p.level > 5
    assert herbalist.to_next(5) is not None


def test_the_price_of_a_level_stops_climbing(herbalist):
    """"dont increase the points required to level beyond 100" — past the written
    thresholds the cost is the last one, unchanged."""
    top = herbalist.thresholds[-1]
    assert herbalist.to_next(herbalist.max_level) == top
    assert herbalist.to_next(herbalist.max_level + 40) == top


def test_a_track_that_wants_a_ceiling_still_gets_one(herbalist):
    """Uncapped by default, not by force: `capped` is how a track says otherwise."""
    import dataclasses

    walled = dataclasses.replace(herbalist, capped=True)
    assert walled.to_next(walled.max_level) is None


# --- through the engine --------------------------------------------------------------------

def test_a_character_begins_a_track_by_doing_it(engine, pc):
    """Begun rather than chosen: the class levels by use, so anyone who forages is an
    Herbalist. Choosing it at creation is a head start with the tools, not permission."""
    assert not pc.world_classes
    engine.run(engine.validate([
        {"op": "craft", "actor": "pc", "because": "she has time and a mortar",
         "params": {"track": "herbalist", "recipe": "woundwort styptic",
                    "tier": "common", "stages": 1}},
    ]))
    assert pc.track("herbalist").level == 1
    assert pc.track("herbalist").mp == 3


def test_the_engine_narrates_what_a_new_level_unlocks(engine, pc):
    pc.track("herbalist").mp = 24
    res = engine.run(engine.validate([
        {"op": "craft", "actor": "pc",
         "params": {"track": "herbalist", "recipe": "aaron's rod salve",
                    "tier": "common", "stages": 2}},
    ]))
    tell = res.outcomes[0].tell
    assert "Herbalist 2" in tell and "extract" in tell


def test_work_above_your_level_is_refused_with_the_level_that_allows_it(engine):
    """Scoring it instead would let a track level itself: mastery for work the character
    has neither the tools nor the methods to attempt."""
    with pytest.raises(IntentError, match="Reach Herbalist 3"):
        engine.validate([{"op": "craft", "actor": "pc",
                          "params": {"track": "herbalist", "recipe": "selpeme tincture",
                                     "tier": "rare"}}])


def test_an_unknown_track_is_refused_with_the_ones_that_exist(engine):
    # "blacksmith" was the unknown example here until the blacksmithing world class
    # arrived and made it real — the refusal needs a track that stays fictional.
    with pytest.raises(IntentError, match="herbalist"):
        engine.validate([{"op": "craft", "actor": "pc",
                          "params": {"track": "basket weaver", "recipe": "a basket"}}])


def test_progress_survives_a_save(pc):
    p = pc.track("herbalist")
    p.level, p.mp = 3, 12
    p.crafted["woundwort styptic"] = 2
    p.milestones.append("legendary-catalyst")

    back = from_dict(to_dict(pc))
    got = back.world_classes["herbalist"]
    assert got.level == 3 and got.mp == 12
    assert got.crafted["woundwort styptic"] == 2
    assert got.milestones == ["legendary-catalyst"]
