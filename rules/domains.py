"""Domains — a cleric's two, a druid's one through nature bond — derived from the corpus.

Asked for on 2026-09-19: *"oh i had forgotten domains those need chosen at creation as
well."* And the ruling that settles the half of it nobody wanted: *"grab whatever the
belief system of the world is and let that be enough. dont worry about the gods or the
alignment."*

So there is **no deity step and no alignment gate here**. A cleric picks two domains, and
what she believes is read off the world she is in — its own `Metaphysics` fact says why
that is enough: *"Gods are real, distant, and plural; no single faith holds the whole
world."* Her people's Belief, Rites and Taboos do the rest, and they are already reachable
from `world_people_id`, which creation stamps.

**The lists are derivable today.** Measured 2026-09-19: 153 distinct domain names across
452 spells, carried on the spell itself as `domain: "Luck (2), Tactics (2)"` — the name and
the level it sits at for that domain. So every domain's spell list is a query, and nothing
needed transcribing. What the corpus does NOT carry is the domain *powers* (the granted
abilities at 1st and 6th or 8th). Since 2026-10-04 the seven a druid may take are written
as documents in content/domains/powers.json (see "granted powers" below); every other
domain still grants its spells and its slot only, and the sheet says so.

**Which classes take domains, and how many, is the class document's to say** (its
`choices`, `rules/classes.py`), never this module's: the cleric's says two from every
domain there is, the druid's says one from Air, Animal, Earth, Fire, Plant, Water or
Weather — if the bond she takes is the domain and not the animal companion.
"""
from __future__ import annotations

import re
from functools import lru_cache

# "Luck (2), Tactics (2)" — a domain and the spell level it sits at for that domain.
_ENTRY = re.compile(r"([A-Za-z][A-Za-z' -]*?)\s*\((\d+)\)")


@lru_cache(maxsize=1)
def index() -> dict[str, dict[int, list[str]]]:
    """Every domain, and the spell ids it grants at each level."""
    from . import spells as spells_mod

    out: dict[str, dict[int, list[str]]] = {}
    for spell in spells_mod.all_spells().values():
        raw = str(getattr(spell, "domain", "") or "").strip()
        if not raw:
            continue
        for name, level in _ENTRY.findall(raw):
            name = " ".join(name.split()).strip().title()
            if not name:
                continue
            out.setdefault(name, {}).setdefault(int(level), []).append(spell.id)
    for levels in out.values():
        for ids in levels.values():
            ids.sort()
    return out


def names() -> list[str]:
    """Every domain a cleric could pick, alphabetically."""
    return sorted(index())


def spells_of(domain: str, level: int | None = None) -> list[str]:
    """The spell ids this domain grants, at one level or at every level."""
    levels = index().get(" ".join(str(domain or "").split()).title(), {})
    if level is None:
        return sorted({sid for ids in levels.values() for sid in ids})
    return list(levels.get(int(level), []))


def of(actor) -> list[str]:
    """The domains this character has taken, as the sheet holds them."""
    return [str(d) for d in (getattr(actor, "domains", None) or []) if str(d).strip()]


def grants(actor, level: int) -> list[str]:
    """Every spell id this character's own domains grant at that spell level.

    What a domain slot may hold: "Each day, a cleric can prepare one of the spells from her
    two domains in that slot."
    """
    out: list[str] = []
    for domain in of(actor):
        for sid in spells_of(domain, level):
            if sid not in out:
                out.append(sid)
    return out


def is_domain_spell(actor, spell_id: str, level: int | None = None) -> bool:
    """Whether this spell is one of theirs, at that level or at any level."""
    sid = str(spell_id or "").strip().lower()
    if level is not None:
        return sid in grants(actor, level)
    return any(sid in spells_of(d) for d in of(actor))


def rule_for(cid: str, answers=None, level: int = 1) -> dict | None:
    """How many domains this class takes and from which list, or None for none.

    Read off the class document's `choices` (`rules/classes.py`), never off the class's
    name. Until 2026-10-04 this was `if cid != "cleric": "takes no domains"`, and the
    owner's druid was made with no nature's bond at all: "I was given no choice for my
    natures bond and I dont think we have domains ... set up yet". A cleric's document
    says one option, two domains from every one there is; a druid's says nature bond is
    a domain from seven OR an animal companion, so the druid has a domain rule only when
    the bond taken is the domain.

    `answers` is the character's `class_choices` ({choice id: {"option": kind, ...}}).
    A choice with a single option needs no answer — the cleric has nothing to pick
    between, only domains to pick.
    """
    from . import classes as classes_mod

    for choice in classes_mod.choices_for(cid, level):
        option = classes_mod.option_taken(choice, answers)
        if option and option.get("kind") == "domain":
            pool = option.get("from")
            return {"choice": choice.get("id"), "how_many": int(option.get("how_many", 1)),
                    "from": None if pool in (None, "all") else
                    [" ".join(str(d).split()).title() for d in pool],
                    "member": classes_mod.member_noun(cid) or cid}
    return None


def offered(cid: str, level: int = 1) -> dict | None:
    """The domain rule a class OFFERS, whether or not the character takes it — what the
    forge draws its picker from. The druid offers seven even though she may take the
    companion instead."""
    from . import classes as classes_mod

    for choice in classes_mod.choices_for(cid, level):
        for option in choice.get("options") or ():
            if option.get("kind") == "domain":
                pool = option.get("from")
                return {"choice": choice.get("id"),
                        "how_many": int(option.get("how_many", 1)),
                        "from": None if pool in (None, "all") else
                        [" ".join(str(d).split()).title() for d in pool]}
    return None


def problems(picked, cid: str, answers=None) -> list[str]:
    """What is wrong with this pick, in the forge's own voice, or []."""
    chosen = [" ".join(str(p).split()).title() for p in (picked or []) if str(p).strip()]
    rule = rule_for(cid, answers)
    if rule is None:
        if not chosen:
            return []
        if offered(cid) is not None:
            from . import classes as classes_mod

            noun = (classes_mod.member_noun(cid) or cid).lower()
            return [f"A {noun} takes a domain only through {offered(cid)['choice']}; "
                    f"take the domain option there, or send no domains."]
        return [f"A {cid or 'character'} takes no domains."]
    want, noun = rule["how_many"], rule["member"]
    if len(chosen) != want:
        return [f"A {noun.lower()} takes {want} domain{'' if want == 1 else 's'}; "
                f"that is {len(chosen)}."]
    if len(set(chosen)) != len(chosen):
        return ["The two domains must be different."]
    known = set(index())
    unknown = [c for c in chosen if c not in known]
    if unknown:
        return [f"No domain called {u!r}." for u in unknown]
    if rule["from"] is not None:
        outside = [c for c in chosen if c not in rule["from"]]
        if outside:
            return [f"{c} is not one of a {noun.lower()}'s domains: "
                    f"{', '.join(rule['from'])}." for c in outside]
    return []


# --- the domains' granted powers ----------------------------------------------------------
#
# What the corpus does not carry (the module docstring's last paragraph), written as data
# in content/domains/powers.json: one document per power, in the class `grants`
# vocabulary — `pool` and `cost` for uses per day, `tags` with `by_level` rungs, `not_yet`
# for what has no reader. Read LIVE off the character's own domain list, the way a feat
# is read off the feat list (`Actor._feat_mods`): nothing is copied onto the sheet, so a
# corrected document corrects every character holding the domain, and a domain lost is a
# power lost with nothing left behind to clean up.

_POWER_KEYS = frozenset({"key", "name", "level", "kind", "line", "pool", "cost", "tags",
                         "by_level", "not_yet", "companion_offset"})


@lru_cache(maxsize=1)
def powers_doc() -> dict:
    """The shipped document. Content, not user data, so it is read from the install."""
    import json
    from pathlib import Path

    from django.conf import settings

    path = Path(settings.BASE_DIR) / "content" / "domains" / "powers.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"domains": {}}


def documented() -> list[str]:
    """The domains whose powers are written down. The rest grant their spells only."""
    return sorted((powers_doc().get("domains") or {}))


def powers_of(domain: str) -> list[dict]:
    entry = (powers_doc().get("domains") or {}).get(
        " ".join(str(domain or "").split()).title()) or {}
    return [p for p in entry.get("powers") or [] if isinstance(p, dict)]


def caster_level(actor) -> int:
    """The level a domain power reads. "The druid's effective cleric level is equal to her
    druid level" (Core Rulebook, Nature Bond), and a cleric's is her own."""
    return max(1, int(getattr(actor, "level", 1) or 1))


def powers_had(actor) -> list[tuple[str, dict]]:
    """(domain, power) for every power this character's domains grant at their level."""
    level = caster_level(actor)
    return [(d, p) for d in of(actor) for p in powers_of(d)
            if int(p.get("level", 1) or 1) <= level]


def _rung(power: dict, level: int) -> dict:
    """The power with its highest `by_level` rung at or below `level` laid over it."""
    out = dict(power)
    best = 0
    for at, rung in (power.get("by_level") or {}).items():
        if str(at).isdigit() and best < int(at) <= level and isinstance(rung, dict):
            best = int(at)
            out = {**dict(power), **rung}
    return out


def standing_tags(actor) -> list[str]:
    """The tags this character's domain powers hold right now — `resist.fire.10` — read
    by `Actor.standing_tags`, so `resistance()` and `immune_to()` answer from them with no
    second reader (both already ask `resist.*` / `immune.*` of the tag vocabulary)."""
    level = caster_level(actor)
    out: list[str] = []
    for _domain, power in powers_had(actor):
        for tag in _rung(power, level).get("tags") or ():
            if str(tag).strip() and tag not in out:
                out.append(str(tag))
    return out


def pool_specs(actor) -> list[dict]:
    """The uses-per-day pools the powers declare, as `resources.define` rows."""
    out = []
    for domain, power in powers_had(actor):
        spec = power.get("pool")
        if isinstance(spec, dict) and spec.get("max") not in (None, ""):
            out.append({"id": str(power.get("key") or power.get("name")).lower(),
                        "max": spec["max"], "starts": "max",
                        "refresh": spec.get("refresh", "rest.night"),
                        "source": f"{domain} domain"})
    return out


def power_lines(actor) -> list[dict]:
    """What the sheet shows: each power had, its line, and what is not built yet."""
    level = caster_level(actor)
    return [{"domain": d, "name": str(p.get("name") or p.get("key")),
             "kind": str(p.get("kind") or ""), "line": str(_rung(p, level).get("line")
                                                           or p.get("line") or ""),
             "not_yet": [str(n) for n in p.get("not_yet") or ()]}
            for d, p in powers_had(actor)]


def validate_powers(doc: dict | None = None) -> list[str]:
    """Every problem with the powers document, each with the fix named.

    The classbuilder's voice and the reason it has one: a power whose pool has no max is
    a power that is never usable, and nothing on screen would say why.
    """
    from . import resources

    doc = powers_doc() if doc is None else doc
    problems: list[str] = []
    known = set(index())
    for domain, entry in (doc.get("domains") or {}).items():
        at = f"domains.{domain}"
        if domain not in known:
            problems.append(f"{at}: no domain called {domain!r} in the spell corpus — "
                            f"write it as the corpus does ({', '.join(sorted(known)[:5])}…).")
        for i, power in enumerate((entry or {}).get("powers") or []):
            pat = f"{at}.powers[{i}]"
            if not isinstance(power, dict):
                problems.append(f"{pat}: a power is an object.")
                continue
            extra = sorted(set(power) - _POWER_KEYS)
            if extra:
                problems.append(f"{pat}: unknown field(s) {', '.join(extra)}; the reader "
                                f"would ignore them. A power carries: "
                                f"{', '.join(sorted(_POWER_KEYS))}.")
            if not str(power.get("key") or "").strip():
                problems.append(f"{pat}: needs a key — the pool's id and the power's name "
                                f"in lower case.")
            lvl = power.get("level")
            if not isinstance(lvl, int) or not 1 <= lvl <= 20:
                problems.append(f"{pat}.level: the class level it arrives at, 1-20.")
            pool = power.get("pool")
            if pool is not None:
                if not isinstance(pool, dict) or resources.check(pool.get("max")):
                    problems.append(f"{pat}.pool: {{\"max\": \"3 + wis_mod\", \"refresh\": "
                                    f"\"rest.night\"}} — a formula over the sheet.")
            cost = power.get("cost")
            if cost is not None and (not isinstance(cost, dict) or str(cost.get("pool", ""))
                                     .lower() != str(power.get("key", "")).lower()):
                problems.append(f"{pat}.cost: spends its own pool — "
                                f"{{\"pool\": \"{power.get('key', '')}\", \"amount\": 1}}.")
            for rung_at, rung in (power.get("by_level") or {}).items():
                if not str(rung_at).isdigit() or not isinstance(rung, dict):
                    problems.append(f"{pat}.by_level: rungs keyed by class level, "
                                    f"{{\"12\": {{\"tags\": [...]}}}}.")
            for field_name in ("tags", "not_yet"):
                got = power.get(field_name)
                if got is not None and (not isinstance(got, list)
                                        or any(not str(t).strip() for t in got)):
                    problems.append(f"{pat}.{field_name}: a list of strings.")
    return problems
