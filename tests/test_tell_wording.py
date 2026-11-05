"""Tells a 12B narrator cannot misread, and the pipeline defects one deed's two tells set
off (2026-11-04).

The owner, that day: "I want to have better narration. so lets make it work." The narration
diagnosis bench (docs/narration-diagnosis.md: 44 lines, 704 blind-scored beats, 0.20
errors a beat) found the errors systematic, and about a quarter of them were the tells' own
wording misread. Each test here names the mechanism it was measured as and what the page
said. Names and prose are synthetic; the bench's lines and saves stay in scratch.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from gm import acts_to_ops, judgement, narration, planned
from gm import beat_verify as bv
from rules import dc as dc_mod
from rules import harvest, trial
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.sheet import load_pc
from tests import test_narration_faithfulness as tf
from tests import test_trial as tt
from tests._places import stand_on


def _scene(biome: str = "forest"):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    stand_on(s, biome)
    return s


def _dead_wolf(s):
    wolf = s.add(instantiate("wolf", scene=s))
    wolf.hp = -20
    wolf.die("test")
    harvest.mark_the_dead(s)
    return wolf


# --- mechanism 1: one deed, two tells -------------------------------------------------------

def test_a_take_beside_a_harvest_of_the_same_carcass_is_the_harvest():
    """"I skin the wolf and take its pelt" was read `harvest: the wolf` then `take: its
    pelt, target: the wolf`; the take built a give from the wolf, refused as "the wolf has
    no pelt to take. Nothing changes hands." beside the harvest's own "peels the wolf pelt
    off the wolf" — 14% of the bench's errors traced to this chain. One deed, one op."""
    s = _scene()
    wolf = _dead_wolf(s)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "harvest", "target": "the wolf", "object": "the wolf", "commit": "done",
         "span": "skin the wolf"},
        {"act": "take", "target": "the wolf", "object": "its pelt", "commit": "done",
         "span": "take its pelt"}]}
    rows = acts_to_ops.table(frame, s)
    built = [i for r in rows for i in r.intents]
    assert [b["op"] for b in built] == ["harvest"], built
    assert built[0]["target"] == wolf.ref
    assert "with the harvest" in rows[1].note
    # The plan's own give of the pelt is dropped too: the reading named it and the table
    # moved nothing (`apply`'s `nothing` rule).
    plan = [{"op": "give", "actor": "pc", "params": {"item": "pelt", "to": "pc",
                                                     "from_": wolf.ref}}]
    kept = acts_to_ops.apply(plan, rows, frame, s)
    assert [k.get("op") for k in kept] == ["harvest"], kept


def test_a_take_from_somebody_else_beside_a_harvest_still_takes():
    """Only a take out of the carcass being harvested is folded."""
    s = _scene()
    _dead_wolf(s)
    rows = [acts_to_ops.Row(index=0, act="harvest"), acts_to_ops.Row(index=1, act="take")]
    rows[0].intents = [{"op": "harvest", "target": "c9", "params": {}}]
    rows[1].intents = [{"op": "give", "params": {"item": "rope", "from_": "c4", "to": "pc"}}]
    acts_to_ops._take_is_the_harvest(rows)
    assert rows[1].intents and rows[1].intents[0]["params"]["item"] == "rope"


def _o(tell, status="resolved", about=()):
    return SimpleNamespace(tell=tell, status=status, about=tuple(about))


def test_the_tells_check_never_judges_a_resolved_act_against_its_own_deeds_refusal(
        monkeypatch):
    """The second link of the chain: the harvest slot's true "You peel the pelt off the
    wolf" was flagged against the refused take, the remake could not agree with both, and
    the engine's line stood in. A refused tell about the very body a slot's resolved act
    was about (`Outcome.about`, refs) costs that slot nothing; the refused deed's own slot
    is still judged."""
    harvested = _o("Pell Arrow peels the wolf pelt off the wolf.", about=("c9",))
    refused = _o("the wolf has no pelt to take. Nothing changes hands.", "refused", ("c9",))
    out = tf._beat(("fact1", "You peel the pelt off the wolf in one long pull."),
                   ("fact2", "The wolf yields nothing more."))
    out.slots[0]["tells"] = [harvested.tell]
    out.slots[1]["tells"] = [refused.tell]
    asked = tf._remakes(monkeypatch)
    chat = tf._chat(tf._verdicts(("contradicts", "F2", "You peel the pelt off the wolf"),
                                 ("agrees", "F2", "")))
    planned._tells_kept(out, tf.WHO, tf._faith(chat), [harvested.tell, refused.tell],
                        refused=[refused.tell], outcomes=[harvested, refused])
    assert not asked and not out.remade
    assert out.slots[0]["wrote"] == "You peel the pelt off the wolf in one long pull."
    assert any("same deed" in n for n in out.notes)


def test_a_refusal_about_another_body_is_still_a_clash(monkeypatch):
    """The rule is the same deed, by ref — not any refusal."""
    harvested = _o("Pell Arrow peels the wolf pelt off the wolf.", about=("c9",))
    refused = _o("The tinker has no rope to take.", "refused", ("c4",))
    out = tf._beat(("fact1", "You take the tinker's rope and skin the wolf."))
    out.slots[0]["tells"] = [harvested.tell]
    asked = tf._remakes(monkeypatch, "You skin the wolf.")
    chat = tf._chat(tf._verdicts(("contradicts", "F2", "You take the tinker's rope")),
                    tf._verdicts(("agrees", "F1", "")))
    planned._tells_kept(out, tf.WHO, tf._faith(chat), [harvested.tell, refused.tell],
                        refused=[refused.tell], outcomes=[harvested, refused])
    assert asked and out.slots[0]["wrote"] == "You skin the wolf."


def test_an_outcome_says_which_bodies_its_deed_was_about():
    s = _scene()
    wolf = _dead_wolf(s)
    e = Engine(s, Dice(seed=3))
    out = e.run(e.validate([{"op": "give", "actor": "pc",
                             "params": {"item": "pelt", "to": "pc", "from_": wolf.ref}}],
                           origin="author:test")).outcomes[0]
    assert out.status == "refused" and out.about == (wolf.ref,)
    assert "about" not in out.as_dict(), "the turn log keeps the intent, not a copy"


def test_the_engines_own_line_about_a_corpse_is_not_the_corpse_acting():
    """The third link: the engine's harvest line stood in — "<the PC> peels the wolf pelt
    off the wolf. <the PC> cuts the sinew thread from the wolf." — and
    `cut_dead_men_walking` cut both as the dead wolf acting. The engine's own lines by a
    living actor, and a sentence the player's character opens, keep their corpse as the
    thing worked on."""
    line = "Pell Arrow peels the wolf pelt off the wolf."
    text = (f"{line} Pell Arrow cuts the sinew thread from the wolf. Pell Arrow gains 2 "
            f"mastery for the work.")
    kept, cut = narration.cut_dead_men_walking(
        text, ["the wolf"], engine_lines=[line], player_names=["Pell Arrow"])
    assert kept == text and cut == []
    # Each alone keeps its own sentence: the engine's line, and the player's name.
    _kept, cut = narration.cut_dead_men_walking(text, ["the wolf"], engine_lines=[line])
    assert cut == ["Pell Arrow cuts the sinew thread from the wolf."]
    _kept, cut = narration.cut_dead_men_walking(text, ["the wolf"],
                                                player_names=["Pell Arrow"])
    assert cut == []
    _kept, cut = narration.cut_dead_men_walking(text, ["the wolf"])
    assert len(cut) == 2, "before: both of the player's sentences cut as the wolf acting"
    # It still catches a corpse that acts.
    _kept, cut = narration.cut_dead_men_walking(
        "The wolf snarls and lunges at your throat.", ["the wolf"],
        engine_lines=[line], player_names=["Pell Arrow"])
    assert cut == ["The wolf snarls and lunges at your throat."]


def test_a_cut_in_the_middle_leaves_its_neighbours_apart():
    """"You gain 2 mastery for the work.You remain focused" — the cut sentence took the
    space in front of it, `_without` the space after it, and the page glued the two."""
    text = "You gain 2 mastery for the work. The wolf lifts its head. You remain focused."
    kept, cut = narration.cut_dead_men_walking(text, ["the wolf"])
    assert cut == ["The wolf lifts its head."]
    assert kept == "You gain 2 mastery for the work. You remain focused."
    kept, _ = narration.cut_dead_men_walking("The wolf lifts its head. You wait.",
                                             ["the wolf"])
    assert kept == "You wait."


# --- mechanism 4: made by nothing -----------------------------------------------------------

def test_a_check_made_by_nothing_is_said_made_only_just():
    """"makes the perception check by 0" was told as a failure (a trip "by 0" as the wolf
    still standing): 10% of the bench's errors. A total equal to the DC succeeds (CRB p.86)
    and is told so: "only just", never "by 0"."""
    assert dc_mod.by(3) == " by 3" and dc_mod.by(0) == ", only just"
    s = _scene()
    e = Engine(s, Dice(seed=1))
    probe = tt._run(e, {"op": "check", "actor": "pc", "because": "t",
                        "params": {"skill": "perception", "dc": 10}}, face=10)
    made = next(o for o in probe.outcomes if o.op == "check")
    bonus = made.margin
    res = tt._run(e, {"op": "check", "actor": "pc", "because": "t",
                      "params": {"skill": "perception", "dc": 10 + bonus}}, face=10)
    out = next(o for o in res.outcomes if o.op == "check")
    assert out.margin == 0 and out.verdict == "success"
    assert "only just" in out.tell and "by 0" not in out.tell, out.tell


# --- mechanism 6: the hour a wait ends at ---------------------------------------------------

def test_a_wait_says_the_hour_it_ends_at():
    """"696 minutes pass" — an overnight wait — was told "until the sun hangs in the
    afternoon sky": a count of minutes says no hour, and the narrator guessed one."""
    s = _scene()
    s.clock_minutes = 2 * 24 * 60 + 18 * 60 + 24          # day 3, 18:24
    e = Engine(s, Dice(seed=1))
    out = e.run(e.validate([{"op": "advance_time", "because": "t",
                             "params": {"amount": 696, "unit": "minute"}}])).outcomes[0]
    assert out.tell.startswith("11 hours 36 minutes pass: it is now early morning")
    assert "the next day" in out.tell and "696" not in out.tell, out.tell
    out = e.run(e.validate([{"op": "advance_time", "because": "t",
                             "params": {"amount": 1, "unit": "hour"}}])).outcomes[0]
    assert out.tell.startswith("1 hour passes: it is now"), out.tell
    assert "next day" not in out.tell


def test_a_wait_until_morning_is_one_wait_not_a_sleep_and_a_wait():
    """"I wait until morning" at 18:24: the plan wrote a night's rest AND the wait; the rest
    slept twelve hours and the wait ran 696 minutes on top — out at 17:36 the next day,
    which the narrator then wrote as afternoon. A rest no rest act of the reading owes goes."""
    s = _scene()
    s.clock_minutes = 2 * 24 * 60 + 18 * 60 + 24
    frame = {"question": False, "claims": [], "actions": [
        {"act": "wait", "time": "until morning", "until": "morning", "commit": "done",
         "span": "wait until morning"}]}
    raw = [{"op": "rest", "actor": "pc", "params": {"kind": "night"}},
           {"op": "advance_time", "params": {"amount": 1, "unit": "day"}}]
    notes: list = []
    got = acts_to_ops.timed_waits(raw, frame, s, notes=notes)
    assert [g["op"] for g in got] == ["advance_time"], got
    assert any("rest dropped" in n for n in notes)
    # The player's own rest act keeps the rest.
    frame["actions"][0]["act"] = "rest"
    frame["actions"].append({"act": "wait", "until": "morning", "commit": "done"})
    assert [g["op"] for g in acts_to_ops.timed_waits(raw, frame, s)] == \
        ["rest", "advance_time"]


# --- mechanism 10: whose it is, and who has it ----------------------------------------------

def test_a_theft_says_the_thief_has_it_and_whose_it_still_is():
    """"it is still theirs" (ownership) was told as never taken — "The bracelet remains in
    <the stallholder>'s possession despite your theft"."""
    s = _scene()
    man = s.add(instantiate("guildhand", scene=s, name="the tinker"))
    man.goods["copper ring"] = 1
    e = Engine(s, Dice(seed=1))
    out = e.run(e.validate([{"op": "give", "params": {"item": "copper ring",
                                                       "to": "pc"}}])).outcomes[0]
    pc = s.pc().name
    assert f"{pc} has it now; it still belongs to the tinker." in out.tell, out.tell
    assert "still theirs" not in out.tell


# --- mechanisms 9 and 11: the sentence still to come, and the choices -----------------------

def test_the_verdict_says_the_sentence_is_still_to_be_passed():
    """"The sentence for murder is death … Before it is passed, … may speak once more" came
    back "He informs you that you are sentenced to death by hanging"."""
    s, e, pc, g = tt._murderer()
    tt._wait(e)
    tt._wait(e)
    res = tt._check(e, "diplomacy", g.ref, face=1)
    t = tt._tells(res)
    assert "will pass sentence after" in t and "has not passed it yet" in t, t
    assert "the law's sentence will be death" in t
    assert f"Still for {pc.name} to choose: speak once more" in t


def test_choices_are_said_last_and_apart_in_one_form():
    """"A last chance: break their hold — slip it (Escape Artist) or wrench free … — and
    run, or fight. Or go to it." came back "You wrench your arms free". Every tell that
    offers ways out says them in `trial.choices`' form, after the facts."""
    assert trial.choices("Mira", ["run", "fight"]) == "Still for Mira to choose: run, or fight."
    s, e, pc, g, _ = tt._condemned()
    res = tt._wait(e)
    t = tt._tells(res)
    assert "hands held fast." in t and f"Still for {pc.name} to choose: slip their hold" in t
    assert "A last chance" not in t and "Or go to it" not in t


# --- 3: the dying -------------------------------------------------------------------------------

def test_a_harvest_of_a_body_that_still_breathes_is_the_killing_blow_first():
    """"I cut the dying bandit's throat" was read `harvest` and refused — "still breathing:
    nothing is cut from a living body". The engine's state says: down, not dead — a coup de
    grâce (CRB p.197), and the harvest only where the sheet could take parts."""
    s = _scene()
    wolf = s.add(instantiate("wolf", scene=s))
    wolf.hp = -2
    wolf.add_condition("dying")
    frame = {"question": False, "claims": [], "actions": [
        {"act": "harvest", "target": "the wolf", "commit": "done", "span": "skin the wolf"}]}
    built = [i for r in acts_to_ops.table(frame, s) for i in r.intents]
    assert [(b["op"], (b.get("params") or {}).get("coup_de_grace")) for b in built] == \
        [("attack", True), ("harvest", None)], built
    bandit = s.add(instantiate("bandit", scene=s, name="the bandit"))
    bandit.hp = -2
    bandit.add_condition("dying")
    frame["actions"][0].update(target="the bandit", span="cut the dying bandit's throat")
    built = [i for r in acts_to_ops.table(frame, s) for i in r.intents]
    assert [b["op"] for b in built] == ["attack"], "a bandit is no carcass to harvest"


def test_the_coup_de_grace_rides_the_plans_own_blow():
    """"I finish off the dying bandit with my longsword": the table built the coup de
    grâce, the plan's own attack at the bandit stood in its place without it, and the blow
    was an ordinary swing (on run 1, a hit that did not kill)."""
    s = _scene()
    bandit = s.add(instantiate("bandit", scene=s, name="the bandit"))
    bandit.hp = -2
    bandit.add_condition("dying")
    frame = {"question": False, "claims": [], "actions": [
        {"act": "attack", "target": "the dying bandit", "object": "my longsword",
         "commit": "done", "span": "finish off the dying bandit with my longsword"}]}
    rows = acts_to_ops.table(frame, s)
    acts_to_ops.victims(rows, frame, s)
    plan = [{"op": "attack", "actor": "pc", "target": bandit.ref,
             "params": {"weapon": "longsword", "full_attack": False}}]
    got = judgement.inject_fight(plan, "finish off the dying bandit", s, rows=rows,
                                 frame=frame)
    attacks = [g for g in got if g.get("op") == "attack"]
    assert len(attacks) == 1 and attacks[0]["params"]["coup_de_grace"] is True
    assert attacks[0]["params"]["weapon"] == "longsword"


def test_a_blow_at_a_body_already_down_moves_no_attitude():
    """"the bandit cools: wants you gone, and is past talking" was told of a dying bandit
    struck where he lay: a mind out cold sees nobody strike it."""
    s = _scene()
    s.clock_minutes = 12 * 60                     # noon: no dim-light miss chance
    bandit = s.add(instantiate("bandit", scene=s, name="the bandit"))
    bandit.hp = -1
    bandit.add_condition("dying")
    e = Engine(s, Dice(seed=2))
    # A pulled blow, so the bandit lives through it (the dead have no attitude anyway).
    res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": bandit.ref,
                             "params": {"lethality": "nonlethal"}}], origin="author:test"))
    faces = [15, 1, 1, 1]
    while res.awaiting:
        res = e.resume(faces.pop(0))
    effects = [f for o in res.outcomes for f in o.effects]
    assert any(f.get("kind") == "damage" for f in effects), "the blow landed"
    assert not bandit.has_state("state.down.dead")
    t = " ".join(o.tell for o in res.outcomes)
    assert not any(f.get("kind") == "attitude" for f in effects)
    assert "cools" not in t and "wants you gone" not in t, t


# --- the two oddities seen on the tells bench ---------------------------------------------------

def _sleep(s, until):
    e = Engine(s, Dice(seed=1))
    return e, e.run(e.validate([{"op": "rest", "actor": "pc", "because": "t",
                                 "params": {"kind": "night", "until": until}}])).outcomes[0]


def test_sleep_until_morning_said_in_the_morning_is_asked_not_a_day_gone():
    """"I go up to my room and sleep until morning" at 08:03: the next morning was 23 hours
    57 minutes off, so the engine kept the player awake 15 hours 57 minutes and slept the
    last eight — a day gone that the player never said, never told on the page (3 of 3
    runs). The time named came less than four hours ago (the clock, the engine's state):
    refused before a coin or a minute is spent, with the hour and the two readings said."""
    s = _scene()
    s.clock_minutes = 13 * 24 * 60 + 8 * 60 + 3          # 08:03
    purse = dict(s.pc().purse)
    e, out = _sleep(s, "until morning")
    assert out.status == "refused" and out.code == "already_then", out
    assert s.clock_minutes == 13 * 24 * 60 + 8 * 60 + 3 and s.pc().purse == purse
    assert "already come today" in out.tell and "about 8 in the morning" in out.tell
    assert f"Still for {s.pc().name} to choose: sleep now" in out.tell
    assert "wait until evening" in out.tell, "an answer the same rule will not refuse again"


def test_sleep_until_a_time_further_off_keeps_the_night_rule():
    """In the evening "until morning" sleeps to the morning; at noon (four hours after
    morning, no longer morning) the kept-awake rule of `_camp_for` stands as before."""
    s = _scene()
    s.clock_minutes = 13 * 24 * 60 + 20 * 60              # 20:00
    _e, out = _sleep(s, "until morning")
    assert out.status == "resolved" and "rests for 12 hours" in out.tell, out.tell
    s = _scene()
    s.clock_minutes = 13 * 24 * 60 + 12 * 60              # noon
    _e, out = _sleep(s, "until morning")
    assert out.status == "resolved" and "awake for 12 hours" in out.tell, out.tell


def test_a_body_searched_is_the_loot_not_a_forage_and_a_roll():
    """"I search the bandit's body" was read `loot` and the table built the loot; the
    plan's own `forage` and Survival check stood beside it — "1 hour of looking: … comes
    back with 2 Angelica", "makes the survival check by 14" — on 2 of 3 runs, a check on
    all 3. With nothing in the reading that gathers, looks, searches or tracks, they go."""
    s = _scene()
    bandit = s.add(instantiate("bandit", scene=s, name="the bandit"))
    bandit.hp = -20
    bandit.die("test")
    frame = {"question": False, "claims": [], "actions": [
        {"act": "loot", "target": "the bandit's body", "commit": "done",
         "span": "search the bandit's body"}]}
    rows = acts_to_ops.table(frame, s)
    plan = [{"op": "forage", "actor": "pc", "params": {}},
            {"op": "check", "actor": "pc", "params": {"skill": "survival",
                                                      "dc": {"band": "average"}}},
            {"op": "loot", "actor": "pc", "params": {"from_": bandit.ref}}]
    notes: list = []
    got = acts_to_ops.apply(plan, rows, frame, s, notes=notes)
    assert [g["op"] for g in got] == ["loot"], got
    assert sum("search a body" in n for n in notes) == 2
    # Dropped from the plan, the same check came back from the word injector, whose verbs
    # read "search" as Perception (live check, 2 of 2): folded after it too, and the
    # detector's check no longer declared to the plan's schema.
    from gm import interpret

    injected = judgement.inject_checks(got, "I search the bandit's body", s)
    assert [g["op"] for g in injected] == ["loot", "check"], "the premise"
    assert [g["op"] for g in acts_to_ops.loot_is_the_search(injected, frame, s)] == ["loot"]
    assert interpret.supported(["check", "loot"], frame) == (["loot"], ["check"])
    # A line that also looks around keeps the plan's look.
    frame["actions"].append({"act": "look", "commit": "done", "span": "look around"})
    got = acts_to_ops.apply(plan, acts_to_ops.table(frame, s), frame, s)
    assert "check" in [g["op"] for g in got]
    assert acts_to_ops.loot_is_the_search(got, frame, s) == got
