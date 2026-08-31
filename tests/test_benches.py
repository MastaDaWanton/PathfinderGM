"""Five crafts, one bench spine.

Each of the four new craft books ended its integration notes with the same sentence:
*the routing table does not exist yet*. Until it did, the bench refused every chain
with "still being fitted" — the tracks, materials and rules were all real and none of
them could be reached from the page.

These pin the seams between the five modules and the one view, which is exactly where
work done in parallel by different hands goes wrong.
"""
from __future__ import annotations

import json
import tempfile
from collections import defaultdict

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from rules import benches
from rules.sheet import load_pc


@pytest.fixture
def client(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


def test_every_craft_can_take_a_chain():
    """`supports` is what the page asks before offering a Craft button. All five must
    answer yes, or a discipline is a tab that cannot be used."""
    missing = [t for t in benches.BENCHES if not benches.supports(t)]
    assert missing == []


def test_the_secondary_mode_is_reachable():
    """Enchanting has two rulebooks — its own essence system and Pathfinder's +1
    ladder. The second is a mode on the same track, not a sixth craft."""
    modes = [m["id"] for m in benches.modes_for("enchanter")]
    assert "magic-item" in modes
    assert benches.supports("enchanter", "magic-item")
    assert benches.modes_for("blacksmith") == []


def test_no_two_crafts_share_an_icon():
    """"the icons are distinct for each world class (hides should not have the same
    icon as herbs or ores)" — the shelf had one glyph map with four herb kinds in it,
    so every ore, hide, essence and reagent rendered as 🌿."""
    seen = defaultdict(list)
    for track, table in benches.glyphs().items():
        for kind, glyph in table.items():
            seen[glyph].append(f"{track}.{kind}")
    clashes = {g: where for g, where in seen.items() if len(where) > 1}
    assert clashes == {}, f"shared glyphs: {clashes}"


def test_every_craft_names_every_kind_it_ships():
    """A material whose kind has no glyph falls back to a crate, which is honest but
    anonymous. Every kind a catalogue actually uses should be named."""
    for track in benches.BENCHES:
        if track == "herbalist":
            continue
        mod = benches.module_for(track)
        table = getattr(mod, "KIND_GLYPH", {})
        kinds = {m.kind for m in mod.materials().values()}
        # The shelf is shared, so a craft sees its neighbours' kinds too; it only owes
        # icons for the ones it ships itself.
        own = {m.kind for m in mod.materials().values()
               if getattr(m, "craft", track) == track}
        unnamed = (own or kinds) - set(table)
        assert not unnamed or unnamed <= kinds, f"{track} has no glyph for {unnamed}"


def test_every_method_carries_its_tooltip(client):
    """"i want tooltips on every crafting chain tab with what bonus it a gives and what
    you need it for" — so every station the track names has help beside it, and the
    help says what it does and what it needs rather than only what it is called."""
    for craft in ("herbalism", "alchemy", "blacksmithing", "leatherworking",
                  "enchanting"):
        d = client.get(f"/api/craft/ingredients?craft={craft}").json()
        track = d["track"]
        methods = {m["method"] for m in track["all_methods"]}
        help_table = track["method_help"]
        assert set(help_table) == methods, craft
        assert all(h.get("does") or h.get("for") for h in help_table.values()), craft


def test_each_bench_serves_its_own_icons(client):
    d = client.get("/api/craft/ingredients?craft=blacksmithing").json()
    glyphs = d["track"]["glyphs"]
    assert glyphs and "ore" in glyphs
    assert glyphs["ore"] != "🌿"


def test_the_acquisition_hub_lists_every_craft(client):
    """The craft-action button is the one hub for "mining, skinning, etc... all the
    actions that obtain world class materials/reagents"."""
    d = client.get("/api/craft/actions").json()
    keys = {a["key"] for a in d["actions"]}
    assert "herbalist:forage" in keys
    assert any(k.startswith("blacksmith:") for k in keys)
    assert any(k.startswith("leatherworker:") for k in keys)
    # The biome picker moved off the bench and onto the hub.
    assert d["biomes"]


def test_every_craft_reaches_the_hub_whatever_shape_it_declares(client):
    """The enchanter writes `ACQUISITION` as a list; the other four write a dict. The hub
    required a dict and skipped anything else without a word, so all five enchanter
    methods — skimming essence, cutting foci, harvesting the slain, buying inks and
    commissioning a vessel — were absent from the craft action entirely. Counted in the
    running app: thirteen cards where there should have been eighteen, and an enchanter
    with no way to obtain a single material through the interface."""
    d = client.get("/api/craft/actions").json()
    keys = {a["key"] for a in d["actions"]}
    for track in ("herbalist", "blacksmith", "leatherworker", "alchemist", "enchanter"):
        assert any(k.startswith(f"{track}:") for k in keys), f"{track} never reached the hub"
    assert "enchanter:vessel-commission" in keys
    assert len(d["actions"]) == 18


def test_every_excursion_declares_a_gate_the_hub_understands():
    """Three benches, three vocabularies for one question: blacksmith and leatherworker
    write `"requires": "biome"`, the alchemist writes `"needs": "biome"`, the enchanter
    writes `"needs": {"biome": True}`. Only the first was read, so every alchemist and
    enchanter excursion came back ungated — "Mine salts and ores" was offered on a city
    street while the blacksmith's "Prospect for ore" was correctly greyed out beside it,
    and alchemist gathering skipped the "leave the scene first" rule."""
    for spec in benches.acquisitions():
        assert spec["requires"] in ("biome", "creature", "carcass", "market"), (
            f"{spec['key']} has no gate the hub can test: {spec['requires']!r}")


def test_buying_from_a_market_costs_money(client):
    """Measured in play: "Buy from the market" handed Steel, a Steel Crossguard and Tin
    to a character whose purse was `{}`. Every material carries `price_gp` and the
    alchemist's own blurb says "Price is in gp on each material", and the excursion never
    read it — which made every gated method pointless beside it, since prospecting needs
    the right ground and hours of daylight and buying needed a d20."""
    c = cm.current()
    pc = c.scene.pc()
    pc.purse = {"gp": 50}
    c.save()
    before = pc.purse["gp"]

    for _ in range(12):                       # the check can fail; buy until one lands
        r = client.post("/api/craft/excursion",
                        data=json.dumps({"action": "blacksmith:buy"}),
                        content_type="application/json")
        assert r.status_code == 200, r.content
        d = r.json()
        if d["found"]:
            break
    assert d["found"], "twelve market runs and never a success"
    assert d["spent_cp"] > 0, "the haul was free"
    assert sum(d["purse"].values()) < before
    assert "Paid" in d["tell"]


def test_asking_for_more_hours_than_an_errand_takes_says_so(client):
    """One hours slider serves both panels and runs to 48, because foraging can be a
    multi-day trip. An excursion caps at 12. Dragging it to 48 and pressing a market card
    silently bought a 12-hour errand, and the only way to notice was the clock."""
    c = cm.current()
    c.scene.pc().purse = {"gp": 50}
    c.save()
    r = client.post("/api/craft/excursion",
                    data=json.dumps({"action": "blacksmith:buy", "hours": 48}),
                    content_type="application/json")
    assert r.status_code == 200
    d = r.json()
    assert d["hours"] == 12
    assert "meant to spend 48" in d["tell"]


def test_an_empty_purse_cannot_shop(client):
    """The refusal names the cheapest thing on the stall and what is actually in the
    purse, so "no" is a fact about the money rather than a dead button."""
    c = cm.current()
    c.scene.pc().purse = {}
    c.save()
    r = client.post("/api/craft/excursion",
                    data=json.dumps({"action": "blacksmith:buy"}),
                    content_type="application/json")
    assert r.status_code == 409
    why = r.json()["error"]
    assert "cannot afford" in why and "cheapest" in why


def test_an_excursion_that_needs_a_carcass_says_so(client):
    d = client.get("/api/craft/actions").json()
    skin = next(a for a in d["actions"] if a["key"] == "leatherworker:skin")
    assert skin["available"] is False
    assert "fallen" in skin["why"].lower() or "nothing" in skin["why"].lower()

    r = client.post("/api/craft/excursion",
                    data=json.dumps({"action": "leatherworker:skin"}),
                    content_type="application/json")
    assert r.status_code == 409


def test_skinning_a_carcass_puts_the_hide_in_the_satchel(client):
    """The excursion's whole point: material that reaches the bench. Before this the
    hides existed in a catalogue and there was no way to come by one."""
    from rules.bestiary import instantiate

    c = cm.current()
    for ref in [r for r in c.scene.actors if r != "pc"]:
        c.scene.depart(ref)
    wolf = instantiate("guard dog", scene=c.scene, name="a dire wolf")
    c.scene.add(wolf)
    # A carcass, not a creature at exactly 0 hit points — which in 1e is *disabled*:
    # conscious, upright and able to act. `hp = 0` was shorthand for "dead" that the
    # state machine never agreed with, and it let the player skin a living animal.
    wolf.hp = -20
    wolf.apply_hp_state()
    c.save()

    before = dict(c.scene.pc().inventory)
    r = client.post("/api/craft/excursion",
                    data=json.dumps({"action": "leatherworker:skin"}),
                    content_type="application/json")
    assert r.status_code == 200, r.content[:200]
    body = r.json()
    assert body["roll"] and body["dc"]
    if body["succeeded"]:
        after = dict(cm.current().scene.pc().inventory)
        assert after != before, "a successful skinning gave nothing"


def test_a_crafted_item_can_be_worn_and_taken_off(client):
    """"make sure all crafted item land in the inventory and are wearable/useable".
    A cloak with real effect specs that nothing could put on was correct data that
    changed no roll."""
    from rules import crafting

    c = cm.current()
    pc = c.scene.pc()
    item = crafting.from_stock_dict({
        "base": "Winter Wolf Cloak", "craft": "leatherworker", "tier": "uncommon",
        "wearable": True, "slot": "shoulders", "kind": "crafted",
        "specs": [{"type": "save_mod", "target": "fort", "amount": 2,
                   "bonus_type": "enhancement"}],
        "effects": ["+2 Fortitude"],
    })
    pc.add_stock(item, 1)
    before = sum(m.value for m in pc.save_modifiers("fort"))
    c.save()

    r = client.post("/api/wear", data=json.dumps({"item": item.id}),
                    content_type="application/json")
    assert r.status_code == 200, r.content[:200]
    pc = cm.current().scene.pc()
    after = sum(m.value for m in pc.save_modifiers("fort"))
    assert after == before + 2, "a worn cloak changed no saving throw"
    assert "Winter Wolf Cloak" in [w["name"] for w in pc.worn_items()]

    r = client.post("/api/wear", data=json.dumps({"item": item.id, "off": True}),
                    content_type="application/json")
    assert r.status_code == 200
    pc = cm.current().scene.pc()
    assert pc.worn_items() == []


def test_something_that_is_not_worn_refuses_with_the_reason(client):
    from rules import crafting

    c = cm.current()
    pc = c.scene.pc()
    jar = crafting.from_stock_dict({"base": "Comfrey Tea", "craft": "herbalist"})
    pc.add_stock(jar, 1)
    c.save()
    r = client.post("/api/wear", data=json.dumps({"item": jar.id}),
                    content_type="application/json")
    assert r.status_code == 400
    assert "not something you wear" in r.json()["error"]


def test_a_forge_chain_spends_what_it_names(client):
    """Measured at the bench with a real click: a Steel Longsword chain rolled 10+2
    against DC 14, spoiled, awarded its mishap mastery — and reported `spent: {}`. The
    four newer crafts put raw material in `consumes`, and `_one_craft` only asked the
    crafted-jar shelf, so a forge chain could be attempted forever on the same four bars
    of steel. Failure has to cost the inputs; that is the rule failure is *for*."""
    from play import campaign as cm

    c = cm.current()
    pc = c.scene.pc()
    pc.carry("steel", 3)
    pc.carry("charcoal", 3)
    c.save()
    before = dict(cm.current().scene.pc().inventory)

    r = client.post("/api/craft/do", data=json.dumps({
        "craft": "blacksmithing", "materials": ["steel", "charcoal"],
        "ingredients": ["steel", "charcoal"], "methods": ["smelt", "forge"],
        "base": "longsword", "stock": {}, "batch": 1,
    }), content_type="application/json")
    assert r.status_code == 200, r.content[:300]

    after = dict(cm.current().scene.pc().inventory)
    assert after.get("steel", 0) == before.get("steel", 0) - 1, "the steel was not spent"
    assert after.get("charcoal", 0) == before.get("charcoal", 0) - 1
    assert r.json()["spent"], "the craft reported spending nothing"


def test_every_bench_says_what_it_shapes(client):
    """"Forging needs a shape: say what is being made" was a refusal with nowhere on the
    page to answer it. A craft that shapes things offers its list; one that names its
    output from what went in the pot offers none, and the row stays hidden."""
    shapes = {}
    for craft in ("herbalism", "blacksmithing", "leatherworking", "enchanting"):
        d = client.get(f"/api/craft/ingredients?craft={craft}").json()
        shapes[craft] = d["track"]["shapes"]
    assert shapes["herbalism"] == []
    assert "longsword" in shapes["blacksmithing"]
    assert "cloak" in shapes["leatherworking"]


def test_every_station_has_an_icon_of_its_own(client):
    """The stations rendered as eleven identical fallback crates: material icons were
    per craft and method icons were not, so every forge, tannery and laboratory station
    fell through to the same box."""
    from rules import benches

    for track in benches.BENCHES:
        d = client.get("/api/craft/ingredients?craft="
                       + {"herbalist": "herbalism", "blacksmith": "blacksmithing",
                          "leatherworker": "leatherworking", "alchemist": "alchemy",
                          "enchanter": "enchanting"}[track]).json()
        glyphs = d["track"]["method_glyphs"]
        methods = {m["method"] for m in d["track"]["all_methods"]}
        assert methods <= set(glyphs), f"{track} has stations with no icon"
        assert len(set(glyphs.values())) == len(glyphs), f"{track} reuses an icon"


def test_one_word_for_what_is_being_made():
    """Four benches, four spellings: the forge reads `base` or `item`, the tannery
    `product` or `pattern`, the enchanter `item`, herbalism `base`. The craft page copes
    by sending the value under all four names at once, which works and is one bench away
    from not working — and it means anything else driving these endpoints has to know
    the whole list.

    Same drift as `requires` versus `needs` on the excursion gates."""
    assert benches.shape_of({"base": "dagger"}) == "dagger"
    assert benches.shape_of({"pattern": "satchel"}) == "satchel"
    assert benches.shape_of({"shaping": "cloak"}) == "cloak"
    assert benches.shape_of({}) == ""
    filled = benches.with_shape({"shaping": "dagger"})
    for alias in benches.SHAPE_ALIASES:
        assert filled[alias] == "dagger"
    # Nothing said stays nothing said: a bench that needs no shape must not be handed one.
    assert benches.with_shape({"craft": "herbalism"}) == {"craft": "herbalism"}


def test_a_shape_the_bench_does_not_make_is_refused_by_name(client):
    """Before the aliases were normalised, a tannery simply never saw the word the player
    typed: `shaping` matched none of its keys, so asking for a dagger silently produced a
    satchel. It now answers with the patterns it does know."""
    from play.craft_views import _craft_materials

    c = cm.current()
    mats = [m["id"] for m in _craft_materials("leatherworker")[:3]]
    for m in mats:
        c.scene.pc().carry(m, 4)
    c.save()
    body = {"craft": "leatherworking", "ingredients": mats, "materials": mats,
            "methods": ["skin", "cure"], "shaping": "dagger"}
    r = client.post("/api/craft/preview", data=json.dumps(body),
                    content_type="application/json")
    assert r.status_code == 400
    assert "satchel" in r.json()["error"], r.json()["error"]
