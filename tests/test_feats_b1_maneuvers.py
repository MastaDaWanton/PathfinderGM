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


# --- the assault feats: a declared -5 for a rider on every melee hit --------------------

class _HitAndFail(Dice):
    """The attack d20 lands on 15 and every save the riders roll on a 1."""

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if "save against" in (label or ""):
            return self.given(1, modifiers, label)
        if notation == "1d20" and "ttack" in (label or ""):
            return self.given(15, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _assault(*feats: str, **params):
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-borin.json")
    pc.level = 16                                   # BAB +16: every assault's prerequisite
    pc.feats = list(pc.feats) + list(feats)
    scene.add(pc)
    scene.add(instantiate("ogre", scene=scene, name="the ogre"))
    engine = Engine(scene, _HitAndFail(seed=3))
    engine._ensure_encounter("pc")
    scene.positions["pc"], scene.positions["c1"] = (6, 10), (7, 10)
    scene.resync_zones()
    res = engine.run(engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                                       "visibility": "hidden", "params": params}]))
    while res.awaiting:
        res = engine.resume(15)
    return pc, scene.get("c1"), next(o for o in res.outcomes if o.op == "attack")


def test_stunning_assault_costs_five_and_stuns_on_a_failed_fortitude():
    """APG: -5 on melee attack rolls and CMB, a hit stuns 1 round unless Fortitude DC 10 +
    BAB (26 here). Before the document the feat bought nothing at all."""
    pc, ogre, out = _assault("Stunning Assault", stunning_assault=True)
    attack = next(r for r in out.rolls if r.label.startswith("Attack"))
    assert any(m.source == "Stunning Assault" and m.value == -5 for m in attack.modifiers)
    assert any(m.source == "Stunning Assault" and m.value == -5
               for m in pc.cmb_modifiers("trip"))     # "until your next turn": the stance
    assert ogre.has_condition("stunned")
    assert "DC 26" in out.tell and "stunned for 1 round." in out.tell


def test_dazing_assault_dazes_and_bloody_assault_bleeds():
    pc, ogre, out = _assault("Dazing Assault", "Bloody Assault", dazing_assault=True,
                             bloody_assault=True)
    assert ogre.has_condition("dazed")
    bleed = [e for e in ogre.effects if e.key == "bleed"]
    assert bleed and bleed[0].periodic[0]["damage"] == "1d4"
    assert bleed[0].origin == "rule:feat-bloody-assault"


def test_an_assault_not_declared_lays_nothing():
    pc, ogre, out = _assault("Stunning Assault")
    assert not ogre.has_condition("stunned")
    attack = next(r for r in out.rolls if r.label.startswith("Attack"))
    assert not any(m.source == "Stunning Assault" for m in attack.modifiers)


def test_an_assault_needs_its_feat_and_a_melee_weapon():
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-borin.json")
    scene.add(pc)
    assert pc.can_choose("dazing_assault")             # no feat: refused, with the name
    pc.level, pc.feats = 16, list(pc.feats) + ["Dazing Assault"]
    assert pc.can_choose("dazing_assault") is None
    assert "dazing_assault" in pc.attack_choices()


# --- Stealth while watched: Hellcat Stealth, Go Unnoticed --------------------------------

def _in_the_open(*feats: str, fight: bool = False):
    """Noon in the open, the thug six squares off with a clear line: the case CRB p.106
    refuses ("If people are observing you ... you can't use Stealth")."""
    from rules.grid import Grid
    from tests._places import stand_on

    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
    pc = load_pc("fixtures/pc-kesst.json")
    pc.feats = list(pc.feats) + list(feats)
    s.add(pc, at=(5, 5))
    s.add(instantiate("thug", scene=s, name=THUG), at=(11, 5))
    stand_on(s, "urban")
    s.clock_minutes = 12 * 60
    if fight:
        s.sides = {"us": ["pc"], "them": ["c1"]}
        s.initiative = [("pc", 20), ("c1", 10)]
        s.round, s.turn = 1, 0
    e = Engine(s, Dice(seed=7))
    res = e.run(e.validate([{
        "op": "check", "actor": "pc", "because": "hide",
        "params": {"skill": "stealth", "opposed_by": {"ref": "c1", "skill": "perception"}}}]))
    while res.awaiting:
        res = e.resume(10)
    return pc, next(o for o in res.outcomes if o.op == "check")


def test_hellcat_stealth_hides_in_plain_sight_at_minus_ten():
    """Without the feat nothing is rolled (the refusal names cover or concealment); with it
    the check is made, the -10 named on the roll."""
    _, plain = _in_the_open()
    assert plain.status == "refused"
    _, hellcat = _in_the_open("Hellcat Stealth")
    assert hellcat.status != "refused", hellcat.tell
    roll = next(r for r in hellcat.rolls if "tealth" in r.label)
    assert any(m.value == -10 and "Hellcat" in m.source for m in roll.modifiers)


def test_go_unnoticed_only_against_a_foe_still_flat_footed_in_the_fight():
    """APG: in the first round, a flat-footed foe (one who has not acted) has not noticed
    you. Out of a fight the feat gives nothing: the thug is watching."""
    _, outside = _in_the_open("Go Unnoticed")
    assert outside.status == "refused"
    _, first_round = _in_the_open("Go Unnoticed", fight=True)
    assert first_round.status != "refused", first_round.tell
    roll = next(r for r in first_round.rolls if "tealth" in r.label)
    assert not any(m.value == -10 for m in roll.modifiers)


# --- which use of a skill: lies, feints; the saves that ask who cast it -------------------

def test_a_bluff_against_sense_motive_is_a_lie_and_a_feint_is_not():
    """Stone-Faced's +4 and Careful Speaker's +2 are "to lie ... but not to feint"; Voice
    of the Sibyl's +1 is every spoken Bluff, never a feint (APG, ISWG, UM)."""
    from rules.intents import Intent

    lie = Engine._skill_use_ctx(Intent(op="check", actor="pc", params={
        "skill": "bluff", "opposed_by": {"ref": "c1", "skill": "sense motive"}}), "bluff")
    feint = Engine._skill_use_ctx(Intent(op="check", actor="pc", params={
        "skill": "bluff", "feint": True}), "bluff")
    assert lie == {"skill_use": "lie"} and feint == {"skill_use": "feint"}
    pc = load_pc("fixtures/pc-kesst.json")
    pc.feats = list(pc.feats) + ["Stone-Faced", "Careful Speaker", "Voice of the Sibyl"]

    def terms(ctx):
        return {m.source: m.value for m in pc.skill_modifiers("bluff", ctx=ctx)}

    lying = terms(lie)
    assert lying["Stone-Faced"] == 4 and lying["Careful Speaker"] == 2
    assert lying["Voice of the Sibyl"] == 1
    feinting = terms(feint)
    assert not {"Stone-Faced", "Careful Speaker", "Voice of the Sibyl"} & set(feinting)
    pc.ranks["diplomacy"] = 10
    assert {m.source: m.value for m in pc.skill_modifiers("diplomacy")}[
        "Voice of the Sibyl"] == 3


def test_stone_faced_raises_the_hunch_dc_about_you_to_25():
    from rules import skilluses

    pc = load_pc("fixtures/pc-kesst.json")
    assert skilluses.dc(skilluses.HUNCH, pc) == 20
    pc.feats = list(pc.feats) + ["Stone-Faced"]
    assert skilluses.dc(skilluses.HUNCH, pc) == 25


def test_careful_speaker_and_seen_and_unseen_read_the_spells_own_school():
    """detect thoughts is divination and mind-affecting: "mind-reading" (`spell_against`);
    scrying is the subschool. Careful Speaker's +2 Will reaches both, not a charm."""
    from rules import effectspec, spells

    pc = load_pc("fixtures/pc-kesst.json")
    pc.feats = list(pc.feats) + ["Careful Speaker", "Seen and Unseen"]

    def will(spell_id, feat):
        ctx = {"against": effectspec.spell_against(spells.get(spell_id))}
        return sum(m.value for m in pc.save_modifiers("will", ctx) if m.source == feat)

    assert will("detect-thoughts", "Careful Speaker") == 2
    assert will("scrying", "Careful Speaker") == 2
    assert will("charm-person", "Careful Speaker") == 0
    assert will("scrying", "Seen and Unseen") == 2
    assert will("charm-person", "Seen and Unseen") == 0


def test_dragonheart_on_a_save_against_a_dragons_rider():
    """+1 on saves against a dragon-type creature's special attacks, read off who made it
    (`attacker_actor`, now passed by the rider saves and the cast's saves)."""
    scene, engine, pc, thug = _fight("Dragonheart")
    drake = instantiate("pseudodragon", scene=scene)
    scene.add(drake)
    state: dict = {}
    engine._rider_save(pc, "fort", 15, "Fortitude save against a sting", state,
                       attacker=drake)
    engine._rider_save(pc, "fort", 15, "Fortitude save against a sap", state,
                       attacker=thug)
    stung, sapped = state["rolls"]
    assert any(m["value"] == 1 and "Dragonheart" in str(m.get("source"))
               for m in stung["modifiers"])
    assert not any("Dragonheart" in str(m.get("source")) for m in sapped["modifiers"])


# --- a manoeuvre in a swing of the full attack: trip anywhere, Quick X in the first ------

def _slot(feats=(), **params):
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-borin.json")
    pc.level = 6                                    # BAB +6: two swings, +6/+1
    pc.feats = list(pc.feats) + list(feats)
    scene.add(pc)
    scene.add(instantiate("thug", scene=scene, name=THUG))
    engine = Engine(scene, _AimedCMB(10))
    engine._ensure_encounter("pc")
    scene.positions["pc"], scene.positions["c1"] = (6, 10), (7, 10)
    scene.resync_zones()
    return pc, _maneuver(engine, **params)


def test_a_bull_rush_cannot_take_a_swing_without_quick_bull_rush():
    """UC, Quick Bull Rush: "Normal: A bull rush combat maneuver is a standard action."
    Before this a swing slot could carry no manoeuvre at all; now the engine says which."""
    _, out = _slot(key="bull rush", iteration=0)
    assert out.status == "refused" and "standard action" in out.tell
    _, out = _slot(["Quick Bull Rush"], key="bull rush", iteration=0)
    assert out.status != "refused", out.tell
    _, out = _slot(["Quick Bull Rush"], key="bull rush", iteration=1)
    assert out.status == "refused" and "first" in out.tell


def test_a_trip_stands_in_a_later_swing_at_that_swings_bonus():
    """CRB: a trip is made "in place of a melee attack" — the second swing's -5 rides it."""
    pc, out = _slot(key="trip", iteration=1)
    assert out.status != "refused", out.tell
    assert _named(_cmb_roll(out), "a later swing") == -5


def test_the_combat_bar_offers_each_swing_only_what_the_engine_takes():
    from play.views import _slot_maneuvers

    pc = load_pc("fixtures/pc-borin.json")
    pc.level = 6
    pc.feats = list(pc.feats) + ["Quick Steal"]
    first, second = _slot_maneuvers(pc)
    assert set(first) == {"disarm", "sunder", "trip", "steal"}
    assert set(second) == {"disarm", "sunder", "trip"}
