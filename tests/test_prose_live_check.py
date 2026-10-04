"""Two prose checks the third live turn on the merged 2026-10-03 batch showed were missing.

"I pick the crate back up, then tip the coins from the pouch into my coin purse" — the
engine (now) moved the crate into Kesst's goods and nothing out, and the page read:

    "Beside you, the smith, Korvu, reaches out with a hand calloused into leather and
    takes the crate from you."

Two untruths in one sentence: the crate handed away though the engine kept it with her,
and a people's name (Korvu) given to the smith as his own. Item 14's fix stopped the
record being named that way; nothing read the page.

The crate half — and the refused sale settled on the page, which this file also held —
retired on 2026-10-03 with `gm/checks/thing_kept.py` and `trade_claimed.py` into the beat
read back (gm/checks/beat_verified.py), which measured R 0.80 and 1.00 against their 0.40
and 0.50 on the bench, both at precision 1.00 (docs/beat-verify.md). Their measurements
moved with them: tests/test_beat_verify_diff.py, and the covered-member repair test to
tests/test_beat_verified_in_the_turn.py.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from gm.checks import peoples_name
from rules.engine import Scene
from rules.sheet import load_pc
from world import loader

PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")
LIVE = ("Beside you, the smith, Korvu, reaches out with a hand calloused into leather and "
        "takes the crate from you.")


def _ctx(text, *, goods=None, outcomes=()):
    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    pc.goods = dict(goods or {})
    s.add(pc)
    return SimpleNamespace(text=text, scene=s, world=PANGRELLA, outcomes=tuple(outcomes))


# --- a people's name as one person's name -------------------------------------------------

@pytest.mark.parametrize("sentence, fixed", [
    (LIVE, "Beside you, the smith reaches out with a hand calloused into leather and "
           "takes the crate from you."),
    # The items save, turn 57 and turn 62, as the narrator wrote them.
    ("The laborer—a man named Korvu, his face etched with the deep lines of a life spent "
     "under heavy loads—stops his struggle and looks up.",
     "The laborer—a man, his face etched with the deep lines of a life spent under heavy "
     "loads—stops his struggle and looks up."),
    ("Korvu leans his head back against the timber post.",
     "The Korvu leans his head back against the timber post."),
])
def test_a_peoples_name_given_to_a_person_is_caught_and_respelled(sentence, fixed):
    ctx = _ctx(sentence)
    found = peoples_name.find(ctx)
    assert [f.kind for f in found] == ["peoples-name-as-name"]
    kept, _ = peoples_name.backstop(ctx, sentence, found)
    assert kept == fixed


@pytest.mark.parametrize("sentence", [
    "The merchant with a heavy pack is of the Korvu people: hair the colour of wet rope.",
    "A Korvu porter shoulders past you.",
    "The Korvu keep to the upper terraces.",
    "One of the Korvu watches from the doorway.",
    "Korvu people crowd the square.",
    "'Korvu leans on nobody,' the clerk says.",               # a character may say it
])
def test_the_people_themselves_are_not_flagged(sentence):
    assert peoples_name.find(_ctx(sentence)) == []


def test_a_peoples_name_is_cut_never_rewritten():
    """Measured live on the merged structured-turn branch: the rewrite turned "The smith,
    Korvu, leans over the crate" into "The smith, the man in the heavy coat, leans…" —
    another person's description, copied from the check's own fix hint. The backstop's
    respelling is exact, so the model is never asked."""
    assert peoples_name.REWRITE is False
    ctx = _ctx("The smith, Korvu, leans over the crate you just set down.")
    found = peoples_name.find(ctx)
    kept, _ = peoples_name.backstop(ctx, ctx.text, found)
    assert kept == "The smith leans over the crate you just set down."
