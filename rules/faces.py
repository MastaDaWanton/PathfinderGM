"""A face of their own for every person the scene makes.

Reported 2026-09-23 with the beat on screen, the sixth orc in a row to be "Powerfully
built, prominent lower tusks, thick hide that resists minor scarring": *"this is the
description of every person who is an orc. descriptions should be detailed and unique
when possible."* Measured on that save: eight people in the scene, six of them carrying
that one sentence word for word, because `play.races` ships ONE body line per people
and `names.appearance_for` had nothing else to draw on.

The people's line stays — it is the world's own, and an orc here should read as an orc
of this world — and what is added is what a person has that their people do not: their
years, what is on their head, a mark, and what their hands say about them. Dwarf
Fortress is the standing example of this shape, a creature's caste fixing what CAN vary
(hair, eye, skin, build) and each individual drawing its own values, which is why every
dwarf in a fortress can be told apart in a paragraph. Caves of Qud does the same for
its village folk. The pools below are that idea at the size this app can hold: a
handful of categories, a dozen values each, three drawn per person.

Deterministic, seeded off the ref and the location the way the name is (`names.py`), so
a save replayed does not hand the stranger a second face. And in the people's frame:
a detail that would contradict the body line — grey hair on a feathered people, a
broken nose on a beaked one — is not offered, decided by what the body line says rather
than by a list of races kept here.

The result keeps the label form `People: body. details.` that `narration.a_face_for`
reads, so the backstop still says "The man is an Orc: …" and the brief still shows the
people's name.
"""
from __future__ import annotations

import hashlib
import re

# Years. Not a number — the narrator is never handed one — but where in a life.
YEARS = (
    "young, not long out of their growing",
    "young enough that the face has not settled yet",
    "somewhere in the middle of life",
    "past the middle of life and carrying it easily",
    "grey-streaked and unbothered by it",
    "old enough to have stopped counting",
    "weathered well past what the years alone would do",
    "of no age anybody could put a number to",
)

# What is on the head. Only offered to a people whose body line does not say otherwise
# (see `_no_hair`): a feathered, furred, scaled or bare-skinned people keeps its own.
HEAD = (
    "hair cropped close to the skull",
    "hair tied back hard and going grey at the temples",
    "a shaved head, nicked in two places by the razor",
    "hair worn in a single thick braid down the back",
    "a mane of hair left to do as it likes",
    "hair hidden under a cap that has not been off in a while",
    "hair gone white early and kept short",
    "hair oiled flat and parted with care",
    "a fringe cut straight across, badly",
    "hair the colour of wet rope, tied with a strip of cloth",
)

# A mark. Chosen so that any humanoid can carry it — no noses, no ears, nothing a beak
# or a frog's face would make nonsense of.
MARK = (
    "a scar through one eyebrow",
    "the last two fingers of the left hand gone at the knuckle",
    "an old burn across the back of one hand",
    "a healed break in the jaw that set a little crooked",
    "one eye clouded and turned slightly out",
    "a line of blue ink dots across the knuckles",
    "a limp favouring the right leg",
    "a stoop that has become the way they stand",
    "a pale seam of scar tissue down one forearm",
    "the marks of an old pox across the cheeks",
    "a missing front tooth that shows when they talk",
    "a brand on the inside of the wrist, old and blurred",
)

# What the hands and the clothes say. The one category that is about a life rather than
# a body, and the one a narrator most often reaches for on its own — so it is given
# something true to reach for.
HANDS = (
    "hands stained to the wrist with dye that will not wash out",
    "hands thick with the calluses of rope and haft",
    "hands soft and clean, the nails kept",
    "fingers stained black at the tips with ink",
    "a carter's shoulders and a carter's rolling walk",
    "clothes good once and mended more than once since",
    "clothes too clean for the work they say they do",
    "a coat too heavy for the weather, worn anyway",
    "boots that have walked further than the rest of the outfit",
    "a knife at the belt that is a tool and not a weapon",
    "rings on three fingers, none of them worth much",
    "a smell of smoke and hot iron that goes everywhere they do",
)

# Words in a body line that mean the head is not a head of hair.
_NO_HAIR = ("feather", "beak", "frog", "scale", "fur", "feline", "simian", "rodent",
            "crow", "hairless", "shell", "chitin")


def _pick(pool, ref: str, location_id: str, salt: str) -> str:
    n = int(hashlib.sha256(f"{location_id}|{ref}|{salt}".encode()).hexdigest()[:8], 16)
    return pool[n % len(pool)]


def _no_hair(body: str) -> bool:
    low = body.lower()
    return any(w in low for w in _NO_HAIR)


def details_for(body: str, ref: str, location_id: str | None = None) -> str:
    """Three things that are this person's and not their people's, as one sentence.

    `body` is the people's own line, read only to decide what may be offered. Empty
    `ref` gives nothing: a face with no person behind it is the people's line alone,
    which is what the brief's "Looks" of a generic role wants.
    """
    if not ref:
        return ""
    where = str(location_id or "")
    bits = [_pick(YEARS, ref, where, "years")]
    if not _no_hair(body or ""):
        bits.append(_pick(HEAD, ref, where, "head"))
    bits.append(_pick(MARK, ref, where, "mark"))
    bits.append(_pick(HANDS, ref, where, "hands"))
    # Three, so the line stays a line: years and a mark always, and one of the other
    # two — the head where a people has one, the hands otherwise.
    if len(bits) == 4:
        bits = [bits[0], bits[1], bits[2]] if _pick((0, 1), ref, where, "which") else \
               [bits[0], bits[2], bits[3]]
    said = "; ".join(bits)
    return said[0].upper() + said[1:] + "."


# --- a people described once -----------------------------------------------------------
#
# Reported 2026-09-24, on the second orc of the session: *"the description is the same
# description for every other orc ever introduced."* The people's own line — the
# world's one sentence for what an orc is — was printed in full for every orc, before the
# details that are the person's own. A table GM says what an orc looks like once; after
# that, "another orc" and what is different about this one. So the people's line is
# shown for the FIRST person of that people described in a campaign, and every later one
# gets the people's name and their own details only.

def people_of(appearance: str) -> str:
    """"Orc" for "Orc: Powerfully built… Old enough…", "" for a resident's free text."""
    people, sep, _ = str(appearance or "").partition(": ")
    return people.strip() if sep and 1 <= len(people.split()) <= 3 else ""


def own_details(appearance: str) -> str:
    """The person's own sentence — the last one — without the people's line."""
    _, sep, body = str(appearance or "").partition(": ")
    if not sep:
        return ""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", body.strip()) if p.strip()]
    return parts[-1] if len(parts) > 1 else ""


def for_the_page(appearance: str, people_seen: bool) -> str:
    """What to print for this person: the whole line the first time their people is
    described, the people's name and their own details after that."""
    if not people_seen:
        return str(appearance or "")
    people, details = people_of(appearance), own_details(appearance)
    if not people or not details:
        return str(appearance or "")
    return f"{people}: {details}"


def people_seen_before(actor, everyone) -> bool:
    """Whether another person of this people has already been described here."""
    mine = people_of(getattr(actor, "appearance", ""))
    if not mine:
        return False
    for other in everyone:
        if other is actor or getattr(other, "is_pc", False):
            continue
        if getattr(other, "described", False) and \
                people_of(getattr(other, "appearance", "")) == mine:
            return True
    return False
