"""Herbalism: the shelf's records and the step bench.

`Stock` is the one record every craft's output is filed as (a tea, a forged blade, a
bound ring), with the readers that bring an old save's jar up to date. Below it is the
herbalism step bench (docs/herbalism-revamp-plan.md): one method per step, each its own
roll, its strength baked into the specs the engine runs.

The module began as the old chain bench's reader — "Crafting Chains, combining multiple
methods across different tools", validated whole and rolled once. Herbalism left the
chain for the step bench on 2026-10-02, and the chain's preview, its pot-sifting rules
and its routes were deleted on 2026-11-08 (audit finding #20): nothing could reach them.
"""
from __future__ import annotations

import copy as _copy
from dataclasses import dataclass, field

from . import consumables as con
from . import effectspec
from . import inprogress
from . import ingredients as ing_mod
from . import worldclass as wc
from . import words as english


# --- concentration ------------------------------------------------------------------------
#
# RETIRED 2026-10-02 (plan §5.3): the old x2 Concentrate — two doses of a jar into one of
# twice the potency at the still — is gone. Concentration is now the step bench's Dry (a
# solid) and Reduce (a liquid), two into one at x1.5, with a DC that climbs 2n at step n;
# the numbers live in content/rules/herbal-methods.json.
#
# What the old rule got right is kept: each concentration moves the result one band
# rarer, so the ladder stays gated by level. The engine's craft check reads this constant
# to know what a concentrate was made *from*, which is why it outlives the rest.
CONCENTRATE_RARITY_STEP = 1


def _a(noun: str) -> str:
    """"an infusion", "a salve": the article a refusal reads with. Written as f"a {form}"
    the bench told players "A infusion can carry none of what this does"."""
    noun = str(noun or "")
    return english.a(noun)


@dataclass
class Stock:
    """A crafted item a character is carrying, and can craft with again.

    Held per base name and concentration rather than as a list of individual doses:
    three identical teas are a count of three, not three objects, and the crafting page
    only ever asks "how many of these do I have".
    """
    base: str
    concentration: int = 1
    tier: str = "common"
    potency: float = 1.0
    count: int = 1
    craft: str = "herbalism"
    effects: list[str] = field(default_factory=list)
    drawbacks: list[str] = field(default_factory=list)
    from_ingredients: list[str] = field(default_factory=list)
    # The same effects as `effects`, in the structured form `rules/effectspec.py`
    # defines. `effects` is what a card shows; this is what the engine can actually run.
    # Without it a crafted potion is a paragraph, and drinking one could only ever be
    # narration — which is exactly what it was.
    specs: list[dict] = field(default_factory=list)

    # --- what kind of thing this is, once four more crafts made things -----------------
    #
    # Herbalism makes one shape: a dose in a jar, which you drink, throw or paint on a
    # blade. A forge makes a sword, a tannery makes a cloak and an enchanter makes a
    # ring, and none of those is drunk. Rather than a second container per craft — four
    # more save formats, four more inventory panels — the jar learned the handful of
    # facts the other shapes need. Every field defaults to the herbalism answer, so a
    # jar saved before any of this loads unchanged and behaves identically.
    kind: str = "crafted"
    # Body slot, from `tables.SLOTS`. None for anything not worn.
    slot: str | None = None
    wearable: bool = False
    # Whether it can be consumed at all, and how. Herbalism's own jars answer this from
    # their effects (see `consumables.plan`), so the default of None means "ask the old
    # way" and a list means the maker has said outright.
    how: list[str] = field(default_factory=list)
    # A forge's output points at the base item it really is, so wielding it is the
    # weapon the rules already know rather than a new one invented at the bench.
    weapon: str | None = None
    armour: str | None = None
    masterwork: bool = False
    enhancement: int = 0
    properties: list[str] = field(default_factory=list)
    # A potion that holds a spell: the spell's own id, verified against the spell list
    # by whoever brewed it. This is the field the enchanter reads when a potion stands
    # in for knowing the spell.
    holds_spell: str | None = None
    caster_level: int | None = None
    from_materials: list[str] = field(default_factory=list)

    # --- the step bench (docs/herbalism-revamp-plan.md, contracts §3) -----------------
    #
    # Every field below defaults to "not made at the step bench", so the three places
    # rules/engine.py builds a Stock with positional base and a handful of keywords, and
    # every jar saved before the revamp, load and behave exactly as they did. `as_dict`
    # writes each one only when it is set, so an old save round-trips byte for byte.
    #
    # What the thing is now: a product or intermediate form from herbal-products.json
    # (infusion, poultice, powder, dried ...), the ingredient state it is in (raw,
    # extracted, neutralised, ground, dried), and the quality index the bench gave it.
    form: str | None = None
    state: str | None = None
    quality: int | None = None
    # A steeping jar: the world minute it is ready. The satchel shows it under Steeping
    # and the bench refuses it until then (plan §6, "steeping happens in the world").
    ready_minute: int | None = None
    # When it goes off, from the minute it was made and its form's shelf life.
    spoils_minute: int | None = None
    # Made by a method the owner retired (distill, purify, refine, preserve, catalyst
    # crafting): still usable and sellable under its old name, never worked further
    # (plan §14.2). Detected on load for jars that predate the field.
    old_method: str = ""
    # The step bench's arithmetic, kept so a later step multiplies from the authored
    # effects rather than from numbers already rounded once. `base_specs` are the effects
    # the line still carries, unscaled, each with an `origin` naming its ingredient and
    # property key; `mults` is the line's running potency, duration and drawback
    # multipliers; `specs` above is the two baked together, which is what the engine runs.
    # Baking compounds rounding when it is repeated (1d4 x1.1 then x1.5 is 1d4+3 by steps
    # and 1d4+2 from the source), which is why the source is kept.
    base_specs: list[dict] = field(default_factory=list)
    mults: dict = field(default_factory=dict)
    # The methods this line has been through, oldest first. Whether a thing was ever
    # extracted, neutralised or dried is a question the order rules ask, and a single
    # `state` can only remember the latest.
    worked: list[str] = field(default_factory=list)

    # --- the shared sections (docs/enchanting-contracts.md §8.1) ----------------------------
    #
    # Both default to None and are written by `as_dict` only when set, so every save from
    # before them reads back byte for byte. Neither is part of `id`: a thing going into or
    # out of progress, or taking a magic layer, must not re-key the entry it sits under.
    #
    # `work`: the In-progress block (rules/inprogress.py is its one door). Present while
    # the thing is in progress, working or ready; lifted when it is collected.
    work: dict | None = None
    # `magic`: the layer on a stock-kept vessel, read and written through
    # rules/magic_layer.py (lane B). Carried here untouched.
    magic: dict | None = None

    @property
    def stepped(self) -> bool:
        """Made at the step bench, rather than by the old chain or by another craft."""
        return bool(self.form or self.state or self.quality is not None
                    or self.ready_minute is not None)

    @property
    def id(self) -> str:
        slug = "".join(c if c.isalnum() else "-" for c in self.base.lower()).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        if not self.stepped:
            return f"{slug}#{self.concentration}"
        # Two Fine comfrey poultices made from different lines are different things: one
        # was ground from a dried herb and heals more. The name cannot tell them apart and
        # stacking them would hand the weaker batch the stronger one's dice, so the id
        # carries a digest of what the thing actually does. The shelf life is left out on
        # purpose: two batches of one remedy stack, and the older date is kept.
        import hashlib
        import json as _json

        sig = _json.dumps([self.form, self.state, self.quality, self.ready_minute,
                           self.specs, sorted(self.from_ingredients)],
                          sort_keys=True, default=str)
        return f"{slug}#{self.concentration}~{hashlib.md5(sig.encode()).hexdigest()[:8]}"

    @property
    def name(self) -> str:
        if self.stepped:
            # "Tier" means quality at the step bench (Crude to Flawless), so a
            # concentration is said in words rather than as a second, clashing tier.
            steps = self.concentration - 1
            # "Dried Mint" and "Mint Reduction" already say their first concentration.
            if self.form in ("dried", "reduction"):
                steps -= 1
            return self.base if steps <= 0 else f"{self.base} ({_concentrated(steps)})"
        return self.base if self.concentration <= 1 \
            else f"{self.base} (Tier {self.concentration})"

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    def as_dict(self) -> dict:
        d = {
            "id": self.id, "name": self.name, "base": self.base,
            "concentration": self.concentration, "tier": self.tier, "rank": self.rank,
            "potency": round(self.potency, 2), "count": self.count, "craft": self.craft,
            "effects": self.effects, "drawbacks": self.drawbacks,
            "specs": self.specs, "from_ingredients": self.from_ingredients,
            "kind": self.kind, "crafted": True,
            "slot": self.slot, "wearable": self.wearable, "how": list(self.how),
            "weapon": self.weapon, "armour": self.armour,
            "masterwork": self.masterwork, "enhancement": self.enhancement,
            "properties": list(self.properties),
            "holds_spell": self.holds_spell, "caster_level": self.caster_level,
            "from_materials": list(self.from_materials),
        }
        # The step bench's fields, only when set, so a save written before the revamp
        # reads back identical and a forge's blade never grows a `quality: null`.
        if self.form:
            d["form"] = self.form
        if self.state:
            d["state"] = self.state
        if self.quality is not None:
            d["quality"] = int(self.quality)
            d["quality_name"] = quality_name(int(self.quality))
            # Quality as a tag (plan §13): asked by prefix, never matched as a word.
            d["quality_tag"] = f"quality.{quality_name(int(self.quality)).lower().replace(' ', '').replace('+', '-plus-')}"
        if self.ready_minute is not None:
            d["ready_minute"] = int(self.ready_minute)
        if self.spoils_minute is not None:
            d["spoils_minute"] = int(self.spoils_minute)
        # Written only when the name would not say it again on load: a pre-revamp jar is
        # healed on read (the way `backfill_specs` heals it), so writing the detection
        # back would turn every old save into a different file the first time it saved.
        if self.old_method and self.old_method != _old_method_of(d):
            d["old_method"] = self.old_method
        if self.base_specs:
            d["base_specs"] = [dict(s) for s in self.base_specs]
        if self.mults:
            d["mults"] = {k: round(float(v), 4) for k, v in self.mults.items()}
        if self.worked:
            d["worked"] = list(self.worked)
        if self.work:
            d["work"] = _copy.deepcopy(self.work)
        if self.magic:
            d["magic"] = _copy.deepcopy(self.magic)
        return d


# What the old cleansing wrote on a jar it had purified. The sentence no longer appears
# anywhere in the code — cleansing names the poisons it removes now — but it is written
# into every jar saved before that change, and it is the only record those jars carry of
# having been purified at all.
LEGACY_CLEANSED = "Side effects and secondary toxicities removed by the chain."


def _shape_slugs() -> list[str]:
    """The method words, as they appear inside a stock id. Longest first, so "purified
    draught" is stripped before "draught" can take half of it."""
    words = {w.lower().replace(" ", "-") for w in SHAPE_WORDS.values()}
    words.add("preparation")
    return sorted(words, key=len, reverse=True)


def base_ingredient_id(ref: str) -> str:
    """The raw ingredient at the bottom of a crafted item's id.

    `from_ingredients` mixes raw ids with the ids of crafted things that went back into
    the pot — `mad-cap` beside `mad-cap-tincture-tincture-tincture-tincture-infusion#2`.
    The crafted one still carries its lead ingredient at the front, so stripping the
    method words off the end gets back to something the shelf knows. Measured on the two
    live campaigns: all four crafted references resolve this way, and all eighteen raw
    ones already did.
    """
    slug = str(ref or "").split("#")[0].strip().lower()
    changed = True
    while changed:
        changed = False
        for word in _shape_slugs():
            if slug.endswith("-" + word):
                slug = slug[: -(len(word) + 1)]
                changed = True
    return slug


def heal_name(base: str) -> str:
    """Undo a name that compounded before `_name_for` stopped stacking shape words.

    Saved jars carry the damage: "Dragon Flower Tincture Tincture Tincture Tincture
    Tincture Tincture Tincture Tincture Tincture Tincture" is a real entry in a real
    campaign. The last shape word is kept, because it is still what the thing is.
    """
    import re

    # A concentration marker baked into the *base*. `Stock.name` appends "(Tier 2)" for
    # display and an earlier bug crafted from the display name, so it is sitting mid-string
    # in real saves — "Mad Cap Tincture Tincture Tincture Tincture Infusion (Tier 2)
    # Tincture" — where it blocks the strip loop from ever reaching the words in front of
    # it. The real concentration is a field on the jar; this is only ever a duplicate.
    name = re.sub(r"\s*\(Tier \d+\)", "", str(base or "")).strip()
    # Ellipses accumulate one per re-craft the same way shape words did — a real live
    # jar reads "Blackthorn Tincture (Acacia Infusion, Allnight Infusion…………) Purified
    # Draught", four crafts deep. Any run of dots or ellipsis characters is one elision.
    name = re.sub(r"(?:…|\.\.){2,}\.?|…\.+|\.{4,}", "…", name)
    words = sorted(set(SHAPE_WORDS.values()) | {"Preparation"}, key=len, reverse=True)
    tail = ""
    for word in words:
        if name.lower().endswith(" " + word.lower()):
            tail = name[-len(word):]
            break
    if not tail:
        return name
    stripped = name
    changed = True
    while changed:
        changed = False
        for word in words:
            if stripped.lower().endswith(" " + word.lower()):
                stripped = stripped[: -(len(word) + 1)].rstrip()
                changed = True
    return f"{stripped} {tail}".strip()


def backfill_specs(d: dict) -> list[dict]:
    """Rebuild a pre-`specs` jar's structured effects from what it was made of.

    Every jar saved before the field existed carries only prose, so it cannot be sorted
    into Effects and Drawbacks, cannot be drunk, thrown or painted on a blade, and shows
    its poisons as benefits. All fifteen in the two live campaigns are in that state.

    Rebuilt from `from_ingredients`, which every one of them does have, rather than parsed
    back out of the rendered strings — re-reading "Belladonna: DC 15" to guess at the spec
    that produced it would be a guess, and a wrong guess here is a poison that does the
    wrong thing when somebody drinks it.

    Healed on read rather than migrated on disk, which is how `Campaign.biome` treats the
    same problem: a save that needs a migration step before it is playable is a save that
    breaks the moment somebody opens an old one.
    """
    from . import consumables, ingredients as ing_mod

    refs = list(d.get("from_ingredients") or [])
    if not refs:
        return []

    out: list[dict] = []
    seen: set[str] = set()
    for ref in refs:
        try:
            source = ing_mod.get(base_ingredient_id(ref))
        except KeyError:
            continue
        for spec in source.specs:
            marked = {**spec, "from": spec.get("from") or source.name}
            key = repr(sorted(marked.items(), key=lambda kv: kv[0]))
            if key not in seen:
                seen.add(key)
                out.append(marked)

    # A jar the old chain purified says so in its effects, and that sentence is the only
    # record it has. Honouring it matters: rebuilding a Purified Draught's specs from its
    # ingredients would otherwise hand back every poison the purifying took out.
    if any(LEGACY_CLEANSED in str(line) for line in (d.get("effects") or [])):
        out = [s for s in out if not consumables.hurts(s)]
    return out


def from_stock_dict(d: dict) -> Stock:
    # An alchemist's product (docs/alchemy-contracts.md §6) keeps its record whole under
    # "alchemy" — ids and grades, never numbers — and is rebuilt from it on every load, so
    # a corrected material document fixes every bottle on the next one. Read here, the one
    # loader every saved row passes through, as the forge's record is read in `sheet._stock`.
    if isinstance(d.get("alchemy"), dict):
        from . import alchemy_items

        return alchemy_items.stock_item(d)
    # A forge-shape record (pieces and a gear kind: the forge's, and every leatherworker
    # product since the leather revamp, plan §13.1) keeps its record whole, its `base` the
    # TABLE key. Read here as `sheet._stock` reads it on load, because the bench's output
    # door (`play/craft_views.py`) comes through this function and not that one. Measured
    # (leatherworking inventory §0.1): a crafted suit through here became a plain Stock
    # whose `base` is its name — the field the engine's wear reads first — so the suit was
    # "not built on any suit the rules know ('Deer Armour')".
    from . import forge_items

    if forge_items.is_forged(d):
        return forge_items.stock_item(d)
    # `specs` absent is not the same as `specs` empty. Absent means the jar predates the
    # field and its structure has to be rebuilt; empty means a jar whose every effect was
    # prose, or one the chain purified down to nothing, and rebuilding *that* would hand
    # a cleansed draught its poisons back. "Empty is not the same as absent" — CLAUDE.md,
    # about a different form, for exactly this reason.
    specs = d.get("specs")
    if specs is None:
        specs = backfill_specs(d)

    # The step bench's fields belong to herbalism alone. A forge's output dict says
    # `"quality": "plain"` about a blade, and reading that as a quality index raised on
    # every forge craft (measured: test_a_forge_chain_spends_what_it_names went 500).
    stepped = str(d.get("craft") or "herbalism") in HERBAL_CRAFTS
    try:
        quality = int(d["quality"]) if stepped and d.get("quality") is not None \
            and not isinstance(d.get("quality"), bool) else None
    except (TypeError, ValueError):
        quality = None

    def _minute(key):
        try:
            return int(d[key]) if stepped and d.get(key) is not None else None
        except (TypeError, ValueError):
            return None

    return Stock(
        base=heal_name(d.get("base", d.get("name", "Preparation"))),
        concentration=int(d.get("concentration", 1)),
        tier=d.get("tier", "common"), potency=float(d.get("potency", 1.0)),
        count=int(d.get("count", 1)), craft=d.get("craft", "herbalism"),
        effects=list(d.get("effects", [])), drawbacks=list(d.get("drawbacks", [])),
        specs=[dict(x) for x in specs],
        from_ingredients=list(d.get("from_ingredients", [])),
        kind=d.get("kind") or "crafted",
        slot=(d.get("slot") or None),
        wearable=bool(d.get("wearable", False)),
        how=list(d.get("how") or []),
        weapon=(d.get("weapon") or None), armour=(d.get("armour") or None),
        masterwork=bool(d.get("masterwork", False)),
        enhancement=int(d.get("enhancement", 0) or 0),
        properties=list(d.get("properties") or []),
        holds_spell=(d.get("holds_spell") or None),
        caster_level=(int(d["caster_level"]) if d.get("caster_level") else None),
        from_materials=list(d.get("from_materials") or []),
        form=(str(d.get("form")) if stepped and d.get("form") else None),
        state=(str(d.get("state")) if stepped and d.get("state") else None),
        quality=quality,
        ready_minute=_minute("ready_minute"),
        spoils_minute=_minute("spoils_minute"),
        old_method=str(d.get("old_method") or "") or _old_method_of(d),
        base_specs=([dict(x) for x in (d.get("base_specs") or []) if isinstance(x, dict)]
                    if stepped else []),
        mults=({str(k): float(v) for k, v in (d.get("mults") or {}).items()}
               if stepped and isinstance(d.get("mults"), dict) else {}),
        worked=([str(m) for m in (d.get("worked") or [])] if stepped else []),
        # Every craft's, not herbalism's alone: a binding or a hide in the vat is in
        # progress the same way a jar is.
        work=(_copy.deepcopy(d["work"]) if isinstance(d.get("work"), dict) and d["work"]
              else None),
        magic=(_copy.deepcopy(d["magic"]) if isinstance(d.get("magic"), dict) and d["magic"]
               else None),
    )


# The methods the owner retired on 2026-10-02 (plan §2, "Methods removed"), by the shape
# word the old chain wrote onto everything they made. Read off the name because that is
# the only record a pre-revamp jar carries of how it was made. Longest first, so "Purified Draught" wins over a bare word.
RETIRED_METHODS = ("distill", "purify", "refine", "preserve", "catalyst crafting")
_RETIRED_BY_WORD = (("Purified Draught", "purify"), ("Tincture", "distill"),
                    ("Elixir", "refine"), ("Preserve", "preserve"),
                    ("Catalyst", "catalyst crafting"))


def _old_method_of(d: dict) -> str:
    """The retired method that made this jar, or "" (plan §14.2).

    Only herbalism's own pre-revamp jars are asked: a step-bench tincture is a tincture
    made by Steep, and a forge's work never went through a still.
    """
    if str(d.get("craft") or "herbalism") not in ("herbalism", "herbalist"):
        return ""
    if d.get("form") or d.get("state") or d.get("quality") is not None:
        return ""
    name = str(d.get("base") or d.get("name") or "")
    for word, method in _RETIRED_BY_WORD:
        if word.lower() in name.lower():
            return method
    return ""


# Herbalism's half of the acquisition hub. Foraging was a panel inside the crafting
# page; it belongs beside mining and skinning on the play page's craft-action button,
# because they are all the same kind of thing — going out and coming back with material
# — and only one of them was ever narrated into the scene.
ACQUISITION: dict[str, dict] = {
    "forage": {
        "id": "forage",
        "label": "Forage for herbs",
        "obtain": "gathered",
        "requires": "biome",
        "verb": "foraging",
        "blurb": "Walk the ground you are standing on and take what grows there. "
                 "What turns up is what the biome holds, hour by hour, against a "
                 "Survival check that gets no easier for wanting it.",
    },
}


def obtainable(obtain_kind: str, *, biome=None, creature=None) -> list:
    """What foraging could turn up here.

    Delegates to the foraging table rather than answering itself: the biome tables are
    where "what grows in a marsh" is decided, and a second answer here would be a
    second thing to keep level with the first.
    """
    if str(obtain_kind or "").lower() != "gathered":
        return []
    return [i for i in ing_mod.all_ingredients().values()
            if i.forageable and (not biome or biome in (i.biomes or []))]


def check_terms(actor, level: int) -> list[dict]:
    """What a crafter adds to the die, itemised.

    The author's formula: **d20 + track level + half character level + Wisdom**. It
    replaced `3 * level + 2 * (level - rank)`, which was invented here and had no
    counterpart anywhere in 1e — and, being invisible, could not be reasoned about at the
    bench. Every term now comes from somewhere the player can point at on their sheet.

    Itemised rather than summed because the sum is the boring half. "+9" says nothing;
    "Herbalist 4, half level +3, Wis +2" says which of the three to go and improve.
    """
    # Half the better of Craft and Profession ranks rides last (option A, the owner's
    # choice of 2026-10-07; `tradecraft.bench_terms`). 0 of 5 benches read a rank before it.
    from . import tradecraft

    return tradecraft.bench_check_terms(actor, level, track="herbalist", name="Herbalist",
                                        ability="wis")


def check_bonus(actor, level: int) -> int:
    return sum(t["value"] for t in check_terms(actor, level))


SHAPE_WORDS = {
    "grind": "Powder", "mix": "Compound", "brew": "Tea", "preserve": "Preserve",
    "extract": "Extract", "distill": "Tincture", "purify": "Purified Draught",
    "infuse": "Infusion", "neutralize": "Neutralised Draught", "refine": "Elixir",
    "catalyst crafting": "Catalyst",
}


# =========================================================================================
# THE STEP BENCH (docs/herbalism-revamp-plan.md, docs/herbalism-contracts.md §3)
# =========================================================================================
#
# One method per step. Each step is its own roll, its own minigame, and its output lands
# back on the shelf where the next step can reach it. The owner's decisions (plan §2) are
# the spec; the numbers are rule rows in content/rules/herbal-*.json, never constants here,
# so a playtest can retune them without a code change.
#
# A thing's strength is its ingredient's own effects (the base stat) times every method
# it went through, times the form it ended in, times the quality the player's hands gave
# each step, times the crafter's perks (plan §7). The effects are baked into the specs the
# engine runs, so the card and the drink read one number: the lesson of the Power leaf
# (playtest 2026-09-30), where the card said +20 and the drink landed +26 because two
# readers applied the potency two different ways. A step-bench thing therefore carries
# `potency` 1.0; its strength lives in `mults` for the next step and for the price.

import functools
import json as _json
import math
import re as _re

HERBAL_CRAFTS = ("herbalism", "herbalist")
TRACK_ID = "herbalist"
# The routes a herbal product may carry: the data lane's list, never a second copy.
BODY_ROUTES = tuple(ing_mod.HERBAL_ROUTES)
ROUTE_WORDS = {
    "ingest": "what must be swallowed", "inhale": "what must be breathed in",
    "skin": "what works on the skin", "eyes": "what works on the eyes",
    "wound": "what works in a wound",
}
# Forms that are still raw material for the bench, rather than something finished.
_WORKABLE_SOLID_FORMS = (None, "dried", "powder", "extract")
_LIQUID_PRODUCTS = ("infusion", "decoction", "tincture", "acetum", "reduction")


def _rules_file(name: str) -> dict:
    """One rule-row file. Read through BASE_DIR, never `__file__`, which points inside
    the PyInstaller bundle when frozen (CLAUDE.md)."""
    from pathlib import Path

    from django.conf import settings

    path = Path(settings.BASE_DIR) / "content" / "rules" / name
    return _json.loads(path.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=None)
def herbal_rules() -> dict:
    """The three rule-row files, read once.

    Shipped content only, with no homebrew overlay under CAMPAIGN_DIR, so this cache
    cannot leak one test's data into the next and needs no entry in conftest._CACHED.
    Callers treat the result as read-only.
    """
    return {"methods": _rules_file("herbal-methods.json"),
            "products": _rules_file("herbal-products.json"),
            "quality": _rules_file("herbal-quality.json")}


def method_row(method: str) -> dict | None:
    return herbal_rules()["methods"]["methods"].get(str(method or "").strip().lower())


def product_row(form: str | None) -> dict:
    return herbal_rules()["products"]["products"].get(str(form or ""), {})


# --- quality ---------------------------------------------------------------------------

def quality_name(index: int) -> str:
    """0 Crude ... 4 Flawless, then "Flawless +1" and on. The progression lane's one
    copy (`worldclass.quality_name`), asked rather than repeated: the page never builds a
    name (contracts §2), and two server copies could drift."""
    return wc.quality_name(index)


def quality_mult(kind: str, index: int) -> float:
    """One column of the ladder at one index, running on past Flawless by the `beyond`
    steps: potency and duration +0.1 a step, price +0.5, the drawback held at 0.25."""
    q = herbal_rules()["quality"]
    row = q[kind]
    index = max(0, int(index))
    if index < len(row):
        return float(row[index])
    over = index - len(row) + 1
    beyond = q["beyond"]
    if kind == "drawback":
        return float(beyond["drawback"])
    step = float(beyond.get(f"{kind}_step", 0))
    return float(row[-1]) + step * over


def tier_from_score(score, ceiling: int) -> tuple[int, float]:
    """The minigame's 0..1 as a quality index, spread evenly under the crafter's ceiling.

    Clamped first. The page sends the score and the server decides what it is worth, so a
    hand-written `score: 7` or a forged 1.0 at Herbalist 1 lands on the ceiling and no
    higher (plan §15.1: "a tier above the ceiling is impossible"). A perfect run lands
    exactly on the ceiling and the bands below share the range equally.
    """
    try:
        s = float(score)
    except (TypeError, ValueError):
        s = 0.0
    if s != s or s in (float("inf"), float("-inf")):    # NaN and infinities
        s = 0.0 if s != s or s < 0 else 1.0
    s = max(0.0, min(1.0, s))
    ceiling = max(0, int(ceiling))
    # A score on a band's edge lands in that band, not the one below: the strip's live
    # word is drawn from the same edges (`tuning_for`), and float arithmetic would
    # otherwise floor 1/3 x 3 one rung short of what the player was shown.
    return min(ceiling, int(s * (ceiling + 1) + 1e-6)), round(s, 4)


# --- baking a strength into an effect ----------------------------------------------------

_DICE_RE = _re.compile(r"^\s*(\d+)d(\d+)\s*(?:([+-])\s*(\d+))?\s*$", _re.I)
_RANGE_RE = _re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
# Effect types whose `amount` is a strength to scale. Everything else (a DC, a count of
# uses, an immunity's name) is left as written.
_SCALED_TYPES = set(con.SCALED_BONUSES) | {
    "situational_mod", "resistance", "damage_reduction", "fast_healing", "speed",
    "temp_hp", "heal", "damage", "ability_damage", "ability_drain", "bleed"}


def _round(x: float, up: bool) -> int:
    """The module's rounding rule: benefits round up, costs round down (module header).
    The epsilon keeps 1.5 * 2 = 3.0000000004 from rounding up to 4."""
    return math.ceil(x - 1e-9) if up else math.floor(x + 1e-9)


def _scale_dice(text, mult: float, up: bool) -> str:
    """A dice expression at a strength, scaling the flat part as `consumables.scale`
    does ("1d6 at 125%" is 1d6+1, never 1.25d6), with the rounding direction said: a
    benefit's extra rounds up, a harm's rounds down."""
    raw = str(text or "")
    r = _RANGE_RE.match(raw)
    if r and int(r.group(2)) > int(r.group(1)):
        lo, hi = int(r.group(1)), int(r.group(2))
        raw = f"1d{hi - lo + 1}" + (f"+{lo - 1}" if lo > 1 else "")
    m = _DICE_RE.match(raw)
    if not m:
        try:
            n = float(raw)
        except ValueError:
            return str(text)
        return str(_round(n * mult, up))
    if abs(mult - 1.0) < 1e-9:
        return raw
    count, sides = int(m.group(1)), int(m.group(2))
    flat = int(m.group(4) or 0) * (-1 if m.group(3) == "-" else 1)
    average = count * (sides + 1) / 2 + flat
    flat += _round(average * (mult - 1.0), up)
    if flat > 0:
        return f"{count}d{sides}+{flat}"
    if flat < 0:
        return f"{count}d{sides}{flat}"
    return f"{count}d{sides}"


def _scale_amount(value, mult: float, up: bool):
    """A flat number at a strength. A penalty (a negative benefit-type amount on a
    drawback) shrinks or grows in magnitude, rounded the way a cost rounds."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        n = float(value)
    else:
        text = str(value or "").strip()
        if _DICE_RE.match(text) or _RANGE_RE.match(text):
            return _scale_dice(text, mult, up)
        try:
            n = float(text)
        except ValueError:
            return value
    if n < 0:
        return -_round(abs(n) * mult, not up)
    return _round(n * mult, up)


def _scale_duration(duration, mult: float, up: bool):
    """A duration at a strength. Never below 1: a duration of 0 reads as no duration,
    which for a condition is "for ever", the opposite of what softening meant."""
    if not isinstance(duration, dict) or abs(mult - 1.0) < 1e-9:
        return duration
    amount = duration.get("amount")
    try:
        n = float(str(amount).strip())
    except (TypeError, ValueError):
        # A dice duration stays dice and is rolled each time it lands (the owner,
        # 2026-10-02: "roll them"); its average moves by the multiplier the way a dice
        # amount does ("1d4 at 150%" is 1d4+1). Before this it passed through untouched,
        # so the one kind of duration quality could not lengthen was the source's dice.
        return {**duration, "amount": _scale_dice(str(amount), mult, up)}
    return {**duration, "amount": max(1, _round(n * mult, up))}



def _harmful_ids(specs: list[dict]) -> set[int]:
    """Which of these specs are harm.

    Two readers, both asked, never copied: `consumables.sort_harm` groups a poison's
    save with the damage it gates (so the gate files beside its body), and
    `herbknowledge.classify` is what the herbarium labels a property with (so a property
    the Journal calls a drawback is never a benefit on the bench: it adds vulnerability,
    which the jar's sort predates).
    """
    from . import herbknowledge

    sorted_out = con.sort_harm(specs)
    benefits = {id(s) for s in sorted_out.benefits}
    return {id(s) for s in specs
            if id(s) not in benefits or herbknowledge.is_drawback(s)}


def bake(specs: list[dict], potency: float, duration: float,
         drawback: float) -> list[dict]:
    """The effects as the engine will run them, at this strength.

    Benefits take `potency` and `duration`, rounded up; harm takes `drawback` for both
    its strength and how long it lasts, rounded down (quality "softens drawbacks"). The
    `origin` bookkeeping stays behind on `base_specs`; the engine never sees it.
    """
    harm = _harmful_ids(specs)
    out = []
    for spec in specs:
        harmful = id(spec) in harm
        mult = drawback if harmful else potency
        dmult = drawback if harmful else duration
        up = not harmful
        s = {k: v for k, v in spec.items() if k != "origin"}
        kind = str(s.get("type", ""))
        if "dice" in s and s["dice"] not in (None, ""):
            s["dice"] = _scale_dice(s["dice"], mult, up)
        if kind in _SCALED_TYPES and s.get("amount") not in (None, ""):
            s["amount"] = _scale_amount(s["amount"], mult, up)
        if "duration" in s:
            s["duration"] = _scale_duration(s["duration"], dmult, up)
        out.append(s)
    return out


def _concentrated(steps: int) -> str:
    words = {1: "concentrated once", 2: "concentrated twice", 3: "concentrated thrice"}
    return words.get(int(steps), f"concentrated {int(steps)} times")


# --- what is on the shelf ----------------------------------------------------------------

@dataclass
class Material:
    """One satchel entry as the bench sees it: a raw ingredient from the satchel's counts,
    or something made, from the crafted shelf. The same questions are asked of both."""
    key: str
    name: str
    ingredient_id: str
    kind: str
    part: str
    tier: str
    count: int
    state: str | None = "raw"
    form: str | None = None
    quality: int | None = None
    crafted: bool = False
    ingredient: object = None
    stock: Stock | None = None
    spoils_in: int | None = None
    spoiled: bool = False
    ready_minute: int | None = None
    # In progress (rules/inprogress.py): "working", "ready" (done, not yet collected) or
    # None. Read off the clock when the satchel was built, so the fit check can say which.
    work_state: str | None = None
    ready_at: int | None = None
    old: str = ""
    worked: list[str] = field(default_factory=list)
    concentration: int = 0              # concentration steps this line has had
    base_specs: list[dict] = field(default_factory=list)
    mults: dict = field(default_factory=dict)
    from_ingredients: list[str] = field(default_factory=list)

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    def _ing_field(self, name, default):
        if self.crafted or self.ingredient is None:
            return default
        return getattr(self.ingredient, name, default)

    @property
    def solvent(self) -> str:
        return str(self._ing_field("solvent", "") or "").strip().lower()

    @property
    def base_for(self) -> list[str]:
        return [str(x).lower() for x in (self._ing_field("base_for", []) or [])]

    @property
    def neutralizer(self) -> int:
        try:
            return int(self._ing_field("neutralizer", 0) or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def prep(self):
        from . import herbprep

        lead = self.ingredient
        if lead is None and self.from_ingredients:
            try:
                lead = ing_mod.get(base_ingredient_id(self.from_ingredients[0]))
            except KeyError:
                lead = None
        return herbprep.Prep.of(lead) if lead is not None else herbprep.Prep()

    @property
    def liquid(self) -> bool:
        if self.form:
            return bool(product_row(self.form).get("liquid"))
        if self.part in ("liquid", "oil"):
            return True
        return bool(self.prep.liquid) and self.part not in ("bark", "resin")

    @property
    def reagent(self) -> str:
        """What kind of reagent this is ("solvent", "neutralizer", "base"), or "" for a
        thing with effects of its own. Oil, alcohol, vinegar, beeswax and neutralizers
        arrive as ingredients carrying these fields (contracts §2)."""
        if self.crafted:
            return "base" if self.form == "salve-base" else ""
        if self.solvent:
            return "solvent"
        if self.neutralizer > 0:
            return "neutralizer"
        if self.base_for and not self.base_specs:
            return "base"
        return ""

    @property
    def is_base(self) -> bool:
        return self.form == "salve-base" or (not self.crafted and bool(self.base_for))

    @property
    def neutralised(self) -> bool:
        return "neutralize" in self.worked or self.state == "neutralised"

    @property
    def extracted(self) -> bool:
        return "extract" in self.worked or self.state == "extracted"

    @property
    def dried(self) -> bool:
        return "dry" in self.worked or self.state == "dried"

    @property
    def prep_state(self) -> str:
        """The state `herbprep.can` understands. It knows no "dried": a dried thing has
        been extracted already if it ever needed to be, which is what the walk asks."""
        if self.state == "ground":
            return "ground"
        if self.neutralised:
            return "neutralised"
        if self.extracted or self.dried:
            return "extracted"
        return "raw"

    def mult(self, kind: str) -> float:
        return float((self.mults or {}).get(kind, 1.0))

    @property
    def base_dc(self) -> int:
        """This line's DC: its hardest source ingredient's own DC (an authored craft_dc
        wins, as `_dc` rules), plus n(n+1) for the concentration it has already had."""
        dcs = []
        for ref in self.from_ingredients or [self.ingredient_id]:
            try:
                ing = ing_mod.get(base_ingredient_id(ref))
            except KeyError:
                continue
            dcs.append(ing.craft_dc if ing.craft_dc is not None else 5 + 5 * ing.rank)
        base = max(dcs) if dcs else 5 + 5 * self.rank
        n = self.concentration
        return base + n * (n + 1)

    def as_item(self, actor=None, now_minute: int | None = None) -> dict:
        """The satchel item shape (contracts §3)."""
        from . import herbknowledge

        if self.crafted:
            unknown = _unknown_carried(actor, self.base_specs)
        else:
            unknown = herbknowledge.unknown_count(actor, self.ingredient) \
                if actor is not None and self.ingredient is not None else 0
        # Set while the thing is In progress, working OR ready: a jar whose day has come
        # stays in the satchel's Steeping group ("ready now") until it is collected, the
        # owner's rule (rules/inprogress.py), rather than dropping silently into the shelf.
        ready_at = int(self.ready_at) if self.work_state is not None \
            and self.ready_at is not None else None
        d = {"key": self.key, "name": self.name, "ingredient_id": self.ingredient_id,
             "kind": self.kind, "part": self.part, "tier": self.tier,
             "state": self.state, "form": self.form,
             "quality": self.quality,
             "quality_name": quality_name(self.quality) if self.quality is not None
             else None,
             "count": self.count, "unknown": int(unknown),
             "spoils_in": self.spoils_in, "ready_at": ready_at,
             "crafted": self.crafted}
        if ready_at is not None:
            d["ready_in"] = max(0, ready_at - int(now_minute or 0))
            d["ready_day"] = ready_at // 1440 + 1
            d["work_state"] = self.work_state
        if self.old:
            d["old_method"] = self.old
        return d


def _unknown_carried(actor, base_specs) -> int:
    """How many of the properties a made thing carries the actor does not know. A
    product reveals what it carries when it is made, so this is 0 for anything made at
    the step bench; it is not 0 for a remedy somebody else made and gave them."""
    from . import herbknowledge

    if actor is None:
        return 0
    seen, unknown = set(), 0
    for spec in base_specs or []:
        origin = spec.get("origin") or {}
        iid, key = origin.get("ingredient"), origin.get("key")
        if not iid or (iid, key) in seen:
            continue
        seen.add((iid, key))
        try:
            ing = ing_mod.get(iid)
        except KeyError:
            continue
        if key not in set(herbknowledge.known_keys(actor, ing)):
            unknown += 1
    return unknown


def part_of(ingredient) -> str:
    """An ingredient's part, with the data lane's defaults by kind for an entry that
    never said (`ingredients.default_part`)."""
    got = getattr(ingredient, "part", None)
    if got:
        return str(got).strip().lower()
    return ing_mod.default_part(str(getattr(ingredient, "kind", "") or ""))


def ingredient_specs(ing) -> list[dict]:
    """An ingredient's own effects, each stamped with where it came from: the name a card
    prints (`from`) and the property key the herbarium knows it by (`origin`). The key is
    the effect's position in `Ingredient.pairs`, as `herbknowledge.property_keys` counts."""
    out = []
    for i, (_line, spec) in enumerate(ing.pairs):
        if spec:
            out.append({**spec, "from": spec.get("from") or ing.name,
                        "origin": {"ingredient": ing.id, "key": f"p{i}"}})
    return out


def _route(spec: dict) -> str:
    """An effect's route, asked of the data lane's one reader: a missing route is ingest
    and an unknown one external, so a route nobody recognises never slips into a remedy."""
    return str(ing_mod.route_of(spec))


def _ingredient(iid: str):
    """An ingredient or reagent by id, or None. `ingredients.get` reaches the reagents in
    content/materials as well (Lane A); `all_ingredients` does not, on purpose."""
    try:
        return ing_mod.get(iid)
    except KeyError:
        return None


def _reagent_for_stock(item):
    """A reagent bought at a counter arrives as `Stock(base="Beeswax", craft="")` through
    `goods.deliver`. Mapped back to its reagent row so it reaches the bench as what it
    is, rather than as a jar of nothing."""
    return ing_mod.reagent_named(item.base)


def is_reagent_ingredient(ing) -> bool:
    return str(getattr(ing, "kind", "") or "") == "reagent" or bool(
        getattr(ing, "solvent", "") or getattr(ing, "neutralizer", 0)
        or (getattr(ing, "base_for", None) and not getattr(ing, "specs", None)))


def satchel(actor, now_minute: int | None = None,
            reserved: dict | None = None) -> list[Material]:
    """Everything the bench can reach for: raw herbs and reagents in the satchel's counts,
    and everything herbalism has made. Only what is carried (UI plan §6.2): the herbs met
    and not carried live in the herbarium, which retires the 161-tile wall.

    `reserved` is `{key: count}` set aside by a craft between its roll and its finish;
    the counts shown are what is left to use.
    """
    from . import herbprep

    reserved = reserved or {}
    out: list[Material] = []
    if actor is None:
        return out

    def raw(key, iid, ing, count):
        spoils_in, spoiled = None, False
        # Oil, spirits, wax and lime do not rot on the week a leaf does (Lane A's
        # finding: they were taking herbprep's one-week default).
        if now_minute is not None and not is_reagent_ingredient(ing):
            spoiled, hours_left = actor.freshness(iid, now_minute, herbprep.Prep.of(ing))
            spoils_in = None if hours_left < 0 else int(hours_left) * 60
        return Material(
            key=key, name=ing.name, ingredient_id=ing.id, kind=ing.kind,
            part=part_of(ing), tier=wc.TIERS[ing.rank - 1], count=count, ingredient=ing,
            spoils_in=spoils_in, spoiled=spoiled,
            base_specs=ingredient_specs(ing), from_ingredients=[ing.id])

    for iid, n in sorted((actor.inventory or {}).items()):
        ing = _ingredient(iid)
        if ing is None or int(n or 0) <= 0:
            continue
        key = f"ing:{iid}"
        count = int(n) - int(reserved.get(key, 0))
        if count > 0:
            out.append(raw(key, iid, ing, count))
    for sid, item in sorted((actor.stock or {}).items(), key=lambda kv: kv[1].name.lower()):
        key = f"stock:{sid}"
        count = int(item.count or 0) - int(reserved.get(key, 0))
        if count <= 0:
            continue
        if str(item.craft or "") not in HERBAL_CRAFTS:
            reagent = _reagent_for_stock(item) if not item.stepped else None
            if reagent is not None:
                out.append(raw(key, reagent.id, reagent, count))
            continue
        lead = base_ingredient_id(item.from_ingredients[0]) if item.from_ingredients \
            else ""
        lead_ing = _ingredient(lead) if lead else None
        spoils_in, spoiled = None, False
        if item.spoils_minute is not None and now_minute is not None:
            spoils_in = int(item.spoils_minute) - int(now_minute)
            spoiled = spoils_in <= 0
            spoils_in = max(0, spoils_in)
        old = ""
        if not item.stepped:
            # Pre-revamp work: still usable and sellable, never worked further (§14.2).
            old = item.old_method or "old bench"
        out.append(Material(
            key=key, name=item.name, ingredient_id=lead,
            kind=(lead_ing.kind if lead_ing is not None else str(item.kind or "crafted")),
            part=(part_of(lead_ing) if lead_ing is not None else "liquid"),
            tier=item.tier, count=count, state=item.state, form=item.form,
            quality=item.quality, crafted=True, stock=item,
            spoils_in=spoils_in, spoiled=spoiled, ready_minute=item.ready_minute,
            work_state=inprogress.state_of(item, now_minute),
            ready_at=inprogress.end_of(item, now_minute),
            old=old, worked=list(item.worked),
            concentration=max(0, int(item.concentration or 1) - 1) if item.stepped else 0,
            base_specs=[dict(s) for s in item.base_specs], mults=dict(item.mults),
            from_ingredients=list(item.from_ingredients)))
    return out


# `settle_steeping` lived here until 2026-10-05: every bench request lifted the jars whose
# day had come, silently, and the satchel showed them as tinctures from then on. The owner's
# In-progress ruling ("all the crafts sit before they can be collected") retired it: the
# clock's own door turns a jar READY and tells it (`Scene.advance` -> `inprogress.settle`),
# and the jar stays in the section until the player collects it. One store, one door; a
# second settle here would have swallowed the tell the clock owes.


def _collect_jar(item, actor) -> dict:
    """Collecting a steeped jar: it is the tincture or acetum it always was, so nothing is
    done beyond the section's own lift."""
    return {"said": f"You take the {item.name} out of its steep."}


inprogress.register("herbalist", collect=_collect_jar, icon="steeping")


# --- levels, rarity and the check --------------------------------------------------------

def rarity_ceiling(level: int) -> int:
    """The rarest band a herbalist of this level may work (plan §2: L1 common and
    uncommon, L2 rare and exotic, L3 legendary), read from the Herbalist's own document
    so the bench and the engine's craft check cannot disagree."""
    track = wc.get(TRACK_ID)
    return wc.tier_rank(track.at(max(1, int(level))).max_tier)


def level_for_rank(rank: int) -> int | None:
    track = wc.get(TRACK_ID)
    for lvl in sorted(track.levels, key=lambda x: x.level):
        if wc.tier_rank(lvl.max_tier) >= rank:
            return lvl.level
    return None


def methods_view(level: int) -> list[dict]:
    """The method strip (contracts §3.1): every method in the craft's order, with the
    level it is learned at in words when it is locked (UI plan §6.1: never a tooltip
    only)."""
    rules = herbal_rules()["methods"]
    out = []
    for mid in rules["order"]:
        row = rules["methods"][mid]
        need = int(row.get("level", 1))
        locked = need > int(level)
        out.append({"id": mid, "name": row.get("name", mid.title()), "level": need,
                    "locked": locked,
                    "lock_reason": f"Herbalist {need}" if locked else "",
                    "takes": row.get("takes", ""), "makes": row.get("makes", "")})
    return out


def check_odds(dc: int, bonus: int) -> tuple[int | None, str]:
    """The face needed, or None and why no face will do.

    No automatic natural 20 on a bench check, and no automatic natural 1 either: the CRB
    gives the d20's naturals to attacks and saves, not to skill checks (p.180, the reader
    is `dice.d20_succeeds`, which skills never ask). Under the old bench's natural 20 any
    depth of concentration was reachable with enough doses and luck, and the climbing DC
    gated nothing (plan §5.3). The odds shown are the odds rolled.
    """
    gap = int(dc) - int(bonus)
    if gap > 20:
        return None, f"needs +{gap - 20} more to the check"
    return max(1, gap), ""


# --- whether one thing fits -------------------------------------------------------------

def _single_kind_methods() -> tuple[str, ...]:
    return ("grind", "dry", "reduce", "extract", "brew", "neutralize", "infuse", "steep")


def _finished(m: Material) -> bool:
    return m.form not in _WORKABLE_SOLID_FORMS and m.form not in _LIQUID_PRODUCTS \
        if m.form else False


def fit_reason(method: str, m: Material, pot: list[Material], level: int) -> str:
    """Why this satchel item cannot go on the bench for this method with this pot, in
    words, or "" when it fits. Every dimmed tile carries one (UI plan §6.2, the Game
    Accessibility Guidelines: never colour alone).

    `pot` is what is already on the tool, without this item.
    """
    from . import herbprep

    row = method_row(method)
    if row is None:
        return f"there is no method called {method!r}"
    need = int(row.get("level", 1))
    if need > int(level):
        return f"{row['name']} is learned at Herbalist {need}"
    # In progress (rules/inprogress.py): a jar still steeping, or steeped and waiting to be
    # collected, is not on the shelf yet. The second is new with the owner's ruling that
    # finished work sits in the section until it is collected.
    if m.work_state == "working":
        end = m.ready_at if m.ready_at is not None else (m.ready_minute or 0)
        return f"still steeping: ready on day {int(end) // 1440 + 1}"
    if m.work_state == "ready":
        return "ready to collect: take it out of In progress first"
    if m.spoiled:
        return "it has spoiled"
    if m.old:
        return ("made by an old method: it can be used and sold, not worked further"
                if m.old in RETIRED_METHODS else
                "made at the old bench: it can be used and sold, not worked further")
    ceiling = rarity_ceiling(level)
    if m.rank > ceiling:
        lvl = level_for_rank(m.rank)
        return (f"Herbalist {lvl} for {m.tier}" if lvl
                else f"{m.tier} is beyond any Herbalist level")

    reagent = m.reagent
    work = [p for p in pot if not p.reagent]
    reagents = [p for p in pot if p.reagent]
    prep = m.prep
    state = m.prep_state

    def shell_first() -> str:
        # herbprep's own sentence, so the bench and every other reader of the order
        # rules say it one way.
        if prep.needs_extraction and not m.extracted:
            return herbprep.can("mix", prep, "raw")[1]
        return ""

    def one_thing(word: str) -> str:
        if not reagent and any(p.key != m.key for p in work):
            return f"{word} works one thing at a time; clear the bench first"
        return ""

    if method == "grind":
        if reagent in ("solvent", "neutralizer"):
            return "it is a reagent, not something to grind"
        if m.state == "ground" or m.form in ("powder", "salve-base"):
            return "it is already ground"
        if _finished(m) or m.form in _LIQUID_PRODUCTS:
            return f"a finished {product_row(m.form).get('name', m.form).lower()} " \
                   f"cannot be ground"
        if m.liquid and m.part not in herbal_rules()["methods"]["salve_base_parts"]:
            return "it pours; there is nothing to grind"
        ok, why = herbprep.can("grind", prep, state)
        if not ok:
            if prep.volatile and not m.neutralised and not shell_first():
                # The lock stays until Neutralize is learned (plan Q3), and says so: a
                # reason that names no way through reads like a bug.
                return ("it is volatile: it must be neutralized before it is ground, "
                        "and Neutralize is learned at Herbalist 3" if int(level) < 3
                        else why)
            return why
        return one_thing("The mortar")

    if method == "dry":
        if reagent:
            return "it is a reagent, not something to dry"
        if m.liquid:
            return "it pours; a liquid is reduced, not dried"
        if m.form not in _WORKABLE_SOLID_FORMS:
            return f"a finished {product_row(m.form).get('name', m.form).lower()} " \
                   f"is not dried"
        if shell_first():
            return shell_first()
        if m.count < 2:
            return f"drying takes two; you carry {m.count}"
        return one_thing("The rack")

    if method == "reduce":
        if reagent:
            return "it is a solvent, not a remedy; there is nothing in it to reduce"
        if not m.liquid:
            return "only a liquid reduces; a solid is dried"
        if m.form == "infused-oil":
            return "oil does not reduce; it scorches"
        if m.count < 2:
            return f"reducing takes two; you carry {m.count}"
        return one_thing("The pan")

    if method == "extract":
        if reagent:
            return "it is a reagent; there is nothing to extract"
        if m.form not in (None,) or not prep.needs_extraction:
            return "there is nothing to extract it from"
        if m.extracted:
            return "it has already been extracted"
        return one_thing("The board")

    if method == "brew":
        if reagent:
            return "it is a reagent, not something to brew"
        if m.form in _LIQUID_PRODUCTS or m.form == "infused-oil" or \
                (m.liquid and m.form is None):
            return "it already pours; brewing makes a liquid from a solid"
        if _finished(m):
            return f"a finished {product_row(m.form).get('name', m.form).lower()} " \
                   f"is not brewed"
        ok, why = herbprep.can("brew", prep, state)
        if not ok:
            return why
        if m.part not in herbal_rules()["methods"]["brew_product_by_part"]:
            return f"{_a(m.part)} does not brew"
        return one_thing("The pot")

    if method == "neutralize":
        if reagent == "neutralizer":
            if any(p.reagent == "neutralizer" and p.key != m.key for p in reagents):
                return "one neutralizer at a time"
            return ""
        if reagent:
            return "it is a reagent; Neutralize takes a volatile thing and a neutralizer"
        if not prep.volatile:
            return "it is not volatile; there is nothing to neutralize"
        if m.neutralised:
            return "it is already neutralised"
        if _finished(m):
            return f"a finished {product_row(m.form).get('name', m.form).lower()} " \
                   f"is past neutralizing"
        if shell_first():
            return shell_first()
        return one_thing("The dropper")

    if method == "infuse":
        if reagent == "solvent":
            if m.solvent != "oil":
                return f"infused oil takes an oil; this is {m.solvent}"
            if any(p.reagent == "solvent" and p.key != m.key for p in reagents):
                return "one oil at a time"
            return ""
        if reagent:
            return "infused oil takes a dried herb and an oil"
        if m.liquid or _finished(m):
            return "infused oil takes a dried herb and an oil"
        if not m.dried:
            return "dry it first: infused oil needs a dried herb"
        return one_thing("The crock")

    if method == "steep":
        if reagent == "solvent":
            if m.solvent not in ("alcohol", "vinegar"):
                return (f"steeping takes alcohol or vinegar; {m.solvent} is for "
                        f"{'Infuse' if m.solvent == 'oil' else 'something else'}")
            if any(p.reagent == "solvent" and p.key != m.key for p in reagents):
                return "one solvent at a time"
            return ""
        if reagent:
            return "a jar takes a herb and alcohol or vinegar"
        if m.liquid or _finished(m):
            return "a jar takes a herb and alcohol or vinegar"
        if shell_first():
            return shell_first()
        return one_thing("The jar")

    if method == "mix":
        if reagent in ("solvent", "neutralizer"):
            return {"solvent": "a solvent belongs in a jar or an oil crock, not a mix",
                    "neutralizer": "a neutralizer is for Neutralize, not a mix"}[reagent]
        poultice_pot = any(p.state == "ground" and not p.is_base for p in pot)
        salve_pot = any(p.is_base or p.form in ("infused-oil", "infusion") for p in pot)
        if m.is_base or m.form in ("infused-oil", "infusion"):
            if poultice_pot:
                return "this mix is a poultice; bases and oils make a salve"
            return ""
        if m.form in _LIQUID_PRODUCTS or m.form == "reduction" or \
                (m.liquid and m.form is None):
            return "a mix takes ground herbs, bases, oils and infusions"
        if _finished(m):
            return f"a finished {product_row(m.form).get('name', m.form).lower()} " \
                   f"is not mixed again"
        if m.state != "ground":
            return "grind it first: a poultice takes a ground herb"
        if salve_pot:
            return "this mix is a salve; a ground herb makes a poultice"
        return ""

    return f"{method} is not something the bench does"


def fits_for(method: str, items: list[Material], pot: list[tuple[Material, int]],
             level: int) -> dict:
    """`{key: reason or ""}` for every satchel item (contracts §3.2: `fits` covers every
    item, which is what dims tiles). An item already on the tool is judged against the
    rest of the pot."""
    pot_mats = [m for m, _ in pot]
    return {m.key: fit_reason(method, m, [p for p in pot_mats if p.key != m.key], level)
            for m in items}


# --- the step itself ---------------------------------------------------------------------

@dataclass
class StepPlan:
    """What one step would do: everything `check` shows, `roll` gates on and `finish`
    makes. Built fresh for every request; nothing in it is trusted from the page."""
    method: str
    batch: int = 1
    picks: list[tuple[Material, int]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    form: str | None = None
    state: str | None = None
    name: str = ""
    doses: int = 0
    minutes: int = 0
    ready_minutes: int | None = None
    dc: int = 0
    bonus: int = 0
    terms: list[dict] = field(default_factory=list)
    need: int | None = None
    impossible: str = ""
    consumes: list[tuple[Material, int]] = field(default_factory=list)
    base_specs: list[dict] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)
    pre: dict = field(default_factory=dict)      # potency/duration/drawback before quality
    # What the line carries in (`Material.mult`, or Mix's weighted mean) and this step's
    # own multipliers before the quality the hands give it; `strength_at` combines them
    # by `combine_multipliers`. `pre` is the same thing at quality 1.0, kept for readers.
    carried: dict = field(default_factory=dict)
    factors: dict = field(default_factory=dict)
    # Drying is a batch method (owner, 2026-11-01): how many batches the doses take and
    # how many doses one batch holds. 0 for every method timed per dose.
    batches: int = 0
    batch_capacity: int = 0
    concentration: int = 0
    tier: str = "common"
    rank_in: int = 1
    part: str = "leaf"
    lead: Material | None = None
    worked: list[str] = field(default_factory=list)
    from_ingredients: list[str] = field(default_factory=list)
    level: int = 1
    ceiling: int = 2

    @property
    def can_roll(self) -> bool:
        return not self.problems and self.need is not None and self.doses > 0


def _lead_name(m: Material) -> str:
    """The plain name a product is called after: the lead ingredient's own, never the
    stock's, so names cannot compound ("Tincture Tincture Tincture", seen in play)."""
    try:
        return ing_mod.get(m.ingredient_id).name
    except KeyError:
        return heal_name(m.name)


def _weighted(parts: list[tuple[Material, int]], kind: str) -> float:
    carrying = [(m, n) for m, n in parts if m.base_specs]
    if not carrying:
        return 1.0
    total = sum(n for _, n in carrying)
    return sum(m.mult(kind) * n for m, n in carrying) / max(1, total)


def plan_step(actor, progress, method: str, picks: list[tuple[Material, int]],
              batch: int = 1, perks: dict | None = None) -> StepPlan:
    """One step, worked out without changing anything.

    `picks` are (satchel item, count per batch unit); `batch` repeats the unit. One roll
    and one minigame cover the whole batch and it shares one tier (plan §6, "Bulk").
    """
    rules = herbal_rules()
    method = str(method or "").strip().lower()
    level = int(getattr(progress, "level", 1) or 1)
    batch = max(1, int(batch or 1))
    plan = StepPlan(method=method, batch=batch, picks=list(picks), level=level,
                    ceiling=wc.ceiling_index(progress) if progress is not None else 2)
    row = method_row(method)
    if row is None:
        plan.problems.append(f"There is no method called {method!r}.")
        return plan
    plan.terms = check_terms(actor, level)
    plan.bonus = sum(t["value"] for t in plan.terms)
    if int(row.get("level", 1)) > level:
        plan.problems.append(f"{row['name']} is learned at Herbalist {row['level']}.")
    if not picks:
        plan.problems.append("Nothing on the bench yet.")
        return plan

    for m, n in picks:
        why = fit_reason(method, m, [p for p, _ in picks if p.key != m.key], level)
        if why:
            plan.problems.append(f"{m.name}: {why}.")
        if n <= 0:
            plan.problems.append(f"{m.name}: a count of {n} is nothing.")
        elif n * batch > m.count:
            plan.problems.append(
                f"{m.name}: the batch wants {n * batch} and you carry {m.count}.")
    if plan.problems:
        return plan

    work = [(m, n) for m, n in picks if not m.reagent]
    reagents = [(m, n) for m, n in picks if m.reagent]
    perks = perks or {}
    mrow_p, mrow_d = row.get("potency", 1.0), row.get("duration", 1.0)

    def take(m, n):
        plan.consumes.append((m, n))

    # --- what this method makes from what is on it ---------------------------------
    if method in _single_kind_methods():
        if not work:
            plan.problems.append("Add the thing to be worked; a reagent alone makes "
                                 "nothing.")
            return plan
        lead, per = work[0]
        units = per * batch
        per_dose = int(row.get("inputs_per_dose", 1))
        if per_dose > 1:
            if per % per_dose:
                plan.problems.append(
                    f"{row['name']} takes {per_dose} for each dose: add an even number.")
                return plan
            plan.doses = units // per_dose
        else:
            plan.doses = units
        take(lead, units)
        reagent_want = {"infuse": "solvent", "steep": "solvent",
                        "neutralize": "neutralizer"}.get(method)
        if reagent_want:
            got = [(m, n) for m, n in reagents if m.reagent == reagent_want]
            what = {"infuse": "oil", "steep": "alcohol or vinegar",
                    "neutralize": "neutralizer"}[method]
            have = sum(n for _, n in got) * batch
            if not got or have < plan.doses:
                plan.problems.append(
                    f"Add {what}: one for each dose ({plan.doses} needed, "
                    f"{have} on the bench).")
                return plan
            take(got[0][0], plan.doses)
        part = lead.part
        if method == "grind":
            plan.form = "salve-base" if part in rules["methods"]["salve_base_parts"] \
                else "powder"
            plan.state = "ground"
        elif method == "dry":
            plan.form = "powder" if lead.form == "powder" else "dried"
            plan.state = lead.state if lead.form == "powder" else "dried"
        elif method == "reduce":
            plan.form = lead.form if lead.form in _LIQUID_PRODUCTS else "reduction"
            # A liquid has no ingredient state; the five states are a solid's.
            plan.state = None
        elif method == "extract":
            plan.form, plan.state = "extract", "extracted"
        elif method == "brew":
            plan.form = rules["methods"]["brew_product_by_part"].get(part, "decoction")
            plan.state = None
        elif method == "infuse":
            plan.form, plan.state = "infused-oil", None
        elif method == "steep":
            solvent = next(m.solvent for m, _ in reagents if m.reagent == "solvent")
            plan.form = "tincture" if solvent == "alcohol" else "acetum"
            plan.state = None
            plan.ready_minutes = int(row.get("ready_minutes", {}).get(plan.form, 0))
        elif method == "neutralize":
            plan.form, plan.state = lead.form, "neutralised"
        carried = [(lead, per)]
        p_in, d_in, w_in = lead.mult("potency"), lead.mult("duration"), \
            lead.mult("drawback")
        conc_in = lead.concentration
    else:
        # Mix: one batch unit makes one dose, from everything on the bowl.
        bases = [(m, n) for m, n in picks if m.is_base]
        oils = [(m, n) for m, n in picks if m.form == "infused-oil"]
        infusions = [(m, n) for m, n in picks if m.form == "infusion"]
        herbs = [(m, n) for m, n in picks if m.state == "ground" and not m.is_base]
        base_units = sum(n for _, n in bases)
        oil_units = sum(n for _, n in oils)
        if herbs and not (bases or oils or infusions):
            plan.form = "poultice"
        elif bases and not (oils or infusions or herbs):
            if base_units < 2:
                plan.problems.append("A salve base blend takes two bases or more.")
                return plan
            plan.form = "salve-base"
        elif bases and infusions:
            plan.form = "cream"
        elif bases and oils:
            plan.form = "balm" if base_units >= 2 * oil_units else "salve"
        else:
            plan.problems.append("Add a salve base: oils and infusions are mixed into "
                                 "one.")
            return plan
        plan.doses = batch
        plan.state = None
        for m, n in picks:
            take(m, n * batch)
        carried = list(picks)
        lead = (herbs or oils or infusions or bases)[0][0]
        p_in = _weighted(carried, "potency")
        d_in = _weighted(carried, "duration")
        w_in = _weighted(carried, "drawback")
        conc_in = max((m.concentration for m, _ in carried), default=0)
        mrow_p = mrow_d = 1.0

    prow = product_row(plan.form)
    plan.lead = lead
    plan.part = lead.part
    plan.worked = list(lead.worked) + [method]
    plan.from_ingredients = list(dict.fromkeys(
        ref for m, _ in carried for ref in (m.from_ingredients or [m.ingredient_id])))

    # --- concentration, rarity and the DC ------------------------------------------
    concentrates = bool(row.get("concentrates"))
    cfg = rules["methods"]["concentration"]
    plan.concentration = conc_in + 1 if concentrates else conc_in
    base_dc = max(m.base_dc for m, _ in carried)
    plan.dc = base_dc + (int(cfg["dc_per_step"]) * plan.concentration
                         if concentrates else 0)
    plan.rank_in = max(m.rank for m, _ in carried)
    rank_out = min(len(wc.TIERS), plan.rank_in + (int(cfg["rarity_step"])
                                                  if concentrates else 0))
    plan.tier = wc.TIERS[rank_out - 1]
    ceiling_rank = rarity_ceiling(level)
    if rank_out > ceiling_rank:
        lvl = level_for_rank(rank_out)
        plan.problems.append(
            f"This would make {plan.tier} material, beyond Herbalist {level}: "
            + (f"it needs Herbalist {lvl}." if lvl else "no Herbalist level works it."))
    plan.need, plan.impossible = check_odds(plan.dc, plan.bonus)

    # --- strength before the player's hands ------------------------------------------
    perk_p = float(perks.get("potency", 1.0) or 1.0)
    perk_d = float(perks.get("duration", 1.0) or 1.0)
    prod_p, prod_d = float(prow.get("potency", 1.0)), float(prow.get("duration", 1.0))
    plan.carried = {"potency": p_in, "duration": d_in, "drawback": w_in}
    plan.factors = {
        "potency": [float(mrow_p), prod_p, perk_p],
        "duration": [float(mrow_d), prod_d, perk_d],
        # Harm grows with concentration and the form's strength, as the dose does; the
        # crafter's perks are a benefit and leave it alone.
        "drawback": [float(mrow_p), prod_p],
    }
    plan.pre = {k: combine_multipliers(plan.carried[k], plan.factors[k])
                for k in plan.carried}

    # --- which effects the form can carry --------------------------------------------
    seen = set()
    specs = []
    for m, _ in carried:
        for spec in m.base_specs:
            sig = _json.dumps(spec, sort_keys=True, default=str)
            if sig not in seen:
                seen.add(sig)
                specs.append(dict(spec))
    routes = set(prow.get("routes") or BODY_ROUTES)
    kept = []
    for spec in specs:
        route = _route(spec)
        if route == "external":
            # Never silently kept and never silently lost (plan §5.2).
            plan.dropped.append({"spec": spec, "why": "alchemy only"})
        elif route not in routes:
            plan.dropped.append({"spec": spec, "why":
                                 f"{_a(prow.get('name', plan.form).lower())} cannot carry "
                                 f"{ROUTE_WORDS.get(route, route)}"})
        else:
            kept.append(spec)
    if method == "neutralize":
        harm = _harmful_ids(kept)
        plan.removed = [{"spec": s, "why": "neutralized"} for s in kept if id(s) in harm]
        kept = [s for s in kept if id(s) not in harm]
    # A remedy whose every helpful effect fell away is a poison with a herbal name
    # (Lane A, measured on Harpy Vocal Cord and Salamander Ember Gland: once the external
    # effects go, only the harm is left). Refused, with the reason in words.
    before_harm = _harmful_ids(specs)
    lost_help = [d for d in plan.dropped if id(d["spec"]) not in before_harm]
    kept_harm = _harmful_ids(kept)
    if plan.form == "salve-base":
        # A base is structure, not medicine: ground bark thickens a salve whatever its
        # own effects were (measured live: Breeam, whose every effect is external, was
        # refused as a salve base for carrying nothing). What it does carry is filtered
        # again by the salve, balm or cream it goes into.
        pass
    elif specs and not kept and plan.dropped and method != "neutralize":
        # The form could carry none of it: a poultice of a herb that only works when
        # swallowed is a wet leaf, and making one would spend the herb for nothing.
        plan.problems.append(
            f"{_a(prow.get('name', plan.form).lower()).capitalize()} can carry none of what this does "
            f"({plan.dropped[0]['why']}).")
    elif lost_help and kept and all(id(s) in kept_harm for s in kept):
        if all(d["why"] == "alchemy only" for d in lost_help):
            plan.problems.append("Everything this does that helps is alchemy's; only "
                                 "its harm would be left in a herbal remedy.")
        else:
            plan.problems.append(
                f"Everything this does that helps, a "
                f"{prow.get('name', plan.form).lower()} cannot carry; only its harm "
                f"would be left.")
    # A save whose harm was dropped gates nothing; left on, it would read as a poison.
    harm = _harmful_ids(kept)
    gated_by = {str(s.get("from")) for s in kept
                if id(s) in harm and s.get("type") != "save_gate"}
    plan.base_specs = [s for s in kept if s.get("type") != "save_gate"
                       or str(s.get("from")) in gated_by or id(s) not in harm]

    # --- the name and the time ------------------------------------------------------
    plan.name = _product_name(method, plan.form, lead, prow)
    if row.get("minutes_per_batch"):
        # A batch method (Dry; the owner's ruling of 2026-11-01): one batch takes its
        # time however many doses are on the racks, up to what they hold, and more than
        # that takes another batch. Measured on Ansel's save before it: 24 Ground
        # Caranator dried into 12 doses at 480 minutes a dose took 96 hours, and two
        # such steps 8 days. How much one batch holds grows with the Herbalist level, as
        # Ultimate Wilderness p.152 has an herbalist prepare as many doses at once as
        # she has ranks in Profession (herbalist); the size per level is the rule row's.
        plan.batch_capacity = max(1, int(row.get("batch_doses_per_level", 1)) * level)
        plan.batches = math.ceil(plan.doses / plan.batch_capacity) if plan.doses else 0
        plan.minutes = int(row["minutes_per_batch"]) * plan.batches
        return plan
    per_dose = row.get("minutes_per_dose", 0)
    if isinstance(per_dose, dict):
        per_dose = per_dose.get(plan.form, max(per_dose.values()))
    plan.minutes = int(per_dose) * plan.doses
    return plan


def _product_name(method: str, form: str | None, lead: Material, prow: dict) -> str:
    who = _lead_name(lead)
    if method == "neutralize":
        return f"Neutralised {heal_name(lead.name) if lead.crafted else who}"
    if method == "reduce" and form in _LIQUID_PRODUCTS and lead.crafted \
            and lead.stock is not None:
        return lead.stock.base
    if method == "dry" and form == "powder" and lead.crafted and lead.stock is not None:
        return lead.stock.base
    return {
        "powder": f"Ground {who}", "dried": f"Dried {who}",
        "extract": f"{who} Extract", "reduction": f"{who} Reduction",
        "salve-base": f"{who} Salve Base", "infused-oil": f"{who} Infused Oil",
    }.get(form or "", f"{who} {prow.get('name', (form or 'Preparation').title())}")


def combine_multipliers(carried: float, factors) -> float:
    """What a line carries in, combined with one step's multipliers, by the Pathfinder
    rule for multiplying rather than by multiplying.

    The owner's ruling of 2026-11-01: potency stays uncapped but must grow much more
    slowly. Until then every step multiplied the running strength by method x product x
    perk x quality, so a chain compounded geometrically. Measured on Ansel's save: a
    four-step Caranator Decoction (grind Fine, dry Flawless +4, brew Flawless +6, reduce
    Flawless +4, read off his transcript) reached potency 33.7147 and duration 30.6497, a
    +2 Will became +68 for 31 hours; at Flawless +9 every step the same chain is 128x
    (+257). docs/herbalism-revamp-plan.md §17 has the full before/after table.

    Prior art. The Core Rulebook's Multiplying rule (Getting Started, Common Terms; also
    d20pfsrd's glossary): "When you are asked to apply more than one multiplier to a
    roll, the multipliers are not multiplied by one another. Instead, you combine them
    into a single multiplier, with each extra multiple adding 1 less than its value to
    the first multiple" -- x2 twice is x3. League of Legends abandoned compounding
    percentage cooldown reduction for linear Ability Haste in patch 10.23 (its notes: the
    old stat was "more valuable the more of it you got"); Path of Exile pools
    every "increased" modifier additively for the same reason. So every multiplier above
    1 adds what it is worth less one, whether it is this step's or one carried in, and the
    strength grows linearly in steps and in quality, never geometrically.

    A multiplier BELOW 1 (Crude hands, Neutralize's 0.9, the drawback's softening by good
    hands) still multiplies. The Core Rulebook's rule speaks only of multiples; I could
    not find a Pathfinder rule for stacked fractions, so this keeps what the bench always
    did with them. It also keeps the drawback's softening exactly as it was (0.25 per
    Flawless step, and on past Flawless, `quality_mult`), so a long chain made in good
    hands still sheds its harm, and nothing can reach zero or go negative.
    """
    gain = sum(float(f) - 1.0 for f in factors if float(f) > 1.0)
    keep = math.prod(float(f) for f in factors if float(f) < 1.0)
    return (float(carried) + gain) * keep


def strength_at(plan: StepPlan, tier: int) -> dict:
    """The step's strength at the tier the hands earned: what it carries in combined with
    the method, the form, the perks and that tier's quality (`combine_multipliers`)."""
    return {k: combine_multipliers(plan.carried[k],
                                   list(plan.factors[k]) + [quality_mult(k, tier)])
            for k in ("potency", "duration", "drawback")}


def make(plan: StepPlan, tier: int, now_minute: int) -> Stock:
    """What a finished step puts on the shelf, at the tier the player's hands earned."""
    s = strength_at(plan, tier)
    specs = bake(plan.base_specs, s["potency"], s["duration"], s["drawback"])
    harm = _harmful_ids(specs)
    effects = [f"{x.get('from')}: {effectspec.render(x)}" if x.get("from")
               else effectspec.render(x) for x in specs if id(x) not in harm]
    drawbacks = [f"{x.get('from')}: {effectspec.render(x)}" if x.get("from")
                 else effectspec.render(x) for x in specs if id(x) in harm]
    prow = product_row(plan.form)
    keeps = prow.get("keeps_minutes")
    if keeps is None and plan.lead is not None:
        from . import herbprep

        keeps = herbprep.spoils_after(plan.lead.prep) * 60
    ready = (int(now_minute) + int(plan.ready_minutes)) if plan.ready_minutes else None
    start = ready if ready is not None else int(now_minute)
    kind = prow.get("kind", "product")
    how = ["in_progress"] if ready is not None else (
        ["ingredient"] if kind == "intermediate" or plan.form is None else [])
    return Stock(
        base=plan.name, concentration=plan.concentration + 1, tier=plan.tier,
        potency=1.0, count=plan.doses, craft=TRACK_ID,
        effects=effects, drawbacks=drawbacks, specs=specs,
        from_ingredients=list(plan.from_ingredients),
        kind="crafted", how=how,
        form=plan.form, state=plan.state, quality=int(tier),
        ready_minute=ready,
        spoils_minute=(start + int(keeps)) if keeps else None,
        base_specs=[dict(x) for x in plan.base_specs],
        mults={k: round(v, 6) for k, v in s.items()},
        worked=list(plan.worked),
        # A steep goes straight into In progress (rules/inprogress.py): made now, ready on
        # its day, and waiting there until it is collected.
        work=(inprogress.block(craft=TRACK_ID, label="Steeping", doing="steeping",
                               started=int(now_minute), minutes=int(plan.ready_minutes))
              if ready is not None else None),
    )


def failure_losses(plan: StepPlan, miss: int) -> list[tuple[Material, int]]:
    """What a failed roll ruins, by the book's Craft rule (plan §2): miss by 4 or less
    and only the time is lost; miss by 5 or more and half the materials are ruined,
    rounded up, across the whole bulk stack. Shared out by each material's share of the
    stack, largest remainders first, so the total is exactly half rounded up."""
    if miss < 5:
        return []
    total = sum(n for _, n in plan.consumes)
    ruin = math.ceil(total / 2)
    shares = []
    for m, n in plan.consumes:
        exact = n * ruin / total if total else 0
        shares.append([m, int(exact), exact - int(exact), n])
    left = ruin - sum(s[1] for s in shares)
    for s in sorted(shares, key=lambda s: -s[2]):
        if left <= 0:
            break
        if s[1] < s[3]:
            s[1] += 1
            left -= 1
    return [(m, k) for m, k, _, _ in shares if k > 0]


def spend(actor, consumes: list[tuple[Material, int]]) -> list[dict]:
    """Take materials out of the satchel. Raw ones from the counts, made ones off the
    shelf, by the key the satchel was read under."""
    out = []
    for m, n in consumes:
        if n <= 0:
            continue
        if m.key.startswith("stock:"):
            took = actor.take_stock(m.key.split(":", 1)[1], n)
        else:
            took = actor.spend(m.ingredient_id, n)
        if took:
            out.append({"key": m.key, "name": m.name, "count": int(took)})
    return out


def product_card(plan: StepPlan, actor=None) -> dict:
    """The result tag's content (contracts §3.2 `product`): what this step would make,
    with each effect at every tier from Crude to the ceiling. Unknown properties are
    counted, never shown (plan §8.1): not on the card, not as a dropped line."""
    from . import herbknowledge

    prow = product_row(plan.form)
    known_by_ing: dict[str, set] = {}

    def known(spec) -> bool:
        origin = spec.get("origin") or {}
        iid = origin.get("ingredient")
        if not iid or actor is None:
            return True
        if iid not in known_by_ing:
            try:
                known_by_ing[iid] = set(herbknowledge.known_keys(actor, ing_mod.get(iid)))
            except KeyError:
                known_by_ing[iid] = set()
        return origin.get("key") in known_by_ing[iid]

    tiers = list(range(0, plan.ceiling + 1))
    baked = {t: bake(plan.base_specs, **strength_at(plan, t)) for t in tiers}
    harm = _harmful_ids(plan.base_specs)
    effects, drawbacks, unknown = [], [], 0
    for i, spec in enumerate(plan.base_specs):
        if not known(spec):
            unknown += 1
            continue
        line = {"base": effectspec.render({k: v for k, v in spec.items()
                                           if k != "origin"}),
                "from": spec.get("from", ""),
                "by_tier": [effectspec.render(baked[t][i]) for t in tiers]}
        (drawbacks if id(spec) in harm else effects).append(line)
    dropped = []
    for d in plan.dropped + plan.removed:
        if known(d["spec"]):
            dropped.append({"text": effectspec.render(
                {k: v for k, v in d["spec"].items() if k != "origin"}),
                "from": d["spec"].get("from", ""), "why": d["why"]})
        else:
            unknown += 0      # an unknown dropped property stays unknown and uncounted
    sources = []
    for ref in plan.from_ingredients:
        try:
            ing = ing_mod.get(base_ingredient_id(ref))
        except KeyError:
            continue
        if ing.text:
            sources.append(f"{ing.name}: {ing.text}")
    return {"name": plan.name, "form": plan.form, "state": plan.state,
            "taken": prow.get("taken", ""), "action": prow.get("action", ""),
            "keeps_minutes": prow.get("keeps_minutes"),
            "routes": list(prow.get("routes") or []),
            "unknown": unknown, "effects": effects, "drawbacks": drawbacks,
            "dropped": dropped, "doses": plan.doses, "tier": plan.tier,
            "concentration": plan.concentration,
            "ready_minutes": plan.ready_minutes,
            "ladder": [quality_name(t) for t in tiers],
            "source_text": "\n\n".join(dict.fromkeys(sources))}


def revealed_keys(stock: Stock) -> dict[str, list[str]]:
    """`{ingredient id: [property keys]}` a made thing shows by carrying them (plan §8.1:
    making a product reveals every effect it actually carries)."""
    out: dict[str, list[str]] = {}
    for spec in stock.base_specs:
        origin = spec.get("origin") or {}
        iid, key = origin.get("ingredient"), origin.get("key")
        if iid and key and key not in out.setdefault(iid, []):
            out[iid].append(key)
    return out


def tuning_for(plan: StepPlan) -> dict:
    """The minigame's numbers (contracts §3.3): from the method's rule row, with the
    difficulty by part, harder for root and bark, easier for leaf and flower. The same at
    every level: the owner chose "quality only", so skill raises the ceiling, not the
    window (plan §9.2)."""
    row = method_row(plan.method) or {}
    tun = row.get("tuning") or {}
    diff = tun.get("difficulty") or {}
    ceiling = max(0, int(plan.ceiling))
    return {"method": plan.method, "part": plan.part,
            "difficulty": float(diff.get(plan.part, diff.get("default", 0.5))),
            "seconds": tun.get("seconds", 6), "beats": tun.get("beats", 6),
            "infusion": plan.form == "infusion",
            # The ladder the strip shows while the game runs: every name to the ceiling
            # and each tier's lower score bound, by the same even spread `tier_from_score`
            # uses at finish, so the live word and the landed tier cannot disagree.
            "names": [quality_name(t) for t in range(ceiling + 1)],
            # Unrounded: 0.3333 x 3 floors to Crude where the strip showed Sound (measured
            # by the test that pins this, before the epsilon in `tier_from_score`).
            "bands": [t / (ceiling + 1) for t in range(ceiling + 1)]}


# --- settling a herb bench step (shared by the bench and a typed line) -------------------
#
# Lifted out of play/bench_views.py on 2026-10-28 for the engine's `make` op
# (rules/typed_craft.py): "I brew a tea from the yarrow" settles its step by the same rule
# the bench's roll and finish do, never a second copy of it.

HERB_TRACK = "herbalist"


def settle_miss(actor, progress, plan: StepPlan, miss: int) -> dict:
    """A failed roll at the herb bench (`failure_losses`, the book's rule as the plan
    states it): what is ruined is spent now, and the stack is paid as that many failed
    steps. Returns {"lost", "said", "mastery"}."""
    track = wc.get(HERB_TRACK)
    lost = spend(actor, failure_losses(plan, miss))
    if lost:
        ruined = ", ".join(f"{x['count']} {x['name']}" for x in lost)
        said = f"Missed by {miss}. Half the materials are ruined: {ruined}."
    else:
        said = f"Missed by {miss}. The time is lost; the materials are kept."
    lead = plan.lead
    # The whole stack failed on one roll, so it is that many failed steps (the finish's
    # reason, below).
    got = wc.award_step(track, progress, method=plan.method,
                        ingredient_id=lead.ingredient_id if lead else "",
                        rarity_rank=plan.rank_in, quality_index=0, success=False,
                        name=_lead_name(lead) if lead else "",
                        count=plan.doses, noun="dose")
    return {"lost": lost, "said": said, "mastery": got}


def first_time(progress, key: str) -> bool:
    """Whether this is the first time, recorded in the track's own ledger so it survives
    a save. Keys are `form:<form>` and `herb:<id>`, apart from the (method, ingredient)
    keys the step award uses."""
    seen = int(progress.crafted.get(key, 0))
    progress.crafted[key] = seen + 1
    return seen == 0


def settle_made(actor, progress, plan: StepPlan, tier: int, consumes, *, dice=None,
                now: int = 0) -> dict:
    """A made roll at the herb bench, finished at `tier`: the product is made, the Yield
    perk's d100 rolled on `dice` (none, no roll), the materials in `consumes` (read fresh)
    spent, the product put in the satchel, and the step, the firsts and the discoveries
    paid. Returns {"made": Stock, "count", "lines", "levelled", "discoveries"}.

    A batch pays as its doses made one at a time would (owner, 2026-10-05: "batch
    crafting does not give equivalent experience"): one step per dose, every one paid
    ("batch of 10 should pay 10"), each with its bands and the stack's one quality bonus.
    Doses, not `plan.batch`: three Mint on the mortar at batch 1 is three grinds as surely
    as one Mint at batch 3, and the smallest craft any method allows is one dose. The yield
    perk's extra dose is a gift of the perk, not a step worked, so it is not counted.
    Firsts and discoveries stay once per finish, however many doses."""
    from . import herbknowledge

    track = wc.get(HERB_TRACK)
    made = make(plan, tier, now)
    got_perks = dict(wc.perk_multipliers(progress))
    chance = float(got_perks.get("yield_chance", 0) or 0)
    # A fraction is the contract; a percentage would read as a certainty (bench_views'
    # `perk_multipliers` brings it back to one the same way).
    if chance > 1:
        chance = chance / 100.0
    extra, yield_line = 0, None
    if dice is not None and chance > 0:
        roll = dice.roll("1d100", label="Yield perk", visibility="player")
        need = int(round(chance * 100))
        extra = 1 if roll.total <= need else 0
        yield_line = {"why": f"Yield perk: d100 {roll.total} against {need} or less, "
                             f"{'one more dose' if extra else 'no extra dose'}", "mp": 0}

    spend(actor, list(consumes))
    count = int(made.count) + extra
    actor.add_stock(made, count)

    lines: list[dict] = []
    levelled: list[int] = []
    lead = plan.lead
    got = wc.award_step(track, progress, method=plan.method,
                        ingredient_id=lead.ingredient_id if lead else "",
                        rarity_rank=plan.rank_in, quality_index=tier, success=True,
                        name=_lead_name(lead) if lead else "",
                        count=plan.doses, noun="dose")
    lines += list(got.get("reasons") or [])
    levelled += list(got.get("levelled") or [])

    def bonus(why: str) -> None:
        res = wc.award_bonus(track, progress, why=why, mp=wc.FIRST_MP)
        lines.extend(res.get("reasons") or [])
        levelled.extend(res.get("levelled") or [])

    form_name = product_row(plan.form).get("name", plan.form or "")
    if plan.form and first_time(progress, f"form:{plan.form}"):
        bonus(f"first {form_name.lower()}")
    for m, _ in plan.picks:
        if m.reagent or not m.ingredient_id:
            continue
        if first_time(progress, f"herb:{m.ingredient_id}"):
            bonus(f"first work with {_lead_name(m)}")

    discoveries = []
    how = f"made it, day {int(now) // 1440 + 1}"
    for iid, keys in revealed_keys(made).items():
        new = herbknowledge.reveal(actor, iid, keys, how)
        try:
            ing = ing_mod.get(iid)
        except KeyError:
            continue
        pairs = ing.pairs
        for k in new:
            idx = int(k[1:]) if k[1:].isdigit() else -1
            text = pairs[idx][0] if 0 <= idx < len(pairs) else ""
            discoveries.append({"ingredient_id": iid, "name": ing.name, "key": k,
                                "text": text})
            bonus(f"learned: {ing.name}, {text}" if text else f"learned: {ing.name}")
    if yield_line:
        lines.append(yield_line)
    return {"made": made, "count": count, "lines": lines, "levelled": levelled,
            "discoveries": discoveries}
