"""Round 2 of the narration fixes, the pipeline and reader side (2026-11-05).

docs/narration-diagnosis.md, "Round 2: the pipeline and the reader", records the bench.
One test per defect, the measurement in the docstring:

  1. the trial denial refused as a declaration (the reader's bare claim, `means.said_aloud`);
  2. `_repair_sentences` on planned beats: the checks that stand aside, the ones that are
     backstopped without a rewrite, and no act slot left untold (`keep_act_slots`);
  3. the tells check's fallback: no fragment left, the engine's line whole;
  4. the intimate invitation's say carried only "up to my room" (`interpret.words_said`);
  5. a made Perception check rewritten into murk (`light_shown._searching`).
"""
from __future__ import annotations

from types import SimpleNamespace

from gm import agent, beat_verify, checks, interpret, judgement, means, narration, planned
from gm.checks import (beat_verified, light_shown, power_unbacked, road_claimed,
                       route_walked, stop_shown)
from gm.narration import Finding


# --- 1. the denial said aloud ----------------------------------------------------------------

def _frame(actions=(), claims=()):
    return {"question": False, "actions": list(actions), "claims": list(claims)}


def test_a_denial_said_aloud_becomes_talk_and_is_not_refused():
    """On the rerun of the 44 lines (2026-11-05) "I swear I never touched her", at the trial,
    was refused before the turn on 7 of 7 runs — "saying so does not make it so" — where
    the baseline narrated it 7 of 7. The reader wrote a bare claim, and the claim alone put
    to `claim_kind` came back "declared true". Asked with the whole line, a fourth answer
    (said aloud) turns the frame into the talk it is, and the gate refuses nothing."""
    line = "I swear I never touched her"
    fr = _frame(claims=["I never touched her"])
    asked = {}

    def ask(claim, sentence=""):
        asked["claim"], asked["sentence"] = claim, sentence
        return means.SAYS

    means.said_aloud(fr, line, ask=ask)
    assert asked == {"claim": "I never touched her", "sentence": line}
    assert fr["claims"] == [] and fr["claim_kind"] == means.SAYS
    (a,) = fr["actions"]
    assert a["act"] == "talk" and a["says"] == "I never touched her" and interpret.acting(a)
    assert interpret.words_said(fr, line) == "I never touched her"
    # The gate, given the kind already asked, has nothing to refuse.
    assert means.overreach(fr, SimpleNamespace(pc=lambda: object()),
                           claim_ask=lambda c: fr["claim_kind"]) == []


def test_a_declaration_is_still_refused_and_nothing_is_asked_without_a_reader():
    """The same door still refuses what it was built for ("I know exactly where the bandit
    camp is", 6 of 6 probes refused before and after), and with no reader (the suite)
    the frame is left exactly as it came."""
    fr = _frame(claims=["I know exactly where the bandit camp is"])
    means.said_aloud(fr, "I know exactly where the bandit camp is",
                     ask=lambda c, sentence="": means.DECLARES)
    assert fr["claims"] and not fr["actions"] and fr["claim_kind"] == means.DECLARES
    untouched = _frame(claims=["I never touched her"])
    means.said_aloud(untouched, "I swear I never touched her", ask=None)
    assert untouched == _frame(claims=["I never touched her"])
    # A frame with a deed in it is never asked: the claim rides beside an attempt.
    ask_calls = []
    with_deed = _frame(actions=[{"span": "kick in the door", "act": "break_in"}],
                       claims=["the guards cower"])
    means.said_aloud(with_deed, "x", ask=lambda c, sentence="": ask_calls.append(c))
    assert ask_calls == []


def test_claim_kind_is_asked_about_the_whole_line():
    """The claim alone ("I never touched her") loses the "I swear" that makes it speech, and
    the line alone loses what is claimed: "I decide that the smith owes me fifty gold" came
    back "a plan" on 6 of 6 probes asked by its line. Both are shown; the enum carries the
    fourth answer, and a failed call still refuses (the safe direction)."""
    seen = {}

    def chat(messages, model, host, **kw):
        seen["asked"] = messages[-1]["content"]
        seen["enum"] = kw["schema"]["properties"]["kind"]["enum"]
        raise RuntimeError("down")

    got = means.claim_kind("I never touched her", sentence="I swear I never touched her",
                           chat=chat, model="m", host="h")
    assert got == means.DECLARES
    assert seen["asked"].splitlines() == ["The line: I swear I never touched her",
                                          "What it states: I never touched her"]
    assert means.SAYS in seen["enum"]


def test_an_oath_and_a_protest_are_demonstrated_as_talk():
    """The reader is SHOWN that an oath and a protest are talk with their words in `says`
    (demonstration over instruction, CLAUDE.md): before, "I insist …", "I deny everything"
    and "I swear on my mother's grave …" came back the `claim` act on 18 of 18 probes. The
    demonstrations are not probe lines and not labelled lines."""
    from tests.interpreter.gold import GOLD

    gold = {g["text"] if isinstance(g, dict) else g[0] for g in GOLD}
    spoken = [(said, fr) for said, fr in interpret._DEMOS
              if said.startswith(("I swear by", "I protest"))]
    assert len(spoken) == 2
    for said, fr in spoken:
        assert said not in gold and fr["claims"] == []
        (a,) = fr["actions"]
        assert a["act"] == "talk" and a["says"] and a["says"] in said


# --- 4. the whole of what is said ------------------------------------------------------------

_INVITE = "I invite the innkeeper up to my room to share my bed tonight"


def _invite_frame():
    return _frame(actions=[
        {"span": "invite the innkeeper up to my room", "commit": "done", "act": "talk",
         "target": "the innkeeper", "says": "up to my room"},
        {"span": "to share my bed tonight", "commit": "intended", "act": "talk",
         "target": None, "says": "share my bed tonight"}])


def test_the_words_said_run_on_through_the_speech_that_follows():
    """The rerun's intimate invitation: the reader split it into a talk saying "up to my
    room" and an intended talk "to share my bed tonight", and only "up to my room" reached
    the say on 7 of 7 runs — the slot told it as asking for a room ("You turn to the gnome
    and ask for a room for the night"), and the deed backstop told the invitation again.
    Two speech acts spoken in one breath are one line said; two joined by "and" are not."""
    # And reported speech is said from its own verb: carried as "up to my room to share my
    # bed tonight", the say slot wrote "you request a room to share your bed" on 5 of 5
    # live runs. A quotation is the quotation, as typed.
    assert interpret.words_said(_invite_frame(), _INVITE) == \
        "invite the innkeeper up to my room to share my bed tonight"
    two = _frame(actions=[
        {"span": "tell the guard hello", "commit": "done", "act": "talk",
         "target": "the guard", "says": "hello"},
        {"span": "ask where the inn is", "commit": "done", "act": "talk",
         "target": "the guard", "says": "where the inn is"}])
    assert interpret.words_said(two, "I tell the guard hello and ask where the inn is") == \
        "tell the guard hello"
    quoted = _frame(actions=[{"span": 'tell the sergeant, "We march at dawn."',
                              "commit": "done", "act": "talk", "target": "the sergeant",
                              "says": "We march at dawn."}])
    assert interpret.words_said(quoted, 'I tell the sergeant, "We march at dawn."') == \
        "We march at dawn."
    assert interpret.words_said(_frame(), "I wait") == ""


def test_a_say_carrying_part_of_the_line_carries_all_of_it_closed_as_a_sentence():
    """The planner's say copied "up to my room" off the reading; the whole line said is the
    say, told once. And reported words are closed as a sentence: the engine's tell ran them
    into its next one ("…to the effect that forge me a longsword You are in conversation
    with the smith", commission run 2), and the tells check's fallback put that run-on on
    the page as the engine's own line."""
    notes: list = []
    out = judgement.own_words_only(
        [{"op": "say", "actor": "pc", "params": {"to": "c17", "words": "up to my room"}}],
        _INVITE, _invite_frame(), notes=notes)
    assert out[0]["params"]["words"] == \
        "invite the innkeeper up to my room to share my bed tonight."
    assert notes and "carried part of the line" in notes[0]
    quoted = judgement.own_words_only(
        [{"op": "say", "actor": "pc", "params": {"words": "Good morning to you",
                                                 "quoted": True}}],
        'I tell him "Good morning to you"', None)
    assert quoted[0]["params"]["words"] == "Good morning to you"


# --- 3. the tells check's fallback -----------------------------------------------------------

def test_a_name_initial_does_not_end_a_sentence_that_goes_on():
    """Gallows runs 1 and 4: the tells check split "…your promise to accompany Mira H. to
    his execution." at the initial, cut the first half and the page opened on "to his
    execution."; the example-cast pass rejoined "Mira H.'" and "s neck" as "you' s neck".
    A capital after the stop still ends the sentence."""
    s = ("You walk with the guards, as you promised to accompany Mira H. to his execution. "
         "A noose cinches tight around Mira H.'s neck.")
    assert narration._sentences(s) == [
        "You walk with the guards, as you promised to accompany Mira H. to his execution.",
        "A noose cinches tight around Mira H.'s neck."]
    assert narration._sentences("The blow hits Mira H. Then he falls.") == [
        "The blow hits Mira H.", "Then he falls."]
    assert "H.'s neck" in narration.strip_example_cast(
        "A noose cinches tight around Mira H.'s neck.", "I walk")


def test_a_cut_leaves_no_fragment_and_the_engine_line_is_whole_second_person():
    """What a cut leaves must be whole sentences; nothing whole left is nothing left, and
    the engine's own line stands in — whole, and "you" once the groom's second-person step
    runs over it (gallows: "to his execution." stood as the whole act slot)."""
    assert planned.cut_slot_sentence("You walk on. to his execution.", "You walk on.") == ""
    assert planned.cut_slot_sentence("You walk on. The crowd waits.", "You walk on.") == \
        "The crowd waits."
    line = planned.engine_line(["Mira H. goes along with the escort toward the market, "
                                "held."])
    assert narration._sentences(line) == [line]
    assert narration.pc_to_second_person(line, "Mira H.")[0] == \
        "You go along with the escort toward the market, held."
    # No bookkeeping on the page: the replay put "You gain 100 XP for the intimidate
    # check." there when the engine's line stood in (crude, run 7).
    assert planned.engine_line([
        "Tam makes the intimidate check, only just. You gain 100 XP for the intimidate "
        "check (DC 12) (6,000 of 9,000 for level 4). The guild clerk is unmoved."]) == \
        "Tam makes the intimidate check, only just. The guild clerk is unmoved."


# --- 2. the narrator checks on a planned beat ------------------------------------------------

def test_the_checks_a_planned_beat_does_not_need_stand_aside():
    """On the rerun every planned finding of these kinds was the check misreading a slot the
    tells check had already held to its tells: the stop shown and pasted again (3 of 3), the
    player asking about a road read as being on it (4 of 4, 2 cutting the ask), the finished
    belt cut as an unmade item (2 of 2, 4 scored omissions)."""
    assert stop_shown.PLANNED_OFF == {"stop-not-shown"}
    assert route_walked.PLANNED_OFF == {"route-not-walked"}
    assert road_claimed.PLANNED_OFF == {"road-claimed"}
    assert beat_verified.PLANNED_OFF == {"beat-makes-item"}
    # The gloom is still rewritten (kept: measured); a light MISS is not (round 3).
    assert light_shown.PLANNED_NO_REWRITE == {"light-miss-unshown"}
    assert power_unbacked.PLANNED_NO_REWRITE == {"power-unbacked"}
    planned_ctx = SimpleNamespace(planned=True)
    assert checks.planned_off(stop_shown, planned_ctx) == {"stop-not-shown"}
    assert checks.planned_off(stop_shown, SimpleNamespace(planned=False)) == frozenset()


def test_run_drops_a_planned_off_kind_only_on_a_planned_beat(monkeypatch):
    member = SimpleNamespace(
        __name__="gm.checks.fake", ORDER=1, KINDS=frozenset({"a", "b"}),
        DOORS=frozenset({"turn"}), PLANNED_OFF=frozenset({"a"}),
        find=lambda ctx: [Finding("a", "x", "y", sentences=("s1",)),
                          Finding("b", "x", "y", sentences=("s2",))])
    monkeypatch.setattr(checks, "registered", lambda: (member,))
    kinds = lambda planned: [f.kind for f in checks.run(  # noqa: E731
        SimpleNamespace(door="turn", planned=planned))]
    assert kinds(True) == ["b"]
    assert kinds(False) == ["a", "b"]


def test_no_repair_leaves_an_act_slot_untold():
    """Theft run 1: the arrest slot's only sentence ("The captain and two guards
    approach you …") was cut by the presence backstop — the arrest never told, for both
    scorers. A slot that had a sentence on the page and has none after the repairs gets its
    tells' engine line where its sentences stood, before the next slot's."""
    slots = ({"key": "fact1", "wrote": "You pocket the bracelet.",
              "tells": ["Mira H. takes the silver bracelet from the stallholder."]},
             {"key": "fact2", "wrote": "Two guards approach you, demanding you come.",
              "tells": ["The guardsman and the second guardsman come for Mira H."]},
             {"key": "fact3", "wrote": "The crowd falls silent.",
              "tells": ["The market goes quiet."]})
    before = ("You pocket the bracelet. Two guards approach you, demanding you come. "
              "The crowd falls silent. What do you do?")
    after = "You pocket the bracelet. The crowd falls silent. What do you do?"
    text, notes = agent.keep_act_slots(before, after, slots)
    assert text == ("You pocket the bracelet. The guardsman and the second guardsman come "
                    "for Mira H. The crowd falls silent. What do you do?")
    assert notes and '"fact2"' in notes[0]
    # A slot rewritten in place, or never on the page, is left alone.
    assert agent.keep_act_slots(before, before, slots) == (before, [])


def test_a_planned_beats_invented_power_is_cut_without_the_refusal_line(monkeypatch):
    """The rerun shipped "Whatever you reach for does not answer; the moment stays exactly
    as it was" on 3 planned pages (2 scored errors, 3 Q pages): the line refuses a reach the
    player made, and on a planned beat the player made none — a declared power out of reach
    is refused before the turn — so the power is the slot's, and it is only cut."""
    bad = "You unleash a surge of blood magic."
    text = f"You square up to the guard. {bad} What do you do?"
    monkeypatch.setattr(power_unbacked, "_found", lambda ctx, t: bad)
    ctx = SimpleNamespace(planned=True, scene=SimpleNamespace(said={}))
    out, notes = power_unbacked.backstop(ctx, text, [])
    assert out == "You square up to the guard. What do you do?"
    assert not power_unbacked.authored_in(out)
    free, _ = power_unbacked.backstop(SimpleNamespace(planned=False,
                                                      scene=SimpleNamespace(said={})),
                                      text, [])
    assert power_unbacked.authored_in(free)


def test_a_masterwork_weapon_is_the_same_weapon():
    """Second punch, 7 of 7 runs: the captain's stat block prints "guisarme", the engine
    swung his "mwk guisarme", the reader named the guisarme, and the check replaced the
    enemy slot's blow with the engine's line every time."""
    assert beat_verify._same_weapon("guisarme", ("mwk guisarme",))
    assert beat_verify._same_weapon("longsword", ("+1 longsword",))
    assert not beat_verify._same_weapon("longspear", ("mwk guisarme",))
    assert not beat_verify._same_weapon("", ("mwk guisarme",))


# --- 5. a made Perception check is not murk ---------------------------------------------------

def test_a_made_search_owes_no_gloom():
    """Climb run 7: "makes the perception check by 15" rewritten into "a sea of barely
    discernible, shifting shapes" by the light check's repair, an error for both scorers. A
    search that succeeded found what it looked for; only one that did not owes the gloom."""
    made = SimpleNamespace(op="check", verdict="success",
                           tell="Mira H. makes the perception check by 15.")
    failed = SimpleNamespace(op="check", verdict="failure",
                             tell="Mira H. fails the perception check by 3.")
    assert not light_shown._searching(SimpleNamespace(outcomes=(made,)))
    assert light_shown._searching(SimpleNamespace(outcomes=(failed,)))
