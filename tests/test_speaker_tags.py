"""Who said it is written by the model that wrote the line, not guessed afterwards.

docs/declared-not-guessed.md, the first door (2026-09-25). Before this, `hailed_by` and
`introductions` decided who spoke a quoted line from the words round it — the first role
word outside the quotes — and they misread: "'Gorvothor Kragnir,' he says" beside "a low,
resonant grind" took "low" for the speaker (2026-09-19), and any sentence naming a second
person hands the line to whichever role word comes first. The prose call now writes
`<say who=c3 to=you>'…'</say>`; `speech.lift` takes the tags out the moment a reply is
read and keeps what they said, and the old guess is only the fallback for untagged lines.

Prior art: Intra (Bicking, 2025) writes `<dialog from= to=>` inline for the same reason —
text markup over tools for narrative work. Nobody has measured tag compliance by 8-12B
models inside prose, so the turn log carries the measurement (`speech-tags`).
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from gm import judgement, narration, speech
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.sheet import load_pc


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="man by the fire"))
    s.add(instantiate("guildhand", scene=s, name="woman at the counter"))
    return s


def _refs(scene):
    return {a.name: r for r, a in scene.actors.items() if not a.is_pc}


# --- lifting ---------------------------------------------------------------------------

@pytest.mark.parametrize("tagged, clean, who, to", [
    ("<say who=c2 to=you>'You're late,'</say> she says.", "'You're late,' she says.",
     "c2", "you"),
    ('<say who="c2" to="you">\'Go.\'</say>', "'Go.'", "c2", "you"),
    ("<SAY WHO=c2 TO=c3>“Fine weather,”</SAY> the carter says.",
     "“Fine weather,” the carter says.", "c2", "c3"),
    ("<say who=c2>'Two days,' he says. 'Maybe three.'</say> He turns back.",
     "'Two days,' he says. 'Maybe three.' He turns back.", "c2", ""),
])
def test_tags_come_out_and_what_they_said_stays(tagged, clean, who, to):
    text, said = speech.lift(tagged, refs={"c2", "c3"})
    assert text == clean
    assert said and all(r["who"] == who and r["to"] == to for r in said)
    assert "<" not in text


def test_a_ref_nobody_holds_keeps_its_words_and_attributes_nothing():
    """An unknown ref is never trusted and never books anybody: the tool-call literature
    finds invented ids on unconstrained output at every model size, so every tag is
    checked against the roster."""
    text, said = speech.lift("<say who=c9 to=you>'Hello.'</say> A stranger nods.",
                             refs={"c2"})
    assert text == "'Hello.' A stranger nods."
    # Kept only so the miss can be counted: it attributes the line to nobody.
    assert said == [{"who": "", "to": "you", "line": "Hello.", "was": "c9"}]
    assert (speech.speaker(said, "Hello.") or {}).get("who") == ""


def test_a_broken_tag_never_reaches_the_page():
    for raw in ["<say who=c2>'Unclosed line.' The crowd shifts.", "Stray </say> close.",
                "<say who=c2><say who=c3>'Nested.'</say>"]:
        text, _ = speech.lift(raw, refs={"c2", "c3"})
        assert "say" not in text.lower() and "<" not in text, raw


def test_a_name_where_the_ref_belongs_is_read_as_that_person():
    text, said = speech.lift("<say who='the smith' to='you'>Come back tomorrow</say>, he says.",
                             refs={"c2"}, names={"the smith": "c2"})
    assert text == "“Come back tomorrow”, he says."
    assert said == [{"who": "c2", "to": "you", "line": "Come back tomorrow"}]


# --- the readers take the tag over the guess -------------------------------------------

def test_the_tag_decides_who_hailed_the_player(scene):
    """The guess takes the first role word outside the quotes: here "man", so the man by
    the fire was said to have hailed the player when the woman did."""
    man, woman = _refs(scene)["man by the fire"], _refs(scene)["woman at the counter"]
    tagged = (f"The man looks up from the fire. <say who={woman} to=you>'You're late,'"
              f"</say> the woman says.")
    beat, said = speech.lift(tagged, refs={man, woman})
    # The guess this replaced said [man]; since 2026-10-03 there is no guess at all: an
    # unbooked line hails nobody, and the beat reader books what the tags left out.
    assert judgement.hailed_by(scene, beat) == []
    assert judgement.hailed_by(scene, beat, said=said) == [woman]


def test_a_line_said_to_somebody_else_is_not_a_hail(scene):
    man, woman = _refs(scene)["man by the fire"], _refs(scene)["woman at the counter"]
    beat, said = speech.lift(f"<say who={woman} to={man}>'You never listen,'</say> the "
                             f"woman tells the man.", refs={man, woman})
    assert judgement.hailed_by(scene, beat, said=said) == []


def test_the_tag_decides_whose_name_was_given(scene):
    """"The woman glances at the man. 'Call me Kael,' he says." The guess reads the first
    role word, "woman", and gave her his name."""
    man, woman = _refs(scene)["man by the fire"], _refs(scene)["woman at the counter"]
    tagged = f"The woman glances at the man. <say who={man} to=you>'Call me Kael,'</say> he says."
    beat, said = speech.lift(tagged, refs={man, woman})
    assert narration.introductions(beat) == [("woman", "Kael")], "the defect this replaces"
    named = judgement.apply_introductions(scene, beat, "", said=said)
    assert named == [(man, "Kael")]
    assert scene.actors[man].name == "Kael" and scene.actors[woman].name != "Kael"


def test_an_untagged_line_is_the_readers_to_book(scene):
    """"'You're late,' she says", untagged. The old answer was a guess from the role word
    before the line; the beat reader books the line now (`speaker_real`), and the booked
    line is the hail."""
    from play.aftermath import speaker_real
    from tests.beat_reader import stub

    woman = _refs(scene)["woman at the counter"]
    beat = "The woman at the counter looks at you. 'You're late,' she says."
    assert judgement.hailed_by(scene, beat, said=[]) == []
    said: list = []
    reading = stub.read(beat, scene, who={"The woman": woman},
                        lines={"You're late": (woman, "you")})
    speaker_real.step(stub.ctx(scene, reading, text=beat, said=said))
    assert judgement.hailed_by(scene, beat, said=said) == [woman]


# --- every reader lifts, and nothing reaches the page ----------------------------------

def test_every_reader_of_a_models_narration_lifts_the_tags():
    """The examples teach the tags to every call that sees them, so every place a reply's
    narration is read must lift them before anything else touches the text."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path("gm/agent.py").read_text(encoding="utf-8"))
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def lifted(node) -> bool:
        while node in parents:
            node = parents[node]
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "_lift"):
                return True
        return False

    reads = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "get" and n.args
             and isinstance(n.args[0], ast.Constant) and n.args[0].value == "narration"]
    assert len(reads) >= 5
    for n in reads:
        assert lifted(n), f"gm/agent.py:{n.lineno} reads narration without lifting its tags"
    # The consequence call reads the reply's raw text, not a JSON field.
    raw = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "text"
           and isinstance(n.value, ast.Name) and n.value.id == "reply"
           and isinstance(parents.get(n), ast.Attribute) and parents[n].attr == "strip"]
    assert raw and any(lifted(n) for n in raw), "the consequence call reads raw text"
    opening = ast.parse(Path("play/opening_prose.py").read_text(encoding="utf-8"))
    assert any(isinstance(n, ast.Attribute) and n.attr == "lift"
               and isinstance(n.value, ast.Name) and n.value.id == "speech"
               for n in ast.walk(opening)), "the opening lifts its tags"


def test_every_speaking_example_is_tagged():
    """Demonstration beats instruction here (CLAUDE.md): an example with an untagged line
    teaches the model to leave lines untagged."""
    from gm import prompts

    for name in ("EXAMPLES", "CARRY_ON_EXAMPLES", "NPC_EXAMPLES", "COMBAT_EXAMPLES"):
        for i, e in enumerate(getattr(prompts, name)):
            raw = e["reply"].get("narration", "")
            clean, said = speech.lift(raw, refs={"c1", "c2", "c3"})
            assert len(said) == len(speech.spans(clean)), (name, i)


@pytest.fixture
def live(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import concurrency

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.current("tags")
        c.save()
        yield cm, c
        cm._LIVE.clear()


def test_a_tagged_turn_reaches_the_page_clean_and_opens_the_conversation(live, monkeypatch):
    """Through the path the player clicks: POST /api/say, a planned `narrate_only`, the
    real prose call with its reply scripted, and `_finish`."""
    cm, c = live
    from gm import client as gm_client
    from gm.client import Reply
    from play import views

    who = next(r for r, a in c.scene.actors.items() if not a.is_pc)
    name = c.scene.actors[who].name

    from gm.agent import TurnPlan

    def plan(agent, *a, **kw):
        agent.last_said = []
        return TurnPlan(narration="", intents=agent.engine.validate(
            [{"op": "narrate_only", "because": "talking"}]))

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    prose = (f"{name[0].upper()}{name[1:]} sets down what they were holding and looks at "
             f"you properly for the first time since you arrived, as if weighing whether "
             f"you are worth the trouble of an answer. The noise of the place goes on "
             f"around the two of you, carts and voices and somebody laughing too loudly "
             f"somewhere behind, and none of it seems to reach them. "
             f"<say who={who} to=you>'You've the look of somebody who has been walking "
             f"since before dawn,'</say> they say at last, and the corner of their mouth "
             f"moves. <say who={who} to=you>'Sit, if you like. Nobody here will mind.'</say> "
             f"They nod at the bench beside them and wait to see what you will do. What do "
             f"you do?")

    def chat(*a, **kw):
        return Reply(json.dumps({"narration": prose, "suggestions": ["I sit"]}), 0.1, "stub")

    monkeypatch.setattr(gm_client, "chat", chat)
    r = Client().post("/api/say", data=json.dumps({"text": "I nod to them."}),
                      content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    beat = next(b for b in reversed(r.json()["transcript"]) if b.get("who") == "gm")
    assert "<" not in beat["text"] and "say who" not in beat["text"]
    assert [s["who"] for s in beat.get("said", [])] == [who, who]
    c = cm.current()
    row = next(r for r in reversed(c.turn_log) if r.get("kind") == "speech-tags")
    assert row["tagged"] == 2 and row["hails_tagged"] == [who]


def test_the_model_is_shown_its_earlier_speech_tagged_and_the_checks_are_not():
    """Measured on the first live run with tags (2026-09-25, gemma-4-12B, 12 turns): 11 of
    21 quoted lines tagged, all or nothing per beat, and the untagged beats followed tagged
    ones the prompt had shown back with the tags lifted out. The model's own last two
    beats are the nearest demonstration it reads, so they carry their tags again — in the
    prompt only; every repetition and name check keeps reading the plain beat."""
    raw = ("The smith wipes his hands. <say who=c2 to=you>'Two days,'</say> he says. "
           "<say who=c2 to=you>'Maybe three, if the ore is bad.'</say>")
    plain, said = speech.lift(raw, refs={"c2"})
    assert speech.retag(plain, said) == raw
    transcript = [{"who": "gm", "kind": "setup", "text": plain, "said": said}]
    assert narration.own_prose(transcript) == [plain]
    assert narration.own_prose(transcript, tagged=True) == [raw]
