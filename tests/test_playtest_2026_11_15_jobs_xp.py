"""Playtest 2026-11-15 (0.3.6, the Blood Bender outlaw): jobs, the Journal, XP and skill use.

Items 8, 9, 11, 40, 53, 73, 79, 80, 82, 83, 84, 99 and 100 of
pgm-work/playtest-2026-11-15.md, each test naming the item and what was measured. Day 1 of
that run paid 535 XP — 100 for a Stealth "vs 12" at a bracelet that did not exist, 200 for
the GM's private note moving mid-mugging, 135 for the merchant, 100 for an Intimidate "vs
12" at a guard who was not there; by the CRB's "overcome a challenge" only the merchant's
135 stands.
"""
from __future__ import annotations

from gm import acts_to_ops, interpret, narration
from rules import cards, disguise, goods, jobs, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from tests._places import stand_on
from tests.test_real_jobs import _escort, _hiring_table, _job, _run, _week


def _street(seed=7):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    stand_on(s, "urban")
    s.clock_minutes = 12 * 60
    return s, Engine(s, Dice(seed=seed))


# --- XP: obstacles overcome, not rolls (#11, #53, #40) -------------------------------------

def test_a_check_at_nobody_pays_nothing_however_well_it_rolls():
    """#11/#53: "You gain 100 XP for the intimidate check" at a gate guard who did not
    exist, and the same for a Stealth "vs 12" whose bracelet was not there. A plan band DC
    at nobody is no obstacle on the record (CRB "Awarding Experience": monsters, traps,
    obstacles and roleplaying encounters overcome)."""
    s, e = _street()
    pc = s.pc()
    xp = pc.xp
    for skill in ("intimidate", "stealth"):
        out = _run(e, [{"op": "check", "actor": "pc", "visibility": "hidden",
                        "params": {"skill": skill, "dc": {"band": "average"}}}]).outcomes[-1]
        assert "XP" not in out.tell, out.tell
    assert pc.xp == xp


def test_an_obstacle_overcome_pays_once_not_every_time():
    """Once per obstacle and skill: the same thug out-sneaked twice is one challenge."""
    s, e = _street()
    s.add(instantiate("thug", scene=s, name="the thug"))
    pc = s.pc()
    first = e.reward_check(pc, "stealth", 15, modifier=3, obstacle="c1")
    assert "XP" in first
    assert e.reward_check(pc, "stealth", 15, modifier=3, obstacle="c1") == ""


# --- jobs (#8, #9, #84) --------------------------------------------------------------------

def test_the_hirers_doing_is_taught_as_no_agreement():
    """#8: "While Lyra writes my name" signed the character onto a five-day caravan. The
    job reader's demonstrations now show the hirer's own doing as "something else", and a
    job already taken given up as "turns it down" (#9)."""
    demos = {said: answer for said, _w, _t, answer, _k, _j in interpret._JOB_DEMOS}
    assert demos["while the drover counts out the wages"] == "something else"
    assert demos["as the foreman writes my name in his ledger"] == "something else"
    assert "hirer is doing is something else" in interpret.job_messages("x", "y", [])[0][
        "content"]


def test_changing_your_mind_gives_up_the_job_held_not_the_other_offer(worlds):
    """#9: "I've changed my mind about the caravan" turned down the town week, and the
    caravan she was signed to stayed. The taken job is now on the reader's list, and the
    decline gives it up — the wagons' pay leaves the master's purse again."""
    s, e, clerk = _hiring_table(worlds)
    _job(e, clerk, "offer", work="fight")
    esc = _escort(s)
    _job(e, clerk, "accept", job=esc.id)
    master = s.people[esc.job["counterpart"]["master"]]
    funded = goods.in_copper(master.purse)
    frame = {"question": False, "claims": [], "actions": [
        {"span": "tell the clerk I've changed my mind about the caravan",
         "target": "the clerk", "says": "I've changed my mind about the caravan",
         "act": "talk"}]}
    seen = []

    def ask(span, who, titles):
        seen.append(list(titles))
        return {"answer": "turns it down", "work": "not said", "job": esc.title}

    rows = acts_to_ops.table(frame, s, places=e.places())
    acts_to_ops.jobs_spoken(rows, frame, s, ask=ask)
    assert esc.title in seen[0], "the taken job is on the reader's list"
    built = [i for r in rows for i in r.intents if i["op"] == "job"]
    assert built[0]["params"] == {"do": "decline", "job": esc.id}
    out = _run(e, built).outcomes[-1]
    assert "gives up" in out.tell, out.tell
    esc = cards.find(s, esc.id)
    assert esc.job["state"] == "declined" and not esc.live
    assert goods.in_copper(master.purse) < funded


def test_a_dock_keeper_has_work_when_asked():
    """#84: asked for paid dock work, the harbourmaster said there was always labour, and no
    job existed — 1 gp in hand, a 28.8 gp fare, no honest way to earn it. A keeper of a place
    in `jobs.HIRES` opens a priced week of hauling when asked."""
    s, e = _street()
    keeper = instantiate("commoner-level-1", scene=s, name="the harbourmaster")
    from rules import keepers

    keeper.world_entity_id = keepers.entity_id(s.location_id + "~urban:the-docks")
    s.add(keeper)
    assert jobs.hires_hands(keeper) == ("carry", "labour")
    out = _run(e, [{"op": "job", "actor": "pc", "target": keeper.ref,
                    "params": {"do": "offer"}}]).outcomes[-1]
    assert out.status != "refused", out.tell
    week = next(c for c in jobs.jobs(s) if c.giver == keeper.ref)
    assert week.job["work"] == "carry" and jobs.total_cp(week) == 7 * jobs.UNTRAINED_CP
    assert cards.standing(week) == cards.OFFERED


# --- the Journal (#99, #100, #73) -----------------------------------------------------------

def test_a_week_turned_down_leaves_the_journal_and_a_missed_job_reads_missed(worlds):
    """#99: the town week turned down on day 1 was still "in play" a month on, and the
    caravan she missed sat under "Finished" as if seen through."""
    s, e, clerk = _hiring_table(worlds)
    _job(e, clerk, "offer", work="fight")
    week = _week(s)
    _job(e, clerk, "decline", job=week.id)
    log = cards.quest_log(s)
    assert week.id not in {r["id"] for r in log["active"]}
    esc = _escort(s)
    jobs.close(e, esc.id, "lapsed")
    cards.resolve(s, esc.id, how="dropped")
    row = next(r for r in cards.quest_log(s)["finished"] if r["id"] == esc.id)
    assert row["ended"] in ("missed", "turned down"), row


def test_a_job_keeps_only_its_own_tells_and_never_a_stump():
    """#100: "Lyra Lyraxys c Vesna Kroll speaks to the harbourmaster…" — tells cut at 200
    characters mid-word, and any tell naming the employer filed on her job."""
    from rules.engine import Outcome

    s, e = _street()
    clerk = instantiate("commoner-level-1", scene=s, name="the clerk")
    s.add(clerk)
    card = cards.open_card(s, cards.Card(id="job-1-week", title="A week's work",
                                         kind="job", people=[clerk.ref], giver=clerk.ref))
    long = ("The clerk says a good deal about the road. " * 6).strip()
    cards.touch_from_outcomes(s, [Outcome("i1", "say", tell=long)], turn=3)
    assert cards.find(s, card.id).facts == [], "a tell about no job is not the job's"
    cards.touch_from_outcomes(s, [Outcome("i2", "job", tell=long, effects=[
        {"kind": "job", "id": card.id, "state": "offered"}])], turn=4)
    fact = cards.find(s, card.id).facts[-1]
    assert len(fact) <= 200 and fact.endswith(".")


def test_a_known_name_misspelt_is_that_person_not_the_stranger():
    """#73: "Word reaches you from Lyra Lyraxs" became "from the stranger"."""
    text, unnamed = narration.unname_strangers(
        "Word reaches you from Lyra Lyraxs about the escort.", {"Lyra Lyraxys"})
    assert text == "Word reaches you from Lyra Lyraxys about the escort." and not unnamed


# --- skills and clothes (#79, #80, #82, #83) ------------------------------------------------

def test_changing_into_a_carried_outfit_puts_it_on():
    """#79: "I change into the new traveler's outfit" did nothing; an outfit was "not
    something that can be worn"."""
    s, e = _street()
    pc = s.pc()
    pc.goods["peasant outfit"] = 1
    frame = {"question": False, "claims": [], "actions": [
        {"span": "change into the peasant outfit", "object": "the peasant outfit",
         "act": "use"}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    built = [i for r in rows for i in r.intents]
    assert built and built[0]["op"] == "wear"
    out = _run(e, built).outcomes[-1]
    assert pc.slot_list("body")[0] == "peasant outfit", out.tell
    assert "peasant outfit" not in pc.goods


def test_a_skill_named_in_a_use_is_the_skill_not_a_thing():
    """#80: "I use my Disguise skill to make myself look like a dock labourer" was refused
    "There is no disguise skill here"."""
    s, e = _street()
    frame = {"question": False, "claims": [], "actions": [
        {"span": "use my Disguise skill to look like a dock labourer",
         "object": "Disguise skill", "power": "Disguise", "means": "power", "act": "use"}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    assert [i["op"] for r in rows for i in r.intents] == ["disguise"]


def test_a_disguise_is_held_and_the_watch_asks_it():
    """#82: Disguise rolled "vs 10" and nothing stayed on the character. Now the secret
    result is `state.disguised` through the applicator, and a guard who sees a wanted
    woman knows her only when his Perception (taking 10) beats it."""
    from rules import arrest

    s, e = _street()
    pc = s.pc()
    out = _run(e, [{"op": "disguise", "actor": "pc", "params": {"as": "a dock labourer"}}]
               ).outcomes[-1]
    assert pc.has_state(disguise.TAG), out.tell
    assert out.rolls and "vs" not in out.tell
    held = disguise.worn(pc)
    guard = instantiate("commoner-level-1", scene=s, name="the guard")
    s.add(guard)
    guard.apply_effect(ActiveEffect(name="guard", kind="role", source="test",
                                    origin="author:test", duration="until-dismissed",
                                    tags=(states.GUARD,)))
    held.payload["result"] = 99
    assert disguise.passes(guard, pc) and guard not in arrest.guards_who_see(e, pc)
    held.payload["result"] = 1
    assert not disguise.passes(guard, pc) and guard in arrest.guards_who_see(e, pc)


def test_the_plans_disguise_check_is_the_disguise_too():
    """#83: the same words rolled the plan's Disguise check one turn and nothing the next.
    Whichever door it comes in by, a Disguise check makes the held disguise."""
    s, e = _street()
    _run(e, [{"op": "check", "actor": "pc", "visibility": "hidden",
              "params": {"skill": "disguise", "dc": {"band": "easy"}}}])
    assert s.pc().has_state(disguise.TAG)
    frame = {"question": False, "claims": [], "actions": [
        {"span": "disguise myself as a dock labourer", "object": "a dock labourer",
         "act": "disguise"}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    plan = [{"op": "check", "params": {"skill": "disguise", "dc": {"band": "easy"}}}]
    out = acts_to_ops.apply(plan, rows, frame, s)
    assert [r["op"] for r in out] == ["disguise"]


def test_a_built_disguise_is_not_rolled_twice_by_the_declared_check():
    """Live, 2026-11-15: "I disguise myself as a dock labourer" built the disguise, and the
    declared-check injector added a second Disguise check from the same words, which made
    a second disguise over the first (30 minutes, then 10 more, the first replaced)."""
    from gm import judgement

    s, _e = _street()
    raw = [{"op": "disguise", "actor": "pc", "params": {"as": "a dock labourer"}}]
    assert judgement.inject_checks(raw, "I disguise myself as a dock labourer", s) == raw


def test_who_the_player_is_disguised_as_is_never_a_newcomer():
    """Live, 2026-11-15: after "I use my Disguise skill to make myself look like a dock
    labourer" the prose said "the weary air of a dock laborer", and the seen-people step
    made a dock labourer (c18) stand in the market with a face of his own."""
    from gm import judgement

    s, e = _street()
    _run(e, [{"op": "disguise", "actor": "pc", "params": {"as": "a dock labourer"}}])
    assert judgement._the_disguise(s, "dock laborer")
    assert judgement._the_disguise(s, "the dock labourer")
    assert not judgement._the_disguise(s, "the harbourmaster")
