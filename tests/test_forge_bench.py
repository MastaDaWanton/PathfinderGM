"""The forge's step bench, rules side (docs/blacksmithing-revamp-plan.md §4, §7, §10, §11;
docs/blacksmithing-contracts.md §4, §7).

Lanes B (`rules/forge_items.py`), C (`rules/materials.py`) and E (`rules/knowledge.py`)
are built in parallel with this one, so a small shelf of material documents in lane C's
normalised shape (contracts §3) and stand-ins for B's build and E's knowledge are put in
`sys.modules` here. The stand-ins are deliberately dumb: they echo what they were given,
so these tests check what the bench *sends* across the contract, never maths that is
another lane's to own. Each test names the defect it prevents.
"""
from __future__ import annotations

import sys
import types

import pytest

from rules import blacksmith as bs
from rules import worldclass as wc
from rules.sheet import from_dict, load_pc, to_dict

KIT = {"smithy": None, "kit": True}
SMITHY = {"smithy": {"kind": "owned", "place": "my-smithy", "keeper": None,
                     "rate_cp_per_hour": 0}, "kit": True}
TOWN = {"smithy": {"kind": "town", "place": "the-forge", "keeper": "npc:brannoc",
                   "rate_cp_per_hour": 10}, "kit": False}
NOWHERE = {"smithy": None, "kit": False}

_STRUCT = {"weapon": ["head", "fittings"], "armour": ["body", "fastenings"]}


def _doc(mid, name, kind, tier="common", *, form=None, material=None, pieces=None,
         working=(), craft_dc=None, weapon=None, armour=None):
    return {"id": mid, "name": name, "kind": kind, "tier": tier,
            "form": form or {"ore": "ore", "metal": "bar", "alloy": "bar"}.get(kind, kind),
            "material": material or mid,
            "pieces": pieces if pieces is not None else (
                _STRUCT if kind in ("metal", "alloy") else {}),
            "weapon": weapon if weapon is not None else (
                [{"type": "combat_mod", "target": "damage", "amount": 2},
                 {"type": "combat_mod", "target": "attack", "amount": -2},
                 {"type": "gear_mod", "target": "hardness", "amount": 2}]
                if kind in ("metal", "alloy") else []),
            "armour": armour if armour is not None else [],
            "working": [{"type": "working", "trait": t} for t in working],
            "quench_mark": None, "book": False, "price_gp": 1, "text": f"{name}.",
            "craft_dc": craft_dc}


SHELF = {d["id"]: d for d in [
    _doc("iron-ore", "Iron Ore", "ore", material="iron", craft_dc=10),
    _doc("bog-iron", "Bog Iron", "ore", material="iron", working=["slaggy"], craft_dc=10),
    _doc("adamantine-ore", "Adamantine Ore", "ore", "exotic", material="adamantine",
         craft_dc=25),
    _doc("iron", "Iron", "metal", working=["forgiving"], craft_dc=10),
    _doc("copper", "Copper", "metal"),
    _doc("tin", "Tin", "metal"),
    _doc("lead", "Lead", "metal"),
    _doc("silver", "Silver", "metal", "uncommon"),
    _doc("gold", "Gold", "metal", "uncommon", working=["malleable"]),
    _doc("cold-iron", "Cold Iron", "metal", "uncommon", craft_dc=15),
    _doc("mithral", "Mithral", "metal", "rare", craft_dc=20),
    _doc("star-iron", "Star Iron", "metal", "rare", working=["flawless"], craft_dc=20),
    _doc("adamantine", "Adamantine", "metal", "exotic", craft_dc=25),
    _doc("noqual", "Noqual", "metal", "exotic", working=["reactive"], craft_dc=25),
    _doc("steel", "Steel", "alloy", craft_dc=10),
    _doc("high-carbon-steel", "High-Carbon Steel", "alloy", "uncommon",
         working=["narrow_window"], craft_dc=15),
    _doc("pattern-steel", "Pattern Steel", "alloy", "uncommon", craft_dc=15),
    _doc("bronze", "Bronze", "alloy"),
    _doc("bell-bronze", "Bell Bronze", "alloy", "uncommon"),
    _doc("pewter", "Pewter", "alloy"),
    _doc("nexavaran-steel", "Nexavaran Steel", "alloy", "uncommon", craft_dc=15),
    _doc("charcoal", "Charcoal", "fuel", working=["clean_heat"], craft_dc=10),
    _doc("coal", "Coal", "fuel", working=["sulfurous"]),
    _doc("dragonfire-coal", "Dragonfire Coal", "fuel", "rare", craft_dc=20),
    _doc("limestone", "Limestone", "flux", working=["cleans_slag"]),
    _doc("borax", "Borax", "flux", "uncommon", working=["weld_aid"]),
    _doc("water", "Water", "quenchant"),
    _doc("quenching-brine", "Quenching Brine", "quenchant"),
    _doc("ash-haft", "Ash Haft", "fitting", form="haft", pieces={"weapon": ["haft"]}),
    _doc("brass-guard", "Brass Guard", "fitting", form="guard",
         pieces={"weapon": ["fittings"]}),
    _doc("padding", "Quilted Padding", "fitting", form="lining",
         pieces={"armour": ["lining"]}),
    _doc("bluing", "Bluing", "treatment"),
    _doc("alchemical-silver-plating", "Alchemical Silver Plating", "treatment",
         "uncommon", craft_dc=15),
    _doc("holy-anointing", "Holy Anointing", "treatment", "rare", craft_dc=20),
]}


def fake_materials() -> types.ModuleType:
    mod = types.ModuleType("rules.materials")
    mod.get = lambda mid: dict(SHELF[mid]) if mid in SHELF else None
    mod.all = lambda: {k: dict(v) for k, v in SHELF.items()}
    mod.of_kind = lambda kind: [dict(v) for v in SHELF.values() if v["kind"] == kind]
    mod.material_of = lambda mid: (SHELF.get(mid) or {}).get("material", mid)
    mod.TIER_CEILING = {"common": 2, "uncommon": 2, "rare": 3, "exotic": 3, "legendary": 4}
    return mod


def fake_forge_items(calls: list) -> types.ModuleType:
    """Lane B's two functions, echoing their arguments so a test can see exactly what the
    bench sent across contracts §4."""
    mod = types.ModuleType("rules.forge_items")

    def build(record):
        calls.append(("build", record))
        return {"specs": [], "book": [], "strikes_as": [], "gear": {}, "riders": [],
                "sum": [{"target": "probe",
                         "pieces": {k: v["passes"] for k, v in record["pieces"].items()},
                         "final": 0}],
                "masterwork": record["masterwork"]}

    def preview(pieces, *, gear, base, quality_index, level, perks):
        calls.append(("preview", {"pieces": pieces, "gear": gear, "base": base,
                                  "quality_index": quality_index, "level": level,
                                  "perks": perks}))
        return {"specs": [], "sum": [], "quality_index": quality_index,
                "masterwork": quality_index >= 3}

    mod.build, mod.preview = build, preview
    return mod


def fake_knowledge() -> types.ModuleType:
    """Lane E's knowledge over material documents: one positional key per weapon effect,
    armour effect and working trait, in that order (contracts §6, "as today")."""
    mod = types.ModuleType("rules.knowledge")

    def property_keys(doc):
        n = len(doc.get("weapon") or []) + len(doc.get("armour") or []) \
            + len(doc.get("working") or [])
        return [f"k{i}" for i in range(n)]

    def properties(actor, doc):
        known = set(((actor.herb_known or {}).get(doc["id"]) or {}).get("keys") or [])
        rows = []
        texts = ([f"weapon {e['target']} {e['amount']:+d}" for e in doc.get("weapon") or []]
                 + [f"armour {e.get('target')}" for e in doc.get("armour") or []]
                 + [f"works {w['trait']}" for w in doc.get("working") or []])
        for i, text in enumerate(texts):
            k = f"k{i}"
            rows.append({"key": k, "known": k in known, "text": text if k in known else ""})
        return rows

    def reveal(actor, mid, keys, how):
        entry = actor.herb_known.setdefault(mid, {"keys": [], "how": {}})
        new = [k for k in keys if k not in entry["keys"]]
        entry["keys"] += new
        for k in new:
            entry["how"][k] = how
        return new

    def assay(actor, mid, total, *, clock):
        doc = SHELF[mid]
        keys = property_keys(doc)
        new = reveal(actor, mid, keys[:2], f"assayed, day {clock // 1440 + 1}")
        cost = {"ore": 1} if doc["kind"] == "ore" else {"bars": 0.1}
        return {"revealed": new, "cost": cost, "minutes": 10, "danger": None}

    mod.property_keys, mod.properties, mod.reveal, mod.assay = \
        property_keys, properties, reveal, assay
    mod.assay_dc = lambda doc, actor: 12
    mod.ledger = lambda actor: [{"id": k, "known": len(v.get("keys") or [])}
                                for k, v in (actor.herb_known or {}).items()]
    return mod


@pytest.fixture
def lanes(monkeypatch):
    """Lanes B, C and E as stand-ins; returns the list lane B's calls land in."""
    calls: list = []
    monkeypatch.setitem(sys.modules, "rules.materials", fake_materials())
    monkeypatch.setitem(sys.modules, "rules.forge_items", fake_forge_items(calls))
    monkeypatch.setitem(sys.modules, "rules.knowledge", fake_knowledge())
    return calls


@pytest.fixture
def pc(lanes):
    actor = load_pc("fixtures/pc-kesst.json")
    actor.inventory.clear()
    actor.stock.clear()
    actor.herb_known.clear()
    return actor


def prog(level: int, **perks) -> wc.Progress:
    return wc.Progress(track="blacksmith", level=level, perks=dict(perks))


def at(actor, key: str) -> bs.Piece:
    return next(p for p in bs.rack(actor) if p.key == key)


def held(actor, form: str) -> list[bs.Piece]:
    return [p for p in bs.rack(actor) if p.form == form]


def step(actor, level, method, slots, *, batch=1, shape="", where=KIT, masterwork=True,
         **perks):
    """A plan from {slot: key or (key, count)} against the actor's rack."""
    built = {}
    for slot, val in slots.items():
        key, n = (val, 1) if isinstance(val, str) else val
        built[slot] = (at(actor, key), n)
    return bs.plan_step(actor, prog(level, **perks), method, built, batch, shape=shape,
                        where=where, masterwork=masterwork)


def work(actor, plan, tier=2, extra=0):
    """Finish a planned step as the views do: spend, make, land."""
    assert plan.can_roll, plan.problems
    bs.spend(actor, plan.consumes)
    return bs.land(actor, bs.make(plan, tier, extra=extra))


def blank(actor, metal="iron", shape="longsword", level=1, *, quality=2, worked=(),
          quench="", traits=(), passes=0) -> str:
    gear = (bs.shape_info(shape) or {}).get("gear", "weapon")
    w = bs.Work(form="blank" if gear == "weapon" else "plate", material=metal,
                shape=bs.shape_info(shape)["id"], gear=gear, quality=quality,
                worked=list(worked), quench=quench, traits=list(traits), passes=passes,
                tier=SHELF[metal]["tier"])
    return "stock:" + bs.put(actor, w, 1)


def ready_blank(actor, metal="iron", shape="longsword", quality=3):
    edged = bs.shape_info(shape)["edged"]
    return blank(actor, metal, shape, quality=quality, quench="water",
                 worked=["quench", "temper"] + (["hone"] if edged else []))


# --- the track ---------------------------------------------------------------------------

def test_smelting_makes_a_real_ingot_of_the_ores_metal(pc):
    """Smelting produced no ingot: the old chain went ore-to-sword in one roll and nothing
    in between ever reached the shelf (plan §2, "real intermediates land on the shelf").
    Two iron ore and two charcoal make one Iron Ingot of the ore's parent metal."""
    pc.carry("iron-ore", 4)
    pc.carry("charcoal", 4)
    plan = step(pc, 1, "smelt", {"ore": "inv:iron-ore", "fuel": "inv:charcoal"},
                batch=2, where=SMITHY)
    assert plan.problems == []
    assert plan.dc == 10 and plan.minutes == 120
    assert [(p.key, n) for p, n in plan.consumes] == [("inv:iron-ore", 4),
                                                       ("inv:charcoal", 4)]
    landed = work(pc, plan, tier=1)
    (key, w, n), = landed
    assert (w.form, w.material, n, w.name) == ("ingot", "iron", 2, "Iron Ingot")
    ingot = at(pc, f"stock:{key}")
    assert ingot.count == 2 and ingot.quality == 1
    assert "iron-ore" not in pc.inventory and "charcoal" not in pc.inventory


def test_smelting_needs_a_smithy_and_says_so(pc):
    """Plan §10: the field kit has no furnace. Smelt is greyed with the reason in words,
    never a silent no."""
    pc.carry("iron-ore", 2)
    pc.carry("charcoal", 2)
    plan = step(pc, 1, "smelt", {"ore": "inv:iron-ore", "fuel": "inv:charcoal"})
    assert any("Smelt needs a smithy" in p for p in plan.problems)
    lock = next(m for m in bs.methods_view(1, KIT) if m["id"] == "smelt")
    assert lock["locked"] and lock["lock_reason"] == "Needs a smithy"


def test_flux_in_the_charge_cancels_slaggy_ore(pc):
    """Flux is no longer a method (plan §2): it is an ingredient of Smelt. Bog iron
    smelted without it is slaggy, which takes a step off the quality ceiling until it is
    folded; with limestone in the charge the ingot comes out clean."""
    pc.carry("bog-iron", 4)
    pc.carry("charcoal", 4)
    pc.carry("limestone", 1)
    dirty = step(pc, 1, "smelt", {"ore": "inv:bog-iron", "fuel": "inv:charcoal"},
                 where=SMITHY)
    assert dirty.outputs[0][0].traits == ["slaggy"]
    assert dirty.step_ceiling == dirty.ceiling - 1
    clean = step(pc, 1, "smelt", {"ore": "inv:bog-iron", "fuel": "inv:charcoal",
                                  "flux": "inv:limestone"}, where=SMITHY)
    assert clean.outputs[0][0].traits == []
    assert clean.step_ceiling == clean.ceiling


def test_skymetal_ore_does_not_melt_over_charcoal(pc):
    """Today's rule, kept (plan §7): exotic ore needs a rare-tier fuel."""
    pc.carry("adamantine-ore", 2)
    pc.carry("charcoal", 2)
    pc.carry("dragonfire-coal", 2)
    cold = step(pc, 2, "smelt", {"ore": "inv:adamantine-ore", "fuel": "inv:charcoal"},
                where=SMITHY)
    assert any("does not melt over charcoal" in p for p in cold.problems)
    hot = step(pc, 2, "smelt", {"ore": "inv:adamantine-ore",
                                "fuel": "inv:dragonfire-coal"}, where=SMITHY)
    assert hot.problems == []


def test_alloying_iron_with_carbon_pours_named_steel(pc):
    """Alloying iron and copper yielded 'Iron Work': the old chain named every product
    after its first metal. The recipe table names the alloy, and one bar comes out for
    every bar that went in; the carbon is taken up."""
    pc.carry("iron", 4)
    pc.carry("charcoal", 1)
    plan = step(pc, 2, "alloy", {"a": ("inv:iron", 4), "b": ("inv:charcoal", 1)},
                where=SMITHY)
    assert plan.problems == []
    (key, w, n), = work(pc, plan)
    assert (w.material, w.form, n, w.name) == ("steel", "bar", 4, "Steel Bar")
    assert pc.inventory == {}


def test_the_ratio_window_picks_the_alloy_and_refuses_outside_every_window(pc):
    """Vintage Story's model (plan §7): copper and tin make bronze, bell bronze or pewter
    by their shares. A melt outside every window is refused with the windows named."""
    pc.carry("copper", 9)
    pc.carry("tin", 4)
    for copper, tin, want in ((9, 1, "bronze"), (4, 1, "bell-bronze"), (1, 4, "pewter")):
        plan = step(pc, 2, "alloy", {"a": ("inv:copper", copper), "b": ("inv:tin", tin)},
                    where=SMITHY)
        assert plan.problems == [], (copper, tin, plan.problems)
        assert plan.outputs[0][0].material == want
    bad = step(pc, 2, "alloy", {"a": ("inv:copper", 1), "b": ("inv:tin", 1)},
               where=SMITHY)
    assert bad.problems and "bronze" in bad.problems[0] and "%" in bad.problems[0]


def test_an_unlisted_pair_is_a_novel_alloy_under_a_real_name(pc):
    """Plan §7: an unlisted pair keeps the novel-alloy rank step "but under a real name".
    Copper and lead, two different common metals, pour an uncommon Copper-Lead Alloy."""
    pc.carry("copper", 2)
    pc.carry("lead", 2)
    plan = step(pc, 2, "alloy", {"a": ("inv:copper", 2), "b": ("inv:lead", 2)},
                where=SMITHY)
    assert plan.problems == []
    w, n = plan.outputs[0]
    assert (w.material, w.alloy_of, w.tier, n) == ("copper", ["lead"], "uncommon", 4)
    (key, made, _), = work(pc, plan)
    assert made.name == "Copper-Lead Alloy Bar"


def test_solitary_metals_enter_only_the_recipe_that_names_them(pc):
    """What makes cold iron cold iron does not survive the mixing, except in the one alloy
    the book names for it (nexavaran steel)."""
    pc.carry("cold-iron", 3)
    pc.carry("iron", 1)
    pc.carry("steel", 1)
    alone = step(pc, 2, "alloy", {"a": ("inv:cold-iron", 1), "b": ("inv:iron", 1)},
                 where=SMITHY)
    assert any("Cold Iron works alone" in p for p in alone.problems)
    named = step(pc, 2, "alloy", {"a": ("inv:cold-iron", 3), "b": ("inv:steel", 1)},
                 where=SMITHY)
    assert named.problems == [] and named.outputs[0][0].material == "nexavaran-steel"


def test_pattern_steel_is_folded_not_melted(pc):
    """Plan §7: Fold "makes pattern steel from two steels". The crucible refuses the pair
    with the way to do it; the fold makes it."""
    pc.carry("steel", 1)
    pc.carry("high-carbon-steel", 1)
    melt = step(pc, 2, "alloy", {"a": ("inv:steel", 1), "b": ("inv:high-carbon-steel", 1)},
                where=SMITHY)
    assert any("folded, not melted" in p for p in melt.problems)
    fold = step(pc, 2, "fold", {"piece": "inv:steel", "with": "inv:high-carbon-steel"},
                where=SMITHY)
    assert fold.problems == []
    (key, w, n), = work(pc, fold)
    assert (w.material, w.name) == ("pattern-steel", "Pattern Steel Bar")


def test_the_shape_is_picked_from_the_engines_list_never_typed(pc):
    """Ground every name (CLAUDE.md): a blank's shape is a weapon or armour the tables
    know. A free-text shape is refused; a real one carries the book's Craft DC."""
    pc.carry("iron", 5)
    pc.carry("charcoal", 2)
    junk = step(pc, 1, "forge", {"metal": "inv:iron", "fuel": "inv:charcoal"},
                shape="vorpal-zweihander")
    assert any("weapon or armour lists" in p for p in junk.problems)
    sword = step(pc, 1, "forge", {"metal": "inv:iron", "fuel": "inv:charcoal"},
                 shape="Longsword")
    assert sword.problems == [] and sword.dc == 15
    w = sword.outputs[0][0]
    assert (w.form, w.shape, w.gear) == ("blank", "longsword", "weapon")
    plate = step(pc, 1, "forge", {"metal": "inv:iron", "fuel": "inv:charcoal"},
                 shape="breastplate")
    assert plate.dc == 16, "armour is 10 + its AC bonus (breastplate +6)"
    assert plate.outputs[0][0].form == "plate"
    assert [n for _, n in plate.consumes] == [3, 1], "30 lb of armour is three bars"
    names = {s["id"] for f in bs.shapes()["families"] for s in f["shapes"]}
    assert "longsword" in names and "full plate" in names and "heavy shield" in names
    assert "leather" not in names and "longbow" not in names


def test_quench_marks_the_piece_and_leaves_it_brittle_until_tempered(pc):
    """Plan §7, accepted 2026-10-03: skipping Temper leaves a real flaw. The quench mark
    is the bath's id on the piece, never a number."""
    key = blank(pc)
    pc.carry("water", 1)
    q = step(pc, 1, "quench", {"piece": key, "quenchant": "inv:water"})
    assert q.problems == []
    (qkey, w, _), = work(pc, q)
    assert w.quench == "water" and "brittle" in w.traits
    assert w.name == "Quenched Iron Blank (Longsword)"
    t = step(pc, 2, "temper", {"piece": f"stock:{qkey}"})
    (tkey, tw, _), = work(pc, t)
    assert "brittle" not in tw.traits and "temper" in tw.worked
    again = step(pc, 2, "temper", {"piece": f"stock:{tkey}"})
    assert any("already tempered" in p for p in again.problems)


def test_an_untempered_item_keeps_brittle_and_cannot_be_masterwork(pc):
    """The flaw reaches the record (`flaws`), and a brittle head caps the work below
    Superior: masterwork is earned work (plan §7, "masterwork chain")."""
    key = blank(pc, quality=3, quench="water", worked=["quench"], traits=["brittle"])
    pc.carry("ash-haft", 1)
    plan = step(pc, 2, "assemble", {"head": key, "haft": "inv:ash-haft"})
    assert plan.problems == []
    assert plan.step_ceiling == 2 and not plan.masterwork_work
    assert "not tempered" in plan.masterwork_why
    (k, w, _), = work(pc, plan, tier=4)
    rec = bs.record(w)
    assert rec["flaws"] == ["brittle"] and rec["quality_index"] == 2
    assert rec["masterwork"] is False


def test_masterwork_is_superior_work_at_dc_20(pc):
    """Plan §4.4: Superior or better is masterwork, and the book's masterwork component is
    DC 20. A tempered and honed head at Blacksmith 2 reaches it; Blacksmith 1 tops out at
    Fine, and a smith not aiming for it keeps the book DC and a Fine cap."""
    key = ready_blank(pc)
    pc.carry("ash-haft", 2)
    pc.carry("brass-guard", 1)
    plan = step(pc, 2, "assemble", {"head": key, "haft": "inv:ash-haft",
                                    "fittings": "inv:brass-guard"})
    assert plan.problems == [] and plan.dc == 20 and plan.step_ceiling == 3
    modest = step(pc, 2, "assemble", {"head": key, "haft": "inv:ash-haft"},
                  masterwork=False)
    assert modest.dc == 15 and modest.step_ceiling == 2
    novice = step(pc, 1, "assemble", {"head": key, "haft": "inv:ash-haft"})
    assert novice.step_ceiling == 2 and novice.dc == 15
    (k, w, _), = work(pc, plan, tier=3)
    rec = bs.record(w)
    assert rec["masterwork"] is True and rec["quality"] == "superior"
    assert w.name == "Superior Iron Longsword"
    assert pc.stock[k].masterwork is True


def test_hone_is_for_edges_and_a_hammer_needs_none(pc):
    """An edged weapon needs a honed head for Superior (plan §7); a warhammer has no edge,
    so honing it is refused and its masterwork needs only the temper."""
    hammer = blank(pc, shape="warhammer", quality=3, quench="water",
                   worked=["quench", "temper"])
    refused = step(pc, 2, "hone", {"piece": hammer})
    assert any("no edge to hone" in p for p in refused.problems)
    ok, _ = bs.masterwork_ready(at(pc, hammer).work)
    assert ok
    sword = blank(pc, quality=3, quench="water", worked=["quench", "temper"])
    ok, why = bs.masterwork_ready(at(pc, sword).work)
    assert not ok and "not honed" in why


def test_flawless_metal_waives_the_masterwork_dc(pc):
    """Pathfinder Unchained's flawless raw material: no DC increase for masterwork."""
    key = ready_blank(pc, metal="star-iron")
    pc.carry("ash-haft", 1)
    plan = step(pc, 2, "assemble", {"head": key, "haft": "inv:ash-haft"}, where=SMITHY)
    assert plan.problems == [] and plan.dc == 15 and plan.step_ceiling == 3


def test_assemble_writes_the_contract_record_with_ids_and_passes_only(pc, lanes):
    """The read-live rule (contracts §4): the record stores ids and passes, never a
    computed number, and lane B's build is asked of the record. Measured before the
    revamp: a forged sword's specs were baked in at the bench and nothing re-derived them
    when the material changed."""
    key = blank(pc, quality=2, quench="water", worked=["quench", "temper", "hone"],
                passes=1)
    pc.carry("ash-haft", 1)
    pc.carry("brass-guard", 1)
    plan = step(pc, 2, "assemble", {"head": key, "haft": "inv:ash-haft",
                                    "fittings": "inv:brass-guard"}, masterwork=False)
    (k, w, _), = work(pc, plan, tier=2)
    rec = bs.record(pc.stock[k])
    assert rec == {
        "id": "fine-iron-longsword", "name": "Fine Iron Longsword",
        "kind": "crafted", "craft": "blacksmith", "count": 1,
        "gear": "weapon", "base": "longsword", "slot": "hands",
        "quality": "fine", "quality_index": 2, "masterwork": False,
        "pieces": {"head": {"material": "iron", "passes": 1},
                   "haft": {"material": "ash-haft", "passes": 0},
                   "fittings": {"material": "brass-guard", "passes": 0}},
        "quench": "water", "finish": [], "flaws": [],
        "smith": {"level": 2, "perks": {"potency": 0, "hardening": 0}},
        "schema": 3,
    }
    built = bs.build_of(rec)
    assert lanes[-1] == ("build", rec)
    assert built["sum"][0]["pieces"] == {"head": 1, "haft": 0, "fittings": 0}


def test_the_worked_example_record_comes_out_of_the_real_chain(pc):
    """Plan §6.4's longsword (iron head strengthened once, ash haft, brass fittings,
    Fine, smith level 2) made step by step, so lane B's worked-example test and this bench
    meet on the same record: strengthen, forge, quench, temper, assemble."""
    pc.carry("iron", 2)
    pc.carry("charcoal", 1)
    pc.carry("water", 1)
    pc.carry("ash-haft", 1)
    pc.carry("brass-guard", 1)
    (bar, w, n), = work(pc, step(pc, 2, "strengthen", {"bar": "inv:iron"}, where=SMITHY))
    assert (w.passes, n, w.name) == (1, 1, "Iron Bar (strengthened ×1)")
    (bl, w, _), = work(pc, step(pc, 2, "forge", {"metal": f"stock:{bar}",
                                                 "fuel": "inv:charcoal"},
                                shape="longsword"), tier=2)
    assert w.passes == 1
    (bl, w, _), = work(pc, step(pc, 2, "quench", {"piece": f"stock:{bl}",
                                                  "quenchant": "inv:water"}), tier=2)
    (bl, w, _), = work(pc, step(pc, 2, "temper", {"piece": f"stock:{bl}"}), tier=2)
    plan = step(pc, 2, "assemble", {"head": f"stock:{bl}", "haft": "inv:ash-haft",
                                    "fittings": "inv:brass-guard"})
    (k, item, _), = work(pc, plan, tier=2)
    rec = bs.record(pc.stock[k])
    assert rec["pieces"] == {"head": {"material": "iron", "passes": 1},
                             "haft": {"material": "ash-haft", "passes": 0},
                             "fittings": {"material": "brass-guard", "passes": 0}}
    assert (rec["quality"], rec["smith"]["level"], rec["quench"]) == ("fine", 2, "water")


def test_no_bulk_at_assemble(pc):
    """Accepted 2026-10-03: a stack of ten identical longswords from one minigame is the
    Bannerlord exploit shape. Assemble refuses a batch; Smelt, Alloy, Forge and
    Strengthen keep theirs."""
    key = ready_blank(pc)
    pc.carry("ash-haft", 2)
    plan = step(pc, 2, "assemble", {"head": key, "haft": "inv:ash-haft"}, batch=2)
    assert any("one piece at a time" in p for p in plan.problems)
    bulky = {m["id"] for m in bs.methods_view(3, SMITHY) if m["bulk"]}
    assert bulky == {"smelt", "alloy", "forge", "strengthen"}


def test_strengthen_makes_two_bars_one_and_counts_the_pass(pc):
    """The smithing concentration (plan §2): two bars of one metal make one strengthened
    bar, repeatable, and the passes travel into the blank and the record."""
    pc.carry("iron", 4)
    plan = step(pc, 2, "strengthen", {"bar": "inv:iron"}, batch=2, where=SMITHY)
    assert [n for _, n in plan.consumes] == [4]
    (key, w, n), = work(pc, plan)
    assert (w.passes, n) == (1, 2)
    again = step(pc, 2, "strengthen", {"bar": f"stock:{key}"}, where=SMITHY)
    assert again.outputs[0][0].passes == 2
    assert step(pc, 2, "strengthen", {"bar": f"stock:{key}"}).problems, \
        "strengthening is forge-welding heat: a smithy"


def test_finish_obeys_the_books_restrictions_and_the_sacred_level(pc):
    """Plan §6.3: alchemical silver will not take on adamantine, cold iron or mithral; the
    sacred finishes open at Blacksmith 3 (plan §4.1)."""
    item = bs.Work(form="item", material="mithral", shape="longsword", gear="weapon",
                   quality=2, pieces={"head": {"material": "mithral", "passes": 0},
                                      "haft": {"material": "ash-haft", "passes": 0}},
                   smith={"level": 2, "perks": {}}, tier="rare")
    item.name = bs.work_name(item)
    key = "stock:" + bs.put(pc, item, 1)
    pc.carry("alchemical-silver-plating", 1)
    pc.carry("holy-anointing", 1)
    pc.carry("bluing", 1)
    silver = step(pc, 2, "finish", {"item": key, "treatment":
                                    "inv:alchemical-silver-plating"}, where=SMITHY)
    assert any("will not take on mithral" in p for p in silver.problems)
    holy = step(pc, 2, "finish", {"item": key, "treatment": "inv:holy-anointing"},
                where=SMITHY)
    assert any("learned at Blacksmith 3" in p for p in holy.problems)
    holy3 = step(pc, 3, "finish", {"item": key, "treatment": "inv:holy-anointing"},
                 where=SMITHY)
    assert holy3.problems == []
    (k, w, _), = work(pc, holy3, tier=0)
    assert w.finish == ["holy-anointing"] and w.quality == 2, \
        "a finish never re-grades the item"


def test_the_pf1e_fail_rule_and_its_generous_tie(pc):
    """Plan §11: fail by 4 or less loses only the time; by 5 or more, half of what was on
    the anvil, rounded down. A tie spoils the cheaper raw thing: a failed quench by 5
    spoils the bath, not the blank. Malleable metal forgives it entirely."""
    key = blank(pc)
    pc.carry("water", 1)
    q = step(pc, 1, "quench", {"piece": key, "quenchant": "inv:water"})
    assert bs.failure_losses(q, 4) == []
    lost = bs.failure_losses(q, 5)
    assert [(p.key, n) for p, n in lost] == [("inv:water", 1)]
    pc.carry("iron-ore", 2)
    pc.carry("charcoal", 2)
    s = step(pc, 1, "smelt", {"ore": "inv:iron-ore", "fuel": "inv:charcoal"},
             where=SMITHY)
    assert sorted(n for _, n in bs.failure_losses(s, 9)) == [1, 1]
    pc.carry("gold", 1)
    soft = step(pc, 1, "forge", {"metal": "inv:gold", "fuel": "inv:charcoal"},
                shape="dagger")
    assert soft.problems == [] and bs.failure_losses(soft, 12) == []


def test_a_minigame_miss_after_a_successful_roll_loses_nothing(pc):
    """WoW removed Inspiration for "a lack of decision making and agency" (sweep §1): no
    losses after a successful roll. A score of 0 still lands the product, at Crude."""
    pc.carry("iron", 1)
    pc.carry("charcoal", 1)
    plan = step(pc, 1, "forge", {"metal": "inv:iron", "fuel": "inv:charcoal"},
                shape="dagger")
    (key, w, n), = work(pc, plan, tier=0)
    assert n == 1 and w.quality == 0 and at(pc, f"stock:{key}").count == 1


def test_rarity_follows_the_level_and_rare_metal_needs_a_smithy(pc):
    """Plan §4.1 and §10: Blacksmith 1 works common and uncommon; rare and up open at 2,
    and only at a smithy, never on the field kit."""
    pc.carry("mithral", 1)
    pc.carry("charcoal", 1)
    slots = {"metal": "inv:mithral", "fuel": "inv:charcoal"}
    one = step(pc, 1, "forge", slots, shape="dagger", where=SMITHY)
    assert any("Mithral is rare; Blacksmith 1 works uncommon at best: it needs "
               "Blacksmith 2." in p for p in one.problems)
    kit = step(pc, 2, "forge", slots, shape="dagger", where=KIT)
    assert any("rare and rarer metal needs a smithy" in p for p in kit.problems)
    assert step(pc, 2, "forge", slots, shape="dagger", where=SMITHY).problems == []
    assert any("no field kit" in p for p in
               step(pc, 1, "forge", {"metal": "inv:mithral", "fuel": "inv:charcoal"},
                    shape="dagger", where=NOWHERE).problems)


def test_the_score_never_climbs_past_the_steps_ceiling(pc):
    """The page sends a score and the server decides what it is worth (plan §11): a
    forged 1.0 at Blacksmith 1 lands on Fine, and slaggy metal one lower."""
    from rules import crafting

    pc.carry("iron", 1)
    pc.carry("charcoal", 1)
    plan = step(pc, 1, "forge", {"metal": "inv:iron", "fuel": "inv:charcoal"},
                shape="dagger")
    tier, _ = crafting.tier_from_score(7, plan.step_ceiling)
    assert tier == 2 and bs.make(plan, 9)[0][0].quality == 2


def test_no_dc_creeps_up_a_chain(pc):
    """Plan §7: "No per-stage +2 creep". The old chain added 2 a stage; each step is its
    own roll now, so a temper after three earlier steps is the metal's own DC."""
    key = blank(pc, quench="water", worked=["quench"], traits=["brittle"])
    assert step(pc, 2, "temper", {"piece": key}).dc == 10
    pc.carry("water", 1)
    assert step(pc, 1, "quench", {"piece": blank(pc, shape="dagger"),
                                  "quenchant": "inv:water"}).dc == 10


def test_a_forged_piece_survives_save_and_load(pc):
    """The forge's state travels in `Stock.properties` tags; a save that dropped them would
    turn a tempered strengthened blank into a nameless jar. Round-tripped through the
    sheet's own to_dict/from_dict, the record is identical."""
    key = ready_blank(pc)
    pc.carry("ash-haft", 1)
    (k, w, _), = work(pc, step(pc, 2, "assemble", {"head": key, "haft": "inv:ash-haft"}),
                      tier=3)
    before = bs.record(pc.stock[k])
    back = from_dict(to_dict(pc))
    assert bs.record(back.stock[k]) == before
    assert {p.key for p in bs.rack(back)} == {p.key for p in bs.rack(pc)}


def test_two_different_builds_never_share_a_name(pc):
    """`worn` is keyed by name and lane B resolves a record by id or name, so two Fine
    Iron Longswords on different hafts stacking or sharing a name would wield the wrong
    one. The second is numbered."""
    pc.carry("ash-haft", 1)
    pc.carry("brass-guard", 1)
    a = blank(pc, quality=1)
    work(pc, step(pc, 1, "assemble", {"head": a, "haft": "inv:ash-haft"}), tier=2)
    b = blank(pc, quality=1)
    pc.carry("ash-haft", 1)
    (k, w, _), = work(pc, step(pc, 1, "assemble", {"head": b, "haft": "inv:ash-haft",
                                                   "fittings": "inv:brass-guard"}),
                      tier=2)
    names = sorted(st.name for st in pc.stock.values())
    assert names == ["Fine Iron Longsword", "Fine Iron Longsword (2)"]
    assert bs.record(pc.stock[k])["id"] == "fine-iron-longsword-2"


def test_yield_and_a_crude_sulfurous_heat(pc):
    """Yield is one more ingot or blank, rolled by the caller (plan §4.2). A Crude result
    over sulfurous coal is hot-short (plan §5.5); clean charcoal never is."""
    pc.carry("iron", 2)
    pc.carry("coal", 1)
    pc.carry("charcoal", 1)
    hot = step(pc, 1, "forge", {"metal": "inv:iron", "fuel": "inv:coal"}, shape="dagger")
    (w, n), = bs.make(hot, 0, extra=1)
    assert n == 2 and "hot_short" in w.traits
    clean = step(pc, 1, "forge", {"metal": "inv:iron", "fuel": "inv:charcoal"},
                 shape="dagger")
    assert "hot_short" not in bs.make(clean, 0)[0][0].traits


def test_tuning_follows_the_metal_not_the_level(pc):
    """Better metal, tighter window (Giants' Foundry); forgiving iron widens the band,
    narrow-window steel narrows it. The level never widens it (the ceiling grows)."""
    pc.carry("iron", 1)
    pc.carry("high-carbon-steel", 1)
    pc.carry("charcoal", 2)
    iron = bs.tuning_for(step(pc, 1, "forge", {"metal": "inv:iron",
                                               "fuel": "inv:charcoal"}, shape="dagger"))
    hc = bs.tuning_for(step(pc, 1, "forge", {"metal": "inv:high-carbon-steel",
                                             "fuel": "inv:charcoal"}, shape="dagger"))
    assert iron["band_scale"] == 1.2 and hc["band_scale"] == 0.8
    assert hc["difficulty"] > iron["difficulty"]
    lvl3 = bs.tuning_for(step(pc, 3, "forge", {"metal": "inv:iron",
                                               "fuel": "inv:charcoal"}, shape="dagger"))
    assert lvl3["difficulty"] == iron["difficulty"] and len(lvl3["names"]) == 5


def test_prospected_ore_reaches_the_rack_under_either_craft_id(pc):
    """Plan §12.7: `_op_prospect` writes `craft="smithing"` and the old bench filtered on
    "blacksmith", so prospected ore never reached the forge. The rack reads both."""
    from rules.crafting import Stock

    pc.add_stock(Stock(base="Iron Ore", tier="common", kind="ore", craft="smithing"), 3)
    ore = held(pc, "ore")
    assert [(p.material, p.count) for p in ore] == [("iron-ore", 3)]


def test_the_bench_reads_lane_gs_real_smithy_kit_and_rent():
    """Contracts §8 against lane G's merged code, not a stand-in: standing in Caddonbury's
    smithy the bench finds a town smithy, Smelt unlocks, and two hours of smelting cost
    what `market.forge_rent` says (1 sp an hour). Outside it, with no kit carried, every
    kit method is locked with the reason in words; carrying "Smith's Field Kit" opens
    them. Measured on this branch before lane G merged: there was no smithy anywhere."""
    from tests.test_forge_places import SYNTHETIC, _table
    from rules import places

    city = next(SYNTHETIC.get(r["id"]) for r in SYNTHETIC.play["settlements"]
                if SYNTHETIC.get(r["id"]).name == "Caddonbury")
    smithy = next(p for p in places.home_set(city) if p.name == "the smithy")
    scene, engine = _table(SYNTHETIC, city.id)
    pc = scene.pc()
    pc.goods.clear()
    pc.stock.clear()
    outside = bs.where_here(scene, pc, engine.places())
    assert outside == {"smithy": None, "kit": False}
    locks = {m["id"]: m["lock_reason"] for m in bs.methods_view(1, outside)}
    assert locks["forge"] == "Needs a field kit or a smithy"
    pc.goods["Smith's Field Kit"] = 1
    assert bs.where_here(scene, pc, engine.places())["kit"] is True

    engine.place_party(smithy.id)
    here = bs.where_here(scene, pc, engine.places())
    assert here["smithy"]["kind"] == "town"
    assert {m["id"]: m["lock_reason"] for m in bs.methods_view(1, here)}["smelt"] == ""
    assert bs.rent_cp(scene, here["smithy"], 120, engine.places()) == 20


def test_assay_cuts_a_tenth_of_a_bar(pc):
    """Plan §9.2: "bars track tenths". The assay's sliver is a tenth of a carried bar; ten
    of them use the bar up."""
    pc.carry("iron", 2)
    bs.pay_assay(pc, "iron", {"bars": 0.1})
    p = next(x for x in bs.rack(pc) if x.material == "iron" and x.cut)
    assert (p.count, p.amount) == (0, 0.9)
    for _ in range(9):
        bs.pay_assay(pc, "iron", {"bars": 0.1})
    left = [x for x in bs.rack(pc) if x.material == "iron"]
    assert sum(x.amount for x in left) == pytest.approx(1.0)
