"""What the three critics found on the scheme runner, pinned (2026-09-08).

Phase 4 of docs/quest-schemes-plan.md: a fairness critic, a leak critic and a
three-laws critic each read the merged work with one lens and reported verified
findings. Each test here names one finding and the measurement behind it, so the fix
cannot be lost by the next person.
"""
from __future__ import annotations

import pytest

from gm import prompts
from rules import cards, keepers, provenance, schemes, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"
MARKET = f"{TOWN}~urban:the-market"


@pytest.fixture(autouse=True)
def schemes_on(monkeypatch):
    monkeypatch.setattr(schemes, "ENABLED", True)


def _table():
    s = Scene(location_id=TOWN)
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party(MARKET)
    return s, e, pc


def _hide(actor):
    actor.apply_effect(ActiveEffect(name="hidden", kind="situation", key="t:hidden",
                                    source="t", origin="t", duration="until-dismissed",
                                    tags=("state.hidden",)))


# --- the leak critic ------------------------------------------------------------------------

def test_a_hidden_person_is_not_in_the_narrators_room():
    """Leak finding 1: the giver, hidden at the lodging, was listed in WHO IS HERE beside
    the corpse while the engine held him hidden — the narrator handed a presence the
    character could not know."""
    s, e, pc = _table()
    marra = s.add(instantiate("guildhand", s, name="Marra Vell"))
    brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN), here=e.here(), known=e.places())
    assert "Marra Vell" in brief
    _hide(marra)
    brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN), here=e.here(), known=e.places())
    assert "Marra Vell" not in brief.split("WHO IS HERE")[1].split("\n\n")[0]


def test_the_travel_tell_does_not_name_the_hidden_or_the_dead_left_behind():
    """Leak finding 4: "Left behind: Ariniel Thorne, Arinthal Lyrien" — the hidden giver
    and the corpse — and the line stuck to the visible card."""
    s, e, pc = _table()
    seen = s.add(instantiate("guildhand", s, name="Seen Person"))
    hid = s.add(instantiate("guildhand", s, name="Hidden Person"))
    _hide(hid)
    intents = e.validate([{"op": "travel", "actor": "pc", "because": "t",
                           "params": {"place": "the gate"}}], origin="author:test")
    out = e.run(intents).outcomes[0]
    assert "Seen Person" in out.tell and "Hidden Person" not in out.tell


def test_gossip_is_never_carried_by_the_hidden_or_the_dead():
    """Leak finding 2: the hidden giver of the murder narrated the murder as gossip."""
    s, e, pc = _table()
    inst = {"slots": {"giver": {"kind": "actor", "ref": "x"}}}
    hid = s.add(instantiate("guildhand", s, name="Hidden Giver"))
    inst["slots"]["giver"]["ref"] = hid.ref
    _hide(hid)
    # The market has a stallholder in it since 2026-09-16 (`rules/keepers.py`), and she
    # would carry the news perfectly well — which is right, and is not what is under
    # test. The question here is whether the HIDDEN giver can, so the room is emptied
    # of everybody who is not hiding.
    for keep in [a for a in list(e.scene.actors.values())
                 if keepers.is_keeper(a.world_entity_id or "")]:
        e.scene.depart(keep.ref)
    ok, how = schemes._news_arrives(e, inst, {"carrier": "gossip", "says": "x"})
    assert not ok, "nobody visible to hear it from"
    other = s.add(instantiate("guildhand", s, name="Passer By"))
    ok, how = schemes._news_arrives(e, inst, {"carrier": "gossip", "says": "x"})
    assert ok and "Passer By" in how and "Hidden Giver" not in how


def test_a_silent_steps_award_is_banked_until_a_perceptible_tell():
    """Leak finding 3: a silent step's XP line was emitted as a visible tell, telling the
    player the price on their head was withdrawn out of sight."""
    from rules.engine import Outcome

    s, e, pc = _table()
    doc = {"id": "probe", "title": "Probe", "slots": {"market": {"place": "market"}},
           "cards": [{"key": "q", "kind": "quest", "title": "A probe quest", "objectives": ["x"]}],
           "steps": [
               {"id": "offstage", "criteria": ["not at($market)", "since(open) >= 1h"],
                "action": {"do": "outcome", "name": "done"}, "tell": {"silent": "it happened"}},
               {"id": "seen", "criteria": ["at($market)", "has(pc, knows.done)"],
                "action": {"do": "fact", "card": "q", "text": "word reaches you"},
                "tell": {"perceptible": "Word reaches you."}}],
           "outcomes": {"done": {"resolve": "q", "award": "new",
                                 "grants": [{"to": "pc", "tags": ["knows.done"]}]}}}
    assert schemes.validate(doc) == []
    # An authored scheme arrives as a file on the bench; the tick steps only what it
    # can load, so the probe is written there for the length of the test.
    import json as _json
    path = schemes.homebrew_dir(make=True) / "probe.json"
    path.write_text(_json.dumps(doc), encoding="utf-8")
    try:
        _banked_body(s, e, pc, doc)
    finally:
        path.unlink()


def _banked_body(s, e, pc, doc):
    inst = schemes.open_scheme(e, doc)
    before = pc.xp
    intents = e.validate([{"op": "travel", "actor": "pc", "because": "t", "params": {"place": "the gate"}}], origin="author:test")
    e.run(intents)
    res = e.run(e.validate([{"op": "advance_time", "actor": "pc", "because": "t",
                             "params": {"amount": 61, "unit": "minutes"}}], origin="author:test"))
    assert "offstage" in inst["fired"] and pc.xp > before
    assert not [o for o in res.outcomes if o.op == "scheme" and o.tell], "silent stays silent"
    assert cards.quests(s)[0].live, "the resolution waits for the player to learn it"
    # Back at the market the perceptible step fires on the arrival tick, carrying the
    # banked line and landing the deferred resolution.
    res = e.run(e.validate([{"op": "travel", "actor": "pc", "because": "t", "params": {"place": "the market"}}], origin="author:test"))
    told = [o.tell for o in res.outcomes if o.op == "scheme"]
    assert told and "Word reaches you." in told[0] and "XP" in told[0]
    assert not cards.quests(s)[0].live


# --- the three-laws critic ---------------------------------------------------------------------

def test_the_watchman_carries_the_laws_tag_and_the_reader_asks_only_the_tag():
    """Three-laws finding 1: `_law_joins` decided who is the law by template string
    because `role.guard` had a reader and no writer."""
    s, e, pc = _table()
    w = s.add(instantiate("watchman", s))
    assert w.has_state(states.GUARD)
    import inspect
    from rules import engine as engine_mod
    src = inspect.getsource(engine_mod.Engine._law_joins)
    assert 'from_template == "watchman"' not in src


def test_a_schemes_provenance_is_a_kind_the_provenance_module_knows():
    """Three-laws finding 2: `scheme:` was stamped as an origin the provenance module
    refused as well-formed."""
    assert provenance.well_formed("scheme:a-small-favour/betrayed")
    assert provenance.well_formed("card:salt-levy")
    assert provenance.well_formed("place:t~urban:the-market")


def test_a_scheme_may_not_grant_a_state_that_stops_actions_or_ends_on_rest():
    """Three-laws finding 6: a document granting `state.down.dead` validated clean."""
    doc = {"id": "bad", "title": "Bad", "slots": {"market": {"place": "market"}},
           "cards": [], "steps": [{"id": "s", "criteria": ["at($market)"],
                                   "action": {"do": "grant", "to": "pc", "tags": ["state.down.dead"]},
                                   "tell": {"perceptible": "x"}}],
           "outcomes": {"o": {"grants": [{"to": "pc", "tags": ["recovery.rest"]}]}}}
    problems = schemes.validate(doc)
    assert any("state.down.dead" in p and "may grant" in p for p in problems)
    assert any("recovery.rest" in p for p in problems)


def test_town_on_a_tag_is_the_town_the_scheme_opened_in():
    """Three-laws finding 5: `$town` read the ground the player stood on at grant
    time, so a removal after a travel missed."""
    s, e, pc = _table()
    inst = {"slots": {}, "town": "elsewhere-town"}
    tags = schemes._tags_of(s, {"tags": ["state.wanted.$town"]}, inst)
    assert tags == (states.wanted_tag("elsewhere-town"),)


# --- the fairness critic ---------------------------------------------------------------------------

def test_a_framing_step_needs_fairness_whatever_its_tell_says():
    """Fairness finding 1: `guards-arrive` with its fairness list deleted validated clean,
    because the twist detector read words in the tell."""
    import copy
    doc = copy.deepcopy(schemes.shipped()["a-small-favour"])
    st = next(x for x in doc["steps"] if x["id"] == "guards-arrive")
    st.pop("fairness", None)
    assert any("guards-arrive" in p and "foreshadow" in p for p in schemes.validate(doc))


def test_the_foreshadowing_is_on_the_brief_in_words():
    """Fairness finding 2: `knows.giver-uneasy` was a tag the brief never rendered."""
    s, e, pc = _table()
    doc = schemes.shipped()["a-small-favour"]
    inst = schemes.open_scheme(e, doc)
    brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN), here=e.here(), known=e.places())
    assert "What they have noticed" in brief and "would not meet your eye" in brief


def test_a_step_keyed_only_on_another_persons_state_is_not_player_changeable():
    """Fairness finding 11: `killed` rewritten to `alive($victim)` + a clock validated."""
    import copy
    doc = copy.deepcopy(schemes.shipped()["a-small-favour"])
    st = next(x for x in doc["steps"] if x["id"] == "killed")
    st["criteria"] = ["alive($victim)", "since(open) >= 3h"]
    assert any("killed" in p and "could change" in p for p in schemes.validate(doc))


# --- the playtest agent (2026-09-08) ---------------------------------------------------------------

def test_a_foraged_ingredient_counts_as_held():
    """Playtest finding 2: `holds(pc, $errand)` read the crafted shelf only; foraging
    writes the satchel, so the frame could never fire from real play."""
    s, e, pc = _table()
    slot = {"kind": "item", "id": "pennyroyal", "name": "Pennyroyal"}
    assert not schemes._holds(pc, slot)
    pc.carry("pennyroyal", 2)
    assert schemes._holds(pc, slot)


def test_news_arrives_across_requests_not_only_within_one_engine():
    """Playtest finding 3: the tick counter lived on an Engine the live app rebuilds
    per request, so it read 1 forever and news born on tick 1 never arrived."""
    import json as _json

    s, e, pc = _table()
    doc = {"id": "probe2", "title": "Probe", "slots": {"market": {"place": "market"}},
           "cards": [{"key": "q", "kind": "quest", "title": "A probe quest", "objectives": ["x"]}],
           "steps": [{"id": "word", "criteria": ["at($market)", "since(open) >= 1h"],
                      "action": {"do": "news", "carrier": "crier", "reach": "town", "delay": "0h",
                                 "says": "Something happened."},
                      "tell": {"silent": "it happened"}}],
           "outcomes": {}}
    path = schemes.homebrew_dir(make=True) / "probe2.json"
    path.write_text(_json.dumps(doc), encoding="utf-8")
    try:
        inst = schemes.open_scheme(e, doc)
        wait = lambda eng, m: eng.run(eng.validate([{"op": "advance_time", "actor": "pc", "because": "t",
                                                     "params": {"amount": m, "unit": "minutes"}}], origin="author:test"))
        wait(e, 61)
        assert inst["news"] and "word" in inst["fired"]
        # A fresh engine on the same scene, as the next request would build.
        e2 = Engine(s, Dice(seed=4), world=WORLD)
        res = wait(e2, 1)
        told = [o.tell for o in res.outcomes if o.op == "scheme"]
        assert told and "Something happened." in told[0]
        assert not inst["news"]
    finally:
        path.unlink()


def test_a_role_no_cast_member_here_can_fill_is_never_named_after_the_role():
    """Playtest finding 1: with three cast members in the town and four roles, the
    victim was a man called "standing"."""
    s, e, pc = _table()
    doc = schemes.shipped()["a-small-favour"]
    inst = schemes.open_scheme(e, doc)
    for name, slot in inst["slots"].items():
        if slot.get("kind") == "actor":
            person = s.people[slot["ref"]]
            assert person.name.lower() not in ("standing", "companion", "guard officer", "trader", "kin"), (name, person.name)


def test_two_schemes_in_one_town_want_different_things_and_the_road_is_not_the_wild():
    """Playtest finding 7: the errand and the lost thing both asked for the same herb,
    and road and wild were one place."""
    s, e, pc = _table()
    a = schemes.open_scheme(e, schemes.shipped()["the-lost-thing"])
    b = schemes.open_scheme(e, schemes.shipped()["a-small-favour"])
    assert a["slots"]["lost"]["id"] != b["slots"]["errand"]["id"]
    assert b["slots"]["road"]["id"] != b["slots"]["wild"]["id"]


def test_travel_with_nowhere_named_is_a_printable_refusal():
    """Playtest finding 5: a travel with neither place nor biome passed validate and
    raised in run — three 502s in one session."""
    s, e, pc = _table()
    out = e.run(e.validate([{"op": "travel", "actor": "pc", "because": "t", "params": {"note": "back"}}],
                           origin="author:test")).outcomes[0]
    assert out.effects == [] and "where to" in out.tell and "the gate" in out.tell


def test_the_open_ground_is_reachable_by_the_name_the_card_uses():
    """Playtest finding 4: "the approach" on the quest card could not be travelled to
    by name from inside the town; only a travel by biome reached it."""
    s, e, pc = _table()
    out = e.run(e.validate([{"op": "travel", "actor": "pc", "because": "t", "params": {"place": "the heart of it"}}],
                           origin="author:test")).outcomes[0]
    assert out.effects, out.tell
    assert "the-heart-of-it" in s.at
    # New ground beats a same-ground place when the model sends both.
    e.place_party(MARKET)
    out = e.run(e.validate([{"op": "travel", "actor": "pc", "because": "t",
                             "params": {"biome": "grassland", "place": "the gate"}}], origin="author:test")).outcomes[0]
    assert "grassland" in s.at


def test_saying_you_wait_passes_the_time():
    """Playtest finding 6: "I wait at the market for ten hours" was narrate_only and the
    clock did not move, so a scheme keyed on the hours never came."""
    from gm import judgement

    s, e, pc = _table()
    raw = judgement.inject_wait([{"op": "narrate_only"}], "I wait at the market for ten hours.", s)
    assert raw and raw[-1]["op"] == "advance_time" and raw[-1]["params"]["amount"] == 600
    raw = judgement.inject_wait([], "We spend the whole day here.", s)
    assert raw[-1]["params"]["amount"] == 600
    assert judgement.inject_wait([], "How long would we wait?", s) == []
    assert judgement.inject_wait([{"op": "rest"}], "I rest here for an hour", s) == [{"op": "rest"}]
