"""Going up a level, and the paths a class can branch into.

Two things that only look separate. A level is where a class hands something over, and
for a class with paths it is also where the player chooses *which* branch hands it over
— so the same call has to know both what the table grants and what the character has
elected to follow.

**The engine raises the level; it does not invent the class.** Everything granted comes
out of the class file — hit die, BAB, saves, the per-level `grants` list, the pools and
their formulas. Nothing here writes a feature, which is why a class the app has never
seen levels correctly the moment somebody drops its JSON in.

**Hit points at a level are rolled, not maximised.** First level takes the whole die
(see `creation.max_hit_die`, and the user's own wording: "lvl 1 should get Max HP");
every level after it rolls, because that is the rule the same sentence draws the
contrast against. The roll goes through the engine's dice so it lands in the turn log
like every other number the app produces.

**Paths are declared by the class, never assumed.** A class file that lists `paths` has
them; one that does not, does not, and `needs_path` answers honestly either way. Blood
Bending declares four — battle blood, blood spike, coagulator, blood commander — and
the abilities behind them are not in the file yet. That absence is deliberate and
documented in the file itself; this module carries the *choice* so it is recorded on
the sheet and shown on the class tab, and the moment the abilities are written they
grant like anything else without a line changing here.
"""
from __future__ import annotations

import re

from . import classes as classes_mod
from .tables import ability_modifier, bab_for, save_for

MAX_LEVEL = 20


def paths_for(class_id: str) -> list[str]:
    """The branches this class offers, or [] when it offers none.

    A class may declare its paths as bare names or as a mapping of name to detail.
    Iterating a dict yields its keys, so both shapes read the same here — which is what
    let the four Blood Bending names become four full paths without this line changing.
    """
    found = classes_mod.get(class_id).get("paths") or []
    return [str(p) for p in found if str(p).strip()]


def path_detail(class_id: str, name: str) -> dict:
    """Everything the class file says about one path. {} when it says only the name."""
    found = classes_mod.get(class_id).get("paths")
    if isinstance(found, dict):
        got = found.get(str(name).strip().lower())
        if isinstance(got, dict):
            return got
    return {}


def control_blood(actor) -> dict:
    """How far along each branch this character has come.

    The class table grants "control blood 1a" at 1st, "2a" at 3rd, up to "5a" at 10th,
    then "1b" at 11th through "5b" at 20th. Two tracks, and the reason the class asks
    you to choose "a path or both paths": the a-track is the first path you follow and
    the b-track the second. So a Control Blood level is not one number — it is one per
    branch, and the abilities of a path are tiered against its own.

    Read from the grants rather than from a table written out again here, because the
    class file is the class and a second copy of its progression is a second thing to
    keep level with the first.
    """
    reached = {"a": 0, "b": 0}
    # Defensive because `resources.variables` calls this for every formula on every
    # sheet, including the stand-in actors the pool tests build with three attributes.
    # A branching track is one class's business; nothing else should fail over it.
    try:
        features = classes_mod.features_at(getattr(actor, "char_class", "") or "",
                                           int(getattr(actor, "level", 1) or 1))
    except Exception:
        return reached
    for feature in features:
        m = re.fullmatch(r"control blood\s*(\d+)\s*([ab])", str(feature).strip().lower())
        if m:
            track = m.group(2)
            reached[track] = max(reached[track], int(m.group(1)))
    return reached


def control_blood_for(actor, path: str) -> int:
    """The tier this character has reached *in this path*.

    The first path taken runs on the a-track and the second on the b-track, which is
    what the two halves of the progression are for. A path the character does not
    follow is 0 — they have no tier in a branch they never took.
    """
    taken = [p.lower() for p in (getattr(actor, "paths", None) or [])]
    key = str(path).strip().lower()
    if key not in taken:
        return 0
    return control_blood(actor)["a" if taken.index(key) == 0 else "b"]


def table_die(actor, column: str) -> str:
    """A die the class prints on its own table for this level — "blood", "fist".

    Read by column name rather than by a list of the ones this app knows, which is the
    same reason the class tab draws whatever columns it finds: a class that ships with
    a die nobody here has heard of still works.
    """
    row = classes_mod.table_at(getattr(actor, "char_class", "") or "",
                               int(getattr(actor, "level", 1) or 1))
    return str(row.get(column) or "")


def multiply_dice(notation: str, times: int) -> str:
    """"1d8" three times over is "3d8".

    The count multiplies and the face does not, which is what a damage multiplier means
    in 1e — three times a d8 is three d8s, not one d24. A flat bonus rides along
    multiplied too, because it is part of the thing being tripled.
    """
    m = re.fullmatch(r"\s*(\d*)d(\d+)\s*(?:([+-])\s*(\d+))?\s*", str(notation or ""),
                     re.I)
    if not m or times < 1:
        return str(notation or "")
    count = max(1, int(m.group(1) or 1)) * int(times)
    out = f"{count}d{m.group(2)}"
    if m.group(3):
        out += f"{m.group(3)}{int(m.group(4)) * int(times)}"
    return out


def resolve_effect(spec: dict, actor, path: str = "") -> dict:
    """One effect with its scaling worked out for this character.

    A tiered value picks the highest rung at or below the tier reached — "DR 2 (Lvl 1),
    DR 5 (Lvl 2), DR 8 (Lvl 3), DR 12 (Lvl 5)" is DR 8 at tier 4, because tier 4 grants
    nothing new and the rung below is still in force. A formula is evaluated against
    the sheet the same way a pool's is. Anything with neither passes through untouched.
    """
    out = dict(spec)
    tier = control_blood_for(actor, path) if path else max(control_blood(actor).values())
    out["control_blood"] = tier

    if spec.get("scales_by") == "control_blood":
        rungs = {int(k): v for k, v in (spec.get("by_tier") or {}).items()}
        reached = [n for n in sorted(rungs) if n <= tier]
        if reached:
            out.update(rungs[reached[-1]])
            out["at_tier"] = reached[-1]
        else:
            out["inactive"] = True      # the character is not far enough along yet
    if spec.get("dice_from"):
        die = table_die(actor, spec["dice_from"])
        if die:
            out["dice"] = multiply_dice(die, int(spec.get("times", 1) or 1))
            out["from_column"] = f"{spec['dice_from']} {die}"
        else:
            out["inactive"] = True      # this class prints no such column
    if spec.get("formula"):
        from . import resources

        try:
            out["amount"] = resources.evaluate(spec["formula"], actor)
        except Exception:
            out["inactive"] = True
    return out


def needs_path(class_id: str) -> bool:
    return bool(paths_for(class_id))


def check_paths(class_id: str, chosen) -> tuple[list[str], list[str]]:
    """The paths as the rules will accept them, and every problem at once.

    A class with paths must have at least one — "you have to choose a path or both
    paths" — and may have as many as it declares. A class without paths must not carry
    any, because a rogue with a Coagulator branch is a save that will confuse
    everything downstream that reads it.
    """
    offered = paths_for(class_id)
    picked, problems = [], []
    for name in (chosen or []):
        key = " ".join(str(name).split()).strip().lower()
        if not key:
            continue
        if key not in offered:
            problems.append(
                f"{name!r} is not a path of this class"
                + (f": {', '.join(offered)}." if offered else "; it has none."))
        elif key not in picked:
            picked.append(key)
    if offered and not picked:
        problems.append(
            f"A {classes_mod.get(class_id).get('name', class_id)} follows at least one "
            f"path: {', '.join(offered)}. Take one, or take more than one.")
    return picked, problems


def preview(class_id: str, level: int, paths=None) -> list[dict]:
    """The whole class table up to a level, for a player planning ahead.

    Every row, including the ones not reached yet, because the point of showing the
    table is to decide what to build towards. `reached` says which side of the line
    each row is on.
    """
    rows = []
    for n in range(1, MAX_LEVEL + 1):
        table = classes_mod.table_at(class_id, n)
        rows.append({
            "level": n,
            "reached": n <= int(level or 1),
            "grants": list(table.get("grants") or []),
            # Whatever else the class prints on its own table — a monk's fist damage,
            # a Blood Bender's blood die. Read rather than named, so a class with
            # columns this app has never heard of still shows them.
            "columns": {k: v for k, v in table.items()
                        if k not in ("level", "grants") and not k.startswith("_")},
        })
    return rows


def gains_at(class_id: str, level: int) -> dict:
    """What reaching this level is worth, before the dice are rolled."""
    cls = classes_mod.get(class_id)
    before, after = max(0, int(level) - 1), int(level)
    saves = {}
    for save in ("fort", "ref", "will"):
        good = save in (cls.get("good_saves") or [])
        was = save_for(good, before) if before else 0
        saves[save] = save_for(good, after) - was
    return {
        "level": after,
        "bab": bab_for(cls.get("bab", "three_quarter"), after)
               - (bab_for(cls.get("bab", "three_quarter"), before) if before else 0),
        "saves": {k: v for k, v in saves.items() if v},
        "grants": [g for g in classes_mod.table_at(class_id, after).get("grants") or []],
        "skill_ranks": int(cls.get("skill_ranks", 2)),
    }


def level_up(actor, dice=None) -> dict:
    """Raise the character one level and hand back exactly what changed.

    Returns a record rather than mutating quietly: every number on this sheet is
    supposed to show where it came from, and a level that silently added seven hit
    points would be the one change on the page nobody could account for.
    """
    if int(actor.level or 1) >= MAX_LEVEL:
        return {"ok": False, "why": f"{actor.name} is already {MAX_LEVEL}th level."}

    cls = classes_mod.get(actor.char_class or "")
    if not cls:
        return {"ok": False, "why": f"no class data for {actor.char_class!r}."}

    new_level = int(actor.level or 1) + 1
    gains = gains_at(actor.char_class, new_level)

    from .creation import max_hit_die

    die = max_hit_die(cls.get("hit_die", 8))
    rolled = (dice.roll(f"1d{die}", label="hit points", visibility="player").total
              if dice is not None else (die + 1) // 2)
    con = ability_modifier(actor.ability_score("con"))
    hp = max(1, rolled + con)          # never a level that costs you hit points

    actor.level = new_level
    actor.hp_max += hp
    actor.hp += hp
    # Pools are formulas in the class file, so they resize themselves against the new
    # level rather than being recomputed here — the whole reason they were written as
    # formulas in the first place.
    refreshed = actor.rebuild_pools() if hasattr(actor, "rebuild_pools") else []

    return {
        "ok": True, "level": new_level, "rolled": rolled, "con": con, "hp": hp,
        "hp_max": actor.hp_max, "grants": gains["grants"], "bab": gains["bab"],
        "saves": gains["saves"], "skill_ranks": gains["skill_ranks"],
        "pools": refreshed,
    }
