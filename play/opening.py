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


def suggestions_for(situation: Situation) -> list[str]:
    """Three things the player could do from here, in their own voice, for the
    template opening; the written opening supplies its own."""
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
    """The smallest inhabited place the export describes, or nothing.

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
    return " ".join(str(text or "").split()).rstrip(" .;,")


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


def the_world_here(place) -> str:
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
    said = []
    for keys, template in (
        (("Formal Power", "Governance", "Administration"), "{name} keeps to {fact}."),
        (("Social Classes",), "Its people are {fact}."),
    ):
        fact = _first_fact(place, keys)
        if fact:
            said.append(template.format(name=place.name, fact=_listed(_clause(fact))))
            break
    day = _first_fact(place, ("Daily Norms", "Daily Life", "Customs", "Urban Life"))
    if day:
        said.append(f"The day here is {_listed(_clause(day))}.")
    return " ".join(said)


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
    where += f" in {place.name}." if place is not None else "."
    where += f" You are {here.where}"
    look = _first_fact(place, LOOK_KEYS)
    # Case left exactly as the export wrote it, for the reason `_clause` records:
    # lower-casing read better on "Turf roofs" and turned "Khy'vyr-centric clans" into
    # "khy'vyr-centric clans", which is this app respelling one of the world's own
    # names. A capital mid-sentence is the smaller cost.
    where += f", among {_listed(_clause(look))}." if look else "."
    preface = the_world_here(place)

    # WHY: who you are, why you came, what you are doing.
    why = f"{who_you_are(pc, standing)} {here.errand} {here.doing}".strip()

    # WHAT: the thing already happening, and the person it is happening beside.
    watcher = _sentence(here.who)[:-1]
    # "Has stopped to watch", not "has stopped working": half the people in the table
    # are not working — the old man ahead of you in a queue, the stranger sharing a
    # step — and the one verb has to fit all twelve.
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


def _lower_first(text: str) -> str:
    """A suggestion, in the player's voice, folded into the narrator's sentence:
    "Ask the drover what is going on" becomes "ask the drover what is going on", and
    "Go and see for myself" becomes "go and see for yourself"."""
    text = text.strip()
    text = text[:1].lower() + text[1:]
    return re.sub(r"\bmyself\b", "yourself", re.sub(r"\b[Ii] came\b", "you came", text))


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
        strain = _first_fact(starting_place(world), STRAIN_KEYS)
        cause = _first_fact(starting_place(world), ("Cause", "Volatility", "Status"))
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
