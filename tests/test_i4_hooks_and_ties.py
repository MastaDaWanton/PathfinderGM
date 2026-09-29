"""Phase 3, I4: a quest hook knows who its giver is to the player, and the lost-thing's
tell waits for the player to have spoken with the giver.

What was measured on the Bobby playtest (docs/playtest-2026-09-28.md item 12;
tests/replays/bobby-2026-09-28, turn 4): Drenn Ironvale — who, by Bobby's own
background, TAUGHT him bonesetting — opened on his former pupil with a stranger's
sizing-up: "You! You have the look of someone who can navigate the nuances of a search …
do you have any idea where such a thing might be hidden?" Lane D gave the `greets` row
its tie; the `asked` row (the player turning to the giver) and `sends_word` still told
the narrator only "says what they want" — the same cold pitch, one approach over.

And the-lost-thing's `noticed` step, moved off the open by Lane D, fired on `present`
alone: the player "noticed" the giver keeping something back while only standing in the
same market. The design asked for `event:talk($giver)`, which nothing emitted.

Every scene test runs on the three worlds.
"""
from __future__ import annotations

import re

import pytest

from gm import interpret
from rules import backgrounds, cards, hooks, schemes, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.sheet import load_pc

WORK_HOUR = 10 * 60
DAY_TWO = 24 * 60 + 9 * 60

# The stranger's first-meeting formulas the playtest's Drenn used, and the pitch's
# instruction to walk up and open. None may be in a pull for somebody who knows the player.
COLD = ("say the first word", "you have the look of", "who are you")


def _bonesetter_at_market(world, clock=WORK_HOUR):
    """Thessaly (the bonesetter background, the owner's own example start), bound to this
    world through Lane C's door: her ties are real, `scene.acquainted` holds the teacher."""
    row = (world.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    pc = load_pc("fixtures/pc-thessaly.json")
    s.add(pc)
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=5), world=world)
    market = schemes._place_for(e, "market", {})
    e.place_party(market["id"])
    bound = backgrounds.bind(e, pc)
    pc.background_ties = [b["says"] for b in bound]
    tied = next((b for b in bound if b.get("entity") and b.get("who")), None)
    return s, e, pc, tied


def _tied_giver(s, tied):
    """The person the tie names, walking in through the arrival door — which is what
    gives them `bond.knows-you` from the `background:` source."""
    g = instantiate("guildhand", scene=s, name=tied["who"], world_entity_id=tied["entity"])
    s.add(g)
    return g


def _quest(s, giver, turn=1):
    return cards.open_quest(
        s, title=f"Find {giver.name}'s lost satchel", objectives=["Search the quays for it"],
        giver=giver.ref, reward="a debt of thanks, and a word at the healers' door",
        people=[giver.ref], place=str(s.at), origin="author:test", turn=turn)


def _pull(s, text, reading, turn=4):
    interpret.remember(text, reading)
    return cards.thread_to_pull(s, recent=["The market is loud."], player_text=text,
                                turn=turn)


def test_a_background_tied_giver_is_tied_through_lane_cs_door(worlds):
    """The relationship is read from engine facts Lane C writes: `scene.acquainted` and the
    `bond.knows-you` whose source is `background:bonesetter` — not from the model."""
    s, e, pc, tied = _bonesetter_at_market(worlds)
    assert tied, f"{worlds.name}: the bonesetter's teacher tie binds to somebody"
    g = _tied_giver(s, tied)
    assert tied["entity"] in s.acquainted
    knows = [x for x in g.effects if states.KNOWS_YOU in (x.tags or ())]
    assert knows and str(knows[0].source).startswith("background:")
    assert hooks.relationship(s, g) == hooks.TIED
    assert hooks.tie_sentence(s, g) and g.name in hooks.tie_sentence(s, g)


@pytest.mark.parametrize("scene", ["present", "asked", "elsewhere"])
def test_a_tied_givers_pull_is_never_a_cold_pitch(worlds, scene):
    """Drenn pitched his own former pupil as a stranger. For a giver the PC's background
    names, every approach that reaches the player — greeting them present, answering
    when turned to, sending word from elsewhere — says they know the player, carries the
    tie's own sentence and asks as a favour; none is a stranger's opener."""
    s, e, pc, tied = _bonesetter_at_market(worlds)
    g = _tied_giver(s, tied)
    _quest(s, g)
    if scene == "present":
        text, reading = "I look around the stalls.", {"actions": [{"act": "look"}]}
        want = "greets"
    elif scene == "asked":
        text = f"I ask {g.name} what is wrong."
        reading = {"actions": [{"act": "talk", "target": g.name, "says": "what is wrong"}]}
        want = "asked"
    else:
        elsewhere = next(p.id for p in e.places() if p.id != s.at)
        s.move(g.ref, elsewhere)
        text, reading = "I look around the stalls.", {"actions": [{"act": "look"}]}
        want = "sends_word"
    pull = _pull(s, text, {"question": False, "claims": [], **reading})
    assert pull["approach"] == want, pull
    assert pull["to_player"]["relationship"] == hooks.TIED
    low = pull["text"].lower()
    assert "knows the player" in low or "who knows them" in low, pull["text"]
    assert hooks.tie_sentence(s, g) in pull["text"], pull["text"]
    assert not any(c in low for c in COLD), pull["text"]
    if want in ("greets", "asked"):
        assert "never as a stranger" in low and "favour" in low, pull["text"]
    assert not re.search(r"\d", pull["text"])


def test_a_stranger_asked_is_not_told_they_know_the_player(worlds):
    """The known/tied wording is the relationship's, never everybody's: the same giver
    with no tie is asked plainly."""
    s, e, pc, tied = _bonesetter_at_market(worlds)
    g = instantiate("guildhand", scene=s, name="Tavi Holm")
    s.add(g)
    _quest(s, g)
    pull = _pull(s, f"I ask {g.name} what is wrong.", {"question": False, "claims": [],
                 "actions": [{"act": "talk", "target": g.name, "says": "what is wrong"}]})
    assert pull["approach"] == "asked"
    assert pull["to_player"]["relationship"] == hooks.STRANGER
    assert "knows" not in pull["text"].lower()


# --- the lost thing: the tell after the talk -----------------------------------------------

@pytest.fixture
def schemes_on(monkeypatch):
    monkeypatch.setattr(schemes, "ENABLED", True)


def _lost_thing_at_market(world):
    row = (world.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    s.clock_minutes = DAY_TWO
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party(schemes._place_for(e, "market", {})["id"])
    inst = schemes.open_scheme(e, schemes.shipped()["the-lost-thing"], turn=1)
    giver = s.people[inst["slots"]["giver"]["ref"]]
    return s, e, pc, inst, giver


def _run(e, ops):
    return e.run(e.validate(ops, origin="author:test"))


def _wait(e):
    return _run(e, [{"op": "advance_time", "actor": "pc", "because": "t",
                     "params": {"amount": 1, "unit": "minutes"}}])


def test_the_lost_thing_grant_lands_only_after_the_player_talks_to_the_giver(worlds,
                                                                             schemes_on):
    """Before I4 the `noticed` step fired on `at($market)` and `present($giver)`: the
    player knew the giver "keeps glancing at an empty place" while only standing in the
    same market. Now three waits beside the giver grant nothing; one word to them does."""
    s, e, pc, inst, giver = _lost_thing_at_market(worlds)
    assert giver.at == s.at
    for _ in range(3):
        _wait(e)
    assert "noticed" not in inst["fired"]
    assert not pc.has_state("knows.giver-hides-something")
    _run(e, [{"op": "say", "actor": "pc", "because": "t",
              "params": {"words": "Good morning.", "to": giver.ref}}])
    assert "noticed" in inst["fired"] and inst["fired"]["noticed"]["silent"]
    assert pc.has_state("knows.giver-hides-something")


def test_talking_to_somebody_else_does_not_grant_it(worlds, schemes_on):
    s, e, pc, inst, giver = _lost_thing_at_market(worlds)
    other = instantiate("guildhand", scene=s, name="Tavi Holm")
    s.add(other)
    _run(e, [{"op": "say", "actor": "pc", "because": "t",
              "params": {"words": "Good morning.", "to": other.ref}}])
    assert "noticed" not in inst["fired"]
    assert not pc.has_state("knows.giver-hides-something")


def test_talk_events_come_from_say_outcomes_between_the_player_and_one_other():
    """`event:talk($slot)` names the other party of an exchange with the player, either
    way round; two NPCs talking, or anybody speaking to nobody, is no talk event."""
    def said(who, to):
        return Outcome(intent_id="i", op="say", effects=[
            {"kind": "said", "who": who, "to": to, "words": "hello"}])

    ev = schemes._events_from([said("pc", "c4"), said("c5", "pc"), said("", "c6"),
                               said("c7", "c8"), said("c9", ""), said("pc", "")],
                              pc_ref="pc")
    assert ev == [{"event": "talk", "to": "c4"}, {"event": "talk", "to": "c5"},
                  {"event": "talk", "to": "c6"}]


def test_the_validator_holds_hook_fields_and_event_names():
    """The hook reaches the narrator word for word, so it is held to what a title is held
    to; and an event nothing emits is named — `event:talk` sat in the design for a
    phase with no emitter, and the grammar alone would have accepted a step that could
    never fire."""
    doc = schemes.shipped()["the-lost-thing"]
    assert schemes.validate(doc) == []
    assert "event:talk($giver)" in next(st for st in doc["steps"]
                                        if st["id"] == "noticed")["criteria"]
    import copy

    bad = copy.deepcopy(doc)
    errand = next(c for c in bad["cards"] if c["key"] == "errand")
    errand["hook"] = {"motive": "it cost $giver 3 years of savings",
                      "doing": "haggling with $stranger", "mood": "sad"}
    next(st for st in bad["steps"] if st["id"] == "noticed")["criteria"].append(
        "event:chat($giver)")
    problems = " | ".join(schemes.validate(bad))
    assert "hook.motive" in problems and "number" in problems
    assert "$stranger is not a slot" in problems
    assert "hook.mood: not read" in problems
    assert "event:chat($giver)" in problems and "nothing emits" in problems
