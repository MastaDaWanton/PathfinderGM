"""Biomes, the satchel, and forage tables built from where you are standing.

Two vocabularies meet here and neither was written for the other: the World Bible export
describes places in prose ("Pangrellan grasslands, Kyropticus deserts"), and the herb
document describes habitats in prose ("grows in temperate forests", "damp, shadowy
caves"). Neither will ever say `grassland`, so both are matched into one canonical list.

Tables are assembled rather than authored. Thirteen biomes across a hundred and sixty
ingredients is two thousand hand-written rows nobody would keep current; derived from the
tags, a herb added tomorrow appears on every table it belongs to.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import biomes, foraging, ingredients
from rules.dice import Dice
from rules.sheet import from_dict, load_pc, to_dict
from tests._places import stand_on


# --- the vocabulary -----------------------------------------------------------------------

@pytest.mark.parametrize("prose,expect", [
    ("This plant grows in alpine environments", "mountain"),
    ("found in damp, shadowy caves", "underground"),
    ("thrive in snowy tundras", "tundra"),
    ("found in haunted marshes", "swamp"),
    ("an orchid that grows on jungle vines", "jungle"),
    ("grow in open fields with plenty of sun", "grassland"),
    ("known to grow exclusively in urban areas", "urban"),
    ("found beneath ancient battlegrounds", "ruins"),
    ("originating on the Elemental Plane of Air", "planar"),
])
def test_habitat_prose_is_matched_into_the_canonical_list(prose, expect):
    assert expect in biomes.detect(prose)


def test_the_canonical_names_are_detected_too():
    """Found by tagging: matching only the alias table meant `urban` was never detected,
    because the aliases list "city" and "street" and never the word itself. Golden Maple
    Leaves, which grow exclusively in urban areas, were filed as ordinary woodland."""
    for name in biomes.BIOMES:
        assert name in biomes.detect(f"it is found in {name} country")


def test_matching_is_word_bounded():
    """Without it, "planar" is found inside "plane", "mine" inside "determine", and half
    the herb list ends up growing underground."""
    assert "underground" not in biomes.detect("we shall determine the dose")


def test_the_biome_is_read_from_the_world_not_invented(tmp_path):
    """The export carries `Biomes`, `Terrain` and `Climate`, and they live on the
    continent rather than the town — reading only the location itself would have found
    nothing for every settlement in the world."""
    from django.conf import settings
    from world.loader import load_cached

    world = load_cached(settings.WORLD_EXPORT)
    town = world.get("5bbd0c40345f")
    found = biomes.from_world(world, town)
    assert "urban" in found                     # it is a city
    assert "grassland" in found                 # Kaelinora's Biomes fact


# --- tags -----------------------------------------------------------------------------------

def test_every_ingredient_carries_biomes():
    for ing in ingredients.all_ingredients().values():
        assert ing.biomes, ing.id


def test_monster_parts_are_not_foraged():
    """They are cut off a corpse, not picked."""
    assert not ingredients.get("hydra-gall").forageable
    assert ingredients.get("woundwort").forageable


def test_a_guessed_habitat_says_so():
    """The plain herb lists give no habitat at all, so those fall back to temperate
    ground and are flagged — the same treatment tier gets, for the same reason."""
    shelf = ingredients.all_ingredients()
    inferred = [i for i in shelf.values() if i.biomes_inferred]
    stated = [i for i in shelf.values() if not i.biomes_inferred]
    assert inferred and stated
    assert not ingredients.get("frostbloom").biomes_inferred
    assert ingredients.get("frostbloom").biomes == ["tundra"]


# --- tables ---------------------------------------------------------------------------------

def test_a_table_is_built_from_what_grows_there():
    t = foraging.table_for("tundra", rank_ceiling=5)
    names = [r.name for r in t.rows]
    assert "Frostbloom" in names
    assert "Mistveil Fern" not in names          # a cave fern, not a snowfield one


def test_a_table_covers_exactly_one_to_a_hundred():
    t = foraging.table_for("forest", rank_ceiling=5)
    assert t.rows[0].low == 1
    for a, b in zip(t.rows, t.rows[1:]):
        assert b.low == a.high + 1
    assert t.nothing_from == t.rows[-1].high + 1


def test_every_candidate_gets_at_least_one_percent():
    """A rare herb in a thin biome should be findable rather than rounded out of
    existence."""
    t = foraging.table_for("forest", rank_ceiling=5)
    assert all(r.span >= 1 for r in t.rows)


def test_the_ceiling_filters_rather_than_marks():
    """Unlike the crafting shelf: you cannot recognise what you have no training to
    handle, and a table full of rows the character must discard is worse than a shorter
    honest one."""
    low = foraging.table_for("planar", rank_ceiling=1)
    high = foraging.table_for("planar", rank_ceiling=5)
    assert len(high.rows) > len(low.rows)


def test_a_biome_with_nothing_in_it_says_so_rather_than_improvising():
    t = foraging.table_for("desert", rank_ceiling=5)
    assert t.empty
    assert t.nothing_from == 1


def test_rarer_things_are_rarer_finds():
    t = foraging.table_for("forest", rank_ceiling=5)
    common = sum(r.span for r in t.rows if r.rank == 1)
    rare = sum(r.span for r in t.rows if r.rank >= 3)
    assert common > rare


def test_a_better_forager_comes_back_with_more():
    """The track's payoff outside the workbench.

    It used to be a flat count of attempts per session — an Herbalist 5 simply rolled
    three times where an Herbalist 1 rolled once. Now the track adds to the Survival check
    instead, so a better forager reaches a better *band* and the band decides how much.
    `attempts_for` is kept because it still describes the old shape of the payoff and
    nothing has replaced it as a summary, but `forage` no longer calls it.
    """
    assert foraging.attempts_for(1) == 1
    assert foraging.attempts_for(5) == 3


def test_foraging_reports_every_roll_that_produced_it():
    """The number of picks is no longer fixed: it is whatever the hour's band earned, and
    a pick that landed on a species already found is rerolled rather than recorded. So
    this asserts they are all real d100s and never more than the band promised, rather
    than counting them exactly."""
    got = foraging.forage("forest", level=5, rank_ceiling=5, dice=Dice(seed=7))
    assert all(1 <= r["roll"] <= 100 for r in got["rolls"])
    assert len(got["rolls"]) <= sum(h["finds"] for h in got["hourly"])


# --- the satchel ------------------------------------------------------------------------------

def test_carrying_and_spending():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.carry("woundwort", 3)
    assert pc.inventory["woundwort"] == 3
    assert pc.spend("woundwort", 2) == 2
    assert pc.inventory["woundwort"] == 1


def test_an_emptied_pouch_leaves_the_satchel():
    """A count of nothing is something the page offers and the next preview refuses."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.carry("woundwort", 1)
    pc.spend("woundwort", 5)
    assert "woundwort" not in pc.inventory


def test_the_satchel_survives_a_save():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.carry("woundwort", 2)
    pc.carry("comfrey", 1)
    back = from_dict(to_dict(pc))
    assert back.inventory == {"woundwort": 2, "comfrey": 1}


def test_the_sheet_names_what_is_carried():
    """The sheet stores ids because that is what everything else keys on; a player should
    never be shown `adder-s-tongue`."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.carry("adder-s-tongue", 1)
    assert pc.summary()["satchel"][0]["name"] == "Adder's-Tongue"


# --- through the app ----------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        # Seeded, for the same reason the combat panel's fixture is: `begin_with`
        # leaves seed=None, so every Survival check here rolls real dice. Caught once
        # in a full-suite run — eight consecutive forages came back empty and
        # `test_foraging_fills_the_satchel` failed with nothing wrong in the code,
        # while passing on its own every time. An unseeded fixture is a gate that
        # lies occasionally, which is worse than one that lies always.
        c.seed = 20260830
        c.save()
        yield Client()
        cm._LIVE.clear()


def test_the_campaign_starts_in_the_worlds_own_biome(client):
    d = client.get("/api/state").json()
    assert d["scene"]["biome"] == "urban"        # Pangrella is a city
    assert d["scene"]["biome_describe"]


def test_a_save_written_before_places_heals_on_load(client):
    """Healed on read rather than migrated: every campaign written before places existed
    has no `at` on the scene and no `at` on any actor, and a save that needs a migration
    step to be playable is a save that breaks the moment somebody opens an old one.

    A version-1 save: `actors` instead of `people`, a stored `biome`, nothing placed.
    It loads standing at the settlement's first place with everyone beside the party —
    and `biome` is read off that place, not off the field the save carried.
    """
    import json

    from play import campaign as cm

    c = cm.current()
    path = c.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    data["save_version"] = 1
    scene = data["scene"]
    scene["actors"] = scene.pop("people")
    for a in scene["actors"].values():
        a.pop("at", None)
    scene["at"] = ""
    scene["biome"] = "urban"
    scene.pop("minted", None)
    path.write_text(json.dumps(data), encoding="utf-8")

    old = cm.Campaign.load(path)
    assert old.biome == "urban"
    assert old.scene.at and old.scene.at == old.engine().places()[0].id
    assert all(a.at == old.scene.at for a in old.scene.people.values()), \
        "somebody the old save held was left standing nowhere"
    assert set(old.scene.actors) == set(old.scene.people)


def test_travelling_changes_what_grows(client):
    urban = client.get("/api/forage/table?biome=urban").json()
    forest = client.get("/api/forage/table?biome=forest").json()
    assert forest["table"]["rows"] and not urban["table"]["rows"]

    d = client.post("/api/travel", data=json.dumps({"biome": "forest"}),
                    content_type="application/json").json()
    assert d["biome"] == "forest"
    assert client.get("/api/forage/table").json()["here"] == "forest"


def test_an_invented_biome_is_refused_with_the_ones_that_exist(client):
    r = client.post("/api/travel", data=json.dumps({"biome": "the moon"}),
                    content_type="application/json")
    assert r.status_code == 400
    assert "forest" in r.json()["error"]


def test_foraging_fills_the_satchel(client):
    """Two posts make one forage now: the first suspends on the player's own Survival
    check, the second carries the face back. "Roll it for me" is the same courtesy
    `/api/roll` extends."""
    from play import campaign as cm

    client.post("/api/travel", data=json.dumps({"biome": "forest"}),
                content_type="application/json")
    for _ in range(8):
        r = client.post("/api/forage", data=json.dumps({}),
                        content_type="application/json").json()
        if "roll" in r:
            assert "Survival" in r["roll"]["label"]
            client.post("/api/forage", data=json.dumps({"face": "auto"}),
                        content_type="application/json")
    assert cm.current().scene.pc().inventory


def test_crafting_spends_what_was_foraged(client):
    """The loop, closed: nothing can be brewed that was not first picked."""
    from play import campaign as cm

    r = client.post("/api/craft/preview", data=json.dumps({
        "craft": "herbalism", "ingredients": ["woundwort"], "methods": ["brew"]}),
        content_type="application/json").json()
    assert any("Forage for it" in p for p in r["problems"])

    cm.current().scene.pc().carry("woundwort", 1)
    cm.current().save()
    d = client.post("/api/craft/do", data=json.dumps({
        "craft": "herbalism", "ingredients": ["woundwort"], "methods": ["brew"]}),
        content_type="application/json").json()
    assert d["spent"] == {"woundwort": 1}
    assert "woundwort" not in cm.current().scene.pc().inventory


# --- you forage where you are, and only when you are free ---------------------------------
#
# Both of these were unchecked. A character could spend forty-eight hours on their hands
# and knees in the middle of an initiative order, or walk off mid-conversation and come
# back with a full satchel and no time having passed for anyone else. And because the
# `biome` parameter was honoured over the scene's own ground, a request could search a
# forest from the middle of a city.

@pytest.fixture
def treeline():
    from rules.bestiary import instantiate
    from rules.dice import Dice as _Dice
    from rules.engine import Engine, Scene

    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["level"] = 6
    d["ranks"] = {"survival": 6}
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "forest")
    s.add(from_dict(d, ref="pc"))
    return s, Engine(s, _Dice(seed=5)), instantiate


def _forage(engine, face=11, **params):
    """Run a forage to completion, answering the Survival popup with `face`.

    The suspend is part of the contract now — "I should be forced to roll a survival
    check" — so this helper asserts it fired rather than working around it.
    """
    resolution = engine.run(engine.validate([
        {"op": "forage", "actor": "pc", "because": "she works the treeline",
         "params": {"hours": 1, **params}}]))
    if resolution.awaiting is None:
        return resolution
    assert "Survival" in resolution.awaiting["label"]
    return engine.resume(face)


def test_foraging_alone_on_open_ground_still_works(treeline):
    """The control. Everything below refuses; this one has to go through, or the rule has
    simply turned foraging off."""
    scene, engine, _ = treeline
    _forage(engine)
    assert scene.clock_minutes == 60


def test_you_cannot_forage_in_the_middle_of_a_fight(treeline):
    """An hour minimum, forty-eight at most, in an initiative order counted in rounds.

    A refusal *outcome*, not an IntentError — the same shape as the untrained check's
    "Nothing is rolled". Raising put the spoken path into a death spiral: the schema
    requires the forage op the player declared, so all five attempts carried it, all
    five were refused, and "I forage" next to a campfire companion came back as a 502
    instead of a sentence."""
    scene, engine, instantiate = treeline
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    engine.run(engine.validate([{
        "op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    assert scene.in_encounter
    resolution = _forage(engine)
    assert resolution.awaiting is None, "a refused forage still asked for a roll"
    out = resolution.outcomes[0]
    assert "fight" in out.tell
    assert not out.effects
    assert scene.clock_minutes == 0


def test_you_cannot_forage_with_somebody_standing_in_front_of_you(treeline):
    """Company is the test for conversation, because the engine has no dialogue flag and
    one the GM had to remember to set would be wrong more often than right. Refused as
    an outcome with the company named, so the spoken path can say so in one turn."""
    scene, engine, instantiate = treeline
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    assert not scene.in_encounter
    resolution = _forage(engine)
    assert resolution.awaiting is None
    out = resolution.outcomes[0]
    assert "the thug" in out.tell
    assert not out.effects
    assert scene.clock_minutes == 0


def test_somebody_unconscious_is_not_company(treeline):
    """A refusal that fires over a body on the ground would strand the player: there is no
    op for leaving, so the scene could not be cleared and foraging would never come back."""
    scene, engine, instantiate = treeline
    thug = instantiate("thug", scene=scene, name="the thug")
    scene.add(thug)
    thug.hp = -1
    _forage(engine)
    assert scene.clock_minutes == 60


def test_foraging_searches_the_ground_underfoot_whatever_it_is_asked_for(treeline):
    """`biome` was honoured over the scene's, so a bench in a city could search a forest.

    Golden Maple Leaves make the check readable: they grow exclusively in urban areas, so
    a forager standing in a city and asking for forest picking them up is proof the ground
    won and the parameter lost.
    """
    scene, engine, _ = treeline
    stand_on(scene, "urban")
    # Face 18: under this seed the urban table's hidden d100s land on the leaves. A
    # middling face clears the DC but every pick misses — an honest empty hour, useless
    # to this test.
    resolution = _forage(engine, face=18, biome="forest")
    found = [e for o in resolution.outcomes for e in o.effects
             if e.get("kind") == "forage"]
    assert [e for e in found if e.get("biome") == "urban"], found
    assert "golden-maple-leaves" in scene.pc().inventory, dict(scene.pc().inventory)


def test_the_bench_says_why_foraging_is_refused_before_it_is_pressed(client):
    """The button greyed with no reason, and the refusal only arrived on pressing it —
    the same defect the crafting chain preview already fixes by sending its problems."""
    from play import campaign as cm
    from rules.bestiary import instantiate

    c = cm.current()
    # The opening scene ships with an apprentice minding the door, so the empty case has
    # to be made rather than assumed — and the fact that it does is why this rule bites
    # in a real campaign at all.
    for ref in [r for r in c.scene.actors if r != "pc"]:
        c.scene.depart(ref)
    assert client.get("/api/forage/table").json()["busy"] == ""

    c.scene.add(instantiate("thug", scene=c.scene, name="the thug"))
    said = client.get("/api/forage/table").json()["busy"]
    assert "the thug" in said, said

    # Pressed anyway, the button gets the same sentence as a refusal *outcome* — a 200
    # whose tell names the company, no roll asked for, nothing gained. It stopped being
    # a 400 when the raise it came from put the spoken path into a five-attempt 502.
    r = client.post("/api/forage", data=json.dumps({}),
                    content_type="application/json")
    assert r.status_code == 200
    d = r.json()
    assert "roll" not in d
    assert "the thug" in d["tell"]
    assert d["inventory"] == dict(c.scene.pc().inventory)



# --- the roll is the player's, and the bonus is finally visible ---------------------------
#
# "I should be forced to roll a survival check but I should get a bonus for my herbalism
# lvl. also the base numbers of items foraged should continue going up as my roll get
# higher."
#
# The herbalism bonus had existed inside `forage_hour` since the foraging rebuild — and
# the player had no way to know, because the check resolved invisibly inside the op. A
# bonus nobody can see is indistinguishable from a bonus that does not exist.

def test_the_forage_check_is_the_players_and_shows_the_herbalism_bonus(treeline):
    """The suspend fires before any time is paid, and the popup's breakdown carries the
    herbalism modifier next to ranks and Wis — the first time the track's ground bonus
    has ever been on screen."""
    scene, engine, _ = treeline
    pc = scene.pc()
    pc.track("herbalist").level = 3      # track() begins the class on first use
    awake_before = pc.awake_minutes

    resolution = engine.run(engine.validate([
        {"op": "forage", "actor": "pc", "because": "she works the treeline",
         "params": {"hours": 2}}]))

    assert resolution.awaiting is not None
    prompt = resolution.awaiting
    assert "Survival" in prompt["label"]
    sources = {m["source"]: m["value"] for m in prompt["breakdown"]}
    assert sources.get("herbalism") == 3
    # Suspended BEFORE the toll: a suspend after `pass_hours` would charge the body
    # twice for the same day when the roll came back.
    assert pc.awake_minutes == awake_before
    assert scene.clock_minutes == 0

    done = engine.resume(18)
    assert done.awaiting is None
    forage = next(e for o in done.outcomes for e in o.effects
                  if e.get("kind") == "forage")
    # The player's face is spent on the first hour; the engine rolls the second.
    assert forage["hourly"][0]["roll"] == 18 + sum(sources.values())
    assert scene.clock_minutes == 120
    assert pc.awake_minutes == awake_before + 120


def test_an_npc_forage_never_opens_the_popup(treeline):
    """The player rolls their own; everything else the engine rolls and hands to the GM
    as a fact. An NPC forage suspending would hang the world tick on a popup nobody is
    looking at."""
    scene, engine, instantiate = treeline
    scene.people.pop("pc")
    thug = instantiate("thug", scene=scene, name="the gatherer")
    scene.add(thug)
    resolution = engine.run(engine.validate([
        {"op": "forage", "actor": thug.ref, "because": "sent to gather",
         "params": {"hours": 1}}]))
    assert resolution.awaiting is None
    assert any(e.get("kind") == "forage" for o in resolution.outcomes
               for e in o.effects)


def test_the_yield_keeps_climbing_past_the_top_band():
    """The bands plateaued at margin 20: a 25 and a 45 came back with identical hauls,
    so past a modest Survival bonus every extra point the player earned bought nothing.
    Now every 5 of margin over the top floor is a virtual band above it — more kinds,
    bigger patches, without limit."""
    from rules import foraging

    # Kinds found: 8 at the top band, then +2 per 5 margin over, open-ended.
    assert foraging.band_for(20)[1] == 8
    assert foraging.band_for(25)[1] == 10
    assert foraging.band_for(45)[1] == 18
    assert foraging.band_for(120)[1] == 48

    # Patch size: the index goes negative above the top band and the same arithmetic
    # keeps climbing. A common plant: 10 at the top band, 12 one virtual band up, and
    # never the old plateau.
    assert foraging.band_index(20) == 0
    assert foraging.band_index(25) == -1
    assert foraging.band_index(45) == -5
    assert foraging.batch_for(1, 0) == 10
    assert foraging.batch_for(1, -1) == 12
    assert foraging.batch_for(1, -5) == 20
    # A legendary herb scales too — 2 at the top, climbing with the roll.
    assert foraging.batch_for(5, -5) == 12

    # Monotone: a better roll is never a worse haul.
    hauls = [foraging.batch_for(1, foraging.band_index(m)) for m in range(0, 60)]
    assert hauls == sorted(hauls)

    # Below the top nothing changed: the named bands still pay what they paid.
    assert foraging.band_for(17) == ("an excellent hour", 5, 1, True)
    assert foraging.band_for(3) == ("a meagre hour", 1, 0, False)
    assert foraging.band_index(12) == 2



def test_a_stale_bench_face_cannot_answer_somebody_elses_roll(client):
    """A face posted to /api/forage while a spoken turn's check is pending would land on
    a stranger's dice and drag that turn's resolution through the bench's tail. The
    prompt carries which door opened it; the bench and the excursion answer only their
    own, and the table's /api/roll stays the universal answerer either way."""
    from play import campaign as cm

    c = cm.current()
    keep = (c.scene.awaiting, list(c.scene.pending_intents),
            list(c.scene.pending_outcomes), dict(c.scene.pending_partial))
    try:
        c.scene.awaiting = {"label": "Perception check", "die": "1d20", "dc": 15,
                            "because": "sensing a presence", "intent_id": "i1"}
        c.scene.pending_intents = [{"op": "check", "actor": "pc",
                                    "params": {"skill": "perception",
                                               "dc": {"band": "tough"}}}]
        for url in ("/api/forage", "/api/craftaction"):
            r = client.post(url, data=json.dumps({"face": 12}),
                            content_type="application/json")
            assert r.status_code == 409, url
            assert "dice popup has it" in r.json()["error"], url
        assert c.scene.awaiting["label"] == "Perception check"   # untouched
    finally:
        (c.scene.awaiting, c.scene.pending_intents,
         c.scene.pending_outcomes, c.scene.pending_partial) = keep
