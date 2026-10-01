"""Intimate scenes at an explicit table: detected in code, briefed at the end of the
prompt, and shown the table's own demonstrations.

**The measurement this answers (2026-10-01, the owner's save `sam`).** With the content
house rule on "explicit", two beats the player asked for in as many words — "We go all
the way" and "we climax together and then clean up and get dressed" — came back soft and
metaphorical, a beat that ended "Every touch is a spark". The pipeline did not soften
them: the prose rows show the model's first drafts reached the page unchanged, the only
edit a recurring-phrase polish. The cause was the prompt. "Explicit" added one
~350-character line (`prompts.content_line`) to a system message of 13,103 characters of
turn briefing, behind 13,634 characters of worked examples written in a restrained
register, and two earlier beats written the same way. CLAUDE.md's lesson — instruction
volume loses to demonstration volume — measured once more.

So, for the one beat where it applies and no other, the balance is changed rather than
the wording:

  * **detection, in code** (`decide`): the player's line, the narrator's last two beats
    and the people here. Never asked of a model.
  * **a dedicated briefing** (`prompts.INTIMATE_BRIEFING`) in place of the turn
    briefing, which keeps the game's laws — the engine's tells, no numbers, nothing done
    for the player that they did not say, the hand-back — and drops what fights "write
    it plainly in the body": the four moves with their PUSH (the weather turns, a door
    closes), the wound-and-blow language of `PROSE_AFTER_EXTRA`, the op reference.
  * **a note at the end** of the last message (`prompts.INTIMATE_NOTE`).
  * **the table's own passages as example turns**, from ONE file in the data folder that
    the owner writes: `<data dir>/homebrew/style/intimate.txt` — on the owner's machine
    `C:\\Users\\natha\\AppData\\Local\\PathfinderGM\\homebrew\\style\\intimate.txt`
    (`demonstrations_path`). Created holding only a header, and only when it is missing:
    the owner may write it before any build reads it, and a file that exists is never
    overwritten or prepended to.

**Prior art (searched 2026-10-01, primary documentation unless said).**

  * SillyTavern's World Info activates an entry only when its keywords appear in the
    last N messages ("Scan Depth"), and orders insertion so that "entries with larger
    order numbers will be inserted closer to the end of the context as they will have
    more impact on the output" (docs.sillytavern.app/usage/core-concepts/worldinfo/).
    Taken: a scene-specific instruction triggered by detection over the recent beats,
    not carried on every turn.
  * SillyTavern's Author's Note is inserted at a depth counted from the end of the chat
    ("Depth 0 = placed at the very end"), and "the closer the Author's Note is to the
    bottom of the prompt, the more impact it has on the next AI response"
    (…/core-concepts/authors-note/). KoboldAI's wiki says the same of its two slots:
    Memory is "the first thing that the AI sees" and the farthest from the new text;
    the Author's Note sits "only a few lines above the new text" and has "a larger
    impact on the newly generated prose" (KoboldAI-Client wiki, "Memory, Author's Note
    and World Info"). Taken: `INTIMATE_NOTE` goes last in the final user message, after
    the tells and the scene as it stands. Neither source says WHY the end wins; the
    measured basis is *Lost in the Middle* (Liu et al., 2023), already the reason
    `call_prose_messages` puts its load-bearing blocks last.
  * SillyTavern's example dialogues (`{{mesExamples}}`) are put into the prompt
    "instruct-formatted with a separator" — as turns, in the model's own chat format
    (…/prompts/context-template/). That they are inserted "like chat history" and pushed
    out once the real conversation grows is said by third-party guides only; I could not
    confirm it in the primary docs. Taken: the owner's passages go in as example turns
    through `call_one_messages(examples=…)` — the mechanism Continue already uses — and
    REPLACE the restrained worked examples for this beat, so the only scene-shaped
    replies the model sees are the ones written the way the table wants. Pasted into the
    system text instead, they would be one more paragraph of instruction at the far end
    of the window, which is the slot that lost.

Adults only, without exception, in code and not in the prompt alone: the briefing is
never used when anyone here, or anyone the player's line or the last two beats name, is a
minor (`judgement.a_child_in`); the beat fades to black instead. A demonstration that names
a child is never shown. And `views._finish` still discards any finished beat that reads as
sexual with a child in it — on this path it does so whatever the beat's vocabulary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

# --- the owner's file -------------------------------------------------------------------

# How many of the owner's passages are shown in one beat, and how much in all. Three
# because one passage is copied and three varied ones are a register
# (`CARRY_ON_EXAMPLES` shows three for the same reason). The total, 5,400, is under half
# the 13,634 characters of worked examples it replaces, so `prompts.pack` never has to
# drop the scene's history to make room for it. A file holding more than fits is not
# cut: whole passages are chosen, and the choice ROTATES with the beat (`select`), so
# every passage the owner wrote is shown over a scene and no one passage is the only
# one the model ever learns from.
MAX_PASSAGES = 3
TOTAL_CHARS = 5400
# The grammar's ceiling on the narration string (`prompts.GRAMMAR_MAXLENGTH_CEILING`). A
# demonstration longer than the model is allowed to write teaches a length the sampler
# then cuts mid-word (item 6, 2026-09-30), so a longer passage is flagged in the turn
# log — and still shown whole: a passage cut in the middle would teach a scene that
# stops in the middle.
PASSAGE_CHARS = 1800
# What a passage is shown answering when the owner gave no "> " line of their own. A
# generic continuation, deliberately: it names no act and nobody, so it can neither
# teach the model a particular move nor put words in the player's mouth, and it reads
# the same as the beats a passage without one is most like — the middle of a scene.
DEFAULT_PLAYER_LINE = "I go on with what we are doing."

HEADER = """\
# Intimate scenes: how you want them written
#
# Put passages here written the way you want the narrator to write an intimate
# scene: the register, how plainly, how long. The narrator is shown them as replies
# it wrote earlier, which steers it far harder than any instruction can.
#
# The format. Separate passages with a numbered line on its own ("1.)", "2.)") or a
# line of three or more dashes (---). Start each passage with a line beginning "> ":
# the player's line it answers, for example
#   > I take their hand and lead them to the bed
# and write the narrator's reply below it. A passage with no "> " line is shown as
# the answer to "I go on with what we are doing."
#
# Writing them well:
# - No names. A name in here leaks into play, and the game will flag it as a person
#   who does not exist. Write "she", "he", "they", "you".
# - Keep the setting neutral: no particular room, town or weather to copy.
# - Keep each passage under about 1,500 characters (about 250 words). The narrator
#   can write at most 1,800; a longer example teaches a length it will be cut at.
# - Write it as the game narrates, to the player as "you" -- but let the narrator
#   describe and the OTHER person speak and act. A passage where the narrator speaks
#   or decides for "you" teaches it to act for the player.
#
# How many: as many as you like. Up to 3 are shown on any one beat, about 5,400
# characters in all, and which ones turns over from beat to beat so they all get used.
# Problems (a passage too long, a name that recurs) are noted in the game's turn log.
#
# When it is used: only with the house rule "When a scene turns to intimacy" set to
# Explicit, only on a beat the game has detected as an intimate scene, and only
# when everyone present or named in the scene is an adult. With a child present or
# named, the scene fades to black instead, whatever is in this file, and a passage
# that names a child is never shown.
#
# It is read fresh on every beat: save this file and the next beat uses it, no
# restart. Lines starting with # are notes like these and are never shown to the
# narrator. With no passages, the narrator still gets the explicit-scene briefing,
# without examples.
"""


def demonstrations_path() -> Path:
    """`<data>/homebrew/style/intimate.txt` — the data folder the app resolves
    (`settings.CAMPAIGN_DIR`, from PATHFINDER_GM_DATA or the user's local app data),
    never the install or the bundle: CLAUDE.md's frozen-app rule, `__file__` points
    inside PyInstaller's temporary folder and says nothing about where the table's own
    files live. Beside `house-rules.json`, the same way `houserules._path` finds it."""
    return Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "style" / "intimate.txt"


def ensure_file() -> Path:
    """The file, created holding only the header when it is missing — and only then.
    The owner may write it before any build reads it: an existing file is never
    overwritten or prepended to. The `style` folder is made as needed."""
    path = demonstrations_path()
    if not path.exists():
        from pathfindergm import files

        files.write_text(path, HEADER)
    return path


# Where one passage ends and the next begins: a numbered line on its own ("1.)", "2.",
# "3))") or a line of three or more dashes. Both, because the owner's own draft numbers
# them and the header shows dashes.
_SEPARATOR = re.compile(r"(?m)^\s*(?:\d+[.)]+|-{3,})\s*$")
# A capitalised word not at the start of a sentence: a name, most likely. Shown to the
# model, a name becomes "a person who does not exist" in play (`invented-name`).
_CAPITAL = re.compile(r"(?<![.!?]\s)(?<![.!?][\"'”’]\s)(?<!^)\b([A-Z][a-z]{2,})\b")
_NOT_NAMES = {"You", "Your", "Yours", "She", "Her", "Hers", "He", "His", "Him", "They",
              "Their", "Them", "The", "And", "But", "Then", "When", "What", "Yes", "Not",
              "God", "Gods", "Oh"}


@dataclass
class Passage:
    n: int
    player: str
    narration: str

    @property
    def size(self) -> int:
        return len(self.player) + len(self.narration)


@dataclass
class Demonstrations:
    """What the file gave this beat: the passages chosen, as example turns, and the
    counts and warnings the turn log records. Never the passages' text in the log."""
    examples: list[dict] = field(default_factory=list)
    chars: int = 0
    on_file: int = 0
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse(raw: str) -> tuple[list[Passage], list[str]]:
    """Every passage in the file, in order, and why any was left out. Comment lines go
    first, so a numbered or dashed line inside a comment separates nothing."""
    from . import judgement

    body = "\n".join(ln for ln in str(raw or "").splitlines()
                     if not ln.lstrip().startswith("#"))
    out: list[Passage] = []
    dropped: list[str] = []
    n = 0
    for chunk in _SEPARATOR.split(body):
        lines = [ln for ln in chunk.strip().splitlines() if ln.strip()]
        if not lines:
            continue
        n += 1
        player = DEFAULT_PLAYER_LINE
        if lines[0].lstrip().startswith(">"):
            player = " ".join(lines[0].lstrip()[1:].split()) or DEFAULT_PLAYER_LINE
            lines = lines[1:]
        narration = " ".join(" ".join(lines).split())
        if not narration:
            dropped.append(f"passage {n}: a player's line and no reply")
            continue
        # Adults only, on the owner's own words too: a passage naming a child is never
        # shown, whatever the rest of it says.
        if judgement.a_child_in(None, f"{player} {narration}"):
            dropped.append(f"passage {n}: names a child, never shown")
            continue
        out.append(Passage(n, player, narration))
    return out, dropped


def warnings_for(passages: list[Passage]) -> list[str]:
    """What the owner should know about the file, for the turn log — never blocking.
    A passage longer than the narrator may write; a capitalised name that recurs
    across passages, which the model would carry into play."""
    out = [f"passage {p.n}: {len(p.narration):,} characters, over the "
           f"{PASSAGE_CHARS:,} the narrator can write — it teaches a length that gets cut"
           for p in passages if len(p.narration) > PASSAGE_CHARS]
    seen: dict[str, set[int]] = {}
    for p in passages:
        for line in (p.player, p.narration):
            for m in _CAPITAL.finditer(line):
                word = m.group(1)
                if word not in _NOT_NAMES:
                    seen.setdefault(word, set()).add(p.n)
    recurring = sorted(w for w, ns in seen.items() if len(ns) >= 2)
    if recurring:
        out.append(f"names recurring across passages: {', '.join(recurring)} — they "
                   f"would leak into play as people who do not exist")
    return out


def select(passages: list[Passage], beat: int = 0) -> tuple[list[Passage], list[str]]:
    """Whole passages for this beat, within `MAX_PASSAGES` and `TOTAL_CHARS`, starting
    at `beat` modulo how many there are and going round — deterministic, so a replay
    shows the same ones, and turning over, so a long file is all used across a scene.
    Never a passage cut part-way."""
    if not passages:
        return [], []
    start = int(beat or 0) % len(passages)
    order = passages[start:] + passages[:start]
    chosen: list[Passage] = []
    total = 0
    left: list[str] = []
    for p in order:
        if len(chosen) >= MAX_PASSAGES:
            left.append(f"passage {p.n}: not this beat ({MAX_PASSAGES} shown)")
            continue
        if total + p.size > TOTAL_CHARS:
            left.append(f"passage {p.n}: not this beat (over the {TOTAL_CHARS:,} total)")
            continue
        chosen.append(p)
        total += p.size
    return chosen, left


def read_demonstrations(beat: int = 0) -> Demonstrations:
    """The owner's passages for this beat, read fresh — no cache, the `houserules`
    reasoning: a cached copy of a file the owner just saved is a change that silently
    is not in effect.

    Each chosen passage becomes one example exchange in the shape `call_one_messages`
    takes: `{"player": <their "> " line>, "reply": {"narration": <the reply>}}`."""
    out = Demonstrations()
    try:
        raw = ensure_file().read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        out.skipped.append(f"unreadable: {exc}")
        return out
    passages, out.skipped = parse(raw)
    out.on_file = len(passages)
    out.warnings = warnings_for(passages)
    chosen, left = select(passages, beat)
    out.skipped += left
    for p in chosen:
        out.examples.append({"player": p.player, "reply": {"narration": p.narration}})
        out.chars += p.size
    return out


# --- detection ----------------------------------------------------------------------------

# The player's line asking for intimacy, in words softer than `narration.intimate`'s.
# Never enough alone — every one of these has an ordinary reading ("all the way to the
# gate", a kiss goodbye, "I go to bed") — so each needs a scene already warm around it.
_CUE = re.compile(
    r"\b(?:all the way|kiss(?:es|ed|ing)?|make love|making love|lie with|"
    r"sleep(?:s|ing)? with|to bed|into bed|onto the bed|undress\w*|disrob\w*|"
    r"strip(?:s|ped|ping)? (?:her|him|them|off|naked)|caress\w*|fondl\w*|embrac\w*|"
    r"inside (?:her|him|them|me)|on top of (?:her|him|them|me)|deeper|"
    r"(?:her|his|their) (?:lead|body|bodies|breasts?|thighs|hips|lips|neck|mouth)|"
    r"letting (?:her|him|them) lead)\b", re.I)

# What a beat already in the middle of intimacy reads like, as the narrator writes it —
# metaphor and all. Calibrated on the owner's own beats, where `narration.intimate` (the
# minors guard's vocabulary, built for explicit words) fired on none of five: the prose
# was too euphemistic for it. Counted as DISTINCT kinds, so one word repeated is one.
_WARM = {
    "kiss": r"\bkiss\w*",
    "lips": r"\blips\b",
    "moan": r"\bmoan\w*",
    "gasp": r"\bgasp\w*",
    "breath": r"\bbreath\w*\b[^.!?]{0,25}\b(?:against|on|at) (?:your|her|his|their) "
              r"(?:skin|neck|ear|throat|lips|mouth)",
    "skin": r"\bskin (?:on|against) skin\b|\bbare skin\b|\bagainst your skin\b",
    "arch": r"\barch(?:es|ed|ing)? (?:into|against|beneath|under|up)\b",
    "body": r"\b(?:her|his|their) body (?:against|beneath|under|over)\b|"
            r"\bagainst your (?:chest|body)\b",
    "thighs": r"\bthighs?\b",
    "hips": r"\bhips?\b",
    "undress": r"\bundress\w*|\bnaked\b|\bnude\b",
    "straddle": r"\bstraddl\w*",
    "caress": r"\bcaress\w*|\bfondl\w*",
    "desire": r"\bdesire\b|\baroused\b|\barousal\b|\bpleasure\b",
    "slick": r"\bslick\w*",
    "shudder": r"\bshudder\w*|\btrembl\w*",
    "bed": r"\bbed\b|\bsheets\b",
    "embrace": r"\bembrac\w*",
}
_WARM_RX = {k: re.compile(v, re.I) for k, v in _WARM.items()}
# Three distinct kinds across the last two beats. Two fired on a whispered secret ("her
# breath against your ear, her lips close") in the cases below; three did not, and every
# beat of the owner's scene from the second on carried three or more.
WARM_AT = 3
# How many of the narrator's own beats the scene is read from: the one being continued
# and the one before it, the window `prompts.EARLIER_BEATS` already shows the model.
WINDOW = 2

# The person a strong word is about. "I wait for the climax of the play" is not a
# scene with anybody.
_PERSON = re.compile(r"\b(?:her|him|them|we|us|each other|one another)\b", re.I)


def warm_kinds(texts) -> set[str]:
    """Which kinds of intimate description the beats carry, by name."""
    joined = " ".join(str(t or "") for t in texts)
    return {k for k, rx in _WARM_RX.items() if rx.search(joined)}


def partners(scene) -> list:
    """Who here the scene could be with: alive, up, not the player, not hostile."""
    from rules import states

    out = []
    for a in (getattr(scene, "actors", {}) or {}).values():
        if a.is_pc or a.is_down or int(getattr(a, "hp", 0) or 0) <= 0:
            continue
        if states.attitude_of(a) == "hostile":
            continue
        out.append(a)
    return out


def reads_intimate(player_input: str, earlier, scene) -> tuple[bool, str]:
    """Whether this beat is an intimate scene, and why, decided in code.

    Measured cases (tests/test_intimate_scenes.py): the owner's "We go all the way" and
    "we climax together and then clean up and get dressed" detect; "I pay for the room",
    "she hugs her brother goodbye", "I go all the way to the docks", a kiss goodbye after
    an ordinary beat, and "I wait for the climax of the play" do not.

    Privacy is NOT a gate: the engine holds no fact that says a room is private, and a
    word-guess at one ("chamber", "alone") would be the free-text guessing CLAUDE.md
    warns against. Somebody to be intimate with, out of a fight, is."""
    from . import judgement, narration
    from .prompts import CARRY_ON

    if scene is not None and getattr(scene, "in_encounter", False):
        return False, "a fight is running"
    if scene is not None and not partners(scene):
        return False, "nobody here to be intimate with"
    line = str(player_input or "")
    if line != CARRY_ON and judgement.player_departs(line):
        return False, "the player is leaving"
    recent = [str(b or "") for b in list(earlier or [])[-WINDOW:]]
    warm = warm_kinds(recent)
    warm_scene = len(warm) >= WARM_AT or any(narration.intimate(b) for b in recent)
    if line != CARRY_ON and narration.intimate(line) and (_PERSON.search(line) or warm_scene):
        return True, "the player's line is sexual"
    if not warm_scene:
        return False, "the scene is not intimate"
    if line == CARRY_ON:
        return True, "Continue, in a scene already intimate"
    if _CUE.search(line):
        return True, "the player's line carries an intimate scene on"
    return False, "the player's line turns elsewhere"


def minors_involved(scene, player_input: str, earlier) -> bool:
    """Anybody here whose record is a minor, or a child the player's line, the last two
    beats or the names of the people here mention. Errs wide, the way the guard after
    the prose does: a false positive fades one scene, which is the right way to be
    wrong."""
    from . import judgement

    names = " ".join(str(a.name or "") for a in
                     (getattr(scene, "actors", {}) or {}).values()) if scene else ""
    text = " ".join([str(player_input or ""), names]
                    + [str(b or "") for b in list(earlier or [])[-WINDOW:]])
    return judgement.a_child_in(scene, text)


@dataclass
class Decision:
    """What this beat's prose call is briefed with.

    `mode`: "intimate" — the dedicated briefing; "fade" — the fade line, forced because
    a child is present or named; "" — today's behaviour, `prompts.content_line()`."""
    mode: str = ""
    why: str = ""
    demonstrations: Demonstrations | None = None

    @property
    def fired(self) -> bool:
        return self.mode == "intimate"

    def as_log(self) -> dict:
        """For the turn log: whether it fired and how much was injected, never the
        text."""
        demo = self.demonstrations
        return {"fired": self.fired, "mode": self.mode or "default", "why": self.why,
                "demos": len(demo.examples) if demo else 0,
                "demo_chars": demo.chars if demo else 0,
                **({"on_file": demo.on_file} if demo else {}),
                **({"skipped": list(demo.skipped)} if demo and demo.skipped else {}),
                **({"warnings": list(demo.warnings)} if demo and demo.warnings else {})}


def decide(player_input: str, earlier, scene, content: str | None = None,
           beat: int = 0) -> Decision:
    """The one place the content rule, the detection and the adults-only rule meet.

      * "fade" at the table: exactly today's prompt, nothing read, nothing changed;
      * "explicit" with a child present or named: the fade line, whatever was detected
        — stricter than before this module, when an explicit table's line went out
        with a child in the scene and only the guard after the prose stood in the way;
      * "explicit", detected, adults only: the dedicated briefing and the owner's
        passages;
      * "explicit", not detected: today's prompt.

    `beat` is how far into the campaign this beat is (the transcript's length), which
    turns the owner's passages over (`select`).
    """
    if content is None:
        from rules import houserules

        content = houserules.content()
    if content != "explicit":
        return Decision(why="the table fades")
    if minors_involved(scene, player_input, earlier):
        return Decision(mode="fade", why="a child is present or named")
    hit, why = reads_intimate(player_input, earlier, scene)
    if not hit:
        return Decision(why=why)
    return Decision(mode="intimate", why=why, demonstrations=read_demonstrations(beat))
