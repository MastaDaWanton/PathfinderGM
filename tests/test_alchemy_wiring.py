"""The seams wave 1 left between the alchemy lanes, closed (the wiring lane, 2026-10-07).

Lane G built the laboratory, its rent and its line; lane F built the bench that should
charge the one and say the other. Lane C built the drink door and lane F the potions that
needed it to carry more; lane A built the danger door and lane F a private copy beside
it. Each test here names the seam it closes and what was measured across it.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from django.test import Client, override_settings

from play import alchemy_views
from play import campaign as cm
from rules import alchemist as al
from rules import alchemy_items as items
from rules import consumables, formulae, goods, keepers, knowledge, market, materials, places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

SYNTHETIC = loader.load_cached("fixtures/synthetic-world.json")

LAB = {"kind": "town", "place": "quiet-the-bread-stall", "keeper": None,
       "rate_cp_per_hour": 20, "fume_hood": True}


# --- the API, with the laboratory switchable -------------------------------------------------

@pytest.fixture
def where(monkeypatch):
    state = {"lab": None}
    monkeypatch.setattr(places, "laboratory_here", lambda scene, known=(): state["lab"])
    return state


@pytest.fixture
def bench(tmp_path, where):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        alchemy_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"),
                          start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.purse = {"gp": 200}
        goods.deliver(c.scene, pc, goods.good("alchemist's field kit"))
        c.save()
        yield Client()
        cm._LIVE.clear()
        alchemy_views._PENDING.clear()


def _pc():
    return cm.current().scene.pc()


def post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def test_a_town_laboratory_charges_its_hours_at_the_roll(bench, where):
    """Seam G->F (plan §14): `market.lab_rent` beside `Scene.advance`. Ten minutes'
    Dissolve at 2 sp an hour is 4 cp (a copper begun is a copper paid), taken from the
    purse at the roll; your own laboratory is free."""
    where["lab"] = dict(LAB)
    _pc().carry("brimstone", 2)
    _pc().carry("lamp-oil", 2)
    cm.current().save()
    body = {"method": "dissolve", "inputs": ["inv:brimstone"], "solvent": "inv:lamp-oil"}
    chk = post(bench, "/api/alchemy/check", body).json()
    assert chk["rent_cp"] == 4 and chk["minutes"] == 10, {k: chk.get(k) for k in (
        "rent_cp", "minutes", "problems", "lab", "units")}
    before = goods.in_copper(_pc().purse)
    clock = cm.current().scene.clock_minutes
    r = post(bench, "/api/alchemy/roll", dict(body, face=20)).json()
    assert r["rent"] and r["rent"][0]["cp"] == 4
    assert goods.in_copper(_pc().purse) == before - 4
    assert cm.current().scene.clock_minutes == clock + 10
    where["lab"] = dict(LAB, kind="owned", rate_cp_per_hour=0)
    before = goods.in_copper(_pc().purse)
    r = post(bench, "/api/alchemy/roll", dict(body, face=20)).json()
    assert r["rent"] == [] and goods.in_copper(_pc().purse) == before


def test_a_purse_that_cannot_pay_the_hours_is_refused_before_the_roll(bench, where):
    """Measured before: the roll's `goods.spend` failed quietly when the purse was short,
    and the step was worked in the town's laboratory for nothing. Now the check says so
    in words and the roll refuses with the clock and the shelf untouched."""
    where["lab"] = dict(LAB)
    _pc().carry("brimstone", 1)
    _pc().carry("lamp-oil", 1)
    _pc().purse = {"cp": 2}
    cm.current().save()
    body = {"method": "dissolve", "inputs": ["inv:brimstone"], "solvent": "inv:lamp-oil"}
    chk = post(bench, "/api/alchemy/check", body).json()
    assert any("laboratory wants 4 cp" in p for p in chk["problems"]), chk["problems"]
    clock = cm.current().scene.clock_minutes
    r = post(bench, "/api/alchemy/roll", dict(body, face=20))
    assert r.status_code == 400 and "laboratory wants" in r.json()["error"]
    assert cm.current().scene.clock_minutes == clock
    assert _pc().inventory.get("brimstone") == 1 and goods.in_copper(_pc().purse) == 2


def test_an_assay_in_a_rented_laboratory_pays_for_its_ten_minutes(bench, where):
    """The assay takes the laboratory's +2 (it is the alchemist's own check there), so it
    pays the glass's time like any step. Before, a rented laboratory's assay was free."""
    where["lab"] = dict(LAB)
    _pc().carry("brimstone", 1)
    cm.current().save()
    before = goods.in_copper(_pc().purse)
    a = post(bench, "/api/alchemy/assay", {"material": "brimstone", "face": 10}).json()
    assert a["rent"] and goods.in_copper(_pc().purse) == before - a["rent"][0]["cp"] > 0


def test_the_state_says_where_a_laboratory_is(bench, where):
    """Seam G->F: `places.laboratory_line` reaches the bench. Before, the state said
    nothing about where to find one, and Distill's "Needs a laboratory" read the same in a
    city with one two streets away as in a hamlet with none. Standing in one, no line."""
    st = bench.get("/api/alchemy/state").json()
    assert "laboratory" in st["where"]["lab_line"], st["where"]
    where["lab"] = dict(LAB)
    assert bench.get("/api/alchemy/state").json()["where"]["lab_line"] == ""


def test_bottling_takes_no_coin(bench, where):
    """The owner, 2026-10-07: "Ingredients only". A bottle at the field kit spends its
    materials and not a copper (lane H's `pricing.coin_to_make` is built and not called)."""
    _pc().carry("brimstone", 1)
    _pc().carry("lamp-oil", 1)
    _pc().carry("clay-flask", 1)
    cm.current().save()
    purse = goods.in_copper(_pc().purse)
    for body in ({"method": "dissolve", "inputs": ["inv:brimstone"],
                  "solvent": "inv:lamp-oil"}, None):
        if body is None:
            sol = next(k for k, s in _pc().stock.items() if isinstance(s, items.AlchemyStock)
                       and s.record.get("form") == "solution")
            body = {"method": "bottle", "inputs": [f"stock:{sol}"],
                    "vessel": "inv:clay-flask", "formula": "alchemists-fire"}
        r = post(bench, "/api/alchemy/roll", dict(body, face=20)).json()
        f = post(bench, "/api/alchemy/finish", {"token": r["token"], "score": 0.5})
        assert f.status_code == 200, f.content[:300]
    assert goods.in_copper(_pc().purse) == purse


# --- the kit, the keeper, the counter -------------------------------------------------------

def test_the_field_kit_is_a_real_good_and_opens_the_bench():
    """Seam G/H->F. Lane G's `has_alchemy_kit` looked for "alchemist's field kit" in the
    pack, and no GEAR row, gear.json row or counter had one: measured on build/alchemy, 8
    API tests answered "Needs a field kit or a laboratory" the day lane G merged. The kit
    is the book's alchemy crafting kit at its price and weight (UE p.77: 25 gp, 5 lb),
    sold by the alchemist and the laboratory, and delivered it opens the field bench."""
    assert goods.GEAR["alchemist's field kit"] == {"name": "alchemist's field kit",
                                                  "cost_gp": 25.0, "lb": 5}
    from rules import gear

    assert gear.row_for("alchemist's field kit")[0] == "alchemist's field kit"
    assert "alchemist's field kit" in market.gear_of("market:alchemist")
    assert "alchemist's field kit" in goods.stocked_at("laboratory")
    assert "alchemist's mask and gloves" in goods.stocked_at("laboratory")
    pc = load_pc("fixtures/pc-kesst.json")
    pc.stock.clear()
    pc.goods.clear()
    assert not places.has_alchemy_kit(pc)
    assert al.methods_view(1, al.where_here(None, pc))[0]["lock_reason"] == \
        "Needs a field kit or a laboratory"
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    goods.deliver(s, pc, goods.good("alchemist's field kit"))
    assert places.has_alchemy_kit(pc)
    goods.deliver(s, pc, goods.good("alchemist's mask and gloves"))
    assert al.protected(pc, None) == "your mask and gloves"


def test_the_laboratory_counter_sells_the_alchemists_goods_not_the_general_store():
    """Before, the laboratory fell to `stocked_at`'s everything-else branch: its keeper
    sold rope, a tent and a crowbar, and drew the general pool."""
    shelf = goods.goods_at("laboratory")
    names = {g.name for g in shelf}
    assert "alchemist's fire" in names and "alchemist's field kit" in names
    assert "hemp rope" not in names and "tent" not in names
    assert market.place_draw("laboratory") == ("alchemist", "potions")
    assert market.consumables_at("laboratory") == ("alchemist",)


def _city_lab():
    city = next(SYNTHETIC.get(r["id"]) for r in SYNTHETIC.play["settlements"]
                if SYNTHETIC.get(r["id"]).name == "Caddonbury")
    lab = next(p for p in places.home_set(city) if p.name == "the laboratory")
    scene = Scene(location_id=city.id)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=3), world=SYNTHETIC)
    engine.place_party(lab.id)
    keepers.staff(engine)
    return scene, engine, lab


def test_the_laboratory_keeper_teaches_the_trade():
    """Seam G->A: the keeper the laboratory stands up is "the alchemist", and the
    alchemy lore's teacher row names that occupation, so the keeper is somebody you can
    ask about a reagent or learn a formula from."""
    from rules import population

    teacher = knowledge.lore(knowledge.ALCHEMIST)["teacher"]
    assert "alchemist" in teacher["works"]
    assert {"alchemist", "chymist"} <= set(teacher["words"])
    scene, engine, lab = _city_lab()
    keeper = keepers.keeper_in(scene, lab.id)
    assert keeper is not None
    assert knowledge.teaches(keeper, population.of_ref(scene, keeper.ref), knowledge.ALCHEMIST)


def _shelves(kind: str, days: int = 30):
    out = []
    for day in range(days):
        out += market.on_sale("aaaabbbbcccc", kind, day, {}, counter_kind=kind, scale="city")
    return out


def _catalogue(m) -> str:
    return str((materials.get(str(getattr(m, "id", "") or "")) or {}).get("catalogue") or "")


def test_no_magic_on_an_alchemists_counter():
    """Measured 2026-10-07: of the 238 materials the alchemist's daily draw held, 164 were
    other crafts' (83 the enchanter's, 54 the blacksmith's, 27 the leatherworker's), because
    `alchemist.obtainable` is shelf-wide for the acquisition hub and `priced_from` took it
    whole; with the base value capping a city shelf at 8,000 gp the alchemist shelved
    Flaming Burst Essence, Warding Essence IV and Amulet Blanks. And the laboratory's
    keeper, on the general draw, shelved Amulet and Wand Blanks on 9 of 20 days. Over 30
    days in a city, both counters now sell alchemy and nothing of another craft's."""
    for kind in ("market:alchemist", "laboratory"):
        cats = {_catalogue(m) for m in _shelves(kind)} - {""}
        assert cats == {"alchemist-materials"}, (kind, cats)


def test_no_counter_but_a_designed_one_sells_the_enchanters_magic():
    """The general draw (a merchants' row, a warehouse) loses the enchanter's catalogue;
    the curio stall, whose row names the enchanter's bench, keeps it on purpose."""
    assert "enchanter-materials" not in {_catalogue(m) for m in _shelves("merchants row")}
    assert "enchanter-materials" in {_catalogue(m) for m in _shelves("market:stall-curios")}


# --- a derived spell potion carries more than its spell (plan §6.3) ---------------------------

def _scene(pc):
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    return s


def test_a_derived_spell_potion_carries_traits_beside_its_spell():
    """Seam C->F. `consumables.spell_of` returned None for any potion with documents, so
    one inherited trait beside a derived spell turned the spell off, and lane F had to make
    every derived spell fill the bottle alone ("the spell holds the bottle alone"). Plan
    §6.3 promises "a spell potion its spell plus two". Now the slots are free, and drunk,
    both the spell (divine favor's luck to attack) and the trait (bear hairs' Con) land."""
    p = items.pool([{"material": "bear-hairs"}], level=1)
    got = items.choose(p, family="potion", formula=formulae.get("potion-of-divine-favor"),
                       picks=["ability_mod.con.ingest"], level=1)
    assert got["free"] == 2 and [r["key"] for r in got["traits"]] == ["ability_mod.con.ingest"]
    rec = items.new_record(family="potion", formula="potion-of-divine-favor",
                           traits=got["traits"], drawbacks=got["drawbacks"],
                           vessel="glass-vial", made_minute=0)
    pc = load_pc("fixtures/pc-kesst.json")
    key = items.put(pc, rec, 1)
    st = pc.stock[key]
    assert consumables.spell_of(st) == {"spell": "divine-favor", "cl": rec["caster_level"]}
    e = Engine(_scene(pc), Dice(seed=5))
    res = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "drink",
                             "params": {"item": key, "how": "drink"}}],
                           origin="author:test"))
    assert res.status == "complete", res
    sources = " | ".join(f"{x.source} {x.origin}" for x in pc.effects)
    assert "Divine Favor" in sources or "divine-favor" in sources, sources
    assert any(str((m or {}).get("target")) == "con"
               for x in pc.effects for m in (x.modifiers or ())), sources


def test_the_44_still_keep_their_own_documents():
    """The other half of the contract (`tests/test_magicitem.py`): an authored potion's
    documents ARE its spell, so it never resolves the spell a second time."""
    rec = items.record_for_formula("potion-of-heroism")
    st = items.to_stock(rec)
    assert st.specs and not items.spell_beside(rec)
    assert consumables.spell_of(st) is None


# --- the one danger door (law 2) -----------------------------------------------------------

def test_every_toxic_document_reaches_the_alchemist_through_one_door():
    """Seam A->F. `knowledge.apply_danger` read a danger through the drink door, and all
    18 of 18 alchemy toxic documents (a Fortitude save gating Constitution damage) came
    back "nothing in Quicksilver works when swallowed": nothing applied, so lane F wrote
    `alchemist.rule_intents`, a second applicator. Now the door turns every one into
    intents and the bench calls it, stamped rule:toxic:<material>."""
    shelf = materials.alchemy_shelf()
    toxic = {mid: d["toxic"] for mid, d in shelf.items() if d.get("toxic")}
    assert len(toxic) >= 18
    dropped = [mid for mid, spec in toxic.items()
               if not consumables.document_intents([spec], "pc", "t", mid)]
    assert dropped == []
    assert not hasattr(al, "rule_intents")
    pc = load_pc("fixtures/pc-kesst.json")
    e = Engine(_scene(pc), Dice(seed=3))
    stamped = []
    real = e.validate

    def validate(raw, **kw):
        stamped.append(kw.get("origin"))
        return real(raw, **kw)

    e.validate = validate
    out = al.apply_rule(e, pc, [("quicksilver", "Quicksilver", toxic["quicksilver"])],
                        kind="toxic")
    assert out, "the toxic document applied nothing"
    assert stamped == ["rule:toxic:quicksilver"]
    assert any(o.op == "save" for o in out), [o.op for o in out]


# --- time and the hands on an intermediate (plan §5.5, §6.1, §12.1) --------------------------

def _rpc(level: int = 1, **carry):
    pc = load_pc("fixtures/pc-kesst.json")
    pc.inventory.clear()
    pc.stock.clear()
    pc.herb_known.clear()
    pc.track("alchemist").level = level
    for k, n in carry.items():
        pc.carry(k.replace("_", "-"), n)
    formulae.grant_starting(pc)
    return pc


def _plan(pc, method, body, now=0):
    where = {"lab": None, "kit": True, "fight": False, "protected": ""}
    return al.plan_step(pc, pc.track("alchemist"), method, body, where=where, now=now)


def _dice_of(rec, key="damage.fire.struck"):
    b = items.build(rec)
    return next(s["dice"] for s in b["specs"] if s.get("type") == "damage"
                and not s.get("book") and s.get("route") != "splash")


def test_an_intermediates_quality_carries_into_the_bottle():
    """Plan §6.1 ("grades and all") and herbalism's running potency: before, only the last
    step's hands counted — a Flawless solution bottled at Sound made exactly the flask a
    Crude one did. Brimstone in lamp oil at Alchemist 2 (fire grade 2), the solution made
    Crude and then at the alchemist's ceiling, each bottled at Sound as a house flask: the
    two flasks' fire now differs, and the record holds the solution's tier, not a number."""
    flasks = {}
    for low in (True, False):
        pc = _rpc(2, brimstone=1, lamp_oil=1, clay_flask=1)
        plan = _plan(pc, "dissolve", {"inputs": ["inv:brimstone"], "solvent": "inv:lamp-oil"})
        assert plan.problems == [], plan.problems
        tier = 0 if low else plan.ceiling
        al.spend(pc, plan.consumes)
        landed = al.land(pc, plan, al.make(plan, tier, now=0), now=0)
        plan = _plan(pc, "bottle", {"inputs": [f"stock:{landed[0]['key']}"],
                                    "vessel": "inv:clay-flask", "picks": ["damage.fire.struck"]})
        assert plan.problems == [], plan.problems
        rec = al.make(plan, 1, now=0)[0]
        assert rec["traits"][0]["steps"] == [tier]
        flasks[tier] = _dice_of(rec)
    assert len(set(flasks.values())) == 2, flasks


def test_a_light_sensitive_intermediate_loses_a_grade_a_day():
    """Plan §5.5: `light_sensitive`, "an intermediate left unsealed loses one grade a
    day". Nothing read it: the trait was data on nine materials. A grade-2 solution with
    olive oil in it is grade 1 a day later and has nothing left on the second; the stored
    record keeps its grades (time is derived, never written)."""
    rec = items.new_record(family=items.INTERMEDIATE, form="solution",
                           traits=[{"key": "damage.fire.struck", "grade": 2,
                                    "from": ["brimstone", "olive-oil"]}],
                           made_minute=0)
    assert items.light_sensitive(rec)
    assert items.aged(rec, 1439)["traits"][0]["grade"] == 2
    assert items.aged(rec, 1440)["traits"][0]["grade"] == 1
    assert items.aged(rec, 2880)["traits"] == []
    assert rec["traits"][0]["grade"] == 2
    plain = items.new_record(family=items.INTERMEDIATE, form="solution",
                             traits=[{"key": "damage.fire.struck", "grade": 2,
                                      "from": ["brimstone", "lamp-oil"]}], made_minute=0)
    assert not items.light_sensitive(plain)
    assert items.aged(plain, 10 * 1440)["traits"][0]["grade"] == 2


def test_a_solution_past_its_keeping_is_refused_at_the_bench():
    """Plan §12.1: solutions, filtrates and admixtures keep 3 days. The Keeps column was a
    shelf label nothing asked, so a day-40 solution reacted as well as a fresh one."""
    pc = _rpc(1, brimstone=1, lamp_oil=1, clay_flask=1)
    plan = _plan(pc, "dissolve", {"inputs": ["inv:brimstone"], "solvent": "inv:lamp-oil"})
    al.spend(pc, plan.consumes)
    landed = al.land(pc, plan, al.make(plan, 1, now=0), now=0)
    body = {"inputs": [f"stock:{landed[0]['key']}"], "vessel": "inv:clay-flask",
            "formula": "alchemists-fire"}
    assert _plan(pc, "bottle", body, now=3 * 1440 - 1).problems == []
    late = _plan(pc, "bottle", body, now=3 * 1440)
    assert any("has gone off" in p and "3 days" in p for p in late.problems), late.problems


def test_a_flask_kept_past_its_year_is_refused_at_the_use_door():
    """Plan §12.1: a splash flask keeps a year. The use door now asks."""
    from rules.intents import IntentError

    rec = items.record_for_formula("alchemists-fire", vessel="clay-flask")
    rec["made_minute"] = 0
    pc = _rpc(1)
    key = items.put(pc, rec, 1)
    s = _scene(pc)
    s.clock_minutes = 525600
    e = Engine(s, Dice(seed=1))
    try:
        res = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "t",
                                 "params": {"item": key, "how": "throw", "square": [3, 3]}}],
                               origin="author:test"))
        told = " ".join(o.tell for o in res.outcomes)
    except IntentError as err:
        told = str(err)
    assert "has gone off" in told, told
    assert pc.stock[key].count == 1


def test_orichalcum_names_the_formula_an_ambiguous_experiment_becomes():
    """Plan §5.8, lane D's proposal (docs/alchemy-review.md item 4): orichalcum grains
    make "an experiment that fits several formulae ... the one the alchemist names, if it
    is within reach". Before, the job was written on the catalyst and nothing read it.
    acid 1 + change 1 in a vial fits two formulae at every level; named, it is the one
    named; a wrong name finds nothing and says nothing."""
    pc = _rpc(1)
    mix = {"traits": [{"key": "x.acid", "essence": "acid", "grade": 1, "from": []},
                      {"key": "x.change", "essence": "change", "grade": 1, "from": []}],
           "drawbacks": [], "materials": []}
    blind = formulae.match(pc, mix, "glass-vial", None)
    assert blind["ambiguous"] == 2 and blind["formula"] is None
    named = formulae.match(pc, mix, "glass-vial", None, aim="potion-of-acid-splash")
    assert named["formula"] == "potion-of-acid-splash" and named["found"]
    assert formulae.match(pc, mix, "glass-vial", None, aim="potion-of-haste")["formula"] is None
    assert "names_formula" in al._catalyst_jobs("orichalcum-grains")


# --- the narrator and the parser (lane C3's two) ----------------------------------------------

def test_a_fight_beat_copied_from_a_combat_example_is_caught():
    """Lane C3, 2026-10-07: a night fight beat shipped "You break contact and the window is
    four running steps away..." word for word from `prompts.COMBAT_EXAMPLES`, because
    `GMAgent._echo_index` indexed EXAMPLES and NPC_EXAMPLES only. Every combat and
    Continue example coming back is now caught."""
    from gm import narration, prompts
    from gm.agent import GMAgent

    echoes = GMAgent._echo_index(SimpleNamespace(_echoes=None))
    for ex in list(prompts.COMBAT_EXAMPLES) + list(prompts.CARRY_ON_EXAMPLES):
        text = prompts.fill_enemy(ex["reply"]["narration"], None)
        r = narration.review(text, echo_index=echoes)
        assert any(f.kind == "echoes-the-examples" for f in r.findings), text[:60]


def test_extinguish_reads_its_roll_as_a_yes_or_a_no():
    """Lane C3: `extinguish`'s `roll` (rolling on the ground, +2) was missing from
    `FLAG_PARAMS`, so a model writing "roll": "false" got the bonus: bool("false")."""
    from rules import intents

    got = intents.parse({"op": "extinguish", "actor": "pc", "because": "t",
                         "params": {"roll": "false"}})
    assert got.params["roll"] is False
    got = intents.parse({"op": "extinguish", "actor": "pc", "because": "t",
                         "params": {"roll": "yes"}})
    assert got.params["roll"] is True


def test_heroism_the_spell_does_what_the_potion_does():
    """The heroism potion row is right (CRB: "+2 morale bonus on attack rolls, saves, and
    skill checks", 10 min/level, so 50 minutes at CL 5). The spell's read-by-hand document
    (content/spells/mechanics/part-09.json, which wins over spells-mechanics.json) wrote
    the skill half as a situational_mod "all skill checks" from before skill_mod `all`
    existed, so a cast heroism's skill bonus reached no roll. It is skill_mod `all` now,
    as are greater and hollow heroism, prayer, good hope and pessimism (the same copy)."""
    from rules import spells

    def bonuses(effects):
        return {(e["type"], e["target"], e["amount"], e["bonus_type"]) for e in effects}

    want = {("combat_mod", "attack", 2, "morale"), ("save_mod", "fort", 2, "morale"),
            ("save_mod", "ref", 2, "morale"), ("save_mod", "will", 2, "morale"),
            ("skill_mod", "all", 2, "morale")}
    assert bonuses(spells.effects_at(spells.get("heroism"), 5)) == want
    potion = next(r for r in json.load(open("content/materials/alchemist-spell-potions.json",
                                            encoding="utf-8"))["potions"]
                  if r["id"] == "potion-of-heroism")
    assert bonuses(potion["effects"]) == want
    greater = {(e["type"], e.get("target"), e.get("amount"), e.get("bonus_type"))
               for e in spells.effects_at(spells.get("heroism-greater"), 11)}
    assert ("save_mod", "will", 4, "morale") in greater and \
        ("skill_mod", "all", 4, "morale") in greater
    # And it reaches a roll: the spell's own documents, landed the way a bottled heroism
    # lands them (`consumables.spell_intents`), put +2 on a skill the sheet rolls.
    pc = load_pc("fixtures/pc-kesst.json")
    e = Engine(_scene(pc), Dice(seed=2))
    before = sum(m.value for m in pc.skill_modifiers("climb"))
    made = consumables.spell_intents({"spell": "heroism", "cl": 5}, "pc", "drunk", e.dice)
    e.run(e.validate(made, origin="spell:heroism"))
    assert sum(m.value for m in pc.skill_modifiers("climb")) - before == 2
