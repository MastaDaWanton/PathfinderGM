"""Leaving narrated as arriving, and arriving as leaving (item 16.4).

Measured on the Bobby playtest, 2026-09-28, turn 5: the move went from the market out to
the way in — out of the village — and the page said "The dusty road stretches out behind
you" and "the gates of Vormoor open to receive you". Nothing compared the prose's
direction with the move's.

The direction is the engine's: `direction` on the move's effect (`"out" | "in" |
"along"`, Lane B's field, docs/fix-interfaces.md §2.7). Until every move carries it, one
is read off the effect's own places — the settlement's edge spots (the way in, a gate, the
approach) and its ground (`urban` or not) — which are this app's place kinds, not any
world's words. A move neither can place is not judged.

Detect, on an outward move: the settlement receiving the player (its gates or walls
opening to admit them, the town welcoming them, "you enter / arrive in / step into" it),
or the road lying behind them. On an inward one: the settlement left behind. The
settlement words are the settlement's own name, its scale word (`places.scale_of`) and
the generic town / village / city / settlement / gates / walls.

Repair: one rewrite naming from, to and which way. Backstop: the sentences are cut — the
tell already says where the party is.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._page import cut, effects, field, page_sentences

ORDER = 30
KINDS = frozenset({"direction-reversed"})
DOORS = frozenset({"plan", "turn"})

# The spots that are a settlement's edge, by the slug `places` gives them — the way out
# and the way in are the same door, and which one it is depends on where you came from.
_EDGE = ("the-way-in", "gate", "the-gate", "gates", "the-approach", "the-edge",
         "outskirts")
_INNER_BIOME = "urban"


def _spot(place_id: str) -> tuple[str, str]:
    """(ground, spot slug) out of a place id "<settlement>~<ground>:<spot>"."""
    rest = str(place_id or "").split("~", 1)[-1]
    ground, _, spot = rest.partition(":")
    return ground, spot


def direction_of(e: dict) -> str:
    """"out", "in", "along" or "" — the effect's own field first."""
    got = str(e.get("direction") or "")
    if got in ("out", "in", "along"):
        return got
    to_ground, to_spot = _spot(e.get("place", ""))
    from_ground, from_spot = _spot(e.get("was_place", ""))
    if not to_ground or not from_ground:
        return ""
    if from_ground == _INNER_BIOME and to_ground != _INNER_BIOME:
        return "out"
    if from_ground != _INNER_BIOME and to_ground == _INNER_BIOME:
        return "in"
    if to_ground == from_ground == _INNER_BIOME:
        edge_to = any(to_spot == s or to_spot.endswith(s) for s in _EDGE)
        edge_from = any(from_spot == s or from_spot.endswith(s) for s in _EDGE)
        if edge_to and not edge_from:
            return "out"
        if edge_from and not edge_to:
            return "in"
    return ""


def _settlement_words(ctx) -> str:
    words = ["town", "village", "city", "settlement", "gates?", "walls?", "hamlet"]
    loc = ctx.location
    if loc is None and ctx.world is not None:
        loc = ctx.world.get(getattr(ctx.scene, "location_id", "") or "")
    name = str(getattr(loc, "name", "") or "").strip()
    if name:
        words.append(re.escape(name))
    try:
        from rules import places as places_mod

        scale = str(places_mod.scale_of(loc) or "").strip() if loc is not None else ""
    except Exception:  # noqa: BLE001 — no scale word, the generic words stand
        scale = ""
    if scale and scale.isalpha():
        words.append(re.escape(scale.lower()))
    return "|".join(words)


def _patterns(ctx, way: str) -> list[re.Pattern]:
    town = _settlement_words(ctx)
    if way == "out":
        return [
            re.compile(rf"\b(?:{town})\b[^.!?]{{0,60}}\b(?:opens?|swings?\s+open|part|"
                       rf"parts|stand\s+open)\s+(?:wide\s+)?(?:to\s+)?(?:receive|admit|"
                       rf"welcome|let\s+in|swallow)\s+you\b", re.I),
            re.compile(rf"\b(?:{town})\b[^.!?]{{0,40}}\b(?:welcomes?|receives?|admits?|"
                       rf"swallows?|embraces?)\s+you\b", re.I),
            re.compile(rf"\byou\s+(?:enter|arrive\s+in|arrive\s+at|step\s+into|walk\s+into|"
                       rf"pass\s+(?:in\s+)?through\s+the\s+gates?\s+into|come\s+into)\s+"
                       rf"(?:the\s+)?(?:{town})\b", re.I),
            re.compile(r"\b(?:road|path|track|highway|trail)\b[^.!?]{0,60}\bbehind\s+you\b",
                       re.I),
        ]
    if way == "in":
        return [
            re.compile(rf"\byou\s+leave\s+(?:the\s+)?(?:{town})\b[^.!?]{{0,30}}\bbehind\b",
                       re.I),
            re.compile(rf"\b(?:{town})\b[^.!?]{{0,40}}\b(?:falls?\s+away|recedes?|"
                       rf"shrinks?|dwindles?)\s+behind\s+you\b", re.I),
        ]
    return []


def _move(ctx):
    for o in ctx.outcomes:
        if field(o, "status") == "refused" or field(o, "op") not in ("travel", "venture",
                                                                     "journey"):
            continue
        for e in effects(o):
            if e.get("kind") == "biome" or e.get("place"):
                way = direction_of(e)
                if way in ("out", "in"):
                    return e, way
    return None, ""


def find(ctx) -> list:
    e, way = _move(ctx)
    if e is None:
        return []
    rules = _patterns(ctx, way)
    flagged = tuple(w for w, n in page_sentences(ctx.text)
                    if "?" not in n and any(r.search(n) for r in rules))
    if not flagged:
        return []
    loc = ctx.location if ctx.location is not None else (
        ctx.world.get(getattr(ctx.scene, "location_id", "") or "") if ctx.world else None)
    town = str(getattr(loc, "name", "") or "the settlement")
    going = "out of" if way == "out" else "into"
    wrong = "arriving" if way == "out" else "leaving"
    return [Finding(
        "direction-reversed",
        f"the move went {going} {town} and the prose has the player {wrong}: "
        f"{flagged[0][:90]!r}",
        f"The player is going {going} {town} — from where they were to where they are "
        f"now — not {wrong}. Rewrite the sentence so the direction is the move's: what "
        f"lies ahead and what is left behind the right way round.",
        weight=3, sentences=flagged)]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    e, way = _move(ctx)
    if e is None:
        return text, []
    rules = _patterns(ctx, way)
    gone = [w for w, n in page_sentences(text) if any(r.search(n) for r in rules)]
    if not gone:
        return text, []
    return cut(text, gone), [f"direction reversed: cut {len(gone)} sentence(s)"]
