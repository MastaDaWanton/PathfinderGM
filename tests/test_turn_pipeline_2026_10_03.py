"""Lane D of the 2026-10-03 playtest (docs/playtest-2026-10-03.md, items 17-22): the
turn pipeline. Every case below is a line read off the owner's two Zhilvarnia saves
("market-talk" and "items"); the saves themselves are never committed. The research
behind each fix is in docs/turn-pipeline-2026-10-03.md.
"""
from __future__ import annotations

import io
import json
import logging
import urllib.error
from types import SimpleNamespace

import pytest

from gm import agent as agent_mod
from gm import client, judgement, ledger, narration, prompts
from play import campaign as C
from play import opening
from rules.intents import parse_all

from _a_truth import MARKET, scene_at


class _Reply:
    def __init__(self, text, model="stub"):
        self.text, self.seconds, self.model = text, 0.0, model

    def json(self):
        return json.loads(self.text)


# --- 17. the repeat guard and a conversation -----------------------------------------------

def _talk(words, to="c4"):
    return parse_all([{"op": "narrate_only"},
                      {"op": "say", "because": "the player said it",
                       "params": {"words": words, "to": to}}])


def test_a_new_question_to_the_same_man_is_not_the_last_turn_again():
    """Measured on market-talk: "about the docks" (say to c4) and then "I ask him who the
    master of the docks is" (say to c4) had one signature — op, `because` "the player said
    it", and no identifying param — so the guard refused five attempts running (75.8 s)
    and the turn was lost. The words are part of what a `say` IS."""
    previous = judgement._signature(_talk("about the docks"))
    plan = _talk("who the master of the docks is")
    v = judgement.review("I ask him who the master of the docks is.", plan, None,
                         previous=previous)
    assert v.ok, v.as_log()


def test_a_say_carrying_the_players_new_words_is_never_a_repeat():
    """The other lost turn: "Is there anything I can do for some coin?" then '"Is there
    anything I can do to earn some coin?"' (85.5 s, five refusals). And a player who says
    the same words twice on purpose is answered twice: the plan read them."""
    previous = judgement._signature(_talk("Is there anything I can do for some coin?", to=""))
    again = _talk("Is there anything I can do for some coin?", to="")
    v = judgement.review('"Is there anything I can do for some coin?"', again, None,
                         previous=previous)
    assert v.ok


def test_the_old_say_replayed_against_new_words_is_still_caught():
    """The guard still does its job: the plan that comes back with LAST turn's words while
    the player has said something else has not read them."""
    previous = judgement._signature(_talk("about the docks"))
    v = judgement.review("I ask him who the master of the docks is.",
                         _talk("about the docks"), None, previous=previous)
    assert [o.kind for o in v.objections] == ["repeats-the-last-turn"]


def test_a_signature_read_back_from_a_save_still_compares():
    """The campaign stores the signature as JSON and loads it as `[tuple(row)]`, whose
    params element is a LIST; `["", ""] != ("", "")`, so after a reload the guard could
    never fire on the first turn. Compared frozen now."""
    raw = [{"op": "check", "actor": "pc", "because": "over the wall",
            "params": {"skill": "stealth", "dc": {"band": "average"}}}]
    saved = [tuple(row) for row in json.loads(json.dumps(
        judgement._signature(parse_all(raw))))]
    v = judgement.review("two bravos come round the corner, I turn and fight",
                         parse_all(raw), None, previous=saved)
    assert not v.ok


def test_asking_again_for_what_was_refused_is_not_a_repeat(monkeypatch):
    """Measured live on the merged branch: the smith's counter was shut at half past one
    and the sale refused; the player asked again, "I offer the smith the crate and agree
    to sell it to him for whatever it is worth", and the planner's `sell crate to c13` —
    exactly last turn's, exactly right — was refused twice as a repeat, the turn degraded
    to narration, and the engine never said why the sale could not happen."""
    from gm import interpret

    monkeypatch.setattr(interpret, "_READINGS", {})
    said = "I offer the smith the crate and agree to sell it to him for whatever it is worth."
    interpret.remember(said, {"actions": [
        {"act": "give", "target": "the smith", "object": "the crate"},
        {"act": "sell", "object": "it", "target": "him"}]})
    plan = parse_all([{"op": "narrate_only"},
                      {"op": "sell", "actor": "pc", "params": {"item": "crate", "to": "c13"}}])
    v = judgement.review(said, plan, None, previous=judgement._signature(plan))
    assert v.ok, v.as_log()
    # The guard's own case stands: a plan that does something the player did NOT
    # declare this turn, repeated, has not read them.
    other = "I look around the forge."
    interpret.remember(other, {"actions": [{"act": "look"}]})
    v = judgement.review(other, plan, None, previous=judgement._signature(plan))
    assert [o.kind for o in v.objections] == ["repeats-the-last-turn"]


def test_a_quiet_plan_is_quiet():
    assert judgement.is_quiet(_talk("hello"))
    assert not judgement.is_quiet(parse_all([{"op": "check", "actor": "pc",
                                              "params": {"skill": "stealth",
                                                         "dc": {"band": "average"}}}]))


def test_the_repeat_guard_spends_one_retry_and_then_the_turn_degrades(monkeypatch):
    """Five attempts of five came back as the same plan after being told (76 s and 85 s on
    the owner's two turns), then two more slots went to a fallback that was not there. One
    retry is all the rule may spend: the same MECHANICAL plan a second time degrades the
    turn at once rather than rolling last turn's check again."""
    agent, _engine = scene_at(MARKET, [("the clerk", "guildhand")])
    stealth = [{"op": "check", "actor": "pc", "because": "over the wall",
                "params": {"skill": "stealth", "dc": {"band": "average"}}}]
    calls: list[str] = []

    def fake_chat(messages, model, host, **kw):
        calls.append(model)
        return _Reply(json.dumps({"narration": "", "intents": stealth}))

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    plan = agent.plan_turn("I ask the clerk who runs the docks.", history=[],
                           previous_intents=judgement._signature(parse_all(stealth)))
    told = [r for r in plan.rejections if "same thing as last turn" in r]
    assert len(told) == 1
    assert any("not retried" in r for r in plan.rejections)
    assert len(calls) == 2, calls
    assert [i.op for i in plan.intents] == ["narrate_only"]
    assert plan.repairs == ["turn degraded to narration after 2 failed attempts"]


# --- 18. the backup narrator that was never pulled -------------------------------------------

def test_a_404_from_ollama_says_the_model_is_not_installed(monkeypatch):
    """Logged twice on market-talk: "richardyoung/qwen3-4b-instruct-2507-abliterated could
    not be reached: cannot reach Ollama at http://localhost:11434: HTTP Error 404: Not
    Found. Start Ollama…" — while the same Ollama answered the narrator in the same turn.
    Ollama's routes answer 404 `model 'x' not found` for a model that is not pulled."""
    def not_pulled(req, *a, **k):
        raise urllib.error.HTTPError(
            req.full_url, 404, "Not Found", {},
            io.BytesIO(b'{"error":"model \'qwen-x\' not found"}'))

    monkeypatch.setattr(client.urllib.request, "urlopen", not_pulled)
    with pytest.raises(client.ModelNotInstalled) as caught:
        client.chat([{"role": "user", "content": "hi"}], "qwen-x", "http://localhost:11434")
    said = str(caught.value)
    assert "not installed" in said and "cannot reach" not in said
    assert isinstance(caught.value, client.ModelUnavailable)   # every old catch still holds


def test_the_turn_is_not_handed_to_a_fallback_ollama_does_not_have(monkeypatch):
    """The two handoffs on market-talk each cost a 404 and a line saying Ollama was down.
    With the fallback absent from `/api/tags` it is never scheduled, and the turn log says
    so once."""
    from django.conf import settings

    narrator = settings.MODELS["narrator"]["model"]
    monkeypatch.setattr(client, "probe",
                        lambda *a, **k: client.Probe(True, installed=(narrator,)))
    agent, _engine = scene_at(MARKET)
    calls: list[str] = []

    def fake_chat(messages, model, host, **kw):
        calls.append(model)
        return _Reply("I will not emit JSON today.")

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    plan = agent.plan_turn("I look around.", history=[])
    assert settings.MODELS["fallback"]["model"] not in calls
    assert len(calls) == 5
    assert any("no handoff" in r and "not installed" in r for r in plan.rejections)
    assert not any("handing the turn to" in r for r in plan.rejections)


def test_a_missing_model_is_logged_once_not_every_turn(caplog):
    with caplog.at_level(logging.WARNING, logger="pathfindergm"):
        assert client.say_missing_once("qwen-x", "http://localhost:11434", role="fallback")
        assert not client.say_missing_once("qwen-x:latest", "http://localhost:11434/")
    assert sum("not installed" in r.getMessage() for r in caplog.records) == 1


def test_has_model_reads_ollamas_own_spelling(monkeypatch):
    monkeypatch.setattr(client, "probe", lambda *a, **k: client.Probe(
        True, installed=("richardyoung/qwen3-4b-instruct-2507-abliterated:latest",)))
    assert client.has_model("richardyoung/qwen3-4b-instruct-2507-abliterated") is True
    assert client.has_model("llama3.1:8b") is False
    assert client.has_model("gpt-4o", provider="openai") is None   # hosted: not ours to ask


# --- 19. a rewrite goes back through the page checks -----------------------------------------

# The second polish market-talk shipped, reduced to its faults: the brief's refs on the
# page, and a line the grammar closed mid-word on a stray apostrophe.
_SHIPPED_TAIL = ("He finally turns his head, his eyes squinting under the brim of his cap. "
                 "\"You're going to have to decide how you want to play this. You can try "
                 "to find his name through the whispers of the dock-workers, or you can go "
                 "to the nearest merchant who still has a sense of the old ways and see if "
                 "they'll sell you a'")


def test_a_line_closed_by_the_wrong_mark_is_unfinished():
    """'…see if they'll sell you a\\'' read as finished: the double-quoted line ran to the
    end of the text and the last character was a quote mark, any quote mark. It shipped as
    "…sell you a'. What do you do?"."""
    assert narration.ends_unfinished(_SHIPPED_TAIL)
    kept, gone = narration.trim_unfinished(_SHIPPED_TAIL)
    assert kept.endswith('how you want to play this."')
    assert gone.endswith("sell you a'")
    for whole in ("He waits. 'Go home.'", "He nods. 'Go home,'", 'He nods. "Fine."',
                  "She smiles. “Come in.”"):
        assert not narration.ends_unfinished(whole), whole


def _rewrite_reply():
    body = ("The market is quiet at this hour, the stalls shuttered and the lamps low. "
            "The servant (c1) shifts the weight of the jugs in his arms. The man in the "
            "heavy coat (c4) leans against a timber post and studies the cracks in the "
            "boards before he answers you. \"The docks? Ask anybody who hauls there,\" he "
            "says, rubbing the back of his neck. \"They all know who signs the sheets.\" "
            "He looks past you toward the water, where a cart is being loaded in the "
            "half-light. A dog noses through a heap of straw by the well. ") * 2
    return _Reply(json.dumps({"narration": body + _SHIPPED_TAIL}))


def test_a_polish_rewrite_is_cleaned_like_a_first_draft(monkeypatch):
    """Market-talk's last turn: the draft was cut to 24 characters, the polish rewrote it,
    and the rewrite went to the page as written — "(c1)" and "(c4)" on it, and cut off
    mid-word. The page pass now runs on every candidate before it is judged."""
    agent, _ = scene_at(MARKET)
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _rewrite_reply())
    out, notes, attempts = agent.polish("'The docks?' sufficient.", min_chars=800)
    assert out != "'The docks?' sufficient.", notes
    assert "(c1)" not in out and "(c4)" not in out
    assert not narration.ends_unfinished(out)
    assert "sell you a'" not in out
    assert any("page:" in (a.note or "") for a in attempts)


def test_a_rewrite_the_registered_checks_fault_is_refused(monkeypatch):
    """The second polish also said "midnight" on an evening clock. Lane B registers a
    time-of-day check; the candidate is now judged by every registered check as well as
    the review, and a kind of fault the draft did not have refuses it — so the draft, the
    best earlier candidate, stands instead of the last one written."""
    from gm import checks

    agent, _ = scene_at(MARKET)
    ctx = agent._beat_context("turn", player_input="I ask him who the master of the "
                                                   "docks is.", brief="")

    def fake_run(c, errors=None):
        return [SimpleNamespace(kind="wrong-time-of-day")] if "midnight" in c.text else []

    monkeypatch.setattr(checks, "run", fake_run)
    reply = _rewrite_reply()
    reply.text = reply.text.replace("at this hour", "under the midnight air")
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: reply)
    draft = "'The docks?' sufficient."
    out, notes, _ = agent.polish(draft, min_chars=800, ctx=ctx)
    assert out == draft
    assert any(n.startswith("unrepaired") for n in notes)


def test_the_page_pass_runs_again_after_the_repairs(monkeypatch):
    """A repair late in `_groom` that writes a ref and a cut-off line onto the page — the
    state-claims repair stands in for every model repair after the first page pass — is
    cleaned before the hand-back is judged, as a first draft would have been."""
    agent, _ = scene_at(MARKET)

    def writes_badly(text, changes):
        return text + " The servant (c1) nods toward the water. And then the", ["x"], []

    monkeypatch.setattr(agent, "_repair_state_claims", writes_badly)
    out, notes, _ = agent._groom("You stand in the market and watch the carts go by.",
                                 rewrite=False, claims=False, hand_back=True)
    assert "(c1)" not in out and "And then the" not in out, out
    assert out.endswith("What do you do?")
    assert any(n.startswith("after the repairs") for n in notes)


# --- 20. eyes that drop are not a body that falls --------------------------------------------

_CLERK = ("The clerk’s eyes drop to the floor for a heartbeat, as if measuring the "
          "distance between your voice and his ears, before he looks back up.")


def test_the_clerks_eyes_dropping_is_not_the_clerk_down():
    """Items save, the counting house: this sentence was `contradicts-the-engine` — "the
    clerk of the counting house is described as down or dead" — and the turn spent a
    polish call on it. `_FELLED` read "drop to the floor" without asking whose."""
    state = {"the clerk": {"alive": True, "hurt": False}}
    assert narration.contradicts_state(_CLERK, state) == []
    assert not narration.felled(_CLERK)


@pytest.mark.parametrize("line", [
    "He drops to the floor.",
    "The clerk drops to the floor, his eyes rolling back.",
    "The clerk collapses, his gaze dropping to the floor.",
    "His gaze falls to the floor and he slumps against the wall.",
    "The guard falls dead.",
    "The man hits the ground hard.",
])
def test_a_body_going_down_still_reads_as_down(line):
    assert narration.felled(line)


@pytest.mark.parametrize("line", [
    "Her eyes briefly drop to the cobbles.",
    "His shoulders slump.",
    "The guard's voice dies to a whisper.",
    "His face falls still for a moment.",
])
def test_a_part_of_somebody_falling_is_not_them_falling(line):
    assert not narration.felled(line)


# --- 21. a deed shown in other words ---------------------------------------------------------

_DROP = {"act": "give", "target": "the Brunt of the weight", "place": "the ground",
         "span": "drop the Brunt of the weight on the ground"}


@pytest.mark.parametrize("passage", [
    # Both passages the repair wrote on the items save, each refused as "does not show".
    "You release your grip on the heavy weight and let it fall, the object hitting the "
    "dirt floor with a heavy thud.",
    "You loosen your grip on the heavy metal object and let it fall, the weight hitting "
    "the dirt floor with a dull thud.",
    # And the beat itself, which had shown it before any repair was asked for.
    "The coins are heavy in your purse, and the Brunt of the Weight is left behind on the "
    "dirt floor of the forge, its purpose finished.",
])
def test_the_drop_was_shown(passage):
    """The reading put the thing dropped in `target` (act give, place the ground), so it
    was struck from the cues as "the person it is done to", and the cues left were "drop"
    and "ground" — neither written. A deed done to a place keeps its thing as a cue, and
    "let it fall", "release", "set down" are the drop's own verb class."""
    deed = dict(_DROP, cues=narration.deed_cues(_DROP))
    assert narration.shows_deed(passage, deed)


def test_a_beat_without_the_drop_still_owes_it():
    deed = dict(_DROP, cues=narration.deed_cues(_DROP))
    assert not narration.shows_deed("The smith nods and turns back to the forge. You "
                                    "count the coins in your purse.", deed)


def test_a_verb_class_member_shows_the_cue():
    deed = {"act": "other", "span": "drop the crate", "cues": ["drop"]}
    assert narration.shows_deed("You set the crate down by the door.", deed)
    assert narration.shows_deed("You let it fall.", deed)
    assert not narration.shows_deed("You hold on to it.", deed)


# --- 22. the rolling memory ------------------------------------------------------------------

def test_travel_is_remembered_by_place_names_never_ids():
    """Items save: "you went to ca~urban:the-docks" — the travel effect carries the place
    as an id and the shape printed it, digits stripped. Both places are named now, from
    and to, and an id the table does not hold is still read as its own slug."""
    c = C.new_campaign("slice", seed=7)
    eng = c.engine()
    out = eng.run(eng.validate([{"op": "travel", "params": {"place": "the well"}}]))
    named = {p.id: p.name for p in eng.places()}
    for places in (named, None):
        entry = ledger.note(out.outcomes, turn=2, hist=3, places=places,
                            names={r: a.name for r, a in c.scene.people.items()})
        assert entry is not None
        assert "~" not in entry["text"] and ":" not in entry["text"], entry["text"]
        assert entry["text"].startswith("you went from the market to the well")


def test_an_old_entry_with_an_id_is_read_as_a_name():
    """Entries are never rewritten, so the owner's save keeps its ids; the block reads
    them as names on the way into the prompt."""
    block = ledger.block([{"hist": 1, "at": "Zhilvarnia",
                           "text": "you founded the storage area, went to "
                                   "ca~urban:the-docks/the-storage-area"}], before_hist=5)
    assert "~" not in block
    assert "went to the storage area" in block


def test_a_ref_nobody_can_name_is_not_printed():
    """"c4" with its digit stripped is "you told c". Nobody is better than that."""
    o = SimpleNamespace(op="say", effects=[{"kind": "said", "to": "c4", "words": "hello"}])
    entry = ledger.note([o], turn=1, hist=2, names={})
    assert entry["text"] == "you told someone, “hello”"


def test_a_measure_under_a_name_key_is_not_a_name():
    """A `say` with no addressee still carries a `regard` effect whose "to" is a number."""
    o = SimpleNamespace(op="say", effects=[{"kind": "said", "to": "", "words": "hello"},
                                           {"kind": "regard", "ref": "c4", "from": 35,
                                            "to": 37}])
    assert ledger.note([o], turn=1, hist=2, spoke_with="the clerk")["text"] == \
        "you told the clerk, “hello”"


def test_speech_is_remembered_with_the_person_spoken_to(monkeypatch):
    """Market-talk: "you spoke with someone" — the words named nobody, so the line named
    nobody, while the engine held the conversation with the man in the heavy coat."""
    from play import views
    from rules import states

    c = C.new_campaign("slice", seed=7)
    eng = c.engine()
    who = c.scene.actors["c4"]
    eng.join_talk(who)
    assert who.has_state(states.TALKING)
    views._remember(c, SimpleNamespace(outcomes=[]), '"Any work going?" I ask.')
    assert c.ledger[-1]["text"] == f"you spoke with {who.name}"
    assert c.ledger[-1]["at"] == f"the market, {c.location.name}"


def test_the_opening_frame_reaches_the_planner():
    """Every turn of both saves logged "dropped the oldest 1 message(s)" from the first
    turn on, and that one message was the opening — "Evening in Zhilvarnia… to find a bed
    you can pay for" — because a kept stretch must open on a player's line. It rides in
    its own slot now, like the GM's note, from turn one to turn sixty."""
    note = {"role": "user", "content": opening.private_note("The guild skims the tithe.")}
    frame = {"role": "assistant", "content": "Evening in Zhilvarnia. You came in out of "
                                             "the weather to find a bed you can pay for."}
    report: dict = {}
    first = prompts.call_one_messages("BRIEF", [note, frame], "What is going on?",
                                      report=report)
    assert frame in first and report["dropped"] == 0
    turns = []
    for i in range(60):
        turns += [{"role": "user", "content": f"I look around, turn {i}. " * 4},
                  {"role": "assistant", "content": '{"intents": []}'},
                  {"role": "assistant", "content": "The square is busy. " * 30}]
    report = {}
    late = prompts.call_one_messages("BRIEF " * 200, [note, frame] + turns, "I wait.",
                                     report=report)
    assert report["dropped"] > 0, "the premise: the history has outgrown the window"
    assert frame in late
