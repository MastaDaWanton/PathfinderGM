""""That's wrong": a beat the player marks wrong is remade, put right everywhere the game
keeps it, and logged as training data (play/corrections.py; the owner, 2026-10-09).

The narrator — gemma-4-12B on the player's own machine — makes an error within about three
beats. Each test here names the defect it prevents:

  * the narrator continuing a beat the player had marked wrong, because the remake reached
    the page but not `earlier` (`own_prose`), the planner's history or the conversation
    log — every store a beat lives in;
  * "Put the first one back" restoring the page and leaving the remake in the history;
  * a fourth remake after three the player also rejected;
  * a record that is not self-contained — no prompt, no versions, no verdicts — or that
    never says the player moved on (`implicit: true`);
  * an export that pairs a beat with nothing, or drops the episodes that never got a good
    version (the ones KTO is for);
  * a log path anchored on `__file__`, which lies inside the frozen bundle.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from django.test import Client, override_settings

from gm import client as gm_client
from gm import narration

WRONG_SENTENCE = "The guard crumples to the cobbles, dead before he lands."
WRONG = ("Your blade flashes in the lamplight. " + WRONG_SENTENCE
         + " The street goes very quiet. What do you do?")
FIXED = ("Your blade flashes in the lamplight and the guard twists aside; the steel "
         "rings off his buckler. He sets his feet, breathing hard. What do you do?")
SECOND = ("The guard turns your cut on his buckler and steps back out of reach, eyes "
          "never leaving your blade. What do you do?")
TELL = "Kesst attacks the guard: 7 + 3 = 10 against AC 15 — a miss."
PROMPT = [{"role": "system", "content": "You are the Game Master."},
          {"role": "user", "content": "The player said: I swing at the guard."}]


class _Reply:
    def __init__(self, text, model="stub-narrator"):
        self.text, self.seconds, self.model = text, 1.5, model
        self.prompt_tokens = self.reply_tokens = 0
        self.done_reason = "stop"

    def json(self):
        return json.loads(self.text)


class _Outcome:
    """The one tell the turn produced, in the shape `_finish` reads."""
    op = "attack"
    tell = TELL
    effects: list = []
    status = "resolved"

    def as_dict(self):
        return {"op": self.op, "tell": self.tell, "effects": [], "status": self.status}


@pytest.fixture
def table(tmp_path, monkeypatch):
    """A campaign in play, a way to play a turn whose beat is `text`, and the repair
    calls the remake makes (each one's messages, in order)."""
    from gm import watcher
    from gm.agent import GMAgent
    from play import campaign as cm
    from play import concurrency, views
    from rules.engine import Resolution
    from rules.sheet import load_pc

    monkeypatch.setattr(watcher, "kick", lambda c: None)
    asked: list[list[dict]] = []
    replies: list[str] = []

    def chat(messages, *a, **k):
        asked.append(messages)
        return _Reply(json.dumps({"narration": replies.pop(0) if replies else FIXED}))

    monkeypatch.setattr(gm_client, "chat", chat)
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "data" / "campaigns")):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        cm.set_active(c.id)
        shown: list[list[str]] = []

        def turn(text, player="I swing at the guard."):
            def narrate(self, outcomes, player_input, brief, earlier=None, **k):
                shown.append(list(earlier or []))
                self.last_prose_messages = PROMPT
                self.last_prose_model = "gemma-stub"
                self.last_prose_draft = text
                self.last_said = []
                return text, [], []

            monkeypatch.setattr(GMAgent, "narrate_turn", narrate)
            agent = GMAgent(c.world, c.engine())
            views._arm_cards(agent, c)
            agent.intents_first = True
            c.transcript.append({"who": "player", "text": player})
            views._finish(c, agent, Resolution(outcomes=[_Outcome()]), "", player, None,
                          hand_over=False)
            return max(i for i, b in enumerate(c.transcript)
                       if b.get("kind") == "setup")

        yield {"c": c, "turn": turn, "asked": asked, "replies": replies,
               "shown": shown, "root": tmp_path / "data"}
        cm._LIVE.clear()


def _post(**body):
    return Client().post("/api/beat/correct", data=json.dumps(body),
                         content_type="application/json")


def _log(root: Path) -> list[dict]:
    from play import corrections

    return corrections.read_log(root / "training" / "corrections.jsonl")


# --- the remake reaches every store ------------------------------------------------------

def test_the_remake_replaces_the_beat_everywhere_the_narrator_reads_it(table):
    """The defect: a wrong beat fixed on the page but left in `earlier` is continued by the
    narrator next turn — "the guard crumples, dead" stays the narrator's own last beat,
    and it writes the corpse into the next one. The remake must reach the transcript, the
    narrator's `earlier` (own_prose), the planner's history, and be what the next prose
    call is shown."""
    c, turn = table["c"], table["turn"]
    i = turn(WRONG)
    r = _post(beat=i, do="fix", sentences=[WRONG_SENTENCE], note="he missed, the dice said so")
    assert r.status_code == 200, r.content
    assert c.transcript[i]["text"] == FIXED
    assert narration.own_prose(c.transcript)[-1] == FIXED
    assert not any(WRONG_SENTENCE in b for b in narration.own_prose(c.transcript))
    assert not any(WRONG_SENTENCE in str(m.get("content")) for m in c.history)
    assert any(m.get("content") == FIXED for m in c.history)

    # The repair call was asked with the player's sentence, their note, and the tell.
    repair = table["asked"][-1][-1]["content"]
    assert WRONG_SENTENCE in repair and "he missed" in repair and TELL in repair

    # And the next turn's narrator is shown the remake, never the beat marked wrong.
    turn("The guard steps back. What do you do?", player="I press him.")
    assert FIXED in table["shown"][-1]
    assert not any(WRONG_SENTENCE in b for b in table["shown"][-1])
    # The page draws from the state, which carries the offers for the new turn only.
    st = Client().get("/api/state").json()
    assert st["transcript"][i]["text"] == FIXED


def test_putting_the_first_one_back_restores_it_in_every_store(table):
    """The defect: "Put the first one back" restored the page and left the remake in the
    history the planner reads — two versions of one beat, one on screen and the other in
    the model's context."""
    c, turn = table["c"], table["turn"]
    i = turn(WRONG)
    assert _post(beat=i, do="fix").status_code == 200
    assert c.transcript[i]["text"] == FIXED
    r = _post(beat=i, do="put_back")
    assert r.status_code == 200, r.content
    assert c.transcript[i]["text"] == WRONG
    assert narration.own_prose(c.transcript)[-1] == WRONG
    assert any(m.get("content") == WRONG for m in c.history)
    assert not any(m.get("content") == FIXED for m in c.history)
    rec = _log(table["root"])[-1]
    assert [v["verdict"] for v in rec["versions"]] == ["wrong", "reverted"]
    assert rec["outcome"] == "put back"


def test_three_rejected_remakes_and_the_fix_button_is_gone(table):
    """The owner's rule: after three remakes the player also rejected, no fourth — the
    panel offers only writing it, putting the first back, or leaving it. Measured as the
    server's refusal and the state's `remake: false`, not as a hidden button alone."""
    c, turn = table["c"], table["turn"]
    i = turn(WRONG)
    table["replies"].extend([FIXED, SECOND, "A third try at the same miss. What do you do?"])
    for n in range(3):
        assert _post(beat=i, do="fix").status_code == 200, n
    st = Client().get("/api/state").json()["corrections"]["beats"][str(i)]
    assert st["remakes"] == 3 and st["remake"] is False and st["remakes_left"] == 0
    assert st["write"] and st["put_back"]
    r = _post(beat=i, do="fix")
    assert r.status_code == 409 and "3 times" in r.json()["error"]
    # Writing it is still open, and the player's words become the beat.
    mine = "You miss. The guard laughs at you. What do you do?"
    assert _post(beat=i, do="write", text=mine).status_code == 200
    assert c.transcript[i]["text"] == mine
    rec = _log(table["root"])[-1]
    assert [v["by"] for v in rec["versions"]] == ["narrator", "remake", "remake", "remake",
                                                  "player"]
    assert [v["verdict"] for v in rec["versions"]] == ["wrong"] * 4 + ["kept"]
    assert rec["versions"][-1]["implicit"] is False
    assert rec["outcome"] == "player wrote"


def test_the_record_is_whole_and_moving_on_keeps_the_remake_implicitly(table):
    """The defect a training log can have: a record that needs the save to read (no
    prompt), or one that never closes. One record per episode, self-contained: the
    prose call's own messages, every version with its verdict, the repair call's
    messages for each remake — and when the player sends the next turn, the version on
    the page is `kept` with `implicit: true`, weaker than a Keep pressed by hand."""
    c, turn = table["c"], table["turn"]
    i = turn(WRONG)
    _post(beat=i, do="fix", sentences=[WRONG_SENTENCE, "not in the beat at all"],
          note="he missed")
    rec = _log(table["root"])[-1]
    assert rec["format"] == 1 and rec["campaign"] == c.id and rec["beat"] == i
    assert rec["narrator_model"] == "gemma-stub" and rec["app_version"]
    assert rec["input"]["captured"] and rec["input"]["messages"] == PROMPT
    assert rec["input"]["facts"] == [TELL]
    first, remade = rec["versions"]
    # A sentence the beat does not hold is not recorded as flagged.
    assert first["flagged_sentences"] == [WRONG_SENTENCE] and first["note"] == "he missed"
    assert first["verdict"] == "wrong" and first["by"] == "narrator"
    assert remade["by"] == "remake" and remade["verdict"] is None
    assert remade["repair_messages"][-1]["content"].count(WRONG_SENTENCE) >= 1
    assert rec["closed"] is False

    turn("The guard steps back. What do you do?", player="I press him.")
    rec = _log(table["root"])[-1]
    assert rec["closed"] is True and rec["outcome"] == "remake kept"
    assert rec["versions"][1]["verdict"] == "kept" and rec["versions"][1]["implicit"] is True
    # The save no longer carries the versions: the log has them.
    assert c.transcript[i]["fix"] == {"id": rec["id"], "closed": True,
                                      "outcome": "remake kept", "versions": 2}
    # And the beat is no longer remade: later beats stand on it.
    assert _post(beat=i, do="fix").status_code == 409


def test_an_explicit_keep_is_not_implicit(table):
    turn = table["turn"]
    i = turn(WRONG)
    _post(beat=i, do="fix")
    assert _post(beat=i, do="keep").status_code == 200
    turn("Next. What do you do?", player="I wait.")
    v = _log(table["root"])[-1]["versions"][1]
    assert v["verdict"] == "kept" and v["implicit"] is False


def test_an_older_beat_is_marked_and_logged_never_remade(table):
    """An older beat has later beats built on it, so it is marked wrong and logged —
    "left wrong" — and the page is not changed."""
    c, turn = table["c"], table["turn"]
    i = turn(WRONG)
    turn("Next. What do you do?", player="I wait.")
    assert _post(beat=i, do="fix").status_code == 409
    assert _post(beat=i, do="write", text="Mine.").status_code == 409
    r = _post(beat=i, do="mark", sentences=[WRONG_SENTENCE])
    assert r.status_code == 200
    assert c.transcript[i]["text"] == WRONG
    rec = _log(table["root"])[-1]
    assert rec["outcome"] == "left wrong" and rec["closed"] is True
    assert rec["versions"][0]["flagged_sentences"] == [WRONG_SENTENCE]
    # Marked once: the state no longer offers it.
    st = Client().get("/api/state").json()["corrections"]["beats"][str(i)]
    assert st["flaggable"] is False


def test_an_empty_remake_leaves_the_beat_and_says_so(table):
    """A remake that came back empty was going to replace the beat with nothing. Refused
    with words; the beat stands; the failed call is still logged."""
    c, turn = table["c"], table["turn"]
    i = turn(WRONG)
    table["replies"].append("")
    r = _post(beat=i, do="fix")
    assert r.status_code == 502 and "nothing usable" in r.json()["error"]
    assert c.transcript[i]["text"] == WRONG
    assert _log(table["root"])[-1]["failed_remakes"]


def test_the_conversation_log_follows_the_remake(table):
    """A line the wrong beat booked must not outlive it in the conversation log."""
    c, turn = table["c"], table["turn"]
    i = turn(WRONG)
    ref = next(r for r, a in c.scene.actors.items() if not a.is_pc)
    c.transcript[i]["said"] = [{"who": ref, "to": "you", "line": "You'll hang for this."}]
    c.scene.conversation_log = [{"n": 1, "beat": i, "who": ref, "kind": "line",
                                 "text": "You'll hang for this.", "src": "tag"},
                                {"n": 2, "beat": i, "who": "you", "kind": "line",
                                 "text": "Stand aside.", "src": "player"}]
    _post(beat=i, do="fix")
    texts = [e["text"] for e in c.scene.conversation_log]
    assert "You'll hang for this." not in texts and "Stand aside." in texts


# --- the export ----------------------------------------------------------------------------

def test_the_exporter_pairs_kept_against_wrong_and_keeps_the_unpaired():
    """DPO needs a chosen; KTO does not. An episode the player only ever rejected gives no
    pair and still gives its bad examples."""
    from tools.corrections_to_pairs import convert

    good = {"input": {"messages": PROMPT}, "id": "a", "versions": [
        {"by": "narrator", "text": WRONG, "model_text": WRONG, "verdict": "wrong"},
        {"by": "remake", "text": FIXED, "model_text": FIXED, "verdict": "kept",
         "implicit": True, "repair_messages": [{"role": "user", "content": "fix"}]}]}
    lost = {"input": {"messages": PROMPT}, "id": "b", "versions": [
        {"by": "narrator", "text": WRONG, "model_text": WRONG, "verdict": "wrong"},
        {"by": "remake", "text": SECOND, "model_text": SECOND, "verdict": "wrong",
         "repair_messages": [{"role": "user", "content": "fix"}]}]}
    blind = {"input": {"captured": False}, "id": "c", "versions": [
        {"by": "narrator", "text": WRONG, "verdict": "wrong"}]}
    sets = convert([good, lost, blind])
    dpo = sets["pairs.dpo.jsonl"]
    assert len(dpo) == 1 and dpo[0]["prompt"] == PROMPT
    assert json.loads(dpo[0]["chosen"][0]["content"]) == {"narration": FIXED}
    assert json.loads(dpo[0]["rejected"][0]["content"]) == {"narration": WRONG}
    assert dpo[0]["meta"]["implicit"] is True
    kto = sets["examples.kto.jsonl"]
    assert [r["label"] for r in kto] == [False, True, False, False]
    assert [r["label"] for r in sets["repair.kto.jsonl"]] == [True, False]
    assert convert([good], explicit_only=True)["pairs.dpo.jsonl"] == []
    assert convert([good], plain=True)["pairs.dpo.jsonl"][0]["chosen"][0]["content"] == FIXED


def test_the_exporter_reads_a_real_log(table, tmp_path):
    """End to end over the file the table writes: a remake kept by moving on is one pair."""
    from tools.corrections_to_pairs import main

    turn = table["turn"]
    i = turn(WRONG)
    _post(beat=i, do="fix", sentences=[WRONG_SENTENCE])
    turn("Next. What do you do?", player="I wait.")
    log = table["root"] / "training" / "corrections.jsonl"
    assert main([str(log), "--out", str(tmp_path / "out")]) == 0
    rows = (tmp_path / "out" / "pairs.dpo.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1


# --- where it lives --------------------------------------------------------------------------

def test_the_log_lives_in_the_data_folder_never_beside_the_code(table, monkeypatch):
    """CLAUDE.md: `__file__` points inside the PyInstaller bundle once frozen. The log is
    under the data folder `CAMPAIGN_DIR` sits in (`paths.user_data_root()` in the app),
    and stays there with the app frozen."""
    import sys

    from play import corrections

    import ast

    tree = ast.parse(inspect.getsource(corrections))
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "__file__"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(table["root"] / "_MEI12345"), raising=False)
    assert corrections.log_path() == table["root"] / "training" / "corrections.jsonl"


def test_the_report_carries_the_log_with_the_save_and_withholds_intimate_prompts(table):
    """Report-a-problem includes `training/corrections.jsonl` when "Include the save" is
    ticked, and not otherwise; an intimate beat's prompt (the table's own passages) never
    leaves the machine in it."""
    from play import corrections, report

    turn = table["turn"]
    i = turn(WRONG)
    _post(beat=i, do="fix")
    names = [m.name for m in report.members(probe=False)]
    assert "training/corrections.jsonl" in names
    assert "training/corrections.jsonl" not in [
        m.name for m in report.members(include_save=False, probe=False)]

    rec = _log(table["root"])[-1]
    rec["intimate"] = True
    corrections._write_record(rec)
    sent = json.loads(corrections.for_report().splitlines()[-1])
    assert "messages" not in sent["input"] and sent["input"]["messages_withheld"]
    assert all("repair_messages" not in v for v in sent["versions"])
    # The local log keeps the prompt.
    assert _log(table["root"])[-1]["input"]["messages"] == PROMPT


def test_settings_counts_the_corrections(table):
    turn = table["turn"]
    assert Client().get("/api/corrections").json()["episodes"] == 0
    i = turn(WRONG)
    _post(beat=i, do="fix")
    got = Client().get("/api/corrections").json()
    assert got["episodes"] == 1 and got["versions"] == 2
    assert got["folder"].endswith("training")
