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
# it needs and can hold. `price_gp` is the CRB's (Table 6-9, Transport): what the law prices
# a taken ship at (rules/trial.py, the theft fine).
#
# Every speed on this table is under sail, and a ship with the wind behind it moves at
# double — which is the one weather rule this app has, and it is the book's.
VESSELS: dict[str, dict] = {
    "keelboat": {
        "name": "keelboat", "price_gp": 3000, "ac": 8, "hp": 60, "save": 4, "speed": 30, "arms": 1,
        "ram": "2d6+6", "squares": 2, "crew": (1, 4), "passengers": 15,
        "about": "a river boat with a shallow draught and no pretensions",
        "places": (("the deck", "planking, a tiller, and not much room", False),
                   ("the hold", "cargo, bilge water, and a low beam", True)),
    },
    "longship": {
        "name": "longship", "price_gp": 10000, "ac": 6, "hp": 75, "save": 5, "speed": 60, "arms": 1,
        "ram": "4d6+18", "squares": 3, "crew": (50, 50), "passengers": 75,
        "about": "shallow, fast, and built to be dragged up a beach",
        "places": (("the deck", "benches, oars, and the shields along the rail", False),
                   ("the steering deck", "the steerboard, and whoever holds it", False)),
    },
    "sailing ship": {
        "name": "sailing ship", "price_gp": 10000, "ac": 6, "hp": 125, "save": 6, "speed": 60, "arms": 2,
        "ram": "3d6+12", "squares": 3, "crew": (20, 20), "passengers": 50,
        # Two masts, as Ultimate Combat's sailing ship has them (the deck layout follows UC).
        "about": "a trader: two masts, a deep hold, and a crew who want no trouble",
        "places": (("the deck", "the mainmast, the hatches, and the rail", False),
                   ("below decks", "hammocks, lamplight, and everybody's belongings", True),
                   ("the hold", "the cargo, lashed down and in the way", True),
                   ("the rigging", "up among the sheets, with the deck a long way down",
                    False)),
    },
    "warship": {
        "name": "warship", "price_gp": 25000, "ac": 2, "hp": 175, "save": 7, "speed": 60, "arms": 3,
        "ram": "3d6+12", "squares": 4, "crew": (60, 60), "passengers": 80,
        "about": "built to close with other ships and take them",
        "places": (("the deck", "cleared for action, and the engines on it", False),
                   ("the sterncastle", "high, railed, and where the orders come from",
                    False),
                   ("below decks", "the crew's quarters, and the arms locker", True),
                   ("the hold", "powder, shot, and water in barrels", True)),
    },
    "galley": {
        "name": "galley", "price_gp": 30000, "ac": 2, "hp": 200, "save": 8, "speed": 90, "arms": 4,
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

# How far each vessel goes in a day: Core Rulebook Table 7-9, Mounts and Vehicles (aonprd
# Rules "Movement", Exploration Movement, fetched 2026-11-16): "Sailing ship (sailed) 2
# miles [an hour], 48 miles [a day]"; warship 60, longship 72, galley 96; "for a sailing
# ship, it represents 24 hours". The keelboat is rowed 10 miles in its 10 hours "and can
# also float an additional 14 hours, if someone can guide it, adding an additional 42
# miles" — a passage boat has a crew to guide her, so 52.
#
# Until 2026-11-16 the day was worked out from Ultimate Combat's TACTICAL speed (60 ft a
# round, so 6 mph for 24 hours, 144 miles a day): three times the book's sailing ship, and
# with World Bible's 192-mile crossings it made every sea passage of the shipped worlds a
# day and a half (the owner: "over water it should be a few weeks minimum"). The table is
# the overland rule and the feet are the battle's; UC prints no conversion between them.
MILES_A_DAY: dict[str, int] = {"keelboat": 52, "longship": 72, "sailing ship": 48,
                               "warship": 60, "galley": 96}

# The shortest passage between two settlements, in days, when the world's miles are not
# marked measured (`journey.Leg.measured`). The owner, 2026-11-16: "over land ... it should
# be a few days minimum to other cities and over water it should be a few weeks minimum."
# Two weeks is the app's reading of "a few weeks"; a river runs inside one continent, so
# it takes the road's floor (`journey.ROAD_DAYS_AT_LEAST`). Why a floor and not the miles:
# World Bible's distances are DERIVED from its containment tree and "never measured"
# (World Bible agent_engine/distance.py, its own words), banded in walking days at 24
# miles a day, so its sea band of 192-216 miles is eight or nine days ON FOOT and four by
# the book's sailing ship. for-world-bible ask 31 asks for measured miles at a voyage's
# scale; a world that marks its miles measured is taken at its word.
PASSAGE_DAYS_AT_LEAST = 14

# A cruise (`Engine._cruise`): a ship hunting sails looks each watch, four watches a day —
# the land's rate (Ultimate Wilderness p.127: four checks a day), not a passage's one roll
# a stretch — so a day of it meets something 1 - 0.8^4 = 59% of the time. The cruise runs
# day after day until she meets something or `CRUISE_DAYS` pass (2026-11-16: one day a
# turn was the day-by-day the owner asked to be rid of).
WATCH_MINUTES = 6 * 60
CRUISE_WATCHES = 4
CRUISE_DAYS = 7

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
    # A passage (2026-11-13): the port she put out from, the crossing's length in days,
    # and the clock minute her last sea day was reckoned to — None while she lies at the
    # quay. The wreck's wash-up reads the first two (`wash_up_near`).
    came_from: str = ""
    days_total: int = 0
    sailed_at: int | None = None
    # Who paid for a berth: the refs that come ashore with the party, wherever ashore is.
    passengers: list = field(default_factory=list)
    # A river passage: no storm is rolled on it (the weather table is open water's).
    river: bool = False
    # Where she ties up when `bound_for` is inland (2026-11-15): the port at the foot of
    # the destination's quickest road (`journey.harbour_road`), walked from there. "" when
    # she ties up at `bound_for` itself.
    lands_at: str = ""
    # Whose she is, when she is somebody's in play (2026-11-15, playtest #94): the ref of
    # the PC whose threat or blade made her people yield (`Engine._ship_taken`). "" for a
    # ship that is her owners' still; `_sail` takes a held ship wherever the holder says.
    held_by: str = ""
    # The town her seizure was sworn in, by the master who yielded her (2026-11-16,
    # `Engine._ships_left_settle`): sworn once, whoever answers for her after him.
    sworn: str = ""
    # What her hold carries that is her owners' (`lading`, playtest 2026-11-16 #92): rows
    # of `rules/trade.py`, {"key", "units", "commodity"}. None until she is laden (the
    # first `Engine._keep_vessel`); [] once emptied, or once taken — a prize's cargo moves
    # to `Scene.cargo` as the holder's lots in her hold, where selling it already works.
    cargo: list | None = None

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind, "hp": self.hp,
                "sinking": self.sinking, "crew": self.crew, "at": self.at,
                "bound_for": self.bound_for, "days_left": self.days_left,
                "came_from": self.came_from, "days_total": self.days_total,
                "sailed_at": self.sailed_at, "passengers": list(self.passengers),
                "river": self.river,
                **({"lands_at": self.lands_at} if self.lands_at else {}),
                **({"held_by": self.held_by} if self.held_by else {}),
                **({"sworn": self.sworn} if self.sworn else {}),
                **({"cargo": [dict(x) for x in self.cargo]} if self.cargo is not None
                   else {})}

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
                   days_left=int(d.get("days_left", 0) or 0),
                   came_from=str(d.get("came_from") or ""),
                   days_total=int(d.get("days_total", 0) or 0),
                   sailed_at=(int(d["sailed_at"]) if d.get("sailed_at") is not None
                              else None),
                   passengers=[str(r) for r in (d.get("passengers") or [])],
                   river=bool(d.get("river")), lands_at=str(d.get("lands_at") or ""),
                   held_by=str(d.get("held_by") or ""), sworn=str(d.get("sworn") or ""),
                   cargo=([dict(x) for x in d["cargo"] if isinstance(x, dict)]
                          if isinstance(d.get("cargo"), list) else None))

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

    The kind rides in the id too (`ship-sailing-ship-<hex>`, 2026-11-13), so the rooms of
    a ship are derivable from a place id alone (`rooms_at`) — every caller of
    `places.for_scene` holds a place id and none holds the scene's vessel list.
    """
    digest = hashlib.sha256(f"{port_id}|{kind}|{n}".encode()).hexdigest()[:12]
    return f"ship-{kind.replace(' ', '-')}-{digest}"


def kind_of_id(vessel_id: str) -> str:
    """The kind a vessel id carries, or "" for an id from before kinds were in it."""
    head = str(vessel_id or "")
    if not head.startswith("ship-"):
        return ""
    kind = head[len("ship-"):].rsplit("-", 1)[0].replace("-", " ")
    return kind if kind in VESSELS else ""


def vessel_of(place_id: str) -> str:
    """The vessel id a place id stands on (`{vessel}~deck:{room}`), or ""."""
    from . import places as places_mod

    head = places_mod.location_of(str(place_id or ""))
    return head if head.startswith("ship-") else ""


def rooms_at(place_id: str):
    """The rooms of the ship this place id is aboard, derived from the id; () ashore."""
    vid = vessel_of(place_id)
    kind = kind_of_id(vid)
    if not kind:
        return ()
    return places_of(Vessel(id=vid, name=name_for(vid), kind=kind, hp=VESSELS[kind]["hp"]))


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


# --- what a trader carries ---------------------------------------------------------------
#
# Playtest 2026-11-16 #92: a merchantman taken by threat had nothing in her hold, so a
# Perception roll decided whether the crates in plain sight held anything. A trader's hold
# is laden; what is in it is seen, not searched for.
#
# How much: Skull & Shackles' plunder (The Wormwood Mutiny, as quoted on Paizo's forums;
# the book itself could not be read): a point of plunder is about 1,000 gp of goods and
# takes about 10 tons of hold. A prize of mixed goods runs about 3 points. A keelboat is
# rated one point here, which is this app's call. What the goods are is her home port's own
# trade (`trade.supplied_at`), priced and weighed by the trade table (`trade.ROWS`). Cheap
# goods fill the hold before they reach the value: a grain ship carries grain by the ton,
# not 1,000 gp of it per point.
PLUNDER = {"sailing ship": 3, "keelboat": 1}
PLUNDER_GP = 1000
PLUNDER_LB = 20000
# A port that ships nothing the trade table prices still loads something. These are staples
# from the Core table. Livestock never goes in: a hold of animals needs feeding.
STAPLES = ("wheat", "iron", "linen", "salt", "wool", "cheese")


def lading(vessel_id: str, kind: str, supplies: dict | None = None) -> list[dict]:
    """The cargo a trader of this kind carries out of a port that ships `supplies` ({row:
    the world's word}). One or two rows, seeded off her id like her name, so the same ship
    always carries the same goods. [] for a kind that carries no trade (a warship's hold is
    powder and shot)."""
    from . import trade

    points = PLUNDER.get(kind, 0)
    if not points:
        return []
    supplies = dict(supplies or {})
    rows = [k for k in supplies if k in trade.ROWS and trade.ROWS[k][4] != "livestock"]         or list(STAPLES)
    seed = _seed(f"{vessel_id}|cargo")
    picks = [rows[seed % len(rows)]]
    other = rows[(seed >> 8) % len(rows)]
    if other not in picks:
        picks.append(other)
    out = []
    for key in picks:
        _name, cp, _unit, lb, _kind = trade.ROWS[key]
        units = int(points * PLUNDER_GP * 100 / len(picks) // cp)
        if lb:
            units = min(units, int(points * PLUNDER_LB / len(picks) // lb))
        if units > 0:
            out.append({"key": key, "units": units,
                        "commodity": str(supplies.get(key) or trade.ROWS[key][0])})
    return out


def hold_said(scene, vessel: Vessel) -> tuple[list[str], list[str]]:
    """Everything in her hold, in words ("15000 lb of iron"): (her owners' cargo, the
    party's lots stowed in her — `trade.shipping_in`, a prize's cargo among them), each
    with the world's own name for it when it has one."""
    from . import trade

    def said(lot: dict) -> str:
        words = trade.said({"key": lot["key"], "name": trade.ROWS[lot["key"]][0],
                            "units": lot["units"]})
        own = str(lot.get("commodity") or "")
        return words + (f" ({own})" if own and own.lower() != trade.ROWS[lot["key"]][0]
                        else "")

    theirs = [said(x) for x in (vessel.cargo or ()) if x.get("key") in trade.ROWS]
    ours = [said(x) for x in trade.shipping_in(scene, vessel.id)]
    return theirs, ours


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
             with_the_wind: bool = False, *, measured: bool = False,
             river: bool = False) -> int:
    """How long a passage takes, in days.

    Miles when the world states them, at the vessel's day's run (`MILES_A_DAY`, the CRB's
    Table 7-9). When the world states no distance, the tree's own ordering stands in,
    exactly as it does for a road: two settlements on one continent are nearer than two on
    different ones, whatever the miles turn out to be.

    Never less than the passage floor (`PASSAGE_DAYS_AT_LEAST` at sea, the road's on a
    river) unless the world marked its miles `measured`; never less than a day.
    """
    from . import journey as journey_mod

    per_day = miles_a_day(kind) * (2 if with_the_wind else 1)
    days = (max(1, round(int(miles) / max(1, per_day))) if miles
            else max(1, int(days_apart)))
    if measured:
        return days
    return max(days, journey_mod.ROAD_DAYS_AT_LEAST if river else PASSAGE_DAYS_AT_LEAST)


def leg_days(leg, kind: str) -> int:
    """`days_for` for a journey leg: its miles when stated, its tree days when not, and
    whether the world measured them. The one reading of a leg's days at sea — the booking,
    the exits row and a held ship coming about all ask it."""
    return days_for(leg.miles if leg.source == "exact" else None, kind, leg.days_apart,
                    measured=bool(getattr(leg, "measured", False)),
                    river=getattr(leg, "by", "") == "river")


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


def aboard(scene) -> "Vessel | None":
    """The vessel the party stands on, read from the scene alone, or None ashore."""
    vid = vessel_of(str(getattr(scene, "at", "") or ""))
    for raw in (getattr(scene, "vessels", None) or ()) if vid else ():
        if isinstance(raw, dict) and str(raw.get("id")) == vid:
            return Vessel.from_dict(raw)
    return None


def crew_of(scene, ship) -> list:
    """The people who work her: anybody standing on her rooms who is not a passenger, not
    the party's, not a boarder (`scene.sea["foes"]`), and a person by their stat block
    (`npcs._PEOPLE_TYPES`) — never the creature that came over the rail.

    shortcut: read from where they stand rather than a crew tag laid when they are minted
    (`Engine._ships_company`), so saves from before 2026-11-15 read the same; a tag at
    minting is the upgrade when a ship carries more than her master and a hand."""
    from . import bestiary, npcs, states

    if ship is None or scene is None:
        return []
    rooms = {p.id for p in places_of(ship)}
    boarders = set((getattr(scene, "sea", None) or {}).get("foes") or ())

    def a_person(a) -> bool:
        row = bestiary.raw_block(str(getattr(a, "from_template", "") or "")) or {}
        return row.get("creature_type") in npcs._PEOPLE_TYPES

    return [a for r, a in (getattr(scene, "people", None) or {}).items()
            if a.at in rooms and not a.is_pc and r not in ship.passengers
            and r not in boarders and not a.has_state(states.TRAVELS_WITH_YOU)
            and not a.has_state("state.down.dead") and a_person(a)]


def master_of(crew: list):
    """Who answers for her: the most Hit Dice among her people, the lower ref on a tie."""
    from . import attitude

    return min(crew, key=lambda a: (-attitude._hit_dice(a), a.ref)) if crew else None


def her_waters(world, vessel: Vessel) -> list:
    """The sea and river legs a ship can sail from where she is: from the quay she lies at,
    else from the port she put out from — and, out on a cruise, the way back into that port
    (live 2026-11-16: "bring her back into Mirabalos" had no leg, because the legs from a
    port never lead to itself). The way back is a day: a cruise is a day's sail at most
    from her port (`CRUISE_WATCHES`)."""
    from . import journey as journey_mod

    home = vessel.at or vessel.came_from
    legs = [x for x in journey_mod.legs_from(world, home)
            if x.by_sea or x.by in ("sea", "river")] if home else []
    if not vessel.at and vessel.came_from and not vessel.bound_for:
        town = world.get(vessel.came_from) if world is not None else None
        legs.append(journey_mod.Leg(to_id=vessel.came_from,
                                    to_name=str(getattr(town, "name", "") or "port"),
                                    days_apart=1, by="sea", by_sea=True, to_port=True,
                                    # A day back to her own port is the cruise's own
                                    # reach, not a passage between two settlements: the
                                    # passage floor is not hers.
                                    measured=True))
    return legs


def crewed(vessel: Vessel) -> bool:
    """Whether there are enough hands to work her. A galley wants two hundred; a keelboat
    wants one. A ship below her minimum does not move, which is the quiet reason you
    cannot simply steal a warship."""
    return vessel.crew >= int(vessel.row["crew"][0])


# --- passage: paying for a berth, and the days at sea ------------------------------------------
#
# Owner, 2026-11-13: "make ships boardable and have sea/ocean travel be accessible." A
# passage is bought at a port, the party stands on the deck from then until she makes
# port, and the crossing is reckoned a day at a time so the sea can turn on her.

# "Ship's passage: 1 sp per mile" — Core Rulebook, Table 6-9 Goods and Services, the same
# row as Adventurer's Armory's Transport, Sea table (aonprd, fetched 2026-11-13). Per
# passenger, as every row of that table is; food is the ship's, as a berth's always was.
PASSAGE_CP_PER_MILE = 10

# A day at sea is a whole one (HOURS_AT_SEA): the CRB's sailing ship makes 2 miles an
# hour, 48 miles a day (`MILES_A_DAY`).
MINUTES_A_DAY = 24 * 60


def miles_a_day(kind: str) -> int:
    return int(MILES_A_DAY.get(kind, MILES_A_DAY["sailing ship"]))


def fare_cp(miles: int, heads: int = 1) -> int:
    return max(1, int(miles)) * PASSAGE_CP_PER_MILE * max(1, int(heads))


def passenger_ship(port_id: str, scale: str, river: bool = False) -> "Vessel":
    """The ship a harbourmaster puts a passenger aboard: a sailing ship when one lies here
    (Table 7-49's trader, "a crew who want no trouble"), else the port's first regular
    built for open water. A keelboat is a river boat ("shallow draught and no
    pretensions"), so it carries a passenger to sea only where it is all the port keeps —
    and on a river it is the boat, whatever else lies at the quay.
    """
    if river:
        vid = vessel_id(port_id, "keelboat", 0)
        row = VESSELS["keelboat"]
        return Vessel(id=vid, name=name_for(vid), kind="keelboat", hp=int(row["hp"]),
                      crew=int(row["crew"][0]), at=str(port_id))
    lying = offered_at(port_id, scale, n=3)
    return next((v for v in lying if v.kind == "sailing ship"),
                next((v for v in lying if v.kind != "keelboat"), lying[0]))


# --- the weather at sea ------------------------------------------------------------------------
#
# Researched 2026-11-13, when it was rolled once per day at sea:
#
# - Ultimate Wilderness p.165ff, Table 4-28 (Wind), rolled "for the day's wind": 96–100
#   is a windstorm. A 5% day is the storm a ship has to ride out.
# - Core Rulebook Table 13-9 (Random Weather): 91–99 storm, 100 powerful storm (windstorm,
#   hurricane). One storm in ten is the powerful kind, and that is the one that breaks a
#   ship. So a wreck is 10% of storms.
# - Skull & Shackles' own Shackles weather table (Tempest Rising p.72) could not be
#   read; its numbers are not used and not claimed. Stormwrack (3.5) likewise.
#
# Since 2026-11-16 (travel pacing) a storm is a band of the voyage table (content/rules/
# journey-events.json `sea`, widened by volatility like the other danger bands), not a
# daily roll of its own: a daily 5% beside the stretch check stopped a fortnight's passage
# for weather half the time (1 - 0.95^14 = 51%), the day-by-day the owner asked away.
WRECK_PCT_OF_STORMS = 10


def storm_wrecks(dice) -> bool:
    """Whether a storm a voyage met (the journey table's `storm` band, 2026-11-16) is the
    powerful kind that breaks her: one in ten (CRB Table 13-9)."""
    return dice.roll("1d100", label="how bad the storm is",
                     visibility="hidden").total <= WRECK_PCT_OF_STORMS


# The storm on deck, as the Core Rulebook's Storm entry writes it (Environment,
# Weather): visibility cut by three quarters, "imposing a -8 penalty on Perception
# checks", and "Storms make ranged weapon attacks impossible, except for those using siege
# weapons" (CRB p.438). Both ride one effect that ends with the day: the penalty as its
# modifier, the ranged half as its tag (`states.NO_RANGED_WEAPONS`), which the attack op
# refuses a ranged or thrown weapon under. Spells are not weapon attacks and fly.
STORM_PERCEPTION = -8
STORM_ROUNDS = 24 * 60 * 10


# --- the wreck -----------------------------------------------------------------------------------
#
# Into stormy water and swimming for it. The Swim skill (CRB): stormy water is DC 20, and
# "each hour that you swim, you must make a DC 20 Swim check or take 1d6 points of
# nonlethal damage from fatigue." How many hours to land is the app's (1d4: the wreck is
# within sight of a coast, which is why anybody lives) — no source states it.
WRECK_SWIM_HOURS = "1d4"
# The hourly 1d6 is the Swim skill's, kept once in `water.HOURLY_NONLETHAL`.

# Out to a ship lying off a shore with no docks (owner ruling 2026-11-14). How far off
# she lies is this app's number, not a source's: a cable's length (a tenth of a nautical
# mile, about 600 feet). World Bible ask 22 would make it the world's.
ANCHORED_OFF_FT = 600
# The boat out: Ultimate Equipment p.87 (and CRB p.159), the rowboat, "about 1-1/2 miles
# per hour", holding "two or three Medium passengers", passage 2 cp per mile. A party
# bigger than the boat takes more than one trip; a head pays at least 1 cp.
ROWBOAT_CP_PER_MILE = 2
ROWBOAT_FT_PER_MINUTE = 132          # 1.5 mph
ROWBOAT_HEADS = 3


def rowboat_cp(heads: int, feet: int = ANCHORED_OFF_FT) -> int:
    """The boat out's fare for `heads`, by UE's 2 cp a mile, never under 1 cp a head."""
    return max(1, -(-ROWBOAT_CP_PER_MILE * feet // 5280)) * max(1, int(heads))


def rowboat_minutes(heads: int, feet: int = ANCHORED_OFF_FT) -> int:
    """Minutes until the last of `heads` is aboard: out, and back for the next load."""
    trips = -(-max(1, int(heads)) // ROWBOAT_HEADS)
    return -(-feet // ROWBOAT_FT_PER_MINUTE) * (2 * trips - 1)
# A wreck comes ashore near the end of the crossing she was nearer, most of the time; a
# storm that carries a ship far off her course puts her people somewhere else. The
# share is the app's, stated and not sourced.
WASHED_FAR_PCT = 25
# What the sea takes, a stated house rule (no 1e book prints one): raw materials carried
# loose (herbs, hides, ore — `Actor.inventory`) are soaked through and lost; of the loose
# things the fiction handed over (`Actor.goods`), each kind is lost on a hidden coin toss.
# Coin, and the gear and arms that are worn or kept in the pack, come ashore with you.
GOODS_LOST_PCT = 50


def wash_up_near(vessel: "Vessel") -> str:
    """The settlement nearer the wreck: where she came from in the first half of the
    crossing, where she was going in the second."""
    sailed = max(0, int(vessel.days_total) - int(vessel.days_left))
    if vessel.came_from and sailed * 2 < max(1, int(vessel.days_total)):
        return vessel.came_from
    return vessel.lands_at or vessel.bound_for or vessel.came_from
