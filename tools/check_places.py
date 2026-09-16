"""Check a World Bible export's `play.places[]` against what Pathfinder GM can read.

Standalone on purpose. It imports nothing from Pathfinder GM and nothing from World
Bible — only the standard library and `place-vocabulary.json`, which is generated from
`rules/places.py` and `rules/floorplan.py`. Copy this file and that one into the World
Bible repo and it runs there:

    python check_places.py <world>-campaign.json
    python check_places.py <world>-campaign.json --vocab place-vocabulary.json
    python check_places.py <world>-campaign.json --tier 2

The contract it checks is `docs/places-and-races-for-world-bible.md`. It reports, per
settlement, what the consumer would build from the list, and every way the list is
unusable — an id that parses to nothing, an exit to a place that is not there, somewhere a
party can walk into and not out of.

**The failure it was written for.** Measured 2026-09-15 against the live tables: the id
format the original ask 3 specified — `{settlement}:{slug}`, no terrain segment — gives an
authored place whose name the consumer does not already know a twenty-by-twenty field of
open ground, the blank battlefield that a fortnight of work existed to remove. A place the
consumer happens to recognise by slug (`the-market`) survives it by accident, so checking
one familiar name proves the wrong thing and a checker has to look at all of them.

Exit code is 1 if any place has a problem. Notes never fail the run: a missing docks in a
port town is worth saying and is not worth refusing an export over.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

# The consumer tokenises a settlement's facts and prose with exactly this before matching
# the cue table, so the checker has to as well — a cue is matched against whole words, and
# "reporting" does not contain "port" for these purposes.
_WORDS = re.compile(r"[a-z][a-z'-]+")
_DIGIT = re.compile(r"\d")

# Fields that would be a second spatial authority if anybody shipped them. Ask 3 has
# refused distances since it was written — Fate shipped weighted zone borders and deleted
# them — and this is the mechanical form of that refusal.
_REFUSED = ("distance", "distances", "miles", "feet_to", "weight", "weights", "cost",
            "travel_time", "minutes", "x", "y", "lat", "lon", "latitude", "longitude",
            "coordinates", "image", "pixels", "pixels_per_grid")

TIER2 = ("size_ft", "clutter", "footing", "vertical")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --- the id, which is where the whole thing turns ----------------------------------------

def parse_id(pid: str) -> tuple[str, str, str, int] | None:
    """(parent, terrain, slug, storey) or None if it does not parse.

    Deliberately a reimplementation of `places.terrain_of` rather than a call to it: this
    script has to run in a repo that does not have Pathfinder GM in it, and a checker that
    agrees with the consumer only because it imports it cannot be shipped anywhere.
    """
    head, sep, tail = str(pid or "").partition(":")
    if not sep or "~" not in head:
        return None
    parent, _, terrain = head.rpartition("~")
    slug, caret, storey = tail.partition("^")
    if not parent or not terrain or not slug:
        return None
    if caret:
        try:
            level = int(storey)
        except ValueError:
            return None
    else:
        level = 0
    return parent, terrain.strip().lower(), slug.strip().lower(), level


# --- one place ---------------------------------------------------------------------------

def check_place(place: dict, vocab: dict, known: set[str], entities: set[str],
                tier: int) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    notes: list[str] = []
    pid = str(place.get("id") or "")

    parts = parse_id(pid)
    if parts is None:
        problems.append(
            f"id {pid!r} does not parse as {vocab['id_grammar']['pattern']} — "
            f"the consumer would build open ground here. Example: "
            f"{vocab['id_grammar']['example']}")
        parent = terrain = ""
    else:
        parent, terrain, _slug, _storey = parts
        if terrain not in vocab["terrains"]:
            problems.append(f"terrain {terrain!r} in the id is not one the consumer "
                            f"knows: {', '.join(vocab['terrains'])}")
        stated = str(place.get("terrain") or "").strip().lower()
        if stated and stated != terrain:
            problems.append(f"id says {terrain!r} and the terrain field says {stated!r}; "
                            f"the id wins and the field is what a reader believes")
        elif not stated:
            notes.append("no terrain field — legal, since the id carries it, but a reader "
                         "should not have to parse an id")
        if parent not in entities:
            problems.append(f"id names parent {parent!r}, which is not an entity in this "
                            f"export")

    for key in ("name", "about"):
        if not str(place.get(key) or "").strip():
            problems.append(f"no {key}")
    if _DIGIT.search(str(place.get("about") or "")):
        problems.append("a digit in `about` — it is prose the narrator may repeat, and no "
                        "model is ever handed a number")

    stated_parent = str(place.get("parent") or "").strip()
    if stated_parent and stated_parent not in entities:
        problems.append(f"parent {stated_parent!r} is not an entity in this export")
    if parts and stated_parent and stated_parent != parent:
        problems.append(f"parent field {stated_parent!r} disagrees with the id's "
                        f"{parent!r}")

    origin = str(place.get("origin") or "").strip()
    if origin != "world":
        problems.append(f"origin {origin!r}; everything World Bible exports is 'world' "
                        f"({', '.join(vocab['origins'])} are the three)")

    exits = place.get("exits")
    if not isinstance(exits, list):
        problems.append("no exits[] — a place with no way out is somewhere a party is "
                        "stranded")
        exits = []
    for other in exits:
        if str(other) not in known:
            problems.append(f"exit to {other!r}, which is not a place in this export")
        elif str(other) == pid:
            problems.append("exits to itself")

    if place.get("described_only") and exits:
        notes.append("described_only with exits — it cannot be entered, so its exits are "
                     "never walked")

    for bad in _REFUSED:
        if bad in place:
            problems.append(f"field {bad!r}: a place carries no distance, weight or "
                            f"coordinate. Adjacency only")

    if tier >= 2:
        problems.extend(_tier2(place, vocab))
    if tier >= 3:
        problems.extend(_tier3(place))
    return problems, notes


def _tier2(place: dict, vocab: dict) -> list[str]:
    out: list[str] = []
    missing = [f for f in TIER2 if f not in place]
    if len(missing) == len(TIER2):
        return ["no tier 2 fields at all; the consumer derives the room's shape from its "
                "id instead, which is a working export and not a described one"]
    if missing:
        out.append(f"tier 2 half-written: missing {', '.join(missing)}")

    size = place.get("size_ft")
    if size is not None:
        if not isinstance(size, dict):
            out.append("size_ft is not an object of {width, depth, height}")
        else:
            for key in ("width", "depth"):
                v = size.get(key)
                if not isinstance(v, (int, float)) or v <= 0:
                    out.append(f"size_ft.{key} is {v!r}; it is a measurement in feet")
                elif v < 10:
                    out.append(f"size_ft.{key} is {v} — that is squares or metres, not "
                               f"feet. A room is tens of feet across")
                elif v > 300:
                    out.append(f"size_ft.{key} is {v}; over 300 ft makes a slow fight and "
                               f"a narrator that cannot say where anything is")
            h = size.get("height", "missing")
            if h == "missing":
                out.append("size_ft has no height; write null for open sky, so the "
                           "difference between outdoors and unstated is on the page")
            elif h is not None and (not isinstance(h, (int, float)) or h <= 0):
                out.append(f"size_ft.height is {h!r}; feet, or null for open sky")
            elif isinstance(h, (int, float)) and h < vocab["ceilings_ft"]["house"]:
                out.append(f"size_ft.height is {h} ft, under a house's "
                           f"{vocab['ceilings_ft']['house']} — a crawl. Be sure")

    for field, legal in (("clutter", vocab["clutter"]["words"]),
                         ("footing", vocab["footing"]["words"]),
                         ("vertical", vocab["vertical"])):
        word = place.get(field)
        if word is None:
            continue
        if str(word) not in legal:
            out.append(f"{field} {word!r} is not one of {', '.join(sorted(legal))}")

    storeys = place.get("storeys")
    if storeys is not None:
        if not isinstance(storeys, dict):
            out.append("storeys is not an object of {up, down}")
        else:
            for key in ("up", "down"):
                v = storeys.get(key, 0)
                if not isinstance(v, int) or v < 0:
                    out.append(f"storeys.{key} is {v!r}; a count of floors, 0 or more")
            outdoors = isinstance(size, dict) and size.get("height", "x") is None
            if outdoors and (storeys.get("up") or storeys.get("down")):
                out.append("storeys under open sky; a place with no ceiling has no "
                           "upstairs, and the consumer will refuse the stairs")
    return out


def _tier3(place: dict) -> list[str]:
    out: list[str] = []
    size = place.get("size_ft") if isinstance(place.get("size_ft"), dict) else {}
    w = int(size.get("width") or 0) // 5
    d = int(size.get("depth") or 0) // 5
    ceiling = size.get("height")

    for field in ("blocked", "difficult"):
        cells = place.get(field)
        if cells is None:
            continue
        if not isinstance(cells, list):
            out.append(f"{field} is not a list of [x, y]")
            continue
        for cell in cells:
            if (not isinstance(cell, (list, tuple)) or len(cell) != 2
                    or not all(isinstance(n, int) for n in cell)):
                out.append(f"{field} contains {cell!r}; each is [x, y] in squares")
            elif w and d and not (0 <= cell[0] < w and 0 <= cell[1] < d):
                out.append(f"{field} {list(cell)} is outside the {w}x{d} square grid "
                           f"size_ft describes")

    for field in ("floor", "parapet"):
        heights = place.get(field)
        if heights is None:
            continue
        if not isinstance(heights, dict):
            out.append(f"{field} is not an object of {{'x,y': height_ft}}")
            continue
        for key, ft in heights.items():
            try:
                x, y = (int(n) for n in str(key).split(","))
            except ValueError:
                out.append(f"{field} key {key!r} is not 'x,y'")
                continue
            if w and d and not (0 <= x < w and 0 <= y < d):
                out.append(f"{field} {key!r} is outside the {w}x{d} square grid")
            if not isinstance(ft, (int, float)) or ft < 0:
                out.append(f"{field}[{key!r}] is {ft!r}; a height in feet")
            elif ceiling and ft >= ceiling:
                out.append(f"{field}[{key!r}] is {ft} ft under a {ceiling} ft ceiling; "
                           f"nothing can stand on it")
    return out


# --- a settlement's worth of them ----------------------------------------------------------

def reachable_from(start: str, by_id: dict[str, dict]) -> set[str]:
    """Every place walkable from `start`, following exits forward only.

    Forward only on purpose: the consumer walks exits, it does not infer a way back, so a
    one-way exit is a real thing an author can write and this has to be able to see it.
    """
    seen, queue = {start}, deque([start])
    while queue:
        for nxt in by_id.get(queue.popleft(), {}).get("exits") or []:
            if str(nxt) in by_id and str(nxt) not in seen:
                seen.add(str(nxt))
                queue.append(str(nxt))
    return seen


def settlement_text(entity: dict) -> set[str]:
    """The words the consumer reads a settlement's implied places out of: its facts and
    every paragraph of its sections."""
    facts = entity.get("facts") or {}
    bits = [str(v) for v in (facts.values() if isinstance(facts, dict) else facts)]
    for section in entity.get("sections") or []:
        bits.extend(str(p) for p in (section.get("paragraphs") or []))
    bits.append(str(entity.get("summary") or ""))
    return set(_WORDS.findall(" ".join(bits).lower()))


def check_group(pid_parent: str, group: list[dict], entity: dict, vocab: dict,
                ) -> tuple[list[str], list[str]]:
    """What is wrong with one location's whole set, as against one place in it."""
    problems: list[str] = []
    notes: list[str] = []
    by_id = {str(p.get("id")): p for p in group}
    enterable = [p for p in group if not p.get("described_only")]

    # Everything the campaign overlay remembers about a place is keyed by its id, so two
    # places sharing one is not a duplicate row — it is one place with two descriptions
    # and whichever the reader saw last.
    seen: set[str] = set()
    for place in group:
        pid = str(place.get("id"))
        if pid in seen:
            problems.append(f"two places share the id {pid!r}")
        seen.add(pid)

    kind = str((entity or {}).get("kind") or "").upper()
    if kind == "CITY" and len(enterable) < 4:
        notes.append(f"a CITY with {len(enterable)} place(s); four is the floor the "
                     f"contract asks for, and the consumer's own generator makes three "
                     f"to {vocab['most_places']}")

    if len(enterable) > vocab["most_places"]:
        notes.append(
            f"{len(enterable)} places; the consumer's own ceiling is "
            f"{vocab['most_places']} — {vocab.get('most_generated', '?')} generic plus "
            f"{vocab.get('most_implied', '?')} its own words may earn — and the extra "
            f"ones are somewhere a narrator can strand a player with nothing to do")

    if enterable:
        start = str(enterable[0]["id"])
        got = reachable_from(start, by_id)
        stranded = [str(p["id"]) for p in enterable if str(p["id"]) not in got]
        if stranded:
            problems.append(f"not reachable from {start}: {', '.join(sorted(stranded))}")
        for place in enterable:
            here = str(place["id"])
            # Only exits that resolve. An exit to nowhere is already a problem on the
            # place itself, and calling it "one-way" as well described it wrongly — the
            # party cannot walk in either.
            back = [o for o in (place.get("exits") or [])
                    if str(o) in by_id
                    and here not in ((by_id[str(o)].get("exits")) or [])]
            for other in back:
                notes.append(f"{here} -> {other} is one-way; the party can walk in and "
                             f"not out unless `about` says why")

    if entity is not None:
        words = settlement_text(entity)
        have = {str(p.get("name") or "").strip().lower() for p in group}
        for row in vocab["implied"]:
            hit = sorted(w for w in row["words"] if w in words)
            if hit and row["place"] not in have:
                notes.append(f"its own words say {', '.join(hit[:3])} and there is no "
                             f"{row['place']} — the consumer would mint one")
    return problems, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export", type=Path, help="a <world>-campaign.json")
    ap.add_argument("--vocab", type=Path,
                    default=Path(__file__).with_name("place-vocabulary.json"))
    ap.add_argument("--tier", type=int, default=1, choices=(1, 2, 3),
                    help="how much of the contract to hold the export to (default 1)")
    args = ap.parse_args()

    if not args.vocab.exists():
        alt = Path(__file__).resolve().parents[1] / "docs" / "place-vocabulary.json"
        if alt.exists():
            args.vocab = alt
        else:
            print(f"cannot find {args.vocab} — it is generated by Pathfinder GM's "
                  f"tools/export_place_vocab.py and must sit beside this script.")
            return 2
    vocab = load(args.vocab)
    world = load(args.export)
    written = (world.get("play") or {}).get("places") or []
    entities = {str(e.get("id")): e for e in world.get("entities") or []}

    print(f"{args.export.name}: schema {world.get('schema_version')}, "
          f"{len(written)} place(s), tier {args.tier}")
    if args.tier >= 2:
        print("note: clutter and footing are a proposed vocabulary — nothing reads them "
              "yet, so these checks hold you to the contract rather than to the engine.")

    if not written:
        print("\nno play.places[] — the consumer generates a settlement's places from "
              "its id and mints the ones its own words imply. That is a working export; "
              "it is not an authored one, and the narrator cannot be grounded against a "
              "list of places that does not exist.")
        return 0

    known = {str(p.get("id")) for p in written}
    groups: dict[str, list[dict]] = {}
    for place in written:
        parts = parse_id(str(place.get("id") or ""))
        groups.setdefault(parts[0] if parts else "(unparseable)", []).append(place)

    bad = noted = 0
    verticals: dict[str, int] = {}
    for parent, group in sorted(groups.items()):
        entity = entities.get(parent)
        name = str((entity or {}).get("name") or parent)
        print(f"\n  {name} — {len(group)} place(s)")
        gp, gn = check_group(parent, group, entity, vocab)
        for problem in gp:
            print(f"    PROBLEM  {problem}")
        for note in gn:
            print(f"    note     {note}")
        bad += bool(gp)
        noted += bool(gn)
        for place in sorted(group, key=lambda p: str(p.get("id"))):
            problems, notes = check_place(place, vocab, known, set(entities), args.tier)
            shape = ""
            if args.tier >= 2 and isinstance(place.get("size_ft"), dict):
                s = place["size_ft"]
                roof = f"{s.get('height')} ft" if s.get("height") else "open sky"
                shape = f" [{s.get('width')}x{s.get('depth')} ft, {roof}, " \
                        f"{place.get('vertical', '?')}]"
            print(f"    {str(place.get('name') or '(unnamed)')}{shape}")
            for problem in problems:
                print(f"      PROBLEM  {problem}")
            for note in notes:
                print(f"      note     {note}")
            bad += bool(problems)
            noted += bool(notes)
            word = str(place.get("vertical") or "")
            if word:
                verticals[word] = verticals.get(word, 0) + 1

    print()
    if verticals:
        flat = verticals.get("none", 0)
        total = sum(verticals.values())
        print(f"verticality: {total - flat} of {total} places are shaped upward "
              f"({', '.join(f'{k} {v}' for k, v in sorted(verticals.items()))}). "
              f"The consumer's own tables are {vocab['vertical_balance']['consumer_tables']}.")
        # Both ends. The instruction has two halves — "more likely to have verticality
        # than not, but not so much that every place has it even when it is silly" — and
        # the first version of this only checked the first half, so an export where
        # NOTHING was flat printed "72 of 72" as though that were the goal. A guard on one
        # side of a two-sided rule reads as approval of the other.
        if total and (total - flat) / total < 0.5:
            print("  note: more of this world is flat than is not, which is the opposite "
                  "of the standing instruction. Reach for a reason to make a place flat, "
                  "not a reason to make it vertical.")
        elif total >= 8 and not flat:
            example = ", ".join(sorted(vocab["flat_by_design"])[:3])
            print(f"  note: not one place in this world is flat. `none` is a word in the "
                  f"vocabulary and nothing reached for it — the consumer's own tables are "
                  f"{vocab['vertical_balance']['consumer_tables']}, and the places it "
                  f"keeps flat are the ones a reader would agree are flat ({example}). "
                  f"A generator with no rule for refusing verticality will put a gallery "
                  f"in an alley.")
    print(f"{len(written)} place(s) in {len(groups)} location(s): {bad} with problems, "
          f"{noted} with notes.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
