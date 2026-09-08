"""Quest schemes: the contract, as tests, written before the machinery (phase 1 of
docs/quest-schemes-plan.md §6.10).

Two sets. The passing set says what a scheme does: opens from the world's own
people and places with no invented name, advances by the most specific step whose
criteria hold, stays silent where the player is not, pays and punishes through the one
applicator, survives the save. The refusal set says what the validator must refuse
with the fix named: a step no player can change, a twist with no foreshadowing, a
criterion in prose, a digit in a reward, an action outside the vocabulary.

Measured before this (2026-09-08, in design): the first draft fired steps by the hour,
and this app's clock jumps by travel, so a step keyed to "hour four" would fire
mid-haggle; and the first draft handed the narrator a "meanwhile" paragraph, which
tells the player what their character cannot know.
"""
from __future__ import annotations

import json

import pytest

from rules import cards, schemes
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"


@pytest.fixture(autouse=True)
def schemes_on(monkeypatch):
    """conftest turns schemes off for every other test; these are about them."""
    monkeypatch.setattr(schemes, "ENABLED", True)
MARKET = f"{TOWN}~urban:the-market"


def _table(seed=3):
    s = Scene(location_id=TOWN)
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party(MARKET)
    return s, e, pc


def _run(engine, op, params, actor="pc"):
    intents = engine.validate([{"op": op, "actor": actor, "because": "t", "params": params}],
                              origin="author:test")
    return engine.run(intents)


def _travel(engine, place):
    return _run(engine, "travel", {"place": place})


def _out(engine, inst):
    """Into the wild the way a player does: by naming the ground, not a place id."""
    return _run(engine, "travel", {"biome": inst["slots"]["wild"]["terrain"]})


def _wait(engine, minutes: int):
    return _run(engine, "advance_time", {"amount": minutes, "unit": "minutes"})


def _instance(scene, sid="the-lost-thing"):
    return next(i for i in scene.schemes if i["scheme"] == sid)


# --- the document ---------------------------------------------------------------------

def test_the_shipped_scheme_validates_and_names_no_one():
    docs = schemes.shipped()
    assert "the-lost-thing" in docs
    doc = docs["the-lost-thing"]
    assert schemes.validate(doc) == []
    text = json.dumps(doc)
    # World-agnostic: every person, place and thing is a slot.
    for slot in ("giver", "rival", "market", "wild", "lost"):
        assert f"${slot}" in text
    assert not any(ch.isdigit() for card in doc["cards"] for ch in " ".join(card.get("facts") or []) + card.get("title", ""))


# --- opening from the world -------------------------------------------------------------

def test_a_scheme_opens_at_the_market_with_slots_filled_from_the_world():
    """The giver is a person from the world's own cast with a stat block, standing at
    the market; the rival is out at the wild place; the lost thing is something that
    grows in this biome; nothing is a name the world does not know."""
    s, e, pc = _table()
    res = _wait(e, 1)
    inst = _instance(s)
    slots = inst["slots"]
    giver = s.people[slots["giver"]["ref"]]
    assert giver.at == MARKET and not giver.is_pc
    assert giver.name and giver.name.lower() not in ("guildhand", "watchman", "thug")
    assert giver.world_entity_id, "a cast member, grounded"
    rival = s.people[slots["rival"]["ref"]]
    assert rival.at != MARKET and slots["wild"]["terrain"] in rival.at
    assert slots["lost"]["name"]
    # The visible quest card is on the table with the slots filled in words.
    q = cards.quests(s)
    assert len(q) == 1 and giver.name in q[0].title and slots["lost"]["name"] in q[0].title
    assert q[0].giver == giver.ref and len(q[0].objectives) == 2
    # The secret card is the GM's alone.
    truth = next(c for c in cards.load(s) if c.secret)
    assert rival.name in " ".join(truth.facts) and giver.name in " ".join(truth.facts)
    # The foreshadowing is granted at open through the applicator, so the brief carries it.
    assert pc.has_state("knows.giver-hides-something")
    eff = next(x for x in pc.effects if "knows.giver-hides-something" in x.tags)
    assert eff.source.startswith("scheme:the-lost-thing")
    # Opening is silent to the prose: nothing happened the player could see.
    assert not [o for o in res.outcomes if o.op == "scheme" and o.tell]


def test_a_scheme_opens_once_and_survives_the_save():
    from play.campaign import Campaign

    s, e, pc = _table()
    _wait(e, 1)
    _wait(e, 1)
    assert len([i for i in s.schemes if i["scheme"] == "the-lost-thing"]) == 1
    c = Campaign(id="t-schemes", world_source="fixtures/pangrella-campaign.json", scene=s)
    back = Campaign.load(c.save())
    assert _instance(back.scene)["slots"] == _instance(s)["slots"]
    assert back.scene.people[_instance(back.scene)["slots"]["rival"]["ref"]].name


# --- steps, salience, silence -------------------------------------------------------------

def test_arriving_where_the_rival_is_fires_the_most_specific_step_with_a_tell():
    s, e, pc = _table()
    _wait(e, 1)
    inst = _instance(s)
    rival = s.people[inst["slots"]["rival"]["ref"]]
    res = _out(e, inst)
    fired = [o for o in res.outcomes if o.op == "scheme"]
    assert fired and rival.name in fired[0].tell and "has the" in fired[0].tell
    assert "found" in inst["fired"]
    q = cards.quests(s)[0]
    assert q.objectives[0]["done"] and len(q.objectives) == 3     # revealed
    assert pc.has_state("knows.rival-has-it")
    # One step per tick: the twist waits for the next.
    assert "twist" not in inst["fired"]
    res = _wait(e, 1)
    assert "twist" in inst["fired"] and pc.has_state("knows.rival-is-kin")
    assert any("kin" in o.tell for o in res.outcomes if o.op == "scheme")


def test_a_twist_without_its_foreshadowing_does_not_fire_and_says_why():
    s, e, pc = _table()
    _wait(e, 1)
    inst = _instance(s)
    # Strip the foreshadowing the open granted.
    pc.remove_effects(match=lambda x: "knows.giver-hides-something" in x.tags)
    _out(e, inst)
    _wait(e, 1)
    assert "twist" not in inst["fired"]
    assert any(sk["step"] == "twist" and "knows.giver-hides-something" in sk["why"]
               for sk in inst.get("skipped", []))


def test_a_step_out_of_sight_is_silent_and_goes_to_the_log_and_the_secret_card():
    """The rival comes to town after six hours away: the world changes, the prose is
    told nothing, the turn log and the secret card carry it."""
    s, e, pc = _table()
    _wait(e, 1)
    inst = _instance(s)
    rival = s.people[inst["slots"]["rival"]["ref"]]
    _out(e, inst)
    _travel(e, "the market")
    res = _wait(e, 6 * 60 + 5)
    assert "rival-comes-to-town" in inst["fired"]
    assert rival.at == MARKET
    assert not [o for o in res.outcomes if o.op == "scheme" and o.tell], "silent"
    assert inst["fired"]["rival-comes-to-town"]["silent"]
    truth = next(c for c in cards.load(s) if c.secret)
    assert any("looking for" in f for f in truth.facts)
    # The news it carried is queued, and gossip needs somebody present who heard it.
    assert inst["news"] and inst["news"][0]["carrier"] == "gossip"


def test_news_arrives_as_a_person_or_thing_in_the_scene_and_grants_knows():
    s, e, pc = _table()
    _wait(e, 1)
    inst = _instance(s)
    _out(e, inst)
    _travel(e, "the market")
    _wait(e, 6 * 60 + 5)
    # The giver is at the market and would have heard: the gossip arrives next tick.
    res = _wait(e, 1)
    told = [o for o in res.outcomes if o.op == "scheme" and o.tell]
    assert told and "quarrelling" in told[0].tell
    assert pc.has_state("knows.news.quarrel-at-the-market") or any(
        t.startswith("knows.news.") for t in pc.standing_tags() + tuple(
            tg for x in pc.effects for tg in x.tags))
    assert not inst["news"]


# --- outcomes ------------------------------------------------------------------------------------

def test_returning_the_thing_pays_the_story_award_and_regard_through_the_applicator():
    s, e, pc = _table()
    _wait(e, 1)
    inst = _instance(s)
    giver = s.people[inst["slots"]["giver"]["ref"]]
    _out(e, inst)
    _wait(e, 1)
    # Take the thing: the test hands it over the way loot or a gift would.
    schemes.hand_item(s, pc, inst["slots"]["lost"]["name"])
    before = pc.xp
    res = _travel(e, "the market")
    assert "returned" in inst["fired"] and inst["outcome"] == "returned"
    assert pc.xp > before
    assert giver.has_state("attitude.friendly")
    eff = next(x for x in giver.effects if "attitude.friendly" in x.tags)
    assert eff.source == "scheme:the-lost-thing/returned"
    assert not cards.quests(s)[0].live
    assert any(giver.name in o.tell for o in res.outcomes if o.op == "scheme")


def test_giving_it_to_the_rival_costs_the_givers_regard():
    s, e, pc = _table()
    _wait(e, 1)
    inst = _instance(s)
    giver = s.people[inst["slots"]["giver"]["ref"]]
    rival = s.people[inst["slots"]["rival"]["ref"]]
    _out(e, inst)
    _wait(e, 1)            # the twist
    schemes.hand_item(s, pc, inst["slots"]["lost"]["name"])
    res = _run(e, "give", {"item": inst["slots"]["lost"]["name"], "to": rival.ref})
    assert inst["outcome"] == "gave-to-rival"
    assert giver.has_state("attitude.unfriendly") and rival.has_state("attitude.friendly")


# --- the refusal set -------------------------------------------------------------------------

def _doc(**over):
    base = json.loads(json.dumps(schemes.shipped()["the-lost-thing"]))
    base.update(over)
    return base


def test_a_step_no_player_can_change_is_refused():
    d = _doc()
    d["steps"][0]["criteria"] = ["since(open) >= 1h"]
    problems = schemes.validate(d)
    assert any("found" in p and "player" in p for p in problems)


def test_a_twist_with_no_foreshadowing_is_refused():
    d = _doc()
    d["steps"][1]["fairness"] = []
    problems = schemes.validate(d)
    assert any("twist" in p and "foreshadow" in p for p in problems)


def test_a_criterion_in_prose_is_refused_with_the_shapes_named():
    d = _doc()
    d["steps"][0]["criteria"].append("the player feels uneasy")
    problems = schemes.validate(d)
    assert any("the player feels uneasy" in p and "at($place)" in p for p in problems)


def test_a_digit_in_a_reward_or_a_fact_is_refused():
    d = _doc()
    d["cards"][0]["reward"] = "50 gold"
    problems = schemes.validate(d)
    assert any("50 gold" in p and "number" in p for p in problems)


def test_an_action_outside_the_vocabulary_and_an_unknown_slot_are_refused():
    d = _doc()
    d["steps"][0]["action"] = {"do": "teleport", "who": "$giver"}
    d["steps"][2]["criteria"].append("at($castle)")
    problems = schemes.validate(d)
    assert any("teleport" in p for p in problems)
    assert any("$castle" in p for p in problems)
