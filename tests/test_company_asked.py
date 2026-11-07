"""Somebody comes along only on the player's own word.

The owner's save of 2026-11-05 (owner-save-2026-11-05/slice.json, turn_log row 7). Vyrnys
had just offered a week of guard work, and the player said "Accept the terms of the work".

* The reader read one act, `other`. Its table built only the `job` accept
  (`acts_to_ops.jobs_spoken`), and the plan's `quest` was replaced by it.
* The plan ALSO wrote `{"op": "company", "params": {"who": "c2"}}`, with no actor and an
  empty `because`. That is the prompt's own example, word for word (gm/prompts.py teaches
  company for "a friend, a guide, a hired sword"), and c2 was Vyrnys.
* The engine refused it: "Vyrnys is indifferent towards you and does not walk out of here
  at your word. Talk them round first — that is a Diplomacy check against them."
* The planned narrator's first fact slot then wrote "Vyrnys remains unmoved by your
  words…", and the beat told the player "You must find a way to convince them", on a turn
  where they had simply taken a job.

The fix (`acts_to_ops.company_asked`, and the job's employer rule in `acts_to_ops.apply`):
the plan proposes, the reading confirms. A `company` stands only where a deed done now has
that person come along (or, for `leave`, sends them away), by ONE closed question
(`interpret.confirm_company`) asked only when the plan wrote one. With no question, or a
failed call, words said (`talk`, `request`) carry it by structure, as before; an `other`
does not. Anything else is struck from the plan silently, never refused onto the page.

Not code-only, as `job` is: the reader has no "come with me" act (it is a `talk` or a
`request`), so the plan stays the door a real invitation comes in by.
"""
from __future__ import annotations

import json

import pytest

from gm import acts_to_ops, planned
from rules import jobs, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

from test_real_jobs import _hiring_table, _job, _week

ACCEPT = "Accept the terms of the work"
# The reading the owner's save logged for the line, verbatim.
ACCEPT_READ = {"question": False, "claims": [],
               "actions": [{"act": "other", "span": ACCEPT}]}
# The refusal the engine gave, and the narrator's line it became.
REFUSED = "Talk them round first"


def _run(e, raw):
    return e.run(e.validate(raw, origin="author:test"))


def _the_save(world):
    """The hiring table with the week's guard work put to the player, the clerk
    indifferent, as Vyrnys was in the owner's save."""
    s, e, clerk = _hiring_table(world)
    _job(e, clerk, "offer", work="fight")
    e.settle_attitude(clerk, "indifferent", None, "test")
    return s, e, clerk


def _accept_rows(s, e, clerk, frame=ACCEPT_READ):
    """The table and the job the reader's closed answer built, as on row 7."""
    week = _week(s)
    rows = acts_to_ops.table(frame, s, places=e.places())
    acts_to_ops.jobs_spoken(
        rows, frame, s,
        ask=lambda span, who, titles: {"answer": "agrees to the job", "work": "not said",
                                       "job": week.title})
    return rows, week


def test_the_plans_company_left_in_was_the_refusal_on_the_page(worlds):
    """The defect itself, kept so the next reader sees what the fix prevents: the plan's
    `company` of an indifferent clerk is refused with the Diplomacy line the narrator
    turned into "remains unmoved by your words"."""
    s, e, clerk = _the_save(worlds)
    out = _run(e, [{"op": "company", "params": {"who": clerk.ref}}]).outcomes[0]
    assert out.status == "refused" and REFUSED in out.tell


def test_a_job_accepted_brings_nobody_along_and_refuses_nothing(worlds):
    """Row 7's plan, `[company c2, quest]`, with the reading `[other]` and the job the
    table built: the company is struck, the job is taken, and no outcome, tell or slot of
    the planned narrator says anybody was not talked round."""
    s, e, clerk = _the_save(worlds)
    rows, week = _accept_rows(s, e, clerk)
    assert [i["op"] for r in rows for i in r.intents] == ["job"]
    plan = [{"op": "company", "params": {"who": clerk.ref}},
            {"op": "quest", "params": {"title": week.title, "objectives": ["Guard"],
                                       "giver": clerk.ref}}]
    notes: list[str] = []
    raw = acts_to_ops.apply(plan, rows, ACCEPT_READ, s, notes=notes)
    # The question asked, as live: the words take work, they bring nobody along.
    raw = acts_to_ops.company_asked(raw, ACCEPT_READ, s,
                                    ask=lambda span, who: "something else", notes=notes)
    assert [r["op"] for r in raw] == ["job"], notes
    res = _run(e, raw)
    assert not [o for o in res.outcomes if o.op == "company"]
    told = " ".join(o.tell for o in res.outcomes)
    assert REFUSED not in told and "indifferent" not in told, told
    assert any(c.id == week.id and c.job.get("state") for c in jobs.jobs(s))
    assert not clerk.has_state(states.TRAVELS_WITH_YOU)
    slots = json.dumps(planned.build_plan(e, ACCEPT, res.outcomes))
    assert REFUSED not in slots and "indifferent" not in slots and "unmoved" not in slots


def test_the_employer_rule_holds_with_no_question_at_all(worlds):
    """The job's employer is never the plan's company on the turn the job is settled,
    whatever the question would say (`apply`'s employer rule) — and with no question an
    `other` stands behind no company either."""
    s, e, clerk = _the_save(worlds)
    rows, _week_card = _accept_rows(s, e, clerk)
    plan = [{"op": "company", "params": {"who": clerk.ref}}]
    notes: list[str] = []
    raw = acts_to_ops.apply(plan, rows, ACCEPT_READ, s, notes=notes)
    assert [r["op"] for r in raw] == ["job"]
    assert any("the reading's job is the turn's word on the employer" in n for n in notes)
    # And without the job: an `other` alone, unasked, carries no company.
    bare = acts_to_ops.company_asked(plan, ACCEPT_READ, s, ask=None)
    assert [r["op"] for r in bare] == ["narrate_only"]


# --- the real "come with me" still reaches the engine -----------------------------------------

TOWN_WORLD = load_cached("fixtures/pangrella-campaign.json")
TOWN = TOWN_WORLD.play["settlements"][0]["id"]
COME = "I ask Marra to come with me to the market"
COME_READ = {"question": False, "claims": [], "actions": [
    {"act": "request", "target": "Marra", "object": "to come with me to the market",
     "asks_for": "favour", "commit": "done", "span": "ask Marra to come with me to the market"}]}


def _friend(mood="friendly"):
    s = Scene(location_id=TOWN)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 40
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=TOWN_WORLD)
    e.place_party()
    who = instantiate("guildhand", scene=s, name="Marra")
    s.add(who)
    e.settle_attitude(who, mood, None, "test")
    return s, e, who


@pytest.mark.parametrize("answer", ["has them come along", None, ""])
def test_asking_somebody_to_come_along_still_brings_them(answer):
    """A deed that does ask somebody to come — confirmed by the question, or, with no
    question (`None`) or a failed call (`""`), a request done now — keeps the plan's
    company, and the engine grants the bond through the one applicator."""
    s, e, who = _friend()
    seen = []

    def ask(span, name):
        seen.append((span, name))
        return answer

    plan = [{"op": "company", "actor": "pc", "because": "she agrees to come",
             "params": {"who": who.ref}}]
    raw = acts_to_ops.company_asked(plan, COME_READ, s, ask=ask if answer is not None else None)
    assert [r["op"] for r in raw] == ["company"]
    if answer is not None:
        assert seen == [(COME_READ["actions"][0]["span"], "Marra")]
    _run(e, raw)
    assert who.has_state(states.TRAVELS_WITH_YOU)


def test_the_question_overrules_words_that_were_not_an_invitation():
    """A `talk` that only talks ("ask her about the road") does not carry the plan's
    company when the question says so; and a talk about coming along cannot carry a
    `leave` the words never said."""
    s, _e, who = _friend()
    talk = {"question": False, "claims": [], "actions": [
        {"act": "talk", "target": "Marra", "says": "what is the road like",
         "commit": "done", "span": "ask Marra what the road is like"}]}
    plan = [{"op": "company", "params": {"who": who.ref}}]
    got = acts_to_ops.company_asked(plan, talk, s, ask=lambda span, name: "something else")
    assert [r["op"] for r in got] == ["narrate_only"]
    leave = [{"op": "company", "params": {"who": who.ref, "do": "leave"}}]
    got = acts_to_ops.company_asked(leave, COME_READ, s,
                                    ask=lambda span, name: "has them come along")
    assert [r["op"] for r in got] == ["narrate_only"]


def test_words_only_intended_or_asked_about_bring_nobody():
    """Only a deed done or tried now moves the engine (`interpret.COMMITS`): "I might ask
    Marra to come along" is no invitation, and nobody is asked."""
    s, _e, who = _friend()
    frame = {"actions": [dict(COME_READ["actions"][0], commit="intended")]}
    asked = []
    got = acts_to_ops.company_asked([{"op": "company", "params": {"who": who.ref}}], frame,
                                    s, ask=lambda *a: asked.append(a) or "has them come along")
    assert [r["op"] for r in got] == ["narrate_only"] and not asked


def test_with_no_reading_the_plan_stands_alone():
    """As at every door of the table: no reading, nothing to stand behind or overrule
    with — the plan's company goes to the engine, which decides."""
    s, _e, who = _friend()
    plan = [{"op": "company", "params": {"who": who.ref}}]
    assert acts_to_ops.company_asked(plan, None, s) == plan
    assert acts_to_ops.company_asked(plan, {"error": "down"}, s) == plan


def test_the_question_is_asked_once_across_attempts():
    """`asked` memoises the answer: the plan loop's five attempts ask the same words about
    the same person once."""
    s, _e, who = _friend()
    calls = []
    memo: dict = {}
    plan = [{"op": "company", "params": {"who": who.ref}}]
    for _ in range(3):
        acts_to_ops.company_asked(plan, COME_READ, s, asked=memo,
                                  ask=lambda *a: calls.append(a) or "has them come along")
    assert len(calls) == 1


def test_the_question_offers_only_its_closed_answers(monkeypatch):
    """The sampler holds the answer to `COMPANY_ANSWERS`; anything else is a failed call,
    and the owner's own line is not among the demonstrations."""
    from gm import client, interpret

    sent = {}

    class _Reply:
        def json(self):
            return {"answer": "maybe"}

    def chat(messages, *a, schema=None, **k):
        sent["schema"], sent["messages"] = schema, messages
        return _Reply()

    monkeypatch.setattr(client, "chat", chat)
    assert interpret.confirm_company(ACCEPT, "Vyrnys") == ""
    assert sent["schema"]["properties"]["answer"]["enum"] == list(interpret.COMPANY_ANSWERS)
    shown = " ".join(m["content"] for m in sent["messages"][:-1])
    assert ACCEPT.lower() not in shown.lower() and "Vyrnys" not in shown


def test_the_planner_path_strikes_the_unasked_company(monkeypatch):
    """Row 7 through the real `plan_turn`, the model writing the prompt's own example:
    the company never reaches the engine, and the turn log says why."""
    from gm import agent as agent_mod
    from gm import interpret
    from _a_truth import MARKET, scene_at

    gm, _refs = scene_at(MARKET, [("Vyrnys", "guildhand")])
    vyrnys = next(a for a in gm.engine.scene.actors.values() if a.name == "Vyrnys")
    gm.engine.settle_attitude(vyrnys, "indifferent", None, "test")
    interpret.remember(ACCEPT, ACCEPT_READ)

    class _Reply:
        text = json.dumps({"narration": "", "intents": [
            {"op": "company", "params": {"who": vyrnys.ref}}]})
        seconds, model, prompt_tokens, reply_tokens, done_reason = 0.0, "stub", 0, 0, "stop"

        def json(self):
            return json.loads(self.text)

    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply())
    got = gm.plan_turn(ACCEPT, history=[])
    assert "company" not in [i.op for i in got.intents], got.rejections
    assert any("company of Vyrnys struck" in r for r in got.repairs), got.repairs
    res = gm.engine.run(got.intents)
    assert REFUSED not in " ".join(o.tell for o in res.outcomes)
