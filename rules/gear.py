"""What carried gear does: the reader for content/rules/gear.json.

Asked for by the owner, 2026-10-01: *"I have items like hemp, flint and steel, tent, trail
rations and so on. They are listed as having no effect. but they should have effects: a
tent should decrease the chance of being attacked in my sleep and protect me from the
elements to a degree. A bedroll should negate the negative of waking up fatigued after
sleeping on the floor or ground and a degree of protection from the cold. a blanket is a
degree of protection from the cold. trail rations reset my hunger, a backpack allows me to
carry more than a couple of things / increases my carry weight. ink and paper allow me to
write notes or draw maps using ink and paper."*

Measured before this module, on the owner's own save (Sam, 2026-10-01): nine of the ten
things in the pack — backpack, bedroll, blanket, hemp rope, ink and paper, trail rations,
tent, flint and steel, traveler's outfit — drew "for show, no effect in play" on the
Equipment tab, because a bought good lands in `stock` as a jar with no `specs`, and a jar
with no specs is, to every reader in the app, nothing.

**Effects as documents, never as item names in engine code.** A row in gear.json says
what a thing does in the grammar the engine already reads: feat-shaped `modifiers` with a
`when` (the bedroll's +2 against cold applies only to a roll whose context says cold and
resting), standing `tags` under `gear.*` asked with `has_state("gear.bedding")`, and four
small verbs (`eat`, `carry`, `camp`, `writes`). The engine asks the vocabulary, not the
name: the sleeping-rough rule spares whoever holds `gear.bedding`, whatever it is called.

**The pack is the store** (the stage 8 ruling for feats, applied to gear): nothing is
copied onto the sheet. `Actor._gear_mods` reads the carried rows on every roll the way
`_feat_mods` reads the feat list, so selling the blanket takes its term away with nothing
to clean up — Foundry v11 abandoned the copied-effect-with-a-pointer shape for exactly the
drift that copying invites (docs/states-effects-tells.md).

**What the book gives and what this table gives are kept apart.** 1e prints rules text for
the rope, the flint and steel and the masterwork backpack; it prints none for the tent,
the bedroll or the blanket. Every number the book does not print is a row's
`house_rule`, quoting the owner's words, and the Equipment tab shows the words.

Carrying capacity is the Core Rulebook's Table 7-4 by Strength and size, read here because
the backpack needs something to raise. Load penalties (Table 7-5) are NOT applied: the
owner ruled encumbrance a later batch (docs/playtest-2026-09-30-findings.md, E9), so the
capacity is shown on the Equipment tab and nothing is slowed by it yet.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_DOC: dict | None = None

# The verbs a row may carry beside the feat grammar. Anything else is refused by
# `validate`, because the reader would ignore it and the row would be a promise.
ROW_KEYS = frozenset({"names", "does", "source", "house_rule", "modifiers", "tags", "eat",
                      "carry", "camp", "writes", "not_yet"})
MOD_KEYS = frozenset({"type", "target", "amount", "bonus_type", "when", "note"})
CAMP_KEYS = frozenset({"night_check_scale"})


def doc() -> dict:
    """The whole document, read once: it ships in the install, never in the user's data,
    so there is no stale copy to outlive a reinstall (the hazards reader does the same)."""
    global _DOC
    if _DOC is None:
        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "rules" / "gear.json"
        _DOC = json.loads(path.read_text(encoding="utf-8"))
    return _DOC


def items() -> dict[str, dict]:
    return {k: v for k, v in (doc().get("items") or {}).items() if not str(k).startswith("_")}


def camp_rule(rule_id: str) -> dict:
    return dict((doc().get("camp") or {}).get(rule_id) or {})


def _norm(name) -> str:
    return " ".join(str(name or "").lower().split())


_NAMES: dict[str, str] | None = None


def _by_name() -> dict[str, str]:
    # Built once with the document: `carried` runs inside every roll's modifier funnel.
    global _NAMES
    if _NAMES is None:
        out: dict[str, str] = {}
        for key, row in items().items():
            for n in [key, *(row.get("names") or ())]:
                out.setdefault(_norm(n), key)
        _NAMES = out
    return _NAMES


def row_for(name) -> tuple[str, dict] | tuple[None, None]:
    """The row a carried thing's name is, by exact name (lower-cased, spaces folded): the
    names a counter sells it under and the ones the fiction hands it over by. Never a
    substring — "rope dart" is a weapon, not a rope."""
    key = _by_name().get(_norm(name))
    if key is None:
        return None, None
    return key, items()[key]


def does(name) -> str:
    """The Equipment tab's words for this thing, or "" when it has no row."""
    _, row = row_for(name)
    return str((row or {}).get("does") or "")


def carried(actor) -> list[dict]:
    """Every carried thing that has a row: [{"key", "row", "name", "count", "where",
    "id"}]. Reads both stores a thing can be in — a counter's purchases in `stock`, the
    fiction's handovers in `goods` — because the owner's bedroll was bought and the next
    player's may be found."""
    out = []
    for sid, s in (getattr(actor, "stock", None) or {}).items():
        if int(getattr(s, "count", 0) or 0) <= 0:
            continue
        key, row = row_for(getattr(s, "base", "") or getattr(s, "name", ""))
        if key:
            out.append({"key": key, "row": row, "name": str(s.name), "count": int(s.count),
                        "where": "stock", "id": sid})
    for name, n in (getattr(actor, "goods", None) or {}).items():
        if int(n or 0) <= 0:
            continue
        key, row = row_for(name)
        if key:
            out.append({"key": key, "row": row, "name": str(name), "count": int(n),
                        "where": "goods", "id": str(name)})
    return out


def holds(actor, key: str) -> bool:
    return any(c["key"] == key for c in carried(actor))


def tags(actor) -> tuple[str, ...]:
    """The standing tags carried gear grants (`gear.bedding`, `gear.shelter`, ...), for
    `Actor.standing_tags`."""
    out: list[str] = []
    for c in carried(actor):
        for t in c["row"].get("tags") or ():
            if t not in out:
                out.append(str(t))
    return tuple(out)


def modifier_specs(actor, kind: str, target: str) -> list[tuple[str, dict]]:
    """(the item's name, the spec) for every carried row's modifier on this channel.
    One row once, however many of it are carried: two blankets are not twice as warm
    (1e: circumstance bonuses from the same source do not stack)."""
    want = str(target).lower()
    out, seen = [], set()
    for c in carried(actor):
        if c["key"] in seen:
            continue
        seen.add(c["key"])
        for spec in c["row"].get("modifiers") or ():
            if spec.get("type") == kind and str(spec.get("target", "")).lower() == want:
                out.append((c["key"], spec))
    return out


def carry_bonus(actor) -> tuple[int, str]:
    """(how much higher Strength counts for carrying, the thing that does it). The best
    one, not a sum: two backpacks on one back are still one."""
    best, by = 0, ""
    for c in carried(actor):
        n = int((c["row"].get("carry") or {}).get("str", 0) or 0)
        if n > best:
            best, by = n, c["key"]
    return best, by


def night_scale(actor) -> tuple[float, str]:
    """(what the night's encounter chance is multiplied by, the thing that does it)."""
    best, by = 1.0, ""
    for c in carried(actor):
        x = (c["row"].get("camp") or {}).get("night_check_scale")
        if x is not None and float(x) < best:
            best, by = float(x), c["key"]
    return best, by


def can_write(actor) -> tuple[bool, str]:
    """Whether this character has what writing takes, and the reason when not."""
    if any(c["row"].get("writes") for c in carried(actor)):
        return True, ""
    return False, ("Writing a note or drawing a map takes ink and paper, and "
                   f"{getattr(actor, 'name', 'you')} carries none. A general store sells "
                   f"them.")


def food(actor, said: str = "") -> dict | None:
    """The carried thing to eat for `said` (an id, a name, or empty for "something to
    eat"), or None. Trail rations first when nothing is named: they are what a pack is
    provisioned with."""
    pool = [c for c in carried(actor) if c["row"].get("eat")]
    if not pool:
        return None
    want = _norm(said)
    if want:
        for c in pool:
            if want in (_norm(c["id"]), _norm(c["name"]), c["key"]):
                return c
        key, _ = row_for(want)
        hit = [c for c in pool if c["key"] == key]
        if hit:
            return hit[0]
        words = [w for w in re.findall(r"[a-z]+", want) if len(w) > 2]
        hit = [c for c in pool if words and all(w in _norm(c["name"]) for w in words)]
        return hit[0] if len(hit) == 1 else None
    pool.sort(key=lambda c: (c["key"] != "trail rations", c["name"]))
    return pool[0]


def spend(actor, c: dict, n: int = 1) -> int:
    """Take `n` of a carried thing out of whichever store it is in; how many are left."""
    if c["where"] == "stock":
        actor.take_stock(c["id"], n)
        s = (actor.stock or {}).get(c["id"])
        return int(getattr(s, "count", 0) or 0) if s is not None else 0
    left = int(actor.goods.get(c["id"], 0) or 0) - n
    if left <= 0:
        actor.goods.pop(c["id"], None)
        return 0
    actor.goods[c["id"]] = left
    return left


# --- carrying capacity (CRB Table 7-4) ------------------------------------------------------
#
# The upper bound of each load, light / medium / heavy, for Strength 1 to 29 — read from
# the PRD's own table (legacy.aonprd.com/coreRulebook/additionalRules.html, 2026-10-01).
CAPACITY: dict[int, tuple[int, int, int]] = {
    1: (3, 6, 10), 2: (6, 13, 20), 3: (10, 20, 30), 4: (13, 26, 40), 5: (16, 33, 50),
    6: (20, 40, 60), 7: (23, 46, 70), 8: (26, 53, 80), 9: (30, 60, 90),
    10: (33, 66, 100), 11: (38, 76, 115), 12: (43, 86, 130), 13: (50, 100, 150),
    14: (58, 116, 175), 15: (66, 133, 200), 16: (76, 153, 230), 17: (86, 173, 260),
    18: (100, 200, 300), 19: (116, 233, 350), 20: (133, 266, 400), 21: (153, 306, 460),
    22: (173, 346, 520), 23: (200, 400, 600), 24: (233, 466, 700), 25: (266, 533, 800),
    26: (306, 613, 920), 27: (346, 693, 1040), 28: (400, 800, 1200), 29: (466, 933, 1400),
}
# "Larger and Smaller Creatures: ... bipeds: Fine x1/8, Diminutive x1/4, Tiny x1/2, Small
# x3/4, Medium x1, Large x2, Huge x4, Gargantuan x8, Colossal x16."
SIZE_FACTOR = {"fine": 0.125, "diminutive": 0.25, "tiny": 0.5, "small": 0.75, "medium": 1.0,
               "large": 2.0, "huge": 4.0, "gargantuan": 8.0, "colossal": 16.0}


def capacity(strength: int, size: str = "medium") -> tuple[int, int, int]:
    """The light, medium and heavy load limits in pounds. Above 29, the book's Tremendous
    Strength rule: the row 20–29 with the same last digit, times 4 for every ten above it."""
    s = max(0, int(strength))
    if s <= 0:
        base = (0, 0, 0)
    elif s <= 29:
        base = CAPACITY[s]
    else:
        row = 20 + s % 10
        times = 4 ** ((s - row) // 10)
        base = tuple(x * times for x in CAPACITY[row])
    f = SIZE_FACTOR.get(str(size or "medium").lower(), 1.0)
    return tuple(int(x * f) for x in base)


def _good_weight(name: str, count: int) -> float | None:
    """A general-store good's weight for `count` of it (counted in its unit), or None."""
    from .goods import GEAR

    low = _norm(name)
    for row in GEAR.values():
        if _norm(row["name"]) == low and row.get("lb") is not None:
            return float(row["lb"]) * int(count) / max(1, int(row.get("per", 1) or 1))
    return None


def load(actor) -> dict:
    """What this character carries, in pounds, against what they can.

    Counted: weapons, ammunition, armour and shields (their tables' weights) and the general
    store's goods (`goods.GEAR` carries the CRB weights). Clothes are worn and not counted.
    Anything else is listed in `unknown` rather than guessed at."""
    from . import weapons as weapons_mod
    from .tables import ARMOUR, SHIELDS

    lb = 0.0
    unknown: list[str] = []
    for w in getattr(actor, "weapons", None) or ():
        k = weapons_mod.key_for(w) or ""
        if not k or k == "unarmed":
            continue
        lb += float(weapons_mod.all_weapons()[k].get("weight_lb") or 0)
    for attr, table in (("armour", ARMOUR), ("shield", SHIELDS)):
        key = str(getattr(actor, attr, "none") or "none").lower()
        if key != "none" and key in table:
            lb += float(table[key].get("lb") or 0)
    for name, n in (getattr(actor, "goods", None) or {}).items():
        n = int(n or 0)
        if n <= 0:
            continue
        low = _norm(name)
        if "outfit" in low or "clothes" in low:
            continue
        if weapons_mod.is_ammunition(name):
            k = weapons_mod.key_for(name)
            lb += float(weapons_mod.all_weapons()[k].get("weight_lb") or 0) * n \
                / max(1, weapons_mod.rounds_per(k))
            continue
        if low in ARMOUR or low in SHIELDS:
            lb += float((ARMOUR.get(low) or SHIELDS.get(low) or {}).get("lb") or 0) * n
            continue
        got = _good_weight(name, n)
        if got is None:
            unknown.append(str(name))
        else:
            lb += got
    for s in (getattr(actor, "stock", None) or {}).values():
        n = int(getattr(s, "count", 0) or 0)
        base = str(getattr(s, "base", "") or "")
        if n <= 0 or "outfit" in base.lower():
            continue
        got = _good_weight(base, n)
        if got is None:
            unknown.append(str(s.name))
        else:
            lb += got
    strength = int(actor.ability_score("str")) if hasattr(actor, "ability_score") else 10
    bonus, by = carry_bonus(actor)
    light, medium, heavy = capacity(strength + bonus, getattr(actor, "size", "medium"))
    lb = round(lb, 1)
    band = ("light" if lb <= light else "medium" if lb <= medium
            else "heavy" if lb <= heavy else "over")
    return {"lb": lb, "light": light, "medium": medium, "heavy": heavy, "band": band,
            "str": strength, "str_bonus": bonus, "str_bonus_from": by,
            "unknown": sorted(set(unknown)), "enforced": False}


def validate(d: dict | None = None) -> list[str]:
    """Everything wrong with the document, each with the fix named — the classbuilder's
    style, and the same modifier vocabulary (`classbuilder.validate_effect`)."""
    from .classbuilder import validate_effect

    d = doc() if d is None else d
    problems: list[str] = []
    for key, row in (d.get("items") or {}).items():
        at = f"gear.{key}"
        if not isinstance(row, dict):
            problems.append(f"{at}: a row is an object.")
            continue
        extra = sorted(set(row) - ROW_KEYS)
        if extra:
            problems.append(f"{at}: unknown field(s) {', '.join(extra)}; the reader would "
                            f"ignore them. A row carries: {', '.join(sorted(ROW_KEYS))}.")
        if not str(row.get("does") or "").strip():
            problems.append(f"{at}.does: say in words what it does — the Equipment tab "
                            f"prints this instead of 'no effect'.")
        for i, spec in enumerate(row.get("modifiers") or ()):
            mat = f"{at}.modifiers[{i}]"
            bad = sorted(set(spec) - MOD_KEYS)
            if bad:
                problems.append(f"{mat}: unknown key(s) {', '.join(bad)}. A modifier "
                                f"carries: {', '.join(sorted(MOD_KEYS))}.")
            if not isinstance(spec.get("amount"), int):
                problems.append(f"{mat}.amount: a whole number, written here — a model "
                                f"never supplies it.")
            probe = {k: v for k, v in spec.items() if k in ("type", "target", "amount",
                                                            "bonus_type", "note")}
            problems.extend(validate_effect(probe, mat, ()))
            if "when" in spec and not isinstance(spec["when"], dict):
                problems.append(f"{mat}.when: an object, like {{\"against\": \"cold\"}}.")
        for t in row.get("tags") or ():
            if not str(t).startswith("gear."):
                problems.append(f"{at}.tags: {t!r} — gear grants tags under `gear.*`.")
        camp = row.get("camp")
        if camp is not None:
            bad = sorted(set(camp) - CAMP_KEYS) if isinstance(camp, dict) else ["(not an object)"]
            x = camp.get("night_check_scale") if isinstance(camp, dict) else None
            if bad or not isinstance(x, (int, float)) or not 0 <= x <= 1:
                problems.append(f"{at}.camp: {{\"night_check_scale\": a number from 0 to 1}}.")
        carry = row.get("carry")
        if carry is not None and (not isinstance(carry, dict)
                                  or not isinstance(carry.get("str"), int)):
            problems.append(f"{at}.carry: {{\"str\": a whole number}}.")
        eat = row.get("eat")
        if eat is not None and (not isinstance(eat, dict)
                                or not isinstance(eat.get("spends", 1), int)):
            problems.append(f"{at}.eat: {{\"spends\": a whole number}}.")
    names: dict[str, str] = {}
    for key, row in (d.get("items") or {}).items():
        for n in [key, *((row or {}).get("names") or ())]:
            low = _norm(n)
            if low in names and names[low] != key:
                problems.append(f"gear.{key}.names: {n!r} is already {names[low]!r}'s; a "
                                f"name is one thing.")
            names.setdefault(low, key)
    return problems


__all__ = ["CAPACITY", "SIZE_FACTOR", "camp_rule", "can_write", "capacity", "carried",
           "carry_bonus", "doc", "does", "food", "holds", "items", "load",
           "modifier_specs", "night_scale", "row_for", "spend", "tags", "validate"]
