"""Experience: earned by doing, spent by sleeping on it.

"leveling up is something i can just choose to do but it should be gated by Experience
gained from doing things or killing things" — so levels stop being a button and become a
ledger. The thresholds are 1e's medium track, verbatim; a defeated creature is worth the
XP its bestiary row states, or its CR row here when the bestiary is silent.

The award happens when a fight *ends*, not when a body drops: mid-fight the sides are
still declared and the outcome is still open, and 1e's own framing is that the encounter
is the unit of reward. Sleeping is when a level lands — `rest` asks this module whether
the character has earned one and runs the level-up before they wake.
"""
from __future__ import annotations

# Total XP required to *be* each level. Pathfinder 1e, medium advancement.
MEDIUM = {
    1: 0, 2: 2000, 3: 5000, 4: 9000, 5: 15000, 6: 23000, 7: 35000, 8: 51000,
    9: 75000, 10: 105000, 11: 155000, 12: 220000, 13: 315000, 14: 445000,
    15: 635000, 16: 890000, 17: 1300000, 18: 1800000, 19: 2550000, 20: 3600000,
}

# XP award per CR, the Core table. Fractional CRs arrive as floats from the bestiary.
CR_AWARD = {
    0.125: 50, 0.167: 65, 0.25: 100, 0.333: 135, 0.5: 200,
    1: 400, 2: 600, 3: 800, 4: 1200, 5: 1600, 6: 2400, 7: 3200, 8: 4800,
    9: 6400, 10: 9600, 11: 12800, 12: 19200, 13: 25600, 14: 38400, 15: 51200,
    16: 76800, 17: 102400, 18: 153600, 19: 204800, 20: 307200,
}


def total_for(level: int) -> int:
    """XP required to be this level. Past the table's end, nobody is counting."""
    return MEDIUM.get(max(1, min(20, int(level))), 0)


def worth(actor) -> int:
    """What defeating this creature awards.

    The bestiary's own xp column first; its CR against the Core table second; zero for
    anything unrated, which is honest — a creature the book does not price is a story
    beat, and story beats are the `xp` op's business, not this table's.
    """
    stated = int(getattr(actor, "xp_value", 0) or 0)
    if stated:
        return stated

    # Healed on read rather than migrated, the same way `Campaign.biome` heals a save
    # written before biomes existed. Every creature already in a scene when `xp_value`
    # was added carries a zero, and the fight that killed it paid nothing — measured in
    # real play: a bear died and awarded 0 XP. Looking the creature up by the name it is
    # still carrying recovers the number without touching the save.
    from . import bestiary

    # The template first, which is exact: a creature keeps the stat block it was made
    # from however the GM renames it.
    tried = [str(getattr(actor, "from_template", "") or "").strip().lower()]
    # Then the display name, slugified, for creatures spawned before the link existed.
    # Best effort and nothing more — "a bear" is not a creature in the corpus, and
    # guessing which bear would be inventing a number.
    name = str(getattr(actor, "name", "") or "").strip().lower()
    for bare in (name, name.removeprefix("the ").strip(), name.removeprefix("a ").strip()):
        if bare:
            tried.append(bare.replace(" ", "-"))
    for key in tried:
        if not key:
            continue
        found = bestiary.lookup(key)
        if found and found.get("xp"):
            return int(found["xp"])
    return 0


def award_for_fallen(scene, pc) -> tuple[int, list[str]]:
    """The XP a finished fight owes, and who it was owed for.

    Called while the sides are still declared — the enemy sides are everyone not
    standing beside the PC — and only for the fallen: a fight that ends with the enemy
    fled or spared awards nothing here, which leaves mercy as the GM's `xp` op to
    reward rather than a tax.
    """
    if pc is None or not scene.sides:
        return 0, []
    mine = next((refs for refs in scene.sides.values() if pc.ref in refs), [])
    total, names = 0, []
    for side, refs in scene.sides.items():
        if pc.ref in refs:
            continue
        for ref in refs:
            foe = scene.actors.get(ref)
            # Hit points alone missed the half of "beaten" that has none. Measured:
            # petrifying the last enemy ends the fight — `sides_standing` drops to one
            # and the views print "The fight is over." — with 135 XP unpaid and nothing
            # said about it, because a statue is at full health. Widened rather than
            # replaced: `is_down` is `hp < 0 or state.down`, so asking it alone would
            # stop paying for a foe beaten to exactly 0.
            if foe is None or (foe.hp > 0 and not foe.is_down):
                continue
            got = worth(foe)
            if got:
                total += got
                names.append(foe.name)
    return total, names


def ready_to_level(actor) -> bool:
    """Whether the XP ledger covers the next level."""
    level = int(getattr(actor, "level", 1) or 1)
    if level >= 20:
        return False
    return int(getattr(actor, "xp", 0) or 0) >= total_for(level + 1)
