"""A thing the engine left in the player's hands, handed away in the prose.

Measured live on the 2026-10-03 batch, the third turn played on the merged branch. "I pick
the crate back up, then tip the coins from the pouch into my coin purse": the engine
moved the crate into Kesst's goods and nothing out of them, and the page read "Beside
you, the smith, Korvu, reaches out with a hand calloused into leather and takes the crate
from you … The transaction is finished". The next turn would have resolved with the crate
on her back and a smith who remembers taking it — the two-truths failure every
`contradicts-the-engine` check exists to stop, on the one channel (things) that Lane A of
that batch gave a single holder.

Closed vocabulary, as the other truth checks: the things are the player's own goods (the
engine's record, never a noun read off the prose), and a sentence counts only when it
puts one of them in somebody else's hands — a third party taking it ("takes the crate
from you", "relieves you of the crate"), or the player handing it over ("you hand him the
crate"). A thing a resolved outcome of this turn moved out of the player's hands is
exempt: then the prose is right. Repair: one rewrite naming the holder; backstop: the
sentences go.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._page import cut, effects, field, page_sentences

ORDER = 22
KINDS = frozenset({"thing-kept-shown-given"})
DOORS = frozenset({"plan", "turn"})

_TAKER_VERBS = (r"takes|took|grabs|grabbed|accepts|accepted|receives|received|snatches|"
                r"snatched|lifts|lifted|pulls|pulled|relieves\s+you\s+of|relieved\s+you\s+of|"
                r"claims|claimed|hefts|hefted")
_GIVER_VERBS = r"hand|hands|handed|pass|passed|give|gave|surrender|surrendered"


def _moved_out(ctx, pc_ref: str) -> set[str]:
    """Heads of the things a resolved outcome of this turn took out of the player's hands."""
    from rules import holding

    out: set[str] = set()
    for o in ctx.outcomes:
        if field(o, "status") == "refused":
            continue
        for e in effects(o):
            if str(e.get("from") or "") == pc_ref or e.get("kind") in ("sold",):
                if e.get("item"):
                    out.add(holding.head_of(str(e["item"])))
    return out


def _gives_away(narration: str, head: str) -> bool:
    thing = rf"(?:the|your|that|this)\s+(?:[\w'-]+\s+){{0,2}}?{re.escape(head)}s?\b"
    if re.match(r"\s*you\b", narration, re.I) is None and re.search(
            rf"\b(?:{_TAKER_VERBS})\b[^.!?;]*?\b{thing}", narration, re.I):
        return True
    return bool(re.search(
        rf"\byou\s+(?:{_GIVER_VERBS})\b(?:\s+(?:over|it))?[^.!?;]*?\b{thing}", narration,
        re.I))


def find(ctx) -> list:
    from rules import holding

    pc = ctx.scene.pc() if hasattr(ctx.scene, "pc") else None
    if pc is None or not getattr(pc, "goods", None):
        return []
    gone = _moved_out(ctx, pc.ref)
    heads = {holding.head_of(name): name for name in pc.goods
             if holding.head_of(name) and holding.head_of(name) not in gone}
    flagged: list[str] = []
    held: list[str] = []
    for written, narration in page_sentences(ctx.text):
        for head, name in heads.items():
            if _gives_away(narration, head):
                flagged.append(written)
                held.append(name)
                break
    if not flagged:
        return []
    things = ", ".join(dict.fromkeys(held))
    return [Finding(
        "thing-kept-shown-given",
        f"{pc.name} still holds {things}, and the prose hands it away: {flagged[0][:90]!r}",
        f"Nothing changed hands: {pc.name} still carries {things}. Rewrite those "
        f"sentences so nobody takes it and the player does not give it — someone may "
        f"look at it, reach for it, or ask for it. Keep the rest.",
        weight=3, sentences=tuple(flagged))]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    gone = [s for f in findings for s in f.sentences if s in text]
    if not gone:
        return text, []
    return cut(text, gone), [f"a thing still held, given away in the prose: cut {len(gone)}"]
