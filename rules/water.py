"""Being in water, and what it does to a body.

Until 2026-09-16 this app had no water. Fourteen terrains and not one of them was wet:
`aquatic`, `underwater`, `river` and `lake` all resolved to `coast`, so the sea was the
sand beside it and 468 creatures — every shark and kraken in the bestiary — lived on a
beach. The gap was written down in this app's own tables and reported to World Bible as a
reason two race traits could not work: **"a swim speed: the engine has no water"**.

Two terrains now, because the Core Rulebook treats them as two situations. `water` is a
surface: you can breathe, you have improved cover from anyone on land, and you are either
swimming or wading. `underwater` is below it: you cannot breathe, you have total cover,
fire does not burn, and the only clock that matters is the breath you brought. Diving is a
move between two places, which is the shape a storey already has.

**The footing is the whole of it.** Table 13-7 does not ask what you are doing; it asks
what you have. Four rows, best to worst, and every penalty in the book falls out of which
one you are in:

    freedom of movement   nothing applies. The spell is the answer to this whole table
    a swim speed          slashing and bludgeoning at -2 and half damage; piercing whole
    a made Swim check     the same, and a quarter of your speed on a move action
    firm footing          the same, and half speed — standing on the bottom, weighed down
    none of those         everything at -2 and half, opponents at +2, and no Dex to AC

That last row is what happens to an armoured character who goes over the side, and it is
the reason a fight in water is a different fight rather than the same fight in a blue
room: you are not harder to hit, you are easier, and your sword does half.

**What this module is and is not.** It is the rules as data and the derivations off them —
which row a creature is in, what a Swim check costs, how long a held breath lasts, what
drowning does next. It applies nothing: the engine owns the applicator, the same as
`rules/attitude.py` owns the attitude table and `Engine._set_attitude` owns the writing.

Sources, read 2026-09-16: Core Rulebook "Underwater Combat" (Table 13-7, the ranged
penalty, the cover from land, the caster level check for fire), "Aquatic Terrain", the
Swim skill, and the drowning rules under Environment.
"""
from __future__ import annotations

# The two grounds this module speaks for. `terrain_of` parses one off a place id and
# nothing here looks anything up, which is the arrangement the whole place model keeps.
SURFACE = "water"
UNDER = "underwater"
WET = (SURFACE, UNDER)

# --- which row you are in -----------------------------------------------------------------

# Best to worst. The names are this app's, the rows are the book's.
FREE = "free"                 # freedom of movement: the table does not apply
SWIMMER = "swimmer"           # a natural swim speed
SWIMMING = "swimming"         # treading water on a made Swim check
FOOTING = "footing"           # standing on the bottom, weighed down
OFF_BALANCE = "off-balance"   # none of the above, and it is as bad as it sounds

ROWS = (FREE, SWIMMER, SWIMMING, FOOTING, OFF_BALANCE)

# What each row costs, as the numbers the funnel takes. `attack` and `damage_halved` are
# scoped to the damage TYPES named, because that is how the book scopes them: a spear
# works in water and a sword does not.
#
# `opponents` is the +2 other creatures get against you, carried here rather than on them
# — it is a fact about your footing, and the attack roll reads it off the defender.
PENALTIES: dict[str, dict] = {
    FREE: {},
    SWIMMER: {"attack": -2, "against": ("slashing", "bludgeoning"), "halved": True},
    SWIMMING: {"attack": -2, "against": ("slashing", "bludgeoning"), "halved": True,
               "speed": 0.25},
    FOOTING: {"attack": -2, "against": ("slashing", "bludgeoning"), "halved": True,
              "speed": 0.5},
    OFF_BALANCE: {"attack": -2, "against": ("slashing", "bludgeoning", "piercing"),
                  "halved": True, "opponents": 2, "no_dex_to_ac": True},
}

# A thrown weapon is useless in water whatever your footing, and everything else loses two
# for every five feet of water it crosses. Both are the book's, and both are about the
# water rather than about the swimmer.
RANGED_PER_5FT = -2
THROWN_WORKS = False

# Improved cover from anyone on land while you are at the surface; total cover once you
# are under it. The numbers are the book's own improved-cover line.
COVER_AC, COVER_REFLEX = 8, 4

# A spell with the fire descriptor needs a caster level check to work down there, and
# casting at all needs concentration if you cannot breathe the stuff.
FIRE_DC_BASE = 20
CONCENTRATION_DC_BASE = 15

# Swim DCs by how rough it is. The Swim skill's own table.
SWIM_DC = {"calm": 10, "rough": 15, "stormy": 20}
DEFAULT_WATER = "calm"

# Drowning, from Environment. You hold your breath for twice your Constitution in rounds;
# after that it is a Constitution check each round at DC 10, rising by one each time, and
# three rounds from the first failure you are dead.
BREATH_ROUNDS_PER_CON = 2
DROWN_DC_BASE = 10


def is_wet(terrain: str) -> bool:
    return str(terrain or "").strip().lower() in WET


def is_under(terrain: str) -> bool:
    return str(terrain or "").strip().lower() == UNDER


def row_for(actor, made_swim_check: bool | None = None) -> str:
    """Which row of Table 13-7 this creature is in, worst case first.

    Asked of the creature and never of the narrator: it is a fact about what they have on
    and what their body can do, which is exactly the kind of thing this app refuses to let
    a model assert. `made_swim_check` is the engine's own roll when it made one — None
    means nobody has asked, which is the ordinary case for a creature that is simply in
    the water and not trying to get anywhere.
    """
    if _has(actor, "freedom-of-movement") or _has(actor, "buff.freedom-of-movement"):
        return FREE
    if swim_speed(actor):
        return SWIMMER
    if made_swim_check:
        return SWIMMING
    if made_swim_check is False:
        return OFF_BALANCE
    # Nobody asked, so it is what they are wearing that decides. A character in heavy
    # armour is on the bottom whether they like it or not; one in cloth is treading water.
    return FOOTING if _weighed_down(actor) else OFF_BALANCE


def swim_speed(actor) -> int:
    """A creature's own swim speed in feet, or 0. Read through the tag vocabulary."""
    speeds = getattr(actor, "speeds", None)
    if callable(speeds):
        try:
            return int((speeds() or {}).get("swim", 0) or 0)
        except Exception:
            pass
    elif isinstance(speeds, dict):
        return int(speeds.get("swim", 0) or 0)
    for tag in _tags(actor):
        if str(tag).startswith("move.swim."):
            try:
                return int(str(tag).rsplit(".", 1)[-1])
            except ValueError:
                return 0
    return 0


def breathes_water(actor) -> bool:
    """Whether the water is somewhere this creature simply lives.

    `amphibious` is the race tag for it and the aquatic subtype is the bestiary's. Both
    are asked through the vocabulary rather than matched as strings anywhere else.
    """
    if _has(actor, "amphibious") or _has(actor, "breathes.water"):
        return True
    subtypes = getattr(actor, "subtypes", None) or ()
    return any(str(s).strip().lower() == "aquatic" for s in subtypes)


def breath_rounds(actor) -> int:
    """How long this creature can hold its breath, in rounds.

    Twice Constitution, and four times it for a race that says so — `hold-breath` is a
    trait World Bible's cards can grant off their own words ("they can stay under for
    minutes at a time").
    """
    con = 10
    mod = getattr(actor, "ability_score", None)
    if callable(mod):
        try:
            con = int(mod("con"))
        except Exception:
            con = 10
    rounds = max(1, con) * BREATH_ROUNDS_PER_CON
    return rounds * 2 if _has(actor, "hold-breath") else rounds


def drown_dc(failed_checks: int) -> int:
    """DC 10, and one harder every round you keep trying."""
    return DROWN_DC_BASE + max(0, int(failed_checks))


def swim_dc(water: str = DEFAULT_WATER) -> int:
    return SWIM_DC.get(str(water or "").strip().lower(), SWIM_DC[DEFAULT_WATER])


def attack_penalty(row: str, damage_type: str) -> int:
    """What the water takes off a swing of this kind. Zero for a spear in a swimmer's
    hand, which is the whole point of the table being scoped by type."""
    rule = PENALTIES.get(row) or {}
    against = rule.get("against") or ()
    return int(rule.get("attack", 0)) if _matches(damage_type, against) else 0


def damage_halved(row: str, damage_type: str) -> bool:
    rule = PENALTIES.get(row) or {}
    return bool(rule.get("halved")) and _matches(damage_type, rule.get("against") or ())


def speed_factor(row: str) -> float:
    """What fraction of their speed this creature moves at. 1.0 where the table says
    nothing, which is a swimmer and anybody the spell is on."""
    return float((PENALTIES.get(row) or {}).get("speed", 1.0))


def bonus_against(row: str) -> int:
    """What everybody else gets on attack rolls against a creature in this row."""
    return int((PENALTIES.get(row) or {}).get("opponents", 0))


def loses_dex_to_ac(row: str) -> bool:
    return bool((PENALTIES.get(row) or {}).get("no_dex_to_ac"))


def said(row: str) -> str:
    """The tell for what the water is doing to somebody. Never a number — third law."""
    return {
        FREE: "moves through the water as though it were not there",
        SWIMMER: "swims as easily as walking",
        SWIMMING: "is treading water, and everything costs more",
        FOOTING: "is on the bottom, wading, and slow with it",
        OFF_BALANCE: "is floundering: no footing, no guard, and nothing behind a blow",
    }.get(row, "is in the water")


# --- reading a creature, whatever kind it is ------------------------------------------------

def _tags(actor) -> tuple:
    got = getattr(actor, "tags", None)
    if callable(got):
        try:
            got = got()
        except Exception:
            got = ()
    return tuple(got or ())


def _has(actor, tag: str) -> bool:
    """One question asked one way. `has_state` is the vocabulary's own door and every
    actor has it; the tag list is the race document's, for a creature that is not an
    actor yet."""
    fn = getattr(actor, "has_state", None)
    if callable(fn):
        try:
            if fn(tag):
                return True
        except Exception:
            pass
    return any(str(t) == tag or str(t).startswith(tag + ".") for t in _tags(actor))


def _weighed_down(actor) -> bool:
    """Whether what they are carrying puts them on the bottom rather than on the surface.

    Medium or heavy armour, or a load past light. The book's "firm footing" row is about
    being weighed down enough to stand, and this is the reading that makes an armoured
    character's problem in water the same as their problem everywhere else.
    """
    worn = getattr(actor, "worn", None) or {}
    for item in (worn.values() if hasattr(worn, "values") else worn):
        weight = str((item or {}).get("armour_type") or (item or {}).get("category") or "")
        if weight.strip().lower() in ("medium", "heavy"):
            return True
    load = getattr(actor, "load", None)
    if callable(load):
        try:
            return str(load()).strip().lower() in ("medium", "heavy", "overloaded")
        except Exception:
            return False
    return False


def _matches(damage_type: str, against: tuple) -> bool:
    """Whether this damage is of a kind the water spoils.

    A weapon may say "slashing or piercing" — a longsword does — and the honest reading of
    a weapon that can do either is that the wielder uses the half that still works. So a
    type that names ANY kind the water does not spoil escapes the penalty.
    """
    said = str(damage_type or "").strip().lower()
    if not said:
        return False
    kinds = {k.strip() for k in said.replace("/", " or ").replace(",", " or ").split(" or ")
             if k.strip()}
    if not kinds:
        return False
    return kinds <= set(against)
