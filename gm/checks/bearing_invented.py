"""A compass direction the world never gave.

Measured 2026-09-28 (docs/playtest-2026-09-28.md, items 16.6 and 19): asked for a
bearing, the page put signposts on the road — one "points toward the north, where the
mountains rise", another "toward the west, where the coastal road begins" — and the next
beat had "the road toward Dustgate" under northern peaks. The world records no compass
direction between any two of its settlements; every one of those was invented, and a
player who walks north on the strength of it is walking on the narrator's word.

Detect in code: a compass word in the same sentence as a settlement's name, or within
six words of a road, path or track. When an export states a route's bearing (`Road.bearing`, an ask in
docs/from-world-bible.md), that bearing is allowed for that destination and no other.
Repair: the road-relative answer (where it leaves from, what it crosses, how long).
Backstop: cut the compass phrase.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from . import _space

ORDER = 62
KINDS = frozenset({"bearing-invented"})
DOORS = frozenset({"turn", "outcome"})

WINDOW = 6
_COMPASS = ("north-east", "north-west", "south-east", "south-west", "northeast",
            "northwest", "southeast", "southwest", "north", "south", "east", "west")
_COMPASS_WORD = re.compile(
    r"^(north|south|east|west|north-?east|north-?west|south-?east|south-?west)"
    r"(?:ward|wards|ern|erly)?$")
_ANCHORS = frozenset({"road", "roads", "path", "paths", "track", "trail", "highway",
                      "signpost", "signposts", "post", "sign", "milestone"})


def _canon(word: str) -> str:
    m = _COMPASS_WORD.match(word)
    if not m:
        return ""
    w = m.group(1)
    return {"northeast": "north-east", "northwest": "north-west",
            "southeast": "south-east", "southwest": "south-west"}.get(w, w)


def _names(ctx) -> dict[str, str]:
    """Each settlement a road reaches, lower-cased, to the bearing the world states for
    it ("" when none), plus the settlement the party is in."""
    out = {str(r.to_name).lower(): r.bearing for r in _space.roads(ctx)}
    here = _space.settlement(ctx)
    if here is not None and getattr(here, "name", ""):
        out.setdefault(str(here.name).lower(), "")
    return out


def invented(sentence: str, names: dict[str, str]) -> list[str]:
    """The compass words in this sentence that sit near a settlement or a road, and are
    not the bearing the world gave for that settlement."""
    text = _space.unquoted(sentence)
    toks = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    low = [t.lower() for t in toks]
    hits: list[str] = []
    for i, w in enumerate(low):
        c = _canon(w)
        if not c:
            continue
        # A city's own places are named by the quarter ("the east crossing"): a name,
        # not a bearing.
        if i + 1 < len(low) and low[i + 1] in ("crossing", "quarter"):
            continue
        lo, hi = max(0, i - WINDOW), min(len(low), i + WINDOW + 1)
        near = low[lo:hi]
        # A settlement anywhere in the same sentence: "To the north, the horizon is jagged
        # with the peaks, and the road toward Dustgate is a straight line" (Bobby's turn
        # 8) puts Dustgate north as surely as "north to Dustgate" does, eleven words on.
        whole = " ".join(low)
        named = [n for n in names if n and re.search(rf"\b{re.escape(n)}\b", whole)]
        if named:
            if all(names[n] and names[n] == c for n in named):
                continue
            hits.append(w)
            continue
        if set(near) & _ANCHORS:
            if names and any(b == c for b in names.values() if b):
                continue
            hits.append(w)
    return hits


def find(ctx) -> list[Finding]:
    names = _names(ctx)
    flagged = [(s, invented(s, names)) for s in _space.sentences(ctx.text)]
    flagged = [(s, h) for s, h in flagged if h]
    if not flagged:
        return []
    rows = [f"{r.to_name}: {r.how or 'the way'} from {r.leaves_from}, {r.time_words}"
            + (f", over {r.crosses_words}" if r.crosses_words else "")
            for r in _space.roads(ctx)]
    return [Finding(
        kind="bearing-invented",
        detail=f"a compass bearing the world never gave: {', '.join(h for _s, hs in flagged for h in hs)}",
        fix_hint=("The world records no compass direction for these roads. Say where each "
                  "road leaves from, what it crosses and how long it takes, never which "
                  "way it points: " + "; ".join(rows[:5]) + "."),
        weight=2, sentences=tuple(s for s, _h in flagged))]


_PHRASE = re.compile(
    r"(?:,\s*)?\b(?:to(?:ward|wards)?|in|from|toward|towards|heading)\s+the\s+"
    r"(?:north|south|east|west)(?:-?(?:east|west))?\b"
    r"|\b(?:north|south|east|west)(?:-?(?:east|west))?(?:ward|wards)\b"
    r"|\b(?:north|south|east|west)(?:-?(?:east|west))?\s+(?=to\b|of\b)",
    re.I)


def backstop(ctx, text: str, findings: list) -> tuple[str, list[str]]:
    """Cut the compass phrases out of the flagged sentences — "to the north", "westward",
    "north to" — and tidy the space and the comma they leave."""
    notes: list[str] = []
    for f in findings:
        if f.kind != "bearing-invented":
            continue
        for s in f.sentences:
            if s not in text:
                continue
            cut = _PHRASE.sub(" ", s)
            cut = re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"\s{2,}", " ", cut)).strip()
            cut = re.sub(r",\s*,", ",", cut)
            if cut != s:
                text = text.replace(s, cut, 1)
                notes.append(f"cut a bearing: {s[:60]}")
    return text, notes
