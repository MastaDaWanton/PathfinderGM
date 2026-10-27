"""A matter the player never heard of is never the player's goal (the owner's report,
2026-10-27, 0.2.21 on Planned narration).

What was measured, on the owner's save (turn-log rows 90 and 137):

  * a scheme ("The lost thing") opened "Find Tanna Ashbourne's lost Coldwood" at the market
    as a quest card — on the board, in the brief as a QUEST and in the Journal from the
    hour it opened, though nobody had put it to the player;
  * tracking a caravan across an empty field, the pull picked it (approach `go_between`,
    with nobody there to be a go-between) and the planned slot was told "A matter the
    engine keeps open: Find Tanna Ashbourne's lost Coldwood — Search the approach for the
    Coldwood. Let it touch the scene in one sentence";
  * the beat said "You keep the goal of finding Tanna Ashbourne's lost Coldwood in mind as
    you scout the approach", and the owner pressed "That's wrong": "my goal is finding the
    caravan I have not spoken about or accepted a request to find lost coldwood".

The fix is a state the engine keeps (`Card.known`: unheard, heard, offered, taken), one
reader of it (`cards.standing`), a pull that only fires through somebody here to carry a
matter that is not the player's, a slot worded from it, and a read-back of the slot.
Every scene test runs on the three worlds.
"""
from __future__ import annotations

import json

import pytest

from gm import beat_verify, interpret, planned
from rules import cards, schemes
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Intent, Scene
from rules.sheet import load_pc

DAY_TWO = 24 * 60 + 9 * 60
LOOK = {"question": False, "claims": [], "actions": [{"act": "look"}]}


def _market(world, clock=DAY_TWO):
    row = (world.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=5), world=world)
    market = schemes._place_for(e, "market", {})
    e.place_party(market["id"])
    return s, e, market


def _lost_thing(s, e):
    inst = schemes.open_scheme(e, schemes.shipped()["the-lost-thing"], turn=1)
    quest = next(c for c in cards.load(s) if c.kind == "quest")
    giver = s.people[inst["slots"]["giver"]["ref"]]
    return inst, quest, giver


def _pull(s, text="I look around.", reading=LOOK, turn=40, recent=("The market is loud.",)):
    interpret.remember(text, reading)
    return cards.thread_to_pull(s, recent=list(recent), player_text=text, turn=turn)


# --- the engine's record ----------------------------------------------------------------------

def test_a_schemes_quest_opens_unheard_and_is_nobodys_goal_of_the_players(worlds):
    """The Coldwood quest was a "QUEST:" in every brief, and in the Journal, from the hour
    its scheme opened. Now it opens unheard: not in the Journal, not in the prose's brief,
    and marked in the plan's as the GM's alone and nobody's goal of the player's."""
    s, e, _m = _market(worlds)
    _inst, quest, _giver = _lost_thing(s, e)
    assert quest.known == "unheard" and cards.standing(quest) == cards.UNHEARD
    assert quest.title not in json.dumps(cards.quest_log(s))
    prose = cards.brief(s, [], turn=2)
    assert quest.title not in prose
    plan = cards.brief(s, [], turn=2, secret=True)
    assert f"NOT YET PUT TO THE PLAYER" in plan and quest.title in plan
    assert "QUEST: " + quest.title not in plan


def test_an_owners_save_card_reads_its_standing_from_its_approaches():
    """The owner's own Coldwood card, as saved by 0.2.21 (no `known`): opened by a scheme,
    reached for twice in passing (overheard at turn 74, go_between at 86) and never put to
    the player. It reads as heard of — never the player's own. A quest the party took (the
    `quest` op's origin) reads as taken, as it always was; a card with `known` unset
    round-trips byte-identically."""
    saved = {"id": "quest-2-find-tanna-ashbourne-s-l",
             "title": "Find Tanna Ashbourne's lost Coldwood", "kind": "quest",
             "tags": ["situation.quest", "situation.play"], "people": ["c14"],
             "giver": "c14", "origin": "scheme:the-lost-thing", "stage": "moving",
             "objectives": [{"text": "Search the approach for the Coldwood", "done": False},
                            {"text": "Bring the Coldwood back to Tanna Ashbourne",
                             "done": False}],
             "approaches": [{"turn": 74, "approach": "overheard"},
                            {"turn": 86, "approach": "go_between"}]}
    card = cards.Card.from_dict(saved)
    assert cards.standing(card) == cards.HEARD and not cards.is_own(card)
    assert cards.Card.from_dict(card.as_dict()).as_dict() == card.as_dict()
    assert "known" not in card.as_dict()
    taken = cards.Card.from_dict({**saved, "origin": "gm", "approaches": []})
    assert cards.standing(taken) == cards.OWN
    asked = cards.Card.from_dict({**saved, "approaches": [{"turn": 9, "approach": "asked"}]})
    assert cards.standing(asked) == cards.OFFERED


# --- the pull: nobody here to carry it, no pull ------------------------------------------------

def test_an_unheard_quest_is_not_pulled_into_an_empty_field(worlds):
    """Row 137: the party in the fields, nobody there, the recent beats full of the
    quest's own words (the player had made Coldwood salve; another giver was an
    Ashbourne). The pull picked the Coldwood quest as `go_between`. Now a matter that is
    not the player's, with nobody here to carry it, is not pulled at all."""
    s, e, _m = _market(worlds)
    _inst, quest, giver = _lost_thing(s, e)
    e.place_party(s.at.split("~", 1)[0] + "~farmland:@the-fields")
    assert giver.ref not in s.actors
    recent = [f"You grind the {quest.title.split()[-1]} into a salve base. "
              f"{giver.name} is far behind you.", "The fields are empty."]
    ranked = cards.salience(s, recent=recent, player_text="I look around.", turn=40)
    assert any(c.id == quest.id for _n, _why, c in ranked), \
        "it still scores (its words are in the recent beats): the carrier rule stops it"
    pull = _pull(s, recent=recent)
    assert pull is None or pull["id"] != quest.id, pull


def test_a_go_between_needs_somebody_here_to_carry_it(worlds):
    """`go_between` said "if somebody the player is already dealing with fits it" — and in
    the field there was nobody, so the beat had no mouth to put it in. The engine now names
    the carrier, a person of this place standing here; with nobody, there is no pull."""
    s, e, _m = _market(worlds)
    _inst, quest, giver = _lost_thing(s, e)
    e.place_party(s.at.split("~", 1)[0] + "~farmland:@the-fields")
    assert giver.ref not in s.actors
    recent = [f"{giver.name} and the lost thing, far off at the market."]
    alone = _pull(s, turn=40, recent=recent)
    assert alone is None or alone["id"] != quest.id, alone
    farmer = instantiate("guildhand", scene=s, name="Orla Venn")
    s.add(farmer)
    got = _pull(s, turn=80, recent=recent)
    assert got is not None and got["id"] == quest.id, got
    assert got["approach"] == "go_between" and got["carrier"]["name"] == "Orla Venn"
    assert "Orla Venn, who is here, mentions" in got["text"]
    assert "NOT the player's" in got["text"]


def test_the_free_narrators_pull_never_hands_an_objective_of_a_matter_not_taken(worlds):
    """The free narrator's head was "STILL OPEN … Find X — Search the approach for the
    Coldwood": the player's to-do list, for a quest the player had not taken. For a matter
    that is not theirs the head says whose it is, and carries no objective."""
    s, e, _m = _market(worlds)
    _inst, quest, giver = _lost_thing(s, e)
    pull = _pull(s)
    assert pull is not None and pull["id"] == quest.id and pull["approach"] == "overheard"
    assert pull["standing"] == cards.UNHEARD and pull["fact"] == ""
    assert "NOT the player's" in pull["text"] and "never heard of it" in pull["text"]
    assert quest.objectives[0]["text"] not in pull["text"]
    assert not pull["urgent"]


# --- the write-back and the taking up --------------------------------------------------------

def test_a_beat_that_carries_the_matter_makes_it_heard_or_offered_never_less(worlds):
    """Overheard is a rumour (BG3's journal guidelines: a voice bark starts no quest;
    Skyrim's overheard objectives were modded out by its players): known, not in the
    Journal. Asked is an offer: in the Journal, marked offered. A later rumour never
    unmakes an offer, and a beat that did not carry the matter changes nothing."""
    s, e, _m = _market(worlds)
    _inst, quest, _giver = _lost_thing(s, e)
    pull = {"id": quest.id, "approach": "overheard"}
    assert cards.note_heard(s, pull, carried=[]) == ""
    assert cards.find(s, quest.id).known == "unheard"
    assert cards.note_heard(s, pull, carried=[quest.title]) == quest.id
    assert cards.standing(cards.find(s, quest.id)) == cards.HEARD
    assert quest.title not in json.dumps(cards.quest_log(s))
    cards.note_heard(s, {"id": quest.id, "approach": "asked"}, carried=[quest.title])
    row = cards.quest_log(s)["active"][0]
    assert row["title"] == quest.title and row["standing"] == "offered"
    cards.note_heard(s, pull, carried=[quest.title])
    assert cards.find(s, quest.id).known == "offered"
    assert cards.note_heard(s, {"id": quest.id, "approach": "waits"},
                            carried=[quest.title]) == ""


def test_taking_up_a_quest_put_to_the_player_makes_it_theirs(worlds):
    """Until 2026-10-27 the `quest` op refused a scheme's quest as "already a quest on
    the table" — it was the player's from the start. Now the player takes it up by its
    title once they know of it; one they never heard of is refused, with why."""
    s, e, _m = _market(worlds)
    _inst, quest, giver = _lost_thing(s, e)
    # The planner writes its own wording of the objectives; the card keeps its own.
    raw = [{"op": "quest", "actor": "pc", "because": "t",
            "params": {"title": quest.title, "objectives": ["find it for them"]}}]
    refused = e.run(e.validate(raw, origin="author:test")).outcomes[-1]
    assert refused.effects == [] and "never been put to the player" in refused.tell, refused
    assert cards.find(s, quest.id).known == "unheard"
    cards.note_heard(s, {"id": quest.id, "approach": "asked"}, carried=[quest.title])
    took = e.run(e.validate(raw, origin="author:test")).outcomes[-1]
    assert took.effects and took.effects[0].get("taken_up"), took.tell
    assert "takes it on: " + quest.title in took.tell and giver.name in took.tell
    assert cards.standing(cards.find(s, quest.id)) == cards.OWN
    assert len(cards.quests(s)) == 1, "taken up, not a second card"
    assert cards.find(s, quest.id).objectives == quest.objectives, "the card's own objectives"
    # A new quest still needs objectives, and the schema says so: made optional for the
    # take-up, the live planner (2026-10-27) proposed a quest with none and was refused.
    from rules.intents import OPS

    assert OPS["quest"][0] == ("title", "objectives")


def test_a_planned_beat_that_dropped_the_matter_slot_did_not_tell_it():
    """Measured live 2026-10-27 on a scratch Fizspark campaign: "Fetch Glowvine for Peleth
    Ashbourne" was pulled `overheard`, the budget dropped the matter slot, a scheme's own
    tell named Peleth Ashbourne on the page, and the name alone made the quest heard. On
    a planned beat it is told only when the slot that carried it stood."""
    from types import SimpleNamespace

    from play.views import _matter_told

    free = SimpleNamespace(last_narration="free", last_prose_slots=[])
    assert _matter_told(free)
    dropped = SimpleNamespace(last_narration="planned", last_prose_slots=[
        {"key": "fact1", "wrote": "Twelve hours pass."},
        {"key": "aside", "wrote": "Peleth Ashbourne keeps watching the door."}])
    assert not _matter_told(dropped)
    stood = SimpleNamespace(last_narration="planned", last_prose_slots=[
        {"key": "matter", "wrote": "Peleth Ashbourne frets over the glowvine."}])
    assert _matter_told(stood)
    folded = SimpleNamespace(last_narration="planned", last_prose_slots=[
        {"key": "reply", "wrote": "'Find it for me?'", "not_own": "Fetch Glowvine"}])
    assert _matter_told(folded)


def test_agreeing_to_the_giver_takes_the_quest_up_and_it_reaches_the_journal(worlds):
    """Measured live 2026-10-27: "I tell Brix, 'I will find your Coldwood for you.'" to the
    giver of a quest the player had heard of, and the planner proposed no take-up, so the
    quest stayed his and out of the Journal. The engine sees the player speaking to the
    giver of a quest they know of and asks the reader one question; on yes, the table
    builds the take-up with the card's own title and objectives."""
    from gm import acts_to_ops

    s, e, _m = _market(worlds)
    _inst, quest, giver = _lost_thing(s, e)
    cards.note_heard(s, {"id": quest.id, "approach": "overheard"}, carried=[quest.title])
    said = f"I tell {giver.name}, \"I will find it for you.\""
    frame = {"question": False, "claims": [], "actions": [
        {"act": "talk", "target": giver.name, "span": said[2:]}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    assert acts_to_ops.take_ups(rows, frame, s, ask=None) == []
    asked: list = []

    def ask(span, who, matter):
        asked.append((who, matter))
        return "agrees to do it"

    notes = acts_to_ops.take_ups(rows, frame, s, ask=ask)
    assert asked == [(giver.name, quest.title)] and notes
    plan = [{"op": "quest", "actor": "pc", "params": {"title": "Find the lost wood",
                                                       "objectives": ["Look for it"]}}]
    got = acts_to_ops.apply(plan, rows, frame, s)
    taken = [r for r in got if r["op"] == "quest"]
    assert len(taken) == 1 and taken[0]["params"]["quest"] == quest.id
    out = e.run(e.validate(taken, origin="author:test")).outcomes[-1]
    assert out.effects and out.effects[0].get("taken_up"), out.tell
    assert [r["title"] for r in cards.quest_log(s)["active"]] == [quest.title]


# --- the planned slot, and its read-back -----------------------------------------------------

def _pull_dict(standing, approach="overheard", **kw):
    return {"id": "q1", "title": "Find Tanna Ashbourne's lost Coldwood",
            "fact": "" if standing != "own" else "Search the approach for the Coldwood",
            "standing": standing, "approach": approach,
            "giver": {"ref": "c14", "name": "Tanna Ashbourne"},
            "doing": "minding the pitch", **kw}


def test_the_matter_slot_says_whose_the_matter_is():
    """Row 137's slot: "A matter the engine keeps open: Find Tanna Ashbourne's lost
    Coldwood — Search the approach for the Coldwood." Somebody else's matter is now shown
    only through the person carrying it, and the slot says it is not the player's; the
    player's own reads as theirs; a matter nobody can carry makes no slot."""
    mine = planned.matter_slot(_pull_dict("own"))
    assert mine["say"].startswith("The player's own open matter")
    assert "not_own" not in mine
    theirs = planned.matter_slot(_pull_dict("unheard"))
    assert theirs["not_own"] == "Find Tanna Ashbourne's lost Coldwood"
    assert "Tanna Ashbourne is here, minding the pitch" in theirs["say"]
    assert "not the player's" in theirs["say"] and "never heard of it" in theirs["say"]
    assert "Search the approach" not in theirs["say"]
    assert "keeps open" not in theirs["say"]
    assert planned.matter_slot(_pull_dict("heard", approach="go_between")) is None
    carried = planned.matter_slot(_pull_dict("heard", approach="go_between",
                                             carrier={"ref": "c2", "name": "Orla Venn"}))
    assert carried["say"].startswith("Orla Venn, who is here, mentions")
    assert planned.matter_slot("The bounty")["say"].startswith("A matter the engine keeps")


GOAL = "You keep the goal of finding Tanna Ashbourne's lost Coldwood in mind as you scout."


def test_a_matter_slot_that_makes_it_the_players_goal_is_asked_again_then_dropped(
        monkeypatch):
    """The read-back: the slot carrying somebody else's matter is read for the sentence
    that makes it the player's goal (`beat_verify.own_goal_sentence`), asked once more with
    that sentence named, and dropped when it says it again — never shipped."""
    from tests.test_planned_narration import LAST_BEAT, _fake as plan_fake, _scene

    s, engine = _scene()
    calls: list = []
    monkeypatch.setattr(planned.client, "chat",
                        plan_fake(calls, slot_text={"matter": [GOAL, GOAL]}))
    asked: list = []

    def goal(matter, text):
        asked.append((matter, text))
        return text if "keep the goal" in text else ""

    out = planned.write(engine, brief="BRIEF", player_input="I wait.", outcomes=[],
                        pull=_pull_dict("unheard"), goal=goal,
                        who=("stub-12b", "http://x", "ollama", ""), last_beat=LAST_BEAT)
    assert [m for m, _t in asked] == ["Find Tanna Ashbourne's lost Coldwood"] * 2
    redo = [c for c in calls
            if any("the player's own goal, and it is not theirs" in str(m.get("content"))
                   for m in c["messages"])]
    assert redo, "asked again with the sentence named"
    assert "keep the goal" not in out.text
    assert any("player's goal twice: dropped" in n for n in out.notes)


def test_the_read_back_answers_from_a_closed_list_of_the_narrations_sentences():
    """The question is the model's (models read); the answer is a sentence number from a
    list the code builds, speech blanked — the giver asking "will you find it?" is the
    ask, not the player's goal — and the page's own sentence comes back for the cut."""
    seen = {}

    def chat(messages, model, host, **kw):
        from gm.client import Reply

        seen["schema"] = kw["schema"]
        seen["user"] = messages[-1]["content"]
        line = next(ln for ln in seen["user"].splitlines() if "keep the goal" in ln)
        return Reply(json.dumps({"sentence": line.split(".", 1)[0]}), 0.1, model)

    text = ('Tanna Ashbourne frets at her pitch. "Will you find my Coldwood?" she asks. '
            + GOAL)
    got = beat_verify.own_goal_sentence(text, "Find Tanna Ashbourne's lost Coldwood",
                                        chat=chat, model="m")
    assert got == GOAL
    enum = seen["schema"]["properties"]["sentence"]["enum"]
    assert enum[0] == "none" and enum[1:] == [str(i) for i in range(1, len(enum))]
    assert "Will you find" not in seen["user"]
    assert beat_verify.own_goal_sentence("", "x", chat=chat) == ""

    def broken(*a, **kw):
        raise RuntimeError("down")

    assert beat_verify.own_goal_sentence(text, "x", chat=broken, model="m") is None


def test_the_free_beat_loses_the_sentence_that_makes_it_the_players_goal(monkeypatch):
    """The free narrator is told the same thing, and an instruction alone does not hold:
    its beat is read back and the sentence cut in code."""
    from gm.agent import GMAgent

    monkeypatch.setattr(beat_verify, "ENABLED", True)
    monkeypatch.setattr(beat_verify, "own_goal_sentence",
                        lambda text, matter, **kw: GOAL if GOAL in text else "")
    agent = GMAgent.__new__(GMAgent)
    agent.prose_model, agent.prose_host = "m", "h"
    agent.prose_provider, agent.prose_key = "ollama", ""
    beat = "You walk the furrows. " + GOAL + " What do you do?"
    text, note = agent._not_their_goal(beat, _pull_dict("unheard"))
    assert GOAL not in text and text.startswith("You walk the furrows.")
    assert "cut" in note
    same, none = agent._not_their_goal(beat, _pull_dict("own"))
    assert same == beat and none == ""


def test_a_schemes_step_on_a_quest_not_taken_says_whose_it_is(worlds):
    """Live 2026-10-27 (and the owner's save, row 82): walking out to the fields fired
    a-small-favour's `reached` step — "the approach, the ground where Glowvine grows" —
    for a quest the player had only overheard, and the beat had them "searching the soil
    where the luminescent Glowvine is known to take root". The step still fires (the
    scheme tests hold the world's story to moving), but its outcome names the quest as
    not the player's, and the planned slot for it carries the read-back mark."""
    from rules.engine import Outcome

    s, e, _m = _market(worlds)
    inst, quest, _giver = _lost_thing(s, e)
    step = {"action": {"do": "objective", "card": "errand", "n": 1}}
    assert schemes._progress_not_taken(s, inst, step) == quest.title
    assert schemes._progress_not_taken(s, inst, {"action": {"do": "grant"}}) == ""
    cards.take_up(s, quest.id)
    assert schemes._progress_not_taken(s, inst, step) == ""
    told = Outcome("", "scheme", tell="the approach, the ground where Glowvine grows.",
                   effects=[{"kind": "scheme", "not_own": "Fetch Glowvine for Peleth"}])
    slot = next(x for x in planned.build_plan(e, "I head out to the fields.", [told])
                if x["key"] == "fact1")
    assert slot["not_own"] == "Fetch Glowvine for Peleth"
    assert "somebody else's matter" in slot["say"]


# --- a job nobody holds -------------------------------------------------------------------

CLERK = ("The details are simple: you are to escort a shipment of supplies to the outpost "
         "and ensure no bandits interfere with the trade")


def test_a_reply_that_makes_up_work_nobody_holds_is_asked_again(monkeypatch):
    """The hiring table, the same report: the opening's own line was "Hands wanted for the
    week, fed and paid at the end of it", and the clerk's reply slot made up "escort a
    shipment of supplies to the outpost" — no such job, caravan or outpost in the engine.
    The reply of a speaker the engine holds no work from is read back
    (`beat_verify.invented_job_sentence`) and asked again with the sentence named."""
    from rules.engine import Outcome
    from tests.test_planned_narration import LAST_BEAT, _fake as plan_fake, _scene

    s, engine = _scene()
    calls: list = []
    monkeypatch.setattr(planned.client, "chat", plan_fake(calls, slot_text={"reply": [
        {"words": CLERK, "manner": "warmly"},
        {"words": "Hands are wanted for the week, fed and paid at the end of it",
         "manner": "warmly"}]}))
    jarek = next(a for a in s.actors.values() if not a.is_pc)
    talk = [Outcome("i1", "say", tell=f"You speak to {jarek.name}.",
                    effects=[{"kind": "said", "who": "", "to": jarek.ref}])]
    slots = planned.build_plan(engine, "I can fight.", talk, last_beat=LAST_BEAT)
    reply = next(x for x in slots if x["key"] == "reply")
    assert reply["no_job"] == jarek.name
    seen: list = []

    def job(speaker, text):
        seen.append(text)
        return text if "escort" in text else ""

    out = planned.write(engine, brief="BRIEF", player_input="I can fight.", outcomes=talk,
                        job=job, who=("stub-12b", "http://x", "ollama", ""),
                        last_beat=LAST_BEAT)
    assert len(seen) == 2 and "escort" not in out.text
    assert any("made up work — asked again, fixed" in n for n in out.notes)
    # A speaker who has put a quest to the player holds work: never asked.
    cards.open_quest(s, title="Mend the weir", objectives=["Mend it"], giver=jarek.ref,
                     known="offered")
    again = planned.build_plan(engine, "I can fight.", talk, last_beat=LAST_BEAT)
    assert "no_job" not in next(x for x in again if x["key"] == "reply")


def test_the_job_read_back_names_a_sentence_from_a_closed_list():
    def chat(messages, model, host, **kw):
        from gm.client import Reply

        lines = messages[-1]["content"].splitlines()
        hit = next(ln for ln in lines if "escort" in ln)
        return Reply(json.dumps({"sentence": hit.split(".", 1)[0]}), 0.1, model)

    text = f"'Good. {CLERK},' the guild clerk says warmly."
    got = beat_verify.invented_job_sentence(text, "the guild clerk", chat=chat, model="m")
    assert got and "escort" in got
