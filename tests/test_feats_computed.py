"""Feats the sheet called "not computed" that the engine now applies on its own.

The owner, 2026-10-09, with a screenshot of the Sheet's feat list showing Endurance and
Combat Casting tagged "not computed" — "the rules carry the feat and its text but apply no
number for it; those are yours to invoke at the table": *"these should be automatically
used when applicable."*

What was measured before the change:

- **Endurance**: every roll its benefit names that the engine makes was built by hand —
  survival's hourly thirst check and daily hunger check were `[Modifier(con)]`, the breath
  held underwater the same, and the heat hazard rolled its 1d4 with no save at all. No
  document could reach any of them, so there was nothing for a feat to modify.
- **Combat Casting**: there was no concentration check anywhere in the engine. The cast
  op had accepted a `defensively` param since it was written and nothing read it, and a
  spell cast beside a thug provoked nothing — so casting defensively would have been a
  risk with no reason to take it.
- **The sweep**: 46 of 1,474 feats had a document. Five shipped skill pairs carried a
  `not_yet` for their ten-rank rung; Point-Blank Shot's range clause was dropped on every
  shot because the attack op passed no range.

Now: ability checks and concentration go through the funnel (`ability_check_modifiers`,
`concentration_modifiers`), each roll carries what it is made against (`effectspec.
AGAINST`, `CASTING_SITUATIONS`), a cast provokes unless cast defensively, and the documents
say which clauses still wait and on what.
"""
from __future__ import annotations

import pytest

from rules import casting, classbuilder, effectspec, feats, reactions, spells, survival
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.sheet import from_dict, full_sheet, load_pc, to_dict

HOUR = 60


class _Rng:
    """Every d20 comes off the list; every other die rolls its lowest face."""

    def __init__(self, d20s):
        self.d20s = list(d20s)

    def randint(self, a, b):
        return self.d20s.pop(0) if b == 20 and self.d20s else a


class Loaded(Dice):
    def __init__(self, *d20s):
        super().__init__(0)
        self._rng = _Rng(d20s)


def _pc(*held, **kw):
    pc = from_dict(to_dict(load_pc("fixtures/pc-kesst.json")), ref="pc")
    pc.kind = "pc"
    pc.feats = list(held)
    for k, v in kw.items():
        setattr(pc, k, v)
    return pc


def _named(mods, source):
    return [m.value for m in mods if m.source == source]


# --- the documents -------------------------------------------------------------------------

def test_the_shipped_documents_validate_and_the_two_named_feats_are_computed():
    """The owner's screenshot: Endurance and Combat Casting tagged "not computed". The tag
    is `applied: False` on the sheet's feat row, which is "no document"."""
    assert classbuilder.validate_feat_documents(feats.documents()) == []
    rows = {r["name"]: r for r in full_sheet(_pc("Endurance", "Combat Casting"))["feats"]}
    assert rows["Endurance"]["applied"] and rows["Combat Casting"]["applied"]
    assert "against thirst" in rows["Endurance"]["effect"]
    assert "casting defensively" in rows["Combat Casting"]["effect"]


def test_a_when_naming_a_danger_nothing_rolls_against_is_refused():
    """`against` took any string until now and is answered by equality: "dehydration"
    where the survival clock passes "thirst" would have held for nobody, silently."""
    bad = classbuilder.validate_feat_document("endurance", {"modifiers": [
        {"type": "combat_mod", "target": "con_check", "amount": 4, "bonus_type": "untyped",
         "when": {"against": "dehydration"}}]})
    assert len(bad) == 1 and "against" in bad[0] and "thirst" in bad[0]
    bad = classbuilder.validate_feat_document("combat-casting", {"modifiers": [
        {"type": "combat_mod", "target": "concentration", "amount": 4,
         "bonus_type": "untyped", "when": {"casting": "upside down"}}]})
    assert len(bad) == 1 and "defensively" in bad[0]
    for word in ("thirst", "starvation", "breath", "cold", "heat"):
        assert word in effectspec.AGAINST


# --- Endurance -----------------------------------------------------------------------------

def test_endurance_is_on_the_constitution_check_against_thirst_and_starvation_and_breath():
    pc = _pc("Endurance")
    for danger in ("thirst", "starvation", "breath"):
        assert _named(pc.ability_check_modifiers("con", {"against": danger}),
                      "Endurance") == [4], danger
    # Not on a Constitution check that is about something else (stabilising, a bare check).
    assert not _named(pc.ability_check_modifiers("con"), "Endurance")
    assert not _named(_pc().ability_check_modifiers("con", {"against": "thirst"}),
                      "Endurance")


def test_endurance_is_on_the_fortitude_save_against_cold_and_heat_and_nothing_else():
    pc = _pc("Endurance")
    assert _named(pc.save_modifiers("fort", {"against": "cold"}), "Endurance") == [4]
    assert _named(pc.save_modifiers("fort", {"against": "heat"}), "Endurance") == [4]
    assert not _named(pc.save_modifiers("fort", {"against": "poison"}), "Endurance")
    assert not _named(pc.save_modifiers("fort"), "Endurance")


def _parched(*held):
    pc = _pc(*held)
    pc.hp_max = pc.hp = 40
    pc.watered_minutes = (survival.hours_until_thirsty(pc) - 1) * HOUR
    pc.fed_minutes = pc.awake_minutes = 0
    s = Scene(location_id="bde94b038cba")
    s.add(pc)
    s.clock_minutes = 9 * HOUR
    return s, Engine(s, Dice(seed=4))


def test_a_character_with_endurance_going_without_water_sees_it_on_the_thirst_check():
    """The owner's check, end to end through the clock's door: a wait past the grace
    rolls the hourly thirst check, and the body's outcome carries the roll with "+4
    Endurance" beside the Constitution. Before, the check was a total in a sentence."""
    for held, want in ((("Endurance",), [4]), ((), [])):
        s, e = _parched(*held)
        res = e.run(e.validate([{"op": "advance_time", "actor": "pc", "because": "waits",
                                 "params": {"amount": 3, "unit": "hour"}}]))
        body = [o for o in res.outcomes if o.op == "body"]
        assert body, "the thirst check was told"
        thirst = [r for o in body for r in o.rolls if r.label == "Thirst check"]
        assert thirst, [r.label for o in body for r in o.rolls]
        assert _named(thirst[0].modifiers, "Endurance") == want
        assert thirst[0].visibility == "player"


def test_three_weeks_of_passed_checks_do_not_carry_three_weeks_of_rolls():
    """The roll rides on the first check of each kind and on every failure only: a
    21-day wait is five hundred hourly thirst checks and the passes are one sentence."""
    toll = survival.Toll(checks=[{"kind": "Thirst", "passed": True, "rolled": {"x": 1}}
                                 for _ in range(500)])
    kept = [c for c in toll.as_dict()["checks"] if c.get("rolled")]
    assert len(kept) == 1


def test_endurance_holds_the_breath_underwater():
    """Engine.breathe's Constitution check, in the `breath` context."""
    pc = _pc("Endurance")
    mods = pc.ability_check_modifiers("con", {"against": "breath"})
    assert "Endurance" in [m.source for m in mods]


def test_the_heat_hazard_rolls_the_fortitude_save_its_source_names_with_endurance_on_it():
    """hazards.json's heat row said "on a failed Fortitude save" and rolled the 1d4 with
    no save at all — the cold row's defect, fixed for cold on 2026-10-01 and left on heat.
    Endurance's "Fortitude saves made to resist damage from hot or cold environments" had
    no heat save to land on."""
    s = Scene(location_id="5bbd0c40345f")
    pc = _pc("Endurance")
    s.add(pc)
    e = Engine(s, Loaded(20, 20))
    out = e.run(e.validate([{"op": "hazard", "actor": "pc",
                             "params": {"rule": "heat", "hours": 2, "to": "pc"}}],
                           origin="author:test")).outcomes[0]
    saves = [r for r in out.rolls if "Fortitude" in r.label]
    assert len(saves) == 2
    assert all(_named(r.modifiers, "Endurance") == [4] for r in saves)
    assert "the heat did not get in" in out.tell and pc.nonlethal == 0


def test_a_printed_creature_keeps_its_situational_feat_terms():
    """A printed Fort is the always-true number; "+4 vs. cold" is printed beside it, not
    inside it. Until now the feat channel was shut entirely under a printed save, so a
    printed creature with Endurance never had it, while Iron Will stays out of a printed
    Will (it is inside it)."""
    pc = _pc("Endurance", "Iron Will")
    pc.flat_saves = {"fort": 5, "will": 3}
    assert _named(pc.save_modifiers("fort", {"against": "cold"}), "Endurance") == [4]
    assert not _named(pc.save_modifiers("will"), "Iron Will")


def test_endurance_says_which_clauses_still_wait_and_on_what():
    waits = " ".join(feats.document("endurance")["not_yet"]).lower()
    for clause in ("swim", "running", "forced march", "suffocation", "armour"):
        assert clause in waits, clause


# --- Combat Casting and concentration -----------------------------------------------------

def _wizard(*held, level=1, int_score=11, book=("mage-armor", "magic-missile")):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "wizard", "level": level, "ranks": {}, "armour": "none",
              "feats": list(held)})
    d["abilities"]["int"] = int_score
    d["spellbook"] = list(book)
    d["prepared"] = {k: 3 for k in book}
    pc = from_dict(d, ref="pc")
    pc.kind = "pc"
    return pc


def _board(pc, dice, thug_at=(6, 5)):
    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
    s.add(pc, at=(5, 5))
    s.add(instantiate("thug", scene=s, name="the thug"), at=thug_at)
    s.sides = {"us": ["pc"], "them": ["c1"]}
    s.initiative = [("pc", 20), ("c1", 10)]
    s.round, s.turn = 1, 0
    return s, Engine(s, dice)


def _cast(e, defensively=None, spell="mage-armor"):
    params = {"spell": spell, "at": "pc"}
    if defensively is not None:
        params["defensively"] = defensively
    return e.run(e.validate([{"op": "cast", "actor": "pc", "because": "she casts",
                              "params": params}]))


def test_casting_defensively_rolls_concentration_with_combat_casting_on_it():
    """The owner's check: casting defensively shows +4 (Combat Casting) on the
    concentration roll, DC 15 + twice the spell's level, and provokes nothing."""
    pc = _wizard("Combat Casting")
    s, e = _board(pc, Loaded(12))
    res = _cast(e, defensively=True)
    assert [o.op for o in res.outcomes] == ["cast"]          # no attack of opportunity
    conc = [r for r in res.outcomes[0].rolls if r.label.startswith("Concentration")]
    assert len(conc) == 1 and "DC 17" in conc[0].label
    assert _named(conc[0].modifiers, "Combat Casting") == [4]
    assert _named(conc[0].modifiers, "caster level") == [1]
    assert conc[0].total == 17 and "holds Mage Armor together" in res.outcomes[0].tell


def test_a_failed_defensive_cast_loses_the_spell_and_its_slot():
    pc = _wizard()                                        # no Combat Casting: 1 + 0 + 12
    s, e = _board(pc, Loaded(12))
    left = casting.slots_left(pc, 1)
    out = _cast(e, defensively=True).outcomes[0]
    assert any(x.get("kind") == "concentration_lost" for x in out.effects)
    assert "loses it" in out.tell and casting.slots_left(pc, 1) == left - 1
    assert not pc.has_state("buff")                       # nothing landed
    assert not any(x.get("kind") == "cast" for x in out.effects)


def test_a_spell_cast_within_reach_provokes_and_one_out_of_reach_does_not():
    """CRB Table 8-2, "Cast a spell": attack of opportunity, yes. Until 2026-10-09 a
    cast provoked nothing, and the thug beside the wizard watched it happen."""
    s, e = _board(_wizard(), Dice(seed=2))
    res = _cast(e)
    assert [o.op for o in res.outcomes][:2] == ["attack", "cast"]
    assert s.reacted == {"c1:attack_of_opportunity": 1}
    s, e = _board(_wizard(), Dice(seed=2), thug_at=(12, 5))
    assert [o.op for o in _cast(e).outcomes] == ["cast"]


def test_defensively_written_as_the_word_false_is_not_defensive():
    """A yes/no param written as a word ("false") was truthy to `bool()` — the extinguish
    roll's defect (lane C3). `defensively` joins FLAG_PARAMS, so the cast provokes."""
    s, e = _board(_wizard(), Dice(seed=2))
    assert [o.op for o in _cast(e, defensively="false").outcomes][:1] == ["attack"]


def test_struck_while_casting_is_a_concentration_check_on_the_damage():
    """"If you take damage while trying to cast a spell, you must make a concentration
    check (DC 10 + damage taken + spell level)" (CRB p.206). The provoked sap lands, and
    the cast reads what it took. Combat Casting does not help here — the book's clause is
    defensive or grappled only."""
    pc = _wizard("Combat Casting")
    s, e = _board(pc, Loaded(19, 1))
    res = _cast(e)
    assert [o.op for o in res.outcomes] == ["attack", "cast"]
    cast = res.outcomes[1]
    conc = [r for r in cast.rolls if r.label.startswith("Concentration")]
    assert conc and "struck for" in conc[0].label
    assert not _named(conc[0].modifiers, "Combat Casting")
    assert any(x.get("kind") == "concentration_lost" for x in cast.effects)


def test_a_grappled_caster_checks_against_the_grapplers_cmb(monkeypatch):
    """"A grappled character who attempts to cast a spell ... must make a concentration
    check (DC 10 + grappler's CMB + spell level)" (CRB, Grappled). The grappler was a
    name in the condition's `source` sentence; the grapple now writes its ref."""
    monkeypatch.setattr(reactions, "provoked_by_maneuver", lambda *a, **k: [])
    pc = _wizard("Combat Casting")
    s, e = _board(pc, Loaded(20, 20, 15))
    e.run(e.validate([{"op": "attack", "actor": "c1", "target": "pc", "because": "grabs",
                       "params": {"manoeuvre": "grapple"}}]))
    assert pc.has_state("state.held.grappled")
    held = [x for x in pc.effects if "state.held.grappled" in x.tags]
    assert held and held[0].payload.get("by") == "c1"
    s.turn = 0
    res = _cast(e, defensively=True)          # defensively: no swing in the way
    conc = [r for r in res.outcomes[-1].rolls if "held by" in r.label]
    assert conc and _named(conc[0].modifiers, "Combat Casting") == [4]
    cmb = sum(m.value for m in s.actors["c1"].cmb_modifiers("grapple"))
    assert f"DC {10 + cmb + 1}" in conc[0].label


# --- the sweep ------------------------------------------------------------------------------

@pytest.mark.parametrize("fid,skills", [
    ("alertness", ("perception", "sense motive")), ("athletic", ("climb", "swim")),
    ("self-sufficient", ("heal", "survival")),
    ("magical-aptitude", ("spellcraft", "use magic device")),
    ("animal-affinity", ("handle animal", "ride")),
    ("deft-hands", ("disable device", "sleight of hand")),
    ("stealthy", ("stealth", "escape artist")), ("acrobatic", ("acrobatics", "fly")),
    ("deceitful", ("bluff", "disguise")), ("persuasive", ("diplomacy", "intimidate"))])
def test_a_skill_pair_is_two_then_four_at_ten_ranks(fid, skills):
    """"If you have 10 or more ranks in one of these skills, the bonus increases to +4
    for that skill." Five of these shipped with that clause under `not_yet`; five more
    (Athletic, Self-Sufficient, Magical Aptitude, Animal Affinity, Deft Hands) were not
    computed at all."""
    name = feats.get(fid).name
    for skill in skills:
        pc = _pc(fid)
        pc.ranks = {skill: 1}
        assert _named(pc.skill_modifiers(skill), name) == [2], skill
        pc.ranks = {skill: 10}
        assert _named(pc.skill_modifiers(skill), name) == [4], skill
    assert not feats.document(fid).get("not_yet")


def test_skill_focus_binds_to_the_skill_in_its_parenthetical():
    pc = _pc("Skill Focus (perception)")
    pc.ranks = {"perception": 2}
    assert _named(pc.skill_modifiers("perception"), "Skill Focus") == [3]
    assert not _named(pc.skill_modifiers("stealth"), "Skill Focus")
    pc.ranks = {"perception": 10}
    assert _named(pc.skill_modifiers("perception"), "Skill Focus") == [6]
    assert not _named(_pc("Skill Focus").skill_modifiers("perception"), "Skill Focus")


def test_spell_focus_raises_its_schools_dc_and_no_other():
    w = _wizard("Spell Focus (evocation)", level=5, int_score=16)
    fire, armour = spells.get("fireball"), spells.get("mage-armor")
    plain = casting.save_dc(w, 3)
    assert casting.save_dc(w, 3, fire) == plain + 1
    assert casting.save_dc(w, 1, armour) == casting.save_dc(w, 1)


def test_spell_penetration_is_on_the_check_against_spell_resistance_and_is_not_resistance():
    """"+2 on caster level checks made to overcome a creature's spell resistance". The
    vocabulary's `spell_resistance` target is both the caster's bonus on that check
    (`Engine._resists`) and a creature's own rating (`spell_resistance_rating`), so the
    feat's term is a `when` on the check's context: written unconditionally it would
    have given every wizard who took it spell resistance 2."""
    from tests.test_e_magic_harm import board
    from tests.test_item_powers import _run

    s, e, man = board(fight=True)
    pc = s.actors["pc"]
    pc.feats = list(pc.feats) + ["Spell Penetration"]
    assert pc.spell_resistance_rating()[0] == 0
    who = s.actors[man]
    who.hp = who.hp_max = 100
    who.wear({"id": "sr", "name": "Warded Band", "slot": "ring",
              "specs": [{"type": "spell_resistance", "amount": 19}]}, 0)
    r = _run(e, [{"op": "cast", "actor": "pc", "because": "t", "visibility": "player",
                  "params": {"spell": "burning-hands", "aim": f"ref:{who.ref}"}}])
    seen = []
    for _ in range(10):
        if r.awaiting is None:
            break
        if r.awaiting["label"].startswith("Caster level"):
            seen = [(m["source"], m["value"]) for m in r.awaiting["breakdown"]]
        r = e.resume(int(r.awaiting["min"]))
    assert ("Spell Penetration", 2) in seen, seen


def test_fleet_is_five_feet_in_light_armour_and_nothing_in_medium():
    pc = _pc("Fleet")
    pc.armour = "leather"
    assert pc.speed_feet == pc.speed + 5
    pc.armour = "scale mail"
    assert pc.speed_feet == _pc(armour="scale mail").speed_feet


def test_shield_focus_needs_a_shield():
    pc = _pc("Shield Focus")
    bare = pc.ac()
    pc.shield = "heavy wooden shield"
    with_shield = pc.ac()
    plain = _pc(shield="heavy wooden shield").ac()
    assert with_shield == plain + 1 and bare == _pc().ac()


def test_diehard_stabilises_without_the_roll_and_loses_no_blood():
    pc = _pc("Diehard")
    pc.hp = -3
    pc.apply_hp_state()
    assert pc.has_condition("dying")
    out = pc.bleed_out(Dice(seed=1))
    assert out["outcome"] == "stable" and out.get("automatic")
    assert pc.hp == -3 and pc.has_condition("stable")


def test_greater_focus_and_specialization_stack_with_the_lesser():
    pc = _pc("Weapon Focus (rapier)", "Greater Weapon Focus (rapier)",
             "Weapon Specialization (rapier)", "Greater Weapon Specialization (rapier)")
    atk = pc.attack_modifiers("rapier")
    dmg = pc.damage_modifiers("rapier")
    assert _named(atk, "Weapon Focus") == [1] and _named(atk, "Greater Weapon Focus") == [1]
    assert _named(dmg, "Greater Weapon Specialization") == [2]
    assert not _named(pc.attack_modifiers("dagger"), "Greater Weapon Focus")


class _Percent(Dice):
    """d20s and d100s off their own lists; everything else its lowest face."""

    def __init__(self, d20s, d100s):
        super().__init__(0)
        lists = {20: list(d20s), 100: list(d100s)}

        class _R:
            def randint(self, a, b):
                return lists[b].pop(0) if lists.get(b) else a

        self._rng = _R()


def test_blind_fight_rerolls_a_melee_miss_chance_once(monkeypatch):
    """"In melee, every time you miss because of concealment, you can reroll your miss
    chance percentile roll one time." The feat document's tag, read at the miss roll."""
    monkeypatch.setattr(Engine, "_concealment_of", lambda self, a, d: (50, "blur"))
    for held, landed in ((("Blind-Fight",), True), ((), False)):
        s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
        s.add(_pc(*held), at=(5, 5))
        s.add(instantiate("thug", scene=s, name="the thug"), at=(6, 5))
        s.sides = {"us": ["pc"], "them": ["c1"]}
        s.initiative = [("pc", 20), ("c1", 10)]
        s.round, s.turn = 1, 0
        e = Engine(s, _Percent([19], [10, 80]))
        out = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                                 "because": "stab", "visibility": "hidden",
                                 "params": {"weapon": "rapier"}}]))
        assert out.status == "complete"
        tell = " ".join(o.tell for o in out.outcomes)
        assert tell and ("finds nothing there" not in tell) == landed, tell


def test_intimidating_prowess_adds_strength():
    pc = _pc("Intimidating Prowess")
    pc.abilities["str"] = 16
    assert _named(pc.skill_modifiers("intimidate"), "Intimidating Prowess") == [3]
