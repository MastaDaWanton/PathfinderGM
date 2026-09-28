"""Narrator checks: one module per check, found by filename (docs/fix-interfaces.md §2.1).

A check reads one groomed beat — after `polish`, after `mentions.attribute` — and names
what the page says that the engine does not: a move that was refused, a victim for a roll
that reached nobody, the brief's own wording printed as prose. It never edits the text.
The findings go to `GMAgent._repair_sentences`, which repairs them sentence by sentence
the house way: detect in code, one targeted rewrite naming the fact, a backstop last.

**Why a registry and not another block in `_groom`.** Six lanes add checks in parallel
in the 2026-09-28 fix pass, and `_groom` was already the one function every one of them
would have edited (docs/fix-plan-2026-09-28.md). A module dropped into this package is a
member; nothing has a list to edit, so no two lanes ever touch the same line.

**Why the run site is `_groom` and not `narration.review()`.** The plan first put the
hook in `review()`. `review()` runs only inside `polish`, only when `rewrite=True`, and
before the attribution exists — so a check hooked there would never see who the prose
means and would miss every NPC beat (fix-interfaces §1.1, P2).

The member contract (a module that breaks it is refused with the fix named, the way a
document is refused at the validator door):

    ORDER: int                        # run order; ties broken by module name
    KINDS: frozenset[str]             # every Finding.kind the module can emit
    DOORS: frozenset[str]             # a subset of {"plan", "turn", "npc", "outcome"}
    def find(ctx: BeatContext) -> list[Finding]
    def backstop(ctx, text, findings) -> tuple[str, list[str]]     # optional

A module whose name starts with `_` is a helper (`_people.py`), never a member.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:  # pragma: no cover - names for the annotations only
    from gm.mentions import Attribution
    from gm.narration import Finding
    from rules.engine import Engine, Outcome, Scene
    from world.loader import World

# `_groom`'s four callers, by the name a member opts in with.
ALL_DOORS = frozenset({"plan", "turn", "npc", "outcome"})


@dataclass(frozen=True)
class BeatContext:
    """Everything a check may read about one beat. Built at `_groom`'s four callers, and
    handed to the checks with `text`, `attribution` and `said` brought up to date after
    the rewrite. Derived values are deliberately not fields: `here` is `engine.here()`,
    `known` is `engine.places()`, `in_fight` is `scene.in_encounter` — a second copy of a
    fact the engine already holds is the parallel store law two forbids."""
    door: str                         # "plan" | "turn" | "npc" | "outcome"
    text: str                         # the draft when the checks run (after polish and attribution)
    player_text: str
    engine: "Engine"                  # read-only by contract: here(), places(), talking_to()
    scene: "Scene"
    world: "World | None"
    location: object | None           # the settlement entity
    reading: Mapping | None           # agent.reading (the interpreter frame)
    outcomes: tuple["Outcome", ...]   # ALL of resolution.outcomes, refused and tell-less included
    tells: tuple[str, ...]            # what _groom already calls `facts`
    said: tuple[Mapping, ...]         # speech.lift records for this draft (a copy of agent.last_said)
    attribution: "Attribution | None"
    brief: str                        # the whole brief as sent
    brief_facts: Mapping[str, Mapping]  # keyed by brief-section module name (§2.2)
    pull: Mapping | None              # thread_to_pull's dict, as passed to _groom
    was_at: str                       # scene.at when plan_turn began (agent._was_at)
    acting: str                       # the NPC ref on an NPC's turn, else ""
    turn: int


class CheckContractError(TypeError):
    """A member module that does not keep the contract above. Raised with the module and
    the fix named, so a lane that drops in a malformed check fails the suite on the spot
    instead of silently checking nothing in the packaged app."""


def _short(module: ModuleType) -> str:
    return module.__name__.rsplit(".", 1)[-1]


def _validate(module: ModuleType) -> None:
    name = _short(module)
    order = getattr(module, "ORDER", None)
    if not isinstance(order, int) or isinstance(order, bool):
        raise CheckContractError(f"gm.checks.{name}: ORDER must be an int "
                                 f"(got {order!r}); set e.g. `ORDER = 50`")
    kinds = getattr(module, "KINDS", None)
    if not isinstance(kinds, frozenset) or not kinds \
            or not all(isinstance(k, str) and k for k in kinds):
        raise CheckContractError(f"gm.checks.{name}: KINDS must be a non-empty frozenset "
                                 f"of the Finding kinds it emits (got {kinds!r})")
    doors = getattr(module, "DOORS", None)
    if not isinstance(doors, frozenset) or not doors or not doors <= ALL_DOORS:
        raise CheckContractError(f"gm.checks.{name}: DOORS must be a non-empty frozenset "
                                 f"drawn from {sorted(ALL_DOORS)} (got {doors!r})")
    if not callable(getattr(module, "find", None)):
        raise CheckContractError(f"gm.checks.{name}: needs `def find(ctx) -> "
                                 f"list[Finding]`")
    if hasattr(module, "backstop") and not callable(module.backstop):
        raise CheckContractError(f"gm.checks.{name}: `backstop` must be a function "
                                 f"(ctx, text, findings) -> (text, notes)")


def registered() -> tuple[ModuleType, ...]:
    """The member modules, sorted by (ORDER, module name).

    Discovered afresh on every call, over the package's own `__path__`, never from a list
    and never cached: the directory is the registry. Frozen, PyInstaller's `pkgutil`
    runtime hook answers `iter_modules` from the bundle — which holds only what the spec
    collected, so `pathfindergm.spec` names this package (CLAUDE.md: prove the frozen app
    discovers what the source tree does)."""
    members = []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        _validate(module)
        members.append(module)
    members.sort(key=lambda m: (m.ORDER, _short(m)))
    # One owner per finding kind, so the repair can find the backstop that goes with a
    # finding without guessing (`owner_of`).
    seen: dict[str, str] = {}
    for m in members:
        for kind in m.KINDS:
            if kind in seen:
                raise CheckContractError(
                    f"gm.checks.{_short(m)} and gm.checks.{seen[kind]} both declare the "
                    f"kind {kind!r}; a kind has one owner — rename one of them")
            seen[kind] = _short(m)
    return tuple(members)


def owner_of(kind: str) -> ModuleType | None:
    """The member that declares a finding kind, for its `backstop`."""
    return next((m for m in registered() if kind in m.KINDS), None)


def _key(sentence: str) -> str:
    return " ".join(str(sentence).split())


def _drop_covered(found: list["Finding"]) -> list["Finding"]:
    """Drop a finding whose non-empty `sentences` were all flagged already by a heavier
    finding. Two checks reading one sentence — a harmed bystander is both "no victim for
    the roll" and a state contradiction — must cost one repair of that sentence, not two
    rewrites fighting over it (docs/design-a-truth.md, item 22.4).

    Heavier means a higher `weight`; at equal weight, the finding raised first in run
    order counts as heavier, so an exact duplicate is dropped once and not both kept.
    A finding with no sentences is never dropped: it names nothing to overlap with."""
    rank = sorted(range(len(found)), key=lambda i: (-int(found[i].weight or 0), i))
    flagged: set[str] = set()
    dropped: set[int] = set()
    for i in rank:
        spans = {_key(s) for s in (found[i].sentences or ()) if _key(s)}
        if spans and spans <= flagged:
            dropped.add(i)
            continue
        flagged |= spans
    return [f for i, f in enumerate(found) if i not in dropped]


def run(ctx: BeatContext, *, errors: list | None = None) -> list["Finding"]:
    """Every member that opted in to `ctx.door`, in order; their findings, overlaps dropped.

    `errors=None` lets a member's exception (or a finding of a kind it did not declare)
    propagate — what the tests want. The game passes a list: a broken check then costs
    only its own findings, recorded as `{"kind": "check-error", "member", "error"}`, and
    never the turn."""
    found: list = []
    for member in registered():
        if ctx.door not in member.DOORS:
            continue
        try:
            out = list(member.find(ctx) or [])
            stray = sorted({f.kind for f in out} - member.KINDS)
            if stray:
                raise CheckContractError(
                    f"gm.checks.{_short(member)} emitted {stray} not in its KINDS; "
                    f"declare them")
        except Exception as exc:  # noqa: BLE001 — a broken check must not lose the turn
            if errors is None:
                raise
            errors.append({"kind": "check-error", "member": _short(member),
                           "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
            continue
        found.extend(out)
    return _drop_covered(found)
