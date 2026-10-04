"""The Herbalist's endless levels, perks, step mastery and the migration of old saves.

The owner's herbalism ruling of 2026-10-02 (docs/herbalism-revamp-plan.md §4, §14): three
unlock levels, then levels that never stop, each banking two perk picks from potency,
duration, quality and yield, the same one twice allowed. The bench pays mastery per step
rather than per recipe. An old Herbalist 4 or 5 keeps its level, which now *is* its bank
of picks.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from rules import worldclass as wc
from rules.sheet import from_dict, load_pc, to_dict

# Blacksmith left this list with its own revamp (docs/blacksmithing-revamp-plan.md §4): it
# is three levels then endless now, pinned by tests/test_forge_bench.py.
OTHERS = ("alchemist", "leatherworker", "enchanter")


@pytest.fixture
def herbalist():
    return wc.get("herbalist")


def _at(level: int, **kw) -> wc.Progress:
    return wc.Progress(track="herbalist", level=level, schema=wc.HERBALISM_SCHEMA, **kw)


# --- levels past 3 never stop --------------------------------------------------------------

def test_levels_past_3_never_stop_and_climb_gently(herbalist):
    """The five-level table priced every unwritten level at a flat 100 (`top_cost`). The
    ruling's curve is 50 + 10 x (level - 3): leaving 3 costs 50, leaving 4 costs 60. A
    track that lost its `endless` block would fall back to the flat price and charge
    double for level 4 without any test noticing, so the curve is pinned to level 60."""
    assert herbalist.max_level == 3
    assert [herbalist.to_next(n) for n in (1, 2)] == [25, 65]
    for level in range(3, 61):
        assert herbalist.to_next(level) == 50 + 10 * (level - 3), level

    p = _at(3, mp=10_000)
    wc.award_bonus(herbalist, p, why="test", mp=0)
    assert p.level > 30                                    # spent, not stopped


def test_the_unlock_table_reads_cleanly_at_level_9(herbalist):
    """`Track.at` clamps to the last written row, so an endless level reads level 3's
    legendary ceiling and Flawless quality rather than raising or falling back to level 1.
    Every method is still known: methods do not expire past the table."""
    row = herbalist.at(9)
    assert row.level == 3
    assert wc.tier_rank(row.max_tier) == 5
    assert row.ceiling == 4
    assert herbalist.unlocked_methods(9) == [
        "grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep",
        "neutralize"]


def test_the_retired_methods_are_gone_from_every_level(herbalist):
    """Distill, preserve, purify, refine and catalyst crafting were removed by the ruling.
    A copy left in a level row or in `method_descriptions` would keep offering the bench a
    method no engine step can perform."""
    retired = {"distill", "preserve", "purify", "refine", "catalyst crafting"}
    assert not retired & set(herbalist.unlocked_methods(99))
    raw = json.loads(Path("content/world-classes/herbalist.json").read_text("utf-8"))
    assert set(raw["method_descriptions"]) == set(herbalist.unlocked_methods(3))
    assert "legendary-catalyst" not in json.dumps(
        {k: v for k, v in raw.items() if not k.startswith("_")})


def test_endless_levels_are_declared_by_the_track_not_named_in_code():
    """The endless curve, the picks per level and the perk sizes come from the track's
    JSON. A track built from a dict with its own `endless` block gets endless levels with
    no code change, and the module's code names the Herbalist exactly once, in the
    migration table, because a migration is by definition one track's own history."""
    t = wc.from_dict({"id": "weaver", "name": "Weaver", "thresholds": [10],
                      "levels": [{"level": 1, "methods": ["twine"], "ceiling": 1},
                                 {"level": 2, "methods": ["loom"], "ceiling": 2}],
                      "endless": {"_note": "ignored", "base": 7, "step": 3,
                                  "picks_per_level": 1, "perks": {"quality": 1}}})
    assert [t.to_next(n) for n in (1, 2, 3, 4)] == [10, 7, 10, 13]
    assert "_note" not in t.endless
    p = wc.Progress(track="weaver", level=4)
    assert wc._banked(t, p) == 2
    assert wc._ceiling(t, p) == 2

    source = Path("rules/worldclass.py").read_text(encoding="utf-8")
    source = re.sub(r'"""(?:.|\n)*?"""', "", source)
    code = "\n".join(re.sub(r"#.*$", "", line) for line in source.splitlines())
    assert code.count('"herbalist"') == 1, "a track id hard-coded outside MIGRATIONS"


# --- perks ----------------------------------------------------------------------------------

@pytest.mark.parametrize("level,banked", [(1, 0), (3, 0), (4, 2), (5, 4), (9, 12)])
def test_picks_bank_two_per_endless_level(level, banked):
    """Nothing is auto-picked (plan §4.2): picks wait in the bank until the player
    chooses, counted from the level so the bank can never drift from it."""
    assert wc.perk_picks_banked(_at(level)) == banked


def test_the_same_perk_twice_is_allowed(herbalist):
    """"the same one twice is allowed" (owner, 2026-10-02). A picker that deduplicated
    would silently turn quality, quality into one Quality perk."""
    p = _at(4)
    got = wc.pick_perks(herbalist, p, ["quality", "quality"])
    assert p.perks == {"quality": 2}
    assert got["picks_banked"] == 0
    assert got["ceiling"] == 6 and got["ceiling_name"] == "Flawless +2"


def test_over_picking_is_refused_and_takes_nothing(herbalist):
    """Three picks against a bank of two must not spend two and refuse the third: all are
    checked before any is taken, so a refusal leaves the bank exactly as it was."""
    p = _at(4)
    with pytest.raises(ValueError, match="2 perk picks banked and chose 3"):
        wc.pick_perks(herbalist, p, ["potency", "duration", "yield"])
    assert p.perks == {}
    with pytest.raises(ValueError, match="no perk called 'luck'"):
        wc.pick_perks(herbalist, p, ["potency", "luck"])
    assert p.perks == {}
    with pytest.raises(ValueError, match="no perk picks banked"):
        wc.pick_perks(herbalist, _at(3), ["potency"])
    with pytest.raises(ValueError, match="at least one"):
        wc.pick_perks(herbalist, p, [])


def test_picks_can_be_spent_in_parts(herbalist):
    p = _at(5)
    wc.pick_perks(herbalist, p, ["potency"])
    assert wc.perk_picks_banked(p) == 3
    wc.pick_perks(herbalist, p, ["potency", "duration", "yield"])
    assert wc.perk_picks_banked(p) == 0
    assert p.perks == {"potency": 2, "duration": 1, "yield": 1}


def test_perk_multipliers_are_the_accepted_sizes():
    """+5% potency, +10% duration, +5% yield chance per pick (plan §4.2). Rounded:
    1 + 0.05 x 3 is 1.1500000000000001 in floating point, and that reached the page."""
    p = _at(9, perks={"potency": 3, "duration": 2, "yield": 1})
    assert wc.perk_multipliers(p) == {"potency": 1.15, "duration": 1.2,
                                      "yield_chance": 0.05}
    assert wc.perk_multipliers(_at(1)) == {"potency": 1.0, "duration": 1.0,
                                           "yield_chance": 0.0}


# --- the quality ceiling --------------------------------------------------------------------

@pytest.mark.parametrize("level,quality,ceiling,name", [
    (1, 0, 2, "Fine"), (2, 0, 3, "Superior"), (3, 0, 4, "Flawless"),
    (9, 0, 4, "Flawless"), (9, 1, 5, "Flawless +1"), (9, 8, 12, "Flawless +8"),
])
def test_the_ceiling_by_level_and_quality_perk(level, quality, ceiling, name):
    """Plan §4.3: your level raises the ceiling and each Quality perk adds one past
    Flawless. An endless level by itself must not raise it, or every level would be a
    free Quality perk."""
    p = _at(level, perks={"quality": quality} if quality else {})
    assert wc.ceiling_index(p) == ceiling
    assert wc.quality_name(ceiling) == name


def test_the_track_summary_is_the_contract_object(herbalist):
    """Contracts §3.1: the bench state's `track`. `to_next` is {need, have}, the price
    and the bank, not `_remaining`'s {need-left, of}; a page reading one as the other
    draws a bar that is full when it is empty."""
    got = wc.track_summary(herbalist, _at(2, mp=30))
    assert got == {"id": "herbalist", "level": 2, "mp": 30,
                   "to_next": {"need": 65, "have": 30}, "ceiling": 3,
                   "ceiling_name": "Superior", "perks": {}, "picks_banked": 0,
                   "next_rung": "Flawless at Herbalist 3"}
    assert wc.track_summary(herbalist, _at(1))["next_rung"] == "Superior at Herbalist 2"
    later = wc.track_summary(herbalist, _at(6, perks={"quality": 1}))
    assert later["next_rung"] == "Flawless +2 at your next Quality perk"
    assert later["picks_banked"] == 5


# --- mastery from the bench -----------------------------------------------------------------

def test_a_step_pays_one_plus_rarity_plus_quality(herbalist):
    """Plan §4.4: 1 a step, +1 per rarity band above common, +1 at Superior, +2 at
    Flawless or higher. Itemised like `award`, so the player can check the sum."""
    p = _at(1)
    got = wc.award_step(herbalist, p, method="grind", ingredient_id="comfrey",
                        rarity_rank=3, quality_index=5, name="Comfrey")
    assert got["reasons"] == [{"why": "Grind, Comfrey", "mp": 1},
                              {"why": "rare material", "mp": 2},
                              {"why": "Flawless +1 work", "mp": 2}]
    assert got["mp"] == 5 and p.mp == 5
    plain = wc.award_step(herbalist, p, method="grind", ingredient_id="yarrow",
                          rarity_rank=1, quality_index=2)
    assert plain["mp"] == 1 and plain["reasons"][0]["why"] == "Grind, yarrow"
    sup = wc.award_step(herbalist, p, method="mix", ingredient_id="yarrow",
                        rarity_rank=1, quality_index=3)
    assert sup["mp"] == 2


def test_the_repeat_limit_is_per_method_and_ingredient(herbalist):
    """The anti-grind rule (`REPEAT_LIMIT` 3) keyed on (method, ingredient), not the old
    recipe id: a production line of one grind stops paying after three, and the same herb
    under a new method is new work. Without the key, steps would never repeat at all and
    the limit would be dead code."""
    p = _at(1)
    paid = [wc.award_step(herbalist, p, method="grind", ingredient_id="comfrey",
                          rarity_rank=1, quality_index=4)["mp"] for _ in range(5)]
    assert paid == [3, 3, 3, 0, 0]
    assert p.crafted["grind:comfrey"] == 5
    assert wc.award_step(herbalist, p, method="brew", ingredient_id="comfrey",
                         rarity_rank=1, quality_index=0)["mp"] == 1


def test_a_mishap_teaches_twice_then_nothing(herbalist):
    """`MISHAP_LIMIT` 2 per (method, ingredient): deliberate failure on a cheap herb is
    not free progress."""
    p = _at(1)
    got = [wc.award_step(herbalist, p, method="grind", ingredient_id="comfrey",
                         rarity_rank=1, quality_index=0, success=False)["mp"]
           for _ in range(4)]
    assert got == [1, 1, 0, 0]
    assert "grind:comfrey" not in p.crafted


def test_no_step_is_beneath_an_endless_herbalist(herbalist):
    """`TRIVIAL_GAP` is dropped for the step path: past level 3 the levels no longer
    climb in rarity bands. Under `award` an Herbalist 9 grinding common material earns 0,
    which would make every common herb worthless to the levels the ruling made endless."""
    p = _at(9)
    assert wc.award(herbalist, wc.Progress(track="herbalist", level=9),
                    recipe_id="tea", tier="common")["mp"] == 0
    assert wc.award_step(herbalist, p, method="grind", ingredient_id="comfrey",
                         rarity_rank=1, quality_index=0)["mp"] == 1


def test_firsts_and_manuals_through_award_bonus(herbalist):
    p = _at(1, mp=20)
    got = wc.award_bonus(herbalist, p, why="first poultice", mp=wc.FIRST_MP)
    assert got["reasons"] == [{"why": "first poultice", "mp": 3}]
    got = wc.award_bonus(herbalist, p, why="read a herbal", mp=wc.MANUAL_MP)
    assert got["levelled"] == [2] and p.mp == 3
    assert wc.award_bonus(herbalist, p, why="nothing", mp=0)["reasons"] == []


# --- migration ------------------------------------------------------------------------------

@pytest.mark.parametrize("old,banked", [(4, 2), (5, 4), (7, 8)])
def test_an_old_high_herbalist_becomes_endless_levels_with_picks(old, banked):
    """Plan §14: Herbalist 4 becomes 3 plus one pick-pair, Herbalist 5 becomes 3 plus two,
    and the uncapped 6+ the five-level table allowed follows the same rule. Banked
    mastery is kept to the point; the picker opens on the first visit and nothing is
    spent for the player."""
    p = wc.Progress(track="herbalist", level=old, mp=37,
                    milestones=["legendary-catalyst"])
    assert wc.migrate_herbalist(p) is True
    assert p.schema == wc.HERBALISM_SCHEMA
    assert p.level == old and p.mp == 37 and p.perks == {}
    assert wc.perk_picks_banked(p) == banked


def test_migration_runs_once(herbalist):
    """Load-time migration runs on every load, so it must be idempotent by its stamp. The
    defect it guards: a second run that re-banked picks would hand out perks on every
    load, and one that reset perks would take back what the player chose."""
    p = wc.Progress(track="herbalist", level=5, mp=12)
    assert wc.migrate(p) is True
    wc.pick_perks(herbalist, p, ["quality", "potency"])
    before = (p.level, p.mp, dict(p.perks), p.schema)
    assert wc.migrate(p) is False
    assert wc.migrate_herbalist(p) is False
    assert (p.level, p.mp, dict(p.perks), p.schema) == before
    assert wc.perk_picks_banked(p) == 2


def test_a_save_loads_migrated_and_keeps_its_mastery():
    """The real load path (`sheet._progress`), not the function alone: an old save with
    Herbalist 5 and 88 MP comes back stamped, with two pick-pairs banked and every point
    kept, and the other tracks on the same character are not stamped."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.track("herbalist").level, pc.track("herbalist").mp = 5, 88
    pc.track("blacksmith").level = 5
    d = to_dict(pc)
    assert "schema" not in d["world_classes"]["herbalist"]      # a pre-revamp save

    back = from_dict(d)
    herb = back.world_classes["herbalist"]
    assert (herb.level, herb.mp, herb.schema) == (5, 88, wc.HERBALISM_SCHEMA)
    assert wc.perk_picks_banked(herb) == 4
    # The blacksmith migrates on the same load now (the forge revamp's `migrate_blacksmith`).
    assert back.world_classes["blacksmith"].schema == wc.BLACKSMITH_SCHEMA


def test_a_settled_save_round_trips_byte_for_byte():
    """A progress with no perks writes no `perks` key, and a perk held at 0 writes none
    either: the scaffold wrote `"perks": {}` for {"quality": 0}, a key the save before
    never had. Once stamped, load and save are the identity on the bytes."""
    pc = load_pc("fixtures/pc-kesst.json")
    p = pc.track("herbalist")
    p.level, p.mp, p.schema = 4, 9, wc.HERBALISM_SCHEMA
    p.perks = {"quality": 0}
    first = json.dumps(to_dict(pc))
    assert '"perks"' not in json.dumps(to_dict(pc)["world_classes"])
    again = json.dumps(to_dict(from_dict(json.loads(first))))
    assert again == first

    p.perks = {"quality": 2}
    p.level = 5
    first = json.dumps(to_dict(pc))
    assert json.dumps(to_dict(from_dict(json.loads(first)))) == first


# --- everyone else -------------------------------------------------------------------------

@pytest.mark.parametrize("track_id", OTHERS)
def test_the_other_world_classes_are_unaffected(track_id):
    """The endless block is the Herbalist's alone. Before it was declared per track, the
    scaffold counted perk picks for any track past level 3, so an Alchemist 7 would have
    been offered eight Herbalist perks. Each other track keeps its five-level table, its
    flat price past it, its per-recipe award and no migration."""
    t = wc.get(track_id)
    assert t.max_level == 5 and not t.endless
    assert t.to_next(9) == t.top_cost == t.thresholds[-1]
    p = wc.Progress(track=track_id, level=9)
    assert wc.perk_picks_banked(p) == 0
    assert wc.migrate(p) is False and p.schema == 0
    fresh = wc.Progress(track=track_id)
    assert wc.award(t, fresh, recipe_id="x", tier="common")["mp"] == 3
