"""The combat panel's turn, in the order the player chose.

The owner, 2026-11-06: "when setting up a turn in combat I can only move before I attack I
should be able to drag or move the order of things before I commit the turn so i can attack
and then move after." Traced: `commitTurn` (play/static/js/table/04-combat-and-turns.js)
always posted the plan as move, swift, frees, standard, whatever the player meant, and the
plan chips had no order to change. The Core Rulebook ("Action Types", "Move Actions") lets
the move come before or after the standard action; only a full-round action keeps the
move out (a 5-foot step is all it leaves).

These tests hold the three halves. The server runs `[attack, move]` as posted, the blow and
then the walk, with the attack of opportunity the walk out of a threatened square draws.
The door refuses what the reorder newly makes possible and the rules do not allow — a move
after a full attack or a coup de grâce, a strike placed before the move that would only
have reached after it — in words, before anything happens. The page keeps an order array,
reorders it by drag, by pointer on touch, and by earlier/later buttons, and Commit turn
posts in that order.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from django.test import Client, override_settings

from rules.sheet import load_pc
from tests._board import face_to_face
from tests._exits_dom import PRELUDE, TABLE


# --- the server: the order posted is the order run ----------------------------------------

@pytest.fixture
def panel(tmp_path):
    from play import campaign as cm
    from rules.bestiary import instantiate

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        # Seeded, as test_combat_panel.py's fixture is: the thug's attack of opportunity
        # and his turn after are real rolls against a 9-hit-point rogue.
        c.seed = 20261106
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        thug = instantiate("thug", scene=c.scene, name="the thug")
        thug.ref = "c1"
        c.scene.add(thug)
        e = c.engine()
        e.run(e.validate([{"op": "begin_encounter",
                           "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
        while c.scene.current_ref() != "pc":
            c.scene.advance_turn()
        if not c.scene.has_grid:
            pytest.skip("the fixture scene has no map to move on")
        face_to_face(c.scene)
        c.save()
        yield Client(), cm
        cm._LIVE.clear()


def _post(client, actions, end_turn=False):
    return client.post("/api/combat/act", content_type="application/json",
                       data=json.dumps({"actions": actions, "label": "the plan",
                                        "end_turn": end_turn}))


def _answer_rolls(client, cm):
    guard = 0
    while cm.current().scene.awaiting and guard < 12:
        prompt = cm.current().scene.awaiting
        face = min(15, int(prompt.get("max", 20)))
        r = client.post("/api/roll", data=json.dumps({"face": face}),
                        content_type="application/json")
        assert r.status_code == 200, r.content
        guard += 1


def _square_away(scene, steps=2):
    """An open square `steps` squares from the player on the side away from the thug:
    leaving the thug's reach for it is a walk out of a threatened square, not a step."""
    here = tuple(scene.positions["pc"])[:2]
    foe = tuple(scene.positions["c1"])[:2]
    sx = -1 if foe[0] > here[0] else (1 if foe[0] < here[0] else 0)
    sy = -1 if foe[1] > here[1] else (1 if foe[1] < here[1] else 0)
    taken = scene.occupied(ignore="pc")
    for dx, dy in ((sx, sy), (sx, 0), (0, sy), (-sy, sx), (sy, -sx)):
        if (dx, dy) == (0, 0):
            continue
        sq = (here[0] + dx * steps, here[1] + dy * steps)
        if scene.grid.inside(sq) and scene.grid.passable(sq) and sq not in taken:
            return [sq[0], sq[1]]
    pytest.skip("no open square away from the thug on this board")


def _outcomes(cm):
    """Every outcome the turn logged, in the order the engine ran them."""
    out = []
    for e in cm.current().turn_log:
        out += [o for o in (e.get("outcomes") or [])]
    return out


def test_a_strike_then_a_move_resolves_both_in_that_order(panel):
    """The owner's request, the server half: `[attack, move]` posted to /api/combat/act.
    Before the reorder the page could never send it (commitTurn put the move first every
    time); nothing in the door or the engine refuses a move for coming second. The blow
    suspends into the player's d20, the move waits behind it, and once the dice are
    answered the move walks — after the thug's attack of opportunity for leaving his
    reach, which `_reactions_before` splices in front of it as for any move."""
    client, cm = panel
    scene = cm.current().scene
    start = tuple(scene.positions["pc"])[:2]
    to = _square_away(scene)
    before = len(cm.current().turn_log)
    r = _post(client, [{"op": "attack", "target": "c1", "params": {}},
                       {"op": "move", "params": {"zone": "near", "square": to}}])
    assert r.status_code == 200, r.json()
    assert r.json()["awaiting"], "the strike comes first, waiting on the player's d20"
    assert tuple(cm.current().scene.positions["pc"])[:2] == start, \
        "the move ran before the strike it was ordered after"
    _answer_rolls(client, cm)
    c = cm.current()
    ran = [o for e in c.turn_log[before:] for o in (e.get("outcomes") or [])]
    mine = [(o.get("op"), o.get("actor")) for o in ran if o.get("op") in ("attack", "move")]
    assert ("attack", "pc") in mine and ("move", "pc") in mine, mine
    assert mine.index(("attack", "pc")) < mine.index(("move", "pc")), mine
    # The walk out of the thug's reach drew his swing, between the blow and the move
    # (seeded: measured as attack pc, attack c1, move pc, then the thug's own turn).
    aoo = [i for i, (op, who) in enumerate(mine) if op == "attack" and who == "c1"]
    assert aoo and mine.index(("attack", "pc")) < aoo[0] < mine.index(("move", "pc")), mine
    assert not c.scene.pc().is_down
    assert list(c.scene.positions["pc"])[:2] == to, "the move did not walk"


def test_a_move_after_a_full_attack_is_refused_in_words(panel):
    """A full attack is a full-round action: "the only movement you can take during a full
    attack is a 5-foot step" (Core Rulebook, Full Attack). Once the plan can be reordered
    the panel can post `[attack it0, attack it1, move]`, which the engine would have run
    — the move op does not ask what the round has spent (rules/coup_de_grace.py names
    this as not built). The door refuses it with nothing done, as it refuses a strike out
    of reach."""
    client, cm = panel
    scene = cm.current().scene
    start = tuple(scene.positions["pc"])[:2]
    to = _square_away(scene)
    r = _post(client, [{"op": "attack", "target": "c1", "params": {"iteration": 0}},
                       {"op": "attack", "target": "c1", "params": {"iteration": 1}},
                       {"op": "move", "params": {"zone": "near", "square": to}}])
    assert r.status_code == 400, r.json()
    said = r.json()["error"]
    assert "full attack" in said and "5-foot step" in said and "Nothing was done" in said
    assert "{" not in said
    assert tuple(cm.current().scene.positions["pc"])[:2] == start
    assert not cm.current().scene.awaiting


def test_a_five_foot_step_after_a_full_attack_is_let_through(panel):
    """The rule's own exception: a 5-foot step may follow the full attack."""
    client, cm = panel
    scene = cm.current().scene
    step = _square_away(scene, steps=1)
    r = _post(client, [{"op": "attack", "target": "c1", "params": {"iteration": 0}},
                       {"op": "attack", "target": "c1", "params": {"iteration": 1}},
                       {"op": "move", "params": {"zone": "near", "square": step}}])
    assert r.status_code == 200, r.json()


def test_a_move_after_a_coup_de_grace_is_refused(panel):
    """A coup de grâce takes the whole round (CRB p.197); a walk after it is refused at
    the door, in words, before the coup is rolled."""
    client, cm = panel
    scene = cm.current().scene
    to = _square_away(scene)
    r = _post(client, [{"op": "attack", "target": "c1", "params": {"coup_de_grace": True}},
                       {"op": "move", "params": {"zone": "near", "square": to}}])
    assert r.status_code == 400, r.json()
    assert "coup de grâce" in r.json()["error"] and "Nothing was done" in r.json()["error"]


def test_a_strike_before_the_move_is_measured_from_where_the_player_stands(panel):
    """Order-aware reach, the server half. A strike ordered BEFORE the move is struck from
    the square the player stands on now. Out of reach there, the engine would close the
    distance itself (a move action) and then walk the declared move as a second one: a
    standard and two moves. Refused instead, naming the fix — put the move first."""
    client, cm = panel
    scene = cm.current().scene
    here = tuple(scene.positions["pc"])[:2]
    # The thug three squares off, then the plan: strike him, then walk up beside him.
    far = None
    for dx, dy in ((3, 0), (-3, 0), (0, 3), (0, -3)):
        sq = (here[0] + dx, here[1] + dy)
        if scene.grid.inside(sq) and scene.grid.passable(sq) \
                and sq not in scene.occupied(ignore="c1"):
            far, beside = sq, (here[0] + dx * 2 // 3, here[1] + dy * 2 // 3)
            break
    if far is None:
        pytest.skip("no open square three away from the player")
    scene.positions["c1"] = far + tuple(scene.positions["c1"][2:3])
    scene.resync_zones()
    cm.current().save()
    r = _post(client, [{"op": "attack", "target": "c1", "params": {}},
                       {"op": "move", "params": {"zone": "near", "square": list(beside)}}])
    assert r.status_code == 400, r.json()
    said = r.json()["error"]
    assert "before the move" in said and "Nothing was done" in said, said
    assert tuple(cm.current().scene.positions["pc"])[:2] == here
    # The same two steps the other way round are the ordinary move-and-strike.
    r = _post(client, [{"op": "move", "params": {"zone": "near", "square": list(beside)}},
                       {"op": "attack", "target": "c1", "params": {}}])
    assert r.status_code == 200, r.json()


# --- the page: the order array, the controls, and Commit turn honouring them -------------

def test_the_plan_keeps_an_order_and_commit_posts_in_it():
    """Page source: the order array on COMBAT, reconciled on every read (`planOrder`), and
    commitTurn building its actions and its words from it rather than from the fixed
    move-swift-frees-standard sequence the owner could not change (2026-11-06)."""
    from pagesource import table_source

    src = table_source()
    assert "order: []," in src and "function planOrder()" in src
    assert "const STEP_RANK = { move: 0, swift: 1, free: 2, standard: 3 };" in src
    body = src[src.index("async function commitTurn("):]
    body = body[:body.index("\n}\n")]
    assert "for (const key of planOrder())" in body
    assert "said.push(step.said)" in body
    # The fixed sequence is gone from the commit: no slot is pushed by name any more.
    assert "if (COMBAT.move) {" not in body and "for (const f of COMBAT.frees)" not in body


def test_the_plan_chips_are_numbered_and_carry_reorder_controls():
    """Page source: numbered chips; earlier/later buttons with aria labels (the table is
    played from a phone over LAN, where HTML5 drag-and-drop never fires); a pointer-event
    drag; and a removal that takes the step out of the order too."""
    from pagesource import table_source

    src = table_source()
    assert 'class="cb-num"' in src
    assert 'data-steporder="${key}:-1" aria-label="Earlier: ${label}"' in src
    assert 'data-steporder="${key}:1" aria-label="Later: ${label}"' in src
    assert 'document.addEventListener("pointerdown"' in src
    assert 'document.addEventListener("pointermove"' in src
    assert 'document.addEventListener("pointercancel"' in src
    assert "touch-action: none" in src
    assert "unplanStep(un.dataset.unplan)" in src
    assert "function unplanStep(key)" in src


def test_the_reach_warning_reads_the_order():
    """Page source: `strikeOutOfReach` measures from the move's end square only when the
    move comes first, and from the square the player stands on when the strike does; the
    quiet notes for a swift/free after the blow and a walk after a full-round action share
    the existing `.cb-warn` style."""
    from pagesource import table_source

    src = table_source()
    fn = src[src.index("function strikeOutOfReach()"):]
    fn = fn[:fn.index("\n}\n")]
    assert 'order.indexOf("move") < order.indexOf("standard")' in fn
    assert "moveFirst ? COMBAT.move : pcSquare()" in fn
    assert "function declaredAfterTheBlow(order)" in src
    assert "function wholeRoundAndMove(order)" in src
    assert '`<span class="cb-warn">${esc(w)}</span>`' in src


NODE = shutil.which("node")

# The page furniture 04 touches as it loads (the Say form) and as the plan draws.
_DOM = r"""
ELS.combatbar = el("combatbar"); ELS["cb-menu"] = el("cb-menu");
ELS["cb-plan"] = el("cb-plan"); ELS["cb-round"] = el("cb-round");
ELS["cb-turn"] = el("cb-turn"); ELS["cb-targets"] = el("cb-targets");
ELS["cb-coup"] = el("cb-coup"); ELS.sayform = el("sayform"); ELS.carryon = el("carryon");
ELS["cb-plan"].querySelector = () => null;
"""

_FIGHT = r"""
STATE = { scene: { in_encounter: true, turn_ref: "pc", round: 1, initiative: [],
  actors: [{ ref: "pc", name: "Kesst", is_pc: true, at: [1, 1], hp: 9, hp_max: 9 },
           { ref: "c1", name: "the thug", hp: 9, hp_max: 9, conditions: [], at: [2, 1] }] },
  pc: { ref: "pc" }, abilities: [], attacks: { reach: { c1: [[1, 1], [3, 1], [2, 2]] },
  sequence: [0, -5], weapons: ["rapier"] } };
const POSTS = [];
async function post(url, body) { POSTS.push({ url, body }); return STATE; }
function render(s) { STATE = s; }
function busy() {}
const strike = () => ({ label: "Strike the thug",
  actions: [{ op: "attack", target: "c1", params: {} }] });
"""


def _page(tmp_path, steps: str) -> dict:
    if NODE is None:
        pytest.skip("node is not installed")
    turns = (TABLE / "04-combat-and-turns.js").read_text(encoding="utf-8")
    turns = turns[:turns.index("/* ---- The full character sheet")]
    f = tmp_path / "plan.js"
    f.write_text(PRELUDE + _DOM + turns + "\n" + _FIGHT + "\n" + steps, encoding="utf-8")
    done = subprocess.run([NODE, str(f)], capture_output=True, text=True,
                          encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_left_alone_the_order_is_the_one_always_posted(tmp_path):
    """A player who never reorders posts exactly what was posted before the change:
    move, swift, frees, standard — the order that puts a rage or smite before its blow."""
    got = _page(tmp_path, r"""
COMBAT.target = "c1"; COMBAT.standard = strike(); COMBAT.frees = ["Rage"];
COMBAT.swift = "Smite Evil"; COMBAT.move = [3, 1];
commitTurn(false).then(() => console.log(JSON.stringify(POSTS[0].body)));
""")
    assert [(a["op"], (a.get("params") or {}).get("ability")) for a in got["actions"]] == [
        ("move", None), ("use_ability", "Smite Evil"), ("use_ability", "Rage"),
        ("attack", None)]
    assert got["label"] == "move to (3,1); swift: Smite Evil; free: Rage; strike the thug"


def test_strike_then_move_is_posted_in_that_order(tmp_path):
    """The owner's turn: Strike, then the Earlier arrow on the strike (a click through the
    page's own listener), then Commit — `[attack, move]`, and the words follow it."""
    got = _page(tmp_path, r"""
COMBAT.target = "c1"; COMBAT.move = [3, 1]; COMBAT.standard = strike(); renderPlan();
const before = COMBAT.order.slice();
fire("click", { closest: s => s === "[data-steporder]"
  ? { dataset: { steporder: "standard:-1" } } : null });
const after = COMBAT.order.slice(); const html = ELS["cb-plan"].innerHTML;
commitTurn(false).then(() => console.log(JSON.stringify({ before, after, html,
  body: POSTS[0].body })));
""")
    assert got["before"] == ["move", "standard"] and got["after"] == ["standard", "move"]
    assert [a["op"] for a in got["body"]["actions"]] == ["attack", "move"]
    assert got["body"]["label"] == "strike the thug; move to (3,1)"
    # Numbered in the new order.
    html = got["html"]
    assert html.index('data-step="standard"') < html.index('data-step="move"')
    assert 'aria-label="Step 1 of 2: Strike the thug"' in html
    assert 'aria-label="Step 2 of 2: Move to 3,1"' in html


def test_a_new_step_joins_where_it_always_went_and_removal_leaves_the_order(tmp_path):
    """A swift staged into "strike, then move" goes before the strike; a free removed
    takes its key out of the order and the frees after it close up; a drop by the drag
    (`placeStep`) puts a step where it fell."""
    got = _page(tmp_path, r"""
COMBAT.target = "c1"; COMBAT.move = [3, 1]; COMBAT.standard = strike(); planOrder();
placeStep("move", 2);  // the drag: the move dropped after the strike
const dragged = COMBAT.order.slice();
COMBAT.swift = "Smite Evil"; const joined = planOrder().slice();
COMBAT.frees = ["Rage", "Ki Dodge"]; planOrder(); placeStep("free:1", 99);
const withFrees = COMBAT.order.slice();
unplanStep("free:0"); const removed = planOrder().slice();
console.log(JSON.stringify({ dragged, joined, withFrees, removed, frees: COMBAT.frees }));
""")
    assert got["dragged"] == ["standard", "move"]
    assert got["joined"] == ["swift", "standard", "move"]
    assert got["withFrees"] == ["swift", "free:0", "standard", "move", "free:1"]
    assert got["removed"] == ["swift", "standard", "move", "free:0"]
    assert got["frees"] == ["Ki Dodge"]


def test_the_plan_warns_by_the_order_it_will_run_in(tmp_path):
    """The quiet notes, on the page's own functions. From (1,1) the thug at (2,1) is in
    reach; from (5,5) he is not. A strike placed before a move to (5,5) is fine — it is
    struck from (1,1); after it, it is not. A rage after the strike is said; a full attack
    followed by a walk is said; nothing is blocked."""
    got = _page(tmp_path, r"""
COMBAT.target = "c1"; COMBAT.move = [5, 5]; COMBAT.standard = strike(); planOrder();
const moveFirst = strikeOutOfReach();
placeStep("standard", 0); const strikeFirst = strikeOutOfReach();
STATE.scene.actors[0].at = [5, 5]; const strikeFirstFar = strikeOutOfReach();
STATE.scene.actors[0].at = [1, 1];
COMBAT.frees = ["Rage"]; planOrder(); placeStep("free:0", 99);
const late = declaredAfterTheBlow(COMBAT.order);
COMBAT.frees = [];
COMBAT.standard = { label: "Full attack: weapon, weapon on the thug", actions: [
  { op: "attack", target: "c1", params: { iteration: 0 } },
  { op: "attack", target: "c1", params: { iteration: 1 } }] };
const full = wholeRoundAndMove(planOrder());
COMBAT.move = [2, 2]; const step = wholeRoundAndMove(planOrder());
renderPlan(); const html = ELS["cb-plan"].innerHTML;
console.log(JSON.stringify({ moveFirst, strikeFirst, strikeFirstFar, late, full, step, html }));
""")
    assert "From 5,5 the strike will not reach the thug" in got["moveFirst"]
    assert got["strikeFirst"] == "", "struck from (1,1), beside the thug"
    assert "comes before the move" in got["strikeFirstFar"]
    assert got["late"].startswith("Rage comes after the attack")
    assert "A full attack takes the whole round" in got["full"] and "5-foot step" in got["full"]
    assert got["step"] == "", "a 5-foot step after a full attack is the rule's own exception"
    assert 'role="alert"' not in got["html"], "the order notes are quiet"
