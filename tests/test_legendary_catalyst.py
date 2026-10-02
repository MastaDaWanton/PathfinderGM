"""The top of the Herbalist track, and why nobody could ever reach it.

The report was that "legendary catalysts are generally unattainable". Measured against
the shipped content, they were not merely rare — they were impossible, for four separate
reasons stacked on the same door:

  1. The gate was circular. Herbalist 5 waited on the deed `legendary-catalyst`, but
     `catalyst crafting` was a Level 5 method and legendary was Level 5 material. Brute
     forced over every method permutation an Herbalist 1-4 knew against all four
     legendary ingredients: 0 legal chains. The deed needed the level it was gating.

  2. The bench never recorded a deed. `craft_do` sent no `milestone` param at all, so
     even a perfect legendary craft left the level locked for good.

  3. `crafting.preview` and `engine._check_craft` held two copies of the tier-ceiling
     rule and disagreed. Concentration is the one craft whose output is deliberately
     rarer than its input; `crafting` checked the input and let it climb, the engine
     checked the output and refused. /api/craft/preview answered 200 with a real
     percentage and /api/craft/do answered 400 on the identical chain.

  4. `foraging.table_for` laid its rows down commonest-first and stopped when the d100
     ran out, which deleted the *rarest* end. Forest fielded 105 candidates, kept 95,
     and lost both of its exotic herbs and six of its seven rare ones while keeping all
     88 commons: 0% of the richest biome's table was rank 3 or better.

**Retired 2026-10-02.** The owner's herbalism ruling removed catalyst crafting, distill,
the old levels 4 and 5, the `legendary-catalyst` milestone and its deed
(docs/herbalism-revamp-plan.md §4.1). Legendary material now opens at Herbalist 3, the
last unlock level, and every level after it is an endless level bought with mastery
alone. What each defect becomes:

  1 and 2 are re-pinned as "no Herbalist level waits on a deed" and "every level lands
  on mastery alone", including the owner's own save that sat at 110 of 100 MP.

  3 is re-pinned through the engine against the new level-3 gate. The tests that drove
  it through the old bench's distill chain (/api/craft/preview and /api/craft/do) are
  deleted: distill is gone, and the bench and its concentration ladder belong to the
  bench-engine lane, which re-pins the ceiling against the new bench.

  The old concentration-DC test is deleted for the same reason: it pinned
  `crafting._dc`'s retired ×2 ladder, which the bench-engine lane replaces with the
  n(n+1) curve of plan §5.3 and pins in its own tests.

  4 is untouched: the forage table never depended on the Herbalist's levels.
"""
from __future__ import annotations

import pytest
from django.test import Client, override_settings

from rules import foraging, ingredients
from rules import worldclass as wc
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from tests._places import stand_on


@pytest.fixture
def herbalist():
    return wc.get("herbalist")


@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


def _engine_at(level: int) -> Engine:
    pc = load_pc("fixtures/pc-kesst.json")
    pc.track("herbalist").level = level
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(pc)
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    return Engine(scene, Dice(seed=42))


# --- 1 and 2. the circular gate, and the deed nobody recorded ------------------------------

def test_no_herbalist_level_waits_on_a_deed(herbalist):
    """The circle was a level waiting on a deed that needed that level, and the bench
    never recorded the deed anyway: 0 legal chains of every opening an Herbalist 1-4 had,
    and a level that stayed locked whatever the character did. The ruling removed the
    deed, so the pin is that none comes back: no milestone, no deed, and nothing for
    `deed_done` to name that a bench could fail to record."""
    assert herbalist.milestones == {}
    assert herbalist.deeds == {}
    assert herbalist.deed_done(tier="legendary", success=True) == ""


def test_legendary_material_opens_at_the_last_unlock_level(herbalist):
    """The other half of the circle: legendary material was gated behind the very level
    whose deed demanded it. Now the level that opens legendary is the last written level,
    reached by points, with nothing after it gating anything."""
    opens = next(row.level for row in sorted(herbalist.levels, key=lambda r: r.level)
                 if wc.tier_rank(row.max_tier) >= 5)
    assert opens == 3 == herbalist.max_level
    assert wc.tier_rank(herbalist.at(2).max_tier) == 4      # exotic at best before it
    assert "neutralize" in herbalist.unlocked_methods(3)
    # And it stays open: an endless level reads the last row, never a lower one.
    assert wc.tier_rank(herbalist.at(9).max_tier) == 5


def test_every_level_lands_on_mastery_alone(herbalist):
    """Steps alone, common material, no deed: from Herbalist 1 to 6 with never a moment
    where the banked mastery covers the price and the level does not move. That moment
    was the whole defect, seen in the owner's save as a full bar going nowhere."""
    p = wc.Progress(track="herbalist", schema=wc.HERBALISM_SCHEMA)
    n = 0
    while p.level < 6:
        n += 1
        assert n < 2000, f"stalled at Herbalist {p.level} with {p.mp} MP"
        # A fresh ingredient each time, so the repeat limit never zeroes the step.
        wc.award_step(herbalist, p, method="grind", ingredient_id=f"herb-{n}",
                      rarity_rank=1, quality_index=2)
        need = herbalist.to_next(p.level)
        assert p.mp < need, (p.level, p.mp, need)
    assert p.level == 6


def test_the_save_that_sat_at_110_of_100_now_levels(herbalist):
    """Found in the owner's own live save: Herbalist 4 at 110 MP of a 100 MP threshold,
    `to_next.need` 0, bar drawn full, level not moving, waiting on `legendary-catalyst`.
    Migrated, level 4 is an endless level costing 60 with no deed, so the next step it
    earns lands Herbalist 5 and the rest of the 110 carries over."""
    p = wc.Progress(track="herbalist", level=4, mp=110)
    assert wc.migrate(p)
    assert p.level == 4 and p.mp == 110                      # migration moves nothing
    assert wc._remaining(herbalist, p)["milestone"] is None

    got = wc.award_step(herbalist, p, method="dry", ingredient_id="comfrey",
                        rarity_rank=1, quality_index=2)
    assert got["levelled"] == [5]
    assert p.mp == 110 + 1 - 60


# --- 3. the ceiling, one copy, through the engine -------------------------------------------

def test_a_narrated_legendary_craft_is_refused_below_herbalist_3():
    """The engine's copy of the ceiling against the new gate. A GM narrating "she brews
    something legendary" at Herbalist 2 is refused with the level that allows it, because
    scoring it would let a track level itself on work it has neither the tools nor the
    methods to attempt. Before the ruling the refusal named Herbalist 5."""
    with pytest.raises(IntentError, match="Reach Herbalist 3"):
        _engine_at(2).validate([{"op": "craft", "actor": "pc",
                                 "params": {"track": "herbalist", "recipe": "a grand elixir",
                                            "tier": "legendary"}}])


def test_an_herbalist_3_may_work_legendary_material(herbalist):
    """The way to the top needs no concentration ladder and no monster part now: the one
    forageable legendary herb is within an Herbalist 3's reach, and the engine accepts the
    craft that the old track refused until a level nobody could reach."""
    herb = ingredients.all_ingredients()["tahtoalehti"]
    assert herb.rank == 5 and herb.forageable
    assert herb.rank <= wc.tier_rank(herbalist.at(3).max_tier)
    _engine_at(3).validate([{"op": "craft", "actor": "pc",
                             "params": {"track": "herbalist", "recipe": "tahtoalehti tea",
                                        "tier": "legendary"}}])


# --- 5. the forage table deleted its own rare end -----------------------------------------

def test_a_rich_biome_no_longer_loses_its_rare_end_to_the_hundred(client):
    """Forest fields 105 forageable candidates and a d100 has room for 95 rows. Laying
    them down commonest-first and breaking when the cursor ran out kept all 88 commons
    and deleted the top: 0% of the forest table was rank 3 or better, though 8 such herbs
    grow there — both exotics (Cotsbalm, Orticusp) and six of seven rares. Trimming from
    the common end instead, the same table is 8% rank 3 or better and still 78% common."""
    table = foraging.table_for("forest", rank_ceiling=5)
    assert len(table.rows) == 95

    on_table = {r.ingredient_id for r in table.rows}
    for herb in ("cotsbalm", "orticusp"):
        assert herb in on_table, herb

    share = {rank: sum(r.span for r in table.rows if r.rank == rank)
             for rank in (1, 2, 3, 4, 5)}
    assert share[3] + share[4] + share[5] == 8         # was 0
    assert share[1] == 78                              # still four fifths common


def test_the_table_still_covers_one_to_a_hundred_without_gaps():
    """Trimming candidates must not leave a hole a d100 can land in."""
    for biome in ("forest", "grassland", "tundra", "farmland"):
        table = foraging.table_for(biome, rank_ceiling=5)
        assert table.rows[0].low == 1
        for a, b in zip(table.rows, table.rows[1:]):
            assert b.low == a.high + 1
        assert table.nothing_from == table.rows[-1].high + 1


def test_a_legendary_find_is_still_an_event_not_a_tuesday():
    """None of this made legendary material common, and the numbers should say so
    plainly. Exactly one of the four legendary ingredients can be foraged at all, it is
    tagged to exactly one of fourteen biomes, and it holds exactly one percentage point
    of that biome's table. Simulated over 10,000 Herbalist 5 sessions per biome
    (three rolls each): 307 of 10,000 sessions in farmland turned one up, and 0 of
    130,000 sessions everywhere else."""
    shelf = ingredients.all_ingredients()
    legendary = [i for i in shelf.values() if i.rank == 5]
    forageable = [i for i in legendary if i.forageable]
    assert len(legendary) == 4 and len(forageable) == 1
    assert forageable[0].id == "tahtoalehti"

    with_row = [b for b in ("urban", "grassland", "farmland", "forest", "jungle",
                            "swamp", "hills", "mountain", "desert", "tundra", "coast",
                            "underground", "ruins", "planar")
                if any(r.rank == 5 for r in foraging.table_for(b, 5).rows)]
    assert with_row == ["farmland"]
    assert sum(r.span for r in foraging.table_for("farmland", 5).rows
               if r.rank == 5) == 1

    dice = Dice(seed=11)
    hits = sum(bool(foraging.forage("forest", 5, 5, dice)["found"].get("tahtoalehti"))
               for _ in range(2000))
    assert hits == 0


def test_three_of_the_four_legendary_ingredients_cannot_be_foraged():
    """Behemoth Hide, Kraken Ink and Phoenix Feather are monster parts, so `forageable`
    is False and foraging filters on it. No amount of walking the ground finds one.

    This test used to add that nothing in the app could put them in a satchel at all —
    `Actor.carry` had exactly one caller, `_op_forage`. That is no longer true: the `give`
    op routes anything `ingredients.by_name` recognises into the satchel with a clock on
    it, so a GM handing over a Phoenix Feather works and is now the only way to hold one.
    There is still no harvest or loot op, so killing the phoenix yourself does not.

    None of which blocks the top of the track. Since the 2026-10-02 ruling an Herbalist 3
    works legendary material directly, and the one forageable legendary herb is enough:
    `test_an_herbalist_3_may_work_legendary_material` above.
    """
    shelf = ingredients.all_ingredients()
    stranded = [i for i in shelf.values() if i.rank == 5 and not i.forageable]
    assert sorted(i.id for i in stranded) == ["behemoth-hide", "kraken-ink",
                                              "phoenix-feather"]
    assert all(i.kind == "monster part" for i in stranded)


def test_a_gm_can_hand_over_a_legendary_monster_part(client):
    """The route that opened after this file was written. `give` puts anything the
    ingredient list recognises into the satchel, `forageable` or not — so the three
    legendary monster parts are holdable, even though no legal play finds one."""
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    scene = Scene(location_id="5bbd0c40345f")
    stand_on(scene, "forest")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name="a wandering trader"))
    engine = Engine(scene, Dice(seed=3))
    engine.run(engine.validate([{
        "op": "give", "actor": "c1", "because": "the trader hands it over",
        "params": {"to": "pc", "item": "Phoenix Feather", "count": 1}}]))
    assert scene.pc().inventory.get("phoenix-feather") == 1
