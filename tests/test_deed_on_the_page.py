"""The player's act on the page, read by a model and held to the page in code.

The owner, 2026-10-05: "narrator does not describe my actions". The line was "I flirt with
Vroka"; the beat opened on her — her eyes travelling back, an amused smile, "A bold play,"
she says — and the flirt itself was never written. Not what was said, not how, not a
gesture.

Why the declared-deed check of 2026-10-01 missed it, on the real turn: the reader read the
line `other: flirt with Vroka`, and `narration.owed_deeds` owes an `other` only on a move
turn; talk was owed only without words and without "ask"/"tell"/"say". A still social turn
owed nothing. On the next turn ("…continuing to flirt with her") it did fire, and the cue
word "flirt" refused both passages the model wrote — "a low, teasing remark about her
daring nature" and "a playful remark about her sharp wit": the flirt, in other words.

Measured on tests/deeds/gold.py plus the owner's labelled beats (80 deeds, 54 not shown;
docs/narrator-guards.md, "The deed on the page"): the shipped check caught 2 of the 54
(P 0.40, R 0.04); the deed reader, gemma-4-12B, caught 53, with 3 false alarms on the 26
shown (P 0.95, R 0.98, three runs within one alarm of each other).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from gm import deed_reader, narration, prompts
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

LINE = "I flirt with Vroka"
RAW = json.dumps({"question": False, "actions": [
    {"span": "flirt with Vroka", "commit": "done", "target": "Vroka", "act": "other"}],
    "claims": []})
READING = {"question": False, "actions": [{"act": "other", "target": "Vroka",
                                           "commit": "done"}],
           "claims": [], "raw": RAW}
# The shape of the owner's beat, shortened and reworded: it opens on her reaction.
BEAT = ("Vroka's eyes travel back to you, and a small, amused smile plays on her lips. "
        "She leans against the archway. 'A bold play,' she says. The guard at the post "
        "shifts his weight. What do you do?")
STILL = [SimpleNamespace(op="narrate_only", status="resolved", tell="")]
# What the model wrote when asked, live, 2026-10-05 (the second turn's repair call):
# the flirt in other words, which the cue word refused.
PASSAGE = ("You lean in, your voice dropping to a low murmur as you deliver a playful "
           "remark about her sharp wit.")


class _World:
    name, secret, premise, entities = "Testholme", "", {}, {}
    unwritten, chronology, factions = [], [], []

    def ancestors(self, _):
        return []


class _Reply:
    def __init__(self, payload):
        self.text = json.dumps(payload)
        self.seconds, self.model = 0.3, "stub"

    def json(self):
        return json.loads(self.text)


def _verdict(how, sentence="0"):
    return {"d1": {"sentence": str(sentence), "how": how}}


@pytest.fixture
def gate(monkeypatch):
    """Kesst, Vroka and a guard, the deed reader on. `reads` is the queue of the reader's
    answers, in the order asked; `passages` the deeds call's."""
    from gm import agent as agent_mod
    from gm.agent import GMAgent

    monkeypatch.setattr(deed_reader, "ENABLED", True)
    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="Vroka"))
    s.add(instantiate("thug", scene=s, name="Gorm"))
    gm = GMAgent(_World(), Engine(s, Dice(seed=3)))
    gm.reading = dict(READING)
    monkeypatch.setattr(GMAgent, "polish", lambda self, text, **k: (text, [], []))
    state = SimpleNamespace(reads=[], passages=[], read_calls=[], deed_calls=[])

    def chat(messages, *a, **k):
        system = messages[0]["content"]
        if system.startswith("You check one passage"):
            state.read_calls.append(messages)
            return _Reply(state.reads.pop(0))
        if "WRITE ONLY THIS, IN THIS ORDER" in messages[1]["content"]:
            state.deed_calls.append(messages)
            return _Reply({"passage": state.passages.pop(0)})
        raise RuntimeError("no model in this test")

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    monkeypatch.setattr(deed_reader, "read", _read_through(deed_reader.read, chat))
    return gm, state


def _read_through(real, chat):
    def read(*a, **k):
        k["chat"] = chat
        return real(*a, **k)
    return read


def _groom(gm, text=BEAT, said=LINE, outcomes=STILL):
    gm.deed_lines = []
    return gm._groom(text, player_input=said, brief="The gate.",
                     earlier=["The gate is a hive of activity."], facts=[],
                     hand_back=True, claims=False, outcomes=list(outcomes))


# --- why it was missed ------------------------------------------------------------------

def test_the_shipped_check_owed_nothing_on_the_owners_turn():
    """The regression record: `owed_deeds` owes `other` only on a move turn, so the flirt
    was never looked for. The reader's list owes it."""
    assert narration.owed_deeds(READING, LINE, STILL) == []
    assert [d["span"] for d in deed_reader.deeds_of(READING, LINE, STILL)] == \
        ["flirt with Vroka"]


def test_the_cue_word_refused_the_flirt_in_other_words():
    """Live, 2026-10-05, the next turn: both repair passages refused as "does not show"."""
    deed = {"span": "continuing to flirt with her",
            "cues": narration.deed_cues({"span": "continuing to flirt with her"})}
    assert not narration.shows_deed(PASSAGE, deed)


def test_the_cue_word_takes_the_aftermath_for_the_deed():
    """"The words of your challenge hang in the damp air" — the beat picking up after the
    challenge, which the owner's 2026-10-01 report names — carries the cue word."""
    deed = {"cues": narration.deed_cues({"span": "challenge the goblins to a dance-off"})}
    assert narration.shows_deed("The words of your challenge hang in the damp air.", deed)


# --- which deeds are owed -----------------------------------------------------------------

def _reading(*actions):
    raw = json.dumps({"actions": [dict(a) for a in actions]})
    return {"actions": [{k: v for k, v in a.items() if k != "span"} for a in actions],
            "raw": raw}


def test_speech_is_owed_too():
    line = "I ask the smith about the ore he uses."
    r = _reading({"span": "ask the smith about the ore he uses", "act": "talk",
                  "target": "the smith", "says": "about the ore he uses"})
    assert [d["span"] for d in deed_reader.deeds_of(r, line, STILL)] == \
        ["ask the smith about the ore he uses"]


@pytest.mark.parametrize("act,commit", [("go", "done"), ("look", "done"),
                                        ("wait", "done"), ("talk", "intended"),
                                        ("talk", "asked"), ("cast", "done")])
def test_what_the_engine_writes_itself_or_is_not_done_is_not_owed(act, commit):
    r = _reading({"span": "do the thing", "act": act, "commit": commit})
    assert deed_reader.deeds_of(r, "I do the thing", STILL) == []


def test_a_refused_hand_over_owes_the_refusal():
    r = _reading({"span": "pay the fee", "act": "give", "object": "the fee"})
    refused = [SimpleNamespace(op="give", status="refused", tell="You carry no coin.")]
    assert deed_reader.deeds_of(r, "I pay the fee", refused) == []


def test_a_question_to_the_game_owes_nothing():
    assert deed_reader.deeds_of({"question": True, "actions": []}, "is it raining?") == []


# --- the read, held to the page -----------------------------------------------------------

def _chat_answering(payload, seen=None):
    def chat(messages, *a, **k):
        if seen is not None:
            seen.append((messages, k))
        return _Reply(payload)
    return chat


def test_the_reader_is_asked_closed_questions():
    seen = []
    deed_reader.read(BEAT, ["flirt with Vroka"], LINE, chat=_chat_answering(
        _verdict("absent"), seen))
    messages, kw = seen[0]
    schema = kw["schema"]
    assert schema["required"] == ["d1"]
    one = schema["properties"]["d1"]
    assert one["required"] == ["sentence", "how"]
    assert one["properties"]["how"]["enum"] == ["shown", "after", "absent"]
    assert one["properties"]["sentence"]["enum"] == ["0", "1", "2", "3", "4", "5"]
    assert "d1. flirt with Vroka" in messages[-1]["content"]
    assert "1. Vroka's eyes travel back to you" in messages[-1]["content"]


def test_an_absent_deed_is_missing():
    got = deed_reader.read(BEAT, ["flirt with Vroka"], LINE,
                           chat=_chat_answering(_verdict("absent")))
    assert [v.span for v in got.missing] == ["flirt with Vroka"]


def test_a_reaction_cited_as_the_deed_is_not_believed():
    """A `shown` must name a sentence about the player. "She leans against the archway"
    is not, so the reading abstains — neither shown nor alarmed."""
    got = deed_reader.read(BEAT, ["flirt with Vroka"], LINE,
                           chat=_chat_answering(_verdict("shown", 2)))
    assert got.verdicts[0].verdict == deed_reader.UNSURE
    assert got.missing == []


def test_a_shown_deed_in_a_sentence_about_you_stands():
    text = PASSAGE + " " + BEAT
    got = deed_reader.read(text, ["flirt with Vroka"], LINE,
                           chat=_chat_answering(_verdict("shown", 1)))
    assert got.verdicts[0].verdict == "shown" and got.missing == []


def test_the_players_own_quoted_words_count_as_about_them():
    line = 'I lean in and whisper "My heart is steady enough to win."'
    text = "'My heart is steady enough to win,' comes out barely a breath. She smiles."
    got = deed_reader.read(text, ['whisper "My heart is steady enough to win."'], line,
                           chat=_chat_answering(_verdict("shown", 1)))
    assert got.verdicts[0].verdict == "shown"


def test_a_failed_read_says_so_and_judges_nothing():
    def down(*a, **k):
        raise ConnectionError("ollama down")

    got = deed_reader.read(BEAT, ["flirt with Vroka"], LINE, chat=down)
    assert got.error.startswith("ConnectionError") and got.verdicts == []


# --- in the turn ----------------------------------------------------------------------------

def test_the_owners_turn_gets_the_flirt_written_first(gate):
    gm, st = gate
    st.reads = [_verdict("after", 1), _verdict("shown", 1)]
    st.passages = [PASSAGE]
    out, repairs, attempts = _groom(gm)
    assert out.startswith(PASSAGE) and out.endswith("What do you do?")
    assert BEAT in out
    assert any(r == "declared and not shown: wrote flirt with Vroka" for r in repairs), repairs
    # The beat was read, then the passage; and both reads are in the turn log.
    assert len(st.read_calls) == 2 and len(st.deed_calls) == 1
    rows = [r for r in gm.mention_rows if r.get("kind") == "deeds-read"]
    assert [r["verdicts"][0]["verdict"] for r in rows] == ["after", "shown"]
    # Told to report speech, not to quote words the player never wrote.
    assert "quote nothing" in st.deed_calls[0][0]["content"]


def test_a_beat_that_shows_the_flirt_costs_one_read_and_no_repair(gate):
    gm, st = gate
    st.reads = [_verdict("shown", 1)]
    text = "You catch her eye and tell her she wears the gate well. " + BEAT
    out, repairs, _ = _groom(gm, text=text)
    assert out == text and len(st.deed_calls) == 0
    assert not any("declared" in r for r in repairs)


def test_when_the_passage_will_not_hold_the_players_own_line_opens_the_beat(gate):
    """Twice refused (it hands the turn back), so the backstop: the player's line, turned
    onto "you" — and marked ours, so the next prose call never sees it as its own."""
    gm, st = gate
    st.reads = [_verdict("absent")]
    st.passages = ["You smile at her. Do you lean closer?", "You smile. What now?"]
    out, repairs, _ = _groom(gm)
    assert out.startswith("You flirt with Vroka. ") and BEAT in out
    assert gm.deed_lines == ["You flirt with Vroka."]
    assert any("hands the turn back" in r and "wrote the player's own line" in r
               for r in repairs), repairs


def test_the_backstop_is_not_the_same_line_twice_running(gate):
    gm, st = gate
    firsts = []
    for _ in range(3):
        st.reads = [_verdict("absent")]
        st.passages = ["What now?", "What now?"]
        out, _r, _a = _groom(gm)
        firsts.append(out.split(" Vroka's eyes")[0])
    assert len(set(firsts)) == 3, firsts
    assert all("flirt with Vroka" in f for f in firsts)


def test_a_failed_call_still_gets_the_players_line(gate, monkeypatch):
    from gm import agent as agent_mod

    gm, st = gate
    st.reads = [_verdict("absent")]
    real = agent_mod.client.chat

    def chat(messages, *a, **k):
        if "WRITE ONLY THIS, IN THIS ORDER" in messages[1]["content"]:
            raise ConnectionError("ollama down")
        return real(messages, *a, **k)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    out, repairs, _ = _groom(gm)
    assert out.startswith("You flirt with Vroka.")
    assert any("the call failed (ConnectionError)" in r for r in repairs), repairs


def test_a_passage_that_speaks_for_the_player_is_refused(gate):
    """Only the player speaks for their character: a passage with lines the player never
    wrote is refused, and the second try (reported speech) goes in."""
    gm, st = gate
    st.reads = [_verdict("absent"), _verdict("shown", 1)]
    st.passages = ["'You look like trouble worth having,' you say, grinning at her.",
                   PASSAGE]
    out, repairs, _ = _groom(gm)
    assert out.startswith(PASSAGE)
    assert "puts words in the player's mouth" in st.deed_calls[1][-1]["content"]


def test_a_passage_the_reader_says_does_not_show_it_is_retried(gate):
    gm, st = gate
    st.reads = [_verdict("absent"), _verdict("absent"), _verdict("shown", 1)]
    st.passages = ["You glance at the guard.", PASSAGE]
    out, _repairs, _ = _groom(gm)
    assert out.startswith(PASSAGE)
    assert st.deed_calls[1][-1]["content"].startswith(
        "That passage does not show flirt with Vroka.")


def test_not_in_a_fight_nor_an_intimate_beat(gate):
    gm, st = gate
    gm.intimate = SimpleNamespace(fired=True, mode="intimate", demonstrations=None)
    _groom(gm)
    assert st.read_calls == []


# --- the backstop's words ---------------------------------------------------------------------

@pytest.mark.parametrize("line,missing,whole,want", [
    ("I flirt with Vroka", ["flirt with Vroka"], True, "You flirt with Vroka."),
    ("i pull her close to me and kiss my fingers", [], True,
     "You pull her close to you and kiss your fingers."),
    ('"I can fly so i doubt I\'ll get lost."', [], True,
     "You say, “I can fly so i doubt I'll get lost.”"),
    ('I go back to vroka, "how was that?"', ["how was that?"], False,
     "You say, “How was that?”"),
    ("I thank her smack her butt and then leave", ["thank her", "smack her butt"], False,
     "You thank her and smack her butt."),
    ("I ignore everyone else and pull Vroka close to me continuing to flirt with her",
     ["continuing to flirt with her"], False,
     "You ignore everyone else and pull Vroka close to you continuing to flirt with her."),
    ("I ask him who I should see. I am tired", [], True,
     "You ask him who you should see. You are tired."),
])
def test_the_players_line_turned_onto_you(line, missing, whole, want):
    """AI Dungeon's Do mode: "You" in front, first person turned outside the quotes, the
    player's quoted words untouched. A gerund span cannot take "you", so the whole line."""
    assert narration.declared_line(line, missing, whole=whole) == want


# --- the prompt taught it ---------------------------------------------------------------------

def test_no_talking_example_opens_on_the_other_person():
    """All three talking examples opened on the listener — "He does not answer straight
    away", "She lets that sit", "He does not stop planing" — and the 2026-09-25 ask turns
    opened on the listener in 25 of 27. Each now opens with the player's act."""
    talking = 0
    for ex in prompts.EXAMPLES:
        said = ex["player"].lower()
        words = ex["reply"]["narration"]
        if said.startswith(("i ask ", "i tell ", "i knock ")):
            talking += 1
            first = narration._sentences(words)[0]
            assert first.startswith("You "), (ex["player"], first)
        if " ask " in said or " tell " in said:
            # And wherever the asking comes in the line, it is on the page.
            assert " ask " in words or "You tell " in words or "the question" in words,                 ex["player"]
    assert talking == 4


def test_the_briefing_no_longer_says_pick_up_after_it():
    assert "pick up from what just happened" not in prompts.BRIEFING
    assert "what the player just did, as it happens" in prompts.BRIEFING
    assert "what the player does, as it plays out" in prompts.PROSE_AFTER_EXTRA


def test_the_opening_repair_no_longer_says_not_to_begin_with_the_player():
    review = narration.review(
        "You lean in close. The room is warm.", earlier=[
            "You lean back. The rain falls.", "You lean on the bar. It is late."])
    hints = [f.fix_hint for f in review.findings if f.kind == "formulaic-opening"]
    assert hints and all("do not begin it with the player" not in h for h in hints)
    assert all("keep what the player does" in h for h in hints)


# --- the bench --------------------------------------------------------------------------------

def test_the_bench_loads_and_its_labels_are_what_the_doc_says():
    from pathlib import Path

    from tests.deeds import gold

    root = Path(__file__).resolve().parents[1]
    labelled = []
    for source, deeds in gold.GOLD:
        player, text = gold.load(source, root)
        assert player and text, source
        labelled += [lab for _s, lab in deeds if lab is not None]
    assert (len(labelled), labelled.count(False)) == (64, 46)


# --- the player under at the end of the turn stays under (gm/checks/sleep_kept.py) --------

NAP = ("You sway on your feet, and the ground comes up to meet you; sleep takes you where "
       "you stand. When you open your eyes the sky has gone the colour of a bruise. You sit "
       "up, stiff, and rub your face. That was a long nap. What do you do?")


def _sleeper(monkeypatch, answer, *, asleep=True):
    from gm.checks import sleep_kept
    from rules import survival

    monkeypatch.setattr(deed_reader, "ENABLED", True)
    s = Scene()
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    if asleep:
        pc.add_condition("unconscious", source=survival.SLEEP_SOURCE)
    seen = []

    def chat(messages, *a, **k):
        seen.append(messages)
        return _Reply({"sentence": str(answer)})

    monkeypatch.setattr(deed_reader, "read_under",
                        _read_through(deed_reader.read_under, chat))
    ctx = SimpleNamespace(scene=s, text=NAP, reader={"model": "stub", "host": "h"})
    return sleep_kept, ctx, seen


def test_a_player_the_engine_put_to_sleep_does_not_wake_on_the_page(monkeypatch):
    """The survival lane's live run, 2026-10-05: the tell said Sammy "cannot stay awake any
    longer and falls asleep where they stand"; the prose had them waking at twilight —
    "that was a long nap". The waking sentence is found and the beat cut from it."""
    check, ctx, seen = _sleeper(monkeypatch, 2)
    found = check.find(ctx)
    assert [f.kind for f in found] == ["player-up-while-under"]
    assert found[0].sentences == ("When you open your eyes the sky has gone the colour of "
                                  "a bruise.",)
    assert "ASLEEP" in seen[0][0]["content"]
    out, notes = check.backstop(ctx, NAP, found)
    assert out.startswith("You sway on your feet") and "long nap" not in out
    assert out.endswith(check.POOL["asleep"][0]) and notes
    assert check.authored_in(out) == [check.POOL["asleep"][0]]


def test_a_player_who_is_up_is_never_read(monkeypatch):
    check, ctx, seen = _sleeper(monkeypatch, 2, asleep=False)
    assert check.find(ctx) == [] and seen == []


def test_nothing_named_nothing_cut(monkeypatch):
    check, ctx, _ = _sleeper(monkeypatch, 0)
    assert check.find(ctx) == []
