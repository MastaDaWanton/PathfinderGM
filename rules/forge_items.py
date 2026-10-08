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
    # The leatherworker's worn goods — cloak, boots, gloves, bracers, belt, cap
    # (leatherworking plan §13.6, §18.2; contracts §4.2): a body and a lining, read from the
    # hide's `armour` list less the numbers that only mean something on a suit
    # (`WORN_DROPS`).
    "worn": ("body", "lining"),
}
MAIN_PIECE = {"weapon": "head", "armour": "body", "shield": "body", "worn": "body"}
MAKER_KEYS = ("smith", "maker")

# What a worn good leaves out of a hide's armour list (plan §13.6): "AC, ACP, max Dex and
# spell failure are dropped from them (there is no armour bonus to fold into)". The armour
# category and the speed penalty go with them for the same reason — a cloak has no weight
# class to shift and slows nobody as a suit does. A typed AC that is not the armour bonus
# (a deflection lining) is not an armour number and stays.
WORN_DROPS = frozenset({"acp", "max_dex", "asf", "category", "speed_penalty"})

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
# Suits the book names by a piece that is not the body, whose book effects are therefore
# the suit's (leatherworking plan §4.2, §18.5): the book's bone-studded leather is
# studded leather whose STUDS are bone — "1 less AC than metal and 1 less check penalty".
# Measured before (lanes D and E, 2026-10-08): book effects were read from the main piece
# only, so bone studs' −1 AC and +1 check penalty sat in the fastenings and never applied,
# and a bone-studded leather suit came out AC 3 and ACP −1, studded leather's own numbers.
# Keyed by the suit, not by the material: mithral fittings and adamantine buckles carry
# their metal's whole book too, and on a breastplate's fastenings that book is not the
# suit's (the forge's main-piece rule, §6.3, stands everywhere else).
BOOK_PIECES: dict[str, tuple[str, ...]] = {"studded leather": ("fastenings",)}
# Item numbers a book effect may floor (`"minimum"` on a gear_mod): the book's darkleaf
# cloth lowers spell failure by 10% "to a minimum of 5%" (Ultimate Equipment; prior art
# §1.3). Never below what the suit already had: a floor is a limit on the reduction, not
# a penalty on a suit that started under it.
_FLOORED = ("asf", "max_dex")


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
    own `shield` list when it has one and its armour list otherwise; a worn good reads the
    armour list without the suit's own numbers (`WORN_DROPS`, and the AC that would fold
    into an armour bonus it does not have)."""
    if gear == "shield":
        raw = doc.get("shield") or doc.get("armour") or []
    elif gear == "worn":
        raw = [e for e in doc.get("armour") or [] if isinstance(e, dict)
               and not (e.get("type") == "gear_mod" and str(e.get("target")) in WORN_DROPS)
               and not _folds_into_armour(e)]
    else:
        raw = doc.get(gear) or []
    return [dict(e) for e in raw if isinstance(e, dict)]


def _inherited(creature_id: str) -> list[dict]:
    """What a generic hide carries from the beast it was taken off (leatherworking plan §5.4;
    contracts §4.1, §5.2): lane C's `harvest.inherited(creature)`, derived from the stat
    block on read and never stored. Imported lazily, as `material` imports lane D's door:
    built in parallel, a module that is not there yet answers nothing. Every effect comes
    back marked `from_creature` so the build can tell it from a house number."""
    if not creature_id:
        return []
    try:
        from . import harvest as _harvest
    except ImportError:
        return []
    fn = getattr(_harvest, "inherited", None)
    if not callable(fn):
        return []
    try:
        got = fn(str(creature_id)) or []
    except Exception:  # noqa: BLE001 — an unknown beast is a problem in the build, not a crash
        return []
    return [dict(e, from_creature=True) for e in got if isinstance(e, dict)]


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


def _base_weight(gear: str, base: str) -> str:
    """The weight class of the suit the item is built on ("light", "medium", "heavy"), or
    "" — a shield has none in CRB Table 6-6, and a weapon is not armour."""
    if gear != "armour" or not base:
        return ""
    from . import armour as armour_mod
    from .tables import ARMOUR

    kind, key = armour_mod.key_for(base)
    row = ARMOUR.get(key or str(base).strip().lower())
    return str((row or {}).get("weight") or "")


def at_build(eff: dict, gear: str, base: str) -> dict | None:
    """An effect with the clauses the BUILD can answer answered, or None when they fail.

    `when: {"armour": {"weight": "light"}}` is a question about the suit, not about the
    roll: adamantine's book DR is 1/— on light armour, 2/— on medium, 3/— on heavy, and the
    suit's weight class is fixed the moment it is assembled. Measured 2026-10-04 (lane H):
    no reader asked it, so `damage_reduction` met all three rows on an adamantine chain
    shirt and took the best — DR 3/— on a light suit. Answered here, once, so the clause
    is gone from the spec every reader sees: a row that holds keeps the rest of its `when`
    (elysian bronze's attacker clause is the roll's to ask); a row that fails is not on
    the item at all. A shield has no weight class, so an armour-weight row is not on one.
    """
    when = eff.get("when")
    if not isinstance(when, dict) or "armour" not in when:
        return eff
    want = when.get("armour")
    have = _base_weight(gear, base)
    if not isinstance(want, dict) or not have:
        return None
    for field_name, value in want.items():
        if field_name != "weight":
            return None                     # a clause nothing can answer is dropped
        wanted = value if isinstance(value, (list, tuple)) else [value]
        if have not in [str(v).strip().lower() for v in wanted]:
            return None
    rest = {k: v for k, v in when.items() if k != "armour"}
    out = {k: v for k, v in eff.items() if k != "when"}
    if rest:
        out["when"] = rest
    return out


def _key(spec: dict) -> tuple:
    """What two modifiers must share to be summed as one target: the same type and target,
    the same channel, the same bypass and the same `when`. "+2 attack against fey" is not
    "+2 attack", and summing them would hand the fey clause to every swing."""
    return (str(spec.get("type") or ""), str(spec.get("target") or ""),
            str(spec.get("bonus_type") or ""), str(spec.get("bypass") or ""),
            json.dumps(spec.get("when"), sort_keys=True) if spec.get("when") else "")


# --- the build -------------------------------------------------------------------------------

def _parts_label(parts, made: str = "forged") -> str:
    """The roll term's words for a summed row: which forged pieces it comes from, "forged
    iron head" or "forged ash haft and brass guard".

    Every summed spec used to reach a roll under the item's name alone, so a Superior iron
    longsword's damage read "+4 Superior Iron Longsword" beside the Str term (the final
    pass, 2026-10-06, read off `damage_modifiers` with the sword in hand). Measured, it is no
    double count: it is the forge's own house number for the iron head, 2 x 1.5 for its one
    strengthening pass x 1.5 for Superior = 4.5, toward zero 4, and the only damage term the
    sword adds. It needed naming, not removing. The sheet's reader takes a spec's `label`
    before the item's name (`Actor._standing_mods`)."""
    words = []
    for slot, mid in parts:
        doc = material(mid) or {}
        name = str(doc.get("name") or mid.replace("-", " ")).lower()
        # "Ash Haft" and "Brass Guard" already say the piece; "Iron" does not.
        piece = slot if not any(w in name.split() for w in
                                ("haft", "guard", "grip", "pommel", "head", "blade", "body",
                                 "lining", "fastenings", "buckle", "rivets", "straps")) else ""
        words.append(f"{name} {piece}".strip())
    if not words:
        return ""
    return f"{made} " + (words[0] if len(words) == 1
                        else ", ".join(words[:-1]) + " and " + words[-1])


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
    base_key = str(rec.get("base") or rec.get(gear) or "")
    main = MAIN_PIECE[gear]
    # The maker's level and perks under either key (contracts §4.2): writers use "smith"
    # for now, and a tanner's record may say "maker".
    smith = next((rec[k] for k in MAKER_KEYS if isinstance(rec.get(k), dict)), {})
    perks = smith.get("perks") if isinstance(smith.get("perks"), dict) else {}
    level = int(smith.get("level", 1) or 1)
    quality_index = int(rec.get("quality_index", 1) if rec.get("quality_index") is not None
                        else 1)
    q_mult = quality_multiplier(quality_index) * (
        1 + POTENCY_PER_PICK * max(0, int(perks.get("potency", 0) or 0)))
    cut = negative_cut(level, int(perks.get("hardening", 0) or 0))
    # The roll term's verb (`_parts_label`): a tanner's wolf pelt is not "forged".
    made = "worked" if str(rec.get("craft") or "") == "leatherworker" else "forged"

    rows: dict[tuple, dict] = {}
    book: list[dict] = []
    riders: list[dict] = []
    extras: list[dict] = []
    strikes: list[str] = []
    gear_out = {t: 0 for t in GEAR_TARGETS}
    problems: list[str] = []

    pieces = rec.get("pieces") if isinstance(rec.get("pieces"), dict) else {}
    order = list(PIECES[gear]) + [p for p in pieces if p not in PIECES[gear]]
    # The leatherworker's readers (leatherworking contracts §4.2, plan §13.4, §15, §5.4):
    always_masterwork = False
    as_base = ""
    inherited: list[tuple[dict, str]] = []
    book_slots = (BOOK_PIECES.get(_armour_key_of(base_key)[1] or base_key.strip().lower(), ())
                  if gear == "armour" and base_key else ())
    for slot in order:
        spec = pieces.get(slot)
        if isinstance(spec, str):
            spec = {"material": spec}
        if not isinstance(spec, dict):
            continue
        mid = str(spec.get("material") or "").strip()
        if not mid or mid.lower() == "none":
            continue
        if spec.get("plain"):
            # A piece the record names and the item does not count: plan §14's migrated
            # "Iron Work", whose haft and fittings the old bench never recorded and which
            # default to plain ash and iron "at value 0". Named so the card can say what
            # it is made of; not summed, because nobody chose those pieces.
            continue
        doc = material(mid)
        if doc is None:
            problems.append(f"{slot}: no material called {mid!r}.")
            continue
        if slot == main:
            # The book's "always masterwork" hides (dragonhide, eel hide, angelskin,
            # darkleaf: plan §13.4, Q3.4). Measured before (inventory §0.7): a dragonhide
            # suit was not masterwork without the Tool step, which the book never asks.
            always_masterwork = doc.get("always_masterwork") is True
            allowed = [str(b).strip().lower() for b in doc.get("allowed_bases") or () if b]
            if allowed and gear in ("armour", "shield"):
                _, have = _armour_key_of(base_key)
                if (have or base_key.strip().lower()) not in allowed:
                    problems.append(
                        f"{slot}: {doc.get('name') or mid} is made only into "
                        f"{_listed(allowed)}, not {base_key or 'nothing'} (the book's own "
                        f"limit).")
        # What a generic hide carries from its beast (plan §5.4): the stock's `creature`,
        # copied onto the piece by the bench, read live through lane C. Collected for the
        # one rule below, never summed.
        if spec.get("creature"):
            inherited += [(e, slot) for e in _inherited(str(spec["creature"]))]
        passes = max(0, int(spec.get("passes", 0) or 0))
        mult = (MAIN_WEIGHT if slot == main else OTHER_WEIGHT) * STRENGTHEN_PER_PASS ** passes
        for eff in _effects_for(doc, gear):
            eff = at_build(eff, gear, base_key)
            if eff is None:
                continue
            kind = str(eff.get("type") or "")
            if kind == "as_base":
                # Bulette leather "has the same statistics as studded leather" (plan
                # §14.5): the main piece's word, read by `armour_row`. The row's metal is
                # not carried with it — the material tag reads the pieces, and no piece
                # here is metal.
                if slot == main and gear == "armour":
                    want = str(eff.get("target") or "").strip().lower()
                    from .tables import ARMOUR as _ARMOUR

                    if want in _ARMOUR and want != "none":
                        as_base = want
                    else:
                        problems.append(f"{slot}: {doc.get('name') or mid} names no armour "
                                        f"row called {want!r} to take statistics from.")
                if eff.get("book") and slot == main:
                    book.append(dict(eff, origin=origin, source=mid))
                continue
            if eff.get("from_creature"):
                # A creature's own DR or resistance on a named hide: the one rule below.
                inherited.append((eff, slot))
                continue
            if eff.get("book"):
                # The book is the main piece's alone, and never scaled (§6.3) — save on a
                # suit the book names by another piece (`BOOK_PIECES`: bone studs).
                if slot == main or slot in book_slots:
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
            if (slot, mid) not in row.setdefault("parts", []):
                row["parts"].append((slot, mid))

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
               "origin": origin, "source": "+".join(row["sources"]),
               "label": _parts_label(row.get("parts") or (), made)}
        if row["bypass"]:
            out["bypass"] = row["bypass"]
        if row["when"]:
            out["when"] = row["when"]
        specs.append(out)

    # The book's own numbers: gear deltas join the item's numbers, a strike joins the list.
    floors: dict[str, int] = {}
    for eff in book:
        kind = str(eff.get("type") or "")
        if kind == "gear_mod":
            target = str(eff.get("target") or "")
            if target in gear_out:
                gear_out[target] += int(_number(eff.get("amount")) or 0)
            low = _number(eff.get("minimum"))
            if target in _FLOORED and low is not None:
                floors[target] = max(floors.get(target, 0), int(low))
        elif kind == "strikes_as":
            strikes.append(str(eff.get("target") or ""))

    masterwork = (bool(rec.get("masterwork")) or quality_index >= MASTERWORK_AT
                  or always_masterwork)
    if masterwork:
        # The book's masterwork: +1 enhancement on attack rolls for a weapon (it does not
        # stack with a magic weapon's enhancement, which is why it is typed), 1 less armour
        # check penalty for armour or a shield. Its own effect, never scaled (§4.4). A worn
        # good has no check penalty to lighten.
        if gear == "weapon":
            specs.append({"type": "combat_mod", "target": "attack", "amount": 1,
                          "bonus_type": "enhancement", "origin": "rule:masterwork",
                          "source": "masterwork", "item": item_id})
        elif gear in ("armour", "shield"):
            gear_out["acp"] += 1

    def _unscaled(eff: dict, source: str) -> None:
        eff = at_build(eff, gear, base_key)
        if eff is None:
            return
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

    # A hide's DR and energy resistance INHERITED FROM ITS CREATURE (`from_creature`, lane
    # C's mark; leatherworking plan §5.4 and open point 6, the owner's "reduced DR",
    # 2026-10-08: DR max(1, N/5)/x on a rare-and-up hide) apply whole and once, when the
    # hide is the main piece — the suit's body, a worn good's whole — and never from a
    # lining or fastenings. Measured before this rule (tests/test_leather_items.py): the
    # forge's sum SCALES such a number, so a DR 1/silver hide body at Crude came out
    # 1 x 0.75 = 0.75, toward zero 0, and as a lining 1 x 0.5 = 0 at any quality below
    # +3 — the owner's floor of 1 rounded away to nothing. Hand-written house DR and
    # resistance on the material documents keep the forge's maths. Laminate's passes do not
    # multiply it either: the beast's hide resists what the beast resisted.
    seen_inherited: set[str] = set()
    for eff, slot in inherited:
        if slot != main:
            continue
        sig = json.dumps({k: v for k, v in eff.items() if k not in ("origin", "source")},
                         sort_keys=True)
        if sig in seen_inherited:
            continue
        seen_inherited.add(sig)
        src = str((pieces.get(main) or {}).get("creature") or "") if isinstance(
            pieces.get(main), dict) else ""
        _unscaled(dict(eff, from_creature=True),
                  f"creature:{src}" if src else str(eff.get("source") or "creature"))

    specs.extend(extras)
    out = {
        "id": item_id, "name": str(rec.get("name") or item_id), "kind": gear,
        "base": str(rec.get("base") or rec.get(gear) or ""),
        "specs": specs, "book": book,
        "strikes_as": sorted({s for s in strikes if s}),
        "gear": gear_out, "riders": riders, "sum": sums, "masterwork": masterwork,
        "always_masterwork": always_masterwork, "as_base": as_base,
        "floors": floors,
        "quality_index": quality_index,
        "multipliers": {"quality": round(q_mult, 4), "negative_cut": round(cut, 4)},
        "problems": problems,
    }
    # The enchanter's layer (enchanting contracts §3.2), merged into the lists every
    # reader already reads — specs into the funnel, the DR traits into `strikes_as` — so
    # a +1 sword needs no second door. The whole layer rides under "magic" for the readers
    # that need more (bane's raise, powers, wielded and worn effects, riders). A record
    # with no layer gets no key and builds exactly as it did (tests/test_magic_layer.py
    # pins the equality).
    #
    # Riders are NOT merged into `riders`, though §3.2 first said so. Measured 2026-10-05:
    # `Engine._item_riders` turns a rider into a damage intent through
    # `consumables._spec_to_intents`, which never asks the rider's `when`, so a merged bane
    # rider put its +2d6 on every foe — the exact defect bane's `when` exists to close —
    # and its tell named "the property:bane". Lane C reads `build["magic"]["riders"]`
    # (contracts §4) with the `when` asked. Specs are safe to merge: `_standing_mods` asks
    # every spec's `when` (`_when_holds`).
    from . import magic_layer

    if magic_layer.has_layer(rec):
        lay = magic_layer.layer(rec)
        out["magic"] = lay
        out["specs"] = specs + [dict(s) for s in lay["specs"]]
        out["strikes_as"] = sorted(set(out["strikes_as"]) | set(lay["strikes_as"]))
        out["problems"] = problems + [f"magic: {p}" for p in lay["problems"]]
    out["object_immunity"] = object_immunities(out)
    return out


def object_immunities(b: dict) -> list[str]:
    """The energies the ITEM itself takes no damage from (`object_immunity`, leatherworking
    plan §15, §18.4): dragonhide's book power, "the armour is immune ... although this does
    not confer any protection to the wearer". Read off the build's book (the main piece's
    printed effects) and its other specs, sorted. Asked by `Actor.damage_item`, the one
    door every sunder, acid splash and fireball on gear goes through."""
    from .tables import ENERGY_DAMAGE

    out: set[str] = set()
    for s in list(b.get("book") or ()) + list(b.get("specs") or ()):
        if isinstance(s, dict) and s.get("type") == "object_immunity":
            t = str(s.get("target") or "").strip().lower()
            if t in ENERGY_DAMAGE:
                out.add(t)
    return sorted(out)


def _armour_key_of(base: str) -> tuple[str, str]:
    from . import armour as armour_mod

    return armour_mod.key_for(base)


def _listed(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " or " + words[-1]


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
        if not is_forged(rebuilt):
            return None
        # A forge item kept as a plain Stock keeps its magic layer on the Stock's own
        # `magic` field (lane G's, contracts §8.1), since its record is rebuilt from tags
        # that know nothing of magic. Without this the layer would be on the shelf and in
        # no build: the old enchanter's dropped-build defect, by a different road.
        magic = getattr(thing, "magic", None)
        if isinstance(magic, dict) and magic:
            import copy as _copy

            rebuilt["magic"] = _copy.deepcopy(magic)
        return rebuilt
    return None


def record_for_base(base: str, *, gear: str, quality_index: int = 3,
                    pieces: dict | None = None, item_id: str | None = None,
                    name: str | None = None) -> dict:
    """A contracts §4 record for an item nobody forged — bought, looted, a stat block's
    sword — so it can carry a magic layer (enchanting plan §6.2: "a record is made for it
    on first touch") and answer the material tag.

    Its pieces are the base's defaults from `content/rules/base-pieces.json`, marked
    `plain` as the forge migration marks the pieces nobody chose (`blacksmith.
    MIGRATED_PLAIN`): named, so the card and the material tag can say what it is made of,
    and never summed, because a bought longsword is the book's longsword and the forge's
    house numbers are for metal somebody worked. Pieces the caller names (a bought cold
    iron blade: `{"head": "cold-iron"}`) replace those defaults and are not plain.

    Refuses (ValueError) a base the tables do not know or a gear it is not.
    """
    from . import armour as armour_mod
    from . import item_tags
    from .worldclass import quality_name

    gear = str(gear or "").strip().lower()
    if gear not in PIECES:
        raise ValueError(f"gear must be one of {', '.join(PIECES)}, not {gear!r}.")
    if gear == "weapon":
        key = item_tags.weapon_key(base)
        printed = key
        if key:
            from . import weapons as weapons_mod

            printed = str(weapons_mod.get(key).get("name") or key)
    else:
        kind, key = armour_mod.key_for(base)
        if kind != gear:
            key = ""
        printed = str(armour_mod.row(gear, key).get("name") or key) if key else ""
    defaults = item_tags.default_pieces(key, gear) if key else None
    if not key or defaults is None:
        raise ValueError(f"No {gear} called {base!r} in the tables.")
    made = {slot: {"material": mid, "passes": 0, "plain": True}
            for slot, mid in defaults.items()}
    for slot, spec in (pieces or {}).items():
        mid = spec if isinstance(spec, str) else (spec or {}).get("material")
        if mid:
            made[slot] = {"material": str(mid).strip().lower(),
                          "passes": int((spec or {}).get("passes", 0) or 0)
                          if isinstance(spec, dict) else 0}
    q = int(quality_index)
    label = name or f"{quality_name(q)} {printed}"
    rid = item_id or "-".join("".join(ch if ch.isalnum() else " " for ch in label.lower())
                              .split())
    return {
        "id": rid, "name": label,
        "kind": "crafted", "craft": "bought", "count": 1,
        "gear": gear, "base": key,
        "slot": {"weapon": "hands", "shield": "shield"}.get(gear, "armor"),
        "quality": quality_name(q).lower(), "quality_index": q,
        "masterwork": q >= MASTERWORK_AT,
        "pieces": made, "quench": None, "finish": [], "flaws": [],
        "smith": {"level": 1, "perks": {}},
    }


# `object_immunity` and `as_base` are about the item, never a roll: read by
# `object_immunities` and `armour_row`.
_ROLL_EXCLUDED = frozenset({"gear_mod", "strikes_as", "working", "narrative",
                            "object_immunity", "as_base"})


def roll_specs(b: dict) -> list[dict]:
    """The modifiers a roll reads: the summed specs and the book's own roll modifiers.
    Gear numbers, strikes and riders are read by their own readers."""
    out = [dict(s) for s in b.get("specs") or []
           if str(s.get("type") or "") not in ("object_immunity", "as_base")]
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
    as_base = str(b.get("as_base") or "")
    if as_base:
        # Bulette leather (plan §14.5): the named row's statistics replace the suit's own
        # — armour bonus, max Dex, check penalty, spell failure, weight and class — and
        # the build moves those. Its name and donning stay the suit's, and its metal is the
        # pieces' (`item_tags`), never the row's: a bulette suit is studded leather's
        # numbers with no studs.
        from .tables import ARMOUR as _ARMOUR

        stats = _ARMOUR.get(as_base) or {}
        for k in ("ac", "max_dex", "acp", "asf", "lb", "weight"):
            if k in stats:
                row[k] = stats[k]
        row["as_base"] = as_base
        base = row
    g = b.get("gear") or {}
    ac_add = sum(int(s.get("amount", 0) or 0) for s in roll_specs(b) if _folds_into_armour(s))
    row["ac"] = max(0, int(base.get("ac", 0) or 0) + ac_add)
    row["acp"] = min(0, int(base.get("acp", 0) or 0) + int(g.get("acp", 0) or 0))
    row["max_dex"] = max(0, int(base.get("max_dex", 99) or 0) + int(g.get("max_dex", 0) or 0))
    row["asf"] = max(0, int(base.get("asf", 0) or 0) + int(g.get("asf", 0) or 0))
    for target, low in (b.get("floors") or {}).items():
        # A book floor (darkleaf: spell failure "to a minimum of 5%"), never above what
        # the suit had before the material: padded's 5% stays 5%, leather's 10% stops at
        # 5%. Measured before: a darkleaf leather suit computed 10 - 10 = 0%.
        if target in _FLOORED and target in row:
            had = int(base.get(target, 0) or 0)
            row[target] = max(int(row[target]), min(had, int(low)))
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
        # A shield goes in the shield slot (contracts §12 item 6): the old default put a
        # forged buckler in the armour slot, where it would have been read as a suit.
        # A worn good has no default: a cloak and a pair of boots are the record's to say
        # (`Actor.wear` refuses a slot it does not know, rather than guessing "armor").
        slot=str(rec.get("slot") or {"weapon": "hands", "shield": "shield",
                                     "worn": ""}.get(gear, "armor")),
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


__all__ = ["build", "preview", "material", "is_forged", "record_of", "record_for_base",
           "object_immunities", "WORN_DROPS",
           "roll_specs",
           "standing_specs", "armour_row", "weapon_row", "ForgedStock", "stock_item",
           "material_carried_effects", "quality_multiplier", "negative_cut", "PIECES",
           "MAIN_PIECE", "GEAR_TARGETS", "TRIGGERS", "FLAWS"]
