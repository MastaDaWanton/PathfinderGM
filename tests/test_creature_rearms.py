"""A disarmed creature takes its weapon back up, and stooping for it costs what 1e says.

Found 2026-09-27, closing the first "Still open" line of docs/maneuver-outcomes.md. A
successful disarm put the thug's sap on the ground and the legality check refused him
swinging it there — and then nothing let him recover it. The creature turn's op list had
no `give`, and the fallback path (the only one with Ollama down) swung `equipped`, which
the disarm had set to "unarmed": a disarmed thug punched round after round with his sap
at his feet and a dagger in his belt.

The shape is TemplePlus's (ToEE `ai.cpp`: before any tactic, "check if disarmed, if so,
try to pick up weapon" — only with an empty hand, only within reach) and the price is the
Core Rulebook's (Table 7-2: picking an item up is a move action that provokes; drawing a
weapon is a move action that does not). The order — pick it up, else draw, else fists —
is the user's ruling of 2026-09-27. docs/creature-rearms.md is the record.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from gm import judgement
from rules import reactions
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

THUG = "the thug"


class _AimedCMB(Dice):
    """Every CMB d20 lands on the face asked for; everything else rolls as usual."""

    def __init__(self, face: int = 20, seed: int = 20260927):
        super().__init__(seed=seed)
        self.face = face

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if "(CMB)" in (label or ""):
            return self.given(self.face, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _disarmed(pc_at=(6, 10), thug_at=(7, 10)):
    """The player and a thug on the map a fight lays, the thug's sap knocked to his
    feet by a disarm that beats his CMD by 10 or more. Both are given hit points
    enough that no stray blow ends the fight under the test."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name=THUG))
    engine = Engine(scene, _AimedCMB())
    engine._ensure_encounter("pc")
    scene.positions["pc"], scene.positions["c1"] = pc_at, thug_at
    scene.resync_zones()
    pc, thug = scene.get("pc"), scene.get("c1")
    pc.abilities["str"] = 30
    for a in (pc, thug):
        a.hp = a.hp_max = 400
    res = engine.run(engine.validate([{
        "op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
        "params": {"manoeuvre": "disarm", "item": "sap"}}]))
    while res.awaiting:
        res = engine.resume(20)
    assert thug.equipped == "unarmed" and scene.out_of_hand("c1", "sap")
    return scene, engine, pc, thug


def _settle(engine, res):
    """Answer every roll the player is asked for with a middling face."""
    while res.awaiting:
        res = engine.resume(min(10, res.awaiting.get("max", 20)))
    return res


def _run(engine, raw):
    return _settle(engine, engine.run(engine.validate(raw))).outcomes


def _swung(outcomes, label="Attack with") -> list[str]:
    """The thug's swings, by the weapon on the roll's label (the player's attack of
    opportunity is not his)."""
    return [r["label"] for o in outcomes if o.op == "attack" and o.tell.startswith(THUG)
            for r in (o.as_dict().get("rolls") or []) if label in r.get("label", "")]


# --- the defect, on the path the player actually meets ------------------------------------

@pytest.fixture
def campaign_fight(tmp_path):
    """The combat panel's fight (tests/test_combat_panel.py), the thug disarmed and
    standing over his sap. The model is refused by conftest, so the NPC loop takes the
    fallback path — the one every creature turn took with Ollama down."""
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.seed = 20260927
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        thug = instantiate("thug", scene=c.scene, name=THUG)
        thug.ref = "c1"
        c.scene.add(thug)
        e = c.engine()
        e.run(e.validate([{"op": "begin_encounter",
                           "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
        c.scene.positions["pc"], c.scene.positions["c1"] = (6, 8), (7, 8)
        c.scene.resync_zones()
        pc = c.scene.pc()
        pc.abilities["str"] = 30
        for a in (pc, thug):
            a.hp = a.hp_max = 400
        aimed = Engine(c.scene, _AimedCMB())
        res = aimed.run(aimed.validate([{
            "op": "attack", "actor": "pc", "target": "c1",
            "params": {"manoeuvre": "disarm", "item": "sap"}}]))
        while res.awaiting:
            res = aimed.resume(20)
        while c.scene.current_ref() != "pc":
            c.scene.advance_turn()
        c.save()
        yield Client(), cm
        cm._LIVE.clear()


def _hold_six_rounds(client, cm) -> list[str]:
    """The player passes six turns at the panel, answering any roll the engine asks of
    them (the attack of opportunity the pick-up provokes). Returns the label of every
    swing the thug made."""
    for _ in range(6):
        r = client.post("/api/combat/act",
                        data=json.dumps({"actions": [], "end_turn": True}),
                        content_type="application/json")
        assert r.status_code == 200, r.content[:300]
        for _ in range(8):
            if not cm.current().scene.awaiting:
                break
            client.post("/api/roll", data="{}", content_type="application/json")
    swings = []
    for entry in cm.current().scene.log:
        if entry.get("op") != "attack":
            continue
        for roll in entry.get("rolls") or []:
            if roll.get("label", "").startswith("Attack with") and "Kesst" not in str(
                    entry.get("tell", ""))[:10]:
                if entry.get("tell", "").startswith(THUG):
                    swings.append(roll["label"])
    return swings


def test_a_disarmed_thug_punched_for_six_rounds_with_his_sap_at_his_feet(campaign_fight):
    """Measured before the fix: six rounds of the thug's fallback turn, six swings, every
    one `equipped` — "unarmed" — with his sap lying in his own square and a dagger on
    his weapons list. Now the first turn picks the sap up and every swing is the sap."""
    client, cm = campaign_fight
    swings = _hold_six_rounds(client, cm)
    assert len(swings) >= 5, swings
    assert set(swings) == {"Attack with sap"}, swings
    tells = [e.get("tell", "") for e in cm.current().scene.log if e.get("op") == "give"]
    assert tells == ["the thug takes the sap back up off the ground; it is in hand again."]
    assert cm.current().scene.get("c1").equipped == "sap"
    assert not cm.current().scene.out_of_hand("c1", "sap")


# --- the model's path --------------------------------------------------------------------

def test_the_models_plan_is_rearmed_and_its_prompt_is_told_so(monkeypatch):
    """The model cannot emit a `give` on a creature's turn (the enum), so left to itself
    it swings fists — measured: `attack` with `weapon: unarmed` and a full attack. The
    engine puts the pick-up first and cuts the rest to one swing with what is in hand;
    the prompt says so as a fact, so the wind-up does not raise the fists."""
    from gm import agent as agent_mod, client

    scene, engine, pc, thug = _disarmed()

    class World:
        name, secret, premise, entities = "Testholme", "", {}, {}
        unwritten, chronology, factions = [], [], []

        def ancestors(self, _):
            return []

    seen = []

    def chat(messages, model, *a, **kw):
        seen.append(messages[-1]["content"])
        return client.Reply(json.dumps({
            "narration": "The thug comes on with his fists up.",
            "intents": [{"op": "attack", "actor": "c1", "target": "pc",
                         "params": {"weapon": "unarmed", "full_attack": True}}]}),
            0.1, model)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    gm = agent_mod.GMAgent(World(), engine)
    plan = gm.npc_turn("c1")
    assert "Its sap (a light one-handed bludgeoning weapon: weighted head" in seen[0]
    assert "lies at its feet" in seen[0] and "swings once" in seen[0]
    ops = [(i.op, dict(i.params)) for i in plan.intents]
    assert ops[0][0] == "give" and ops[0][1]["item"] == "the thug's sap"
    attack = ops[1][1]
    assert not attack.get("full_attack") and "weapon" not in attack
    assert any(r.startswith("rearm:") for r in plan.repairs), plan.repairs
    out = _settle(engine, engine.run(plan.intents))
    assert _swung(out.outcomes) == ["Attack with sap"]


def test_a_full_attack_after_a_pick_up_is_one_swing():
    """A pick-up is a move action; what is left is a standard action — one attack."""
    scene, engine, pc, thug = _disarmed()
    raw, repairs = judgement.rearm(scene, "c1", [
        {"op": "attack", "actor": "c1", "target": "pc", "params": {"full_attack": True}},
        {"op": "attack", "actor": "c1", "target": "pc", "params": {"iteration": 1}}])
    assert [r["op"] for r in raw] == ["give", "attack"]
    assert raw[1]["params"]["full_attack"] is False
    assert "rearm: full attack cut to one swing" in repairs


# --- the order: pick it up, else draw, else fists ---------------------------------------

def test_a_sap_out_of_reach_leaves_the_dagger_to_draw():
    """Knocked 15 feet from his sap (a bull rush after the disarm), he does not walk to
    it — TemplePlus's AI never does — he draws the dagger he carries, which provokes
    nothing (Table 7-2), and swings that."""
    scene, engine, pc, thug = _disarmed()
    scene.positions["c1"] = (10, 10)
    # And the player stepped in after him: the swing that follows the draw has its reach
    # (the melee-reach rule merged to master while this test was written; at 20 ft the
    # dagger swing is refused, which is right and not what this test is about).
    scene.positions["pc"] = (11, 10)
    scene.resync_zones()
    assert scene.within_reach("c1", scene.out_of_hand("c1", "sap")) == 10
    assert judgement.rearm_step(scene, "c1") == ("draw", "dagger")
    raw, _ = judgement.rearm(scene, "c1", [{"op": "attack", "actor": "c1", "target": "pc"}])
    outcomes = _run(engine, raw)
    assert outcomes[0].tell == "the thug draws the dagger."
    assert thug.equipped == "dagger"
    assert "held_by" not in scene.out_of_hand("c1", "sap")   # still where it fell


def test_a_sap_in_the_players_hands_leaves_the_dagger_to_draw():
    scene, engine, pc, thug = _disarmed()
    _run(engine, [{"op": "give", "actor": "pc", "params": {"item": "sap", "to": "pc"}}])
    assert scene.out_of_hand("c1", "sap")["held_by"] == "pc"
    assert judgement.rearm_step(scene, "c1") == ("draw", "dagger")


def test_with_nothing_to_re_arm_with_the_fists_are_left_alone():
    scene, engine, pc, thug = _disarmed()
    thug.weapons.clear()
    scene.positions["c1"] = (10, 10)
    raw = [{"op": "attack", "actor": "c1", "target": "pc"}]
    assert judgement.rearm(scene, "c1", raw) == (raw, [])


def test_a_creature_never_disarmed_keeps_the_hand_it_chose():
    """Rearm is for the disarmed. A thug who put his sap away to brawl is not."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name=THUG))
    Engine(scene, Dice(seed=1))._ensure_encounter("pc")
    scene.get("c1").equipped = "unarmed"
    assert judgement.rearm_step(scene, "c1") is None


# --- the price: a pick-up provokes, and has to be reached ------------------------------

def test_stooping_for_a_sap_beside_the_player_provokes_the_players_swing():
    """Table 7-2, "Pick up an item": attack of opportunity, yes. The player standing
    over the thug gets the swing, and rolls it — the reaction suspends for their die."""
    scene, engine, pc, thug = _disarmed()
    raw, _ = judgement.rearm(scene, "c1", [{"op": "attack", "actor": "c1", "target": "pc"}])
    res = engine.run(engine.validate(raw))
    assert res.awaiting and res.awaiting["because"] == "the thug stooped for the sap within reach"
    assert scene.reacted.get("pc:attack_of_opportunity") == 1


def test_the_players_own_pick_up_provokes_an_armed_foe_and_not_a_disarmed_one():
    """One rule, both ways. The player picking up the sap beside a thug who has drawn
    his dagger takes the thug's swing; beside a thug with nothing in hand, none — "an
    unarmed character can't take attacks of opportunity" (Actions in Combat), which
    until this was moot because nothing but a move provoked."""
    scene, engine, pc, thug = _disarmed()
    assert reactions.disarmed_and_empty_handed(scene, thug)
    assert not reactions.provoked_by_action(scene, "pc")
    thug.equipped = "dagger"
    assert [w for w, _ in reactions.provoked_by_action(scene, "pc")] == ["c1"]
    outcomes = _run(engine, [{"op": "give", "actor": "pc",
                              "params": {"item": "sap", "to": "pc"}}])
    assert [o.op for o in outcomes] == ["attack", "give"]
    assert outcomes[0].because == "Kesst Vayr stooped for the sap within reach"


def test_a_sap_out_of_reach_is_walked_to_not_taken_across_the_room():
    scene, engine, pc, thug = _disarmed()
    scene.positions["pc"] = (2, 10)
    scene.resync_zones()
    out = _run(engine, [{"op": "give", "actor": "pc", "params": {"item": "sap", "to": "pc"}}])
    assert out[-1].status == "refused"
    # (2,10) to the sap at (7,10): 25 ft, less a Medium reach of 5.
    assert "20 ft beyond Kesst Vayr's reach. Move next to it first" in out[-1].tell
    assert "held_by" not in scene.out_of_hand("c1", "sap")


def test_a_blow_that_drops_him_as_he_stoops_stops_the_pick_up_and_the_swing():
    """The move's rule, for a pick-up: the attack of opportunity lands before the hand
    closes, and if it drops him he never has the sap — nor the swing queued behind it,
    which measured live still rolled from an unconscious thug."""
    scene, engine, pc, thug = _disarmed()
    thug.hp = 1
    raw, _ = judgement.rearm(scene, "c1", [{"op": "attack", "actor": "c1", "target": "pc"}])
    res = engine.run(engine.validate(raw))
    faces = iter([20, 20, 6, 6, 6])
    while res.awaiting:
        res = engine.resume(min(next(faces), res.awaiting["max"]))
    tells = [o.tell for o in res.outcomes]
    assert thug.is_down, tells
    assert any("never picks up the sap" in t for t in tells), tells
    assert any("never swings" in t for t in tells), tells
    assert not _swung(res.outcomes, "Attack with sap")
    assert "held_by" not in scene.out_of_hand("c1", "sap")


def test_where_a_disarmed_weapon_fell_is_kept_on_its_record():
    """Greater Disarm's Normal line: "Disarmed weapons and gear land at the feet of the
    disarmed creature" — in his square, so a push after the disarm leaves it behind."""
    scene, engine, pc, thug = _disarmed()
    assert scene.out_of_hand("c1", "sap")["square"] == [7, 10]


def test_every_trigger_a_reaction_answers_is_declared():
    for reaction in reactions.reactions_for(load_pc("fixtures/pc-kesst.json")):
        for trig in (reaction.trigger, *reaction.also):
            assert trig in reactions.TRIGGERS


def test_the_tell_says_what_the_blow_was_struck_with():
    """Measured live 2026-09-27: the thug had his sap back and swung it three rounds
    running; the tells read "the thug hits Kesst Vayr for 5 bludgeoning", and the prose
    had him grabbing her forearm, punching her ribs and raking with "its taloned
    limbs". The narrator is fed tells only, so the weapon is in the tell — as the
    instrument, after the defender, never as the subject (narration.wrong_hands)."""
    scene, engine, pc, thug = _disarmed()
    raw, _ = judgement.rearm(scene, "c1", [{"op": "attack", "actor": "c1", "target": "pc"}])
    tells = [o.tell for o in _run(engine, raw) if o.op == "attack" and o.tell.startswith(THUG)]
    assert tells and all(" with the sap " in t for t in tells), tells
    assert tells[0].startswith(("the thug hits Kesst Vayr with the sap for ",
                                "the thug's attack with the sap misses Kesst Vayr ")), tells
    # A bare hand names nothing: "with the unarmed strike" is not a sentence.
    fists = _run(engine, [{"op": "attack", "actor": "pc", "target": "c1",
                           "params": {"weapon": "unarmed"}}])
    assert not any("with the unarmed" in o.tell for o in fists), [o.tell for o in fists]


def test_a_creatures_turn_is_told_what_is_in_its_hand_and_what_that_is():
    """Measured live 2026-09-27, two runs. Told nothing, a thug holding his sap was
    written grabbing, pinning and seizing (0 of 3 wind-ups named a weapon); told "the
    sap", 4 of 4 named it and the model made it "a heavy vial of sap" whose "sticky
    liquid splashes wide". The row's own words say what a sap is."""
    from gm import prompts

    scene, engine, pc, thug = _disarmed()
    thug.equipped = "sap"
    ask = prompts.npc_turn_messages("brief", [], "c1", thug, 2)[-1]["content"]
    assert "In hand: the sap (a light one-handed bludgeoning weapon: weighted head, "            "wrapped grip)." in ask
    thug.equipped = "unarmed"
    ask = prompts.npc_turn_messages("brief", [], "c1", thug, 2)[-1]["content"]
    assert "In hand" not in ask


def test_a_move_and_a_swing_after_a_pick_up_keeps_one_or_the_other():
    """Pick-up (move) + swing (standard) is a turn; pick-up + move + swing is not. The
    swing stays when the foe is in reach from where he stands; otherwise he closes and
    does not swing. A plan with no swing keeps its move: two move actions."""
    scene, engine, pc, thug = _disarmed()
    step = {"op": "move", "actor": "c1", "params": {"square": [9, 10]}}
    swing = {"op": "attack", "actor": "c1", "target": "pc"}
    raw, _ = judgement.rearm(scene, "c1", [dict(step), dict(swing)])
    assert [r["op"] for r in raw] == ["give", "attack"]
    scene.positions["pc"] = (2, 10)                  # out of his reach
    raw, repairs = judgement.rearm(scene, "c1", [dict(step), dict(swing)])
    assert [r["op"] for r in raw] == ["give", "move"]
    assert "rearm: the target is out of reach; it closes instead of swinging" in repairs
    raw, _ = judgement.rearm(scene, "c1", [dict(step)])
    assert [r["op"] for r in raw] == ["give", "move"]


def test_the_fallback_turn_re_arms_then_closes_when_the_player_is_out_of_reach():
    """Where two branches met (2026-09-28): master's fallback closes the distance before a
    swing (melee reach), and this branch's re-arms a disarmed creature first. Together,
    in the rule's order: pick the sap up (a move action), then — the player being out of
    reach — close instead of swinging (the second move action), never swing from afar."""
    scene, engine, pc, thug = _disarmed()
    scene.positions["pc"] = (2, 10)           # the player steps well back out of reach
    scene.resync_zones()
    planned = judgement.default_npc_action(scene, "c1")
    ops = [r["op"] for r in planned]
    assert ops[0] == "give" and planned[0]["params"]["to"] == "c1"   # the sap, first
    assert "attack" not in ops and "move" in ops, planned
