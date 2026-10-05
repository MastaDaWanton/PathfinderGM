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


def toggle_key(actor, name: str) -> str:
    """The condition key this ability toggles, or "" for an ordinary ability.

    Declared in the class data (`paths.<path>.toggles`): Extracorporeal Blood Armament
    was a fire-and-forget use with nothing on screen to say whether it still held, and
    "the user isn't confused about whether or not its active" is the whole feature. A
    toggle is a standing condition with no clock — visible wherever conditions are.
    """
    want = " ".join(str(name or "").split()).strip().lower()
    if not want:
        return ""
    for path in (getattr(actor, "paths", None) or []):
        det = path_detail(getattr(actor, "char_class", "") or "", path)
        for listed, key in (det.get("toggles") or {}).items():
            if str(listed).lower() == want:
                return str(key)
    return ""


def ability_doc(actor, name: str) -> tuple[str, dict]:
    """The ability's document — requirements, cost, granted effect, tell — and the
    path that carries it. `("", {})` for an ability that has none.

    Stage 3 of docs/states-effects-tells.md: declared in the class data
    (`paths.<path>.grants`, keyed by the resolved name like `effects`), so an
    ability's activation requirements, pool cost, modifiers, granted tags and tells
    are data the classbuilder validates rather than code the engine special-cases.
    """
    want = " ".join(str(name or "").split()).strip().lower()
    if not want:
        return "", {}
    for path in (getattr(actor, "paths", None) or []):
        det = path_detail(getattr(actor, "char_class", "") or "", path)
        resolved = ""
        for listed, real in (det.get("resolves") or {}).items():
            if str(listed).lower() == want:
                resolved = str(real)
                break
        doc = (det.get("grants") or {}).get(resolved or "")
        if isinstance(doc, dict) and doc:
            return path, doc
    return "", {}


def granted_weapons(actor) -> list[dict]:
    """Every weapon a followed path's documents can put in this character's hands.

    Each entry: `{"ability": <resolved name>, "key": <toggle condition>, "weapon":
    <the document's weapon block>}`. This is what replaced the armament's name-list
    special case in `Actor.weapon` — the class file says which aliases exist, which
    table column the die comes from, and which toggle must hold, and a homebrew class
    stating the same fields gets the same treatment.
    """
    out: list[dict] = []
    for path in (getattr(actor, "paths", None) or []):
        det = path_detail(getattr(actor, "char_class", "") or "", path)
        toggles = {str(k).lower(): str(v) for k, v in (det.get("toggles") or {}).items()}
        for name, doc in (det.get("grants") or {}).items():
            if not isinstance(doc, dict) or not isinstance(doc.get("weapon"), dict):
                continue
            out.append({"ability": str(name), "key": toggles.get(str(name).lower(), ""),
                        "weapon": dict(doc["weapon"])})
    return out


def granted_weapon_named(actor, key: str) -> dict | None:
    """The grant whose aliases include this weapon name, or None."""
    want = " ".join(str(key or "").split()).strip().lower()
    for g in granted_weapons(actor):
        aliases = {str(a).lower() for a in (g["weapon"].get("aliases") or ())}
        if want in aliases:
            return g
    return None


def standing_dr(actor) -> list[dict]:
    """Damage reduction the followed paths' passive documents grant, live-read.

    Live-read like worn gear rather than applied as an effect, because Iron Clot is
    "permanent": there is no action that turns it on, no save that could lose it, and
    the tier rungs must follow the level the moment it changes. Only documents whose
    ability sits in `paths.<path>.passive` land here — a toggled stance's DR would
    arrive through its ActiveEffect payload instead.

    Each entry: `{"amount": int, "bypass": str, "source": <resolved name>}`. A rung
    the character has not reached resolves inactive and contributes nothing.
    """
    out: list[dict] = []
    for path in (getattr(actor, "paths", None) or []):
        det = path_detail(getattr(actor, "char_class", "") or "", path)
        passives = {str(n).lower() for n in (det.get("passive") or [])}
        for name, doc in (det.get("grants") or {}).items():
            if not isinstance(doc, dict) or not isinstance(doc.get("dr"), dict):
                continue
            if str(name).lower() not in passives:
                continue
            got = resolve_effect(dict(doc["dr"]), actor, path)
            if got.get("inactive"):
                continue
            amount = int(got.get("amount", 0) or 0)
            if amount > 0:
                out.append({"amount": amount,
                            "bypass": str(got.get("bypass") or ""),
                            "against": str(got.get("against") or ""),
                            "source": str(name)})
    return out


def is_passive(actor, name: str) -> bool:
    """Whether this ability is an always-active passive in a path the actor follows.

    Declared in the class data (`paths.<path>.passive`) rather than guessed from prose:
    Swift Strikes was on the abilities bar as a button, and "using" it swallowed the
    attack it was supposed to be modifying — a passive is never used, it simply happens.
    """
    want = " ".join(str(name or "").split()).strip().lower()
    if not want:
        return False
    for path in (getattr(actor, "paths", None) or []):
        det = path_detail(getattr(actor, "char_class", "") or "", path)
        passives = {str(n).lower() for n in (det.get("passive") or [])}
        if want in passives:
            return True
        # A tier lists Iron Clot only through its rungs — "Iron Clot (DR 2/-)" —
        # and find_ability hands back the listed variant, so membership has to be
        # checked through resolves as well or a rung-named passive stays a button.
        for listed, real in (det.get("resolves") or {}).items():
            if str(listed).lower() == want and str(real).lower() in passives:
                return True
    return False


def has_passive(actor, name: str) -> bool:
    """`is_passive`, and the actor has actually reached its tier."""
    want = " ".join(str(name or "").split()).strip().lower()
    for path in (getattr(actor, "paths", None) or []):
        det = path_detail(getattr(actor, "char_class", "") or "", path)
        if want not in {str(n).lower() for n in (det.get("passive") or [])}:
            continue
        reached = control_blood_for(actor, path)
        for tier, names in (det.get("tiers") or {}).items():
            if want in {str(n).lower() for n in names} and int(tier) <= reached:
                return True
    return False


def find_ability(actor, wanted: str) -> tuple[str, str, list[dict]]:
    """The ability this character has by that name: its path, its real name, its effects.

    Searched only across the paths they actually follow, and only at or below the tier
    they have reached — an ability is not yours because the class prints it somewhere.
    Returns ("", "", []) when they do not have it, so the caller can say which of the
    two reasons applies.
    """
    want = " ".join(str(wanted or "").split()).strip().lower()
    if not want:
        return "", "", []
    for path in (getattr(actor, "paths", None) or []):
        det = path_detail(getattr(actor, "char_class", "") or "", path)
        tier_of = {}
        for tier, names in (det.get("tiers") or {}).items():
            for listed in names:
                tier_of[listed.lower()] = int(tier)
        reached = control_blood_for(actor, path)
        for listed, tier in tier_of.items():
            if listed != want and not listed.startswith(want):
                continue
            if tier > reached:
                return path, listed, []          # theirs eventually, not yet
            key = (det.get("resolves") or {}).get(
                next(n for n in (det.get("tiers") or {}).get(str(tier), [])
                     if n.lower() == listed))
            specs = (det.get("effects") or {}).get(key or "", [])
            return path, listed, [resolve_effect(s, actor, path) for s in specs]
    return "", "", []


def tier_needed(actor, wanted: str) -> int:
    """Which tier an ability sits at on a path this character follows. 0 if none does."""
    want = " ".join(str(wanted or "").split()).strip().lower()
    for path in (getattr(actor, "paths", None) or []):
        det = path_detail(getattr(actor, "char_class", "") or "", path)
        for tier, names in (det.get("tiers") or {}).items():
            for listed in names:
                if listed.lower() == want or listed.lower().startswith(want):
                    return int(tier)
    return 0


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
    limit = max_paths(class_id)
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
    name = classes_mod.get(class_id).get("name", class_id)
    if offered and not picked:
        problems.append(
            f"A {name} follows a path. Take one to be your Path A: "
            f"{', '.join(offered)}.")
    if limit and len(picked) > limit:
        # Order is the whole meaning of the choice: the first is Path A and runs from
        # first level, the second is Path B and waits for the track to open.
        problems.append(
            f"A {name} follows {limit} paths at most — the first is Path A and the "
            f"second Path B. You have taken {len(picked)}: "
            f"{', '.join(picked)}.")
    return picked, problems


def max_paths(class_id: str) -> int:
    """How many branches this class allows. 0 when it does not say.

    Blood Bending's table has an a-track and a b-track and no third, so two is not a
    house rule here — it is what the progression can actually carry.
    """
    found = classes_mod.get(class_id).get("paths")
    if not found:
        return 0
    stated = classes_mod.get(class_id).get("max_paths")
    if stated:
        return int(stated)
    tracks = {m.group(1) for lvl in range(1, MAX_LEVEL + 1)
              for feature in classes_mod.table_at(class_id, lvl).get("grants") or []
              if (m := re.search(r"control blood\s*\d+\s*([ab])",
                                 str(feature).lower()))}
    return len(tracks) or 0


def unlocks_at(class_id: str, index: int) -> int:
    """The level the track behind the index-th path opens. 0 if it never does.

    Read off the grants: Path B is available when the table first grants "control
    blood 1b", which is 11th level and is the class's business rather than this
    module's.
    """
    track = "ab"[index] if index < 2 else ""
    if not track:
        return 0
    for lvl in range(1, MAX_LEVEL + 1):
        for feature in classes_mod.table_at(class_id, lvl).get("grants") or []:
            if re.fullmatch(rf"control blood\s*1\s*{track}",
                            str(feature).strip().lower()):
                return lvl
    return 0


def preview(class_id: str, level: int, paths=None, rules: dict | None = None) -> list[dict]:
    """The whole class table up to a level, for a player planning ahead.

    Every row, including the ones not reached yet, because the point of showing the
    table is to decide what to build towards. `reached` says which side of the line
    each row is on.

    `gains` is everything the row is worth (`gains_at`'s `said`), not only the class's
    own `grants`. The rows used to carry the grants alone, and the Class tab printed
    "nothing new" under 47 levels of the core classes — wizard 15, cleric 10, sorcerer
    9, druid 8, bard 3, paladin 1, ranger 1 — when every one of them raises a save, a
    base attack, a spell slot or owes a feat. The owner, 2026-10-04: "there are a bunch
    of levels that say you gain nothing but there are no level where you gain nothing."
    """
    if rules is None:
        rules = house_rhythms()
    rows = []
    for n in range(1, MAX_LEVEL + 1):
        table = classes_mod.table_at(class_id, n)
        rows.append({
            "level": n,
            "reached": n <= int(level or 1),
            "grants": list(table.get("grants") or []),
            "gains": gains_at(class_id, n, rules)["said"],
            # Whatever else the class prints on its own table — a monk's fist damage,
            # a Blood Bender's blood die. Read rather than named, so a class with
            # columns this app has never heard of still shows them.
            "columns": {k: v for k, v in table.items()
                        if k not in ("level", "grants") and not k.startswith("_")},
        })
    return rows


def house_rhythms() -> dict:
    """The two level-up house rules, read once for a caller that asks about many levels."""
    from . import houserules

    live = houserules.active()
    return {"bonus_feats": live.get("bonus_feats", "off"),
            "bonus_ability_points": live.get("bonus_ability_points", "off")}


def _ordinal(n: int) -> str:
    n = int(n)
    tail = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{tail}"


def _caster_block(class_id: str) -> dict:
    """How a class casts, without an actor: its own `casting` block, else the table's."""
    from . import casting

    declared = classes_mod.get(class_id).get("casting")
    if isinstance(declared, dict) and declared:
        return declared
    return casting.CASTERS.get(str(class_id or "").strip().lower(), {})


def _spell_lines(class_id: str, level: int) -> list[str]:
    """New spell slots, spells known and free spellbook spells this level brings.

    The BASE table, as the Core Rulebook prints it; bonus slots for a high ability are
    the character's, not the level's, and the Spells tab shows those.
    """
    from . import casting

    data = _caster_block(class_id)
    if not data:
        return []
    out: list[str] = []
    table = casting.PROGRESSIONS.get(data.get("progression", "full")) or []

    def row(at: int) -> list[int]:
        if not table or at < 1:
            return []
        return list(table[min(at, len(table)) - 1])

    now, was = row(level), row(level - 1)
    for spell_level, n in enumerate(now):
        before = was[spell_level] if spell_level < len(was) else 0
        if n > max(0, before):
            what = "cantrip" if spell_level == 0 else f"{_ordinal(spell_level)}-level"
            out.append(f"first {what} spell slot{'s' if n > 1 else ''} ({n})"
                       if before <= 0 else
                       f"+{n - before} {what} slot{'s' if n - before > 1 else ''}")
    known_now = casting.known_row(data, level)
    known_was = casting.known_row(data, level - 1) if level > 1 else {}
    for spell_level, n in sorted(known_now.items()):
        gained = n - known_was.get(spell_level, 0)
        if gained > 0 and level > 1:
            what = "cantrip" if spell_level == 0 else f"{_ordinal(spell_level)}-level spell"
            out.append(f"+{gained} {what}{'s' if gained > 1 else ''} known")
    per = int(data.get("learns_per_level") or 0)
    if per and level > 1 and data.get("prepare_from") == "spellbook":
        out.append(f"{per} spells for the spellbook")
    return out


def _pool_at(spec: dict, level: int, per_level: int, bab: str) -> int | None:
    """A class pool's maximum at a level, for a sheet of plain 10s.

    Ability modifiers are held at 0 because the question is what the LEVEL adds; the
    character's own modifier is the same either side of it and cancels.
    """
    import ast

    from . import resources

    if int(spec.get("from_level", 1)) > level:
        return None
    names = {"level": level, "hit_dice": level * max(1, per_level), "hp": 0,
             "hp_max": 0, "temp_hp": 0, "control_blood": 0, "control_blood_a": 0,
             "control_blood_b": 0}
    try:
        names["bab"] = bab_for(bab, level)
    except ValueError:
        names["bab"] = level * 3 // 4
    for ab in ("str", "dex", "con", "int", "wis", "cha"):
        names[ab], names[f"{ab}_mod"] = 10, 0
    text = str(spec.get("max", "") or "").strip()
    if not text:
        return None
    try:
        return int(resources._walk(ast.parse(text, mode="eval").body, names, text) // 1)
    except Exception:       # noqa: BLE001 - a formula the parser refuses says nothing here
        return None


def _pool_lines(class_id: str, level: int, grants: list[str]) -> list[str]:
    cls = classes_mod.get(class_id)
    per = int(cls.get("hit_dice_per_level") or 1)
    bab = cls.get("bab", "three_quarter")
    said = " ".join(str(g).lower() for g in grants)
    out = []
    for spec in cls.get("pools") or []:
        pid = str(spec.get("id", "")).strip()
        now = _pool_at(spec, level, per, bab)
        if now is None:
            continue
        was = _pool_at(spec, level - 1, per, bab) if level > 1 else None
        if was is None:
            # A pool the table already names on this row ("ki pool") is not said twice.
            if level > 1 and pid.lower() not in said:
                out.append(f"{pid} pool opens")
        elif now > was:
            out.append(f"{pid} +{now - was}")
    return out


def gains_at(class_id: str, level: int, rules: dict | None = None) -> dict:
    """What reaching this level is worth, before the dice are rolled.

    `said` is the whole of it in words, for the Class tab's row, the Next level card and
    the level-up line alike — one list, so the three cannot disagree. Computed here and
    never in the page (the brief: "Compute in Python … never in the page").
    """
    if rules is None:
        rules = house_rhythms()
    cls = classes_mod.get(class_id)
    before, after = max(0, int(level) - 1), int(level)
    saves = {}
    for save in ("fort", "ref", "will"):
        good = save in (cls.get("good_saves") or [])
        was = save_for(good, before) if before else 0
        saves[save] = save_for(good, after) - was
    grants = [g for g in classes_mod.table_at(class_id, after).get("grants") or []]
    try:
        bab = bab_for(cls.get("bab", "three_quarter"), after) \
            - (bab_for(cls.get("bab", "three_quarter"), before) if before else 0)
    except ValueError:
        bab = 0
    picks = picks_at(class_id, after, rules)
    said: list[str] = []
    if bab:
        said.append(f"base attack +{bab}")
    said += [f"{k.title()} +{v}" for k, v in saves.items() if v]
    if picks["feat"]:
        said.append("a feat" if after > 1 else "a feat (chosen at creation)")
    said += [str(g) for g in grants]
    if picks["points"]:
        said.append("+1 to an ability score")
    if picks["house_feats"]:
        said.append(f"{picks['house_feats']} extra feat (house rule)")
    if picks["house_points"]:
        said.append(f"{picks['house_points']} ability points (house rule)")
    said += _spell_lines(class_id, after)
    said += _pool_lines(class_id, after, grants)
    return {
        "level": after,
        "bab": bab,
        "saves": {k: v for k, v in saves.items() if v},
        "grants": grants,
        "skill_ranks": int(cls.get("skill_ranks", 2)),
        "feats": picks["feat"] + picks["house_feats"],
        "bonus_feats": picks["bonus"],
        "ability_points": picks["points"] + picks["house_points"],
        "said": said,
    }


# --- feats and ability points a level owes ----------------------------------------------
#
# The Core Rulebook's Character Advancement table: a feat at 1st level and every odd
# level after (3, 5, 7 … 19), and +1 to one ability score at 4th, 8th, 12th, 16th and
# 20th. A fighter's bonus feats are the class table's own ("bonus feat" at 1, 2, 4, 6 …),
# read off the grants rather than off the class's name, so a homebrew class written on
# the class builder with "bonus feat" on its rows owes them too.
#
# Before 2026-10-04 none of it was granted anywhere: `level_up` rolled hit points, grew
# the class's own `ability_growth` and resized the pools, and nothing in the app ever
# appended to `actor.feats` after the forge. A level-5 fighter was owed four feats past
# creation (two general, at 3 and 5; two bonus, at 2 and 4) and had been given none.
#
# The shape is the spellbook's (`casting.learning`): what is OWED is computed from the
# level against a stored count of what has been TAKEN, and the player chooses on the
# sheet whenever they like — a level taken in the night is offered the same as one taken
# from the Class card. The builders do the same. Foundry's PF1 level-up form tracks the
# ability points as `new`, `used` and `available` (pf1.applications.LevelUpForm), Hero
# Lab validates "too few feats selected" against a count and models a table's extra-feat
# rule as an adjustment to that count rather than as a different rule (forums.wolflair.com
# t=19473). Neither stores a list of slots; both store a number and derive the rest.
#
# Three counters, because the picks obey three different rules:
#   level_feats_taken     the general feats and the homebrew extra feats — any feat the
#                         character qualifies for, so one count serves both
#   bonus_feats_taken     the class's bonus feats, restricted (`bonus_feat_rule`)
#   ability_points_taken  +1s placed, the book's and the homebrew's — any score
#
# Level 1 is the forge's: the 1st-level feat and a fighter's 1st-level bonus feat are in
# its budget, so they are not owed here. The homebrew rule is the exception, and on
# purpose: a rule set to "every" or "odd" grants at 1st level too, the forge offers it,
# and what the forge did not take stays owed on the sheet — so a character made before
# the table turned the rule on is offered their 1st-level share like any other level.
#
# Changing a rule takes nothing back. A count of picks taken that exceeds what is owed
# now reads as nothing owed; the feats stay on the sheet.

BOOK_ABILITY_EVERY = 4

# What a class's bonus feats may be, by the book. Read from the class file's own
# `bonus_feats` block first, so a homebrew class declares its own; this table is the
# fallback for the core classes, whose files this lane may not edit (stage 9 moves class
# names out of the engine, and this is a table it should move).
#   fighter  "These bonus feats must be selected from those listed as combat feats."
#   wizard   "a metamagic feat, an item creation feat, or Spell Mastery"
#   monk     a list that grows at 6th and 10th, and "a monk need not have any of the
#            prerequisites normally required for these feats to select them"
BONUS_FEAT_RULES: dict[str, dict] = {
    "fighter": {"types": ["combat"], "say": "a combat feat"},
    "wizard": {"types": ["metamagic", "item creation"], "ids": ["spell-mastery"],
               "say": "a metamagic or item creation feat, or Spell Mastery"},
    "monk": {"ids_by_level": {
        1: ["catch-off-guard", "combat-reflexes", "deflect-arrows", "dodge",
            "improved-grapple", "scorpion-style", "throw-anything"],
        6: ["gorgon-s-fist", "improved-bull-rush", "improved-disarm", "improved-feint",
            "improved-trip", "mobility"],
        10: ["improved-critical", "medusa-s-wrath", "snatch-arrows", "spring-attack"]},
        "ignore_prereqs": True,
        "say": "one of the monk's bonus feats, prerequisites waived"},
}


def class_bonus_feats_at(class_id: str, level: int) -> int:
    """How many bonus feats the class table grants on this row."""
    return sum(1 for g in classes_mod.table_at(class_id, int(level)).get("grants") or []
               if str(g).strip().lower() == "bonus feat")


def bonus_feat_rule(class_id: str) -> dict:
    """What this class's bonus feats may be. `{}` is any feat qualified for."""
    declared = classes_mod.get(class_id).get("bonus_feats")
    if isinstance(declared, dict):
        return declared
    return BONUS_FEAT_RULES.get(str(class_id or "").strip().lower(), {})


def picks_at(class_id: str, level: int, rules: dict | None = None) -> dict:
    """What one level owes in picks: `{"feat", "bonus", "points", "house_feats",
    "house_points"}` — level 1's book feat included, for the table to say."""
    from . import houserules

    if rules is None:
        rules = house_rhythms()
    level = int(level)
    return {
        "feat": 1 if level % 2 == 1 else 0,
        "bonus": class_bonus_feats_at(class_id, level),
        "points": 1 if level % BOOK_ABILITY_EVERY == 0 else 0,
        "house_feats": (houserules.BONUS_FEATS_PER_LEVEL
                        if houserules.qualifies(rules.get("bonus_feats", "off"), level)
                        else 0),
        "house_points": (houserules.BONUS_POINTS_PER_LEVEL
                         if houserules.qualifies(rules.get("bonus_ability_points", "off"),
                                                 level) else 0),
    }


def owed(actor, rules: dict | None = None) -> dict:
    """Every feat and ability point this character's levels owe and they have not taken.

    `{"feats": {"owed", "picks"}, "bonus": {"owed", "picks", "rule"}, "points": {"owed",
    "picks"}, "house": {...}, "total"}`. Each `picks` row is one still owed, oldest first:
    `{"for_level", "source": "book"|"house"}`, and for points `"points"` too (a homebrew
    level's two can be half taken).
    """
    if rules is None:
        rules = house_rhythms()
    cid = str(getattr(actor, "char_class", "") or "")
    level = max(1, int(getattr(actor, "level", 1) or 1))
    feats, bonus, points = [], [], []
    for n in range(1, level + 1):
        got = picks_at(cid, n, rules)
        if n > 1 and got["feat"]:
            feats.append({"for_level": n, "source": "book"})
        feats += [{"for_level": n, "source": "house"}] * got["house_feats"]
        if n > 1:
            bonus += [{"for_level": n, "source": "book"}] * got["bonus"]
        if got["points"]:
            points.append({"for_level": n, "source": "book", "points": got["points"]})
        if got["house_points"]:
            points.append({"for_level": n, "source": "house",
                           "points": got["house_points"]})

    feats = feats[int(getattr(actor, "level_feats_taken", 0) or 0):]
    bonus = bonus[int(getattr(actor, "bonus_feats_taken", 0) or 0):]
    spent = int(getattr(actor, "ability_points_taken", 0) or 0)
    left = []
    for row in points:
        if spent >= row["points"]:
            spent -= row["points"]
            continue
        left.append({**row, "points": row["points"] - spent})
        spent = 0
    rule = bonus_feat_rule(cid)
    out = {
        "feats": {"owed": len(feats), "picks": feats},
        "bonus": {"owed": len(bonus), "picks": bonus,
                  "rule": str(rule.get("say") or "any feat they qualify for")},
        "points": {"owed": sum(r["points"] for r in left), "picks": left},
        "house": dict(rules),
    }
    out["total"] = out["feats"]["owed"] + out["bonus"]["owed"] + out["points"]["owed"]
    return out


def _bonus_allows(actor, feat, rule: dict, for_level: int) -> bool:
    if not rule:
        return True
    ids = set(rule.get("ids") or [])
    by_level = rule.get("ids_by_level") or {}
    for at, names in by_level.items():
        if int(at) <= int(for_level):
            ids |= set(names)
    if feat.id in ids:
        return True
    types = {str(t).lower() for t in feat.types or ()}
    return bool(types & {str(t).lower() for t in rule.get("types") or ()})


def feat_menu(actor, pool: str = "feats") -> dict:
    """Every feat this character could take for what `pool` owes, and why the rest are
    shut — the forge's list (`creation.feat_rows`), asked of the living character.

    `pool` is "feats" (general and homebrew: anything qualified for) or "bonus" (the
    class's bonus feats, under `bonus_feat_rule`). Feats already held are left out unless
    the feat may be taken more than once.
    """
    from . import creation

    due = owed(actor)
    rule = bonus_feat_rule(actor.char_class or "") if pool == "bonus" else {}
    latest = max([p["for_level"] for p in due["bonus"]["picks"]] or [actor.level])
    rows = creation.feat_rows(
        actor,
        allow=(lambda f: _bonus_allows(actor, f, rule, latest)) if rule else None,
        waive=bool(rule.get("ignore_prereqs")))
    return {"pool": pool, "owed": due[pool]["owed"],
            "rule": due["bonus"]["rule"] if pool == "bonus" else
            "any feat they qualify for", **rows}


def _parse_feats(raw) -> list[tuple[str, str]]:
    out = []
    for f in raw or []:
        fid = str(f.get("id", "") if isinstance(f, dict) else f).strip().lower()
        target = str(f.get("target", "") if isinstance(f, dict) else "").strip().lower()
        if fid:
            out.append((fid, target))
    return out


def feat_problems(actor, raw, pool: str = "feats") -> list[str]:
    """Every reason these feats cannot all be taken now, with the fix named. Empty means
    `take_feats` may write them. Checked in order, each against the character with the
    ones before it already taken, so Power Attack and Cleave may be chosen together."""
    from . import feats as feats_mod

    if pool not in ("feats", "bonus"):
        return [f"{pool!r} is not a kind of feat pick; it is 'feats' or 'bonus'."]
    due = owed(actor)[pool]
    name = str(getattr(actor, "name", "") or "This character")
    picks = _parse_feats(raw)
    if not picks:
        return ["Choose at least one feat."]
    if not due["owed"]:
        return [f"{name} has no {'bonus ' if pool == 'bonus' else ''}feats owed for the "
                f"levels gained."]
    problems: list[str] = []
    if len(picks) > due["owed"]:
        problems.append(f"That is {len(picks)} feats against {due['owed']} owed. "
                        f"Choose {due['owed']}.")
    rule = bonus_feat_rule(actor.char_class or "") if pool == "bonus" else {}
    kept = list(actor.feats)
    try:
        for (fid, target), pick in zip(picks, due["picks"]):
            try:
                feat = feats_mod.get(fid)
            except LookupError:
                problems.append(f"No feat called {fid!r}.")
                continue
            types = {str(t).lower() for t in feat.types or ()}
            if "mythic" in types:
                problems.append(f"{feat.name} is a mythic feat, and this game has no "
                                f"mythic tiers.")
                continue
            doc = feats_mod.documents().get(feat.id)
            if feats_mod.needs_target(doc) and not target:
                problems.append(f"{feat.name} needs a weapon: send {{\"id\": "
                                f"\"{feat.id}\", \"target\": \"<weapon>\"}}.")
                continue
            line = feat.name.lower() + (f" ({target})" if target else "")
            held = {str(f).strip().lower() for f in actor.feats}
            if line in held or (feat.id in feats_mod._held(actor) and not feat.multiples):
                problems.append(f"{name} already has {feat.name}; choose another.")
                continue
            if rule and not _bonus_allows(actor, feat, rule, pick["for_level"]):
                problems.append(f"{feat.name} is not {rule.get('say', 'allowed')}; a "
                                f"bonus feat for level {pick['for_level']} must be.")
                continue
            if not rule.get("ignore_prereqs"):
                verdict = feats_mod.meets(actor, feat)
                if verdict.get("unmet"):
                    problems.append(f"{feat.name} requires "
                                    f"{', '.join(verdict['unmet'])}; {name} does not meet "
                                    f"that.")
                    continue
            actor.feats.append(line)
    finally:
        actor.feats[:] = kept
    return problems


def take_feats(actor, raw, pool: str = "feats") -> tuple[list[str], list[str]]:
    """Write owed feats onto the sheet. `(lines added, [])`, or `([], problems)` and
    nothing written. Hit points follow a feat that moves the maximum (Toughness) the way
    they follow Constitution: current travels with the maximum."""
    problems = feat_problems(actor, raw, pool)
    if problems:
        return [], problems
    from . import feats as feats_mod

    before = actor.hp_max
    added = []
    for fid, target in _parse_feats(raw):
        feat = feats_mod.get(fid)
        line = feat.name.lower() + (f" ({target})" if target else "")
        actor.feats.append(line)
        added.append(line)
    key = "bonus_feats_taken" if pool == "bonus" else "level_feats_taken"
    setattr(actor, key, int(getattr(actor, key, 0) or 0) + len(added))
    actor._follow_con(before)
    actor.rebuild_pools()
    return added, []


def _parse_points(spread) -> dict[str, int] | None:
    if not isinstance(spread, dict):
        return None
    out = {}
    for ab, n in spread.items():
        try:
            n = int(n)
        except (TypeError, ValueError):
            return None
        if n:
            out[str(ab).strip().lower()] = n
    return out


def point_problems(actor, spread) -> list[str]:
    """Every reason this spread of ability points cannot be placed, with the fix named."""
    from .tables import ABILITIES

    name = str(getattr(actor, "name", "") or "This character")
    parsed = _parse_points(spread)
    if parsed is None:
        return ["Send the points as an object of ability to points, like "
                "{\"str\": 1, \"con\": 1}."]
    if not parsed:
        return ["Place at least one point."]
    problems = []
    for ab, n in parsed.items():
        if ab not in ABILITIES:
            problems.append(f"{ab!r} is not an ability; they are "
                            f"{', '.join(ABILITIES)}.")
        elif n < 0:
            problems.append(f"{ab.title()}: points only ever raise a score.")
    due = owed(actor)["points"]["owed"]
    total = sum(n for n in parsed.values() if n > 0)
    if not due:
        problems.append(f"{name} has no ability points owed for the levels gained.")
    elif total > due:
        problems.append(f"That is {total} points against {due} owed. Place {due}.")
    return problems


def take_points(actor, spread) -> tuple[list[dict], list[str]]:
    """Raise base scores by the owed points, through `Actor.grow_ability` so a
    Constitution point pays every Hit Die already earned. `(changes, [])` or
    `([], problems)` and nothing written."""
    problems = point_problems(actor, spread)
    if problems:
        return [], problems
    changes = []
    for ab, n in _parse_points(spread).items():
        changes.append(actor.grow_ability(ab, n))
    actor.ability_points_taken = int(getattr(actor, "ability_points_taken", 0) or 0) \
        + sum(c["amount"] for c in changes)
    actor.rebuild_pools()
    return changes, []


def owed_lines(due: dict) -> list[str]:
    """What is still to choose, in the words the level-up line and the journal use."""
    out = []
    n = due["feats"]["owed"]
    if n:
        out.append(f"{n} feat{'s' if n != 1 else ''} to choose (Class tab)")
    n = due["bonus"]["owed"]
    if n:
        out.append(f"{n} bonus feat{'s' if n != 1 else ''} to choose — "
                   f"{due['bonus']['rule']} (Class tab)")
    n = due["points"]["owed"]
    if n:
        out.append(f"{n} ability point{'s' if n != 1 else ''} to place (Class tab)")
    return out


def level_up(actor, dice=None) -> dict:
    """Raise the character one level and hand back exactly what changed.

    Returns a record rather than mutating quietly: every number on this sheet is
    supposed to show where it came from, and a level that silently added seven hit
    points would be the one change on the page nobody could account for.
    """
    if int(actor.level or 1) >= MAX_LEVEL:
        return {"ok": False, "why": f"{actor.name} is already {MAX_LEVEL}th level."}

    # The gate: a level is earned, not chosen. PCs only — the GM's creatures level by
    # authorship, not ledger.
    if getattr(actor, "is_pc", False):
        from . import xp as xp_mod

        need = xp_mod.total_for(int(actor.level or 1) + 1)
        have = int(getattr(actor, "xp", 0) or 0)
        if have < need:
            return {"ok": False,
                    "why": f"{actor.name} has {have:,} XP; "
                           f"level {int(actor.level or 1) + 1} needs {need:,}."}

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

    before_max = actor.hp_max
    actor.level = new_level
    # What the level is WORTH is `hp` — the roll plus Constitution, floored at 1,
    # because 1e never lets a level cost you hit points however wretched your Con.
    # The store is the rolled base and Constitution's share is derived from the Hit
    # Dice, so the base takes the difference: a level adds `hp_base` such that the
    # derived total rises by exactly `hp`. With Con 3 (-4) and a roll of 1 that means
    # the base gains 5 so the total gains 1 — add `rolled` alone and a bad
    # Constitution would make levelling up take hit points away.
    actor.hp_base += hp - con * max(1, int(actor.hit_dice_per_level or 1))
    # Current hit points follow the whole rise of the maximum, not only the roll: a
    # feat that scales with Hit Dice moves it too. Measured live 2026-10-04: a fighter
    # with Toughness reached 4th level at 43 of 44, Toughness's +1 for the fourth Hit Die
    # added to the maximum and never to the hit points she had.
    actor.hp += max(hp, actor.hp_max - before_max)

    # Permanent ability growth the class states as data — Blood Bond's +2 Con every
    # five levels. Applied to the base score, so it survives every recompute; the
    # levels it fires on are the multiples, so a character levelled past several at
    # once is owed each of them.
    grown = []
    for g in cls.get("ability_growth", []) or []:
        every, amount = int(g.get("every", 0) or 0), int(g.get("amount", 0) or 0)
        ab = str(g.get("ability", "")).lower()
        if every > 0 and amount and ab in actor.abilities \
                and new_level % every == 0:
            # Through the applicator, not `actor.abilities[ab] += amount`: raising
            # Constitution owes every Hit Die already earned its share, and a bare
            # increment cannot reach that arithmetic. Measured on the shipped class at
            # 20th level: 100 hit points never granted — 210 against 310 owed.
            got = actor.grow_ability(ab, amount)
            grown.append(f"{ab.title()} +{amount} (permanent)")
            if got["hp_change"]:
                grown.append(f"{got['hp_change']:+d} hit points "
                             f"({ab.title()} raised every Hit Die)")
    # Pools are formulas in the class file, so they resize themselves against the new
    # level rather than being recomputed here — the whole reason they were written as
    # formulas in the first place.
    #
    # `hasattr` guarded a method that had never existed, so this silently returned []
    # for the whole life of the feature: nine levels gained in one session left a rage
    # pool at its 1st-level size of 5 when its own formula said 25, and only a reload —
    # which re-runs `classes.apply` — put it right, which is why it healed itself
    # every time anybody went looking for it.
    refreshed = actor.rebuild_pools()

    # Spells the new level owes the book, said with everything else the level gave. The
    # owner, 2026-10-01: "leveled up as a wizard and did not choose new spells". Not
    # chosen here — the choice is the player's, on the Spells tab, and stays owed (and
    # saved) until made — but said, so the level-up line and the journal both carry it.
    from . import casting

    spells_due = casting.learning(actor)["owed"]
    if spells_due:
        grown.append(f"{spells_due} new spell{'s' if spells_due != 1 else ''} to choose "
                     f"for the spellbook (Spells tab)")
    # And the feats and ability points, on the same footing: owed from the level and
    # chosen on the Class tab (`owed`). Said as a running total, so a feat left unchosen
    # at the last level is still in this line rather than forgotten behind it.
    picks = owed(actor)
    grown += owed_lines(picks)

    return {
        "ok": True, "level": new_level, "rolled": rolled, "con": con, "hp": hp,
        "hp_max": actor.hp_max,
        # Everything the level is worth — base attack, saves, slots, feats, ability
        # points, pool uses and the class's own grants (`gains_at`'s `said`) — and then
        # what it changed and what is left to choose. The line used to print the class
        # grants alone, so a wizard's 3rd level read "Gains:" and nothing.
        "grants": gains["said"] + grown, "class_grants": gains["grants"],
        "bab": gains["bab"],
        "saves": gains["saves"], "skill_ranks": gains["skill_ranks"],
        "pools": refreshed, "spells_owed": spells_due, "picks_owed": picks,
    }


def usable_names(actor) -> list[str]:
    """Every class ability this character can use right now, by name.

    One list, two readers. The scene brief computed this inline to tell the model what
    the player can do, and the engine's refusal for an unknown ability printed the
    PATHS instead — "Their paths are blood spike" — when the names were the whole point
    of the message. CLAUDE.md: when you fix a rule, grep for every copy of it; this is
    the copy.
    """
    usable: list[str] = []
    for path in getattr(actor, "paths", None) or []:
        det = path_detail(getattr(actor, "char_class", "") or "", path)
        reached = control_blood_for(actor, path)
        for tier, names in sorted((det.get("tiers") or {}).items()):
            if int(tier) <= reached:
                usable += [str(n) for n in names]
    return usable
