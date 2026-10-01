"""The Journal's history of the character (owner, 2026-10-01; play/history.py).

Asked for: "a history section at the bottom that will read the full history of the
character read from the stored information of the campaign". Before this, the Journal's
last line read "The adventure log, a record of each session, is not kept yet."

What it must be, and what is measured here:

* built from the engine's record of each turn — the outcome effects in `turn_log` — and
  never the narrator's prose;
* one line per thing that happened, from an allow-list, so a hundred blows and rolls are
  not a hundred lines (Crusader Kings II's chronicle, dropped in III as filler);
* the same outcome told once, though a resumed turn's resolution row repeats it;
* no ref ever on the page (ruling 2026-09-28): a line about somebody with no name
  anywhere is left out, not printed as "c99";
* by day where the row kept the clock — which rows written from 2026-10-01 do.

First measured on the 200-turn scratch copy of the owner's Sam campaign (not committed):
thirteen lines, from "You took on “The Fighter's Debt” for the cage owner." to "Quin Nutmeg
is well disposed towards you." Two defects the first run showed are pinned below: a
crafted jar named by its key ("power_leaf_tea#1") and the outskirts as "outside".
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import history
from rules.sheet import load_pc


@pytest.fixture
def camp(tmp_path):
    from play import campaign as cm
    from rules.bestiary import instantiate

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        thug = instantiate("thug", scene=c.scene, name="the thug")
        thug.ref = "c77"
        c.scene.add(thug)
        c.turn_log.clear()
        yield c
        cm._LIVE.clear()


def _turn(*effects, kind="turn", intent_id="i1", op="x", actor="pc", clock=None, tell=""):
    row = {"kind": kind,
           "intents": [{"id": intent_id, "op": op, "actor": actor}],
           "outcomes": [{"intent_id": intent_id, "op": op, "tell": tell or op,
                         "effects": list(effects)}]}
    if clock is not None:
        row["clock"] = clock
    return row


def _lines(c) -> list[str]:
    return [l["text"] for d in history.history(c)["days"] for l in d["lines"]]


def test_what_happened_is_told_one_line_each(camp):
    c = camp
    c.turn_log += [
        _turn({"kind": "quest", "id": "q1", "title": "The Fighter's Debt", "giver": "c77"}),
        _turn({"kind": "battle_joined", "ref": "pc", "target": "c77"}, op="attack"),
        _turn({"ref": "c77", "kind": "condition", "condition": "dead", "rounds_left": None}),
        _turn({"ref": "pc", "kind": "bought", "item": "rope", "count": 2, "paid_cp": 20}),
        {"kind": "level-up", "level": 2},
    ]
    assert _lines(c) == [
        "You took on “The Fighter's Debt” for the thug.",
        "A fight began with the thug.",
        "The thug died.",
        "You bought rope ×2.",
        "You reached level 2.",
    ]


def test_rolls_and_diagnostics_are_not_history(camp):
    """A check, a blow that missed, a mention row: none of them is a line."""
    c = camp
    c.turn_log += [
        _turn({"kind": "damage", "ref": "c77", "amount": 4}, op="attack"),
        {"kind": "mentions", "refs": ["c77"]},
        {"kind": "prose", "repairs": []},
        _turn(op="check"),
    ]
    assert _lines(c) == []


def test_a_resumed_turn_is_told_once(camp):
    """The resolution row after a roll repeats the turn's outcomes under the same
    per-turn intent ids; measured on the scratch Sam campaign, every lie and every quest
    would have been listed twice."""
    c = camp
    quest = {"kind": "quest", "id": "q1", "title": "The Debt", "giver": "c77"}
    c.turn_log += [_turn(quest, op="quest"), _turn(quest, kind="resolution", op="quest")]
    assert _lines(c) == ["You took on “The Debt” for the thug."]


def test_no_ref_ever_reaches_the_page(camp):
    c = camp
    c.turn_log += [_turn({"kind": "battle_joined", "ref": "pc", "target": "c99"},
                         op="attack"),
                   _turn({"ref": "c99", "kind": "condition", "condition": "dead"})]
    out = json.dumps(history.history(c))
    assert "c99" not in out
    assert _lines(c) == []


def test_days_come_from_the_clock_and_older_rows_keep_their_order(camp):
    c = camp
    c.turn_log += [
        _turn({"kind": "place", "name": "the Old Mill"}),                    # no clock
        _turn({"kind": "place", "name": "the Ferry"}, clock=10 * 60),
        _turn({"kind": "place", "name": "the Weir"}, clock=26 * 60),
    ]
    days = history.history(c)["days"]
    assert [d["day"] for d in days] == [None, 1, 2]
    assert [d["lines"][0]["text"] for d in days] == [
        "You found the Old Mill.", "You found the Ferry.", "You found the Weir."]


def test_a_crafted_thing_is_named_not_keyed(camp):
    """The first run: "You gave power_leaf_tea#1 to guard"."""
    c = camp
    c.turn_log.append(_turn({"ref": "c77", "kind": "give", "item": "power_leaf_tea#1",
                             "count": 1, "satchel": {}}, op="give", actor="pc"))
    assert _lines(c) == ["You gave power leaf tea to the thug."]


def test_a_secret_card_is_not_told(camp):
    from rules import cards as cards_mod

    c = camp
    card = cards_mod.open_quest(c.scene, title="The Hidden Thing", objectives=["Find it"])
    card.secret = True
    cards_mod._store(c.scene, card)
    c.turn_log.append(_turn({"kind": "quest_step", "id": card.id, "objective": 1,
                             "finished": True}))
    assert _lines(c) == []


def test_how_it_began_is_the_errand_in_its_own_words(camp):
    """The opening card's title spliced into a sentence read "You had come for somebody
    sent a runner for the bonesetter, and you are the bonesetter." The errand fact is a
    whole sentence already."""
    began = history.history(camp)["began"]
    assert began.startswith("It began in ") or began.startswith("You came")
    assert "You had come for" not in began


def test_turn_rows_are_stamped_with_the_clock_and_the_place(camp):
    from gm.agent import TurnPlan
    from play import views
    from rules.engine import Resolution

    c = camp
    c.scene.clock_minutes = 1234
    views._log_turn(c, TurnPlan(narration="", intents=[]), Resolution(outcomes=[]))
    row = c.turn_log[-1]
    assert row["clock"] == 1234 and row["at"] == c.scene.at
    # Replaced after the prose: still when the turn happened, not when it was rewritten.
    c.scene.clock_minutes = 2000
    views._log_turn(c, TurnPlan(narration="", intents=[]), Resolution(outcomes=[]),
                    replace=True)
    assert c.turn_log[-1]["clock"] == 1234


def test_taking_a_level_writes_the_row_its_docstring_promised(camp):
    """`level_up` has said since it was written that the roll "lands in the turn log";
    nothing wrote a row until 2026-10-01."""
    c = camp
    c.scene.pc().xp = 10 ** 6
    c.save()
    r = Client().post("/api/level-up", data="{}", content_type="application/json")
    assert r.status_code == 200, r.json()
    from play import campaign as cm

    rows = [x for x in cm.current().turn_log if x.get("kind") == "level-up"]
    assert rows and rows[-1]["level"] == cm.current().scene.pc().level
    assert "You reached level" in json.dumps(history.history(cm.current()))


def test_the_journal_reads_it_over_http(camp):
    camp.turn_log.append(_turn({"kind": "place", "name": "the Ferry"}))
    camp.save()
    d = Client().get("/api/history").json()
    assert d["days"][-1]["lines"][-1]["text"] == "You found the Ferry."


def test_a_quest_giver_left_behind_is_named_not_reffed(camp):
    """Seen beside the history in the running app (scratch Sam campaign, 2026-10-01): the
    Matters card read "for c1" once the cage owner was out of the room, because the quest
    log named givers from who is HERE. Refs are never on the page."""
    from rules import cards as cards_mod

    c = camp
    cards_mod.open_quest(c.scene, title="The Debt", objectives=["Pay it"], giver="c77")
    c.scene.people["c77"].at = "somewhere~urban:else"
    assert "c77" not in c.scene.actors
    row = cards_mod.quest_log(c.scene)["active"][0]
    assert row["giver"] == "the thug"
    del c.scene.people["c77"]
    assert cards_mod.quest_log(c.scene)["active"][0]["giver"] == ""


def test_the_page_draws_a_history_where_the_placeholder_was():
    from pathlib import Path

    js = Path("play/static/js/table/05-sheet.js").read_text(encoding="utf-8")
    assert "not kept yet" not in js
    assert '"/api/history"' in js and 'sheetCard("jr-history", "History"' in js
