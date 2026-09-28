"""A punch knocks out, a sap knocks out, and either can be swung to kill — at -4.

The defect, measured 2026-09-27 through `Engine.run`: `tables.WEAPONS` had marked the
sap and the unarmed strike `"nonlethal": True` since the slice, and nothing read the
flag. `_op_attack` called `_apply_damage` with its default `lethality="lethal"`, so
Kesst's punch took the thug from 13 to 4 hit points with his nonlethal still 0, and the
thug's sap — "Prefers a sap: a body that wakes up cannot testify" — took Kesst from 9
to 1. The `fight` narrator-audit script is mostly punches, so every one of its blows
was a wound.

The rules, Core Rulebook p.182 and p.191: unarmed strikes and saps deal nonlethal; a
melee weapon that deals lethal damage may deal nonlethal instead, and a nonlethal one
lethal instead, each at -4 on the attack roll; Improved Unarmed Strike (a monk's from
1st level) chooses either with no penalty. Rogue: no sneak attack on a lethal weapon
swung for nonlethal. Bestiary: undead and constructs are not subject to nonlethal
damage. And "if a creature's nonlethal damage is equal to his total maximum hit points,
all further nonlethal damage is treated as lethal damage."
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules import weapons as weapons_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, IntentError, Scene
from rules.intents import parse
from rules.sheet import from_dict, load_pc, to_dict


def _fight(pc=None, seed=5):
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(pc or load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    engine = Engine(scene, Dice(seed=seed))
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"you": ["pc"], "them": ["c1"]}}}]))
    return scene, engine


def _swing(engine, actor, target, **params):
    """One swing the engine rolls for (hidden), so the test never waits on a popup."""
    scene = engine.scene
    scene.turn = [r for r, _ in scene.initiative].index(actor)
    return engine.run(engine.validate([{
        "op": "attack", "actor": actor, "target": target, "visibility": "hidden",
        "params": params, "because": "test"}])).outcomes[-1]


def _until_a_hit(engine, actor, target, tries=12, **params):
    for _ in range(tries):
        out = _swing(engine, actor, target, **params)
        if any(e.get("kind") == "damage" for e in out.effects):
            return out
    pytest.fail(f"{actor} never hit {target} in {tries} swings")


def _pc(**changes):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update(changes)
    return from_dict(d, ref="pc")


def _attack_mod(out, needle):
    return [m for r in out.rolls for m in r.modifiers if needle in m.source]


# --- the defect ----------------------------------------------------------------------

def test_a_punch_lands_on_the_nonlethal_pool_and_leaves_hit_points_alone():
    """Measured before the fix: a punch took the thug 13 -> 4 hp, nonlethal 0 -> 0."""
    scene, engine = _fight()
    thug = scene.actors["c1"]
    hp = thug.hp
    out = _until_a_hit(engine, "pc", "c1", weapon="unarmed")
    hit = next(e for e in out.effects if e.get("kind") == "damage")
    assert hit["lethality"] == "nonlethal"
    assert thug.hp == hp, "a punch is not a wound"
    assert thug.nonlethal == hit["amount"] > 0
    # The narrator is fed the tell and nothing else: the one word has to be in it.
    assert "non-lethal bludgeoning" in out.tell


def test_the_thugs_sap_knocks_down_rather_than_cuts():
    """Measured before the fix: the thug's sap took Kesst 9 -> 1 hp, nonlethal 0."""
    scene, engine = _fight()
    pc = scene.actors["pc"]
    hp = pc.hp
    out = _until_a_hit(engine, "c1", "pc", weapon="sap")
    assert pc.hp == hp and pc.nonlethal > 0
    assert next(e for e in out.effects if e.get("kind") == "damage")["lethality"] \
        == "nonlethal"


def test_enough_nonlethal_is_unconscious_and_not_dying():
    scene, engine = _fight()
    thug = scene.actors["c1"]
    thug.nonlethal = thug.hp          # staggered: one more point puts him out
    out = _until_a_hit(engine, "pc", "c1", weapon="unarmed")
    assert thug.has_condition("unconscious") and not thug.has_condition("dying")
    assert thug.is_down and thug.hp > 0
    assert "the thug is unconscious" in out.tell


# --- swinging the other way ----------------------------------------------------------

def test_a_rapier_turned_to_spare_costs_four_and_deals_nonlethal():
    scene, engine = _fight()
    out = _until_a_hit(engine, "pc", "c1", weapon="rapier", lethality="nonlethal")
    assert [m.value for m in _attack_mod(out, "pulling the blow")] == [-4]
    assert next(e for e in out.effects if e.get("kind") == "damage")["lethality"] \
        == "nonlethal"
    assert "meaning to leave the thug alive" in out.tell


def test_a_fist_swung_to_kill_costs_four_and_deals_lethal():
    scene, engine = _fight()
    thug = scene.actors["c1"]
    hp = thug.hp
    out = _until_a_hit(engine, "pc", "c1", weapon="unarmed", lethality="lethal")
    assert [m.value for m in _attack_mod(out, "striking to kill")] == [-4]
    assert thug.hp < hp and thug.nonlethal == 0


def test_a_weapons_own_lethality_costs_nothing():
    scene, engine = _fight()
    out = _until_a_hit(engine, "pc", "c1", weapon="unarmed", lethality="nonlethal")
    assert not _attack_mod(out, "pulling") and not _attack_mod(out, "striking to kill")


def test_improved_unarmed_strike_and_the_monk_kill_with_a_fist_at_no_penalty():
    """p.182: "If you have the Improved Unarmed Strike feat, you can deal lethal damage
    with an unarmed strike without taking a penalty" — and a monk has the feat at 1st."""
    plain = _pc()
    feat = _pc(feats=["improved unarmed strike"])
    monk = _pc(**{"class": "monk", "ranks": {}})
    assert plain.lethality_swap("unarmed", "lethal")
    assert feat.lethality_swap("unarmed", "lethal") == ""
    assert monk.lethality_swap("unarmed", "lethal") == ""
    # The feat is about fists: it does not make a rapier's blow free to pull.
    assert feat.lethality_swap("rapier", "nonlethal")


def test_a_ranged_weapon_cannot_pull_its_blow():
    """p.191 says a MELEE weapon; an arrow cannot be turned to the flat."""
    borin = load_pc("fixtures/pc-borin.json")
    scene, engine = _fight(pc=from_dict(to_dict(borin), ref="pc"))
    with pytest.raises(IntentError, match="cannot pull its blow"):
        _swing(engine, "pc", "c1", weapon="shortbow", lethality="nonlethal")


def test_a_pulled_blow_is_no_sneak_attack_but_a_punch_is():
    """Rogue: "She cannot use a weapon that deals lethal damage to deal nonlethal damage
    in a sneak attack, not even with the usual -4 penalty." A sap or a fist can."""
    from rules import precision

    scene, _ = _fight()
    kesst, thug = scene.actors["pc"], scene.actors["c1"]
    fist = kesst.weapon("unarmed")
    rapier = kesst.weapon("rapier")
    assert precision.applies(scene, kesst, thug, fist, flat_footed=True)[0]
    dice, why = precision.applies(scene, kesst, thug, rapier, flat_footed=True,
                                  pulled=True)
    assert not dice and "pulled" in why


# --- what the weapon record says -----------------------------------------------------

def test_the_content_files_nonlethal_trait_is_read_too():
    """The content file writes the whip and the bolas as `traits: ["nonlethal"]`, the
    slice table wrote a bool — nine weapons, and neither spelling had a reader."""
    assert weapons_mod.lethality_of(weapons_mod.get("whip")) == "nonlethal"
    assert weapons_mod.lethality_of(weapons_mod.get("sap")) == "nonlethal"
    assert weapons_mod.lethality_of(weapons_mod.get("rapier")) == "lethal"
    # An explicit flag wins: a bite is built on the unarmed strike and is lethal.
    assert weapons_mod.lethality_of({"nonlethal": False, "traits": ["nonlethal"]}) \
        == "lethal"


def test_the_blood_armament_is_lethal_and_free_to_pull():
    """Built on the unarmed strike, so reading the fist's flag would have made it a sap.
    Its text: "piercing/bludgeoning (or non-lethal)" — lethal, with the choice free."""
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "blood bending", "level": 1, "ranks": {},
              "paths": ["battle blood"]})
    bender = from_dict(d, ref="pc")
    bender.add_condition("blood armament", source="test")
    punch = bender.weapon("armed punch")
    assert weapons_mod.lethality_of(punch) == "lethal"
    assert bender.lethality_swap("armed punch", "nonlethal") == ""


def test_a_class_document_with_a_nonsense_lethality_is_refused():
    import json
    from pathlib import Path

    from rules import classbuilder

    doc = json.loads(Path("content/classes/blood-bending.json").read_text("utf-8"))
    text = json.dumps(doc).replace('"lethality": "either"', '"lethality": "gentle"')
    problems = classbuilder.validate_class(json.loads(text))
    assert any("lethality 'gentle'" in p for p in problems)


# --- what the defender is ------------------------------------------------------------

def test_undead_are_not_subject_to_nonlethal_damage():
    """Bestiary, creature types. Until punches dealt nonlethal a skeleton punched was a
    skeleton hurt; the day they did, it would have been a skeleton knocked out."""
    scene, _ = _fight()
    bones = scene.actors["c1"]
    bones.immunities = ["undead traits"]
    d = bones.take_damage(6, "bludgeoning", lethality="nonlethal")
    assert d["taken"] == 0 and bones.nonlethal == 0 and d["immune_nonlethal"]
    # The same blow swung to kill lands: it is the lethality they ignore, not the fist.
    assert bones.take_damage(6, "bludgeoning")["taken"] == 6


def test_nonlethal_past_maximum_hit_points_is_lethal():
    """A blow of 30 on a 13-hp thug used to leave him on 13 hit points forever."""
    scene, _ = _fight()
    thug = scene.actors["c1"]
    thug.hp = thug.hp_max = 13
    d = thug.take_damage(30, "bludgeoning", lethality="nonlethal")
    assert thug.nonlethal == 13 and thug.hp == -4 and d["overflow"] == 17


# --- time ----------------------------------------------------------------------------

def test_nonlethal_heals_an_hour_at_a_time_even_in_ten_minute_steps():
    """1 point per hour per level. Only a night's rest healed it before, and the clock
    mostly moves ten minutes at a time, so a minutes // 60 would never heal at all."""
    scene, _ = _fight()
    kesst = scene.actors["pc"]
    kesst.nonlethal = 5
    for _ in range(6):
        scene.advance(10)
    assert kesst.nonlethal == 4
    scene.advance(180)
    assert kesst.nonlethal == 1


def test_a_player_knocked_out_cold_wakes_when_the_rules_say_and_keeps_their_hp():
    """The downed resolver floored hp at 1 and cleared unconscious after one hour — for a
    knockout of 20 on 9 hit points that woke a player the rules still had out cold."""
    from types import SimpleNamespace

    from play import downed

    scene, engine = _fight()
    kesst = scene.actors["pc"]
    kesst.nonlethal = 20
    kesst.apply_hp_state()
    assert kesst.has_condition("unconscious")
    camp = SimpleNamespace(scene=scene, engine=lambda: engine)
    out = downed.resolve(camp)
    assert out.playable and not kesst.has_condition("unconscious")
    assert kesst.hp == 9 and kesst.nonlethal <= kesst.hp
    assert "11 hours later" in out.lines[-1]


# --- the words -----------------------------------------------------------------------

@pytest.mark.parametrize("said,spelled", [
    ("non-lethal", "nonlethal"), ("Nonlethal", "nonlethal"), ("subdual", "nonlethal"),
    ("lethal", "lethal"), ("kill", "lethal")])
def test_the_param_takes_its_spellings(said, spelled):
    got = parse({"op": "attack", "actor": "pc", "target": "c1",
                 "params": {"lethality": said}})
    assert got.params["lethality"] == spelled


def test_a_lethality_that_is_neither_is_refused_with_both_named():
    with pytest.raises(IntentError, match="'lethal' or 'nonlethal'"):
        parse({"op": "attack", "actor": "pc", "target": "c1",
               "params": {"lethality": "gentle"}})


def _plan(*attacks):
    return [dict(a) for a in attacks]


@pytest.mark.parametrize("text,weapon,expected", [
    # The fight script's own lines: a fist is a knockout and nothing needs saying.
    ("I punch him in the face.", "unarmed", None),
    ("I keep hitting him.", "unarmed", None),
    # The kills script's: a fist swung to kill.
    ("I put him down for good.", "unarmed", "lethal"),
    ("I finish him off.", "unarmed", "lethal"),
    # A blade turned.
    ("I knock him out with the pommel of my rapier.", "rapier", "nonlethal"),
    ("I hit him with the flat of my blade.", "rapier", "nonlethal"),
    ("I attack him, trying not to kill him.", "rapier", "nonlethal"),
    ("I want him alive for questioning, so I pull my blows.", "rapier", "nonlethal"),
    # A blade swung as a blade: the weapon's own, so no param.
    ("I run him through.", "rapier", None),
    ("I kill him.", "rapier", None),
])
def test_the_players_words_choose_the_lethality(text, weapon, expected):
    scene, _ = _fight()
    raw = _plan({"op": "attack", "actor": "pc", "target": "c1",
                 "params": {"weapon": weapon}})
    out = judgement.declare_lethality(raw, text, scene)
    assert out[0]["params"].get("lethality") == expected


def test_a_lethality_the_model_chose_for_the_player_is_struck():
    """A -4 on the player's roll that the player never asked for."""
    scene, _ = _fight()
    raw = _plan({"op": "attack", "actor": "pc", "target": "c1",
                 "params": {"weapon": "rapier", "lethality": "nonlethal"}},
                {"op": "attack", "actor": "c1", "target": "pc",
                 "params": {"weapon": "sap", "lethality": "lethal"}})
    out = judgement.declare_lethality(raw, "I stab him.", scene)
    assert "lethality" not in out[0]["params"]
    assert out[1]["params"]["lethality"] == "lethal", "the thug's is the GM's call"


def test_a_threat_spoken_is_not_a_blow_declared():
    scene, _ = _fight()
    raw = _plan({"op": "attack", "actor": "pc", "target": "c1",
                 "params": {"weapon": "unarmed"}})
    out = judgement.declare_lethality(raw, 'I shout "I\'ll kill you!" and punch him.',
                                      scene)
    assert "lethality" not in out[0]["params"]


def test_the_param_survives_the_attack_normaliser():
    """`normalize_attacks` strips every param it does not know; this one it must."""
    scene, _ = _fight()
    raw = [{"op": "attack", "actor": "pc", "target": "c1",
            "params": {"weapon": "rapier", "lethality": "nonlethal"}}]
    out = judgement.normalize_attacks(raw, scene) or raw
    assert out[0]["params"]["lethality"] == "nonlethal"


# --- what strikes --------------------------------------------------------------------

@pytest.mark.parametrize("text,model_weapon,expected", [
    # The fight script's lines, measured 2026-09-27 with --record: the plan named no
    # weapon, the equipped rapier swung, and the tells read "for 3 piercing".
    ("I punch him in the face.", None, "unarmed"),
    ("I punch him again.", None, "unarmed"),
    ("I kick him in the knee.", "rapier", "unarmed"),
    ("I headbutt the guard.", None, "unarmed"),
    # "hit" names nothing about what hits: the sword-arm's own.
    ("I keep hitting him.", None, None),
    # A held weapon in the same sentence decides instead.
    ("I punch him with the hilt of my rapier.", None, None),
    ("I kick him and stab him with my dagger.", "dagger", "dagger"),
])
def test_a_blow_with_the_body_is_the_unarmed_strike(text, model_weapon, expected):
    scene, _ = _fight()
    params = {"weapon": model_weapon} if model_weapon else {}
    raw = [{"op": "attack", "actor": "pc", "target": "c1", "params": params}]
    out = judgement.declare_unarmed(raw, text, scene)
    assert out[0]["params"].get("weapon") == expected


def test_a_kicked_stool_stays_an_improvised_weapon_and_a_trip_stays_a_trip():
    scene, _ = _fight()
    raw = [{"op": "attack", "actor": "pc", "target": "c1",
            "params": {"weapon": "improvised", "item": "stool"}},
           {"op": "attack", "actor": "pc", "target": "c1",
            "params": {"manoeuvre": "trip"}}]
    out = judgement.declare_unarmed(raw, "I kick the stool into him and sweep his legs.",
                                    scene)
    assert out[0]["params"]["weapon"] == "improvised"
    assert "weapon" not in out[1]["params"]


def test_the_players_punch_reaches_the_engine_as_a_knockout():
    """End to end through the declarers and Engine.run: the sentence, not the sheet's
    equipped rapier, decides what lands."""
    scene, engine = _fight()
    thug = scene.actors["c1"]
    hp = thug.hp
    for _ in range(12):
        raw = [{"op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
                "params": {}, "because": "test"}]
        raw = judgement.declare_unarmed(raw, "I punch him in the face.", scene)
        raw = judgement.declare_lethality(raw, "I punch him in the face.", scene)
        scene.turn = [r for r, _ in scene.initiative].index("pc")
        out = engine.run(engine.validate(raw)).outcomes[-1]
        if any(e.get("kind") == "damage" for e in out.effects):
            break
    assert "non-lethal bludgeoning" in out.tell
    assert thug.hp == hp and thug.nonlethal > 0
