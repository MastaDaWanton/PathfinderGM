"""The board's fight payload (`scene.grid.tactics`, play/views.py `_tactics`), 2026-11-13.

The owner chose the polish mocks' variant D (docs/mock/polish/variants/d-phone-worst-case on
mock/polish) and asked for everything it has that 0.3.0 lacked. D drew threatened squares,
safe and provoking moves, fog, a hunch's range and an attack preview from `extras` that
docs/mock/polish/build_data.py worked out by hand; the live `/api/state` sent none of them,
so the table could not draw one. These are those extras, from the same engine functions the
rules use, and what each must never say about a creature the player has not found.
"""
from __future__ import annotations

import json

from play import campaign as campaign_mod
from play import views
from rules import awareness, reactions
from rules.bestiary import instantiate
from tests.test_hidden_leaks import _board


def _camp(s):
    return campaign_mod.Campaign(id="board-tactics", world_source="fixtures/pangrella-campaign.json",
                                 scene=s, seed=7)


def _fight():
    """Kesst at (5,5), a goblin she can see beside her at (6,5), and the hidden goblin of
    tests/test_hidden_leaks.py at (9,9) with a hunch of it."""
    s, e, hidden = _board(goblin_at=(9, 9))
    awareness.hunch(s, s.pc(), hidden)
    seen = instantiate("goblin", scene=s, index=1)
    s.add(seen, at=(6, 5))
    s.sides["them"].append(seen.ref)
    s.initiative.append((seen.ref, 5))
    return s, e, hidden, seen


def _tactics(s):
    return views._state(_camp(s))["scene"]["grid"]["tactics"]


def test_threat_and_provokes_are_the_rules_own_answers():
    """Before: the live state sent no threat and no provokes, so the board could not tell a
    safe step from a move that hands the goblin a free swing. Each now matches
    `reactions.threatened_by` and `reactions.provoked_by_move` square for square (the view
    asks the second once per distinct vacated footprint: 112 calls were 111 ms)."""
    s, e, hidden, seen = _fight()
    tac = _tactics(s)
    assert set(tac["threat"]) == {f"{x},{y}" for x, y in reactions.threatened_by(s, seen.ref)}
    here = tuple(s.positions["pc"])
    for x, y, _cost, lvl in views._grid_state(s)["reachable"]:
        who = sorted({r for r, _ in reactions.provoked_by_move(s, "pc", here, (x, y))
                      if r != hidden.ref})
        assert tac["provokes"].get(f"{x},{y}", []) == who, (x, y)
    # A five-foot step provokes nothing; walking off does, from the goblin beside her.
    assert "4,5" not in tac["provokes"]
    assert tac["provokes"]["2,5"] == [seen.ref]


def test_the_attack_preview_is_the_number_the_roll_uses():
    """The readout leads with the PC's own total against the foe. It is the swing loop's
    sum (`Engine.attack_preview` shares `_situational_attack_mods` with it), so a real
    attack's roll asks for exactly that modifier, term for term, and the foe's AC is in
    no entry."""
    s, e, hidden, seen = _fight()
    row = _tactics(s)["attack"][seen.ref][0]
    assert row["in_reach"] is True
    assert set(row) == {"weapon", "name", "bonus", "terms", "situational", "in_reach"}
    res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": seen.ref,
                             "because": "a stab", "params": {}}]))
    asked = res.awaiting
    assert asked["modifier"] == row["bonus"]
    assert [[t["source"], t["value"]] for t in asked["breakdown"] if t["value"]] == row["terms"]


def test_flanking_is_a_situational_term():
    """Situational terms (flanking, higher ground, range) are drawn in gold apart from the
    sheet's own: `position.attack_mods` gives flanking with the watchman opposite."""
    s, e, hidden, seen = _fight()
    ally = instantiate("watchman", scene=s)
    s.add(ally, at=(7, 5))
    s.sides["us"].append(ally.ref)
    row = _tactics(s)["attack"][seen.ref][0]
    assert any("flank" in t.lower() for t, _ in row["situational"]), row
    assert row["situational"][0] in row["terms"]


def test_unseen_squares_are_the_line_of_sights():
    """Fog is `Grid.line_of_sight` from the PC: a wall along row 7 from column 2 to 8 hides
    the squares straight behind it, and the remembered answer is asked again when the
    terrain changes (a wall knocked down must lift the fog)."""
    s, e, hidden, seen = _fight()
    for x in range(0, 12):
        s.grid.blocked.add((x, 7))
    unseen = {tuple(p) for p in _tactics(s)["unseen"]}
    assert (5, 9) in unseen and (5, 6) not in unseen
    for x in range(0, 12):
        s.grid.blocked.discard((x, 7))
    assert (5, 9) not in {tuple(p) for p in _tactics(s)["unseen"]}


def test_a_hidden_foe_appears_in_none_of_it():
    """The leak this guards: every field keyed by ref or square would place the hidden
    goblin — its threatened squares round (9,9), its ref as a provoker, an attack preview
    against it, its name among a spell's caught. It is in none of them; the hunch is a
    count and the squares within 30 ft of the PC, never a ref or the goblin's square."""
    s, e, hidden, seen = _fight()
    c = _camp(s)
    c.turn_log = [{"kind": "turn", "outcomes": [{"op": "cast", "effects": [
        {"kind": "cast", "spell": "burning-hands", "caught": [seen.ref, hidden.ref],
         "area": {"squares": [[6, 5, 0], [9, 9, 0]]}}]}]}]
    grid = views._state(c)["scene"]["grid"]
    tac = grid["tactics"]
    assert hidden.ref not in json.dumps(tac)
    assert "10,10" not in tac["threat"]           # only the hidden goblin threatens it
    assert grid["areas"][0]["caught"] == [seen.ref]
    assert [(h["within_ft"], h["count"]) for h in tac["hunches"]] == [(30, 1)]
    assert set(tac["hunches"][0]) == {"within_ft", "count", "squares"}
    # Found, it is in every field.
    awareness.pinpoint(s, s.pc(), hidden, "spotted")
    assert hidden.ref in json.dumps(_tactics(s)["attack"])
    assert _tactics(s)["hunches"] == []


def test_outside_a_fight_there_is_nothing():
    """Only while it matters: out of an encounter the payload is {}, so a walk round town
    pays nothing for it."""
    s, e, hidden, seen = _fight()
    s.initiative = []
    assert not s.in_encounter
    assert _tactics(s) == {}


def test_a_preview_leaves_the_scenes_engine_as_it_was():
    """`Campaign.engine()` lends a fresh engine and dice to the scene; the preview builds
    one and must put back whatever the turn was using."""
    s, e, hidden, seen = _fight()
    c = _camp(s)
    dice, engine = s._dice, s._engine
    shown = {r: a for r, a in s.actors.items() if a.is_pc or awareness.player_locates(s, a)}
    assert views._tactics(c, shown, views._grid_state(s)["reachable"])["attack"]
    assert s._dice is dice and s._engine is engine


def test_the_readout_loads_before_the_first_board_is_drawn():
    """renderMap calls `mapReadout` (25-map-readout.js) and draws the first board while the
    later scripts are still loading (measured for the zoom script, tests/test_map_zoom.py),
    so the readout's tag sits with the zoom's, before 04."""
    from pagesource import _SRC, TABLE

    tags = [m for m in _SRC.findall(TABLE.read_text(encoding="utf-8")) if "js/table/" in m]
    at = {n: next(i for i, t in enumerate(tags) if n in t)
          for n in ("24-map-zoom.js", "25-map-readout.js", "04-combat-and-turns.js")}
    assert at["24-map-zoom.js"] < at["25-map-readout.js"] < at["04-combat-and-turns.js"], at


def test_hover_only_paints_where_a_pointer_can_hover():
    """Variant D's phone pass: on a touch screen the first tap applies :hover and leaves it
    stuck, so a tapped 3D square stayed gold after the finger left. Every board hover rule
    sits inside `(hover: hover) and (pointer: fine)`."""
    from pagesource import TABLE

    page = TABLE.read_text(encoding="utf-8")
    for rule in ("#view3d .lit.face-top:hover", "#view3d .xsq:hover", "#view3d:not(:hover) .xsq"):
        before = page[:page.index(rule)]
        assert before.rstrip().endswith("{") and "(hover: hover) and (pointer: fine)" in \
            before[-80:], rule


def test_a_hidden_creatures_turn_does_not_name_it():
    """`scene.turn_ref` sent the hidden goblin's ref on its own turn: the one field the
    0.3.0 hidden-leak pass missed (found by the variant D port, 2026-11-13)."""
    s, _e, hidden, seen = _fight()
    s.turn = next(i for i, (r, _v) in enumerate(s.initiative) if r == hidden.ref)
    assert s.current_ref() == hidden.ref
    assert views._state(_camp(s))["scene"]["turn_ref"] == ""
    s.turn = next(i for i, (r, _v) in enumerate(s.initiative) if r == seen.ref)
    assert views._state(_camp(s))["scene"]["turn_ref"] == seen.ref
