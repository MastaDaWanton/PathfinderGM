"""English articles and plurals, the one copy.

Twenty-eight copies of `"an" if word[:1] in "aeiou" else "a"` lived across rules/, gm/
and play/ until 2026-11-13, when the encounter budget began sending groups and a live
road check printed "an unicorn" and "three astomois". The article is chosen by the sound,
not the letter (a unicorn, a one-eyed giant, an hour); the plural leaves a name that is
already plural alone. No dependency: `inflect` is not bundled and these are the cases the
bestiary and the world's nouns actually reach.
"""
from __future__ import annotations

# Spelled with a vowel, said with a consonant: "a unicorn", "a one-eyed", "a European".
_CONSONANT_SOUND = ("uni", "use", "usu", "uti", "ura", "ure", "uro", "eu", "ewe", "one",
                    "once", "ubiq", "ufo", "uvu", "uk")
# Spelled with a consonant, said with a vowel: "an hour", "an honest".
_VOWEL_SOUND = ("hour", "honest", "honor", "honour", "heir")
# Already plural, or the same in both: "three astomoi", "two lizardfolk", "four sheep".
_SAME = ("folk", "sheep", "deer", "fish", "people", "oi", "ae", "kin", "swine", "moose",
         "bison", "elk", "aurochs", "series", "species")


def article(word) -> str:
    """ "a" or "an" for the word that follows it."""
    w = str(word or "").strip().lower()
    if w.startswith(_VOWEL_SOUND):
        return "an"
    if w.startswith(_CONSONANT_SOUND):
        return "a"
    return "an" if w[:1] in "aeiou" else "a"


def a(noun) -> str:
    """ "a wolf", "an owl", "a unicorn"."""
    return f"{article(noun)} {noun}"


def plural(noun: str) -> str:
    """English plural of a noun's last word: wolf → wolves, lynx → lynxes, harpy →
    harpies, watchman → watchmen, astomoi and lizardfolk unchanged."""
    words = str(noun or "").split()
    if not words:
        return str(noun or "")
    last = words[-1]
    low = last.lower()
    if low.endswith(_SAME):
        pl = last
    elif low.endswith("man") and not low.endswith(("human", "shaman", "talisman")):
        pl = last[:-3] + "men"
    elif low.endswith("fe"):
        pl = last[:-2] + "ves"
    elif low.endswith("f") and not low.endswith(("ff", "oof", "ief")):
        pl = last[:-1] + "ves"
    elif low.endswith(("s", "x", "z", "ch", "sh")):
        pl = last + "es"
    elif low.endswith("y") and low[-2:-1] not in "aeiou":
        pl = last[:-1] + "ies"
    else:
        pl = last + "s"
    return " ".join(words[:-1] + [pl])
