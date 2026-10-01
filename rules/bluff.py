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

import json
import re
from pathlib import Path

from .dice import Modifier

# **And what a lie does to how they feel** (owner ruling, 2026-10-01; the house rule is
# written out in content/rules/claims.json's note). A believed claim about who you are
# moves the listener on the attitude track, up or down by how they feel about what you
# claimed: a king to a man who hates the high-born cools him. A caught lie costs a little
# regard and leaves them wary — Ultimate Intrigue's rule for a lie found out (p.182): a
# later lie to them "takes a similar penalty as if she had failed to deceive the target
# (either a -10 penalty ...)". The size of the swing is Diplomacy's (`attitude.steps_for`).
WARY_PENALTY = -10
_CLAIMS: list | None = None


def _kinds() -> list:
    """content/rules/claims.json, read once. Through `settings.BASE_DIR`, never
    `__file__`, which points inside the bundle when frozen."""
    global _CLAIMS
    if _CLAIMS is None:
        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "rules" / "claims.json"
        _CLAIMS = json.loads(path.read_text(encoding="utf-8"))["kinds"]
    return _CLAIMS


def claim_kind(claim: str) -> str:
    """Which kind of standing a claim lays claim to — "rank", "holy", "dread", "renown" —
    or "" for a cover story that claims none. The first kind in the table whose words the
    claim uses wins, so "the chosen heir" is rank before holy."""
    words = set()
    for w in re.findall(r"[a-z][a-z'’-]+", str(claim or "").lower()):
        words.add(w)
        words.update(p for p in w.split("-") if p)
        if w.endswith("s"):
            words.add(w[:-1])
    for kind in _kinds():
        if words & set(kind.get("words") or ()):
            return str(kind["id"])
    return ""


def _disposition(scene, listener, axis: str) -> int:
    """The listener's score on `axis`, 0-100, from the life rolled for them
    (`rules/lives.py`); 50, the silent middle, for anybody with no life recorded — a
    bestiary thug has no temperament to read, and the middle is what nobody-in-particular
    feels."""
    from . import lives, population

    rec = population.of_ref(scene, getattr(listener, "ref", "")) if scene is not None else None
    life = (rec or {}).get("life") or {}
    if axis == "rank":
        seed = (f"{rec.get('home')}|{rec['id']}" if rec
                else f"actor|{getattr(listener, 'ref', '')}")
        return lives.rank_score(seed, lives.work_class_of(str(life.get("work") or "")))
    return int((life.get("axes") or {}).get(axis, 50))


def reaction(kind: str, listener, scene) -> tuple[int, str]:
    """(swing, why) for a believed claim of `kind`: +1 warms, -1 cools, 0 unmoved, and the
    reason in words for the tell. (0, "") for a kind the table does not hold."""
    row = next((k for k in _kinds() if k["id"] == kind), None)
    if row is None:
        return 0, ""
    if not row.get("axis"):
        pole = row.get("all") or {}
    else:
        score = _disposition(scene, listener, str(row["axis"]))
        pole = row.get("low" if score < 40 else "high" if score > 60 else "middle") or {}
    return int(pole.get("swing", 0)), str(pole.get("why", ""))


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
