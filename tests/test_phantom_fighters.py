"""In a fight, somebody the engine does not hold fights on the page.

Measured live 2026-10-17 on the integration branch (free narrator, gemma-4-12B): the player
and the one behind the bar were the only people in the inn, and the beat read "The other
man, his eyes wide with shock, hesitates for a heartbeat before lunging toward you, his
hands out like claws." The read back claimed nothing of him (an unlisted person is never
judged); the beat reader read him as a newcomer here, and the aftermath rightly made no
body in a fight — so he stayed on the page as a phantom fighter.
"""
from __future__ import annotations

from types import SimpleNamespace

from gm import beat_reader, beat_verify as bv, mentions
from gm.checks import phantom_fighter

# --- 2. a fighter the engine does not hold ----------------------------------------------------

LUNGE = ("The other man, his eyes wide with shock, hesitates for a heartbeat before lunging "
         "toward you, his hands out like claws.")
GAWK = "A woman by the door, her eyes wide with shock, backs away into the hallway."


def _reading(text, *newcomers):
    """A beat reader's answer as the live one gave it: the newcomer's mention "new",
    and where "here"."""
    found, comers = [], []
    for i, (phrase, sentence, where) in enumerate(newcomers, 1):
        found.append(mentions.Mention(id=f"m{i}", sentence=sentence, phrase=phrase,
                                      kind="description", model="nobody"))
        comers.append(beat_reader.Newcomer(root=f"m{i}", mentions=[f"m{i}"], where=where,
                                           words=phrase.lower().removeprefix("the ")))
    r = beat_reader.Reading(mentions=found, newcomers=comers, read=True)
    r.sentences = {mentions._key(s) for _p, s, _w in newcomers}
    return r


def _ctx(text, reading, *, fighting=True):
    return SimpleNamespace(scene=SimpleNamespace(in_encounter=fighting), attribution=reading,
                           text=text, reader={"model": "stub", "host": ""})


def test_a_newcomer_here_in_a_fight_is_asked_whether_they_fight(monkeypatch):
    text = "The man's face buckles under your strike. " + LUNGE + " " + GAWK + " What do you do?"
    reading = _reading(text, ("The other man", LUNGE, beat_reader.HERE),
                       ("A woman", GAWK, beat_reader.HERE))
    monkeypatch.setattr(bv, "ENABLED", True)
    phantom_fighter._ASKED.clear()
    asked = []

    def ask(sentence, q, **k):
        asked.append((sentence, q))
        return "lunging" in sentence

    monkeypatch.setattr(bv, "ask", ask)
    found = phantom_fighter.find(_ctx(text, reading))
    assert [f.sentences for f in found] == [(LUNGE,)]
    assert found[0].kind == "fighter-not-in-fight" and found[0].weight == 3
    assert asked[0][1].startswith("Does this sentence show The other man fighting — "
                                  "The other man themselves")
    assert "not only being attacked or grabbed, watching, shouting" in asked[0][1]
    assert len(asked) == 2, "the woman backing away was asked, and spared by the answer"
    out, notes = phantom_fighter.backstop(_ctx(text, reading), text, found)
    assert "lunging" not in out and GAWK in out and notes


def test_nobody_is_asked_out_of_a_fight_elsewhere_or_unread(monkeypatch):
    text = LUNGE + " What do you do?"
    monkeypatch.setattr(bv, "ENABLED", True)
    monkeypatch.setattr(bv, "ask", lambda *a, **k: True)
    phantom_fighter._ASKED.clear()
    here = _reading(text, ("The other man", LUNGE, beat_reader.HERE))
    assert phantom_fighter.find(_ctx(text, here, fighting=False)) == []
    away = _reading(text, ("The other man", LUNGE, beat_reader.ELSEWHERE))
    assert phantom_fighter.find(_ctx(text, away)) == []
    unread = _reading(text, ("The other man", LUNGE, beat_reader.HERE))
    unread.read = False
    assert phantom_fighter.find(_ctx(text, unread)) == []
    # A sentence a guard already took off the page is not asked about.
    assert phantom_fighter.find(_ctx("What do you do?", here)) == []
    # And with the read back off (the suite's default), nothing at all.
    monkeypatch.setattr(bv, "ENABLED", False)
    assert phantom_fighter.find(_ctx(text, here)) == []


def test_somebody_held_elsewhere_in_town_is_asked_too(monkeypatch):
    """On the replay of the live beat the same "The other man" came back "new" twice and
    as the away guard (c6) once: neither is in this fight. And "The man's" is asked as
    "The man"."""
    text = "The man's face buckles under your strike. " + LUNGE
    found = [mentions.Mention(id="m1", sentence="The man's face buckles under your strike.",
                              phrase="The man's", kind="description", model="c8"),
             mentions.Mention(id="m2", sentence=LUNGE, phrase="The other man's",
                              kind="description", model="c6")]
    reading = beat_reader.Reading(mentions=found, read=True, refs={"pc", "c8"}, away={"c6"})
    rows = phantom_fighter.candidates(_ctx(text, reading))
    assert [(s, w) for s, w, _b in rows] == [(LUNGE, "The other man")]


ASK_SECOND = "Do you turn to face the second man or move for the exit?"


def test_a_closing_question_that_offers_nobody_here_is_cut(monkeypatch):
    """Live 2026-10-17 (integration branch, gemma-4-12B): the other man's charge was cut,
    and the beat still closed "Do you turn to face the second man or move for the exit?" —
    the reader's newcomer "second man", here. No model call: the reader's closed answer and
    the question being the last sentence are the whole test. The groom then puts the plain
    hand-back in its place (`ensure_hand_back`)."""
    text = "The blade finds the gap in his jerkin. " + ASK_SECOND
    reading = _reading(text, ("the second man", ASK_SECOND, beat_reader.HERE))
    monkeypatch.setattr(bv, "ENABLED", True)
    monkeypatch.setattr(bv, "ask", lambda *a, **k: False)   # he does not FIGHT in it
    phantom_fighter._ASKED.clear()
    found = phantom_fighter.find(_ctx(text, reading))
    assert [(f.kind, f.sentences) for f in found] == [("hand-back-names-nobody", (ASK_SECOND,))]
    out, notes = phantom_fighter.backstop(_ctx(text, reading), text, found)
    assert out == "The blade finds the gap in his jerkin."
    assert notes == [f"a question about nobody here: cut {ASK_SECOND[:70]!r}"]
    from gm import narration

    assert narration.ensure_hand_back(out)[0].endswith("?")
    # Not in a fight, or a question about somebody the engine holds: left.
    assert phantom_fighter.hand_back_naming_nobody(_ctx(text, reading, fighting=False)) == ""
    held = mentions.Mention(id="m1", sentence=ASK_SECOND, phrase="the second man",
                            kind="description", model="c8")
    r = beat_reader.Reading(mentions=[held], read=True, refs={"pc", "c8"})
    assert phantom_fighter.hand_back_naming_nobody(_ctx(text, r)) == ""


def test_the_member_is_cut_only():
    """A rewrite's re-check would read the reader's mentions of the OLD sentence, find none,
    and pass a rewrite that still has him lunging."""
    assert phantom_fighter.REWRITE is False
    assert phantom_fighter.DOORS == frozenset({"plan", "turn", "npc", "outcome"})
