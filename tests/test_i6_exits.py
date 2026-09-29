"""I6: the "From here" row — the ways on, from the engine's own place graph.

The owner, 2026-09-29: "give the choices based on entrances, what areas are connected to
where i am."

Measured 2026-09-28 (G2, the leave-town script, docs/design-b-space.md §8): "I walk to the
nearest crossroads" was refused by the engine (`found kind=crossroads`, "no such kind of
place") and narrated as a walk anyway, so the page stood the player on the outskirts while
the engine held them at the way in, and every later turn resolved from where the engine
was. The row is the other half of that fix: every way on it is an edge of the engine's
graph, a click names the place by the engine's own id and moves the party with a declared
`travel` (or `journey`) — no model is asked where — and a way the rules would refuse is
shown shut with the rules' own sentence, never offered and then refused.

Every test runs once per export (`worlds`, the fix pass's rule: no fix keyed on a world).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.test import Client, override_settings

from play import exits as exits_mod
from rules import outskirts, places, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene


class _Quiet:
    """Dice that never meet anything on the way: every d100 check misses (the Lane B
    tests' own, so a walk tested here is the walk and not a hawker)."""

    def __init__(self, real):
        self.real = real

    def __getattr__(self, name):
        return getattr(self.real, name)

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation == "1d100":
            return self.real.given(100, modifiers, label, notation)
        return self.real.roll(notation, modifiers, label, visibility)


def _settled(world):
    for row in world.play.get("settlements") or []:
        e = world.get(row["id"])
        if e is not None and places._settled(e, ""):
            yield e


def _party(world, town_id, at=""):
    s = Scene(location_id=town_id)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 60
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party(at)
    e.dice = _Quiet(e.dice)
    return s, e, pc


def _want(pc, town, how="wanted"):
    tag = states.wanted_tag(town) if how == "wanted" else states.suspected_tag(town)
    pc.apply_effect(ActiveEffect(name=how, kind="situation", key=f"test:{tag}",
                                 source="test", origin="test",
                                 duration="until-dismissed", tags=(tag,)))


def _with_a_ring(world):
    """Settlements whose way in opens onto the ring (every settlement, by Lane B)."""
    for loc in _settled(world):
        s, e, _pc = _party(world, loc.id)
        if any(places.is_ring(p.id) for p in e.places()):
            yield loc


def _journey_spot(world):
    """(settlement, place id) where the row offers a journey: a road head, or the docks
    or shore a passage leaves from. The first one in the world's own order."""
    for loc in _settled(world):
        s, e, _pc = _party(world, loc.id)
        for p in e.places():
            if not (places.is_ring(p.id) or places.setting_of(p.id) != "outside"):
                continue
            e.place_party(p.id)
            if any(x["journey"] for x in exits_mod.exits(e, world)):
                return loc, p.id
    return None, ""


# --- the row is the engine's graph ------------------------------------------------------

def test_next_door_is_the_graphs_own_edges_and_nothing_else(worlds):
    """"what areas are connected to where i am": next door is exactly `Place.exits`
    (in and under the settlement), each with its walk in words; nothing invented, and
    here is never an exit."""
    checked = 0
    for loc in list(_settled(worlds))[:6]:
        s, e, pc = _party(worlds, loc.id)
        for here in [p for p in e.places() if places.setting_of(p.id) != "outside"][:4]:
            e.place_party(here.id)
            known = e.places()
            row = exits_mod.exits(e, worlds)
            ids = {x["id"] for x in row if not x["journey"]}
            assert here.id not in ids
            assert ids <= {p.id for p in known}, "every way on is a place the engine holds"
            want = {x for x in here.exits
                    if places.find(known, x) is not None
                    and places.setting_of(x) != "outside"
                    and not places.find(known, x).described_only}
            got = {x["id"] for x in row if x["group"] == "next_door"}
            assert got == want, (loc.name, here.name)
            for x in row:
                assert x["time_words"], x
                assert set(x) == {"id", "name", "group", "time_words", "blocked", "journey"}
            checked += 1
    assert checked


def test_nothing_the_engine_would_refuse_is_offered_unmarked(worlds):
    """Every way the row offers open, the engine walks: travel to it from here is not
    refused. Checked from the way in and from the outskirts, where the ring is offered,
    because that is where G2's crossroads was refused and narrated as walked."""
    walked = 0
    for loc in list(_with_a_ring(worlds))[:3]:
        s, e, pc = _party(worlds, loc.id)
        starts = [e.here().id] + [p.id for p in e.places()
                                  if p.name == outskirts.OUTSKIRTS and places.is_ring(p.id)]
        for start in starts:
            e.place_party(start)
            for x in exits_mod.exits(e, worlds):
                if x["journey"] or x["blocked"]:
                    continue
                s2, e2, pc2 = _party(worlds, loc.id, start)
                e2._journeyed = ""
                out = e2.run(e2.validate([{"op": "travel", "actor": pc2.ref,
                                           "because": "t",
                                           "params": {"place": x["id"]}}]))
                o = out.outcomes[0]
                assert o.status != "refused", (loc.name, x["name"], o.tell)
                assert s2.at == x["id"], (loc.name, x["name"])
                walked += 1
    assert walked


def test_the_ring_is_offered_from_a_way_out(worlds):
    """"outside is the ring from a way out": standing at the way in, the outskirts and
    the rest of the ring are listed as outside, with the minutes the walk takes."""
    loc = next(_with_a_ring(worlds))
    s, e, pc = _party(worlds, loc.id)
    row = exits_mod.exits(e, worlds)
    outside = [x for x in row if x["group"] == "outside"]
    assert any(x["name"] == outskirts.OUTSKIRTS for x in outside), [x["name"] for x in row]
    ring = {p.id for p in e.places() if places.is_ring(p.id) and not outskirts.is_along(p.id)}
    assert {x["id"] for x in outside} == ring


# --- the page: the click is a declared move ------------------------------------------------

class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"
        self.prompt_tokens = self.reply_tokens = 0
        self.done_reason = "stop"

    def json(self):
        return json.loads(self.text)


@pytest.fixture
def table(worlds, tmp_path, monkeypatch):
    """A campaign in this world, the model stubbed and every plan call counted: the row's
    move must reach the engine with no planner asked."""
    from gm import client as gm_client
    from gm import watcher
    from gm.agent import TurnPlan
    from play import campaign as cm
    from play import concurrency, views
    from rules.sheet import load_pc

    monkeypatch.setattr(watcher, "kick", lambda c: None)
    calls = {"plan": 0, "chat": 0}

    def plan(agent, text, *a, **kw):
        calls["plan"] += 1
        agent.last_said = []
        return TurnPlan(narration="", intents=agent.engine.validate(
            [{"op": "narrate_only", "because": "t"}]))

    def chat(*a, **k):
        calls["chat"] += 1
        return _Reply(json.dumps({"narration": "The way goes by underfoot. " * 6,
                                  "suggestions": ["I look around"]}))

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    monkeypatch.setattr(gm_client, "chat", chat)
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.begin_with(load_pc("fixtures/pc-thessaly.json"),
                          world_source=str(Path(worlds.source)))

        def stand(loc, place_id=""):
            """Put the party alone at a place of `loc`, out of any fight or road."""
            if c.scene.in_encounter:
                c.scene.end_encounter()
            pc = c.scene.pc()
            for ref in [r for r in c.scene.people if r != pc.ref]:
                c.scene.people.pop(ref)
            c.scene.location_id = loc.id
            c.scene.road = {}
            c.engine().place_party(place_id)
            c.save()
            return c

        yield {"c": c, "calls": calls, "stand": stand}
        cm._LIVE.clear()


def _state():
    return Client().get("/api/state").json()


def _say(body):
    return Client().post("/api/say", data=json.dumps(body), content_type="application/json")


def test_state_carries_the_exits(worlds, table):
    """`scene.exits` is on `/api/state`, rebuilt from the engine for where the party is."""
    loc = next(_with_a_ring(worlds))
    c = table["stand"](loc)
    got = _state()["scene"]["exits"]
    assert got == exits_mod.exits(c.engine(), c.world)
    assert got and all(x["group"] in ("next_door", "outside", "road") for x in got)


def test_a_place_attachment_moves_the_party_with_no_model_guess(worlds, table):
    """G2: "I walk to the nearest crossroads" went through the planner, was refused and
    narrated as a walk. A click on the row names the engine's own id: the party is moved
    by one declared `travel` to that id, the planner is asked nothing, and the narrator
    is handed the engine's tells to describe the walk."""
    loc = next(_with_a_ring(worlds))
    c = table["stand"](loc)
    x = next(v for v in _state()["scene"]["exits"] if v["group"] == "next_door")
    r = _say({"text": f"I go to {x['name']}.",
              "attachments": [{"kind": "place", "id": x["id"]}]})
    assert r.status_code == 200, r.content[:300]
    assert table["calls"]["plan"] == 0
    assert c.scene.at == x["id"]
    turn = [e for e in c.turn_log if e.get("kind") == "turn"][-1]
    assert [(i["op"], i["params"].get("place")) for i in turn["intents"]] == \
        [("travel", x["id"])]
    assert turn["attachments"][0]["id"] == x["id"]
    player = [b for b in c.transcript if b["who"] == "player"][-1]
    assert player["text"] == f"I go to {x['name']}."
    assert "attachments" not in player, "the line already names the place"
    assert table["calls"]["chat"] >= 1, "the narrator describes the walk"


def test_the_ring_is_reached_by_the_row_too(worlds, table):
    """From the way in, the outskirts (outside the walls) is one click, as the owner
    asked, and the engine stands the party there."""
    loc = next(_with_a_ring(worlds))
    c = table["stand"](loc)
    x = next(v for v in _state()["scene"]["exits"] if v["name"] == outskirts.OUTSKIRTS)
    r = _say({"text": "", "attachments": [{"kind": "place", "id": x["id"]}]})
    assert r.status_code == 200, r.content[:300]
    assert places.setting_of(c.scene.at) == "outside"
    assert table["calls"]["plan"] == 0


def test_an_attachment_not_in_the_exits_is_a_400_with_a_sentence(worlds, table):
    """A place the engine holds but that is not a way on from here, a place that is
    nowhere, and a place chip on Continue: each a 400 with a sentence, and the turn never
    happened (no beat, no clock, no plan).

    Words beside the chip were a 400 here too until 2026-09-29 ("a turn of its own"),
    because the click went straight to the engine and the words were silently ignored.
    The owner asked for the words to say where in the turn the move happens; they are
    read now (tests/test_exits_attach.py), not refused."""
    loc = next(_with_a_ring(worlds))
    c = table["stand"](loc)
    here_ids = {x["id"] for x in _state()["scene"]["exits"]}
    far = next((p for p in c.engine().places()
                if p.id not in here_ids and p.id != c.scene.at), None)
    was, clock = len(c.transcript), c.scene.clock_minutes
    bodies = [{"text": "", "attachments": [{"kind": "place", "id": "nowhere-at-all"}]}]
    if far is not None:
        bodies.append({"text": "", "attachments": [{"kind": "place", "id": far.id}]})
    first = next(iter(here_ids))
    bodies.append({"carry_on": True, "attachments": [{"kind": "place", "id": first}]})
    for body in bodies:
        r = _say(body)
        assert r.status_code == 400, (body, r.content[:200])
        assert r.json()["error"].endswith("."), r.json()
    assert len(c.transcript) == was and c.scene.clock_minutes == clock
    assert table["calls"]["plan"] == 0


def test_a_journey_asks_before_it_spends_days(worlds, table):
    """A journey is days on the clock. The page confirms it by the attach-then-Say (the
    chip carries `confirmed`, and its line says the days); the server holds the same
    line, so a journey attachment without `confirmed` is a 400 that says how far it is,
    and nothing moves. Confirmed, the engine takes the declared `journey`."""
    loc, spot = _journey_spot(worlds)
    assert loc is not None, "every export has a way out that is a journey"
    c = table["stand"](loc, spot)
    x = next(v for v in _state()["scene"]["exits"] if v["journey"])
    assert x["group"] == "road"
    was_clock, was_at = c.scene.clock_minutes, c.scene.at
    r = _say({"text": "", "attachments": [{"kind": "place", "id": x["id"]}]})
    assert r.status_code == 400 and "Confirm" in r.json()["error"]
    assert x["time_words"] in r.json()["error"]
    assert c.scene.clock_minutes == was_clock and c.scene.at == was_at
    r = _say({"text": f"I go to {x['name']}.",
              "attachments": [{"kind": "place", "id": x["id"], "confirmed": True}]})
    assert r.status_code == 200, r.content[:300]
    assert table["calls"]["plan"] == 0
    turn = [e for e in c.turn_log if e.get("kind") == "turn"][-1]
    assert [(i["op"], i["params"].get("to")) for i in turn["intents"]] == \
        [("journey", x["id"])]
    assert c.scene.clock_minutes > was_clock + 60, "a journey costs hours at least"


def test_a_wanted_character_sees_the_way_out_shut_with_the_reason(worlds, table):
    """"wanted at the gate": the row greys the way out in the engine's own sentence
    (`Engine.watch_at_the_way_out`, the rule `_op_travel` applies), the click is refused
    with it, and the engine refuses the same move when asked directly — one rule, two
    askers, so they cannot disagree."""
    loc = next(_with_a_ring(worlds))
    c = table["stand"](loc)
    _want(c.scene.pc(), loc.id)
    c.save()
    row = _state()["scene"]["exits"]
    out = next(v for v in row if v["name"] == outskirts.OUTSKIRTS)
    assert "wanted" in out["blocked"]
    assert "—" not in out["blocked"] and "–" not in out["blocked"]
    # Inside the walls nothing is shut: the watch stands at the way out.
    assert all(not v["blocked"] for v in row if v["group"] == "next_door"
               and " ".join(v["name"].split()).lower() not in places.ENTRANCES)
    was = len(c.transcript)
    r = _say({"text": "", "attachments": [{"kind": "place", "id": out["id"]}]})
    assert r.status_code == 400 and "wanted" in r.json()["error"]
    assert len(c.transcript) == was
    e = c.engine()
    e.dice = _Quiet(e.dice)
    o = e.run(e.validate([{"op": "travel", "actor": c.scene.pc().ref, "because": "t",
                           "params": {"place": out["id"]}}])).outcomes[0]
    assert o.status == "refused" and "wanted" in o.tell


def test_the_road_out_is_shut_to_the_wanted_too(worlds, table):
    """The journey reads the warrant as the gate does (`Engine.watch_on_the_road`)."""
    loc, spot = _journey_spot(worlds)
    c = table["stand"](loc, spot)
    _want(c.scene.pc(), loc.id)
    c.save()
    road = next(v for v in _state()["scene"]["exits"] if v["journey"])
    assert "wanted" in road["blocked"]
    r = _say({"text": "", "attachments": [{"kind": "place", "id": road["id"],
                                           "confirmed": True}]})
    assert r.status_code == 400 and "wanted" in r.json()["error"]


def test_a_shop_shut_for_the_night_is_greyed_in_the_keepers_words(worlds):
    """"a shop shut for the night": the door `_at_their_door` would knock at (a keeper
    who lives over a trade counter, in the night slots, counter shut) is shut on the row
    with the keeper's own line (`keepers.shut_line`). Skipped for a world with no such
    shop next to anywhere."""
    from rules import keepers

    for loc in _settled(worlds):
        s, e, pc = _party(worlds, loc.id)
        for shop in e.places():
            if places.setting_of(shop.id) != "in" or not places.is_indoors(shop.id) \
                    or places.category_of(f"the {keepers.kind_of(shop.id)}") != "trade":
                continue
            beside = next((places.find(e.places(), x) for x in shop.exits
                           if places.find(e.places(), x) is not None), None)
            if beside is None:
                continue
            s.clock_minutes = 10 * 60
            e.place_party(shop.id)            # staffed by day
            if keepers.keeper_in(s, shop.id) is None:
                continue
            e.place_party(beside.id)
            s.clock_minutes = 24 * 60 + 60     # the small hours
            row = {x["id"]: x for x in exits_mod.exits(e, worlds)}
            if shop.id not in row:
                continue
            assert row[shop.id]["blocked"], row[shop.id]
            assert "shut" in row[shop.id]["blocked"] or "open" in row[shop.id]["blocked"]
            return
    pytest.skip("no roofed trade shop beside anywhere in this world")


# --- the page's own furniture ---------------------------------------------------------------

def test_the_row_is_on_the_page_above_the_input_and_says_no_dashes():
    """The mount point sits in the footer before the say form, the script is loaded in
    the asset idiom after the spells, and the row's own words carry no em or en dash and
    no arrow (the owner's UI rule)."""
    root = Path(__file__).resolve().parent.parent
    page = (root / "play/templates/play/table.html").read_text(encoding="utf-8")
    assert page.index('id="exits"') < page.index('id="sayform"')
    assert page.index("js/table/10-spells.js") < page.index("js/table/11-exits.js")
    code = (root / "play/static/js/table/11-exits.js").read_text(encoding="utf-8")
    strings = [line for line in code.splitlines() if not line.lstrip().startswith("//")]
    for bad in ("—", "–", "→", "←"):
        assert not any(bad in line for line in strings), bad
    assert "@keyframes" not in code and "animation" not in code
