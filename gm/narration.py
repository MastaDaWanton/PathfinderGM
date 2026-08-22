"""Checking the prose itself.

Narration is the surface the whole app is judged by, and the failures in it turned out to
be as systematic as the mechanical ones — which means they can be detected rather than
asked about. Measured across the play sessions in this repo's history:

  * **The examples were being copied verbatim.** "Two of them, come round the corner of
    the wall with saps out" — a sentence from `prompts.EXAMPLES` — appeared word for word
    in four separate turns. The demonstrations that teach the model the *shape* of a
    reply were teaching it the words too.
  * **The player's character kept slipping into third person.** "Kesst Vayr easily
    sidesteps the blow", "The blow catches Kesst Vayr on the jaw and sends *him*
    stumbling" — in narration addressed to "you", about a character the sheet never gave
    a pronoun for, so the model guessed and guessed inconsistently.
  * **Names arrived from nowhere.** The World Bible lesson, in its natural habitat: given
    freedom a model invents a person or a place and then treats it as settled fact.

Everything here returns findings for a targeted repair. Nothing rewrites prose on its own
except the person slips, where the substitution is unambiguous.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Six words is long enough that sharing one is copying rather than coincidence, and short
# enough to catch a lifted clause rather than only a whole sentence.
ECHO_LENGTH = 6

_WORD = re.compile(r"[a-z']+")
_QUOTED = re.compile(r"[\"“”'‘’][^\"“”]{0,300}?[\"“”]|'[^']{8,300}?'")
_SENTENCE = re.compile(r"[^.!?]+[.!?]?")

# Capitalised words that are not names.
_NOT_A_NAME = {
    "the", "a", "an", "and", "but", "or", "so", "if", "when", "while", "as", "at", "in",
    "on", "of", "for", "from", "to", "with", "without", "into", "onto", "over", "under",
    "behind", "before", "after", "above", "below", "beside", "between", "through",
    "you", "your", "yours", "he", "she", "it", "they", "him", "her", "them", "his",
    "hers", "its", "their", "there", "here", "this", "that", "these", "those", "what",
    "who", "whom", "why", "how", "then", "than", "now", "not", "no", "yes", "one", "two",
    "three", "his", "someone", "something", "nothing", "nobody", "anyone", "everyone",
    "i", "we", "us", "our", "my", "me", "mine",
    # Days, and the handful of common capitalised nouns that show up in rules prose.
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "ac", "hp", "dc", "cr", "cmb", "cmd", "gm",
}


@dataclass
class Finding:
    kind: str
    detail: str
    fix_hint: str = ""
    # How bad it is, not just that it is. A repair that removed twenty of twenty-one
    # borrowed phrases used to be thrown away, because one echo finding before and one
    # echo finding after is not "fewer findings" — measured on a model that reproduces
    # whole example paragraphs, where every repair was discarded and the plagiarism kept.
    weight: int = 1


@dataclass
class Review:
    findings: list[Finding] = field(default_factory=list)
    text: str = ""

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def score(self) -> int:
        """Total badness. What a repair has to reduce to be worth keeping."""
        return sum(f.weight for f in self.findings)

    def complaint(self) -> str:
        return " ".join(f.fix_hint or f.detail for f in self.findings)

    def as_log(self) -> list[str]:
        return [f"{f.kind}: {f.detail}" for f in self.findings]


def _words(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def _ngrams(text: str, n: int = ECHO_LENGTH) -> set[tuple]:
    w = _words(text)
    return {tuple(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def build_echo_index(*sources: str) -> set[tuple]:
    """The phrases the GM must not simply repeat back."""
    out: set[tuple] = set()
    for s in sources:
        out |= _ngrams(s)
    return out


def unquoted(text: str) -> str:
    """The narration with spoken dialogue removed.

    An NPC may perfectly well say the player's name out loud; the narrator may not use it
    to describe them.
    """
    return _QUOTED.sub(" ", text or "")


# A turn shorter than this is not a scene. Measured: with the old prompt the model
# returned a mean of 81 characters — "The air inside is stale, thick with the smell of
# parchment and ink." — because the examples it was shown averaged 102. The floor is set
# well under the length the examples now demonstrate (~600) so that a genuinely brief beat
# is allowed and only a one-liner is caught.
#
# Length is used here and nowhere else, deliberately. It is the one thing about prose that
# can be measured without lying about it: counting sensory words or scoring "vividness"
# with a regex is exactly the kind of metric CLAUDE.md records as having given confident,
# wrong answers about quality.
MIN_SCENE_CHARS = 320


def review(text: str, *, pc_name: str = "", echo_index: set[tuple] | None = None,
           known_names: set[str] | None = None, earlier: list[str] | None = None,
           min_chars: int = 0) -> Review:
    out = Review(text=text or "")
    if not text:
        return out

    # 5. A single line where a scene should be. Only asked of the turn narration —
    #    `min_chars` is left at zero for the consequence call, which is meant to be two or
    #    three sentences and would be made worse by padding.
    if min_chars and len(text.strip()) < min_chars:
        out.findings.append(Finding(
            "too-short", f"{len(text.strip())} characters, under {min_chars}",
            "This is one line where the player needs a scene. Take what just happened and "
            "carry it on: put them somewhere they can see and hear and feel, let the "
            "people and the place act back at them, and finish by giving them a real "
            "choice to make. Do not summarise — write it.",
        ))

    # 6. The turn is not handed back. Every example ends by asking the player something,
    #    and a turn that closes on a full stop tends to close the fiction with it.
    if min_chars and "?" not in text:
        out.findings.append(Finding(
            "no-hand-back", "does not ask the player anything",
            "End by handing the turn to the player with a real question about what they "
            "do next.",
        ))

    # 1. Lifted straight from the examples.
    if echo_index:
        shared = _ngrams(text) & echo_index
        if shared:
            # Every distinct run, not just one. Measured against a model that copies:
            # naming a single phrase let it rewrite that clause and leave the rest of the
            # borrowed paragraph standing, so the repair "failed" and the plagiarised
            # text was kept.
            phrases = [" ".join(p) for p in sorted(shared, key=len, reverse=True)[:4]]
            quoted = "; ".join(repr(p) for p in phrases)
            out.findings.append(Finding(
                "echoes-the-examples",
                f"reuses {len(shared)} phrases from the examples, "
                f"including {phrases[0]!r}",
                # The phrase is named. A repair the model cannot locate is a blind retry,
                # and a blind retry costs a whole regeneration — the same reason the ref
                # rejection lists the refs that do exist. The first version of this hint
                # said only "write this scene in your own words", and against a model
                # that had reproduced an entire example paragraph it simply did not work.
                f"You have copied wording from the examples: {quoted}. The examples show "
                f"the shape and the length of a reply, never its words — this scene is "
                f"not that scene. Rewrite it completely, about the same length, using "
                f"none of those phrases and describing what is actually in front of the "
                f"player now.",
                weight=len(shared),
            ))

    # 2. The player's character described in the third person.
    body = unquoted(text)
    if pc_name:
        for token in {pc_name, pc_name.split()[0]}:
            if re.search(rf"\b{re.escape(token)}\b", body):
                out.findings.append(Finding(
                    "third-person-pc", f"calls the player's character {token!r}",
                    f"You are narrating to the player. Their character is 'you', never "
                    f"'{token}' and never 'he' or 'she'. Only a character speaking aloud "
                    f"may use their name.",
                ))
                break

    # 3. Repeating a beat the player has already read.
    if earlier:
        recent = {s.strip().lower() for e in earlier[-6:]
                  for s in _SENTENCE.findall(e or "") if len(s.strip()) > 30}
        for s in _SENTENCE.findall(text):
            if s.strip().lower() in recent and len(s.strip()) > 30:
                out.findings.append(Finding(
                    "repeats-an-earlier-beat", f"repeats {s.strip()[:60]!r}",
                    "You have repeated a sentence the player has already read. Carry the "
                    "scene forward instead of restating it.",
                ))
                break

    # 4. A name from nowhere. The World Bible lesson: given freedom a model invents a
    #    person or a place and then treats it as settled fact.
    if known_names is not None:
        for name in invented_names(body, known_names):
            out.findings.append(Finding(
                "invented-name", f"names {name!r}, which is not in this world",
                f"{name!r} is not a person or place in this world. Use only the people "
                f"in the scene and the places the world contains, or describe someone "
                f"without naming them.",
            ))
            break

    return out


def invented_names(text: str, known: set[str]) -> list[str]:
    """Capitalised words that name nobody the world knows about.

    Conservative on purpose: a false positive costs a repair call and makes the prose
    blander, so sentence-initial words are skipped entirely and anything the world, the
    scene or the rules already contain is allowed.
    """
    allowed = {w.lower() for name in known for w in _WORD.findall(name.lower())}
    found: list[str] = []
    for sentence in _SENTENCE.findall(text or ""):
        tokens = re.findall(r"\b[A-Z][a-zA-Z'’-]{2,}\b", sentence)
        if not tokens:
            continue
        first = sentence.strip().split(" ")[0].strip(".,!?;:'\"")
        for tok in tokens:
            low = tok.lower()
            if low in _NOT_A_NAME or low in allowed:
                continue
            if tok == first:                     # start of a sentence proves nothing
                continue
            if low not in found:
                found.append(tok)
    return found
