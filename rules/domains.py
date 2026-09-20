"""A cleric's domains, derived from the corpus rather than authored.

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
needed transcribing. What the corpus does NOT carry is the domain *powers* (channelling
bonuses, bonus feats, the granted abilities at 1st and 8th), and those are left unbuilt
rather than invented — a domain grants its spells here, and says so.
"""
from __future__ import annotations

import re
from functools import lru_cache

# "Luck (2), Tactics (2)" — a domain and the spell level it sits at for that domain.
_ENTRY = re.compile(r"([A-Za-z][A-Za-z' -]*?)\s*\((\d+)\)")
# How many a cleric picks. The Core Rulebook's number, and the reason the sheet field is a
# list rather than a string.
HOW_MANY = 2


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


def problems(picked, cid: str) -> list[str]:
    """What is wrong with this pick, in the forge's own voice, or []."""
    if str(cid or "").strip().lower() != "cleric":
        return ([f"A {cid or 'character'} takes no domains."] if picked else [])
    chosen = [" ".join(str(p).split()).title() for p in (picked or []) if str(p).strip()]
    if len(chosen) != HOW_MANY:
        return [f"A cleric takes {HOW_MANY} domains; that is {len(chosen)}."]
    if len(set(chosen)) != len(chosen):
        return ["The two domains must be different."]
    known = set(index())
    unknown = [c for c in chosen if c not in known]
    if unknown:
        return [f"No domain called {u!r}." for u in unknown]
    return []
