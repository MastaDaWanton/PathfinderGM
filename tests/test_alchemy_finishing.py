"""The alchemy finishing lane (2026-10-07): what the bench-shell lane found live and left.

1. Equipment's Throw posted no target, so the engine refused every press ("Throw the
   Alchemist's fire at somebody, or at a square"), and the combat panel offered no flask;
   only typing "I throw my alchemist's fire at the thug" threw one.
2. A thrown flask's attack outcome carried no `verdict` and no mark, so the log could not
   tell it from anything else and U5's `combat.shatter` could not be wired.
3. An opened pinch (an assay's unit, plan §13.2) was refused at the bench as "a finished
   product cannot go back into the glass".
4. The Equipment tab said "poisons whoever drinks it" of thrown alchemist's fire and of a
   sickening drawback, and offered Drink on an opened pinch of quicksilver.
5. The shelf's empty state pointed nowhere; Bottle's `as`, a catalyst's `aim` and `strip`
   were taken by the server and offered by nothing.

Each test names what was measured.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from django.test import Client, override_settings

from play import alchemy_views
from play import campaign as cm
from play import views
from rules import alchemist as al
from rules import consumables, goods
from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene, _rehydrate
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parent.parent
FIRE = [{"type": "damage", "dice": "1d6", "damage_type": "fire", "route": "struck"},
        {"type": "burning", "dice": "1d6", "rounds": 1, "dc": 15, "smother_bonus": 2,
         "route": "struck"}]


# --- the engine: the splash attack marks itself ------------------------------------------------

def _board(seed=7):
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    pc.stock["flask#1"] = Stock(base="Alchemist's Fire", count=3,
                                specs=[dict(x) for x in FIRE])
    e = Engine(s, Dice(seed=seed))
    e._ensure_encounter("pc")
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (5, 10)
    s.resync_zones()
    return s, e


def _throw(e, face, **params):
    res = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "she throws it",
                             "params": {"item": "flask#1", "how": "throw", **params}}]))
    if res.status != "complete":
        res = e.resume(face=face)
    return res


@pytest.mark.parametrize("face,verdict", [(20, "hit"), (1, "miss")])
def test_a_thrown_flask_attack_carries_a_verdict_and_says_it_was_a_splash(face, verdict):
    """Measured 2026-10-07: `_splash_attack`'s outcome had verdict None and nothing else to
    tell it by, so 04-combat-and-turns.js's attackSounds skipped every throw and the
    `combat.shatter` sound U5 built could not be wired. It now marks itself as an ordinary
    attack does (verdict hit or miss, the AC in `dc`) plus `mode: "splash"`, which survives
    the turn log's round trip and the player-visible copy the page reads."""
    s, e = _board()
    res = _throw(e, face, to="c1")
    attack = next(o for o in res.outcomes if o.op == "attack")
    assert attack.verdict == verdict
    assert attack.mode == "splash"
    assert attack.dc and isinstance(attack.dc.get("value"), int)
    d = attack.as_dict()
    assert d["mode"] == "splash"
    assert _rehydrate(d).mode == "splash"
    seen = views._player_visible_entry({"kind": "turn", "outcomes": [d]})
    assert seen["outcomes"][0]["mode"] == "splash"
    assert seen["outcomes"][0]["verdict"] == verdict


def test_an_ordinary_outcome_still_reads_back_as_its_ten_keys():
    """`mode` is written only when set: every turn log written before it reads back the same,
    and an outcome that is not a flask is the same ten keys it always was."""
    d = Outcome(intent_id="x", op="attack", verdict="hit").as_dict()
    assert "mode" not in d
    assert len(d) == 10


def test_the_throw_refusal_is_one_reader_for_the_door_and_the_menu():
    """The Equipment menu greys a target the throw would refuse by asking the same function
    the use_item door asks (`Engine.throw_refusal`), so the two cannot disagree. Past five
    10-ft increments (a thug 60 ft off) both say so in the same words."""
    s, e = _board()
    pc, thug = s.pc(), s.actors["c1"]
    assert e.throw_refusal(pc, thug, None, 10, "fire") == ""
    s.positions["c1"] = (14, 10)
    s.resync_zones()
    said = e.throw_refusal(pc, thug, None, 10, "fire")
    assert "past a thrown flask's reach" in said
    res = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "x",
                             "params": {"item": "flask#1", "how": "throw", "to": "c1"}}]))
    assert said in " ".join(o.tell for o in res.outcomes)
    assert e.throw_refusal(pc, None, None, 10, "fire").startswith("Throw the fire at somebody")


# --- the table: a clickable throw ----------------------------------------------------------------

@pytest.fixture
def table(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        alchemy_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        pc = c.scene.pc()
        pc.stock.clear()
        # As a counter delivers it: keyed by its own id, which the Equipment row sends.
        pc.add_stock(goods.alchemy_stock("alchemists-fire"), 2)
        c.save()
        yield Client()
        cm._LIVE.clear()
        alchemy_views._PENDING.clear()


def _thug(fight: bool):
    c = cm.current()
    engine = c.engine()
    before = set(c.scene.actors)
    engine.run(engine.validate([{"op": "spawn", "because": "a thug steps out",
                                 "params": {"template": "thug", "count": 1,
                                            "zone": "near"}}]))
    ref = next(r for r in c.scene.actors if r not in before)
    if fight:
        engine.run(engine.validate([{"op": "begin_encounter", "because": "he draws",
                                     "params": {"sides": {"pc": ["pc"], "foes": [ref]}}}]))
        while c.scene.in_encounter and c.scene.current_ref() != "pc":
            c.scene.turn = (c.scene.turn + 1) % len(c.scene.initiative)
    # Five feet off on the grid, so no throw is refused for its reach.
    here = c.scene.positions.get("pc")
    if here is not None:
        c.scene.positions[ref] = (here[0] + 1, here[1]) + tuple(here[2:])
        c.scene.resync_zones()
    c.save()
    return ref


def _fire() -> str:
    """The flask's stock id, as the Equipment row and the combat panel send it."""
    return next(sid for sid, s in cm.current().scene.pc().stock.items()
                if s.name == "Alchemist's fire")


def _row(client, name):
    sheet = client.get("/api/sheet").json()
    return next(r for r in sheet["equipment"]["carried"] if r["name"] == name)


def post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def test_equipment_throw_names_who_it_is_thrown_at(table):
    """Measured 2026-10-07: Equipment's Throw posted `{item, how: "throw"}` with no target,
    and the engine refused every press. The act now carries a menu of the people here, by
    ref, each with the body /api/use takes; never the thrower, and only the scene's own
    people."""
    ref = _thug(fight=True)
    row = _row(table, "Alchemist's fire")
    throw = next(a for a in row["acts"] if a["label"] == "Throw")
    assert throw["menu"], throw
    # The fight's foe first; everybody else here after, never the thrower.
    assert throw["menu"][0]["body"] == {"item": _fire(), "how": "throw", "to": ref}
    assert throw["menu"][0]["foe"] is True and "foe" in throw["menu"][0]["line"]
    scene = cm.current().scene
    assert all(m["body"]["to"] in scene.actors and m["body"]["to"] != "pc"
               for m in throw["menu"])
    assert {m["body"]["to"] for m in throw["menu"]} == {
        r for r, a in scene.actors.items()
        if not a.is_pc and not a.has_state("state.down.dead")
        and not a.has_state("state.hidden")}


def test_a_throw_from_equipment_rolls_the_players_d20_and_lands(table):
    """The menu's own body, posted through the one door (/api/use how=throw -> consumables
    -> the engine's splash attack): the throw suspends for the player's d20, and the roll
    resolves into a splash attack the log carries with its verdict and mode, and the thug
    takes the fire."""
    ref = _thug(fight=True)
    thug = cm.current().scene.actors[ref]
    hp = thug.hp
    row = _row(table, "Alchemist's fire")
    body = next(a for a in row["acts"] if a["label"] == "Throw")["menu"][0]["body"]
    r = post(table, "/api/use", body)
    assert r.status_code == 200, r.json()
    state = table.get("/api/state").json()
    assert state["awaiting"] and state["awaiting"]["die"] == "1d20"
    r = post(table, "/api/roll", {"face": 20})
    assert r.status_code == 200, r.json()
    log = r.json()["log"]
    thrown = [o for e in log for o in e["outcomes"] if o.get("mode") == "splash"]
    assert thrown and thrown[-1]["verdict"] == "hit"
    assert cm.current().scene.actors[ref].hp < hp
    assert cm.current().scene.pc().stock[body["item"]].count == 1


def test_a_throw_cannot_start_over_a_roll_still_owed(table):
    """A throw suspends for the player's die; a second one started before it is rolled
    would freeze its queue over the first's. Refused, as the combat panel refuses."""
    ref = _thug(fight=True)
    post(table, "/api/use", {"item": _fire(), "how": "throw", "to": ref})
    r = post(table, "/api/use", {"item": _fire(), "how": "throw", "to": ref})
    assert r.status_code == 409
    assert "roll waiting" in r.json()["error"]


def test_a_flask_is_offered_where_attacks_are_picked(table):
    """The combat panel offered no flask (2026-10-07). `attacks.flasks` lists every flask
    that could be thrown now with the id use_item takes, and a turn built from it goes
    through /api/combat/act's use_item, the same op, and rolls the player's d20."""
    ref = _thug(fight=True)
    state = table.get("/api/state").json()
    flasks = state["attacks"]["flasks"]
    assert [f["item"] for f in flasks] == [_fire()]
    assert "fire" in flasks[0]["line"]
    r = post(table, "/api/combat/act", {
        "actions": [{"op": "use_item", "params": {"item": _fire(), "how": "throw",
                                                  "to": ref}}],
        "end_turn": True, "label": "throw the fire"})
    assert r.status_code == 200, r.json()
    assert r.json()["awaiting"]["die"] == "1d20"


def test_a_flask_aimed_at_a_square_reaches_the_engine(table):
    """CRB, Throw Splash Weapon: "target a specific grid intersection ... AC 5". The
    engine took `square` and no page sent one; /api/use now passes it through."""
    _thug(fight=True)
    here = cm.current().scene.positions["pc"]
    r = post(table, "/api/use", {"item": _fire(), "how": "throw",
                                 "square": [here[0] + 1, here[1]]})
    assert r.status_code == 200, r.json()
    assert cm.current().scene.awaiting["dc"] == 5


# --- the Equipment tab's wording, from the server ---------------------------------------------------

def test_a_thrown_flask_is_not_said_to_poison_whoever_drinks_it(table):
    """Measured 2026-10-07: alchemist's fire, thrown and never drunk, read "poisons whoever
    drinks it". The row's warning is the server's sentence for the ways the row offers to
    use it on somebody; a flask offers none, so it says nothing."""
    _thug(fight=False)
    row = _row(table, "Alchemist's fire")
    assert row["harm"] == ""
    assert "poisons" not in row


def test_a_drawback_is_said_as_what_it_does(table):
    """The experimental Cure Light Wounds potion's drawback, sickened for 3 rounds, was
    called "poisons whoever drinks it" (measured 2026-10-07). It is said as it is, in the
    engine's words: "Harm to whoever drinks it: causes sickened for 3 rounds"."""
    jar = Stock(base="Experimental Cure Light Wounds", count=1, how=["drink"], specs=[
        {"type": "heal", "dice": "1d8+1", "route": "ingest"},
        {"type": "apply_condition", "target": "sickened", "route": "ingest",
         "duration": {"amount": 3, "unit": "round"}, "drawback": True}])
    lines = consumables.harm_lines(jar, "ingest")
    assert len(lines) == 1 and "sickened" in lines[0].lower() and "3" in lines[0]
    fire = goods.alchemy_stock("alchemists-fire")
    assert consumables.harm_lines(fire, "ingest") == []
    cm.current().scene.pc().add_stock(jar, 1)
    cm.current().save()
    row = _row(table, "Experimental Cure Light Wounds")
    assert row["harm"].startswith("Harm to whoever drinks it: ")
    assert "sickened for 3 rounds" in row["harm"] and "poison" not in row["harm"].lower()


def test_an_opened_pinch_is_not_offered_as_a_drink(table):
    """Measured 2026-10-07: an assay's opened quicksilver (a raw reagent, tracked in tenths)
    offered Drink on the Equipment tab, because a jar with no documents reads as harmless.
    The planner refuses a raw reagent, so the sheet offers nothing, and the row says what it
    is and where it is worked."""
    pc = cm.current().scene.pc()
    pc.carry("quicksilver", 1)
    it = al.find(pc, "inv:quicksilver")
    al.take_pinch(pc, it, 1)
    cm.current().save()
    row = _row(table, "Quicksilver")
    assert not [a for a in row["acts"] if a["label"] in ("Drink", "Throw", "Coat", "Use")]
    assert "0.9 of one" in row["line"]
    assert "alchemy bench" in row["note"]
    st = next(s for s in pc.stock.values() if consumables.is_raw_reagent(s))
    assert not consumables.plan(st, how="drink").ok


# --- the bench: an opened pinch ------------------------------------------------------------------

def test_an_opened_pinch_says_the_true_reason_it_cannot_go_in():
    """Measured 2026-10-07: the opened unit was refused as "a finished product cannot go back
    into the glass". It is the raw material, 0.9 of one (plan §13.2); a step takes whole
    units, as the forge's cut bar ("bars track tenths"), and the rest is the next assay's,
    which takes from it first. The bookkeeping in tenths is unchanged."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.inventory.clear()
    pc.stock.clear()
    pc.carry("quicksilver", 2)
    al.take_pinch(pc, al.find(pc, "inv:quicksilver"), 1)
    opened = next(it for it in al.shelf(pc) if it.cut)
    assert not opened.finished and opened.opened
    assert opened.amount == 0.9
    why = al.fit_reason("dissolve", "inputs", opened)
    assert "finished product" not in why
    assert "0.9 of one is left" in why and "whole" in why
    # The whole one still in the satchel is an input as before.
    whole = al.find(pc, "inv:quicksilver")
    assert whole.count == 1 and al.fit_reason("react", "inputs", whole) == ""
    # And the next assay cuts the opened unit, not a fresh one.
    assert al.assay_source(pc, "quicksilver").key == opened.key


# --- the bench: the choices the server takes, offered ---------------------------------------------

@pytest.fixture
def bench(tmp_path, monkeypatch):
    from rules import places

    monkeypatch.setattr(places, "laboratory_here", lambda scene, known=(): None,
                        raising=False)
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        alchemy_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"),
                          start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.herb_known.clear()
        goods.deliver(c.scene, pc, goods.good("alchemist's field kit"))
        c.save()
        yield Client()
        cm._LIVE.clear()
        alchemy_views._PENDING.clear()


def _check(client, body):
    r = post(client, "/api/alchemy/check", body)
    assert r.status_code == 200, r.content
    return r.json()


def test_a_vessel_that_bottles_two_families_offers_the_choice(bench):
    """`plan_step` took `as` for a glass vial (a potion or an oil) and nothing offered it:
    an experiment in a vial was always a potion. The check sends the vessel's families with
    how each is used, and `as` decides."""
    pc = cm.current().scene.pc()
    pc.carry("strong-spirits", 1)
    pc.carry("glass-vial", 1)
    cm.current().save()
    base = {"method": "bottle", "inputs": ["inv:strong-spirits"],
            "vessel": "inv:glass-vial", "formula": "experiment"}
    c = _check(bench, base)
    fam = c["choices"]["families"]
    assert [f["id"] for f in fam["options"]] == ["potion", "oil"]
    assert fam["open"] is True and fam["chosen"] == "potion"
    assert "drink" in fam["options"][0]["how"]
    c = _check(bench, dict(base, **{"as": "oil"}))
    assert c["choices"]["families"]["chosen"] == "oil"
    assert c["family"] == "oil"


def test_catalysts_offer_what_they_are_told(bench):
    """Orichalcum grains (`names_formula`) and a unicorn horn shaving (`strip_one`) took
    `aim` and `strip` from the body; nothing offered either. The check now sends the
    formulae within reach for this vessel to name (the fixed table, never the mix's
    candidates) and the pool's drawbacks to strip, the server's pick until one is named."""
    pc = cm.current().scene.pc()
    pc.track("alchemist").level = 3
    for mid in ("quicksilver", "glass-vial", "orichalcum-grains", "unicorn-horn-shaving"):
        pc.carry(mid, 1)
    cm.current().save()
    c = _check(bench, {"method": "bottle", "inputs": ["inv:quicksilver"],
                       "vessel": "inv:glass-vial", "formula": "experiment",
                       "catalysts": ["inv:orichalcum-grains", "inv:unicorn-horn-shaving"]})
    ch = c["choices"]
    assert ch["aim"]["options"], ch
    from rules import formulae

    for f in ch["aim"]["options"]:
        assert formulae.within_reach(formulae.get(f["id"]), 3)
    assert ch["strip"]["options"] and ch["strip"]["chosen"] == ch["strip"]["options"][0]["key"]


def test_an_empty_shelf_points_at_the_market(tmp_path):
    """An empty shelf said "markets sell the common ones" and offered nothing. The state's
    `buy` names this settlement's counter that sells the alchemist's staples (the
    alchemist's shop before the general store), with whether the party stands at the
    market so the page can open the Trade tab on it; nothing out in the wilds."""
    from rules import market

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        known = c.engine().places()
        spot = next((p for p in known if market.is_market(p.id, c.scene.founded or ())), None)
        if spot is None:
            pytest.skip("the fixture's start has no market among its places")
        c.engine().place_party(spot.id)
        got = alchemy_views._buy(c)
        assert got["here"] is True and got["line"] in ("alchemist", "general")
        assert "reagents" in got["said"]
        lines = market.counters(c.location if c.location is not None else c.scene.location_id)
        assert got["line"] in {x.id for x in lines}
        cm._LIVE.clear()


# --- the page: the shatter is heard --------------------------------------------------------------

NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_thrown_flask_is_heard_as_a_shatter_hit_or_miss(tmp_path):
    """The log's splash attacks play `combat.shatter`, a hit and a miss alike (a miss still
    breaks in a square nearby), and never the blade's combat.hit / combat.miss. Run on the
    real attackSounds out of 04-combat-and-turns.js with a stand-in Sound."""
    src = (ROOT / "play/static/js/table/04-combat-and-turns.js").read_text(encoding="utf-8")
    start = src.index("function newLogEntries")
    end = src.index("async function commitTurn")
    script = tmp_path / "s.js"
    script.write_text(
        "const played = []; const window = { Sound: { play: (n) => played.push(n) } };\n"
        "const Sound = window.Sound;\n" + src[start:end] + "\n"
        "const after = [{kind: 'turn', outcomes: ["
        "{op: 'attack', mode: 'splash', verdict: 'hit', dc: {value: 12}, rolls: []},"
        "{op: 'attack', mode: 'splash', verdict: 'miss', dc: {value: 12}, rolls: []},"
        "{op: 'attack', mode: '', verdict: 'hit', dc: {value: 12}, rolls: []}]}];\n"
        "attackSounds([], after, null);\n"
        "setTimeout(() => console.log(JSON.stringify(played)), 0);\n", encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == ["combat.shatter", "combat.shatter", "combat.hit"]
