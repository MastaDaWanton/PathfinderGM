"""`misgendered-pc`: the player's pronoun swapped in place, never the line cut.

Until 2026-10-17 the finding had no repair but the whole-beat rewrite. A refused rewrite —
in a fight, the only one — shipped the pronoun, and docs/narrator-guards.md listed it as
"left: no cut that would not take dialogue or a whole line". A pronoun is one word, and
the grammar of its swap is a fixed map; whether a word MEANS the player is a reading.

Measured on the scratch saves' shipped beats the same day, the finder itself was the first
fault: 12 beats flagged, 11 of them the ±90-character window cutting a word at its edge —
"the competing cries" read as "he competing", "The ground here" as "The ground he" — on a
she/her character's opening line. The twelfth was an intimate scene whose five she/her were
all the partner's, around her "I want more, Sam". After the window takes whole words and a
narration pronoun is not held to a name only said aloud, 0 of the 12 are flagged; the
made cases below (the original report among them) still are.

The reads, probed on eleven labelled sentences x2 (gemma-4-12B): asked about the marked
wrong word ("does «his» mean Thessaly Corr?") the reader matched the word's gender to the
name and answered 8 of 22; shown the word in its they-form and asked who it points to,
copied from the passage, 20 of 22. Whether "his"/"her" owns what follows: 12 of 12.
"""
from __future__ import annotations

import json

from gm import agent as agent_mod
from gm import beat_verify as bv
from gm import narration

from _a_truth import MARKET, scene_at

# The opening line of a she/her character's game, as it shipped (alch-c, 2026-10): the
# window's edge fell inside "the competing" and the finder read "he".
OPENING = (
    "The air in the market is thick with the competing cries of hawkers, the smell of fresh "
    "bread, fish, and trodden dung.  You are Kesst Vayr, a Zhilakai with a rapier at your "
    "side and clad in leather. You have come to sell what you carry.")
# The intimate beat's lines (sam.json, 2026-09-30): every pronoun is the partner's.
PARTNER = ("\"More,\" she gasps against your lips, her voice cracked and desperate. \"I want "
           "more, Sam.\" You grunt in response, your hands gripping her hips. \"Sam...\" she "
           "cries out, her voice a broken plea.")
REPORT = "One of them spots you and points, exclaiming loudly, 'It's him! Thessaly Corr!'"


def test_a_word_cut_at_the_windows_edge_is_no_pronoun():
    at = OPENING.index("Kesst Vayr")
    # The window reaches back into "the competing": its edge falls inside a word.
    assert OPENING[at - narration.MISGENDER_WINDOW:].startswith("he competing")
    assert narration.misgendered(OPENING, "Kesst Vayr", "she/her") == []
    assert narration.misgendered("You are Kesst Vayr. The ground here is soft.",
                                 "Kesst Vayr", "she/her") == []


def test_a_narration_pronoun_beside_a_name_only_said_aloud_is_not_the_players():
    assert narration.misgendered(PARTNER, "Sam", "he/him") == []
    assert narration.misgendered("'Sit down, Kesst Vayr,' she says, and pushes the bowl "
                                 "across to you.", "Kesst Vayr", "he/him") == []
    # Said aloud about the player, it is still found — the report that made the finder.
    assert narration.misgendered(REPORT, "Thessaly Corr", "she/her") == ["him"]
    toks = narration.misgendered_tokens(REPORT, "Thessaly Corr", "she/her")
    assert [(REPORT[a:b], t) for a, b, t, _lo, _hi in toks] == [("him", "him")]


def test_the_swap_is_a_fixed_table_with_two_questions_asked():
    sw = narration.pronoun_swap
    assert sw("she/her", "him") == "her" and sw("she/her", "He") == "She"
    assert sw("she/her", "himself") == "herself"
    assert sw("she/her", "his", owns=True) == "her" and sw("she/her", "his", owns=False) == "hers"
    assert sw("he/him", "her", owns=True) == "his" and sw("he/him", "her", owns=False) == "him"
    assert sw("he/him", "she") == "he" and sw("he/him", "hers") == "his"
    # Unanswered, an ambiguous form is not guessed.
    assert sw("she/her", "his") == "" and sw("he/him", "her", owns=None) == ""
    # A they/them character: object, possessive and reflexive; never "he" -> "they",
    # which would leave "they walks".
    assert sw("they/them", "him") == "them" and sw("they/them", "her", owns=True) == "their"
    assert sw("they/them", "himself") == "themself" and sw("they/them", "he") == ""
    assert narration.pronoun_neutral("He") == "they"
    assert narration.pronoun_neutral("his", owns=False) == "theirs"


def _agent(monkeypatch, means=True, owns=True):
    agent, _ = scene_at(MARKET)
    pc = agent.engine.scene.pc()
    pc.name, pc.pronouns = "Thessaly Corr", "she/her"
    agent.prose_model = "stub"
    monkeypatch.setattr(bv, "ENABLED", True)
    asked = []

    def points_to(passage, word, who, **k):
        asked.append(("who", passage, word, who))
        return means

    def owns_fn(passage, token, **k):
        asked.append(("owns", passage, token))
        return owns

    monkeypatch.setattr(bv, "pronoun_points_to", points_to)
    monkeypatch.setattr(bv, "pronoun_owns", owns_fn)
    return agent, asked


def test_a_pronoun_that_means_the_player_is_swapped_and_nothing_else_moves(monkeypatch):
    agent, asked = _agent(monkeypatch)
    out, notes, cleared = agent._swap_pronouns(REPORT)
    assert out == REPORT.replace("It's him!", "It's her!") and cleared
    # Asked in its they-form, never the gendered word beside the name.
    assert asked == [("who", "One of them spots you and points, exclaiming loudly, 'It's "
                             "«them»! Thessaly Corr!'", "them", "Thessaly Corr")]
    assert notes == ["misgendered-pc: 'him' -> 'her' in \"One of them spots you and points, "
                     "exclaiming loudly, 'It's «him»! Thes\""]
    said = "'That's Thessaly Corr,' a voice mutters. 'I'd know his face anywhere.'"
    out, _n, _c = agent._swap_pronouns(said)
    assert out == said.replace("his face", "her face")
    assert asked[-2][0] == "owns" and asked[-1][2] == "their"


def test_refuted_unanswered_and_unknown_are_left_as_written(monkeypatch):
    agent, _ = _agent(monkeypatch, means=False)
    out, notes, cleared = agent._swap_pronouns(REPORT)
    assert out == REPORT and cleared and "refuted" in notes[0]
    agent, _ = _agent(monkeypatch, means=None)
    out, notes, cleared = agent._swap_pronouns(REPORT)
    assert out == REPORT and not cleared and "unanswered" in notes[0]
    agent, _ = _agent(monkeypatch, owns=None)
    said = "'That's Thessaly Corr,' a voice mutters. 'I'd know his face anywhere.'"
    out, notes, cleared = agent._swap_pronouns(said)
    assert out == said and not cleared and "what follows 'his' went unanswered" in notes[0]
    # With the read off (the suite) nothing is swapped: a wrong swap misgenders whoever
    # the word did mean.
    monkeypatch.setattr(bv, "ENABLED", False)
    assert agent._swap_pronouns(REPORT) == (REPORT, [], False)


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def test_a_refused_rewrite_no_longer_ships_the_pronoun(monkeypatch):
    """The polish path: the rewrite comes back no better (refused), and the pronoun is
    swapped in the draft instead of being logged `unrepaired: misgendered-pc`."""
    agent, _ = _agent(monkeypatch)
    draft = REPORT + " The crowd presses closer. What do you do?"
    monkeypatch.setattr(agent_mod.client, "chat",
                        lambda *a, **k: _Reply(json.dumps({"narration": draft})))
    out, notes, _ = agent.polish(draft)
    assert "It's her! Thessaly Corr!" in out
    assert not any(n.startswith("unrepaired") and "misgendered-pc" in n for n in notes)
    assert any("'him' -> 'her'" in n for n in notes)
