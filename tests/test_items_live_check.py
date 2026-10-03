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

from gm import interpret, judgement
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


@pytest.mark.parametrize("said, read", [
    (LIVE, "I pick up the crate. I tip the coins from the pouch into my coin purse."),
    ("I drop the pouch on the floor and pick up the crate.",
     "I drop the pouch on the floor. I pick up the crate."),
    # A bare "and" between nouns, or before a verb no deed reader reads, stays put.
    ("I buy the bread and cheese.", "I buy the bread and cheese."),
    ("I take the rope and the lantern.", "I take the rope and the lantern."),
    ("I walk in and look around.", "I walk in and look around."),
])
def test_a_sequenced_deed_is_read_as_its_own_declaration(said, read):
    assert judgement.as_declarations(said) == read


def test_the_live_sentence_plans_the_crate_and_the_coins():
    """Both deeds reach the plan, and the coins' give does not stand in for the crate's:
    coin goes to the purse, not the pack, so it is not the turn's one thing coming in."""
    s = _scene()
    s.pc().goods["pouch"] = 1
    raw = judgement.declare_emptying([{"op": "narrate_only"}], LIVE, s)
    raw = judgement.inject_goods(raw, LIVE, s)
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
    raw = judgement.inject_goods([{"op": "narrate_only"}], LIVE, s)
    for r in raw:
        r.setdefault("actor", "pc")
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
