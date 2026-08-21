"""Tests for the intent protocol's four mechanical checks.

These are the tests that matter most in the project. Every one of them documents a way a
model can wreck the game that no amount of prompt instruction reliably prevents.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError, find_outcome_claims, parse, parse_all
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


# --- Check 1: schema --------------------------------------------------------------

def test_unknown_op_is_rejected():
    with pytest.raises(IntentError, match="unknown op") as e:
        parse({"op": "vibes", "actor": "pc"})
    assert e.value.check == "schema"


def test_missing_required_param_is_rejected():
    with pytest.raises(IntentError, match="missing required param"):
        parse({"op": "save", "actor": "pc", "params": {"save": "ref"}})


def test_a_genuinely_unknown_param_is_rejected():
    """A param the engine silently drops is a mechanic the GM believes it applied. If we
    have never heard of it, we cannot know it was harmless."""
    with pytest.raises(IntentError, match="unknown param"):
        parse({"op": "check", "actor": "pc",
               "params": {"skill": "stealth", "dc": {"band": "tough"},
                          "moon_phase": "waxing"}})


def test_engine_owned_params_are_dropped_and_logged_not_rejected():
    """docs/intent-protocol.md §1: "the engine ignores it and logs the discrepancy... a
    turn that dies because the model said '+7' is worse than one that overrides it."

    Hard-rejecting these contradicted that rule, and in live play it killed five
    consecutive attempts to attack a guard over `damage_type`, `dice` and `damage_roll`
    — every one of which the engine reads off the weapon anyway.
    """
    got = parse({"op": "attack", "actor": "pc", "target": "c1",
                 "params": {"weapon": "rapier", "damage_type": "piercing",
                            "dice": "1d6", "damage_roll": 4, "attack_bonus": 3}})
    assert got.params == {"weapon": "rapier", "full_attack": False}
    assert got.ignored_params == ["attack_bonus", "damage_roll", "damage_type", "dice"]


def test_the_rejection_names_the_params_the_op_does_take():
    with pytest.raises(IntentError, match="attack takes full_attack, manoeuvre"):
        parse({"op": "attack", "actor": "pc", "target": "c1",
               "params": {"enthusiasm": "high"}})


def test_other_editions_skill_names_are_mapped_rather_than_rejected():
    """Measured on the first live turn: llama3.1:8b emitted "melee", "initiative" and
    "dodge" as skills on three consecutive attempts and lost the turn entirely.

    A model has read far more 5e and 3.5e than PF1e and reaches for those words under
    pressure. The unambiguous ones are mapped in code — which is cheaper and more
    reliable than adding a list of skill names to the prompt and hoping.
    """
    for said, means in [("sneaking", "stealth"), ("hide", "stealth"),
                        ("insight", "sense motive"), ("persuasion", "diplomacy"),
                        ("deception", "bluff"), ("notice", "perception"),
                        ("lockpicking", "disable device"), ("arcana", "knowledge (arcana)")]:
        got = parse({"op": "check", "actor": "pc",
                     "params": {"skill": said, "dc": {"band": "tough"}}})
        assert got.params["skill"] == means, f"{said!r} should mean {means!r}"


def test_a_skill_that_means_nothing_is_rejected_with_the_legal_list():
    """Rejecting an unknown skill without saying what *is* legal costs a whole
    regeneration, so the rejection carries the list and the nearest matches."""
    with pytest.raises(IntentError) as e:
        parse({"op": "check", "actor": "pc",
               "params": {"skill": "parkour", "dc": {"band": "tough"}}})
    msg = str(e.value)
    assert "not a Pathfinder 1e skill" in msg
    assert "stealth" in msg and "perception" in msg   # the legal list travels with it


@pytest.mark.parametrize("said", ["attack", "melee", "to hit", "weapon", "strike"])
def test_attacking_is_pointed_at_the_attack_op_not_at_a_skill_list(said):
    """Measured: the model tried `check` with skill "attack", then spent four more
    attempts guessing at `attack`'s params. Attacking is not a skill check in 1e and no
    list of skills will ever contain the answer, so the rejection names the right op
    instead of offering 34 wrong ones.
    """
    with pytest.raises(IntentError, match=r'"op": "attack"'):
        parse({"op": "check", "actor": "pc",
               "params": {"skill": said, "dc": {"band": "tough"}}})


def test_ambiguous_cross_edition_names_are_not_guessed():
    """"athletics" is climb *or* swim in 1e. Picking one would be inventing a mechanic,
    so it is rejected with a suggestion instead of silently resolved."""
    with pytest.raises(IntentError):
        parse({"op": "check", "actor": "pc",
               "params": {"skill": "athletics", "dc": {"band": "tough"}}})


def test_initiative_is_pointed_at_begin_encounter():
    """Also measured while trying to attack a guard: the model reached for a skill check
    called "initiative". The nearest-match suggestion offered "intimidate", which is
    worse than useless — so this one is answered directly too."""
    with pytest.raises(IntentError, match="begin_encounter"):
        parse({"op": "check", "actor": "pc",
               "params": {"skill": "initiative", "dc": {"band": "tough"}}})


def test_initiative_cannot_be_used_as_an_opposing_skill():
    """The model reached for 'initiative' and 'dodge' to mean 'he resists'. The
    rejection says what to oppose with instead."""
    with pytest.raises(IntentError, match="oppose with 'perception'"):
        parse({"op": "check", "actor": "pc",
               "params": {"skill": "stealth",
                          "opposed_by": {"ref": "c1", "skill": "initiative"}}})


def test_save_aliases_are_accepted_because_models_write_them_out():
    """'reflex' and 'fortitude' are what a model writes; accept them and normalise
    rather than failing a turn over vocabulary."""
    assert parse({"op": "save", "actor": "pc",
                  "params": {"save": "Reflex", "dc": {"band": "tough"}}}).params["save"] == "ref"
    assert parse({"op": "save", "actor": "pc",
                  "params": {"save": "Fortitude", "dc": 15}}).params["save"] == "fort"


def test_an_invented_creature_template_is_rejected_with_the_list():
    """Validation has to cover everything resolution accepts. `spawn` required a
    `template` but never checked it, so an invented one reached the bestiary and raised
    UnknownTemplate as a 500 mid-turn — the same shape of gap as the bare-string DC.
    """
    with pytest.raises(IntentError) as e:
        parse({"op": "spawn", "params": {"template": "guild bravo", "count": 2}})
    msg = str(e.value)
    assert "no template" in msg
    assert "thug" in msg and "watchman" in msg


def test_a_real_template_survives_and_the_count_is_bounded():
    got = parse({"op": "spawn", "params": {"template": "Thug", "count": "3"}})
    assert got.params["template"] == "thug"
    assert got.params["count"] == 3
    assert parse({"op": "spawn",
                  "params": {"template": "thug", "count": 99}}).params["count"] == 12


def test_every_shape_the_resolver_accepts_is_also_validated():
    """Measured on the second live turn: the model sent `"dc": "DC 15"` as a bare
    string. `rules.dc.resolve` accepted strings, `_check_params` only validated the dict
    form, so it sailed past check 1 and raised inside the engine as a 500 — an uncaught
    crash instead of a rejection the model could have repaired.

    Validation must cover everything resolution accepts. These are all the shapes.
    """
    def dc_of(spec):
        return parse({"op": "check", "actor": "pc",
                      "params": {"skill": "stealth", "dc": spec}}).params["dc"]

    assert dc_of("DC 15") == {"value": 15}
    assert dc_of("15") == {"value": 15}
    assert dc_of(15) == {"value": 15}
    assert dc_of({"value": 15}) == {"value": 15}
    assert dc_of("tough") == {"band": "tough"}
    assert dc_of("Nearly Impossible") == {"band": "nearly_impossible"}
    assert dc_of({"band": "tough"}) == {"band": "tough"}


def test_a_canonicalised_dc_resolves_without_raising():
    """The point of canonicalising in check 1 is that the engine never sees a shape it
    does not understand. Anything parse() accepts, resolve() must handle."""
    from rules.dc import resolve as resolve_dc

    for spec in ("DC 15", "15", 15, {"value": 15}, "tough", {"band": "formidable"}):
        canonical = parse({"op": "check", "actor": "pc",
                           "params": {"skill": "stealth", "dc": spec}}).params["dc"]
        assert isinstance(resolve_dc(canonical, level=1).final, int)


def test_invented_difficulty_band_is_rejected():
    """Given freedom a model invents vocabulary and then treats it as settled. The band
    list is closed and enforced here, not suggested in a prompt."""
    with pytest.raises(IntentError) as e:
        parse({"op": "check", "actor": "pc",
               "params": {"skill": "stealth", "dc": {"band": "very hard"}}})
    msg = str(e.value)
    assert "is not a difficulty band" in msg
    assert "challenging" in msg   # the legal list travels with the rejection


def test_circumstance_cannot_be_a_number():
    with pytest.raises(IntentError, match="circumstance must be"):
        parse({"op": "check", "actor": "pc",
               "params": {"skill": "stealth", "dc": {"band": "tough"},
                          "circumstance": {"value": 4}}})


def test_check_without_a_dc_or_an_opponent_is_rejected_with_both_remedies():
    """A check with nothing to beat is meaningless, and this was the single most common
    rejection across live turns. The message spells out both legal completions, because
    a rejection the model cannot act on costs a whole regeneration."""
    with pytest.raises(IntentError) as e:
        parse({"op": "check", "actor": "pc", "params": {"skill": "stealth"}})
    msg = str(e.value)
    assert '"dc"' in msg and '"opposed_by"' in msg and "challenging" in msg


def test_a_third_word_for_who_rolls_is_mapped_to_hidden():
    """Observed on two separate live turns: the model wrote `visibility: "gm"` and then
    `visibility: "game"`, both meaning "the engine rolls this one". That is what hidden
    means, so it is mapped rather than costing a regeneration."""
    for said in ("gm", "game", "GM", "engine", "secret"):
        got = parse({"op": "check", "actor": "pc", "visibility": said,
                     "params": {"skill": "stealth", "dc": 15}})
        assert got.visibility == "hidden", f"{said!r} should mean hidden"
    assert parse({"op": "check", "actor": "pc", "visibility": "pc",
                  "params": {"skill": "stealth", "dc": 15}}).visibility == "player"


def test_empty_intent_list_is_a_failure_not_a_quiet_turn():
    """The reason `narrate_only` exists.

    Without it, a model that forgot to emit intents is indistinguishable from a
    conversation beat, and that failure is invisible. With it, it is this assertion.
    """
    with pytest.raises(IntentError, match="narrate_only"):
        parse_all([])
    assert parse_all([{"op": "narrate_only"}])[0].op == "narrate_only"


# --- Check 2: refs -----------------------------------------------------------------

def test_intent_naming_an_actor_that_does_not_exist_is_rejected(engine):
    """World Bible's own prose invents places and people that do not exist and then
    treats them as settled fact — 'Aviari's Spire' and 'Elyria's Forge' are documented
    cases. The GM will do the same with people. It cannot make the orc that is not on
    the board attack.
    """
    with pytest.raises(IntentError, match="unknown actor") as e:
        engine.validate([{"op": "attack", "actor": "c7", "target": "pc"}])
    assert e.value.check == "refs"


def test_intent_naming_a_target_by_name_instead_of_ref_is_rejected(engine):
    with pytest.raises(IntentError, match="unknown target"):
        engine.validate([{"op": "attack", "actor": "c1", "target": "the guildhand"}])


def test_opposed_check_against_an_unknown_ref_is_rejected(engine):
    with pytest.raises(IntentError, match="opposed_by names unknown ref"):
        engine.validate([{
            "op": "check", "actor": "pc",
            "params": {"skill": "stealth",
                       "opposed_by": {"ref": "c9", "skill": "perception"}},
        }])


def test_the_rejection_lists_the_refs_that_do_exist(engine):
    """A rejection the model cannot act on costs a whole regeneration. Naming the legal
    refs turns a retry into a repair."""
    with pytest.raises(IntentError, match=r"known refs are \['c1', 'pc'\]"):
        engine.validate([{"op": "attack", "actor": "nobody", "target": "pc"}])


# --- Check 3: legality ---------------------------------------------------------------

def test_an_unconscious_actor_cannot_act(engine, scene):
    scene.get("c1").add_condition("unconscious")
    with pytest.raises(IntentError, match="cannot act") as e:
        engine.validate([{"op": "attack", "actor": "c1", "target": "pc"}])
    assert e.value.check == "legality"


def test_attacking_with_a_weapon_the_actor_is_not_carrying_is_rejected(engine):
    """Kesst carries a rapier and a dagger. The GM does not get to hand her a longsword
    by narrating one."""
    with pytest.raises(IntentError, match="not carrying"):
        engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                          "params": {"weapon": "longsword"}}])


# --- Check 4: the outcome-claim detector ----------------------------------------------

@pytest.mark.parametrize("narration,why", [
    ("The bolt catches her in the shoulder and you take 6 damage.", "damage number"),
    ("You succeed, barely, and the latch gives.", "success"),
    ("The blade bites deep into his side.", "attack landing"),
    ("His swing goes wide.", "attack missing"),
    ("You slip past him into the dark.", "stealth result"),
    ("He doesn't notice you at all.", "perception result"),
    # Produced in live play, in the setup narration, before the opposed Stealth check
    # had been rolled — the GM had quietly decided the guildhand failed his Perception.
    ("The guildhand blinks once, rubs his eye, and goes back to his cup, unaware.",
     "unaware"),
    ("He is oblivious to the shape on the wall.", "oblivious"),
    # Produced in a live fight, in setup narration, while the engine still had her
    # grappled. Escaping a grapple is a combat manoeuvre check like any other.
    ("You squirm and twist, managing to slip free of the grapple.", "slips free"),
    ("She breaks loose and puts the post between them.", "breaks loose"),
    ("He manages to get his shield up in time.", "manages to"),
    ("She shakes herself free of his grip.", "shakes free"),
    ("He never sees you cross the yard.", "never sees"),
    ("The guildhand fails to notice the movement above him.", "fails to notice"),
    ("You're hit before you can move.", "being hit"),
    ("Make a Reflex save, DC 18.", "DC in prose"),
    ("You roll a 14 and the rope holds.", "die result"),
    ("Your hit points are running low.", "hit points"),
])
def test_outcome_claims_are_detected(narration, why):
    """Every string here is a phrasing a model produced while the prompt explicitly told
    it not to state outcomes. Instruction volume loses; detection does not.
    """
    claims = find_outcome_claims(narration)
    assert claims, f"undetected outcome claim ({why}): {narration!r}"


@pytest.mark.parametrize("narration", [
    "The lamp on its chain sweeps the yard wall and starts back.",
    "Behind it a guildhand leans in the doorway, half-asleep over a cup.",
    "He is a big man, and the club at his belt has seen use.",
    "The gantry pin shears with a sound like a snapped bone.",
    "She draws the rapier. The alley is narrow enough that it will matter.",
    "'You're a long way from the lower quarter,' he says, not moving.",
])
def test_legitimate_setup_narration_is_not_flagged(narration):
    """The detector has to be usable, which means the wind-up must survive it. A detector
    that flags ordinary scene-setting would force a repair call every single turn.
    """
    assert not find_outcome_claims(narration), f"false positive: {narration!r}"


def test_the_claim_reports_the_sentence_so_the_repair_can_be_targeted():
    """The repair call is 'fix this sentence, change nothing else'. That needs the
    sentence, not the whole narration."""
    text = ("The lamp sweeps away from the wall. You slip past him into the dark. "
            "Somewhere a door closes.")
    claims = find_outcome_claims(text)
    assert claims
    assert claims[0].sentence == "You slip past him into the dark."
