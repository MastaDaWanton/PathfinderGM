"""Going home WITH somebody standing beside you, and a walk to nowhere said aloud.

The owner's save of 2026-11-05 (Pangrella, the market). Ariniel Thorne, a character the
world wrote, stood beside the player, helpful (a /cheat set it), with no home on record.
Four tries to go to "her private quarters" with her moved nobody:

  * row 56, "I follow Ariniel Thorne to her private quarters": read `follow: Ariniel
    Thorne` and `go, commit: intended, place: her private quarters`. The table built
    nothing ("intended, not done this turn: no op"); the plan walked a square toward her.
  * row 69, "Continue walking toward the quarters": read `go: the quarters`, ops [], a
    bare `narrate_only`, and the page said "You remain in the market".
  * and the engine had no route at all: `call_on` refuses a person who is here ("is here,
    with you; there is no need to go to their door").

These tests replay that shape on the fixture's own Pangrella and its own Ariniel Thorne,
with the readings copied from the save's turn_log (the save itself lives outside the repo).
"""
from __future__ import annotations

import copy
import json

from gm import acts_to_ops
from rules import attitude
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")
PANGRELLA = WORLD.by_name("Pangrella", kind="CITY").id
ARINIEL = next(e.id for e in WORLD.entities.values()
               if e.kind == "CHARACTER" and e.name == "Ariniel Thorne")
CLOCK = 9604            # the save's clock at row 56: day 7, four in the afternoon

# The readings, as the save's turn_log recorded them.
ROW_56 = {"question": False, "claims": [], "actions": [
    {"act": "follow", "target": "Ariniel Thorne", "span": "follow Ariniel Thorne"},
    {"act": "go", "commit": "intended", "place": "her private quarters",
     "span": "to her private quarters"}]}
ROW_69 = {"question": False, "claims": [], "actions": [
    {"act": "go", "place": "the quarters", "span": "Continue walking toward the quarters"}]}


def _market(helpful=True):
    s = Scene(location_id=PANGRELLA)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = CLOCK
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    market = next(p for p in e.places() if p.name == "the market")
    if s.at != market.id:
        e.run(e.validate([{"op": "travel", "params": {"place": market.name}}],
                         origin="author:test"))
    made = e._bring_in("guildhand", name="Ariniel Thorne", from_entity_id=ARINIEL)
    body = s.people[made[0]["ref"]]
    body.pronouns = "she/her"
    if helpful:
        # As the owner's /cheat did it (row 47): the condition, by the author's hand.
        e.run(e.validate([{"op": "condition",
                           "params": {"condition": "helpful", "to": body.ref}}],
                         origin="author:cheat"))
    else:
        attitude.set_regard(body, 45, "test")      # indifferent
    assert body.ref in s.actors
    return s, e, body


def _turn(e, frame, plan=None):
    """The reading through the table, the plan through `apply` and `nowhere_to_go`, as
    `GMAgent.plan_turn` runs them, and the engine on the result."""
    frame = copy.deepcopy(frame)
    rows = acts_to_ops.table(frame, e.scene, places=e.places())
    raw = acts_to_ops.apply(list(plan or [{"op": "narrate_only"}]), rows, frame, e.scene,
                            notes=[])
    raw = acts_to_ops.nowhere_to_go(raw, rows)
    return frame, rows, raw, e.run(e.validate(raw))


def _homes(s, ref):
    return [p for p in s.founded if p.get("owner") == ref and p.get("origin") == "home"]


def test_following_her_to_her_quarters_takes_you_home_with_her():
    """Row 56: the follow and the walk, with Ariniel helpful and no home on record. Before
    the fix the table built no op and the party stayed in the market; now her house is
    made off a street, and the player and she both end in it."""
    s, e, body = _market()
    assert not _homes(s, body.ref)
    _f, _rows, _raw, out = _turn(e, ROW_56)
    call = next(o for o in out.outcomes if o.op == "call_on")
    assert call.status == "resolved", call.tell
    homes = _homes(s, body.ref)
    assert len(homes) == 1
    assert s.at == homes[0]["id"] and body.at == s.at and body.ref in s.actors
    assert call.tell.startswith("Ariniel Thorne leads you to") and "lets you in" in call.tell
    # Shown the way is knowing it.
    assert s.pc().has_state(f"knows.home.{ARINIEL}")


def test_the_follow_and_go_reading_is_not_dropped_as_intended():
    """Row 56 again, at the table only: the go was read `intended`, and the table's
    "intended, not done this turn: no op" rule dropped it. Riding on a follow of somebody
    standing here, it is done now, and builds the walk home whole."""
    s, e, body = _market()
    frame = copy.deepcopy(ROW_56)
    rows = acts_to_ops.table(frame, s, places=e.places())
    go = rows[1].record()
    assert "intended" not in str(go.get("note", "")) and go.get("commit") is None
    assert go["built"] == [{"op": "call_on", "params": {"who": body.ref, "together": True}}]
    assert frame["actions"][1]["commit"] == "done"


def test_the_plans_own_walk_beside_the_walk_home_is_dropped():
    """Rows 56 and 62 had the plan reach for travels to "the private quarters" and a
    `found` for it. Beside the walk home those would walk elsewhere or mint a second
    place."""
    s, e, body = _market()
    frame = copy.deepcopy(ROW_56)
    rows = acts_to_ops.table(frame, s, places=e.places())
    plan = [{"op": "found", "params": {"name": "the private quarters", "kind": "tavern"}},
            {"op": "travel", "params": {"place": "the private quarters"}}]
    raw = acts_to_ops.apply(plan, rows, frame, s, notes=[])
    assert [r["op"] for r in raw] == ["call_on"]


def test_an_indifferent_person_will_not_take_you_home_and_says_the_fix():
    """The same words to somebody indifferent: refused, with the fix named the way
    `_op_company` names it, and nothing moves and no house is made."""
    s, e, body = _market(helpful=False)
    was = s.at
    _f, _rows, _raw, out = _turn(e, ROW_56)
    call = next(o for o in out.outcomes if o.op == "call_on")
    assert call.status == "refused"
    assert "indifferent" in call.tell and "Diplomacy" in call.tell
    assert s.at == was and body.at == was and not _homes(s, body.ref)


def test_the_readers_own_call_on_somebody_here_goes_together():
    """"I go round to Ariniel Thorne's house" with her beside you is read `call_on`; the
    plain call refused her as "here, with you". It is the same walk home."""
    s, e, body = _market()
    frame = {"question": False, "claims": [], "actions": [
        {"act": "call_on", "target": "Ariniel Thorne", "place": "Ariniel Thorne's house",
         "span": "go round to Ariniel Thorne's house"}]}
    _f, rows, _raw, out = _turn(e, frame)
    assert rows[0].ops == []
    call = next(o for o in out.outcomes if o.op == "call_on")
    assert call.status == "resolved", call.tell
    assert body.at == s.at == _homes(s, body.ref)[0]["id"]


def test_a_walk_to_nowhere_known_is_a_printed_refusal():
    """Row 69: "Continue walking toward the quarters", `go: the quarters`, nobody
    followed. Before, a bare `narrate_only` and "You remain in the market"; now the
    engine's own sentence, refused, and nobody moves."""
    s, e, body = _market()
    was = s.at
    _f, rows, raw, out = _turn(e, ROW_69)
    said = 'You don\'t know of anywhere called "the quarters" here.'
    assert rows[0].nowhere == said
    o = out.outcomes[-1]
    assert o.op == "narrate_only" and o.status == "refused" and o.tell == said
    assert s.at == was


def test_a_plan_that_walks_or_founds_is_left_alone():
    """Places are creatable in play (ruling 2026-10-03): a plan that founds the place it
    could not find, or walks anywhere, is not overruled by the walk-to-nowhere answer."""
    s, e, body = _market()
    frame = copy.deepcopy(ROW_69)
    rows = acts_to_ops.table(frame, s, places=e.places())
    founds = [{"op": "found", "params": {"name": "the quarters", "kind": "house"}},
              {"op": "travel", "params": {"place": "the quarters"}}]
    assert acts_to_ops.nowhere_to_go(founds, rows) == founds
    # Nor a turn that does anything else: "go back up to my room and sleep" is the sleep.
    sleeps = [{"op": "rest", "actor": "pc", "params": {"kind": "night"}}]
    assert acts_to_ops.nowhere_to_go(sleeps, rows) == sleeps


def test_the_players_own_room_is_never_anywhere_unknown():
    """"go back up to my room" at the inn (the leave-by-deed turns): the player's own
    room is the rest's to answer, not a place the town is asked to have."""
    s, e, body = _market()
    frame = {"question": False, "claims": [], "actions": [
        {"act": "go", "place": "my room", "span": "go back up to my room"}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    assert rows[0].nowhere == ""


def test_a_fixture_of_the_room_is_a_walk_across_it_not_a_refusal():
    """"I walk over to the counter" is read `go: the counter`; a counter is a thing in the
    room (`judgement._FIXTURES`), and crossing to it is never "anywhere" unknown."""
    s, e, body = _market()
    frame = {"question": False, "claims": [], "actions": [
        {"act": "go", "place": "the counter", "span": "walk over to the counter"}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    assert rows[0].nowhere == ""
    assert acts_to_ops.nowhere_to_go([{"op": "narrate_only"}], rows) == [
        {"op": "narrate_only"}]


def test_the_quarters_with_nobody_followed_name_nobodys_home():
    """The dwelling noun alone does not pick an owner: "the quarters" with nobody
    followed is nobody's, and nothing is built for anybody standing here."""
    s, e, body = _market()
    rows = acts_to_ops.table(copy.deepcopy(ROW_69), s, places=e.places())
    assert rows[0].intents == []


HER_HOUSE = {"question": False, "claims": [], "actions": [
    {"act": "go", "place": "her house", "span": "go with her to her house"}]}


def test_her_house_is_the_person_you_are_talking_to():
    """"her" with nobody followed is the one person the player is dealing with, when the
    pronoun fits her (`addressed`, the engine's state) — and only while the character
    knows nobody else's home, whose door the plain call's own pronoun rule would find."""
    s, e, body = _market()
    e.run(e.validate([{"op": "say", "params": {"words": "Lead on.", "to": body.ref}}],
                     origin="author:test"))
    rows = acts_to_ops.table(copy.deepcopy(HER_HOUSE), s, places=e.places())
    assert rows[0].record()["built"] == [
        {"op": "call_on", "params": {"who": body.ref, "together": True}}]
    from rules.activeeffect import ActiveEffect

    s.pc().apply_effect(ActiveEffect(
        name="knows where the baker lives", kind="knowledge", key="knows-home:p9",
        source="home:p9", origin="test", duration="until-dismissed",
        tags=("knows.home.p9",)))
    rows = acts_to_ops.table(copy.deepcopy(HER_HOUSE), s, places=e.places())
    assert rows[0].intents == []
    # And her house is never "anywhere" unknown: it is the knock's to answer.
    assert rows[0].nowhere == ""


def test_calling_on_her_without_going_together_still_says_she_is_here():
    """The plain knock is unchanged: `together` is the table's, and a call with no
    `together` on somebody beside you is still told so."""
    s, e, body = _market()
    out = e.run(e.validate([{"op": "call_on", "params": {"who": body.ref}}],
                           origin="author:test"))
    assert out.outcomes[0].status == "refused" and "here, with you" in out.outcomes[0].tell


class _Reply:
    """The planner's reply, stubbed: no model is called."""

    def __init__(self, plan):
        self.text = json.dumps({"narration": "", "intents": plan})
        self.seconds, self.model = 0.0, "stub"
        self.prompt_tokens = self.reply_tokens = 0
        self.done_reason = "stop"

    def json(self):
        return json.loads(self.text)


def test_both_rows_through_the_real_plan_turn(monkeypatch):
    """Rows 56 and 69 through `GMAgent.plan_turn`, the stubbed planner writing the plans
    the save logged (a square's `move` toward her; a bare `narrate_only`)."""
    from gm import agent as agent_mod
    from gm import interpret
    from gm.agent import GMAgent

    s, e, body = _market()
    said = "I follow Ariniel Thorne to her private quarters"
    interpret.remember(said, copy.deepcopy(ROW_56))
    plan = [{"op": "move", "actor": "pc", "params": {"zone": "near"},
             "because": "the player walks up to Ariniel Thorne"}]
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply(plan))
    got = GMAgent(WORLD, e).plan_turn(said, history=[])
    assert [i.op for i in got.intents].count("call_on") == 1, got.rejections
    e.run(got.intents)
    assert s.at == _homes(s, body.ref)[0]["id"] and body.at == s.at

    s, e, body = _market()
    said = "Continue walking toward the quarters"
    interpret.remember(said, copy.deepcopy(ROW_69))
    plan = [{"op": "narrate_only",
             "because": "the player moves within the scene, toward the quarters"}]
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply(plan))
    got = GMAgent(WORLD, e).plan_turn(said, history=[])
    res = e.run(got.intents)
    told = [o for o in res.outcomes if o.op == "narrate_only" and o.status == "refused"]
    assert told and told[0].tell == 'You don\'t know of anywhere called "the quarters" here.'
