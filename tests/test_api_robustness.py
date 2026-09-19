"""What the endpoints do with input no honest browser would send.

Found by probing one endpoint with twenty-seven hostile bodies: seven came back HTTP 500
with a traceback. In the packaged app a 500 is a button that does nothing and says
nothing, which is the same failure CLAUDE.md already records for a hidden required field
— "nothing happens, and nothing says why".

All seven were two lines repeated across the app:

* `json.loads(request.body or "{}")` followed by `body.get(...)`, which raises on
  malformed JSON *and* on a bare array, string or null — those parse fine and then die
  on `.get`. The pattern was at twenty-seven call sites in five modules.
* `int(body.get("hours", 1) or 1)`, which is fine for a number and raises for `"many"`,
  for `[1, 2]` and for `NaN`.

A refusal is the app working; only a 5xx or an exception is a break. These pin that.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from play.apiutil import read_body, read_int
from rules.sheet import load_pc


@pytest.fixture
def client(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.pc().purse = {"gp": 500}
        c.save()
        yield Client()
        cm._LIVE.clear()


HOSTILE_BODIES = [
    ("negative hours", {"action": "blacksmith:buy", "hours": -5}),
    ("huge hours", {"action": "blacksmith:buy", "hours": 10 ** 9}),
    ("string hours", {"action": "blacksmith:buy", "hours": "many"}),
    ("list hours", {"action": "blacksmith:buy", "hours": [1, 2]}),
    ("nan hours", {"action": "blacksmith:buy", "hours": float("nan")}),
    ("null hours", {"action": "blacksmith:buy", "hours": None}),
    ("unknown action", {"action": "wizard:handwave"}),
    ("null action", {"action": None}),
    ("list action", {"action": ["blacksmith:buy"]}),
    ("no action key", {}),
    ("very long action", {"action": "x" * 5000}),
    # Built with chr() rather than written as an escape: a literal NUL in the
    # source is the same trap CLAUDE.md records for backslashes, and pytest
    # cannot even parse the file.
    ("nul byte in action", {"action": "blacksmith:buy" + chr(0)}),
    ("path traversal", {"action": "../../etc/passwd"}),
    ("creature is a dict", {"action": "leatherworker:skin", "creature": {"a": 1}}),
]


@pytest.mark.parametrize("name,body", HOSTILE_BODIES, ids=[n for n, _ in HOSTILE_BODIES])
def test_a_hostile_body_is_refused_rather_than_raised(client, name, body):
    r = client.post("/api/craft/excursion", data=json.dumps(body),
                    content_type="application/json")
    assert r.status_code < 500, f"{name} -> {r.status_code}"


RAW_BODIES = [("not json", b"{not json"), ("empty", b""), ("array", b"[1,2,3]"),
              ("bare string", b'"hello"'), ("bare null", b"null"),
              ("bare number", b"42"), ("nested deep", b'{"a":' * 40 + b"1" + b"}" * 40)]


@pytest.mark.parametrize("name,raw", RAW_BODIES, ids=[n for n, _ in RAW_BODIES])
def test_a_body_that_is_not_an_object_is_refused_rather_than_raised(client, name, raw):
    """A JSON array parses perfectly well and then kills `.get`. Four of the original
    seven 500s were exactly this."""
    r = client.post("/api/craft/excursion", data=raw,
                    content_type="application/json")
    assert r.status_code < 500, f"{name} -> {r.status_code}"


def test_read_body_answers_with_an_object_or_nothing():
    class Req:
        def __init__(self, body):
            self.body = body

    assert read_body(Req(b'{"a": 1}')) == {"a": 1}
    for junk in (b"{not json", b"[1,2]", b'"hi"', b"null", b"42", b"", None):
        assert read_body(Req(junk)) == {}, junk


def test_read_int_never_raises_and_clamps():
    assert read_int({"n": 5}, "n", 1) == 5
    assert read_int({"n": "7"}, "n", 1) == 7
    assert read_int({"n": 2.9}, "n", 1) == 2
    assert read_int({}, "n", 3) == 3
    for junk in ("many", [1, 2], {"a": 1}, None, float("nan"), float("inf")):
        assert read_int({"n": junk}, "n", 1) == 1, junk
    # A JSON `true` is an int in Python and must not become one hour.
    assert read_int({"n": True}, "n", 4) == 4
    assert read_int({"n": 99}, "n", 1, lo=1, hi=12) == 12
    assert read_int({"n": -99}, "n", 1, lo=1, hi=12) == 1


# --- the second sweep, across every endpoint that resolves without the model ----------
#
# The first probe covered one endpoint and found seven 500s. Sweeping the other ten found
# three more, all the same shape a third time: a field that should be a list or an object
# arrives as something else, and the code calls `.get` on it.

def test_effects_that_are_not_a_list_are_refused_not_raised(client):
    """`"effects": "notalist"` walked into `effectspec.validate` a character at a time
    and died on `.get`; `[null]` did the same. The spell builder is built to show a list
    of problems, and both came back as HTTP 500 with a traceback instead."""
    from rules.spells import validate_spell

    for junk in ("notalist", 5, {"a": 1}):
        problems = validate_spell({"name": "t", "effects": junk})
        assert any("list of effects" in p for p in problems), junk
    problems = validate_spell({"name": "t", "effects": [None, "x"]})
    assert sum("must be an object" in p for p in problems) == 2


def test_abilities_that_are_not_an_object_are_refused_not_raised():
    """`"abilities": "x"` reached `raw.get(ab)` and raised AttributeError, so a
    malformed create answered 500 rather than the list of problems `build` exists to
    return."""
    from rules import creation

    _, problems = creation.build({"name": "T", "race": "dwarf", "class": "fighter",
                                  "abilities": "x"})
    assert any("object of six scores" in p for p in problems), problems


@pytest.mark.parametrize("url", [
    "/api/roll", "/api/combat/act", "/api/craft/preview", "/api/craft/do",
    "/api/craft/forage", "/api/spells/save", "/api/level-up", "/api/slots",
    "/api/character/create", "/api/travel",
])
def test_no_endpoint_answers_a_bad_body_with_a_traceback(client, url):
    """One case per endpoint, the shape that broke three of them: a field that should be
    a container arriving as a bare string."""
    for body in ({"effects": "x", "actions": "x", "abilities": "x", "choices": "x",
                  "ingredients": "x", "name": "t", "craft": "herbalism"},
                 {}, [1, 2, 3]):
        r = client.post(url, data=json.dumps(body), content_type="application/json")
        assert r.status_code < 500, f"{url} -> {r.status_code} on {body}"



def test_a_face_that_is_not_a_number_is_refused_not_crashed(client):
    """The adversarial audit posted {"face": "banana"} at a pending roll and took the
    view down with an uncaught ValueError — a 500 with the roll still open. A garbage
    face must 400 with the roll intact, and a real face must still land afterwards."""
    import json as _json

    from play import campaign as cm

    c = cm.current()
    if c.scene.pc() is None or c.scene.awaiting or c.scene.in_encounter:
        pytest.skip("needs a quiet live campaign")
    had_company = [r for r, a in c.scene.actors.items() if not a.is_pc]
    if had_company:
        pytest.skip("foraging needs solitude and this scene has company")

    r = client.post("/api/forage", data="{}", content_type="application/json")
    if r.status_code != 200 or "roll" not in r.json():
        pytest.skip(f"could not open a roll here: {r.status_code}")
    try:
        r = client.post("/api/roll", data=_json.dumps({"face": "banana"}),
                        content_type="application/json")
        assert r.status_code == 400
        assert "between" in r.json()["error"]
        assert cm.current().scene.awaiting, "the garbage face consumed the roll"
    finally:
        client.post("/api/roll", data="{}", content_type="application/json")


def test_every_resolution_door_catches_the_same_failures():
    """A resolution-time raise must never reach Django as a 500.

    `_advance` caught (IntentError, ValueError) while the NPC turn path three hundred
    lines below it caught KeyError too — and KeyError is reachable from an intent list
    that PASSED validation: `travel` departs an actor and a later intent in the same list
    still names them, so `self.scene.actors[ref]` raises a bare KeyError('c1'). Verified
    by driving travel-then-damage through a real Engine. Django has no exception
    middleware here, so "I strike him and head for the treeline" was a traceback rather
    than the 502 that branch is careful to produce.

    Compared between the doors rather than asserted at one, because the defect was the
    two disagreeing.
    """
    import ast
    from pathlib import Path

    src = Path("play/views.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    def caught(fn_name):
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == fn_name), None)
        assert fn is not None, f"play/views.py lost {fn_name}; update this test"
        names = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                parts = (node.type.elts if isinstance(node.type, ast.Tuple)
                         else [node.type])
                names.update(getattr(p, "id", "") for p in parts)
        return names

    door = caught("_advance")
    for kind in ("IntentError", "ValueError", "KeyError"):
        assert kind in door, (
            f"_advance does not catch {kind}, so a resolution-time {kind} reaches "
            f"Django as a 500 with a traceback")


def test_a_refused_turn_leaves_no_creatures_standing():
    """A 502 must undo the half of the turn that already resolved.

    Read out of a live save on 2026-09-01. The server log shows
    `POST /api/say ... 502` at 11:08:44 and a successful one at 11:09:20. The
    campaign's own turn log records exactly two creatures created all game — the
    foreman (killed) and one thug (killed) — and the saved scene held TEN
    pristine thugs, all `hp 13/13`, all zoned `engaged`, none of them the one
    that fought and none carrying the loot the watcher had garnished onto it.

    The mechanism is that `_drive` applies each intent before it reaches the
    next, so the spawn landed and a later intent raised. The 502 branch popped
    the player's line from the transcript and did not save — but not-saving is
    not not-happening: the campaign lives in `_LIVE`, so the next successful
    turn wrote the ghosts to disk.
    """
    from rules import keepers
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.intents import IntentError

    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=3))
    before = scene.snapshot()

    # A list that PASSES validation and raises at RESOLUTION — the only kind that
    # can half-apply. Stage 7 made every refusal validate can foresee a validate-time
    # one and every other a printed sentence, so the list has to change under itself
    # to reach a raise at all: the spawn projects four refs the attack may name, the
    # travel then walks the party out of their room, and the attack finds its target
    # "not on the board at resolution time" — the one floor validate cannot see past.
    #
    # Four rather than ten since 2026-09-19: a spawn of five or more now arrives as ONE
    # troop with the combined hit points of its members (item 33, `rules/troops.py`), so a
    # count of ten would leave one actor standing and prove nothing about a half-applied
    # list. Four bodies half-apply exactly as well as ten did.
    other = next(p for p in engine.places() if p.id != engine.here().id)
    raw = [{"op": "spawn", "because": "the ambush",
            "params": {"template": "thug", "count": 4, "zone": "engaged"}},
           {"op": "travel", "because": "away", "params": {"place": other.name}},
           {"op": "attack", "actor": "pc", "target": "c1", "because": "the swing"}]
    with pytest.raises((IntentError, ValueError, KeyError)):
        engine.run(engine.validate(raw))
    # The four thugs and the player. Whoever keeps the room the travel walked into is
    # standing in it too (`rules/keepers.py`) and is not one of the ghosts, so they are
    # not counted among them.
    ghosts = [r for r, a in scene.people.items()
              if not keepers.is_keeper(a.world_entity_id or "")]
    assert len(ghosts) == 5, (
        "the probe no longer reproduces a half-applied list; find one that does")

    scene.restore(before)
    # Including the ledger of which counters have been staffed: a refused turn that
    # left a place marked staffed would leave that shop empty for the rest of the
    # campaign, since a counter is only ever staffed once.
    assert scene.staffed == []
    assert sorted(scene.people) == ["pc"], (
        f"the refused turn left {len(scene.people) - 1} creatures in the campaign: "
        f"{sorted(scene.people)}")
    assert sorted(scene.zones) == ["pc"], \
        "the creatures are gone and their zones are not"


def test_the_snapshot_covers_the_whole_scene_not_a_field_list():
    """The rollback must not be a second, hand-written copy of the save format.

    The save format is a hand-written field list and it has already proved
    incomplete twice — `Ward.as_dict` and `Manifestation.as_dict` existed and
    were called by nothing, so a reload deleted every fog cloud and wall of
    stone in the scene. A snapshot that forgets a field is worse than no
    snapshot, because it silently reverts *some* of the turn. Every dataclass
    field is checked, so a field added tomorrow is covered without this test
    being edited.
    """
    import dataclasses

    from rules.engine import Scene

    scene = Scene(location_id="5bbd0c40345f")
    snap = scene.snapshot()
    fields = {f.name for f in dataclasses.fields(Scene)} - {"_dice"}
    missing = sorted(fields - set(snap))
    assert not missing, f"snapshot does not carry {missing}"


def test_a_turn_is_written_to_the_log_once():
    """Eight `turn` entries for four turns made the ghost-thug hunt twice as long.

    `_log_turn(replace=True)` replaced only when the LAST entry was a turn, and
    under intents-first the prose entry is appended between the two writes — so
    every turn was logged, then logged again. The live save read as though the
    spawn had resolved twice, which is a whole wrong theory to rule out.
    """
    import ast
    from pathlib import Path

    src = Path("play/views.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_log_turn")
    text = ast.get_source_segment(src, fn) or ""
    assert "turn_log[-1]" not in text, (
        "_log_turn looks at the last entry again; the prose entry sits between "
        "the two writes, so the replace misses and the turn is logged twice")


def test_every_door_that_resolves_also_knows_how_to_undo():
    """A ratchet, because the fix is only as good as the door that forgot it.

    Four functions in `play/views.py` drive resolution — the spoken turn, the
    combat panel, the dice popup and the NPC loop — and each has its own refusal
    branch. `_advance` was the one the live 502 came through; nothing stops the
    next door from being written without a rollback, and the symptom (ghost
    creatures appearing in a later save) points nowhere near the code.
    """
    import ast
    from pathlib import Path

    src = Path("play/views.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    guilty = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        body = ast.get_source_segment(src, fn) or ""
        if ".run(" not in body and ".resume(" not in body:
            continue
        if ".snapshot()" not in body or ".restore(" not in body:
            guilty.append(fn.name)
    assert not guilty, (
        f"{guilty} resolve intents without taking a snapshot to restore on "
        f"refusal — a raise half-way through leaves the earlier half standing")


def test_a_fight_never_ends_a_request_on_somebody_elses_turn():
    """"It is not your turn" with nothing that can make it your turn is a dead game.

    Measured live on 2026-09-01: a market fight held twelve creatures in
    initiative — ten thugs, a woman and a collective. `_run_npc_turns` had a
    fixed budget of twelve, so all twelve iterations went on NPCs and it
    returned with a thug still holding the turn. The combat panel answered "It
    is not your turn", the free-text box goes through the same gate, and nothing
    in the app advances the order except the loop that had just given up. There
    was no way forward at all.

    Two halves, and both are needed: the budget is now a round rather than a
    constant, and if it ever runs out anyway the turn is parked on the player.
    """
    import ast
    from pathlib import Path

    src = Path("play/views.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    loop = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_run_npc_turns")
    body = ast.get_source_segment(src, loop) or ""
    assert "len(scene.initiative)" in body, (
        "the NPC budget is a constant again; a fight bigger than it can never come "
        "back round to the player")
    assert "_hand_the_turn_back" in body, (
        "_run_npc_turns can fall out of its loop with an NPC holding the turn and "
        "say nothing about it")

    panel = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "combat_act")
    text = ast.get_source_segment(src, panel) or ""
    assert "It is not your turn." not in text or "_run_npc_turns" in text, (
        "the panel refuses a turn it holds without running the turns it is "
        "waiting on")


def test_the_turn_comes_back_to_the_player_from_any_slot():
    """The recovery itself, on a scene parked exactly as the live save was."""
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene

    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=5))
    # Four thugs, not ten: since 2026-09-19 a spawn of five or more arrives as one troop
    # with a shared pool (item 33), and this test wants several separate creatures in the
    # initiative so the parked slot can be any of them.
    engine.run(engine.validate([
        {"op": "spawn", "because": "the crowd",
         "params": {"template": "thug", "count": 4, "zone": "engaged"}},
        {"op": "begin_encounter", "because": "the ambush",
         "params": {"sides": {"you": ["pc"],
                              "them": [f"c{i}" for i in range(1, 5)]}}}]))

    class _Campaign:
        def __init__(self, scene):
            self.scene = scene
            self.transcript = []

    c = _Campaign(scene)
    parked = next(i for i, (r, _) in enumerate(scene.initiative) if r != "pc")
    scene.turn = parked
    assert scene.current_ref() != "pc"

    from play.views import _hand_the_turn_back

    _hand_the_turn_back(c, "back to you")
    assert scene.current_ref() == "pc", "the player still cannot act"
    assert c.transcript, "the skipped round happened silently"
