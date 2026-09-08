"""What an `origin` may look like, and which kinds the engine knows how to stamp.

Stage 8. An origin is `kind:id` — the document behind a number — set only by
`Engine.validate(raw, origin=...)` or by an engine door onto an effect record. This
module is the one list of kinds, so a test can ask "was this stamped by a door" without
grepping strings, and so a new door cannot invent a kind nobody reads.

Deliberately NOT a resolver against the live world: the jar's last dose is popped from
the satchel before its own heal validates, so "does the referent still exist" is the
wrong question (docs/stage-8-plan.md, amendment A2). Well-formed and of a known kind is
the check; the door that stamped it held the document when it did.
"""
from __future__ import annotations

import re

# kind -> what the id half is. `author` and `creature` carry no document id to check
# beyond being non-empty; the rest are ids in the shape their corpus keys by.
KINDS = {
    "item": "a stock id or the jar's name",
    "spell": "a spell id from content/spells",
    "ability": "<path>/<resolved ability name>",
    "feat": "a feat id from content/feats",
    "rule": "a row in content/rules/*.json, or rest",
    "ward": "the spell name a standing ward was placed by",
    "creature": "the bestiary template a path-less creature was spawned from",
    # Doors added after stage 8, each a kind provenance can name: a scheme's step
    # or outcome, a situation card's grant, a founded place's holding.
    "scheme": "<scheme id>/<step|outcome|open|news>",
    "card": "<card id>",
    "place": "<place id>",
    "author": "cheat | test — the author's own hand",
}

_SHAPE = re.compile(r"^(?P<kind>[a-z]+):(?P<id>.+)$")


def parse(origin: str) -> tuple[str, str] | None:
    m = _SHAPE.match(str(origin or "").strip())
    if not m or m.group("kind") not in KINDS:
        return None
    return m.group("kind"), m.group("id")


def well_formed(origin: str) -> bool:
    """A known kind and a non-empty id; `author:` only cheat or test."""
    got = parse(origin)
    if got is None:
        return False
    kind, ident = got
    if kind == "author":
        return ident in ("cheat", "test")
    if kind == "ability":
        return "/" in ident and all(part.strip() for part in ident.split("/", 1))
    return bool(ident.strip())


def describe(origin: str) -> str:
    """For a message: what this origin claims to be."""
    got = parse(origin)
    if got is None:
        return "no document"
    kind, ident = got
    return f"{kind} {ident}"
