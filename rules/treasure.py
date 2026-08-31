"""What the dead were carrying.

The bestiary has carried a `treasure` field all along — 550 creatures declare one of the
Core Rulebook's classes (`none`, `incidental`, `standard`, `double`, `triple`) — and
nothing read it. That was invisible while buying was free. It stopped being invisible the
moment a market started charging: a character begins with their class's starting wealth,
spends it, and had no way on earth to get any more. The economy ran one direction only.

This is the third field tonight found declared and unread, after `starting_wealth` on
every class and `price_gp` on every material. They are worth looking for as a class of
bug: data written by one pass and never wired by the next.

**Values are the Core Rulebook's own** — Table: Treasure Values per Encounter, the NPC
Gear column rounded to the gold piece — so a fight pays what the book says a fight of
that CR pays. Rolled around that centre rather than paid flat, because a purse that is
always exactly 260 gp is a table nobody has to think about.

Settled where XP is settled, and for the same reason: two different pieces of code end
fights, and both have to pay out the same way.
"""
from __future__ import annotations

from . import dice as dice_mod

# Core Rulebook, Treasure Values per Encounter, "slow"/"medium" NPC gear column in gp.
# Index is CR; CR 0 and fractional CRs share the lowest rung, which is what the book does
# with them in practice.
_BY_CR: dict[int, int] = {
    0: 100, 1: 260, 2: 550, 3: 800, 4: 1150, 5: 1550, 6: 2000, 7: 2600, 8: 3350,
    9: 4250, 10: 5450, 11: 7000, 12: 9000, 13: 12000, 14: 15000, 15: 19500,
    16: 25000, 17: 32000, 18: 41000, 19: 53000, 20: 67000,
}

# What the creature's own entry says it is carrying, as a multiple of the CR value.
CLASSES: dict[str, float] = {
    "none": 0.0,
    "incidental": 0.5,
    "standard": 1.0,
    "double": 2.0,
    "triple": 3.0,
}

# A single creature is not a whole encounter. The book's table prices the *encounter*, so
# paying it per corpse would make a pack of six wolves six encounters' worth of gold.
PER_CREATURE = 0.25


def _entry(actor) -> dict:
    """This actor's bestiary entry, looked up the way `xp.worth` looks one up.

    An instantiated Actor carries neither `cr` nor `treasure` — those stay in the
    template it was stamped from — so reading the attributes off the actor answered ''
    and 0 for every creature in the game. Same resolution order as the XP award: the
    template link first, which is exact however the GM renamed the thing, then the
    display name slugified for creatures spawned before that link existed.
    """
    from . import bestiary

    # `everything()`, not `lookup()`. Lookup answers with the trimmed playable stat
    # block — hp, ac, saves, attacks — and drops the import's own columns, so it reports
    # `treasure = None` and `cr = None` for every creature in the game including the
    # 550 that declare one.
    corpus = bestiary.everything()
    tried = [str(getattr(actor, "from_template", "") or "").strip().lower()]
    name = str(getattr(actor, "name", "") or "").strip().lower()
    for bare in (name, name.removeprefix("the ").strip(), name.removeprefix("a ").strip()):
        if bare:
            tried.append(bare.replace(" ", "-"))
    for key in tried:
        found = corpus.get(key) if key else None
        if isinstance(found, dict):
            return found
    return {}


def _cr_of(actor) -> int:
    entry = _entry(actor)
    for source in (actor, entry):
        for attr in ("cr_value", "cr"):
            raw = (source.get(attr) if isinstance(source, dict)
                   else getattr(source, attr, None))
            if raw in (None, ""):
                continue
            try:
                return max(0, min(20, int(float(str(raw).split("/")[0].strip() or 0))))
            except (TypeError, ValueError):
                continue
    return 0


def class_of(actor) -> str:
    """The treasure class this creature declares, or "" when it declares nothing.

    Empty is not the same as `none`: 6,355 of the bestiary's 7,136 entries simply never
    had the column filled in, and treating silence as "carries nothing" would quietly
    make almost every fight in the game worthless. Silence means the GM decides, which
    is the same answer `xp.worth` gives for a creature with no price.
    """
    raw = str(getattr(actor, "treasure", "") or "").strip().lower()
    if not raw:
        raw = str(_entry(actor).get("treasure", "") or "").strip().lower()
    for name in CLASSES:
        if raw.startswith(name):
            return name
    return ""


def worth(actor, rng=None) -> int:
    """What this one body is carrying, in gp. 0 when it says nothing or says none."""
    kind = class_of(actor)
    if not kind or kind == "none":
        return 0
    centre = _BY_CR.get(_cr_of(actor), 0) * CLASSES[kind] * PER_CREATURE
    if centre <= 0:
        return 0
    # Rolled around the centre: 50%–150%, so the same wolf is not the same purse twice.
    roll = (rng or dice_mod.Dice()).roll("2d6").total          # 2..12, centred on 7
    return max(1, int(round(centre * (0.5 + (roll - 2) / 10.0))))


def take_from_fallen(scene, pc, rng=None) -> tuple[int, list[str]]:
    """The gold a finished fight leaves on the ground, and who was carrying it.

    Shaped exactly like `xp.award_for_fallen`, and called beside it: only the fallen on
    a side the PC was not on, while the sides are still declared. A foe who fled or was
    spared keeps their purse, which leaves mercy costing something rather than paying.
    """
    if pc is None or not scene.sides:
        return 0, []
    total, names = 0, []
    for side, refs in scene.sides.items():
        if pc.ref in refs:
            continue
        for ref in refs:
            foe = scene.actors.get(ref)
            # The same reading as `xp.award_for_fallen`: half of "beaten" has full
            # hit points, and a petrified foe dropped its purse nowhere.
            if foe is None or (foe.hp > 0 and not foe.is_down):
                continue
            got = worth(foe, rng)
            if got:
                total += got
                names.append(foe.name)
    return total, names
