"""The interpreter's reading, in the turn (docs/the-interpreter.md, "first integration").

The readers consult the reading before their regex; the planner is shown it; the ops it
grounds join the schema's requirements; the turn log records it beside the detectors'
opinion. Nothing here reaches a model: the reading is put in place as a turn would.
"""
from __future__ import annotations

from gm import interpret, judgement
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id


def _read(text, actions, question=False, claims=()):
    frame = {"question": question, "actions": actions, "claims": list(claims)}
    interpret.remember(text, frame)
    return frame


def test_the_reading_names_who_is_sought_where_the_regex_could_not():
    """Before the regex patches, "the woman WHO SOLD me bread" was "woman"; the reading
    carries the definite description whole."""
    text = "I go to the market and ask around for the woman who sold me bread."
    _read(text, [{"act": "go", "place": "the market"},
                 {"act": "seek", "target": "the woman who sold me bread"}])
    assert judgement.person_sought(text) == "woman who sold me bread"


def test_an_indefinite_newcomer_keeps_only_the_head():
    text = "I ask around for a guide who knows the grassland."
    _read(text, [{"act": "seek", "target": "a guide who knows the grassland"}])
    assert judgement.person_sought(text) == "guide"


def test_the_reading_says_a_drink_bought_for_a_man_is_a_gift():
    text = "I buy the man a drink."
    _read(text, [{"act": "give", "target": "the man", "object": "a drink"}])
    assert judgement.purchase_sought(text) == ""
    text2 = "I go to the market and pick up a coil of rope for the road."
    _read(text2, [{"act": "go", "place": "the market"},
                  {"act": "buy", "object": "a coil of rope"}])
    assert judgement.purchase_sought(text2) == "a coil of rope"


def test_the_reading_grounds_a_walk_only_to_a_place_that_exists():
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=1), world=WORLD)
    e.place_party()
    places = e.places()
    other = next(p for p in places if p.id != s.at)
    ops = interpret.ops_for({"actions": [{"act": "go", "place": other.name},
                                         {"act": "wait", "time": "until dusk"}]},
                            s, places)
    assert ops == ["travel", "advance_time"]
    assert interpret.ops_for({"actions": [{"act": "go", "place": "the moon"}]},
                             s, places) == []


def test_the_planner_is_told_what_was_read_and_what_is_only_claimed():
    lines = interpret.brief_lines({"question": False, "claims": ["the guards cower"],
                                   "actions": [{"act": "break_in", "object": "the door"}]})
    assert "1. break_in — object: the door" in lines
    assert "CLAIMS" in lines and "the guards cower" in lines
    asked = interpret.brief_lines({"question": True, "actions": [], "claims": []})
    assert "a question asked of the game" in asked


def test_a_reading_that_fails_leaves_the_regex_in_charge():
    text = "I kick in her door."
    interpret.remember(text, {"error": "timed out"})
    assert judgement.breaks_in(text) == ("her", "force")


# --- found live, 2026-09-27 (strangers and calling, with the reading in the turn) ----------

def test_a_reading_of_her_means_nobody_new():
    """Live: "I buy a loaf from her and ask her name" read as talking to her; falling back
    to the regex brought back "her name" as a person to introduce."""
    text = "I buy a loaf from her and ask her name."
    _read(text, [{"act": "buy", "object": "a loaf", "target": "her"},
                 {"act": "talk", "target": "her", "says": "name"}])
    assert judgement.person_sought(text) == ""


def test_the_counter_takes_the_payment_not_a_give():
    raw = judgement.strip_counter_buys(
        [{"op": "give", "params": {"item": "gp"}}, {"op": "say", "params": {"words": "hi"}}],
        "I buy a loaf from her.")
    assert [r["op"] for r in raw] == ["say"]


def test_a_placeholder_is_not_who_somebody_is():
    """Live: `introduce who="new1"` put a person called "new1" in the scene."""
    assert not judgement._describes({"who": "new1"})
    assert judgement._describes({"who": "a carter"})


def test_the_schema_asks_for_a_declared_op_as_a_required_key():
    """Measured: Ollama enforced `contains` in 0 of 6 replies and a required property in
    6 of 6. The declared op is a required key, and a travel's place is one of the real
    places by name."""
    from gm import prompts
    from gm.agent import GMAgent

    schema = prompts.turn_schema(must_contain=("travel",), places=("the market", "the well"))
    decl = schema["properties"]["declared"]
    assert decl["required"] == ["travel"] and "declared" in schema["required"]
    assert decl["properties"]["travel"]["properties"]["params"]["properties"]["place"][
        "enum"] == ["the market", "the well"]
    merged = GMAgent._merge_declared([{"op": "narrate_only"}],
                                     {"travel": {"params": {"place": "the market"}}})
    assert merged[0]["op"] == "travel" and merged[0]["params"]["place"] == "the market"
    kept = GMAgent._merge_declared([{"op": "travel", "params": {"place": "the well"}}],
                                   {"travel": {"params": {"place": "the market"}}})
    assert len(kept) == 1 and kept[0]["params"]["place"] == "the well"


def test_a_declared_introduce_comes_before_whatever_addresses_them():
    """Live: appended last, the model's own `say` to new1 came before the introduce that
    makes new1; every attempt was refused and the turn fell back to narrate_only."""
    from gm.agent import GMAgent

    merged = GMAgent._merge_declared(
        [{"op": "narrate_only"}, {"op": "say", "params": {"words": "hi", "to": "new1"}}],
        {"introduce": {"params": {"who": "a baker", "how": "already_here"}},
         "travel": {"params": {"place": "the market"}}})
    assert [r["op"] for r in merged] == ["travel", "introduce", "narrate_only", "say"]
