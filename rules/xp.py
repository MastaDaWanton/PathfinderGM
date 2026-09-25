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
                names.append(_definite(foe.name))
    # And the crowds, whose members die one at a time. A unit pays for the members who
    # FELL, whether or not the rest are still standing and whether or not they ran: eight
    # raiders dead and four fled is not mercy, and paying nothing for it is the answer the
    # player would notice first (item 33, 2026-09-19). A unit wiped out is caught above by
    # its hit points, so it is counted here only for what the loop did not already pay.
    from . import troops as troops_mod

    for ref, foe in (scene.actors or {}).items():
        unit = getattr(foe, "troop", None)
        if unit is None or ref in mine or foe.is_pc:
            continue
        if not (foe.hp > 0 and not foe.is_down) and ref in {
                r for s, refs in scene.sides.items() if pc.ref not in refs for r in refs}:
            continue                      # already paid for as a fallen actor
        owed = troops_mod.xp_owed(unit)
        if owed:
            total += owed
            names.append(f"{unit.fallen} of {_definite(foe.name)}")
    # A unit that ROUTED is no longer in the scene to be asked — it left the board with its
    # survivors — so the engine wrote the debt down where the scene remembers things
    # (`Engine._rout`), and this is where it is settled.
    for gone in list(getattr(scene, "routed_xp", None) or []):
        if not isinstance(gone, dict):
            continue
        owed = max(0, int(gone.get("xp", 0) or 0))
        if owed:
            total += owed
            names.append(f"{int(gone.get('fallen', 0) or 0)} of "
                         f"{_definite(str(gone.get('who') or 'them'))}")
    return total, names


def _definite(name: str) -> str:
    """"desperate man" → "the desperate man"; "Drenn Ironvale" stays. The award line
    reaches the page raw by design, and "You gain 200 XP for weapon, desperate man"
    (2026-09-18) printed actor names as the ledger holds them."""
    name = " ".join(str(name or "").split())
    if not name:
        return name
    first = name.split()[0]
    if first[:1].isupper() or first.lower() in {"the", "a", "an", "your", "his", "her",
                                                  "their", "its", "some"}:
        return name
    return "the " + name


def ready_to_level(actor) -> bool:
    """Whether the XP ledger covers the next level."""
    level = int(getattr(actor, "level", 1) or 1)
    if level >= 20:
        return False
    return int(getattr(actor, "xp", 0) or 0) >= total_for(level + 1)


# --- experience for things that are not fights ------------------------------------------
#
# "i should be receiving EXP for doing things and resolving situations and succeeding on
# checks otherwise It will take a lot for an individual to level, and they are forced to
# seek out violence." The Core Rulebook agrees in principle and is thin in practice:
# "Story Awards" (Gamemastering, Awarding Experience) pay double the XP of a CR equal to
# the APL for concluding a major storyline, and traps and hazards pay as the CR they
# carry; a skill check overcome has no line of its own. So the check award is this
# app's own rule, written down here so it can be argued with: a DC is read as a CR the
# way a trap's is — every two points of DC above 10 is a CR — and a check pays a QUARTER
# of that CR's fight award, because a check is one roll and a fight is a dozen. DC 15
# is 100 XP, DC 20 is 300, DC 25 is 600; a first-level character needs 2,000 to advance,
# so twenty moderate checks or seven hard ones is a level, against five CR 1 fights.

CHECK_SHARE = 4          # a check is a quarter of the fight its DC would be
STORY = {"new": 2.0, "advance": 0.5}   # of a CR = level award; "new" is the CRB's double


def cr_for_dc(dc: int) -> float:
    """A difficulty class read as a challenge rating, the way a trap's is."""
    steps = (int(dc) - 10) / 2
    if steps < 1:
        return 1 / 3 if steps >= 0 else 0
    return min(20, int(steps))


def challenge_award(level: int, dc: int | None) -> int:
    """What beating this DC is worth to a character of this level, or 0.

    Nothing for a DC the character could not fail — under 10 + half their level is
    routine, not a challenge — and never more than the fight award of their own level:
    a lucky roll against an absurd DC is not five fights.
    """
    if dc is None:
        return 0
    if int(dc) < 10 + max(0, int(level)) // 2:
        return 0
    cr = cr_for_dc(int(dc))
    # Below CR 1 — a DC of 10 or 11 — is routine: measured on the first live probe,
    # a DC 10 Perception check to notice a crowd paid 33 XP, which is a level in
    # sixty glances.
    if not cr or cr < 1:
        return 0
    award = CR_AWARD.get(cr) or CR_AWARD.get(round(cr, 3)) or 0
    cap = CR_AWARD.get(max(1, min(20, int(level))), 0)
    return max(0, min(award // CHECK_SHARE, cap))


def story_award(level: int, action: str) -> int:
    """A storyline concluded ("new") pays the CRB's double; one advanced pays half."""
    share = STORY.get(str(action or "").lower(), 0)
    return int(CR_AWARD.get(max(1, min(20, int(level))), 0) * share)
