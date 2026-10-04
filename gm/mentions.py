"""Who the prose means: every mention of a person in a beat, attributed to a ref.

docs/who-the-prose-means.md. The engine never loses track of who is who; the prose is
where "who" goes soft, and a dozen checks used to GUESS from names and nouns which ref a
sentence meant ("the warrior", "the Korvu", a dead man and a living one both "thug").
This module declares it instead, in three steps:

  1. CODE FINDS the mentions — the name words of the people present, and descriptions
     ("the brute with the marked knuckles") whose head noun is a person word — in the
     narration only; speech is a character's to say.
  2. CODE SETTLES what is certain: a name whose words belong to exactly one person here.
  3. ONE SHORT CALL LABELS the rest, and checks the names: for each mention, which of
     the people here is meant, as an ENUM the sampler cannot leave (measured on this
     stack 2026-09-27: required properties and enums held 6 of 6; `contains` 0 of 6).

Why not ask the narrator to tag while writing (the note's first idea): markup taught only
by demonstration is unreliable at this size — 14% for LLaMA-2-7B citing from examples
(Huang et al. 2024), LLaMA3-8B "often failed to understand" a coreference-markup prompt —
and our own speaker tags needed the model's beats shown back tagged to reach 80%. A
closed multiple choice is the kind of task constrained output helps. The price is a
label AFTER writing, which lost to inline citation in ALCE (73.6 vs 26.7) — but there the
after-the-fact condition wrote without its sources; here the labeller is shown the cast
and the engine's tells.

The player never sees any of this: nothing here touches the text.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from . import speech

# On in the app. Off in the test suite (tests/conftest.py), as the interpreter is: most
# turn tests script the model's replies in order, and a label call would spend one. With
# it off, the code-settled names still attribute; descriptions stay unknown and every
# check falls back to its old guess.
ENABLED = True

# The most mentions one call labels. A beat that names more people than this is rare;
# the rest keep their code answer or stay unknown.
MAX_LABELLED = 12

NOBODY = "nobody"

_GLUE = {"the", "a", "an", "of", "with", "in", "on", "at", "and", "or", "to", "from",
         "by", "for", "who", "that", "whose"}

# Person words a description is headed by. The cast roles the booking door already
# reads (judgement._CAST_ROLES), the creature nouns (`narration._CREATURE_NOUNS`), and —
# added per scene — the head of every descriptor name here, every template and every
# people's name ("the Korvu").
_PERSON_WORDS = (
    "man|men|woman|women|boy|girl|child|lad|lass|youth|stranger|figure|person|fellow|"
    "folk|people|crowd|warrior|fighter|brawler|brute|bruiser|ruffian|thug|tough|hulk|"
    "giant|drunk|guard|guardsman|watchman|soldier|sailor|merchant|trader|vendor|keeper|"
    "innkeeper|barkeep|bartender|smith|elder|priest|priestess|servant|apprentice|"
    "farmer|drover|porter|scribe|beggar|urchin|noble|mercenary|sellsword|raider|"
    "bandit|brigand|outlaw|intruder|attacker|opponent|foe|enemy|challenger|veteran|"
    "beast|creature|monster|thing|abomination|fiend|demon|devil|animal|horror|"
    "clansman|clanswoman|swordsman|duellist|dockhand|rider|pirate|cutthroat")

# Not "that" (a relative pronoun as often as not: "shouting something that makes the
# nearby crowd flinch") and not the possessives ("missing his guard by a hair" is a
# stance): both read as people on the corpus, 2026-09-28.
_DETERMINERS = r"(?:the|a|an|this)"

# What may sit between the determiner and the head noun: describing words, never a
# function word — "a panicked scuffle as people" was read as one person.
_FILLER = (r"(?:(?!(?:as|of|and|or|but|who|whom|that|which|with|to|in|on|at|from|by|"
           r"for|into|onto|than|while|when|where|is|was|are|were)\b)"
           r"[A-Za-z][A-Za-z'’-]*\s+)")


@dataclass
class Mention:
    id: str
    sentence: str          # the sentence as written, narration only
    phrase: str            # the words that name or describe the person
    kind: str              # "name" or "description"
    code: str | None = None     # the ref code is certain of, names only
    model: str | None = None    # the labeller's ref, or NOBODY

    @property
    def ref(self) -> str | None:
        """Who this mention means, all told: the labeller's answer where it gave a
        person; else the code's. "nobody" from the labeller on a description is taken
        as it stands (a crowd, an absent man); on a name the code's answer holds."""
        if self.model and self.model != NOBODY:
            return self.model
        if self.model == NOBODY and self.kind == "description":
            return None
        return self.code

    @property
    def misnamed(self) -> bool:
        """The words name one person and the sentence means another: the prose put a
        name on the wrong person (stage 3)."""
        return bool(self.kind == "name" and self.code and self.model
                    and self.model not in (NOBODY, self.code))


@dataclass
class Attribution:
    mentions: list[Mention] = field(default_factory=list)
    labelled: bool = False
    seconds: float = 0.0
    error: str = ""
    raw: str = ""

    def _in(self, sentence: str) -> list[Mention]:
        key = _key(sentence)
        return [m for m in self.mentions if _key(m.sentence) == key]

    # Every narration sentence the attribution read, keyed — so "this sentence mentions
    # nobody" can be told from "this sentence was rewritten after I read it".
    sentences: set = field(default_factory=set)

    def refs_in(self, sentence: str) -> set[str] | None:
        """The refs a sentence mentions, or None when this sentence is not one the
        attribution saw (a later cut or rewrite changed it) — the caller's cue to fall
        back to its own guess."""
        if _key(sentence) not in self.sentences:
            return None
        return {m.ref for m in self._in(sentence) if m.ref}

    def who(self, sentence: str, phrase: str) -> str | None:
        """The ref of the mention whose words are `phrase` in `sentence`, if known."""
        p = _key(phrase)
        for m in self._in(sentence):
            if _key(m.phrase) == p or p in _key(m.phrase) or _key(m.phrase) in p:
                return m.ref
        return None

    def mentions_ref(self, ref: str) -> bool:
        return any(m.ref == ref for m in self.mentions)

    def mentioned_in(self, text: str, ref: str) -> bool | None:
        """Whether `text` — the beat as it stands NOW, after whatever was cut — mentions
        `ref` in a sentence this attribution read. True when one does; None when none
        does, since an unread sentence may still (the caller falls back)."""
        from .narration import _sentences

        for s in _sentences(speech.unquoted(str(text or ""))):
            refs = self.refs_in(s)
            if refs and ref in refs:
                return True
        return None

    def misnamed(self) -> list[Mention]:
        return [m for m in self.mentions if m.misnamed]

    def as_log(self) -> dict:
        return {
            "kind": "mentions",
            "mentions": len(self.mentions),
            "by_name": sum(1 for m in self.mentions if m.code),
            "labelled": sum(1 for m in self.mentions if m.model),
            "unknown": sum(1 for m in self.mentions if not m.ref),
            "misnamed": [{"phrase": m.phrase, "named": m.code, "meant": m.model,
                          "sentence": m.sentence[:160]} for m in self.misnamed()],
            "seconds": self.seconds,
            **({"error": self.error} if self.error else {}),
        }


def _key(text: str) -> str:
    """A sentence's identity, whoever split it: speech out (a caller may hand over the
    sentence with its quotation still in), case and spacing ignored."""
    return " ".join(speech.unquoted(str(text or "")).lower().split())


# --- step 1 and 2: code finds, code settles ------------------------------------------

def _name_words(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'’-]+", str(text or ""))
            if w.lower() not in _GLUE and len(w) > 2}


def _proper(name: str) -> bool:
    name = str(name or "").strip()
    return bool(name) and name[:1].isupper() and not name.lower().startswith(
        ("the ", "a ", "an "))


def _head(name: str) -> str:
    """A descriptor name's head noun: "man with the marked knuckles" -> "man", "second
    thug" -> "thug", "the watchman waving traffic through" -> "watchman".

    The one rule, `checks._people.head_of`. This copy used to take the last word before
    the first function word, and was wrong for 10 of the 12 opening companions — it
    stopped at no participle ("clearing", "minding") and no adverb ("ahead"), so the
    attribution looked for the watchman as "through" (item 4, 2026-09-28)."""
    from .checks._people import head_of

    head = head_of(name)
    if " " in head:
        head = head.split()[-1]
    return head.lower()


def people(scene) -> list[dict]:
    """Everyone here, as the labeller is shown them: ref, name, what they are."""
    out = []
    for ref, a in (getattr(scene, "actors", {}) or {}).items():
        what = []
        template = str(getattr(a, "from_template", "") or "")
        if template and template.lower() not in str(a.name).lower():
            what.append(template.replace("_", " "))
        race = str(getattr(a, "race", "") or "")
        if race and race.lower() not in str(a.name).lower():
            what.append(race)
        dead = bool(getattr(a, "hp", 1) < 0 or (hasattr(a, "has_state")
                                                 and a.has_state("state.down.dead")))
        out.append({"ref": ref, "name": str(a.name), "true": str(getattr(a, "true_name", "") or ""),
                    "pc": bool(getattr(a, "is_pc", False)), "what": ", ".join(what),
                    "dead": dead})
    return out


# Words in the content tables' person vocabularies that are no person on the page: a
# calloused "hand", and the occupation table's qualifiers ("day labourer", "herbal …").
_NOT_A_PERSON = frozenset({"hand", "caravan", "day", "herbal", "household", "market",
                           "minor", "tavern", "town", "travelling", "retired", "reeve's",
                           "smith's", "family", "kin", "crew"})
_VOCAB: list = []


def _vocabulary() -> frozenset:
    """Every person word the project already holds, as candidates for the finder: the
    narration checks' (`checks._people._PERSON`), the population's, and the occupations'
    ids and names (content/people). Measured on the beat-reader gold, 2026-10-03: with
    only the list above, "a lone laborer", "the clerk" and "the lamplighter" were never
    marked, so the reader could not be asked about them — the finder's recall, not the
    reader's, was the ceiling. Over-finding is cheap: "nobody" is an answer."""
    if not _VOCAB:
        words: set[str] = set()
        try:
            from rules import lives, population
            from .checks._people import _PERSON

            words |= {w.lower() for w in _PERSON}
            words |= {w.lower() for w in population._PERSON_WORDS}
            for occ in lives.tables()["occupations"]:
                words.add(str(occ["id"]).lower())
                words |= {w.lower() for w in str(occ["name"]).split()}
        except Exception:  # noqa: BLE001 — no content to hand: the list above stands
            return frozenset()
        _VOCAB.append(frozenset(w for w in words
                                if w not in _NOT_A_PERSON and re.fullmatch(r"[a-z][a-z-]+", w)))
    return _VOCAB[0]


def find(text: str, cast: list[dict]) -> list[Mention]:
    """Every mention of a person in the beat's narration, with the ref code is certain
    of for names. Speech is left out: a character may name anybody, here or not."""
    body = speech.unquoted(str(text or ""))
    from .narration import _sentences

    # Name words: every proper-name word of anybody here, shown or true.
    owners: dict[str, set[str]] = {}
    for p in cast:
        for held in (p["name"], p["true"]):
            if _proper(held):
                for w in _name_words(held):
                    owners.setdefault(w, set()).add(p["ref"])
    heads = set(_PERSON_WORDS.split("|")) | _vocabulary()
    for p in cast:
        if not _proper(p["name"]) and _head(p["name"]):
            heads.add(_head(p["name"]))
        for w in re.findall(r"[A-Za-z]+", p["what"]):
            if len(w) > 2:
                heads.add(w.lower())
    heads.discard("you")

    word = r"[A-Za-z][A-Za-z'’-]*"
    name_re = None
    if owners:
        alt = "|".join(sorted((re.escape(w) for w in owners), key=len, reverse=True))
        name_re = re.compile(rf"\b(?:{alt})(?:\s+(?:{alt}))*(?:['’]s)?\b", re.I)
    head_alt = "|".join(sorted((re.escape(h) for h in heads), key=len, reverse=True))
    desc_re = re.compile(
        rf"\b{_DETERMINERS}\s+{_FILLER}{{0,3}}?(?:{head_alt})(?:e?s)?(?:['’]s)?\b",
        re.I)

    out: list[Mention] = []
    for s in _sentences(body):
        taken: list[tuple[int, int]] = []
        found: list[tuple[int, Mention]] = []
        if name_re:
            for m in name_re.finditer(s):
                if not m.group(0)[:1].isupper():
                    continue       # a name is written with its capital; "borin" is not one
                words = _name_words(re.sub(r"['’]s$", "", m.group(0)))
                refs = set.intersection(*(owners.get(w, set()) for w in words)) \
                    if words else set()
                code = next(iter(refs)) if len(refs) == 1 else None
                # A name word beside a capitalised word nobody here owns is part of a
                # name the cast does not hold: "the ostler, Lyraea Lyraxys" is not
                # Aethorin Lyraxys, whose surname it shares (the corpus, 2026-09-28).
                before = re.search(r"([A-Z][A-Za-z'’-]+)\s+$", s[:m.start()])
                after = re.match(r"\s+([A-Z][A-Za-z'’-]+)", s[m.end():])
                for side in (before, after):
                    if side and side.group(1).lower() not in owners and not (
                            side is before and not s[:side.start()].strip()):
                        code = None
                taken.append(m.span())
                found.append((m.start(), Mention("", s, m.group(0), "name", code=code)))
        for m in desc_re.finditer(s):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            found.append((m.start(), Mention("", s, m.group(0), "description")))
        for _, mention in sorted(found, key=lambda x: x[0]):
            out.append(mention)
    for i, m in enumerate(out, 1):
        m.id = f"m{i}"
    return out


# --- step 3: one short call labels ---------------------------------------------------

def schema(ids: list[str], refs: list[str]) -> dict:
    choices = list(refs) + [NOBODY]
    return {"type": "object",
            "properties": {i: {"type": "string", "enum": choices} for i in ids},
            "required": list(ids)}


_SYSTEM = (
    "You read a passage of a story and say who each marked phrase refers to. The people "
    "present are listed with a code. For each marked phrase, answer the code of the person "
    "the sentence is actually about at that point — the one doing or undergoing what it "
    "says — even when the words used are the wrong name for them. The player's character "
    "is \"you\" in the story; a phrase can still refer to them. Answer \"nobody\" for a "
    "phrase that means nobody listed: a crowd, someone absent, a thing, or somebody new "
    "who is only being described for the first time.")

# One demonstration, not a page of rules (CLAUDE.md: instruction volume loses to
# demonstration volume). It carries the three hard cases: a description that is a named
# man, a name written onto the wrong person, and somebody the list does not hold — the
# measured error (2026-09-28, 3 of 4 wrong labels in a graded sample of 45): a newcomer
# described in passing was put on whoever was listed.
_EXAMPLE_USER = (
    "People present:\n"
    "pc: Ashka Verel — the player's character (\"you\")\n"
    "c4: Dunmar Oake — ferryman\n"
    "c5: the drover — a commoner\n\n"
    "Passage:\n"
    "[m1: The ferryman] swings his pole at your head. You duck, and [m2: the big man]'s "
    "momentum carries him into the rail. [m3: The drover] backs away, past [m4: a woman] "
    "with a basket of eels who has stopped to watch. [m5: Ashka Verel]'s pole cracks "
    "against the planks where you stood.")
_EXAMPLE_ASSISTANT = '{"m1": "c4", "m2": "c4", "m3": "c5", "m4": "nobody", "m5": "c4"}'


def messages(text: str, found: list[Mention], cast: list[dict], acting: str = "",
             facts: list[str] | None = None) -> list[dict]:
    lines = ["People present:"]
    for p in cast:
        desc = "the player's character (\"you\")" if p["pc"] else (p["what"] or "")
        if p["dead"]:
            desc = (desc + ", dead").strip(", ")
        lines.append(f"{p['ref']}: {p['name']}" + (f" — {desc}" if desc else ""))
    if acting:
        lines.append(f"\nIt is {acting}'s turn.")
    if facts:
        lines.append("What happened: " + " ".join(f for f in facts if f))
    marked = _marked(found)
    lines.append("\nPassage:\n" + marked)
    return [{"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _EXAMPLE_USER},
            {"role": "assistant", "content": _EXAMPLE_ASSISTANT},
            {"role": "user", "content": "\n".join(lines)}]


def _marked(found: list[Mention]) -> str:
    """The passage with each labelled phrase marked [mN: …], sentence by sentence."""
    by_sentence: dict[str, list[Mention]] = {}
    order: list[str] = []
    for m in found:
        if m.sentence not in by_sentence:
            order.append(m.sentence)
        by_sentence.setdefault(m.sentence, []).append(m)
    out = []
    for s in order:
        marked = s
        cursor = 0
        pieces = []
        for m in by_sentence[s]:
            i = marked.find(m.phrase, cursor)
            if i < 0:
                continue
            pieces.append(marked[cursor:i])
            pieces.append(f"[{m.id}: {m.phrase}]")
            cursor = i + len(m.phrase)
        pieces.append(marked[cursor:])
        out.append("".join(pieces))
    return " ".join(out)


def name_words_of(text: str) -> set[str]:
    """The capitalised name words in a piece of text, lower-cased: what "the wrong name
    is gone" is checked against."""
    return {w.lower() for w in re.findall(r"\b[A-Z][A-Za-z'’-]{2,}", str(text or ""))
            if w.lower() not in _GLUE} - {"you", "your", "the"}


def repair_schema(n: int) -> dict:
    keys = [f"s{i}" for i in range(1, n + 1)]
    return {"type": "object", "properties": {k: {"type": "string"} for k in keys},
            "required": keys}


def repair_messages(text: str, flagged: list[Mention], names: dict) -> list[dict]:
    """Rewrite only the sentences where a name sits on the wrong person."""
    asks = []
    for i, m in enumerate(flagged, 1):
        right = names.get(m.model, m.model)
        who = "the player's character, \"you\"" if m.model == "pc" else right
        asks.append(f"s{i}: {m.sentence}\n    \"{m.phrase}\" names {names.get(m.code, m.code)}, "
                    f"but this sentence is about {who}. Rewrite it so it refers to {who} "
                    f"(by name, as \"he\"/\"she\"/\"they\", or as \"you\" for the player) "
                    f"and changes nothing else.")
    return [
        {"role": "system", "content": (
            "You correct a single mistake in a story: a name written on the wrong person. "
            "Rewrite each numbered sentence exactly as instructed, keeping every other word "
            "the same. Never use the wrong name.")},
        {"role": "user", "content": "The passage, for context:\n" + text + "\n\nFix:\n"
                                    + "\n".join(asks)},
    ]


def attribute(text: str, scene, *, acting: str = "", facts: list[str] | None = None,
              chat=None, model: str = "", host: str = "", provider: str = "ollama",
              api_key: str = "") -> Attribution:
    """The beat's mentions and who each means. Never raises: a failed call leaves the
    code's answers and says why."""
    cast = people(scene)
    found = find(text, cast)
    result = Attribution(mentions=found)
    from .narration import _sentences

    result.sentences = {_key(s) for s in _sentences(speech.unquoted(str(text or "")))}
    ask = [m for m in found][:MAX_LABELLED]
    if not ENABLED or not ask or len(cast) < 2:
        return result
    refs = [p["ref"] for p in cast]
    if chat is None:
        from . import client

        chat = client.chat
    started = time.monotonic()
    try:
        reply = chat(messages(text, ask, cast, acting, facts), model, host,
                     as_json=True, think=False, temperature=0.0,
                     num_predict=24 + 12 * len(ask), provider=provider, api_key=api_key,
                     schema=schema([m.id for m in ask], refs))
        result.raw = reply.text
        answers = reply.json()
        for m in ask:
            got = str((answers or {}).get(m.id) or "")
            if got in refs or got == NOBODY:
                m.model = got
        result.labelled = True
    except Exception as exc:  # a failed label must never lose the turn
        result.error = f"{type(exc).__name__}: {str(exc)[:160]}"
    result.seconds = round(time.monotonic() - started, 2)
    return result
