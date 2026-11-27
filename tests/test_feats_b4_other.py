"""Feat loop batch 4, lane b4-other (2026-11-26): saves and resolve, luck, senses, healing,
meditation, the Deathless line, and five engine defects batch 3 found, proved through the
engine.

Before this lane, measured on integrate/feats-b3 71e7ce50: none of the lane's 62 feats had
a document; a gray ooze could be charmed and a skeleton frightened; a night's sleep left a
climber clinging to the wall; and the plain Bestiary orc was of no orc subtype.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import classbuilder, states
from rules.activeeffect import ActiveEffect
from tests.test_feats_b3_martial import _attack, _effects, _fight, _rolls, _tells

LANE = Path("content/feats/mechanics/b4-other.json")


def test_the_lane_file_validates():
    doc = json.loads(LANE.read_text("utf-8"))
    assert classbuilder.validate_feat_documents(
        {k: v for k, v in doc.items() if not k.startswith("_")}) == []


# --- the five defects batch 3 found ---------------------------------------------------------

def _lay(engine, target, condition, descriptors, origin="spell:charm-monster"):
    return engine.run(engine.validate([{
        "op": "condition", "actor": "pc", "target": target, "because": "test",
        "params": {"condition": condition, "to": target, "descriptors": descriptors,
                   "duration": 10}}], origin=origin)).outcomes[-1]


@pytest.mark.parametrize("foe", ["gray ooze", "giant spider"])
def test_a_mindless_ooze_or_vermin_cannot_be_charmed(foe):
    """Batch 3: the ooze bundle had no mind-affecting immunity and vermin had no bundle at
    all, and the condition op asked only the printed list — a gray ooze (no "ooze traits"
    printed, no Int score) took a charm. The giant spider prints "mind-affecting effects",
    a plural no immunity row was keyed by, and took it too."""
    scene, engine, pc, foe_actor = _fight(foe=foe)
    out = _lay(engine, "c1", "charmed", ["charm", "mind-affecting"])
    assert "immune" in out.tell, out.tell
    assert not foe_actor.has_condition("charmed")


def test_an_ooze_with_a_mind_can_still_be_charmed():
    """Bestiary, Nonabilities: mindlessness is having no Int score. The brain ooze prints
    Int 15 and "ooze traits" and nothing about minds — 19 shipped oozes have an Int, and
    the ones the book makes immune print it (the shoggoth's "charm effects")."""
    scene, engine, pc, tracker = _fight(foe="brain-ooze")
    assert states.immune_to(tracker, "", "charmed", ("charm", "mind-affecting")) == ""


def test_a_skeleton_cannot_be_frightened():
    """Batch 3: the undead bundle listed charms and compulsions but no fear word, so cause
    fear's shaken landed on a skeleton (undead: "immunity to all mind-affecting effects
    (charms, compulsions, morale effects, patterns, and phantasms)", Bestiary p.309)."""
    scene, engine, pc, bones = _fight(foe="skeleton")
    out = _lay(engine, "c1", "shaken", ["fear", "mind-affecting"], origin="spell:cause-fear")
    assert "immune" in out.tell
    assert not bones.has_condition("shaken")


def test_a_night_s_sleep_takes_the_climber_off_the_wall():
    """Batch 3: `clear_states` swept conditions only, so the climbing situation's
    `recovery.rest` — and smite evil's buff, which carries the same tag — outlived a rest."""
    scene, engine, pc, _ = _fight()
    for kind, key in (("situation", "climbing"), ("buff", "smite evil")):
        pc.apply_effect(ActiveEffect(name=key, kind=kind, key=key, source="test",
                                     origin="author:test", tags=("recovery.rest",)))
    pc.rest("night")
    assert not [e for e in pc.effects if e.key in ("climbing", "smite evil")]


def test_a_rest_sweep_still_leaves_buffs_alone_on_any_other_query():
    """The widening is the `recovery.*` families only: clearing "fatigued" never reaches a
    buff that happens to carry a fatigue tag."""
    scene, engine, pc, _ = _fight()
    pc.apply_effect(ActiveEffect(name="x", kind="buff", key="x", source="test",
                                 origin="author:test", tags=("state.impaired.fatigued",)))
    pc.clear_states("state.impaired.fatigued")
    assert any(e.key == "x" for e in pc.effects)


def test_the_bestiary_orc_is_of_the_orc_subtype():
    """Bestiary 1's orc prints "CE Medium humanoid" with no "(orc)" (read off the PDF,
    p.222), so it had no subtype tag and War Singer's "+2 for creatures of the orc
    subtype" missed the most common orc in the game."""
    scene, engine, pc, orc = _fight(foe="orc")
    assert orc.has_state("subtype.orc")
    pc.feats = list(pc.feats) + ["War Singer"]
    mods = pc._buff_mods("combat_mod", "bardic-performance.dc", {"target_actor": orc})
    assert sum(m.value for m in mods if m.source == "War Singer") == 2


def test_the_class_line_names_the_subtype_only_where_a_block_prints_it():
    """tools/extract_bestiary_pdfs.kin_subtypes: "Orc warrior 1" fills the orc's subtype
    because other humanoid blocks print "(orc)"; a class line's word no block prints as a
    subtype is never taken."""
    import sys

    sys.path.insert(0, "tools")
    from extract_bestiary_pdfs import kin_subtypes

    rows = [{"creature_type": "humanoid", "subtype": "", "_kin": "orc"},
            {"creature_type": "humanoid", "subtype": "", "_kin": "bandit"},
            {"creature_type": "humanoid", "subtype": "orc"}]
    assert kin_subtypes(rows) == 1
    assert [r["subtype"] for r in rows] == ["orc", "", "orc"]
    assert not any("_kin" in r for r in rows)


def test_inexplicable_luck_says_spell_saves_carry_luck():
    """Batch 3 put a spell's saves through the luck doors (`Engine._cast_save` passes
    `kind=save.<x>`), and Inexplicable Luck's not_yet still said they carried none."""
    doc = json.loads(Path("content/feats/mechanics/batch2-styles.json").read_text("utf-8"))
    said = " ".join(doc["inexplicable-luck"]["not_yet"])
    assert "a spell" not in said.split(":")[0]
    assert "a spell calls for" in said


# --- saves and luck ---------------------------------------------------------------------

from rules.bestiary import instantiate  # noqa: E402
from tests.test_feats_b2_styles import Faces, _luck_pc, _save  # noqa: E402


@pytest.mark.parametrize("feat,save", [("Improved Great Fortitude", "fort"),
                                       ("Improved Iron Will", "will"),
                                       ("Improved Lightning Reflexes", "ref")])
def test_the_improved_save_feats_reroll_one_failed_save_a_day(feat, save):
    """CRB: "Once per day, you may reroll a [Fortitude / Will / Reflex] save ... You must
    take the second roll, even if it is worse." A thug who fails on a 2 rolls again (15)
    and makes it; the next failure that day stands. Before this lane none had a document."""
    scene, engine, pc = _luck_pc()
    thug = instantiate("thug", scene=scene, name="the thug")
    thug.feats += [feat]
    scene.add(thug)
    engine.dice = Faces([2, 15, 2])
    first = _save(engine, thug.ref, save=save, dc=14, vis="hidden")
    assert next(o for o in first.outcomes if o.op == "save").verdict == "success"
    assert f"rolls again ({feat})" in next(o for o in first.outcomes if o.op == "luck").tell
    again = _save(engine, thug.ref, save=save, dc=14, vis="hidden")
    assert next(o for o in again.outcomes if o.op == "save").verdict == "failure"


def test_the_player_is_offered_the_improved_save_on_the_popup():
    """The player decides on their own die: a failed Will save is offered the reroll."""
    scene, engine, pc = _luck_pc("Improved Iron Will")
    assert _save(engine, "pc").awaiting
    again = engine.resume(3)
    assert [o["id"] for o in again.awaiting["luck"]] == ["improved-iron-will"]


def test_pure_faith_is_four_sacred_against_poison():
    """UM: "+4 sacred bonus to saving throws against poison" — and nothing against a
    plain save."""
    scene, engine, pc = _luck_pc("Pure Faith")
    pois = sum(m.value for m in pc.save_modifiers("fort", {"against": "poison"})
               if m.source == "Pure Faith")
    plain = sum(m.value for m in pc.save_modifiers("fort") if m.source == "Pure Faith")
    assert (pois, plain) == (4, 0)


def test_extra_rogue_talent_owes_one_more_talent_each_time():
    """APG: "You gain one additional rogue talent", taken more than once. A 4th-level rogue
    is owed two talents by her levels; each copy adds one."""
    from rules import classes

    for copies, want in ((0, 2), (1, 3), (2, 4)):
        scene, engine, pc = _luck_pc(*(["Extra Rogue Talent"] * copies))
        rows = [r for r in classes.owed_rows("rogue", 4, {}, (), classes.feat_slots(pc))
                if r["choice"] == "rogue talent"]
        assert len(rows) == want, copies


from rules.dice import Dice  # noqa: E402


class _Crit(Dice):
    """The swing lands on 20; each confirmation takes the next face in `confirms`."""

    def __init__(self, confirms):
        super().__init__(seed=20261126)
        self.confirms = list(confirms)

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation.strip() == "1d20" and (label or "").startswith("Attack"):
            return self.given(20, modifiers, label)
        if notation.strip() == "1d20" and (label or "").startswith("Confirm critical") \
                and self.confirms:
            return self.given(self.confirms.pop(0), modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _critical(res) -> bool:
    return any(b.get("critical") for o in res.outcomes for b in (o.blows or []))


def _crit_at_pc(feats, confirms):
    scene, engine, pc, thug = _fight(feats=feats)
    pc.hp = pc.hp_max = 200
    engine.dice = _Crit(confirms)
    res = _attack(engine, by="c1", target="pc")
    return pc, res, [r for r in _rolls(res, "Confirm critical")]


def test_deathless_zealot_makes_the_confirmation_roll_twice_and_take_the_lower():
    """UC: "Whenever a creature rolls to confirm a critical hit against you, it must roll
    twice and take the lowest result." 19 then 2: the 2 stands and the threat is a plain
    hit."""
    pc, res, confirms = _crit_at_pc(["Deathless Zealot"], [19, 2])
    assert "takes the lower" in _tells(res)
    assert not _critical(res)
    pc, res, confirms = _crit_at_pc([], [19, 2])
    assert _critical(res)


def test_defiant_luck_forces_a_confirmed_critical_to_be_rerolled_once_a_day():
    """ARG: "Once per day, after ... a critical hit is confirmed against you, you can ...
    force the creature that confirmed the critical hit against you to reroll the critical
    confirmation roll." Confirmed on 19, rerolled to 2; the next day's-worth is gone."""
    pc, res, confirms = _crit_at_pc(["Defiant Luck"], [19, 2, 19])
    assert "Defiant Luck" in _tells(res)
    assert not _critical(res)
    assert pc.pool("defiant-luck").current == 0


def test_defiant_luck_rerolls_a_natural_one_on_a_save():
    """ARG: "after you roll a natural 1 on a saving throw ... you can ... reroll that saving
    throw" — the same once a day as the critical."""
    scene, engine, pc = _luck_pc("Defiant Luck")
    _save(engine, "pc")
    again = engine.resume(1)
    assert [o["id"] for o in again.awaiting["luck"]] == ["defiant-luck"]


def test_bestow_luck_gives_defiant_luck_a_second_use():
    """ARG: "You gain an extra use per day of your Defiant Luck ability." """
    from rules import luck

    scene, engine, pc = _luck_pc("Defiant Luck", "Bestow Luck")
    doc, entry = luck.find(pc, "defiant-luck", "reroll")
    assert luck.uses_left(pc, doc, entry) == 2


# --- meditation -------------------------------------------------------------------------

def _rested(*feats):
    from rules.dice import Dice as _D

    scene, engine, pc = _luck_pc(*feats)
    out = pc.sleep_through("night", _D(seed=1))
    return pc, out


def test_meditation_master_meditates_after_a_full_night_and_holds_the_edge_a_day():
    """F&P: "When you meditate for at least 1 hour after getting at least 8 hours of rest
    ... you gain a +1 insight bonus that you can apply to any d20 roll over the course of
    the next 24 hours". Folded into the morning (the owner's Q40 did the same for the
    wizard's hour of study): the effect for 24 hours, the +1 offered on the popup once."""
    pc, out = _rested("Meditation Master")
    held = next(e for e in pc.effects if states.matches(next(iter(e.tags)), "meditation"))
    assert held.rounds_left == 14400
    assert "meditates" in out["prepared"]
    scene, engine = None, None
    from rules.engine import Engine, Scene

    scene = Scene(location_id="5bbd0c40345f")
    scene.add(pc)
    engine = Engine(scene, Dice(seed=3))
    first = _save(engine, "pc").awaiting
    assert any(o["id"] == "meditation-master" for o in first["luck"])


def test_no_meditation_no_insight():
    """Without the night's meditation the +1 is not on offer: "An unused bonus fades after
    24 hours", and before meditating there is none."""
    scene, engine, pc = _luck_pc("Meditation Master")
    first = _save(engine, "pc").awaiting
    assert not any(o["id"] == "meditation-master" for o in first.get("luck") or ())


def test_body_mastery_is_dr_two_for_the_day_after_meditating():
    """F&P: "For 24 hours after you meditate, you gain damage reduction 2/-." """
    pc, _ = _rested("Meditation Master", "Body Control", "Body Mastery")
    dr = pc.damage_reduction("slashing")
    assert dr is not None and dr.amount == 2 and dr.bypass == ""
    bare, _ = _rested("Meditation Master")
    assert bare.damage_reduction("slashing") is None


def test_bend_with_the_wind_resists_cold_and_fire_five_after_meditating():
    """F&P: "For 24 hours after you meditate, you gain cold resistance 5 and fire
    resistance 5." A 7-point fire burn leaves 2."""
    pc, _ = _rested("Meditation Master", "Body Control", "Bend with the Wind")
    pc.hp = pc.hp_max
    got = pc.take_damage(7, "fire")
    assert pc.hp_max - pc.hp == 2, got


def test_body_control_is_plus_one_fortitude_against_poison_after_meditating():
    pc, _ = _rested("Meditation Master", "Body Control")
    assert sum(m.value for m in pc.save_modifiers("fort", {"against": "poison"})
               if m.source == "Body Control") == 1
    assert sum(m.value for m in pc.save_modifiers("fort")
               if m.source == "Body Control") == 0


# --- healing, cold and senses -------------------------------------------------------------

def test_fast_healer_adds_half_con_to_a_night_and_to_a_cure():
    """APG: "When you regain hit points by resting or through magical healing, you recover
    additional hit points equal to half your Constitution modifier (minimum +1)." Con 14:
    +1 on the night and +1 on a stamped cure; nothing on a heal with no stamp."""
    scene, engine, pc = _luck_pc("Fast Healer")
    pc.abilities["con"] = 14
    pc.hp = 1
    pc.rest("night")
    assert pc.hp == min(pc.hp_max, 1 + pc.level + 1)
    pc.hp = 1
    engine.run(engine.validate([{"op": "heal", "actor": "pc", "target": "pc",
                                 "because": "test", "params": {"amount": 3}}],
                               origin="spell:cure-light-wounds"))
    assert pc.hp == 5


def test_attuned_to_the_wild_doubles_the_night_in_its_own_terrain():
    """ARG: "While you are in your selected terrain type, your natural healing rate ...
    doubles." In the forest a 3rd-level elf heals 6 a night; on the plains, 3."""
    for at, want in (("forest", 6), ("plains", 3)):
        scene, engine, pc = _luck_pc("Attuned to the Wild (forest)")
        pc.level = 3
        from rules import classfeatures

        pc.hp = 1
        orig = classfeatures.bearer_facts
        try:
            classfeatures.bearer_facts = lambda a, _o=orig, _t=at: dict(_o(a), terrain=_t)
            pc.rest("night")
        finally:
            classfeatures.bearer_facts = orig
        assert pc.hp - 1 == want, at


def test_rugged_northerner_feels_no_cold_weather():
    """ISWG: "You are not impacted at all by normal cold weather conditions ... you do not
    become fatigued by frostbite or hypothermia." Eight hours of cold: no save, no harm."""
    scene, engine, pc = _luck_pc("Rugged Northerner")
    rolls, fx, said = engine._exposure(pc, "cold", 8)
    assert (rolls, fx) == ([], []) and "at home in the cold" in said
    scene, engine, plain = _luck_pc()
    rolls, fx, said = engine._exposure(plain, "cold", 8)
    assert len(rolls) >= 1


def _hidden_thug(feats, gap_squares):
    from rules import awareness

    scene, engine, pc, thug = _fight(feats=feats, at=((6, 10), (6 + gap_squares, 10)))
    thug.apply_effect(ActiveEffect(name="hidden", kind="situation", key="hidden",
                                   source="test", origin="author:test",
                                   tags=(awareness.HIDDEN,)))
    return scene, pc, thug


def test_keen_scent_smells_a_hidden_foe_near_and_pinpoints_it_beside():
    """Scent (UMR): "detect opponents within 30 feet ... When the creature is within 5 feet
    of the source, it pinpoints the source's location." Before the lane the tag had no
    reader at all."""
    from rules import awareness

    scene, pc, thug = _hidden_thug(["Keen Scent"], 3)
    assert awareness.senses(scene, pc, thug) == "near"
    assert not awareness.locates(scene, pc, thug)
    scene, pc, thug = _hidden_thug(["Keen Scent"], 1)
    assert awareness.locates(scene, pc, thug)
    scene, pc, thug = _hidden_thug([], 1)
    assert not awareness.locates(scene, pc, thug)


def test_stone_sense_pinpoints_what_stands_within_ten_feet():
    """Stone Sense (APG): "tremorsense to a range of 10 feet" — "automatically pinpoint the
    location of anything that is in contact with the ground"."""
    from rules import awareness

    scene, pc, thug = _hidden_thug(["Stone Sense"], 2)
    assert awareness.locates(scene, pc, thug)
    scene, pc, thug = _hidden_thug(["Stone Sense"], 3)
    assert not awareness.locates(scene, pc, thug)


# --- fear and resolve ---------------------------------------------------------------------

def test_stoic_is_plus_one_against_fear():
    scene, engine, pc = _luck_pc("Stoic")
    assert sum(m.value for m in pc.save_modifiers("will", {"against": ("fear",)})
               if m.source == "Stoic") == 1


def test_courage_in_numbers_counts_allies_within_ten_feet_up_to_eight():
    """DSH: "+2 morale bonus on saves against fear for every ally within 10 feet who
    possesses this feat (maximum +8)". One ally two squares off: +2."""
    from rules.sheet import Moment, _MOMENT

    scene, engine, pc, thug = _fight(feats=["Courage in Numbers"],
                                     ally=((8, 10), ["Courage in Numbers"]))
    token = _MOMENT.set(Moment(scene=scene))
    try:
        got = sum(m.value for m in pc.save_modifiers("will", {"against": ("fear",)})
                  if m.source.lower() == "courage in numbers")
    finally:
        _MOMENT.reset(token)
    assert got == 2


def test_a_paladins_aura_of_resolve_reaches_ten_feet_and_twenty_with_ultimate_resolve():
    """CRB: "Each ally within 10 feet of her gains a +4 morale bonus on saving throws
    against charm effects" — a not_yet on the paladin's document until this lane. UM,
    Ultimate Resolve: "Your aura of resolve is a 20-foot emanation, and does not end if you
    fall unconscious." The paladin stands 15 feet off."""
    from rules.sheet import Moment, _MOMENT

    def bonus(feats, down=False):
        scene, engine, pc, thug = _fight(ally=((9, 10), feats))
        pal = scene.get("ally")
        pal.char_class, pal.level = "paladin", 12
        if down:
            pal.add_condition("unconscious", source="test")
        token = _MOMENT.set(Moment(scene=scene))
        try:
            return sum(m.value for m in pc.save_modifiers("will", {"against": ("charm",)})
                       if "aura" in m.source)
        finally:
            _MOMENT.reset(token)

    assert bonus([]) == 0
    assert bonus(["Ultimate Resolve"]) == 4
    assert bonus(["Ultimate Resolve"], down=True) == 4


# --- the rest of the lane's mechanics ------------------------------------------------------

def test_stage_combatant_pulls_a_focused_blow_to_nonlethal_with_no_penalty():
    """UC: "When you make an attack with a weapon that you have Weapon Focus in, you take no
    penalty on the attack roll when you are attempting to make an attack that deals ...
    nonlethal damage." Borin's longsword (his Weapon Focus) loses the -4; his dagger keeps
    it."""
    scene, engine, pc = _luck_pc("Stage Combatant")
    assert pc.lethality_swap("longsword", "nonlethal") == ""
    assert pc.lethality_swap("dagger", "nonlethal") != ""
    bare = _luck_pc()[2]
    assert bare.lethality_swap("longsword", "nonlethal") != ""


def test_fast_empathy_lets_wild_empathy_into_a_fight():
    """UM: "Using wild empathy is a standard action for you" (normally a minute, which the
    engine refuses in a fight's round)."""
    from rules import animals

    for feats, refused in (([], True), (["Fast Empathy"], False)):
        scene, engine, pc, wolf = _fight(foe="wolf", feats=feats, cls="druid", level=3)
        out = animals.wild_empathy(engine, engine.validate([{
            "op": "check", "actor": "pc", "target": "c1", "visibility": "hidden",
            "params": {"skill": "handle animal"}}])[0], pc, wolf, {})
        said = (out.tell or "") if out is not None else ""
        assert ("calm work" in said) == refused, said


def test_ferocious_summons_gives_each_summons_ferocity():
    """ARG: "Creatures you summon gain the ferocity universal monster ability" — the tag the
    hit-point ladder asks: below 0 the summoned wolf stays up, staggered."""
    scene, engine, pc, thug = _fight(feats=["Ferocious Summons"])
    wolf = instantiate("wolf", scene=scene, name="the summoned wolf")
    scene.add(wolf)
    said = engine._summons_granted(pc, [{"ref": wolf.ref}], {"rounds": 5})
    assert wolf.has_state("ferocity") and said
    wolf.hp = -2
    wolf.apply_hp_state()
    assert not wolf.has_condition("unconscious")


def test_sure_grasp_climbs_on_the_better_of_two_dice():
    """UC: "Roll twice while climbing ... and take the higher result"."""
    from rules import bodyskills

    scene, engine, pc = _luck_pc("Sure Grasp")
    engine.dice = Faces([3, 17])
    first = engine.dice.d20([], label="Climb check")
    got = bodyskills._twice(engine, pc, first, "skill.climb")
    assert got.natural == 17
    scene, engine, plain = _luck_pc()
    engine.dice = Faces([3, 17])
    first = engine.dice.d20([], label="Climb check")
    assert bodyskills._twice(engine, plain, first, "skill.climb").natural == 3


def test_stoic_steels_against_a_casters_fear_for_a_day():
    """ISWG: "If you successfully save against any fear effect, you are immune to further
    fear effects from that source for 24 hours." Saved once against the hedge wizard's
    cause fear: the next one finds no hold whatever the die."""
    from rules import spells
    from tests.test_skill_uses_mind import _here, _wizard

    scene, engine, pc = _here(faces={"Will save": 20}, rest=10)
    pc.feats = list(pc.feats) + ["Stoic"]
    wiz = _wizard(scene)
    wiz.spellbook = list(wiz.spellbook) + ["cause-fear"]
    wiz.prepared = dict(wiz.prepared, **{"cause-fear": 2})
    spell = spells.get("cause-fear")
    state = {"rolls": [], "tells": [], "effects": []}
    intent = engine.validate([{"op": "cast", "actor": "c2", "target": "pc",
                               "visibility": "hidden", "params": {"spell": "cause-fear"}}])[0]
    saved, _ = engine._cast_save(intent, pc, "will", 30, spell, {}, state)
    assert saved and pc.has_state(f"immune.fear.from.{wiz.ref}")
    state2 = {"rolls": [], "tells": [], "effects": []}
    engine.dice.faces = {"Will save": 1}
    saved2, _ = engine._cast_save(intent, pc, "will", 30, spell, {}, state2)
    assert saved2 and "Stoic" in " ".join(state2["tells"])


def test_diehard_fights_on_below_zero_and_deathless_initiate_is_not_staggered():
    """CRB Diehard: "You may choose to act as if you were disabled, rather than dying ...
    When using this feat, you are staggered." UC Deathless Initiate: "You are not staggered
    while using the Diehard feat ... while using the Diehard feat, you gain a +2 bonus on
    melee attacks and damage rolls." At -3 she stands, disabled, not dying."""
    # The fight-on alone (Deathless Master's document carries it too): disabled, staggered.
    scene, engine, pc = _luck_pc("Diehard", "Endurance", "Deathless Master")
    pc.hp = -3
    pc.apply_hp_state()
    assert pc.has_condition("disabled") and pc.has_state("state.impaired.staggered")
    assert not pc.has_condition("dying") and not pc.is_down
    # Deathless Initiate: neither limit, still up, still not dying.
    scene, engine, pc = _luck_pc("Diehard", "Endurance", "Deathless Initiate")
    pc.hp = -3
    pc.apply_hp_state()
    assert not pc.has_condition("dying") and not pc.has_condition("unconscious")
    assert not pc.has_state("state.impaired.staggered") and not pc.is_down
    assert pc.has_state("state.fighting-on")
    assert sum(m.value for m in pc.attack_modifiers("longsword")
               if m.source.lower() == "deathless initiate") == 2
    pc.heal(10)
    pc.apply_hp_state()
    pc.clear_states("recovery.hit-points")
    assert not pc.has_state("state.fighting-on")


def test_deathless_master_pays_no_hit_point_for_acting_below_zero():
    """UC: "When you are at 0 or fewer hit points, you do not lose 1 hit point when you take
    an action." Below 0 with Deathless Initiate a full attack (a full-round action) costs
    1; with Deathless Master, none."""
    for feats, cost in ((["Diehard", "Deathless Initiate"], 1),
                        (["Diehard", "Deathless Initiate", "Deathless Master"], 0)):
        scene, engine, pc, thug = _fight(feats=feats)
        pc.hp = -2
        pc.apply_hp_state()
        assert not pc.is_down
        was = pc.hp
        res = _attack(engine, by="pc", target="c1", full_attack=True)
        assert was - pc.hp == cost, (feats, _tells(res))


def test_lookout_lifts_an_unaware_holder_beside_an_aware_one_into_the_surprise_round():
    """APG: "Whenever you are adjacent to an ally who also has this feat, you may act in the
    surprise round as long as your ally would normally be able to act"."""
    from rules import surprise

    scene, engine, pc, thug = _fight(feats=["Lookout"], ally=((7, 11), ["Lookout"]))
    sides = {"pc": ["pc", "ally"], "them": ["c1"]}
    aware, unaware = ["c1", "pc"], ["ally"]
    full = surprise._lookouts(engine, sides, aware, unaware)
    assert "ally" in aware and unaware == [] and full == set()
    aware, unaware = ["c1", "pc", "ally"], []
    assert surprise._lookouts(engine, sides, aware, unaware) == {"pc", "ally"}


def test_shield_wall_raises_ac_by_the_ally_s_shield():
    """APG: beside an ally with the feat, "If your ally is wielding a buckler or a light
    shield, your shield bonus increases by +1 ... a heavy shield or a tower shield ... +2"."""
    from rules.sheet import Moment, _MOMENT

    for ally_shield, want in (("light shield", 1), ("heavy shield", 2), ("none", 0)):
        scene, engine, pc, thug = _fight(feats=["Shield Wall"],
                                         ally=((7, 10), ["Shield Wall"]))
        pc.shield = "light shield"
        scene.get("ally").shield = ally_shield
        token = _MOMENT.set(Moment(scene=scene))
        try:
            got = sum(m.value for m in pc.ac_modifiers()
                      if m.source.lower() == "shield wall")
        finally:
            _MOMENT.reset(token)
        assert got == want, ally_shield


def test_acrobatic_steps_and_light_step_cross_difficult_ground_as_normal():
    """CRB Acrobatic Steps: "move through up to 15 feet of difficult terrain each round as
    if it were normal terrain". APG Light Step: "ignore the effects of difficult terrain in
    natural environments". Nimble Moves' not_yet measured it: nothing lifted difficult
    terrain's double cost. A band of bramble six squares deep: 60 ft for anybody, 45 with the
    first three easy, 30 with all of them."""
    from rules.grid import Grid

    grid = Grid(20, 20)
    grid.difficult = {(x, y) for x in range(1, 7) for y in range(20)}
    end = (6, 5)
    assert grid.reachable((0, 5), 100)[end] == 60
    assert grid.reachable((0, 5), 100, easy_ft=15)[end] == 45
    assert grid.reachable((0, 5), 100, easy_ft=Grid.EASY_ALL)[end] == 30
    scene, engine, pc = _luck_pc("Acrobatic Steps")
    assert engine._easy_ft(pc) == 15
