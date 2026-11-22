"""The body and movement skill uses (rules/bodyskills.py, lane impl2/skills-body).

The implementation audit of 2026-11-22 (docs/implementation-audit-2026-11-22.md §2) measured
these as narrated or absent:

  * Fly and Ride: "No resolved use at all" — a Ride check was a roll at the plan's DC that
    changed nothing, and nobody could sit on a horse the party owned;
  * Climb: "'Climbing is not a way of moving' is still true" — a failed climb dropped
    nobody, and nobody lost Dexterity on a wall;
  * Acrobatics: "soften a fall, jump distances" (gap 9) — a jump's DC was the plan's band,
    whatever the gap;
  * Heal: "treat poison, treat disease" (gap 6) — the affliction executor rolled every save
    with nothing a healer could add, and round 1 found companions never rest-healed, so
    long-term care on one "shows nothing";
  * Escape Artist: only the grapple.

Every behaviour test goes through `Engine.run` and reads the sheet and the tells.
"""
from __future__ import annotations

import pytest

from rules import bodyskills, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


class _Faces(Dice):
    """Every d20 whose label holds a key lands on that key's face; the rest on `rest`."""

    def __init__(self, faces: dict | None = None, rest: int = 10):
        super().__init__(seed=20261122)
        self.faces, self.rest = dict(faces or {}), rest
        self.labels: list[str] = []

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if str(notation).lstrip("1").startswith("d20"):
            self.labels.append(label or "")
            face = next((f for k, f in self.faces.items() if k in (label or "")), self.rest)
            return self.given(face, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _scene(faces=None, rest=10, fight=False, foe=None):
    foe = foe or ("thug" if fight else None)     # a fight needs somebody to fight
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    if foe:
        scene.add(instantiate(foe, scene=scene, name="the foe"))
    engine = Engine(scene, _Faces(faces, rest))
    if fight:
        engine._ensure_encounter("pc")
        scene.acted.update(scene.actors)
    return scene, engine, scene.get("pc")


def _run(engine, *raws):
    res = engine.run(engine.validate([dict(r, visibility="hidden") for r in raws]))
    assert not res.awaiting
    return res.outcomes


def _check(**params):
    return {"op": "check", "actor": "pc", "params": params}


def _total(actor, skill):
    return sum(m.value for m in actor.skill_modifiers(skill))


# --- the table, the parse ---------------------------------------------------------------------

def test_every_declarable_use_has_a_row_and_a_door():
    from rules import skilluses

    rows = skilluses.rows()
    for skill, uses in bodyskills.USES.items():
        for use in uses:
            uid = bodyskills.use_id(skill, use)
            assert uid in rows, uid
            assert uid in bodyskills.DOORS, uid


def test_a_use_of_another_skill_is_refused_at_the_parse_with_the_fix_named():
    from rules.intents import IntentError

    scene, engine, pc = _scene()
    with pytest.raises(IntentError, match="not a use of 'perception'"):
        engine.validate([_check(skill="perception", use="jump")])
    with pytest.raises(IntentError, match="distance_ft is from 0 to 100"):
        engine.validate([_check(skill="acrobatics", use="jump", distance_ft=400)])


# --- Acrobatics: jump, soften a fall, balance -------------------------------------------------

def test_a_jumps_dc_is_the_gap_not_the_plans_band():
    """Audit gap 9: "jump distances" — the DC was whatever band the plan wrote. A 15-foot
    gap is DC 15 by the book whatever the plan says; the jumper's own speed term rides on
    the roll (Kesst moves 30 ft: no term)."""
    scene, engine, pc = _scene(faces={"Acrobatics": 10})
    out = _run(engine, _check(skill="acrobatics", use="jump", distance_ft=15,
                              dc={"band": "easy"}))[0]
    assert out.dc["value"] == 15
    need = 15 - _total(pc, "acrobatics")
    assert (out.verdict == "success") == (10 >= need)


def test_a_jump_missed_by_five_drops_the_jumper_into_the_gap_and_hurts():
    """"If you fail by 5 or more, you fail to make the jump and fall": the drop is the
    fiction's height_ft, the damage the falling row's, and damage from a fall leaves the
    body prone."""
    scene, engine, pc = _scene(faces={"Acrobatics": 1})
    hp = pc.hp
    out = _run(engine, _check(skill="acrobatics", use="jump", distance_ft=20, height_ft=20))[0]
    assert out.verdict == "failure" and out.margin <= -5
    assert "drops into the gap" in out.tell and "a fall" in out.tell
    assert pc.hp < hp and (pc.has_state("state.position.prone") or pc.is_down)


def test_a_jump_missed_by_four_or_less_is_a_reflex_save_for_the_far_edge():
    scene, engine, pc = _scene(faces={"Acrobatics": 10, "Reflex": 20})
    need = 10 + _total(pc, "acrobatics") + 2       # a gap two feet beyond the roll
    out = _run(engine, _check(skill="acrobatics", use="jump", distance_ft=need,
                              height_ft=30))[0]
    assert -4 <= out.margin < 0, out.margin
    assert "grabs the far edge" in out.tell
    assert pc.has_state(bodyskills.CLIMBING), "hanging there, the pull-up is a Climb check"


def test_without_a_running_start_in_a_fight_the_dc_doubles():
    """"If you do not have at least 10 feet of space to get a running start, the DC is
    doubled": in a fight, a jump with no move made first this round."""
    scene, engine, pc = _scene(faces={"Acrobatics": 20}, fight=True)
    out = _run(engine, _check(skill="acrobatics", use="jump", distance_ft=10))[0]
    assert out.dc["value"] == 20 and "doubled" in out.dc["basis"]


def test_a_high_jump_is_four_times_the_height():
    scene, engine, pc = _scene(faces={"Acrobatics": 20})
    out = _run(engine, _check(skill="acrobatics", use="high-jump", distance_ft=3))[0]
    assert out.dc["value"] == 12


def test_a_slow_jumper_takes_the_racial_penalty():
    """"–4 racial penalty on Acrobatics checks made to jump for every 10 feet of speed
    below 30 feet"."""
    scene, engine, pc = _scene()
    pc.speed = 20
    out = _run(engine, _check(skill="acrobatics", use="jump", distance_ft=5))[0]
    assert any(m.value == -4 and "jumping" in m.source for m in out.rolls[0].modifiers)


def test_a_deliberate_drop_softened_counts_ten_feet_less():
    """CRB, Acrobatics: "a DC 15 Acrobatics skill check allows you to ignore the first 10
    feet fallen". A 20-foot drop made soft is a 10-foot fall: one die, and that die the
    deliberate jump's nonlethal one."""
    scene, engine, pc = _scene(faces={"Acrobatics": 20})
    hp = pc.hp
    out = _run(engine, _check(skill="acrobatics", use="soften-fall", height_ft=20))[0]
    assert out.verdict == "success" and "as if the drop were 10 feet" in out.tell
    dmg = [e for e in out.effects if e.get("kind") == "damage"]
    assert dmg and all(e["lethality"] == "nonlethal" for e in dmg)
    assert pc.hp == hp


def test_a_missed_balance_over_a_drop_is_a_fall():
    scene, engine, pc = _scene(faces={"Acrobatics": 1})
    out = _run(engine, _check(skill="acrobatics", use="balance", dc={"band": "challenging"},
                              height_ft=30))[0]
    assert out.verdict == "failure" and "falls off" in out.tell
    assert pc.has_state("state.position.prone") or pc.is_down


def test_balancing_in_a_fight_takes_the_dexterity_from_ac():
    """"you are considered flat-footed and lose your Dexterity bonus to your AC"."""
    scene, engine, pc = _scene(faces={"Acrobatics": 20}, fight=True)
    _run(engine, _check(skill="acrobatics", use="balance", dc={"band": "easy"}))
    assert pc.has_state(bodyskills.BALANCING) and pc.loses_dex_to_ac


# --- Climb -----------------------------------------------------------------------------------

def test_a_climb_out_of_a_fight_goes_stretch_by_stretch_to_the_top():
    """CRB, Climb: a quarter of speed per move action, a check each. Kesst (30 ft) climbs
    7 feet a check, so a 20-foot wall is three made checks; at the top nothing holds."""
    scene, engine, pc = _scene(faces={"Climb": 20})
    out = _run(engine, _check(skill="climb", dc={"band": "tough"}, height_ft=20))[0]
    assert out.verdict == "success" and "reaches the top, 20 feet up" in out.tell
    assert engine.dice.labels.count("Climb check") == 3
    assert not pc.has_state(bodyskills.CLIMBING)


def test_a_climb_missed_by_five_halfway_up_falls_from_the_height_reached():
    """"fail by 5 or more ... you fall from whatever height you have already attained",
    and catching yourself is the wall's DC + 20. The audit: "a failed climb does not drop
    you"."""

    class Climbs(_Faces):
        n = 0

        def roll(self, notation, modifiers=None, label="", visibility="hidden"):
            if label == "Climb check":
                Climbs.n += 1
                return self.given(20 if Climbs.n < 3 else 1, modifiers, label)
            return super().roll(notation, modifiers, label, visibility)

    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Climbs({"catch": 1}))
    pc = scene.get("pc")
    hp = pc.hp
    out = _run(engine, _check(skill="climb", dc={"band": "tough"}, height_ft=40))[0]
    assert "loses their grip 14 feet up" in out.tell, out.tell
    assert "catch the wall misses" in out.tell
    assert pc.hp < hp and not pc.has_state(bodyskills.CLIMBING)


def test_in_a_fight_a_climber_holds_the_wall_and_loses_dexterity():
    scene, engine, pc = _scene(faces={"Climb": 20}, fight=True)
    out = _run(engine, _check(skill="climb", dc={"band": "tough"}, height_ft=30))[0]
    assert "7 of 30 feet up" in out.tell
    assert pc.has_state(bodyskills.CLIMBING) and pc.loses_dex_to_ac
    # The next check is the next move action: refused this round, it goes on next round.
    again = _run(engine, _check(skill="climb"))[0]
    assert again.status == "refused" and "move action" in again.tell
    scene.round += 1
    on = _run(engine, _check(skill="climb"))[0]
    assert "14 of 30 feet up" in on.tell


# --- Escape Artist ----------------------------------------------------------------------------

def test_a_tied_body_slips_its_ropes_with_escape_artist_and_the_bond_comes_off():
    scene, engine, pc = _scene(faces={"Escape Artist": 20})
    pc.add_condition("bound", source="the bandits' rope")
    assert pc.has_state("state.held.bound") and pc.loses_dex_to_ac
    out = _run(engine, _check(skill="escape artist", dc={"band": "tough"}))[0]
    assert out.dc["value"] == 20 and out.verdict == "success"
    assert not pc.has_state("state.held.bound")


def test_manacles_are_dc_thirty_and_out_of_reach_of_a_low_bonus():
    scene, engine, pc = _scene()
    pc.add_condition("manacled", source="the watch")
    out = _run(engine, _check(skill="escape artist", dc={"band": "easy"}))[0]
    if _total(pc, "escape artist") < 10:
        assert out.status == "refused" and "DC 30" in out.tell
    else:
        assert out.dc["value"] == 30


def test_squeezing_through_is_dc_thirty_and_a_minute():
    scene, engine, pc = _scene(faces={"Escape Artist": 20})
    before = scene.clock_minutes
    out = _run(engine, _check(skill="escape artist", use="squeeze"))[0]
    assert out.dc["value"] == 30 and scene.clock_minutes == before + 1


# --- Fly -------------------------------------------------------------------------------------

def test_a_fly_check_needs_a_way_to_fly():
    scene, engine, pc = _scene()
    out = _run(engine, _check(skill="fly", use="hover"))[0]
    assert out.status == "refused" and "no way to fly" in out.tell


def _flying(pc):
    pc.apply_effect(ActiveEffect(name="fly", kind="buff", key="fly", source="fly",
                                 origin="spell:fly", modifiers=[{
                                     "kind": "speed", "target": "fly", "amount": 60}]))


def test_hover_is_dc_fifteen_and_a_spells_flight_does_not_plummet():
    """CRB, Fly: hover DC 15; "If you are using wings and you fail a Fly check by 5 or
    more, you plummet" — a spell's flight is not wings."""
    scene, engine, pc = _scene(faces={"Fly": 1})
    _flying(pc)
    hp = pc.hp
    out = _run(engine, _check(skill="fly", use="hover", height_ft=40))[0]
    assert out.dc["value"] == 15 and out.verdict == "failure"
    assert "plummets" not in out.tell and pc.hp == hp


def test_a_high_wind_blows_a_small_flier_back_and_batters_it():
    scene, engine, pc = _scene(faces={"Fly": 1})
    _flying(pc)
    pc.size = "small"
    out = _run(engine, _check(skill="fly", use="wind", wind="windstorm"))[0]
    assert out.dc["value"] == 25 and "throws" in out.tell
    assert any(m.value == -8 for m in out.rolls[0].modifiers)
    assert pc.nonlethal > 0


# --- Ride ------------------------------------------------------------------------------------

def _stable(faces=None, fight=False):
    scene, engine, pc = _scene(faces, fight=False)
    horse = scene.add(instantiate("heavy-horse", scene=scene, name="the bay"))
    horse.apply_effect(ActiveEffect(name="travels with you", kind="bond", key="c:travels",
                                    source="company:x", origin="bought:pc",
                                    tags=(states.TRAVELS_WITH_YOU,)))
    if fight:
        scene.add(instantiate("thug", scene=scene, name="the foe"))
        engine._ensure_encounter("pc")
        scene.acted.update(scene.actors)
        scene.positions["pc"], scene.positions[horse.ref] = (5, 5), (6, 5)
        scene.positions["c2"] = (16, 12)
        scene.resync_zones()
    return scene, engine, pc, horse


def test_mounting_the_partys_horse_puts_the_rider_on_it_and_both_know():
    """Audit: Ride had "no resolved use at all". Out of a fight getting on is no roll; the
    rider holds `state.position.mounted`, the horse `state.position.ridden`."""
    scene, engine, pc, horse = _stable()
    out = _run(engine, _check(skill="ride", use="mount"))[0]
    assert out.status == "resolved" and "mounts the bay" in out.tell
    assert bodyskills.mount_of(scene, pc) is horse
    assert bodyskills.rider_of(scene, horse) is pc
    off = _run(engine, _check(skill="ride", use="dismount"))[0]
    assert "gets down" in off.tell and bodyskills.mount_of(scene, pc) is None


def test_a_mounted_rider_moves_on_the_horses_legs():
    """CRB, Mounted Combat: "You move at the mount's speed" — the move the rider declares
    is the horse's, and the rider sits where the horse stands."""
    scene, engine, pc, horse = _stable(faces={"Ride": 20}, fight=True)
    _run(engine, _check(skill="ride", use="mount"))
    assert scene.positions["pc"] == scene.positions[horse.ref]
    _run(engine, {"op": "move", "actor": "pc", "params": {"square": [12, 5]}})
    assert tuple(scene.positions[horse.ref])[:2] == (12, 5)
    assert scene.positions["pc"] == scene.positions[horse.ref]


def test_a_fast_mount_in_a_fight_is_free_on_a_made_dc_twenty_and_a_move_action_if_not():
    scene, engine, pc, horse = _stable(faces={"Ride": 1}, fight=True)
    out = _run(engine, _check(skill="ride", use="mount"))[0]
    assert "a move action" in out.tell and scene.move_spent.get("pc") == scene.round


def test_spurring_adds_ten_feet_and_cuts_the_horse():
    scene, engine, pc, horse = _stable(faces={"Ride": 20}, fight=True)
    _run(engine, _check(skill="ride", use="mount"))
    speed, hp = horse.speed_feet, horse.hp
    scene.round += 1
    out = _run(engine, _check(skill="ride", use="spur"))[0]
    assert out.verdict == "success" and horse.speed_feet == speed + 10 and horse.hp < hp


def test_mounted_combat_turns_a_hit_on_the_horse_once_a_round():
    """CRB feat: "The hit is negated if your Ride check is greater than the opponent's
    attack roll". Before, no feat document existed and a hit on the mount always landed."""
    scene, engine, pc, horse = _stable(faces={"Ride": 20}, fight=False)
    engine.dice.rest = 18
    foe = scene.add(instantiate("thug", scene=scene, name="the foe"))
    engine._ensure_encounter("pc")
    scene.acted.update(scene.actors)
    pc.feats.append("mounted combat")
    assert pc.has_state(bodyskills.MOUNTED_COMBAT)
    scene.positions["pc"], scene.positions[horse.ref] = (5, 5), (6, 5)
    scene.positions[foe.ref] = (8, 5)
    scene.resync_zones()
    mounted = _run(engine, _check(skill="ride", use="mount"))[0]
    assert bodyskills.mount_of(scene, pc) is horse, mounted.tell
    hp = horse.hp
    out = _run(engine, {"op": "attack", "actor": foe.ref, "target": horse.ref})
    swing = next(o for o in out if o.op == "attack")
    assert "Mounted Combat" in swing.tell, swing.tell
    assert horse.hp == hp


# --- Heal: poison, disease, the company's night ----------------------------------------------

def _venom(pc, dc=12):
    aff = {"kind": "poison", "save": "fort", "dc": dc, "cure": 1,
           "effects": [{"ability": "str", "dice": "1", "drain": False}]}
    eff, _ = pc.take_affliction(aff, name="spider venom", source="t", origin="author:test",
                                onset_rounds=1, every_rounds=1, limit=6)
    return eff


def test_treating_poison_lays_four_on_the_next_save_and_that_save_spends_it():
    """CRB, Heal: "If your Heal check exceeds the DC of the poison, the character receives
    a +4 competence bonus on his saving throw against the poison." Audit gap 6: the
    executor rolled every save with nothing a healer could add."""
    scene, engine, pc = _scene(faces={"Heal": 20, "save against": 1})
    _venom(pc)
    out = _run(engine, _check(skill="heal", dc={"band": "average"}))[0]
    assert out.verdict == "success" and "+4 on the next save" in out.tell
    assert pc.has_state("care.treated.poison")
    fort = sum(m.value for m in pc.save_modifiers("fort", {"against": "poison"}))
    assert fort == sum(m.value for m in pc.save_modifiers("fort")) + 4
    got = pc.run_periodic("round", 1, engine.dice)
    assert any(e.get("kind") == "affliction_save" for e in got)
    assert not pc.has_state("care.treated.poison"), "one save, then it is spent"


def test_a_heal_check_that_only_ties_the_poison_does_not_help():
    """"exceeds": RAW, a tie is not enough (owner call recorded in the research note)."""
    scene, engine, pc = _scene()
    _venom(pc, dc=10 + _total(pc, "heal"))
    out = _run(engine, _check(skill="heal", use="treat-poison"))[0]
    assert out.verdict == "failure" and not pc.has_state("care.treated")


def test_companions_heal_in_the_night_and_long_term_care_doubles_it():
    """Round 1 (lane E) found "only your own character heals by resting yet, so long-term
    care given to a companion does not show". Now the company sleeps the same night."""
    def night(cared: bool) -> tuple[int, list]:
        scene, engine, pc, horse = _stable()
        horse.hp = 5
        if cared:
            horse.apply_effect(ActiveEffect(
                name="care", kind="situation", key="long-term-care",
                source="rule:long-term-care", origin="rule:long-term-care",
                tags=("care.long-term",), payload={"by": "pc"}))
        out = _run(engine, {"op": "rest", "actor": "pc", "params": {"kind": "night"}})
        return horse.hp - 5, [o.tell for o in out]

    plain, said = night(False)
    assert plain > 0 and any("the bay heals" in s for s in said), said
    cared, _ = night(True)
    assert cared == 2 * plain
