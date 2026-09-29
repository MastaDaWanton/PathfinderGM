"""What the words for a person already say about them: man or woman, young or old, a
child or not, and which of the world's peoples.

Measured on the 2026-09-28 playtest (docs/playtest-2026-09-28.md item 5.3): "I ask him
about the girl in the market" spawned a body called *girl* with pronouns they/them, race
human (the template's) and an Orc face (the local people's). Every one of those facts was
in the player's word or in the world, and the spawn door read none of them. A spawn, an
embodied record and a person placed elsewhere by an NPC's line all go through here, so
the word is honoured the same way whichever door the person came in by.

Pure: no scene. The world is read only for its peoples' names ("an elf girl").

The rulings it carries:

  * **Q25 (2026-09-28): "girl" is a young adult** unless "child", "little" or kin words
    say otherwise. The watchman's "the girl in the market" is a young woman keeping a
    stall, and the table's content rule makes a child a different kind of person to
    write. "boy" and "lad" keep the reading the life tables already give them (a child);
    the ruling was asked, and answered, about "girl".
  * **Identity, not state.** Gender and pronouns are what a person is called, like the
    name — not a mechanical state, so they are fields on the actor and never an effect.
"""
from __future__ import annotations

import re

_FEMALE = frozenset({
    "woman", "women", "lady", "dame", "goodwife", "matron", "madam", "wife", "female",
    "mistress", "girl", "lass", "lassie", "maid", "maiden", "mother", "daughter", "sister",
    "aunt", "niece", "grandmother", "granny", "grandma", "widow", "crone", "hag", "queen",
    "princess", "duchess", "countess", "baroness", "empress", "priestess", "sorceress",
    "seamstress", "hostess", "huntress", "waitress", "governess", "abbess", "fishwife",
    "washerwoman", "barmaid", "milkmaid", "nun", "matriarch",
})
# No pronouns in either list: in a description a pronoun is somebody else's — "her
# husband" is a man, "the boy with his sister" is a boy.
_MALE = frozenset({
    "man", "men", "fellow", "gent", "gentleman", "chap", "bloke", "male", "sir", "goodman",
    "boy", "lad", "laddie", "father", "son", "brother", "uncle", "nephew", "husband",
    "grandfather", "grandpa", "gaffer", "greybeard", "graybeard", "king", "prince", "duke",
    "baron", "emperor", "lord", "monk", "abbot", "patriarch",
})
# A word ending "-man" is a man in English usage ("the watchman ... his eyes"), and
# "-woman" a woman — except where the ending is no word for a person at all.
_NOT_A_MAN = frozenset({"human", "woman", "shaman", "talisman", "caiman", "german",
                        "ottoman", "layman", "yeoman"})

_OLD = frozenset({"old", "elderly", "aged", "ancient", "wizened", "grey", "gray",
                  "grizzled", "white-haired", "grey-haired", "grey-bearded", "greybeard",
                  "graybeard", "crone", "hag", "granny", "gaffer", "grandmother",
                  "grandfather", "grandma", "grandpa"})
_YOUNG = frozenset({"young", "youthful", "youth", "youngster", "lad", "lass", "lassie",
                    "girl", "boy", "maiden"})
# The words that make somebody a child, whatever else is said.
_CHILD = frozenset({"child", "children", "kid", "kids", "urchin", "brat", "little",
                    "tiny", "infant", "baby", "toddler", "youngster"})
# "boy" and "lad" are children in the life tables (`content/people/occupations.json`,
# the `child` occupation) and stay so; "girl" and "lass" do not, by the Q25 ruling.
_CHILD_BY_DEFAULT = frozenset({"boy", "lad", "laddie"})
_GIRL = frozenset({"girl", "lass", "lassie"})
# Kin words: "the smith's girl", "his girl", "her daughter" are somebody's child.
_KIN = frozenset({"daughter", "son", "niece", "nephew", "grandchild", "granddaughter",
                  "grandson", "stepdaughter", "stepson"})
_POSSESSED = re.compile(r"(?:\b(?:his|her|their|my|your|our)|['’]s)\s+(?:little\s+)?"
                        r"(?:girl|lass|lassie|boy|lad)\b", re.I)

_WORD = re.compile(r"[a-z][a-z'’-]*")

PRONOUNS = {"woman": "she/her", "man": "he/him"}


def _words(phrase: str) -> list[str]:
    return [w.strip("'’-") for w in _WORD.findall(str(phrase or "").lower())]


def gender_of(words) -> str:
    """"woman", "man" or "" from the words of a description: the first gendered word
    decides ("a woman and her son" is the woman)."""
    for w in words:
        if w in _FEMALE or (w.endswith("woman") and len(w) > 5):
            return "woman"
        if w in _MALE or (w.endswith("man") and len(w) > 3 and w not in _NOT_A_MAN
                          and not w.endswith("woman")):
            return "man"
    return ""


def people_named(phrase: str, world) -> str:
    """The PEOPLE id a phrase names ("an elf girl", "the half-orc smith"), or "".

    The world's own peoples only (the PEOPLE entities and `play.races` names), longest
    name first, so "half-orc" is never read as "orc"."""
    if world is None or not phrase:
        return ""
    from . import names as names_mod

    named = dict(names_mod.peoples(world))
    play = getattr(world, "play", None) or {}
    for r in (play.get("races") if isinstance(play, dict) else None) or []:
        if isinstance(r, dict) and r.get("people_id") and r.get("name"):
            named.setdefault(str(r["people_id"]), str(r["name"]))
    low = " ".join(str(phrase).lower().split())
    for pid, name in sorted(named.items(), key=lambda kv: -len(kv[1])):
        n = " ".join(str(name).lower().split())
        if n and re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", low):
            return str(pid)
    return ""


def people_drawn(world, location_id: str | None) -> str:
    """The people whose body `names.appearance_for` draws for a stranger made here when
    no people is named — the same answer, so a body and its people cannot disagree.

    Measured on the playtest: c2 was "race human" with "Orc: …" as its face, because the
    face came from the town's people and nothing else did."""
    if world is None:
        return ""
    from . import names as names_mod

    pid = names_mod.people_of(world, location_id)
    play = getattr(world, "play", None) or {}
    races = [r for r in ((play.get("races") if isinstance(play, dict) else None) or [])
             if isinstance(r, dict)]
    if pid and any(r.get("people_id") == pid for r in races):
        return str(pid)
    known = names_mod.peoples(world)
    fallback = next((r for r in races if r.get("people_id") in known), None)
    if fallback is not None:
        return str(fallback.get("people_id") or "")
    return str(pid or "")


def people_name(world, people_id: str) -> str:
    """A people's name as the world writes it, from `play.races` or its PEOPLE entity."""
    if world is None or not people_id:
        return ""
    play = getattr(world, "play", None) or {}
    for r in (play.get("races") if isinstance(play, dict) else None) or []:
        if isinstance(r, dict) and r.get("people_id") == people_id and r.get("name"):
            return str(r["name"])
    from . import names as names_mod

    return names_mod.people_name(world, people_id)


def from_words(phrase: str, world=None, location_id: str = "") -> dict:
    """What the words for a person say about them.

    Returns ``{"gender", "pronouns", "age", "minor", "people_id"}``: gender "woman",
    "man" or ""; pronouns "she/her", "he/him" or "" (nothing said); age "child", "young",
    "old" or ""; `minor` True only for a child; people_id the world's PEOPLE id the words
    name, or "". `location_id` is taken for the register's signature; the people drawn
    when none is named is `people_drawn`'s answer, asked by the caller that draws the face.
    """
    words = _words(phrase)
    wordset = set(words)
    gender = gender_of(words)
    minor = bool(wordset & _CHILD) or bool(wordset & _CHILD_BY_DEFAULT)
    if wordset & _GIRL and (wordset & _KIN or _POSSESSED.search(str(phrase or ""))):
        minor = True
    if wordset & _KIN and wordset & (_GIRL | _CHILD_BY_DEFAULT):
        minor = True
    if minor:
        age = "child"
    elif wordset & _OLD:
        age = "old"
    elif wordset & _YOUNG:
        age = "young"
    else:
        age = ""
    return {"gender": gender, "pronouns": PRONOUNS.get(gender, ""), "age": age,
            "minor": minor, "people_id": people_named(phrase, world)}


def roll_phrase(phrase: str, said: dict | None = None) -> str:
    """The phrase the life roll reads (`lives.roll`), with the Q25 ruling applied.

    The life tables read "girl" as the child occupation. A girl the words do not make a
    child is rolled as "a young woman" — the record keeps the speaker's own words, which
    are what the player will paraphrase; only the roll sees the gloss."""
    said = said if said is not None else from_words(phrase)
    if said.get("minor"):
        return str(phrase or "")
    return re.sub(r"\b(?:girl|lass|lassie)\b", "young woman", str(phrase or ""),
                  flags=re.I)


def honour_spawn(scene, world, made: list[dict], name: str) -> None:
    """The spawn door's half (`Engine._op_spawn`): each body the word made gets what the
    word says, and the `made` rows carry it into the outcome (`spawn.actors[]`
    `pronouns` and `from_words`, fix-interfaces §2.7 — emitted only when set).

    * gender and pronouns from the word ("girl": she/her);
    * the people: the one named ("an elf girl"), else the one whose body the face is
      drawn from, as the actor's `world_people_id` and `heritage` — the sheet's own split
      (05-sheet.js: the heritage is who they are in the world, the race is what the rules
      use), so the stat block's race stays the rules' and the face and the people agree;
    * the years: when the word says young, old or a child, the face is drawn again with
      those years (`lives.roll` reads them from the same words).

    The name is left alone: the world ships no gender per given name yet, and the
    standing ruling is that `names.true_name` does not guess one (design D §4.3)."""
    if not made or scene is None:
        return
    location = str(getattr(scene, "location_id", "") or "")
    said = from_words(name, world, location)
    pid = said["people_id"] or people_drawn(world, location)
    for row in made:
        if row.get("members"):
            continue                       # a crowd is a unit, not a person
        ref = str(row.get("ref") or "")
        actor = (getattr(scene, "people", None) or {}).get(ref) \
            or (getattr(scene, "actors", None) or {}).get(ref)
        if actor is None:
            continue
        apply(actor, said)
        if world is not None and pid:
            from . import lives, names as names_mod

            actor.world_people_id = pid
            actor.heritage = people_name(world, pid) or actor.heritage
            if said["age"] or said["people_id"]:
                life = lives.roll(f"{location}|{ref}|spawn", phrase=roll_phrase(name, said))
                actor.appearance = names_mod.appearance_for(world, location, people_id=pid,
                                                            ref=ref, own=life.face)
            if said["people_id"]:
                taken = [a.true_name for a in scene.actors.values()
                         if getattr(a, "true_name", "") and a is not actor]
                taken += [a.name for a in scene.actors.values() if a is not actor]
                actor.true_name = names_mod.true_name(world, location, ref, taken,
                                                      people_id=pid)
        if said["gender"]:
            row["pronouns"] = str(actor.pronouns)
        if said["gender"] or said["age"] or said["people_id"]:
            row["from_words"] = dict(said)


def apply(actor, said: dict) -> bool:
    """Put the words' gender and pronouns on an actor who has none set. Returns whether
    anything changed. Never overwrites: a person the world or the player already gave a
    gender keeps it."""
    if actor is None or not said or not said.get("gender"):
        return False
    if str(getattr(actor, "gender", "") or "").strip():
        return False
    actor.gender = said["gender"]
    actor.pronouns = said.get("pronouns") or PRONOUNS.get(said["gender"], actor.pronouns)
    return True
