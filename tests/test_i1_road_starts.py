"""Phase 3, I1 — starts on the road outside a settlement (docs/fix-interfaces.md §3.3, Q22,
Q24; docs/design-c-starts.md §4.5; docs/design-b-space.md's ring).

The owner's own example, 2026-09-28: "walking toward a town and as i crest a hill i see a
caravan under attack. this on the road scenario would be the best start and its simple."
Before this task both road documents validated and `openings.placeable` refused them —
1,000 of 1,000 draws for the caravan hand, whose start it is, never reached the road
(`test_c_starts.test_a_road_start_waits_for_the_outskirts`, retired here with the refusal).

Engine-side only: no model is asked. Every test runs once per world (`worlds`).
"""
from __future__ import annotations

import collections
import json

import pytest
from django.test import override_settings

from play import campaign as cm
from play import opening, opening_prose
from rules import geography, openings, outskirts, places
from rules.sheet import load_pc

BORIN = "fixtures/pc-borin.json"
KESST = "fixtures/pc-kesst.json"
ROAD = ("road-caravan-attack", "road-in")


def _open(worlds, tmp_path, start_id: str, seed: int = 11, pc_path: str = BORIN):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign(f"i1-{start_id}-{seed}", seed=seed, character=load_pc(pc_path),
                            world_source=str(worlds.source), start_id=start_id)
    assert c.start_id == start_id, (worlds.source, start_id, c.start_id)
    return c


# --- placement ----------------------------------------------------------------------------

@pytest.mark.parametrize("start_id", ROAD)
def test_a_road_start_stands_the_party_outside_on_a_real_road(worlds, tmp_path, start_id):
    """`where: road` stands the party at one of the settlement's own road heads — Lane B's
    ring place `the road to {To}`, a real place id the engine's place set contains — and
    never inside the town. Before I1 the refusal was total (0 of 1,000 draws placed); the
    risk it guarded against was "the gate wearing a road's name", so the checks are that
    the place is OUTSIDE by its id's own grammar and is a road head of THIS settlement."""
    c = _open(worlds, tmp_path, start_id)
    at = c.scene.at
    assert places.setting_of(at) == "outside", at
    assert outskirts.road_head_of(at) and not outskirts.is_along(at), at
    assert places.location_of(at) == c.scene.location_id
    here = places.find(c.engine().places(), at)
    assert here is not None and here.name.lower().startswith(("the road to", "the way to"))
    assert c.scene.pc().at == at
    # The panel says where they are as Lane B made it say it: near the town, not in it.
    assert geography.where(worlds, c.scene, here).label.startswith("near ")
    rec = c.scene.start
    assert rec["setting"] == "outside" and rec["outside"] == c.location.name
    assert rec["where_words"] == f"on {here.name}, outside {c.location.name}"


def test_every_road_head_a_draw_can_reach_is_outside(worlds):
    """Across every town a start may open in: a road start is drawable exactly where the
    town has a road head, and the spot it would stand on is always an outside ring place
    of that town — never one of its rooms (measured at this commit: Aurvantis 59 of 64
    towns, Pangrella 9 of 12, the synthetic world 6 of 6)."""
    doc = openings.get("road-in")
    drawable = 0
    for town in openings.towns(worlds):
        spot = openings.spot_for(worlds, town, doc)
        if spot is None:
            assert not openings.fits(worlds, town, doc)
            continue
        drawable += 1
        assert places.setting_of(spot.id) == "outside", spot.id
        assert places.location_of(spot.id) == str(town.id)
        assert outskirts.road_head_of(spot.id), spot.id
    assert drawable >= 1


# --- the caravan attack ----------------------------------------------------------------------

@pytest.mark.parametrize("seed", [0, 1, 4, 7])
def test_the_caravan_attack_is_a_real_encounter_near_the_party_level(worlds, tmp_path, seed):
    """The owner's caravan under attack is a fight the engine holds: the encounter open,
    the attackers on their own side, every one from a stat block (bandits from the codex
    since 2026-09-30; until then the bestiary by the road head's own biome — never a number
    a model wrote), the
    encounter's CR within one of the party's level by the Core Rulebook's XP table, and
    the caravan's own people on the board as bystanders in no side. Measured on the first
    draws (2026-09-29): a giant solifugid, two vultures, two adolescent wolves, two
    raiders — and "the medium giant scorpion", named as the index names it, until
    `creature_noun` dropped the size."""
    from rules import bestiary, xp

    c = _open(worlds, tmp_path, "road-caravan-attack", seed=seed)
    scene, rec = c.scene, c.scene.start
    pc = scene.pc()
    assert scene.in_encounter
    foes = rec["foes"]
    assert foes and scene.sides.get("raiders") == foes
    assert pc.ref in scene.sides.get("party", [])
    total = 0
    for ref in foes:
        foe = scene.people[ref]
        assert bestiary.lookup(foe.from_template), foe.from_template
        total += xp.worth(foe)
        assert foe.ref in scene.positions
    level = int(pc.level)
    assert level - 1 <= openings.encounter_cr(total) <= level + 1, (total, level)
    # The raiders are people since 2026-09-30 (`from: outlaws`): the land sent Pangrella's
    # caravan two ponies as "raiders", and the prose put riders on them. Every raider is a
    # humanoid stat block with a person's face (tests/test_road_raiders_are_people.py).
    for ref in foes:
        row = bestiary.raw_block(scene.people[ref].from_template) or {}
        assert str(row.get("creature_type") or "humanoid") == "humanoid", row.get("id")
        assert scene.people[ref].appearance
    in_sides = {r for refs in scene.sides.values() for r in refs}
    drovers = [a for a in scene.people.values() if a.name.endswith("drover")]
    assert len(drovers) == 2
    for civ in drovers + [scene.people[rec["slots"]["lead"]]]:
        assert civ.ref not in in_sides and scene.conscious(civ.ref)
        assert civ.ref in scene.positions


@pytest.mark.parametrize("start_id", ROAD)
def test_the_hand_off_is_not_crossed(worlds, tmp_path, start_id):
    """The opening stops where the player takes over, and the engine agrees with it: for
    the caravan, the party holds the turn (an attacker that won initiative has spent it
    coming at the wagon — `_up_to_the_party`), nobody has been struck, no roll is owed,
    and nothing is in the turn log. The template names the moment, crosses nothing in
    `CROSSED`, and ends on the question."""
    c = _open(worlds, tmp_path, start_id)
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm.open_the_story(c, written=False)
    text = c.transcript[-1]["text"]
    doc = openings.get(start_id)
    assert openings.crossed(text, c.scene.start) == []
    assert doc["hand_off"]["moment"] in text
    assert text.rstrip().endswith("What do you do?")
    assert "$" not in text
    scene = c.scene
    assert not scene.awaiting and c.turn_log == []
    for a in scene.people.values():
        assert a.hp == a.hp_max, (a.name, a.hp, a.hp_max)
    if doc["hand_off"]["at"] == "fight":
        assert scene.current_ref() == scene.pc().ref


@pytest.mark.parametrize("seed", range(12))
def test_the_party_holds_the_turn_whoever_wins_initiative(tmp_path, seed):
    """Over twelve story seeds on one world the attackers win initiative in some and lose
    it in others (measured: 6 of 8 Aurvantis seeds had an attacker first); in every one the
    start hands over on the PC's own turn with every creature unhurt. A turn left on an
    NPC is the dead state `views._hand_the_turn_back` exists to end — the Spells tab
    answers "It is not your turn" to a wizard who has not had one."""
    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    c = _open(world, tmp_path, "road-caravan-attack", seed=seed)
    scene = c.scene
    assert scene.current_ref() == scene.pc().ref
    assert all(a.hp == a.hp_max for a in scene.people.values())


def test_the_road_opening_describes_the_road_and_the_land_not_a_room(worlds, tmp_path):
    """A road start's first paragraph is the road and the world's land around it, from
    Lane B's LAND AROUND (`geography.land_around`): "outside {town}", the road head's own
    caption, the near ground by name — and no "buildings round about", which is the room
    template's line and would put the party back in the town. The model's material says
    the same, with the world's land in its own words."""
    c = _open(worlds, tmp_path, "road-in")
    skeleton = opening.compose(c, "")
    first = skeleton.split("\n\n")[0]
    town = c.location.name
    assert f"outside {town}" in first
    assert "buildings round about" not in first
    land = geography.land_around(worlds, c.location)
    near = [g for g in land.near if g != "coast"]
    if near:
        assert near[0] in first, (near, first)
    assert len(opening_prose.physical_detail(first)) >= 3
    material, _allowed = opening_prose.material(c, opening.situation_for(c), skeleton)
    assert f"outside {town}, on the road" in material
    if land.source != "unknown":
        assert f"The land around {town}" in material


# --- the draw -----------------------------------------------------------------------------------

def _road_share(world, pc, n: int = 400) -> float:
    got = collections.Counter(
        openings.choose(world, pc, openings.rng_for(seed, "start"))[1]["id"]
        for seed in range(n))
    return sum(got[s] for s in ROAD) / n


def test_the_caravan_hand_draws_road_starts_more_than_the_thief_taker(worlds):
    """Borin is a caravan hand, and the caravan attack is written for him (six times the
    weight); Kesst, a thief-taker, draws the road only as any start. Measured at this
    commit over a thousand seeds: Borin 33–35 % road starts, Kesst 11–13 %, and a
    character with no background 18–25 % — each road start weighted as one start among
    the ones the town can host, so the road comes up in proportion and never as a habit."""
    borin = _road_share(worlds, load_pc(BORIN))
    kesst = _road_share(worlds, load_pc(KESST))
    nobody = load_pc(KESST)
    nobody.background = ""
    anyone = _road_share(worlds, nobody)
    assert borin > 2 * kesst, (borin, kesst)
    assert 0.05 <= kesst <= 0.25, kesst
    assert 0.10 <= anyone <= 0.40, anyone


# --- opens_scheme ------------------------------------------------------------------------------

def _homebrew_start(tmp_path, **changes) -> dict:
    doc = json.loads(json.dumps(openings.get("road-in")))
    doc.update(id="i1-road-in-opens-a-scheme", name="The road in, with a story", **changes)
    folder = tmp_path / "homebrew" / "openings"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "i1.json").write_text(json.dumps({"starts": [doc]}), encoding="utf-8")
    return doc


def test_opens_scheme_opens_its_scheme(worlds, tmp_path):
    """The owner's answer to Q22: "The lost thing" opens on day two at the market by its
    own criteria, "and starts may also open it". A start that names it opens it at hour
    zero through `schemes.open_scheme` — slots, cards and grants filled from the world as
    the day-two open would — and the instance records which door opened it. Before I1 the
    field validated and nothing read it: a start that said it opened a story and did not
    is the `open_card` bug (schemes._open_one_card) over again."""
    doc = _homebrew_start(tmp_path, opens_scheme="the-lost-thing")
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        assert openings.validate(openings.get(doc["id"])) == []
        c = cm.new_campaign("i1-scheme", seed=11, character=load_pc(BORIN),
                            world_source=str(worlds.source), start_id=doc["id"])
    assert c.start_id == doc["id"]
    inst = [i for i in c.scene.schemes if i.get("scheme") == "the-lost-thing"]
    assert len(inst) == 1
    assert inst[0]["opened_by"] == f"start:{doc['id']}"
    assert inst[0]["opened_turn"] == 0 and inst[0]["cards"]
    assert c.scene.start["opened"] == ["the-lost-thing"]


def test_a_start_naming_no_such_scheme_is_refused(tmp_path):
    """Refused with the fix named, never skipped at staging."""
    doc = json.loads(json.dumps(openings.get("road-in")))
    doc["opens_scheme"] = "the-found-thing"
    problems = openings.validate(doc)
    assert any("is not a scheme" in p and "the-lost-thing" in p for p in problems), problems


@pytest.mark.parametrize("change,named", [
    (lambda d: d["incident"][1].update({"from": "sky"}), "from is empty"),
    (lambda d: d.update(edge="The lead wagon has stopped, with $wolves in the road."),
     "$wolves is not a slot"),
])
def test_the_road_document_rules_name_the_fix(change, named):
    """The two rules the road documents added: where a fight's attackers come from, and a
    `$slot` in the opening's text that no step brings in (it would reach the page as a
    dollar sign)."""
    doc = json.loads(json.dumps(openings.get("road-caravan-attack")))
    assert openings.validate(doc) == []
    change(doc)
    problems = openings.validate(doc)
    assert any(named in p for p in problems), problems


def test_group_phrases_are_said_in_words():
    """The incident's people as the opening says them: number words, English plurals, the
    bestiary's index order and size prefix undone."""
    assert openings.group_phrase("the wolf", 2) == "two wolves"
    assert openings.group_phrase("the raider", 1) == "a raider"
    assert openings.group_phrase("the adolescent wolf", 1) == "an adolescent wolf"
    assert openings.creature_noun("Dog, Riding") == "riding dog"
    assert openings.creature_noun("Medium Giant Scorpion") == "giant scorpion"
    assert openings.creature_noun("Large Scorpion") == "large scorpion"
    assert openings.group_phrase("the harpy", 3) == "three harpies"
