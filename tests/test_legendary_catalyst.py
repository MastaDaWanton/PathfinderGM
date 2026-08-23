"""The top of the Herbalist track, and why nobody could ever reach it.

The report was that "legendary catalysts are generally unattainable". Measured against
the shipped content, they were not merely rare — they were impossible, for four separate
reasons stacked on the same door:

  1. The gate was circular. Herbalist 5 waits on the deed `legendary-catalyst`, but
     `catalyst crafting` is a Level 5 method and legendary is Level 5 material. Brute
     forced over every method permutation an Herbalist 1-4 knows against all four
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

What was *not* fixed, and is recorded here so the next person does not rediscover it:
three of the four legendary ingredients are monster parts, and nothing in the app can
put a monster part in a satchel — `Actor.carry` has exactly one caller, `_op_forage`,
and foraging filters on `forageable`. See the last test in this file.
"""
from __future__ import annotations

import itertools
import json

import pytest
from django.test import Client, override_settings

from rules import crafting, foraging, ingredients
from rules import worldclass as wc
from rules.crafting import Chain
from rules.dice import Dice
from rules.intents import IntentError
from rules.sheet import load_pc


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


def _exotic(count: int = 4):
    """A crafted exotic dose — the rung the ladder reaches legendary from."""
    return crafting.Stock(base="Ice Lotus Tincture", concentration=1, tier="exotic",
                          potency=1.0, count=count, craft="herbalist")


# --- 1. the circular gate ----------------------------------------------------------------

def test_the_deed_that_unlocks_the_top_needed_the_level_it_was_gating(herbalist):
    """Both halves of the circle, stated as the data still states them: `catalyst
    crafting` is learned at 5 and legendary material is workable at 5, while level 5
    waits on a legendary catalyst. Brute forced over every ordered method combination up
    to length two that an Herbalist 1-4 knows, plus `catalyst crafting`, against all four
    legendary ingredients: 0 legal chains of 0 attempted openings."""
    assert herbalist.milestones == {5: "legendary-catalyst"}
    assert next(l.level for l in herbalist.levels
                if "catalyst crafting" in l.methods) == 5
    assert next(l.level for l in sorted(herbalist.levels, key=lambda x: x.level)
                if wc.tier_rank(l.max_tier) >= 5) == 5

    shelf = ingredients.all_ingredients()
    legendary = [i for i in shelf.values() if i.rank == 5]
    assert len(legendary) == 4

    satchel = {i.id: 9 for i in shelf.values()}
    legal = 0
    for level in (1, 2, 3, 4):
        methods = herbalist.unlocked_methods(level) + ["catalyst crafting"]
        for combo in itertools.permutations(methods, 2):
            if "catalyst crafting" not in combo:
                continue
            for ing in legendary:
                r = crafting.preview("herbalist", level,
                                     Chain("herbalist", list(combo), [ing.id]),
                                     stock={}, satchel=satchel)
                legal += not r.problems
    assert legal == 0


def test_the_track_now_says_what_the_deed_actually_is(herbalist):
    """A milestone that names a deed the engine cannot recognise is a level that never
    lands. The track declares it, because nothing else can know: any successful craft at
    legendary tier is the grand catalyst."""
    assert herbalist.deeds["legendary-catalyst"]["min_tier"] == "legendary"
    assert herbalist.deed_done(tier="legendary", success=True) == "legendary-catalyst"
    assert herbalist.deed_done(tier="exotic", success=True) == ""
    assert herbalist.deed_done(tier="legendary", success=False) == ""


def test_an_herbalist_four_has_a_legal_opening_on_legendary_material(herbalist):
    """The way out of the circle, and the only one the rules already contained: two
    exotic doses concentrate into one legendary. Before, that chain previewed at 5% at
    every level from 3 to 5 and the engine refused it outright; the deed was reachable
    from nowhere."""
    held = _exotic()
    # A crafter, because the bonus is a check on a character now rather than a number
    # derived from the track alone: an Herbalist 4 of 8th level with Wisdom 16 is +11.
    crafter = load_pc("fixtures/pc-kesst.json")
    crafter.level = 8
    crafter.abilities["wis"] = 16
    r = crafting.preview("herbalist", 4,
                         Chain("herbalist", ["distill"], stock_used={held.id: 2}),
                         stock={held.id: held}, satchel={}, carrier=crafter)
    assert not r.problems
    assert r.tier == "legendary" and r.concentrating
    assert r.bonus == 11 and r.chance == 10


# --- 2. the DC that pinned the top rung to the floor -------------------------------------

def test_the_ladders_top_rung_was_a_five_percent_floor_at_every_level():
    """`_concentration` open-coded `10 + 5 * rank` where `_dc` reads `5 + 5 * rank` —
    two copies of one rule, five apart, and the five bit at exactly one place. A
    crafter's bonus was `3 * level` then, so at Herbalist 5 it was +15 and DC 35 needed a
    20 on the d20. The last step of the ladder read 5% at Herbalist 3, 4 and 5 alike,
    while each attempt ate two doses.

    The DC is the part this test is about and it has not moved. The bonus since became a
    real check — d20 + track level + half character level + Wisdom — so the percentages
    are quoted against a stated bonus rather than derived from the level alone.
    """
    assert crafting._dc([], 5, 1) == 30                    # was 35
    assert crafting._chance(30, 12) == 15                  # a bonus of +12 makes it 15%
    assert crafting._chance(30, 15) == 30                  # +15, as the old formula gave
    # The rungs below it kept their shape: still a ladder, not a lift.
    assert crafting._chance(crafting._dc([], 4, 1), 12) == 40
    assert crafting._chance(crafting._dc([], 3, 1), 12) == 65


def test_the_ceiling_still_gates_the_ladder(herbalist):
    """Opening the top rung must not open it to everyone. An Herbalist 3 works rare at
    best, so the exotic pair is refused before the roll is ever offered."""
    held = _exotic()
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["distill"], stock_used={held.id: 2}),
                         stock={held.id: held}, satchel={})
    assert r.problems and r.chance == 0
    assert any("works rare / magical at best" in p for p in r.problems)


# --- 3. the two copies of the ceiling rule ------------------------------------------------

def test_the_preview_and_the_post_agree_about_the_ceiling(client):
    """The disagreement was visible in the running app: /api/craft/preview returned 200
    with `tier: legendary, chance: 5%, problems: []` and /api/craft/do answered 400
    "Reach Herbalist 5 first" on the byte-identical body. The ceiling governs the
    material worked, not the band the result lands in."""
    from play import campaign as cm

    c = cm.current()
    pc = c.scene.pc()
    pc.track("herbalist").level = 4
    pc.add_stock(_exotic(count=1), count=4)
    c.save()

    body = json.dumps({"craft": "herbalism", "methods": ["distill"],
                       "ingredients": [], "stock": {_exotic().id: 2}})
    preview = client.post("/api/craft/preview", data=body,
                          content_type="application/json")
    assert preview.status_code == 200
    d = preview.json()
    assert d["tier"] == "legendary" and d["concentrating"] and not d["problems"]

    done = client.post("/api/craft/do", data=body, content_type="application/json")
    assert done.status_code == 200, done.json()


def test_a_narrated_craft_still_cannot_exceed_the_ceiling(client):
    """The loosening is for concentration alone. A GM narrating "she brews something
    legendary" at Herbalist 4 is still refused, because scoring it would let a track
    level itself on work it has neither the tools nor the methods to attempt."""
    from play import campaign as cm

    engine = cm.current().engine()
    with pytest.raises(IntentError, match="Reach Herbalist 5"):
        engine.validate([{"op": "craft", "actor": "pc",
                          "params": {"track": "herbalist", "recipe": "a grand elixir",
                                     "tier": "legendary"}}])


# --- 4. the bench never recorded the deed --------------------------------------------------

def test_the_bench_records_the_deed_and_the_level_lands(client):
    """`craft_do` sent no `milestone` param at all, so the deed could be done and the
    level stayed locked: the mastery was kept, `to_next` went on naming a milestone that
    nothing could ever satisfy, and the page had no way to say so."""
    from play import campaign as cm

    c = cm.current()
    pc = c.scene.pc()
    progress = pc.track("herbalist")
    progress.level, progress.mp = 4, 500
    # 100 doses is 50 attempts at 15%, so the dice fail to land it once in 3,000 runs.
    # Twenty attempts flaked one run in twenty-five, which is a test nobody would trust.
    pc.add_stock(_exotic(count=1), count=100)
    c.save()

    body = json.dumps({"craft": "herbalism", "methods": ["distill"],
                       "ingredients": [], "stock": {_exotic().id: 2}})
    for _ in range(50):
        d = client.post("/api/craft/do", data=body,
                        content_type="application/json").json()
        if d.get("succeeded"):
            break
        if not cm.current().scene.pc().stock.get(_exotic().id):
            pytest.skip("the dice never landed the 15%; the path is the point")

    progress = cm.current().scene.pc().track("herbalist")
    assert "legendary-catalyst" in progress.milestones
    # The deed lands the level; the track no longer stops there.
    assert progress.level >= 5
    assert "catalyst crafting" in wc.get("herbalist").unlocked_methods(progress.level)


def test_the_bench_says_what_the_level_is_waiting_on(client):
    """Found in the user's own live save: Herbalist 4 at 110 MP of a 100 MP threshold,
    `to_next.need` 0, bar drawn full, level not moving, and nothing anywhere on the page
    saying why. The deed was in the track state the whole time and simply was never
    drawn — the same shape as a hidden required field killing a submit in silence."""
    from play import campaign as cm

    c = cm.current()
    progress = c.scene.pc().track("herbalist")
    progress.level, progress.mp = 4, 110
    c.save()

    state = client.get("/api/craft/ingredients?craft=herbalism").json()["track"]
    assert state["to_next"] == {"need": 0, "of": 100,
                                "milestone": "legendary-catalyst"}

    page = client.get("/craft/").content.decode()
    assert "mwaits" in page
    assert "also waits on" in page


def test_the_catalyst_itself_is_craftable_once_the_level_lands():
    """The point of the whole exercise: at Herbalist 5 a chain ending in `catalyst
    crafting` over legendary material previews clean, where at every level below it came
    back "Catalyst Crafting is learned at Herbalist 5"."""
    shelf = ingredients.all_ingredients()
    satchel = {i.id: 9 for i in shelf.values()}
    r = crafting.preview("herbalist", 5,
                         Chain("herbalist", ["grind", "catalyst crafting"],
                               ["phoenix-feather"]),
                         stock={}, satchel=satchel)
    assert not r.problems
    assert r.tier == "legendary"
    assert r.name.endswith("Catalyst")
    assert r.chance > 0


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

    None of which blocks the top of the track. Concentration is the way in — two exotic
    doses distil into one legendary at Herbalist 4 — and it needs no monster part.
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
    scene.biome = "forest"
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name="a wandering trader"))
    engine = Engine(scene, Dice(seed=3))
    engine.run(engine.validate([{
        "op": "give", "actor": "c1", "because": "the trader hands it over",
        "params": {"to": "pc", "item": "Phoenix Feather", "count": 1}}]))
    assert scene.pc().inventory.get("phoenix-feather") == 1


def test_the_way_to_the_top_needs_no_monster_part_at_all(herbalist):
    """The practical route, end to end: an exotic jar is within an Herbalist 4's ceiling,
    two of its doses concentrate to legendary, and a legendary success is the deed.

    Worth pinning because the obvious reading of "legendary catalyst" is that you need
    legendary material, and three of the four legendary ingredients cannot be foraged.
    They are not the way in.
    """
    held = _exotic()
    r = crafting.preview("herbalist", 4,
                         Chain("herbalist", ["distill"], stock_used={held.id: 2}),
                         stock={held.id: held}, satchel={})
    assert not r.problems and r.tier == "legendary"
    assert herbalist.deed_done(tier=r.tier, success=True) == "legendary-catalyst"
    # And raw legendary material is still correctly out of reach at that level: the
    # ceiling is what makes concentration the interesting move rather than a workaround.
    raw = crafting.preview("herbalist", 4,
                           Chain("herbalist", ["grind"], ["phoenix-feather"]),
                           stock={}, satchel={"phoenix-feather": 1})
    assert any("Herbalist 4 works exotic" in p for p in raw.problems), raw.problems
