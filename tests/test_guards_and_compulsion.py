"""Getting between a blow, and being pulled towards a target you did not choose.

Two problems this app has that a table does not.

**Interception.** Damage used to be a straight line: roll it, subtract damage reduction,
spend temporary hit points, take the rest. That line has no room in it for anything that
wants to change the blow — a Coagulator throwing themselves in front of a companion, a ward
that turns a cut into a bruise, a bloodlink that makes two creatures share what one suffers.
Blood Bending's whole Coagulator path is those three things, and not one of them is
expressible as a modifier on the attacker or a subtraction on the defender.

**Compulsion.** With one player character, nothing on the board makes a monster attack the
*right* person, because there is only one person. Blood Bending's Blood Commander path is
built on forcing that choice.

The rule the compulsion half exists to enforce, and it is a design decision rather than a
reading of 1e: **it penalises, it never prohibits.** An aggro mechanic that forbids taking
the choice away hands the fight to a number, and in this engine a prohibition would surface
as an `IntentError` — the GM's whole intent list dying because a monster wanted to do
something reasonable.

Two things interception broke on the way in, both recorded below: the tell named whoever the
blow was *aimed* at rather than whoever took it, and the hit-point state check ran on the
intended target — so a redirected blow that dropped the guardian never knocked them out.
"""
from __future__ import annotations

import pytest

from rules import compulsion, guards
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.guards import Guard, Packet
from rules.sheet import from_dict, load_pc, to_dict


def board(pc_at=(5, 5), ally_at=(6, 5), foe_at=(8, 5), mapped=True):
    s = Scene(location_id="5bbd0c40345f",
              grid=Grid(20, 20) if mapped else None)
    s.add(load_pc("fixtures/pc-kesst.json"), at=pc_at if mapped else None)
    s.add(instantiate("thug", scene=s, name="the companion"),
          at=ally_at if mapped else None)
    s.add(instantiate("thug", scene=s, name="the raider"), at=foe_at if mapped else None)
    s.sides = {"us": ["pc", "c1"], "them": ["c2"]}
    s.initiative = [("pc", 20), ("c1", 15), ("c2", 10)]
    s.turn = 0
    return s, Engine(s, Dice(seed=3))


def guard(engine, kind="redirect", protects="c1", actor="pc", **params):
    return engine.run(engine.validate([
        {"op": "guard", "actor": actor, "because": "Crimson Guard",
         "params": {"to": protects, "kind": kind, "range_ft": 10, **params}}]))


def hurt(engine, to="c1", amount=12, dtype="fire", lethality="lethal"):
    return engine.run(engine.validate([
        {"op": "damage", "actor": "c2", "because": "a hurled flask",
         "params": {"to": to, "amount": amount, "type": dtype,
                    "lethality": lethality}}]))


# --- interception: the four kinds ---------------------------------------------------------

def test_redirect_moves_the_whole_blow_to_the_guardian():
    s, e = board()
    guard(e, "redirect")
    hurt(e, amount=12)
    assert s.actors["c1"].hp == 13                       # untouched
    assert s.actors["pc"].hp == -3                       # 9 - 12


def test_share_splits_it_and_both_take_their_half():
    s, e = board()
    guard(e, "share", amount=50)
    ally_before = s.actors["c1"].hp
    hurt(e, amount=12)
    assert s.actors["pc"].hp == 3                        # 9 - 6
    assert s.actors["c1"].hp == ally_before - 6


def test_a_share_of_an_odd_number_never_costs_more_than_the_blow():
    """Rounded down to the guardian. Rounding both up would have the two of them pay 8
    between them for a 7-point hit."""
    s, e = board()
    guard(e, "share", amount=50)
    ally_before, pc_before = s.actors["c1"].hp, s.actors["pc"].hp
    hurt(e, amount=7)
    taken = (pc_before - s.actors["pc"].hp) + (ally_before - s.actors["c1"].hp)
    assert taken == 7


def test_absorb_eats_what_it_can_and_the_rest_lands():
    s, e = board()
    guard(e, "absorb", amount=8)
    ally_before = s.actors["c1"].hp
    hurt(e, amount=12)
    assert s.actors["c1"].hp == ally_before - 4
    assert s.actors["pc"].hp == 9                        # the ward paid, not the guardian


def test_absorb_can_stop_a_blow_outright():
    s, e = board()
    guard(e, "absorb", amount=20)
    ally_before = s.actors["c1"].hp
    res = hurt(e, amount=12)
    assert s.actors["c1"].hp == ally_before
    assert res.outcomes[0].effects[0]["amount"] == 0


def test_convert_turns_a_cut_into_a_bruise():
    s, e = board()
    guard(e, "convert")
    hurt(e, amount=12)
    assert s.actors["c1"].hp == 13                       # no hit points lost
    assert s.actors["c1"].nonlethal == 12


def test_convert_does_nothing_to_damage_that_is_already_non_lethal():
    """Otherwise the ward spends itself on a blow it could not improve."""
    s, e = board()
    guard(e, "convert", uses=1)
    hurt(e, amount=6, lethality="nonlethal")
    assert s.guards[0].uses_left == 1


# --- the order the pipeline runs in ---------------------------------------------------------

def test_interception_happens_before_damage_reduction():
    """A blow redirected to somebody else has to meet *that* creature's armour. Resolving
    DR first and moving the leftovers applies the wrong person's.

    Slashing rather than fire, because 1e damage reduction does not touch energy damage at
    all — a first version of this test used fire and proved nothing."""
    from rules.sheet import Reduction

    s, e = board()
    s.actors["pc"].reductions = [Reduction(amount=5, source="coagulated blood")]
    guard(e, "redirect")
    hurt(e, amount=12, dtype="slashing")
    assert s.actors["pc"].hp == 2                        # 9 - (12 - 5), the guardian's DR


def test_the_protected_creatures_reduction_is_not_the_one_that_applies():
    """The other half of the same point. If DR ran before interception, the companion's
    armour would protect the guardian."""
    from rules.sheet import Reduction

    s, e = board()
    s.actors["c1"].reductions = [Reduction(amount=5, source="thick hide")]
    guard(e, "redirect")
    hurt(e, amount=12, dtype="slashing")
    assert s.actors["pc"].hp == -3                       # the full 12, undiminished


def test_the_cheapest_intervention_goes_first():
    """A ward that can simply eat the blow does, rather than a companion needlessly
    throwing themselves in front of something harmless."""
    s, e = board()
    guard(e, "redirect")
    guard(e, "absorb", amount=20)
    hurt(e, amount=12)
    assert s.actors["pc"].hp == 9                        # absorbed; nobody interposed


def test_guards_do_not_each_get_the_full_packet():
    """Two absorbs of 10 against a 12-point hit consume 10 and 2, not 10 and 10."""
    s, e = board()
    guard(e, "absorb", amount=10)
    e.run(e.validate([{"op": "guard", "actor": "c2", "because": "a rival ward",
                       "params": {"to": "c1", "kind": "absorb", "amount": 10,
                                  "range_ft": 20}}]))
    ally_before = s.actors["c1"].hp
    hurt(e, amount=12)
    assert s.actors["c1"].hp == ally_before              # 10 + 2 eaten, nothing left


def test_two_guardians_protecting_each_other_do_not_bounce_forever():
    """Each guard gets one go at a packet. Without that, two Coagulators covering each
    other pass a blow between them until the stack runs out."""
    s, e = board()
    guard(e, "redirect", protects="c1", actor="pc")
    guard(e, "redirect", protects="pc", actor="c1")
    hurt(e, amount=6)                                    # must terminate
    assert s.actors["pc"].hp + s.actors["c1"].hp == 9 + 13 - 6


# --- who takes it, and what the player is told -----------------------------------------------

def test_the_tell_names_whoever_actually_took_it():
    """The first thing interception broke. "The companion takes 12" when a guardian threw
    themselves in front of it is a lie the player has no way to catch."""
    s, e = board()
    guard(e, "redirect")
    res = hurt(e, amount=12)
    assert "Kesst Vayr takes 12" in res.outcomes[0].tell
    assert "the companion takes" not in res.outcomes[0].tell


def test_a_shared_blow_tells_the_player_about_both_halves():
    s, e = board()
    guard(e, "share", amount=50)
    tell = hurt(e, amount=12).outcomes[0].tell
    assert "Kesst Vayr takes 6" in tell
    assert "the companion takes 6" in tell


def test_the_tell_says_the_damage_became_something_else():
    """Damage that quietly turned into something different is the most confusing thing
    that can happen to a player."""
    s, e = board()
    guard(e, "convert")
    assert "turned non-lethal" in hurt(e, amount=12).outcomes[0].tell


def test_a_redirected_blow_that_drops_the_guardian_knocks_them_out():
    """The second thing interception broke. The hit-point state check ran on the creature
    the blow was aimed at, so the guardian went to -3 and stayed on their feet."""
    s, e = board()
    guard(e, "redirect")
    res = hurt(e, amount=12)
    assert s.actors["pc"].hp == -3
    assert s.actors["pc"].has_condition("dying")
    assert {e["condition"] for e in res.outcomes[0].effects
            if e.get("kind") == "condition"} == {"unconscious", "dying"}


# --- when a guard does not apply ---------------------------------------------------------------

def test_a_guardian_out_of_range_cannot_interpose():
    s, e = board(ally_at=(15, 5))
    guard(e, "redirect", range_ft=5)
    ally_before = s.actors["c1"].hp
    hurt(e, amount=12)
    assert s.actors["c1"].hp == ally_before - 12
    assert s.actors["pc"].hp == 9


def test_a_guardian_who_cannot_act_cannot_interpose():
    s, e = board()
    guard(e, "redirect")
    s.actors["pc"].add_condition("unconscious")
    ally_before = s.actors["c1"].hp
    hurt(e, amount=6)
    assert s.actors["c1"].hp == ally_before - 6


def test_a_spent_guard_stops_applying():
    s, e = board()
    guard(e, "redirect", uses=1)
    hurt(e, amount=3)
    ally_before = s.actors["c1"].hp
    hurt(e, amount=3)
    assert s.actors["c1"].hp == ally_before - 3


def test_a_guard_works_on_a_scene_with_no_map():
    """Refusing without a grid would make the ability silently stop existing outside a
    tactical fight, which is worse than being generous about the distance."""
    s, e = board(mapped=False)
    guard(e, "redirect")
    hurt(e, amount=6)
    assert s.actors["pc"].hp == 3


def test_redeclaring_the_same_guard_renews_rather_than_stacks():
    """Two copies of one arrangement would double every absorb."""
    s, e = board()
    guard(e, "absorb", amount=8)
    guard(e, "absorb", amount=8)
    assert len(s.guards) == 1
    ally_before = s.actors["c1"].hp
    hurt(e, amount=12)
    assert s.actors["c1"].hp == ally_before - 4          # 8 eaten once, not 16


def test_an_unknown_guard_kind_is_refused_at_validation():
    """The list in `guards.KINDS` and the one validation checks going out of step is the
    failure `ACTOR_RULES` exists to prevent, one layer up."""
    from rules.intents import IntentError

    s, e = board()
    with pytest.raises(IntentError, match="kind must be one of"):
        e.validate([{"op": "guard", "actor": "pc",
                     "params": {"to": "c1", "kind": "parry"}}])


def test_damage_is_untouched_when_nobody_is_guarding():
    s, e = board()
    ally_before = s.actors["c1"].hp
    res = hurt(e, amount=12)
    assert s.actors["c1"].hp == ally_before - 12
    assert "intercepted" not in res.outcomes[0].effects[0]


# --- compulsions ---------------------------------------------------------------------------------

def test_a_compulsion_penalises_and_never_prohibits():
    """The design decision this half of the file exists for. A compelled creature may
    always swing at whoever it likes; doing so is just worse."""
    s, e = board()
    e.run(e.validate([{"op": "compel", "actor": "pc", "because": "a taunt",
                       "params": {"to": "c2", "penalty": 4}}]))
    # Not an error, not a refusal — the attack validates and resolves.
    res = e.run(e.validate([{"op": "attack", "actor": "c2", "target": "c1",
                             "because": "ignoring the taunt",
                             "params": {"full_attack": False}}]))
    assert res.outcomes[0].op == "attack"


def test_obeying_a_compulsion_costs_nothing():
    s, e = board()
    raider = s.actors["c2"]
    compulsion.add(raider, by="pc", penalty=4, source="a taunt")
    assert compulsion.penalty_against(raider, "pc") == []


def test_defying_one_costs_its_penalty():
    s, e = board()
    raider = s.actors["c2"]
    compulsion.add(raider, by="pc", penalty=4, source="a taunt")
    mods = compulsion.penalty_against(raider, "c1")
    assert [m.value for m in mods] == [-4]
    assert mods[0].source == "a taunt"


def test_the_penalty_reaches_the_attack_roll():
    """Charged in the engine rather than in `attack_modifiers`, because the penalty
    depends on who is being attacked and the sheet does not know that."""
    s, e = board()
    compulsion.add(s.actors["c2"], by="pc", penalty=4, source="a taunt")
    res = e.run(e.validate([{"op": "attack", "actor": "c2", "target": "c1",
                             "because": "defying it", "params": {"full_attack": False}}]))
    terms = res.outcomes[0].rolls[0].modifiers
    assert any(m.source == "a taunt" and m.value == -4 for m in terms)


def test_rival_compulsions_sum_when_all_are_defied():
    """Three creatures screaming for your attention and being ignored by all three is
    meaningfully worse than one, so this sums rather than taking the worst."""
    s, e = board()
    raider = s.actors["c2"]
    compulsion.add(raider, by="pc", penalty=4, source="a taunt")
    compulsion.add(raider, by="c1", penalty=2, source="a second shout")
    assert sum(m.value for m in compulsion.penalty_against(raider, "c9")) == -6


def test_satisfying_one_of_two_rivals_still_charges_the_other():
    s, e = board()
    raider = s.actors["c2"]
    compulsion.add(raider, by="pc", penalty=4, source="a taunt")
    compulsion.add(raider, by="c1", penalty=2, source="a second shout")
    assert [m.value for m in compulsion.penalty_against(raider, "pc")] == [-2]


def test_the_same_source_refreshes_rather_than_stacking():
    """Two taunts from the same enemy are one taunt shouted twice. Stacking would make the
    mechanic scale with how often the GM happened to mention it."""
    s, e = board()
    raider = s.actors["c2"]
    compulsion.add(raider, by="pc", penalty=4, source="a taunt")
    compulsion.add(raider, by="pc", penalty=4, source="a taunt")
    assert len(raider.compulsions) == 1


def test_refreshing_keeps_the_stronger_pull():
    s, e = board()
    raider = s.actors["c2"]
    compulsion.add(raider, by="pc", penalty=6, source="a taunt")
    compulsion.add(raider, by="pc", penalty=2, source="a taunt")
    assert raider.compulsions[0].penalty == 6


def test_a_compulsion_counts_down_and_ends():
    s, e = board()
    raider = s.actors["c2"]
    compulsion.add(raider, by="pc", penalty=4, rounds=2, source="a taunt")
    # Through the one ticker. `compulsion.tick` is gone: a compulsion expires with
    # everything else now, so it counts down on every clock rather than only on the
    # combat rollover — which is why one applied out of a fight used to last until the
    # next fight began.
    assert raider.tick_effects(1) == []
    assert raider.tick_effects(1) == ["a taunt"]
    assert raider.compulsions == []


def test_one_with_no_duration_does_not_expire():
    s, e = board()
    raider = s.actors["c2"]
    compulsion.add(raider, by="pc", penalty=4, source="a bloodlink")
    raider.tick_effects(50)
    assert len(raider.compulsions) == 1


def test_the_tell_says_what_defying_it_costs():
    """"The thug is compelled" tells a player nothing they can act on."""
    s, e = board()
    res = e.run(e.validate([{"op": "compel", "actor": "pc", "because": "a taunt",
                             "params": {"to": "c2", "penalty": 4,
                                        "duration": {"amount": 3, "unit": "round"}}}]))
    assert "to attack anyone else" in res.outcomes[0].tell
    assert "3 rounds" in res.outcomes[0].tell


def test_a_negative_penalty_is_read_as_how_bad_rather_than_double_negated():
    """Stored positive and applied negative, because a stored -4 gets double-negated by
    somebody eventually."""
    s, e = board()
    e.run(e.validate([{"op": "compel", "actor": "pc", "because": "a taunt",
                       "params": {"to": "c2", "penalty": -4}}]))
    assert [m.value for m in compulsion.penalty_against(s.actors["c2"], "c1")] == [-4]


# --- persistence ---------------------------------------------------------------------------------

def test_compulsions_survive_a_save():
    a = load_pc("fixtures/pc-kesst.json")
    compulsion.add(a, by="c2", penalty=4, rounds=3, source="a taunt", why="bloodlink")
    back = from_dict(to_dict(a)).compulsions
    assert len(back) == 1
    assert (back[0].by, back[0].penalty, back[0].rounds_left) == ("c2", 4, 3)
    assert back[0].source == "a taunt"


def test_guards_survive_a_save(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path)
    from play import campaign as campaign_mod

    c = campaign_mod.begin_with(load_pc("fixtures/pc-kesst.json"))
    c.scene.guards = [Guard(guardian="pc", protects="c1", kind="absorb", amount=8,
                            range_ft=10, uses_left=2, source="Blood Sponge")]
    c.save()

    back = campaign_mod.Campaign.load(c.path()).scene.guards
    assert len(back) == 1
    assert (back[0].kind, back[0].amount, back[0].uses_left) == ("absorb", 8, 2)


def test_a_save_from_before_either_existed_still_loads(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path)
    from play import campaign as campaign_mod

    c = campaign_mod.begin_with(load_pc("fixtures/pc-kesst.json"))
    c.save()
    back = campaign_mod.Campaign.load(c.path())
    assert back.scene.guards == []
    assert back.scene.pc().compulsions == []


# --- the pipeline on its own -----------------------------------------------------------------------

def test_intercept_can_return_more_than_one_packet():
    """Callers must handle it. Assuming exactly one back is the mistake the return type
    exists to prevent."""
    s, _ = board()
    s.guards = [Guard(guardian="pc", protects="c1", kind="share", amount=50, range_ft=99)]
    out = guards.intercept(s, Packet(amount=10, target="c1"))
    assert sorted(p.target for p in out) == ["c1", "pc"]


def test_intercept_can_return_nothing_at_all():
    s, _ = board()
    s.guards = [Guard(guardian="pc", protects="c1", kind="absorb", amount=50,
                      range_ft=99)]
    assert all(p.amount == 0 for p in guards.intercept(s, Packet(amount=10, target="c1")))


def test_a_ward_that_eats_a_blow_whole_says_so():
    """"hits for 0" is technically true and reads as a miss. A ward that stopped the blow
    is a thing that happened, and the player paid for it. An early version printed the
    developer docstring for the guard kind straight into the narration — backticks and
    all — which is the same failure in the other direction."""
    s, e = board()
    guard(e, "absorb", amount=20)
    tell = hurt(e, amount=12).outcomes[0].tell
    assert "nothing reaches the companion" in tell
    assert "absorbed by Crimson Guard" in tell
    assert "takes 0" not in tell


def test_the_guard_tell_is_written_for_a_player():
    s, e = board()
    tell = guard(e, "absorb", amount=8).outcomes[0].tell
    assert "steps in front of the companion" in tell
    assert "`" not in tell and "amount" not in tell


def test_a_compulsion_expires_out_of_combat():
    """Its only ticker was the combat rollover, so a compulsion applied outside a fight
    lasted until the next fight started — however many hours or days passed. It is an
    effect now and expires on every clock."""
    s, e = board()
    raider = s.actors["c2"]
    compulsion.add(raider, by="pc", penalty=4, rounds=10, source="a taunt")
    was_round = s.round
    s.advance(1)                       # one minute of world time, no turn taken
    assert s.round == was_round, "no round was played; only the clock moved"
    assert raider.compulsions == []


def test_the_penalty_is_not_a_modifier_and_must_not_become_one():
    """The trap in the obvious implementation. Authoring the -4 as a `combat_mod` so it
    flows through the one funnel INVERTS the mechanic: `_buff_mods` has no notion of
    whom you are attacking, so the penalty would apply to every swing including the one
    that obeys — and "obeying is free" is the whole design of this module."""
    s, e = board()
    raider = s.actors["c2"]
    compulsion.add(raider, by="pc", penalty=4, source="a taunt")
    held = [x for x in raider.effects if x.kind == "compulsion"]
    assert held and all(not x.modifiers for x in held)
    assert not any(m.source == "a taunt" for m in raider.attack_modifiers())
    assert compulsion.penalty_against(raider, "pc") == []
    assert [m.value for m in compulsion.penalty_against(raider, "c1")] == [-4]


def test_a_compulsion_survives_a_save():
    from rules.sheet import from_dict, to_dict

    s, e = board()
    raider = s.actors["c2"]
    compulsion.add(raider, by="pc", penalty=6, rounds=5, source="a bloodlink")
    back = from_dict(to_dict(raider), ref="c2")
    assert [(c.by, c.penalty, c.rounds_left) for c in back.compulsions] == [("pc", 6, 5)]
    # and a reload does not double them
    twice = from_dict(to_dict(back), ref="c2")
    assert len(twice.compulsions) == 1
