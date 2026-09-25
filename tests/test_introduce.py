"""People enter the scene because the plan declares them, before the prose is written.

docs/declared-not-guessed.md, the second door (2026-09-25). Until `introduce`, the only way
anybody entered a scene was the finished prose describing them and a regex booking them
afterwards (`note_cast` → `promote_cast`), and every misfire of that regex was a person
nobody declared: the phantom elder read out of "the elder-quarter" inside a quote
(2026-09-24), the second old man booked beside the opening's own (2026-09-25). Labyrinth
(arXiv 2409.06949) found letting the model rewrite state from its own dialogue the worst
approach it tried; its `create_npc` is declared, as this is.

The plan targets the people it introduces as new1…new3 — placeholders in the manner of
JSON:API's `lid` and ReWOO's `#E1`, legal only after the intent that makes them — rather
than asking the model to predict the next minted ref, as `spawn` does.
"""
from __future__ import annotations

import pytest

from gm import judgement, prompts
from rules import population
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError, parse_all
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id


@pytest.fixture
def engine():
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    return e


def _run(e, plan):
    return e.run(e.validate(plan, origin="author:test"))


def _intro(who, **params):
    return {"op": "introduce", "because": "t", "params": {"who": who, **params}}


def test_the_plan_speaks_to_the_person_it_just_introduced(engine):
    res = _run(engine, [_intro("old ferryman mending a net"),
                        {"op": "say", "actor": "pc", "because": "t",
                         "params": {"words": "Know the river?", "to": "new1"}}])
    s = engine.scene
    ref = next(r for r, a in s.actors.items() if a.name == "old ferryman mending a net")
    assert res.outcomes[1].status == "resolved" and s.actors[ref].name in res.outcomes[1].tell
    # A bystander with a population record, a life and the face it rolled.
    rec = population.of_ref(s, ref)
    assert rec and rec["life"]["face"] in s.actors[ref].appearance
    assert s.actors[ref].has_state("role.bystander")


def test_a_placeholder_is_legal_only_after_the_intent_that_makes_it(engine):
    with pytest.raises(IntentError):
        engine.validate([{"op": "say", "actor": "pc", "params": {"words": "hi", "to": "new1"}},
                         _intro("baker")])


def test_one_introduce_per_turn(engine):
    """An op always on offer gets over-used: Labyrinth's state-only planner "calls state
    functions too frequently"; When2Call measured Llama-3.1-8B calling a tool where none
    fitted 67% of the time. One per turn, a group by `count`, until live play says more."""
    with pytest.raises(IntentError, match="one introduce per turn"):
        engine.validate([_intro("baker"), _intro("carter")])


def test_the_model_cannot_write_the_placeholders_itself():
    with pytest.raises(IntentError):
        parse_all([_intro("baker", placeholders=["c1"])])


def test_already_here_is_the_glimpse_the_population_holds(engine):
    """Found again, not made twice: a glimpse the prose painted at this spot is who the
    plan means, and she walks on wearing the face her record rolled."""
    her = population.note(engine.scene, "old woman mending fishing nets by the doorway")
    _run(engine, [_intro("old woman mending nets")])
    assert her["ref"] and len(engine.scene.population) == 1
    assert her["life"]["face"] in engine.scene.actors[her["ref"]].appearance


def test_already_here_is_the_person_already_standing_here(engine):
    _run(engine, [_intro("old ferryman mending a net")])
    before = dict(engine.scene.actors)
    _run(engine, [_intro("the old ferryman"),
                  {"op": "say", "actor": "pc", "because": "t",
                   "params": {"words": "Again.", "to": "new1"}}])
    assert engine.scene.actors.keys() == before.keys(), "nobody new"


def test_a_newcomer_is_always_somebody_new(engine):
    _run(engine, [_intro("watchman", how="arrives")])
    _run(engine, [_intro("watchman", how="arrives")])
    assert sum(1 for a in engine.scene.actors.values() if a.name == "watchman") == 2
    refs = {r["ref"] for r in engine.scene.population.values()}
    assert len(refs) == 2, "two records, one per person"


def test_a_group_is_that_many_people(engine):
    res = _run(engine, [_intro("porter", count=2, how="arrives"),
                        {"op": "say", "actor": "pc", "because": "t",
                         "params": {"words": "You two.", "to": "new2"}}])
    porters = [r for r, a in engine.scene.actors.items() if a.name == "porter"]
    assert len(porters) == 2
    bound = res.outcomes[0].effects[0]["bound"]
    assert set(bound) == {"new1", "new2"} and set(bound.values()) == set(porters)


def test_a_turn_that_waits_on_the_player_keeps_real_refs(engine):
    """The queue is saved as it stands when a roll suspends the turn, and the next request
    runs it in a fresh engine: the swap happens in the queue, not in memory."""
    res = _run(engine, [
        _intro("ferryman", count=2, how="arrives"),
        {"op": "check", "actor": "pc", "because": "t",
         "params": {"skill": "sense motive", "opposed_by": {"ref": "new1", "skill": "bluff"}}},
        {"op": "say", "actor": "pc", "because": "t", "params": {"words": "Evening.", "to": "new2"}},
    ])
    assert res.awaiting
    s = engine.scene
    first, second = [r for r, a in s.actors.items() if a.name == "ferryman"]
    assert s.pending_intents[0]["params"]["opposed_by"]["ref"] == first
    assert s.pending_intents[1]["params"]["to"] == second
    done = Engine(s, Dice(seed=4), world=WORLD).resume(11)
    assert done.outcomes[-1].status == "resolved"
    assert done.outcomes[-1].effects[0]["to"] == second


def test_the_prose_describing_them_does_not_book_them_again(engine):
    """The ledger is what `note_cast` asks whether "the old ferryman" is somebody here."""
    res = _run(engine, [_intro("old ferryman mending a net")])
    judgement.book_introduced(engine.scene, res.outcomes, turn=1)
    booked = judgement.note_cast(
        engine.scene, "The old ferryman looks up from his net and squints at you.", turn=1)
    assert booked == []


def test_the_words_choose_the_stat_block(engine):
    raw = judgement.fill_introduce_templates([_intro("watchman at the gate")], engine.scene)
    assert raw[0]["params"]["template"] == "watchman"


def test_the_schema_offers_the_placeholders_where_introduce_can_be_written():
    calm = prompts.turn_schema(refs=("pc", "c1"))
    enum = calm["properties"]["intents"]["items"]["properties"]["target"]["enum"]
    assert {"new1", "new2", "new3"} <= set(enum)
    fight = prompts.turn_schema(fighting=True, refs=("pc", "c1"))
    assert "new1" not in fight["properties"]["intents"]["items"]["properties"]["target"]["enum"]


def test_the_worked_example_demonstrates_it():
    """Demonstration beats instruction (CLAUDE.md): the plan prompt teaches ops by
    example, so an op no example shows is an op the planner does not use."""
    shown = [i for e in prompts.EXAMPLES for i in (e["reply"].get("intents") or [])]
    assert any(i["op"] == "introduce" for i in shown)
    assert any((i.get("params") or {}).get("to") == "new1" for i in shown)
