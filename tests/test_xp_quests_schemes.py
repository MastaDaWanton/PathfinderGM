"""Experience paid for what happened, and only once: quests, schemes and the watcher.

Measured on the owner's 0.2.25 save (Corvin, 2026-11-01), the character went from level 1
to level 3 in about two game days, almost none of it for anything done:

* **800 XP for resting.** "find a place to rest" at the shrine came back as a
  `quest_step` for "Go out by the edge" — the player never left town — and the engine
  ticked it and paid "seeing a matter through", because `_op_quest_step` checked only that
  the objective existed and was not done. A repro finished "What a faction within Ashgate
  Reach holds" from the marsh with three bare `quest_step`s for 1,600 XP.
* **1,700 XP for one note.** The watcher paid a story award every time it rewrote its
  private undercurrent — seven times for the same stallholder's grip on the same sleeve —
  and three more for "advancing" or "resolving" scheme cards the engine still had running.
* **Clues that were not things.** "Examine the coin more closely" was refused "not
  carrying the coin": a scheme clue is a `knows.clue.*` tag, never an item.
* **The wrong Ashbourne.** "Search … for Kwolla Ashbourne" was answered with Glib
  Ashbourne, in another town, on one shared word.

Synthetic scenes only: the owner's save is private.
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from rules import cards, schemes, scope, tracking
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "58b90a214ada"
MARKET = f"{TOWN}~urban:the-market"


@pytest.fixture(autouse=True)
def schemes_on(monkeypatch):
    monkeypatch.setattr(schemes, "ENABLED", True)


# A quest the player owns from its first tick (it opens on what they know, as the wanted
# line's "Leave by the edge" does), whose objectives the engine can measure: a place to
# reach, a thing to hand over.
EDGE = {
    "id": "edge-probe", "title": "Edge probe",
    "opens": ["has(pc, knows.probe-open)"],
    "slots": {"market": {"place": "market"}, "gate": {"place": "gate"},
              "giver": {"role": "trader", "level": "pc", "prefer": "cast", "at": "$market"}},
    "cards": [{"key": "road", "kind": "quest", "title": "Leave by the gate before the watch",
               "giver": "$giver",
               "objectives": ["Go out by $gate", "Hand the pass to $giver",
                              "Decide what to tell the watch"]}],
    "steps": [
        {"id": "out", "criteria": ["at($gate)", "has(pc, knows.probe-open)"],
         "action": {"do": "objective", "card": "road", "n": 1},
         "tell": {"perceptible": "You are out past $gate."}},
        {"id": "handed", "criteria": ["event:give($giver)"],
         "action": {"do": "objective", "card": "road", "n": 2},
         "tell": {"perceptible": "$giver takes the pass."}}],
}


def _table(monkeypatch, doc=EDGE, *, owned=True):
    monkeypatch.setattr(schemes, "all_schemes", lambda: {doc["id"]: doc})
    s = Scene(location_id=TOWN)
    pc = load_pc("fixtures/pc-kesst.json")
    from rules import survival

    for need in (survival.NO_SLEEP, survival.NO_FOOD, survival.NO_WATER):
        pc.overrides[need] = True
    s.add(pc)
    if owned:
        pc.apply_effect(ActiveEffect(name="probe", kind="situation", key="probe",
                                     source="author:test", origin="author:test",
                                     duration="until-dismissed",
                                     tags=("knows.probe-open",)))
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party(MARKET)
    inst = schemes.open_scheme(e, doc, turn=1)
    return s, e, pc, inst


def _run(e, *raws):
    return e.run(e.validate([{"actor": "pc", "because": "t", **r} for r in raws],
                            origin="author:test"))


def _step(e, card_id, n):
    return _run(e, {"op": "quest_step", "params": {"quest": card_id, "objective": n,
                                                   "note": "done"}}).outcomes


# --- 1. a quest_step is a claim the engine checks -----------------------------------------

def test_resting_in_town_does_not_finish_going_out_by_the_gate(monkeypatch):
    """The 800 XP: a `quest_step` for "Go out by the edge" while the player rested at the
    shrine. Refused, with what is missing in words; no XP; nothing ticked."""
    s, e, pc, inst = _table(monkeypatch)
    card = cards.find(s, inst["cards"]["road"])
    assert cards.standing(card) == cards.OWN
    xp = pc.xp
    out = _step(e, card.id, 1)[0]
    assert out.status == "refused"
    assert "is not at the gate" in out.tell, out.tell
    assert pc.xp == xp
    assert not cards.find(s, card.id).objectives[0]["done"]


def test_three_bare_steps_finish_nothing(monkeypatch):
    """The 1,600 XP repro: every objective claimed from where none of them was done."""
    s, e, pc, inst = _table(monkeypatch)
    card_id = inst["cards"]["road"]
    xp = pc.xp
    outs = [_step(e, card_id, n)[0] for n in (1, 2, 3)]
    assert [o.status for o in outs] == ["refused"] * 3, [o.tell for o in outs]
    assert "has not handed anything to" in outs[1].tell
    assert "settled by how the matter ends" in outs[2].tell, "no step ticks it: not claimable"
    assert pc.xp == xp and cards.find(s, card_id).live


def test_where_it_is_true_the_schemes_own_step_ticks_it(monkeypatch):
    """At the gate the claim is true, and is passed over in silence: the scheme's step
    fires after the batch with its own tell, so the planner's word never jumps the
    scheme's ending (or pays its own award on top)."""
    s, e, pc, inst = _table(monkeypatch)
    card_id = inst["cards"]["road"]
    res = _run(e, {"op": "travel", "params": {"place": "the gate"}},
               {"op": "quest_step", "params": {"quest": card_id, "objective": 1}})
    step = next(o for o in res.outcomes if o.op == "quest_step")
    assert step.status != "refused" and step.tell == ""
    assert step.effects[0].get("engine_owns") and "objective" not in step.effects[0]
    assert cards.find(s, card_id).objectives[0]["done"]
    assert any(o.op == "scheme" and "out past" in o.tell for o in res.outcomes)


def test_a_hand_over_earlier_in_the_batch_is_what_makes_the_claim_true(monkeypatch):
    """`event:give($giver)` asked of the batch so far (`Engine._so_far`)."""
    s, e, pc, inst = _table(monkeypatch)
    card_id = inst["cards"]["road"]
    giver = inst["slots"]["giver"]["ref"]
    pc.goods["travel pass"] = 1
    res = _run(e, {"op": "give", "params": {"item": "travel pass", "to": giver}},
               {"op": "quest_step", "params": {"quest": card_id, "objective": 2}})
    step = next(o for o in res.outcomes if o.op == "quest_step")
    assert step.status != "refused", step.tell
    assert cards.find(s, card_id).objectives[1]["done"]


def test_a_quest_never_taken_on_cannot_be_stepped(monkeypatch):
    """A scheme that starts a story opens its quest unheard (docs/known-matters.md); a
    `quest_step` on it is refused before anything else is asked."""
    fresh = dict(EDGE, id="edge-fresh", opens=["at($market)"],
                 steps=[dict(EDGE["steps"][0], criteria=["at($gate)"])])
    s, e, pc, inst = _table(monkeypatch, fresh, owned=False)
    card = cards.find(s, inst["cards"]["road"])
    assert cards.standing(card) == cards.UNHEARD
    out = _step(e, card.id, 1)[0]
    assert out.status == "refused" and "never taken on" in out.tell


def test_an_outcome_pays_only_for_a_quest_the_player_took(monkeypatch):
    """The sickness's `in-time` on the owner's save resolved a quest never heard of; its
    tell was hushed (the owner's answer 7) and its award was credited anyway."""
    doc = {
        "id": "pay-probe", "title": "Pay probe", "opens": ["at($market)"],
        "slots": {"market": {"place": "market"}, "gate": {"place": "gate"}},
        "cards": [{"key": "q", "kind": "quest", "title": "A probe errand",
                   "objectives": ["Go out by $gate"]}],
        "steps": [{"id": "out", "criteria": ["at($gate)"],
                   "action": {"do": "objective", "card": "q", "n": 1},
                   "also": [{"do": "outcome", "name": "done"}],
                   "tell": {"perceptible": "Out past $gate."}}],
        "outcomes": {"done": {"resolve": "q", "award": "new"}},
    }
    s, e, pc, inst = _table(monkeypatch, doc, owned=False)
    xp = pc.xp
    _run(e, {"op": "travel", "params": {"place": "the gate"}})
    assert inst.get("outcome") == "done"
    assert pc.xp == xp, "paid for a matter the player never took on"


def test_an_event_step_is_not_lost_behind_a_standing_one(monkeypatch):
    """A step keyed on this batch's event outranks one keyed on standing state: in the
    sick room the sickness's four-criterion `seen` would have beaten the hand-over until
    it fired, and the herb, given, would have been gone with the quest left open."""
    assert schemes._rank({"criteria": ["event:give($sick, $herb)", "alive($sick)"]}) > \
        schemes._rank({"criteria": ["at($lodging)", "present($sick)", "alive($sick)",
                                    "has(pc, knows.what-the-herb-is)"]})


def test_the_grammar_knows_taken_and_a_given_thing():
    assert schemes.validate(dict(EDGE, steps=EDGE["steps"] + [
        {"id": "t", "criteria": ["taken(road)", "event:give($giver, $gate)"],
         "action": {"do": "fact", "card": "road", "text": "x"},
         "tell": {"perceptible": "y"}}])) == []
    bad = schemes.validate(dict(EDGE, steps=[
        {"id": "t", "criteria": ["taken(nothing)", "at($market)"],
         "action": {"do": "fact", "card": "road", "text": "x"}, "tell": {"perceptible": "y"}}]))
    assert any("taken() takes a quest card's key" in p for p in bad), bad


def test_every_shipped_return_objective_asks_for_a_hand_over():
    """Give and return objectives need a real give: the steps that tick them read
    `event:give`, never `holds` beside `present` (the walk-in that ticked the sickness)."""
    docs = schemes.shipped()
    for sid, card_key, n in (("the-sickness", "remedy", 2), ("the-lost-thing", "errand", 2),
                             ("a-small-favour", "errand", 3)):
        steps = schemes.ticking_steps(docs[sid], card_key, n)
        assert steps, (sid, card_key, n)
        for st in steps:
            assert any(c.startswith("event:give(") for c in st["criteria"]), (sid, st["id"])


# --- 2. the watcher pays once per thread and step -----------------------------------------

@pytest.fixture
def campaign(tmp_path):
    from gm import watcher
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        watcher._reset()
        yield cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        cm._LIVE.clear()
        watcher._reset()


def _rewrite(c, sentence, action="advance"):
    from gm import watcher

    i = watcher._find_note(c.history)
    was = str(c.history[i].get("content", "")) if i >= 0 else ""
    return watcher._apply_undercurrent(c, {"was": was, "sentence": sentence,
                                           "action": action, "thread": "the old note"})


def test_one_recycled_note_pays_once_not_seven_times(campaign):
    """The 1,700 XP: seven rewrites of one private note, each paid as an advance."""
    c = campaign
    pc = c.scene.pc()
    xp = pc.xp
    for i in range(7):
        assert _rewrite(c, f"The stallholder's grip on your sleeve tightens again, take {i}.")
    from rules import xp as xp_mod

    assert pc.xp - xp == xp_mod.story_award(pc.level, "advance")
    lines = [t for t in c.transcript if "XP" in str(t.get("text", ""))]
    assert len(lines) == 1
    assert "stallholder" not in lines[0]["text"], "the GM's private note printed on the page"


def test_a_thread_ends_once_and_only_after_it_moved(campaign):
    c = campaign
    pc = c.scene.pc()
    xp = pc.xp
    _rewrite(c, "A new thread nobody has moved yet begins here.", action="new")
    assert pc.xp == xp, "an ending paid for a thread that never moved"
    _rewrite(c, "The second thread moves a step along now.")
    moved = pc.xp
    assert moved > xp
    _rewrite(c, "The second thread is over and a third begins.", action="new")
    ended = pc.xp
    assert ended > moved
    _rewrite(c, "The third thread is called over before it moved.", action="new")
    assert pc.xp == ended


def test_the_watcher_cannot_close_or_fill_a_schemes_card(campaign):
    """Three scheme cards — two secret — were advanced or resolved by the watcher on the
    owner's save and paid 200 XP each while their schemes still ran."""
    from gm import watcher

    c = campaign
    pc = c.scene.pc()
    card = cards.open_card(c.scene, cards.Card(
        id="scheme-probe-plan-1", title="The giver's plan", origin="scheme:probe",
        secret=True, clock_max=2, people=[]), turn=0)
    xp = pc.xp
    for _ in range(4):
        now = cards.find(c.scene, card.id)
        watcher._apply_cards(c, {"changes": [{"id": card.id, "action": "advance",
                                              "fact": "The giver's plan moves along.",
                                              "was": [now.stage, now.clock]}]})
    now = cards.find(c.scene, card.id)
    assert "The giver's plan moves along." in now.facts, "the advance itself was refused"
    assert now.live and now.clock == 0
    watcher._apply_cards(c, {"changes": [{"id": card.id, "action": "resolve", "fact": "",
                                          "was": [now.stage, now.clock]}]})
    assert cards.find(c.scene, card.id).live
    assert pc.xp == xp


# --- 3, 6. a clue is a record --------------------------------------------------------------

def test_examining_a_clue_answers_with_what_was_found(monkeypatch):
    """"Examine the coin more closely" was refused "not carrying the coin"."""
    s, e, pc, inst = _table(monkeypatch)
    inst["fired"]["coin"] = {"clock": 0, "turn": 0, "silent": False,
                             "tell": "Sewn into the coat is coin struck with a faction's mark."}
    pc.apply_effect(ActiveEffect(name="coin", kind="situation",
                                 key="scheme:edge-probe/coin:knows.clue.coin",
                                 source="scheme:edge-probe/coin", origin="scheme:edge-probe/coin",
                                 duration="until-dismissed", tags=("knows.clue.coin",)))
    out = _run(e, {"op": "judge", "params": {"item": "the coin"}}).outcomes[0]
    assert out.status != "refused", out.tell
    assert "faction's mark" in out.tell
    assert out.effects[0]["kind"] == "clue" and out.effects[0]["origin"] == "scheme:edge-probe/coin"
    nothing = _run(e, {"op": "judge", "params": {"item": "the dagger of kings"}}).outcomes[0]
    assert nothing.status == "refused"


# --- 5. a whole name before a shared word ---------------------------------------------------

def test_a_whole_name_is_the_one_meant_not_a_shared_surname():
    """"Search … for Kwolla Ashbourne" answered "Glib Ashbourne, fleet pilot, is in
    Reedsink" twice: the world was asked before the scene's own people, on one word."""
    s = Scene(location_id=TOWN)
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    e = Engine(s, Dice(seed=1), world=WORLD)
    e.place_party(MARKET)
    glib = instantiate("guildhand", scene=s, name="Glib Ashbourne")
    kwolla = instantiate("guildhand", scene=s, name="Kwolla Ashbourne")
    s.add(glib)
    s.add(kwolla)
    s.move(glib.ref, f"{TOWN}~urban:the-gate")
    s.move(kwolla.ref, f"{TOWN}~grassland:@the-fields")
    got = scope.look_for(WORLD, "Kwolla Ashbourne", s, TOWN)
    assert got["scope"] == scope.ELSEWHERE and got["who"] == "Kwolla Ashbourne", got
    assert "Glib" not in got["line"]
    assert tracking.quarry_of(s, "Kwolla Ashbourne", world=WORLD) == {
        "ref": kwolla.ref, "name": "Kwolla Ashbourne"}
    # A shared word alone names nobody in particular.
    assert scope.held_by_whole_name(s, "Ashbourne") == ""


def test_the_worlds_roll_prefers_the_whole_name():
    class Ent:
        def __init__(self, eid, name, parent):
            self.id, self.name, self.parent_id, self.kind = eid, name, parent, "CHARACTER"
            self.facts = {}

    class World:
        entities = {"a": Ent("a", "Glib Ashbourne", TOWN), "b": Ent("b", "Kwolla Ashbourne", "x")}

        def get(self, eid):
            return {"x": type("P", (), {"name": "Elsewhere"})()}.get(eid)

    got = scope.look_for(World(), "Kwolla Ashbourne", None, TOWN)
    assert got["who"] == "Kwolla Ashbourne", got
