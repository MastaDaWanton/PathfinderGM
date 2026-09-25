"""Somebody the prose described can be found again, by the player's own words.

Measured on the code before this (2026-09-25), with the population already recording her:
the woman watching from a doorway stood in the population at the party's own spot, and
"I talk to the woman in the doorway" was answered, by all three of the lookups the player's
words go through — `scope.look_for`, `judgement.absent_answer` and `repair_unknown_refs` —
with **"No woman in the doorway is here, and Vormoor has none the world names."** The
lookups knew the actors and the world's named characters; a person the prose painted and
nobody engaged was neither.

Design record: docs/the-population.md §6 — scope rings, a synonym table, "which do you
mean", never a guess; after Inform and TADS, which resolve by scope and then ask.
"""
from __future__ import annotations

import time

import pytest

from gm import judgement
from rules import population, scope
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id


@pytest.fixture
def scene():
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = 600
    population.drain_misses()
    return s


def test_the_woman_in_the_doorway_is_found_where_she_stands(scene):
    rec = population.note(scene, "woman watching from a doorway")
    found = scope.look_for(WORLD, "woman in the doorway", scene, VORMOOR)
    assert found["scope"] == scope.HERE and found["record"] == rec["id"]
    assert judgement.absent_answer(scene, WORLD, "I talk to the woman in the doorway") == ""


@pytest.mark.parametrize("said", ["the lady by the door", "the woman at the doorway",
                                  "the watching woman", "the lady who was staring"])
def test_the_players_words_need_not_be_the_prose_words(scene, said):
    rec = population.note(scene, "woman watching from a doorway")
    found = population.find(scene, said)
    assert found.scope == population.HERE and found.people == [rec], said


def test_a_trade_is_found_by_any_name_the_trade_goes_by(scene):
    rec = population.note(scene, "the smith")
    assert population.find(scene, "the blacksmith").people == [rec]


def test_unknown_is_not_contradicted_but_the_wrong_one_is(scene):
    """The prose's "someone mending nets" said nothing about who they are, so "the woman
    mending nets" is them; "a woman mending nets" is never "the man mending nets"."""
    someone = population.note(scene, "someone mending nets")
    assert population.find(scene, "the woman mending nets").people == [someone]
    scene.population.clear()
    population.note(scene, "a woman mending nets")
    assert population.find(scene, "the man mending nets").scope == population.NONE


def test_two_that_fit_are_asked_about_never_guessed(scene):
    population.note(scene, "a woman at the well")
    population.note(scene, "a woman selling eels")
    found = scope.look_for(WORLD, "the woman", scene, VORMOOR)
    assert found["scope"] == scope.AMBIGUOUS
    assert found["line"] == ("Which do you mean — the woman at the well, "
                             "or the woman selling eels?")


def test_the_nearer_ring_wins_before_anybody_is_asked(scene):
    """A guard at the gate an hour ago and a guard here now: "the guard" is this one."""
    scene.at = "gate"
    population.note(scene, "a guard")
    scene.at = "plaza"
    scene.clock_minutes += 90
    here = population.note(scene, "a guard")
    found = population.find(scene, "the guard")
    assert found.scope == population.HERE and found.people == [here]


def test_somebody_seen_elsewhere_is_said_to_be_elsewhere(scene):
    places = Engine(scene, Dice(seed=1), world=WORLD).places()
    first, second = places[0], places[1]
    scene.at = first.id
    population.note(scene, "an old fisherman mending nets")
    scene.at = second.id
    found = scope.look_for(WORLD, "the old fisherman", scene, VORMOOR)
    assert found["scope"] == scope.ELSEWHERE
    assert found["line"] == (f"The old fisherman mending nets was at {first.name} when "
                             f"you saw them, and is not here.")


def test_a_vague_word_does_not_read_out_the_town(scene):
    """"the woman" names half the town. Thirty women seen long ago elsewhere in town are
    not a question worth asking; asked vaguely, only the room and the recent are searched."""
    scene.at = "docks"
    for i, what in enumerate(["selling eels", "at the well", "with a basket", "mending sails",
                              "carrying water", "sweeping", "shouting", "singing"]):
        population.note(scene, f"a woman {what}")
    scene.at = "plaza"
    scene.clock_minutes += 600
    assert scope.look_for(WORLD, "the woman", scene, VORMOOR)["scope"] == ""


def test_the_model_reaching_for_her_gives_her_her_own_body(scene):
    """The repair path: the GM wrote `woman_doorway`, the ref registry refused it, and the
    old repair answered that no such woman existed. Now she is embodied from her record —
    her rolled face, her record keeping the ref — and nobody else is spawned."""
    rec = population.note(scene, "woman watching from a doorway")
    raw = [{"op": "say", "actor": "pc", "target": "woman_doorway",
            "params": {"words": "Good evening."}}]
    out = judgement.repair_unknown_refs(raw, "I talk to the woman in the doorway", scene,
                                        world=WORLD)
    assert not any(r.get("op") == "spawn" for r in out)
    ref = out[0]["target"]
    actor = scene.actors[ref]
    assert rec["ref"] == ref and rec["life"]["face"] in actor.appearance
    assert population.of_ref(scene, ref) is rec
    Engine(scene, Dice(seed=2), world=WORLD).validate(out)


def test_the_model_reaching_for_one_of_two_is_asked_back(scene):
    population.note(scene, "a woman at the well")
    population.note(scene, "a woman selling eels")
    raw = [{"op": "say", "actor": "pc", "target": "woman1", "params": {"words": "Hello."}}]
    out = judgement.repair_unknown_refs(raw, "I talk to the woman", scene, world=WORLD)
    assert not any(r.get("op") == "spawn" for r in out)
    assert out[-1]["params"]["not_here"].startswith("Which do you mean")
    assert all(not r.get("ref") for r in scene.population.values()), "nobody chosen"


def test_a_search_that_finds_nobody_is_written_down(scene):
    """The synonym table grows from real play: every miss reaches the turn log."""
    population.note(scene, "woman watching from a doorway")
    population.find(scene, "the tinker with the cart")
    missed = population.drain_misses()
    assert missed and missed[0]["kind"] == "population-miss"
    assert missed[0]["phrase"] == "the tinker with the cart"


def test_the_world_named_people_are_still_answered_first(scene):
    """The mayor case (item 29) is untouched by a population: nobody the prose described
    is a mayor, and Vormoor's answer is still its reeve."""
    population.note(scene, "woman watching from a doorway")
    assert scope.look_for(WORLD, "mayor", scene, VORMOOR)["scope"] == scope.NOWHERE


def test_a_big_town_is_searched_in_milliseconds(scene):
    """Measured before an index was reached for (§6 names SQLite FTS5): a linear scan
    over five thousand records. If this fails, build the index; do not loosen it."""
    words = ["baker", "fishwife", "carter", "guard", "scribe", "weaver", "beggar", "sailor",
             "tanner", "potter", "minstrel", "servant", "farmer", "clerk", "smith"]
    for i in range(5000):
        scene.population[f"p{i + 1}"] = {
            "id": f"p{i + 1}", "phrase": f"a {words[i % len(words)]} with a {i}-knot cord",
            "home": VORMOOR, "spot": f"spot{i % 40}", "first_seen": 0, "last_seen": 0,
            "last_met": None, "turn": 0, "ref": "", "tier": "glimpse",
            "life": {"work": "", "work_name": "", "face": "a plain face"}}
    start = time.perf_counter()
    population.find(scene, "the tinker with the cart")
    assert time.perf_counter() - start < 0.5
