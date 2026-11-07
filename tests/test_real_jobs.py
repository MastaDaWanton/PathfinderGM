"""Real jobs: the hiring table's work is held by the engine before anybody speaks of it.

The owner's report of 2026-10-27 (0.2.21, Planned narration): the "hiring table" start said
"Hands wanted for the week, fed and paid at the end of it. Can you carry, count or fight?",
and over five planned replies the clerk made up an escort of supplies to an outpost,
bandits, paperwork tomorrow and a caravan that "moved toward the outskirts". The save's
`scene.agreements` was empty and there was no caravan, no place for one and no card for it;
the player then tracked a caravan that never existed (docs/known-matters.md §1).

The owner's answers of the same day (§4.2), each with a test named after it:

  1. "I can fight" is offered a real escort when one is going out, or a week of guard work;
  2. a caravan is several real people, each with a sheet;
  3. the opening lists real jobs, opened when it is staged;
  4. a job not turned up for lapses, and the employer's regard drops a little;
  5. the pay is the book's hireling wage for the danger, raised by Diplomacy up to 3x;
  6. the owner's existing save is left as it is (nothing here migrates a save);
  7. an unheard errand's step ticks silently: nothing about it reaches the page.

Every staged test runs on the three worlds.
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, planned
from rules import attitude, cards, goods, jobs, openings, schemes, tracking
from rules.dice import Dice
from rules.engine import Engine, Intent, Scene
from rules.sheet import load_pc

MORNING = 8 * 60


def _hiring_table(world, seed=7):
    """A fresh campaign's hiring table, staged as `new_campaign` stages it: the party in a
    town that has a land road out, the start document run through `openings.stage`."""
    doc = openings.get("the-hiring-table")
    for row in world.play.get("settlements") or []:
        s = Scene(location_id=row["id"])
        s.add(load_pc("fixtures/pc-kesst.json"))
        s.clock_minutes = MORNING
        e = Engine(s, Dice(seed=seed), world=world)
        e.place_party()
        if not jobs._land_legs(e) or not any(jobs._road_head(e, leg) for leg in
                                               jobs._land_legs(e)):
            continue
        openings.stage(e, doc, story_seed=seed)
        clerk = s.people[s.start["slots"]["lead"]]
        return s, e, clerk
    pytest.skip("no settlement in this world has a land road out")


def _escort(s):
    return next(c for c in jobs.jobs(s) if c.job.get("work") == "escort")


def _week(s):
    return next(c for c in jobs.jobs(s) if c.job.get("work") != "escort")


def _run(e, raw):
    return e.run(e.validate(raw, origin="author:test"))


def _job(e, clerk, do, **params):
    return _run(e, [{"op": "job", "actor": "pc", "target": clerk.ref,
                     "params": {"do": do, **params}}])


# --- 3. the opening lists real jobs -------------------------------------------------------

def test_the_opening_lists_real_jobs_held_before_the_clerk_speaks(worlds):
    """Answer 3: the hiring table's start opens its work when it is staged — the escort with
    a real road, a real meeting place and hour, and the week's posting — so nothing the
    clerk says of work has to be made up. Before this the save held nothing at all."""
    s, e, clerk = _hiring_table(worlds)
    esc, week = _escort(s), _week(s)
    assert s.start.get("jobs") == [esc.id, week.id]
    assert esc.giver == clerk.ref and week.giver == clerk.ref
    # Heard: the clerk's call reached the player; no particular job is put to them until
    # the clerk answers what they can do (then offered, in the Journal).
    assert cards.standing(esc) == cards.HEARD and not cards.quest_log(s)["active"]
    _job(e, clerk, "offer")
    assert {r["id"] for r in cards.quest_log(s)["active"]} == {esc.id, week.id}
    route, meets = esc.job["route"], esc.job["meets"]
    legs = {leg.to_id for leg in jobs._land_legs(e)}
    assert route["to"] in legs and route["from"] == s.location_id
    assert meets["at"] in {p.id for p in e.places()}
    assert meets["minute"] == 12 * 60, "noon today, the morning being young"
    assert jobs.WORK and esc.job["work"] in jobs.WORK
    # Kept on the card through a save.
    again = cards.Card.from_dict(esc.as_dict())
    assert again.job == esc.job and again.kind == "job"


# --- 2. a caravan is several real people -------------------------------------------------

def test_a_caravan_is_several_real_people_each_with_a_sheet(worlds):
    """Answer 2: "several real people: drivers and guards, each a person with a sheet" —
    never one group actor. Each stands at the meeting place with a stat block, a true
    name, a face and a people."""
    s, e, _clerk = _hiring_table(worlds)
    esc = _escort(s)
    refs = esc.job["counterpart"]["people"]
    assert len(refs) == 4 and esc.job["counterpart"]["master"] == refs[0]
    from rules import names

    pooled = bool(names.pool_for(worlds, s.location_id, None))
    for r in refs:
        a = s.people[r]
        assert a.at == esc.job["meets"]["at"] and a.hp_max > 0
        assert a.appearance, a.name
        # A name from the world's pool where it has one (Pangrella's towns have none).
        assert a.true_name or not pooled, a.name
    names = {s.people[r].name for r in refs}
    assert names == {"the caravan master", "the lead teamster", "the second teamster",
                     "the hired sword"}
    assert not any(r in s.actors for r in refs), "they are at the road head, not the table"


# --- 1. "I can fight": a real escort, or a week's guard work ------------------------------

def test_i_can_fight_is_offered_a_real_escort_or_a_week_of_guard_work(worlds):
    """Answer 1: the clerk offers EITHER a real escort job (when one is going out) or a
    week of guard work (the existing `work` op). With the caravan going out, the offer is
    the escort and the guard week beside it; once it has gone, the guard week alone."""
    s, e, clerk = _hiring_table(worlds)
    res = _job(e, clerk, "offer", work="fight")
    tell = res.outcomes[0].tell
    esc = _escort(s)
    assert esc.job["route"]["to_name"] in tell and esc.job["meets"]["where"] in tell
    assert "noon today" in tell and "Or, in town:" in tell
    assert jobs.last_put(s, clerk.ref).id == esc.id
    assert _week(s).job["work"] == "guard"
    # The caravan gone (past its hour), "fight" is the week's guard work only.
    s.clock_minutes = esc.job["meets"]["minute"] + jobs.GRACE_MINUTES + 1
    jobs.settle(e)
    assert jobs.escort_going_out(s, clerk.ref) is None
    again = _job(e, clerk, "offer", work="fight").outcomes[0].tell
    assert "guard" in again and esc.job["route"]["to_name"] not in again


def test_carry_and_count_are_the_weeks_work_at_the_books_flat_wages(worlds):
    """Carrying is the CRB's untrained hireling (1 sp a day), counting a trained one's
    (3 sp): the clerk's other two words, priced by the engine."""
    s, e, clerk = _hiring_table(worlds)
    _job(e, clerk, "offer", work="carry")
    assert jobs.pay_of(_week(s))["per_day_cp"] == jobs.UNTRAINED_CP
    _job(e, clerk, "offer", work="count")
    assert jobs.pay_of(_week(s))["per_day_cp"] == jobs.TRAINED_CP


# --- 5. the pay -----------------------------------------------------------------------------

def test_the_pay_is_the_books_hireling_wage_for_the_works_danger():
    """Answer 5: CRB trained 3 sp/day; Cohorts & Companions' risk wages (harmless 3 sp,
    questionable 6 sp, hazardous 1 gp) times the hireling's level squared, for guarding
    and escorting only. A road is questionable for its beasts; hard country more."""
    assert jobs.per_day_cp("guard", 1, jobs.risk_of("guard")) == 30
    assert jobs.risk_of("escort", ("grassland",)) == "questionable"
    assert jobs.risk_of("escort", ("forest",)) == "hazardous"
    assert jobs.risk_of("escort", ("mountain",)) == "deadly"
    assert jobs.per_day_cp("escort", 1, "questionable") == 60
    assert jobs.per_day_cp("escort", 3, "questionable") == 60 * 9
    assert jobs.per_day_cp("carry", 5, "questionable") == 10, "labour is flat"


def test_diplomacy_raises_the_pay_by_a_lot_and_never_past_three_times():
    """Answer 5: "if I can convince someone I'm worth more than I am I should get paid up
    to 3x". Influence Attitude's steps — one for making it, one more per 5 over — at half
    the offer a step: 1.5x, 2x, 2.5x, then 3x and never more."""
    assert [jobs.haggled_times(m) for m in (0, 4, 5, 10, 15, 40)] == [1.5, 1.5, 2.0, 2.5,
                                                                      3.0, 3.0]


def test_haggling_the_pay_is_the_make_request_roll_and_the_engine_prices_it(worlds):
    """Answer 5, end to end: a request for payment made of the employer of a job just
    offered is the haggle (CRB p.93's DC, +5 per earlier request), and a granted one raises
    the offer the card, the reward and the tell all carry."""
    s, e, clerk = _hiring_table(worlds)
    _job(e, clerk, "offer", work="fight")
    esc = _escort(s)
    base = jobs.pay_of(esc)["per_day_cp"]
    _run(e, [{"op": "check", "actor": "pc", "target": clerk.ref,
              "params": {"skill": "diplomacy", "request": "payment"}}])
    assert s.awaiting and s.awaiting["label"] == "Diplomacy check", "the player's popup"
    res = e.resume(20)
    out = next(o for o in res.outcomes if o.op == "check")
    assert out.verdict == "success" and "better pay" in out.tell
    now = jobs.pay_of(cards.find(s, esc.id))
    assert now["per_day_cp"] == int(round(base * jobs.haggled_times(out.margin)))
    assert now["per_day_cp"] <= base * 3
    assert jobs.coin_words(e, now["per_day_cp"]) in out.tell
    # The employer's patience: the next request is +5 harder.
    from rules import requests

    assert requests.memory(clerk, s.clock_minutes)["asked"] == 1


# --- accepting, meeting, travelling, being paid --------------------------------------------

def test_an_escort_taken_met_travelled_and_paid(worlds):
    """The owner's path: offered, taken, at the road head at the hour (the caravan's people
    there), the road walked WITH them (`came_along`), and paid at the far end by the
    caravan master out of the purse the job put the wage in."""
    s, e, clerk = _hiring_table(worlds)
    _job(e, clerk, "offer", work="fight")
    took = _job(e, clerk, "accept").outcomes[0]
    esc = _escort(s)
    assert cards.standing(cards.find(s, esc.id)) == cards.OWN
    assert "signs on" in took.tell and esc.job["meets"]["where"] in took.tell
    master = s.people[esc.job["counterpart"]["master"]]
    owed = jobs.total_cp(cards.find(s, esc.id))
    assert goods.in_copper(master.purse) >= owed
    # Walk to the road head; the meeting is made.
    res = _run(e, [{"op": "travel", "params": {"place": esc.job["meets"]["where"]}}])
    met = [o for o in res.outcomes if o.op == "job"]
    assert met and "counts" in met[0].tell
    assert cards.find(s, esc.id).job["state"] == "met"
    assert all(r in s.actors for r in esc.job["counterpart"]["people"])
    # The road, with them.
    before = goods.in_copper(s.pc().purse)
    s.clock_minutes = esc.job["meets"]["minute"]
    e.dice = Dice(seed=3)
    for _ in range(12):
        e._journeyed = ""
        res = _run(e, [{"op": "journey", "params": {"to": esc.job["route"]["to_name"]}}])
        if s.in_encounter:
            s.end_encounter()
        if s.location_id == esc.job["route"]["to"]:
            break
    assert s.location_id == esc.job["route"]["to"]
    assert all(s.people[r].at == s.at for r in esc.job["counterpart"]["people"]
               if not s.people[r].has_state("state.down.dead"))
    card = cards.find(s, esc.id)
    assert card.job["state"] == "paid" and card.stage == "resolved"
    assert goods.in_copper(s.pc().purse) - before == owed


def test_the_wagons_introduced_are_the_caravans_people_never_somebody_new(worlds):
    """Measured live 2026-10-27: "I walk out to the road to Kalixiri to meet the wagons" had
    the plan introduce "the wagons", and a fifth person named the wagons stood beside the
    caravan's four. Words that name the job's caravan bind to its master, already here."""
    s, e, _clerk = _hiring_table(worlds)
    esc = _escort(s)
    e.place_party(esc.job["meets"]["at"])
    before = set(s.people)
    out = _run(e, [{"op": "introduce", "params": {"who": "the wagons"}}]).outcomes[0]
    assert set(s.people) == before
    assert out.effects[0]["how"] == "already_here"
    assert esc.job["counterpart"]["master"] in out.tell


def test_setting_out_with_the_caravan_owes_the_journey_and_needs_no_talking_round(worlds):
    """Measured live 2026-10-27, at the road head with the caravan met: "I give the word and
    set out with the caravan for Kalixiri" was read `go: Kalixiri`, which owed nothing, the
    plan walked the party to the road head it already stood on, and asked each of the four
    to join — all refused as indifferent, and the beat had them "remain indifferent to your
    command". A `go` naming a town the roads reach owes the journey; the caravan's people
    go with the wagons by the job, with nothing granted."""
    from gm import interpret

    s, e, clerk = _hiring_table(worlds)
    _job(e, clerk, "offer", work="fight")
    _job(e, clerk, "accept")
    esc = _escort(s)
    _run(e, [{"op": "travel", "params": {"place": esc.job["meets"]["where"]}}])
    to = esc.job["route"]["to_name"]
    frame = {"actions": [{"act": "go", "place": to, "span": f"set out for {to}"}]}
    assert interpret.ops_for(frame, s, e.places()) == ["journey"]
    master = esc.job["counterpart"]["master"]
    out = _run(e, [{"op": "company", "params": {"who": master}}]).outcomes[0]
    assert out.status != "refused" and "goes with the wagons" in out.tell
    assert not s.people[master].has_state("bond.travels-with-you")


# --- 4. not turning up -----------------------------------------------------------------------

def test_a_job_not_turned_up_for_lapses_and_the_employers_regard_drops_a_little(worlds):
    """Answer 4: taken, and the hour passed with the player elsewhere: the wagons leave
    without them, the card is let go, and the clerk's regard drops by MISSED_REGARD — said
    in a tell, since the player knew the hour they missed."""
    s, e, clerk = _hiring_table(worlds)
    _job(e, clerk, "offer", work="fight")
    _job(e, clerk, "accept")
    esc = _escort(s)
    before = attitude.regard_of(clerk)
    s.clock_minutes = esc.job["meets"]["minute"] + jobs.GRACE_MINUTES + 1
    told = jobs.settle(e)
    assert told and "left without" in told[0].tell
    card = cards.find(s, esc.id)
    assert card.job["state"] == "lapsed" and card.stage == "dropped"
    assert attitude.regard_of(clerk) == before - jobs.MISSED_REGARD
    # The caravan is gone, toward its town, and its trail is real (`tracking`).
    master = s.people[esc.job["counterpart"]["master"]]
    assert not tracking.same_ground(master.at, s.at)
    assert tracking.quarry_of(s, "the caravan")["ref"] == master.ref


def test_an_offer_never_taken_lets_the_wagons_go_and_costs_nothing(worlds):
    """Only a job taken and missed costs regard: an offer the player never took up is let
    go when the wagons leave."""
    s, e, clerk = _hiring_table(worlds)
    esc = _escort(s)
    before = attitude.regard_of(clerk)
    s.clock_minutes = esc.job["meets"]["minute"] + jobs.GRACE_MINUTES + 1
    assert jobs.settle(e) == []
    assert cards.find(s, esc.id).job["state"] == "gone"
    assert attitude.regard_of(clerk) == before


# --- the guard week -------------------------------------------------------------------------

def test_the_guard_week_is_the_work_op_at_the_jobs_wage(worlds):
    """Answer 1's other half: taking the week's guard work runs the existing `work` op —
    its clock, its body — at the job's engine-priced wage, and the job is done and paid."""
    s, e, clerk = _hiring_table(worlds)
    esc = _escort(s)
    s.clock_minutes = esc.job["meets"]["minute"] + jobs.GRACE_MINUTES + 1
    jobs.settle(e)
    _job(e, clerk, "offer", work="fight")
    week = _week(s)
    wage = jobs.pay_of(week)["per_day_cp"]
    before = goods.in_copper(s.pc().purse)
    res = _job(e, clerk, "accept")
    out = res.outcomes[0]
    # The take-up said as agreeing to the work, never as taking a thing from somebody
    # (tests/test_job_worked_and_paid_is_told.py, the beat-hands-over of 2026-11-05).
    assert out.op == "work" and f"agrees to work the week for {clerk.name}" in out.tell
    card = cards.find(s, week.id)
    paid = goods.in_copper(s.pc().purse) - before
    assert paid == wage * 7 and card.job["state"] == "paid" and card.stage == "resolved"


# --- what the clerk may say ------------------------------------------------------------------

def test_the_clerks_reply_slot_carries_the_jobs_facts_and_is_read_back_against_them(worlds):
    """The reply slot of an employer gets the job's facts — road, hour, people, pay — and
    is marked for the read-back with them (`holds`), so "the outpost" either is the job's
    destination or is made up."""
    from rules.engine import Outcome

    s, e, clerk = _hiring_table(worlds)
    talk = [Outcome("i1", "say", tell=f"You speak to {clerk.name}.",
                    effects=[{"kind": "said", "who": "", "to": clerk.ref}])]
    slots = planned.build_plan(e, "What is the work?", talk, last_beat="The clerk writes.")
    reply = next(x for x in slots if x["key"] == "reply")
    esc = _escort(s)
    assert esc.job["route"]["to_name"] in reply["say"]
    assert reply["no_job"] == clerk.name and esc.job["route"]["to_name"] in reply["holds"]


def test_the_reading_builds_the_job_op_and_the_plans_own_is_dropped(worlds):
    """"I tell the clerk I can fight": the reader's closed answer (`interpret.confirm_job`)
    builds the `job` op whole; a `job` or `work` the plan wrote is dropped — the plan never
    offers or takes work (the five made-up replies of the owner's save)."""
    s, e, clerk = _hiring_table(worlds)
    frame = {"question": False, "claims": [], "actions": [
        {"span": "tell the clerk I can fight", "target": "the clerk", "says": "I can fight",
         "act": "talk"}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    seen = []

    def ask(span, who, titles):
        seen.append((span, who, list(titles)))
        return {"answer": "says what work they can do", "work": "fight", "job": "not said"}

    notes = acts_to_ops.jobs_spoken(rows, frame, s, ask=ask)
    built = [i for r in rows for i in r.intents]
    assert built and built[0]["op"] == "job" and built[0]["params"] == {
        "do": "offer", "work": "fight"}
    assert seen and seen[0][1] == clerk.name and notes
    plan = [{"op": "work", "params": {"days": 7}}, {"op": "job", "params": {"do": "accept"}},
            {"op": "say", "params": {"words": "I can fight"}}]
    out = acts_to_ops.apply(plan, rows, frame, s)
    assert [r["op"] for r in out] == ["say", "job"]


def test_asking_for_more_pay_in_words_is_the_make_request_roll(worlds):
    """Answer 5 through the reader: "That's too little for a sword arm" is read as talk, and
    the closed answer "asks for more pay" builds the Diplomacy request against the employer
    — the popup — which the engine makes the haggle. Before an offer is priced there is
    nothing to haggle, and nothing is built."""
    s, e, clerk = _hiring_table(worlds)
    frame = {"question": False, "claims": [], "actions": [
        {"span": "tell the clerk that's too little for a sword arm", "target": "the clerk",
         "says": "that's too little for a sword arm", "act": "talk"}]}

    def ask(span, who, titles):
        return {"answer": "asks for more pay", "work": "not said", "job": "not said"}

    rows = acts_to_ops.table(frame, s, places=e.places())
    acts_to_ops.jobs_spoken(rows, frame, s, ask=ask)
    assert not [i for r in rows for i in r.intents], "no offer priced yet"
    _job(e, clerk, "offer", work="fight")
    rows = acts_to_ops.table(frame, s, places=e.places())
    acts_to_ops.jobs_spoken(rows, frame, s, ask=ask)
    built = [i for r in rows for i in r.intents]
    assert built == [{"op": "check", "actor": "pc", "target": clerk.ref,
                      "params": {"skill": "diplomacy", "request": "payment"},
                      "because": f"the player asks {clerk.name} for better pay"}]
    # One request a sentence. Measured live: the same line read as a talk AND a request
    # handed the player two Diplomacy popups, the second at +5.
    both = {"question": False, "claims": [], "actions": [
        dict(frame["actions"][0]),
        {"span": "ask for better pay", "object": "better pay", "asks_for": "payment",
         "act": "request"}]}
    rows = acts_to_ops.table(both, s, places=e.places())
    acts_to_ops.jobs_spoken(rows, both, s, ask=ask)
    assert len([i for r in rows for i in r.intents if i["op"] == "check"]) == 1


def test_the_owners_existing_save_is_left_as_it_is(worlds):
    """Answer 6: nothing migrates a save. A card written before jobs existed round-trips
    with no `job` key, and the clock's job pass over a scene with no jobs changes nothing
    and says nothing — jobs open only when a start is staged."""
    from tests.test_known_matters import _market

    s, e, _m = _market(worlds)
    old = {"id": "quest-1-x", "title": "Find the caravan", "kind": "quest",
           "objectives": [{"text": "Find it", "done": False}], "known": "heard"}
    card = cards.Card.from_dict(old)
    assert "job" not in card.as_dict() and card.job == {}
    before = [c.as_dict() for c in cards.load(s)]
    assert jobs.settle(e) == []
    assert [c.as_dict() for c in cards.load(s)] == before and not jobs.jobs(s)


# --- tracking a caravan that exists --------------------------------------------------------

def test_a_caravan_that_exists_can_be_tracked_and_followed(worlds):
    """The owner's first report: tracking a caravan the engine never held. Now the caravan
    is real: at the road head its trail ends where it stands; gone, its wagons' trail leads
    off toward its town, a journey not a walk."""
    s, e, clerk = _hiring_table(worlds)
    esc = _escort(s)
    e.place_party(esc.job["meets"]["at"])
    held = tracking.quarry_of(s, "the caravan")
    assert held is not None and held["ref"] == esc.job["counterpart"]["master"]
    s.clock_minutes = esc.job["meets"]["minute"] + jobs.GRACE_MINUTES + 1
    e.place_party(next(p.id for p in e.places() if p.id != esc.job["meets"]["at"]
                       and tracking.same_ground(p.id, s.at)))
    jobs.settle(e)
    e.place_party(esc.job["meets"]["at"])
    trail = next(t for t in tracking.trails(s) if t["ref"] == held["ref"])
    assert trail["size"] == "large" and not trail["here"]
    words, walk = tracking.after(s, quarry="the caravan", quarry_held=held, found=[trail],
                                 every=[trail], follow=True, beat_ground=True,
                                 place_name=lambda pid: pid)
    assert "journey, not a walk" in words and walk == ""


# --- 7. someone else's errand ---------------------------------------------------------------

def test_an_unheard_errands_step_ticks_silently_and_nothing_reaches_the_page(worlds,
                                                                              monkeypatch):
    """Answer 7: "if I am in the right spot and I get the item that is fine but no mention
    should be made to me about anything since my character would be unaware that I had an
    item someone wanted." Measured before: a-small-favour's `reached` fired at the fields
    for a quest the player had never heard of, its tell "the approach, the ground where
    Glowvine grows" came back as the player "searching the soil where the luminescent
    Glowvine is known to take root". Now the objective ticks and the tick returns nothing:
    no outcome, so no tell and no planned slot. Heard is different, and keeps its tell."""
    from tests.test_known_matters import _market

    monkeypatch.setattr(schemes, "ENABLED", True)
    s, e, _m = _market(worlds)
    inst = schemes.open_scheme(e, schemes.shipped()["a-small-favour"], turn=1)
    quest = next(c for c in cards.load(s) if c.kind == "quest")
    assert cards.standing(quest) == cards.UNHEARD
    wild = inst["slots"].get("wild") or {}
    if not wild.get("id"):
        pytest.skip("no wild place in this world for the errand")
    e.place_party(wild["id"])
    told = schemes.tick(e, [])
    assert cards.find(s, quest.id).objectives[0]["done"], "the objective still counts"
    assert not any(quest.title in str(o.tell) or "Glowvine" in str(o.tell) or
                   any(isinstance(x, dict) and x.get("not_own") for x in o.effects or ())
                   for o in told)
    assert inst["fired"]["reached"]["silent"] is True
    assert not cards.quest_log(s)["active"], "not in the Journal either"


def test_a_heard_errands_step_keeps_its_tell_marked_not_the_players(worlds, monkeypatch):
    """Heard is different (answer 7): the player knows of it, so the step is told, and the
    tell is marked `not_own` for the read-back that keeps it somebody else's matter."""
    from tests.test_known_matters import _market

    monkeypatch.setattr(schemes, "ENABLED", True)
    s, e, _m = _market(worlds)
    inst = schemes.open_scheme(e, schemes.shipped()["a-small-favour"], turn=1)
    quest = next(c for c in cards.load(s) if c.kind == "quest")
    quest.known = "heard"
    cards._store(s, quest)
    wild = inst["slots"].get("wild") or {}
    if not wild.get("id"):
        pytest.skip("no wild place in this world for the errand")
    e.place_party(wild["id"])
    told = schemes.tick(e, [])
    marked = [o for o in told for x in o.effects or ()
              if isinstance(x, dict) and x.get("not_own") == quest.title]
    assert marked
