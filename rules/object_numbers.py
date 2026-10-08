"""An object's hardness and hit points: the book's row first, then what it is made of.

The one reader for an item's object numbers (the owner, 2026-10-07: "use the book but only
as a base — the materials used when smithing should change that if they say so"). Asked by
`Actor.item` (so by sunder, acid, mending and every other door that hurts or heals a thing),
by the judge-its-make look, and on load to re-derive a save's records. There is no second
table: Table 7-12 and Table 7-13 both live in `rules/tables.py`.

How the numbers are found, in order:

1. **The book's row.** A weapon, suit or shield takes Core Rulebook Table 7-12 (p.175):
   a light blade 2 hit points, a one-handed blade 5, a heavy steel shield 20, a suit its
   armour bonus x 5, and so on. Before 2026-10-07 every steel thing got Table 7-13's inch
   of steel (30 hit points), and a broken longsword took fifteen or sixteen hours to mend.
   Which row a weapon is: a launcher (bow, crossbow, sling, firearm) is a projectile
   weapon; a light or heavy blade (the fighter groups, `weapons.groups_of`) is a blade;
   anything else is hafted when its haft is wood and metal-hafted when its haft (or, with
   no haft but a grip, its head) is metal — the haft's substance read from what the thing
   is made of (`item_tags.default_pieces` for a bought one, the forged record's own
   pieces), because Table 7-12's rows are named for exactly that. Light, one-handed or
   two-handed is the weapon table's own. A suit's hardness is its body's substance from
   Table 7-13 ("Armor: special — varies by material").
2. **What it is made of, when its documents say so.** A forged thing adds the build's own
   `hardness` and `hp_per_inch` numbers (`forge_items.build(...)["gear"]`: the main
   piece's book effects, every piece's weighted modifiers, flaws, folds and finishes). A
   bought thing named for a special material ("adamantine longsword") adds that
   material's BOOK numbers only — its document's `book: true` effects — since no smith
   chose its grip. The documents state hit points per inch as a change from steel's 30
   (adamantine +10 is the book's 40; inubrix −20 is its "10 hit points per inch"), so a
   change of N per inch is N/30 of the row's hit points, rounded toward zero like every
   forge number (the owner's ruling of 2026-10-03): adamantine's +10 is the book's "one-
   third more hit points than normal" (CRB p.154), and a house ±2 leaves a 5-hit-point
   blade alone. A HIDE's documents state theirs as a change from leather's own row
   (hardness 2, 5 per inch): a thing whose body is leather reads its per-inch step against
   5 (leatherworking plan §15, dragonhide's 10 per inch is +5), and a worn good or a madu,
   which Table 7-12 has no row for, still takes its build's numbers on its inch of leather.
3. **Its enhancement.** "+2 hardness and +10 hit points for each +1" (CRB p.174).

Anything Table 7-12 has no row for — a cloak, a rope, a ring, a whip, arrows — keeps the
old reading: one inch of what its name says it is made of (Table 7-13).

Not done: Table 7-12's size footnote (halved per size below Medium). Nothing records the
size an item was made for, and guessing it from whoever holds it would change a sword's
hit points when a halfling picks it up.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .tables import (
    ARMOUR, HARDNESS_PER_ENHANCEMENT, HP_PER_ENHANCEMENT, MATERIALS, OBJECT_ROWS, SHIELDS,
    material_for,
)

# What the material documents measure their per-inch hit points against: Table 7-13's
# iron or steel. Pinned by tests/test_object_numbers.py against every document that
# states an absolute figure in its own note.
DOCUMENT_BASE_HP_PER_INCH = MATERIALS["steel"]["hp_per_inch"]

# A substance (`states.SUBSTANCES`) to its Table 7-13 row. Horn has no row in the book;
# bone is the nearest it prints (HOUSE).
_SUBSTANCE_ROW = {"metal": "steel", "wood": "wood", "leather": "leather", "bone": "bone",
                  "horn": "bone", "cloth": "cloth", "cord": "rope", "stone": "stone",
                  "glass": "glass"}

# The words a bought thing's name uses for a special material, to that material's
# document. Only these four are named in the Core Rulebook's Special Materials for
# weapons and armour; a name that says none of them is ordinary make.
_NAMED_MATERIALS = (("adamantine", "adamantine"), ("mithral", "mithral"),
                    ("mithril", "mithral"), ("cold iron", "cold-iron"),
                    ("darkwood", "darkwood-haft"))

_PLUS = re.compile(r"\+\s*(\d+)")


@dataclass(frozen=True)
class Numbers:
    """What one object is: its hardness, its full hit points, its Table 7-13 material and
    the reasons, in words, each with its source — for the judge's look and the tests."""
    hardness: int
    hp_max: int
    material: str
    row: str = ""
    why: tuple[str, ...] = ()


def _toward_zero(x: float) -> int:
    """Rounded toward zero, once (rounded to six places first, as `forge_items` does, so
    a floating-point epsilon never moves an integer)."""
    return int(math.trunc(round(x, 6)))


def substance_numbers(material: str) -> tuple[int, int]:
    """(hardness, hit points) of one inch of a Table 7-13 material; steel when unknown."""
    spec = MATERIALS.get(material, MATERIALS["steel"])
    return int(spec["hardness"]), max(1, int(spec["hp_per_inch"]))


def _clean(name: str) -> str:
    """A carried name with the words that do not change what table row it is taken off:
    an owner, an enhancement, masterwork, a special material."""
    low = " ".join(str(name or "").split()).lower()
    low = re.sub(r"^.*?'s\s+", "", low)
    low = _PLUS.sub(" ", low)
    low = re.sub(r"\bmasterwork\b", " ", low)
    low = re.sub(r"^\s*(my|the|an?|his|her|their)\s+", "", low)
    for word, _mid in _NAMED_MATERIALS:
        low = low.replace(word, " ")
    return " ".join(low.split())


def _gear_and_base(name: str, rec: dict | None) -> tuple[str, str]:
    """("weapon" | "armour" | "shield", the table key) or ("", "")."""
    from . import armour as armour_mod
    from . import forge_items
    from . import weapons as weapons_mod

    if forge_items.is_forged(rec):
        gear = str(rec.get("gear") or "weapon")
        base = str(rec.get("base") or rec.get(gear) or "")
        if gear == "worn":
            # A leatherworker's cloak or boots: no Table 7-12 row, so an inch of what its
            # body is made of (`numbers` reads the pieces for it).
            return "worn", base
        if gear in ("armour", "shield"):
            kind, key = armour_mod.key_for(base)
            return (gear, key) if key else ("", "")
        key = weapons_mod.key_for(base)
        return ("weapon", key) if key and weapons_mod.has(key) else ("", "")
    candidates = []
    if isinstance(rec, dict):
        candidates += [str(rec.get(k) or "") for k in ("armour", "weapon", "base")]
    candidates.append(_clean(name))
    for text in candidates:
        if not text:
            continue
        kind, key = armour_mod.key_for(text)
        if kind:
            return kind, key
        wkey = weapons_mod.key_for(text)
        if wkey and weapons_mod.has(wkey):
            return "weapon", wkey
    return "", ""


def _pieces(gear: str, base: str, rec: dict | None) -> dict[str, str]:
    from . import forge_items
    from . import item_tags

    if forge_items.is_forged(rec):
        out = {}
        for slot, p in (rec.get("pieces") or {}).items():
            mid = p.get("material") if isinstance(p, dict) else p
            if mid and str(mid).lower() != "none":
                out[slot] = str(mid).strip().lower()
        return out
    return dict(item_tags.default_pieces(base, gear) or {})


def _substance(material_id: str) -> str:
    from . import item_tags

    return item_tags.substance_of(material_id) if material_id else ""


def _weapon_row(key: str, pieces: dict[str, str]) -> str:
    """Table 7-12's row name for a weapon, or "" when the book has no row for it."""
    from . import weapons as weapons_mod

    if weapons_mod.is_ammunition(key):
        return ""
    w = weapons_mod.get(key)
    groups = weapons_mod.groups_of(key)
    if groups & {"bows", "crossbows", "firearms"} or weapons_mod.is_launcher(key):
        return "projectile weapon"
    size = ("light" if w.get("light")
            else "two-handed" if int(w.get("hands") or 1) >= 2 else "one-handed")
    if groups & {"light blades", "heavy blades"}:
        return f"{size} blade"
    haft, head = _substance(pieces.get("haft", "")), _substance(pieces.get("head", ""))
    for said in (haft, head):
        if said == "wood":
            return f"{size} hafted weapon"
        if said == "metal":
            return f"{size} metal-hafted weapon"
    return ""


def _enhancement(name: str, rec: dict | None, gear: str) -> int:
    from . import magic_layer

    if not gear:
        return 0
    plus = 0
    if isinstance(rec, dict):
        plus = max(int(rec.get("enhancement") or 0),
                   int(magic_layer.magic_of(rec).get("enhancement") or 0))
    said = _PLUS.search(str(name or ""))
    if said:
        plus = max(plus, int(said.group(1)))
    return plus


def _table_material(pieces: dict[str, str], main: str, fallback_name: str) -> str:
    """The Table 7-13 key the thing is mostly made of, for `Item.material` (the fragments
    a sunder leaves, the acid's bite)."""
    mid = pieces.get(main, "")
    if mid in MATERIALS:
        return mid
    if mid.replace("-", " ") in MATERIALS:
        return mid.replace("-", " ")
    row = _SUBSTANCE_ROW.get(_substance(mid))
    return row or material_for(fallback_name)


def _named_material_deltas(name: str, gear: str, base: str) -> tuple[int, int, list[str]]:
    """(hardness, hit points per inch, the reasons) a bought thing's special material adds:
    its document's `book: true` gear numbers only."""
    from . import forge_items

    low = " ".join(str(name or "").split()).lower()
    for word, mid in _NAMED_MATERIALS:
        if word not in low:
            continue
        doc = forge_items.material(mid)
        if not doc:
            return 0, 0, []
        hard = per_inch = 0
        for eff in forge_items._effects_for(doc, gear):
            eff = forge_items.at_build(eff, gear, base)
            if not eff or not eff.get("book") or eff.get("type") != "gear_mod":
                continue
            if eff.get("target") == "hardness":
                hard += int(eff.get("amount") or 0)
            elif eff.get("target") == "hp_per_inch":
                per_inch += int(eff.get("amount") or 0)
        why = []
        if hard or per_inch:
            why.append(f"{doc.get('name') or mid} (CRB Special Materials): hardness "
                       f"{hard:+d}, hit points {per_inch:+d} per inch")
        return hard, per_inch, why
    return 0, 0, []


def _made_deltas(rec: dict, material: str, hard: int, hp: int) -> tuple[int, int, list[str]]:
    """(hardness, hit points, the reasons) of a forged thing with no Table 7-12 row — a
    worn good, a madu — moved by its build's own numbers, its per-inch step read against
    the inch of `material` it is (a hide's from leather's 5, a metal's from steel's 30)."""
    from . import forge_items

    made = forge_items.build(rec).get("gear") or {}
    d_hard = int(made.get("hardness", 0) or 0)
    d_inch = int(made.get("hp_per_inch", 0) or 0)
    said = []
    if d_hard or d_inch:
        said.append(f"its making: hardness {d_hard:+d}, hit points {d_inch:+d} per inch")
    per_inch = substance_numbers(material)[1] if material in ("leather", "hide") \
        else DOCUMENT_BASE_HP_PER_INCH
    return hard + d_hard, hp + _toward_zero(hp * d_inch / per_inch), said


def numbers(name: str, record: dict | None = None) -> Numbers:
    """The object numbers of a thing called `name`, read from `record` when it has one."""
    from . import forge_items

    rec = record if isinstance(record, dict) else None
    gear, base = _gear_and_base(name, rec)
    row_name, row = "", None
    pieces = _pieces(gear, base, rec) if gear else {}
    if gear == "weapon":
        row_name = _weapon_row(base, pieces)
    elif gear == "armour" and base in ARMOUR:
        row_name = "armor"
    elif gear == "shield" and base in SHIELDS:
        row_name = str(SHIELDS[base].get("name") or base).lower()
    row = OBJECT_ROWS.get(row_name)
    main = forge_items.MAIN_PIECE.get(gear, "head")
    named = next((mid for word, mid in _NAMED_MATERIALS
                  if word in str(name or "").lower() and mid.replace("-", " ") in MATERIALS),
                 "")
    if row is None:
        # What its main piece is made of when the tables know (a whip is leather), else
        # what its name says.
        material = (named or _table_material(pieces, main, name) if pieces
                    else named or material_for(str((rec or {}).get("name") or name)))
        hard, hp = substance_numbers(material)
        why = [f"an inch of {material} (CRB Table 7-13)"]
        if gear in ("worn", "shield", "armour") and forge_items.is_forged(rec):
            # A leatherworker's cloak or madu has no Table 7-12 row, but its hide still says
            # what it does to the thing, as it says it for a suit (`_made_deltas`).
            hard, hp, said = _made_deltas(rec, material, hard, hp)
            why += said
        return Numbers(hardness=max(0, hard), hp_max=max(1, hp), material=material, row="",
                       why=tuple(why))

    material = named or _table_material(pieces, main, name)
    why: list[str] = []
    per_inch_base = DOCUMENT_BASE_HP_PER_INCH
    if row_name == "armor":
        # Bulette leather "has the same statistics as studded leather" (`as_base`), its
        # hit points among them: armour bonus 3 x 5, not leather's 2 x 5.
        stats = base
        if forge_items.is_forged(rec):
            stats = str(forge_items.build(rec).get("as_base") or base)
        bonus = int(ARMOUR[stats].get("ac") or 0)
        hp = bonus * int(row["hp_per_armour_bonus"])
        # The body's SUBSTANCE, not its special metal: the material documents state their
        # hardness as a step from steel (mithral +5), so reading mithral's own 15 here and
        # then adding the step would count it twice — the defect the old forged branch
        # had (an adamantine blade at 29 hardness).
        plain = _SUBSTANCE_ROW.get(_substance(pieces.get(main, ""))) or material_for(name)
        hardness = substance_numbers(plain)[0]
        # A hide's documents state their steps from LEATHER (Table 7-13: hardness 2, 5 hit
        # points per inch), as a metal's state them from steel: dragonhide's book hardness
        # 10 and 10 per inch are +8 and +5 (leatherworking plan §15). So a leather body's
        # per-inch step is a fraction of leather's 5, not of steel's 30 — read off steel, a
        # +5 would have moved a 10-hit-point leather suit by one.
        if plain in ("leather", "hide"):
            per_inch_base = substance_numbers(plain)[1]
        why.append(f"armour: its armour bonus {bonus} x 5 hit points, hardness of "
                   f"{plain} (CRB Tables 7-12, 7-13)")
    else:
        hp, hardness = int(row["hp"]), int(row["hardness"])
        why.append(f"a {row_name} (CRB Table 7-12)")

    if forge_items.is_forged(rec):
        made = forge_items.build(rec).get("gear") or {}
        d_hard = int(made.get("hardness", 0) or 0)
        d_inch = int(made.get("hp_per_inch", 0) or 0)
        if d_hard or d_inch:
            why.append(f"its making: hardness {d_hard:+d}, hit points {d_inch:+d} per inch")
    else:
        d_hard, d_inch, said = _named_material_deltas(name, gear, base)
        why += said
    hardness += d_hard
    hp += _toward_zero(hp * d_inch / per_inch_base)

    plus = _enhancement(name, rec, gear)
    if plus:
        hardness += HARDNESS_PER_ENHANCEMENT * plus
        hp += HP_PER_ENHANCEMENT * plus
        why.append(f"+{plus} enhancement: hardness +{HARDNESS_PER_ENHANCEMENT * plus}, "
                   f"hit points +{HP_PER_ENHANCEMENT * plus} (CRB p.174)")
    return Numbers(hardness=max(0, hardness), hp_max=max(1, hp), material=material,
                   row=row_name, why=tuple(why))


def for_actor(actor, name: str) -> Numbers:
    """The numbers of something `actor` carries: its own forged or bought record when it
    has one (`Actor.crafted_record`), else the name alone."""
    finder = getattr(actor, "crafted_record", None)
    rec = finder(name) if callable(finder) else None
    return numbers(name, rec)


def carry_damage(item, new: Numbers) -> bool:
    """Move a stored record onto new numbers, keeping its state. True if anything moved.

    Old saves stored hit points from the old rule (an inch of the metal, 30 for steel). A
    record is re-derived, never trusted, so the next corrected document reaches a notched
    blade too; what it had suffered is carried over by proportion:

      * whole stays whole, ruined (0) stays ruined;
      * otherwise the same fraction of the new maximum, rounded down, never below 1 and
        never back to whole — and broken stays broken (at most half), sound stays sound
        (more than half) wherever the new maximum leaves room for both. A 2-hit-point
        dagger has no room for "scratched but sound": 1 is broken, so a sound scratch on
        one is carried as whole rather than as broken.
    """
    old_max, old_hp = int(item.hp_max or 0), int(item.hp if item.hp is not None else 0)
    moved = item.hardness != new.hardness or item.material != new.material
    item.hardness, item.material = new.hardness, new.material
    if old_max == new.hp_max:
        return moved
    new_max = new.hp_max
    if old_hp >= old_max:
        hp = new_max
    elif old_hp <= 0:
        hp = 0
    else:
        was_broken = old_hp <= old_max // 2
        hp = max(1, min(new_max - 1, (old_hp * new_max) // max(1, old_max)))
        if was_broken:
            hp = max(1, min(hp, new_max // 2))
        elif hp <= new_max // 2:
            hp = new_max // 2 + 1
        hp = min(hp, new_max)
    item.hp, item.hp_max = hp, new_max
    return True


__all__ = ["Numbers", "numbers", "for_actor", "carry_damage", "substance_numbers",
           "DOCUMENT_BASE_HP_PER_INCH"]
