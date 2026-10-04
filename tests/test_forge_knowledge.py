"""What a smith knows about each metal (docs/blacksmithing-revamp-plan.md §9; the API is
docs/blacksmithing-contracts.md §6, lane E).

Before this lane, discovery was herbs' alone: `herbknowledge.property_keys` reads
`Ingredient.pairs`, so a material document had **0 discoverable properties** (measured on
every material shape: a dict has no `pairs`), and nothing at the forge could be learned.
What is pinned here:

* a material's properties are one positional key per effect in `weapon`, `armour`,
  `working` and `quench_mark`, and an unknown one says nothing on the card;
* a metal's drawbacks are read off the spec by target, not by sign alone, so mithral's
  -10% spell failure is a benefit and a -5 hardness a drawback;
* assaying costs a sliver and ten minutes, reveals one benefit and one drawback, is
  easier for every known metal of the same kind (at most -4), and a reactive metal's own
  carrier effect lands for real through the engine (abysium sickens);
* one store: `Actor.herb_known`, keyed by material id, a form on its parent, surviving a
  save; and every name `rules/herbknowledge.py` had still works;
* smiths teach, libraries tell common knowledge, and smithing manuals are a goods table
  sold at the smiths' counters, bought, held and read like the herbal ones.

Lane C's `rules/materials.py` is built in parallel, so every material here comes through
a fake door stood in `sys.modules` — the suite passes with or without lane C merged.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from rules import goods, herbknowledge, knowledge, market
from rules import ingredients as ing_mod
from rules.sheet import Actor, from_dict, to_dict


# --- fixture materials, in contract §3's normalised shape ----------------------------------

def _mod(target, amount, **kw):
    return {"type": "combat_mod", "target": target, "amount": amount,
            "bonus_type": "material", **kw}


def _gear(target, amount, **kw):
    return {"type": "gear_mod", "target": target, "amount": amount, **kw}


def _trait(trait):
    return {"type": "working", "trait": trait}


def _doc(id, name, kind, tier, *, weapon=(), armour=(), working=(), mark=None, **kw):
    return {"id": id, "name": name, "kind": kind, "tier": tier, "form": "bar",
            "material": id, "pieces": {}, "weapon": list(weapon), "armour": list(armour),
            "working": list(working), "quench_mark": mark, "book": False, "price_gp": 1,
            "text": "", "biomes": [], "obtain": "bought", **kw}


IRON = _doc("testiron", "Testiron", "metal", "common",
            weapon=[_mod("damage", 2), _mod("attack", -2), _gear("hardness", 2)],
            armour=[_mod("ac", 2), _gear("acp", -2), _gear("hardness", 2)],
            working=[_trait("forgiving")])
BRONZE = _doc("testbronze", "Testbronze", "alloy", "common",
              weapon=[_mod("attack", 2), _mod("damage", -2), _gear("hardness", 1)],
              armour=[_mod("ac", 1), _gear("weight_pct", 10), _gear("hardness", 1)],
              working=[_trait("forgiving")])
MITHRAL = _doc("testmithral", "Testmithral", "metal", "rare",
               weapon=[{"type": "strikes_as", "target": "silver", "book": True},
                       _mod("attack", 2), _mod("damage", -2)],
               armour=[_gear("asf", -10, book=True), _gear("weight_pct", -50, book=True),
                       _gear("hardness", -5)],
               working=[_trait("easily_worked")])
SICKENS = {"type": "apply_condition", "target": "sickened", "trigger": "carried",
           "book": True}
ABYSIUM = _doc("testabysium", "Testabysium", "metal", "exotic",
               weapon=[_mod("damage", 2), SICKENS, _mod("attack", -2)],
               armour=[_mod("ac", 2), SICKENS, _gear("acp", -2)],
               working=[_trait("reactive")])
NOQUAL = _doc("testnoqual", "Testnoqual", "metal", "exotic",
              weapon=[_mod("damage", 2), _mod("attack", -2), _gear("hardness", 2)],
              armour=[_gear("asf", 20, book=True), _mod("ac", 2), _gear("acp", -2)],
              working=[_trait("reactive")])
CARRIED_SAFE = _doc("testlode", "Testlode", "metal", "uncommon",
                    weapon=[_mod("damage", 2), SICKENS, _mod("attack", -2)],
                    working=[_trait("forgiving")])
ORE = _doc("testore", "Testore", "ore", "common", form="ore",
           working=[_trait("slaggy"), _trait("forgiving")])
QUENCH = _doc("testbrine", "Testbrine", "quenchant", "common",
              working=[_trait("quench_sensitive"), _trait("clean_heat")],
              mark=_gear("hardness", 1))
FIXTURES = {d["id"]: d for d in (IRON, BRONZE, MITHRAL, ABYSIUM, NOQUAL, CARRIED_SAFE, ORE,
                                  QUENCH)}
FORMS = {"testmithral-fittings": "testmithral"}


@pytest.fixture
def door(monkeypatch):
    """A stand-in for lane C's `rules/materials.py` (contract §3), holding the fixtures."""
    fake = types.ModuleType("rules.materials")
    fake.get = lambda mid: FIXTURES.get(FORMS.get(mid, mid))
    fake.all = lambda: dict(FIXTURES)
    fake.of_kind = lambda kind: [d for d in FIXTURES.values() if d["kind"] == kind]
    fake.material_of = lambda mid: FORMS.get(mid, mid)
    fake.validate = lambda doc: []
    monkeypatch.setitem(sys.modules, "rules.materials", fake)
    return fake


def _pc():
    return Actor(name="Smith", ref="pc")


# --- properties --------------------------------------------------------------------------

def test_a_material_has_one_property_per_effect(door):
    """The defect: `herbknowledge.property_keys` read `Ingredient.pairs`, so every material
    document had 0 properties to discover. A structural metal has its 3 + 3 + working
    keys; a quenchant its working traits and its mark (contract §3)."""
    assert herbknowledge.property_keys(IRON) == ["w0", "w1", "w2", "a0", "a1", "a2", "t0"]
    assert knowledge.property_keys(IRON) == ["w0", "w1", "w2", "a0", "a1", "a2", "t0"]
    assert knowledge.property_keys(QUENCH) == ["t0", "t1", "q0"]
    assert knowledge.property_keys(ORE) == ["t0", "t1"]


def test_herb_keys_and_store_are_untouched_by_the_door(door):
    """A herb is still keyed p0.. and stored under its own id with a materials door in
    place: the door is asked about materials and nothing else."""
    herb = ing_mod.get("comfrey")
    pc = _pc()
    keys = knowledge.property_keys(herb)
    assert keys and all(k.startswith("p") for k in keys)
    herbknowledge.reveal(pc, "comfrey", keys[:1], "test")
    assert list(pc.herb_known) == ["comfrey"]
    assert herbknowledge.known_keys(pc, herb) == keys[:1]


def test_a_metals_drawback_is_read_by_target_not_by_sign():
    """`consumables.hurts` calls every negative `_mod` harm. Measured on mithral's book
    armour line: it reads -10% spell failure and -50% weight, two of the book's three
    benefits, as drawbacks, and would have had a teacher warn of them first. The
    classifier asks the target: lower is better for spell failure, weight, category and
    speed penalty; higher for hardness, max Dex and the (negative) check penalty."""
    from rules import consumables

    book = MITHRAL["armour"][:2]
    assert all(consumables.hurts(s) for s in book)  # the sign rule's wrong answer
    assert [knowledge.classify(s) for s in book] == [knowledge.BENEFIT] * 2
    assert knowledge.classify(_gear("hardness", -5)) == knowledge.DRAWBACK
    assert knowledge.classify(_gear("acp", -2)) == knowledge.DRAWBACK
    assert knowledge.classify(_gear("acp", 3)) == knowledge.BENEFIT
    assert knowledge.classify(_gear("max_dex", 2)) == knowledge.BENEFIT
    assert knowledge.classify(_gear("category", -1)) == knowledge.BENEFIT
    assert knowledge.classify(_gear("asf", 20)) == knowledge.DRAWBACK
    assert knowledge.classify(_gear("hardness", 0)) == knowledge.NEUTRAL
    assert knowledge.classify({"type": "strikes_as", "target": "cold_iron"}) == knowledge.BENEFIT
    assert knowledge.classify(_trait("slaggy")) == knowledge.DRAWBACK
    assert knowledge.classify(_trait("reactive")) == knowledge.DRAWBACK
    assert knowledge.classify(_trait("forgiving")) == knowledge.BENEFIT
    # A blow's rider lands on the foe: wyvern blood's poison is why you quench in it.
    rider = {"type": "save_gate", "target": "fort", "dc": 17, "trigger": "first_wound_daily",
             "on_failure": [{"type": "ability_damage", "target": "con", "dice": "1d4"}]}
    assert knowledge.classify(rider) == knowledge.BENEFIT
    assert knowledge.classify(SICKENS) == knowledge.DRAWBACK


def test_an_unknown_property_says_nothing_on_the_card(door):
    """Law 3 at the bench: an unknown row carries no words and no drawback flag, only
    which list it is in; a known row says what it does and how it was learned."""
    pc = _pc()
    knowledge.reveal(pc, "testiron", ["w0", "a1"], "test, day 1")
    rows = {r["key"]: r for r in knowledge.properties(pc, IRON)}
    assert rows["w0"]["known"] and rows["w0"]["text"] == knowledge.line(IRON["weapon"][0])
    assert rows["w0"]["drawback"] is False and rows["w0"]["group"] == "weapon"
    assert rows["a1"]["drawback"] is True and rows["a1"]["how"] == "test, day 1"
    for key in ("w1", "w2", "a0", "a2", "t0"):
        assert rows[key] == {"key": key, "known": False, "text": None, "drawback": None,
                             "how": None, "group": rows[key]["group"]}
    assert rows["t0"]["group"] == "working"
    assert "armour check penalty" in knowledge.danger_known(pc, IRON)


def test_every_new_type_has_words(monkeypatch):
    """The vocabulary's renderer (lane A) does not speak the smith's three types yet and
    answers with the bare type id: measured, `effectspec.render` of a gear_mod returned
    'gear_mod'. A card reading 'gear_mod' tells the player nothing, so knowledge has a
    line for each until it does. The exact fallback words are asked with the renderer
    held at its bare-id answer, so lane A's renderer landing does not fail this test."""
    from rules import effectspec

    for spec in (_gear("acp", -2), {"type": "strikes_as", "target": "cold_iron"},
                 _trait("forgiving")):
        said = knowledge.line(spec)
        assert said and said != spec["type"], said
    monkeypatch.setattr(effectspec, "render", lambda spec: str(spec.get("type")))
    assert knowledge.line(_gear("asf", -10)) == "-10% arcane spell failure"
    assert knowledge.line(_gear("hardness", 2)) == "+2 hardness"
    assert knowledge.line({"type": "strikes_as", "target": "cold_iron"}) == "Strikes as cold iron"
    assert knowledge.line(_trait("forgiving")).startswith("Forgiving: ")


# --- one store ---------------------------------------------------------------------------

def test_one_store_keyed_by_material_and_a_form_learns_its_parent(door):
    """Contract §6: no new Actor field — `herb_known` holds the smith's knowledge by
    material id. A form ("mithral fittings" at the leatherworker's) is stored on its
    parent, the owner's "one material, many shelves" ruling: learning it at one bench
    teaches it at every bench. And it survives a save."""
    pc = _pc()
    knowledge.reveal(pc, "testmithral-fittings", ["a0"], "test")
    assert "testmithral" in pc.herb_known and "testmithral-fittings" not in pc.herb_known
    assert knowledge.known_keys(pc, MITHRAL) == ["a0"]
    back = from_dict(to_dict(pc))
    assert knowledge.known_keys(back, MITHRAL) == ["a0"]


def test_the_herb_modules_names_all_still_answer():
    """The generalisation moved the machinery to rules/knowledge.py; a name dropped from
    rules/herbknowledge.py breaks the herb bench, the taste op, crafting and the brief
    (callers in seven files of gm/, play/ and rules/, counted 2026-10-03). Every public
    name it had
    is pinned, and the moved ones ARE the generic ones — one copy of each rule."""
    names = """SEEDED BENEFIT DRAWBACK NEUTRAL lore manuals property_keys classify is_drawback
        anatomy known_keys unknown_count reveal meet day_of properties danger_known carried
        stock_of met entry herbarium card taste_picks taste_condition study_dc study_skill
        study_waits study_order study teaches lesson_size lesson_order with_gates is_library
        common_knowledge manual_keys manual_named holds_manual is_herbalist homeland_biomes
        seed_homeland herbs_in seed_converted ensure_seeded brief_line""".split()
    missing = [n for n in names if not hasattr(herbknowledge, n)]
    assert not missing, missing
    for n in ("reveal", "known_keys", "classify", "properties", "study", "anatomy",
              "manual_keys", "holds_manual"):
        assert getattr(herbknowledge, n) is getattr(knowledge, n), n
    assert herbknowledge.taste_picks is knowledge.reveal_picks
    assert set(herbknowledge.manuals()) == set(knowledge.manuals(knowledge.HERBALIST))
    assert not set(herbknowledge.manuals()) & set(knowledge.manuals(knowledge.BLACKSMITH))


def test_without_lane_cs_door_nothing_breaks(monkeypatch):
    """rules/materials.py may not exist yet in this branch. With no door, a material id
    resolves to nothing and herbs answer as before; nothing raises."""
    monkeypatch.setitem(sys.modules, "rules.materials", None)  # import raises ImportError
    assert knowledge.material("iron") is None
    assert knowledge.ledger(_pc()) == []
    assert knowledge.manual_keys({"teaches": [{"material": "iron", "keys": "all"}]}) == {}
    herb = ing_mod.get("comfrey")
    assert knowledge.property_keys(herb) == herbknowledge.property_keys(herb)


# --- assay -------------------------------------------------------------------------------

def test_assaying_reveals_one_benefit_and_one_drawback(door):
    """Plan §16.1, lane 6. The owner's ruling: a sliver, ten minutes, one positive and
    one negative property. A second assay reveals the next unknown pair, never the same."""
    pc = _pc()
    first = knowledge.assay(pc, "testiron", 30, clock=0)
    assert first["success"] and first["minutes"] == 10
    assert first["cost"] == {"bars": 0.1}
    assert first["danger"] is None
    kinds = [knowledge.classify(knowledge.anatomy(IRON)["specs"][k]) for k in first["revealed"]]
    assert sorted(kinds) == [knowledge.BENEFIT, knowledge.DRAWBACK]
    second = knowledge.assay(pc, "testiron", 30, clock=0)
    assert len(second["revealed"]) == 2 and not set(second["revealed"]) & set(first["revealed"])
    assert pc.herb_known["testiron"]["how"][first["revealed"][0]] == "assayed, day 1"


def test_an_ore_costs_one_ore(door):
    """A sliver is one ore, not a tenth of one: ores are counted whole (plan §9.2)."""
    assert knowledge.assay(_pc(), "testore", 30, clock=0)["cost"] == {"ore": 1}


def test_a_missed_assay_teaches_nothing_but_the_sliver_is_spent(door):
    """A miss reveals nothing and still names its cost and its time: the sliver was cut.
    The metal is met, so the ledger lists it."""
    pc = _pc()
    got = knowledge.assay(pc, "testiron", 1, clock=0)
    assert not got["success"] and got["revealed"] == []
    assert got["cost"] == {"bars": 0.1} and got["minutes"] == 10
    assert [r["id"] for r in knowledge.ledger(pc)] == ["testiron"]


def test_assay_dc_falls_with_each_known_metal_of_the_kind(door):
    """Touchstone comparison (prior art §3.8): -1 for each OTHER known material of the
    same kind, at most -4. A known fuel says nothing of a metal; the metal being assayed
    is no reference for itself; a material met but unread is no needle."""
    pc = _pc()
    assert knowledge.assay_dc(MITHRAL, pc) == 20  # rare: 10 + 5 x 2
    knowledge.reveal(pc, "testmithral", ["w0"], "t")
    knowledge.reveal(pc, "testbrine", ["t0"], "t")       # a quenchant: another kind
    knowledge.reveal(pc, "testbronze", ["w0"], "t")      # an alloy: another kind
    knowledge.meet(pc, "testnoqual")                     # met, nothing known
    assert knowledge.assay_dc(MITHRAL, pc) == 20
    for mid in ("testiron", "testabysium", "testnoqual", "testlode"):
        knowledge.reveal(pc, mid, ["w0"], "t")
    assert knowledge.assay_dc(MITHRAL, pc) == 16
    assert knowledge.assay_dc(IRON, pc) == 6  # common 10, four other known metals
    # The cap: a fifth known metal cuts nothing more.
    FIXTURES["testextra"] = _doc("testextra", "Testextra", "metal", "common",
                                 weapon=[_mod("damage", 2)])
    try:
        knowledge.reveal(pc, "testextra", ["w0"], "t")
        assert knowledge.assay_dc(MITHRAL, pc) == 16
    finally:
        FIXTURES.pop("testextra")


def _scene():
    from rules.engine import Scene
    from rules.sheet import load_pc
    from tests._places import stand_on

    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    return s, pc


def test_assaying_abysium_sickens(door):
    """Plan §16.1, lane 6, and the owner's ruling: assay is safe except for reactive
    metals, where the danger is real. The metal's own carrier effect lands through the
    engine (law 2: an ActiveEffect from the condition op, not a flag written here), for
    the book's 1d4 hours after, and what was learned is the sickness itself."""
    from rules.activeeffect import ActiveEffect
    from rules.dice import Dice
    from rules.engine import Engine

    s, pc = _scene()
    got = knowledge.assay(pc, "testabysium", 40, clock=0)
    assert got["danger"]["type"] == "apply_condition"
    assert got["danger"]["target"] == "sickened"
    assert "trigger" not in got["danger"]
    assert got["danger"]["duration"] == {"amount": "1d4", "unit": "hour"}
    assert "w1" in got["revealed"]  # the landed drawback is the one learned
    outcomes = knowledge.apply_danger(Engine(s, Dice(seed=3)), pc, "testabysium",
                                      got["danger"])
    assert outcomes
    held = [e for e in pc.effects if isinstance(e, ActiveEffect) and e.key == "sickened"]
    assert held, pc.effects
    # `_op_condition` stamps the intent's `because` as the source and no `origin` (the
    # herb taste's paralysis is the same, measured 2026-10-03: origin ''), so the
    # provenance asked here is the source line and the condition op's own tell.
    assert held[0].source == "assaying Testabysium"
    assert any(o.op == "condition" and "sickened" in o.tell for o in outcomes)
    assert 1 * 600 <= held[0].rounds_left <= 4 * 600


def test_the_danger_is_the_handling_not_the_reading(door):
    """A missed assay of abysium still names the danger: the sliver was handled."""
    got = knowledge.assay(_pc(), "testabysium", 0, clock=0)
    assert not got["success"] and got["danger"]["target"] == "sickened"


def test_only_reactive_metals_are_dangerous_to_assay(door):
    """The owner: no danger 'except for reactive metals'. A carrier effect on a metal
    that is not reactive is felt by carrying it, not by a ten-minute assay; a reactive
    metal with no carrier effect has nothing to do to a handler."""
    assert knowledge.assay(_pc(), "testlode", 40, clock=0)["danger"] is None
    assert knowledge.assay(_pc(), "testnoqual", 40, clock=0)["danger"] is None
    assert knowledge.apply_danger(None, _pc(), "testnoqual", None) == []


def test_working_a_metal_reveals_its_working_traits(door):
    """Plan §9.2: any successful step reveals the working traits — you watched it
    behave. Nothing of what the finished item does is learned that way."""
    pc = _pc()
    assert knowledge.worked(pc, "testore", clock=0) == ["t0", "t1"]
    assert knowledge.worked(pc, "testore", clock=0) == []
    assert knowledge.worked(pc, "testiron", clock=0) == ["t0"]


# --- the ledger --------------------------------------------------------------------------

def test_the_ledger_lists_every_metal_met_and_carried(door):
    """The herbarium's counterpart (plan §9.4): every material met, known and unknown
    counts, by kind then name. Prospected ore is shelved by NAME (`_op_prospect` writes
    `Stock(base=pick.name)`), so a carried shelf entry counts by name as well as id."""
    from rules import crafting

    pc = _pc()
    knowledge.reveal(pc, "testiron", ["w0", "w1"], "t")
    pc.add_stock(crafting.Stock(base="Testore", tier="common", kind="ore",
                                craft="smithing"), 3)
    rows = knowledge.ledger(pc)
    assert [r["id"] for r in rows] == ["testiron", "testore"]
    iron, ore = rows
    assert (iron["known"], iron["total"], iron["carried"]) == (2, 7, 0)
    assert (ore["known"], ore["total"], ore["carried"]) == (0, 2, 3)
    assert iron["danger_known"] == knowledge.line(IRON["weapon"][1])
    assert ore["danger_known"] == ""


# --- teachers, libraries, manuals ---------------------------------------------------------

class _Person:
    def __init__(self, name, template="", notes=""):
        self.name, self.template, self.notes = name, template, notes


def test_smiths_teach_metals_and_healers_teach_herbs():
    """Plan §9.3: smiths in settlements teach, by the herbalism route keyed on their
    occupation. A smith knows metals and not herbs; a healer herbs and not metals.
    'goldsmith' names a metalworker though 'smith' alone does not match inside it."""
    smith_rec = {"life": {"work": "smith"}}
    healer_rec = {"life": {"work": "healer"}}
    anyone = _Person("Hal")
    assert knowledge.teaches(anyone, smith_rec, knowledge.BLACKSMITH)
    assert not knowledge.teaches(anyone, smith_rec, knowledge.HERBALIST)
    assert not herbknowledge.teaches(anyone, smith_rec)
    assert knowledge.teaches(anyone, healer_rec, knowledge.HERBALIST)
    assert not knowledge.teaches(anyone, healer_rec, knowledge.BLACKSMITH)
    assert knowledge.teaches(anyone, {"life": {"work": "smith-apprentice"}},
                             knowledge.BLACKSMITH)
    assert knowledge.teaches(_Person("Mira the goldsmith"), None, knowledge.BLACKSMITH)
    assert not knowledge.teaches(_Person("Mira the weaver"), None, knowledge.BLACKSMITH)
    # The occupation ids the rule names are the population table's own.
    occupations = json.loads(Path("content/people/occupations.json").read_text(encoding="utf-8"))
    ids = {o["id"] for o in occupations["occupations"]}
    assert set(knowledge.lore(knowledge.BLACKSMITH)["teacher"]["works"]) <= ids


def test_a_smith_warns_before_they_recommend(door):
    """The teacher's order is the herbalist's: drawbacks first. An indifferent smith
    teaches one property for the fee."""
    assert knowledge.lesson_order(_pc(), IRON)[0] == "w1"
    assert knowledge.lesson_size(Actor(name="Smith", ref="npc1"), knowledge.BLACKSMITH) == 1


def test_a_library_tells_a_common_metals_benefits_only(door):
    """What the world writes down: the benefits of a common or uncommon metal. A rare
    metal's secrets and every drawback stay unwritten, as for herbs."""
    assert knowledge.common_knowledge(IRON) == ["w0", "w2", "a0", "a2", "t0"]
    assert knowledge.common_knowledge(MITHRAL) == []
    place = types.SimpleNamespace(name="the guildhall", kind="hall", described_only=False)
    assert knowledge.is_library(place, knowledge.BLACKSMITH)
    assert not herbknowledge.is_library(place)


def _raw_material_ids() -> set[str]:
    ids = set()
    for path in Path("content/materials").glob("*-materials.json"):
        ids |= {m["id"] for m in json.loads(path.read_text(encoding="utf-8"))["materials"]}
    return ids


def test_every_smithing_manual_names_real_materials():
    """`manual_keys` skips an id the materials do not hold, silently, so a mistyped id is
    a book that teaches nothing and says nothing. Every row is checked against the
    shipped files (lane C keeps every id: contract §3)."""
    books = knowledge.manuals(knowledge.BLACKSMITH)
    assert len(books) >= 4
    ids = _raw_material_ids()
    words = {"all", "benefits", "drawbacks", "working"}
    for mid, m in books.items():
        assert m["teaches"], mid
        assert m["price_gp"] > 0 and m["hours"] > 0, mid
        for row in m["teaches"]:
            assert row["material"] in ids, (mid, row)
            assert row["keys"] in words or isinstance(row["keys"], list), (mid, row)


def test_a_manual_resolves_against_the_material_as_it_stands(door):
    """"drawbacks" means the drawbacks after a data edit moves them; "working" the
    working traits only; an unknown id is skipped, never invented."""
    book = {"teaches": [{"material": "testiron", "keys": "drawbacks"},
                        {"material": "testore", "keys": "working"},
                        {"material": "testmithral-fittings", "keys": ["w1", "zz"]},
                        {"material": "no-such-metal", "keys": "all"}]}
    assert knowledge.manual_keys(book) == {"testiron": ["w1", "a1"], "testore": ["t0", "t1"],
                                           "testmithral": ["w1"]}


def test_smithing_manuals_are_sold_where_smiths_are():
    """The 0.2.4 lesson (tests/test_herb_manuals_market.py): six herbal manuals existed
    and 0 were on any counter. The smithing manuals are a goods table, and the armorer's
    counter carries all of them as staples. Not the weaponsmith's: the trade window files
    that counter's every row under "weapons" (tests/test_i7_trade_window.py pins it, and
    putting the books there too failed it, measured 2026-10-03)."""
    books = set(knowledge.manuals(knowledge.BLACKSMITH))
    table = {g.key for g in goods.table_goods("smithing-manuals")}
    assert table == books
    on_counter = {g.key for g in market.staples_of(market.COUNTER_PREFIX + "armorer")}
    assert books <= on_counter
    for shop in ("weaponsmith", "alchemist"):
        theirs = {g.key for g in market.staples_of(market.COUNTER_PREFIX + shop)}
        assert not books & theirs, shop


def test_the_smiths_field_kit_is_a_good_a_smith_sells():
    """Lane G's `places.FIELD_KIT` names a carried good that did not exist: no row in
    GEAR, none in gear.json, so `has_field_kit` could never be true and the kit's
    common-and-uncommon-anywhere rule (plan §2) was unreachable. The kit is a GEAR row
    with a PROPOSED price and weight, a gear.json row saying what it does, and it is on
    the armorer's counter and every smithy's shelf; a bought one is carried under the
    kit's own name, which is what the carried-gear reader matches."""
    from rules import gear

    assert goods.GEAR["smith's field kit"] == {"name": "smith's field kit",
                                                "cost_gp": 15.0, "lb": 55}
    doc = json.loads(Path("content/rules/gear.json").read_text(encoding="utf-8"))
    kit = doc["items"]["smith's field kit"]
    for name in ("smithing kit", "field forge", "portable forge"):
        assert name in kit["names"]
    assert "PROPOSED" in kit["house_rule"]
    assert not gear.validate(doc)
    armorer = {g.key for g in market.staples_of(market.COUNTER_PREFIX + "armorer")}
    assert "smith's field kit" in armorer
    assert "smith's field kit" in goods.stocked_at("smithy")
    buyer = Actor(name="Smith", ref="pc")
    goods.deliver(None, buyer, goods.good("smith's field kit"), 1)
    carried = [c["name"] for c in gear.carried(buyer)]
    assert any("field kit" in str(n).lower() for n in carried), carried


def test_a_bought_smithing_manual_is_one_the_reader_holds():
    """`deliver` shelves a bought book under its name, and `holds_manual` must find it,
    or the book is paid for and can never be read."""
    manual = next(iter(knowledge.manuals(knowledge.BLACKSMITH).values()))
    good = next(g for g in goods.table_goods("smithing-manuals") if g.key == manual["id"])
    reader = Actor(name="Reader", ref="pc")
    assert not knowledge.holds_manual(reader, manual)
    goods.deliver(None, reader, good, 1)
    assert knowledge.holds_manual(reader, manual)
    assert knowledge.manual_named(manual["name"])["id"] == manual["id"]
    assert herbknowledge.manual_named(manual["name"]) is None
