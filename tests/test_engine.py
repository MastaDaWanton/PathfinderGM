"""Tests for resolution, including the suspend/resume round trip a player roll forces."""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the guildhand"))
    return s


@pytest.fixture
def engine(scene):
    return Engine(scene, Dice(seed=20250819))


@pytest.fixture
def fight(engine):
    """An encounter already running, initiator's turn kept — the old auto-start
    semantics, done in setup. Since the battle gate landed, a first swing out of
    combat opens the fight and defers; these fixtures test the swing itself."""
    engine._ensure_encounter("pc")
    return engine


def run(engine, raw):
    return engine.run(engine.validate(raw))


def play_through(engine, raw, faces):
    """Run an intent list, answering every dice prompt from `faces` in order.

    The PC rolls their own to-hit *and* their own damage, so one attack can suspend
    several times. Returns (resolution, prompts_seen).
    """
    res = engine.run(engine.validate(raw))
    prompts = []
    supply = list(faces)
    while res.awaiting:
        prompts.append(res.awaiting)
        assert supply, f"ran out of faces at prompt {res.awaiting['label']!r}"
        res = engine.resume(supply.pop(0))
    return res, prompts


# --- Suspend and resume ---------------------------------------------------------------

def test_a_player_roll_suspends_the_whole_list(engine):
    """Resolution is a state machine, not a function: a player roll is asynchronous human
    input in the middle of an intent list, and everything after it must wait."""
    res = run(engine, [
        {"op": "check", "actor": "pc", "because": "going over the wall",
         "params": {"skill": "stealth",
                    "opposed_by": {"ref": "c1", "skill": "perception"}}},
        {"op": "advance_time", "params": {"amount": 1, "unit": "minute"}},
    ])
    assert res.status == "awaiting_player_roll"
    assert res.outcomes == []
    assert res.awaiting["label"] == "Stealth check"
    assert res.awaiting["modifier"] == 9


def test_the_prompt_carries_the_itemised_modifier_and_the_reason(engine):
    """The popup has to say what you are rolling and why. A bare '+9' is the bookkeeping
    the app exists to expose, still hidden."""
    res = run(engine, [{
        "op": "check", "actor": "pc", "because": "the lamp is at the far end of its swing",
        "params": {"skill": "stealth", "dc": {"band": "tough"}},
    }])
    p = res.awaiting
    assert p["because"] == "the lamp is at the far end of its swing"
    assert {b["source"] for b in p["breakdown"]} == {"ranks", "class skill", "Dex", "Stealthy"}
    assert p["dc"] == 15


def test_resume_finishes_the_list_from_where_it_stopped(engine):
    res = run(engine, [
        {"op": "check", "actor": "pc", "params": {"skill": "stealth", "dc": {"band": "easy"}}},
        {"op": "advance_time", "params": {"amount": 1, "unit": "minute"}},
    ])
    assert res.status == "awaiting_player_roll"
    done = engine.resume(face=13)
    assert done.status == "complete"
    assert [o.op for o in done.outcomes] == ["check", "advance_time"]
    assert done.outcomes[0].rolls[0].total == 22
    assert done.outcomes[0].verdict == "success"


def test_the_opposed_roll_is_made_before_suspending_and_is_not_rerolled(engine):
    """If the hidden side were rolled after the resume, a player who reloaded the page
    would get a fresh opponent roll — a re-roll they could farm. It is rolled once,
    before the suspend, and carried through the continuation.
    """
    run(engine, [{
        "op": "check", "actor": "pc",
        "params": {"skill": "stealth", "opposed_by": {"ref": "c1", "skill": "perception"}},
    }])
    carried = engine.scene.pending_partial["opposed_roll"]
    first = engine.resume(face=10)
    assert first.outcomes[0].rolls[1].as_dict()["faces"] == carried["faces"]


def test_an_npc_roll_can_never_be_player_visible(engine):
    """Measured on the first fully successful live turn: the GM marked the guildhand's
    Perception check `visibility: "player"`.

    Nothing suspended, because the popup only ever asks the player for their own rolls —
    so the engine rolled it and then labelled it player-visible, which would show the
    player a number nobody rolled and hand the GM a hidden roll it could leak. Only the
    PC's rolls can be player-visible, and that is enforced, not requested.
    """
    intents = engine.validate([{
        "op": "check", "actor": "c1", "visibility": "player",
        "params": {"skill": "perception", "dc": {"band": "tough"}},
    }])
    assert intents[0].visibility == "hidden"

    res = engine.run(intents)
    assert res.status == "complete"
    assert all(r.visibility == "hidden" for r in res.outcomes[0].rolls)
    assert res.outcomes[0].player_visible()["rolls"] == []


def test_the_pcs_own_roll_keeps_player_visibility(engine):
    intents = engine.validate([{
        "op": "check", "actor": "pc", "visibility": "player",
        "params": {"skill": "stealth", "dc": {"band": "tough"}},
    }])
    assert intents[0].visibility == "player"


def test_hidden_rolls_never_suspend(engine):
    """Only the player's own rolls reach the popup. The guildhand's Perception is the
    engine's business."""
    res = run(engine, [{
        "op": "check", "actor": "c1", "visibility": "hidden",
        "params": {"skill": "perception", "dc": {"band": "average"}},
    }])
    assert res.status == "complete"
    assert res.outcomes[0].rolls[0].visibility == "hidden"


# --- What the GM is allowed to see -------------------------------------------------------

def test_hidden_roll_numbers_are_stripped_before_the_gm_sees_them(engine):
    """The GM cannot leak a number it was never given. This is why the narrator is handed
    `player_visible()` and not the outcome."""
    res = run(engine, [{
        "op": "check", "actor": "c1", "visibility": "hidden", "because": "he heard something",
        "params": {"skill": "perception", "dc": {"band": "average"}},
    }])
    visible = res.outcomes[0].player_visible()
    assert visible["rolls"] == []
    assert visible["tell"]
    assert visible["verdict"] in ("success", "failure")


def test_every_outcome_carries_a_tell_written_by_code(engine):
    """If the narrator model falls over mid-turn, the tell renders raw and play
    continues. The narrator is a garnish on a game that works without it."""
    res = run(engine, [
        {"op": "check", "actor": "pc", "visibility": "hidden",
         "params": {"skill": "perception", "dc": {"band": "easy"}}},
        {"op": "condition", "params": {"condition": "shaken", "to": "c1",
                                       "duration": {"amount": 3, "unit": "round"}}},
    ])
    assert all(o.tell for o in res.outcomes)
    assert "shaken for 3 rounds" in res.outcomes[1].tell


# --- Combat maths --------------------------------------------------------------------------

def test_the_player_rolls_their_own_to_hit_and_their_own_damage(fight, scene):
    engine = fight
    """The architecture decision is "player rolls surface on a dice popup and the player
    rolls them" — which has to include the attack roll and the damage roll.

    The `attack` op defaulted to hidden visibility, so the engine was silently rolling
    the player's own attacks for them. Found by the user attacking a guard.
    """
    res, prompts = play_through(
        engine,
        [{"op": "attack", "actor": "pc", "target": "c1",
          "because": "she has run out of talking"}],
        faces=[15, 4],          # to-hit, then damage (15 hits without threatening)
    )
    assert [p["label"] for p in prompts] == [
        "Attack with rapier", "Damage (rapier)",
    ]
    # The to-hit prompt shows the terms and what to beat; the damage prompt shows a d6.
    assert prompts[0]["dc"] == 10                      # guildhand AC, flat-footed
    assert {b["source"] for b in prompts[0]["breakdown"]} == {"BAB", "Dex (Finesse)"}
    assert prompts[1]["die"] == "1d6"
    assert (prompts[1]["min"], prompts[1]["max"]) == (1, 6)
    assert [b["source"] for b in prompts[1]["breakdown"]] == ["Str"]

    o = res.outcomes[0]
    assert o.verdict == "hit"
    assert all(r.visibility == "player" for r in o.rolls)
    assert scene.get("c1").hp == 4 - 5                 # 4 on the die, +1 Str


def test_a_missed_attack_never_asks_for_damage(fight):
    engine = fight
    """A miss ends the attack. Asking for damage after one would be the clearest
    possible tell that the popup is cosmetic rather than part of resolution."""
    res, prompts = play_through(
        engine, [{"op": "attack", "actor": "pc", "target": "c1"}], faces=[2],
    )
    assert [p["label"] for p in prompts] == ["Attack with rapier"]
    assert res.outcomes[0].verdict == "miss"


def test_a_full_attack_at_bab_zero_is_still_one_attack(fight):
    engine = fight
    """Kesst is BAB +0. A GM that asks for a full attack does not thereby grant her an
    iterative she has not earned."""
    res, prompts = play_through(
        engine, [{"op": "attack", "actor": "pc", "target": "c1",
                  "params": {"full_attack": True}}],
        faces=[15, 4],
    )
    assert len([p for p in prompts if p["label"].startswith("Attack")]) == 1


def test_an_npc_attack_is_rolled_by_the_engine_and_never_prompts(engine, scene):
    """Only the PC's rolls reach the popup. The thug's attack is the engine's business,
    and its rolls stay hidden from the GM."""
    res = run(engine, [{"op": "attack", "actor": "c1", "target": "pc"}])
    assert res.status == "complete"
    assert all(r.visibility == "hidden" for r in res.outcomes[0].rolls)
    assert res.outcomes[0].player_visible()["rolls"] == []


def test_a_critical_threat_asks_the_player_to_confirm_it(fight, scene):
    engine = fight
    """A rapier threatens on 18-20, and a threat is not a crit until it is confirmed —
    the step a person forgets mid-fight. The confirmation is the player's roll too."""
    res, prompts = play_through(
        engine, [{"op": "attack", "actor": "pc", "target": "c1"}],
        faces=[19, 15, 7],       # threat, confirm, damage (2d6 on a x2 crit)
    )
    assert [p["label"] for p in prompts] == [
        "Attack with rapier", "Confirm critical (rapier)", "Damage (rapier — CRITICAL)",
    ]
    assert prompts[2]["die"] == "2d6"
    # Str is multiplied by the crit multiplier along with the dice.
    assert [b["source"] for b in prompts[2]["breakdown"]] == ["Str x2"]
    assert "critically hits" in res.outcomes[0].tell


def test_an_unaware_defender_is_flat_footed_and_loses_dex_to_ac(engine, scene):
    """Kesst opens on a guildhand who has not acted. AC 10 either way for that NPC, so
    the assertion is on a defender who actually has a Dex bonus to lose."""
    from rules.bestiary import instantiate

    dog = instantiate("guard dog", scene=scene)
    scene.add(dog)
    assert dog.ac() == 14
    assert dog.ac(flat_footed=True) == 14   # flat_ac stat blocks carry one number

    kesst = scene.pc()
    assert kesst.ac() == 15
    assert kesst.ac(flat_footed=True) == 12

    _, prompts = play_through(
        engine, [{"op": "attack", "actor": "c1", "target": "pc"}], faces=[],
    )
    assert prompts == []                     # NPC attack never prompts


def test_power_attack_is_declared_by_the_gm_but_scored_by_the_engine(scene):
    """The tactical choice is fiction and the GM may declare it; the -1/+2 and its
    scaling are the engine's. A character without the feat cannot use it at all."""
    from rules.sheet import from_dict

    brute = from_dict({
        "name": "Borin", "kind": "pc", "class": "fighter", "level": 8,
        "abilities": {"str": 18, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8},
        "hp": 70, "ranks": {}, "feats": ["power attack"],
        "armour": "breastplate", "weapons": ["greatsword"], "equipped": "greatsword",
    }, ref="brute")
    assert brute.bab == 8
    # BAB 8 -> 3 steps of Power Attack; two-handed, so +3 damage per step.
    assert brute.power_attack_terms("greatsword") == (-3, 9)
    atk = sum(m.value for m in brute.attack_modifiers("greatsword", power_attack=True))
    plain = sum(m.value for m in brute.attack_modifiers("greatsword"))
    assert plain - atk == 3
    dmg = sum(m.value for m in brute.damage_modifiers("greatsword", power_attack=True))
    assert dmg == 4 + 9          # Str 18 plus the Power Attack bonus


def test_power_attack_without_the_feat_is_refused(engine):
    """Kesst has neither the feat nor the BAB nor the Str for it."""
    with pytest.raises(IntentError, match="does not have Power Attack"):
        engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                          "params": {"power_attack": True}}])


def test_non_proficiency_costs_four(scene):
    """Kesst is a rogue: proficient with the rapier, not with the longsword. A -4 nobody
    applies is four points of pure invisible cheating."""
    kesst = scene.pc()
    assert kesst.is_proficient("rapier")
    assert not kesst.is_proficient("longsword")
    terms = {m.source: m.value for m in kesst.attack_modifiers("longsword")}
    assert terms["not proficient with longsword"] == -4


def test_damage_drops_the_target_and_the_engine_applies_the_condition(engine, scene):
    """1e's death thresholds are applied by code, so nobody has to remember them
    mid-scene. The guildhand has 4 hp and Con 11."""
    res = run(engine, [{"op": "damage", "params": {"amount": 6, "type": "bludgeoning",
                                                   "to": "c1"}}])
    assert scene.get("c1").hp == -2
    assert scene.get("c1").has_condition("unconscious")
    assert any(e["kind"] == "condition" for e in res.outcomes[0].effects)


def test_time_passing_expires_timed_conditions(engine, scene):
    run(engine, [{"op": "condition", "params": {"condition": "shaken", "to": "c1",
                                                "duration": {"amount": 2, "unit": "round"}}}])
    assert scene.get("c1").has_condition("shaken")
    res = run(engine, [{"op": "advance_time", "params": {"amount": 1, "unit": "minute"}}])
    assert not scene.get("c1").has_condition("shaken")
    assert "Shaken" in res.outcomes[0].tell


def test_initiative_orders_everyone_on_the_board(engine, scene):
    res = run(engine, [{"op": "begin_encounter",
                        "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}])
    assert scene.round == 1
    assert len(scene.initiative) == 2
    assert scene.initiative[0][1] >= scene.initiative[1][1]


def test_spawn_mints_a_real_ref_the_gm_can_then_use(engine, scene):
    """The GM cannot invent an NPC by naming one, but it can ask for one — and what it
    gets back is a registered ref that passes check 2."""
    res = run(engine, [{"op": "spawn", "params": {"template": "watchman", "count": 2}}])
    made = res.outcomes[0].effects[0]["actors"]
    assert [m["ref"] for m in made] == ["c2", "c3"]
    engine.validate([{"op": "attack", "actor": "c2", "target": "pc"}])


def test_seeded_dice_make_a_whole_scene_reproducible(scene):
    """Every roll goes through one Dice instance, so a seed replays a scene exactly.
    Without it, a failing scene cannot be re-run."""
    def play():
        s = Scene()
        s.add(load_pc("fixtures/pc-kesst.json"))
        s.add(instantiate("thug", scene=s))
        e = Engine(s, Dice(seed=7))
        r = e.run(e.validate([{"op": "attack", "actor": "c1", "target": "pc"}]))
        return [roll.faces for roll in r.outcomes[0].rolls]

    assert play() == play()
