"""Asking the GM a question, out of character, and getting the truth.

The player asked for this in as many words and the honest answer was that the app had
no door for it: the only way out of the fiction was `/cheat`, which makes a statement
true rather than answering anything. Every multiplayer text tradition ships one — Diku
and its descendants have an `ooc` channel, MUSH has `page` — because somebody at the
table always needs to ask about the game without their character doing something.

The rules that make it worth having:

  * answered by the engine, never by a model, because a model's answer is a guess with
    good grammar and the whole point is to get the truth instead of the fiction;
  * not a turn — nothing rolls, no time passes, no NPC acts;
  * and never in the model's history, or the narrator reads the question and the answer
    as facts about the world and writes them into the next beat.
"""
from pathlib import Path

from play import gm_answers
from pagesource import table_source


def test_a_question_routes_to_what_it_asked_about():
    assert gm_answers.topics_for("who is here") == ["who"]
    assert gm_answers.topics_for("where am i") == ["where"]
    assert gm_answers.topics_for("am i hurt") == ["me"]
    assert gm_answers.topics_for("what am I carrying") == ["carrying"]
    assert gm_answers.topics_for("what just happened") == ["last"]
    # Nothing named means everything, because "/gm" on its own is "tell me the state".
    assert set(gm_answers.topics_for("")) == set(gm_answers.TOPICS)


def test_a_question_the_engine_cannot_answer_goes_to_the_gm():
    """The player's ruling, 2026-09-09: "I should be able to ask the GM anything,
    including questions about the world and questions about the system or the rules."
    Before it, seven topics answered and everything else was refused with a list of the
    seven, which is a door that answers seven questions and shuts on the eighth."""
    kind, text = gm_answers.answer(None, None, "what is the airspeed of a swallow")
    assert kind == "gm"
    assert text == "", "an unanswerable question should be handed on, not answered here"


def test_the_answer_comes_from_the_engine():
    from play import campaign as C

    c = C.new_campaign("slice", seed=7)
    eng = c.engine()
    eng.run(eng.validate([{"op": "spawn", "because": "the stall",
                           "params": {"template": "guildhand", "count": 1,
                                      "name": "the clerk"}}]))
    kind, said = gm_answers.answer(c, eng, "who is here")
    assert kind == "engine"
    assert "the clerk" in said
    # By ref, because a ref is what everything else in the app is keyed on and a
    # question about the game deserves the engine's own vocabulary.
    assert "(c" in said

    _, said = gm_answers.answer(c, eng, "where am i")
    assert eng.here().name in said


def test_asking_is_not_a_turn():
    """Nothing rolls, no time passes, nobody acts. The whole door is read-only."""
    from play import campaign as C

    c = C.new_campaign("slice", seed=7)
    eng = c.engine()
    before = (eng.scene.clock_minutes, len(eng.scene.actors), eng.scene.round)
    for q in ("", "who", "where", "am i hurt", "quests", "what just happened"):
        gm_answers.answer(c, eng, q)
    assert (eng.scene.clock_minutes, len(eng.scene.actors), eng.scene.round) == before


def test_the_answer_never_reaches_the_model():
    """An out-of-character exchange sitting in the conversation the narrator reads is,
    as far as the narrator is concerned, a fact about the world — and it will write it
    into the fiction on the next turn."""
    src = (Path(__file__).resolve().parents[1] / "play" / "views.py").read_text(
        encoding="utf-8")
    door = src[src.index("def _gm_answer("):][:1400]
    assert "c.transcript.append" in door
    # The call, not the word: the comment above it explains at length why `c.history`
    # is the one place this must never go, and the comment is not the bug.
    assert "c.history.append" not in door,         "the out-of-character answer is being fed to the model"


def test_the_gm_view_house_rule_has_a_reader_and_a_renderer():
    """It had a reader in the state payload and NO renderer anywhere, and no control on
    the bench either: turning it on changed nothing a player could see. Measured
    2026-09-08 by grepping for it."""
    root = Path(__file__).resolve().parents[1]
    views = (root / "play" / "views.py").read_text(encoding="utf-8")
    table = table_source()
    home = (root / "play" / "templates" / "play" / "home.html").read_text(encoding="utf-8")

    assert "schemes_mod.gm_view(c.scene)" in views, "the state no longer carries it"
    assert "renderGmView" in table, "the page has no renderer for it again"
    assert 'id="gmview"' in table, "the panel it renders into is gone"
    assert "data-hbgmview" in home, "the bench has no control to turn it on"

    doors = (root / "play" / "gm_answers.py").read_text(encoding="utf-8")
    assert "houserules.gm_view()" in doors, "/gm no longer honours the setting"
