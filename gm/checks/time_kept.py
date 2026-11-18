"""The page passes no time the engine did not: nobody sleeps the night on an unmoved clock.

Measured on a scratch save of 2026-10-16 (gemma-4-12B, Pangrella, turn_log row 125): every
plan for "I say goodbye to the barkeep, go back up to my room and sleep until dawn" was
refused, the turn fell to narration only, and the page said "You collapse onto the pallet…
sleep takes hold. When you finally stir, the light has changed" while the engine's clock
had not moved a minute. The read-back (`beat_verified`) ran on that door and its move and
hour rows both passed: the stairs went to no place the engine lists, and "the sun is
hanging lower in the sky" was true of the clock as it stood. No row asked whether hours
went by — which is the thing a degraded turn most often narrates, because it is what the
player asked for and nothing in the plan did it.

The mirror of `sleep_kept` (the player under who wakes on the page).

**Detection** is a model's, held in code: when the reading has the player ask for time to
pass (a `rest`, `wait` or `journey` act), the engine moved the clock less than an hour this
turn, and the player is not under (`sleep_kept` owns that), one closed question
asks which sentence first has the player fall asleep or let hours go by
(`deed_reader.read_slept`); the sentence must be about the player. Asked only on a turn
the clock stood still, so a false alarm can only cost a sentence the engine contradicts.

**Repair** is the house shape: one rewrite of that sentence with the engine's fact named;
then the backstop — cut from it (every sentence after a night the engine never passed is
set in a morning that did not come, `hold_the_door`'s shape) and close on an authored line,
least-recently-used per campaign and marked ours (`authored_in`, D4).

Not measured on a bench: the one recorded beat above, replayed in
tests/test_time_kept.py. The reader is the deed reader's model and shape.
"""
from __future__ import annotations

from gm.narration import Finding

from ._page import cut_from

ORDER = 63
KINDS = frozenset({"time-passed-unrun"})
DOORS = frozenset({"turn"})

# Less than this many minutes on the clock is "no time passed" for a page that sleeps:
# a beat's own business (a talk, a search, a short wait) moves it by minutes, a night by
# hundreds.
STILL_MINUTES = 60

POOL: tuple[str, ...] = (
    "The hour has not moved; you are still awake, and still here.",
    "No time has gone by yet — you are as awake as you were, where you were.",
    "None of the day has passed; you are wide awake still.",
)


# The reading's acts that ask for time to pass (gm/interpret.py ACT_SLOTS, a closed list):
# the page is only asked about hours on a turn the player asked for hours. Asked on every
# turn the clock stood still, this was one more model call on nearly every turn of play.
ASKS_FOR_TIME = frozenset({"rest", "wait", "journey"})


def _refused_rest(ctx):
    """This turn's refused `rest` outcome, or None.

    Measured live 2026-10-17 (dn-live, the inn): "I pay for a room for the night and go to
    bed" while in conversation — the rest was refused ("You are still in conversation with
    the one behind the bar… Take your leave first."), and the page had the keys handed
    over, the room secured, a room found at the back and the player lying down. The
    read-back cut the one sentence it read as a sale; the keys, the room and the bed were
    no claim any of its rows could make, and the refusal itself was nowhere on the page."""
    for o in getattr(ctx, "outcomes", ()) or ():
        get = o.get if isinstance(o, dict) else (lambda k, _o=o: getattr(_o, k, None))
        if get("op") == "rest" and get("status") == "refused" and str(get("tell") or ""):
            return o
    return None


def _refusal_line(o) -> str:
    tell = o.get("tell") if isinstance(o, dict) else getattr(o, "tell", "")
    return " ".join(str(tell or "").split())


def _still(ctx) -> bool:
    """The player is up, and either the engine refused their rest, or their words asked for
    time to pass and the clock moved less than STILL_MINUTES this turn."""
    from gm import interpret
    from rules import survival

    pc = ctx.scene.pc() if hasattr(ctx.scene, "pc") else None
    if pc is None or pc.is_down or survival.asleep(pc) is not None:
        return False
    # The clock first, whatever was refused: hours the engine passed are hours that went
    # by. Measured on the bench of 2026-11-02 (the night in the condemned cell, 2 of 3
    # runs): the rest was refused ("still in conversation …") while the trial passed 672
    # minutes, and this backstop cut "the hours bleed into one another as you sit in the
    # dim, damp cell" — the trial's own "the night passes in the cell" — and wrote the
    # refusal in its place.
    was = getattr(ctx, "was_clock", None)
    now = getattr(ctx.scene, "clock_minutes", None)
    try:
        if was is not None and now is not None and int(now) - int(was) >= STILL_MINUTES:
            return False
    except (TypeError, ValueError):
        pass
    if _refused_rest(ctx) is not None:
        return True
    reading = getattr(ctx, "reading", None) or {}
    if not any(a.get("act") in ASKS_FOR_TIME and interpret.acting(a)
               for a in reading.get("actions") or [] if isinstance(a, dict)):
        return False
    if was is None or now is None:
        return False
    try:
        int(now) - int(was)
    except (TypeError, ValueError):
        return False
    return True


def _slept(ctx, text: str) -> str:
    from gm import deed_reader

    route = dict(getattr(ctx, "reader", None) or {})
    if not _still(ctx) or not deed_reader.ENABLED or not route.get("model"):
        return ""
    pc = ctx.scene.pc()
    sentence, error = deed_reader.read_slept(
        text, **route, pc_name=str(getattr(pc, "name", "") or ""),
        refused=_refused_rest(ctx) is not None)
    if error:
        raise RuntimeError(f"the page could not be read for time passing: {error}")
    return sentence


def _moved(ctx) -> int:
    """The minutes the engine passed this turn (0 when unknown)."""
    try:
        return max(0, int(ctx.scene.clock_minutes) - int(getattr(ctx, "was_clock", None)))
    except (TypeError, ValueError):
        return 0


def _cut(ctx, text: str, sentence: str) -> str:
    """The page without the flagged sentence and what follows it — in its own slot only,
    on a planned beat. jack T211 (owner's save 2026-11-17): "I wait for the innkeepers
    response" passed ten minutes, the page's "as the minutes pass" was read as hours, and
    the cut ran to the end of the page and took the innkeeper's reply with it; what
    another slot wrote is not set in the morning that never came."""
    from gm import narration, planned

    slots = [s for s in getattr(ctx, "slots", ()) or ()
             if isinstance(s, dict) and str(s.get("wrote") or "").strip()]         if getattr(ctx, "planned", False) else []
    n = planned.slot_of(sentence, slots) if slots else None
    if n is None:
        return cut_from(text, sentence)
    page = narration._sentences(text)
    at = next((i for i, x in enumerate(page) if x == sentence.strip()), None)
    if at is None:
        return cut_from(text, sentence)
    for x in page[at:]:
        if planned.slot_of(x, slots) == n:
            text = text.replace(x, "", 1)
    return text.strip()


def find(ctx) -> list:
    sentence = _slept(ctx, ctx.text)
    if not sentence:
        return []
    from rules import residency, sky

    hour = residency.time_words(int(ctx.scene.clock_minutes))
    refused = _refused_rest(ctx)
    moved = _moved(ctx)
    if refused is not None:
        why = _refusal_line(refused)
        return [Finding(
            "time-passed-unrun",
            f"the engine refused the rest ({why[:80]!r}); the page has the player take a "
            f"room or bed, or sleep: {sentence[:90]!r}",
            f"The player's character did not rest: {why} They take no room and no bed, "
            f"and do not sleep. Rewrite the sentence so it does not happen — keep "
            f"anything else it says.",
            weight=3, sentences=(sentence,))]
    if moved:
        # A clock that moved is never told it stood still (jack T212: "The hour has not
        # moved" printed beside the engine's own "10 minutes pass").
        span = sky.span_words(moved)
        return [Finding(
            "time-passed-unrun",
            f"the engine passed only {span} this turn (it is {hour}); the page has the "
            f"player sleep or let hours go by: {sentence[:90]!r}",
            f"Only {span} pass for the player's character this turn: it is {hour}, they "
            f"stay awake and where they are. Rewrite the sentence so they do not fall "
            f"asleep, wake or let hours pass — keep anything else it says.",
            weight=3, sentences=(sentence,))]
    return [Finding(
        "time-passed-unrun",
        f"the engine passed no time this turn (it is still {hour}); the page has the "
        f"player sleep or let hours go by: {sentence[:90]!r}",
        f"No time passes for the player's character this turn: it is still {hour}, they "
        f"stay awake and where they are. Rewrite the sentence so they do not fall asleep, "
        f"wake or let hours pass — keep anything else it says.",
        weight=3, sentences=(sentence,))]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    from gm import narration as narration_mod

    sentence = _slept(ctx, text)
    if not sentence or sentence not in text:
        return text, []
    refused = _refused_rest(ctx)
    # A refused rest closes on the engine's own refusal, the one sentence the page owed
    # and did not carry; anything else on the authored lines.
    # A clock that moved closes on nothing of ours: the engine's own time tell says how
    # long it was, and "the hour has not moved" beside it is false.
    line = (_refusal_line(refused) if refused is not None
            else "" if _moved(ctx)
            else POOL[narration_mod.least_recently_used(getattr(ctx.scene, "said", None),
                                                        "time-still", len(POOL))])
    text = f"{_cut(ctx, text, sentence)} {line}".strip()
    return text, [f"no time passed this turn: cut from {sentence[:60]!r}, "
                  f"wrote {line[:50]!r}"]


def authored_in(text: str) -> list[str]:
    """The backstop's own sentences on this page, for `GMAgent.last_added` (D4)."""
    return [line for line in POOL if line in str(text or "")]
