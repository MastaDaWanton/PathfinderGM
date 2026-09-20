"""A crowd as one thing: the troop, its attrition, and whether it runs.

Asked for on 2026-09-19: *"A crowd of people should be spawned as a single unit with the
combined hp of all its members, it should take up however many squares the people would
take up, find a way to display this and allow for them to be killed giving xp, run away and
scatter."*

The only collective code in the app did the opposite on purpose. `bestiary.split_collective_name`
turns "a pair of guards" into two actors, and its docstring records why: a single 11-hp actor
called "pair of guards" meant the player "fought half as many people as the fiction
described". That was right for two guards and wrong for a crowd, so this is a design
reversal rather than a gap — and the line between them is the member count, which is why
`form` takes one.

Three traditions, each supplying the part the others lack.

**Pathfinder's troop subtype** ([Archives of Nethys](https://www.aonprd.com/MonsterSubtypes.aspx?ItemName=Troop))
gives the shape, and its words are the spec:

  * "A single troop occupies a 20-foot-by-20-foot square, equal in size to a Gargantuan
    creature, though the actual size category of the troop is the same as that of the
    component creatures."
  * Instead of attack rolls, "they deal automatic damage to any creature within reach or
    whose space they occupy at the end of their move, with no attack roll needed."
  * "A troop attempts saving throws as a single creature."
  * "A troop is immune to any spell or effect that targets a specific number of creatures."
  * "A troop takes half again as much damage (+50%) from spells or effects that affect an
    area."
  * "Reducing a troop to 0 hit points or fewer causes it to break up, effectively
    destroying the troop."

One of those is deliberately NOT implemented as written: the fixed 20-by-20 square. The
player's own ruling is "however many squares the people would take up", and a band of three
filling a Gargantuan footprint would be the opposite of what was asked. `size_for` derives
the size from the member count instead, and the grid and the map already draw whatever comes
out (`grid.footprint`, `tables.SPACE_AND_REACH`).

**13th Age's mooks** supply the attrition the troop rules lack: a mob of mooks has a
collective hit-point pool equal to the sum of its members', and every time the mob takes one
member's worth of damage, one member dies, with the excess cascading. That is the "combined
hp" of the request exactly, and it is what makes the unit visibly shrink.

**Basic D&D's morale** is where they run, because Pathfinder has no general morale rule —
which is why a troop can only be destroyed. The Old School Essentials SRD keeps the durable
version: the referee rolls 2d6 against a morale score of 2 to 12; higher than the score and
the monsters surrender or flee, equal or lower and they fight on. It is checked "when the
first combatant on the monster's side has been killed, or when half of the monster's group
have been killed", a 2 never fights at all, a 12 never checks, and a side that passes twice
fights to the death with no further checks.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

# Morale scores, Basic D&D's 2-12 scale. 8 is where the published bandits and raiders sit:
# they will fight, and they will not die for it. 12 means no check is ever made.
# How many people it takes to be a crowd rather than a handful. Below this they arrive as
# themselves, which keeps `split_collective_name`'s original ruling intact where it was
# right: "a pair of guards" is two guards, and one 11-hp actor called "pair of guards" meant
# the player fought half as many people as the fiction described. At five and up the fiction
# is a crowd, the board cannot hold them as bodies anyway (`_PROMOTED_CAP` is four), and one
# unit of twelve is a truer answer than four actors named "twelve soldier".
UNIT_FROM = 5

MORALE_DEFAULT = 8
MORALE_FEARLESS = 12
MORALE_WILL_NOT_FIGHT = 2
# "If a monster makes two successful morale checks in an encounter, it will fight until
# killed, with no further checks necessary."
CHECKS_BEFORE_RESOLVE = 2
# The dice, and the two moments. Both from the same rule.
MORALE_DICE = "2d6"


@dataclass
class Troop:
    """What makes a unit a unit, beside the ordinary actor carrying it.

    `members` is the live count and falls as the pool does; `members_max` is what arrived,
    so the readout can say "17 of 24" and the XP can pay for the difference. `fallen` is
    kept separately from the subtraction because a unit that ROUTS still owes experience
    for the ones who died, and after a rout the live count is no longer a record of that.
    """
    member: str = "guildhand"          # the template each member is
    member_name: str = ""              # what one of them is called, for the tells
    member_hp: int = 4                 # one member's hit points
    member_xp: int = 0                 # what one of them is worth
    members: int = 1
    members_max: int = 1
    morale: int = MORALE_DEFAULT
    fallen: int = 0
    checks_passed: int = 0
    checked_first_blood: bool = False
    checked_half: bool = False
    routed: bool = False

    def as_dict(self) -> dict:
        return {"member": self.member, "member_name": self.member_name,
                "member_hp": int(self.member_hp), "member_xp": int(self.member_xp),
                "members": int(self.members), "members_max": int(self.members_max),
                "morale": int(self.morale), "fallen": int(self.fallen),
                "checks_passed": int(self.checks_passed),
                "checked_first_blood": bool(self.checked_first_blood),
                "checked_half": bool(self.checked_half), "routed": bool(self.routed)}

    @classmethod
    def from_dict(cls, data: dict | None) -> "Troop | None":
        if not isinstance(data, dict) or not data:
            return None
        return cls(
            member=str(data.get("member") or "guildhand"),
            member_name=str(data.get("member_name") or ""),
            member_hp=max(1, int(data.get("member_hp", 4) or 4)),
            member_xp=max(0, int(data.get("member_xp", 0) or 0)),
            members=max(0, int(data.get("members", 1) or 0)),
            members_max=max(1, int(data.get("members_max", 1) or 1)),
            morale=int(data.get("morale", MORALE_DEFAULT) or MORALE_DEFAULT),
            fallen=max(0, int(data.get("fallen", 0) or 0)),
            checks_passed=max(0, int(data.get("checks_passed", 0) or 0)),
            checked_first_blood=bool(data.get("checked_first_blood")),
            checked_half=bool(data.get("checked_half")),
            routed=bool(data.get("routed")),
        )


# The size bands by how many five-foot squares they cover, from `tables.SPACE_AND_REACH`.
# Read here rather than imported as a dict comprehension so the order is explicit: the
# smallest band that holds the members wins.
_BANDS = (("medium", 1), ("large", 4), ("huge", 9), ("gargantuan", 16), ("colossal", 36))


def size_for(members: int) -> str:
    """The size band whose footprint holds this many people, one square each.

    The player's ruling, in place of the troop subtype's fixed 20-by-20: "it should take up
    however many squares the people would take up". Twelve raiders are a 4x4 Gargantuan
    block with four squares to spare; three are Large. Past thirty-six the band runs out and
    Colossal stands — a crowd that big is a crowd, and no grid the app draws has room to
    spread it further.
    """
    n = max(1, int(members or 1))
    for size, squares in _BANDS:
        if n <= squares:
            return size
    return _BANDS[-1][0]


def pool_for(members: int, member_hp: int) -> int:
    """13th Age's mob: "a collective HP pool equal to the sum of the HP of the mooks"."""
    return max(1, int(members or 1)) * max(1, int(member_hp or 1))


def members_left(hp: int, member_hp: int) -> int:
    """How many are still standing, from what is left of the pool.

    Rounded UP, because a member with one hit point left is a member still swinging: a pool
    of 29 against members of 29 is one raider, and a pool of 1 is still one raider. At zero
    or below, nobody — Pathfinder's "reducing a troop to 0 hit points or fewer causes it to
    break up".
    """
    if int(hp) <= 0:
        return 0
    return max(1, math.ceil(int(hp) / max(1, int(member_hp or 1))))


def settle(troop: Troop, hp: int) -> int:
    """Bring the member count in line with the pool, and return how many just fell.

    The one writer of `members` and `fallen`. Every path that changes a troop's hit points
    comes through here, so attrition cannot be applied twice or forgotten once — the law
    about one applicator, kept for a number that is not an effect.
    """
    if troop is None:
        return 0
    now = members_left(hp, troop.member_hp)
    fell = max(0, int(troop.members) - now)
    troop.members = now
    troop.fallen = int(troop.fallen) + fell
    return fell


def owes_a_check(troop: Troop, fell: int) -> str:
    """Which morale check this damage has earned, or "".

    Basic D&D's two moments: "when the first combatant on the monster's side has been
    killed, or when half of the monster's group have been killed or incapacitated". A 12
    never checks and a side that has passed twice never checks again.
    """
    if troop is None or troop.routed or not fell:
        return ""
    if troop.morale >= MORALE_FEARLESS:
        return ""
    if troop.checks_passed >= CHECKS_BEFORE_RESOLVE:
        return ""
    if not troop.checked_first_blood:
        return "first blood"
    if not troop.checked_half and troop.members * 2 <= troop.members_max:
        return "half of them down"
    return ""


def morale_holds(troop: Troop, rolled: int, moment: str) -> bool:
    """2d6 against the morale score: equal or lower and they fight on, higher and they run.

    Marks the moment as checked either way — a check is spent whether or not it is passed,
    or first blood would ask again on every blow.
    """
    if troop is None:
        return True
    if moment == "first blood":
        troop.checked_first_blood = True
    elif moment == "half of them down":
        troop.checked_half = True
    held = int(rolled) <= int(troop.morale)
    if held:
        troop.checks_passed = int(troop.checks_passed) + 1
    else:
        troop.routed = True
    return held


def xp_owed(troop: Troop) -> int:
    """What the members who fell are worth, whether or not the rest ran.

    `xp.award_for_fallen` pays one all-or-nothing award per fallen actor and nothing at all
    for a rout, deliberately, so that mercy is not taxed. A unit is the case that breaks:
    eight raiders dead and four fled is not mercy, and paying nothing for it would be the
    dishonest answer the player would notice first.
    """
    if troop is None:
        return 0
    return max(0, int(troop.fallen)) * max(0, int(troop.member_xp))


def form(template: str, members: int, scene=None, name: str = "",
         morale: int = MORALE_DEFAULT):
    """One actor that is many people: the unit, built out of one member's stat block.

    Everything but the pool, the count and the size comes from the member — its attacks,
    its saves, its armour class — because a unit of raiders fights like a raider, and
    Pathfinder's own troops are built exactly that way ("the actual size category of the
    troop is the same as that of the component creatures", with the block's numbers standing
    for the whole). Saves are the member's and are thrown once, which is the troop rule with
    nothing added: it is one actor.
    """
    from .bestiary import instantiate

    n = max(1, int(members or 1))
    one = instantiate(template, scene=scene)
    member_hp = max(1, int(one.hp_max or one.hp or 1))
    actor = instantiate(template, scene=scene, name=name or _plural_name(one.name, n))
    actor.troop = Troop(member=str(getattr(one, "from_template", "") or template),
                        member_name=str(one.name or template),
                        member_hp=member_hp,
                        member_xp=int(getattr(one, "xp_value", 0) or 0),
                        members=n, members_max=n, morale=int(morale))
    actor.hp_max = pool_for(n, member_hp)
    actor.hp = actor.hp_max
    actor.size = size_for(n)
    # What the unit is worth as a whole, so anything that reads `xp_value` without knowing
    # about troops still pays for what it killed. `xp_owed` is the finer answer for a rout.
    actor.xp_value = int(getattr(one, "xp_value", 0) or 0) * n
    return actor


def _plural_name(one: str, members: int) -> str:
    """"raider" and twelve becomes "twelve raiders" — the name the ledger booked, which is
    the name the prose used. Words the prose already pluralised are left alone."""
    from .bestiary import split_collective_name

    word = " ".join(str(one or "crowd").split()).lower()
    _, singular = split_collective_name(word)
    word = singular or word
    if not word.endswith("s"):
        word = word + ("es" if word.endswith(("s", "x", "ch", "sh")) else "s")
    return f"{_number_word(members)} {word}"


_NUMBERS = ("", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
            "ten", "eleven", "twelve")


def _number_word(n: int) -> str:
    n = max(1, int(n or 1))
    return _NUMBERS[n] if n < len(_NUMBERS) else str(n)


def damage_multiplier(troop: Troop, traits: tuple[str, ...] = ()) -> float:
    """1.5 for an area effect against a unit, 1.0 otherwise.

    "A troop takes half again as much damage (+50%) from spells or effects that affect an
    area." This is the rule that makes a fireball feel right against a crowd, and it is the
    reason a caster has something better to do than pick off one member at a time.
    """
    if troop is None:
        return 1.0
    words = {str(t).strip().lower() for t in (traits or ())}
    return 1.5 if words & {"area", "burst", "spread", "cone", "line", "emanation"} else 1.0


def immune_to_single_target(troop: Troop, targets: int) -> bool:
    """"A troop is immune to any spell or effect that targets a specific number of
    creatures (including single-target spells such as disintegrate and multiple-target
    spells such as haste)."

    An effect with no stated target count is an area or a whole-scene effect and lands.
    """
    return troop is not None and not troop.routed and int(targets or 0) > 0


def tell_of(troop: Troop, name: str, fell: int) -> str:
    """The tell for a blow that killed some of them, in words and never in numbers the
    narrator has to do arithmetic on — the third law. "" when nobody fell."""
    if troop is None or not fell:
        return ""
    who = name or "the crowd"
    if troop.members <= 0:
        return f"{who} breaks apart; the last of them go down."
    # The member's own word, lowercased and pluralised as the count needs: the stat block
    # calls itself "Raider" and "10 Raider go down" is not a sentence.
    one = str(troop.member_name or "").strip().lower()
    body = (f"{fell} of them go down" if not one else
            f"{fell} {one if one.endswith('s') else one + 's'} go down" if fell > 1 else
            f"one {one} goes down")
    return f"{body}; {troop.members} of {who} still stand."


def rout_tell(name: str, troop: Troop) -> str:
    """The tell for a unit whose morale broke."""
    who = name or "the crowd"
    left = max(0, int(getattr(troop, "members", 0)))
    return (f"{who} breaks: the {left} still standing scatter and run."
            if left else f"{who} breaks.")


# --- the corpus's own troop blocks -------------------------------------------------------

# What the subtype says a crowd is, quoted from Archives of Nethys (read 2026-09-20,
# aonprd.com/MonsterSubtypes.aspx?ItemName=Troop): "A troop of Small or Medium creatures
# consists of approximately 12 to 30 creatures."
#
# `docs/the-crowd.md` recorded these blocks as deliberately left alone, because "a
# published troop's hit points ARE the unit's pool and its member count is nowhere in the
# data, so giving them attrition would mean inventing a number per block". The count is
# not in the block — but it is in the RULES, as a band, and that is the half the note
# missed. Nothing is invented per block: the band is the subtype's, and which number
# inside it each block gets comes out of that block's own published hit points.
PUBLISHED_MIN = 12
PUBLISHED_MAX = 30
# Sixteen, and the number is where the subtype's two statements meet this app's own ruling.
# The subtype says "a single troop occupies a 20-foot-by-20-foot square"; twenty feet is
# four squares, so the stated footprint is 4x4 = SIXTEEN squares. `size_for` puts one
# person in each square — the player's ruling, which replaced the subtype's fixed size
# band — so sixteen members is exactly the count at which the published footprint and this
# app's ruling agree, and it sits inside the stated 12-to-30.
#
# A ceiling rather than a target: dividing the pool by it gives a member's share ROUNDED
# UP, so the count that falls out is never more than sixteen and a published troop is
# always the Gargantuan block the subtype describes.
PUBLISHED_SQUARES = 16


def from_block(pool_hp: int) -> tuple[int, int]:
    """(members, member_hp) for a published troop block, from its hit points alone.

    A member's share is the pool over the footprint, rounded up; the count is then what
    `members_left` makes of the full pool, so the arithmetic that runs attrition in play is
    the same arithmetic that sets the roster up — a block cannot start out disagreeing with
    itself, and cannot overflow the square the subtype gives it.

    Measured over the twenty troop blocks the corpus ships (2026-09-20): every one lands
    between 13 and 16 members, inside the subtype's 12-to-30 and Gargantuan to a block,
    with members worth 5 hit points in a cult rabble and 12 in a paladin troop. That spread
    is the point — it comes from the blocks, not from here.
    """
    pool = max(1, int(pool_hp or 1))
    member_hp = max(1, math.ceil(pool / PUBLISHED_SQUARES))
    return members_left(pool, member_hp), member_hp


def published_member_count_is_sane(members: int) -> bool:
    """Whether a derived count sits inside the band the subtype states. Read by the test
    that walks all twenty blocks, so a corpus re-import that breaks the assumption says
    so instead of quietly shipping a troop of three."""
    return PUBLISHED_MIN <= int(members) <= PUBLISHED_MAX


def is_a_published_troop(doc: dict) -> bool:
    """Whether a stat block carries the troop subtype.

    The subtype is stripped before the Actor is built (`bestiary._NOT_ON_THE_SHEET`), so
    this reads the document, which is where it survives.
    """
    if not isinstance(doc, dict):
        return False
    parts = {p.strip().lower()
             for p in re.split(r"[,;]", str(doc.get("subtype") or "")) if p.strip()}
    return "troop" in parts


# What a published block's NAME says about its members, and when it says nothing useful.
#
# "Troop" is the only word that reliably means "this is a unit and not a person": strip it
# and "Imperial Archers Troop" leaves an archer. The COLLECTIVE words below name a crowd
# without naming anybody in it — a member of a Cult Rabble is not a "cult", and a member of
# an Avalanche Legion is not an "avalanche" — so those answer with nothing at all, and
# `tell_of` says "eight of them go down", which is true and reads properly. Deciding that a
# member of a Cult Rabble is a "cultist" would be chasing vocabulary, which CLAUDE.md
# records as the losing move; saying "of them" costs nothing and is never wrong.
_UNIT_WORD = "troop"
_COLLECTIVE = frozenset({"legion", "rabble", "phalanx", "swarm", "horde", "mob", "host",
                         "company", "band", "infantry"})


def one_of(block_name: str) -> str:
    """A member's name out of the unit's published name, or "" when the name has none.

    "Imperial Archers Troop" -> "imperial archer"; "Troop, Cultist" -> "cultist"; "Cult
    Rabble" -> "" because a cult rabble is made of people the name never mentions.
    """
    words = [w.strip(",") for w in str(block_name or "").split() if w.strip(",")]
    words = [w for w in words if w.lower() != _UNIT_WORD]
    if not words:
        return ""
    # A company named after somebody is not a kind of person: "Irgal's Axe Troop" has
    # members, and "irgal's axe" is not what one of them is called.
    if any(w.lower().endswith(("'s", "’s")) for w in words):
        return ""
    if words[-1].lower() in _COLLECTIVE:
        return ""
    last = words[-1]
    if len(last) > 3 and last.lower().endswith("s") and not last.lower().endswith("ss"):
        words[-1] = last[:-1]
    return " ".join(words).lower()
