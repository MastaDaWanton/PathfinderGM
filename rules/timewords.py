"""A time of day said in words, turned into the clock's minutes: "until dawn", "until ten at
night".

Moved here from gm/judgement.py on 2026-10-09 so the engine can read the time a player's
sleep runs to (`Engine._camp_for`) without importing the GM layer, and so the wait door
(`judgement.minutes_until`) and the sleep door read ONE table — CLAUDE.md's "when you fix a
rule, grep for every copy of it". Not in rules/sky.py, which by its own test imports
nothing at all (tests/test_sky.py, "the sky asks the world for nothing").

A closed vocabulary of named times and numbers, the interpreter's rule: "times stay words;
code turns them into minutes" (gm/interpret.py). The hours are the table's as they were;
dawn is `sky.DAWN_MINUTE`, so the night that runs "to the dawn" (`Engine._camp_for`) and
the sleep that runs "until dawn" end on the same minute.
"""
from __future__ import annotations

import re

from . import sky

_DAWN = sky.DAWN_MINUTE // 60
_UNTIL_HOUR = {"dark": 19, "nightfall": 19, "dusk": 19, "sunset": 19, "evening": 19,
               "dawn": _DAWN, "first light": _DAWN, "sunrise": _DAWN, "daybreak": _DAWN,
               "morning": 8, "noon": 12, "midday": 12, "midnight": 0}
_NUMBER = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
           "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
_UNTIL = re.compile(
    r"\b(?:until|till)\s+(?:it\s+is\s+)?(?:fully\s+|well\s+after\s+|after\s+)?(?:the\s+)?"
    r"(?:(?P<word>first light|nightfall|daybreak|sunrise|sunset|midnight|midday|morning|"
    r"evening|dark|dusk|dawn|noon)"
    r"|(?P<n>\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
    r"(?:\s*o'clock)?\s*(?P<half>am|pm|a\.m\.|p\.m\.|in the morning|in the afternoon|"
    r"in the evening|at night|tonight)?)\b", re.I)


def minutes_until(words: str, clock: int) -> int | None:
    """Minutes from `clock` to the next time the words name ("until ten at night", "until
    dawn"), or None when they name none. Always more than nothing: "until dawn" said AT
    dawn is the next one, a day on. Measured live 2026-09-27: "I wait at the well until ten
    at night" at mid-morning was planned as 140 minutes — the model's arithmetic."""
    m = _UNTIL.search(str(words or ""))
    if not m:
        return None
    if m.group("word"):
        hour = _UNTIL_HOUR[m.group("word").lower()]
    else:
        n = m.group("n").lower()
        hour = int(n) if n.isdigit() else _NUMBER.get(n, 0)
        half = (m.group("half") or "").lower().replace(".", "")
        if hour > 24:
            return None
        if half in ("pm", "in the afternoon", "in the evening", "at night", "tonight") \
                and hour < 12:
            hour += 12
        elif half in ("am", "in the morning") and hour == 12:
            hour = 0
        elif not half and hour < 12:
            # A bare "until ten": the next ten o'clock to come.
            now_h = (int(clock) % sky.DAY) / 60
            if hour <= now_h and hour + 12 > now_h:
                hour += 12
        hour %= 24
    now = int(clock) % sky.DAY
    return ((hour * 60 - now) % sky.DAY) or sky.DAY
