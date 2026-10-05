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
from pathfindergm import files

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
    """With no homebrew classes, built once per process (`rules.pristine`)."""
    global _ALL
    if _ALL is None:
        from . import pristine

        _ALL = pristine.memo("classes", [_homebrew("classes")], _build_classes)
    return _ALL


def _build_classes() -> dict[str, dict]:
    out = {k: dict(v) for k, v in SHIPPED.items()}
    for folder in (_dir("classes"), _homebrew("classes")):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                files.unreadable(path, exc)
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
    return out


def get(class_id: str) -> dict:
    """A class by id — a playable one, or a progression only a companion follows.

    The second store exists for the animal companion (`rules/animal_companion.py`): its
    Hit Dice, base attack and saves are a three-quarter-BAB, good-Fortitude-and-Reflex
    d8 progression at its Hit Dice, which is exactly what this module already derives
    for a class. Kept OUT of `all_classes()` on purpose — the forge, the Class tab and
    thirteen "build every class" tests iterate that dict, and a wolf is not a class a
    player can be.
    """
    key = (class_id or "").strip().lower()
    found = all_classes().get(key)
    if found is not None:
        return found
    from . import animal_companion

    return animal_companion.progression_classes().get(key, {})


# --- class choices ------------------------------------------------------------------------
#
# The grammar `paths` was the only instance of: a class document declares a choice made
# at a level, and the forge asks it, the build refuses without it, the sheet stores the
# answer. Written 2026-10-04 for the druid's nature bond — the owner: "The druid class
# does not work I was given no choice for my natures bond" — and shaped to carry the
# others the table still lists as bare strings (bloodline, arcane school, hunter's bond,
# divine bond, favoured enemy) once each has an option kind.
#
#   "choices": [{"id": "nature bond", "name": "Nature's Bond", "level": 1,
#                "options": [{"kind": "domain", "from": ["Air", ...], "how_many": 1},
#                            {"kind": "animal companion", "from": ["wolf", ...]}]}]
#
# The ANSWER is `class_choices` on the sheet: {"nature bond": {"option": "domain"}} with
# the domain itself in `domains` (the store casting already reads), or {"nature bond":
# {"option": "animal companion", "pick": "wolf"}}. A choice with one option needs no
# answer: the cleric has nothing to pick between, only her two domains to pick.

CHOICE_KINDS = ("domain", "animal companion")
_CHOICE_KEYS = frozenset({"id", "name", "level", "text", "options"})
_OPTION_KEYS = frozenset({"kind", "name", "text", "from", "how_many", "level_offset"})


def choices_for(class_id: str, level: int = 20) -> list[dict]:
    """The choices this class asks for by this level, in document order."""
    return [c for c in (get(class_id).get("choices") or [])
            if isinstance(c, dict) and int(c.get("level", 1) or 1) <= int(level or 1)]


def option_taken(choice: dict, answers) -> dict | None:
    """Which of a choice's options the answers took, or None when none was."""
    options = [o for o in (choice.get("options") or []) if isinstance(o, dict)]
    if len(options) == 1:
        return options[0]
    said = (answers or {}).get(str(choice.get("id"))) if isinstance(answers, dict) else None
    kind = str((said or {}).get("option", "") if isinstance(said, dict) else said or "")
    kind = " ".join(kind.split()).lower()
    return next((o for o in options if str(o.get("kind")).lower() == kind), None)


def check_choices(class_id: str, answers, domains_sent=(), level: int = 1) -> tuple[dict, list[str]]:
    """The answers as the rules will accept them, and every problem at once, with the fix.

    The generalised `leveling.check_paths`. A choice left unanswered is refused — "a druid
    was made with no nature's bond choice at all" is the defect — except that a domain
    sent with no answer IS the answer when the choice offers a domain: picking Air from
    the druid's seven is choosing the domain bond, and saying so twice is not required.
    The domain list itself is `domains.problems`' to judge; this judges the option.
    """
    from . import animal_companion

    cls = get(class_id)
    name = (member_noun(class_id) or class_id).lower()
    clean: dict[str, dict] = {}
    problems: list[str] = []
    answers = dict(answers or {}) if isinstance(answers, dict) else {}
    asked = choices_for(class_id, level)
    known_ids = {str(c.get("id")) for c in asked}
    for key in answers:
        if key not in known_ids:
            problems.append(
                f"{key!r} is not a choice a {name} makes"
                + (f": {', '.join(sorted(known_ids))}." if known_ids else "; it makes none."))
    for choice in asked:
        cid = str(choice.get("id"))
        options = [o for o in (choice.get("options") or []) if isinstance(o, dict)]
        if len(options) == 1:
            continue                      # nothing to pick between (the cleric's domains)
        option = option_taken(choice, answers)
        said = answers.get(cid)
        if option is None and said in (None, "", {}) and domains_sent and any(
                o.get("kind") == "domain" for o in options):
            option = next(o for o in options if o.get("kind") == "domain")
        title = str(choice.get("name") or cid)
        if option is None:
            kinds = " or ".join(str(o.get("name") or o.get("kind")).lower() for o in options)
            problems.append(
                f"A {name} chooses {title} at {int(choice.get('level', 1))}"
                f"{_ordinal(int(choice.get('level', 1)))} level: {kinds}. "
                f"Pick one in the class step.")
            continue
        kind = str(option.get("kind"))
        entry: dict = {"option": kind}
        if kind == "animal companion":
            raw = str((said or {}).get("pick", "") if isinstance(said, dict) else "").strip()
            pick = animal_companion.key_for(raw) or raw.lower()
            allowed = [animal_companion.key_for(a) for a in option.get("from") or []]
            if not pick:
                problems.append(
                    f"{title}: an animal companion needs an animal — one of "
                    f"{', '.join(animal_companion.name_of(a) for a in allowed)}.")
                continue
            if pick not in allowed:
                problems.append(
                    f"{title}: {pick!r} is not on a {name}'s companion list — one of "
                    f"{', '.join(animal_companion.name_of(a) for a in allowed)}.")
                continue
            entry["pick"] = pick
            # The player's own name for it, if they gave one. Words only, and short —
            # it is what the narrator will call the animal.
            called = " ".join(str((said or {}).get("name") or "").split())[:40] \
                if isinstance(said, dict) else ""
            if called:
                entry["name"] = called
        clean[cid] = entry
    _ = cls
    return clean, problems


def _ordinal(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def validate_choices(d: dict) -> list[str]:
    """Everything wrong with a class document's `choices`, each with the fix named.

    Called by `classbuilder.validate_class` (the bench refuses the class) and by the test
    that walks every shipped class, so a druid document naming a domain the corpus has
    never heard of fails on load rather than at the forge.
    """
    from . import animal_companion, domains as domains_mod

    raw = d.get("choices")
    if raw is None:
        return []
    if not isinstance(raw, list):
        return ["choices: a list of choices — [{\"id\": \"nature bond\", \"level\": 1, "
                "\"options\": [...]}]."]
    problems: list[str] = []
    seen: set[str] = set()
    for i, choice in enumerate(raw):
        at = f"choices[{i}]"
        if not isinstance(choice, dict):
            problems.append(f"{at}: a choice is an object.")
            continue
        extra = sorted(k for k in set(choice) - _CHOICE_KEYS if not str(k).startswith("_"))
        if extra:
            problems.append(f"{at}: unknown field(s) {', '.join(extra)}. A choice carries: "
                            f"{', '.join(sorted(_CHOICE_KEYS))}.")
        cid = str(choice.get("id") or "").strip()
        if not cid:
            problems.append(f"{at}: needs an id — the name the sheet stores the answer "
                            f"under, like \"nature bond\".")
        elif cid in seen:
            problems.append(f"{at}: a second choice called {cid!r}; ids are unique.")
        seen.add(cid)
        lvl = choice.get("level", 1)
        if not isinstance(lvl, int) or not 1 <= lvl <= 20:
            problems.append(f"{at}.level: the class level it is chosen at, 1-20.")
        options = choice.get("options")
        if not isinstance(options, list) or not options:
            problems.append(f"{at}.options: at least one option — "
                            f"{{\"kind\": \"domain\", \"from\": [...]}}.")
            continue
        for j, option in enumerate(options):
            oat = f"{at}.options[{j}]"
            if not isinstance(option, dict):
                problems.append(f"{oat}: an option is an object.")
                continue
            extra = sorted(k for k in set(option) - _OPTION_KEYS
                           if not str(k).startswith("_"))
            if extra:
                problems.append(f"{oat}: unknown field(s) {', '.join(extra)}. An option "
                                f"carries: {', '.join(sorted(_OPTION_KEYS))}.")
            kind = str(option.get("kind") or "")
            if kind not in CHOICE_KINDS:
                problems.append(f"{oat}.kind: {kind!r} has no reader. One of: "
                                f"{', '.join(CHOICE_KINDS)}.")
                continue
            pool = option.get("from")
            if kind == "domain":
                known = set(domains_mod.names())
                if pool not in (None, "all"):
                    if not isinstance(pool, list) or not pool:
                        problems.append(f"{oat}.from: \"all\", or a list of domain names.")
                        continue
                    for name in pool:
                        if " ".join(str(name).split()).title() not in known:
                            problems.append(
                                f"{oat}.from: no domain called {name!r} in the spell "
                                f"corpus, so it could never be picked. Spell it as the "
                                f"corpus does (Air, Animal, Earth…).")
                n = option.get("how_many", 1)
                size = len(known) if pool in (None, "all") else len(pool or [])
                if not isinstance(n, int) or not 1 <= n <= max(1, size):
                    problems.append(f"{oat}.how_many: how many domains, 1 to {size}.")
            elif kind == "animal companion":
                if not isinstance(pool, list) or not pool:
                    problems.append(f"{oat}.from: the animals offered, by key — "
                                    f"{', '.join(sorted(animal_companion.animals())[:4])}…")
                    continue
                for a in pool:
                    if animal_companion.key_for(a) not in animal_companion.animals():
                        problems.append(
                            f"{oat}.from: no companion animal called {a!r} in "
                            f"content/companions/animal-companions.json. One of: "
                            f"{', '.join(sorted(animal_companion.animals()))}.")
                off = option.get("level_offset", 0)
                if not isinstance(off, int) or off > 0:
                    problems.append(f"{oat}.level_offset: 0 or negative — the Animal "
                                    f"domain's companion is -3.")
    return problems


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
    # The uses per day a domain's powers declare (content/domains/powers.json) — Lightning
    # Arc's 3 + Wis — through the same door as the class's own pools, so they refresh on
    # a night and show on the sheet with no second mechanism. Recomputed on every load,
    # which is how a Wisdom raised at 4th reaches the pool.
    from . import domains as domains_mod

    for spec in domains_mod.pool_specs(actor):
        resources.define(actor, spec)
        made.append(spec["id"])

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
