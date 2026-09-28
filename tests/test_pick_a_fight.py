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
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from gm import interpret, judgement
from rules.engine import Scene
from rules.sheet import load_pc

REPLAY = Path(__file__).resolve().parent / "replay"


def _scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


def _gives(said, scene=None):
    out = judgement.inject_goods([{"op": "narrate_only"}], said, scene or _scene())
    return [i["params"] for i in out if i.get("op") == "give"]


@pytest.fixture(autouse=True)
def _no_readings(monkeypatch):
    monkeypatch.setattr(interpret, "_READINGS", {})


@pytest.mark.parametrize("said", [
    "I pick a fight with the biggest man in the room.",
    "I grab him and throw him over a table.",
    "I pick a quarrel with the guard.",
    "I take him by the collar and slam him into the door.",
    # The same verb in the 2026-09-27 battery: the detector required a give for it.
    "I pick the lock on her door.",
    "I pick his pocket while he is distracted.",
])
def test_no_item_comes_from_a_fight(said):
    assert _gives(said) == [], said


@pytest.mark.parametrize("said,item", [
    ("I pick an apple from the tree.", "apple"),
    ("I grab the lantern and run.", "lantern"),
    ("I take back the silver ring", "silver ring"),
    ("I pick up a chunk of wood and throw it at the man", "chunk of wood"),
])
def test_the_verbs_own_object_is_still_taken(said, item):
    """The control: anchoring the object to the verb must not lose a real pick-up."""
    assert [g["item"] for g in _gives(said)] == [item]


def test_the_reading_is_asked_at_this_door_too():
    """"I take the table by the window" is sitting down, and the regex cannot tell. A
    reading that says so is obeyed here as it is for the plan's own give; a reading
    that says `take` is not second-guessed; with no reading the regex decides."""
    said = "I take the table by the window."
    assert [g["item"] for g in _gives(said)] == ["table by the window"]
    interpret.remember(said, {"actions": [{"act": "rest", "place": "the table"}]})
    assert _gives(said) == []
    interpret.remember(said, {"actions": [{"act": "take", "object": "the table"}]})
    assert [g["item"] for g in _gives(said)] == ["table by the window"]
    interpret.remember(said, {"error": "the model was down"})
    assert [g["item"] for g in _gives(said)] == ["table by the window"]


def test_handing_over_is_not_the_readings_to_veto():
    """Only gains to the player are the reading's to stop, as in `drop_unread_gifts`: a
    give away from the player takes nothing from nowhere."""
    said = "I hand over the brass key"
    interpret.remember(said, {"actions": [{"act": "talk"}]})
    assert _gives(said) == [{"item": "brass key", "from_": "pc"}]


@pytest.mark.parametrize("act", ["insult", "attack", "talk", "rest", "go",
                                 *sorted(interpret.GETTING_ACTS)])
def test_both_doors_answer_the_same_reading_the_same_way(act):
    """The plan's give (`drop_unread_gifts`) and the detector's (`inject_goods`) stand
    or fall together for every act: the second door stayed open because it never asked
    the question the first one did."""
    said = "I take the brass key"
    frame = {"actions": [{"act": act}]}
    interpret.remember(said, frame)
    plan = [{"op": "give", "params": {"item": "brass key", "to": "pc"}}]
    plan_kept = bool(interpret.drop_unread_gifts(plan, frame)[0])
    detector_gave = bool(_gives(said))
    assert plan_kept == detector_gave == (act in interpret.GETTING_ACTS), act


def test_the_recorded_sentences_give_nothing():
    """Every player sentence in the recordings, through the injector: two gave something
    before (both wrong: "fight", "table"), none now."""
    said = set()
    for f in [*REPLAY.glob("*.jsonl.gz"), *REPLAY.glob("plans/*.jsonl.gz")]:
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            said |= {json.loads(line)["player"] for line in fh}
    assert "I pick a fight with the biggest man in the room." in said
    assert "I grab him and throw him over a table." in said
    assert {s: g for s in sorted(said) if (g := _gives(s))} == {}
