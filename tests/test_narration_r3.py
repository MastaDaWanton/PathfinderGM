"""Round 3 of the narration fixes, the three leftovers before 0.2.26 (2026-11-05).

docs/narration-diagnosis.md, "Round 3", records the bench. The final rerun of round 2 left
three things a reader would notice; one test (or a few) per defect, the measurement in the
docstring. Names are synthetic or the public fixture's; the bench's saves stay in scratch.

  1. spells: the attack of opportunity a cast provoked lost its blow facts across the
     player's damage roll, and the light check's rewrite moved a miss onto the wrong man;
  2. the gallows walk: a dead character offered "What do you do?", the road ahead and a
     shopping trip;
  3. the commission: the request told after the work it asked for, and the smith's reply
     answering as if the spoiled work were done.
"""
from __future__ import annotations

from types import SimpleNamespace

from gm import agent as agent_mod
from gm import narration, planned
from gm.checks import BeatContext, light_shown
from gm.narration import Finding
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene, _rehydrate
from rules.intents import claims_the_engine_backs, find_outcome_claims
from rules.sheet import load_pc
from tests import test_feats_computed as fc

from _a_truth import MARKET, scene_at


# --- 1a. the provoked blow keeps its facts across the damage roll ---------------------------

def _provoked_cast(seed):
    """A first-level wizard casting magic missile beside a thug, rolling her own damage:
    the thug's attack of opportunity resolves, the batch waits for the player's die, and
    resumes. (resolution outcomes, engine) — or None when the seed's blow downed her."""
    pc = fc._wizard()
    s, e = fc._board(pc, Dice(seed=seed))
    res = e.run(e.validate([{"op": "cast", "actor": "pc", "because": "she casts",
                             "visibility": "player",
                             "params": {"spell": "magic-missile", "at": "c1"}}]))
    if res.awaiting is None:
        return None
    done = e.resume(3)
    return done.outcomes, e


def test_the_provoked_blow_keeps_its_facts_across_the_players_damage_roll():
    """The final rerun of 2026-11-05: "the second robber hits <the caster> with the club for
    3 bludgeoning" was never told on burning hands run 3, nor the robber's 4 on magic
    missile run 4 (2 of the spell lines' 4 errors). Not the slot: the attack of opportunity
    the cast provoked was resolved before the damage roll, parked as a dict while the
    player rolled, and came back with no `blows` (`_rehydrate` dropped them) — so the
    spell's blow slot was handed THE BLOW of the spell alone, every time a cast provoked."""
    for seed in range(1, 60):
        got = _provoked_cast(seed)
        if got is None:
            continue
        outcomes, e = got
        aoo = [o for o in outcomes if o.op == "attack"]
        if aoo:
            break
    else:
        raise AssertionError("no seed provoked a blow and waited for the damage roll")
    assert aoo[0].blows and aoo[0].blows[0].get("ref") == "pc", aoo[0].as_dict()
    slot = next(x for x in planned.build_plan(e, "I cast magic missile at the thug", outcomes)
                if x["key"] == "fact1")
    # The thug's blow is a fact of the act beside the spell's own, as it was rolled.
    assert ("- HIT — the thug at you" in slot["say"]
            or "- MISS — the thug at you" in slot["say"]), slot["say"]
    assert "you at the thug" in slot["say"], slot["say"]


def test_an_outcome_round_trips_with_its_blows():
    """The round trip itself: everything `as_dict` emits comes back."""
    o = Outcome("i1", "attack", tell="the robber hits Mira H. with the club for 3.",
                actor="c2", blows=[{"result": "hit", "ref": "pc", "weapon": "club",
                                    "severity": "heavy", "left": "badly hurt"}])
    back = _rehydrate(o.as_dict())
    assert back.blows == o.blows and back.as_dict() == o.as_dict()
    assert _rehydrate(Outcome("i2", "cast").as_dict()).blows == []


# --- 1b. a light miss is never rewritten on a planned beat ----------------------------------

_MISS_TELL = "the robber finds nothing there — dim light, 20% miss chance (5)."
_DRAFT = ("The second robber's club connects with your body, but as you channel your will, a "
          "cone of searing flame erupts from your hands. The fire engulfs the robber. "
          "What do you do?")


def _light_ctx(text, *, at_you=True):
    pc = SimpleNamespace(ref="pc", name="Mira H.")
    scene = SimpleNamespace(pc=lambda: pc, said={}, in_encounter=True, actors={})
    miss = Outcome("i1", "attack", tell=_MISS_TELL, actor="c2",
                   blows=[{"result": "miss", "how": "unseen",
                           "ref": "pc" if at_you else "c9", "weapon": "club"}])
    return BeatContext(door="turn", text=text, player_text="", engine=None, scene=scene,
                       world=None, location=None, reading=None, outcomes=(miss,),
                       tells=(_MISS_TELL,), said=(), attribution=None, brief="",
                       brief_facts={}, pull=None, was_at="", acting="", turn=0,
                       planned=True)


def test_a_light_miss_on_a_planned_beat_is_backstopped_never_rewritten(monkeypatch):
    """Burning hands runs 1 and 3 of the final rerun, both scored errors: the light check's
    rewrite folded "the robber finds nothing there" into the sentence about the SECOND
    robber — "The second robber swings at a target lost in the gloom", over a sentence that
    had told his hit. Of the rerun's four `light-miss-unshown` findings on planned beats,
    the two rewrites kept were these two errors. The backstop names nobody, and says "at
    you" because the engine's record says the blow was at the player."""
    assert light_shown.PLANNED_NO_REWRITE == {"light-miss-unshown"}

    def no_model(*a, **k):
        raise AssertionError("a light miss on a planned beat was sent to the model")

    monkeypatch.setattr(agent_mod.client, "chat", no_model)
    ctx = _light_ctx(_DRAFT)
    found = light_shown.find(ctx)
    assert [f.kind for f in found] == ["light-miss-unshown"]
    stand_in = SimpleNamespace(engine=SimpleNamespace(scene=ctx.scene), _TRUTH_CALLS=3)
    out, notes, attempts = agent_mod.GMAgent._repair_sentences(stand_in, _DRAFT, found, ctx)
    assert attempts == []
    assert "The second robber's club connects with your body" in out
    assert any(line in out for line in light_shown.POOL["theirs:dim"]), out
    assert out.rstrip().endswith("What do you do?")


def test_a_light_miss_between_others_is_told_aside():
    out, _ = light_shown.backstop(_light_ctx(_DRAFT, at_you=False), _DRAFT, [])
    assert any(line in out for line in light_shown.POOL["aside:dim"]), out


# --- 2. the dead are offered nothing ----------------------------------------------------------

def _dead(pc):
    pc.hp = -100
    pc.apply_hp_state()
    assert pc.has_state("state.down.dead")


def _hanging_engine():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the master of the market"))
    return s, Engine(s, Dice(seed=3))


_HANGED = Outcome("", "trial", tell="At the market, with the town looking on, Kesst Vayr "
                                    "is hanged for murder. Kesst Vayr is dead.",
                  effects=[{"kind": "condition", "ref": "pc", "condition": "dead",
                            "origin": "rule:trial/execution"}])
_PULL = {"title": "Buy what you need for the road", "fact": "The way runs east.",
         "standing": "own"}


def test_a_beat_that_kills_the_player_ends_on_the_death():
    """The gallows walk, all 7 pages of the final rerun broken: the matter slot gave the
    hanged man "The road ahead leads through the east crossing" and "You have just enough
    coin to gather the supplies you need" (twice after a tells-check remake of that slot),
    and the aside had the master of the market "collecting the morning's fees". With the
    player's character dead the beat is the acts alone."""
    s, e = _hanging_engine()
    alive = [x["key"] for x in planned.build_plan(e, "I walk with them to the gallows",
                                                  [_HANGED], pull=_PULL)]
    assert "matter" in alive and "aside" in alive, alive
    _dead(s.pc())
    dead = [x["key"] for x in planned.build_plan(e, "I walk with them to the gallows",
                                                 [_HANGED], pull=_PULL)]
    assert dead == ["fact1"], dead
    assert planned.player_dead(e)


def test_the_closing_question_comes_off_a_dead_mans_page():
    """"You die for the crime of murder. What do you do?" (run 4) — `ensure_hand_back`
    added the question to every gallows page. Read off the page's shape: only a final
    unquoted question goes."""
    assert narration.drop_hand_back("You die. What do you do?") == ("You die.",
                                                                    "What do you do?")
    assert narration.drop_hand_back("You die.") == ("You die.", "")
    asked = "The hangman leans in. 'Any last words?'"
    assert narration.drop_hand_back(asked) == (asked, "")


def test_the_groom_hands_nothing_back_to_the_dead():
    agent, _ = scene_at(MARKET)
    out, _notes, _ = agent._groom("You are hanged at the market.", rewrite=False,
                                  claims=False, hand_back=True)
    assert out.endswith("What do you do?")
    _dead(agent.engine.scene.pc())
    out, notes, _ = agent._groom("You are hanged at the market. What do you do?",
                                 rewrite=False, claims=False, hand_back=True)
    assert out == "You are hanged at the market.", out
    assert any("dead" in n for n in notes), notes


def test_a_death_the_engine_dealt_backs_you_are_dead():
    """Run 5: the slot wrote "You are dead." after the hanging, and the outcome-claims
    repair rewrote it "You are breathless." — the row "states being hit" (you are … dead)
    had nothing in the record to back it. A `condition` effect of "dead" does."""
    backed = claims_the_engine_backs([_HANGED])
    assert find_outcome_claims("You are dead.", backed=backed) == []
    assert find_outcome_claims("You are dead.", backed=claims_the_engine_backs([])) != []


# --- 3. the commission: the request first, the reply knowing the work -----------------------

def _smithy():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    smith = s.add(instantiate("guildhand", scene=s, name="the smith"))
    return s, Engine(s, Dice(seed=3)), smith


def _commission_turn(smith_ref, *, spoiled=True):
    work = Outcome("i2", "commission", actor="pc",
                   tell=("The smith takes the work in hand and spoils it: the smith forges "
                         "pewter into the blank of a longsword, and the work is spoiled. "
                         "Missed by 6. No fee is asked for spoiled work, and no job is "
                         "taken: nothing is being made for Kesst Vayr.") if spoiled else
                   "The smith takes the job: a longsword will be ready in an hour.",
                   effects=[{"kind": "commission", "ref": "pc", "keeper": smith_ref,
                             "items": [], "spoiled": spoiled, "cp": 0}])
    work.about = (smith_ref,)
    say = Outcome("i3", "say", tell="Kesst Vayr speaks to the smith, to the effect that "
                                    "forge me a longsword. You are in conversation with "
                                    "the smith.",
                  effects=[{"kind": "said", "who": "", "to": smith_ref,
                            "words": "forge me a longsword."}])
    return [work, say]


_ONE_SPAN = {"question": False, "claims": [], "actions": [
    {"span": "ask the smith to forge me a longsword", "commit": "done", "act": "commission",
     "target": "the smith", "object": "a longsword"}]}


def test_the_request_is_told_before_the_work_it_asked_for():
    """"I ask the smith to forge me a longsword", the final rerun: the page told the smith
    spoiling the blank or taking the fee, and then "You look at the smith and request that
    they forge a longsword for you" — 7 of 7 runs (and the baseline's and round 1's alike),
    6 scored broken pages, "request told after the result; events told backwards". The
    reader read one `commission` span; the say was injected from its words and run last."""
    _s, e, smith = _smithy()
    slots = planned.build_plan(e, "I ask the smith to forge me a longsword",
                               _commission_turn(smith.ref), reading=_ONE_SPAN)
    facts = [x for x in slots if x["key"].startswith("fact")]
    assert "speaks to the smith" in facts[0]["say"], [x["say"][:60] for x in facts]
    assert "spoils it" in facts[1]["say"]
    assert "Show the player saying it, once, and stop there" in facts[0]["say"]


def test_speech_read_as_its_own_act_keeps_the_engines_order():
    """"I pay the smith and thank him": the thanks is speech the reader read on its own, so
    nothing moves (the order is the one the engine ran)."""
    _s, e, smith = _smithy()
    reading = {"question": False, "claims": [], "actions": [
        {"span": "ask the smith to make a blade", "act": "commission", "commit": "done"},
        {"span": "forge me a longsword", "act": "talk", "says": "forge me a longsword",
         "commit": "done"}]}
    slots = planned.build_plan(e, "x", _commission_turn(smith.ref), reading=reading)
    facts = [x for x in slots if x["key"].startswith("fact")]
    assert "spoils it" in facts[0]["say"]


def test_the_smiths_reply_knows_the_work_it_just_spoiled():
    """The same line's reply answered the request as if nothing had happened ("I can shape
    this for you", "I'll have it ready once I've hammered the shape true") or, on the
    made-up-work re-ask, as done: "It is finished. The metal is stubborn" (run 2). Re-asked
    with the recorded calls (4 spoiled runs × 4): the work told done, promised or held as a
    job 13 of 16 as recorded; 3-5 of 16 with the act's line and that no job is held — the
    words the commission's tell now ends on."""
    _s, e, smith = _smithy()
    reply = next(x for x in planned.build_plan(e, "I ask the smith to forge me a longsword",
                                               _commission_turn(smith.ref),
                                               reading=_ONE_SPAN)
                 if x["key"] == "reply")
    assert "The smith has just done this, as the engine decided it" in reply["say"]
    assert "Missed." in reply["say"] and "6" not in reply["say"]
    assert "no job is taken: nothing is being made for Kesst Vayr." in reply["say"]
    taken = next(x for x in planned.build_plan(e, "x", _commission_turn(smith.ref,
                                                                        spoiled=False))
                 if x["key"] == "reply")
    assert "has just done this" in taken["say"] and "no job" not in taken["say"]
    # Nobody else's act is carried: a reply from somebody the commission was not about.
    other = _commission_turn("c9")
    assert "has just done this" not in next(
        x for x in planned.build_plan(e, "x", other[:1] + [_commission_turn(smith.ref)[1]])
        if x["key"] == "reply")["say"]


def test_a_say_slot_that_told_the_ask_is_not_told_again():
    """Ask-road, runs 4 and 7 of round 2's replay: the say slot wrote "You turn to the horse
    dealer and ask what the road to Caelholt is like", the deed reader judged it unshown,
    and the deeds backstop (`_show_declared`) wrote the ask a second time. A speech deed
    whose say an act slot carries is that slot's to tell."""
    pc = SimpleNamespace(ref="pc")
    say = Outcome("i1", "say", tell="Kesst Vayr speaks to the horse dealer, to the effect "
                                    "that what the road is like.",
                  effects=[{"kind": "said", "who": "pc", "to": "c7", "words": "x"}])
    deeds = [{"act": "talk", "span": "ask the horse dealer what the road is like"},
             {"act": "give", "span": "hand him a coin"}]
    slots = ({"key": "fact1", "wrote": "You ask the horse dealer about the road.",
              "tells": [say.tell]},)
    kept, aside = agent_mod.said_by_its_slot(deeds, [say], slots, pc)
    assert kept == [deeds[1]] and aside == ["ask the horse dealer what the road is like"]
    # No say slot on the page (dropped, or none written): the backstop still owes it.
    assert agent_mod.said_by_its_slot(deeds, [say], (), pc) == (deeds, [])
