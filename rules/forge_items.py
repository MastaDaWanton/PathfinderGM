"""What a forged item does, computed from what it is made of.

docs/blacksmithing-revamp-plan.md §6 is the maths and docs/blacksmithing-contracts.md §4 the
shape. The bench (lane D) writes a record that stores **ids and passes, never computed
numbers** — which material went into the head, how many times its bar was Strengthened, the
quality the Assemble step reached, the smith's level and perks at the time. Everything a
fight reads is computed here, on read, from the material documents (`rules/materials.py`,
contract §3). That is the read-live rule herbalism's `base_specs` learned the hard way:
baking a number in compounds rounding every time it is re-baked, and a corrected material
document would never reach a sword already made.

The sum (§6.2), per modifier target:

    raw       = Σ over pieces of value × weight(piece) × 1.5 ^ passes(piece)
                    weight: the main piece (head, body) 1.0, every other piece 0.5
    bonuses   = raw beneficial × quality × (1 + 0.05 × potency perks)
    negatives = raw detrimental × max(0.5, 0.9 ^ (level − 1) × 0.95 ^ hardening perks)
    final     = bonuses + negatives, rounded TOWARD ZERO, once

Bonuses and negatives are kept apart until the end because quality must never worsen a
negative and the level cut must never shrink a bonus. "Rounded down" is read as toward zero
(−1.45 is −1, not −2): the owner's ruling of 2026-10-03, so small numbers stay small.

What is NOT in the sum (§6.3): the main piece's book effects (the printed PF1e number is the
number — never weighted, never Strengthened, never multiplied by quality), masterwork (its own
effect from the quality tier, `rule:masterwork`), the quench mark (once, unscaled) and finish
treatments (their own effects, unscaled).

"Beneficial" is decided by what the number does, not by its sign. A `gear_mod` on arcane
spell failure, weight, armour category or a speed penalty is worse the higher it goes, so +10
spell failure is a negative and gets the level cut, while −2 armour check penalty (the
ARMOUR table's own convention: a more negative check penalty is a worse one) is a negative
too. Sorting by sign alone would have let a Flawless quality multiply a shirt's spell failure.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from . import effectspec as _effectspec
from .crafting import Stock

# --- the shape of an item -------------------------------------------------------------------

# Contract §3: weapon pieces head, haft, fittings; armour and shield body, fastenings, lining.
PIECES: dict[str, tuple[str, ...]] = {
    "weapon": ("head", "haft", "fittings"),
    "armour": ("body", "fastenings", "lining"),
    "shield": ("body", "fastenings", "lining"),
}
MAIN_PIECE = {"weapon": "head", "armour": "body", "shield": "body"}

# --- the numbers of §6.2, each named once ---------------------------------------------------

MAIN_WEIGHT = 1.0
OTHER_WEIGHT = 0.5
STRENGTHEN_PER_PASS = 1.5
# Crude 0.75, Sound 1, Fine 1.25, Superior 1.5, Flawless 1.75, each +N another 0.25 — one line,
# because the ladder is linear in the bench's quality index (0 Crude ... 4 Flawless, 5 = +1).
QUALITY_AT_CRUDE = 0.75
QUALITY_PER_STEP = 0.25
POTENCY_PER_PICK = 0.05
NEGATIVE_CUT_PER_LEVEL = 0.9
NEGATIVE_CUT_PER_HARDENING = 0.95
NEGATIVE_FLOOR = 0.5
# Superior or better is masterwork (§4.4).
MASTERWORK_AT = 3

# The item's own numbers (contract §2's `gear_mod` targets), all present in every build so a
# reader can index without asking. Which way is better is lane A's table
# (`effectspec.GEAR_TARGETS[...]["better"]`), asked rather than copied: a second copy of
# "asf gets worse as it rises" is the copy nobody updates.
GEAR_TARGETS = tuple(_effectspec.GEAR_TARGETS)
TRIGGERS = tuple(_effectspec.ITEM_TRIGGERS)
# Effect types that carry no number for the sum and are read elsewhere: strikes_as by the
# damage path, working traits by the bench, narrative by nobody (lane C's validator refuses it).
_NOT_SUMMED = frozenset({"strikes_as", "working", "narrative"})
# What a flaw costs, fixed and outside the sum (plan §7 and §5.5): skipping Temper leaves the
# blade brittle, a sulfurous fuel's Crude result leaves it hot-short. Each −1 hardness.
FLAWS: dict[str, list[dict]] = {
    "brittle": [{"type": "gear_mod", "target": "hardness", "amount": -1}],
    "hot_short": [{"type": "gear_mod", "target": "hardness", "amount": -1}],
}
# For armour, a material's AC folds into the suit's ARMOUR bonus (plan §5.2, as the book does
# for gold armour's −2), so it never meets the suit's own armour bonus as a second, non-stacking
# term. These are the bonus types that fold; anything else typed (a deflection lining) stays a
# term of its own.
_FOLDS_INTO_ARMOUR = frozenset({"", "material", "armour", "armor", "untyped"})
_WEIGHT_CLASSES = ("light", "medium", "heavy")


# --- the one door to material documents -----------------------------------------------------

def material(material_id: str) -> dict | None:
    """The normalised material document (contract §3), or None.

    Through lane C's `rules/materials.py`, imported lazily: the two lanes are built in
    parallel, and a module that is not there yet must not take the engine down with it. Tests
    replace this function to supply documents of their own.
    """
    if not material_id:
        return None
    try:
        from . import materials as _materials
    except ImportError:
        return None
    try:
        return _materials.get(str(material_id))
    except Exception:  # noqa: BLE001 — a bad document is a problem in the build, not a crash
        return None


def _effects_for(doc: dict, gear: str) -> list[dict]:
    """The effect list a material brings to this kind of gear. A shield reads the material's
    own `shield` list when it has one and its armour list otherwise."""
    if gear == "shield":
        raw = doc.get("shield") or doc.get("armour") or []
    else:
        raw = doc.get(gear) or []
    return [dict(e) for e in raw if isinstance(e, dict)]


def _number(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _toward_zero(x: float) -> int:
    """Rounded toward zero, once. Rounded to six places first, because 1.25 − 2.7 is
    −1.4500000000000002 in floating point and a stray epsilon must never move an integer."""
    return int(math.trunc(round(x, 6)))


def quality_multiplier(quality_index: int) -> float:
    return QUALITY_AT_CRUDE + QUALITY_PER_STEP * max(0, int(quality_index or 0))


def negative_cut(level: int, hardening: int = 0) -> float:
    """What a detrimental modifier is multiplied by: 0.9 per Blacksmith level after the
    first, 0.95 per Hardening pick, never below half (§4.3) — so a negative never vanishes."""
    level = max(1, int(level or 1))
    return max(NEGATIVE_FLOOR, NEGATIVE_CUT_PER_LEVEL ** (level - 1)
               * NEGATIVE_CUT_PER_HARDENING ** max(0, int(hardening or 0)))


def _detrimental(spec: dict, value: float) -> bool:
    """Whether this weighted value leaves the item worse — `effectspec.is_drawback`'s
    direction rule, asked of the weighted number (a half-weight −2 is still a drawback)."""
    if spec.get("type") == "gear_mod":
        better = _effectspec.GEAR_TARGETS.get(str(spec.get("target") or ""), {}).get("better", 1)
        return value * better < 0
    return value < 0


def _key(spec: dict) -> tuple:
    """What two modifiers must share to be summed as one target: the same type and target,
    the same channel, the same bypass and the same `when`. "+2 attack against fey" is not
    "+2 attack", and summing them would hand the fey clause to every swing."""
    return (str(spec.get("type") or ""), str(spec.get("target") or ""),
            str(spec.get("bonus_type") or ""), str(spec.get("bypass") or ""),
            json.dumps(spec.get("when"), sort_keys=True) if spec.get("when") else "")


# --- the build -------------------------------------------------------------------------------

def build(record: dict) -> dict:
    """Everything a forged item does, from its record (contract §4).

    Returns `specs` (the summed modifiers that are not the item's own numbers, plus
    masterwork, the quench mark and finishes, each stamped `origin`), `book` (the main piece's
    printed effects, unscaled), `strikes_as`, `gear` (the item's own numbers as deltas),
    `riders` (trigger-bearing effects), `sum` (the arithmetic, row by row, for the card) and
    `masterwork`. `roll_specs` is what a roll reads: specs plus the book's roll modifiers.
    """
    rec = dict(record or {})
    gear = str(rec.get("gear") or "weapon").strip().lower()
    if gear not in PIECES:
        gear = "weapon"
    item_id = str(rec.get("id") or rec.get("name") or "forged").strip()
    origin = f"item:{item_id}"
    main = MAIN_PIECE[gear]
    smith = rec.get("smith") if isinstance(rec.get("smith"), dict) else {}
    perks = smith.get("perks") if isinstance(smith.get("perks"), dict) else {}
    level = int(smith.get("level", 1) or 1)
    quality_index = int(rec.get("quality_index", 1) if rec.get("quality_index") is not None
                        else 1)
    q_mult = quality_multiplier(quality_index) * (
        1 + POTENCY_PER_PICK * max(0, int(perks.get("potency", 0) or 0)))
    cut = negative_cut(level, int(perks.get("hardening", 0) or 0))

    rows: dict[tuple, dict] = {}
    book: list[dict] = []
    riders: list[dict] = []
    extras: list[dict] = []
    strikes: list[str] = []
    gear_out = {t: 0 for t in GEAR_TARGETS}
    problems: list[str] = []

    pieces = rec.get("pieces") if isinstance(rec.get("pieces"), dict) else {}
    order = list(PIECES[gear]) + [p for p in pieces if p not in PIECES[gear]]
    for slot in order:
        spec = pieces.get(slot)
        if isinstance(spec, str):
            spec = {"material": spec}
        if not isinstance(spec, dict):
            continue
        mid = str(spec.get("material") or "").strip()
        if not mid or mid.lower() == "none":
            continue
        doc = material(mid)
        if doc is None:
            problems.append(f"{slot}: no material called {mid!r}.")
            continue
        passes = max(0, int(spec.get("passes", 0) or 0))
        mult = (MAIN_WEIGHT if slot == main else OTHER_WEIGHT) * STRENGTHEN_PER_PASS ** passes
        for eff in _effects_for(doc, gear):
            kind = str(eff.get("type") or "")
            if eff.get("book"):
                # The book is the main piece's alone, and never scaled (§6.3).
                if slot == main:
                    book.append(dict(eff, origin=origin, source=mid))
                continue
            if eff.get("trigger"):
                riders.append(dict(eff, origin=origin, source=mid))
                continue
            if kind in _NOT_SUMMED:
                if kind == "strikes_as" and slot == main:
                    strikes.append(str(eff.get("target") or ""))
                continue
            value = _number(eff.get("amount"))
            if value is None:
                # A defence or an immunity with no number: the main piece's, unscaled.
                if slot == main:
                    extras.append(dict(eff, origin=origin, source=mid))
                continue
            weighted = value * mult
            row = rows.setdefault(_key(eff), {
                "type": kind, "target": str(eff.get("target") or ""),
                "bonus_type": str(eff.get("bonus_type") or ""),
                "bypass": str(eff.get("bypass") or ""), "when": eff.get("when"),
                "pieces": {p: 0.0 for p in PIECES[gear]},
                "raw_bonus": 0.0, "raw_negative": 0.0, "sources": [],
            })
            row["pieces"][slot] = row["pieces"].get(slot, 0.0) + weighted
            if _detrimental(eff, weighted):
                row["raw_negative"] += weighted
            else:
                row["raw_bonus"] += weighted
            if mid not in row["sources"]:
                row["sources"].append(mid)

    sums: list[dict] = []
    specs: list[dict] = []
    for row in rows.values():
        bonus = row["raw_bonus"] * q_mult
        negative = row["raw_negative"] * cut
        final = _toward_zero(bonus + negative)
        line = {"type": row["type"], "target": row["target"],
                "pieces": {p: round(v, 4) for p, v in row["pieces"].items()},
                "bonus": round(bonus, 4), "negative": round(negative, 4), "final": final}
        if row["when"]:
            line["when"] = row["when"]
        sums.append(line)
        if not final:
            continue
        if row["type"] == "gear_mod":
            if row["target"] in gear_out:
                gear_out[row["target"]] += final
            continue
        out = {"type": row["type"], "target": row["target"], "amount": final,
               "bonus_type": row["bonus_type"] or "material",
               "origin": origin, "source": "+".join(row["sources"])}
        if row["bypass"]:
            out["bypass"] = row["bypass"]
        if row["when"]:
            out["when"] = row["when"]
        specs.append(out)

    # The book's own numbers: gear deltas join the item's numbers, a strike joins the list.
    for eff in book:
        kind = str(eff.get("type") or "")
        if kind == "gear_mod":
            target = str(eff.get("target") or "")
            if target in gear_out:
                gear_out[target] += int(_number(eff.get("amount")) or 0)
        elif kind == "strikes_as":
            strikes.append(str(eff.get("target") or ""))

    masterwork = bool(rec.get("masterwork")) or quality_index >= MASTERWORK_AT
    if masterwork:
        # The book's masterwork: +1 enhancement on attack rolls for a weapon (it does not
        # stack with a magic weapon's enhancement, which is why it is typed), 1 less armour
        # check penalty for armour or a shield. Its own effect, never scaled (§4.4).
        if gear == "weapon":
            specs.append({"type": "combat_mod", "target": "attack", "amount": 1,
                          "bonus_type": "enhancement", "origin": "rule:masterwork",
                          "source": "masterwork", "item": item_id})
        else:
            gear_out["acp"] += 1

    def _unscaled(eff: dict, source: str) -> None:
        kind = str(eff.get("type") or "")
        stamped = dict(eff, origin=origin, source=source)
        if eff.get("trigger"):
            riders.append(stamped)
        elif kind == "strikes_as":
            strikes.append(str(eff.get("target") or ""))
        elif kind == "gear_mod":
            target = str(eff.get("target") or "")
            if target in gear_out:
                gear_out[target] += int(_number(eff.get("amount")) or 0)
        elif kind not in ("working", "narrative"):
            extras.append(stamped)

    quench = str(rec.get("quench") or "").strip()
    if quench:
        doc = material(quench)
        mark = (doc or {}).get("quench_mark")
        if isinstance(mark, dict) and (gear in mark or "weapon" in mark or "armour" in mark) \
                and "type" not in mark:
            mark = mark.get(gear) or (mark.get("armour") if gear == "shield" else None)
        for eff in ([mark] if isinstance(mark, dict) else list(mark or [])):
            if isinstance(eff, dict):
                _unscaled(eff, quench)

    for fin in rec.get("finish") or []:
        fid = str(fin.get("material") if isinstance(fin, dict) else fin or "").strip()
        doc = material(fid)
        if doc is None:
            if fid:
                problems.append(f"finish: no treatment called {fid!r}.")
            continue
        for eff in _effects_for(doc, gear):
            _unscaled(eff, fid)

    for flaw in rec.get("flaws") or []:
        for eff in FLAWS.get(str(flaw).strip().lower(), ()):
            _unscaled(eff, f"flaw:{flaw}")

    # Fold on clean metal (plan §7): the bench marks the piece `folded`, and it is worth +1
    # hardness, fixed and outside the sum like a flaw. On slaggy metal Fold only cancels the
    # flaw, which the bench records by not leaving `slaggy` in the flaws.
    for slot, piece in (rec.get("pieces") or {}).items():
        if isinstance(piece, dict) and piece.get("folded"):
            _unscaled({"type": "gear_mod", "target": "hardness", "amount": 1},
                      f"folded:{slot}")

    specs.extend(extras)
    return {
        "id": item_id, "name": str(rec.get("name") or item_id), "kind": gear,
        "base": str(rec.get("base") or rec.get(gear) or ""),
        "specs": specs, "book": book,
        "strikes_as": sorted({s for s in strikes if s}),
        "gear": gear_out, "riders": riders, "sum": sums, "masterwork": masterwork,
        "quality_index": quality_index,
        "multipliers": {"quality": round(q_mult, 4), "negative_cut": round(cut, 4)},
        "problems": problems,
    }


def preview(pieces: dict, *, gear: str, base: str, quality_index: int, level: int,
            perks: dict | None = None, quench: str | None = None, finish=(), flaws=(),
            masterwork: bool | None = None, item_id: str = "preview",
            name: str = "") -> dict:
    """The build of an item not yet made — what Assemble would give, same shape (§4)."""
    return build({
        "id": item_id, "name": name or item_id, "gear": gear, "base": base,
        "pieces": dict(pieces or {}), "quality_index": quality_index,
        "masterwork": bool(masterwork) if masterwork is not None else False,
        "quench": quench or "", "finish": list(finish or ()), "flaws": list(flaws or ()),
        "smith": {"level": level, "perks": dict(perks or {})},
    })


# --- what readers ask ------------------------------------------------------------------------

def is_forged(record) -> bool:
    """A record made at the new bench: pieces and a gear kind (contract §4). The old
    "Iron Work" records carry flat `specs` instead and are read the old way."""
    return (isinstance(record, dict) and isinstance(record.get("pieces"), dict)
            and str(record.get("gear") or "") in PIECES)


def record_of(thing) -> dict | None:
    """The forged record behind a stock entry or a worn dict, or None."""
    if is_forged(thing):
        return thing
    rec = getattr(thing, "record", None)
    if is_forged(rec):
        return rec
    # The bench keeps a finished item as a plain `crafting.Stock` with its build in
    # `forge.*` tags (no change to crafting.py), and `blacksmith.record` rebuilds the
    # contract §4 record from them. Asked here so every reader that goes through this door
    # finds a forged blade wherever it was stored; without it the readers and the bench were
    # two halves that never met (found when lanes B and D were merged, 2026-10-04).
    if getattr(thing, "craft", None) == "blacksmith" and getattr(thing, "properties", None):
        from . import blacksmith

        try:
            rebuilt = blacksmith.record(thing)
        except Exception:  # noqa: BLE001 - a shelf entry that is not a forge item
            return None
        return rebuilt if is_forged(rebuilt) else None
    return None


_ROLL_EXCLUDED = frozenset({"gear_mod", "strikes_as", "working", "narrative"})


def roll_specs(b: dict) -> list[dict]:
    """The modifiers a roll reads: the summed specs and the book's own roll modifiers.
    Gear numbers, strikes and riders are read by their own readers."""
    out = [dict(s) for s in b.get("specs") or []]
    out += [dict(s) for s in b.get("book") or []
            if str(s.get("type") or "") not in _ROLL_EXCLUDED and not s.get("trigger")]
    return out


def _folds_into_armour(spec: dict) -> bool:
    return (spec.get("type") == "combat_mod" and str(spec.get("target")) == "ac"
            and not spec.get("when")
            and str(spec.get("bonus_type") or "").lower() in _FOLDS_INTO_ARMOUR)


def standing_specs(b: dict) -> list[dict]:
    """What the item adds through the modifier funnel while worn or wielded. An armour
    build's plain AC is NOT here: it is folded into the suit's armour bonus (`armour_row`)."""
    specs = roll_specs(b)
    if b.get("kind") in ("armour", "shield"):
        specs = [s for s in specs if not _folds_into_armour(s)]
    return specs


def armour_row(base: dict, b: dict) -> dict:
    """The ARMOUR table row for a forged suit: the base suit's numbers moved by the build.

    The check penalty never goes above 0 and max Dex and spell failure never below it — the
    book's mithral is "−3 armour check penalty (minimum 0)". `move_weight` is the weight
    class for MOVEMENT only (mithral's "one category lighter for movement"); `weight` itself
    stays the suit's, because proficiency asks it and the book does not let mithral change
    which proficiency a suit needs.
    """
    row = dict(base)
    g = b.get("gear") or {}
    ac_add = sum(int(s.get("amount", 0) or 0) for s in roll_specs(b) if _folds_into_armour(s))
    row["ac"] = max(0, int(base.get("ac", 0) or 0) + ac_add)
    row["acp"] = min(0, int(base.get("acp", 0) or 0) + int(g.get("acp", 0) or 0))
    row["max_dex"] = max(0, int(base.get("max_dex", 99) or 0) + int(g.get("max_dex", 0) or 0))
    row["asf"] = max(0, int(base.get("asf", 0) or 0) + int(g.get("asf", 0) or 0))
    row["lb"] = round(float(base.get("lb", 0) or 0)
                      * max(0.0, 1 + int(g.get("weight_pct", 0) or 0) / 100), 2)
    weight = str(base.get("weight") or "light")
    idx = _WEIGHT_CLASSES.index(weight) if weight in _WEIGHT_CLASSES else 0
    shifted = max(0, min(len(_WEIGHT_CLASSES) - 1, idx + int(g.get("category", 0) or 0)))
    row["move_weight"] = _WEIGHT_CLASSES[shifted]
    row["speed_penalty"] = int(g.get("speed_penalty", 0) or 0)
    row["hardness_delta"] = int(g.get("hardness", 0) or 0)
    row["strikes_as"] = list(b.get("strikes_as") or [])
    row["name"] = b.get("name") or base.get("name")
    row["crafted"] = b.get("id")
    return row


def weapon_row(base: dict, b: dict, record: dict) -> dict:
    """The weapons-table row for a forged weapon: the base weapon, named for the record,
    weighing what the build says, carrying its record and build for the readers."""
    row = dict(base)
    g = b.get("gear") or {}
    if row.get("weight_lb") is not None:
        row["weight_lb"] = round(float(row["weight_lb"] or 0)
                                 * max(0.0, 1 + int(g.get("weight_pct", 0) or 0) / 100), 2)
    row["name"] = str(record.get("name") or b.get("name") or row.get("name"))
    row["crafted_record"] = record
    row["crafted_base"] = str(base.get("id") or b.get("base") or "")
    row["build"] = b
    row["strikes_as"] = list(b.get("strikes_as") or [])
    row["masterwork"] = bool(b.get("masterwork"))
    return row


# --- the record in the pack ------------------------------------------------------------------

@dataclass
class ForgedStock(Stock):
    """A forged record on the shelf.

    `Actor.stock` holds `crafting.Stock` objects, and a Stock has no field for `pieces`, a
    quality index or a smith's perks — so the record of contract §4, put into the pack as a
    plain Stock, would come back from the next save as a name with nothing to compute from.
    This keeps the record whole: the id and name are the record's own, and `as_dict` writes
    the record back exactly (the read-live rule: ids and passes, never numbers), which is what
    `rules/sheet.py`'s loader recognises on the way in.
    """
    record: dict = field(default_factory=dict)

    @property
    def id(self) -> str:  # type: ignore[override]
        return str(self.record.get("id") or super().id)

    @property
    def name(self) -> str:  # type: ignore[override]
        return str(self.record.get("name") or self.base)

    def as_dict(self) -> dict:
        d = dict(self.record)
        d.update({"count": self.count, "kind": d.get("kind") or "crafted",
                  "craft": d.get("craft") or "blacksmith", "crafted": True,
                  "wearable": True})
        return d


def stock_item(record: dict, count: int | None = None) -> ForgedStock:
    """The shelf entry for a forged record — what Assemble puts in the pack with
    `actor.add_stock(forge_items.stock_item(record))`."""
    rec = {k: v for k, v in dict(record).items() if k not in ("crafted", "wearable")}
    gear = str(rec.get("gear") or "weapon")
    base = str(rec.get("base") or "")
    n = int(count if count is not None else rec.get("count", 1) or 1)
    rec["count"] = n
    return ForgedStock(
        base=str(rec.get("name") or rec.get("id") or "Forged item"),
        count=n, craft=str(rec.get("craft") or "blacksmith"), kind="crafted",
        tier=str(rec.get("tier") or "common"),
        slot=str(rec.get("slot") or ("hands" if gear == "weapon" else "armor")),
        wearable=True,
        weapon=base if gear == "weapon" else None,
        armour=base if gear == "armour" else None,
        masterwork=bool(rec.get("masterwork")),
        from_materials=sorted({str((p or {}).get("material") if isinstance(p, dict) else p)
                               for p in (rec.get("pieces") or {}).values() if p}),
        record=rec,
    )


def material_carried_effects(material_id: str) -> list[dict]:
    """The `carried` effects of a raw material in the pack — abysium sickens whoever carries
    it, bar or blade (plan §12.5). Read from both of its lists, once each."""
    doc = material(material_id)
    if not doc:
        return []
    seen, out = set(), []
    for gear in ("weapon", "armour"):
        for eff in _effects_for(doc, gear):
            if str(eff.get("trigger") or "") != "carried":
                continue
            sig = json.dumps(eff, sort_keys=True)
            if sig not in seen:
                seen.add(sig)
                out.append(dict(eff, source=str(material_id)))
    return out


__all__ = ["build", "preview", "material", "is_forged", "record_of", "roll_specs",
           "standing_specs", "armour_row", "weapon_row", "ForgedStock", "stock_item",
           "material_carried_effects", "quality_multiplier", "negative_cut", "PIECES",
           "MAIN_PIECE", "GEAR_TARGETS", "TRIGGERS", "FLAWS"]
