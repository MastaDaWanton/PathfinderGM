"""A lie told to somebody: Bluff against their Sense Motive, at the book's believability.

Owner ruling B1, 2026-09-30 (docs/fix-plan-2026-09-30.md): a spoken lie is opposed by the
listener's Sense Motive, with 1e's believability modifiers, instead of the flat DC 30
"heroic" band `judgement.inject_false_claim` used to write. With Sam's Bluff +6 that band
failed by construction — 10, 18 and 7 against 30, three times in one session — and it
was never the rule.

**The rule** (Core Rulebook p.90; Archives of Nethys, Skills > Bluff, aonprd.com/
Skills.aspx?ItemName=Bluff): Bluff "is an opposed skill check against your opponent's
Sense Motive skill", and the check is modified by the table *Bluff Modifiers*:

    the target wants to believe you   +5
    the lie is believable             +0
    the lie is unlikely               -5
    the lie is far-fetched            -10
    the lie is impossible             -20
    the target is drunk or impaired   +5
    you possess convincing proof      up to +10

The column is a BLUFF modifier in 1e — on the liar's roll, not the listener's. That is a
change from 3.5, whose table modified the Sense Motive check instead, and it is the 1e
table that is used here.

**What is built and what is not.** Only the believability rows: which of them a claim is
gets decided in code from the claim's own words (`judgement.lie_of`), never by a model —
the category travels on the check's `opposed_by` as `lie`, the engine reads it here, and
the number it becomes is this table's. "Wants to believe you", "drunk or impaired" and
"convincing proof" have no reader yet: nothing on a sheet says a listener is drunk, and a
prop a player shows is the very thing `false_possession` holds false. The book's try-again
rule ("further attempts to deceive them are at a -10 penalty") is not kept either; the
ledger in the report names both.
"""
from __future__ import annotations

from .dice import Modifier

# The believability rows of the table, by the word the check carries.
LIES: dict[str, int] = {
    "believable": 0,
    "unlikely": -5,
    "far_fetched": -10,
    "impossible": -20,
}


def said(lie: str) -> str:
    """The row in words, for the roll's breakdown: "the lie is far-fetched"."""
    return f"the lie is {str(lie).replace('_', '-')}"


def modifier(lie) -> Modifier | None:
    """The term the lie adds to the liar's Bluff, or None for no lie or a believable one.

    A believable lie adds nothing, and a zero term on the roll would be noise; an unknown
    word is ignored rather than guessed at, because the only writer is code."""
    value = LIES.get(str(lie or "").strip().lower())
    if not value:
        return None
    return Modifier(value, said(str(lie).strip().lower()))
