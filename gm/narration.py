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
import statistics
from collections import Counter
from dataclasses import dataclass, field

# Six words is long enough that sharing one is copying rather than coincidence, and short
# enough to catch a lifted clause rather than only a whole sentence.
ECHO_LENGTH = 6

_WORD = re.compile(r"[a-z']+")
# The single-quote alternative pairs on word boundaries, because an apostrophe inside a
# word is never a closing quote. The old form (`'[^']{8,300}?'`) could not cross
# "that's" or "I'll", so a boatman's speech riddled with contractions was carved at the
# wrong boundaries and "between you and me" leaked into narration — where the
# first-person detector read it as the narrator having a body. An opener must follow
# whitespace (or start); a closer must precede whitespace, punctuation or the end.
_QUOTED = re.compile(
    r"[\"“”‘][^\"“”]{0,300}?[\"“”]"
    r"|(?:^|(?<=\s))'[^\n]{2,300}?'(?=$|[\s.,!?;:)\]])")
_SENTENCE = re.compile(r"[^.!?]+[.!?]?")

# Capitalised words that are not names.
# The nouns a place is named with. A capitalised token beside one of these — "the
# Weaver's Rest", "Salt Market", "Harrow Bridge" — is somewhere, not somebody, and the
# un-namer must leave it be: measured at the table, 2026-09-06, "The Weaver's Rest is a
# place for those seeking rest" shipped as "The Weaver's the stranger is a place…", and
# the cast ledger then booked "Weaver's the stranger" as a person.
#
# Only the nouns that are never a surname. "Vale", "Hill", "Wood", "Bank", "Reach",
# "Ford", "Moor" are all people's names in this app's own tests ("Serath Vale"), and a
# list that held them turned a person into a place.
PLACE_NOUNS = frozenset({
    "rest", "inn", "tavern", "alehouse", "market", "square", "street", "lane", "road",
    "row", "gate", "gatehouse", "bridge", "district", "quarter", "ward", "hall",
    "yard", "bazaar", "temple", "shrine", "tower", "keep", "crossing", "wharf", "dock",
    "docks", "quay", "stairs", "landing", "chapel", "abbey", "guildhall", "exchange",
    "cellars", "plaza", "arcade", "colonnade",
})

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
# parchment and ink." — because the examples it was shown averaged 102.
#
# Raised from 320 on the table's instruction: "dialogue and general world descriptions can
# increase in length". 320 was set as a floor well *under* what the examples demonstrate,
# so that a genuinely brief beat survived — and it turned out to be doing nothing, because
# a 20-turn town run measured a mean of 839 characters and a minimum of 559. Every turn
# already cleared the old floor by a wide margin. 600 is what the examples actually
# demonstrate, which makes it a floor that can bite.
#
# Enforced at the sampler through `turn_schema`, not asked for in words — which is why it
# works. CLAUDE.md's rule is that instruction volume loses to demonstration volume; a
# `minLength` is neither, it is the grammar.
#
# The fight keeps its own numbers below. This is the half the table asked to grow.
#
# And asked again, 2026-09-04: "i want more text and more description per generation",
# and what was measured that hour rewrote the paragraph above. For the prose model
# now in use (gemma-4 12B) a minLength in the grammar does compile, and does harm:
# held inside a string it had finished, the model wrote the rest of the object into
# it escaped — the suggestions key, the intents key — on three turns in four, which
# `cut_schema_bleed` trimmed back to a beat UNDER the floor. So the prose call
# carries no floor in its grammar (`prompts.prose_schema` says why) and the floor
# lives here: `review` reports a short beat as `too-short` with the fix named, and
# the repair call that follows writes the room — the repo's sanctioned shape, detect
# in code and repair with a targeted call. Measured: three beats of 703-791
# characters were each repaired to 1,469-1,579, with the brief's new paragraphs of
# the place (`prompts.place_in_its_own_words`) as the material.
#
# The floor may therefore sit ABOVE what the examples demonstrate. Growing the
# examples instead was tried first and reverted the same hour: the model copied
# their FURNITURE, and a common room got "the heavy oak desk you just searched".
MIN_SCENE_CHARS = 800

# In a fight the pace of the prose is the pace of the fight. Three or four sentences is
# the right answer and 900 characters of weather is not, so the floor drops and there is a
# ceiling as well — the only place in this module where prose is capped, because a turn
# that takes four sentences to reach the threat has already lost it.
MIN_COMBAT_CHARS = 140
# Double the length the combat examples actually demonstrate (they average 299), which is
# generous for a turn that needs an extra clause and still catches a scene-setter that has
# wandered into a fight. The first value was 700, which was above every example in the
# file and therefore caught nothing at all.
MAX_COMBAT_CHARS = 600

# The GM asking the player to do the GM's job. Measured in live play (2026-08-22,
# llama3.1:8b, zero rejections on every turn — this is the narrator's own drift and not
# the fallback's): three consecutive beats ended "What do you see?", "What do you notice
# next?" and "What do you feel next?". The player had asked to follow somebody into a
# room; describing that room is the only thing the narrator is for.
#
# The rule that produced it is one line up the file — a turn must end in a question —
# and the model satisfied it the cheapest way available. Instructing it not to is the
# fix CLAUDE.md records as never having held, so the shape is detected instead.
_PERCEPTION = (r"see|notice|feel|hear|smell|taste|sense|observe|spot|perceive|find|"
               r"think|believe|remember|recall|imagine|picture|want|wish|expect")
_ASKS_TO_NARRATE = re.compile(
    # Either "what/how ... you ... <perceive>", or the same request with the verb in
    # front of the pronoun — "What does the room look like to you now?"
    rf"\b(?:what|how|which)\b(?:"
    rf"[^.?!]{{0,70}}\byou\b[^.?!]{{0,40}}\b(?:{_PERCEPTION})\b"
    rf"|[^.?!]{{0,70}}\blooks?\s+like\b"
    rf")",
    re.I)
# "What do you want to do?" reaches for `want` and is a perfectly good hand-back: the
# thing being asked for is still an action. Only the perception itself is refused.
_STILL_AN_ACTION = re.compile(
    # What follows "to" has to be a verb. Without the lookahead, "What does the room
    # look like to you now?" matched on "like to you" and was waved through as an
    # action — the exemption swallowing the very case it sits next to.
    r"\b(?:want|wish|like|choose|mean|try|care|hope)\w*\s+to\s+"
    r"(?!you\b|him\b|her\b|them\b|it\b|me\b|us\b|the\b|an?\b)\w+", re.I)
_QUESTION = re.compile(r"[^.?!]*\?")


def _bad_hand_back(sentence: str) -> bool:
    if any(q in sentence for q in "\"“”"):
        return False        # an NPC may ask the player anything they like
    return bool(_ASKS_TO_NARRATE.search(sentence)
                and not _STILL_AN_ACTION.search(sentence))


def _closing_question(text: str):
    """The hand-back itself: the final sentence, and only when it is a question.

    Anything earlier is dialogue or rhetoric — "'What do you need?' you ask the
    guildhand" is the player's character speaking, not the narrator handing over, and
    judging it as the hand-back would fix the wrong sentence.
    """
    if not (text or "").rstrip().endswith("?"):
        return None
    questions = [m for m in _QUESTION.finditer(text) if m.group().strip()]
    return questions[-1] if questions else None


def asks_player_to_narrate(text: str) -> str:
    """The closing question, if it asks the player to describe the world. Else ""."""
    found = _closing_question(text)
    if found is None:
        return ""
    last = found.group().strip()
    return last if _bad_hand_back(last) else ""


def fix_hand_back(text: str) -> tuple[str, str]:
    """Swap a describe-it-for-me question for the one the examples all use.

    A backstop, not the repair: `review` raises this as a finding first and the model
    gets a chance to write the description it skipped. If that rewrite fails the turn
    still must not ship asking the player what they can see, and replacing the question
    is always safe — every example in the prompt ends on this exact sentence.

    By span, never `str.replace`: the same trap `cut_outcome_claims` documents, where a
    whitespace shift between the extracted sentence and the text it came from turns the
    replacement into a silent no-op.
    """
    span = _closing_question(text)
    if span is None or not _bad_hand_back(span.group().strip()):
        return text, ""
    gone = span.group().strip()
    fixed = (text[:span.start()] + span.group()[:len(span.group())
                                                - len(span.group().lstrip())]
             + "What do you do?" + text[span.end():])
    return " ".join(fixed.split()), gone


# --- the decoding stutter ---------------------------------------------------------------
#
# A period, a space, and a lowercase continuation: "making them feel almost. alive",
# "some sort of. marking?", "'My chest is. muscular". Fourteen instances measured across
# the live saves, one of which broke a *detector* — the stray period in "My chest is.
# muscular" is why `_owner_of` had to read ownership backwards.
#
# Two different model errors share the surface and need opposite repairs. When the word
# before the period cannot end an English sentence ("almost.", "of.", "is.") the period
# is a stutter and is removed. When it could ("He stops. dead ahead, the bridge looms")
# deleting the period would silently merge two sentences into a fluent run-on that says
# something else — so the following letter is capitalised instead, which repairs the
# dropped-capital case and is harmless if the model really had finished the sentence.
_ABBREVIATIONS = {"mr", "mrs", "dr", "st", "vs", "etc", "ft", "no"}
_NEVER_ENDS_A_SENTENCE = {
    "a", "an", "the", "of", "to", "and", "or", "but", "nor", "is", "was", "are",
    "were", "be", "being", "been", "am", "has", "have", "had", "do", "does", "did",
    "will", "would", "shall", "should", "can", "could", "may", "might", "must",
    "than", "as", "at", "by", "for", "from", "in", "into", "on", "onto", "with",
    "without", "almost", "very", "quite", "rather", "so", "too", "such", "about",
    "their", "his", "her", "its", "your", "my", "our", "some", "any", "each",
    "every", "if", "when", "while", "because", "although", "whose", "which",
}
# One period only — "and then... nothing" is deliberate trailing, and eating a dot out
# of an ellipsis mangles it.
_STUTTER = re.compile(r"([A-Za-z']+)(?<!\.)\.(?!\.)(\s+)([a-z])")


def destutter(text: str) -> str:
    """Repair the mid-sentence stray period, both ways it happens."""
    def _fix(m: re.Match) -> str:
        word = m.group(1).lower().lstrip("'")
        if word in _ABBREVIATIONS:
            return m.group(0)
        if word in _NEVER_ENDS_A_SENTENCE:
            return f"{m.group(1)}{m.group(2)}{m.group(3)}"
        return f"{m.group(1)}.{m.group(2)}{m.group(3).upper()}"

    return _STUTTER.sub(_fix, text or "")


# --- the model looping -------------------------------------------------------------------

# A sentence that begins speech. Straight and curly doubles always; a single quote only
# when it follows a word boundary, because an apostrophe is intra-word and almost every
# sentence of prose has one.
_OPENS_SPEECH = re.compile(r"(?:^|\s)[\'‘\"“]")


# Above this share of a beat's sentences already read, the beat is the last one again.
REGURGITATED_SHARE = 40


def _same_words(sentence: str) -> str:
    """A sentence reduced to its words, so a re-quoting with the punctuation moved —
    "'And the guards at the main gate are. '" for "…and the guards at the main gate
    are…" — is the same sentence."""
    return " ".join(re.findall(r"[a-z0-9']+", (sentence or "").lower()))


def drop_repeated_beats(text: str, earlier: list[str] | None) -> tuple[str, int]:
    """Delete sentences the player has already read, mechanically.

    Promotion of `repeats-an-earlier-beat` to the deterministic tier: measured across all
    seven saves, 6 of 11 repeat findings shipped unrepaired — three consecutive turns of
    one campaign ended on the identical clause "...labels and bottles before turning to
    you." Deleting a repeat is always safe *in narration*: the player has read it.

    Spoken repetition is exempt. A guard repeating his refusal word for word when the
    player tries the door twice is characterisation, not degeneration, and the sentence
    that carries quote marks is his to repeat.
    """
    if not text or not earlier:
        return text or "", 0
    recent = {_same_words(s) for e in earlier[-6:]
              for s in _SENTENCE.findall(e or "") if len(s.strip()) > 30}
    recent.discard("")
    if not recent:
        return text, 0
    sentences = [s.strip() for s in _SENTENCE.findall(text) if s.strip()]
    repeated = [len(s) > 30 and _same_words(s) in recent for s in sentences]
    # A beat that is mostly the last beat again is not a guard repeating himself,
    # whatever the quote marks say. Reported at the table, 2026-09-06: "I thank her"
    # came back as the previous two beats re-quoted nearly word for word, and every
    # repeated sentence sat inside her speech, so the speech exemption shipped it.
    regurgitated = (sum(repeated) >= 2
                    and sum(repeated) * 100 >= REGURGITATED_SHARE * len(sentences))
    kept: list[str] = []
    cut = 0
    prev_cut = False
    for s, again in zip(sentences, repeated):
        if again and (regurgitated or not _OPENS_SPEECH.search(s)):
            cut += 1
            prev_cut = True
            continue
        # A cut sentence's closing quote lands at the head of the next one — "head. '
        # She hands you" splits as "' She hands you" — and an unmatched leading quote
        # after a cut is that orphan.
        if prev_cut and s[:1] in "'‘’\"“”" and s.count(s[0]) % 2 == 1:
            s = s[1:].lstrip()
        prev_cut = False
        kept.append(s)
    if not kept or not cut:
        # Cutting everything would be worse than repeating; and zero cuts means the
        # original spacing is kept rather than re-joined for nothing.
        return text, 0
    return " ".join(kept), cut


# --- people from nowhere: the deterministic end of it ------------------------------------
#
# `invented-name` shipped unrepaired 23 of 41 times across the live saves — worse than a
# coin toss — and the people it shipped became fixtures: Kaida persists across eight
# turns of one campaign, Vorgath across a dozen of another, neither ever an actor the
# engine knows. The rewrite is still asked for first; this is what happens when it loses,
# on the same bargain as `right_body`: never invent, only stop asserting. The module
# already states the trade — a bland sentence is far cheaper than a person who does not
# exist entering the campaign.
_STRANGER_WORDS = ("the stranger", "the onlooker", "the passer-by")
# A name directly after one of these is a *place* being named, and "the corner of the
# stranger" is garbage. The sentence is cut instead, which is always safe. Deliberately
# NOT to/at/from/in — those precede people constantly ("she glances at Vorgath", "he
# confides in Kaida"), and the first version cut a perfectly repairable glance because
# "at" was on the list.
_PLACE_BEFORE = re.compile(r"\b(?:of|into|near|toward|towards)\s+$", re.I)
_CAP_TOKEN_BEFORE = re.compile(r"([A-Z][a-zA-Z'’-]{2,})\s+$")


def unname_strangers(text: str, known: set[str]) -> tuple[str, list[str]]:
    """Replace first-appearance invented people with an unnamed descriptor.

    Names the engine knows stay; so do a legacy campaign's established people (the caller
    widens `known` with them). Everything else is somebody the model conjured this turn,
    and they leave before the player ever meets them — which is also what stops them
    recurring, because the transcript the next turn reads never contains them.

    Span edits on the original text, never a sentence re-join: the first version split
    into sentences and glued them back with spaces, and "Stay back, Kaida!' the guard
    shouts" came out with a stray space inside the closing quote.
    """
    found = invented_names(text, known)
    if not found:
        return text, []
    known_words = {w.lower() for name in known for w in _WORD.findall(name.lower())}

    alt = "|".join(re.escape(n) for n in found)
    run = re.compile(rf"\b(?:{alt})(?:\s+(?:{alt}))*(['’]s)?\b")

    # (start, end, matched, possessive) in absolute offsets, with each match extended
    # leftward over adjacent capitalised tokens the detector's sentence-initial blind
    # spot missed — "Serath Vale" where only "Vale" was flaggable is one person, and
    # half-replacing him gave "Serath the stranger".
    spans: list[tuple[int, int, str, str]] = []
    for m in run.finditer(text):
        start = m.start()
        while True:
            lead = _CAP_TOKEN_BEFORE.search(text[:start])
            if not lead:
                break
            token = lead.group(1)
            stem = re.sub(r"['’]s$", "", token.lower())
            # The stem too, or "There's Glimble" swallows "There's" — "there" is on the
            # not-a-name list but "there's" is not.
            if (token.lower() in known_words or stem in known_words
                    or token.lower() in _NOT_A_NAME or stem in _NOT_A_NAME):
                break
            start = lead.start(1)
        spans.append((start, m.end(), text[start:m.end()], m.group(1) or ""))

    if not spans:
        return text, []

    # Sentences that name a place get cut whole rather than repaired into nonsense.
    sentence_spans = [sm.span() for sm in _SENTENCE.finditer(text)]

    def _sentence_of(pos: int) -> tuple[int, int]:
        for lo, hi in sentence_spans:
            if lo <= pos < hi:
                return lo, hi
        return pos, pos

    cut: list[tuple[int, int]] = []
    keep: list[tuple[int, int, str, str]] = []
    for start, end, matched, poss in spans:
        lo, hi = _sentence_of(start)
        if _PLACE_BEFORE.search(text[lo:start]):
            # Take the orphan closing quote with the sentence, or "'There's Glimble at
            # the corner of Wind and Elm.'" leaves a floating "'" glued to what remains.
            while hi < len(text) and text[hi] in "\"“”'‘’ ":
                hi += 1
            if (lo, hi) not in cut:
                cut.append((lo, hi))
        else:
            keep.append((start, end, matched, poss))

    by_person: dict[str, str] = {}

    def _descriptor(matched: str) -> str:
        key = re.sub(r"['’]s$", "", matched).strip().lower()
        if key not in by_person:
            by_person[key] = _STRANGER_WORDS[min(len(by_person),
                                                 len(_STRANGER_WORDS) - 1)]
        return by_person[key]

    replaced = sorted({matched for _, _, matched, _ in spans})
    # A cut leaves one space behind, not nothing — gluing "leans in." to "He waits."
    # is what nothing produced.
    edits: list[tuple[int, int, str]] = [(lo, hi, " ") for lo, hi in cut]
    for start, end, matched, poss in keep:
        if any(lo <= start < hi for lo, hi, _ in edits):
            continue                       # inside a sentence already being cut
        descriptor = _descriptor(matched)
        before = text[:start].rstrip()
        if before.endswith(","):
            # Direct address — "Stay back, Vorgath!" — takes the bare word.
            replacement = descriptor.split()[-1]
        else:
            replacement = descriptor
            head = text[max(0, start - 24):start]
            if not head.strip() or re.search(r"[.!?]\s*[\"“”'‘’]?\s*$", head):
                replacement = replacement[0].upper() + replacement[1:]
        stripped = re.sub(r"['’]s$", "", matched)
        replacement += poss if matched.endswith(("'s", "’s")) and stripped else ""
        edits.append((start, end, replacement))

    out = text
    for start, end, replacement in sorted(edits, key=lambda e: -e[0]):
        out = out[:start] + replacement + out[end:]
    out = re.sub(r"  +", " ", out).strip()
    if not out or not re.search(r"[a-zA-Z]", out):
        return text, []
    return out, replaced


def established_names(earlier: list[str] | None, minimum: int = 2) -> set[str]:
    """Names woven into the campaign before the un-naming backstop existed.

    A capitalised token appearing in `minimum`+ distinct earlier GM beats is part of this
    campaign's fiction — Vorgath and Lyra are in sixty turns of one live save — and
    retroactively scrubbing an established person mid-conversation is its own
    people-out-of-thin-air weirdness, run backwards.

    Player beats deliberately do not count. The measured Glimble case shipped "Head to
    Glimble's immediately" as a suggestion chip; one click would have laundered the
    invention into permanence. And because `unname_strangers` stops new names ever
    shipping once, this set can only be reached by pre-fix saves — which is the right
    set, and shrinks to nothing on campaigns started after today.
    """
    counts: dict[str, int] = {}
    for beat in (earlier or []):
        for tok in set(re.findall(r"\b[A-Z][a-zA-Z'’-]{2,}\b", beat or "")):
            counts[tok] = counts.get(tok, 0) + 1
    return {t for t, n in counts.items() if n >= minimum}


# --- the narrator in the scene: the deterministic end of it ------------------------------

# Sentences that report a written thing — a note, a sign, an inscription — legitimately
# carry first person in narration and are not the narrator slipping in.
_WRITTEN_ARTIFACT = re.compile(
    r"\b(?:reads?|inscribed|carved|etched|scrawled|written|note|letter|sign|plaque)\b",
    re.I)
_FIRST_TO_SECOND = {
    "me": "you", "my": "your", "myself": "yourself",
    "i": "you", "i'm": "you're", "i'll": "you'll", "i've": "you've", "i'd": "you'd",
}
_FP_TOKEN = re.compile(r"\b(?:i'm|i'll|i've|i'd|i|me|my|myself)\b", re.I)


def second_person_narrator(text: str) -> tuple[str, list[str]]:
    """Turn the narrator's first person back onto the player, where it can be done
    safely.

    The measured cases, in the order they taught this function: "Lyra stands beside me,
    her gaze scanning every detail of my image" (me/my — the original), then "As I push
    aside the tangled branches and leaves, I find myself face-to-face with a dense
    thicket" — which shipped, because a sentence containing nominative I used to be
    skipped whole on the theory that "I draw my blade" half-swapped would be worse than
    the defect. The theory was right and the conclusion wrong: the fix for
    half-swapping is swapping the *whole* set — I/I'm/I'll/I've/I'd with me/my/myself —
    with the two verb agreements English actually demands (am→are, was→were), so no
    sentence can come out half-turned.

    Speech keeps its first person by span, not by guesswork: any sentence overlapping a
    `_QUOTED` match is left alone, which protects multi-sentence dialogue in single
    quotes — the shape the old per-sentence quote-character checks could not see.
    Written artifacts (a note that reads "I will come at dusk") stay exempt, and "mine"
    stays unswapped: it is a hole in the ground far more often than a pronoun in this
    genre.
    """
    if not text:
        return text or "", []
    protected = [m.span() for m in _QUOTED.finditer(text)]
    out: list[str] = []
    swapped: list[str] = []
    changed = False
    for m in _SENTENCE.finditer(text):
        s, lo, hi = m.group(0), m.start(), m.end()
        touches_speech = any(qlo < hi and lo < qhi for qlo, qhi in protected)
        if (not touches_speech
                and '"' not in s and "“" not in s and "”" not in s
                and not _OPENS_SPEECH.search(s)
                and not _WRITTEN_ARTIFACT.search(s)):
            first_alpha = next((i for i, ch in enumerate(s) if ch.isalpha()), -1)

            def _swap(mt: re.Match, _first: int = first_alpha) -> str:
                low = mt.group(0).lower()
                new = _FIRST_TO_SECOND[low]
                swapped.append(low)
                # Sentence-position-aware, not case-aware: "I" is capitalised wherever
                # it stands, so copying its case would write "as You push" mid-clause.
                return new.capitalize() if mt.start() == _first else new

            fixed = _FP_TOKEN.sub(_swap, s)
            fixed = re.sub(r"\b([Yy]ou) am\b", r"\1 are", fixed)
            fixed = re.sub(r"\b([Yy]ou) was\b", r"\1 were", fixed)
            if fixed != s:
                changed = True
            s = fixed
        out.append(s.strip())
    if not changed:
        return text, []
    return " ".join(out), sorted(set(swapped))


# What every worked example in `prompts.EXAMPLES` ends on, word for word. Kept as one
# constant because two places now write it and a hand-back that differed between them
# would read as two different narrators.
HAND_BACK = "What do you do?"


def ensure_hand_back(text: str) -> tuple[str, bool]:
    """Give the turn back to the player when it has forgotten to.

    `fix_hand_back` handles the *wrong* question — "What do you see?", the GM asking the
    player to do the GM's job. It cannot handle a missing one: `_closing_question` returns
    None the moment the text does not end in "?", so it bows out of exactly the case
    `no-hand-back` names.

    Measured over fourteen turns of one live campaign: six shipped without a closing
    question, every one of them logged `unrepaired: no-hand-back`. The model was asked to
    rewrite and its rewrite lost, six times out of six.

    Appending is always safe, which is what makes this a backstop rather than a guess —
    every example in the prompt ends on this exact sentence, and a turn that has run out
    of things to say still has to hand over.
    """
    said = (text or "").rstrip()
    if not said or said.endswith("?"):
        return text, False
    # A turn that trails off mid-sentence gets its full stop as well; "almost. alive"
    # and friends are what the model does when it runs out of budget.
    #
    # Closing quote marks do not count as missing punctuation. A beat that ends on
    # "...but what it is remains unclear.'" already has its stop *inside* the speech, and
    # adding another produced ".'. What do you do?".
    if said.rstrip("\"“”'‘’")[-1:] not in (".", "!", ""):
        said += "."
    return f"{said} {HAND_BACK}", True


# --- prose that contradicts the engine ---------------------------------------------
#
# The third law says the narrator is fed tells and nothing else about mechanics. It does
# not say the narrator cannot write mechanics anyway, and when a turn produces no tells
# there is nothing to contradict it with — so it invents.
#
# Reported 2026-09-17, and the day's `attack: actor null` bug made it vivid: seven
# rejected attempts, no roll of any kind, and prose describing a guard whose "scream is
# cut short as the air is forced from his lungs" and who "collapses forward into the
# dirt" — while the scene list beside it showed that guard at 11/11, unhurt, standing.
# The player's own summary: "no rolls were done at all and combat never happened."
#
# Detected by comparing what the prose asserts against what the engine holds, because
# every other shape of fix on this project has failed: the brief already tells the model
# who is alive, and instructing it not to kill them is the instruction-volume trap.
#
# Bound to a name, never floating. "his voice dies", "the sound falls away" and "the
# light collapses" are all ordinary prose, and a detector that read the verb without
# asking who it was about would refuse the narrator its own language.
_FELLED = re.compile(
    r"\b(?:dies|died|dying|dead|killed|kills|slain|slays|lifeless|corpse|body|"
    r"collapses?|collapsed|crumples?|crumpled|slumps?|slumped|"
    r"drops?\s+(?:dead|to\s+the\s+(?:ground|floor|cobbles|dirt))|"
    r"falls?\s+(?:dead|lifeless|limp|still|unconscious)|"
    r"goes\s+(?:limp|still|slack)|"
    r"hits?\s+the\s+(?:ground|floor|cobbles|dirt))\b", re.I)

# A place going about its business. Harmless prose, and the one thing a square with
# bodies in it is not doing.
#
# Reported 2026-09-17 with the scene list beside it — `man (c7) - dead`, `guards (c8) -
# dead`, the crowd scattering — under a turn that opened: "The market of Vyrakon is a
# cacophony of commerce - the rhythmic thud of hammers on anvils, the sharp cries of
# vendors hawking salt and textiles, and the heavy, earthy scent of livestock." The
# player's verdict: "the place was a screaming mess and it's doubtful anyone would have
# been shopping."
#
# The model was not ignorant of it — the same paragraph later names "the fleeing
# bystanders" and "the dying guard". It opened on a stock description of the location
# and only then remembered the scene, which is why this is a finding about the prose
# rather than a gap in the brief.
_BUSINESS_AS_USUAL = re.compile(
    r"\b(?:cacophony\s+of\s+commerce|bustling|bustle|hawking|hawkers?|haggling|haggles?|"
    r"browsing|shoppers?|shopping|going\s+about\s+(?:their|its)\s+business|"
    r"business\s+as\s+usual|the\s+usual\s+(?:crowd|din|noise|trade)|"
    r"trade\s+continues|market\s+day|merry|cheerful|laughter\s+(?:rings|drifts)|"
    r"idle\s+chatter|lively)\b", re.I)

# Hurt, short of felled. Kept separate because the threshold is different: a narrator
# may say somebody is bleeding when they have taken a point, and may not say it when
# nothing has touched them at all.
_WOUNDED = re.compile(
    r"\b(?:wounded|bleeding|bleeds|blood\s+(?:pours|runs|spurts|sprays)|"
    r"staggers?|staggered|reels?|reeled|cries?\s+out|screams?|howls?\s+in\s+pain|"
    r"shattered|broken|cracks?\s+(?:open|apart)|gashed|torn\s+open)\b", re.I)


def _name_stems(name: str) -> list[str]:
    """The distinctive words of a name, singular and plural both.

    Matched on words rather than the whole string because the scene calls somebody "the
    crier working through the notices" and the prose calls them "the crier" — comparing
    full strings sees two different people.

    And on stems because of the case this was written for: the scene named the actor
    `guards` and the prose wrote "the guard's scream is cut short". Without the stem the
    detector reads those as two different people and passes a death it should have
    caught, which is exactly the way a checker fails silently.
    """
    stems = []
    for w in _WORD.findall(name.lower()):
        w = w.strip("'")
        if len(w) <= 3 or w in _NOT_A_NAME:
            continue
        stems.append(w[:-1] if w.endswith("s") and len(w) > 4 else w)
    return stems


def _sentences_about(text: str, name: str) -> list[str]:
    """Every sentence in already-unquoted prose that names this actor."""
    stems = _name_stems(name)
    if not stems:
        return []
    # Built with `chr(92)` rather than typed. The first version of this line went
    # in through a shell heredoc and both word boundaries arrived as literal
    # backspace bytes - CLAUDE.md's "bash heredocs mangle backslashes", which it
    # says has already cost this project real time twice. The regex still compiled
    # and matched nothing, so the detector passed a death it should have caught
    # and looked from the outside exactly like a detector that worked.
    edge = chr(92) + "b"
    hit = re.compile(edge + r"(?:" + "|".join(re.escape(x) for x in stems)
                     + r")(?:s|es)?" + edge, re.I)
    return [s for s in _SENTENCE.findall(text or "") if hit.search(s)]


def contradicts_state(text: str, state: dict | None) -> list[tuple]:
    """Claims in the prose that the engine says are not true.

    `state` is `{name: {"alive": bool, "hurt": bool}}`, built by the caller off the live
    scene. Returns `(name, claim, sentence)` for each contradiction, so the repair can
    quote the sentence back rather than describe the problem in the abstract.
    """
    if not text or not state:
        return []
    # Speech stripped from the whole passage before anything is split into sentences. A
    # character may perfectly well SAY somebody is dead, and a quotation routinely runs
    # across a full stop — `The crier shouts, "The guard is dead, he collapsed!"` is two
    # sentences to the splitter and one utterance to a reader, so stripping per sentence
    # let the second half through as if the narrator had asserted it.
    bare_text = unquoted(text)
    out = []
    for name, how in state.items():
        if not isinstance(how, dict):
            continue
        for sentence in _sentences_about(bare_text, str(name)):
            bare = sentence
            if how.get("alive") and _FELLED.search(bare):
                out.append((name, "down or dead", sentence.strip()))
                break
            if not how.get("hurt") and _WOUNDED.search(bare):
                out.append((name, "hurt", sentence.strip()))
                break
    return out


def review(text: str, *, pc_name: str = "", echo_index: set[tuple] | None = None,
           known_names: set[str] | None = None, earlier: list[str] | None = None,
           min_chars: int = 0, max_chars: int = 0, alone: bool = False,
           pronouns: str = '', others: tuple = (), gender: str = '',
           state: dict | None = None, deaths: list[dict] | None = None,
           pull: dict | None = None) -> Review:
    out = Review(text=text or "")
    if not text:
        return out

    # 0d. The one open matter nearest to hand has gone unmentioned too long, and this
    #     beat did not carry it either. `pull` is `rules.cards.thread_to_pull`'s pick —
    #     chosen in code by criteria count, never by asking the model (Drama Llama let a
    #     model judge salience and its authors reported the triggers misfiring) — and it
    #     is only handed over out of fights, so this cannot cost a rewrite mid-combat.
    #     The hint names the matter and one fact of it; no deterministic backstop,
    #     because an appended anchor sentence would be the formula this file has just
    #     stopped writing twice over.
    #     Quests only. Measured on the first run after this shipped: eight fires in
    #     fifty turns, six of them on the world's own strain cards ("Volatility between
    #     winged clans and flightless communities"), and the rewrites came back all but
    #     unchanged — a fact about a town's politics is colour the beat may pass over;
    #     a task the player took on and has not heard of for ten turns is the failure
    #     the player described.
    if pull and pull.get("urgent") and pull.get("kind") == "quest":
        low = (text or "").lower()
        keys = [str(k).lower() for k in pull.get("keys") or [] if len(str(k)) >= 4]
        names = [str(n).lower() for n in pull.get("people") or [] if len(str(n)) >= 3]
        carried = any(re.search(r"\b" + re.escape(k) + r"\w{0,2}\b", low) for k in keys) \
            or any(n in low for n in names)
        if not carried:
            out.findings.append(Finding(
                "drops-the-thread",
                f"{pull.get('title', '')!r} has not come up for {pull.get('since', 0)} turns",
                f"The player has an open matter that has not come up for many turns: "
                f"{pull.get('title', '')} — {pull.get('fact', '')}. Work one concrete "
                f"sign of it into this scene where it fits — somebody here who knows "
                f"of it, a detail that recalls it, a road toward it — in a sentence or "
                f"two. Do not resolve it, do not add a roll, and change nothing else.",
                weight=2,
            ))

    # 0a. The engine killed somebody and the prose has not said so. Weight 3, like the
    #     contradiction it is the mirror of: a death that did not happen and a death
    #     that did not reach the page are both the turn being untrue. The fix hint
    #     carries the facts — who, by what, how far past dead in words — because the
    #     repair that held everywhere else here is the one handed something specific
    #     to write. Measured before this existed: the prose wrote a wounded man, the
    #     dead-men cut deleted him, and an authored template filled the hole, four times
    #     out of four in one save. The template is now the backstop under THIS.
    for d in deaths or []:
        who = str(d.get("name") or "").strip()
        if not who or death_on_the_page(text, who):
            continue
        fam = death_family(str(d.get("family") or ""))
        bucket = death_bucket(int(d.get("margin", 0) or 0), int(d.get("hp_max", 1) or 1))
        how = {"barely": "just enough to kill",
               "ruinous": "far more than enough — the wound is ruinous",
               "overkill": "more than the whole body could take — the blow carries "
                           "through"}[bucket]
        blow = ("a blow" if fam == "other" else f"a {fam} blow")
        out.findings.append(Finding(
            "death-left-off-the-page",
            f"{definite(who)} died this turn and the prose does not say so",
            f"{definite(who)} is dead. The engine resolved it: {blow}, {how}. The "
            f"passage does not say so, and it must — write {definite(who)}'s death in "
            f"one or two sentences that are specific to this body and this blow: where "
            f"it landed, what it did to them, how they fall and where they lie. Say "
            f"plainly that they are dead. Do not have them speak, stagger, or struggle "
            f"for breath afterwards. Leave the rest of the passage as it is.",
            weight=3,
        ))
        break

    # 0. The prose says somebody was felled or hurt and the engine says otherwise.
    #    First because it is the one finding about whether the turn was *true*: every
    #    other rule here is about how the prose reads. Weight 3 so a rewrite that fixes
    #    only this one still counts as an improvement worth keeping.
    wrong = contradicts_state(text, state)
    if wrong:
        who = "; ".join(f"{n} is described as {claim} — {s!r}" for n, claim, s in wrong[:3])
        out.findings.append(Finding(
            "contradicts-the-engine", who,
            "You have written an outcome that did not happen. The engine resolves what "
            "lands and what does not, and nobody named here was hurt or felled this "
            "turn — so the blow missed, was turned, or never connected. Rewrite those "
            "sentences to describe the attempt and its failure, and leave everyone "
            "standing exactly as they are. Describe effort, not effect.",
            weight=3,
        ))

    # 0b. The square has bodies in it and the prose is describing a market day.
    #     Gated on somebody actually being down, so an untouched market keeps every one
    #     of these words — the finding is the contradiction, never the vocabulary.
    felled = [n for n, how in (state or {}).items()
              if isinstance(how, dict) and not how.get("alive")]
    if felled:
        stock = _BUSINESS_AS_USUAL.search(unquoted(text))
        if stock:
            out.findings.append(Finding(
                "ignores-the-dead",
                f"{stock.group(0)!r} with {', '.join(sorted(felled)[:3])} down",
                f"There are bodies on the ground and you have written {stock.group(0)!r}. "
                f"The place has seen what happened: the trade nearest the violence has "
                f"stopped, people are backing away or staring or running, and whoever is "
                f"still shouting is shouting about this. Open on what the square is doing "
                f"*now*, not on what it does on an ordinary morning.",
                weight=2,
            ))

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

    # 5b. A fight that stopped to describe the weather.
    if max_chars and len(text.strip()) > max_chars:
        out.findings.append(Finding(
            "too-long-for-a-fight", f"{len(text.strip())} characters, over {max_chars}",
            "This is a fight and it is running too long. Three or four sentences: what "
            "the last beat did, what is coming at them now, one thing they could use, "
            "and the question. Cut the scene-setting.",
        ))

    # 6. The turn is not handed back. Every example ends by asking the player something,
    #    and a turn that closes on a full stop tends to close the fiction with it.
    #    Tested on the *ending*, not on the presence of a question mark anywhere. A turn
    #    that closed "'What do you need?' you ask the guildhand, trying to keep your tone
    #    neutral." satisfied `"?" in text` on its own dialogue punctuation and shipped: the
    #    player's character asked a question, nobody answered it, and the scene stopped
    #    with nothing handed back.
    #
    #    Stripping the speech first and looking for a question mark in what is left would
    #    also have caught that one, and is the weaker rule: it still accepts a question
    #    buried three sentences from the end. The hand-back is by definition the last
    #    thing in the turn, so that is what is checked.
    if min_chars and not text.rstrip().endswith("?"):
        out.findings.append(Finding(
            "no-hand-back", f"ends on {text.rstrip()[-40:]!r}, not on a question",
            "The turn has to end by handing back to the player, and the last thing in it "
            "must be that question. If they asked somebody something, the answer is what "
            "this turn is for — give it to them in the person's own words, let them react, "
            "and then ask what the player does.",
        ))

    # 6b. Handed back, but by asking the player to do the narrating. The rule above is
    #     what produces this: a question is required, and "What do you see?" is the
    #     cheapest one there is.
    outsourced = asks_player_to_narrate(text)
    if outsourced:
        out.findings.append(Finding(
            "asks-the-player-to-narrate", f"ends on {outsourced!r}",
            f"You ended with {outsourced!r}. That is your job, not theirs — the player "
            f"cannot see anything you have not written. Describe what is actually there: "
            f"what they see, hear and smell in this room, what the people in it are "
            f"doing, and what has just changed. Then hand the turn back by asking what "
            f"they *do*.",
            weight=2,
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

    # 3b. Opening the same way as the turns just before it. Measured on the first
    #     60-turn run — the first long script this project has ever had, and the first
    #     thing it found: the commonest opening took 16% of the first third of the
    #     session, 26% of the second and **48% of the last**. Nearly half of every turn
    #     began "As you", and faults nearly doubled alongside it (4, 3, 7).
    #
    #     Invisible to every check that existed. `repeats-an-earlier-beat` wants a whole
    #     sentence repeated exactly; this is the same sentence *shape* returning, which is
    #     what a narrator narrowing actually looks like. And invisible to the ten-line
    #     looping scripts, which measure a narrator's first ten turns over and over.
    #
    #     Two, not one. A turn opening like the one before it is a coincidence; opening
    #     like two of the last six is the pattern that ends at 48%.
    if earlier and text:
        mine = opening_of(_sentences(text)[0] if _sentences(text) else "")
        recent = [opening_of(_sentences(e)[0]) for e in earlier[-6:] if _sentences(e)]
        same = sum(1 for o in recent if o and o == mine)
        if mine and same >= 2:
            out.findings.append(Finding(
                "formulaic-opening", f"{same} recent turns also open {mine!r}",
                f"You have opened {same + 1} turns in a row with {mine!r}. Start this one "
                f"somewhere else — on a person, on a sound, on the thing that has "
                f"changed — and do not begin it with the player.",
                weight=2,
            ))

    # 3c. A phrase this narrator keeps reaching for. Measured on the 2026-09-17
    #     sixty-turn baseline, AFTER the opening repair had brought the commonest
    #     opening down to 7%: "the transition from the" in 12 of 53 beats, "to your
    #     left the" in 9, "the silence of the" in 7, "the ground beneath your boots" in
    #     6 — none of it visible to 3 (a whole sentence), 3b (the first two words) or
    #     the echo index (the worked examples, never the campaign's own prose). Xu et
    #     al. (NeurIPS 2022) name the mechanism: a sentence already in the context
    #     self-reinforces, and the phrasings that were likeliest to begin with converge
    #     fastest. So the campaign's own recent beats are the index here, and the
    #     phrase is named in the hint — a repair the model cannot locate is a blind
    #     retry. No deterministic backstop: cutting a clause from the middle of a
    #     paragraph leaves a hole where a sentence was.
    if earlier:
        tics = recurring_phrases(text, earlier)
        if tics:
            named = "; ".join(repr(p) for p, _ in tics[:3])
            out.findings.append(Finding(
                "recurring-phrase",
                f"{tics[0][0]!r} has appeared in {tics[0][1]} recent turns",
                f"You keep writing the same phrases: {named}. Each of those has "
                f"appeared in several recent turns already. Rewrite the sentences that "
                f"contain them so that none of those phrases appears, saying the same "
                f"thing in a different shape — a different subject, a different verb, "
                f"a detail of this place rather than a formula. Change nothing else.",
                weight=2,
            ))

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
    #
    #    Read against `text` and not `body`. `body` is the narration with spoken dialogue
    #    stripped, which is right for the player's-name rule above — an NPC may say
    #    "Grist" out loud — but it exempted every name introduced inside quotation marks,
    #    and dialogue is precisely where one NPC names another. Measured in play: the
    #    stranger said "There's Glimble at the corner of Wind and Elm", a smith with no
    #    entry anywhere in Pangrella, and the review returned ok with zero findings while
    #    `invented_names` on the same sentence found him immediately. The suggestion chips
    #    then offered "Head to Glimble's immediately", which is the invention becoming
    #    settled fact one turn later.
    if known_names is not None:
        for name in invented_names(text, known_names):
            out.findings.append(Finding(
                "invented-name", f"names {name!r}, which is not in this world",
                f"{name!r} is not a person or place in this world. Use only the people "
                f"in the scene and the places the world contains, or describe someone "
                f"without naming them. This applies inside dialogue too — what a "
                f"character says out loud invents a person just as firmly as narration.",
                # Heavier than a prose nit. `polish` keeps the original whenever the
                # rewrite does not score better, and a bland sentence is a far cheaper
                # outcome than a person who does not exist entering the campaign.
                weight=3,
            ))
            break

    # 4b. An ally the player has not got. The same failure as the invented name and
    #     invisible to that check, because "companion" carries no capital letter.
    # 2b. The player's character given somebody else's pronouns. The scene brief has
    #     always stated them — "when someone speaks about them, she/her" — and the model
    #     still gets it wrong, which is the oldest lesson here arriving somewhere new.
    #     Measured on a wizard whose sheet says she/her: a winged youth burst into the
    #     gymnasium, pointed and shouted "It's him! Thessaly Corr!"
    #
    #     Check 2 above cannot see it: that reads `unquoted(text)`, because an NPC may
    #     say the player's name aloud, and shouting it is exactly what happened.
    for said in misgendered(text, pc_name, pronouns, tuple(others or ())):
        out.findings.append(Finding(
            "misgendered-pc", f"calls the player's character {said!r}",
            f"The player's character uses {pronouns}. Never {said!r} — not in narration "
            f"and not in anybody's mouth.",
            weight=3,
        ))
        break

    # 2c. The player's character given the wrong body. Separate from 2b and not reachable
    #     from it: the paragraph that prompted this was in the second person from end to
    #     end and contained no pronoun at all.
    for part in wrong_body(text, gender, tuple(others or ())):
        out.findings.append(Finding(
            "wrong-body", f"gives the player's character {part!r}",
            f"The player's character is a {gender}. {part!r} is not part of her body — "
            f"describe the one she has, or describe something else. This is not about "
            f"which words you use for her; it is about what is there."
            if str(gender).lower() == "woman" else
            f"The player's character is a {gender}. {part!r} is not part of their body — "
            f"describe the one they have, or describe something else.",
            weight=3,
        ))
        break

    # 7. The narrator writing itself into the scene. Measured in the same mirror beat:
    #    "Lyra stands beside me... every detail of my image." Check 2 cannot see this —
    #    it looks for the player's name, and there is no name here at all.
    said = narrator_in_first_person(text)
    if said:
        out.findings.append(Finding(
            "narrator-in-first-person", f"narrates as {', '.join(repr(s) for s in said)}",
            f"You are not in this scene and you have no body in it. Nothing outside "
            f"quoted speech may say {said[0]!r} — the player is 'you', everybody else "
            f"has a name. Rewrite those clauses from the player's point of view.",
            weight=2,
        ))

    if alone:
        for phrase in invented_companions(text):
            out.findings.append(Finding(
                "invented-companion", f"gives the player {phrase!r}, who is not there",
                f"Nobody is fighting beside them. Remove {phrase!r}: every blow in this "
                f"scene is the player's own, and crediting a second pair of hands "
                f"rewrites who did what.",
                weight=3,
            ))
            break

    return out



# --- the player's character, gendered by guesswork -------------------------------------
#
# The scene brief has always told the model the pronouns — "when someone speaks about
# them, she/her" — and it still gets them wrong, which is this project's oldest lesson
# arriving somewhere new. Measured in play on a wizard whose sheet said she/her: a winged
# youth burst into the gymnasium, pointed, and shouted "It's him! Thessaly Corr!"
#
# The existing third-person check cannot see it. That one reads `unquoted(text)`, because
# an NPC may perfectly well say the player's name out loud — and shouting it is exactly
# what happened.
# How far either side of the name to look. Wide enough for "It's him! Thessaly Corr!"
# and the clause on either side of it; narrow enough that a paragraph about three
# people does not pool all their pronouns together.
MISGENDER_WINDOW = 90

_PRONOUN_SETS = {
    "she": ("she", "her", "hers", "herself"),
    "he": ("he", "him", "his", "himself"),
    "they": ("they", "them", "their", "theirs", "themself", "themselves"),
}


def _pronoun_family(pronouns: str) -> str:
    """"she/her" -> "she". Anything unrecognised answers "", which checks nothing: a
    table that invented ze/hir gets no opinion from this rule rather than a wrong one."""
    first = str(pronouns or "").split("/")[0].strip().lower()
    return first if first in _PRONOUN_SETS else ""


def misgendered(text: str, pc_name: str, pronouns: str,
                others: tuple[str, ...] = ()) -> list[str]:
    """Pronouns used for the player's character that their sheet does not use.

    Narrow on purpose, because the risk is the other way: "Thessaly nods and the trainer
    steps back as he lowers his guard" has her name and a `he` in one sentence and is
    perfectly correct prose about somebody else. So a sentence only counts when the
    player's character is the *only* named person in it — which is what "It's him!
    Thessaly Corr!" is, and what a sentence about the trainer is not.
    """
    family = _pronoun_family(pronouns)
    if not family or not pc_name:
        return []
    # Only the opposite binary pronoun counts as evidence. "they" is deliberately never
    # wrong here: it is the plural everybody uses for a crowd, and including it made
    # "One of *them* spots you" and "*They* shout that it is her" both report the player
    # as misgendered in the very line that gets her right.
    wrong = {w for fam, words in _PRONOUN_SETS.items()
             if fam != family and fam != "they" for w in words}
    names = [n for n in others if n and n.lower() != pc_name.lower()]
    first = pc_name.split()[0]
    # A window of characters around the name, not a sentence. `_SENTENCE` splits on
    # "!", so the line that prompted this - "It's him! Thessaly Corr!" - puts the
    # pronoun and the name in two different sentences, and a per-sentence rule sees
    # nothing at all.
    text = text or ''
    found: list[str] = []
    pattern = r'\b(?:' + re.escape(pc_name) + '|' + re.escape(first) + r')\b'
    for m in re.finditer(pattern, text, re.I):
        lo = max(0, m.start() - MISGENDER_WINDOW)
        window = text[lo:m.end() + MISGENDER_WINDOW]
        if any(re.search(r'\b' + re.escape(n) + r'\b', window, re.I) for n in names):
            continue      # somebody else is in earshot; the pronoun may be theirs
        for token in re.findall(r"\b[A-Za-z']+\b", window):
            low = token.lower()
            if low in wrong and low not in found:
                found.append(low)
    return found


# --- the player's character, given the wrong body -------------------------------------
#
# Pronouns were never going to reach this and could not have. Measured in play: a
# character whose sheet said they/them stood in front of a mirror and was narrated
# "your eyes scan your face, noting the sharp lines of your jaw" and then "a faint,
# intricate pattern etched into the surface of your pectoralis major muscles" — a man's
# chest, in a paragraph containing no pronoun anywhere, because the narration is in the
# second person and the second person has no gender in English.
#
# So the pronoun check above is structurally blind to it, the brief's one sentence about
# pronouns had nothing to bite on, and the model wrote the body it defaults to. The
# repair is in two halves: the brief now says what the character *is* in plain words
# (`prompts.scene_brief`), and this catches it when that does not hold.
#
# Only anatomy that actually belongs to one body. "Jaw", "shoulders", "hands" and
# "chest" are everybody's and are not evidence of anything — a check that flagged them
# would fire on every correct description of a woman and make the prose worse for it.
_MALE_BODY = (r"beards?|bearded|stubble|moustaches?|mustaches?|whiskers|sideburns"
              r"|adam'?s apple|pectorals?|pectoralis|chest hair|manhood|penis|phallus"
              r"|testicles?|scrotum")
_FEMALE_BODY = (r"breasts?|bosom|cleavage|womb|uterus|vulva|vagina|ovaries"
                r"|nipples? swell")
_WRONG_BODY = {"woman": _MALE_BODY, "man": _FEMALE_BODY}

# How far after "your" the part may sit. "the surface of your pectoralis major muscles"
# is four words; a whole clause is too far and starts collecting other people's bodies.
# Punctuation is excluded so the window cannot cross into the next sentence.
_BODY_GAP = 40

# "your" and "my", because the player's body gets described in both. Measured, the turn
# after the second-person case was fixed: asked to describe her chest aloud, the model
# put the whole description in her own mouth — "'My chest is. muscular, with well-defined
# pectoralis muscles that curve outward from the center of my body.'" — and a check
# reading only `your` saw nothing at all in it.
#
# `my` needs a speaker, though. An NPC saying "my beard" is describing their own face and
# is nobody's business but theirs, so a first-person possessive only counts when the
# player is the one talking.
_OWNS = r"your|my"

# How far back to look for who is speaking. Wide enough to reach past "You take a deep
# breath and begin to describe your chest, speaking in a low, matter-of-fact tone." and
# find the "You" that starts it.
_SPEAKER_LOOKBACK = 160


# Whose part it is, when something owns it. Read backwards from the part itself rather
# than forwards from a possessive, because the forward rule cannot cross a full stop and
# the model's punctuation is not reliable: the line that prompted this reads "'My chest
# is. muscular, with well-defined pectoralis muscles" — a stray period between the
# possessive and the part, and a gap rule that excludes "." saw nothing in it at all.
_POSSESSIVE = re.compile(r"\b(my|your|his|her|their|its|our)\b|['’]s\b", re.I)

# How far back a possessive still governs the part. Long enough for the broken sentence
# above (38 characters from "My" to "pectoralis"), short enough that it does not reach
# back into the previous speaker's turn.
_OWNER_LOOKBACK = 60


def _owner_of(text: str, at: int) -> str:
    """Who the part at this position belongs to: "my", "your", "his", "" for nobody."""
    window = text[max(0, at - _OWNER_LOOKBACK):at]
    found = list(_POSSESSIVE.finditer(window))
    if not found:
        return ""
    last = found[-1]
    return (last.group(1) or "someone").lower()


def _player_is_speaking(text: str, at: int, others: tuple[str, ...] = ()) -> bool:
    """Whether the "my" at this position belongs to the player's character.

    Read off the attribution in front of it, nearest wins. "Vorgath says, 'My beard…'"
    has his name closer than any "you", and is his to describe.
    """
    window = text[max(0, at - _SPEAKER_LOOKBACK):at]
    mine = [m.start() for m in re.finditer(r"\byou\b|\byour\b", window, re.I)]
    theirs = [m.start() for n in others if n
              for m in re.finditer(r"\b" + re.escape(n) + r"\b", window, re.I)]
    if not mine:
        return False
    return not theirs or max(mine) > max(theirs)


def _parts_of_the_player(text: str, marks: str, others: tuple[str, ...]):
    """Every match of `marks` that is a part of the player's character's body.

    The question is *whose body is being described*, not which pronoun happens to sit in
    front of the word — that is what the two versions before this got wrong, each in its
    own way. The first read only "your" and missed the turn where the character described
    herself out loud. The second added "my" as a prefix and still missed it, because the
    model wrote "'My chest is. muscular, with well-defined pectoralis muscles" and a
    forward rule that will not cross a full stop cannot get from the possessive to the
    part.

    So ownership is read backwards from the part, and there are exactly two ways for it
    to be the player's: the narration says "your", or the player is the one speaking and
    says "my". Anything owned by a third person is theirs.

    Who is speaking is read off the attribution rather than off a matched pair of quote
    marks, and that is not a shortcut. `_QUOTED` caps a span at 300 characters, and the
    real turn this was written against ran to a 500-character speech — so the quote never
    matched, the "inside a player quote" test answered no, and the check missed the very
    line it had just been extended to catch.
    """
    for m in re.finditer(rf"\b({marks})\b", text, re.I):
        owner = _owner_of(text, m.start())
        if owner == "your":
            yield m
        elif owner == "my" and _player_is_speaking(text, m.start(), others):
            yield m


def wrong_body(text: str, gender: str, others: tuple[str, ...] = ()) -> list[str]:
    """Sex-specific anatomy on the player's character's body.

    Whether the narration is describing her or she is describing herself, and neither
    case is reachable by a pronoun rule: "you" and "my" both carry no gender in English,
    which is the whole reason this check has to know what she *is* rather than what she
    is called. An unstated gender gets no opinion — most of the bestiary has none, and
    inventing one to check against would be the guess this field exists to stop.
    """
    marks = _WRONG_BODY.get(str(gender or "").strip().lower())
    if not marks or not text:
        return []
    found: list[str] = []
    for m in _parts_of_the_player(text, marks, tuple(others or ())):
        part = m.group(1).lower()
        if part not in found:
            found.append(part)
    return found


# What each wrong part becomes. Per gender, and this matters: the first version of this
# table swapped every chest word for the neutral "chest", which reads as a fix and is a
# quieter way of being wrong. "a woman should have breasts, whatever size they may be,
# otherwise its a man" — a woman looking at her own bare chest in a mirror does not see a
# neutral noun, and a narrator who has been stopped from saying the wrong thing but not
# told the right one will simply go vague forever.
#
# So the substitution asserts, where there is something to assert. Where there is not, it
# falls back to a part everybody has: a woman has no beard, and "jaw" is the true thing
# to say about the place one would be.
_RIGHT_PART = {
    "woman": {
        "pectoral": "breasts", "pectorals": "breasts", "pectoralis": "breasts",
        "chest hair": "breasts",
        "beard": "jaw", "beards": "jaw", "bearded": "bare",
        "stubble": "jaw", "whiskers": "jaw", "sideburns": "temples",
        "moustache": "mouth", "moustaches": "mouth",
        "mustache": "mouth", "mustaches": "mouth",
        "adam's apple": "throat", "adams apple": "throat",
        "manhood": "body", "penis": "body", "phallus": "body",
        "testicles": "body", "scrotum": "body",
    },
    "man": {
        "breast": "chest", "breasts": "chest", "bosom": "chest",
        "cleavage": "collarbone",
        "womb": "belly", "uterus": "belly", "ovaries": "belly",
        "vulva": "body", "vagina": "body",
    },
}

# "pectoralis major muscles" is one part with three words. Whatever qualifies the noun
# has to go with it, or the swap leaves "the surface of your chest major muscles".
_ANATOMY_TAIL = re.compile(r"\s+(?:major|minor)?\s*(?:muscles?)\b", re.I)


def right_body(text: str, gender: str,
               others: tuple[str, ...] = ()) -> tuple[str, list[str]]:
    """Swap anatomy that is not theirs for the part that is.

    The backstop, not the repair. `review` raises `wrong-body` first and the model gets a
    chance to rewrite the paragraph properly, which is much the better outcome — measured
    live, though, that rewrite does not always land: on the turn this was written for it
    had three findings to beat at once and kept the original, so "your pectoralis major
    muscles" reached the player a second time.

    Named for what it does now. It was `neutralise_body`, and neutral was the wrong
    target: swapping a woman's pectorals for a "chest" stops the sentence being wrong
    without ever making it right, and a narrator held to that produces a woman with no
    body at all.
    """
    said = str(gender or "").strip().lower()
    marks = _WRONG_BODY.get(said)
    table = _RIGHT_PART.get(said) or {}
    if not marks or not text:
        return text, []
    swapped: list[str] = []

    # The *same* matches the detector found, not a second regex that agrees with it by
    # eye. Two expressions drifted apart once already — the fix shaved the beard off a
    # face the detector had deliberately exempted — and this is the only way they cannot.
    #
    # Right to left, so an earlier replacement cannot shift the offsets of a later one.
    hits = list(_parts_of_the_player(text, marks, tuple(others or ())))
    out = text
    for m in reversed(hits):
        right = table.get(m.group(1).lower())
        if not right:
            continue
        swapped.append(m.group(1).lower())
        # By span, never `str.replace` — the trap `fix_hand_back` documents, where a
        # whitespace shift between what was found and what is replaced makes the fix a
        # silent no-op. Whatever qualifies the noun goes with it, or "your pectoralis
        # major muscles" becomes "your breasts major muscles".
        end = m.end()
        tail = _ANATOMY_TAIL.match(out, end)
        out = out[:m.start()] + right + out[(tail.end() if tail else end):]
    swapped.reverse()
    return out, swapped


# --- the narrator becoming a character ------------------------------------------------
#
# Measured in the same mirror scene: "Lyra stands beside me, her gaze locked onto the
# mirror, her eyes scanning every detail of my image." The narrator is not in the scene
# and has no image. This is the third-person slip inverted — instead of pushing the
# player out to arm's length it pulls the narrator in — and the existing check cannot see
# it, because it looks for the player's *name* and there is none here.
# Case-insensitive, and that flag is load-bearing: without it the lowercase `i` in
# this pattern can never match the always-capitalised pronoun, and the detector spent
# its whole life blind to the single commonest first-person word. "As I push through,
# the wood darkens" shipped undetected; the audit only caught its neighbour because
# the same sentence also said "myself".
_FIRST_PERSON = re.compile(r"\b(?:i|me|my|mine|myself)\b", re.I)


def narrator_in_first_person(text: str) -> list[str]:
    """First-person words in narration. Dialogue is exempt — everybody says "I" — and
    so is a sentence reporting a written thing, the same exemption the converter makes:
    a sign that reads "I buy old iron" is the sign speaking, not the narrator."""
    found: set[str] = set()
    for sentence in _SENTENCE.findall(unquoted(text or "")):
        if _WRITTEN_ARTIFACT.search(sentence):
            continue
        found |= {m.group(0).lower() for m in _FIRST_PERSON.finditer(sentence)}
    return sorted(found)


# Enemies who exist only in the prose. Measured at the Zhilvarnia gate: the engine
# printed "The fight is over" while the narration had officials "regain their composure
# and press forward, trying to overwhelm you with sheer numbers" — a group the scene
# never contained. A group-noun within reach of a closing-in verb is the shape; the
# caller gates it on the scene actually holding no living opposition, so a real second
# wave is never touched.
_PHANTOM_OPPOSITION = re.compile(
    r"\b(?:guards?|officials?|soldiers?|watchmen|attackers?|enemies|assailants?|"
    r"the\s+rest\s+of\s+them|they)\b[^.!?]{0,80}?"
    r"\b(?:closing\s+in|close\s+in|press(?:es|ing)?\s+forward|surround(?:ing)?|"
    r"advance|advancing|charg(?:e|es|ing)|moving\s+to\s+(?:surround|attack)|"
    r"overwhelm|regroup(?:ing)?|form(?:ing)?\s+a\s+(?:defensive\s+)?line)\b", re.I)


# The model's own option menu, bleeding into the book. Measured on the second prompt
# of a live session: "the stranger: * the onlooker off your opponent * the passer-by
# to disarm or disable them * ... : None required; you've already acted." — a
# suggestions list, half-mangled by the stranger-renamer, shipped as narration. Prose
# never bullet-points and a narrator never tells the player what they are "required"
# to do; both shapes are cut whole.
_LEAKED_OPTIONS = re.compile(
    r"\s\*\s|\bNone required\b|\byou'?ve already acted\b|\bchoose one of\b|"
    # "(Combat is now ongoing." and "(You are still in the midst of a fight. )" —
    # the GM whispering stage directions in parentheses, measured twice live.
    r"\byour options are\b|\(\s*Combat is now|\(\s*You are still in the midst|"
    # "Suggested actions: ..." and "Next, you'll wait for your decision before
    # proceeding with the scene." — the scaffold reciting itself, measured live
    # in the Eldrida beat.
    r"\bSuggested actions?\s*:|\bNext, you'?ll wait for your decision\b|"
    r"\bwait for your decision before proceeding\b", re.I)


# What a corpse may still do in a sentence. Lying there, being looked at, being
# stripped — anything else is the resurrection the scene panel contradicts.
_DEAD_MAY = re.compile(
    # "still" only as posture — bare, it matched "still reeling from your earlier
    # strike" and a dead merchant walked a whole beat behind that one adverb.
    r"\b(?:lies|lay|lying|dead|corpse|body|bod(?:y|ies)|motionless|fallen|"
    r"lies still|lying still|crumpled|sprawled|remains?|blood|late)\b", re.I)


# The player is the subject, so whoever is named after them is not the one acting — and
# this is usually the killing blow itself. "You cut the thug down where he stands" names
# a man who is dead by the end of the sentence, which is the one sentence about him that
# MUST survive.
#
# Measured, and it was deleting them: "You kill the thug.", "You drive your blade through
# the thug and he drops." and "Your fist connects with a meaty thud and the thug crashes
# to the deck." were all cut whole, because the dead list is built from live `hp <= 0`
# and is already true the instant the blow resolves. Stage 6a made it bite harder by
# telling the narrator about the death, so the model writes these sentences more often —
# a live prose loss that the tell fix made worse until this went in beside it.
#
# The cost, stated rather than hidden: "You watch the thug get up and run" now survives.
# That is far rarer than a kill, and the engine's own tell states the death regardless.
_PLAYER_ACTS = re.compile(r"[\"“'‘]?\s*Your?\b", re.I)


def cut_dead_men_walking(text: str, dead_names, fresh=()) -> tuple[str, list[str]]:
    """Drop sentences where a dead actor gets up and acts.

    Measured across a live session: the stranger died in the opening turns, the panel
    said Dead beside his name for the rest of the evening, and the narration kept
    casting him — "The stranger from earlier bursts out of nowhere, grabbing at your
    arm", yelling, glaring, stumbling. A sentence naming the dead survives when it
    treats them as dead (lying, fallen, a body, being stripped); one that has them
    doing anything else is cut whole.

    `fresh` names whoever died THIS turn. For them a sentence carrying felling or
    death language is the killing blow itself and is kept — "the sailor crumples to
    the deck and does not move" has no word from `_DEAD_MAY` in it, and until this
    it was cut as a dead man acting, which left the beat with no death in it at all
    and handed the page to `press_the_death`'s one template. Measured in
    `spooter.json`: four kills, four identical appended lines. Long-dead actors keep
    the strict rule, because "the stranger collapses" two turns after he died is the
    resurrection this cut exists for.
    """
    if not text or not dead_names:
        return text or "", []
    names = [n for n in dead_names if n and len(n) >= 3]
    if not names:
        return text, []
    pattern = re.compile("|".join(re.escape(n) for n in names), re.I)
    just_died = re.compile("|".join(re.escape(n) for n in fresh if n and len(n) >= 3),
                           re.I) if any(n and len(n) >= 3 for n in fresh) else None
    kept, cut = [], []
    for m in _SENTENCE.finditer(text):
        s = m.group(0)
        hit = pattern.search(s)
        dying_now = bool(just_died and just_died.search(s)
                         and (_FELLED.search(s) or _DEATH_LANGUAGE.search(s)))
        if hit and not dying_now and not _DEAD_MAY.search(s) \
                and not _PLAYER_ACTS.match(s.strip()):
            # The quote exemption exists so a living speaker may *mention* the
            # dead — and it let the dead keep talking, measured live: a merchant
            # at -19 spat "You'll pay for this!" and nodded through two beats,
            # protected by his own quotation marks. The exemption now holds only
            # when the dead name sits INSIDE the quoted span; a dead man as the
            # speaker outside the quotes is cut, speech and all.
            # A quote OPENER, not any apostrophe: "it's" must not shield a dead
            # man named after the contraction.
            opener = re.search(r"[\"“]|(?<=[\s,:])['‘]", s)
            if opener is None or hit.start() < opener.start():
                cut.append(s.strip())
                continue
        kept.append(s.strip())
    if not cut:
        return text, []
    return " ".join(kept), cut


def strip_leaked_options(text: str) -> tuple[str, list[str]]:
    """Drop sentences where the option menu leaked into the narration."""
    if not text:
        return text or "", []
    kept, cut = [], []
    for m in _SENTENCE.finditer(text):
        s = m.group(0)
        (cut if _LEAKED_OPTIONS.search(s) else kept).append(s.strip())
    if not cut:
        return text, []
    return " ".join(kept), cut


def cut_phantom_opposition(text: str) -> tuple[str, list[str]]:
    """Drop sentences that press an attack nobody is present to press.

    Sentence-level, like `drop_repeated_beats`: the surrounding prose (the crowd, the
    aftermath, the hand-back) is usually fine, and one sentence of ghosts does not
    forfeit the paragraph. Quoted speech is exempt — a frightened bystander may say
    the guards are coming, and being wrong out loud is in character.
    """
    if not text:
        return text or "", []
    kept, cut = [], []
    for m in _SENTENCE.finditer(text):
        s = m.group(0)
        if _PHANTOM_OPPOSITION.search(s) and not _OPENS_SPEECH.search(s) \
                and '"' not in s and "“" not in s:
            cut.append(s.strip())
            continue
        kept.append(s.strip())
    if not cut:
        return text, []
    return " ".join(kept), cut


# An ally the player has not got. Measured in the tavern: the killing blow came back as
# "your fist connects with a meaty impact, and **your companion's** next swing brings you
# another crushing blow" — Grist was alone in that fight, and had been for the whole
# scene. The invented-name check cannot see this: "companion" is a common noun with no
# capital letter, so there is nothing for a name check to catch.
_COMPANION = re.compile(
    r"\byour (?:companion|companions|ally|allies|friend|friends|comrade|comrades"
    r"|partner|band|party|group|men|people|crew)\b"
    r"|\bthe others\b|\byour side\b|\bone of your (?:companions|allies|friends)\b",
    re.I)


def invented_companions(text: str) -> list[str]:
    """Phrases that hand the player somebody who is not there."""
    return sorted({m.group(0) for m in _COMPANION.finditer(text or "")})


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
        # A place, by its shape: a capitalised token beside a place noun, or a place
        # noun after a possessive ("the Weaver's Rest"), is somewhere, not somebody.
        words = re.findall(r"[A-Za-z][a-zA-Z'’-]*", sentence)
        placed: set[str] = set()
        for i, w in enumerate(words):
            prev = words[i - 1] if i else ""
            nxt = words[i + 1] if i + 1 < len(words) else ""
            # Both halves capitalised: "Salt Market" and "the Weaver's Rest" are places;
            # "let Kaida rest" and "Serath Vale steps out" are people doing things.
            if (w[:1].isupper() and w.lower() in PLACE_NOUNS
                    and (prev[:1].isupper() or prev.endswith(("'s", "’s")))):
                placed.add(w)
                if prev[:1].isupper():
                    placed.add(prev)
            elif nxt[:1].isupper() and nxt.lower() in PLACE_NOUNS and w[:1].isupper():
                placed.add(w)
        first = sentence.strip().split(" ")[0].strip(".,!?;:'\"")
        # A quote begins a sentence too. `_SENTENCE` splits on full stops, so the first
        # word *inside* speech sits mid-sentence and was read as a name: measured across
        # two 60-turn runs, "Enjoy", "Ask", "Meet", "Just" and "Very" were all reported as
        # invented people, every one of them the opening word of somebody's line.
        opens_speech = {
            m.group(1) for m in re.finditer(r"[\"“”'‘’]\s*([A-Z][a-zA-Z'’-]{2,})",
                                            sentence)}
        for tok in tokens:
            low = tok.lower()
            # The whole token first, so a name that owns its apostrophe survives: this
            # world's people are Khy'vyr and Khra'gix, and splitting before checking
            # would reduce them to "khy" and report both as invented.
            if low in _NOT_A_NAME or low in allowed:
                continue
            # "Thrain's place" is Thrain, who exists. Reading the possessive as its own
            # token reported a real clan elder as an invention.
            stem = re.sub(r"['’]s$", "", low)
            if stem != low and (stem in allowed or stem in _NOT_A_NAME):
                continue
            # "I've", "I'll", "We're" — a capitalised contraction is not a name. Tested
            # on the head rather than a list of forms, so every contraction of a word
            # already known not to be a name is covered without enumerating them.
            if re.split(r"['’]", low)[0] in _NOT_A_NAME:
                continue
            if tok == first or tok in opens_speech:   # a sentence start proves nothing
                continue
            if tok in placed:
                continue
            if low not in found:
                found.append(tok)
    return found


# --- texture: what can be measured about prose without lying about it ---------------------
#
# The instruction was to score whether the prose is any *good*. The honest answer is that
# most of what "good" means cannot be measured here, and CLAUDE.md says why: counting
# sensory words or scoring vividness with a regex is named there as the kind of metric that
# has given confident, wrong answers about quality.
#
# So this measures symptoms of *formula*, which is a different thing and is real. The
# precedent is "ten of ten paragraphs ended the same way" — countable, undeniable, and
# fixed once seen. Everything here is a number a person can check by reading the prose.
#
# Measured on 20 real town turns, llama3.1:8b, 2026-08-25, the first run in which the
# harness actually read the prose at all:
#
#     length          mean 839 chars, median 760, range 559-1165
#     sentences       170, mean 17.0 words, stdev 8.7
#     openings        varied — the most repeated turn-opener appeared twice in nineteen
#     second person   31 of 170 sentences begin "you" (18%)
#     dialogue        9 of 19 turns contain speech, and 7 of 7 spoken questions were
#                     answered in somebody's own words
#
# That corpus shows no formula defect these measures can see, which is the finding rather
# than a failure of the measures. They are reported by `tools/narrator_audit.py` so drift
# has a baseline to drift *from* — a number nobody is watching is not a measurement.
_OPENER_WORDS = 2

# --- the narrator measured against itself -------------------------------------------------
#
# Holtzman's *Repetition* metric counts a phrase repeating three times at the END of one
# generation, which scores this project's problem at zero; distinct-n falls with length
# whatever the model does (Rethinking and Refining the Distinct Metric, ACL 2022). The
# two that fit are the self-repetition score of Salkar et al. (AACL 2022) — n-grams of
# four or more words that appear in MORE THAN ONE output of the same system — and the
# gzip compression ratio Shaib et al. (2024) recommend as the cheap measure that tracks
# the n-gram ones. Both are a few lines and need nothing installed. docs/narrator-guards.md.

# Words that carry no content on their own. A four-word phrase made only of these ("and
# then it is") is English, not a tic; one with a single content word in it ("the
# transition from the") is exactly the kind of tic that was measured.
_FUNCTION_WORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "by", "for",
    "from", "with", "as", "is", "are", "was", "were", "be", "been", "it", "its", "you",
    "your", "he", "she", "they", "his", "her", "their", "them", "him", "that", "this",
    "there", "here", "then", "than", "not", "no", "so", "if", "into", "out", "up",
    "down", "over", "under", "off", "do", "does", "did", "have", "has", "had", "what",
    "who", "which", "when", "where", "how", "own", "one", "all", "some", "any",
})

# The recent-beat windows the phrase check reads, and the thresholds. Four words in
# three of twelve is a phrase the narrator is settling into (the baseline's worst was
# twelve of fifty-three); six words shared with two of the last eight is a clause being
# lifted whole. See `recurring_phrases` for why not one of eight.
PHRASE_WINDOW = 12
PHRASE_REPEATS = 3
LIFT_WINDOW = 8
LIFT_LENGTH = 6


_CASED_WORD = re.compile(r"[A-Za-z][A-Za-z']*")


def _phrase_grams(text: str, n: int) -> set[tuple]:
    """The n-word phrases of a beat that could be a tic: speech and the hand-back
    stripped, at least one content word in each, and no phrase that is mostly a proper
    name — "the Guild of Salt and Timber" recurring is the world, not a formula."""
    body = unquoted(text or "")
    sentences = [s for s in _sentences(body) if not s.rstrip().endswith("?")]
    out: set[tuple] = set()
    for s in sentences:
        cased = _CASED_WORD.findall(s)
        for i in range(max(0, len(cased) - n + 1)):
            span = cased[i:i + n]
            # Capitals past the first word of the sentence are names.
            names = sum(1 for k, x in enumerate(span) if x[:1].isupper() and (i + k) > 0)
            if names >= 2:
                continue
            g = tuple(x.lower() for x in span)
            if any(x not in _FUNCTION_WORDS for x in g):
                out.add(g)
    return out


def recurring_phrases(text: str, earlier: list[str] | None,
                      window: int = PHRASE_WINDOW, repeats: int = PHRASE_REPEATS,
                      lift_window: int = LIFT_WINDOW,
                      lift_length: int = LIFT_LENGTH) -> list[tuple[str, int]]:
    """The phrases of this beat that recent beats already used, worst first.

    Returns `(phrase, beats)` pairs: four-word phrases found in `repeats` or more of
    the last `window` beats, and `lift_length`-word phrases found in two or more of the
    last `lift_window`. Calibrated on the 2026-09-17 baseline: at "any of the last
    eight" the six-word rule fired on 29 of 56 beats, most of them a beat honestly
    continuing the scene of the one before it ("the slap of water against the pilings"
    while still standing at the river); at two of eight, 17 of 56, every one a tic. A
    phrase is counted once per beat it appears in, so a beat that says a thing twice is
    one beat.
    """
    if not text or not earlier:
        return []
    mine4 = _phrase_grams(text, 4)
    mine6 = _phrase_grams(text, lift_length)
    if not mine4 and not mine6:
        return []
    count4: Counter = Counter()
    count6: Counter = Counter()
    recent = [e for e in earlier if e][-window:]
    for i, beat in enumerate(recent):
        theirs4 = _phrase_grams(beat, 4) & mine4
        count4.update(theirs4)
        if i >= len(recent) - lift_window:
            count6.update(_phrase_grams(beat, lift_length) & mine6)
    found: dict[str, int] = {}
    for g, c in count6.items():
        if c >= 2:
            found[" ".join(g)] = c
    for g, c in count4.items():
        if c >= repeats:
            phrase = " ".join(g)
            # A four-word phrase inside a six-word one already reported is the same
            # finding twice.
            if not any(phrase in longer for longer in found):
                found[phrase] = max(c, found.get(phrase, 0))
    return sorted(found.items(), key=lambda kv: (-kv[1], kv[0]))


def self_repetition(turns: list[str], n: int = 4) -> dict:
    """Salkar et al.'s self-repetition, over a run: the share of each beat's n-word
    phrases that also appear in some OTHER beat of the same run, averaged, plus the
    phrases that recur in most beats. Speech and hand-backs excluded, as above."""
    grams = [_phrase_grams(t, n) for t in (turns or []) if t]
    if len(grams) < 2:
        return {"score": 0.0, "beats": len(grams), "top": []}
    in_beats: Counter = Counter()
    for g in grams:
        in_beats.update(g)
    shares = []
    for g in grams:
        if not g:
            continue
        shared = sum(1 for x in g if in_beats[x] > 1)
        shares.append(shared / len(g))
    top = [(" ".join(g), c) for g, c in in_beats.most_common(60) if c >= 3][:12]
    return {
        "score": round(sum(shares) / len(shares), 3) if shares else 0.0,
        "beats": len(grams),
        "top": top,
    }


def compression_ratio(turns: list[str]) -> float:
    """Bytes of prose per byte of gzip — Shaib et al.'s direction, so HIGHER is samer:
    redundant text compresses further. Reported beside length, as they insist, because
    a longer run compresses better whatever its variety."""
    import gzip

    joined = "\n".join(t for t in (turns or []) if t).encode("utf-8")
    if not joined:
        return 0.0
    return round(len(joined) / max(1, len(gzip.compress(joined))), 3)


# How much opener reuse is too much. The measured rate is 2 repeats in 19 turns; a run
# where more than a third of turns open the same way is formulaic in the sense that has
# been fixed here before, and is nowhere near what a healthy run does.
FORMULA_SHARE = 0.34


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.findall(text or "") if s.strip()]


def opening_of(sentence: str, words: int = _OPENER_WORDS) -> str:
    """The first couple of words, lowercased — the handle a formula is held by."""
    found = re.findall(r"[A-Za-z']+", sentence or "")
    return " ".join(w.lower() for w in found[:words])


def texture(text: str, earlier: list[str] | None = None) -> dict:
    """Countable facts about one turn's prose.

    No verdict attached. A caller that wants one applies its own threshold — `review`
    uses exactly one of these, and only at a share no healthy run approaches.
    """
    sentences = _sentences(text)
    lengths = [len(re.findall(r"[A-Za-z']+", s)) for s in sentences]
    openers = [opening_of(s) for s in sentences]
    before = [opening_of(s) for e in (earlier or []) for s in _sentences(e)]
    return {
        "chars": len(text or ""),
        "sentences": len(sentences),
        "words_mean": round(sum(lengths) / len(lengths), 1) if lengths else 0.0,
        # Spread, not average. A page of fourteen-word sentences and a page that runs
        # from four words to forty read nothing alike and average the same.
        "words_spread": (round(statistics.pstdev(lengths), 1)
                         if len(lengths) > 1 else 0.0),
        "opens": openers[0] if openers else "",
        # Openings this turn shares with the turns just before it. The soft form of
        # `repeats-an-earlier-beat`, which only catches a whole sentence repeated exactly.
        "echoed_openings": sum(1 for o in openers if o and o in before),
        "second_person": sum(1 for o in openers if o.split()[:1] == ["you"]),
        "has_speech": bool(re.search(r'["“][^"”]{4,}["”]|\'[^\']{8,}\'', text or "")),
    }


def formulaic(turns: list[str]) -> tuple[float, str]:
    """How much of a run opens the same way, and the opener that does it.

    For the harness rather than for a turn: formula is a property of a session, and a
    single turn opening "You step" says nothing at all.
    """
    firsts = [opening_of(_sentences(t)[0]) for t in turns if _sentences(t)]
    if not firsts:
        return 0.0, ""
    counted = Counter(firsts).most_common(1)[0]
    return counted[1] / len(firsts), counted[0]


# --- the consequence call ------------------------------------------------------------------

# The scaffold headers of `prompts.call_two_messages`, as they come back when a model
# echoes its own prompt. Measured on richardyoung/qwen3-4b-instruct-2507-abliterated,
# first live playtest turn: the whole user message came back inside the answer — headers,
# bullet lists, the lot — repeated four times over, 2,897 characters written straight into
# the transcript because nothing stood between call 2 and `c.transcript.append`.
#
# Matched anywhere, not only at line starts: the echoed header lands mid-line whenever the
# model glues it to the end of a sentence — "...falling. The player said: I look around" —
# and an anchored pattern left exactly that fragment in front of the player.
_SCAFFOLD = re.compile(
    r"(?:the player said|you had already narrated|what the engine decided"
    r"|why it was rolled)\b[:\s]*[^\n]*|^\s*-\s.*$", re.I | re.M)

# Two or three sentences is the brief; this is far past any honest answer and exists so a
# looping model cannot write a page. Same reasoning as MAX_COMBAT_CHARS: a cap set above
# everything legitimate catches only the pathological.
MAX_CONSEQUENCE_CHARS = 700


# The consequence example's own scenery, which was chosen to exist nowhere in the shipped
# world precisely so this list could be written. Verified live within the hour: llama
# narrated a guild-yard punch and continued "the ferry's motion is starting to get worse,
# and you can feel it pulling loose from its moorings" — a paraphrase, which no verbatim
# check can touch, but the nouns give it away. A sentence naming one of these is the
# example bleeding through, unless the turn itself is genuinely about a ferry — which is
# what the `context` parameter decides.
_EXAMPLE_MARKS = ("ferry", "mooring", "piling", "ashka", "verel", "old man", "ferryman")

# The NPC-turn examples have a cast of their own, and it bleeds the same way: in a real
# bear fight the bear's turn was narrated as "The thug, grinning..., swinging the sap" and
# the consequence call staggered "the old man" — the worked examples playing themselves
# instead of the scene, in common nouns no capitalised-name check can see. Unlike the
# ferry, a thug and a guildhand genuinely exist as templates, so the context parameter is
# what keeps a real thug fight narratable: the caller passes the scene's actual cast.
_NPC_EXAMPLE_MARKS = ("thug", "guildhand", "old man")
# Not "sap": it is the thug template's real weapon, so a genuine thug fight talks about
# it constantly, and every bled sentence observed live named its wielder anyway.


def _example_bled(sentence_key: str, marks, low_context: str) -> bool:
    """Whether a sentence names the worked examples' own cast or scenery.

    Word-boundary matches, not substrings — "sap" must not condemn "sapling", and it was
    substring matching that would have made this check too eager to ship for the NPC
    marks at all.
    """
    for mark in marks:
        # A trailing s is allowed — the live ferry catch was the plural "moorings" —
        # but nothing longer: "sapling" is not "sap".
        if re.search(rf"\b{re.escape(mark)}s?\b", sentence_key) and mark not in low_context:
            return True
    return False


def strip_example_cast(text: str, context: str, marks=_NPC_EXAMPLE_MARKS) -> str:
    """Drop the sentences in which a worked example plays itself.

    Same doctrine as `clean_consequence`, applied to NPC-turn narration: detect
    mechanically, and cutting too much is safe because the engine's own tell still says
    what happened. `context` is everything the turn is genuinely about — the scene's
    cast above all — and a mark found there is not a bleed.
    """
    if not text:
        return ""
    low_context = (context or "").lower()
    kept = [(" ".join(s.split())) for s in _SENTENCE.findall(text)
            if not _example_bled(s.lower().strip(".!? "), marks, low_context)]
    out = " ".join(kept).strip()
    if not re.search(r"[a-zA-Z]", out):
        return ""
    return out


def clean_consequence(text: str, example_answer: str = "", context: str = "") -> str:
    """What survives of a call-2 reply once the prompt itself is taken back out of it.

    Everything here is mechanical — no model call, following the rule that held all
    through World Bible: detect mechanically, and only then decide whether to repair.
    The caller treats an empty answer as "render the engine's tells raw", which is always
    correct and never invents anything, so cutting too much is safe and cutting too
    little puts prompt scaffolding in front of the player.

    Three cuts, in the order the damage was observed:

    - scaffold lines: the model returning its own prompt as prose;
    - the worked example's answer: the 4B copied it word for word, and because the example
      had been written about the very guildhand the fixture opens on, the plagiarism read
      exactly like play and narrated the player over a wall they never went near;
    - repetition: the loop that wrote the same paragraph four times. Sentences are kept
      once, in order, and the text is capped.
    """
    if not text:
        return ""
    text = _SCAFFOLD.sub("", text)

    if example_answer:
        for sentence in _SENTENCE.findall(example_answer):
            wanted = sentence.strip()
            if len(wanted) > 20:
                text = text.replace(wanted, "")

    low_context = (context or "").lower()
    seen: set[str] = set()
    kept: list[str] = []
    for sentence in _SENTENCE.findall(text):
        s = " ".join(sentence.split())
        key = s.lower().strip(".!? ")
        if not key or key in seen:
            continue
        if _example_bled(key, _EXAMPLE_MARKS, low_context):
            continue
        seen.add(key)
        kept.append(s)
    out = " ".join(kept).strip()
    # A residue with no letters — a lone "-", a stray bullet glyph — is not a sentence,
    # and rendering it prints punctuation as the GM's whole reply. Observed live: the
    # transcript line read exactly "-".
    if not re.search(r"[a-zA-Z]", out):
        return ""
    return out[:MAX_CONSEQUENCE_CHARS].rstrip()


# What counts as the prose having actually put a death on the page.
_DEATH_LANGUAGE = re.compile(
    r"\b(dead|dies|died|dying|lifeless|corpse|slain|kills?|killed|"
    r"no longer breath\w*|last breath|life leaves|lifeblood)\b", re.I)


def death_on_the_page(text: str, name: str) -> bool:
    """Whether the prose already commits to this actor's death.

    A sentence naming them (or carrying a third-person pronoun, which in a beat about
    one death is them) with death language in it. Shared by the finding in `review`
    and by the backstop below, so the two cannot disagree about what counts.
    """
    first = str(name or "").split()[0] if str(name or "").strip() else ""
    if not first:
        return False
    return any(_DEATH_LANGUAGE.search(s) for s in _sentences(text)
               if re.search(rf"\b{re.escape(first)}", s, re.I)
               or re.search(r"\b(he|she|they)\b", s, re.I))


def definite(name: str) -> str:
    """"sailor" → "the sailor"; "Grist" and "the watchman" stay as they are.

    Measured in `spooter.json`: four death lines reading "fell sailor as unmake them",
    because the actor's name was a bare common noun and the template pasted it in
    unchanged. A capitalised name is a proper name; a lowercase one is a kind of
    person and takes the article.
    """
    name = " ".join(str(name or "").split())
    if not name:
        return name
    first = name.split()[0]
    if first[:1].isupper() or first.lower() in {"the", "a", "an", "your", "his", "her",
                                                  "their", "its", "my", "our", "some"}:
        return name
    return "the " + name


# How the death line is chosen: by what the blow was and how far past dead it went,
# never by asking for variety.
#
# Measured 2026-09-17 in the player's own saves: `spooter.json`, eleven beats, four
# kills, four BYTE-IDENTICAL sentences — "The blow does not so much fell sailor as
# unmake them…" — because a one-punch kill reaches the top rung every time and the top
# rung held exactly one line. The player quoted it back as the narrator's tic. It was
# ours.
#
# Rebuilt the way six codebases that were read at source do it (docs/narrator-guards.md):
# CircleMUD consults a random pool only for misses and death blows, and every death line
# in it is anatomical and specific to the attack type; QuickMUD (a ROM fork — stock ROM
# 2.4 used absolute damage) keys severity on damage as a share of the victim's own hit
# points; Discworld crosses attack type with body part; DCSS lets the target supply the
# image. None of them fixed thin, repetitive kill text
# by asking for variety — they added mechanical axes and kept the pools tiny. So: three
# lines per cell, each concrete, keyed on the damage family and the margin bucket, and
# chosen least-recently-used per campaign, which is Inform 7's default `[at random]`
# ("the same choice cannot come up twice running … to avoid the deadening effect of
# repeating the exact same message") made deterministic.
#
# Slots: {name} (with its article), {subj}/{Subj}, {obj}, {poss}, {self}, {is_}, {was},
# {has}, {does}, and the verb suffixes {s}/{es}, so a group actor ("the guards") reads as
# grammatically as one person. No number anywhere: the third law.
# Every line says "dead" in as many words. `death_on_the_page` is what decides whether
# a death reached the page, and a backstop whose own sentence it could not recognise
# would be pressed again by the next pass over the same beat.
_DEATHS: dict[str, dict[str, list[str]]] = {
    "bludgeoning": {
        "barely": [
            "{name} take{s} it on the side of the head and {poss} knees go first; {subj} "
            "{is_} on the ground before {poss} hands know to break the fall, and {subj} "
            "{does} not get up. {Subj} {is_} dead.",
            "The blow lands under {poss} ear. {name} stand{s} one moment longer with "
            "{poss} mouth working, then fold{s} sideways and lie{s} dead.",
            "It catches {name} across the temple; {subj} sit{s} down hard, sway{s} once, "
            "and slump{s} over dead.",
        ],
        "ruinous": [
            "The impact caves in the side of {poss} skull. {name} drop{s} dead where "
            "{subj} stood, one arm flung out, and the only movement after that is the "
            "blood finding the low side of the floor.",
            "{name}'s chest gives under it with a sound like a crate stove in. {Subj} "
            "{is_} thrown back a step, {poss} legs already gone, and land{s} dead.",
            "It breaks {poss} neck. {name}'s head goes over at an angle no living neck "
            "allows and {subj} drop{s} in a heap, dead before the fall is done.",
        ],
        "overkill": [
            "The blow does not stop at {name}. It goes through the skull and carries on, "
            "and what hits the ground is dead and has no face left to speak of.",
            "{name} burst{s} under it. The head is simply gone, and the body stands for "
            "one grotesque instant, spraying, before it topples, dead.",
            "It drives {name}'s ribs through lung and heart together; {subj} {is_} dead "
            "standing, and fall{s} a moment later like a coat slipping off a hook.",
        ],
    },
    "piercing": {
        "barely": [
            "The point goes in under {poss} ribs and {name} fold{s} over it, mouth "
            "working, and slide{s} off the steel to the ground, dead, without another "
            "sound.",
            "It finds {poss} throat. {name} clap{s} both hands to it and the blood comes "
            "through {poss} fingers anyway, and {subj} kneel{s}, and then {subj} {is_} "
            "lying down, dead.",
            "{name} look{s} down at the thing standing out of {poss} chest as if somebody "
            "else had put it there, and {poss} legs quit, and {subj} {is_} dead by the "
            "time {subj} reach{es} the floor.",
        ],
        "ruinous": [
            "It goes in through the eye. {name} stop{s} — every part of {obj} at once — "
            "and drop{s} straight down like a cut rope, dead.",
            "The point takes {name} through the heart and out under the shoulder blade. "
            "{Subj} {has} time to look surprised, and no more; {subj} {is_} dead on "
            "{poss} feet.",
            "It punches through {poss} breastbone and {name} {is_} lifted onto {poss} "
            "toes by it, hanging there with {poss} arms slack, and when it is pulled "
            "free {subj} {is_} only dead weight.",
        ],
        "overkill": [
            "It goes through {name} and out the other side with most of {poss} back on "
            "it. {Subj} fall{s} in two directions at once, dead.",
            "The blow opens {name} from breastbone to hip; the insides follow it out, "
            "and {subj} drop{s} into them, dead.",
            "{name} {is_} pinned through and lifted clean off {poss} feet, and where the "
            "point stops so {does} {subj}: {poss} head goes back, {subj} {is_} dead, "
            "and nothing in {obj} moves again.",
        ],
    },
    "slashing": {
        "barely": [
            "The edge opens {poss} throat. {name} stagger{s} two steps, hands full of it, "
            "and sit{s} down against nothing and {is_} dead.",
            "It takes {name} across the belly and {subj} fold{s} over the wound, trying "
            "to hold {self} shut, and cannot, and {is_} dead on {poss} knees.",
            "The cut goes deep under the arm. {name} turn{s} half round as if to leave, "
            "and the leaving becomes a fall, and the fall ends with {obj} dead on the "
            "ground.",
        ],
        "ruinous": [
            "It takes {poss} arm at the shoulder and half the chest beneath it. {name} "
            "look{s} at the place where the arm was, and then {subj} {is_} dead on the "
            "ground, and the blood is everywhere the arm is not.",
            "The edge goes through {poss} collarbone and into the chest. {name} drop{s} "
            "the way a puppet drops when the hand lets go — all at once, every string, "
            "dead.",
            "{name}'s head comes half off. {Subj} stand{s} a heartbeat longer, a "
            "fountain, and then the knees give and {subj} {is_} a dead heap on the "
            "stones.",
        ],
        "overkill": [
            "The edge goes through {name} from shoulder to hip and does not slow; {subj} "
            "{is_} dead in the same instant, and the two halves part company on the way "
            "down.",
            "{name} {is_} opened like a sack, everything inside {obj} on the ground "
            "before the rest of {obj} follows it, dead.",
            "It takes {poss} head clean off. The body of {name} stands for one long "
            "instant, not yet informed, then drops, dead.",
        ],
    },
    "fire": {
        "barely": [
            "The heat takes {name} in the face and the scream stops in the middle. "
            "{Subj} fall{s} burning, and the burning goes on after {subj} {is_} dead.",
            "{name} beat{s} at the flames on {poss} chest and the beating slows and "
            "stops, and {subj} sink{s} down dead into the fire {subj} {was} making.",
            "The fire finds {poss} lungs. {name} draw{s} one breath of it, and there is "
            "no second; {subj} {is_} dead where {subj} stood.",
        ],
        "ruinous": [
            "{name} go{es} up like oiled cloth. Whatever {subj} {was} trying to shout is "
            "lost in the roar, and what drops to the ground is black and dead.",
            "The blast lifts {name} off {poss} feet and sets {obj} down again alight, "
            "and {subj} {does} not get up from it; {subj} {is_} dead.",
            "Heat strips the skin from {poss} arms before {subj} can raise them; {name} "
            "fall{s} forward dead into it, and the smell arrives a moment after the "
            "silence.",
        ],
        "overkill": [
            "There is a flash and {name} {is_} dead in the instant of it — a shape of "
            "ash standing in {poss} own outline, and then not even that.",
            "The fire goes through {name} entire. What falls out of it onto the stones "
            "is dead: bone with the meat cooked off it, still smoking.",
            "{name} {is_} dead and gone into the blaze so fast that the shadow on the "
            "wall behind {obj} outlasts {obj}.",
        ],
    },
    "cold": {
        "barely": [
            "The cold goes into {name} and {poss} breath stops on the way out, white, "
            "and hangs there after {subj} {has} fallen dead.",
            "{name} shudder{s} once, violently, and then not at all; {subj} {is_} rigid "
            "and dead before {subj} reach{es} the ground.",
            "Frost climbs {poss} face from the jaw up. {name} blink{s} at it, once, and "
            "the eyes stay open and go dull; {subj} {is_} dead.",
        ],
        "ruinous": [
            "It freezes {name} dead where {subj} stand{s}. The fall comes a moment "
            "later, and something breaks off when {subj} land{s}.",
            "The cold stops {poss} heart between one beat and the next. {name} {is_} "
            "already dead when {poss} knees hit the floor, rimed white to the elbows.",
            "{name}'s scream turns to frost in the air. {Subj} {is_} dead before {subj} "
            "topple{s}, like something carved, and shatter{s} at the shoulder.",
        ],
        "overkill": [
            "{name} {is_} dead and ice before {subj} {is_} anything else — a figure of "
            "it, mouth open — and the figure comes apart on the stones.",
            "The cold takes {name} so completely that the dead body rings when it falls, "
            "and the arm that hits first breaks off and skids away.",
            "Frost goes through {name} to the marrow in an instant; what topples is a "
            "statue of {obj}, dead, and it does not survive the landing whole.",
        ],
    },
    # Acid, lightning, sonic, force, the untyped: what the engine does not name a
    # family for is written as the body failing rather than as a wound of a kind.
    "other": {
        "barely": [
            "{name} jerk{s} as if struck from inside, and the strength leaves {obj} all "
            "at once, and {subj} {is_} down and dead.",
            "Something goes out of {name}'s face — not pain, exactly; more like "
            "attention — and {subj} sag{s} and fall{s} and {does} not stir again; "
            "{subj} {is_} dead.",
            "{name} take{s} one step that is not toward anything, and the second step "
            "is a fall, and after that nothing: {subj} {is_} dead.",
        ],
        "ruinous": [
            "It goes through {name} like a shout through a room. {Subj} arch{es}, every "
            "muscle at once, and drop{s} slack and dead.",
            "{name} {is_} thrown down as if the ground had reached up for {obj}, and "
            "lie{s} dead where {subj} land{s}, eyes open, seeing nothing.",
            "Whatever it is takes {name} at the root. {Subj} fold{s} in on {self} and "
            "{is_} dead before the fold is finished.",
        ],
        "overkill": [
            "{name} come{s} apart under it — torn loose at the joints, and what lands "
            "has already stopped being a person; {subj} {is_} dead.",
            "The force of it empties {name} the way a struck bell empties of sound; "
            "{subj} {is_} dead on {poss} feet and fall{s} a moment later.",
            "It goes through {name} and leaves nothing standing behind it but the "
            "outline of where {subj} {was}; {subj} {is_} dead.",
        ],
    },
}

_DEATH_FAMILIES = ("bludgeoning", "piercing", "slashing", "fire", "cold")


def death_family(dtype: str) -> str:
    """The pool a damage type draws from. Anything unnamed is `other`."""
    d = str(dtype or "").strip().lower()
    for fam in _DEATH_FAMILIES:
        if fam in d:
            return fam
    return "other"


def death_bucket(margin: int, hp_max: int) -> str:
    """How far past dead, in words: damage as a share of the victim (QuickMUD's rule,
    the one change a ROM fork made to thirty-five years of absolute thresholds), in
    three rungs."""
    hp_max = max(1, int(hp_max or 1))
    margin = int(margin or 0)
    if margin >= hp_max:
        return "overkill"
    if margin >= max(3, hp_max // 2):
        return "ruinous"
    return "barely"


def least_recently_used(said: dict | None, key: str, size: int) -> int:
    """Pick from a pool the index that has waited longest, and record the pick.

    Inform 7's `[at random]` — the same alternative never twice running — made
    deterministic and stretched: a pool of three is walked whole before any line
    returns, and the walk is stored on the campaign (`Scene.said`) so it survives a
    reload. Handed no store, it returns the first line, which is what a caller with
    no campaign (a test, a one-off) should get.
    """
    size = max(1, int(size))
    if said is None:
        return 0
    used = [int(i) for i in (said.get(key) or []) if isinstance(i, (int, float))]
    unused = [i for i in range(size) if i not in used]
    # `used` is oldest-first, so the line that has waited longest is the one nearest
    # the FRONT. The first cut took the nearest the back and, once a pool had been
    # walked, returned its last line for ever — the smoke test caught it on the fifth
    # kill.
    pick = unused[0] if unused else min(range(size), key=lambda i: used.index(i))
    used = [i for i in used if i != pick] + [pick]
    said[key] = used[-size:]
    return pick


def _fill(line: str, name: str, subj: str, obj: str, poss: str) -> str:
    plural = subj == "they"
    words = {
        "name": name, "subj": subj, "Subj": subj[:1].upper() + subj[1:], "obj": obj,
        "poss": poss,
        "self": {"he": "himself", "she": "herself", "it": "itself"}.get(subj, "themselves"),
        "is_": "are" if plural else "is", "was": "were" if plural else "was",
        "has": "have" if plural else "has", "does": "do" if plural else "does",
        "s": "" if plural else "s", "es": "" if plural else "es",
    }
    out = line.format(**words)
    # A name opens some of these lines mid-way — "…beneath it. {name} look{s}…" — and
    # "the guards" arrives lowercase, so every sentence start is capitalised, not only
    # the first.
    out = re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)
    return out[:1].upper() + out[1:]


def death_line(death: dict, said: dict | None = None) -> str:
    """The authored backstop for one death, chosen by its axes and never twice running."""
    name = definite(str(death.get("name") or ""))
    fam = death_family(str(death.get("family") or ""))
    bucket = death_bucket(int(death.get("margin", 0) or 0), int(death.get("hp_max", 1) or 1))
    pool = _DEATHS[fam][bucket]
    pick = least_recently_used(said, f"death:{fam}/{bucket}", len(pool))
    # The actor's own pronouns, defaulting neutral — the same courtesy `right_body`
    # already enforces everywhere else in the prose.
    return _fill(pool[pick], name, str(death.get("subj") or "they"),
                 str(death.get("obj") or "them"), str(death.get("poss") or "their"))


def press_the_death(text: str, deaths: list[dict],
                    said: dict | None = None) -> tuple[str, list[str]]:
    """A kill the engine resolved must be a death the prose commits to.

    Measured live: a watchman at -21 of 11 hit points — twice his whole life past
    dead — was narrated as "his eyes widen in shock as he struggles to catch his
    breath". Nobody struggles for breath at -21; the model writes wounded-man prose
    because wounded men are what its training saw, and no instruction has moved it.

    This is now the BACKSTOP, not the repair. The repair is `review`'s
    `death-left-off-the-page`, which hands the model the facts of the death and asks
    for the two sentences itself; this runs only when that rewrite was refused or
    failed, and what it appends is chosen by `death_line` — by damage family and
    margin, least recently used — rather than the one sentence per rung it used to
    hold. Measured before the change: four kills, four identical lines.

    `deaths` entries: {"name", "margin" (hit points past the death line), "hp_max",
    "family" (the damage type), "subj"/"obj"/"poss"}. Appended after grooming.
    """
    added = []
    for d in deaths or []:
        name = str(d.get("name") or "").strip()
        if not name or death_on_the_page(text, name):
            continue
        added.append(name)
        text = _append_before_hand_back(text, death_line(d, said))
    return text, added


def _append_before_hand_back(text: str, line: str) -> str:
    """Insert before a trailing question, else append — a death narrated after
    "What do you do?" reads like the GM forgot and doubled back."""
    parts = _sentences(text)
    if parts and parts[-1].rstrip().endswith("?"):
        return " ".join(parts[:-1] + [line, parts[-1]]).strip()
    return (text.rstrip() + " " + line).strip()


def added_sentences(before: str, after: str) -> list[str]:
    """The sentences `after` has that `before` did not — what a backstop appended."""
    had = set(_sentences(before))
    return [s for s in _sentences(after) if s not in had]


def own_prose(transcript, n: int = 12) -> list[str]:
    """The narrator's own recent beats, as the model wrote them: the last `n` GM beats
    of kind "setup", each with the pipeline's appended sentences taken back out.

    Two things this is not, both measured 2026-09-17 on the first sixty-turn run after
    the guards. Not the engine's lines: award and tell beats ("You gain XP for moving a
    matter along", "The fight is over") are `consequence`, and shown back as "what you
    narrated" they became the register of four of the last nineteen beats. And not
    four beats long: the window used to be `transcript[-8:]` filtered to the GM, which
    with the player's lines interleaved left the phrase check (twelve beats by design)
    looking at four — it fired once in fifty turns while the phrase it exists for sat
    in eleven of them. Every consumer slices its own tail from this list, so widening it
    changes nothing for the ones that wanted six or two.
    """
    out = []
    for b in list(transcript or [])[-4 * n:]:
        if not isinstance(b, dict) or b.get("who") != "gm" or b.get("kind") != "setup":
            continue
        text = strip_added(str(b.get("text") or ""), b.get("added"))
        if text:
            out.append(text)
    return out[-n:]


def strip_added(text: str, added) -> str:
    """The beat as the model wrote it, with the pipeline's own appended sentences
    taken back out.

    Used to build what the next prose call is shown of the narrator's recent work. Xu
    et al. (NeurIPS 2022) measured why this matters: a sentence already in the context
    self-reinforces, and the likelier it was to begin with the faster it converges. An
    authored death line or thread anchor shown back as "what you narrated just before
    this" is a template being taught — measured in `spooter.json`, where the model
    began writing the template's own word ("unmade") after seeing it once.
    """
    if not text or not added:
        return text or ""
    gone = {str(a).strip() for a in added if str(a).strip()}
    kept = [s for s in _sentences(text) if s not in gone]
    return " ".join(kept).strip()


_THREAD_STOP = {"the", "a", "an", "that", "who", "which", "walked", "away", "two",
                "three", "some", "their", "his", "her", "its", "in", "of", "with",
                "and", "to", "from", "near", "by"}


# The anchor, in five shapes, chosen least recently used. Measured on the 2026-09-17
# sixty-turn baseline: the single old anchor — "Through it all you keep your attention
# where you put it: …" — shipped verbatim in four of fifty-three beats, the same defect
# as the death template and for the same reason (one line, appended every time). None
# of these needs the subject to agree in number, so "the woman" and "the two guards"
# both read.
_ANCHORS = (
    "You have not let {subject} out of your sight; you are still {doing} them.",
    "Whatever else is happening, you have not lost {subject}: you are still {doing} "
    "them.",
    "None of it moves you off {subject} — you are still {doing} them, and they have "
    "not slipped away.",
    "You keep {subject} where you can see them, and go on {doing} them.",
    "In front of you, still: {subject}. You are still {doing} them.",
)

_WH_SUBJECT = re.compile(r"^(?:who|whom|whose|what|which|where|when|why|how|whether|if)\b",
                         re.I)
_FIRST_IN_SUBJECT = re.compile(r"\b(?:i|i'm|i'll|i've|i'd|me|my|mine|myself)\b", re.I)


def keep_the_thread(text: str, thread: dict, said: dict | None = None) -> tuple[str, str]:
    """The subject of a standing engagement cannot vanish from the page.

    Measured live: following two guards toward a market, the next beat was a
    haunted house and the guards were gone — the model lost the thread, and no
    instruction has ever held one. So the check is code: if none of the subject's
    content words survive into the beat, an anchor sentence is added before the
    hand-back. It re-tethers rather than rewrites — the model's scenery stands,
    but the person the player is engaged with is put back in it.

    Two things the anchor may not do, both measured on the sixty-turn baseline: repeat
    itself (one shape, four times in fifty-three beats — so `_ANCHORS`, least recently
    used), and carry the player's own words in the first person. "I ask who I should
    speak to about work outside the walls" made *who I should speak to…* the subject,
    the anchor placed it in the narration, and `narrator-in-first-person` fired on our
    own sentence. A subject that is a clause rather than somebody is refused here
    (belt) and no longer set by `judgement.update_thread` (braces); a first-person
    token that somehow arrives is turned to the second person before it is placed.
    """
    subject = str((thread or {}).get("subject") or "").strip()
    if not subject or not text:
        return text, ""
    if _WH_SUBJECT.match(subject):
        return text, ""
    words = [w for w in re.findall(r"[a-z']+", subject.lower())
             if w not in _THREAD_STOP and len(w) > 2]
    if not words:
        return text, ""
    if any(re.search(rf"\b{re.escape(w)}", text, re.I) for w in words):
        return text, ""
    # Pronouns are presence. Measured live: a whole beat written about her —
    # 'her eyes close', 'she leans into the contact' — never used the word
    # 'woman', so the anchor fired and told the player they were still waiting
    # for somebody who was in their arms. A beat carrying third-person pronouns
    # and introducing nobody new is continuing with the person already there.
    if re.search(r"\b(she|her|hers|he|him|his|they|them|their)\b", text, re.I):
        return text, ""
    placed = _FIRST_IN_SUBJECT.sub(
        lambda m: {"i": "you", "i'm": "you're", "i'll": "you'll", "i've": "you've",
                   "i'd": "you'd", "me": "you", "my": "your", "mine": "yours",
                   "myself": "yourself"}.get(m.group(0).lower(), m.group(0)), subject)
    doing = str(thread.get("doing") or "").strip() or "with"
    pick = least_recently_used(said, "anchor", len(_ANCHORS))
    anchor = _ANCHORS[pick].format(subject=placed, doing=doing)
    return _append_before_hand_back(text, anchor), subject


def already_there(text: str, where: str) -> tuple[str, list[str]]:
    """You cannot arrive at the place you are standing in.

    Measured live twice in one session: the player and the stranger were both in
    the market, and the beat had them "heading towards the central market square"
    and re-entering it. The thread knows where they already are, so arrival
    language aimed at that place is rewritten in place — the smallest edit that
    keeps the model's scenery while unbreaking the geography.
    """
    where = str(where or "").strip()
    if not where or not text:
        return text, []
    head = re.escape(re.sub(r"^the\s+", "", where, flags=re.I))
    swaps = [
        (rf"\b(step|walk|head|move|push|go|going|heading|making (?:your|their) way)"
         rf"(s|ing|es)?\s+(?:back\s+)?(?:to|towards?|into|for)\s+(the\s+{head})",
         r"\1\2 through \3"),
        (rf"\b(enter|re-enter|reenter)(s|ing|ed)?\s+(the\s+{head})",
         r"cross\2 \3"),
        (rf"\b(arrive|arriving|arrives?d?)\s+(?:at|in)\s+(the\s+{head})",
         r"stand in \2"),
        (rf"\b(reach|reaches|reaching)\s+(the\s+{head})", r"move through \2"),
    ]
    done = []
    for pat, rep in swaps:
        new = re.sub(pat, rep, text, flags=re.I)
        if new != text:
            done.append(rep)
            text = new
    return text, done


# Verbs a combat beat actually uses, base forms the s-form maps to. A list, not a
# stemmer: "you gauntlets" is a noun and must not be "fixed".
_YOU_VERBS = {
    "is": "are", "was": "were", "has": "have", "does": "do",
    "swings": "swing", "steps": "step", "drives": "drive", "brings": "bring",
    "takes": "take", "catches": "catch", "moves": "move", "presses": "press",
    "turns": "turn", "raises": "raise", "lunges": "lunge", "slams": "slam",
    "throws": "throw", "lands": "land", "feels": "feel", "sees": "see",
    "hears": "hear", "stands": "stand", "drops": "drop", "pulls": "pull",
    "pushes": "push", "grips": "grip", "draws": "draw", "breathes": "breathe",
    "ducks": "duck", "dodges": "dodge", "staggers": "stagger",
    "strikes": "strike", "watches": "watch", "reaches": "reach",
    "keeps": "keep", "holds": "hold", "looks": "look", "leans": "lean",
    "knows": "know", "finds": "find", "twists": "twist", "readies": "ready",
    "closes": "close", "opens": "open", "charges": "charge", "leaps": "leap",
    "plants": "plant", "snaps": "snap", "sets": "set",
    # The engine's own tell verbs, found when the tell fallback started flowing
    # through this: "You hits the drover" shipped with an s.
    "hits": "hit", "misses": "miss", "gains": "gain", "attacks": "attack",
    "deals": "deal", "makes": "make", "rolls": "roll", "wins": "win",
    "squares": "square", "loots": "loot", "pays": "pay", "spends": "spend",
}


def pc_to_second_person(text: str, pc_name: str) -> tuple[str, int]:
    """The player's character is 'you', even when the model names her.

    Measured on the gemma4:12b fight audit: six of twelve combat turns narrated
    "Kesst Vayr's blade..." — clean prose, wrong person, the single fault class
    of the whole run. Deterministic, whole-set, same doctrine as
    `second_person_narrator`: name and possessive swap together, the verb that
    follows is fixed from a list rather than a guess, and speech spans are left
    alone — somebody may shout her name.
    """
    name = str(pc_name or "").strip()
    if not name or not text or name.lower() not in text.lower():
        return text or "", 0
    first = name.split()[0]
    pattern = re.compile(
        rf"\b(?:{re.escape(name)}|{re.escape(first)})('s)?\b")
    protected = [m.span() for m in _QUOTED.finditer(text)]
    count = 0
    out = []
    last = 0
    for m in pattern.finditer(text):
        if any(qlo <= m.start() < qhi for qlo, qhi in protected):
            continue
        out.append(text[last:m.start()])
        out.append("your" if m.group(1) else "you")
        last = m.end()
        count += 1
    out.append(text[last:])
    if not count:
        return text, 0
    swapped = "".join(out)
    swapped = re.sub(
        r"\byou (\w+)\b",
        lambda m: "you " + _YOU_VERBS.get(m.group(1), m.group(1)),
        swapped)
    # Sentence starts: "you swing" opening a sentence keeps its capital.
    swapped = re.sub(r"(^|[.!?]\s+)you(r)?\b",
                     lambda m: m.group(1) + "You" + (m.group(2) or ""), swapped)
    return swapped, count


_SCHEMA_BLEED = re.compile(
    r'''(?x)(
        "\s*,\s*"suggestions           # the narration string closing into keys
      | ,?\s*"suggestions(\s+\w+)?"\s*:  # bare suggestions key (or mangled variant)
      | ,?\s*"intents"\s*:
      | <tool_call
      | ```+\s*json
      | ```+
      | \{\s*"narration"\s*:
    )''')


# "A merchant (c4) is haggling loudly" — the brief's refs, which exist so the model can
# NAME people in its intents, shipped to the page in the prose. Measured live,
# 2026-09-04, four of them in one beat. The tag goes; the noun before it stays.
_REF_TAG = re.compile(r"\s*\(\s*(?:c|n|pc)\d*\s*\)")


def strip_ref_tags(text: str) -> tuple[str, int]:
    """The prose with the brief's "(c4)" tags removed, and how many there were."""
    cleaned, n = _REF_TAG.subn("", text or "")
    return cleaned, n


def cut_schema_bleed(text: str) -> tuple[str, list[str]]:
    """The schema is not the story.

    Measured live on gemma4:12b: the model nested its whole JSON reply inside
    the narration field — the prose, then '", "suggestions woorden": [...]',
    a <tool_call|> marker, a fenced ```json block repeating the entire beat,
    and the intents key — and every character of it shipped to the page. The
    first schema artefact ends the prose; everything from there is plumbing.
    """
    if not text:
        return text or "", []
    m = _SCHEMA_BLEED.search(text)
    if not m:
        return text, []
    kept = text[:m.start()].rstrip().rstrip('"').rstrip()
    return kept, [text[m.start():m.start() + 40]]


# The assistant stepping out from behind the narrator to decline. Not a moral
# judgement on the tune — a mechanical fact about this reply: it is commentary
# about the scene rather than the scene, so the turn has no prose yet.
_DECLINED = re.compile(
    r"\b(?:i(?:'m| am)?\s*(?:can(?:no|')t|won'?t|will not|unable to|not able to|"
    r"not comfortable|cannot)\s+(?:write|continue|create|generate|assist|help|"
    r"produce|narrate|depict|go)"
    r"|as an ai\b"
    r"|i (?:must|have to) (?:decline|refuse)"
    r"|(?:this|that) (?:request|content) (?:is|violates)"
    r"|i'?m sorry,? but\b)", re.I)


def reads_as_a_refusal(text: str) -> bool:
    """Whether this reply is the assistant declining rather than the GM narrating.

    Detected, not argued with: a tune that will not write a beat is the wrong
    tune for that beat, and the fallback model exists for exactly that. Only
    fires on short replies — a long passage that happens to contain "I can't"
    in dialogue is a character speaking, which is the opposite of a refusal.
    """
    t = (text or "").strip()
    if not t or len(t) >= 600:
        return False
    # In the opening sentence and outside quotes. "'I can't help you,' she says"
    # is a character refusing inside the fiction — the opposite of the model
    # refusing to write it — and an unanchored search called that a refusal.
    head = _sentences(t)[:1]
    if not head:
        return False
    first = head[0]
    if _QUOTED.search(first):
        return False
    return bool(_DECLINED.search(first))


def reintroduces_the_present(text: str, names) -> list[str]:
    """Somebody already standing here cannot walk in as a stranger.

    Measured live on an intimate beat the model would not continue: instead of
    a refusal it wrote a different scene — a door broken down, and 'A woman is
    there', indefinite, as though meeting her for the first time, though she had
    been in the player's arms one beat earlier. A deflection reads as prose and
    passes every check aimed at refusals, but it always leaves this fingerprint:
    an indefinite article in front of somebody the scene already holds.

    Returns the names re-introduced. The caller decides what to do with a beat
    that has lost the scene — the honest answer is to ask a different model.
    """
    if not text:
        return []
    found = []
    # A group is not a person. The cast ledger promotes "a group of men in fine
    # tunics" to four actors each called "man", and "a man" in the next beat is not
    # the fingerprint above — there are four of him already and the prose has every
    # right to a fifth. Reported at the table, 2026-09-04: two beats in a row fell
    # to the holding line because gemma's good answer read "lost the scene,
    # re-introduced man, man, man, man" and was thrown away, and the fallback model
    # then died on its budget. A name that several actors share is a group's.
    from collections import Counter

    shared = {n for n, c in Counter(str(n or "").strip().lower() for n in names or ()).items()
              if c > 1}
    for name in names or ():
        if str(name or "").strip().lower() in shared:
            continue
        head = str(name or "").strip().lower().split()[-1:] or [""]
        head = head[0]
        if len(head) < 3:
            continue
        if re.search(rf"\b(?:a|an|another)\s+(?:\w+\s+){{0,2}}{re.escape(head)}\b",
                     text, re.I):
            found.append(str(name))
    return found


# --- when the player spoke and the turn produced nothing ---------------------------
#
# The holding line ("The moment holds — nothing new shows itself just yet.") is a
# parser-error floor. Measured on the 2026-09-08 playtest, it was answering SPEECH:
# every time the player wrote something their character said, the reply came back as
# the holding line or as "You have no honest answer to give", while physical actions
# in the same session worked. The player's note: dialogue "struggles more than if i
# write actions".
#
# No tradition in interactive fiction accepts silence here. TADS 3 asks authors to
# define a `DefaultAskTellTopic` matched at the lowest possible priority, so a topic
# nobody anticipated still reaches a designed, in-character non-answer. Façade carries
# a catch-all discourse act, `DASystemCannotUnderstand`, plus "generic deflection and
# recovery global mix-ins" that run whatever beat is active. Emily Short's craft
# writing treats a bare "nothing happens" as a named failure, and names the
# alternative: a characterful reply that reveals something and admits the attempt
# happened. See docs/speech-vs-action.md.
#
# So this is the floor for a turn where the player spoke: it never claims a mechanic,
# never invents a fact, and never says nothing. Four shapes rather than one, chosen by
# the turn number, because ten paragraphs ending the same way is this project's oldest
# measured smell.
_UNANSWERED = (
    "{who} hears you out, and gives you nothing back but a look.",
    "Your words land on {who}, and sit there a moment without an answer.",
    "{who} takes that in. Whatever it settles, it is not settled yet.",
    "You say your piece. {who} lets the quiet do the answering.",
)


def unanswered_speech(player_text: str, names=(), turn: int = 0) -> str:
    """An in-character non-answer for a turn where the player spoke and nothing came.

    `names` is who is actually in the scene, so the reply can address the person the
    player addressed and nobody else. Ground every name: if the line names nobody the
    engine holds, the answer stays with the people who are demonstrably here.
    """
    line = str(player_text or "")
    who = ""
    for name in names or ():
        head = str(name or "").strip()
        if len(head) > 2 and re.search(rf"\b{re.escape(head.split()[-1])}\b", line, re.I):
            who = head
            break
    if not who:
        who = "whoever is nearest"
    # Capitalised once, at the front of the finished sentence rather than on the name:
    # two of the four shapes carry {who} mid-sentence, and "Your words land on The
    # clerk" is what capitalising the substitution gives you.
    shape = _UNANSWERED[int(turn) % len(_UNANSWERED)]
    said = shape.format(who=who)
    return said[0].upper() + said[1:] + " What do you do?"
