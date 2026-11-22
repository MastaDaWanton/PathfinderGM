"""Spell items: the item creation feats out of the game, scrolls and wands at the circle.

Owner ruling 2026-11-22: "Remove item creation feats they are unnecessary, instead build the
magic items like wands and scrolls and constructs into the enchanting world class."
The design record is docs/item-creation-feats-study.md (options A for scrolls and wands).

What was measured before this lane, on integrate/0.5.1-impl 0eee57ff:
- all nine item creation feats were takeable and did nothing (the audit's "item-creation"
  NARRATED reason); every wizard was handed Scribe Scroll at 1st level, and so was every
  Rune cleric;
- there was no scroll, no wand and no maker of either; Use Magic Device's honesty line
  read "There are no wands or scrolls to find or buy yet ... so nothing calls for it";
- three readers waited for a scroll that could not exist: the alchemy formula route
  "copied from a scroll", the enchanter's carried-scroll-stands-in rule, and the wizard
  text "copied into the book from a scroll".
"""
from __future__ import annotations

import json

import pytest

from rules import creation, feats, leveling
from rules.sheet import from_dict, to_dict

ABILITIES = {"str": 10, "dex": 14, "con": 12, "int": 16, "wis": 12, "cha": 10}


def _wizard(**over):
    body = {"name": "Scroll Test", "race": "human", "class": "wizard", "gender": "woman",
            "abilities": dict(ABILITIES), "choices": ["int"], "skills": ["spellcraft"],
            "feats": [], "domains": creation.starter_domains("wizard"),
            "spellbook": creation.starter_spells("wizard", 1)}
    body.update(over)
    built, problems = creation.build(body)
    assert problems == [], problems
    return from_dict(built["sheet"], ref="pc")


# --- the feats leave -----------------------------------------------------------------------

def test_the_item_creation_feats_are_out_of_the_catalogue_and_the_picker():
    """Before: `feats.search(kind="item creation")` offered Brew Potion, Scribe Scroll,
    Craft Wand, Craft Staff, Craft Rod, Craft Wondrous Item, Craft Magic Arms and Armor,
    Forge Ring and Craft Construct, nine feats with no effect."""
    for fid in feats.RETIRED:
        assert fid not in feats.all_feats()
        with pytest.raises(KeyError):
            feats.get(fid)
    offered = {f.id for f in feats.search(kind="item creation")}
    assert not offered & feats.RETIRED
    # Master Craftsman keeps its own +2 and stays.
    assert "master-craftsman" in feats.all_feats()


def test_a_saved_wizard_holding_scribe_scroll_loads_with_a_free_pick_back():
    """The owner's saves hold Scribe Scroll (the study counted two). A load must not fail
    and must not keep a dead feat: the line goes, and one feat pick comes back, owed on the
    Class card until it is spent, and saved as a count so the next load still owes it."""
    pc = _wizard()
    d = to_dict(pc)
    d["feats"] = list(d.get("feats") or []) + ["scribe scroll"]
    before = leveling.owed(from_dict(json.loads(json.dumps({**d, "feats": d["feats"][:-1]})),
                                     ref="pc"))["feats"]["owed"]
    back = from_dict(d, ref="pc")
    assert "scribe scroll" not in back.feats
    assert back.feats_refunded == 1
    due = leveling.owed(back)["feats"]
    assert due["owed"] == before + 1
    assert {"for_level": 1, "source": "refund"} in due["picks"]
    again = from_dict(json.loads(json.dumps(to_dict(back))), ref="pc")
    assert again.feats_refunded == 1 and "scribe scroll" not in again.feats
    # Spent like any general pick.
    again.level_feats_taken = 1
    assert leveling.owed(again)["feats"]["owed"] == before


def test_a_printed_creature_sheds_the_feat_with_no_pick_and_no_note():
    """A bestiary block lists Craft Wondrous Item (a lich, a hag): the creature loads
    without the line, and owes nothing, because a printed creature takes no picks."""
    pc = _wizard()
    d = to_dict(pc)
    d.update(kind="npc", feats=["craft wondrous item", "Craft Magic Arms and Armor",
                                "combat casting"])
    npc = from_dict(d, ref="c1")
    assert npc.feats == ["combat casting"]
    assert npc.feats_refunded == 0


def test_the_wizard_takes_a_bonus_feat_at_first_level_in_scribe_scrolls_place():
    """By the book a wizard's 1st-level Scribe Scroll; with it gone, the least surprising
    replacement is one more wizard bonus feat (a metamagic feat or Spell Mastery). An
    owner call (lane report)."""
    assert leveling.class_bonus_feats_at("wizard", 1) == 1
    pc = _wizard(feats=["toughness", "extend-spell"])
    assert "extend spell" in pc.feats
    body = {"name": "Scroll Test", "race": "human", "class": "wizard", "gender": "woman",
            "abilities": dict(ABILITIES), "choices": ["int"], "skills": ["spellcraft"],
            "feats": ["toughness", "iron-will", "alertness"],
            "domains": creation.starter_domains("wizard"),
            "spellbook": creation.starter_spells("wizard", 1)}
    _built, problems = creation.build(body)
    assert any("metamagic feat or Spell Mastery" in p for p in problems), problems


# --- scrolls and wands at the circle -------------------------------------------------------

from rules import enchanter as en  # noqa: E402
from rules import goods, magicitem, spellitems  # noqa: E402
from rules.dice import Dice  # noqa: E402
from rules.engine import Engine, Scene  # noqa: E402


def _circle_wizard(level: int = 1):
    pc = _wizard()
    pc.kind = "pc"
    pc.inventory.update({"scroll-vellum": 2, "silver-ink": 2, "wand-vessel": 1})
    pc.purse = {"gp": 2000}
    prog = pc.track("enchanter")
    prog.level = level
    return pc, prog


def test_scribe_is_an_enchanter_one_method_with_the_books_dc_and_cost():
    """Before: no method made a scroll. Scribe takes vellum and an ink, is DC 5 + the
    scroll's caster level (+5 for a spell neither known nor carried), costs half the book
    price, and goes In progress for 2 hours at 250 gp or less (CRB, Magic Item Creation)."""
    pc, prog = _circle_wizard()
    assert en.method_level("scroll") == 1 and en.method_level("wand") == 2
    plan = en.plan_step(pc, prog, "scroll", {"spell": "mage-armor",
                                              "blank": "inv:scroll-vellum",
                                              "ink": "inv:silver-ink"})
    assert plan.problems == []
    assert plan.item_cl == 1 and plan.spell_level == 1
    assert plan.dc == 5 + 1 + (0 if "mage-armor" in pc.spellbook else 5)
    assert plan.work_minutes == 120
    # 25 gp at market, 12.5 to make: the vellum and the silver ink already pay it.
    assert plan.coin_cp == 0
    high = en.plan_step(pc, prog, "scroll", {"spell": "fireball",
                                              "blank": "inv:scroll-vellum",
                                              "ink": "inv:silver-ink"})
    assert any("writes spells up to 1st-level" in p for p in high.problems)


def test_a_scribed_scroll_waits_in_progress_then_reads_as_its_spell():
    """The made scroll is a real item: In progress for its 2 hours, then read through the
    item cast door at its caster level, and the stack goes down by one."""
    from rules import inprogress

    pc, prog = _circle_wizard()
    plan = en.plan_step(pc, prog, "scroll", {"spell": "mage-armor",
                                              "blank": "inv:scroll-vellum",
                                              "ink": "inv:silver-ink"})
    got = en.finish(pc, prog, plan, 1, now=0)
    key = got["products"][0]["key"].split(":", 1)[1]
    st = pc.stock[key]
    assert inprogress.work_of(st, 60) is not None and inprogress.work_of(st, 200) is not None
    assert pc.inventory["scroll-vellum"] == 1 and pc.inventory["silver-ink"] == 1
    assert spellitems.kind_of(st) == "scroll"
    tags = en._lane("magic_layer").layer({"magic": st.magic, "id": key,
                                          "name": st.name})["tags"]
    assert "item.scroll" in tags and "activation.completion" in tags
    inprogress.collect(pc, key, now=200, here=None)
    assert inprogress.work_of(st, 200) is None
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    e = Engine(s, Dice(seed=3))
    res = e.run(e.validate([{"op": "use_item", "actor": "pc",
                             "params": {"item": st.name, "power": "mage-armor"}}]))
    tell = " ".join(o.tell for o in res.outcomes)
    assert "Mage Armor" in tell and key not in pc.stock
    assert any(m.source == "Mage Armor" for m in pc.ac_modifiers())


def _rogue():
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    pc.ref, pc.kind = "pc", "pc"
    return pc


def test_a_non_caster_needs_use_magic_device_and_the_book_dc():
    """Use Magic Device had no resolved use ("nothing calls for it"). A rogue with no
    ranks is refused in words and keeps the scroll; with ranks, the check is DC 20 + the
    scroll's caster level, and a failure spends nothing."""
    pc = _rogue()
    # Mage armour: no die of the player's to wait on, so each reading resolves at once.
    pc.add_stock(spellitems.make("scroll", "mage-armor", how="bought"), 2)
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    e = Engine(s, Dice(seed=11))
    name = "Scroll of Mage Armor (CL 1)"
    res = e.run(e.validate([{"op": "use_item", "actor": "pc",
                             "params": {"item": name, "power": "mage-armor"}}]))
    assert "trained in Use Magic Device" in res.outcomes[0].tell
    sid = next(k for k, v in pc.stock.items() if spellitems.kind_of(v))
    assert pc.stock[sid].count == 2
    spare = next(k for k, v in pc.ranks.items() if v)
    pc.ranks[spare] -= 1
    pc.ranks["use magic device"] = 1
    seen = []
    for _ in range(6):
        res = e.run(e.validate([{"op": "use_item", "actor": "pc",
                                 "params": {"item": name, "power": "mage-armor"}}]))
        o = res.outcomes[0]
        umd = [r for r in o.rolls if r.label.startswith("Use Magic Device (")]
        assert umd and "DC 21" in umd[0].label
        seen.append(umd[0].total >= 21)
        if sid not in pc.stock:
            break
    left = pc.stock[sid].count if sid in pc.stock else 0
    assert left == 2 - sum(seen)


def test_a_wand_has_fifty_charges_that_outlast_the_night():
    """A wand is a count of 50 on the layer, never a day's: `reset_item_uses` keeps it,
    and the last charge takes the wand off the stack."""
    pc = _rogue()
    pc.add_stock(spellitems.make("wand", "mage-armor", how="bought"), 1)
    sid = next(k for k, v in pc.stock.items() if spellitems.kind_of(v) == "wand")
    pc.stock[sid].magic["uses"] = {"mage-armor": 48}
    pc.reset_item_uses()
    assert pc.stock[sid].magic["uses"] == {"mage-armor": 48}
    entry = spellitems.entry_of(pc.stock[sid])
    assert entry["uses_count"] == 50 and entry["activation"] == "trigger"
    spare = next(k for k, v in pc.ranks.items() if v)
    pc.ranks[spare] -= 1
    pc.ranks["use magic device"] = 1
    pc.skill_modifiers  # the sheet answers UMD from here on
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    e = Engine(s, Dice(seed=5))
    spent = 0
    for _ in range(30):
        res = e.run(e.validate([{"op": "use_item", "actor": "pc", "params": {
            "item": "Wand of Mage Armor (CL 1)", "power": "mage-armor"}}]))
        if any(x.get("kind") == "item_power" for x in res.outcomes[0].effects):
            spent += 1
        if sid not in pc.stock:
            break
    assert spent == 2 and sid not in pc.stock
    assert "last charge" in res.outcomes[0].tell


def test_a_wizard_copies_a_scroll_into_the_book_by_the_books_check():
    """CRB, Arcane Magical Writings: Spellcraft DC 15 + level after an hour's study, the
    scroll spent only on a success, a week before another try; the page cost is paid only
    for a spell written. No code copied a spell into a spellbook before."""
    pc = _wizard()
    pc.purse = {"gp": 100}
    pc.add_stock(spellitems.make("scroll", "magic-missile", how="bought"), 1)
    sid = next(k for k, v in pc.stock.items() if spellitems.kind_of(v))
    plan = spellitems.copy_plan(pc, pc.stock[sid], clock=0)
    if "magic-missile" in pc.spellbook:
        assert plan["refused"]
        return
    assert plan["dc"] == 16 and plan["cost_gp"] == 10 and plan["minutes"] == 120
    failed = spellitems.resolve_copy(pc, sid, 10, clock=0)
    assert not failed["success"] and sid in pc.stock
    assert spellitems.copy_plan(pc, pc.stock[sid], clock=60)["refused"]
    week = 7 * 24 * 60
    got = spellitems.resolve_copy(pc, sid, 16, clock=week)
    assert got["success"] and "magic-missile" in pc.spellbook and sid not in pc.stock
    assert goods.in_copper(pc.purse) == 9000


def test_magic_counters_sell_the_classic_scrolls_and_wands_at_book_price():
    """Nothing sold a scroll or a wand. The magic draw now carries the classic list at the
    book's price, and the bought thing is the circle's own item."""
    sold = {g.key: g for g in goods.magic_item_goods()}
    assert sold["scroll:mage-armor"].price_gp == 25
    assert sold["scroll:fireball"].price_gp == 375
    assert sold["wand:cure-light-wounds"].price_gp == 750
    st = magicitem.finished("wand:cure-light-wounds")
    assert spellitems.kind_of(st) == "wand" and st.magic["known"]["intent"]


def test_a_wand_is_not_a_scroll_to_the_alchemist_or_a_spent_prerequisite():
    """The waiting readers asked only `holds_spell`: a wand would have been copied as a
    scroll for an alchemy formula and spent whole as the enchanter's stand-in spell."""
    pc = _wizard()
    pc.add_stock(spellitems.make("wand", "mage-armor", how="bought"), 1)
    pc.add_stock(spellitems.make("scroll", "shield", how="bought"), 1)
    held = en._spells_held(pc)
    assert "shield" in held and "mage-armor" not in held
