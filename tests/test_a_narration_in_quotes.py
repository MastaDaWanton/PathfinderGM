"""Item 12 of docs/playtest-2026-09-30.md: narration put inside a speaker's quotation marks.

Measured in Sam's save (the owner's first play of 0.2.0): 5 narration sentences inside
Gorm Vesper's quotes across beats 51 and 53. `keeper_forward` flagged his spoken lines,
`_repair_sentences` spliced the model's rewrite in with a string replace INSIDE the
quotation marks, and the rewrite paraphrased the check's own fix hint ("…until you turn to
them", with the wrong pronoun). The acceptance check passed any rewrite that differed, and
beat 53's narration was then logged as Gorm's words ("Depends on the lady, who remains at
her post and only speaks if you turn to her" matched his tag by containment).

The beats below are the save's own text, verbatim.
"""
from __future__ import annotations

import json

from gm import agent as agent_mod
from gm import checks
from gm.checks import _quotes, keeper_forward, narration_in_quotes
from gm.narration import Finding
from rules import hooks, keepers

from _a_truth import MARKET, WAY_IN, context, scene_at

BEAT_51 = (
    "The woodsmoke and the heavy, sweet musk of bodies huddled together in the heat hang "
    "thick in the air of the stranger Veil. This tavern, a squat, leaning structure of "
    "lashed-together beams, sits tucked away from the main roads, its atmosphere muffled "
    "from the bustle of the town outside. Inside, the room is dim, lit by flickering lamps "
    "that cast a golden, hazy glow over the rough-hewn tables and the hearth. Behind a "
    "scarred wooden counter, Gorm Vesper—a young Ratfolk with a crooked jaw—is methodically "
    "polishing a tankard with a grimy cloth. He looks up as the door creaks, his eyes "
    "narrowing as he takes in your arrival. 'Gorm Vesper watches you from their workspace, "
    "remaining silent until you turn to face them.' he says, his voice a low rasp that "
    "barely carries over the crackle of the fire. 'Gorm Vesper remains at their post, "
    "silent, until you turn to them.' He pauses, the rag still in his hand, waiting for "
    "your order. What do you do?")
BEAT_53 = (
    "The question hangs in the thick, smoky air of the tavern, a stark contrast to the "
    "polite inquiry for a drink. Gorm's hand pauses on the tankard, the rag still and damp. "
    "He doesn't look at the others in the room, but his ears twitch. Behind the counter, "
    "the transaction of the flesh is a common enough thing, but it is a transaction that "
    "carries different weights depending on who is being bought. He leans forward just "
    "enough for the light to catch the scar on his jaw. 'Depends on the lady, who remains "
    "at her post and only speaks if you turn to her.' he says, his voice a low, gravelly "
    "rasp. 'Some are willing for a few coins to forget a long day. Others... others, like "
    "Gorm Vesper, require a heavy purse to forget a heavy past.' He gestures with a single, "
    "clawed finger toward the back of the tavern, where a heavy curtain of stained linen "
    "hangs over a doorway. 'Gorm Vesper doesn't care much for the price, so long as the "
    "coin is real and the company is... tolerable.' He lets that word linger, his eyes "
    "tracking your reaction. What do you do?")
# Beat 51 as the prose call wrote Gorm's lines, before the repair (turn log, the two
# keeper-forward findings of that beat).
BEAT_51_DRAFT = BEAT_51.replace(
    "'Gorm Vesper watches you from their workspace, remaining silent until you turn to "
    "face them.'", "'You look like you've walked a long road,'").replace(
    "'Gorm Vesper remains at their post, silent, until you turn to them.'",
    "'What can I get for you?'")


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _answer(monkeypatch, *sentences):
    asked: list = []
    queue = list(sentences)

    def fake_chat(messages, *a, **k):
        asked.append(messages)
        return _Reply(json.dumps({"sentence": queue.pop(0) if queue else ""}))

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    return asked


def _gorm(keeper: bool = True, place: str = MARKET):
    agent, _ = scene_at(place, [("Gorm Vesper", "guildhand")])
    s = agent.engine.scene
    gorm = next(a for a in s.actors.values() if a.name == "Gorm Vesper")
    gorm.pronouns = "he/him"
    if keeper:
        gorm.world_entity_id = keepers.entity_id(s.at)
    return agent, gorm


def test_the_five_narration_lines_of_beats_51_and_53_are_found():
    """5 narration sentences in quotes at beats 51 and 53: three hold the fix hint's own
    wording, two name Gorm in the third person in a line attributed to Gorm."""
    agent, gorm = _gorm(keeper=False)
    actors = dict(agent.engine.scene.actors)
    said_53 = [{"who": gorm.ref, "to": "you", "line": "Depends on the lady,"}]
    f51 = narration_in_quotes.quoted_narration(BEAT_51, [], actors)
    f53 = narration_in_quotes.quoted_narration(BEAT_53, said_53, actors)
    assert len(f51) == 2 and len(f53) == 3
    assert sum("third person" in why for _l, why in f51 + f53) == 2


def test_the_backstop_cuts_each_line_with_its_clause_and_keeps_the_narration():
    agent, gorm = _gorm(keeper=False)
    said = [{"who": gorm.ref, "to": "you", "line": "Depends on the lady,"}]
    for beat in (BEAT_51, BEAT_53):
        ctx = context(agent, beat, said=said)
        found = narration_in_quotes.find(ctx)
        out, notes = narration_in_quotes.backstop(ctx, beat, found)
        assert "'" not in out.replace("doesn't", "").replace("Gorm's", "")
        # The clause goes with its line: no "he says, his voice…" claiming a line that
        # is gone, and nothing glued together.
        assert "he says" not in out and "  " not in out
        assert out.endswith("What do you do?")
    out51, _ = narration_in_quotes.backstop(
        context(agent, BEAT_51), BEAT_51, narration_in_quotes.find(context(agent, BEAT_51)))
    assert "He looks up as the door creaks" in out51 and "He pauses, the rag" in out51


def test_a_keeper_speaking_first_is_cut_with_no_model_call(monkeypatch):
    """The beat-51 draft: Gorm, a keeper the player had not dealt with, spoke first. The
    repair used to ask the model twice and splice its narration into his quotes; now the
    line and its clause are cut, and nobody is asked."""
    agent, gorm = _gorm()
    said = [{"who": gorm.ref, "to": "you", "line": "You look like you've walked a long road,"},
            {"who": gorm.ref, "to": "you", "line": "What can I get for you?"}]
    ctx = context(agent, BEAT_51_DRAFT, said=said, player="I head toward the Velvet Veil.")
    found = [f for f in checks.run(ctx) if f.kind == "keeper-forward"]
    assert found and "at his work" in found[0].fix_hint and "turns to him" in found[0].fix_hint
    asked = _answer(monkeypatch)
    out, notes, _ = agent._repair_sentences(BEAT_51_DRAFT, found, ctx)
    assert asked == []
    assert "walked a long road" not in out and "What can I get" not in out
    assert "he says" not in out and "He pauses, the rag still in his hand" in out
    assert any(n.startswith("keeper-forward: cut") for n in notes)
    assert keeper_forward.find(context(agent, out, said=said,
                                       player="I head toward the Velvet Veil.")) == []


class _Member:
    """A rewriteable check that finds nothing on a second look, so only the repair's own
    vetting decides."""
    KINDS = frozenset({"test-kind"})

    @staticmethod
    def find(ctx):
        return []


def test_a_repair_aimed_at_a_quoted_line_rewrites_the_whole_speech_unit(monkeypatch):
    agent, gorm = _gorm(keeper=False)
    text = ("Gorm sets the tankard down. 'The city never sleeps,' he says, wiping the "
            "counter. What do you do?")
    monkeypatch.setattr(checks, "owner_of", lambda kind: _Member)
    asked = _answer(monkeypatch, "'The town never sleeps,' he says, wiping the counter.")
    f = Finding("test-kind", "city", "It is a town.", sentences=("The city never sleeps,",))
    out, _notes, _ = agent._repair_sentences(text, [f], context(agent, text))
    assert "he says, wiping the counter." in asked[0][1]["content"]
    assert out == ("Gorm sets the tankard down. 'The town never sleeps,' he says, wiping the "
                   "counter. What do you do?")


def test_a_rewrite_that_puts_narration_in_quotes_is_refused(monkeypatch):
    agent, gorm = _gorm(keeper=False)
    text = "Gorm polishes a tankard. 'What'll it be?' he asks. What do you do?"
    monkeypatch.setattr(checks, "owner_of", lambda kind: _Member)
    _answer(monkeypatch, "'Gorm Vesper remains at his post until you turn to him,' he says.")
    f = Finding("test-kind", "x", "y", sentences=("What'll it be?",))
    out, notes, _ = agent._repair_sentences(text, [f], context(agent, text))
    assert out == text
    assert any("narration in quotes" in n for n in notes)


def test_a_speech_unit_is_the_quote_and_its_clause():
    t = "He leans in. 'Depends,' he says, his voice low. He waits."
    qa = t.index("'")
    qb = t.index("'", t.index("Depends,") + 8) + 1
    a, b = _quotes.unit(t, qa, qb)
    assert t[a:b] == "'Depends,' he says, his voice low."
    t2 = "He says, 'Go home.' The door shuts."
    a, b = _quotes.unit(t2, t2.index("'"), t2.index(".'") + 2)
    assert t2[a:b] == "He says, 'Go home.'"
    # Narration that is not a clause stays outside: the head is closed with a stop.
    t3 = "He leans in, 'Depends,' he says. He waits."
    assert _quotes.cut_units(t3, ["Depends,"])[0] == "He leans in. He waits."


def test_an_untargeted_question_turns_to_the_only_keeper():
    """Beat 53: "I ask how much for a woman" read as talk with the target "how much for a
    woman", which resolves to nobody, and Gorm stayed "in the background"."""
    agent, gorm = _gorm(place=WAY_IN)
    assert [a for a in agent.engine.scene.actors.values()
            if keepers.is_keeper(getattr(a, "world_entity_id", "") or "")] == [gorm]
    s = agent.engine.scene
    reading = {"actions": [{"act": "talk", "target": "how much for a woman"}]}
    assert hooks.dealt_with(s, gorm, reading, "I ask how much for a woman")
    # A target naming somebody who is not here does not turn to the keeper.
    away = {"actions": [{"act": "talk", "target": "the harbourmaster"}]}
    assert not hooks.dealt_with(s, gorm, away, "I ask the harbourmaster about ships")


def test_an_untargeted_question_with_two_keepers_turns_to_neither():
    """The market holds its own counter keeper beside Gorm: a question into that room is
    nobody's in particular."""
    agent, gorm = _gorm()
    s = agent.engine.scene
    assert len([a for a in s.actors.values()
                if keepers.is_keeper(getattr(a, "world_entity_id", "") or "")]) >= 2
    reading = {"actions": [{"act": "talk", "target": "how much for a woman"}]}
    assert not hooks.dealt_with(s, gorm, reading, "I ask how much for a woman")
