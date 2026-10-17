"""The read back judges a gift by the floor, a deal the engine never had, and every check.

Measured live on 0.2.20's code (2026-10-16, a scratch save of this session): the player
helped the smith lift his cart and asked him for fair pay. The engine rolled both — the
help failed ("misses the Strength check to help the smith by 1: no help"), the smith lifted
it anyway, and the request failed ("the smith says no and pays nothing: nothing changes
hands"). The free narrator then wrote "He reaches into a pouch at his belt … pulls out a
piece of coarse, stained leather. He tosses it into the dirt between you. 'There's your
pay.'" and ended the beat "You are still here, and the trade is finished."

The read back heard all of it and judged it wrongly twice:

  * the toss was read as `something else`, c4 -> the floor, and skipped — only a hand-over
    INTO the player's hands was judged (fix/requests-and-rewards), so a thing a person
    produces and drops, tosses or sets down for the player escaped;
  * "the trade is finished" was read as a settled sale of `something else`, and the repair
    wrote "You are still here, and the trade is not finished." — a trade still open, on a
    turn with no sale, purchase or haggle at all.

And nothing compared the page with a check's verdict at all: the claims scrubber is
English regex, and backs any success claim once a turn has any verdict. The attempts
question (`beat_verify.attempts_of` / `read`'s third call) asks, per check and save the
engine settled, whether the beat shows it succeeding, failing, or neither, and code
compares. docs/beat-verify.md, "Gifts by the floor, deals nobody made, and the attempts",
has the bench.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from gm import beat_verify as bv

PC = bv.Person("pc", "Kesst Vayr", pc=True)
SMITH = bv.Person("c4", "the smith", "Korvu")
GUARD = bv.Person("c1", "the guard by the mounting block", "Korvu")

REFUSED_PAY = {"intent_id": "i4", "op": "check", "status": "resolved", "actor": "pc",
               "verdict": "failure",
               "rolls": [{"label": "Diplomacy check", "visibility": "player"}],
               "effects": [{"kind": "request", "ref": "c4", "request": "payment",
                            "granted": False}],
               "because": "the player asks the smith for payment",
               "tell": "Kesst Vayr asks the smith for payment for the work. Kesst Vayr "
                       "misses the diplomacy check by 6. the smith says no and pays "
                       "nothing: nothing changes hands."}
AID = {"intent_id": "i3", "op": "check", "status": "resolved", "actor": "pc",
       "verdict": "success",
       "rolls": [{"label": "Strength check to help the smith", "visibility": "player"},
                 {"label": "the smith Strength check", "visibility": "hidden"}],
       "effects": [{"kind": "aid", "ref": "c4", "made": False, "bonus": 0, "task_dc": 10,
                    "done": True}],
       "tell": "Kesst Vayr misses the Strength check to help the smith by 1: no help. the "
               "smith makes the Strength check by 4: the attempt succeeds."}
TOSS = "He tosses it into the dirt between you."
FINISHED = "You are still here, and the trade is finished."


def facts(*outcomes, **kw):
    base = dict(start="the gate", end="the gate", places=("the gate", "the market"),
                people=(PC, GUARD, SMITH), clock=1809, outcomes=tuple(outcomes))
    base.update(kw)
    return bv.Facts(**base)


def claim(category, sentence="The sentence as written.", **slots):
    return bv.Claim(category, slots, quote=sentence, sentence=sentence, valid=True)


# --- 1. an unlisted thing parted with by the floor ------------------------------------------

def test_a_thing_tossed_into_the_dirt_for_the_player_is_a_contradiction():
    """The live beat's own read-back claim (`something else`, c4 -> the floor, the quote
    "He tosses it into the dirt between you") raised nothing on 0.2.20. Now it is a hands
    contradiction, its fact naming what the smith must not do, and its second read asks
    whether the thing is given FOR the player — the question code cannot answer."""
    f = facts(AID, REFUSED_PAY)
    found = bv.diff([claim("hands", TOSS, item=bv.OTHER_THING, **{"from": "c4"},
                           to=bv.FLOOR)], f, TOSS)
    assert [(d.kind, d.category) for d in found] == [("contradiction", "hands")]
    assert found[0].fact.startswith("Nothing was given to the player: the smith pays nothing")
    assert "lands at the player's feet" in found[0].fact
    q = bv.question(found[0], f)
    assert "the smith gives something to you" in q and "as payment or a gift" in q
    # Read as "nobody" (tossed away) it is the same question.
    assert bv.diff([claim("hands", TOSS, item=bv.OTHER_THING, **{"from": "c4"},
                          to=bv.NOBODY)], f, TOSS)


def test_scenery_and_the_engines_own_moves_are_left_alone():
    """Precision. A crow dropping a feather is nobody listed; a thing the engine itself
    set down for the smith, or a turn on which the engine paid the player, backs whatever
    the page calls it. (The smith laying his own hammer on the anvil is the second read's:
    on the bench it refuted that and the bent nail on the scrap heap, 2 of 2.)"""
    feather = claim("hands", "A crow drops a feather into the dirt beside you.",
                    item=bv.OTHER_THING, **{"from": bv.NEW_PERSON}, to=bv.FLOOR)
    assert bv.diff([feather], facts(REFUSED_PAY)) == []
    dropped = {"op": "give", "status": "resolved", "actor": "c4", "effects": [
        {"ref": "c4", "kind": "give", "item": "hammer", "from": "c4", "to": ""}]}
    paid = {"op": "check", "status": "resolved", "effects": [
        {"kind": "give", "item": "coin", "count": 10, "how": "paid", "from": "c4",
         "to": "pc"}]}
    toss = claim("hands", TOSS, item=bv.OTHER_THING, **{"from": "c4"}, to=bv.FLOOR)
    assert bv.diff([toss], facts(dropped)) == []
    assert bv.diff([toss], facts(paid)) == []
    # Somebody held elsewhere is the `absent` reader's, not this one's.
    away = bv.Person("c4", "the smith", "Korvu", here=False)
    assert bv.diff([toss], facts(REFUSED_PAY, people=(PC, GUARD, away))) == []


def test_a_deal_the_engine_never_had_is_not_judged():
    """The live beat's "the trade is finished": read back as a settled sale of
    `something else` on a turn with no sale, purchase or haggle, cut as "Nothing was sold
    or bought", and rewritten "…the trade is not finished." Judged now only when the
    engine has a side of it — a trade op this turn, refused or not, or a thing it names."""
    deal = claim("trade", FINISHED, item=bv.OTHER_THING, seller="c4", buyer="pc",
                 settled=True)
    assert bv.diff([deal], facts(AID, REFUSED_PAY), FINISHED) == []
    refused_sale = {"op": "sell", "status": "refused", "effects": [],
                    "tell": "The smith's counter is closed."}
    assert [d.category for d in bv.diff([deal], facts(refused_sale), FINISHED)] == ["trade"]
    haggled = {"op": "haggle", "status": "resolved", "verdict": "failure", "effects": []}
    assert [d.category for d in bv.diff([deal], facts(haggled), FINISHED)] == ["trade"]
    # A thing the engine names and still holds is not sold, trade op or none (kesst:18).
    crate = claim("trade", "the transaction is finalized", item="crate", seller="pc",
                  buyer="c4", settled=True)
    assert [d.category for d in bv.diff([crate], facts(pack=("crate",)))] == ["trade"]


# --- 2. the attempts --------------------------------------------------------------------------

def test_the_attempts_are_the_engines_checks_and_saves_named_by_whose_they_were():
    """Built from the records, never a tell: Aid Another is two attempts (the player's
    help, which failed, and the smith's own effort, which succeeded — the live beat told
    both truly, and one verdict would have called it wrong); a request is labelled as the
    request; an attack is the blow lane's and is not listed; an outcome with no actor on
    record names nobody and is not asked about."""
    attack = {"op": "attack", "status": "resolved", "actor": "pc", "verdict": "miss"}
    unowned = dict(REFUSED_PAY, actor="")
    att = bv.attempts_of(facts(AID, REFUSED_PAY, attack, unowned))
    assert [(a.code, a.who, a.verdict) for a in att] == [
        ("a1", "pc", "failure"), ("a2", "c4", "success"), ("a3", "pc", "failure")]
    lines = [bv._attempt_line(a, facts()) for a in att]
    assert lines[0] == "a1: you (the player) — Strength check to help the smith"
    assert lines[2] == ("a3: you (the player) — Diplomacy check: asking the smith for "
                        "payment for the work")
    # The verdict is never shown to the reader.
    assert not any(w in " ".join(lines) for w in ("fail", "success", "miss", "made"))
    save = {"op": "save", "status": "resolved", "actor": "pc", "verdict": "success",
            "rolls": [{"label": "Fortitude save"}], "because": "the spider's venom"}
    assert bv.attempts_of(facts(save))[0].save


def test_an_attempt_told_the_other_way_round_is_a_contradiction_and_unsure_abstains():
    """A failed lift told as the cart rising, a passed save told as the venom taking hold
    (bench gold `att-*`). "unsure" is no claim, and a beat that agrees raises nothing."""
    lift = {"op": "check", "status": "resolved", "actor": "pc", "verdict": "failure",
            "rolls": [{"label": "Strength check"}], "because": "the player lifts the cart"}
    f = facts(lift)
    found = bv.diff([claim("attempt", attempt="a1", shown="succeeds")], f)
    assert [(d.kind, d.category, d.ref) for d in found] == [("contradiction", "attempt", "pc")]
    assert "the attempt does not work" in found[0].fact
    assert "by 4" not in found[0].fact and not any(ch.isdigit() for ch in found[0].fact)
    assert bv.diff([claim("attempt", attempt="a1", shown="fails")], f) == []
    assert bv.attempt_claims({"a1": {"shown": "unsure", "quote": ""}},
                             bv.attempts_of(f)) == []
    save = {"op": "save", "status": "resolved", "actor": "pc", "verdict": "success",
            "rolls": [{"label": "Fortitude save"}], "because": "the spider's venom"}
    found = bv.diff([claim("attempt", attempt="a1", shown="fails")], facts(save))
    assert "you resist it" in found[0].fact
    refused = bv.diff([claim("attempt", attempt="a1", shown="succeeds")], facts(REFUSED_PAY))
    assert refused[0].fact.startswith("The smith says no to the request for payment")
    q = bv.question(refused[0], facts(REFUSED_PAY))
    assert "attempt" in q and "working" in q


def test_an_attempts_quote_may_be_speech_and_may_be_joined_by_an_ellipsis():
    """A refusal is often only spoken — "'Not a chance,' he says" — and every other claim's
    quote must be narration. And the reader joined two pieces with "..." on 2 of 32 attempt
    quotes of the first bench run, both true, both dropped: the first piece stands."""
    f = facts(REFUSED_PAY)
    text = "He folds his arms. 'Not a chance, not for you,' he says. The forge roars."
    said = bv.Claim("attempt", {"attempt": "a1", "shown": "fails"},
                    "'Not a chance, not for you,' he says")
    joined = bv.Claim("attempt", {"attempt": "a1", "shown": "fails"},
                      "He folds his arms... The forge roars")
    kept, dropped = bv.validate([said, joined], text, f)
    assert [c.sentence for c in kept] == ["'Not a chance, not for you,' he says.",
                                          "He folds his arms."] and not dropped
    # A hands claim from the same speech is still dropped: a character may say anything.
    gift = bv.Claim("hands", {"item": bv.OTHER_THING, "from": "c4", "to": "pc"},
                    "'Not a chance, not for you,'")
    assert bv.validate([gift], text, f)[0] == []


def _scripted(*answers):
    calls = []

    def chat(msgs, model, host, **kw):
        calls.append((msgs, kw.get("schema")))
        text = json.dumps(answers[len(calls) - 1])
        return SimpleNamespace(text=text, json=lambda: json.loads(text))
    return chat, calls


EMPTY = {"player_ends_at": {"place": "the gate", "quote": ""}, "changed_hands": [],
         "trades": [], "harmed": [], "arrived": [], "left": [], "time_of_day": []}


def test_the_attempts_are_a_call_of_their_own_and_the_first_read_is_unchanged():
    """Asked in a third call, only on a beat with a listed attempt — the first read's
    messages and schema are byte-identical with or without one (folded into it, the slot
    measured on the bench in docs/beat-verify.md). A beat with no check costs no call."""
    text = "You heave, and the cart rises out of the rut."
    lift = {"intent_id": "i1", "op": "check", "status": "resolved", "actor": "pc",
            "verdict": "failure", "rolls": [{"label": "Strength check"}],
            "because": "the player lifts the cart"}
    chat, calls = _scripted(EMPTY, {"a1": {"shown": "succeeds",
                                           "quote": "the cart rises out of the rut"}})
    reading = bv.read(text, facts(lift), model="stub", chat=chat)
    assert len(calls) == 2 and set(calls[1][1]["required"]) == {"a1"}
    assert calls[0][0] == bv.messages(text, facts())
    assert calls[0][1] == bv.schema(facts())
    assert [(c.category, c.slots) for c in reading.claims] == [
        ("attempt", {"attempt": "a1", "shown": "succeeds"})]
    assert [d.category for d in bv.diff(reading.claims, facts(lift), text)] == ["attempt"]
    chat, calls = _scripted(EMPTY)
    bv.read(text, facts(), model="stub", chat=chat)
    assert len(calls) == 1


def test_the_member_raises_an_attempt_finding():
    from gm.checks import beat_verified

    assert beat_verified._KIND["attempt"] == ("beat-attempt", 3)
    assert "beat-attempt" in beat_verified.KINDS


def test_the_engine_stamps_who_made_each_attempt():
    """`Outcome.actor`, stamped where every op leaves the engine: the attempts are named
    by whose they were, and the tell's leading name was the only trace of it before. A
    player's check is suspended for the popup and resumed, and the stamp survives that."""
    from rules.dice import Dice
    from rules.engine import Engine, Outcome

    from test_requests_and_rewards import PAY_ME, _asked, _scene

    s, _carter = _scene()
    _rows, plan = _asked(s, PAY_ME)
    e = Engine(s, Dice(seed=1))
    e.run(e.validate(plan))
    res = e.resume(1)
    check = next(o for o in res.outcomes if o.op == "check")
    assert check.actor == "pc" and check.as_dict()["actor"] == "pc"
    assert "actor" not in Outcome(intent_id="x", op="check").as_dict()
