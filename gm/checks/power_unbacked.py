"""No power on the page that the turn did not resolve.

The owner, 2026-10-05: *"getting rid of the regex has brought back the ability to use
psychic powers and alter memories through narration"* — and then, *"whatever you do must
catch anything that is not within the players power to do"*. Reproduced on a copy of the
owner's save: "I erase the apprentice's memory of me" reached the prose with nothing
resolved but `narrate_only`, and the page wrote "the flicker of recognition of your
presence … simply dissolves". The forward gate (gm/means.py) now refuses that deed before
any model is asked; this is the backward half, for the page that writes a power working
whatever the turn resolved — the narrator inflating a Bluff into a memory wipe, or a
mixed turn's refused half written as done.

**Detection** is a model's, held in code (docs/structured-turn.md): one closed question
(`means.read_unbacked`) — which sentence, if any, has the player's character doing what
no ordinary person can that the rules did not resolve this turn — shown the turn's
resolved tells and the character's own gifts (race traits, feats, abilities: the owner's
asura flies on her own wings and no tell says so). The sentence must be about the player
(`deed_reader.about_the_player`). Asked of the player's own beats only.

**Repair** is the house shape: one rewrite of that sentence naming the fact; then the
backstop — that sentence cut (not everything after it: the rest of the beat is usually the
world's answer, and true) and an authored line put in its place, least-recently-used per
campaign and marked ours (`authored_in`, D4).

Measured on the means corpus and live turns in docs/means-gate.md.
"""
from __future__ import annotations

from gm.narration import Finding

from ._page import cut

ORDER = 61
KINDS = frozenset({"power-unbacked"})
DOORS = frozenset({"plan", "turn"})

POOL = (
    "Whatever you reach for does not answer; the moment stays exactly as it was.",
    "Nothing bends to it. The world goes on as plainly as before.",
    "You reach, and there is nothing there to reach with.",
)

# The ops whose resolution is a power at work, for the reader's RULES list.
_POWER_OPS = frozenset({"cast", "use_ability", "use_item", "condition", "compel",
                        "check", "say", "attack", "maneuver"})


def _field(o, key):
    return o.get(key) if isinstance(o, dict) else getattr(o, key, None)


def _rules(ctx) -> list[str]:
    out = []
    for o in ctx.outcomes or ():
        if _field(o, "status") == "refused":
            continue
        tell = " ".join(str(_field(o, "tell") or "").split())
        if tell and _field(o, "op") in _POWER_OPS:
            out.append(tell[:240])
    return out[:8]


def _found(ctx, text: str) -> str:
    from gm import deed_reader, means

    route = dict(getattr(ctx, "reader", None) or {})
    if not deed_reader.ENABLED or not route.get("model"):
        return ""
    scene = ctx.scene
    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    if pc is None:
        return ""
    sentence, error = means.read_unbacked(
        text, _rules(ctx), means.gifts_of(pc), **route,
        pc_name=str(getattr(pc, "name", "") or ""))
    if error:
        raise RuntimeError(f"the page could not be read for unbacked powers: {error}")
    return sentence


def find(ctx) -> list:
    sentence = _found(ctx, ctx.text)
    if not sentence:
        return []
    pc = ctx.scene.pc()
    who = str(getattr(pc, "name", "") or "the player's character")
    return [Finding(
        "power-unbacked",
        f"the page has {who} doing what no ordinary person can, and the turn resolved no "
        f"power that does it: {sentence[:90]!r}",
        f"{who} has no power that does this and the rules resolved none this turn: it "
        f"did not happen. Rewrite the sentence so the attempt simply does not work — no "
        f"mind is read or changed, nothing appears, vanishes or transforms — and keep "
        f"anything else it says about the world.",
        weight=4, sentences=(sentence,))]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    from gm import narration as narration_mod

    sentence = _found(ctx, text)
    if not sentence or sentence not in text:
        return text, []
    line = POOL[narration_mod.least_recently_used(getattr(ctx.scene, "said", None),
                                                  "power-unbacked", len(POOL))]
    at = text.find(sentence)
    before, after = text[:at], text[at + len(sentence):]
    text = cut(f"{before}{line}{after}", ())
    return text, [f"a power no tell backs: cut {sentence[:60]!r}, wrote {line[:50]!r}"]


def authored_in(text: str) -> list[str]:
    """The backstop's own sentences on this page, for `GMAgent.last_added` (D4)."""
    return [line for line in POOL if line in str(text or "")]
