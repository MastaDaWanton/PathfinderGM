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

**Detection** is a model's, held in code: when the engine moved the clock less than an
hour this turn and the player is not under (`sleep_kept` owns that), one closed question
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


def _still(ctx) -> bool:
    """The clock moved less than STILL_MINUTES this turn and the player is up."""
    from rules import survival

    was = getattr(ctx, "was_clock", None)
    scene = ctx.scene
    now = getattr(scene, "clock_minutes", None)
    if was is None or now is None:
        return False
    try:
        if int(now) - int(was) >= STILL_MINUTES:
            return False
    except (TypeError, ValueError):
        return False
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None or pc.is_down or survival.asleep(pc) is not None:
        return False
    return True


def _slept(ctx, text: str) -> str:
    from gm import deed_reader

    route = dict(getattr(ctx, "reader", None) or {})
    if not _still(ctx) or not deed_reader.ENABLED or not route.get("model"):
        return ""
    pc = ctx.scene.pc()
    sentence, error = deed_reader.read_slept(
        text, **route, pc_name=str(getattr(pc, "name", "") or ""))
    if error:
        raise RuntimeError(f"the page could not be read for time passing: {error}")
    return sentence


def find(ctx) -> list:
    sentence = _slept(ctx, ctx.text)
    if not sentence:
        return []
    from rules import residency

    hour = residency.time_words(int(ctx.scene.clock_minutes))
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
    line = POOL[narration_mod.least_recently_used(getattr(ctx.scene, "said", None),
                                                  "time-still", len(POOL))]
    text = f"{cut_from(text, sentence)} {line}".strip()
    return text, [f"no time passed this turn: cut from {sentence[:60]!r}, "
                  f"wrote {line[:50]!r}"]


def authored_in(text: str) -> list[str]:
    """The backstop's own sentences on this page, for `GMAgent.last_added` (D4)."""
    return [line for line in POOL if line in str(text or "")]
