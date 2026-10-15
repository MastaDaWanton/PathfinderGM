"""The narrator switch: Free (the narrator as it always wrote) or Planned (gm/planned.py).

Measured 2026-10-09 on the owner's gemma-4-12B heretic, three live runs hand-scored against
the engine's facts: the free narrator made ~10 errors in 12 town beats, ~8 in 10
conversation beats and ~8-9 in 8 fight beats (invented people, inns and institutions, a
window escape written when the engine said only "battle is joined"); the engine-planned
beat, its slots written one call at a time, ~4, ~3 and ~2. Each test names what it holds:

  * the switch is a house rule that defaults to free, round-trips, and refuses nonsense —
    the content switch's own history (a key `set_active` wrote and `active` dropped);
  * the v2 slots: no closing slot (it came back "…stretches out before you" every beat),
    the player's line on the FIRST tell (a slot each said it twice), a "doing" slot only when
    the engine decided nothing, a reply only out of fights;
  * one act, one slot: a goodbye of three tells gave three farewell sentences;
  * one call per slot, each shown what is already written — the variant that beat writing
    every slot at once (a model asked for N things answers in parallel);
  * the "still" slot copying the beat before: 12 of 16 shared a five-word run, 6 of 16
    near-verbatim; named once, then dropped;
  * the 800-character floor never fires on a planned beat (its repair is free prose);
  * an intimate beat is always free; a failed slot hands the beat to free, never a blank;
  * "That's wrong" records which narrator wrote the beat and every slot call;
  * the brief's looks line no longer reads "Korvu: …", which models took for a NAME.
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest

from gm import agent as agent_mod
from gm import planned, prompts
from rules import houserules
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.sheet import load_pc

LAST_BEAT = ("The smith works the bellows without looking up. The forge breathes orange "
             "light across the scarred anvil and the racks of half-finished blades.")
SLOT_TEXT = {
    "still": "The bellows wheeze on, the anvil still waiting under its glow.",
    "fact1": "You ask the smith about the ore, and he hears you out.",
    "fact2": "He sets the tongs down on the bench.",
    "doing": "You lean on the doorframe and watch him work.",
    "keeps": "You keep watching the street.",
    "matter": "The debt you carry sits at the back of your mind.",
    "reply": "<say who=c1 to=you>'Ore comes up from the pits on the third day,'</say> "
             "Jarek says.",
}


class FakeWorld:
    name = "Testholme"
    secret = ""
    premise: dict = {}
    entities: dict = {}
    unwritten: list = []
    chronology: list = []
    factions: list = []

    def ancestors(self, _):
        return []


class FakeReply:
    def __init__(self, text, model="stub-12b"):
        self.text, self.seconds, self.model = text, 0.4, model
        self.done_reason, self.prompt_tokens, self.reply_tokens = "stop", 0, 0

    def json(self):
        return json.loads(self.text)


@pytest.fixture
def rules_dir(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    return tmp_path


def _scene(*, fighting=False):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    smith = instantiate("guildhand", scene=s, name="Jarek")
    smith.appearance = ("Korvu: Four-limbed and heavy-browed. Grey-streaked and unbothered "
                        "by it; a scar through one eyebrow.")
    s.add(smith)
    if fighting:
        s.initiative = [(r, 10) for r in s.actors]
        s.turn = 0
    return s, Engine(s, Dice(seed=3))


def _fake(calls, *, slot_text=None, free="", fail_slots=False):
    """`client.chat` as the tests see it: a slot reply for a slot schema, the free
    narration for a prose schema, and nothing else answered (the readers are off)."""
    texts = dict(SLOT_TEXT, **(slot_text or {}))

    def chat(messages, model, host, **kw):
        schema = kw.get("schema") or {}
        calls.append({"messages": messages, "schema": schema, "model": model})
        props = schema.get("properties") or {}
        if "text" in props:
            if fail_slots:
                raise RuntimeError("the model wrote nothing usable")
            key = re.findall(r'Now write slot \d+, "(\w+)"', messages[-1]["content"])[-1]
            said = texts[key]
            if isinstance(said, list):
                said = said.pop(0) if len(said) > 1 else said[0]
            return FakeReply(json.dumps({"text": said,
                                         "suggestions": ["Ask about the pits",
                                                         "Leave the forge"]}))
        if "narration" in props:
            return FakeReply(json.dumps({"narration": free}))
        raise RuntimeError("not answered in this test")

    return chat


# --- the switch --------------------------------------------------------------------------

def test_the_switch_defaults_to_free_round_trips_and_refuses_nonsense(rules_dir):
    """Free is the default, the owner flips it to try Planned, and the file must read back
    what it wrote: the content switch shipped once as a key `set_active` wrote and the
    whitelist in `active` dropped, so it could be pressed and never held."""
    assert houserules.narration() == "free"
    rules, problems = houserules.set_active({"narration": "planned"})
    assert not problems and rules["narration"] == "planned"
    assert houserules.narration() == "planned"
    rules, problems = houserules.set_active({"narration": "poetic"})
    assert problems and "'free' or 'planned'" in problems[0]
    assert houserules.narration() == "planned", "a refused change leaves the rule alone"


def test_the_switch_is_served_and_set_through_the_house_rules_endpoint(rules_dir):
    """The Settings card posts to /api/homebrew/rules like every other switch."""
    from django.test import Client

    web = Client()
    r = web.post("/api/homebrew/rules", data=json.dumps({"narration": "planned"}),
                 content_type="application/json")
    assert r.status_code == 200 and r.json()["rules"]["narration"] == "planned"
    r = web.post("/api/homebrew/rules", data=json.dumps({"narration": "loud"}),
                 content_type="application/json")
    assert r.status_code == 400 and r.json()["rules"]["narration"] == "planned"


# --- the plan ----------------------------------------------------------------------------

def test_the_v2_slots_carry_the_players_line_on_the_first_tell_and_never_close():
    """Bench run 1 (2026-10-09, 12 beats): the player's line and the tell each had a slot
    and said the same thing twice, and a closing slot came back "…stretches out before
    you" on every beat. Now: the line rides the first tell, and there is no close."""
    s, engine = _scene()
    outcomes = [Outcome("i1", "check", tell="Kesst Vayr makes the diplomacy check by 4."),
                Outcome("i2", "attack", tell="Kesst Vayr's attack misses Jarek.")]
    slots = planned.build_plan(engine, "I ask about the ore.", outcomes,
                               last_beat=LAST_BEAT)
    keys = [x["key"] for x in slots]
    assert keys == ["still", "fact1", "fact2", "reply"]
    assert '"I ask about the ore."' in slots[1]["say"]
    assert "I ask about the ore." not in slots[2]["say"]
    assert not any(k in ("close", "closing", "deed", "doing") for k in keys)


def test_a_doing_slot_only_when_the_engine_decided_nothing_and_a_reply_only_out_of_fights():
    """With no tells the player's deed gets its own slot (the bench's talk run, beat 1); in
    a fight the people answer with their turns, never with a reply slot."""
    s, engine = _scene()
    keys = [x["key"] for x in planned.build_plan(engine, "I greet the smith.", [],
                                                  last_beat=LAST_BEAT)]
    assert keys == ["still", "doing", "reply"]
    s2, fight = _scene(fighting=True)
    keys = [x["key"] for x in planned.build_plan(
        fight, "I punch him.", [Outcome("i1", "attack", tell="Kesst Vayr hits Jarek.")],
        last_beat=LAST_BEAT)]
    assert "reply" not in keys and "doing" not in keys


def test_one_act_is_one_slot_however_many_tells_it_made():
    """Flaw (b): "I say goodbye and walk on" came as three tells — leave Jarek, leave
    Arinthal, speak to Jarek — and the slots wrote three farewell sentences. Aggregated by
    the engine's own ops (Reiter & Dale's aggregation), never by the words."""
    s, engine = _scene()
    goodbye = [Outcome("i1", "leave_talk", tell="You take your leave of Jarek."),
               Outcome("i2", "leave_talk", tell="You take your leave of Arinthal."),
               Outcome("i3", "say", tell="Kesst Vayr speaks to Jarek, to the effect that "
                                         "goodbye")]
    slots = planned.build_plan(engine, "I say goodbye and walk on.", goodbye,
                               last_beat=LAST_BEAT)
    facts = [x for x in slots if x["key"].startswith("fact")]
    assert len(facts) == 1 and len(facts[0]["tells"]) == 3
    assert "ONE moment" in facts[0]["say"]
    # The step a blow needs is the blow's: the engine derives its id ("i1-close").
    blow = planned.acts([Outcome("i1-close", "move", tell="Kesst closes 10 ft to strike."),
                         Outcome("i1", "attack", tell="Kesst hits the guard.")])
    assert len(blow) == 1
    # Separate acts stay separate: a check and a blow are two moments.
    two = planned.acts([Outcome("a", "check", tell="x"), Outcome("b", "attack", tell="y")])
    assert len(two) == 2


def test_a_fight_declared_and_not_struck_is_not_shown_landing():
    """The first live planned fight (2026-10-10): the slot said "show the player doing
    it", the tell said "nothing has landed yet", and the model landed the punch; the truth
    pass cut it and the beat lost the declaration. Read off the engine's own
    `battle_joined` effect, the slot asks for the squaring-up and nothing after it."""
    s, engine = _scene()
    joined = Outcome("i1", "attack", tell="Battle is joined: Kesst Vayr squares off "
                     "against Jarek. Nothing has landed yet.",
                     effects=[{"kind": "battle_joined", "ref": "pc", "target": "c1"}])
    say = planned.build_plan(engine, "I punch him.", [joined], last_beat=LAST_BEAT)[1]["say"]
    assert "no blow lands" in say and "doing it and what came of it" not in say
    struck = Outcome("i1", "attack", tell="Kesst Vayr hits Jarek.")
    say = planned.build_plan(engine, "I punch him.", [struck], last_beat=LAST_BEAT)[1]["say"]
    assert "doing it and what came of it" in say


def test_an_arrival_has_no_still_slot():
    """Arriving somewhere, there is no "what was going on" to keep: the engine's travel
    outcome says so by its biome effect, not by the words of its tell."""
    s, engine = _scene()
    walk = Outcome("i1", "travel", tell="You are at the forge now.",
                   effects=[{"kind": "biome", "place": "forge", "was_place": "market"}])
    keys = [x["key"] for x in planned.build_plan(engine, "I walk to the forge.", [walk],
                                                  last_beat=LAST_BEAT)]
    assert keys[0] == "fact1"


def test_the_people_are_named_with_their_people_said_as_a_people():
    """"Korvu looks up from his work": the people's name taken for the person's, in both
    narrators. PEOPLE HERE says what Korvu is."""
    s, engine = _scene()
    people = planned.present(engine)
    msgs = planned.plan_messages("BRIEF", [{"key": "doing", "say": "x", "max": 10}], people,
                                 "the forge")
    assert "Jarek (c" in msgs[1]["content"]
    assert "one of the Korvu people; Korvu is their people, not their name" in \
        msgs[1]["content"]


# --- one call at a time ------------------------------------------------------------------

def test_each_slot_is_its_own_call_shown_the_plan_and_what_is_already_written(monkeypatch):
    """The Text-Blueprint iterative variant, which beat batch realisation in the bench:
    every slot is a call of its own, each opening with the same plan bytes and shown the
    slots already written, asked for one slot alone."""
    s, engine = _scene()
    calls: list = []
    monkeypatch.setattr(planned.client, "chat", _fake(calls))
    out = planned.write(engine, brief="BRIEF", player_input="I ask about the ore.",
                        outcomes=[Outcome("i1", "check", tell="Kesst asks Jarek.")],
                        who=("stub-12b", "http://x", "ollama", ""), last_beat=LAST_BEAT)
    assert [x["key"] for x in out.slots] == ["still", "fact1", "reply"]
    assert len(calls) == 3
    plan_bytes = out.messages[1]["content"]
    for c in calls:
        assert c["messages"][0] == out.messages[0]
        assert c["messages"][1]["content"].startswith(plan_bytes)
    assert "WRITTEN SO FAR" not in calls[0]["messages"][1]["content"]
    assert SLOT_TEXT["still"] in calls[1]["messages"][1]["content"]
    assert SLOT_TEXT["fact1"] in calls[2]["messages"][1]["content"]
    assert out.suggestions == ["Ask about the pits", "Leave the forge"], \
        "the last slot carries the chips, or the page keeps last beat's"


def test_a_still_slot_that_copies_the_last_beat_is_named_once_then_dropped(monkeypatch):
    """Flaw (a), measured on the bench's two runs: 12 of 16 still slots shared a five-word
    run with the beat before, 6 of 16 near-verbatim. Detected in code, asked once more
    with the copied words named, and dropped if it copies again — it changes nothing."""
    s, engine = _scene()
    copy = "The forge breathes orange light across the scarred anvil."
    calls: list = []
    monkeypatch.setattr(planned.client, "chat", _fake(calls, slot_text={"still": copy}))
    out = planned.write(engine, brief="BRIEF", player_input="I wait.", outcomes=[],
                        who=("stub-12b", "http://x", "ollama", ""), last_beat=LAST_BEAT)
    assert planned.copied_from(copy, LAST_BEAT)
    still_calls = [c for c in calls if '"still", and only' in c["messages"][1]["content"]]
    assert len(still_calls) == 2
    assert "reuses words from the last thing you wrote" in \
        still_calls[1]["messages"][1]["content"]
    assert copy not in out.text
    assert any("dropped" in n for n in out.notes)
    # A still slot in new words is kept as written.
    assert not planned.copied_from(SLOT_TEXT["still"], LAST_BEAT)


def test_speech_in_two_pairs_of_quotes_keeps_one():
    """Live, 2026-10-10: the reply slot came back with double quotes round the tagged
    speech, and the page read "'Best? Provisions for the long haul…' "."""
    said = "She shrugs. \"'Best? Provisions for the long haul.' \" She turns away."
    assert planned._unwrap_quotes(said) == \
        "She shrugs. 'Best? Provisions for the long haul.' She turns away."
    plain = "She says 'no' and then \"yes\"."
    assert planned._unwrap_quotes(plain) == plain


# --- through narrate_turn ----------------------------------------------------------------

def _agent(engine):
    return agent_mod.GMAgent(FakeWorld(), engine)


def test_the_length_floor_never_fires_on_a_planned_beat(rules_dir, monkeypatch):
    """A planned beat runs 380-580 characters by design (the bench) and the 800-character
    scene floor's repair is a whole-beat free-prose rewrite — the very prose the switch
    turns off. So no polish on a planned beat; on a free beat as short, it fires."""
    houserules.set_active({"narration": "planned"})
    s, engine = _scene()
    calls: list = []
    polished: list = []
    monkeypatch.setattr(agent_mod.client, "chat", _fake(calls, free="Short. " * 20))
    real_polish = agent_mod.GMAgent.polish

    def spy(self, text, *a, **k):
        polished.append(k.get("min_chars"))
        return real_polish(self, text, *a, **k)

    monkeypatch.setattr(agent_mod.GMAgent, "polish", spy)
    gm = _agent(engine)
    text, repairs, attempts = gm.narrate_turn(
        [Outcome("i1", "check", tell="Kesst asks Jarek about the ore.")],
        "I ask about the ore.", "BRIEF", earlier=[LAST_BEAT])
    assert gm.last_narration == "planned"
    assert len(text) < 800 and SLOT_TEXT["fact1"] in text
    assert polished == [], "no whole-beat rewrite on a planned beat"
    assert not any("too-short" in r for r in repairs)
    assert {a.kind for a in attempts} >= {"plan-slot"}
    assert text.rstrip().endswith("?"), "the hand-back question is kept"
    # The control: the same short beat from the free narrator meets the floor.
    houserules.set_active({"narration": "free"})
    gm2 = _agent(engine)
    gm2.narrate_turn([], "I wait.", "BRIEF", earlier=[LAST_BEAT])
    assert polished and polished[-1] == 800


def test_an_intimate_beat_is_always_free(rules_dir, monkeypatch):
    """The planned path has no briefing, no demonstrations and no 3,000-character budget
    for an intimate scene; with Planned on, an intimate beat still goes to free."""
    houserules.set_active({"narration": "planned"})
    s, engine = _scene()
    calls: list = []
    monkeypatch.setattr(agent_mod.client, "chat", _fake(calls, free="Long. " * 160))
    monkeypatch.setattr(agent_mod.GMAgent, "_intimate_beat", lambda self: True)
    gm = _agent(engine)
    gm.narrate_turn([], "I kiss her.", "BRIEF", earlier=[LAST_BEAT])
    assert gm.last_narration == "free"
    assert not any("text" in (c["schema"].get("properties") or {}) for c in calls)


def test_a_failing_slot_hands_the_beat_to_the_free_narrator_and_says_why(rules_dir,
                                                                        monkeypatch):
    """Never an empty page: a slot call that fails gives the beat to the free narrator,
    with the reason in the repairs and the failed call in the attempts."""
    houserules.set_active({"narration": "planned"})
    s, engine = _scene()
    calls: list = []
    free = ("The smith looks up from the anvil and wipes his hands on his apron. " * 14
            + "What do you do?")
    monkeypatch.setattr(agent_mod.client, "chat", _fake(calls, free=free, fail_slots=True))
    gm = _agent(engine)
    text, repairs, attempts = gm.narrate_turn([], "I wait.", "BRIEF", earlier=[LAST_BEAT])
    assert gm.last_narration == "free"
    assert text.startswith("The smith looks up")
    assert repairs and repairs[0].startswith("planned narration failed")
    assert any(a.kind == "plan-slot" and "failed" in a.note for a in attempts)


def test_a_reply_with_narration_in_its_quotes_is_asked_again(rules_dir, monkeypatch):
    """The first live planned beat (2026-10-10): asked who keeps order, the master of the
    market answered "…but the master of the market maintains the order of these stalls",
    `narration-in-quotes` cut the whole answer, and the question went unanswered. The same
    check now judges the reply slot as it is written, and the slot is asked once more
    with the fault named."""
    houserules.set_active({"narration": "planned"})
    s, engine = _scene()
    smith = next(r for r, a in s.actors.items() if not a.is_pc)
    bad = f"<say who={smith} to=you>'Jarek keeps order here, and Jarek alone.'</say>"
    good = f"<say who={smith} to=you>'I keep order here,'</say> he says, not looking up."
    calls: list = []
    monkeypatch.setattr(agent_mod.client, "chat",
                        _fake(calls, slot_text={"reply": [bad, good]}))
    gm = _agent(engine)
    text, repairs, attempts = gm.narrate_turn([], "I ask who keeps order.", "BRIEF",
                                              earlier=[LAST_BEAT])
    replies = [c for c in calls if '"reply", and only' in c["messages"][1]["content"]]
    assert len(replies) == 2
    assert "narration, not speech" in replies[1]["messages"][1]["content"]
    assert "I keep order here" in text and "Jarek alone" not in text
    assert [r["line"] for r in gm.last_said] == ["I keep order here,"], \
        "the first answer's line is not booked as said"


# --- That's wrong ------------------------------------------------------------------------

def test_thats_wrong_records_which_narrator_wrote_the_beat_and_every_slot_call(rules_dir):
    """Training data and comparisons must know which narrator wrote a beat. A planned
    beat's input is the plan and every slot call as it was sent; the record says
    "planned", and the exporter keeps those episodes out of the free narrator's sets."""
    from play import corrections
    from tools.corrections_to_pairs import convert

    beat = "You ask the smith about the ore. What do you do?"
    c = SimpleNamespace(id="plan-test", turn_log=[], ended=False,
                        scene=SimpleNamespace(awaiting=None),
                        transcript=[{"who": "player", "text": "I ask about the ore."},
                                    {"who": "gm", "kind": "setup", "text": beat}])
    slot_calls = [{"key": "fact1", "messages": [{"role": "user", "content": "slot 1"}],
                   "reply": '{"text": "You ask."}', "note": ""}]
    agent = SimpleNamespace(last_narration="planned", last_prose_slots=slot_calls,
                            last_prose_messages=[{"role": "system", "content": "PLAN"}],
                            last_prose_model="stub-12b", last_prose_draft=beat,
                            prose_model="stub-12b", _intimate_beat=lambda: False)
    corrections.remember_input(c, 1, agent=agent, player_input="I ask about the ore.",
                               brief="BRIEF", facts=["Kesst asks."])
    assert not c.turn_log, c.turn_log
    rec = corrections.mark(c, 1, [], "he never said that")
    assert rec["narration"] == "planned"
    assert rec["input"]["narration"] == "planned"
    assert rec["input"]["slots"] == slot_calls
    assert rec["input"]["messages"] == [{"role": "system", "content": "PLAN"}]
    sets = convert([rec])
    assert sets["examples.kto.jsonl"] == []
    assert sets["examples.planned.kto.jsonl"][0]["meta"]["narration"] == "planned"


# --- the looks line ----------------------------------------------------------------------

def test_the_looks_line_says_what_a_people_is_not_a_name():
    """Seen in BOTH narrators on 2026-10-09: the brief's "Looks (fact — …): Korvu:
    Grey-streaked…" was read as the person's name ("Korvu looks up from his work"), on
    beats where they had one. Said at the source as what it is."""
    from gm.brief import faces as brief_faces
    from rules import faces

    assert faces.for_a_model("Korvu: Grey-streaked and unbothered by it.") == \
        "one of the Korvu people: Grey-streaked and unbothered by it."
    assert faces.for_a_model("favors plain dress") == "favors plain dress"
    s, engine = _scene()
    smith = next(a for a in s.actors.values() if not a.is_pc)
    smith.described = True
    smith.described_as = ["A heavy-browed smith."]
    text, _ = brief_faces.section(SimpleNamespace(scene=s))
    assert "one of the Korvu people: Four-limbed" in text
    assert "| Korvu:" not in text


def test_the_scene_briefs_looks_line_reads_one_of_the_people():
    """The same, through the whole brief the narrator reads."""
    from gm import prompts as p
    from play import campaign as cm

    world = cm.load_cached(cm._resolve_world_source("fixtures/aurvantis-campaign.json"))
    s = Scene(location_id=world.by_name("Vormoor", kind="CITY").id)
    s.add(load_pc("fixtures/pc-kesst.json"))
    smith = instantiate("guildhand", scene=s, name="Jarek")
    smith.appearance = "Korvu: Four-limbed and heavy-browed. Grey-streaked."
    s.add(smith)
    brief = p.scene_brief(world, s, None, [])
    assert "keeps to it): one of the Korvu people:" in brief
    assert "keeps to it): Korvu:" not in brief
