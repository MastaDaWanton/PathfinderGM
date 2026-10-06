"""The enchanting circle's step rules (docs/enchanting-revamp-plan.md §4, §5, §10; contracts
§6, lane E), on the REAL track, property table, essence shelf and magic layer.

Each test names the defect it prevents. The plan's §21.1 list for lane E is here: an
enchantment started at the circle reaches the item's record (the `/craft/` tab could never
pass its masterwork gate), a missing spell is +5 DC and never a refusal, a miss by 1 to 4
keeps the essences, the check never reads a worn item, and no natural decides it.
"""
from __future__ import annotations

import json

import pytest

from rules import enchanter as en
from rules import forge_items, inprogress, magic_layer, worldclass as wc
from rules.activeeffect import ActiveEffect
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

NOON = 12 * 60          # day 1, inside noon: fire's phase
NIGHT = 22 * 60         # day 1, night


def forged(rid="iron-longsword", head="iron", base="longsword", q=3, gear="weapon"):
    pieces = ({"head": {"material": head, "passes": 1},
               "haft": {"material": "ash-haft", "passes": 0},
               "fittings": {"material": "brass-guard", "passes": 0}} if gear == "weapon"
              else {"body": {"material": head, "passes": 0},
                    "fastenings": {"material": "iron", "passes": 0},
                    "lining": {"material": "padded-lining", "passes": 0}})
    return {"id": rid, "name": f"{wc.quality_name(q)} {rid.replace('-', ' ').title()}",
            "kind": "crafted", "craft": "blacksmith", "count": 1, "gear": gear, "base": base,
            "slot": "hands" if gear == "weapon" else "armor", "quality_index": q,
            "masterwork": q >= 3, "pieces": pieces, "quench": None, "finish": [],
            "flaws": [], "smith": {"level": 3, "perks": {}}, "schema": 3}


@pytest.fixture
def world():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    pc = s.pc()
    pc.inventory.clear()
    pc.stock.clear()
    pc.herb_known.clear()
    prog = pc.track("enchanter")
    prog.level, prog.mp = 4, 0
    return pc, s, Engine(s, Dice(seed=7)), prog


def carry(pc, **counts):
    for k, n in counts.items():
        pc.carry(k.replace("_", "-"), n)


def give(pc, rec):
    pc.add_stock(forge_items.stock_item(rec), 1)
    return f"stock:{rec['id']}"


def step(pc, prog, s, method, body, now, tier=3, engine=None, flawed=False):
    plan = en.plan_step(pc, prog, method, body, scene=s, now=now)
    assert not plan.problems, plan.problems
    return plan, en.finish(pc, prog, plan, tier, engine=engine, now=now, flawed=flawed)


def prepared_and_attuned(pc, prog, s, seats, now=NOON, chalk="consecrated-chalk",
                         rec=None, choices=None):
    carry(pc, **{chalk.replace("-", "_"): 1, "silver_ink": 1})
    key = give(pc, rec or forged())
    step(pc, prog, s, "prepare", {"vessel": key, "circle": [f"inv:{chalk}", "inv:silver-ink"]},
         now)
    step(pc, prog, s, "attune", {"vessel": key, "seats": seats, "choices": choices or {}},
         now)
    return key


# --- the path, end to end ---------------------------------------------------------------------

def test_a_flaming_binding_reaches_the_forged_record_and_keeps_its_build(world):
    """Measured on master e028885 (plan §1): the old bench wrote a NEW record that dropped
    the forged build, and from /craft/ every essence binding was refused "not masterwork".
    Prepare, attune and bind a +1 flaming longsword; the work waits In progress for the
    book's 8 days (8,000 gp: 64 hours at 8 a day); collected, the SAME record carries the
    layer and keeps its pieces, and its build now has the +1 and the fire."""
    pc, s, e, prog = world
    carry(pc, arcane_essence_i=1, flaming_essence=1)
    key = prepared_and_attuned(pc, prog, s, {"point": "inv:flaming-essence",
                                             "edge": "inv:arcane-essence-i"})
    plan, got = step(pc, prog, s, "bind", {"vessel": key}, NOON, engine=e)
    assert plan.days == 8 and plan.work_minutes == 8 * 1440
    assert "flaming-essence" not in pc.inventory and "arcane-essence-i" not in pc.inventory
    rows = inprogress.entries(pc, NOON)
    assert [r["craft"] for r in rows] == ["enchanter"] and rows[0]["ready_words"] == \
        "ready in 8 days"
    st = pc.stock[key[6:]]
    assert inprogress.held_back(st, NOON).startswith("still binding")
    assert inprogress.collect(pc, key, now=NOON + 60, here=None)["ok"] is False
    got = inprogress.collect(pc, key, now=NOON + 8 * 1440, here=None)
    assert got["ok"], got
    rec = forge_items.record_of(pc.stock[key[6:]])
    assert rec["pieces"]["head"]["material"] == "iron"
    assert rec["name"] == "+1 Flaming Superior Iron Longsword"
    assert rec["magic"]["enhancement"] == 1
    assert "circle" not in rec["magic"]
    build = forge_items.build(rec)
    assert any(sp.get("target") == "attack" and sp.get("amount") == 1
               and sp.get("bonus_type") == "enhancement"
               for sp in forge_items.roll_specs(build))
    assert any(r.get("damage_type") == "fire" and r.get("trigger") == "hit"
               for r in build["magic"]["riders"])


def test_the_check_is_the_books_dc_through_the_layer_plan(world):
    """Before the revamp the circle's DC was a house 10 + 5 × rank and the book mode's
    5 + CL: two rules for one craft. Now Bind's DC is `magic_layer.plan`'s, every term
    named: 5 + caster level 10, +5 for flame blade neither known nor carried, +5 for an
    Enchanter 4 below caster level 10, and a catalyst's -2."""
    pc, s, e, prog = world
    carry(pc, arcane_essence_i=1, flaming_essence=1, powdered_pearl=1)
    key = prepared_and_attuned(pc, prog, s, {"point": "inv:flaming-essence",
                                             "edge": "inv:arcane-essence-i"})
    plan = en.plan_step(pc, prog, "bind", {"vessel": key, "catalyst": "inv:powdered-pearl"},
                        scene=s, now=NOON)
    assert not plan.problems
    assert [t["dc"] for t in plan.dc_terms] == [15, 5, 5, -2]
    assert plan.dc == 23
    assert plan.bonus == sum(t["value"] for t in en.check_terms(pc, 4))


def test_a_missing_spell_is_five_dc_and_a_carried_potion_is_spent_instead(world):
    """The owner (round 1): each missing prerequisite is +5 DC, never a refusal. The old
    book mode REFUSED a working whose spell was unknown. A carried potion of flame blade
    satisfies it (the book's "through another magic item") and is spent at the Bind."""
    from rules.crafting import Stock

    pc, s, e, prog = world
    carry(pc, arcane_essence_i=1, flaming_essence=1)
    key = prepared_and_attuned(pc, prog, s, {"point": "inv:flaming-essence",
                                             "edge": "inv:arcane-essence-i"})
    without = en.plan_step(pc, prog, "bind", {"vessel": key}, scene=s, now=NOON)
    assert not without.problems and any("Flame Blade" in t["why"] for t in without.dc_terms)
    pc.stock["potion-flame-blade"] = Stock(base="Potion of Flame Blade", count=1,
                                          craft="alchemist", holds_spell="flame-blade")
    withp = en.plan_step(pc, prog, "bind", {"vessel": key}, scene=s, now=NOON)
    assert withp.dc == without.dc - 5
    assert withp.potions == ["potion-flame-blade"]
    en.finish(pc, prog, withp, 3, engine=e, now=NOON)
    assert "potion-flame-blade" not in pc.stock


def test_a_miss_by_one_to_four_keeps_the_essences_and_the_attunement(world):
    """Plan §10.1 (the cross-craft rule): a Bind missed by 1 to 4 does not take; time lost,
    essences kept, the vessel stays attuned. The book wastes the materials; the owner's
    crafts never take materials for a small miss."""
    pc, s, e, prog = world
    carry(pc, arcane_essence_i=1, flaming_essence=1)
    key = prepared_and_attuned(pc, prog, s, {"point": "inv:flaming-essence",
                                             "edge": "inv:arcane-essence-i"})
    plan = en.plan_step(pc, prog, "bind", {"vessel": key}, scene=s, now=NOON)
    assert en.verdict_of(plan, -4) == "failure"
    got = en.miss(pc, prog, plan, -4, now=NOON)
    assert got["lost"] == [] and "essences are kept" in got["said"]
    assert pc.inventory["flaming-essence"] == 1
    assert en.find_vessel(pc, key, NOON).state == "attuned"


def test_a_miss_by_five_takes_flawed_and_the_curse_never_reaches_the_page(world):
    """Owner round 1 and round 4 point 2: a Bind missed by 5 or more works, flawed, with a
    hidden curse; the margin is shown, which curse is not. The curse record (lane F's, a
    stub here) rides in the In-progress result and on the layer, and no row or card the
    page is sent carries it."""
    pc, s, e, prog = world
    carry(pc, arcane_essence_i=1, flaming_essence=1)
    key = prepared_and_attuned(pc, prog, s, {"point": "inv:flaming-essence",
                                             "edge": "inv:arcane-essence-i"})
    plan = en.plan_step(pc, prog, "bind", {"vessel": key}, scene=s, now=NOON)
    assert en.verdict_of(plan, -5) == "flawed"
    en.finish(pc, prog, plan, 2, engine=e, now=NOON, flawed=True)
    rows = json.dumps(inprogress.entries(pc, NOON))
    assert "d100" not in rows and "curse" not in rows
    assert inprogress.collect(pc, key, now=NOON + 9 * 1440, here=None)["ok"]
    rec = forge_items.record_of(pc.stock[key[6:]])
    assert rec["magic"]["curse"] and rec["magic"]["known"]["curse"] is False
    card = json.dumps(en.item_card(rec))
    assert "d100" not in card and "pending" not in card
    assert json.dumps(en.shelf(pc, NOON + 9 * 1440)).count("d100") == 0


def test_the_attunement_lapses_after_a_day_and_nothing_is_written(world):
    """Owner round 4 point 9: an attuned vessel holds a day, then the essences drift back
    to the shelf unharmed. They were never taken off it, only held back, so the lapse is
    the clock passing and not a write anybody could forget."""
    pc, s, e, prog = world
    carry(pc, arcane_essence_i=1, flaming_essence=1)
    key = prepared_and_attuned(pc, prog, s, {"point": "inv:flaming-essence",
                                             "edge": "inv:arcane-essence-i"})
    assert en.reserved(pc, NOON) == {"inv:flaming-essence": 1, "inv:arcane-essence-i": 1}
    assert not [p for p in en.phials(pc, en.reserved(pc, NOON)) if p.id == "flaming-essence"]
    later = NOON + 1440
    assert en.reserved(pc, later) == {}
    assert [p.id for p in en.phials(pc, en.reserved(pc, later))].count("flaming-essence") == 1
    assert en.find_vessel(pc, key, later).state == "prepared"


def test_no_limit_on_bindings_in_progress(world):
    """Owner round 4 point 5: no limit to how many things are in progress at once. The plan
    had taken the book's 'one item at a time'."""
    pc, s, e, prog = world
    carry(pc, arcane_essence_i=2, consecrated_chalk=2, silver_ink=2)
    keys = []
    for rid in ("blade-one", "blade-two"):
        key = give(pc, forged(rid=rid))
        step(pc, prog, s, "prepare", {"vessel": key, "circle": ["inv:consecrated-chalk",
                                                                "inv:silver-ink"]}, NOON)
        keys.append(key)
    for key in keys:
        step(pc, prog, s, "attune", {"vessel": key, "seats": {"point": "inv:arcane-essence-i"}},
             NOON)
        step(pc, prog, s, "bind", {"vessel": key}, NOON, engine=e)
    assert len(inprogress.entries(pc, NOON, craft="enchanter")) == 2


# --- the circle's refusals and helps ---------------------------------------------------------

def test_a_white_chalk_circle_holds_nothing_rarer_than_uncommon(world):
    """Plan §7.3: a circle's chalk sets the rarest essence it holds (white chalk: common and
    uncommon). Without the rule every chalk was the same chalk."""
    pc, s, e, prog = world
    carry(pc, white_chalk=1, silver_ink=1, flaming_essence=1, arcane_essence_i=1)
    key = give(pc, forged())
    step(pc, prog, s, "prepare", {"vessel": key, "circle": ["inv:white-chalk",
                                                            "inv:silver-ink"]}, NOON)
    plan = en.plan_step(pc, prog, "attune", {"vessel": key, "seats": {
        "point": "inv:flaming-essence", "edge": "inv:arcane-essence-i"}}, scene=s, now=NOON)
    assert any("holds nothing rarer than uncommon" in p for p in plan.problems)


def test_an_arcane_essence_will_not_sit_on_armour(world):
    """Polarity is a seat rule now, not +5 DC (plan §7.2): an arcane essence is a weapon's
    +N priced at the weapon's rate; on armour it would be the wrong price."""
    pc, s, e, prog = world
    carry(pc, consecrated_chalk=1, silver_ink=1, arcane_essence_i=1)
    key = give(pc, forged(rid="iron-breastplate", base="breastplate", gear="armour"))
    step(pc, prog, s, "prepare", {"vessel": key, "circle": ["inv:consecrated-chalk",
                                                            "inv:silver-ink"]}, NOON)
    plan = en.plan_step(pc, prog, "attune", {"vessel": key, "seats": {
        "breast": "inv:arcane-essence-i"}}, scene=s, now=NOON)
    assert any("wants a weapon" in p for p in plan.problems)


def test_affinity_takes_one_a_seat_and_never_more_than_two(world):
    """Owner round 4 point 9: an essence seated on a material its family suits is -1 DC,
    at most -2. Fire suits copper; a copper-headed blade has two seats on its head."""
    pc, s, e, prog = world
    carry(pc, arcane_essence_i=1, flaming_essence=1, red_dragon_ichor=1)
    prog.level = 6
    key = prepared_and_attuned(pc, prog, s, {"point": "inv:flaming-essence",
                                             "edge": "inv:red-dragon-ichor",
                                             "guard": "inv:arcane-essence-i"},
                               rec=forged(head="copper"), chalk="bone-chalk")
    plan = en.plan_step(pc, prog, "bind", {"vessel": key}, scene=s, now=NOON)
    aff = [t for t in plan.dc_terms if t["why"].startswith("affinity")]
    assert aff and aff[0]["dc"] == -2


def test_ghost_residue_binds_only_between_dusk_and_dawn_unless_varnished(world):
    """Plan §7.3: `night_only` (ghost residue) binds only between dusk and dawn, unless the
    vessel was prepared with a treatment that lifts it (moonlit varnish)."""
    pc, s, e, prog = world
    carry(pc, arcane_essence_i=1, ghost_residue=1)
    prog.level = 6
    key = prepared_and_attuned(pc, prog, s, {"point": "inv:ghost-residue",
                                             "edge": "inv:arcane-essence-i"})
    noon = en.plan_step(pc, prog, "bind", {"vessel": key}, scene=s, now=NOON)
    assert any("between dusk and dawn" in p for p in noon.problems)
    night = en.plan_step(pc, prog, "bind", {"vessel": key}, scene=s, now=NIGHT)
    assert not any("between dusk and dawn" in p for p in night.problems)


def test_two_new_properties_in_one_working_wait_for_enchanter_2(world):
    """Plan §5.1: more than one new property in one working opens at Enchanter 2. Below it
    the circle says so instead of rolling."""
    pc, s, e, prog = world
    prog.level = 1
    carry(pc, consecrated_chalk=1, silver_ink=1, flaming_essence=1, keen_essence=1)
    key = give(pc, forged())
    step(pc, prog, s, "prepare", {"vessel": key, "circle": ["inv:consecrated-chalk",
                                                            "inv:silver-ink"]}, NOON)
    plan = en.plan_step(pc, prog, "attune", {"vessel": key, "seats": {
        "point": "inv:flaming-essence", "edge": "inv:keen-essence"}}, scene=s, now=NOON)
    assert any("Enchanter 2" in p for p in plan.problems)


def test_the_essence_tier_gates_the_binder_and_the_property_tier_does_not(world):
    """Lane D left this to lane E (docs/enchanting-review.md row 2). Speed is "legendary" in
    the property table and its essence is exotic by its price band. Gating on the property
    would make an Enchanter 2 wait for level 3 to bind a 15,000 gp phial; the essence's band
    (the material the binder handles) is the gate."""
    pc, s, e, prog = world
    prog.level = 2
    carry(pc, speed_essence=1, vorpal_essence=1)
    fits = en.fits_for(en.plan_step(pc, prog, "refine", {}, scene=s, now=NOON), pc, NOON)
    assert fits["inv:speed-essence"]["ok"]
    assert not fits["inv:vorpal-essence"]["ok"]
    assert "Enchanter 3" in fits["inv:vorpal-essence"]["why"]


def test_capacity_never_less_than_one_and_half_the_level_after(world):
    """Owner rounds 4 and 7: a Superior blade holds floor(level / 2), never less than +1.
    An Enchanter 1 could bind nothing onto a Superior sword before round 7."""
    pc, s, e, prog = world
    give(pc, forged())
    for level, holds in ((1, 1), (2, 1), (4, 2), (9, 4)):
        prog.level = level
        item = en.vessels(pc, NOON)[0].as_item(pc, NOON)
        assert item["holds"]["bonus"] == holds, level


def test_hurry_halves_the_days_for_five_dc(world):
    """The book: 4 hours a 1,000 gp at +5 DC. 64 hours become 32: 4 days, not 8."""
    pc, s, e, prog = world
    carry(pc, arcane_essence_i=1, flaming_essence=1)
    key = prepared_and_attuned(pc, prog, s, {"point": "inv:flaming-essence",
                                             "edge": "inv:arcane-essence-i"})
    slow = en.plan_step(pc, prog, "bind", {"vessel": key}, scene=s, now=NOON)
    fast = en.plan_step(pc, prog, "bind", {"vessel": key, "hurry": True}, scene=s, now=NOON)
    assert (slow.days, fast.days) == (8, 4) and fast.dc == slow.dc + 5


def test_binding_quality_is_held_under_the_circle_it_was_laid_in(world):
    """Plan §10.2: a careless circle limits the work. Prepared and attuned at Sound, Bind
    reaches Fine at most even for an Enchanter whose hands reach Superior."""
    pc, s, e, prog = world
    carry(pc, consecrated_chalk=1, silver_ink=1, arcane_essence_i=1)
    key = give(pc, forged())
    step(pc, prog, s, "prepare", {"vessel": key, "circle": ["inv:consecrated-chalk",
                                                            "inv:silver-ink"]}, NOON, tier=1)
    step(pc, prog, s, "attune", {"vessel": key, "seats": {"point": "inv:arcane-essence-i"}},
         NOON, tier=1)
    plan = en.plan_step(pc, prog, "bind", {"vessel": key}, scene=s, now=NOON)
    assert plan.ceiling == 2


# --- the check never feeds itself; no naturals ------------------------------------------------

def test_the_check_never_reads_a_worn_item(world):
    """Skyrim's Fortify loop (prior art §5.6; plan §4.5): gear an enchanter makes must never
    raise the next enchanting check. A +2 Intelligence item raises the sheet's Intelligence
    and leaves the check's Intelligence term where it was."""
    pc, s, e, prog = world
    before_mod = pc.ability_mod("int")
    before = en.check_terms(pc, 4)
    pc.apply_effect(ActiveEffect(name="Headband of Vast Intelligence +4", kind="buff",
                                 source="item:headband", modifiers=[
                                     {"kind": "ability_mod", "target": "int", "amount": 4,
                                      "bonus_type": "enhancement"}]))
    assert pc.ability_mod("int") == before_mod + 2
    assert en.check_terms(pc, 4) == before


def test_no_natural_decides_the_check(world):
    """CRB p.180: skill checks take no natural 1 or 20. The old /craft/ bench applied both
    to the enchanting check (craft_views._one_craft)."""
    pc, s, e, prog = world
    plan = en.StepPlan(method="bind", level=4, flawed_ok=True)
    assert en.verdict_of(plan, 0) == "success"     # a 1 that makes the DC still makes it
    assert en.verdict_of(plan, -1) == "failure"    # a 20 that misses still misses


# --- refine, unbind, cleanse, identify ------------------------------------------------------

def _sanctum(monkeypatch):
    monkeypatch.setattr(en, "sanctum_here", lambda scene, actor, known=():
                        {"kind": "owned", "place": "x", "name": "Sanctum"})


def test_refine_condenses_one_family_by_how_cleanly_it_was_drawn(world, monkeypatch):
    """Plan §10 (Cennini's paler draws): two or more phials of one family become one, the
    motes kept by the draw's quality (Crude 0.8 ... Flawless 1.0). Two families never
    share a phial."""
    pc, s, e, prog = world
    _sanctum(monkeypatch)
    carry(pc, fire_mote=3, frost_mote=1)
    mixed = en.plan_step(pc, prog, "refine", {"phials": {"inv:fire-mote": 1,
                                                         "inv:frost-mote": 1}},
                         scene=s, now=NOON)
    assert any("One family at a time" in p for p in mixed.problems)
    plan, got = step(pc, prog, s, "refine", {"phials": {"inv:fire-mote": 3}}, NOON, tier=0)
    assert "fire-mote" not in pc.inventory
    refined = [p for p in en.phials(pc) if p.stocked]
    assert len(refined) == 1 and refined[0].motes == 4      # 6 motes x 0.8, rounded down
    assert refined[0].family == "fire"


def test_unbind_keeps_the_smiths_item_and_gives_back_a_quarter(world):
    """Owner round 4 point 6: the item stays, a quarter of the motes come back; Unbind
    teaches the property TYPES, never their size (Skyrim, plan §12.3)."""
    pc, s, e, prog = world
    rec = magic_layer.write(forged(), {"enhancement": 1, "properties": [{"id": "flaming"}]},
                            binding={"quality_index": 3, "level": 4, "perks": {},
                                     "vessel_name": "Superior Iron Longsword"}, day=1)
    key = give(pc, rec)
    plan, got = step(pc, prog, s, "unbind", {"vessel": key}, NOON)
    left = forge_items.record_of(pc.stock[key[6:]])
    assert not magic_layer.has_layer(left) and left["pieces"]["head"]["material"] == "iron"
    assert left["name"] == "Superior Iron Longsword"
    # 8,000 gp: 40 motes to make, a quarter back as arcane residue at one mote a phial.
    assert pc.inventory.get("arcane-residue") == 10
    residue = [p for p in en.phials(pc) if p.id == "arcane-residue"]
    assert residue and residue[0].motes == 1 and residue[0].count == 10
    assert {"property": "flaming"} in got["discoveries"]


def test_legendary_magic_waits_for_enchanter_3_to_unbind(world):
    """Plan §13: an item whose magic is legendary needs Enchanter 3 to unbind (the rarity
    lock every method keeps). A +5 vorpal sword is 200,000 gp of magic: legendary."""
    pc, s, e, prog = world
    rec = magic_layer.write(forged(), {"enhancement": 5, "properties": [{"id": "vorpal"}]},
                            binding={"quality_index": 4, "level": 20, "perks": {}}, day=1)
    key = give(pc, rec)
    prog.level = 2
    plan = en.plan_step(pc, prog, "unbind", {"vessel": key}, scene=s, now=NOON)
    assert any("Enchanter 3" in p for p in plan.problems)
    prog.level = 3
    plan = en.plan_step(pc, prog, "unbind", {"vessel": key}, scene=s, now=NOON)
    assert not any("Enchanter 3" in p for p in plan.problems)


def test_cleanse_lifts_a_known_curse_and_keeps_the_rest(world, monkeypatch):
    """Plan §10: Cleanse (Enchanter 3, a sanctum) lifts a curse whose existence is known and
    keeps the layer; an unknown curse cannot be cleansed."""
    pc, s, e, prog = world
    _sanctum(monkeypatch)
    rec = magic_layer.write(forged(), {"enhancement": 1},
                            binding={"quality_index": 3, "level": 4, "perks": {}},
                            curse={"d100": 30, "cl": 3}, day=1)
    key = give(pc, rec)
    hidden = en.plan_step(pc, prog, "cleanse", {"vessel": key}, scene=s, now=NOON)
    assert any("know of no curse" in p for p in hidden.problems)
    m = pc.stock[key[6:]].record["magic"]
    m["known"]["curse"] = True
    plan, got = step(pc, prog, s, "cleanse", {"vessel": key}, NOON)
    after = pc.stock[key[6:]].record["magic"]
    assert after["curse"] is None and after["enhancement"] == 1


def test_identify_shows_the_intent_by_nine_and_the_curse_by_ten_once_a_day(world):
    """Plan §12.1 (lane F's API, stubbed here until it lands): beat DC 15 + CL to learn the
    intent, by 10 to see the curse; a second try the same day returns the same answer."""
    pc, s, e, prog = world
    rec = magic_layer.write(forged(), {"enhancement": 1},
                            binding={"quality_index": 3, "level": 4, "perks": {}},
                            curse={"d100": 30, "cl": 3}, day=1)
    import copy

    dc = 15 + 3
    a = copy.deepcopy(rec)            # two items: what is learned is on each item's own
    got = en.identify_item(pc, a, dc + 9, day=2)
    assert got["result"] == "intent" and not a["magic"]["known"]["curse"]
    again = en.identify_item(pc, a, dc + 20, day=2)
    assert again["result"] == "intent" and again.get("repeat")
    b = copy.deepcopy(rec)
    assert en.identify_item(pc, b, dc + 10, day=2)["result"] == "curse"
    assert b["magic"]["known"]["curse"] is True


# --- mastery -----------------------------------------------------------------------------------

def test_every_successful_step_pays_and_failing_stops_teaching(world):
    """Owner 2026-10-05: "batch of 10 should pay 10": every success pays, no repeat cap; a
    failure teaches `MISHAP_LIMIT` times per method and material and then nothing."""
    pc, s, e, prog = world
    plan = en.StepPlan(method="attune", level=4, lead={"id": "arcane-essence-i",
                                                       "name": "Arcane Essence I"}, rank=2)
    paid = [en.miss(pc, prog, plan, -2, now=NOON)["mastery"]["mp"] for _ in range(4)]
    assert paid == [1, 1, 0, 0]
    t = wc.get("enchanter")
    got = [wc.award_step(t, prog, method="bind", ingredient_id="x", rarity_rank=1,
                         quality_index=0)["mp"] for _ in range(6)]
    assert got == [1] * 6
