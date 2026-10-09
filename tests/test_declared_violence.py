"""A declared blow lands on a real person here, or the turn says there is nobody to strike.

The owner's ruling, 2026-10-09: "if i say I attack the closest person or i go on a rampage
or i assault a civilian etc. it should be able to start a fight."

Measured live the same day, before the fix (gemma-4-12B heretic, scratch data, a market of
three bystanders — the fruit seller five feet off, the porter at fifteen, a boy at forty):

  * "I attack the closest person." — the planner aimed rightly at the fruit seller, and the
    "fight" declarer (`declared_ops` asking the template-thug `inject_fight` what it would
    add) REQUIRED a `spawn`: two bandits came out of nowhere and joined her side.
  * "I go on a rampage." — read `other`; five plans aimed at the placeholder `new1`, and the
    turn degraded into prose about slicing men who were not there.
  * "I pick a fight with the biggest bruiser in the room." — read `insult` (the gloss said
    "pick a fight with words"); the declarer required `spawn` + `begin_encounter`, five
    attempts failed on placeholder refs, and the fallback model timed out at 600 s.
  * "I assault a civilian." — "assault" was not on the regex's list, so it happened to work.

What replaced it (docs/structured-turn.md: models read, code validates): the reader's
`attack` act declares the blow; `acts_to_ops.victims` finds who it lands on through the
engine's finders, and for words no finder answers asks ONE question with the people here
as an enum (`interpret.confirm_victims`); the nearest of those, by the squares people keep,
is the engine's answer. Nobody is made from the words, and with nobody here the turn is the
refusal. The question is stubbed here with what it answered live (14 of 14 hand-written
probes, 2026-10-09); `tests/_violence.py` holds the live readings.
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, interpret, judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.sheet import load_pc
from tests._violence import everyone, nobody, reading, through_the_reading


def _market(*, bruiser=False, guard_beside=False):
    """The scratch market of the live repro, on a map: the player at (5, 5)."""
    s = Scene()
    s.grid = Grid(width=20, height=20)
    s.add(load_pc("fixtures/pc-kesst.json"), at=(5, 5))
    people = []
    if guard_beside:
        people.append(("the watchman by the stall", "watchman", (6, 5)))
    people += [("the old porter resting on his barrow", "guildhand", (5, 8)),
               ("the fruit seller with the red scarf", "guildhand", (6, 6)),
               ("a boy selling spiced nuts", "guildhand", (5, 13))]
    if bruiser:
        people.append(("the hulking dockhand with a broken nose", "thug", (12, 12)))
    for name, template, at in people:
        a = s.add(instantiate(template, scene=s, name=name), at=at)
        a.add_condition("bystander", source="introduced by the scene")
    return s


def _ref(s, words):
    return next(r for r, a in s.actors.items() if words in a.name)


def test_the_closest_person_is_the_nearest_by_the_squares_people_keep():
    """"I attack the closest person." conjured two bandits on 2026-10-09. The blow lands on
    the fruit seller five feet off — not the porter, who is the lower ref, at fifteen."""
    s = _market()
    seller, porter = _ref(s, "fruit seller"), _ref(s, "porter")
    assert porter < seller, "the premise: the nearest is not the lowest ref"
    out, stop = through_the_reading([{"op": "narrate_only"}], "I attack the closest person.",
                                    s, ask=everyone)
    assert not stop
    assert [(i["op"], i.get("target")) for i in out if i["op"] != "narrate_only"] == [
        ("attack", seller)]


def test_a_civilian_is_never_the_guard_beside_you():
    """"a civilian" is whoever the words could mean, asked of the people here; the nearest
    of THOSE is struck — not the watchman standing closer than any of them."""
    s = _market(guard_beside=True)
    guard, seller = _ref(s, "watchman"), _ref(s, "fruit seller")

    def civilians(span, words, people):
        return [r for r, label in people if "(a guard" not in label]

    out, _ = through_the_reading([], "I assault a civilian.", s, ask=civilians)
    assert [(i["op"], i["target"]) for i in out] == [("attack", seller)]
    assert guard not in {i["target"] for i in out}
    # The label the question is shown carries the engine's fact, never a guess.
    assert acts_to_ops.label(s.actors[guard]).endswith("(a guard)")


def test_a_rampage_strikes_the_nearest_person_each_turn():
    """"I go on a rampage." was read `other` and degraded into prose about men who were not
    there (2026-10-09). Read as an attack now (a demonstration of that day), it lands on
    the nearest; and once she is down, "I continue my rampage." lands on the next nearest."""
    s = _market()
    seller, porter = _ref(s, "fruit seller"), _ref(s, "porter")
    out, _ = through_the_reading([], "I go on a rampage.", s, ask=everyone)
    assert [i["target"] for i in out] == [seller]
    s.actors[seller].hp = -1
    s.actors[seller].add_condition("dying", source="the rampage")
    out, _ = through_the_reading([], "I continue my rampage.", s, ask=everyone)
    assert [i["target"] for i in out] == [porter]


def test_the_biggest_bruiser_when_there_is_one_and_the_refusal_when_there_is_not():
    """With a bruiser here the blow is his, though three people stand nearer. With none,
    the words fit nobody and the turn says so — the regex made one up."""
    s = _market(bruiser=True)
    dockhand = _ref(s, "dockhand")

    def the_bruiser(span, words, people):
        return [r for r, label in people if "hulking" in label]

    line = "I pick a fight with the biggest bruiser in the room."
    out, stop = through_the_reading([], line, s, ask=the_bruiser)
    assert [i["target"] for i in out] == [dockhand] and not stop

    out, stop = through_the_reading([], line, _market(), ask=nobody)
    assert out == [] or all(i["op"] != "attack" for i in out)
    assert stop == "Nobody here answers to the biggest bruiser in the room."


def test_nobody_here_is_a_refusal_in_words_never_an_opponent():
    """Not a soul but the player: "There is nobody here to attack." The template thug used
    to answer this sentence."""
    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    for line in ("I attack the closest person.", "I go on a rampage.", "I assault a civilian.",
                 "I pick a fight with the biggest bruiser in the room."):
        out, stop = through_the_reading([{"op": "narrate_only"}], line, s, ask=everyone)
        assert stop == "There is nobody here to attack.", line
        assert [i["op"] for i in out] == ["narrate_only"], line


def test_the_plans_conjuring_is_dropped_and_its_blow_aimed_at_the_real_person():
    """The live plan of 2026-10-09, verbatim in shape: begin_encounter + attack + the spawn
    the declarer demanded. What survives is one blow, at the person the words mean; the
    attack's battle gate opens the fight (it draws the sides as striker and struck)."""
    s = _market()
    seller, porter = _ref(s, "fruit seller"), _ref(s, "porter")
    plan = [{"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": [porter]}}},
            {"op": "attack", "actor": "pc", "target": porter, "params": {"full_attack": False},
             "because": "she strikes the nearest man"},
            {"op": "spawn", "params": {"template": "bandit", "count": 2},
             "because": "the player's words commit the turn to it"}]
    out, _ = through_the_reading(plan, "I attack the closest person.", s, ask=everyone)
    assert [(i["op"], i.get("target")) for i in out] == [("attack", seller)]
    assert out[0]["params"] == {"full_attack": False}, "the plan's own params are kept"


def test_the_fight_opens_on_the_real_person_and_their_own_kind_answers():
    """End to end through the engine: no new actor, the struck one on the other side, and
    a second watchman — her own kind — comes in through the existing rule (`Engine.rally`);
    the fruit seller across the way stays out of it."""
    s = _market(guard_beside=True)
    other = s.add(instantiate("watchman", scene=s, name="the watchman at the well"),
                  at=(9, 9))
    other.add_condition("bystander", source="introduced by the scene")
    guard = _ref(s, "by the stall")
    before = set(s.actors)
    out, _ = through_the_reading([], "I attack the closest person.", s, ask=everyone)
    assert [i["target"] for i in out] == [guard]
    e = Engine(s, Dice(seed=7))
    res = e.run(e.validate(out))
    assert set(s.actors) == before, "nobody walked on"
    assert s.in_encounter
    them = next(refs for side, refs in s.sides.items() if "pc" not in refs)
    assert guard in them and other.ref in them
    assert _ref(s, "fruit seller") not in them
    assert any("Battle is joined" in (o.tell or "") for o in res.outcomes)


def test_a_pronoun_in_a_fight_still_never_means_a_bystander():
    """The 2026-09-18 rule `_can_be_fought` exists for, kept: with the map open, the
    planner's attack on "the man" landed on a 4-hp bystander who had never been in the
    fight. "I punch him." in a fight means the man in it."""
    s = _market()
    thug = s.add(instantiate("thug", scene=s, name="the thug"), at=(9, 9))
    e = Engine(s, Dice(seed=3))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"party": ["pc"], "them": [thug.ref]}}}],
                     origin="author:test"))
    out, _ = through_the_reading([], "I punch him.", s, ask=everyone)
    assert [i["target"] for i in out] == [thug.ref]


def test_a_blow_after_a_walk_is_left_to_the_room_it_lands_in():
    """"I shoulder my way into the tavern and pick a fight with the bruiser": the people
    standing here at plan time are not the tavern's, so nothing is decided or refused here
    — and the plan still makes nobody (Engine.validate, beat reader's seen people)."""
    s = _market()
    out, stop = through_the_reading(
        [{"op": "spawn", "params": {"template": "thug"}}],
        "I shoulder my way into the tavern and pick a fight with the bruiser.", s,
        ask=everyone)
    assert not stop and not [i for i in out if i["op"] == "attack"]


def test_no_reading_means_no_blow_is_invented():
    """A failed reader call (or the reader off) is the plan alone, for blows as for every
    act: no regex reads the sentence behind it."""
    s = _market()
    assert judgement.inject_fight([{"op": "narrate_only"}], "I attack the closest person.",
                                  s) == [{"op": "narrate_only"}]
    assert judgement.inject_fight([{"op": "narrate_only"}], "I go on a rampage.", s,
                                  rows=[], frame=None) == [{"op": "narrate_only"}]


def test_a_failed_question_builds_nothing():
    """`confirm_victims` answering None (the call failed) builds no blow and refuses
    nothing: the plan's own blow stands."""
    s = _market()
    out, stop = through_the_reading([], "I attack the closest person.", s,
                                    ask=lambda *a: None)
    assert out == [] and not stop


def test_the_schema_no_longer_demands_a_spawn_for_a_fight():
    """The channel the bandits came through: `declared_ops` asked the template thug what it
    would add to an empty turn, and the planner's schema then required spawn and
    begin_encounter for "I attack the closest person" (detectors: ['spawn',
    'begin_encounter', 'attack'], turn log, 2026-10-09)."""
    s = _market()
    for line in ("I attack the closest person.", "I go on a rampage.",
                 "I pick a fight with the biggest bruiser in the room."):
        ops = judgement.declared_ops(line, s)
        assert not {"spawn", "begin_encounter", "introduce"} & set(ops), (line, ops)
    assert not hasattr(judgement, "wants_a_fight")
    assert not hasattr(judgement, "opponent_count")


def test_the_victim_question_holds_its_answer_to_the_people_here(monkeypatch):
    """The sampler enforces the enum (memory: enums 6/6); code checks it again, and a
    failed call is None, never a guess."""
    from gm import client

    class Reply:
        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    seen = {}

    def chat(messages, *a, schema=None, **k):
        seen["schema"] = schema
        seen["last"] = messages[-1]["content"]
        return Reply({"meant": ["c6", "c99", "c6"]})

    monkeypatch.setattr(client, "chat", chat)
    people = [("c6", "the fruit seller"), ("c7", "the porter")]
    assert interpret.confirm_victims("attack the closest person", "the closest person",
                                     people) == ["c6"]
    assert seen["schema"]["properties"]["meant"]["items"]["enum"] == ["c6", "c7"]
    assert "c7: the porter" in seen["last"] and "attack the closest person" in seen["last"]

    def broken(*a, **k):
        raise RuntimeError("Ollama is not answering")

    monkeypatch.setattr(client, "chat", broken)
    assert interpret.confirm_victims("attack the closest person", "", people) is None


@pytest.mark.parametrize("line", ["I attack the closest person.", "I assault a civilian.",
                                  "I go on a rampage.",
                                  "I pick a fight with the biggest bruiser in the room."])
def test_the_live_reader_read_each_of_the_owners_lines_as_a_blow(line):
    """Recorded 2026-10-09 after the two demonstrations: all four read `attack` (before
    them, the rampage was `other` and the bruiser `insult`)."""
    assert [a["act"] for a in reading(line)["actions"]] == ["attack"]
