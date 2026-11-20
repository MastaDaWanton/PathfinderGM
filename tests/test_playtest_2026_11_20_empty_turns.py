"""Playtest 2026-11-20 (the owner's 0.4.4 game), items 7, 14 and 15: turns that said what the
player did and not how the world answered, a beat that contradicted itself, and a table voice
that pointed at things that were never there. The research and the probes behind each fix are
in docs/research/2026-11-20-empty-turns.md."""
from __future__ import annotations

import json

from gm import acts_to_ops, planned
from gm.checks import closing_claimed
from rules.dice import Dice
from rules.engine import Engine, Outcome
from tests.test_closing_claimed import OWNERS_BEAT, _ctx
from tests.test_creature_closes import TOWARD, _owners_board, _run
from tests.test_narration_faithfulness import _Reply
from tests.test_planned_slot_shapes import LAST_BEAT, _say, _scene
from tests.test_requests_and_rewards import _asked
from tests.test_requests_and_rewards import _scene as _carter_scene

SEARCH_AWAY = {"question": False, "claims": [], "actions": [
    {"act": "search", "object": "a different way into the gallery",
     "span": "Look for a different way into the gallery"}]}


# --- item 7: the engine resolved nothing ------------------------------------------------------

def test_a_search_nothing_answered_is_the_perception_search_of_here():
    """#50: "Look for a different way into the gallery" was read `search` with `where` left
    at elsewhere, the table built nothing, the plan's check was dropped as aimed at a
    placeholder, and the turn resolved only `narrate_only` — the page showed the attempt and
    asked "What do you do?". By the book a search is Perception (a move action)."""
    s, _engine, _foe, _ally = _scene()
    raw = acts_to_ops.search_unanswered(
        [{"op": "narrate_only", "because": "the only ops were aimed at nobody"}],
        SEARCH_AWAY, s)
    assert raw == [{"op": "check", "actor": s.pc().ref,
                    "params": {"skill": "perception", "search": True},
                    "because": "the player searches"}]


def test_a_search_another_door_answered_is_left_alone():
    """Only a turn that is otherwise nothing: a travel, or a printed answer, is the turn's
    answer already ("look for a tavern" is the travel door's)."""
    s, _engine, _foe, _ally = _scene()
    walk = [{"op": "travel", "params": {"to": "the inn"}}]
    assert acts_to_ops.search_unanswered(walk, SEARCH_AWAY, s) == walk
    said = [{"op": "narrate_only", "params": {"not_here": "No gallery here."}}]
    assert acts_to_ops.search_unanswered(said, SEARCH_AWAY, s) == said
    nothing = [{"op": "narrate_only"}]
    talk = {"actions": [{"act": "talk", "span": "ask"}]}
    assert acts_to_ops.search_unanswered(nothing, talk, s) == nothing


# --- item 7: the favour with nothing named ----------------------------------------------------

def test_a_granted_favour_says_what_was_asked_and_that_nothing_has_changed_hands_yet():
    """#14: "I'd like an item from his pack in exchange" was told "the carter agrees to do
    Shadow the favour. Nothing changes hands." — what favour? — and the carter's answer,
    "I can certainly share something from my pack", was cut twice as a clash with it and
    dropped: the page held the act and no answer. A promise is no handover."""
    s, carter = _carter_scene()
    frame = {"question": False, "claims": [], "actions": [
        {"act": "request", "target": "the carter", "asks_for": "favour",
         "object": "an item from his pack in exchange"}]}
    _rows, plan = _asked(s, frame)
    check = next(r for r in plan if r.get("op") == "check")
    assert check["params"]["wants"] == "an item from his pack in exchange"
    e = Engine(s, Dice(seed=1))
    e.run(e.validate(plan))
    res = e.resume(20)
    tell = " ".join(o.tell for o in res.outcomes)
    assert f"asks {carter.name} for a favour: an item from his pack in exchange." in tell
    assert f"{carter.name} agrees to it. Nothing has changed hands yet." in tell


# --- item 7: the creature's answer cut by a backstop -----------------------------------------

def test_the_closing_backstop_keeps_the_creatures_walk():
    """#86: the cockroach "moves 30 ft toward Shadow and is still 25 ft away"; the prose
    "closing the distance by thirty feet until it stands twenty-five feet away" was cut, and
    the stand-in kept only "The giant cockroach is still 25 feet from you." — its whole
    answer to the player's move. The stand-in now says the walk, from the position effect."""
    _scene_, engine = _owners_board()
    res = _run(engine, [TOWARD])
    moved = sum(e.get("feet", 0) for o in res.outcomes for e in o.effects
                if e.get("kind") == "position")
    ctx = _ctx(engine, OWNERS_BEAT, outcomes=res.outcomes)
    kept, _notes = closing_claimed.backstop(ctx, OWNERS_BEAT, closing_claimed.find(ctx))
    assert moved and kept.endswith(
        f"The Clockwork Spy comes {moved} feet closer and is still 10 feet from you.")


# --- item 7: the beat that showed only the attempt -------------------------------------------

def _write_search(monkeypatch, answers, verdicts):
    s, engine, _foe, _ally = _scene()
    found = Outcome("i1", "check", actor="pc",
                    tell="Kesst Vayr searches the market and finds nothing.")
    asked = []

    def call_slot(slot, messages, who, **kw):
        asked.append((slot["key"], messages[-1]["content"]))
        reply = _Reply(json.dumps({"text": answers.pop(0)}))
        return reply, reply.json()

    monkeypatch.setattr(planned, "call_slot", call_slot)

    def faith(text, tells):
        from gm import beat_verify as bv

        return bv.TellsRead()

    faith.second = lambda text, fact: "tells it"
    faith.came = lambda passage, result: verdicts.pop(0)
    out = planned.write(engine, brief="", outcomes=[found], player_input="I search.",
                        who=("stub", "", "ollama", ""), faith=faith, last_beat=LAST_BEAT)
    return out, asked


def test_an_act_slot_that_shows_only_the_attempt_is_asked_for_the_outcome(monkeypatch):
    """The owner: "a turn that tells me what I did without telling me how the world
    responded and asks again what do I do." An omission contradicts nothing, so the tells
    check never saw it; probed, the fact-first read passed 3 of 4 attempt-only passages,
    the outcome read caught 6 of 6. The slot is asked once more with the result named."""
    out, asked = _write_search(monkeypatch, [
        "You scan the stalls, searching for anything hidden.",
        "You go over the stalls, and nothing is hidden there."], [False, True])
    acts = [a for k, a in asked if k == "fact1"]
    assert len(acts) == 2 and "It shows only the attempt" in acts[1]
    assert "finds nothing" in acts[1] and "nothing is hidden there" in out.text


def test_a_remake_that_still_shows_only_the_attempt_keeps_the_first(monkeypatch):
    out, _asked = _write_search(monkeypatch, [
        "You scan the stalls, searching for anything hidden.",
        "You keep scanning the stalls."], [False, False])
    assert "searching for anything hidden" in out.text and "keep scanning" not in out.text
    assert any("first answer kept" in n for n in out.notes)


def test_a_walk_a_refusal_and_a_blow_are_not_read_for_an_outcome():
    """Their own asks carry their own results: a walk's is its arrival, a refusal's is that
    it did not happen, a blow's are THE BLOW's facts."""
    s, engine, foe, _ally = _scene()
    walk = Outcome("i1", "move", actor="pc", tell="Kesst Vayr moves 20 ft.")
    no = Outcome("i2", "take", actor="pc", status="refused", tell="There is no lamp here.")
    hit = Outcome("i3", "attack", actor="pc", tell="Kesst Vayr hits the bandit.",
                  blows=[{"result": "hit", "ref": foe.ref, "weapon": "longsword",
                          "severity": "brutal", "left": "standing"}])
    slots = planned.build_plan(engine, "go", [walk, no, hit], last_beat=LAST_BEAT)
    assert not any(x.get("outcome") for x in slots)
    look = Outcome("i4", "check", actor="pc", tell="Kesst Vayr searches and finds nothing.")
    slots = planned.build_plan(engine, "look", [look], last_beat=LAST_BEAT)
    assert next(x for x in slots if x["key"] == "fact1")["outcome"]


# --- item 14: a beat that contradicts itself ----------------------------------------------------

def test_a_declared_fight_with_a_walk_later_in_the_turn_does_not_say_nobody_moves():
    """#97, "I move to A14 and strike the clockwork spy": the squaring-up slot was told "from
    where they stand: nobody moves" because the walk was another act of the same turn, and
    the page read "preparing to strike from your current position. You move across the
    ground…" — one beat, both."""
    s, engine, foe, _ally = _scene()
    joined = Outcome("i1", "attack", actor="pc",
                     tell="Battle is joined: Kesst Vayr squares off against the bandit.",
                     effects=[{"kind": "battle_joined", "ref": "pc", "target": foe.ref}])
    walk = Outcome("i2", "move", actor="pc", tell="Kesst Vayr moves 35 ft, beside rubble.")
    say = _say(planned.build_plan(engine, "I move and strike", [joined, walk],
                                  last_beat=LAST_BEAT), "fact1")
    assert "nobody moves" not in say and "from where they stand" not in say
    alone = _say(planned.build_plan(engine, "I strike", [joined], last_beat=LAST_BEAT),
                 "fact1")
    assert "nobody moves" in alone


# --- item 15: the table voice's leads ------------------------------------------------------------

def test_the_table_lines_read_sees_the_story_the_player_just_read(monkeypatch):
    """#9, #45, #48: "Anything in those crates catch your eye?" over a cart that held none,
    "a cellar or a crawlspace", "listening beneath the stones". The read excused any question
    or advice; it now flags one that points at what nothing holds, and the story on the page
    is a source of what is there, so the rubble it described may still be pointed at. Probed:
    0 of 4 such leads caught before, 4 of 4 after, 0 false alarms in 6 clean lines."""
    from gm import beat_verify
    from play import table_talk

    seen = []

    def beyond(text, premises, **kw):
        seen.append(list(premises))
        return []

    monkeypatch.setattr(beat_verify, "beyond_tells", beyond)
    line, why, _ = table_talk._nothing_past_the_facts(
        None, [], "Try the rubble again.", "", ["What happened: nothing found."], "Shadow",
        {}, "", [], story="You sift the rubble and broken walls.")
    assert line and not why
    assert seen[0][-1] == "The story the player just read: You sift the rubble and broken walls."
    assert "points at" in beat_verify._BEYOND_SYSTEM
    assert "point at another way only if the MOMENT or THE SCENE names one" in \
        table_talk.JOBS["refused"]
