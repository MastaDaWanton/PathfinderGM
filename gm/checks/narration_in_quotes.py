"""narration-in-quotes: narration printed as somebody's speech.

Measured on the 2026-09-30 playtest (item 12), Sam's save, beats 51 and 53: five
narration sentences inside Gorm Vesper's quotation marks —

    'Gorm Vesper watches you from their workspace, remaining silent until you turn to
    face them.' he says, his voice a low rasp…
    'Depends on the lady, who remains at her post and only speaks if you turn to her.'
    'Others... others, like Gorm Vesper, require a heavy purse to forget a heavy past.'

They came from our own repair (keeper-forward's rewrite spliced inside the quotes; that
door is shut in `_quotes` and `keeper_forward`), but nothing on the page side would have
seen them, and the conversation log (item 1) books whatever a quote attributed to Gorm
holds as Gorm's words. Two marks, both mechanical:

  * **a check's own wording in a quote.** "until you turn to", "only speaks if you turn",
    "the player" — the phrases of `keeper_forward`'s and `master_unprompted`'s fix hints
    and of the brief's IN THE BACKGROUND line. No speaker in the fiction says "the
    player"; when a quote does, our instruction leaked into it.
  * **a quote that names its own speaker in the third person.** A line attributed to X
    (`_quotes.speakers`: the tag, the clause, the line before) that names X, and is not X
    giving their name ("I'm Gorm", "the name's Gorm" — `narration.introductions`).
    Illeism is real speech, but rare enough that the false positives are cheaper than
    narration booked as a person's words.

Cut, never rewritten (`REWRITE = False`): the rewrite is what put it there. The backstop
cuts the line with its speech clause (`_quotes.cut_units`).
"""
from __future__ import annotations

import re

from gm.narration import Finding

ORDER = 65
KINDS = frozenset({"narration-in-quotes"})
DOORS = frozenset({"plan", "turn", "npc", "outcome"})
REWRITE = False

# The fix hints' and the brief's own wording, as it came back inside a quote.
_HINT_ECHO = re.compile(
    r"\bthe player\b"
    r"|\buntil (?:you|the player) turns? to\b"
    r"|\bonly (?:speaks?|answers?|talks?|responds?) (?:if|when|once) (?:you|the player)\b"
    r"|\b(?:remains?|remaining|stays?|staying|waits?|waiting)\b[^.!?]{0,40}"
    r"\buntil (?:you|the player)\b"
    r"|\bdoes not approach the\b"
    r"|\bin the background\b",
    re.I)


def quoted_narration(text: str, said, actors) -> list[tuple[str, str]]:
    """(line, why) for every quotation on the page that is narration in quotes."""
    from gm.checks._people import names_person
    from gm.checks._quotes import speakers
    from gm.narration import introductions

    out: list[tuple[str, str]] = []
    for _qa, _qb, line, ref in speakers(text, said, actors):
        if not line.strip():
            continue
        m = _HINT_ECHO.search(line)
        if m:
            out.append((line, f"the line holds a check's own wording ({m.group(0)!r})"))
            continue
        actor = actors.get(ref) if ref else None
        if actor is None:
            continue
        name = str(getattr(actor, "name", "") or "")
        if not name or not names_person(line, name):
            continue
        given = {w.lower() for _, n in introductions(line) for w in n.split()}
        if given & {w.lower() for w in name.split()}:
            continue            # X giving their own name is speech
        out.append((line, f"a line attributed to {name} ({ref}) names {name} in the "
                          f"third person"))
    return out


def find(ctx) -> list:
    actors = dict(getattr(ctx.scene, "actors", {}) or {})
    found = quoted_narration(ctx.text, ctx.said, actors)
    if not found:
        return []
    return [Finding(
        "narration-in-quotes",
        f"narration inside a speaker's quotation marks: {line[:100]!r} — {why}",
        "This is narration, not something anybody says: it does not belong in quotes.",
        weight=3, sentences=(line,)) for line, why in found]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut each flagged line with its speech clause."""
    from gm.checks._quotes import cut_units

    lines = [s for f in findings if f.kind in KINDS for s in f.sentences]
    out, gone = cut_units(text, lines)
    return out, [f"narration-in-quotes: cut {g[:80]!r}" for g in gone]
