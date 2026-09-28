"""A manoeuvre's tell says only what the engine did, and the engine does what it says.

Found 2026-09-27 on the tells-by-name branch, reading `rules/tables.py` MANEUVERS beside
`Engine._resolve_maneuver`: seven of the ten manoeuvres told the narrator an outcome that
nothing in state carried.

- disarm: "the thug drops one carried item" — his sap still `equipped`, still swingable;
  the backfire's "drops the weapon used for the disarm" left it in the hand too.
- steal: "takes an object Kesst Vayr is carrying" — no item moved anywhere.
- bull rush / drag / reposition / overrun: "pushed back 5 feet", "dragged 5 feet",
  "moved through the space" — `Scene.positions` untouched; the map showed both where they
  started.
- dirty trick: "blinded, dazzled, deafened, entangled, shaken or sickened for 1 round" —
  six claimed, one (dazzled) applied, and that one until dismissed rather than a round.

The narrator is fed tells and nothing else (the third law), so each was prose asserting
a fact the next beat could not find: the thug "disarmed" swings the same sap, the purse
"stolen" is still his to pay with. The rules are the Core Rulebook's and the APG's
(aonprd.com, Combat Maneuvers); where the book is silent — where a dropped weapon lands —
the choice is Greater Disarm's implication and ROM's `disarm()`: at the wielder's feet.
"""
from __future__ import annotations

import re

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from rules.tables import MANEUVERS

PC = "Kesst Vayr"
THUG = "the thug"


class _AimedCMB(Dice):
    """Every CMB d20 lands on the face asked for; everything else rolls as usual."""

    def __init__(self, face: int):
        super().__init__(seed=20260927)
        self.face = face

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if "(CMB)" in (label or ""):
            return self.given(self.face, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _fight(face: int = 20, strength: int = 30, by: str = "pc"):
    """The player and a thug, side by side on the map a fight lays, with the CMB face
    aimed and the attacker's Strength set so the margin lands where the branch needs it
    (face 20 with Str 30 beats CMD by 10 or more; a 1 with Str 1 fails by 10)."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name=THUG))
    engine = Engine(scene, _AimedCMB(face))
    engine._ensure_encounter("pc")
    scene.positions["pc"], scene.positions["c1"] = (6, 10), (7, 10)
    scene.resync_zones()
    scene.get(by).abilities["str"] = strength
    return scene, engine, scene.get("pc"), scene.get("c1")


def _do(engine, key: str, by: str = "pc", **params):
    target = "c1" if by == "pc" else "pc"
    res = engine.run(engine.validate([{
        "op": "attack", "actor": by, "target": target, "visibility": "hidden",
        "params": {"manoeuvre": key, **params}}]))
    while res.awaiting:
        res = engine.resume(engine.dice.face)
    return next(o for o in res.outcomes if o.op == "attack")


def _state(scene) -> dict:
    """Everything a manoeuvre could claim to have changed, for a before/after diff."""
    out = {}
    for ref, a in scene.actors.items():
        out[ref] = (sorted(e.key for e in a.effects if e.kind == "condition"),
                    list(a.weapons), a.equipped, a.shield, dict(a.goods), dict(a.purse),
                    dict(a.inventory), scene.positions.get(ref),
                    {k: i.hp for k, i in a.gear.items()})
    out["props"] = [dict(r) for r in scene.props]
    return out


# --- the ratchet ------------------------------------------------------------------------

def test_every_manoeuvre_row_names_what_makes_its_effect_true():
    """A row's `effect` is a claim. It must be carried by a `condition`, the sunder's
    `damages_item`, or an `outcome` the engine has an applicator for — seven rows had
    none of the three on 2026-09-27, and the narrator was told all seven."""
    unbacked = [key for key, m in MANEUVERS.items()
                if not (m.get("condition") or m.get("damages_item")
                        or m.get("outcome") in Engine._MANEUVER_OUTCOMES)]
    assert not unbacked, f"these rows claim an effect nothing applies: {unbacked}"


@pytest.mark.parametrize("key", sorted(MANEUVERS))
def test_every_successful_manoeuvre_changes_the_state_it_tells_of(key):
    """Before/after, on a success by 10 or more: the tell is not allowed to be the only
    thing that happened. Seven of ten failed this on 2026-09-27."""
    scene, engine, pc, thug = _fight()
    thug.goods["dice of bone"] = 1      # something loose to steal
    before = _state(scene)
    out = _do(engine, key)
    assert out.verdict == "success", out.tell
    assert _state(scene) != before, f"{key}: {out.tell!r} and nothing changed"


# --- disarm -----------------------------------------------------------------------------

def test_a_disarm_tell_said_the_thug_dropped_his_sap_and_his_sap_was_still_equipped():
    scene, engine, pc, thug = _fight(face=20, strength=14)
    out = _do(engine, "disarm")
    assert out.verdict == "success" and out.margin < 10, out.tell
    assert "the thug drops the sap" in out.tell, out.tell
    assert thug.equipped == "unarmed"
    assert "sap" not in thug.weapons and "dagger" in thug.weapons
    rec = scene.prop_named("the thug's sap")
    assert rec is not None and rec["owner"] == "c1" and rec["from_"] == "sap"
    assert rec.get("at") == scene.at and not rec.get("held_by"), "at his feet"


def test_a_disarmed_weapon_cannot_be_swung_by_name_even_with_an_empty_weapons_list():
    """The carried-list check is skipped when the list is empty, so a thug disarmed of
    his only weapon could name the sap on the ground and hit with it."""
    scene, engine, pc, thug = _fight(face=20, strength=14)
    thug.weapons = ["sap"]
    _do(engine, "disarm")
    assert thug.weapons == []
    with pytest.raises(IntentError, match="sap lies on the ground"):
        engine.validate([{"op": "attack", "actor": "c1", "target": "pc",
                          "params": {"weapon": "sap"}}])


def test_beating_cmd_by_ten_empties_both_hands_and_the_shield_stops_counting():
    """"The target drops the items in both hands." A held shield is one of them, and
    its AC goes with it — derived from the slot, so nothing needs subtracting."""
    scene, engine, pc, thug = _fight(face=20, by="c1")
    pc.shield = "light shield"
    pc.add_condition("stunned")         # the thug's CMB is a flat 3; +4 against the stunned
    ac_with = pc.ac()
    out = _do(engine, "disarm", by="c1")
    assert out.margin >= 10, out.tell
    assert "Kesst Vayr drops the rapier and the light shield" in out.tell, out.tell
    assert pc.equipped == "unarmed" and pc.shield == "none"
    assert pc.ac() == ac_with - 1
    lying = {r["name"] for r in scene.props_here()}
    assert {"Kesst Vayr's rapier", "Kesst Vayr's light shield"} <= lying


def test_picking_your_weapon_back_up_puts_it_in_your_hand():
    scene, engine, pc, thug = _fight(face=20, strength=14, by="c1")
    _do(engine, "disarm", by="c1")
    assert pc.equipped == "unarmed" and "rapier" not in pc.weapons
    res = engine.run(engine.validate([{"op": "give", "actor": "pc", "target": "pc",
                                       "params": {"item": "rapier"}}]))
    # Stooping for it beside the armed thug provokes (Table 7-2; tests/
    # test_creature_rearms.py) — his swing lands first, then the hand closes on it.
    assert [o.op for o in res.outcomes] == ["attack", "give"]
    assert res.outcomes[-1].tell == ("Kesst Vayr takes the rapier back up off the "
                                     "ground; it is in hand again."), res.outcomes[-1].tell
    assert pc.equipped == "rapier" and "rapier" in pc.weapons
    assert scene.prop_named("Kesst Vayr's rapier")["held_by"] == "pc"
    engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                      "params": {"weapon": "rapier"}}])     # swingable again


def test_an_unarmed_disarm_catches_what_it_knocks_loose():
    """"If you successfully disarm your opponent without using a weapon, you may
    automatically pick up the item dropped" — and it stays the thug's sap, so the thug
    is refused it by name while it is in the player's hand."""
    scene, engine, pc, thug = _fight(face=20, strength=14)
    pc.equipped = "unarmed"
    out = _do(engine, "disarm")
    assert "Kesst Vayr picks up the sap" in out.tell, out.tell
    assert pc.equipped == "sap"
    rec = scene.prop_named("the thug's sap")
    assert rec["held_by"] == "pc" and rec["owner"] == "c1"
    with pytest.raises(IntentError, match="sap is in Kesst Vayr's hands"):
        engine.validate([{"op": "attack", "actor": "c1", "target": "pc",
                          "params": {"weapon": "sap"}}])


def test_a_disarm_that_fails_by_ten_drops_the_attackers_own_weapon():
    """The backfire said "drops the weapon used for the disarm" and left it in hand."""
    scene, engine, pc, thug = _fight(face=1, strength=1, by="c1")
    out = _do(engine, "disarm", by="c1")
    assert out.margin <= -10 and "The thug drops the sap." in out.tell, out.tell
    assert thug.equipped == "unarmed" and "sap" not in thug.weapons
    assert scene.prop_named("the thug's sap")["owner"] == "c1"


def test_a_fist_that_fails_a_disarm_drops_nothing_and_says_nothing_dropped():
    scene, engine, pc, thug = _fight(face=1, strength=1, by="c1")
    thug.equipped = "unarmed"
    out = _do(engine, "disarm", by="c1")
    assert "drops" not in out.tell and not scene.props, out.tell


# --- steal ------------------------------------------------------------------------------

def test_a_steal_tell_said_an_object_was_taken_and_nothing_moved():
    """The kit a thug was generated with collapses on the first hand in his pockets;
    the loose thing goes, from his inventory into the thief's, owner recorded."""
    scene, engine, pc, thug = _fight()
    out = _do(engine, "steal")
    assert re.search(r"Kesst Vayr takes the (dice of bone|strip of dried meat) "
                     r"from the thug", out.tell), out.tell
    took = next(e for e in out.effects if e["kind"] == "stolen")
    key = took["item"].replace(" ", "-")
    assert pc.inventory.get(key) == 1 and key not in thug.inventory
    assert scene.prop_named(took["prop"])["owner"] == "c1"


def test_a_fastened_purse_is_worth_five_cmd_and_all_of_its_coin_moves():
    scene, engine, pc, thug = _fight()
    thug.kit_pending = {}               # no 2d4 sp collapsing in on top
    thug.purse = {"sp": 7}
    out = _do(engine, "steal", item="his coin purse")
    assert any("fastened" in b["source"] for b in out.dc["breakdown"]), out.dc
    assert "Kesst Vayr takes the coin purse (7 silver pieces) from the thug" in out.tell,         out.tell
    assert thug.purse == {} and pc.purse.get("sp") == 7


def test_a_sheathed_dagger_can_be_stolen_and_is_then_not_the_thugs_to_swing():
    scene, engine, pc, thug = _fight()
    out = _do(engine, "steal", item="dagger")
    assert "takes the dagger from the thug" in out.tell, out.tell
    assert "dagger" in pc.weapons and "dagger" not in thug.weapons
    with pytest.raises(IntentError, match="dagger is in Kesst Vayr's hands"):
        engine.validate([{"op": "attack", "actor": "c1", "target": "pc",
                          "params": {"weapon": "dagger"}}])


@pytest.mark.parametrize("item,why", [
    ("sap", "is holding the sap.*disarm"),
    ("leather", "worn close"),
    ("crown of stars", "has no crown of stars"),
])
def test_what_a_steal_cannot_take_is_refused_before_the_roll(item, why):
    scene, engine, pc, thug = _fight()
    res = engine.run(engine.validate([{
        "op": "attack", "actor": "pc", "target": "c1",
        "params": {"manoeuvre": "steal", "item": item}}]))
    assert not res.awaiting, "no die is handed over for a steal that cannot happen"
    assert re.search(why, res.outcomes[0].tell), res.outcomes[0].tell


# --- dirty trick ------------------------------------------------------------------------

def test_a_dirty_trick_told_six_conditions_and_applied_one_until_dismissed():
    scene, engine, pc, thug = _fight(face=20, strength=14)
    out = _do(engine, "dirty trick", trick="blinded")
    rounds = 1 + out.margin // 5
    assert thug.has_condition("blinded") and not thug.has_condition("dazzled")
    eff = next(e for e in thug.effects if e.key == "blinded")
    assert eff.rounds_left == rounds
    assert f"the thug is blinded for {rounds} round" in out.tell, out.tell
    assert "deafened" not in out.tell and "sickened" not in out.tell
    thug.tick_effects(rounds)
    assert not thug.has_condition("blinded"), "it ends; it is not a permanent penalty"


def test_a_dirty_trick_with_no_trick_named_dazzles_for_its_rounds():
    scene, engine, pc, thug = _fight(face=20, strength=14)
    out = _do(engine, "dirty trick")
    assert next(e for e in thug.effects if e.key == "dazzled").rounds_left == \
        1 + out.margin // 5


def test_a_trick_that_is_not_one_of_the_six_is_refused_at_parse():
    scene, engine, pc, thug = _fight()
    with pytest.raises(IntentError, match="blinded, dazzled"):
        engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                          "params": {"manoeuvre": "dirty trick", "trick": "stunned"}}])


# --- the moving four --------------------------------------------------------------------

def test_a_bull_rush_tell_said_pushed_back_and_the_square_never_changed():
    scene, engine, pc, thug = _fight(face=20, strength=30)
    out = _do(engine, "bull rush")
    want = 5 + out.margin // 5 * 5
    assert f"the thug is pushed back {want} feet" in out.tell, out.tell
    assert scene.positions["c1"] == (7 + want // 5, 10)
    assert scene.positions["pc"] == (6, 10), "the pusher did not choose to follow"
    moved = next(e for e in out.effects if e["kind"] == "position")
    assert moved["feet"] == want and moved["forced"] == "bull rush"


def test_a_push_stops_at_a_wall_and_says_how_far_it_got():
    scene, engine, pc, thug = _fight(face=20, strength=30)
    scene.grid.blocked.add((9, 10))
    out = _do(engine, "bull rush")
    assert scene.positions["c1"] == (8, 10)
    assert "pushed back only 5 feet before the way is blocked" in out.tell, out.tell


def test_a_push_against_a_body_goes_nowhere_and_says_so():
    scene, engine, pc, thug = _fight(face=20, strength=30)
    other = scene.add(instantiate("thug", scene=scene, name="the other thug"),
                      at=(8, 10))
    out = _do(engine, "bull rush")
    assert scene.positions["c1"] == (7, 10) and scene.positions[other.ref] == (8, 10)
    assert "driven against something solid and goes nowhere" in out.tell, out.tell


def test_a_drag_moves_both_and_they_are_still_side_by_side():
    scene, engine, pc, thug = _fight(face=20, strength=14)
    out = _do(engine, "drag")
    want = 5 + out.margin // 5 * 5
    squares = want // 5
    assert scene.positions["pc"] == (6 - squares, 10)
    assert scene.positions["c1"] == (7 - squares, 10)
    assert f"the thug is dragged {want} feet" in out.tell, out.tell


def test_a_reposition_goes_where_it_was_aimed_within_reach():
    scene, engine, pc, thug = _fight(face=20, strength=14)
    out = _do(engine, "reposition", square=[6, 11])
    assert scene.positions["c1"] == (6, 11), out.tell
    assert "Kesst Vayr moves the thug 5 feet" in out.tell, out.tell


def test_a_reposition_with_no_square_named_still_moves_them_and_keeps_them_in_reach():
    from rules.grid import distance_between

    scene, engine, pc, thug = _fight(face=20, strength=14)
    out = _do(engine, "reposition")
    assert scene.positions["c1"] != (7, 10), out.tell
    assert distance_between(scene.positions["pc"], "medium",
                            scene.positions["c1"], "medium") <= 10


def test_an_overrun_ends_on_the_far_side_and_never_in_their_square():
    scene, engine, pc, thug = _fight(face=20, strength=30)
    out = _do(engine, "overrun")
    assert scene.positions["pc"] == (8, 10), out.tell
    assert thug.has_condition("prone"), "by 5 or more"
    assert "Kesst Vayr moves through the thug's space" in out.tell


def test_an_overrun_with_no_room_past_says_so_and_nobody_shares_a_square():
    scene, engine, pc, thug = _fight(face=20, strength=30)
    scene.grid.blocked.add((8, 10))
    out = _do(engine, "overrun")
    assert scene.positions["pc"] == (6, 10)
    assert "Kesst Vayr finds no room past the thug" in out.tell, out.tell


def test_with_no_map_a_bull_rush_still_breaks_reach_in_the_zones():
    """No map: the zones are the only record. Five feet breaks melee reach and does not
    cross a whole zone (13th Age's "popping free"), so the thug goes `near`. Defensive
    only — measured while writing this, the first blow of any fight lays a map, so no
    manoeuvre in play reaches this branch; the map is taken away by hand here."""
    scene, engine, pc, thug = _fight(face=20, strength=30)
    scene.grid = None
    scene.positions.clear()
    scene.zones["c1"] = "engaged"
    out = _do(engine, "bull rush")
    assert scene.grid is None and scene.zones["c1"] == "near", out.tell


# --- the shared template ----------------------------------------------------------------

def test_one_thugs_disarm_no_longer_disarms_every_thug():
    """`instantiate` shallow-copies the template and `from_dict` kept its lists: every
    thug shared one `weapons` list and one `abilities` dict. Measured 2026-09-27: after
    one thug's backfire dropped his sap, the next thug made in the same run held only a
    dagger — and setting one thug's Strength had been setting them all."""
    scene, engine, pc, thug = _fight(face=1, strength=1, by="c1")
    _do(engine, "disarm", by="c1")
    fresh = instantiate("thug", scene=scene, name="another thug")
    assert fresh.weapons == ["sap", "dagger"]
    assert fresh.abilities["str"] != 1


# --- reaching the applicators from a player's sentence ---------------------------------
#
# The scripted live fight of 2026-09-27 (gemma-4-12B, the real /api/say loop) typed seven
# manoeuvre lines and reached the new applicators with none of them: the grit was a
# `trick` with no manoeuvre and rolled against AC, the shove filed `bull_rush` as the
# weapon and was refused, and the drag was overruled into a grapple — because drag and
# reposition had no cue in `judgement.MANOEUVRE_CUES`, so a GM choosing either was always
# "the manoeuvre nobody asked for".

def _reviewed(text, raw):
    from gm import judgement
    from rules.intents import parse_all

    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name=THUG))
    raw = judgement.normalize_attacks(raw, scene) or raw
    intents = parse_all(raw)
    judgement.review(text, intents, scene)
    return intents[0].params


def test_a_trick_with_no_manoeuvre_is_a_dirty_trick():
    params = _reviewed("I throw a handful of grit in his eyes to blind him.",
                       [{"op": "attack", "actor": "pc", "target": "c1",
                         "params": {"trick": "blinded"}}])
    assert params.get("manoeuvre") == "dirty trick" and params["trick"] == "blinded"


def test_a_manoeuvre_filed_as_the_weapon_moves_to_the_manoeuvre():
    params = _reviewed("I shove him back hard, away from me.",
                       [{"op": "attack", "actor": "pc", "target": "c1",
                         "params": {"weapon": "bull_rush"}}])
    assert params.get("manoeuvre") == "bull rush" and "weapon" not in params


@pytest.mark.parametrize("text,man", [
    ("I grab him by the collar and drag him toward the door.", "drag"),
    ("I haul him back towards the stairs.", "drag"),
    ("I steer him into the corner.", "reposition"),
    ("I force him against the bar.", "reposition"),
])
def test_a_drag_or_reposition_the_player_described_is_not_overruled(text, man):
    params = _reviewed(text, [{"op": "attack", "actor": "pc", "target": "c1",
                               "params": {"manoeuvre": man}}])
    assert params.get("manoeuvre") == man
