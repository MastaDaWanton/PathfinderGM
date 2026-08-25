"""What the dead were carrying.

The bestiary has carried a `treasure` column all along — 550 creatures declare one of
the Core Rulebook's classes — and nothing read it. Invisible while buying was free; the
moment a market started charging it became the whole economy, because a character spent
their starting wealth and had no way in the game to earn a copper.

Third field found declared-and-unread in one session, after `starting_wealth` on every
class and `price_gp` on every material.
"""
from __future__ import annotations

import pytest

from rules import bestiary, goods, treasure
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _scene_with(template: str):
    scene = Scene()
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    foe = bestiary.instantiate(template, scene=scene, name=template)
    scene.add(foe)
    return scene, pc, foe


def test_the_book_decides_what_a_body_is_worth():
    """Core Rulebook, Treasure Values per Encounter, quartered because a single creature
    is not a whole encounter — six wolves would otherwise be six encounters of gold."""
    scene, _, foe = _scene_with("achaierai")           # CR 5, standard
    assert treasure.class_of(foe) == "standard"
    assert treasure._cr_of(foe) == 5
    centre = 1550 * 1.0 * treasure.PER_CREATURE        # 387.5
    got = [treasure.worth(foe) for _ in range(200)]
    assert min(got) >= centre * 0.4, min(got)
    assert max(got) <= centre * 1.6, max(got)
    assert len(set(got)) > 1, "the same body twice is the same purse twice"


def test_the_class_scales_it():
    """incidental is half a standard haul, double is two, triple is three."""
    scene, _, vine = _scene_with("assassin-vine")      # CR 3, incidental
    assert treasure.class_of(vine) == "incidental"
    centre = 800 * 0.5 * treasure.PER_CREATURE         # 100
    got = [treasure.worth(vine) for _ in range(200)]
    assert min(got) >= centre * 0.4 and max(got) <= centre * 1.6


def test_a_creature_that_says_none_carries_none():
    scene, _, thing = _scene_with("animated-object")
    assert treasure.class_of(thing) == "none"
    assert treasure.worth(thing) == 0


def test_silence_is_not_the_same_as_none():
    """6,355 of the bestiary's 7,136 entries never had the column filled in. Reading
    silence as "carries nothing" would make almost every fight in the game worthless;
    it means the GM decides, the same answer `xp.worth` gives for an unpriced creature."""
    scene, _, bear = _scene_with("black-bear")
    assert treasure.class_of(bear) == ""
    assert treasure.worth(bear) == 0


def test_the_column_is_read_off_the_template_not_the_actor():
    """An instantiated Actor carries neither `cr` nor `treasure` — they stay in the
    template — and `bestiary.lookup` answers with the trimmed playable stat block, which
    drops both. Read through `lookup`, every creature in the game reported no treasure
    and CR 0."""
    scene, _, foe = _scene_with("achaierai")
    assert getattr(foe, "treasure", None) in (None, "")
    assert treasure.class_of(foe) == "standard"        # found anyway, via the template


def test_a_finished_fight_leaves_gold_on_the_ground():
    """The loop the market opened: kill something, take what it had, buy materials."""
    scene, pc, foe = _scene_with("achaierai")
    pc.purse = {}
    engine = Engine(scene, Dice(seed=7))
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"us": [pc.ref],
                                                      "them": [foe.ref]}}}]))
    foe.hp = 0
    tell = engine._settle_xp()
    assert goods.in_copper(pc.purse) > 0, tell
    assert "Taken from" in tell


def test_the_ones_who_ran_keep_their_purses():
    """Only the fallen pay, the same rule the XP award uses — which leaves mercy costing
    something rather than paying."""
    scene, pc, foe = _scene_with("achaierai")
    pc.purse = {}
    engine = Engine(scene, Dice(seed=7))
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"us": [pc.ref],
                                                      "them": [foe.ref]}}}]))
    engine._settle_xp()                                 # foe still standing
    assert goods.in_copper(pc.purse) == 0


def test_treasure_settles_even_when_the_kill_pays_no_xp():
    """Written as `return line + self._settle_treasure()` on the paying branch only, a
    creature with a treasure column and no XP price dropped its purse on the floor and
    nobody picked it up."""
    scene, pc, foe = _scene_with("achaierai")
    pc.purse = {}
    foe.xp_value = 0
    engine = Engine(scene, Dice(seed=11))
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"us": [pc.ref],
                                                      "them": [foe.ref]}}}]))
    foe.hp = 0
    tell = engine._settle_xp()
    assert "Taken from" in tell, tell


def test_credit_is_the_counterpart_to_spend():
    assert goods.in_copper(goods.credit({}, 250)) == 250
    assert goods.in_copper(goods.credit({"gp": 1}, 250)) == 350
    assert goods.credit({}, 0) == {}
    assert goods.credit({}, -5) == {}
