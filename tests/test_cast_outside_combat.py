"""A spell can be cast from the Spells tab, fight or no fight.

Reported 2026-09-24: *"I have no way of casting spells outside of combat."* The `cast` op
never needed an encounter — it spends the slot, sets the DC and runs the spell's effects
whenever it is asked — but the only button that offered one was the combat bar, which is
hidden outside a fight, and the Spells tab only prepared and unprepared. `/api/cast` is
the same declared intent by another door, and the tab now has a Cast button and a target
picker on every row.
"""
from __future__ import annotations

from pathlib import Path

from django.urls import reverse

from rules.dice import Dice
from rules.engine import Engine, Scene
from test_casting_executes import cleric


class TestTheEngineNeverNeededAFight:
    def test_a_cleric_casts_in_a_quiet_room(self):
        s = Scene(location_id="5bbd0c40345f")
        pc = s.add(cleric(level=3))
        e = Engine(s, Dice(seed=2), world=None)
        assert not s.in_encounter
        raw = {"op": "cast", "actor": pc.ref, "because": "t",
               "params": {"spell": "cure-light-wounds", "at": pc.ref}}
        out = e.run(e.validate([raw], origin="author:test")).outcomes[-1]
        assert out.op == "cast" and out.status != "refused", out.tell
        assert not s.in_encounter, "casting did not start a fight"


class TestTheDoor:
    def test_the_route_exists(self):
        assert reverse("cast_act") == "/api/cast"

    def test_the_spells_tab_offers_it(self):
        html = Path("play/templates/play/table.html").read_text(encoding="utf-8")
        assert 'class="prepbtn castbtn"' in html
        assert 'class="casttarget"' in html
        assert 'post("/api/cast"' in html

    def test_the_view_refuses_off_turn_in_a_fight_and_nothing_else(self):
        src = Path("play/views.py").read_text(encoding="utf-8")
        body = src[src.index("def cast_act("):]
        body = body[:body.index("\ndef ", 10)]
        assert "It is not your turn." in body
        assert "No fight is on" not in body
