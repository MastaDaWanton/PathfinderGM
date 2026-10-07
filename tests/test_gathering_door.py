"""One gathering door for every craft (owner, 2026-10-06).

"when i am prospecting for ore using blacksmithing i get almost nothing but when i use
alchemy to mine ore and salts i get a ton ... Herbalism is the only skill that actually
prompts the LLM for prose and runs encounter tables."

Measured that day on scratch data (50 runs each, four hours, the same level-1 character):
on a mountain the hub's Prospect brought 1.28 ore and the alchemist's quarry 1.50 ore plus
3.34 of everything else; at level 3 the Prospect fell to 0.40 while a forage on the same
character brought 4.74 herbs. Three formulas for one act — the forage op's hourly bands,
the prospect op's one pick an hour, the hub's single d20 whose take grew with the size of
the pool — and only the forage ran the ground's encounter or reached the narrator. These
pin the one door that replaced them (`Engine._gather`, `rules/gathering.py`).
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import benches, foraging, gathering, worldclass
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from tests._places import stand_on


def _table(seed: int, biome: str, track: str = "", level: int = 1):
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    stand_on(scene, biome)
    if track:
        scene.pc().track(track).level = level
    return scene, Engine(scene, Dice(seed=seed))


def _run(engine, op: str, hours: int, face: int, **params):
    res = engine.run(engine.validate([{"op": op, "actor": "pc", "because": "t",
                                       "params": dict({"hours": hours}, **params)}],
                                      origin="author:test"))
    if res.awaiting:
        res = engine.resume(face)
    return res


def _ore_in(pc) -> int:
    """Ore and native metal carried, by the shelf's own kind."""
    from rules import blacksmith

    shelf = blacksmith.materials()
    return sum(int(n) for i, n in pc.inventory.items()
               if getattr(shelf.get(i), "kind", "") in ("ore", "metal"))


@pytest.mark.parametrize("biome,level", [("mountain", 1), ("mountain", 3), ("hills", 1)])
def test_the_smith_digs_more_ore_than_the_alchemist(biome, level):
    """The owner's report, as numbers: before the door, a level-1 alchemist's quarry
    brought more ore off a mountain than a level-1 smith's prospect (1.50 against 1.28 in
    four hours, 50 runs), because the quarry read the whole shared shelf and the hub's
    take grew with the pool. The smith's seam is mostly ore now, and the alchemist's ore
    is a side find at half a batch (Ultimate Campaign: an unsuitable skill earns half)."""
    smith = alch = 0
    for seed in range(20):
        s, e = _table(seed, biome, "blacksmith", level)
        _run(e, "prospect", 4, Dice(seed=seed + 99).roll("1d20").total)
        smith += _ore_in(s.pc())
        s, e = _table(seed, biome, "alchemist", level)
        _run(e, "gather", 4, Dice(seed=seed + 99).roll("1d20").total,
             key="alchemist:quarry")
        alch += _ore_in(s.pc())
    assert smith > 2 * alch, (biome, level, smith, alch)
    assert smith >= 20, f"twenty four-hour prospects brought {smith} ore"


def test_side_finds_come_at_half_a_batch_and_the_trade_finds_its_own_in_full():
    quarry = gathering.excursion("alchemist:quarry")
    rows = gathering.material_table(quarry, "mountain", 5).rows
    ore = [r for r in rows if r.kind in ("ore", "metal")]
    own = [r for r in rows if r.kind in quarry["own"]]
    assert ore and own
    assert all(r.batch == 0.5 for r in ore), [(r.name, r.batch) for r in ore]
    assert all(r.batch == 1.0 for r in own)
    prospect = gathering.excursion("blacksmith:prospect")
    seam = gathering.material_table(prospect, "mountain", 5).rows
    share = sum(r.span for r in seam if r.kind in ("ore", "metal")) / sum(
        r.span for r in seam)
    assert share > 0.8, f"a prospector's seam is {share:.0%} ore"
    # The batch arithmetic: a half batch rounds half up and never reaches nothing.
    assert foraging.batch_for(1, 0, 0.5) == 5
    assert foraging.batch_for(1, 4, 0.5) == 1


def test_herb_tables_are_laid_exactly_as_before():
    """Herbalism unchanged: the layout moved into `lay_table` for every trade, and a
    herb row is a full batch with no kind, as every row was."""
    t = foraging.table_for("forest", 5)
    assert t.rows and all(r.batch == 1.0 and r.kind == "" for r in t.rows)
    assert gathering.material_table(gathering.excursion("herbalist:forage"),
                                    "forest", 5).rows == t.rows


def test_no_trade_table_drops_its_rarest_rows():
    """Measured 2026-10-06: ten trade tables asked the d100 for more than it holds, and
    the layout's cursor ran off the end — the smith's mountain seam (22 materials) kept
    19 and lost both legendary metals; the enchanter's underground gem seam lost its
    exotic and legendary stones."""
    from rules import biomes

    for key in gathering.excursion_keys():
        spec = gathering.excursion(key)
        if spec.get("source") == "ingredients":
            continue
        for b in biomes.EVERYWHERE:
            pool = benches.obtainable(spec["track"], spec["obtain"], biome=b)
            rows = gathering.material_table(spec, b, 5).rows
            assert len(rows) == min(len(pool), 95), (key, b, len(rows), len(pool))
            assert not rows or rows[-1].high <= 95


def test_the_ground_sets_the_dc_for_what_the_trade_seeks():
    """Every trade took the herb DC: a mountain was DC 17 to a smith because it is DC 17
    to a herbalist. Ultimate Wilderness sets the DC by how much of the thing sought is
    there — abundant 10, standard 15, barren 20 — so a mountain is barren herb ground and
    abundant ore ground."""
    prospect = gathering.excursion("blacksmith:prospect")
    assert gathering.dc_for(prospect, "mountain") == 10
    assert gathering.dc_for(gathering.excursion("herbalist:forage"), "mountain") == 17
    assert gathering.dc_for(gathering.excursion("alchemist:quarry"), "grassland") == 20


def test_one_of_one_is_not_rolled():
    """`Dice.parse` refuses "1d1": 53 of 100 four-hour prospects in the desert raised
    BadDice (2026-10-06), because the desert's only common mined material is one row and
    the prospect rolled f"1d{len(pool)}" to pick it."""
    assert gathering.pick_index(Dice(seed=1), 1, "x") == 0
    for seed in range(10):
        s, e = _table(seed, "desert", "blacksmith", 1)
        _run(e, "prospect", 4, 15)


def test_every_open_ground_excursion_runs_through_the_door():
    """The ratchet: a craft that offers gathering on open ground has a table here, so a
    new one cannot ship a fourth formula beside the door."""
    missing = [a["key"] for a in benches.acquisitions()
               if a["requires"] == "biome" and gathering.excursion(a["key"]) is None]
    assert missing == []


def test_gathering_pays_mastery_and_failure_teaches_twice():
    """No gathering paid any mastery before the door: four hours prospecting taught a
    smith nothing. Every successful hour pays a step now (owner, 2026-10-05: "every
    success pays"); a missed hour is a mishap, paid `MISHAP_LIMIT` times per ground."""
    s, e = _table(3, "hills", "blacksmith", 1)
    before = s.pc().track("blacksmith").mp
    out = _run(e, "prospect", 3, 20).outcomes[-1]
    assert s.pc().track("blacksmith").mp > before, out.tell
    assert "mastery" in out.tell

    hourly = [{"margin": -3, "biome": "hills", "picks": []}] * 6
    steps = gathering.mastery_steps(hourly)
    track = worldclass.get("blacksmith")
    progress = worldclass.Progress(track="blacksmith")
    paid = sum(worldclass.award_step(track, progress, method="prospect",
                                     ingredient_id=st["id"], rarity_rank=1,
                                     quality_index=0, success=False)["mp"]
               for st in steps)
    assert paid == worldclass.MISHAP_LIMIT * worldclass.MP_AWARDS["mishap"]
    # Ground with nothing of the trade's on it teaches nothing either way.
    assert gathering.mastery_steps([{"margin": -3, "empty": True, "picks": []}]) == []


def test_a_guarded_vein_of_ore_is_paid_by_its_own_name():
    """A booked find was paid by `ing_mod.get(iid).name` — the ingredient list — which
    raises KeyError on a vein of ore. And stone carries no herb's clock."""
    from rules import bestiary

    s, e = _table(1, "mountain")
    pc = s.pc()
    wolf = bestiary.search(text="wolf", limit=1)[0]
    import rules.gathering as g

    real = g.roll
    g.roll = lambda *a, **k: g.Encounter("guarded", 97, creature=wolf, yield_times=3)
    try:
        effects = [{"names": {"iron-ore": "Iron Ore"}}]
        e._gathering_encounter(pc, "mountain", 1, "ore", found={"iron-ore": 2},
                               effects=effects, spot="seam", dug=True, fresh=False)
    finally:
        g.roll = real
    guard = s.guarded_finds[0]["guard"]
    s.actors[guard].hp = -20
    line = e._settle_guarded_finds()
    assert "6× Iron Ore" in line, line
    assert pc.inventory.get("iron-ore") == 6
    assert "iron-ore" not in pc.picked_at


def test_prospect_hours_are_bounded_like_a_forage():
    """forage.hours was bounded at 48 and prospect.hours not at all: one authored value
    drove the hour loop as long as it liked."""
    s, e = _table(1, "hills")
    for op, extra in (("prospect", {}), ("gather", {"key": "alchemist:quarry"})):
        intent = e.validate([{"op": op, "actor": "pc", "because": "t",
                              "params": dict({"hours": 5000}, **extra)}])[0]
        assert intent.params["hours"] == 48, op


def test_harvest_tags_are_read_off_the_carcass(monkeypatch):
    """Owner, 2026-10-05: "Apply the tags to the beasts and just have a reader in
    skinning to find the relevant tag; no list is necessary." The carcass excursions
    matched the creature's display name, so a world's beast named in its own words
    yielded nothing of its own. A tag naming a material the shelf lacks is ignored."""
    from rules.bestiary import instantiate

    s, _e = _table(1, "forest")
    beast = instantiate("guard dog", scene=s, name="a marsh strider")
    monkeypatch.setattr(type(beast), "standing_tags", lambda self: (
        "harvest.hide.wolf-pelt", "harvest.hide.no-such-hide", "harvest.reagent.x"))
    got = [m.id for m in gathering.harvest_tagged(beast, "leatherworker")]
    assert got == ["wolf-pelt"]
    by_name = [m.id for m in gathering.carcass_yield("leatherworker", "harvested", beast,
                                                     "a marsh strider")]
    assert "wolf-pelt" in by_name
    # No tags: the name is matched as before.
    monkeypatch.setattr(type(beast), "standing_tags", lambda self: ())
    assert "wolf-pelt" in [m.id for m in gathering.carcass_yield(
        "leatherworker", "harvested", beast, "wolf")]


# --- the craft panel: every trade narrated -----------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    from play import campaign as cm, craft_views

    monkeypatch.setattr(craft_views, "_narrate", lambda *a, **k: None)
    told: list = []

    def closing(c, opening, outcomes, line):
        told.append((opening, [o.tell for o in outcomes], line))
        return ""

    monkeypatch.setattr(craft_views, "_narrate_outcome", closing)
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        stand_on(c.scene, "mountain")
        c.save()
        cl = Client()
        cl.told = told
        yield cl
        cm._LIVE.clear()


def test_a_prospect_from_the_panel_is_told_like_a_forage(client):
    """The smith's Prospect was one d20 and a tally line; it is the forage's three beats
    now — the setting out, the finding before the tally, "What do you do?" — with the
    player's own check, and the closing is fed the haul's tell alone (law three), never
    the mastery line or the encounter, which has its own scene call."""
    from play import campaign as cm

    before = len(cm.current().transcript)
    r = client.post("/api/craftaction", data=json.dumps(
        {"action": "blacksmith:prospect", "hours": 3}), content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    assert "prospecting" in r.json()["roll"]["label"]
    assert r.json()["roll"]["dc"] == 10
    r = client.post("/api/craftaction", data=json.dumps({"face": 18}),
                    content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    d = r.json()
    book = cm.current().transcript[before:]
    assert "prospect for ore" in book[0]["text"]
    assert "Gathered:" in book[1]["text"] and book[-1]["text"] == "What do you do?"
    assert d["suggestions"][0] in ("Keep prospecting",) or "Approach" in d["suggestions"][0]
    assert client.told, "the closing never reached the narrator"
    opening, tells, line = client.told[-1]
    assert tells and "of digging" in tells[0] or "nothing" in tells[0]
    assert not any("mastery" in t for t in tells), tells
    assert cm.current().scene.clock_minutes > 0


def test_a_refused_excursion_tells_no_hours_passing(client):
    """Seen live 2026-10-07: a quarry refused for the Atomie still in the scene printed
    "The hours pass in digging and sorting, and the ground gives nothing back" over no
    time at all. The refusal's own tell is the beat now."""
    from play import campaign as cm
    from rules.bestiary import instantiate

    c = cm.current()
    c.scene.add(instantiate("thug", scene=c.scene, name="a road warden"))
    c.save()
    r = client.post("/api/craftaction", data=json.dumps(
        {"action": "alchemist:quarry", "hours": 2}), content_type="application/json")
    assert r.status_code == 200
    line = cm.current().transcript[-2]["text"]
    assert line.startswith("No gathering happens.") and "hours pass" not in line, line


def test_the_hub_no_longer_has_a_formula_of_its_own(client):
    """`/api/craft/excursion` on open ground runs the door too: hours on the clock, the
    body charged hour by hour, the haul from the trade's table."""
    from play import campaign as cm

    clock = cm.current().scene.clock_minutes
    r = client.post("/api/craft/excursion", data=json.dumps(
        {"action": "alchemist:quarry", "hours": 2}), content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    d = r.json()
    assert d["dc"] == gathering.dc_for(gathering.excursion("alchemist:quarry"), "mountain")
    assert cm.current().scene.clock_minutes >= clock + 2 * 60
    assert "hour" in d["tell"]


def test_a_closing_naming_the_ore_it_found_is_not_invented_loot():
    """The first live prospect (2026-10-07) was narrated "you gather a handful of copper
    and nickel ore" for a haul of 4 Copper Ore and 2 Nickel Ore, and the substring check
    read the shelf's metal "Copper" inside it as invented loot: the model's closing was
    thrown away and the floor printed instead."""
    from play import craft_views
    from rules import blacksmith

    shelf = [m.name for m in blacksmith.materials().values()]
    good = "you gather a handful of copper and nickel ore from the shattered stone"
    assert not craft_views.invents_loot(good, ["Copper Ore", "Nickel Ore"], shelf)
    assert craft_views.invents_loot("and a lump of adamantine besides", ["Copper Ore"],
                                    shelf)
    # The first live quarry: the closing named the ore its tell said was spoiled.
    tell = "1 hour came to nothing but Lead Ore broken up and lost in the getting."
    assert not craft_views.invents_loot("the lead ore has crumbled into useless grit",
                                        ["Rock Salt"], shelf, told=tell)


def test_the_page_sends_open_ground_to_the_narrated_door():
    from pagesource import table_source

    js = table_source()
    assert 'data-gather="${esc(a.key)}"' in js
    assert 'a.requires === "biome"' in js
