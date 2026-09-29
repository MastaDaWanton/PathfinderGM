"""THE ONE THE PLAYER CAME LOOKING FOR: the finder's answer, after the move, as a fact.

Measured on the 2026-09-28 playtest (item 9): "I head to the market and look for the girl
that the watchman described" — the party reached the market, the girl was not there
(nothing had recorded her), and the beat gave itself to the quest-giver instead. With
the girl now recorded where the watchman placed her (`play/aftermath/mentioned_elsewhere`),
the finder does find her; but `judgement.embody_sought` runs before the plan, while the
party is still at the gate, so after the `travel` she is HERE with no body and nothing in
the brief says so. This section says it, from the engine's own finder, after the
resolution — so the beat answers the search the player made.

Only the HERE answer is this section's. ELSEWHERE and NOWHERE are already the brief's
"WHO THE PLAYER LOOKED FOR AND IS NOT HERE" line (`judgement.absent_answer`).
"""
from __future__ import annotations

import re

ORDER = 30
SLOT = "people"
SCAFFOLD = (
    "THE ONE THE PLAYER CAME LOOKING FOR (fact):",
    "is here",
    "This is who the player finds; the beat answers the search.",
    "Speak of them as",
)

_LOOKING = re.compile(r"\b(?:look(?:s|ing)?|search(?:es|ing)?|ask(?:s|ing)?\s+around|"
                      r"go(?:es|ing)?\s+around)\s+for\b|\bseek|\bfind\b|\bhead(?:s)?\s+for\b",
                      re.I)


def sought_phrase(reading, player_text: str) -> str:
    """The person the player's words go looking for: the reading's `seek` or `call_on`
    target when there is a reading, else the regex's reading of the sentence."""
    from gm import interpret as _interpret
    from gm import judgement

    if reading and not reading.get("error"):
        return _interpret.target_of(reading, acts=("seek", "call_on"))
    # No reading: only a sentence that goes LOOKING for somebody. The regex reader also
    # answers for "I talk to the smith", and a person addressed is not a person sought.
    if not player_text or not _LOOKING.search(str(player_text)):
        return ""
    return judgement.person_sought(player_text)


def answer(world, scene, reading, player_text: str) -> dict:
    """`scope.look_for` over the sought phrase, as the scene stands now, or {}."""
    from rules import scope as scope_mod

    phrase = sought_phrase(reading, player_text)
    if not phrase or scene is None:
        return {}
    found = scope_mod.look_for(world, phrase, scene, getattr(scene, "location_id", None))
    return dict(found, sought=phrase)


def section(ctx) -> tuple[str, dict]:
    from rules import names as names_mod
    from rules import person_words
    from rules import scope as scope_mod

    found = answer(ctx.world, ctx.scene, ctx.reading, ctx.player_text)
    if found.get("scope") != scope_mod.HERE:
        return "", {}
    scene = ctx.scene
    phrase = found["sought"]
    ref = found.get("ref") or ""
    if ref and ref in (scene.actors or {}):
        actor = scene.actors[ref]
        text = (f"\nTHE ONE THE PLAYER CAME LOOKING FOR (fact): {phrase} is here — "
                f"{actor.name} ({ref}). This is who the player finds; the beat answers the "
                f"search.")
        return text, {"sought": phrase, "ref": ref, "record": found.get("record", "")}
    rec = (getattr(scene, "population", {}) or {}).get(found.get("record") or "")
    if rec is None:
        return "", {}
    life = rec.get("life") or {}
    face = names_mod.appearance_for(ctx.world, getattr(scene, "location_id", None),
                                    ref=rec["id"], own=life.get("face") or None) \
        if ctx.world is not None else str(life.get("face") or "")
    said = person_words.from_words(rec.get("phrase", ""))
    speak = f" Speak of them as {said['pronouns']}." if said.get("pronouns") else ""
    looks = f" — {face.rstrip('.')}" if face else ""
    text = (f"\nTHE ONE THE PLAYER CAME LOOKING FOR (fact): {rec['phrase']} is here{looks}. "
            f"This is who the player finds; the beat answers the search.{speak}")
    return text, {"sought": phrase, "record": rec["id"], "phrase": rec["phrase"],
                  "pronouns": said.get("pronouns", "")}
