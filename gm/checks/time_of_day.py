"""The hour the page says, against the hour the engine keeps (playtest 2026-10-03, item 11).

Measured on the owner's two saves of 2026-10-03 (Kesst in Zhilvarnia). The engine's clock
went from 0 to 88 minutes — a little past midnight, which is what the brief told the
narrator every turn ("WHEN (fact): day 1, deep in the night (about midnight)") — and the
page went: "the frantic, rhythmic work of the morning" at the docks, then "the first hint
of dawn is beginning to grey the edges of the windows", then "the pre-dawn gloom". The
clock never left the night; the prose ran a whole day backwards and forwards round it.
(The opening had said "Evening": that save began before the clock started at the
opening's hour, 2026-09-27 — see docs/where-and-when.md.)

The traditions agree on who owns the hour. Inform keeps `the time of day` itself and an
author's text asks it ("if the time of day is after …", WI §9.6); CircleMUD's
`another_hour` moves `time_info.hours` and only then sends "The sun rises in the east" to
the rooms outdoors; Evennia's extended room shows only the text tagged for the current
slot of the game clock. None lets the description decide what time it is. Here the
description is a model's prose, so it is checked: detect in code, repair without a call.

**What counts as the narrator saying what time it is NOW**, narration only (a character
may talk about "the morning shift" or "midnight" whenever they like):

  * an hour word before a word for the air, the light or the sky — "the midnight air",
    "the pre-dawn gloom", "the morning sun", "the evening light";
  * the busy-ness OF an hour — "the work of the morning", "the hush of the night";
  * the first light or the last — "the first hint of dawn", "the glow of sunset";
  * "it is morning", "it's nearly midnight";
  * the sun or the dark doing something — "the sun beats down", "night is falling".

Never "tomorrow morning", "since dawn", "until evening", "every night", "last night":
those are other hours. The windows are generous on purpose (evening runs 16:00-23:59,
night 18:00-06:59): a narrator calling 19:00 "night" is not wrong, and a guard that
argues with dusk is noise.

**The repair is the clock's own word**, put where the wrong one stood: "the work of the
morning" at 20:00 is "the work of the evening", "the first hint of dawn" is "the first
hint of dusk". `REWRITE = False` — no model call (item 26: every lane should avoid
adding them). A sentence whose claim is a verb ("the sun rises", "night is falling") has
no word to swap, and is cut.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from . import _space

ORDER = 58
KINDS = frozenset({"time-of-day"})
DOORS = frozenset({"plan", "turn", "npc", "outcome"})
REWRITE = False

DAY = 24 * 60

# Each hour word and the hours (0-23) at which a narrator may truthfully say it. Longest
# alternatives first in the pattern below, so "pre-dawn" is not read as "dawn".
_TRANSITION_DAWN = ("pre-dawn", "predawn", "first light", "daybreak", "sunrise", "sun-up",
                    "dawn")
_TRANSITION_DUSK = ("sundown", "sunset", "nightfall", "twilight", "dusk", "gloaming")


def _hours(a: int, b: int) -> frozenset[int]:
    """a..b inclusive, wrapping past midnight."""
    out, h = set(), a
    while True:
        out.add(h % 24)
        if h % 24 == b % 24:
            return frozenset(out)
        h += 1


WINDOWS: dict[str, frozenset[int]] = {}
for _w in _TRANSITION_DAWN:
    WINDOWS[_w] = _hours(3, 8)
for _w in _TRANSITION_DUSK:
    WINDOWS[_w] = _hours(16, 21)
WINDOWS.update({
    "early morning": _hours(3, 10), "mid-morning": _hours(7, 12),
    "late morning": _hours(8, 13), "morning": _hours(4, 11),
    "noonday": _hours(10, 14), "mid-day": _hours(10, 14), "midday": _hours(10, 14),
    "noon": _hours(10, 14),
    "late afternoon": _hours(14, 19), "afternoon": _hours(12, 18),
    "early evening": _hours(15, 21), "evening": _hours(16, 23),
    "night-time": _hours(18, 6), "nighttime": _hours(18, 6), "night": _hours(18, 6),
    "midnight": _hours(21, 4), "small hours": _hours(0, 5), "dead of night": _hours(21, 4),
})
_TIME = "|".join(re.escape(w) for w in sorted(WINDOWS, key=len, reverse=True))

# The air, the light, the sky: what an hour word in front of it describes as present.
_ATMOS = (r"air|light|sun|sunlight|sunshine|sky|skies|gloom|chill|cold|heat|warmth|mist|"
          r"mists|fog|haze|quiet|hush|stillness|darkness|dark|shadows?|glow|breeze|wind|"
          r"bustle|rush|calm|silence|dew|murk|grey|gray|half-light|stars|moon|moonlight|"
          r"streets?|crowds?")
# The busy-ness of an hour.
_OF_NOUN = (r"work|bustle|business|trade|light|air|chill|quiet|hush|heat|warmth|rush|"
            r"crowds?|noise|stillness|gloom|darkness|cold|calm|clamou?r|din|traffic|"
            r"hubbub|lull|dead|depths?|middle|small\s+hours")
# "through" is NOT here: "you move through the pre-dawn gloom" is the gloom you are in
# (the owner's save, turn 21), where "through the night" would be a duration.
_NOT_NOW = (r"(?:tomorrow|yesterday|last|next|until|till|since|every|each|before|after|"
            r"by|come|all|throughout|one|that|some|toward|towards|in\s+the|this)")

_FORMS = (
    # "the midnight air", "the pre-dawn gloom", "the cold morning light"
    re.compile(r"\b(?:the|a|an)\s+(?:[a-z'’-]+\s+){0,2}?(?P<t>" + _TIME + r")(?:['’]s)?\s+"
               r"(?:" + _ATMOS + r")\b", re.I),
    # "the frantic, rhythmic work of the morning", "the hush of night"
    re.compile(r"\b(?:" + _OF_NOUN + r")\s+of\s+(?:the\s+)?(?:early\s+|late\s+)?"
               r"(?P<t>" + _TIME + r")\b(?!['’]s)", re.I),
    # "the first hint of dawn", "the glow of sunset" (index `_LIGHT_FORM`)
    re.compile(r"\b(?:hint|touch|glow|blush|grey|gray|edge|promise|herald|first|last|"
               r"light|colou?r|break)\s+of\s+(?:the\s+)?(?P<t>" + _TIME + r")\b", re.I),
    # "It is morning", "it's nearly midnight", "it is late evening now"
    re.compile(r"\b(?:it\s+is|it['’]s|it\s+was|now)\s+(?:now\s+|nearly\s+|almost\s+|"
               r"already\s+|well\s+past\s+)?(?:the\s+)?(?P<t>" + _TIME + r")\b", re.I),
)
_LIGHT_FORM = 2
# Verb claims: no single word to put right, so the sentence goes.
_VERBS = (
    re.compile(r"\b(?P<t>dawn|day|night|morning|evening|dusk|twilight|darkness)\s+"
               r"(?:is\s+breaking|breaks|broke|has\s+broken|is\s+falling|falls|fell|has\s+"
               r"fallen|is\s+coming\s+on|comes\s+on|creeps\s+in|settles\s+in|is\s+drawing\s+"
               r"in|draws\s+in)\b", re.I),
    re.compile(r"\bthe\s+sun\s+(?P<v>rises|is\s+rising|has\s+risen|climbs|is\s+climbing|"
               r"is\s+high|stands\s+high|beats\s+down|blazes|sets|is\s+setting|has\s+set|"
               r"sinks|is\s+sinking|dips)\b", re.I),
)
_SUN = {"rise": _hours(4, 9), "high": _hours(9, 16), "set": _hours(15, 21)}


def _sun_window(verb: str) -> frozenset[int]:
    v = verb.lower()
    if "ris" in v or "climb" in v:
        return _SUN["rise"]
    if "high" in v or "beat" in v or "blaz" in v:
        return _SUN["high"]
    return _SUN["set"]


def _verb_window(word: str) -> frozenset[int]:
    w = word.lower()
    if w in ("day", "dawn", "morning"):
        return WINDOWS["dawn"] if w != "morning" else WINDOWS["morning"]
    if w in ("night", "darkness"):
        return _hours(16, 22)                  # night FALLING is dusk
    return WINDOWS.get(w, WINDOWS["evening"])


def hour_of(clock: int) -> int:
    return (int(clock or 0) % DAY) // 60


def clock_word(clock: int, said: str) -> str:
    """The word for the clock's hour that stands where `said` stood: a transition word
    (dawn, dusk) answers with the transition the clock is in, else the part of the day."""
    h = hour_of(clock)
    w = said.lower()
    if w in _TRANSITION_DAWN or w in _TRANSITION_DUSK:
        if 16 <= h <= 21:
            return "dusk"
        if 4 <= h <= 7:
            return "dawn"
    if w in ("midnight", "dead of night", "small hours") and (h >= 21 or h <= 4):
        return w
    if h <= 4 or h >= 22:
        return "night"
    if h <= 11:
        return "morning"
    if h <= 13:
        return "midday"
    if h <= 16:
        return "afternoon"
    return "evening"


def _not_now(narration: str, start: int) -> bool:
    before = narration[max(0, start - 24):start].lower()
    return bool(re.search(r"\b" + _NOT_NOW + r"\s+(?:the\s+)?(?:[a-z'’-]+\s+)?$", before))


def wrong_hours(narration: str, clock: int) -> list[tuple[str, int, int, bool]]:
    """Every claim about the present hour in a stretch of narration that the clock does
    not allow: `(word, start, end, swappable)`, start/end the hour word's own span."""
    h = hour_of(clock)
    out: list[tuple[str, int, int, bool]] = []
    for n, rx in enumerate(_FORMS):
        for m in rx.finditer(narration):
            word = m.group("t")
            if h in WINDOWS[word.lower()] or _not_now(narration, m.start()):
                continue
            if any(a <= m.start("t") < b for _w, a, b, _s in out):
                continue
            # "the first hint of dawn" takes dusk at dusk, but at one in the morning
            # there is no light coming to have a first hint of — "the first hint of
            # night" was the substitution's own nonsense, so that sentence is cut.
            swappable = n != _LIGHT_FORM or clock_word(clock, word) in ("dawn", "dusk")
            out.append((word, m.start("t"), m.end("t"), swappable))
    for rx in _VERBS:
        for m in rx.finditer(narration):
            window = (_sun_window(m.group("v")) if "v" in rx.groupindex
                      else _verb_window(m.group("t")))
            if h in window:
                continue
            out.append((m.group(0), m.start(), m.end(), False))
    return out


def _narration(sentence: str):
    from gm import speech

    return [(is_speech, chunk) for is_speech, chunk in speech.split(sentence)]


def flagged_in(sentence: str, clock: int) -> list[tuple[str, int, int, bool]]:
    return [hit for is_speech, chunk in _narration(sentence) if not is_speech
            for hit in wrong_hours(chunk, clock)]


def _clock(ctx) -> int | None:
    clock = getattr(ctx.scene, "clock_minutes", None)
    return None if clock is None else int(clock)


def find(ctx) -> list[Finding]:
    clock = _clock(ctx)
    if clock is None:
        return []
    flagged: list[tuple[str, list[str]]] = []
    for s in _space.sentences(ctx.text):
        hits = flagged_in(s, clock)
        if hits:
            flagged.append((s, [w for w, *_ in hits]))
    if not flagged:
        return []
    from rules import residency

    now = residency.time_words(clock)
    said = list(dict.fromkeys(w for _s, ws in flagged for w in ws))
    return [Finding(
        kind="time-of-day",
        detail=f"the page says " + ", ".join(repr(w) for w in said)
               + f" — the engine's clock says {now}",
        fix_hint=(f"It is {now}: the engine keeps the clock. Say "
                  f"{clock_word(clock, said[0])!r}, not "
                  + ", ".join(repr(w) for w in said) + "."),
        weight=2, sentences=tuple(s for s, _w in flagged))]


def _case(like: str, word: str) -> str:
    return word[:1].upper() + word[1:] if like[:1].isupper() else word


def put_right(sentence: str, clock: int) -> str | None:
    """The sentence with every wrong hour word replaced by the clock's, narration only;
    None when a claim in it has no word to swap (a verb claim)."""
    parts = []
    for is_speech, chunk in _narration(sentence):
        if is_speech:
            parts.append(chunk)
            continue
        hits = wrong_hours(chunk, clock)
        if any(not swappable for *_x, swappable in hits):
            return None
        for word, a, b, _s in sorted(hits, key=lambda x: -x[1]):
            chunk = chunk[:a] + _case(word, clock_word(clock, word)) + chunk[b:]
        parts.append(chunk)
    return "".join(parts)


def backstop(ctx, text: str, findings: list) -> tuple[str, list[str]]:
    clock = _clock(ctx)
    if clock is None:
        return text, []
    notes: list[str] = []
    for f in findings:
        if f.kind != "time-of-day":
            continue
        for s in f.sentences:
            if s not in text:
                continue
            fixed = put_right(s, clock)
            if fixed is None or flagged_in(fixed, clock):
                text = re.sub(r"\s*" + re.escape(s), "", text, count=1).strip()
                notes.append(f"time of day: cut {s[:80]!r}")
            elif fixed != s:
                text = text.replace(s, fixed, 1)
                notes.append(f"time of day: {fixed[:80]!r}")
    return text, notes
