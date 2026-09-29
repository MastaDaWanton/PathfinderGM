"""pull-took-the-beat: the player went looking for somebody, and the beat gave itself to the
open matter's person instead.

Measured on the 2026-09-28 playtest (item 9.2, turn 4): "I head to the market and look for
the girl that the watchman described to me" — the beat arrived at the market, found no
girl, and handed itself to Drenn Ironvale, who walked up and pitched his lost Power leaf.
The pull had told him to (`cards.thread_to_pull`: "they approach the player and say the
first word"); the reading's `seek` was never consulted. The pull now yields (approach
`waits`), and this holds the page to it: the reading seeks somebody, nothing on the page
answers the search (their head noun, the finder's name for them, the not-here line), and
one of the pull's people has a line.

The repair asks for the search to be answered first and the giver left at their business;
the deterministic backstop is the engine's own answer — the not-here line, or the brief's
HERE line — which the beat already carries when it is repaired.
"""
from __future__ import annotations

import re

from gm.narration import Finding

ORDER = 60
KINDS = frozenset({"pull-took-the-beat"})
DOORS = frozenset({"turn"})


def answered(ctx, found: dict) -> bool:
    """Whether the page answers the search: the sought person's head noun, the finder's
    name for who was found, or the engine's not-here line."""
    from gm.checks._people import head_of

    page = str(ctx.text or "")
    low = page.lower()
    head = head_of(found.get("sought") or "").lower()
    # The head noun in a sentence that is not the search restated. The playtest's beat
    # said "Scanning the crowd for the girl the watchman described, your eyes land on a
    # man in a suit" — the girl named only as what was being looked for, and never found
    # or ruled out.
    if head:
        for sentence in re.split(r"(?<=[.!?])\s+", page):
            s = sentence.lower()
            if not re.search(rf"\b{re.escape(head)}\b", s):
                continue
            if re.search(rf"\b(?:look\w*|search\w*|scan\w*|seek\w*|hunt\w*|for)\b"
                         rf"(?:\W+\w+){{0,4}}?\W+{re.escape(head)}\b", s):
                continue
            return True
    who = str(found.get("who") or "")
    if who and who.lower() in low:
        return True
    if found.get("ref"):
        actor = (getattr(ctx.scene, "actors", {}) or {}).get(found["ref"])
        if actor is not None and str(actor.name).lower() in low:
            return True
    line = str(found.get("line") or "").strip()
    if line and line.lower()[:40] in low:
        return True
    return False


def find(ctx) -> list:
    from gm.checks import _sought

    pull = ctx.pull or {}
    if not pull:
        return []
    found = _sought.sought(ctx)
    if not found.get("sought"):
        return []
    refs = _sought.people_refs(ctx, pull.get("people") or ())
    giver = (pull.get("giver") or {}).get("ref")
    if giver:
        refs.add(str(giver))
    # The one sought is never "the pull's person" taking the beat — finding them is the
    # answer.
    refs.discard(str(found.get("ref") or ""))
    spoke = _sought.lines_by(ctx, refs)
    if not spoke or answered(ctx, found):
        return []
    who = ", ".join(sorted({(getattr(ctx.scene, "actors", {}) or {})[r].name
                            for r in refs if r in (getattr(ctx.scene, "actors", {}) or {})}))
    return [Finding(
        "pull-took-the-beat",
        f"the player went looking for {found['sought']!r} and the beat never answers it, "
        f"while {who or 'the open matter’s person'} speaks up instead",
        f"Answer the search first: say whether {found['sought']} is found here"
        + (f" ({found.get('line')})" if found.get("line") else "")
        + f". Leave {who or 'them'} at their own business — they do not approach the "
          f"player or raise their matter this beat.",
        weight=3, sentences=tuple(spoke))]
