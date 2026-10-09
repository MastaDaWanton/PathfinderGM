"""The forge hand-off (docs/leatherworking-revamp-plan.md §4.3-4.5, §23 row H; contracts
§11 lane H): the leather bench makes the base, the grip and the lacing set; the forge takes
them as items and finishes them. Owner's answers of 2026-10-08: a finished suit's quality
is the LOWER of the base's and the forge's Assemble; steel lamellar is the forge's steel
laced with the leatherworker's lacing set.

Real material documents throughout (content/materials), because the defects these tests
pin were measured on the real catalogue: a raw deer hide on the forge's rack, bone studs'
book numbers lost in a fastening, darkleaf's spell failure at 0%. Each test names the
defect it prevents.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from play import forge_views
from rules import blacksmith as bs
from rules import forge_items
from rules import leatherworker as lw
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from rules.tables import ARMOUR

KIT = {"smithy": None, "kit": True}


def base_record(*, rid="fine-deer-leather-armour", name="Fine Deer Leather Armour", q=2,
                body="deer-hide", creature="", base_for=("studded leather", "armored coat"),
                base="leather") -> dict:
    """A leather armour record exactly as the leather bench's Assemble writes it
    (`leatherworker._record`): the body hardened plates, laced with deer hide."""
    body_spec = {"material": body, "passes": 0, "grade": 2, "tannage": "oak-bark"}
    if creature:
        body_spec["creature"] = creature
    return {"id": rid, "name": name, "kind": "crafted", "craft": "leatherworker", "count": 1,
            "gear": "armour", "base": base, "slot": "armor",
            "quality": "fine", "quality_index": q, "masterwork": q >= 3,
            "pieces": {"body": body_spec,
                       "fastenings": {"material": "deer-hide", "passes": 0, "grade": 2,
                                      "tannage": "oak-bark", "form": "lacing"}},
            "quench": None, "finish": [], "flaws": [], "marks": [],
            "base_for": list(base_for), "product": "leather armour", "tier": "common",
            "smith": {"level": 1, "perks": {"potency": 0, "hardening": 0}}, "schema": 3}


def kesst():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.inventory.clear()
    pc.stock.clear()
    return pc


def carry_base(pc, **over) -> str:
    item = forge_items.stock_item(base_record(**over))
    pc.add_stock(item, 1)
    return f"stock:{item.id}"


def carry_leather(pc, form: str, material: str, **over) -> str:
    h = lw.Hide(form=form, material=material, quarters=1, grade=2, tannage="oak-bark", **over)
    return f"stock:{lw.put_hide(pc, h)}"


def carry_work(pc, w: bs.Work) -> str:
    return f"stock:{bs.put(pc, w)}"


def rack(pc) -> dict:
    return {p.key: p for p in bs.rack(pc)}


def assemble(pc, slots: dict, *, level=1, shape="", aim=True):
    progress = pc.track("blacksmith")
    progress.level = level
    by = rack(pc)
    return bs.plan_step(pc, progress, "assemble",
                        {s: (by[k], 1) for s, k in slots.items()}, where=KIT, shape=shape,
                        masterwork=aim)


def tempered_blank(shape="longsword", gear="weapon", form="blank", material="iron", q=2):
    worked = ["quench", "temper"] + (["hone"] if gear == "weapon" else [])
    return bs.Work(form=form, material=material, shape=shape, gear=gear, quality=q,
                   worked=worked, quench="water")


# --- the rack (plan §4.5 item 1) ------------------------------------------------------------

def test_a_raw_hide_never_reaches_the_forge_rack():
    """Lane D, live, 2026-10-08: once hides listed the pieces they fill, a carried RAW deer
    hide went on the forge's rack and "FITS a breastplate's lining and fastenings" untanned.
    The rack now takes leather only as stock in a form that fills a piece: a grip, a lacing
    set, a base. A hide in the satchel (raw, or bought by the hide in its `sold_as` form),
    a tannin, an oil and leather by the hide on the shelf are the leather bench's alone."""
    pc = kesst()
    pc.inventory.update({"deer-hide": 2, "sharkskin": 1, "oak-bark": 1, "neatsfoot-oil": 1,
                         "steel-studs": 2})
    hide = carry_leather(pc, "leather", "elk-hide")
    lacing = carry_leather(pc, "lacing", "deer-hide")
    base = carry_base(pc)
    by = rack(pc)
    assert "inv:deer-hide" not in by and "inv:sharkskin" not in by
    assert "inv:oak-bark" not in by and "inv:neatsfoot-oil" not in by
    assert hide not in by, "leather by the hide is not cut into anything the forge fits"
    assert {by[lacing].form, by[base].form} == {"lacing", "base"}
    assert "inv:steel-studs" in by, "the forge's studs still reach it"
    # And none of what is on the rack fits a breastplate's lining untanned.
    fits = bs.fits_for("assemble", list(by.values()), gear="armour")
    assert all(why for key, why in fits["lining"].items() if by[key].from_leather)
    assert fits["fastenings"][lacing] == ""


# --- Assemble from a base (plan §4.3, §4.5 items 2 and 3; §23.1 H) --------------------------

def test_the_forge_finishes_a_leather_base_as_studded_leather():
    """§23.1 H: the forge's Assemble accepts a leather base for studded leather. Measured
    before (contracts §9): Assemble refused any finished item as a piece and the rack never
    listed leather records, so a base made at the leather bench could not reach the anvil.
    The base is consumed whole and its body and lining kept, with their grade and tannin;
    the studs fill the fastenings; the record says where the base came from."""
    pc = kesst()
    pc.inventory["steel-studs"] = 1
    base = carry_base(pc)
    plan = assemble(pc, {"body": base, "fastenings": "inv:steel-studs"})
    assert plan.problems == [] and plan.shape == "studded leather"
    assert plan.dc == 13, "the book's DC for studded leather: 10 + its armour bonus 3"
    bs.spend(pc, plan.consumes)
    (key, w, _n), = bs.land(pc, bs.make(plan, 2))
    rec = bs.record(pc.stock[key])
    assert rec["base"] == "studded leather" and rec["name"] == "Fine Deer Studded Leather"
    assert rec["pieces"]["body"] == {"material": "deer-hide", "passes": 0, "grade": 2,
                                     "tannage": "oak-bark"}
    assert rec["pieces"]["fastenings"] == {"material": "steel-studs", "passes": 0}
    assert rec["from_base"]["id"] == "fine-deer-leather-armour"
    assert base.split(":", 1)[1] not in pc.stock and "steel-studs" not in pc.inventory
    # Steel studs carry forge steel's house +2 material AC at half weight (the lead's
    # ruling of 2026-10-08): studded leather's +3 and one more.
    row = forge_items.armour_row(ARMOUR["studded leather"], forge_items.build(rec))
    assert row["ac"] == 4


def test_the_forge_refuses_a_leather_base_for_full_plate():
    """§23.1 H: ...and refuses it for full plate. A base becomes only what its maker made it
    a base for (`base_for`), asked by name or not; a suit that is no base (hide armour) is
    refused on the rack row with the reason in words, as is a base the character wears."""
    pc = kesst()
    pc.inventory["steel-studs"] = 1
    base = carry_base(pc)
    plan = assemble(pc, {"body": base, "fastenings": "inv:steel-studs"}, shape="full plate")
    assert plan.problems == ["Fine Deer Leather Armour is a base for studded leather or "
                             "armored coat, not full plate."]
    hide = carry_base(pc, rid="elk-hide-armour", name="Elk Hide Armour", base="hide armour",
                      base_for=())
    by = rack(pc)
    assert hide not in by, "a finished suit that is nobody's base stays on the leather bench"
    pc.worn["fine-deer-leather-armour"] = dict(by[base].base)
    # Worn is the slot holding it, not the kept record alone (`Actor.worn` keeps a record
    # after it comes off; the final pass found the forge reading that store, 2026-10-09).
    pc.slots["armor"] = ["fine-deer-leather-armour"]
    assert bs.fit_reason("assemble", "body", rack(pc)[base], gear="armour") == \
        "you are wearing it: take it off before the smith works it"


def test_a_sharkskin_grip_fills_a_longsword_haft():
    """§23.1 H: a sharkskin grip fills a longsword's haft. The leather bench cuts a grip from
    a grip-capable hide (plan §4.4); the forge wraps it at Assemble and the record keeps it
    as the leather bench's piece — the hide, its form, grade and tannin — so the build
    reads sharkskin's weapon list at half weight (CMB +2 x 0.5 = +1 at Sound)."""
    pc = kesst()
    grip = carry_leather(pc, "grip", "sharkskin")
    blade = carry_work(pc, tempered_blank())
    assert bs.fit_reason("assemble", "haft", rack(pc)[grip], gear="weapon") == ""
    assert bs.fit_reason("assemble", "fastenings", rack(pc)[grip], gear="armour") == \
        "a grip is wrapped over a weapon's haft"
    plan = assemble(pc, {"head": blade, "haft": grip})
    assert plan.problems == []
    w = bs.make(plan, 1)[0][0]
    rec = bs.record(w)
    assert rec["pieces"]["haft"] == {"material": "sharkskin", "passes": 0, "form": "grip",
                                     "grade": 2, "tannage": "oak-bark"}
    cmb = [s for s in forge_items.build(rec)["specs"] if s["target"] == "cmb"]
    assert [(s["amount"], s["source"]) for s in cmb] == [(1, "sharkskin")]


def test_quality_is_the_lower_of_the_base_and_the_assemble():
    """The owner's answer 2 (2026-10-08): a suit finished across two crafts takes the LOWER
    of the base's tier and the forge's Assemble tier, so neither craft lifts the other's
    work. A Sound base at Blacksmith 3 (ceiling Flawless) caps the step at Sound, and a
    perfect game still makes Sound; a Superior base aiming for masterwork meets the book's
    DC 20, and not aiming caps it at Fine."""
    pc = kesst()
    pc.inventory["steel-studs"] = 3
    sound = carry_base(pc, rid="deer-leather-armour", name="Deer Leather Armour", q=1)
    plan = assemble(pc, {"body": sound, "fastenings": "inv:steel-studs"}, level=3)
    assert plan.step_ceiling == 1
    assert bs.make(plan, 4)[0][0].quality == 1
    superior = carry_base(pc, rid="superior-deer-leather-armour",
                          name="Superior Deer Leather Armour", q=3)
    plan = assemble(pc, {"body": superior, "fastenings": "inv:steel-studs"}, level=3)
    assert (plan.step_ceiling, plan.dc, plan.masterwork_work) == (3, 20, True)
    plan = assemble(pc, {"body": superior, "fastenings": "inv:steel-studs"}, level=3,
                    aim=False)
    assert (plan.step_ceiling, plan.dc) == (2, 13)


def test_studded_leather_is_never_forged_from_bars():
    """Plan §4.5 item 3: the finished leather suits are forge shapes reachable ONLY from a
    base. Studded leather has nothing to forge (the base and its studs), so Forge refuses it
    in words; a metal plate shaped for an armored coat is its lining, never its body."""
    pc = kesst()
    pc.inventory.update({"iron": 3, "charcoal": 2})
    by = rack(pc)
    progress = pc.track("blacksmith")
    plan = bs.plan_step(pc, progress, "forge", {"metal": (by["inv:iron"], 1),
                                                "fuel": (by["inv:charcoal"], 1)},
                        shape="studded leather", where=KIT)
    assert plan.problems == ["Studded leather is finished from a leather base: there is "
                             "nothing to forge for it. Put the base and its studs on the "
                             "anvil at Assemble."]
    plates = carry_work(pc, tempered_blank("armored coat", "armour", "plate"))
    assert bs.fit_reason("assemble", "body", rack(pc)[plates], gear="armour") == (
        "an armored coat is finished from a leather base: put the base in the body and "
        "these plates in the lining")


def test_an_armored_coat_is_a_leather_base_lined_with_forged_plates():
    """Plan §4.2: the book puts the armored coat's metal in its lining, so the forge fills
    the lining slot with plates forged for the coat, and the base keeps its own lacing."""
    pc = kesst()
    base = carry_base(pc)
    plates = carry_work(pc, tempered_blank("armored coat", "armour", "plate", "steel"))
    plan = assemble(pc, {"body": base, "lining": plates})
    assert plan.problems == [] and plan.shape == "armored coat"
    rec = bs.record(bs.make(plan, 2)[0][0])
    assert rec["base"] == "armored coat"
    assert rec["pieces"]["lining"]["material"] == "steel"
    assert rec["pieces"]["fastenings"]["form"] == "lacing"


def test_steel_lamellar_is_laced_with_the_leatherworkers_lacing_set():
    """The owner's answer 1 (2026-10-08): steel lamellar is the forge's steel plates with
    the leatherworker's lacing set. Studs in its fastenings are refused in words; a lacing
    set fills them and the record keeps it as the leather bench's piece."""
    pc = kesst()
    pc.inventory["steel-studs"] = 1
    plate = carry_work(pc, tempered_blank("steel lamellar", "armour", "plate", "steel"))
    lacing = carry_leather(pc, "lacing", "deer-hide")
    plan = assemble(pc, {"body": plate, "fastenings": "inv:steel-studs"})
    assert plan.problems == ["A steel lamellar is laced: its fastenings are a "
                             "leatherworker's lacing set, not steel studs."]
    plan = assemble(pc, {"body": plate, "fastenings": lacing})
    assert plan.problems == []
    rec = bs.record(bs.make(plan, 1)[0][0])
    assert rec["base"] == "steel lamellar"
    assert rec["pieces"]["fastenings"]["form"] == "lacing"


def test_a_generic_hide_base_keeps_its_beast_through_the_forge():
    """Contracts §4.1: a generic hide's inherited DR and resistance are read live from its
    beast, which the leather bench writes on the piece as `creature`. The forge keeps its
    product in tags, and a piece's tag carried only material and passes, so a wolf-hide
    base studded at the forge would have come out without its wolf."""
    pc = kesst()
    pc.inventory["steel-studs"] = 1
    base = carry_base(pc, body="generic-fur-hide", creature="dire-wolf")
    plan = assemble(pc, {"body": base, "fastenings": "inv:steel-studs"})
    assert plan.problems == []
    (key, _w, _n), = bs.land(pc, bs.make(plan, 1))
    again = bs.record(pc.stock[key])
    assert again["pieces"]["body"]["creature"] == "dire-wolf"
    assert again["pieces"]["body"]["grade"] == 2


def test_a_failed_finish_spoils_the_studs_before_the_base():
    """The forge's failure rule (plan §11): a miss by 5 ruins half of what was on the anvil,
    a tie going to the cheaper, unworked thing. The base counted as unworked raw stock, so
    a miss by 5 with one base and one set of studs threw away the leatherworker's suit."""
    pc = kesst()
    pc.inventory["steel-studs"] = 1
    base = carry_base(pc)
    plan = assemble(pc, {"body": base, "fastenings": "inv:steel-studs"})
    assert [(p.key, n) for p, n in bs.failure_losses(plan, 5)] == [("inv:steel-studs", 1)]


def test_leather_fitted_at_the_forge_is_not_gated_by_the_smiths_level():
    """The smith fits a grip or studs a base; the hide is the tanner's work. Blacksmith 1
    works uncommon metal at best, and a rare red dragonhide base was refused as "beyond
    Blacksmith 1" though the smith's own piece, the studs, is common."""
    pc = kesst()
    pc.inventory["steel-studs"] = 1
    base = carry_base(pc, body="red-dragonhide", rid="red-dragonhide-leather-armour",
                      name="Red Dragonhide Leather Armour")
    plan = assemble(pc, {"body": base, "fastenings": "inv:steel-studs"})
    assert plan.problems == []


# --- forge_items (lane B finished; the two fixes the hand-off needs) ------------------------

PLAIN = {"id": "plain-hide", "name": "Plain Hide", "kind": "hide", "tier": "common",
         "pieces": {"armour": ["body", "fastenings", "lining"]},
         "armour": [{"type": "skill_mod", "target": "survival", "amount": 2,
                     "bonus_type": "material"}], "working": []}


def test_bone_studs_book_numbers_reach_bone_studded_leather(monkeypatch):
    """Lanes D and E, 2026-10-08: bone studs' book effects (1 less AC than metal studs, 1
    less check penalty) sit in the fastening, and the build read book effects from the main
    piece only, so a bone-studded leather suit on a hide with no armour numbers measured AC
    3 and ACP -1: studded leather's own row, the book's -1 and +1 lost. Now AC 2, ACP 0.
    The main-piece rule stands everywhere else: mithral fittings on a breastplate do not
    bring mithral's spell-failure book."""
    real = forge_items.material
    monkeypatch.setattr(forge_items, "material", lambda m: PLAIN if m == "plain-hide" else real(m))
    rec = {"id": "bone", "name": "Bone-Studded Leather", "gear": "armour",
           "base": "studded leather", "craft": "leatherworker", "quality_index": 1,
           "pieces": {"body": {"material": "plain-hide"},
                      "fastenings": {"material": "bone-studs"}},
           "smith": {"level": 1, "perks": {}}}
    row = forge_items.armour_row(ARMOUR["studded leather"], forge_items.build(rec))
    assert (row["ac"], row["acp"]) == (2, 0)
    plate = {"id": "bp", "name": "Breastplate", "gear": "armour", "base": "breastplate",
             "quality_index": 1, "pieces": {"body": {"material": "iron"},
                                            "fastenings": {"material": "mithral-fittings"}},
             "smith": {"level": 1, "perks": {}}}
    b = forge_items.build(plate)
    assert not [e for e in b["book"] if e.get("source") == "mithral-fittings"]
    assert forge_items.armour_row(ARMOUR["breastplate"], b)["asf"] == 25


def test_darkleaf_spell_failure_stops_at_five_percent():
    """Lanes B and E, 2026-10-08: darkleaf cloth lowers arcane spell failure by 10% "to a
    minimum of 5%" (Ultimate Equipment; prior art §1.3), and a darkleaf leather suit
    computed 10 - 10 = 0%. Now 5%; padded's 5% stays 5% (the floor never raises a suit),
    studded leather's 15% comes down to 5% as the book's ten points say."""
    def asf(base):
        rec = {"id": "d", "name": "Darkleaf", "gear": "armour", "base": base,
               "craft": "leatherworker", "quality_index": 1,
               "pieces": {"body": {"material": "darkleaf-cloth"}},
               "smith": {"level": 1, "perks": {}}}
        return forge_items.armour_row(ARMOUR[base], forge_items.build(rec))["asf"]

    assert (asf("leather"), asf("padded"), asf("studded leather")) == (5, 5, 5)


# --- through the API and the engine ---------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    from rules import places

    monkeypatch.setattr(places, "smithy_here", lambda scene, known=(): None, raising=False)
    monkeypatch.setattr(places, "has_field_kit", lambda actor, *a, **k: True, raising=False)
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        forge_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        c.save()
        yield Client()
        cm._LIVE.clear()
        forge_views._PENDING.clear()


def post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def test_a_base_is_studded_through_the_forge_api_and_worn(client):
    """The whole hand-off as the page drives it: the state's rack lists the base and the
    studs and no raw hide; check, roll and finish make studded leather; the base is gone
    from the pack; and Kesst, in table leather at AC 15, wears the forge's studded leather
    at 17 (studded leather's +3, and steel studs' house +1)."""
    c = cm.current()
    pc = c.scene.pc()
    pc.inventory.update({"steel-studs": 1, "deer-hide": 1})
    base = carry_base(pc, q=1, rid="deer-leather-armour", name="Deer Leather Armour")
    c.save()
    state = client.get("/api/forge/state").json()
    rows = {x["key"]: x for x in state["rack"]}
    assert "inv:deer-hide" not in rows
    assert rows[base]["form"] == "base" and rows[base]["group"] == "Leather bases"
    # Put on the anvil anyway (an old page, a hand-made request), the raw hide is refused
    # in words, not as "no longer on your rack" about a hide still in the pack.
    r = post(client, "/api/forge/check", {"method": "assemble",
                                          "slots": {"body": "inv:deer-hide"}})
    assert r.status_code == 400 and r.json()["error"] == (
        "Deer Hide is a hide, not yet a piece the forge can use: tan it and cut it at the "
        "leather bench into a grip, a lacing set or a base.")
    body = {"method": "assemble", "slots": {"body": base, "fastenings": "inv:steel-studs"}}
    check = post(client, "/api/forge/check", body).json()
    assert check["problems"] == [] and check["gear"] == "armour"
    assert check["preview"]["card"] is not None
    rolled = post(client, "/api/forge/roll", {**body, "face": 20}).json()
    assert rolled["roll"]["success"], rolled
    done = post(client, "/api/forge/finish", {"token": rolled["token"], "score": 1.0}).json()
    (product,) = done["products"]
    assert product["name"] == "Deer Studded Leather" and product["record"]["base"] == \
        "studded leather"
    assert not [d for d in done["discoveries"] if d["material"] == "deer-hide"]
    pc = cm.current().scene.pc()
    assert base.split(":", 1)[1] not in pc.stock
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(pc)
    engine = Engine(scene, Dice(seed=5))
    assert pc.ac() == 15
    out = engine.run(engine.validate([{"op": "wear", "actor": "pc", "because": "test",
                                       "params": {"item": product["name"]}}])).outcomes[0]
    assert out.effects, out.tell
    assert pc.armour == "studded leather" and pc.ac() == 17


def test_the_forges_teacher_never_teaches_a_hide(client):
    """Lane F, 2026-10-08: the forge's Ask always used the smith's rows whatever was asked
    about, so a blacksmith would teach deer hide at the smith's price and pay Blacksmith
    mastery for it. A hide answers to the leatherworker's rows (`knowledge.craft_of`):
    the forge refuses in words and names where to ask, and its card offers no smith."""
    r = post(client, "/api/forge/ask", {"material": "deer-hide", "ref": "anyone"})
    assert r.status_code == 400
    assert r.json()["error"] == ("Deer Hide is a tanner's material, not a smith's: show it "
                                 "to a leatherworker at the leather bench.")
    # A metal is still the smith's: the refusal is about the person, not the material.
    r = post(client, "/api/forge/ask", {"material": "iron", "ref": "anyone"})
    assert r.json()["error"] == "Nobody here by that name knows metals."


def test_the_smiths_ledger_holds_no_hide_and_serves_no_hide_card(client):
    """Lane U5, live, 2026-10-08: `knowledge.ledger` lists every material met, so the
    Smith's ledger listed the hides and tannins carried (here deer hide and oak bark beside
    iron), and the forge's card for a hide came in the steel swatch with an Assay that would
    cut a sliver of hide as if it were a bar. A tanner's material belongs to the Tanner's
    ledger: the forge's ledger leaves it out, and its card refuses in words and names the
    leather bench's card for the page to open instead."""
    c = cm.current()
    pc = c.scene.pc()
    pc.inventory.update({"deer-hide": 1, "oak-bark": 1, "iron": 1})
    c.save()
    ids = {row["id"] for row in client.get("/api/forge/ledger").json()["ledger"]}
    assert "iron" in ids and not ids & {"deer-hide", "oak-bark"}, ids
    r = client.get("/api/forge/material/deer-hide")
    assert r.status_code == 409
    assert r.json() == {"error": "Deer Hide is a tanner's material: its card is in the "
                                 "Tanner's ledger at the leather bench.",
                        "track": "leatherworker", "card": "/api/leather/material/deer-hide"}
    assert client.get("/api/forge/material/iron").status_code == 200


def test_the_forge_racks_card_opens_from_the_question_mark_and_never_from_the_row():
    """The owner's emergency rule of 2026-10-08 (master 39a783c, skillhelp.js): a help card
    opens from a "?" only. Lane U5 measured the forge's rack still opening its ledger card
    on hovering anywhere on a rack row (`closest(".fr.has-info")`) and on focusing a row's
    add button (`closest(".fr-add")`), so walking the rack by pointer or by arrow keys
    dragged a card over the next rows. Every listener that opens or keeps the card now
    resolves the "?" itself (`infoOf`), and none looks for the row or its add button."""
    from pathlib import Path

    js = (Path("play") / "static" / "js" / "table" / "41-forge-rack.js").read_text(
        encoding="utf-8")
    start = js.index("// --- the ledger card")
    card = js[start:]
    for event in ("mouseover", "mouseout", "focusin"):
        at = card.index(f'list.addEventListener("{event}"')
        body = card[at:card.index("});", at)]
        assert "infoOf(e.target)" in body, event
        assert '".fr.has-info")' not in body and '".fr-add")' not in body, event
    assert '.bt-info[data-material]' in card[card.index("function infoOf"):]
