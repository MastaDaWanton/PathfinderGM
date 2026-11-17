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
  corridor, the talking statue) and nothing here may author it — until the concept's
  authored tag could: in a dungeon with a story the second room is "special" and holds
  the tag's ally (`meet_ally`); and a monster room's
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

**The quest** (owner, 2026-11-16): finding the way down opens the player's own quest to
clear it, finished by the boss or by every trial, with the CRB's story award — see the
quest section below `disarm_lands`.

**The story** (owner, 2026-11-16: "A proper dungeon cannot just be random rooms and it must
hold a cohesive story/pattern"): every way down recorded since carries a concept, chosen
on entering the venture and before any room (`concept_for`, the section after
`deeper_at`): who built it and for what, how old, how it fell, who used it after, the one
ruin tag that says who holds it now, why it is still unlooted and what the town makes of
it. The rooms are then the builders' and the tag's (`generate` with a concept), the
climax the tag leader's lair, the "special" room above the tag's ally, the traps the
builders', and each room tells one trace of the history on its first entry; the town's
talk of it is the hook (`spread_rumours`). A dungeon generated before concepts keeps its
rooms, and everything above it: completion still reads `role`, `stock`, `foes` and
`trap.armed`, never a room's name.
"""
from __future__ import annotations

import json
import random
import re
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
        # The concept is chosen here, before any room exists: the owner's "cohesive
        # story/pattern" is what the rooms are then built from (`mint`).
        head["deeper"] = {"kind": kind, "feature": feat, "spot": spot,
                          "found": False, "noticed": False,
                          "concept": concept_for(world, head["id"], kind,
                                                 str(getattr(scene, "location_id", "") or ""))}
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


# --- the story: a concept chosen before any room ----------------------------------------
#
# The owner, 2026-11-16: "A proper dungeon cannot just be random rooms and it must hold a
# cohesive story/pattern." Measured before this: every dungeon's rooms were the same six
# names per kind of ground, shuffled ("the guardroom", "the ossuary", "the sealed vault"),
# and stocked by whatever the bestiary had for the terrain, so a culvert could hold a fire
# beetle, a trap and an ooze in a row with nothing between them.
#
# What the traditions say, and what was taken (searched 2026-11-16):
# - Origin, history, ecology (Hal Johnson, "Anatomy of a dungeon", 2024, which names the
#   three; the brief credited All Dead Generations, which could not be confirmed for this
#   framing): who built it and why, what happened since, what lives there now. Taken as
#   the concept's builders, ruin and users, and the tag.
# - Layered history (Sly Flourish, "Making awesome dungeons": "Every room can tell a
#   story"; what it was built for, what it became, what it serves now; three to nine
#   rooms, five the most common). Taken as one trace per room, the builders' layer nearer
#   the way in, the tag's deeper, the revelation last.
# - Worlds Without Number's ruins (Kevin Crawford): about seven questions — type, age, how
#   it was ruined, why it is unplundered, previous users, what the locals think — and one
#   ruin TAG supplying linked enemies, friends, complications, things and places. Read
#   through secondary sources only (the brief's: a generator site, a podcast read-along, a
#   review; the generator page answered 404 on 2026-11-16, and the book itself was not
#   used). Taken whole: the tag is the cohesion engine, authored in
#   content/dungeons/tags.json. The review's complaint — a rich backstory with no reason to
#   go there — is why the local attitude becomes a rumour in town (`spread_rumours`).
# - Jaquaying (The Alexandrian, "Jaquaying the dungeon"): loops and more than one way
#   through. Kept, and the loop is now always there (five or six rooms).
# - Refused, still: Gygax's room-by-room Appendix A; a scripted plot (the tag is a
#   situation, never a sequence the player must follow); read-aloud backstory (history is
#   shown in traces and the last room's revelation, never told as a block).
#
# Every word is authored (content/dungeons/) or the world's own name (`_world_sources`);
# no model writes any of it. The concept is seeded off the venture's id, so the same way
# down has the same story every time it is asked, before it is found and after.

CONCEPT_VERSION = 1
_STORY: dict | None = None
FAMILY = {"cave": "natural", "mine": "dug"}       # every other kind is built ground


def family(kind: str) -> str:
    return FAMILY.get(kind, "built")


def story() -> dict:
    """content/dungeons/: the builders and their history rows, and the ruin tags."""
    global _STORY
    if _STORY is None:
        from django.conf import settings

        root = Path(settings.BASE_DIR) / "content" / "dungeons"
        built = json.loads((root / "builders.json").read_text(encoding="utf-8"))
        tags = json.loads((root / "tags.json").read_text(encoding="utf-8"))
        _STORY = {k: v for k, v in built.items() if not k.startswith("_")}
        _STORY["tags"] = tags["tags"]
    return _STORY


def _world_sources(world, location_id: str) -> dict:
    """The world's own names a concept may be grounded in: its peoples (the town's own
    continent first), its nations (the town's own first), its factions with their own
    words, and its dated events, the oldest half. Empty for a world that exports none."""
    out: dict = {"people": [], "nation": [], "faction": [], "events": []}
    if world is None:
        return out
    try:
        near = {e.id for e in world.ancestors(location_id)} if location_id else set()
        ents = sorted(world.entities.values(), key=lambda e: e.id)
    except Exception:  # noqa: BLE001 — a world that cannot answer grounds nothing
        return out
    for kind, key in (("PEOPLE", "people"), ("NATION", "nation")):
        rows = [e for e in ents if str(e.kind).upper() == kind and str(e.name or "").strip()]
        mine = [e for e in rows if e.id in near or e.parent_id in near]
        out[key] = [(e.id, e.name) for e in (mine or rows)]
    for f in getattr(world, "factions", None) or []:
        if isinstance(f, dict) and str(f.get("name") or "").strip():
            words = " ".join(str(f.get(k) or "") for k in ("description", "aim", "method",
                                                           "reach")).lower()
            out["faction"].append((str(f.get("id") or f["name"]), str(f["name"]), words))
    dated = sorted((e for e in getattr(world, "chronology", None) or []
                    if getattr(e, "year", None) is not None and str(e.name or "").strip()),
                   key=lambda e: (e.year, e.name))
    out["events"] = [e.name for e in dated[:max(1, len(dated) // 2)]] if dated else []
    return out


def _event_said(name: str) -> str:
    """An event's own name, as the age it gives: "in the days the chronicles call the
    Founding of Pangrella". Named rather than worked into a phrase, because the world's
    event names are not all noun phrases: measured on the playtest save, "Kaelinoran
    Settlements Arrive" came out as "in the days of the Kaelinoran Settlements Arrive"."""
    name = " ".join(str(name).split())
    if name.split(" ", 1)[0] == "The":
        name = "the" + name[3:]
    return f"in the days the chronicles call {name}"


def _ground(spec: dict | None, src: dict, r: random.Random, fallback: str,
            exclude: str = "") -> dict:
    """Who, in the world's own name where the row allows it and the world has one; the
    row's generic `who` otherwise."""
    if spec:
        pool: list[tuple[str, str]] = []
        if spec.get("from") in ("people", "nation"):
            pool = list(src[spec["from"]])
        elif spec.get("from") == "faction":
            words = [w.lower() for w in spec.get("words") or ()]
            pool = [(fid, name) for fid, name, text in src["faction"]
                    if any(w in text for w in words)]
        pool = [p for p in pool if not exclude or p[0] != exclude]
        if pool:
            eid, name = pool[r.randrange(len(pool))]
            return {"who": spec.get("as", "{name}").replace("{name}", name), "entity": eid}
    return {"who": fallback, "entity": ""}


def concept_for(world, head_id: str, kind: str, location_id: str = "") -> dict | None:
    """The dungeon's concept, chosen before any room: what it is (the venture's kind),
    how old, who built it and for what, how it was ruined, who used it after, who holds
    it now (the tag), why it is still unlooted, and what the town makes of it. Seeded off
    the venture, so the same answer every time; None for ground that holds no way down."""
    if kind not in FEATURES:
        return None
    st = story()
    fam = family(kind)
    r = _rng(head_id, "concept")
    src = _world_sources(world, location_id)
    builders = [bid for bid, b in sorted(st["builders"].items())
                if kind in b["kinds"] and fam in b["rooms"]]
    if not builders:
        return None
    bid = builders[r.randrange(len(builders))]
    b = st["builders"][bid]
    tags = [tid for tid, t in sorted(st["tags"].items())
            if fam in t["places"] and ("any" in t["builders"] or bid in t["builders"])]
    if not tags:
        return None
    tid = tags[r.randrange(len(tags))]
    built_by = _ground(b.get("ground"), src, r, b["who"])
    ages = [dict(a) for a in st["ages"]] + [
        {"id": f"event:{name}", "said": _event_said(name)}
        for name in src["events"]]
    age = ages[r.randrange(len(ages))]
    falls = [x for x in st["ruin"] if x["id"] in b.get("ruin", [x["id"]])] or st["ruin"]
    ruin = falls[r.randrange(len(falls))]
    users_row = st["users"][r.randrange(len(st["users"]))]
    # Never the builders again: a second layer is somebody else's.
    used_by = _ground(users_row.get("ground"), src, r, users_row["who"],
                      exclude=built_by["entity"])
    unlooted = st["unlooted"][r.randrange(len(st["unlooted"]))]
    attitude = st["attitudes"][r.randrange(len(st["attitudes"]))]
    return {"v": CONCEPT_VERSION, "kind": kind, "family": fam,
            "builders": {"id": bid, **built_by}, "purpose": b["purpose"],
            "age": {"id": age["id"], "said": age["said"]},
            "ruined": {"id": ruin["id"], "said": ruin["said"]},
            "users": {"id": users_row["id"], **used_by},
            "inhabitants": st["tags"][tid]["who"],
            "unlooted": unlooted["id"], "attitude": attitude["id"], "tag": tid}


def _row(rows: list[dict], rid: str) -> dict:
    return next((x for x in rows if x["id"] == rid), rows[0])


def slots_of(concept: dict, *, town: str = "", where: str = "") -> dict:
    """The words a concept's sentences are filled with: each one authored, or the
    world's own name."""
    tag = story()["tags"][concept["tag"]]
    return {"builders": concept["builders"]["who"], "users": concept["users"]["who"],
            "town": town or "the town", "where": where or "the place",
            "age": concept["age"]["said"], "leader": tag["leader"]["title"],
            "lair": tag["places"][concept["family"]][-1][0],
            "ally": f"the {tag['ally']['as']}"}


_SLOT = re.compile(r"\{(\w+)\}")


def fill(text: str, slots: dict) -> str:
    """A sentence with its slots filled and its first letter capitalised. An unknown slot
    is left as written, so a test finds it."""
    return _cap(_SLOT.sub(lambda m: str(slots.get(m.group(1), m.group(0))), str(text or "")))


def room_names() -> frozenset[str]:
    """Every name a dungeon room can be given, without "the": the stock rooms (`ROOMS`)
    and the story's builders' and tags' (content/dungeons/). A closed vocabulary, as
    `places.generated_names` is."""
    st = story()
    rows = [r for fam in ROOMS.values() for r in fam]
    for kind in ("builders", "tags"):
        for spec in (st.get(kind) or {}).values():
            for fam in ((spec.get("rooms") or spec.get("places") or {}).values()):
                rows += [tuple(x) for x in fam]
    return frozenset(str(r[0]).removeprefix("the ") for r in rows)


def _concept_rooms(concept: dict, n: int) -> tuple[list[tuple[str, str]], list[str]]:
    """(name, about) for each of `n` rooms, and the layer each belongs to: the builders'
    rooms from the way in, in their own order (the gatehouse before the armoury behind
    it), then the tag's places, the lair last."""
    st = story()
    fam = concept["family"]
    own = [tuple(x) for x in st["builders"][concept["builders"]["id"]]["rooms"][fam]]
    tag = [tuple(x) for x in st["tags"][concept["tag"]]["places"][fam]]
    middle = n - 2
    nb, nt = (middle + 1) // 2, middle // 2
    picked = [own[0]] + own[1:1 + nb] + tag[:-1][:nt] + [tag[-1]]
    layer = ["builders"] * (1 + nb) + ["tag"] * nt + ["lair"]
    # Two rooms of one name would be one place id.
    seen: set[str] = set()
    for i, (name, about) in enumerate(picked):
        if name in seen:
            picked[i] = (f"{name} beyond", about)
        seen.add(picked[i][0])
    return picked, layer


def _traces(concept: dict, slots: dict, layer: list[str]) -> list[str]:
    """One trace per room, filled: the builders' rooms show the builders, then how the
    place fell, then who used it after; the tag's places show what holds it now; the
    lair holds the revelation."""
    st = story()
    b = st["builders"][concept["builders"]["id"]]
    tag = st["tags"][concept["tag"]]
    history = [b["traces"][0], _row(st["ruin"], concept["ruined"]["id"])["trace"],
               _row(st["users"], concept["users"]["id"])["trace"], *b["traces"][1:]]
    now = list(tag["traces"])
    out = []
    for kind in layer:
        if kind == "lair":
            out.append(fill(tag["revelation"], slots))
        elif kind == "builders" or not now:
            out.append(fill(history.pop(0), slots) if history else "")
        else:
            out.append(fill(now.pop(0), slots))
    return out


def rumour_line(concept: dict, slots: dict) -> str:
    """What the town says of it: its attitude, and the tag's rumour."""
    st = story()
    said = fill(_row(st["attitudes"], concept["attitude"])["said"], slots)
    heard = fill(st["tags"][concept["tag"]]["rumour"], slots)
    return f"{said}: {heard[:1].lower()}{heard[1:]}."


def concept_of(head: dict) -> dict | None:
    """The concept a way down's dungeon is built from, or None for one recorded before
    concepts existed whose rooms are already made (they are kept as they were)."""
    c = (head.get("deeper") or {}).get("concept")
    return c if isinstance(c, dict) and c.get("tag") in story()["tags"] else None


def generate(head_id: str, kind: str, spot_id: str, terrain: str, feature: dict,
             apl: int, concept: dict | None = None, slots: dict | None = None) -> list[dict]:
    """The rooms behind the way down, as founded records, seeded off the venture.

    With a `concept` (`concept_for`) the rooms are the concept's: the builders' rooms
    nearer the way in and the tag's places deeper, the lair last, five or six of them so
    the loop is always there; every room carries its one trace, the second room the ally,
    the traps the builders'. Without one, the generic per-kind rooms of 0.3.7 — the shape
    an older save's dungeon was generated with, kept so a test or a caller with no
    concept gets what it always got."""
    from . import treasure

    r = _rng(head_id, "rooms")
    if concept is not None:
        n = 5 + r.randint(0, 1)              # 5..6 rooms: the arc, and always the loop
        picked, layer = _concept_rooms(concept, n)
    else:
        names = list(ROOMS[kind])
        climax = names.pop()
        n = 4 + r.randint(0, 2)              # 4..6 rooms
        r.shuffle(names)
        picked = names[:n - 1] + [climax]
        layer = [""] * n
    centre = treasure._BY_CR[max(0, min(20, int(apl)))]
    trap_rows = [k for k, v in traps().items() if v["cr"] <= max(1, int(apl) + 1)]
    if concept is not None:
        # The builders' own traps (a tomb seals, a drain's floor gives way), where any of
        # them is in the party's reach; the whole list where none is.
        own = [k for k in story()["builders"][concept["builders"]["id"]]["traps"]
               if k in trap_rows]
        trap_rows = own or trap_rows
    traces = _traces(concept, slots or {}, layer) if concept is not None else [""] * n

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
        elif concept is not None and i == 1:
            # B/X's "special" room, read as empty while nothing could author it; the
            # concept's ally is what authors it now, in the Five Room Dungeon's second
            # room (the role-play challenge).
            stock = "special"
        else:
            face = r.randint(1, 6)
            stock = "monster" if face in (3, 4) else "trap" if face == 6 else "empty"
        d = {"of": head_id, "role": "climax" if last else "entrance" if i == 0 else "room",
             "stock": stock, "stocked": False, "cache_gp": 0, "trap": None}
        if concept is not None:
            d["trace"] = traces[i]
            d["layer"] = layer[i]
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
            # A builder whose only trap in reach works on a door, in a doorless room: the
            # book's other traps in reach, rather than none.
            pool = pool or [k for k, v in traps().items() if v["trigger"] != "touch"
                            and v["cr"] <= max(1, int(apl) + 1)]
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


def shut_door_named(scene, words) -> str:
    """The name of the place beyond a closed door out of here that `words` name — by that
    place's name ("the door to the beast's pool") or by the door's own last word ("the
    stuck door") — or "". Names the engine holds, matched against the player's words."""
    said = " ".join(str(words or "").lower().split())
    here = str(getattr(scene, "at", "") or "")
    founded = getattr(scene, "founded", None) or []
    if not said or not here or not founded:
        return ""
    up = (_rec(scene, here) or {}).get("parent")
    near = [r.get("id") for r in founded if r.get("parent") == here] + [up]
    for other in near:
        door = door_between(scene, here, other) if other else None
        if door is None:
            continue
        name = str((_rec(scene, other) or {}).get("name") or "").lower()
        noun = (str(door.get("name") or "").lower().split() or [""])[-1]
        if (name and name in said) or (noun and noun in said.split()):
            return name or noun
    return ""


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


# --- who holds it: a concept's rooms stocked from its tag --------------------------------
#
# The enemies, the leader and the ally are the tag's (content/dungeons/tags.json), drawn
# through the encounter budget at the party's APL (`encounter_budget.choose`, the owner's
# whole-group ruling of 2026-11-13), so "monsters that fit the context" (Sly Flourish) and
# the budget are both kept. The leader is the climax's one creature, priced as a guard or
# a lair is ("guarded": challenging or hard sometimes); where the d100's difficulty buys
# none of the tag's leaders the hard budget is asked before giving up, never an epic one.

# Mindless or alien things that go for the living on sight, beside the beasts
# `gathering.AGGRESSIVE` already names: a skeleton, a guardian, a thing from below.
_ON_SIGHT = frozenset({"undead", "construct", "aberration", "outsider"})


def _spec_rows(spec: dict) -> list[dict]:
    """The bestiary rows a tag's spec names: every rung of each codex person's ladder
    (the bandit at levels 1, 3 and 6), and each creature by its exact id."""
    from . import bestiary
    from . import npcs

    book = bestiary.imported()
    index = npcs.index()
    rows: list[dict] = []
    for base in spec.get("people") or ():
        for _cr, bid in (index.get(base) or {}).get("ladder", ()):
            if bid in book:
                rows.append(book[bid])
    for cid in spec.get("creatures") or ():
        if cid in book:
            rows.append(book[cid])
    return [r for r in rows if r.get("cr_value") is not None]


def _people_ids(spec: dict) -> set[str]:
    from . import npcs

    index = npcs.index()
    return {bid for base in spec.get("people") or ()
            for _cr, bid in (index.get(base) or {}).get("ladder", ())}


def _draw(engine, rows: list[dict], *, kind: str, most: int, hard: bool = False):
    """The budget's draw from `rows`: the d100's difficulty, or the hard end of `kind`
    when `hard` (a climax that would otherwise stand empty). None when nothing fits."""
    from . import encounter_budget as eb
    from . import gathering

    if not rows:
        return None
    roll = 100 if hard else engine.dice.roll("1d100", label="how hard it is",
                                             visibility="hidden").total
    return eb.choose(rows, eb.party_apl(engine.scene), roll,
                     lambda n: gathering.pick_index(engine.dice, n, "who holds it"),
                     kind=kind, most=most)


def stock_room(engine, place, d: dict, concept: dict) -> tuple[list[dict], str]:
    """A concept room's inhabitants: the tag's leader in the climax, the tag's enemies in
    any other monster room, brought in by the one door (`Engine._inhabit`). People who
    hold the place are wary of strangers rather than attacking on sight, unless the tag
    says they attack; beasts and the mindless dead attack. (effects, tell)."""
    from . import attitude as attitude_mod
    from . import encounter_budget as eb
    from . import gathering
    from . import words as english

    tag = story()["tags"][concept["tag"]]
    climax = d["role"] == "climax"
    if climax:
        lead = _spec_rows(tag["leader"])
        got = (_draw(engine, lead, kind="guarded", most=1)
               or _draw(engine, lead, kind="guarded", most=1, hard=True)
               or _draw(engine, _spec_rows(tag["enemies"]), kind="guarded", most=1, hard=True))
        title = tag["leader"]["title"]
    else:
        got = _draw(engine, _spec_rows(tag["enemies"]), kind="wandering", most=eb.MOST)
        title = None
    if got is None:
        return [], ""
    person = got.row.get("id") in (_people_ids(tag["leader"]) | _people_ids(tag["enemies"]))
    on_sight = (bool(tag.get("hostile")) if person
                else got.row.get("creature_type") in (gathering.AGGRESSIVE | _ON_SIGHT))
    # A creature goes by its kind; the title is told once, in the line below. Playtest
    # 2026-11-17 #46/#47: named "the beast they kept", the dog's tells read "the beast
    # they kept's attack", and "I stab at the dog" found nobody once it was down. A
    # person's title is a noun phrase ("the band's captain") and stays their name.
    fx, _said = engine._inhabit(place, guarding=climax, row=got.row, count=got.count,
                                name=title if person else None, hostile=on_sight)
    refs = [r for e in fx for r in (e.get("refs") or [e.get("ref")]) if r]
    if person and not on_sight:
        for r in refs:
            a = engine.scene.people.get(r)
            if a is not None:
                engine._set_attitude(a, attitude_mod.WARY, None, f"rule:dungeon/{d['of']}")
    from .openings import creature_noun

    noun = creature_noun(got.row.get("name", "")).lower()
    calm = ", wary of strangers." if person else ", further in."
    if title:
        said = (f"{_cap(title)}, {english.a(noun)}, holds this place"
                + (", and has seen you." if on_sight else
                   ", and is watching you." if person else calm))
    elif got.count > 1:
        count = {2: "Two", 3: "Three"}.get(got.count, str(got.count))
        said = (f"{count} {english.plural(noun)} are here"
                + (", and have seen you." if on_sight else calm))
    else:
        said = f"{_cap(english.a(noun))} is here" + (", and has seen you." if on_sight else calm)
    for e in fx:
        e["dungeon"] = concept["tag"]
    return fx, said


def meet_ally(engine, place, concept: dict, head: dict) -> tuple[list[dict], str]:
    """The tag's ally or witness, a real person in the second room (the owner's ruling
    of 2026-10-01: anyone the narration shows is a full actor, saved): the codex person
    at the bottom of their ladder, kept near, friendly to whoever has come down, and
    holding what they know as their own note, so a conversation has it. (effects, tell)"""
    from . import attitude as attitude_mod
    from . import npcs

    tag = story()["tags"][concept["tag"]]
    ally = tag["ally"]
    ladder = (npcs.index().get(ally["people"]) or {}).get("ladder") or ()
    if not ladder:
        return [], ""
    slots = slots_of(concept, town=_town(engine), where=_where(engine, head))
    born = engine._bring_in(ladder[0][1], count=1, name=f"the {ally['as']}")
    ref = born[0]["ref"]
    a = engine.scene.people.get(ref)
    if a is None:
        return [], ""
    engine.scene.zones[ref] = "near"
    # The complication is theirs to know too: playtest 2026-11-16 #58, the smuggler "will not
    # leave without" the cargo, and with only the notes held he told the player it was gone.
    # What a person knows is their notes (`planned.known_to`).
    a.notes = " ".join(x for x in (fill(ally["notes"], slots),
                                   fill(tag.get("complication") or "", slots)) if x)
    engine._set_attitude(a, attitude_mod.CONFIDES_A_HINT, None, f"rule:dungeon/{head['id']}")
    said = f"{_cap(a.name)} is here, alive. {a.notes}"
    return ([{"kind": "dungeon_ally", "ref": ref, "name": a.name, "at": place.id,
              "dungeon": concept["tag"]}], said)


def _town(engine) -> str:
    """The settlement's own name, from the world."""
    w = getattr(engine, "world", None)
    e = w.get(engine.scene.location_id) if w is not None else None
    return str(getattr(e, "name", "") or "")


# --- the hook: what the town says of it -------------------------------------------------
#
# The WWN review's complaint was a rich backstory with no reason to go there. The local
# attitude is the reason: it reaches the player as talk in town, before the way down is
# found, through the one store of matters (rules/cards.py) as a situation card tagged
# `cards.TAG_RUMOUR`. A rumour is ambient and qualifies to be pulled only until the prose
# has carried it once (`cards.salience`), the Alexandrian's "in the general conversation"
# (Rumor tables, part 2) — never the fifty-beats-of-faction-politics the ambient rule
# exists against. One per settlement, the first of its ways down in a seeded order.

RUMOURS_PER_TOWN = 1
_HOLY = ("temple", "graveyard", "shrine", "chapel", "cemetery", "tomb")


def _parents_for(places, kind: str, town_of: str) -> list:
    """The places of this settlement a `kind` of venture is gone into from, as play goes
    into them: ground under the town (the sewers, the cellars, a crypt off a holy place)
    from its rooms, ground away from it (a cave, the ruins) from its edge."""
    under = int(places_mod.VENTURES[kind].get("hours") or 0) == 0
    out = []
    for p in places:
        if places_mod.location_of(p.id) != town_of or p.origin in ("venture", ORIGIN):
            continue
        where = places_mod.setting_of(p.id)
        # A room on the ground: nobody goes down to the sewers from an upper floor.
        if under and (where != "in" or places_mod.storey_of(p.id) != 0):
            continue
        if not under and where != "outside":
            continue
        if kind == "crypt" and not any(w in str(p.name).lower() for w in _HOLY):
            continue
        out.append(p)
    return out


def spread_rumours(engine) -> None:
    """Once a settlement: the talk of its ways down still unfound, opened as cards. No
    tell; the card reaches the prose the way any matter does."""
    from . import cards as cards_mod

    scene = engine.scene
    town_of = places_mod.location_of(str(getattr(scene, "at", "") or ""))
    key = f"rumours:{town_of}"
    if not town_of or key in scene.said or engine.world is None:
        return
    from . import ships

    if ships.vessel_of(town_of):
        # A ship at the quay is no settlement: her rigging opened onto "the sewers off the
        # rigging" (playtest 2026-11-16 #90). The town's talk is spread ashore.
        return
    if places_mod.setting_of(str(scene.at or "")) not in ("in", "outside"):
        return
    town = _town(engine)
    if not town:
        return
    scene.said[key] = True
    places = list(engine.places())
    found = []
    for kind in sorted(FEATURES):
        for parent in sorted(_parents_for(places, kind, town_of), key=lambda p: p.id):
            head = places_mod.venture_set(parent, kind)[0]
            rec = _rec(scene, head.id)
            if rec is not None and (rec.get("deeper") or {}).get("found"):
                continue
            if rolled(head.id) > chance(engine.world, head.id, parent.id):
                continue
            found.append((head, parent, kind))
    _rng(town_of, "rumours").shuffle(found)
    for head, parent, kind in found[:RUMOURS_PER_TOWN]:
        concept = concept_for(engine.world, head.id, kind, scene.location_id)
        if concept is None:
            continue
        where = f"{head.name} off {parent.name}"
        line = rumour_line(concept, slots_of(concept, town=town, where=where))
        cid = f"rumour-{places_mod._seed(head.id)}"
        if cards_mod.find(scene, cid) is not None:
            continue
        cards_mod.open_card(scene, cards_mod.Card(
            id=cid, title=f"What {town} says of {where}", facts=[line],
            keys=cards_mod.keys_from(where, line), tags=(cards_mod.TAG_RUMOUR,),
            place=head.id, origin=f"rule:rumour/{head.id}", clock_max=6))


# --- the engine's doors --------------------------------------------------------------------

def mint(engine, head: dict, deeper: dict) -> list[str]:
    """The rooms come into being: found, so now real. The names said."""
    from . import encounter_budget

    if any((p.get("dungeon") or {}).get("of") == head["id"] for p in engine.scene.founded):
        return []
    spot = places_mod.find(engine.places(), deeper["spot"])
    terrain = getattr(spot, "terrain", "") or head.get("terrain", "")
    concept = concept_of(head)
    if concept is None and "concept" not in deeper:
        # A way down recorded before concepts, its rooms not yet made: it gets one now.
        # One whose rooms were made already never comes here (the guard above).
        concept = deeper["concept"] = concept_for(engine.world, head["id"], deeper["kind"],
                                                  engine.scene.location_id)
    slots = (slots_of(concept, town=_town(engine), where=_where(engine, head))
             if concept else None)
    made = generate(head["id"], deeper["kind"], deeper["spot"], terrain, deeper["feature"],
                    encounter_budget.party_apl(engine.scene), concept=concept, slots=slots)
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
    # The owner, 2026-11-16: finding the way down gives the quest (see `open_quest`).
    q_fx, q_said = open_quest(engine, head)
    return ({"kind": "way_down_found", "feature": feat["name"], "at": deeper["spot"],
             "leads_to": first.get("id", ""),
             **({"quest": q_fx[0]["id"]} if q_fx else {})},
            f"Here: {feat['about']} — {feat['name']}.{tail}" + (f" {q_said}" if q_said else ""))


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
    if pc is not None and engine.scene.sees_nothing(pc):
        # No light and no darkvision: what the room looks like is not the player's to
        # be told (playtest 2026-11-16 #57). Its trace waits for a lit visit.
        bits.append(f"{_cap(place.name)} is pitch dark: nothing of it can be seen, only "
                    f"heard, smelt and felt.")
        d.setdefault("traced", False)
    else:
        bits.append(f"{_cap(place.name)}: {place.about}.")
        # A room saved before `traced` was kept told its trace when it was stocked.
        if not d.get("traced", d["stocked"]) and d.get("trace"):
            # The room's one trace of its history, told on the first SEEN entry so the
            # narrator has it and invents none (the owner's "cohesive story", shown and
            # not told).
            bits.append(d["trace"])
            d["traced"] = True
    trap = d.get("trap")
    if trap and trap["armed"] and trap["on"] == "room":
        row = traps()[trap["id"]]
        if trap["found"]:
            bits.append(f"The party steps round {row['name']} they found.")
        else:
            rolls, sprung, said = spring(engine, trap, _party(engine))
            fx.extend(sprung)
            bits.extend(said)
    if d["stocked"]:
        # Back in a room already stocked: whoever lives here is still here, and the
        # stocking's own line was told on the first entry only. Playtest 2026-11-17 #27:
        # back in the turnkey's room by torchlight, the dire rat that had bitten her there
        # stood in it, and the tell (so the beat) never said so.
        seen = pc is None or not engine.scene.sees_nothing(pc)
        for ref in d.get("foes") or ():
            a = engine.scene.actors.get(ref)
            if (seen and a is not None and getattr(a, "at", "") == place.id
                    and not a.has_state("state.hidden")
                    and not a.has_state("state.down.dead")):
                from .names import definite

                bits.append(f"{_cap(definite(a.name))} {'lies' if a.is_down else 'is'} "
                            f"here.")
    if not d["stocked"]:
        d["stocked"] = True
        head = _rec(engine.scene, d.get("of", "")) or {}
        concept = concept_of(head) if d.get("layer") else None
        if d["stock"] == "monster":
            if concept is not None:
                got, said = stock_room(engine, place, d, concept)
            else:
                got, said = engine._inhabit(place, guarding=d["role"] == "climax")
            # Who was stocked here, so the quest can ask whether they are dealt with.
            d["foes"] = [r for e in got for r in (e.get("refs") or [e.get("ref")]) if r]
            fx.extend(got)
            if said:
                bits.append(said)
        if d["stock"] == "special" and concept is not None:
            got, said = meet_ally(engine, place, concept, head)
            fx.extend(got)
            if said:
                bits.append(said)
        if d["cache_gp"]:
            name = "an iron-bound chest" if d["role"] == "climax" else "a small strongbox"
            dressed = ""
            if concept is not None:
                st = story()
                if d["role"] == "climax":
                    reward = st["tags"][concept["tag"]]["reward"]
                    name, dressed = reward["container"], reward["said"]
                else:
                    name = st["builders"][concept["builders"]["id"]]["cache"]
            engine.scene.props.append({
                "name": name, "owner": "", "from_": "", "state": "intact",
                "turn": int(engine.scene.clock_minutes), "at": place.id,
                "contents": {"purse": {"gp": int(d["cache_gp"])}, "goods": {}},
                "origin": f"rule:treasure/{d['of']}"})
            fx.append({"kind": "treasure_placed", "at": place.id, "container": name})
            # Dressed as the concept's goods, and still the CRB's value in coin: what it
            # holds is the purse the ledger carries, never goods nobody priced.
            bits.append(f"{_cap(name)} is here, and in it {dressed}." if dressed
                        else f"There is {name} here.")
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
        elif "drop" in eff:
            # A falling weight (the portcullis): Reflex avoids it, else its dice.
            save = engine.dice.d20(v.save_modifiers("ref", {"against": "trap"}),
                                   label=f"{v.name} Reflex against {row['name']}",
                                   visibility="hidden")
            rolls.append(save)
            if dice_mod.d20_succeeds(save, int(eff["reflex"])):
                bits.append(f"{v.name} throws themself clear of it.")
                continue
            drop = engine.dice.roll(eff["drop"], label=row["name"], visibility="hidden")
            rolls.append(drop)
            hit = engine._apply_damage(v, max(1, drop.total), eff["type"])
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
            # At the bottom until they climb out (`climb_out`), through the one applicator.
            # Playtest 2026-11-17 #38: the fall did its damage and nothing held her down
            # there, so "I climb up out of the pit" had nothing to leave.
            climb = int(eff.get("climb") or PIT_CLIMB_DC)
            v.add_condition(IN_A_PIT, source=origin, origin=origin,
                            payload={"climb": climb, "pit_ft": int(eff["pit_ft"]),
                                     "at": getattr(v, "at", "")})
            fx.append({"ref": v.ref, "kind": "condition", "condition": IN_A_PIT,
                       "origin": origin})
            bits.append(f"{v.name} falls {eff['pit_ft']} feet into the pit, and is at the "
                        f"bottom of it: climbing out is a DC {climb} Climb check.")
        hit["origin"] = origin
        fx.append(hit)
        hurt.append(v)
        bits.append(engine._damage_tell(hit))
    if eff.get("seals"):
        # A sealing trap: what fell now shuts the way back, until it is lifted at its
        # printed Strength DC (the falling portcullis: "a DC 25 Strength check can lift").
        rec = next((p for p in engine.scene.founded
                    if (p.get("dungeon") or {}).get("trap") is trap), None)
        if rec is not None:
            rec["dungeon"]["door"] = {"name": f"the fallen {row['name'].split()[-1]}",
                                      "state": "stuck", "force": int(eff["seals"])}
            fx.append({"kind": "dungeon_door", "to": rec["id"], "sealed": True,
                       "origin": origin})
            bits.append(f"It has come down across the way back: "
                        f"{shut_line(engine.scene, rec.get('parent', ''), rec['id'])}")
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


# --- the quest: the way down found, the dungeon to clear -----------------------------------
#
# The owner, 2026-11-16: "i would like finding the way down to give you a quest to complete
# it and mark the location for returning. and completing it should be defeating the Boss at
# the end or completing all trials."
#
# What the traditions do, and what was taken:
# - Skyrim: a location is "Cleared" when every actor with the Boss LocationRefType is dead
#   (Creation Kit wiki, ck.uesp.net/wiki/IsCleared_-_Location), not when every enemy is;
#   UESP's Delver page notes a cleared dungeon can still hold living enemies. Taken as (a):
#   the climax room's creatures dealt with.
# - Diablo II's Den of Evil finishes when every monster in the cave is dead (diablowiki,
#   "Den of Evil"). Taken as (b): every room seen through. A trap counts too here, because
#   the B/X stocking makes a trap room a room's whole challenge.
# - Daggerfall: a quest's dungeon is revealed on the travel map when the quest names it
#   (UESP "Daggerfall:Locations"), but its automap reset on leaving ("all map information is
#   lost"). Refused, as NetHack refused map amnesia (play/places_found.py): the rooms are
#   founded places and `Scene.been` only grows, so the way back stays on the chart.
# The quest is the player's own from the first moment (BG3's journal starts a quest on the
# personal, the find itself), so finishing it is their part (`cards.took_part`), and the
# CRB's story award pays: "Feel free to award Story Awards when players conclude a major
# storyline ... worth double the amount of experience points for a CR equal to the APL"
# (CRB p.397, "Awarding Experience"; `xp.STORY["new"]`). Once: the head's `cleared` and the
# card's closing both say so. No model writes any of it: the words are place names in code.

QUEST_ORIGIN = "rule:dungeon"
QUEST_OBJECTIVE = ("Defeat whatever holds the deepest room, or see every room below through: "
                   "every room entered, every creature dealt with, every trap disarmed or sprung")


def quest_origin(head_id: str) -> str:
    return f"{QUEST_ORIGIN}/{head_id}"


def is_quest(card) -> bool:
    """A dungeon's quest, whose one objective only the engine ticks (`settle`)."""
    return str(getattr(card, "origin", "") or "").startswith(QUEST_ORIGIN + "/")


def _name(engine, place_id: str) -> str:
    p = places_mod.find(engine.places(), place_id) if place_id else None
    return str(getattr(p, "name", "") or "")


def _where(engine, head: dict) -> str:
    """"the sewers off the gardens": the venture and the place it was ventured from."""
    town = _name(engine, head.get("parent", ""))
    return str(head.get("name") or "the way down") + (f" off {town}" if town else "")


def quest_words(engine, head: dict) -> tuple[str, str]:
    """(title, journal entry) of a dungeon's quest: the one place its words are made, so a
    generator that knows a dungeon's origin can name it here."""
    deeper = head.get("deeper") or {}
    spot = _name(engine, deeper.get("spot", ""))
    title = _cap(f"Clear what lies below {_where(engine, head)}")[:80]
    concept = concept_of(head)
    if concept is not None:
        # The concept's own quest, in words that name the place and not the answer
        # ("Find who works the old run below the sewers off the gardens").
        quest = story()["tags"][concept["tag"]]["quest"]
        for where in (_where(engine, head), str(head.get("name") or "the way down")):
            said = fill(quest, slots_of(concept, town=_town(engine), where=where))
            if len(said) <= 80:
                title = said
                break
    fact = (f"The way down is {(deeper.get('feature') or {}).get('name', 'a way down')}"
            + (f" in {spot}" if spot else "") + f", in {_where(engine, head)}.")
    return title, fact


def _rooms(scene, head_id: str) -> list[dict]:
    return [p for p in scene.founded if (p.get("dungeon") or {}).get("of") == head_id]


def _dealt_with(engine, ref: str, room_id: str) -> bool:
    """Dead, fled, yielded or out of the fight: gone from the campaign, down, yielded, or
    no longer in the room and on no side of a fight (run off, not chasing the party)."""
    from . import morale

    a = engine.scene.people.get(ref)
    if a is None or a.is_down or morale.yielded(a):
        return True
    fighting = any(ref in refs for refs in (engine.scene.sides or {}).values())
    return str(getattr(a, "at", "") or "") != room_id and not fighting


def _foes(engine, rec: dict) -> list[str]:
    """Who was stocked in a room; for a room stocked before that was recorded, whoever not
    of the party stands in it now."""
    from . import states

    d = rec["dungeon"]
    if "foes" in d:
        return list(d["foes"])
    return [r for r, a in engine.scene.people.items()
            if str(getattr(a, "at", "") or "") == rec["id"] and not a.is_pc
            and not a.has_state(states.TRAVELS_WITH_YOU)]


def _seen_through(engine, rec: dict) -> bool:
    d = rec["dungeon"]
    return bool(d.get("stocked")) and all(_dealt_with(engine, r, rec["id"])
                                          for r in _foes(engine, rec))


def completion(engine, head_id: str) -> str:
    """"boss" when the climax room held creatures and they are dealt with, "trials" when
    every room is entered, its creatures dealt with and its trap disarmed or sprung; else "".

    A climax the bestiary stocked with nobody has no boss to defeat, so only the trials
    finish that dungeon (an owner call): entering an empty last room is not a victory."""
    rooms = _rooms(engine.scene, head_id)
    if not rooms:
        return ""
    climax = next((r for r in rooms if r["dungeon"].get("role") == "climax"), None)
    if climax is not None and _foes(engine, climax) and _seen_through(engine, climax):
        return "boss"
    if all(_seen_through(engine, r) and not (r["dungeon"].get("trap") or {}).get("armed")
           for r in rooms):
        return "trials"
    return ""


def quest_of(scene, head_id: str):
    from . import cards as cards_mod

    origin = quest_origin(head_id)
    return next((c for c in cards_mod.quests(scene) if c.origin == origin), None)


def open_quest(engine, head: dict) -> tuple[list[dict], str]:
    """The player's own quest for this way down, through the one quest store, and its
    tell. (effects, tell); nothing when it is open already."""
    from . import cards as cards_mod

    if quest_of(engine.scene, head["id"]) is not None:
        return [], ""
    pc = engine.scene.pc()
    origin = quest_origin(head["id"])
    title, fact = quest_words(engine, head)
    card = cards_mod.open_quest(engine.scene, title=title, objectives=[QUEST_OBJECTIVE],
                                facts=[fact], place=str(head["deeper"].get("spot") or ""),
                                origin=origin, known="taken")
    return ([{"kind": "quest", "id": card.id, "title": card.title,
              "objectives": [QUEST_OBJECTIVE], "origin": origin}],
            f"{pc.name if pc else 'The party'} takes it on: {card.title}. "
            f"(1) {QUEST_OBJECTIVE}. {fact} The way down is marked on the chart, to come "
            f"back to.")


def settle(engine) -> list:
    """Once a batch: every found way down has its quest (opened the batch it is found, or
    the first batch after an older save loads), and an open one is finished the moment the
    dungeon is cleared — the quest closed, the story award paid once, a tell each."""
    from . import cards as cards_mod
    from .engine import Outcome

    scene = engine.scene
    pc = scene.pc()
    if pc is None:
        return []
    out = []
    # The talk of this settlement's ways down, before any is found (the hook).
    spread_rumours(engine)
    for head in list(scene.founded):
        deeper = head.get("deeper")
        if not deeper or not deeper.get("found"):
            continue
        # Found: the talk of it is no longer talk.
        rumour = cards_mod.find(scene, f"rumour-{places_mod._seed(head['id'])}")
        if rumour is not None and rumour.live:
            cards_mod.resolve(scene, rumour.id, "found")
        origin = quest_origin(head["id"])
        card = quest_of(scene, head["id"])
        if card is None:
            # A save from before the quest existed: the way found, no quest on it.
            fx, said = open_quest(engine, head)
            card = quest_of(scene, head["id"])
            out.append(Outcome(intent_id="", op="quest", effects=fx, tell=said,
                               because="the way down was found"))
        if not card.live or deeper.get("cleared"):
            continue
        how = completion(engine, head["id"])
        if not how:
            continue
        deeper["cleared"] = how
        said = ("What held the deepest room is dealt with." if how == "boss"
                else "Every room below has been seen through.")
        cards_mod.objective_done(scene, card.id, 0, note=said)
        line = engine.award_story("new", card.title).strip()
        out.append(Outcome(
            intent_id="", op="quest_step",
            effects=[{"kind": "quest_step", "id": card.id, "objective": 1, "finished": True,
                      "cleared": how, "origin": origin}],
            tell=f"{said} {card.title} is finished." + (f" {line}" if line else "")
                 + " The way down stays on the chart.",
            because="the dungeon is cleared"))
    return out


# At the bottom of a pit a trap dropped them into (`spring`): a condition, so it is a tag
# (`states.TAGS`) on an `ActiveEffect` whose payload carries the trap's Climb DC. The
# printed pit blocks (CRB p.420) give no DC out; the Climb table does (CRB p.90): DC 15 "a
# surface with adequate handholds and footholds", the default for a row that names none.
IN_A_PIT = "in a pit"
PIT_CLIMB_DC = 15


def in_pit(actor) -> dict | None:
    """The pit effect's payload when `actor` is at the bottom of one, else None."""
    if actor is None or not actor.has_state("state.position.pit"):
        return None
    eff = next((e for e in actor.effects if e.key == IN_A_PIT), None)
    return dict(eff.payload or {}) if eff is not None else {"climb": PIT_CLIMB_DC}


def climb_out(engine, intent, actor, partial: dict):
    """A Climb check out of the pit, at the pit's DC whatever the plan wrote (playtest
    2026-11-17 #40: the plan's "average (DC 10)"), or None when they are in no pit.

    Climb, CRB p.90: success advances "at one-quarter your normal speed"; "a failed check
    by 4 or less means you make no progress, and one that fails by 5 or more means you
    fall from whatever height you have already attained" — from the bottom that is under
    10 ft, so no falling damage (1d6 per 10 ft, CRB p.443). The time is the climb's: the
    pit's depth at a quarter speed, two move actions a round."""
    from .engine import Outcome

    pit = in_pit(actor)
    if pit is None:
        return None
    dc = int(pit.get("climb") or PIT_CLIMB_DC)
    mods = list(actor.skill_modifiers("climb"))
    roll = engine._roll_or_suspend(intent, actor, mods, "Climb check — out of the pit", dc,
                                   partial)
    made = roll.total >= dc
    engine._judge(roll, made)
    if made:
        per_round = max(5, int(getattr(actor, "speed", 30) or 30) // 2)
        engine.scene.advance(0, rounds=max(1, -(-int(pit.get("pit_ft") or 10) // per_round)))
        actor.remove_effects(match=lambda e: e.key == IN_A_PIT)
        tell = f"{actor.name} climbs up out of the pit ({roll.total} against DC {dc})."
    else:
        engine.scene.advance(0, rounds=1)
        tell = (f"{actor.name} " + ("slips back to the bottom of the pit"
                                    if dc - roll.total >= 5 else "makes no headway up the pit wall")
                + f" ({roll.total} against DC {dc}).")
    return Outcome(intent_id=intent.id, op="check", rolls=[roll], dc=dc,
                   verdict="success" if made else "failure",
                   effects=[{"ref": actor.ref, "kind": "climb_out", "made": made, "dc": dc}],
                   tell=tell, because=intent.because)


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
        # No XP: a door has break and lock DCs, not a CR (CRB p.397 pays for CR'd
        # challenges; doors, CRB p.412, list none). Playtest 2026-11-17 #44: forcing two
        # stuck doors paid 200 XP each and carried her to level 2.
    else:
        bits.append(f"{_cap(door['name'])} holds.")
    fx.append({"kind": "dungeon_door", "to": far, "how": how, "opened": opened})
    return Outcome(intent_id=intent.id, op="break_in", effects=fx, rolls=[roll], dc=dc,
                   tell=" ".join(b for b in bits if b), because=intent.because)
