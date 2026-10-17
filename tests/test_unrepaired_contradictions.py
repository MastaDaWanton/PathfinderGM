"""A found contradiction that shipped: the whole-beat rewrite mended it and was refused.

Measured live 2026-10-17 on the integration branch (free narrator, gemma-4-12B, a scratch
copy of the owner's data): the player's dagger hit the one behind the bar for 6 (17 of 23
left), and the page said "He cries out… and collapses against the bar". The turn log:
`unrepaired: contradicts-the-engine … too-long-for-a-fight`. The rewrite had fixed both
(review score 4 -> 0) and was REFUSED for keeping 0.0 of the draft's "events" — the
collapse itself, and a phantom fighter's lunge, were two of the three. In a fight there is
no retry, and the finding had no backstop. Across 511 scratch saves, 139 beats logged
`unrepaired:`; `contradicts-the-engine` was in 26 and `stands-elsewhere` in 30.
"""
from __future__ import annotations

import json

from gm import agent as agent_mod
from gm import beat_verify as bv

from _a_truth import MARKET, scene_at

DRAFT = (
    "The man's face buckles under your strike, and the blade bites deep into his shoulder. "
    "He cries out—a jagged, wet sound—and collapses against the bar, knocking several "
    "glasses to the floor. The sound of shattering glass rings through the room like a "
    "bell. Outside, the muffled sounds of the morning market are suddenly punctuated by a "
    "shout from someone in the hallway. The other man, his eyes wide with shock, hesitates "
    "for a heartbeat before lunging toward you, his hands out like claws. The air smells of "
    "spilled ale and the sharp, metallic tang of blood. You are cornered between the bar and "
    "the nearest exit. What do you do?")
# The rewrite the live polish call returned, word for word.
REFUSED = (
    "You lunge forward, closing the distance to the one behind the bar as he falters. Your "
    "dagger finds a gap in his defense, piercing his hide with a sharp thrust. He recoils "
    "from the strike, his breath hitching in his throat. The heavy wooden counter stands "
    "between you and the nearest exit, but a heavy stool remains within your reach. What do "
    "you do?")
COLLAPSE = ("He cries out—a jagged, wet sound—and collapses against the bar, knocking "
            "several glasses to the floor.")


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _barkeep_hurt():
    agent, _ = scene_at(MARKET, [("the one behind the bar", "guildhand")])
    man = next(a for a in agent.engine.scene.actors.values() if not a.is_pc)
    man.hp = max(1, man.hp_max - 2)          # struck, hurt, on his feet
    return agent, man


# --- 1. a found contradiction never ships ---------------------------------------------------

def test_the_review_names_the_untrue_sentence_and_a_question_for_it():
    """The finding carried no sentence, so nothing downstream could cut it, and the events
    guard counted the collapse itself as something a rewrite had to keep."""
    agent, _ = _barkeep_hurt()
    review = agent_mod.narration_mod.review(
        DRAFT, state=agent._body_count(), max_chars=600)
    found = next(f for f in review.findings if f.kind == "contradicts-the-engine")
    assert found.sentences == (COLLAPSE,)
    q = found.questions[0]
    assert "the one behind the bar (who may be called he, she or they here)" in q
    assert "collapses, falls, drops" in q and "Not only staggers" in q


def test_the_recorded_refused_rewrite_no_longer_ships_the_collapse(monkeypatch):
    """The live beat replayed: the same rewrite is still refused (it rewrote the strike
    and dropped the other man, keeping 0 of the draft's two true sentences), and the
    collapse is now cut instead of shipping as `unrepaired`."""
    agent, _ = _barkeep_hurt()
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply(
        json.dumps({"narration": REFUSED})))
    out, notes, _ = agent.polish(DRAFT, max_chars=600)
    assert "collapses against the bar" not in out
    assert out.startswith("The man's face buckles under your strike")
    assert any(n.startswith("contradicts-the-engine: no rewrite held; cut") for n in notes)
    assert not any("contradicts-the-engine" in n for n in notes if n.startswith("unrepaired"))
    assert len(out) < 600, "the cut takes the beat under the fight's ceiling too"


def test_a_rewrite_that_only_drops_the_untrue_sentence_is_not_refused(monkeypatch):
    """Two events in the draft, the second the collapse: a rewrite keeping the first and
    putting the man on his feet kept 1 of 2 (0.5) and was refused before. The untrue
    sentence is no event a rewrite owes the draft."""
    agent, _ = _barkeep_hurt()
    draft = ("The man's face buckles under your strike, and the blade bites deep into his "
             "shoulder. " + COLLAPSE + " The air smells of spilled ale. What do you do?")
    fixed = ("The man's face buckles under your strike, and the blade bites deep into his "
             "shoulder. He snarls and keeps his feet, one hand pressed to the wound. The air "
             "smells of spilled ale. What do you do?")
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply(
        json.dumps({"narration": fixed})))
    out, notes, _ = agent.polish(draft, max_chars=600)
    assert out == fixed, notes


def test_the_second_read_decides_before_a_sentence_is_cut(monkeypatch):
    """The finder is English regex; the read back's second read is asked first, and a no
    keeps the sentence (and says so). A call that fails would keep the finding's answer."""
    agent, _ = _barkeep_hurt()
    agent.prose_model = "stub"
    monkeypatch.setattr(bv, "ENABLED", True)
    asked = []

    def chat(messages, *a, schema=None, **k):
        if "answer" in (schema or {}).get("properties", {}):
            asked.append(messages[-1]["content"])
            return _Reply(json.dumps({"answer": "no"}))
        return _Reply(json.dumps({"narration": REFUSED}))

    monkeypatch.setattr(agent_mod.client, "chat", chat)     # gm.client, both callers' door
    out, notes, _ = agent.polish(DRAFT, max_chars=600)
    assert asked and "collapses against the bar" in asked[0]
    assert "the one behind the bar" in asked[0]
    assert "collapses against the bar" in out
    assert any("the second read refuted" in n for n in notes)


def test_a_failed_rewrite_call_cuts_the_untrue_sentence_too(monkeypatch):
    agent, _ = _barkeep_hurt()

    def boom(*a, **k):
        raise TimeoutError("model stalled")

    monkeypatch.setattr(agent_mod.client, "chat", boom)
    out, notes, _ = agent.polish(DRAFT, max_chars=600)
    assert "collapses against the bar" not in out
    assert any(n.startswith("polish failed") for n in notes)
