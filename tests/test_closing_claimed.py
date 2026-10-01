"""A creature's beat that has it reach the player, when the board says it did not.

Measured on the owner's save, 2026-10-01: the Clockwork Spy's move resolved "Clockwork
Spy moves from far to far." and it stayed forty feet off; the consequence beat for its
turn read "It covers the distance in a blur of motion, closing the gap and landing right
before you." The owner's map had it still far away. Nothing on the page compared a
creature's distance with what the beat claimed. `gm/checks/closing_claimed.py` does, on
the acting creature's own consequence beat, and the backstop cuts the claim and ends on
how far off the engine holds it.
"""
from __future__ import annotations

import pytest

from gm import checks
from gm.checks import BeatContext, closing_claimed

from test_creature_closes import TOWARD, _owners_board, _run

# The owner's consequence beat for the spy's turn, as it reached the page.
OWNERS_BEAT = ("The Clockwork Spy's mechanical limbs whir with violent intensity as it "
               "propels itself across the deck. It covers the distance in a blur of "
               "motion, closing the gap and landing right before you.")


def _ctx(engine, text, acting="c1", door="outcome", outcomes=()):
    return BeatContext(
        door=door, text=text, player_text="", engine=engine, scene=engine.scene,
        world=None, location=None, reading=None, outcomes=tuple(outcomes), tells=(),
        said=(), attribution=None, brief="", brief_facts={}, pull=None, was_at="",
        acting=acting, turn=0)


@pytest.mark.parametrize("sentence", [
    "It covers the distance in a blur of motion, closing the gap and landing right "
    "before you.",
    "The spy closes the gap in three bounds.",
    "It is upon you before you can blink.",
    "The construct reaches you and rears up.",
    "It skids to a halt and settles right at your feet.",
    "It hurls itself at you and lands right before you.",
])
def test_an_arrival_at_the_player_is_a_claim(sentence):
    assert closing_claimed.claims(sentence)


@pytest.mark.parametrize("sentence", [
    "It lets out a grinding hiss and lunges forward, attempting to close the gap.",
    "It rushes forward to close the distance.",
    "It has not reached you yet.",
    "You close the gap with two long strides.",
    "It lands on the far rocks with a clatter.",
    "Will it reach you before you can draw?",
    "It nearly closes the distance before the rocks stop it.",
])
def test_an_attempt_a_denial_the_players_walk_and_a_question_are_not(sentence):
    assert not closing_claimed.claims(sentence)


def test_the_owners_beat_is_flagged_with_the_spy_still_ten_feet_off():
    """After the fixed move the spy is 10 ft off (it walked 30 of 40). The owner's beat,
    "landing right before you", is the claim the board contradicts."""
    scene, engine = _owners_board()
    _run(engine, [TOWARD])
    assert scene.distance_between("c1", "pc") == 10
    (found,) = closing_claimed.find(_ctx(engine, OWNERS_BEAT))
    assert found.kind == "closing-claimed"
    assert found.sentences == ("It covers the distance in a blur of motion, closing the "
                               "gap and landing right before you.",)
    assert "still 10 feet away" in found.fix_hint


def test_the_same_beat_is_true_once_the_spy_is_in_the_square():
    """In the player's square (0 ft) — or beside them — the beat is the truth."""
    scene, engine = _owners_board(spy_at=(5, 7))
    assert closing_claimed.find(_ctx(engine, OWNERS_BEAT)) == []
    scene2, engine2 = _owners_board(spy_at=(5, 8))
    assert closing_claimed.find(_ctx(engine2, OWNERS_BEAT)) == []


def test_bounded_to_the_acting_creature_on_its_own_consequence_beat():
    """Not the plan beat written before the engine moved anything (door `npc`), not the
    player's turn (no `acting`), and not a scene with no map."""
    scene, engine = _owners_board()
    assert closing_claimed.find(_ctx(engine, OWNERS_BEAT, acting="")) == []
    assert closing_claimed.find(_ctx(engine, OWNERS_BEAT, acting="pc")) == []
    assert closing_claimed.DOORS == frozenset({"outcome"})
    assert closing_claimed in checks.registered()
    scene.grid = None
    assert closing_claimed.find(_ctx(engine, OWNERS_BEAT)) == []


def test_the_backstop_cuts_the_claim_and_ends_on_the_distance():
    scene, engine = _owners_board()
    _run(engine, [TOWARD])
    ctx = _ctx(engine, OWNERS_BEAT)
    found = closing_claimed.find(ctx)
    kept, notes = closing_claimed.backstop(ctx, OWNERS_BEAT, found)
    assert kept == ("The Clockwork Spy's mechanical limbs whir with violent intensity as "
                    "it propels itself across the deck. The Clockwork Spy is still 10 feet "
                    "from you.")
    assert notes and "10 ft off" in notes[0]


def test_through_the_real_door_the_beat_reaches_the_page_without_the_claim(monkeypatch):
    """`narrate_outcome`, the call the NPC loop makes for a creature's consequence beat:
    the model writes the owner's beat, the targeted repair is unavailable, and the
    backstop leaves the page saying where the spy really is."""
    from gm import agent as agent_mod
    from gm import client

    from test_wrong_actor import _World

    scene, engine = _owners_board()
    res = _run(engine, [TOWARD])
    gm = agent_mod.GMAgent(_World(), engine)
    calls = []

    def chat(messages, model, *a, **kw):
        calls.append(messages)
        if len(calls) == 1:
            return client.Reply(OWNERS_BEAT, 0.1, model)
        raise client.ModelUnavailable("down")

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    text, attempt = gm.narrate_outcome("", res.outcomes, "Clockwork Spy acts",
                                       rewrite=False, acting="Clockwork Spy")
    assert "landing right before you" not in text
    assert text.endswith("The Clockwork Spy is still 10 feet from you.")
    assert "closing claimed" in attempt.note
