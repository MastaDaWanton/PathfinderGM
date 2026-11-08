"""The GM at the table: the person running the game, as distinct from the world.

The owner, 2026-11-05, on a ruling they had written for the GM's Rulings page: what made
it feel "like you are actually playing with someone" was the GM's own voice coming through
their actions — "[I knock my knuckles against the table, pointing right at you.] Bold
move." The narrator speaks for the world. Until this file nobody spoke for the person
behind the screen, so every ruling read as a machine's verdict.

Two doors use it:

**Table talk after a beat** (`after_the_beat`, called from `views._finish`). One or two
lines, out of character, in their own style on the page. They are never added to
`c.history`: they are commentary on the game, not facts in it, and an aside in the
conversation the narrator reads becomes fiction on the next turn (the `/gm` door's own
reason, play/gm_answers.py).

**`/gm` answers in the same voice** (`voiced_record`, and the persona block handed to
`prompts.out_of_character_messages`).

What keeps it honest is the shape every fix that held on this project has had: detect in
code, never instruct and hope (CLAUDE.md).

* **It sees only what the player saw.** Its input is the moment built here from the turn's
  own outcomes (the PC's, never an NPC's), each tell through `views.plain_tell`, plus the
  beat already on the page and the player's own line. No brief, no cards, no hidden roll,
  no withheld fact: a GM who grins before you open the door has told you about the trap.
  A layer that cannot see a secret cannot leak it.
* **No model authors a number** (the third law). A table line holding a digit is dropped.
  A voiced `/gm` record must carry every number the record had and no other.
* **No invented names.** A capitalised word mid-sentence that the moment never used is
  dropped as a line, the "ground every name" rule.
* **No copied examples and no tic.** A run of six words from any voice's examples drops
  the line (the narrator's own echo rule). A bracketed action too like one of the last
  few is cut and the spoken part kept: Friends & Fables' players keep a list of its GM's
  favourite things (windmills, hooded figures), and the worst tic this project ever
  measured was its own template (docs/narrator-guards.md).

When to talk is the table's house rule `table_talk`: "off", "big" (the moments a table
reacts to, `BIG`) or "always". Which GM talks is `dm_voice`, one of the personalities in
content/style/dm-voices.json. A dropped line is nothing on the page; the reason goes to the
scene's `table:log` (`_log`), so a bench can count what the checks threw away.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from django.conf import settings

from rules import houserules

# The moments a real table reacts to out loud. Closed: a moment not named here is not
# "big" and only `always` hears it.
BIG = frozenset({"refused", "natural", "critical", "foe_down", "you_down",
                 "fight_starts", "fight_ends", "bend"})

# A line longer than this is a speech, not table talk.
MAX_WORDS = 45
# How many recent table lines a new action is compared against for a tic.
RECENT = 4
# A run this long shared with a voice's own example is a copy (gm/narration.py's echo rule
# measures six-word runs too).
COPY_RUN = 6

_VOICES: dict | None = None


def voices_path() -> Path:
    """The shipped personalities. Through `settings.BASE_DIR`, the bundle root when frozen,
    never `__file__` (CLAUDE.md: `__file__` points inside the PyInstaller bundle)."""
    return Path(settings.BASE_DIR) / "content" / "style" / "dm-voices.json"


def voices() -> dict[str, dict]:
    """Every voice by id, read once."""
    global _VOICES
    if _VOICES is None:
        data = json.loads(voices_path().read_text(encoding="utf-8"))
        _VOICES = {v["id"]: v for v in data.get("voices", [])}
    return _VOICES


def voice(voice_id: str | None = None) -> dict:
    """The table's chosen GM, or the named one; the first in the file if neither exists."""
    found = voices()
    want = voice_id or houserules.dm_voice()
    return found.get(want) or next(iter(found.values()))


def voice_cards() -> list[dict]:
    """What Settings shows for each voice, in the house rule's own order."""
    found = voices()
    return [{"id": v, "name": found[v]["name"], "blurb": found[v]["blurb"]}
            for v in houserules.DM_VOICES if v in found]


# --- the moment ------------------------------------------------------------------------

def _pc_ref(scene) -> str:
    return next((r for r, a in (getattr(scene, "people", {}) or {}).items()
                 if getattr(a, "is_pc", False)), "")


def moments(c, resolution) -> tuple[list[str], list[str]]:
    """(kinds, facts) for the player's part of this turn: what kind of moment it was, and
    each thing the table saw, in words the player has already been shown.

    Only the PC's outcomes. NPC turns are not in `resolution`, and a creature's hidden
    roll is the clearest secret there is. A tell goes through `plain_tell`, which strips
    the arithmetic the engine writes for the narrator ("5 against AC 12"). A check's DC
    is never said; its circumstance reason is, because the ruling's WHY is the one thing
    the player is meant to hear from the GM.
    """
    from .views import plain_tell

    scene = c.scene
    pc_ref = _pc_ref(scene)
    kinds: list[str] = []
    facts: list[str] = []
    for o in getattr(resolution, "outcomes", None) or []:
        actor = str(getattr(o, "actor", "") or "")
        if actor and pc_ref and actor != pc_ref:
            continue
        tell = plain_tell(str(getattr(o, "tell", "") or ""), scene)
        if getattr(o, "status", "") == "refused":
            said = str(getattr(o, "for_a_person", "") or "") or tell
            if said:
                kinds.append("refused")
                facts.append("Refused: " + said)
            continue
        if not tell:
            # A silent step (a scheme's quiet move, rules/schemes.py) is nobody's to hear.
            continue
        facts.append("What happened: " + tell)
        dc = getattr(o, "dc", None)
        if isinstance(dc, dict) and dc.get("circumstance") and dc.get("circumstance_why"):
            word = "bonus" if int(dc["circumstance"]) > 0 else "penalty"
            kinds.append("bend")
            facts.append(f"You gave a {word} for how it was done: {dc['circumstance_why']}")
        for r in getattr(o, "rolls", None) or []:
            if getattr(r, "visibility", "") != "player":
                continue
            face = getattr(r, "natural", None)
            if face in (1, 20):
                kinds.append("natural")
                label = str(getattr(r, "label", "") or "roll").strip()
                facts.append(f"The die showed a natural {'twenty' if face == 20 else 'one'}"
                             f" on the {label}.")
        if any(b.get("critical") for b in (getattr(o, "blows", None) or [])):
            kinds.append("critical")
        for e in getattr(o, "effects", None) or []:
            kind = e.get("kind")
            if kind == "battle_joined":
                kinds.append("fight_starts")
            elif kind == "encounter" and e.get("ended"):
                kinds.append("fight_ends")
            elif (kind == "condition" and e.get("condition") in ("dead", "dying", "unconscious")
                  and e.get("ref") and e.get("ref") != pc_ref):
                kinds.append("foe_down")
    # The PC going down is said once, on the turn it happens, not on every turn after.
    pc = scene.pc() if hasattr(scene, "pc") else None
    said_mem = getattr(scene, "said", None)
    down = bool(pc is not None and pc.is_down)
    if isinstance(said_mem, dict):
        if down and not said_mem.get("table:down"):
            kinds.append("you_down")
            facts.append(f"{pc.name} is down.")
        said_mem["table:down"] = down
    return list(dict.fromkeys(kinds)), facts


def wanted(kinds: list[str], facts: list[str], mode: str | None = None) -> bool:
    """Whether the table's house rule asks for a line on this moment."""
    mode = mode or houserules.table_talk()
    if mode == "off":
        return False
    # "Always" means every turn, a turn with nothing the engine decided included. Measured
    # 2026-11-07 on the owner's game: "I wiggle my butt and spread my legs wide…" was
    # pure narration, no roll and no outcome, so no facts, and the GM said nothing on
    # "always" without even a line in the log. The quiet job reacts to the player's own
    # words and the beat, which every turn has.
    return mode == "always" or bool(facts and BIG & set(kinds))


# --- the prompt ------------------------------------------------------------------------

TABLE_SYSTEM = """You are {name}: the person running this Pathfinder game, talking to the \
player across the table, out of character. {manner} {never}

The story has already been told; you are not the narrator. Say one or two short sentences \
to the player about what just happened at the table: react to what they did, and if there \
was a ruling, say its reason in plain words.

- Under 40 words.
- You may begin with one short action of your own in square brackets, like [I lean back.] \
At most one, and leave it out more often than not.
- React only to what the MOMENT says. Never mention, hint at or tease anything else: no \
knowing looks, no warnings about what is coming. You know nothing beyond the moment.
- No numbers of any kind.
- Do not describe the world, do not say what anyone in it does next, and never speak or \
act for the player's character.
- Talk to the player as "you". Plain words, no quotation marks around them."""


# What a GM's line is FOR, by the moment it answers. Measured on the owner's first game with
# the voice (2026-11-05, six lines): every one was praise — "Pure audacity! I love the
# nerve." — including the two said over REFUSALS, where a GM's one job is to say why it did
# not happen. The prompt said "react to what they did" and the examples mostly praised, so
# it praised (CLAUDE.md: the shape of a prompt becomes the shape of the output). Each call is
# now handed the job of its moment, and the examples are labelled with theirs, so the
# demonstration and the request have the same shape.
JOBS = {
    "refused": "Something the player tried did not happen. Tell them plainly why, using "
               "the reason in the MOMENT, and point at another way if there is an obvious "
               "one. Do not praise the attempt.",
    "you_down": "The player's character is down. Make the danger felt. No jokes.",
    "bend": "You gave a bonus or a penalty for how it was done. Say why, in a few words.",
    "fight_starts": "A fight has started. Make the stakes felt in a few words.",
    "critical": "A big moment. React to it, briefly.",
    "natural": "The die did something special. React to it, briefly.",
    "foe_down": "Someone they fought is down. React to it, briefly.",
    "fight_ends": "The fight is over. A short reaction.",
    # Only "always" asks on a quiet turn, and the owner's first test of it (2026-11-07,
    # the dance with the wagon master) got the dash: the GM "chose silence" on the one
    # setting that promises a line every turn. So a quiet turn is a short line, never none.
    "quiet": "Nothing big happened. Say one short thing a GM would say across the table "
             "now: a reaction to what they did, or a question back to them about what "
             "they do next. Never repeat what the story already said.",
}


def _mend_ask(why: str) -> str:
    """The one narrow request that can mend a dropped line, or "" (CLAUDE.md: detect, then
    repair only what was found). Measured 2026-11-07 on the owner's first packaged game:
    the welcome said "English" (a language, not a person), was dropped whole, and a new
    campaign opened with no GM at all. One more ask, naming the fault; still faulty, it
    is dropped."""
    if why.startswith("a name the moment never used: "):
        word = why.split(": ", 1)[1]
        return (f'Say it again without the word "{word}", and name nobody and nothing '
                f"that is not given above.")
    if why.startswith("praise word again: "):
        # The owner's next turn after the mend landed (2026-11-07): "nice" two lines after
        # "Nice try", dropped whole, and the GM skipped a turn on "always".
        word = why.split(": ", 1)[1]
        return (f'Say it again without the word "{word}" or any other praise. React to '
                f"what they did, or ask what they do next.")
    if why == "a number":
        return "Say it again with no numbers in it at all."
    if why == "too long":
        return "Say it again, shorter."
    return ""
# Which job a turn with several moments gets: the one a GM would speak to first.
JOB_ORDER = ("refused", "you_down", "bend", "fight_starts", "critical", "natural",
             "foe_down", "fight_ends")
# The answer that means "nothing to say", which the quiet example demonstrates.
SILENCE = "-"


def job_for(kinds: list[str]) -> str:
    return next((k for k in JOB_ORDER if k in kinds), "quiet")


def table_messages(v: dict, facts: list[str], player_line: str, beat: str,
                   job: str = "quiet") -> list[dict]:
    """The voice's own examples as earlier turns, then this moment in the same shape."""
    msgs = [{"role": "system", "content": TABLE_SYSTEM.format(
        name=v["name"] + " GM", manner=v["manner"], never=v["never"])}]
    for ex in v.get("examples", []):
        kind = ex.get("kind", "quiet")
        msgs.append({"role": "user", "content": f"YOUR JOB: {JOBS.get(kind, JOBS['quiet'])}"
                                                f"\nMOMENT: {ex['moment']}"})
        msgs.append({"role": "assistant", "content": ex["said"]})
    ask = f"YOUR JOB: {JOBS.get(job, JOBS['quiet'])}\nMOMENT: " + (
        " ".join(facts) or "No roll and no ruling: they did what they wrote, and the story "
        "told it.")
    if player_line:
        ask += f"\n\nThe player wrote: {player_line}"
    if beat:
        ask += f"\n\nThe story they have just read: {beat}"
    msgs.append({"role": "user", "content": ask})
    return msgs


def ooc_voice_block(v: dict | None = None, gestures: bool | None = None) -> str:
    """The persona for a `/gm` answer: who is answering and how they sound, with the
    voice's own out-of-character examples. Appended to the OOC system prompt; the rules
    of that prompt (answer from the notes, say when they do not cover it) still stand."""
    v = v or voice()
    if gestures is None:
        gestures = houserules.table_talk() != "off"
    lines = [f"WHO YOU ARE: the {v['name']} GM. {v['manner']} {v['never']}"]
    if gestures:
        lines.append("You may open with one short action of your own in square brackets, "
                     "like [I glance at your sheet.] Leave it out more often than not.")
    else:
        lines.append("Do not describe your own actions; just answer.")
    lines.append("How you answer, for example:")
    for ex in v.get("ooc_examples", []):
        said = ex["said"] if gestures else strip_gestures(ex["said"])
        lines.append(f"Player asks: {ex['asked']}\nYou: {said}")
    return "\n\n".join(lines)


# --- the checks ------------------------------------------------------------------------

_GESTURE = re.compile(r"\[([^\]\n]{1,200})\]")
_CAPWORD = re.compile(r"\b[A-Z][a-z’'\-]+\b")
_WORD = re.compile(r"[a-z’']+")
# Words a GM says mid-sentence that are capitalised by habit, not because they name anybody.
_ALWAYS = {"I", "GM", "Okay", "OK", "Oh", "Well", "No", "Yes", "Natural", "Pathfinder"}
_STOP = {"the", "a", "an", "and", "my", "your", "you", "to", "of", "at", "on", "in", "with",
         "it", "is", "i", "me", "back", "up", "down", "over", "out", "this", "that"}


def strip_gestures(text: str) -> str:
    return " ".join(_GESTURE.sub("", text or "").split())


def _sentence_start(text: str, i: int) -> bool:
    before = text[:i].rstrip()
    return not before or before[-1] in ".!?[]\"“”:—-("


def _shingles(text: str, n: int) -> set[tuple[str, ...]]:
    words = _WORD.findall((text or "").lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if len(w) > 3 and w not in _STOP}


def _example_runs() -> set[tuple[str, ...]]:
    runs: set[tuple[str, ...]] = set()
    for v in voices().values():
        for ex in v.get("examples", []) + v.get("ooc_examples", []):
            runs |= _shingles(ex["said"], COPY_RUN)
    return runs


def _example_words() -> list[tuple[str, ...]]:
    """Every example's spoken words, for the copy check's whole-line half."""
    return [tuple(_WORD.findall(strip_gestures(ex["said"]).lower()))
            for v in voices().values()
            for ex in v.get("examples", []) + v.get("ooc_examples", [])]


def tidy(text: str, sentences: int = 2) -> str:
    """The model's line as a line: one paragraph, no speaker label, no wrapping quotes, the
    first bracketed action kept and any later one dropped, at most `sentences` sentences."""
    text = " ".join(str(text or "").split())
    text = re.sub(r"^(?:the )?(?:gm|dm|game ?master)\s*:\s*", "", text, flags=re.I)
    if len(text) >= 2 and text[0] in "\"“" and text[-1] in "\"”":
        text = text[1:-1].strip()
    first = _GESTURE.search(text)
    if first:
        head, tail = text[:first.end()], text[first.end():]
        text = head + _GESTURE.sub("", tail)
    text = " ".join(text.split())
    gesture = ""
    m = _GESTURE.match(text)
    if m:
        gesture, text = m.group(0), text[m.end():].strip()
    found = re.findall(r"[^.!?]+[.!?]+[\"”’]*|[^.!?]+$", text)
    text = " ".join(s.strip() for s in found[:sentences] if s.strip())
    return (gesture + " " + text).strip() if gesture else text


def check(line: str, allowed_text: str, recent: list[str], digits: str = "none",
          max_words: int | None = MAX_WORDS, sentences: int = 2) -> tuple[str, str]:
    """(line, "") when it may go on the page, else ("", why).

    `digits` is "none" for table talk (no model authors a number) and "free" for a voiced
    `/gm` record, whose numbers `voiced_record` checks against the record itself.
    """
    line = tidy(line, sentences)
    if not strip_gestures(line):
        return "", "empty"
    if digits == "none" and re.search(r"\d", line):
        return "", "a number"
    if max_words and len(line.split()) > max_words:
        return "", "too long"
    allowed = set(_CAPWORD.findall(allowed_text or "")) | _ALWAYS
    for m in _CAPWORD.finditer(line):
        if m.group(0) not in allowed and not _sentence_start(line, m.start()):
            return "", f"a name the moment never used: {m.group(0)}"
    # A run of six words, or the whole line when it is shorter than that: "Well. That
    # settles that." is a copy at four words, and a six-word run alone never sees it.
    words = tuple(_WORD.findall(strip_gestures(line).lower()))
    if _shingles(line, COPY_RUN) & _example_runs() or (
            len(words) >= 3 and any(ex[:len(words)] == words for ex in _example_words())):
        return "", "copied an example"
    # The tic check. A repeated action is cut and the words kept; a repeated line is not
    # a line worth keeping at all.
    m = _GESTURE.match(line)
    if m:
        mine = _content_words(m.group(1))
        for old in recent:
            om = _GESTURE.search(old or "")
            theirs = _content_words(om.group(1)) if om else set()
            if mine and theirs and len(mine & theirs) * 2 >= min(len(mine), len(theirs)):
                line = line[m.end():].strip()
                break
    spoken = strip_gestures(line)
    for old in recent:
        if _shingles(spoken, 4) & _shingles(strip_gestures(old), 4):
            return "", "repeats a recent line"
    # The pet word. "Love" three times in six lines on the owner's first game, with "bold",
    # "audacity" and "nerve" beside it: a near-synonym walks past the four-word check above.
    # The same word of praise in one of the last few lines drops this one.
    mine = set(_WORD.findall(spoken.lower())) & PRAISE
    for old in recent[-PRAISE_WINDOW:]:
        if mine & set(_WORD.findall(strip_gestures(old).lower())):
            return "", f"praise word again: {sorted(mine)[0]}"
    return line, ""


# Words of praise a GM leans on. A closed list for a style tic, which is what mechanical
# detection is for on this project (CLAUDE.md); it decides nothing about meaning.
PRAISE = frozenset({"love", "loved", "bold", "boldly", "nerve", "audacity", "audacious",
                    "priceless", "brilliant", "amazing", "awesome", "chaos", "madness",
                    "genius", "legendary", "incredible", "fantastic", "solid", "nice"})
PRAISE_WINDOW = 3


def echoes(line: str, beat: str) -> bool:
    """Whether the line says again what the story just said: a run of five words shared
    with the beat. "You've successfully made your exit and made it to the market" told the
    player only what the page above it had. A paraphrase passes this; the quiet job's own
    instruction is what asks for silence instead."""
    return bool(_shingles(strip_gestures(line), 5) & _shingles(beat, 5))


def gives_the_reason(line: str, facts: list[str]) -> bool:
    """Whether a line over a refusal uses the refusal's own reason: at least one content word
    of a "Refused:" fact. Over both refusals of the owner's first game the GM praised the
    attempt and never said why it failed."""
    reasons = set()
    for f in facts:
        if f.startswith("Refused:"):
            reasons |= _content_words(f[len("Refused:"):]) - _GENERIC_REFUSAL
    return not reasons or bool(_content_words(strip_gestures(line)) & reasons)


# Words every refusal's sentence shares, which say nothing of THIS one's reason.
_GENERIC_REFUSAL = {"nothing", "rolled", "cannot", "there", "here", "they", "them",
                    "their", "first", "does", "doesn't", "will", "would", "that", "this"}


# --- after the beat --------------------------------------------------------------------

def _beat_since_player(c) -> tuple[str, str]:
    """(the player's last line, the GM's words on the page since it)."""
    player, beats = "", []
    for b in reversed(c.transcript):
        if b.get("who") == "player":
            player = str(b.get("text") or "")
            break
        if b.get("who") == "gm" and b.get("kind") != "aside":
            beats.append(str(b.get("text") or ""))
    beat = " ".join(reversed(beats))
    return player, beat[-900:]


def _recent_lines(c) -> list[str]:
    return [str(b.get("text") or "") for b in c.transcript
            if b.get("who") == "table"][-RECENT:]


# How many table-talk records the scene keeps for a bench or a report to read.
KEEP_LOG = 40


def _log(c, row: dict) -> None:
    """What the table talk did this turn, said or dropped and why, on the scene's own
    memory (`scene.said["table:log"]`, the last KEEP_LOG). Not `c.turn_log`: its length is
    the character's "turns played" (`campaign.save` → `roster.record`), and a line of
    commentary is not a turn."""
    mem = getattr(getattr(c, "scene", None), "said", None)
    if isinstance(mem, dict):
        log = list(mem.get("table:log") or [])
        log.append(row)
        mem["table:log"] = log[-KEEP_LOG:]


def after_the_beat(c, agent, resolution) -> None:
    """One or two lines of the GM's own voice under the beat, when the house rule asks.

    Never raises and never blocks the turn on a failure: table talk is the one part of a
    turn that may simply not happen. Appends `{"who": "table", "kind": "table", ...}` to
    the transcript. `who` is its own value, not "gm", on purpose: a dozen readers feed
    every `who == "gm"` beat back to the narrator (views `recent_narration`, the watcher),
    and the GM's table talk is not the story.
    """
    try:
        if houserules.table_talk() == "off":
            return
        # Every silent way out below "off" leaves its reason in the log: a turn with no GM
        # and no row was undiagnosable from the owner's own save (2026-11-07).
        intimate = getattr(agent, "_intimate_beat", None)
        if callable(intimate) and intimate():
            _log(c, {"said": "", "dropped": "an intimate beat"})
            return
        kinds, facts = moments(c, resolution)
        if not wanted(kinds, facts):
            _log(c, {"moments": kinds, "said": "", "dropped": "not a big moment"})
            return
        from gm import client
        from gm.client import ModelUnavailable

        v = voice()
        player, beat = _beat_since_player(c)
        job = job_for(kinds)
        msgs = table_messages(v, facts, player, beat, job)
        started = time.monotonic()

        def ask(messages):
            return str(getattr(client.chat(
                messages, agent.prose_model, agent.prose_host, as_json=False, think=False,
                temperature=0.8, num_predict=120, provider=agent.prose_provider,
                api_key=agent.prose_key), "text", "") or "")

        try:
            said = ask(msgs)
        except ModelUnavailable as exc:
            _log(c, {"moments": kinds, "said": "", "dropped": f"no model: {exc}"})
            return
        pc = c.scene.pc() if hasattr(c.scene, "pc") else None
        allowed = " ".join([*facts, player, beat, v["name"],
                            str(getattr(pc, "name", "") or "")])
        recent = _recent_lines(c)
        remade = False
        if said.strip() in (SILENCE, "—", "–", ""):
            line, why = "", "chose silence"
        else:
            line, why = check(said, allowed, recent)
            mend = _mend_ask(why) if not line else ""
            if mend:
                remade = True
                try:
                    said = ask(msgs + [{"role": "assistant", "content": said},
                                       {"role": "user", "content": mend}])
                except ModelUnavailable:
                    said = ""
                line, why = check(said, allowed, recent) if said else ("", why)
            if line and echoes(line, beat):
                line, why = "", "says the story again"
            if line and job == "refused" and not gives_the_reason(line, facts):
                # Detect, then repair narrowly (CLAUDE.md): one more ask for only what was
                # missing, the refusal's reason. Still missing, and the line is dropped.
                remade = True
                reason = " ".join(f[len("Refused:"):].strip() for f in facts
                                  if f.startswith("Refused:"))
                try:
                    again = ask(msgs + [
                        {"role": "assistant", "content": said},
                        {"role": "user", "content": "That does not tell them why it did "
                         f"not happen. In one or two sentences, say why, using this: {reason}"}])
                except ModelUnavailable:
                    again = ""
                line, why = check(again, allowed, recent) if again else ("", "no model")
                if line and not gives_the_reason(line, facts):
                    line, why = "", "never said why it was refused"
        seconds = round(time.monotonic() - started, 1)
        _log(c, {"moments": kinds, "job": job, "said": line, "dropped": why,
                 "seconds": seconds, "voice": v["id"], "remade": remade})
        if line:
            c.transcript.append({"who": "table", "kind": "table", "text": line,
                                 "voice": v["id"], "voice_name": v["name"]})
    except Exception as exc:  # noqa: BLE001 — commentary must never cost the turn
        _log(c, {"said": "", "dropped": f"error: {type(exc).__name__}: {exc}"})


# --- the GM's welcome, once, at the start of a campaign -----------------------------------

# What a new player is told about how this table works. Fixed, because these are facts
# about the app, not the world: the model says them in the GM's voice and adds nothing.
TABLE_TIPS = (
    "Say what your character does or says in your own words, the way you would at a table.",
    "Type /gm and a question to ask me anything out of character, about the game, the "
    "rules or the world.",
    "Press Continue when you want to let the world move on without doing anything.",
)

INTRO_SYSTEM = """You are {name}: the person running this Pathfinder game, greeting the \
player at the table before the first scene begins, out of character. {manner} {never}

Welcome them in three to five sentences. Name their character, the world and the place \
the story opens, from THE TABLE below, and nothing else: invent no person, place or \
event, and do not describe the scene (the story does that). Then pass on the tips below \
in your own words, briefly. No numbers.
{gestures}"""


def introduction(c, agent=None) -> None:
    """The GM's welcome, once, under a new campaign's opening beat (owner, 2026-11-06: "I
    think the GM should give an introduction on the first turn").

    Grounded like everything this layer says: the names come from the engine (the world,
    the place the story opens, the character's name, people and class), the tips from
    TABLE_TIPS, and the line is held by the same checks as table talk (no number, no
    name the table did not give, no copied example). Once per campaign, marked on the
    scene. With table talk off, or no model to ask, there is no welcome: the opening beat
    stands alone, as it always has. Never raises.
    """
    try:
        mem = getattr(c.scene, "said", None)
        if not isinstance(mem, dict) or mem.get("table:welcomed"):
            return
        mem["table:welcomed"] = True
        if houserules.table_talk() == "off":
            return
        from gm import client
        from gm.client import ModelUnavailable

        if agent is None:
            from gm.agent import GMAgent

            agent = GMAgent(c.world, c.engine())
        v = voice()
        pc = c.scene.pc() if hasattr(c.scene, "pc") else None
        world = str(getattr(getattr(c, "world", None), "name", "") or "")
        # Where the scene actually opens (the engine's own place), not the town it belongs
        # to: measured live 2026-11-07, Borin's story began on the road to Dunmarch and
        # the welcome said "Let's get started in Glimgear", read off `c.location`.
        try:
            place = str(getattr(c.engine().here(), "name", "") or "")
        except Exception:  # noqa: BLE001 — the town is the fallback, never an error
            place = ""
        place = place or str(getattr(getattr(c, "location", None), "name", "") or "")
        who = str(getattr(pc, "name", "") or "")
        what = " ".join(str(getattr(pc, k, "") or "") for k in ("race", "char_class")
                        if getattr(pc, k, "")).strip()
        table = "\n".join(x for x in (
            f"The character: {who}" + (f", {what}" if what else "") if who else "",
            f"The world: {world}" if world else "",
            f"Where the story opens: {place}" if place else "") if x)
        tips = "\n".join(f"- {t}" for t in TABLE_TIPS)
        system = INTRO_SYSTEM.format(name=v["name"] + " GM", manner=v["manner"],
                                     never=v["never"],
                                     gestures=_gesture_rule(True).replace(
                                         "- You may open", "You may open"))
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": f"THE TABLE:\n{table}\n\nTHE TIPS:\n{tips}"}]

        def ask(messages) -> str:
            return str(getattr(client.chat(
                messages, agent.prose_model, agent.prose_host, as_json=False, think=False,
                temperature=0.7, num_predict=260, provider=agent.prose_provider,
                api_key=agent.prose_key), "text", "") or "")

        try:
            said = ask(msgs)
        except ModelUnavailable as exc:
            _log(c, {"intro": True, "said": "", "dropped": f"no model: {exc}"})
            return
        allowed = " ".join([table, tips, v["name"]])
        line, why = check(said, allowed, [], digits="none", max_words=140, sentences=6)
        mend = _mend_ask(why) if not line else ""
        if mend:
            try:
                said = ask(msgs + [{"role": "assistant", "content": said},
                                   {"role": "user", "content": mend}])
            except ModelUnavailable:
                said = ""
            if said:
                line, why = check(said, allowed, [], digits="none", max_words=140,
                                  sentences=6)
        _log(c, {"intro": True, "said": line, "dropped": why, "voice": v["id"],
                 "remade": bool(mend)})
        if line:
            c.transcript.append({"who": "table", "kind": "table", "text": line,
                                 "voice": v["id"], "voice_name": v["name"],
                                 "welcome": True})
    except Exception as exc:  # noqa: BLE001 — a welcome must never stop a game beginning
        _log(c, {"intro": True, "said": "", "dropped": f"error: {type(exc).__name__}: {exc}"})


# --- /gm: the engine's record, in the GM's voice ---------------------------------------

_REFS = re.compile(r"\s*\(\s*c\d+\s*\)|\bc\d+\b")
_ID_LINE = re.compile(r"^\s*id:.*$", re.M)
_NUMBER = re.compile(r"\d+")
_NAME_RUN = re.compile(r"\b[A-Z][a-z’'\-]+(?:\s+[A-Z][a-z’'\-]+)*")
# Past this the record is a list, and a list is better read than retold: the GM says one
# line and the record is shown open beneath it.
SHORT_RECORD = 600
MAX_FACTS = 14


def _record_for_reading(record: str) -> str:
    text = _ID_LINE.sub("", record or "")
    return "\n".join(line.rstrip() for line in _REFS.sub("", text).splitlines() if line.strip())


def _record_facts(record: str) -> tuple[set[str], set[str]]:
    """(numbers, names) a retelling must keep: every number, and every capitalised name
    that is not a section heading ("WHERE:") or a sentence's first word alone."""
    numbers = set(_NUMBER.findall(record))
    names: set[str] = set()
    for line in record.splitlines():
        body = re.sub(r"^\s*[A-Z ]{3,}:\s*", "", line)
        for m in _NAME_RUN.finditer(body):
            run = m.group(0)
            if " " in run or not _sentence_start(body, m.start()):
                names.add(run)
    return numbers, names


RECORD_SYSTEM = """You are {name}: the person running this Pathfinder game, answering the \
player out of character. {manner} {never}

The player asked a question and the game's own record has the answer, below. Tell them \
what it says, across the table, in two to four sentences. This is not a scene: describe \
nothing in the world.

- Keep EVERY number and EVERY name from the record, exactly as written. Add no number and \
no name of your own.
- Do not add, guess or explain anything the record does not say.
{gestures}"""

LEAD_SYSTEM = """You are {name}: the person running this Pathfinder game, answering the \
player out of character. {manner} {never}

The player asked a question and you are about to hand them the game's record, which they \
will read for themselves. Say ONE short sentence as you hand it over. Mention no number, \
no name and no fact from the record.
{gestures}"""


def _gesture_rule(on: bool) -> str:
    return ("- You may open with one short action of your own in square brackets, like "
            "[I glance at your sheet.]" if on else
            "- Do not describe your own actions.")


def voiced_record(c, question: str, record: str) -> dict:
    """The `/gm` transcript entry for an answer the engine read off its own state.

    Short records are retold in the GM's voice, and the retelling is held to the record:
    it must carry every number and name the record has and no number it does not
    (`_record_facts`), or the plain record goes on the page instead. A long record (a
    pack, a roster) gets one handing-over line in the voice and the record shown open
    beneath it. Either way the record itself rides on the entry (`record`), one click
    away, because the one thing that must never blur is which words are the engine's.
    """
    plain = {"who": "gm", "kind": "aside", "text": record}
    try:
        from gm import client
        from gm.agent import GMAgent
        from gm.client import ModelUnavailable

        v = voice()
        gestures = houserules.table_talk() != "off"
        reading = _record_for_reading(record)
        numbers, names = _record_facts(reading)
        long = len(reading) > SHORT_RECORD or len(numbers) + len(names) > MAX_FACTS
        agent = GMAgent(c.world, c.engine())
        system = (LEAD_SYSTEM if long else RECORD_SYSTEM).format(
            name=v["name"] + " GM", manner=v["manner"], never=v["never"],
            gestures=_gesture_rule(gestures))
        ask = (f"The player asks: {question}" if long
               else f"The player asks: {question}\n\nTHE RECORD:\n{reading}")
        try:
            reply = client.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": ask}],
                agent.prose_model, agent.prose_host, as_json=False, think=False,
                temperature=0.5, num_predict=220, provider=agent.prose_provider,
                api_key=agent.prose_key)
        except ModelUnavailable:
            return plain
        said = str(getattr(reply, "text", "") or "")
        if not gestures:
            said = strip_gestures(said)
        pc = c.scene.pc() if hasattr(c.scene, "pc") else None
        allowed = " ".join([reading, question, v["name"], str(getattr(pc, "name", "") or "")])
        if long:
            line, why = check(said, allowed, [], digits="none", max_words=30, sentences=1)
            if not line:
                return plain
            return {"who": "gm", "kind": "aside", "text": line, "record": record,
                    "open": True, "voiced": True, "voice_name": v["name"]}
        line, why = check(said, allowed, [], digits="free", max_words=90, sentences=5)
        if not line:
            return plain
        said_numbers = set(_NUMBER.findall(line))
        if said_numbers != numbers or any(n not in line for n in names):
            # A number moved, appeared or vanished, or a name went missing: the record,
            # not a retelling of it.
            return plain
        return {"who": "gm", "kind": "aside", "text": line, "record": record,
                "voiced": True, "voice_name": v["name"]}
    except Exception:  # noqa: BLE001 — the record is always a correct answer
        return plain
