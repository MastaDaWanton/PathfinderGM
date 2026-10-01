"""What happens on the way there.

Asked for 2026-09-22, in the player's own words: *"if it is 4 places i move through there
should be some kind of NPC encounter table that rolls for chance encounters, perhaps my
journey is stopped short because as im moving through the streets a child pickpockets me
or I get blocked by a pedestrian squabble. these should not happen every time but
occasionally. the chance should roll for every movement and it should roll on the table
for the respective area im moving through and stop rolling if an encounter hits."*

That is the wandering-monster check, which every tradition has and this app had in exactly
one place: `rules/gathering.py` rolls it once per foraging expedition, because Ultimate
Wilderness says to. Crossing a city — measured below at two to four hops — rolled nothing
at all. This module is the same check for the other two kinds of movement, and the shape
is deliberately gathering's: bands on a d100, the engine's own hidden dice, and a creature
drawn from the shipped bestiary rather than invented.

THE NUMBERS, and where each comes from.

  Published: "check for encounters four times per day — at dawn, noon, dusk and midnight,
  with a 20% chance of an encounter each time" (Archives of Nethys, GM rules, Step 4:
  Create Random Encounter Tables). That is the road's number and it is used verbatim: a
  watch is six hours, and each watch is a 20% check.

  Measured, for the street: across the 76 settlements the two shipped worlds contain,
  10,792 pairs of places have a route between them and the mean route is **2.726 hops**
  (histogram 1:3144, 2:2954, 3:2824, 4:5338; 40 pairs have no route at all). Rolling the
  published 20% per HOP would interrupt 60% of crossings, which is the thing the source
  itself warns about — "too many random encounters can slow down the progression of your
  plot and can frustrate players". So the per-hop chance is set so that a crossing of
  average length comes to the published 20%:

      1 - 0.8 ** (1 / 2.726) = 0.0786

  Eight percent. One step across the square is 8%, a four-hop city crossing is 28%, and
  the longer way across town is genuinely the riskier one, which is the whole reason the
  check is per movement rather than per journey.

THE STREET TABLE is authored to the temper of the AD&D 1e DMG's city encounters, which is
the oldest published version of this table and still the only one that is mostly *not* a
fight: beggars (and its own rule that alms bring nine more), pickpockets, brawls, and the
watch. Four bands in a hundred are somebody who means harm. At 20% a crossing that is
about one street fight in every 125 times you cross town, which is the "occasionally" the
request asked for and is not a number anybody would have arrived at by feel.

Nobody in either table is invented. The street's people are grounded through `npcs.choose`
against the 7,133 loaded stat blocks, the same door `rules/roster.py` uses; the road's are
drawn from the bestiary by the ground's own biome and a CR window around the party, which
is `gathering.creature_for` exactly. A model is never asked who is in the way.

PASSING AND STOPPING (owner's ruling C1, 2026-09-30). "I should be able to go anywhere but
if it would take me through a place the journey through that place should be described and
encounters should roll once for each place and a low chance of encounters stopping the
travel." Until then every hit stopped the walk: replayed on the owner's own save, the
gate → back streets → Velvet Veil walk met something in 23.7% of 300 walks, and every one
of those was a stop. The chance of a meeting is unchanged — one roll per place, at the
measured rate above — and what changed is what most meetings DO:

  passing   told in the hop's line and left behind; nobody is brought into the scene and
            the walk goes on, still rolling for the places after it. The hawker, the
            beggar, the cart in the press, the watch going by a clean (or merely
            suspected) name, travellers on the road, a creature that lets you be.
  stopping  what the code always did: the walk ends at that place and whoever it was is
            there. A squabble blocking the way, a cutpurse, trouble, the watch for a
            WANTED name, a creature that comes at you, weather, and a toll (a toll is a
            decision, pay or go round, and a toll that let you by would be no toll).

Sources. Pathfinder 2e's hexploration rolls one check a day and, when it hits, rolls the
kind: "Harmless" 1–5, "Hazard" 6–7, "Creature" 8–10 (Gamemastery Guide, Random Encounters,
2e.aonprd.com/Rules.aspx?ID=3114) — half of everything met is harmless, which is the shape
here. Necropraxis's "Overloading the encounter die" (necropraxis.com/2014/02/03/
overloading-the-encounter-die/) rolls once per area entered and makes most faces something
other than a fight — a percept, a spoor, a sign that something is near — which is what a
passing meeting is: it happened, it is told, it does not take the turn. And Inform's
*Approaches* (GO TO a known room, walked in one command, stopped only by the rules) is the
walk this all happens on. The target the plan set was "about 8–10% stopping on a 3-hop
walk"; `test_on_the_way.py` measures it over 300 seeded walks.

To land there the street table moved five points from the press to the squabble (press
1–17, squabble 18–42): with the squabble, the cutpurse and trouble stopping a clean name,
39% of hits stop — 8% × 39% = 3.1% a hop, 1 − 0.969³ = 9.1% on three hops; a wanted name,
whom the patrol also stops, 53% of hits and 12.0%. Measured over 300 seeded three-hop
walks (seeds 0–299): 24 stopped, 8.0%, against 66 that met anything (22%); with the old
bands and every meeting a stop, those 66 were all stops. The violence band (trouble, 4 in
100) is untouched. (Over the same seeds the 2-point move gave 7.7% — the low edge of the
plan's target — which is why it is five.)
"""
from __future__ import annotations

from dataclasses import dataclass

from . import npcs

# The published road check, unchanged: four a day, 20% each (AoN, Step 4: Create Random
# Encounter Tables). Six hours is a watch, so an eight-hour walking day is one full check
# and part of a second — which is right, because the other sixteen hours are camp and the
# camp has its own machinery in `survival`.
WATCH_HOURS = 6
ROAD_PERCENT = 20

# The street, derived above from the road's number and the measured route length.
STREET_PERCENT = 8

# The bands, low to high, on a d100 rolled only once the check above has already hit.
#   key, hi, who they are (words `npcs.choose` grounds against), how many
STREET = (
    ("press", 17, ("drover", "carter", "laborer"), 1),
    ("squabble", 42, ("commoner", "townsfolk"), 2),
    ("hawker", 58, ("peddler", "merchant", "trader"), 1),
    ("beggar", 72, ("beggar", "commoner"), 1),
    ("patrol", 86, ("guard", "watch"), 2),
    ("cutpurse", 96, ("urchin", "thief", "rogue"), 1),
    ("trouble", 100, ("thug", "bravo", "footpad"), 1),
)

# The road's four bands. Two of them are people or things; two of them are the road
# itself, and both of those were added only once there was something real behind them —
# an authored line with no teeth is worse than no line, which is why the table shipped
# with two bands and a note rather than four and a bluff.
#
#   creature     what the ground actually holds, from the bestiary
#   travellers   people using the same road you are
#   weather      the road turns against you: hours the clock and the body both pay
#   toll         somebody is charging for the crossing, and the coin is the player's to
#                hand over — a `give`, never a deduction the engine makes for them
ROAD = (
    ("creature", 45),
    ("travellers", 75),
    ("weather", 90),
    ("toll", 100),
)

# What weather costs when it stops you: hours spent going nowhere, charged to the body
# like any other hours on the road. Two to five, so it is a lost afternoon and never a
# lost week.
WEATHER_HOURS = "1d4+1"

# What a crossing costs, in copper. A toll is small: the point of it is the decision,
# not the sum.
TOLL_DICE = "2d10+20"

# Creature types that come at you on sight, and the CR window around the party. Both are
# `gathering`'s, named here rather than imported so that changing the foraging table does
# not silently change what walks up to you on a road.
AGGRESSIVE = frozenset({"animal", "vermin", "magical beast", "ooze", "plant"})
BELOW, ABOVE = 2, 1

# What the cutpurse is trying: "Sleight of Hand DC 20 to lift a small object from another
# person", opposed by the mark's Perception (Core Rulebook, Sleight of Hand). The thief
# rolls, the mark rolls, and the coin only moves when the thief wins — there is no flat
# chance anywhere in this.
LIFT_DC = 20
# How much a street thief gets: a handful of small coin, not the purse. Twelve to thirty
# copper, which is a couple of silver — enough to be worth saying and never enough to be
# the reason a character cannot buy armour.
LIFT_DICE = "2d10+10"


@dataclass(frozen=True)
class Meeting:
    """Somebody, or something, between you and where you were going."""

    kind: str
    roll: int
    words: tuple[str, ...] = ()
    count: int = 1
    template: str = ""
    creature: dict | None = None
    aggressive: bool = False
    # Which hop, or which watch, it happened on. The caller stops there.
    after: int = 0


def _band(table, roll: int) -> str:
    for key, hi, *_ in table:
        if roll <= hi:
            return key
    return table[-1][0]


def street(dice, level: int = 1) -> Meeting | None:
    """One hop of a town. None most of the time, which is the point.

    Two rolls and not one: the check decides *whether*, the table decides *what*. Kept
    apart because they answer to different sources — the chance is derived from a
    published rate and a measurement, and the table is authored — and a single d100 with
    the quiet band at the bottom would have tangled them into one number nobody could
    argue with separately.
    """
    if dice.roll("1d100", label="the street", visibility="hidden").total > STREET_PERCENT:
        return None
    r = dice.roll("1d100", label="who is in the way", visibility="hidden").total
    kind = _band(STREET, r)
    row = next(x for x in STREET if x[0] == kind)
    got = npcs.choose(list(row[2]), max(1, int(level or 1))) or {}
    return Meeting(kind=kind, roll=r, words=row[2], count=row[3],
                   template=str(got.get("id") or "guildhand"),
                   aggressive=(kind == "trouble"))


def road(dice, hours: int, biome: str, level: int = 1, *,
         minutes: int | None = None) -> Meeting | None:
    """The march, checked once a watch until something happens or the road runs out.

    Stops rolling at the first hit, as asked, which is also what the published procedure
    does with a day's four checks in practice: the party is no longer travelling.

    `minutes` is a step shorter than an hour — a half-mile hop between the outskirts and
    the fields (`rules/outskirts.py`) — checked at its share of a watch, never less than
    one in a hundred.
    """
    from . import bestiary

    # A part-watch gets a part-share of the check, pro rata. The alternative — rounding
    # every stub of a walk up to a whole watch — makes stepping outside the walls for an
    # hour as dangerous as a dawn-to-noon march, and that step is the most common move
    # in the game: `_op_travel` charges exactly one hour for it.
    if minutes is not None:
        shares = [max(1, round(ROAD_PERCENT * max(0, int(minutes))
                               / (WATCH_HOURS * 60)))]
    else:
        full, rest = divmod(max(0, int(hours)), WATCH_HOURS)
        shares = [ROAD_PERCENT] * full
        if rest or not full:
            shares.append(max(1, round(ROAD_PERCENT * (rest or int(hours)) / WATCH_HOURS)))
    for w, chance in enumerate(shares, start=1):
        if dice.roll("1d100", label="the road", visibility="hidden").total > chance:
            continue
        r = dice.roll("1d100", label="what is on the road", visibility="hidden").total
        kind = _band(ROAD, r)
        if kind == "creature":
            low = max(1 / 3, int(level or 1) - BELOW)
            high = max(1, int(level or 1) + ABOVE)
            rows = [x for x in bestiary.search(biome=biome, cr_min=low, cr_max=high,
                                               limit=400)
                    if x.get("cr_value") is not None]
            if rows:
                pick = dice.roll(f"1d{len(rows)}", label="what lives out here",
                                 visibility="hidden").total
                row = rows[pick - 1]
                return Meeting(kind="creature", roll=r, creature=row,
                               template=str(row.get("id") or ""),
                               count=1, after=w,
                               aggressive=row.get("creature_type") in AGGRESSIVE)
            # Ground the book does not stock still has a road through it, and the
            # check HIT: what is met is other travellers, never a None that would
            # make a hit say nothing (`test_ground_the_book_does_not_stock_is_not_
            # silently_empty`). This comment said the opposite until 2026-09-23.
            kind = "travellers"
        if kind == "weather":
            # Nobody arrives. The road itself is the meeting, so no template is drawn
            # and the caller brings nobody in.
            return Meeting(kind="weather", roll=r, count=0, after=w)
        if kind == "toll":
            got = npcs.choose(["toll", "guard", "warden"],
                              max(1, int(level or 1))) or {}
            return Meeting(kind="toll", roll=r, words=("toll-keeper", "warden"),
                           count=1, template=str(got.get("id") or "guildhand"), after=w)
        got = npcs.choose(["merchant", "guard", "traveler"],
                          max(1, int(level or 1))) or {}
        return Meeting(kind="travellers", roll=r, words=("merchant", "guard"), count=2,
                       template=str(got.get("id") or "guildhand"), after=w)
    return None


def night(dice, hours: int, biome: str, level: int = 1, *,
          scale: float = 1.0) -> Meeting | None:
    """The camp's check, watch by watch over the hours slept: the road's own procedure
    ("four times per day ... with a 20% chance of an encounter each time"), because a
    night in the open is the sixteen hours this module's road check leaves to the camp.

    Asked for 2026-10-01 — "a tent should decrease the chance of being attacked in my
    sleep" — and until then there was nothing to decrease: `rest` rolled no check at all,
    so a night on the open ground was as safe as one in the inn. `scale` is what the
    camp's gear multiplies each watch's chance by (a tent's row in content/rules/
    gear.json: one half), never below one in a hundred.

    Only the creature band is drawn at night. Travellers, a toll and the weather are the
    road's: nobody collects a toll at a sleeping camp, and what the weather does to a
    sleeper is the cold rule's. A watch that hits on ground the bestiary does not stock
    meets nothing — a quiet night, not travellers in the dark."""
    from . import bestiary

    full, rest = divmod(max(0, int(hours)), WATCH_HOURS)
    shares = [ROAD_PERCENT] * full
    if rest or not full:
        shares.append(max(1, round(ROAD_PERCENT * (rest or int(hours)) / WATCH_HOURS)))
    shares = [max(1, round(s * float(scale))) for s in shares]
    for w, chance in enumerate(shares, start=1):
        if dice.roll("1d100", label="the night", visibility="hidden").total > chance:
            continue
        low = max(1 / 3, int(level or 1) - BELOW)
        high = max(1, int(level or 1) + ABOVE)
        rows = [x for x in bestiary.search(biome=biome, cr_min=low, cr_max=high, limit=400)
                if x.get("cr_value") is not None]
        if not rows:
            return None
        pick = dice.roll(f"1d{len(rows)}", label="what lives out here",
                         visibility="hidden").total
        row = rows[pick - 1]
        return Meeting(kind="creature", roll=chance, creature=row,
                       template=str(row.get("id") or ""), count=1, after=w,
                       aggressive=row.get("creature_type") in AGGRESSIVE)
    return None


def hours_walked(meeting: "Meeting | None", hours: int) -> int:
    """How far along the road the party got before it stopped.

    A watch is six hours and the check is made at its end, so a hit on watch two is
    twelve hours of road behind them — capped at the whole journey, since the last watch
    of a march is usually a part-watch.
    """
    if meeting is None or not meeting.after:
        return int(hours)
    return min(int(hours), int(meeting.after) * WATCH_HOURS)


# Why each kind of stop is a stop, in a clause. Said beside who it was (`describe`'s
# `who`), because a tell that says only "You get no further" left the prose free to turn
# the stop into scenery: on 2026-09-28 the patrol that stopped Bobby at the way in came
# back as "the watchmen are making their rounds" (docs/playtest-2026-09-28.md, 16).
WHY = {
    "press": "the cart is across the way and will not shift",
    "squabble": "the crowd round them will not part",
    "hawker": "they want a sale out of you",
    "beggar": "they want alms",
    "patrol": "they are looking at faces, yours among them",
    "cutpurse": "they want your purse",
    "trouble": "they were waiting for somebody, and you will do",
    "travellers": "they have stopped where you are",
    "toll": "they want paying before you pass",
    "creature": "it is in the way",
}


def _names(who) -> str:
    who = [str(w) for w in (who or ()) if str(w)]
    if len(who) <= 1:
        return "".join(who)
    return ", ".join(who[:-1]) + " and " + who[-1]


# The kinds that are told and left behind (owner's ruling C1; the module docstring says
# why each side is where it is). The patrol and the creature are each one or the other by
# what the engine knows: the warrant, and whether the creature is one that comes at you.
PASSING = frozenset({"press", "hawker", "beggar", "travellers"})


def stops(meeting: Meeting, law: str = "") -> bool:
    """Does this meeting end the walk where it happened? `law` is the town's standing
    with the walker (`states.standing_with_the_law`): only a WANTED name is stopped by
    the watch; a suspected one is looked at twice and let by, as at the gate."""
    if meeting.kind == "patrol":
        return law == "wanted"
    if meeting.kind == "creature":
        return bool(meeting.aggressive)
    return meeting.kind not in PASSING


def passing(meeting: Meeting, where: str = "", law: str = "") -> str:
    """The sentence for a meeting the walk goes on through, said as part of that hop.

    In the engine's voice and naming nobody, like the stopping sentences: nobody is
    brought into the scene for it, so there is nobody to name, and the narrator is told
    in so many words that the walk went on — "you walk on" — so the prose cannot make it
    the stop it is not."""
    at = f"At {where}, " if where else ""
    if meeting.kind == "press":
        lead = "a cart is across the way and a drover is arguing with it"
        tail = "you squeeze past it and walk on"
    elif meeting.kind == "hawker":
        lead = "somebody decides you are buying and walks beside you a while"
        tail = "they give up, and you walk on"
    elif meeting.kind == "beggar":
        lead = "a hand comes out, and the mouth above it knows your face is new"
        tail = "you are past it before the asking is done"
    elif meeting.kind == "patrol":
        lead = "the watch comes by, two of them, looking at faces"
        tail = ("one of them looks at yours twice, and lets you go on"
                if law == "suspected" else "they go on their way, and so do you")
    elif meeting.kind == "travellers":
        lead = "there are others on the road"
        tail = "you pass them, and walk on"
    elif meeting.kind == "creature" and meeting.creature:
        name = str(meeting.creature.get("name") or "something")
        article = "an" if name[:1].lower() in "aeiou" else "a"
        lead = f"{article} {name} is near the way"
        tail = "it lets you pass, and you walk on"
    else:
        return ""
    sentence = f"{at}{lead}; {tail}."
    return sentence[:1].upper() + sentence[1:]


# The stop's last words, said only where the walk was cut short. A meeting on the LAST hop
# happened at the destination, and "You get no further" there told the player they had
# not arrived where they had: 24 of the 71 stops in the item-9 replay (300 walks to the
# Velvet Veil) fell on that last hop.
NO_FURTHER = " You get no further."


def describe(meeting: Meeting, where: str = "", law: str = "", who=(),
             arrived: bool = False) -> str:
    """The tell's clause: what stopped you, and — when the caller knows them — who.

    `who` is the names of the people the engine just brought in for this meeting. With
    them the tell ends "Stopped by Guard and second Guard: they are looking at faces", so
    a stop names who and why and cannot be read as background.

    `arrived` is a meeting at the place the walk was going to: it is said, and who is
    there is said, but nobody was stopped from getting anywhere.
    """
    said = _describe(meeting, where, law)
    if arrived and said.endswith(NO_FURTHER):
        said = said[:-len(NO_FURTHER)]
    names = _names(who)
    if said and names and meeting.kind in WHY:
        said += (f" Met there by {names}: {WHY[meeting.kind]}." if arrived else
                 f" Stopped by {names}: {WHY[meeting.kind]}.")
    return said


def _describe(meeting: Meeting, where: str = "", law: str = "") -> str:
    """The tell's clause: what stopped you, in the engine's own voice.

    `law` is what this town's watch holds against the player (`states.standing_with_the_law`),
    and only the patrol band reads it: a warrant changes what meeting the watch IS.

    The people are named as what they are and not by name — the engine has just created
    them and the narrator is the one who gets to introduce them. What this sentence owes
    the player is the mechanical fact: the walk ended here, and this is why.
    """
    at = f" at {where}" if where else ""
    if meeting.kind == "press":
        return (f"The way is blocked{at}: a cart across the road and a drover arguing "
                f"with it. You get no further.")
    if meeting.kind == "squabble":
        return (f"Two of them are going at each other in the middle of the road{at}, and "
                f"the crowd has stopped to watch. You get no further.")
    if meeting.kind == "hawker":
        return (f"Somebody has decided you are buying{at} and has stepped into your "
                f"path to prove it. You get no further.")
    if meeting.kind == "beggar":
        return (f"A hand comes out{at}, and the mouth above it knows your face is new. "
                f"You get no further.")
    if meeting.kind == "patrol":
        # The watch reads the warrant, which is the one thing this band was missing when
        # it shipped: a wanted character met the patrol, was told they were looking at
        # faces, and nothing followed. The gate is still where a warrant is ENFORCED
        # (docs/wanted.md, reader one) — this is the second reader, and what it adds is
        # that the street stops being safe once your name is on the list.
        if law == "wanted":
            return (f"The watch comes down the road{at}, two of them, looking at faces "
                    f"— and they have yours. They are coming straight for you.")
        if law == "suspected":
            return (f"The watch comes down the road{at}, two of them, looking at faces. "
                    f"One of them looks at yours twice. You get no further.")
        return (f"The watch comes down the road{at}, two of them, looking at faces. "
                f"You get no further.")
    if meeting.kind == "cutpurse":
        return f"Somebody comes in hard against your side{at}."
    if meeting.kind == "trouble":
        return (f"Somebody has been waiting for somebody, and you will do{at}. "
                f"You get no further.")
    if meeting.kind == "creature" and meeting.creature:
        name = str(meeting.creature.get("name") or "something")
        article = "an" if name[:1].lower() in "aeiou" else "a"
        return (f"The road is not empty: {article} {name} is on it, and it has seen you."
                if meeting.aggressive else
                f"The road is not empty: {article} {name} is on it, and it has not moved.")
    if meeting.kind == "travellers":
        return "There are others on this road, and they have stopped where you are."
    if meeting.kind == "weather":
        return ("The road turns against you — there is no walking through this. You "
                "get off it and wait.")
    if meeting.kind == "toll":
        return ("Somebody is charging for this crossing, and they are standing in the "
                "middle of it. Pay them or find another way.")
    return ""
