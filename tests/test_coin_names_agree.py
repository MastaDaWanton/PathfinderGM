"""Every line that names money names the coin the sheet names, for the same actor and place.

Measured live 2026-10-17 on a Pangrella save at Khalmorin's inn: the sheet's purse read
"12 Winged silver pieces" and the room's tell read "Kesst Vayr pays the one behind the
bar 5 Saltmakers' silver pieces for a room at the inn". **The room's tell said
Saltmakers' while the sheet said Winged** — and the narrator is fed the tells, so the
prose could name the other people's coin too.

Three answers were in the code for one purse. The sheet asked `coinage(world, the town)`;
the room charge, the purse taken in a fight, the give and the pick-up asked
`coinage(world, None)`, which falls to the world's first faction ("The Guild of
Saltmakers' Sons"); the buy, the sell, the loot, the work, the mend, the stable, the
trade panel and the narrator's own brief asked `coinage()`, the book's bare "silver
piece", and the buy and the sell priced in "1 gp" beside both. `goods.coins_here` is now
the one answer, and the ratchet at the bottom keeps a fourth from appearing.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from django.test import Client, override_settings

from gm import prompts
from rules import goods, keepers
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "b36e9f16214d"                                  # Khalmorin, where it was seen
INN = f"{TOWN}~urban:the-inn"     # the live one was founded; a generated inn bills alike
MARKET = f"{TOWN}~urban:the-market"
ROOT = Path(__file__).resolve().parent.parent

# "5 Saltmakers' silver pieces", "1 silver piece": a number, then the name up to the metal.
_COIN = re.compile(r"\b\d[\d,]* ((?:[^\s,.;()]+ )*?)(copper|silver|gold|platinum) pieces?\b")
_ABBREV = re.compile(r"\b\d[\d,]*(?:\.\d+)? (?:gp|sp|cp|pp)\b")


def _stem(coins) -> str:
    """What the coin is called before its metal: "Winged" in "Winged silver piece"."""
    return coins[1].name.rsplit(" silver piece", 1)[0]


def _names_in(text: str) -> set[str]:
    return {m.group(1).strip() for m in _COIN.finditer(text or "")}


def _assert_names(text: str, coins) -> None:
    said = _names_in(text)
    assert said, f"no coin named in {text!r}"
    assert said == {_stem(coins)}, (
        f"the tell named {sorted(said)} where the sheet names {_stem(coins)!r}: {text!r}")
    assert not _ABBREV.search(text), f"the book's abbreviation beside the coin: {text!r}"


def test_the_place_and_the_world_name_different_coins_here():
    """The precondition that makes the rest mean something: at Khalmorin the town's coin
    and the world's first faction's coin are different words, so a path that asked the
    wrong one shows up as a different name."""
    s = Scene(location_id=TOWN)
    assert _stem(goods.coins_here(WORLD, s)) != _stem(goods.coinage(WORLD, None))
    assert _stem(goods.coinage(WORLD, None)) == "Saltmakers'"


SETTLEMENTS = ("CITY", "TOWN", "VILLAGE", "HAMLET")


@pytest.mark.parametrize("path", ["fixtures/pangrella-campaign.json",
                                  "fixtures/aurvantis-campaign.json",
                                  "fixtures/synthetic-world.json"])
def test_a_towns_coin_is_named_by_the_nation_it_stands_in(path):
    """Measured 2026-10-17: all 12 of Pangrella's cities coined their money from the
    first word of a culture fact — "Winged nobility…" gave "Winged", "Clans, merchant
    guilds…" "Clans", "Four castes…" "Four", "Patrilineal clans…" "Patrilineal" — and a
    live transcript recorded "180 Clans gold pieces". Aurvantis's came out possessive
    ("Ardenhale's silver piece"). Golarion and the Realms name coin by the nation that
    strikes it; every settlement in every fixture world sits under one."""
    world = loader.load_cached(path)
    wrong = {}
    for e in world.entities.values():
        if e.kind not in SETTLEMENTS:
            continue
        nation = next((a for a in world.ancestors(e.id) if a.kind == "NATION"), None)
        assert nation is not None, e.name
        stem = _stem(goods.coinage(world, e))
        if stem not in nation.name.split() or stem.endswith("'s"):
            wrong[e.name] = (stem, nation.name)
    assert not wrong, wrong


# --- the engine's paths, each against the sheet's own answer -------------------------------

def _here(purse=None, at=INN):
    s = Scene(location_id=TOWN)
    if at == INN:
        s.at = at          # a founded inn, as on the live save (`test_inn_stay`)
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    pc.purse = dict(purse if purse is not None else {"sp": 12})
    s.clock_minutes = 10 * 60
    e = Engine(s, Dice(seed=3), world=WORLD)
    if at != INN:
        e.place_party(at)
    keeper = instantiate("thug", scene=s, name="the one behind the bar")
    keeper.world_entity_id = keepers.entity_id(s.at)
    keeper.at = s.at
    s.add(keeper)
    return s, pc, keeper, e


def _run(e, *raw, actor="pc"):
    """The outcome of the op asked for — not whatever the clock's door told after it."""
    res = e.run(e.validate([{"actor": actor, "because": "test", **r} for r in raw],
                           origin="author:test"))
    for _ in range(4):
        if not res.awaiting:
            break
        res = e.resume(15)
    want = raw[-1]["op"]
    return next(o for o in reversed(res.outcomes) if o.op == want)


def test_the_room_tell_names_the_coin_the_sheet_names():
    """The case seen live: a night at the inn, out of a purse of 12 silver."""
    s, pc, keeper, e = _here()
    out = _run(e, {"op": "rest", "params": {"kind": "night"}})
    assert "for a room" in out.tell, out.tell
    _assert_names(out.tell.split(" rests for")[0], goods.coins_here(WORLD, s))
    assert "Saltmakers'" not in out.tell


def test_a_room_the_purse_cannot_cover_names_the_same_coin():
    s, pc, keeper, e = _here(purse={"cp": 3})
    out = _run(e, {"op": "rest", "params": {"kind": "night"}})
    _assert_names(out.tell, goods.coins_here(WORLD, s))


def test_a_purchase_names_the_price_and_the_purse_in_the_sheets_coin():
    """The buy said "pays the stallholder 1 gp … (7 silver pieces left)": the book's
    abbreviation and the book's bare coin, beside a sheet in the town's."""
    s, pc, keeper, e = _here(purse={"gp": 3}, at=MARKET)
    out = _run(e, {"op": "buy", "params": {"item": "rope"}})
    assert out.status == "resolved", out.tell
    _assert_names(out.tell, goods.coins_here(WORLD, s))


def test_a_purchase_refused_for_want_of_coin_names_the_same_coin():
    s, pc, keeper, e = _here(purse={"cp": 2}, at=MARKET)
    out = _run(e, {"op": "buy", "params": {"item": "rope"}})
    _assert_names(out.tell, goods.coins_here(WORLD, s))


def test_coin_handed_over_and_a_price_paid_name_the_same_coin():
    """The give asked `coinage(world, None)` — the world's faction, Saltmakers'."""
    s, pc, keeper, e = _here()
    out = _run(e, {"op": "give", "target": keeper.ref,
                   "params": {"item": "sp", "count": 2, "to": keeper.ref, "from_": "pc"}})
    _assert_names(out.tell, goods.coins_here(WORLD, s))
    keeper.goods["lantern"] = 1
    out = _run(e, {"op": "give", "params": {"item": "lantern", "to": "pc",
                                            "from_": keeper.ref, "price": "1 sp"}})
    if _names_in(out.tell):
        _assert_names(out.tell, goods.coins_here(WORLD, s))


def test_a_days_work_names_the_pay_in_the_sheets_coin():
    s, pc, keeper, e = _here(at=MARKET)
    out = _run(e, {"op": "work", "params": {"days": 1}})
    _assert_names(out.tell, goods.coins_here(WORLD, s))


def test_the_narrators_brief_names_the_purse_as_the_sheet_does():
    """The brief said "HAS (fact): purse 12 silver pieces" — the book's coin — while the
    tells said Saltmakers' and the sheet said Winged."""
    s, pc, keeper, e = _here()
    brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN))
    line = next(x for x in brief.splitlines() if "HAS (fact): purse" in x)
    assert goods.purse_line(pc.purse, goods.coins_here(WORLD, s)) in line, line


# --- the sheet itself, through the page's own endpoint ---------------------------------------

@pytest.fixture
def at_the_inn(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import concurrency

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.location_id = TOWN
        c.scene.clock_minutes = 10 * 60
        c.engine().place_party(MARKET)
        c.scene.at = INN
        for a in c.scene.people.values():
            if a.is_pc or a.at == MARKET:
                a.at = INN
        c.scene.pc().purse = {"sp": 12}
        c.save()
        yield cm
        cm._LIVE.clear()


def test_the_sheet_and_the_room_tell_agree_on_one_campaign(at_the_inn):
    """End to end on one campaign: the coinage `/api/state` sends the sheet (what
    `purseLine` renders), against the tell the engine writes for the room."""
    state = Client().get("/api/state").json()
    sheet = {c["id"]: c for c in state["coinage"]}
    c = at_the_inn.current()
    s = c.scene
    keeper = instantiate("thug", scene=s, name="the one behind the bar")
    keeper.world_entity_id = keepers.entity_id(s.at)
    keeper.at = s.at
    s.add(keeper)
    e = c.engine()
    out = _run(e, {"op": "rest", "params": {"kind": "night"}}, actor=s.pc().ref)
    assert "for a room" in out.tell, out.tell
    assert f"5 {sheet['sp']['plural']}" in out.tell, (out.tell, sheet["sp"])
    assert "Saltmakers'" not in out.tell


def test_the_trade_panel_names_the_purse_as_the_sheet_does(at_the_inn):
    """The trade panel's purse line was `coinage()`: "12 silver pieces" in the panel
    beside "12 Winged silver pieces" on the sheet."""
    c = at_the_inn.current()
    c.engine().place_party(MARKET)
    c.save()
    state = Client().get("/api/state").json()
    sheet = {x["id"]: x for x in state["coinage"]}
    got = Client().post("/api/trade", data=json.dumps({"want": ""}),
                        content_type="application/json").json()
    assert got.get("purse") == f"12 {sheet['sp']['plural']}", got.get("purse")


# --- the ratchet -------------------------------------------------------------------------------

def _calls(name: str):
    for top in ("rules", "play", "gm"):
        for path in sorted((ROOT / top).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    fn = node.func
                    called = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                    if called == name:
                        yield path.relative_to(ROOT).as_posix(), node


def test_no_line_asks_for_coin_names_but_through_coins_here():
    """Fourteen calls asked `coinage` directly — five with no place, nine with nothing at
    all — and each was a door to a different name for the same purse. Only
    `goods.coins_here` may ask it now."""
    stray = [f"{p}:{n.lineno}" for p, n in _calls("coinage") if p != "rules/goods.py"]
    assert not stray, f"ask goods.coins_here(world, scene) instead: {stray}"


def test_every_purse_line_is_told_which_coin():
    """`purse_line(purse)` alone falls back to the book's bare names: the narrator's
    brief and the robbery's late tell both said "silver pieces" that way."""
    bare = [f"{p}:{n.lineno}" for p, n in _calls("purse_line")
            if p != "rules/goods.py" and len(n.args) + len(n.keywords) < 2]
    assert not bare, f"pass the coins from goods.coins_here: {bare}"


def test_the_engines_tells_price_in_the_coin_not_the_books_abbreviation():
    """The buy, the sell and the mend wrote "1 gp" in the same tell as "7 Winged silver
    pieces left". `pricing.as_text` stays for the panels' price columns; the tells say
    money through `_coin_text`."""
    stray = [f"{p}:{n.lineno}" for p, n in _calls("as_text") if p == "rules/engine.py"]
    assert not stray, stray
