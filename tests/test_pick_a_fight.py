""""I pick a fight" is not picking something up, and the reading's word holds at every door.

Measured live 2026-09-27 (`narrator_audit.py --script fight`, gemma-4-12B, branch
placeholders-are-ours), turn 1, "I pick a fight with the biggest man in the room": the
reading read an insult, `interpret.supported` overruled the `give` a detector required,
and the turn still ended "Kesst Vayr takes fight." with `goods: {"fight": 1}`.
`inject_goods` wrote it: `_ACQUIRES` matched "I pick", `_THING` took "a fight". It runs
after `interpret.drop_unread_gifts`, the door that already removes a give the reading
never asked for, and never asked the reading itself.

It was not new. In every fight recording the give was there on every turn those
sentences resolved: "fight" four times in the committed corpus (tests/replay, 2026-09-25)
and once on 2026-09-27; "table" four times in the corpus and twice on 2026-09-27 for "I
grab him and throw him over a table", where `_THING` searched past "him" to the table
after "over". The reading could not have caught the table: it read "grab him" as `take`.
Of the 40 distinct player sentences in the recordings, `inject_goods` gave something for
two, both of them these; after the fix, for none.

So both: (a) the injector consults the reading (`interpret.gets_nothing`, one rule for
both doors), and (b) the object must be the verb's own — right after it — and a fight is
not a thing.

Since 2026-10-03 there is no second door: `inject_goods` is retired, and the reading drives
every take (gm/acts_to_ops.py, docs/structured-turn.md). What these tests pin now is that
the reading's word is the only word — a fight read as an insult takes nothing, a take of
"him" is a grapple and never goods, and a plan's give no act stands behind is overruled at
the one door left (`acts_to_ops.apply`) exactly as at `interpret.drop_unread_gifts`.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from gm import acts_to_ops, interpret
from rules.engine import Scene
from rules.sheet import load_pc

REPLAY = Path(__file__).resolve().parent / "replay"


def _scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


def _gives(said, frame, scene=None, plan=None):
    scene = scene or _scene()
    rows = acts_to_ops.table(frame, scene, sentence=said)
    out = acts_to_ops.apply(list(plan or [{"op": "narrate_only"}]), rows, frame, scene)
    return [i["params"] for i in out if i.get("op") == "give"]


@pytest.fixture(autouse=True)
def _no_readings(monkeypatch):
    monkeypatch.setattr(interpret, "_READINGS", {})


@pytest.mark.parametrize("said,actions", [
    ("I pick a fight with the biggest man in the room.",
     [{"act": "insult", "target": "the biggest man in the room"}]),
    # The reading read "grab him" as `take` (2026-09-27): a take of a person is no goods.
    ("I grab him and throw him over a table.",
     [{"act": "take", "object": "him"}, {"act": "attack", "target": "him",
                                         "place": "a table"}]),
    ("I pick a quarrel with the guard.", [{"act": "insult", "target": "the guard"}]),
    ("I take him by the collar and slam him into the door.",
     [{"act": "take", "object": "him"}, {"act": "attack", "target": "him"}]),
    # The same verb in the 2026-09-27 battery: the detector required a give for it.
    ("I pick the lock on her door.", [{"act": "break_in", "target": "her door"}]),
    ("I pick his pocket while he is distracted.", [{"act": "steal", "target": "him"}]),
])
def test_no_item_comes_from_a_fight(said, actions):
    assert _gives(said, {"actions": actions}) == [], said


@pytest.mark.parametrize("said,obj,item", [
    ("I pick an apple from the tree.", "an apple", "apple"),
    ("I grab the lantern and run.", "the lantern", "lantern"),
    ("I take back the silver ring", "the silver ring", "silver ring"),
    ("I pick up a chunk of wood and throw it at the man", "a chunk of wood",
     "chunk of wood"),
])
def test_the_verbs_own_object_is_still_taken(said, obj, item):
    """The control: a real pick-up the reading reads is still taken."""
    assert [g["item"] for g in _gives(said, {"actions": [{"act": "take", "object": obj}]})] \
        == [item]


def test_the_reading_is_the_only_word():
    """"I take the table by the window" is sitting down, and only the reading can tell. A
    reading that says so takes nothing; a reading that says `take` is not second-guessed;
    with no reading nothing reads the words behind the plan (the plan alone)."""
    said = "I take the table by the window."
    assert _gives(said, {"actions": [{"act": "rest", "place": "the table"}]}) == []
    assert [g["item"] for g in _gives(said, {"actions": [
        {"act": "take", "object": "the table by the window"}]})] == ["table by the window"]
    assert _gives(said, {"error": "the model was down"}) == []


def test_handing_over_is_the_readings_to_declare():
    """Item 8, 2026-10-03: "I give a friendly wink" read as `other` + `talk`, and the
    detector still planned a give of "friendly wink" — "Kesst Vayr has no friendly wink
    to give" reached the narrator and the ledger kept "handed something to Kesst Vayr".
    A hand-over is the reading's: a carried thing given is built; words and a wink are
    not."""
    said = "I hand over the brass key"
    scene = _scene()
    from rules.bestiary import instantiate

    scene.add(instantiate("guildhand", scene=scene, name="the guard"))
    scene.pc().goods["brass key"] = 1
    guard = next(r for r, a in scene.actors.items() if a.name == "the guard")
    assert _gives(said, {"actions": [{"act": "give", "object": "the brass key"}]}, scene) \
        == [{"item": "brass key", "from_": "pc", "to": guard}]
    assert _gives(said, {"actions": [{"act": "talk"}]}, scene) == []
    winked = "I give a friendly wink and say hello"
    assert _gives(winked, {"actions": [{"act": "other", "target": "a friendly wink"},
                                       {"act": "talk"}]}, scene,
                  plan=[{"op": "give", "params": {"item": "friendly wink",
                                                  "from_": "pc"}}]) == []


@pytest.mark.parametrize("act", ["insult", "attack", "talk", "rest", "go",
                                 *sorted(interpret.GETTING_ACTS)])
def test_both_doors_answer_the_same_reading_the_same_way(act):
    """The plan's give (`drop_unread_gifts`) and the table's overrule (`acts_to_ops.apply`)
    stand or fall together for every act: the second door stayed open, until 2026-09-27,
    because it never asked the question the first one did."""
    frame = {"actions": [{"act": act}]}
    plan = [{"op": "give", "params": {"item": "brass key", "to": "pc"}}]
    plan_kept = bool(interpret.drop_unread_gifts(plan, frame)[0])
    table_kept = bool(_gives("I take the brass key", frame, plan=plan))
    assert plan_kept == table_kept == (act in interpret.GETTING_ACTS), act


def test_the_recorded_readings_give_nothing():
    """Every recorded turn that carries the reading the live reader gave it, through the
    table: the fight turns ("I pick a fight…", read as an insult, and the punch) take
    nothing. Only 4 of the 108 recorded turns carry a reading — the recordings predate
    it — so the sentence-level sweep this test once ran over all 40 sentences with the
    regex has nothing left to sweep: there is no regex."""
    seen = []
    for f in [*REPLAY.glob("*.jsonl.gz"), *REPLAY.glob("plans/*.jsonl.gz")]:
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                for t in rec.get("added_turn_log") or []:
                    if t.get("kind") == "turn" and t.get("reading"):
                        seen.append((rec["player"], t["reading"]))
    assert "I pick a fight with the biggest man in the room." in {s for s, _ in seen}
    assert {s: g for s, r in seen if (g := _gives(s, r))} == {}
