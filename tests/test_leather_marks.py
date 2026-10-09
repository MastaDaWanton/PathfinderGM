"""The tanner's marks (docs/leatherworking-revamp-plan.md §14.6; the owner, 2026-10-08:
"keep marks as planned"): a tannin, oil, wax, thread or dye leaves at most one small mark on
what it was worked into, applied once and unscaled from the step that used it; an item
carries one per consumable kind; two marks of one kind give the higher; a mark is a
property to discover, so the page names it only once it is known.

Measured before this lane, 2026-10-08, which is what these tests hold:

  * marks were held: the nine proposed marks sat in a `marks_on_hold` block nothing read,
    `materials.MARKS_HELD` refused a mark on any document, the bench wrote `marks: []` on
    every item and `forge_items.build` had no reader for the field at all, so salamander
    oil's fire resistance 1 never reached an item;
  * a studded leather finished at the forge from a leather base dropped everything the
    base's record carried but its pieces;
  * `Engine._damage_note`, whose job is that "damage disappearing without explanation" never
    happens, said DR, percent resistance and temporary hit points, and never energy
    resistance: a fire-resistant coat took a point off every burn in silence;
  * the leather finish response sent the item's whole build to the page, mark specs and
    their consumable's id included, whether or not the tanner knew the mark.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from play import leather_views as views
from rules import blacksmith, forge_items, knowledge, materials
from rules import leatherworker as lw
from rules.dice import Dice
from rules.engine import Engine, Scene, _damage_note
from rules.sheet import full_sheet, load_pc

TANNERY = {"at": "tannery",
           "tannery": {"kind": "town", "place": "loc~urban:the-tannery", "keeper": None,
                       "rate_cp_per_hour": 10, "vat_rate_cp_per_day": 20, "vats": 4,
                       "vats_free": 0, "vat_units": 4},
           "field_kit": True, "tiers": ("common", "uncommon", "rare", "exotic", "legendary"),
           "vats": True, "name": "the tannery"}


def _table(seed=5):
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    pc.inventory.clear()
    pc.stock.clear()
    pc.herb_known.clear()
    scene.add(pc)
    pc.track(lw.TRACK_ID).level = 10
    return scene, Engine(scene, Dice(seed=seed)), pc


def _rack(pc):
    return {p.key: p for p in lw.rack(pc, 0)}


def _key(pc, form, material=None, **want):
    for p in lw.rack(pc, 0):
        if p.form == form and (material is None or p.material == material) and all(
                getattr(p.hide, k, None) == v for k, v in want.items()):
            return p.key
    raise AssertionError(f"no {form} {material} on the rack: "
                         f"{[(p.key, p.form) for p in lw.rack(pc, 0)]}")


def _step(pc, method, slots, **kw):
    rack = _rack(pc)
    p = lw.plan_step(pc, pc.track(lw.TRACK_ID), method,
                     {k: (rack[v], 1) for k, v in slots.items()}, 1, where=TANNERY, **kw)
    assert not p.problems, p.problems
    made = lw.make(p, 2)
    lw.spend(pc, p.consumes)
    return lw.land(pc, p, made, now=0, where=TANNERY, setup_score=0.5)


def _suit(pc, oil="salamander-oil"):
    """Leather armour through the real steps: a bought deer leather curried with the oil,
    cut for a leather armour's body, hardened, and laced with plain deer lacing."""
    pc.carry("deer-hide", 3)
    pc.carry(oil, 2)
    for _ in range(2):                  # a leather armour's body is two units of hide
        _step(pc, "curry", {"piece": "inv:deer-hide", "oil": f"inv:{oil}"})
    curried = next(p.key for p in lw.rack(pc, 0)
                   if p.hide is not None and "curry" in p.hide.worked)
    _step(pc, "cut", {"hide": curried}, product="leather armour", part="body")
    _step(pc, "harden", {"piece": _key(pc, "panel", "deer-hide", pattern="leather armour")})
    _step(pc, "cut", {"hide": "inv:deer-hide"}, product="lacing")
    got = _step(pc, "assemble", {"body": _key(pc, "plate", "deer-hide"),
                                 "fastenings": _key(pc, "lacing", "deer-hide")},
                masterwork=False)
    return got[0]["record"]


def _wear(engine, item):
    return engine.run(engine.validate([{"op": "wear", "actor": "pc", "because": "test",
                                        "params": {"item": item}}])).outcomes[0]


def _record(marks, q=1, passes=0, rid="probe-coat"):
    return {"id": rid, "name": "Probe Coat", "kind": "crafted", "craft": "leatherworker",
            "gear": "armour", "base": "leather", "slot": "armor", "quality_index": q,
            "pieces": {"body": {"material": "deer-hide", "passes": passes,
                                "tannage": "oak-bark"}},
            "marks": list(marks), "smith": {"level": 1, "perks": {}}}


def _fire(build):
    return [s for s in build["specs"] if s.get("type") == "resistance"
            and s.get("target") == "fire"]


# --- the bench writes it, the build reads it, the wearer gets it -----------------------------

def test_salamander_oil_at_the_curry_step_reaches_the_wearer_through_the_funnel():
    """Salamander oil's fire resistance 1 never reached an item while marks were held (the
    bench wrote `marks: []`, the build had no reader). Curried into the body of a leather
    armour, it is now on the record by id, read live by the build (stamped `item:<id>`, its
    source the oil), worn through the engine's `wear` op, read by `Actor.resistance` and the
    sheet, gone when the suit comes off, and said in the damage tell when it soaks a burn."""
    scene, engine, pc = _table()
    rec = _suit(pc)
    assert rec["marks"] == ["oak-bark", "salamander-oil"]
    b = forge_items.build(rec)
    fire = _fire(b)
    assert [(s["amount"], s["source"], s["origin"]) for s in fire] == [
        (1, "salamander-oil", f"item:{rec['id']}")]
    assert [r["material"] for r in b["marks"] if r["applied"]] == ["salamander-oil"]
    assert pc.resistance("fire") == 0
    out = _wear(engine, rec["id"])
    assert out.effects, out.tell
    assert pc.resistance("fire") == 1
    assert {"type": "fire", "amount": 1} in full_sheet(pc)["defense"]["resistances"]
    d = pc.take_damage(5, "fire")
    assert d["taken"] == 4 and d["resisted"] == 1
    assert "less fire resistance (1)" in _damage_note(d)
    engine.run(engine.validate([{"op": "take_off", "actor": "pc", "because": "test",
                                 "params": {"item": rec["id"]}}]))
    assert pc.resistance("fire") == 0, "remove the suit and the mark's contribution evaporates"


def test_the_record_survives_a_save_and_a_studding_at_the_forge():
    """The record names its consumables by id and nothing computed (the forge's rule), so a
    save keeps them; and a studded leather finished at the forge from a leather base dropped
    everything the base carried but its pieces: the forge's `Work` now carries `marks` in
    its tags (`forge.mark.<id>`), so studding a salamander-oiled coat keeps the oil's mark."""
    w = blacksmith.Work(form="item", material="deer-hide", shape="studded leather",
                        gear="armour", quality=2, pieces={"body": {"material": "deer-hide"}},
                        marks=["oak-bark", "salamander-oil"], name="Deer Studded Leather")
    back = blacksmith.Work.from_tags(w.tags(), name=w.name)
    assert back.marks == ["oak-bark", "salamander-oil"]
    rec = blacksmith.record(back)
    assert rec["marks"] == ["oak-bark", "salamander-oil"]
    assert [s["amount"] for s in _fire(forge_items.build(rec))] == [1]
    plain = blacksmith.record(blacksmith.Work(form="item", material="iron", shape="longsword",
                                              gear="weapon", quality=1, name="Sword"))
    assert "marks" not in plain, "a smith's own item is unchanged"


# --- the rules of a mark -------------------------------------------------------------------------

def test_two_fire_marks_give_the_higher_and_one_mark_per_kind(monkeypatch):
    """Plan §14.6: "marks of one kind do not stack with each other (two fire-resistance marks
    give the higher)", and "at most one mark per consumable kind". Salamander oil and
    fireproof wax both leave fire resistance 1: the coat resists 1, not 2. A stronger fire
    mark (a probe oil at 2) beats the 1 whichever is listed first. And a hand-edited record
    naming two oils keeps the first: the second is listed with why it gives nothing."""
    both = forge_items.build(_record(["salamander-oil", "fireproof-wax"]))
    assert [s["amount"] for s in _fire(both)] == [1]
    rows = {r["material"]: r for r in both["marks"]}
    assert rows["salamander-oil"]["applied"] and not rows["fireproof-wax"]["applied"]
    assert "do not stack" in rows["fireproof-wax"]["why"]

    real = forge_items.material
    hot = dict(materials.get("salamander-oil"), id="probe-hot-wax", name="Probe Hot Wax",
               kind="wax", mark={"type": "resistance", "target": "fire", "amount": 2})
    monkeypatch.setattr(forge_items, "material",
                        lambda mid: hot if mid == "probe-hot-wax" else real(mid))
    b = forge_items.build(_record(["salamander-oil", "probe-hot-wax"]))
    assert [(s["amount"], s["source"]) for s in _fire(b)] == [(2, "probe-hot-wax")]
    assert "higher" in {r["material"]: r for r in b["marks"]}["salamander-oil"]["why"]

    two_oils = forge_items.build(_record(["salamander-oil", "troll-fat"]))
    rows = {r["material"]: r for r in two_oils["marks"]}
    assert not rows["troll-fat"]["applied"] and "one mark per oil" in rows["troll-fat"]["why"]
    assert two_oils["gear"]["hardness"] == forge_items.build(_record([]))["gear"]["hardness"]


def test_a_mark_is_applied_once_and_never_scaled():
    """Plan §13.3: "marks are applied once, unscaled, like the quench mark". The forge's sum
    multiplies a piece's numbers by quality, potency and 1.5 per lamination and rounds
    toward zero; a fire resistance 1 through that maths at Crude is 0.75, which rounds to
    nothing. Measured at every quality from Crude to Legendary and with two laminations:
    fireproof wax gives 1, troll fat's hardness gives 1, and a two-dye record gives one."""
    for q in range(0, 6):
        for passes in (0, 2):
            b = forge_items.build(_record(["fireproof-wax", "troll-fat"], q=q, passes=passes))
            plain = forge_items.build(_record(["oak-bark"], q=q, passes=passes))
            assert [s["amount"] for s in _fire(b)] == [1], (q, passes)
            assert b["gear"]["hardness"] - plain["gear"]["hardness"] == 1, (q, passes)
    stealth = forge_items.build(_record(["shadow-black", "void-dye"]))
    assert [s["amount"] for s in stealth["specs"] if s.get("target") == "stealth"] == [1], \
        "two dyes: the first dye's mark, one per kind"


def test_a_grip_only_mark_never_reaches_a_suit():
    """Styx-mordant's mark is "+1 damage vs outsiders on a grip" (plan §14.6). A suit's
    standing specs are read on every roll its wearer makes (`Actor._standing_mods`), so an
    unkeyed damage mark on armour would put +1 on every blow the wearer struck at an
    outsider. Keyed to a weapon, a styx-tanned coat carries nothing from it."""
    b = forge_items.build(_record(["styx-mordant"]))
    assert not [s for s in b["specs"] if s.get("target") == "damage"]
    assert [r["effect"] for r in b["marks"]] == [None]


# --- a mark is a property to discover --------------------------------------------------------------

def test_an_ungraded_mark_is_never_on_the_page_and_a_graded_one_is():
    """A mark is a discoverable property (plan §14.6, §16). Measured before: the finish
    response sent the build whole, so an ungraded salamander oil's spec ("resistance fire 1",
    source "salamander-oil") was in the page's JSON. Now the build card's `marks` and the
    page's copy of the build carry only marks the tanner knows; the item's own numbers stay
    (they are on the sheet anyway). Working the oil teaches its working trait and not its
    mark; a Grade that finds the mark puts it on the card as "Curry with Salamander Oil:
    Resist fire 1"."""
    scene, engine, pc = _table()
    rec = _suit(pc)
    b = forge_items.build(rec)
    oil = materials.get("salamander-oil")
    knowledge.worked(pc, "salamander-oil", clock=0)     # what the finish route does
    assert "t0" in knowledge.known_keys(pc, oil), "curry taught the oil's working trait"
    assert "k0" not in knowledge.known_keys(pc, oil), "and not its mark"
    card = views._card(b, rec["pieces"], "armour", "Fine", pc)
    assert card["marks"] == []
    page = views._page_build(b, pc)
    assert "salamander-oil" not in json.dumps(page["specs"]) + json.dumps(page["marks"])
    assert "fire" not in json.dumps(page["specs"])
    assert _fire(b), "the item itself still has it"

    knowledge.reveal(pc, "salamander-oil", ["k0"], "graded, day 1")
    card = views._card(b, rec["pieces"], "armour", "Fine", pc)
    assert card["marks"] == [{"step": "Curry", "material": "Salamander Oil",
                              "text": "Resist fire 1", "applied": True, "why": ""}]
    assert _fire(views._page_build(b, pc))


def test_grade_finds_the_mark_of_an_oil_that_has_been_worked():
    """Grade reveals one benefit and one drawback (plan §16), the first unknown of each in
    key order. Before, the store skipped the mark while held, and grading salamander oil
    could only ever teach "supple". Now: working the oil (a Curry) teaches "supple" free,
    and the next Grade finds the fire mark. (Measured: on a never-worked oil the first Grade
    finds "supple", a working trait being a benefit and sorting before the mark; the second
    finds the mark.)"""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.herb_known.clear()
    knowledge.worked(pc, "salamander-oil", clock=0)
    got = knowledge.grade(pc, "salamander-oil", 40, clock=0)
    assert got["success"] and got["revealed"] == ["k0"], got
    pc.herb_known.clear()
    first = knowledge.grade(pc, "salamander-oil", 40, clock=0)["revealed"]
    second = knowledge.grade(pc, "salamander-oil", 40, clock=0)["revealed"]
    assert (first, second) == (["t0"], ["k0"])


def test_the_build_card_draws_the_marks_the_server_sends_and_nothing_else():
    """Plan §14.6, "listed under the item's build". The forge's one card (43-forge-order.js,
    `BuildCard`) gains `markLines`, which prints the server's `marks` rows in its own words
    and nothing it was not sent; the leather work order (58) draws the same lines under the
    build, from `BuildCard.markLines` alone. Run in node on the real function."""
    import re
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    root = Path(__file__).resolve().parent.parent / "play" / "static" / "js" / "table"
    forge = (root / "43-forge-order.js").read_text(encoding="utf-8")
    fn = re.search(r"  function markLines\(card\) \{.*?\n  \}\n", forge, re.S).group(0)
    card = {"marks": [
        {"step": "Curry", "material": "Salamander Oil", "text": "Resist fire 1",
         "applied": True, "why": ""},
        {"step": "Tool", "material": "Fireproof Wax", "text": "Resist fire 1",
         "applied": False, "why": "the salamander oil mark is the same, and marks of one "
                                  "kind do not stack"}]}
    js = fn + f"\nconsole.log(JSON.stringify([markLines({json.dumps(card)}), markLines({{}})]));"
    got = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True,
                                    check=True).stdout)
    assert got == [["Curry with Salamander Oil: Resist fire 1",
                    "Tool with Fireproof Wax: Resist fire 1 (not applied: the salamander oil "
                    "mark is the same, and marks of one kind do not stack)"], []]
    assert "markLines: markLines" in forge and "markLines(card).length" in forge
    order = (root / "58-leather-order.js").read_text(encoding="utf-8")
    assert "BuildCard.markLines(card)" in order and ">Marks: " in order
    assert "—" not in fn and "–" not in fn


@pytest.fixture
def client(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        yield Client()
        cm._LIVE.clear()


def test_the_ledger_card_sends_an_unknown_mark_blank_and_a_known_one_under_its_group(client):
    """GET api/leather/material/<id>: an unknown row goes out as `unknown-N` with no text and
    no group (lane U5's fix), so a supply's mark is not even counted as a mark before Grade;
    once known it is the `mark` group's row with its words."""
    c = cm.current()
    c.scene.pc().carry("salamander-oil", 1)
    c.save()
    rows = client.get("/api/leather/material/salamander-oil").json()["properties"]
    assert all(r.get("group") is None for r in rows if not r["known"])
    assert not any("fire" in str(r.get("text") or "").lower() for r in rows)
    c = cm.current()
    knowledge.reveal(c.scene.pc(), "salamander-oil", ["k0"], "graded, day 1")
    c.save()
    rows = client.get("/api/leather/material/salamander-oil").json()["properties"]
    assert {"key": "k0", "group": "mark", "text": "Resist fire 1"}.items() <= next(
        r for r in rows if r["key"] == "k0").items()
