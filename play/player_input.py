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

# A thing declared into existence, with the player as the subject of the sentence.
#
# Reported 2026-09-17: "I use my godly powers to will the missing transport of refined
# salt to appear before me". `gm/judgement.py` now refuses the *claimed faculty*, and
# that fix has a one-word bypass — "I use my **rope** to make a wagon of salt appear"
# names nothing supernatural, so no faculty door opens and the model's `spawn` puts the
# cart in the market. Found by the player who reported the original, asking what else
# would work.
#
# The exemption above — anything with a nominative "I" is the player's to say — is right
# for *actions*, and the file says why: "I find a chest containing five thousand gold
# pieces" is allowed through because the engine is what makes sure no chest exists. That
# reasoning does not reach this shape. "I make a wagon of salt appear" is not an attempt
# at anything the engine can adjudicate; the sentence's whole content is that the world
# now contains something it did not. There is no roll to fail.
#
# Deliberately NOT here: summon, conjure, manifest. Those are spell vocabulary, and a
# summoner is entitled to type them — the sheet decides whether they have it, which is
# `gm/judgement.py`'s job and not a regex's. What this owns is fiat: a wagon appearing
# because it was willed to.
FIAT_CREATION = re.compile(
    r"\b(?:make|makes|making|have|has|cause|causes|will|wills|willing|"
    r"command|commands|order|orders|bring|brings|force|forces)\s+"
    # A determiner is required, and it is what keeps "I will appear calm" out: the verb
    # has to be followed by the *thing*, not by the appearing.
    r"(?:the|a|an|some|that|this|my|their|his|her|its|every|all|\d+)\s+"
    r"[\w\s,'\-]{0,50}?"
    r"\b(?:appear|appears|materiali[sz]e|materiali[sz]es|exist|exists)\b"
    r"|\binto\s+(?:being|existence)\b"
    r"|\bout\s+of\s+(?:thin\s+air|nowhere)\b",
    re.I)

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
        # Dialogue the player's character speaks is theirs, quotes and all. Hoisted
        # above the first-person exemption because the fiat check below has to read a
        # sentence the player is the subject of, and a boast inside quotation marks —
        # "I tell him I will make a dragon appear" — is still only a boast.
        bare = _QUOTED.sub(" ", s)
        if FIAT_CREATION.search(bare):
            return Verdict(
                ok=False,
                offending=s,
                hint=(
                    f"{s.rstrip('.')} — whether that exists is the GM's to decide, and "
                    f"there is no roll that makes it so. Say what your character does "
                    f"about the thing you want: search for it, ask after it, go where "
                    f"it would be."
                ),
            )
        if FIRST_PERSON.search(s):
            continue
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
