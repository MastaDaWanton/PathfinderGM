"""Cantrips and orisons: prepared first, then cast at will (fix-interfaces §3.4, found by I5).

The rule, from each class entry on Archives of Nethys (fetched 2026-09-29):

  * Wizard: "Wizards can prepare a number of cantrips, or 0-level spells, each day, as
    noted on Table: Wizard under 'Spells per Day.' These spells are cast like any other
    spell, but they are not expended when cast and may be used again." Three at 1st
    level, four from 2nd.
  * Cleric and Druid: the same two sentences with "orisons" (3 at 1st, 4 from 2nd).
  * Sorcerer and Bard: "…learn a number of cantrips, or 0-level spells, as noted on
    Table: … Spells Known… they do not consume any slots and may be used again."
  * Paladin and Ranger: no 0-level spells (their tables start at 1st).

Measured before the fix, both halves wrong and in opposite directions:

  1. The engine SPENT a 0-level slot per cast: the sheet's "Spell Slot 0 3 of 3" drained,
     and a level 5 wizard's Light went 4, 3, 2, 1, 0 and was then refused.
  2. The engine did NOT require a cantrip to be prepared (`_check_cast` exempted level 0
     from "did not prepare"), so every cantrip in a wizard's book was castable.
  3. `casting.ensure_prepared` skipped level 0 (`lvl > 0`), so the first morning and every
     rest left the cantrip slots empty.
  4. The popover (`10-spells.js` `spellRows`) offered every cantrip in the book, and the
     Spells page said each cast spends a cantrip slot.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from django.test import override_settings

from pagesource import TABLE_SCRIPTS
from rules import casting
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import PLAYER_FIXABLE, IntentError
from rules.sheet import from_dict, load_pc, to_dict


def ysolde(**over):
    """The pc-caster pregen: a wizard 1, Int 17 — three cantrip slots and two level 1."""
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d.update(over)
    return from_dict(d, ref="pc")


def sorcerer(book=("resistance", "read-magic", "magic-missile")):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "sorcerer", "level": 1, "spellbook": list(book), "ranks": {},
              "prepared": {}})
    d["abilities"]["cha"] = 16
    return from_dict(d, ref="pc")


def cantrips_in_book(actor):
    return [s for s in actor.spellbook if casting._level(actor, s) == 0]


def cast(engine, spell, at="pc"):
    return engine.run(engine.validate([{"op": "cast", "actor": "pc", "because": "t",
                                        "params": {"spell": spell, "at": at}}]))


def table(caster):
    s = Scene(location_id="5bbd0c40345f")
    s.add(caster)
    casting.define_slots(caster)
    return s, Engine(s, Dice(seed=3))


# --- the first morning ------------------------------------------------------------------------

def test_a_wizard_1_starts_with_three_cantrips_and_two_first_level_spells(tmp_path):
    """Defect 3: the first morning filled the level 1 slots and skipped the cantrip slots
    (`lvl > 0`), so a new wizard held no cantrip at all — and only got away with it
    because the engine let any cantrip in the book be cast unprepared. Through the real
    door a campaign begins by (`play.campaign.begin_with` → `ensure_prepared`)."""
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        try:
            c = cm.begin_with(ysolde(prepared={}, loadout={}))
            pc = c.scene.pc()
            by_level = {}
            for sid, n in pc.prepared.items():
                lvl = casting._level(pc, sid)
                by_level[lvl] = by_level.get(lvl, 0) + n
            assert casting.slots_for(pc) == {0: 3, 1: 2}
            assert by_level == {0: 3, 1: 2}
            # One of each distinct cantrip, in the book's own order.
            assert [s for s in pc.prepared if casting._level(pc, s) == 0] \
                == cantrips_in_book(pc)[:3]
            assert all(pc.prepared[s] == 1 for s in cantrips_in_book(pc)[:3])
            assert casting.empty_slots(pc) == {}
        finally:
            cm._LIVE.clear()


# --- at will ----------------------------------------------------------------------------------

def test_casting_a_prepared_cantrip_five_times_spends_nothing():
    """Defect 1: "not expended when cast and may be used again". Five casts of one
    prepared cantrip leave the 0-level pool full and the cantrip still prepared — before
    the fix the pool fell 3, 2, 1, 0 and the fourth cast was refused "no level 0 slots"."""
    w = ysolde(prepared={"read-magic": 1}, loadout={})
    assert "read-magic" in w.spellbook
    s, e = table(w)
    before = casting.slots_left(w, 0)
    assert before == 3
    for _ in range(5):
        out = cast(e, "read-magic")
        assert out.outcomes and out.outcomes[-1].status == "resolved", out.outcomes[-1].tell
    assert casting.slots_left(w, 0) == before
    assert w.prepared == {"read-magic": 1}
    record = [x for x in out.outcomes[-1].effects if x.get("kind") == "cast"][0]
    assert record["at_will"] is True and record["slots_left"] == before


def test_a_drained_cantrip_pool_from_an_old_save_does_not_stop_a_cast():
    """A save made before the fix can hold "spell slot 0" at 0 of 3. The at-will cast
    neither asks the pool nor spends it."""
    w = ysolde(prepared={"read-magic": 1}, loadout={})
    s, e = table(w)
    w.spend_pool(casting.slot_pool(0), 3)
    assert casting.slots_left(w, 0) == 0
    out = cast(e, "read-magic")
    assert out.outcomes[-1].status == "resolved", out.outcomes[-1].tell


def test_a_first_level_spell_still_spends_its_slot():
    """The exemption is the 0-level spell and nothing else: Magic Missile still spends a
    level 1 slot and its prepared copy."""
    w = ysolde(prepared={"magic-missile": 1}, loadout={})
    s, e = table(w)
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.initiative, s.sides, s.round, s.turn = (
        [("pc", 20), ("c1", 10)], {"pc": ["pc"], "them": ["c1"]}, 1, 0)
    cast(e, "magic-missile", at="c1")
    assert casting.slots_left(w, 1) == 1 and "magic-missile" not in w.prepared


# --- prepared first ---------------------------------------------------------------------------

def test_an_unprepared_cantrip_is_refused_not_prepared():
    """Defect 2: `_check_cast` exempted level 0 from "did not prepare", so every cantrip
    in the book — twenty-odd for a wizard — was castable. An unprepared cantrip is now
    refused like any unprepared spell, with the code the player can fix (a Prepare
    button), never the plan loop's to retry."""
    w = ysolde(prepared={"read-magic": 1}, loadout={})
    assert "detect-magic" in w.spellbook
    s, e = table(w)
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "pc", "because": "t",
                     "params": {"spell": "detect-magic", "at": "pc"}}])
    assert err.value.code == "unprepared" and "unprepared" in PLAYER_FIXABLE
    assert "did not prepare Detect Magic" in str(err.value)
    assert err.value.fix == {"kind": "prepare", "spell": "detect-magic"}


def test_rest_keeps_the_players_cantrips():
    """The cantrips the player chose are the loadout the mornings refill — not the book's
    first three. `remember_loadout` left level 0 out before the fix."""
    w = ysolde(prepared={}, loadout={})
    chosen = cantrips_in_book(w)[-3:]
    assert set(chosen).isdisjoint(cantrips_in_book(w)[:3])
    w.prepared = {sid: 1 for sid in chosen}
    w.prepared["magic-missile"] = 2
    casting.remember_loadout(w)
    assert w.loadout == {**{sid: 1 for sid in chosen}, "magic-missile": 2}
    s, e = table(w)
    cast(e, chosen[0])
    w.prepared.pop(chosen[1])            # a cantrip let go of during the day
    e.run(e.validate([{"op": "rest", "actor": "pc", "because": "t",
                       "params": {"kind": "night"}}]))
    assert w.prepared == {**{sid: 1 for sid in chosen}, "magic-missile": 2}


def test_an_old_loadout_with_no_cantrip_fills_the_cantrip_slots_from_the_book():
    """Every loadout saved before the fix names no cantrip. The night fills those slots
    from the book rather than leave a wizard with nothing to cast at will."""
    w = ysolde(prepared={}, loadout={"magic-missile": 2})
    s, e = table(w)
    out = e.run(e.validate([{"op": "rest", "actor": "pc", "because": "t",
                             "params": {"kind": "night"}}])).outcomes[0]
    assert w.prepared == {"magic-missile": 2, **{c: 1 for c in cantrips_in_book(w)[:3]}}
    assert "Cantrip slots stand empty" not in out.tell


def test_a_cleric_with_no_orisons_chosen_is_warned_in_words():
    """Owner Q39: a list caster is never given an invented choice. The empty orison slots
    are named in the rest's tell as cantrip slots, not "Level 0"."""
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "cleric", "level": 1, "spellbook": [], "prepared": {}, "ranks": {}})
    d["abilities"]["wis"] = 16
    cleric = from_dict(d, ref="pc")
    got = casting.ensure_prepared(cleric)
    assert got["added"] == {} and got["empty"][0] == 3
    assert "Cantrip slots stand empty" in casting.prepared_said(cleric, got)


# --- spontaneous casters ----------------------------------------------------------------------

def test_a_sorcerer_casts_known_cantrips_at_will():
    """Sorcerer: cantrips "do not consume any slots and may be used again". Nothing to
    prepare (a sorcerer prepares nothing), five casts, the pool untouched; a cantrip not
    known is still refused."""
    sorc = sorcerer()
    s, e = table(sorc)
    before = casting.slots_left(sorc, 0)
    for _ in range(5):
        out = cast(e, "resistance" if _ % 2 else "read-magic")
        assert out.outcomes[-1].status == "resolved", out.outcomes[-1].tell
    assert casting.slots_left(sorc, 0) == before
    assert casting.ensure_prepared(sorc)["added"] == {} and sorc.prepared == {}
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "pc", "because": "t",
                     "params": {"spell": "light", "at": "pc"}}])
    assert err.value.code == "not_known"


# --- the popover ------------------------------------------------------------------------------

def _node(source: str, tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    f = tmp_path / "probe.js"
    f.write_text(source, encoding="utf-8")
    done = subprocess.run([node, str(f)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


_STUBS = """
const document = { addEventListener() {}, getElementById() { return null; },
                   querySelector() { return null; } };
const window = {};
const $ = () => null;
function onRender() {}
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
"""


def test_the_popover_offers_prepared_cantrips_at_will_and_counts_the_rest(tmp_path):
    """Defect 4: `spellRows` offered every cantrip in a prepared caster's book, on the
    engine's old exemption. Now a prepared caster is offered the cantrips prepared today,
    under a heading that says at will (no pips: nothing is counted down), and the others
    join the "not prepared today" count. A sorcerer is offered every cantrip known."""
    wiz = {"kind": "prepared", "slots": [{"level": 0, "max": 3, "left": 3},
                                         {"level": 1, "max": 2, "left": 2}],
           "known": [{"id": "light", "name": "Light", "level": 0, "prepared": 1},
                     {"id": "daze", "name": "Daze", "level": 0, "prepared": 0},
                     {"id": "flare", "name": "Flare", "level": 0, "prepared": 0},
                     {"id": "magic-missile", "name": "Magic Missile", "level": 1,
                      "prepared": 1}]}
    sorc = {"kind": "spontaneous", "slots": [{"level": 0, "max": 4, "left": 0},
                                             {"level": 1, "max": 3, "left": 3}],
            "known": [{"id": "light", "name": "Light", "level": 0, "prepared": 0},
                      {"id": "daze", "name": "Daze", "level": 0, "prepared": 0}]}
    src = _STUBS + (TABLE_SCRIPTS / "10-spells.js").read_text(encoding="utf-8") + f"""
    const W = {json.dumps(wiz)}, S = {json.dumps(sorc)};
    const w = spellRows(W), s = spellRows(S);
    console.log(JSON.stringify({{
      wiz: w.rows.map(r => [r.id, r.why]), unprepared: w.unprepared,
      sorc: s.rows.map(r => [r.id, r.why]),
      html: spellPickerHtml({{ spells: W }}),
    }}));"""
    got = _node(src, tmp_path)
    assert got["wiz"] == [["light", ""], ["magic-missile", ""]]
    assert got["unprepared"] == 2
    # A drained 0-level pool from an old save does not grey a sorcerer's cantrip.
    assert got["sorc"] == [["light", ""], ["daze", ""]]
    head = got["html"][got["html"].index('data-level="0"'):]
    head = head[:head.index("</div>")]
    assert "at will" in head and "sp-pips" not in head
    assert "2 more in your book are not prepared today" in got["html"]
