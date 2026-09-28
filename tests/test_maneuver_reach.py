"""A melee blow needs its target within reach — and the refusal names the square to step to.

Measured 2026-09-27: `Engine._ensure_encounter` laid the thug at (7,10) and the player at
(4,10), fifteen feet apart in zone "near", and from there a disarm, a trip, a grapple and
a plain rapier thrust (8 piercing) all resolved. Nothing between the intent and the dice
asked how far away the target stood. The rule: "With a normal melee weapon, you can strike
any opponent within 5 feet ... Some melee weapons have reach" (Core Rulebook p.182,
aonprd.com/Rules.aspx?ID=131), and a manoeuvre is made "in place of a melee attack" or
as its own action against a foe in reach (p.198-201; an overrun's "during your move" is
the move op before it — the engine has no charge).

The refusal is the classbuilder's shape — the fault with its numbers, then the fix
written out — and the fix is a SQUARE, not "move first": the model plans in zones, and a
`move zone=engaged` on a mapped fight relabels the zone and leaves the body where it was.
The attacker is never moved by the refusal. Only turns the engine composes for a creature
itself (the fallback, the blow that opens a fight from their side) declare their own
closing move, as a real intent that is told and provokes.
"""
from __future__ import annotations

import json
import re

import pytest

from gm import judgement
from rules import position, reactions
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.intents import IntentError
from rules.sheet import load_pc
from rules.tables import MANEUVERS
from tests._board import face_to_face


def _fight(seed: int = 7):
    """The measured board: a fight opened on the thug, who is laid fifteen feet off."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    engine = Engine(scene, Dice(seed=seed))
    engine._ensure_encounter("pc", "c1")
    return scene, engine


def _attack(params=None, actor="pc", target="c1"):
    return {"op": "attack", "actor": actor, "target": target, "visibility": "hidden",
            "because": "test", "params": dict(params or {})}


def _named_square(message: str) -> tuple[int, int]:
    got = re.search(r'"square": \[(\d+), (\d+)\]', message)
    assert got, f"the refusal names no square to step to: {message}"
    return int(got.group(1)), int(got.group(2))


def _finish(engine, res):
    for _ in range(8):
        if not res.awaiting:
            break
        res = engine.resume(min(15, int(res.awaiting.get("max", 20))))
    return res


# --- the measured defect --------------------------------------------------------------------

def test_the_board_the_defect_was_measured_on():
    scene, _ = _fight()
    assert scene.positions["pc"] == (4, 10) and scene.positions["c1"] == (7, 10)
    assert scene.distance_between("pc", "c1") == 15
    assert scene.zones["c1"] == "near"


@pytest.mark.parametrize("key", sorted(MANEUVERS))
def test_a_manoeuvre_from_15_feet_is_refused_with_the_square_named(key):
    """A disarm from 15 feet resolved; the thug was never in reach. So did every other
    manoeuvre in the table — none of the ten asked."""
    scene, engine = _fight()
    with pytest.raises(IntentError) as err:
        engine.validate([_attack({"manoeuvre": key})])
    said = str(err.value)
    assert err.value.check == "legality"
    assert "15 ft away" in said and f"{key} needs them within reach" in said
    assert '"op": "move"' in said
    square = _named_square(said)
    # The square is one the move op accepts, and from it the thug is in reach.
    engine.validate([{"op": "move", "actor": "pc", "params": {"square": list(square)}}])
    assert scene.positions["pc"] == (4, 10), "the refusal moved nobody"


def test_a_plain_melee_swing_from_15_feet_is_refused_too():
    """The same gap in the ordinary attack: a rapier thrust from fifteen feet hit the thug
    for 8. Closed together with the manoeuvres, on the user's ruling (2026-09-27)."""
    scene, engine = _fight()
    with pytest.raises(IntentError) as err:
        engine.validate([_attack()])
    said = str(err.value)
    assert "Kesst Vayr reaches 5 ft with the rapier and the thug is 15 ft away" in said
    assert _named_square(said) == (6, 10), "squarest-on to a thug straight ahead"


@pytest.mark.parametrize("key", sorted(MANEUVERS))
def test_the_named_move_then_the_manoeuvre_resolves_in_one_list(key):
    """The repair the refusal asks for. Validation sees the list before any of it runs,
    so an attack after a move of its own attacker is left to the floor at resolution —
    otherwise the fixed list would be refused for the distance it is about to close."""
    scene, engine = _fight()
    try:
        engine.validate([_attack({"manoeuvre": key})])
    except IntentError as exc:
        square = _named_square(str(exc))
    res = _finish(engine, engine.run(engine.validate([
        {"op": "move", "actor": "pc", "params": {"square": list(square)}},
        _attack({"manoeuvre": key})])))
    assert res.outcomes[0].op == "move" and scene.get("pc") is not None
    swing = res.outcomes[-1]
    assert swing.op == "attack" and swing.status != "refused", swing.tell
    assert swing.rolls or swing.verdict, swing.tell


def test_the_combat_panels_move_and_strike_resolves():
    """The panel posts `[move square, attack]` as one list (04-combat-and-turns.js
    commitTurn). A reach check asked of the board as it stands would refuse that."""
    scene, engine = _fight()
    res = _finish(engine, engine.run(engine.validate([
        {"op": "move", "actor": "pc", "params": {"zone": "near", "square": [6, 10]}},
        _attack()])))
    assert [o.op for o in res.outcomes] == ["move", "attack"]
    assert res.outcomes[-1].rolls


# --- the floor ------------------------------------------------------------------------------

def test_a_move_that_falls_short_is_refused_at_resolution_in_prose():
    """The floor under validate's check: the list moved the attacker, so validation let
    the swing through, and the move stopped ten feet short. Printed, not raised — and a
    tell is fed to the narrator, so it carries no JSON and no grid square."""
    scene, engine = _fight()
    thug_hp = scene.get("c1").hp
    res = engine.run(engine.validate([
        {"op": "move", "actor": "pc", "params": {"square": [5, 10]}}, _attack()]))
    swing = res.outcomes[-1]
    assert swing.status == "refused" and not swing.rolls
    assert "10 ft away" in swing.tell and "Nothing is rolled" in swing.tell
    assert "{" not in swing.tell and "square" not in swing.tell
    assert scene.get("c1").hp == thug_hp and not scene.awaiting


def test_a_blow_that_cannot_land_draws_no_bystander_in():
    """The floor is asked before `join_fight`: a swing refused for its distance used to be
    able to put a merchant fifteen feet off onto the enemy side and into the initiative."""
    scene, engine = _fight()
    merchant = scene.add(instantiate("guildhand", scene=scene, name="the merchant"))
    merchant.add_condition("bystander", source="test")
    scene.positions[merchant.ref] = (4, 14)
    engine.run(engine.validate([
        {"op": "move", "actor": "pc", "params": {"square": [4, 11]}},
        _attack(target=merchant.ref)]))
    assert merchant.has_state("role.bystander")
    assert not any(merchant.ref in refs for refs in scene.sides.values())


# --- what reach is ------------------------------------------------------------------------

def _armed(scene, weapon):
    pc = scene.get("pc")
    pc.weapons = list(pc.weapons) + [weapon]
    pc.equipped = weapon
    return pc


def test_a_reach_weapon_strikes_at_ten_feet_and_not_beside_you():
    """Both halves of the rule land together, as they do for attacks of opportunity
    (`reactions._reach_of`): the half easy to forget is the one that costs the player."""
    scene, engine = _fight()
    _armed(scene, "glaive")
    scene.positions["pc"] = (5, 10)
    engine.validate([_attack({"weapon": "glaive"})])            # 10 ft: in reach
    scene.positions["pc"] = (6, 10)
    with pytest.raises(IntentError, match="cannot strike a foe beside you"):
        engine.validate([_attack({"weapon": "glaive"})])
    engine.validate([_attack({"weapon": "unarmed"})])           # a fist reaches


def test_a_whip_trips_at_ten_feet_but_a_grapple_is_the_bodys():
    """Disarm, sunder and trip are made with the weapon (`MANEUVERS_WITH_THE_WEAPON`);
    the whip carries the trip quality so it can be. A grab is a hand's reach."""
    scene, engine = _fight()
    _armed(scene, "whip")
    scene.positions["pc"] = (5, 10)
    engine.validate([_attack({"weapon": "whip", "manoeuvre": "trip"})])
    with pytest.raises(IntentError, match="grapple needs them within reach"):
        engine.validate([_attack({"weapon": "whip", "manoeuvre": "grapple"})])


def test_a_bow_has_no_reach_to_be_out_of():
    scene, engine = _fight()
    _armed(scene, "longbow")
    res = _finish(engine, engine.run(engine.validate([_attack({"weapon": "longbow"})])))
    assert res.outcomes[-1].rolls


def test_a_large_creature_reaches_ten_feet_with_its_body():
    """Measured edge to edge, so a 2x2 body anchored at (6,10) has its near edge ten feet
    from the player — out of a Medium arm's reach, inside a Large one's."""
    scene, engine = _fight()
    ogre = scene.get("c1")
    ogre.size = "large"
    scene.positions["c1"] = (6, 10)
    assert scene.distance_between("c1", "pc") == 10
    engine.validate([_attack(actor="c1", target="pc")])
    with pytest.raises(IntentError, match="10 ft away"):
        engine.validate([_attack()])                  # and the player cannot answer back


def test_the_attack_and_the_attack_of_opportunity_read_one_rule():
    """`reach_with` is the one copy; the threatened squares and the refusal both read it,
    so they cannot disagree about how far a glaive goes."""
    scene, _ = _fight()
    pc = _armed(scene, "glaive")
    assert reactions.reach_with(pc, "glaive") == (10, True)
    assert reactions._reach_of(pc) == 10 and reactions.reach_gap(pc)
    assert reactions.reach_with(pc, "unarmed") == (5, False)


# --- what it does not refuse ----------------------------------------------------------------

def test_the_swing_that_opens_a_fight_is_not_measured():
    """The opening swing rolls nothing: it joins battle ("Battle is joined") and the blow
    is the attacker's to declare — and have measured — on their first combat turn. And
    the fight moves nobody (the ruling of 2026-09-28): both stand where they stood."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"), at=(1, 1))
    scene.add(instantiate("thug", scene=scene, name="the thug"), at=(12, 12))
    scene.grid = Grid(width=20, height=20)
    engine = Engine(scene, Dice(seed=3))
    assert scene.distance_between("pc", "c1") > 5
    res = engine.run(engine.validate([_attack()]))
    assert "Battle is joined" in res.outcomes[0].tell
    assert scene.positions["pc"] == (1, 1) and scene.positions["c1"] == (12, 12)


def test_a_mapless_scene_is_not_refused():
    """`Scene.distance_between` answers None with no map — "we are not tracking that" —
    and a distance nobody measured is not a refusal."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name="the thug"), zone="near")
    scene.sides = {"pc": ["pc"], "them": ["c1"]}
    scene.initiative = [("pc", 20), ("c1", 10)]
    assert scene.distance_between("pc", "c1") is None
    assert position.out_of_reach(scene, scene.get("pc"), scene.get("c1"), "rapier") is None


def test_an_undecided_target_is_asked_about_before_it_is_measured():
    """With two live foes and no name, the ref is a placeholder and the engine asks
    "which of them?" — the distance to a person nobody chose is not the refusal."""
    scene, engine = _fight()
    other = scene.add(instantiate("thug", scene=scene, name="the other thug"))
    engine.join_fight(other.ref)
    raw = _attack()
    raw["params"]["undecided"] = ["c1", other.ref]
    res = engine.run(engine.validate([raw]))
    assert "Which of them" in res.outcomes[0].tell


# --- the turns the engine composes itself ---------------------------------------------------

def test_the_fallback_closes_then_swings_and_is_told():
    scene, engine = _fight()
    engine.scene.turn = next(i for i, (r, _) in enumerate(scene.initiative) if r == "c1")
    plan = judgement.default_npc_action(scene, "c1")
    assert [r["op"] for r in plan] == ["move", "attack"]
    res = engine.run(engine.validate(plan))
    assert res.outcomes[0].op == "move" and "moves" in res.outcomes[0].tell
    assert res.outcomes[-1].rolls, "the blow after the move was rolled"


def test_a_fallback_too_far_for_one_move_crosses_the_room_and_does_not_swing():
    scene, engine = _fight()
    scene.positions["c1"] = (19, 10) if scene.grid.width > 19 else (scene.grid.width - 1, 10)
    thug = scene.get("c1")
    before = scene.distance_between("c1", "pc")
    if before - 5 <= thug.speed_feet:
        pytest.skip("this room is too small to be more than one move across")
    plan = judgement.default_npc_action(scene, "c1")
    assert [r["op"] for r in plan] == ["move"]
    engine.run(engine.validate(plan))
    assert scene.distance_between("c1", "pc") < before


def test_a_bystander_takes_no_attack_of_opportunity():
    """Measured the day creatures began closing to reach: the merchant beside the man in
    the apron swung as he stepped in, knocked him unconscious, and was drawn into a fight
    the scene had kept him out of. A bystander joins by joining."""
    scene, engine = _fight()
    merchant = scene.add(instantiate("guildhand", scene=scene, name="the merchant"))
    merchant.add_condition("bystander", source="test")
    scene.positions[merchant.ref] = (7, 11)
    assert reactions.threatens(scene, merchant.ref, (7, 10))
    assert reactions.provoked_by_move(scene, "c1", (7, 10), (5, 10)) == []


def test_the_prompt_the_model_reads_is_the_refusal_it_repairs_from():
    """The retry loop hands the refusal back to the model verbatim; the move in it has to
    parse as an intent of its own, or the model is asked to copy something malformed."""
    scene, engine = _fight()
    with pytest.raises(IntentError) as err:
        engine.validate([_attack({"manoeuvre": "disarm"})])
    move = json.loads(re.search(r'(\{"op": "move".*?\}\})', str(err.value)).group(1))
    engine.validate([move])


# --- the combat panel, where a person reads the refusal ------------------------------------

@pytest.fixture
def panel(tmp_path):
    from django.test import Client, override_settings

    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.seed = 20260928
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        thug = instantiate("thug", scene=c.scene, name="the thug")
        thug.ref = "c1"
        c.scene.add(thug)
        e = c.engine()
        e.run(e.validate([{"op": "begin_encounter",
                           "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
        while c.scene.current_ref() != "pc":
            c.scene.advance_turn()
        c.save()
        yield Client(), cm
        cm._LIVE.clear()


def _post(client, actions):
    return client.post("/api/combat/act", content_type="application/json",
                       data=json.dumps({"actions": actions, "label": "strike",
                                        "end_turn": False}))


def test_the_panel_says_which_square_to_click_and_shows_no_json(panel):
    """The first live run (2026-09-28) put the model's repair sentence on the page:
    `{"op": "move", "actor": "pc", "params": {"square": [6, 8]}}` in red under the
    prose. The panel is read by a person; the square is named the way the map names it."""
    client, cm = panel
    scene = cm.current().scene
    assert scene.distance_between("pc", "c1") == 15
    r = _post(client, [{"op": "attack", "target": "c1", "params": {}}])
    assert r.status_code == 400
    said = r.json()["error"]
    assert "15 ft away" in said and "Click square" in said
    assert "{" not in said and '"op"' not in said
    got = re.search(r"Click square (\d+),(\d+)", said)
    square = [int(got.group(1)), int(got.group(2))]
    # And doing what it says works: the panel's own move-and-strike list.
    r = _post(client, [{"op": "move", "params": {"zone": "near", "square": square}},
                       {"op": "attack", "target": "c1", "params": {}}])
    assert r.status_code == 200, r.json()
    assert r.json()["awaiting"], "the strike is waiting on the player's own d20"
