"""The narration, the GM's table talk and the talk paraphrase of the 2026-11-15 playtest
(a Blood Bender outlaw on 0.3.6; log pgm-work/playtest-2026-11-15.md, the item numbers
below). Each test names what the page said."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from django.test import Client, override_settings


# --- #58: the talk paraphrase keeps its frame verb ------------------------------------------

def test_reported_speech_drops_the_tell_x_that_frame():
    """#58: "speaks to the sergeant of the watch, to the effect that tell the sergeant of the
    watch that I am the one who beat and robbed the merchant…" — the words came from their
    own verb, and the tell said the frame twice."""
    from rules.engine import reported_speech

    at = " to the sergeant of the watch"
    said = reported_speech("Vesna Kroll", at, "tell the sergeant of the watch that I am the "
                           "one who beat the merchant.", "the sergeant of the watch")
    assert said == ("Vesna Kroll speaks to the sergeant of the watch, to the effect that I am "
                    "the one who beat the merchant.")
    # The first words of the name are enough, with no "that".
    assert reported_speech("Vesna Kroll", at, "tell the sergeant I yield.",
                           "the sergeant of the watch").endswith("to the effect that I yield.")
    assert reported_speech("Vesna Kroll", " to Lyra Lyraxys", "tell Lyra I can fight.",
                           "Lyra Lyraxys").endswith("to the effect that I can fight.")
    # "ask" is the tell's own verb: a question is not a statement.
    assert reported_speech("Vesna Kroll", " to the harbourmaster",
                           "ask the harbourmaster what passage costs.", "the harbourmaster") \
        == "Vesna Kroll asks the harbourmaster what passage costs."
    # Anything else is told as it always was: "invite" carries the meaning.
    assert reported_speech("Vesna Kroll", " to the innkeeper", "invite the innkeeper up.",
                           "the innkeeper") == ("Vesna Kroll speaks to the innkeeper, to the "
                                                "effect that invite the innkeeper up.")


# --- #68: silence booked as speech -----------------------------------------------------------

def test_a_talk_read_with_no_words_books_no_say():
    """#68: "I say nothing and stare at the wall" was read `talk` with no `says`, and
    `inject_say`'s redactor booked "nothing and stare at the wall" as her line."""
    from gm import judgement

    line = "I say nothing and stare at the wall."
    reading = {"question": False, "actions": [
        {"act": "talk", "cost": "free", "span": "say nothing"},
        {"act": "look", "object": "the wall", "span": "stare at the wall"}]}
    raw = [{"op": "narrate_only"},
           {"op": "say", "because": "the player said it",
            "params": {"words": "nothing and stare at the wall.", "to": "c10"}}]
    out = judgement.own_words_only(raw, line, reading)
    assert not [i for i in out if i.get("op") == "say"]
    # A quotation is still speech, whatever the reading.
    quoted = [{"op": "say", "params": {"words": "Never.", "quoted": True}}]
    assert judgement.own_words_only(quoted, 'I say "Never."', reading) == quoted


# --- #35: a doubled word ---------------------------------------------------------------------

def test_a_doubled_word_is_said_once():
    """#35: "missing you entirely in a clumsy and clumsy strike"."""
    from gm import narration

    assert narration.undouble("a clumsy and clumsy strike") == "a clumsy strike"
    for kept in ("again and again", "closer and closer", "on and on",
                 '"No, no!" she says'):
        assert narration.undouble(kept) == kept


def test_a_line_with_no_opening_mark_is_given_one():
    """#71: "…Then the silence is your only defense. If you cannot find the words…,' the
    sergeant of the watch says" — a closing mark with no opening one."""
    from gm import narration

    page = ("The sergeant looms over you. If you cannot find the words, you will pay,' the "
            "sergeant of the watch says gruffly. What do you do?")
    assert narration.mend_orphan_close(page) == (
        "The sergeant looms over you. 'If you cannot find the words, you will pay,' the "
        "sergeant of the watch says gruffly. What do you do?")
    for whole in ("'Go home,' the guard says. The guards' boots ring.", "It's the dogs' bowl.",
                  "‘Go,’ she says."):
        assert narration.mend_orphan_close(whole) == whole


# --- #63, #95: the blow's own words ------------------------------------------------------------

def test_no_blow_wording_names_a_condition_the_band_is_not():
    """#63: "You are thrown off balance as the sergeant… misses you wildly" (the natural 1's
    own wording) and "you stumble, left unsteady on your feet" after a plain hit."""
    from gm import planned

    words = " ".join(w for pool in (*planned._MISS.values(), *planned._LEFT.values(),
                                    *planned._SEVERITY.values()) for w in pool)
    for bad in ("off balance", "unsteady", "shaken", "staggering under"):
        assert bad not in words, bad


def test_a_blow_names_its_weapon_as_a_sentence_does_and_keeps_a_stab_in_hand():
    """#95: "A mwk dagger finds its mark", and the same captain's stab told as "The
    captain's dagger flies through the air"."""
    from gm import planned
    from rules.engine import _in_hand, spoken_weapon

    assert spoken_weapon("mwk dagger") == "masterwork dagger"
    assert _in_hand({"category": "melee"}, "dagger")
    assert not _in_hand({"category": "ranged", "thrown": True}, "dagger")
    assert not _in_hand({"category": "melee", "natural": True}, "bite")
    assert not _in_hand({"category": "melee"}, "unarmed")
    pc = SimpleNamespace(is_pc=True, name="Vesna Kroll")
    captain = SimpleNamespace(is_pc=False, name="the captain")
    engine = SimpleNamespace(scene=SimpleNamespace(actors={"pc": pc, "c19": captain}))
    o = SimpleNamespace(actor="c19", blows=[
        {"result": "hit", "ref": "pc", "weapon": "mwk dagger", "in_hand": True,
         "type": "piercing", "severity": "glancing", "left": "marked"},
        {"result": "miss", "ref": "pc", "weapon": "mwk dagger", "in_hand": True,
         "how": "plain"}])
    facts = planned.blow_facts([o], engine)
    assert all("mwk" not in f for f in facts), facts
    assert all("masterwork dagger, in hand" in f for f in facts), facts


# --- #49: an attitude's end told as a change of manner -------------------------------------

def test_a_friendliness_that_runs_out_is_told_as_manner_not_magic():
    """#49: "Friendly wears off the merchant" came back "the lingering aura of warmth and
    peace dissipates from the merchant's body"."""
    from rules.engine import _ward_tell

    merchant = SimpleNamespace(name="the merchant", is_pc=False, has_state=lambda t: False)
    pc = SimpleNamespace(name="Vesna Kroll", is_pc=True)
    scene = SimpleNamespace(actors={"c9": merchant}, pc=lambda: pc)
    said = _ward_tell(scene, {"kind": "effect_ended", "ref": "c9", "what": "Friendly"})
    assert "wears off" not in said
    assert said.startswith("the merchant no longer acts friendly toward Vesna Kroll")
    # Any other effect is told as before.
    assert _ward_tell(scene, {"kind": "effect_ended", "ref": "c9", "what": "Bless"}) == \
        "Bless wears off the merchant."


# --- #16: the engine's line on the page --------------------------------------------------------

def test_a_slot_that_broke_a_tell_twice_gets_the_engine_line_retold(monkeypatch):
    """#16: "You cannot attempt sleight of hand untrained. Nothing is rolled." — the stand-in
    for a slot that broke a tell twice was the engine's own sentence. It is asked once more,
    narrowly, and kept only when the tells check finds nothing in it."""
    from gm import planned

    s = {"key": "fact1", "messages": [{"role": "system", "content": "SCENE"}], "max": 200}
    asked = []

    def call(slot, msgs, who, **kw):
        asked.append(msgs[-1]["content"])
        return SimpleNamespace(text='{"text": "Your fingers close on nothing."}',
                               model="m"), {"text": "Your fingers close on nothing."}

    monkeypatch.setattr(planned, "call_slot", call)
    clean = lambda text, tells: SimpleNamespace(error="", clashes=[], as_log=lambda: {})
    out = planned.Planned(text="", slots=[])
    line = "Vesna Kroll cannot attempt sleight of hand untrained. Nothing is rolled."
    assert planned._retold(s, line, ("m", "", "ollama", ""), None, clean, [line], out) == \
        "Your fingers close on nothing."
    assert line in asked[0] and "no check, roll" in asked[0]
    clash = lambda text, tells: SimpleNamespace(error="", clashes=[object()],
                                                as_log=lambda: {})
    assert planned._retold(s, line, ("m", "", "ollama", ""), None, clash, [line], out) == ""


# --- the GM's table talk: the scene, and the tells check --------------------------------------

def test_the_table_sees_who_is_here_and_how():
    """#44: "The man is long gone" of a merchant lying unconscious in the scene. #81: "You
    don't have the skill" to a character with ranks in Disguise."""
    from play import table_talk

    down = {"state.down", "state.down.unconscious"}
    merchant = SimpleNamespace(is_pc=False, name="the merchant",
                               has_state=lambda t: t in down)
    hidden = SimpleNamespace(is_pc=False, name="the cutpurse",
                             has_state=lambda t: t == "state.hidden")
    pc = SimpleNamespace(is_pc=True, name="Vesna Kroll", ranks={"disguise": 1, "climb": 0},
                         has_state=lambda t: False)
    scene = SimpleNamespace(actors={"pc": pc, "c9": merchant, "c3": hidden}, pc=lambda: pc)
    c = SimpleNamespace(scene=scene, turn_log=[
        {"kind": "turn", "outcomes": []},
        {"kind": "npc-turn", "outcomes": [{"tell": "The merchant's attack misses Vesna "
                                                  "Kroll (13 against AC 18)."}]}])
    said, checked = table_talk.scene_facts(c)
    assert said[0] == "Here with you: the merchant (unconscious)."
    assert said[1] == "Then: The merchant's attack misses Vesna Kroll."
    assert checked == ["Vesna Kroll is trained in these skills: disguise."]


def test_a_table_line_that_breaks_a_tell_is_asked_again_then_dropped(monkeypatch):
    """#25: "A solid gut punch" while the engine said "Nothing has landed yet — the first
    blow is still to be struck". The narrator's own tells check reads the line; a clash is
    remade once with the fact named, and dropped if it still breaks one."""
    from gm import beat_verify
    from play import table_talk

    monkeypatch.setattr(beat_verify, "ENABLED", True)
    clash = SimpleNamespace(words="A solid gut punch", tell="Nothing has landed yet.")
    reads = []

    def against(text, premises, **kw):
        reads.append(text)
        return SimpleNamespace(clashes=[clash] if "punch" in text else [])

    monkeypatch.setattr(beat_verify, "against_tells", against)
    agent = SimpleNamespace(prose_model="m", prose_host="", prose_provider="ollama",
                            prose_key="")
    mends = []

    def ask(msgs):
        mends.append(msgs[-1]["content"])
        return "Squaring up in the open. Bold."

    line, why, remade = table_talk._held_to_the_tells(
        agent, ask, [], "A solid gut punch.", "A solid gut punch.",
        ["What happened: Nothing has landed yet."], None, "", [])
    assert (line, why, remade) == ("Squaring up in the open. Bold.", "", True)
    assert "Nothing has landed yet." in mends[0]
    line, why, _ = table_talk._held_to_the_tells(
        agent, lambda m: "Another punch lands.", [], "A solid gut punch.", "x",
        ["What happened: Nothing has landed yet."], None, "", [])
    assert line == "" and why.startswith("contradicts the engine twice")


# --- #85: a cheat is no event in the fiction ---------------------------------------------------

@pytest.fixture
def live(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import concurrency

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.current("cheat")
        c.save()
        yield cm, c
        cm._LIVE.clear()


def test_a_cheat_is_told_out_of_the_fiction_and_nobody_answers_it(live, monkeypatch):
    """#85: "/cheat give me 40 gold pieces" was narrated ("You reach into your purse and take
    forty… gold pieces") and the harbourmaster answered it ("I see the coin")."""
    cm, c = live
    from play import views

    def no_narrator(*a, **kw):
        raise AssertionError("a cheat reached the narrator")

    monkeypatch.setattr(views, "_finish", no_narrator)
    monkeypatch.setattr(views, "_run_npc_turns", no_narrator)
    history = len(c.history)
    before = sum((c.scene.pc().purse or {}).values())
    r = Client().post("/api/say", data=json.dumps({"text": "/cheat I have 40 gold"}),
                      content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    c = cm.current()
    assert sum((c.scene.pc().purse or {}).values()) > before
    last = c.transcript[-1]
    assert last["who"] == "table" and last["text"].startswith("By the author's word:")
    assert c.transcript[-2]["kind"] == "aside"
    assert len(c.history) == history
