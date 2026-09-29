"""A spell aimed at nobody is refused, and a victim the page invents is caught (G2).

The measurement, the Phase-2 live gate, 2026-09-28 (gemma-4-12B, Aurvantis,
`tools/narrator_audit.py --script cast-area --character fixtures/pc-caster.json`). The
scene held Ysolde (pc), Kaelith Dagmar (c1) and the innkeeper (c2). The player said "I
cast burning hands at the man standing nearest me."; the interpreter read `cast, target:
"the man standing nearest me"`; the plan was

    {"op": "cast", "actor": "pc", "params": {"spell": "burning-hands", "at": "new2"}}

— a placeholder ref for a person nobody introduced. The engine RESOLVED it: the tell
said "…The flames reach nobody.", the effect was `{"kind": "cast", "caught": [],
"no_victim": true}`. The page then invented a man, "Dagan Havenstone", described him, and
burned him: "He screams, his skin blistering as he is thrown backward…". Next turn, "I
cast magic missile at him." reached nobody the same way and the page hit him again. No
truth-check repair ran (`repairs: []`).

Two defects, one per half of this file. The engine never checked the legacy `at` at all
(`_check_aim` read only the `aim` param), so a dangling aim resolved at nobody. And the
no-victim check (`gm/checks/empty_roll.py`) only asked about the people on the actor
list — Dagan was not on it, so the pass ran and found nothing.
"""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from gm import agent as agent_mod
from gm import checks
from gm.checks import empty_roll
from rules import grid as gridmod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.intents import IntentError
from rules.sheet import from_dict, load_pc, to_dict

from _a_truth import VORMOOR, WORLD, context, scene_at

LINE = "I cast burning hands at the man standing nearest me."

# The plan the live gate recorded, verbatim.
DANGLING = {"op": "cast", "actor": "pc", "params": {"spell": "burning-hands", "at": "new2"}}

# The beat the page wrote over "The flames reach nobody." (G2, turn 1). The face line is
# Kaelith Dagmar's, from the brief, with the invented name put on it.
DAGAN = (
    "The flame from your palm licks into the air, a searing cone of heat that catches "
    "Dagan's sleeve and the wood of the stall behind him. Dagan Havenstone is a Human: "
    "old enough to have stopped counting; one eye clouded and turned slightly out; "
    "clothes good once and mended more than once since. He screams, his skin blistering "
    "as he is thrown backward into the structure, which groans and splinters under the "
    "force. The air is thick with the smell of scorched fabric and singed hair. The fire "
    "is still flickering in the wood of the stall. He is gasping, clutching his arm, and "
    "the fire is your only light in the sudden, panicked gap of the room. What do you do?")

# And the magic missile beat of the turn after (G2, turn 2).
MISSILE = (
    "The shimmering darts of force strike him with and without a physical sound, "
    "slamming into his chest and shoulder. He recoils, the force of the impact knocking "
    "the air from his lungs and throwing him back against the splintered woodwork of his "
    "stall. What do you do?")


def _caster():
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d["abilities"]["int"] = 18
    d["prepared"] = {"burning-hands": 1, "magic-missile": 1}
    return from_dict(d, ref="pc")


def _home(world):
    """The world's first settlement: Vormoor for Aurvantis, as `_a_truth` has it."""
    if world is WORLD:
        return VORMOOR
    row = (world.play.get("settlements") or [])[0]
    return world.get(row["id"])


def _room(fight: bool = True, world=WORLD):
    """Ysolde with Kaelith Dagmar and the innkeeper, as the gate's scene held them, on a
    board — Kaelith in the cone's path, the innkeeper across the room. In a fight, so a
    cast resolves rather than opening one (the battle gate is Lane E's, and tested
    there)."""
    s = Scene(location_id=_home(world).id)
    s.add(_caster())
    kaelith = s.add(instantiate("guildhand", scene=s, name="Kaelith Dagmar"))
    keeper = s.add(instantiate("guildhand", scene=s, name="the innkeeper"))
    e = Engine(s, Dice(seed=4), world=world)
    e.place_party()
    s.grid = gridmod.Grid(20, 20)
    s.positions["pc"] = (4, 7)
    s.positions[kaelith.ref], s.positions[keeper.ref] = (3, 7), (12, 14)
    if fight:
        s.initiative = [("pc", 20), (kaelith.ref, 10), (keeper.ref, 5)]
        s.sides = {"pc": ["pc"], "them": [kaelith.ref, keeper.ref]}
        s.round, s.turn = 1, 0
    return s, e, kaelith.ref, keeper.ref


# --- defect 1: the engine refuses an aim at nobody ------------------------------------------

def test_the_dangling_at_is_refused_no_such_target_with_the_people_here_named(worlds):
    """G2: `cast at=new2` passed validation and resolved "The flames reach nobody." It is
    refused now, plan-fixable (`no_such_target`, fix-interfaces §2.6), in the attack op's
    words: the people who ARE here, and the introduce that would bring somebody new."""
    s, e, kaelith, keeper = _room(world=worlds)
    with pytest.raises(IntentError) as got:
        e.validate([dict(DANGLING)])
    exc = got.value
    assert exc.code == "no_such_target" and exc.check == "refs"
    assert exc.fixable_by == "plan", "the loop retries it; the player cannot fix a ref"
    said = str(exc)
    assert f"{kaelith} (Kaelith Dagmar)" in said and f"{keeper} (the innkeeper)" in said
    assert "placeholder" in said and "introduce" in said


@pytest.mark.parametrize("params", [
    {"spell": "magic-missile", "at": "c9"},
    {"spell": "burning-hands", "aim": "ref:c9"},
    {"spell": "burning-hands", "aim": "ref:new1"},
])
def test_every_form_of_an_aim_at_nobody_is_refused(params):
    """The next turn of G2 — "I cast magic missile at him." — reached nobody the same
    way. A target spell's `at`, an area spell's `aim: ref:`, and the placeholder in
    either: one refusal, never a resolution."""
    s, e, *_ = _room()
    with pytest.raises(IntentError) as got:
        e.validate([{"op": "cast", "actor": "pc", "params": params}])
    assert got.value.code == "no_such_target"


def test_at_self_is_the_caster_and_not_a_person_called_self():
    """`self` is the aim grammar's word for the caster. Written in the legacy `at` slot
    it was read as a ref — `caught: ["self"]`, nobody — and the refusal above would now
    cost the plan a retry for it. It is the caster."""
    s, e, *_ = _room()
    s.actors["pc"].prepared["mage-armor"] = 1
    outs = e.run(e.validate([{"op": "cast", "actor": "pc",
                              "params": {"spell": "mage-armor", "at": "self"}}])).outcomes
    cast = next(x for x in outs[0].effects if x.get("kind") == "cast")
    assert cast["targets"] == ["pc"]


def test_an_aim_at_somebody_introduced_earlier_in_the_plan_is_legal_and_lands():
    """The fix the refusal names has to work. `_check_aim` asked of the scene as it
    stood, so `introduce` then `aim ref:new1` was refused although new1 is made before
    the cast runs; and `_rename_refs` rewrote no aim, so `at=new1` validated and then
    resolved at "new1", a ref nobody holds. The introduced person is caught now."""
    s, e, *_ = _room()
    intents = e.validate([
        {"op": "introduce", "params": {"who": "a drover warming his hands"}},
        {"op": "cast", "actor": "pc", "params": {"spell": "magic-missile", "at": "new1"}},
    ])
    outs = e.run(intents).outcomes
    made = next(x["bound"]["new1"] for o in outs for x in o.effects
                if x.get("kind") == "introduce")
    cast = next(x for o in outs if o.op == "cast" for x in o.effects
                if x.get("kind") == "cast")
    assert not cast.get("no_victim")
    assert made in cast["targets"]


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def test_the_plan_loop_retries_the_dangling_ref_and_the_real_one_lands(monkeypatch):
    """G2 through `plan_turn`: the stubbed model answers the gate's own plan first and
    a real ref second. Before: one attempt, accepted, "The flames reach nobody." Now the
    first is refused with the people named, the loop goes round, and the second resolves
    with Kaelith caught in the cone."""
    s, e, kaelith, _ = _room()
    gm = agent_mod.GMAgent(WORLD, e)
    replies = [DANGLING, {"op": "cast", "actor": "pc",
                          "params": {"spell": "burning-hands", "aim": f"ref:{kaelith}"}}]
    asked: list = []

    def fake_chat(messages, model, host, **kw):
        asked.append(messages)
        return _Reply(json.dumps({"narration": "", "intents": [replies[min(
            len(asked) - 1, len(replies) - 1)]]}))

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    plan = gm.plan_turn(LINE, history=[])
    assert len(asked) == 2, plan.rejections
    assert "[refs]" in plan.rejections[0] and "'new2' is the placeholder" in \
        plan.rejections[0]
    assert "Kaelith Dagmar" in asked[1][-1]["content"], "the retry is told who is here"
    assert plan.refusal is None
    outs = e.run(plan.intents).outcomes
    cast = next(x for o in outs if o.op == "cast" for x in o.effects
                if x.get("kind") == "cast")
    assert kaelith in cast["caught"] and not cast.get("no_victim")


def test_an_unaimed_cast_takes_the_person_the_players_words_name():
    """The plan leaving the aim empty is the other half: an area spell with none is
    refused "Where do you aim it?" even when the sentence named her. The existing reader
    (`areas.aim_from_words`) grounds a name; "the man standing nearest me" in a room of
    two grounds nothing, and nothing is guessed."""
    from gm import judgement

    s, e, kaelith, _ = _room()
    bare = [{"op": "cast", "actor": "pc", "params": {"spell": "burning-hands"}}]
    named = judgement.aim_the_cast(
        [dict(r) for r in bare], "I cast burning hands at Kaelith.", s,
        {"actions": [{"act": "cast", "object": "burning hands", "target": "Kaelith"}]})
    assert named[0]["params"]["aim"] == f"ref:{kaelith}"
    vague = judgement.aim_the_cast(
        [dict(r) for r in bare], LINE, s,
        {"actions": [{"act": "cast", "object": "burning hands",
                      "target": "the man standing nearest me"}]})
    assert "aim" not in vague[0]["params"]


# --- defect 2: the victim the page invents ---------------------------------------------------

def _nobody(spell="Burning Hands", sid="burning-hands", fire=True):
    """The outcome the gate recorded: resolved, `caught: []`, `no_victim`."""
    return Outcome(
        intent_id="i1", op="cast",
        effects=[{"ref": "pc", "kind": "cast", "spell": sid, "name": spell,
                  "targets": [], "caught": [], "no_victim": True, "dice": "1d4",
                  "aim": {"kind": "ref", "value": "new2", "said": ""}}],
        tell=(f"Ysolde Marrach casts {spell} (caster level 1). "
              + ("The flames reach nobody." if fire else f"{spell} reaches nobody.")))


def _beat(text, outcome=None, world=WORLD):
    """The beat over the gate's two people, in the world's first settlement — the names
    the phantom check trusts (places, the world's own words) are each world's."""
    agent, _ = scene_at("" if world is not WORLD else f"{VORMOOR.id}~urban:the-market",
                        [("Kaelith Dagmar", "guildhand"), ("the innkeeper", "guildhand")],
                        world=world, location=_home(world))
    return agent, context(agent, text, outcomes=[outcome or _nobody()], player=LINE)


def test_the_invented_dagan_havenstone_is_flagged(worlds):
    """G2: the pass ran over this beat and found nothing — `_unharmed` lists the scene's
    actors, and Dagan is not one. The sentences that burn him are flagged now, by his
    invented name and the pronouns that carry him, and the fact is the engine's."""
    agent, ctx = _beat(DAGAN, world=worlds)
    assert "Dagan" not in {a.name for a in agent.engine.scene.actors.values()}
    got = empty_roll.find(ctx)
    assert [f.kind for f in got] == ["harm-without-a-victim"]
    flagged = got[0].sentences
    assert any("blistering" in s and "thrown backward" in s for s in flagged)
    assert any("clutching his arm" in s for s in flagged)
    assert not any(s.startswith("The flame from your palm") for s in flagged), \
        "the spell leaving her hand happened"
    assert "Dagan" in got[0].detail
    assert "reached nobody: there is nobody there it hit" in got[0].fix_hint


def test_the_magic_missile_beat_is_flagged_too():
    """The turn after: "slamming into his chest", "knocking the air from his lungs",
    "throwing him back" — none of which the first cut's impact words read."""
    agent, ctx = _beat("Dagan Havenstone stands by his stall. " + MISSILE,
                       _nobody("Magic Missile", "magic-missile", fire=False))
    got = empty_roll.find(ctx)
    assert got and any("slamming into his chest" in s for s in got[0].sentences)
    assert any("knocking the air" in s for s in got[0].sentences)


def test_the_backstop_cuts_the_phantom_harm_and_states_the_engines_line(worlds):
    agent, ctx = _beat(DAGAN, world=worlds)
    kept, notes = empty_roll.backstop(ctx, ctx.text, empty_roll.find(ctx))
    assert "blistering" not in kept and "clutching his arm" not in kept
    assert "The flames reach nobody." in kept
    assert kept.rstrip().endswith("What do you do?"), "the hand-back stays last"
    assert notes and "not here" in notes[-1]
    assert empty_roll.find(context(agent, kept, outcomes=ctx.outcomes)) == []


def test_the_repair_rewrites_then_the_backstop_holds(monkeypatch):
    """Through `_repair_sentences`, the house way: one rewrite per flagged sentence with
    the fact named, kept only if the check no longer finds it; what the model cannot
    mend the backstop cuts."""
    agent, ctx = _beat(DAGAN)
    asked: list = []

    def fake_chat(messages, *a, **k):
        asked.append(messages)
        return _Reply(json.dumps({"sentence": "The heat washes past the stall and "
                                              "touches nobody."}))

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    out, notes, _ = agent._repair_sentences(ctx.text, checks.run(ctx), ctx)
    assert asked and "there is nobody there it hit" in asked[0][-1]["content"]
    assert "blistering" not in out and "clutching his arm" not in out
    assert empty_roll.find(replace(ctx, text=out)) == []


@pytest.mark.parametrize("text", [
    "The flames scorch the ground where Dagan stood a moment ago. What do you do?",
    "The heat scorches the ground and blackens the earth. What do you do?",
    "Dagan Havenstone watches from the door. The flames scorch the ground at his feet.",
])
def test_the_ground_scorched_is_not_a_victim(text, worlds):
    """The `_GROUND` guard holds for the invented man as it does for the people here:
    fire on the earth is the spell landing on nothing, which is what happened."""
    agent, ctx = _beat(text, world=worlds)
    assert empty_roll.find(ctx) == []


def test_harm_to_the_caster_and_to_somebody_really_hit_is_not_a_phantom():
    """Not every harm sentence in a no-victim beat is false: the caster singeing their
    own hair is theirs, and a blow that did land this turn (another outcome) stays."""
    agent, _ = _beat("")
    s = agent.engine.scene
    kaelith = next(r for r, a in s.actors.items() if a.name == "Kaelith Dagmar")
    hit = Outcome(intent_id="i2", op="attack",
                  effects=[{"kind": "damage", "ref": kaelith, "amount": 3}],
                  tell="Ysolde hits Kaelith Dagmar for 3.")
    text = ("The heat singes the hair on your arms. Your dagger opens Kaelith Dagmar's "
            "arm and she staggers back, bleeding. What do you do?")
    ctx = context(agent, text, outcomes=[_nobody(), hit], player=LINE)
    assert empty_roll.find(ctx) == []


def test_the_turn_door_runs_the_checks_on_the_cast_path(monkeypatch):
    """The spy the gate asked for: with the beat's `repairs: []`, did the truth pass run
    at all on the narrate_turn door for a no-victim cast? It did — and on the real door,
    with the invented man burned, it now finds him and the backstop cuts him."""
    from gm.checks import BeatContext  # noqa: F401 — the contract the spy reads

    agent, _ = _beat("")
    seen: list = []
    real = checks.run

    def spy(ctx, **kw):
        found = real(ctx, **kw)
        seen.append((ctx.door, [f.kind for f in found], ctx.outcomes))
        return found

    monkeypatch.setattr(checks, "run", spy)
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply(json.dumps(
        {"narration": DAGAN, "sentence": "", "suggestions": []})))
    text, repairs, _ = agent.narrate_turn([_nobody()], LINE, "THE BRIEF", [])
    doors = [d for d, *_ in seen]
    assert "turn" in doors, doors
    turn = next(x for x in seen if x[0] == "turn")
    assert turn[2] and turn[2][0].effects[0]["no_victim"], "the outcome reached the check"
    assert "harm-without-a-victim" in turn[1]
    assert "blistering" not in text and "The flames reach nobody." in text
    assert any("not here" in r for r in repairs)
