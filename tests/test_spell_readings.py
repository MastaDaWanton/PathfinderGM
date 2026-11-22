"""The regex layer read by hand (lane B, 2026-11-22), and what the cast does with a reading.

The audit of 2026-11-22 found 341 of the 376 "FULL" spells were `spells-mechanics.json` as a
regex made it, with nobody having checked one. The critic drove one cast: web at caster
level 7 dealt "the thug takes 3 fire" (13 -> 10 hp) and turned him hostile. Dimension door
hit for 1d6 on a failed Will save; phantasmal killer did 3d6 instead of killing. The
eleven-spell veto in test_casting_executes.py caught none of them, because it listed spells
somebody had already noticed.

All 354 were read into content/spells/mechanics/part-21.json. Of the 354, 231 were wrong
(a number or an effect the spell does not do), 75 incomplete (the dice right, the rest
missing) and 48 right. These tests hold what the reading changed and the four engine gaps
the reading exposed.
"""
from __future__ import annotations

import pytest

from rules import effectspec, spells as spells_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict


def caster(spell_ids, level=7, klass="wizard", stat="int"):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": klass, "level": level, "ranks": {}, "armour": "none"})
    d["abilities"][stat] = 18
    d["spellbook"] = list(spell_ids)
    d["prepared"] = {k: 3 for k in spell_ids}
    return from_dict(d, ref="pc")


def table(pc, seed=5, foe="thug"):
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    s.add(instantiate(foe, scene=s, name="the thug"))
    s.initiative = [("pc", 20), ("c1", 10)]
    s.sides = {"pc": ["pc"], "them": ["c1"]}
    s.round, s.turn = 1, 0
    return s, Engine(s, Dice(seed=seed))


def cast(engine, spell, at="c1", **params):
    return engine.run(engine.validate([{
        "op": "cast", "actor": "pc", "because": "she speaks the word",
        "params": {"spell": spell, "at": at, **params}}]))


# --- no machine reading is left standing ---------------------------------------------------

def test_no_shipped_spell_runs_on_an_unread_regex_reading():
    """The check that would have caught web, and every one of the 231 like it: a spell's
    effects are either read by a person (`effects_read`) or hand-written in code
    (`spells.CURATED`), never a regex's guess (`effects_converted`). Measured 2026-11-22:
    341 FULL spells ran on the regex layer; 0 now."""
    unread = sorted(s.id for s in spells_mod.all_spells().values()
                    if s.effects and s.effects_converted)
    assert unread == [], f"{len(unread)} spells still run on the regex: {unread[:20]}"


def test_every_reading_validates():
    """Part-21's 354 entries through the same schema the editor uses."""
    bad = []
    for s in spells_mod.all_spells().values():
        for i, spec in enumerate(s.effects or ()):
            bad.extend(f"{s.id} {i + 1}: {p}" for p in effectspec.validate(spec, s.id))
    assert bad == []


@pytest.mark.parametrize("spell_id, why", [
    ("web", "entangles in sticky strands; the 2d4 fire is what burning webs do"),
    ("dimension-door", "a teleport; the 1d6 was its arrival mishap"),
    ("meld-into-stone", "the 5d6 is being expelled from the stone"),
    ("blink", "the 1d6 is being shunted out of a solid object"),
    ("snare", "a trap that waits; nothing is struck when it is cast"),
    ("shillelagh", "makes the caster's club a better weapon"),
    ("wall-of-iron", "the crush is a tipped wall, later and optional"),
    ("forbiddance", "hurts only those who enter, by alignment"),
    ("ethereal-jaunt", "the 1d6 is the caster's own, rematerialising in an object"),
    ("glyph-of-warding", "a trap: nothing goes off when it is cast"),
])
def test_the_audits_misreadings_roll_nothing_on_casting(spell_id, why):
    """Audit 2026-11-22: each of these rolled dice at its target at caster level 7 (web
    "2d4 fire, Reflex negates", wall of iron 10d6, forbiddance 6d6)."""
    sp = spells_mod.get(spell_id)
    plan = spells_mod.casting_plan(sp, 7)
    assert plan["dice"] == "", f"{why}: {plan['dice']}"
    assert not sp.scaling, why


def test_web_at_a_thug_deals_no_fire_and_holds_him_or_he_saves():
    """The critic's reproduction, driven through the engine: web at caster level 7 took a
    thug from 13 to 10 hp ("the thug takes 3 fire"). Read, it deals nothing, and a failed
    Reflex save leaves him grappled by the strands."""
    for seed in range(1, 9):
        s, e = table(caster(["web"]), seed=seed)
        before = s.actors["c1"].hp
        out = cast(e, "web").outcomes[0]
        assert s.actors["c1"].hp == before, out.tell
        assert not [x for x in out.effects if x.get("kind") == "damage"]
        held = s.actors["c1"].has_state("state.held.grappled")
        assert held or "makes the Reflex save" in out.tell, out.tell


def test_a_webbed_creature_can_tear_free_with_the_escape_op():
    """Web (CRB): "a creature can escape or burst the web with a successful combat
    maneuver check or Escape Artist check" against the spell's DC. Before the reading laid
    a holder-less grapple, `escape` answered "Nobody is holding" — stuck for 70 rounds."""
    for seed in range(1, 30):
        s, e = table(caster(["web"]), seed=seed)
        cast(e, "web")
        thug = s.actors["c1"]
        if not thug.has_state("state.held.grappled"):
            continue
        hold = Engine._spell_hold(thug)
        assert hold is not None and hold.payload["ends_when"]["escape"]["dc"] > 10
        tries = []
        for _ in range(20):
            res = e.run(e.validate([{"op": "escape", "actor": "c1", "because": "pulls",
                                     "visibility": "hidden"}], origin="author:test"))
            out = res.outcomes[0]
            assert out.status != "refused", out.tell
            tries.append(out.tell)
            if not thug.has_state("state.held.grappled"):
                break
        assert not thug.has_state("state.held.grappled"), tries
        assert "tears free of the" in tries[-1]
        return
    pytest.fail("the thug made every save across 29 seeds")


def test_phantasmal_killer_kills_on_a_failed_fortitude_and_never_rolls_3d6_for_it():
    """Audit: phantasmal killer rolled "3d6, Fort partial (not death)". By the book, a
    failed Will to disbelieve then a failed Fortitude save kills; the 3d6 is what a
    successful Fortitude save still costs."""
    gate = spells_mod.get("phantasmal-killer").effects[0]
    assert gate["target"] == "will"
    inner = gate["on_failure"][0]
    assert inner["type"] == "save_gate" and inner["target"] == "fort"
    assert [b["type"] for b in inner["on_failure"]] == ["slay"]
    assert [b["dice"] for b in inner["on_success"]] == ["3d6"]
    assert spells_mod.casting_plan(spells_mod.get("phantasmal-killer"), 7)["dice"] == ""


# --- the casting plan ---------------------------------------------------------------------

def test_a_gate_keeps_its_condition_when_its_damage_is_taken_for_the_roll():
    """Audit 2026-11-22: `casting_plan.take()` lifted the damage out of a save gate and
    dropped the rest of the failure branch without a word — 13 spells, sirocco and
    thundering drums among them. Thundering drums (Fort partial): 1d8/level sonic max 5d8,
    and prone on a failed save. The prone must reach the riders, under the same save."""
    plan = spells_mod.casting_plan(spells_mod.get("thundering-drums"), 7)
    assert plan["dice"] == "5d8" and plan["save"] == "fort"
    rest = [r for r in plan["riders"] if r.get("type") == "save_gate"]
    assert rest and rest[0]["target"] == "fort"
    assert [b.get("target") for b in rest[0]["on_failure"]] == ["prone"]
    assert not [b for b in rest[0]["on_success"] if b.get("type") == "damage"]


def test_a_read_spell_halves_on_a_save_its_line_calls_partial():
    """Thundering drums prints "Fortitude partial" and halves its damage on a save. The
    printed line was the authority, and a "partial" save dealt 0 (lane B: 29 read spells
    halve under a "partial" or "negates" line). A reading's own branches now say it."""
    assert spells_mod.get("thundering-drums").save_effect == "partial"
    assert spells_mod.casting_plan(spells_mod.get("thundering-drums"), 7)["save_effect"] \
        == "half"
    # Shout: "Fortitude partial, Reflex negates (object)" parses as negates; RAW halves.
    assert spells_mod.casting_plan(spells_mod.get("shout"), 7)["save_effect"] == "half"


def test_shout_halves_through_the_engine_on_a_made_save():
    """End to end: shout's printed "Fortitude partial, Reflex negates (object)" parsed as
    negates, and a made save took 0 of its 5d6. RAW it takes half the rolled total."""
    halved = 0
    for seed in range(1, 25):
        s, e = table(caster(["shout"]), seed=seed)
        out = cast(e, "shout").outcomes[0]
        if "makes the Fortitude save" not in out.tell:
            continue
        hits = [x for x in out.effects if x.get("kind") == "damage"]
        rolled = next(r.total for r in out.rolls if r.die == "5d6")
        assert hits and hits[0]["rolled"] == rolled // 2, out.tell
        halved += 1
    assert halved, "no made save in 24 seeds"


def test_a_spell_that_harms_one_kind_of_creature_leaves_a_thug_alone():
    """Disrupt undead (CRB): positive energy that harms only undead. Read correctly, it
    still rolled 1d6 at a living thug, because the cast asked no one whether he was undead.
    The damage's `when` is asked per target through `sheet._when_holds`."""
    s, e = table(caster(["disrupt-undead"]))
    before = s.actors["c1"].hp
    out = cast(e, "disrupt-undead").outcomes[0]
    assert s.actors["c1"].hp == before
    assert "untouched" in out.tell
    s, e = table(caster(["disrupt-undead"]), foe="zombie")
    before = s.actors["c1"].hp
    cast(e, "disrupt-undead")
    assert s.actors["c1"].hp < before


def test_a_machine_formula_does_not_outlive_the_reading_that_replaced_it():
    """Web kept the regex's `scaling` (2d4 fire) and with it a fire element after its
    effects were read. Thirteen spells read before this kept a stale formula the same way
    (blast of wind, etherealness, phase step ...). The loader drops it now."""
    for sid in ("web", "etherealness", "phase-step", "blast-of-wind"):
        assert not spells_mod.get(sid).scaling, sid
    assert spells_mod.get("web").element == ""
    assert spells_mod.get("fireball").scaling.get("cap_dice") == 10


# --- lane C's chosen element ------------------------------------------------------------------

@pytest.mark.parametrize("cl, points", [(1, 10), (3, 10), (6, 10), (7, 20), (10, 20),
                                        (11, 30), (20, 30)])
def test_resist_energy_is_a_choice_of_five_with_the_books_steps(cl, points):
    """Resist energy (CRB): one of five energies chosen at casting, 10 points, 20 at caster
    level 7, 30 at 11. It was a narrative because `resistance.amount` took only an int and
    no type held a choice; `choose_one` holds the choice (the cast's `choose` param) and the
    amount is a formula now."""
    choice = spells_mod.get("resist-energy").effects[0]
    assert choice["type"] == "choose_one"
    got = {o["target"] for o in choice["options"]}
    assert got == {"acid", "cold", "electricity", "fire", "sonic"}
    for o in choice["options"]:
        assert effectspec.evaluate(o["amount"], {"caster_level": cl}) == points


# --- save-or-condition, finished -----------------------------------------------------------

def _failed(out, save):
    return f"fails the {save} save" in out.tell


def test_a_failed_save_deals_the_ability_damage_its_branch_names():
    """Audit 2026-11-22: 14 spells' failure branch held `ability_damage` (chill touch's
    1 Strength, haunting mists' 1d2 Wisdom) and `_magic_gate` applied only conditions, so
    the score damage was told and never dealt. Chill touch, read: 1d6 negative always, and
    1 Strength damage on a failed Fortitude save."""
    hit = 0
    for seed in range(1, 30):
        s, e = table(caster(["chill-touch"], level=1), seed=seed)
        out = cast(e, "chill-touch").outcomes[0]
        if _failed(out, "Fortitude"):
            assert "takes 1 Strength damage" in out.tell, out.tell
            hit += 1
        elif "makes the Fortitude save" in out.tell:
            assert "takes 1 Strength damage" not in out.tell, out.tell
    assert hit, "no failed save in 29 seeds"


def test_blindness_deafness_blinds_whom_the_caster_chose_on_a_failed_save():
    """Blindness/deafness (CRB): blinded or deafened, chosen at casting, Fortitude negates,
    permanent. It was a narrative because no type held the choice; `choose_one` does, and
    the chosen option's save is the cast's to roll (`_rider_saves`)."""
    for seed in range(1, 30):
        s, e = table(caster(["blindness-deafness"]), seed=seed)
        out = cast(e, "blindness-deafness", choose=1).outcomes[0]
        thug = s.actors["c1"]
        if _failed(out, "Fortitude"):
            assert thug.has_state("state.senses.blinded"), out.tell
            assert not thug.has_state("state.senses.deafened")
            return
        assert not thug.has_state("state.senses.blinded"), out.tell
    pytest.fail("no failed save in 29 seeds")


def test_an_unchosen_blindness_deafness_lays_nothing_and_rolls_no_save():
    s, e = table(caster(["blindness-deafness"]))
    out = cast(e, "blindness-deafness").outcomes[0]
    assert not s.actors["c1"].has_state("state.senses")
    assert "Fortitude save" not in out.tell
    assert "Nothing is applied until one is chosen" in out.tell


def test_command_halt_dazes_for_one_round_on_a_failed_will_save():
    """Command (CRB): "Halt: The subject stands in place for 1 round. It may not take any
    actions but is not considered helpless" — the book's dazed ("can take no actions, but
    has no penalty to AC"). It was a narrative under a Will gate; halt and fall now lay."""
    for seed in range(1, 30):
        s, e = table(caster(["command"], level=3, klass="cleric", stat="wis"), seed=seed)
        out = cast(e, "command", choose=5).outcomes[0]
        thug = s.actors["c1"]
        if _failed(out, "Will"):
            assert thug.has_state("state.unable.dazed"), out.tell
            return
    pytest.fail("no failed save in 29 seeds")
