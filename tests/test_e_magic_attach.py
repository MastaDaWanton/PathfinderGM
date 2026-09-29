"""Lane E: a spell attached to the player's words, and the Spells tab's aim (item 21).

Measured 2026-09-28 (Bobby, turn 12): "I cast burning hands into the tree tops" with
nothing prepared. The refusal was correct and the player never saw it: the plan loop was
refused seven times with the same "did not prepare Burning Hands today", handed to a second
model, and degraded to narrate_only. A fact about the character is not a plan to retry;
it is answered at once, in one sentence, with the fix a button can offer (§2.6, Q4 (a):
HTTP 422, no beat, no clock, no NPC turn). And the Spells tab could aim only at a person —
a cone sent with no target resolved as `targets: []` (item 22).
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import grid as gridmod
from rules.bestiary import instantiate
from rules.sheet import from_dict, load_pc, to_dict
from tests._places import stand_on


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"
        self.prompt_tokens = self.reply_tokens = 0
        self.done_reason = "stop"

    def json(self):
        return json.loads(self.text)


def ysolde(prepared):
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d["prepared"] = dict(prepared)
    return from_dict(d, ref="pc")


@pytest.fixture
def table(tmp_path, monkeypatch):
    """A campaign in the forest with the caster, a stranger fifteen feet away, and the
    model stubbed: every plan and prose call is counted."""
    from gm import client as gm_client
    from gm import watcher
    from gm.agent import TurnPlan
    from play import campaign as cm
    from play import concurrency, views

    monkeypatch.setattr(watcher, "kick", lambda c: None)
    calls = {"plan": 0, "chat": 0, "attachments": None, "refusal": None}

    def plan(agent, text, *a, **kw):
        calls["plan"] += 1
        calls["attachments"] = getattr(agent, "attachments", None)
        agent.last_said = []
        made = TurnPlan(narration="", intents=agent.engine.validate(
            [{"op": "narrate_only", "because": "t"}]))
        if calls["refusal"]:
            made.refusal = calls["refusal"]
        return made

    def chat(*a, **k):
        calls["chat"] += 1
        return _Reply(json.dumps({"narration": "The trees stand over you. " * 6,
                                  "suggestions": ["I look"]}))

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    monkeypatch.setattr(gm_client, "chat", chat)
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        concurrency.reset_for_tests()

        def begin(prepared):
            c = cm.begin_with(ysolde(prepared))
            man = c.scene.add(instantiate("guildhand", scene=c.scene,
                                          name="the man in a stained jerkin"))
            for ref in [r for r in c.scene.people if r not in ("pc", man.ref)]:
                c.scene.people.pop(ref)
            stand_on(c.scene, "forest")
            c.scene.grid = gridmod.Grid(20, 20)
            c.scene.positions.clear()
            c.scene.positions["pc"], c.scene.positions[man.ref] = (4, 7), (1, 8)
            c.save()
            return c, man.ref

        yield {"begin": begin, "calls": calls}
        cm._LIVE.clear()


def _say(body):
    return Client().post("/api/say", data=json.dumps(body), content_type="application/json")


def _cast(body):
    return Client().post("/api/cast", data=json.dumps(body), content_type="application/json")


def test_e_attached_unprepared_spell_answers_in_one_sentence(table):
    """Seven plan attempts, a hand-off and a narrate_only for one refusal (Bobby, turn 12).
    Now: the attached cast is validated before any model call — a 422 with the player's
    sentence, `code: unprepared` and a Prepare fix; the model is called zero times; no
    beat, no clock."""
    c, _man = table["begin"]({})
    was, clock = len(c.transcript), c.scene.clock_minutes
    r = _say({"text": "I cast burning hands into the tree tops",
              "attachments": [{"kind": "spell", "id": "burning-hands"}]})
    assert r.status_code == 422, r.content[:300]
    body = r.json()
    assert body["refusal"]["code"] == "unprepared"
    assert body["refusal"]["fix"] == {"kind": "prepare", "spell": "burning-hands"}
    assert "not prepared" in body["error"]
    assert table["calls"]["plan"] == 0 and table["calls"]["chat"] == 0
    assert len(c.transcript) == was and c.scene.clock_minutes == clock


def test_e_the_chip_carries_an_aim_grounded_from_the_words(table):
    """"Into the tree tops" names the canopy with no model asked (`areas.aim_from_words`),
    and the planner is handed the chip with that aim."""
    c, _man = table["begin"]({"burning-hands": 1})
    r = _say({"text": "I cast burning hands into the tree tops",
              "attachments": [{"kind": "spell", "id": "burning-hands"}]})
    assert r.status_code == 200, r.content[:300]
    chip = table["calls"]["attachments"][0]
    assert chip["id"] == "burning-hands" and chip["aim"] == "object:canopy"
    player = [b for b in c.transcript if b["who"] == "player"][-1]
    assert "aim" not in player["attachments"][0], "the beat keeps what the player sent"


def test_e_a_plan_that_stops_on_a_player_refusal_is_the_same_422(table):
    """Lane A's plan loop sets `TurnPlan.refusal` when it stops on a player-fixable
    refusal; `say` answers it in the one shape, and the line comes off the transcript."""
    c, _man = table["begin"]({})
    table["calls"]["refusal"] = {"text": "Magic Missile is not prepared.",
                                 "code": "unprepared",
                                 "fix": {"kind": "prepare", "spell": "magic-missile"}}
    was = len(c.transcript)
    r = _say({"text": "I cast magic missile at the man"})
    assert r.status_code == 422
    assert r.json()["refusal"]["code"] == "unprepared"
    assert len(c.transcript) == was


def test_e_the_spells_tab_takes_an_aim_and_is_not_the_players_words(table, monkeypatch):
    """The Spells tab's cast carries an `aim`, not only a person; the area is laid and
    its cells go to the map (`scene.grid.areas`). And its label is a button's, so the
    after-the-beat steps get `player_text=""` (fix-interfaces §3.4)."""
    from play import views

    c, man = table["begin"]({"burning-hands": 2})
    seen = []
    real = views._after_the_beat

    def spy(c_, agent, stage, door, **fields):
        seen.append(fields.get("player_text"))
        return real(c_, agent, stage, door, **fields)

    monkeypatch.setattr(views, "_after_the_beat", spy)
    r = _cast({"spell": "burning-hands", "aim": "dir:up", "label": "I cast Burning Hands"})
    assert r.status_code == 200, r.content[:300]
    assert seen and set(seen) == {""}
    areas_drawn = r.json()["scene"]["grid"]["areas"]
    assert areas_drawn and areas_drawn[0]["spell"] == "burning-hands"
    assert all(cell[2] >= 2 for cell in areas_drawn[0]["cells"])


def test_e_the_spells_tab_refuses_in_the_one_shape(table):
    c, man = table["begin"]({})
    r = _cast({"spell": "burning-hands", "aim": f"ref:{man}"})
    assert r.status_code == 422
    assert r.json()["refusal"]["fix"] == {"kind": "prepare", "spell": "burning-hands"}
    r = _cast({"spell": "burning-hands", "aim": "westward"})
    assert r.status_code == 400 and "is not an aim" in r.json()["error"]


def test_e_bobbys_two_turns_replayed(table):
    """G2's gate, on the owner's corpus when it is on this disk. Turn 12: his own line,
    now with the chip, and nothing prepared → one 422 carrying `unprepared`, zero model
    calls (the recording shows seven refusals). Turn 13: the Spells tab's cast with no aim
    — recorded as `targets: []` and a bare 1d4 — is now refused `no_aim`, the player's to
    answer, and nothing is spent."""
    import replays
    from rules import casting

    if not replays.available():
        pytest.skip("the Bobby corpus is not on this disk")
    twelve, thirteen = replays.turn(12), replays.turn(13)
    recorded = next(e for o in replays.outcomes(thirteen) for e in o["effects"]
                    if e.get("kind") == "cast")
    assert recorded["targets"] == [] and recorded["dice"] == "1d4"
    c, _man = table["begin"]({})
    r = _say({"text": twelve["player"],
              "attachments": [{"kind": "spell", "id": "burning-hands"}]})
    assert r.status_code == 422 and r.json()["refusal"]["code"] == "unprepared"
    assert table["calls"]["plan"] == table["calls"]["chat"] == 0
    c.scene.pc().prepared = {"burning-hands": 1}
    c.save()
    before = casting.slots_left(c.scene.pc(), 1)
    r = _cast({"spell": "burning-hands", "label": thirteen["player"]})
    assert r.status_code == 422 and r.json()["refusal"]["code"] == "no_aim"
    assert casting.slots_left(c.scene.pc(), 1) == before


def test_e_a_typed_cast_aims_like_an_attached_one():
    """One route for typed and attached casts: "into the tree tops" typed with no chip is
    grounded by the same reader, so the typed cast does not arrive aimed at nothing."""
    from gm import judgement
    from rules.engine import Scene

    s = Scene(location_id="5bbd0c40345f")
    s.add(ysolde({"burning-hands": 1}))
    stand_on(s, "forest")
    out = judgement.inject_cast([], "I cast burning hands into the tree tops", s)
    assert out[-1]["params"] == {"spell": "burning-hands", "aim": "object:canopy"}


def test_e_the_chip_beats_the_words_and_the_model():
    """One chip is one spell: the plan's cast takes the chip's spell id and aim; a plan
    with no cast gets one; a second cast is dropped."""
    from gm import judgement
    from rules.engine import Scene

    s = Scene(location_id="5bbd0c40345f")
    s.add(ysolde({"burning-hands": 1}))
    chip = ({"kind": "spell", "id": "burning-hands", "aim": "object:canopy"},)
    raw = [{"op": "cast", "actor": "pc", "params": {"spell": "magic-missile"}},
           {"op": "cast", "actor": "pc", "params": {"spell": "shield"}}]
    out = judgement.inject_cast(raw, "I cast magic missile", s, attached=chip)
    casts = [r for r in out if r["op"] == "cast"]
    assert [c["params"] for c in casts] == [{"spell": "burning-hands",
                                            "aim": "object:canopy"}]
    assert judgement.inject_cast([], "", s, attached=chip)[0]["params"]["spell"] == \
        "burning-hands"
