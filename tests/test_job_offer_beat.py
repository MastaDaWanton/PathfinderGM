"""The job offer's first beat (the 0.2.22 release check, 2026-10-27).

The line "I walk up to the guild clerk and tell them I can fight." on a fresh hiring-table
campaign (Pangrella, gemma-4-12B, Planned). The job tell offered the caravan (6 Eldrida gold)
or the guard week (2 gold 1 silver), and the shipped beat was:

  "You step forward … declare to the guild clerk that you can fight. The clerk lists two
  options: a caravan to Kalixiri leaving at noon for a handful of gold pieces, or a week of
  local guard duty for a few coins. You state your proficiency in combat to the clerk, who
  listens as you confirm your ability to fight while they await your decision. 'Then
  choose: the caravan to Kalixiri leaves at noon for six gold, or stay here for a week of
  local guard duty paid at two gold and one silver,'. What do you do?"

Four faults, each pinned here:
  1. the job read-back called the clerk's TRUE reply made-up work, twice;
  2. its cut took the speaker and left "…silver,'." with nobody saying it;
  3. the money row rewrote the engine's own sums into "a handful" and "a few coins";
  4. "you can fight" was told three ways — the step's slot, the say's slot, the reply.
"""
from __future__ import annotations

import json

from gm import beat_verify, narration, planned
from rules import intents
from rules.engine import Outcome

from tests.test_real_jobs import _hiring_table, _job

SAY = {"speaker": "c3", "speaker_name": "the guild clerk"}
ONE = ("Then choose: the caravan to Kalixiri leaves at noon for six gold, or stay here for "
       "a week of local guard duty paid at two gold and one silver.")
TELL = ("The guild clerk puts work to Kesst Vayr: the caravan master takes wagons to Kalixiri "
        "… at 1 Eldrida gold piece a day for 6 days, 6 Eldrida gold pieces in all, paid at "
        "the end by the caravan master. Or, in town: A week of guard work in town … 3 "
        "Eldrida silver pieces a day for 7 days, which is 2 Eldrida gold pieces, 1 Eldrida "
        "silver piece for the whole week, all of it paid at the end of the week.")


# --- 2. a cut leaves whole sentences -------------------------------------------------------------

def test_a_cut_reply_never_loses_its_speaker_or_its_quote_marks():
    """Measured: the clerk's one-sentence reply flagged whole was cut on a blanked copy whose
    speech is spaces; the span started after the quotation, so the cut took "the guild clerk
    says curtly." and left "'Then choose: … silver,'." A reply is now cut inside its quoted
    words and composed again (`planned.cut_slot_sentence`); one with nothing left is "";
    the page cutter's span starts at the text's first word, not the blanked copy's."""
    text = planned.compose_reply(SAY, ONE, "curtly")
    assert planned.cut_slot_sentence(text, narration._sentences(text)[0]) == ""
    bare = f"'{ONE[:-1]},' the guild clerk says curtly."
    assert narration._cut_sentences(bare, [bare]) == ""
    three = planned.compose_reply(SAY, "Good. The caravan leaves at noon. You will ride the "
                                        "salt barge to the old fort.", "curtly")
    for s in narration._sentences(three):
        cut = planned.cut_slot_sentence(three, s)
        assert cut.startswith("<say who=c3 to=you>'") and cut.endswith(
            "'</say> the guild clerk says curtly."), cut
        assert len(narration._sentences(cut)) == 2


# --- 1. the read-back of a true reply --------------------------------------------------------------

def test_the_job_read_back_asks_which_held_job_each_sentence_speaks_of():
    """Measured on the release check's save (gemma-4-12B, 2 runs): asked for "the sentence
    that puts work that is NOT that work" with both held jobs in one paragraph, the read-back
    flagged 10 of 24 true replies — every one about the SECOND job ("Or a week of guard work
    here in town, three silver a day") — and missed 0 of 24 invented ones. Asked of each
    sentence WHICH numbered job it speaks of, with "other work" the flag: 0 of 24 false
    alarms, 2 of 24 missed (one line, "Sign the papers at the counting house tomorrow",
    both runs). The jobs reach it one a line (`jobs.slot_facts`)."""
    seen: list[str] = []

    def chat(answer):
        def _chat(messages, model, host, **kw):
            from gm.client import Reply

            seen.append(messages[-1]["content"])
            assert kw["schema"]["properties"]["work"]["enum"][:2] == ["1", "2"]
            return Reply(json.dumps({"work": answer}), 0.1, model)
        return _chat

    held = "the caravan … 6 Eldrida gold pieces in all.\nA week of guard work in town …"
    text = planned.compose_reply(SAY, ONE, "curtly")
    assert beat_verify.invented_job_sentence(text, "the guild clerk", held=held,
                                             chat=chat("several of them"), model="m") == ""
    assert "1. the caravan" in seen[-1] and "\n2. A week of guard work" in seen[-1]
    got = beat_verify.invented_job_sentence(text, "the guild clerk", held=held,
                                            chat=chat("other work"), model="m")
    assert got and "Then choose" in got


def test_the_held_jobs_reach_the_read_back_one_a_line(worlds):
    """The reply slot's `holds` (what the read-back is asked against) carries each job the
    clerk holds on its own line — the measured fault was the two run together."""
    s, e, clerk = _hiring_table(worlds)
    _job(e, clerk, "offer", work="fight")
    talk = [Outcome("i1", "say", tell=f"You speak to {clerk.name}.",
                    effects=[{"kind": "said", "who": "", "to": clerk.ref}])]
    reply = next(x for x in planned.build_plan(e, "What pays?", talk, last_beat="x")
                 if x["key"] == "reply")
    assert len(reply["holds"].splitlines()) == 2


# --- 3. the engine's own sums ---------------------------------------------------------------------

def test_a_sum_the_tells_state_stays_on_the_page_and_an_invented_one_does_not():
    """Measured: "a caravan to Kalixiri … for 6 gold pieces, or a week … for 2 gold and 1
    silver" was rewritten "for a handful of gold pieces, or … for a few coins" by the money
    row, though the turn's own tell stated both sums. A sum the tells state is an engine
    fact (`intents.sums_told`, compared as number and metal); 60 gold is still a claim. The
    backstop cut is asked with the same backing: without it the cut undid the repair."""
    told = Outcome("i2", "job", tell=TELL)
    backed = intents.claims_the_engine_backs([told])
    page = ("The clerk lists two options: a caravan to Kalixiri leaving at noon for 6 gold "
            "pieces, or a week of local guard duty for 2 gold and 1 silver.")
    assert intents.find_outcome_claims(page, backed=backed) == []
    assert [c.why for c in intents.find_outcome_claims(page.replace("6 gold", "60 gold"),
                                                       backed=backed)] == [
        "states a sum of money"]
    assert intents.cut_outcome_claims(page, backed=backed) == (page, [])


def test_a_told_sum_is_never_stripped_as_a_roll_that_showed_the_same_number():
    """`narration.strip_turn_numbers` lifts a number the turn rolled ("for 6" after a die
    showed 6) and leaves prices: it now reads the same told sums, so "for 6 gold pieces" on
    a turn whose haggle die showed a 6 stays — the two guards cannot disagree about a sum."""
    told = Outcome("i2", "job", tell=TELL, rolls=[{"total": 2, "natural": 6, "faces": [6]}])
    page = "The caravan pays for 6 gold pieces, and the week for 2 gold."
    assert narration.strip_turn_numbers(page, [told]) == (page, [])
    rolled = Outcome("i3", "attack", tell="hits for 6 piercing",
                     rolls=[{"total": 14, "natural": 6, "faces": [6]}])
    assert narration.strip_turn_numbers("Your blade hits for 6 piercing.", [rolled])[1]


def test_a_size_word_in_a_characters_mouth_is_never_flagged_as_narration():
    """Measured on the job-offer re-run: the clerk said "'If you prefer the city, I can offer
    you a week … Otherwise, …,' the guild clerk says flatly." The size-words finder read the
    first sentence of the quotation alone — a quote mark it never closes — took "city" for
    narration, the repair dropped the opening quote, and the narrator-in-the-scene check
    turned "I can offer" into "you can offer you". Speech is blanked over the whole text."""
    from types import SimpleNamespace

    from gm.checks import size_words

    # As the truth checks read it: the say tags are lifted before them.
    text = ("'If you prefer the city, I can offer you a week of guard duty. Otherwise, the "
            "caravan leaves at noon,' the guild clerk says flatly.")
    town = SimpleNamespace(id="t1", name="Kalimnar")
    ctx = SimpleNamespace(text=text)
    orig = size_words._small_settlement, size_words._other_places
    size_words._small_settlement = lambda c: (town, "town")
    size_words._other_places = lambda c, loc: []
    try:
        assert size_words.find(ctx) == []
        ctx.text = "You walk into the city. " + text
        assert size_words.find(ctx)[0].sentences == ("You walk into the city.",)
    finally:
        size_words._small_settlement, size_words._other_places = orig


def test_a_sentence_opening_a_quotation_is_repaired_with_its_speaker():
    """The same re-run: the truth-check repair took the speech unit only for a sentence that
    began AFTER the quote mark (`qa < at`), so the quotation's opening sentence — which
    starts ON the mark — was rewritten alone and lost it. Pinned in the source: `<=`."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "gm" / "agent.py").read_text(encoding="utf-8")
    assert "if qa <= at and at + len(sentence) <= qb" in src


def test_a_sentence_an_earlier_slot_wrote_is_never_written_twice(monkeypatch):
    """Measured on the re-run: the step's slot and the say's slot both wrote "You step
    forward, closing the distance until you stand directly before the trestle table." The
    second copy goes; a slot with nothing else in it goes whole."""
    from tests.test_planned_narration import LAST_BEAT, _fake as plan_fake, _scene

    s, engine = _scene()
    step = "You step forward, closing the distance until you stand before the table."
    calls: list = []
    monkeypatch.setattr(planned.client, "chat", plan_fake(calls, slot_text={
        "fact1": step, "fact2": step + " You tell the smith you can fight."}))
    smith = next(a for a in s.actors.values() if not a.is_pc)
    outcomes = [Outcome("i1", "move", tell="Kesst Vayr moves to near (10 ft)."),
                Outcome("i2", "say", tell=f"Kesst Vayr speaks to {smith.name}, to the effect "
                                          f"that I can fight",
                        effects=[{"kind": "said", "who": "pc", "to": smith.ref}])]
    out = planned.write(engine, brief="BRIEF", player_input="I walk up and say I can fight.",
                        outcomes=outcomes, who=("stub-12b", "http://x", "ollama", ""),
                        last_beat=LAST_BEAT)
    assert out.text.count("You step forward") == 1
    assert "You tell the smith you can fight." in out.text
    assert any("repeated an earlier sentence" in n for n in out.notes)


def test_a_coins_name_never_lands_a_tell_on_the_nation_it_is_named_for():
    """The cause under the next test, measured on the re-run's save: the job tell ("…6
    Eldrida gold pieces in all… work…") hit the Cartographers' Conclave card's keys "work" and
    "eldrida" — the coin's name — and was filed as that world card's newest fact, twice; the
    matter slot, told the card's latest fact, wrote the caravan as the Conclave's matter.
    The coin as the engine writes it is money, not a word about anything."""
    from types import SimpleNamespace

    from rules import cards

    facts = ["Their work has led to trade agreements in Eldrida."]
    title = "A network of mapmakers and cartographers"
    card = cards.Card(id="w1", title=title, facts=facts, tags=(cards.TAG_WORLD,),
                      keys=cards.keys_from(title, *facts))
    scene = SimpleNamespace(cards=[card.as_dict()], actors={}, clock_minutes=0)
    told = Outcome("i2", "job", tell="The guild clerk puts work to you: 1 Eldrida gold piece "
                                     "a day, 6 Eldrida gold pieces in all.")
    assert cards.touch_from_outcomes(scene, [told]) == []
    real = Outcome("i3", "say", tell="Their work for Eldrida's crown is spoken of here.")
    assert cards.touch_from_outcomes(scene, [real]) == ["w1"]


def test_a_matter_slot_that_writes_another_matter_is_asked_again_then_dropped(monkeypatch):
    """Measured twice on the re-run: "I ask the clerk what the caravan job pays" with the
    open matter "A network of mapmakers, cartographers, and travelers …", and the matter
    slot wrote "The clerk's mutterings mention a caravan master departing at noon for
    Kalixiri" and then "The clerk's ledger contains the details of a caravan bound for
    Kalixiri" — the job a third time, the matter not at all. Read back by the matter's own
    identity words (`cards.identity_keys`, as `note_mentions` counts them); asked once more
    with the matter named; dropped when it still is not about it."""
    from tests.test_planned_narration import LAST_BEAT, _fake as plan_fake, _scene

    s, engine = _scene()
    pull = {"id": "w1", "title": "A network of mapmakers and cartographers",
            "fact": "", "standing": "situation", "keys": ["network", "mapmakers",
                                                         "cartographers"]}
    caravan = "The clerk's ledger holds the details of a caravan bound for Kalixiri."
    for second, kept in ((caravan, False),
                         ("Two mapmakers argue over a chart by the well.", True)):
        calls: list = []
        monkeypatch.setattr(planned.client, "chat",
                            plan_fake(calls, slot_text={"matter": [caravan, second]}))
        out = planned.write(engine, brief="BRIEF", player_input="I wait.", outcomes=[],
                            pull=pull, who=("stub-12b", "http://x", "ollama", ""),
                            last_beat=LAST_BEAT)
        assert "caravan bound for Kalixiri" not in out.text
        assert ("mapmakers argue" in out.text) is kept
        assert any("That is not about A network of mapmakers" in str(m.get("content"))
                   for c in calls for m in c["messages"])


# --- 4. one telling of the player's words -----------------------------------------------------------

def test_the_players_words_ride_the_say_and_the_offer_is_said_once_by_its_speaker(worlds):
    """Measured: the step's slot carried the player's line ("…declare to the guild clerk that
    you can fight"), the say's slot told it again ("You state your proficiency in combat"),
    and the job's act slot ("The clerk lists two options") stood beside the clerk's own
    answer listing them. Now the say tells the words the engine heard and the line rides
    no slot (since 2026-11-04: the line's other deeds are other acts' — "I agree to his
    price and pay" on the say slot wrote the refused payment as made), the step is only a
    step, and the offer is folded into the answer of the one who made it."""
    s, e, clerk = _hiring_table(worlds)
    offer = _job(e, clerk, "offer", work="fight").outcomes[0]
    offer.intent_id = "i2"
    outcomes = [Outcome("i1", "move", tell="Kesst Vayr moves to near (10 ft)."), offer,
                Outcome("i3", "say", tell=f"Kesst Vayr speaks to {clerk.name}, to the effect "
                                          f"that I can fight",
                        effects=[{"kind": "said", "who": "pc", "to": clerk.ref,
                                  "words": "I can fight"}])]
    line = "I walk up to the guild clerk and tell them I can fight."
    slots = planned.build_plan(e, line, outcomes, last_beat="x")
    facts = [x for x in slots if x["key"].startswith("fact")]
    assert not any(line in x["say"] for x in slots), "one telling: the say's own"
    said = [x for x in facts if "speaks to" in x["say"]]
    assert len(said) == 1 and "to the effect that I can fight" in said[0]["say"]
    assert not any("puts work to" in x["say"] for x in facts)
    reply = next(x for x in slots if x["key"] == "reply")
    assert "putting this work to the player now" in reply["say"]
    # The re-run's second line, "I ask the clerk what the caravan job pays": the say slot
    # was told to show "what came of it" and wrote the clerk's answer, which the reply then
    # gave again. It shows the asking only; the answer is the reply's.
    assert "answer is written next, so none of it here" in said[0]["say"]
