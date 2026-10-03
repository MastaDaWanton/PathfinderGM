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


def _speaker(e, name="the clerk of the counting house"):
    from rules.bestiary import instantiate

    who = instantiate("guildhand", scene=e.scene, name=name)
    e.scene.add(who)
    return who.ref


def _heard(e, line: str, ref: str, places=(), placed=(), turn: int = 40):
    """One NPC line in a beat, the beat reader's places answer for it (stubbed with what a
    careful reader says: tests/beat_reader/stub.py), and `places_heard` applying it — the
    path a turn takes since 2026-10-03. The places used to be read out of the line by
    `heard_places.heard_in`'s patterns; the cases below are the ones it was measured on,
    and they now pin what the engine's checks keep of the reader's answer."""
    from play.aftermath import places_heard
    from tests.beat_reader import stub

    text = f"The speaker leans in. '{line}'"
    said = [{"who": ref, "to": "you", "line": line}]
    prefix = " ".join(line.split()[:3])
    reading = stub.read(text, e.scene, engine=e, said=said, lines={prefix: (ref, "you")},
                        places=[(prefix, *p) for p in places])
    ctx = stub.ctx(e.scene, reading, text=text, engine=e, said=said, turn=turn,
                   stage="beat")
    return places_heard.step(ctx), reading


# --- what a line names, read by the reader and checked by the engine ----------------------

def test_the_clerks_smithy_is_heard_of_off_the_counting_house():
    """"through the side door, past the smithy", said in the counting house: the smithy is
    not on Zhilvarnia's map, and the side door is the counting house's own."""
    e = _agent(COUNTING).engine
    clerk = _speaker(e)
    _heard(e, CLERK, clerk, places=[("the smithy", "smithy", "where the speaker is")])
    (got,) = e.scene.heard_places
    assert (got["name"], got["kind"], got["landmark"], got["from"]) == \
        ("the smithy", "smithy", COUNTING, clerk)


def test_the_western_warehouses_are_heard_of_by_the_line_that_names_them():
    """Measured on the items save: the docks man's "the western warehouses" was never
    recorded. Said in a line, it is; with no landmark the speaker gave, it has none."""
    e = _agent(MARKET).engine
    man = _speaker(e, "the man on the stool")
    line = ("There's work moving the shipments from the western warehouses before the "
            "tide turns.")
    _heard(e, line, man, places=[("the western warehouses", "warehouses", "none")])
    (got,) = e.scene.heard_places
    assert (got["name"], got["kind"], got["landmark"]) == \
        ("the western warehouses", "warehouses", "")


@pytest.mark.parametrize("line, place, want", [
    ("There is a tannery out past the docks.", ("a tannery", "tannery", "the docks"),
     ("the tannery", "tannery", DOCKS)),
    ("You will find the harbourmaster at his office by the docks.",
     ("his office", "other", "the docks"), ("his office", "", DOCKS)),
])
def test_a_landmark_the_speaker_gives_is_kept(line, place, want):
    e = _agent(MARKET).engine
    _heard(e, line, _speaker(e), places=[place])
    (got,) = e.scene.heard_places
    assert (got["name"], got["kind"], got["landmark"]) == want


@pytest.mark.parametrize("line, place, why", [
    ("I know a man in the counting house.",
     ("the counting house", "counting house", "none"), "on the map already"),
    ("Try the tavern, or the docks at dawn.", ("the tavern", "tavern", "none"),
     "on the map already"),
    ("Marra's house is three streets over.", ("Marra's house", "house", "none"),
     "somebody's house"),
    ("Ask at the guild about it.", ("the tannery", "tannery", "none"),
     "the words are not the speaker's"),
])
def test_what_the_engine_refuses_of_a_readers_place(line, place, why):
    """The reader's answer is checked, not trusted: a place the town has is on the map
    already; somebody's house is `call_on`'s, which founds it the first time anybody calls
    and knows whose it is; and a name not in the speaker's own words is the model's, not
    the page's (LangExtract's rule: an extraction not located in the source is not kept).
    Each refusal is a row of the reading, saying why."""
    e = _agent(MARKET).engine
    rows, reading = _heard(e, line, _speaker(e), places=[place])
    assert rows == [] and e.scene.heard_places == []
    assert any(why in d.get("why", "") for d in reading.dropped), reading.dropped


def test_one_place_told_of_twice_is_one_record_with_what_both_gave():
    """Measured live 2026-10-03: "'The Forge of the Broken Tide,' … 'Follow the main quay
    until you hit the turn for the wharf … sitting in the back of the smithy'" became TWO
    heard-of places, neither with a landmark. The reader links the second name to the
    first ("same as"), and the record keeps the proper name, the kind and the landmark."""
    from play.aftermath import places_heard
    from tests.beat_reader import stub

    e = _agent(MARKET).engine
    man = _speaker(e, "man in the heavy coat")
    text = ("He turns his head. 'The Forge of the Broken Tide,' he says. 'Follow the main "
            "quay until you hit the turn for the wharf. He's there every night, sitting in "
            "the back of the smithy.'")
    said = [{"who": man, "to": "you", "line": "The Forge of the Broken Tide,"},
            {"who": man, "to": "you", "line": "Follow the main quay until you hit the turn "
                                             "for the wharf. He's there every night, "
                                             "sitting in the back of the smithy."}]
    reading = stub.read(text, e.scene, engine=e, said=said,
                        lines={"The Forge": (man, "you"), "Follow the main": (man, "you")},
                        places=[("The Forge", "The Forge of the Broken Tide", "other",
                                 "none"),
                                ("Follow the main", "the smithy", "smithy", "the docks",
                                 "entry 1")])
    places_heard.step(stub.ctx(e.scene, reading, text=text, engine=e, said=said, turn=22,
                               stage="beat"))
    (got,) = e.scene.heard_places
    assert (got["name"], got["kind"], got["landmark"]) == \
        ("The Forge of the Broken Tide", "smithy", DOCKS)


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

SMITHY = {"name": "the smithy", "kind": "smithy", "landmark": COUNTING}


def test_going_to_the_smithy_founds_it_where_the_clerk_said_and_stands_you_in_it():
    """The items save's turn, as it should have gone: the clerk named the smithy, the
    player goes there, and the smithy is a place off the counting house with the party in
    it — then a place for every later turn, so a second visit founds nothing."""
    agent = _agent(COUNTING)
    e = agent.engine
    heard_places.record(e.scene, SMITHY, said_by="c12", line=CLERK)
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
    heard_places.record(e.scene, SMITHY)
    plan = judgement.fill_found_parent(
        [{"op": "found", "params": {"name": "the smithy", "kind": "smithy"}}],
        "I head out to the smithy.", e.scene, PANGRELLA)
    assert plan[0]["params"]["parent"] == "the counting house"


def test_a_question_about_it_goes_nowhere():
    agent = _agent(COUNTING)
    e = agent.engine
    heard_places.record(e.scene, SMITHY)
    plan = judgement.go_to_heard_place([{"op": "narrate_only"}],
                                       "Where is the smithy?", e.scene, tuple(e.places()))
    assert plan == [{"op": "narrate_only"}]


# --- the beat that records it, the save that keeps it, the brief that shows it -------------

def test_the_beat_records_an_npcs_place_and_never_the_players():
    """A place in the player's own quoted words is no NPC telling the player of one: the
    reader is shown every line, and what it takes from a line it gives to the player is
    dropped after (`beat_reader._places_from_npcs`)."""
    from play.aftermath import places_heard
    from tests.beat_reader import stub

    agent = _agent(COUNTING)
    e = agent.engine
    clerk = _speaker(e)
    text = (f"The clerk leans back. '{CLERK}' You nod. 'I'll try the tannery past the "
            f"docks,' you say.")
    said = [{"who": clerk, "to": "you", "line": CLERK}]
    reading = stub.read(text, e.scene, engine=e, said=said,
                        lines={"I suggest you": (clerk, "you"), "I'll try": ("you", clerk)},
                        places=[("I suggest you", "the smithy", "smithy",
                                 "where the speaker is"),
                                ("I'll try", "the tannery", "tannery", "the docks")])
    rows = places_heard.step(stub.ctx(e.scene, reading, text=text, engine=e, said=said,
                                      turn=40, stage="beat"))
    assert [r["name"] for r in rows] == ["the smithy"]
    assert e.scene.heard_places[0]["from"] == clerk
    assert any(d.get("why") == "not a line an NPC spoke" for d in reading.dropped)
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
    heard_places.record(e.scene, SMITHY, said_by=clerk.ref)
    ctx = SimpleNamespace(scene=e.scene, known=tuple(e.places()))
    text, facts = brief.section(ctx)
    assert "the smithy — off the counting house, as the clerk told it" in text
    assert facts["heard_places"][0]["landmark"] == COUNTING


SMITH_ANSWER = ("He's at the smithy near the west crossing. But be warned\u2014he's a grumpy "
                "man, and he does not care for strangers.")


def test_the_answer_naming_the_smithy_is_speech_and_is_heard_of():
    """Measured live: asked where a rapier could be sharpened, the man in the heavy coat
    answered with this line; `narration_in_quotes` read the "man" in "a grumpy man" as
    the speaker naming himself, cut it as narration, and the answer — and the smithy —
    never reached the page or the record. The whole description names him; a word of it
    does not. And the smithy he names is heard of, by the west crossing he gave."""
    from gm.checks.narration_in_quotes import _names_self

    assert not _names_self(SMITH_ANSWER, "man in the heavy coat")
    assert _names_self("The man in the heavy coat says nothing.", "man in the heavy coat")
    assert _names_self("Gorm Vesper watches you from their workspace.", "Gorm Vesper")
    e = _agent(MARKET).engine
    _heard(e, SMITH_ANSWER, _speaker(e, "man in the heavy coat"),
           places=[("the smithy", "smithy", "the west crossing")])
    (got,) = e.scene.heard_places
    assert (got["name"], got["kind"], got["landmark"]) == \
        ("the smithy", "smithy", "6953424c8a82~urban:the-west-crossing")
