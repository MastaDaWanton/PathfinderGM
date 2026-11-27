"""Feat loop batch 5, lane b5-other (2026-11-26): the meditation line, luck that takes 10
or is lent, Wind Stance and Nimble Moves on the board, the social openings and the teamwork
leftovers, proved through the engine.

Before this lane, measured on integrate/feats-b4 e3c9d166: none of these feats had a
document but Body Control, Bestow Luck and Nimble Moves, and each of those three carried a
`not_yet`; Combat Meditation's use could not roll twice; nothing let a player take 10 on a
check; a 20% miss chance could not be scoped to ranged attacks; and Acrobatic Steps'
allowance came back on every move of the round.
"""
from __future__ import annotations

import json
from pathlib import Path

from rules import classbuilder, luck, survival
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Scene, Engine
from tests.test_feats_b2_styles import Faces, _luck_pc, _save
from tests.test_feats_b4_moves import _attack, _board, _pc, _run, _tells

LANE = Path("content/feats/mechanics/b5-other.json")


def test_the_lane_file_validates():
    doc = json.loads(LANE.read_text("utf-8"))
    assert classbuilder.validate_feat_documents(
        {k: v for k, v in doc.items() if not k.startswith("_")}) == []


def _held_by(pc, tag):
    pc.apply_effect(ActiveEffect(name=tag, kind="buff", key=tag, source="test",
                                 origin="author:test", duration="rounds", rounds_left=5,
                                 tags=(tag,)))


# --- Wind Stance, Nimble Moves ---------------------------------------------------------------

def test_wind_stance_conceals_against_ranged_blows_only_after_a_walk_past_five_feet():
    """CRB: "If you move more than 5 feet this turn, you gain 20% concealment for 1 round
    against ranged attacks." A miss chance could not be scoped to ranged blows before this
    lane (`Actor.concealment` read no context): a 5-foot step lays nothing; a 15-foot walk
    lays 20% that a bow meets and a sword does not."""
    pc = _pc("fighter", feats=["Wind Stance"])
    s, e = _board(pc, ("thug", (18, 18)))
    _run(e, {"op": "move", "actor": "pc", "params": {"square": [6, 5]}})
    assert e._concealment_of(s.actors["c1"], pc, ranged=True)[0] == 0
    res = _run(e, {"op": "move", "actor": "pc", "params": {"square": [9, 5]}})
    assert "Wind Stance" in _tells(res)
    assert e._concealment_of(s.actors["c1"], pc, ranged=True)[0] == 20
    assert e._concealment_of(s.actors["c1"], pc, ranged=False)[0] == 0
    assert e._concealment_of(s.actors["c1"], pc)[0] == 0


def test_nimble_moves_and_acrobatic_steps_give_twenty_feet_a_round_not_a_move():
    """CRB Acrobatic Steps: "The effects of this feat stack with those provided by Nimble
    Moves (allowing you to move normally through a total of 20 feet of difficult terrain
    each round)". Measured before: Nimble Moves had no term (15 ft, not 20) and the allowance
    came back for the second move of the same round. A walk across bramble spends it until
    the walker's next turn; a walk on open ground spends nothing."""
    pc = _pc("fighter", feats=["Nimble Moves", "Acrobatic Steps"])
    s, e = _board(pc, ("thug", (18, 18)))
    assert e._easy_ft(pc) == 20
    _run(e, {"op": "move", "actor": "pc", "params": {"square": [5, 7]}})
    assert e._easy_ft(pc) == 20                 # open ground: nothing spent
    s.grid.difficult = {(x, 7) for x in range(6, 10)}
    _run(e, {"op": "move", "actor": "pc", "params": {"square": [9, 7]}})
    assert e._easy_ft(pc) == 0
    pc.tick_effects(1)
    assert e._easy_ft(pc) == 20


def test_nimble_moves_alone_is_five_feet():
    pc = _pc("fighter", feats=["Nimble Moves"])
    s, e = _board(pc, ("thug", (18, 18)))
    assert e._easy_ft(pc) == 5 and pc.has_state("move.step.difficult")


# --- the meditation line ---------------------------------------------------------------------

def _meditated(*feats):
    from rules.dice import Dice as _D

    scene, engine, pc = _luck_pc("Meditation Master", *feats)
    pc.sleep_through("night", _D(seed=1))
    return scene, engine, pc


def test_combat_meditation_rolls_twice_for_meditation_master_s_plus_one():
    """F&P: "expend the +1 insight bonus granted from the Meditation Master feat to instead
    roll twice ... taking the better of the two results. You must decide to use this ability
    before the initial roll is made." Offered before the throw; taken, the +1's use is spent
    and the better die stands (the player's 3, the engine's 17)."""
    scene, engine, pc = _meditated("Combat Meditation")
    first = _save(engine, "pc").awaiting
    offer = next(o for o in first["luck"] if o["id"] == "combat-meditation")
    assert offer["when"] == "before" and "twice" in offer["text"].lower()
    engine.dice = Faces([17], match="second die")
    done = engine.resume(3, luck="combat-meditation")
    while done.awaiting:
        done = engine.resume(int(done.awaiting.get("luck_face") or 10), luck="keep")
    roll = next(o for o in done.outcomes if o.op == "save").rolls[0]
    assert roll.natural == 17
    doc, entry = luck.find(pc, "meditation-master", "bonus")
    assert luck.uses_left(pc, doc, entry) == 0


def test_combat_meditation_offers_nothing_without_the_meditation():
    scene, engine, pc = _luck_pc("Meditation Master", "Combat Meditation")
    first = _save(engine, "pc").awaiting
    assert not any(o["id"] == "combat-meditation" for o in first.get("luck") or ())


def _monk_meditates(*feats, level=8):
    from tests.test_feats_b2_attack_a import _use
    from tests.test_feats_b4_maneuver import _bout, _monk

    monk = _monk(["Meditation Master", "Combat Meditation", *feats])
    monk.level = level
    scene, e, thug = _bout(monk)
    out = _use(e, "Combat Meditation")
    return monk, scene, e, out


def test_meditative_concentration_is_four_on_concentration_after_a_combat_meditation():
    """F&P: "For 1 round per character level after you perform combat meditation ... a
    concentration check to avoid losing a spell or a Fortitude save to resist a distraction
    effect ... +4". The night's meditation (`meditation.held`) is not combat meditation, so
    only the combat one (`meditation.held.combat`) carries it."""
    scene, engine, pc = _meditated("Combat Meditation", "Meditative Concentration")
    assert sum(m.value for m in pc.concentration_modifiers({})
               if m.source == "Meditative Concentration") == 0
    monk, s, e, _ = _monk_meditates("Meditative Concentration")
    assert sum(m.value for m in monk.concentration_modifiers({})
               if m.source == "Meditative Concentration") == 4
    assert sum(m.value for m in monk.save_modifiers("fort", {"against": ("distraction",)})
               if m.source == "Meditative Concentration") == 4
    assert sum(m.value for m in monk.save_modifiers("fort")
               if m.source == "Meditative Concentration") == 0


def test_a_swarm_s_distraction_save_is_against_distraction():
    """The save the swarm's distraction calls for says what it is (`origin_name`), so the
    +4 reaches it: before this lane that save carried no `against` at all."""
    monk, s, e, _ = _monk_meditates("Meditative Concentration")
    res = e.run(e.validate([{"op": "save", "actor": "pc", "visibility": "hidden",
                             "params": {"save": "fort", "dc": 12,
                                        "on_failure": {"condition": "nauseated", "rounds": 1}}}],
                           origin="creature:spider-swarm", origin_name="distraction"))
    roll = next(o for o in res.outcomes if o.op == "save").rolls[0]
    assert any(m.source == "Meditative Concentration" and m.value == 4
               for m in roll.modifiers)


def test_slow_time_hastes_the_combat_meditation_once_a_day():
    """F&P: "Once per day, when you meditate ... using the Combat Meditation feat, you gain
    the effects of haste for 1 round per 2 character levels." Level 8: 4 rounds of +1 to
    hit, +1 dodge AC; the second meditation that day brings none."""
    monk, s, e, out = _monk_meditates("Slow Time")
    haste = [x for x in monk.effects if x.name == "Slow Time"]
    assert haste and haste[0].rounds_left == 4, out.tell
    assert {(m["target"], m["amount"]) for m in haste[0].modifiers} >= {("attack", 1), ("ac", 1)}
    from tests.test_feats_b2_attack_a import _use

    monk.remove_effects(match=lambda x: x.name == "Slow Time")
    _use(e, "Combat Meditation")
    assert not [x for x in monk.effects if x.name == "Slow Time"]


def test_perfect_center_offers_the_player_ten_and_takes_it():
    """F&P: "You can take 10 on any skill check or concentration check". Nothing let a
    player take 10 on a check before this lane. The popup offers it; taken, the die is
    set aside and 10 stands, whatever face was thrown."""
    scene, engine, pc = _luck_pc("Perfect Center")
    res = engine.run(engine.validate([{"op": "check", "actor": "pc", "visibility": "player",
                                       "params": {"skill": "perception", "dc": 12}}]))
    offer = next(o for o in res.awaiting["luck"] if o["id"] == "perfect-center")
    assert offer["kind"] == "take_ten"
    done = engine.resume(2, luck="perfect-center")
    roll = next(o for o in done.outcomes if o.op == "check").rolls[0]
    assert roll.natural == 10


def test_perfect_center_lets_anybody_else_take_ten_when_ten_makes_it():
    scene, engine, pc = _luck_pc()
    thug = instantiate("thug", scene=scene, name="the thug")
    thug.feats += ["Perfect Center"]
    scene.add(thug)
    engine.dice = Faces([1])
    res = engine.run(engine.validate([{"op": "check", "actor": thug.ref,
                                       "visibility": "hidden",
                                       "params": {"skill": "perception", "dc": 5}}]))
    roll = next(o for o in res.outcomes if o.op == "check").rolls[0]
    assert roll.natural == 10 and "takes 10" in _tells(res)


# --- luck lent, the body's needs -------------------------------------------------------------

def test_bestow_luck_lends_inexplicable_luck_to_an_ally_short_by_four():
    """ARG: "use your Inexplicable Luck ability to grant an ally that can see and hear its
    benefit". Measured before: "a creature's luck reaches only its own d20". A companion
    one short of a save takes the lender's +4, and the lender's use is spent."""
    scene, engine, pc = _luck_pc("Inexplicable Luck", "Defiant Luck", "Bestow Luck")
    friend = instantiate("thug", scene=scene, name="the friend")
    scene.add(friend)
    scene.sides = {"pc": ["pc", friend.ref], "them": []}
    need = 10 + sum(m.value for m in friend.save_modifiers("will")) + 2
    engine.dice = Faces([10])
    res = _save(engine, friend.ref, dc=need, vis="hidden")
    assert next(o for o in res.outcomes if o.op == "save").verdict == "success"
    assert "lends" in _tells(res)
    doc, entry = luck.find(pc, "inexplicable-luck", "bonus")
    assert luck.uses_left(pc, doc, entry) == 0


def test_body_control_halves_food_and_water_and_steels_against_fatigue():
    """F&P: "+1 ... against ... effects that would make you fatigued or exhausted. You need
    only half as much food ... half as much water". Before: "a save does not say what its
    failure would leave" and the body's needs were fixed."""
    scene, engine, pc = _meditated("Body Control")
    assert survival.daily_need(pc, "water") == survival.daily_need(
        _luck_pc()[2], "water") / 2
    res = engine.run(engine.validate([{"op": "save", "actor": "pc", "visibility": "hidden",
                                       "params": {"save": "fort", "dc": 12, "on_failure": {
                                           "condition": "fatigued", "rounds": 10}}}],
                                     origin="author:test"))
    roll = next(o for o in res.outcomes if o.op == "save").rolls[0]
    assert any(m.source == "Body Control" and m.value == 1 for m in roll.modifiers)


# --- the social openings ---------------------------------------------------------------------

def test_betrayer_opens_a_friend_made_by_diplomacy_to_a_flat_footed_blow():
    """UC: "If you changed your target's attitude to friendly or better, your target is
    considered flat-footed against this attack ... -2 penalty on its initiative check"."""
    scene, engine, pc = _luck_pc("Betrayer")
    mark = instantiate("thug", scene=scene, name="the mark")
    scene.add(mark)
    engine._sway(pc, mark, "diplomacy", 10, "test")
    assert mark.has_state("state.exposed.betrayed") and mark.loses_dex_to_ac
    assert sum(m.value for m in mark._buff_mods("combat_mod", "initiative")) == -2
    other = instantiate("thug", scene=scene, name="the other")
    scene.add(other)
    plain = _luck_pc()[2]
    engine._sway(plain, other, "diplomacy", 10, "test")
    assert not other.has_state("betrayed.open")


def _social(feats, held=False):
    scene, engine, pc = _luck_pc(*feats)
    pc.ranks = {**pc.ranks, "bluff": 1}
    mark = instantiate("thug", scene=scene, name="the mark")
    scene.add(mark)
    if held:
        pc.add_condition("grappled", 10, source="test")
    return scene, engine, pc, mark


def _use_on(engine, name, to):
    return engine.run(engine.validate([{"op": "use_ability", "actor": "pc",
                                        "because": "test",
                                        "params": {"ability": name, "to": to}}])).outcomes[-1]


def test_rhetorical_flourish_won_is_four_on_diplomacy_with_that_creature_only():
    """UC: "If you succeed, you gain a +4 bonus on your next Diplomacy check against that
    creature ... If you fail by 5 or more, you instead take a -2 penalty"."""
    scene, engine, pc, mark = _social(["Rhetorical Flourish"])
    engine.dice = Faces([20, 1], match="")
    out = _use_on(engine, "Rhetorical Flourish", mark.ref)
    assert "beats" in out.tell, out.tell
    on_mark = sum(m.value for m in pc.skill_modifiers("diplomacy", ctx={"target_actor": mark})
                  if "Rhetorical" in m.source)
    assert on_mark == 4
    assert sum(m.value for m in pc.skill_modifiers("diplomacy")
               if "Rhetorical" in m.source) == 0
    scene, engine, pc, mark = _social(["Rhetorical Flourish"])
    engine.dice = Faces([1, 20], match="")
    out = _use_on(engine, "Rhetorical Flourish", mark.ref)
    assert sum(m.value for m in pc.skill_modifiers("diplomacy", ctx={"target_actor": mark})
               if "Rhetorical" in m.source) == -2, out.tell


def test_helpless_prisoner_needs_bonds_and_buys_five_on_escape_artist():
    """GoG: "When you are restrained or imprisoned ... a Bluff check against any one
    creature within 30 feet ... +5 bonus on your next Escape Artist check"."""
    scene, engine, pc, mark = _social(["Helpless Prisoner"])
    out = _use_on(engine, "Helpless Prisoner", mark.ref)
    assert "held" in out.tell, out.tell
    scene, engine, pc, mark = _social(["Helpless Prisoner"], held=True)
    engine.dice = Faces([20, 1], match="")
    out = _use_on(engine, "Helpless Prisoner", mark.ref)
    assert sum(m.value for m in pc.skill_modifiers("escape artist")
               if "Helpless Prisoner" in m.source) == 5, out.tell


def test_osyluth_guile_is_charisma_dodge_against_one_foe_s_melee_while_defending():
    """Osyluth Guile: "While you are fighting defensively or using the total defense action,
    select one opponent. Add your Charisma bonus to your AC as a dodge bonus against that
    opponent's melee attacks"."""
    pc = _pc("fighter", feats=["Osyluth Guile"])
    s, e = _board(pc, ("thug", (6, 5)), ("thug", (4, 5)))
    out = _use_on(e, "Osyluth Guile", "c1")
    assert "fighting defensively" in out.tell
    _held_by(pc, "buff.stance.total-defense")
    _use_on(e, "Osyluth Guile", "c1")
    cha = pc.ability_mod("cha")
    vs = sum(m.value for m in pc._buff_mods("combat_mod", "ac", pc._ac_context(
        "melee", s.actors["c1"])) if m.source.startswith("Osyluth"))
    other = sum(m.value for m in pc._buff_mods("combat_mod", "ac", pc._ac_context(
        "melee", s.actors["c2"])) if m.source.startswith("Osyluth"))
    shot = sum(m.value for m in pc._buff_mods("combat_mod", "ac", pc._ac_context(
        "ranged", s.actors["c1"])) if m.source.startswith("Osyluth"))
    assert (vs, other, shot) == (cha, 0, 0)


# --- teamwork --------------------------------------------------------------------------------

def test_ferocious_loyalty_against_a_foe_threatening_a_loyal_ally_then_two_when_they_fall():
    """Blood of the Moon: "+1 morale bonus on attack rolls against any foe that currently
    threatens an ally who also has this feat. Whenever an ally with this feat is rendered
    helpless or killed within 30 feet of you, you gain a +2 morale bonus on attack rolls
    for 1 minute or until the foe responsible is rendered helpless or killed"."""
    from rules.sheet import situation_of  # noqa: F401 - the moment is the engine's

    ally = _pc("fighter", feats=["Ferocious Loyalty"])
    ally.ref, ally.kind, ally.name = "ally", "npc", "Ally"
    pc = _pc("fighter", feats=["Ferocious Loyalty"])
    s, e = _board(pc, ("thug", (12, 5)), allies=[(ally, (11, 5))])
    thug = s.actors["c1"]
    s.positions["pc"] = (10, 5)
    res = _attack(e)
    swing = next(r for o in res.outcomes for r in o.rolls if (r.label or "").startswith(
        "Attack"))
    assert any(m.source == "Ferocious Loyalty" and m.value == 1 for m in swing.modifiers)
    from rules import feat_events

    ally.hp = -5
    ally.add_condition("unconscious", 10, source="test")
    feat_events._ferocious_loyalty(e, thug, ally)
    held = [x for x in pc.effects if x.origin == feat_events.LOYAL_ORIGIN]
    assert held and held[0].rounds_left == 10
    thug.add_condition("unconscious", 10, source="test")
    feat_events._ferocious_loyalty(e, pc, thug)
    assert not [x for x in pc.effects if x.origin == feat_events.LOYAL_ORIGIN]


def test_brewmaster_is_two_on_the_alchemist_s_bench_check_only():
    """ARG: "+2 bonus on Craft (alchemy)" — the alchemist's bench check is the game's
    Craft (alchemy); the forge's check gets nothing."""
    from rules import alchemist, tradecraft

    scene, engine, pc = _luck_pc("Brewmaster")
    terms = alchemist.check_terms(pc, 1)
    assert {"label": "Brewmaster", "value": 2} in terms
    forge = tradecraft.bench_check_terms(pc, 1, track="blacksmith", name="Blacksmith",
                                         ability="str")
    assert not any(t["label"] == "Brewmaster" for t in forge)
