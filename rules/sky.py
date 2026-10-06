"""The parts of the day that magic keeps, read off the world clock.

The owner's ruling of 2026-10-05 (docs/enchanting-answers.md, Round 4 point 10): **not
Earth's planets**. "This is not earth", and the Key of Solomon's planetary hours would name
seven worlds no world of World Bible's need have. What every world does have is a day, so
the timed windows of the enchanting bench are its phases: dawn, morning, noon, dusk, night
and midnight, each favouring some essence families in data (`phase` on the family, lane D),
and nothing here asks the world for anything.

Where the phases come from (searched 2026-10-05, before this file was written):

* **The game's own tradition.** D&D 3.5's divine caster prays for spells at a fixed time of
  day, and the SRD names the four that matter: "Dawn, dusk, noon, or midnight are common
  choices" (Player's Handbook p.179, reproduced at realmshelps.net/magic/divine.shtml).
  Pathfinder kept the rule and dropped the list: the time "is usually associated with some
  daily event" (Core Rulebook p.220, aonprd.com/Rules.aspx?ID=243). Those four turning
  points are the short windows here.
* **Folk practice ties work to the same four.** Magical plants were gathered before sunrise,
  with the dew still on them (Richard Folkard, *Plant Lore, Legends, and Lyrics*, 1884,
  gutenberg.org/ebooks/44638); the Slavic Lady Midday walks the fields only "on the hottest
  part of the day" (en.wikipedia.org/wiki/Lady_Midday); the witching hour is "the hour
  immediately after midnight" (en.wikipedia.org/wiki/Witching_hour). Hence the owner's
  examples: fire at noon, the dead at midnight, frost before dawn.
* **Games name phases off the clock and nothing else.** Pokémon Gold and Silver split the
  real clock into morning 04:00-09:59, day 10:00-17:59 and night 18:00-03:59, and gated
  evolutions on them (Eevee to Espeon by day, Umbreon by night; serebii.net/gs/
  evolution.shtml) — fixed windows, no sun, no season, which is exactly this app's clock.

The windows. The app has no sunrise: the engine's dawn is 06:00 (`Engine._camp_for` runs a
night to it) and night is 18:00-06:00 (`play/craft_views._is_night`, the survival rules'
window). Those two are the one constant pair below, so a world that later has seasons
changes one place. Each of the four turning points owns the two hours centred on it —
dawn 05:00-07:00, noon 11:00-13:00, dusk 17:00-19:00, midnight 23:00-01:00 — and the
stretches between are morning, afternoon and night (night in two pieces, either side of
midnight).

**Afternoon is not in the owner's list**, and is here on purpose: six names cannot cover a
day without calling 15:00 "noon" or "dusk", which the narrator's own hour check would call a
false hour (`gm/beat_verify.PARTS`: midday 10-14, dusk 16-21). Seven names keep every label
true; no essence family need favour the afternoon. Folding it into noon is a one-row change
to `_WINDOWS` if the owner rules that way. `tests/test_sky.py` holds every window inside the
narrator's window of the same word, so the bench and the prose can never disagree about the
hour.
"""
from __future__ import annotations

DAY = 24 * 60

# The engine's sunrise and nightfall (see the docstring). One pair, read by everything below.
DAWN_MINUTE = 6 * 60
DUSK_MINUTE = 18 * 60

# How long each turning point holds: an hour either side of its moment.
TURNING = 60

PHASES = ("dawn", "morning", "noon", "afternoon", "dusk", "night", "midnight")

# The phases the owner named (Round 4, point 10). An essence family's `phase` should be one
# of these; `afternoon` is accepted (see the docstring) but no family is expected to want it.
OWNER_PHASES = ("dawn", "morning", "noon", "dusk", "night", "midnight")

_NOON = (DAWN_MINUTE + DUSK_MINUTE) // 2
_MIDNIGHT = (_NOON + DAY // 2) % DAY

# (start minute of the day, phase), in clock order from 00:00. Each window runs to the next
# row's start; the last wraps into the first. Built from the constant pair, never typed in.
_WINDOWS: tuple[tuple[int, str], ...] = tuple(sorted((
    ((_MIDNIGHT + TURNING) % DAY, "night"),
    ((DAWN_MINUTE - TURNING) % DAY, "dawn"),
    ((DAWN_MINUTE + TURNING) % DAY, "morning"),
    ((_NOON - TURNING) % DAY, "noon"),
    ((_NOON + TURNING) % DAY, "afternoon"),
    ((DUSK_MINUTE - TURNING) % DAY, "dusk"),
    ((DUSK_MINUTE + TURNING) % DAY, "night"),
    ((_MIDNIGHT - TURNING) % DAY, "midnight"),
)))


def _check_phase(phase: str) -> str:
    p = str(phase or "").strip().lower()
    if p not in PHASES:
        raise ValueError(f"no phase of the day called {phase!r}; the phases are "
                         f"{', '.join(PHASES)}")
    return p


def phase_at(clock: int) -> dict:
    """The phase the clock stands in, and the world minutes it began and ends.

    `{"phase": "noon", "starts": 660, "ends": 780, "left": 42}`; `starts` and `ends` are
    absolute clock minutes (not minutes of the day), so `ends - clock` is the time left even
    across midnight. A night window is the stretch it is in now, not both pieces.
    """
    clock = int(clock or 0)
    day0 = clock - clock % DAY
    mod = clock % DAY
    # The window holding `mod`: the last start at or before it, else the last row of the
    # day before (midnight's window wraps across 00:00).
    idx = max((i for i, (s, _) in enumerate(_WINDOWS) if s <= mod), default=len(_WINDOWS) - 1)
    start, phase = _WINDOWS[idx]
    starts = day0 + start if start <= mod else day0 - DAY + start
    nxt = _WINDOWS[(idx + 1) % len(_WINDOWS)][0]
    ends = starts - start + nxt if nxt > start else starts - start + DAY + nxt
    return {"phase": phase, "starts": starts, "ends": ends, "left": ends - clock}


def inside(phase: str, clock: int) -> bool:
    return phase_at(clock)["phase"] == _check_phase(phase)


def next_phase(phase: str, clock: int) -> int:
    """Minutes until `phase` next begins; 0 if the clock already stands in it."""
    phase = _check_phase(phase)
    clock = int(clock or 0)
    if phase_at(clock)["phase"] == phase:
        return 0
    mod = clock % DAY
    waits = [(s - mod) % DAY for s, p in _WINDOWS if p == phase]
    return min(w for w in waits if w > 0)


def span_words(minutes: int) -> str:
    """A stretch of game time in words: "42 minutes", "3 hours 10 minutes", "6 days".

    The countdowns' words, shared by the bench's phase line and the In-progress section.
    Days round UP from two days on, so a countdown never says a thing is ready sooner than
    it is; under two days the hours are said, since "1 day" for 47 hours misleads by most
    of a day.
    """
    m = max(0, int(minutes or 0))
    if m < 60:
        return f"{m} minute{'s' if m != 1 else ''}"
    if m < DAY:
        h, r = divmod(m, 60)
        out = f"{h} hour{'s' if h != 1 else ''}"
        return out + (f" {r} minute{'s' if r != 1 else ''}" if r else "")
    if m < 2 * DAY:
        h = -(-(m - DAY) // 60)
        if h >= 24:                 # 47h01m rounds up to the second day, not "1 day 24 hours"
            return "2 days"
        return "1 day" + (f" {h} hour{'s' if h != 1 else ''}" if h else "")
    d = -(-m // DAY)
    return f"{d} days"


def words(clock: int, phase: str) -> str:
    """The bench's line for one phase: "Noon, 42 minutes left" inside it, "Midnight in 3
    hours 10 minutes" before it."""
    phase = _check_phase(phase)
    now = phase_at(clock)
    title = phase.capitalize()
    if now["phase"] == phase:
        return f"{title}, {span_words(now['left'])} left"
    return f"{title} in {span_words(next_phase(phase, clock))}"


def windows() -> list[dict]:
    """Every window of one day, for a page that draws the dial: `{phase, starts, ends}` in
    minutes of the day (an `ends` past 1440 wraps)."""
    out = []
    for i, (s, p) in enumerate(_WINDOWS):
        nxt = _WINDOWS[(i + 1) % len(_WINDOWS)][0]
        out.append({"phase": p, "starts": s, "ends": nxt if nxt > s else nxt + DAY})
    return out
