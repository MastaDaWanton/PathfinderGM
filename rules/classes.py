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
import re
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

# Extended 2026-10-05 (docs/class-audit.md, lane 1) to every choice the core classes make,
# at any level. The audit measured 19 choices that could not be made at all — "'bloodline'
# is not a choice a sorcerer makes; it makes none" — and a grammar asked only at 1st level.
# The shape is the one every mature PF1 builder converged on (audit §5): PCGen's
# `ABILITYCATEGORY` with a `POOL` formula (`BONUS:ABILITYPOOL|Rogue Talent|RogueTalentLVL/2`)
# and Hero Lab's per-level count both store a NUMBER OWED derived from the class level and
# check the selections against it; neither stores slots, and none forces the choice at the
# moment of level-up — Foundry's LevelUpForm never prompts for one, PCGen lists unspent
# pools under "Things to be Done". So here:
#
#   "at_levels": [2, 4, 6 …]   a pick is owed at each listed level (`level` is the one-level
#                              spelling, and still reads as `[level]`)
#   "kind": "class option"     the picks come from a catalogue in content/class-options/
#                              (`"from": "rage-powers"`), each entry an id with a min_level,
#                              `requires`, `repeatable` and, for a bloodline's dragon, variants
#   "kind": "feature"          an option with nothing further to pick: the paladin's bonded
#                              weapon, the ranger's bond with his companions
#   "from_choice": "<id>"      the picks are earlier picks of another choice — the ranger's
#                              +2 to "any one favored enemy (including the one just selected)"
#   "when": {"choice", "not"}  owed only once another choice is answered, and not with these
#                              picks (a universalist takes no opposition schools);
#                              `"only": [...]` owes it only WITH one of them (lane 2: the
#                              Animal domain's companion)
#   "distinct_from": "<id>"    may not repeat another choice's picks (opposition schools are
#                              not your own school)
#
# The ANSWER for a catalogue choice is `{"option": <key>, "picks": [{"pick", "level",
# "variant"?}]}` — one shape whether the class picks once or ten times, so a reader never
# branches on how many. Read through `chosen(actor, choice_id)`, never by digging in the
# dict: that is the API lanes 2-4 build mechanics on (docs/class-audit.md, "Lane 1").

CHOICE_KINDS = ("domain", "animal companion", "class option", "feature")
_CHOICE_KEYS = frozenset({"id", "name", "level", "at_levels", "text", "options", "when",
                          "distinct_from"})
_OPTION_KEYS = frozenset({"id", "kind", "name", "text", "from", "how_many", "level_offset",
                          "from_choice", "exclude", "raise"})
_ENTRY_KEYS_CHECKED = frozenset({"id", "name", "min_level", "requires", "repeatable",
                                 "variants"})


def _norm(text) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def choice_levels(choice: dict) -> list[int]:
    """The levels a choice owes a pick at, lowest first. `level` alone is `[level]`."""
    at = choice.get("at_levels")
    if isinstance(at, list) and at:
        return sorted(int(n) for n in at)
    return [int(choice.get("level", 1) or 1)]


def choices_for(class_id: str, level: int = 20) -> list[dict]:
    """The choices this class asks for by this level, in document order — a choice whose
    first pick falls at or below the level."""
    return [c for c in (get(class_id).get("choices") or [])
            if isinstance(c, dict) and choice_levels(c)[0] <= int(level or 1)]


def choice(class_id: str, choice_id: str) -> dict:
    """One choice of a class by id, or {}."""
    want = _norm(choice_id)
    return next((c for c in (get(class_id).get("choices") or [])
                 if isinstance(c, dict) and _norm(c.get("id")) == want), {})


def option_key(option: dict) -> str:
    """What an answer names an option by: its `id`, else its `kind`. Two options of one
    kind (the wizard's bonded object and familiar would be) need ids to be told apart;
    the druid's two are different kinds and were written before ids existed."""
    return _norm(option.get("id") or option.get("kind"))


def option_taken(choice: dict, answers) -> dict | None:
    """Which of a choice's options the answers took, or None when none was."""
    options = [o for o in (choice.get("options") or []) if isinstance(o, dict)]
    if len(options) == 1:
        return options[0]
    said = (answers or {}).get(str(choice.get("id"))) if isinstance(answers, dict) else None
    kind = _norm((said or {}).get("option", "") if isinstance(said, dict) else said or "")
    return (next((o for o in options if option_key(o) == kind), None)
            or next((o for o in options if _norm(o.get("kind")) == kind), None))


# --- catalogues: the option lists, as data ------------------------------------------------

def _build_catalogues() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for folder in (_dir("class-options"), _homebrew("class-options")):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                files.unreadable(path, exc)
                continue
            if not isinstance(data, dict):
                continue
            key = _norm(data.get("id") or path.stem)
            # A homebrew catalogue of the same id adds and replaces entries by id rather
            # than erasing the shipped list — the `paths` lesson above, learned once.
            base = dict(out.get(key) or {})
            entries = {_norm(e.get("id")): e for e in (base.get("options") or [])}
            for e in data.get("options") or []:
                if isinstance(e, dict) and _norm(e.get("id")):
                    entries[_norm(e.get("id"))] = e
            base.update({k: v for k, v in data.items() if k != "options"})
            base["options"] = list(entries.values())
            out[key] = base
    return out


def catalogues() -> dict[str, dict]:
    """Every option catalogue by id (content/class-options, then the homebrew folder)."""
    from . import pristine

    return pristine.memo("class-options", [_homebrew("class-options")], _build_catalogues)


def catalogue(name: str) -> dict:
    """One catalogue by id — "rage-powers" — or {}."""
    return catalogues().get(_norm(name), {})


def entry(name: str, entry_id: str) -> dict:
    """One entry of a catalogue by id, or {}."""
    want = _norm(entry_id)
    return next((e for e in catalogue(name).get("options") or []
                 if _norm(e.get("id")) == want), {})


def _variants(e: dict) -> list[str]:
    spec = e.get("variants") or {}
    return [_norm(v.get("id") if isinstance(v, dict) else v)
            for v in (spec.get("from") or [])] if isinstance(spec, dict) else []


# --- the read API (lanes 2-4 build on this; documented in docs/class-audit.md) ------------

def answer(actor, choice_id: str) -> dict:
    """The stored answer to one choice, as saved — {} when none. Prefer `chosen`."""
    got = (getattr(actor, "class_choices", None) or {}).get(str(choice_id))
    if got is None:
        want = _norm(choice_id)
        got = next((v for k, v in (getattr(actor, "class_choices", None) or {}).items()
                    if _norm(k) == want), None)
    return dict(got) if isinstance(got, dict) else {}


def chosen(actor, choice_id: str) -> list[dict]:
    """What this character chose for one of their class's choices, one dict per pick.

    The single door every mechanic reads a choice through. Each pick is
    `{"id", "name", "level", "variant", "option", "entry"}`: `entry` is the catalogue's
    whole document for it (a bloodline's `bonus_feats`, `powers`, `class_skill`; a mercy's
    `condition`), so a reader never opens the catalogue itself. An animal companion is one
    pick whose id is the animal; a `feature` option is one pick whose id is the option's;
    a domain option is one pick per domain held. [] when nothing is chosen — or the class
    asks no such thing, which a reader needs to treat the same way.
    """
    cid = str(getattr(actor, "char_class", "") or "")
    ch = choice(cid, choice_id)
    said = answer(actor, choice_id)
    if not ch:
        return []
    option = option_taken(ch, {str(ch.get("id")): said} if said else {})
    if option is None:
        return []
    kind = _norm(option.get("kind"))
    key = option_key(option)
    if kind == "domain":
        return [{"id": d, "name": d, "level": choice_levels(ch)[0], "variant": "",
                 "option": key, "entry": {}} for d in (getattr(actor, "domains", None) or [])]
    if kind == "animal companion":
        from . import animal_companion

        pick = _norm(said.get("pick"))
        return ([{"id": pick, "name": str(said.get("name") or "")
                  or animal_companion.name_of(pick), "level": choice_levels(ch)[0],
                  "variant": "", "option": key, "entry": {}}] if pick else [])
    if kind == "feature":
        return ([{"id": key, "name": str(option.get("name") or key),
                  "level": choice_levels(ch)[0], "variant": "", "option": key,
                  "entry": dict(option)}] if said else [])
    out = []
    for p in said.get("picks") or []:
        if not isinstance(p, dict):
            continue
        pid = _norm(p.get("pick"))
        if option.get("from_choice"):
            # A pick of another choice's pick: the entry is that pick's own.
            src = choice(cid, option["from_choice"])
            src_opt = option_taken(src, {str(src.get("id")): answer(
                actor, option["from_choice"])}) if src else None
            doc = entry(str((src_opt or {}).get("from") or ""), pid) if src_opt else {}
        else:
            doc = entry(str(option.get("from") or ""), pid)
        row = {"id": pid, "name": str(doc.get("name") or pid),
               "level": int(p.get("level", 0) or 0),
               "variant": _norm(p.get("variant")), "option": key, "entry": dict(doc)}
        # What a raise wrote onto the pick (`sync_raises`): a favored enemy's +2/+4/….
        if "bonus" in p:
            row["bonus"] = int(p.get("bonus") or 0)
        out.append(row)
    return out


def chosen_ids(actor, choice_id: str) -> list[str]:
    """The ids `chosen` returns, in pick order (repeats kept: a favoured enemy raised twice
    appears twice in "favored enemy bonus")."""
    return [p["id"] for p in chosen(actor, choice_id)]


def has_chosen(actor, choice_id: str, entry_id: str) -> bool:
    """Whether this character took this entry under this choice."""
    return _norm(entry_id) in chosen_ids(actor, choice_id)


# --- what is owed, and judging a pick ------------------------------------------------------
#
# One judge for both doors. The forge (`check_choices`, level 1, the whole answer at once)
# and the sheet (`take_choice`, any level, the picks still owed) ask the same questions in
# the same words, so the two cannot come to disagree about what a sorcerer may be.

def _said_picks(said) -> list[dict]:
    """An answer's picks, whichever spelling it came in: `{"picks": [...]}`, a list of
    ids, or the single-pick shorthand `{"pick": "draconic", "variant": "red"}`."""
    if isinstance(said, list):
        raw = said
    elif isinstance(said, dict):
        raw = said.get("picks")
        if raw is None and said.get("pick") not in (None, ""):
            raw = [{"pick": said.get("pick"), "variant": said.get("variant")}]
    else:
        raw = [said] if said not in (None, "") else []
    out = []
    for p in raw or []:
        if isinstance(p, dict):
            pid = _norm(p.get("pick") or p.get("id"))
            if pid:
                row = {"pick": pid}
                if _norm(p.get("variant")):
                    row["variant"] = _norm(p.get("variant"))
                if p.get("level"):
                    row["level"] = int(p.get("level"))
                out.append(row)
        elif _norm(p):
            out.append({"pick": _norm(p)})
    return out


def _picks_of(class_id: str, answers: dict, domains, choice_id: str) -> list[str]:
    """The ids another choice holds in a set of answers (forge draft or sheet alike)."""
    ch = choice(class_id, choice_id)
    if not ch:
        return []
    said = answers.get(str(ch.get("id"))) or {}
    option = option_taken(ch, {str(ch.get("id")): said} if said else {})
    if option is None:
        return []
    kind = _norm(option.get("kind"))
    if kind == "domain":
        return [_norm(d) for d in domains or []]
    if kind == "animal companion":
        return [_norm(said.get("pick"))] if isinstance(said, dict) and said.get("pick") else []
    if kind == "feature":
        return [option_key(option)] if said else []
    return [p["pick"] for p in _said_picks(said)]


def _when_ok(class_id: str, ch: dict, answers: dict, domains) -> bool:
    """A choice gated on another (`when`) is owed only once that one is answered, and not
    when it was answered with a pick the gate names — a universalist's opposition."""
    gate = ch.get("when")
    if not isinstance(gate, dict) or not gate.get("choice"):
        return True
    held = _picks_of(class_id, answers, domains, str(gate["choice"]))
    if not held:
        return False
    # `only`: owed only WITH one of these picks — the Animal domain's companion at 4th
    # (lane 2, 2026-10-05), asked of a cleric or druid who holds Animal and nobody else.
    only = {_norm(x) for x in gate.get("only") or []}
    if only and not (only & set(held)):
        return False
    return not ({_norm(x) for x in gate.get("not") or []} & set(held))


def _per_level(option: dict) -> int:
    try:
        return max(1, int(option.get("how_many", 1) or 1))
    except (TypeError, ValueError):
        return 1


def pick_levels(ch: dict, option: dict, level: int) -> list[int]:
    """Every level a catalogue choice has owed a pick at by this level, oldest first —
    `how_many` per listed level (the wizard's two opposition schools at 1st)."""
    return [n for n in choice_levels(ch) if n <= int(level) for _ in range(_per_level(option))]


def open_slots(ch: dict, option: dict, level: int, said) -> list[int]:
    """The levels still owed a pick: every slot by this level, less the slot each stored
    pick filled (a pick saved without one fills the oldest left)."""
    left = pick_levels(ch, option, level)
    loose = 0
    for p in _said_picks(said):
        at = int(p.get("level", 0) or 0)
        if at in left:
            left.remove(at)
        else:
            loose += 1
    return left[loose:]


def candidates(class_id: str, option: dict, answers: dict, domains=()) -> list[dict]:
    """The entries a catalogue option may pick from: the catalogue's, or for `from_choice`
    the other choice's picks (each once, with that catalogue's document)."""
    if option.get("from_choice"):
        src = choice(class_id, str(option["from_choice"]))
        src_opt = option_taken(src, {str(src.get("id")): answers.get(str(src.get("id")))
                                     or {}}) if src else None
        cat = str((src_opt or {}).get("from") or "")
        seen: list[str] = []
        for pid in _picks_of(class_id, answers, domains, str(option["from_choice"])):
            if pid not in seen:
                seen.append(pid)
        return [entry(cat, pid) or {"id": pid, "name": pid} for pid in seen]
    exclude = {_norm(x) for x in option.get("exclude") or []}
    return [e for e in catalogue(str(option.get("from") or "")).get("options") or []
            if isinstance(e, dict) and _norm(e.get("id")) not in exclude]


def owed_rows(class_id: str, level: int, answers: dict, domains=()) -> list[dict]:
    """Every class choice still to be made by this level: one row per pick owed,
    `{"choice", "name", "for_level", "need"}`, oldest first within a choice. `need` says
    what is missing: "option" (which of a choice's options), "domain", "animal", "pick"."""
    answers = answers if isinstance(answers, dict) else {}
    rows: list[dict] = []
    for ch in choices_for(class_id, level):
        cid = str(ch.get("id"))
        title = str(ch.get("name") or cid)
        if not _when_ok(class_id, ch, answers, domains):
            continue
        said = answers.get(cid) or {}
        option = option_taken(ch, {cid: said} if said else {})
        first = choice_levels(ch)[0]
        base = {"choice": cid, "name": title}
        if option is None:
            rows.append({**base, "for_level": first, "need": "option"})
            continue
        kind = _norm(option.get("kind"))
        if kind == "domain":
            short = _per_level(option) - len(list(domains or []))
            rows += [{**base, "for_level": first, "need": "domain"}] * max(0, short)
        elif kind == "animal companion":
            if not (isinstance(said, dict) and said.get("pick")):
                rows.append({**base, "for_level": first, "need": "animal"})
        elif kind == "feature":
            if not said:
                rows.append({**base, "for_level": first, "need": "option"})
        else:
            rows += [{**base, "for_level": n, "need": "pick"}
                     for n in open_slots(ch, option, level, said)]
    return rows


def _judge_picks(class_id: str, ch: dict, option: dict, new: list[dict], held: list[str],
                 slots: list[int], answers: dict, domains) -> tuple[list[dict], list[str]]:
    """New catalogue picks against the slots still owed, each judged with the ones before
    it already taken — so Intimidating Glare and the Terrifying Howl it opens may be chosen
    together. `(picks with their level, problems)`; nothing is kept unless all pass."""
    title = str(ch.get("name") or ch.get("id"))
    member = member_noun(class_id).lower() or class_id
    problems: list[str] = []
    if not new:
        return [], [f"{title}: choose at least one."]
    if not slots:
        return [], [f"{title}: nothing is owed — every pick your levels give is made."]
    if len(new) > len(slots):
        problems.append(f"{title}: that is {len(new)} picks against {len(slots)} owed. "
                        f"Choose {len(slots)}.")
        return [], problems
    pool = {_norm(e.get("id")): e for e in candidates(class_id, option, answers, domains)}
    if not pool:
        return [], [f"{title}: there is nothing to pick from yet"
                    + (f" — choose your {choice(class_id, option['from_choice']).get('name', option['from_choice'])} first."
                       if option.get("from_choice") else ".")]
    other = set()
    if ch.get("distinct_from"):
        other = set(_picks_of(class_id, answers, domains, str(ch["distinct_from"])))
    # Each pick into the oldest slot it fits, the most demanding first. Every pick fits
    # any slot at or above its level, so that greedy order always finds a legal pairing
    # when one exists: a 6th-level barbarian owed 2, 4 and 6 who sends Renewed Vigor
    # (4th) alone gets it filed at 4 and keeps 2 open, where pairing in the order sent
    # put it in slot 2 and refused it. Judged afterwards in the order sent, so a
    # prerequisite sent first still counts for the pick it opens.
    def need_of(p) -> int:
        return int((pool.get(p["pick"]) or {}).get("min_level", 1) or 1)

    free = sorted(slots)
    placed: dict[int, int] = {}
    for i in sorted(range(len(new)), key=lambda i: -need_of(new[i])):
        fit = next((s for s in free if s >= need_of(new[i])), None)
        if fit is None:
            fit = free[0] if free else 0
        if free:
            free.remove(fit)
        placed[i] = fit
    taken = list(held)
    out: list[dict] = []
    for i, p in enumerate(new):
        at = placed[i]
        e = pool.get(p["pick"])
        if e is None:
            names = ", ".join(str(x.get("name") or x.get("id")) for x in list(pool.values())[:12])
            problems.append(f"{title}: {p['pick']!r} is not one of the choices — "
                            f"{names}{'…' if len(pool) > 12 else ''}.")
            continue
        name = str(e.get("name") or e.get("id"))
        need = int(e.get("min_level", 1) or 1)
        if need > at:
            problems.append(f"{title}: {name} is open from {need}{_ordinal(need)} level; "
                            f"this pick is the one for level {at}.")
            continue
        variants = _variants(e)
        if variants:
            v = _norm(p.get("variant"))
            label = str((e.get("variants") or {}).get("name") or "kind").lower()
            if not v:
                problems.append(f"{title}: {name} needs a {label} — one of "
                                f"{', '.join(variants)}.")
                continue
            if v not in variants:
                problems.append(f"{title}: {v!r} is not a {label} of {name} — one of "
                                f"{', '.join(variants)}.")
                continue
        # Against everything held and everything sent with it, whatever the order.
        sent = {q["pick"] for j, q in enumerate(new) if j != i}
        missing = [r for r in (e.get("requires") or [])
                   if _norm(r) not in taken and _norm(r) not in sent]
        if missing:
            said = ", ".join(str((pool.get(_norm(r)) or {}).get("name") or r) for r in missing)
            problems.append(f"{title}: {name} requires {said} first.")
            continue
        if p["pick"] in taken and not e.get("repeatable") and not option.get("from_choice"):
            problems.append(f"{title}: already chosen {name}; choose another.")
            continue
        if p["pick"] in other:
            problems.append(f"{title}: {name} is already your "
                            f"{str(choice(class_id, ch['distinct_from']).get('name') or ch['distinct_from']).lower()};"
                            f" a {member} cannot take it here too.")
            continue
        taken.append(p["pick"])
        row = {"pick": p["pick"], "level": int(at)}
        if p.get("variant"):
            row["variant"] = _norm(p["variant"])
        out.append(row)
    return (out, []) if not problems else ([], problems)


def _judge_animal(ch: dict, option: dict, said, member: str) -> tuple[dict, list[str]]:
    from . import animal_companion

    title = str(ch.get("name") or ch.get("id"))
    raw = str((said or {}).get("pick", "") if isinstance(said, dict) else "").strip()
    pick = animal_companion.key_for(raw) or raw.lower()
    allowed = [animal_companion.key_for(a) for a in option.get("from") or []]
    if not pick:
        return {}, [f"{title}: an animal companion needs an animal — one of "
                    f"{', '.join(animal_companion.name_of(a) for a in allowed)}."]
    if pick not in allowed:
        return {}, [f"{title}: {pick!r} is not on a {member}'s companion list — one of "
                    f"{', '.join(animal_companion.name_of(a) for a in allowed)}."]
    out = {"option": option_key(option), "pick": pick}
    # The player's own name for it, if they gave one. Words only, and short — it is what
    # the narrator will call the animal.
    called = " ".join(str((said or {}).get("name") or "").split())[:40] \
        if isinstance(said, dict) else ""
    if called:
        out["name"] = called
    return out, []


def check_choices(class_id: str, answers, domains_sent=(), level: int = 1) -> tuple[dict, list[str]]:
    """The answers as the rules will accept them, and every problem at once, with the fix.

    The forge's door: every choice owed by `level` (1st, there) must be answered in full —
    "a druid was made with no nature's bond choice at all" is the defect, and so is a
    sorcerer with no bloodline. A domain sent with no answer IS the answer when the
    choice offers a domain: picking Air from the druid's seven is choosing the domain
    bond, and saying so twice is not required. The domain list itself is
    `domains.problems`' to judge; this judges the option.
    """
    member = (member_noun(class_id) or class_id).lower()
    clean: dict[str, dict] = {}
    problems: list[str] = []
    answers = dict(answers or {}) if isinstance(answers, dict) else {}
    asked = choices_for(class_id, level)
    known_ids = {str(c.get("id")) for c in asked}
    for key in answers:
        if key not in known_ids:
            problems.append(
                f"{key!r} is not a choice a {member} makes"
                + (f" at {level}{_ordinal(level)} level: {', '.join(sorted(known_ids))}."
                   if known_ids else "; it makes none."))
    for ch in asked:
        cid = str(ch.get("id"))
        title = str(ch.get("name") or cid)
        options = [o for o in (ch.get("options") or []) if isinstance(o, dict)]
        if not _when_ok(class_id, ch, clean, domains_sent):
            # Owed only after another choice (`when`): an unanswered gate is reported
            # under its own name, and a universalist's opposition is simply not asked.
            if answers.get(cid) and _picks_of(class_id, clean, domains_sent,
                                              str(ch["when"]["choice"])):
                problems.append(f"{title} is not asked of that choice of "
                                f"{choice(class_id, ch['when']['choice']).get('name', '')}"
                                f"; leave it out.")
            continue
        said = answers.get(cid)
        option = option_taken(ch, answers)
        if option is None and said in (None, "", {}) and domains_sent and any(
                o.get("kind") == "domain" for o in options):
            option = next(o for o in options if o.get("kind") == "domain")
        at = choice_levels(ch)[0]
        if option is None:
            kinds = " or ".join(str(o.get("name") or o.get("kind")).lower() for o in options)
            problems.append(f"A {member} chooses {title} at {at}{_ordinal(at)} level: "
                            f"{kinds}. Pick one in the class step.")
            continue
        kind = _norm(option.get("kind"))
        if kind == "domain":
            if len(options) > 1:
                clean[cid] = {"option": option_key(option)}
            continue                    # the cleric's two: `domains.problems` judges them
        if kind == "animal companion":
            got, bad = _judge_animal(ch, option, said, member)
            problems += bad
            if got:
                clean[cid] = got
            continue
        if kind == "feature":
            clean[cid] = {"option": option_key(option)}
            continue
        # A catalogue pick left unmade is NOT refused here, unlike the druid's bond above:
        # it stays owed on the sheet's "To choose from your levels" block, which is what
        # every builder the audit read does (§5 — Hero Lab reds the table, PCGen lists it
        # under "Things to be Done", none blocks the character). What IS sent is judged in
        # full, so a sorcerer can never be saved holding a bloodline that does not exist.
        slots = pick_levels(ch, option, level)
        new = _said_picks(said)
        if not new:
            continue
        picks, bad = _judge_picks(class_id, ch, option, new, [], slots, clean, domains_sent)
        problems += bad
        if picks:
            clean[cid] = {"option": option_key(option), "picks": picks}
    return sync_raises(class_id, clean), problems


def choice_menu(actor, choice_id: str) -> dict:
    """What the sheet's picker draws for one choice: its options, and under the taken one
    (or each, while none is) the entries with whether this character may take each now
    and why not. `{"choice", "owed": [levels], "options": [...], "taken": [...]}`."""
    from . import animal_companion, domains as domains_mod

    cid = str(getattr(actor, "char_class", "") or "")
    ch = choice(cid, choice_id)
    if not ch:
        return {}
    answers = dict(getattr(actor, "class_choices", None) or {})
    domains = list(getattr(actor, "domains", None) or [])
    level = int(getattr(actor, "level", 1) or 1)
    rows = [r for r in owed_rows(cid, level, answers, domains)
            if r["choice"] == str(ch.get("id"))]
    said = answers.get(str(ch.get("id"))) or {}
    taken = option_taken(ch, {str(ch.get("id")): said} if said else {})
    held = _picks_of(cid, answers, domains, str(ch.get("id")))
    other = set(_picks_of(cid, answers, domains, str(ch["distinct_from"]))) \
        if ch.get("distinct_from") else set()
    slots = [r["for_level"] for r in rows]
    top = max(slots) if slots else level
    options = []
    for o in ch.get("options") or []:
        if not isinstance(o, dict) or (taken is not None and o is not taken):
            continue
        kind = _norm(o.get("kind"))
        row = {"key": option_key(o), "kind": kind, "name": str(o.get("name") or kind),
               "text": str(o.get("text") or "")}
        if kind == "class option":
            entries = []
            for e in candidates(cid, o, answers, domains):
                eid = _norm(e.get("id"))
                why = ""
                need = int(e.get("min_level", 1) or 1)
                if need > top:
                    why = f"open from {need}{_ordinal(need)} level"
                elif eid in held and not e.get("repeatable") and not o.get("from_choice"):
                    why = "already chosen"
                elif eid in other:
                    why = f"already your {str(choice(cid, ch['distinct_from']).get('name', '')).lower()}"
                else:
                    missing = [r for r in (e.get("requires") or []) if _norm(r) not in held]
                    if missing:
                        why = "requires " + ", ".join(
                            str(entry(str(o.get('from') or ''), r).get("name") or r)
                            for r in missing)
                entries.append({"id": eid, "name": str(e.get("name") or eid),
                                "text": str(e.get("text") or ""), "min_level": need,
                                "variants": _variants(e),
                                "variant_name": str((e.get("variants") or {}).get("name")
                                                    or "") if isinstance(
                                                        e.get("variants"), dict) else "",
                                "open": not why, "why": why})
            row["entries"] = entries
        elif kind == "animal companion":
            row["animals"] = [{"key": animal_companion.key_for(a),
                               "name": animal_companion.name_of(a)}
                              for a in o.get("from") or []]
        elif kind == "domain":
            pool = o.get("from")
            row["domains"] = (domains_mod.names() if pool in (None, "all")
                              else [" ".join(str(d).split()).title() for d in pool])
            row["how_many"] = _per_level(o)
        options.append(row)
    return {"choice": {"id": str(ch.get("id")), "name": str(ch.get("name") or ch.get("id")),
                       "text": str(ch.get("text") or "")},
            "owed": slots, "options": options,
            "taken": [p["name"] for p in chosen(actor, str(ch.get("id")))]}


def take_choice(actor, choice_id: str, body: dict) -> tuple[list[str], list[str]]:
    """Answer an owed class choice on a living character: `(what was taken, [])`, or
    `([], problems)` and nothing written.

    `body`: `{"option": <key>}` where a choice has options not yet taken, then what the
    option needs — `"picks": [id | {"pick", "variant"}]` for a catalogue, `"pick"` (and
    `"name"`) for an animal, `"domains"` for a domain. Only what is OWED may be taken:
    the slots come from `owed_rows`, so a 4th-level barbarian sending three rage powers
    is told she has two.
    """
    from . import domains as domains_mod

    cid = str(getattr(actor, "char_class", "") or "")
    member = (member_noun(cid) or cid).lower()
    ch = choice(cid, choice_id)
    if not ch:
        known = [str(c.get("id")) for c in (get(cid).get("choices") or [])]
        return [], [f"{choice_id!r} is not a choice a {member} makes"
                    + (f": {', '.join(known)}." if known else "; it makes none.")]
    key = str(ch.get("id"))
    title = str(ch.get("name") or key)
    level = int(getattr(actor, "level", 1) or 1)
    answers = dict(getattr(actor, "class_choices", None) or {})
    domains = list(getattr(actor, "domains", None) or [])
    rows = [r for r in owed_rows(cid, level, answers, domains) if r["choice"] == key]
    if not rows:
        first = choice_levels(ch)[0]
        if first > level:
            return [], [f"{title} is chosen at {first}{_ordinal(first)} level; "
                        f"{getattr(actor, 'name', 'this character')} is {level}{_ordinal(level)}."]
        if not _when_ok(cid, ch, answers, domains):
            gate = choice(cid, ch["when"]["choice"]).get("name") or ch["when"]["choice"]
            return [], [f"{title} waits on {gate}, or is not asked of the one chosen."]
        return [], [f"{title}: nothing is owed — every pick your levels give is made."]
    body = body if isinstance(body, dict) else {}
    said = answers.get(key) or {}
    option = option_taken(ch, {key: said} if said else {})
    if option is None:
        want = _norm(body.get("option"))
        option = next((o for o in ch.get("options") or []
                       if isinstance(o, dict) and option_key(o) == want), None) \
            or next((o for o in ch.get("options") or []
                     if isinstance(o, dict) and _norm(o.get("kind")) == want), None)
        if option is None:
            names = " or ".join(f"{option_key(o)!r}" for o in ch.get("options") or [])
            return [], [f"{title}: say which — {names}."]
    kind = _norm(option.get("kind"))
    entry_out: dict = {"option": option_key(option)}
    said_words: list[str] = []
    if kind == "feature":
        said_words = [str(option.get("name") or option_key(option))]
    elif kind == "animal companion":
        got, bad = _judge_animal(ch, option, body, member)
        if bad:
            return [], bad
        entry_out = got
        from . import animal_companion

        said_words = [got.get("name") or animal_companion.name_of(got["pick"])]
    elif kind == "domain":
        sent = [" ".join(str(d).split()).title() for d in body.get("domains") or []
                if str(d).strip()]
        if not sent:
            return [], [f"{title}: name the domain{'s' if len(rows) > 1 else ''}."]
        if len(sent) > len(rows):
            return [], [f"{title}: that is {len(sent)} domains against {len(rows)} owed."]
        trial = dict(answers)
        trial[key] = entry_out if len(ch.get("options") or []) > 1 else said
        bad = domains_mod.problems(domains + sent, cid, trial)
        # The domain judge counts toward the full number; a druid adding her one is
        # judged whole, and a "takes 2 … that is 1" for a cleric adding one of two is not
        # a refusal of the one sent.
        bad = [b for b in bad if "that is" not in b or len(domains + sent) >= _per_level(option)]
        if bad:
            return [], bad
        actor.domains = domains + sent
        said_words = sent
        if len(ch.get("options") or []) == 1:
            entry_out = {}
    else:
        new = _said_picks(body.get("picks") if body.get("picks") is not None else body)
        slots = [r["for_level"] for r in rows]
        held = _picks_of(cid, answers, domains, key)
        picks, bad = _judge_picks(cid, ch, option, new, held, slots, answers, domains)
        if bad:
            return [], bad
        entry_out["picks"] = list((said.get("picks") if isinstance(said, dict) else None)
                                  or []) + picks
        pool = {_norm(e.get("id")): e for e in candidates(cid, option, answers, domains)}
        said_words = [str((pool.get(p["pick"]) or {}).get("name") or p["pick"])
                      + (f" ({p['variant']})" if p.get("variant") else "") for p in picks]
    if entry_out:
        actor.class_choices = sync_raises(cid, {**answers, key: entry_out})
    return said_words, []


def sync_raises(class_id: str, answers: dict) -> dict:
    """Write each raise onto the pick it raises, so a reader of the source choice sees
    the number without counting: `{"pick": "undead", "level": 5, "bonus": 4}`.

    The ranger's "+2 to any one favored enemy (including the one just selected)" is its
    own choice (`favored enemy bonus`, a `from_choice` option), because the player picks
    WHICH enemy each time. Its option's `raise` — `{"field": "bonus", "base": 2,
    "step": 2}` — says what that pick is worth on the source: the base on every source
    pick, plus a step for each time it was raised. Lane 3 reads the source's `bonus`
    (rules/classfeatures.py `chosen`); the raises stay the record. Recomputed whole on
    every write, so it can never drift from the picks it summarises.
    """
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (answers or {}).items()}
    for ch in get(class_id).get("choices") or []:
        for option in ch.get("options") or []:
            spec = option.get("raise") if isinstance(option, dict) else None
            src = option.get("from_choice") if isinstance(option, dict) else None
            if not isinstance(spec, dict) or not src or not isinstance(out.get(src), dict):
                continue
            raised = [p["pick"] for p in _said_picks(out.get(str(ch.get("id"))) or {})]
            field = str(spec.get("field") or "bonus")
            base, step = int(spec.get("base", 0) or 0), int(spec.get("step", 0) or 0)
            picks = []
            for p in out[src].get("picks") or []:
                if isinstance(p, dict):
                    p = {**p, field: base + step * raised.count(_norm(p.get("pick")))}
                picks.append(p)
            out[src] = {**out[src], "picks": picks}
    return out


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
        at_levels = choice.get("at_levels")
        if at_levels is not None and (
                not isinstance(at_levels, list) or not at_levels
                or not all(isinstance(n, int) and 1 <= n <= 20 for n in at_levels)
                or len(set(at_levels)) != len(at_levels)):
            problems.append(f"{at}.at_levels: the levels a pick is owed at, each 1-20 and "
                            f"once — [2, 4, 6] for a barbarian's rage powers.")
        ids_here = {str(c.get("id")) for c in raw if isinstance(c, dict)}
        for ref_key in ("distinct_from",):
            ref = choice.get(ref_key)
            if ref is not None and str(ref) not in ids_here:
                problems.append(f"{at}.{ref_key}: no choice called {ref!r} in this class.")
        gate = choice.get("when")
        if gate is not None and (not isinstance(gate, dict)
                                 or str(gate.get("choice")) not in ids_here):
            problems.append(f"{at}.when: {{\"choice\": <another choice's id>, \"not\": "
                            f"[picks]}} — owed once that choice is answered.")
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
            elif kind == "class option":
                src = option.get("from_choice")
                if src is not None:
                    if str(src) not in ids_here:
                        problems.append(f"{oat}.from_choice: no choice called {src!r} in "
                                        f"this class.")
                elif not catalogue(str(pool or "")):
                    problems.append(
                        f"{oat}.from: no catalogue called {pool!r} in "
                        f"content/class-options/. One of: {', '.join(sorted(catalogues()))}.")
                n = option.get("how_many", 1)
                if not isinstance(n, int) or not 1 <= n <= 5:
                    problems.append(f"{oat}.how_many: picks per level, 1 to 5.")
                spec = option.get("raise")
                if spec is not None and (
                        src is None or not isinstance(spec, dict)
                        or not isinstance(spec.get("base", 0), int)
                        or not isinstance(spec.get("step", 0), int)):
                    problems.append(f"{oat}.raise: only on a from_choice option — "
                                    f"{{\"field\": \"bonus\", \"base\": 2, \"step\": 2}}.")
    return problems


# --- class features as prerequisites -------------------------------------------------------
#
# 207 feat prerequisites in the corpus name a class feature ("rage class feature", "Channel
# energy class feature"), and `feats.meets` answered every one "unknown" — so a 3rd-level
# wizard took Extra Rage Power with 200 (audit D5). Answered here from what the character
# actually has: the class table's grants by level (the `class.*` tags), the choices made,
# and the domains held. A feature this character's class never grants is a real "no": a
# wizard has no rage. A clause that is not a class-feature name ("You must have lost class
# features by violating the code…") stays unknown, which is the honest answer.

# A prerequisite's wording against the name the class table uses for the same thing.
_FEATURE_ALIASES = {
    "channel positive energy": ("channel positive energy", "channel energy"),
    "channel negative energy": ("channel negative energy", "channel energy"),
    "wizard school": ("arcane school",),
    "sorcerer bloodline": ("bloodline",),
    "detect alignment": ("detect evil",),
    "aura": ("aura", "aura of good"),
    "detect undead paladin": (),
}
# Features held through a choice rather than a table row: the answer is the choice's.
_FEATURE_CHOICES = {"familiar": ("arcane bond", "familiar"),
                    "animal companion": ("", "animal companion"),
                    "mount": ("divine bond", "animal companion")}


def _has_one_feature(actor, name: str) -> bool | None:
    from . import classfeatures

    name = re.sub(r"^(?:the\s+)?ability to use (?:the\s+)?", "", _norm(name))
    name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
    if not name:
        return None
    cid = str(getattr(actor, "char_class", "") or "")
    level = int(getattr(actor, "level", 1) or 1)
    if name == "domain":
        return bool(getattr(actor, "domains", None))
    if name in _FEATURE_CHOICES:
        choice_id, want = _FEATURE_CHOICES[name]
        if want == "animal companion" and not choice_id:
            from . import animal_companion

            return animal_companion.wanted(actor) is not None
        picks = chosen(actor, choice_id)
        return any(p["option"] == want or p["id"] == want for p in picks) or any(
            _norm(p["entry"].get("id")) == want for p in picks)
    held = set(classfeatures.tags_for(cid, level))
    for alias in _FEATURE_ALIASES.get(name, (name,)):
        leaf = classfeatures.slug(alias)
        tag = f"{classfeatures.FAMILY}.{leaf}"
        # Asked of the vocabulary first (law one). The table's ladders still slug per
        # rung — `class.smite-evil-1-day` — until lane 3's slug fix, so a rung of the
        # ladder answers for its name too.
        has_state = getattr(actor, "has_state", None)
        if callable(has_state) and has_state(tag):
            return True
        if tag in held or any(t.startswith(tag + "-") for t in held):
            return True
    return False


def has_feature(actor, text: str) -> bool | None:
    """Does this character have the class feature a prerequisite names? True, False, or
    None when the clause is not a class-feature name this can read.

    "Grit class feature or Amateur Gunslinger feat": either side answers yes; a side
    that is not a class feature (a feat, a spell) is unknown here, so the whole is
    unknown unless a readable side said yes — `feats.meets` keeps those apart.
    """
    verdicts = []
    for part in re.split(r"\s*\bor\b\s*", _norm(text)):
        part = part.strip(" ,.")
        m = re.fullmatch(r"(.+?)\s+class feature", part)
        if not m:
            verdicts.append(None if part else False)
            continue
        said = m.group(1)
        # A name, not a sentence: "You have no levels in a class that has the grit
        # class feature" ends the same way and means the opposite.
        if len(said.split()) > 5 or re.search(r"\b(?:you|must|have|has|no)\b", said):
            verdicts.append(None)
            continue
        verdicts.append(_has_one_feature(actor, said))
    if any(v is True for v in verdicts):
        return True
    if verdicts and all(v is False for v in verdicts):
        return False
    return None


def validate_catalogue(d: dict) -> list[str]:
    """Everything wrong with one content/class-options file, each with the fix named.

    Only the fields this module reads are judged (`id`, `name`, `min_level`, `requires`,
    `repeatable`, `variants`); everything else on an entry — a bloodline's `bonus_feats`,
    a mercy's `condition` — is the lane that reads it to judge.
    """
    problems: list[str] = []
    if not isinstance(d, dict) or not _norm(d.get("id")):
        return ["A catalogue is an object with an id: {\"id\": \"rage-powers\", "
                "\"options\": [...]}."]
    entries = d.get("options")
    if not isinstance(entries, list) or not entries:
        return [f"{d.get('id')}: options, a list of at least one entry."]
    ids = [_norm(e.get("id")) for e in entries if isinstance(e, dict)]
    for i, e in enumerate(entries):
        at = f"{d.get('id')}.options[{i}]"
        if not isinstance(e, dict) or not _norm(e.get("id")):
            problems.append(f"{at}: an entry needs an id.")
            continue
        if ids.count(_norm(e["id"])) > 1:
            problems.append(f"{at}: a second entry called {e['id']!r}; ids are unique.")
        if not str(e.get("name") or "").strip():
            problems.append(f"{at}: needs a name to show the player.")
        lvl = e.get("min_level", 1)
        if not isinstance(lvl, int) or not 1 <= lvl <= 20:
            problems.append(f"{at}.min_level: 1-20.")
        for r in e.get("requires") or []:
            if _norm(r) not in ids:
                problems.append(f"{at}.requires: no entry called {r!r} in this catalogue.")
        if "variants" in e and not _variants(e):
            problems.append(f"{at}.variants: {{\"name\": \"Dragon type\", \"from\": "
                            f"[{{\"id\": \"red\"}}, ...]}}.")
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
    # The uses per day a granted power declares — a domain's Lightning Arc (3 + Wis), a
    # bloodline's Claws (3 + Cha rounds), a school's Force Missile (3 + Int), a bonded
    # object's daily spell (rules/grantedpowers.py) — through the same door as the
    # class's own pools, so they refresh on a night and show on the sheet with no second
    # mechanism. Recomputed on every load, which is how a Wisdom raised at 4th reaches
    # the pool.
    from . import grantedpowers

    for spec in grantedpowers.pool_specs(actor):
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
