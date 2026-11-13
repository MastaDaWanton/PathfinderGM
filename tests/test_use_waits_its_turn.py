"""The Equipment tab's `/api/use` waits for the player's turn in a fight.

Measured by the alchemy finishing lane on 2026-10-07: `/api/use` checked whether a roll
was owed and never whose turn it was, so a potion could be drunk or a flask thrown from
the Equipment tab while a foe held the turn. The combat panel, the Spells tab and the
From-here row each asked, in three inline copies of one expression; the fourth door had
none. The check is one helper now (`views._off_turn`), and every door reads it.

The state the tests park the scene in is the real one: `_LIVE` holds one campaign for
every request, and a commit's NPC turns run model calls for minutes with the order on
the foe — any click on the sheet in that window lands on somebody else's turn.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from rules import crafting, goods
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parent.parent


def _tea():
    return crafting.Stock(
        base="Acacia Tea", tier="common", count=2, potency=1.0, craft="herbalist",
        effects=["+1 Will saves"],
        specs=[{"type": "save_mod", "amount": 1, "target": "will",
                "bonus_type": "untyped", "from": "Acacia",
                "duration": {"amount": 1, "unit": "hour"}}])


@pytest.fixture
def table(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.seed = 20261008
        pc = c.scene.pc()
        pc.stock.clear()
        tea = _tea()
        pc.add_stock(tea, tea.count)
        pc.add_stock(goods.alchemy_stock("alchemists-fire"), 2)
        c.save()
        yield Client()
        cm._LIVE.clear()


def _ids():
    stock = cm.current().scene.pc().stock
    tea = next(sid for sid, s in stock.items() if s.base == "Acacia Tea")
    fire = next(sid for sid, s in stock.items() if s.name == "Alchemist's fire")
    return tea, fire


def _fight(on_the_foe: bool) -> str:
    """A thug, a fight, and the turn parked on whoever the test names."""
    c = cm.current()
    engine = c.engine()
    if c.scene.in_encounter:
        # The opening is not seeded and can start a robbery (measured 2026-11-13: 1 of
        # 4 begin_with calls), and a turn's plan may not spawn into a fight, so these
        # tests failed at random. End the opening's own fight first.
        engine.run(engine.validate([{"op": "end_encounter", "because": "test setup"}]))
    before = set(c.scene.actors)
    engine.run(engine.validate([{"op": "spawn", "because": "a thug steps out",
                                 "params": {"template": "thug", "count": 1,
                                            "zone": "near"}}]))
    ref = next(r for r in c.scene.actors if r not in before)
    engine.run(engine.validate([{"op": "begin_encounter", "because": "he draws",
                                 "params": {"sides": {"pc": ["pc"], "foes": [ref]}}}]))
    want = ref if on_the_foe else "pc"
    while c.scene.current_ref() != want:
        c.scene.turn = (c.scene.turn + 1) % len(c.scene.initiative)
    here = c.scene.positions.get("pc")
    if here is not None:
        c.scene.positions[ref] = (here[0] + 1, here[1]) + tuple(here[2:])
        c.scene.resync_zones()
    c.save()
    return ref


def _use(client, body):
    return client.post("/api/use", data=json.dumps(body), content_type="application/json")


def test_a_potion_is_not_drunk_on_a_foes_turn(table):
    """The finding itself: Drink on the Equipment tab while the thug held the turn drank
    the tea. Refused now with 409, in words that name who is acting, and the dose is
    still in the satchel."""
    ref = _fight(on_the_foe=True)
    tea, _ = _ids()
    r = _use(table, {"item": tea, "how": "drink"})
    assert r.status_code == 409, r.json()
    said = r.json()["error"]
    assert said.startswith("It is not your turn.")
    # Named as a sentence names him: the spawned thug is "thug", a kind of person, and
    # "thug is acting" read like a typo on the first live check.
    assert cm.current().scene.actors[ref].name == "thug"
    assert "The thug is acting" in said, said
    scene = cm.current().scene
    assert scene.pc().stock[tea].count == 2
    assert scene.current_ref() == ref, "a refusal moved the order"


def test_a_flask_is_not_thrown_on_a_foes_turn(table):
    """A throw is a ranged attack that suspends for the player's d20; thrown off-turn it
    would leave a roll owed on the foe's turn. Refused before anything is spent."""
    ref = _fight(on_the_foe=True)
    _, fire = _ids()
    r = _use(table, {"item": fire, "how": "throw", "to": ref})
    assert r.status_code == 409, r.json()
    assert r.json()["error"].startswith("It is not your turn.")
    scene = cm.current().scene
    assert scene.pc().stock[fire].count == 2
    assert not scene.awaiting


def test_on_the_players_own_turn_the_drink_goes_down(table):
    """The gate is the turn, not the fight: on the PC's turn the same press drinks."""
    _fight(on_the_foe=False)
    tea, _ = _ids()
    r = _use(table, {"item": tea, "how": "drink"})
    assert r.status_code == 200, r.json()
    assert "drinks" in r.json()["tell"]
    assert cm.current().scene.pc().stock[tea].count == 1


def test_out_of_a_fight_nothing_changes(table):
    """No encounter, no turn: the Equipment tab drinks as it always has."""
    tea, _ = _ids()
    assert not cm.current().scene.in_encounter
    r = _use(table, {"item": tea, "how": "drink"})
    assert r.status_code == 200, r.json()
    assert cm.current().scene.pc().stock[tea].count == 1


def test_a_roll_owed_is_said_before_the_turn(table):
    """A die the player owes mid-foe-turn (a save against the thug's blow) is the thing
    they can act on; it is answered first, as it was before the turn check existed."""
    _fight(on_the_foe=True)
    tea, _ = _ids()
    scene = cm.current().scene
    scene.awaiting = {"die": "1d20", "why": "a save"}
    r = _use(table, {"item": tea, "how": "drink"})
    assert r.status_code == 409
    assert "roll waiting" in r.json()["error"]


def test_the_turn_check_has_one_home():
    """Three doors held their own copy of `in_encounter and current_ref() != pc.ref`, and
    the fourth door had none: the copy nobody wrote is how `/api/use` shipped without it
    (CLAUDE.md, "when you fix a rule, grep for every copy of it"). Every door that acts
    in a fight reads `_off_turn`, and no view spells the comparison out again."""
    src = (ROOT / "play" / "views.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    copies = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef) or fn.name == "_off_turn":
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Compare) and any(
                    isinstance(op, ast.NotEq) for op in node.ops) and \
                    "current_ref()" in (ast.get_source_segment(src, node) or ""):
                copies.append(fn.name)
    assert not copies, f"{copies} compare current_ref() inline; call _off_turn"
    for door in ("use_item", "cast_act", "combat_act", "say"):
        body = ast.get_source_segment(src, next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == door)) or ""
        assert "_off_turn(" in body or "_wait_your_turn(" in body, door
