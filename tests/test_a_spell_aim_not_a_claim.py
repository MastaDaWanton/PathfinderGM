"""A spell's aim is not a possession claim (item 21.5).

Measured on the Bobby playtest, 2026-09-28, turn 12: "I cast burning hands into the tree
tops" was read by the false-claim check as producing "a tree tops you do not have" —
`_PRODUCE` counts "hands" as a verb ("hands over"). The claim went to the prose as a
false-claim block and to the heat note, and the man in the woods mocked a bluff.
"""
from __future__ import annotations

from gm import judgement

from _a_truth import APPROACH, scene_at


def _bobby():
    agent, _ = scene_at(APPROACH)
    pc = agent.engine.scene.pc()
    pc.char_class = "wizard"
    pc.spellbook = ["burning-hands", "magic-missile"]
    return agent.engine.scene


def test_the_tree_tops_are_no_longer_claimed():
    scene = _bobby()
    # The shape that misread it is still there — "hands" is still a verb of handing
    # over — and the spell's name is what is masked before it is read.
    assert judgement._PRODUCE.search("I cast burning hands into the tree tops")
    assert judgement.false_possession("I cast burning hands into the tree tops", scene) == ""
    assert judgement.false_claim("I cast burning hands into the tree tops", scene) == ""


def test_the_reading_names_the_spell_even_off_the_sheet():
    """The interpreter's own reading of the cast is masked too: the spell is what the
    player said it is, whatever words it is made of."""
    agent, _ = scene_at(APPROACH)
    scene = agent.engine.scene
    reading = {"actions": [{"act": "cast", "object": "burning hands",
                            "target": "the tree tops"}]}
    assert judgement.false_possession("I cast burning hands into the tree tops", scene,
                                      reading=reading) == ""


def test_a_real_false_possession_still_is_one():
    """Item 37's crown is untouched by the mask."""
    scene = _bobby()
    assert "crown" in judgement.false_possession("I pull out my crown and show them",
                                                 scene)
