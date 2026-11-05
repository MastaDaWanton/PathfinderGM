"""Who may refuse a clash the tells check's first read found (2026-11-03).

`beat_verify.against_tells` reads every sentence of a planned beat against its tells, and
until 2026-11-03 put every clash it found to a fact-first second read, which refused any
it did not call "cannot both be true". Measured offline on the 102 labelled bench beats
(22 contradictions a tell can catch, 71 clean beats):

  * both reads, as shipped:  5 of 22 caught,  5 of 71 clean beats flagged;
  * the first read alone:   11 of 22 caught, 12 of 71 clean beats flagged;
  * the second read refusing only a clash that does not echo its tell: 9 of 22, 5 of 71.

The second read's refusals were of two kinds. Right: "the two guardsmen" against "the
guardsman and the second guardsman" (5 clean beats), sharing no word with the tell. Wrong:
"you wrench your arms free from their grip" against a tell offering "wrench free" as a way
out — 4 of 4 true clashes refused as "tells it", fooled by the tell's own words.

The names and prose here are synthetic; the numbers are in docs/narration-faithfulness.md.
"""
from __future__ import annotations

import json

import pytest

from gm import beat_verify as bv

HELD = ["Mira Holt is held by the bailiff: there is no leaving until his hold is broken (slip "
        "it, or wrench free) or he is fought."]
TAKEN_IN = ["The watchman and the second watchman take Mira Holt in to the lock-up."]
FINE = ["The reeve passes sentence on Mira Holt. The fine is 6 gold pieces; Mira Holt pays 6 "
        "gold pieces."]


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _chat(*replies):
    queue = [json.dumps(r) for r in replies]
    asked: list = []

    def chat(messages, *a, **k):
        asked.append(messages)
        if not queue:
            raise AssertionError("asked more than the test scripted")
        return _Reply(queue.pop(0))

    chat.asked = asked
    return chat


def _clash(fact, words):
    return {"1": {"verdict": "contradicts", "fact": fact, "words": words}}


# --- what echoes a tell -----------------------------------------------------------------

@pytest.mark.parametrize("words, tell, echoes", [
    # The bench's wrong refusals: the way out the tell offers, written taken.
    ("You wrench your arm out of the bailiff's grip", HELD[0], True),
    ("you wrench your arms free from their grip", HELD[0], True),
    ("breaking their hold as you struggle free", HELD[0], True),
    # The bench's right refusals: who, counted differently. No stemming, so "watchmen"
    # is not "watchman".
    ("the two watchmen", TAKEN_IN[0], False),
    # One shared noun is the topic, not the tell's phrase.
    ("you pay it in gold", FINE[0], False),
    # A name says who the sentence is about; it echoes nothing — a clash on who, the
    # second read's to judge.
    ("Odo Brack and the two watchmen",
     "Odo Brack, the watchman and the second watchman take Mira Holt in.", False),
    # A function word is no echo: "until evening" against "until his hold is broken".
    ("until evening", HELD[0], False),
])
def test_an_echo_is_two_of_the_tells_own_words(words, tell, echoes):
    assert bv.echoes_tell(words, tell) is echoes


# --- the three vetoes -------------------------------------------------------------------

def test_an_echoing_clash_is_not_put_to_the_second_read(monkeypatch):
    """The wrench-free slip under the "echo" veto: the first read's clash repeats the
    tell's own words, the shape the second read refused on 4 of 4 bench beats, so it is
    kept without asking — one call, not two."""
    monkeypatch.setenv("PATHFINDER_GM_TELLS_VETO", "echo")
    chat = _chat(_clash("F1", "you wrench your arms free from their grip"))
    got = bv.against_tells("As they lead you on, you wrench your arms free from their grip.",
                           HELD, who="Mira Holt", chat=chat)
    assert [c.words for c in got.clashes] == ["you wrench your arms free from their grip"]
    assert got.calls == 1 and len(chat.asked) == 1
    assert got.clashes[0].as_log()["unasked"] == "echoes the tell"


def test_a_clash_on_who_is_still_put_to_the_second_read(monkeypatch):
    """The false alarm the second read was built for, under the "echo" veto: "the two
    watchmen" against "the watchman and the second watchman" shares no word with the tell,
    so it is asked, and "tells it" refuses it — 5 clean bench beats spared a remake."""
    monkeypatch.setenv("PATHFINDER_GM_TELLS_VETO", "echo")
    chat = _chat(_clash("F1", "the two watchmen"), {"answer": "tells it"})
    got = bv.against_tells("You walk to the lock-up between the two watchmen.", TAKEN_IN,
                           who="Mira Holt", chat=chat)
    assert not got.clashes and [c.words for c in got.refused] == ["the two watchmen"]
    assert got.calls == 2 and got.refused[0].as_log()["second"] == "tells it"


def test_the_first_read_alone_asks_nothing_more(monkeypatch):
    monkeypatch.setenv("PATHFINDER_GM_TELLS_VETO", "none")
    chat = _chat(_clash("F1", "the two watchmen"))
    got = bv.against_tells("You walk to the lock-up between the two watchmen.", TAKEN_IN,
                           who="Mira Holt", chat=chat)
    assert [c.words for c in got.clashes] == ["the two watchmen"] and got.calls == 1
    assert got.clashes[0].as_log()["unasked"] == "the first read alone"


def test_the_second_read_refuses_any_clash_under_the_second_veto(monkeypatch):
    """Today's shape before 2026-11-03, kept for a bench's baseline: the wrench-free clash
    asked and refused — the measured miss."""
    monkeypatch.setenv("PATHFINDER_GM_TELLS_VETO", "second")
    chat = _chat(_clash("F1", "you wrench your arms free from their grip"),
                 {"answer": "tells it"})
    got = bv.against_tells("As they lead you on, you wrench your arms free from their grip.",
                           HELD, who="Mira Holt", chat=chat)
    assert not got.clashes and got.calls == 2


def test_the_veto_is_no_settings_switch(monkeypatch):
    """The owner's ruling of 2026-11-02: the check is always on, with no Settings switch.
    The veto is code's (`TELLS_VETO`); only an environment variable the app never sets
    moves it, for a bench. Anything else it might say is the default."""
    monkeypatch.delenv("PATHFINDER_GM_TELLS_VETO", raising=False)
    assert bv.tells_veto() == bv.TELLS_VETO
    monkeypatch.setenv("PATHFINDER_GM_TELLS_VETO", "anything")
    assert bv.tells_veto() == bv.TELLS_VETO


def test_the_first_read_alone_is_the_default(monkeypatch):
    """Measured on full turns, 2026-11-03 (two blind scorers a round). The slip the veto
    decides: the escort's hold written broken on the walk to the gallows ("you wrench
    yourself free from their grip" beside "slip it or wrench free — or fight") shipped on
    6 of 6 runs with the second read and 0 of 6 with the first read alone; over the whole
    bench the three vetoes were within noise (errors 13/11, 15/13, 12/10 in 60 beats), the
    remakes did not double (10 and 10), and seconds a turn did not move (median 31.2 s and
    31.1 s)."""
    monkeypatch.delenv("PATHFINDER_GM_TELLS_VETO", raising=False)
    assert bv.TELLS_VETO == "none" and bv.tells_veto() == "none"
    chat = _chat(_clash("F1", "you wrench yourself free from their grip"))
    got = bv.against_tells("As they lead you on, you wrench yourself free from their grip.",
                           HELD, who="Mira Holt", chat=chat)
    assert [c.words for c in got.clashes] == ["you wrench yourself free from their grip"]
    assert got.calls == 1


def test_the_engines_line_in_a_cut_slot_loses_its_bracketed_labels(monkeypatch):
    """Measured on the first-read-alone bench (2026-11-03): 2 of 6 gallows catches failed
    their remake, and the act slot took the engine's own line — "slip it (Escape Artist) or
    wrench free (a combat manoeuvre)" — whose "(Escape Artist)" the un-namer then took for a
    person: "slip it (the stranger)" on the page, both scorers marking it broken. The
    labels are the table's choice, not the story's: they go."""

    from gm import planned

    out = planned.Planned(text="", slots=[])
    out.slots = [{"key": "fact1", "max": 220, "tells": HELD,
                  "wrote": "As they lead you on, you wrench your arms free from their grip.",
                  "messages": [{"role": "system", "content": "plan"},
                               {"role": "user", "content": 'Now write slot "fact1"'}],
                  "reply": json.dumps({"text": "x"})}]

    def call_slot(s, messages, who, **kw):
        reply = _Reply(json.dumps({"text": "You wrench your arms free and run."}))
        return reply, reply.json()

    monkeypatch.setattr(planned, "call_slot", call_slot)
    chat = _chat(_clash("F1", "you wrench your arms free from their grip"),
                 _clash("F1", "You wrench your arms free and run"))
    planned._tells_kept(out, ("stub", "", "ollama", ""),
                        lambda text, tells: bv.against_tells(text, tells, who="Mira Holt",
                                                             chat=chat), HELD)
    assert out.slots[0]["wrote"] == ("Mira Holt is held by the bailiff: there is no leaving "
                                     "until his hold is broken or he is fought.")
