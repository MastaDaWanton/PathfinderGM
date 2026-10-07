"""The alchemy bench's rules (docs/alchemy-revamp-plan.md §6-§9, §12, §20.1 lane 6;
contracts §6, §8; lane F).

On the real shelf (lane D's data, lane E's formulae). The product's documents are driven
through the real engine where it matters: a brewed potion drunk, a brewed flask thrown.
Each test names the defect it prevents.
"""
from __future__ import annotations

import pytest

from rules import alchemist as al
from rules import alchemy_items as items
from rules import formulae, inprogress
from rules import worldclass as wc
from rules.crafting import from_stock_dict
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _pc(level: int = 1, **carry):
    pc = load_pc("fixtures/pc-kesst.json")
    pc.inventory.clear()
    pc.stock.clear()
    pc.herb_known.clear()
    pc.track("alchemist").level = level
    for k, n in carry.items():
        pc.carry(k.replace("_", "-"), n)
    formulae.grant_starting(pc)
    return pc


def _plan(pc, method, body, *, lab=False, protected=""):
    where = {"lab": {"kind": "owned", "place": "p", "fume_hood": True} if lab else None,
             "kit": True, "fight": False,
             "protected": protected or ("the laboratory's fume hood" if lab else "")}
    return al.plan_step(pc, pc.track("alchemist"), method, body, where=where)


def _make(pc, method, body, tier=1, **kw):
    plan = _plan(pc, method, body, **kw)
    assert plan.problems == [], plan.problems
    al.spend(pc, plan.consumes)
    made = al.make(plan, tier, now=0)
    return plan, al.land(pc, plan, made, now=0)


# --- trait inheritance (plan §6) -------------------------------------------------------------

def test_same_named_traits_add_capped_at_the_level():
    """Plan §6.2: brimstone's and lamp oil's fire-damage-struck are one trait; their grades
    add (Ryza's 2 + 5 = 7), capped at the Alchemist level. At Alchemist 1 nothing merges
    past grade 1; at 2 the pair is grade 2, and the card says what the cap held back."""
    one = items.pool([{"material": "brimstone"}, {"material": "lamp-oil"}], level=1)
    fire = next(r for r in one["traits"] if r["key"] == "damage.fire.struck")
    assert (fire["raw"], fire["grade"], fire["capped"]) == (2, 1, True)
    two = items.pool([{"material": "brimstone"}, {"material": "lamp-oil"}], level=2)
    fire2 = next(r for r in two["traits"] if r["key"] == "damage.fire.struck")
    assert fire2["grade"] == 2 and not fire2["capped"]
    assert set(fire2["from"]) == {"brimstone", "lamp-oil"}


def test_a_grade_is_read_from_the_rule_row():
    """content/rules/alchemy-grades.json: dice count times g, a save's DC +2 a grade above
    1, a condition's duration times g."""
    assert items.graded({"type": "damage", "dice": "1d6"}, 3)["dice"] == "3d6"
    gate = items.graded({"type": "save_gate", "target": "fort", "dc": 12,
                         "on_failure": [{"type": "apply_condition", "target": "sickened",
                                         "duration": {"amount": 2, "unit": "round"}}]}, 2)
    assert gate["dc"] == 14 and gate["on_failure"][0]["duration"]["amount"] == 4


def test_a_potion_carries_at_most_three_benefits_and_its_drawbacks():
    """Plan §6.3: a potion has three slots; the rest of the pool is shown with its reason,
    and the drawbacks of every material whose benefit is carried come along (Morrowind's
    rule) and take no slot."""
    p = items.pool([{"material": m} for m in ("bear-hairs", "alum", "font-water",
                                              "fullers-earth", "strong-spirits")], level=3)
    got = items.choose(p, family="potion", picks=None, level=3)
    assert len(got["traits"]) <= 3
    over = [r for r in got["rows"] if not r["picked"] and "slots" in r["reason"]]
    assert over, [r["reason"] for r in got["rows"]]
    used = {m for r in got["traits"] for m in r["from"]}
    assert all(set(d["from"]) & used for d in got["drawbacks"])


def test_a_trait_the_family_cannot_deliver_is_dropped_with_its_reason():
    """Plan §5.3: a family carries only the routes it delivers; a struck fire in a vial is
    shown dimmed with the reason, never silently kept."""
    p = items.pool([{"material": "brimstone"}], level=1)
    got = items.choose(p, family="potion", level=1)
    row = next(r for r in got["rows"] if r["key"] == "damage.fire.struck")
    assert not row["picked"] and "cannot carry" in row["reason"]


def test_filter_strips_every_drawback_and_keeps_them_on_the_cloth():
    """Plan §7: Filter's filtrate carries no drawback at x0.9, and the precipitate holds
    what the cloth kept back. Owner Q3.1: Precipitate is Filter's solid end."""
    pc = _pc(2, brimstone=1, lamp_oil=1)
    _p, landed = _make(pc, "dissolve", {"inputs": ["inv:brimstone"],
                                        "solvent": "inv:lamp-oil"})
    sol = landed[0]["key"]
    plan, landed = _make(pc, "filter", {"inputs": [f"stock:{sol}"]})
    forms = {x["record"]["form"]: x["record"] for x in landed}
    assert forms["filtrate"]["drawbacks"] == [] and forms["filtrate"]["filtered"] == 1
    assert forms["precipitate"]["drawbacks"]
    assert items.multipliers(forms["filtrate"])["potency"] < \
        items.multipliers(dict(forms["filtrate"], filtered=0))["potency"]


def test_a_finished_product_is_never_an_input():
    """Ryza's dead end (plan §6.3): a potion cannot go back into the glass."""
    pc = _pc(1)
    rec = items.record_for_formula("alchemists-fire", bought=False)
    key = items.put(pc, rec, 1)
    plan = _plan(pc, "dissolve", {"inputs": [f"stock:{key}"], "solvent": "inv:x"})
    assert any("cannot go back into the glass" in p for p in plan.problems)


# --- what the record keeps, and what it reads back as ----------------------------------------

def test_quality_reaches_the_stock_and_the_record_keeps_no_numbers():
    """inv §0.1, measured on the old chain: `preview` multiplied potency and the stock said
    1.0, so a Superior flask did what a Crude one did. Now the record keeps ids and grades,
    the build scales by quality on read, and the stock's specs are the build's."""
    pc = _pc(1, brimstone=1, lamp_oil=1, clay_flask=2)
    _p, landed = _make(pc, "dissolve", {"inputs": ["inv:brimstone"],
                                        "solvent": "inv:lamp-oil"})
    sol = f"stock:{landed[0]['key']}"
    plan = _plan(pc, "bottle", {"inputs": [sol], "vessel": "inv:clay-flask",
                                "formula": "alchemists-fire"})
    sound = items.build(al.make(plan, 1)[0])
    fine = items.build(al.make(plan, 2)[0])
    core = lambda b: next(s for s in b["specs"] if s["type"] == "damage" and s.get("book"))
    assert core(sound)["dice"] == "1d6" and core(fine)["dice"] == "1d6+1"
    rec = al.make(plan, 2)[0]
    # `steps` is the quality index of each earlier step a trait came through (the
    # solution's tier here): an index on the ladder, like `quality_index`, never a number
    # to run — the build turns it into a multiplier on read.
    assert all(set(t) <= {"key", "grade", "from", "essence", "via", "steps"}
               for t in rec["traits"])
    assert all(isinstance(q, int) for t in rec["traits"] for q in t.get("steps") or ())
    st = items.to_stock(rec, 1)
    assert st.specs == fine["specs"]


def test_a_corrected_material_fixes_every_bottle_on_the_next_load(monkeypatch):
    """CLAUDE.md's derived-cache lesson: the stored specs are a cache, rebuilt from the
    record on every load and compared by content, so a corrected reagent document reaches
    a bottle already on the shelf."""
    pc = _pc(2, brimstone=1, lamp_oil=1)
    _p, landed = _make(pc, "dissolve", {"inputs": ["inv:brimstone"],
                                        "solvent": "inv:lamp-oil"})
    saved = pc.stock[landed[0]["key"]].as_dict()
    real = items.product_specs

    def louder(mid):
        out = real(mid)
        for s in out:
            if s.get("type") == "damage" and s.get("damage_type") == "fire":
                s["dice"] = "1d8"
        return out

    monkeypatch.setattr(items, "product_specs", louder)
    back = from_stock_dict(saved)
    assert isinstance(back, items.AlchemyStock) and back.id == pc.stock[landed[0]["key"]].id
    fire = next(l for l in items.build(back.record)["lines"] if l.get("key") ==
                "damage.fire.struck")
    assert "2d8" in fire["text"]


def test_old_alchemist_work_is_never_rebuilt():
    """Contracts §6: old work (a row with no record) stays exactly as it was. The row is in
    the old chain bench's real shape, `from_materials` included (every old preview wrote
    the chain's materials; tests/alchemy_migration/old-items.json): a plain alchemist row
    WITHOUT materials is a bought product, finished work rather than old (lane I)."""
    d = {"base": "Brimstone Sealed Flask", "craft": "alchemist", "count": 2,
         "from_materials": ["brimstone", "lamp-oil"],
         "specs": [{"type": "damage", "dice": "2d6", "damage_type": "fire"}]}
    st = from_stock_dict(d)
    assert not isinstance(st, items.AlchemyStock) and st.specs == d["specs"]
    pc = _pc(1)
    pc.stock["old#1"] = st
    row = next(i for i in al.shelf(pc) if i.key == "stock:old#1")
    assert row.old and al.fit_reason("dissolve", "inputs", row) == row.old


def test_a_bought_flask_is_the_crafted_document():
    """Owner Q8.3: shop items are the same documents as crafted ones, at Sound. Before,
    a bought alchemist's fire did nothing (inv §0)."""
    rec = items.record_for_formula("alchemists-fire", bought=True)
    st = items.to_stock(rec, 1)
    assert st.bought and st.specs and st.price_gp == 20 and st.how == ["throw"]
    # `pricing.alchemy_worth` (lane H) reads `formula` off a stock row: every product says.
    assert st.formula == "alchemists-fire"


# --- volatility and the toxic (plan §8) --------------------------------------------------------

def test_containment_makes_the_mishap_smaller_and_the_dc_lower():
    """Plan §4.2: Containment, -1 DC a pick on a volatile step, each mishap's dice one step
    smaller (1d6 -> 1d4 -> 1d3 -> 1, never below 1 point)."""
    assert al._smaller("1d6", 1) == "1d4" and al._smaller("1d6", 2) == "1d3"
    assert al._smaller("1d4", 5) == "1"
    pc = _pc(4, brimstone=1, white_vinegar=1)
    before = _plan(pc, "dissolve", {"inputs": ["inv:brimstone"],
                                    "solvent": "inv:white-vinegar"})
    pc.track("alchemist").perks["containment"] = 1
    after = _plan(pc, "dissolve", {"inputs": ["inv:brimstone"],
                                   "solvent": "inv:white-vinegar"})
    assert after.dc == before.dc - 1
    assert after.mishaps[0][2]["dice"] == "1d3"            # brimstone's 1d4, one smaller


def test_a_toxic_reagent_hurts_at_the_bench_unless_protected():
    """Plan §8.4: quicksilver's tax moved from whoever drinks the product to the
    alchemist working it, unless a mask and gloves or a fume hood spare them."""
    pc = _pc(2, quicksilver=1, distilled_water=1)
    body = {"inputs": ["inv:quicksilver", "inv:distilled-water"]}
    bare = _plan(pc, "react", body)
    assert bare.problems == [] and [m for m, *_ in bare.toxics] == ["quicksilver"]
    assert _plan(pc, "react", body, protected="your mask and gloves").toxics == []
    assert _plan(pc, "react", body, lab=True).toxics == []
    e = Engine(_scene(pc), Dice(seed=3))
    out = al.apply_rule(e, pc, bare.toxics, kind="toxic")
    assert out and any(x.get("save") or x.get("kind") for o in out for x in o.effects)


def _scene(pc):
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    return s


# --- the laboratory and rarity (plan §14) ------------------------------------------------------

def test_rare_work_and_distilling_need_a_laboratory():
    pc = _pc(2, fullers_earth=1, quenching_clay=1, strong_spirits=2)
    rare = _plan(pc, "dissolve", {"inputs": ["inv:quenching-clay"],
                                  "solvent": "inv:strong-spirits"})
    assert any("needs a laboratory" in p for p in rare.problems)
    dist = _plan(pc, "distill", {"inputs": ["inv:strong-spirits"]})
    assert any("needs a laboratory" in p for p in dist.problems)
    lab = _plan(pc, "distill", {"inputs": ["inv:strong-spirits"]}, lab=True)
    assert lab.problems == [] and lab.concentration == 1
    assert {"label": "laboratory", "value": 2} in lab.terms
    assert any(t["label"] == "concentration step 1" for t in lab.dc_terms)


def test_a_corrosive_input_refuses_a_metal_vessel():
    """Contracts §10.2 via `item_tags`: an iron flask is metal; vinegar eats it."""
    pc = _pc(1, white_vinegar=1, iron_flask=1, glass_vial=1)
    metal = _plan(pc, "bottle", {"inputs": ["inv:white-vinegar"], "vessel": "inv:iron-flask"})
    assert any("eat through" in p for p in metal.problems)
    glass = _plan(pc, "bottle", {"inputs": ["inv:white-vinegar"], "vessel": "inv:glass-vial"})
    assert not any("eat through" in p for p in glass.problems)


# --- transmute (plan §9) -----------------------------------------------------------------------

def test_transmute_goes_one_band_rarer_within_the_kind():
    """Plan §9: the same kind, exactly one band rarer, an essence shared. Two bands, or a
    different kind, is refused in words."""
    from rules import materials

    shelf = materials.alchemy_shelf()
    found = None
    for mid, d in sorted(shelf.items()):
        got = al.transmute_candidates(mid, 3)
        if got and d["tier"] == "common":
            found = (mid, got[0]["id"])
            break
    assert found, "no common material on the shelf transmutes"
    a, b = found
    assert al.transmute_refusal(a, b) == ""
    other = next(m for m, d in shelf.items() if d["kind"] != shelf[a]["kind"]
                 and d["tier"] == shelf[b]["tier"])
    assert "own kind" in al.transmute_refusal(a, other)
    far = next(m for m, d in shelf.items() if d["kind"] == shelf[a]["kind"]
               and wc.tier_rank(d["tier"]) == wc.tier_rank(shelf[a]["tier"]) + 2)
    assert "one band rarer" in al.transmute_refusal(a, far)


def test_a_transmutation_waits_a_day_and_lands_in_the_satchel():
    """Plan §9, §12.3: one day In progress, collected when done (the shared section)."""
    from rules import materials

    shelf = materials.alchemy_shelf()
    a, b = next((m, al.transmute_candidates(m, 3)[0]["id"]) for m in sorted(shelf)
                if shelf[m]["tier"] == "common" and al.transmute_candidates(m, 3)
                and shelf[m]["kind"] != "herb" and not materials.is_herb_view(shelf[m]))
    pc = _pc(3, **{a.replace("-", "_"): 2})
    plan, landed = _make(pc, "transmute", {"inputs": [f"inv:{a}"], "target": b}, lab=True)
    assert landed[0]["waits"] == 1440 and plan.minutes == 60
    key = landed[0]["key"]
    assert not inprogress.collect(pc, key, now=100, here=None)["ok"]
    got = inprogress.collect(pc, key, now=1500, here="p")
    assert got["ok"] and pc.inventory.get(b) == 1 and key not in pc.stock


# --- the engine: what a product does in play ---------------------------------------------------

def test_a_brewed_cure_light_wounds_heals_its_drinker_once_collected():
    """End to end: wintergreen essence bottled in a glass vial by experiment is a potion of
    cure light wounds; it sets two hours (Brew Potion, plan §11.4) and the use door refuses
    it until collected; drunk, it heals through the spell's own documents at the caster
    level the bench stamped (`formulae.caster_level`, not lane C's 2 x level - 1 fallback).
    """
    pc = _pc(1, wintergreen_essence=1, glass_vial=1)
    plan, landed = _make(pc, "bottle", {"inputs": ["inv:wintergreen-essence"],
                                        "vessel": "inv:glass-vial"}, tier=2)
    assert plan.formula["id"] == "potion-of-cure-light-wounds"
    key = landed[0]["key"]
    st = pc.stock[key]
    assert st.holds_spell == "cure-light-wounds"
    assert st.caster_level == formulae.caster_level("cure-light-wounds", 2)
    s = _scene(pc)
    e = Engine(s, Dice(seed=5))
    pc.hp = 1
    from rules.intents import IntentError

    try:
        e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "drink",
                           "params": {"item": key, "how": "drink"}}]))
    except IntentError:
        pass
    assert pc.hp == 1 and pc.stock[key].count == 1          # still setting: refused
    s.clock_minutes = 200
    assert inprogress.collect(pc, key, now=200, here=None)["ok"]
    e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "drink",
                       "params": {"item": key, "how": "drink"}}]))
    assert pc.hp > 1


def test_a_brewed_alchemists_fire_is_thrown_as_a_splash_weapon():
    """A bench-made flask is lane C's splash weapon: a ranged touch attack, the book's
    burn, and the splash on the neighbour."""
    from rules.bestiary import instantiate

    pc = _pc(1, brimstone=1, lamp_oil=1, clay_flask=1)
    _p, landed = _make(pc, "dissolve", {"inputs": ["inv:brimstone"],
                                        "solvent": "inv:lamp-oil"})
    _p, landed = _make(pc, "bottle", {"inputs": [f"stock:{landed[0]['key']}"],
                                      "vessel": "inv:clay-flask",
                                      "formula": "alchemists-fire"})
    key = landed[0]["key"]
    s = _scene(pc)
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.add(instantiate("thug", scene=s, name="the other thug"))
    e = Engine(s, Dice(seed=7))
    e._ensure_encounter("pc")
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (5, 10)
    s.positions["c2"] = (6, 10)
    s.resync_zones()
    res = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "she throws it",
                             "params": {"item": key, "how": "throw", "to": "c1"}}]))
    if res.status != "complete":
        assert res.awaiting["die"] == "1d20"
        res = e.resume(face=20)
    told = " ".join(o.tell for o in res.outcomes)
    effects = [x for o in res.outcomes for x in o.effects]
    assert any(x.get("kind") == "splash" for x in effects), told
    assert key not in pc.stock or pc.stock[key].count == 0
