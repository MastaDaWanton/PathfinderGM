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


# --- who said it: speaker tags written by the prose call ----------------------------------
#
# docs/declared-not-guessed.md, the first door (2026-09-25). The prose call writes a line of
# dialogue as `<say who=c3 to=you>'You're a long way from home.'</say>`; the tags are
# lifted out here, the moment a reply arrives, before any check or rewrite reads the text,
# and what they said is kept beside the beat as `Said` records. Guessing the speaker after
# the fact from the words round the quote is what `hailed_by` and `introductions` did, and
# it misread; the model knows who is talking while it writes.
#
# Keyed by the words of the line, never by offsets: every groomer after this point may
# rewrite the beat, and a record whose line no longer appears simply stops matching, so a
# rewrite costs a fallback to the old guess rather than a wrong speaker.

_SAY_OPEN = re.compile(r"<\s*say\b([^<>]*)>", re.I)
_SAY_CLOSE = re.compile(r"<\s*/\s*say\s*>", re.I)
_ATTR = re.compile(r"\b(who|to)\s*=\s*(?:\"([^\"<>]*)\"|'([^'<>]*)'|([^\"'\s<>]+))", re.I)


def _key(line: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", str(line or "").lower().replace("’", "'")))


def lift(text: str, refs=None, names=None) -> tuple[str, list[dict]]:
    """(the beat with every speaker tag removed, the lines they attributed).

    Each record is {"who": ref, "to": "you" | ref | "", "line": what was said}. `refs`
    are the scene's refs: a tag naming anything else keeps its words and loses its
    attribution — its record has an empty "who" and the claim in "was", so the miss can
    be counted — and never books anybody. `names` maps a lowercase name or descriptor to its
    ref, for the model that writes `who="the smith"` instead of the ref it was shown.
    Unclosed and stray tags are removed; a tag with no quotation inside keeps its words
    and is wrapped in quote marks, because the model tagged it as speech.
    """
    text = str(text or "")
    if "<" not in text:
        return text, []
    known = set(refs or [])
    by_name = {str(k).lower(): v for k, v in (names or {}).items()}
    said: list[dict] = []
    out: list[str] = []
    at = 0
    for m in _SAY_OPEN.finditer(text):
        if m.start() < at:
            continue
        out.append(text[at:m.start()])
        close = _SAY_CLOSE.search(text, m.end())
        nxt = _SAY_OPEN.search(text, m.end())
        if close is None or (nxt is not None and nxt.start() < close.start()):
            # Unclosed: the words run on as they are, unattributed.
            at = m.end()
            continue
        inner = text[m.end():close.start()]
        attrs = {k.lower(): (a or b or c) for k, a, b, c in _ATTR.findall(m.group(1))}
        claimed = who = attrs.get("who", "").strip()
        if who not in known:
            who = by_name.get(who.lower().replace("_", " "), "") if who else ""
        to = attrs.get("to", "").strip().lower()
        to = "you" if to in ("you", "pc", "player") else (to if to in known else "")
        found = spans(inner)
        if not found and inner.strip():
            inner = f"“{inner.strip()}”"
            found = spans(inner)
        if who or claimed:
            for a, b in found:
                line = inner[a + 1:b - 1] if b - a >= 2 else ""
                if line.strip():
                    rec = {"who": who, "to": to, "line": line.strip()}
                    if not who:
                        # Kept, with what the model claimed, so the miss can be counted;
                        # an empty `who` attributes nothing to anybody.
                        rec["was"] = claimed
                    said.append(rec)
        out.append(inner)
        at = close.end()
    out.append(text[at:])
    clean = _SAY_CLOSE.sub("", "".join(out))
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    return clean, said


def retag(text: str, said) -> str:
    """The beat with its recorded speakers written back round their lines — `lift`
    undone — for the one place the model is shown its own earlier prose.

    Measured on the first live run with tags (2026-09-25, gemma-4-12B, 12 turns): tagging
    was all or nothing per beat, 4 beats tagged and 4 not, and the untagged ones followed
    a tagged beat that the prompt had shown back to the model with its tags lifted out —
    two beats of its own untagged speech in front of it, against the examples' tagged
    ones. Demonstration volume beats instruction volume (CLAUDE.md), and the nearest
    demonstration was ours.
    """
    text = str(text or "")
    if not said:
        return text
    out, at = [], 0
    for a, b in spans(text):
        rec = speaker(said, text[a + 1:b - 1] if b - a >= 2 else "")
        if not rec or not rec.get("who"):
            continue
        to = f" to={rec['to']}" if rec.get("to") else ""
        out.append(text[at:a])
        out.append(f"<say who={rec['who']}{to}>{text[a:b]}</say>")
        at = b
    out.append(text[at:])
    return "".join(out)


def speaker(said, line: str) -> dict | None:
    """The record whose line this is, if the prose tagged it. Equal words first; then one
    containing the other, for a groomer that trimmed a line's tail — but only for lines of
    four words or more, where containment is not an accident."""
    want = _key(line)
    if not want:
        return None
    for rec in said or []:
        if _key(rec.get("line", "")) == want:
            return rec
    for rec in said or []:
        have = _key(rec.get("line", ""))
        if len(want.split()) >= 4 and len(have.split()) >= 4 and (want in have or have in want):
            return rec
    return None


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
