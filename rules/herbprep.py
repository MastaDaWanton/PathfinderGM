"""What has to happen to an ingredient before it can be used, and what that costs.

The crafting bench could already brew, but it treated every ingredient as equally
ready: a shelled nut, a volatile resin and a handful of leaves all went into the pot
the same way. The author's rules say otherwise, and they are rules about *states* — a
thing is raw, or extracted, or neutralised, or ground, or preserved — with each step
allowed or refused per ingredient and each one moving the potency.

**States and the order they come in.** Extraction first, because a thing still in its
shell cannot be neutralised or ground or mixed. Neutralising second, and only for the
volatile, because grinding one of those without it is the accident the rule exists to
prevent. Grinding third. Preservation is not a step in that line at all — it is
something done to a *fresh* thing to stop the clock, and it is the only step that costs
potency rather than adding it.

**Potency is the whole economy.** Grinding and brewing each raise it, and how much
depends on the herbalist: a novice grinding a leaf gets less out of it than a master
does. Preserving lowers it, which is the price of not losing the material entirely.

**Freshness is a clock, not a flag.** An animal part has 48 hours before it is refuse;
a plant has a week. Preserved, neither spoils. The numbers are the author's and live in
one place so the bench, the sheet and the ingredient editor cannot disagree.

Everything here reads flags off the ingredient, and every flag has a default that makes
an ingredient written before this module behave exactly as it did: ordinary leaves that
grind, mix, brew and keep for a week. Nothing already authored becomes wrong.
"""
from __future__ import annotations

from dataclasses import dataclass

# Hours before unpreserved material is refuse. The author's numbers.
ANIMAL_HOURS = 48
PLANT_HOURS = 24 * 7

# What each step does to potency, before the herbalist's own skill is added.
GRIND_POTENCY = 0.25
BREW_POTENCY = 0.25
PRESERVE_POTENCY = -0.20

# Per level of the herbalism track, on top of the base. A master gets more out of the
# same leaf, which is what levelling a craft is for.
PER_LEVEL = 0.05

STATES = ("raw", "extracted", "neutralised", "ground", "preserved")


@dataclass(frozen=True)
class Prep:
    """One ingredient's processing rules, with defaults that preserve old behaviour."""
    needs_extraction: bool = False      # in a shell, a pod, a gland
    volatile: bool = False              # must be neutralised before grinding
    can_grind: bool = True
    mix_raw: bool = True                # or only once ground
    brew_raw: bool = True               # or only once ground
    animal: bool = False                # 48 hours rather than a week
    liquid: bool = False                # a sap, an oil, a gall — already pourable

    @classmethod
    def of(cls, ingredient) -> "Prep":
        """Read from an ingredient object or a plain dict, either way."""
        def flag(name, default):
            if isinstance(ingredient, dict):
                got = ingredient.get(name, default)
            else:
                got = getattr(ingredient, name, default)
            if isinstance(got, str):
                return got.strip().lower() in ("yes", "true", "1")
            return bool(got) if got is not None else default

        kind = (ingredient.get("kind") if isinstance(ingredient, dict)
                else getattr(ingredient, "kind", "")) or ""
        return cls(
            needs_extraction=flag("needs_extraction", False),
            volatile=flag("volatile", False),
            can_grind=flag("can_grind", True),
            mix_raw=flag("mix_raw", True),
            brew_raw=flag("brew_raw", True),
            # An ingredient that never said so is an animal part if its kind says it is.
            animal=flag("animal", "monster part" in str(kind).lower()),
            # And is a liquid if its own name says it is. Detected rather than tagged
            # because 162 ingredients would otherwise all need a second pass to teach
            # the corpus something its names already say; an explicit tag still wins.
            liquid=flag("liquid", looks_liquid(
                (ingredient.get("name") if isinstance(ingredient, dict)
                 else getattr(ingredient, "name", "")) or "", kind)),
        )


# Words that mean a thing arrives already pourable. Whole words only: "Sapwood" is not a
# sap and "Oilseed" is a seed. Kept deliberately short — over-detecting here would hand
# distillation back the permissiveness this list exists to take away.
LIQUID_WORDS = (
    "sap", "oil", "essence", "gall", "blood", "ichor", "venom", "nectar",
    "milk", "juice", "brine", "resin", "tears", "honey", "dew", "wine",
    "water", "extract", "syrup", "bile", "serum", "tincture", "tea",
)


def looks_liquid(name: str, kind: str = "") -> bool:
    """Whether an ingredient's own name says it arrives as a liquid.

    Read off the name rather than tagged, because the corpus already says it — "Cotsbalm
    Sap", "Banshee Wail Essence", "Hydra Gall". A tag on the ingredient still wins, so
    anything the names get wrong is one edit away in the ingredient editor.
    """
    import re

    said = f"{name} {kind}".lower()
    return any(re.search(rf"\b{w}s?\b", said) for w in LIQUID_WORDS)


def spoils_after(prep: Prep) -> int:
    """Hours before this is refuse, unpreserved."""
    return ANIMAL_HOURS if prep.animal else PLANT_HOURS


def is_spoiled(prep: Prep, hours_old: int, preserved: bool = False) -> bool:
    return not preserved and int(hours_old or 0) >= spoils_after(prep)


# What preserving takes. Salt by any of the names a shelf might use for it, because the
# player buys "a bag of salt" and the goods table has never heard of an id.
SALT = ("salt", "rock salt", "sea salt", "curing salt", "saltpetre", "saltpeter")


def has_salt(actor) -> bool:
    """Whether this character is carrying something they could cure with."""
    carried = list(getattr(actor, "goods", {}) or {}) + \
        list(getattr(actor, "inventory", {}) or {})
    return any(any(s in str(name).lower() for s in SALT) for name in carried)


def preserve_automatically(actor, prep: Prep) -> tuple[bool, float, str]:
    """Whether this is cured on the spot, and what it costs.

    "preservation can be automatic if i have salt" — so it is not an action the player
    has to remember on the turn they pick a gland up, which is the turn they are least
    likely to be thinking about the forty-eight hours that start now. Carrying salt is
    the whole condition; the potency it costs is the price, and it is charged once.
    """
    if not has_salt(actor):
        return False, 0.0, ("no salt — this keeps for "
                            f"{spoils_after(prep)} hours and then it is refuse")
    return True, potency_change("preserve"), "preserved with salt"


def can(step: str, prep: Prep, state: str = "raw") -> tuple[bool, str]:
    """Whether a step is allowed now, and the reason when it is not.

    The reason is the whole point. "You cannot grind this" teaches nothing; "this is
    volatile — neutralise it first" is the rule, and a player who reads it once knows
    it for every volatile thing afterwards.
    """
    step, state = str(step).lower(), str(state or "raw").lower()

    if prep.needs_extraction and state == "raw" and step != "extract":
        return False, "it has to be extracted before anything else can be done with it"

    if step == "extract":
        if not prep.needs_extraction:
            return False, "there is nothing to extract it from"
        if state != "raw":
            return False, "it has already been extracted"
        return True, ""

    if step == "neutralise":
        if not prep.volatile:
            return False, "it is not volatile; there is nothing to neutralise"
        if state == "neutralised":
            return False, "it is already neutralised"
        return True, ""

    if step == "grind":
        if not prep.can_grind:
            return False, "it cannot be ground"
        if state == "ground":
            return False, "it is already ground"
        if prep.volatile and state != "neutralised":
            return False, "it is volatile — neutralise it before grinding"
        return True, ""

    if step == "mix":
        if state == "ground" or prep.mix_raw:
            return True, ""
        return False, "it can only be mixed once it has been ground"

    if step == "brew":
        if state == "ground" or prep.brew_raw:
            return True, ""
        return False, "it can only be brewed once it has been ground"

    if step == "preserve":
        return True, ""

    return False, f"{step!r} is not something you can do to an ingredient"


def potency_change(step: str, herbalism_level: int = 0) -> float:
    """What a step does to potency. Negative for preservation, which is its price."""
    step = str(step).lower()
    bonus = max(0, int(herbalism_level or 0)) * PER_LEVEL
    if step == "grind":
        return GRIND_POTENCY + bonus
    if step == "brew":
        return BREW_POTENCY + bonus
    if step == "preserve":
        return PRESERVE_POTENCY
    return 0.0


def after(step: str, state: str = "raw") -> str:
    """The state a step leaves the ingredient in."""
    step, state = str(step).lower(), str(state or "raw").lower()
    return {"extract": "extracted", "neutralise": "neutralised",
            "grind": "ground"}.get(step, state)


# --- infusions ----------------------------------------------------------------------

def can_infuse(base, addition, state: str = "raw") -> tuple[bool, str]:
    """Whether this can go into an existing tincture.

    "Infusions are only possible on already crafted tinctures, they can be infused with
    other tinctures or brews, ground or mixed herbs, raw herbs as long as the raw herbs
    could be brewed raw, and some herbs that are volatile need extraction."

    So the base has to be finished work, and the addition has to be in a state the
    tincture can actually take up — which for a raw herb is the same question as
    whether it could have been brewed raw in the first place.
    """
    base_kind = str((base or {}).get("kind", "") if isinstance(base, dict)
                    else getattr(base, "kind", "")).lower()
    if "tincture" not in base_kind and not (
            base.get("crafted") if isinstance(base, dict)
            else getattr(base, "crafted", False)):
        return False, "an infusion goes into a tincture that has already been crafted"

    prep = Prep.of(addition)
    state = str(state or "raw").lower()

    if prep.needs_extraction and state == "raw":
        return False, "it has to be extracted before it can be infused"
    if state in ("ground", "extracted", "neutralised"):
        return True, ""
    if prep.brew_raw:
        return True, ""
    return False, ("a raw herb can only be infused if it could be brewed raw; "
                   "grind it first")
