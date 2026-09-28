"""Brief sections: the parts of `prompts.scene_brief` that are one module each.

The register is `docs/fix-interfaces.md` §2.2. Six lanes of the 2026-09-28 fix pass each
wanted a few lines in the brief, and `scene_brief` is one function in a 1,400-line file
with one owner. A shared file with a list to append to is the merge conflict every lane
would have hit, so there is no list: a member is a module in this package, found by name.

**Discovery** is `pkgutil.iter_modules` over the package's own `__path__`, never a glob
of the directory beside `__file__`. CLAUDE.md's rule is that `__file__` lies once the app
is frozen — inside the PyInstaller archive there is no directory to glob — and
`pkgutil` is what PyInstaller's own `pyi_rth_pkgutil` hook teaches to list its archive.
A name starting with `_` is a helper, never a member. Members run sorted by
`(ORDER, module name)`, so two lanes that pick the same ORDER still get one answer.

**A member** exports:

    ORDER: int
    SLOT: str                          # "place" | "people"
    SCAFFOLD: tuple[str, ...]          # the section's fixed words, values left out
    def section(ctx: BriefContext) -> tuple[str, dict]

`section` returns its text — including its own leading "\\n" and indent, exactly as it
will sit in the brief — and the facts it printed, keyed however the section likes. A
section with nothing to say returns ("", {}). The facts are what a narrator check reads
to learn what the model was actually SHOWN (`BeatContext.brief_facts`), rather than
deriving the same thing a second time or parsing the brief's strings back out — which
would be the first law's error again, a fact held in two places.

**The slots** are where `scene_brief` calls `run`: "place" where the HERE / ROADS OUT /
fact-key block used to be written inline, and "people" after WHO IS HERE.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from types import ModuleType
from typing import Mapping

SLOTS = ("place", "people")


@dataclass(frozen=True)
class BriefContext:
    """Everything `scene_brief` was handed, once, for every section to read.

    The fields are `scene_brief`'s own arguments and nothing derived, with one
    exception: `here` and `known` are the engine's answer when the caller had an engine,
    and `places.for_scene`'s when it did not — resolved once in `scene_brief`, because the
    thread line after the place slot needs `here` as well.
    """
    world: object
    scene: object
    location: object | None
    here: object | None
    known: tuple
    recent_events: list | None
    recent: list | None
    secret: bool
    turn: int
    names_for: object | None
    absent: str
    buying: str
    reading: Mapping | None
    player_text: str


def _check(mod: ModuleType) -> None:
    """Refuse a member that would fail later, with the fix named."""
    name = mod.__name__
    missing = [a for a in ("ORDER", "SLOT", "SCAFFOLD", "section") if not hasattr(mod, a)]
    if missing:
        raise TypeError(f"{name} is in gm/brief/ but lacks {', '.join(missing)}; a member "
                        f"exports ORDER, SLOT, SCAFFOLD and section(ctx) — or rename the "
                        f"file with a leading '_' if it is a helper")
    if mod.SLOT not in SLOTS:
        raise ValueError(f"{name}.SLOT is {mod.SLOT!r}; it must be one of {SLOTS}")
    if not isinstance(mod.ORDER, int):
        raise TypeError(f"{name}.ORDER must be an int, not {type(mod.ORDER).__name__}")


def discover(package: ModuleType) -> tuple[ModuleType, ...]:
    """Every member module of `package`, checked, in running order."""
    import importlib
    import pkgutil

    found = []
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_") or info.ispkg:
            continue
        mod = importlib.import_module(f"{package.__name__}.{info.name}")
        _check(mod)
        found.append(mod)
    found.sort(key=lambda m: (m.ORDER, short_name(m)))
    return tuple(found)


@lru_cache(maxsize=1)
def _discovered() -> tuple[ModuleType, ...]:
    import sys

    return discover(sys.modules[__name__])


def short_name(mod: ModuleType) -> str:
    """`gm.brief.here` -> `here`: the key facts are filed under."""
    return mod.__name__.rsplit(".", 1)[-1]


def registered(slot: str | None = None) -> tuple[ModuleType, ...]:
    """Every member, in running order; only one slot's when `slot` is given."""
    members = _discovered()
    if slot is None:
        return members
    return tuple(m for m in members if m.SLOT == slot)


def run(slot: str, ctx: BriefContext) -> tuple[str, dict]:
    """One slot's text, and every member's facts keyed by its module name.

    The texts are joined with "\\n" — the separator `scene_brief` joins its own lines
    with — so a slot's members sit in the brief exactly as lines written inline would.
    Every member that ran is in the facts, `{}` included: a section that ran and printed
    nothing is a different fact from a section that never ran.
    """
    if slot not in SLOTS:
        raise ValueError(f"no brief slot {slot!r}; the slots are {SLOTS}")
    parts, facts = [], {}
    for mod in registered(slot):
        text, said = mod.section(ctx)
        if text:
            parts.append(text)
        facts[short_name(mod)] = dict(said or {})
    return "\n".join(parts), facts


# The fixed words of a section, in the shape `brief_verbatim` compares prose against
# (docs/design-a-truth.md, item 17.6): the model pastes a brief's own phrasing onto the
# page, and a 4-gram of a label's words is long enough to be that and short enough to
# survive the model's re-casing and punctuation. Words are lowercase runs of letters,
# digits and apostrophes, so "ROADS OUT OF" and "roads out of" are one gram. Grams never
# span two SCAFFOLD strings: between them sat a value — a name, a list — which is the
# world's own words and not scaffold.
_WORD = re.compile(r"[a-z0-9']+")
GRAM = 4


def words(text: str) -> list[str]:
    """The words `scaffold()` is counted in, for a check to split prose the same way."""
    return _WORD.findall(str(text or "").lower())


def grams(text: str, n: int = GRAM) -> set[tuple[str, ...]]:
    """Every run of `n` consecutive words in `text`."""
    w = words(text)
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def scaffold() -> frozenset[tuple[str, ...]]:
    """The 4-grams of every member's SCAFFOLD, every slot."""
    out: set[tuple[str, ...]] = set()
    for mod in registered():
        for fixed in mod.SCAFFOLD:
            out |= grams(fixed)
    return frozenset(out)
