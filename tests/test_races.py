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
    the other five are ethnic groups with no body of their own.

    This is the DERIVED path — what the consumer does for a world that ships no race
    cards — and forcing it took two goes.

    The first version patched `races.written_for`, which `from_world` does not call: it
    reads `world.play["races"]` itself. So the patch was inert and the test exercised
    whichever branch the fixture happened to trigger, passing only because the fixture
    was schema 1.0 and had no `play.races[]` at all. A World Bible export at 1.3 put one
    there, the written branch ran, the Korvu came back with the ability array from their
    own card (`perceptive, clever` against `hardy`), and the assertion below about the
    generic spread failed — correctly, and three versions of the schema late.

    So the emptying is done where the function actually looks. `test_a_world_that_ships
    _race_cards_is_read_from_them` covers the other branch.

    BOTH are needed, and they are different things with confusingly similar names.
    `written_for` is the races somebody wrote BY HAND for this world in `content/races`
    or on the bench; `play["races"]` is the list the EXPORT ships. `heritages_from_world`
    reads the first and `from_world` reads the second, so silencing one says nothing
    about the other.
    """
    monkeypatch.setattr(races, "written_for", lambda w: {})
    monkeypatch.setattr(WORLD, "play", {**(WORLD.play or {}), "races": []}, raising=False)
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


def test_a_world_that_ships_race_cards_is_read_from_them_not_derived(monkeypatch):
    """The other branch, which had no test at all until an export exercised it by
    accident.

    A card carrying `strengths` and `weakness` gives the people a fixed array; the
    derived path cannot, because a `PEOPLE` entity's anatomy facts say what a body looks
    like and never what it is good at. So the two branches genuinely differ, and which
    one runs is decided by whether `play.races[]` is there — not by any patching.
    """
    card = {"id": "korvu", "name": "Korvu", "people_id": "fd4449bc9a64",
            "size": "medium", "speed": "normal",
            "body": ["Korvu have avian-like wings and bodies."],
            "senses": ["Korvu have enhanced echolocation abilities."],
            "movement": ["Korvu have avian-like wings and bodies."],
            "about": "One paragraph.",
            "strengths": ["perceptive", "clever"], "weakness": "hardy"}
    monkeypatch.setattr(WORLD, "play", {**(WORLD.play or {}), "races": [card]},
                        raising=False)
    drafted = races.from_world(WORLD)
    assert [d["name"] for d in drafted] == ["Korvu"]
    korvu = drafted[0]
    # perceptive -> wis, clever -> int, hardy -> con. Words in, table out: the export
    # states what the people is good at and never what that is worth.
    assert korvu["mods"] == {"wis": 2, "int": 2, "con": -2}
    assert korvu["choose"] == [], "a stated array and a chosen one are not both given"
    # And the body still comes from the card's own sentences.
    assert "move.fly.30" in korvu["tags"]


def test_an_incomplete_ability_array_falls_back_rather_than_half_applying():
    """The contract says all three or none. Half an array priced as a race would be the
    world's opinion applied and the player's choice taken away in the same move."""
    for strengths, weakness in ((["perceptive"], "hardy"),      # one strength
                                (["perceptive", "clever"], ""),  # no weakness
                                (["clever", "clever"], "hardy"),  # not two distinct
                                (["clever", "hardy"], "hardy")):  # weakness is a strength
        mods, choose = races.array_from_words(strengths, weakness)
        assert mods == {}, (strengths, weakness)
        assert choose == list(races.STANDARD_CHOOSE), (strengths, weakness)


# --- a tag the world grants has to be a thing the character can do --------------------------

def test_a_race_the_world_wrote_can_actually_swing_its_bite():
    """Measured 2026-09-16, on the shipped world and reported from the World Bible side
    as thin race cards: four of Aurvantis's sixteen races grant claws or a bite off their
    own words, and not one of them could use it.

    The machinery was all there — the validator knows every natural weapon's name, the
    sheet builds one at the right die for the body's size, `_NATURAL_RIDERS` resolves what
    a bite does past its damage — and the one missing link was `expand` turning the TAG
    into a weapon. A race card only ever carries tags: it has no evolutions, because
    nobody picked any. So the weapon comes from the evolution that grants the same tag,
    which keeps one definition of what a bite is worth.

    This is the half of "thin" that was this app's own, and it was being reported to the
    supplier as a defect in their content.
    """
    card = {"id": "fangfolk", "name": "Fangfolk", "size": "medium", "speed": "normal",
            "body": ["Fangfolk have heavy fangs and clawed hands."],
            "senses": [], "movement": [], "about": "One paragraph.",
            "strengths": ["strong", "hardy"], "weakness": "clever"}
    doc = races.expand(races.draft(card["name"], card["body"],
                                   size_hint=card["size"], speed_hint=card["speed"],
                                   strengths=card["strengths"],
                                   weakness=card["weakness"]))
    assert {"natural.bite", "natural.claws"} <= set(doc["tags"]), doc["tags"]
    keys = {str(w.get("key")) for w in doc.get("weapons") or []}
    assert {"bite", "claws"} <= keys, keys
    # The die is the body's, not a constant: one definition of what a bite is worth.
    bite = next(w for w in doc["weapons"] if w["key"] == "bite")
    assert bite["damage"]["medium"] == "1d6" and bite["damage"]["small"] == "1d4"
    # And nothing tells the player it is waiting on the engine any more.
    assert not any("natural attacks" in line for line in doc.get("not_yet") or [])


def test_the_published_cue_list_is_what_the_table_says_today():
    """`docs/race-cues.json` is what World Bible reads to know which words do something,
    and it is generated — but generating it is only half. It was published saying 6 of 12
    cues were engine-ready while the table said 10, so an author was told that four of the
    traits they write reach nothing. The same guard the place vocabulary already had."""
    from pathlib import Path

    import importlib.util

    from django.conf import settings

    path = Path(settings.BASE_DIR, "tools", "export_race_cues.py")
    spec = importlib.util.spec_from_file_location("export_race_cues", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    on_disk = json.loads(
        Path(settings.BASE_DIR, "docs", "race-cues.json").read_text(encoding="utf-8"))
    assert on_disk == module.build(), (
        "docs/race-cues.json is stale — run tools/export_race_cues.py")
    assert on_disk["engine_ready_count"] == sum(1 for *_x, waits in races.CUES if not waits)


def test_versatile_and_lucky_are_words_this_app_now_knows():
    """The supplier was right and this was the gap on our side.

    Three of Aurvantis's sixteen race cards produced no usable trait, and this app called
    them content defects. They were checked against their own anatomy before anything was
    touched: a Human "physically unremarkable and highly variable" and a Halfling with
    "unusually good luck" are described correctly and completely — there was simply no cue
    that meant versatile or lucky, so the words reached nothing. They declined to invent
    traits to fill a vocabulary gap, which was the right call.

    Both are plain 1e: a human's extra feat and extra skill rank, a halfling's +1 racial
    bonus on all saving throws.
    """
    human = races.expand(races.draft(
        "Human", ["Humans are physically unremarkable and highly variable."]))
    assert "versatile" in human["tags"]
    assert human["budget"] == {"feats": 1, "ranks": 1}, human["budget"]

    halfling = races.expand(races.draft(
        "Halfling", ["Halflings are small, nimble, and have unusually good luck."]))
    assert "lucky" in halfling["tags"]
    saves = {m["target"] for m in halfling["modifiers"] if m["type"] == "save_mod"}
    assert saves == {"fort", "ref", "will"}, halfling["modifiers"]
    assert all(m["amount"] == 1 and m["bonus_type"] == "racial"
               for m in halfling["modifiers"])


def test_the_two_new_cues_price_themselves_from_parts_and_never_from_a_guess():
    """`versatile` carries its cost in the budget it grants — the Race Builder prices a
    bonus feat and a bonus rank, and `BUDGET_RP` is that. `lucky` carries its cost in its
    modifiers.

    Neither tag is in `TAG_RP`, and that is deliberate rather than an omission: the Race
    Builder's own price for a +1 racial bonus on all saves could not be sourced in two
    searches, and `price_tag` has a three-way answer for exactly this — it reports
    `unknown` instead of letting an unpriced tag look free.
    """
    assert races.price_tag("versatile")[2] == "unknown"
    assert races.price_tag("lucky")[2] == "unknown"
    human = races.expand(races.draft("Human", ["Physically unremarkable and variable."]))
    assert races.rp(human) >= sum(races.BUDGET_RP.values()), "the budget priced at nothing"


def test_the_checker_we_ship_reads_the_vocabulary_we_ship():
    """The defect this prevents, found 2026-09-16 and six days old by then.

    `tools/check_race_cards.py` is written to be copied into the World Bible repo with
    `race-cues.json` beside it, so its default looked for the file next to itself. A
    second copy of that generated list had been sitting in `tools/` since 10 September —
    **twelve cues against fourteen, six engine-ready against twelve** — and because it was
    beside the script, it won.

    Every count this checker printed in between was measured against a vocabulary this app
    had already moved past, including the counts reported to the supplier as evidence
    about THEIR content. On the same fixture, with nothing in the world changed, the real
    numbers were 1 card with problems and 11 thin against the 3 and 15 that were reported.

    A generated file with two copies is the exact trap CLAUDE.md names, one level down
    from the rule it names it in.
    """
    import importlib.util
    from pathlib import Path

    from django.conf import settings

    path = Path(settings.BASE_DIR, "tools", "check_race_cards.py")
    spec = importlib.util.spec_from_file_location("check_race_cards", path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    assert not path.with_name("race-cues.json").exists(), (
        "a second copy of the generated cue list is back in tools/ — it will go stale "
        "and it will win, because the checker looks beside itself first")
    cues = checker.load_cues(checker._default_cues())
    assert cues["cue_count"] == len(races.CUES), (
        f"the checker reads {cues['cue_count']} cues and the table has {len(races.CUES)}")
    assert cues["engine_ready_count"] == sum(1 for *_x, waits in races.CUES if not waits)


# --- the card states its own tags (schema 1.5) -----------------------------------------

def _traits_of(doc) -> list:
    """A document's tags minus its own identity. `race.half-orc` is what the race IS and
    every document has one; these tests are about what it GRANTS."""
    return [t for t in doc["tags"] if not t.startswith("race.")]

def test_every_tag_a_cue_can_grant_has_a_meaning_of_its_own():
    """`TAG_MEANS` is what a tag shows when a card STATES it rather than describing it.

    A cue row can grant two tags and show one line for both — the gills row grants
    `amphibious` and `move.swim.30` and shows "amphibious; swim 30 ft". A card stating
    only one of them would get the other's words, so the line belongs to the tag. This
    asserts the two tables cannot drift: a cue added without a meaning fails here.
    """
    from_cues = {t for _p, granted, _l, _w in races.CUES for t in granted}
    assert from_cues <= set(races.TAG_MEANS), from_cues - set(races.TAG_MEANS)


def test_a_card_that_states_its_tags_is_not_read_for_them():
    """Ruled 2026-09-16: *"we should not need to interpret anatomy on import. We should
    receive exactly the anatomy as our engine will read it."*

    Measured on the shipped Aurvantis export the same day, which is why the rule was
    needed: the Half-Orc card's body said "sometimes visible tusks", the `tusks?` cue
    granted `natural.bite`, and every half-orc a player could roll walked out of the
    forge with a 1d6 bite.

    The defect is not the bite. Ruled hours later, correcting the first version of this
    docstring: *"these races are specific to this world even if they are called Orcs, so
    it's okay if they're different."* A world's half-orcs may bite. The defect is that
    the world could not say NO — declining the bite meant deleting the word "tusks" from
    a sentence about their faces. The card is the authority on what it grants now, which
    makes both answers sayable.
    """
    tusks = ["Human build with orcish ruggedness — a heavier brow, visible tusks."]
    read = races.draft("Half-Orc", tusks)
    assert "natural.bite" in read["tags"], "the cue table is what this rule replaces"

    stated = races.draft("Half-Orc", tusks, granted=["sense.darkvision.60"])
    assert _traits_of(stated) == ["sense.darkvision.60"]
    assert stated["traits"] == ["darkvision 60 ft"]


def test_a_stated_tag_is_granted_even_when_no_word_in_the_card_would_have_found_it():
    """The other direction, and the one that makes this a contract rather than a filter:
    a tag the prose gives no hint of is still granted. Otherwise the cue table is still
    the authority and the card is only allowed to agree with it."""
    quiet = races.draft("Stoneborn", ["They keep to themselves and say little."],
                        granted=["move.burrow.20", "sense.darkvision.60"])
    assert _traits_of(quiet) == ["move.burrow.20", "sense.darkvision.60"]
    assert "burrow 20 ft" in quiet["traits"]
    # And a tag the engine cannot use yet still says so, exactly as the prose path does.
    assert any("no earth" in n for n in quiet["not_yet"]), quiet["not_yet"]


def test_a_stated_tag_this_engine_cannot_name_is_reported_and_not_dropped():
    """Two programs sharing a vocabulary will disagree about it eventually. The quiet
    version of that is a race missing something nobody can name, so an unknown tag
    becomes a `not_yet` line the forge shows and never a silent omission."""
    odd = races.draft("Aetherkin", ["They flicker."],
                      granted=["sense.darkvision.60", "sense.tremorsense.60"])
    assert _traits_of(odd) == ["sense.darkvision.60"]
    assert any("sense.tremorsense.60" in n for n in odd["not_yet"]), odd["not_yet"]


def test_a_card_that_stated_its_tags_is_not_marked_as_converted():
    """`converted` means this app read prose and guessed. On a stated card nothing
    guessed, and the flag would be a lie — the ingredient bench shows it as
    "unreviewed"."""
    assert races.draft("Tengu", ["Crow-featured."], granted=["natural.bite"])["converted"] is False
    assert races.draft("Tengu", ["Crow-featured, with a beak."])["converted"] is True


def test_the_shipped_world_s_cards_reach_the_forge_by_their_own_tags():
    """End to end on real data rather than a constructed card: every Aurvantis race the
    forge offers carries exactly the tags its card states.

    Measured when this was built: all 16 agree with what the cue table would have read,
    because World Bible generates `grants[]` by running the same vocabulary. That makes
    this change a no-op on today's export ON PURPOSE — the point is that the next time
    their generator gets better at anatomy, this engine follows without a regex here.
    """
    world = loader.load_cached("fixtures/aurvantis-campaign.json")
    cards = {c["name"]: c for c in (world.play or {}).get("races") or []}
    assert cards, "the fixture stopped carrying race cards"
    built = {d["name"]: d for d in races.from_world(world)}
    for name, card in cards.items():
        stated = [t for t in (card.get("grants") or []) if t in races.TAG_MEANS]
        assert _traits_of(built[name]) == stated, name
