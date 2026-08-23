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
