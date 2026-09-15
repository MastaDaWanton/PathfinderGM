"""Races as documents, and a world's own peoples as playable races.

"instead of picking the fantasy races that ship with pathfinder we should be able to
play as the races that ship with the world" — "make sure whatever we decide on all
follows our GAS like framework". 2026-09-06.

Measured before this: the seven races were dicts in `rules/creation.py`; the sheet's
rank check asked `actor.race.lower() == "human"` and the forge asked
`f.race === "human"` twice (a string match, the thing law one forbids); an elf's
"+2 Perception" was a line of prose nothing applied; the fixture world's Korvu — wings,
talons, echolocation in their own entry — could not be played at all.
"""
from __future__ import annotations

import json

import pytest

from rules import houserules, races
from rules.creation import build, options
from rules.dice import Dice
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


# --- the document ---------------------------------------------------------------------

def test_the_core_seven_ship_as_documents_priced_in_the_standard_tier():
    """The Race Builder caps a standard race at 10 RP, and every Core race prices
    inside it off its own parts — a human's bonus feat and extra rank alone are 8."""
    docs = {k: d for k, d in races.shipped().items() if not d.get("world")}
    assert set(docs) == {"human", "dwarf", "elf", "gnome", "half-elf", "half-orc",
                         "halfling"}
    for rid, d in docs.items():
        assert races.rp(d) <= races.STANDARD_RP, (rid, races.rp(d))
        assert races.validate(d) == [], (rid, races.validate(d))
    assert races.rp(docs["human"]) == 8
    assert docs["human"]["choose"] == [{"amount": 2, "from": "any"}]
    assert docs["human"]["budget"] == {"feats": 1, "ranks": 1}


def test_the_old_tables_spelling_is_still_read():
    """`any: 2` and `bonus_feat: true` were the seven-row table's words; a homebrew
    file written in them still says the same thing."""
    d = races.normalise({"id": "x", "name": "X", "any": 2, "bonus_feat": True,
                         "bonus_ranks": True, "mods": "con +2, cha -2"})
    assert d["choose"] == [{"amount": 2, "from": "any"}]
    assert d["budget"] == {"feats": 1, "ranks": 1}
    assert d["mods"] == {"con": 2, "cha": -2}
    assert "race.x" in d["tags"]


def test_the_bench_lines_round_trip_and_a_bad_line_is_refused_with_the_shape_named():
    d = races.derive(races.shipped()["dwarf"])
    lines = races.render_lines(d)
    assert "combat_mod cmd +4 racial when maneuver=bull rush|trip" in lines["modifiers"]
    back, problems = races.save_from_bench({**d, **lines})
    assert problems == []
    assert back["modifiers"] == d["modifiers"] and back["mods"] == d["mods"]
    _, problems = races.save_from_bench({"name": "Bad", "modifiers": "save_mod fortitude +2 racial\nperception plus two"})
    assert any("fort, ref or will" in p for p in problems)
    assert any("skill_mod perception +2 racial" in p for p in problems)


# --- the three laws --------------------------------------------------------------------

def test_a_racial_bonus_reaches_the_roll_through_the_funnel_and_names_itself():
    """An elf's +2 Perception used to be prose. Now it is a `skill_mod` on the document,
    read live like a feat's, and it leaves with the race."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.race = "elf"
    mods = pc.skill_modifiers("perception")
    elf = [m for m in mods if m.source == "Elf"]
    assert elf and elf[0].value == 2 and elf[0].type == "racial"
    pc.race = "human"
    assert not [m for m in pc.skill_modifiers("perception") if m.source == "Elf"]


def test_the_race_is_a_tag_question_not_a_string_match():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.race = "dwarf"
    assert pc.has_state("race.dwarf") and pc.has_state("sense.darkvision")
    assert not pc.has_state("race.human")
    pc.race = "human"
    assert pc.has_state("race.human") and not pc.has_state("sense.darkvision")


def test_the_extra_rank_is_asked_of_the_document():
    assert races.budget("human", "ranks") == 1 and races.budget("elf", "ranks") == 0
    assert races.budget("nobody", "ranks") == 0


# --- the forge --------------------------------------------------------------------------

def _payload(**over):
    base = {"name": "Test", "race": "human", "class": "fighter", "gender": "woman",
            "abilities": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
            "skills": ["climb", "swim", "perception"], "feats": ["toughness", "dodge"]}
    base.update(over)
    return base


def test_a_human_places_the_two_and_the_standard_option_places_three():
    built, problems = build(_payload(choices=["str"]))
    assert not problems, problems
    assert built["sheet"]["abilities"]["str"] == 17
    # The old single-pick spelling still answers the first slot.
    built, problems = build(_payload(bonus_ability="dex"))
    assert not problems and built["sheet"]["abilities"]["dex"] == 16
    # Nothing chosen: the fix is named.
    _, problems = build(_payload(choices=[]))
    assert any("puts +2 on any ability" in p for p in problems)


def test_a_race_over_the_tables_tier_is_refused_with_the_fix_named(tmp_path, monkeypatch):
    doc = races.normalise({"id": "dragonkin", "name": "Dragonkin", "type": "dragon",
                           "tags": ["sense.darkvision.60", "move.fly.30"],
                           "choose": list(races.STANDARD_CHOOSE)})
    assert races.rp(doc) > races.STANDARD_RP
    # The table's tier, pinned: this read the shared test data's rules file once, and
    # a probe that had set the tier to 20 made the refusal vanish.
    monkeypatch.setattr(houserules, "race_rp", lambda: races.STANDARD_RP)
    races.homebrew_dir(make=True).joinpath("dragonkin.json").write_text(
        json.dumps(doc), encoding="utf-8")
    try:
        _, problems = build(_payload(race="dragonkin", choices=["str", "cha", "wis"]))
        assert any("RP race" in p and "Rulesets bench" in p for p in problems)
    finally:
        races.homebrew_dir().joinpath("dragonkin.json").unlink()


# --- from the world ---------------------------------------------------------------------

def test_a_people_with_a_body_is_a_race_and_one_without_is_a_heritage(monkeypatch):
    """The fixture's six peoples: the Korvu carry Anatomy, Body, Senses and Lifecycle;
    the other five are ethnic groups with no body of their own. (With nothing written
    for the world — Pangrella ships its races now, so that is switched off here.)"""
    monkeypatch.setattr(races, "written_for", lambda w: {})
    drafted = races.from_world(WORLD)
    assert [d["name"] for d in drafted] == ["Korvu"]
    korvu = drafted[0]
    # Wings, talons and echolocation, read off their own sentences and priced from the
    # Race Builder — no number authored by anyone.
    assert "move.fly.30" in korvu["tags"] and "natural.claws" in korvu["tags"]
    assert "sense.blindsense.30" in korvu["tags"]
    assert korvu["choose"] == list(races.STANDARD_CHOOSE)
    assert korvu["converted"] and korvu["origin"].startswith("world:")
    assert korvu["people_id"] == "fd4449bc9a64"
    # The fly speed used to carry "the engine moves on the ground only" here, and this
    # asserted it was said rather than dropped. Stage 3 (2026-09-14) gave the engine a
    # level to move to, so the caveat came off — and the assertion flipped rather than
    # being deleted, because the thing worth pinning is that the Korvu's wings and the
    # Flight evolution agree about what they deliver. `tests/test_movement_modes.py`
    # holds both doors to that.
    assert not any("fly speed" in n for n in korvu["not_yet"]), korvu["not_yet"]
    assert races.speeds(korvu)["fly"] == 30
    heritages = [h["name"] for h in races.heritages_from_world(WORLD)]
    assert "Nahyrin" in heritages and "Korvu" not in heritages


def test_the_export_may_write_races_directly_in_words():
    class W:
        id = "w"; name = "W"; entities = {}
        play = {"races": [{"id": "sea-folk", "name": "Sea Folk", "size": "small",
                           "speed": "fast", "body": ["Gills line their necks."],
                           "senses": ["They see well in the dark of the deep."],
                           "movement": []}]}
    d = races.from_world(W())[0]
    assert d["size"] == "small" and d["speed"] == 40
    assert "amphibious" in d["tags"] and "sense.darkvision.60" in d["tags"]


def test_the_forge_offers_the_worlds_races_first_and_can_hide_the_core_seven(monkeypatch):
    monkeypatch.setattr("rules.creation._world", lambda wid: WORLD if wid == "pangrella" else None)
    got = options("pangrella")["races"]
    assert got[0]["of"] == WORLD.name and got[0]["name"] == "Kaelinoran"
    assert {r["id"] for r in got} >= {"korvu", "kaelinoran", "human", "elf"}
    monkeypatch.setattr(houserules, "core_races", lambda: False)
    got = options("pangrella")["races"]
    assert [r["id"] for r in got] == ["kaelinoran", "kelvaxian", "korvathyran", "korvu",
                                      "kyrexi", "valtorian"]
    # With no world there is always something to play.
    assert {r["id"] for r in options("")["races"]} >= {"human", "elf"}


def test_importing_writes_drafts_the_bench_can_correct_and_keeps_an_edited_copy(monkeypatch):
    monkeypatch.setattr(races, "written_for", lambda w: {})
    folder = races.homebrew_dir(make=True)
    path = folder / "korvu.json"
    if path.exists():
        path.unlink()
    try:
        assert races.import_from_world(WORLD) == ["korvu"]
        assert races.import_from_world(WORLD) == []          # kept, not clobbered
        edited = json.loads(path.read_text(encoding="utf-8"))
        edited["speed"] = 20
        path.write_text(json.dumps(edited), encoding="utf-8")
        offered = {d["id"]: d for d in races.for_world(WORLD)}
        assert offered["korvu"]["speed"] == 20                # the bench's copy wins
    finally:
        if path.exists():
            path.unlink()


def test_saving_an_imported_race_on_the_bench_keeps_where_it_came_from(client, monkeypatch):
    monkeypatch.setattr(races, "written_for", lambda w: {})
    """The generic save rebuilt the file from the form's declared fields alone, so an
    imported race lost `people_id` and `world` on its first correction — and with them
    the `world_people_id` every character of that race is stamped with."""
    folder = races.homebrew_dir(make=True)
    path = folder / "korvu.json"
    if path.exists():
        path.unlink()
    try:
        assert races.import_from_world(WORLD) == ["korvu"]
        opened = client.get("/api/bench/races/open/korvu").json()
        assert "sense.blindsense.30" in opened["tags"]          # rendered one per line
        body = {k: v for k, v in opened.items() if k != "source"}
        body["speed"] = 20
        r = client.post("/api/bench/races/save", data=json.dumps(body),
                        content_type="application/json")
        assert r.status_code == 200, r.content
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["people_id"] == "fd4449bc9a64" and saved["world"]
        assert saved["speed"] == 20 and saved["converted"] is False
        assert "sense.blindsense.30" in saved["tags"] and isinstance(saved["tags"], list)
        # A line the grammar cannot read is refused with the shape named.
        body["modifiers"] = "perception plus two"
        r = client.post("/api/bench/races/save", data=json.dumps(body),
                        content_type="application/json")
        assert r.status_code == 400 and "skill_mod perception +2 racial" in r.json()["error"]
    finally:
        if path.exists():
            path.unlink()


# --- the anatomy: eidolon evolutions, free of cost ----------------------------------------------

def test_evolutions_expand_into_the_grammar_and_cost_no_race_points():
    """"they can craft the anatomy from the Eidolon evolutions free of cost": claws
    become a natural weapon, flight a fly speed at the base speed, +8 Stealth a
    skill_mod, extra legs +10 ft — and none of it moves the race-point total."""
    doc = {"name": "Built", "choose": list(races.STANDARD_CHOOSE),
           "evolutions": [{"id": "claws"}, {"id": "flight"}, {"id": "skilled", "choice": "stealth"},
                          {"id": "limbs-legs"}, {"id": "resistance", "choice": "fire"},
                          {"id": "immunity", "choice": "cold"}, {"id": "ferocity"}]}
    d = races.derive(doc)
    assert d["speed"] == 40 and d["speeds"] == {"land": 40, "fly": 40}
    assert [w["key"] for w in d["weapons"]] == ["claws"]
    assert {"type": "skill_mod", "target": "stealth", "amount": 8, "bonus_type": "racial"} in d["modifiers"]
    assert "resist.fire.5" in d["tags"] and "immune.cold" in d["tags"] and "ferocity" in d["tags"]
    assert races.rp(doc) == 0 == races.rp({"name": "Bare", "choose": list(races.STANDARD_CHOOSE)})
    assert races.validate(doc) == []
    # A pick without its choice, and an attack without the body part it hangs off.
    problems = races.validate({"name": "x", "evolutions": [{"id": "sting"}, {"id": "skilled"}]})
    assert any("pick the skill" in p for p in problems)
    assert any("needs Tail" in p for p in problems)
    assert len(races.evolutions()) >= 50


def _built(tmp_id="built-one", **evs):
    doc = races.normalise({"id": tmp_id, "name": "Built One", "size": "small",
                           "choose": list(races.STANDARD_CHOOSE),
                           "evolutions": evs.get("evolutions", [])})
    races.homebrew_dir(make=True).joinpath(f"{tmp_id}.json").write_text(
        json.dumps(doc), encoding="utf-8")
    return races.homebrew_dir().joinpath(f"{tmp_id}.json")


def test_a_natural_weapon_is_in_the_hand_by_the_bodys_size_and_is_proficient():
    path = _built(evolutions=[{"id": "claws"}, {"id": "bite"}])
    try:
        pc = load_pc("fixtures/pc-kesst.json")
        pc.race = "built-one"
        pc.size = "small"
        claws = pc.weapon("claws")
        assert claws["name"] == "claws" and claws["damage"] == "1d3"   # Small
        assert claws["type"] == "slashing" and claws["natural"]
        assert pc.weapon("talons")["name"] == "claws"                   # an alias
        assert pc.is_proficient("claws") and pc.is_proficient("bite")
        pc.size = "medium"
        assert pc.weapon("bite")["damage"] == "1d6"
    finally:
        path.unlink()


def test_immunity_resistance_and_ferocity_are_read_off_the_tags():
    path = _built(evolutions=[{"id": "immunity", "choice": "cold"},
                              {"id": "resistance", "choice": "fire"}, {"id": "ferocity"}])
    try:
        pc = load_pc("fixtures/pc-kesst.json")
        pc.race = "built-one"
        assert pc.immune_to("cold") and not pc.immune_to("fire")
        assert pc.resistance("fire") == 5 and pc.resistance("acid") == 0
        # Below 0 with ferocity: staggered and dying, not unconscious.
        pc.hp = -2
        pc.apply_hp_state()
        assert pc.has_condition("staggered") and pc.has_condition("dying")
        assert not pc.has_condition("unconscious")
        pc.race = "human"
        pc.remove_condition("staggered"); pc.remove_condition("dying")
        pc.apply_hp_state()
        assert pc.has_condition("unconscious")
    finally:
        path.unlink()


def test_the_brief_tells_the_narrator_what_the_body_can_do():
    from gm import prompts
    from rules.engine import Engine, Scene

    path = _built(evolutions=[{"id": "flight"}, {"id": "darkvision"}, {"id": "claws"}])
    try:
        s = Scene(location_id="5bbd0c40345f")
        pc = load_pc("fixtures/pc-kesst.json")
        pc.race = "built-one"
        s.add(pc)
        e = Engine(s, Dice(seed=1), world=WORLD)
        brief = prompts.scene_brief(WORLD, s, WORLD.get("5bbd0c40345f"), here=e.here(), known=e.places())
        assert "A Built One: moves by fly 30 ft as well as on foot; senses: darkvision 60 ft; natural weapons: claws." in brief
    finally:
        path.unlink()


def test_the_race_editor_page_carries_the_catalogue_and_opens_a_race(client):
    r = client.get("/homebrew/races/?open=dwarf")
    assert r.status_code == 200
    page = r.content.decode("utf-8")
    assert '"evolutions"' in page and "Claws" in page and '"open": "dwarf"' in page
    d = client.get("/api/races/open/dwarf").json()
    assert d["source"] == "shipped" and d["rp"] > 0 and "sense.darkvision.60" in d["tags"]
    # A pickers-built document saves through the same door as the bench.
    body = {"name": "Editor Built", "type": "humanoid", "size": "medium", "speed": 30,
            "mods": {}, "choose": list(races.STANDARD_CHOOSE), "budget": {},
            "languages": ["common"],
            "evolutions": [{"id": "bite"}, {"id": "skilled", "choice": "perception"}]}
    r = client.post("/api/bench/races/save", data=json.dumps(body), content_type="application/json")
    assert r.status_code == 200, r.content
    try:
        saved = json.loads(races.homebrew_dir().joinpath("editor-built.json").read_text(encoding="utf-8"))
        assert saved["evolutions"] == [{"id": "bite", "choice": "", "times": 1},
                                       {"id": "skilled", "choice": "perception", "times": 1}]
        assert "natural.bite" in races.document("editor-built")["tags"]
    finally:
        races.homebrew_dir().joinpath("editor-built.json").unlink()


# --- the two worlds' own races -------------------------------------------------------------------

def test_pangrella_ships_its_species_with_their_peoples_as_heritages():
    """The continents name the species in their own words — winged Kaelinorans and
    Korvathyrans, flightless Kyrexi and Valtorians, subterranean Kelvaxians — and the
    Korvu are a body of their own. The six PEOPLE entries are cultures of those, so a
    Nahyrin is offered as a Kaelinoran heritage and not as a race; nothing is drafted
    twice."""
    offered = {d["id"]: d for d in races.for_world(WORLD)}
    assert set(offered) == {"korvu", "kaelinoran", "kyrexi", "korvathyran", "valtorian",
                            "kelvaxian"}
    assert "move.fly.30" in offered["kaelinoran"]["tags"]
    assert "sense.blindsense.30" in offered["korvu"]["tags"] and "natural.claws" in offered["korvu"]["tags"]
    assert "sense.darkvision.60" in offered["kelvaxian"]["tags"]
    assert [h["name"] for h in offered["valtorian"]["heritages"]] == ["Khra'gix", "Khy'vyr", "Nirkor"]
    assert [h["name"] for h in offered["kyrexi"]["heritages"]] == ["Zhilakai"]
    assert races.heritages_from_world(WORLD) == []          # every people is spoken for
    assert all(races.validate(d) == [] for d in offered.values())
    assert all(races.rp(d) <= races.STANDARD_RP for d in offered.values())
    # Not drafted twice, and not written twice: importing the world writes nothing.
    assert races.import_from_world(WORLD) == []


def test_every_shipped_world_race_validates_and_names_its_world():
    for rid, d in races.shipped().items():
        assert races.validate(d) == [], (rid, races.validate(d))
        if d.get("world"):
            assert d["world"] in ("pangrella-campaign", "fantasia-campaign"), rid
            assert d["origin"].startswith("world:"), rid
    fantasia = [d for d in races.shipped().values() if d.get("world") == "fantasia-campaign"]
    assert len(fantasia) == 12
    # Outside its world a world's race is not offered; inside, it is.
    assert "khyzhi" not in {r["id"] for r in options("")["races"]}


def test_a_repeatable_evolution_has_no_ceiling_and_each_take_keeps_its_own_pick():
    """"in every case that I can choose the evolution again it needs to be the full
    picking. I should be able to have as many arms and legs as I want." Four pairs of
    legs validate and add forty feet; three resistances to three energies are three
    picks; a once-only evolution taken twice is still refused."""
    doc = {"name": "Many", "choose": list(races.STANDARD_CHOOSE),
           "evolutions": [{"id": "limbs-legs"}] * 4
                         + [{"id": "resistance", "choice": "fire"}, {"id": "resistance", "choice": "cold"},
                            {"id": "resistance", "choice": "acid"}, {"id": "skilled", "choice": "stealth"},
                            {"id": "skilled", "choice": "perception"}]}
    assert races.validate(doc) == []
    d = races.derive(doc)
    assert d["speed"] == 70
    assert {"resist.fire.5", "resist.cold.5", "resist.acid.5"} <= set(d["tags"])
    assert [m["target"] for m in d["modifiers"] if m["type"] == "skill_mod"] == ["stealth", "perception"]
    twice = races.validate({"name": "x", "evolutions": [{"id": "gills"}, {"id": "gills"}]})
    assert any("once" in p for p in twice)
    assert "unarmed strike" in races.catalogue()["attacks"]


# --- what a people is good and bad at, in the world's own words ---------------------------

def test_a_card_could_not_say_what_a_race_was_good_at_and_now_can():
    """The gap the race cards shipped with, measured 2026-09-10 against a live card.

    A World Bible race card could express a size, a speed and twelve possible traits,
    and nothing else — so every world race got the generic +2 physical / +2 mental /
    -2 any and differed from every other race in that world only in its senses. Ability
    modifiers are the most defining mechanical feature of a 1e race and the export had
    no channel for them.

    Six words carry it now, none of which needs a rules system to say. The Race Builder
    prices the result itself: a fixed +2/+2/-2 is 0 RP when one bonus is physical and
    one mental, 1 RP when both sit in the same group, which is the table's own
    standard/specialised split.
    """
    mods, choose = races.array_from_words(["nimble", "perceptive"], "commanding")
    assert mods == {"dex": 2, "wis": 2, "cha": -2}
    assert choose == [], "a card that states its array leaves nothing to choose"
    # Speed 30 on purpose: a fast race costs a race point for the speed, and this is
    # measuring what the ARRAY costs.
    doc = races.derive(races.normalise(
        {"id": "vanara", "name": "Vanara", "size": "medium", "speed": 30,
         "mods": mods, "choose": choose}))
    assert races.rp(doc) == 0 and races.power(races.rp(doc)) == "standard"
    fast = races.derive(races.normalise(
        {"id": "vanara", "name": "Vanara", "size": "medium", "speed": 40,
         "mods": mods, "choose": choose}))
    assert races.rp(fast) == 1, "the extra point is the speed, not the array"

    both_physical, _ = races.array_from_words(["strong", "hardy"], "clever")
    priced = races.derive(races.normalise(
        {"id": "x", "name": "X", "size": "medium", "speed": 30,
         "mods": both_physical, "choose": []}))
    assert races.rp(priced) == 1, "two physical bonuses is the specialised row, 1 RP"


@pytest.mark.parametrize("strengths,weakness,why", [
    (["nimble"], "commanding", "one strength is half an array"),
    (["nimble", "perceptive"], "", "no weakness is half an array"),
    (["nimble", "nimble"], "commanding", "the same strength twice"),
    (["nimble", "perceptive"], "nimble", "the weakness is also a strength"),
    (["fast", "wise"], "rude", "words the table does not know"),
    ([], "", "nothing said at all"),
])
def test_half_an_array_is_not_an_array(strengths, weakness, why):
    """Exactly two strengths and one weakness, or none of it counts.

    The Advanced Race Guide's standard array is +2/+2/-2 as a unit. Accepting half of
    one would let a card grant a net +4 by leaving the weakness out, which is a power
    creep bought by saying less — so every malformed case falls back to the generic
    choose the card would have had anyway, and nothing is priced above standard.
    """
    mods, choose = races.array_from_words(strengths, weakness)
    assert mods == {}, why
    assert choose == list(races.STANDARD_CHOOSE), why


def test_saying_it_wrong_is_recorded_where_the_player_can_see_it():
    """Silently handing back the generic array would hide the author's mistake from
    everyone who could fix it. `not_yet` is where this file already says what it could
    not do."""
    d = races.draft("Half", ["They climb well."], strengths=["nimble"], weakness="")
    assert any("two strengths and one weakness" in line for line in d["not_yet"])
    assert all("commanding" in line for line in d["not_yet"] if "strengths" in line), \
        "the refusal names the six words, the way every validator here names the fix"
    quiet = races.draft("Quiet", ["They climb well."])
    assert not any("strengths" in line for line in quiet["not_yet"]), \
        "a card that says nothing about it is not nagged about it"


def test_a_card_without_the_new_fields_behaves_exactly_as_before():
    """Additive, so a 1.1 export keeps working unchanged — the fields are read when
    present and absent otherwise."""
    class World:
        play = {"races": [{"id": "korvu", "name": "Korvu", "people_id": "k",
                           "size": "medium", "speed": "normal",
                           "body": ["They have broad wings."], "senses": [], "movement": []}]}
        entities = {}
        source = "pangrella-campaign.json"

    d = races.from_world(World())[0]
    assert d["mods"] == {}
    assert d["choose"] == list(races.STANDARD_CHOOSE)


# --- pricing a tag the table has never seen ---------------------------------------------
#
# Measured 2026-09-13, asking what happens when World Bible describes a people this app
# has not seen before. `TAG_RP` was twenty-one exact strings with the magnitude baked
# into the key, and every miss fell through `TAG_RP.get(t, (0, ""))[0]` and cost nothing.
# So `move.fly.30` was 4 RP and `move.fly.40` was free, and the forge reported a race as
# cheaper than it is with no sign anything had been skipped.
#
# Two readers of the same tag already disagreed about this: `speeds()` and `senses()`
# pull the number out with a regex and handle any value, while the price list handled
# twenty-one. The half that generalises was the half that was right.

def test_a_speed_the_table_never_listed_is_not_free():
    from rules.races import price_tag

    assert price_tag("move.fly.30")[0] == 4, "the anchor must not move"
    faster, _words, how = price_tag("move.fly.40")
    assert faster > 4, "flying further cost nothing"
    assert how == "derived"


def test_every_anchor_keeps_the_price_the_book_gave_it():
    """The scaling must not quietly re-price the rows the Advanced Race Guide actually
    has. Those are the ones the shipped races are built from."""
    from rules.races import TAG_RP, price_tag

    for tag, (cost, _words) in TAG_RP.items():
        got, _w, how = price_tag(tag)
        assert (got, how) == (cost, "exact"), f"{tag} moved: {cost} -> {got}"


def test_no_shipped_race_changed_price():
    """The whole change should bite only on values the table never had."""
    from rules import races

    for rid, doc in races.all_races().items():
        d = races.normalise(doc)
        old = sum(races.TAG_RP.get(t, (0, ""))[0] for t in d["tags"])
        new = sum(races.price_tag(t)[0] for t in d["tags"])
        assert old == new, f"{rid}: {old} -> {new}"


def test_a_family_nobody_has_priced_is_named_rather_than_silently_free():
    """It still costs nothing — inventing a number would be worse — but it is on the
    card as unpriced instead of being indistinguishable from a trait that is free."""
    from rules.races import derive, price_tag

    cost, _words, how = price_tag("glows.faintly")
    assert (cost, how) == (0, "unknown")

    # `derive` is what the forge renders a race card from; `normalise` is the raw
    # document underneath it and carries neither list.
    d = derive({"id": "lamplit", "name": "Lamplit", "size": "medium", "speed": 30,
                   "tags": ["glows.faintly", "move.fly.40"]})
    assert "glows.faintly" in d["unpriced"], d["unpriced"]
    # A speed the table can scale is NOT unpriced — that lumping is what hid the bug.
    assert "move.fly.40" not in d["unpriced"]
    assert any("move.fly.40" in line for line in d["derived_prices"]), d["derived_prices"]


def test_the_scaled_price_is_shown_as_scaled():
    """A derived number must not present itself as the book's. The forge says which."""
    from rules.races import derive

    d = derive({"id": "deepseer", "name": "Deepseer", "size": "medium", "speed": 30,
                   "tags": ["sense.darkvision.90"]})
    assert d["derived_prices"] and "scaled" in d["derived_prices"][0]
