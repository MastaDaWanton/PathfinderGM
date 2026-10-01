"""Mending a construct, and making it yours: the owner's house rule and the book it departs from.

The owner's report, 2026-10-01, playing Sam (a 1st-level wizard with Knowledge ranks): "I
attempt to use my knowledge of engineering and my deft hands to fix the spy in a way that
makes it recognize me as its owner." The Clockwork Spy lay at -1 hit points. The prose
described a full repair and a machine recognising its new master; the engine resolved
nothing at all ("did not heal the clockwork spy when I fixed it"), and the next turn
printed "Clockwork Spy has bled out where they fell" beside "it now waits for your
command". Both halves were the narrator's: no rule had been asked.

WHAT THE BOOK SAYS, read 2026-10-01 (content/rules/repairs.json quotes each), and what the
first fix built: a construct is "immediately destroyed when reduced to 0 hit points or
less" (Bestiary); a damaged one is repaired with the Craft Construct feat, 100 gp per Hit
Die, a crafting check at DC less 5, a day, 1d6 per Hit Die (Ultimate Magic p.113); and it
obeys its maker, never its mender — taking one is control construct, a 7th-level spell.
By the book the owner's spy was wreckage.

THE OWNER RULED OTHERWISE, the same day — a HOUSE RULE, verbatim: "Broken, then fixable and
claimable — House rule: a construct at 0 to -10 is broken, not destroyed (destroyed only
past that). Anyone with the skill can mend it with a Craft or Knowledge (engineering)
check, which heals it. A second, harder check rewrites its loyalty so it becomes yours: it
follows you, obeys, and you can name it." So:

  * broken, not destroyed — `Actor.death_floor` reads `broken_floor` (-10) off the row and
    `Actor.settle_broken` writes the `broken` condition between it and 0;
  * the repair — no feat, no coin; the better of Craft and Knowledge (engineering); DC the
    crafting DC less 5 (the book's arithmetic, kept); ten minutes; 1d6 per Hit Die through
    the heal applicator, stamped `rule:repair-construct`; a broken machine mended above 0
    rises, and nobody's yet (indifferent);
  * the claim — the better of Knowledge (engineering) and Disable Device, at the repair
    DC + 10, on a working construct that is not fighting you; a success grants
    `bond.owned-by-you`, `bond.travels-with-you` and `devoted`, and a failure by 5 or more
    turns it hostile.

Every number above is a row field marked HOUSE with the departure stated; this module only
reads them. Ultimate Magic stays cited in the row as the thing departed from.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import states

_ROWS: dict[str, dict] | None = None
RULE = "repair-construct"
CLAIM = "claim-construct"


def rows() -> dict[str, dict]:
    global _ROWS
    if _ROWS is None:
        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "rules" / "repairs.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        _ROWS = {k: v for k, v in data.items() if not str(k).startswith("_")}
    return _ROWS


def row(rule: str = RULE) -> dict:
    return rows()[rule]


def broken_floor() -> int:
    """The total at which a construct is destroyed: one past the row's lowest broken total.
    "0 to -10 is broken ... destroyed only past that", so -10 is still broken and -11 is
    not — `Actor.death_floor`'s meaning is "dead at or below", hence the -1."""
    return int(row(RULE)["broken_floor"]) - 1


def is_construct(actor) -> bool:
    return bool(actor is not None and actor.has_state(states.CONSTRUCT))


def destroyed(actor) -> bool:
    """Dead, or at a hit point total the ladder says is dead."""
    return bool(actor is not None and (actor.has_state("state.down.dead")
                                       or actor.hp <= actor.death_floor()))


def broken(actor) -> bool:
    """Broken by the house rule — the condition, or a save's spy at 0 to -10 that has not
    been settled onto it yet."""
    return bool(actor is not None and not destroyed(actor) and is_construct(actor)
                and (actor.has_state("state.down.broken") or actor.hp <= 0))


def owned(actor) -> bool:
    return bool(actor is not None and actor.has_state(states.OWNED_BY_YOU))


def crafting_dc(subject, rule: dict) -> tuple[int, bool]:
    """The DC to craft this construct, and whether it is the row's HOUSE default.

    A stat block that carries its construction line (`construction.dc`) is the book; the
    shipped bestiary carries none yet, so the row's DC 20 stands in — which for the
    Clockwork Spy is its own printed DC (Bestiary 3)."""
    doc = subject._creature_doc() if hasattr(subject, "_creature_doc") else None
    printed = ((doc or {}).get("construction") or {}).get("dc")
    try:
        if printed:
            return int(printed), False
    except (TypeError, ValueError):
        pass
    return int(rule["crafting_dc"]), True


def repair_dc(subject) -> int:
    rule = row(RULE)
    return crafting_dc(subject, rule)[0] - int(rule["dc_less"])


def claim_dc(subject) -> int:
    return repair_dc(subject) + int(row(CLAIM)["dc_over_repair"])


def dice(subject, rule: dict) -> str:
    count, sides = str(rule["dice_per_hd"]).lower().split("d")
    return f"{int(count) * max(1, int(subject.hit_dice))}d{int(sides)}"


def best_skill(actor, skills) -> tuple[str, list] | None:
    """(skill, its modifiers) — the best of `skills` this character can attempt at all,
    or None. A trained-only skill with no ranks is not attempted (`skill_modifiers`
    refuses it), which is 1e's own rule and why Disable Device and Knowledge are asked
    rather than assumed."""
    from .sheet import IllegalSheet

    best = None
    for skill in skills:
        try:
            mods = actor.skill_modifiers(skill)
        except (IllegalSheet, KeyError):
            continue
        total = sum(m.value for m in mods)
        if best is None or total > best[0]:
            best = (total, skill, mods)
    return (best[1], best[2]) if best else None


def _working_against_you(subject) -> bool:
    return (states.attitude_of(subject) in ("hostile",) and subject.can_act()
            and not subject.is_down)


def repair_refusal(scene, actor, subject) -> str:
    """Why this repair does not happen at all, or "". Printed at resolution — each line
    is a fact the player could not have seen from their own sheet."""
    name = subject.name
    if not is_construct(subject):
        return (f"{name} is not a construct, and there is nothing to mend: a living body "
                f"is healed, not repaired.")
    if destroyed(subject):
        return (f"{name} is destroyed — past the point a construct can be brought back "
                f"from — and what is left is parts.")
    if subject.hp >= subject.hp_max:
        return f"{name} is undamaged; there is nothing to repair."
    if getattr(scene, "in_encounter", False):
        return (f"A repair is ten minutes' work at the least; it cannot be done in the "
                f"middle of a fight.")
    if _working_against_you(subject):
        return (f"{name} is still working, and not for you: it has to be stopped before "
                f"it can be mended.")
    if best_skill(actor, row(RULE)["skills"]) is None:
        return (f"{actor.name} has neither Craft nor Knowledge (engineering) to mend it "
                f"with.")
    return ""


def claim_refusal(scene, actor, subject) -> str:
    """Why the loyalty cannot be rewritten now, or ""."""
    name = subject.name
    if not is_construct(subject):
        return (f"{name} is not a construct; a mind is won by talking, not rewritten "
                f"with tools.")
    if destroyed(subject):
        return f"{name} is destroyed; there is nothing left to answer to anybody."
    if broken(subject) or subject.is_down:
        return (f"{name} is broken and inert: it has to be mended and working before its "
                f"loyalty can be rewritten.")
    if getattr(scene, "in_encounter", False) or _working_against_you(subject):
        return (f"{name} is fighting you; its loyalty cannot be rewritten while it is "
                f"trying to stop you.")
    if best_skill(actor, row(CLAIM)["skills"]) is None:
        return (f"Rewriting a construct's loyalty takes training in Knowledge "
                f"(engineering) or Disable Device, and {actor.name} has neither.")
    return ""
