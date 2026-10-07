"""In progress: every craft's unfinished work, on the world clock, until it is collected
(rules/inprogress.py; docs/enchanting-contracts.md §8; docs/enchanting-revamp-plan.md §15).

The owner's rulings these pin (2026-10-05): finished work sits in the section until it is
collected (leatherworking Q9.3), and there is no limit to how much is in progress at once
(enchanting Round 4, point 5). Herbalism's steeping jar is the first user, moved over from a
silent lift that ran on every bench request. Each test names the defect it prevents.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from rules import crafting, inprogress
from rules.crafting import Stock, from_stock_dict
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict

# The herb bench's own fixture and helpers, so the steep below is the one the player makes.
from test_bench_api import (_c, _carry, _craft, _get, _key, _level, _pc, _post,  # noqa: F401
                            bench)

DAY = 1440
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def testcraft():
    """A craft that keeps its work at a place and can be stopped, registered for the test
    and taken away after, so the registry the app uses is left as it was."""
    seen = {"collected": [], "cancelled": []}

    def collect(item, actor):
        seen["collected"].append(item.name)
        return {"said": f"The {item.name} is done.",
                "product": {"key": "stock:x", "name": item.name}}

    def cancel(item, actor):
        seen["cancelled"].append(item.name)
        return {"said": f"You stop the {item.name}. The essences are spent."}

    inprogress.register("testcraft", collect=collect, cancel=cancel, icon="anvil",
                        stop_words="The vessel comes back unenchanted.")
    yield seen
    inprogress._CRAFTS.pop("testcraft", None)


def _board():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s, Engine(s, Dice(seed=4))


def _thing(pc, name="Longsword", **kw) -> str:
    item = Stock(base=name, count=1, craft="testcraft", kind="crafted", **kw)
    pc.stock[item.id] = item
    return item.id


# --- herbalism's pinned case, moved to the section ----------------------------------------

def test_a_tincture_is_not_collectable_on_day_13_and_is_on_day_14(bench):
    """Plan §6 / Q6 and plan §21.1 G: steeping is world time, two weeks for a tincture.
    Before 2026-10-05 the jar lifted itself on day 14 inside whatever bench request came
    next, with no tell and no collect; the owner's ruling is that it waits to be collected.
    Through the routes the player's page calls: the bench's steep, then api/works."""
    _level(2)
    _carry(mint=2, spirits=1)
    done = _craft(bench, "steep", [{"key": _key(bench, "Mint"), "count": 1},
                                   {"key": _key(bench, "Strong Spirits"), "count": 1}])
    jar = done["made"]
    assert jar["form"] == "tincture" and jar["ready_at"] is not None
    key = jar["key"].split(":", 1)[1]

    rows = _get(bench, "/api/works")["rows"]
    assert [r["key"] for r in rows] == [key] and rows[0]["state"] == "working"
    assert rows[0]["craft"] == "herbalist" and rows[0]["ready_words"] == "ready in 14 days"

    c = _c()
    c.scene.advance(13 * DAY, charge_body=False)
    refused = _post(bench, "/api/works/collect", {"key": key}, status=409)
    assert refused["error"].startswith(f"{_pc().stock[key].name} is not ready yet")
    fits = _post(bench, "/api/bench/check", {"method": "reduce", "items": []})["fits"]
    assert fits[jar["key"]].startswith("still steeping: ready on day")

    c.scene.advance(1 * DAY, charge_body=False)
    listing = _get(bench, "/api/works")
    assert listing["rows"][0]["state"] == "ready" and listing["rows"][0]["can_collect"]
    assert listing["summary"] == {"ready": 1, "working": 0, "next": None}
    # Ready is not collected: the bench still will not take it.
    fits = _post(bench, "/api/bench/check", {"method": "reduce", "items": []})["fits"]
    assert fits[jar["key"]].startswith("ready to collect")

    got = _post(bench, "/api/works/collect", {"key": jar["key"]})
    assert got["ok"] and got["product"]["key"] == jar["key"] and got["rows"] == []
    held = _pc().stock[key]
    assert held.work is None and not any(h in inprogress.HELD_WORDS for h in held.how)
    item = next(i for i in _get(bench, "/api/bench/state")["satchel"] if i["key"] == jar["key"])
    assert item["ready_at"] is None
    fits = _post(bench, "/api/bench/check", {"method": "reduce", "items": []})["fits"]
    assert not fits[jar["key"]].startswith(("still steeping", "ready to collect"))
    assert _c().transcript[-1]["text"].startswith("You take the")


def test_a_ready_jar_waits_until_it_is_collected_and_cannot_be_drunk():
    """The owner: "all the crafts sit before they can be collected". A month past its day
    the jar is still in the section, and the narrated door refuses it until it is collected
    — under the old lift a ready jar was on the shelf and drinkable with no collect at all."""
    scene, engine = _board()
    pc = scene.pc()
    scene.clock_minutes = 1000
    jar = Stock(base="Comfrey Tincture", count=1, effects=["x"], craft="herbalist",
                specs=[{"type": "heal", "amount": "1d4"}], form="tincture",
                ready_minute=1000 + 14 * DAY, how=["in_progress"],
                work=inprogress.block(craft="herbalist", label="Steeping",
                                      started=1000, minutes=14 * DAY))
    pc.stock[jar.id] = jar
    scene.advance(44 * DAY, charge_body=False)
    rows = inprogress.entries(pc, scene.clock_minutes)
    assert len(rows) == 1 and rows[0]["state"] == "ready"
    assert rows[0]["ready_words"].startswith("ready since day")

    def drink():
        return engine.run(engine.validate([{"op": "use_item", "actor": "pc", "params": {
            "item": jar.id, "how": "drink"}}])).outcomes[0]

    out = drink()
    assert "ready to collect" in out.tell and pc.stock[jar.id].count == 1
    assert inprogress.collect(pc, jar.id, now=scene.clock_minutes, here=pc.at)["ok"]
    drink()
    assert jar.id not in pc.stock


def test_the_clock_door_tells_a_finished_work_once():
    """Law 3 and plan §21.1 G: `Scene.advance` across the ready minute says "is ready to
    collect" once. Most of the clock's callers (a journey, the benches, the forge) drop
    `advance`'s return, so the line is buffered like the body's tolls and told at the end
    of the next engine batch; a second batch must not say it again."""
    scene, engine = _board()
    pc = scene.pc()
    scene.clock_minutes = 0
    inprogress.register("testcraft", icon="anvil")
    try:
        key = _thing(pc)
        assert inprogress.begin(pc, key, craft="testcraft", minutes=8 * 60, now=0,
                                label="Binding a +1 longsword")["ok"]
        assert scene.advance(7 * 60)["ready"] == []
        passed = scene.advance(2 * 60)
        assert [r["what"] for r in passed["ready"]] == ["Longsword"]
        assert scene.advance(60)["ready"] == []
        first = engine.run(engine.validate([{"op": "advance_time", "actor": "pc",
                                             "params": {"amount": 1, "unit": "minute"}}]))
        works = [o for o in first.outcomes if o.op == "works"]
        assert len(works) == 1 and works[0].tell == f"{pc.name}'s Longsword is ready to collect."
        assert works[0].effects[0]["origin"] == "rule:in-progress"
        again = engine.run(engine.validate([{"op": "advance_time", "actor": "pc",
                                             "params": {"amount": 1, "unit": "hour"}}]))
        assert not [o for o in again.outcomes if o.op == "works"]
        # Told is not collected: it is still there.
        assert inprogress.entries(pc, scene.clock_minutes)[0]["state"] == "ready"
    finally:
        inprogress._CRAFTS.pop("testcraft", None)


def test_the_tell_lands_behind_the_wait_that_finished_it():
    """Inside a batch the line follows the op whose hours finished the work, as the body's
    tolls do (`_drive`), rather than trailing every later op of the turn."""
    scene, engine = _board()
    pc = scene.pc()
    scene.clock_minutes = 0
    inprogress.register("testcraft")
    try:
        inprogress.begin(pc, _thing(pc), craft="testcraft", minutes=30, now=0, label="Binding")
        ops = [o.op for o in engine.run(engine.validate([{
            "op": "advance_time", "actor": "pc",
            "params": {"amount": 1, "unit": "hour"}}])).outcomes]
        assert ops.index("works") == ops.index("advance_time") + 1
    finally:
        inprogress._CRAFTS.pop("testcraft", None)


# --- places, stopping, limits ---------------------------------------------------------------

def test_work_left_at_a_place_is_collected_there_and_nowhere_else(testcraft):
    """Plan §15.3 and §21.1 G: a hide in the tannery's vat is collected at the tannery. With
    no `where` the section could not say why Collect was missing away from it."""
    pc = load_pc("fixtures/pc-kesst.json")
    key = _thing(pc, "Wolf Hide")
    inprogress.begin(pc, key, craft="testcraft", minutes=60, now=0, label="Tanning",
                     where="place:tannery", where_name="Brannoc's tannery")
    row = inprogress.entries(pc, 120, here="market")[0]
    assert row["where_words"] == "at Brannoc's tannery"
    assert not row["can_collect"] and row["why_not"] == "Collect at Brannoc's tannery"
    refused = inprogress.collect(pc, key, now=120, here="market")
    assert not refused["ok"] and refused["why"] == "Collect it at Brannoc's tannery."
    assert inprogress.entries(pc, 120, here="tannery")[0]["can_collect"]
    got = inprogress.collect(pc, key, now=120, here="tannery")
    assert got["ok"] and testcraft["collected"] == ["Wolf Hide"]
    assert got["said"] == "The Wolf Hide is done."


def test_stop_is_the_crafts_own_and_a_jar_cannot_be_stopped(testcraft):
    """Plan §15.3: each craft says what Stop means. A craft that registered no cancel (the
    herb bench: a steep cannot be hurried) is refused in words, never half-undone."""
    pc = load_pc("fixtures/pc-kesst.json")
    key = _thing(pc)
    inprogress.begin(pc, key, craft="testcraft", minutes=600, now=0, label="Binding")
    row = inprogress.entries(pc, 10)[0]
    assert row["can_stop"] and row["stop_words"] == "The vessel comes back unenchanted."
    got = inprogress.cancel(pc, key, now=10)
    assert got["ok"] and testcraft["cancelled"] == ["Longsword"]
    assert inprogress.work_of(pc.stock[key], 10) is None
    jar = Stock(base="Mint Tincture", craft="herbalist", form="tincture", ready_minute=100,
                how=["in_progress"],
                work=inprogress.block(craft="herbalist", label="Steeping", started=0,
                                      minutes=100))
    pc.stock[jar.id] = jar
    assert not inprogress.entries(pc, 10, craft="herbalist")[0]["can_stop"]
    assert inprogress.cancel(pc, jar.id, now=10) == {"ok": False,
                                                     "why": "Steeping cannot be stopped."}


def test_there_is_no_limit_to_what_is_in_progress(testcraft):
    """Owner, Round 4 point 5: "there should be no limit to how many things are crafting",
    in every craft. The plan had one binding at a time and a `limit` on the registry; a
    craft passing one now fails loudly with the ruling named, and thirty pieces of work run
    side by side."""
    with pytest.raises(ValueError, match="no limit"):
        inprogress.register("enchanter-test", limit=1)
    assert "enchanter-test" not in inprogress._CRAFTS
    pc = load_pc("fixtures/pc-kesst.json")
    for n in range(30):
        key = _thing(pc, f"Ring {n}")
        assert inprogress.begin(pc, key, craft="testcraft", minutes=60 + n, now=0,
                                label="Binding")["ok"]
    rows = inprogress.entries(pc, 0)
    assert len(rows) == 30 and [r["name"] for r in rows[:2]] == ["Ring 0", "Ring 1"]
    assert inprogress.summary(pc, 0)["working"] == 30


def test_rows_are_ready_first_then_soonest(testcraft):
    """UI plan §6.10, from what Stardew's players built for themselves: one list across
    every craft and place, ready first, then working by soonest."""
    pc = load_pc("fixtures/pc-kesst.json")
    for name, minutes in (("Late", 900), ("Soon", 300), ("Done", 60)):
        inprogress.begin(pc, _thing(pc, name), craft="testcraft", minutes=minutes, now=0,
                         label="Binding")
    rows = inprogress.entries(pc, 120)
    assert [(r["name"], r["state"]) for r in rows] == [
        ("Done", "ready"), ("Soon", "working"), ("Late", "working")]
    soon = rows[1]
    assert soon["ready_in"] == 180 and soon["ready_words"] == "ready in 3 hours"
    assert soon["fraction"] == 0.4 and soon["ready_day"] == 1
    assert "result" not in json.dumps(rows)


def test_a_fortnight_with_five_minutes_left_is_not_a_full_dial(testcraft):
    """Measured on the live check (2026-10-05): a tincture 5 minutes short of its 14 days
    was sent `fraction: 1.0`, a full dial on a row that still said "working"."""
    pc = load_pc("fixtures/pc-kesst.json")
    inprogress.begin(pc, _thing(pc), craft="testcraft", minutes=14 * DAY, now=0,
                     label="Steeping")
    row = inprogress.entries(pc, 14 * DAY - 5)[0]
    assert row["state"] == "working" and row["fraction"] < 1


def test_an_unregistered_craft_cannot_begin_work():
    """A craft that never registered would put work in the section nobody can collect."""
    pc = load_pc("fixtures/pc-kesst.json")
    with pytest.raises(ValueError, match="has not registered"):
        inprogress.begin(pc, _thing(pc), craft="nobody", minutes=60, now=0, label="Binding")


# --- saves ----------------------------------------------------------------------------------

def test_a_save_with_nothing_in_progress_round_trips_byte_for_byte():
    """Contracts §8.1: `work` and `magic` are written only when set. Had either been
    written as null, every save in the field would have become a different file the first
    time it was saved after this change."""
    raw = to_dict(load_pc("fixtures/pc-kesst.json"))
    pc = from_dict(json.loads(json.dumps(raw)))
    jar = Stock(base="Mint Infusion", craft="herbalist", form="infusion", quality=2)
    pc.stock[jar.id] = jar
    first = json.dumps(to_dict(pc), sort_keys=True)
    again = json.dumps(to_dict(from_dict(json.loads(first))), sort_keys=True)
    assert first == again
    assert "\"work\"" not in first and "\"magic\"" not in first


def test_work_in_progress_survives_a_save():
    """The block is on the Stock in the one store, so it saves with the pack; a store of
    its own would have needed a save field of its own, and the save is a hand-written list
    that has dropped whole stores before (docs/states-effects-tells.md)."""
    pc = load_pc("fixtures/pc-kesst.json")
    inprogress.register("testcraft")
    try:
        key = _thing(pc, magic={"enhancement": 1})
        inprogress.begin(pc, key, craft="testcraft", minutes=600, now=100, label="Binding",
                         result={"enhancement": 2})
        back = from_dict(json.loads(json.dumps(to_dict(pc))))
        item = back.stock[key]
        assert item.work["result"] == {"enhancement": 2} and item.magic == {"enhancement": 1}
        assert inprogress.end_of(item, 100) == 700
        assert "in_progress" in item.how
    finally:
        inprogress._CRAFTS.pop("testcraft", None)


def test_a_forged_vessel_keeps_its_block_through_a_save():
    """A forged record saves only its `record` (`ForgedStock.as_dict`), so a block kept on
    the Stock alone would have vanished from a binding on a forged sword at the first save."""
    from rules import forge_items
    from rules.sheet import _stock

    pc = load_pc("fixtures/pc-kesst.json")
    rec = {"id": "forged-longsword-1", "name": "Longsword", "gear": "weapon",
           "base": "longsword", "pieces": {"blade": {"material": "iron"}}}
    item = forge_items.stock_item(rec)
    pc.stock[item.id] = item
    inprogress.register("testcraft")
    try:
        inprogress.begin(pc, item.id, craft="testcraft", minutes=60, now=0, label="Binding")
        saved = {k: v.as_dict() for k, v in pc.stock.items()}
        assert saved[item.id]["work"]["label"] == "Binding"
        back = _stock(json.loads(json.dumps(saved)))[item.id]
        assert inprogress.state_of(back, 30) == "working"
        assert inprogress.collect(pc, item.id, now=60, here=None)["ok"]
        assert "work" not in pc.stock[item.id].as_dict()
    finally:
        inprogress._CRAFTS.pop("testcraft", None)


def test_an_old_steeping_jar_loads_into_the_section():
    """Plan §19: jars saved before the section (`how: ["steeping"]`, a `ready_minute`, no
    block) appear In progress, and past their minute load as ready — without being
    rewritten until something happens to them, so the save still reads back as it was."""
    old = {"base": "Mint Tincture", "craft": "herbalist", "form": "tincture", "quality": 2,
           "count": 3, "how": ["steeping"], "ready_minute": 20 * DAY}
    jar = from_stock_dict(old)
    as_saved = jar.as_dict()
    assert "work" not in as_saved and as_saved["how"] == ["steeping"]
    pc = load_pc("fixtures/pc-kesst.json")
    pc.stock[jar.id] = jar
    row = inprogress.entries(pc, 10 * DAY)[0]
    assert row["state"] == "working" and row["fraction"] == 0.286   # 4 of 14 days
    assert inprogress.entries(pc, 21 * DAY)[0]["state"] == "ready"
    assert from_stock_dict(as_saved).as_dict() == as_saved
    # The first settle after loading tells it, once, and writes it with its block.
    assert inprogress.settle(pc, 21 * DAY) == [jar.name]
    assert inprogress.settle(pc, 22 * DAY) == []
    assert jar.work["state"] == "ready" and jar.how == ["in_progress"]
    assert jar.id in pc.stock


def test_beginning_work_never_re_keys_a_jar():
    """A stepped jar's id carries a digest of its `ready_minute`. Had `begin` set the
    minute, the entry would sit under a key that is no longer its id and the next stack
    or take would miss it."""
    pc = load_pc("fixtures/pc-kesst.json")
    jar = Stock(base="Mint Infusion", craft="herbalist", form="infusion", quality=2)
    pc.stock[jar.id] = jar
    before = jar.id
    inprogress.begin(pc, before, craft="herbalist", minutes=60, now=0, label="Steeping")
    assert jar.id == before and jar.ready_minute is None


# --- one store, one door --------------------------------------------------------------------

def test_one_store_and_no_second_settle():
    """Law 2: no parallel store, no second ticker. The section reads `actor.stock` and
    keeps no rows of its own; the herb bench's silent `settle_steeping` is gone; no view
    settles (a view that did would swallow the tell the clock owes); and only
    `Scene.advance` calls `settle`."""
    assert not hasattr(crafting, "settle_steeping")
    # No clock of its own: the module never reads or writes a scene's clock (walked as an
    # AST, the way test_three_laws reads code); every function is handed `now`.
    tree = ast.parse(Path(inprogress.__file__).read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree)
                if isinstance(n, ast.Attribute) and n.attr == "clock_minutes"]
    module_state = [n for n, v in vars(inprogress).items()
                    if isinstance(v, (list, dict)) and not n.startswith("__")]
    assert module_state == ["_ALIASES", "_CRAFTS"], module_state
    callers = []
    for path in list((ROOT / "play").glob("*.py")) + list((ROOT / "rules").glob("*.py")) \
            + list((ROOT / "gm").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "inprogress.settle(" in text or "settle_steeping(" in text:
            callers.append(path.name)
    assert callers == ["engine.py"], callers


def test_the_enchanter_is_registered_whatever_was_imported_first():
    """Lane E: a binding collected before anything imported rules.enchanter fell back to
    a placeholder craft with no collect, lifted the block, and never wrote the layer —
    import order decided whether the sword was made. The registry asks for it, as it
    already asked for herbalism."""
    import subprocess
    import sys

    code = ("import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', "
            "'pathfindergm.settings'); django.setup(); "
            "from rules import inprogress; r = inprogress._registry(); "
            "print('enchanter' in r and 'alchemist' in r)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         stdin=subprocess.DEVNULL, timeout=120)
    assert out.stdout.strip().endswith("True"), out.stderr[-500:]
