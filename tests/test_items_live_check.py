"""What the first live turns on the merged 2026-10-03 batch found (docs/playtest-2026-10-03.md).

The five lanes' tests were green, and the first three turns played in the running app on a
copy of the owner's items save still went wrong:

- "I pick the crate back up, then tip the coins from the pouch into my coin purse": the
  reading had both takes, the plan was `narrate_only`, the prose lifted the crate and
  tipped the coins, and the engine moved neither. Every deed reader anchors on "I <verb>"
  and the second clause has no "I"; `_OBJECT` reads "pick up the crate", never "pick the
  crate back up".
- With the second clause read, the coins' give still blocked the crate's: one
  acquisition per direction, and coin into the purse was counted as the pack's.
- The save loaded with `brunt of the weight` and `coins` still in the pack, minted
  before the fixes.
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, interpret, judgement
from play.campaign import _heal_minted_goods
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

LIVE = "I pick the crate back up, then tip the coins from the pouch into my coin purse."


@pytest.fixture(autouse=True)
def _no_readings(monkeypatch):
    monkeypatch.setattr(interpret, "_READINGS", {})


def _scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


# The reading of LIVE, as the reader produced it on 2026-10-03: two takes, in order. The
# regex that split "…, then tip" into its own "I tip" declaration (`as_declarations`) is
# retired with the readers it fed (docs/structured-turn.md): a reading is already one
# action per deed, whether or not the deed has its own "I".
LIVE_READING = {"question": False, "claims": [], "actions": [
    {"act": "take", "object": "the crate"},
    {"act": "take", "object": "the coins", "target": "the pouch"}]}


def _table(said, frame, s, plan=None):
    rows = acts_to_ops.table(frame, s, sentence=said)
    return acts_to_ops.apply(list(plan or [{"op": "narrate_only"}]), rows, frame, s)


@pytest.mark.parametrize("said, frame, items", [
    (LIVE, LIVE_READING, ["crate", "coins"]),
    ("I drop the pouch on the floor and pick up the crate.",
     {"actions": [{"act": "drop", "object": "the pouch", "place": "the floor"},
                  {"act": "take", "object": "the crate"}]}, ["pouch", "crate"]),
])
def test_a_sequenced_deed_is_its_own_op(said, frame, items):
    """Each deed of the reading is its own op, the second clause's with no "I" too."""
    s = _scene()
    s.pc().goods["pouch"] = 1
    assert [r["params"]["item"] for r in _table(said, frame, s)
            if r.get("op") == "give"] == items


def test_the_live_sentence_plans_the_crate_and_the_coins():
    """Both deeds reach the plan, and the coins' give does not stand in for the crate's:
    coin goes to the purse, out of the pouch, and the crate into the pack."""
    s = _scene()
    s.pc().goods["pouch"] = 1
    raw = _table(LIVE, LIVE_READING, s)
    gives = [(r["params"].get("item"), r["params"].get("from_"), r["params"].get("to"))
             for r in raw if r.get("op") == "give"]
    assert ("coins", "pouch", s.pc().ref) in gives
    assert ("crate", None, s.pc().ref) in gives


def test_a_crate_set_down_is_picked_back_up_off_the_floor():
    """The first live turn set the crate down ("Kesst Vayr sets down crate; it lies
    here."); the second must lift that same crate, not mint another."""
    s = _scene()
    s.pc().goods["crate"] = 1
    e = Engine(s, Dice(seed=1))
    e.run(e.validate([{"op": "give", "actor": "pc",
                       "params": {"item": "crate", "from_": "pc"}}]))
    assert "crate" not in s.pc().goods
    raw = _table(LIVE, {"actions": [{"act": "take", "object": "the crate"}]}, s)
    e.run(e.validate(raw))
    assert s.pc().goods.get("crate") == 1
    assert not [p for p in s.props_here() if p.get("name") == "crate"]


def test_goods_minted_from_words_are_put_right_on_load():
    """The items save's pack, `{"brunt of the weight": 1, "pouch": 1, "coins": 1}`: the
    figure of speech goes, the coin goes to the purse at the engine's own one-copper rate
    (no amount was ever recorded), and the pouch — a real pouch — stays."""
    s = _scene()
    pc = s.pc()
    pc.goods.update({"brunt of the weight": 1, "pouch": 1, "coins": 1, "crate": 1})
    pc.purse = {}
    _heal_minted_goods(s)
    assert pc.goods == {"pouch": 1, "crate": 1}
    assert pc.purse == {"cp": 1}


def test_the_ledger_gives_a_descriptor_name_its_article():
    """The healed market-talk save, played live: "you told man in the heavy coat, “who the
    master of the docks is”". A descriptor name carries no article of its own."""
    from types import SimpleNamespace

    from gm import ledger

    said = SimpleNamespace(op="say", status="resolved", effects=[
        {"kind": "said", "who": "", "to": "c4", "words": "who the master of the docks is"}])
    got = ledger.note([said], turn=18, names={"c4": "man in the heavy coat", "c7": "Grix"})
    assert got["text"] == "you told the man in the heavy coat, “who the master of the docks is”"
    named = SimpleNamespace(op="say", status="resolved", effects=[
        {"kind": "said", "who": "", "to": "c7", "words": "hello"}])
    assert ledger.note([named], turn=1, names={"c7": "Grix"})["text"] == "you told Grix, “hello”"


@pytest.mark.parametrize("op, params", [
    ("sell", {"item": "crate"}),
    ("buy", {"item": "rope"}),
])
def test_a_trade_with_no_actor_is_the_players_not_a_crash(op, params):
    """Measured live: "I agree to sell the crate to the smith for whatever it is worth"
    came back from the model as a `sell` with no actor, `_op_sell` read
    `scene.actors[None]`, and the player saw "The engine refused the GM's intents: None"
    with the turn thrown away. Whatever the trade then says, it says it as a refusal or
    a sale — never a KeyError."""
    s = _scene()
    s.pc().goods["crate"] = 1
    e = Engine(s, Dice(seed=1))
    out = e.run(e.validate([{"op": op, "params": dict(params)}])).outcomes
    assert [o.op for o in out] == [op]


def test_a_cast_with_no_caster_is_refused_by_name():
    """The other bare lookup on the same line of handlers: a `cast` with nobody casting
    is refused at validation, where the planner gets the fix named, not guessed at."""
    from rules.intents import IntentError

    e = Engine(_scene(), Dice(seed=1))
    with pytest.raises(IntentError):
        e.validate([{"op": "cast", "params": {"spell": "light"}}])


# --- the live sale at first light -------------------------------------------------------------

SMITH_BEAT = ("The man at the workbench—the smith—does not look up from the crate as you "
              "speak. He is a large man, his hands calloused and stained with the grey of "
              "ash. 'Well,' he grunts. 'Let's see what's inside before we talk of coin.'")


def _smithy(people=(("the smith", "guildhand"),)):
    from rules.bestiary import instantiate

    s = _scene()
    refs = [s.add(instantiate(t, scene=s, name=n)).ref for n, t in people]
    return s, refs


def test_a_description_after_he_is_is_nobody_new():
    """Measured live: "He is a large man" became a second smith (c15), the "he" of the
    next line carried to him, and with two people in the conversation the deal found no
    buyer. `judgement.only_a_predicate` caught that one phrasing with a pattern the same
    day; the beat reader answers it now — "a large man" is the smith — and nobody is made.
    The beat itself is on the bench (tests/beat_reader/gold.py, kesst-62), where the
    reader is measured on it."""
    from play.aftermath import seen_people
    from tests.beat_reader import stub
    from tests.beat_reader.gold import CASES

    gold = next(c for c in CASES if c["id"] == "kesst-62-he-is-a-large-man")
    assert gold["people"]["a large man"].split("|")[0] == "c13" and not gold["new"]
    s, (smith,) = _smithy()
    before = set(s.actors)
    reading = stub.read(SMITH_BEAT, s, who={"The man": smith, "the smith": smith,
                                            "a large man": smith},
                        lines={"Well": (smith, "you"), "Let's see": (smith, "you")})
    seen_people.step(stub.ctx(s, reading, text=SMITH_BEAT, turn=62))
    assert set(s.actors) == before and not reading.newcomers


def test_a_new_person_after_a_description_is_still_somebody():
    """The other side of it: a woman walking in after the description is somebody new,
    and the reader's "new … here" makes her."""
    from play.aftermath import seen_people
    from tests.beat_reader import stub

    beat = "He is a large man. A woman with a basket stops at the door."
    s, (smith,) = _smithy()
    before = set(s.actors)
    reading = stub.read(beat, s, who={"a large man": smith, "A woman": "new"},
                        new=[("A woman", "here", "woman with a basket")])
    rows = seen_people.step(stub.ctx(s, reading, text=beat, turn=63))
    made = set(s.actors) - before
    assert len(made) == 1 and s.actors[made.pop()].name == "woman with a basket", rows


def test_a_deal_spoken_aloud_sells_to_the_one_in_conversation():
    """Measured live at first light, the counter open: '"It's a deal. You can have the
    crate."' — the whole line in quotation marks. `redact_speech` blanked all of it, the
    close was never read, and nobody was named, so even a read close found no buyer. The
    words that close a deal are spoken; the buyer is the one being spoken to."""
    from rules.bestiary import instantiate

    s = _scene()
    s.pc().goods["crate"] = 1
    smith = instantiate("guildhand", scene=s, name="the smith")
    s.add(smith)
    s.add(instantiate("guildhand", scene=s, name="man"))
    Engine(s, Dice(seed=1)).join_talk(smith)
    said = '"It\'s a deal. You can have the crate."'
    out = _table(said, {"actions": [{"act": "talk", "says": said.strip('"')},
                                    {"act": "sell", "object": "the crate"}]}, s)
    sells = [r for r in out if r.get("op") == "sell"]
    assert sells and sells[0]["params"] == {"item": "crate", "to": smith.ref}
    # And a mere mention inside speech is still not a sale: the reading reads a question
    # said, and no act of it stands behind a sale.
    out = _table('"Would you sell me rope?"',
                 {"actions": [{"act": "talk", "says": "Would you sell me rope?"}]}, s,
                 plan=[{"op": "sell", "actor": "pc", "params": {"item": "crate"}}])
    assert not [r for r in out if r.get("op") == "sell"]


def test_a_deal_said_to_the_smith_by_name_finds_him_though_two_are_talking():
    """Measured live: 'I tell the smith, "It's a deal. You can have the crate."' redacted
    to "I tell the" — the buyer's name went with the speech — and with a second person in
    the conversation nothing chose between them. Read off the whole line, the smith is
    named."""
    from rules.bestiary import instantiate

    s = _scene()
    s.pc().goods["crate"] = 1
    # Each added before the next is made: made together, both drew the ref c1 and the
    # second replaced the first — this test passed for months with no smith in the room.
    smith = instantiate("guildhand", scene=s, name="the smith")
    s.add(smith)
    other = instantiate("guildhand", scene=s, name="large man")
    s.add(other)
    assert smith.ref != other.ref
    e = Engine(s, Dice(seed=1))
    e.join_talk(smith)
    e.join_talk(other)
    said = 'I tell the smith, "It\'s a deal. You can have the crate."'
    out = _table(said, {"actions": [
        {"act": "talk", "target": "the smith", "says": "It's a deal. You can have the crate."},
        {"act": "sell", "object": "the crate", "target": "the smith"}]}, s)
    sells = [r for r in out if r.get("op") == "sell"]
    assert sells and sells[0]["params"]["to"] == smith.ref
