"""What the player is entitled to say.

The player controls one character. The GM controls the world. So "I turn and fight" is a
turn, and "two guild bravos come round the corner" is not — that is the player deciding
what exists, which is the GM's job and the reason the GM has a whole world to answer
from.

This was got wrong for a while and the mistake ran deep: a worked example in
`gm/prompts.py` used exactly that shape, and `gm/judgement.py` read the player's sentence
for how many enemies to create. The app was not merely accepting the wrong input, it was
teaching it and then honouring it.

The guard is deliberately gentle. It does not consume the turn or lose what was typed —
it says which half was the player's to declare and lets them rephrase.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Only the nominative forms. The first cut of this exempted any sentence containing
# me/my/mine/us/our — and an adversarial audit walked straight through the gap: "Two
# dragons land beside ME and swear to obey MY every command" and "The stallholder
# decides she loves ME and gives ME her entire stock for free" both passed, because a
# world-declaration with the player as its *object* still mentions them. Whose sentence
# it is turns on who is doing something, and that is the subject, not the beneficiary.
FIRST_PERSON = re.compile(r"\b(i|i'm|i'd|i'll|i've|we|we're|we'd|we'll|we've)\b", re.I)

# Things happening in the world, told rather than asked. The verb list is what a player
# reaches for when they narrate an arrival, an NPC's action — or, the audit added, an
# NPC's generosity: decides, gives, swears, grants came from the lines that got through.
WORLD_VERB = re.compile(
    r"\b(comes?|coming|steps?|stepping|walks?|appears?|arrives?|emerges?|enters?|"
    r"rounds?|rushes|charges?|attacks?|swings?|draws?|grabs?|shouts?|yells?|says?|"
    r"falls?|drops?|opens?|closes?|slams?|blocks?|leaps?|jumps?|lunges?|turns?|"
    r"stands?|sits?|dies?|flees?|runs?|bursts?|slips?|throws?|lands?|landing|"
    r"swoops?|descends?|kneels?|bows?|decides?|deciding|gives?|giving|hands?|"
    r"handing|offers?|agrees?|swears?|grants?|names?|obeys?|surrenders?)\b",
    re.I,
)

# A sentence that starts by naming somebody or something other than the player.
# "everyone"/"nobody" joined after "Everyone in this town instantly dies" opened a
# sentence no pattern owned.
SUBJECT = re.compile(
    r"^\s*(the|a|an|two|three|four|five|six|several|some|a few|another|one of|"
    r"his|her|their|its|everyone|everybody|nobody|no one|all of|each of|\d+)\b",
    re.I,
)

_SENTENCE = re.compile(r"[^.!?]+[.!?]?")
_QUOTED = re.compile(r"[\"“”][^\"“”]*[\"“”]")


@dataclass
class Verdict:
    ok: bool
    offending: str = ""
    hint: str = ""


def check(text: str) -> Verdict:
    """Is this the player describing what their character does?

    Conservative: a sentence only counts against the player when it names something
    other than them *and* has them nowhere in it *and* asserts an event. Anything with
    "I" in it is theirs to say, and a question is asking rather than declaring.
    """
    for sentence in _SENTENCE.findall(text or ""):
        s = sentence.strip()
        if len(s) < 8 or s.endswith("?"):
            continue
        if FIRST_PERSON.search(s):
            continue
        # Dialogue the player's character speaks is theirs, quotes and all.
        bare = _QUOTED.sub(" ", s)
        if not SUBJECT.match(bare) or not WORLD_VERB.search(bare):
            continue
        return Verdict(
            ok=False,
            offending=s,
            hint=(
                f"{s.rstrip('.')} — that part is the GM's to decide. Say what your "
                f"character does and let the world answer: “I turn to face whoever is "
                f"behind me”, not who is there or what they do."
            ),
        )
    return Verdict(ok=True)
