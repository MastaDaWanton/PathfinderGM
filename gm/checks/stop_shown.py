"""A stop the engine rolled, written as background (item 16.3).

Measured on the Bobby playtest, 2026-09-28, turn 5. The walk from the market was stopped
by the street check: the travel effect carried `met: "patrol"` and the tell said "The
watch comes down the road at the way in, two of them, looking at faces. You get no
further." The page made it scenery: "the watchmen are making their rounds, their heavy
boots thudding against the cobblestones". Nothing read `met`; the tell was there and the
prose went its own way, which is this repo's first law measured once more.

Detect: a move whose effect met somebody (`met`) or stopped short (`stopped_short`), and
no sentence in the narration where somebody stops, blocks, bars, questions or looks the
player over — a closed list of verbs acting on "you", so habitual framing ("making their
rounds") never counts as the stop. Repair: the sentences that bring the meeting in as
background are rewritten with the engine's own meeting sentence named, happening to the
player now. Backstop: that meeting sentence, in the engine's words, after the first
sentence of the beat — the tell already says it, so the page may.

World-agnostic: reads the effect's fields and the tell the engine wrote; the people
words come from the meeting sentence itself, never a list of who patrols where.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._page import effects, field, page_sentences

ORDER = 20
KINDS = frozenset({"stop-not-shown"})
DOORS = frozenset({"plan", "turn"})

MOVE_OPS = ("travel", "venture", "journey")

# Somebody stopping the player, now. Verbs acting on "you" (or the way in front of you),
# and the engine's own words for it.
_STOPS = re.compile(
    r"\b(?:stops?|stopped|stopping|blocks?|blocked|blocking|bars?|barred|barring|"
    r"halts?|halted|halting|holds?\s+up|held\s+up|detains?|detained|questions?|"
    r"questioned|questioning|challenges?|challenged|turns?\s+back|turned\s+back)\s+"
    r"(?:you|your\s+(?:way|path|progress|road))\b"
    r"|\b(?:steps?|stepped|moves?|moved|plants?)\s+(?:themselves\s+|himself\s+|herself\s+)?"
    r"(?:into|across|in)\s+your\s+(?:path|way|road)\b"
    r"|\blooks?\s+you\s+over\b|\blooked\s+you\s+over\b"
    r"|\b(?:get|go|walk)\s+no\s+further\b|\bno\s+further\s+for\s+now\b"
    r"|\b(?:won't|will\s+not|does\s+not|doesn't|do\s+not|don't)\s+let\s+you\s+"
    r"(?:pass|through|by|go)\b"
    r"|\b(?:blocking|barring)\s+the\s+(?:way|road|path|street|lane)\b", re.I)

_PERSONISH = re.compile(r"[A-Za-z]{4,}")


def meeting(o) -> dict | None:
    """The move effect that met somebody or stopped short, or None."""
    if field(o, "op") not in MOVE_OPS:
        return None
    for e in effects(o):
        if e.get("met") or e.get("stopped_short"):
            return e
    return None


def meeting_sentences(o) -> str:
    """The engine's own sentences for the meeting, lifted out of the tell: what comes
    after the "You are at … now." line, up to "Left behind:". The tell is ours, not the
    model's, so its shape is a fact of this code (`Engine._op_travel`,
    `ontheway.describe`)."""
    tell = " ".join(str(field(o, "tell") or "").split())
    if not tell:
        return ""
    tell = re.split(r"\s*Left behind:", tell)[0]
    m = re.search(r"\bnow\.\s+(.*)$", tell)
    return (m.group(1) if m else tell).strip()


def _words(sentence: str) -> set[str]:
    stop = {"comes", "down", "road", "looking", "faces", "further", "there", "they",
            "them", "their", "with", "have", "your", "yours", "that", "this", "where",
            "what", "somebody", "something", "about", "from", "into", "away"}
    return {w.lower() for w in _PERSONISH.findall(sentence) if w.lower() not in stop}


def find(ctx) -> list:
    out = []
    for o in ctx.outcomes:
        if field(o, "status") == "refused":
            continue
        e = meeting(o)
        if e is None:
            continue
        pairs = page_sentences(ctx.text)
        if any(_STOPS.search(n) for _, n in pairs):
            continue
        said = meeting_sentences(o)
        # The sentences that bring the meeting's people in as background: those sharing
        # a word with the engine's meeting sentence ("watch" → "the watchmen are making
        # their rounds"). With none, the finding names no sentence and the backstop
        # adds the meeting.
        words = _words(said)
        flagged = tuple(w for w, n in pairs
                        if words and any(re.search(rf"\b{re.escape(x)}", n, re.I)
                                         for x in words))
        out.append(Finding(
            "stop-not-shown",
            f"the engine stopped the walk ({e.get('met') or 'stopped short'}: {said!r}) "
            f"and the prose does not show it",
            f"The engine decided this, and it happens to the player now: {said} Rewrite "
            f"the sentence so it is that stop, happening to the player — not people "
            f"going about their business.",
            weight=3, sentences=flagged[:2]))
        break
    return out


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """The engine's own meeting sentence, after the beat's first sentence."""
    if any(_STOPS.search(n) for _, n in page_sentences(text)):
        return text, []
    said = next((meeting_sentences(o) for o in ctx.outcomes
                 if field(o, "status") != "refused" and meeting(o) is not None), "")
    if not said:
        return text, []
    pairs = page_sentences(text)
    if not pairs:
        return said, ["stop not shown: the engine's meeting sentence stands"]
    first = pairs[0][0]
    at = text.find(first)
    if at < 0:
        return f"{text} {said}".strip(), ["stop not shown: added the engine's sentence"]
    end = at + len(first)
    return (f"{text[:end]} {said} {text[end:].lstrip()}".strip(),
            ["stop not shown: added the engine's meeting sentence"])
