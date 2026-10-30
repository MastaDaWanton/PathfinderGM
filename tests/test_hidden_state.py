"""Hiding is held across turns: invisibility and Stealth, asked of each observer.

The owner, 2026-10-30: "with potions of invisibility and the stealth skill will npcs not only
fail to see me the turn i take it but also still honor that in the following turns assuming
I have not done anything to reveal myself?" Measured on 0.2.23 (the investigation's probes,
scratchpad `invis/`), the answer was no, eight ways over:

  * the potion's `ends_when` was dropped by `consumables`, so Kesst stabbed the thug for 9
    and stayed invisible for all 30 rounds (p3);
  * the fallback planner picked the invisible player 4 of 4 rounds and walked to her square
    (p2 A), and gemma wrote `attack target=pc` 3 of 3 turns (live_npc.out);
  * walking out of a Large thug's reach drew his attack of opportunity (p2 B);
  * the invisibility spells were narrative only — a cast changed nothing (p4);
  * a won Stealth check left no state behind, and next turn the thug walked up and hit (p7);
  * the brief said only "Conditions: invisible" and every wind-up was "aimed at your head";
  * the invisible attacker's Dex denial held only in round one (p2 D);
  * one Stealth check paid a level-2 PC 300 XP (live_pc.out).

The rules are the Core Rulebook's (rules/awareness.py carries the quotes and the AoN pages):
Invisibility p.301-302, Invisibility p.564, Concealment p.196, Stealth p.106, Perception p.102.
"""
from __future__ import annotations

import json

import pytest

from rules import awareness, goods, reactions
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.intents import IntentError
from rules.sheet import load_pc
from tests._places import stand_on


def _board(fight=True, seed=7, thug_at=(6, 5), pc_at=(5, 5)):
    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
    s.add(load_pc("fixtures/pc-kesst.json"), at=pc_at)
    s.add(instantiate("thug", scene=s, name="the thug"), at=thug_at)
    stand_on(s, "urban")
    s.clock_minutes = 12 * 60
    if fight:
        s.sides = {"us": ["pc"], "them": ["c1"]}
        s.initiative = [("pc", 20), ("c1", 10)]
        s.round, s.turn = 1, 0
    pc = s.actors["pc"]
    pc.hp = pc.hp_max = 500
    thug = s.actors["c1"]
    thug.hp = thug.hp_max = 500
    return s, Engine(s, Dice(seed=seed))


def _drink(s, e):
    pc = s.actors["pc"]
    good = next(g for g in goods.potion_goods() if g.name == "Potion of Invisibility")
    goods.deliver(s, pc, good)
    iid = next(k for k, v in pc.stock.items() if "nvisib" in v.base)
    return e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "drinks",
                              "params": {"item": iid, "how": "drink"}}]))


def _cast_on(e, spell_id, target="pc", caster="pc"):
    """The spell's own document, laid through the cast door's executor."""
    from rules import spells

    spell = spells.get(spell_id)
    return e._run_specs([s for s in spells.effects_at(spell, 5)
                         if s.get("type") == "apply_condition"],
                        {"caster": caster, "targets": [target], "rounds": 10,
                         "source": spell.name, "origin": f"spell:{spell_id}",
                         "self_ok": True})


def _finish(e, res, face=15):
    n, outcomes = 0, list(res.outcomes)
    while res.status != "complete" and n < 8:
        aw = e.scene.awaiting if isinstance(e.scene.awaiting, dict) else {}
        res = e.resume(face=max(int(aw.get("min", 1)), min(face, int(aw.get("max", 20)))))
        outcomes += list(res.outcomes)
        n += 1
    res.outcomes = outcomes
    return res


def _tells(res):
    return " ".join(o.tell for o in res.outcomes if o.tell)


# --- 1. ends on attack ---------------------------------------------------------------------

def test_the_potion_of_invisibility_ends_the_moment_its_drinker_attacks():
    """Probe p3, 0.2.23: Kesst drank, stabbed the thug for 9 and stayed invisible for the
    potion's whole 30 rounds — `consumables` dropped `ends_when` and nothing read one.
    Invisibility, CRB p.301: "The spell ends if the subject attacks any creature." The end
    is told with the blow, and the blow that breaks it still had the +2."""
    s, e = _board()
    _drink(s, e)
    pc = s.actors["pc"]
    assert pc.has_state("state.hidden.invisible")
    eff = next(x for x in pc.effects if x.key == "invisible")
    assert eff.payload["ends_when"] == {"acts": ["attack", "cast_offensive"]}
    res = _finish(e, e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                                        "because": "stab"}])))
    assert not pc.has_state("state.hidden.invisible")
    assert "visible again" in _tells(res)
    assert any(x.get("kind") == "effect_ended" for o in res.outcomes for x in o.effects)


def test_greater_invisibility_survives_the_attack():
    """"This spell functions like invisibility, except that it doesn't end if the subject
    attacks" (CRB p.302): the document carries no `ends_when`. The struck thug learns the
    square the blow came from (CRB p.564) — and loses it when the player steps away."""
    s, e = _board()
    pc, thug = s.actors["pc"], s.actors["c1"]
    _cast_on(e, "invisibility-greater")
    assert pc.has_state("state.hidden.invisible")
    res = _finish(e, e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                                        "because": "stab"}])), face=19)
    assert pc.has_state("state.hidden.invisible"), _tells(res)
    if any(o.verdict == "hit" for o in res.outcomes):
        assert awareness.knows_where(s, thug, pc)
        assert not awareness.sees(s, thug, pc), "a pinpoint is not sight: 50% still"
        moved = e.run(e.validate([{"op": "move", "actor": "pc", "because": "step",
                                   "params": {"square": [4, 4]}}]))
        assert not awareness.knows_where(s, thug, pc)
        assert "no longer knows where" in _tells(moved)


def test_a_harmful_spell_at_a_foe_ends_it_and_the_spell_documents_lay_it():
    """Probe p4, 0.2.23: a wizard cast invisibility and nothing about her changed — the
    four invisibility spells' mechanics were narrative under a stale note that "the
    vocabulary has no 'invisible' condition". Now each lays the condition, the plain and
    mass and sphere with the attack's end, the greater without; and a harmful spell at a
    foe is an attack ("any spell targeting a foe", CRB p.301)."""
    from rules import spells

    for sid, ends in (("invisibility", True), ("invisibility-greater", False),
                      ("invisibility-mass", True), ("invisibility-sphere", True)):
        doc = spells.effects_at(spells.get(sid), 5)
        cond = [x for x in doc if x.get("type") == "apply_condition"]
        assert [c["target"] for c in cond] == ["invisible"], sid
        assert bool(cond[0].get("ends_when")) is ends, sid
        assert "no 'invisible' condition" not in json.dumps(doc), sid
    s, e = _board()
    pc = s.actors["pc"]
    _cast_on(e, "invisibility")
    assert pc.has_state("state.hidden.invisible")
    said, kept = e._ends_on_act(pc, "cast_offensive")
    assert said and not pc.has_state("state.hidden.invisible")


def test_a_manoeuvre_is_an_attack_and_ends_it_too():
    """A trip is an attack roll (CMB against CMD) at a creature: "an attack includes any
    spell targeting a foe" says how wide the book draws it (CRB p.301), and the manoeuvre
    door returns early from the attack op, so it is asked on its own."""
    s, e = _board()
    _drink(s, e)
    pc = s.actors["pc"]
    res = _finish(e, e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                                        "because": "trip",
                                        "params": {"manoeuvre": "trip"}}])), face=12)
    assert any(o.op == "attack" and o.rolls for o in res.outcomes), _tells(res)
    assert not pc.has_state("state.hidden.invisible")
    assert "visible again" in _tells(res)


# --- 2. Stealth, held --------------------------------------------------------------------

def _behind_a_wall(s):
    for y in range(2, 9):
        s.grid.blocked.add((8, y))


def test_a_won_stealth_check_is_held_and_the_next_turn_honours_it():
    """Probe p7, 0.2.23: "I hide behind the crates" beat the thug's Perception by 19 and
    left nothing behind — next turn his fallback walked up and swung. Stealth, CRB p.106:
    "Creatures that fail to beat your Stealth check are not aware of you". The result is
    kept (`state.hidden.stealth`, source rule:stealth), sneaking is half speed, and the
    thug's fallback searches instead of swinging."""
    s, e = _board(fight=False, thug_at=(12, 5))
    _behind_a_wall(s)
    pc = s.actors["pc"]
    pc.add_buff("skill_mod", "stealth", 40, source="test: a very quiet rogue")
    res = _finish(e, e.run(e.validate([{
        "op": "check", "actor": "pc", "because": "hide",
        "params": {"skill": "stealth", "opposed_by": {"ref": "c1", "skill": "perception"}}}])),
        face=15)
    assert pc.has_state(awareness.SNEAKING), _tells(res)
    assert awareness.stealth_result(pc) >= 50
    assert pc.speed_feet == 15, "sneaking at half speed (CRB p.106)"
    s.sides = {"us": ["pc"], "them": ["c1"]}
    s.initiative = [("pc", 20), ("c1", 10)]
    s.round, s.turn = 1, 1
    from gm import judgement

    plan = judgement.default_npc_action(s, "c1")
    assert plan[0]["op"] == "check" and plan[0]["params"].get("search"), plan


def test_stealth_is_refused_while_watched_in_the_open():
    """"If people are observing you ... you can't use Stealth. Against most creatures,
    finding cover or concealment allows you to use Stealth" (CRB p.106). At noon in the
    open with the thug six squares off, nothing is rolled and the way round is named."""
    s, e = _board(fight=False, thug_at=(11, 5))
    res = e.run(e.validate([{
        "op": "check", "actor": "pc", "because": "sneak",
        "params": {"skill": "stealth", "opposed_by": {"ref": "c1", "skill": "perception"}}}]))
    assert res.status == "complete"
    out = next(o for o in res.outcomes if o.op == "check")
    assert out.status == "refused" and "cover or concealment" in out.tell
    assert not s.actors["pc"].has_state("state.hidden")


def test_an_attack_from_stealth_ends_it_but_a_snipe_from_ten_feet_keeps_it():
    """"Your Stealth immediately ends after you make an attack roll ... (except when
    sniping)"; sniping: "at least 10 feet from your target, you can make one ranged attack
    and then immediately use Stealth again ... a -20 penalty" (CRB p.106)."""
    s, e = _board(thug_at=(9, 5))
    pc = s.actors["pc"]
    pc.add_buff("skill_mod", "stealth", 80, source="test: a ghost")
    pc.apply_effect(ActiveEffect(
        name="Hidden", kind="condition", key="sneaking", source="rule:stealth",
        origin="rule:stealth", tags=("state.hidden.stealth", "state.slowed"),
        payload={"result": 90, "at": s.at, "ends_when": dict(awareness.ENDS_ON_ATTACK)}))
    thug = s.actors["c1"]
    weapon = {"category": "ranged", "name": "shortbow"}
    fx, said = e._hiding_after_attack(pc, thug, weapon, "shortbow",
                                      {"seen": False, "rolls": []}, True)
    assert pc.has_state(awareness.SNEAKING), said
    assert any(x.get("kind") == "sniping" for x in fx)
    assert awareness.stealth_result(pc) >= 60, "re-hidden at -20 with +80"
    fx, said = e._hiding_after_attack(pc, thug, {"category": "melee"}, "rapier",
                                      {"seen": True, "rolls": []}, True)
    assert not pc.has_state(awareness.SNEAKING)
    assert any("no longer hidden" in x for x in said)


# --- 3. per-observer awareness -----------------------------------------------------------

def test_perception_at_the_top_of_a_turn_finds_a_player_who_ran():
    """Invisibility, CRB p.564: DC 20 to notice within 30 ft, +20 to pinpoint; running is
    -20, standing still +20. A thug with a hound's nose (+40) finds a player who ran, at
    the top of his turn, through the one applicator (`knows.where.pc` on HIM)."""
    s, e = _board(thug_at=(9, 9))
    _drink(s, e)
    pc, thug = s.actors["pc"], s.actors["c1"]
    thug.add_buff("skill_mod", "perception", 40, source="test: a hound's nose")
    e.run(e.validate([{"op": "move", "actor": "pc", "because": "runs",
                       "params": {"square": [5, 11]}}]))
    assert awareness.motion(s, pc) in ("full", "run")
    found = e.turn_begins("c1")
    assert awareness.knows_where(s, thug, pc), [o.tell for o in found]
    assert any(t.startswith(awareness.KNOWS_WHERE) for x in thug.effects for t in x.tags)
    assert found and "fixes on where you" in found[0].tell


def test_an_invisible_player_holding_still_is_beyond_an_ordinary_thug():
    """The same table's other end: still and invisible is DC 40 to notice, 60 to pinpoint.
    The ordinary thug's turn-top check finds nothing, and nothing is told."""
    s, e = _board()
    _drink(s, e)
    assert awareness.notice_dcs(s, s.actors["c1"], s.actors["pc"])[:2] == (40, 60)
    assert e.turn_begins("c1") == []
    assert not awareness.locates(s, s.actors["c1"], s.actors["pc"])


def test_invisible_stealth_is_forty_holding_still_and_twenty_moving():
    """Stealth, CRB p.106: "+40 bonus on Stealth checks if you are immobile, or a +20
    bonus ... if you're moving". The potion's document carried a flat +20 and never the
    +40; the condition carries both now, asked of how they moved."""
    from rules.sheet import situated

    s, e = _board()
    _drink(s, e)
    pc = s.actors["pc"]
    with situated(s):
        assert any(m.value == 40 for m in pc.skill_modifiers("stealth"))
    awareness.note_motion(s, pc, 20)
    with situated(s):
        mods = pc.skill_modifiers("stealth")
    assert any(m.value == 20 for m in mods) and not any(m.value == 40 for m in mods)


# --- 4. targeting ------------------------------------------------------------------------

def test_a_creature_cannot_aim_at_a_player_it_has_not_found():
    """p2 A and live_npc.out: the fallback picked the invisible player 4 of 4 rounds and
    gemma 3 of 3. Concealment, CRB p.196: "You can't attack an opponent that has total
    concealment, though you can attack into a square that you think he occupies." Refused
    at validate with both fixes named; a search earlier in the list defers it to the
    floor; the fallback searches; nobody walks to the square."""
    from gm import judgement
    from rules import position

    s, e = _board()
    _drink(s, e)
    s.turn = 1
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "attack", "actor": "c1", "target": "pc", "because": "x"}])
    assert err.value.code == "unseen_target"
    assert '"search": true' in str(err.value) and '"guess": true' in str(err.value)
    plan = e.validate([{"op": "check", "actor": "c1", "because": "looks",
                        "params": {"skill": "perception", "search": True}},
                       {"op": "attack", "actor": "c1", "target": "pc", "because": "x"}])
    assert [i.op for i in plan] == ["check", "attack"]
    assert judgement.default_npc_action(s, "c1")[0]["params"]["search"] is True
    s.positions["c1"] = (9, 5)
    assert position.closing_move(s, s.actors["c1"], s.actors["pc"], "sap") is None


def test_a_blind_swing_lands_only_on_the_square_the_player_is_in(monkeypatch):
    """The guessed square (CRB p.564, Concealment p.196): the engine's die picks among the
    open squares the creature reaches. With one square in its reach, and the player in
    it, the blind swing is a real attack — through invisibility's 50%; with the player
    elsewhere it is a swing at air, told as a miss and nothing more."""
    s, e = _board()
    _drink(s, e)
    s.turn = 1
    monkeypatch.setattr(reactions, "threatened_by", lambda scene, ref: {(5, 5)})
    res = e.run(e.validate([{"op": "attack", "actor": "c1", "because": "blind swing",
                             "params": {"guess": True}}]))
    out = next(o for o in res.outcomes if o.op == "attack")
    labels = [str(getattr(r, "label", "")) for r in out.rolls]
    assert any("miss chance" in lab for lab in labels) or "finds nothing there" in out.tell \
        or out.verdict in ("hit", "miss"), (out.tell, labels)
    assert "names nobody" not in out.tell
    monkeypatch.setattr(reactions, "threatened_by", lambda scene, ref: {(7, 5)})
    res = e.run(e.validate([{"op": "attack", "actor": "c1", "because": "blind swing",
                             "params": {"guess": True}}]))
    out = next(o for o in res.outcomes if o.op == "attack")
    assert out.verdict == "miss" and "swings blind" in out.tell and "Kesst" not in out.tell


def test_the_turn_prompt_says_it_cannot_see_the_player_and_its_refs_leave_her_out(
        monkeypatch):
    """live_npc.out: the prompt said only "Conditions: invisible" and 3 of 3 wind-ups were
    "aimed at your head". Now the turn says it plainly with the fixes, and the schema's
    ref enum leaves the unfound player out."""
    from gm import agent as agent_mod, client

    s, e = _board()
    _drink(s, e)

    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    seen = []

    def chat(messages, model, *a, **kw):
        seen.append((messages[-1]["content"], kw.get("schema")))
        return client.Reply(json.dumps({
            "narration": "The thug turns a slow circle, listening.",
            "intents": [{"op": "check", "actor": "c1",
                         "params": {"skill": "perception", "search": True}}]}), 0.1, model)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    plan = agent_mod.GMAgent(world, e).npc_turn("c1")
    prompt, schema = seen[0]
    assert "cannot see the player's character" in prompt
    refs = schema["properties"]["intents"]["items"]["properties"]["target"]["enum"]
    assert "pc" not in refs and "c1" in refs
    assert plan.intents[0].params.get("search")


# --- 5. attacks of opportunity -----------------------------------------------------------

def test_no_attack_of_opportunity_at_an_invisible_mover():
    """p2 B, 0.2.23: the invisible player walked out of a Large thug's reach and took his
    swing. "You can't execute an attack of opportunity against an opponent with total
    concealment, even if you know what square or squares the opponent occupies" (CRB
    p.196) — pinpointed or not."""
    s, e = _board()
    s.actors["c1"].size = "large"
    before = reactions.provoked_by_move(s, "pc", (5, 5), (1, 5))
    assert before, "seen, she provokes"
    _drink(s, e)
    assert reactions.provoked_by_move(s, "pc", (5, 5), (1, 5)) == []
    awareness.pinpoint(s, s.actors["c1"], s.actors["pc"], "test")
    assert reactions.provoked_by_move(s, "pc", (5, 5), (1, 5)) == []
    assert reactions.provoked_by_action(s, "pc") == []


def test_an_unseen_attacker_denies_dex_after_the_defender_has_acted():
    """The invisible condition "ignores its opponent's Dexterity bonus to AC" (CRB p.565).
    Measured p2 D: only the not-yet-acted flat-footedness of round one ever denied it."""
    s, e = _board()
    _drink(s, e)
    s.acted.add("c1")
    assert e._unseen_attacker(s.actors["c1"], s.actors["pc"])
    assert not e._unseen_attacker(s.actors["pc"], s.actors["c1"])


# --- 7. out of a fight -------------------------------------------------------------------

def test_nobody_opens_a_conversation_with_a_player_they_cannot_see():
    s, e = _board(fight=False)
    _drink(s, e)
    assert e.join_talk(s.actors["c1"], how="they spoke to you") == ""
    assert e.join_talk(s.actors["c1"], how="you spoke to them"), \
        "the player speaking first is the player's call"


def test_a_newcomer_rolls_against_the_hiding_once():
    """Out of a fight, everybody here checks against the hiding at the end of the batch —
    the onlookers the opposed check did not name, and anyone who arrives — once each."""
    s, e = _board(fight=False)
    _drink(s, e)
    s.add(instantiate("thug", scene=s, name="the second thug"), at=(10, 10))
    e.run(e.validate([{"op": "narrate_only", "actor": "pc", "because": "waits"}]))
    eff = next(x for x in s.actors["pc"].effects if x.key == "invisible")
    assert set(eff.payload["checked"]) >= {"c1", "c2"}


# --- 8. the narrator ---------------------------------------------------------------------

def test_unnoticed_is_backed_while_the_player_is_hidden():
    """intents.py's stealth row cut "unnoticed" on every turn but the check's own; the
    hiding is an engine fact on every turn it holds."""
    from rules.intents import claims_held_by_hiding, find_outcome_claims

    text = "You stay unnoticed by the far wall."
    assert find_outcome_claims(text)
    assert not find_outcome_claims(text, backed=claims_held_by_hiding())


def test_the_read_back_flags_a_creature_looking_at_a_player_it_cannot_see():
    """live_npc.out: "swinging the heavy-headed sap in a desperate arc aimed at your head"
    against an invisible player, three turns running. The closed question's answer is
    compared in code with `Facts.unseen`; a search told as a search is not flagged."""
    from gm import beat_verify as bv

    s, e = _board()
    _drink(s, e)

    class Ctx:
        engine, scene, intimate, acting = e, s, False, "c1"

    assert bv._unseen_of(Ctx, s, s.actors["pc"]) == {"unseen": ("c1",)}
    facts = bv.Facts(start="", end="", places=(), people=(
        bv.Person(ref="pc", name="Kesst", pc=True), bv.Person(ref="c1", name="the thug")),
        unseen=("c1",))
    assert bv.unseen_schema(facts)["properties"]["unseen_at_you"]["items"]["properties"][
        "who"]["enum"] == ["c1", bv.NEW_PERSON]
    wrong = bv.Claim("unseen", {"who": "c1"}, "aimed at your head")
    wrong.sentence = "The thug swings the sap in an arc aimed at your head."
    wrong.valid = True
    found = bv.diff([wrong], facts, wrong.sentence)
    assert [d.category for d in found] == ["unseen"]
    assert "cannot see you" in found[0].fact
    assert bv.question(found[0], facts)


def test_the_creature_turn_call_is_told_it_cannot_see_the_player():
    from gm import planned

    s, e = _board()
    assert planned.unseen_line(e, "c1") == ""
    _drink(s, e)
    line = planned.unseen_line(e, "c1")
    assert "cannot see you" in line and line.startswith("The thug")


# --- 9. what a check pays ----------------------------------------------------------------

def test_an_opposed_check_pays_by_the_opposers_take_ten_not_their_die():
    """live_pc.out, 0.2.23: an invisible level-2 Kesst's Stealth beat a thug's Perception
    roll of 19 by 27 and was paid 300 XP. The CRB pays no XP per skill check ("Awarding
    Experience", p.399) and the owner's own rule reads a DC as a CR; an opposed check's DC
    is now the other side's 10 + modifier, and a check the player could not fail pays
    nothing (a skill check has no automatic failure, CRB p.86)."""
    s, e = _board(fight=False)
    pc = s.actors["pc"]
    assert e.reward_check(pc, "stealth", 11, modifier=29) == ""
    assert e.reward_check(pc, "climb", 15, modifier=3)
