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
#
# THE RETIRED CHAIN BENCH'S NUMBERS. The table's step bench reads its multipliers from
# content/rules/herbal-methods.json (grind x1.1, brew x1.0 with the decoction's x1.25 on
# the product, plan §6), and the Herbalist level no longer scales potency: it raises the
# quality ceiling and the check instead. These stay only for `crafting.preview`, the old
# chain reader kept as a library; nothing a player clicks reaches them.
GRIND_POTENCY = 0.25
BREW_POTENCY = 0.25
PRESERVE_POTENCY = -0.20

# Per level of the herbalism track, on top of the base. A master gets more out of the
# same leaf, which is what levelling a craft is for.
PER_LEVEL = 0.05

# The ingredient states (docs/herbalism-contracts.md §2). "dried" is the step bench's
# Dry; "preserved" left the list with the Preserve method — salting is a flag on the
# satchel (`Actor.preserved`), not a state an ingredient is worked into.
STATES = ("raw", "extracted", "neutralised", "ground", "dried")


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


# What preserving takes: curing salt, read by MATERIAL ID AND DOCUMENT through the one door
# (`materials.is_salt`: `curing-salt`, or a document saying `"salt": true`), never by a
# word in a name. Until 2026-10-08 this matched name fragments ("salt", "rock salt",
# "saltpetre") over everything carried — the shape law 1 refuses (leatherworking plan §6),
# and the alchemist's "salt" kind (vitriol, brimstone) is no curing salt at all. And it
# cost nothing: lanes U5-U7 found a hide carried with a minute was marked salted for free
# whenever any salt was in the pack, against the owner's "salt costs salt" (answer 8,
# 2026-10-08). One reader now, for herbalism's animal parts and the leatherworker's hides
# alike: `salt_measures` counts, `spend_salt` spends, `preserve_on_pick` decides.


def _is_salt_id(key: str) -> bool:
    try:
        from . import materials

        return bool(materials.is_salt(str(key)))
    except Exception:          # noqa: BLE001 - no door (a bare test double) is no salt
        return str(key).strip().lower() == "curing-salt"


def salt_ids(actor) -> list[str]:
    """The satchel keys that hold curing salt, by id (a counter's purchase lands in
    `inventory` under its material id, `goods.deliver`)."""
    return [k for k, n in sorted((getattr(actor, "inventory", {}) or {}).items())
            if int(n or 0) > 0 and _is_salt_id(k)]


def salt_measures(actor) -> int:
    """How many measures of curing salt this character carries."""
    inv = getattr(actor, "inventory", {}) or {}
    return sum(int(inv.get(k, 0) or 0) for k in salt_ids(actor))


def spend_salt(actor, n: int) -> int:
    """Spend up to `n` measures, curing salt first by id order. Returns how many were spent."""
    left, spent = max(0, int(n)), 0
    for key in salt_ids(actor):
        if left <= 0:
            break
        took = actor.spend(key, left) if hasattr(actor, "spend") else 0
        spent += int(took or 0)
        left -= int(took or 0)
    return spent


def has_salt(actor) -> bool:
    """Whether this character is carrying curing salt (herbalism's callers, unchanged)."""
    return salt_measures(actor) > 0


def salt_needed(key: str, count: int = 1) -> int:
    """Measures it costs to salt `count` of this as it is picked: a leatherworker's hide one
    per hide unit (the Salt method's `salt_per_unit`), a herbalist's animal part
    `animal_part_salt` each (content/rules/harvest.json), anything else — a plant — nothing:
    the owner's answer named hides and animal parts, and a pressed leaf in a salted pack
    stays the free preservation it always was."""
    import math

    key = str(key or "").strip().lower()
    try:
        from . import materials

        doc = materials.get(key)
    except Exception:          # noqa: BLE001
        doc = None
    if doc and str(doc.get("kind") or "") == "hide":
        from . import leatherworker as lw

        per = float((lw.method_row("salt") or {}).get("salt_per_unit", 1) or 1)
        units = lw.units_of_size(lw.hide_size(key))
        return int(math.ceil(units * per)) * max(0, int(count))
    try:
        from . import ingredients

        ing = ingredients.all_ingredients().get(key)
    except Exception:          # noqa: BLE001
        ing = None
    if ing is not None and Prep.of(ing).animal:
        try:
            from . import harvest

            each = int(harvest.rules().get("animal_part_salt", 1))
        except Exception:      # noqa: BLE001
            each = 1
        return each * max(0, int(count))
    return 0


def preserve_on_pick(actor, key: str, count: int = 1) -> bool:
    """Whether what was just picked is salted, spending what that costs (`salt_needed`).
    Not enough salt for all of it salts none of it and spends nothing: the satchel keeps one
    flag per pile, so a half-salted pile cannot be said."""
    if not has_salt(actor):
        return False
    need = salt_needed(key, count)
    if need <= 0:
        return True
    if salt_measures(actor) < need:
        return False
    return spend_salt(actor, need) >= need


def preserve_automatically(actor, prep: Prep) -> tuple[bool, float, str]:
    """Whether this is cured on the spot, and what it costs.

    "preservation can be automatic if i have salt" — so it is not an action the player
    has to remember on the turn they pick a gland up, which is the turn they are least
    likely to be thinking about the forty-eight hours that start now. Carrying curing salt
    is the condition; the potency it costs is the price, and it is charged once. (The salt
    itself is spent where the thing is picked, `preserve_on_pick`.)
    """
    if not has_salt(actor):
        return False, 0.0, ("no salt: this keeps for "
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
            # A colon, not a dash: this sentence is printed on the bench's tiles, and the
            # bench's player-facing strings carry no em-dashes (UI plan §8).
            return False, "it is volatile: neutralise it before grinding"
        return True, ""

    if step == "dry":
        # The step bench's solid concentration (plan §5.3): anything solid that is out
        # of its shell. Whether it is solid is the bench's question, not the
        # ingredient's flags'.
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
        # Retired as a bench method on 2026-10-02 (plan §2). Salt in the satchel still
        # cures a fresh thing as it is picked (`preserve_automatically`), which was never
        # a step anyone took at the bench.
        return False, ("preserving is not a bench step any more: salt in your pack "
                       "cures a fresh thing as it is picked")

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
            "grind": "ground", "dry": "dried"}.get(step, state)


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
