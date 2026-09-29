"""Where the speech is in a GM beat. One scanner, read by every pass that needs to know.

Measured 2026-09-25: nine separate rules answered "is this inside a quotation?" and they
disagreed. `narration._QUOTED` opened on ‘ but closed only on a double quote; two
`re.split` copies read the apostrophe in "guards'" and "it's" as a close and flipped
narration and speech for the rest of the beat; `_ANY_SPEECH` could not cross "it's";
no rule at all recognised curly single quotes, which is how the phantom elder of
2026-09-24 could still be reproduced — `place_the_face` wrote "The elder is a stooped
man…" into the middle of Korgath's ‘…’ line. Each copy had been fixed for the case in
front of it; none was fixed for the others. CLAUDE.md: "when you fix a rule, grep for
every copy of it" — this module is the answer to having to.

A scanner rather than a regex, because the one hard question is contextual: an
apostrophe INSIDE a word ("don't", "it's", "don’t" — the curly close and the curly
apostrophe are the same character) is part of the line, never its close. A close is a
quote mark not followed by a letter or a digit.

The rules:
  - "…" and “…”: a double quote opens anywhere. Unclosed, it runs to the end of its
    paragraph — the convention for a speech that goes on into the next paragraph.
  - '…' and ‘…’: a single quote opens only at the start of the text, after whitespace or
    after an opening bracket or dash, and only before a non-space. It closes on a single
    quote that is not followed by a letter or digit. Unclosed by the end of the
    paragraph, it was never a quotation: "gave 'em a hiding" and "'tis" are elisions.
  - Inside a quotation the other kind of mark is nested speech, and part of it.

Offsets are the point. `blanked` keeps the length so a detector can read the narration
and still point back into the original beat; `unquoted` collapses each quotation to one
space for the passes that only read words.
"""
from __future__ import annotations

import re

_DOUBLE_OPEN = "\"“‟"
_DOUBLE_CLOSE = {"\"": "\"“”", "“": "”\"", "‟": "”\""}
_SINGLE_OPEN = "'‘"
_SINGLE_CLOSE = "'’"
_OPENS_AFTER = "([{—–-\"“"


def _closes(text: str, i: int) -> bool:
    """A single quote at `i` is a close unless a letter or a digit follows it."""
    nxt = text[i + 1] if i + 1 < len(text) else ""
    return not nxt.isalnum()


def _paragraph_end(text: str, i: int) -> int:
    j = text.find("\n\n", i)
    return len(text) if j < 0 else j


def spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of every quotation in `text`, quote marks included, in order."""
    text = str(text or "")
    out: list[tuple[int, int]] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in _DOUBLE_OPEN:
            closers = _DOUBLE_CLOSE[ch]
            j = i + 1
            end = _paragraph_end(text, i)
            while j < end and text[j] not in closers:
                j += 1
            stop = j + 1 if j < end else end
            out.append((i, stop))
            i = stop
            continue
        if ch in _SINGLE_OPEN:
            prev = text[i - 1] if i else ""
            nxt = text[i + 1] if i + 1 < n else ""
            opens = (ch == "‘" or not prev or prev.isspace() or prev in _OPENS_AFTER)
            if opens and nxt and not nxt.isspace():
                end = _paragraph_end(text, i)
                j = i + 1
                while j < end:
                    # A space BEFORE the close is allowed: the model writes "Which path
                    # will you take? '" — measured on the real Korgath beat of
                    # 2026-09-24, and a rule refusing it read his whole speech as
                    # narration and booked the elder again.
                    if text[j] in _SINGLE_CLOSE and _closes(text, j):
                        break
                    j += 1
                if j < end:
                    out.append((i, j + 1))
                    i = j + 1
                    continue
        i += 1
    return out


def _end_of(text: str, a: int, b: int) -> int | None:
    """Where the sentence-ending mark of a quotation stands — the "!" of `"Enough!"` —
    or None when the line does not end a sentence (`'Go home,' the guard says`)."""
    k = b - 1
    while k > a and (text[k] in "\"'“”‘’" or text[k].isspace()):
        k -= 1
    if not (k > a and text[k] in ".!?"):
        return None
    # And only when a new sentence follows. `Ashla says "We go. Now." and turns away.`
    # is one sentence: the line's full stop is hers, and the narration carries on.
    rest = text[b:].lstrip(" \t")
    if rest and not (rest[0].isupper() or rest[0] == "\n"):
        return None
    return k


def blanked(text: str) -> str:
    """`text` with every quotation's characters turned to spaces, the same length —
    except the mark that ends the sentence, which stays where it stands.

    Kept because the sentence splitters read this: `He yells, "Enough!" The crowd gasps.`
    blanked whole is ONE sentence, and a cut aimed at the yell took the crowd with it
    (measured 2026-09-25)."""
    text = str(text or "")
    out = list(text)
    for a, b in spans(text):
        keep = _end_of(text, a, b)
        for k in range(a, b):
            if k != keep and not out[k].isspace():
                out[k] = " "
    return "".join(out)


def unquoted(text: str) -> str:
    """`text` with each quotation replaced by one space — and its sentence-ending mark,
    when it had one, so the sentences around it still split where they did."""
    text = str(text or "")
    parts, at = [], 0
    for a, b in spans(text):
        parts.append(text[at:a])
        keep = _end_of(text, a, b)
        parts.append(" " if keep is None else f" {text[keep]} ")
        at = b
    parts.append(text[at:])
    return "".join(parts)


def split(text: str) -> list[tuple[bool, str]]:
    """The beat as alternating runs, (is_speech, run). Joined back, it is `text`."""
    text = str(text or "")
    out: list[tuple[bool, str]] = []
    at = 0
    for a, b in spans(text):
        if a > at:
            out.append((False, text[at:a]))
        out.append((True, text[a:b]))
        at = b
    if at < len(text):
        out.append((False, text[at:]))
    return out


def lines(text: str) -> list[str]:
    """What was said: each quotation's inside, marks stripped."""
    text = str(text or "")
    return [text[a + 1:b - 1] if b - a >= 2 else "" for a, b in spans(text)]


def has_speech(text: str, min_chars: int = 1) -> bool:
    """Whether anybody speaks in `text`: a quotation with at least `min_chars` inside."""
    return any(len(s.strip()) >= min_chars for s in lines(text))


def inside(text: str, offset: int) -> bool:
    """Whether `offset` falls inside a quotation."""
    return any(a <= offset < b for a, b in spans(text))


# --- one sentence at a time --------------------------------------------------------------
#
# Some passes work on a single sentence cut out of a beat, where a quotation that runs
# across several sentences has lost its close. `spans` rightly refuses an unclosed single
# quote (it may be an elision), so these ask the lenient question — is there an OPENING
# mark here? — and they live here, beside the scanner, rather than as a tenth rule.

# An opening single quote is followed by the first letter of the line, never a space:
# "' The merchant nods" is the CLOSE of the sentence before, left at the front of this
# one by the sentence split — read as an opener it shielded a dead man's "nods" from
# `cut_dead_men_walking` (test_the_dead_cannot_talk_their_way_past_the_scrubber).
_OPENING_MARK = re.compile(r"(?:^|(?<=[\s,:(\[—–-]))['‘](?=\S)|[\"“]")
_LINE_OPENER = re.compile(r"[\"“”'‘’]\s*([A-Z][a-zA-Z'’-]{2,})")


# --- who said it: speaker tags written by the prose call ----------------------------------
#
# docs/declared-not-guessed.md, the first door (2026-09-25). The prose call writes a line of
# dialogue as `<say who=c3 to=you>'You're a long way from home.'</say>`; the tags are
# lifted out here, the moment a reply arrives, before any check or rewrite reads the text,
# and what they said is kept beside the beat as `Said` records. Guessing the speaker after
# the fact from the words round the quote is what `hailed_by` and `introductions` did, and
# it misread; the model knows who is talking while it writes.
#
# Keyed by the words of the line, never by offsets: every groomer after this point may
# rewrite the beat, and a record whose line no longer appears simply stops matching, so a
# rewrite costs a fallback to the old guess rather than a wrong speaker.

_SAY_OPEN = re.compile(r"<\s*say\b([^<>]*)>", re.I)
_SAY_CLOSE = re.compile(r"<\s*/\s*say\s*>", re.I)
_ATTR = re.compile(r"\b(who|to)\s*=\s*(?:\"([^\"<>]*)\"|'([^'<>]*)'|([^\"'\s<>]+))", re.I)


def _key(line: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", str(line or "").lower().replace("’", "'")))


def lift(text: str, refs=None, names=None) -> tuple[str, list[dict]]:
    """(the beat with every speaker tag removed, the lines they attributed).

    Each record is {"who": ref, "to": "you" | ref | "", "line": what was said}. `refs`
    are the scene's refs: a tag naming anything else keeps its words and loses its
    attribution — its record has an empty "who" and the claim in "was", so the miss can
    be counted — and never books anybody. `names` maps a lowercase name or descriptor to its
    ref, for the model that writes `who="the smith"` instead of the ref it was shown.
    Unclosed and stray tags are removed; a tag with no quotation inside keeps its words
    and is wrapped in quote marks, because the model tagged it as speech.
    """
    text = str(text or "")
    if "<" not in text:
        return text, []
    known = set(refs or [])
    by_name = {str(k).lower(): v for k, v in (names or {}).items()}
    said: list[dict] = []
    out: list[str] = []
    at = 0
    for m in _SAY_OPEN.finditer(text):
        if m.start() < at:
            continue
        out.append(text[at:m.start()])
        close = _SAY_CLOSE.search(text, m.end())
        nxt = _SAY_OPEN.search(text, m.end())
        if close is None or (nxt is not None and nxt.start() < close.start()):
            # Unclosed: the words run on as they are, unattributed.
            at = m.end()
            continue
        inner = text[m.end():close.start()]
        attrs = {k.lower(): (a or b or c) for k, a, b, c in _ATTR.findall(m.group(1))}
        claimed = who = attrs.get("who", "").strip()
        if who not in known:
            who = by_name.get(who.lower().replace("_", " "), "") if who else ""
        to = attrs.get("to", "").strip().lower()
        to = "you" if to in ("you", "pc", "player") else (to if to in known else "")
        found = spans(inner)
        if not found and inner.strip():
            inner = f"“{inner.strip()}”"
            found = spans(inner)
        if who or claimed:
            for a, b in found:
                line = inner[a + 1:b - 1] if b - a >= 2 else ""
                if line.strip():
                    rec = {"who": who, "to": to, "line": line.strip()}
                    if not who:
                        # Kept, with what the model claimed, so the miss can be counted;
                        # an empty `who` attributes nothing to anybody.
                        rec["was"] = claimed
                    said.append(rec)
        out.append(inner)
        at = close.end()
    out.append(text[at:])
    clean = _SAY_CLOSE.sub("", "".join(out))
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    return clean, said


def retag(text: str, said) -> str:
    """The beat with its recorded speakers written back round their lines — `lift`
    undone — for the one place the model is shown its own earlier prose.

    Measured on the first live run with tags (2026-09-25, gemma-4-12B, 12 turns): tagging
    was all or nothing per beat, 4 beats tagged and 4 not, and the untagged ones followed
    a tagged beat that the prompt had shown back to the model with its tags lifted out —
    two beats of its own untagged speech in front of it, against the examples' tagged
    ones. Demonstration volume beats instruction volume (CLAUDE.md), and the nearest
    demonstration was ours.
    """
    text = str(text or "")
    if not said:
        return text
    out, at = [], 0
    for a, b in spans(text):
        rec = speaker(said, text[a + 1:b - 1] if b - a >= 2 else "")
        if not rec or not rec.get("who"):
            continue
        to = f" to={rec['to']}" if rec.get("to") else ""
        out.append(text[at:a])
        out.append(f"<say who={rec['who']}{to}>{text[a:b]}</say>")
        at = b
    out.append(text[at:])
    return "".join(out)


def speaker(said, line: str) -> dict | None:
    """The record whose line this is, if the prose tagged it. Equal words first; then one
    containing the other, for a groomer that trimmed a line's tail — but only for lines of
    four words or more, where containment is not an accident."""
    want = _key(line)
    if not want:
        return None
    for rec in said or []:
        if _key(rec.get("line", "")) == want:
            return rec
    for rec in said or []:
        have = _key(rec.get("line", ""))
        if len(want.split()) >= 4 and len(have.split()) >= 4 and (want in have or have in want):
            return rec
    return None


def opens(sentence: str) -> bool:
    """Whether a sentence has speech opening in it — a double quote anywhere, a single
    quote at a word boundary (never the apostrophe inside "it's")."""
    return bool(_OPENING_MARK.search(str(sentence or "")))


def first_opening(sentence: str) -> int | None:
    """Where the first opening quote mark in a sentence stands, or None."""
    m = _OPENING_MARK.search(str(sentence or ""))
    return m.start() if m else None


def line_openers(sentence: str) -> set[str]:
    """The capitalised words that open somebody's line in this sentence: "Enjoy",
    "Ask", "Meet" — the first word of speech, which is not a name."""
    return {m.group(1) for m in _LINE_OPENER.finditer(str(sentence or ""))}


# --- the sounds people make that are not words -------------------------------------------
#
# docs/design-f-ui.md §4.2, playtest item 7.2: "just the dialogue and vocalizations such as
# grunting or laughing". The conversation log wants the grunt beside the line, and a grunt
# is untagged prose — so it is DETECTED here, in code, never asked of the model as a tag.
# Three reasons a `<vocal>` tag was refused before it was tried: speaker tagging was all or
# nothing per beat (4 of 8, measured 2026-09-25) and a second tag inherits that; `lift`
# wraps a tag's unquoted inner text in quote marks, so `<say who=c1>grunts</say>` would
# become a spoken line "grunts"; and a detector would still be needed for untagged beats.
#
# Precision over recall, on purpose. A missed grunt costs one italic row in a log; a grunt
# booked to the wrong person puts words in somebody's mouth, which is the defect the whole
# fix pass is about. So the vocabulary is closed (the MUD-socials tradition: `laugh`,
# `cackle`… as a declared list, not a guess), the speaker has to be found by one of three
# rules that each answer only when there is exactly one person they could mean, and a
# vocal word nobody can be found for is reported as a miss for measuring, never booked.
#
# Measured on the owner's playtest of 2026-09-28 (tests/replays/bobby-2026-09-28, the
# thirteen beats): the four grunts and laughs a reader books to the watchman or the man in
# the jerkin are found, to the right person, and none of the eight near misses is booked —
# "the village hums", "the low moan of the wind", "his voice a low growl", "'…,' he
# grunts" (a dialogue tag: the line itself is logged) and "he gasps for breath"
# (breathing). tests/test_f_vocalisations.py holds it.

_VOCALS = ("laugh", "chuckle", "giggle", "cackle", "snicker", "snigger", "chortle",
           "guffaw", "titter", "grunt", "groan", "moan", "sigh", "huff", "snort", "scoff",
           "sniff", "sob", "whimper", "wail", "gasp", "growl", "snarl", "hiss", "hum",
           "whistle", "cough", "yelp", "shriek", "scream", "tut")
# Short verbs that double their last letter: sobbed, hummed, tutted.
_DOUBLES = frozenset({"sob", "hum", "tut"})


def _third(base: str) -> str:
    return base + ("es" if base.endswith(("s", "sh", "ch", "x", "z")) else "s")


def _past(base: str) -> str:
    if base.endswith("e"):
        return base + "d"
    return base + (base[-1] if base in _DOUBLES else "") + "ed"


# "laughs", "laughed": what somebody else does. The bare "laugh" is only ever the
# player's own "I laugh" — in prose it is the noun ("a laugh", "stifles a laugh"), which
# is the reason a bare form is never read as a verb here.
_VERB_FORMS = {f: b for b in _VOCALS for f in (_third(b), _past(b))}
_BASE_FORMS = {b: b for b in _VOCALS}
_VERB_RE = re.compile(r"\b(" + "|".join(sorted(_VERB_FORMS, key=len, reverse=True))
                      + r")\b", re.I)
_BASE_RE = re.compile(r"\b(" + "|".join(sorted(set(_VERB_FORMS) | set(_BASE_FORMS),
                                               key=len, reverse=True)) + r")\b", re.I)
# The noun after a verb of making a sound: "lets out a low, dry grunt", "gives a short,
# dry laugh", "a short, dry bark of a laugh". At most five words between, so a sentence
# cannot wander from "gives" to a laugh three clauses later.
_NOUNS = "|".join(sorted(_VOCALS, key=len, reverse=True))
_NOUN_RE = re.compile(
    r"\b(?P<trig>lets\s+out|let\s+out|letting\s+out|gives|gave|give)\s+"
    r"(?P<mid>(?:an?\s+)?(?:[a-z'’-]+,?\s+){0,5}?)"
    r"(?P<noun>" + _NOUNS + r")(?:s|es)?\b", re.I)
# "says with a short laugh": the sound beside a line of speech. Only after a verb of
# speaking or of face, and with at most three words between, so "with a whistle round
# his neck" is not a whistle blown.
_WITH_VERBS = frozenset((
    "says said replies replied answers answered adds added asks asked admits admitted "
    "agrees agreed murmurs murmured mutters muttered continues continued nods nodded "
    "shrugs shrugged grins grinned smiles smiled speaks spoke repeats repeated "
    "offers offered concedes conceded").split())
_WITH_RE = re.compile(
    r"\b(?P<verb>[a-z]+)\s+with\s+(?P<mid>(?:an?\s+)(?:[a-z'’-]+,?\s+){0,3}?)"
    r"(?P<noun>" + _NOUNS + r")(?:s|es)?\b", re.I)
_THROAT_RE = re.compile(r"\b(?P<verb>clears|cleared|clear)\s+(?:his|her|their|its|my)\s+throat\b",
                        re.I)
# The player's own emote: "*grunts*", "*laughs softly*".
_EMOTE_RE = re.compile(r"\*\s*(?P<body>[A-Za-z][A-Za-z ,'’-]{0,40}?)\s*\*")

# Refused outright: a sound somebody did not make.
_NEGATION = frozenset((
    "not never no without nor stifles stifled stifling suppresses suppressed swallows "
    "swallowed holds held bites bit fights fought".split()))
# Breathing is not a vocalisation, whatever the verb: "he gasps for breath" (Bobby, beat 13).
_BREATH_RE = re.compile(r"^\s*for\s+(?:breath|air)\b", re.I)
# Words between a subject and its verb that are not the subject: "and then he gives".
_ADVERBS = frozenset((
    "then just only also still again even suddenly finally simply merely almost nearly "
    "soon once instead abruptly quietly softly briefly".split()))
_LEADS = frozenset("and but so yet or then".split())
# Heads that are many people, never one: "the crowd laughs" books nobody.
_COLLECTIVE = frozenset((
    "crowd folk people men women everyone everybody onlookers others all "
    "guards soldiers villagers children".split()))
_FEMALE = frozenset((
    "woman girl lady lass maid maiden mother sister daughter wife widow queen priestess "
    "nun aunt fishwife midwife clanswoman matron crone hag grandmother mistress").split())
_MALE = frozenset((
    "man boy lad father brother son husband king uncle monk clansman fellow grandfather "
    "lord master").split())
_DETS = frozenset("the that this".split())
# Where a vocal clause ends, for the phrase that is kept.
_CLAUSE_END = re.compile(
    r"[,;:.!?\n]|\s(?:and|as|before|while|but|then|that|which|until|so)\s", re.I)
_WORDS = re.compile(r"[A-Za-z][A-Za-z'’-]*")


def _gender(person: dict, head: str) -> str:
    """"f", "m" or "" from what the scene says: the stated pronouns, else a head noun
    that carries it ("the girl"). They/them says nothing here — every person the world
    gave no gender reads they/them (Bobby's save: all nine), and the page calls them he."""
    pro = str(person.get("pronouns") or "").lower()
    if pro.startswith("she"):
        return "f"
    if pro.startswith("he"):
        return "m"
    return "f" if head in _FEMALE else "m" if head in _MALE else ""


def _keys(people) -> list[tuple[str, str, str, bool]]:
    """(ref, key, gender, proper) for every non-PC person: a proper name whole and by its
    first word when no one else shares it, a description by its head noun ("the watchman
    waving traffic through" is found as "the watchman")."""
    from gm.checks._people import _PERSON, head_of

    rows: list[tuple[str, str, str, bool]] = []
    firsts: dict[str, int] = {}
    named = []
    for ref, p in (people or {}).items():
        if (p or {}).get("is_pc"):
            continue
        name = " ".join(str((p or {}).get("name") or "").split())
        if not name:
            continue
        head = head_of(name)
        words = head.split()
        # A lone capitalised trade ("Guard") is a description, not somebody's name.
        proper = bool(words) and not (len(words) == 1 and words[0].lower() in _PERSON)
        if proper:
            named.append((ref, head, p))
            firsts[words[0]] = firsts.get(words[0], 0) + 1
        elif head:
            rows.append((ref, head.lower(), _gender(p, head.lower()), False))
    for ref, head, p in named:
        rows.append((ref, head, _gender(p, ""), True))
        first = head.split()[0]
        if first != head and firsts.get(first) == 1 and len(first) >= 3:
            rows.append((ref, first, _gender(p, ""), True))
    return rows


def _mentioned(stretch: str, keys) -> set[tuple[str, str]]:
    """(ref, gender) of every person `stretch` names: a proper name as written, a head
    noun after "the/that/this" and at most two words ("the old watchman")."""
    found = set()
    for ref, key, gender, proper in keys:
        if proper:
            pat = r"\b" + re.escape(key) + r"\b"
            hit = re.search(pat, stretch)
        else:
            pat = (r"\b(?:the|that|this)\s+(?:[a-z'’-]+\s+){0,2}?" + re.escape(key)
                   + r"(?:'s|’s)?\b")
            hit = re.search(pat, stretch, re.I)
        if hit and not (not proper and key in _COLLECTIVE):
            found.add((ref, gender))
    return found


def _subject(prefix: str) -> list[str]:
    """The words of the clause before a verb, adverbs and leading conjunctions dropped."""
    cut = max(prefix.rfind(c) for c in ",;:—–()\n")
    words = _WORDS.findall(prefix[cut + 1:])
    while words and words[0].lower() in _LEADS:
        words.pop(0)
    while words and (words[-1].lower() in _ADVERBS
                     or (words[-1].lower().endswith("ly") and len(words[-1]) > 4)):
        words.pop()
    return words


def _named(words: list[str], keys) -> list[str]:
    """The refs a subject's words end on, by name or by "the <head>"."""
    hits = []
    tail = " ".join(words)
    for ref, key, _gender_, proper in keys:
        if proper:
            if tail == key or tail.endswith(" " + key):
                hits.append(ref)
        elif words and words[-1].lower() == key and key not in _COLLECTIVE:
            before = [w.lower() for w in words[-4:-1]]
            if any(w in _DETS for w in before):
                hits.append(ref)
    return list(dict.fromkeys(hits))


def _negated(words_before: list[str]) -> bool:
    last = [w.lower() for w in words_before[-3:]]
    return any(w in _NEGATION or w.endswith(("n't", "n’t")) for w in last)


def _phrase(text: str, start: int, end_min: int, cap: int = 10) -> str:
    """From `start` to the clause's end, never shorter than `end_min`, at most `cap`
    words: "lets out a low, dry grunt", "laughs softly at you"."""
    m = _CLAUSE_END.search(text, end_min)
    stop = m.start() if m else len(text)
    words = text[start:stop].split()[:cap]
    return " ".join(words).strip(" ,;:'\"“”‘’")


def _sentences(blank: str) -> list[tuple[int, int]]:
    """(start, end) of each sentence of the blanked beat — quotations are spaces, so a
    full stop inside a line never ends the sentence around it."""
    out, at = [], 0
    for m in re.finditer(r"[.!?]+(?=\s|$)|\n", blank):
        out.append((at, m.end()))
        at = m.end()
    if at < len(blank):
        out.append((at, len(blank)))
    return out


def _speakers_in(text: str, a: int, b: int, said, pc: set[str]) -> set[str]:
    """The tagged speakers of the quotations inside text[a:b], the PC left out."""
    who = set()
    for s, e in spans(text):
        if s >= a and e <= b + 1:
            rec = speaker(said, text[s + 1:e - 1] if e - s >= 2 else "")
            if rec and rec.get("who") and rec["who"] not in pc:
                who.add(rec["who"])
    return who


def vocalisations(text: str, said=(), people=None, *, player: bool = False) -> list[dict]:
    """The grunts, laughs and sighs in `text`, each with who made it — or a miss.

    Each is `{"who": ref, "to": "you" | ref | "", "text": phrase, "src": tier, "at":
    offset}`; `src` is how the speaker was found:

      * ``tag-adjacent`` — "he" beside a quotation the prose call tagged, with one speaker
        in the sentence ("'Two days,' he says with a short laugh");
      * ``named`` — the subject is a person's name, or "the <head noun>" of exactly one
        person ("Drenn grunts", "the watchman laughs");
      * ``pronoun`` — "he"/"she" with exactly one person it can mean, in the same sentence
        before it or, failing any, the nearest earlier sentence of the paragraph that names
        or quotes anybody (up to three back). Gender only excludes: a "he" is never "the
        girl". This tier costs about a third in the literature (PDNC: 98.6 % explicit
        against 68.9 % implicit), so two candidates are a miss, not a guess;
      * ``player`` — with `player=True`, the player's own words: "I laugh", "*grunts*".

    A miss is the same dict with `"who": ""` and `"why"` ("pronoun", "ambiguous", "no
    person"), for the turn log to count — recall is measured before any tag is considered.

    Nothing inside a quotation is ever a vocalisation (`blanked`): a quoted "Hmph." is a
    line. Refused, and not reported: a negated sound ("does not laugh", "without a
    laugh"), a dialogue tag whose verb is the sound ("'…,' he grunts" — the line is logged,
    the grunt is how it was said) and breathing ("gasps for breath").

    `people` is ref -> {"name", "pronouns", "is_pc"} (`play.aftermath.people_of`). With
    `player=False` (GM prose) the PC is never the speaker: the narrator does not decide
    what the player's character did. With `player=True` only the PC is.
    """
    text = str(text or "")
    if not text.strip():
        return []
    blank = blanked(text)
    people = people or {}
    pc_refs = {r for r, p in people.items() if (p or {}).get("is_pc")}
    pc = next(iter(sorted(pc_refs)), "")
    keys = [] if player else _keys(people)
    quotes = spans(text)
    found: list[dict] = []
    taken: list[tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return not any(a < y and x < b for x, y in taken)

    def to_of(phrase: str) -> str:
        m = re.search(r"\bat\s+(you|yourself)\b", phrase, re.I)
        if m:
            return "you"
        m = re.search(r"\bat\s+(.+)$", phrase)
        if m and keys:
            hit = {ref for ref, _g in _mentioned(m.group(1), keys)}
            if len(hit) == 1:
                return hit.pop()
        return ""

    # Every candidate: (verb or trigger start, where the phrase must reach, form).
    cands: list[tuple[int, int, int, str]] = []
    for m in (_BASE_RE if player else _VERB_RE).finditer(blank):
        cands.append((m.start(), m.end(), m.end(), "verb"))
    for m in _NOUN_RE.finditer(blank):
        cands.append((m.start(), m.end(), m.end(), "noun"))
    for m in _WITH_RE.finditer(blank):
        if m.group("verb").lower() in _WITH_VERBS:
            cands.append((m.start(), m.end(), m.end(), "with"))
    for m in _THROAT_RE.finditer(blank):
        cands.append((m.start(), m.end(), m.end(), "verb"))
    # Longest first at a place, so "lets out a laugh" is read before its bare "laugh".
    cands.sort(key=lambda c: (c[0], -(c[1] - c[0])))
    sentences = _sentences(blank)

    for start, end, reach, form in cands:
        if not free(start, end):
            continue
        s_at = next((i for i, (a, b) in enumerate(sentences) if a <= start < b), None)
        if s_at is None:
            continue
        s_start, s_end = sentences[s_at]
        prefix = blank[s_start:start]
        # For "says with a laugh" the match starts at the verb of speaking, so the words
        # before it are the speaker, as they are for "Drenn grunts".
        words = _subject(prefix)
        if _negated(_WORDS.findall(prefix)[-3:]):
            continue
        if form == "verb" and _BREATH_RE.match(blank[end:]):
            continue
        phrase = _phrase(blank, start, reach)
        if not phrase:
            continue
        head = [w.lower() for w in words]

        if player:
            if head and head[-1] == "i" and pc:
                taken.append((start, end))
                found.append({"who": pc, "to": to_of(phrase), "text": phrase,
                              "src": "player", "at": start})
            continue
        if form == "verb" and _VERB_FORMS.get(blank[start:end].lower()) is None \
                and not _THROAT_RE.match(blank, start):
            continue
        # A sound used as the verb of a line of speech is how the line was said.
        if form == "verb":
            before = next((e for s, e in reversed(quotes) if e <= start), None)
            subj_at = s_start + prefix.rfind(words[0]) if words else start
            if before is not None and not re.sub(r"[\s,]", "", text[before:max(before, subj_at)]):
                continue
            after = next((s for s, e in quotes if s >= end), None)
            if after is not None and re.fullmatch(r"\s*(?:\w+ly\s*)?[,:]?\s*",
                                                  text[end:after]):
                continue

        who, src, why = "", "", ""
        if head and head[-1] in ("he", "she"):
            want = "f" if head[-1] == "she" else "m"
            ok = lambda g: g in ("", want)  # noqa: E731 — gender only ever excludes
            tagged = _speakers_in(text, s_start, s_end, said, pc_refs)
            if len(tagged) == 1:
                who, src = tagged.pop(), "tag-adjacent"
            else:
                here = {r for r, g in _mentioned(blank[s_start:start], keys) if ok(g)}
                if len(here) == 1:
                    who, src = here.pop(), "pronoun"
                elif here:
                    why = "ambiguous"
                else:
                    # Back through the paragraph, at most three sentences, to the nearest
                    # one that names or quotes anybody; a paragraph break ends the search.
                    for back in range(s_at - 1, s_at - 4, -1):
                        if back < 0:
                            break
                        a, b = sentences[back]
                        if not blank[a:b].strip():
                            break
                        near = {r for r, g in _mentioned(blank[a:b], keys) if ok(g)}
                        near |= _speakers_in(text, a, b, said, pc_refs)
                        if near:
                            if len(near) == 1:
                                who, src = near.pop(), "pronoun"
                            else:
                                why = "ambiguous"
                            break
                    if not who and not why:
                        why = "pronoun"
        elif head:
            hits = _named(words, keys)
            if len(hits) == 1:
                who, src = hits[0], "named"
            else:
                why = "ambiguous" if hits else "no person"
        else:
            why = "no person"
        taken.append((start, end))
        if who in pc_refs:
            continue
        found.append({"who": who, "to": to_of(phrase) if who else "", "text": phrase,
                      "src": src, "at": start, **({"why": why} if not who else {})})

    # The player's emotes, which name no subject at all.
    if player and pc:
        for m in _EMOTE_RE.finditer(text):
            body = m.group("body").strip()
            first = body.split()[0].lower() if body.split() else ""
            if first in _VERB_FORMS or first in _BASE_FORMS or body.lower().startswith(
                    ("lets out", "let out", "clears", "clear")):
                if free(m.start(), m.end()):
                    taken.append((m.start(), m.end()))
                    found.append({"who": pc, "to": to_of(body), "text": body,
                                  "src": "player", "at": m.start()})
    found.sort(key=lambda f: f["at"])
    return found
