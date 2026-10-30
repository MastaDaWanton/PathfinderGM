"""A printed hit does what its stat block says rides it.

Measured 2026-10-30 (found by the 0.2.24 monster-attacks lane): "bite +3 (1d6+1 plus
disease and paralysis)" compiled into an attack carrying `riders: ["disease",
"paralysis"]`, and nothing fired them. Over the compiled bestiary that day there were
1,036 rider words on 161 distinct riders — grab 326, poison 191, disease 64, bleed 42 (and
26 "plus 1d8 bleed" the reader dropped without a word), energy drain 40, trip 36, burn 32,
paralysis 31 — and every one of them did nothing. A ghoul paralysed nobody; a giant
spider's venom was a bite; a rat swarm's filth fever infected nobody; a wolf tripped
nobody. docs/attack-riders.md has the rules cited and the counts.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import attack_riders, bestiary, statblock_attacks
from rules import sheet as sheet_mod
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parents[1]


def _fight(template: str, seed: int, race: str = ""):
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    if race:
        pc.race = race
    scene.add(pc)
    foe = scene.add(bestiary.instantiate(template, scene=scene))
    engine = Engine(scene, Dice(seed=seed))
    engine._ensure_encounter(foe.ref)
    if scene.has_grid:
        scene.positions[pc.ref] = (4, 5)
        scene.positions[foe.ref] = (5, 5)
        scene.resync_zones()
    pc.hp = pc.hp_max = 500
    return engine, pc, foe


def _full_attack(engine, foe, target="pc"):
    return engine.run(engine.validate([
        {"op": "attack", "actor": foe.ref, "target": target, "because": "the test",
         "params": {"full_attack": True}}])).outcomes


def _tells(outcomes) -> str:
    return " ".join(o.tell or "" for o in outcomes)


def _effects(outcomes) -> list[dict]:
    return [e for o in outcomes for e in o.effects]


# --- the reader -----------------------------------------------------------------------

def test_the_affliction_format_reads_whole():
    """The Bestiary's format (Poison UMR: "Sting—injury; save Fort DC 22, frequency 1/round
    for 6 rounds, effect 1d4 Con damage, cure 2 consecutive saves") read field for field,
    the shape Combat Manager's `Affliction.FromSpecialAbility` reads it in."""
    doc = {"special_abilities": "Poison (Ex) Sting—injury; save Fort DC 22, frequency "
                                "1/round for 6 rounds, effect 1d4 Con damage, cure 2 "
                                "consecutive saves."}
    (a,) = attack_riders.afflictions(doc)
    assert (a["kind"], a["cause"], a["save"], a["dc"]) == ("poison", "Sting", "fort", 22)
    assert a["frequency"] == {"unit": "round", "count": 1, "limit": "6"}
    assert a["effects"] == [{"ability": "con", "dice": "1d4", "drain": False}]
    assert a["cure"] == 2 and a["onset"] is None and a["unread"] == []


def test_a_disease_reads_its_onset_and_name():
    doc = {"special_abilities": "Disease (Su) Ghoul Fever : Bite—injury; save Fort DC 12; "
                                "onset 1 day; frequency 1 day; effect 1d3 Con and 1d3 Dex "
                                "damage; cure 2 consecutive saves."}
    (a,) = attack_riders.afflictions(doc)
    assert (a["kind"], a["name"]) == ("disease", "Ghoul Fever")
    assert a["onset"] == {"dice": "1", "unit": "day"}
    assert {e["ability"] for e in a["effects"]} == {"con", "dex"}


@pytest.mark.parametrize("text, want", [
    # The serpentfolk's dash came in as an HTML entity: seven blocks read no poison at all.
    ("Poison (Ex) Bite&#8211;injury; save Fort DC 17; frequency 1/round for 6 rounds; "
     "effect 1d2 Str; cure 2 saves.", ("Bite", 17)),
    # The couatl prints the vector first.
    ("Poison (Ex) Injury—bite; save Fortitude DC 16; frequency 1/ minute for 10 minutes; "
     "effect 1d4 Str; cure 2 consecutive saves.", ("bite", 16)),
    # A DC with a note on it.
    ("Poison (Ex) Bite—injury; save Fort DC 14 (includes +2 racial bonus); frequency "
     "1/round for 4 rounds; effect 1d2 Str; cure 1 save.", ("Bite", 14)),
])
def test_the_prints_odd_affliction_shapes_read(text, want):
    (a,) = attack_riders.afflictions({"special_abilities": text})
    assert (a["cause"], a["dc"]) == want and a["effects"]


def test_a_rider_with_its_amount_in_front_is_carried_not_dropped():
    """"plus 1d8 bleed": until 2026-10-30 a piece that began with a digit and was not a
    damage type was thrown away — 26 bleeds and 13 ability damages and drains."""
    (opt,), _ = statblock_attacks.read("bite +23 (2d6+11 plus 1d8 bleed and rotting curse)")
    assert opt[0]["riders"] == ["bleed", "rotting curse"]
    assert opt[0]["amounts"] == {"bleed": "1d8"}
    (opt,), _ = statblock_attacks.read("bite +19 (1d8+5 plus 1d4 Cha drain)")
    assert opt[0]["riders"] == ["cha drain"] and opt[0]["amounts"] == {"cha drain": "1d4"}


def test_a_constant_typed_extra_is_damage():
    """"plus 6 fire" (an adult magma dragon's bite) is fire damage; the dice-only pattern
    dropped it."""
    (opt,), _ = statblock_attacks.read("bite +28 (2d8+15 plus 6 fire)")
    assert opt[0]["extra"] == [{"dice": "6", "type": "fire"}]


def test_a_missing_definition_is_reported_not_invented():
    """The giant centipede's block says "poison" and prints no Poison entry. Nothing is
    made up: the rider says why it does not fire."""
    doc = bestiary._build_imported(printed_only=True)["centipede-giant"]
    a = statblock_attacks.of_block(doc)["melee"][0][0]
    (rule,) = attack_riders.rules_for(doc, a)
    assert rule["kind"] == "unsupported" and "no Poison entry" in rule["why"]


# --- the riders, live -----------------------------------------------------------------

def test_a_ghouls_bite_paralysed_nobody():
    """The ghoul's paralysis (1d4+1 rounds, DC 13). Over 12 seeded full attacks against
    Kesst before 2026-10-30: 0 paralysed. Now the failed save leaves the condition, stamped
    with the ghoul, for 2 to 5 rounds; the made save leaves nothing."""
    paralysed = resisted = 0
    for seed in range(1, 13):
        engine, pc, ghoul = _fight("ghoul", seed)
        tells = _tells(_full_attack(engine, ghoul))
        if pc.has_state("state.held.paralyzed") or pc.has_condition("paralyzed"):
            paralysed += 1
            eff = next(e for e in pc.effects if e.key == "paralyzed")
            assert eff.origin == "creature:ghoul" and 2 <= eff.rounds_left <= 5
            assert "paralysis" in tells
        elif "resists the ghoul's paralysis" in tells:
            resisted += 1
    assert paralysed and resisted


def test_elves_are_immune_to_ghoul_paralysis():
    """The ghoul's own line: "elves are immune to this effect"."""
    for seed in range(1, 13):
        engine, pc, ghoul = _fight("ghoul", seed, race="elf")
        tells = _tells(_full_attack(engine, ghoul))
        assert not pc.has_condition("paralyzed")
        if "paralysis has no hold on Kesst Vayr" in tells:
            return
    pytest.fail("no ghoul hit an elf in 12 seeds")


def test_a_giant_spiders_venom_was_only_a_bite():
    """Poison (Ex) Bite—injury; save Fort DC 14; frequency 1/round for 4 rounds; effect 1d2
    Strength damage; cure 1 save. A failed save poisons, the first Strength damage lands at
    once, and the rest come on the round's clock until a save cures it or four effects have
    run — never a fifth."""
    for seed in range(1, 40):
        engine, pc, spider = _fight("spider-giant", seed)
        tells = _tells(_full_attack(engine, spider))
        if "is poisoned with the giant spider poison" not in tells:
            continue
        aff = next(e for e in pc.effects if e.kind == "affliction")
        assert aff.origin == "creature:spider-giant" and pc.has_state("state.afflicted.poison")
        struck = sum(1 for _ in [0] if pc.ability_damage.get("str"))
        assert struck and "Strength damage" in tells
        records = []
        for _ in range(8):
            records += pc.run_periodic("round", 1, engine.dice)
        saves = [r for r in records if r["kind"] == "affliction_save"]
        assert 1 <= len(saves) <= 3, saves      # four effects at most: one at the bite
        assert records[-1]["kind"] == "affliction_ended"
        assert not pc.has_state("state.afflicted")
        return
    pytest.fail("the spider never poisoned Kesst in 39 seeds")


def test_a_rat_swarms_filth_fever_infected_nobody():
    """Filth fever (the rat swarm): onset 1d3 days, 1/day, 1d3 Dex and 1d3 Con, cure 2
    consecutive saves. Infected, nothing happens until the onset has passed; then the days
    of the world clock roll the saves, across a save and load."""
    for seed in range(1, 60):
        engine, pc, swarm = _fight("rat-swarm", seed)
        printed = swarm.weapon("swarm")["stat_block"]
        got = engine._printed_riders(engine.validate([{
            "op": "attack", "actor": swarm.ref, "target": "pc", "because": "t"}])[0],
            swarm, pc, printed, {"rolls": []})
        if not pc.has_state("state.afflicted.disease"):
            continue
        assert any("infected with filth fever; it will take hold in" in g["tell"]
                   for g in got)
        assert not pc.ability_damage                       # the onset holds it off
        engine.scene.end_encounter()
        # Saved and loaded: the fever's clock and count ride the effect.
        back = sheet_mod.from_dict(sheet_mod.to_dict(pc), ref="pc")
        aff = next(e for e in back.effects if e.kind == "affliction")
        assert aff.periodic[0]["affliction"]["wait"] >= 14400
        engine.scene.people["pc"] = back
        pc = back
        engine.scene.advance(minutes=60 * 24 * 12)
        said = " ".join(engine.scene._body_said[-1].get("said") or ()) \
            if engine.scene._body_said else ""
        assert "filth fever" in said
        assert pc.ability_damage or not pc.has_state("state.afflicted.disease")
        return
    pytest.fail("the swarm never infected Kesst in 59 seeds")


def test_a_wolf_tripped_nobody():
    """Trip (Bestiary UMR): a free trip on the bite, no attack of opportunity, and "if the
    attempt fails, the creature is not tripped in return"."""
    prone = 0
    for seed in range(1, 30):
        engine, pc, wolf = _fight("wolf", seed)
        _full_attack(engine, wolf)
        prone += pc.has_state("state.position.prone")
        assert not wolf.has_state("state.position.prone")
    assert prone


def test_a_failed_trip_rider_never_backfires():
    engine, pc, wolf = _fight("wolf", 3)
    pc.flat_cmd = 60                                 # fails by 10 or more every time
    got = engine._rider_maneuver(
        engine.validate([{"op": "attack", "actor": wolf.ref, "target": "pc",
                          "because": "t"}])[0],
        wolf, pc, {"rider": "trip", "kind": "maneuver", "maneuver": "trip"},
        "creature:wolf", {"rolls": []})
    assert "fails" in " ".join(g["tell"] for g in got)
    assert not wolf.has_state("state.position.prone")


def test_grab_holds_and_constricts():
    """The assassin vine: slam (plus grab), constrict (1d8+7). The free grapple has the
    UMR's +4, both sides end grappled, and the hold crushes at once."""
    for seed in range(1, 30):
        engine, pc, vine = _fight("assassin-vine", seed)
        outs = _full_attack(engine, vine)
        if not pc.has_state("state.held.grappled"):
            continue
        assert vine.has_state("state.held.grappled")
        assert "constricts Kesst Vayr" in _tells(outs)
        rolls = [r for o in outs for r in o.rolls]
        assert any(m.get("source") == "grab" and m.get("value") == 4
                   for r in rolls for m in (r.as_dict().get("modifiers") or ()))
        return
    pytest.fail("the vine never grabbed")


def test_the_dead_and_the_made_take_no_venom():
    """Undead and constructs are immune to poison, disease and paralysis by their type
    (Bestiary pp. 307, 309), asked by tag: a skeleton bitten by a ghoul or a spider takes
    the wound and nothing that rides it."""
    engine, pc, spider = _fight("spider-giant", 1)
    bones = engine.scene.add(bestiary.instantiate("human-skeleton", scene=engine.scene))
    printed = spider.weapon("bite")["stat_block"]
    intent = engine.validate([{"op": "attack", "actor": spider.ref, "target": bones.ref,
                               "because": "t"}])[0]
    got = engine._printed_riders(intent, spider, bones, printed, {"rolls": []})
    assert got and all(g["effect"]["kind"] == "rider_refused" for g in got)
    assert not bones.has_state("state.afflicted")
    ghoul = engine.scene.add(bestiary.instantiate("ghoul", scene=engine.scene))
    got = engine._printed_riders(intent, ghoul, bones,
                                 ghoul.weapon("claws")["stat_block"], {"rolls": []})
    assert got and not bones.has_condition("paralyzed")


def test_delay_poison_holds_the_venom_without_spending_it():
    """Delay poison: "any [poison] it is exposed to ... does not affect it until the spell
    ends". While the body is immune the saves are not made and nothing is counted."""
    pc = load_pc("fixtures/pc-kesst.json")
    aff = {"kind": "poison", "save": "fort", "dc": 30, "cure": 2,
           "effects": [{"ability": "str", "dice": "1", "drain": False}]}
    eff, _ = pc.take_affliction(aff, name="test venom", source="t", origin="author:test",
                                onset_rounds=1, every_rounds=1, limit=6)
    pc.grant_defence("immunity", "poison", source="delay poison")
    assert pc.run_periodic("round", 5, Dice(seed=1)) == []
    assert eff.periodic[0]["affliction"]["left"] == 6
    pc.remove_effects(kind="immunity", source="delay poison")
    assert pc.run_periodic("round", 1, Dice(seed=1))


def test_every_compiled_rider_is_applied_or_reported():
    """No silent drop: every rider document in the compiled bestiary is one the engine
    applies, or `unsupported` with its reason. The ratchet holds the unsupported count to
    what was measured on 2026-10-30 (358 of 1,112 rider documents) and lets it only fall."""
    doc = json.loads((ROOT / "content" / "bestiary" / "compiled.json")
                     .read_text(encoding="utf-8"))
    unsupported = 0
    for rec in doc["creatures"].values():
        for cat in ("melee", "ranged"):
            for opt in rec["attacks"][cat]:
                for a in opt:
                    assert len(a["rules"]) == len(a["riders"])
                    for r in a["rules"]:
                        if r["kind"] == "unsupported":
                            assert r.get("why")
                            unsupported += 1
                        else:
                            assert r["kind"] in Engine._RIDERS or r["kind"] == "distraction"
    assert unsupported <= 358


def test_the_panel_names_a_running_affliction():
    """An affliction is not a condition row, and the panel's words after a person's hit
    points showed nothing for a fever saving every day until it said so by name."""
    from play.views import _shown_conditions

    pc = load_pc("fixtures/pc-kesst.json")
    pc.take_affliction({"kind": "disease", "dc": 12, "effects": []}, name="filth fever",
                       source="t", origin="author:test", onset_rounds=14400,
                       every_rounds=14400, limit=None)
    assert "filth fever" in _shown_conditions(pc)
