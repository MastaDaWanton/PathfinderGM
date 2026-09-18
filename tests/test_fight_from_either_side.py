"""The fight is the engine's, from either side.

The 2026-09-18 play-test (docs/playtest-2026-09-18.md, items 13a, 14, 16, 17, 18, 19),
measured off the `masta` save: a man drew on the player and lunged — "he lunges, the
blade whistling through the air as he tries to overwhelm your guard" — and the engine
rolled nothing, because the only door into an encounter from the world's side was the
model's own `begin_encounter` op. He was never on the board either: introduced as "the
man in the leather apron", the cast ledger kept "man", found "desperate man" already
booked, and skipped him. "I strike the weapon and sunder it" then died five times on
"a sunder needs a target" and the misaim repair spawned a THUG NAMED "weapon", 13 hp,
which the player killed for XP. The sunder that did land rolled no damage: the table's
`damages_item` flag was read by nothing. Seven bystanders promoted from prose were all
fightable targets and candidates for "him", so a 4-hp boy died to a thrown chunk of
wood; the death backstop then appended a second death after a beat that had already laid
him in the dirt, and a pebble took a head off. And the NPC's miss reached the page as
"Your blade whistles through the air".
"""
from __future__ import annotations

import pytest

from gm import judgement, narration
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, IntentError, Scene
from rules.sheet import load_pc


@pytest.fixture
def market():
    """The player, a bystander merchant, and nobody else — the ring before the man
    in the apron arrives."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    merchant = instantiate("guildhand", scene=s, name="nearby merchant")
    s.add(merchant, zone="near")
    merchant.add_condition("bystander", source="introduced by the scene")
    return s


# --- 16(b): the second man is booked -------------------------------------------------------

def test_a_second_man_with_a_different_description_is_a_second_person(market):
    """"the man in the leather apron" beside "desperate man": before, the head word
    "man" was already taken and he was skipped; "the man" alone is still the same man."""
    market.cast = [{"who": "desperate man", "turn": 1}]
    added = judgement.note_cast(
        market, "The man in the leather apron laughs and steps forward. The man "
                "plants his feet.", turn=2)
    assert added == ["man in the leather apron"]
    # A bare repeat of a booked head is not a third man.
    assert judgement.note_cast(market, "The man spits.", turn=3) == []
    # And the description stops at the noun: no verb is booked as part of a name.
    added = judgement.note_cast(market, "A woman in the doorway watches you.", turn=3)
    assert added == ["woman in the doorway"]


def test_promoted_people_are_bystanders_and_not_targets(market):
    added = judgement.note_cast(market, "A boy darts between the stalls.", turn=1)
    made = judgement.promote_cast(market, added)
    assert made == ["boy"]
    boy = next(a for a in market.actors.values() if a.name == "boy")
    assert boy.has_state("role.bystander")
    assert not judgement._can_be_fought(boy)
    # Two civilians in the room, nobody engaged: an untargeted attack stays untargeted
    # rather than landing on either of them.
    raw = [{"op": "attack", "actor": "pc"}]
    assert judgement.fill_obvious_targets(raw, market)[0].get("target") is None


def test_the_promotion_cap_counts_standing_civilians_not_ledger_entries(market):
    """The ledger is cleared after every fight and the actors were not, so the cap
    restarted at zero while nine non-player actors stood on a five-by-five board."""
    for n in range(judgement._PROMOTED_CAP - 1):
        a = instantiate("guildhand", scene=market, name=f"trader {n}")
        market.add(a)
        a.add_condition("bystander")
    market.cast = []                      # as after a fight
    added = judgement.note_cast(market, "A porter and a scribe hurry past.", turn=1)
    made = judgement.promote_cast(market, added)
    assert len(made) == 0, "the cap is about the bodies standing, not the ledger"


# --- 16(a): the fight opens on THEIR swing -----------------------------------------------

BEAT_31 = ("The man in the leather apron laughs. He plants his feet, the leather of his "
           "apron creaking as he coils his muscles, waiting for you to bridge the gap "
           "between the words and the steel. 'Step up, then,' he growls.")
BEAT_33 = ("The smithy's apprentice freezes, his face twisting into fury. He takes a step "
           "forward. 'Is that the best you've got?' he growls. He doesn't wait for an "
           "answer; he lunges, the blade whistling through the air as he tries to "
           "overwhelm your guard with a heavy, horizontal sweep. What do you do?")


def test_the_beat_that_swings_names_its_striker_and_the_beat_that_waits_does_not(market):
    judgement.promote_cast(market, judgement.note_cast(market, BEAT_31, turn=1))
    apron = next(a for a in market.actors.values() if "apron" in a.name)
    assert judgement.attacked_by(market, BEAT_31) == [], "coiling and waiting is not a blow"
    struck = judgement.attacked_by(
        market, "The man in the leather apron lunges at you with the blade.")
    assert [r for r, _ in struck] == [apron.ref]
    # A pronoun's striker is the last person the beat named before it.
    struck = judgement.attacked_by(
        market, "The man in the leather apron steps in. " + BEAT_33.split(". ", 1)[1])
    assert [r for r, _ in struck] == [apron.ref]
    # Speech is not action, and a threat is not a blow.
    assert judgement.attacked_by(
        market, "The man in the leather apron says, 'I'll strike you down.' He threatens "
                "to lunge at you.") == []


def test_struck_first_opens_the_fight_from_their_side_and_rolls_their_blow(market):
    judgement.promote_cast(market, judgement.note_cast(market, BEAT_31, turn=1))
    apron = next(a for a in market.actors.values() if "apron" in a.name)
    merchant = next(a for a in market.actors.values() if a.name == "nearby merchant")
    engine = Engine(market, Dice(seed=7))
    outs = engine.struck_first(apron.ref)

    assert market.in_encounter and market.grid is not None
    # The fight is between him and the player; the merchant is still a bystander.
    assert market.sides == {"pc": ["pc"], "them": [apron.ref]}
    assert merchant.ref not in market.initiative_refs() if hasattr(market, "initiative_refs") \
        else all(r != merchant.ref for r, _ in market.initiative)
    assert merchant.has_state("role.bystander") and not apron.has_state("role.bystander")
    # Two outcomes: battle joined, then his swing — rolled, not deferred to the player.
    assert any("Battle is joined" in o.tell for o in outs)
    swung = [o for o in outs if o.rolls]
    assert swung and apron.name in swung[0].tell
    assert not market.awaiting, "an NPC's die is never the player's popup"
    # Nothing opens twice, and nothing opens on a body.
    assert engine.struck_first(apron.ref) == []


# --- 16(c): a thing is not a person ----------------------------------------------------------

def test_a_strike_at_the_weapon_is_a_sunder_on_its_holder(market):
    judgement.promote_cast(market, judgement.note_cast(market, BEAT_31, turn=1))
    apron = next(a for a in market.actors.values() if "apron" in a.name)
    # The player waited for him, so the thread is bound to him.
    judgement.update_thread(market, "I wait for a challenger")
    assert market.thread.get("subject")
    judgement.bind_thread(market, [apron.ref])
    assert market.thread.get("ref") == apron.ref

    text = "I strike the weapon and sunder it"
    assert judgement.repair_misaimed_attack([{"op": "attack", "actor": "pc"}], text,
                                            market) is None, "never a victim called weapon"
    fixed = judgement.aim_at_the_holder([{"op": "attack", "actor": "pc"}], text, market)
    assert fixed[0]["target"] == apron.ref
    assert fixed[0]["params"]["manoeuvre"] == "sunder"
    assert judgement.names_a_thing("weapon") and judgement.names_a_thing("the heavy club")
    assert not judgement.names_a_thing("desperate man")


def test_a_spawn_named_after_a_thing_is_refused_with_the_fix_named(market):
    engine = Engine(market, Dice(seed=1))
    with pytest.raises(IntentError) as err:
        engine.validate([{"op": "spawn", "params": {"template": "thug", "count": 1,
                                                    "name": "weapon"}}])
    assert "is a thing, not a person" in str(err.value)
    assert "person holding" in str(err.value)
    # A person is still spawned.
    engine.validate([{"op": "spawn", "params": {"template": "thug", "count": 1,
                                                "name": "scarred man"}}])


# --- 14: the engagement is bound, and the plan's target is held to it ----------------------

def test_the_thread_binds_to_the_one_promoted_challenger_and_survives_the_fight(market):
    judgement.update_thread(market, "I wait for a challenger")
    assert market.thread["subject"] == "a challenger" and not market.thread.get("ref")
    added = judgement.note_cast(market, "A desperate man pushes to the front.", turn=2)
    judgement.promote_cast(market, added)
    challenger = next(a for a in market.actors.values() if a.name == "desperate man")
    assert market.thread["ref"] == challenger.ref
    judgement.update_thread(market, "I tell him to come at me")
    assert market.thread["ref"] == challenger.ref
    judgement.update_thread(market, "I strike", ["begin_encounter", "attack"])
    assert market.thread == {"opponent": challenger.ref}, "the fight keeps its opponent"
    assert judgement.engaged_refs(market) == [challenger.ref]


def test_an_attack_aimed_off_the_engaged_man_is_moved_back_onto_him(market):
    stranger = instantiate("guildhand", scene=market, name="the stranger sharing the step")
    market.add(stranger)
    added = judgement.note_cast(market, "A desperate man steps up.", turn=1)
    judgement.promote_cast(market, added)
    challenger = next(a for a in market.actors.values() if a.name == "desperate man")
    judgement.update_thread(market, "I wait for a challenger")
    judgement.bind_thread(market, [challenger.ref])
    raw = [{"op": "attack", "actor": "pc", "target": stranger.ref,
            "because": "you strike his weapon"}]
    fixed = judgement.check_the_target(raw, "I strike his weapon", market)
    assert fixed[0]["target"] == challenger.ref
    assert "engaged with desperate man" in fixed[0]["because"]
    # Naming the stranger is the player's call, and is never second-guessed.
    assert judgement.check_the_target(raw, "I attack the stranger", market) is raw


def test_two_live_foes_and_no_name_hands_the_question_back(market):
    a = instantiate("thug", scene=market, name="the challenger with the spiked club")
    b = instantiate("thug", scene=market, name="the stranger sharing the step")
    market.add(a)
    market.add(b)
    engine = Engine(market, Dice(seed=3))
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"pc": ["pc"], "them": [a.ref, b.ref]}}}]))
    civilian = next(x for x in market.actors.values() if x.name == "nearby merchant")
    raw = [{"op": "attack", "actor": "pc", "target": civilian.ref}]
    fixed = judgement.check_the_target(raw, "I hit him", market)
    assert sorted(fixed[0]["params"]["undecided"]) == sorted([a.ref, b.ref])
    res = engine.run(engine.validate(fixed))
    assert "Which of them" in res.outcomes[0].tell and "Say who" in res.outcomes[0].tell
    assert civilian.hp == civilian.hp_max


# --- 13(a): sunder rolls damage against the item and the tell names its state ---------------

def test_a_sunder_damages_the_item_through_hardness_and_says_what_became_of_it(market):
    """Core Rulebook, Sunder: "you deal damage to the item normally. Damage that exceeds
    the object's Hardness is subtracted from its hit points … equal to or less than
    half its total hit points remaining, it gains the broken condition … less than 0
    hit points, you can choose to destroy it." Before this the table's `damages_item`
    flag was read by nothing: the tell said "you damage an item", no die was rolled and
    the club took nothing."""
    thug = instantiate("thug", scene=market, name="the challenger")
    market.add(thug)
    pc = market.pc()
    engine = Engine(market, Dice(seed=11))
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"pc": ["pc"], "them": [thug.ref]}}}]))
    # The NPC sunders the player's rapier: hidden dice, so the whole thing resolves.
    landed = None
    for seed in range(1, 40):
        engine.dice = Dice(seed=seed)
        before = pc.item("rapier").hp
        res = engine.run(engine.validate([{"op": "attack", "actor": thug.ref, "target": "pc",
                                           "params": {"manoeuvre": "sunder"}}]))
        out = res.outcomes[0]
        if out.verdict == "success":
            landed = (out, before)
            break
    assert landed, "no seed landed a sunder in forty tries"
    out, before = landed
    assert "you damage an item" not in out.tell
    assert "rapier takes" in out.tell and "through hardness" in out.tell
    dmg = [e for e in out.effects if e.get("kind") == "item_damage"]
    assert dmg and dmg[0]["item"] == "rapier" and dmg[0]["owner"] == "pc"
    assert len(out.rolls) == 2, "the CMB roll and the damage roll"
    assert any(w in out.tell for w in ("unmarked", "dented", "broken", "destroyed"))


def test_the_player_rolls_the_cmb_and_then_the_damage_and_neither_twice(market):
    thug = instantiate("thug", scene=market, name="the challenger")
    market.add(thug)
    engine = Engine(market, Dice(seed=5))
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"pc": ["pc"], "them": [thug.ref]}}}]))
    engine.run(engine.validate([{"op": "attack", "actor": "pc", "target": thug.ref,
                                 "params": {"manoeuvre": "sunder"}}]))
    assert market.awaiting and "Sunder (CMB)" in market.awaiting["label"]
    res = engine.resume(20)                       # a natural 20 always succeeds
    assert market.awaiting and "Sunder damage" in market.awaiting["label"]
    assert "sap" in market.awaiting["label"], "against the thug's held weapon"
    res = engine.resume(6)
    out = res.outcomes[0]
    assert not market.awaiting
    assert len(out.rolls) == 2 and out.rolls[0].natural == 20
    assert "sap takes" in out.tell


# --- 17: agency held, one death not two, a pebble takes no head ---------------------------------

def test_a_described_death_counts_and_the_backstop_replaces_the_fall_rather_than_appending():
    beat = ("The pebble strikes him with enough force to cave in his cheek. He collapses "
            "into the dirt, his body hitting the ground with a sickening thud. He doesn't "
            "move. What do you do?")
    assert narration.death_on_the_page(beat, "desperate man")
    # Without the line that says it, the death line stands where the fall was, once.
    fell = ("The pebble strikes him. The desperate man collapses into the dirt with a "
            "thud. The crowd shrinks back. What do you do?")
    death = {"name": "desperate man", "margin": 17, "hp_max": 4, "family": "bludgeoning",
             "heft": "light", "subj": "he", "obj": "him", "poss": "his"}
    text, added = narration.press_the_death(fell, [death])
    assert added == ["desperate man"]
    assert "collapses into the dirt" not in text, "the fall is replaced, not doubled"
    assert text.count("dead") == 1
    assert "head is simply gone" not in text and "skull" not in text


def test_a_light_weapon_never_takes_a_head_off():
    death = {"name": "desperate man", "margin": 40, "hp_max": 4, "family": "bludgeoning",
             "heft": "light"}
    for _ in range(6):
        line = narration.death_line(death, said={})
        assert "gone" not in line and "burst" not in line and "skull" not in line
    heavy = dict(death, heft="heavy")
    lines = {narration.death_line(heavy, said={}) for _ in range(3)}
    assert any("gone" in ln or "through" in ln or "burst" in ln for ln in lines)


def test_somebody_elses_blow_is_not_written_in_the_players_hands():
    blows = [{"attacker": "the challenger", "pc": False,
              "tell": "The challenger's attack misses you."}]
    prose = ("Your blade whistles through the air, but the heavy iron of the guard's "
             "shield turns it aside. The crowd gasps.")
    assert narration.wrong_hands(prose, blows) == [
        "Your blade whistles through the air, but the heavy iron of the guard's shield "
        "turns it aside."]
    fixed, cut = narration.right_hands(prose, blows)
    assert cut and fixed == "The crowd gasps. The challenger's attack misses you."
    # The player's own blow is theirs to have.
    mine = [{"attacker": "Kesst Vayr", "pc": True, "tell": "You hit the challenger."}]
    assert narration.wrong_hands(prose, mine) == []
    assert narration.review(prose, blows=blows).findings[0].kind == "wrong-hands"


# --- 19: the award names people -------------------------------------------------------------------

def test_the_award_line_names_the_fallen_as_people():
    from rules import xp

    assert xp._definite("desperate man") == "the desperate man"
    assert xp._definite("Drenn Ironvale") == "Drenn Ironvale"
    assert xp._definite("the stranger") == "the stranger"
