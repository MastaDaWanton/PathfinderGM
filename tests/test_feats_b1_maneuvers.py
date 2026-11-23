"""Feat loop batch 1, the manoeuvres lane: each feat's numbers measured through the engine.

Before this batch none of these feats had a mechanics document, so each was a name on the
sheet that changed no roll (worklist 2026-11-22: 82 manoeuvre-family feats TODO). The
CMB and CMD a manoeuvre rolls also knew nothing of the other side: `cmb_modifiers` built
its roll context with the manoeuvre alone and `cmd_modifiers` passed `{"maneuver": ...}`
and nothing else, so "+4 against enemies denied their Dexterity bonus" (Kobold Style) or
"adjacent to an ally who also has this feat" (the teamwork feats) had nothing to be asked
of. Now the opponent and the moment ride both, and the tests below roll the real
manoeuvre and read the terms it rolled with.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc, situated

THUG = "the thug"


@pytest.fixture(autouse=True)
def _the_provoked_swing_waived(monkeypatch):
    """A manoeuvre without its Improved feat provokes (tests/test_reactions.py); the swing
    would spend the scripted dice these tests read."""
    from rules import reactions as _reactions

    monkeypatch.setattr(_reactions, "provoked_by_maneuver", lambda *a, **k: [])


class _AimedCMB(Dice):
    """Every CMB d20 lands on the face asked for; everything else rolls as usual."""

    def __init__(self, face: int = 10):
        super().__init__(seed=20261122)
        self.face = face

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if "(CMB)" in (label or "") or "break the grapple" in (label or ""):
            return self.given(self.face, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _fight(*feats: str, ally_feats=(), ally_at=None, face: int = 10):
    """Kesst (rogue 1) beside a thug on the map a fight lays; optionally Borin as Kesst's
    ally at `ally_at`."""
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    pc.feats = list(pc.feats) + list(feats)
    scene.add(pc)
    scene.add(instantiate("thug", scene=scene, name=THUG))
    engine = Engine(scene, _AimedCMB(face))
    engine._ensure_encounter("pc")
    scene.positions["pc"], scene.positions["c1"] = (6, 10), (7, 10)
    if ally_at is not None:
        ally = load_pc("fixtures/pc-borin.json")
        ally.ref, ally.kind = "ally", "npc"
        ally.feats = list(ally.feats) + list(ally_feats)
        scene.add(ally)
        scene.positions["ally"] = ally_at
        scene.sides = {"pc": ["pc", "ally"], "them": ["c1"]}
    scene.resync_zones()
    return scene, engine, scene.get("pc"), scene.get("c1")


def _maneuver(engine, key: str, by: str = "pc", target: str = "c1", **params):
    res = engine.run(engine.validate([{
        "op": "attack", "actor": by, "target": target, "visibility": "hidden",
        "params": {"manoeuvre": key, **params}}]))
    while res.awaiting:
        res = engine.resume(engine.dice.face)
    return next(o for o in res.outcomes if o.op == "attack")


def _named(roll: dict, name: str) -> int:
    return sum(int(m["value"]) for m in roll.get("modifiers") or ()
               if str(m.get("source") or m.get("label") or "").startswith(name))


def _cmb_roll(outcome) -> dict:
    return next(r.as_dict() for r in outcome.rolls if "(CMB)" in (r.label or ""))


def test_defensive_combat_training_reads_hit_dice_for_bab_in_cmd():
    """Kesst is a 1st-level rogue: BAB 0, 1 Hit Die. "You treat your total Hit Dice as your
    base attack bonus when calculating your CMD" (CRB) is +1 here; nothing changed before."""
    scene, engine, pc, _ = _fight()
    before = pc.cmd()
    pc.feats.append("Defensive Combat Training")
    assert pc.cmd() - before == pc.hit_dice - pc.bab == 1


def test_fury_s_fall_adds_dexterity_to_a_trip_and_nothing_else():
    """Kesst's Dex bonus is +3: a trip's CMB rises by it, a bull rush's does not."""
    scene, engine, pc, _ = _fight()
    trip, rush = (sum(m.value for m in pc.cmb_modifiers(k)) for k in ("trip", "bull rush"))
    pc.feats.append("Fury's Fall")
    assert sum(m.value for m in pc.cmb_modifiers("trip")) - trip == 3
    assert sum(m.value for m in pc.cmb_modifiers("bull rush")) == rush


def test_kobold_style_counts_only_against_a_foe_denied_dexterity():
    """Rolled through the real manoeuvre: +4 on the trip at a stunned thug (denied Dex,
    `state.exposed`), nothing at a thug on guard."""
    scene, engine, pc, thug = _fight("Kobold Style")
    on_guard = _cmb_roll(_maneuver(engine, "trip"))
    assert _named(on_guard, "Kobold Style") == 0
    scene, engine, pc, thug = _fight("Kobold Style")
    thug.add_condition("stunned", 2, source="test")
    exposed = _cmb_roll(_maneuver(engine, "trip"))
    assert _named(exposed, "Kobold Style") == 4


def test_solo_maneuvers_only_while_nobody_else_threatens_the_foe():
    """Alone beside the thug, +1 on Kesst's CMB and her CMD against his manoeuvre; with an
    ally beside the thug too, neither."""
    scene, engine, pc, thug = _fight("Solo Maneuvers")
    alone = _cmb_roll(_maneuver(engine, "trip"))
    assert _named(alone, "Solo Maneuvers") == 1
    with situated(scene):
        assert any(m.source == "Solo Maneuvers"
                   for m in pc.cmd_modifiers(maneuver="trip", attacker=thug))
    scene, engine, pc, thug = _fight("Solo Maneuvers", ally_at=(7, 11))
    crowded = _cmb_roll(_maneuver(engine, "trip"))
    assert _named(crowded, "Solo Maneuvers") == 0


def test_coordinated_defense_needs_the_ally_beside_with_the_feat():
    """+2 competence to CMD beside an ally with the feat; nothing if the ally lacks it or
    stands away; +4 against a foe larger than both."""
    def cmd_terms(*, ally_feats, ally_at, large=False):
        scene, engine, pc, thug = _fight("Coordinated Defense", ally_feats=ally_feats,
                                         ally_at=ally_at)
        if large:
            thug.size = "large"
        with situated(scene):
            return sum(m.value for m in pc.cmd_modifiers(maneuver="trip", attacker=thug)
                       if m.source == "Coordinated Defense")

    assert cmd_terms(ally_feats=["Coordinated Defense"], ally_at=(5, 10)) == 2
    assert cmd_terms(ally_feats=[], ally_at=(5, 10)) == 0
    assert cmd_terms(ally_feats=["Coordinated Defense"], ally_at=(2, 10)) == 0
    assert cmd_terms(ally_feats=["Coordinated Defense"], ally_at=(5, 10), large=True) == 4


def test_coordinated_maneuvers_on_the_roll_and_on_the_escape():
    """+2 competence on Kesst's trip beside Borin with the feat; +4 on breaking his grapple."""
    scene, engine, pc, thug = _fight("Coordinated Maneuvers",
                                     ally_feats=["Coordinated Maneuvers"], ally_at=(5, 10))
    assert _named(_cmb_roll(_maneuver(engine, "trip")), "Coordinated Maneuvers") == 2
    with situated(scene):
        assert sum(m.value for m in pc.cmb_modifiers("escape", defender=thug)
                   if m.source == "Coordinated Maneuvers") == 4


def test_free_spirit_on_mind_saves_and_escapes_only():
    """+2 morale on a Will save against a mind-affecting effect, not against a plain spell;
    +2 on the CMB and Escape Artist of a break-free, not on a trip."""
    scene, engine, pc, thug = _fight("Free Spirit")
    will = lambda ctx: sum(m.value for m in pc.save_modifiers("will", ctx)
                           if m.source == "Free Spirit")
    assert will({"against": ("spell", "enchantment", "mind-affecting")}) == 2
    assert will({"against": ("spell", "evocation")}) == 0
    assert sum(m.value for m in pc.cmb_modifiers("escape") if m.source == "Free Spirit") == 2
    assert sum(m.value for m in pc.cmb_modifiers("trip") if m.source == "Free Spirit") == 0
    art = pc.skill_modifiers("escape artist", ctx={"maneuver": "escape"})
    assert any(m.source == "Free Spirit" and m.value == 2 for m in art)


def test_focused_discipline_against_fear_saves():
    scene, engine, pc, thug = _fight("Focused Discipline")
    assert any(m.source == "Focused Discipline" and m.value == 2
               for m in pc.save_modifiers("will", {"against": ("spell", "fear")}))
    assert not any(m.source == "Focused Discipline"
                   for m in pc.save_modifiers("will", {"against": ("spell",)}))
