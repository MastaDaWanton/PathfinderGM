"""Granted powers: what a chosen domain, bloodline, arcane school or arcane bond DOES.

Measured 2026-10-05 (docs/class-audit.md §1, §3): a cleric's Sun domain gave **nothing**
(7 of 153 domains had a power written down), a sorcerer's bloodline and a wizard's school
could not even be chosen, and once lane 1 built the pickers the choice was stored and read
by nothing — a 1st-level draconic sorcerer had no claws, no bonus spell at 3rd and no
resistance at 3rd; a 1st-level evoker had no force missile and no specialist slot.

**One reader for four kinds of choice**, because they are one shape in the book and in
every builder that models them (audit §5: "a choice made at 1st whose effects arrive
later is one document carrying its own level-gated grants, re-read against the class
level" — Foundry's level-gated supplements, PCGen's PREVARGTEQ, Hero Lab's bootstraps
with level conditions). A domain, a bloodline, a school and a bond each name an ENTRY;
the entry carries `powers`; each power arrives at a class level and may climb by
`by_level` rungs. Nothing is copied onto the sheet: every reader here asks the choice
and the document live, the way `Actor._feat_mods` reads the feat list — a corrected
document corrects every character, and a power lost leaves nothing behind.

Where the documents are, and which choice each hangs on, is the documents' own business:

    content/domains/powers.json       the character's `domains` (cleric, druid's bond)
    content/bloodlines/powers.json    {"choice": "bloodline", "entries": {...}}
    content/schools/powers.json       {"choice": "arcane school", ...}
    content/schools/bonds.json        {"choice": "arcane bond", ...}

So no class and no choice is named in this code: a file says which class choice it
answers (`classes.chosen` is the one door to it, lane 1's read API), and a homebrew class
with a choice of its own gets powers by shipping a file.

A power is a document in the class `grants` vocabulary (the domains file's original
grammar, widened):

    key, name, level, kind, line   the power; `level` is the class level it arrives at
    pool, cost                     uses per day (a `resources.define` row) and the spend
    tags                           held while the power is had (`resist.fire.10`)
    modifiers                      passive numbers through the one funnel — the feat and
                                   class-feature grammar (`type`, `target`, `amount` |
                                   `formula`, `bonus_type`, `when`); read by
                                   `Actor._class_mods`, never stored
    class_skills, feats            what the power makes a class skill / hands over as a feat
    by_level                       {"9": {...}} rungs laid over the power at that level
    by_variant                     {"red": {...}} laid over by the variant picked with the
                                   choice (a dragon, an element, a familiar)
    not_yet                        what the book says that nothing here does yet, out loud
    action, attack, range_ft, roll, save, effect, self, affects, aim, toggle, drain,
    tell, tell_off, text, source, radius_ft, count, charge, aliases
                                   USING the power: the activation grammar of
                                   rules/class_abilities.py (lane 4 of the audit). This
                                   module validates and serves them (`ability_documents`)
                                   and applies none of them — the engine's one executor
                                   does, so the engine still names no class.

`$energy`, `$breath`, `$movement`, `$object`, `$element` in any string are the variant's
own fields (the catalogue's `variants.from[]`: a red dragon's `energy` is "fire").
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# Shipped with the install and never overlaid from a campaign (the class-features reader
# makes the same choice), so deliberately NOT the `_NAME: ... | None = None` cache shape
# the isolation ratchet in tests/test_three_laws.py reads as "merged with homebrew".
_FILES: dict[str, dict] = {}

FOLDERS = ("bloodlines", "schools")

POWER_KEYS = frozenset({
    "key", "name", "level", "kind", "line", "pool", "cost", "tags", "by_level", "by_variant",
    "not_yet", "modifiers", "class_skills", "feats",
    # the activation grammar (rules/class_abilities.py, lane 4) — served, never applied here
    "action", "attack", "range_ft", "reach_ft", "roll", "save", "effect", "self", "affects",
    "aim", "toggle", "drain", "tell", "tell_off", "text", "source", "radius_ft", "count",
    "charge", "aliases", "harmful", "living", "undead_only", "choice", "after",
})
ENTRY_KEYS = frozenset({"powers", "class_skills", "not_yet", "spells", "note", "replaces",
                        "parent"})
ACTIVATION = ("action", "attack", "roll", "save", "effect", "self", "affects", "toggle",
              "charge")
# The activation vocabulary lane 4's executor reads (rules/class_abilities.py: ACTIONS,
# AFFECTS, `attack`). Repeated here, not imported, because that module is on another lane's
# unmerged branch; tests/test_granted_powers.py compares the two when both are present.
ACTIONS = ("free", "swift", "immediate", "move", "standard", "full-round")
AFFECTS = ("self", "target", "ally", "allies", "enemies", "all")
ATTACKS = ("ranged touch", "melee touch")
MOD_TYPES = ("ability_mod", "skill_mod", "save_mod", "combat_mod", "speed")
MOD_KEYS = frozenset({"type", "target", "amount", "formula", "bonus_type", "when", "note"})
_PLACEHOLDER = re.compile(r"\$([a-z_]+)")


def _norm(text) -> str:
    return " ".join(str(text or "").replace("’", "'").split()).strip().lower()


def _content() -> Path:
    from django.conf import settings

    return Path(settings.BASE_DIR) / "content"


def forget() -> None:
    _FILES.clear()


def files() -> dict[str, dict]:
    """Every choice-keyed powers file (content/bloodlines, content/schools), by path."""
    if not _FILES:
        for folder in FOLDERS:
            base = _content() / folder
            if not base.is_dir():
                continue
            for path in sorted(base.glob("*.json")):
                try:
                    _FILES[f"{folder}/{path.name}"] = json.loads(
                        path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
    return _FILES


# --- where a character's powers come from ---------------------------------------------------

def level_of(actor) -> int:
    """The class level a power reads. Single-classed: the character's level. A druid's
    domain uses her druid level (CRB Nature Bond); a sorcerer's bloodline, her sorcerer
    level; a wizard's school, his wizard level."""
    return max(1, int(getattr(actor, "level", 1) or 1))


def _variant_fields(pick: dict) -> dict:
    """The chosen variant's own fields — {"id": "red", "energy": "fire", ...} — read off
    the catalogue entry `classes.chosen` already handed over."""
    want = _norm(pick.get("variant"))
    if not want:
        return {}
    spec = (pick.get("entry") or {}).get("variants") or {}
    for v in spec.get("from") or ():
        if isinstance(v, dict) and _norm(v.get("id")) == want:
            out = {k: v[k] for k in v if isinstance(v[k], (str, int))}
            # `$element` names an elemental bloodline's element and `$object` a bonded
            # object: both are the variant's id.
            out.setdefault("element", v.get("id"))
            out.setdefault("object", v.get("id"))
            out.setdefault("familiar", v.get("id"))
            return out
    return {"id": want, "element": want, "object": want, "familiar": want}


def sources(actor) -> list[dict]:
    """Every entry this character's choices name, with what to read it by:
    `{"label": "Fire domain", "kind": "domain", "id", "entry": {...powers file entry},
    "pick": {...classes.chosen row or {}}, "vars": {...variant fields}}`."""
    from . import domains as domains_mod

    out: list[dict] = []
    for name in domains_mod.of(actor):
        entry = domains_mod.entry_of(name)
        out.append({"label": f"{name} domain", "kind": "domain", "id": name,
                    "entry": entry, "pick": {}, "vars": {}})
    if not getattr(actor, "char_class", ""):
        return out
    from . import classes as classes_mod

    for _path, doc in files().items():
        choice = str(doc.get("choice") or "")
        if not choice:
            continue
        noun = str(doc.get("label") or choice)
        entries = {_norm(k): v for k, v in (doc.get("entries") or {}).items()}
        for pick in classes_mod.chosen(actor, choice):
            entry = entries.get(_norm(pick.get("id")))
            if not isinstance(entry, dict):
                continue
            out.append({"label": f"{pick.get('name') or pick.get('id')} {noun}",
                        "kind": noun, "id": _norm(pick.get("id")), "entry": entry,
                        "pick": pick, "vars": _variant_fields(pick)})
    return out


def _substitute(value, vars_: dict):
    if isinstance(value, str):
        return _PLACEHOLDER.sub(lambda m: str(vars_.get(m.group(1), m.group(0))), value)
    if isinstance(value, list):
        return [_substitute(v, vars_) for v in value]
    if isinstance(value, dict):
        return {k: _substitute(v, vars_) for k, v in value.items()}
    return value


def resolve(power: dict, level: int, vars_: dict | None = None) -> dict:
    """The power as it stands at this level for this variant: the highest `by_level` rung
    at or below the level laid over it, then the variant's overlay, then `$energy` and its
    kind filled in."""
    out = {k: v for k, v in power.items() if k not in ("by_level", "by_variant")}
    best = 0
    for at, rung in sorted(((int(a), r) for a, r in (power.get("by_level") or {}).items()
                            if str(a).isdigit()), key=lambda p: p[0]):
        if best < at <= level and isinstance(rung, dict):
            best = at
            out.update(rung)
    vars_ = vars_ or {}
    variant = _norm(vars_.get("id"))
    overlay = {_norm(k): v for k, v in (power.get("by_variant") or {}).items()}.get(variant)
    if isinstance(overlay, dict):
        out.update(overlay)
    return _substitute(out, vars_) if vars_ else out


def had(actor) -> list[dict]:
    """Every power this character has right now, resolved: `{"label", "kind", "power"}`.
    A power whose `level` the class level has not reached is not had."""
    level = level_of(actor)
    out = []
    for src in sources(actor):
        for power in (src["entry"].get("powers") or ()):
            if not isinstance(power, dict) or int(power.get("level", 1) or 1) > level:
                continue
            out.append({"label": src["label"], "kind": src["kind"], "id": src["id"],
                        "power": resolve(power, level, src["vars"])})
    return out


# --- the readers -----------------------------------------------------------------------------

def standing_tags(actor) -> list[str]:
    """The tags held right now — `resist.fire.10`, `immune.electricity` — joined to
    `Actor.standing_tags`, so `resistance()` and `immune_to()` answer with no second
    reader."""
    out: list[str] = []
    for row in had(actor):
        for tag in row["power"].get("tags") or ():
            if str(tag).strip() and tag not in out:
                out.append(str(tag))
    return out


def pool_specs(actor) -> list[dict]:
    """The uses-per-day pools the powers declare, as `resources.define` rows, defined by
    `classes.apply` beside the class's own pools (one door, one refresh on a night)."""
    out = []
    seen: set[str] = set()
    for row in had(actor):
        power = row["power"]
        spec = power.get("pool")
        pid = _norm(power.get("key") or power.get("name"))
        if isinstance(spec, dict) and spec.get("max") not in (None, "") and pid not in seen:
            seen.add(pid)
            out.append({"id": pid, "max": spec["max"], "starts": "max",
                        "refresh": spec.get("refresh", "rest.night"),
                        "source": row["label"]})
    return out


def modifiers(actor, kind: str, target: str, ctx: dict | None = None) -> list:
    """Every passive term these powers put on one number, as the funnel's `Modifier`s,
    each named for its power so the dice popup says where it came from. Called from
    `Actor._class_mods`, inside its re-entrancy guard (a formula reads `wis_mod`, and an
    ability score reads the funnel)."""
    from . import classfeatures, resources
    from .sheet import Modifier, _bonus_type

    want = _norm(target)
    out = []
    for row in had(actor):
        power = row["power"]
        for spec in power.get("modifiers") or ():
            if not isinstance(spec, dict) or spec.get("type") != kind \
                    or _norm(spec.get("target")) != want:
                continue
            if not classfeatures.holds(spec.get("when"), actor, ctx):
                continue
            try:
                amount = (resources.evaluate(spec["formula"], actor)
                          if spec.get("formula") is not None
                          else int(spec.get("amount", 0) or 0))
            except Exception:  # noqa: BLE001 — a malformed formula grants nothing
                amount = 0
            if amount:
                out.append(Modifier(amount, str(power.get("name") or row["label"]),
                                    _bonus_type(spec.get("bonus_type"))))
    return out


def class_skills(actor) -> list[str]:
    """Skills a choice makes class skills: a bloodline's (the catalogue's `class_skill`),
    a domain's (Knowledge: every Knowledge skill; Trickery: Bluff, Disguise, Stealth), and
    any power's own `class_skills`."""
    out: list[str] = []

    def add(skill):
        s = _norm(skill)
        if s and s not in out:
            out.append(s)

    for src in sources(actor):
        for s in src["entry"].get("class_skills") or ():
            add(s)
        cat = (src.get("pick") or {}).get("entry") or {}
        if cat.get("class_skill"):
            add(cat["class_skill"])
    for row in had(actor):
        for s in row["power"].get("class_skills") or ():
            add(s)
    return out


def granted_feats(actor) -> list[str]:
    """Feat ids a power hands over (Darkness's Blind-Fight, Rune's Scribe Scroll,
    Nobility's Leadership at 8th) — written by `leveling.grant_class_feats` with the
    class's own, at the forge and at each level."""
    out: list[str] = []
    for row in had(actor):
        for fid in row["power"].get("feats") or ():
            if _norm(fid) and _norm(fid) not in out:
                out.append(_norm(fid))
    return out


def power_lines(actor) -> list[dict]:
    """What the sheet shows: each power had, where it comes from, its line, its uses, and
    what is not built yet. `domain` is kept for the domain rows the page drew first."""
    out = []
    for row in had(actor):
        p = row["power"]
        pid = _norm(p.get("key") or p.get("name"))
        pool = actor.pool(pid) if hasattr(actor, "pool") else None
        line = {"source": row["label"], "kind_of": row["kind"],
                "name": str(p.get("name") or p.get("key")), "kind": str(p.get("kind") or ""),
                "line": str(p.get("line") or ""),
                "usable": bool(p.get("action")),
                "not_yet": [str(n) for n in p.get("not_yet") or ()]}
        if row["kind"] == "domain":
            line["domain"] = row["id"]
        if pool is not None and isinstance(p.get("pool"), dict):
            line.update({"uses": pool.current, "max": pool.maximum})
        out.append(line)
    return out


def ability_documents(actor) -> list[dict]:
    """The powers USED as actions, as rules/class_abilities.py documents: `class` is the
    kind ("domain", "bloodline", "school", "arcane bond") so the provenance stem reads
    `ability:bloodline/claws`; `pool` carries the id the cost spends. The executor is lane
    4's; this is the list it would read beside the class's own documents."""
    out = []
    seen: set[str] = set()
    for row in had(actor):
        p = row["power"]
        if not p.get("action"):
            continue
        key = _norm(p.get("key") or p.get("name"))
        if key in seen:
            continue
        seen.add(key)
        doc = {k: v for k, v in p.items() if k not in ("pool", "tags", "modifiers",
                                                        "class_skills", "feats", "line",
                                                        "kind")}
        doc.update({"key": key, "name": str(p.get("name") or key), "level": 1,
                    "class": row["kind"], "power_of": row["label"]})
        doc.setdefault("text", str(p.get("line") or ""))
        doc.setdefault("source", f"{row['label']}: {p.get('line') or ''}".strip())
        if isinstance(p.get("pool"), dict):
            doc["pool"] = {"id": key, **p["pool"]}
        out.append(doc)
    return out


# --- validation ------------------------------------------------------------------------------

def validate_power(power, at: str, variants: set[str] | None = None) -> list[str]:
    """Every problem with one power document, each with the fix named — the classbuilder's
    voice, because a power whose pool has no max is never usable and nothing would say
    why, and a modifier aimed at a kind nobody reads is a number shown and never rolled."""
    from . import classfeatures, resources

    problems: list[str] = []
    if not isinstance(power, dict):
        return [f"{at}: a power is an object."]
    extra = sorted(set(power) - POWER_KEYS)
    if extra:
        problems.append(f"{at}: unknown field(s) {', '.join(extra)}; the reader would ignore "
                        f"them. A power carries: {', '.join(sorted(POWER_KEYS))}.")
    key = _norm(power.get("key"))
    if not key:
        problems.append(f"{at}: needs a key — the pool's id and the power's name in lower "
                        f"case.")
    lvl = power.get("level")
    if not isinstance(lvl, int) or not 1 <= lvl <= 20:
        problems.append(f"{at}.level: the class level it arrives at, 1-20.")
    layers = [("", power)]
    layers += [(f".by_level.{k}", v) for k, v in (power.get("by_level") or {}).items()]
    layers += [(f".by_variant.{k}", v) for k, v in (power.get("by_variant") or {}).items()]
    for k in (power.get("by_level") or {}):
        if not str(k).isdigit():
            problems.append(f"{at}.by_level: rungs keyed by class level, "
                            f"{{\"12\": {{\"tags\": [...]}}}}.")
    if variants is not None:
        for k in (power.get("by_variant") or {}):
            if _norm(k) not in variants:
                problems.append(f"{at}.by_variant.{k}: no such variant; the catalogue "
                                f"offers {', '.join(sorted(variants)) or 'none'}.")
    for where, layer in layers:
        if not isinstance(layer, dict):
            problems.append(f"{at}{where}: an object of fields to lay over the power.")
            continue
        pool = layer.get("pool")
        if pool is not None and (not isinstance(pool, dict)
                                 or resources.check(pool.get("max"))):
            problems.append(f"{at}{where}.pool: {{\"max\": \"3 + wis_mod\", \"refresh\": "
                            f"\"rest.night\"}} — a formula over the sheet.")
        cost = layer.get("cost")
        if cost is not None and (not isinstance(cost, dict)
                                 or _norm(cost.get("pool")) != key):
            problems.append(f"{at}{where}.cost: spends its own pool — "
                            f"{{\"pool\": \"{power.get('key', '')}\", \"amount\": 1}}.")
        for i, m in enumerate(layer.get("modifiers") or ()):
            mat = f"{at}{where}.modifiers[{i}]"
            if not isinstance(m, dict):
                problems.append(f"{mat}: a modifier is an object.")
                continue
            if sorted(set(m) - MOD_KEYS):
                problems.append(f"{mat}: unknown field(s) "
                                f"{', '.join(sorted(set(m) - MOD_KEYS))}.")
            if m.get("type") not in MOD_TYPES:
                problems.append(f"{mat}.type: one of {', '.join(MOD_TYPES)}.")
            if not str(m.get("target") or "").strip():
                problems.append(f"{mat}.target: the number it moves (\"ac\", \"will\", "
                                f"\"land_base\", a skill).")
            if m.get("formula") is not None:
                bad = classfeatures.check_formula(m["formula"])
                if bad:
                    problems.append(f"{mat}.formula: {bad}")
            elif not isinstance(m.get("amount"), int):
                problems.append(f"{mat}: an `amount` (a whole number) or a `formula`.")
        for field_name in ("tags", "not_yet", "class_skills", "feats", "aliases"):
            got = layer.get(field_name)
            if got is not None and (not isinstance(got, list)
                                    or any(not str(t).strip() for t in got)):
                problems.append(f"{at}{where}.{field_name}: a list of strings.")
        act = layer.get("action")
        if act is not None:
            for a in (act.values() if isinstance(act, dict) else [act]):
                if a not in ACTIONS:
                    problems.append(f"{at}{where}.action: {a!r} is not one of "
                                    f"{', '.join(ACTIONS)}.")
        if layer.get("affects") is not None and layer["affects"] not in AFFECTS:
            problems.append(f"{at}{where}.affects: one of {', '.join(AFFECTS)}.")
        if layer.get("attack") is not None and layer["attack"] not in ATTACKS:
            problems.append(f"{at}{where}.attack: {' or '.join(ATTACKS)}.")
    used = any(power.get(k) is not None for k in ACTIVATION if k != "action")
    if used and not power.get("action"):
        problems.append(f"{at}: an attack, roll, save or effect with no `action` is never "
                        f"offered — say what action using it takes.")
    if power.get("action") and not power.get("tell"):
        problems.append(f"{at}: a power used as an action needs a `tell` (the third law: "
                        f"every application says what happened).")
    return problems


def validate(doc_files: dict | None = None) -> list[str]:
    """Every problem across the choice-keyed powers files, against the catalogues their
    choices draw from."""
    from . import classes as classes_mod

    problems: list[str] = []
    for path, doc in (files() if doc_files is None else doc_files).items():
        choice = str(doc.get("choice") or "")
        if not choice:
            problems.append(f"{path}: names no `choice` — the class choice whose picks "
                            f"are its entries (\"bloodline\").")
            continue
        catalogue_ids: dict[str, set[str]] = {}
        for cls in classes_mod.all_classes().values():
            for ch in cls.get("choices") or ():
                if _norm(ch.get("id")) != _norm(choice):
                    continue
                for opt in ch.get("options") or ():
                    for e in classes_mod.catalogue(str(opt.get("from") or "")).get(
                            "options") or ():
                        catalogue_ids[_norm(e.get("id"))] = set(classes_mod._variants(e))
        if not catalogue_ids:
            problems.append(f"{path}: no class asks the choice {choice!r} from a catalogue.")
        for eid, entry in (doc.get("entries") or {}).items():
            at = f"{path}.entries.{eid}"
            if catalogue_ids and _norm(eid) not in catalogue_ids:
                problems.append(f"{at}: no entry {eid!r} in the {choice!r} catalogue: "
                                f"{', '.join(sorted(catalogue_ids))}.")
            if not isinstance(entry, dict):
                problems.append(f"{at}: an entry is an object with `powers`.")
                continue
            extra = sorted(set(entry) - ENTRY_KEYS)
            if extra:
                problems.append(f"{at}: unknown field(s) {', '.join(extra)}.")
            variants = catalogue_ids.get(_norm(eid))
            for i, power in enumerate(entry.get("powers") or ()):
                problems += validate_power(power, f"{at}.powers[{i}]",
                                           variants if variants else None)
    return problems


__all__ = ["ability_documents", "class_skills", "granted_feats", "had",
           "modifiers", "pool_specs", "power_lines", "resolve", "sources", "standing_tags",
           "validate", "validate_power"]
