"""Where the speech is in a GM beat. One scanner, read by every pass that needs to know.

Measured 2026-09-25: nine separate rules answered "is this inside a quotation?" and they
disagreed. `narration._QUOTED` opened on ‘ but closed only on a double quote; two
`re.split` copies read the apostrophe in "guards'" and "it's" as a close and flipped
narration and speech for the rest of the beat; `_ANY_SPEECH` could not cross "it's";
no rule at all recognised curly single quotes, which is how the phantom elder of
2026-09-24 could still be reproduced — `place_the_face` wrote "The elder is a stooped
man…" into the middle of Korgath's ‘…’ line. Each copy had been fixed for the case in
front of it; none was fixed for the others. CLAUDE.md: "when you fix a rule, grep for
every copy of it" — this module is the answer to having to.

A scanner rather than a regex, because the one hard question is contextual: an
apostrophe INSIDE a word ("don't", "it's", "don’t" — the curly close and the curly
apostrophe are the same character) is part of the line, never its close. A close is a
quote mark not followed by a letter or a digit.

The rules:
  - "…" and “…”: a double quote opens anywhere. Unclosed, it runs to the end of its
    paragraph — the convention for a speech that goes on into the next paragraph.
  - '…' and ‘…’: a single quote opens only at the start of the text, after whitespace or
    after an opening bracket or dash, and only before a non-space. It closes on a single
    quote that is not followed by a letter or digit. Unclosed by the end of the
    paragraph, it was never a quotation: "gave 'em a hiding" and "'tis" are elisions.
  - Inside a quotation the other kind of mark is nested speech, and part of it.

Offsets are the point. `blanked` keeps the length so a detector can read the narration
and still point back into the original beat; `unquoted` collapses each quotation to one
space for the passes that only read words.
"""
from __future__ import annotations

import re

_DOUBLE_OPEN = "\"“‟"
_DOUBLE_CLOSE = {"\"": "\"“”", "“": "”\"", "‟": "”\""}
_SINGLE_OPEN = "'‘"
_SINGLE_CLOSE = "'’"
_OPENS_AFTER = "([{—–-\"“"


def _closes(text: str, i: int) -> bool:
    """A single quote at `i` is a close unless a letter or a digit follows it."""
    nxt = text[i + 1] if i + 1 < len(text) else ""
    return not nxt.isalnum()


def _paragraph_end(text: str, i: int) -> int:
    j = text.find("\n\n", i)
    return len(text) if j < 0 else j


def spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of every quotation in `text`, quote marks included, in order."""
    text = str(text or "")
    out: list[tuple[int, int]] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in _DOUBLE_OPEN:
            closers = _DOUBLE_CLOSE[ch]
            j = i + 1
            end = _paragraph_end(text, i)
            while j < end and text[j] not in closers:
                j += 1
            stop = j + 1 if j < end else end
            out.append((i, stop))
            i = stop
            continue
        if ch in _SINGLE_OPEN:
            prev = text[i - 1] if i else ""
            nxt = text[i + 1] if i + 1 < n else ""
            opens = (ch == "‘" or not prev or prev.isspace() or prev in _OPENS_AFTER)
            if opens and nxt and not nxt.isspace():
                end = _paragraph_end(text, i)
                j = i + 1
                while j < end:
                    # A space BEFORE the close is allowed: the model writes "Which path
                    # will you take? '" — measured on the real Korgath beat of
                    # 2026-09-24, and a rule refusing it read his whole speech as
                    # narration and booked the elder again.
                    if text[j] in _SINGLE_CLOSE and _closes(text, j):
                        break
                    j += 1
                if j < end:
                    out.append((i, j + 1))
                    i = j + 1
                    continue
        i += 1
    return out


def _end_of(text: str, a: int, b: int) -> int | None:
    """Where the sentence-ending mark of a quotation stands — the "!" of `"Enough!"` —
    or None when the line does not end a sentence (`'Go home,' the guard says`)."""
    k = b - 1
    while k > a and (text[k] in "\"'“”‘’" or text[k].isspace()):
        k -= 1
    if not (k > a and text[k] in ".!?"):
        return None
    # And only when a new sentence follows. `Ashla says "We go. Now." and turns away.`
    # is one sentence: the line's full stop is hers, and the narration carries on.
    rest = text[b:].lstrip(" \t")
    if rest and not (rest[0].isupper() or rest[0] == "\n"):
        return None
    return k


def blanked(text: str) -> str:
    """`text` with every quotation's characters turned to spaces, the same length —
    except the mark that ends the sentence, which stays where it stands.

    Kept because the sentence splitters read this: `He yells, "Enough!" The crowd gasps.`
    blanked whole is ONE sentence, and a cut aimed at the yell took the crowd with it
    (measured 2026-09-25)."""
    text = str(text or "")
    out = list(text)
    for a, b in spans(text):
        keep = _end_of(text, a, b)
        for k in range(a, b):
            if k != keep and not out[k].isspace():
                out[k] = " "
    return "".join(out)


def unquoted(text: str) -> str:
    """`text` with each quotation replaced by one space — and its sentence-ending mark,
    when it had one, so the sentences around it still split where they did."""
    text = str(text or "")
    parts, at = [], 0
    for a, b in spans(text):
        parts.append(text[at:a])
        keep = _end_of(text, a, b)
        parts.append(" " if keep is None else f" {text[keep]} ")
        at = b
    parts.append(text[at:])
    return "".join(parts)


def split(text: str) -> list[tuple[bool, str]]:
    """The beat as alternating runs, (is_speech, run). Joined back, it is `text`."""
    text = str(text or "")
    out: list[tuple[bool, str]] = []
    at = 0
    for a, b in spans(text):
        if a > at:
            out.append((False, text[at:a]))
        out.append((True, text[a:b]))
        at = b
    if at < len(text):
        out.append((False, text[at:]))
    return out


def lines(text: str) -> list[str]:
    """What was said: each quotation's inside, marks stripped."""
    text = str(text or "")
    return [text[a + 1:b - 1] if b - a >= 2 else "" for a, b in spans(text)]


def has_speech(text: str, min_chars: int = 1) -> bool:
    """Whether anybody speaks in `text`: a quotation with at least `min_chars` inside."""
    return any(len(s.strip()) >= min_chars for s in lines(text))


def inside(text: str, offset: int) -> bool:
    """Whether `offset` falls inside a quotation."""
    return any(a <= offset < b for a, b in spans(text))


# --- one sentence at a time --------------------------------------------------------------
#
# Some passes work on a single sentence cut out of a beat, where a quotation that runs
# across several sentences has lost its close. `spans` rightly refuses an unclosed single
# quote (it may be an elision), so these ask the lenient question — is there an OPENING
# mark here? — and they live here, beside the scanner, rather than as a tenth rule.

# An opening single quote is followed by the first letter of the line, never a space:
# "' The merchant nods" is the CLOSE of the sentence before, left at the front of this
# one by the sentence split — read as an opener it shielded a dead man's "nods" from
# `cut_dead_men_walking` (test_the_dead_cannot_talk_their_way_past_the_scrubber).
_OPENING_MARK = re.compile(r"(?:^|(?<=[\s,:(\[—–-]))['‘](?=\S)|[\"“]")
_LINE_OPENER = re.compile(r"[\"“”'‘’]\s*([A-Z][a-zA-Z'’-]{2,})")


def opens(sentence: str) -> bool:
    """Whether a sentence has speech opening in it — a double quote anywhere, a single
    quote at a word boundary (never the apostrophe inside "it's")."""
    return bool(_OPENING_MARK.search(str(sentence or "")))


def first_opening(sentence: str) -> int | None:
    """Where the first opening quote mark in a sentence stands, or None."""
    m = _OPENING_MARK.search(str(sentence or ""))
    return m.start() if m else None


def line_openers(sentence: str) -> set[str]:
    """The capitalised words that open somebody's line in this sentence: "Enjoy",
    "Ask", "Meet" — the first word of speech, which is not a name."""
    return {m.group(1) for m in _LINE_OPENER.finditer(str(sentence or ""))}
