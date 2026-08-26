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
MIN_SCENE_CHARS = 600

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
    recent = {s.strip().lower() for e in earlier[-6:]
              for s in _SENTENCE.findall(e or "") if len(s.strip()) > 30}
    if not recent:
        return text, 0
    kept: list[str] = []
    cut = 0
    for sentence in _SENTENCE.findall(text):
        s = sentence.strip()
        if (len(s) > 30 and s.lower() in recent
                and not _OPENS_SPEECH.search(s)):
            cut += 1
            continue
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


def review(text: str, *, pc_name: str = "", echo_index: set[tuple] | None = None,
           known_names: set[str] | None = None, earlier: list[str] | None = None,
           min_chars: int = 0, max_chars: int = 0, alone: bool = False,
           pronouns: str = '', others: tuple = (), gender: str = '') -> Review:
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
