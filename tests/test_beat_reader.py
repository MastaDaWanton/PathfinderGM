"""The beat reader's checks: every answer the model gives is held to what the engine owns,
and one that fails is dropped with the reason — never repaired, never guessed round
(gm/beat_reader.py, docs/beat-reader.md).

The model's replies are stubbed (tests/beat_reader/stub.py) so each test pins the CODE's
side: the schema it asks with, the checks it applies, what reaches the engine. How well
the model answers is the bench's to measure (tools/beat_reader_bench.py), on the owner's
own beats.
"""
from __future__ import annotations

import json

import pytest

from gm import beat_reader
from play.aftermath import seen_people, speaker_real
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from tests.beat_reader import stub
from world import loader

PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")
ZHIL = "6953424c8a82"
MARKET = f"{ZHIL}~urban:the-market"


def _market(*names):
    s = Scene(location_id=ZHIL)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=2), world=PANGRELLA)
    e.place_party(MARKET)
    refs = [s.add(instantiate("guildhand", scene=s, name=n)).ref for n in names]
    return s, e, refs


# --- the schema: only what the sampler enforces --------------------------------------------

def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_the_schemas_use_only_constructs_the_sampler_was_measured_to_hold():
    """Probed 2026-10-03 on gemma-4-12B, 6 runs each, every prompt asking for what the
    schema forbade: nested objects of required enums, a different enum per property,
    arrays of objects with maxItems and item enums — all 6/6. `contains` and
    `prefixItems` held 0/6 (memory `ollama-schema-enforcement`), so neither is used, nor
    anything else unprobed."""
    probed = {"type", "properties", "required", "enum", "items", "maxItems"}
    people = beat_reader.people_schema(["m1", "m2"], ["pc", "c1"], ["q1"], ["c1"],
                                       away=["c7"])
    places = beat_reader.places_schema(["q1"], ["the market", "the docks"])
    for schema in (people, places):
        for node in _walk(schema):
            if "type" in node or "enum" in node:
                assert set(node) <= probed, set(node) - probed
    # Each mention may only be "the same as" an EARLIER mention — a closed choice.
    assert "same as m1" in people["properties"]["m2"]["enum"]
    assert not [e for e in people["properties"]["m1"]["enum"] if e.startswith("same as")]
    # The people known elsewhere are a choice for a mention and for "arrived", not a
    # speaker of a line here.
    assert "c7" in people["properties"]["m1"]["enum"]
    assert "c7" not in people["properties"]["q1"]["properties"]["by"]["enum"]


# --- the people call's answers, checked -----------------------------------------------------

def test_a_newcomers_words_must_be_the_pages_own():
    """LangExtract's rule (an extraction not located in the source is not kept): words the
    model wrote for a newcomer that are not in the narration are dropped, with the reason,
    and the newcomer is recorded under the marked words the reader called new."""
    s, e, _ = _market()
    text = "A woman with a basket stops at the stall."
    reading = stub.read(text, s, engine=e, who={"A woman": "new"},
                        new=[("A woman", "here", "fishwife with a red shawl")])
    (n,) = reading.newcomers
    assert n.words == "woman" and n.where == "here"
    assert any(d["why"] == "the words are not the narration's" for d in reading.dropped)


def test_a_mention_the_same_as_a_listed_person_is_that_person():
    """Measured on the bench: "A man in a stained leather harness, a passing carter" came
    back m5 "same as m4", m4 being the carter already listed. It is the carter."""
    s, e, (carter,) = _market("passing carter")
    text = "A man in a stained leather harness, a passing carter, leads his cart past."
    reading = stub.read(text, s, engine=e, who={"A man": carter,
                                                "a passing carter": "same as A man"})
    assert [m.ref for m in reading.mentions] == [carter, carter]
    assert not reading.newcomers


def test_a_line_given_to_a_mention_that_is_nobody_books_nobody():
    s, e, _ = _market()
    text = "The crowd mutters. 'Move along,' somebody calls."
    reading = stub.read(text, s, engine=e, who={"The crowd": "nobody"},
                        lines={"Move along": ("The crowd", "you")})
    (ln,) = reading.lines
    assert ln.by == beat_reader.NOBODY
    said: list = []
    speaker_real.step(stub.ctx(s, reading, text=text, engine=e, said=said))
    assert said == []


def test_an_arrival_the_passage_never_mentions_is_the_models_not_the_pages():
    """"arrived" may name only somebody known elsewhere whom a mention of THIS passage was
    answered as; anything else is dropped, and nobody walks in."""
    s, e, _ = _market()
    gone = instantiate("guildhand", scene=s, name="the net mender")
    s.arrive(gone, place_id=f"{ZHIL}~urban:the-docks")
    text = "The square is quiet. A boy sleeps by the well."
    reading = stub.read(text, s, engine=e, who={"A boy": "nobody"}, arrived=[gone.ref])
    assert reading.arrived == []
    assert any(d.get("arrived") == gone.ref for d in reading.dropped)
    seen_people.step(stub.ctx(s, reading, text=text, engine=e, world=PANGRELLA))
    assert gone.ref not in s.actors


# --- names the page gives, through the engine's checks -------------------------------------

@pytest.mark.parametrize("name, taken, why", [
    ("Caspian Tidestone", True, ""),
    ("Korvu", False, "a people of this world"),     # item 14: "a man named Korvu"
    ("Gorm", False, "answers to it"),               # the Borin case, 2026-09-27
])
def test_a_name_read_off_the_page_is_taken_only_through_the_checks(name, taken, why):
    """Measured 2026-10-03 (item 14): "The laborer—a man named Korvu" renamed c11 after
    one of the world's peoples, and on 2026-09-27 a thug was renamed "Borin" beside Borin
    Lyraxys. The reader reads the name; `beat_reader.name_refusal` holds it to the
    engine: nobody else here answers to it, it is no people of the world, and the person
    has no proper name yet."""
    s, e, (sergeant, gorm) = _market("the sergeant of the watch", "Gorm Vesper")
    s.actors[gorm].true_name = "Gorm Vesper"
    text = f"The sergeant shrugs. '{name},' he says. 'Now move along.'"
    reading = stub.read(text, s, engine=e, who={"The sergeant": sergeant},
                        lines={name: (sergeant, "you")}, names={sergeant: name})
    rows = seen_people.step(stub.ctx(s, reading, text=text, engine=e, world=PANGRELLA))
    (row,) = [r for r in rows if r["kind"] == "name-read"]
    assert row["taken"] is taken and why in row.get("why", "")
    assert (s.actors[sergeant].name == name) is taken


def test_a_name_not_written_on_the_page_is_dropped():
    s, e, (sergeant,) = _market("the sergeant of the watch")
    text = "The sergeant shrugs and says nothing of himself."
    reading = stub.read(text, s, engine=e, who={"The sergeant": sergeant},
                        names={sergeant: "Caspian Tidestone"})
    assert reading.names == []
    assert any(d.get("why") == "not a name as the page writes it" for d in reading.dropped)


# --- when the call fails -------------------------------------------------------------------

def test_a_failed_read_harvests_nothing_and_every_step_says_so():
    """The owner: "this will be an endless loop" — the patterns the reader replaced do
    not come back when it fails. No newcomer, no booked line, no place; one
    `beat-unread` row per step, with the error."""
    from play.aftermath import mentioned_elsewhere, places_heard

    s, e, _ = _market()
    text = "A man by the stall looks up. 'Try the forge by the docks,' he says."
    said: list = []
    reading = stub.read(text, s, engine=e, fail="people")
    assert reading.asked and not reading.read and reading.error.startswith("people:")
    before = (set(s.actors), dict(s.population or {}))
    rows = seen_people.step(stub.ctx(s, reading, text=text, engine=e, said=said))
    rows += speaker_real.step(stub.ctx(s, reading, text=text, engine=e, said=said))
    rows += places_heard.step(stub.ctx(s, reading, text=text, engine=e, said=said,
                                       stage="beat"))
    rows += mentioned_elsewhere.step(stub.ctx(s, reading, text=text, engine=e, said=said,
                                              stage="beat"))
    assert (set(s.actors), dict(s.population or {})) == before and said == []
    assert s.heard_places == []
    assert [r["step"] for r in rows if r["kind"] == "beat-unread"] == \
        ["seen_people", "speaker_real"]


def test_a_failed_places_call_keeps_the_people_and_logs_the_places_unread():
    s, e, (man,) = _market("man by the stall")
    text = "The man by the stall looks up. 'Try the forge by the docks,' he says."
    reading = stub.read(text, s, engine=e, who={"The man": man},
                        lines={"Try the forge": (man, "you")}, fail="places")
    assert reading.read and not reading.places_read and "places:" in reading.error
    from play.aftermath import places_heard

    rows = places_heard.step(stub.ctx(s, reading, text=text, engine=e, stage="beat"))
    assert rows == [reading.unread_row("places_heard")]


def test_the_reader_is_off_in_the_suite_unless_a_test_asks():
    """Off by default here (tests/conftest.py), as the interpreter and the labeller are: a
    turn test scripting the model's replies would have them spent. A `chat` passed in
    asks for a reading regardless."""
    s, e, _ = _market()
    calls: list = []
    off = beat_reader.read("A man waves. 'You there!'", s, engine=e)
    assert not off.asked
    on = stub.read("A man waves. 'You there!'", s, engine=e, calls=calls,
                   who={"A man": "new"}, new=[("A man", "here", "man")])
    assert on.read and [k for k, *_ in calls] == ["places", "people"] or \
        [k for k, *_ in calls] == ["people", "places"]


def test_the_reading_row_says_what_was_read_and_what_was_dropped():
    s, e, _ = _market()
    text = "A woman with a basket stops at the stall."
    reading = stub.read(text, s, engine=e, who={"A woman": "new"},
                        new=[("A woman", "here", "woman with a basket")])
    row = reading.as_log()
    assert row["kind"] == "beat-reading" and row["read"] is True
    assert row["newcomers"] == [{"words": "woman with a basket", "where": "here",
                                 "mentions": ["m1"]}]
    json.dumps(row)                                  # a turn-log row is plain data


def test_a_possessive_newcomer_is_the_person_not_their_name():
    """Measured live on the merged structured-turn branch, 2026-10-03: "the steady,
    rhythmic thud of a worker's mallet against a frame" made a person called "worker's"
    (c15). The 's is grammar, a closed form: the newcomer is "worker"."""
    s, e, _ = _market()
    text = "The only sound is the steady, rhythmic thud of a worker's mallet against a frame."
    ids = stub._mention_ids(text, s)
    phrase = next(p for p in ids if "worker" in p)
    reading = stub.read(text, s, engine=e, who={phrase: "new"}, new=[(phrase, "here", "")])
    (n,) = reading.newcomers
    assert n.words == "worker"
