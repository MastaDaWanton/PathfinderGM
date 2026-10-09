"""After the player is beaten, robbed and left, the raiders do not come back on the page.

Reported 2026-10-09 by the skull-enemy lane (three runs, gemma-4-12B heretic, the caravan
ambush): the player went down, the winners robbed them and went (`rules/defeat.py`), and
the next Continue narrated the raiders still swinging — once with a shield the player
does not own — and that beat made new bystanders through the beat reader. Reproduced here
(docs/narrator-after-defeat.md has the runs): on the first replay of the defeat the page
read "The raider, his jaw bruised and swelling from your blow, ignores the pain and lunges
again … The raider in front of you lunges again, his blade aimed not at your chest, but at
the axle of the wagon" an hour after "The raider and the second raider have gone." Over
all the replays: the departed raiders back on the page in 8 of 8 narrated beats before
this fix (swinging in 7, "your buckler" in 1), and in 0 of 11 after.

Three causes, each fixed where it lives, none by reading English in code:

1. **The input.** The prose call was shown the fight as "the scene as it stands, which
   you are continuing", and not one line of what the downed door did: the hour, the
   robbery, who went (`own_prose` keeps engine lines out on purpose). The door's lines are
   marked `moved_on` and shown after the fight as where the scene stands now
   (`narration.since_narrated`), and the scene block says who is gone (`scene_now`'s
   `gone`, from the engine's own `left` records).
2. **The check.** The read back (`gm/beat_verify.py`) had no code for anybody not here,
   and the lunges at an axle hurt nobody and arrived nowhere — claims of nothing it could
   judge. It now offers the people held elsewhere in town as "not here" codes and asks
   which of them the page shows here anyway (`shown_here`); code judges somebody absent
   acting here, and the second read asks WHO the sentence shows and compares.
3. **The bodies.** `seen_people` made people from the reading of the draft, before the
   checks cut what was false; and the engine's walk-in door took anybody. Now a person who
   stood only in a sentence the guards struck is nobody (`Reading.struck`), and
   `Engine.walk_in` refuses a foe of the player's — they come back by the engine's doors.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from gm import beat_verify as bv
from gm import narration, prompts
from rules import attitude
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine
from rules.sheet import load_pc
from tests.test_seen_people import GATE, WORLD, _beat, veil  # noqa: F401 — the fixture

# The beat as the narrator wrote it on the first replay (2026-10-09, gemma-4-12B heretic,
# the caravan ambush on the road out of Xylorvotha), cut to the sentences the tests read.
LUNGES = ("The raider, his jaw bruised and swelling from your blow, ignores the pain and "
          "lunges again, his rapier whistling through the air toward the edge of the "
          "wagon's frame.")
MASTER = ("Vyraxys is a whirlwind of motion on the box, shouting orders that are half-lost "
          "to the wind.")
AXLE = ("The raider in front of you lunges again, his blade aimed not at your chest, but "
        "at the axle of the wagon.")
BEAT = f"{LUNGES} {MASTER} {AXLE} What do you do?"

PC = bv.Person("pc", "Tam a", pc=True)
MASTER_P = bv.Person("c1", "Vyraxys Vexarion", "trader")
DROVER = bv.Person("c2", "the drover", "commoner")
RAIDER = bv.Person("c4", "the raider", here=False)
SECOND = bv.Person("c5", "the second raider", here=False)


def _facts(**kw):
    base = dict(start="the road to Kalixiri", end="the road to Kalixiri",
                places=("the road to Kalixiri",),
                people=(PC, MASTER_P, DROVER, RAIDER, SECOND), clock=780)
    base.update(kw)
    return bv.Facts(**base)


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _chat(answer):
    def chat(messages, *a, **k):
        chat.asked.append(messages)
        return _Reply(json.dumps(answer))

    chat.asked = []
    return chat


EMPTY = {"player_ends_at": {"place": "the road to Kalixiri", "quote": ""},
         "changed_hands": [], "trades": [], "harmed": [], "arrived": [], "left": [],
         "time_of_day": [], "shown_here": []}


def _read(answer, facts=None, text=BEAT):
    facts = facts or _facts()
    reading = bv.read(text, facts, model="stub", chat=_chat(answer))
    assert not reading.error
    return reading, bv.diff(reading.claims, facts, text)


# --- 2. the check ----------------------------------------------------------------------

def test_the_departed_raiders_shown_on_the_page_are_found():
    """The measured beat: both lunges show c4, whom the engine holds off stage ("made-off")
    since the robbery — at an axle and a wagon frame, so no harm and no arrival: only a slot
    that asks who is shown here could see them. Each sentence is an `absent` contradiction
    with the fact named for the repair; the wagon master, listed too (the slot offers every
    code), is here and not judged."""
    answer = dict(EMPTY, shown_here=[
        {"who": "c4", "quote": "ignores the pain and lunges again"},
        {"who": "c1", "quote": "Vyraxys is a whirlwind of motion on the box"},
        {"who": "c4", "quote": "The raider in front of you lunges again"}])
    _r, found = _read(answer)
    assert [(d.kind, d.category) for d in found] == [("contradiction", "absent")] * 2
    assert {d.sentence for d in found} == {LUNGES, AXLE}
    assert all(d.ref == "c4" for d in found)
    assert "the raider is not here" in found[0].fact


def test_somebody_away_arriving_hurt_or_leaving_is_judged_by_where_the_engine_holds_them():
    """An away person walking in on the page, with no arrival the engine made, is not
    here; hurt here, likewise. Leaving is simply true of somebody already gone."""
    answer = dict(EMPTY, arrived=[{"who": "c5", "quote": "The raider in front of you"}],
                  harmed=[{"who": "c4", "how": "hurt",
                           "quote": "his jaw bruised and swelling from your blow"}],
                  left=[{"who": "c4", "quote": "Vyraxys is a whirlwind of motion"}])
    _r, found = _read(answer)
    assert sorted((d.category, d.sentence) for d in found) == [("absent", AXLE),
                                                               ("absent", LUNGES)]


def test_the_reader_is_asked_who_is_shown_only_when_somebody_is_away():
    """Every slot an enum the engine supplies (memory `ollama-schema-enforcement`: enums and
    required properties hold 6/6). The away raiders are codes, marked not here; and a beat
    with nobody away is asked exactly what it was asked before, so the bench's fifty beats
    of 2026-10-03 cannot move for it."""
    f = _facts()
    s = bv.schema(f)
    shown = s["properties"]["shown_here"]["items"]
    assert set(shown["required"]) == {"who", "quote"}
    assert {"pc", "c1", "c4", "c5", bv.NEW_PERSON} <= set(shown["properties"]["who"]["enum"])
    assert "shown_here" in s["required"]
    asked = bv.messages(BEAT, f)[-1]["content"]
    assert "c4: the raider — not here" in asked
    assert "bargeman" in bv.messages(BEAT, f)[3]["content"]
    home_facts = _facts(people=(PC, MASTER_P, DROVER))
    home = bv.schema(home_facts)
    assert "shown_here" not in home["properties"] and "shown_here" not in home["required"]
    plain = bv.messages(BEAT, home_facts)
    assert plain[0]["content"] == bv._SYSTEM and plain[3]["content"] == bv._DEMO2_USER
    assert "bargeman" not in json.dumps(plain[:5])
    assert "attacks" not in s["properties"]


def test_the_engine_side_lists_the_people_held_elsewhere_in_town_as_not_here(veil):
    """`facts_from` reads the beat reader's own list of the away (`away_people`), so the
    two readers of a beat cannot disagree about who is gone."""
    from types import SimpleNamespace

    scene, engine, gorm = veil
    foe = instantiate("thug", scene=scene, name="the raider")
    scene.arrive(foe, place_id=GATE)
    ctx = SimpleNamespace(engine=engine, scene=scene, was_at=scene.at, outcomes=())
    f = bv.facts_from(ctx)
    assert f.person(foe.ref) is not None and not f.person(foe.ref).here
    assert f.person(gorm.ref).here
    assert f.absent(foe.ref) and not f.absent(gorm.ref)


def test_the_second_read_of_somebody_absent_asks_who_the_sentence_shows():
    """The first live run after the fix: the reader put "Vyraxys is busy at the front" down
    as the raider shown here, and the yes-or-no second read ("Does this sentence show the
    raider here …?") answered yes twice of twice — the wagon master's sentence was cut. So
    an `absent` contradiction is confirmed by asking WHO the sentence shows, from the
    codes, and comparing in code: probed live on six of the run's sentences (the wagon
    master twice, the raiders four times), 6 of 6 answered as they should."""
    f = _facts()
    master = "Vyraxys is busy at the front, his voice now low and raspy."
    found = [bv._not_here(RAIDER, bv.Claim("shown", {"who": "c4"}, master, master, True)),
             bv._not_here(RAIDER, bv.Claim("shown", {"who": "c4"}, AXLE, AXLE, True))]
    answers = iter([{"shown": ["c1"]}, {"shown": ["pc", "c4"]}])

    def chat(messages, *a, **k):
        chat.asked.append((messages, k))
        return _Reply(json.dumps(next(answers)))

    chat.asked = []
    kept, refuted, _s = bv.confirm(found, f"{master} {AXLE}", f, model="stub", chat=chat)
    assert [d.sentence for d in kept] == [AXLE] and [d.sentence for d in refuted] == [master]
    question, kw = chat.asked[0]
    assert "which of these people does this sentence show" in question[-1]["content"]
    assert "c4" in kw["schema"]["properties"]["shown"]["items"]["enum"]


def test_the_new_kinds_are_the_registry_members_and_weigh_as_a_wound():
    from gm import checks
    from gm.checks import beat_verified

    assert checks.owner_of("beat-absent") is beat_verified
    assert beat_verified._KIND["absent"][1] == beat_verified._KIND["harm"][1]


# --- 3. the bodies -----------------------------------------------------------------------

def _hostile(actor):
    """Hostile on the attitude track, as `Engine._foes_settle` leaves everybody who fought
    the player (`rules/defeat.py` reads the same track for who stands over them)."""
    actor.add_condition(attitude.HOSTILE, None, source="test")


def test_a_foe_who_went_is_not_walked_back_in_by_the_page(veil):
    """`Engine.walk_in` is the door the page's people come through. A foe of the player's
    is refused at it — the robbers come back by `defeat.settle` or a fight, never because a
    beat wrote them standing on the road — and nobody is made in their place."""
    scene, engine, gorm = veil
    foe = instantiate("thug", scene=scene, name="the raider")
    scene.arrive(foe, place_id=GATE)
    _hostile(foe)
    assert attitude.of(foe, default="") == attitude.HOSTILE
    count = len(scene.people)
    assert engine.walk_in(foe.ref) is False and foe.at == GATE
    reading, _, rows = _beat(scene, "The raider stands by the door, watching you.", 70,
                             engine=engine, who={"The raider": foe.ref},
                             arrived=[foe.ref])
    assert foe.at == GATE and foe.ref not in scene.actors
    assert len(scene.people) == count, rows
    assert any(r.get("walked_in") is False for r in rows)


def test_a_friend_held_elsewhere_still_walks_in(veil):
    """The refusal is the attitude track's, not everybody's: the old fisherman still walks
    into the tavern when the page shows him there (`test_seen_people`'s case)."""
    scene, engine, gorm = veil
    owner = instantiate("guildhand", scene=scene, name="the old fisherman")
    scene.arrive(owner, place_id=GATE)
    assert engine.walk_in(owner.ref) is True and owner.ref in scene.actors


def test_nobody_is_made_from_a_sentence_the_guards_struck(veil):
    """The reader reads the draft before the checks; a person who stood only in a sentence
    a check then cut is not on the page the player reads, and is nobody. A sentence only
    reworded after the checks (the un-namer, "you" for the player's name) was not struck,
    and still shows whoever it showed."""
    scene, engine, gorm = veil
    count = len(scene.people)
    text = "A man in a dusty scarf swings a club at you. A girl sweeps the step."
    from tests.beat_reader import stub
    from play.aftermath import seen_people

    reading = stub.read(text, scene, engine=engine,
                        who={"A man": "new", "A girl": "new"},
                        new=[("A man", "here", "man in a dusty scarf"),
                             ("A girl", "here", "girl")])
    reading.strike("A girl sweeps the step.")          # the checks cut the swing
    rows = seen_people.step(stub.ctx(scene, reading, text="A girl sweeps the step.",
                                     engine=engine, world=WORLD, turn=80))
    made = [scene.people[r["made"]].name for r in rows if r.get("made")]
    assert made == ["girl"], rows
    assert any(r.get("why", "").startswith("the sentences that showed them") for r in rows)
    assert len(scene.people) == count + 1


# --- 1. the input --------------------------------------------------------------------------

DOWNED_LINES = [
    "You come round about an hour later, face down where you fell, on 1 hit point.",
    "The raider took 135 of your 180 Clans gold pieces.",
    "The raider and the second raider have gone.",
]


def _transcript():
    return ([{"who": "gm", "kind": "setup", "text": "The raider is closing the distance."},
             {"who": "gm", "kind": "consequence", "text": "The fight is over."},
             {"who": "player", "text": "…"}]
            + [{"who": "gm", "kind": "consequence", "text": t, "moved_on": True}
               for t in DOWNED_LINES]
            + [{"who": "player", "text": "…"}])


def test_the_lines_that_carried_the_scene_on_are_what_comes_after_the_last_beat():
    assert narration.since_narrated(_transcript()) == DOWNED_LINES
    later = _transcript() + [{"who": "gm", "kind": "setup", "text": "Dust on the road."}]
    assert narration.since_narrated(later) == []
    # Only the door's own lines: an award or a tell after a narrated beat is that beat's.
    assert "The fight is over." not in narration.since_narrated(_transcript())


def test_the_prose_call_sees_where_the_scene_stands_after_the_fight_it_narrated():
    """Measured: the first replay's prompt held the fight under "the scene as it stands,
    which you are continuing" and nothing of the hour, the robbery or who went. Now the
    fight is "the scene as it was then", the door's lines follow it as where the scene
    stands, and the scene block — last — names who is gone."""
    msgs = prompts.call_prose_messages(
        "BRIEF", [], prompts.CARRY_ON, [], earlier=["The raider is closing the distance."],
        since=DOWNED_LINES,
        scene_now_block=prompts.scene_now(None) or "")
    last = msgs[-1]["content"]
    assert "the scene as it stands, which you are continuing" not in last
    assert "the scene as it was then" in last
    assert last.index("The raider is closing") < last.index("SINCE THEN") \
        < last.index("have gone") < last.index("The player said")
    # Without the door's lines, the block is as it was.
    plain = prompts.call_prose_messages("BRIEF", [], prompts.CARRY_ON, [],
                                        earlier=["The raider is closing the distance."])
    assert "the scene as it stands, which you are continuing" in plain[-1]["content"]
    assert "SINCE THEN" not in plain[-1]["content"]


def test_the_scene_block_names_who_is_gone_on_the_beat_after_and_only_then(veil):
    scene, engine, gorm = veil
    said = prompts.scene_now(scene, gone=["the raider", "the second raider"])
    assert "GONE from here since the last passage" in said and "the second raider" in said
    assert "GONE" not in prompts.scene_now(scene)


# --- the real path: the downed door, then Continue ------------------------------------------

@pytest.fixture
def robbed(tmp_path):
    """The measured board: the player down and stable, two raiders standing over them on
    the road, hostile; the drover by the wagon."""
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        for name in ("the raider", "the second raider"):
            foe = instantiate("thug", scene=c.scene, name=name)
            c.scene.add(foe)
            _hostile(foe)
        pc = c.scene.pc()
        pc.purse = {"gp": 180}
        pc.hp = -2
        pc.apply_hp_state()
        pc.clear_states("state.down.dying")
        pc.add_condition("stable", None, source="test")
        c.save()
        yield c
        cm._LIVE.clear()


def test_after_the_robbery_continue_shows_the_narrator_who_went_and_the_page_keeps_them_gone(
        robbed, monkeypatch):
    """The whole path the player clicks: Continue through the downed door (robbed, the
    raiders go), then Continue again. The prose call is shown the door's lines and the
    gone; the narrator writes the measured lunge anyway; the read back finds the absent
    raider acting; the rewrite is refused by the scripted model, so the backstop cuts the
    sentence — and nobody is made."""
    from gm import agent as agent_mod
    from gm import beat_verify as bv_mod
    from play import views

    c = robbed
    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    monkeypatch.setattr(bv_mod, "ENABLED", True)
    bv_mod.clear_cache()
    asked: list = []
    raiders = [r for r, a in c.scene.people.items() if "raider" in a.name]

    def chat(messages, model, host="", **kw):
        system = str(messages[0]["content"])
        asked.append(messages)
        if system.startswith("You read a passage of a story told to a player"):
            return _Reply(json.dumps(dict(EMPTY, shown_here=[
                {"who": raiders[0], "quote": "The raider in front of you lunges again"}])))
        if system.startswith("You answer one yes-or-no question"):
            return _Reply('{"answer": "yes"}')
        if system.startswith("You answer one question"):      # who the sentence shows
            return _Reply(json.dumps({"shown": [raiders[0]]}))
        schema = kw.get("schema") or {}
        if "sentence" in (schema.get("properties") or {}):
            return _Reply(json.dumps({"sentence": AXLE}))      # a rewrite that fails
        return _Reply(json.dumps({"narration": f"{MASTER} {AXLE} What do you do?",
                                  "suggestions": [], "intents": []}))

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    client = Client()
    r = client.post("/api/say", data=json.dumps({"text": "", "carry_on": True}),
                    content_type="application/json")
    assert r.status_code == 200
    assert all(c.scene.people[ref].ref not in c.scene.actors for ref in raiders)
    count = len(c.scene.people)
    r = client.post("/api/say", data=json.dumps({"text": "", "carry_on": True}),
                    content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    prose = next(m for m in asked if "The player said: I take no action" in
                 str(m[-1]["content"]))[-1]["content"]
    assert "SINCE THEN" in prose and "have gone" in prose
    assert "GONE from here since the last passage" in prose
    page = c.transcript[-1]["text"]
    assert "lunges again" not in page and "Vyraxys" in page
    assert len(c.scene.people) == count
    assert all(ref not in c.scene.actors for ref in raiders)
