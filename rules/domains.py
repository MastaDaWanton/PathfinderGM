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


def _title(domain) -> str:
    return " ".join(str(domain or "").split()).title()


# --- subdomains ---------------------------------------------------------------------------
#
# Measured 2026-10-05 (docs/class-audit.md §1): the forge offered all 153 names in the
# corpus, 120 of them not core domains, and 117 of the 153 had no spell at one or more of
# levels 1-9 — "Ash" has spells at 7 and 9 only, so an Ash cleric's domain slot stood
# empty at seven of nine levels. The corpus is right: Ash is a SUBDOMAIN of Fire, and a
# subdomain "replaces a granted power and a number of spells" of its associated domain
# (APG, Cleric: Subdomains). Its list is Fire's with 7th and 9th swapped, so the parent
# fills the gaps; a cleric "cannot select its associated domain as her other domain
# choice". Foundry and PCGen both model it this way (the parent's list with replacements);
# the map is data, content/domains/subdomains.json, from Archives of Nethys.

@lru_cache(maxsize=1)
def subdomains() -> dict[str, list[str]]:
    """Every subdomain and its associated domain(s), as the shipped document names them."""
    import json
    from pathlib import Path

    from django.conf import settings

    path = Path(settings.BASE_DIR) / "content" / "domains" / "subdomains.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8")).get("subdomains") or {}
    except (OSError, ValueError):
        return {}
    return {_title(k): [_title(p) for p in v] for k, v in raw.items()}


def parents_of(domain: str) -> list[str]:
    """The domain(s) a subdomain belongs to; [] for a domain that is no subdomain."""
    return list(subdomains().get(_title(domain), []))


def _levels(domain: str) -> dict[int, list[str]]:
    """The domain's spells by level, a subdomain's gaps filled from its first parent."""
    own = dict(index().get(_title(domain), {}))
    for parent in parents_of(domain)[:1]:
        for lvl, ids in index().get(parent, {}).items():
            own.setdefault(lvl, ids)
    return own


def is_complete(domain: str) -> bool:
    """Whether the domain has a spell at every level 1-9 — every domain slot fillable."""
    levels = _levels(domain)
    return all(levels.get(lvl) for lvl in range(1, 10))


def names() -> list[str]:
    """Every domain a cleric could pick, alphabetically: the ones whose list is whole,
    a subdomain's with its parent's filling it. Ruins and Creation (spells at a few
    levels, no parent in the map) are left out rather than offered with empty slots."""
    return sorted(n for n in index() if is_complete(n))


def spells_of(domain: str, level: int | None = None) -> list[str]:
    """The spell ids this domain grants, at one level or at every level — a subdomain's
    own where it has one, its parent's where it does not."""
    levels = _levels(domain)
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
    whole = [c for c in chosen if not is_complete(c)]
    if whole:
        return [f"{c} has spells at levels "
                f"{', '.join(str(lvl) for lvl in sorted(index().get(c, {})))} only and no "
                f"parent domain to fill the rest, so its domain slots would stand empty; "
                f"choose another." for c in whole]
    for c in chosen:
        clash = [p for p in parents_of(c) if p in chosen]
        if clash:
            return [f"{c} is a subdomain of {clash[0]}: it takes {clash[0]}'s place, so a "
                    f"{noun.lower()} takes one or the other, not both."]
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
# vocabulary — `pool` and `cost` for uses per day, `tags` with `by_level` rungs,
# `modifiers` for a passive number, `not_yet` for what has no reader. Read LIVE off the
# character's own domain list, the way a feat is read off the feat list
# (`Actor._feat_mods`): nothing is copied onto the sheet, so a corrected document corrects
# every character holding the domain, and a domain lost is a power lost with nothing left
# behind to clean up.
#
# Since 2026-10-05 the reading is `rules/grantedpowers.py`'s, shared with the bloodlines,
# schools and bonds — the same shape in the book and in the documents. Measured before it:
# 7 of the 33 core domains had powers (the druid's seven); a Sun cleric got nothing at
# all. All 33 are written now. The functions below are the domain-only views kept for the
# callers that ask about domains alone (the forge's picker, the class-ability executor).

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
    """The domains whose powers are written down."""
    return sorted((powers_doc().get("domains") or {}))


def entry_of(domain: str) -> dict:
    """A domain's whole document — its `powers`, and its `class_skills` — or {}.

    A subdomain with no document of its own reads its parent's: it "replaces a granted
    power" of the parent and keeps the other (APG), and which one it replaces, with what,
    is not written yet — so the parent's stand in, and the first says so on the sheet."""
    own = (powers_doc().get("domains") or {}).get(_title(domain))
    if own is not None:
        return dict(own)
    for parent in parents_of(domain)[:1]:
        base = (powers_doc().get("domains") or {}).get(parent)
        if not base:
            continue
        powers = [dict(p) for p in base.get("powers") or [] if isinstance(p, dict)]
        if powers:
            powers[0]["not_yet"] = list(powers[0].get("not_yet") or []) + [
                f"{_title(domain)} is a subdomain of {parent}: it swaps one of {parent}'s "
                f"powers for its own, which is not written yet, so {parent}'s powers "
                f"stand in."]
        return {**dict(base), "powers": powers}
    return {}


def powers_of(domain: str) -> list[dict]:
    return [p for p in entry_of(domain).get("powers") or [] if isinstance(p, dict)]


def caster_level(actor) -> int:
    """The level a domain power reads. "The druid's effective cleric level is equal to her
    druid level" (Core Rulebook, Nature Bond), and a cleric's is her own."""
    return max(1, int(getattr(actor, "level", 1) or 1))


def powers_had(actor) -> list[tuple[str, dict]]:
    """(domain, power) for every power this character's domains grant at their level,
    each with its rung for that level laid over it."""
    from . import grantedpowers

    return [(row["id"], row["power"]) for row in grantedpowers.had(actor)
            if row["kind"] == "domain"]


def standing_tags(actor) -> list[str]:
    """The tags this character's domain powers hold right now — `resist.fire.10`."""
    out: list[str] = []
    for _domain, power in powers_had(actor):
        for tag in power.get("tags") or ():
            if str(tag).strip() and tag not in out:
                out.append(str(tag))
    return out


def pool_specs(actor) -> list[dict]:
    """The uses-per-day pools the domain powers declare, as `resources.define` rows."""
    from . import grantedpowers

    return [s for s in grantedpowers.pool_specs(actor) if s["source"].endswith(" domain")]


def power_lines(actor) -> list[dict]:
    """What the sheet shows: every granted power — domains, a bloodline, a school, a
    bond — with its line and what is not built yet (`grantedpowers.power_lines`). Kept
    under this name because the sheet's `domain_powers` key was drawn from it first."""
    from . import grantedpowers

    return grantedpowers.power_lines(actor)


def validate_powers(doc: dict | None = None) -> list[str]:
    """Every problem with the powers document, each with the fix named.

    The classbuilder's voice and the reason it has one: a power whose pool has no max is
    a power that is never usable, and nothing on screen would say why.
    """
    from . import grantedpowers

    doc = powers_doc() if doc is None else doc
    problems: list[str] = []
    known = set(index())
    for domain, entry in (doc.get("domains") or {}).items():
        at = f"domains.{domain}"
        if domain not in known:
            problems.append(f"{at}: no domain called {domain!r} in the spell corpus — "
                            f"write it as the corpus does ({', '.join(sorted(known)[:5])}…).")
        if not isinstance(entry, dict):
            problems.append(f"{at}: a domain is an object with `powers`.")
            continue
        extra = sorted(set(entry) - grantedpowers.ENTRY_KEYS)
        if extra:
            problems.append(f"{at}: unknown field(s) {', '.join(extra)}.")
        for i, power in enumerate(entry.get("powers") or []):
            problems += grantedpowers.validate_power(power, f"{at}.powers[{i}]")
    return problems
