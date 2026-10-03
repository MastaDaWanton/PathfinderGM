"""The round trip (gm/beat_verify.py, gm/checks/beat_verified.py): the finished beat read
back into the engine's vocabulary by a model, and compared with the engine in code.

The owner, 2026-10-03: "we cant really depend i think on just layering mechanical
detection logic on top this will be an endless loop". The regex checks this replaces each
read English with their own patterns, and each new phrasing needed new code: "You move
toward the anvil" was a walk out of the smithy, "The clerk's eyes drop to the floor" a man
down. These tests replay the model's ACTUAL answers on the owner's beats — recorded by
tools/beat_verify_bench.py with gemma-4-12B on 2026-10-03 — so what is pinned is the
comparison code, not a hope about the model. The bench's numbers are in docs/beat-verify.md.
"""
from __future__ import annotations

import json

import pytest

from gm import beat_verify as bv
from tests.beat_verify import gold as G


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _chat(*replies):
    """A chat that answers in order; records what it was asked."""
    queue = [r if isinstance(r, str) else json.dumps(r) for r in replies]
    asked: list = []

    def chat(messages, *a, **k):
        asked.append((messages, k))
        return _Reply(queue.pop(0) if queue else '{"answer": "yes"}')

    chat.asked = asked
    return chat


# The model's own answers, as recorded on the first bench run (gemma-4-12B, temperature 0).
RECORDED = {
    "anvil": {"player_ends_at": {"place": "the smithy", "quote": "You move toward the anvil, the massive block of iron standing like a monument in the center of the room."}, "changed_hands": [{"item": "crate", "from": "someone not listed", "to": "the floor", "quote": "The heavy crate meets the dirt with a dull thud"}], "trades": [], "harmed": [], "arrived": [], "left": [], "time_of_day": {"part": "unstated", "quote": ""}},
    "finalized": {"player_ends_at": {"place": "the smithy", "quote": "You stand on the threshold between the heavy labor of the forge and the open road ahead."}, "changed_hands": [{"item": "crate", "from": "pc", "to": "c13", "quote": "Korvu takes the crate with a grunt"}], "trades": [{"item": "something else", "seller": "pc", "buyer": "c13", "settled": True, "quote": "The transaction is finalized."}], "harmed": [], "arrived": [], "left": [], "time_of_day": {"part": "dawn", "quote": "the pre-dawn light is just beginning to bleed into the gray"}},
    "eyes-drop": {"player_ends_at": {"place": "the counting house", "quote": ""}, "changed_hands": [], "trades": [], "harmed": [], "arrived": [], "left": [], "time_of_day": {"part": "unstated", "quote": ""}},
    "street": {"player_ends_at": {"place": "somewhere not listed", "quote": "move through the pre-dawn gloom of the district"}, "changed_hands": [{"item": "brunt of the weight", "from": "pc", "to": "the floor", "quote": "the Brunt of the Weight is left behind on the dirt floor of the forge"}], "trades": [], "harmed": [], "arrived": [], "left": [], "time_of_day": {"part": "dawn", "quote": "pre-dawn gloom"}},
    "payment-is-yours": {"player_ends_at": {"place": "the counting house", "quote": ""}, "changed_hands": [{"item": "crate", "from": "pc", "to": "c12", "quote": "The crate is mine."}, {"item": "something else", "from": "pc", "to": "c12", "quote": "He takes the paper back from you"}], "trades": [{"item": "crate", "seller": "pc", "buyer": "c12", "settled": True, "quote": "the transaction is finalized in the eyes of the guild"}], "harmed": [], "arrived": [], "left": [], "time_of_day": {"part": "unstated", "quote": ""}},
    "burning-hands": {"player_ends_at": {"place": "the approach", "quote": ""}, "changed_hands": [], "trades": [], "harmed": [{"who": "c8", "how": "hurt", "quote": "the heat licks across his face and the heavy leather of his tunic"}, {"who": "c8", "how": "hurt", "quote": "his hands clutching his scorched arms"}], "arrived": [], "left": [], "time_of_day": {"part": "unstated", "quote": ""}},
    "outskirts": {"player_ends_at": {"place": "somewhere not listed", "quote": "You are now on the outskirts, where the immediate reach of Vormoor's presence fades into the distance."}, "changed_hands": [], "trades": [], "harmed": [], "arrived": [], "left": [], "time_of_day": {"part": "unstated", "quote": ""}},
    "first-hint-of-dawn": {"player_ends_at": {"place": "the counting house", "quote": ""}, "changed_hands": [{"item": "pouch", "from": "pc", "to": "nobody", "quote": "You pull the drawstring and tip the contents into your hand."}], "trades": [], "harmed": [], "arrived": [], "left": [], "time_of_day": {"part": "dawn", "quote": "the first hint of dawn is beginning to grey the edges of the windows"}},
    "midnight-air": {"player_ends_at": {"place": "the market", "quote": ""}, "changed_hands": [], "trades": [], "harmed": [], "arrived": [], "left": [], "time_of_day": {"part": "night", "quote": "under the weight of the midnight air"}},
    "counter-and-go": {"player_ends_at": {"place": "the counting house", "quote": "into the counting house"}, "changed_hands": [{"item": "crate", "from": "pc", "to": "c12", "quote": "he takes it from your hands"}], "trades": [{"item": "crate", "seller": "pc", "buyer": "c12", "settled": True, "quote": "the exchange"}], "harmed": [], "arrived": [], "left": [], "time_of_day": {"part": "unstated", "quote": ""}},
}


def _diff(beat_id: str):
    beat = G.by_id(beat_id)
    facts = G.facts(beat)
    reading = bv.read(beat["text"], facts, model="stub", chat=_chat(RECORDED[beat_id]))
    assert not reading.error
    return reading, bv.diff(reading.claims, facts, beat["text"])


@pytest.mark.parametrize("beat_id,alarms", [
    # The six known cases of the 2026-10-03 live check, as the engine contradicts them.
    ("finalized", {"trade", "hands", "hour"}),
    ("street", {"move", "hands", "hour"}),
    ("payment-is-yours", {"trade"}),
    ("burning-hands", {"harm"}),
    ("outskirts", {"move"}),
    ("first-hint-of-dawn", {"hour"}),
    ("counter-and-go", {"hands"}),
])
def test_the_known_cases_raise_what_the_engine_contradicts(beat_id, alarms):
    """The live check of 2026-10-03 found each of these by hand: a refused sale settled on
    the page ("The transaction is finalized"), a crate the engine kept handed to the
    smith, "the pre-dawn light" at 01:28, a walk out into the street the engine refused, a
    man burned by a spell that reached nobody. The model's recorded reading of each,
    compared in code, raises exactly those categories."""
    _r, found = _diff(beat_id)
    assert {d.category for d in found if d.kind == "contradiction"} == alarms


@pytest.mark.parametrize("beat_id", ["anvil", "eyes-drop", "midnight-air"])
def test_the_beats_the_regex_misread_raise_nothing(beat_id):
    """"You move toward the anvil" was cut as a refused journey (live check, item 1), and
    "The clerk's eyes drop to the floor" was read as the clerk down or dead (playtest item
    20) — both by a pattern over English. Read back, the anvil is a walk inside the smithy
    (the model answered the smithy) and the clerk is nobody harmed; midnight at clock 0 is
    the truth."""
    _r, found = _diff(beat_id)
    assert found == []


def test_a_claim_quoted_from_speech_is_dropped():
    """"'The payment is yours. The crate is mine.'" is the clerk talking: the model
    reported the crate as handed to him on the strength of it, and the quote check — the
    narration only, speech blanked — dropped the claim. A character may say anything."""
    reading, _f = _diff("payment-is-yours")
    dropped = [c for c in reading.dropped if c.category == "hands"]
    assert [c.quote for c in dropped] == ["The crate is mine."]
    assert "not the page's narration" in dropped[0].why


def test_a_quote_too_short_to_say_anything_is_dropped():
    """"the exchange", quoted from "You turn your back on the man and the exchange", was
    read as a settled sale on the first bench run (counter-and-go) — the false alarm a
    one-word trigger always gives. Two words cannot carry a claim; the claim is dropped."""
    reading, found = _diff("counter-and-go")
    assert not [d for d in found if d.category == "trade"]
    assert any(c.quote == "the exchange" and "too short" in c.why for c in reading.dropped)


def test_a_quote_that_is_not_on_the_page_is_dropped():
    beat = G.by_id("eyes-drop")
    facts = G.facts(beat)
    answer = dict(RECORDED["eyes-drop"], harmed=[
        {"who": "c12", "how": "down", "quote": "the clerk collapses to the floor"}])
    reading = bv.read(beat["text"], facts, model="stub", chat=_chat(answer))
    assert reading.claims == [] and reading.dropped[0].category == "harm"
    assert bv.diff(reading.claims, facts, beat["text"]) == []


def test_the_same_claim_twice_is_one_claim():
    """The burned man was reported hurt twice, once per sentence that burned him; the
    first bench run scored the second as a false positive. Code keeps the first."""
    reading, found = _diff("burning-hands")
    assert len([c for c in reading.claims if c.category == "harm"]) == 1
    assert len(found) == 1


def test_every_slot_is_an_enum_the_engine_supplies():
    """Ollama enforced required properties, enums, booleans and maxItems inside arrays of
    objects 6 of 6 for gemma-4-12B and for Osmosis-Structure-0.6B (probe of 2026-10-03,
    docs/beat-verify.md) — so every slot is one, built from the facts at call time."""
    facts = G.facts(G.by_id("finalized"))
    s = bv.schema(facts)
    assert set(s["required"]) == set(s["properties"])
    where = s["properties"]["player_ends_at"]["properties"]["place"]["enum"]
    assert "the smithy" in where and bv.UNLISTED_PLACE in where
    hands = s["properties"]["changed_hands"]["items"]
    assert set(hands["required"]) == {"item", "from", "to", "quote"}
    assert set(hands["properties"]["item"]["enum"]) == {"pouch", "crate", bv.OTHER_THING}
    assert set(hands["properties"]["to"]["enum"]) == {"pc", "c13", bv.NEW_PERSON, bv.FLOOR,
                                                      bv.NOBODY}


def test_a_value_off_the_engines_list_is_dropped():
    """A hosted provider does not enforce the schema: a place nobody knows is no claim."""
    beat = G.by_id("anvil")
    facts = G.facts(beat)
    answer = dict(RECORDED["anvil"], changed_hands=[
        {"item": "anvil", "from": "pc", "to": "c13",
         "quote": "You move toward the anvil, the massive block"}])
    reading = bv.read(beat["text"], facts, model="stub", chat=_chat(answer))
    assert not reading.claims and "engine's value" in reading.dropped[0].why


def test_a_failed_read_is_an_error_and_no_claim():
    def broken(*a, **k):
        raise ConnectionError("ollama is down")

    beat = G.by_id("finalized")
    reading = bv.read(beat["text"], G.facts(beat), model="stub", chat=broken)
    assert reading.claims == [] and "ConnectionError" in reading.error


# --- the second read -------------------------------------------------------------------

def test_a_contradiction_the_second_read_does_not_confirm_costs_nothing():
    """The narrow question about one sentence is asked before a contradiction costs a
    word; a "no" refutes it. The hour is not asked: "the pre-dawn light" is not "dawn",
    and a second read that grades the reader's word refused that true alarm (probe of
    2026-10-03)."""
    _r, found = _diff("finalized")
    beat = G.by_id("finalized")
    chat = _chat({"answer": "yes"}, {"answer": "no"})
    kept, refuted, _s = bv.confirm(found, beat["text"], G.facts(beat), model="stub",
                                   chat=chat)
    assert {d.category for d in kept} == {"hands", "hour"}
    assert [d.category for d in refuted] == ["trade"]
    assert len(chat.asked) == 2
    question = chat.asked[0][0][-1]["content"]
    assert "Question: Does this sentence say" in question


def test_a_second_read_that_fails_keeps_the_first_reads_answer():
    _r, found = _diff("finalized")
    beat = G.by_id("finalized")

    def broken(*a, **k):
        raise ConnectionError("down")

    kept, refuted, _s = bv.confirm(found, beat["text"], G.facts(beat), model="stub",
                                   chat=broken)
    assert len(kept) == len(found) and not refuted


# --- the cache ---------------------------------------------------------------------------

def test_a_beat_is_read_once_and_a_rewrite_reads_only_its_new_sentence():
    """The repair asks the member again after each rewrite and again before the backstops
    (`GMAgent._repair_sentences`); reading the whole beat each time would cost a call per
    ask. Unchanged sentences keep their claims; a rewritten one is read alone."""
    bv.clear_cache()
    beat = G.by_id("finalized")
    facts = G.facts(beat)
    chat = _chat(RECORDED["finalized"], {"player_ends_at": {"place": "the smithy",
                                                            "quote": ""},
                                         "changed_hands": [], "trades": [], "harmed": [],
                                         "arrived": [], "left": [],
                                         "time_of_day": {"part": "unstated", "quote": ""}})
    first = bv.read_beat(beat["text"], facts, model="stub", chat=chat)
    again = bv.read_beat(beat["text"], facts, model="stub", chat=chat)
    assert len(chat.asked) == 1 and len(again.claims) == len(first.claims)
    fixed = beat["text"].replace("The transaction is finalized.",
                                 "The smith shakes his head at the shut counter.")
    after = bv.read_beat(fixed, facts, model="stub", chat=chat)
    assert len(chat.asked) == 2
    assert "shakes his head" in chat.asked[1][0][-1]["content"]
    assert "Korvu takes the crate" not in chat.asked[1][0][-1]["content"]
    assert not [c for c in after.claims if c.category == "trade"]
    bv.clear_cache()


# --- the bench file itself --------------------------------------------------------------

def test_the_bench_labels_only_values_the_engine_offers():
    """A gold label the schema could never produce would score as a miss forever."""
    for beat in G.GOLD:
        facts = G.facts(beat)
        allowed = {"place": set(bv._places(facts)), "item": set(facts.things) | {bv.OTHER_THING},
                   "from": set(bv._holders(facts)), "to": set(bv._holders(facts)),
                   "seller": set(bv._who(facts)), "buyer": set(bv._who(facts)),
                   "who": set(bv._who(facts)), "how": set(bv.HOW), "part": set(bv.PARTS)}
        for claim in beat["claims"]:
            for k, v in claim.items():
                if k in allowed:
                    for one in (v if isinstance(v, list) else [v]):
                        assert one in allowed[k], (beat["id"], k, one)
        for d in beat["text"]:
            pass
        assert beat["start"] in bv._places(facts)
