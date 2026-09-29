"""Lane E: prepared casters start and wake with spells prepared (item 21.4).

Measured 2026-09-28: Bobby, a wizard with fifty spells in his book, had nothing prepared,
and no prompt, default or warning said so. Under it, worse: `Actor.rest` set
`self.prepared = {}` every night, so every prepared caster also WOKE with nothing — the
line guarded against keeping spells already cast, which `_op_cast` had stopped needing
since item 25 (it spends the prepared copy with the slot). 1e keeps "the ones that he
already had prepared from the previous day and has not yet used" (CRB magic chapter).
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import casting
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import _castable_summary, from_dict, load_pc, to_dict


def ysolde(prepared=None, loadout=None):
    """The pc-caster pregen: a wizard 1, Int 17 — two level 1 slots."""
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d["prepared"] = dict(prepared or {})
    d["loadout"] = dict(loadout or {})
    return from_dict(d, ref="pc")


def night(actor):
    s = Scene(location_id="5bbd0c40345f")
    s.add(actor)
    e = Engine(s, Dice(seed=2))
    return e.run(e.validate([{"op": "rest", "actor": "pc", "because": "t",
                              "params": {"kind": "night"}}])).outcomes[0]


def test_e_the_caster_pregen_has_a_book():
    """Every shipped pregen had an empty spellbook (fix-interfaces §3.4, R0-4), so no live
    run could cast anything; `pc-caster.json` is a wizard with a real one."""
    w = ysolde()
    assert "burning-hands" in w.spellbook and "magic-missile" in w.spellbook
    assert casting.slots_for(w) == {0: 3, 1: 2}
    assert load_pc("fixtures/pc-thessaly.json").spellbook == [], "Thessaly is untouched"


def test_e_rest_keeps_what_was_not_cast():
    """Prepare Burning Hands and Magic Missile, cast the missile, sleep: Burning Hands is
    still prepared (it was never cast) and the missile comes back from the loadout. Before
    the fix the night wiped both."""
    w = ysolde(prepared={"burning-hands": 1, "magic-missile": 1})
    casting.remember_loadout(w)
    s = Scene(location_id="5bbd0c40345f")
    s.add(w)
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.initiative, s.sides, s.round, s.turn = (
        [("pc", 20), ("c1", 10)], {"pc": ["pc"], "them": ["c1"]}, 1, 0)
    e = Engine(s, Dice(seed=2))
    e.run(e.validate([{"op": "cast", "actor": "pc", "because": "t",
                       "params": {"spell": "magic-missile", "at": "c1"}}]))
    assert w.prepared == {"burning-hands": 1}
    s.initiative, s.sides, s.turn = [], {}, 0
    out = e.run(e.validate([{"op": "rest", "actor": "pc", "because": "t",
                             "params": {"kind": "night"}}])).outcomes[0]
    assert w.prepared == {"burning-hands": 1, "magic-missile": 1}
    assert "prepares Magic Missile" in out.tell


def test_e_a_bare_night_no_longer_wipes():
    """`Actor.rest` itself: what is prepared stays."""
    w = ysolde(prepared={"burning-hands": 2})
    w.rest("night")
    assert w.prepared == {"burning-hands": 2}


def test_e_fresh_wizard_is_prepared_from_book_order():
    """No loadout ever: a book caster's empty slots fill from the book in its own order, one
    of each distinct spell before any repeat — Burning Hands, then Magic Missile."""
    w = ysolde()
    out = night(w)
    assert w.prepared == {"burning-hands": 1, "magic-missile": 1}
    assert "prepares Burning Hands, Magic Missile from the book" in out.tell
    assert casting.empty_slots(w) == {}


def test_e_the_loadout_decides_over_the_book():
    """The player's last preparation (Kingmaker's persistent memorised list) is what the
    morning refills — two missiles, not the book's first two."""
    w = ysolde(loadout={"magic-missile": 2})
    night(w)
    assert w.prepared == {"magic-missile": 2}


def test_e_list_caster_is_warned_not_guessed():
    """Owner, Q39: a cleric's first morning with nothing chosen is left empty, with a
    warning — no invented choice out of 1,143 spells."""
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "cleric", "level": 1, "spellbook": [], "prepared": {}, "ranks": {}})
    d["abilities"]["wis"] = 16
    cleric = from_dict(d, ref="pc")
    got = casting.ensure_prepared(cleric)
    assert got["added"] == {} and cleric.prepared == {}
    assert got["empty"] == casting.empty_slots(cleric) and got["empty"][1] >= 1
    out = night(cleric)
    assert "Level 1 slots stand empty" in out.tell


def test_e_nothing_prepared_offers_only_cantrips():
    """`_castable_summary` read `if prepared and not left`, and `{}` is falsy — so a
    prepared caster with NOTHING prepared was offered the whole book (fix-interfaces §1.7
    F1), every button past the cantrips one the engine would refuse."""
    from rules import spells as spells_mod

    w = ysolde()
    offered = _castable_summary(w)
    assert offered and all(
        casting.spell_level_for(w, spells_mod.get(x["id"])) == 0 for x in offered)
    w.prepared = {"burning-hands": 1}
    ids = {x["id"] for x in _castable_summary(w)}
    assert "burning-hands" in ids and "magic-missile" not in ids


def test_e_spontaneous_casters_are_left_alone():
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "sorcerer", "level": 1, "spellbook": ["magic-missile"], "ranks": {},
              "prepared": {}})
    d["abilities"]["cha"] = 16
    sorc = from_dict(d, ref="pc")
    assert casting.ensure_prepared(sorc)["added"] == {} and casting.empty_slots(sorc) == {}
    assert [x["id"] for x in _castable_summary(sorc)] == ["magic-missile"]


@pytest.fixture
def campaign(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        yield cm.begin_with(ysolde())
        cm._LIVE.clear()


def test_e_the_sheet_warns_of_empty_slots_and_the_prepare_tab_remembers(campaign):
    """`/api/state` `spellcasting.empty_slots` names the empty slots (§2.10), and every
    change on the Spells tab is the loadout the next morning refills."""
    s = Client().get("/api/state").json()
    assert s["spellcasting"]["empty_slots"] == {"1": 2}
    r = Client().post("/api/spells/prepare", data=json.dumps(
        {"action": "prepare", "spell": "burning-hands"}), content_type="application/json")
    assert r.status_code == 200
    pc = campaign.scene.pc()
    assert pc.loadout == {"burning-hands": 1}
    assert Client().get("/api/state").json()["spellcasting"]["empty_slots"] == {"1": 1}
