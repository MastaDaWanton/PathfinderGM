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


def review(text: str, *, pc_name: str = "", echo_index: set[tuple] | None = None,
           known_names: set[str] | None = None, earlier: list[str] | None = None,
           min_chars: int = 0, max_chars: int = 0, alone: bool = False) -> Review:
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
            if tok == first:                     # start of a sentence proves nothing
                continue
            if low not in found:
                found.append(tok)
    return found


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
