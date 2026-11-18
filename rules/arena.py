"""An arena's bout: the house stages a fight for a purse, and nobody dies of it.

Playtest 2026-11-17b #24: "Then put me in the next bout. Who do I fight, and what does the
winner take?" to Mirabalos's master of the games built nothing. The arena was a place with
a master (`places.STAFFED["the arena"]`) and no bouts: he gave two speeches about blood and
coin and never offered a fight.

**The books and the games** (read 2026-11-18):

  * Ultimate Combat, Performance Combat (aonprd.com Rules.aspx?ID=1082): bouts come in
    kinds — a *knockout bout*, where "As long as both sides in the performance combat
    remain standing, the fight continues"; *to the death*, where "Only the death of one
    side ends these bouts"; to a number of wounds or first blood; toward a goal. A crowd
    "Typically ... starts out with an indifferent attitude toward each side." It says
    nothing of purses, so the purse below is not from it.
  * Core Rulebook Table 12-5, Treasure Values per Encounter (the engine's copy is
    `treasure._BY_CR`): what a fight of that CR pays. The loser of a bout keeps their own
    gear (nobody strips a gladiator who is still breathing), so the house's purse stands
    in for the treasure a fight would have paid.
  * The owner's encounter ruling (2026-11-13, `rules/encounter_budget.py`): the whole
    encounter priced by the party's APL, a lone PC at level - 2, mostly average fights.
  * Oblivion's Arena (UESP, Oblivion:Arena; Game8's guide): the Blademaster stages one match
    at a time, only between 9am and 9pm, and the purse rises with the fighter's rank
    (50 gold a win at the bottom). Its matches are to the death, and there is no way down
    the ladder for it. Taken: the house stages it, in its hours, one bout at a time.
    Refused: to the death by default (a bout a player asks for in passing should not kill
    them) and the rank ladder (not built: said, not hidden).

**What is built.** A knockout bout, nonlethal: the house picks one opponent from the codex's
fighters (`STAFFED["the arena"]` words: gladiator, champion, fighter) at the CR of the
party's average encounter, every blow between the two is pulled to nonlethal
(`states.IN_A_BOUT`, read by the attack), the fight is the engine's ordinary fight, and
when it ends the purse is paid to a winner still standing (`Engine._settle_bout`). One
bout a day at each arena: the house does not stage a second the same day (a purse a fight
must not be farmed).

**Design calls** (recorded for the owner): nonlethal knockout as the only kind; the purse
is the book's treasure for the bout's CR, in full; one bout a day per arena; the house pays
from its own coffers, not the master's purse; the crowd's attitude and Performance
Combat's victory points are not built.
"""
from __future__ import annotations

from . import encounter_budget, npcs, treasure

# Who fights in an arena, in the codex's words: the staffing table's own for the arena.
FIGHTER_WORDS = ("gladiator", "champion", "fighter")
KIND = "arena"
DAY = 24 * 60


def purse_cp(cr: float) -> int:
    """The house's purse for a bout of this CR, in copper: CRB Table 12-5's treasure for
    an encounter of that CR (CR below 1 is the table's lowest rung, as `treasure` reads)."""
    return int(treasure._BY_CR[max(0, min(20, int(cr)))]) * 100


def opponent(scene) -> tuple[dict, float] | None:
    """(the codex block, its CR) the house puts up against the party: the fighter nearest
    the party's average encounter, stepped down until its XP is inside that budget
    (Table 12-1 via `encounter_budget`). None when the codex holds nobody that small."""
    from . import xp as xp_mod

    index = encounter_budget.party_apl(scene)
    cap = encounter_budget.budget(index)
    want = encounter_budget.rung(index)
    level = max(1, int(want) + 1) if want >= 1 else 1
    while level >= 1:
        block = npcs.choose(FIGHTER_WORDS, level)
        cr = block.get("cr_value") if block else None
        if block and cr is not None:
            near = min(xp_mod.CR_AWARD, key=lambda k: abs(float(k) - float(cr)))
            if xp_mod.CR_AWARD[near] <= cap:
                return block, float(cr)
        level -= 1
    return None


def staged_today(scene, place_id: str) -> bool:
    day = int(scene.clock_minutes) // DAY
    return (getattr(scene, "rewarded", None) or {}).get(f"bout|{place_id}") == day


def mark_staged(scene, place_id: str) -> None:
    scene.rewarded[f"bout|{place_id}"] = int(scene.clock_minutes) // DAY
