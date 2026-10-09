"""Nobody is made from a turn's words, and the enemies' turns end where the player's
turn comes round.

Reported by a player on 0.2.10 (2026-10-08, gemma-4-12B heretic, a fresh character whose
first scene was a fight), and reproduced live the same day in the caravan ambush:

1. "I attack the top of his skull" spawned a 13-hp thug NAMED "top of his skull": the
   misaim repair (`judgement.repair_misaimed_attack`) read "the top of his skull" out of
   the sentence with a regex as a victim the scene had never made, and spawned it, on a
   side of its own ("them") beside the raiders. Offline, 9 of 13 sentences aiming at a
   head, a skull, a neck or "the raider's head" minted somebody — and so had "the
   weapon" (2026-09-18) and "twelve raiders coming up the road" (2026-09-19), each closed
   with its own word list. The owner's ruling (2026-10-09): fix it without regex, for
   every phrase. So the misaim repair is gone, the refs repair and the corpse redirect
   make nobody, and `Engine.validate` refuses any spawn or introduce on an untrusted list
   while a fight is on — whatever words a door read.
2. The panel's attack, then the roll: the player fell on the first raider's blow, the
   order skipped them from then on, and the enemy loop gave three creatures four rounds
   each in one reply — twelve turns, 180 s of model calls, the player killed in the
   second round and struck as a corpse in the third and fourth ("You are already dead;
   the blow falls on a corpse"), the same three attacks narrated again each round. The
   campaign did not end until a typed line reached `say`'s downed door; meanwhile the
   combat panel stayed live and its Attack came back 409 "… is in no condition to act."
   — 51 bytes for an 11-letter name, the body in the player's server log.
3. The downed door wrote one line per round bled: "You are bleeding out. (-6 hit
   points)", "(-7 …)", "(-8 …)", "(-9 …)" — four near-identical lines in one reply.
"""
from __future__ import annotations

import json

import pytest
from django.test import override_settings

from gm import judgement
from gm.agent import TurnPlan
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc


# --- 1. nobody is made from a turn's words ------------------------------------------------

# The measured sentences, and earlier victims of the same door: any phrase at all, and none
# of them may make anybody, because nothing here reads which phrase it is.
SENTENCES = [
    "I swing my sword at the top of his skull",
    "I attack the top of his skull",
    "I strike the top of his skull with my sword",
    "I go for the top of his skull",
    "I slash the top of his skull",
    "I aim for his head",
    "I attack his head",
    "I go for the raider's head",
    "I stab the raider in the throat",
    "I swing at the top of his skull",
    "I cut the bandit's head off",
    "I lunge at the back of his neck",
    "I charge the top of his skull",
    "I rush the winged woman and run her through.",
    "I charge the twelve raiders coming up the road",
    "I attack the careful walker",
    "I talk to the merchant and then attack the raider",
]


def _raider_fight():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    foe = instantiate("thug", scene=s, name="the raider")
    s.add(foe)
    e = Engine(s, Dice(seed=3))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"party": ["pc"], "raiders": [foe.ref]}}}],
                     origin="author:test"))
    return s, e, foe


def _the_fight_repairs(raw, line, s):
    """The plan repairs that touch an attack or a person, in `plan_turn`'s order."""
    raw = judgement.bind_placeholders(raw, line, s)
    raw = judgement.fill_obvious_targets(raw, s)
    raw = judgement.aim_at_the_holder(raw, line, s) or raw
    raw = judgement.check_the_target(raw, line, s) or raw
    raw = judgement.redirect_attacks_off_corpses(raw, line, s) or raw
    raw = judgement.inject_fight(raw, line, s)
    raw = judgement.inject_company(raw, line, s)
    raw = judgement.inject_introduce(raw, line, s, None)
    return raw


@pytest.mark.parametrize("target", ["c1", None])
@pytest.mark.parametrize("line", SENTENCES)
def test_no_repair_makes_anybody_in_a_fight_whatever_the_words(line, target):
    """9 of the first 13 sentences spawned a person named for the body part before the fix
    ("top of his skull", "raider's head", "back of his neck"); the measured one killed the
    player. The blow stays on the raider: the plan's own target, or the lone-foe fill's."""
    s, e, foe = _raider_fight()
    raw = [{"op": "attack", "actor": "pc", **({"target": target} if target else {})}]
    raw = _the_fight_repairs(raw, line, s)
    assert not [r for r in raw if r.get("op") in ("spawn", "introduce")], raw
    assert {r.get("target") for r in raw if r.get("op") == "attack"} == {foe.ref}
    e.run(e.validate(raw))
    assert set(s.actors) == {"pc", foe.ref}
    assert set(s.sides) == {"party", "raiders"}


@pytest.mark.parametrize("op,params", [
    ("spawn", {"template": "thug", "name": "top of his skull"}),
    ("spawn", {"template": "thug", "name": "a perfectly ordinary bandit"}),
    ("spawn", {"template": "thug"}),
    ("introduce", {"who": "the back of his neck"}),
    ("introduce", {"who": "an old ferryman"}),
])
def test_the_engine_brings_nobody_into_a_fight_on_a_turns_plan(op, params):
    """The structural check under every door: what the name says is never read. Any spawn
    or introduce on an untrusted list is refused while a fight is on, with the refs that
    ARE here named as the fix."""
    s, e, foe = _raider_fight()
    with pytest.raises(IntentError) as exc:
        e.validate([{"op": op, "params": params},
                    {"op": "attack", "actor": "pc", "target": foe.ref}])
    assert exc.value.code == "no_bodies_in_a_fight"
    assert foe.ref in str(exc.value)


def test_a_trusted_door_may_still_bring_people_into_a_fight():
    """A start, a scheme or the author's cheat carries an `origin`: the world's arrivals are
    the world's, not a turn's words."""
    s, e, _foe = _raider_fight()
    e.run(e.validate([{"op": "spawn", "params": {"template": "thug", "count": 1}}],
                     origin="author:test"))
    assert len(s.actors) == 3


def test_out_of_a_fight_the_plans_own_spawn_still_validates():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    (i,) = Engine(s, Dice(seed=1)).validate(
        [{"op": "spawn", "params": {"template": "thug", "count": 1}}])
    assert i.op == "spawn"


def test_an_invented_ref_is_never_a_new_thug():
    """`attack top_of_his_skull` reaching the refs repair was `spawn name="top of his
    skull"`, and `attack winged_woman` a thug called "winged woman": made from the ref's
    words. In a fight nothing is made or embodied; out of one, only a person the beat
    reader recorded here is given a body, and anybody else is validation's refusal."""
    s, _e, _foe = _raider_fight()
    for ref in ("top_of_his_skull", "winged_woman", "kaldrimia"):
        assert judgement.repair_unknown_refs(
            [{"op": "attack", "actor": "pc", "target": ref}], "I attack her", s) is None
    s.end_encounter()
    for ref in ("top_of_his_skull", "winged_woman", "kaldrimia"):
        assert judgement.repair_unknown_refs(
            [{"op": "attack", "actor": "pc", "target": ref}], "I attack her", s) is None


def test_a_swing_at_the_dead_makes_no_new_opponent():
    """With every foe down, "the raiders keep coming" spawned a Raider from the corpus by
    the player's words. Kicking the fallen stands; nobody is made."""
    s, _e, foe = _raider_fight()
    foe.hp = -20
    foe.apply_hp_state()
    raw = [{"op": "attack", "actor": "pc", "target": foe.ref}]
    assert judgement.redirect_attacks_off_corpses(
        raw, "I keep swinging as the raiders keep coming", s) is None


class _Reply:
    def __init__(self, text, model="fake"):
        self.text, self.seconds, self.model = text, 0.0, model

    def json(self):
        return json.loads(self.text)


def test_the_measured_turn_through_the_plan_attacks_the_raider_and_makes_nobody(
        monkeypatch):
    """The 2026-10-08 turn through `plan_turn`, the model answering what it answered live
    (`attack c4`, "because": "target his skull"): before, the plan came back
    [spawn "top of his skull", attack c2]; now it is the one attack on the raider."""
    from gm import agent as agent_mod
    from world import loader

    world = loader.load_cached("fixtures/aurvantis-campaign.json")
    s, e, foe = _raider_fight()
    e.world = world

    def fake_chat(messages, model, host, **kw):
        return _Reply(json.dumps({"narration": "", "intents": [
            {"op": "attack", "actor": "pc", "target": foe.ref,
             "because": "target his skull"}]}))

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    plan = agent_mod.GMAgent(world, e).plan_turn("I attack the top of his skull",
                                                 history=[])
    assert [(i.op, i.target) for i in plan.intents] == [("attack", foe.ref)]


# --- 2. the enemies' turns end where the player's turn comes round ------------------------

@pytest.fixture
def ambush(tmp_path):
    """The measured board: the player, two raiders, and a third foe on a side of its own
    (the minted "top of his skull" landed on "them"), so the player falling did not make
    `sides_standing` one and end the fight."""
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        for ref, name in (("c1", "the raider"), ("c2", "the second raider"),
                          ("c3", "the third man")):
            foe = instantiate("thug", scene=c.scene, name=name)
            foe.ref = ref
            c.scene.add(foe)
        e = c.engine()
        e.run(e.validate([{"op": "begin_encounter", "params": {
            "sides": {"party": ["pc"], "raiders": ["c1", "c2"], "them": ["c3"]}}}]))
        yield c
        cm._LIVE.clear()


class _Swings:
    """Every creature swings at the player, through the engine like the model's plan."""
    engine = None

    def __init__(self, kill_on: str = ""):
        self.kill_on = kill_on

    def npc_turn(self, ref, **_k):
        scene = self.engine.scene
        if ref == self.kill_on:
            pc = scene.pc()
            pc.hp = -99
            pc.apply_hp_state()
            return TurnPlan(narration="", intents=[])
        return TurnPlan(narration="", intents=self.engine.validate(
            [{"op": "attack", "actor": ref, "target": "pc"}], origin="author:test"))

    def narrate_outcome(self, *a, **k):
        return "", None


def _turns(c):
    return [r["ref"] for r in c.turn_log if r.get("kind") == "npc-turn"]


def test_a_downed_player_gets_one_round_per_reply_not_the_whole_budget(ambush, monkeypatch):
    """Measured 2026-10-08: 12 creature turns in one reply (3 creatures × 4 rounds, 180 s)
    while the player lay dying. Now the downed player's slot ends the round: no creature
    acts twice in one reply, the turn is parked on the player, and they are told once."""
    from play import views

    c = ambush
    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    pc = c.scene.pc()
    pc.hp = -1
    pc.apply_hp_state()
    # The player has just had their turn (the blow that dropped them came after it).
    c.scene.turn = next(i for i, (r, _) in enumerate(c.scene.initiative) if r == "pc")
    views._run_npc_turns(c, _Swings())
    turns = _turns(c)
    assert turns and len(turns) == len(set(turns)), turns
    if not c.ended:
        assert c.scene.current_ref() == "pc"
        told = [b for b in c.transcript if "The fight goes on" in b.get("text", "")]
        assert len(told) == 1
        assert not any("scuffle blurs" in b.get("text", "") for b in c.transcript)


def test_a_player_killed_on_the_enemies_turns_ends_the_campaign_in_that_reply(
        ambush, monkeypatch):
    """The player died in the loop and three creatures went on striking the corpse; the
    death waited for a typed line while the panel answered 409. Now nobody acts after the
    death, and the state this reply returns carries `ended` for the page's death screen."""
    from play import views

    c = ambush
    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    c.scene.turn = next(i for i, (r, _) in enumerate(c.scene.initiative) if r == "pc")
    first = c.scene.initiative[(c.scene.turn + 1) % len(c.scene.initiative)][0]
    views._run_npc_turns(c, _Swings(kill_on=first))
    assert _turns(c) == [first]
    assert c.ended == "died"
    assert views._state(c)["ended"] == "died"
    assert "is dead" in c.transcript[-1]["text"]


def test_a_player_up_still_gets_their_turn_back(ambush, monkeypatch):
    """The halt is for the downed: a standing player's turn comes round as before."""
    from play import views

    c = ambush
    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    views._run_npc_turns(c, _Swings())
    if not c.ended and c.scene.in_encounter:
        assert c.scene.current_ref() == "pc"


def test_the_order_halts_on_a_downed_player_slot():
    """`advance_turn(halt_on=…)` stops on the player's slot whether or not they can act;
    without it the walk skipped them and went round again."""
    s, e, foe = _raider_fight()
    pc = s.pc()
    pc.hp = -2
    pc.apply_hp_state()
    seen = [s.advance_turn(halt_on="pc") for _ in range(4)]
    assert "pc" in seen
    assert [s.advance_turn() for _ in range(3)] == [foe.ref] * 3


# --- 3. the bleeding said once -------------------------------------------------------------

def test_the_rounds_bled_are_one_line_not_one_per_round():
    """"You are bleeding out. (-6 hit points)" … "(-9 hit points)": four lines in the
    measured reply. Every round is still rolled; the rounds are said once."""
    from play import downed
    from tests.test_death import FakeCampaign

    for seed in range(1, 9):
        s = Scene(location_id="5bbd0c40345f")
        s.add(load_pc("fixtures/pc-kesst.json"))
        pc = s.pc()
        pc.hp = -5
        pc.apply_hp_state()
        out = downed.resolve(FakeCampaign(s, seed=seed))
        bled = [line for line in out.lines if line.startswith("You bleed for")]
        assert len(bled) == 1, out.lines
        assert not any("You are bleeding out" in line for line in out.lines)
