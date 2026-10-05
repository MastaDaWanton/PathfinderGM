"""The core classes' active abilities, as documents: `content/class-abilities/*.json`.

The defect this exists for, measured 2026-10-05 (docs/class-audit.md §4): rage, smite
evil, lay on hands, ki, wild shape and bardic performance were counters only. Each pool
refilled on a night's rest and the generic `resource` op subtracted from it, but nothing
applied what the pool was FOR; `use_ability` refused all fourteen names tried on every
core class ("has no ability called rage. They can use: nothing yet."); the ability bar
and the GM's brief listed Blood Bending's path abilities and nothing else; channel energy
and stunning fist had no pool at all.

Each ability here is a document in the same `grants` vocabulary Blood Bending's paths
prove (`paths.<path>.grants`: requirements, cost, drain, modifiers, tags, tells), with the
fields a core class needs on top of it. The engine reads the FIELDS, never a name — the
grep ratchet in tests/test_three_laws.py pins that, and `Engine._use_class_ability` is the
one executor. Nothing here applies anything; this module finds a document, resolves its
numbers for one character, and answers "what can they use, and how many are left".

**Why a module and not `leveling.find_ability`.** That function searches the paths a
character follows and only those; a fighter has none. It lives in `rules/leveling.py`,
which another lane owns while class choices are rebuilt, so the core classes' lookup is
said here and the engine asks both. `leveling.usable_names` and `find_ability` stay the
path half (gm/judgement.py still asks only them — see the report of 2026-10-05).

The grammar, one ability:

- `key`, `name`, `level` (the class level it arrives at), `aliases`, `source` (the page
  the numbers came from), `text` (one line for the bar), `action` (free, swift, move,
  standard, full-round — or `{"1": "standard", "7": "move"}` by level).
- `requires`, `requires_not`: tag queries against the one vocabulary (`Actor.has_state`).
- `requires_choice`: `{"choice": "rage power", "pick": "renewed vigor"}` — the ability
  exists only for a character who chose it (lane 1's class choices, read by `chosen`).
- `pool`: a pool row (`resources.define`) for a use count the class file does not carry
  (channel energy's 3 + Cha, stunning fist's level per day). Defined on first use.
- `cost`: `{"pool": <id>, "amount": n}` — spent from the existing pools.
- `toggle`: `{"key": <condition key>, "exclusive": bool}` — a stance. Using it again ends
  it. `exclusive` ends whichever other document holds the same key (one performance at a
  time). `drain` spends a pool each round it holds, as Blood Rage's does.
- `after`: what ending a stance leaves behind — `{"condition": "fatigued",
  "rounds_per_spent": 2, "until_level": 17}` is rage's fatigue.
- `self`: the effect on the user — `modifiers`, `tags`, `rounds`, `natural_weapons`,
  `vs_target` (every modifier counts only against the creature named in `to`: smite).
- `affects`: who else it reaches — `target` (`to`), `ally` (`to`, never the user),
  `allies`, `enemies`, `all`; `radius_ft` measured on the map when there is one; `living`
  or `undead` filters; `count` caps how many.
- `effect`: the effect on each one it reaches — `modifiers`, `tags`, `condition`,
  `rounds`, `temp_hp`.
- `attack`: `"ranged touch"` or `"melee touch"`, with `range_ft` — a roll against touch AC.
- `roll`: `{"count": <formula>, "die": 6, "bonus": <formula>, "as": "heal"|"damage",
  "type": ..., "lethality": ...}` — rolled ONCE, as a fireball is, and shared.
- `save`: `{"save": "will", "dc": <formula>, "success": "half"|"negates"}`.
- `charge`: arms the user's next hit with a weapon in `weapons`: `{"weapons": [...],
  "save": {...}, "condition": ..., "rounds": ...}` (stunning fist).
- `removes`: `{"choice": "mercy", "catalogue": {"<pick>": [<condition keys>]}}` — what the
  chosen mercies lift from whoever is healed.
- `choice`: what the player names in brackets — "Wild Shape (wolf)", "Channel Energy
  (harm)", "Inspire Competence (diplomacy)". `{"kind": "mode", "options": {<name>:
  <overlay>}}` lays an overlay over the document; `"kind": "form"` reads the animal
  catalogue; `"kind": "skill"` aims a skill modifier; `"kind": "condition"` picks a rung.
- `addons`: `[{"choice": "rage power", "pick": ..., "modifiers": [...],
  "natural_weapons": [...]}]` — what a chosen rage power adds to the stance it rides.
- `not_yet`: what the book says that nothing here does yet, said out loud.

A number anywhere is `amount` (an int), `formula` (the restricted parser in
`rules/resources.py`, over `level`, `<ab>_mod` and the rest), or `by_level` rungs
(`{"1": 4, "11": 6, "20": 8}` — greater and mighty rage are rungs, not code).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# The documents, read once per process. Declared in the cache shape tests/conftest.py
# clears between tests (`test_every_content_cache_is_isolated_between_tests`).
_DOCS: dict | None = None

ACTIONS = ("free", "swift", "immediate", "move", "standard", "full-round")
AFFECTS = ("self", "target", "ally", "allies", "enemies", "all")
_KINDS = ("combat_mod", "save_mod", "ability_mod", "skill_mod", "speed")


def _folder() -> Path:
    from django.conf import settings

    return Path(settings.BASE_DIR) / "content" / "class-abilities"


def documents() -> dict[str, dict]:
    """Every class-abilities file, by its `class` (a class id, or "domain")."""
    global _DOCS
    if _DOCS is None:
        out: dict[str, dict] = {}
        folder = _folder()
        if folder.is_dir():
            for path in sorted(folder.glob("*.json")):
                doc = json.loads(path.read_text(encoding="utf-8"))
                out[str(doc.get("class", path.stem)).strip().lower()] = doc
        _DOCS = out
    return _DOCS


def _norm(text) -> str:
    return " ".join(str(text or "").replace("’", "'").split()).strip().lower()


def class_of(actor) -> str:
    return _norm(getattr(actor, "char_class", "") or "")


def level_of(actor) -> int:
    return max(1, int(getattr(actor, "level", 1) or 1))


# --- what was chosen ---------------------------------------------------------------------

def chosen(actor, choice: str) -> list[str]:
    """What this character picked for a class choice — rage powers, mercies — lowercased.

    Lane 1 of the class audit is building the writer; until it lands nothing stores these
    and the answer is empty, which every caller treats as "not chosen". The reader takes
    the shapes the existing grammar already uses (`class_choices` on the sheet, keyed by
    the choice id): a string, a list, `{"pick": X}`, `{"picks": [...]}` or
    `{"option": X}`, under the id singular or plural ("mercy" or "mercies").
    """
    answers = getattr(actor, "class_choices", None) or {}
    if not isinstance(answers, dict):
        return []
    # Lane 1's picker landed after this was written and stores `{"picks": [{"pick":
    # "animal-fury", "level": 2}]}` — catalogue ids inside records. Read as below, each
    # record became the text of a dict and no rage power or mercy picked on the sheet
    # ever matched (measured at the 2026-10-05 merge). Its own reader comes first, and
    # each pick answers to both its name and its id with the hyphens as spaces.
    from . import classes as classes_mod

    out: list[str] = []
    for p in classes_mod.chosen(actor, choice):
        for word in (p.get("name"), str(p.get("id") or "").replace("-", " ")):
            if _norm(word) and _norm(word) not in out:
                out.append(_norm(word))
    if out:
        return out
    want = _norm(choice)
    keys = {want, want + "s", want.replace(" ", "_"), want.replace(" ", "_") + "s"}
    if want.endswith("y"):
        keys.add(want[:-1] + "ies")
    for k, v in answers.items():
        if _norm(k) not in keys:
            continue
        vals = v
        if isinstance(v, dict):
            vals = v.get("picks") or v.get("pick") or v.get("option") or []
        if isinstance(vals, str):
            vals = [vals]
        out.extend(_norm(x) for x in vals or () if _norm(x))
    return out


# --- numbers ------------------------------------------------------------------------------

def amount(spec, actor, default: int = 0) -> int:
    """One number from a document: an int, a formula, or `by_level` rungs."""
    from . import resources

    if spec is None:
        return default
    if isinstance(spec, bool):
        return int(spec)
    if isinstance(spec, (int, float)):
        return int(spec)
    if isinstance(spec, str):
        try:
            return resources.evaluate(spec, actor)
        except resources.FormulaError:
            return default
    if isinstance(spec, dict):
        if "by_level" in spec:
            rung = rung_at(spec["by_level"], level_of(actor))
            return amount(rung, actor, default) if rung is not None else default
        if "formula" in spec:
            return amount(str(spec["formula"]), actor, default)
        if "amount" in spec:
            return amount(spec["amount"], actor, default)
    return default


def rung_at(rungs: dict, level: int):
    """The highest rung at or below this level, or None when none has arrived."""
    best, got = 0, None
    for at, value in (rungs or {}).items():
        if str(at).isdigit() and best < int(at) <= level:
            best, got = int(at), value
    return got


def action_of(doc: dict, actor) -> str:
    """The action this takes at this level — bardic performance quickens at 7 and 13."""
    act = doc.get("action") or "standard"
    if isinstance(act, dict):
        act = rung_at(act, level_of(actor)) or "standard"
    return str(act)


def modifiers(specs, actor) -> list[dict]:
    """A document's modifier specs as the effect store holds them, numbers worked out.

    A spec that resolves to 0 is dropped rather than stored as a dead +0 line — a rage
    power whose rung has not arrived contributes nothing, and the sheet should not say it
    does.
    """
    out = []
    for spec in specs or ():
        n = amount(spec, actor)
        if not n:
            continue
        m = {"kind": str(spec.get("type") or "combat_mod"),
             "target": str(spec.get("target") or ""),
             "amount": n, "bonus_type": str(spec.get("bonus_type") or "untyped")}
        if spec.get("when"):
            m["when"] = dict(spec["when"])
        out.append(m)
    return out


def dice(spec: dict, actor) -> str:
    """A roll's notation for this character — "3d6", "1d6+2"."""
    count = max(0, amount(spec.get("count", 1), actor, 1))
    if not count:
        return ""
    out = f"{count}d{int(spec.get('die', 6) or 6)}"
    bonus = amount(spec.get("bonus"), actor, 0)
    if bonus:
        out += f"{bonus:+d}"
    return out


# --- finding them ---------------------------------------------------------------------------

def _docs_for(actor) -> list[dict]:
    """Every document this character's class carries, plus their domains' powers, each
    stamped with the `class` it came from (the provenance stem)."""
    out: list[dict] = []
    cid = class_of(actor)
    own = documents().get(cid) or {}
    for doc in own.get("abilities") or ():
        out.append({**doc, "class": cid})
    domain_doc = documents().get("domain") or {}
    if domain_doc:
        from . import domains

        had = {_norm(p.get("key") or p.get("name")) for _d, p in domains.powers_had(actor)}
        for doc in domain_doc.get("abilities") or ():
            if _norm(doc.get("power") or doc.get("key")) in had:
                out.append({**doc, "class": "domain"})
    return out


def _names_of(doc: dict) -> list[str]:
    return [_norm(doc.get("name"))] + [_norm(a) for a in doc.get("aliases") or ()]


def _has_it(actor, doc: dict) -> bool:
    if int(doc.get("level", 1) or 1) > level_of(actor):
        return False
    need = doc.get("requires_choice") or {}
    if need and _norm(need.get("pick")) not in chosen(actor, need.get("choice", "")):
        return False
    return True


def _match(wanted: str, doc: dict) -> tuple[int, str] | None:
    """(how much of the words the name took, the bracketed choice after it), or None if
    the words do not name this document.

    "wild shape (wolf)", "wild shape: wolf", "wild shape into a wolf" and "channel energy
    to harm" all name the document with a choice; the name alone is the choice-less use.
    """
    want = _norm(wanted)
    best: tuple[int, str] | None = None
    for name in _names_of(doc):
        if not name:
            continue
        if want == name:
            return len(name), ""
        if want.startswith(name) and not want[len(name)].isalnum():
            rest = want[len(name):].strip()
            rest = rest.strip("()[]:,-—– ").strip()
            rest = re.sub(r"^(?:into|as|to|on|for|with)\s+(?:an?\s+|the\s+)?", "", rest)
            rest = rest.strip("()[] ").strip()
            if rest and (best is None or len(name) > best[0]):
                best = (len(name), rest)
    return best


def find(actor, wanted: str) -> tuple[dict | None, str]:
    """The document by that name this character has, and the choice named with it.

    The longest name wins: "inspire competence (diplomacy)" also begins with Inspire
    Courage's alias "inspire", and measured on the first run it struck up the courage.

    `(None, "")` when they have no such ability — including one their class prints at a
    level they have not reached (`arrives_at` says which).
    """
    best: tuple[int, dict, str] | None = None
    for doc in _docs_for(actor):
        got = _match(wanted, doc)
        if got is None:
            continue
        if best is None or got[0] > best[0]:
            best = (got[0], doc, got[1])
    # Decided over every document the class prints, had or not: a 1st-level bard's
    # "inspire competence" is that ability, not yet hers — never her Inspire Courage with
    # "competence" read as its choice.
    if best is None or not _has_it(actor, best[1]):
        return None, ""
    return best[1], best[2]


def arrives_at(actor, wanted: str) -> int:
    """The class level this ability arrives at, when the class has it but they are below
    it; 0 otherwise."""
    best: tuple[int, dict] | None = None
    for doc in _docs_for(actor):
        got = _match(wanted, doc)
        if got is not None and (best is None or got[0] > best[0]):
            best = (got[0], doc)
    if best is not None and int(best[1].get("level", 1) or 1) > level_of(actor):
        return int(best[1].get("level", 1) or 1)
    return 0


def names(actor) -> list[str]:
    """The names this character can use, for a refusal that names the fix."""
    return [str(d["name"]) for d in _docs_for(actor) if _has_it(actor, d)]


def ensure_pool(actor, doc: dict) -> None:
    """Define the pool a document declares, if the class file does not.

    Channel energy is 3 + Cha a day and stunning fist a monk's level; neither is in its
    class file (the audit's "Missing" row). `resources.define` recomputes the maximum and
    leaves the current value alone, so calling this on every use is how a level gained
    reaches the count.
    """
    from . import resources

    spec = doc.get("pool")
    if isinstance(spec, dict) and spec.get("id"):
        resources.define(actor, {**spec, "source": spec.get("source") or doc.get("name")})


def uses_left(actor, doc: dict) -> tuple[int | None, int | None, str]:
    """(left, most, pool id) for the bar; (None, None, "") for a free-for-all ability.

    Read-only: a pool the document declares and the character has never touched is shown
    at its maximum without being created, so drawing the bar changes nothing.
    """
    from . import resources

    cost = doc.get("cost") or {}
    pid = _norm(cost.get("pool"))
    if not pid:
        return None, None, ""
    pool = actor.pool(pid)
    if pool is not None:
        return pool.current, pool.maximum, pid
    spec = doc.get("pool")
    if isinstance(spec, dict) and _norm(spec.get("id")) == pid:
        try:
            most = resources.evaluate(spec.get("max", 0), actor)
        except resources.FormulaError:
            most = 0
        return most, most, pid
    return 0, 0, pid


def toggle_key(doc: dict) -> str:
    return _norm((doc.get("toggle") or {}).get("key"))


def holding(actor, doc: dict):
    """The standing effect this document's toggle put on the actor, or None."""
    key = toggle_key(doc)
    if not key:
        return None
    return next((e for e in actor.effects if e.kind == "condition" and e.key == key), None)


def origin_of(doc: dict) -> str:
    return f"ability:{doc.get('class')}/{_norm(doc.get('key') or doc.get('name'))}"


def choices_of(actor, doc: dict) -> list[str]:
    """What may go in the brackets, for this character at this level."""
    spec = doc.get("choice") or {}
    kind = spec.get("kind")
    level = level_of(actor)
    if kind == "mode":
        return [k for k, v in (spec.get("options") or {}).items()
                if int((v or {}).get("level", 1) or 1) <= level]
    if kind == "condition":
        return [k for k, v in (spec.get("options") or {}).items()
                if int((v or {}).get("level", 1) or 1) <= level]
    if kind == "skill":
        from .tables import SKILLS

        return sorted(SKILLS)
    if kind == "form":
        return sorted(forms_for(actor, doc))
    return []


def forms_for(actor, doc: dict) -> dict[str, dict]:
    """The animals this character may become, at this level, by key.

    Read off the druid's own animal catalogue (`content/companions/animal-companions.json`)
    because it is the list of animals the class already knows by size and attack — a
    second bestiary of "wild shape animals" would drift from it on the first edit.
    """
    from . import animal_companion

    spec = doc.get("choice") or {}
    sizes = rung_at(spec.get("sizes") or {}, level_of(actor)) or []
    allowed = {_norm(s) for s in sizes}
    return {k: v for k, v in animal_companion.animals().items()
            if _norm(v.get("size")) in allowed}


def usable(actor) -> list[dict]:
    """Every ability for the bar and the brief: name, action, uses, toggle state, choices.

    The bar's list and the brief's list are this one list, for the reason
    `leveling.usable_names` gives: two copies drift, and the brief once named paths where
    the model needed abilities.
    """
    out = []
    for doc in _docs_for(actor):
        if not _has_it(actor, doc):
            continue
        left, most, pid = uses_left(actor, doc)
        held = holding(actor, doc)
        entry = {"name": str(doc["name"]), "class": str(doc.get("class") or ""),
                 "action": action_of(doc, actor),
                 "text": f"{action_of(doc, actor)} — {doc.get('text') or ''}".strip(" —"),
                 "aim": str(doc.get("aim") or ("self" if (doc.get("affects") or "self")
                                                in ("self", "allies") else "foe")),
                 "origin": origin_of(doc)}
        if pid:
            cost = int((doc.get("cost") or {}).get("amount", 1) or 1)
            entry.update({"uses": left, "max": most, "pool": pid, "cost": cost})
        if toggle_key(doc):
            entry["toggle"] = True
            entry["active"] = bool(held is not None and held.origin == origin_of(doc))
        picks = choices_of(actor, doc)
        kind = (doc.get("choice") or {}).get("kind")
        if kind:
            entry["choice_kind"] = str(kind)
        if picks and kind != "skill":
            entry["choices"] = picks
        out.append(entry)
    return out


# --- the document, with the choice laid over it -----------------------------------------

def with_choice(actor, doc: dict, choice: str) -> tuple[dict, str]:
    """The document as this use of it reads, and a refusal sentence when the choice is
    wrong ("" when it is fine).

    A refusal names every option this character has, which is the fix.
    """
    spec = doc.get("choice") or {}
    kind = spec.get("kind")
    name = str(doc.get("name"))
    pick = _norm(choice)
    if not kind:
        return doc, ""
    options = choices_of(actor, doc)
    if not pick:
        default = spec.get("default")
        if default and _norm(default) in options:
            pick = _norm(default)
        elif kind == "skill" and doc.get("default_skill"):
            pick = _norm(doc["default_skill"])
        else:
            shown = ", ".join(f"{name} ({o})" for o in options) or "none at this level"
            return doc, f"{name} needs a {kind} named with it: {shown}."
    if kind == "skill":
        from .tables import SKILLS

        if pick not in SKILLS:
            return doc, (f"{name} is aimed at one skill, and {choice!r} is not one: "
                         f"{', '.join(sorted(SKILLS))}.")
        out = dict(doc)
        out["skill"] = pick
        return out, ""
    if kind == "form":
        forms = forms_for(actor, doc)
        from . import animal_companion

        key = animal_companion.key_for(pick) if pick not in forms else pick
        if key not in forms:
            shown = ", ".join(f"{name} ({o})" for o in sorted(forms)) or "none at this level"
            return doc, f"{name} has no form called {choice!r} at level {level_of(actor)}: {shown}."
        out = dict(doc)
        out["form"] = {"key": key, **forms[key]}
        return out, ""
    # mode / condition: an overlay from the options.
    table = {_norm(k): v for k, v in (spec.get("options") or {}).items()}
    if pick not in table or pick not in options:
        later = table.get(pick)
        if later is not None:
            return doc, (f"{name} ({pick}) arrives at level {int(later.get('level', 1))}; "
                         f"at {level_of(actor)} it is: "
                         + ", ".join(f"{name} ({o})" for o in options) + ".")
        return doc, (f"{name} has no {kind} called {choice!r}: "
                     + ", ".join(f"{name} ({o})" for o in options) + ".")
    overlay = {k: v for k, v in (table[pick] or {}).items() if k != "level"}
    out = {**doc, **overlay}
    # The energy a cleric channels is a choice of hers (the app has no alignment to read
    # it off): negative swaps who the burst heals and who it harms, as the book's
    # evil cleric does.
    if doc.get("energy_choice") and "negative" in chosen(actor, doc["energy_choice"]):
        out.update((doc.get("negative") or {}).get(pick) or {})
    out["picked"] = pick
    return out, ""


# --- validation ----------------------------------------------------------------------------

def validate_documents(docs: dict | None = None) -> list[str]:
    """Every problem with the documents, each with the fix named — the classbuilder's voice.

    A cost naming a pool nothing defines is an ability that is refused forever with no
    reason anybody could act on; a modifier aimed at a kind the effect store has no reader
    for is a number that is shown and never rolled.
    """
    from . import classes as classes_mod, resources

    docs = documents() if docs is None else docs
    problems: list[str] = []
    for cid, file in docs.items():
        class_pools: set[str] = set()
        if cid != "domain":
            cls = classes_mod.all_classes().get(cid)
            if not cls:
                problems.append(f"{cid}: no class called {cid!r} — name the file's "
                                f"`class` as content/classes/ does.")
                continue
            class_pools = {_norm(p.get("id")) for p in cls.get("pools") or ()}
        for i, doc in enumerate(file.get("abilities") or ()):
            at = f"{cid}.abilities[{i}] ({doc.get('name')})"
            if not doc.get("key") or not doc.get("name"):
                problems.append(f"{at}: needs a `key` and a `name`.")
            if not doc.get("source"):
                problems.append(f"{at}: say where the numbers came from in `source`.")
            act = doc.get("action") or "standard"
            for a in (act.values() if isinstance(act, dict) else [act]):
                if a not in ACTIONS:
                    problems.append(f"{at}: action {a!r} is not one of {', '.join(ACTIONS)}.")
            if (doc.get("affects") or "self") not in AFFECTS:
                problems.append(f"{at}: affects {doc.get('affects')!r} is not one of "
                                f"{', '.join(AFFECTS)}.")
            pools = set(class_pools)
            if isinstance(doc.get("pool"), dict):
                pools.add(_norm(doc["pool"].get("id")))
                if doc["pool"].get("max") not in (None, ""):
                    bad = resources.check(doc["pool"]["max"])
                    if bad:
                        problems.append(f"{at}: pool max — {bad}")
            if cid == "domain":
                pools.add(_norm(doc.get("power") or doc.get("key")))
            for side in ("cost", "drain"):
                pid = _norm((doc.get(side) or {}).get("pool"))
                if pid and pid not in pools:
                    problems.append(
                        f"{at}: {side} spends {pid!r}, which neither the class file nor "
                        f"this document's `pool` defines. Pools here: "
                        f"{', '.join(sorted(p for p in pools if p)) or 'none'}.")
            for where in ("self", "effect"):
                for m in (doc.get(where) or {}).get("modifiers") or ():
                    if str(m.get("type") or "combat_mod") not in _KINDS:
                        problems.append(f"{at}: {where} modifier type {m.get('type')!r} "
                                        f"is not one of {', '.join(_KINDS)}.")
            if doc.get("attack") not in (None, "ranged touch", "melee touch"):
                problems.append(f"{at}: attack {doc.get('attack')!r} must be 'ranged "
                                f"touch' or 'melee touch'.")
    return problems
