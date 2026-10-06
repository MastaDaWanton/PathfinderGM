"""The herbalism step bench, through its API (docs/herbalism-contracts.md §3).

Driven through the Django test client on a real campaign, with a small shelf of herbs
whose parts, routes and reagent fields are known, standing in for the corpus while the
content lanes rewrite it. Each test names the defect it prevents.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import bench_views
from play import campaign as cm
from rules import crafting, ingredients
from rules.ingredients import Ingredient
from rules.sheet import load_pc


def Herb(**kw) -> Ingredient:
    """An ingredient with the data lane's fields (contracts §2), a leaf unless it says."""
    kw.setdefault("part", "leaf")
    return Ingredient(**kw)


def _shelf() -> dict:
    heal = {"type": "heal", "dice": "1d4"}
    rows = [
        Herb(id="mint", name="Mint", effects=[
            {**heal, "route": "ingest"},
            {"type": "save_mod", "target": "poison", "amount": 2,
             "duration": {"amount": 1, "unit": "hour"}, "route": "ingest"}]),
        Herb(id="comfrey", name="Comfrey", part="root",
             effects=[{"type": "heal", "dice": "1d6", "route": "wound"}]),
        Herb(id="ironbark", name="Ironbark", part="bark",
             effects=[{"type": "heal", "dice": "1d4", "route": "skin"}]),
        Herb(id="shadowbark", name="Shadowbark", part="bark", effects=[
            {"type": "narrative", "target": "a shadow that hides", "route": "external"}]),
        Herb(id="glowcap", name="Glowcap", kind="fungus", part="fungus", effects=[
            {"type": "narrative", "target": "glows like a lantern", "route": "external"},
            {**heal, "route": "ingest"}]),
        Herb(id="harpy-cord", name="Harpy Cord", kind="monster part", part="organ",
             effects=[
                 {"type": "narrative", "target": "a voice that charms", "route": "external"},
                 {"type": "save_gate", "save": "fort", "dc": 14, "route": "ingest"},
                 {"type": "damage", "dice": "1d6", "route": "ingest"}]),
        Herb(id="dragon-flower", name="Dragon Flower", volatile=True,
             effects=[{**heal, "route": "ingest"}]),
        Herb(id="nut", name="Shell Nut", part="seed", needs_extraction=True,
             effects=[{**heal, "route": "ingest"}]),
        Herb(id="hardroot", name="Hardroot", part="root", craft_dc=20,
             effects=[{**heal, "route": "ingest"}]),
        Herb(id="easyleaf", name="Easyleaf", craft_dc=2,
             effects=[{**heal, "route": "ingest"}]),
        Herb(id="impossible", name="Impossible Moss", craft_dc=40,
             effects=[{**heal, "route": "ingest"}]),
        Herb(id="starbloom", name="Starbloom", tier="legendary",
             effects=[{**heal, "route": "ingest"}]),
        Herb(id="nightshade", name="Nightshade", effects=[
            {**heal, "route": "ingest"},
            {"type": "save_gate", "save": "fort", "dc": 12, "route": "ingest"},
            {"type": "damage", "dice": "1d6", "route": "ingest"}]),
        Herb(id="olive-oil", name="Olive Oil", kind="reagent", part="oil", solvent="oil"),
        Herb(id="spirits", name="Strong Spirits", kind="reagent", part="liquid",
             solvent="alcohol"),
        Herb(id="vinegar", name="White Vinegar", kind="reagent", part="liquid",
             solvent="vinegar"),
        Herb(id="beeswax", name="Beeswax", kind="reagent", part="wax",
             base_for=["salve", "balm", "cream"]),
        Herb(id="charcoal", name="Willow Charcoal", kind="reagent", part="mineral",
             neutralizer=1),
    ]
    return {h.id: h for h in rows}


@pytest.fixture
def bench(tmp_path, monkeypatch):
    shelf = _shelf()
    monkeypatch.setattr(ingredients, "all_ingredients", lambda: shelf)
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        bench_views._PENDING.clear()
        # A quiet start: the default opening can begin in a fight, and the bench
        # (rightly) waits until a fight is over.
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"),
                          start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        c.save()
        yield Client()
        cm._LIVE.clear()
        bench_views._PENDING.clear()


def _c():
    return cm.current()


def _pc():
    return cm.current().scene.pc()


def _carry(**counts):
    for iid, n in counts.items():
        _pc().carry(iid.replace("_", "-"), n)


def _level(n: int):
    _pc().track("herbalist").level = n


def _know(*ids):
    """Teach the character every property of these herbs, as a study would."""
    from rules import herbknowledge

    for iid in ids:
        ing = ingredients.get(iid)
        herbknowledge.reveal(_pc(), iid, herbknowledge.property_keys(ing), "test")


def _get(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.content
    return r.json()


def _post(client, url, body, status=200):
    r = client.post(url, data=json.dumps(body), content_type="application/json")
    assert r.status_code == status, (r.status_code, r.content)
    return r.json()


def _key(client, name, **want):
    for item in _get(client, "/api/bench/state")["satchel"]:
        if item["name"] == name and all(item.get(k) == v for k, v in want.items()):
            return item["key"]
    raise AssertionError(f"{name} {want} not in the satchel")


def _craft(client, method, items, batch=1, face=20, score=0.5):
    body = {"method": method, "items": items, "batch": batch, "face": face}
    rolled = _post(client, "/api/bench/roll", body)
    assert rolled["roll"]["success"], rolled
    return _post(client, "/api/bench/finish", {"token": rolled["token"], "score": score})


ITEM_KEYS = {"key", "name", "ingredient_id", "kind", "part", "tier", "state", "form",
             "quality", "quality_name", "count", "unknown", "spoils_in", "ready_at",
             "crafted"}


# --- the routes -----------------------------------------------------------------------

def test_the_bench_routes_reach_the_bench():
    """Measured 2026-10-02: all six /api/bench/* routes resolved to the homebrew editor's
    `home_views.bench`, because its `api/bench/<str:bench_id>` was listed first, and the
    page got its 404 ("no bench 'state'") for every call. The lead moved them (02d1dac)."""
    from django.urls import resolve

    for name in ("state", "check", "roll", "finish", "perks", "recipe"):
        assert resolve(f"/api/bench/{name}").func.__module__ == "play.bench_views"


# --- §3.1 state -----------------------------------------------------------------------

def test_the_state_has_every_part_the_page_draws(bench):
    """The page builds the method strip, satchel, footer and ground from one GET; a key
    missing from it is a panel that draws nothing and says nothing."""
    _carry(mint=3, olive_oil=1)
    d = _get(bench, "/api/bench/state")
    assert set(d) >= {"track", "methods", "satchel", "ground", "recipes", "clock"}
    assert set(d["track"]) >= {"id", "level", "mp", "to_next", "ceiling", "ceiling_name",
                               "perks", "picks_banked", "next_rung"}
    assert [m["id"] for m in d["methods"]] == [
        "grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep",
        "neutralize"]
    assert set(d["ground"]) >= {"biome", "roofed", "minute", "place"}
    assert set(d["clock"]) >= {"day", "label"}
    for item in d["satchel"]:
        assert ITEM_KEYS <= set(item), ITEM_KEYS - set(item)
    assert {i["name"] for i in d["satchel"]} == {"Mint", "Olive Oil"}


def test_a_locked_method_says_its_level_in_words(bench):
    """UI plan §6.1: a locked station shows the level in its label, never a tooltip
    only. At Herbalist 1 every level-2 and level-3 method must say which level opens it."""
    d = _get(bench, "/api/bench/state")
    by = {m["id"]: m for m in d["methods"]}
    assert not by["grind"]["locked"] and by["grind"]["lock_reason"] == ""
    assert by["dry"]["locked"] and by["dry"]["lock_reason"] == "Herbalist 2"
    assert by["neutralize"]["lock_reason"] == "Herbalist 3"


def test_the_ceiling_is_the_servers_word(bench):
    """The page never names a tier (contracts §3.4). At Herbalist 1 the ceiling is Fine
    (plan §4.3), and it says so by name."""
    t = _get(bench, "/api/bench/state")["track"]
    assert t["ceiling"] == 2 and t["ceiling_name"] == "Fine"


# --- §3.2 check -----------------------------------------------------------------------

def test_fits_gives_every_satchel_item_a_reason_or_a_yes(bench):
    """Every dimmed tile says why in words (UI plan §6.2; Game Accessibility Guidelines:
    never colour alone). A key missing from `fits` is a tile the page cannot explain."""
    _carry(mint=2, comfrey=1, olive_oil=1, beeswax=1, dragon_flower=1, nut=1, starbloom=1)
    satchel = _get(bench, "/api/bench/state")["satchel"]
    for method in ("grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep",
                   "neutralize"):
        d = _post(bench, "/api/bench/check", {"method": method, "items": []})
        assert set(d["fits"]) == {i["key"] for i in satchel}, method
        assert all(isinstance(v, str) for v in d["fits"].values())
    grind = _post(bench, "/api/bench/check", {"method": "grind", "items": []})["fits"]
    by = {i["name"]: grind[i["key"]] for i in satchel}
    assert by["Mint"] == ""
    assert "reagent" in by["Olive Oil"]
    assert "Neutralize is learned at Herbalist 3" in by["Dragon Flower"]
    assert "extracted" in by["Shell Nut"]
    assert by["Starbloom"].startswith("Herbalist ")


def test_check_has_the_contract_shape(bench):
    """`check` is what the info line and the result tag are drawn from (contracts
    §3.2); every key it promises is present."""
    _carry(mint=2)
    _know("mint")
    d = _post(bench, "/api/bench/check",
              {"method": "brew", "items": [{"key": _key(bench, "Mint"), "count": 2}]})
    assert set(d) >= {"fits", "problems", "can_roll", "minutes", "dc", "bonus", "terms",
                      "need", "impossible", "product"}
    assert d["can_roll"] and d["problems"] == []
    p = d["product"]
    assert set(p) >= {"name", "form", "taken", "keeps_minutes", "routes", "unknown",
                      "effects", "drawbacks", "source_text"}
    assert p["form"] == "infusion" and p["name"] == "Mint Infusion"
    # by_tier runs from Crude to the ceiling: Fine at Herbalist 1 is three rungs.
    assert len(p["effects"]) == 2
    assert all(len(e["by_tier"]) == 3 for e in p["effects"])


def test_an_unknown_property_is_counted_on_the_card_and_never_shown(bench):
    """Plan §8.1: unknown properties stay hidden on the bench card. A card that printed
    what an untasted herb does would make the herbarium pointless; it says how many are
    unknown instead, and a dropped one is not named either."""
    _carry(glowcap=1)
    card = _post(bench, "/api/bench/check", {"method": "brew", "items": [
        {"key": _key(bench, "Glowcap"), "count": 1}]})["product"]
    assert card["effects"] == [] and card["dropped"] == []
    assert card["unknown"] == 1
    assert "glows" not in json.dumps(card["effects"] + card["drawbacks"] + card["dropped"])


def test_a_hand_written_key_that_is_not_carried_is_refused_not_raised(bench):
    """A stale tile (the herb was used up in another tab) must answer 409 with a
    sentence, never a 500."""
    d = _post(bench, "/api/bench/check",
              {"method": "grind", "items": [{"key": "ing:nothing", "count": 1}]}, 409)
    assert "no longer in your satchel" in d["error"]
    _post(bench, "/api/bench/check", {"method": "grind", "items": "x"}, 400)


# --- the d20 ----------------------------------------------------------------------------

def test_no_natural_20_on_a_bench_check(bench):
    """Plan §5.3: under the old bench's natural 20 any concentration depth was reachable
    by luck, and the climbing DC gated nothing. DC 40 against +1 is 19 past the die: the
    check says so in words, offers no roll, and a forced face of 20 is refused."""
    _carry(impossible=2)
    body = {"method": "grind", "items": [{"key": _key(bench, "Impossible Moss"),
                                          "count": 1}]}
    d = _post(bench, "/api/bench/check", body)
    gap = d["dc"] - d["bonus"]
    assert d["need"] is None and not d["can_roll"]
    assert d["impossible"] == f"needs +{gap - 20} more to the check"
    _post(bench, "/api/bench/roll", {**body, "face": 20}, 400)


def test_a_natural_one_is_not_an_automatic_failure_either(bench):
    """The CRB gives naturals to attacks and saves, not skill checks. Easyleaf is DC 2
    against +1: a 1 makes it, and the shown need of 1 is the truth."""
    _carry(easyleaf=1)
    body = {"method": "grind", "items": [{"key": _key(bench, "Easyleaf"), "count": 1}]}
    assert _post(bench, "/api/bench/check", body)["need"] == 1
    assert _post(bench, "/api/bench/roll", {**body, "face": 1})["roll"]["success"]


def test_the_shown_need_is_the_roll(bench):
    """The odds must match the roll: the face `need` names succeeds and the face below
    it fails, at the DC the check showed."""
    _carry(hardroot=4)
    body = {"method": "grind", "items": [{"key": _key(bench, "Hardroot"), "count": 1}]}
    need = _post(bench, "/api/bench/check", body)["need"]
    assert _post(bench, "/api/bench/roll", {**body, "face": need})["roll"]["success"]
    assert not _post(bench, "/api/bench/roll",
                     {**body, "face": need - 1})["roll"]["success"]


def test_the_concentration_dc_climbs_two_n_at_step_n(bench):
    """Plan §5.3: step n adds 2n, so n(n+1) over the line: +2, +6, +12. Mint is DC 10.
    Two drying steps and a third, each read off `check`, and each one band rarer."""
    # Herbalist 4: exotic material is in reach under the Herbalist document both before
    # and after the progression lane re-cuts its levels.
    _level(4)
    _carry(mint=8)
    seen = []
    name = "Mint"
    want = {}
    for step in (1, 2, 3):
        key = _key(bench, name, **want)
        have = next(i for i in _get(bench, "/api/bench/state")["satchel"]
                    if i["key"] == key)["count"]
        body = {"method": "dry", "items": [{"key": key, "count": have}]}
        d = _post(bench, "/api/bench/check", body)
        seen.append(d["dc"])
        made = _craft(bench, "dry", body["items"], face=20)["made"]
        name, want = made["name"], {"form": "dried"}
        assert made["tier"] == ("common", "uncommon", "rare", "exotic")[step]
    assert seen == [12, 16, 22]


# --- the book's failure rule ---------------------------------------------------------------

def test_a_miss_by_four_loses_the_time_and_nothing_else(bench):
    """The PF1e Craft rule (plan §2): fail by 4 or less and only the time is lost."""
    _carry(hardroot=4)
    body = {"method": "grind", "items": [{"key": _key(bench, "Hardroot"), "count": 2}]}
    d = _post(bench, "/api/bench/check", body)
    face = d["dc"] - d["bonus"] - 4
    r = _post(bench, "/api/bench/roll", {**body, "face": face})
    assert r["roll"]["margin"] == -4 and r["lost"] == []
    assert _pc().inventory["hardroot"] == 4


def test_a_miss_by_five_ruins_exactly_half_rounded_up_across_the_stack(bench):
    """Fail by 5 or more and half the materials are ruined, rounded up, across the whole
    bulk stack: a batch of 5 loses 3, never 5 and never 2."""
    _carry(hardroot=7)
    body = {"method": "grind", "items": [{"key": _key(bench, "Hardroot"), "count": 1}],
            "batch": 5}
    d = _post(bench, "/api/bench/check", body)
    face = d["dc"] - d["bonus"] - 5
    r = _post(bench, "/api/bench/roll", {**body, "face": face})
    assert sum(x["count"] for x in r["lost"]) == 3
    assert _pc().inventory["hardroot"] == 4


def test_a_ruined_stack_shares_the_loss_across_its_materials(bench):
    """Reagents are materials too: steeping 3 mint in 3 spirits and missing by 5 ruins 3
    of the 6, shared out, not 3 of each."""
    _level(2)
    _carry(hardroot=3, spirits=3)
    body = {"method": "steep",
            "items": [{"key": _key(bench, "Hardroot"), "count": 3},
                      {"key": _key(bench, "Strong Spirits"), "count": 3}]}
    d = _post(bench, "/api/bench/check", body)
    face = d["dc"] - d["bonus"] - 6
    r = _post(bench, "/api/bench/roll", {**body, "face": face})
    assert sum(x["count"] for x in r["lost"]) == 3
    assert _pc().inventory.get("hardroot", 0) + _pc().inventory.get("spirits", 0) == 3


def test_a_minigame_score_never_takes_materials(bench):
    """Research, plan §3: no surviving game punishes twice. After a successful roll, a
    score of 0 lowers the quality and spends exactly what the step consumes, no more."""
    _carry(mint=5)
    done = _craft(bench, "grind", [{"key": _key(bench, "Mint"), "count": 2}], score=0.0)
    assert done["tier_name"] == "Crude" and done["count"] == 2
    assert _pc().inventory["mint"] == 3


def test_a_forged_score_is_clamped_to_the_ceiling(bench):
    """Plan §15.1: a tier above the ceiling is impossible. At Herbalist 1 a forged 1.0
    is Fine, and so is 7; a negative or a word is Crude."""
    _carry(mint=4)
    for score, tier in ((1.0, "Fine"), (7, "Fine"), (-3, "Crude"), ("lots", "Crude")):
        done = _craft(bench, "grind", [{"key": _key(bench, "Mint"), "count": 1}],
                      score=score)
        assert done["tier_name"] == tier and done["tier"] <= done["ceiling"]


# --- routes and forms -------------------------------------------------------------------

def test_an_external_effect_never_reaches_a_herbal_product(bench):
    """Plan §5.2 ratchet, by set comparison: a herbal product never carries an
    `external` effect. Glowcap's glow is dropped from the tea and the card says
    "alchemy only"; its heal is kept."""
    _carry(glowcap=2)
    _know("glowcap")
    body = {"method": "brew", "items": [{"key": _key(bench, "Glowcap"), "count": 1}]}
    card = _post(bench, "/api/bench/check", body)["product"]
    assert [d["why"] for d in card["dropped"]] == ["alchemy only"]
    _craft(bench, "brew", body["items"])
    for item in _pc().stock.values():
        routes = {crafting._route(s) for s in item.base_specs}
        assert "external" not in routes
        assert all("glows" not in json.dumps(s) for s in item.specs)


def test_a_remedy_whose_help_is_all_alchemy_is_refused(bench):
    """Lane A's finding on Harpy Vocal Cord: once the external effect goes, only the
    poison is left. Making that would be a poison with a herbal name."""
    _carry(harpy_cord=1)
    d = _post(bench, "/api/bench/check",
              {"method": "brew", "items": [{"key": _key(bench, "Harpy Cord"),
                                            "count": 1}]})
    assert not d["can_roll"]
    assert any("alchemy's" in p for p in d["problems"])


def test_bark_that_does_nothing_herbal_still_grinds_into_a_salve_base(bench):
    """Measured live on the owner's data: Breeam's every effect is external, and its
    bark was refused as a salve base for "carrying none of what this does". A base is
    structure, not medicine; it is the salve made from it that carries effects."""
    _carry(shadowbark=1)
    d = _post(bench, "/api/bench/check", {"method": "grind", "items": [
        {"key": _key(bench, "Shadowbark"), "count": 1}]})
    assert d["can_roll"], d["problems"]
    assert d["product"]["form"] == "salve-base"


def test_each_form_carries_only_its_routes(bench):
    """Plan §7: who can use what follows the routes. Comfrey works in a wound, so a
    poultice carries it and a decoction (drunk) cannot; mint is swallowed, so a tea
    carries it and a poultice cannot."""
    _carry(comfrey=4, mint=4)
    brew = _post(bench, "/api/bench/check",
                 {"method": "brew", "items": [{"key": _key(bench, "Comfrey"),
                                               "count": 1}]})
    assert brew["product"]["form"] == "decoction" and not brew["can_roll"]
    _craft(bench, "grind", [{"key": _key(bench, "Comfrey"), "count": 1}])
    _craft(bench, "grind", [{"key": _key(bench, "Mint"), "count": 1}])
    pc_key = _key(bench, "Ground Comfrey")
    poultice = _post(bench, "/api/bench/check",
                     {"method": "mix", "items": [{"key": pc_key, "count": 1}]})
    assert poultice["can_roll"] and poultice["product"]["form"] == "poultice"
    assert poultice["product"]["effects"][0]["by_tier"]
    mint_poultice = _post(bench, "/api/bench/check",
                          {"method": "mix",
                           "items": [{"key": _key(bench, "Ground Mint"), "count": 1}]})
    assert not mint_poultice["can_roll"]


def test_bark_grinds_into_a_salve_base_and_a_salve_needs_its_oil(bench):
    """Plan §2, Bases: grinding bark makes a salve base; mixing a base with an infused
    oil makes a salve. The whole topical line, one step at a time."""
    _level(2)
    _carry(ironbark=1, mint=2, olive_oil=1)
    _craft(bench, "grind", [{"key": _key(bench, "Ironbark"), "count": 1}])
    assert _key(bench, "Ironbark Salve Base", form="salve-base")
    _craft(bench, "dry", [{"key": _key(bench, "Mint"), "count": 2}])
    oil = _craft(bench, "infuse", [{"key": _key(bench, "Dried Mint"), "count": 1},
                                   {"key": _key(bench, "Olive Oil"), "count": 1}])
    assert oil["made"]["form"] == "infused-oil"
    d = _post(bench, "/api/bench/check", {"method": "mix", "items": [
        {"key": _key(bench, "Ironbark Salve Base"), "count": 1},
        {"key": oil["made"]["key"], "count": 1}]})
    assert d["product"]["form"] == "salve", d


# --- steeping -------------------------------------------------------------------------------

# The tincture's two weeks (plan §6 / Q6) moved to tests/test_inprogress.py on 2026-10-05,
# when the owner's In-progress ruling made a finished jar wait to be collected rather than
# lift itself: `test_a_tincture_is_not_collectable_on_day_13_and_is_on_day_14`.


# --- bulk and time --------------------------------------------------------------------------

def test_one_step_is_one_line_in_the_log(bench):
    """Measured live on the real page: the roll wrote "works X at the bench" and the
    finish "makes X", two lines in the table's log for every step, where the old bench
    wrote one per batch. One step is one line, written when it lands; a miss writes its
    own line, since it never lands."""
    _carry(mint=2, hardroot=1)
    before = len(_c().transcript)
    _craft(bench, "grind", [{"key": _key(bench, "Mint"), "count": 1}])
    assert len(_c().transcript) == before + 1
    _post(bench, "/api/bench/roll", {"method": "grind", "face": 1, "items": [
        {"key": _key(bench, "Hardroot"), "count": 1}]})
    assert len(_c().transcript) == before + 2


def test_a_bulk_batch_shares_one_tier(bench):
    """The owner's bulk rule (plan §2): one roll and one minigame for the stack, and the
    whole stack lands as one tier in one satchel entry."""
    _carry(mint=6)
    done = _craft(bench, "grind", [{"key": _key(bench, "Mint"), "count": 1}], batch=5,
                  score=0.71)
    assert done["count"] == 5
    made = [s for s in _pc().stock.values() if s.form == "powder"]
    assert len(made) == 1 and made[0].count == 5 and made[0].quality == done["tier"]


def test_time_is_per_dose_times_the_batch(bench):
    """World time grows with batch size, no discount (plan §6): grinding is 10 minutes a
    dose, so a batch of 3 is 30 minutes, on the clock, whether the roll lands or not."""
    _carry(hardroot=6)
    body = {"method": "grind", "items": [{"key": _key(bench, "Hardroot"), "count": 1}],
            "batch": 3}
    assert _post(bench, "/api/bench/check", body)["minutes"] == 30
    before = _c().scene.clock_minutes
    r = _post(bench, "/api/bench/roll", {**body, "face": 1})
    assert not r["roll"]["success"] and r["minutes"] == 30
    assert _c().scene.clock_minutes == before + 30


# --- reservation ------------------------------------------------------------------------

def test_a_reload_returns_the_reservation_rather_than_eating_it(bench):
    """Between roll and finish the materials are set aside, not spent. A reload (the
    page asks for the state again) lets the craft go: the herbs are all still there and
    the old token is refused."""
    _carry(mint=3)
    body = {"method": "grind", "items": [{"key": _key(bench, "Mint"), "count": 2}],
            "face": 20}
    token = _post(bench, "/api/bench/roll", body)["token"]
    shown = _post(bench, "/api/bench/check", {"method": "grind", "items": []})
    assert shown  # the reservation does not break the shelf
    assert _get(bench, "/api/bench/state")["satchel"][0]["count"] == 3
    _post(bench, "/api/bench/finish", {"token": token, "score": 1}, 409)
    assert _pc().inventory["mint"] == 3


# --- finish ---------------------------------------------------------------------------------

def test_finish_has_the_contract_shape_and_pays_the_firsts(bench):
    """Contracts §3.4, and plan §4.4: the first product of a form, the first work with a
    herb and each property learned are itemised mastery lines, and the refreshed state
    comes back so the page needs no second request."""
    _carry(mint=2)
    done = _craft(bench, "brew", [{"key": _key(bench, "Mint"), "count": 1}], score=0.9)
    assert set(done) >= {"tier", "tier_name", "score", "ceiling", "made", "count",
                         "mastery", "discoveries", "next", "state"}
    assert ITEM_KEYS <= set(done["made"])
    whys = [line["why"] for line in done["mastery"]["lines"]]
    assert "first infusion" in whys and "first work with Mint" in whys
    assert done["mastery"]["total"] == _pc().track("herbalist").mp
    assert {d["ingredient_id"] for d in done["discoveries"]} == {"mint"}
    again = _craft(bench, "brew", [{"key": _key(bench, "Mint"), "count": 1}])
    assert not any(line["why"].startswith("first") for line in again["mastery"]["lines"])


def test_the_yield_perk_is_rolled_and_shown(bench):
    """The extra dose is the bench's one random reward, so its roll is in the result
    lines (plan §3): never a silent extra."""
    _carry(mint=2)
    _pc().track("herbalist").perks["yield"] = 20       # a certain extra dose
    done = _craft(bench, "grind", [{"key": _key(bench, "Mint"), "count": 1}])
    assert done["count"] == 2
    assert any("Yield perk: d100" in line["why"] for line in done["mastery"]["lines"])


# --- saves -----------------------------------------------------------------------------------

def test_a_made_thing_round_trips_through_a_save(bench):
    """Every new Stock field is written only when set and read back the same: a remedy
    that lost its quality, its jar date or its effects on reload is a remedy the bench
    made and the save forgot."""
    _level(2)
    _carry(mint=2, spirits=1)
    _craft(bench, "steep", [{"key": _key(bench, "Mint"), "count": 1},
                            {"key": _key(bench, "Strong Spirits"), "count": 1}],
           score=0.9)
    before = {k: v.as_dict() for k, v in _pc().stock.items()}
    c = _c()
    c.save()
    cid = c.id
    cm._LIVE.clear()
    after = {k: v.as_dict() for k, v in cm.current(cid).scene.pc().stock.items()}
    assert after == before
    jar = next(iter(after.values()))
    assert jar["form"] == "tincture" and jar["quality_name"] and jar["ready_minute"]


def test_old_stock_loads_and_is_kept_out_of_the_new_methods(bench):
    """Plan §14.2: distilled and purified jars stay usable and sellable under their old
    names, marked as an old method, and the new bench will not work them further."""
    old = crafting.from_stock_dict({"base": "Mint Tincture", "craft": "herbalist",
                                    "count": 2, "tier": "common",
                                    "specs": [{"type": "heal", "dice": "1d4"}]})
    assert old.old_method == "distill" and not old.stepped
    assert "old_method" not in old.as_dict()     # healed on read, never rewritten
    _pc().add_stock(old, 2)
    item = next(i for i in _get(bench, "/api/bench/state")["satchel"]
                if i["name"] == "Mint Tincture")
    assert item["old_method"] == "distill"
    fits = _post(bench, "/api/bench/check", {"method": "mix", "items": []})["fits"]
    assert fits[item["key"]].startswith("made by an old method")


# --- perks and recipes ----------------------------------------------------------------------

def test_perks_need_banked_picks(bench):
    """Endless levels pick two perks each (plan §4.2). With none banked the picker is
    refused in words; at Herbalist 5 there are four, taken two at a time."""
    d = _post(bench, "/api/bench/perks", {"picks": ["quality"]}, 400)
    assert "banked" in d["error"]
    _level(5)
    t = _post(bench, "/api/bench/perks", {"picks": ["quality", "quality"]})
    assert t["perks"]["quality"] == 2 and t["picks_banked"] == 2
    assert t["ceiling"] == 6


def test_recipes_save_list_and_delete_and_old_ones_are_flagged(bench):
    """Contracts §3.6, and plan §14.3: a recipe naming a retired method is kept and says
    which step no longer exists."""
    c = _c()
    c.recipes.append({"name": "Old Draught", "craft": "herbalism",
                      "methods": ["grind", "distill"], "ingredients": ["mint", "mint"]})
    r = _post(bench, "/api/bench/recipe", {"name": "Mint tea", "steps": [
        {"method": "brew", "items": [{"ingredient_id": "mint", "count": 1}]}]})["recipes"]
    by = {x["name"]: x for x in r}
    assert by["Mint tea"]["flag"] == "" and by["Mint tea"]["steps"][0]["method"] == "brew"
    assert "Distill no longer exists" in by["Old Draught"]["flag"]
    assert by["Old Draught"]["steps"][0]["items"] == [{"ingredient_id": "mint",
                                                       "count": 2}]
    _post(bench, "/api/bench/recipe", {"name": "x", "steps": [{"method": "distill"}]},
          400)
    left = _post(bench, "/api/bench/recipe", {"delete": by["Mint tea"]["id"]})["recipes"]
    assert [x["name"] for x in left] == ["Old Draught"]


def test_a_loaded_recipe_offers_its_next_step(bench):
    """UI plan §5 step 7: with a recipe loaded, finishing one step offers the next."""
    _carry(comfrey=1)
    rid = _post(bench, "/api/bench/recipe", {"name": "Comfrey poultice", "steps": [
        {"method": "grind", "items": [{"ingredient_id": "comfrey", "count": 1}]},
        {"method": "mix", "items": []}]})["recipes"][0]["id"]
    rolled = _post(bench, "/api/bench/roll", {
        "method": "grind", "items": [{"key": _key(bench, "Comfrey"), "count": 1}],
        "face": 20, "recipe": rid, "step": 0})
    done = _post(bench, "/api/bench/finish", {"token": rolled["token"], "score": 0.5})
    assert done["next"]["method"] == "mix"
    assert done["recipe"] == {"id": rid, "step": 0}


def test_the_page_may_name_its_recipe_on_any_request_and_hears_it_back(bench):
    """The bench UI keeps its loaded recipe as {recipe, step} and may send it on check,
    roll or finish; each echoes it back as {id, step}, and finish's `next` follows the
    step the page says it is on rather than the one the roll remembered."""
    _carry(comfrey=2)
    rid = _post(bench, "/api/bench/recipe", {"name": "Three steps", "steps": [
        {"method": "grind", "items": []}, {"method": "grind", "items": []},
        {"method": "mix", "items": []}]})["recipes"][0]["id"]
    items = [{"key": _key(bench, "Comfrey"), "count": 1}]
    ref = {"recipe": {"id": rid}, "step": 0}
    assert _post(bench, "/api/bench/check", {"method": "grind", "items": items,
                                             "recipe": ref})["recipe"] == {"id": rid,
                                                                            "step": 0}
    rolled = _post(bench, "/api/bench/roll", {"method": "grind", "items": items,
                                              "face": 20, "recipe": ref})
    assert rolled["recipe"]["id"] == rid
    done = _post(bench, "/api/bench/finish", {"token": rolled["token"], "score": 0.5,
                                              "recipe": rid, "step": 1})
    assert done["next"] == {"method": "mix", "recipe": rid, "step": 2}


def test_the_track_names_every_rung_and_what_each_perk_would_do(bench):
    """The UI reads `track.tiers` before its own fallback names and `track.perk_info` for
    the picker's numbers ("+5% potency, total +15%"); without them the page would have to
    build names and sums the server owns."""
    t = _get(bench, "/api/bench/state")["track"]
    assert t["tiers"] == ["Crude", "Sound", "Fine"]
    assert t["perk_info"]["potency"]["next"] == "+5% potency, total +5%"
    _level(4)
    _pc().track("herbalist").perks["potency"] = 2
    t = _get(bench, "/api/bench/state")["track"]
    assert t["perk_info"]["potency"] == {"next": "+5% potency, total +15%", "taken": 2}
    assert t["perk_info"]["quality"]["next"].endswith("Flawless +1")
    assert t["tiers"][-1] == t["ceiling_name"]


def test_the_strips_live_word_and_the_finish_agree_on_every_band(bench):
    """The minigame strip shows a live tier word from `tuning.names` and `tuning.bands`
    while the page never names the final tier. If the bands were not the finish's own
    spread, the strip could say Fine and the result land Sound: every band's lower bound,
    sent as the score, must finish on that band's name."""
    _carry(mint=6)
    items = [{"key": _key(bench, "Mint"), "count": 1}]
    tuning = _post(bench, "/api/bench/roll", {"method": "grind", "items": items,
                                              "face": 20})["tuning"]
    assert tuning["names"] == ["Crude", "Sound", "Fine"]
    assert tuning["bands"][0] == 0
    for name, low in zip(tuning["names"], tuning["bands"]):
        rolled = _post(bench, "/api/bench/roll", {"method": "grind", "items": items,
                                                  "face": 20})
        done = _post(bench, "/api/bench/finish", {"token": rolled["token"], "score": low})
        assert done["tier_name"] == name, (low, done["tier_name"])


def test_check_says_the_most_the_pot_allows_under_the_name_the_page_reads(bench):
    """The "All" button reads `max_batch`: batch units the satchel covers for what is on
    the tool, so 5 mint at 2 a unit is 2, not 5 and not 2.5."""
    _carry(mint=5)
    d = _post(bench, "/api/bench/check", {"method": "grind", "items": [
        {"key": _key(bench, "Mint"), "count": 2}]})
    assert d["max_batch"] == d["batch_max"] == 2


# --- re-pinned from the old bench's tests ----------------------------------------------------
#
# Defects the chain bench's tests recorded that still apply at the step bench, pinned
# again on the new endpoints when the old ones retired (2026-10-02).

def test_a_step_that_cannot_be_made_is_refused_before_it_is_scored(bench):
    """Scoring it would let a track level itself on work the character has neither the
    level nor the material to attempt; nor may the clock move for it."""
    _carry(starbloom=1)
    before = (_pc().track("herbalist").mp, _c().scene.clock_minutes)
    _post(bench, "/api/bench/roll", {"method": "grind", "face": 20, "items": [
        {"key": _key(bench, "Starbloom"), "count": 1}]}, 400)
    assert (_pc().track("herbalist").mp, _c().scene.clock_minutes) == before


def test_the_shelf_and_the_roll_button_agree(bench):
    """Both answers come from one function (`fit_reason`), so an item `fits` marks must
    also be a named problem when it is put on the tool, and one left unmarked must not."""
    _carry(mint=2, comfrey=1, olive_oil=1, beeswax=1, dragon_flower=1, nut=1,
           starbloom=1)
    for method in ("grind", "brew", "mix"):
        fits = _post(bench, "/api/bench/check", {"method": method, "items": []})["fits"]
        for item in _get(bench, "/api/bench/state")["satchel"]:
            problems = _post(bench, "/api/bench/check", {
                "method": method, "items": [{"key": item["key"], "count": 1}]})["problems"]
            named = [p for p in problems if p.startswith(item["name"] + ":")]
            assert bool(named) == bool(fits[item["key"]]), (method, item["name"],
                                                             problems, fits)


def test_a_batch_bigger_than_the_satchel_is_refused_before_it_runs(bench):
    """The old bench ran a batch until it ran short and stopped partway. One roll for the
    stack means the shortfall is said up front, with the numbers, and the stepper is told
    the most the satchel allows."""
    _carry(mint=3)
    d = _post(bench, "/api/bench/check", {"method": "grind", "batch": 5, "items": [
        {"key": _key(bench, "Mint"), "count": 1}]})
    assert not d["can_roll"] and d["batch_max"] == 3
    assert any("the batch wants 5 and you carry 3" in p for p in d["problems"])


def test_the_roll_reports_the_whole_check_not_a_verdict(bench):
    """The die, each term and the DC, so the bench can show the arithmetic: "+3" says
    nothing, "Herbalist 2, half level +1" says what to improve."""
    _carry(mint=1)
    r = _post(bench, "/api/bench/roll", {"method": "grind", "face": 12, "items": [
        {"key": _key(bench, "Mint"), "count": 1}]})["roll"]
    assert set(r) >= {"face", "bonus", "total", "dc", "success", "margin", "terms"}
    assert r["total"] == 12 + r["bonus"] == 12 + sum(t["value"] for t in r["terms"])
    assert r["margin"] == r["total"] - r["dc"]


def test_harm_is_on_the_card_as_a_drawback_and_softens_with_quality(bench):
    """The card's Drawbacks list is harm only, with the save beside it, and quality
    "softens drawbacks" (plan §2): Nightshade's 1d6 is worse at Crude than at Fine."""
    _carry(nightshade=1)
    _know("nightshade")
    card = _post(bench, "/api/bench/check", {"method": "brew", "items": [
        {"key": _key(bench, "Nightshade"), "count": 1}]})["product"]
    assert [e["from"] for e in card["effects"]] == ["Nightshade"]
    damage = next(d for d in card["drawbacks"] if "1d6" in d["base"])
    crude, sound, fine = damage["by_tier"]
    assert crude != fine and "1d6" in sound


def test_a_recipe_saved_under_its_own_name_replaces_it(bench):
    """A bench where the second save silently makes a duplicate is a bench nobody can
    correct a recipe at."""
    step = {"method": "grind", "items": [{"ingredient_id": "mint", "count": 1}]}
    _post(bench, "/api/bench/recipe", {"name": "Wash", "steps": [step]})
    got = _post(bench, "/api/bench/recipe", {"name": "wash", "steps": [step, {
        "method": "mix", "items": []}]})["recipes"]
    assert len(got) == 1 and len(got[0]["steps"]) == 2


def test_a_nameless_recipe_is_refused(bench):
    _post(bench, "/api/bench/recipe", {"steps": [{"method": "grind"}]}, 400)


HOSTILE = [{}, [1, 2], {"method": ["grind"]}, {"method": "grind", "items": [{"key": 5}]},
           {"method": "grind", "items": [None]}, {"method": "grind", "batch": "many",
                                                  "items": []},
           {"method": "grind", "face": [20], "items": []},
           {"method": "grind", "face": "banana", "items": []},
           {"token": ["x"], "score": {"a": 1}}, {"picks": "quality"},
           {"picks": [None, 3]}, {"name": "x", "steps": [None]},
           {"name": "x", "steps": [{"method": "grind", "items": [None]}]},
           {"delete": ["r1"]}]


@pytest.mark.parametrize("url", ["/api/bench/check", "/api/bench/roll",
                                 "/api/bench/finish", "/api/bench/perks",
                                 "/api/bench/recipe"])
def test_no_bench_endpoint_answers_a_bad_body_with_a_traceback(bench, url):
    """tests/test_api_robustness.py's measurement, for the new doors: seven of the old
    endpoints answered hostile bodies with a 500, which in the packaged app is a button
    that does nothing and says nothing. A refusal is the app working."""
    _carry(mint=2)
    for body in HOSTILE:
        r = bench.post(url, data=json.dumps(body), content_type="application/json")
        assert r.status_code < 500, (url, body, r.content)


# --- the old page ---------------------------------------------------------------------------

def test_the_old_page_refuses_herbalism_chains_in_words(bench):
    """Herbalism's chain path retired from /craft/ (plan §9): its endpoints answer 409
    with a sentence saying where the bench went, rather than running the retired rules."""
    for url in ("/api/craft/preview", "/api/craft/do", "/api/craft/recipes"):
        d = _post(bench, url, {"craft": "herbalism", "name": "x",
                               "ingredients": ["mint"], "methods": ["grind"]}, 409)
        assert "at the table now" in d["error"] and d["moved"]
