"""The player's search: the engine's Perception against what is hidden, taking 10 or 20.

Playtest 2026-11-16 (docs: C:/Users/natha/pgm-work/playtest-2026-11-16.md), the hunt for the
hidden dungeon. The reading's `search` act owed no op, so the plan rolled what it liked: of
six searches, Survival "finding tracks" for a way into the crypts (#24) and for the
masonry of a sewer (#49), Perception at its own "average (DC 10)" (#29, #35), a forage for
a ship's hold (#15); a +2 for torchlight from a torch the engine had just refused (#28);
"makes the perception check by 10" and nothing more (#30); "taking twenty" rolled a live
d20 (#49, #52). The way down (`dungeons.searched`, DC 20) ran on none of them. And the
culvert, recorded at the main channel, was never told on arrival (#48).
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, interpret
from rules import dungeons
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

VYRAKON = "5bbd0c40345f"
WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


@pytest.fixture(autouse=True)
def _no_readings(monkeypatch):
    monkeypatch.setattr(interpret, "_READINGS", {})


@pytest.fixture
def always(monkeypatch):
    monkeypatch.setattr(dungeons, "chance", lambda *a, **k: 100)


def _room(seed=3):
    s = Scene(location_id=VYRAKON)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s, Engine(s, Dice(seed=seed), world=WORLD)


def _run(engine, op, params, visibility="hidden"):
    intents = engine.validate([{"op": op, "actor": "pc", "because": "t", "params": params,
                                "visibility": visibility}], origin="author:test")
    return engine.run(intents).outcomes[-1]


def _at_the_culvert(engine, s):
    """Into the sewers, to the way down's spot, with the reactive look already made and
    missed — the save's own state at beat 243 (`found: false, noticed: true`)."""
    _run(engine, "venture", {"kind": "sewers"})
    head = next(p for p in s.founded if p.get("deeper"))
    head["deeper"]["noticed"] = True
    return head, head["deeper"]


def _perception(s) -> int:
    return sum(m.value for m in s.pc().skill_modifiers("perception"))


def test_taking_20_finds_the_way_down_at_its_dc_and_costs_two_minutes(always):
    """#49/#52: "I take 20 on Perception" rolled a live 10 against the plan's DC 8. By the
    book (CRB p.86) a take 20 is an automatic 20 and twenty times the time: the culvert's
    DC 20 is met by any searcher with Perception +0 or better, and the clock moves 2
    minutes."""
    s, engine = _room()
    head, deeper = _at_the_culvert(engine, s)
    _run(engine, "travel", {"place": deeper["spot"]})
    assert _perception(s) >= 0 and not deeper["found"]
    before = s.clock_minutes
    out = _run(engine, "check", {"skill": "perception", "search": True, "take": 20},
               visibility="player")
    assert out.rolls[0].natural == 20 and out.verdict == "success"
    assert deeper["found"] and "bricked-up culvert" in out.tell, out.tell
    assert s.clock_minutes - before == 2


def test_take_20_is_refused_in_a_fight():
    """CRB p.86: "Distractions or threats (such as combat) make it impossible" to take 10
    or 20. Refused with the rule named, nothing rolled."""
    s, engine = _room()
    s.initiative, s.turn = [("pc", 15)], 0
    out = _run(engine, "check", {"skill": "perception", "search": True, "take": 20})
    assert out.status == "refused" and "fight" in out.tell and not out.rolls


def test_a_search_says_what_it_found_or_that_it_found_nothing():
    """#30: "makes the perception check by 10", and nothing followed — no passage, no
    "there is none". A search now always ends in what it found, or "finds nothing", and
    carries no DC of the plan's (#29: "average (DC 10)") nor its circumstance (#28: +2 for
    torchlight from no torch)."""
    s, engine = _room()
    out = engine.run(engine.validate([{
        "op": "check", "actor": "pc", "because": "t", "visibility": "hidden",
        "params": {"skill": "perception", "search": True,
                   "circumstance": {"value": "favorable", "why": "the torchlight"}}}],
        origin="author:test")).outcomes[-1]
    assert out.tell.endswith("finds nothing."), out.tell
    assert out.dc is None and "torchlight" not in out.tell and out.verdict == "failure"


def test_a_roll_below_the_way_downs_dc_finds_nothing_however_the_plan_set_it(always):
    """#29: the plan's DC 10 let an 18 "succeed" at a secret door the CRB puts at 20. The
    total is set against the culvert's own 20: a 10 taken misses it."""
    s, engine = _room()
    head, deeper = _at_the_culvert(engine, s)
    _run(engine, "travel", {"place": deeper["spot"]})
    if _perception(s) >= 10:
        pytest.skip("this sheet takes 10 past DC 20")
    out = _run(engine, "check", {"skill": "perception", "search": True, "take": 10})
    assert not deeper["found"] and out.tell.endswith("finds nothing."), out.tell


def test_arriving_where_the_way_down_hides_tells_its_sign(always):
    """#48: the gardens' sewers had no sump, so the culvert went to the main channel,
    recorded `noticed: true`; arriving there told only "You are at the main channel now".
    While it is unfound the spot's sign is told on every arrival, so the player knows a
    search here is worth it; the way itself stays at its DC."""
    s, engine = _room()
    head, deeper = _at_the_culvert(engine, s)
    deeper["feature"].pop("sign", None)     # recorded before the rows had signs
    went = _run(engine, "travel", {"place": deeper["spot"]})
    assert "newer brick" in went.tell, went.tell
    assert not deeper["found"]


def _frame(*actions):
    return {"question": False, "actions": [dict(a) for a in actions], "claims": []}


def _scene():
    s = Scene(location_id=VYRAKON)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


def test_a_search_here_is_built_whole_and_the_plans_survival_and_forage_go():
    """#24/#49: Survival for a way down; #15: a forage for a ship's hold. A search read
    `where: here` is the engine's Perception search, and the plan's Survival, track and
    forage beside it are dropped. Beat 256's two search acts (one "taking twenty") make
    one search, taking 20."""
    s = _scene()
    frame = _frame({"act": "search", "object": "every brick", "place": "the walls",
                    "where": "here"},
                   {"act": "search", "object": "twenty", "take": "twenty"})
    rows = acts_to_ops.table(frame, s, sentence="…")
    plan = [{"op": "check", "actor": "pc", "params": {"skill": "survival",
                                                      "dc": {"band": "average"}}},
            {"op": "forage", "actor": "pc", "params": {}}]
    raw = acts_to_ops.apply(plan, rows, frame, s)
    checks = [r for r in raw if r.get("op") == "check"]
    assert checks == [{"op": "check", "actor": "pc", "because": "the player searches",
                       "params": {"skill": "perception", "search": True, "take": 20}}]
    assert not any(r.get("op") == "forage" for r in raw)


def test_a_search_for_somewhere_else_builds_nothing():
    """"I find somewhere dry to shelter" is a search `where: elsewhere`: the travel and
    found doors answer it, as before; no Perception is rolled at the ground underfoot."""
    rows = acts_to_ops.table(_frame({"act": "search", "object": "somewhere dry"}),
                             _scene(), sentence="…")
    assert not any(r.intents for r in rows)


def test_the_reader_keeps_where_and_take_only_inside_their_enums():
    """The closed answers survive grounding only as the enums' words."""
    said = "I go over the walls, taking twenty."
    got, _ = interpret.ground({"question": False, "claims": [], "actions": [
        {"act": "search", "span": "go over the walls, taking twenty", "place": "the walls",
         "where": "here", "take": "twenty"},
        {"act": "search", "span": "go over the walls", "where": "under", "take": "lots"}]},
        said)
    a, b = got["actions"]
    assert a.get("where") == "here" and a.get("take") == "twenty"
    assert "where" not in b and "take" not in b


def test_the_plans_own_search_under_an_alias_is_replaced_too():
    """Live 2026-11-16 (beat 256 replayed): beside the table's search, taking 20, the
    plan's own Perception check "searching the bricks for a mechanism" at "average" with
    a +2 for the brickwork survived and rolled a 5, "misses the perception check by 3",
    beside the search that found the culvert. A plan's skill is read as validation reads
    it: "search" and "investigation" are Perception."""
    s = _scene()
    frame = _frame({"act": "search", "place": "the walls", "where": "here",
                    "take": "twenty"})
    rows = acts_to_ops.table(frame, s, sentence="…")
    for alias in ("search", "Investigation", "Perception"):
        plan = [{"op": "check", "actor": "pc", "params": {"skill": alias,
                                                          "dc": {"band": "average"}}}]
        raw = acts_to_ops.apply(plan, rows, frame, s)
        assert [r["params"] for r in raw if r.get("op") == "check"] == [
            {"skill": "perception", "search": True, "take": 20}], alias
