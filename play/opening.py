"""Where a game starts, and the first thing the player reads.

The old opening was one hard-coded sentence about a shut guild yard after dark, in a
town named in the source. It was written for the fixture's rogue and it told everyone
else the same thing: a wizard, a paladin and a Blood Bender all began the game at
night outside the same locked gate with nothing to do.

Three things changed, and the third is the constraint the other two answer to.

**It reads off any world.** Nothing here names a place, a people or a faction. The
starting settlement is *found* — the smallest inhabited thing the export describes —
and every fact is read by key with a fallback, because a world written by a different
run of World Bible will not carry the same fact names. A world that describes almost
nothing still produces a coherent opening; it is simply shorter.

**It is rolled.** `SITUATIONS` is a table and the game rolls on it, the same as
anything else the app decides. Seeded from the campaign, so the opening is stable for
a given game and different between games.

**It puts the player somewhere alive.** Every situation is daylight or lamplit
evening, among people, doing something ordinary — a market, a queue, a meal, a work
yard. None of them is a locked door at midnight. A game that opens on somebody with
nothing to do and no one to talk to has to be rescued by its first turn.

Only common nouns appear in the table — bread, a bucket, a doorway. Inventing a
proper noun here would be the app putting a place into the world that World Bible
never wrote, which is the failure `CLAUDE.md` files under "ground every name".
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rules.dice import Dice

# Fact keys carry different names between exports, so everything is looked up through a
# list of candidates and may legitimately find nothing.
LOOK_KEYS = ("Architecture", "Terrain", "Geography", "Landscape")
LIFE_KEYS = ("Urban Life", "Daily Norms", "Daily Life", "Culture", "Customs")
ORDER_KEYS = ("Social Classes", "Governance", "Formal Power", "Administration")
STRAIN_KEYS = ("Tension", "Conflict", "Volatility", "Shadow Power")
SETTLEMENT_KINDS = ("CITY", "TOWN", "SETTLEMENT", "VILLAGE")
SETTLEMENT_SCALES = ("hamlet", "village", "town", "city", "district", "quarter")

# Premise keys that describe the *writing*, not the world. The shipped export carries
# `tone: Evocative`, and a character does not know that they live somewhere evocative —
# it turned up in the opening as a thing everybody here takes for granted.
META_PREMISE = ("tone", "style", "voice", "genre", "mood", "register", "pov",
                "perspective", "prose", "format")


@dataclass(frozen=True)
class Situation:
    """One way a life is being lived when the game picks it up."""
    when: str
    where: str
    doing: str
    # An ordinary person already there, so the first turn has someone to talk to.
    # The name is a common noun; the template is a stat block that ships.
    who: str
    template: str = "guildhand"


# Deliberately ordinary. The player can go looking for trouble — the point is that
# trouble is not the only thing on offer in the first sentence.
SITUATIONS: tuple[Situation, ...] = (
    Situation("Mid-morning", "in the market row, where the awnings are still going up",
              "You are haggling over yesterday's bread, and losing.",
              "the woman at the bread stall"),
    Situation("Just past noon", "in a crowded common room at the height of the meal",
              "You have a bowl in front of you and half of it left.",
              "the man clearing the next table"),
    Situation("Late afternoon", "in a work yard, loud with somebody else's trade",
              "You are waiting on a job of work, and have been waiting a while.",
              "the foreman with the tally board"),
    Situation("Early evening", "at a well-head where the queue has turned to gossip",
              "You are third in line with an empty bucket.",
              "the old man ahead of you"),
    Situation("Morning", "on the road in, under the gate, in the day's first crowd",
              "You are arriving on foot with the dust of the road still on you.",
              "the watchman waving traffic through", "watchman"),
    Situation("Midday", "in a public square where something is being read aloud",
              "You have stopped to listen along with everybody else.",
              "the crier working through the notices"),
    Situation("Afternoon", "in a lane of open workshop doors",
              "You are watching a thing being made that you half know how to make.",
              "the apprentice minding the door"),
    Situation("Evening", "in a lit doorway with a room's noise behind it",
              "You have just come in out of the weather and not sat down yet.",
              "the servant carrying jugs two at a time"),
    Situation("Mid-morning", "in a yard of carts being loaded for somewhere else",
              "You are counting the carts, and wondering.",
              "the drover checking his harness"),
    Situation("Late morning", "on a step in the sun where people have stopped to eat",
              "You are halfway through something bought from a stall.",
              "the stranger sharing the step"),
    Situation("Dusk", "at a crossing thick with people heading home",
              "You are going against the flow of everyone else.",
              "the lamplighter starting his round", "watchman"),
    Situation("Morning", "at a gathering for one of the regular public rituals",
              "You are standing where you are expected to stand.",
              "the neighbour beside you who knows the words"),
)


def _first_fact(place, keys) -> str:
    for key in keys:
        found = (place.fact(key, "") or "").strip() if place is not None else ""
        if found:
            return found
    return ""


def starting_place(world):
    """The smallest inhabited place the export describes, or nothing.

    Found rather than named. The previous code held a literal entity id from the
    fixture, so every other world started nowhere and the opening said so.
    """
    people_places = [
        e for e in world.entities.values()
        if e.kind in SETTLEMENT_KINDS
        or (e.scale or "").lower() in SETTLEMENT_SCALES
    ]
    if people_places:
        # The best-described one, not the smallest. Ranking by scale picked whichever
        # hamlet sorted first and started the game somewhere the export had nothing to
        # say about; the place the world's author wrote the most about is the place a
        # game has the most to draw on.
        def described(e):
            return (len(e.facts), len(e.sections), len(e.summary or ""))
        return sorted(people_places, key=lambda e: (described(e), e.name),
                      reverse=True)[0]
    other = [e for e in world.entities.values() if e.kind not in ("WORLD",)]
    return other[0] if other else None


def roll(campaign_id: str, seed: int | None = None) -> Situation:
    """Roll the opening.

    Taken by id rather than by campaign because the scene is built before the campaign
    object exists, and the person the opening puts beside the player has to be the
    person actually standing in the scene. Two different answers there would be a
    guildhand on a gate the prose never mentions — which is what the fixture's opening
    used to do to every other world.
    """
    picked = seed if seed is not None else _seed_from(campaign_id)
    roll_result = Dice(picked).roll(f"1d{len(SITUATIONS)}", visibility="hidden")
    return SITUATIONS[roll_result.total - 1]


def situation_for(campaign) -> Situation:
    return roll(campaign.id, campaign.seed)


def _seed_from(text: str) -> int:
    """A stable number from a campaign id. `hash()` is salted per process in Python and
    would hand the same campaign a different opening on every restart."""
    total = 0
    for ch in text or "":
        total = (total * 131 + ord(ch)) % 1_000_003
    return total


def _sentence(text: str) -> str:
    """A fact is a fragment — "Winged nobility, merchant castes, and artisan guilds" —
    and pasting fragments together makes a list, not prose. Each is closed off as its
    own statement instead, which reads honestly and never claims a link the export did
    not draw."""
    text = " ".join(str(text or "").split()).rstrip(" .;,")
    if not text:
        return ""
    return text[0].upper() + text[1:] + "."


def _clause(text: str) -> str:
    """A fact as one item in a litany: trailing punctuation removed, nothing else.

    The case is left exactly as the export wrote it. Lower-casing the first letter
    read better on "Ringworld" and turned "Khy'vyr-centric clans" into "khy'vyr-centric
    clans" — the app quietly restyling one of the world's own names, which is the
    opposite of grounding them. A capital mid-list is a much smaller cost than a
    people whose name this app spells differently from every other page in it.
    """
    return " ".join(str(text or "").split()).rstrip(" .;,")


def what_you_know(world, place) -> str:
    """The world as this character knows it: the premise, then the place's own order.

    Everything a person raised here would take for granted, and nothing else — no
    plot, no secret, no hook. What they know, not what is about to happen to them.
    """
    known = [_clause(v) for k, v in (world.premise or {}).items()
             if str(v).strip() and str(k).strip().lower() not in META_PREMISE]
    for keys in (ORDER_KEYS, LIFE_KEYS):
        fact = _first_fact(place, keys)
        if fact:
            known.append(_clause(fact))
    known = [k for k in known if k]
    if not known:
        return ""
    body = "; ".join(known)
    strain = _first_fact(place, STRAIN_KEYS)
    tail = (f" You have grown up knowing better than to say the next part at table: "
            f"{_clause(strain)}.") if strain else ""
    return f"What you know, the way anyone born to it knows it: {body}.{tail}"


def who_you_are(pc, standing: str) -> str:
    """Name and calling first, then where that leaves you here.

    The standing already carries an em dash — "Zhilakai — flightless, in a city whose
    nobility is not" — so folding the class in with another one gave a sentence with
    two of them and no main clause.
    """
    kind = " ".join((pc.char_class or "").split()).strip()
    line = f"You are {pc.name}"
    if kind:
        line += f", {_article(kind)} {kind}"
    standing = " ".join((standing or "").split()).rstrip(".")
    return f"{line}. {standing[0].upper() + standing[1:]}." if standing else f"{line}."


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def compose(campaign, standing: str) -> str:
    """The opening the player reads, in four beats: the world as they know it, where
    they are standing, who they are, and what they are in the middle of doing."""
    world, place, pc = campaign.world, campaign.location, campaign.scene.pc()
    here = situation_for(campaign)

    where = (f"{here.when} in {place.name}." if place is not None else f"{here.when}.")
    where += f" You are {here.where}."
    look = _first_fact(place, LOOK_KEYS)
    if look:
        where += f" Around you: {_clause(look)}."

    parts = [p for p in (
        what_you_know(world, place),
        where,
        who_you_are(pc, standing),
        f"{here.doing} {_sentence(here.who)[:-1]} is close enough to speak to."
        f"\n\nWhat do you do?",
    ) if p]
    return "\n\n".join(parts)


# World-agnostic undercurrents, for a world that ships no unwritten hooks. Shapes, not
# stories: each names a tension the GM can hang anything local on, and none names a
# person or place the world would have to contain.
UNDERCURRENTS = [
    "An old debt in this place is being called in, and the collector is not patient.",
    "Something that should have arrived days ago has not, and people who know are "
    "starting to change their routines.",
    "Two people who publicly cooperate are privately at war, and each is recruiting.",
    "A recent death everyone calls natural was not, and one person here knows it.",
    "Somebody powerful is quietly selling what is not theirs to sell.",
    "A stranger has been asking questions about the player's kind of person.",
    "The cheapest goods in the market are cheap for a reason nobody says aloud.",
    "An institution here is weeks from failing, and its keepers are hiding it.",
    "Someone is leaving, soon and secretly, and needs one thing before they go.",
    "What was stolen last season is about to resurface in the wrong hands.",
]


def hook_texts(world) -> list[str]:
    """The world's own unwritten hooks, as sentences.

    The export's shape: {"name": "Kaelvyr", "kind": "CHARACTER", "why": "Nirkor
    engineer who discovered the hidden vein of salt"}. The `why` is the hook; the name
    alone is just a stranger. One parser for the two readers — the opening roll and
    the event watcher — because a rule with two copies is how the stale one ships.
    """
    hooks = []
    for u in getattr(world, "unwritten", None) or []:
        if isinstance(u, dict):
            name = str(u.get("name") or "").strip()
            why = str(u.get("why") or u.get("text") or u.get("hook") or "").strip()
            text = f"{name} — {why}" if name and why else (why or name)
        else:
            text = str(u)
        if text and text.strip():
            hooks.append(text.strip())
    return hooks


def undercurrent(world, seed: int | None = None) -> str:
    """The campaign's live thread, rolled once at the start.

    The world's own `unwritten` hooks first — they are exactly this, authored by the
    world's generator and reaching nothing until now — and the agnostic table only
    when the export ships none. Seeded from the campaign seed so a rerolled campaign
    is a genuinely different evening.
    """
    d = Dice(seed=seed)
    pool = hook_texts(world) or UNDERCURRENTS
    return pool[d.roll(f"1d{len(pool)}").total - 1] if pool else ""


# The GM's private note: how the undercurrent rides in `history`. One writer at the
# start (`new_campaign`) and one rewriter forever after (`gm/watcher.py`), and both
# must produce byte-identical framing or the prefix search finds two notes where the
# rule says one.
NOTE_PREFIX = "(The GM's private note"

_NOTE_BODY = re.compile(
    r"for this campaign:\s*(.*?)\s*The player does not know this", re.S)


def private_note(thread: str) -> str:
    return (f"(The GM's private note for this campaign: {thread} The "
            f"player does not know this. Let it surface in small ways; "
            f"never announce it.)")


def note_thread(content: str) -> str:
    """The thread back out of the note's framing, or ""."""
    m = _NOTE_BODY.search(str(content or ""))
    return m.group(1).strip() if m else ""
