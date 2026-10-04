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


def test_a_suggestion_about_a_woman_the_smith_spoke_of_is_left_alone():
    """Measured live on the merged structured-turn branch: the smith said "There is a woman
    who operates near the old tannery. She is discreet…", the suggestion read "I ask her
    name or where exactly she is located", and with the smith the only one present it was
    rewritten to "I ask his name or where exactly he is located" — the fence turned into
    the smith. A pronoun the beat just used is left for whoever the beat used it for."""
    from play.aftermath import suggestion_pronouns
    from rules.bestiary import instantiate

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    smith = instantiate("guildhand", scene=s, name="the smith")
    smith.gender, smith.pronouns = "man", "he/him"
    s.add(smith)
    said = "There is a woman who operates near the old tannery. She is discreet."
    camp = SimpleNamespace(suggestions=["I ask her name or where exactly she is located."])
    ctx = SimpleNamespace(campaign=camp, scene=s, text=f"'{said}' he says.",
                          said=[{"who": smith.ref, "to": "you", "line": said}],
                          talking_after=(smith.ref,), attribution=None, reading=None)
    assert suggestion_pronouns.step(ctx) == []
    assert camp.suggestions == ["I ask her name or where exactly she is located."]
    # The measured defect it was built for still holds: nobody spoken of as "she", only
    # the smith on the page, and "I ask her…" is his.
    camp.suggestions = ["I ask her what she is looking for."]
    ctx.text, ctx.said = "'Back again,' he says.", [{"who": smith.ref, "to": "you",
                                                      "line": "Back again."}]
    suggestion_pronouns.step(ctx)
    assert camp.suggestions == ["I ask him what he is looking for."]
