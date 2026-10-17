"""A placeholder nobody introduced never costs the turn.

Measured live 2026-10-16 on master (gemma-4-12B, a Pangrella scratch campaign standing in a
tavern): the plan wrote `new1` as a target with no `introduce` on 5 of 5 attempts across
two turns ("I pay for a room for the night and go to bed", "I ask the barkeep for a room
for the night…"). Validation refused every attempt, the turn degraded to narration only,
and the prose put the character in bed upstairs while the engine's place and clock had not
moved. The same lane's scratch saves hold two more shapes, each refused seven times:
`travel target=new1` from the outskirts with nobody there ("I head into the city and go to
the inn"), and `say to=new1` beside the one person in the tavern, c8 "the one behind the
bar" ("I say goodbye to the barkeep, go back up to my room and sleep until dawn").

`bind_placeholders` (2026-09-27) had not regressed — it binds one dangling label only when
the player's words can only mean one person, and "the barkeep" named nobody by name, so it
correctly bound nothing. Nothing after it took the placeholder out, and the schema offers
`new1` in every ref enum out of a fight. `judgement.settle_placeholders` is the step after:
bind to the one person meant, else empty a slot the op never reads, else drop the op.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from gm import judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import OPS
from rules.sheet import load_pc


def _scene(*names):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    for name in names:
        s.add(instantiate("thug", scene=s, name=name))
    return s


def _talk(target, says="goodbye"):
    return {"actions": [{"act": "talk", "target": target, "says": says,
                         "span": f"say {says} to {target}"},
                        {"act": "rest", "time": "until dawn", "span": "sleep until dawn"}]}


def test_the_goodbye_goes_to_the_one_behind_the_bar():
    """The er-data save, turn_log row 125: `say to=new1` with c8 the only person in the
    tavern. "The barkeep" shares no word with "the one behind the bar", so the name finder
    answers nothing — but a line is said to somebody, and the one person the player is
    dealing with is the one here."""
    scene = _scene("the one behind the bar")
    raw = [{"op": "say", "actor": "pc", "params": {"words": "Goodbye.", "to": "new1"}},
           {"op": "rest", "actor": "pc", "params": {"kind": "night"}}]
    notes: list[str] = []
    out = judgement.settle_placeholders(
        raw, "I say goodbye to the barkeep, go back up to my room and sleep until dawn.",
        scene, _talk("the barkeep"), notes=notes)
    assert out[0]["params"]["to"] == "c1"
    assert [r["op"] for r in out] == ["say", "rest"]
    assert notes and "c1" in notes[0]
    Engine(scene, Dice(seed=1)).validate(out)


def test_two_people_and_no_name_the_line_is_said_to_the_room():
    """With a second patron in the room and nothing naming either, nobody is chosen for
    the player: the say keeps its words and loses only the placeholder, and the rest
    stands — where before the whole turn was five refusals and a narrated nothing."""
    scene = _scene("the one behind the bar", "a man working wire")
    raw = [{"op": "say", "actor": "pc", "target": "new1",
            "params": {"words": "A room for the night.", "to": "new1"}},
           {"op": "rest", "actor": "pc", "target": "new1", "params": {"kind": "night"}}]
    out = judgement.settle_placeholders(
        raw, "I ask the barkeep for a room for the night and go to sleep.", scene,
        _talk("the barkeep", "a room for the night"))
    assert [r["op"] for r in out] == ["say", "rest"]
    assert "to" not in out[0]["params"] and "target" not in out[0]
    assert "target" not in out[1]
    Engine(scene, Dice(seed=1)).validate(out)


def test_a_walk_aimed_at_nobody_still_walks():
    """The er-data save, row 96: `travel target=new1` at the outskirts, nobody there, seven
    refusals. A travel's target is never read; it goes, and the walk stands."""
    scene = _scene()
    raw = [{"op": "travel", "target": "new1", "params": {"place": "the market"}}]
    out = judgement.settle_placeholders(raw, "I head into the city and go to the inn.",
                                        scene, {"actions": [{"act": "go",
                                                             "place": "the inn"}]})
    assert out == [{"op": "travel", "params": {"place": "the market"}}]


def test_the_reading_names_who_a_blow_is_at():
    """A blow is bound only by the finder, never by the dealing-with guess: "Hesk" in the
    reading's target slot is c2 even with Borin standing nearer."""
    scene = _scene("Borin Lyraxys", "Hesk")
    raw = [{"op": "attack", "actor": "pc", "target": "enemy1"}]
    out = judgement.settle_placeholders(
        raw, "I go for the wiry one.", scene,
        {"actions": [{"act": "attack", "target": "Hesk", "span": "go for Hesk"}]})
    assert out[0]["target"] == "c2"


def test_a_blow_at_nobody_goes_and_the_rest_of_the_turn_stands():
    scene = _scene("Borin Lyraxys", "Hesk")
    raw = [{"op": "attack", "actor": "pc", "target": "new1"},
           {"op": "say", "actor": "pc", "params": {"words": "Come on, then."}}]
    notes: list[str] = []
    out = judgement.settle_placeholders(raw, "I punch him.", scene, None, notes=notes)
    assert [r["op"] for r in out] == ["say"]
    assert "attack dropped" in notes[0]


def test_nothing_left_is_a_quiet_turn_not_an_empty_one():
    scene = _scene("Borin Lyraxys", "Hesk")
    out = judgement.settle_placeholders(
        [{"op": "give", "actor": "pc", "target": "new1", "params": {"item": "coin"}}],
        "I pay him.", scene, None)
    assert [r["op"] for r in out] == ["narrate_only"]


def test_an_act_by_a_placeholder_is_nobody_acting():
    scene = _scene("Borin Lyraxys", "Hesk")
    raw = [{"op": "say", "actor": "new1", "params": {"words": "Rooms are five silver."}},
           {"op": "rest", "actor": "pc", "params": {"kind": "night"}}]
    out = judgement.settle_placeholders(raw, "I go to bed.", scene, None)
    assert [r["op"] for r in out] == ["rest"]


def test_an_introduced_placeholder_and_a_real_ref_are_left_alone():
    scene = _scene("Borin Lyraxys")
    raw = [{"op": "introduce", "params": {"who": "a ferryman"}},
           {"op": "say", "actor": "pc", "params": {"words": "Hello.", "to": "new1"}},
           {"op": "attack", "actor": "pc", "target": "c1"}]
    assert judgement.settle_placeholders(raw, "I hail the ferryman.", scene, None) == raw


def test_a_spawn_is_never_re_aimed_at_somebody_already_here():
    """A spawn's bodies are `bind_placeholders`' to number. A placeholder beyond them is
    settled, but never by the one-person guess — that man is not the newcomer."""
    scene = _scene("Borin Lyraxys")
    raw = [{"op": "spawn", "params": {"template": "thug", "count": 1}},
           {"op": "attack", "actor": "pc", "target": "new2"}]
    out = judgement.settle_placeholders(raw, "I punch the newcomer.", scene, None)
    assert [r["op"] for r in out] == ["spawn"]


def test_the_ops_about_somebody_are_the_ones_the_engine_aims():
    """Every `_op_<name>` that reads `intent.target` is in `_ABOUT_SOMEBODY`, so an op that
    starts reading its target can never have that target silently emptied here. Walked as
    an AST, as test_three_laws does (tests/test_suite_isolation.py caps source pins)."""
    tree = ast.parse((Path(__file__).resolve().parents[1] / "rules" / "engine.py")
                     .read_text(encoding="utf-8"))
    engine = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Engine")
    reads = set()
    for fn in engine.body:
        m = re.fullmatch(r"_op_(\w+)", getattr(fn, "name", "") or "")
        if not (isinstance(fn, ast.FunctionDef) and m and m.group(1) in OPS):
            continue
        if any(isinstance(n, ast.Attribute) and n.attr == "target"
               and isinstance(n.value, ast.Name) and n.value.id == "intent"
               for n in ast.walk(fn)):
            reads.add(m.group(1))
    assert reads, "no handler read a target: the pin is reading the wrong thing"
    assert reads <= judgement._ABOUT_SOMEBODY, sorted(reads - judgement._ABOUT_SOMEBODY)


@pytest.mark.parametrize("op", ["travel", "rest", "say"])
def test_the_measured_ops_are_ones_whose_target_is_never_read(op):
    assert op not in judgement._ABOUT_SOMEBODY


def test_the_players_own_blow_is_held_for_one_retry_only():
    scene = _scene("Borin Lyraxys", "Hesk")
    raw = [{"op": "attack", "actor": "pc", "target": "new1"}]
    assert judgement.settle_placeholders(raw, "I punch him.", scene, None,
                                         hold_players=True) == raw
    # Somebody else's act at nobody is never held: no retry can make it the player's.
    npc = [{"op": "attack", "actor": "c1", "target": "new1"}]
    out = judgement.settle_placeholders(npc, "I watch.", scene, None, hold_players=True)
    assert [r["op"] for r in out] == ["narrate_only"]


# --- through the real planner --------------------------------------------------------------

class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"
        self.prompt_tokens = self.reply_tokens = 0
        self.done_reason = "stop"

    def json(self):
        import json

        return json.loads(self.text)


def _tavern():
    from _a_truth import MARKET, scene_at

    return scene_at(MARKET, [("the one behind the bar", "guildhand"),
                             ("a man working wire", "guildhand")])


def _stub(monkeypatch, plan: list):
    import json

    from gm import agent as agent_mod

    asked: list = []

    def fake_chat(messages, model, host, **kw):
        asked.append(messages)
        return _Reply(json.dumps({"narration": "", "intents": plan}))

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    return asked


ROOM = "I pay for a room for the night and go to bed."
# The reading's shape for the Pangrella lane's line: a purchase and a sleep, nobody named.
ROOM_READ = {"question": False, "actions": [
    {"act": "buy", "object": "a room for the night", "span": "pay for a room for the night"},
    {"act": "rest", "span": "go to bed"}]}


def test_the_room_and_the_bed_stand_on_the_first_attempt(monkeypatch):
    """The measured turn's shape, the model writing it identically on every attempt as it
    did live (7 refusals on the er-data save, 5 of 5 on the Pangrella lane's): `say
    to=new1` and `rest target=new1`, nobody introduced, two people in the tavern. Before:
    every attempt refused and "You try — … — but the moment does not answer". Now one
    attempt, and the sleep the player asked for resolves."""
    from gm import interpret

    gm, _refs = _tavern()
    interpret.remember(ROOM, ROOM_READ)
    asked = _stub(monkeypatch, [
        {"op": "say", "actor": "pc", "target": "new1",
         "params": {"words": "Goodbye, then.", "to": "new1"}},
        {"op": "rest", "actor": "pc", "target": "new1", "params": {"kind": "night"}}])
    plan = gm.plan_turn(ROOM, history=[])
    shown = [(i.op, i.target, i.params) for i in plan.intents]
    assert len(asked) == 1, plan.rejections
    assert not any("degraded" in r for r in plan.repairs), plan.repairs
    assert "rest" in [i.op for i in plan.intents], shown
    assert all(i.target != "new1" and i.params.get("to") != "new1"
               for i in plan.intents), shown


def test_an_ask_at_nobody_costs_one_retry_then_the_rest_stands(monkeypatch):
    """The player's own act on somebody (a Diplomacy check at `new1`) gets one retry with
    the people here named; written again, it goes and the sleep stands."""
    from gm import interpret

    gm, _refs = _tavern()
    interpret.remember(ROOM, ROOM_READ)
    asked = _stub(monkeypatch, [
        {"op": "check", "actor": "pc", "target": "new1",
         "params": {"skill": "diplomacy"}},
        {"op": "rest", "actor": "pc", "params": {"kind": "night"}}])
    plan = gm.plan_turn(ROOM, history=[])
    shown = [(i.op, i.target, i.params) for i in plan.intents]
    assert len(asked) == 2, (shown, plan.rejections)
    assert "'new1' is the placeholder" in plan.rejections[0]
    assert "check" not in [i.op for i in plan.intents], shown
    assert "rest" in [i.op for i in plan.intents], shown
    assert not any("degraded" in r for r in plan.repairs), plan.repairs


ASK = "I ask the barkeep for a room for the night and go to sleep."


def test_the_recorded_ask_for_a_room_stands(monkeypatch):
    """Reproduced live on master d4f84e20 (gemma-4-12B, the hv-data scratch campaign in
    the inn off Khalmorin's market, c8 "the one behind the bar" and c9 present): five
    plans of exactly this — `travel target=new1`, `rest target=new1`, nobody introduced —
    five refusals, a 600 s wait on an absent fallback model, and narration only. The plan
    is replayed here as the model wrote it, on every attempt."""
    from gm import interpret

    gm, _refs = _tavern()
    interpret.remember(ASK, {"question": False, "actions": [
        {"act": "request", "target": "the barkeep", "object": "a room for the night",
         "span": "ask the barkeep for a room for the night"},
        {"act": "rest", "span": "go to sleep"}]})
    asked = _stub(monkeypatch, [{"op": "travel", "actor": "pc", "target": "new1"},
                                {"op": "rest", "actor": "pc", "target": "new1"}])
    plan = gm.plan_turn(ASK, history=[])
    shown = [(i.op, i.target, i.params) for i in plan.intents]
    assert len(asked) == 1, plan.rejections
    assert not any("degraded" in r for r in plan.repairs), plan.repairs
    assert "rest" in [i.op for i in plan.intents], shown
