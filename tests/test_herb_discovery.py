"""Herb discovery: what a character knows about each herb, and the four ways to learn
more (docs/herbalism-revamp-plan.md §8; the API is docs/herbalism-contracts.md §4).

Before the revamp every property of every herb read as known (the scaffold's
`known_keys` returned them all), so a character who had never seen hemlock knew it
paralyses, and nothing in the game could be discovered. What is pinned here:

* tasting is real: the dose is spent, the herb's own specs land through the one
  applicator with `origin item:<id>`, a poison's save GATES its body, and at most one
  benefit and one drawback are learned;
* a deadly taste kills or downs through the existing doors (`Actor.die`, the hit-point
  ladder), so the table's deathveil sees it;
* an unknown property never reaches the narrator's brief or the taste's tell (law 3);
* study is a skill check on the player's die with no automatic natural 20, reveals one
  more property per 5 over the DC, and a miss waits for a rest;
* a teacher is gated by attitude and paid; a library tells only common knowledge;
* a manual pays mastery once; a herbalist's homeland and crafted herbs are seeded once;
* the knowledge survives a save, and every §4 endpoint answers its contract's shape.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.test import Client, override_settings

from rules import herbknowledge as hk
from rules import ingredients as ing_mod
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from tests._places import stand_on


def _scene(*herbs, hp=None):
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    for h in herbs:
        pc.inventory[h] = pc.inventory.get(h, 0) + 1
    if hp is not None:
        pc.hp = hp
    return s, pc


def _taste(s, herb, seed=1):
    e = Engine(s, Dice(seed=seed))
    return e.run(e.validate([{"op": "taste", "actor": "pc", "params": {"item": herb}}]))


def _ing(i):
    return ing_mod.get(i)


# Fixture herbs, each with exactly the specs a mechanics test needs. Added 2026-10-02 when
# the relevance pass rewrote the corpus: hemlock gained a poultice in front of its poison
# and a four-minute paralysis, Menhirite's "Causes dead" went (a misparse), and Monkshood
# gained a liniment that healed its own taster back up, so six tests that pinned shipped
# herbs failed with every rule still working. A mechanism pinned to a fixture cannot be
# broken by the next data edit; a test about the shipped corpus still reads the corpus.
TESTBANE = {  # hemlock as it was: a Fortitude DC 15 gate on an unbounded paralysis
    "id": "testbane", "name": "Testbane", "kind": "herb", "tier": "common",
    "effects": [{"type": "save_gate", "target": "fort", "dc": 15, "route": "ingest"},
                {"type": "apply_condition", "target": "paralyzed", "route": "ingest"}]}
TESTMORT = {  # a death effect with no save, as Menhirite's misparse was
    "id": "testmort", "name": "Testmort", "kind": "herb", "tier": "common",
    "effects": [{"type": "apply_condition", "target": "dead", "route": "ingest"}]}
TESTSHADE = {  # Monkshood as it was: 1d3 lethal poison damage and nothing else
    "id": "testshade", "name": "Testshade", "kind": "herb", "tier": "common",
    "effects": [{"type": "damage", "dice": "1d3", "damage_type": "poison",
                 "lethality": "lethal", "route": "ingest"}]}


@pytest.fixture
def fixture_herbs(monkeypatch):
    """The three fixture herbs on the shelf beside the corpus, for one test."""
    shelf = dict(ing_mod.all_ingredients())
    for raw in (TESTBANE, TESTMORT, TESTSHADE):
        shelf[raw["id"]] = ing_mod.from_dict(raw)
    monkeypatch.setattr(ing_mod, "_ALL", shelf)
    return shelf


# --- the classifier --------------------------------------------------------------------

def test_drawback_or_benefit_is_read_off_the_spec(fixture_herbs):
    """The card's `drawback` field. Read from the structured spec, never the words: a
    condition caused, damage, ability damage and a penalty are drawbacks; healing, a
    bonus and a condition ended are benefits; a bare DC is neither. Measured on the
    corpus: 38 of 161 ingredients carry a bare "DC n" that gates nothing (the crafting
    DC restated), and filing those as drawbacks would invent 38 poisons.

    Re-pinned 2026-10-02 because the herb data changed: hemlock's poultice now sits at
    p0, so its gate moved to p1. The gate-to-body tie is asked of Testbane, a fixture
    with hemlock's old two specs, so a data edit cannot move it again."""
    assert hk.classify({"type": "apply_condition", "target": "paralyzed"}) == hk.DRAWBACK
    assert hk.classify({"type": "ability_damage", "target": "con", "dice": "1d6"}) == hk.DRAWBACK
    assert hk.classify({"type": "damage", "dice": "1d3", "damage_type": "poison"}) == hk.DRAWBACK
    assert hk.classify({"type": "skill_mod", "target": "perception", "amount": -2}) == hk.DRAWBACK
    assert hk.classify({"type": "heal", "dice": "1d4"}) == hk.BENEFIT
    assert hk.classify({"type": "save_mod", "target": "ref", "amount": 4}) == hk.BENEFIT
    assert hk.classify({"type": "remove_condition", "target": "paralyzed"}) == hk.BENEFIT
    assert hk.classify({"type": "save_gate", "dc": 15}) == hk.NEUTRAL
    # An authored gate that carries its own harm is the whole poison.
    assert hk.classify({"type": "save_gate", "dc": 15, "on_failure": [
        {"type": "apply_condition", "target": "nauseated"}]}) == hk.DRAWBACK
    # And the herb's own gate is tied to the body it guards.
    assert hk.anatomy(_ing("testbane"))["gate_of"] == {"p1": "p0"}


def test_nothing_is_known_before_anything_is_learned(fixture_herbs):
    """The scaffold read every property as known, which is how the game behaved before the
    revamp: a stranger to hemlock already knew it paralyses.

    Re-pinned 2026-10-02 because the herb data changed: hemlock went from 2 properties to
    4. Testbane, a fixture with hemlock's old 2, keeps the count exact."""
    _s, pc = _scene("testbane")
    assert hk.known_keys(pc, _ing("testbane")) == []
    assert hk.unknown_count(pc, _ing("testbane")) == 2
    card = hk.card(pc, _ing("testbane"))
    assert all(p["text"] is None and p["drawback"] is None for p in card["properties"])
    assert card["danger_known"] == ""


# --- tasting ---------------------------------------------------------------------------

def test_tasting_hemlock_paralyses_through_the_one_applicator(fixture_herbs):
    """The owner's rule: "Real risk ... applies the raw effect for real." Hemlock's own
    spec is "Fortitude DC 15 / Causes paralyzed"; a failed save puts a real paralysed
    `ActiveEffect` on the taster, and the record names the herb as the document.

    Re-pinned 2026-10-02 because the herb data changed: hemlock's paralysis now states
    4 minutes, so the rule row's bound for a condition that states none was no longer
    exercised by any shipped herb. Testbane, a fixture with hemlock's old specs, keeps
    the unbounded "Causes paralyzed" this test exists to bound."""
    from rules.activeeffect import ActiveEffect

    for seed in range(1, 40):
        s, pc = _scene("testbane")
        r = _taste(s, "testbane", seed=seed)
        save = next(o for o in r.outcomes[0:1])  # the taste outcome
        if pc.has_state("state.held"):
            break
    else:
        pytest.fail("no seed in 1..39 failed the DC 15 save")
    held = [e for e in pc.effects if isinstance(e, ActiveEffect) and e.key == "paralyzed"]
    assert held, pc.effects
    # Bounded by the rule row, never the unbounded paralysis the bare spec would mint.
    assert held[0].rounds_left == hk.lore()["taste"]["condition_minutes"] * 10
    taste = r.outcomes[0]
    assert taste.op == "taste"
    assert any(e.get("kind") == "taste" and e.get("origin") == "item:testbane"
               for e in taste.effects)
    assert "paralyzed" in taste.tell
    assert set(hk.known_keys(pc, _ing("testbane"))) == {"p0", "p1"}
    assert save is taste


def test_a_made_save_keeps_the_poison_body_off():
    """`use_item` rolls a poison's save and then lands the body whatever it said; a taste
    must not copy that. With the save made, nobody is paralysed."""
    for seed in range(1, 60):
        s, pc = _scene("hemlock")
        r = _taste(s, "hemlock", seed=seed)
        if "makes the Fortitude save" in r.outcomes[0].tell:
            assert not pc.has_state("state.held")
            return
    pytest.fail("no seed in 1..59 made the DC 15 save")


def test_a_buff_from_a_taste_names_the_herb_as_its_origin():
    """Nightshade's "+4 Reflex" lands as a typed modifier through the funnel, its
    `ActiveEffect.origin` the herb (stage 8's provenance rule)."""
    s, pc = _scene("nightshade")
    _taste(s, "nightshade", seed=3)
    assert any(getattr(e, "origin", "") == "item:nightshade" for e in pc.effects), \
        [(e.key, e.origin) for e in pc.effects]


@pytest.mark.parametrize("herb", sorted(ing_mod.all_ingredients()))
def test_a_taste_teaches_at_most_one_benefit_and_one_drawback(herb):
    """The ruling: a taste "reveals 1 positive and 1 negative trait (if the herb has a
    negative one)". Walked over the whole corpus, so a herb with five drawbacks still
    teaches one. A poison's gate rides with its body and is not a third trait. The dose
    is spent: one in, none left."""
    s, pc = _scene(herb)
    r = _taste(s, herb, seed=7)
    assert r.outcomes[0].op == "taste" and r.outcomes[0].status != "refused", r.outcomes[0].tell
    ing = _ing(herb)
    a = hk.anatomy(ing)
    learned = hk.known_keys(pc, ing)
    gates = set(a["gate_of"].values())
    bad = [k for k in learned if a["kinds"][k] == hk.DRAWBACK]
    good = [k for k in learned if a["kinds"][k] != hk.DRAWBACK and k not in gates]
    assert len(bad) <= 1 and len(good) <= 1, (learned, a["kinds"])
    if any(v == hk.DRAWBACK for v in a["kinds"].values()):
        assert len(bad) == 1
    assert pc.inventory.get(herb, 0) == 0


def test_a_second_taste_teaches_what_the_first_did_not():
    """"It prefers traits you don't know yet, so tasting a second time teaches you
    something new." Nightshade has one benefit and three drawbacks."""
    s, pc = _scene("nightshade", "nightshade")
    _taste(s, "nightshade", seed=3)
    first = set(hk.known_keys(pc, _ing("nightshade")))
    pc.clear_states("recovery.rest")
    for e in list(pc.effects):
        if e.key == "paralyzed":
            pc.remove_effects(kind="condition", match=lambda x: x.key == "paralyzed")
    _taste(s, "nightshade", seed=4)
    second = set(hk.known_keys(pc, _ing("nightshade")))
    assert second > first


def test_the_dose_is_spent_and_none_is_refused_in_words():
    """The dose first, as a jar's is. With nothing left the taste is refused and says
    what is carried — never a raise the turn dies on."""
    s, pc = _scene("comfrey")
    pc.inventory["comfrey"] = 2
    _taste(s, "comfrey")
    assert pc.inventory["comfrey"] == 1
    _taste(s, "comfrey")
    assert "comfrey" not in pc.inventory
    r = _taste(s, "comfrey")
    assert r.outcomes[0].status == "refused"
    assert "no Comfrey" in r.outcomes[0].tell


def test_a_deadly_taste_kills_through_the_one_door(fixture_herbs):
    """Menhirite "Causes dead". Death is written by `Actor.die`, the door that clears the
    ladder above it, never a bare condition op beside a living body.

    Re-pinned 2026-10-02 because the herb data changed: no shipped herb applies "dead"
    now, which is right (Menhirite's and Nahre Lotus's were misparses). The door is still
    the taste's to use, for a homebrew herb that does kill, so Testmort, a fixture death
    effect with no save, keeps it tested."""
    s, pc = _scene("testmort")
    assert not pc.is_dead  # the premise
    r = _taste(s, "testmort")
    assert pc.is_dead
    assert "is dead" in r.outcomes[0].tell


def test_a_poison_that_hurts_downs_through_the_hit_point_ladder(fixture_herbs):
    """Monkshood's 1d3 poison damage on a taster at 1 hit point crosses the ladder the
    way a blow does, and the tell says so.

    Re-pinned 2026-10-02 because the herb data changed: Monkshood gained a liniment that
    heals 1d3, and a taste lands every property, so the taster was healed straight back
    to 1 hit point. Testshade, a fixture with Monkshood's old damage alone, keeps the
    ladder crossing tested."""
    s, pc = _scene("testshade", hp=1)
    r = _taste(s, "testshade", seed=2)
    assert pc.hp <= 0
    assert pc.has_state("state.down") or pc.has_condition("disabled") or pc.hp == 0
    assert any(w in r.outcomes[0].tell for w in ("dying", "unconscious", "disabled"))


# --- the narrator gate (law 3) -----------------------------------------------------------

@pytest.fixture
def camp(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.turn_log.clear()
        yield c
        cm._LIVE.clear()


def _brief(c):
    from gm import prompts

    return prompts.scene_brief(c.world, c.scene, c.location, [])


def test_an_unknown_property_never_reaches_the_brief(camp):
    """Plan §8.1: "The narrator never learns an unknown property." Nightshade carried with
    only its Reflex bonus known: the brief names the herb and that line, and none of the
    three it does not know — grepped for each hidden line's own text."""
    pc = camp.scene.pc()
    pc.inventory["nightshade"] = 2
    hk.reveal(pc, "nightshade", ["p1"], "test")
    brief = _brief(camp)
    ing = _ing("nightshade")
    lines = dict(zip(hk.property_keys(ing), ing.lines))
    assert "Nightshade ×2" in brief
    assert lines["p1"] in brief
    for k in ("p0", "p2", "p3", "p4"):
        assert lines[k] not in brief, (k, lines[k])
    assert "3 more not known" in brief or "4 more not known" in brief


def test_a_herb_known_of_nothing_says_so_and_nothing_else(camp):
    pc = camp.scene.pc()
    pc.inventory["hemlock"] = 1
    brief = _brief(camp)
    assert "Hemlock (nothing known of what it does)" in brief
    assert "paralyzed" not in brief.lower()


def test_the_taste_tell_names_only_what_was_learned():
    """The tell is what reaches the narrator. Nightshade does four things to a taster and
    teaches two: the Constitution damage it did not teach is "at work" and unnamed."""
    s, pc = _scene("nightshade")
    r = _taste(s, "nightshade", seed=3)
    tell = r.outcomes[0].tell
    ing = _ing("nightshade")
    lines = dict(zip(hk.property_keys(ing), ing.lines))
    known = set(hk.known_keys(pc, ing))
    for k, line in lines.items():
        if k not in known:
            assert line not in tell, (k, line, tell)
    assert "Constitution damage" not in tell or "p2" in known


# --- study ---------------------------------------------------------------------------------

def test_study_dc_is_ten_plus_five_a_band():
    assert hk.study_dc(_ing("comfrey")) == 10           # common
    assert hk.study_dc(_ing("grave-mold")) == 15        # uncommon
    assert hk.study_dc(_ing("basilisk-eye")) == 20      # rare
    assert hk.study_dc(_ing("phoenix-feather")) == 30   # legendary


def test_study_reveals_one_more_per_five_over():
    """"Success reveals one unknown property, and one more for every 5 points above the
    DC." Nightshade (DC 10) at 20 is three; its gate rides with its body for free."""
    _s, pc = _scene("nightshade")
    ing = _ing("nightshade")
    got = hk.study(pc, ing, 20, clock=0)
    assert got["success"] and got["margin"] == 10
    bodies = [k for k in got["revealed"] if k not in set(hk.anatomy(ing)["gate_of"].values())]
    assert len(bodies) == 3
    assert hk.danger_known(pc, ing)        # a drawback was among them


def test_study_has_no_automatic_natural_twenty(camp):
    """A skill check succeeds on its total alone (CRB p.180); `d20_succeeds` is for saves
    and attacks. A natural 20 short of a legendary herb's DC 30 is a miss."""
    pc = camp.scene.pc()
    pc.inventory["phoenix-feather"] = 1
    pc.ranks.pop("appraise", None)
    pc.ranks["knowledge (nature)"] = 1
    camp.save()
    d = Client().post("/api/herb/study", data=json.dumps({"id": "phoenix-feather", "face": 20}),
                      content_type="application/json").json()
    assert d["roll"]["face"] == 20 and d["roll"]["total"] < 30
    assert d["roll"]["success"] is False and d["revealed"] == []


def test_a_missed_study_waits_for_a_rest(camp):
    """"A miss teaches nothing and can be retried after a rest." The second try before
    sleeping is refused; after a night it is allowed."""
    pc = camp.scene.pc()
    pc.inventory["comfrey"] = 1
    pc.ranks.pop("appraise", None)
    pc.ranks["knowledge (nature)"] = 1
    camp.save()
    c = Client()
    first = c.post("/api/herb/study", data=json.dumps({"id": "comfrey", "face": 1}),
                   content_type="application/json")
    assert first.status_code == 200 and first.json()["roll"]["success"] is False
    again = c.post("/api/herb/study", data=json.dumps({"id": "comfrey", "face": 20}),
                   content_type="application/json")
    assert again.status_code == 409, again.json()
    from play import campaign as cm

    live = cm.current()
    live.scene.pc().awake_minutes = 0          # a night's sleep (rules/survival.py `sleep`)
    live.scene.advance(8 * 60, charge_body=False)
    live.save()
    third = c.post("/api/herb/study", data=json.dumps({"id": "comfrey", "face": 20}),
                   content_type="application/json")
    assert third.status_code == 200 and third.json()["roll"]["success"] is True


# --- teachers and libraries ---------------------------------------------------------------

def _healer(c, step=None):
    from rules.bestiary import instantiate

    s = c.scene
    healer = instantiate("guildhand", scene=s, name="the herbalist")
    s.add(healer)
    if step:
        c.engine().settle_attitude(healer, step)
    c.scene.pc().purse = {"gp": 5}
    c.scene.pc().inventory["nightshade"] = 1
    c.save()
    return healer.ref


def test_a_hostile_teacher_refuses_in_words_and_takes_nothing(camp):
    """Gated the way confiding is (rules/confiding.py): below indifferent, nothing is
    taught and no coin moves."""
    ref = _healer(camp, "hostile")
    card = Client().get("/api/herb/nightshade").json()
    assert [t["ref"] for t in card["teachers_here"]] == [ref]
    d = Client().post("/api/herb/ask", data=json.dumps({"id": "nightshade", "ref": ref}),
                      content_type="application/json").json()
    assert d["refused"] and d["revealed"] == [] and d["paid"] == ""
    from play import campaign as cm

    assert cm.current().scene.pc().purse == {"gp": 5}


def test_a_friendly_teacher_tells_two_dangers_first_for_a_fee(camp):
    ref = _healer(camp, "friendly")
    d = Client().post("/api/herb/ask", data=json.dumps({"id": "nightshade", "ref": ref}),
                      content_type="application/json").json()
    assert d["refused"] == "" and d["paid"] == "2 sp"
    bodies = [p for p in d["revealed"] if p["drawback"]]
    assert len(bodies) == 2


def test_a_library_tells_only_common_knowledge(camp, monkeypatch):
    """"It reveals what the world knows (the herb's common properties), never its rare
    secrets." Nightshade's benefit comes back and its three drawbacks do not; a rare
    herb is not written of at all."""
    from play import herb_views

    monkeypatch.setattr(herb_views, "library_here",
                        lambda c: {"name": "the library", "price": "5 sp", "minutes": 60})
    camp.scene.pc().purse = {"gp": 5}
    camp.save()
    d = Client().post("/api/herb/library", data=json.dumps({"id": "nightshade"}),
                      content_type="application/json").json()
    assert d["revealed"] and not any(p["drawback"] for p in d["revealed"])
    assert d["paid"] == "5 sp" and d["minutes"] == 60
    assert hk.common_knowledge(_ing("basilisk-eye")) == []
    rare = Client().post("/api/herb/library", data=json.dumps({"id": "basilisk-eye"}),
                         content_type="application/json").json()
    assert rare["revealed"] == [] and rare["refused"]


# --- manuals --------------------------------------------------------------------------------

def test_every_manual_teaches_real_herbs():
    """A manual names herbs by id; an id the corpus does not hold would teach nothing and
    say nothing. Four to six books, each priced, timed and teaching something."""
    books = hk.manuals()
    assert 4 <= len(books) <= 6
    for m in books.values():
        assert m["price_gp"] > 0 and m["hours"] > 0 and m["name"]
        for row in m["teaches"]:
            assert row["ingredient"] in ing_mod.all_ingredients(), row
        assert hk.manual_keys(m), m["id"]


def test_a_manual_pays_mastery_once(camp):
    """Plan §8.4: "pays +5 mastery once (unread -> read is recorded per manual)"."""
    from rules.crafting import Stock

    pc = camp.scene.pc()
    book = hk.manuals()["hedge-wifes-almanac"]
    pc.add_stock(Stock(base=book["name"], craft=""), 1)
    camp.save()
    c = Client()
    first = c.post("/api/herb/manual", data=json.dumps({"item": book["id"]}),
                   content_type="application/json").json()
    assert first["mastery"]["lines"] == [{"why": f"read {book['name']}", "mp": 5}]
    assert first["revealed"] and first["minutes"] == book["hours"] * 60
    second = c.post("/api/herb/manual", data=json.dumps({"item": book["id"]}),
                    content_type="application/json").json()
    assert second["mastery"]["lines"] == [] and second["revealed"] == []
    from play import campaign as cm

    assert cm.current().scene.pc().manuals_read == [book["id"]]


def test_a_manual_not_carried_is_not_read(camp):
    d = Client().post("/api/herb/manual", data=json.dumps({"item": "hedge-wifes-almanac"}),
                      content_type="application/json")
    assert d.status_code == 400


# --- what a herbalist already knows ----------------------------------------------------------

def test_the_homeland_seed_is_the_owners_ruling_and_runs_once():
    """Q4: a new herbalist knows the common herbs native to their homeland's biomes, every
    property, how = "homeland". Run twice, the second does nothing."""
    s, pc = _scene()
    pc.track("herbalist")
    seeded = hk.seed_homeland(pc, ["swamp"])
    assert "marsh-mallow" in seeded and "anise" in seeded
    assert "hemlock" not in seeded                      # forest and grassland
    assert "fleshshiver" not in seeded                  # uncommon
    ing = _ing("marsh-mallow")
    assert hk.known_keys(pc, ing) == hk.property_keys(ing)
    assert set(pc.herb_known["marsh-mallow"]["how"].values()) == {"homeland"}
    assert hk.seed_homeland(pc, ["forest"]) == []
    assert hk.ensure_seeded(pc, scene=s).get("homeland") is None


def test_a_non_herbalist_is_seeded_nothing():
    s, pc = _scene()
    pc.world_classes.pop("herbalist", None)
    assert hk.ensure_seeded(pc, scene=s) == {}
    assert not pc.herb_known


def test_the_homeland_is_the_peoples_own_homeland_fact():
    """A world race's people carry a `Homeland` fact ("The Pangrellan grasslands of
    southern Kaelinora"); that is where the herbalist grew up, not where the campaign
    happened to open."""
    from world import loader

    world = loader.load_cached("fixtures/pangrella-campaign.json")
    _s, pc = _scene()
    pc.race = "korvu"
    assert hk.homeland_biomes(pc, world=world) == ["grassland"]


def test_a_converted_herbalist_knows_what_they_crafted_with():
    """Plan §14 item 4: "a converted herbalist knows every property of every herb they
    have already crafted with"."""
    _s, pc = _scene()
    pc.track("herbalist").crafted["woundwort styptic"] = 3
    pc.track("herbalist").crafted["distilled juniper berry tea"] = 1
    got = hk.seed_converted(pc)
    assert "woundwort" in got and "juniper-berry" in got and "juniper" not in got
    assert hk.unknown_count(pc, _ing("woundwort")) == 0
    assert hk.seed_converted(pc) == []


def test_the_knowledge_survives_a_save():
    """`herb_known` and `manuals_read` round-trip, the seed marks with them — a seed that
    forgot it ran would re-seed over what the character learned since."""
    _s, pc = _scene()
    pc.track("herbalist")
    hk.seed_homeland(pc, ["swamp"])
    hk.reveal(pc, "hemlock", ["p1"], "tasted, day 3")
    pc.manuals_read.append("what-not-to-eat")
    back = from_dict(json.loads(json.dumps(to_dict(pc))))
    assert back.herb_known == pc.herb_known
    assert back.manuals_read == ["what-not-to-eat"]
    assert hk.seed_homeland(back, ["forest"]) == []


# --- the endpoints' shapes (docs/herbalism-contracts.md §4) -----------------------------------

def test_every_endpoint_answers_its_contract(camp, monkeypatch):
    from play import herb_views

    pc = camp.scene.pc()
    pc.inventory.update({"comfrey": 3, "hemlock": 1})
    pc.purse = {"gp": 5}
    pc.ranks.pop("appraise", None)
    pc.ranks["knowledge (nature)"] = 1
    camp.save()
    c = Client()

    d = c.get("/api/herbarium").json()
    row = next(e for e in d["entries"] if e["id"] == "comfrey")
    assert set(row) >= {"id", "name", "kind", "part", "tier", "known", "total", "biomes",
                        "carried"}
    assert row["carried"] == 3 and row["part"]

    card = c.get("/api/herb/comfrey").json()
    assert set(card) >= {"id", "name", "kind", "part", "tier", "biomes", "danger_known",
                         "properties", "can_study", "study_minutes", "can_taste",
                         "teachers_here", "library_here"}
    assert set(card["properties"][0]) == {"key", "known", "text", "drawback", "how"}
    assert card["can_taste"] is True
    assert c.get("/api/herb/no-such-herb").status_code == 404

    st = c.post("/api/herb/study", data=json.dumps({"id": "comfrey", "face": 15}),
                content_type="application/json").json()
    assert set(st) >= {"roll", "revealed", "minutes", "clock"}
    assert set(st["roll"]) >= {"face", "bonus", "total", "dc", "success", "margin"}
    assert st["minutes"] == 10 and "label" in st["clock"]

    ta = c.post("/api/herb/taste", data=json.dumps({"id": "comfrey"}),
                content_type="application/json").json()
    assert set(ta) >= {"revealed", "tells", "minutes", "down"}
    assert ta["minutes"] == 1 and ta["down"] is False and ta["tells"]

    monkeypatch.setattr(herb_views, "library_here",
                        lambda c: {"name": "the library", "price": "5 sp", "minutes": 60})
    li = c.post("/api/herb/library", data=json.dumps({"id": "hemlock"}),
                content_type="application/json").json()
    assert set(li) >= {"revealed", "paid", "minutes", "refused"}

    ask = c.post("/api/herb/ask", data=json.dumps({"id": "comfrey", "ref": "c999"}),
                 content_type="application/json")
    assert ask.status_code == 400 and "error" in ask.json()

    ma = c.post("/api/herb/manual", data=json.dumps({"item": "nonsense"}),
                content_type="application/json")
    assert ma.status_code == 400 and "error" in ma.json()

    bad = c.post("/api/herb/study", data=json.dumps({"id": "hemlock", "face": 40}),
                 content_type="application/json")
    assert bad.status_code == 400


def test_a_fatal_taste_from_the_card_ends_the_campaign(camp, fixture_herbs):
    """`down` is true and the campaign ends the way the table's own turn ends it, so the
    deathveil has something to show.

    Re-pinned 2026-10-02 because the herb data changed: Menhirite no longer kills (its
    "Causes dead" was a misparse), so the card's Taste button is driven with Testmort, a
    fixture death effect, through the same endpoint."""
    camp.scene.pc().inventory["testmort"] = 1
    camp.save()
    d = Client().post("/api/herb/taste", data=json.dumps({"id": "testmort"}),
                      content_type="application/json").json()
    assert d["down"] is True and d.get("ended") == "died"


def test_a_taste_is_history(camp):
    """The Journal's History shows "You tasted hemlock." from the turn-log row the card
    writes — engine facts, never prose (play/history.py)."""
    from play import campaign as cm
    from play import history

    camp.scene.pc().inventory["hemlock"] = 1
    camp.save()
    Client().post("/api/herb/taste", data=json.dumps({"id": "hemlock"}),
                  content_type="application/json")
    lines = [l["text"] for d in history.history(cm.current())["days"] for l in d["lines"]]
    assert "You tasted hemlock." in lines


def test_a_two_word_herb_reads_as_one_noun_in_history(camp):
    """Seen in the running page: "You tasted basilisk Eye." — the first letter lowered and
    the title-cased rest left standing."""
    from play import history

    camp.turn_log.append({"kind": "resolution", "outcomes": [{"intent_id": "i", "op": "taste",
                          "tell": "", "effects": [{"ref": camp.scene.pc().ref, "kind": "taste",
                                                   "name": "Basilisk Eye"}]}]})
    lines = [l["text"] for d in history.history(camp)["days"] for l in d["lines"]]
    assert lines == ["You tasted basilisk eye."]


def test_a_library_is_the_settlement_tables_own():
    """`library_here` reads the places the settlement already has (rules/places.py),
    never mints one: Mirabalos in the shipped world has "the library"; a village with
    none has none."""
    from rules import places
    from world import loader

    world = loader.load_cached("fixtures/pangrella-campaign.json")
    assert any(hk.is_library(p) for p in places.home_set(world.get("7ef5e373c993")))
    assert not any(hk.is_library(p) for p in places.home_set(world.get("5bbd0c40345f")))


# --- the declaration, detected in code -------------------------------------------------------

def _declared(text, *herbs):
    from gm import judgement

    s, pc = _scene(*herbs)
    return judgement.declare_taste([], text, s), judgement


def test_a_nibble_is_a_taste_and_not_a_meal():
    """"chew" is an eating word, and before this "I chew a bit of the root" reset the
    hunger clock and left the narrator to say what the root does."""
    out, judgement = _declared("I chew a bit of the hemlock root.", "hemlock")
    assert out == [{"op": "taste", "actor": "pc",
                    "because": "the player tastes it to learn what it does",
                    "params": {"item": "hemlock"}}]
    s, _pc = _scene("hemlock")
    assert not any(r["op"] == "eat" for r in judgement.inject_survival(out, "I chew a bit "
                                                                       "of the hemlock root.", s))


def test_a_plant_word_finds_the_one_herb_carried():
    out, _ = _declared("I carefully taste the leaf", "comfrey")
    assert out[-1]["params"]["item"] == "comfrey"


def test_tasting_the_stew_is_not_a_herb():
    out, _ = _declared("I taste the stew. It is good.", "comfrey")
    assert out == []
    out, _ = _declared("Should I taste the hemlock?", "hemlock")
    assert out == []


def test_a_taste_drops_a_number_the_plan_wrote():
    from gm import judgement

    s, _pc = _scene("comfrey")
    out = judgement.declare_taste([{"op": "heal", "params": {"amount": "1d4"}},
                                   {"op": "eat"}], "I nibble the comfrey", s)
    assert [r["op"] for r in out] == ["taste"]


def test_taste_is_a_declared_op_and_not_an_amount_op():
    from gm import judgement
    from rules.intents import AMOUNT_OPS, OPS

    s, _pc = _scene("comfrey")
    assert "taste" in judgement.declared_ops("I nibble the comfrey root", s)
    assert "taste" not in AMOUNT_OPS
    assert OPS["taste"][0] == ("item",)


# --- the lead's request: endless levels say what they bank -----------------------------------

def test_a_level_beyond_the_tracks_table_is_reported_as_banked_perk_picks():
    """Herbalist 4 used to read "Unlocked: neutralize; tools: ..." because `track.at`
    clamps to the last row: a repeat of the last unlock, not what the level gives."""
    from rules import worldclass

    s, pc = _scene()
    track = worldclass.get("herbalist")
    progress = pc.track("herbalist")
    progress.level = track.max_level
    progress.mp = 10 ** 6
    e = Engine(s, Dice(seed=1))
    r = e.run(e.validate([{"op": "craft", "actor": "pc", "params": {
        "track": "herbalist", "recipe": "a test brew", "tier": "legendary"}}]))
    tell = r.outcomes[0].tell
    beyond = f"is Herbalist {track.max_level + 1}."
    assert beyond in tell
    said = tell.split(beyond, 1)[1].split(" is Herbalist ")[0]
    assert "banks perk picks" in said and "Unlocked" not in said, said


# --- the Journal ----------------------------------------------------------------------------

def test_the_journal_draws_a_herbarium_beside_history():
    """UI plan §6.6, read statically. The list's id is not the card's heading id — the
    history card's first cut replaced its own heading by sharing one."""
    js = Path("play/static/js/table/21-tab-journal.js").read_text(encoding="utf-8")
    assert '"/api/herbarium"' in js and "/api/herb/" in js
    assert 'id="jr-herbarium-list"' in js
    assert 'sheetCard("jr-herbarium", "Herbarium"' in js
    assert "No herbs yet. Forage or buy one and it appears here." in js
    assert "Unknowns first" in js
    assert "BenchIcons" in js
    assert " of ${e.total} known" in js
