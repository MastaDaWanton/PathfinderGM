"""Whether the page shows what the player declared: read by a model, held to the page in code.

The owner, 2026-10-05: *"narrator does not describe my actions"*. The line was "I flirt with
Vroka", at the gate; the beat opened on her — "Vroka Farrow's eyes travel from the man with
the pack back to you, and a small, amused smile plays on her lips" — and the flirt itself,
the player's one act that turn, was never on the page. Not a word, not a gesture.

**Why the declared-deed check (`narration.owed_deeds` / `shows_deed`, 2026-10-01) missed
it.** The reader read the line `other: flirt with Vroka`, and `owed_deeds` owes an `other`
only on a move turn — on a still turn it is the reading's residue, whose words a beat most
often writes in its own, and a cue-word search could not tell. Talk was owed only without
words and without a speech verb ("ask", "tell", "say"): the reply was assumed to carry it.
So a still social turn owed nothing. And where it did fire, the next turn ("…continuing to
flirt with her"), the cue word "flirt" refused both repairs the model wrote ("a low,
teasing remark about her daring nature") — the flirt in other words, which is what a flirt
on a page looks like. A word search reads English, and reads it badly in both directions:
"The words of your challenge hang in the damp air" carries "challenge" and is no
challenge shown; it is the beat picking up after it.

**Measured before building** (docs/narrator-guards.md, "The deed on the page"): hand
labels over the still player turns with a declared act the engine does not narrate for
itself, in the owner's saves (13 beats, 16 deeds: 8 not shown, in 7 of the 13 beats), the
2026-09-25/26 recordings and the beat-verify bench's excerpts — 80 deeds, 54 not shown
(tests/deeds/gold.py holds the 64 that may be committed). The recordings' ask turns opened
on the person asked in 25 of 27 ("He does not answer straight away" was the shape of three
of the worked examples — `prompts.EXAMPLES` taught it).

**The shape** is the structured turn's (docs/structured-turn.md): a model reads, code
validates. One schema-constrained call asks, for each declared deed by number, where on
the page the player's character does it — a sentence number from the page's own list —
and how: `shown` (the act, the gesture, the words said or reported, as it happens),
`after` (only what followed it: an answer, a reaction, "your words hang in the air"),
`absent`. Every slot is an enum; code then holds a `shown` to the page: the sentence it
names must exist and must be about the player (a "you" in its narration, or the player's
own quoted words in it). A `shown` that fails is not believed and not alarmed on either —
the reading abstains (`unsure`); a false alarm costs a sentence the beat did not need.

Prior art for what "shown" means: The Angry GM's declare–determine–describe — the
description is "repeating back the action you already repeated as if it happened as
intended"; play-by-post etiquette, "you write the attempt, they write the result"
(CharHaven, on godmodding); AI Dungeon's Do mode, which writes "> You …" onto the page
before the model continues; Inform's Report rules, which say what the player's action did
after it is carried out. All four put the player's act on the page first, in the player's
own terms, and the world's answer after it.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

# On in the app; off in the test suite (tests/conftest.py), like every other model read: a
# turn test that scripts the model's replies in order would have one spent on this.
ENABLED = True

SHOWN, AFTER, ABSENT = "shown", "after", "absent"
VERDICTS = (SHOWN, AFTER, ABSENT)
# A deed the reader called shown whose sentence fails the page check: not believed, not
# alarmed on.
UNSURE = "unsure"

# The acts a still beat owes the page as the player's own doing. Not the ones the engine
# writes for itself: a move is its travel tell's (`_op_travel`), looking and searching are
# written by what they find, waiting and resting by the time passing, buying by the
# screen, a spell by the cast. Not the checks either — climbing, sneaking, breaking in —
# whose attempt is the roll's and whose outcome the dice own; asking for the attempt here
# invites the prose to settle it.
OWED_ACTS = frozenset({"talk", "insult", "give", "take", "drop", "steal", "use",
                       "consume", "sell", "other", "attack"})
MOVE_ACTS = frozenset({"go", "journey", "leave", "follow", "call_on", "seek"})


@dataclass
class DeedVerdict:
    span: str
    verdict: str            # shown | after | absent | unsure
    sentence: str = ""      # the page sentence the reader named, as written
    why: str = ""           # why a `shown` was not believed

    @property
    def missing(self) -> bool:
        return self.verdict in (AFTER, ABSENT)

    def as_dict(self) -> dict:
        return {"span": self.span, "verdict": self.verdict,
                **({"sentence": self.sentence[:120]} if self.sentence else {}),
                **({"why": self.why} if self.why else {})}


@dataclass
class DeedReading:
    verdicts: list[DeedVerdict] = field(default_factory=list)
    seconds: float = 0.0
    error: str = ""
    raw: str = ""
    model: str = ""

    @property
    def missing(self) -> list[DeedVerdict]:
        return [v for v in self.verdicts if v.missing]

    def as_log(self) -> dict:
        return {"kind": "deeds-read", "verdicts": [v.as_dict() for v in self.verdicts],
                "seconds": self.seconds, "model": self.model,
                **({"error": self.error} if self.error else {})}


# --- which deeds -------------------------------------------------------------------------

def deeds_of(reading: dict | None, sentence: str, outcomes=(), *,
             fighting: bool = False) -> list[dict]:
    """The deeds this turn's reading declares that the page owes as the player's doing:
    each the reading's action with its `span` (the player's own words for it) and
    `before_move` / `after_move` as `narration.owed_deeds` sets them.

    Wider than `owed_deeds` on purpose — that list was bounded by what a cue-word search
    could judge; this one is judged by a reader. Still left alone: a question asked of the
    game, an act only intended or asked about (interpret.COMMITS), an act the engine
    refused outright (the beat owes the refusal), an attack in a fight or one the dice
    rolled (the blow's own checks own that page), and a span with no words of the
    player's."""
    from . import interpret, narration

    if not isinstance(reading, dict) or reading.get("error") or reading.get("question"):
        return []
    actions = narration.declared_spans(reading, sentence)
    moved, _ = narration._op_status(outcomes, narration._MOVE_OPS)
    move_at = next((i for i, a in enumerate(actions) if a.get("act") in MOVE_ACTS), None)
    rolled_attack, _ = narration._op_status(outcomes, ("attack",))
    out = []
    for i, a in enumerate(actions):
        act = a.get("act")
        if act not in OWED_ACTS or not interpret.acting(a):
            continue
        if act == "attack" and (fighting or rolled_attack):
            continue
        ops = narration._ACT_OPS.get(act)
        if ops:
            done, refused = narration._op_status(outcomes, ops)
            if refused and not done:
                continue
        span = str(a.get("span") or "").strip()
        if not span or not re.search(r"[A-Za-z]", span):
            continue
        out.append({**a, "span": span, "index": i,
                    "cues": narration.deed_cues(a),
                    "before_move": bool(moved and move_at is not None and i < move_at),
                    "after_move": bool(moved and move_at is not None and i > move_at)})
    return out


# --- the call ----------------------------------------------------------------------------

_SYSTEM = (
    "You check one passage of a tabletop game, narrated to the player as \"you\". The "
    "player declared what their character does this turn, as numbered DEEDS. For each "
    "deed, find where the passage shows the player's character doing it, and say how:\n"
    "  shown  - a sentence has the player doing this very thing as it happens: the act, "
    "the gesture, or the words, said out or reported (\"you ask him where the road "
    "goes\", \"you lean in and murmur something about her nerve\"). Other words for "
    "the same deed count.\n"
    "  after  - the passage only shows what came after it: someone answering, reacting "
    "or listening, the words hanging in the air, a result. The player is never shown "
    "doing it.\n"
    "  absent - nothing about it at all.\n"
    "Give the sentence number where it is shown, or 0 when it is not. Judge each deed "
    "on its own: the player doing one deed is not the player doing another, and "
    "someone answering a question is not the player asking it.")

# Two demonstrations, written for this call and taken from no bench or save: one beat that
# opens on the other person and one that shows the player first. Balanced on purpose — a
# reader shown only misses learns to find misses.
_DEMO1_DEEDS = ["thank the ferryman", "toss him a coin"]
_DEMO1_PAGE = [
    "The ferryman pockets the coin without looking at it.",
    "'Thanks are cheap on this river,' he says, already pushing off.",
    "The boat drifts out into the brown water and you are alone on the jetty.",
    "What do you do?",
]
_DEMO1_ANSWER = {"d1": {"sentence": "2", "how": AFTER},
                 "d2": {"sentence": "0", "how": AFTER}}
_DEMO2_DEEDS = ["ask the cook what is in the pot", "lean on the counter"]
_DEMO2_PAGE = [
    "You lean your elbows on the scarred counter and ask what she has bubbling in the "
    "pot.",
    "The cook wipes her hands on her apron and lifts the lid for you to see.",
    "'Eel and barley,' she says. 'Same as yesterday.'",
    "What do you do?",
]
_DEMO2_ANSWER = {"d1": {"sentence": "1", "how": SHOWN},
                 "d2": {"sentence": "1", "how": SHOWN}}


def _ask(deeds: list[str], sentences: list[str], player_line: str) -> str:
    page = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences, 1))
    listed = "\n".join(f"d{i}. {d}" for i, d in enumerate(deeds, 1))
    return (f"THE PLAYER WROTE: {player_line}\n\nDEEDS:\n{listed}\n\n"
            f"PASSAGE, BY SENTENCE:\n{page}")


def schema(n_deeds: int, n_sentences: int) -> dict:
    """One required object per deed, `sentence` then `how`, both enums. Required
    properties and enums are what Ollama enforces (memory `ollama-schema-enforcement`,
    6 of 6); an array with a length would not be. The sentence comes first so the verdict
    is written with the evidence already chosen."""
    nums = [str(i) for i in range(n_sentences + 1)]
    one = {"type": "object",
           "properties": {"sentence": {"type": "string", "enum": nums},
                          "how": {"type": "string", "enum": list(VERDICTS)}},
           "required": ["sentence", "how"]}
    keys = [f"d{i}" for i in range(1, n_deeds + 1)]
    return {"type": "object", "properties": {k: one for k in keys}, "required": keys}


def messages(deeds: list[str], sentences: list[str], player_line: str) -> list[dict]:
    return [{"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _ask(_DEMO1_DEEDS, _DEMO1_PAGE,
                                             "I thank the ferryman and toss him a coin.")},
            {"role": "assistant", "content": json.dumps(_DEMO1_ANSWER)},
            {"role": "user", "content": _ask(_DEMO2_DEEDS, _DEMO2_PAGE,
                                             "I lean on the counter and ask the cook "
                                             "what's in the pot.")},
            {"role": "assistant", "content": json.dumps(_DEMO2_ANSWER)},
            {"role": "user", "content": _ask(deeds, sentences, player_line)}]


_YOU = re.compile(r"\b(?:you|your|yours|yourself)\b", re.I)


def _words(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", str(text or "").lower().replace("’", "'")))


def _quoted(player_line: str) -> list[str]:
    """The player's quoted words, as bare words: a page that says them back ends them
    with a comma where the player wrote a full stop."""
    from . import speech

    text = str(player_line or "")
    return [w for w in (_words(text[a + 1:b - 1]) for a, b in speech.spans(text)
                        if b - a > 4) if w]


def about_the_player(written: str, narration: str, player_line: str = "",
                     pc_name: str = "") -> bool:
    """The page check on a `shown`: the sentence's narration (speech blanked) speaks of
    the player — "you", or the character's name — or the sentence carries the player's
    own quoted words."""
    if _YOU.search(narration or ""):
        return True
    first = str(pc_name or "").split()[:1]
    if first and len(first[0]) > 2 and re.search(rf"\b{re.escape(first[0])}\b", narration or ""):
        return True
    low = _words(written)
    return any(q in low for q in _quoted(player_line))


# --- the player still under at the end of the turn -----------------------------------------
#
# The survival lane's live run, 2026-10-05: the engine's tell said Sammy "cannot stay awake
# any longer and falls asleep where they stand", and the prose already had them waking at
# twilight — "that was a long nap". The page ran past the state the engine left the player
# in. One closed question, the same shape as the deeds: which sentence, if any, has the
# player awake or acting AFTER they go under. Code holds the answer to the page (a sentence
# about the player) and the check (gm/checks/sleep_kept.py) cuts from it.

_UNDER_SYSTEM = (
    "You check one passage of a tabletop game, narrated to the player as \"you\". The "
    "rules say the player's character is {state} at the END of this passage, and stays "
    "that way. Find the first sentence where, after going under, the player is awake "
    "again or doing things — waking, getting up, speaking, walking, looking around. "
    "Sentences BEFORE they go under do not count, and neither does dreaming or lying "
    "still. Answer its number, or 0 when there is none.")


def read_under(text: str, state: str, *, chat=None, model: str = "", host: str = "",
               provider: str = "ollama", api_key: str = "",
               pc_name: str = "") -> tuple[str, str]:
    """(the first page sentence that has the player up again after going under, an error).
    "" when there is none, when the reader names a sentence not about the player, or when
    the read fails (the error says so)."""
    from .checks._page import page_sentences

    pairs = page_sentences(text)
    if not pairs:
        return "", ""
    if chat is None:
        from . import client

        chat = client.chat
    written = [w for w, _n in pairs]
    page = "\n".join(f"{i}. {s}" for i, s in enumerate(written, 1))
    schema = {"type": "object",
              "properties": {"sentence": {"type": "string",
                                          "enum": [str(i) for i in range(len(written) + 1)]}},
              "required": ["sentence"]}
    try:
        reply = chat([{"role": "system", "content": _UNDER_SYSTEM.format(state=state)},
                      {"role": "user", "content": f"PASSAGE, BY SENTENCE:\n{page}"}],
                     model, host, as_json=True, think=False, temperature=0.0,
                     num_predict=24, provider=provider, api_key=api_key, schema=schema)
        at = int(str((reply.json() or {}).get("sentence") or "0"))
    except Exception as exc:  # noqa: BLE001 — a failed read must never lose the turn
        return "", f"{type(exc).__name__}: {str(exc)[:120]}"
    if not 1 <= at <= len(written):
        return "", ""
    if not about_the_player(written[at - 1], pairs[at - 1][1], "", pc_name):
        return "", ""
    return written[at - 1], ""


def read(text: str, deeds: list[str], player_line: str, *, chat=None, model: str = "",
         host: str = "", provider: str = "ollama", api_key: str = "",
         pc_name: str = "") -> DeedReading:
    """One call: which of `deeds` (the player's own words for each) the page shows, and
    where. Never raises — a failed call is a reading with `error` set and no verdicts."""
    from .checks._page import page_sentences

    result = DeedReading(model=model)
    deeds = [" ".join(str(d).split()) for d in deeds or () if str(d).strip()]
    pairs = page_sentences(text)
    if not deeds or not pairs:
        return result
    if chat is None:
        from . import client

        chat = client.chat
    written = [w for w, _n in pairs]
    started = time.monotonic()
    try:
        reply = chat(messages(deeds, written, player_line), model, host, as_json=True,
                     think=False, temperature=0.0, num_predict=40 + 24 * len(deeds),
                     provider=provider, api_key=api_key,
                     schema=schema(len(deeds), len(written)))
        result.raw = reply.text
        answer = reply.json() or {}
        for i, span in enumerate(deeds, 1):
            got = answer.get(f"d{i}") if isinstance(answer, dict) else None
            if not isinstance(got, dict) or got.get("how") not in VERDICTS:
                result.verdicts.append(DeedVerdict(span, UNSURE, why="no answer"))
                continue
            how = got["how"]
            try:
                at = int(str(got.get("sentence") or "0"))
            except ValueError:
                at = 0
            sentence = written[at - 1] if 1 <= at <= len(written) else ""
            if how == SHOWN:
                if not sentence:
                    result.verdicts.append(DeedVerdict(span, UNSURE,
                                                       why="shown, with no sentence"))
                    continue
                if not about_the_player(sentence, pairs[at - 1][1], player_line, pc_name):
                    result.verdicts.append(DeedVerdict(
                        span, UNSURE, sentence, why="shown in a sentence not about you"))
                    continue
            result.verdicts.append(DeedVerdict(span, how, sentence))
    except Exception as exc:  # noqa: BLE001 — a failed read must never lose the turn
        result.error = f"{type(exc).__name__}: {str(exc)[:160]}"
        result.verdicts = []
    result.seconds = round(time.monotonic() - started, 2)
    return result
