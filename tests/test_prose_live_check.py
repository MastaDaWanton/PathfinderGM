"""Two prose checks the third live turn on the merged 2026-10-03 batch showed were missing.

"I pick the crate back up, then tip the coins from the pouch into my coin purse" — the
engine (now) moved the crate into Kesst's goods and nothing out, and the page read:

    "Beside you, the smith, Korvu, reaches out with a hand calloused into leather and
    takes the crate from you."

Two untruths in one sentence: the crate handed away though the engine kept it with her,
and a people's name (Korvu) given to the smith as his own. Item 14's fix stopped the
record being named that way; nothing read the page.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from gm.checks import peoples_name, thing_kept
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


# --- a thing still held, given away on the page -------------------------------------------

def test_the_live_sentence_hands_away_a_crate_the_engine_kept():
    ctx = _ctx(LIVE + " What do you do?", goods={"crate": 1, "pouch": 1})
    found = thing_kept.find(ctx)
    assert [f.kind for f in found] == ["thing-kept-shown-given"]
    kept, notes = thing_kept.backstop(ctx, ctx.text, found)
    assert "crate" not in kept and kept.endswith("What do you do?") and notes


@pytest.mark.parametrize("sentence", [
    "You hand him the crate without a word.",
    "The clerk relieves you of the crate.",
    "She snatches the pouch out of your fingers.",
])
def test_every_way_of_handing_it_over_counts(sentence):
    assert thing_kept.find(_ctx(sentence, goods={"crate": 1, "pouch": 1}))


@pytest.mark.parametrize("sentence", [
    "You heave the crate back onto your shoulder.",          # the player holding it
    "The smith eyes the crate on your shoulder.",            # looking is not taking
    "The smith takes the hammer from the rack.",             # not one of her things
    "He reaches for the crate, then thinks better of it.",   # reaching is not taking
])
def test_holding_looking_and_other_things_are_not_flagged(sentence):
    assert thing_kept.find(_ctx(sentence, goods={"crate": 1})) == []


def test_a_hand_over_the_engine_made_may_be_shown():
    """A sale or a give this turn took it out of her hands: then the prose is right."""
    sold = [{"op": "sell", "status": "resolved",
             "effects": [{"kind": "sold", "item": "crate", "from": "pc", "to": "c12"}]}]
    assert thing_kept.find(_ctx(LIVE, goods={"pouch": 1}, outcomes=sold)) == []
    assert thing_kept.find(_ctx(LIVE, goods={"crate": 1}, outcomes=sold)) == []


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


# --- a trade the engine did not make, settled on the page ---------------------------------

from gm.checks import trade_claimed  # noqa: E402

REFUSED = [{"op": "sell", "status": "refused",
            "tell": "The smith's counter is not open yet; it opens at first light.",
            "effects": []}]
SOLD_LIVE = ("The transaction is finalized. The heavy clink of the coin is the only thing "
             "that breaks the silence of the forge. The smith turns toward the quenching "
             "vats. What do you do?")


def _trade_ctx(text, outcomes=(), reading=None):
    ctx = _ctx(text, goods={"crate": 1}, outcomes=outcomes)
    ctx.reading = reading
    return ctx


def test_a_refused_sale_settled_in_the_prose_is_cut_and_the_refusal_stands():
    """Measured live: the engine refused the sale at half past one in the morning, and the
    page opened "The transaction is finalized. The heavy clink of the coin…" with the
    refusal nowhere on it."""
    ctx = _trade_ctx(SOLD_LIVE, REFUSED)
    found = trade_claimed.find(ctx)
    assert [f.kind for f in found] == ["trade-claimed"]
    assert len(found[0].sentences) == 2
    kept, _ = trade_claimed.backstop(ctx, SOLD_LIVE, found)
    assert kept == ("The smith's counter is not open yet; it opens at first light. "
                    "The smith turns toward the quenching vats. What do you do?")


def test_a_declared_sale_that_never_resolved_is_held_too():
    read = {"actions": [{"act": "sell", "object": "the crate", "target": "the smith"}]}
    assert trade_claimed.find(_trade_ctx(SOLD_LIVE, (), read))


def test_a_sale_the_engine_made_may_be_shown():
    sold = [{"op": "sell", "status": "resolved", "tell": "", "effects": []}]
    assert trade_claimed.find(_trade_ctx(SOLD_LIVE, sold)) == []


def test_no_trade_at_all_is_no_finding():
    """Coin clinking in a beat where nobody traded is somebody else's business."""
    assert trade_claimed.find(_trade_ctx(SOLD_LIVE)) == []


def test_the_last_pass_asks_every_member_not_only_the_heaviest():
    """Measured live: "Korvu takes the crate with a grunt" was flagged by thing_kept and
    peoples_name; the lighter finding was dropped as covered, the rewrite fixed the crate,
    and "Korvu eyes the crate" shipped because peoples_name was never asked again."""
    import inspect

    from gm.agent import GMAgent

    src = inspect.getsource(GMAgent._repair_sentences)
    assert "for member in checks.registered():" in src
