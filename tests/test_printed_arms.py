"""A stat block's weapons are things the creature carries, on its sheet like anyone's.

Measured 2026-10-28 (engine probe, the escort job's guard template): a disarm beating the
guard's CMD by 15 told "Guard holds nothing that can be knocked loose", and its next turn
swung the halberd. The same for the ogre's greatclub (by 12) and the wagon driver's club
(by 20). An imported block came in as `equipped` None and `weapons` [] — its halberd a
line of print read through `wielded_key` — while a hand-written thug carried his sap on
the sheet. Two shapes for one fact, and every reader of the hand needed a fallback for
the second: the disarm and sunder read `equipped`; `wear` refused the guard's own heavy
flail; loot handed over nothing from a fallen ogre; the attack gate passed any printed
name ("the stat block is the creature's inventory"), so a halberd lying on the ground
would have been swingable by name.

The fix is one shape (`Actor.take_up_printed_arms`, run by `from_dict` for a spawn and a
load alike): the print's made weapons go on `weapons`, the primary in `equipped`. The
numbers stay the print's, read live. Owner rulings 2026-10-28: printed weapons are real,
lootable items; saves made before this are brought to the same shape on load.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules import reactions
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import from_dict, load_pc, to_dict


@pytest.fixture(autouse=True)
def _the_provoked_swing_waived(monkeypatch):
    """The manoeuvre's own provoked swing would spend the aimed CMB face (as in
    tests/test_maneuver_outcomes.py)."""
    monkeypatch.setattr(reactions, "provoked_by_maneuver", lambda *a, **k: [])


class _AimedCMB(Dice):
    def __init__(self, face: int = 20):
        super().__init__(seed=20261028)
        self.face = face

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if "(CMB)" in (label or ""):
            return self.given(self.face, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _fight(template: str):
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    body = instantiate(template, scene=scene)
    scene.add(body)
    engine = Engine(scene, _AimedCMB())
    engine._ensure_encounter("pc")
    scene.positions["pc"], scene.positions[body.ref] = (6, 10), (7, 10)
    scene.resync_zones()
    pc = scene.get("pc")
    pc.abilities["str"] = 30
    for a in (pc, body):
        a.hp = a.hp_max = 400
    return scene, engine, body


def _settle(engine, res):
    while res.awaiting:
        res = engine.resume(min(10, res.awaiting.get("max", 20)))
    return res


def _manoeuvre(engine, body, key: str):
    res = _settle(engine, engine.run(engine.validate([{
        "op": "attack", "actor": "pc", "target": body.ref, "visibility": "hidden",
        "params": {"manoeuvre": key}}])))
    return next(o for o in res.outcomes if o.op == "attack")


# --- the defect ---------------------------------------------------------------------------

@pytest.mark.parametrize("template, weapon", [
    ("guard", "halberd"), ("ogre", "greatclub"), ("varisian-wagon-driver", "club")])
def test_a_disarm_told_the_creature_held_nothing_while_it_swung_a_printed_weapon(template,
                                                                                  weapon):
    """By 15, 12 and 20 on 2026-10-28, each told "holds nothing that can be knocked
    loose" with the weapon still swung next turn."""
    scene, engine, body = _fight(template)
    assert body.wielded_key() == weapon
    out = _manoeuvre(engine, body, "disarm")
    assert out.verdict == "success" and f"drops the {weapon}" in out.tell, out.tell
    assert body.equipped == "unarmed" and weapon not in body.weapons
    assert scene.out_of_hand(body.ref, weapon) is not None, "at its feet, on the ledger"


def test_a_printed_halberd_on_the_ground_is_not_swung_by_name():
    """The gate passed every printed name; the print is the numbers, not the hand."""
    scene, engine, guard = _fight("guard")
    _manoeuvre(engine, guard, "disarm")
    with pytest.raises(IntentError, match="halberd lies on the ground"):
        engine.validate([{"op": "attack", "actor": guard.ref, "target": "pc",
                          "params": {"weapon": "halberd"}}])
    assert "halberd" not in guard.printed_arms()   # nor offered to the creature's turn


def test_the_guard_takes_its_halberd_back_up_and_swings_the_books_numbers():
    """The re-arm rules (docs/creature-rearms.md) apply to print as to the thug's sap:
    pick it up, a move action, then one swing — at the stat block's +5 and 1d10, not the
    weapons table's."""
    scene, engine, guard = _fight("guard")
    printed = guard.weapon("halberd")
    _manoeuvre(engine, guard, "disarm")
    raw, repairs = judgement.rearm(scene, guard.ref, [
        {"op": "attack", "actor": guard.ref, "target": "pc"}])
    assert [r["op"] for r in raw] == ["give", "attack"], repairs
    _settle(engine, engine.run(engine.validate(raw)))
    assert guard.equipped == "halberd"
    now = guard.weapon(guard.wielded_key())
    assert (now["damage"], now["stat_block"]["bonuses"]) == (
        printed["damage"], printed["stat_block"]["bonuses"])


def test_a_halberd_knocked_out_of_reach_leaves_the_printed_flail_to_draw():
    """`wear` refused "heavy flail": the guard was not carrying it, by its sheet."""
    scene, engine, guard = _fight("guard")
    _manoeuvre(engine, guard, "disarm")
    scene.out_of_hand(guard.ref, "halberd")["square"] = [20, 20]
    assert judgement.rearm_step(scene, guard.ref) == ("draw", "heavy-flail")


def test_sunder_breaks_a_printed_halberd():
    """Sunder read `equipped` too, and found nothing to break."""
    scene, engine, guard = _fight("guard")
    out = _manoeuvre(engine, guard, "sunder")
    assert "halberd takes" in out.tell, out.tell


def test_a_fallen_ogre_gives_up_its_greatclub():
    """Owner ruling 2026-10-28: printed weapons are lootable, as 1e's NPC gear is."""
    scene, engine, ogre = _fight("ogre")
    ogre.hp = -20
    ogre.die("test")
    res = _settle(engine, engine.run(engine.validate([
        {"op": "loot", "actor": "pc", "params": {"from_": ogre.ref}}])))
    assert any("greatclub" in o.tell and "javelin" in o.tell for o in res.outcomes)


# --- the body is not an item ----------------------------------------------------------------

def test_a_bite_is_not_put_in_a_hand_and_cannot_be_knocked_loose():
    scene, engine, dog = _fight("riding-dog")
    assert (dog.equipped, dog.weapons, dog.wielded_key()) == (None, [], "bite")
    out = _manoeuvre(engine, dog, "disarm")
    assert "holds nothing that can be knocked loose" in out.tell, out.tell


def test_a_lizardfolk_with_a_morningstar_on_its_sheet_still_bites():
    """A carried list now exists beside printed natural attacks; the carried-list check
    must not refuse the body's own."""
    scene, engine, lizard = _fight("lizardfolk")
    assert lizard.equipped == "morningstar"
    engine.validate([{"op": "attack", "actor": lizard.ref, "target": "pc",
                      "params": {"weapon": "bite"}}])


@pytest.mark.parametrize("template, held, carried, not_carried", [
    # The fist stands on the table's "unarmed" row, which calls itself wieldable: 489
    # unarmed-strike and flurry attacks put "unarmed" on 1e monks' weapons lists.
    ("battle-monk", None, ["kama"], ["unarmed"]),
    # 97 printed bombs and 9 alchemist's fires went into packs as things to carry: a
    # bomb is made and thrown in the one action, never held (`weapons.wieldable`).
    ("chemist", "morningstar", ["morningstar"], ["bomb"]),
    # Armour spikes are the suit's, and the fiend-born rager prints them first: the
    # first cut put them in its hand, where a disarm could knock them loose.
    ("fiend-born-rager", None, [], ["spiked-armor"]),
])
def test_only_what_a_hand_can_hold_goes_on_the_sheet(template, held, carried, not_carried):
    """Measured 2026-10-28 over the 7,111 blocks, on the commit before this one."""
    _, _, body = _fight(template)
    assert body.equipped == held
    assert all(w in body.weapons for w in carried), body.weapons
    assert not any(w in body.weapons for w in not_carried), body.weapons


def test_a_monk_still_strikes_with_its_printed_fist():
    """Left as the body, the fist still swings at the print's numbers."""
    _, engine, monk = _fight("battle-monk")
    assert monk.wielded_key() == "unarmed strike"
    assert monk.weapon(monk.wielded_key()).get("stat_block")
    engine.validate([{"op": "attack", "actor": monk.ref, "target": "pc",
                      "params": {"weapon": "unarmed strike"}}])


# --- saves ----------------------------------------------------------------------------------

def test_a_save_made_before_this_loads_with_the_guards_weapons_on_its_sheet():
    """Owner ruling 2026-10-28: normalise on load. The escort saves held every caravan
    hand as `equipped` None, `weapons` [] — and no marker."""
    _, _, guard = _fight("guard")
    old = to_dict(guard)
    old.update(equipped=None, weapons=[])
    old.pop("print_armed", None)
    loaded = from_dict(old)
    assert loaded.equipped == "halberd"
    assert loaded.weapons == ["halberd", "heavy-flail", "sap", "heavy-crossbow"]


def test_a_weapon_taken_off_a_living_guard_is_not_handed_back_by_the_print_on_load():
    """Why a marker and not "equipped is None": the print would re-arm it every load."""
    _, _, guard = _fight("guard")
    guard.weapons.remove("sap")
    assert "sap" not in from_dict(to_dict(guard)).weapons


def test_a_save_without_a_printed_weapon_round_trips_byte_for_byte():
    _, _, dog = _fight("riding-dog")
    assert "print_armed" not in to_dict(dog)
