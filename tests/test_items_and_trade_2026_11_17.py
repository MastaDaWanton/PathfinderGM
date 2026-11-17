"""Items, containers and typed trade: playtest 2026-11-17 #11-#19, #41, #42, #45, #48, and
the 2026-11-16 N2/N3 items. Each test replays the reader's own frame for the line (logged
in the vesna-kroll save's turn rows, or read live on the lane, 2026-11-17) against the
engine's finders, so what is pinned is what the reading does with the sentence.
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, interpret, judgement
from rules import goods, holding, trade
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture(autouse=True)
def _no_readings(monkeypatch):
    monkeypatch.setattr(interpret, "_READINGS", {})


def _scene(*names):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    for name in names:
        s.add(instantiate("guildhand", scene=s, name=name))
    return s


def _bought(scene, key, n=1):
    goods.deliver(scene, scene.pc(), goods.good(key), n)


def _frame(*actions):
    return {"question": False, "actions": [dict(a) for a in actions], "claims": []}


def _turn(scene, frame, plan=None):
    rows = acts_to_ops.table(frame, scene)
    raw = acts_to_ops.apply(list(plan or [{"op": "narrate_only"}]), rows, frame, scene)
    return rows, acts_to_ops.order(raw, rows)


def _run(scene, raw):
    engine = Engine(scene, Dice(seed=1))
    return engine.run(engine.validate(raw)).outcomes


def _ops(raw):
    return [r.get("op") for r in raw if isinstance(r, dict)]


# --- a carried torch, lit by the player's own words -----------------------------------------

@pytest.mark.parametrize("said", ["a torch", "one of my torches", "my torch"])
def test_lighting_a_carried_torch_lights_it(said):
    """Playtest 2026-11-17 #13 and #15: "I light a torch" built no op and the page lit it
    anyway; "I light one of my torches", three on the shelf, was refused "There is no one
    of my torches here". Both are the torch on the shelf, lit through `use_item`."""
    scene = _scene()
    _bought(scene, "torch", 3)
    pc = scene.pc()
    sid = holding.stock_key(pc.stock, "torch")
    _rows, raw = _turn(scene, _frame({"act": "use", "object": said}),
                       plan=[{"op": "use_item", "params": {"item": "torch", "how": "light"}}])
    assert _ops(raw).count("use_item") == 1, raw      # the plan's own copy is not a second
    out = _run(scene, raw)
    lit = next(o for o in out if o.op == "use_item")
    assert lit.status == "resolved", lit.tell
    assert pc.stock[sid].count == 2


def test_a_partitive_names_the_thing_carried():
    """#15's root: `holding.plain` left "one of my torches" whole, and `same` made "torches"
    "torche" (`rstrip("s")`), so no torch on the shelf was ever "one of my torches"."""
    assert holding.plain("one of my torches") == "torches"
    assert holding.same("one of my torches", "torch")
    assert holding.same("a couple of the boxes", "box")


def test_flint_and_steel_on_the_shelf_is_carried():
    """Playtest 2026-11-17 #19: "strike my flint and steel" was refused "Vesna Kroll has no
    flint and steel" with one bought an hour earlier: `Engine.unrecorded_thing` asked only
    `goods`, and bought gear is filed on the shelf (`goods.deliver`)."""
    scene = _scene()
    _bought(scene, "flint and steel")
    engine = Engine(scene, Dice(seed=1))
    assert not engine.unrecorded_thing("my flint and steel", scene.pc())
    # #45: a stance naming a carried torch is not a thing missing from the room.
    _bought(scene, "torch")
    assert not engine.unrecorded_thing("torch in one hand and dagger in the other",
                                       scene.pc())


def test_taking_a_torch_out_of_my_pack_moves_nothing():
    """Playtest 2026-11-17 #18: "take a torch out of my pack" built a pick-up that was
    refused "a torch is not here: it lies at the market". Out of the player's own pack is
    already carried; the plan's own pick-up of it goes too."""
    scene = _scene()
    _bought(scene, "torch", 2)
    scene.place_prop("a torch", state="intact", turn=0)
    scene.props[-1]["at"] = "elsewhere"
    rows, raw = _turn(scene, _frame({"act": "take", "object": "a torch",
                                     "target": "my pack"}),
                      plan=[{"op": "give", "params": {"item": "torch", "to": "pc"}}])
    assert rows[0].note == "a torch is already carried"
    assert "give" not in _ops(raw)


# --- a container opened, looked into and emptied --------------------------------------------

def _box_here(scene, gp=50):
    scene.props.append({"name": "a gaoler's box", "owner": "", "state": "intact", "turn": 0,
                        "at": scene.at, "contents": {"purse": {"gp": gp}, "goods": {}}})


def test_looking_into_a_box_tells_what_is_inside():
    """Playtest 2026-11-17 #41: "I open the gaoler's box and see what's inside" was a bare
    narrate_only, and the prose pried the lid and never said — 50 gp on the record."""
    scene = _scene()
    _box_here(scene)
    _rows, raw = _turn(scene, _frame({"act": "other", "object": "the gaoler's box"},
                                     {"act": "look", "object": "what's inside"}))
    looks = [r for r in raw if (r.get("params") or {}).get("looks_in")]
    assert len(looks) == 1
    out = _run(scene, raw)
    told = " ".join(o.tell for o in out)
    assert "Inside: 50 gold" in told, told


def test_taking_everything_in_a_box_empties_it():
    """Playtest 2026-11-17 #42: "I take everything that's in the gaoler's box" was answered
    "'everything' is a word, not a thing", logged resolved, and the 50 gp stayed put."""
    scene = _scene()
    _box_here(scene)
    pc = scene.pc()
    before = goods.in_copper(pc.purse)
    _rows, raw = _turn(scene, _frame({"act": "take", "object": "everything",
                                      "target": "the gaoler's box"}))
    out = _run(scene, raw)
    give = next(o for o in out if o.op == "give")
    assert "empties" in give.tell
    assert goods.in_copper(pc.purse) - before == 5000
    assert holding.coin_in(scene.props[-1]) == 0


def test_a_take_beside_its_give_writes_no_take_off():
    """Playtest 2026-11-17 #48: beside the give of the cargo chest's coin the plan wrote a
    `take_off` that told "is wearing nothing called cargo_chest_coins" — an op nobody
    asked for, and a planner's id on the page."""
    scene = _scene()
    _box_here(scene)
    _rows, raw = _turn(scene, _frame({"act": "take", "object": "the coin",
                                      "target": "the gaoler's box"}),
                       plan=[{"op": "take_off", "params": {"item": "cargo_chest_coins"}}])
    assert "take_off" not in _ops(raw)


# --- coin is never used ---------------------------------------------------------------------

def test_coin_is_never_used():
    """Playtest 2026-11-16 N2: beside a temple purchase the plan wrote `use_item gold
    piece`, refused into "she has no gold" with 12 gp in her purse."""
    scene = _scene()
    _rows, raw = _turn(scene, _frame({"act": "buy", "object": "a cure light wounds",
                                      "target": "the priest"}),
                       plan=[{"op": "use_item", "params": {"item": "gold piece"}}])
    assert "use_item" not in _ops(raw)
    kept = judgement.strip_counter_buys(
        [{"op": "use_item", "params": {"item": "gold piece"}}], "I buy a healing potion")
    assert kept == []


# --- the counter: a list, an offer, the general store's shelf ------------------------------

def test_a_shopping_list_picks_each_thing_the_counter_has():
    """Playtest 2026-11-17 #11: "buy a few torches, a flint and steel, a healer's kit, and
    a couple of potions of cure light wounds" matched no one shelf row, and nothing was
    picked. Each thing the shelf has is (#12: the healer's kit is on it now)."""
    from rules import market

    shelf = market.staples_of("market:general")
    got = [g.id for g in goods.wants_among(
        "a few torches, a flint and steel, a healer's kit, and a couple of potions of cure "
        "light wounds", shelf)]
    assert got == ["gear:torch", "gear:flint and steel", "gear:healer's kit"]


def test_the_general_store_sells_the_book_adventuring_gear():
    """Playtest 2026-11-17 #12: a city general store's 49 wares had Alum and Rennet but no
    healer's kit, sunrod or antitoxin (CRB Table 6-9, Adventuring Gear and Special
    Substances and Items)."""
    from rules import market

    ids = {g.id for g in market.staples_of("market:general")}
    assert {"gear:healer's kit", "gear:sunrod", "gear:antitoxin"} <= ids


def test_an_offer_to_sell_opens_the_counter(monkeypatch):
    """Playtest 2026-11-17 #8: "offer to sell the silk from the Red Gull's hold" is an
    offer (`acts_to_ops._sell`), and nothing was built or said: the counter's screen opens
    for it, as it does for a purchase."""
    said = "I offer to sell the silk from the Red Gull's hold."
    interpret.remember(said, _frame({"act": "sell", "commit": "tried",
                                     "object": "the silk from the Red Gull's hold"}))
    assert judgement.sale_offered(said) == "the silk from the Red Gull's hold"
    assert judgement.purchase_sought(said) == ""


def test_a_stock_line_reads_rope_in_feet():
    """Playtest 2026-11-17 #17: the brief listed "hemp rope ×49", forty-nine ropes; the
    count is feet of one coil (`goods.deliver`: one purchase is fifty feet)."""
    from gm import prompts

    scene = _scene()
    _bought(scene, "rope")
    pc = scene.pc()
    sid = holding.stock_key(pc.stock, "hemp rope")
    pc.stock[sid].count = 49
    assert prompts.held_count(pc.stock[sid]) == ", 49 ft"


# --- a seized ship's cargo goes back with her -----------------------------------------------

def test_a_prize_cargo_is_stolen_and_goes_back_with_the_ship():
    """Playtest 2026-11-16 N3: cargo taken with a seized ship carried no stolen mark, and a
    conviction gave the ship back and left her cargo with the player."""
    from rules import trial
    from rules.ships import Vessel

    scene = _scene()
    engine = Engine(scene, Dice(seed=1))
    ship = Vessel(id="ship-test", name="the Red Gull", kind="sailing ship", hp=100,
                  at=scene.location_id, held_by="pc",
                  cargo=[{"key": "silk", "units": 300, "commodity": "silk"}])
    engine._keep_vessel(ship)
    lot = next(x for x in trade.lots(scene) if x.get("plunder") == "ship-test")
    assert lot["stolen"] is True

    class _Charge:
        kind, warrant, subject, subject_name, taken, goods = (
            "theft", "rule:ship-seized/ship-test", "", "her master", (), ())

    back = trial._confiscate(engine, scene.pc(), [_Charge()])
    assert not [x for x in trade.lots(scene) if x.get("plunder") == "ship-test"]
    assert engine.vessel("ship-test").cargo[0]["units"] == 300
    assert any("silk" in str(b["item"]) for b in back)
