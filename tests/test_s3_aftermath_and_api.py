"""S3 of the 2026-09-28 fix pass: the after-the-beat registry and the API contract, inert.

`play/aftermath/` is where Phase 2's bookkeeping steps land — a speaker made real (A), a
person placed elsewhere (D), a line into the conversation log (F) — one module each, found
by filename, run from `views._finish` at two stages (docs/fix-interfaces.md §2.3). The plan
had one hook "after the said/hails block"; the critic pass measured that the hails are not
there (§1.1 P3): `hailed_by` → `join_talk` runs a hundred lines earlier, so a speaker made
real after it would never join the conversation. Hence "people" before `hailed_by` and
"beat" after the speech-tags row.

What this file holds S3 to:

  * **Inert.** Measured the day it landed against the code before it (phase-1-s3-base,
    460f7c2) by a whole-turn replay of all 104 recorded audit turns in tests/replay/
    through the real `/api/say` (the model's recorded replies handed back in order, dice
    seeded, the player's die answered with the middle of its range) plus the Bobby
    corpus's 13 beats through `_finish`: 842 model calls, 556 turn-log rows, 277
    transcript beats — 134 of them through both aftermath call sites — and every
    `/api/state` after each turn. With S3's new state keys taken out, one dump,
    byte-identical on both (sha256 5f137be0…). The suite keeps a sample of that replay
    and holds it to "a registered member that returns nothing changes nothing".
  * **Discovery by filename**, `_`-prefixed helpers, (STAGE, ORDER, name) order, and a
    member that breaks the contract refused with the fix named.
  * **A broken step never costs the turn**: its exception is an `aftermath-error` row.
  * **"people" runs before `hailed_by`**, on the live `said`, so a speaker it names joins
    the conversation on the same beat.
  * Every §2.10 `/api/state` key at its default shape; `GET /api/conversation` paging; the
    `/api/say` attachment rules, each a 400 with a sentence; the stored attachment; the
    §2.6 refusal shape.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pytest
from django.test import Client, override_settings

import replays
from gm import judgement
from play import aftermath
from play.aftermath import AfterBeat, AftermathContractError

ROOT = Path(__file__).resolve().parent.parent
REPLAY = ROOT / "tests" / "replay"

# The `/api/state` keys that stood before S3, in the order they are sent. Read off the
# base (460f7c2); S3 adds keys after these and changes none of them.
OLD_TOP = ["transcript", "world", "coinage", "suggestions", "quests", "schemes", "merchant",
           "awaiting", "pc", "scene", "abilities", "attacks", "log"]
OLD_SCENE = ["location", "scale", "what_it_is", "biome", "biome_describe", "round",
             "in_encounter", "talk", "busy", "turn_ref", "initiative", "clock_minutes",
             "actors", "grid", "pools"]
NEW_TOP = ["spellcasting", "start"]
NEW_SCENE = ["where_label", "where_detail", "setting", "conversation", "day_part",
             "exits",          # I6, the "From here" row (Phase 3)
             "places_found",   # the fog-of-war place chart (2026-09-30)
             "writings"]       # notes and maps written with ink and paper (2026-10-01)


# --- helpers ------------------------------------------------------------------------------

class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"
        self.prompt_tokens = self.reply_tokens = 0
        self.done_reason = "stop"

    def json(self):
        return json.loads(self.text)


_WAIT = json.dumps({"narration": "You wait, and the room goes on around you. "
                                 "What do you do?",
                    "intents": [{"op": "narrate_only", "because": "waits"}]})


@pytest.fixture
def package(tmp_path, monkeypatch):
    """`play.aftermath` with a throwaway directory on its path: a module written there is a
    member exactly as a file in play/aftermath/ would be."""
    where = tmp_path / "aftermath_members"
    where.mkdir()
    monkeypatch.setattr(aftermath, "__path__", [str(where)])
    written: list[str] = []

    def write(name, body):
        (where / f"{name}.py").write_text(body, encoding="utf-8")
        written.append(f"play.aftermath.{name}")
        sys.modules.pop(f"play.aftermath.{name}", None)

    yield write
    for mod in written:
        sys.modules.pop(mod, None)


_RECORDER = '''
CALLS = []
STAGE = {stage!r}
ORDER = {order}
{doors}
def step(ctx):
    CALLS.append(ctx)
    return {rows}
'''


def _recorder(stage, order=50, rows="[]", doors=""):
    return _RECORDER.format(stage=stage, order=order, rows=rows, doors=doors)


def _member(name):
    return sys.modules[f"play.aftermath.{name}"]


def _wall_clock_out(x):
    """The dump without the turn log's `seconds`: wall-clock time (the reading's own
    `seconds` is `time.monotonic()` rounded to a hundredth), which a loaded machine can
    move between two otherwise identical replays."""
    if isinstance(x, dict):
        return {k: _wall_clock_out(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [_wall_clock_out(v) for v in x]
    return x


def _dump_turn(c, t0, l0, extra=None):
    return _wall_clock_out(json.loads(json.dumps(
        {"transcript": c.transcript[t0:], "turn_log": c.turn_log[l0:], **(extra or {})},
        sort_keys=True, default=str)))


def _first_difference(a, b, path="") -> str:
    """Where two dumps part, and what each holds there — for a failure worth reading."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(a) + [k for k in b if k not in a]:
            if a.get(k) != b.get(k):
                return _first_difference(a.get(k), b.get(k), f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return _first_difference(x, y, f"{path}[{i}]")
        if len(a) != len(b):
            return f"{path}: {len(a)} items against {len(b)}"
    return f"{path}: {str(a)[:200]!r} against {str(b)[:200]!r}"


def _answer_the_die(client, cm):
    """Every die the turn waits on, answered with the middle of its range: chosen, so two
    replays roll alike (an unanswered face is rolled unseeded), and legal for any die — an
    11 is refused on a d6 and the turn stays waiting."""
    for _ in range(12):
        prompt = cm.current().scene.awaiting
        if not prompt:
            return
        face = (int(prompt.get("min", 1)) + int(prompt.get("max", 20))) // 2
        client.post("/api/roll", data=json.dumps({"face": face}),
                    content_type="application/json")


def _replay_sample(tmp_path, monkeypatch, per_file=2):
    """Recorded audit turns through the real `/api/say`: the save before the turn, the
    model's recorded replies in order, seeded dice, the player's die answered with the
    middle of its range. What each turn wrote and the state after it."""
    from gm import client as gm_client
    from gm import interpret, watcher
    from play import campaign as cm
    from play import concurrency
    from rules import population

    # The recorded turns read the sentence first; on, so each reply meets its own call
    # (tests/_replay.py says what happens otherwise).
    monkeypatch.setattr(interpret, "ENABLED", True)
    monkeypatch.setattr(watcher, "kick", lambda c: None)
    monkeypatch.setattr(watcher, "drain", lambda c: False)
    out = []
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "replay-campaigns")):
        for f in sorted(REPLAY.glob("*.jsonl.gz")):
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                recs = [json.loads(line) for line in fh]
            picks = sorted({0, len(recs) // 2})[:per_file]
            for i in picks:
                rec = recs[i]
                replies = [call["raw"] for call in rec["calls"]]
                monkeypatch.setattr(gm_client, "chat", lambda *a, _r=replies, **k: _Reply(
                    _r.pop(0) if _r else _WAIT))
                save = dict(rec["save_before"], seed=20260928 + i)
                # The population's missed-search buffer is module-level, and `_finish`
                # drains it into the turn log: a miss another test left in this worker
                # landed on the first replayed turn once, under the full suite.
                population.drain_misses()
                cm._LIVE.clear()
                concurrency.reset_for_tests()
                Path(tmp_path / "replay-campaigns").mkdir(parents=True, exist_ok=True)
                (tmp_path / "replay-campaigns" / f"{save['id']}.json").write_text(
                    json.dumps(save), encoding="utf-8")
                cm.set_active(save["id"])
                c = cm.current()
                t0, l0 = len(c.transcript), len(c.turn_log)
                client = Client()
                # A fight recorded mid-roll answers the die first, as the audit did.
                _answer_the_die(client, cm)
                r = client.post("/api/say", data=json.dumps({"text": rec["player"]}),
                                content_type="application/json")
                _answer_the_die(client, cm)
                c = cm.current()
                out.append(_dump_turn(c, t0, l0, {
                    "where": f"{f.name}:{i}", "status": r.status_code,
                    "state": client.get("/api/state").json()}))
        cm._LIVE.clear()
    return out


def _bobby_beats(tmp_path, monkeypatch):
    """The owner's playtest of 2026-09-28: each of the 13 beats through `_finish`, the prose
    call standing in with the beat the player saw and the lines tagged on it."""
    from gm import client as gm_client
    from gm import watcher
    from gm.agent import GMAgent
    from play import campaign as cm
    from play import views
    from rules import population
    from rules.bestiary import instantiate
    from rules.engine import Resolution, Scene, _rehydrate
    from rules.sheet import load_pc
    from world.loader import load_cached

    monkeypatch.setattr(watcher, "kick", lambda c: None)
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: _Reply(_WAIT))
    out = []
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "bobby-campaigns")):
        world = load_cached("fixtures/aurvantis-campaign.json")
        s = Scene(location_id=world.by_name("Vormoor", kind="CITY").id)
        s.add(load_pc("fixtures/pc-kesst.json"))
        for p in replays.save("bobby.json")["people"]:
            if p["kind"] != "pc":
                s.add(instantiate(p.get("from_template") or "guildhand", scene=s,
                                  name=p["name"]))
        c = cm.Campaign(id="bobby-s3", world_source="fixtures/aurvantis-campaign.json",
                        scene=s, seed=7)
        c.engine().place_party()
        cm._LIVE.clear()
        cm._LIVE["bobby-s3"] = c
        cm.set_active("bobby-s3")
        for t in replays.turns():
            beat = t["beats"][0]

            def narrate(self, *a, _b=beat, **k):
                self.last_said = [dict(r) for r in (_b.get("said") or [])]
                return _b["text"], [], []

            monkeypatch.setattr(GMAgent, "narrate_turn", narrate)
            agent = GMAgent(c.world, c.engine())
            views._arm_cards(agent, c)
            agent.intents_first = True
            outcomes = [_rehydrate(o) for o in
                        ((t.get("resolution") or {}).get("outcomes")
                         or (t.get("plan") or {}).get("outcomes") or [])]
            c.transcript.append({"who": "player", "text": t["player"]})
            population.drain_misses()     # another test's leftovers (see _replay_sample)
            t0, l0 = len(c.transcript), len(c.turn_log)
            resp = views._finish(c, agent, Resolution(outcomes=outcomes), "", t["player"],
                                 None)
            out.append(_dump_turn(c, t0, l0, {"n": t["n"],
                                              "state": json.loads(resp.content)}))
        cm._LIVE.clear()
    return out


# --- inert ----------------------------------------------------------------------------------

def test_the_real_registry_holds_the_phase_2_steps():
    """Phase 1 shipped the registry empty; Phase 2's lanes are its members (the change
    this test's Phase-1 docstring asked for, on purpose): Lane A's `speaker_real` (item
    20.4), Lane D's three "beat" steps in the register's order (§2.3:
    mentioned_elsewhere 20, pronouns_adopted 30, suggestion_pronouns 40), and Lane F's
    conversation log at the beat stage's ORDER 50, which also runs on the opening."""
    names = [m.__name__.rsplit(".", 1)[-1] for m in aftermath.registered()]
    assert "speaker_real" in names
    mine = [n for n in names if n in ("mentioned_elsewhere", "pronouns_adopted",
                                      "suggestion_pronouns")]
    assert mine == ["mentioned_elsewhere", "pronouns_adopted", "suggestion_pronouns"]
    by_name = {m.__name__.rsplit(".", 1)[-1]: m for m in aftermath.registered()}
    log = by_name["conversation_log"]
    assert (log.STAGE, log.ORDER) == ("beat", 50)
    assert "opening" in log.DOORS


def test_a_member_that_writes_nothing_changes_no_recorded_turn(tmp_path, monkeypatch,
                                                               package):
    """Two recorded turns from each of the eight audit recordings, through the real
    `/api/say`, with the registry empty and then with a member at each stage and every
    door that returns no rows: every beat, every turn-log row and every `/api/state` is
    the same. The members did run — on every turn whose prose reached the page — which is
    what makes the equality mean something: the call sites and their contexts are there,
    and an empty answer appends nothing."""
    empty = _replay_sample(tmp_path / "a", monkeypatch)
    doors = 'DOORS = frozenset({"turn", "carry_on", "opening"})'
    package("s3_people", _recorder("people", doors=doors))
    package("s3_beat", _recorder("beat", doors=doors))
    noop = _replay_sample(tmp_path / "b", monkeypatch)
    assert len(empty) == 16
    assert [t["status"] for t in empty] == [200] * 16
    for a, b in zip(empty, noop):
        assert a == b, (a["where"], _first_difference(a, b))
    people, beat = _member("s3_people").CALLS, _member("s3_beat").CALLS
    assert len(people) == len(beat) >= 12
    assert not any(r.get("kind") == "aftermath-error" for t in noop for r in t["turn_log"])


@pytest.mark.skipif(not replays.available(), reason="the Bobby corpus is not on this disk")
def test_the_bobby_beats_are_unchanged_by_a_member_that_writes_nothing(
        tmp_path, monkeypatch, package):
    """The same holding over the owner's 13 beats through `_finish`, and each stage saw
    each beat once: "people" with no beat index yet, "beat" with the index of the GM beat
    just appended and the lines kept on it."""
    empty = _bobby_beats(tmp_path / "a", monkeypatch)
    package("s3_people", _recorder("people"))
    package("s3_beat", _recorder("beat"))
    noop = _bobby_beats(tmp_path / "b", monkeypatch)
    assert len(empty) == 13 and empty == noop
    people, beat = _member("s3_people").CALLS, _member("s3_beat").CALLS
    assert len(people) == len(beat) == 13
    assert all(ctx.beat_index is None and ctx.stage == "people" for ctx in people)
    for ctx in beat:
        page = ctx.campaign.transcript
        assert ctx.stage == "beat" and ctx.door == "turn"
        assert ctx.beat_index is not None
        assert ctx.turn == ctx.beat_index
    # The context carries the scene's people and the turn's words.
    assert all(ctx.people.get("pc", {}).get("is_pc") for ctx in people)
    assert people[0].player_text == replays.turns()[0]["player"]


def test_the_old_state_keys_come_first_and_unchanged_and_the_new_ones_follow(
        tmp_path, monkeypatch):
    """Every key the page read before S3 is still there, in the same place; the new ones
    are appended after them. A key moved or renamed breaks a page that shipped."""
    from play import campaign as cm
    from play import concurrency
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        cm.begin_with(load_pc("fixtures/pc-kesst.json")).save()
        state = Client().get("/api/state").json()
        cm._LIVE.clear()
    assert list(state) == OLD_TOP + NEW_TOP
    assert list(state["scene"]) == OLD_SCENE + NEW_SCENE


# --- discovery ------------------------------------------------------------------------------

def test_members_are_found_by_filename_sorted_by_stage_then_order_then_name(package):
    """No list to edit: four files and a helper. The helper is never imported."""
    package("s3_zulu", _recorder("beat", order=10))
    package("s3_alpha", _recorder("beat", order=10))
    package("s3_late_people", _recorder("people", order=90))
    package("s3_first_beat", _recorder("beat", order=1))
    package("_s3_helper", "raise RuntimeError('a helper is never imported as a member')\n")
    names = [m.__name__.rsplit(".", 1)[-1] for m in aftermath.registered()]
    assert names == ["s3_late_people", "s3_first_beat", "s3_alpha", "s3_zulu"]


@pytest.mark.parametrize("body, says", [
    ("ORDER = 1\ndef step(ctx): return []\n", "STAGE must be one of"),
    ("STAGE = 'after'\nORDER = 1\ndef step(ctx): return []\n", "STAGE must be one of"),
    ("STAGE = 'beat'\ndef step(ctx): return []\n", "ORDER must be an int"),
    ("STAGE = 'beat'\nORDER = True\ndef step(ctx): return []\n", "ORDER must be an int"),
    ("STAGE = 'beat'\nORDER = 1\nDOORS = {'turn'}\ndef step(ctx): return []\n",
     "DOORS must be a non-empty frozenset"),
    ("STAGE = 'beat'\nORDER = 1\nDOORS = frozenset({'npc'})\ndef step(ctx): return []\n",
     "DOORS must be a non-empty frozenset"),
    ("STAGE = 'beat'\nORDER = 1\n", "needs `def step(ctx)"),
])
def test_a_member_that_breaks_the_contract_is_refused_with_the_fix_named(
        package, body, says):
    """The validator-door rule applied to code: the suite fails on a malformed member,
    naming it and the fix — and the game, which calls `run`, gets a row instead."""
    package("s3_broken", body)
    with pytest.raises(AftermathContractError) as err:
        aftermath.registered()
    assert "play.aftermath.s3_broken" in str(err.value) and says in str(err.value)
    rows = aftermath.run("beat", _ctx())
    assert [r["kind"] for r in rows] == ["aftermath-error"]
    assert rows[0]["member"] == "s3_broken" and says in rows[0]["error"]


def test_the_default_doors_leave_the_opening_out(package):
    """A member that names no DOORS runs on a turn and on Continue, never on the opening:
    the opening is opt-in (Q48 is C's call)."""
    package("s3_default", _recorder("beat"))
    package("s3_opening", _recorder("beat", doors='DOORS = frozenset({"opening"})'))
    for door in ("turn", "carry_on", "opening"):
        aftermath.run("beat", _ctx(door=door))
    assert [c.door for c in _member("s3_default").CALLS] == ["turn", "carry_on"]
    assert [c.door for c in _member("s3_opening").CALLS] == ["opening"]


def _ctx(stage="beat", door="turn", said=None, **over) -> AfterBeat:
    base = dict(stage=stage, door=door, campaign=None, scene=None, world=None, text="",
                said=said if said is not None else [], player_text="", attachments=(),
                reading=None, attribution=None, outcomes=(), people={}, talking_after=(),
                beat_index=None, turn=0)
    base.update(over)
    return AfterBeat(**base)


# --- run ------------------------------------------------------------------------------------

def test_a_broken_step_costs_a_row_not_the_turn_and_the_next_step_runs(package):
    package("s3_a_boom", "STAGE = 'beat'\nORDER = 1\n"
                         "def step(ctx): raise RuntimeError('boom')\n")
    package("s3_b_bad_return", "STAGE = 'beat'\nORDER = 2\ndef step(ctx): return 'rows'\n")
    package("s3_c_good", _recorder("beat", order=3, rows='[{"kind": "good"}]'))
    rows = aftermath.run("beat", _ctx())
    assert rows[0] == {"kind": "aftermath-error", "member": "s3_a_boom",
                       "error": "RuntimeError: boom"}
    assert rows[1]["member"] == "s3_b_bad_return" and "list of turn-log row" in rows[1]["error"]
    assert rows[2] == {"kind": "good"}


def test_only_the_people_stage_may_fill_an_empty_who_and_nothing_else_moves(package):
    """`said` is the page's record of who said which line. "people" may give an untagged
    line a speaker (A's `speaker_real`, with `made`); a step that rewrites anything else
    is an error row, and the record is put back as it was."""
    package("s3_fill", "STAGE = 'people'\nORDER = 1\nDOORS = frozenset({'turn'})\n"
                       "def step(ctx):\n"
                       "    for r in ctx.said:\n"
                       "        if not r['who']:\n"
                       "            r['who'] = r['made'] = 'c1'\n"
                       "    return []\n")
    package("s3_meddle", "STAGE = 'people'\nORDER = 2\n"
                         "def step(ctx):\n"
                         "    ctx.said[0]['line'] = 'something else'\n"
                         "    return []\n")
    said = [{"who": "", "to": "you", "line": "Hello."}, {"who": "c2", "to": "", "line": "Go."}]
    rows = aftermath.run("people", _ctx("people", said=said))
    assert said == [{"who": "c1", "to": "you", "line": "Hello.", "made": "c1"},
                    {"who": "c2", "to": "", "line": "Go."}]
    assert [r["member"] for r in rows] == ["s3_meddle"]
    # The same fill at the "beat" stage is refused: the beat is already on the page.
    package("s3_meddle", "STAGE = 'beat'\nORDER = 2\ndef step(ctx): return []\n")
    package("s3_fill", "STAGE = 'beat'\nORDER = 1\n"
                       "def step(ctx):\n"
                       "    ctx.said[0]['who'] = 'c9'\n"
                       "    return []\n")
    kept = [{"who": "", "to": "you", "line": "Hello."}]
    rows = aftermath.run("beat", _ctx(said=kept))
    assert kept == [{"who": "", "to": "you", "line": "Hello."}]
    assert [r["member"] for r in rows] == ["s3_fill"]


def test_after_opening_runs_both_stages_at_the_opening_door_and_is_wired_to_nothing(
        package, tmp_path):
    """Inert in Phase 1; with no member it returns nothing. Lane C wired it in Phase 2
    (2026-09-28) at the end of `campaign.open_the_story` — the one caller, because
    `after_opening` reads the opening beat and `new_campaign` returns before that beat
    is written."""
    from play import campaign as cm
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        assert aftermath.after_opening(c) == []
        doors = 'DOORS = frozenset({"opening"})'
        package("s3_people", _recorder("people", rows='[{"kind": "p"}]', doors=doors))
        package("s3_beat", _recorder("beat", rows='[{"kind": "b"}]', doors=doors))
        assert aftermath.after_opening(c) == [{"kind": "p"}, {"kind": "b"}]
        (p,), (b,) = _member("s3_people").CALLS, _member("s3_beat").CALLS
        opening = max(i for i, x in enumerate(c.transcript) if x["who"] == "gm")
        assert p.door == b.door == "opening" and p.player_text == ""
        assert p.beat_index is None and b.beat_index == opening
        assert b.text == c.transcript[opening]["text"]
        cm._LIVE.clear()
    callers = [f for f in (ROOT / "play").rglob("*.py")
               if "aftermath" not in f.parts and "after_opening" in f.read_text("utf-8")]
    assert [f.name for f in callers] == ["campaign.py"]


# --- the two call sites in a real turn --------------------------------------------------------

@pytest.fixture
def game(tmp_path, monkeypatch):
    """A campaign with a wizard who carries Burning Hands, a carter standing by, and the
    model stubbed: the plan does nothing, the prose is whatever the test sets."""
    from gm import client as gm_client
    from gm import watcher
    from gm.agent import TurnPlan
    from play import campaign as cm
    from play import concurrency, views
    from rules.bestiary import instantiate
    from rules.sheet import load_pc

    monkeypatch.setattr(watcher, "kick", lambda c: None)
    prose = {"text": "The carter looks up from the wheel. " * 5 + "What do you do?"}
    planned = {}

    def plan(agent, text, *a, **kw):
        planned["attachments"] = getattr(agent, "attachments", "unset")
        planned["text"] = text
        agent.last_said = []
        # An attached spell is in every plan the real chain makes (`inject_cast` puts the
        # chip's cast in), and since 2026-09-29 a plan without it is refused rather than
        # run (play/views.py `_attached_not_planned`), so the stub carries it as well,
        # aimed north-east when the chip and the words left it unaimed, as the model
        # would choose from the aims' enum.
        from rules.intents import IntentError

        raw = judgement.inject_cast([], text, agent.engine.scene,
                                    attached=planned["attachments"])
        for r in raw:
            r.setdefault("params", {}).setdefault("aim", "dir:ne")
        try:
            intents = agent.engine.validate(raw or [{"op": "narrate_only", "because": "t"}])
        except IntentError:
            # An aim the engine will not take for this spell (a cone at `self`): the
            # model's retry would pick another from the enum, so the stub does.
            for r in raw:
                r["params"]["aim"] = "dir:ne"
            intents = agent.engine.validate(raw)
        return TurnPlan(narration="", intents=intents)

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: _Reply(
        json.dumps({"narration": prose["text"], "suggestions": ["I look"]})))
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        pc = load_pc("fixtures/pc-thessaly.json")
        pc.spellbook = ["burning-hands", "magic-missile"]
        c = cm.begin_with(pc)
        carter = c.scene.add(instantiate("guildhand", scene=c.scene, name="the carter"))
        c.save()
        yield {"c": c, "cm": cm, "prose": prose, "planned": planned, "carter": carter.ref}
        cm._LIVE.clear()


def _say(body):
    return Client().post("/api/say", data=json.dumps(body), content_type="application/json")


def test_the_people_stage_runs_before_hailed_by_on_the_live_said(game, package,
                                                                   monkeypatch):
    """The order the register fixes (§2.3): "people", then every `hailed_by`, then "beat".
    A line tagged to nobody here (`was: c9`) is given its speaker by the "people" step, on
    the live list `hailed_by` reads next — so the carter is in conversation on the same
    beat, which a step run after the hails (the plan's site) could never do."""
    from gm import judgement

    carter = game["carter"]
    game["prose"]["text"] = ("The carter wipes his hands. <say who=c9 to=you>'You're "
                             "the one they sent?'</say> He waits for an answer. " * 2)
    order: list = []
    real = judgement.hailed_by

    def spy(scene, text, said=None, **k):
        order.append(("hailed_by", [dict(r) for r in (said or [])]))
        return real(scene, text, said=said, **k)

    monkeypatch.setattr(judgement, "hailed_by", spy)
    package("s3_people", "STAGE = 'people'\nORDER = 1\nWHO = None\nORDER_SEEN = None\n"
                         "def step(ctx):\n"
                         "    ctx.campaign._s3_order.append(('people', None))\n"
                         "    for r in ctx.said:\n"
                         "        if not r['who']:\n"
                         f"            r['who'] = r['made'] = {carter!r}\n"
                         "    return [{'kind': 'made', 'ref': " + repr(carter) + "}]\n")
    package("s3_beat", "STAGE = 'beat'\nORDER = 1\n"
                       "def step(ctx):\n"
                       "    ctx.campaign._s3_order.append(('beat', ctx.beat_index))\n"
                       "    return []\n")
    game["c"]._s3_order = order
    r = _say({"text": "I ask the carter what happened."})
    assert r.status_code == 200, r.content[:300]
    kinds = [k for k, _ in order]
    assert kinds[0] == "people" and kinds[-1] == "beat"
    assert kinds.count("people") == kinds.count("beat") == 1
    first_hail = order[1]
    assert first_hail[0] == "hailed_by"
    assert any(x["who"] == carter and x.get("made") == carter for x in first_hail[1])
    c = game["c"]
    assert carter in {a.ref for a in c.engine().talking_to()}
    assert {"kind": "made", "ref": carter} in c.turn_log
    beat_at = order[-1][1]
    assert c.transcript[beat_at]["who"] == "gm"


def test_a_step_that_raises_is_a_row_and_the_turn_goes_on(game, package):
    package("s3_boom", "STAGE = 'beat'\nORDER = 1\n"
                       "def step(ctx): raise ValueError('the log was full')\n")
    r = _say({"text": "I look around."})
    assert r.status_code == 200
    c = game["c"]
    assert c.transcript[-1]["who"] == "gm"
    assert {"kind": "aftermath-error", "member": "s3_boom",
            "error": "ValueError: the log was full"} in c.turn_log


def test_the_agent_carries_the_brief_facts_and_the_attachments_into_narration(
        game, monkeypatch):
    """What S1's checks read off the agent (`BeatContext.brief_facts`): the facts each
    brief section printed, keyed by section — S2's three moved sections among them."""
    from gm.agent import GMAgent

    seen = {}
    real = GMAgent.narrate_turn

    def spy(self, *a, **k):
        seen["facts"] = dict(getattr(self, "brief_facts", {}) or {})
        seen["attachments"] = getattr(self, "attachments", "unset")
        return real(self, *a, **k)

    monkeypatch.setattr(GMAgent, "narrate_turn", spy)
    # Prepared: since Lane E an attached spell is checked against the character before
    # the model is asked, and an unprepared one is a 422 (item 21.3).
    game["c"].scene.pc().prepared = {"burning-hands": 1}
    r = _say({"text": "", "attachments": [{"kind": "spell", "id": "burning-hands"}]})
    assert r.status_code == 200, r.content[:300]
    assert {"here", "roads_out", "place_facts"} <= set(seen["facts"])
    assert seen["attachments"] == ({"kind": "spell", "id": "burning-hands",
                                    "name": "Burning Hands"},)


def test_the_pull_row_carries_approach_and_yielded_only_when_the_pull_does(
        game, monkeypatch):
    from rules import cards

    monkeypatch.setattr(cards, "thread_to_pull", lambda *a, **k: {
        "title": "the stalled cart", "text": "x", "approach": "comes to you",
        "yielded": False})
    _say({"text": "I look around."})
    row = [r for r in game["c"].turn_log if r.get("kind") == "prose"][-1]
    assert row["pull"] == "the stalled cart"
    assert row["approach"] == "comes to you" and row["yielded"] is False
    monkeypatch.setattr(cards, "thread_to_pull", lambda *a, **k: {"title": "t"})
    _say({"text": "I look around."})
    row = [r for r in game["c"].turn_log if r.get("kind") == "prose"][-1]
    assert "approach" not in row and "yielded" not in row


# --- /api/state -------------------------------------------------------------------------------

def test_every_new_state_key_is_there_at_its_default(game):
    from rules import geography, residency

    c = game["c"]
    s = Client().get("/api/state").json()
    where = geography.where(c.world, c.scene, c.engine().here())
    assert (s["scene"]["where_label"], s["scene"]["where_detail"], s["scene"]["setting"]) \
        == (where.label, where.detail, where.setting)
    assert s["scene"]["where_label"].startswith(c.location.name)
    assert s["scene"]["conversation"] == {"people": [], "recent": [], "seq": 0}
    assert s["scene"]["day_part"] == residency.day_part(c.scene.clock_minutes)
    if s["scene"]["grid"] is not None:
        assert s["scene"]["grid"]["areas"] == []
    # A wizard's first morning is filled from her book since item 21.4's fix (2026-09-28),
    # so the Spells button shows; the warning's shape is Lane E's. The three cantrip slots
    # stand empty since 2026-09-29 (cantrips are prepared, tests/test_cantrips_at_will.py):
    # this fixture's book holds two 1st-level spells and no cantrip to fill them with.
    assert s["spellcasting"] == {"kind": "prepared", "nothing_prepared": False,
                                 "empty_slots": {"0": 3}}
    # Lane C (2026-09-28): a new campaign opens on a start document, so `start` carries
    # it; its shape is still §2.10's, read through the one helper.
    from play import views

    assert s["start"] == views._start_state(c.scene)
    assert set(s["start"]) <= {"id", "kind", "hand_off"}


def test_spellcasting_and_start_read_the_character_and_the_scene():
    from play import views
    from rules.engine import Scene
    from rules.sheet import load_pc

    rogue = load_pc("fixtures/pc-kesst.json")
    assert views._spellcasting_state(rogue) == {"kind": "", "nothing_prepared": False,
                                                "empty_slots": {}}
    wizard = load_pc("fixtures/pc-thessaly.json")
    wizard.prepared = {"burning-hands": 1}
    assert views._spellcasting_state(wizard)["nothing_prepared"] is False
    wizard.prepared = {"burning-hands": 0}
    assert views._spellcasting_state(wizard)["nothing_prepared"] is True
    assert views._spellcasting_state(None)["kind"] == ""
    s = Scene()
    s.start = {"id": "called-to-the-cage", "kind": "trouble", "where": "x", "slots": {},
               "hand_off": {"to": "c1"}, "tells": []}
    assert views._start_state(s) == {"id": "called-to-the-cage", "kind": "trouble",
                                     "hand_off": {"to": "c1"}}


def _entry(n, who, to="", among=(), name="", kind="line"):
    return {"n": n, "t": n, "beat": n, "who": who, "name": name or who, "to": to,
            "kind": kind, "text": f"line {n}", "among": list(among), "src": "tag"}


def test_the_conversation_orders_talking_then_present_then_latest(game):
    """People: talking first, then present, then by their latest entry, newest first, at
    most 30; `recent` the last 80 entries that involve somebody present or talking."""
    from rules.bestiary import instantiate

    c = game["c"]
    carter = game["carter"]
    smith = c.scene.add(instantiate("guildhand", scene=c.scene, name="the smith")).ref
    gone = c.scene.add(instantiate("guildhand", scene=c.scene, name="the pedlar")).ref
    c.engine().join_talk(c.scene.actors[smith], how="test")
    c.scene.actors[gone].at = "somewhere-else"
    c.scene.conversation_log = (
        [_entry(1, carter, to="you"), _entry(2, gone, to="you", name="the pedlar"),
         _entry(3, "you", to=smith, among=[smith])]
        + [_entry(10 + i, carter, to="you") for i in range(90)])
    c.scene.conversation_seq = 99
    convo = Client().get("/api/state").json()["scene"]["conversation"]
    assert [p["ref"] for p in convo["people"]] == [smith, carter, gone]
    smith_row, carter_row, gone_row = convo["people"]
    assert smith_row == {"ref": smith, "name": "the smith", "present": True,
                         "talking": True, "lines": 0, "last": 3}
    assert carter_row["lines"] == 91 and carter_row["last"] == 99
    assert gone_row["present"] is False and gone_row["lines"] == 1
    assert len(convo["recent"]) == 80 and convo["recent"][-1]["n"] == 99
    assert convo["seq"] == 99


def test_the_conversation_endpoint_pages_back_oldest_first(game):
    c = game["c"]
    carter = game["carter"]
    c.scene.conversation_log = [_entry(n, carter if n % 2 else "c77", to="you")
                                for n in range(1, 301)]

    def get(**q):
        r = Client().get("/api/conversation", q)
        assert r.status_code == 200
        return r.json()

    page = get(limit=10)
    assert [e["n"] for e in page["entries"]] == list(range(291, 301)) and page["more"]
    back = get(limit=10, before=291)
    assert [e["n"] for e in back["entries"]] == list(range(281, 291))
    mine = get(**{"with": carter, "limit": 3, "before": 10})
    assert [e["n"] for e in mine["entries"]] == [5, 7, 9] and mine["more"]
    assert get(**{"with": carter, "before": 4, "limit": 200})["more"] is False
    # At most 200, whatever is asked; and nothing asked means a page of 50.
    assert len(get(limit=5000)["entries"]) == 200
    assert len(get()["entries"]) == 50
    assert len(get(limit=-3)["entries"]) == 1
    assert get(**{"with": "c404"}) == {"entries": [], "more": False}


# --- /api/say attachments ---------------------------------------------------------------------

@pytest.mark.parametrize("body, says", [
    ({"text": "I cast", "attachments": {"kind": "spell", "id": "burning-hands"}},
     "Attachments must be a list."),
    ({"text": "I cast", "attachments": [{"kind": "spell", "id": "burning-hands"},
                                        {"kind": "spell", "id": "magic-missile"}]},
     "Only one spell can be attached to a turn."),
    ({"text": "I use it", "attachments": [{"kind": "item", "id": "rope"}]},
     "Only a spell or a place can be attached to a turn."),
    ({"text": "", "attachments": [{"kind": "spell", "id": "not-a-spell"}]},
     "There is no spell called not-a-spell."),
    ({"text": "", "attachments": [{"kind": "spell", "id": "fireball"}]},
     "Thessaly Corr does not know Fireball."),
    ({"text": "", "attachments": [{"kind": "spell", "id": "burning-hands",
                                   "aim": "at the cart"}]},
     "is not an aim a spell can take"),
    ({"carry_on": True, "attachments": [{"kind": "spell", "id": "burning-hands"}]},
     "A spell cannot be attached to Continue"),
    ({"text": "/gm what does it do", "attachments": [{"kind": "spell", "id": "burning-hands"}]},
     "A spell cannot be attached to /gm or /cheat."),
    ({"text": "/cheat I know fireball", "attachments": [{"kind": "spell",
                                                         "id": "burning-hands"}]},
     "A spell cannot be attached to /gm or /cheat."),
])
def test_each_attachment_rule_is_a_400_with_a_sentence(game, body, says):
    """The §2.10 rules, each refused at the door before anything reads the turn: no beat,
    no plan, no clock."""
    c = game["c"]
    was, clock = len(c.transcript), c.scene.clock_minutes
    r = _say(body)
    assert r.status_code == 400
    assert says in r.json()["error"]
    assert len(c.transcript) == was and c.scene.clock_minutes == clock
    assert game["planned"] == {}


@pytest.mark.parametrize("aim", ["ref:c1", "self", "dir:ne", "point:3,4", "point:3,4,1",
                                 "object:the cart"])
def test_every_aim_the_register_names_is_accepted(game, aim):
    """Every form of the grammar passes the door (never the 400 a malformed aim gets).
    Since Lane E the engine then judges it against the scene: an aim at something that is
    not here, or out of reach, is the player's to fix and answers the §2.6 422 — no beat,
    no plan — and any other is stored on the beat as sent."""
    # Prepared: since Lane E an attached spell is checked against the character before
    # the model is asked, and an unprepared one is a 422 (item 21.3).
    game["c"].scene.pc().prepared = {"burning-hands": 1}
    c = game["c"]
    was = len(c.transcript)
    r = _say({"text": "I cast it.", "attachments": [{"kind": "spell", "id": "burning-hands",
                                                     "aim": aim}]})
    assert r.status_code in (200, 422), r.content[:300]
    if r.status_code == 422:
        assert r.json()["refusal"]["code"] in ("no_such_object", "out_of_range",
                                               "no_line_of_effect")
        assert len(c.transcript) == was and game["planned"] == {}
        return
    player = [b for b in c.transcript if b["who"] == "player"][-1]
    assert player["attachments"][0]["aim"] == aim


def test_a_bare_chip_is_a_turn_stored_and_its_cast_planned(game, monkeypatch):
    """Empty text with one spell: the shown line is "I cast Burning Hands.", the chip is on
    the player's beat and the turn log's `turn` row, the planner holds it, and the plan
    carries the chip's cast (the stub puts it in as `inject_cast` does; until 2026-09-29
    this stub declared nothing and the turn ran with no cast, the very shape that is now
    refused rather than run — `_attached_not_planned`).
    `player_input.check` never sees the line we wrote."""
    from play import player_input
    # Prepared: since Lane E an attached spell is checked against the character before
    # the model is asked, and an unprepared one is a 422 (item 21.3).
    game["c"].scene.pc().prepared = {"burning-hands": 1}

    checked = []
    real = player_input.check
    monkeypatch.setattr(player_input, "check", lambda t: checked.append(t) or real(t))
    r = _say({"text": "", "attachments": [{"kind": "spell", "id": "burning-hands"}]})
    assert r.status_code == 200, r.content[:300]
    c = game["c"]
    chip = [{"kind": "spell", "id": "burning-hands", "name": "Burning Hands"}]
    player = [b for b in c.transcript if b["who"] == "player"][-1]
    assert player == {"who": "player", "text": "I cast Burning Hands.", "attachments": chip}
    assert game["planned"] == {"attachments": tuple(chip), "text": "I cast Burning Hands."}
    turn = [row for row in c.turn_log if row.get("kind") == "turn"][-1]
    assert turn["attachments"] == chip
    assert "cast" in [o["op"] for o in turn["outcomes"]]
    assert checked == []
    assert [b for b in r.json()["transcript"] if b["who"] == "player"][-1] == player
    # Typed words beside the chip are checked as ever, and are the line shown.
    _say({"text": "I aim at the cart.",
          "attachments": [{"kind": "spell", "id": "burning-hands"}]})
    assert checked == ["I aim at the cart."]
    # And a turn without one carries no key at all.
    _say({"text": "I look around."})
    assert "attachments" not in [b for b in c.transcript if b["who"] == "player"][-1]
    assert "attachments" not in [row for row in c.turn_log if row.get("kind") == "turn"][-1]


def test_the_aim_pattern_is_the_registers():
    """A copy for the door, held to §2.7's text until Lane E's `areas.AIM_PATTERN` exists
    to be compared with instead."""
    from play import views

    want = (r"^(ref:[A-Za-z0-9_-]+|self|dir:(n|ne|e|se|s|sw|w|nw|up|down)"
            r"|point:\d+,\d+(,\d+)?|object:[^\n]{1,60})$")
    assert views._AIM.pattern == want
    try:
        from rules import areas
    except ImportError:
        return
    assert views._AIM.pattern == areas.AIM_PATTERN


# --- the refusal shape ------------------------------------------------------------------------

def test_a_refusal_renders_into_one_422_shape():
    """§2.6, Q4 (a): a refusal costs no turn and answers 422 with the player's sentence
    beside the code and the fix, so the client can keep the input and offer the fix."""
    from play import views

    r = views._refusal({"text": "Burning Hands is not prepared.", "code": "unprepared",
                        "fix": {"kind": "prepare", "spell": "burning-hands"}})
    assert r.status_code == 422
    assert json.loads(r.content) == {
        "error": "Burning Hands is not prepared.",
        "refusal": {"text": "Burning Hands is not prepared.", "code": "unprepared",
                    "fix": {"kind": "prepare", "spell": "burning-hands"}}}
    bare = json.loads(views._refusal({"text": "No."}).content)
    assert bare["refusal"] == {"text": "No.", "code": "", "fix": None}


def test_the_spec_already_ships_the_package():
    """S1's spec entry collects `play.aftermath` when its `__init__.py` is on disk; S3's
    lands it, so nothing in the spec needed to change."""
    spec = (ROOT / "pathfindergm.spec").read_text(encoding="utf-8")
    assert '"play.aftermath"' in spec
    assert (ROOT / "play" / "aftermath" / "__init__.py").is_file()
