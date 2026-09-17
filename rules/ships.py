"""Ships: something to stand on when the ground is water.

Asked for 2026-09-16, and the ruling that shaped it came with the ask: **ships close and
then people board**. The fight is on the deck.

That ruling is worth its reasons, because the obvious alternative has been tried in
public. Pillars of Eternity II shipped text-based ship-to-ship combat — turns, no picture,
no orientation shown — and reviewers called it the worst naval combat in any RPG they had
played. The specific failures are the ones a narrated text game walks straight into: the
player could not tell where the ships were in relation to each other, the exchange was
tactically trivial, and the winning move was always to close and board, which made the
whole system a tedious prelude to the fight that mattered. Pathfinder offers two systems
and the same reasoning picks between them: Ultimate Combat's vehicle rules (vehicular bull
rush, overrun, ramming maneuvers, crew stations, siege engines with reload times) are a
simulation this app's narrator would have to describe every round, and the GameMastery
Guide's fast-play rules are eight lines. **The fast-play rules, and then a deck.**

**A ship is a place you stand on, not a creature and not a vehicle object.** That is the
whole design and everything else falls out of it:

- the deck is a place with a floor plan, so a fight on it is a fight this engine already
  knows how to run — cover behind the mast, a rail to be thrown over, below-decks through
  a hatch;
- going over the side is a move to the `water` place alongside, which is a rule
  `rules/water.py` already owns, penalties, drowning clock and all;
- the vessel itself is a small record — hit points, speed, crew, what a ram does — held by
  the scene, because unlike a room it MOVES, and where it is is a fact that changes.

Table 7-49 from the GameMastery Guide is below, unaltered. Hardness 5 is wood. A rowboat
is deliberately absent: it is not on that table (it lives in the vehicle rules, which this
does not use), and inventing a row would be inventing Pathfinder.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

# The ground a deck is. Its own terrain and not `water`, because a creature standing on
# planking is not swimming: `water.is_wet` answers no, so none of the underwater table
# applies. Not `urban` either — what lives in a street has no business in the Atlantic.
DECK = "deck"

# Hardness 5, wood, from the same table. Applied to every vessel here because every vessel
# here is made of it.
HARDNESS = 5

# GameMastery Guide, Table 7-49: Ships. AC, hit points, base save, maximum speed in feet,
# arms (how many siege engines it can carry), ram damage, its size in squares, and the crew
# it needs and can hold.
#
# Every speed on this table is under sail, and a ship with the wind behind it moves at
# double — which is the one weather rule this app has, and it is the book's.
VESSELS: dict[str, dict] = {
    "keelboat": {
        "name": "keelboat", "ac": 8, "hp": 60, "save": 4, "speed": 30, "arms": 1,
        "ram": "2d6+6", "squares": 2, "crew": (1, 4), "passengers": 15,
        "about": "a river boat with a shallow draught and no pretensions",
        "places": (("the deck", "planking, a tiller, and not much room", False),
                   ("the hold", "cargo, bilge water, and a low beam", True)),
    },
    "longship": {
        "name": "longship", "ac": 6, "hp": 75, "save": 5, "speed": 60, "arms": 1,
        "ram": "4d6+18", "squares": 3, "crew": (50, 50), "passengers": 75,
        "about": "shallow, fast, and built to be dragged up a beach",
        "places": (("the deck", "benches, oars, and the shields along the rail", False),
                   ("the steering deck", "the steerboard, and whoever holds it", False)),
    },
    "sailing ship": {
        "name": "sailing ship", "ac": 6, "hp": 125, "save": 6, "speed": 60, "arms": 2,
        "ram": "3d6+12", "squares": 3, "crew": (20, 20), "passengers": 50,
        "about": "a trader: three masts, a deep hold, and a crew who want no trouble",
        "places": (("the deck", "the mainmast, the hatches, and the rail", False),
                   ("below decks", "hammocks, lamplight, and everybody's belongings", True),
                   ("the hold", "the cargo, lashed down and in the way", True),
                   ("the rigging", "up among the sheets, with the deck a long way down",
                    False)),
    },
    "warship": {
        "name": "warship", "ac": 2, "hp": 175, "save": 7, "speed": 60, "arms": 3,
        "ram": "3d6+12", "squares": 4, "crew": (60, 60), "passengers": 80,
        "about": "built to close with other ships and take them",
        "places": (("the deck", "cleared for action, and the engines on it", False),
                   ("the sterncastle", "high, railed, and where the orders come from",
                    False),
                   ("below decks", "the crew's quarters, and the arms locker", True),
                   ("the hold", "powder, shot, and water in barrels", True)),
    },
    "galley": {
        "name": "galley", "ac": 2, "hp": 200, "save": 8, "speed": 90, "arms": 4,
        "ram": "6d6+24", "squares": 4, "crew": (200, 200), "passengers": 250,
        "about": "two hundred oars and a beak at the front for using them on",
        "places": (("the deck", "the gangway down the middle, and the engines", False),
                   ("the oar deck", "benches, chains where there are chains, and no air",
                    True),
                   ("the sterncastle", "where the captain stands and can see", False),
                   ("the hold", "what two hundred rowers eat and drink", True)),
    },
}

# What a port keeps. A settlement that can sell you passage is one with somewhere for a
# ship to tie up; what it has tied up is decided by how big the settlement is, which is
# the same `scale` everything else about a settlement reads.
BY_SCALE = {
    "village": ("keelboat",),
    "town": ("keelboat", "sailing ship", "longship"),
    "city": ("sailing ship", "longship", "warship", "galley"),
}

# The places in a settlement that mean it can put a ship to sea. A settlement with none of
# these is inland as far as this app is concerned, whatever the prose says about the view.
PORT_PLACES = ("the docks", "the harbour", "the quay", "the wharf")

# A ship at sea makes way for this much of a day. Eight hours is a marching day on land
# and a ship does not stop at dusk — it has watches — so a sea day is the whole of it,
# which is most of why the sea is faster than the road even at the same speed.
HOURS_AT_SEA = 24

# 0 hit points is not sunk: it is SINKING, which is ten rounds of people getting off.
SINKS_AFTER = 10
# "Damage to sinking ships reduces remaining time by 1 round per 25 damage."
HASTEN_PER = 25


@dataclass
class Vessel:
    """One ship, as the scene holds it.

    Not a `Place` and not an `Actor`. A place does not move and an actor is a creature —
    a vessel is a third thing, and the honest shape for it is the small record that the
    fast-play rules actually need: what it can take, how fast it goes, who is aboard, and
    whether it is going down.
    """
    id: str
    name: str
    kind: str
    hp: int
    sinking: int | None = None          # rounds left once it is going down
    crew: int = 0
    at: str = ""                        # the settlement it lies at, or "" for at sea
    bound_for: str = ""                 # where it is going, when it is going somewhere
    days_left: int = 0

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind, "hp": self.hp,
                "sinking": self.sinking, "crew": self.crew, "at": self.at,
                "bound_for": self.bound_for, "days_left": self.days_left}

    @classmethod
    def from_dict(cls, d: dict) -> "Vessel | None":
        if not isinstance(d, dict) or not str(d.get("id") or "").strip():
            return None
        kind = str(d.get("kind") or "")
        if kind not in VESSELS:
            return None
        return cls(id=str(d["id"]), name=str(d.get("name") or "a ship"), kind=kind,
                   hp=int(d.get("hp", VESSELS[kind]["hp"]) or 0),
                   sinking=(int(d["sinking"]) if d.get("sinking") is not None else None),
                   crew=int(d.get("crew", 0) or 0), at=str(d.get("at") or ""),
                   bound_for=str(d.get("bound_for") or ""),
                   days_left=int(d.get("days_left", 0) or 0))

    @property
    def row(self) -> dict:
        return VESSELS[self.kind]

    @property
    def ac(self) -> int:
        return int(self.row["ac"])

    @property
    def speed(self) -> int:
        return int(self.row["speed"])

    @property
    def afloat(self) -> bool:
        return self.sinking is None and self.hp > 0


# --- naming and minting ---------------------------------------------------------------------

# Ships are named after what they do, what they carry and what their owners hope. Two
# halves, joined, seeded off the vessel id — the same arrangement a keeper's name has, and
# for the same reason: the ship the party took passage on last week is the same ship this
# week, with nothing stored.
_FIRST = ("Grey", "Long", "Salt", "Cold", "Black", "Fair", "Iron", "Red", "Storm",
          "Morning", "Deep", "Far", "Old", "Winter", "Bright")
_SECOND = ("Gull", "Mare", "Lantern", "Bargain", "Widow", "Hound", "Crossing", "Pledge",
           "Herring", "Compass", "Daughter", "Anchor", "Tern", "Wager", "Sister")


def _seed(text: str) -> int:
    """The same durable number every other derived thing in this app takes. Not `hash()`:
    Python salts it per process, so a ship would be renamed by a restart."""
    return int(hashlib.sha256(str(text or "ship").encode()).hexdigest()[:8], 16)


def name_for(vessel_id: str) -> str:
    n = _seed(vessel_id)
    return f"the {_FIRST[n % len(_FIRST)]} {_SECOND[(n >> 8) % len(_SECOND)]}"


def vessel_id(port_id: str, kind: str, n: int = 0) -> str:
    """A ship's durable id: `ship-` and twelve hex characters.

    Shaped like a World Bible entity id on purpose, because a place id is
    `{parent}~{terrain}:{slug}` and the parent half may not contain a colon — the first
    version of this read `ship:<port>:<kind>:<n>`, and `terrain_of` came back with the
    empty string, which is the published way of saying "this place stands on nothing".
    A twelve-by-twenty field of blank ground, which is precisely what the id grammar
    exists to prevent.

    `ship-` rather than `ship:` so it is still obvious at a glance that this is the app's
    own and not the world's, the way `keeper:` is on a person.
    """
    digest = hashlib.sha256(f"{port_id}|{kind}|{n}".encode()).hexdigest()[:12]
    return f"ship-{digest}"


def offered_at(port_id: str, scale: str, n: int = 2) -> list[Vessel]:
    """The ships lying at a port today, which is the same ones tomorrow.

    Derived off the port's own id, so a harbour has its regulars: the player who took the
    Grey Gull out last month finds her at the same quay, and that is worth more to a
    campaign than a fresh roll every visit.
    """
    kinds = BY_SCALE.get(str(scale or "").strip().lower()) or BY_SCALE["town"]
    seed = _seed(port_id)
    out: list[Vessel] = []
    for i in range(max(1, n)):
        kind = kinds[(seed >> (4 * i)) % len(kinds)]
        vid = vessel_id(port_id, kind, i)
        row = VESSELS[kind]
        out.append(Vessel(id=vid, name=name_for(vid), kind=kind, hp=int(row["hp"]),
                          crew=int(row["crew"][0]), at=str(port_id)))
    return out


def places_of(vessel: Vessel):
    """The rooms of a ship, as `places.Place` objects hanging off the vessel's own id.

    The deck first, because that is where you arrive and where a boarding action lands.
    Every one of them stands on `deck` ground, which is what keeps a fight on a ship out
    of the underwater table — you are on planking, not in the sea, until you are.
    """
    from . import places as places_mod

    rows = list(vessel.row["places"])
    ids = [f"{vessel.id}~{DECK}:{places_mod._slug(label)}" for label, _a, _i in rows]
    out = []
    for (label, about, _indoors), pid in zip(rows, ids):
        out.append(places_mod.Place(
            id=pid, name=label, about=about, terrain=DECK,
            exits=tuple(x for x in ids if x != pid),
            parent=vessel.id, origin="ship"))
    return tuple(out)


def deck_of(vessel: Vessel) -> str:
    """Where somebody boarding arrives, and where a fight on this ship happens."""
    got = places_of(vessel)
    return got[0].id if got else ""


# --- what the sea costs ------------------------------------------------------------------------

def days_for(miles: int | None, kind: str, days_apart: int = 1,
             with_the_wind: bool = False) -> int:
    """How long a passage takes, in days.

    Miles when the world states them, at the vessel's own speed — a ship's speed is feet
    per round like everything else in this game, and the conversion to miles an hour is
    the one `rules/journey.py` already uses. When the world states no distance, the tree's
    own ordering stands in, exactly as it does for a road: two settlements on one
    continent are nearer than two on different ones, whatever the miles turn out to be.

    Never less than a day. A crossing that takes an afternoon is a ferry, and a ferry is
    not a passage — it is a road with water under it.
    """
    from . import journey as journey_mod

    speed = int(VESSELS.get(kind, VESSELS["sailing ship"])["speed"])
    if with_the_wind:
        speed *= 2                      # "vessels move at double speed with the wind"
    if not miles:
        return max(1, int(days_apart))
    mph = max(0.1, speed / journey_mod.FEET_PER_MPH)
    return max(1, round(int(miles) / (mph * HOURS_AT_SEA)))


def ram_damage(kind: str) -> str:
    return str(VESSELS.get(kind, VESSELS["sailing ship"])["ram"])


def take_damage(vessel: Vessel, amount: int) -> str:
    """Hit a ship, and say what it did. Hardness first, then the hull.

    0 hit points is the `sinking` condition and not the bottom: ten rounds, less one for
    every 25 damage past it, which is the book's rule and is also the only reason a ship
    fight has a clock worth feeling. Everybody aboard has that long to be somewhere else.
    """
    amount = max(0, int(amount) - HARDNESS)
    if not amount:
        return f"{vessel.name} takes it on the timbers."
    if vessel.sinking is not None:
        vessel.sinking = max(0, vessel.sinking - amount // HASTEN_PER)
        return f"{vessel.name} settles faster."
    vessel.hp -= amount
    if vessel.hp > 0:
        return f"{vessel.name} is holed."
    vessel.hp = 0
    vessel.sinking = SINKS_AFTER
    return f"{vessel.name} is going down."


def sink_tick(vessel: Vessel) -> str:
    """One round of going down. Returns a tell when something changed."""
    if vessel.sinking is None:
        return ""
    vessel.sinking -= 1
    if vessel.sinking <= 0:
        vessel.sinking = 0
        return f"{vessel.name} goes under."
    if vessel.sinking in (5, 3, 1):
        return f"{vessel.name} has {'moments' if vessel.sinking < 3 else 'little time'} left."
    return ""


# --- closing, and then boarding ----------------------------------------------------------------
#
# The whole ship-to-ship model, and it is three words long on purpose.
#
# The fast-play rules put ships on a mat at thirty feet to the square and move them on the
# captain's initiative. This app has no mat and no picture — it has a narrator — and that
# is exactly the ground Pillars of Eternity II came to grief on: its naval combat was
# turns of text in which the player could not tell how the two ships were oriented, and
# the winning move was always to close and board anyway. So the distance between two ships
# is a BAND, the same shape the tactical zones already are, and the interesting decisions
# are what you do while it shrinks.
#
# distant     they are a sail on the horizon. You can run, or you can turn and close
# closing     bowshot: arrows, spells, and the last round in which running is cheap
# alongside   oars touching. Grapnels, boarding planks, and the fight is a deck away
RANGES = ("distant", "closing", "alongside")

# What running costs once the grapnels are in: you do not get to leave until they are cut.
# The one thing on the whole engagement that is not reversible in a round, which is what
# makes throwing them a decision rather than a formality.
GRAPPLE_ESCAPE_DC = 15


def closer(band: str) -> str:
    i = RANGES.index(band) if band in RANGES else 0
    return RANGES[min(len(RANGES) - 1, i + 1)]


def further(band: str) -> str:
    i = RANGES.index(band) if band in RANGES else 0
    return RANGES[max(0, i - 1)]


def ram_self_damage(kind: str) -> int:
    """What ramming costs the rammer.

    "...inflicting damage as indicated on the ship statistics table to the target, as well
    as minimum damage to the ramming ship." The minimum of your own ram dice, which is the
    book's way of saying a ram is a thing you do to a hull with a hull.
    """
    spec = ram_damage(kind)
    dice, _, bonus = spec.partition("+")
    count = int(dice.split("d")[0] or 1)
    return count + (int(bonus) if bonus else 0)


def crewed(vessel: Vessel) -> bool:
    """Whether there are enough hands to work her. A galley wants two hundred; a keelboat
    wants one. A ship below her minimum does not move, which is the quiet reason you
    cannot simply steal a warship."""
    return vessel.crew >= int(vessel.row["crew"][0])
