"""The player under at the end of the turn stays under on the page.

The survival lane's live run, 2026-10-05: the engine's tell said Sammy "cannot stay awake
any longer and falls asleep where they stand"; the prose already had them waking at
twilight — "that was a long nap". The narrator ran past the state the tells leave the
player in, and the next turn opened on a character the page said was awake and the engine
held asleep.

**Detection** is a model's, held in code (docs/structured-turn.md): when the engine holds
the player down at the end of the turn — asleep (`survival.asleep`) or out cold
(`state.down.unconscious`), never dead — one closed question asks which sentence first has
them up again after going under (`deed_reader.read_under`); the sentence must be about the
player. Read only when the player IS down, so a false alarm can only ever cost a beat in
which the player was asleep anyway.

**Repair** is the house shape: one rewrite of that sentence with the engine's fact named;
then the backstop — cut from it (everything after a waking that did not happen is set in a
world where it did, `hold_the_door`'s shape) and close on an authored line for the state,
least-recently-used per campaign and marked ours (`authored_in`, D4).

Not measured on a bench: one live case, the survival lane's. The reader that answers it is
the deed reader's model and shape, measured in docs/narrator-guards.md.
"""
from __future__ import annotations

from gm.narration import Finding

from ._page import cut_from

ORDER = 62
KINDS = frozenset({"player-up-while-under"})
DOORS = frozenset({"turn"})

POOL: dict[str, tuple[str, ...]] = {
    "asleep": (
        "You sleep on where you fell, dead to the world.",
        "Sleep has you now, and it does not let go of you.",
        "You do not stir; your body has taken the sleep it was owed.",
    ),
    "out": (
        "You lie senseless, and the world goes on without you.",
        "You do not come round; there is only the dark.",
        "You stay down, insensible, while the moment passes over you.",
    ),
}


def _state(ctx) -> str:
    """"asleep", "out", or "" when the player is up (or dead, which other checks own)."""
    from rules import survival

    scene = ctx.scene
    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    if pc is None or pc.has_state("state.down.dead"):
        return ""
    if survival.asleep(pc) is not None:
        return "asleep"
    if pc.has_state("state.down.unconscious"):
        return "out"
    return ""


def _woken(ctx, text: str) -> str:
    from gm import deed_reader

    state = _state(ctx)
    route = dict(getattr(ctx, "reader", None) or {})
    if not state or not deed_reader.ENABLED or not route.get("model"):
        return ""
    pc = ctx.scene.pc()
    sentence, error = deed_reader.read_under(
        text, "ASLEEP" if state == "asleep" else "UNCONSCIOUS", **route,
        pc_name=str(getattr(pc, "name", "") or ""))
    if error:
        raise RuntimeError(f"the page could not be read for the sleeper: {error}")
    return sentence


def find(ctx) -> list:
    sentence = _woken(ctx, ctx.text)
    if not sentence:
        return []
    state = "asleep" if _state(ctx) == "asleep" else "unconscious"
    return [Finding(
        "player-up-while-under",
        f"the engine holds the player {state} at the end of the turn; the page has them "
        f"up: {sentence[:90]!r}",
        f"The player's character is {state} at the end of this turn and stays {state}. "
        f"Rewrite the sentence so they do not wake, rise, speak or act — keep anything "
        f"else it says about the world around them.",
        weight=3, sentences=(sentence,))]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    from gm import narration as narration_mod

    sentence = _woken(ctx, text)
    if not sentence or sentence not in text:
        return text, []
    cell = _state(ctx) or "asleep"
    pool = POOL[cell]
    line = pool[narration_mod.least_recently_used(getattr(ctx.scene, "said", None),
                                                  f"under:{cell}", len(pool))]
    text = f"{cut_from(text, sentence)} {line}".strip()
    return text, [f"the player is {cell} at the end of the turn: cut from "
                  f"{sentence[:60]!r}, wrote {line[:50]!r}"]


def authored_in(text: str) -> list[str]:
    """The backstop's own sentences on this page, for `GMAgent.last_added` (D4)."""
    return [line for pool in POOL.values() for line in pool if line in str(text or "")]
