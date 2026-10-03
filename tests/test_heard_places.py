"""Places heard of: named by a person, made a place on the first visit, where they said.

The owner's ruling of 2026-10-03 keeps places creatable ("places must be creatable for
example peoples houses"); what was missing was the middle state. In the owner's items
save the clerk said "make your exit through the side door, past the smithy" and nothing
wrote the smithy down; the player's "head for the side door" then had the planner found
*the smithy* off wherever it could after a refused travel. The docks man's "the western
warehouses" was never recorded at all. Inform's Epistemology (seen / familiar), Skyrim's
grey marker for a place you were told of, and Morrowind's journal directions relative to
known landmarks are the model (rules/heard_places.py).
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from gm import judgement
from rules import heard_places
from rules import places as places_mod
from world import loader

import _a_truth

PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")
ZHIL = PANGRELLA.get("6953424c8a82")
COUNTING = "6953424c8a82~urban:the-counting-house"
MARKET = "6953424c8a82~urban:the-market"
DOCKS = "6953424c8a82~urban:the-docks"

CLERK = ("I suggest you make your exit through the side door, past the smithy. It leads "
         "straight to the main thoroughfare.")
DOCKS_MAN = ("The master of the docks—a man with more coin than sense—is currently "
             "looking for someone with the nerve to move the shipments from the western "
             "warehouses before the tide turns.")


def _known(at):
    return places_mod.for_scene(ZHIL, at)


def _agent(at):
    agent, _ = _a_truth.scene_at(at, world=PANGRELLA, location=ZHIL)
    return agent


# --- what a line names ---------------------------------------------------------------------

def test_the_clerks_smithy_is_heard_of_off_the_counting_house():
    """"through the side door, past the smithy", said in the counting house: the smithy is
    not on Zhilvarnia's map, and the side door is the counting house's own."""
    got = heard_places.heard_in(CLERK, _known(COUNTING), COUNTING)
    assert got == [{"name": "the smithy", "kind": "smithy", "landmark": COUNTING}]


def test_the_western_warehouses_are_heard_of_and_the_master_of_the_docks_is_a_man():
    got = heard_places.heard_in(DOCKS_MAN, _known(MARKET), MARKET)
    assert got == [{"name": "the western warehouses", "kind": "warehouses", "landmark": ""}]


@pytest.mark.parametrize("line, want", [
    ("There is a tannery out past the docks.",
     [{"name": "the tannery", "kind": "tannery", "landmark": DOCKS}]),
    ("You will find the harbourmaster at his office by the docks.",
     [{"name": "the harbourmaster's office", "kind": "", "landmark": DOCKS}]),
])
def test_a_landmark_the_speaker_gives_is_kept(line, want):
    assert heard_places.heard_in(line, _known(MARKET), MARKET) == want


@pytest.mark.parametrize("line", [
    "I know a man in the counting house.",              # on the map already
    "Marra's house is three streets over.",             # somebody's house: call_on's
    "The house of the clerk is by the well.",
    "Try the tavern, or the docks at dawn.",
])
def test_known_places_and_peoples_houses_are_not_heard_of(line):
    assert heard_places.heard_in(line, _known(MARKET), MARKET) == []


def test_a_record_is_kept_once_and_gains_a_landmark_later():
    s = SimpleNamespace(location_id="6953424c8a82", heard_places=[])
    heard_places.record(s, {"name": "the tannery", "kind": "tannery", "landmark": ""})
    heard_places.record(s, {"name": "The Tannery", "kind": "tannery", "landmark": DOCKS})
    assert len(s.heard_places) == 1 and s.heard_places[0]["landmark"] == DOCKS


def test_a_town_holds_only_so_many_heard_of_places():
    s = SimpleNamespace(location_id="6953424c8a82", heard_places=[])
    for n in range(heard_places.MOST_HEARD + 3):
        heard_places.record(s, {"name": f"the yard {n}", "kind": "", "landmark": ""})
    assert len(s.heard_places) == heard_places.MOST_HEARD
    assert s.heard_places[0]["name"] == "the yard 3"


# --- going there ---------------------------------------------------------------------------

def test_going_to_the_smithy_founds_it_where_the_clerk_said_and_stands_you_in_it():
    """The items save's turn, as it should have gone: the clerk named the smithy, the
    player goes there, and the smithy is a place off the counting house with the party in
    it — then a place for every later turn, so a second visit founds nothing."""
    agent = _agent(COUNTING)
    e = agent.engine
    heard_places.record(e.scene, heard_places.heard_in(CLERK, e.places(), COUNTING)[0],
                        said_by="c12", line=CLERK)
    known = tuple(e.places()) + tuple(e.open_ground())
    plan = judgement.go_to_heard_place([{"op": "narrate_only"}], "I go to the smithy.",
                                       e.scene, known)
    assert [r["op"] for r in plan] == ["narrate_only", "found", "travel"]
    assert plan[1]["params"] == {"name": "the smithy", "kind": "smithy",
                                 "parent": "the counting house"}
    e.run(e.validate(plan))
    here = e.here()
    assert here.name == "the smithy" and here.parent == COUNTING
    assert heard_places.of_here(e.scene, e.places()) == []
    again = judgement.go_to_heard_place([{"op": "narrate_only"}], "I go to the smithy.",
                                        e.scene, tuple(e.places()))
    assert [r["op"] for r in again] == ["narrate_only"]


def test_the_planners_own_found_takes_the_speakers_landmark():
    """The model may found it itself, with no landmark: `fill_found_parent` gives it the
    one the speaker said, and keeps it by name though it is where the party stands — the
    engine's unnamed default would climb out of the counting house to the street."""
    agent = _agent(COUNTING)
    e = agent.engine
    heard_places.record(e.scene, heard_places.heard_in(CLERK, e.places(), COUNTING)[0])
    plan = judgement.fill_found_parent(
        [{"op": "found", "params": {"name": "the smithy", "kind": "smithy"}}],
        "I head out to the smithy.", e.scene, PANGRELLA)
    assert plan[0]["params"]["parent"] == "the counting house"


def test_a_question_about_it_goes_nowhere():
    agent = _agent(COUNTING)
    e = agent.engine
    heard_places.record(e.scene, heard_places.heard_in(CLERK, e.places(), COUNTING)[0])
    plan = judgement.go_to_heard_place([{"op": "narrate_only"}],
                                       "Where is the smithy?", e.scene, tuple(e.places()))
    assert plan == [{"op": "narrate_only"}]


# --- the beat that records it, the save that keeps it, the brief that shows it -------------

def test_the_beat_records_an_npcs_place_and_never_the_players():
    from play.aftermath import places_heard

    agent = _agent(COUNTING)
    e = agent.engine
    from rules.bestiary import instantiate

    clerk = instantiate("guildhand", scene=e.scene, name="the clerk of the counting house")
    e.scene.add(clerk)
    ctx = SimpleNamespace(scene=e.scene, turn=40, campaign=SimpleNamespace(engine=lambda: e),
                          said=[{"who": clerk.ref, "to": "you", "line": CLERK},
                                {"who": "you", "to": clerk.ref,
                                 "line": "I'll try the tannery past the docks."}])
    rows = places_heard.step(ctx)
    assert [r["name"] for r in rows] == ["the smithy"]
    assert e.scene.heard_places[0]["from"] == clerk.ref


def test_heard_places_survive_a_save_and_a_load(tmp_path):
    """Nothing derives them — a conversation made them — so a reload that dropped them
    would forget every direction the player was given."""
    from django.test import override_settings

    from play import campaign as cm
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=tmp_path):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.heard_places.append({"name": "the smithy", "kind": "smithy",
                                     "landmark": COUNTING, "from": "c12", "line": CLERK,
                                     "location": c.scene.location_id, "turn": 3})
        path = c.save()
        cm._LIVE.clear()
        again = cm.Campaign.load(path)
    assert again.scene.heard_places == c.scene.heard_places


def test_the_brief_names_it_with_its_landmark_and_speaker():
    from gm.brief import heard_places as brief

    agent = _agent(COUNTING)
    e = agent.engine
    from rules.bestiary import instantiate

    clerk = instantiate("guildhand", scene=e.scene, name="the clerk")
    e.scene.add(clerk)
    heard_places.record(e.scene, heard_places.heard_in(CLERK, e.places(), COUNTING)[0],
                        said_by=clerk.ref)
    ctx = SimpleNamespace(scene=e.scene, known=tuple(e.places()))
    text, facts = brief.section(ctx)
    assert "the smithy — off the counting house, as the clerk told it" in text
    assert facts["heard_places"][0]["landmark"] == COUNTING
