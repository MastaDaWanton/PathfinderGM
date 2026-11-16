"""A way deeper: the hidden dungeon a venture may hold (owner, 2026-11-15).

"perhaps a percentage roll to turn any of those ventures into a full dungeon, like you go to
the cave and you find a boulder that has broken revealing a small gap and a passage, or a
trapdoor in the ruins that leads deeper in, or a mine cart system that is broken over a
large pit with a ladder going down etc... A rooftop wouldnt make sense for this but almost
anywhere else could reasonable fit it in."

**The roll.** A seeded d100 off the venture's own id against `chance` — so the same cave
always has, or always lacks, the same way down, as `places.venture_set` makes the same
cellar every time. The base is the implementer's (an owner call): Dungeon Crawl Stone Soup
offers its sewer portal on 8% of eligible levels (`e.chance(800)` out of 10,000,
crawl-ref/source/dat/des/portals/sewer.des, D:3-6, once a game); a solo player enters
perhaps a dozen ventures a campaign, and at 8% most would never see one, so the base is
`BASE_CHANCE` and the place's `volatility` moves it exactly as it moves the venture's
"is it inhabited" roll (`volatility.scale`: a third on calm ground, twice on lawless).

Not the rooftops (the owner's word) and not the back alley: the way under a street is
already its own venture (the sewers, the cellars), and an alley has no spots of its own —
a way down there would open in the street itself, under the town's traffic, a second door
to ground the first two doors already reach.

**The feature** is the owner's own list, a row per kind (`FEATURES`): found by Perception
at the CRB's secret-door DC ("DC 20 for a typical secret door", CRB p.413), or in plain
sight (the broken cart line); opened, where it must be, by Strength at the CRB's door
break DCs (Table: Doors — simple wooden stuck 13, good wooden stuck 16, locked 18) or
Disable Device at the average lock's 25. The reactive check is made once on arrival at its
spot ("Most Perception checks are reactive", CRB p.102); a search makes it again.

**The dungeon behind it** — what the traditions measured, and what was taken:

- *B/X stocking* (Moldvay Basic B52, as restated by Old-School Essentials, "Designing a
  Dungeon"): d6 — 1-2 empty, 3-4 monster, 5 special, 6 trap; treasure 1-in-6 in an empty
  room, 3-in-6 with a monster, 2-in-6 with a trap. Taken, row for row, with two changes:
  "special" is read as empty, because a special room is authored content (the moaning
  corridor, the talking statue) and nothing here may author it; and a monster room's
  treasure is the creature's own (`rules/treasure.py` pays its printed class when it falls)
  rather than a second roll on top, which would pay that fight twice.
- *The Five Room Dungeon* (Johnn Four): entrance and guardian, puzzle, setback, climax,
  reward. Taken as the skeleton the d6 fills in: the last room is the climax (a guarded
  fight, `encounter_budget`'s "guards and lairs may be challenging or hard") and holds the
  reward; the room before it is the setback (always a trap). Four to six rooms: a solo
  player finishes it in one sitting.
- *Gygax's DMG Appendix A* rolls passage by passage and room by room. **Refused**: its
  own readers call the output a goblin, a trap and a skeleton in a row for no reason, and
  its sample map is all dead ends. Rooms here are drawn whole, from a closed list.
- *Tree layouts* (Brogue's first pass, the Cogmind developer's "no loops and lots of dead
  ends"): **abandoned** by both — Brogue adds loops after the tree, Unexplored (Joris
  Dormans, cyclic generation) builds the cycle first. Taken in the smallest form: a side
  room that also opens onto the main line further down, so there are two ways through and
  the side room is not a dead end.
- *Locks and keys* (Dormans' "hard" and "soft" locks): every door here is soft — forced or
  picked at the book's DC — because a key that must be found is authored content again.

**Traps** are the CRB's sample traps (content/rules/traps.json): Perception to find,
Disable Device to disarm (a difficult device, 2d4 rounds; failing by 5 or more springs
it, CRB p.94). A location trap fires on whoever walks in unaware; once found, the party
steps round it (an owner call); a touch trap sits on a door and fires on whoever works the
door until it is disarmed.

**Treasure** is the CRB's Treasure Values per Encounter at the party's APL
(`treasure._BY_CR`), rolled 50-150% as `treasure.worth` rolls it, as coin in a container
on the props ledger, which `give` already empties.

Every room is a founded place (`origin` "dungeon"), saved in `Scene.founded` with its state
under `dungeon`, walked by `travel`, and on the place chart one exit beyond where the party
has been (play/places_found.py). Nothing here is minted before the way down is found.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from . import places as places_mod

BASE_CHANCE = 20
# A step between two rooms of a dungeon: local movement, a minute, not the overland hour
# `outskirts.hop_minutes` charges between two places out in the land.
HOP_MINUTES = 1
ORIGIN = "dungeon"

# The owner's own examples, one row per kind; `spot` is the venture spot it lies in (the
# last one minted when that one was not). `open` is None for a way that needs only finding.
# `sign` is what anybody standing at the spot sees while the way is still hidden, told on
# every arrival (`arrived`): playtest 2026-11-16 #48, the culvert lay in the main channel
# (that venture had no sump) and arriving there told nothing, so nothing said where to
# search. The secret door stays at its DC; the sign only says a search here is worth it.
# An owner call: the CRB gives no clue rule, and the common GM advice to give a hidden door
# a visible clue could not be traced to a primary source (searched 2026-11-16).
FEATURES: dict[str, list[dict]] = {
    "cave": [{"name": "the split boulder", "spot": "the deep chamber", "find": 20, "open": None,
              "about": "a boulder split by the frost, a gap behind it, and a passage going down",
              "sign": "a cold draught comes from somewhere among the rocks"}],
    "mine": [{"name": "the broken cart line", "spot": "the gallery", "find": 0, "open": None,
              "about": "a mine-cart line broken off over a pit, and a ladder going down the side of it"},
             {"name": "the boarded winze", "spot": "the gallery", "find": 20,
              "open": {"force": 13},
              "about": "a shaft going down, boarded over with rotten timbers",
              "sign": "the floor of the gallery sounds hollow underfoot in one place"}],
    "ruins": [{"name": "the trapdoor", "spot": "the undercroft", "find": 20, "open": {"force": 16},
               "about": "a trapdoor under the rubble, its ring rusted, and steps beneath it",
               "sign": "the rubble lies oddly here, as if it were heaped over something"}],
    "crypt": [{"name": "the trapdoor", "spot": "the deep chamber", "find": 20, "open": {"force": 16},
               "about": "a trapdoor under the dust of the floor, and steps beneath it",
              "sign": "the dust of the floor lies thinner along one line, as if air moves under it"},
              {"name": "the hollow tomb", "spot": "the niches", "find": 20, "open": {"force": 16},
               "about": "a tomb with no floor to it, and steps going down inside",
              "sign": "one of the tombs is colder to the touch than the rest"}],
    "sewers": [{"name": "the bricked-up culvert", "spot": "the sump", "find": 20, "open": None,
                "about": "an old culvert bricked up long ago, the mortar gone to mush",
                "sign": "one stretch of the wall is newer brick than the rest"}],
    "cellar": [{"name": "the sealed stair", "spot": "the vaults", "find": 20, "open": {"force": 16},
                "about": "a flagstone with an iron ring in it, and a stair under it",
              "sign": "one flagstone of the floor sits a little proud of the others"}],
    "tower": [{"name": "the locked trapdoor", "spot": "the foot", "find": 20,
               "open": {"force": 18, "pick": 25},
               "about": "a trapdoor in the floor, iron-bound and locked",
               "sign": "the floorboards here are newer than the rest"}],
}

# Rooms by the ground's family, (name, about); the last is the climax's. A closed list: no
# model names a room.
_NATURAL = (("the low crawl", "a passage you go through bent double"),
            ("the dripping gallery", "water running down the walls"),
            ("the bone-strewn den", "old bones underfoot"),
            ("the flooded grotto", "standing water, knee deep"),
            ("the narrow cleft", "a crack in the rock just wide enough"),
            ("the deep hollow", "the bottom of it, as far down as it goes"))
_DUG = (("the lower drift", "a level dug below the old one"),
        ("the ore chute", "a steep chute the ore came down"),
        ("the old stope", "a worked-out chamber, its props rotten"),
        ("the pump room", "a broken pump and its pipes"),
        ("the collapsed face", "where the digging stopped"),
        ("the deep working", "the last thing they dug"))
_BUILT = (("the guardroom", "benches and a rack, long empty"),
          ("the collapsed hall", "half the roof down"),
          ("the ossuary", "bones stacked in the walls"),
          ("the well room", "an old well shaft"),
          ("the long gallery", "a corridor with niches along it"),
          ("the sealed vault", "the room the rest was built to keep"))
ROOMS = {"cave": _NATURAL, "mine": _DUG, "ruins": _BUILT, "crypt": _BUILT,
         "sewers": _BUILT, "cellar": _BUILT, "tower": _BUILT}
# Built ground has doors; a cave or a mine has passages. CRB Table: Doors, good wooden
# door: stuck 16, locked 18; an average lock, Disable Device 25. Stuck one door in five
# (the CRB's doubled figure "for long-abandoned or neglected dungeons"); locked one in ten
# (the book gives no figure: an owner call).
DOOR = {"name": "a good wooden door", "stuck": 16, "locked": 18, "lock": 25}
_HAS_DOORS = frozenset({"ruins", "crypt", "sewers", "cellar", "tower"})

_TRAPS: dict | None = None


def traps() -> dict[str, dict]:
    global _TRAPS
    if _TRAPS is None:
        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "rules" / "traps.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        _TRAPS = {k: v for k, v in data.items() if not k.startswith("_")}
    return _TRAPS


def _rng(head_id: str, salt: str) -> random.Random:
    return random.Random(places_mod._seed(f"{head_id}#{salt}"))


def fits(kind: str) -> bool:
    return kind in FEATURES


def chance(world, head_id: str, parent_id: str = "") -> int:
    from . import volatility

    return max(1, min(95, round(BASE_CHANCE * volatility.scale(world, head_id, parent_id))))


def rolled(head_id: str) -> int:
    """The venture's own d100, the same every time it is asked."""
    return _rng(head_id, "deeper").randint(1, 100)


def feature_of(head_id: str, kind: str) -> dict | None:
    rows = FEATURES.get(kind) or []
    return dict(_rng(head_id, "feature").choice(rows)) if rows else None


def _rec(scene, place_id: str) -> dict | None:
    return next((p for p in scene.founded if p.get("id") == place_id), None)


def room(scene, place_id: str) -> dict | None:
    """The dungeon state of a room, or None when the place is no dungeon room."""
    rec = _rec(scene, place_id)
    return (rec or {}).get("dungeon")


def is_room(place) -> bool:
    return getattr(place, "origin", "") == ORIGIN


def on_entering(world, scene, head: dict, kind: str, spot_ids: list[str]) -> dict:
    """The venture's roll, made on every entry and the same each time; the way down
    marked on the head's saved record on a hit. The record of the roll (hidden)."""
    holds = fits(kind)
    got = {"kind": "way_down", "rolled": 0, "chance": 0, "holds": False}
    if not holds:
        return got
    got["chance"] = chance(world, head["id"], head.get("parent", ""))
    got["rolled"] = rolled(head["id"])
    got["holds"] = got["rolled"] <= got["chance"]
    if got["holds"] and "deeper" not in head:
        feat = feature_of(head["id"], kind)
        want = places_mod.child_id(head["id"], feat["spot"])
        spot = want if want in spot_ids else (spot_ids[-1] if spot_ids else head["id"])
        head["deeper"] = {"kind": kind, "feature": feat, "spot": spot,
                          "found": False, "noticed": False}
    return got


def sign_of(deeper: dict) -> str:
    """The way down's sign: from its row in `FEATURES`, so a way recorded before the rows
    had signs still shows one."""
    feat = deeper.get("feature") or {}
    if int(feat.get("find") or 0) <= 0:
        return ""
    row = next((r for r in FEATURES.get(deeper.get("kind", ""), ())
                if r["name"] == feat.get("name")), feat)
    return str(row.get("sign") or "")


def deeper_at(scene, place_id: str) -> tuple[dict, dict] | None:
    """(the venture's head record, its way-down record) whose feature lies here."""
    for rec in scene.founded:
        d = rec.get("deeper")
        if d and d.get("spot") == place_id:
            return rec, d
    return None


def generate(head_id: str, kind: str, spot_id: str, terrain: str, feature: dict,
             apl: int) -> list[dict]:
    """The rooms behind the way down, as founded records, seeded off the venture."""
    from . import treasure

    r = _rng(head_id, "rooms")
    names = list(ROOMS[kind])
    climax = names.pop()
    n = 4 + r.randint(0, 2)                  # 4..6 rooms
    r.shuffle(names)
    picked = names[:n - 1] + [climax]
    centre = treasure._BY_CR[max(0, min(20, int(apl)))]
    trap_rows = [k for k, v in traps().items() if v["cr"] <= max(1, int(apl) + 1)]

    def worth(share: float) -> int:
        roll = r.randint(1, 6) + r.randint(1, 6)
        return max(1, round(centre * share * (0.5 + (roll - 2) / 10.0)))

    def door() -> dict | None:
        if kind not in _HAS_DOORS:
            return None
        face = r.randint(1, 10)
        state = "stuck" if face <= 2 else "locked" if face == 3 else "open"
        out = {"name": DOOR["name"], "state": state}
        if state == "stuck":
            out["force"] = DOOR["stuck"]
        if state == "locked":
            out.update(force=DOOR["locked"], pick=DOOR["lock"])
        return out

    # The main line, with the one side room (index `side`) hung off the second room and
    # opening again onto the line two rooms on: the loop.
    main = [i for i in range(n) if i != 1] if n >= 5 else list(range(n))
    side = 1 if n >= 5 else None
    ids: list[str] = []
    out: list[dict] = []
    for i, (label, about) in enumerate(picked):
        if i == 0:
            parent = spot_id
        elif i == side:
            parent = ids[0]
        else:
            parent = ids[main[main.index(i) - 1]]
        pid = places_mod.child_id(parent, label)
        ids.append(pid)
        last = i == n - 1
        if last:
            stock = "monster"
        elif i == main[-2]:
            stock = "trap"           # the Five Room Dungeon's setback, before the climax
        else:
            face = r.randint(1, 6)
            stock = "monster" if face in (3, 4) else "trap" if face == 6 else "empty"
        d = {"of": head_id, "role": "climax" if last else "entrance" if i == 0 else "room",
             "stock": stock, "stocked": False, "cache_gp": 0, "trap": None}
        if i == 0:
            opener = feature.get("open") or {}
            d["door"] = ({"name": feature["name"], "state": "locked" if opener.get("pick")
                          else "stuck", **opener} if opener else None)
        else:
            d["door"] = door()
        if stock == "trap" and trap_rows:
            # A touch trap only where there is a shut door to work (it fires on whoever
            # works it); a location trap anywhere.
            on_door = bool(d["door"]) and d["door"]["state"] != "open"
            pool = [k for k in trap_rows if on_door or traps()[k]["trigger"] != "touch"]
            tid = r.choice(sorted(pool))
            d["trap"] = {"id": tid, "on": "door" if traps()[tid]["trigger"] == "touch"
                         else "room", "found": False, "armed": True}
            if r.randint(1, 6) <= 2:
                d["cache_gp"] = worth(0.5)
        elif stock == "empty" and r.randint(1, 6) == 1:
            d["cache_gp"] = worth(0.5)
        if last:
            d["cache_gp"] = worth(1.0)
        out.append({"id": pid, "name": label, "about": about, "terrain": terrain,
                    "exits": [], "described_only": False, "within": "", "parent": parent,
                    "owner": "", "origin": ORIGIN, "kind": "", "dungeon": d})
    if side is not None and n >= 5:
        # The loop: the side room opens again onto the main line two rooms down.
        rejoin = main[2] if len(main) > 2 else main[-1]
        out[side]["exits"].append(ids[rejoin])
        out[rejoin]["exits"].append(ids[side])
    return out


def door_between(scene, a: str, b: str) -> dict | None:
    """The closed door on the way between two adjacent places, or None when it is open
    or there is none. A room's door is on the way from its parent."""
    for near, far in ((a, b), (b, a)):
        rec = _rec(scene, far)
        d = (rec or {}).get("dungeon")
        if d and rec.get("parent") == near and d.get("door") and d["door"]["state"] != "open":
            return d["door"]
    return None


def shut_line(scene, a: str, b: str) -> str:
    door = door_between(scene, a, b)
    if door is None:
        return ""
    how = ("forced (a Strength check) or its lock picked (Disable Device)"
           if door.get("pick") else "forced (a Strength check)")
    return f"{_cap(door['name'])} is {door['state']}: it has to be {how} first."


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def doors_from(engine, here_id: str) -> list[tuple[str, dict]]:
    """(the place beyond, its closed door) for every closed door out of here."""
    here = places_mod.find(engine.places(), here_id)
    out = []
    for x in getattr(here, "exits", ()) or ():
        door = door_between(engine.scene, here_id, x)
        if door is not None:
            out.append((x, door))
    return out


def _party(engine) -> list:
    from . import states

    pc = engine.scene.pc()
    rest = [a for a in engine.scene.actors.values()
            if not a.is_pc and a.has_state(states.TRAVELS_WITH_YOU) and not a.is_down]
    return ([pc] if pc is not None else []) + rest


# --- the engine's doors --------------------------------------------------------------------

def mint(engine, head: dict, deeper: dict) -> list[str]:
    """The rooms come into being: found, so now real. The names said."""
    from . import encounter_budget

    if any((p.get("dungeon") or {}).get("of") == head["id"] for p in engine.scene.founded):
        return []
    spot = places_mod.find(engine.places(), deeper["spot"])
    terrain = getattr(spot, "terrain", "") or head.get("terrain", "")
    made = generate(head["id"], deeper["kind"], deeper["spot"], terrain, deeper["feature"],
                    encounter_budget.party_apl(engine.scene))
    engine.scene.founded.extend(made)
    return [m["name"] for m in made]


def _found(engine, head: dict, deeper: dict) -> tuple[dict, str]:
    deeper["found"] = True
    mint(engine, head, deeper)
    feat = deeper["feature"]
    first = next((p for p in engine.scene.founded
                  if (p.get("dungeon") or {}).get("of") == head["id"]
                  and (p.get("dungeon") or {}).get("role") == "entrance"), {})
    door = (first.get("dungeon") or {}).get("door")
    tail = (f" {shut_line(engine.scene, deeper['spot'], first['id'])}" if door else
            f" The way down is open, to {first.get('name', 'somewhere below')}.")
    return ({"kind": "way_down_found", "feature": feat["name"], "at": deeper["spot"],
             "leads_to": first.get("id", "")},
            f"Here: {feat['about']} — {feat['name']}.{tail}")


def arrived(engine, place) -> tuple[list[dict], list[str]]:
    """What arriving here does, for a way-down spot and a dungeon room: the reactive look
    for the way down; a trap sprung on whoever walks in unaware; the room stocked on the
    first entry (its creature from the bestiary, its coin on the ledger); and what is here
    said, doors onward included. (effects, tell bits)."""
    fx: list[dict] = []
    bits: list[str] = []
    pc = engine.scene.pc()
    hit = deeper_at(engine.scene, place.id)
    if hit is not None and pc is not None:
        head, deeper = hit
        feat = deeper["feature"]
        if not deeper["found"] and (int(feat["find"]) <= 0 or not deeper["noticed"]):
            deeper["noticed"] = True
            seen = int(feat["find"]) <= 0
            if not seen:
                look = engine.dice.d20(pc.skill_modifiers("perception"),
                                       label=f"{pc.name} notices", visibility="hidden")
                seen = look.total >= int(feat["find"])
            if seen:
                rec, said = _found(engine, head, deeper)
                fx.append(rec)
                bits.append(said)
        sign = sign_of(deeper)
        if not deeper["found"] and sign:
            bits.append(f"{_cap(sign)}.")
    d = room(engine.scene, place.id)
    if d is None:
        return fx, bits
    bits.append(f"{_cap(place.name)}: {place.about}.")
    trap = d.get("trap")
    if trap and trap["armed"] and trap["on"] == "room":
        row = traps()[trap["id"]]
        if trap["found"]:
            bits.append(f"The party steps round {row['name']} they found.")
        else:
            rolls, sprung, said = spring(engine, trap, _party(engine))
            fx.extend(sprung)
            bits.extend(said)
    if not d["stocked"]:
        d["stocked"] = True
        if d["stock"] == "monster":
            got, said = engine._inhabit(place, guarding=d["role"] == "climax")
            fx.extend(got)
            if said:
                bits.append(said)
        if d["cache_gp"]:
            name = "an iron-bound chest" if d["role"] == "climax" else "a small strongbox"
            engine.scene.props.append({
                "name": name, "owner": "", "from_": "", "state": "intact",
                "turn": int(engine.scene.clock_minutes), "at": place.id,
                "contents": {"purse": {"gp": int(d["cache_gp"])}, "goods": {}},
                "origin": f"rule:treasure/{d['of']}"})
            fx.append({"kind": "treasure_placed", "at": place.id, "container": name})
            bits.append(f"There is {name} here.")
    onward = doors_from(engine, place.id)
    for far, door in onward:
        dest = places_mod.find(engine.places(), far)
        bits.append(f"{_cap(door['name'])} leads to {getattr(dest, 'name', 'further in')}; "
                    f"it is {door['state']}.")
    return fx, bits


def spring(engine, trap: dict, victims: list) -> tuple[list, list[dict], list[str]]:
    """The trap goes off: its printed attack, or its pit and the Reflex save that avoids
    it, rolled by the engine against each victim it reaches. (rolls, effects, tells)."""
    from . import dice as dice_mod
    from . import hazards
    from .dice import Modifier

    row = traps()[trap["id"]]
    eff = row["effect"]
    origin = f"rule:trap/{trap['id']}"
    trap["armed"] = False
    trap["found"] = True
    trap["sprung"] = True
    rolls, fx, bits = [], [{"kind": "trap", "trap": trap["id"], "sprung": True,
                            "origin": origin}], [f"{_cap(row['name'])} goes off!"]
    hurt = []
    for v in (victims if eff.get("multiple") else victims[:1]):
        if "attack" in eff:
            mods = [Modifier(int(eff["attack"]), row["name"])]
            atk = engine.dice.d20(mods, label=f"{row['name']} at {v.name}",
                                  visibility="hidden")
            rolls.append(atk)
            ac = v.ac(eff.get("against", "melee"))
            if not dice_mod.d20_succeeds(atk, ac):
                bits.append(f"It misses {v.name}.")
                continue
            times = 1
            if atk.natural == 20:
                again = engine.dice.d20(mods, label="confirming the critical",
                                        visibility="hidden")
                rolls.append(again)
                if dice_mod.d20_succeeds(again, ac):
                    times = int(eff.get("crit", 2))
            total = sum(engine.dice.roll(eff["dice"], label=row["name"],
                                         visibility="hidden").total for _ in range(times))
            hit = engine._apply_damage(v, max(1, total), eff["type"])
        else:
            save = engine.dice.d20(v.save_modifiers("ref", {"against": "trap"}),
                                   label=f"{v.name} Reflex against {row['name']}",
                                   visibility="hidden")
            rolls.append(save)
            if dice_mod.d20_succeeds(save, int(eff["reflex"])):
                bits.append(f"{v.name} jumps clear of the pit.")
                continue
            plan = hazards.plan("falling", {"distance_ft": int(eff["pit_ft"])})
            fall = engine.dice.roll(plan["dice"], label=plan["name"], visibility="hidden")
            rolls.append(fall)
            hit = engine._apply_damage(v, fall.total, plan["type"])
            bits.append(f"{v.name} falls {eff['pit_ft']} feet into the pit.")
        hit["origin"] = origin
        fx.append(hit)
        hurt.append(v)
        bits.append(engine._damage_tell(hit))
    for v in hurt:
        crossed = engine._hp_state_effects(v)
        fx.extend(crossed)
        said = engine._hp_state_tell(crossed)
        if said:
            bits.append(said.strip())
    return rolls, fx, bits


def searched(engine, pc, total: int) -> tuple[list[dict], list[str]]:
    """A Perception result set against what hides here: the way down at its spot, and
    the armed traps of this room and of every room one step on (looked for before walking
    in). Only what was found is told."""
    fx, bits = [], []
    here = engine.here().id
    hit = deeper_at(engine.scene, here)
    if hit is not None and not hit[1]["found"] and total >= int(hit[1]["feature"]["find"]):
        rec, said = _found(engine, *hit)
        fx.append(rec)
        bits.append(said)
    place = places_mod.find(engine.places(), here)
    near = [here, *(getattr(place, "exits", ()) or ())]
    for pid in near:
        d = room(engine.scene, pid)
        trap = (d or {}).get("trap")
        if not trap or not trap["armed"] or trap["found"]:
            continue
        row = traps()[trap["id"]]
        if total >= int(row["perception"]):
            trap["found"] = True
            where = places_mod.find(engine.places(), pid)
            spot = (f"on the door of {where.name}" if trap["on"] == "door"
                    else f"in {where.name}" if pid != here else "here")
            fx.append({"kind": "trap", "trap": trap["id"], "found": True, "at": pid})
            bits.append(f"{pc.name} finds {row['name']} {spot}.")
    return fx, bits


def disarm_target(engine) -> dict | None:
    """The found, armed trap here or one step on that a Disable Device check is for."""
    here = engine.here().id
    place = places_mod.find(engine.places(), here)
    for pid in [here, *(getattr(place, "exits", ()) or ())]:
        trap = (room(engine.scene, pid) or {}).get("trap")
        if trap and trap["armed"] and trap["found"]:
            return trap
    return None


def disarm_lands(engine, actor, trap: dict, margin: int) -> tuple[list[dict], list[str]]:
    """CRB p.94: a difficult device takes 2d4 rounds; success disarms it, failure by 4
    or less does nothing, failure by 5 or more springs it."""
    row = traps()[trap["id"]]
    rounds = engine.dice.roll("2d4", label="how long the work takes", visibility="hidden").total
    engine.scene.advance(0, rounds=rounds)
    if margin >= 0:
        trap["armed"] = False
        return ([{"kind": "trap", "trap": trap["id"], "disarmed": True, "rounds": rounds}],
                [f"{actor.name} disarms {row['name']}."])
    if margin <= -5:
        _rolls, fx, said = spring(engine, trap, [actor])
        return fx, [f"{actor.name} sets {row['name']} off.", *said]
    return [], [f"{row['name'][:1].upper() + row['name'][1:]} is still set."]


def break_door(engine, intent, pc, how: str, partial: dict, *, strict: bool = False):
    """`break_in` at a closed dungeon door or way down: Strength against its break DC, or
    Disable Device against its lock. None when no dungeon door is shut here — or, when
    `strict` (a Disable Device check, not a break-in), when none of them has a lock."""
    from .sheet import IllegalSheet

    here = engine.here().id
    doors = doors_from(engine, here)
    if strict and how == "pick":
        doors = [(far, d) for far, d in doors if d.get("pick")]
    if not doors:
        return None
    want = " ".join(str(intent.params.get("who") or "").lower().split())
    chosen = next(((far, d) for far, d in doors if how != "pick" or d.get("pick")), doors[0])
    for far, door in doors:
        dest = places_mod.find(engine.places(), far)
        if want and (want in door["name"].lower() or want in getattr(dest, "name", "").lower()):
            chosen = (far, door)
    far, door = chosen
    dest = places_mod.find(engine.places(), far)
    if how == "pick" and not door.get("pick"):
        how = "force"
    if how == "pick":
        try:
            mods = list(pc.skill_modifiers("disable device"))
        except IllegalSheet:
            return engine._refuse(intent, f"{pc.name} has no training in picking locks "
                                          f"(Disable Device is trained only). "
                                          f"{_cap(door['name'])} can still be forced.")
        tools = any("thieves' tools" in str(getattr(s, "base", "")).lower()
                    for s in pc.stock.values())
        dc = int(door["pick"]) + (0 if tools else engine.NO_TOOLS)
        label = f"Disable Device — the lock of {door['name']}"
    else:
        mods = list(pc.ability_check_modifiers("str"))
        dc = int(door["force"])
        label = f"Strength check — forcing {door['name']}"
    from .engine import Outcome

    # A touch trap on the door goes off on whoever works it, and the work stops there:
    # the attempt is the trap's, and the next one is the door's.
    trap = (room(engine.scene, far) or {}).get("trap")
    if trap and trap["armed"] and trap["on"] == "door":
        rolls, sprung, said = spring(engine, trap, [pc])
        return Outcome(intent_id=intent.id, op="break_in", effects=sprung, rolls=rolls,
                       tell=" ".join([f"{pc.name} sets to work on {door['name']}.", *said]),
                       because=intent.because)
    fx: list[dict] = []
    bits: list[str] = []
    roll = engine._roll_or_suspend(intent, pc, mods, label, dc, partial)
    engine.scene.advance(0, rounds=1)
    opened = roll.total >= dc
    if opened:
        door["state"] = "open"
        bits.append(f"{_cap(door['name'])} gives: the way to "
                    f"{getattr(dest, 'name', 'beyond')} is open.")
        bits.append(engine.reward_check(pc, "strength" if how == "force" else "disable device",
                                        dc, modifier=roll.modifier_total,
                                        obstacle=f"door:{far}").strip())
    else:
        bits.append(f"{_cap(door['name'])} holds.")
    fx.append({"kind": "dungeon_door", "to": far, "how": how, "opened": opened})
    return Outcome(intent_id=intent.id, op="break_in", effects=fx, rolls=[roll], dc=dc,
                   tell=" ".join(b for b in bits if b), because=intent.because)
