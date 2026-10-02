"""A poison's saving throw decides whether its harm lands.

The defect: a successful Fortitude save against a jar of hemlock still paralysed the
drinker. `consumables.plan` emitted the save and then the poison's body side by side, and
`_op_use_item` ran the list as one batch; nothing read the save's verdict before running
the body. Measured on 2026-10-02 with a dragon-flower tincture: the drinker rolled a
natural 20 on the Fortitude save, the tell said "makes the Fortitude save on a natural
20", and the very next two outcomes took 5 Constitution and left them nauseated. A blade
painted with the same jar did the same to whatever it cut (`coating_intents`).

1e: a made save against a poison means the poison has no effect, unless the poison says
otherwise. The taste door already rolled its gate first and skipped the body on a success
(`Engine._op_taste`, engine-rolled); the jar and blade doors could not copy that, because
their save is the PLAYER's d20 when the drinker is the PC — the batch suspends half-way
and resumes on a later request. So the bodies carry a link to their save
(`Intent.gated_by`, stamped by `Engine.validate(origin=...)`) and `_drive` takes them off
the queue when the save goes the other way — the queue being exactly what a suspension
freezes and a resume walks again.
"""
from __future__ import annotations

import json

import pytest

from rules import ingredients as ing_mod
from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from tests._board import face_to_face


def _from(source: str, specs: list[dict]) -> list[dict]:
    """An ingredient's specs as a compound carries them: each one tagged with its source,
    which is the only thing `consumables.poisons` groups a save with its body by."""
    return [dict(s, **{"from": source}) for s in specs]


@pytest.fixture
def board():
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the beast"))
    pc.stock["hemlock#1"] = Stock(base="Hemlock Tincture", count=3,
                                  specs=_from("Hemlock", ing_mod.get("hemlock").specs))
    e = Engine(s, Dice(seed=9))
    e._ensure_encounter("pc")
    face_to_face(s)
    return s, e


def engine_faces(engine, *faces):
    """The faces the engine's own hidden d20s come up, in order — every save a creature
    other than the PC makes. Once they run out the dice roll as they would."""
    queue = list(faces)
    rolled = engine.dice.d20

    def d20(modifiers=None, label="", visibility="hidden"):
        if not queue:
            return rolled(modifiers, label, visibility)
        return engine.dice.given(queue.pop(0), modifiers, label=label)

    engine.dice.d20 = d20


def use(engine, item, **params):
    return engine.run(engine.validate([
        {"op": "use_item", "actor": "pc", "because": "she uses it",
         "params": {"item": item, **params}}]))


def tells(res):
    return " ".join(o.tell for o in res.outcomes)


# --- the verdict decides --------------------------------------------------------------------

def test_a_made_save_stops_every_body_effect(board):
    """Thrown at the beast, saved on a natural 20: no paralysis, and the tell says the
    poison did nothing rather than leaving the narrator a bare "makes the save"."""
    scene, engine = board
    engine_faces(engine, 20)
    res = use(engine, "hemlock#1", how="throw", to="c1")
    beast = scene.actors["c1"]
    assert not beast.has_condition("paralyzed")
    assert "makes the Fortitude save" in tells(res)
    assert "has no effect on the beast" in tells(res)


def test_a_failed_save_lets_the_poison_land(board):
    scene, engine = board
    engine_faces(engine, 1)
    res = use(engine, "hemlock#1", how="throw", to="c1")
    assert "fails the Fortitude save" in tells(res)
    assert scene.actors["c1"].has_condition("paralyzed")
    assert "has no effect" not in tells(res)


def test_a_made_save_stops_damage_as_well_as_conditions(board):
    """Dragon flower carries both kinds of body — 1d6 Constitution damage and nausea —
    and the measured jar landed both after a natural 20."""
    scene, engine = board
    scene.pc().stock["df#1"] = Stock(
        base="Dragon Flower Tincture", count=1,
        specs=_from("Dragon Flower", ing_mod.get("dragon-flower").specs))
    engine_faces(engine, 20)
    use(engine, "df#1", how="throw", to="c1")
    beast = scene.actors["c1"]
    assert not beast.ability_damage.get("con")
    assert not beast.has_condition("nauseated")


def test_two_poisons_in_one_compound_each_gate_their_own_body(board):
    """Hemlock (paralysis) and dragon flower (Constitution) in one jar: two saves, and
    each save rules only on its own poison — made the first, failed the second, and the
    other way round."""
    specs = (_from("Hemlock", ing_mod.get("hemlock").specs)
             + _from("Dragon Flower", ing_mod.get("dragon-flower").specs))
    for first, second, paralysed, con in ((20, 1, False, True), (1, 20, True, False)):
        s = Scene(location_id="5bbd0c40345f")
        pc = s.add(load_pc("fixtures/pc-kesst.json"))
        s.add(instantiate("thug", scene=s, name="the beast"))
        pc.stock["brew#1"] = Stock(base="Witch's Brew", count=1, specs=list(specs))
        engine = Engine(s, Dice(seed=9))
        engine_faces(engine, first, second)
        res = use(engine, "brew#1", how="throw", to="c1")
        beast = s.actors["c1"]
        # Both saves are inside the one use_item outcome's tell.
        assert tells(res).count("Fortitude save") == 2
        assert beast.has_condition("paralyzed") is paralysed
        assert bool(beast.ability_damage.get("con")) is con


def test_a_poison_that_bites_on_a_made_save_still_does(board):
    """"Unless the poison says otherwise": an authored gate with an `on_success` branch
    keeps that branch on a made save, and drops it on a failed one."""
    scene, engine = board
    gate = {"type": "save_gate", "target": "fort", "dc": 15, "from": "Thornwine",
            "on_failure": [{"type": "ability_damage", "target": "con", "dice": "1d4"}],
            "on_success": [{"type": "ability_damage", "target": "dex", "dice": "1d4"}]}
    scene.pc().stock["thorn#1"] = Stock(base="Thornwine", count=2, specs=[gate])
    beast = scene.actors["c1"]

    engine_faces(engine, 20)
    res = use(engine, "thorn#1", how="throw", to="c1")
    assert beast.ability_damage.get("dex") and not beast.ability_damage.get("con")
    assert "has no effect" not in tells(res)

    beast.ability_damage.clear()
    engine_faces(engine, 1)
    use(engine, "thorn#1", how="throw", to="c1")
    assert beast.ability_damage.get("con") and not beast.ability_damage.get("dex")


# --- the player's own d20 ---------------------------------------------------------------------

def _drink_and_suspend(scene, engine):
    use(engine, "hemlock#1", how="drink")
    assert scene.awaiting and scene.awaiting["label"] == "Fortitude save"
    # The queue as the campaign file holds it between the two requests.
    scene.pending_intents = json.loads(json.dumps(scene.pending_intents))
    assert any(i.get("gated_by") for i in scene.pending_intents)
    assert not scene.pc().has_condition("paralyzed")


def test_a_save_on_the_players_own_die_gates_the_body_across_the_resume(board):
    """The PC drinks: the save is theirs to roll, so the batch stops at it and the
    paralysis waits in the frozen queue. A natural 20 sent back takes it off."""
    scene, engine = board
    _drink_and_suspend(scene, engine)
    res = engine.resume(face=20)
    assert res.status == "complete"
    assert not scene.pc().has_condition("paralyzed")
    assert "has no effect on Kesst Vayr" in tells(res)


def test_a_failed_save_on_the_players_own_die_lands_after_the_resume(board):
    scene, engine = board
    _drink_and_suspend(scene, engine)
    res = engine.resume(face=1)
    assert res.status == "complete"
    assert scene.pc().has_condition("paralyzed")


# --- the blade ------------------------------------------------------------------------------

def _cut(scene, engine):
    use(engine, "hemlock#1", how="coat", weapon="rapier")
    res = engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1", "because": "she cuts",
         "params": {"weapon": "rapier", "full_attack": False}}]))
    for face in (19, 14, 6, 5, 4):
        if res.status == "complete":
            break
        res = engine.resume(face=face)
    assert "goes into the wound" in tells(res)
    return res


def test_a_coated_blade_is_gated_by_the_victims_save(board):
    scene, engine = board
    engine_faces(engine, 20)
    res = _cut(scene, engine)
    assert not scene.actors["c1"].has_condition("paralyzed")
    assert "has no effect on the beast" in tells(res)
    assert not scene.pc().coating, "a dose resisted has still left the blade"


def test_a_coated_blade_lands_on_a_failed_save(board):
    scene, engine = board
    engine_faces(engine, 1)
    _cut(scene, engine)
    assert scene.actors["c1"].has_condition("paralyzed")


# --- the link is the engine's ---------------------------------------------------------------

def test_a_link_written_without_a_document_is_not_read(board):
    """`gated_by` is stamped on the trusted path only, as `origin` is: a model's own list
    carrying one gets nothing from it."""
    scene, engine = board
    got = engine.validate([
        {"op": "save", "actor": "c1", "gate": "x",
         "params": {"save": "fort", "dc": {"value": 15}}},
        {"op": "condition", "gated_by": "x",
         "params": {"condition": "sickened", "to": "c1"}}])
    assert not got[0].gate and not got[1].gated_by


def test_a_body_whose_save_is_missing_is_refused_not_run_ungated(board):
    scene, engine = board
    with pytest.raises(IntentError, match="no save ahead of it"):
        engine.validate([
            {"op": "condition", "gated_by": "poison-0",
             "params": {"condition": "sickened", "to": "c1"}}],
            origin="author:test", origin_name="the test")
