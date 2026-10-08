"""What an item is made of, as tags: `material.metal`, `material.wood.ash`, `material.main.cold-iron`.

Enchanting plan §16 and contracts §3.3; the cross-craft ruling it serves is the owner's
"there are spells that affect metal" (leatherworking Q7.3): heat metal, chill metal,
shocking grasp's +3 against metal armour, the druid's no-metal rule, and the enchanter's
cold iron and noqual surcharges all ask one question — *is it metal, and which metal* —
and before this the only answer was a list of suit names in `rules/armour.py`, which called
a forged mithral-on-darkwood shield metal by its name and a forged noqual breastplate metal
only because "breastplate" was on the list.

**Where the answer comes from, in order:**

1. A forged record (or one from `forge_items.record_for_base`): its `pieces`, each piece's
   material followed to its root (`steel-studs` is steel, `dragonhide-grip` is red
   dragonhide) and asked its substance. The main piece (head, body) is also
   `material.main.<id>`: the book's "only the most prevalent material" (CRB, special
   materials), which is what the cold iron surcharge asks.
2. A leatherworker's piece or an old crafted record: the `from_materials` it was made from
   (studded leather's studs are a metal fitting, so the druid reads the studs, not the name),
   and the table defaults for its base when it lists none.
3. A table key ("chainmail", "light wooden shield", "club"): the default pieces in
   `content/rules/base-pieces.json`, the same file that gives a bought item its record.

**A substance is read from the material's own `kind`** (metal and alloy are metal, hide is
leather, thread is cord), so a world's own metal is metal the day World Bible exports it
with `kind: metal`. A forge fitting's kind says only "fitting", so the fittings that are
not a link to another material (`ash-haft`, `bone-grip`) are named in the data file's
`substances`. Never from a name: "ironwood" is wood and "silver-clasps" is metal, and only
a table can say so.

**A finish is not a substance.** Alchemical silvering lies on steel; the blade is still steel
and still metal. Foundry's PF1 system made the same split (its material registry gives each
material a `baseMaterial` of steel or wood and keeps surface treatments as `addon`
materials; https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1,
module/registry/materials.mjs, read 2026-10-05), and the silvered blade's DR trait stays
the finish's own `strikes_as`, read where it always was.

Tags are asked by prefix through `states.matches` (law 1); `has_material(thing,
"material.metal")` is the whole of "is it metal".
"""
from __future__ import annotations

import functools
import json

from . import states

# Forge pieces by gear (forge_items.PIECES), repeated here only as the order a default row
# is read in; the gear words are the forge's.
_MAIN = {"weapon": "head", "armour": "body", "shield": "body", "worn": "body"}


# --- the data file ---------------------------------------------------------------------------

def _path():
    from pathlib import Path

    from django.conf import settings

    return Path(settings.BASE_DIR) / "content" / "rules" / "base-pieces.json"


@functools.lru_cache(maxsize=1)
def table() -> dict:
    """`content/rules/base-pieces.json`, read once. Shipped data with no homebrew
    overlay; a test that swaps the file calls `table.cache_clear()`."""
    return json.loads(_path().read_text(encoding="utf-8"))


def _material(mid: str) -> dict | None:
    """A material document through the forge's one door (tests replace it there)."""
    from . import forge_items

    return forge_items.material(mid)


def root_material(material_id) -> str:
    """The material a piece is really made of: a form or a fitting followed through its
    `material` link to the root ("steel-studs" -> "steel", "iron-ore" -> "iron"); a
    `substances` row's own `material` ("ash-haft" -> "ash"); otherwise the id itself."""
    mid = str(material_id or "").strip().lower()
    seen: set[str] = set()
    while mid and mid not in seen:
        seen.add(mid)
        row = (table().get("substances") or {}).get(mid)
        if row:
            return str(row.get("material") or mid)
        doc = _material(mid)
        nxt = str((doc or {}).get("material") or "").strip().lower()
        if not nxt or nxt == mid:
            return mid
        mid = nxt
    return mid


def substance_of(material_id) -> str:
    """What a material is: one of `states.SUBSTANCES`, or "" when nothing says (an unknown
    id answers nothing, never a guess). The data file's `substances` row first, then the
    material's own `kind`, then its `material` link followed."""
    mid = str(material_id or "").strip().lower()
    seen: set[str] = set()
    data = table()
    while mid and mid not in seen:
        seen.add(mid)
        row = (data.get("substances") or {}).get(mid)
        if row:
            return str(row.get("substance") or "")
        doc = _material(mid)
        if doc is None:
            return ""
        got = (data.get("kinds") or {}).get(str(doc.get("kind") or ""))
        if got:
            return str(got)
        nxt = str(doc.get("material") or "").strip().lower()
        if not nxt or nxt == mid:
            return ""
        mid = nxt
    return ""


# --- default pieces for a table item ---------------------------------------------------------

def default_pieces(base: str, gear: str = "") -> dict[str, str] | None:
    """The pieces a bought `base` is made of, `{piece: material id}`, or None when the
    tables do not know it. `gear` ("weapon", "armour", "shield") when the caller knows it;
    otherwise the armour, shield and weapon tables are asked in that order."""
    from . import armour as armour_mod

    data = table()
    key = str(base or "").strip().lower()
    if gear in ("", "armour", "shield"):
        kind, akey = armour_mod.key_for(key)
        if kind and (not gear or gear == kind):
            row = (data.get("armour" if kind == "armour" else "shields") or {}).get(akey)
            if row is not None:
                return dict(row)
        if gear in ("armour", "shield"):
            return None
    return _weapon_pieces(key)


def _weapon_pieces(text: str) -> dict[str, str] | None:
    from . import weapons as weapons_mod

    key = weapons_mod.key_for(text) if text else ""
    if not key or not weapons_mod.has(key):
        return None
    w = table().get("weapons") or {}
    rows = w.get("rows") or {}
    if key in rows:
        return dict(rows[key])
    groups = weapons_mod.groups_of(key)
    for group, row in w.get("by_group") or ():
        if group in groups:
            return dict(row)
    section = str(weapons_mod.get(key).get("section") or "")
    if section in (w.get("by_section") or {}):
        return dict(w["by_section"][section])
    return dict(w.get("default") or {})


def weapon_key(text: str) -> str:
    """The weapons-table key a word names, or ""."""
    from . import weapons as weapons_mod

    key = weapons_mod.key_for(str(text or "")) if text else ""
    return key if key and weapons_mod.has(key) else ""


# --- the tags --------------------------------------------------------------------------------

def _piece_material(spec) -> str:
    if isinstance(spec, str):
        return spec.strip().lower()
    if isinstance(spec, dict):
        return str(spec.get("material") or "").strip().lower()
    return ""


def _resolve(thing) -> tuple[dict[str, str], str, list[str]]:
    """({piece: material id}, the main piece's slot, [loose material ids]) for anything
    an item can be passed as. Loose ids are a leatherworker's `from_materials`: what it
    was made of, with no piece each."""
    from . import forge_items

    rec = forge_items.record_of(thing)
    if rec is None and isinstance(thing, dict):
        rec = thing
    if isinstance(rec, dict) and isinstance(rec.get("pieces"), dict):
        gear = str(rec.get("gear") or "weapon")
        pieces = {slot: _piece_material(p) for slot, p in rec["pieces"].items()}
        return {s: m for s, m in pieces.items() if m and m != "none"}, _MAIN.get(gear, "head"), []
    if isinstance(thing, str):
        pieces = default_pieces(thing)
        if pieces is None:
            return {}, "", []
        gear = _gear_of_key(thing)
        return pieces, _MAIN.get(gear, "head"), []
    # A record or a Stock that names its base and perhaps what it was made of.
    get = (thing.get if isinstance(thing, dict)
           else lambda k, d=None: getattr(thing, k, d))
    loose = [str(m).strip().lower() for m in (get("from_materials") or ()) if m]
    base = str(get("armour") or get("weapon") or "")
    if loose:
        return {}, "", loose
    if base:
        # The armour field may name a shield ("buckler"), so the tables decide which.
        pieces = default_pieces(base, "" if get("armour") else "weapon")
        if pieces is not None:
            return pieces, _MAIN.get(_gear_of_key(base), "head"), []
    return {}, "", []


def _gear_of_key(text: str) -> str:
    from . import armour as armour_mod

    kind, _ = armour_mod.key_for(text)
    return kind or "weapon"


def material_tags(thing) -> tuple[str, ...]:
    """Every material tag of an item, sorted: a record, a `Stock`, a table key or a worn
    slot string. () when nothing says what it is made of (a catalogue ring, an unknown
    word) — an item that cannot answer is never guessed metal."""
    pieces, main, loose = _resolve(thing)
    out: set[str] = set()

    def add(mid: str, is_main: bool) -> None:
        sub = substance_of(mid)
        if not sub:
            return
        root = root_material(mid)
        out.add(f"{states.MATERIAL}.{sub}")
        out.add(states.material_tag(sub, root))
        if is_main:
            out.add(states.main_material_tag(root))

    for slot, mid in pieces.items():
        add(mid, slot == main)
    # A leatherworker's piece names no main slot: its first hide is its body, and a
    # forge-made thing listed loose is its first metal (the forge migration's reading).
    first = next((m for m in loose if substance_of(m) in ("leather", "metal")), "")
    for mid in loose:
        add(mid, mid == first)
    return tuple(sorted(out))


def has_material(thing, prefix: str) -> bool:
    """Whether any of the item's material tags answers `prefix` — `material.metal`,
    `material.metal.cold-iron`, `material.main.noqual` — by `states.matches`, never `==`."""
    q = str(prefix or "").strip().lower()
    return any(states.matches(t, q) for t in material_tags(thing))


def main_material(thing) -> str | None:
    """The root id of the item's most prevalent material, or None."""
    lead = states.MATERIAL_MAIN + "."
    for t in material_tags(thing):
        if t.startswith(lead):
            return t[len(lead):]
    return None


def materials_in(thing) -> list[str]:
    """Every root material id in the item, main first — for a reader that asks about one
    material's own data (noqual's `enchant_surcharge_gp`)."""
    pieces, main, loose = _resolve(thing)
    ids = ([pieces[main]] if main in pieces else []) + [m for s, m in pieces.items()
                                                       if s != main] + loose
    out: list[str] = []
    for mid in ids:
        root = root_material(mid)
        if root and root not in out:
            out.append(root)
    return out


__all__ = ["material_tags", "has_material", "main_material", "materials_in",
           "substance_of", "root_material", "default_pieces", "weapon_key", "table"]
