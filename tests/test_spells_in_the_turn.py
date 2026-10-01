"""A spell is cast in the combat panel's turn, beside a move, not through the Say box.

The owner, 2026-10-01, in a fight: "there is a separating of the commit turn and the say
button spells are mapped to the say button instead of the commit turn so i cannot move and
cast in the same turn." Traced: the bottom Spells button and the panel's Cast… both opened
the one picker (10-spells.js), and choosing a spell attached a chip to the Say box
(`attachSpell`), so the cast went to `/api/say` as a spoken turn of its own; a move staged
on the panel (`COMBAT.move`, 04-combat-and-turns.js) went to `/api/combat/act` with
Commit turn. Two doors, two turns: the beat showed a "Magic Missile" chip on the player's
line and the staged step to the square never travelled with it.

`combat_act` has carried `cast` in its whitelist since 2026-08-25 (f8d88e3); what was
missing was the page putting a chosen spell into the panel's turn. These tests hold both
halves: the server runs a move and a cast posted together as one turn, and the page, in a
fight, stages the spell into the turn Commit turn posts (its standard slot, aimed at the
panel's target, or at the caster for a personal spell) instead of the Say box, while out
of a fight the chip still goes to Say.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from django.test import Client, override_settings

from rules import casting
from rules.sheet import from_dict, load_pc, to_dict
from tests._exits_dom import PRELUDE, TABLE


# --- the server: one post, a move and a cast ---------------------------------------------

@pytest.fixture
def caster_fight(tmp_path):
    from play import campaign as cm
    from rules.bestiary import instantiate

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        d = to_dict(load_pc("fixtures/pc-caster.json"))
        d["prepared"] = {"magic-missile": 2, "shield": 1}
        c = cm.begin_with(from_dict(d, ref="pc"))
        c.seed = 20261001
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        thug = instantiate("thug", scene=c.scene, name="the thug")
        thug.ref = "c1"
        c.scene.add(thug)
        e = c.engine()
        e.run(e.validate([{
            "op": "begin_encounter",
            "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
        while c.scene.current_ref() != "pc":
            c.scene.advance_turn()
        c.save()
        yield Client(), cm
        cm._LIVE.clear()


def _free_square_near(scene, ref="pc"):
    here = scene.positions[ref]
    taken = scene.occupied(ignore=ref)
    for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)):
        sq = (here[0] + dx, here[1] + dy)
        if scene.grid.inside(sq) and scene.grid.passable(sq) and sq not in taken:
            return [sq[0], sq[1]]
    pytest.skip("no open square beside the caster on this board")


def test_a_move_and_a_cast_committed_together_are_one_turn(caster_fight):
    """The shape Commit turn posts once a spell is staged: `move` then `cast`, one body.
    Before the fix the page never sent it — the cast went to /api/say on its own — so
    this is the server half proved: both happen, in order, and the slot is spent once."""
    client, cm = caster_fight
    scene = cm.current().scene
    if not scene.has_grid:
        pytest.skip("the fixture scene has no map to move on")
    to = _free_square_near(scene)
    slots_before = casting.slots_left(scene.pc(), 1)
    r = client.post("/api/combat/act", content_type="application/json", data=json.dumps({
        "actions": [{"op": "move", "params": {"zone": "near", "square": to}},
                    {"op": "cast", "target": "c1", "params": {"spell": "magic-missile"}}],
        "label": "move to (%d,%d); cast magic missile at the thug" % tuple(to),
        "end_turn": False}))
    assert r.status_code == 200, r.content
    c = cm.current()
    pc = c.scene.pc()
    assert list(c.scene.positions["pc"][:2]) == to, "the move did not happen"
    # Magic Missile's damage is the player's own die: the cast either finished or is
    # waiting on that roll, and in both cases its slot went on the way in, once.
    assert casting.slots_left(pc, 1) == slots_before - 1, "the cast did not happen"
    awaiting = c.scene.awaiting or {}
    if awaiting:
        assert "magic" in json.dumps(awaiting).lower() or awaiting.get("op") == "cast"
    said = [b for b in c.transcript if b.get("who") == "player"]
    assert said and "magic missile" in said[-1]["text"], \
        "the player's line should name both steps of the one turn"


def test_a_personal_spell_aimed_at_self_is_accepted(caster_fight):
    """Shield is `Range: personal`: the panel stages it with `aim: self`, never at the
    target chip, so the thug is not the one whose AC goes up."""
    client, cm = caster_fight
    pc = cm.current().scene.pc()
    ac_before = pc.ac()
    r = client.post("/api/combat/act", content_type="application/json", data=json.dumps({
        "actions": [{"op": "cast", "params": {"spell": "shield", "aim": "self"}}],
        "label": "cast shield on yourself", "end_turn": False}))
    assert r.status_code == 200, r.content
    pc = cm.current().scene.pc()
    thug = cm.current().scene.actors["c1"]
    assert pc.ac() > ac_before, "Shield went somewhere other than its caster"
    assert not any("shield" in str(b).lower() for b in getattr(thug, "buffs", []) or [])


# --- the page: in a fight, a chosen spell goes into the panel's turn ----------------------

_COMBAT_PRELUDE = r"""
const STATE_FIGHT = { scene: { in_encounter: true, turn_ref: "pc", round: 1,
  initiative: [], actors: [{ ref: "c1", name: "the thug", hp: 9, hp_max: 9,
                             conditions: [] }] }, pc: { ref: "pc" } };
const STATE_PEACE = { scene: { in_encounter: false, actors: [] }, pc: { ref: "pc" } };
ELS.combatbar = el("combatbar"); ELS["cb-menu"] = el("cb-menu");
ELS["cb-plan"] = el("cb-plan"); ELS["cb-round"] = el("cb-round");
ELS["cb-turn"] = el("cb-turn"); ELS["cb-targets"] = el("cb-targets");
ELS["cb-coup"] = el("cb-coup"); ELS["cb-commit"] = el("cb-commit");
ELS["cb-cast"] = el("cb-cast"); ELS.sayform = el("sayform"); ELS.carryon = el("carryon");
const POSTS = [];
async function post(url, body) { POSTS.push({ url, body }); return STATE; }
function render(s) { STATE = s; }
function busy() {}
function readJSON(r) { return r.json(); }
"""


def _run_page(tmp_path, steps: str) -> dict:
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    # 04's tail is the character sheet's: everything from its first line on reads page
    # furniture this stub does not have, and none of it is the turn.
    turns = (TABLE / "04-combat-and-turns.js").read_text(encoding="utf-8")
    turns = turns[:turns.index("/* ---- The full character sheet")]
    spells = (TABLE / "10-spells.js").read_text(encoding="utf-8")
    f =tmp_path / "probe.js"
    f.write_text(PRELUDE + _COMBAT_PRELUDE + turns + "\n" + spells + "\n" + steps,
                 encoding="utf-8")
    done = subprocess.run(["node", str(f)], capture_output=True, text=True,
                          encoding="utf-8")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_in_a_fight_a_chosen_spell_is_staged_beside_the_move_and_committed_with_it(tmp_path):
    """The owner's turn, replayed on the page's own functions: a square clicked on the
    map, Magic Missile chosen from the Spells picker, Commit turn. One post to
    /api/combat/act carries the move and the cast; nothing goes to /api/say and no chip
    is left in the Say box. Before the fix the pick called `attachSpell` and the cast
    could only leave through Say, as a turn of its own."""
    got = _run_page(tmp_path, r"""
renderAll(STATE_FIGHT); STATE = STATE_FIGHT; renderCombat(STATE_FIGHT);
COMBAT.move = [4, 5];
const staged = chooseSpell({ id: "magic-missile", name: "Magic Missile", range: "medium (100 ft. + 10 ft./level)" });
commitTurn(false).then(() => done({ staged, posts: POSTS, said: SENT,
  chips: currentAttachments() }));
""")
    assert got["staged"] == "turn"
    assert got["said"] == [] and got["chips"] == [], "the spell still went to the Say box"
    assert [p["url"] for p in got["posts"]] == ["/api/combat/act"]
    acts = got["posts"][0]["body"]["actions"]
    assert [a["op"] for a in acts] == ["move", "cast"], acts
    assert acts[1]["params"]["spell"] == "magic-missile" and acts[1]["target"] == "c1"
    assert "magic missile" in got["posts"][0]["body"]["label"]


def test_a_personal_spell_is_staged_on_the_caster_not_the_target_chip(tmp_path):
    got = _run_page(tmp_path, r"""
renderAll(STATE_FIGHT); STATE = STATE_FIGHT; renderCombat(STATE_FIGHT);
chooseSpell({ id: "shield", name: "Shield", range: "personal" });
done({ standard: COMBAT.standard });
""")
    act = got["standard"]["actions"][0]
    assert act["op"] == "cast" and act["params"] == {"spell": "shield", "aim": "self"}
    assert not act.get("target"), "a personal spell was aimed at the thug"


def test_out_of_a_fight_the_spell_is_still_a_chip_for_say(tmp_path):
    """Out of a fight there is no panel turn: the Spells button keeps attaching the chip
    and the player says where it goes (owner Q46)."""
    got = _run_page(tmp_path, r"""
renderAll(STATE_PEACE); STATE = STATE_PEACE;
const staged = chooseSpell({ id: "magic-missile", name: "Magic Missile" });
done({ staged, chips: currentAttachments(), standard: COMBAT.standard });
""")
    assert got["staged"] == "chip"
    assert got["chips"] == [{"kind": "spell", "id": "magic-missile", "name": "Magic Missile"}]
    assert got["standard"] is None


def test_every_door_that_chooses_a_spell_goes_through_choose_spell():
    """The picker's rows, the Spells tab's Cast and the page's `attachSpellChip` are the
    three ways a spell is chosen; one of them left on `attachSpell` would be the same
    defect through a door nobody re-tested."""
    spells = (TABLE / "10-spells.js").read_text(encoding="utf-8")
    pick = spells[spells.index('const pick = t.closest("#spellpop .sp-spell");'):]
    pick = pick[:pick.index("return;")]
    assert "chooseSpell(" in pick and "attachSpell(" not in pick
    door = spells[spells.index("window.attachSpellChip = "):]
    door = door[:door.index("};")]
    assert "chooseSpell(" in door
    state = (TABLE / "02-state.js").read_text(encoding="utf-8")
    tab = state[state.index('const cast = e.target.closest(".castbtn");'):]
    tab = tab[:tab.index("return;")]
    assert "chooseSpell(" in tab and "/api/cast" not in tab
