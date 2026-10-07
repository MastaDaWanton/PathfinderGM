"""The alchemy data pass (alchemy plan §5 and §16.9, lane D): the shipped materials, the 44
potions and the hybrid herbs, held to what they must add up to.

Measured before the pass (plan §5.1, on 3bbd361): of the 138 alchemist materials 70 had no
effect at all, 5 were narrative only and none carried three properties; there was no
working layer, no essence a formula could key on, no route a product could deliver by;
quicksilver's and lead dust's "to the handler" damage landed on whoever drank the product;
sunmetal's "harms only undead" sat in an unread note; and 20 of the 44 potions' lines were
narrative. Each test below names the defect it holds shut.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from rules import effectspec, knowledge, market, materials, pricing

ROOT = Path(__file__).resolve().parents[1]


def _raw() -> list[dict]:
    return json.loads((ROOT / "content/materials/alchemist-materials.json")
                      .read_text(encoding="utf-8"))["materials"]


def _docs() -> dict[str, dict]:
    return {r["id"]: materials.get(r["id"]) for r in _raw()}


def _potions() -> list[dict]:
    return json.loads((ROOT / "content/materials/alchemist-spell-potions.json")
                      .read_text(encoding="utf-8"))["potions"]


def _tool(name: str):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- the shipped materials ------------------------------------------------------------------------

def test_every_alchemist_material_passes_the_alchemy_validator():
    """Plan §5.6 through `materials.validate`'s alchemy branch: before the pass nothing
    judged an alchemist's document at all (the forge branch returned early), and 75 of 139
    carried nothing executable."""
    problems = [p for d in _docs().values() for p in materials.validate(d)]
    assert problems == []


def test_every_material_has_three_properties_and_a_reagent_a_drawback():
    """Q7.1: at least three discoverable properties each (it was 0 keys on all 139), and a
    drawback on every material that puts a trait in a bottle, as the card judges one."""
    for mid, d in _docs().items():
        assert len(knowledge.property_keys(d)) >= 3, mid
        if d["product"]:
            assert knowledge.DRAWBACK in knowledge.anatomy(d)["kinds"].values(), mid


def test_apparatus_is_exactly_the_vessels_catalysts_media_and_the_wild():
    """The exceptions to "every material its product traits" (lane A's hand-off), named:
    a material with no product trait is a vessel, a never-spent catalyst, a neutral medium
    or prima materia, and each still has a job at the bench."""
    bare = {mid for mid, d in _docs().items() if not d["product"]}
    kinds = {_docs()[m]["kind"] for m in bare}
    assert kinds <= {"vessel", "catalyst", "solvent", "treatment", "reagent"}
    named = {m for m in bare if _docs()[m]["kind"] not in ("vessel", "catalyst")}
    assert named == {"distilled-water", "rectified-spirits", "oilcloth-wrap",
                     "prima-materia"}
    # The 14 vessels (lane F added the wooden rod, the tool family's: no material had the
    # `stick` trait), 8 of the 9 catalysts (unicorn horn carries the purity lane E's
    # formulae read), and the four named.
    assert len(bare) == 14 + 8 + 4


def test_every_product_trait_names_essence_and_route_and_is_never_narrative():
    """Lane B's rule (`effectspec.product_trait_problems`) on every trait, and the carried
    route only on the three carried types — a carried cost of any other type would be a
    drawback that never lands."""
    for mid, d in _docs().items():
        for i, t in enumerate(d["product"]):
            assert effectspec.product_trait_problems(t, f"{mid} {i}") == []
            assert t["essence"] in effectspec.ESSENCES
            assert t["route"] in effectspec.ROUTES
            if t["route"] == "carried":
                assert t["type"] in effectspec.CARRIED_TYPES


def test_every_product_trait_runs_or_waits_on_a_named_reader():
    """No narrative effects (plan §5.6): every trait executes today, or its type waits on a
    reader the vocabulary names (lane C's sense, permission, light, burning)."""
    waiting = []
    for mid, d in _docs().items():
        for t in d["product"]:
            if effectspec.executable(t):
                continue
            assert (t["type"] in effectspec.AWAITING_READER
                    or t.get("target") in effectspec.TARGETS_AWAITING_READER.get(
                        t["type"], {})), (mid, t)
            waiting.append((mid, t["type"]))
    assert {k for _, k in waiting} <= {"sense", "permission", "light", "burning"}


def test_working_traits_are_the_alchemists_own():
    for mid, d in _docs().items():
        for w in d["working"]:
            assert w["trait"] in effectspec.ALCHEMY_WORKING_TRAITS, (mid, w)


def test_volatile_has_a_mishap_and_toxic_to_handle_a_toxic_document():
    """Q3.2 and Q3.4: the mishap the preview promises exists for every volatile input, and
    the handler's tax exists for every toxic one. The old `volatile` flag (read by the old
    chain bench) agrees with the working trait."""
    for r in _raw():
        traits = {w["trait"] for w in r["working"]}
        assert bool(r["volatile"]) == ("volatile" in traits), r["id"]
        assert bool(r.get("mishap")) == ("volatile" in traits), r["id"]
        assert bool(r.get("toxic")) == ("toxic_to_handle" in traits), r["id"]
        if r.get("mishap"):
            assert r["mishap"]["recipient"] == "self"


def test_every_material_has_a_colour_for_the_stage():
    for mid, d in _docs().items():
        c = d["color"]
        assert isinstance(c, list) and len(c) == 3 and all(0 <= v <= 1 for v in c), mid


def test_house_numbers_stay_inside_the_tier_ceilings():
    """Plan §5.6: brimstone carried 1d6 at common, phlogiston 4d6 at exotic, starfall core
    5d6 at legendary, salamander ash resist 5 at rare. The ceilings now hold for every
    house trait; book traits are exempt."""
    for mid, d in _docs().items():
        cap = materials.dice_max(materials.ALCHEMY_DICE_CEILING[d["tier"]])
        flat = materials.TIER_CEILING[d["tier"]]
        for t in d["product"] + [x for x in (d["mishap"], d["toxic"]) if x]:
            if t.get("book"):
                continue
            for n in materials._walk(t):
                if "dice" in n and materials.dice_max(n["dice"]) is not None:
                    assert materials.dice_max(n["dice"]) <= cap, (mid, n)
                pts = materials.points(n)
                assert pts is None or pts <= flat, (mid, n)


# --- the book fixes on the material side (plan §5.4), by set comparison ---------------------------

BOOK_VENOMS = {
    # id: (save, dc, {(type, target, dice)}) — CRB poisons table; Bestiary 2 crag linnorm
    "adder-venom-gland": ("fort", 11, {("ability_damage", "con", "1d2")}),
    "wyvern-venom-gland": ("fort", 17, {("ability_damage", "con", "1d4")}),
    "purple-worm-venom": ("fort", 24, {("ability_damage", "str", "1d3")}),
    "umbral-distillate": ("fort", 17, {("ability_drain", "str", "1"),
                                       ("ability_damage", "str", "1d2")}),
    "linnorm-venom": ("fort", 24, {("damage", None, "2d6"), ("ability_drain", "con", "1d4")}),
}


@pytest.mark.parametrize("mid", sorted(BOOK_VENOMS))
def test_the_venoms_are_the_books(mid):
    """Wyvern venom was the book's; adder venom read DC 13 (the book's black adder is 11),
    shadow essence read 1d6 Str damage (the book's is 1 drain then 1d2), and the linnorm
    read DC 26, 2d6 Con (the crag linnorm is DC 24, 2d6 fire and 1d4 Con drain)."""
    save, dc, body = BOOK_VENOMS[mid]
    gate = next(t for t in _docs()[mid]["product"] if t["type"] == "save_gate")
    assert gate["book"] and gate["target"] == save and gate["dc"] == dc
    assert {(e["type"], e.get("target"), e["dice"]) for e in gate["on_failure"]} == body
    assert _docs()[mid]["book"]


def test_the_handlers_tax_is_paid_at_the_bench_not_by_the_drinker():
    """Questions §11.11: quicksilver's and lead dust's "to the handler" damage was a
    product effect, so whoever drank the product paid it. It is a toxic document now, and
    no product trait of theirs lands on the user without saying it is a drawback."""
    for mid in ("quicksilver", "lead-dust"):
        d = _docs()[mid]
        assert d["toxic"] and d["toxic"]["recipient"] == "self"
        assert "toxic_to_handle" in {w["trait"] for w in d["working"]}
        for t in d["product"]:
            assert "handler" not in str(t.get("note") or "")


def test_against_undead_only_is_a_when_clause_not_a_note():
    """Questions §11.12: sunmetal and saint's tallow hurt the living, their "undead only"
    in a note nothing read. Both now ask `when: {target: {type: undead}}`."""
    for mid in ("sunmetal-filings", "saints-tallow"):
        hurt = [t for t in _docs()[mid]["product"] if t["type"] == "damage"]
        assert hurt and all(t["when"] == {"target": {"type": "undead"}} for t in hurt)


def test_what_burns_again_is_a_burning_document():
    """"Burns again the following round" was a note on pyre gel and white phosphorus."""
    for mid in ("pyre-gel", "white-phosphorus"):
        burn = [t for t in _docs()[mid]["product"] if t["type"] == "burning"]
        assert burn and burn[0]["dc"] == 15 and burn[0]["save"] == "ref"


def test_the_five_narrative_materials_are_typed():
    """Five materials were narrative only: fire beetle gland (light), smoke resin (smoke),
    slick jelly (grease), oil of cloves (numbing), ectoplasm (touches the incorporeal)."""
    want = {"fire-beetle-gland": "light", "smoke-resin": "manifest",
            "slick-jelly": "save_gate", "oil-of-cloves": "save_mod",
            "ectoplasm-residuum": "strikes_as"}
    for mid, kind in want.items():
        assert kind in {t["type"] for t in _docs()[mid]["product"]}, mid


# --- the hybrid herbs --------------------------------------------------------------------------------

def test_every_hybrid_herb_effect_has_an_essence_and_nothing_else_moved():
    """Plan §5.7: a hybrid herb on the alchemy shelf is read as product traits; each of its
    201 effects gains an essence (contracts §1 row D: only that). Non-hybrid herbs carry
    none."""
    herbs = json.loads((ROOT / "content/ingredients/herbs-and-parts.json")
                       .read_text(encoding="utf-8"))["ingredients"]
    n = 0
    for h in herbs:
        for e in h.get("effects") or []:
            if h.get("hybrid"):
                assert e.get("essence") in effectspec.ESSENCES, h["id"]
                assert effectspec.product_trait_problems(e, h["id"]) == []
                n += 1
            else:
                assert "essence" not in e, h["id"]
    assert n == 201


# --- the 44 potions ----------------------------------------------------------------------------------

def test_the_44_potions_are_fully_typed_and_keep_their_ids():
    """Plan §16.9: 20 narrative lines across the 44 (measured on 3bbd361). None is left;
    ids, spells and caster levels are unchanged (Q10.2, the enchanter's stand-in)."""
    pots = _potions()
    assert len(pots) == 44
    for p in pots:
        for i, e in enumerate(p["effects"]):
            assert e["type"] != "narrative", p["id"]
            assert effectspec.validate(e, f"{p['id']} {i}") == []
    ids = {p["id"]: (p["spell"], p["caster_level"]) for p in pots}
    assert ids["potion-of-invisibility"] == ("invisibility", 3)
    assert ids["potion-of-haste"] == ("haste", 5)


def test_each_potions_old_materials_still_carry_its_essence():
    """Plan §10.1: the 44 potions' exact material sets become essence requirements that
    their old materials still satisfy. At least one essence each potion's typed lines read
    as is carried by its old materials (the review page's table, for lane E)."""
    rule = _tool("alchemy_essence")
    shelf = materials.alchemy_shelf()
    for p in _potions():
        theirs = {rule.essence_of(e) for e in p["effects"]}
        # Benefits only: a drawback's essence (a sickening's `decay`) is no kinship.
        carried = {x["essence"] for m in p["materials"]
                   for x in (shelf.get(m) or {}).get("product") or ()
                   if not x.get("drawback")}
        assert theirs & carried, (p["id"], theirs, carried)


# Lane E's authored requirements that no material in the old recipe can honestly carry
# (2026-10-06): endure elements and smelling salts ask `storm` of camphor, natron, sal
# volatile and sal ammoniac; align weapon asks `binding` of font water and powdered silver;
# keen edge asks `change` of azoth and star-iron dust. Inventing a lightning trait for a
# drying salt would be a number with no reason; the lead and lane E choose between another
# second essence and a material change. Every other row is satisfied by benefit traits.
UNMET_BY_DESIGN = {"potion-of-endure-elements", "oil-of-align-weapon", "oil-of-keen-edge",
                   "smelling-salts"}


def test_old_recipes_carry_lane_es_essences():
    """Lane E (2026-10-06): its formula table hand-chooses each authored row's essences so
    that the old recipe still makes its potion "once the materials pass gives those
    materials their essences". Before this pass no material carried an essence, so every
    row missed; this pass's first draft, written from the essence rule alone, still
    left 28 of the 44 potions short of an essence lane E had chosen. Benefit traits only:
    a drawback's essence is no kinship. Skipped until lane E's table is on this branch."""
    path = ROOT / "content/rules/alchemy-formulae.json"
    if not path.is_file():
        pytest.skip("lane E's formula table is not on this branch")
    table = json.loads(path.read_text(encoding="utf-8"))
    shelf = materials.alchemy_shelf()

    def carried(ids):
        return {x["essence"] for m in ids for x in (shelf.get(m) or {}).get("product") or ()
                if not x.get("drawback")}

    review = _tool("alchemy_review")
    sets = {p["id"]: p["materials"] for p in _potions()}
    sets.update({name.lower().replace("'", "").replace(" ", "-"): ids
                 for name, _p, _s, ids in review.CLASSICS})
    unmet = {}
    for row in list(table.get("classics") or []) + list(table.get("potions") or []):
        need = set((row.get("requires") or {}).get("essences") or {})
        if row["id"] in sets and need - carried(sets[row["id"]]):
            unmet[row["id"]] = sorted(need - carried(sets[row["id"]]))
    assert set(unmet) <= UNMET_BY_DESIGN, unmet


# --- prices -------------------------------------------------------------------------------------------

def test_the_catalogue_passes_the_one_price_rule():
    """Owner, 2026-10-05: catalysts and essences cost ×5 the kind factor, rarer never
    cheaper. Checked on load by `market.lines_doc`; held here for this file."""
    assert pricing.material_price_problems(_raw(), "alchemist-materials.json") == []
    assert [p for p in market.price_problems() if "alchemist" in p] == []


# --- the validator refuses, with the fix named ----------------------------------------------------

def _doc(**kw):
    base = {"id": "testsalt", "name": "Test Salt", "kind": "salt", "tier": "common",
            "product": [{"type": "damage", "dice": "1d4", "damage_type": "fire", "lethality": "lethal",
                         "route": "struck", "essence": "fire"},
                        {"type": "apply_condition", "target": "sickened",
                         "duration": {"amount": 1, "unit": "round"}, "route": "ingest",
                         "essence": "decay", "drawback": True}],
            "working": [{"type": "working", "trait": "solid"}],
            "color": [0.5, 0.5, 0.5]}
    base.update(kw)
    return materials.normalise(base, materials.ALCHEMY_CATALOGUE)


def test_the_validator_passes_a_sound_document():
    assert materials.alchemy_problems(_doc()) == []


@pytest.mark.parametrize("change, words", [
    (dict(product=[{"type": "narrative", "target": "glows", "route": "external",
                    "essence": "light"}]), "never narrative"),
    (dict(product=[{"type": "damage", "dice": "1d4", "damage_type": "fire", "lethality": "lethal",
                    "route": "struck"}]), "names its essence"),
    (dict(product=[{"type": "damage", "dice": "2d6", "damage_type": "fire", "lethality": "lethal",
                    "route": "struck", "essence": "fire"},
                   {"type": "apply_condition", "target": "sickened", "route": "ingest",
                    "essence": "decay", "drawback": True}]), "house die is at most"),
    (dict(working=[{"type": "working", "trait": "solid"},
                   {"type": "working", "trait": "volatile"}]), "has no mishap"),
    (dict(working=[{"type": "working", "trait": "solid"},
                   {"type": "working", "trait": "toxic_to_handle"}]), "no toxic document"),
    (dict(working=[{"type": "working", "trait": "slaggy"}]), "means nothing at the"),
    (dict(product=[{"type": "damage", "dice": "1d4", "damage_type": "fire", "lethality": "lethal",
                    "route": "struck", "essence": "fire"}], working=[]),
     "discoverable propert"),
    (dict(product=[{"type": "damage", "dice": "1d4", "damage_type": "fire", "lethality": "lethal",
                    "route": "struck", "essence": "fire"},
                   {"type": "damage", "dice": "1d4", "damage_type": "acid", "lethality": "lethal",
                    "route": "struck", "essence": "acid"}]), "no drawback"),
    (dict(product=[{"type": "damage", "dice": "1d4", "damage_type": "fire", "lethality": "lethal",
                    "route": "struck", "essence": "fire", "drawback": True},
                   {"type": "apply_condition", "target": "sickened", "route": "ingest",
                    "essence": "decay", "drawback": True}]), "lands on a foe"),
    (dict(product=[], working=[{"type": "working", "trait": "solid"},
                               {"type": "working", "trait": "liquid"},
                               {"type": "working", "trait": "corrosive"}]),
     "no job at the bench"),
    (dict(color=[2, 0, 0]), "color is three numbers"),
])
def test_the_validator_refuses_with_the_fix_named(change, words):
    """Each fence of plan §5.6, refused in words: a narrative trait, a trait with no
    essence, a common 2d6 (the ceiling is 1d4), a volatile with no mishap, a toxic reagent
    with no toxic document, a forge trait at the alchemist's bench, two properties, a
    reagent with no drawback, a "drawback" that lands on the foe, apparatus with no job."""
    problems = materials.alchemy_problems(_doc(**change))
    assert any(words in p for p in problems), problems


def test_dice_max_reads_the_dice_the_catalogue_writes():
    assert [materials.dice_max(s) for s in ("1d4", "2d6+1", "20", "1d8-1", "x")] == [
        4, 13, 20, 7, None]


# --- the review page -----------------------------------------------------------------------------

def test_the_review_page_is_current():
    """docs/alchemy-review.md is generated from the data; a page that drifted from it would
    ask the owner to rule on numbers the game no longer uses."""
    mod = _tool("alchemy_review")
    current = (ROOT / "docs" / "alchemy-review.md").read_text(encoding="utf-8")
    assert current == mod.build(), "run python tools/alchemy_review.py"


def test_the_review_lists_every_classic_and_potion_against_the_book_fraction():
    """Plan §5.9: haste cost 1,750 gp of materials against a 750 gp potion. Every classic
    and every potion has its row."""
    page = (ROOT / "docs" / "alchemy-review.md").read_text(encoding="utf-8")
    section = page.split("## Inputs against the book's fraction")[1].split("\n## ")[0]
    for p in _potions():
        assert f"| {p['name']} |" in section
    mod = _tool("alchemy_review")
    for name, *_ in mod.CLASSICS:
        assert f"| {name} |" in section


def test_the_data_pass_is_idempotent():
    """`tools/alchemy_data_pass.py` rebuilds exactly the shipped files: a hand edit to the
    data that the tool does not know would be undone by its next run."""
    tool = _tool("alchemy_data_pass")
    raw = json.loads((ROOT / "content/materials/alchemist-materials.json")
                     .read_text(encoding="utf-8"))
    rows = [tool.build_material(m) for m in raw["materials"]]
    assert rows == raw["materials"]
    pots = json.loads((ROOT / "content/materials/alchemist-spell-potions.json")
                      .read_text(encoding="utf-8"))
    assert [tool.build_potion(p) for p in pots["potions"]] == pots["potions"]
