"""Poor light on the page: a fight or a search in dim light or darkness reads as one.

The owner, 2026-10-06, on the light model's miss chance (alchemy open point 8): *"keep the
book rule but make sure that it naturally makes it into prose that you can barely see and
that it making it hard to hit your target."* The engine already decides it — `Scene.
light_at` gives the level at a square as a creature sees it, `Actor.concealment` turns dim
light into a 20% miss chance and darkness into 50% (CRB, Vision and Light), and a swing the
miss chance decided is told: "the thug finds nothing there — dim light, 20% miss chance".
Nothing put the light in front of the narrator but that one tell, and nothing held the
page to it: a night fight could read as a sunny brawl, and the blow the dark swallowed
as an ordinary miss.

**What the engine does in the traditions.** DikuMUD's descendants render sight in the
message itself, never by asking the writer: CircleMUD's `PERS(ch, vict)` is
`CAN_SEE(vict, ch) ? GET_NAME(ch) : "someone"` (src/utils.h), so a blow from the dark
arrives as "Someone hits you"; NetHack's blind messages are "You hit it." The narrator here
is a model and cannot be given a macro, so the house shape stands in for one: the fact goes
last in the prompt (`prompts.light_now`, beside `body_now` and `hour_now`), and this check
holds the page to it.

**Three findings, each detected in code** (docs/narrator-guards.md D1):

- `light-miss-unshown` — a swing the light's miss chance decided (the tell's own words,
  `finds nothing there — dim light|darkness`), and no narration sentence that carries both
  a word of poor sight (`SIGHT`) and the blow failing (`MISSED`). The anchor is the first
  sentence about a blow that misses, else about a blow. Read on the player's turn and on the outcome lines of anyone else's — a thug
  swinging at the player in the dark misses in the dark too.
- `light-left-off-the-page` — the player's own sight is dim or dark (`sight`, the one
  derivation `light_now` also reads) in a fight or a search, and no sentence anywhere
  carries a word of poor sight. The player's turn only.
- `light-contradicted` — a sentence that lights the scene the engine holds dark: sunlight,
  daylight, glare, a well-lit room (`BRIGHT`, a closed list). Not when the sentence names a
  light the scene has (a torch's glare is the torch's).

Words, never numbers: a sentence carrying the tell's "miss chance" or a percentage is the
mechanics on the page, and is a `light-contradicted` finding too — the rewrite says it in
the fiction.

**Repair** is one rewrite of the anchor with the fact named; the backstop is an authored
line per cell (miss by the player, miss at the player, the gloom; dim or dark),
least-recently-used per campaign, marked ours (`authored_in`, D4), and a contradicting
sentence the rewrite could not fix is cut. Every authored line carries a `SIGHT` word, so
the detector recognises its own backstop.

Not judged: darkvision's grey world (a player with darkvision in range is not in poor
light by the engine's own reading, so nothing is owed); Stealth and Perception in the dark,
which the owner's ruling leaves for a later pass.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._page import field, page_sentences

ORDER = 63
KINDS = frozenset({"light-miss-unshown", "light-left-off-the-page", "light-contradicted"})
DOORS = frozenset({"turn", "outcome"})

# Words that show poor sight, as a family (`body_shown`'s shape). Not "night", "moon" or
# "stars" alone — they say the hour, not how little can be seen ("the night air is cold"
# is not a man you can barely make out).
#
# Measured over the 191 recorded gm beats in tests/replay (all lit — taverns, streets,
# day; 2026-10-06): the first, generous family found a word of it in 51 of them, so a
# night beat could pass on a word any day beat carries — "shadow" 30 times ("a shadow
# crosses his face"), "silhouette" 10 (backlit in a doorway), "faint" 6 (a faint smell),
# "pitch" 2 (of a voice), "obscured" 2 (by the crowd). Cut to the words that say the
# light itself is poor: 11 of the 191 carry one now, and every one is real dimness ("the
# dim interior", "squinting into the dark"). The same 191 beats gave BRIGHT and NUMBERS
# nothing at all to flag.
#
# Read by hand, those 11 were 7 dim rooms and 4 that were not about the light at all:
# "stained dark by countless spills", "hands stained dark from the tannins", and two
# squints — one at the horizon, one "against the pale morning light", which is a squint
# at too MUCH light. "squint" left the family; a colour "dark" is blanked before matching
# (`_COLOUR`). After both: 7 of 191, all dim rooms.
_SIGHT = re.compile(
    r"\b(?:dark|darker|darkest|darkness|darkened|gloom\w*|murk\w*|dim|dimly|dimness|"
    r"dimmer|unseen|unlit|lightless|pitch[- ](?:black|dark)|blackness|blind(?:ly|ed)?|"
    r"half[- ](?:seen|glimpsed|light)|moonlight|moonlit|starlight|starlit|"
    r"(?:barely|hardly|scarcely) (?:see|make out|tell|glimpse)\w*|make out|"
    r"can(?:no|')t see|could(?:n't| not) see|hard to see|no light|poor light|"
    r"(?:grey|gray) shapes?|the night swallows|swallowed by the night)\b", re.I)
_COLOUR = re.compile(
    r"\b(?:(?:stained|dyed|painted|tanned|weathered|burnished|oiled|turned|gone) dark"
    r"|dark(?:-| )(?:eyed|haired|skinned|eyes|hair|skin|brows?|beard|wood|stain|red|"
    r"brown|green|blue|grey|gray|cloak|leather|wool|cloth|robes?|coat|ink|ale|wine|"
    r"bread|patch|patches|stains?|smudges?))\b", re.I)


class _Sight:
    """`SIGHT.search(n)`, with a colour's "dark" blanked first (`_COLOUR`)."""

    pattern = _SIGHT.pattern

    @staticmethod
    def search(text: str):
        return _SIGHT.search(_COLOUR.sub(" ", str(text or "")))

    @staticmethod
    def finditer(text: str):
        return _SIGHT.finditer(_COLOUR.sub(" ", str(text or "")))


SIGHT = _Sight()

# A blow, so the miss is shown WITH the light rather than beside it.
STRIKE = re.compile(
    r"\b(?:swing\w*|swung|blows?|strik\w*|struck|slash\w*|stab\w*|thrust\w*|lung\w*|"
    r"cuts?|cutting|miss\w*|wide|empty air|nothing there|blades?|swords?|axes?|clubs?|"
    r"saps?|daggers?|knives|knife|fists?|punch\w*|arrows?|bolts?|shots?|shoot\w*|"
    r"flasks?|aim\w*|hits?|hitting|attack\w*|spear\w*|mace\w*|hammer\w*|staff)\b", re.I)

# The blow FAILING, which a miss the light decided must be shown with. Live, 2026-10-06
# (a night fight on the great square, the player's swing lost to the dim light): "The
# rapier's tip whistles through the air, missing his ribs by a hair's breadth as he ducks"
# — no gloom in it — passed on a later sentence, "his eyes narrowed in the dim light, the
# heavy sap held ready for a second strike", because "strike" was a blow word. A sentence
# that shows the light swallowing the miss has to say the miss.
MISSED = re.compile(
    r"\b(?:miss\w*|wide|empty air|thin air|nothing|finds? no\w*|lost|vanish\w*|"
    r"glanc\w*|whistles? past|past (?:him|her|it|them|you)|where \w+ (?:was|were|had been)|"
    r"not quite where)\b", re.I)

# What lights a scene the engine holds dark. A closed list: "light" alone is in half the
# sentences of any night scene ("the last of the light"), and "sun" alone is in every
# "the sun has long since set".
BRIGHT = re.compile(
    r"\b(?:sunlight|sunshine|sunlit|sun-drenched|sun-baked|daylight|broad day|"
    r"bright(?:ly)? lit|well[- ]lit|bright light|brilliant light|glar(?:e|es|ing)|"
    r"dazzl\w*|blazing sun|midday sun|noon sun|the sun (?:beats|blazes|shines|glints))\b",
    re.I)

# The mechanics on the page: the tell's words, or any percentage.
NUMBERS = re.compile(r"\bmiss chance\b|\b\d+\s*(?:%|per ?cent)", re.I)

# The tell a light miss writes (`Engine._concealment_of` → the attack loop and the thrown
# flask): "<who> finds nothing there — dim light, 20% miss chance (14)."
_LIGHT_MISS = re.compile(
    r"(?P<who>[^.()]*?)\s+finds nothing there\s*[—–-]+\s*(?P<why>dim light|darkness)", re.I)

_YOU = re.compile(r"\b(?:you|your|yours|yourself)\b", re.I)
_LEADS = re.compile(r"\s*(?:you|your)\b", re.I)


# --- the one derivation of what the player can see -------------------------------------

def sight(scene) -> dict | None:
    """The player's sight this moment, or None when the light is not poor for them.

    {"level": "dim" | "dark", "why": words for the reason, "lights": [(name, carrier
    name), ...]} — read off the engine (`Scene.light_at` at the player's square as the
    player sees it, low-light vision folded in; darkvision answers "not poor" when it
    has any range, since the near ground is what a fight is fought in). Read by
    `prompts.light_now` and by this check, so the brief and the check cannot disagree."""
    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    if pc is None or not hasattr(scene, "light_at"):
        return None
    try:
        level = scene.light_at(scene.positions.get(pc.ref), viewer=pc)
        ambient = scene.ambient_light()
        eyes = pc.eyes() if hasattr(pc, "eyes") else {}
    except Exception:       # noqa: BLE001 — a scene the light model cannot read owes nothing
        return None
    if level not in ("dim", "dark") or int(eyes.get("darkvision") or 0):
        return None
    from rules import places as places_mod

    at = str(getattr(scene, "at", "") or "")
    if ambient == "dark" and places_mod.terrain_of(at) == "underground":
        why = "underground, with nothing lit"
    elif ambient == "dark":
        why = "nothing lit"
    else:
        why = "night under the open sky, starlight and moonlight only"
    lights = []
    for _sq, _r, _rr, name in (scene.lights() if hasattr(scene, "lights") else ()):
        lights.append(name)
    return {"level": level, "why": why, "lights": lights}


def _fighting(ctx) -> bool:
    if getattr(ctx.scene, "in_encounter", False):
        return True
    return any(field(o, "op") == "attack" for o in ctx.outcomes)


def _searching(ctx) -> bool:
    return any(field(o, "op") == "check"
               and "perception" in str(field(o, "tell") or "").lower()
               for o in ctx.outcomes)


def light_misses(tells) -> list[dict]:
    """Each swing the light's miss chance decided this beat: {"who", "why"} from the
    tell's own words ("the thug finds nothing there — dim light")."""
    out = []
    for t in tells or ():
        for m in _LIGHT_MISS.finditer(str(t or "")):
            who = " ".join(m.group("who").split()).strip(" ,;:")
            # The tell's sentence may follow another in the same string: keep its last
            # clause, the attacker's name.
            who = re.split(r"[.!?]\s+", who)[-1]
            out.append({"who": who, "why": m.group("why").lower()})
    return out


def _miss_shown(text: str) -> bool:
    return any(SIGHT.search(n) and MISSED.search(n) for _w, n in page_sentences(text))


def _gloom_shown(text: str) -> bool:
    return any(SIGHT.search(n) for _w, n in page_sentences(text))


def _lit_by_the_scene(narration: str, lights: list[str]) -> bool:
    low = narration.lower()
    words = {w for name in lights for w in re.findall(r"[a-z]{4,}", str(name).lower())}
    words |= {"torch", "lantern", "lamp", "sunrod", "fire", "flame", "flames", "candle",
              "brazier", "campfire"}
    return any(re.search(rf"\b{re.escape(w)}\w*", low) for w in words)


def _contradictions(text: str, seen: dict | None, misses: list[dict]) -> list[str]:
    out = []
    for w, n in page_sentences(text):
        if NUMBERS.search(n) and (seen or misses):
            out.append(w)
        elif seen and BRIGHT.search(n) and not _lit_by_the_scene(n, seen["lights"]):
            out.append(w)
    return out


def _anchor(text: str, *, blow: bool) -> str:
    """The sentence the rewrite folds the light into: on a miss, the first narration
    sentence about a blow; otherwise the first about the player, leading with them if
    one does — never the hand-back question and never one that already carries it."""
    open_ = [(w, n) for w, n in page_sentences(text)
             if n.strip() and not w.rstrip().endswith("?") and not SIGHT.search(n)
             and not NUMBERS.search(n)]
    if blow:
        hits = ([w for w, n in open_ if STRIKE.search(n) and MISSED.search(n)]
                or [w for w, n in open_ if STRIKE.search(n)])
        if hits:
            return hits[0]
    led = [w for w, n in open_ if _LEADS.match(n)]
    about = [w for w, n in open_ if _YOU.search(n)]
    for w in (*led, *about, *(w for w, _n in open_)):
        return w
    return ""


def _owed(ctx, text: str) -> tuple[dict | None, list[dict]]:
    """(the player's poor sight when this beat owes it, the light misses it owes)."""
    if not str(text or "").strip():
        return None, []
    misses = light_misses(ctx.tells)
    seen = None
    if ctx.door == "turn" and (_fighting(ctx) or _searching(ctx)):
        seen = sight(ctx.scene)
    return seen, misses


def _words(level: str) -> str:
    return "pitch dark" if level == "dark" else "dim, the light poor"


def find(ctx) -> list[Finding]:
    text = ctx.text
    seen, misses = _owed(ctx, text)
    if not seen and not misses:
        return []
    out: list[Finding] = []
    bad = _contradictions(text, seen, misses)
    if bad:
        level = (seen or {}).get("level") or ("dark" if any(m["why"] == "darkness"
                                                             for m in misses) else "dim")
        out.append(Finding(
            "light-contradicted",
            f"the engine holds it {level} here; the page says otherwise or prints the "
            f"rule: {bad[0][:90]!r}",
            (f"It is {_words(level)} here — nobody can see well. Rewrite the sentence so "
             f"the light is as poor as it is: no sun, no glare, no bright light, and no "
             f"numbers or game terms. Keep everything else it says."),
            weight=2, sentences=tuple(bad)))
    if misses and not _miss_shown(text):
        m = misses[0]
        dark = m["why"] == "darkness"
        where = _anchor(text, blow=True)
        out.append(Finding(
            "light-miss-unshown",
            f"{m['who']}'s blow was lost to the {'dark' if dark else 'dim light'} and the "
            f"page does not show it",
            (f"{m['who']} swung at a target that could barely be seen in the "
             f"{'darkness' if dark else 'gloom'}, and the blow found nothing. Rewrite the "
             f"sentence so it shows that — the shape lost in the "
             f"{'dark' if dark else 'poor light'}, the blow going wide into empty air — "
             f"keeping who did what. No numbers."),
            weight=2, sentences=(where,) if where else ()))
    elif seen and not _gloom_shown(text):
        where = _anchor(text, blow=_fighting(ctx))
        out.append(Finding(
            "light-left-off-the-page",
            f"a {'fight' if _fighting(ctx) else 'search'} in {seen['level']} light "
            f"({seen['why']}) and the page shows nothing of it",
            (f"It is {_words(seen['level'])} here ({seen['why']}): the player can barely "
             f"make out shapes. Rewrite the sentence so it ALSO shows how little they can "
             f"see — keeping everything else it says. No numbers."),
            weight=1, sentences=(where,) if where else ()))
    return out


# The backstop's lines. Every one carries a SIGHT word and a MISSED word where it is a
# miss, so `find` recognises its own backstop. No names: an authored line that names
# somebody names the wrong one sooner or later.
POOL: dict[str, tuple[str, ...]] = {
    "mine:dim": (
        "In the poor light you can barely make out where they stand, and your blow finds "
        "nothing but empty air.",
        "The gloom swallows the shape you were aiming at, and your strike goes wide.",
        "You swing at a shape that is not quite where the dim light said it was, and meet "
        "only empty air.",
    ),
    "mine:dark": (
        "In the dark you strike at where a sound was, and there is nothing there.",
        "You cannot see your target at all; your blow cuts through nothing but blackness.",
        "Blind in the dark, you swing at a shape you only guessed at, and miss.",
    ),
    "theirs:dim": (
        "A blow comes at you out of the gloom and goes wide, finding only the place you "
        "stood a moment before.",
        "In the poor light the strike meant for you goes wide, aimed at a shape it could "
        "barely make out.",
        "Something swings at you from the shadows and misses, lost in the dim.",
    ),
    "theirs:dark": (
        "A blow whistles past you in the dark, aimed at where you were.",
        "In the blackness the strike meant for you finds nothing.",
        "Somebody swings at you blind in the dark, and misses.",
    ),
    "gloom:dim": (
        "The light is poor; shapes blur at the edge of sight, and you can barely make out "
        "who stands where.",
        "Everything past arm's reach is grey shapes and shadow in the dim.",
        "You squint into the gloom, and faces are lost to it beyond a few paces.",
    ),
    "gloom:dark": (
        "It is dark, near pitch black, and you can barely see your own hands.",
        "In the darkness you fight by sound and by touch more than by sight.",
        "There is no light to speak of; the dark presses close on every side of you.",
    ),
}


def _pick(ctx, cell: str) -> str:
    from gm import narration as narration_mod

    pool = POOL[cell]
    return pool[narration_mod.least_recently_used(getattr(ctx.scene, "said", None),
                                                  f"light:{cell}", len(pool))]


def _the_player_swung(ctx, who: str) -> bool:
    pc = ctx.scene.pc() if hasattr(ctx.scene, "pc") else None
    name = str(getattr(pc, "name", "") or "").lower()
    who = who.lower()
    return bool(name) and (who == name or who.endswith(" " + name) or name in who)


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    from ._page import cut

    notes: list[str] = []
    seen, misses = _owed(ctx, text)
    if not seen and not misses:
        return text, notes
    for bad in _contradictions(text, seen, misses):
        if bad in text and len(page_sentences(text)) > 1:
            text = cut(text, [bad])
            notes.append(f"light contradicted: cut {bad[:60]!r}")
    from gm import narration as narration_mod

    if misses and not _miss_shown(text):
        m = misses[0]
        side = "mine" if _the_player_swung(ctx, m["who"]) else "theirs"
        cell = f"{side}:{'dark' if m['why'] == 'darkness' else 'dim'}"
        line = _pick(ctx, cell)
        text = narration_mod.put_before_the_hand_back(text, line)
        notes.append(f"a blow lost to the light left off the page: wrote {line[:60]!r}")
    elif seen and not _gloom_shown(text):
        cell = f"gloom:{seen['level']}"
        line = _pick(ctx, cell)
        text = narration_mod.put_before_the_hand_back(text, line)
        notes.append(f"poor light left off the page: wrote {line[:60]!r}")
    return text, notes


def authored_in(text: str) -> list[str]:
    """The backstop's own sentences on this page, for `GMAgent.last_added` (D4)."""
    return [line for pool in POOL.values() for line in pool if line in str(text or "")]
