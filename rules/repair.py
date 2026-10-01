"""Mending a construct: the rule a "fix it" cites, and what it may not do.

The owner's report, 2026-10-01, playing Sam (a 1st-level wizard with Knowledge ranks): "I
attempt to use my knowledge of engineering and my deft hands to fix the spy in a way that
makes it recognize me as its owner." The Clockwork Spy lay at -1 hit points. The prose
described a full repair and a machine recognising its new master; the engine resolved
nothing at all ("did not heal the clockwork spy when I fixed it"), and the next turn
printed "Clockwork Spy has bled out where they fell" beside "it now waits for your
command". Both halves were the narrator's: no rule had been asked.

WHAT THE BOOK SAYS, read 2026-10-01 (content/rules/repairs.json quotes each):

  * Bestiary, Construct type: "Cannot heal damage on its own, but often can be repaired
    ... through the use of the Craft Construct feat. Constructs can also be healed through
    spells such as make whole." And "immediately destroyed when reduced to 0 hit points
    or less" — so the spy at -1 was not a patient but wreckage.
  * Ultimate Magic p.113, Repairing Constructs: the Craft Construct feat, 100 gp per Hit
    Die, a skill check "as if he were crafting the construct" at 5 less than the crafting
    DC, 1d6 hit points per Hit Die on a success, 1 day per 1,000 gp (minimum a day), and
    only "while the construct is inanimate or nonfunctioning". "A construct that has been
    completely destroyed cannot be repaired."
  * Core Rulebook, Craft: "You can repair an item by making checks against the same DC
    that it took to make the item in the first place. The cost of repairing an item is
    one-fifth of the item's price." That is the OBJECT rule. A construct is a creature,
    and the construct rule above is the more specific one, so the object rule is not used
    here. Knowledge (engineering) and Disable Device repair nothing in 1e — no skill
    besides the crafting check does — so the player's words choose the attempt and the
    rule chooses the skill.

So the order this module refuses in is the book's: not a construct (a living body is
healed, not mended — first aid is `rules/firstaid.py`); destroyed (never, by any skill);
undamaged; mid-fight or still working against you (a day's work on a thing at rest);
no Craft Construct (the feat is the rule's own gate — make whole, a 2nd-level spell, is
the other door and goes through `cast`); short of the coin. Only then is anything rolled.

OWNERSHIP IS NOT A REPAIR'S TO GIVE. Craft Construct: "A construct recognizes its creator
intuitively and obeys all commands issued to it by that individual" (d20pfsrd, the feat's
page) — its maker, not whoever mends it. Taking one from its master is control construct
(Ultimate Magic, sorcerer/wizard 7: "You wrest the control of a construct from its master.
For as long as you concentrate..."), which nobody here casts at 1st level. No door in the
engine grants a construct to the player, so the refusal says so whenever the words ask
for it, and `gm/checks/repair_claimed.py` cuts prose that claims it anyway. A real door —
building one with the feat, or the spell — is deferred, and said so in the report.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import states

_ROWS: dict[str, dict] | None = None
RULE = "repair-construct"


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


def is_construct(actor) -> bool:
    return bool(actor is not None and actor.has_state(states.CONSTRUCT))


def destroyed(actor) -> bool:
    """Dead, or at a hit point total the ladder says is dead. The second half is for a
    construct saved "dying" before 2026-10-01 — the owner's own spy, at -1 with no `dead`
    written — which the next round's tick destroys; a repair asked before that tick must
    not find it merely damaged."""
    return bool(actor is not None and (actor.has_state("state.down.dead")
                                       or actor.hp <= actor.death_floor()))


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


def cost_gp(subject, rule: dict) -> int:
    return int(rule["cost_gp_per_hd"]) * max(1, int(subject.hit_dice))


def minutes(subject, rule: dict) -> int:
    """1 day per 1,000 gp spent, minimum a day — whole days, rounded up."""
    gp = cost_gp(subject, rule)
    days = max(1, -(-gp // 1000))
    return max(int(rule["minimum_minutes"]), days * int(rule["minutes_per_1000_gp"]))


def dice(subject, rule: dict) -> str:
    count, sides = str(rule["dice_per_hd"]).lower().split("d")
    return f"{int(count) * max(1, int(subject.hit_dice))}d{int(sides)}"


OWNERSHIP_SAID = (
    "Mending a construct does not make it yours: it answers to its maker, and taking one "
    "from its master is the seventh-level spell control construct, held only while the "
    "caster concentrates.")


def refusal(scene, actor, subject, rule: dict) -> str:
    """Why this repair does not happen at all — the book's reason — or "".

    Each line is a fact the player could not have known from their own sheet, printed
    at resolution (the `_refuse` door), never a validation error the plan retries."""
    name = subject.name
    if not is_construct(subject):
        return (f"{name} is not a construct, and there is nothing to mend: a living body "
                f"is healed, not repaired.")
    if destroyed(subject):
        return (f"{name} was destroyed when it was reduced to 0 hit points, and a "
                f"construct that has been completely destroyed cannot be repaired "
                f"(Ultimate Magic, Repairing Constructs). What is left is parts.")
    if subject.hp >= subject.hp_max:
        return f"{name} is undamaged; there is nothing to repair."
    if getattr(scene, "in_encounter", False):
        return (f"A repair is a day's work on a construct at rest; it cannot be done "
                f"in the middle of a fight.")
    if states.attitude_of(subject) in ("hostile", "unfriendly") and subject.can_act():
        return (f"{name} is still working, and not for you: a construct is repaired "
                f"only while it is inanimate or nonfunctioning.")
    if not actor.has_state(str(rule["requires_tag"])):
        return (f"Repairing a construct takes {rule['requires_said']}, which "
                f"{actor.name} does not have (Ultimate Magic, Repairing Constructs). "
                f"Make whole, a second-level spell, mends one as well.")
    return ""
