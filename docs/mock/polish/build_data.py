"""Regenerate data.js for the visual-polish mocks, from the engine.

Run from the repository root, with a throwaway data directory:

    PATHFINDER_GM_DATA=<somewhere disposable> python docs/mock/polish/build_data.py

Nothing in data.js is written by hand. The method is docs/mock/table-layout's: the scene
is set up through the engine, saved with the app's own `Campaign.save`, loaded back with
`Campaign.load` and read through `play/views.py _state` (the function behind
`/api/state`), so `scenes.*.state` is byte for byte what the table is sent. Every extra
beside it is a named engine function, and each field says which one.

What is placed rather than played, and why (the README repeats this):

- Positions are written into `scene.positions` after `begin_encounter`, the way the
  engine's own tests set up a fight (tests/test_sneak_attack.py): `begin_encounter` lays
  the battlefield itself, and there is no op that stands a creature on a chosen square.
- The PC's turn comes from initiative: the dice seed is the first one, counting from 0,
  on which Kesst wins it. Creature turns are model calls in the app, so a later round
  cannot be reached without a model; it is round 1, the PC's turn.
- One goblin is hidden with the same Hidden effect the engine's Stealth success applies
  (tests/test_hidden_state.py does the same), and the PC is given a hunch about it with
  `awareness.hunch`, the applicator the Perception rules use.
- A watchman stands on the PC's side, because flanking needs an ally opposite the PC
  (`position.flanking_with`) and Kesst has no companion in the fixture.

Hidden information stays out (coordinator ruling): no target AC, no needed d20, no
hidden creature's square, no other creature's hidden roll. Engine answers that need the
hidden goblin are computed and then filtered to what the player could know.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")
assert os.environ.get("PATHFINDER_GM_DATA"), "set PATHFINDER_GM_DATA to a throwaway folder"

import django  # noqa: E402

django.setup()

from play import campaign as campaign_mod  # noqa: E402
from play import views  # noqa: E402
from rules import areas, awareness, compulsion, reactions, residency, sky, spells, states  # noqa: E402
from rules import grid as gridmod  # noqa: E402
from rules import position as position_mod  # noqa: E402
from rules.activeeffect import ActiveEffect  # noqa: E402
from rules.bestiary import instantiate  # noqa: E402
from rules.dice import Dice  # noqa: E402
from rules.engine import Engine, Scene  # noqa: E402
from rules.sheet import load_pc  # noqa: E402
from world.loader import load_cached  # noqa: E402

WORLD = "fixtures/pangrella-campaign.json"
CITY = "6953424c8a82"                       # Zhilvarnia
GATE = CITY + "~urban:the-gate"             # floorplan BY_SPOT: the wall-walk over the gate
PC_FILE = "fixtures/pc-kesst.json"
OUT = Path(__file__).resolve().parent / "data.js"
FIGHT_HOUR = 10 * 60
# The hours for scene B: inside sky.py's own "dawn" window but before DAWN_MINUTE (so the
# engine still calls it dim), its noon, and its night.
HOURS = {"B-dawn": sky.DAWN_MINUTE - 30, "B-noon": 12 * 60, "B-night": 21 * 60}

# Where everybody stands (x, y[, level]). The gate's plan: a wall-walk at level 2 on
# columns 10-11, a rail along column 9, stones at (3,7), (6,8), (9,3), (9,4).
PC_AT = (4, 5)
ALLY_AT = (6, 5)           # opposite the first goblin: the PC flanks it
FOES = [
    ("flanked", (5, 5)),        # between the PC and the watchman
    ("beside", (4, 6)),         # adjacent: walking off provokes from it and the first
    ("on the wall", (10, 5, 2)),  # ten feet up on the wall-walk
    ("hidden", (7, 8)),         # behind the stone at (6,8), and hidden
]


def build(seed: int):
    world = load_cached(WORLD)
    s = Scene(location_id=CITY)
    pc = load_pc(PC_FILE)
    s.add(pc)
    s.clock_minutes = FIGHT_HOUR
    e = Engine(s, Dice(seed=seed), world=world)
    e.place_party(GATE)
    ally = instantiate("watchman", scene=s)
    s.add(ally, zone="near")
    foes = []
    for i, _ in enumerate(FOES):
        f = instantiate("goblin", scene=s, index=i)
        s.add(f, zone="near")
        foes.append(f)
    e.run(e.validate([{"op": "begin_encounter", "actor": pc.ref, "because": "the mock's fight",
                       "params": {"sides": {"party": [pc.ref, ally.ref],
                                            "goblins": [f.ref for f in foes]}}}],
                     origin="author:test"))
    return s, e, pc, ally, foes


seed = next(n for n in range(500) if build(n)[0].current_ref() == "pc")
scene, engine, pc, ally, foes = build(seed)
scene.positions[pc.ref] = PC_AT
scene.positions[ally.ref] = ALLY_AT
for f, (_, at) in zip(foes, FOES):
    scene.positions[f.ref] = at
roles = {f.ref: role for f, (role, _) in zip(foes, FOES)}
hidden = foes[3]
hidden.apply_effect(ActiveEffect(
    name="Hidden", kind="condition", key=awareness.SNEAKING_KEY,
    source=awareness.STEALTH_ORIGIN, origin=awareness.STEALTH_ORIGIN,
    duration="until-dismissed", tags=states.tags_for(awareness.SNEAKING_KEY),
    payload={"result": 30, "at": scene.at, "ends_when": dict(awareness.ENDS_ON_ATTACK),
             "pace": "half"}))
awareness.hunch(scene, pc, hidden)
assert scene.current_ref() == pc.ref and scene.in_encounter

camp = campaign_mod.Campaign(id="polish-mock", world_source=WORLD, scene=scene, seed=seed)
saved = camp.save()


def state_at(clock: int | None = None) -> tuple[dict, campaign_mod.Campaign]:
    c = campaign_mod.Campaign.load(saved)
    if clock is not None:
        c.scene.clock_minutes = clock
    return views._state(c), c


# --- the extras ----------------------------------------------------------------------------

def known(c, ref) -> str:
    """What the PC knows of where `ref` is: awareness.locates / has_hunch."""
    s = c.scene
    me, them = s.pc(), s.actors[ref]
    if awareness.locates(s, me, them):
        return "pinpoint"
    return "hunch" if awareness.has_hunch(me, them) else "unknown"


def terms(mods) -> list:
    return [[m.source, m.value] for m in mods if m.value]


def extras(c) -> dict:
    s = c.scene
    e = c.engine()
    me = s.pc()
    g = s.grid
    here = s.positions[me.ref]
    foe_refs = [r for r in s.sides["goblins"]]
    aware = {r: known(c, r) for r in foe_refs}
    seen = [r for r in foe_refs if aware[r] == "pinpoint"]
    reach = [(x, y) for x, y, *_ in views._grid_state(s)["reachable"]]

    def lvl(sq):
        v = g.ground(sq)
        return (sq[0], sq[1], v) if v else tuple(sq)

    # Squares each foe the PC can locate threatens. reactions.threatened_by is what attacks
    # of opportunity are decided on (it wraps grid.threatened_squares with the creature's
    # reach and whether it can swing at all).
    threatened = {r: sorted(list(sq) for sq in reactions.threatened_by(s, r)) for r in seen}

    # Each reachable square: does arriving there provoke, and from whom. Asked of
    # reactions.provoked_by_move(start, end), the very call the move op makes (engine.py
    # `_swings_at(ref, reactions.provoked_by_move(...))`), which already holds the 5-ft step
    # exception. Provokers the PC cannot locate are dropped.
    provokes = {}
    for sq in reach:
        who = [r for r, _ in reactions.provoked_by_move(s, me.ref, here, lvl(sq)) if r in seen]
        if who:
            provokes[f"{sq[0]},{sq[1]}"] = who

    # Line of sight from the PC to every square (grid.line_of_sight), and the cover each
    # visible foe has against the PC (position.cover_of: hard cover from grid.cover_between,
    # soft cover from a body in the way). The kind only: its +4 is part of the hidden AC.
    sight = {"from": list(here),
             "squares": [[x, y, 1 if g.line_of_sight(tuple(here), lvl((x, y))) else 0]
                         for y in range(g.height) for x in range(g.width)],
             "cover": {r: position_mod.cover_of(s, me, s.actors[r]) or "none" for r in seen}}

    # The PC's own bonus against each foe it can locate, itemised as the attack path builds
    # it (engine.py, the swing loop): Actor.attack_modifiers with the defender and the gap,
    # compulsion.penalty_against, then position.attack_mods. The target's AC is hidden in
    # the game (no dc is shown on an attack roll), so it is not here.
    attack = {}
    for r in seen:
        foe = s.actors[r]
        rows = []
        for key in dict.fromkeys(w.lower() for w in me.weapons):
            w = me.weapon(key)
            mods = (me.attack_modifiers(key, 0, defender=foe, range_ft=e._gap_ft(me, foe))
                    + compulsion.penalty_against(me, r)
                    + position_mod.attack_mods(s, me, foe, w))
            situational = position_mod.attack_mods(s, me, foe, w) \
                + compulsion.penalty_against(me, r)
            rows.append({"weapon": key, "name": w.get("name", key),
                         "category": w.get("category", ""),
                         "in_reach": tuple(s.positions[r][:2]) in reactions.threatened_by(s, me.ref)
                         if w.get("category") != "ranged" else None,
                         "bonus": sum(m.value for m in mods),
                         "terms": terms(mods), "situational": terms(situational)})
        attack[r] = rows

    # Burning hands, laid from a real aim at the goblin beside the PC (areas.lay with the
    # spell's own printed area; areas.caught for who is in it). Kesst cannot cast it: this
    # is the geometry a cast would get, for drawing. Caught creatures the PC cannot locate
    # are dropped.
    spell = spells.get("burning-hands")
    area = areas.lay(s, me.ref, spell, 1, areas.Aim("ref", foes_by_role(s)["beside"]))
    caught = [r for r in areas.caught(s, area, exclude=(me.ref,))
              if r not in foe_refs or r in seen]

    return {
        "threatened": {"source": "rules/reactions.py threatened_by (grid.threatened_squares "
                                 "with reach); foes the PC can locate", "by_foe": threatened},
        "provokes": {"source": "rules/reactions.py provoked_by_move(pc, here, square) for "
                               "each reachable square; 5-ft steps never provoke",
                     "squares": provokes},
        "sight": dict(sight, source="rules/grid.py Grid.line_of_sight from the PC per "
                                    "square [x, y, 1|0]; rules/position.py cover_of per foe"),
        "attack_preview": {"source": "Actor.attack_modifiers(defender, range_ft) + "
                                     "compulsion.penalty_against + position.attack_mods; "
                                     "target AC hidden in the game, so not included",
                           "by_foe": attack},
        "spell_area": {"source": "rules/areas.py lay(burning-hands, CL 1, aim ref) and caught",
                       "spell": spell.id, "shape": area.shape, "length_ft": area.length_ft,
                       "origin": list(area.origin), "direction": area.direction,
                       "aim": area.aim.as_dict(),
                       "cells": [list(x) for x in sorted(area.cells)], "caught": caught,
                       # The shape scene.grid.areas has after a real cast (views._latest_areas)
                       "as_grid_area": {"spell": spell.id,
                                        "cells": [list(x) for x in sorted(area.cells)]}},
        # A hunch is shown without its ref: the player knows something is within 30 ft
        # (awareness.NOTICE_RANGE_FT), not who or where. Unknown foes are left out.
        "awareness": {"source": "rules/awareness.py locates / has_hunch, PC as observer",
                      "pinpoint": seen,
                      "hunches": [{"within_ft": awareness.NOTICE_RANGE_FT}
                                  for v in aware.values() if v == "hunch"]},
        "roles": {r: roles[r] for r in foe_refs if r in seen},
    }


def foes_by_role(s):
    return {role: ref for ref, role in roles.items()}


def light(c) -> dict:
    s = c.scene
    me = s.pc()
    g = s.grid
    return {"source": "Scene.ambient_light, Scene.light_at(square, viewer=PC), "
                      "sky.phase_at, residency.day_part",
            "clock_minutes": s.clock_minutes,
            "ambient": s.ambient_light(),
            "phase": sky.phase_at(s.clock_minutes),
            "day_part": residency.day_part(s.clock_minutes),
            "at_square": [[x, y, s.light_at((x, y), viewer=me)]
                          for y in range(g.height) for x in range(g.width)]}


def keep(state: dict) -> dict:
    # What the board reads (state.scene) plus the side panel's PC summary and the attack
    # slots, for variants that show more of the turn. Everything else is the book's.
    return {k: state[k] for k in ("scene", "pc", "attacks", "awaiting")}


scenes = {}
st, c = state_at()
scenes["A"] = {"label": "The fight", "state": keep(st), "extras": extras(c), "light": light(c)}
for name, clock in HOURS.items():
    st, c = state_at(clock)
    scenes[name] = {"label": f"The hour: {name[2:]}", "state": keep(st), "extras": extras(c),
                    "light": light(c)}

# The hidden goblin must not reach the extras in any field. The state is the game's own
# payload and is kept as sent: `_state` drops the hidden goblin from `actors` but lists it
# in `initiative` with its name and score (found while building this; README, "Found").
for sc in scenes.values():
    assert hidden.ref not in [a["ref"] for a in sc["state"]["scene"]["actors"]]
    assert f'"{hidden.ref}"' not in json.dumps(sc["extras"]), "the hidden goblin reached the extras"
    leak = [i for i in sc["state"]["scene"]["initiative"] if i["ref"] == hidden.ref]
assert leak, "_state no longer lists the hidden goblin in initiative: update the README"

data = {
    "source": {
        "world": WORLD + " (Zhilvarnia, a real World Bible export), " + GATE,
        "pc": PC_FILE,
        "scene": "set up through the engine (begin_encounter, origin author:test), saved "
                 "with Campaign.save, loaded with Campaign.load, read through "
                 "play/views.py _state",
        "seed": seed,
        "placed": "positions written after begin_encounter, as the engine's tests do; one "
                  "goblin hidden with the Stealth effect and a hunch from awareness.hunch",
    },
    "scenes": scenes,
}
with open(OUT, "w", encoding="utf-8") as f:
    f.write("// Generated for the polish mocks from real engine output.\n")
    f.write("// Regenerate with docs/mock/polish/build_data.py; do not edit by hand.\n")
    f.write("window.POLISH_DATA = ")
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")
a = scenes["A"]
print(f"wrote {OUT.name}: seed {seed}, round {a['state']['scene']['round']}, turn "
      f"{a['state']['scene']['turn_ref']}, {len(a['state']['scene']['actors'])} actors shown, "
      f"{len(a['state']['scene']['grid']['reachable'])} reachable, "
      f"{len(a['extras']['provokes']['squares'])} provoking, "
      f"pinpointed {a['extras']['awareness']['pinpoint']}, "
      f"hunches {len(a['extras']['awareness']['hunches'])}, "
      f"light " + ", ".join(f"{k} {v['light']['ambient']}" for k, v in scenes.items()))
