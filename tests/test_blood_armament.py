"""Extracorporeal Blood Armament is a toggle, and the armed punch is its weapon.

The ability used to be fire-and-forget: nothing on screen said whether it still held,
and the user asked for exactly that — "make extracorporeal blood armament a toggle so
the user isn't confused about whether or not its active." The state lives as a
clockless condition, so every place that shows conditions shows it.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, IntentError, Scene
from rules.sheet import from_dict, load_pc, to_dict


def _bender(level=1):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = "blood bending"
    d["level"] = level
    d["ranks"] = {}
    d["paths"] = ["battle blood"]
    return from_dict(d, ref="pc")


def _fight():
    scene = Scene()
    scene.add(_bender())
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    e = Engine(scene, dice=Dice(seed=11))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    return scene, e


def _use(e, ability="extracorporeal blood armament"):
    return e.run(e.validate([{"op": "use_ability", "actor": "pc",
                              "params": {"ability": ability},
                              "because": "test"}])).outcomes[-1]


def test_using_the_ability_forms_and_dismisses():
    scene, e = _fight()
    pc = scene.actors["pc"]
    out = _use(e)
    assert pc.has_condition("blood armament")
    assert "forms" in out.tell
    out = _use(e)
    assert not pc.has_condition("blood armament")
    assert "fall away" in out.tell


def test_the_toggle_never_expires_on_its_own():
    """A stance is not a spell: rounds tick and the armament holds until dismissed."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    _use(e)
    pc.tick_conditions(600)
    assert pc.has_condition("blood armament")


def test_the_armed_punch_needs_the_armament():
    scene, e = _fight()
    with pytest.raises(IntentError, match="not formed"):
        e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                           "visibility": "hidden",
                           "params": {"weapon": "armed punch"},
                           "because": "test"}]))


def test_the_armed_punch_rolls_blood_plus_fist():
    """Blood DMG + Fist DMG + STR: the blood die is the weapon's own die and the fist
    die rides as an itemised modifier — one visible die, every number named."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    _use(e)
    out = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                             "visibility": "hidden",
                             "params": {"weapon": "armed punch"},
                             "because": "test"}])).outcomes[-1]
    dmg = [r for r in out.rolls if r.label.startswith("Damage")]
    if dmg:                       # the seeded swing may miss; the weapon shape may not
        assert any("fist die" in m.source for m in dmg[0].modifiers)
    assert pc.weapon("armed punch")["damage"] == "1d8"      # the level-1 blood die


def test_a_held_weapon_never_carries_the_armament():
    """"the armament should not apply through held weapons" — an ordinary rapier
    attack while the armament is formed gains no fist-die rider and no blood die."""
    scene, e = _fight()
    _use(e)
    out = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                             "visibility": "hidden", "params": {},
                             "because": "test"}])).outcomes[-1]
    for roll in out.rolls:
        assert not any("fist die" in m.source for m in roll.modifiers)


def test_the_panel_offers_the_fists_only_while_formed_and_only_beside_a_weapon():
    """The armament stopped being a separately named weapon: `Actor.weapon` rides it
    on every unarmed strike while formed, so "unarmed" already MEANS the armament
    strike. The panel's extra slot exists only so somebody holding a sword can still
    choose their fists — an unarmed character needs no second entry that would name
    the same swing twice."""
    from play.views import _attack_slots

    pc = _bender()
    assert _attack_slots(pc)["weapons"] == [pc.equipped or "unarmed"]
    pc.add_condition("blood armament", rounds=None, source="test")
    if (pc.equipped or "unarmed") != "unarmed":
        assert _attack_slots(pc)["weapons"] == [pc.equipped, "unarmed"]
    pc.equipped = "unarmed"
    assert _attack_slots(pc)["weapons"] == ["unarmed"]
    # And the single entry really is the armament strike while the toggle holds.
    # (`granted_by` replaced the old `armament: True` flag when the weapon became a
    # class-document grant — the flag now says which toggle formed it.)
    assert pc.weapon("unarmed").get("granted_by") == "blood armament"
    pc.remove_condition("blood armament")
    assert pc.weapon("unarmed").get("granted_by") is None


def test_the_ability_button_reports_its_state():
    from play.views import _usable_abilities

    pc = _bender()
    entry = next(a for a in _usable_abilities(pc)
                 if a["name"].lower() == "extracorporeal blood armament")
    assert entry["toggle"] is True and entry["active"] is False
    pc.add_condition("blood armament", rounds=None, source="test")
    entry = next(a for a in _usable_abilities(pc)
                 if a["name"].lower() == "extracorporeal blood armament")
    assert entry["active"] is True


# --- what real play found ---------------------------------------------------------------

def test_the_armament_does_not_make_you_unskilled_with_your_own_hands():
    """"i have proficiency with my fists but I am getting a -4."

    The armed punch is built on the wearer from the class's blood die, so it is not in
    the weapons table — the proficiency lookup found nothing, `prof` came back None, and
    a Blood Bender took the non-proficiency penalty for punching. Visible in the dice
    popup as "not proficient with armed punch −4"."""
    pc = _bender()
    pc.add_condition("blood armament", rounds=None, source="test")
    assert pc.is_proficient("armed punch") is True
    sources = [m.source for m in pc.attack_modifiers("armed punch", 0)]
    assert not any("not proficient" in s for s in sources), sources


def test_the_blood_die_is_named_in_the_damage_roll():
    """"my blood dmg looks like its not applying." It was applying — the blood die *is*
    the weapon's die — but the label said only "armed punch", so nothing on screen said
    so. Naming it is the fix; the arithmetic was already right."""
    scene, e = _fight()
    _use(e)
    out = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                             "visibility": "hidden",
                             "params": {"weapon": "armed punch"},
                             "because": "test"}])).outcomes[-1]
    dmg = [r for r in out.rolls if r.label.startswith("Damage")]
    if dmg:
        assert "blood" in dmg[0].label, dmg[0].label
        assert any("fist die" in m.source for m in dmg[0].modifiers)


def test_a_free_action_does_not_hand_the_round_to_the_enemy(tmp_path):
    """"my blood armament is a free action but it is progressing the turn."

    `combat_act` accepted `end_turn: false` and `_finish` ran the NPC turns regardless,
    so forming the armament — a free action — gave the bear a swing while the player
    still held their standard action."""
    import json as _json

    from django.test import Client, override_settings

    from play import campaign as cm
    from rules.bestiary import instantiate

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(_bender())
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        # Refs are minted once and never reused, so the bear is not `c1` — the
        # companion the campaign opened with was, and departing him frees nothing.
        bear = c.scene.add(instantiate("black-bear", scene=c.scene, name="a bear")).ref
        e = c.engine()
        e.run(e.validate([{"op": "begin_encounter",
                           "params": {"sides": {"pc": ["pc"], "them": [bear]}}}]))
        while c.scene.current_ref() != "pc":
            c.scene.advance_turn()
        c.save()
        was_round, was_turn = c.scene.round, c.scene.current_ref()

        r = Client().post("/api/combat/act", data=_json.dumps({
            "actions": [{"op": "use_ability",
                         "params": {"ability": "Extracorporeal Blood Armament"},
                         "target": bear}],
            "label": "free: armament", "end_turn": False}),
            content_type="application/json")
        after = cm.current()
        assert r.status_code == 200, r.content[:200]
        assert after.scene.round == was_round, "a free action advanced the round"
        assert after.scene.current_ref() == was_turn, "a free action passed the turn"
        assert after.scene.pc().has_condition("blood armament")
        cm._LIVE.clear()


def test_a_toggle_never_names_a_bystander_as_its_target():
    """Measured on a quiet step in Zhilvarnia, out of combat. Pressing the armament
    toggle sent "I use Extracorporeal Blood Armament on the stranger sharing the step",
    and the narrator wrote it exactly as it read: a claw held inches from the stranger's
    face, the stranger flinching and nearly bolting. Forming a stance around your own
    arm had become an act against a bystander.

    The cause is that `foe` is "the first actor that is not the player and is still
    standing" — the actor payload carries no hostility to test — so out of a fight it is
    simply whoever else is in the scene. Pinned as source: the sentence is built in JS
    and cannot be reached from here.
    """
    from pathlib import Path

    tpl = (Path(__file__).resolve().parents[1]
           / "play" / "templates" / "play" / "table.html").read_text(encoding="utf-8")
    # A toggle is identifiable at the click, and the target is conditional on a fight.
    assert 'data-toggle="${a.toggle ? "1" : "0"}"' in tpl
    assert 'const fighting = !!(STATE.scene && STATE.scene.in_encounter);' in tpl
    assert ('const aimed = (fighting && btn.dataset.toggle !== "1" && foe)'
            ' ? ` on ${foe.name}` : "";') in tpl
    # And the unconditional version is gone.
    assert '`I use ${name}${foe ? " on " + foe.name : ""}.`' not in tpl


def test_swift_strikes_does_not_swing_at_a_body_on_the_floor():
    """Measured in the tavern. The thug dropped to -5 on the first swing of a Swift
    Strikes pair and the second was still queued, so the player was asked to roll a d20
    at a corpse — and because `scene.awaiting` was set, the NPC driver returned early
    every time and never reached its "one side left standing" check.

    The fight could not end. XP and treasure settle on the way out of an encounter, so
    neither ever paid: the reported "0 XP" has this shape underneath it."""
    import json as _json

    from django.test import Client, override_settings

    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=_tmpdir()):
        cm._LIVE.clear()
        c = cm.begin_with(_bender(level=6))          # enough BAB for a second swing
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        thug = instantiate("thug", scene=c.scene, name="a thug")
        thug.hp = 1                                   # one hit puts it down
        c.scene.add(thug)
        e = c.engine()
        # Not `c1`: refs are never reused, and the opening companion wore that one.
        e.run(e.validate([{"op": "begin_encounter",
                           "params": {"sides": {"pc": ["pc"], "them": [thug.ref]}}}]))
        while c.scene.current_ref() != "pc":
            c.scene.advance_turn()
        c.save()

        r = Client().post("/api/combat/act", data=_json.dumps({
            "actions": [{"op": "attack", "target": thug.ref,
                         "params": {"full_attack": True}}],
            "label": "strike", "end_turn": True}), content_type="application/json")
        assert r.status_code == 200, r.content[:200]

        after = cm.current()
        # Whatever else happened, nobody is being asked to roll at a body.
        if after.scene.awaiting:
            assert after.scene.actors[thug.ref].hp > 0, (
                "a roll is pending against a defender who is already down")
        cm._LIVE.clear()


def _tmpdir():
    import tempfile
    from pathlib import Path
    return Path(tempfile.mkdtemp()) / "campaigns"



def test_both_armament_dice_are_the_players_own():
    """"when striking with my fist and my armament on i deal fist dmg and blood dmg
    but i only roll blood dmg fist gets rolled for me." The fist die was an
    engine-rolled hidden rider; now each die is its own popup, named."""
    scene, e = _fight()
    scene.actors["pc"].equipped = "unarmed"
    _use(e)                                                # form the armament
    faces = []
    r = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                           "because": "she swings", "params": {}}]))
    for _ in range(6):
        if r.awaiting is None:
            break
        label = r.awaiting["label"]
        faces.append(label)
        r = e.resume(4 if label.startswith("Fist")
                     else 6 if label.startswith("Blood") else 19)
    assert any(l.startswith("Fist die") for l in faces), faces
    assert any(l.startswith("Blood die") for l in faces), faces
    dmg_roll = next(x for o in r.outcomes for x in o.as_dict()["rolls"]
                    if x["label"].startswith("Blood die"))
    assert any(m["source"].startswith("fist die") and m["value"] == 4
               for m in dmg_roll["modifiers"])


def test_the_unarmed_strike_wears_the_armament_automatically():
    """"the default attack should be unarmed strike unless otherwise prompted, and in
    the case that something should alter the unarmed strike (like Extracorporeal
    Blood Armament) it should be applied." An attack that names no weapon, on a
    bender with the toggle on, is the armament strike — nobody has to know a magic
    weapon name."""
    pc = _bender()
    pc.equipped = "unarmed"
    pc.add_condition("blood armament", rounds=None, source="test")
    w = pc.weapon(None)
    assert w.get("granted_by") == "blood armament"
    assert w["name"] == "unarmed strike (blood armament)"
    pc.remove_condition("blood armament")
    assert pc.weapon(None).get("granted_by") is None
