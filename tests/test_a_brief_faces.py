"""The brief says how the page first described each person, and says it once (item 16.7).

Measured on the Bobby playtest, 2026-09-28: the brief labelled a present person's face
"use it when they are first described", which licensed a new face on every beat after the
first — the watchman, an Orc with hair like wet rope, came back as "an older man with a
face like cracked leather". And the IN CONVERSATION WITH block sat inside the WHO IS HERE
loop, so it printed once per visible person: five people, five copies of one fact
(register §3.4, found by S2).
"""
from __future__ import annotations

from gm import prompts
from rules import states

from _a_truth import MARKET, VORMOOR, WORLD, scene_at


def _scene(n: int, engine: bool = False):
    agent, _ = scene_at(MARKET, [(f"the carter {i}", "guildhand") for i in range(n)])
    return (agent.engine.scene, agent.engine) if engine else agent.engine.scene


def test_the_conversation_block_is_printed_once_however_many_are_here():
    scene, engine = _scene(4, engine=True)
    talker = next(a for a in scene.actors.values() if not a.is_pc)
    assert engine.join_talk(talker, how="test")
    assert talker.has_state(states.TALKING)
    brief = prompts.scene_brief(WORLD, scene, VORMOOR, [])
    visible = sum(1 for a in scene.actors.values()
                  if a.is_pc or not a.has_state("state.hidden"))
    assert visible >= 5
    assert brief.count("IN CONVERSATION WITH:") == 1


def test_a_described_person_is_listed_with_the_pages_own_sentence():
    scene = _scene(1)
    a = next(x for x in scene.actors.values() if not x.is_pc)
    a.described = True
    a.appearance = "Orc: old enough to have stopped counting; hair the colour of wet rope."
    a.described_as = ["The carter is an old Orc with hair like wet rope."]
    brief = prompts.scene_brief(WORLD, scene, VORMOOR, [])
    assert "ALREADY DESCRIBED — keep to it" in brief
    assert f"{a.ref} — {a.name}: the page said: The carter is an old Orc" in brief
    assert "use it when they are first described" not in brief
    assert "every description of them keeps to it" in brief


def test_nobody_undescribed_is_listed():
    scene = _scene(1)
    brief = prompts.scene_brief(WORLD, scene, VORMOOR, [])
    assert "ALREADY DESCRIBED" not in brief
