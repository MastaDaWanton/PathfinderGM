"""Character classes, shipped and authored.

`tables.CLASSES` holds the Core Rulebook four as Python, because they are Open Game Content
and because the engine needs *something* before any file is read. Everything else arrives
as JSON and layers over them — the same overlay pattern ingredients, world classes and
creatures already use, and for the same reason: a corrected table in a later build must not
be shadowed by a stale copy in the user's data directory.

A class here is a full 1e class. It has hit dice, a BAB progression, saving throws, skill
ranks and a level table. That is what separates it from a *world* class
(`rules/worldclass.py`), which has none of those and levels on use.
"""
from __future__ import annotations

import json
from pathlib import Path

from .tables import CLASSES as SHIPPED, save_for

# BAB progressions, by the name a class file uses.
BAB = {"full": 1.0, "three_quarter": 0.75, "half": 0.5}

# Saving throw progressions. `good_plus_1` and `good_minus_1` exist because Blood Bending
# uses them: its Fortitude is the good progression plus one, which is unusual but perfectly
# regular — and derivable, which is the point. A derived column cannot arrive shuffled the
# way a typed one did.
SAVE_TRACKS = ("good", "good_plus_1", "good_minus_1", "poor")


def _dir(name: str) -> Path:
    from django.conf import settings

    return Path(settings.BASE_DIR) / "content" / name


def _homebrew(name: str) -> Path:
    from django.conf import settings

    return Path(settings.CAMPAIGN_DIR).parent / "homebrew" / name


_ALL: dict[str, dict] | None = None


def all_classes() -> dict[str, dict]:
    global _ALL
    if _ALL is None:
        out = {k: dict(v) for k, v in SHIPPED.items()}
        for folder in (_dir("classes"), _homebrew("classes")):
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                entries = data.get("classes") if isinstance(data, dict) else None
                if not isinstance(entries, list):
                    entries = [data] if isinstance(data, dict) and data.get("id") else []
                for e in entries:
                    key = str(e.get("id") or e.get("name", "")).strip().lower()
                    if not key:
                        continue
                    base = dict(out.get(key, {}))
                    for k, v in e.items():
                        if v in (None, ""):
                            continue
                        # `paths` layers per path and per field, never wholesale. A
                        # homebrew copy saved by the in-app editor before `grants` and
                        # `toggles` existed silently erased every ability document the
                        # shipped file had gained since — Blood Rage fell back to the
                        # old effectspec branch and nothing on screen said why.
                        if k == "paths" and isinstance(v, dict) \
                                and isinstance(base.get(k), dict):
                            merged = {pk: dict(pv) for pk, pv in base[k].items()}
                            for pk, pv in v.items():
                                if isinstance(pv, dict) and isinstance(
                                        merged.get(pk), dict):
                                    merged[pk].update(
                                        {fk: fv for fk, fv in pv.items()
                                         if fv not in (None, "")})
                                else:
                                    merged[pk] = pv
                            base[k] = merged
                        else:
                            base[k] = v
                    # The engine reads these two off the class, so they have to be the
                    # shapes it expects rather than the shapes a file happens to use.
                    base["good_saves"] = tuple(base.get("good_saves") or ())
                    base["class_skills"] = tuple(base.get("class_skills") or ())
                    base["proficiencies"] = tuple(base.get("proficiencies") or ())
                    out[key] = base
        _ALL = out
    return _ALL


def get(class_id: str) -> dict:
    return all_classes().get((class_id or "").strip().lower(), {})


def member_noun(class_id: str) -> str:
    """What to call one person of this class.

    Eleven of the thirteen shipped names are already nouns for a person — a Rogue, a
    Paladin — so this never bit until a class was named for the practice rather than
    the practitioner: the opening read "You are Masta, a Blood Bending". The document
    carries the word (`member`) and falls back to the name, so a homebrew class named
    "Storm Calling" fixes itself by saying so rather than by a special case here.
    """
    cls = get(class_id)
    return str(cls.get("member") or cls.get("name") or class_id or "").strip()


def features_at(class_id: str, level: int) -> list[str]:
    """Everything this class has granted by the time it reaches this level."""
    cls = get(class_id)
    out: list[str] = []
    for entry in cls.get("levels", []) or []:
        if int(entry.get("level", 0)) <= level:
            for feature in entry.get("grants", []) or []:
                if feature not in out:
                    out.append(feature)
    return out


def table_at(class_id: str, level: int) -> dict:
    """The row of the class table for this level — the damage columns and the rest."""
    cls = get(class_id)
    for entry in cls.get("levels", []) or []:
        if int(entry.get("level", 0)) == level:
            return entry
    return {}


def pools_for(class_id: str, level: int) -> list[dict]:
    """Resource definitions this class grants by this level.

    Returned rather than applied, because whether a pool is created is the engine's call
    and reading a file should not have side effects on a character sheet.
    """
    cls = get(class_id)
    out = []
    for pool in cls.get("pools", []) or []:
        if int(pool.get("from_level", 1)) <= level:
            out.append(pool)
    return out


def apply(actor) -> dict:
    """Give an actor everything their class grants at their current level.

    Run on every load rather than once at creation. A class file is content: a formula
    corrected in a later build, or a pool that did not exist when the character was rolled
    up, has to reach characters already in play. That is safe because `resources.define`
    recomputes a maximum and leaves the current value alone — a Blood Bender walks out of
    this with the same four rage rounds they walked in with.

    Overrides are merged, never assigned. A ruleset toggle or a homebrew exemption sitting
    on the character is not the class's to erase.

    Unknown rule names are collected and returned rather than set. This is the reason
    `ACTOR_RULES` is a list at all: a class file that says `temp_hp_stacks` where it meant
    `temp_hp.stacks` would otherwise grant a feature that silently never happens, and the
    only symptom would be a Coagulator whose wards quietly stop adding up nine levels in.
    """
    from . import resources
    from .sheet import ACTOR_RULES

    cid = (getattr(actor, "char_class", "") or "").strip().lower()
    cls = all_classes().get(cid)
    if not cls:
        return {"overrides": {}, "pools": [], "unknown_rules": []}

    level = max(1, int(getattr(actor, "level", 1) or 1))

    # Before the pools, because `hit_dice` is a term a pool formula may use and Blood
    # Bending has two Hit Dice per level. Computing a pool first would size it off one.
    per_level = cls.get("hit_dice_per_level")
    if per_level:
        actor.hit_dice_per_level = int(per_level)

    granted: dict[str, bool] = {}
    unknown: list[str] = []
    for rule, value in overrides_for(cid, level).items():
        if rule not in ACTOR_RULES:
            unknown.append(rule)
            continue
        actor.overrides[rule] = value
        granted[rule] = value

    made: list[str] = []
    for spec in pools_for(cid, level):
        resources.define(actor, {**spec,
                                 "source": spec.get("source") or cls.get("name", cid)})
        made.append(str(spec["id"]).strip().lower())

    # Spell slots are ordinary pools, so they refresh on a night, survive a save and show
    # on the sheet with no second mechanism for any of it.
    from . import casting

    made.extend(casting.define_slots(actor))

    return {"overrides": granted, "pools": made, "unknown_rules": unknown}


def save_base(cls: dict, save: str, level: int) -> int | None:
    """This class's base save at this level, or None if the class does not say.

    Two shapes, and the difference matters. A *named track* is derived, so it cannot be
    mistyped and cannot go stale at a level nobody tested. An *explicit column* — twenty
    integers — is for a source table that is not regular, where deriving the number would
    mean inventing one. Blood Bending needs both: its Fortitude is exactly good+1 at all
    twenty levels, and its Will is not exactly anything.

    Levels past the end of an explicit column hold at its last entry rather than raising.
    A 21st-level character is not this function's problem to discover.
    """
    spec = (cls.get("saves") or {}).get(save)
    if spec is None:
        return None
    if isinstance(spec, (list, tuple)):
        if not spec:
            return None
        return int(spec[max(1, min(int(level), len(spec))) - 1])
    track = str(spec).strip().lower()
    if track not in SAVE_TRACKS:
        return None
    good = save_for(True, level)
    return {
        "good": good,
        "good_plus_1": good + 1,
        "good_minus_1": max(0, good - 1),
        "poor": save_for(False, level),
    }[track]


def overrides_for(class_id: str, level: int) -> dict[str, bool]:
    """Named rules this class exempts its members from, by this level.

    Blood Bond grants two at 1st: temporary hit points stack, and non-lethal damage counts
    them before it drops you. Both are the same idea — the class buys its abilities with
    hit points, so where those two lines sit is where the class ends.
    """
    cls = get(class_id)
    out: dict[str, bool] = {}
    for spec in cls.get("overrides", []) or []:
        if int(spec.get("from_level", 1)) <= level:
            out[str(spec["rule"])] = bool(spec.get("value", True))
    return out
