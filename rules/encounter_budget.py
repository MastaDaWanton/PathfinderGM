"""What a fight the engine builds is allowed to cost: the party's level, and the whole
encounter priced by its total XP.

Measured, and the reason this module exists (2026-11-13): monsters hit at printed
strength now (`docs/printed-attacks.md`), and the windows every picker used were tuned
for the fists they used to swing. A lone level-1 PC died to two CR 1 guards. Each guard
was inside the old per-creature window (CR level-2 .. level+1), but two CR 1s are 800 XP,
which is a CR 3 ENCOUNTER (Core Rulebook p.397, Table 12-1/12-2: "add creatures ... whose
combined XP does not exceed the total XP budget") — and a lone level-1 PC's APL is -1 by
the owner's ruling, so that fight was APL+4: past epic.

The owner's ruling (2026-11-13), which this module is the one home of:

1. The WHOLE encounter is priced by its total XP, never per creature.
2. APL is the average level of the PC and the companions actually with them, rounded to
   the nearest (CRB Step 1: "one of the few exceptions to the round down rule"), then
   adjusted for party size by Step 1 — six or more +1, three or fewer -1 — EXCEPT a lone
   PC, who counts -2.
3. Mostly AVERAGE fights (encounter CR = APL); harder only sometimes; a guard or a lair
   may be challenging or hard; nothing epic unless a document deliberately places it.

Research, sources and the reasoning behind `MIX` are in docs/encounter-budget.md.

An APL below 1 walks down the CRB's own progression for a CR below 1 ("its CR drops one
step on the following progression ... 1/2, 1/3, 1/4, 1/6, 1/8", Adding NPCs): APL 0 is
the CR 1/2 rung, -1 the CR 1/3 rung, and so on. So a lone 1st-level PC's average fight is
135 XP — one CR 1/3 creature — and their hard one 400 XP, one CR 1.

Every roll here is the engine's and hidden: which difficulty (a d100 against `MIX`) and
which creature. No model chooses a number.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import xp as xp_mod

# Table 12-1, as an offset from APL.
TIERS = {"easy": -1, "average": 0, "challenging": 1, "hard": 2, "epic": 3}
ORDER = ("easy", "average", "challenging", "hard", "epic")

# The d100 bands per kind of encounter, low to high: (tier, highest roll). The
# implementer's numbers, argued in docs/encounter-budget.md; the owner may override them.
#   wandering  the road, the camp at night, a creature on a forage, whatever lives in a
#              place just found, trouble in the street: what the land happens to hold.
#   guarded    a guarded find, the watch coming for a wanted name: the ruling's "guards
#              and lairs may be challenging or hard".
#   opening    a document's staged fight at the start of a story: average, sometimes a
#              little more, never an easy one that reads as no attack at all.
MIX = {
    "wandering": (("easy", 20), ("average", 90), ("challenging", 100)),
    "guarded": (("average", 50), ("challenging", 85), ("hard", 100)),
    "opening": (("average", 80), ("challenging", 100)),
}

# A group is never bigger than this, whatever the budget would buy: CRB Table 12-3's
# "1d6 trolls" is a party of four's problem, and one PC facing many small things loses to
# the action economy the XP sum does not price (5e prices it with its multiplier, and
# makes it worse for a party under three: docs/encounter-budget.md). Three is the app's
# own "a few" (`openings.COUNTS`).
MOST = 3

# CR below 1, in the CRB's progression order: index 0 is 1/2, -1 is 1/3, ... -4 is 1/8.
_BELOW_ONE = (0.5, 0.333, 0.25, 0.167, 0.125)


def apl(levels) -> int:
    """The party's APL by the owner's ruling (module docstring). May be 0 or below."""
    levels = [max(1, int(lv or 1)) for lv in (levels or ())] or [1]
    n = len(levels)
    avg = int(sum(levels) / n + 0.5)
    if n == 1:
        return avg - 2
    if n <= 3:
        return avg - 1
    if n >= 6:
        return avg + 1
    return avg


def party_levels(scene, pc_level: int | None = None) -> list[int]:
    """The PC's level and every companion's who is actually with them and standing.

    A companion is someone the `company` op bonded (`Engine._travels_with_you`, an
    effect whose origin is `company:<ref>`). The same tag also rides on a bought horse
    (origin `bought:`), a caravan's people on a job (`job:`) and an animal companion
    (its class origin); none of those is the party the CRB's Step 1 counts — a horse is
    gear, a teamster is the job, and an animal companion is the druid's own class
    feature, already in the druid's level. `pc_level` replaces the PC's level (a trade
    level lower than the body's, `gathering`)."""
    from . import states

    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    own = int(pc_level if pc_level is not None else getattr(pc, "level", 1) or 1)
    out = [max(1, own)]
    if scene is None or pc is None:
        return out
    for a in (getattr(scene, "actors", None) or {}).values():
        if a is pc or getattr(a, "is_pc", False) or a.is_down:
            continue
        if not a.has_state(states.TRAVELS_WITH_YOU):
            continue
        if any(states.TRAVELS_WITH_YOU in (e.tags or ())
               and str(e.origin or "").startswith("company:")
               for e in (getattr(a, "effects", ()) or ())):
            out.append(max(1, int(getattr(a, "level", 1) or 1)))
    return out


def party_apl(scene, pc_level: int | None = None) -> int:
    return apl(party_levels(scene, pc_level))


def rung(index: int) -> float:
    """The CR an encounter index stands for: 1..20 as themselves, 0 and below down the
    CRB's 1/2, 1/3, 1/4, 1/6, 1/8 progression (bottoming out at 1/8)."""
    index = int(index)
    if index >= 1:
        # shortcut: Table 12-2 stops at CR 20 here (`xp.CR_AWARD`); a mythic or 20+
        # budget would need the table extended, not this clamp.
        return float(min(20, index))
    return _BELOW_ONE[min(len(_BELOW_ONE) - 1, -index)]


def budget(index: int) -> int:
    """The XP an encounter of this index is built to (Table 12-2)."""
    return int(xp_mod.CR_AWARD[rung(index)])


def xp_of(row: dict) -> int:
    """A bestiary row's award: its own xp column, else its CR's line of Table 12-2."""
    stated = int((row or {}).get("xp") or 0)
    if stated:
        return stated
    cr = (row or {}).get("cr_value")
    if cr is None:
        return 0
    near = min(xp_mod.CR_AWARD, key=lambda k: abs(float(k) - float(cr)))
    return int(xp_mod.CR_AWARD[near])


def fits(total_xp: int, index: int) -> bool:
    """Whether a total is a spend of this index's budget: no more than it (Step 3) and
    more than the next easier one's, so a rolled average fight is an average fight and
    not an easy one wearing the name."""
    return budget(index - 1) < int(total_xp) <= budget(index) or (
        index <= -4 and 0 < int(total_xp) <= budget(index))


def encounter_index(total_xp: int) -> int | None:
    """The index whose budget this total spends, or None for nothing at all."""
    for index in range(-4, 21):
        if fits(total_xp, index):
            return index
    return None if int(total_xp) <= 0 else 20


def tier(roll: int, kind: str = "wandering") -> str:
    """The difficulty a d100 lands on in this kind's `MIX`."""
    bands = MIX[kind]
    for name, hi in bands:
        if int(roll) <= hi:
            return name
    return bands[-1][0]


def highest_cr(party: int, kind: str = "wandering") -> float:
    """The largest single creature this kind of encounter could ever hold: a narrowing
    for the bestiary query, never the budget itself."""
    top = max(TIERS[name] for name, _ in MIX[kind])
    # The book's thirds arrive as 0.3333…, above the table's 0.333 key: a hair over, so a
    # CR 1/3 creature is not narrowed away from a CR 1/3 budget.
    return rung(party + top) + 0.01


def solitary(row: dict) -> bool:
    """The book says this creature comes alone: an organization of "solitary" and nothing
    else."""
    org = " ".join(str((row or {}).get("organization") or "").lower().split()).rstrip(".")
    return org == "solitary"


@dataclass(frozen=True)
class Draw:
    row: dict
    count: int
    tier: str          # the difficulty the encounter actually landed on
    rolled: str        # the difficulty the d100 asked for
    xp: int            # the encounter's total


def choose(rows, party: int, roll: int, pick, *, kind: str = "wandering",
           most: int = MOST) -> Draw | None:
    """A creature and a count whose total XP spends the rolled difficulty's budget.

    `rows` are the candidates the caller already chose by ground and kind; `roll` the
    engine's hidden d100 for the difficulty; `pick(n)` a hidden 0-based pick of one of n.
    When nothing fits the rolled difficulty the next EASIER one is tried, down to easy —
    never a harder one: ground that stocks nothing small enough is a quiet ground (None),
    not a fight above the party."""
    asked = tier(roll, kind)
    rows = [r for r in rows if xp_of(r) > 0]
    for name in reversed(ORDER[:ORDER.index(asked) + 1]):
        index = party + TIERS[name]
        pool = [(r, n) for r in rows for n in range(1, max(1, int(most)) + 1)
                if fits(n * xp_of(r), index) and (n == 1 or not solitary(r))]
        if pool:
            pool.sort(key=lambda p: (str(p[0].get("id") or ""), p[1]))
            row, n = pool[pick(len(pool))]
            return Draw(row=row, count=n, tier=name, rolled=asked, xp=n * xp_of(row))
    return None


def most_of(each_xp: int, wanted: int, party: int, roll: int, *,
            kind: str = "wandering") -> int:
    """How many of a codex person (each worth `each_xp`) a document or a table may bring
    against the party: as many as asked, fewer until the total is inside the rolled
    difficulty's budget, never fewer than one — a single person is who the words named,
    and the words are the floor."""
    if each_xp <= 0:
        return max(1, int(wanted))
    cap = budget(party + TIERS[tier(roll, kind)])
    n = max(1, int(wanted))
    while n > 1 and n * each_xp > cap:
        n -= 1
    return n
