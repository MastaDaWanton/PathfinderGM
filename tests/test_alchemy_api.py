"""The alchemy bench through its API (docs/alchemy-contracts.md §8, lane F).

Driven through the Django test client on a real campaign with the real shelf (lane D's
data, lane E's formulae); lane G's laboratory door is patched onto `rules.places` where a
test needs one, because it has not merged. Each test names the defect it prevents.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings
from django.urls import resolve

from play import alchemy_views
from play import campaign as cm
from rules import formulae, knowledge
from rules.sheet import load_pc

LAB = {"kind": "town", "place": "quiet-the-bread-stall", "keeper": None,
       "rate_cp_per_hour": 20, "fume_hood": True, "name": "the laboratory"}


@pytest.fixture
def where(monkeypatch):
    """Lane G's door, switchable per test: {"lab": dict | None}."""
    from rules import places

    state = {"lab": None}
    monkeypatch.setattr(places, "laboratory_here", lambda scene, known=(): state["lab"],
                        raising=False)
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
        pc.herb_known.clear()
        pc.purse = {"gp": 200}
        c.save()
        yield Client()
        cm._LIVE.clear()
        alchemy_views._PENDING.clear()


def _pc():
    return cm.current().scene.pc()


def _level(n: int):
    _pc().track("alchemist").level = n
    cm.current().save()


def _carry(**counts):
    for iid, n in counts.items():
        _pc().carry(iid.replace("_", "-"), n)
    cm.current().save()


def post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def step(client, body, *, face=20, score=1.0):
    """roll, finish: one step as the page drives it."""
    r = post(client, "/api/alchemy/roll", {**body, "face": face})
    assert r.status_code == 200, r.content[:600]
    rolled = r.json()
    assert rolled["roll"]["success"], rolled
    f = post(client, "/api/alchemy/finish", {"token": rolled["token"], "score": score})
    assert f.status_code == 200, f.content[:600]
    return f.json()


# --- routes ------------------------------------------------------------------------------------

def test_every_alchemy_route_reaches_the_alchemy_bench():
    """The herb bench's measured route-order bug (2026-10-02): a fixed name read as a
    parameter by a pattern declared first answered 404. Every fixed alchemy name resolves
    to its own view, and a material card still resolves to the card."""
    for name in ("state", "check", "roll", "finish", "assay", "identify", "learn", "ask",
                 "collect", "perks", "recipe", "formulary", "codex"):
        assert resolve(f"/api/alchemy/{name}").func.__name__ == f"alchemy_{name}", name
    assert resolve("/api/alchemy/material/brimstone").func.__name__ == "alchemy_material"


# --- state ------------------------------------------------------------------------------------

def test_a_new_alchemist_opens_the_bench_knowing_the_four_classics(bench):
    """Owner Q5.4: alchemist's fire, acid, antitoxin and the tanglefoot bag are known from
    the start. The state lists the methods with their locks in words."""
    st = bench.get("/api/alchemy/state").json()
    assert {f["id"] for f in st["formulae"]} >= set(formulae.starting())
    locks = {m["id"]: m["lock_reason"] for m in st["methods"]}
    assert locks["dissolve"] == "" and locks["distill"] == "Alchemist 2"
    _level(2)
    st = bench.get("/api/alchemy/state").json()
    locks = {m["id"]: m["lock_reason"] for m in st["methods"]}
    assert locks["distill"] == "Needs a laboratory" and locks["react"] == ""


def test_the_shelf_shows_only_what_is_carried_with_hazards_named(bench):
    """UI §6.2: only what you carry; volatile and toxic said in words whether or not the
    rest of the reagent is known (the stakes are stated before every roll, plan §8.1)."""
    _carry(brimstone=2, quicksilver=1)
    rows = {r["key"]: r for r in bench.get("/api/alchemy/state").json()["shelf"]}
    assert set(rows) == {"inv:brimstone", "inv:quicksilver"}
    assert "volatile" in rows["inv:brimstone"]["badges"]
    assert "toxic to handle" in rows["inv:quicksilver"]["badges"]
    assert "combustible" not in rows["inv:brimstone"]["badges"]       # not yet known
    assert rows["inv:brimstone"]["unknown"] >= 3


# --- a step end to end ------------------------------------------------------------------------

def test_alchemists_fire_is_made_in_two_steps_and_is_the_book(bench):
    """Dissolve brimstone in lamp oil, bottle the solution in a clay flask as alchemist's
    fire. The product is the book's (1d6 fire, the burn next round, 1 fire splash, a 10 ft
    increment), not the old bench's 2d6 with no roll and no splash (inv §0.2), and its
    sale price is the book's 20 gp at Sound."""
    _carry(brimstone=1, lamp_oil=1, clay_flask=1)
    purse = dict(_pc().purse)
    made = step(bench, {"method": "dissolve", "inputs": ["inv:brimstone"],
                        "solvent": "inv:lamp-oil"}, score=0.5)
    key = made["products"][0]["key"]
    assert made["products"][0]["record"]["form"] == "solution"
    # Sound, whatever ceiling the first step's mastery reached: the middle of its band.
    from rules import worldclass

    ceiling = worldclass.ceiling_index(_pc().track("alchemist"))
    got = step(bench, {"method": "bottle", "inputs": [key], "vessel": "inv:clay-flask",
                       "formula": "alchemists-fire"}, score=1.5 / (ceiling + 1))
    p = got["products"][0]
    assert p["record"]["quality_index"] == 1
    b = p["build"]
    assert p["name"] == "Alchemist's fire" and b["family"] == "splash"
    assert b["how"] == ["throw"] and b["range_increment_ft"] == 10
    assert b["splash"] == {"amount": 1, "damage_type": "fire"}
    struck = [s for s in b["specs"] if s.get("route") == "struck" and s.get("book")]
    assert {(s["type"], s["dice"]) for s in struck} == {("damage", "1d6"), ("burning", "1d6")}
    assert b["price_gp"] == 20
    st = _pc().stock[p["key"].split(":", 1)[1]]
    assert st.specs == b["specs"] and st.price_gp == 20
    assert not _pc().inventory                                        # all spent
    # "Ingredients only" (the owner, 2026-10-07): brewing takes no coin beyond them.
    assert _pc().purse == purse


def test_the_stakes_are_said_before_the_roll(bench):
    """Plan §8.1: the check carries the mishap line, built from the volatile inputs' own
    documents, before any die is thrown; a second volatile adds 3 to the DC."""
    _carry(brimstone=1, lamp_oil=1)
    ch = post(bench, "/api/alchemy/check", {"method": "dissolve", "inputs": ["inv:brimstone"],
                                            "solvent": "inv:lamp-oil"}).json()
    line = ch["stakes"]["mishap_line"]
    assert line.startswith("If this fails by 5 or more:") and "brimstone" in line
    assert "lamp oil" in line and "Half the materials are ruined." in line
    assert {"label": "2 volatile inputs", "value": 3} in ch["dc_terms"]
    assert ch["liquid"]["start"]["color"] and ch["tuning"]["gauge"] == "reaction"


def test_a_miss_by_five_flares_once_and_ruins_half(bench):
    """Owner Q3.2 and plan §15.2: a fail by 5 or more applies the stated mishap to the
    alchemist through the engine, ONCE for the whole batch (one flash in one crucible),
    and half the materials are ruined. Measured before: the mishap was a sentence nothing
    applied (inv §0.8)."""
    _carry(brimstone=3, white_vinegar=3)
    hp = _pc().hp
    r = post(bench, "/api/alchemy/roll", {"method": "dissolve", "inputs": ["inv:brimstone"],
                                          "solvent": "inv:white-vinegar", "batch": 3,
                                          "face": 1}).json()
    assert r["verdict"]["verdict"] == "failure" and r["flare"] is True
    fire = [e for o in r["mishap"] for e in o["effects"] if e.get("kind") == "damage"]
    assert len(fire) == 1                                 # once, not three times
    assert _pc().hp < hp
    assert sum(x["count"] for x in r["lost"]) == 3        # half of six, rounded down


def test_a_stabilizer_calms_one_volatile(bench):
    """Plan §8.3: a stabilizer in the step cancels one volatile input's surcharge and
    mishap (Stabilize became an ingredient, Q3.1); the old two-volatiles wall is gone."""
    _carry(brimstone=1, lamp_oil=1, fullers_earth=1)
    ch = post(bench, "/api/alchemy/check", {
        "method": "dissolve", "inputs": ["inv:brimstone", "inv:fullers-earth"],
        "solvent": "inv:lamp-oil"}).json()
    assert ch["problems"] == []
    assert ch["stakes"]["volatile_count"] == 1 and ch["stakes"]["stabilized"]
    assert not any(t["label"].endswith("volatile inputs") for t in ch["dc_terms"])


def test_a_minigame_miss_after_a_good_roll_costs_nothing_more(bench):
    """Plan §3: failure that leaves nothing keeps being removed. A score of 0 after a
    success is Crude work, and it spends only what the step always spends."""
    _carry(brimstone=2, lamp_oil=2)
    got = step(bench, {"method": "dissolve", "inputs": ["inv:brimstone"],
                       "solvent": "inv:lamp-oil"}, score=0.0)
    assert got["tier_name"] == "Crude" and got["products"]
    assert _pc().inventory == {"brimstone": 1, "lamp-oil": 1}


def test_an_experiment_never_names_an_unknown_formula_before_it_is_made(bench):
    """Owner Q5.3: a count of the possible formulae, never their names. The check of an
    experiment that would find the potion of cure light wounds (unknown) names neither it
    nor its DC; the finished bottle writes it into the formulary ("found by experiment")
    and, being a spell potion, it sets In progress for the Brew Potion time (2 hours,
    plan §11.4) before it can be drunk."""
    from rules import inprogress

    _carry(wintergreen_essence=1, glass_vial=1)
    body = {"method": "bottle", "inputs": ["inv:wintergreen-essence"],
            "vessel": "inv:glass-vial"}
    ch = post(bench, "/api/alchemy/check", body).json()
    assert ch["problems"] == [], ch["problems"]
    assert ch["match"].get("secret") is True and ch["product"] is None
    text = json.dumps(ch).lower()
    assert "cure light" not in text and "5 + caster level" not in text
    assert ch["could"]["count"] >= 1
    got = step(bench, body)
    assert got["found"]["id"] == "potion-of-cure-light-wounds"
    assert knowledge.formula_how(_pc(), "potion-of-cure-light-wounds").startswith(
        "found by experiment")
    p = got["products"][0]
    assert p["waits"] == 120
    st = _pc().stock[p["key"].split(":", 1)[1]]
    now = cm.current().scene.clock_minutes
    assert inprogress.held_back(st, now).startswith("still setting")
    assert st.holds_spell == "cure-light-wounds" and st.caster_level


# --- assay -------------------------------------------------------------------------------------

def test_an_assay_pays_one_mastery_for_each_property_it_reveals(bench, where):
    """The owner, 2026-10-06: studying a material pays 1 mastery per property it reveals,
    0 if none. A pinch is a tenth of a unit, and an unprotected assay of a toxic reagent
    hurts whatever the roll (plan §13.2), through the engine — `knowledge.apply_danger`
    reads a save-gated toxic document as a drink and drops it ("nothing works when
    swallowed", measured 2026-10-06), so the bench's own door runs it."""
    _carry(quicksilver=1)
    prog = _pc().track("alchemist")
    before = prog.mp
    a = post(bench, "/api/alchemy/assay", {"material": "quicksilver", "face": 20}).json()
    n = len(a["revealed"])
    assert n >= 1 and _pc().track("alchemist").mp == before + n
    assert any(d["kind"] == "toxic" for d in a["dangers"]) and a["danger_applied"]
    assert a["pinch"]["tenths"] == 1
    row = next(r for r in a["shelf"] if r["material"] == "quicksilver")
    assert row["amount"] == 0.9 and row["count"] == 0
    # Everything now known, a second assay reveals nothing and pays nothing.
    _pc().herb_known["quicksilver"]["keys"] = list(
        knowledge.property_keys(knowledge.material("quicksilver")))
    cm.current().save()
    mp = _pc().track("alchemist").mp
    b = post(bench, "/api/alchemy/assay", {"material": "quicksilver", "face": 20}).json()
    assert b["revealed"] == [] and _pc().track("alchemist").mp == mp


def test_a_fume_hood_spares_the_assayer(bench, where):
    where["lab"] = dict(LAB)
    _carry(quicksilver=1)
    a = post(bench, "/api/alchemy/assay", {"material": "quicksilver", "face": 20}).json()
    assert not any(d["kind"] == "toxic" for d in a["dangers"])


# --- learning a formula ----------------------------------------------------------------------

def test_a_potion_in_hand_is_taken_apart_to_learn_its_formula(bench):
    """Owner, open point 9: spend the potion to learn its formula, DC 15 + spell level."""
    from rules import alchemy_items

    rec = alchemy_items.record_for_formula("potion-of-cure-light-wounds")
    key = alchemy_items.put(_pc(), rec, 1)
    cm.current().save()
    r = post(bench, "/api/alchemy/learn", {"from": "potion", "item": f"stock:{key}",
                                           "face": 20}).json()
    assert r["result"]["learned"] and r["result"]["spent"]
    assert key not in _pc().stock
    assert "potion-of-cure-light-wounds" in formulae.known(_pc())


def test_a_carried_formulary_teaches_the_formulae_it_writes_down(bench, monkeypatch):
    """Lane H's formularies (content/rules/alchemy-manuals.json) list formula ids under
    `formulae`; `knowledge.manual_keys` reads only a manual's `teaches`, so a route that
    asked it would never find a formula in any book. Carried, the book teaches with no
    check and is never spent."""
    book = {"id": "the-red-formulary", "name": "The Red Formulary", "craft": "alchemist",
            "formulae": ["liquid-ice"]}
    monkeypatch.setattr(knowledge, "manuals",
                        lambda craft=None: {book["id"]: book} if craft in (None, "alchemist")
                        else {})
    r = post(bench, "/api/alchemy/learn", {"from": "formulary", "fid": "liquid-ice"})
    assert r.status_code == 409                                       # not carried
    _pc().goods["The Red Formulary"] = 1
    cm.current().save()
    got = post(bench, "/api/alchemy/learn", {"from": "formulary", "fid": "liquid-ice"}).json()
    assert got["result"]["learned"] and not got["result"]["spent"]
    assert "liquid-ice" in formulae.known(_pc())
    assert _pc().goods["The Red Formulary"] == 1


# --- recipes ----------------------------------------------------------------------------------

def test_a_recipe_saves_and_loads(bench):
    r = post(bench, "/api/alchemy/recipe", {"name": "Fire", "steps": [
        {"method": "dissolve", "inputs": ["brimstone"], "solvent": "lamp-oil"},
        {"method": "bottle", "vessel": "clay-flask", "formula": "alchemists-fire"}]}).json()
    rid = r["recipes"][0]["id"]
    got = post(bench, "/api/alchemy/recipe", {"load": rid}).json()["recipe"]
    assert [s["method"] for s in got["steps"]] == ["dissolve", "bottle"]
    assert post(bench, "/api/alchemy/recipe", {"name": "X", "steps": [
        {"method": "seal"}]}).status_code == 400
