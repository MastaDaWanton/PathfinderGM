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
    docs = races.shipped()
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
    races.homebrew_dir(make=True).joinpath("dragonkin.json").write_text(
        json.dumps(doc), encoding="utf-8")
    try:
        _, problems = build(_payload(race="dragonkin", choices=["str", "cha", "wis"]))
        assert any("RP race" in p and "Rulesets bench" in p for p in problems)
    finally:
        races.homebrew_dir().joinpath("dragonkin.json").unlink()


# --- from the world ---------------------------------------------------------------------

def test_a_people_with_a_body_is_a_race_and_one_without_is_a_heritage():
    """The fixture's six peoples: the Korvu carry Anatomy, Body, Senses and Lifecycle;
    the other five are ethnic groups with no body of their own."""
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
    # Said, not dropped: the engine has no fly speed yet.
    assert any("fly speed" in n for n in korvu["not_yet"])
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
    assert got[0]["name"] == "Korvu" and got[0]["of"] == WORLD.name
    assert {r["id"] for r in got} >= {"korvu", "human", "elf"}
    monkeypatch.setattr(houserules, "core_races", lambda: False)
    got = options("pangrella")["races"]
    assert [r["id"] for r in got] == ["korvu"]
    # With no world there is always something to play.
    assert {r["id"] for r in options("")["races"]} >= {"human", "elf"}


def test_importing_writes_drafts_the_bench_can_correct_and_keeps_an_edited_copy():
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


def test_saving_an_imported_race_on_the_bench_keeps_where_it_came_from(client):
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
