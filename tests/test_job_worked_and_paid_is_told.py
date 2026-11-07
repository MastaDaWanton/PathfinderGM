"""A job worked and paid is told as worked and paid — to the narrator, on its card, and at
the `/gm` door.

The owner's save of 2026-11-05 (Pangrella, the hiring table, planned narration). "Say I can
fight" put `job-1-week` to the player: guard work for Vyrnys, 3 sp a day for 7 days, paid at
the end. "Accept the terms of the work" ran the `job` accept and the `work` op: the clock
moved six days and eight hours and the purse held 2 gp 1 sp. The engine had done all of it.
Then:

  1. The tell the planned narrator's tells check read (turn_log row 12) was "Kesst Vayr
     works as a guard in Pangrella (the wage agreed with Vyrnys: a hireling's day wage). The
     pay is … in all." — `narration.page_line` had lifted "for 7 days" (its damage-amount
     rule: "for" and a number) and "(2 … gold pieces, 1 … silver piece in hand)" (a bracket
     with a digit). The page said "securing your role as a guard for the next seven days",
     as if the week were still to come, and never that the player was paid.
  2. The job card's facts kept only the offer, so the brief, the plan and the clerk read a
     job still to work; asked to pay up, the clerk made up "the record for the northern gate
     is incomplete".
  3. "/gm have I been paid already?" matched no engine topic and the model answered "Not
     quite yet!"; "/gm have i completed the quest" answered "none open", hiding the job.

Each test replays that shape through the real engine on the three worlds.
"""
from __future__ import annotations

from types import SimpleNamespace

from gm import narration, planned
from gm.beat_verify import tell_premises
from play import gm_answers
from play.views import plain_tell
from rules import cards, goods, jobs
from tests.test_real_jobs import _escort, _hiring_table, _job, _week


def _guard_week(worlds):
    """The save's two turns: the escort let go by the clock (Pangrella's own start had none
    going out), "I can fight" offered the week's guard work, and the work accepted."""
    s, e, clerk = _hiring_table(worlds)
    esc = _escort(s)
    s.clock_minutes = esc.job["meets"]["minute"] + jobs.GRACE_MINUTES + 1
    jobs.settle(e)
    _job(e, clerk, "offer", work="fight")
    week = _week(s)
    before = goods.in_copper(s.pc().purse)
    res = _job(e, clerk, "accept")
    paid = goods.in_copper(s.pc().purse) - before
    return s, e, clerk, week, res, paid


def test_the_week_and_the_payment_survive_the_narrators_number_stripping(worlds):
    """The save's row 12: after `page_line` the tell had no week and no payment in it.
    Every strip a tell passes through on its way to a narrator — the tells check's premise
    (`beat_verify.tell_premises`), the engine-line fallback (`planned.engine_line`), the
    page's own (`views.plain_tell`) and the turn's rolled-number guard — keeps both: the
    days said in words, and the employer paying at the end of the week, with the sum."""
    s, e, clerk, week, res, paid = _guard_week(worlds)
    out = res.outcomes[0]
    assert out.op == "work" and out.status != "refused"
    assert paid == jobs.total_cp(cards.find(s, week.id)) and paid > 0
    week_sum = jobs.coin_words(e, paid)
    stripped = {
        "premise": " ".join(tell_premises([out.tell])),
        "engine line": planned.engine_line([out.tell]),
        "page": plain_tell(out.tell, s),
        "rolled numbers": narration.strip_turn_numbers(out.tell, res.outcomes)[0],
    }
    for how, text in stripped.items():
        assert "seven days" in text and "week is over" in text, (how, text)
        assert f"{clerk.name} pays" in text and week_sum in text, (how, text)
        assert "in hand" in text, (how, text)
    # Not a digit count of days anywhere the narrator could read as a plan to come.
    assert "for 7 days" not in out.tell


def test_the_planned_narrators_slot_is_handed_the_week_as_done(worlds):
    """The slot that wrote "for the next seven days" is the act slot of the work; it is
    handed the tell whole (`planned.build_plan`), and now that tell says the week is over
    and what was paid."""
    s, e, clerk, week, res, paid = _guard_week(worlds)
    slots = planned.build_plan(e, "Accept the terms of the work.", res.outcomes,
                               last_beat="Vyrnys names the pay.")
    fact = next(x for x in slots if x["key"].startswith("fact")
                and any("works the whole week" in t for t in x["tells"]))
    assert "week is over" in fact["say"] and jobs.coin_words(e, paid) in fact["say"]
    assert "seven days" in fact["say"]


def test_a_job_worked_and_paid_says_so_on_its_card_and_in_the_brief(worlds):
    """The save's card kept the offer as its only fact ("… all of it paid at the end of the
    week") and was resolved with `resolved_turn` 0, so it left the brief at once. Now the
    card's newest fact is what came of it, the record holds the sum, and the brief keeps it
    — labelled finished — while the employer stands with the player, turns after the
    ordinary three-turn linger has passed."""
    s, e, clerk, week, res, paid = _guard_week(worlds)
    card = cards.find(s, week.id)
    assert card.stage == "resolved" and card.job["state"] == "paid"
    assert card.job["paid_cp"] == paid and card.job["days_worked"] == 7
    last = card.facts[-1]
    assert "worked the whole week" in last and "was paid" in last
    assert jobs.coin_words(e, paid) in last and clerk.name in last
    # The view stamps the turn the batch ran on (the engine does not know it).
    cards.touch_from_outcomes(s, res.outcomes, turn=4)
    assert cards.find(s, week.id).resolved_turn == 4
    brief = cards.brief(s, [], turn=4 + cards.LINGER_TURNS + 6)
    assert clerk.ref in s.actors
    assert f"JOB, FINISHED: {card.title}" in brief and last in brief, brief
    # The employer's reply slot answers from it: who hired the player knows it was paid.
    assert last in jobs.slot_facts(e, clerk.ref)
    # A day of the world's clock later, it is let go like any other finished matter.
    s.clock_minutes += cards.SETTLED_JOB_MINUTES + 1
    assert card.title not in cards.brief(s, [], turn=4 + cards.LINGER_TURNS + 6)


def _read_back_facts(s, clerk, res):
    """The read-back's engine side for the work turn, as `beat_verify.facts_from` builds it
    in the game: the player and the clerk here, this turn's outcomes as records."""
    from gm import beat_verify as bv

    pc = s.pc()
    here = "the hiring table"
    return bv.Facts(start=here, end=here, places=(here,),
                    people=(bv.Person(pc.ref, pc.name, pc=True),
                            bv.Person(clerk.ref, clerk.name)),
                    outcomes=tuple(o.as_dict() for o in res.outcomes), pc_ref=pc.ref)


def test_taking_the_week_on_is_never_read_as_a_thing_handed_over(worlds):
    """Rows 11-15 of the save: the tell opened "Kesst Vayr takes the week's work from
    Vyrnys", the slot copied it, and the read-back claimed a thing ("something else")
    handed from Vyrnys to the player. `beat_verify._anything_into` did not count the
    week's wage as coin into the player's hands — the `earned` effect has no `purse` — so
    the claim was judged a gift the engine never made (beat-hands-over), and the repair
    wrote "Vyrnys takes the week's work from you" onto the page.

    Now the tell says the work is agreed to, with no "takes … from" in it; and the save's
    own claims, read off the planned beat, raise no beat-hands-over beside a turn that paid
    the player."""
    from gm import beat_verify as bv

    s, e, clerk, week, res, paid = _guard_week(worlds)
    tell = res.outcomes[0].tell
    assert tell.startswith(f"{s.pc().name} agrees to work the week for {clerk.name}.")
    assert " takes " not in tell and f"from {clerk.name}" not in tell
    facts = _read_back_facts(s, clerk, res)
    beat = (f"You agree to work the week for {clerk.name}, and when the week is over "
            f"{clerk.name} pays you the week's wage.")
    claims = [bv.Claim("hands", {"item": bv.OTHER_THING, "from": clerk.ref,
                                 "to": s.pc().ref}, quote=q, sentence=beat, valid=True)
              for q in (f"agree to work the week for {clerk.name}",
                        f"take the week's work from {clerk.name}",
                        f"{clerk.name} pays you the week's wage")]
    assert [d for d in bv.diff(claims, facts, beat) if d.category == "hands"] == []
    # Still judged on a turn that put nothing in the player's hands: the carter's made-up
    # coin of 2026-10-16 (the reason the check exists) is a gift the engine never made.
    unpaid = bv.Facts(**{**facts.__dict__, "outcomes": tuple(
        {**o, "effects": [dict(x, paid_cp=0) if x.get("kind") == "earned" else x
                          for x in o.get("effects") or []]} for o in facts.outcomes)})
    assert [d.category for d in bv.diff(claims[:1], unpaid, beat)] == ["hands"]


def _campaign(s):
    return SimpleNamespace(scene=s, transcript=[], suggestions=[], turn_log=[], world=None)


def test_gm_have_i_been_paid_is_answered_by_the_engine_with_the_sum(worlds):
    """"/gm have I been paid already?" went to the model and came back "Not quite yet!".
    It is the engine's to answer: the job card says worked and paid, with the sum, and the
    purse says what is in it."""
    s, e, clerk, week, res, paid = _guard_week(worlds)
    for asked in ("have I been paid already?", "did I get paid", "what am I owed",
                  "my wages", "is the job done"):
        assert "pay" in gm_answers.topics_for(asked), asked
        kind, text = gm_answers.answer(_campaign(s), e, asked)
        assert kind == "engine", asked
        assert f"{week.title} — worked and paid {jobs.coin_words(e, paid)}" in \
            gm_answers.answer(_campaign(s), e, asked)[1], text
        assert "purse: " + goods.purse_line(s.pc().purse, goods.coins_here(e.world, s)) \
            in text
    # Phrases, never the bare word: a paid guard and paying attention are not about wages.
    for not_asked in ("who is the paid guard", "should I pay attention to the clerk"):
        assert "pay" not in gm_answers.topics_for(not_asked), not_asked


def test_gm_have_i_completed_the_quest_lists_the_finished_job(worlds):
    """"/gm have i completed the quest" answered "The record shows no open quests!" for a
    job worked and paid: the quests section listed open ones only."""
    s, e, clerk, week, res, paid = _guard_week(worlds)
    kind, text = gm_answers.answer(_campaign(s), e,
                                   "have I been paid already? and have i completed the quest")
    assert kind == "engine"
    assert "QUESTS: none open." in text
    assert (f"finished: {week.title} — worked and paid {jobs.coin_words(e, paid)}"
            in text), text


def test_before_the_week_is_worked_the_pay_door_says_nothing_is_paid_yet(worlds):
    """The other side: a job only offered is said to be offered, and nothing is claimed
    paid that the engine has not paid."""
    s, e, clerk = _hiring_table(worlds)
    esc = _escort(s)
    s.clock_minutes = esc.job["meets"]["minute"] + jobs.GRACE_MINUTES + 1
    jobs.settle(e)
    _job(e, clerk, "offer", work="fight")
    kind, text = gm_answers.answer(_campaign(s), e, "have I been paid?")
    assert kind == "engine"
    assert f"{_week(s).title} — offered, not taken up" in text
    assert "worked and paid" not in text
