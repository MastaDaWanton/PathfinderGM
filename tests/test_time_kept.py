"""A turn the engine passed no time on is never a night's sleep on the page.

Measured on a scratch save of 2026-10-16 (gemma-4-12B, Pangrella, turn_log row 125):
"I say goodbye to the barkeep, go back up to my room and sleep until dawn" had every plan
refused (a `say to=new1` nobody introduced), the turn fell to narration only, and the
page slept the night — "You collapse onto the pallet… sleep takes hold. When you finally
stir, the light has changed" — with the engine's clock unmoved at 2305. The read-back ran
on that door: its move row's stairs went nowhere the engine lists and its hour row's "the
sun is hanging lower in the sky" was true of the unmoved clock, so nothing was repaired.
`gm/checks/time_kept.py` asks the one question no row asked.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from gm import checks, deed_reader
from gm.checks import time_kept
from rules.engine import Scene
from rules.sheet import load_pc

# The beat as it shipped (the transcript of that save, beat 35), verbatim but for the
# hour word the hour repair had already put right.
SLEPT = ("You offer a final nod to the man behind the bar—a silent acknowledgment of the "
         "transaction and the weary peace of the afternoon. He accepts the gesture with a "
         "slow, deliberate blink of his eyes. You turn and make your way back up the "
         "creaking stairs, the wood groaning under your weight as it echoes through the "
         "empty hall. Your room is a small, dim space where the air is heavy with the scent "
         "of dry straw and old timber. You collapse onto the pallet, the rough fabric "
         "against your cheek, and let the exhaustion finally pull you under. The world of "
         "Khalmorin falls away as sleep takes hold. When you finally stir, the light has "
         "changed; the sun is hanging lower in the sky, casting long, golden fingers "
         "through the high, small windows. What do you do?")


class _Reply:
    def __init__(self, payload):
        self.text = json.dumps(payload)
        self.seconds, self.model = 0.3, "stub"

    def json(self):
        return json.loads(self.text)


def _ctx(monkeypatch, answer, *, was=2305, now=2305):
    monkeypatch.setattr(deed_reader, "ENABLED", True)
    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = now
    seen = []

    def chat(messages, *a, **k):
        seen.append(messages)
        return _Reply({"sentence": str(answer)})

    real = deed_reader.read_slept
    monkeypatch.setattr(deed_reader, "read_slept",
                        lambda *a, **k: real(*a, **dict(k, chat=chat)))
    ctx = SimpleNamespace(scene=s, text=SLEPT, was_clock=was,
                          reader={"model": "stub", "host": "h"})
    return ctx, seen


def test_the_night_slept_on_an_unmoved_clock_is_cut(monkeypatch):
    """Sentence 5 ("You collapse onto the pallet… pull you under") is where the player goes
    under; the beat is cut from there and closed on the engine's fact."""
    ctx, seen = _ctx(monkeypatch, 5)
    found = time_kept.find(ctx)
    assert [f.kind for f in found] == ["time-passed-unrun"]
    assert found[0].sentences[0].startswith("You collapse onto the pallet")
    assert "NO time passes" in seen[0][0]["content"]
    out, notes = time_kept.backstop(ctx, SLEPT, found)
    assert "sleep takes hold" not in out and "light has changed" not in out
    assert out.startswith("You offer a final nod") and notes
    assert time_kept.authored_in(out) == [time_kept.POOL[0]]


def test_a_night_the_engine_did_pass_is_never_asked_about(monkeypatch):
    ctx, seen = _ctx(monkeypatch, 5, was=1825, now=2305)
    assert time_kept.find(ctx) == [] and seen == []


def test_a_sentence_that_is_not_about_the_player_is_no_answer(monkeypatch):
    ctx, _ = _ctx(monkeypatch, 2)      # "He accepts the gesture…": about the barkeep
    assert time_kept.find(ctx) == []


def test_nothing_named_nothing_cut(monkeypatch):
    ctx, _ = _ctx(monkeypatch, 0)
    assert time_kept.find(ctx) == []


def test_no_clock_to_compare_reads_nothing(monkeypatch):
    ctx, seen = _ctx(monkeypatch, 5, was=None)
    assert time_kept.find(ctx) == [] and seen == []


def test_it_is_a_registered_member_on_the_turn_door():
    assert time_kept in checks.registered()
    assert time_kept.DOORS == frozenset({"turn"})
