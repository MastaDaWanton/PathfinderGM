"""The magic layer (enchanting plan §6, contracts §3, lane B), on the REAL property table and
material documents.

Each test names the defect it prevents. The ones the plan lists (§21.1, lane B) are here,
re-stated where the owner's round 4 rulings changed the numbers: capacity is floor(Enchanter
level / 2) with no +10 ceiling, quality and Capacity perks adding on top.
"""
from __future__ import annotations

import copy
import json
import sys
import types

import pytest

from rules import effectspec, forge_items, magic_layer
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import _when_holds, load_pc


# --- builders --------------------------------------------------------------------------------

def forged(rid="cold-iron-longsword", head="cold-iron", base="longsword", q=3, **over):
    rec = {"id": rid, "name": rid.replace("-", " ").title(), "kind": "crafted",
           "craft": "blacksmith", "count": 1, "gear": "weapon", "base": base,
           "slot": "hands", "quality_index": q, "masterwork": q >= 3,
           "pieces": {"head": {"material": head, "passes": 1},
                      "haft": {"material": "ash-haft", "passes": 0},
                      "fittings": {"material": "brass-guard", "passes": 0}},
           "quench": None, "finish": [], "flaws": [],
           "smith": {"level": 3, "perks": {}}, "schema": 3}
    rec.update(over)
    return rec


def binder(level=10, knows=(), holds=(), perks=None, classes=()):
    return {"level": level, "perks": dict(perks or {}), "knows": set(knows),
            "holds": set(holds), "classes": set(classes)}


def bind(rec, adds, level=10, quality=3):
    return magic_layer.write(rec, adds, binding={"quality_index": quality, "level": level,
                                                 "perks": {}}, day=1)


def kesst(seed=5):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s.pc(), s, Engine(s, Dice(seed=seed))


def wear(e, item, actor="pc"):
    raw = [{"op": "wear", "actor": actor, "because": "test", "params": {"item": item}}]
    return e.run(e.validate(raw, origin="author:test")).outcomes[0]


def total(mods) -> int:
    return sum(m.value for m in mods)


# --- the layer rides on the forged record ------------------------------------------------------

def test_a_layered_forged_sword_keeps_its_pieces_its_sum_and_its_strikes():
    """The old enchanter wrote a NEW record that dropped the forged build — no pieces, no
    `strikes_as`, no `weapon` field — so `Actor.weapon` never found it (plan §1, measured
    on master e028885). The layer is one field on the same record: every forge number
    survives and the layer's are added beside them."""
    rec = forged()
    plain = forge_items.build(rec)
    layered = forge_items.build(bind(rec, {"enhancement": 1}))
    assert layered["sum"] == plain["sum"] and layered["gear"] == plain["gear"]
    assert set(plain["strikes_as"]) <= set(layered["strikes_as"])
    assert "cold_iron" in layered["strikes_as"] and "magic" in layered["strikes_as"]
    assert layered["specs"][:len(plain["specs"])] == plain["specs"]
    added = layered["specs"][len(plain["specs"]):]
    assert {(s["target"], s["amount"], s["bonus_type"]) for s in added} == {
        ("attack", 1, "enhancement"), ("damage", 1, "enhancement")}
    assert all(s["origin"] == "item:cold-iron-longsword" for s in added)


def test_layer_riders_wait_for_lane_cs_reader_instead_of_firing_on_every_foe():
    """Measured 2026-10-05: `Engine._item_riders` turns each `build["riders"]` document into
    intents through `consumables.coating_intents`, which never asks a `when` — so a bane
    rider merged there became a 2d6 damage intent against ANY defender, the note-only bane
    defect of plan §1 by another road (and its tell said "the property:bane"). The layer's
    riders stay under `build["magic"]["riders"]`, with the `when` lane C's reader asks."""
    from rules import consumables

    rec = forged(head="steel", rid="bane-sword")
    plain = forge_items.build(rec)
    bane = forge_items.build(bind(rec, {"enhancement": 1, "properties": [
        {"id": "bane", "choice": {"foe": "undead"}}]}))
    rider = next(r for r in bane["magic"]["riders"] if r["type"] == "damage")
    spec = {k: v for k, v in rider.items() if k not in ("trigger", "origin", "source", "book")}
    fired = consumables.coating_intents(consumables.Coating(item="x", specs=[spec]), "thug")
    assert [i["op"] for i in fired] == ["damage"], "the old reader ignores `when`: keep out"
    assert bane["riders"] == plain["riders"]
    assert rider["when"] == {"target": {"type": "undead"}}


@pytest.mark.parametrize("magic", [None, {}, "absent"])
def test_a_record_with_no_layer_builds_byte_for_byte_as_before(magic):
    """Every forged item in every save has no layer. Its build must not change by a byte
    (contracts §3.2): the same JSON with the field absent, null or empty, and no "magic"
    key in the build."""
    rec = forged()
    base = json.dumps(forge_items.build(rec), sort_keys=True)
    other = dict(rec)
    if magic != "absent":
        other["magic"] = magic
    built = forge_items.build(other)
    assert "magic" not in built
    assert json.dumps(built, sort_keys=True) == base


def test_a_stock_item_with_no_layer_round_trips_byte_for_byte():
    """`ForgedStock.as_dict` writes the record back exactly; the layer must add no key to a
    record that has none, or every old save would rewrite itself on the next load."""
    from rules.sheet import _stock

    rec = forged()
    d = forge_items.stock_item(rec).as_dict()
    assert "magic" not in d
    again = _stock({"k": json.loads(json.dumps(d))})["k"].as_dict()
    assert json.dumps(again, sort_keys=True) == json.dumps(d, sort_keys=True)
    layered = forge_items.stock_item(bind(rec, {"enhancement": 2})).as_dict()
    back = _stock({"k": json.loads(json.dumps(layered))})["k"].as_dict()
    assert back["magic"] == layered["magic"] and back["magic"]["enhancement"] == 2


def test_a_plain_stock_forge_item_carries_its_stock_layer_into_the_build():
    """The bench keeps a finished forge item as a plain `Stock` with `forge.*` tags, and
    `blacksmith.record` rebuilds its record from tags that know nothing of magic. Lane G's
    `Stock.magic` holds the layer; `record_of` must carry it, or the layer is on the shelf
    and in no build — the dropped-build defect again."""
    from rules import blacksmith as bs

    w = bs.Work(form="item", material="steel", shape="longsword", gear="weapon", quality=3,
                pieces={"head": {"material": "steel", "passes": 0},
                        "haft": {"material": "ash-haft", "passes": 0}},
                smith={"level": 2, "perks": {}}, tier="common")
    w.name = bs.work_name(w)
    stock = bs.to_stock(w)
    assert "magic" not in forge_items.build(forge_items.record_of(stock))
    stock.magic = bind(forge_items.record_of(stock), {"enhancement": 1})["magic"]
    built = forge_items.build(forge_items.record_of(stock))
    assert built["magic"]["enhancement"] == 1 and "magic" in built["strikes_as"]


def test_write_and_strip_are_pure_and_unbind_gives_the_smiths_item_back():
    """Unbind (plan §13): the layer comes off whole and the smith's item is what it was. A
    writer that mutated its argument would enchant the shelf copy and the bench's preview
    at once."""
    rec = forged()
    snapshot = copy.deepcopy(rec)
    layered = bind(rec, {"enhancement": 1, "properties": [{"id": "flaming"}]})
    assert rec == snapshot
    bare, lay = magic_layer.strip(layered)
    assert bare == snapshot and lay["enhancement"] == 1
    assert json.dumps(forge_items.build(bare), sort_keys=True) == \
        json.dumps(forge_items.build(rec), sort_keys=True)


def test_the_record_stores_ids_and_choices_never_a_number_it_computed():
    """The read-live rule (forge contracts §4): a stored price or bonus would never see a
    corrected property document."""
    rec = bind(forged(), {"enhancement": 1, "properties": [
        {"id": "bane", "choice": {"foe": "undead"}, "essence": "bane-essence"}]})
    m = rec["magic"]
    assert m["properties"] == [{"id": "bane", "essence": "bane-essence",
                                "choice": {"foe": "undead"}}]
    assert set(m) <= {"schema", "enhancement", "properties", "flat", "powers", "binding",
                      "curse", "known", "uses", "made_day", "worked_day"}


# --- capacity: the owner's round 4 ruling -------------------------------------------------------

@pytest.mark.parametrize("level,q,perks,expected", [
    (20, 3, 0, 10),          # the owner's example: Enchanter 20 = +10
    (30, 3, 0, 15),          # ... and Enchanter 30 = +15: no +10 ceiling
    (1, 3, 0, 1),            # floor(1 / 2) is 0; the owner's round 7 minimum makes it +1
    (7, 3, 0, 3),
    (10, 4, 0, 6),           # Flawless: one step above Superior
    (10, 5, 0, 7),           # Flawless +1: two
    (10, 3, 2, 7),           # two Capacity perks
    (30, 6, 3, 21),          # nothing stops it
])
def test_capacity_is_half_the_enchanter_level_with_quality_and_perks_on_top(level, q, perks,
                                                                           expected):
    """Owner, round 4 Q1: "floor(Enchanter level / 2) worth of enhancement-equivalent bonus,
    with no +10 ceiling ... the smith's quality adds a little more room on top". It
    replaced the plan's Superior +8 / Flawless +9 / +10 cap, which this would have held at
    10 for every row above."""
    cap = magic_layer.capacity(forged(q=q), binder_level=level, binder_perks=perks)
    assert cap["bonus"] == expected and cap["cap"] is None


def test_capacity_refuses_one_past_and_a_better_vessel_makes_room():
    """Plan §21.1's pin, at the owner's numbers: Enchanter 16 holds +8 on a Superior
    vessel, so a +9 working is refused with the numbers named; the same working on a
    Flawless vessel fits."""
    adds = {"enhancement": 5, "properties": [{"id": "flaming-burst"}, {"id": "keen"},
                                             {"id": "bane", "choice": {"foe": "undead"}}]}
    superior = magic_layer.plan(forged(q=3), adds, binder=binder(16))
    assert superior["total_bonus"] == 9 and not superior["ok"]
    assert any("Enchanter 16 holds +8" in p and "+9" in p for p in superior["problems"])
    flawless = magic_layer.plan(forged(q=4), adds, binder=binder(16))
    assert flawless["ok"], flawless["problems"]


def test_past_the_books_ten_is_allowed_and_priced_by_the_square():
    """No +10 ceiling (owner): an Enchanter 30 lays +15 on one sword. The price stays the
    book's formula, 15² × 2,000 gp, never a cap."""
    adds = {"enhancement": 5, "properties": [
        {"id": "vorpal"}, {"id": "speed"}, {"id": "flaming-burst"}]}
    p = magic_layer.plan(forged(q=3), adds, binder=binder(30))
    assert p["ok"], p["problems"]
    assert p["total_bonus"] == 15
    assert p["price"]["market_gp"] == 15 ** 2 * 2000


def test_the_books_five_enhancement_limit_is_kept():
    """The owner lifted the +10 total and nothing else; the book's "+1 to +5" enhancement
    stays, so a sixth step is refused and the room goes to properties."""
    p = magic_layer.plan(forged(), {"enhancement": 6}, binder=binder(30))
    assert any("+5 is the book's highest" in x for x in p["problems"])


def test_a_property_needs_a_plus_one_first():
    """CRB: "a weapon with a special ability must also have at least a +1 enhancement
    bonus". With it in the same working, it binds."""
    alone = magic_layer.plan(forged(), {"properties": [{"id": "flaming"}]}, binder=binder())
    assert any("at least a +1" in p for p in alone["problems"])
    both = magic_layer.plan(forged(), {"enhancement": 1, "properties": [{"id": "flaming"}]},
                            binder=binder())
    assert both["ok"], both["problems"]


def test_only_a_masterwork_weapon_takes_magic():
    """CRB: "only a masterwork weapon can become a magic weapon". A Fine (quality 2) blade
    is refused by its quality's name."""
    p = magic_layer.plan(forged(q=2), {"enhancement": 1}, binder=binder())
    assert any("Only a masterwork" in x and "Fine" in x for x in p["problems"])


# --- the book's prices, motes and time ----------------------------------------------------------

def test_upgrading_a_plus_one_to_plus_one_flaming_costs_the_books_difference():
    """CRB p. 553: "the same as if the item was not magical, less the value of the original
    item". +1 (2,000) to +1 flaming (+2, 8,000) is 6,000 market, 3,000 to make, 30 motes;
    48 hours at 8 per 1,000 gp of the increment."""
    sword = bind(forged(head="steel", rid="steel-sword"), {"enhancement": 1})
    p = magic_layer.plan(sword, {"properties": [{"id": "flaming"}]},
                         binder=binder(knows={"fireball"}))
    assert p["price"]["market_gp"] == 6000 and p["price"]["making_gp"] == 3000
    assert p["price"]["motes"] == 30 and p["price"]["hours"] == 48
    assert p["price"]["days"] == 6


def test_cold_iron_charges_twenty_motes_on_its_first_enhancement_only():
    """CRB: adding magic to a cold iron weapon "increases its price by 2,000 gp ... the
    first time the item is enhanced, not once per ability added" — 20 motes (owner Q9).
    The catalogue's cold iron carries no `enchant_surcharge_gp`, so the book's number was
    unread until this layer."""
    first = magic_layer.plan(forged(), {"enhancement": 1}, binder=binder())
    assert first["price"]["motes"] == 10 + 20
    assert any("Cold Iron" in s["why"] and s["motes"] == 20
               for s in first["price"]["surcharges"])
    again = magic_layer.plan(bind(forged(), {"enhancement": 1}), {"enhancement": 1},
                             binder=binder())
    assert again["price"]["surcharges"] == [] and again["price"]["motes"] == 30


def test_noqual_adds_fifty_motes_from_its_own_document():
    """`enchant_surcharge_gp: 5000` on noqual (blacksmith-materials.json) had no reader
    (plan §1). "Any magic item incorporating noqual": fittings count, not only the head."""
    rec = forged(rid="noqual-guarded", head="steel")
    rec["pieces"]["fittings"] = {"material": "noqual", "passes": 0}
    p = magic_layer.plan(rec, {"enhancement": 1}, binder=binder())
    assert any(s["motes"] == 50 for s in p["price"]["surcharges"])
    assert p["price"]["motes"] == 10 + 50


def test_hurrying_halves_the_time_for_five_more_dc():
    """CRB: the creator may hurry, "reducing the time ... by half", at +5 DC."""
    slow = magic_layer.plan(forged(), {"enhancement": 2}, binder=binder())
    fast = magic_layer.plan(forged(), {"enhancement": 2}, binder=binder(), hurry=True)
    assert fast["price"]["hours"] * 2 == slow["price"]["hours"]
    assert fast["dc"] == slow["dc"] + 5


def test_a_missing_spell_or_level_is_five_dc_never_a_refusal():
    """Owner round 1 and Q4: each unmet prerequisite is +5 DC. The plan's worked example
    (§6.5): +1 flaming is DC 15; without Flame Blade known or carried +5, and an Enchanter
    2 below caster level 10 another +5, so DC 25 — refused never. A carried potion counts
    as known (`holds`)."""
    rec = forged(q=4)
    low = magic_layer.plan(rec, {"enhancement": 1, "properties": [{"id": "flaming"}]},
                           binder=binder(2))
    assert low["dc"] == 25 and not any("spell" in p.lower() for p in low["problems"])
    able = magic_layer.plan(rec, {"enhancement": 1, "properties": [{"id": "flaming"}]},
                            binder=binder(10, holds={"flame-blade"}))
    assert able["dc"] == 15


# --- what the layer does ------------------------------------------------------------------------

def test_masterworks_plus_one_does_not_stack_with_a_plus_one_enhancement():
    """CRB masterwork: "the masterwork bonus does not stack with an enhancement bonus". A +1
    layer on a Superior sword adds +1 damage and NO attack (both are typed enhancement and
    `dice.stack` takes the best); +2 adds one more to attack."""
    pc, s, e = kesst()
    plain = forged(rid="plain-sword", head="steel")
    one = bind(forged(rid="one-sword", head="steel"), {"enhancement": 1})
    two = bind(forged(rid="two-sword", head="steel"), {"enhancement": 2})
    for r in (plain, one, two):
        pc.add_stock(forge_items.stock_item(r))
    atk = {k: total(pc.attack_modifiers(k)) for k in ("plain-sword", "one-sword", "two-sword")}
    dmg = {k: total(pc.damage_modifiers(k)) for k in ("plain-sword", "one-sword", "two-sword")}
    assert atk["one-sword"] == atk["plain-sword"] and atk["two-sword"] == atk["plain-sword"] + 1
    assert dmg["one-sword"] == dmg["plain-sword"] + 1 and dmg["two-sword"] == dmg["plain-sword"] + 2


def test_an_armour_enhancement_folds_into_the_suits_armour_bonus():
    """Plan §6.7: on armour the +N is an enhancement to the ARMOUR bonus, folded into the
    suit's row as `armour_row` folds a material's AC — never a second armour term that
    `dice.stack` would swallow beside the suit's own."""
    pc, s, e = kesst()
    plate = forge_items.record_for_base("breastplate", gear="armour", item_id="bp")
    plus2 = bind(dict(plate, id="bp2", name="Bp2"), {"enhancement": 2})
    base_ac = forge_items.armour_row({"ac": 6}, forge_items.build(plate))["ac"]
    assert forge_items.armour_row({"ac": 6}, forge_items.build(plus2))["ac"] == base_ac + 2
    assert not any(sp.get("target") == "ac" for sp in
                   forge_items.standing_specs(forge_items.build(plus2)))


def test_bane_raises_the_enhancement_only_against_its_foe():
    """The old catalogue's bane put +2 and +2d6 in a note "against the designated foe", so
    any reader would have applied them to everybody (plan §1). Bound against undead, the
    raise answers a skeleton and not a thug, through the existing `_when_holds`, and the DR
    traits follow the raised number (owner Q8): +1 bane is +3 against the dead, enough for
    DR/silver and DR/cold iron."""
    s = Scene(location_id=None)
    skeleton = instantiate("skeleton", scene=s, name="bones")
    thug = instantiate("thug", scene=s, name="thug")
    lay = magic_layer.layer(bind(forged(head="steel", rid="bane-sword"), {
        "enhancement": 1, "properties": [{"id": "bane", "choice": {"foe": "undead"}}]}))

    def holds(who):
        return lambda when: _when_holds(when, {"target_actor": who})

    assert magic_layer.raised_enhancement(lay, holds(skeleton)) == 3
    assert magic_layer.raised_enhancement(lay, holds(thug)) == 1
    assert {"silver", "cold_iron"} <= set(magic_layer.strikes_as_against(lay, holds(skeleton)))
    assert magic_layer.strikes_as_against(lay, holds(thug)) == ("magic",)
    riders = [r for r in lay["riders"] if r["type"] == "damage"]
    assert riders and all(r["when"] == {"target": {"type": "undead"}} for r in riders)


def test_bane_with_no_foe_is_refused_at_plan_and_write():
    """Lane A's rule carried through the layer: a property that asks a question is
    answered before it is bound, so no record can carry an unanswered bane."""
    p = magic_layer.plan(forged(), {"enhancement": 1, "properties": [{"id": "bane"}]},
                         binder=binder())
    assert any("choose its foe" in x for x in p["problems"])
    with pytest.raises(ValueError):
        magic_layer.write(forged(), {"properties": [{"id": "bane"}]}, binding={})


def test_a_property_goes_only_on_the_vessel_the_book_allows():
    """Each ability's own restriction sentence (lane A's `requires`): keen needs piercing
    or slashing, so not a club; distance is for a ranged weapon; shadow is armour's."""
    club = forge_items.record_for_base("club", gear="weapon")
    keen = magic_layer.plan(club, {"enhancement": 1, "properties": [{"id": "keen"}]},
                            binder=binder())
    assert any("piercing or slashing" in p for p in keen["problems"])
    far = magic_layer.plan(forged(), {"enhancement": 1, "properties": [{"id": "distance"}]},
                           binder=binder())
    assert any("ranged weapon" in p for p in far["problems"])
    shade = magic_layer.plan(forged(), {"enhancement": 1, "flat": [{"id": "shadow"}]},
                             binder=binder())
    assert any("not a weapon" in p for p in shade["problems"])


def test_every_document_says_which_item_and_which_property_put_it_there():
    """Law 2 and stage 8's provenance: what the layer adds carries `origin: item:<id>`
    and `source: property:<id>`, so removing the item removes every contribution and a
    tell can name the property."""
    lay = magic_layer.layer(bind(forged(head="steel", rid="s"), {
        "enhancement": 2, "properties": [{"id": "flaming"}, {"id": "keen"}]}))
    docs = lay["specs"] + lay["riders"]
    assert docs and all(d["origin"] == "item:s" for d in docs)
    assert {d["source"] for d in docs} == {"enhancement", "property:flaming", "property:keen"}
    assert lay["tags"] == ["property.flaming", "property.keen"]
    assert lay["aura"] == "moderate" and lay["caster_level"] == 10


@pytest.mark.parametrize("cl,word", [(0, None), (5, "faint"), (6, "moderate"), (12, "strong"),
                                     (20, "strong"), (21, "overwhelming")])
def test_aura_by_caster_level(cl, word):
    """CRB detect magic: faint 5th or lower, moderate 6th-11th, strong 12th-20th,
    overwhelming 21st+."""
    assert magic_layer.aura(cl) == word


# --- rings and wondrous items --------------------------------------------------------------------

def test_a_ring_of_protection_is_held_by_the_same_budget_at_the_books_price():
    """Rings take no enhancement; their room is read through the weapon table's price (a
    +3 deflection ring, 18,000 gp, is +3). Enchanter 6 holds it; Enchanter 4 does not. The
    creator's level is the book's "three times the bonus" (+5 DC below it), the DC 5 + the
    ring's printed CL 5."""
    ring = {"id": "band", "name": "Silver band", "gear": "ring", "slot": "ring",
            "quality_index": 2}
    adds = {"properties": [{"id": "deflection", "choice": {"bonus": 3}}]}
    ok = magic_layer.plan(ring, adds, binder=binder(9, knows={"shield-of-faith"}))
    assert ok["ok"], ok["problems"]
    assert ok["price"]["market_gp"] == 18000 and ok["dc"] == 10
    short = magic_layer.plan(ring, adds, binder=binder(4))
    assert any("Enchanter 4 holds +2" in p for p in short["problems"])
    assert magic_layer.plan(ring, {"enhancement": 1}, binder=binder(9))["problems"]
    lay = magic_layer.layer(magic_layer.write(ring, adds, binding={"level": 9}))
    assert [(d["type"], d["amount"], d["bonus_type"]) for d in lay["specs"]] == [
        ("combat_mod", 3, "deflection")]


def test_a_cloak_property_goes_on_the_shoulders_only():
    """A scaled wondrous property names its body slot (lane A's `slots`)."""
    belt = {"id": "belt", "name": "Belt", "gear": "wondrous", "slot": "belt"}
    p = magic_layer.plan(belt, {"properties": [{"id": "resistance", "choice": {"bonus": 1}}]},
                         binder=binder())
    assert any("shoulders" in x for x in p["problems"])


def test_a_catalogue_recipe_lays_its_own_effects():
    """A catalogue item is a known recipe (owner round 3); its effects reach the layer
    through the same buckets, stamped with the recipe."""
    ring = {"id": "r", "name": "Ring", "gear": "ring", "slot": "ring"}
    lay = magic_layer.layer(magic_layer.write(ring, {"powers": [{"recipe":
                                                               "mi-ring-protection-1"}]},
                                              binding={"level": 2}))
    assert [(d["amount"], d["source"]) for d in lay["specs"]] == [
        (1, "recipe:mi-ring-protection-1")]


# --- house top-ups and the curse seam ------------------------------------------------------------

def test_an_essences_house_top_up_scales_with_binding_quality(monkeypatch):
    """Plan §6.7: house numbers × the forge's quality ladder; book numbers never scale."""
    from rules import materials

    house = [{"type": "combat_mod", "target": "damage", "amount": 2, "bonus_type": "untyped",
              "house": True}]
    monkeypatch.setattr(materials, "essences",
                        lambda: {"ember": {"house": house}}, raising=False)
    rec = bind(forged(head="steel", rid="h"),
               {"enhancement": 1, "properties": [{"id": "flaming", "essence": "ember"}]},
               quality=4)
    lay = magic_layer.layer(rec)
    top = [d for d in lay["specs"] if d.get("source") == "essence:ember"]
    assert [d["amount"] for d in top] == [3]           # 2 × 1.75, toward zero
    assert [d["dice"] for d in lay["riders"]] == ["1d6"]  # the book's flame, unscaled


def test_a_curse_changes_the_layer_through_lane_fs_seam_and_never_shows_itself(monkeypatch):
    """Owner round 4 Q2: the player knows it is flawed, not which curse. `layer` applies
    `curses.documents` (here a stand-in: a delusion suppresses everything); the card's view
    (`believed=True`) is the maker's intent, and the curse's id is in neither output."""
    fake = types.ModuleType("rules.curses")
    fake.documents = lambda curse, lay: {"suppress": True}
    monkeypatch.setitem(sys.modules, "rules.curses", fake)
    import rules

    monkeypatch.setattr(rules, "curses", fake, raising=False)
    rec = magic_layer.write(forged(head="steel", rid="c"), {"enhancement": 1},
                            binding={"level": 4}, curse={"row": "delusion",
                                                         "id": "curse-secret-17"})
    true = magic_layer.layer(rec)
    seen = magic_layer.layer(rec, believed=True)
    assert true["specs"] == [] and true["strikes_as"] == []
    assert len(seen["specs"]) == 2 and "magic" in seen["strikes_as"]
    assert "curse-secret-17" not in json.dumps(true) + json.dumps(seen)
    assert rec["magic"]["known"] == {"intent": True, "curse": False, "how": "made"}


def test_the_property_table_is_read_live_not_copied():
    """A corrected property document must reach every item already made (the read-live
    rule): the layer binds from `effectspec.property` at read time."""
    rec = bind(forged(head="steel", rid="live"), {"enhancement": 1,
                                                  "properties": [{"id": "flaming"}]})
    before = magic_layer.layer(rec)["riders"][0]["dice"]
    prop = effectspec.property("flaming")
    old = prop["documents"][0]["dice"]
    try:
        prop["documents"][0]["dice"] = "1d8"
        assert magic_layer.layer(rec)["riders"][0]["dice"] == "1d8"
    finally:
        prop["documents"][0]["dice"] = old
    assert before == "1d6"


# --- record_for_base ----------------------------------------------------------------------------

def test_a_bought_masterwork_item_gets_a_record_that_builds_as_the_books_item():
    """Plan §6.2: a bought or found masterwork item needs a record before it can carry a
    layer. Its default pieces are named (the card, the metal tag) and `plain`, so the
    forge's house numbers are not summed onto a shop's longsword: its build is masterwork's
    +1 attack and nothing else."""
    rec = forge_items.record_for_base("longsword", gear="weapon")
    assert forge_items.is_forged(rec) and rec["masterwork"] and rec["base"] == "longsword"
    b = forge_items.build(rec)
    assert [(s["target"], s["amount"]) for s in b["specs"]] == [("attack", 1)]
    assert b["sum"] == [] and b["problems"] == []
    with pytest.raises(ValueError):
        forge_items.record_for_base("a stern look", gear="weapon")
    with pytest.raises(ValueError):
        forge_items.record_for_base("longsword", gear="armour")
