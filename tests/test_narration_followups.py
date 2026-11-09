"""The follow-ups to the two narration fix lanes of 2026-11-04, and three owner rulings.

docs/narration-diagnosis.md holds the diagnosis and both lanes ("The tells lane", "The
plan's own patterns, fixed"); its last section, "The follow-ups", records these. One test
per defect, the measurement in the docstring:

  1. a coup de grâce in a fight, by the book (the owner, 2026-11-04): the reader's closed
     `blow`, the full round it costs, the attacks of opportunity it draws;
  2. a long wait heals nothing, and says the character stayed awake;
  3. working a body that still breathes kills it first, then skins it — through the engine;
  4. no whole-passage wrong-actor rewrite on a planned enemy turn;
  5. a tells-check remake on an enemy turn reaches the training log;
  6. an enemy turn after End turn gets THE SCENE;
  7. a say in words the player never wrote, when the reader read no words said.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from gm import acts_to_ops, interpret, judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.grid import Grid
from rules.sheet import load_pc


# --- 1. the coup de grâce in a fight -------------------------------------------------------

def _fight():
    """The player beside a dying bandit, with a second one standing at their shoulder."""
    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
    pc = s.add(load_pc("fixtures/pc-kesst.json"), at=(5, 5))
    pc.hp_max = 200
    pc.hp = 200                                # an attack of opportunity drops nobody here
    down = s.add(instantiate("thug", scene=s, name="the dying bandit"), at=(6, 5))
    standing = s.add(instantiate("thug", scene=s, name="the bandit"), at=(5, 6))
    down.hp = -3
    down.apply_hp_state()
    s.sides = {"us": ["pc"], "them": [down.ref, standing.ref]}
    s.initiative = [("pc", 20), (down.ref, 10), (standing.ref, 5)]
    s.round, s.turn = 1, 0
    # The standing bandit has had a turn: a creature that has not is flat-footed and
    # takes no attack of opportunity (CRB, Combat; enforced since 2026-11-08).
    s.acted = {standing.ref}
    return s, down.ref, standing.ref


def _run(s, raw, seed=11):
    e = Engine(s, Dice(seed=seed))
    return e.run(e.validate(raw))


def _coup(target):
    return {"op": "attack", "actor": "pc", "target": target, "because": "finish him",
            "visibility": "hidden", "params": {"weapon": "rapier", "coup_de_grace": True}}


def test_the_reader_holds_the_blow_to_a_closed_answer():
    """Before 2026-11-04 nothing told a killing stroke from a blow but a regex in the free
    door (`judgement.is_finishing_blow`), which knew "finish him off" and not "slit his
    throat". The attack act now carries `blow` (`interpret.BLOWS`), enforced by the
    sampler; probed live on gemma-4-12B heretic the same day: "I finish him off", "I slit
    the dying bandit's throat", "I put the wolf out of its misery" came back finishing,
    "I stab the bandit", "I kill the guard" ordinary."""
    schema = interpret.per_act_schema()
    alts = schema["properties"]["actions"]["items"]["anyOf"]
    attack = next(a for a in alts if a["properties"]["act"] == {"const": "attack"})
    assert attack["properties"]["blow"]["enum"] == list(interpret.BLOWS)
    assert "blow" in attack["required"]
    assert all("blow" not in a["properties"] for a in alts
               if a["properties"]["act"] != {"const": "attack"})
    assert "`blow` is finishing" in interpret._WHAT_EACH_IS
    # The demonstrations show both answers, and every attack carries one.
    demos = [json.loads(interpret._demo_reply(f)) for _s, f in interpret._DEMOS]
    blows = [a["blow"] for d in demos for a in d["actions"] if a["act"] == "attack"]
    assert "finishing" in blows and "ordinary" in blows
    # Kept only when it says something; anything else is the ordinary blow.
    line = "I slit the dying bandit's throat"
    for said, kept in (("finishing", "finishing"), ("ordinary", None), ("lethal", None)):
        frame, _ = interpret.ground({"actions": [
            {"act": "attack", "span": line[2:], "target": "the dying bandit",
             "blow": said}]}, line)
        assert frame["actions"][0].get("blow") == kept, said


def _built(frame, s):
    """What the act table builds for a reading, the blow table included (`victims`), as
    `GMAgent.plan_turn` runs them; and the rows, for `inject_fight`."""
    rows = acts_to_ops.table(frame, s)
    acts_to_ops.victims(rows, frame, s)
    return rows, [i for r in rows for i in r.intents]


def _reading(blow=None, target="the dying bandit"):
    a = {"act": "attack", "commit": "done", "span": "x", "target": target}
    if blow:
        a["blow"] = blow
    return {"question": False, "claims": [], "actions": [a]}


def test_finishing_words_at_a_helpless_foe_in_a_fight_are_the_coup_de_grace():
    """The owner's ruling: "I finish him off" at a helpless foe in a fight is a coup de
    grâce. The act table made every blow at a body on the floor inside a fight an ordinary
    swing at helpless AC (`victims`, 2026-10-09), whatever the words."""
    s, down, standing = _fight()
    _, built = _built(_reading("finishing"), s)
    assert [(b["target"], b["params"].get("coup_de_grace")) for b in built] == \
        [(down, True)], built


def test_an_ordinary_blow_at_a_helpless_foe_in_a_fight_stays_ordinary():
    """"I stab the dying bandit" in a fight: a blow at helpless AC, no full round spent."""
    s, down, _ = _fight()
    _, built = _built(_reading(None), s)
    assert [(b["target"], b["params"].get("coup_de_grace")) for b in built] == \
        [(down, None)], built


def test_finishing_words_at_a_foe_still_standing_are_an_ordinary_blow():
    """Helpless is the engine's state, never the reader's: "I finish him off" at the bandit
    still on his feet is a blow like any other."""
    s, _, standing = _fight()
    _, built = _built(_reading("finishing", "the bandit"), s)
    assert [(b["target"], (b.get("params") or {}).get("coup_de_grace")) for b in built] \
        == [(standing, None)], built


def test_out_of_a_fight_a_blow_at_the_helpless_is_still_the_coup_de_grace():
    """Unchanged: out of a fight no time is short, and any blow at the helpless is it."""
    s, down, standing = _fight()
    s.initiative, s.turn = [], -1
    s.remove(standing)
    _, built = _built(_reading(None), s)
    assert [(b["target"], b["params"].get("coup_de_grace")) for b in built] == \
        [(down, True)], built


def test_the_reading_decides_the_coup_not_the_regex_or_the_plan():
    """With a reading, the free door's regex stands down (`declare_coup_de_grace`), and a
    coup de grâce the PLAN wrote at a body the reading struck ordinarily in a fight is
    taken off it: since the ruling it costs the round and provokes, and the player's words
    decide that (the reader's closed answer), not the planner's guess."""
    s, down, _ = _fight()
    plan = [{"op": "attack", "actor": "pc", "target": down, "params": {}}]
    frame = _reading(None)
    assert judgement.declare_coup_de_grace(plan, "I finish him off", s, reading=frame) == plan
    # No reading: the regex door, as before.
    got = judgement.declare_coup_de_grace(plan, "I finish him off", s)
    assert got[0]["params"].get("coup_de_grace") is True
    rows, _ = _built(frame, s)
    planned = [{"op": "attack", "actor": "pc", "target": down,
                "params": {"coup_de_grace": True}}]
    notes: list = []
    out = judgement.inject_fight(planned, "I stab the dying bandit", s, rows=rows,
                                 frame=frame, notes=notes)
    blow = next(r for r in out if r.get("op") == "attack")
    assert "coup_de_grace" not in blow["params"], out
    assert any("ordinary blow the reading built" in n for n in notes)
    # And finishing words carry the table's coup onto the plan's own blow, in a fight too.
    frame = _reading("finishing")
    out = judgement.inject_fight([{"op": "attack", "actor": "pc", "target": down,
                                   "params": {}}], "I finish him off", s,
                                 rows=_built(frame, s)[0], frame=frame)
    assert next(r for r in out if r.get("op") == "attack")["params"]["coup_de_grace"]


def test_a_coup_de_grace_in_a_fight_provokes_and_takes_the_whole_round():
    """CRB p.197: "As a full-round action … Doing this provokes attacks of opportunity from
    threatening opponents." Before the ruling the engine charged a coup de grâce in a fight
    nothing: no swing from the bandit at the player's shoulder, and the round left over.
    Now the bandit's swing lands first, the blow is told as the whole round, and nothing
    else of the player's moves or strikes this round."""
    s, down, standing = _fight()
    res = _run(s, [_coup(down)])
    assert res.status == "complete"
    attacks = [o for o in res.outcomes if o.op == "attack"]
    assert [o.actor for o in attacks] == [standing, "pc"], [o.tell for o in attacks]
    coup = attacks[1]
    assert coup.status == "resolved", coup.tell
    assert "delivers a coup de grâce, which takes the whole round" in coup.tell
    victim = s.actors[down]
    # Dead outright, or the save the book gives at DC 10 + the damage, told either way.
    assert victim.has_state("state.down.dead") or "Fortitude" in coup.tell, coup.tell
    assert s.move_spent.get("pc") == s.round


def test_a_coup_de_grace_after_a_move_is_refused_and_draws_no_swing():
    """A full-round action leaves no move action before it (CRB p.187). Refused in words,
    and asked BEFORE the swing: a refused blow invents no opening (`_leaving_the_fight`'s
    rule, the reason the provocation is raised at the point of commitment)."""
    s, down, standing = _fight()
    s.move_spent["pc"] = s.round
    res = _run(s, [_coup(down)])
    assert [o.op for o in res.outcomes] == ["attack"]
    assert res.outcomes[0].status == "refused"
    assert "already moved this turn" in res.outcomes[0].tell
    assert "whole round" in res.outcomes[0].tell


def test_a_blow_behind_a_coup_de_grace_is_refused():
    """"I slit his throat and stab the other one": the coup took the round."""
    s, down, standing = _fight()
    res = _run(s, [_coup(down),
                   {"op": "attack", "actor": "pc", "target": standing, "because": "x",
                    "visibility": "hidden", "params": {"weapon": "rapier"}}])
    mine = [o for o in res.outcomes if o.op == "attack" and o.actor == "pc"]
    assert len(mine) == 2 and mine[0].status == "resolved"
    assert mine[1].status == "refused"
    assert "spent the whole round on the coup de grâce" in mine[1].tell


def test_a_coup_de_grace_at_a_foe_who_is_not_helpless_is_refused_without_a_swing():
    """The engine's own check (`coup_de_grace.refusal`), and no attack of opportunity
    drawn by a blow that was never going to be struck."""
    s, _, standing = _fight()
    res = _run(s, [_coup(standing)])
    assert [o.op for o in res.outcomes] == ["attack"]
    assert res.outcomes[0].status == "refused"
    assert "is not helpless" in res.outcomes[0].tell


# --- 2. a long wait heals nothing, and says so ----------------------------------------------

def _waiting(minutes, hurt=True):
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = 2 * 24 * 60 + 18 * 60 + 24          # day 3, 18:24
    if hurt:
        pc.hp = max(1, pc.hp_max - 4)
    before = pc.hp
    e = Engine(s, Dice(seed=1))
    out = e.run(e.validate([{"op": "advance_time", "because": "t",
                             "params": {"amount": minutes, "unit": "minute"}}])).outcomes[0]
    return out, before, pc


def test_a_long_wait_heals_nothing_and_says_the_character_stayed_awake():
    """The owner's ruling, 2026-11-04: only sleep heals and lifts fatigue (CRB, Natural
    Healing: "with a full night's rest"). The engine healed nothing on the bench's
    overnight wait (696 minutes) already; its tell said only the hour, and the baseline
    narrator wrote it as a night's healing sleep on 2 of 3 runs. Now the tell says it."""
    out, before, pc = _waiting(696)
    assert pc.hp == before, "a wait is not a night's rest"
    assert "stays awake the whole time and does not sleep" in out.tell, out.tell
    assert "no wound heals: only sleep does that" in out.tell, out.tell


def test_a_wait_unhurt_says_awake_and_promises_no_healing_of_nothing():
    out, _, _ = _waiting(696, hurt=False)
    assert "stays awake the whole time and does not sleep." in out.tell
    assert "heals" not in out.tell


def test_a_short_wait_says_nothing_of_sleep():
    """Nobody naps through an hour: the sentence is for a wait a narrator could take for a
    night in bed (`Engine.AWAKE_SAID_MINUTES`, four hours)."""
    out, _, _ = _waiting(60)
    assert "awake" not in out.tell and "sleep" not in out.tell


# --- 3. a body that still breathes is killed, then skinned ---------------------------------

def test_working_a_body_that_still_breathes_kills_it_then_skins_it():
    """The tells lane built the table (`acts_to_ops._harvest`: the coup de grâce first) and
    tested what the table builds; this runs it through the engine, out of a fight. Before
    the lane, "skin the wolf" at a wolf dying at -2 was refused whole — "still breathing:
    nothing is cut from a living body" — while the prose skinned it."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    wolf = s.add(instantiate("wolf", scene=s, name="the wolf"))
    wolf.hp = -2
    wolf.apply_hp_state()
    frame = {"question": False, "claims": [], "actions": [
        {"act": "harvest", "target": "the wolf", "commit": "done", "span": "skin the wolf"}]}
    built = [i for r in acts_to_ops.table(frame, s) for i in r.intents]
    for b in built:
        b.setdefault("visibility", "hidden")
    assert [b["op"] for b in built] == ["attack", "harvest"]
    res = _run(s, built, seed=4)
    coup = next(o for o in res.outcomes if o.op == "attack")
    assert "coup de grâce" in coup.tell and "whole round" not in coup.tell
    if wolf.has_state("state.down.dead"):
        harvest = next(o for o in res.outcomes if o.op == "harvest")
        assert "still breathing" not in harvest.tell, harvest.tell
    else:   # it made the save: the harvest is refused, said, never skinned alive
        assert "Fortitude" in coup.tell


# --- 4. no whole-passage wrong-actor rewrite on a planned enemy turn ------------------------

class _World:
    name, secret, premise, entities = "Testholme", "", {}, {}
    unwritten, chronology, factions = [], [], []

    def ancestors(self, _):
        return []


def test_a_planned_enemy_turn_gets_no_whole_passage_wrong_actor_rewrite(monkeypatch):
    """On the plan lane's bench (2026-11-04) the one scored error left in 16 planned enemy
    turns was written by `_repair_wrong_actor`, a free whole-passage rewrite: the turn's
    only tell was a refusal ABOUT the player ("Corvin T. has no ability called Booming
    Voice"), "you" was its true subject, the detector fired, and the rewrite invented.
    A planned turn is held to its tells slot by slot; the rewrite is not run on it, and
    what the detector saw is kept as a note."""
    from gm import agent as agent_mod
    from gm import client, prompts
    from rules import houserules

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    guard = s.add(instantiate("thug", scene=s, name="Pallo Farrow"))
    s.initiative = [(r, 10) for r in s.actors]
    s.turn = 0
    engine = Engine(s, Dice(seed=3))
    gm = agent_mod.GMAgent(_World(), engine)
    asked = []

    def chat(messages, model, *a, **kw):
        asked.append(messages)
        return client.Reply(json.dumps({"text": "You have no such power to call on."}),
                            0.1, model)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    monkeypatch.setattr(houserules, "narration", lambda: "planned")
    tell = "Kesst Vayr has no ability called Booming Voice."
    text, attempt = gm.narrate_outcome(
        "", [Outcome("i1", "use_ability", status="refused", tell=tell, actor=guard.ref)],
        "Pallo Farrow acts", rewrite=False, acting="Pallo Farrow")
    assert not any(prompts.ACTOR_REPAIR_BRIEFING in str(m) for m in asked), \
        "the whole-passage rewrite ran on a planned turn"
    assert "no such power" in text
    assert "wrong actor seen" in (attempt.note or ""), attempt.note


# --- 5. an enemy turn's remakes reach the training log -------------------------------------

def test_a_remake_on_an_enemy_turn_is_logged_for_training(monkeypatch, tmp_path, settings):
    """The owner asked for narration corrections to be logged for training (2026-11-02).
    Only the player's beat set `last_tells_remade`; the tells check remade 2 enemy slots
    across the plan lane's 16 bench turns, one a "graze your skin" from no word of ours,
    and neither reached `training/auto-corrections.jsonl`. The turn's own input is the
    record's: its plan, its slots, its brief and its tells."""
    from gm import agent as agent_mod
    from gm import planned
    from play import views
    from rules import houserules

    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    wolf = s.add(instantiate("wolf", scene=s, name="the wolf"))
    s.initiative = [(r, 10) for r in s.actors]
    s.turn = 0
    gm = agent_mod.GMAgent(_World(), Engine(s, Dice(seed=3)))
    gm.last_brief = "WHERE: the road"
    remade = [{"slot": "fact1", "passed": True, "prompt": [{"role": "user", "content": "p"}],
               "rejected": "The wolf's teeth graze your skin.", "remade": "The wolf snaps "
               "at empty air.", "clashes": [{"words": "graze your skin",
                                             "tell": "the wolf misses you"}]}]
    beat = SimpleNamespace(text="The wolf snaps at empty air.", remade=remade, faith=[],
                           messages=[{"role": "system", "content": "plan"}],
                           slots=[{"key": "fact1", "wrote": "The wolf snaps at empty air.",
                                   "messages": [{"x": 1}], "reply": "{}"}],
                           model="stub", calls=[], notes=[])
    monkeypatch.setattr(planned, "write", lambda *a, **k: beat)
    monkeypatch.setattr(houserules, "narration", lambda: "planned")
    tells = [Outcome("i1", "attack", verdict="miss", tell="the wolf misses Kesst Vayr.",
                     actor=wolf.ref)]
    assert gm._narrate_turn_planned("", tells, "the wolf", "", "") is not None
    assert gm.last_turn_written["remade"] == remade
    c = SimpleNamespace(id="synthetic", turn_log=[],
                        transcript=[{"who": "gm", "kind": "setup",
                                     "text": "The wolf snaps at empty air."}])
    assert views._log_turn_remakes(c, gm, 0, "the wolf acts",
                                   [o.tell for o in tells]) == 1
    line = json.loads((tmp_path / "training" / "auto-corrections.jsonl")
                      .read_text(encoding="utf-8"))
    assert line["kind"] == "tells-check" and line["label"] == "pair"
    assert line["rejected"] == "The wolf's teeth graze your skin."
    assert line["input"]["scene_brief"] == "WHERE: the road"
    assert line["input"]["player_input"] == "the wolf acts"
    assert line["input"]["messages"] == [{"role": "system", "content": "plan"}]
    assert line["input"]["facts"] == ["the wolf misses Kesst Vayr."]
    # A turn with nothing remade writes nothing.
    gm.last_turn_written = dict(gm.last_turn_written, remade=[])
    assert views._log_turn_remakes(c, gm, 0, "x", []) == 0


# --- 6. THE SCENE after End turn --------------------------------------------------------------

def test_an_enemy_turn_after_end_turn_is_briefed(monkeypatch, tmp_path, settings):
    """A turn ended with End turn and nothing declared builds a fresh agent, and every
    enemy slot was asked with an empty "THE SCENE (reference; the only things that
    exist):" — the plan lane's bench. `_run_npc_turns` now gives an agent with no brief
    the player's turn's own (`prompts.scene_brief`), before the first creature acts."""
    from django.test import override_settings

    from play import campaign as cm
    from play import views
    from rules import houserules

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        thug = instantiate("thug", scene=c.scene, name="the thug")
        c.scene.add(thug)
        e = c.engine()
        e.run(e.validate([{"op": "begin_encounter",
                           "params": {"sides": {"pc": ["pc"], "them": [thug.ref]}}}]))
        seen = {}

        class _Agent:
            engine = None

            def npc_turn(self, ref, **k):
                seen["brief"] = getattr(self, "last_brief", "")
                raise views.ModelUnavailable("stop here")

        monkeypatch.setattr(houserules, "narration", lambda: "planned")
        monkeypatch.setattr(judgement, "default_npc_action", lambda scene, ref: None)
        views._run_npc_turns(c, _Agent(), limit=1)
        assert seen.get("brief", "").startswith("WORLD: "), seen
        assert "WHEN (fact):" in seen["brief"]
        # Free narration writes no planned slot, and is left as it was.
        monkeypatch.setattr(houserules, "narration", lambda: "free")
        seen.clear()
        views._run_npc_turns(c, _Agent(), limit=1)
        assert seen.get("brief") == ""
        cm._LIVE.clear()


# --- 7. words the player never wrote, when the reader read none said -------------------------

def test_a_say_with_the_deed_in_it_is_struck_when_the_reader_read_no_words_said():
    """The commission's "agree" line, run 3 of the plan lane's bench: "I agree to his price
    and pay" was read `sell` + `give` — no words said — and the PLAN wrote the say "I agree
    to your price. Here is the payment."; 2 of its 3 content words were the player's, so it
    passed `own_words_only` at half, and the say slot told the payment as spoken while the
    engine refused it ("pays nothing more"). With a reading that names no words said, a
    say must be the line's own words throughout."""
    line = "I agree to his price and pay"
    reading = {"question": False, "claims": [], "actions": [
        {"act": "sell", "commit": "done", "span": "agree to his price", "target": "his"},
        {"act": "give", "commit": "done", "span": "pay"}]}
    plan = [{"op": "say", "actor": "pc", "target": "c6",
             "params": {"words": "I agree to your price. Here is the payment."}},
            {"op": "commission", "actor": "pc", "params": {}}]
    notes: list = []
    out = judgement.own_words_only(plan, line, reading, notes=notes)
    assert [r["op"] for r in out] == ["commission"], out
    assert any("Here is the payment" in n for n in notes)
    # Words wholly the player's still stand.
    kept = judgement.own_words_only(
        [{"op": "say", "actor": "pc", "params": {"words": "I agree to your price."}}],
        line, reading)
    assert kept[0]["params"]["words"] == "I agree to your price."
    # A reading with words said, or no reading at all, keeps the measured half.
    talk = {"actions": [{"act": "talk", "commit": "done", "says": "agree to his price"}]}
    assert judgement.own_words_only(plan, line, talk)[0]["op"] == "say"
    assert judgement.own_words_only(plan, line, None)[0]["op"] == "say"
