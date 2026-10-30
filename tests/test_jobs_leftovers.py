"""The real-jobs lane's leftovers, fixed for 0.2.22 (docs/known-matters.md §6.4, §6.7).

Four things the 0.2.22 escort run measured on Pangrella (2026-10-27, gemma-4-12B, Planned):

  1. the road's encounter roll drew a reptoid, and the beat said "The reptoid is of the
     Korvu people: weathered well past what the years alone would do …" — a local
     people's face on a bestiary race;
  2. the caravan's four stood outside any fight on the road;
  3. once met at the road head, the wagons waited for ever for the word to set out;
  4. "I go back to the guild clerk and tell them I can fight": the plan failed seven times
     on a walk the engine refused (the clerk was standing there), and the fallback threw
     away the job offer the reading had built.
"""
from __future__ import annotations

from types import SimpleNamespace

from gm import acts_to_ops, companions, interpret
from rules import attitude, bestiary, cards, jobs, names, states
from rules.dice import Dice
from rules.engine import Engine, Scene

from tests.test_real_jobs import _escort, _hiring_table, _job, _run


# --- 1. a face only for somebody with a people ------------------------------------------------

def test_a_reptoid_met_on_the_road_wears_no_local_peoples_face(worlds):
    """Measured on the escort run: a reptoid — "humanoid (reptilian, shapechanger)",
    Bestiary 5, drawn by the road's encounter roll — arrived with a true name and a Korvu
    face, and the beat said it "is of the Korvu people". A humanoid whose block states the
    ground it lives on is a race of its own (67 of 3,747 humanoid blocks: giants,
    goblinoids, reptilians …); a role block with no stated ground (the guard, the bandit,
    a merchant sailor) is what a local person wears, and keeps its face."""
    assert not bestiary.has_a_people("reptoid")
    assert bestiary.body_words("reptoid") == "Medium humanoid"
    assert bestiary.has_a_people("bandit") and bestiary.has_a_people("old-sailor")
    row = (worlds.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    from rules.sheet import load_pc

    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=3), world=worlds)
    e.place_party()
    reptoid = s.actors[e._bring_in("reptoid")[0]["ref"]]
    assert reptoid.appearance == "" and reptoid.true_name == ""
    bandit = s.actors[e._bring_in("bandit")[0]["ref"]]
    pooled = bool(names.pool_for(worlds, s.location_id, None))
    assert bandit.true_name or not pooled


def test_every_door_that_writes_a_face_asks_whether_the_body_has_a_people():
    """`names.face_of` is the one door the minting sites write `Actor.appearance` through
    (the spawn, the caravan, the opening's lead, a keeper, a body for somebody described,
    the opening's companion, the load-time sweep); it answers "" for a body with no
    people. Grepped: no site writes `appearance_for(...)` straight onto an actor any more."""
    import re
    from pathlib import Path

    reptoid = SimpleNamespace(ref="c9", _creature_doc=lambda: bestiary.raw("reptoid"))
    assert names.face_of(object(), "x", reptoid) == ""
    straight = re.compile(r"\.appearance\s*=\s*(?:\(\s*)?names_mod\.appearance_for\(")
    hits = [f"{p}:{n}" for p in Path(".").glob("*/*.py")
            if p.parts[0] in ("rules", "gm", "play", "world")
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if straight.search(line)]
    assert hits == [], hits


def test_a_saved_reptoid_with_a_korvu_face_has_it_taken_off_on_load():
    """A save from the escort run already holds the reptoid's face: the load-time sweep
    (`judgement.name_the_nameless`) puts back what the spawn gave a body with no people —
    a face in the people's own "<people>: …" shape."""
    from gm import judgement

    world = SimpleNamespace(play={"races": [{"id": "k", "name": "Korvu", "body": ["x"]}]})
    reptoid = SimpleNamespace(is_pc=False, true_name="", name="reptoid",
                              appearance="Korvu: weathered well past what the years do",
                              world_entity_id="", from_template="reptoid",
                              _creature_doc=lambda: bestiary.raw("reptoid"))
    scene = SimpleNamespace(actors={"c8": reptoid}, location_id="x")
    import rules.names as names_mod

    orig = names_mod.people_names
    names_mod.people_names = lambda w, s: {"korvu"}
    try:
        judgement.name_the_nameless(scene, world)
    finally:
        names_mod.people_names = orig
    assert reptoid.appearance == ""


def test_the_wagons_named_away_from_the_caravan_bring_nobody_in(worlds):
    """Measured on the leftovers run: stopped at the gate on the way to the road head, the
    plan introduced "the wagons", and a guildhand named "wagons" with a Korvu face stood at
    the gate while the caravan waited at the road. The caravan exists elsewhere: the
    introduce is refused with where it is, and nobody is made."""
    s, e, _clerk = _hiring_table(worlds)
    esc = _escort(s)
    before = set(s.people)
    out = _run(e, [{"op": "introduce", "params": {"who": "the wagons"}}]).outcomes[0]
    assert set(s.people) == before
    assert out.status == "refused" and esc.job["meets"]["where"] in out.tell


def test_the_plans_step_on_a_job_is_passed_over_never_refused_into_the_prose(worlds):
    """Measured on the leftovers run: met at the road head, the plan wrote `quest_step` for
    "JOB, TAKEN ON: Guard the wagons to Kalixiri" (the brief's label), the engine refused
    "No such quest is underway. Nothing has been taken on yet.", and the beat told the
    player "No formal contract is yet recorded in your records". A job's steps are the
    engine's (`jobs.settle`); the plan's is passed over, with nothing said or ticked."""
    s, e, clerk = _hiring_table(worlds)
    _job(e, clerk, "offer", work="fight")
    _job(e, clerk, "accept")
    esc = _escort(s)
    out = _run(e, [{"op": "quest_step", "params": {
        "quest": f"JOB, TAKEN ON: {esc.title}", "objective": 1}}]).outcomes[0]
    assert out.status != "refused" and out.tell == ""
    assert not cards.find(s, esc.id).objectives[0]["done"]


def test_the_plans_quest_copying_a_job_is_passed_over(worlds):
    """Measured on the leftovers run: on the road with the caravan, the plan wrote `quest`
    "Guard the wagons to Kalixiri" with the job's objectives and "6 Eldrida gold pieces" as
    reward, refused "No numbers on a quest …" into the prose on two turns of three. The job
    is the engine's card already: the copy is passed over, and no second card is made."""
    s, e, clerk = _hiring_table(worlds)
    _job(e, clerk, "offer", work="fight")
    _job(e, clerk, "accept")
    esc = _escort(s)
    before = len(cards.load(s))
    out = _run(e, [{"op": "quest", "params": {
        "title": esc.title, "objectives": ["See the wagons safe"],
        "reward": "6 gold pieces"}}]).outcomes[0]
    assert out.status != "refused" and out.tell == "" and len(cards.load(s)) == before


# --- 2. the caravan on the road ---------------------------------------------------------------

def _set_out(worlds):
    s, e, clerk = _hiring_table(worlds)
    _job(e, clerk, "offer", work="fight")
    _job(e, clerk, "accept")
    esc = _escort(s)
    _run(e, [{"op": "travel", "params": {"place": esc.job["meets"]["where"]}}])
    return s, e, clerk, esc


def test_the_caravans_people_join_a_fight_on_the_road_on_the_players_side(worlds):
    """Measured on the escort run: six hours out the road met a reptoid, and the caravan's
    four stood outside anything that came of it. Setting out binds them to the party for
    the road (`jobs.set_out`, `bond.travels-with-you` from `job:<id>`), so a fight drawn
    there brings them into the order on the player's side (`Engine._companions_join`),
    each to decide their own turn in character (the companions ruling, 2026-10-01)."""
    s, e, _clerk, esc = _set_out(worlds)
    people = esc.job["counterpart"]["people"]
    bound = jobs.set_out(e, esc.job["route"]["to"])
    assert sorted(bound) == sorted(people)
    assert all(s.people[r].has_state(states.TRAVELS_WITH_YOU) for r in people)
    foe = s.actors[e._bring_in("bandit")[0]["ref"]]
    assert e._ensure_encounter(s.pc().ref, target=foe.ref)
    pc_side = next(refs for refs in s.sides.values() if s.pc().ref in refs)
    assert set(people) <= set(pc_side)
    assert set(people) <= {r for r, _ in s.initiative}


def test_a_hired_hand_is_told_what_they_were_hired_for_not_that_they_are_a_friend(worlds):
    """Their turn's character facts (`companions.who_they_are`) say what the job hired
    each for — the hired sword fights for the wagons, a teamster drives and may run — and
    not "a friend who came along", which is a companion's. Whether a teamster stands or
    runs is their own turn's decision, from this and their sheet."""
    s, e, _clerk, esc = _set_out(worlds)
    jobs.set_out(e, esc.job["route"]["to"])
    roles = esc.job["counterpart"]["roles"]
    for ref, role in roles.items():
        said = companions.who_they_are(s, s.people[ref])
        assert "friend who came along" not in said
        assert {"master": "caravan master", "driver": "not to fight",
                "guard": "hired sword"}[role] in said


def test_the_bond_goes_when_the_wagons_are_in(worlds):
    """Paid at the far end, the caravan's people stop travelling with the player."""
    s, e, _clerk, esc = _set_out(worlds)
    for _ in range(12):
        e._journeyed = ""
        _run(e, [{"op": "journey", "params": {"to": esc.job["route"]["to_name"]}}])
        if s.in_encounter:
            s.end_encounter()
        if s.location_id == esc.job["route"]["to"]:
            break
    assert cards.find(s, esc.id).job["state"] == "paid"
    assert not any(s.people[r].has_state(states.TRAVELS_WITH_YOU)
                   for r in esc.job["counterpart"]["people"])


def test_leading_the_wagons_on_is_the_journey_not_a_walk_back_or_a_pick_up(worlds):
    """Measured on the leftovers run, on a stretch of the road after the fight: "I nod to the
    merchants and lead the wagons on toward Kalixiri" was read `go: Kalixiri, object: the
    wagons`. The table built "Kesst Vayr takes the wagons" (a pick-up of the caravan), the
    plan added a travel to "the outskirts" beside the owed journey, the travel walked the
    party a day back to Kalimnar and shed the caravan, and the journey was refused as the
    turn's second. The caravan is never carried, and the plan's walk goes."""
    s, e, _clerk, esc = _set_out(worlds)
    to = esc.job["route"]["to_name"]
    frame = {"question": False, "claims": [], "actions": [
        {"act": "go", "place": to, "object": "the wagons",
         "span": f"lead the wagons on toward {to}"}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    assert rows[0].ops == ["journey"] and rows[0].intents == []
    plan = [{"op": "travel", "params": {"place": "the outskirts"}},
            {"op": "journey", "params": {"to": to}}]
    assert [r["op"] for r in acts_to_ops.apply(plan, rows, frame, s)] == ["journey"]


def test_taking_a_broken_road_up_again_is_not_a_repeat_of_the_last_turn():
    """Measured on the leftovers run: stopped by an aasimar in the way, "I lead the wagons
    around the aasimar and on to Kalixiri" (read `go: Kalixiri`) planned the same `journey`
    as the turn before; the repeat guard refused it twice and the turn degraded to
    narration. A journey the words' own `go` owes is the player asking again."""
    from gm import judgement
    from rules.engine import Intent

    line = "I lead the wagons around the aasimar and on to Kalixiri."
    interpret.remember(line, {"question": False, "claims": [], "actions": [
        {"act": "go", "place": "Kalixiri", "span": "lead the wagons on to Kalixiri"}]})
    plan = [Intent(op="journey", params={"to": "Kalixiri"})]
    assert judgement._does_what_was_declared(plan, line)


# --- 3. the wagons do not wait for ever --------------------------------------------------------

def test_met_wagons_leave_an_hour_past_their_hour_and_the_job_lapses(worlds):
    """Measured on the escort run: met at the road head at 8:40, the wagons stood ready
    "and wait for … the word", and nothing ever moved them. The terms say when they leave
    (`meets.minute`, noon); they wait GRACE_MINUTES past it — the same hour a late guard is
    given — and then go, the player standing there or not, and the job lapses as ruling 4
    says: the clerk's regard drops a little."""
    s, e, clerk, esc = _set_out(worlds)
    assert cards.find(s, esc.id).job["state"] == "met"
    before = attitude.regard_of(clerk)
    s.clock_minutes = esc.job["meets"]["minute"] + jobs.GRACE_MINUTES - 1
    assert jobs.settle(e) == [], "still within the hour"
    s.clock_minutes = esc.job["meets"]["minute"] + jobs.GRACE_MINUTES + 1
    told = jobs.settle(e)
    assert told and "has not given the word to set out" in told[0].tell
    card = cards.find(s, esc.id)
    assert card.job["state"] == "lapsed" and card.stage == "dropped"
    assert attitude.regard_of(clerk) == before - jobs.MISSED_REGARD
    assert not any(r in s.actors for r in esc.job["counterpart"]["people"])


def test_wagons_already_on_the_road_are_never_lapsed_by_the_clock(worlds):
    """Set out, the hour no longer applies: a road broken off by an encounter and taken up
    again later is still the job."""
    s, e, _clerk, esc = _set_out(worlds)
    jobs.set_out(e, esc.job["route"]["to"])
    s.clock_minutes = esc.job["meets"]["minute"] + 10 * 60
    assert jobs.settle(e) == []
    assert cards.find(s, esc.id).job["state"] == "met"


# --- 4. the reading's own ops survive a failed plan ---------------------------------------------

def test_a_person_named_where_a_place_goes_licenses_no_walk(worlds):
    """Measured on the escort run: "I go back to the guild clerk and tell them I can fight"
    was read `go: the guild clerk`; the detector's travel stood, the plan walked to the
    market the party stood in seven times, the engine refused it seven times, and the turn
    degraded. A `go` whose place is a person standing here is marked like a seek of
    somebody here (`interpret.ops_for`), and licenses no travel (`supported`)."""
    s, e, clerk = _hiring_table(worlds)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "go", "place": clerk.name, "span": f"go back to {clerk.name}"},
        {"act": "talk", "target": "them", "says": "I can fight",
         "span": "tell them I can fight"}]}
    assert interpret.ops_for({"actions": [frame["actions"][0]]}, s, e.places()) == []
    assert frame["actions"][0].get("here") == clerk.ref
    kept, dropped = interpret.supported(["travel", "say"], frame)
    assert "travel" in dropped and "say" in kept
    plan = [{"op": "travel", "params": {"place": "the market"}},
            {"op": "say", "params": {"words": "I can fight"}}]
    assert [r["op"] for r in acts_to_ops.unasked_travel(plan, frame, s, e.places())] == [
        "say"]


def test_a_plan_that_never_passes_keeps_the_readings_own_ops(worlds, monkeypatch):
    """The same turn's other half: the reading had built the job offer whole, and the
    fallback ("You try … but the moment does not answer") replaced the whole plan with a
    narrate_only. The table's built ops are validated on their own and kept; one refused
    on its own is left out, not the rest with it."""
    from gm.agent import GMAgent

    s, e, clerk = _hiring_table(worlds)
    agent = GMAgent.__new__(GMAgent)
    agent.engine = e
    agent.intents_first = True
    row = acts_to_ops.Row(index=0, act="talk")
    row.intents = [{"op": "job", "actor": "pc", "target": clerk.ref,
                    "params": {"do": "offer", "work": "fight"}, "because": "t"},
                   {"op": "job", "actor": "pc", "target": "c999",
                    "params": {"do": "nonsense"}, "because": "t"}]
    agent.rows = [row]
    kept = agent._built_survives()
    assert [(i.op, i.params.get("do")) for i in kept] == [("job", "offer")]
    out = e.run(kept)
    assert "puts work to" in out.outcomes[0].tell
