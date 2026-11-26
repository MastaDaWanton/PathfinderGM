"""The blood armament takes weapon special abilities, paid in non-lethal damage per turn.

Owner ask 2026-11-26 A2: "even at lvl 1 I should be able to take non-lethal dmg to give my
Extracorporeal blood armament things like corrosive, keen, or vicious." The class: "Apply
special abilities (Corrosive, Keen, Vicious, Advancing) by paying Non-Lethal costs per
turn." Measured on 0.5.1 before this: "Extracorporeal Blood Armament (keen)" toggled the
armament like the bare name did — no property, no price, a 20/x2 armed punch — because
nothing in the class document or the engine knew the sentence existed.
"""
from __future__ import annotations

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene, _ward_tell
from rules.sheet import from_dict, load_pc, to_dict
from tests._board import face_to_face

ARMAMENT = "extracorporeal blood armament"


def _fight(seed=11):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "blood bending", "level": 1, "ranks": {}, "paths": ["battle blood"],
              "hp": 40, "hp_max": 40})
    scene = Scene()
    scene.add(from_dict(d, ref="pc"))
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    e = Engine(scene, dice=Dice(seed=seed))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    face_to_face(scene)
    return scene, e


def _use(e, ability):
    return e.run(e.validate([{"op": "use_ability", "actor": "pc",
                              "params": {"ability": ability},
                              "because": "test"}])).outcomes[-1]


def test_keen_forms_the_armament_pays_and_widens_the_threat_range():
    """Before: the armed punch threatened on a 20 whatever was asked for. Keen (CRB) doubles
    it to 19-20, at 2d6 non-lethal (the class's own price for a +1, Blood Booster)."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    assert pc.weapon("armed punch")["crit_range"] == 20
    out = _use(e, f"{ARMAMENT} (keen)")
    assert out.status != "refused", out.tell
    assert pc.has_condition("blood armament")            # formed on the way
    assert 2 <= pc.nonlethal <= 12                       # 2d6, paid
    assert pc.weapon("armed punch")["crit_range"] == 19
    assert pc.weapon("unarmed")["crit_range"] == 19      # the fist IS the armament now
    assert "keen" in out.tell and "2d6 non-lethal each turn" in out.tell
    assert any(r.label.endswith("the cost") for r in out.rolls)


def test_corrosive_and_vicious_ride_the_armed_punch_as_the_enchanters_riders():
    """The same property documents a forged blade carries: corrosive's 1d6 acid and
    vicious's 2d6 to the foe and 1d6 back, on the armament's own row."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    _use(e, f"{ARMAMENT} (corrosive)")
    _use(e, f"{ARMAMENT} (vicious)")
    riders = (pc.weapon("armed punch").get("magic") or {}).get("riders") or []
    said = {(r.get("dice"), r.get("damage_type"), r.get("recipient", "target"))
            for r in riders}
    assert ("1d6", "acid", "target") in said
    assert ("2d6", "untyped", "target") in said and ("1d6", "untyped", "self") in said
    assert all(r.get("origin") == f"ability:battle blood/{ARMAMENT}" for r in riders)
    assert len(pc.granted_properties("blood armament")) == 2


def test_a_corrosive_hit_deals_its_acid():
    """End to end through the attack op: a hit with the corrosive armament names the acid."""
    for seed in range(1, 40):
        scene, e = _fight(seed)
        _use(e, f"{ARMAMENT} (corrosive)")
        out = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                                 "visibility": "hidden", "params": {"weapon": "armed punch"},
                                 "because": "test"}])).outcomes[-1]
        if "acid" in out.tell:
            return
    raise AssertionError("forty swings with a corrosive armament and no acid told")


def test_the_price_is_paid_again_each_round_and_told():
    """"per turn": the top of every round of the fight charges it, and the round's tell
    says so (law 3)."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    _use(e, f"{ARMAMENT} (keen)")
    had = pc.nonlethal
    records = pc.run_periodic("round", 1, e.dice)
    paid = [r for r in records if r["kind"] == "upkeep_paid"]
    assert paid and pc.nonlethal == had + paid[0]["amount"]
    assert "non-lethal to hold Keen (Extracorporeal Blood Armament)" in _ward_tell(scene, paid[0])


def test_naming_it_again_lifts_it_and_dismissing_the_armament_lifts_all():
    scene, e = _fight()
    pc = scene.actors["pc"]
    _use(e, f"{ARMAMENT} (keen)")
    _use(e, f"{ARMAMENT} (corrosive)")
    had = pc.nonlethal
    out = _use(e, f"{ARMAMENT} (keen)")
    assert "lets the keen go" in out.tell and pc.nonlethal == had
    assert pc.weapon("armed punch")["crit_range"] == 20
    assert pc.has_condition("blood armament")
    _use(e, ARMAMENT)
    assert not pc.has_condition("blood armament")
    assert pc.granted_properties("blood armament") == []


def test_advancing_is_refused_with_the_reason_and_costs_nothing():
    scene, e = _fight()
    pc = scene.actors["pc"]
    out = _use(e, f"{ARMAMENT} (advancing)")
    assert out.status == "refused" and "no swift step" in out.tell
    assert pc.nonlethal == 0 and not pc.has_condition("blood armament")
    out = _use(e, f"{ARMAMENT} (flaming)")
    assert out.status == "refused" and "(keen)" in out.tell


def test_time_out_of_a_fight_lets_it_go():
    """Nobody pays per turn across a ten-minute wait, so it lapses — told, not silent."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    _use(e, f"{ARMAMENT} (keen)")
    scene.end_encounter()
    scene.advance(10)
    assert pc.granted_properties("blood armament") == []
    assert pc.weapon("armed punch")["crit_range"] == 20


def test_the_panel_offers_the_choices_on_the_toggle():
    from play.views import _usable_abilities

    scene, _ = _fight()
    entry = next(a for a in _usable_abilities(scene.actors["pc"])
                 if a["name"] == "Extracorporeal Blood Armament")
    assert entry["toggle"] and entry["choices"] == ["corrosive", "keen", "vicious"]


def _bender_at(level, paths):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "blood bending", "level": level, "ranks": {}, "paths": paths})
    from rules import classes

    pc = from_dict(d, ref="pc")
    classes.apply(pc)
    return pc


def test_unbalancing_strike_exists_at_third_level():
    """Audit 2026-11-26: Unbalancing Strike (level 3) had a pool gated on an ability no
    document defined, so the pool was never made and the name was refused "no ability
    called unbalancing strike". Now a charge the next unarmed swing spends: Fortitude or
    flat-footed for a round."""
    from rules import class_abilities

    pc = _bender_at(3, ["battle blood"])
    assert "Unbalancing Strike" in class_abilities.names(pc)
    assert pc.pool("unbalancing strike") is not None
    scene = Scene()
    scene.add(pc)
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    e = Engine(scene, dice=Dice(seed=3))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    face_to_face(scene)
    out = e.run(e.validate([{"op": "use_ability", "actor": "pc", "target": "c1",
                             "params": {"ability": "unbalancing strike"},
                             "because": "test"}])).outcomes[-1]
    assert out.status != "refused", out.tell
    assert pc.has_state("buff.charged")
    assert "Unbalancing Strike" not in class_abilities.names(_bender_at(2, ["battle blood"]))


def test_a_rung_named_passive_is_no_button():
    """Audit 2026-11-26: "Iron Clot (DR 2/-)" sat on the bar as a standard action that
    could only answer "always active", because the panel asked the tier's name, not the
    resolved one, whether it was passive."""
    from play.views import _usable_abilities

    names = {a["name"] for a in _usable_abilities(_bender_at(3, ["coagulator"]))}
    assert not any(n.startswith("Iron Clot") for n in names)
    names = {a["name"] for a in _usable_abilities(_bender_at(1, ["blood commander"]))}
    assert not any(n.startswith("Blood Buffer") for n in names)


def test_the_brief_tells_the_narrator_the_choices_and_the_passives():
    """The brief listed every path name bare, so the narrator met "Extracorporeal Blood
    Armament" with no word of keen, and Sanguine Spray (which the engine does not run) as a
    thing the character can do."""
    from gm.prompts import _path_ability_said

    pc = _bender_at(1, ["battle blood"])
    said = _path_ability_said(pc, "Extracorporeal Blood Armament")
    assert "corrosive, keen, vicious" in said and "a stance" in said
    assert _path_ability_said(pc, "Swift Strikes").startswith("always active")
    coag = _bender_at(1, ["coagulator"])
    assert "does not run it yet" in _path_ability_said(coag, "Sanguine Spray")
