"""The imported bestiary: 6,406 stat blocks the engine can actually fight.

The difference from the spell list is the whole point. Spells are reference, because the
engine has no spell system. Creatures are **executable**: `instantiate()` builds an Actor
with hit points, an AC, saves, damage reduction and an attack, and the engine rolls against
it. So these tests check that a creature can be put in a scene and hit somebody, not merely
that it loaded.
"""
from __future__ import annotations

import pytest
from django.test import Client, override_settings

from rules import bestiary
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


# --- what was imported ------------------------------------------------------------------

def test_the_bestiary_loaded():
    assert len(bestiary.imported()) > 6000


def test_every_imported_creature_has_what_combat_needs():
    """Nothing was invented to make a row look complete: the importer marks a stat block
    it could not fully parse rather than giving it a default AC that the engine would then
    roll against wrongly, with nobody ever questioning it."""
    for c in bestiary.imported().values():
        assert c["hp"] is not None, c["id"]
        assert c["flat_ac"] is not None, c["id"]
        assert c["abilities"], c["id"]


def test_a_creature_becomes_an_actor_that_can_fight():
    goblin = bestiary.instantiate("goblin", scene=Scene())
    assert goblin.hp > 0
    assert goblin.ac() > 0
    assert goblin.flat_attack is not None
    assert goblin.size == "small"


def test_an_imported_creature_can_actually_hit_the_player():
    """The claim this import makes. Reference material cannot do this."""
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    wolf = scene.add(bestiary.instantiate("wolf", scene=scene))

    engine = Engine(scene, Dice(seed=11))
    res = engine.run(engine.validate([
        {"op": "attack", "actor": wolf.ref, "target": "pc",
         "because": "it comes out of the dark"},
    ]))
    assert res.outcomes[0].verdict in ("hit", "miss")
    assert res.outcomes[0].rolls


def test_damage_reduction_survived_the_import():
    """1,483 creatures carry DR, and the engine has DR — so it has to arrive as something
    `Actor.reductions` can use rather than as a string nobody reads."""
    with_dr = [c for c in bestiary.imported().values() if c["reductions"]]
    assert len(with_dr) > 1000

    actor = bestiary.instantiate(with_dr[0]["id"], scene=Scene())
    assert actor.reductions
    assert actor.reductions[0].amount > 0


def test_ability_scores_a_creature_does_not_have_are_absent_not_ten():
    """An ooze has no Intelligence, and 10 is a real score while "none" is not."""
    missing = [c for c in bestiary.imported().values() if len(c["abilities"]) < 6]
    assert missing


# --- the hand-written NPCs still win --------------------------------------------------------

def test_the_town_npcs_are_not_replaced_by_the_import():
    """They are tuned for the opening scene; a generic import that happens to share a
    name must not silently take over."""
    thug = bestiary.lookup("thug")
    assert "sap" in thug.get("weapons", [])
    assert bestiary.details("thug")["hand_written"]


# --- rejection ------------------------------------------------------------------------------

def test_an_unknown_creature_suggests_rather_than_lists():
    """Naming all four templates was helpful. Naming all 6,406 is a wall of text, and a
    model reading it loses the turn it was in the middle of."""
    msg = bestiary.suggestion("guild bravo")
    assert "guildhand" in msg
    assert len(msg) < 300


def test_a_short_name_still_gets_suggestions():
    """Edit distance fails a short query against long names: "ogre" scored closer to
    nothing than to "ogre-boss", so the suggestion came back empty for the most obvious
    ask in the book."""
    msg = bestiary.suggestion("ogre")
    assert "ogre" in msg and "Did you mean" in msg


def test_a_near_name_is_never_silently_substituted():
    """This import is a variant and NPC bestiary — it holds Ogre Boss and Ambro the Ogre
    and no plain Ogre. Asking for an ogre must not quietly produce a boss."""
    with pytest.raises(bestiary.UnknownTemplate):
        bestiary.instantiate("ogre", scene=Scene())


def test_spawning_an_invented_creature_is_refused_in_validation():
    from rules.intents import IntentError, parse

    with pytest.raises(IntentError) as e:
        parse({"op": "spawn", "params": {"template": "grumbleworm", "count": 1}})
    assert "no creature" in str(e.value)


# --- searching ------------------------------------------------------------------------------

def test_searching_by_challenge_rating():
    low = bestiary.search(cr_max=1, limit=500)
    assert low
    assert all(c["cr_value"] <= 1 for c in low)


def test_searching_narrows_together():
    found = bestiary.search(creature_type="undead", size="large", cr_min=5, limit=50)
    for c in found:
        assert c["creature_type"] == "undead" and c["size"] == "large"
        assert c["cr_value"] >= 5


def test_results_come_back_by_challenge_rating():
    found = bestiary.search(creature_type="animal", limit=40)
    crs = [c["cr_value"] for c in found if c["cr_value"] is not None]
    assert crs == sorted(crs)


def test_the_vocabularies_are_counted():
    v = bestiary.vocabularies()
    assert v["types"]["humanoid"] > 1000
    assert v["sizes"]["medium"] > 1000


# --- through the app --------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


def test_the_creatures_bench_counts_the_whole_bestiary(client):
    d = client.get("/api/bench/creatures").json()
    assert d["bench"]["shipped"] > 6000
    assert d["rows"]
    assert len(d["rows"]) <= 210


def test_the_bench_says_what_the_import_is_missing(client):
    """A variant and NPC bestiary is not the core one, and saying so is the difference
    between a gap somebody can fill and a gap they trip over."""
    d = client.get("/api/bench/creatures").json()
    assert "no plain Ogre" in d["bench"]["waiting"]


def test_hand_written_npcs_are_labelled_on_the_bench(client):
    d = client.get("/api/bench/creatures").json()
    assert any(r["kind"] == "hand-written" for r in d["rows"])
