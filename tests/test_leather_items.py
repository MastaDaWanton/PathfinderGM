"""What a leather item IS, computed from what it is made of (leather lane B: plan §13, §15,
§18.2-18.4; contracts §4.2).

The leatherworker's products are the forge's crafted-item record (`forge_items.build`), so
these pin the build's leather readers — always-masterwork hides, the book's allowed bases,
`as_base`, worn goods, a creature's inherited DR and resistance, an item's own immunity —
and the object numbers the book gives leather (CRB Tables 7-12, 7-13). Material documents
come through `forge_items.material`, the one door the build reads, because lane D's data
pass is built in parallel: these are about the readers, not the 127 documents.
"""
from __future__ import annotations

import pytest

from rules import armour as armour_mod
from rules import forge_items, item_tags, object_numbers
from rules.sheet import Item
from rules.tables import ARMOUR, SHIELDS

DOCS = {
    # A hide with no AC modifier of its own: the plan's proof-of-done body (§13.3).
    "plain-hide": {"id": "plain-hide", "name": "Plain hide", "kind": "hide",
                   "armour": [{"type": "skill_mod", "target": "survival", "amount": 2,
                               "bonus_type": "material"},
                              {"type": "gear_mod", "target": "acp", "amount": -2},
                              {"type": "gear_mod", "target": "max_dex", "amount": 2}]},
    # The plan's worked example's elk (§13.3): AC +2, ACP -2, Survival +2.
    "elk-hide": {"id": "elk-hide", "name": "Elk hide", "kind": "hide",
                 "armour": [{"type": "combat_mod", "target": "ac", "amount": 2,
                             "bonus_type": "material"},
                            {"type": "gear_mod", "target": "acp", "amount": -2},
                            {"type": "skill_mod", "target": "survival", "amount": 2,
                             "bonus_type": "material"}]},
    "winter-wolf-pelt": {"id": "winter-wolf-pelt", "name": "Winter Wolf Pelt", "kind": "hide",
                         "armour": [{"type": "resistance", "target": "cold", "amount": 2},
                                    {"type": "skill_mod", "target": "stealth", "amount": 2,
                                     "bonus_type": "material"},
                                    {"type": "gear_mod", "target": "acp", "amount": -2},
                                    {"type": "combat_mod", "target": "ac", "amount": 1,
                                     "bonus_type": "material"}]},
    "red-dragonhide": {"id": "red-dragonhide", "name": "Red Dragonhide", "kind": "hide",
                       "always_masterwork": True, "druid_permitted": True,
                       "armour": [{"type": "object_immunity", "target": "fire", "book": True},
                                  {"type": "gear_mod", "target": "enchant_cost_pct",
                                   "amount": -25, "applies_to": "energy_resistance",
                                   "book": True},
                                  {"type": "gear_mod", "target": "hardness", "amount": 8,
                                   "book": True},
                                  {"type": "gear_mod", "target": "hp_per_inch", "amount": 5,
                                   "book": True},
                                  {"type": "resistance", "target": "fire", "amount": 2},
                                  {"type": "gear_mod", "target": "weight_pct", "amount": 10}]},
    "electric-eel-skin": {"id": "electric-eel-skin", "name": "Electric Eel Skin",
                          "kind": "hide", "always_masterwork": True,
                          "allowed_bases": ["leather", "hide armour", "studded leather"],
                          "armour": [{"type": "resistance", "target": "electricity",
                                      "amount": 2, "book": True}]},
    "bulette-leather": {"id": "bulette-leather", "name": "Bulette Leather", "kind": "hide",
                        "armour": [{"type": "as_base", "target": "studded leather",
                                    "book": True},
                                   {"type": "gear_mod", "target": "acp", "amount": -2},
                                   {"type": "skill_mod", "target": "survival", "amount": 2,
                                    "bonus_type": "material"}]},
    # House DR on a hand-written document, and the same DR marked as the creature's own.
    "silver-house-hide": {"id": "silver-house-hide", "name": "Silver-touched hide",
                          "kind": "hide",
                          "armour": [{"type": "damage_reduction", "amount": 1,
                                      "bypass": "silver"}]},
    "werewolf-pelt": {"id": "werewolf-pelt", "name": "Werewolf pelt", "kind": "hide",
                      "armour": [{"type": "damage_reduction", "amount": 1, "bypass": "silver",
                                  "from_creature": True},
                                 {"type": "resistance", "target": "cold", "amount": 2,
                                  "from_creature": True}]},
    "deer-hide": {"id": "deer-hide", "name": "Deer hide", "kind": "hide",
                  "armour": [{"type": "gear_mod", "target": "acp", "amount": 2},
                             {"type": "gear_mod", "target": "max_dex", "amount": 2},
                             {"type": "gear_mod", "target": "hardness", "amount": -2}]},
}


@pytest.fixture(autouse=True)
def documents(monkeypatch):
    real = forge_items.material
    monkeypatch.setattr(forge_items, "material",
                        lambda mid: DOCS.get(str(mid)) or real(mid))


def suit(body, *, base="leather", rid="test-suit", q=1, level=1, gear="armour",
         lining=None, fastenings=None, slot="armor", **over) -> dict:
    pieces = {"body": {"material": body, "passes": 0}}
    if fastenings:
        pieces["fastenings"] = {"material": fastenings, "passes": 0}
    if lining:
        pieces["lining"] = {"material": lining, "passes": 0}
    rec = {"id": rid, "name": rid.replace("-", " ").title(), "kind": "crafted",
           "craft": "leatherworker", "count": 1, "gear": gear, "base": base, "slot": slot,
           "quality_index": q, "masterwork": False, "pieces": pieces,
           "smith": {"level": level, "perks": {}}, "schema": 3}
    rec.update(over)
    return rec


def by_type(b, kind):
    return [s for s in forge_items.roll_specs(b) if s.get("type") == kind]


# --- the suits the book prints (plan §13.2) -------------------------------------------------

def test_the_leather_suits_the_book_prints_have_rows():
    """Questions doc, 'Book versus catalogue' 9: hide armour was unreachable and leather
    lamellar, quilted cloth and the madu were missing from the tables entirely, so the bench
    could emit only `leather` or `studded leather`. Numbers read 2026-10-08 off the Archives
    of Nethys light and medium armour tables (APG, UE) and the madu's own page (UE p.9)."""
    want = {
        "quilted cloth": (1, 8, 0, 10, "light", 15),
        "leather lamellar": (4, 3, -2, 20, "light", 25),
        "armored coat": (4, 3, -2, 20, "medium", 20),
        "horn lamellar": (5, 3, -4, 25, "medium", 30),
        "steel lamellar": (6, 3, -5, 25, "medium", 35),
    }
    for key, (ac, dex, acp, asf, weight, lb) in want.items():
        r = ARMOUR[key]
        assert (r["ac"], r["max_dex"], r["acp"], r["asf"], r["weight"], r["lb"]) == \
            (ac, dex, acp, asf, weight, lb), key
        assert armour_mod.key_for(key) == ("armour", key)
    assert (SHIELDS["madu"]["ac"], SHIELDS["madu"]["acp"], SHIELDS["madu"]["asf"],
            SHIELDS["madu"]["lb"]) == (1, -2, 5, 5)
    assert armour_mod.key_for("armoured coat") == ("armour", "armored coat")
    # A bought one knows what it is made of: the armoured coat's metal is in its lining
    # (the book's plates), the leather lamellar has none, and the madu is leather.
    assert item_tags.has_material("armored coat", "material.metal")
    assert not item_tags.has_material("leather lamellar", "material.metal")
    assert not item_tags.has_material("madu", "material.metal")
    assert item_tags.has_material("steel lamellar", "material.metal")


def test_hide_armour_answers_its_weight_class_without_a_bare_hide_alias():
    """The contracts (§4.2) asked for an alias `hide` -> `hide armour` so a
    `when.armour.weight` clause on a hide suit is not dropped ("a bare 'hide' resolves to
    nothing today"). Measured: every record's `base` is the table key "hide armour", which
    already resolves, so the clause holds; and a bare "hide" must stay NOT armour — a
    tanner's raw hide carried in the pack would otherwise become a suit to wear
    (tests/test_gear_usable.py's `test_a_bare_material_word_is_not_armour`). Refused, with
    this as the measurement."""
    eff = {"type": "skill_mod", "target": "survival", "amount": 2,
           "when": {"armour": {"weight": "medium"}}}
    assert forge_items.at_build(eff, "armour", "hide armour") is not None
    assert forge_items.at_build(eff, "armour", "leather") is None
    assert armour_mod.key_for("hide") == ("", "")


# --- masterwork by the book (plan §13.4) ----------------------------------------------------

def test_a_dragonhide_suit_is_masterwork_at_sound():
    """Inventory §0.7, measured: a dragonhide suit was `masterwork: False` without the Tool
    step; the book makes dragonhide (eel hide, angelskin, darkleaf) masterwork by its
    nature. Its ACP is one lighter for it, and an ordinary hide at Sound is not."""
    dragon = forge_items.build(suit("red-dragonhide", base="hide armour", q=1))
    assert dragon["masterwork"] and dragon["always_masterwork"]
    plain = forge_items.build(suit("plain-hide", base="hide armour", q=1))
    assert not plain["masterwork"]
    # Masterwork's -1 ACP (rule:masterwork): the dragonhide's ACP delta is +1, the plain
    # hide's is its own -2 alone.
    assert dragon["gear"]["acp"] == 1 and plain["gear"]["acp"] == -2


def test_a_masterwork_leather_suit_is_one_check_penalty_lighter():
    """Plan §13.4: masterwork armour is the book's -1 ACP (`rule:masterwork`), never
    scaled. The same deer-hide studded leather at Sound and at Superior: Superior's row is
    exactly one lighter (to the floor of 0)."""
    sound = forge_items.armour_row(ARMOUR["studded leather"],
                                   forge_items.build(suit("plain-hide", q=1,
                                                          base="studded leather")))
    superior = forge_items.armour_row(ARMOUR["studded leather"],
                                      forge_items.build(suit("plain-hide", q=3,
                                                             base="studded leather")))
    assert sound["acp"] == -1 - 2
    assert superior["acp"] == sound["acp"] + 1


def test_a_hide_the_book_limits_names_the_suit_it_refuses():
    """Eel hide is "leather, hide or studded leather" only (UE): a problem in the build,
    with the suits named, when a record puts it into a chain shirt; none on a hide suit."""
    bad = forge_items.build(suit("electric-eel-skin", base="chain shirt"))
    assert any("leather, hide armour or studded leather, not chain shirt" in p
               for p in bad["problems"]), bad["problems"]
    assert forge_items.build(suit("electric-eel-skin", base="hide armour"))["problems"] == []


# --- the stacking defect (plan §18.3) -------------------------------------------------------

def test_a_hides_ac_folds_into_the_armour_bonus():
    """Inventory §0.2, measured: hide AC typed `armour` never stacked with the suit's own
    armour bonus — a bulette-plate suit at +5 armour-typed AC came out as leather's 2, and
    13 hide specs did nothing on any suit. In the forge's build a hide's AC is `material`
    and folds INTO the suit's armour bonus: the plan's worked example (§13.3), Fine (x1.25)
    elk hide laminated once on hide armour, Leatherworker 2 — AC 4 + 3 = 7, one term."""
    rec = suit("elk-hide", base="hide armour", q=2, level=2)
    rec["pieces"]["body"]["passes"] = 1
    rec["pieces"]["fastenings"] = {"material": "deer-hide", "form": "lacing", "passes": 0}
    b = forge_items.build(rec)
    row = forge_items.armour_row(ARMOUR["hide armour"], b)
    assert row["ac"] == 7
    assert row["acp"] == -3 - 1          # the worked example's ACP line: -1
    assert row["max_dex"] == 4 + 1        # +1
    assert b["gear"]["hardness"] == 0     # -0.9, toward zero
    survival = [s for s in b["specs"] if s["target"] == "survival"]
    assert [s["amount"] for s in survival] == [3]
    assert not any(s["target"] == "ac" for s in forge_items.standing_specs(b)), \
        "the folded AC must not also ride as a second term"


# --- as_base: bulette leather (plan §14.5) --------------------------------------------------

def test_bulette_leather_has_studded_leathers_statistics_and_no_metal():
    """The source's bulette leather "has the same statistics as studded leather". Measured
    before: the catalogue gave bulette-plate +3 armour-typed AC on a `leather` suit (AC 2
    on the sheet). The suit takes the row's AC 3, max Dex 5, ACP -1, 15% failure and 20 lb,
    the build moves them (its own ACP -2), and it carries no metal: studded leather's
    steel studs are the ROW's, and lane A's note was that `item_tags` must not carry them
    across (the druid reads the metal tag)."""
    rec = suit("bulette-leather", base="leather")
    b = forge_items.build(rec)
    assert b["as_base"] == "studded leather" and b["problems"] == []
    row = forge_items.armour_row(ARMOUR["leather"], b)
    assert (row["ac"], row["max_dex"], row["acp"], row["asf"], row["lb"]) == \
        (3, 5, -1 - 2, 15, 20)
    assert not item_tags.has_material(rec, "material.metal")
    # Its hit points are studded leather's too: armour bonus 3 x 5, hardness of leather.
    got = object_numbers.numbers(rec["name"], rec)
    assert (got.hardness, got.hp_max) == (2, 15)


def test_as_base_naming_no_row_is_a_problem_not_a_crash():
    DOCS["bad-as-base"] = {"id": "bad-as-base", "name": "Bad", "kind": "hide",
                           "armour": [{"type": "as_base", "target": "bulette plate",
                                       "book": True}]}
    try:
        b = forge_items.build(suit("bad-as-base"))
    finally:
        del DOCS["bad-as-base"]
    assert b["as_base"] == "" and any("bulette plate" in p for p in b["problems"])


# --- a creature's own DR and resistance (owner's answer 6, 2026-10-08) -----------------------

def test_house_dr_on_a_hide_keeps_the_forge_maths():
    """Hand-written house DR on a material document is a house number, scaled like every
    other (the forge's §6.2). Measured: DR 1/silver on the body is 1 x 0.75 = 0 at Crude,
    1 at Sound, 2 at Flawless +1 (x2.0); as a lining (x0.5) it is 0 at every tier below
    Flawless +1."""
    def dr(q, **kw):
        got = by_type(forge_items.build(suit(q=q, **kw)), "damage_reduction")
        return [(s["amount"], s.get("bypass")) for s in got]

    assert dr(0, body="silver-house-hide") == []
    assert dr(1, body="silver-house-hide") == [(1, "silver")]
    assert dr(5, body="silver-house-hide") == [(2, "silver")]
    for q in range(0, 5):
        assert dr(q, body="plain-hide", lining="silver-house-hide") == [], q


def test_a_creatures_own_dr_applies_whole_once_and_never_from_a_lining():
    """The owner's "reduced DR" (2026-10-08): a creature's DR N/x gives its hide
    DR max(1, N/5)/x. Measured before this rule, the forge's maths SCALED it: a DR 1/silver
    hide body at Crude came out 0.75 -> 0, and as a lining always 0 — the owner's floor of 1
    rounded away. A `from_creature` effect is the beast's: whole, once, from the main piece
    at any quality and any number of Laminate passes; nothing from a lining."""
    for q in (0, 1, 4, 5):
        rec = suit("werewolf-pelt", q=q)
        rec["pieces"]["body"]["passes"] = 2
        b = forge_items.build(rec)
        assert [(s["amount"], s.get("bypass")) for s in by_type(b, "damage_reduction")] \
            == [(1, "silver")], q
        assert [s["amount"] for s in by_type(b, "resistance")] == [2], q
    lined = forge_items.build(suit("plain-hide", lining="werewolf-pelt", q=5))
    assert by_type(lined, "damage_reduction") == [] and by_type(lined, "resistance") == []


def test_a_generic_hide_reads_its_beasts_numbers_through_lane_cs_door(monkeypatch):
    """Contracts §4.1: a generic hide's inherited numbers are derived from the stock's
    `creature` on read (`harvest.inherited`, lane C), never stored. The piece carries the
    creature id; the build asks lane C and applies what comes back by the creature rule."""
    import sys
    import types

    fake = types.ModuleType("rules.harvest")
    fake.inherited = lambda creature: ([{"type": "resistance", "target": "fire", "amount": 2}]
                                       if creature == "hell-hound" else [])
    monkeypatch.setitem(sys.modules, "rules.harvest", fake)
    import rules

    monkeypatch.setattr(rules, "harvest", fake, raising=False)
    rec = suit("plain-hide", q=0)
    rec["pieces"]["body"]["creature"] = "hell-hound"
    b = forge_items.build(rec)
    got = by_type(b, "resistance")
    assert [(s["target"], s["amount"], s["from_creature"]) for s in got] == [("fire", 2, True)]
    assert got[0]["source"] == "creature:hell-hound"
    # The same beast in the lining gives nothing.
    rec = suit("plain-hide", lining="plain-hide")
    rec["pieces"]["lining"]["creature"] = "hell-hound"
    assert by_type(forge_items.build(rec), "resistance") == []


# --- worn goods (plan §13.6, §18.2) ---------------------------------------------------------

def test_a_worn_good_keeps_what_means_something_off_a_suit():
    """Plan §13.6: a cloak carries the hide's skills, saves and resistances; AC, ACP, max
    Dex and spell failure are dropped, there being no armour bonus to fold into. A
    winter-wolf cloak keeps cold resistance 2 and Stealth, and loses its AC and ACP. No
    masterwork ACP either: a cloak has no check penalty to lighten."""
    b = forge_items.build(suit("winter-wolf-pelt", gear="worn", base="cloak",
                               slot="shoulders", q=3))
    kinds = {(s["type"], s["target"]) for s in forge_items.roll_specs(b)}
    assert ("resistance", "cold") in kinds and ("skill_mod", "stealth") in kinds
    assert ("combat_mod", "ac") not in kinds
    assert b["gear"]["acp"] == 0 and b["masterwork"]
    assert forge_items.PIECES["worn"] == ("body", "lining")


def test_a_worn_goods_object_numbers_are_an_inch_of_its_hide():
    """Table 7-12 has no row for a cloak, so an inch of what its body is (leather: hardness
    2, 5 hit points), moved by its hide's own numbers — a dragonhide cloak's book hardness
    10 and 10 per inch (+8 and +5 from leather, plan §15). Read against steel's 30 the +5
    would have moved 5 hit points by none."""
    rec = suit("red-dragonhide", gear="worn", base="cloak", slot="shoulders")
    got = object_numbers.numbers(rec["name"], rec)
    assert (got.material, got.hardness, got.hp_max) == ("leather", 10, 10)
    plain = object_numbers.numbers("Wolf Cloak", suit("winter-wolf-pelt", gear="worn",
                                                      base="cloak", slot="shoulders",
                                                      rid="wolf-cloak"))
    assert (plain.hardness, plain.hp_max) == (2, 5)


# --- object immunity and object numbers (plan §15, §18.4) -----------------------------------

def test_a_red_dragonhide_suit_is_immune_to_fire_as_an_object():
    """Questions doc, 'Book versus catalogue' 1: eleven dragonhide entries gave the WEARER
    resistance 5; the book makes the ARMOUR immune to the dragon's energy and protects the
    wearer not at all. The build names the immunity; an Item told of it takes nothing from
    fire and full acid."""
    b = forge_items.build(suit("red-dragonhide", base="hide armour"))
    assert b["object_immunity"] == ["fire"]
    assert not by_type(b, "object_immunity"), "an object's immunity is never a roll term"
    item = Item(name="Red Dragonhide Armour", material="leather", hardness=10, hp_max=20)
    burnt = item.take_damage(40, "fire", immune=("fire",))
    assert burnt["taken"] == 0 and burnt["immune"] == "fire" and item.hp == 20
    eaten = item.take_damage(15, "acid", immune=("fire",))
    assert eaten["taken"] == 5 and item.hp == 15


def test_a_leather_suits_object_numbers_are_the_books():
    """CRB Table 7-12: armour has its armour bonus x 5 hit points and the hardness of what
    its body is (Table 7-13, leather 2). A leather suit 10 hp, hide armour 20, a dragonhide
    hide suit hardness 10 (book) and 40 hp (10 per inch against leather's 5: twice)."""
    leather = object_numbers.numbers("Test Suit", suit("plain-hide"))
    assert (leather.hardness, leather.hp_max) == (2, 10)
    hide = object_numbers.numbers("Test Suit", suit("plain-hide", base="hide armour"))
    assert (hide.hardness, hide.hp_max) == (2, 20)
    dragon = object_numbers.numbers("Test Suit", suit("red-dragonhide", base="hide armour"))
    assert (dragon.hardness, dragon.hp_max) == (10, 40)


def test_the_makers_level_is_read_under_either_key():
    """Contracts §4.2: `MAKER_KEYS == ("smith", "maker")`, read either. A Leatherworker 5's
    negatives are cut (x0.9^4 = 0.6561) whichever key the record keeps them under."""
    a = suit("plain-hide", q=1)
    a["smith"] = {"level": 5, "perks": {}}
    b = suit("plain-hide", q=1)
    del b["smith"]
    b["maker"] = {"level": 5, "perks": {}}
    assert forge_items.MAKER_KEYS == ("smith", "maker")
    assert forge_items.build(a)["multipliers"] == forge_items.build(b)["multipliers"]
    assert forge_items.build(b)["multipliers"]["negative_cut"] == 0.6561


def test_a_madu_is_a_leather_shield_with_its_own_object_numbers():
    """The madu (UE p.9): +1, ACP -2. Table 7-12 prints no row for it, so it is an inch of
    leather (hardness 2, 5 hit points) moved by its hide — before, a forged shield with no
    row took no number from its making at all."""
    rec = suit("red-dragonhide", gear="shield", base="madu", slot="shield", rid="madu")
    row = forge_items.armour_row(SHIELDS["madu"], forge_items.build(rec))
    assert (row["ac"], row["acp"]) == (1, -2 + 1)       # always masterwork: one lighter
    got = object_numbers.numbers("Madu", rec)
    assert (got.material, got.hardness, got.hp_max) == ("leather", 10, 10)
