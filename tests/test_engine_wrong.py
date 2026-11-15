""""That's wrong" on what the engine did (play/engine_corrections.py; the owner, 2026-11-15:
"it is the engine that is making the most mistakes now"). Each test names the defect:

  * a hidden goblin's swing, its square, its name or the guard's secret Sense Motive
    reaching the page through the turn's record — the board leaves out what the PC does not
    locate (`awareness.player_locates`), and so must this; the LOG keeps all of it;
  * a beat shown another turn's record (rows are matched to beats by `transcript_at`);
  * a record that does not stand alone (no line, no reading, no snapshot), or a log that is
    rewritten instead of appended;
  * a report zip that leaves the engine log behind while it carries corrections.jsonl;
  * the ruling bench's frozen set touched by the play export.
"""
from __future__ import annotations

import gzip
import json

import pytest
from django.test import Client, override_settings

from rules import awareness, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate

GOBLIN_TELL = "Grak Snaggletooth's attack hits Kesst Vayr (17 against AC 15) for 4."
SECRET_TELL = "The guard watches Kesst closely and believes her."


def _hide(scene, who):
    who.apply_effect(ActiveEffect(
        name="Hidden", kind="condition", key=awareness.SNEAKING_KEY,
        source=awareness.STEALTH_ORIGIN, origin=awareness.STEALTH_ORIGIN,
        duration="until-dismissed", tags=states.tags_for(awareness.SNEAKING_KEY),
        payload={"result": 30, "at": scene.at, "ends_when": dict(awareness.ENDS_ON_ATTACK),
                 "pace": "half"}))


def _roll(label, total, vis, die="1d20"):
    return {"die": die, "faces": [total - 3], "raw": total - 3, "natural": total - 3,
            "modifiers": [{"value": 3, "source": "Dex"}], "modifier_total": 3,
            "total": total, "label": label, "visibility": vis}


@pytest.fixture
def table(tmp_path):
    from play import campaign as cm
    from play import concurrency, history
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "data" / "campaigns")):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        cm.set_active(c.id)
        gob = instantiate("goblin", scene=c.scene)
        gob.name = "Grak Snaggletooth"
        c.scene.add(gob)
        _hide(c.scene, gob)
        assert not awareness.player_locates(c.scene, gob)

        def turn(line, outcomes, reading=None, intents=()):
            c.save()
            c.transcript.append({"who": "player", "text": line})
            c.save()
            row = {"kind": "turn", "intents": list(intents), "outcomes": outcomes}
            if reading:
                row["reading"] = reading
            c.turn_log.append(history.stamp(c, row))
            c.transcript.append({"who": "gm", "kind": "setup", "text": "Beat for " + line})
            c.save()
            return len(c.transcript) - 1

        yield {"c": c, "gob": gob, "turn": turn, "root": tmp_path / "data"}
        cm._LIVE.clear()


def _played(t):
    """A turn of a buy, a seen check, a hidden goblin's swing and a secret Sense Motive."""
    gob = t["gob"]
    reading = {"question": False, "claims": [], "dropped": [],
               "actions": [{"act": "buy", "span": "buy a rope"},
                           {"act": "talk", "span": "tell the guard I'm the duke's cousin"},
                           {"act": "search", "span": "look for the thief"}],
               "table": [{"act": "buy", "ops": ["buy"]}, {"act": "talk", "ops": ["check"]},
                         {"act": "search", "ops": []}]}
    outcomes = [
        {"intent_id": "i1", "op": "buy", "status": "resolved", "rolls": [], "dc": None,
         "verdict": None, "margin": None, "effects": [{"kind": "give", "ref": "pc"}],
         "tell": "Kesst Vayr pays 1 gold piece for a hemp rope.", "because": "",
         "actor": "pc"},
        {"intent_id": "i2", "op": "check", "status": "resolved",
         "rolls": [_roll("Bluff check", 19, "player"), _roll("guard Sense Motive", 11, "hidden")],
         "dc": {"value": 11}, "verdict": "success", "margin": 8, "effects": [],
         "tell": "Kesst's lie holds (19 against 11).", "because": "", "actor": "pc"},
        {"intent_id": "n1", "op": "attack", "status": "resolved",
         "rolls": [_roll("attack", 17, "hidden")], "dc": {"value": 15}, "verdict": "hit",
         "margin": 2, "effects": [{"kind": "damage", "ref": "pc", "by": gob.ref}],
         "tell": GOBLIN_TELL, "because": "", "actor": gob.ref},
        # A creature in the open swings: its roll is hidden like every NPC roll, and the
        # swing is still the player's to see (the sergeant's longspear, live 2026-11-15).
        {"intent_id": "n2", "op": "attack", "status": "resolved",
         "rolls": [_roll("attack", 13, "hidden")], "dc": {"value": 15}, "verdict": "miss",
         "margin": -2, "effects": [], "actor": "c99",
         "tell": "The sergeant's attack misses Kesst Vayr (13 against AC 15)."},
        {"intent_id": "", "op": "check", "status": "resolved",
         "rolls": [_roll("Sense Motive", 23, "hidden"),
                   _roll("oracle", 64, "hidden", die="1d100")],
         "dc": {"value": 15}, "verdict": "success", "margin": 8, "effects": [],
         "tell": SECRET_TELL, "because": ""},
        {"intent_id": "i3", "op": "take", "status": "refused", "rolls": [], "dc": None,
         "verdict": None, "margin": None, "effects": [], "tell": "pc cannot take that.",
         "for_a_person": "Nobody here is selling a horse.", "because": "", "code": "x"},
    ]
    return t["turn"]("I buy a rope and tell the guard I'm the duke's cousin.", outcomes,
                     reading)


def test_a_hidden_foe_and_a_hidden_roll_never_reach_the_page(table):
    """The page shows the PC's own Bluff 19 and the rope's price; it never shows the hidden
    goblin's swing (its name, its ref, its 17), the guard's secret 11 the Bluff was
    measured against, or the secret Sense Motive 23 / oracle 64 check at all."""
    from play import engine_corrections as ec

    c = table["c"]
    i = _played(table)
    r = Client().get(f"/api/beat/engine?beat={i}")
    assert r.status_code == 200
    body = r.content.decode("utf-8")
    page = r.json()
    texts = [ln["text"] for ln in page["lines"]]
    assert "Kesst Vayr pays 1 gold piece for a hemp rope." in texts
    assert any(t.startswith("Kesst's lie holds") for t in texts)
    assert "Refused: Nobody here is selling a horse." in texts
    assert "The sergeant's attack misses Kesst Vayr." in texts
    assert any("No rule was applied to “look for the thief”" in t for t in texts)
    bluff = next(ln for ln in page["lines"] if ln["text"].startswith("Kesst's lie"))
    assert bluff["rolls"] == ["Bluff check: 19 (16 +3 Dex)"]          # no "vs 11"
    for leak in ("Grak", "Snaggletooth", table["gob"].ref, "17", "23", "64", "oracle",
                 "Sense Motive", SECRET_TELL, " 11", "13 against", "AC 15"):
        assert leak not in body, leak
    # The log keeps everything.
    rec = ec.log(c, i, [{"line": bluff["id"], "kind": "needs_roll", "note": "x"}])
    raw = json.dumps(rec)
    assert GOBLIN_TELL in raw and SECRET_TELL in raw


def test_each_beat_is_shown_its_own_turn(table):
    """Two turns: the first beat's record is the first turn's rows and nothing after."""
    from play import engine_corrections as ec

    a = table["turn"]("I wait.", [{"op": "advance_time", "tell": "An hour passes.",
                                   "rolls": [], "status": "resolved"}])
    b = table["turn"]("I go.", [{"op": "move", "tell": "Kesst walks to the door.",
                                 "rolls": [], "status": "resolved"}])
    c = table["c"]
    assert [ln["text"] for ln in ec.lines(c, a)] == ["An hour passes."]
    assert [ln["text"] for ln in ec.lines(c, b)] == ["Kesst walks to the door."]


def test_the_record_stands_alone_is_appended_and_carries_the_start_of_turn(table):
    """Two marks in one turn, a missing thing, and a second record: two lines in the file,
    neither rewritten; the snapshot is the save from before the player's line (`.1`)."""
    from play import engine_corrections as ec

    c = table["c"]
    i = _played(table)
    lines = Client().get(f"/api/beat/engine?beat={i}").json()["lines"]
    r = Client().post("/api/beat/engine", content_type="application/json", data=json.dumps(
        {"beat": i, "marks": [{"line": lines[0]["id"], "kind": "should_work"},
                              {"line": lines[-1]["id"], "kind": "wrong_number",
                               "note": "y" * 900},
                              {"line": "missing", "kind": "missing",
                               "note": "the guard never answered"}]}))
    assert r.status_code == 200, r.content
    first = ec.log_path().read_bytes()
    ec.log(c, i, [{"line": "missing", "kind": "missing"}])
    assert ec.log_path().read_bytes().startswith(first)
    recs = ec.read_log()
    assert len(recs) == 2
    rec = recs[0]
    assert rec["player_line"].startswith("I buy a rope")
    assert rec["reading"]["actions"][0]["span"] == "buy a rope"
    assert [m["kind"] for m in rec["marks"]] == ["should_work", "wrong_number", "missing"]
    assert len(rec["marks"][1]["note"]) == ec.MAX_NOTE
    assert rec["app_version"] and rec["campaign"] == c.id
    snap = rec["snapshot"]
    assert snap["from"].endswith(".1") and snap["bytes"] > 0
    saved = json.loads(gzip.decompress(
        (ec.corrections.training_dir() / snap["file"]).read_bytes()))
    assert not any(b.get("who") == "player" for b in saved["transcript"])
    # Marking saved the game the first cut of this, and a save can rotate the backups:
    # the second mark on the same turn must still find its start (live 2026-11-15).
    assert recs[1]["snapshot"]["from"].endswith(".1")
    assert not any(r.get("kind") == "engine-correction" for r in c.turn_log)


def test_a_mark_on_a_line_the_page_never_showed_is_refused(table):
    from play import engine_corrections as ec

    i = _played(table)
    hidden = next(f"r{n}.o2" for n, _r in ec.rows_for(table["c"], i))
    for marks in ([{"line": hidden, "kind": "shouldnt"}], [{"line": "r0.o0", "kind": "?"}],
                  []):
        with pytest.raises(ec.Refused):
            ec.log(table["c"], i, marks)


def test_the_report_carries_the_engine_log_and_its_snapshot(table):
    from play import engine_corrections as ec
    from play import report

    c = table["c"]
    i = _played(table)
    ec.log(c, i, [{"line": "missing", "kind": "missing"}])
    names = [m.name for m in report.members(include_save=True)]
    assert "training/engine-corrections.jsonl" in names
    assert any(n.startswith("training/engine-snapshots/") and n.endswith(".json")
               for n in names)


def test_the_play_export_makes_candidate_lines_and_never_the_frozen_set(table, tmp_path):
    """needs_roll/should_work/shouldnt are roll/say_yes/refuse; the others are not rulings."""
    from play import engine_corrections as ec
    from tools.ruling_bench import from_play

    c = table["c"]
    i = _played(table)
    lines = ec.lines(c, i)
    talk = next(ln["id"] for ln in lines if "duke" in ln["text"])
    ec.log(c, i, [{"line": talk, "kind": "needs_roll"},
                  {"line": lines[0]["id"], "kind": "wrong_number"},
                  {"line": "missing", "kind": "missing"}])
    got = from_play.candidates(ec.read_log())
    assert [(g["verdict"], g["text"], g["split"], g["author"]) for g in got] == [
        ("roll", "tell the guard I'm the duke's cousin", "play", "owner-play")]
    assert from_play.main([str(ec.log_path()), "--out",
                           str(tmp_path / "ruling-set.json")]) == 2
