"""The exits row attaches, and the words say when the move happens (owner, 2026-09-29).

Two requests, the same day:
  * "when you click a next door button it should attach like a spell does and then apply
    when you send". Measured before: a click on the "From here" row sent "I go to <name>."
    at once (`goToExit` -> `takeTurn`), and a journey or any way out of a fight opened a
    confirm line that a second click answered. Now a click attaches a place chip in the
    spell chip's own slot, and Say sends it; the confirm line's sentence is the line
    held visibly under the chip.
  * "i think the interpreter should be able to see where in the described action the
    move should take place same with spells". Measured before: any words beside a place
    were a 400 ("a place from the exits row is a turn of its own"), because the click went
    straight to the engine and words beside a move had been silently ignored; and an
    attached cast was appended after whatever the plan held, so "I cast burning hands,
    then tell the man to run" warned him first and burned him after. Now the line is cut
    into clauses in the order of doing (gm/sequence.py): what comes before the move runs
    here, the move goes to the chip's place, and what comes after is planned again at the
    destination, stopping the chain as Zork's parser did when a part cannot run.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from django.test import Client, override_settings

import _exits_dom as exits_dom
from gm import judgement, sequence
from play import exits as exits_mod
from rules import outskirts
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from test_i6_exits import _with_a_ring

needs_node = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not on this machine")


# --- the page: a click attaches ------------------------------------------------------------

@needs_node
def test_a_click_attaches_and_sends_nothing_and_a_second_click_takes_it_back(tmp_path):
    """The defect the owner named: a click on "the arena" sent a turn at once. Now the
    click attaches a Go chip before the input, the pressed way says so (`aria-pressed`),
    the placeholder asks how, nothing is sent; the same way pressed again removes it."""
    state = exits_dom.exits_state(False)
    got = exits_dom.run(tmp_path, f"""
      renderAll({json.dumps(state)});
      click("p:arena");
      const chip = ELS.attachments.innerHTML, hidden = ELS.attachments.hidden;
      const holder = ELS.input.placeholder, sent = SENT.length;
      renderAll({json.dumps(state)});
      const row = BOX.innerHTML;
      click("p:arena");
      done(() => ({{ chip, hidden, holder, sent, row, after: ELS.attachments.innerHTML,
              afterHolder: ELS.input.placeholder, said: ELS.saystatus.textContent }}));
    """)
    assert got["sent"] == 0
    assert not got["hidden"]
    assert 'data-kind="place"' in got["chip"] and ">Go<" in got["chip"]
    assert 'aria-label="Remove the arena"' in got["chip"]
    assert got["holder"] == "How do you go to the arena? Or just press Say."
    arena = re.search(r'<button[^>]*data-exit="p:arena"[^>]*>', got["row"]).group(0)
    assert 'aria-pressed="true"' in arena
    road = re.search(r'<button[^>]*data-exit="r:north"[^>]*>', got["row"]).group(0)
    assert 'aria-pressed="false"' in road
    assert got["after"] == "" and got["afterHolder"] == "What do you do?"
    assert got["said"] == "the arena removed."


@needs_node
def test_a_journey_chip_says_its_days_and_sends_confirmed(tmp_path):
    """The journey's confirm line ("about three days on foot; the days pass") was a second
    click. The chip is the confirmation now: its line says the days, visibly, and Say
    carries `confirmed`, which the server still demands of a journey."""
    got = exits_dom.run(tmp_path, f"""
      renderAll({json.dumps(exits_dom.exits_state(False))});
      click("r:north");
      ELS.input.value = "I shoulder my pack";
      done({{ html: ELS.attachments.innerHTML, say: sayBody() }});
    """)
    assert ">Journey<" in got["html"]
    assert '<span class="att-note" id="att-note">About three days on foot; the days pass ' \
           'on the road.</span>' in got["html"]
    assert got["say"] == {"text": "I shoulder my pack", "attachments": [
        {"kind": "place", "id": "r:north", "confirmed": True}]}


@needs_node
def test_a_place_replaces_a_spell_and_a_spell_replaces_a_place(tmp_path):
    """One attachment a turn, as the server holds (`_read_attachments`). A place pressed
    with Burning Hands attached takes its slot and says so, and a spell picked with a
    place attached takes the place's; `window.attachSpellChip` still works."""
    got = exits_dom.run(tmp_path, f"""
      renderAll({json.dumps(exits_dom.exits_state(False))});
      window.attachSpellChip("burning-hands", "Burning Hands");
      click("p:arena");
      setTimeout(() => {{
        const one = ELS.saystatus.textContent, first = currentAttachments();
        attachSpell({{ id: "magic-missile", name: "Magic Missile" }});
        setTimeout(() => done({{ one, first, two: ELS.saystatus.textContent,
                                 second: currentAttachments() }}), 60);
      }}, 60);
    """)
    assert got["first"] == [{"kind": "place", "id": "p:arena", "name": "the arena"}]
    assert got["one"].startswith("the arena attached in place of Burning Hands.")
    assert got["second"] == [{"kind": "spell", "id": "magic-missile",
                              "name": "Magic Missile"}]
    assert got["two"].startswith("Magic Missile attached in place of the arena.")


@needs_node
def test_the_place_chip_comes_off_as_a_spell_chip_does(tmp_path):
    """The spell chip's ✕, its two-press Backspace (Vuetify #3069: chips eaten by the
    Backspace meant for a letter) and Esc take a place chip off the same way; Esc from the
    row takes back what the row attached, as it used to close the row's confirm line."""
    state = json.dumps(exits_dom.exits_state(False))
    got = exits_dom.run(tmp_path, f"""
      renderAll({state});
      click("p:arena"); clickX();
      const byX = currentAttachments().length;
      click("p:arena"); key("Backspace", "#input");
      const armed = ELS.attachments.innerHTML.includes("armed"), stillOn = currentAttachments().length;
      key("Backspace", "#input");
      const byBack = currentAttachments().length;
      click("p:arena"); key("Escape", "#exits");
      const byEsc = currentAttachments().length;
      click("p:arena"); key("Backspace", "#input"); key("Escape", "#input");
      done({{ byX, armed, stillOn, byBack, byEsc, byArmedEsc: currentAttachments().length }});
    """)
    assert got == {"byX": 0, "armed": True, "stillOn": 1, "byBack": 0, "byEsc": 0,
                   "byArmedEsc": 0}


@needs_node
def test_a_shut_way_attaches_nothing_and_a_way_that_shut_takes_its_chip_off(tmp_path):
    """A shut way stays in the row with its reason and cannot be attached; a chip whose
    way has shut since (a warrant came out) comes off with the rules' own sentence,
    rather than being sent to be refused."""
    open_state = exits_dom.exits_state(False)
    shut = json.loads(json.dumps(open_state))
    shut["scene"]["exits"][0]["blocked"] = "The watch stands at the arena's gate."
    got = exits_dom.run(tmp_path, f"""
      renderAll({json.dumps(open_state)});
      const btn = {{ dataset: {{ exit: "p:gate" }}, getAttribute: () => "true" }};
      fire("click", {{ closest: sel => sel.includes(".exitbtn") ? btn : null }});
      const gate = currentAttachments().length;
      click("p:arena");
      renderAll({json.dumps(shut)});
      done(() => ({{ gate, left: currentAttachments().length,
                     said: ELS.saystatus.textContent }}));
    """)
    assert got["gate"] == 0
    assert got["left"] == 0
    assert got["said"] == "the arena is shut: The watch stands at the arena's gate."


@needs_node
def test_somebody_who_does_not_cast_keeps_a_place_chip(tmp_path):
    """10-spells.js clears the slot when the character casts nothing, so a fighter's
    place chip would have vanished on the next render. It clears only a spell."""
    state = exits_dom.exits_state(False)
    state["spellcasting"] = None
    got = exits_dom.run(tmp_path, f"""
      renderAll({json.dumps(state)});
      click("p:arena");
      renderAll({json.dumps(state)});
      done({{ n: currentAttachments().length }});
    """)
    assert got["n"] == 1


def test_on_a_desktop_the_chip_line_is_held_open_so_the_row_does_not_move():
    """The owner's motion rule. Measured 2026-09-29 at 1722x855: `main` is a flex column
    with the footer at the bottom, so the chip appearing in the say form lifted the row
    44px (704 to 660) and a second press meant to take it back landed on the Outside
    group. With the line held open while the row is shown, the same press measured 0px
    for a Go chip and 1px for a Withdraw chip with its line, at 1722 and at 1024 wide.

    Since the table rebuild the row and the pen are both in the desk at the foot of the
    stage, where growth goes upward just as it did in the footer; the rule is written
    for the desk (`.desk:has(#exits:not([hidden]))`) instead of for the row's next
    sibling."""
    page = (Path(__file__).resolve().parent.parent
            / "play" / "templates" / "play" / "table.html").read_text(encoding="utf-8")
    held = ".desk:has(#exits:not([hidden])) #sayform > #attachments"
    block = page[page.index("@media (min-width: 761px) {\n    " + held):]
    block = block[:block.index("\n  }\n")]
    assert held + " {" in block
    assert "min-height: 42px" in block
    assert "#attachments[hidden] { visibility: hidden; }" in block


def test_nothing_sends_an_exit_straight_to_the_table_any_more():
    """Traced before changing it: the one sender of `{kind: "place"}` on the page was
    11-exits.js's `goToExit`, and the map tray's biome picker posts to /api/travel, not
    through the exits. After: no script posts a place itself; the chip rides Say."""
    root = Path(__file__).resolve().parent.parent / "play" / "static" / "js" / "table"
    code = "\n".join(p.read_text(encoding="utf-8") for p in sorted(root.glob("*.js")))
    assert "goToExit" not in code and "exits-confirm" not in code
    assert not re.search(r"takeTurn\([^)]*kind:\s*\"place\"", code)


# --- the order of doing, in code ------------------------------------------------------------

def test_the_clauses_are_read_in_the_order_they_are_done():
    """"After I X, I Y" and "Before I Y, I X" are written in one order and done in the
    other; "then", full stops and an "and" before a new verb separate; "bread and cheese"
    and quoted speech stay whole."""
    assert sequence.clauses("After I cast sleep on the guard, I run for the gate") == \
        ["I cast sleep on the guard", "I run for the gate"]
    assert sequence.clauses("Before I run for the gate, I cast sleep on the guard") == \
        ["I cast sleep on the guard", "I run for the gate"]
    assert sequence.clauses("I buy a waterskin, then head to the market") == \
        ["I buy a waterskin", "head to the market"]
    assert sequence.clauses("I go to the market and buy bread and cheese") == \
        ["I go to the market", "buy bread and cheese"]
    assert sequence.clauses('"Farewell. Be well," I say, and leave') == \
        ['"Farewell. Be well," I say', "leave"]
    assert sequence.clauses("I run after the thief") == ["I run after the thief"]
    assert sequence.joined(["head to the market", "buying bread"]) == \
        "I head to the market. I buy bread."


def test_no_clause_that_is_the_move_puts_it_last():
    """Leaving is what usually ends a turn: "I nod to the watchman" beside a chip for the
    gate nods and then goes. `move_clause` answers None, and the move is appended last."""
    assert sequence.move_clause(["I nod to the watchman"], "the gate") is None
    assert sequence.move_clause(["I buy bread", "I head out"], "the gate") == 1
    assert sequence.move_clause(["I leave the inn", "I walk to the gate"], "the gate") == 1


def _scene_with_a_man():
    s = Scene(location_id="nowhere")
    pc = load_pc("fixtures/pc-thessaly.json")
    s.add(pc)
    man = s.add(instantiate("guildhand", scene=s, name="the man"))
    return s, pc, man


def test_the_attached_cast_lands_where_the_words_put_it_not_at_the_end():
    """Before: `_cast_the_attached` appended a cast the plan lacked after everything else,
    so "I cast burning hands at the man, then tell him to run" spoke first and burned
    after. Now the cast sits at its clause, both when the plan left it out and when the
    plan wrote it in the wrong place."""
    s, pc, man = _scene_with_a_man()
    chip = [{"kind": "spell", "id": "burning-hands", "name": "Burning Hands"}]
    say = {"op": "say", "actor": pc.ref, "target": man.ref, "params": {"words": "run"}}
    got = judgement.order_the_attached(
        [dict(say)], "I cast burning hands at the man, then tell him to run", s, chip)
    assert [r["op"] for r in got] == ["cast", "say"]
    cast = {"op": "cast", "actor": pc.ref, "params": {"spell": "burning-hands"}}
    got = judgement.order_the_attached(
        [dict(cast), dict(say)], "I warn the man, then cast burning hands at him", s, chip)
    assert [r["op"] for r in got] == ["say", "cast"]
    # "after I cast, I say" is the cast first, whatever order the plan wrote.
    got = judgement.order_the_attached(
        [dict(say), dict(cast)], "After I cast burning hands, I tell the man to run", s, chip)
    assert [r["op"] for r in got] == ["cast", "say"]


def test_the_place_chip_decides_where_and_the_move_goes_last():
    """The chip beats the words and the model on WHERE, as the spell chip does on which
    spell: a plan's travel to the ground its words named, and a second travel, become the
    one move to the chip's place, after everything done here; a journey chip is a
    `journey` at the chip's pace; and the declared ops ask for the move up front."""
    s, pc, man = _scene_with_a_man()
    chip = [{"kind": "place", "id": "p:market", "name": "the market", "journey": False}]
    say = {"op": "say", "actor": pc.ref, "target": man.ref, "params": {"words": "bye"}}
    raw = [{"op": "travel", "actor": pc.ref, "params": {"biome": "forest"}}, dict(say),
           {"op": "travel", "actor": pc.ref, "params": {"place": "p:elsewhere"}}]
    got = judgement.travel_to_the_attached(raw, s, chip)
    assert [(r["op"], r.get("params")) for r in got] == [
        ("say", {"words": "bye"}), ("travel", {"place": "p:market"})]
    assert judgement.travel_to_the_attached(got, s, chip) == got, "idempotent"
    road = [{"kind": "place", "id": "r:north", "name": "the north road", "journey": True,
             "pace": "ride"}]
    got = judgement.travel_to_the_attached([], s, road)
    assert got[0]["op"] == "journey" and got[0]["params"] == {"to": "r:north", "pace": "ride"}
    assert "travel" in judgement.declared_ops("I nod to the man", s, attached=chip)
    assert "journey" in judgement.declared_ops("I nod to the man", s, attached=road)


def test_the_planner_holds_its_travel_to_the_chip(monkeypatch):
    """Through the real `plan_turn` chain, the model answering with a walk to the forest:
    the plan that comes out moves to the chip's place, by the engine's id, and nothing
    else — `travel_to_the_attached` runs in the chain, and again last."""
    import json as _json

    from gm import agent as agent_mod
    from _a_truth import MARKET, VORMOOR, WORLD

    s = Scene(location_id=VORMOOR.id)
    s.add(load_pc("fixtures/pc-thessaly.json"))
    e = Engine(s, Dice(seed=5), world=WORLD)
    e.place_party(MARKET)
    way = next(x for x in exits_mod.exits(e, WORLD) if not x["journey"] and not x["blocked"])

    class _Reply:
        text = _json.dumps({"narration": "", "intents": [
            {"op": "travel", "actor": "pc", "params": {"biome": "forest"}}]})
        seconds, model = 0.0, "fake"

        def json(self):
            return _json.loads(self.text)

    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply())
    gm = agent_mod.GMAgent(WORLD, e)
    gm.attachments = ({"kind": "place", "id": way["id"], "name": way["name"],
                       "journey": False},)
    plan = gm.plan_turn("I nod to the stallholders", history=[])
    assert [(i.op, i.params.get("place")) for i in plan.intents] == [("travel", way["id"])]


# --- the server: one turn, cut at the move --------------------------------------------------

@pytest.fixture
def desk(worlds, tmp_path, monkeypatch):
    """A campaign in this world, the narrator stubbed, and the planner stubbed to record
    what it was asked, where the party stood when it was asked, and with what chip — and
    to answer with the chip's move when there is one (the real `travel_to_the_attached`),
    or with the refusal a test sets for a line."""
    from gm import client as gm_client
    from gm import watcher
    from gm.agent import TurnPlan
    from play import campaign as cm
    from play import concurrency, views

    monkeypatch.setattr(watcher, "kick", lambda c: None)
    calls = {"plans": [], "refuse": "", "degrade": False}

    def plan(agent, text, *a, **kw):
        scene = agent.engine.scene
        chips = tuple(getattr(agent, "attachments", ()) or ())
        calls["plans"].append({"text": text, "at": scene.at, "chips": chips})
        agent.last_said = []
        if calls["degrade"]:
            # What `plan_turn` hands back when every attempt was refused: a narrated
            # nothing, with the chip's move nowhere in it.
            return TurnPlan(narration="You look, and the moment does not answer.",
                            intents=agent.engine.validate(
                                [{"op": "narrate_only",
                                  "because": "the turn could not be shaped"}]),
                            repairs=["turn degraded to narration after 7 failed attempts"])
        if calls["refuse"] and calls["refuse"] in text:
            made = TurnPlan(narration="", intents=agent.engine.validate(
                [{"op": "narrate_only", "because": "t"}]))
            made.refusal = {"text": "Nobody here answers to that.", "code": "t",
                            "fix": None}
            return made
        raw = judgement.order_the_attached([], text, scene, chips) or \
            [{"op": "narrate_only", "because": "t"}]
        return TurnPlan(narration="", intents=agent.engine.validate(raw))

    def chat(*a, **k):
        class R:
            text = json.dumps({"narration": "The way goes by underfoot. " * 6,
                               "suggestions": ["I look around"]})
            seconds, model, prompt_tokens, reply_tokens, done_reason = 0.0, "s", 0, 0, "stop"

            def json(self):
                return json.loads(self.text)
        return R()

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    monkeypatch.setattr(gm_client, "chat", chat)
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.begin_with(load_pc("fixtures/pc-thessaly.json"),
                          world_source=str(Path(worlds.source)))
        # Alone at the way in of a settlement with a ring (I6's own `stand`): Pangrella's
        # drawn start is an ambush on a road, with no next door at all.
        if c.scene.in_encounter:
            c.scene.end_encounter()
        pc = c.scene.pc()
        for ref in [r for r in c.scene.people if r != pc.ref]:
            c.scene.people.pop(ref)
        c.scene.location_id = next(_with_a_ring(worlds)).id
        c.scene.road = {}
        c.engine().place_party("")
        c.save()
        yield {"c": c, "calls": calls}
        cm._LIVE.clear()


def _way(c):
    row = Client().get("/api/state").json()["scene"]["exits"]
    return next(x for x in row if x["group"] == "next_door" and not x["blocked"]
                and x["name"] != outskirts.OUTSKIRTS)


def _say(text, way):
    return Client().post("/api/say", content_type="application/json", data=json.dumps(
        {"text": text, "attachments": [{"kind": "place", "id": way["id"]}]}))


def _players(c):
    return [b for b in c.transcript if b["who"] == "player"]


def test_manner_words_take_the_engines_door_and_reach_the_narrator(worlds, desk):
    """"I slip out quietly" beside a chip: before, a 400 ("a turn of its own"); the words
    had been silently ignored when they were let through. Now it is the move and its
    manner: no planner asked (it reads as a Stealth check, which is how one goes), the
    party at the chip's place, the words on the beat with the place chip drawn so the
    beat still says where, and the words handed to the narrator as the player's line."""
    c = desk["c"]
    way = _way(c)
    r = _say("I slip out quietly", way)
    assert r.status_code == 200, r.content[:300]
    assert desk["calls"]["plans"] == []
    assert c.scene.at == way["id"]
    beat = _players(c)[-1]
    assert beat["text"] == "I slip out quietly"
    assert [(a["kind"], a["id"]) for a in beat["attachments"]] == [("place", way["id"])]
    assert "I slip out quietly." in [h["content"] for h in c.history if h["role"] == "user"]


def test_go_then_ask_is_planned_again_at_the_destination(worlds, desk):
    """"I walk to the market and ask after the smith": the walk, then the asking, AT the
    market, against its people — validation reads the scene as it stands, so one intent
    list could only have asked the people being left. The walk takes the engine's door;
    the rest is a second plan, made with the party already there, on a line of its own."""
    c = desk["c"]
    way = _way(c)
    r = _say(f"I walk to {way['name']} and ask after the smith", way)
    assert r.status_code == 200, r.content[:300]
    assert c.scene.at == way["id"]
    plans = desk["calls"]["plans"]
    assert [(p["text"], p["at"], p["chips"]) for p in plans] == \
        [("I ask after the smith.", way["id"], ())]
    texts = [b["text"] for b in _players(c)[-2:]]
    assert texts == [f"I walk to {way['name']}.", "I ask after the smith."]
    assert "unfinished" not in r.json()


def test_a_refused_remainder_stops_the_chain_and_comes_back_to_the_pen(worlds, desk):
    """Zork cleared the rest of the line when a command in it failed (gmain.zil, P-CONT).
    The move stands, the refused remainder leaves no beat, and it is not dropped: the
    response carries it for the pen with "You are at <place>. Not yet done: ..."."""
    c = desk["c"]
    way = _way(c)
    desk["calls"]["refuse"] = "smith"
    r = _say(f"I walk to {way['name']}, then ask after the smith", way)
    assert r.status_code == 200, r.content[:300]
    assert c.scene.at == way["id"]
    left = r.json()["unfinished"]
    assert left["text"] == "I ask after the smith."
    assert left["keep_chip"] is False
    assert left["line"] == f"You are at {c.engine().here().name}. Not yet done: " \
                           f"ask after the smith."
    assert left["why"] == "Nobody here answers to that."
    assert _players(c)[-1]["text"] == f"I walk to {way['name']}."


def test_words_before_the_move_are_done_here_and_the_move_goes_last(worlds, desk):
    """"I wave to the crowd, then head to <place>": one plan, here, with the place chip —
    and the plan's last intent is the move to the chip's place (the stub answers with the
    real `order_the_attached`)."""
    c = desk["c"]
    way = _way(c)
    start = c.scene.at
    r = _say(f"I wave to the crowd, then head to {way['name']}", way)
    assert r.status_code == 200, r.content[:300]
    (plan,) = desk["calls"]["plans"]
    assert plan["text"] == f"I wave to the crowd. I head to {way['name']}."
    assert plan["at"] == start and plan["chips"][0]["id"] == way["id"]
    assert c.scene.at == way["id"]
    turn = [e for e in c.turn_log if e.get("kind") == "turn"][-1]
    assert (turn["intents"][-1]["op"], turn["intents"][-1]["params"].get("place")) == \
        ("travel", way["id"])


def test_a_purchase_before_the_move_stops_there_and_keeps_the_chip(worlds, desk):
    """"I buy a loaf of bread, then go to <place>": the purchase is made on the counter's
    screen after the beat (the owner's ruling, 2026-09-27), so walking off in the same
    turn would open the next place's counter. The buying is planned here, nobody moves,
    and the move comes back to the pen with the chip still attached."""
    c = desk["c"]
    way = _way(c)
    start = c.scene.at
    r = _say(f"I buy a loaf of bread, then go to {way['name']}", way)
    assert r.status_code == 200, r.content[:300]
    (plan,) = desk["calls"]["plans"]
    assert (plan["text"], plan["at"], plan["chips"]) == ("I buy a loaf of bread.", start, ())
    assert c.scene.at == start
    left = r.json()["unfinished"]
    assert left["keep_chip"] is True and left["text"] == f"I go to {way['name']}."
    assert "attachments" not in _players(c)[-1], "the chip was not spent"


def test_no_clause_is_the_move_so_it_comes_last(worlds, desk):
    """"I nod to the watchman" beside a chip names no going: the nod is planned here and
    the move goes after it, because leaving usually ends a turn."""
    c = desk["c"]
    way = _way(c)
    r = _say("I nod to the watchman", way)
    assert r.status_code == 200, r.content[:300]
    (plan,) = desk["calls"]["plans"]
    assert plan["text"] == "I nod to the watchman." and plan["chips"][0]["id"] == way["id"]
    assert c.scene.at == way["id"]


# --- the silent drop, measured live 2026-09-29 -----------------------------------------------
#
# Borin at the crossroads, "the outskirts" attached, "I search the crossroads for tracks,
# then head out": five gemma attempts refused "check: unknown actor None", two fallback
# attempts refused on a placeholder, the turn degraded to `narrate_only`, the search was
# narrated, the party never moved, and the page cleared the chip and the words.

def _agent_at_the_market(monkeypatch, reply: dict):
    import json as _json

    from gm import agent as agent_mod
    from _a_truth import MARKET, VORMOOR, WORLD

    s = Scene(location_id=VORMOOR.id)
    s.add(load_pc("fixtures/pc-thessaly.json"))
    e = Engine(s, Dice(seed=5), world=WORLD)
    e.place_party(MARKET)
    calls = []

    class _Reply:
        text = _json.dumps(reply)
        seconds, model = 0.0, "fake"

        def json(self):
            return _json.loads(self.text)

    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: calls.append(1) or _Reply())
    way = next(x for x in exits_mod.exits(e, WORLD) if not x["journey"] and not x["blocked"])
    return agent_mod.GMAgent(WORLD, e), way, calls


@pytest.mark.parametrize("chip", [True, False], ids=["with-chip", "no-chip"])
def test_a_check_the_player_declared_is_the_pcs_whatever_the_model_left_out(
        monkeypatch, chip):
    """Defect 1. "check: unknown actor None", five attempts of five. The schema asks for
    the declared ops as required keys of `declared`, whose bodies carry no actor, and
    `_merge_declared` put a `check` built from one into the intents with none; the engine
    refuses a check without an actor (`_check_refs`), and a refs refusal regenerates, so
    every attempt died the same way. NOT the chip's doing: the merge is unchanged since
    f6781a7 and the same reply fails the same way with no chip (the `no-chip` case). Now
    a declared check, and a check the model wrote with no actor for words that declare
    one, are the PC's, as `inject_checks` makes them."""
    gm, way, calls = _agent_at_the_market(monkeypatch, {
        "narration": "", "declared": {"check": {"params": {"skill": "perception"}}},
        "intents": []})
    if chip:
        gm.attachments = ({"kind": "place", "id": way["id"], "name": way["name"],
                           "journey": False},)
    plan = gm.plan_turn("I search the stalls for tracks, then head out", history=[])
    assert len(calls) == 1, plan.rejections
    checks = [i for i in plan.intents if i.op == "check"]
    assert checks and checks[0].actor == "pc"
    assert not any("degraded" in r for r in plan.repairs)
    gm, way, calls = _agent_at_the_market(monkeypatch, {
        "narration": "", "intents": [{"op": "check", "params": {"skill": "perception",
                                                                "dc": 15}}]})
    plan = gm.plan_turn("I search the stalls for tracks", history=[])
    assert [(i.op, i.actor) for i in plan.intents][:1] == [("check", "pc")], plan.rejections


def test_a_degraded_plan_does_not_swallow_the_place_chip(worlds, desk):
    """Defect 2. The degraded plan (`narrate_only`, every attempt refused) answered 200:
    the search narrated, the party still at the crossroads, no `unfinished`, and the page
    cleared the chip and the words. The chain rule decides it: the words before the move
    are the first command and failed, and a failed command stops the rest (Zork's
    P-CONT), so the move does not run; nor is the failed command narrated, since the
    words go back to be sent again. Nothing runs: a 422 with no beat and no clock, the
    party where it was, and the sentence says the place is still attached."""
    c = desk["c"]
    way = _way(c)
    start, was, clock = c.scene.at, len(c.transcript), c.scene.clock_minutes
    desk["calls"]["degrade"] = True
    r = _say(f"I search the crossroads for tracks, then head for {way['name']}", way)
    assert r.status_code == 422, r.content[:300]
    body = r.json()
    assert body["refusal"]["code"] == "unshaped"
    assert f"{way['name']} is still attached" in body["error"]
    assert c.scene.at == start and len(c.transcript) == was and c.scene.clock_minutes == clock


def test_a_degraded_plan_does_not_swallow_a_spell_chip():
    """The same rule for spells: a plan without the attached cast is refused before it
    runs, so a cast that did not happen is never narrated and then cleared."""
    from gm.agent import TurnPlan
    from play import views

    s, pc, man = _scene_with_a_man()
    e = Engine(s, Dice(seed=3))
    chip = ({"kind": "spell", "id": "burning-hands", "name": "Burning Hands"},)
    nothing = TurnPlan(narration="", intents=e.validate([{"op": "narrate_only",
                                                          "because": "t"}]))
    refusal = views._attached_not_planned(nothing, chip)
    assert refusal["code"] == "unshaped"
    assert "Burning Hands was not cast and is still attached" in refusal["text"]
    assert views._attached_not_planned(nothing, ()) is None, "no chip: degrade as ever"


def test_a_move_the_engine_refused_comes_back_with_the_chip(worlds, desk, monkeypatch):
    """The plan held the move and the engine refused it when it ran (the watch at the
    gate, a way shut since the page drew it). The words before it ran; the move and the
    rest come back to the pen with the chip, and the engine's sentence says why."""
    from rules.engine import Engine as _Engine, Outcome

    def refused(self, intent, partial):
        return Outcome(intent_id=intent.id, op="travel", status="refused",
                       tell="The watch turns you back at the gate.", because=intent.because)

    monkeypatch.setattr(_Engine, "_op_travel", refused)
    c = desk["c"]
    way = _way(c)
    start = c.scene.at
    r = _say(f"I wave to the crowd, then head to {way['name']}", way)
    assert r.status_code == 200, r.content[:300]
    assert c.scene.at == start
    left = r.json()["unfinished"]
    assert left["keep_chip"] is True
    assert left["text"] == f"I head to {way['name']}."
    assert left["why"] == "The watch turns you back at the gate."


def _quiet_ways(monkeypatch):
    from rules import ontheway

    monkeypatch.setattr(ontheway, "street", lambda dice, level=1: None)
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)


def _walk(c, place_id):
    e = c.engine()
    e.run(e.validate([{"op": "travel", "actor": c.scene.pc().ref, "because": "t",
                       "params": {"place": place_id}}], origin="author:test"))
    c.save()


def test_a_far_chip_walks_the_whole_way_in_one_turn(worlds, desk, monkeypatch):
    """Item 9 (b) of the 2026-09-30 playtest: a place chip had to be one of the ways on
    from here, so the Map tab's Walk there attached one leg a turn — and the owner ruled
    "I should not be forced to play a whole turn for each connecting point." A place the
    chart can walk to through places the party has been (ruling C2) is a chip now, and
    one Say walks every hop of it, through the engine's own door with no planner asked:
    one player beat, the party at the far end, the places between on the tell's route."""
    from play import places_found

    _quiet_ways(monkeypatch)
    c = desk["c"]
    start = c.scene.at
    near = _way(c)
    _walk(c, near["id"])           # stood in once, so the places beyond it are charted
    _walk(c, start)
    chart = places_found.chart(c.engine(), c.world)
    far = next((n for n in chart["nodes"]
                if n["walk"] and len(n["walk"]["legs"]) >= 2), None)
    if far is None:
        pytest.skip("nothing two ways off by the ways known, in this town")
    assert far["id"] not in {x["id"] for x in exits_mod.exits(c.engine(), c.world)}
    beats = len(_players(c))
    r = _say("", far)
    assert r.status_code == 200, r.content[:300]
    assert c.scene.at == far["id"], "the far chip did not take the party the whole way"
    assert len(_players(c)) == beats + 1, "one Say, one turn"
    assert desk["calls"]["plans"] == []
    walked = next(o for o in reversed(c.scene.log) if o.get("op") == "travel")
    assert walked["effects"][0]["went_by"], "the places between are on the route"


def test_a_chip_for_a_place_under_the_fog_is_refused_without_naming_it(worlds, desk):
    """Far, but not anywhere: a place the party has not reached by the ways it knows is
    refused at the door (`_read_place`), the party does not move, and the refusal does not
    name the place — a name in a refusal would lift the fog the chart keeps."""
    from play import places_found

    c = desk["c"]
    start = c.scene.at
    chart = places_found.chart(c.engine(), c.world)
    found = {n["id"] for n in chart["nodes"]}
    hidden = next((p for p in c.engine().places() if p.id not in found), None)
    if hidden is None:
        pytest.skip("everything is charted from here")
    r = _say("", {"id": hidden.id, "name": hidden.name})
    assert r.status_code != 200 or r.json().get("unfinished")
    assert c.scene.at == start
    assert hidden.name not in r.content.decode("utf-8")


def test_the_ratchet_no_place_turn_ends_without_its_move_or_a_word_about_it(
        worlds, desk, monkeypatch):
    """The net under every path: a 200 for a place chip that did not move the party, owes
    no die, and carries no `unfinished` is turned into one that keeps the chip. Proved by
    a path that forgets (the inner turn answers 200 and moves nobody)."""
    from play import views

    c = desk["c"]
    way = _way(c)
    monkeypatch.setattr(views, "_toward", lambda c, *a, **k: views.JsonResponse(
        views._state(c)))
    r = _say("I head out", way)
    assert r.status_code == 200
    left = r.json()["unfinished"]
    assert left["keep_chip"] is True and left["text"] == "I head out."


@pytest.mark.parametrize("line", [
    "I slip out quietly", "I search the crossroads for tracks, then head out",
    "I walk there and ask after the smith", "I buy a loaf of bread, then go",
    "I nod to the watchman"])
@pytest.mark.parametrize("degrade", [False, True], ids=["plans", "degrades"])
def test_every_place_turn_moves_or_keeps_the_chip(worlds, desk, line, degrade):
    """The invariant, over the shapes a place turn takes and a planner that works or
    gives up: the party moved to the chip's place, or the answer keeps the chip (in
    `unfinished` or a refusal that is not a 200). Never a 200 that moved nobody and
    said nothing — the live defect of 2026-09-29."""
    c = desk["c"]
    way = _way(c)
    desk["calls"]["degrade"] = degrade
    r = _say(line, way)
    moved = c.scene.at == way["id"]
    if r.status_code == 200 and not moved:
        assert r.json()["unfinished"]["keep_chip"] is True, (line, r.json().get("unfinished"))
    elif r.status_code != 200:
        assert c.scene.at != way["id"]


@needs_node
def test_the_page_keeps_the_chip_when_a_200_did_not_move_the_party(tmp_path):
    """The page's own check under the server's: `takeTurn` cleared the chip and the words
    on any 200. Now a 200 after a place chip whose way is still a way on from here (so it
    was not taken), with no die owed and no `unfinished`, keeps both and says so."""
    code = (exits_dom.TABLE / "04-combat-and-turns.js").read_text(encoding="utf-8")
    start = code.index("async function takeTurn(")
    fn = code[start:code.index("\n}\n", start) + 3]
    state = exits_dom.exits_state(False)
    got = exits_dom.run(tmp_path, f"""
      ELS.send = el("send");
      let CLEARED = 0, SHOWN = null;
      const post = async () => ({json.dumps(state)});
      function render() {{}} function busy() {{}} function showDeath() {{}}
      function openTrade() {{}}
      clearAttachments = () => {{ CLEARED += 1; }};
      showUnfinished = u => {{ SHOWN = u; }};
      {fn}
      ELS.input.value = "I search the crossroads for tracks, then head out";
      takeTurn({{ text: ELS.input.value,
                  attachments: [{{ kind: "place", id: "p:arena" }}] }}, true)
        .then(() => done({{ CLEARED, SHOWN, value: ELS.input.value }}));
    """)
    assert got["CLEARED"] == 0
    assert got["value"] == "I search the crossroads for tracks, then head out"
    assert got["SHOWN"]["keep_chip"] is True
