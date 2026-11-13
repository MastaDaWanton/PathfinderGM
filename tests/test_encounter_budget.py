"""The one encounter budget (`rules/encounter_budget.py`): the party's APL, the whole
encounter priced by its total XP, and a mix that is mostly average.

The measured defect: a lone level-1 PC died to two CR 1 guards (2026-11-13). Each guard was
inside the old per-creature window (CR level-2 .. level+1), but together they are 800 XP, a
CR 3 encounter (Core Rulebook p.397, Tables 12-1 and 12-2), against an APL of -1 under the
owner's ruling (a lone PC counts two down): APL+4, past epic.
"""
from __future__ import annotations

import pathlib
import random
import re
from collections import Counter

import pytest

from rules import bestiary, encounter_budget as eb, gathering, npcs, ontheway, openings, xp
from rules.dice import Dice


class _Fixed:
    """Dice that answer a written list in order."""

    def __init__(self, *faces):
        self.faces = list(faces)

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        return Dice(seed=1).given(self.faces.pop(0), modifiers, label, notation)


# --- the measured case ---------------------------------------------------------------------

def test_two_cr1_guards_against_a_lone_first_level_pc_is_never_built():
    """800 XP is a CR 3 encounter and a lone level-1 PC is APL -1: four over, epic+1. No
    difficulty any picker can roll spends that much, and above all not "average" (135 XP,
    the CR 1/3 rung)."""
    party = eb.apl([1])
    assert party == -1
    assert eb.encounter_index(2 * xp.CR_AWARD[1]) == 3
    assert eb.budget(party) == 135
    for kind, bands in eb.MIX.items():
        for name, _ in bands:
            assert not eb.fits(800, party + eb.TIERS[name]), (kind, name)
    assert eb.most_of(xp.CR_AWARD[1], 2, party, 50, kind="wandering") == 1


def test_the_watch_comes_for_a_lone_first_level_pc_one_at_a_time(monkeypatch):
    """The street's patrol is the band that turns into the fight when the name is wanted.
    With the watch answering as the CR 1 Guard, two of them at a lone first-level PC was the
    death; at every difficulty roll the patrol is now one, and the tell says one."""
    guard = bestiary.lookup("guard")
    assert guard and int(guard.get("xp") or 0) == 400
    monkeypatch.setattr(npcs, "choose", lambda words, level, **kw: {"id": "guard",
                                                                     "cr_value": 1.0})
    for hard in range(1, 101):
        met = ontheway.street(_Fixed(1, 80, hard), level=1)
        assert met.kind == "patrol" and met.count == 1, hard
    said = ontheway.describe(met, "the square", law="wanted")
    assert "one of them alone" in said and "two of them" not in said
    # A party of four second-level characters (APL 2, 600 XP average) still meets two.
    assert ontheway.street(_Fixed(1, 80, 50), level=2, apl=2).count == 1
    assert ontheway.street(_Fixed(1, 80, 95), level=2, apl=2).count == 2


# --- APL --------------------------------------------------------------------------------------

@pytest.mark.parametrize("levels, want", [
    ([1], -1), ([5], 3),                 # alone: two down (the owner's ruling)
    ([3, 3], 2), ([3, 3, 3], 2),         # three or fewer: one down (CRB Step 1)
    ([4] * 4, 4), ([4] * 5, 4),          # four or five: as they are
    ([4] * 6, 5), ([4] * 8, 5),          # six or more: one up
    ([1, 2], 1),                         # 1.5 rounds to the nearest, 2 (Step 1), then -1
])
def test_apl_by_party_size(levels, want):
    assert eb.apl(levels) == want


def test_apl_below_one_walks_the_books_progression():
    """CRB, Adding NPCs: below 1 a CR drops one step on 1/2, 1/3, 1/4, 1/6, 1/8."""
    assert [eb.rung(i) for i in (1, 0, -1, -2, -3, -4, -9)] == \
        [1.0, 0.5, 0.333, 0.25, 0.167, 0.125, 0.125]
    assert [eb.budget(i) for i in (2, 1, 0, -1)] == [600, 400, 200, 135]


def test_the_party_is_the_pc_and_the_companions_actually_with_them():
    """A companion bonded by the `company` op counts; a bought horse, a caravan's people and
    an animal companion carry the same travels-with-you tag and do not."""
    from rules.activeeffect import ActiveEffect
    from rules.bestiary import instantiate
    from rules.engine import Engine, Scene
    from rules import states
    from rules.sheet import load_pc

    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    pc.level = 3
    s.add(pc)
    e = Engine(s, Dice(seed=1))
    assert eb.party_levels(s) == [3] and eb.party_apl(s) == 1
    friend = instantiate("thug", scene=s)
    friend.level = 3
    s.add(friend)
    e._travels_with_you(friend)
    horse = instantiate("thug", scene=s, name="horse")
    s.add(horse)
    horse.apply_effect(ActiveEffect(
        name="travels with you", kind="bond", key="company:h:travels", source="company:h",
        origin="bought:pc", duration="until-dismissed", tags=(states.TRAVELS_WITH_YOU,)))
    hand = instantiate("thug", scene=s, name="teamster")
    s.add(hand)
    hand.apply_effect(ActiveEffect(
        name="on the road", kind="bond", key="job:1", source="job:1", origin="job:1",
        duration="until-dismissed", tags=(states.TRAVELS_WITH_YOU,)))
    assert sorted(eb.party_levels(s)) == [3, 3]
    assert eb.party_apl(s) == 2
    assert eb.party_levels(s, pc_level=1) == [1, 3]


# --- the mix ------------------------------------------------------------------------------------

@pytest.mark.parametrize("party", [-1, 1, 4])
def test_the_mix_over_many_seeds_is_mostly_average(party):
    """The owner's ruling: mostly average, harder only sometimes, nothing epic. Over 1,000
    seeded road draws in the forest the landed difficulty is average at least 60% of the
    time, never hard or epic, and every draw's total XP spends exactly its tier's budget."""
    rows = [r for r in bestiary.search(biome="forest", cr_max=eb.highest_cr(party),
                                       stated=True, limit=5000)
            if r.get("cr_value") is not None]
    landed = Counter()
    for seed in range(1000):
        rng = random.Random(seed)
        got = eb.choose(rows, party, rng.randint(1, 100), rng.randrange)
        assert got is not None
        assert eb.fits(got.xp, party + eb.TIERS[got.tier]), got
        assert got.count <= eb.MOST
        landed[got.tier] += 1
    assert landed["average"] >= 600, landed
    assert not landed["hard"] and not landed["epic"], landed


def test_a_guard_may_be_hard_and_nothing_is_ever_epic():
    seen = {kind: {eb.tier(r, kind) for r in range(1, 101)} for kind in eb.MIX}
    assert seen["wandering"] == {"easy", "average", "challenging"}
    assert seen["guarded"] == {"average", "challenging", "hard"}
    assert "epic" not in set().union(*seen.values())
    for kind in eb.MIX:
        assert sum(eb.tier(r, kind) == "average" for r in range(1, 101)) >= 50, kind


def test_nothing_fits_steps_easier_never_harder():
    """Ground that stocks only a creature too big for the rolled difficulty is quiet."""
    wyvern = bestiary.imported()["wyvern"]          # CR 6, 2,400 XP
    assert eb.choose([wyvern], eb.apl([1]), 95, lambda n: 0) is None
    got = eb.choose([wyvern], 6, 95, lambda n: 0)    # challenging asked, average landed
    assert got is not None and got.rolled == "challenging" and got.tier == "average"


# --- every picker goes through the shared function -----------------------------------------------

def test_every_picker_spends_the_shared_budget(monkeypatch):
    calls = []
    real = eb.choose

    def spy(*a, **k):
        calls.append(k.get("kind", "wandering"))
        return real(*a, **k)

    monkeypatch.setattr(eb, "choose", spy)
    assert ontheway.road(_Fixed(5, 10, 50, 1), hours=6, biome="forest", level=3)
    assert ontheway.night(_Fixed(1, 50, 1), 8, "forest", 3)
    assert gathering.creature_for("forest", 3, Dice(seed=2)) is not None
    assert gathering.creature_for("forest", 3, Dice(seed=2), guarding=True) is not None
    assert openings.foes_from_the_land("forest", 3, 2, random.Random(1)) is not None
    assert calls == ["wandering", "wandering", "wandering", "guarded", "opening"]

    counted = []
    real_most = eb.most_of
    monkeypatch.setattr(eb, "most_of", lambda *a, **k: counted.append(k["kind"])
                        or real_most(*a, **k))
    openings._within_budget("guard", 3, eb.apl([1]), random.Random(1))
    ontheway.street(_Fixed(1, 80, 50), level=1)
    assert counted == ["opening", "guarded"]
    assert openings._within_budget("guard", 3, eb.apl([1]), random.Random(1)) == 1


def test_no_picker_keeps_a_per_creature_window_of_its_own():
    """The defect was a per-creature CR window (`cr_min`/`cr_max` around the level) in four
    copies. Only the bestiary's own search and this budget may name one now."""
    root = pathlib.Path(__file__).resolve().parent.parent / "rules"
    offenders = []
    for path in root.glob("*.py"):
        if path.name in ("bestiary.py", "encounter_budget.py"):
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"bestiary\.search\([^)]*cr_min", text, re.S) or \
                re.search(r"^(?:BELOW|ABOVE|GUARD_ABOVE)\b[^\n]*=", text, re.M) or \
                re.search(r"cr_max=(?!eb\.highest_cr)", text):
            offenders.append(path.name)
    assert not offenders


# --- the tells say how many -----------------------------------------------------------------------

def test_a_group_on_the_road_is_told_as_a_group():
    wolf = bestiary.imported()["wolf"]
    two = ontheway.Meeting(kind="creature", roll=10, creature=wolf, template="wolf",
                           count=2, aggressive=True)
    assert "two wolves are on it, and they have seen you" in ontheway.describe(two)
    assert "two wolves are near the way; they let you pass" in ontheway.passing(two).lower()
    one = ontheway.Meeting(kind="creature", roll=10, creature=wolf, template="wolf",
                           count=1, aggressive=True)
    assert "a wolf is on it, and it has seen you" in ontheway.describe(one)
