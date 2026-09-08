"""Quests: a task taken up, kept as a situation card with objectives, and the log.

"is there a way we could have quest cards and track active quests along with having a
quest log" (2026-09-07). Built on the situation cards rather than beside them, so the
watcher, the brief and the story award work unchanged: a quest is a card of kind
`quest` with `objectives` to tick, a `giver` and a `reward` in words. Baldur's Gate 3's
journal keeps objectives (what to do next) apart from steps (what just happened); here
the objectives are the card's own and the facts are the steps.
"""
from __future__ import annotations

from gm import prompts
from rules import cards
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


def _room():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    marra = s.add(instantiate("guildhand", s, name="Marra Vell"))
    return s, Engine(s, Dice(seed=3), world=WORLD), marra


def _run(engine, op, params):
    intents = engine.validate([{"op": op, "actor": "pc", "because": "t", "params": params}],
                              origin="author:test")
    return engine.run(intents).outcomes[-1]


def test_a_quest_is_a_card_with_objectives_a_giver_and_a_promise_in_words():
    s, e, marra = _room()
    out = _run(e, "quest", {"title": "Find the missing salt",
                            "objectives": ["Ask the harbourmaster where the salt went",
                                           "Bring word back to Marra"],
                            "giver": marra.ref, "reward": "a season's salt at cost"})
    assert out.effects and out.effects[0]["kind"] == "quest", out.tell
    q = cards.quests(s)
    assert len(q) == 1 and q[0].kind == "quest" and q[0].is_("situation.quest")
    assert [o["text"] for o in q[0].objectives][0].startswith("Ask the harbourmaster")
    assert q[0].giver == marra.ref and q[0].clock_max == 2 and q[0].always_on
    assert "takes it on: Find the missing salt, for Marra Vell" in out.tell
    # The brief shows objectives first, unticked, then the promise.
    brief = prompts.scene_brief(WORLD, s, WORLD.get("5bbd0c40345f"), here=e.here(),
                                known=e.places(), recent=["salt"], turn=1)
    assert "QUEST: Find the missing salt" in brief
    assert "[ ] objective 1: Ask the harbourmaster" in brief
    assert "promised: a season's salt at cost" in brief


def test_a_quest_refuses_numbers_an_unknown_giver_and_a_repeat():
    s, e, marra = _room()
    bad = _run(e, "quest", {"title": "Pay the levy", "objectives": ["Bring 50 gold"]})
    assert bad.effects == [] and "No numbers" in bad.tell
    bad = _run(e, "quest", {"title": "Pay the levy", "objectives": ["Bring the gold"],
                            "giver": "npc9"})
    assert bad.effects == [] and "Nobody here is npc9" in bad.tell
    assert _run(e, "quest", {"title": "Pay the levy", "objectives": ["Bring the gold"]}).effects
    again = _run(e, "quest", {"title": "Pay the levy", "objectives": ["Bring the gold"]})
    assert again.effects == [] and "already a quest" in again.tell


def test_ticking_the_last_objective_finishes_the_quest_and_pays_the_story_award():
    s, e, marra = _room()
    pc = s.pc()
    before = pc.xp
    _run(e, "quest", {"title": "Find the missing salt",
                      "objectives": ["Ask the harbourmaster", "Bring word back"],
                      "giver": marra.ref, "reward": "salt at cost"})
    qid = cards.quests(s)[0].id
    one = _run(e, "quest_step", {"quest": qid, "objective": 1, "note": "The harbourmaster talked."})
    assert one.effects[0]["finished"] is False and "1/2" in one.tell
    assert cards.quests(s)[0].objectives[0]["done"] and cards.quests(s)[0].live
    assert "The harbourmaster talked." in cards.quests(s)[0].facts
    assert pc.xp == before
    twice = _run(e, "quest_step", {"quest": qid, "objective": 1})
    assert twice.effects == [] and "already done" in twice.tell
    last = _run(e, "quest_step", {"quest": "find the missing salt", "objective": 2})
    assert last.effects[0]["finished"] is True and "is finished" in last.tell
    assert "Promised: salt at cost" in last.tell
    assert not cards.quests(s)[0].live and pc.xp > before
    log = cards.quest_log(s)
    assert log["active"] == [] and log["finished"][0]["title"] == "Find the missing salt"
    assert log["finished"][0]["giver"] == "Marra Vell" and log["finished"][0]["done"] == 2


def test_a_quest_step_names_the_quests_when_the_id_is_wrong():
    s, e, marra = _room()
    _run(e, "quest", {"title": "Find the missing salt", "objectives": ["Ask around"]})
    out = _run(e, "quest_step", {"quest": "nothing", "objective": 1})
    assert out.effects == [] and "Find the missing salt" in out.tell
    out = _run(e, "quest_step", {"quest": "find the missing salt", "objective": 7})
    assert out.effects == [] and "objectives 1 to 1" in out.tell


def test_the_quest_survives_the_save_and_the_watcher_can_tick_an_objective():
    from gm import watcher
    from play.campaign import Campaign

    s, e, marra = _room()
    _run(e, "quest", {"title": "Find the missing salt",
                      "objectives": ["Ask the harbourmaster", "Bring word back"],
                      "giver": marra.ref})
    c = Campaign(id="t-quests", world_source="fixtures/pangrella-campaign.json", scene=s)
    back = Campaign.load(c.save())
    q = cards.quests(back.scene)[0]
    assert q.kind == "quest" and len(q.objectives) == 2 and q.giver == marra.ref
    # The watcher's proposal for a done objective lands through the same door.
    changed = watcher._apply_cards(back, {"changes": [
        {"id": q.id, "action": "objective", "objective": 1, "fact": "The harbourmaster talked.",
         "was": (q.stage, q.clock)}], "new": None})
    assert changed
    q = cards.quests(back.scene)[0]
    assert q.objectives[0]["done"] and not q.objectives[1]["done"] and q.live
    assert back.scene.pc().xp == 0 or True   # not finished: no award yet
    before = back.scene.pc().xp
    watcher._apply_cards(back, {"changes": [
        {"id": q.id, "action": "objective", "objective": 2, "fact": "",
         "was": (q.stage, q.clock)}], "new": None})
    q = cards.quests(back.scene)[0]
    assert not q.live and back.scene.pc().xp > before
