"""What a companion has told the player about their own life, and how far they have got.

The owner's ruling, 2026-10-01: "Their wants should appear naturally locked behind their
attitude toward you. but they shouldnt just blurt out personal feelings without some kind
of warm up. like telling there is something they wanted to get off their chest or if you
come across a thing that makes sense to remind them of a thing they can share."

The life `rules.lives` rolled for a person carries three things of their own — what they
want now (`wants`), what they hope for (`goal`), what they do for pleasure (`hobby`). The
narrator is never told them (rules/population.py: a 12B model told a secret leaks it ~83%
of the time). This module holds, per person, how much of each the PLAYER has been told:

    nothing   never mentioned
    hinted    they have said there is something on their mind, and not what
    told      they have said it; from here it is the player's knowledge too

and the one share they owe after a lead-in (`pending`), with a brush-off's postponement.

**Where it lives, and why not an effect.** On the population record, beside the life it
discloses and the quirk's own cadence (`quirk_turn`), not as an `ActiveEffect`. Law two
governs what changes a number, grants a state somebody queries, and wears off; a
disclosure does none of those — no rule reads it, it modifies nothing, and it never
expires (what you were told stays told). The same judgement `places.Place` records for a
place. The record is also where the life is, so the fact and what is known of it cannot
drift apart, and it rides the scene's snapshot and save with no new store.

**The gate is the attitude track** (`attitude.of`), read each time, never cached: below
`CONFIDES_A_HINT` nothing personal; at it, a hint at most; at `CONFIDES` or better — or
claimed and devoted (`bond.owned-by-you`) — the thing itself. A companion who cools keeps
what they already said said, and says nothing more.
"""
from __future__ import annotations

from . import attitude, states

TOPICS = ("wants", "goal", "hobby")
# The table each topic's rows come from in content/people/life.json.
TABLE = {"wants": "wants", "goal": "goals", "hobby": "hobbies"}
# How the Journal heads each one — the row's own words follow.
LABEL = {"wants": "Wants", "goal": "Hopes one day", "hobby": "For pleasure"}

NOTHING, HINTED, TOLD = "nothing", "hinted", "told"
# What the attitude allows.
NONE, HINT, SHARE = "none", "hint", "share"


def gate(actor) -> str:
    """How much of their own life this person will give the player now."""
    if actor is None:
        return NONE
    if actor.has_state(states.OWNED_BY_YOU):
        return SHARE
    at = attitude.step_of(attitude.of(actor))
    if at >= attitude.step_of(attitude.CONFIDES):
        return SHARE
    if at >= attitude.step_of(attitude.CONFIDES_A_HINT):
        return HINT
    return NONE


def life_text(rec: dict | None, topic: str) -> str:
    return " ".join(str(((rec or {}).get("life") or {}).get(topic) or "").split())


def row_of(topic: str, text: str) -> dict | None:
    """The life.json row a stored life text came from. The record keeps the text only
    (`lives.roll` stores what was rolled, not its id); the text is the row's own."""
    from . import lives

    text = " ".join(str(text or "").split())
    if not text or topic not in TABLE:
        return None
    return next((r for r in lives.tables().get(TABLE[topic]) or ()
                 if " ".join(str(r.get("text") or "").split()) == text), None)


def _track(rec: dict) -> dict:
    got = rec.get("confided")
    if not isinstance(got, dict):
        got = rec["confided"] = {}
    return got


def stage(rec: dict | None, topic: str) -> str:
    got = ((rec or {}).get("confided") or {}).get(topic) or {}
    return str(got.get("stage") or NOTHING)


def told(rec: dict | None) -> list[tuple[str, str]]:
    """(topic, their life's words) for everything they have told the player, in order."""
    return [(t, life_text(rec, t)) for t in TOPICS
            if stage(rec, t) == TOLD and life_text(rec, t)]


def untold(rec: dict | None) -> list[str]:
    """The topics with something to tell that has not been told."""
    return [t for t in TOPICS if life_text(rec, t) and stage(rec, t) != TOLD]


def pending(rec: dict | None) -> dict | None:
    got = (rec or {}).get("confide_pending")
    return got if isinstance(got, dict) and got.get("topic") else None


def hint(rec: dict, topic: str, beat: int, door: str, thing: str = "") -> None:
    """They have said there is something on their mind: the topic is hinted and the share
    is owed (`pending`), to come on a later beat."""
    track = _track(rec)
    if stage(rec, topic) != TOLD:
        track[topic] = {"stage": HINTED, "beat": int(beat), "door": door,
                        **({"thing": thing} if thing else {})}
    rec["confide_pending"] = {"topic": topic, "beat": int(beat), "door": door,
                              **({"thing": thing} if thing else {})}


def tell(rec: dict, topic: str, beat: int, door: str, thing: str = "") -> None:
    """They have said it. Never undone, and never announced again."""
    _track(rec)[topic] = {"stage": TOLD, "beat": int(beat), "door": door,
                          **({"thing": thing} if thing else {})}
    pend = pending(rec)
    if pend is not None and pend.get("topic") == topic:
        rec.pop("confide_pending", None)


def postpone(rec: dict, beat: int) -> None:
    """The player brushed it off ("not now", "later"): the share waits."""
    pend = pending(rec)
    if pend is not None:
        pend["postponed"] = int(beat)


def since(rec: dict, beat: int) -> None:
    """When this person was first seen travelling with the player — the clock their first
    lead-in waits on, so a companion of two beats does not open their heart."""
    rec.setdefault("travelling_since", int(beat))
