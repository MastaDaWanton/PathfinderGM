"""The kind of place a beat is set in, read back and judged in code (gm/beat_verify.py).

The report of 2026-10-16 (a real player's 0.2.19 game, in a city market, free narrator):
"The heavy weapon whistles through the air… thudding uselessly into the wooden planks of
the deck." There is no deck in a market. Nothing read it: the only reader of a setting,
gm/checks/setting_kind.py, is a word list of a tavern's and a room's furniture (and is
not to grow — the owner's direction, models read and code validates), and the read-back
had no slot for what kind of place a beat describes.

Now a model answers, sentence by sentence, from the app's own closed kinds
(`places.SETTINGS`), with a quote checked to be the page's narration; code compares the
answer with `places.settings_for` of where the engine holds the party, and a mismatch is
a contradiction the read-back's repair rewrites or cuts. On the bench
(tests/beat_verify/gold.py, docs/beat-verify.md has the numbers) a market written with
timber stalls, a tavern seen across the square, and a ship in a character's mouth raise
nothing.
"""
from __future__ import annotations

import json

import pytest

from gm import beat_verify as bv
from rules import places as places_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from tests.beat_verify import gold as G
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = next(e for e in WORLD.entities.values() if e.name == "Zhilvarnia")
ST, IN, TV, CO, UN, SH = places_mod.SETTINGS


@pytest.fixture(scope="module")
def known():
    s = Scene(location_id=TOWN.id)
    pc = instantiate("guildhand", scene=s, name="Kesst Vayr")
    pc.kind = "pc"
    s.add(pc)
    e = Engine(s, Dice(seed=5), world=WORLD)
    return tuple(e.places()) + tuple(e.open_ground())


@pytest.mark.parametrize("name,kinds", [
    ("the market", {ST}),
    ("the great square", {ST}),
    ("the docks", {ST, SH}),
    ("the tavern", {IN, TV}),
    ("the smithy", {IN}),
    ("the undercroft of the cathedral", {IN, UN}),
    ("the graveyard", {ST, CO}),
    ("the warrens", {ST, IN}),
    ("the outskirts", {ST, CO}),
    ("the gate", {ST, CO}),
    ("the approach", {CO}),
])
def test_the_kinds_a_place_truly_is_come_from_the_engine(known, name, kinds):
    """Derived from what the engine already holds — the ground in the id, the floor plan's
    roof, the side of the settlement's edge, the kind words — never a description. A ship
    is a truth only where the place stands on water: a deck at the docks, not the market.
    The bench's table (`gold.PLACE_SETTINGS`) is these same answers."""
    place = places_mod.find(known, name)
    assert set(places_mod.settings_for(place, known)) == kinds
    if name in G.PLACE_SETTINGS:
        assert set(G.PLACE_SETTINGS[name]) == kinds, "the bench table must match the game"


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _chat(*replies):
    queue = [json.dumps(r) for r in replies]

    def chat(messages, *a, **k):
        chat.asked.append(messages)
        return _Reply(queue.pop(0) if queue else '{"answer": "yes"}')

    chat.asked = []
    return chat


_EMPTY = {"player_ends_at": {"place": "the market", "quote": ""}, "changed_hands": [],
          "trades": [], "harmed": [], "arrived": [], "left": [], "time_of_day": []}
# The model's own answer on the report's beat (bench record, gemma-4-12B, 2026-10-16).
_DECK = {"setting": [{"kind": SH, "quote": "thudding uselessly into the wooden planks of "
                                          "the deck"}]}


def _read(beat_id, setting_answer, bodies=None):
    beat = G.by_id(beat_id)
    facts = G.facts(beat)
    replies = [_EMPTY] + ([bodies or {"conditions": []}] if facts.bodies else []) \
        + [setting_answer]
    reading = bv.read(beat["text"], facts, model="stub", chat=_chat(*replies))
    assert not reading.error
    return facts, reading, bv.diff(reading.claims, facts, beat["text"])


def test_a_deck_in_a_market_is_a_contradiction_with_the_fix_named():
    facts, reading, found = _read("set-deck-in-market", _DECK)
    assert [c.category for c in reading.claims] == ["setting"]
    assert [d.category for d in found] == ["setting"]
    d = found[0]
    assert "planks of the deck" in d.sentence
    assert "the market, in the open air of the town" in d.fact
    assert "no ship, boat, deck" in d.fact
    assert "Is the scene in this sentence set aboard a ship or boat" in bv.question(d, facts)


def test_a_market_with_timber_stalls_is_not_flagged():
    """The false positive the brief named: the market described with timber stalls and
    awnings is a market."""
    _f, reading, found = _read("set-timber-stall", {"setting": [
        {"kind": ST, "quote": "bites into the timber post of a fishmonger's stall"}]})
    assert reading.claims and found == []


def test_a_quote_that_is_only_speech_is_dropped():
    """'…the deck of my ship is no place for a fool like you' is a character talking."""
    _f, reading, found = _read("set-ship-in-speech", {"setting": [
        {"kind": SH, "quote": "the deck of my ship is no place for a fool like you"}]})
    assert not reading.claims and reading.dropped and found == []


def test_a_place_the_engine_cannot_name_is_not_judged_and_not_asked():
    """No kinds for the place (`Facts.settings` empty): no setting call is made at all —
    an answer nothing can judge is a call for nothing."""
    beat = dict(G.by_id("set-deck-in-market"), settings=())
    facts = G.facts(beat)
    chat = _chat(_EMPTY, {"conditions": []})
    bv.read(beat["text"], facts, model="stub", chat=chat)
    assert all("KIND of place" not in m[0]["content"] for m in chat.asked)


def test_the_setting_is_asked_on_its_own_and_the_first_read_is_unchanged():
    """A call of its own (docs/beat-verify.md, "The kind of place"): the first read's
    messages and schema are master's, byte for byte, so every earlier category reads as
    it did; the reader of the setting is not told where the engine holds the party."""
    beat = G.by_id("set-deck-in-market")
    facts = G.facts(beat)
    assert "setting" not in bv.schema(facts)["properties"]
    assert "setting" not in bv.messages(beat["text"], facts)[0]["content"]
    asked = bv.setting_messages(beat["text"])
    assert "the market" not in asked[-1]["content"]
    assert bv.setting_schema()["properties"]["setting"]["items"]["properties"]["kind"][
        "enum"] == list(places_mod.SETTINGS)


def test_a_sentence_naming_where_the_party_is_is_set_there():
    """"the dirt of the west crossing mingling with the blood on his tunic" came back open
    country, both runs and both reads (bench, 2026-10-16): the narrator named the place the
    engine holds, and that name is the setting — compared as a name, never read as English."""
    facts = bv.Facts(start="the west crossing", end="the west crossing", places=(),
                     settings=(ST,))
    named = bv.Claim("setting", {"kind": CO}, "the dirt of the west crossing mingling",
                     "The man lies still, the dirt of the west crossing mingling with the "
                     "blood on his tunic.", True)
    other = bv.Claim("setting", {"kind": CO}, "Branches whip at your face",
                     "Branches whip at your face as you push on.", True)
    assert bv.diff([named], facts) == []
    assert [d.category for d in bv.diff([other], facts)] == ["setting"]


def test_a_thing_shown_taken_after_the_engine_refused_it_is_a_contradiction():
    """Live check, 2026-10-16: "I pick up one of the crates of dried fruit and throw it" was
    refused ("There is no one of the crates … to pick up"), and the page wrote "you have to
    wrench it from the pile. You heave the wood … and it flies." A pick-up off the floor
    was never judged while the world never ran out; on a turn the engine refused one for
    not being there, it is — and the second read asks about a pick-up, not a hand-over
    (probed 4/4 on the beat's sentences and two controls)."""
    why = ("There is no one of the crates of dried fruit here for Kesst Vayr to pick up: "
           "nothing has put one here. Nothing loose lies here.")
    facts = bv.Facts(start="the market", end="the market", places=(),
                     outcomes=({"op": "give", "status": "refused", "code": "not_here",
                                "tell": why},))
    heave = bv.Claim("hands", {"item": bv.OTHER_THING, "from": bv.FLOOR, "to": "pc"},
                     "You heave the wood", "You heave the wood and it flies.", True)
    found = bv.diff([heave], facts)
    assert [(d.category, d.line) for d in found] == [("hands", why)]
    assert "pick something up" in bv.question(found[0], facts)
    # With no such refusal, a stone off the floor is still nobody's business.
    calm = bv.Facts(start="the market", end="the market", places=())
    assert bv.diff([heave], calm) == []


def test_the_finding_is_a_member_kind_and_cut_by_the_backstop():
    from gm.checks import beat_verified

    assert "beat-setting" in beat_verified.KINDS
    assert beat_verified._KIND["setting"] == ("beat-setting", 3)
