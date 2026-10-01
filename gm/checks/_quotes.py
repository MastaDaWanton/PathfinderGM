"""A line of speech as a unit: the quotation, the clause that says who spoke it, and who.

A helper, not a check. Three readers need the same answer and must not each grow a copy
(CLAUDE.md, "grep for every copy of a rule"): the sentence repair in `GMAgent.
_repair_sentences`, the cut-only backstops of `keeper_forward` and `master_unprompted`,
and the page attribution in `play/aftermath/speaker_real.py`.

**Why a unit and not the quotation.** Measured on the 2026-09-30 playtest (item 12):
`keeper_forward` flagged Gorm Vesper's spoken lines, and the repair spliced the model's
rewrite in with a string replace — INSIDE the quotation marks. The rewrite was narration
(it paraphrased the check's own fix hint, "…until you turn to them"), so it shipped as
`'Gorm Vesper watches you from their workspace, remaining silent until you turn to face
them.' he says` — five narration sentences in quotes across beats 51 and 53. The quote is
only a third of what the page says about speaking. PARC 3.0's attribution relation
(Pareti 2016, LREC, aclanthology L16-1619) has three spans — the *source* ("he"), the
*cue* ("says") and the *content* (the quotation) — and a repair that replaces the content
while keeping the cue and the source keeps the claim that somebody SAID it. So a repair
aimed at a line takes the whole relation: the quote and its clause.

The clause patterns were `speaker_real`'s (He et al. 2013; Muzny et al. 2017, the
quote-attribution sieves' "explicit clause" rule) and moved here unchanged, so both
readers find the same clause.
"""
from __future__ import annotations

import re

# The verbs a speech clause is made of. Kept narrow: "he turns" beside a quote is not
# saying it, and the attribution's later rules (the line before, the sentence before)
# catch the untagged rest.
_VERBS = (r"(?:says|said|asks|asked|adds|added|calls|called|mutters|muttered|murmurs|"
          r"murmured|replies|replied|answers|answered|continues|continued|grunts|grunted|"
          r"offers|offered|remarks|remarked|observes|observed|whispers|whispered|shouts|"
          r"shouted|growls|growled|drawls|drawled|notes|noted|tells|told|laughs|laughed|"
          r"snaps|snapped|rasps|rasped|barks|barked|presses|pressed|ventures|ventured|"
          r"chuckles|chuckled|sighs|sighed|grumbles|grumbled|demands|demanded|inquires|"
          r"enquires|repeats|repeated|insists|insisted|explains|explained|agrees|agreed|"
          r"admits|admitted|speaks|spoke|greets|greeted|puts\s+in|goes\s+on|went\s+on)")
_PRONOUN = r"(?:he|she|they|He|She|They)"
_DET = r"(?:the|a|an|this|that|The|A|An|This|That)"
_SUBJECT = r"(?P<subj>" + _PRONOUN + r"|" + _DET + r"\s+[^,.;:!?\n]{1,80}?)"
_ADVERB = r"(?:[a-z]+ly\s+)?"
# "…,' he says" / "…,' the woman in the doorway adds"
_AFTER = re.compile(r"^[\s,—–-]*" + _SUBJECT + r"\s+" + _ADVERB + _VERBS + r"\b")
# "…,' says the carter"
_AFTER_INVERTED = re.compile(r"^[\s,—–-]*" + _VERBS + r"\s+(?P<subj>" + _PRONOUN + r"|"
                             + _DET + r"\s+[^,.;:!?\n]{1,80}?)(?=[,.;:!?\n]|\s+(?:as|and|"
                             r"while|with|before|then)\b|$)")
# "The carter turns to you and asks, '…"
_BEFORE = re.compile(_SUBJECT + r"\s+(?:[a-z]+\s+){0,5}?" + _ADVERB + _VERBS
                     + r"(?:\s+[a-z]+){0,3}\s*[,:]?\s*$")
# A proper name as the clause's subject: "…,' Gorm says" / "Gorm Vesper says, '…".
_NAMED_AFTER = re.compile(r"^[\s,—–-]*(?P<subj>[A-Z][a-zA-Z'’-]+(?:\s+[A-Z][a-zA-Z'’-]+)?)"
                          r"\s+" + _ADVERB + _VERBS + r"\b")
_NAMED_BEFORE = re.compile(r"(?P<subj>[A-Z][a-zA-Z'’-]+(?:\s+[A-Z][a-zA-Z'’-]+)?)\s+"
                           r"(?:[a-z]+\s+){0,5}?" + _ADVERB + _VERBS
                           + r"(?:\s+[a-z]+){0,3}\s*[,:]?\s*$")


def _tail(blank: str, qb: int) -> str:
    """The narration after a quotation, up to its sentence's end."""
    tail = blank[qb:]
    cut = re.search(r"[.!?\n]", tail)
    return tail[:cut.start()] if cut else tail


def _head(blank: str, qa: int) -> str:
    """The narration before a quotation, from its sentence's start."""
    head = blank[:qa]
    start = max(head.rfind("."), head.rfind("!"), head.rfind("?"), head.rfind("\n"))
    return head[start + 1:]


def clause(blank: str, qa: int, qb: int, *, names: bool = False) -> str:
    """The subject of the speech clause beside the quotation at [qa, qb) of `blank`
    (`speech.blanked` of the beat), or "". `names=True` also reads a capitalised name as
    the subject ("…,' Gorm says"); `speaker_real` leaves it off, because a name there is
    somebody on the board, which is attribution and not a body."""
    tail = _tail(blank, qb)
    # After: up to the sentence's end — the blanked quotation keeps its closing mark, so
    # a line ending its own sentence ("…to start?'") has no clause after it.
    if re.search(r"[.!?\n]|\S", blank[qb:]):
        pats = (_AFTER, _AFTER_INVERTED) + ((_NAMED_AFTER,) if names else ())
        for pattern in pats:
            m = pattern.match(tail)
            if m:
                return m.group("subj")
    head = _head(blank, qa)
    for pattern in (_BEFORE,) + ((_NAMED_BEFORE,) if names else ()):
        m = pattern.search(head)
        if m:
            return m.group("subj")
    return ""


def _bounds(blank: str) -> list[tuple[int, int]]:
    from gm.narration import _SENTENCE

    return [m.span() for m in _SENTENCE.finditer(blank) if m.group(0).strip()]


def unit(text: str, qa: int, qb: int) -> tuple[int, int]:
    """(start, end) of the speech unit round the quotation at [qa, qb): the quotation,
    widened to the start of its sentence when what comes before it there is nothing or a
    speech clause ("He says, '…"), and to the end of its sentence when what follows is
    only punctuation or a speech clause ("…,' he says, his voice a low rasp."). Narration
    that is not a clause stays outside the unit: `He leans in. 'Depends.'` keeps its
    first sentence."""
    from gm import speech

    text = str(text or "")
    blank = speech.blanked(text)
    bounds = _bounds(blank)

    def _sentence(pos: int) -> tuple[int, int]:
        for lo, hi in bounds:
            if lo <= pos < hi:
                return lo, hi
        return pos, pos

    s0, _ = _sentence(qa)
    start = qa
    before = blank[s0:qa] if s0 < qa else ""
    if not before.strip() or _BEFORE.search(before) or _NAMED_BEFORE.search(before):
        start = s0 + (len(before) - len(before.lstrip())) if before.strip() else qa
    end = qb
    if speech._end_of(text, qa, qb) is None:
        # The line does not end its sentence: what follows in it is a clause or not.
        _, s1 = _sentence(qb - 1)
        s1 = max(s1, qb)
        after = blank[qb:s1]
        bare = after.strip(" \t,.!?;:—–-\"'“”‘’")
        if not bare or _AFTER.match(_tail(blank, qb)) or _AFTER_INVERTED.match(
                _tail(blank, qb)) or _NAMED_AFTER.match(_tail(blank, qb)):
            end = s1
            # Take the sentence's own closing quote mark too, when one follows.
            while end < len(text) and text[end] in "\"'”’":
                end += 1
    return start, end


def quote_of(text: str, line: str) -> tuple[int, int] | None:
    """(qa, qb) of the quotation on the page whose words are `line` — matched the way a
    tag is (`speech.speaker`), so a line a groomer trimmed still finds its quotation."""
    from gm import speech

    text = str(text or "")
    rec = [{"line": line}]
    for qa, qb in speech.spans(text):
        if speech.speaker(rec, text[qa + 1:qb - 1] if qb - qa >= 2 else ""):
            return qa, qb
    return None


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+([,.;:!?])", r"\1", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def cut_units(text: str, lines) -> tuple[str, list[str]]:
    """`text` without the speech units of the given lines, and the units cut.

    A head left dangling — "He leans in, " before a cut that took the sentence's end —
    is closed with a full stop, so the narration around a cut still reads as sentences."""
    text = str(text or "")
    found: list[tuple[int, int]] = []
    for line in lines or ():
        q = quote_of(text, str(line or ""))
        if q is None:
            continue
        found.append(unit(text, *q))
    if not found:
        return text, []
    found.sort()
    merged: list[list[int]] = []
    for a, b in found:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    cut: list[str] = []
    out = text
    for a, b in reversed(merged):
        cut.append(out[a:b].strip())
        head, rest = out[:a].rstrip(" \t"), out[b:].lstrip(" \t")
        took_end = bool(re.search(r"[.!?][\"'”’]?\s*$", out[a:b]))
        if took_end and head and head[-1] in ",;:—–-":
            head = head.rstrip(",;:—–- ") + "."
        glue = " " if head and rest and not head.endswith("\n") \
            and not rest.startswith("\n") else ""
        out = head + glue + rest
    cut.reverse()
    return _tidy(out), cut


# --- who a quotation belongs to ---------------------------------------------------------

def _board_mentions(blank: str, actors) -> list[tuple[int, str]]:
    """(offset, ref) of every mention of a person on the board in the narration."""
    from gm.checks._people import name_words

    out: list[tuple[int, str]] = []
    for ref, a in actors.items():
        if getattr(a, "is_pc", False):
            continue
        words = set(name_words(str(getattr(a, "name", "") or "")))
        words |= set(name_words(str(getattr(a, "true_name", "") or "")))
        for w in words:
            for m in re.finditer(r"\b" + re.escape(w) + r"(?:['’]s)?\b", blank, re.I):
                out.append((m.start(), ref))
    out.sort()
    return out


def speakers(text: str, said, actors) -> list[tuple[int, int, str, str]]:
    """(qa, qb, line, ref) for every quotation on the page, `ref` the person on the board
    it is attributed to, or "".

    The sieve order of Muzny et al. 2017, cheapest rules first, over the board only (the
    people the scene already holds — PDNC's lesson, Vishnubhotla et al. 2023):
      1. the prose call's own tag (`said`);
      2. an explicit clause beside it: a name on the board, or a pronoun carried to the
         nearest board mention before the line;
      3. the speaker of the line before it in the same paragraph, when it has no clause.
    """
    from gm import speech
    from gm.checks._people import names_person

    text = str(text or "")
    blank = speech.blanked(text)
    mentions = _board_mentions(blank, actors)
    out: list[tuple[int, int, str, str]] = []
    prev: tuple[int, str] | None = None
    for qa, qb in speech.spans(text):
        line = text[qa + 1:qb - 1] if qb - qa >= 2 else ""
        ref = ""
        rec = speech.speaker(list(said or ()), line)
        has_clause = False
        if rec is not None and rec.get("who") in actors:
            ref = str(rec["who"])
        else:
            subj = clause(blank, qa, qb, names=True)
            has_clause = bool(subj)
            if subj and subj.split()[0].lower() in ("he", "she", "they") \
                    and len(subj.split()) == 1:
                before = [r for at, r in mentions if at < qa]
                ref = before[-1] if before else ""
            elif subj:
                hits = [r for r, a in actors.items() if not getattr(a, "is_pc", False)
                        and names_person(subj, str(getattr(a, "name", "") or ""))]
                ref = hits[0] if len(hits) == 1 else ""
            if not has_clause and prev is not None and prev[1] \
                    and "\n\n" not in text[prev[0]:qa]:
                ref = prev[1]
        out.append((qa, qb, line, ref))
        prev = (qb, ref)
    return out
