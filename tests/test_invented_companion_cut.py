"""`invented-companion`: read in the narration only, and cut on a second read's yes.

The finder was measured in the tavern — "your fist connects with a meaty impact, and your
companion's next swing brings you another crushing blow to the thug's jaw", with the
player alone all scene — and until 2026-10-17 it read the whole beat, speech included, and
had no repair but the whole-beat rewrite. docs/narrator-guards.md listed it "left as
written: no cut that would not take dialogue or a whole line". A barkeep spitting "Where
are your friends now?" is his to say; a narrated second pair of hands is not.

Measured on the 2026-10 scratch benches: the finder flagged four beats, and all four were
false — "the bucket being hoisted by the others", "the wound in your side", "the rope tucked
securely against your side", "the others in the room begin to move". The closed question
("Does this sentence show somebody fighting beside you or on your side now?") refuted each
2 of 2 and kept the report's sentence and three made allies 2 of 2 each (gemma-4-12B).
"""
from __future__ import annotations

import json

from gm import agent as agent_mod
from gm import beat_verify as bv
from gm import narration

from _a_truth import MARKET, scene_at

SWING = ("Your fist connects with a meaty impact, and your companion's next swing brings "
         "you another crushing blow to the thug's jaw.")
DRAFT = (SWING + " The thug folds over the crate and does not get up. The yard falls quiet "
         "around you. What do you do?")


def test_a_companion_said_aloud_is_not_the_narrators():
    said = "\"Where are your friends now?\" the barkeep spits, circling. What do you do?"
    r = narration.review(said, pc_name="Kesst Vayr", alone=True)
    assert "invented-companion" not in {f.kind for f in r.findings}


def test_a_narrated_companion_names_its_sentence_and_the_question():
    r = narration.review(DRAFT, pc_name="Kesst Vayr", alone=True)
    f = next(f for f in r.findings if f.kind == "invented-companion")
    assert f.sentences == (SWING,)
    assert f.questions == (narration.COMPANION_QUESTION,)
    assert "invented-companion" in agent_mod.GMAgent._CUT_WHEN_UNREPAIRED


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _polish(monkeypatch, answer):
    agent, _ = scene_at(MARKET)
    # The tavern's scene: the player the last one standing (the market's keepers are
    # placed at it, so the finder's gate is set here rather than by felling them).
    agent._alone = lambda: True
    agent.prose_model = "stub"
    monkeypatch.setattr(bv, "ENABLED", True)
    asked = []

    def ask(sentence, q, **k):
        asked.append((sentence, q))
        return answer

    monkeypatch.setattr(bv, "ask", ask)
    # The rewrite comes back as the draft itself: no better, so refused.
    monkeypatch.setattr(agent_mod.client, "chat",
                        lambda *a, **k: _Reply(json.dumps({"narration": DRAFT})))
    out, notes, _ = agent.polish(DRAFT)
    return out, notes, asked


def test_no_rewrite_held_and_the_second_read_says_yes_the_sentence_goes(monkeypatch):
    out, notes, asked = _polish(monkeypatch, True)
    assert asked == [(SWING, narration.COMPANION_QUESTION)]
    assert "companion" not in out and out.startswith("The thug folds over the crate")
    assert any(n.startswith("invented-companion: no rewrite held; cut") for n in notes)


def test_refuted_it_stays_and_is_not_logged_unrepaired(monkeypatch):
    out, notes, _asked = _polish(monkeypatch, False)
    assert out.startswith(SWING)
    assert not any(n.startswith("unrepaired") and "invented-companion" in n for n in notes)
