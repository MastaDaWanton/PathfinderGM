"""The line "A Small Favour" (docs/quest-schemes-plan.md §3), as five scheme documents
in content/schemes/a-small-favour.json, checked as documents and played in the engine.

What these prevent, measured while authoring (2026-09-08):
- the validator's twist heuristic matched "kin" inside "looking" and "lie" inside
  "lies dead", so two innocent tells were refused as unforeshadowed twists — the
  documents are checked here as shipped, so a reworded tell cannot regress into that;
- a first draft of the errand opened on `at($market)` alone, which put a second quest
  card on the table in the first tick of every lost-thing test (`len(quests) == 1`
  fails); the errand now waits a day, and the honest-path test measures that no step
  of it fires when the player comes back within the hour;
- the tags a twist names for fairness must be *granted* earlier or the engine skips
  the twist every tick with "foreshadowing not on the brief" and the murder is never
  answered for — the lint below counts the grants, not the intent.

Where the grammar cannot say what the plan asked for, the test is xfail with the gap
named, so the engine agent has a red-to-green target and nothing here pretends.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from rules import cards, schemes
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import scheme_lint  # noqa: E402

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
# Zhilgoroth rather than Pangrella since schema 1.5, and the reason is the finding this
# change turned up: the shipped quest chain asks a settlement for five rooms by name — a
# market, somewhere to sleep, a gate, somewhere to pray and a hall — and **only 3 of
# Pangrella's 12 settlements have all five. 6 of Aurvantis's 64.**
#
# A campaign that begins anywhere else gets a chain whose places fall back to whatever is
# nearest: measured here, a scheme wanting somewhere to sleep put its meeting at the
# gatehouse. `tools/check_places.py` publishes the requirement now
# (`scheme_place_kinds`), so a world can be told before it ships rather than after.
TOWN = "58b90a214ada"
MARKET = f"{TOWN}~urban:the-market"


def _lodging() -> tuple[str, str]:
    """Where this scheme's `lodging` slot actually lands, and what to call it.

    Read from the scheme's own place table against the world's own rooms rather than
    named. This file used to hard-code the tavern, and at schema 1.5 Pangrella has no
    tavern and no inn — so the lodging slot falls through to the first room that is not
    the market, which is the gate.

    That is not a bug in either side and it is worth knowing: a scheme that wants
    somewhere to sleep, in a settlement with nowhere to sleep, puts the meeting at the
    gatehouse. It is why `essential_categories` is published to the checker now — 25 of
    Aurvantis's 64 settlements have nowhere of the leisure kind — and until a world
    ships one, this is what the fallback looks like.
    """
    from rules import places as _places
    from rules import schemes as _schemes

    rooms = {p.name: p.id for p in _places.home_set(WORLD.get(TOWN))}
    for name in _schemes.PLACE_KINDS.get("lodging", ()):
        if name in rooms:
            return rooms[name], name
    spare = next(pid for name, pid in rooms.items() if pid != MARKET)
    return spare, next(n for n, pid in rooms.items() if pid == spare)


LODGING, LODGING_NAME = _lodging()
LINE = ("a-small-favour", "wanted", "the-one-who-paid", "the-patron", "the-price-on-your-head")
DAY = 24 * 60


@pytest.fixture(autouse=True)
def schemes_on(monkeypatch):
    """conftest turns schemes off for every other test; these are about them."""
    monkeypatch.setattr(schemes, "ENABLED", True)


def _table(seed=3):
    s = Scene(location_id=TOWN)
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party(MARKET)
    return s, e, pc



def _named_kind(kind: str) -> str:
    """A room of the kind a quest asks for, by whatever this town calls it."""
    from rules import places as _places
    from rules import schemes as _schemes

    rooms = {p.name for p in _places.home_set(WORLD.get(TOWN))}
    for name in _schemes.PLACE_KINDS.get(kind, ()):
        if name in rooms:
            return name
    raise AssertionError(f"{TOWN} has nowhere a quest's {kind!r} could go")

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


def _instance(scene, sid="a-small-favour"):
    return next(i for i in scene.schemes if i["scheme"] == sid)


def _told(res, sid="a-small-favour"):
    """This scheme's own tells on a resolution: "The lost thing" is open at the same
    table and speaks for itself when its rival is met at the wild place."""
    return [o for o in res.outcomes if o.op == "scheme" and o.tell
            and o.effects and o.effects[0].get("scheme") == sid]


def _open_errand(e):
    """A day at the market, then the errand opens (and the witness speaks on the same tick)."""
    return _wait(e, DAY)


def _docs():
    return {sid: d for sid, d in schemes.shipped().items() if sid in LINE}


def _prose(doc):
    """Every field the narrator or the player could read."""
    out = [doc.get("title", "")]
    for c in doc.get("cards") or []:
        out += [c.get("title", ""), c.get("reward", "")] + list(c.get("facts") or []) + list(c.get("objectives") or [])
    for st in doc.get("steps") or []:
        out += list((st.get("tell") or {}).values())
        for a in [st.get("action")] + list(st.get("also") or []):
            if isinstance(a, dict):
                out += [str(a.get("text", "")), str(a.get("says", ""))]
    return out


# --- the documents ---------------------------------------------------------------------------

def test_the_five_schemes_ship_and_validate():
    docs = _docs()
    assert tuple(docs) == LINE, "all five, in the line's order"
    for sid, doc in docs.items():
        assert schemes.validate(doc) == [], sid


def test_no_digit_in_any_prose_field():
    for sid, doc in _docs().items():
        for text in _prose(doc):
            assert not re.search(r"\d", text), f"{sid}: {text!r}"


def test_every_name_is_a_slot_and_no_world_name_appears():
    """World-agnostic: the fixture's own cast and places must not be written in."""
    names = [str(c.get("name")) for c in (WORLD.play or {}).get("cast") or []]
    names += [str(c.get("faction")) for c in (WORLD.play or {}).get("conflicts") or []]
    for sid, doc in _docs().items():
        text = " ".join(_prose(doc))
        for n in names:
            if n:
                assert n not in text, f"{sid} names {n!r}"
        for s in re.findall(r"\$(\w+)", text):
            assert s in doc["slots"], f"{sid}: ${s} is not a slot"


def test_every_twist_names_fairness_tags_that_an_earlier_grant_supplies():
    docs = _docs()
    twists = [(sid, st) for sid, d in docs.items() for st in d["steps"] if st.get("fairness")]
    assert twists, "the line has at least one twist"
    problems = [p for p in scheme_lint.lint_set(docs) if "fairness" in p]
    assert problems == []
    # And concretely: the guards need the giver's unease (the open) and the victim's
    # name (the witness's aside, authored before the guards).
    q1 = docs["a-small-favour"]
    guards = next(st for st in q1["steps"] if st["id"] == "guards-arrive")
    assert set(guards["fairness"]) == {"knows.giver-uneasy", "knows.victim-named"}
    assert "knows.giver-uneasy" in q1["grants_on_open"][0]["tags"]
    ids = [st["id"] for st in q1["steps"]]
    assert ids.index("witness-speaks") < ids.index("guards-arrive")


def test_every_step_has_a_criterion_the_player_can_change():
    for sid, doc in _docs().items():
        for st in doc["steps"]:
            # The validator's own rule, not a copy of it: `has`/`holds` count when the
            # subject is the player, `alive`/`present` only beside a place or event.
            probe = {**doc, "steps": [dict(st, fairness=st.get("fairness") or ["knows.x"])]}
            assert not any("could change" in p for p in schemes.validate(probe)), f"{sid}/{st['id']}"


def test_the_lint_passes_on_the_shipped_line_and_names_the_fix_when_it_fails():
    docs = _docs()
    assert scheme_lint.lint_set(docs) == []
    # Break it four ways and read the fixes named.
    broken = json.loads(json.dumps(docs))
    q1 = broken["a-small-favour"]
    q1["grants_on_open"] = []                                # the unease is never granted
    q1["outcomes"]["orphan"] = {"resolve": "errand"}         # nothing fires it
    q1["cards"].append({"key": "spare", "title": "A card nothing touches"})
    q1["steps"][0]["criteria"].append("since(nowhere) >= 1h")
    problems = scheme_lint.lint_set(broken)
    assert any("knows.giver-uneasy" in p and "grants_on_open" in p for p in problems)
    assert any("'orphan'" in p and "no step fires it" in p for p in problems)
    assert any("'spare'" in p and "no step or outcome touches" in p for p in problems)
    assert any("since(nowhere)" in p for p in problems)


def test_the_silent_rule_is_authored_where_the_player_is_not():
    """Out-of-sight steps are silent; steps whose criteria put the player at the place
    (or that are only about what the player themself holds and knows) are perceptible
    or have a teller; nothing perceptible fires where the player is not."""
    for sid, doc in _docs().items():
        for st in doc["steps"]:
            tell = st["tell"]
            crits = " ".join(st["criteria"])
            present = re.search(r"(?<!not )at\(\$\w+\)", crits) or "present(" in crits or "event:" in crits \
                or all(re.match(r"^(not )?(has|holds)\(pc,", c) for c in st["criteria"]) \
                or st["action"].get("do") == "bring_in"      # arrivals land where the player stands
            if "perceptible" in tell or "teller" in tell:
                assert present, f"{sid}/{st['id']} tells the player something they could not witness"
            else:
                assert "silent" in tell, f"{sid}/{st['id']}"


# --- the errand, played --------------------------------------------------------------------

def test_the_errand_opens_after_a_day_at_the_market_and_the_witness_speaks():
    s, e, pc = _table()
    _wait(e, 1)
    assert not [i for i in s.schemes if i["scheme"] == "a-small-favour"], "not on the first tick"
    res = _open_errand(e)
    inst = _instance(s)
    slots = inst["slots"]
    for name in ("giver", "victim", "witness", "captain"):
        assert slots[name]["kind"] == "actor" and s.people[slots[name]["ref"]].name
    assert slots["patron"]["kind"] == "faction" and slots["patron"]["name"]
    assert s.people[slots["giver"]["ref"]].at == MARKET
    assert s.people[slots["captain"]["ref"]].at == f"{TOWN}~urban:the-gate"
    assert slots["errand"]["name"]
    q = next(c for c in cards.quests(s) if c.origin == "scheme:a-small-favour")
    assert len(q.objectives) == 3 and slots["errand"]["name"] in q.title
    assert pc.has_state("knows.giver-uneasy")
    # The witness's aside fires on the open tick, where the player stands.
    assert "witness-speaks" in inst["fired"] and pc.has_state("knows.victim-named")
    assert any(s.people[slots["victim"]["ref"]].name in o.tell for o in _told(res))
    # Nothing names anyone the world does not know: the secret card is filled in words.
    plan = cards.find(s, inst["cards"]["plan"])
    assert plan.secret and slots["patron"]["name"] in " ".join(plan.facts)


def test_the_honest_path_returning_within_the_hour_fires_nothing():
    """Back at the market inside the hour: the giver is there, unhidden, the victim
    alive, and no step of the errand has fired beyond the witness's aside."""
    s, e, pc = _table()
    _open_errand(e)
    inst = _instance(s)
    giver = s.people[inst["slots"]["giver"]["ref"]]
    victim = s.people[inst["slots"]["victim"]["ref"]]
    _travel(e, "the gate")
    _wait(e, 30)
    _travel(e, "the market")
    _wait(e, 1)
    assert set(inst["fired"]) == {"witness-speaks"}
    assert giver.at == MARKET and not giver.has_state("state.hidden")
    assert not victim.has_state("state.down")
    assert not pc.has_state("knows.betrayed") and inst["outcome"] == ""


def test_the_betrayal_path_the_guards_arrive_and_the_player_is_named():
    """Leave, gather, wait past the hours, come back with the item: the giver hid
    (silent), the victim died at the lodging (silent, gossip queued), the guards come
    into the market (perceptible), the errand fails, and the pc holds knows.betrayed
    and the suspected state through the applicator; Wanted opens on the next tick."""
    s, e, pc = _table()
    _open_errand(e)
    inst = _instance(s)
    giver = s.people[inst["slots"]["giver"]["ref"]]
    victim = s.people[inst["slots"]["victim"]["ref"]]
    captain = s.people[inst["slots"]["captain"]["ref"]]
    people_before = len(s.people)
    res = _out(e, inst)
    assert "reached" in inst["fired"]
    res = _wait(e, 61)
    assert "giver-hides" in inst["fired"] and giver.at == LODGING and giver.has_state("state.hidden")
    assert not _told(res), "hiding is out of sight"
    schemes.hand_item(s, pc, inst["slots"]["errand"]["name"])
    _wait(e, 1)
    assert "gathered" in inst["fired"]
    res = _wait(e, 3 * 60)
    assert "killed" in inst["fired"] and inst["fired"]["killed"]["silent"]
    assert victim.at == LODGING and victim.has_state("state.down.dead")
    assert not _told(res), "the killing is off-stage"
    assert inst["news"] and inst["news"][0]["carrier"] == "gossip"
    plan = cards.find(s, inst["cards"]["plan"])
    assert any("killed" in f for f in plan.facts)
    res = _travel(e, "the market")
    assert "guards-arrive" in inst["fired"] and inst["outcome"] == "betrayed"
    told = _told(res)
    assert told and captain.name in told[0].tell and victim.name in told[0].tell
    assert captain.at == MARKET
    assert len(s.people) == people_before + 2, "two guards brought in"
    assert pc.has_state("knows.betrayed") and pc.has_state("state.suspected")
    eff = next(x for x in pc.effects if "knows.betrayed" in x.tags)
    assert eff.source == "scheme:a-small-favour/betrayed"
    errand = cards.find(s, inst["cards"]["errand"])
    assert not errand.live and any("named you" in f for f in errand.facts)
    # Wanted opens on the tag, on the next tick, and the wanted state is granted.
    _wait(e, 1)
    q2 = _instance(s, "wanted")
    assert pc.has_state("state.wanted") and "notice" in q2["fired"]


def test_the_exposed_path_reaching_the_lodging_early_collapses_the_plan():
    s, e, pc = _table()
    _open_errand(e)
    inst = _instance(s)
    giver = s.people[inst["slots"]["giver"]["ref"]]
    victim = s.people[inst["slots"]["victim"]["ref"]]
    _out(e, inst)
    _wait(e, 61)
    assert giver.has_state("state.hidden")
    res = _travel(e, LODGING_NAME)
    assert "exposed" in inst["fired"] and inst["outcome"] == "exposed"
    assert any(giver.name in o.tell for o in res.outcomes if o.op == "scheme")
    assert pc.has_state("knows.giver-lied") and pc.has_state("knows.giver-to-find")
    assert not victim.has_state("state.down") and victim.has_state("attitude.friendly")
    assert "killed" not in inst["fired"]
    # The one who paid opens early, on the tag.
    _wait(e, 1)
    assert _instance(s, "the-one-who-paid")


def test_the_fairness_gate_holds_the_guards_back_without_the_witnesss_word():
    """Strip the witness's word: the guards do not come, and the log says why."""
    s, e, pc = _table()
    _open_errand(e)
    inst = _instance(s)
    pc.remove_effects(match=lambda x: "knows.victim-named" in x.tags)
    _out(e, inst)
    _wait(e, 61)
    schemes.hand_item(s, pc, inst["slots"]["errand"]["name"])
    _wait(e, 1)
    _wait(e, 3 * 60)
    _travel(e, "the market")
    assert "guards-arrive" not in inst["fired"]
    assert any(sk["step"] == "guards-arrive" and "knows.victim-named" in sk["why"]
               for sk in inst["skipped"])


# --- the line after the errand --------------------------------------------------------------

def _betrayed(e, s, pc):
    _open_errand(e)
    inst = _instance(s)
    _out(e, inst)
    _wait(e, 61)
    schemes.hand_item(s, pc, inst["slots"]["errand"]["name"])
    _wait(e, 1)
    _wait(e, 3 * 60)
    _travel(e, "the market")
    _wait(e, 1)
    return inst


def _two_clues(e, s, pc):
    """At the lodging, by salience: the witness's word (three criteria), the way out
    the witness offers (four), the ledger (three), then the two clues together."""
    _travel(e, LODGING_NAME)
    _wait(e, 1)
    _wait(e, 1)
    _wait(e, 1)
    _wait(e, 1)                        # the one who paid opens on the tag
    return _instance(s, "the-one-who-paid")


def _named(e, s, pc):
    q3 = _two_clues(e, s, pc)
    _out(e, q3)
    _wait(e, 1)                        # named: the patron
    _wait(e, 1)                        # the patron opens on the tag
    return _instance(s, "the-patron")


def test_two_clues_at_the_lodging_open_the_one_who_paid():
    s, e, pc = _table()
    _betrayed(e, s, pc)
    q2 = _instance(s, "wanted")
    res = _travel(e, LODGING_NAME)
    assert "witness-word" in q2["fired"] and pc.has_state("knows.clue.witness")
    assert any("will say so" in o.tell for o in _told(res, "wanted"))
    _wait(e, 1)
    assert "way-out" in q2["fired"] and pc.has_state("knows.way-past-gate"), "four criteria beat three"
    _wait(e, 1)
    assert "ledger" in q2["fired"] and pc.has_state("knows.clue.ledger")
    _wait(e, 1)
    assert q2["outcome"] == "two-clues" and pc.has_state("knows.giver-to-find")
    _wait(e, 1)
    q3 = _instance(s, "the-one-who-paid")
    giver3 = s.people[q3["slots"]["giver"]["ref"]]
    _out(e, q3)
    assert "found" in q3["fired"]
    _wait(e, 1)
    assert "named" in q3["fired"] and pc.has_state("knows.patron-named")
    _wait(e, 61)
    assert q3["outcome"] == "taken" and giver3.has_state("attitude.friendly")
    assert pc.has_state("holds.debt.giver")


def test_justice_at_the_market_with_the_proof():
    s, e, pc = _table()
    _betrayed(e, s, pc)
    q4 = _named(e, s, pc)
    _travel(e, _named_kind("guildhall"))
    assert "books" in q4["fired"]
    _wait(e, 1)
    assert "proof" in q4["fired"] and pc.has_state("knows.proof-held")
    before = pc.xp
    _travel(e, "the market")
    assert q4["outcome"] == "justice" and pc.xp > before
    assert pc.has_state("knows.name-cleared") and pc.has_state("knows.patron-ended")
    captain4 = s.people[q4["slots"]["captain"]["ref"]]
    assert captain4.has_state("attitude.helpful")
    # The price on your head never opens on this path: its tag is failure's alone.
    _wait(e, 1)
    assert not [i for i in s.schemes if i["scheme"] == "the-price-on-your-head"]


# --- the gaps, named -------------------------------------------------------------------------

def test_the_suspected_state_names_the_town():
    s, e, pc = _table()
    _betrayed(e, s, pc)
    assert pc.has_state(f"state.suspected.{TOWN}")


def test_justice_lifts_the_wanted_state():
    s, e, pc = _table()
    _betrayed(e, s, pc)
    q4 = _named(e, s, pc)
    _travel(e, _named_kind("guildhall"))
    _wait(e, 1)
    _travel(e, "the market")
    assert q4["outcome"] == "justice"
    assert not pc.has_state("state.wanted")


def test_the_later_schemes_share_the_errands_people():
    s, e, pc = _table()
    q1 = _betrayed(e, s, pc)
    q2 = _instance(s, "wanted")
    assert q2["slots"]["giver"]["ref"] == q1["slots"]["giver"]["ref"]
    assert q2["slots"]["victim"]["ref"] == q1["slots"]["victim"]["ref"]


def test_a_slug_bearing_tag_and_a_family_grant_are_what_the_validator_allows():
    """The gap, closed the same day it was named: `$town` in a tag is the settlement's
    own leaf, spelled by `states.town_tag` at grant time and never authored; the
    family root is still accepted; and `has(pc, state.wanted)` matches the family by
    prefix. A digit-bearing tag is still refused."""
    doc = json.loads(json.dumps(schemes.shipped()["a-small-favour"]))
    doc["outcomes"]["betrayed"]["grants"][0]["tags"] = ["state.suspected.$town"]
    assert not any("not a tag" in p for p in schemes.validate(doc))
    doc["outcomes"]["betrayed"]["grants"][0]["tags"] = ["State.Suspected"]
    assert any("not a tag" in p for p in schemes.validate(doc))
    from rules import states
    assert states.matches("state.wanted.somewhere", "state.wanted")
