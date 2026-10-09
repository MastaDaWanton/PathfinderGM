"""The harvest of a carcass (docs/leatherworking-revamp-plan.md §5, §6; contracts §5;
docs/deeds-plan.md §10, §13; lane C).

Each test names the measured defect it prevents (plan §23.1 C, deeds plan §12 and §13.5).
Driven on the shipped bestiary's real blocks and tags, on a real campaign through the
Django test client where the route is the thing under test.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings
from django.urls import resolve

from play import campaign as cm
from play import harvest_views
from rules import bestiary, effects, harvest, herbprep
from rules import leatherworker as lw
from rules.sheet import from_dict, load_pc, to_dict as actor_to_dict


# --- fixtures ------------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        harvest_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        c.save()
        yield Client()
        cm._LIVE.clear()
        harvest_views._PENDING.clear()


def _c():
    return cm.current()


def _corpse(template: str, name: str | None = None):
    """A dead creature from a bestiary block, lying where the party stands."""
    c = _c()
    a = c.scene.add(bestiary.instantiate(template, scene=c.scene, name=name))
    a.die("test")
    harvest.mark_the_dead(c.scene)
    c.save()
    return a


def _get(client, path):
    r = client.get(path)
    return r.status_code, json.loads(r.content)


def _post(client, path, body):
    r = client.post(path, data=json.dumps(body), content_type="application/json")
    return r.status_code, json.loads(r.content)


def _hides(rows):
    return [r["material"] for r in rows if r["branch"] == "hide"]


class Body:
    """A dead body of a block, for the reader alone (no scene)."""

    def __init__(self, template, name="it"):
        self.from_template = template
        self.name = name
        self.ref = "c99"
        self.effects = []
        self.harvested = {}
        self.died_at = 0
        self.is_pc = False

    def has_state(self, tag):
        return tag == "state.down.dead"


# --- the reader: tags on the beast, never its name ----------------------------------------

def test_a_red_dragon_offers_only_red_dragonhide():
    """Inventory §0.4: "a red dragon offered all 11 colours" — the old reader matched the
    fragment "dragon" against every dragonhide. Choral the Conqueror's own block (fire cone
    breath, chaotic evil) says red; nothing in its name is asked, and the validator refuses
    another colour's tag on it."""
    block = harvest.block_of("choral-the-conqueror")
    assert harvest.dragon_colour(block) == "red-dragonhide"
    assert [m for b, m in harvest.tagged(block) if b == "hide"] == ["red-dragonhide"]
    wrong = dict(block, tags=["harvest.hide.blue-dragonhide"])
    assert "harvest.hide.blue-dragonhide" in harvest.refused_tags(wrong)
    assert all(m != "blue-dragonhide" for _, m in harvest.tagged(wrong))


def test_no_humanoid_or_native_outsider_offers_anything():
    """Inventory §0.4: "109 humanoids yielded a hide"; and the owner's 2026-10-08 answer 3b:
    native outsiders (aasimar, tieflings, sylphs) are peoples, banned the same way. Every
    such block in the shipped bestiary yields nothing, and a hand tag on one is refused."""
    store = bestiary.imported()
    peoples = [b for b in store.values() if harvest.banned(b)]
    assert len(peoples) > 3000
    assert [b["id"] for b in peoples if harvest.tagged(b)] == []
    aasimar = harvest.block_of("aasimar")
    assert "native outsider" in harvest.banned(aasimar)
    tagged = dict(aasimar, tags=["harvest.hide.generic.smooth"])
    assert harvest.validate_tags(tagged) and harvest.tagged(tagged) == []


def test_a_lion_a_shark_and_a_mastodon_yield_a_hide():
    """Inventory §0.4: "lion, elephant, mammoth, shark... yielded none" — no name fragment
    matched them. The tag pass and the generic rule by type give every animal a hide."""
    for template in ("lion", "shark-dire", "elephant-mastodon"):
        assert _hides(harvest.parts(Body(template), _kesst(), now=0)), template


def test_the_reader_never_reads_the_name():
    """Plan §5.3: the reader reads tags and stat-block fields only. A wolf the GM calls
    "Old Greymuzzle" still yields its pelt, and a scorpion called "the thing" is still
    poisonous (deeds plan §13.5, `test_dangers_never_read_the_name`)."""
    assert _hides(harvest.parts(Body("wolf", "Old Greymuzzle"), _kesst(), now=0)) \
        == ["wolf-pelt"]
    assert harvest.dangers(Body("advanced-giant-scorpion", "the thing")) == ["poison"]


def test_a_wolf_offers_fur_and_nothing_feathered_scaled_or_chitin():
    """Lanes U5-U7, 2026-10-08: the old skin excursion offered a wolf feathered, scaled and
    chitin hides, because its yield ignored the creature. The wolf's own block gives one
    hide, its pelt, and sinew."""
    rows = harvest.parts(Body("wolf"), _kesst(), now=0)
    assert _hides(rows) == ["wolf-pelt"]
    assert {r["material"] for r in rows if r["branch"] == "sinew"} == {"sinew-thread"}


def _kesst():
    return load_pc("fixtures/pc-kesst.json")


# --- the book's numbers --------------------------------------------------------------------

def test_the_dc_is_15_plus_cr_whatever_the_crafters_level():
    """Inventory §0.3: "Leatherworker 5 skinned a wolf at DC 22, level 1 at DC 10". The DC
    is 15 + the creature's CR; the owner's answer 4 puts the craft's level on the ROLL."""
    novice, master = _kesst(), _kesst()
    master.track("leatherworker").level = 5
    a = next(r for r in harvest.parts(Body("wolf"), novice, now=0) if r["branch"] == "hide")
    b = next(r for r in harvest.parts(Body("wolf"), master, now=0) if r["branch"] == "hide")
    assert a["dc"] == b["dc"] == 16
    assert b["bonus"] - a["bonus"] == 4
    assert any(t["label"] == "Leatherworker 5" for t in b["terms"])


def test_the_skinning_kit_adds_two(monkeypatch):
    """The owner's answer 4: "+ the skinning kit's +2" (PA §1.4, taxidermy tools)."""
    from rules import places

    pc = _kesst()
    monkeypatch.setattr(places, "has_field_kit", lambda actor, craft="blacksmith": False)
    bare = harvest.check_terms(pc, "leatherworker", "survival")
    monkeypatch.setattr(places, "has_field_kit", lambda actor, craft="blacksmith":
                        craft == "leatherworker")
    kit = harvest.check_terms(pc, "leatherworker", "survival")
    assert sum(t["value"] for t in kit) - sum(t["value"] for t in bare) == 2


def test_a_good_roll_does_not_multiply_the_haul():
    """Inventory §0.3: the old excursion's `1 + margin // 5` batch made a lucky skinning
    three hides off one wolf. One part is one part: a roll beating the DC by 20 takes the
    wolf's one Medium unit."""
    pc, wolf = _kesst(), Body("wolf")
    got = harvest.take(pc, wolf, "hide:wolf-pelt", 36, now=100)
    assert got["ok"] and sum(s["units"] for s in got["stock"]) == 1.0


def test_one_wolf_yields_its_pelt_once_then_taken():
    """Inventory §0.3: "six skinnings of one wolf ran, three succeeded". The part is taken
    whatever the roll said and never reappears."""
    pc, wolf = _kesst(), Body("wolf")
    harvest.take(pc, wolf, "hide:wolf-pelt", 3, now=100)
    row = next(r for r in harvest.parts(wolf, pc, now=110) if r["key"] == "hide:wolf-pelt")
    assert row["taken"] == 100
    with pytest.raises(ValueError):
        harvest.take(pc, wolf, "hide:wolf-pelt", 30, now=120)


def test_a_harvested_hide_starts_its_48_hour_clock():
    """Inventory §0.3: "`picked_at` was None for everything skinned" — the clock never
    started. The hide lands green, harvested at the minute, 48 hours on its clock."""
    pc, wolf = _kesst(), Body("wolf")
    got = harvest.take(pc, wolf, "hide:wolf-pelt", 30, now=500)
    h = lw.Hide.from_stock(pc.stock[got["stock"][0]["key"]])
    assert (h.form, h.harvested_at) == ("green", 500)
    assert harvest.freshness(lw.record_of_hide(h), 500)["hours_left"] == 48
    assert harvest.freshness(lw.record_of_hide(h), 500 + 48 * 60)["spoiled"]
    # The bench asks the harvest first, so the two can never disagree.
    assert lw.freshness(h, 500)["hours_left"] == 48


def test_a_near_miss_takes_the_part_a_grade_worse_and_a_wide_miss_ruins_it():
    """Plan §5.8 (the Craft rule's shape): a miss by 4 or less still takes the part, one
    grade worse than the game and never better than Grade 3; a miss by 5 or more ruins a
    one-unit hide, and a Large hide keeps half at Grade 4."""
    pc = _kesst()
    near = harvest.take(pc, Body("wolf"), "hide:wolf-pelt", 12, now=0, defects=0.0)
    assert near["grade"] == 3 and near["stock"]
    ruined = harvest.take(pc, Body("wolf"), "hide:wolf-pelt", 11, now=0)
    assert ruined["stock"] == [] and "ruined" in ruined["lost"]
    lion = harvest.take(pc, Body("lion"), "hide:generic-fur-hide", 3, now=0)
    assert [(s["units"], s["grade"]) for s in lion["stock"]] == [(1.0, 4)]


def test_the_game_sets_the_grade_from_the_defect_area():
    """Plan §5.7 (UNIDO): the grade is the only thing the player's hands decide. The page
    reports the area; the server grades it — clean 1, a few holes 2, a third 3, half 4,
    worse a reject (scraps). A landed hide is re-graded, never duplicated."""
    assert [harvest.grade_of(d) for d in (0.0, 0.05, 0.25, 0.45, 0.8)] == [1, 2, 3, 4, 0]
    pc, wolf = _kesst(), Body("wolf")
    got = harvest.take(pc, wolf, "hide:wolf-pelt", 30, now=0)
    assert got["grade"] == 3                     # the unplayed grade, until the game
    after = harvest.regrade(pc, got["game"], 0.0)
    assert after["grade"] == 1
    assert sum(int(s.count) for s in pc.stock.values()) == 1
    h = lw.Hide.from_stock(pc.stock[after["stock"][0]["key"]])
    assert h.grade == 1


# --- salt costs salt ------------------------------------------------------------------------

def test_salt_carried_at_the_harvest_is_spent_one_measure_a_unit():
    """Owner answer 8 (2026-10-08): "salt costs salt" — one measure of curing salt per hide
    unit, spent at the harvest. A Large lion is two units: three measures carried, two
    spent, the hide salted; with one measure, one unit salted and one green."""
    pc = _kesst()
    pc.inventory["curing-salt"] = 3
    got = harvest.take(pc, Body("lion"), "hide:generic-fur-hide", 30, now=0)
    assert got["salt_spent"] == 2 and pc.inventory["curing-salt"] == 1
    assert [s["form"] for s in got["stock"]] == ["salted"]
    got = harvest.take(pc, Body("lion"), "hide:generic-fur-hide", 30, now=0)
    assert got["salt_spent"] == 1 and "curing-salt" not in pc.inventory
    assert sorted((s["form"], s["units"]) for s in got["stock"]) == [("green", 1.0),
                                                                       ("salted", 1.0)]


def test_salt_is_read_by_id_and_costs_what_it_salts():
    """Lanes U5-U7 found `herbprep.has_salt` marked a hide salted for free whenever any
    salt was carried, and it matched name fragments ("rock salt", "saltpetre") — the shape
    law 1 refuses. The one reader reads curing salt by id, and an animal part costs a
    measure as it is picked (owner answer 8: "herbalism's animal parts cost salt too")."""
    pc = _kesst()
    pc.inventory["rock salt"] = 5
    assert not herbprep.has_salt(pc)
    pc.inventory.pop("rock salt")
    pc.inventory["curing-salt"] = 2
    pc.carry("basilisk-eye", 1, at_minute=10)
    assert pc.preserved.get("basilisk-eye") and pc.inventory["curing-salt"] == 1
    # A hide carried with a minute (the old excursion's door) costs a measure a unit.
    pc.carry("horse-hide", 1, at_minute=10)          # a Large hide: two measures
    assert not pc.preserved.get("horse-hide") and pc.inventory["curing-salt"] == 1
    # A plant keeps its free preservation: the answer named hides and animal parts.
    pc.carry("comfrey", 1, at_minute=10)
    assert pc.preserved.get("comfrey") and pc.inventory["curing-salt"] == 1


# --- generic hides from the stat block ------------------------------------------------------

def test_a_generic_hide_takes_its_tier_units_and_numbers_from_the_block():
    """Plan §5.4, §5.5: CR sets a generic hide's tier, size its units, and its highest
    energy resistance (÷ 5, at least 1; an immunity the tier's ceiling) and, rare and up,
    its highest DR as DR max(1, N ÷ 5) — owner answer 6 — come from the block on read.
    Choral (CR 25, Colossal, immune to fire, DR 20/magic) against a CR 4 block with DR 5."""
    block = {"id": "x", "creature_type": "magical beast", "size": "large", "cr_value": 4,
             "reductions": [{"amount": 5, "bypass": "silver"}], "resist": ["cold 10"]}
    assert harvest.tier_of_cr(4) == "uncommon"
    assert harvest.inherited(block) == [{"type": "resistance", "target": "cold", "amount": 2}]
    rare = dict(block, cr_value=7)
    assert {"type": "damage_reduction", "amount": 1, "bypass": "silver"} \
        in harvest.inherited(rare)
    assert harvest.inherited("choral-the-conqueror") == [
        {"type": "resistance", "target": "fire", "amount": 4},
        {"type": "damage_reduction", "amount": 4, "bypass": "magic"}]
    assert harvest.units_for(harvest.block_of("lion"), "hide", "x") == 2.0


def test_a_generic_hide_lands_with_its_beast_for_the_build_to_read():
    """Contracts §4.1: a generic hide's inherited numbers are derived from the stock's
    `creature` on read (lane B's build calls `harvest.inherited`), never stored."""
    pc = _kesst()
    got = harvest.take(pc, Body("lion"), "hide:generic-fur-hide", 30, now=0)
    h = lw.Hide.from_stock(pc.stock[got["stock"][0]["key"]])
    assert (h.creature, h.tier) == ("lion", "uncommon")


# --- dangerous bodies (deeds plan §13) -------------------------------------------------------

def test_the_extractor_reads_abbreviated_abilities():
    """Deeds plan §13.4: of 79 printed poison paragraphs 34 parsed; the 45 between wrote
    "effect 1d2 Con" with no "damage". They parse now, and a bonus is not read as harm."""
    specs = [e.spec for e in effects.extract(
        "Poison (Ex) Bite-injury; save Fort DC 20; frequency 1/round for 6 rounds; "
        "effect 1d2 Con; cure 1 save.")]
    assert {"type": "ability_damage", "target": "con", "dice": "1d2"} in specs
    assert not any(s.get("type") == "ability_damage"
                   for s in (e.spec for e in effects.extract("+2 Con while raging")))


def test_an_unprinted_poison_is_never_invented():
    """Deeds plan §13.4: every core.json block lacks its special abilities, so a core giant
    scorpion prints a "plus poison" rider and no poison. It is a poisonous body (the tag)
    and runs no poison round: a poison nobody printed is not invented."""
    block = harvest.block_of("scorpion-giant")
    assert "poison" in harvest.dangers(block)
    assert [r["kind"] for r in harvest.danger_rounds(Body("scorpion-giant"))] == []
    assert [r["kind"] for r in harvest.danger_rounds(Body("advanced-giant-scorpion"))] \
        == ["poison"]


def test_an_aura_is_not_a_danger_to_the_skinner():
    """Deeds plan §13.2: an aura is the living creature's; immunity alone is a fine hide,
    not a hot one."""
    block = {"creature_type": "magical beast", "special_attacks": "fire aura (5 ft., 1d6)",
             "immune": ["fire"]}
    assert harvest.derive_dangers(block) == []


def test_a_fire_bodied_hide_burns_for_its_own_burn_dice():
    """Deeds plan §13.4: the amount is the book's small one — the creature's own burn or
    heat dice where it prints them, else 1d6, never its breath's."""
    assert harvest.contact_dice("noble-salamander", "fire") == "1d8"
    assert harvest.contact_dice("choral-the-conqueror", "fire") == "1d6"


def test_a_giant_scorpion_forces_its_poison_round_once_per_carcass(client):
    """Deeds plan §13.5: taking three parts makes one round. Per-part exposure would make
    a dragon six hazards."""
    a = _corpse("advanced-giant-scorpion")
    code, got = _post(client, "/api/harvest/take",
                      {"creature": a.ref, "key": "hide:generic-chitin", "face": 20,
                       "danger_faces": {"poison": 20}})
    assert code == 200, got
    assert [d["kind"] for d in got["dangers"]] == ["poison"]
    code, got = _post(client, "/api/harvest/take",
                      {"creature": a.ref, "key": "sinew:sinew-thread", "face": 20})
    assert code == 200 and got["dangers"] == []


def test_a_failed_poison_round_goes_through_the_poison_door(client):
    """Deeds plan §13.5 and the owner's answer 6: exposed only on a miss by 5 or more; then
    a Fortitude save at the printed DC, +2 a dose past the first, the effect landing only
    on a failed save, stamped `creature:<template>`."""
    c = _c()
    a = _corpse("advanced-giant-scorpion")
    pc = c.scene.pc()
    engine = c.engine()
    safe = harvest.face_danger(engine, pc, a, "poison", 15, now=0, dice=engine.dice)
    assert not safe["exposed"] and safe["margin"] == -4
    b = _corpse("advanced-giant-scorpion")
    hit = harvest.face_danger(engine, pc, b, "poison", 14, now=0, dice=engine.dice)
    assert hit["exposed"] and 1 <= hit["doses"] <= 3
    assert hit["dc"] == 19 and hit["save_dc"] == 19 + 2 * (hit["doses"] - 1)
    saves = [o for o in hit["outcomes"] if o.op == "save"]
    assert len(saves) == 1
    landed = [e for o in hit["outcomes"] if o.op != "save" for e in (o.effects or [])]
    if saves[0].verdict == "success":
        assert landed == []
    else:
        assert landed and all(e.get("origin") == "creature:advanced-giant-scorpion"
                              for e in landed if "origin" in e)


def test_an_acid_body_burns_through_the_hazard_door_with_its_own_dice(client):
    """Deeds plan §13.4: acid and energy damage go through the `hazard` op's contact rows,
    stamped `rule:contact-<energy>`, resistance applying in `take_damage`; a fire body
    rolls its own printed heat dice (the noble salamander's 1d8)."""
    c = _c()
    pc = c.scene.pc()
    engine = c.engine()
    sal = _corpse("noble-salamander")
    got = harvest.face_danger(engine, pc, sal, "fire", -10, now=0, dice=engine.dice)
    assert got["exposed"]
    hz = [o for o in got["outcomes"] if o.op == "hazard"]
    assert hz and any(r.die == "1d8" for r in hz[0].rolls)
    assert any(e.get("origin") == "rule:contact-fire" for e in hz[0].effects)


# --- deeds (deeds plan §10, §12) -------------------------------------------------------------

def test_harvesting_an_archon_writes_one_deed_per_carcass(monkeypatch):
    """Deeds plan §12: three parts off one archon are one deed, recorded on the first
    part whatever the roll — the subject is the carcass."""
    calls = []

    class Recorder(harvest._DeedsStub):
        @staticmethod
        def record(actor, tag, **kw):
            calls.append((tag, kw.get("subject"), kw.get("how")))
            return {"tag": tag}

    monkeypatch.setattr(harvest, "_deeds", lambda: Recorder)
    pc, archon = _kesst(), Body("lantern-archon")
    rows = harvest.parts(archon, pc, now=0)
    assert len(rows) == 3 and all(r["deed"] == "deed.harvest.good-outsider" for r in rows)
    for r in rows:
        harvest.take(pc, archon, r["key"], 30, now=0)
    assert calls == [("deed.harvest.good-outsider", "c99", "meant")]


def test_the_deeds_module_is_asked_by_its_own_names(monkeypatch):
    """Deeds plan §10 and the lead's note of 2026-10-08: the merged rules/deeds.py is asked
    `never_harvested` FIRST (nothing is offered when it says so), `of_carcass` for the tag,
    and `record(actor, tag, scene=, subject=, subject_name=, what="", how="meant")` once a
    carcass. A stand-in module with exactly those names is what the harvest calls."""
    import sys
    import types

    seen = []
    fake = types.ModuleType("rules.deeds")
    fake.never_harvested = lambda c: (c or {}).get("id") == "wolf"
    fake.of_carcass = lambda c: "deed.harvest.good-outsider"
    fake.record = lambda actor, tag, **kw: seen.append((tag, sorted(kw))) or {"kind": "deed"}
    monkeypatch.setitem(sys.modules, "rules.deeds", fake)
    import rules

    monkeypatch.setattr(rules, "deeds", fake, raising=False)
    assert harvest.banned(harvest.block_of("wolf"))
    assert harvest.parts(Body("wolf"), _kesst(), now=0) == []
    pc, lion = _kesst(), Body("lion")
    for r in harvest.parts(lion, pc, now=0):
        harvest.take(pc, lion, r["key"], 30, now=0, scene=None)
    assert seen == [("deed.harvest.good-outsider",
                     ["how", "scene", "subject", "subject_name", "what"])]


def test_a_pseudodragon_is_a_good_dragon_by_its_printed_alignment():
    """Deeds plan §12 and open point 12: a good dragon's harvest is a deed, read from the
    printed alignment (the pseudodragon prints NG), never the name."""
    assert harvest.deed_of(Body("pseudodragon", "Sparkle")) == "deed.harvest.good-dragon"
    assert harvest.deed_of(Body("choral-the-conqueror")) is None
    assert harvest.deed_of(Body("wolf")) is None


def test_the_carcass_deed_never_reads_the_name():
    """Deeds plan §12: a renamed archon still writes the deed."""
    assert harvest.deed_of(Body("lantern-archon", "Bob")) == "deed.harvest.good-outsider"


# --- the carcass's record and its window ------------------------------------------------------

def test_a_carcass_records_its_death_and_keeps_24_hours(client):
    """Plan §5.9 and the owner's answer 5: a carcass is harvestable for 24 hours after
    death, recorded as `died_at` when it drops — or a party could skin a week-old corpse."""
    c = _c()
    wolf = _corpse("wolf")
    assert wolf.died_at == c.scene.clock_minutes
    assert harvest.harvestable(wolf, now=wolf.died_at + 24 * 60)[0]
    ok, why = harvest.harvestable(wolf, now=wolf.died_at + 24 * 60 + 1)
    assert not ok and "24 hours" in why


def test_the_engine_stamps_the_minute_a_creature_dies(client):
    """`Engine._drive` stamps `died_at` after each outcome, before the next can move the
    clock (plan §5.9): a wolf killed by a damage op knows when it died."""
    c = _c()
    wolf = c.scene.add(bestiary.instantiate("wolf", scene=c.scene))
    engine = c.engine()
    engine.run(engine.validate([{"op": "damage", "actor": c.scene.pc().ref,
                                 "visibility": "hidden",
                                 "params": {"to": wolf.ref, "amount": 50,
                                            "type": "slashing"}}],
                               origin="author:test"))
    assert wolf.is_dead and wolf.died_at == c.scene.clock_minutes


def test_a_carcass_with_parts_left_is_not_swept_away(client):
    """Measured live 2026-10-08: a wolf dropped in a fight lay dying, bled out in
    `tidy_the_fallen` two turns later and departed in the same call, so no kill from a fight
    was ever a carcass anybody could skin. A beast's carcass stays while it has parts and is
    within its 24 hours; once taken it goes, and a dead person goes as before."""
    c = _c()
    wolf = _corpse("wolf")
    goblin = _corpse("goblin")
    engine = c.engine()
    for _ in range(4):
        engine.tidy_the_fallen()
    assert wolf.ref in c.scene.actors and goblin.ref not in c.scene.actors
    pc = c.scene.pc()
    for p in harvest.parts(wolf, pc, now=c.scene.clock_minutes):
        harvest.take(pc, wolf, p["key"], 30, now=c.scene.clock_minutes)
    for _ in range(4):
        engine.tidy_the_fallen()
    assert wolf.ref not in c.scene.actors


def test_an_old_save_writes_no_carcass_fields():
    """An actor with no carcass record serialises exactly as before
    (`test_the_owners_real_saves_round_trip_byte_identically`), and one with a record
    round-trips it."""
    pc = _kesst()
    d = actor_to_dict(pc)
    assert "died_at" not in d and "harvested" not in d
    pc.died_at, pc.harvested = 40, {"hide:wolf-pelt": 41}
    back = from_dict(actor_to_dict(pc), ref=pc.ref)
    assert (back.died_at, back.harvested) == (40, {"hide:wolf-pelt": 41})


def test_the_four_carcass_excursions_left_the_hub():
    """Plan §5.1: four repeatable excursions over one body (skin, salvage, harvest-reagents,
    reliquary-harvest) were the "six skinnings of one wolf" door. They are gone; the
    non-carcass siblings stay."""
    from rules import benches

    keys = {a["key"] for a in benches.acquisitions()}
    assert not keys & {"leatherworker:skin", "blacksmith:salvage",
                       "alchemist:harvest-reagents", "enchanter:reliquary-harvest"}
    assert {"leatherworker:gather", "blacksmith:prospect"} <= keys


# --- the API end to end ----------------------------------------------------------------------

def test_the_routes_sit_above_the_ref_route():
    """The herb bench's route-order bug (a parameter route swallowing "state"): "take" and
    "finish" must not be read as a carcass's ref."""
    assert resolve("/api/harvest/take").func is harvest_views.harvest_take
    assert resolve("/api/harvest/finish").func is harvest_views.harvest_finish
    assert resolve("/api/harvest/c7").func is harvest_views.harvest_sheet


def test_kill_a_wolf_and_take_its_pelt_through_the_sheet(client):
    """The whole path the page drives: the sheet lists the pelt with its DC and the face
    needed; Take rolls, lands a green hide with its clock and spends the salt; the game's
    defect area grades it; a second Take is refused "already taken"."""
    c = _c()
    c.scene.pc().inventory["curing-salt"] = 1
    c.save()
    wolf = _corpse("wolf")
    code, here = _get(client, "/api/harvest")
    assert code == 200 and [x["ref"] for x in here["carcasses"]] == [wolf.ref]
    code, sheet = _get(client, f"/api/harvest/{wolf.ref}")
    assert code == 200 and sheet["harvestable"]
    pelt = next(p for p in sheet["parts"] if p["key"] == "hide:wolf-pelt")
    assert pelt["dc"] == 16 and pelt["game"] == "harvest" and pelt["need"] is not None
    code, got = _post(client, "/api/harvest/take",
                      {"creature": wolf.ref, "key": "hide:wolf-pelt", "face": 18})
    assert code == 200, got
    assert got["roll"]["success"] and got["token"] and got["salt_spent"] == 1
    assert got["stock"][0]["form"] == "salted"
    code, done = _post(client, "/api/harvest/finish", {"token": got["token"], "defects": 0.05})
    assert code == 200 and done["grade"] == 2
    code, again = _post(client, "/api/harvest/take",
                        {"creature": wolf.ref, "key": "hide:wolf-pelt", "face": 20})
    assert code == 409 and "already been taken" in again["error"]


def test_a_humanoid_corpse_is_never_offered(client):
    """UI plan §6.9: humanoids never appear, so the page has nothing to refuse."""
    c = _c()
    body = c.scene.add(bestiary.instantiate("goblin", scene=c.scene))
    body.die("test")
    c.save()
    code, here = _get(client, "/api/harvest")
    assert code == 200 and body.ref not in [x["ref"] for x in here["carcasses"]]
    code, got = _post(client, "/api/harvest/take",
                      {"creature": body.ref, "key": "hide:generic-smooth-hide"})
    assert code == 409
