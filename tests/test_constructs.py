"""Constructs made at the enchanting circle: the Animate method (rules/constructs.py).

The owner, 2026-11-22: "Remove item creation feats they are unnecessary, instead build the
magic items like wands and scrolls and constructs into the enchanting world class." Before
this the only way to have a construct was the mend-and-claim house rule: the 20-odd golems
sat in the bestiary with no construction line, and nothing made one. Each test names what
it prevents.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gm import companions
from rules import bestiary, constructs, enchanter as en, encounter_budget, inprogress
from rules import repair, spells, states
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

NOON = 12 * 60


@pytest.fixture
def table():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    pc = s.pc()
    pc.inventory.clear()
    pc.stock.clear()
    prog = pc.track("enchanter")
    prog.level, prog.mp = 1, 0
    return pc, s, Engine(s, Dice(seed=7)), prog


def _homunculus_kit(pc, motes=10):
    pc.carry("mandrake", 1)
    pc.carry("fire-mote", motes // 2)


def _animate(pc, prog, s, construct="homunculus", tier=2, now=NOON):
    plan = en.plan_step(pc, prog, "animate", {"construct": construct}, scene=s, now=now)
    assert not plan.problems, plan.problems
    return plan, en.finish(pc, prog, plan, tier, now=now)


# --- the data ------------------------------------------------------------------------------

def test_every_construction_line_names_a_real_stat_block_and_real_spells():
    """A line keyed by a template the bestiary does not hold makes nothing at Collect, and
    a spell id that does not resolve is a +5 DC nobody can ever clear by learning it."""
    for template, r in constructs.rows().items():
        assert bestiary.raw_block(template), template
        assert bestiary.raw_block(template).get("creature_type") == "construct", template
        for group in r["spells"]:
            for sid in group:
                spells.get(sid)          # raises on an unknown id
        assert r["price_gp"] > r.get("body_gp", 0), template
        body = r["body"]
        assert body.get("ingredients") or body.get("forged") or body.get("coin_gp"), template


def test_the_book_costs_come_out_of_the_lines():
    """The Bestiary prints price and cost: cost = (price - body) / 2 + body. Flesh golem
    20,500 / 10,500; homunculus 2,050 / 1,050. The motes are the magic half."""
    flesh = constructs.row("golem-flesh")
    assert constructs.motes_for(flesh) * 100 + flesh["body_gp"] == 10_500
    assert constructs.motes_for(constructs.row("homunculus")) == 10
    # 1 day per 1,000 gp: 2,050 gp is 3 working days of 8 hours.
    assert constructs.days_for(constructs.row("homunculus")) == 3


def test_the_gate_is_the_stat_blocks_cr():
    """Homunculus and the smallest early, golems late (owner call: CR rounded up)."""
    assert constructs.level_for("homunculus") == 1
    assert constructs.level_for("animated-object") == 3
    assert constructs.level_for("golem-flesh") == 7
    assert constructs.level_for("golem-iron") == 13


# --- the step ------------------------------------------------------------------------------

def test_animate_is_refused_above_your_level_with_the_level_named(table):
    pc, s, _e, prog = table
    plan = en.plan_step(pc, prog, "animate", {"construct": "golem-flesh"}, scene=s, now=NOON)
    assert any("Enchanter 7" in p for p in plan.problems), plan.problems


def test_the_dc_is_the_line_plus_the_owners_enchanting_rule(table):
    """Printed DC 12, +5 for each of three spells unknown, +5 for Enchanter 1 below CL 7:
    32, never a refusal (the owner's rule for Bind, kept for Animate)."""
    pc, s, _e, prog = table
    _homunculus_kit(pc)
    plan = en.plan_step(pc, prog, "animate", {"construct": "homunculus"}, scene=s, now=NOON)
    assert plan.dc == 12 + 15 + 5, plan.dc_terms
    assert sum(t["dc"] for t in plan.dc_terms) == plan.dc
    assert not plan.problems


def test_a_body_and_motes_are_required(table):
    pc, s, _e, prog = table
    plan = en.plan_step(pc, prog, "animate", {"construct": "homunculus"}, scene=s, now=NOON)
    words = " ".join(plan.problems)
    assert "Mandrake" in words and "motes" in words


def test_plain_motes_are_spent_before_a_granting_essence(table):
    """A homunculus' 10 motes came off an arcane essence (+1 enhancement, 10 motes) while
    five plain fire motes sat on the shelf: the plan must spend the plain ones."""
    pc, s, _e, prog = table
    _homunculus_kit(pc)
    pc.carry("arcane-essence-i", 1)
    plan = en.plan_step(pc, prog, "animate", {"construct": "homunculus"}, scene=s, now=NOON)
    spent = {k for k, _n, _name in plan.consumes}
    assert "inv:fire-mote" in spent and "inv:arcane-essence-i" not in spent


def test_animate_spends_the_body_and_goes_in_progress_then_rises_yours(table):
    """The whole path on the real circle and the real In progress section."""
    pc, s, engine, prog = table
    _homunculus_kit(pc)
    plan, got = _animate(pc, prog, s, tier=3)
    assert "mandrake" not in pc.inventory and "fire-mote" not in pc.inventory
    work = got["products"][0]["work"]
    key = work["key"]
    assert inprogress.state_of(pc.stock[key], NOON) == "working"
    ready = NOON + 3 * 1440
    got = inprogress.collect(pc, key, now=ready, here=None)
    assert got["ok"], got
    assert key not in pc.stock
    made, tell = constructs.arrive(engine, pc, got["product"]["construct"])
    assert made.ref in s.actors and made.from_template == "homunculus"
    assert made.has_state(states.OWNED_BY_YOU) and made.has_state(states.TRAVELS_WITH_YOU)
    assert states.attitude_of(made) == "devoted"
    # Superior is two steps above Sound: +2 a Hit Die on the printed 11 (2 HD).
    assert made.hp_max == 11 + 4 and made.hp == made.hp_max
    assert "rises" in tell or "is" in tell
    # Removing the bond's effect takes its hit points with it (law 2).
    made.remove_effects(source=f"made:{made.ref}")
    assert made.hp_max == 11


def test_a_stopped_animating_gives_the_satchel_body_back(table):
    pc, s, _e, prog = table
    _homunculus_kit(pc)
    _plan, got = _animate(pc, prog, s)
    key = got["products"][0]["work"]["key"]
    out = inprogress.cancel(pc, key, now=NOON + 60)
    assert out["ok"] and pc.inventory.get("mandrake") == 1
    assert key not in pc.stock


def test_a_forged_suit_of_armour_is_an_animated_objects_body(table):
    from tests.test_enchant_bench import forged, give

    pc, s, engine, prog = table
    prog.level = 3
    key = give(pc, forged("iron-breastplate", base="breastplate", gear="armour"))
    pc.carry("fire-mote", 12)
    plan = en.plan_step(pc, prog, "animate", {"construct": "animated-object"}, scene=s,
                        now=NOON)
    assert not plan.problems, plan.problems
    assert plan.choices["body"] == key.split(":", 1)[1]
    got = en.finish(pc, prog, plan, 1, now=NOON)
    wk = got["products"][0]["work"]["key"]
    done = inprogress.collect(pc, wk, now=NOON + 10 * 1440, here=None)
    made, _tell = constructs.arrive(engine, pc, done["product"]["construct"])
    assert made.from_template == "animated-object" and wk not in pc.stock


# --- what it is once it is here ------------------------------------------------------------

def _made(table, template="homunculus"):
    pc, s, engine, _prog = table
    made, _ = constructs.arrive(engine, pc, {"template": template, "quality_index": 1})
    return pc, s, engine, made


def test_a_made_construct_is_told_mindless_and_mute(table):
    """The book's golem 'does nothing without orders' and has no voice; the homunculus
    'cannot speak'. Before, an owned construct's facts read like a devoted person's."""
    pc, s, _e, made = _made(table, "animated-object")
    words = companions.who_they_are(s, made)
    assert "cannot speak" in words and "no mind of its own" in words
    assert constructs.mindless(made) and constructs.mute(made)
    hom = constructs.arrive(_e, pc, {"template": "homunculus"})[0]
    assert constructs.mute(hom) and not constructs.mindless(hom)
    facts = companions.turn_facts(s, made, [])
    assert "strikes back only at whoever has attacked it" in facts


def test_a_made_construct_counts_in_the_encounter_budget_like_a_claimed_one(table):
    """Counted at its CR, as `companion_level` counts a claimed construct (owner call)."""
    pc, s, _e, made = _made(table, "animated-object")
    assert encounter_budget.companion_with(made)
    assert encounter_budget.companion_level(made) == 3


def test_a_construct_does_not_sleep_its_damage_off(table):
    """Measured 2026-11-22: a homunculus at 3 of 11 rose to 4 after a night's rest, and a
    broken one at -5 rose to 1 — `rest` healed every actor (Bestiary, Construct type:
    'cannot heal damage on its own')."""
    pc, s, _e, made = _made(table)
    made.hp = 3
    made.rest("night")
    assert made.hp == 3
    pc.hp = 1
    pc.rest("night")
    assert pc.hp > 1


def test_the_repair_dc_reads_the_construction_line(table):
    """The house-rule repair stood in DC 20 for every construct; a homunculus' line is
    DC 12, so its repair is DC 7 (the book's 5 less)."""
    pc, s, _e, made = _made(table)
    assert repair.crafting_dc(made, repair.row()) == (12, False)
    assert repair.repair_dc(made) == 7


def test_the_maker_mends_a_made_construct_through_the_existing_repair(table):
    """Mend-and-claim still works beside Animate: the typed repair heals a made one."""
    pc, s, engine, made = _made(table)
    made.hp = 2
    raw = {"op": "repair", "actor": "pc", "target": made.ref, "visibility": "hidden",
           "because": "test", "params": {}}
    res = engine.run(engine.validate([raw]))
    while res.awaiting:
        res = engine.resume(20)
    assert made.hp > 2


def test_make_whole_repairs_a_construct_by_caster_level():
    """Measured 2026-11-22: make whole at caster level 5 rolled 1d6 on a homunculus — its
    heal effect carried no `scales`, so the 1d6-per-level the text prints never reached the
    die. CRB: 1d6 per caster level, at most 5d6."""
    from tests.test_casting_executes import wizard

    w = wizard(level=5, book=("make-whole",), prepared={"make-whole": 1})
    s = Scene(location_id="5bbd0c40345f")
    s.add(w)
    e = Engine(s, Dice(seed=3))
    made, _ = constructs.arrive(e, w, {"template": "homunculus"})
    made.hp = 1
    res = e.run(e.validate([{"op": "cast", "actor": "pc", "because": "test",
                             "params": {"spell": "make-whole", "at": made.ref}}]))
    cast = [o for o in res.outcomes if o.op == "cast"][0]
    assert cast.effects[0]["dice"] == "5d6"
    assert made.hp > 1
