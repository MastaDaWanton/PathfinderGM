"""The player's body on the page: what the engine says it is carrying, shown or not at all.

The owner, 2026-10-05, with a screenshot: *"prose acts like im okay but im literally starving
and days past the last rest. the prose should reflect this."* The sidebar read Life 18 of
73, Hunger "starving", Rest "past a day awake"; the beat was a calm walk down the road to
Grotburrow — "The silence here is heavy, broken only by the distant, low lowing of cattle" —
with no hunger, no wound and no tiredness in it. The brief had carried "18/73 hp" in the
middle of the cast list and nothing at all of hunger, thirst or sleep (they lived on the
sidebar only). The brief now ends with the body (`prompts.body_now`); this holds the page
to it, because an instruction alone is the fix CLAUDE.md records as never holding.

**What counts as shown.** A strain is shown when a sentence of narration (speech blanked —
a character's "you look starved" is not the narrator's) carries a word of its family AND is
about the player: a second-person word in it, or the family's own abstract noun ("Hunger
sits under your ribs", "Exhaustion makes the road swim"). The families are generous on
purpose — precision is what a finding costs, and a beat given the benefit of the doubt
costs nothing: "your muscles ache from the stiffness of the earth" shows fatigue. Code does
not decide what the sentence means; it decides whether the body has a word on the page at
all, the shape `beat_verify._omissions` and `press_the_death` already use (a kill with no
death word anywhere).

**The repair is the house shape** (docs/narrator-guards.md D1). One sentence about the
player — the first narration sentence in the second person that does not say the hour (so
it is not the sentence the hour's repair is rewriting) and carries no body word yet (so a
rewrite that shows half of it is kept, `anchor`) — is sent back once with only what
was missing named: "starving — five days without food". The rewrite is kept only if the
page then shows it (`_repair_sentences` asks `find` again). What still is not shown gets
the **backstop**: an authored sentence for that strain, chosen least-recently-used per
campaign (`narration.least_recently_used`, Inform's `[at random]` made deterministic), put
before the hand-back. Every authored line carries a word of its own family, so the detector
that judges the page recognises its own backstop; and every one is marked added
(`authored_in`, read by `GMAgent.narrate_turn`), so it is never shown back to the model as
its own prose (D4 — the death line taught itself to the model four times running).

Not in a fight: a fight's wounds are the blows' tells, and its beats are short. Not on an
NPC's turn or an outcome line: the player's body is the player's beat.

"many feet" (sammy.json, beat 71, a Kasatha) is a body-PLAN contradiction this module does
not judge: the race document's body line is in the brief (`races.body_line`) and nothing
checks the page against it yet.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._page import page_sentences

ORDER = 63
KINDS = frozenset({"body-left-off-the-page"})
DOORS = frozenset({"turn"})

_YOU = re.compile(r"\b(?:you|your|yours|yourself)\b", re.I)

# Each strain's family. A word of it in a sentence about the player shows the strain.
_SLEEP = (r"sleep\w*|sleepless\w*|tired\w*|wear(?:y|ier|iest|ily|iness)|exhaust\w*|"
          r"fatigu\w*|drows\w*|eyelids?|yawn\w*|groggy|bleary|heavy-lidded|bone-tired|"
          r"stagger\w*|sway(?:s|ed|ing)?|nod(?:s|ded|ding)? off|dozing|doze\w*")
FAMILY: dict[str, re.Pattern] = {
    "hunger": re.compile(
        r"\b(?:hunger\w*|hungry|hungrily|starv\w*|famish\w*|ravenous\w*|stomach\w*|belly|"
        r"bellies|gnaw\w*|unfed|eaten|food|meals?)\b", re.I),
    "thirst": re.compile(
        r"\b(?:thirst\w*|parched|throat|tongue|lips?|swallow\w*|dehydrat\w*|"
        r"(?:dry|dried|cracked) (?:mouth|lips?)|without water|no water)\b", re.I),
    "sleep": re.compile(r"\b(?:" + _SLEEP + r")\b", re.I),
    "fatigue": re.compile(
        r"\b(?:" + _SLEEP + r"|ach(?:e|es|ed|ing)|stiff\w*|heaviness|leaden|sore\w*|"
        r"muscles?|limbs?)\b", re.I),
    "wounds": re.compile(
        r"\b(?:wound\w*|blood\w*|bleed\w*|bled|injur\w*|hurt\w*|pain\w*|bruis\w*|gash\w*|"
        r"bandag\w*|limp(?:s|ed|ing)?|battered|stitch\w*|scab\w*)\b", re.I),
}
# "throb" left the wound family the same day: "the gnawing ache of hunger in your stomach
# has become a constant, dull throb" read as the wounds shown (live, 2026-10-05), and the
# page never touched them.
# "food" alone, live (2026-10-05): "the lack of food makes your head swim with a dull,
# hollow ache" is hunger shown, and the family wanted "without food" — so the backstop wrote
# a second hunger line under the model's own.
# Measured on the owner's 28 long beats (2026-10-05) before these were cut: "heavy" made
# "The heavy, stagnant air … as you pass the crossroads" a tired body (fatigue "shown" in
# 11 of 28), "scrape" made "the rhythmic scrape of your boots" a wound. Scenery words, not
# the body's; the benefit of the doubt is for a body word, not for any word.
# The abstract nouns that are about the player on their own: "Hunger sits like a stone".
_ABSTRACT = re.compile(r"\b(?:hunger|thirst|weariness|exhaustion|fatigue|sleeplessness|"
                       r"pain)\b", re.I)

# Words that say the hour, so the anchor is not the sentence the hour's repair rewrites.
_HOUR = re.compile(r"\b(?:morning|noon|midday|afternoon|evening|night|dawn|dusk|sunset|"
                   r"sunrise|twilight|midnight|sun|moon|stars)\b", re.I)


def _about_the_player(narration: str) -> bool:
    return bool(_YOU.search(narration) or _ABSTRACT.search(narration))


def shown(text: str, key: str) -> bool:
    """Whether the page's narration shows strain `key` on the player at all."""
    family = FAMILY[key]
    return any(family.search(n) and _about_the_player(n) for _w, n in page_sentences(text))


def missing(ctx, text: str | None = None) -> list:
    """The strains the engine holds (`survival.strains`) that the page does not show."""
    from rules import survival

    scene = ctx.scene
    if getattr(scene, "in_encounter", False):
        return []
    pc = scene.pc() if hasattr(scene, "pc") else None
    text = ctx.text if text is None else text
    if pc is None or not str(text or "").strip():
        return []
    return [s for s in survival.strains(pc) if not shown(text, s.key)]


def anchor(text: str) -> str:
    """The sentence the rewrite folds the body into: the first narration sentence about
    the player that is not the hand-back question and does not say the hour; else the
    first about the player; else none (the finding then goes straight to the backstop)."""
    # Never a sentence that already carries the body. Live, 2026-10-05: the rewrite put
    # the hunger into its sentence and not the wound, the next `find` named that same
    # sentence again, and `_repair_sentences` threw the whole rewrite away as "still did
    # it" — the hunger the model had written was lost and both lines came from the pool.
    # Anchored elsewhere, a rewrite that shows part of the body is kept and the backstop
    # writes only the rest.
    open_ = [(w, n) for w, n in page_sentences(text)
             if n.strip() and not w.rstrip().endswith("?")
             and not any(f.search(n) for f in FAMILY.values())]
    about = [(w, n) for w, n in open_ if _YOU.search(n)]
    # The player as the subject first ("You travel the stretch of road…"): a body folds
    # into a sentence about what they do far better than into one about the air.
    led = [(w, n) for w, n in about if _LEADS.match(n)]
    for w, n in (*led, *about, *open_):
        if not _HOUR.search(n):
            return w
    return open_[0][0] if open_ else ""


_LEADS = re.compile(r"\s*(?:you|your)\b", re.I)


def find(ctx) -> list[Finding]:
    gone = missing(ctx)
    if not gone:
        return []
    said = "; ".join(s.words for s in gone)
    where = anchor(ctx.text)
    return [Finding(
        "body-left-off-the-page",
        f"the page shows nothing of the player's body: {said}",
        (f"The player's character is {said}. Rewrite the sentence so it ALSO shows that "
         f"in their body — how it feels, how they move — keeping everything else it "
         f"says. No numbers."),
        weight=2, sentences=(where,) if where else ())]


# The backstop's lines, three to a strain (two for each wound grade), each concrete, each
# in the second person, each carrying a word of its own family so `shown` recognises it.
POOL: dict[str, tuple[str, ...]] = {
    "hunger": (
        "Your stomach has given up growling and settled into a hollow ache; it has been "
        "days since you ate.",
        "Hunger sits under your ribs like a cold stone, and your hands are not as steady "
        "as they should be.",
        "Your empty belly clenches at every smell of smoke or cooking; you are starving, "
        "and every step knows it.",
    ),
    "thirst": (
        "Your tongue is thick and your lips are cracked; thirst has dried your throat to "
        "paper.",
        "Every swallow scrapes your throat, and the thirst has become a dull, constant "
        "drumming behind your eyes.",
        "Your mouth is parched, and you catch yourself thinking of water more than of the "
        "way ahead.",
    ),
    "sleep": (
        "Your eyes burn and your thoughts come slowly; you have gone far too long without "
        "sleep.",
        "Weariness drags at your eyelids, and twice you catch yourself swaying where you "
        "stand.",
        "The edges of everything blur with sleeplessness, and the ground begins to look "
        "almost like a bed to you.",
    ),
    "fatigue": (
        "Your limbs are heavy, and every movement costs you more than it should.",
        "A bone-deep weariness slows you; even standing still is work for your body.",
        "Your muscles ache in a dull, leaden way, and it shows in every step you take.",
    ),
    "wounds:grave": (
        "Your wounds throb with every heartbeat, and you are moving on very little but "
        "stubbornness.",
        "Blood has dried stiff in your clothes, and the pain of your injuries leaves you "
        "light-headed.",
        "Each breath pulls at your wounds; you are badly hurt, and your body will not let "
        "you forget it.",
    ),
    "wounds:bad": (
        "Your wounds pull and sting as you move, a steady reminder of the blows you have "
        "taken.",
        "The pain of your injuries flares whenever you turn too quickly.",
        "Your hurts are stiffening, and you favour the worst of them without thinking.",
    ),
}


def _cell(strain) -> str:
    if strain.key != "wounds":
        return strain.key
    return "wounds:grave" if strain.words.startswith("gravely") else "wounds:bad"


# The most a backstop puts on one beat: two authored sentences in a row already read as a
# list, and the brief still carries every strain for the next beat.
MOST = 2


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    from gm import narration as narration_mod

    notes: list[str] = []
    said = getattr(ctx.scene, "said", None)
    for strain in missing(ctx, text)[:MOST]:
        if shown(text, strain.key):     # an earlier line here may have shown it
            continue
        cell = _cell(strain)
        pool = POOL[cell]
        line = pool[narration_mod.least_recently_used(said, f"body:{cell}", len(pool))]
        text = narration_mod.put_before_the_hand_back(text, line)
        notes.append(f"body left off the page: {strain.words} — wrote {line[:60]!r}")
    return text, notes


def authored_in(text: str) -> list[str]:
    """The backstop's own sentences on this page, for `GMAgent.last_added` (D4)."""
    return [line for pool in POOL.values() for line in pool if line in str(text or "")]
