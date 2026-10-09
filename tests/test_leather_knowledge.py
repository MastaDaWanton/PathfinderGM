"""What a leatherworker knows about each hide and each of the tanner's stores, and the
goods the craft is learned and worked with (docs/leatherworking-revamp-plan.md §16, §10;
docs/leatherworking-contracts.md §1 lane F; the owner's answers of 2026-10-08).

Measured before this lane, 2026-10-08, which is what these tests hold:

  * every one of the 140 leather materials answered to the SMITH's rule rows
    (`knowledge.craft_of` returned "blacksmith" for deer hide): a blacksmith taught it, a
    guildhall shelved it, and grading it was the forge's assay — a tenth of a BAR,
    compared against every known material of kind `hide`, so a known basilisk hide made a
    grizzly's easier to place;
  * nothing said what creature type a hide came from: the bestiary resolves 45 of the 71
    named hides' `from_creatures` and no dragon of any colour, so "−1 DC for each known
    hide of the same creature type" (plan §16) had nothing to compare;
  * four of the leather working traits (slow_tan, ceiling_down, fugitive, rancid — on 53
    of the 140 materials) read as BENEFITS, so a Grade of willow bark could not find the
    drawback it promises and showed its coarse tannage as a virtue;
  * `materials.properties` counted a hide's `shield` list and a consumable's `mark` and
    the knowledge store read neither (lane D's finding);
  * no goods row was named "leatherworker's field kit", so lane G's counter listed a kit
    nobody sold and `places.has_leather_kit` could only be true by a handover; the
    tannery's counter fell to the general-goods branch and sold a tent and rope;
  * there were no leatherworking manuals, and only the herb bench could read any manual.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import effectspec, gear, goods, knowledge, market, materials, places, worldclass
from rules.sheet import Actor


def _pc() -> Actor:
    return Actor(name="Tanner", ref="pc")


def _knows(actor, *ids):
    """Give the actor one known property of each material, as a Grade would."""
    for mid in ids:
        doc = knowledge.material(mid)
        assert doc is not None, mid
        knowledge.reveal(actor, mid, knowledge.property_keys(doc)[:1], "test")


# --- Grade (plan §16) -------------------------------------------------------------------------

def test_grade_reveals_one_benefit_and_one_drawback():
    """Plan §16 and §23.1 F: Grade reveals one positive and one negative property, costs a
    scrap (a quarter unit) and ten minutes, and has no danger. Before: it was the forge's
    assay, whose cost was a tenth of a bar ({"bars": 0.1}) of a hide."""
    pc = _pc()
    deer = knowledge.material("deer-hide")
    got = knowledge.grade(pc, "deer-hide", 30, clock=0)
    assert got["success"] and got["dc"] == 10
    kinds = knowledge.anatomy(deer)["kinds"]
    assert len(got["revealed"]) == 2
    assert sorted(kinds[k] for k in got["revealed"]) == [knowledge.BENEFIT,
                                                         knowledge.DRAWBACK]
    assert got["cost"] == {"units": 0.25}
    assert got["minutes"] == 10 and got["danger"] is None
    assert all(r["how"].startswith("graded") for r in knowledge.properties(pc, deer)
               if r["known"])
    # A second Grade takes the next of each side, never one already known.
    again = knowledge.grade(pc, "deer-hide", 30, clock=0)
    assert not set(again["revealed"]) & set(got["revealed"])


def test_grading_pays_study_mastery_per_property_and_nothing_for_nothing():
    """The owner, 2026-10-06: studying pays `worldclass.STUDY_MP` for each property it
    finds and 0 when nothing; the result says what is owed so every bench pays one number."""
    pc = _pc()
    hit = knowledge.grade(pc, "wolf-pelt", 40, clock=0)
    assert hit["mp"] == worldclass.STUDY_MP * len(hit["revealed"]) == 2
    miss = knowledge.grade(pc, "grizzly-hide", 1, clock=0)
    assert not miss["success"] and miss["revealed"] == [] and miss["mp"] == 0


def test_each_known_hide_of_the_same_creature_type_lowers_the_dc_by_one_at_most_four():
    """Plan §16, §23.1 F: −1 DC for each known hide of the SAME CREATURE TYPE, at most −4.
    Before: the forge's by-kind rule, under which a known basilisk hide (a magical beast)
    or a known owlbear made a grizzly's hide (an animal) easier to place."""
    pc = _pc()
    assert knowledge.assay_dc("grizzly-hide", pc) == 15          # uncommon: 10 + 5
    _knows(pc, "basilisk-hide", "owlbear-hide", "red-dragonhide", "oak-bark")
    assert knowledge.assay_dc("grizzly-hide", pc) == 15          # no animal known
    _knows(pc, "wolf-pelt")
    assert knowledge.assay_dc("grizzly-hide", pc) == 14
    _knows(pc, "dog-hide", "cat-pelt")
    assert knowledge.assay_dc("grizzly-hide", pc) == 12
    _knows(pc, "horse-hide", "goat-hide", "deer-hide")
    assert knowledge.assay_dc("grizzly-hide", pc) == 11          # six known: still −4
    # The hide being graded is not its own reference.
    _knows(pc, "grizzly-hide")
    assert knowledge.assay_dc("grizzly-hide", pc) == 11
    # The magical beasts help each other.
    assert knowledge.assay_dc("manticore-hide", pc) == 20 - 2
    got = knowledge.grade(pc, "grizzly-hide", 11, clock=0)
    assert got["success"] and got["dc"] == 11


def test_a_generic_hide_is_compared_under_the_creature_it_came_from():
    """A generic hide is every beast of its surface at once (plan §5.4), so on its own it
    has no type and no cut; graded with the creature its stock record names (contracts
    §4.1 `creature`), it is compared under that creature's type, read off the bestiary."""
    pc = _pc()
    _knows(pc, "wolf-pelt", "dog-hide")
    assert knowledge.hide_type("generic-fur-hide") is None
    assert knowledge.assay_dc("generic-fur-hide", pc) == 10
    assert knowledge.hide_type("generic-fur-hide", creature="wolf") == "animal"
    assert knowledge.assay_dc("generic-fur-hide", pc, creature="wolf") == 8
    got = knowledge.grade(pc, "generic-fur-hide", 8, clock=0, creature="wolf")
    assert got["success"] and got["dc"] == 8
    # A known generic hide is no reference for any one creature.
    other = _pc()
    _knows(other, "generic-fur-hide")
    assert knowledge.assay_dc("wolf-pelt", other) == 10


def test_every_named_hide_states_its_creature_type():
    """The bestiary resolved 45 of the 71 named hides' `from_creatures` (2026-10-08) and no
    dragonhide at all, so the type is the hide document's own stated fact, in the effect
    vocabulary's spelling. Generic hides state none: theirs is the creature's."""
    hides = [d for d in materials.all().values()
             if d["kind"] == "hide" and materials.is_leather(d)]
    assert len(hides) == 77
    for d in hides:
        if d["id"].startswith("generic-"):
            assert d.get("creature_type") is None, d["id"]
        else:
            assert d.get("creature_type") in effectspec.CREATURE_TYPES, d["id"]
            assert knowledge.hide_type(d) == d["creature_type"], d["id"]
    colours = [d for d in hides if d["id"].endswith("-dragonhide")]
    assert len(colours) == 11 and {d["creature_type"] for d in colours} == {"dragon"}


@pytest.mark.parametrize("raw,want", [
    ("magical beast", "magical-beast"), ("magical", "magical-beast"),
    ("advanced magical beast", "magical-beast"), ("monstrous", "monstrous-humanoid"),
    ("animal companion 5", "animal"), ("animal", "animal"), ("construc", "construct"),
    ("", None), ("bloodshot", None),
])
def test_bestiary_type_words_snap_to_the_vocabulary(raw, want):
    """core.json truncates types ("magical" on 107 blocks, "monstrous" on 55); the
    variant file writes "advanced magical beast". Each reads as the vocabulary's type."""
    assert knowledge._type_word(raw) == want


def test_grade_is_the_leatherworkers_and_never_bites():
    """Grade grades leather only (an iron bar is assayed at the forge); no hide bites back
    when graded (the owner's answer 10: a dangerous body is the harvest's second check)."""
    with pytest.raises(ValueError):
        knowledge.grade(_pc(), "iron", 30, clock=0)
    with pytest.raises(KeyError):
        knowledge.grade(_pc(), "no-such-hide", 30, clock=0)
    for d in materials.all().values():
        if materials.is_leather(d):
            assert knowledge.danger_of(d) is None, d["id"]


# --- the leather rule rows ------------------------------------------------------------------

def test_leather_materials_answer_to_the_leatherworkers_rows():
    """All 140 leather materials answered to the smith's rows before (craft_of). A tanner
    teaches hides; a smith does not; the tanner occupation is the population table's own."""
    leather = [d for d in materials.all().values() if materials.is_leather(d)]
    assert len(leather) == 140
    assert {knowledge.craft_of(d) for d in leather} == {knowledge.LEATHERWORKER}
    assert knowledge.craft_of(knowledge.material("iron")) == knowledge.BLACKSMITH
    rules = knowledge.lore(knowledge.LEATHERWORKER)
    assert rules["grade"]["comparison_max"] == 4 and rules["grade"]["scrap_units"] == 0.25
    tanner = {"life": {"work": "tanner"}}
    anyone = Actor(name="Hal", ref="npc1")
    assert knowledge.teaches(anyone, tanner, knowledge.LEATHERWORKER)
    assert not knowledge.teaches(anyone, {"life": {"work": "smith"}},
                                 knowledge.LEATHERWORKER)
    assert not knowledge.teaches(anyone, tanner, knowledge.BLACKSMITH)
    occ = json.loads(Path("content/people/occupations.json").read_text(encoding="utf-8"))
    leather_works = {o["id"] for o in occ["occupations"] if "leather" in (o.get("tags") or ())}
    assert set(rules["teacher"]["works"]) == leather_works
    # A library tells a common hide's benefits only.
    deer = knowledge.material("deer-hide")
    told = knowledge.common_knowledge(deer)
    kinds = knowledge.anatomy(deer)["kinds"]
    assert told and all(kinds[k] != knowledge.DRAWBACK for k in told)


def test_the_leather_drawback_traits_read_as_drawbacks():
    """slow_tan, ceiling_down, fugitive and rancid read as benefits on 53 of the 140
    leather materials before. Willow bark (ceiling_down, slow_tan) now has two drawbacks,
    and its Grade reveals one of them."""
    for trait in ("slow_tan", "ceiling_down", "fugitive", "rancid"):
        assert knowledge.classify({"type": "working", "trait": trait}) == knowledge.DRAWBACK
    for trait in ("fast_tan", "ceiling_up", "supple", "thick", "fast_colour"):
        assert knowledge.classify({"type": "working", "trait": trait}) == knowledge.BENEFIT
    willow = knowledge.material("willow-bark")
    got = knowledge.grade(_pc(), "willow-bark", 30, clock=0)
    kinds = knowledge.anatomy(willow)["kinds"]
    assert sorted(kinds[k] for k in got["revealed"]) == [knowledge.BENEFIT,
                                                         knowledge.DRAWBACK]


def test_the_shield_list_and_the_mark_are_properties():
    """`materials.properties` counted `shield` and `mark`; the store read neither. A hide's
    shield list is "s" keys and a consumable's mark one "k" key, with no existing key
    moving. The mark was skipped for a day while the owner held marks (open point 13,
    2026-10-08) and is read now they are kept as planned."""
    raw = {"id": "test-shield-hide", "name": "Test Hide", "kind": "hide", "tier": "common",
           "armour": [{"type": "gear_mod", "target": "acp", "amount": 1}],
           "shield": [{"type": "gear_mod", "target": "hardness", "amount": 1},
                      {"type": "gear_mod", "target": "hardness", "amount": -1}],
           "working": [{"type": "working", "trait": "forgiving"}],
           "mark": {"type": "combat_mod", "target": "ac", "amount": 1,
                    "bonus_type": "material"}}
    doc = materials.normalise(raw, materials.LEATHER_CATALOGUE)
    assert not hasattr(materials, "MARKS_HELD"), "the hold is gone, not merely off"
    assert knowledge.property_keys(doc) == ["a0", "s0", "s1", "t0", "k0"]
    rows = knowledge.properties(_pc(), doc)
    assert [r["group"] for r in rows] == ["armour", "shield", "shield", "working", "mark"]
    assert materials.properties(doc) == len(knowledge.property_keys(doc))


def test_every_leather_document_has_as_many_keys_as_the_door_counts():
    """One count of a material's properties, two readers: the door's and the store's. Every
    marked consumable included (11 of them, 2026-10-08): a mark the door counted and the
    store did not would be a property no Grade could ever find."""
    marked = 0
    for d in materials.all().values():
        if materials.is_leather(d):
            assert len(knowledge.property_keys(d)) == materials.properties(d), d["id"]
            marked += bool(d.get("mark"))
    assert marked >= 11


# --- manuals ------------------------------------------------------------------------------

def test_every_leatherworking_manual_names_real_materials_and_teaches():
    """`manual_keys` skips an unknown id silently; every row is checked against the
    shipped catalogue, and every manual teaches something as the data stands."""
    books = knowledge.manuals(knowledge.LEATHERWORKER)
    assert len(books) == 6
    shelf = materials.all()
    words = {"all", "benefits", "drawbacks", "working"}
    for mid, m in books.items():
        assert m["price_gp"] > 0 and m["hours"] > 0, mid
        for row in m["teaches"]:
            assert row["material"] in shelf, (mid, row)
            assert materials.is_leather(shelf[row["material"]]), (mid, row)
            assert row["keys"] in words, (mid, row)
        assert sum(len(k) for k in knowledge.manual_keys(m).values()) >= 8, mid


def test_the_leatherworkers_counter_sells_every_manual_and_a_bought_one_is_read_once():
    """The 0.2.4 defect (manuals in the data, none on a counter) not repeated: the
    leatherworker's counter, in every settlement, carries the table; a bought book is held,
    and its first reading pays the manual's mastery (plan §17.3, +5 once)."""
    books = set(knowledge.manuals(knowledge.LEATHERWORKER))
    table = {g.key for g in goods.table_goods("leatherworking-manuals")}
    assert table == books
    counter = {g.key for g in market.staples_of(market.COUNTER_PREFIX + "leatherworker")}
    assert books <= counter
    manual = knowledge.manuals(knowledge.LEATHERWORKER)["the-tanners-yard-book"]
    pc = _pc()
    assert not knowledge.holds_manual(pc, manual)
    good = next(g for g in goods.table_goods("leatherworking-manuals")
                if g.key == manual["id"])
    goods.deliver(None, pc, good, 1)
    assert knowledge.holds_manual(pc, manual)
    read = knowledge.read_manual(pc, manual, clock=0)
    assert read["first"] and read["mp"] == worldclass.MANUAL_MP == 5
    assert read["minutes"] == 240 and read["craft"] == knowledge.LEATHERWORKER
    deer = knowledge.material("deer-hide")
    assert knowledge.known_keys(pc, deer) == knowledge.property_keys(deer)
    again = knowledge.read_manual(pc, manual, clock=0)
    assert not again["first"] and again["mp"] == 0 and again["revealed"] == {}


# --- the field kit --------------------------------------------------------------------------

def test_the_leatherworkers_field_kit_is_a_good_priced_by_the_books_parts():
    """Lane G's counter named "leatherworker's field kit" and no goods row carried that
    name. The row is the book's parts: artisan's tools (CRB, 5 gp, 5 lb) and a common iron
    pot as the kettle (UE, 8 sp, 4 lb): 5.8 gp and 9 lb. Its name is lane G's exactly."""
    row = goods.GEAR[places.LEATHER_KIT]
    assert row == {"name": "leatherworker's field kit", "cost_gp": 5.8, "lb": 9}
    assert goods.good(places.LEATHER_KIT).price_gp == 5.8
    doc = json.loads(Path("content/rules/gear.json").read_text(encoding="utf-8"))
    kit = doc["items"]["leatherworker's field kit"]
    assert set(kit["names"]) == set(places.LEATHER_KIT_NAMES)
    assert "kettle" in kit["does"] and not gear.validate(doc)


def test_a_bought_field_kit_satisfies_the_kit_reader():
    """Bought off the leatherworker's counter (or the tannery's), the kit is carried under
    its own name, and `has_leather_kit` / `has_field_kit(craft="leatherworker")` find it.
    Before: the counter's `gear_of` dropped the kit (no GEAR row) and the tannery sold a
    tent, a crowbar and rope instead."""
    sold = market.gear_of(market.COUNTER_PREFIX + "leatherworker")
    assert places.LEATHER_KIT in sold
    on_counter = {g.key for g in market.staples_of(market.COUNTER_PREFIX + "leatherworker")}
    assert places.LEATHER_KIT in on_counter
    tannery = goods.stocked_at("tannery")
    assert places.LEATHER_KIT in tannery
    assert not {"tent", "crowbar", "rope"} & set(tannery)
    pc = _pc()
    assert not places.has_leather_kit(pc)
    assert not places.has_field_kit(pc, craft="leatherworker")
    goods.deliver(None, pc, goods.good(places.LEATHER_KIT), 1)
    assert places.has_leather_kit(pc) and places.has_field_kit(pc, craft="leatherworker")
    assert not places.has_field_kit(pc)          # it is not the smith's
    carried = [str(c["name"]).lower() for c in gear.carried(pc)]
    assert any("leatherworker's field kit" in n for n in carried), carried
