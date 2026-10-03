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
from dataclasses import dataclass, replace

from rules import states
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
    # Something already in motion, seen from where the player stands and not
    # explained. Dungeon World's first-session rule is "start the session with a
    # group of player characters in a tense situation" (SRD, "First Session"), and
    # Nelson's overture has to say "what is going on" as well as who and where.
    # Unexplained on purpose: the turn that asks about it is the player's, and the
    # GM's private note is what the answer is drawn from.
    edge: str = ""
    template: str = "guildhand"
    # Why the character came here today. The oldest finding in interactive fiction,
    # re-found at this table on 2026-09-05 ("hardly even know what i am supposed to be
    # doing"): Emily Short's answer to an opening whose goal "is not sufficiently
    # obvious" is "an obvious starting problem, even if it's not the main goal of the
    # game". Concrete, small, and the character's own; the world's story arrives on
    # top of it.
    errand: str = ""
    # --- a start document's (rules/openings.py), all defaulted so the legacy table
    # above reads exactly as it did ---------------------------------------------------
    # How the person beside you is seen, kept OUT of their name. Item 4b, 2026-09-28:
    # "the watchman waving traffic through" was the watchman's name on the panel, and
    # the face check keyed him on "through".
    look: str = ""
    kind: str = ""
    # The document's hand-off as (key, value) pairs — a tuple, so a Situation stays
    # hashable like every other frozen record here; `dict(s.hand_off)` reads it.
    hand_off: tuple = ()
    # The sentence the opening stops on, where the player takes over (Blades' "first
    # serious obstacle"; the cage owner who steps back where the Heal check begins).
    moment: str = ""
    start_id: str = ""
    suggestions: tuple = ()
    # The part they play ("the cage owner") when `who` is a world name, and what they
    # say to the player first.
    label: str = ""
    says: str = ""
    # The legacy table's own answer to a start document's `where.kinds`: the kinds of
    # place (`rules/openings._kind_labels` vocabulary) its words are set in, so the party
    # is stood in one (`play/campaign.new_campaign`). Empty: no settlement kind fits.
    kinds: tuple = ()


# The hour each opening's `when` names, for the world clock. Until 2026-09-27 every game
# began at clock 0, which the app reads as midnight (the crafting bench's night is dusk to
# dawn), under an opening that said "Mid-morning, in the market row" — harmless while
# nothing read the hour, and wrong once the market's counter kept hours and townsfolk kept
# a day (rules/keepers.py, rules/residency.py).
_HOUR_OF = {"morning": 8, "mid-morning": 10, "late morning": 11, "just past noon": 13,
            "midday": 12, "afternoon": 14, "late afternoon": 16, "early evening": 18,
            "evening": 19, "dusk": 19}
OPENING_HOUR = 10


def hour_of(when: str) -> int:
    """The clock hour an opening's `when` means; mid-morning for one the table lacks."""
    return _HOUR_OF.get(" ".join(str(when or "").lower().split()), OPENING_HOUR)


# Deliberately ordinary. The player can go looking for trouble — the point is that
# trouble is not the only thing on offer in the first sentence.
SITUATIONS: tuple[Situation, ...] = (
    Situation("Mid-morning", "in the market row, where the awnings are still going up",
              "You are haggling over yesterday's bread, and losing.",
              "the woman at the bread stall",
              "Two stalls down, a trader has started packing up again, and the ones "
              "either side of her are watching rather than asking."),
    Situation("Just past noon", "in a crowded common room at the height of the meal",
              "You have a bowl in front of you and half of it left.",
              "the man clearing the next table",
              "The clatter nearest the door has died, and the hush is spreading inward "
              "one table at a time."),
    Situation("Late afternoon", "in a work yard, loud with somebody else's trade",
              "You are waiting on a job of work, and have been waiting a while.",
              "the foreman with the tally board",
              "Work has stopped at the far end of the yard. The men there are standing "
              "about, facing the gate, not talking."),
    Situation("Early evening", "at a well-head where the queue has turned to gossip",
              "You are third in line with an empty bucket.",
              "the old man ahead of you",
              "The queue has stopped moving. Whatever is being said at the front of it "
              "is not being repeated back down the line."),
    Situation("Morning", "on the road in, under the gate, in the day's first crowd",
              "You are arriving on foot with the dust of the road still on you.",
              "the watchman waving traffic through",
              "A cart has been pulled out of the line and left standing against the "
              "wall, still loaded, with nobody minding it.", "watchman"),
    Situation("Midday", "in a public square where something is being read aloud",
              "You have stopped to listen along with everybody else.",
              "the crier working through the notices",
              "One of the notices has been torn off the board, and the paste under it "
              "is still wet."),
    Situation("Afternoon", "in a lane of open workshop doors",
              "You are watching a thing being made that you half know how to make.",
              "the apprentice minding the door",
              "The shutters are going up along the row, one door at a time, ahead of "
              "a man nobody is greeting."),
    Situation("Evening", "in a lit doorway with a room's noise behind it",
              "You have just come in out of the weather and not sat down yet.",
              "the servant carrying jugs two at a time",
              "Somebody has just gone out the other door in a hurry, and the room is "
              "working hard at not having noticed."),
    Situation("Mid-morning", "in a yard of carts being loaded for somewhere else",
              "You are counting the carts, and wondering.",
              "the drover checking his harness",
              "One cart is being unloaded again, item by item, and the argument about "
              "it is being conducted very quietly."),
    Situation("Late morning", "on a step in the sun where people have stopped to eat",
              "You are halfway through something bought from a stall.",
              "the stranger sharing the step",
              "People along the step have begun standing up, one at a time, and "
              "looking the same way down the street."),
    Situation("Dusk", "at a crossing thick with people heading home",
              "You are going against the flow of everyone else.",
              "the lamplighter starting his round",
              "The crowd ahead has split around something in the road, and closed up "
              "again behind it, and nobody has looked back.", "watchman"),
    Situation("Morning", "at a gathering for one of the regular public rituals",
              "You are standing where you are expected to stand.",
              "the neighbour beside you who knows the words",
              "The words have stopped in the wrong place. Nobody has picked them up, "
              "and nobody is looking at anybody else."),
)


# One errand per situation, in the table's order. Each is a thing a stranger with a
# thin purse would actually be doing, and each can be walked away from — the point is
# that the player knows what they were about when the world interrupts it.
ERRANDS: tuple[str, ...] = (
    "You came to sell what you carried in and buy a week's food with the money.",
    "You came for a meal you could afford and the name of somebody who hires.",
    "You came for a day's paid work before your money runs out.",
    "You came for water, and to hear where a stranger can sleep tonight.",
    "You came because the road ended here, with a purse about a week from empty.",
    "You came to hear the notices read, in case one of them wants someone like you.",
    "You came looking for a workshop that might take on a pair of hands for pay.",
    "You came in out of the weather to find a bed you can pay for.",
    "You came to ask for a place on a cart going somewhere with work in it.",
    "You came to eat cheaply and to watch the town before you ask anything of it.",
    "You came out to find a bed for the night before the lamps are lit.",
    "You came to be seen standing with the town, because a stranger who is not "
    "seen gets talked about.",
)
assert len(ERRANDS) == len(SITUATIONS)
SITUATIONS = tuple(replace(s, errand=e) for s, e in zip(SITUATIONS, ERRANDS))

# Where each situation's own words are set, in the table's order. Until 2026-10-03 the
# legacy table stood the party wherever `place_party` put them — the way in — and the
# frame said whatever the row said. The owner's save of that date opened "Evening …
# You are in a lit doorway with a room's noise behind it … You have just come in out of
# the weather and not sat down yet" with the engine holding the party at the MARKET;
# the narrator furnished a taproom round them for six turns ("the tavern patrons", "he
# leans back against the bar") because the opening had. So each row names the kinds of
# place its sentence describes, and a new campaign is stood in one when the town has it
# — the start documents' `where.kinds`, for the table that predates them. The dusk
# crossing names no kind: a crossing is a quarter's own place, not a settlement kind.
SITUATION_KINDS: tuple[tuple[str, ...], ...] = (
    ("market",),                                   # the market row, awnings going up
    ("lodging",),                                  # a crowded common room at the meal
    ("workshops", "carters yard", "smithy"),       # a work yard
    ("well", "cistern"),                           # a well-head
    ("gate",),                                     # the road in, under the gate
    ("market", "green"),                           # a public square, notices read
    ("workshops", "lane"),                         # a lane of open workshop doors
    ("lodging",),                                  # a lit doorway with a room's noise
    ("carters yard", "stables", "market"),         # a yard of carts being loaded
    ("market",),                                   # a step where people stop to eat
    (),                                            # a crossing thick with people
    ("temple",),                                   # a regular public ritual
)
assert len(SITUATION_KINDS) == len(SITUATIONS)
SITUATIONS = tuple(replace(s, kinds=k) for s, k in zip(SITUATIONS, SITUATION_KINDS))


def suggestions_for(situation: Situation) -> list[str]:
    """Three things the player could do from here, in their own voice, for the
    template opening; the written opening supplies its own. A start document carries
    its own, written to its hand-off."""
    if situation.suggestions:
        return [str(s) for s in situation.suggestions]
    who = situation.who
    return [f"Ask {who} what is going on",
            "Go and see for myself",
            "Keep to what I came here for"]


def _first_fact(place, keys) -> str:
    for key in keys:
        found = (place.fact(key, "") or "").strip() if place is not None else ""
        if found:
            return found
    return ""


def starting_place(world):
    """The best-described inhabited place the export has, or nothing.

    **No longer where a campaign starts** (2026-09-28): that is `rules/openings.choose`,
    a weighted draw from the campaign's own story seed. Measured before the change: on a
    templated export every settlement has the same number of facts and sections, so this
    ranking fell to summary length and then to reverse alphabetical order, and every
    Aurvantis campaign began in Vormoor — the last of its sixteen villages — while
    "Village" (seven letters) beat "Town" and "City". Kept as the floor `openings.towns`
    falls back to for a world with no adequately described settlement, and for
    `undercurrent`'s strain.

    Found rather than named. The previous code held a literal entity id from the
    fixture, so every other world started nowhere and the opening said so.
    """
    # A world that carries no entities at all is a legitimate export and answers
    # "nowhere" rather than raising — the undercurrent asks this of any world now,
    # including the bare ones the tests build to check the fallback.
    entities = getattr(world, "entities", None) or {}
    people_places = [
        e for e in entities.values()
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
    other = [e for e in entities.values() if e.kind not in ("WORLD",)]
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
    """The situation this campaign opened on.

    A campaign that opened on a start document (`scene.start`) reads it back from the
    document and the people the start actually put in the scene. Everything else — every
    save from before 2026-09-28, and a world no document fits — takes the legacy roll,
    byte for byte what it always was, so an old campaign's opening card cannot change
    under it.
    """
    start = getattr(campaign.scene, "start", None) or {}
    if start.get("id"):
        from rules import openings

        doc = openings.get(start["id"])
        if doc is not None:
            return from_start(doc, campaign.scene)
    return roll(campaign.id, campaign.seed)


def from_start(doc: dict, scene) -> Situation:
    """A start document as the Situation the template, the prose material and the
    opening card already read — one shape for both kinds of opening."""
    start = getattr(scene, "start", None) or {}
    lead = doc.get("lead") or {}
    label = " ".join(str(lead.get("label") or "").split())
    ref = str((start.get("slots") or {}).get("lead") or "")
    actor = scene.people.get(ref) if ref else None
    who = str(actor.name) if actor is not None and actor.name else label
    hand = dict(doc.get("hand_off") or {})
    where = str(start.get("where") or "")
    # An outside start says where it stands as the road does — "on the road to Dustgate,
    # outside Vormoor" — not "at the road to Dustgate", which reads as a room.
    where_words = str(start.get("where_words") or "")
    phrases = dict(start.get("phrases") or {})
    return Situation(
        when=str(doc.get("when") or "Mid-morning"),
        where=where_words or (f"at {where}" if where else "here"),
        doing=_filled(doc.get("doing"), phrases), who=who,
        edge=_filled(doc.get("edge"), phrases),
        template="", errand=str(doc.get("errand") or ""),
        look=str(lead.get("look") or ""), kind=str(doc.get("kind") or ""),
        hand_off=tuple(sorted((str(k), v) for k, v in hand.items()
                              if isinstance(v, (str, bool, int)))),
        moment=str(hand.get("moment") or ""), start_id=str(doc.get("id") or ""),
        suggestions=tuple(str(s) for s in doc.get("suggestions") or ()),
        label=label, says=_filled(lead.get("says"), phrases))


def _filled(text, phrases: dict) -> str:
    """A start document's `$slot` as the people the engine staged for it ("two wolves"),
    capitalised where it opens a sentence. The document cannot know what the land will
    send; the record (`Scene.start["phrases"]`) does. A slot with no phrase is left as
    the document wrote it — the validator refuses an undeclared one."""
    text = str(text or "")
    if "$" not in text or not phrases:
        return text

    def sub(m):
        said = str(phrases.get(m.group(1)) or "")
        if not said:
            return m.group(0)
        before = text[:m.start()].rstrip()
        if not before or before.endswith((".", "!", "?", "“", '"')):
            said = said[:1].upper() + said[1:]
        return said

    return re.sub(r"\$(\w+)", sub, text)


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


def _listed(text: str) -> str:
    """A comma-separated fact as an English list: "a, b" becomes "a and b".

    Joining, not rewriting — the words and their order are the export's. The facts
    are written as bare lists ("wooden buildings, thatched roofs") because they are
    fields in a table, and a field pasted into a sentence keeps reading as a field
    until the last comma becomes a conjunction.
    """
    parts = [p.strip() for p in str(text or "").split(",") if p.strip()]
    if len(parts) < 2:
        return " ".join(str(text or "").split())
    # An Oxford comma leaves the conjunction on the last item — "merchants, artisans,
    # farmers, and herders" — and adding another produced "farmers and and herders".
    if parts[-1].lower().startswith("and "):
        parts[-1] = parts[-1][4:].strip()
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f" and {parts[-1]}"


def _clause(text: str) -> str:
    """A fact as one item in a litany: trailing punctuation removed, nothing else.

    The case is left exactly as the export wrote it. Lower-casing the first letter
    read better on "Ringworld" and turned "Khy'vyr-centric clans" into "khy'vyr-centric
    clans" — the app quietly restyling one of the world's own names, which is the
    opposite of grounding them. A capital mid-list is a much smaller cost than a
    people whose name this app spells differently from every other page in it.
    """
    out = " ".join(str(text or "").split()).rstrip(" .;,")
    # The one exception the reasoning above allows: a leading ARTICLE is nobody's
    # name, and "Vormoor keeps to A local reeve confirmed by…" shipped in the opening
    # of the 2026-09-18 play-test. "A", "An", "The" and "Its" alone are lowered; every
    # other first word keeps the export's case.
    first = out.split(" ", 1)[0] if out else ""
    if first in ("A", "An", "The", "Its", "Their", "Some", "Several", "Mostly"):
        out = first.lower() + out[len(first):]
    return out


def what_you_know(world, place) -> str:
    """Kept for the tests and the watcher; no longer part of the opening.

    It read the export's *premise* aloud, and a World Bible premise is the dials the
    world was generated with rather than anything a person could know. Measured on
    the user's own world on 2026-09-03, the opening's first paragraph was: "Gaia world
    of improbable abundance; Human-baseline to Near-human variants divided by descent,
    varying by region — Full gambit of Fantasy races (elves, Dwarfs etc...); Early
    medieval to Renaissance, varying by region". Three of the six values said "varying
    by region", one carried its own typo, and one was an instruction to the generator
    about how to build regions. Nobody was born knowing that.

    Two rules retire it. Emily Short, *The Prose Medium and IF*: "Words in interactive
    fiction *individually* carry more weight than they carry in static prose … This is
    a medium that rewards restraint." And D.G. Jerz, *Exposition in Interactive
    Fiction*, on why a list in particular misfires: "Casual details like these are
    often found enriching ordinary prose narratives, but when they appear in the
    opening screen of an IF game, they take on a great deal of prominence" — players
    read every noun on the first screen as a promise the game will let them touch.
    Sixteen of them is sixteen promises.

    What the place is actually like now arrives as props inside the scene — Jo
    Walton's *incluing*, "scattering information seamlessly through the text, as
    opposed to stopping the story to impart the information".
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


def the_world_here(place, world=None) -> str:
    """Two sentences of where this is, from the place's own fiction.

    The preface the player asked for, and the thing the first cut of this rewrite
    threw out with the dials. The distinction that matters is not prose versus list,
    it is *whose fact it is*: the export's `premise` is the set of knobs World Bible
    generated the world with ("varying by region", three times), while the settlement
    carries what its author actually wrote about it — how it is governed, what a day
    in it looks like. The first is unusable at any length. The second only ever needed
    to be a sentence instead of a field.

    Two, and no more. Nelson's prologue "has to establish an atmosphere, and give out
    a little background information", and Emily Short: "This is a medium that rewards
    restraint."

    Case is the export's own, for the reason `_clause` records. The shipped worlds
    write these lower case — "matriarchal clan law", "morning markets, evening
    prayers" — and a world that capitalises them keeps its capitals rather than having
    this app respell its names.
    """
    if place is None:
        return ""
    # Each sentence has its own keys, because the fact has to fit the sentence.
    # `ORDER_KEYS` leads with "Social Classes" and gave "Vyrakon keeps to merchants,
    # artisans, farmers and herders", and `LIFE_KEYS` leads with "Urban Life" and gave
    # "The day here is mixed economy with market-driven trade" — a rule that is a list
    # of trades and a day that is an economy. What the place is ruled by and what a
    # day in it looks like are two questions, so they read two sets of keys.
    #
    # And a fact that is already a sentence is said as one. The frames spliced whatever
    # they were given, and the owner's screenshot of 2026-09-28 read "Zhilvarnia keeps
    # to Council of Elders advises on land use and trade" and "The day here is Daily
    # markets, communal gatherings and clan rituals": a clause jammed into a frame, and
    # a list wearing its field's capital. A clause stands alone; a noun phrase gets a
    # frame that fits a noun phrase, an article where it has none, and its first word
    # lowered unless the world uses that word as a name.
    said = []
    for keys, frame in (
        (("Formal Power", "Governance", "Administration"), "{name} answers to {fact}."),
        (("Social Classes",), "Its people are {fact}."),
    ):
        fact = _first_fact(place, keys)
        if fact:
            if _is_clause(fact):
                said.append(_sentence(fact))
            else:
                np = _lower_common(_listed(_clause(fact)), world)
                # An article only where the field's capital was standing in for one:
                # "Council of respected elder women" is a body ("the council …");
                # "matriarchal clan law" is a law, and reads as one without.
                if frame.startswith("{name}") and fact.strip()[:1].isupper():
                    np = _with_article(np)
                said.append(frame.format(name=place.name, fact=np))
            break
    day = _first_fact(place, ("Daily Norms", "Daily Life", "Customs", "Urban Life"))
    if day:
        said.append(_sentence(day) if _is_clause(day)
                    else f"Days here are shaped by {_lower_common(_listed(_clause(day)), world)}.")
    return " ".join(said)


# A finite verb before any relative pronoun makes a fact a clause ("the tide sets the
# working day"); after one, it belongs to a noun phrase ("a dawn bell that opens the
# markets"). A short list of the verbs these facts are written with, measured on the
# three fixtures' governance and daily-life fields — not a grammar, and not meant to be.
_FINITE = re.compile(
    r"\b(?:is|are|was|were|has|have|hold|holds|rule|rules|governs?|advises?|decides?|"
    r"oversees?|leads?|controls?|runs?|keeps?|meets?|sits?|elects?|appoints?|answers?|"
    r"settles?|judges?|manages?|chooses?|serves?|speaks?|enacts?|observes?|avoids?|"
    r"seeks?|turns?|sets?|rings?|comes?|goes|begins?|starts?|ends?|gathers?|prays?|"
    r"rises?|votes?|obeys?|follows?|live|lives|trade|work|works)\b", re.I)
_RELATIVE = re.compile(r"\b(?:that|who|which|where|when|whose)\b|,", re.I)
_DETERMINER = re.compile(r"^(?:a|an|the|its|their|his|her|some|each|every|no|one|two|"
                         r"three|many|most|several|all|[\w'’-]+['’]s?)\b", re.I)


def _is_clause(text: str) -> bool:
    text = " ".join(str(text or "").split())
    stop = _RELATIVE.search(text)
    head = text[:stop.start()] if stop else text
    return bool(_FINITE.search(head))


def _with_article(np: str) -> str:
    """"council of respected elder women" -> "the council of …"; a phrase that already
    has a determiner or a possessive ("High King's representative") keeps its own."""
    first = np.split(" ", 1)[0] if np else ""
    if not np or _DETERMINER.match(np) or first.endswith(("'s", "’s", "s'")):
        return np
    return f"the {np}"


def _name_words(world) -> frozenset:
    """Every capitalised word the world uses in a name: its entities, its cast, its
    peoples. The one test for whether a capital is the world's or a field's."""
    if world is None:
        return frozenset()
    key = id(world)
    got = _NAME_WORDS.get(key)
    if got is None:
        words = set()
        for e in (getattr(world, "entities", None) or {}).values():
            words.update(re.findall(r"[A-Z][\w'’-]*", str(getattr(e, "name", "") or "")))
        for c in ((getattr(world, "play", None) or {}).get("cast") or []):
            if isinstance(c, dict):
                words.update(re.findall(r"[A-Z][\w'’-]*", str(c.get("name") or "")))
        got = _NAME_WORDS[key] = frozenset(words)
    return got


_NAME_WORDS: dict[int, frozenset] = {}


def _lower_common(text: str, world=None) -> str:
    """The first word lowered when it is a field's capital and not a name.

    `_clause` refused to lower anything but articles, for a good reason — "Khy'vyr-centric
    clans" is the world's spelling — and so "Daily markets" kept a capital mid-sentence.
    The world says which words are names: a first word it uses in no name is lowered."""
    text = str(text or "")
    words = text.split(" ")
    first = words[0] if text else ""
    stem = re.split(r"[-'’]", first)[0]
    # Not when the next word is capitalised too: "High King's representative" is a
    # title, one name in two words, whatever the world's entity list says.
    nxt = words[1] if len(words) > 1 else ""
    if (first[:1].isupper() and first[1:2].islower() and "'" not in first
            and "’" not in first and not nxt[:1].isupper()
            and first not in _name_words(world) and stem not in _name_words(world)):
        return first[:1].lower() + text[1:]
    return text


def who_you_are(pc, standing: str) -> str:
    """Name, then where that leaves you here, then what you carry.

    No class label. "You are Borin Achereth, a Fighter" was the player's own example
    of what not to write, 2026-09-04: a game label where a person should be. What
    they carry is on the sheet and says the same thing the way a room would see it
    — a longsword at the hip reads as a fighter without the word.

    The standing already carries an em dash — "Zhilakai — flightless, in a city whose
    nobility is not" — so nothing else here adds one.
    """
    line = f"You are {pc.name}"
    standing = " ".join((standing or "").split()).rstrip(".")
    # The standing's case is its own: it begins with a people's name — "Nahyrin, a
    # long way from anyone who knows you" — and lower-casing it respelled the world.
    if standing:
        line += f", {standing}"
    carry = carrying(pc)
    if carry:
        line += f", {carry}"
    out = line + "."
    # The past the world bound to them, in the world's own names: "You fought where
    # Drenn Ironvale took the bets, near the market, and drew a crowd." Written in the
    # second person by `_bind_background`, so it goes in as it is. Two at most; the
    # template is held to Nelson's budget and this is one sentence of it.
    past = [str(t).strip() for t in (getattr(pc, "background_ties", None) or [])
            if str(t).strip()]
    if past:
        out += " " + " ".join(t if t.endswith((".", "!", "?")) else t + "."
                              for t in past[:2])
    return out


def carrying(pc) -> str:
    """What is on this character that a room would notice, from the sheet.

    The weapon first because it is what a stranger's eye goes to; then the armour.
    Nothing invented: an unarmed character in no armour carries nothing worth a
    clause and gets none.
    """
    if pc is None:
        return ""
    weapon = (getattr(pc, "equipped", "") or "").strip()
    armour = (getattr(pc, "armour", "") or "").strip()
    bits = []
    if weapon and weapon.lower() not in ("unarmed", "none"):
        bits.append(f"with {_article(weapon)} {weapon} at your side")
    if armour and armour.lower() != "none":
        bits.append(f"in {armour}")
    return " and ".join(bits)


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def compose(campaign, standing: str) -> str:
    """The opening the player reads: where, what is already happening, who they are.

    Built to the one documented shape in the tradition. Graham Nelson, *The Craft of
    Adventure* §"The Overture", on the opening of Moriarty's *Trinity*: "Already you
    know: who you are …; exactly where you are …; and what is going on", and the whole
    of it "striking and concise (not an effort to sit through, like the title page of
    `Beyond Zork')". His model does that in two paragraphs and 83 words, so this aims
    at the same budget and `tests/test_opening.py` holds it there.

    Nelson also supplies the last line's shape. The player has to be told what part
    they are playing at the moment they are asked to play it, and he cites Infocom's
    *Witness*, which "asks pointedly on the first turn": "What should you, the
    detective, do now?" A bare "What do you do?" is the same question with the role
    taken out.

    What is deliberately NOT here: the world's premise (see `what_you_know`), and any
    explanation of the thing in motion. The player asks; the narrator answers from the
    GM's private note. Dungeon World's first-session rule is to open "in a tense
    situation" and then "ask questions right away" — the tension arrives unexplained
    on purpose.
    """
    place, pc = campaign.location, campaign.scene.pc()
    here = situation_for(campaign)

    # WHERE first. "I have no idea what is going on or where i am" was said,
    # 2026-09-05, of an opening that led with the thing going wrong and named the
    # place in its second paragraph. A person orients in one order: where am I, why
    # am I here and what am I doing, what is happening, what could I do about it.
    # Don Carson, *Environmental Storytelling*: "it is the physical space that does
    # much of the work of conveying the story."
    where = f"{here.when}"
    if place is not None:
        # WHAT KIND OF PLACE, said before anything else about it. Four sessions in,
        # 2026-09-22: "I have never been aware that vormoor was a village. this should
        # be one of the first things done when you are being dropped into a world." The
        # scale was in the narrator's brief from the first turn and on no screen the
        # player ever read. Nelson's overture is "who you are, exactly where you are,
        # and what is going on", and a village of a few hundred where everyone knows
        # everyone is a different *where* from a city of tens of thousands — it changes
        # what the player expects to be able to do before they type anything.
        from rules import places as _places

        kind = _places.what_it_is(_places.scale_of(place))
        # A road start is OUTSIDE the settlement, with it ahead: "Late morning, outside
        # Vormoor" — "in Vormoor" would put the party back in the room the start moved
        # them out of (docs/fix-interfaces.md §3.3, I1).
        where += (", outside " if outside_start(campaign) else " in ") + \
            f"{place.name}{', ' + kind if kind else ''}."
    else:
        where += "."
    # THE ROOM, not a label for its style. The owner, on 2026-09-28's first screen —
    # "among Wooden Khy'vyr-style homes and Kelvaxian desert architecture" — "we need
    # descriptions of what the room looks like". The spot's own shape (the brief's
    # UNDERFOOT line), what the buildings round it are made of, the light at this hour
    # and what can be heard; the world's architecture fact turned into things you can
    # see, its style labels dropped (`built_of`).
    where += " " + the_spot(campaign, here)
    preface = the_world_here(place, getattr(campaign, "world", None))
    # The world's stock "the city's" at this settlement's own size, as the model's
    # material has it (item 1): a village's template must not call it a city either.
    from rules import geography

    from .opening_prose import stated_scale

    where = geography.in_its_own_words(where, stated_scale(place))
    preface = geography.in_its_own_words(preface, stated_scale(place))

    # WHY: who you are, why you came, what you are doing.
    why = f"{who_you_are(pc, standing)} {here.errand} {here.doing}".strip()

    if here.start_id:
        parts = [p for p in (f"{where} {preface}".strip(), why,
                             _what_now(campaign, here),
                             _now(here)) if p]
        return "\n\n".join(parts)

    # WHAT: the thing already happening, and the person it is happening beside.
    watcher = _sentence(here.who)[:-1]
    # "Has stopped to watch", not "has stopped working": half the people in the table
    # are not working — the old man ahead of you in a queue, the stranger sharing a
    # step — and the one verb has to fit all twelve.
    # And whether that person is a stranger, read off the scene rather than worked out
    # again here: `backgrounds.acquaint` has already put `bond.knows-you` on them if the
    # character's ties say they are known in this town. Two derivations of one fact is
    # the drift CLAUDE.md names, and this is the half the player reads.
    knows_you = any(not a.is_pc and a.has_state(states.KNOWS_YOU)
                    for a in (getattr(campaign.scene, "actors", None) or {}).values())
    watcher = f"{watcher}, who has known you long enough" if knows_you else watcher
    edge = (f"{here.edge} {watcher} has stopped to watch." if here.edge
            else f"{watcher} is close enough to speak to.")

    # NOW: what you could do, then the ask. The role used to ride in the question,
    # after Infocom's *Witness*; the player called it a game label, and the sheet
    # already shows it in the paragraph above.
    could = suggestions_for(here)
    now = (f"You could {_lower_first(could[0])}, {_lower_first(could[1])}, or "
           f"{_lower_first(could[2])}. What do you do?")

    parts = [p for p in (
        f"{where} {preface}".strip(),
        why,
        edge,
        now,
    ) if p]
    return "\n\n".join(parts)


def lead_of(campaign):
    """The start's lead as an actor, or None (a legacy opening has no slots)."""
    ref = str(((getattr(campaign.scene, "start", None) or {}).get("slots") or {})
              .get("lead") or "")
    return campaign.scene.people.get(ref) if ref else None


def face_line(name: str, appearance: str) -> str:
    """The world's own face for somebody, as one sentence about them.

    `names.appearance_for` writes "Orc: Small, wiry, sharp-toothed. A scar …" — the
    people's name, then the body line(s) and a detail of their own. Said here as
    "{name} is an Orc: small, wiry, …" so it reads as a sighting, not a card."""
    appearance = " ".join(str(appearance or "").split())
    if not appearance or not name:
        return ""
    people, _, body = appearance.partition(": ")
    if not body:
        return _sentence(f"{name}: {appearance}")
    body = body[:1].lower() + body[1:] if body[1:2].islower() else body
    # "of the Korvu people", never "a Korvu": the second copy of `narration.a_face_for`'s
    # rule, changed with it (2026-10-03, item 14 — "a man named Korvu").
    return f"{name[:1].upper()}{name[1:]} is of the {people} people: " + (
        body if body.endswith((".", "!", "?")) else body + ".")


def _what_now(campaign, here: Situation) -> str:
    """WHAT, for a start document: the thing in motion, the lead as the player first
    sees them — face included, so nobody is owed a description on turn three (item 4,
    2026-09-28: the watchman was described on the third beat) — and what they say."""
    lead = lead_of(campaign)
    name = here.who
    intro = name if name == here.label or not here.label else f"{name}, {here.label}"
    knows = bool(lead is not None and lead.has_state(states.KNOWS_YOU))
    who = intro[:1].upper() + intro[1:]
    bits = [here.edge.strip()]
    line = who + (f", {here.look}" if here.look else "")
    line += ", who has known you long enough" if knows else ""
    comma = "," if (here.look or knows) else ""
    bits.append(f"{line}{comma} says: “{here.says}”" if here.says
                else f"{line}{comma} is close enough to speak to.")
    face = face_line(name if name != here.label else here.label,
                     getattr(lead, "appearance", "") if lead is not None else "")
    if face:
        bits.append(face)
    return " ".join(b for b in bits if b)


def _now(here: Situation) -> str:
    could = suggestions_for(here)
    if len(could) >= 3:
        choices = (f"You could {_lower_first(could[0])}, {_lower_first(could[1])}, or "
                   f"{_lower_first(could[2])}.")
    elif len(could) == 2:
        choices = f"You could {_lower_first(could[0])} or {_lower_first(could[1])}."
    else:
        choices = ""
    return " ".join(b for b in (here.moment.strip(), choices, "What do you do?") if b)


# --- the room ----------------------------------------------------------------------------------

# Words that name something you can SEE a building made of or shaped as. A style label
# ("Khy'vyr-style", "Kelvaxian desert architecture") names none of them and is dropped.
_BUILT = frozenset("""
wood wooden timber timbered log logs stone stones brick bricks basalt slate thatch thatched
reed reeds clay adobe mud cob tile tiles tiled plaster plastered whitewash whitewashed
granite marble sandstone limestone flint turf iron glass canvas hide hides bone bones
coral driftwood cane bamboo rope silk awning awnings roof roofs rooftop rooftops window
windows wall walls tower towers dome domes arch arches stilt stilts house houses home
homes hut huts cottage cottages hall halls blockhouse blockhouses tent tents building
buildings street streets courtyard courtyards balcony balconies shutter shutters chimney
chimneys door doors terrace terraces terraced column columns pillar pillars platform
platforms frame frames framed facade facades fresco frescoes mosaic mosaiced
weatherboard boards planks gable gables eaves canal canals silo silos crystal
windcatcher windcatchers footings shed sheds warehouse warehouses cathedral dwelling
dwellings structure structures ziggurat ziggurats spire spires archway archways
stonework housing tenement tenements bridges bridge longhouse longhouses yurt yurts
""".split())
_STYLE = re.compile(r"[\w'’]+-(?:style|styled|inspired|influenced|era|type)\b|\b(?:style|"
                    r"styles|styled|design|designs|aesthetic|influences?)\b|^\w+:\s*", re.I)
_ARCHITECTURE = re.compile(r"\barchitecture\b|\barchitectural\b", re.I)
# A people's or a place's adjective: "Kelvaxian", "Khy'vyr", "Nirkorese". A style by
# another name, and nothing a stranger could see.
_PROPER_ADJ = re.compile(r"^[A-Z][\w'’-]*(?:ian|ean|ish|ese|ic|i)$|^[A-Z][\w-]*['’]")


def built_of(fact: str) -> str:
    """The world's architecture fact as the things a person standing there would see.

    "black basalt blockhouses with narrow windows" is already that and is kept whole.
    "Wooden Khy'vyr-style homes, Kelvaxian desert architecture" is two style labels
    round two sights: the labels go, "architecture" becomes the buildings it is, and
    "wooden homes and desert buildings" is what is left. A part that names nothing you
    could see is left out rather than guessed at — the model material still has the
    whole fact, and the template claims nothing it cannot show.
    """
    fact = " ".join(str(fact or "").split()).rstrip(" .;")
    if not fact:
        return ""
    labelled = bool(_STYLE.search(fact) or _ARCHITECTURE.search(fact)
                    or any(w[:1].isupper() for w in fact.split()[1:]))
    if not labelled:
        fact = _listed(fact)
        return fact[:1].lower() + fact[1:] if fact[1:2].islower() else fact
    parts = [p.strip() for p in re.split(r",\s*|\s+and\s+", fact) if p.strip()]
    kept = []
    for part in parts:
        bare = _ARCHITECTURE.sub("buildings", _STYLE.sub(" ", part))
        words = re.findall(r"[A-Za-z][A-Za-z'’-]*", bare)
        # A capitalised word that is not the part's first is somebody's name, and a
        # first word that is a people's adjective is a label: both dropped.
        words = [w for i, w in enumerate(words) if i == 0 or not w[:1].isupper()]
        if words and _PROPER_ADJ.match(words[0]) and words[0].lower() not in _BUILT:
            words = words[1:]
        if not any(w.lower() in _BUILT for w in words):
            continue
        text = " ".join(words)
        kept.append(text[:1].lower() + text[1:] if text[1:2].islower() else text)
    return _listed(", ".join(dict.fromkeys(kept))) if kept else ""


def _light(hour: int) -> str:
    if hour < 11:
        return "The morning light comes in low and cold"
    if hour < 15:
        return "The sun is high and flat over everything"
    if hour < 18:
        return "The afternoon light lies long across the ground"
    return "The light is going, and the first lamps are lit"


# What a spot sounds and smells like, by its label. Short and fixed on purpose: it is
# the template floor, and a floor that tries to be prose becomes the tic 2026-09-17
# measured. The model material carries the world's own writing instead.
_SENSES = {
    "the market": "hawkers calling over each other, and a smell of bread, fish and trodden dung",
    "the merchants row": "shop bells and bargaining, and a smell of spice and polish",
    "the well": "the creak of the windlass and water slopping over stone",
    "the gate": "cartwheels, hooves, and the watch calling the queue forward",
    "the way in": "cartwheels, hooves, and somebody calling out to whoever comes up the road",
    "the tavern": "voices over a hearth, and a smell of smoke and spilled beer",
    "the inn": "voices over a hearth, and a smell of smoke and spilled beer",
    "the arena": "the crowd's roar, and a smell of sand and sweat",
    "the green": "voices carrying over open grass, and a smell of trodden turf",
    "the lane": "footsteps off close walls, and a smell of the gutter",
    "the back streets": "footsteps off close walls, and a smell of the gutter",
    "the warrens": "voices through thin walls on every side, and a smell of the gutter",
    "the docks": "water slapping under the timbers, and a smell of tar and weed",
    "the bridge": "water loud underneath, and a smell of wet stone",
    "the guildhall": "a low murmur of voices, and a smell of dust and candle wax",
    "the moot hall": "a low murmur of voices, and a smell of dust and candle wax",
    "the library": "pages turning somewhere, and a smell of dust and candle wax",
    "the temple": "a hush, and old incense in the air",
    "the shrine": "a hush, and old incense in the air",
    "the stables": "hooves shifting in straw, and a smell of horse and hay",
    "the carters yard": "harness jingling and wheels on cobbles, and a smell of horse and grease",
    "the workshops": "hammers and saws, and a smell of hot iron and sawdust",
}


def outside_start(campaign) -> bool:
    """Whether this campaign opened on a start that stands the party outside the
    settlement (a road start, an outskirts start) — read off the start's own record."""
    start = getattr(getattr(campaign, "scene", None), "start", None) or {}
    return bool(start.get("id")) and start.get("setting") == "outside"


# What open ground sounds and smells like, for an outside start's template floor. One
# line, as `_SENSES` is one line a spot: the model material carries the world's own land.
_OPEN_AIR = "wind over open ground, and a smell of dust and trodden earth"


def the_land(campaign) -> str:
    """The land around the road, from the world: "Round about is farmland, and past it
    mountain." Lane B's LAND AROUND (`geography.land_around`), the same words the brief
    prints outside — the ground near the settlement and the ground further out, never a
    biome the world did not give. "" when the world said nothing."""
    from rules import geography

    place = campaign.location
    world = getattr(campaign, "world", None)
    if place is None or world is None:
        return ""
    try:
        land = geography.land_around(world, place)
    except Exception:
        return ""
    near = [g for g in land.near if g != "coast"]
    coast = "coast" in land.near or land.coast
    bits = []
    if near:
        bits.append(f"Round about is {_listed(', '.join(near))}")
    elif coast:
        bits.append("Round about is the coast")
    if land.beyond:
        bits.append(f"and past it {_listed(', '.join(land.beyond))}" if bits
                    else f"Further out is {_listed(', '.join(land.beyond))}")
    return (", ".join(bits) + ".") if bits else ""


def the_spot(campaign, here: Situation) -> str:
    """The first paragraph's room: where exactly, its shape, its buildings, its air."""
    from rules import floorplan
    from rules import places as places_mod

    spot = None
    try:
        spot = places_mod.find(campaign.engine().places(), campaign.scene.at)
    except Exception:
        spot = None
    if here.start_id and spot is not None and outside_start(campaign):
        # A road start is described as the road and the land, not as a room: the owner's
        # "descriptions of what the room looks like" (2026-09-28) means, out here, what
        # is underfoot and what lies round about — Lane B's ring place's own caption
        # ("a road leaving, ruts either side of it") and the world's land around the
        # settlement. No "buildings round about": there are none on the road.
        about = floorplan.describe(spot.id, spot.terrain, spot.shape)
        bits = [f"You are {here.where}" + (f": {about}." if about else ".")]
        land = the_land(campaign)
        if land:
            bits.append(land)
        bits.append(f"{_light(hour_of(here.when))}, with {_OPEN_AIR}.")
        return " ".join(bits)
    label = " ".join(str(getattr(spot, "name", "") or "").lower().split())
    if here.start_id and spot is not None:
        about = floorplan.describe(spot.id, spot.terrain, spot.shape)
        first = f"You are at {spot.name}" + (f": {about}." if about else ".")
    else:
        first = f"You are {here.where}."
        # The legacy table's phrase is the spot; its air comes from the phrase's own
        # nouns when the party's place is not what it names.
        label = next((k for k in _SENSES if k.removeprefix("the ") in here.where.lower()),
                     "")
    bits = [first]
    built = built_of(_first_fact(campaign.location, ("Architecture",)))
    if built:
        bits.append(f"The buildings round about are {built}.")
    sense = _SENSES.get(label, "people's voices, and woodsmoke on the air")
    bits.append(f"{_light(hour_of(here.when))}, with {sense}.")
    return " ".join(bits)


def _lower_first(text: str) -> str:
    """A suggestion, in the player's voice, folded into the narrator's sentence:
    "Ask the drover what is going on" becomes "ask the drover what is going on", and
    "Go and see for myself" becomes "go and see for yourself"."""
    text = text.strip()
    text = text[:1].lower() + text[1:]
    text = re.sub(r"\bmyself\b", "yourself", re.sub(r"\b[Ii] came\b", "you came", text))
    # The rest of the player's first person, for the start documents' own suggestions:
    # "Turn out my pockets" was folded in as "you could turn out my pockets".
    text = re.sub(r"\bI\b", "you", text)
    text = re.sub(r"\bmy\b", "your", text)
    return re.sub(r"\bme\b", "you", text)


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


def undercurrent(world, seed: int | None = None, place=None) -> str:
    """The campaign's live thread, rolled once at the start.

    The world's own `unwritten` hooks first — they are exactly this, authored by the
    world's generator and reaching nothing until now — then the starting place's own
    strain, and the agnostic table only when the export offers neither. Seeded from
    the campaign seed so a rerolled campaign is a genuinely different evening.

    The middle step was missing and it cost the shipped world its own story. Measured
    2026-09-03: the user's Fantasia export carries no `unwritten` at all, so every
    campaign in it rolled a stranger's debt off the generic table — while the town it
    starts in carried "tensions between Vyrakon and Oorvieth's city government", over
    "border control and taxation", written by the world's own author and read by
    nothing. A world that says what is wrong with a place should not be told what is
    wrong with it.
    """
    d = Dice(seed=seed)
    pool = hook_texts(world)
    if not pool:
        # The town the campaign actually opens in, now that that is drawn rather than
        # always the best-described one; `starting_place` for a caller that has none.
        home = place if place is not None else starting_place(world)
        strain = _first_fact(home, STRAIN_KEYS)
        cause = _first_fact(home, ("Cause", "Volatility", "Status"))
        if strain:
            pool = [f"{_sentence(strain)[:-1]}"
                    + (f" — {_clause(cause).lower()}." if cause else ".")]
    pool = pool or UNDERCURRENTS
    # A place with one strain is a pool of one, and `1d1` is refused by the dice as
    # implausible — rightly, since nothing is being decided.
    return pool[0] if len(pool) == 1 else pool[d.roll(f"1d{len(pool)}").total - 1]


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
