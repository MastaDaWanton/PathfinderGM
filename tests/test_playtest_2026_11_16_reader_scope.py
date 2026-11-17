"""The reader and scope: playtest 2026-11-16, overnight items (Vesna Kroll, 0.4.0).

Each test names the item and what the turn did. The lines are the playtest's own; the
scenes are rebuilt on the fixture world's Mirabalos, the city the save was played in.
"""
from __future__ import annotations

from gm import acts_to_ops, interpret, judgement, sequence
from rules import places, population
from rules.dice import Dice
from rules.engine import Engine, Scene, SeenFrom
from rules.sheet import from_dict, load_pc, to_dict
from world import loader

MIRABALOS = "7ef5e373c993"
WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


def _city():
    s = Scene(location_id=MIRABALOS)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    return s, e


def _place(e, name):
    return next(p for p in e.places() if p.name == name)


def _run(e, *raws):
    intents = e.validate([{"actor": "pc", "because": "t", "visibility": "hidden", **r}
                          for r in raws], origin="author:test")
    return e.run(intents)


# --- #68 and E1: the place finder ---------------------------------------------------------

def test_a_temple_in_a_city_with_a_cathedral_is_the_cathedral():
    """#68: "I walk to the nearest temple" took three plans refused "there is no 'the
    temple' here" before the fourth chose the cathedral, a model call each."""
    s, e = _city()
    known = e.places()
    cathedral = _place(e, "the cathedral")
    for said in ("the nearest temple", "the temple", "a church", "the shrine"):
        assert places.find(known, said, near=s.at).id == cathedral.id, said
    assert places.find(known, "the nearest tavern") is None or \
        places.find(known, "the nearest tavern").name != "the cathedral"


def test_a_room_named_with_where_it_is_is_that_room_not_the_ground_above_it():
    """E1: "I walk back down to the well room under the sewers" was read as "the sewers"
    by the last-word rule (where she stood) and read `within_place` with fixture
    `floor`, and no walk happened. The main channel stands in for the well room here."""
    s, e = _city()
    e.place_party(_place(e, "the gardens").id)
    _run(e, {"op": "venture", "params": {"kind": "sewers"}})
    sewers = s.at
    known = e.places()
    channel = places.find(known, "the main channel under the sewers", near=sewers)
    assert channel is not None and channel.id.startswith(sewers + "/"), channel
    read = {"act": "go", "place": "the main channel under the sewers",
            "within_place": True, "fixture": "floor"}
    assert not interpret.within_place(read, known, sewers)


# --- #56: a room is no person -------------------------------------------------------------

def test_a_dungeon_room_is_not_looked_for_as_a_person():
    """#56: arriving at the cells logged a population miss for a person called "cells"
    (no reading on a Map walk, so the sentence's own words were searched)."""
    assert judgement.person_sought("I go to the cells.") == ""
    assert judgement.person_sought("I go to the turnkey's room.") == ""
    # A person by their trade is still a person.
    assert judgement.person_sought("I go to the smith.") == "smith"


# --- #69: a noun of address ---------------------------------------------------------------

def test_a_form_of_address_in_the_players_words_is_nobody_sought():
    """#69: '"Father, I'm badly hurt..."' was read with target "Father"; the finder
    refused "No Father is here, and Mirabalos has none the world names", and the beat
    said there was no priest while she spoke to him."""
    line = '"Father, I\'m badly hurt. Can you heal me? I can pay." I show him my coin.'
    interpret.remember(line, {"question": False, "claims": [], "actions": [
        {"act": "talk", "target": "Father", "says": "I'm badly hurt. Can you heal me?",
         "span": "Father, I'm badly hurt. Can you heal me? I can pay."}]})
    assert judgement.addressed_in_speech("Father", line)
    assert judgement.person_sought(line) == ""
    # Named outside the quotation, the same word is somebody looked for.
    assert not judgement.addressed_in_speech("Father", 'I ask Father Odo, "Can you heal me?"')


# --- #75 and #94: who is there after the walk ---------------------------------------------

def test_a_bare_trade_is_never_somebody_met_in_another_town():
    """#75: "ask the foreman" at Mirabalos' docks matched a dock labourer glimpsed in
    Zhilvarnia by the trade alone and refused "The dock laborer is in Zhilvarnia now,
    not here"."""
    s, _e = _city()
    s.population = {"p6": {"id": "p6", "phrase": "dock laborer", "home": "6953424c8a82",
                           "spot": "", "seen_at": "", "first_seen": 1, "last_seen": None,
                           "last_met": None, "tier": "glimpse",
                           "life": {"work": "labourer", "mobility": "resident"}}}
    assert population.find(s, "the foreman", world=WORLD).scope == population.NONE
    s.population["p6"]["home"] = MIRABALOS
    assert population.find(s, "the foreman", world=WORLD).scope != population.NONE


def test_the_one_spoken_to_after_a_walk_is_looked_for_where_the_walk_ends():
    """#94: "Go back up on deck and ask the deckhand…" was planned in the hold; the
    deckhand on deck was looked for in the hold, the turn refused "a deckhand is not
    here", and the say went to nobody."""
    s, e = _city()
    docks = _place(e, "the docks")
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["name"] = "a deckhand"
    deckhand = from_dict(d, ref="c20")
    deckhand.kind = "npc"
    s.arrive(deckhand, place_id=docks.id)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "go", "place": "the docks", "span": "go down to the docks"},
        {"act": "talk", "target": "the deckhand", "says": "is there work",
         "span": "ask the deckhand whether there is work"}]}
    view = interpret.scene_by_then(frame, s, e.places())
    assert isinstance(view, SeenFrom) and "c20" in view.actors and "c20" not in s.actors
    raw = [{"op": "travel", "params": {"place": "the docks"}},
           {"op": "say", "actor": "pc", "params": {"line": "is there work"}}]
    out = acts_to_ops.address_the_named(raw, frame, view)
    assert out[1]["params"]["to"] == "c20"
    line = "I go down to the docks and ask the deckhand whether there is work."
    interpret.remember(line, frame)
    said = judgement.answer_the_absent(raw, line, view, WORLD)
    assert not any((r.get("params") or {}).get("not_here") for r in said), said
    # And the engine takes a list that walks there and then speaks to him: it was
    # refused "say: unknown ref 'c20' in params.to" on three plans running.
    e.validate([{"op": "travel", "actor": "pc", "params": {"place": "the docks"}},
                {"op": "say", "actor": "pc", "params": {"to": "c20", "words": "is there work"}}])
    # Asked from the hold as before, the deckhand is not here.
    assert interpret.scene_by_then({"actions": frame["actions"][1:]}, s, e.places()) is s


# --- #63 and #72: the turn's budget -------------------------------------------------------

def _cut(text, actions):
    parts = sequence.clauses(text)
    return sequence.within_budget(parts, actions, interpret.cost_of)


def test_parting_words_then_walking_off_run_in_one_turn():
    """#63, three times: "I tell the smuggler I'll be back for the beast, then make my way
    back out…" was read talk + go + go, the budget ended the turn on the talk, and the
    walk went to the pen; she stayed in the cells, in conversation. The 2026-10-17 ruling:
    a leaving deed in the player's own line takes their leave, speech first."""
    text = ("I tell the smuggler I'll be back for the beast, then make my way back out "
            "the way I came, up through the culvert to the gardens.")
    acts = [{"act": "talk", "target": "the smuggler", "says": "I'll be back for the beast",
             "span": "tell the smuggler I'll be back for the beast"},
            {"act": "go", "place": "the way I came",
             "span": "make my way back out the way I came"},
            {"act": "go", "place": "the gardens", "span": "up through the culvert to the gardens"}]
    assert _cut(text, acts) is None
    text = "\"Then it's you and me.\" I tell the deckhand, then bed down below decks for the night."
    acts = [{"act": "talk", "target": "the deckhand", "says": "Then it's you and me.",
             "span": "I tell the deckhand"},
            {"act": "rest", "place": "below decks", "span": "bed down below decks for the night"}]
    assert _cut(text, acts) is None
    # Words with an answer still to come end the turn as the owner ruled.
    text = "I ask the smuggler where the cargo is, then search the cells."
    acts = [{"act": "talk", "target": "the smuggler", "says": "where the cargo is",
             "span": "ask the smuggler where the cargo is"},
            {"act": "search", "place": "the cells", "span": "search the cells"}]
    assert _cut(text, acts) is not None


def test_a_gesture_at_the_listener_goes_with_the_words():
    """#72: '"…I can pay." I show him my coin.' — the coin shown was cut off into the pen
    and only the speech was played."""
    text = '"Father, I\'m badly hurt. Can you heal me? I can pay." I show him my coin.'
    acts = [{"act": "talk", "target": "Father", "says": "I'm badly hurt.",
             "span": "Father, I'm badly hurt. Can you heal me? I can pay."},
            {"act": "other", "target": "him", "object": "my coin", "span": "I show him my coin"}]
    assert _cut(text, acts) is None


# --- E3 and E4: checks ------------------------------------------------------------------

def test_the_plans_perception_is_dropped_when_the_words_neither_look_nor_search():
    """E3: "Climb back up out of the culvert and walk back up to the gardens" (athletics
    + go) left the plan's Perception at DC 10 waiting for the player's die."""
    climb = {"actions": [{"act": "athletics", "place": "the culvert"},
                         {"act": "go", "place": "the gardens"}]}
    raw = [{"op": "travel", "params": {"place": "the gardens"}},
           {"op": "check", "actor": "pc", "params": {"skill": "perception"}}]
    kept, dropped = interpret.drop_unchosen_checks(raw, climb)
    assert dropped == ["perception"] and len(kept) == 1
    listen = {"actions": [{"act": "look", "object": "the stuck door"}]}
    assert interpret.drop_unchosen_checks(raw, listen)[1] == []


def test_a_failed_climb_walks_nowhere():
    """E4: "climb out and walk to X" rolled the climb after the travel, and a failed
    climb still walked. By the book a failed Climb makes no progress (CRB p.91)."""
    s, e = _city()
    start = s.at
    res = _run(e, {"op": "check", "params": {"skill": "climb", "dc": 25}},
               {"op": "travel", "params": {"place": "the docks"}})
    if res.awaiting:
        res = e.resume(1)
    assert s.at == start, [o.tell for o in res.outcomes]
    assert "gets no further" in res.outcomes[0].tell
    # And made, the walk goes on.
    res = _run(e, {"op": "check", "params": {"skill": "climb", "dc": 5}},
               {"op": "travel", "params": {"place": "the docks"}})
    if res.awaiting:
        res = e.resume(20)
    assert s.at == _place(e, "the docks").id


def test_a_climbs_check_is_put_where_the_climb_is_in_the_words():
    """E4's other half: the check the detector declared had no row, so it kept its place
    after the travel the plan wrote first."""
    s, e = _city()
    rows = acts_to_ops.table({"actions": [
        {"act": "athletics", "place": "the culvert", "span": "climb out of the culvert"},
        {"act": "go", "place": "the docks", "span": "walk to the docks"}]}, s,
        places=e.places())
    raw = [{"op": "travel", "params": {"place": "the docks"}},
           {"op": "check", "actor": "pc", "params": {"skill": "climb"}}]
    assert [r["op"] for r in acts_to_ops.order(raw, rows)] == ["check", "travel"]


# --- #77: keeping clear of a place is the way, not a sneak ---------------------------------

def test_a_sneak_beside_a_walk_that_only_names_the_way_is_taken_out():
    """#77: "…carry on to the docks, keeping well away from the gate" was read go +
    `stealth: the gate`, and the Stealth was refused "the foreman is watching" onto the
    page. The targeted question (`interpret.confirm_hiding`) answered "a way to go" for
    that span live; a hiding the question confirms, or a sneak past somebody, stays."""
    frame = {"actions": [{"act": "go", "place": "the docks", "span": "carry on to the docks"},
                         {"act": "stealth", "place": "the gate",
                          "span": "keeping well away from the gate"}]}
    asked = []
    out = interpret.unhidden(frame, ask=lambda s: asked.append(s) or "a way to go")
    assert out == ["keeping well away from the gate"]
    assert [a["act"] for a in frame["actions"]] == ["go"]
    hiding = {"actions": [{"act": "go", "place": "the docks", "span": "go to the docks"},
                          {"act": "stealth", "span": "keeping low"}]}
    assert interpret.unhidden(hiding, ask=lambda s: "hides") == []
    # A sneak past somebody is asked too since playtest 2026-11-17 #23 ("I step past the
    # toll-keeper" was refused for want of cover); the question's "hides" keeps it.
    past = {"actions": [{"act": "go", "place": "the docks", "span": "go to the docks"},
                        {"act": "stealth", "target": "the guards", "span": "past the guards"}]}
    assert interpret.unhidden(past, ask=lambda s: "hides") == []
    assert len(past["actions"]) == 2
    # No reader in the suite: nothing changes.
    assert interpret.unhidden(frame, ask=None) == []


def test_parting_words_and_a_question_after_the_walk_each_reach_their_own_listener():
    """Live 2026-11-17, #63's and #75's line run whole: "I tell the deckhand I'll be back
    by nightfall, then walk down to the docks and ask the foreman…" sent the parting words
    to nobody ("Vesna Kroll speaks, to the effect that…"), and the plan walked to the docks
    three times, two refused onto the page as "already travelled this turn"."""
    s, e = _city()
    docks = _place(e, "the docks")
    for ref, name, at in (("c20", "a deckhand", s.at), ("c29", "the foreman", docks.id)):
        d = to_dict(load_pc("fixtures/pc-kesst.json"))
        d["name"] = name
        npc = from_dict(d, ref=ref)
        npc.kind = "npc"
        s.arrive(npc, place_id=at)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "talk", "target": "the deckhand", "says": "I'll be back",
         "span": "tell the deckhand I'll be back"},
        {"act": "go", "place": "the docks", "span": "walk down to the docks"},
        {"act": "talk", "target": "the foreman", "says": "is there work",
         "span": "ask the foreman whether there is work"}]}
    raw = [{"op": "say", "actor": "pc", "params": {"words": "I'll be back"}},
           {"op": "travel", "params": {"place": "the docks"}},
           {"op": "travel", "params": {"place": "the docks"}},
           {"op": "say", "actor": "pc", "params": {"words": "is there work"}}]
    out = acts_to_ops.once_each_walk(
        acts_to_ops.address_the_named(raw, frame, s, places=e.places()))
    assert [r["op"] for r in out] == ["say", "travel", "say"]
    assert out[0]["params"]["to"] == "c20" and out[2]["params"]["to"] == "c29"
