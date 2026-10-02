"""Crafting chains: what a set of ingredients and a sequence of methods produces.

The Herbalist document's own framing — *"crafting is no longer limited to single-step
recipes. Complex items require Crafting Chains—combining multiple methods across
different tools"* — so a craft is an ordered list of methods applied to a set of
ingredients, and the chain is the thing that gets validated, not the recipe.

Two rules here are the author's percentages made precise, because 1e has none and a
percentage without a rounding rule is a bug waiting for a report:

  Costs and penalties round **down**, benefits round **up**. A character is never
  surprised in the direction that hurts them, and `mix` at 80% of a 1d4 is 1d4 rather
  than a silent 0.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import consumables as con
from . import effectspec
from . import ingredients as ing_mod
from . import worldclass as wc

# Methods that change what a mixture is worth, as multipliers on its potency. Everything
# else in the method list shapes or enables rather than scaling.
POTENCY = {
    "mix": 0.80,        # "retains the primary effects of both at 80% of base strength"
    "distill": 1.25,    # "increases the strength of a concoction's primary effect by 25%"
    "refine": 1.25,     # "increases the effectiveness of any crafted item to 125%"
}

# Methods that remove an ingredient's drawback rather than scaling it.
CLEANSING = ("purify", "neutralize")

# The method that has to come last if it is used at all: you brew the mixture, you do not
# grind the tea.
FINISHING = ("brew", "catalyst crafting")


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


class CraftError(ValueError):
    """The chain cannot be attempted. Raised before anything is scored, so a chain the
    character cannot make never advances their track."""


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
    )


# The methods the owner retired on 2026-10-02 (plan §2, "Methods removed"), by the shape
# word the old chain wrote onto everything they made. Read off the name because that is
# the only record a pre-revamp jar carries of how it was made — the same reading
# `is_tincture` already does. Longest first, so "Purified Draught" wins over a bare word.
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


@dataclass
class Chain:
    track: str
    methods: list[str] = field(default_factory=list)
    ingredient_ids: list[str] = field(default_factory=list)
    name: str = ""
    # Crafted items going back into the pot, as {stock id: how many}. Kept apart from raw
    # ingredients because these are *spent*: the shelf of herbs is bottomless for now,
    # a jar of tea is not, and concentration only means anything if the pair is consumed.
    stock_used: dict[str, int] = field(default_factory=dict)

    @property
    def stages(self) -> int:
        return len(self.methods)


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


def chain_from_body(body: dict) -> Chain:
    """The bench's POST body as a chain.

    Herbalism's half of the interface `rules/benches.py` routes on. It lived in
    `play/craft_views.py` as a private helper, which was fine while one craft had rules
    and wrong the moment five did: the view would have needed to know each craft's chain
    shape. The craft knows its own shape; the view asks for it.

    Tolerant by design — a missing key is an empty chain, not an error — because the
    problems list is where a chain is judged, and a half-built chain is the normal state
    of the page while somebody is still clicking.
    """
    return Chain(
        track=str(body.get("track") or "herbalist"),
        methods=[str(m).strip().lower() for m in body.get("methods") or []],
        ingredient_ids=[str(i).strip().lower()
                        for i in (body.get("materials") or body.get("ingredients") or [])],
        name=str(body.get("name", "")).strip(),
        stock_used={str(k): int(v) for k, v in (body.get("stock") or {}).items()
                    if int(v) > 0},
    )


@dataclass
class Result:
    name: str
    tier: str
    rank: int
    stages: int
    potency: float
    cleansed: bool
    risky: bool
    dc: int
    chance: int
    ingredients: list[dict]
    effects: list[str]
    drawbacks: list[str]
    # The same drawbacks, grouped and structured: one entry per poison, each with its save
    # and the effects that save gates. `drawbacks` is what a plain card shows; this is what
    # the bench draws, so the save can sit visibly in front of the harm it governs.
    poisons: list[dict] = field(default_factory=list)
    # What Purify or Neutralize took out, named. Empty unless the chain cleansed something.
    removed: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    # The prose the effects were read out of, kept so nothing is lost to the summary.
    described: list[dict] = field(default_factory=list)
    # What the successful craft puts on the shelf, and what it takes off.
    output: dict | None = None
    consumes: dict[str, int] = field(default_factory=dict)
    consumes_raw: dict[str, int] = field(default_factory=dict)
    concentrating: bool = False
    # The crafter's own bonus on this chain, and what it is made of. Carried rather than
    # only the percentage it implies, because the roll is a check now: the bench shows
    # d20 + bonus against the DC, and a player who can see the terms can see what would
    # improve them.
    bonus: int = 0
    terms: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "name": self.name, "tier": self.tier, "rank": self.rank,
            "stages": self.stages, "potency": round(self.potency, 2),
            "cleansed": self.cleansed, "risky": self.risky, "dc": self.dc,
            "chance": self.chance, "bonus": self.bonus, "terms": self.terms,
            "ingredients": self.ingredients,
            "effects": self.effects, "drawbacks": self.drawbacks,
            "poisons": self.poisons, "removed": self.removed,
            "problems": self.problems, "described": self.described,
            "output": self.output,
            "consumes": self.consumes, "consumes_raw": self.consumes_raw,
            "concentrating": self.concentrating,
        }


def _in_the_pot(items, used) -> list[tuple[str, str, dict]]:
    """Everything in the pot as (source, card line, spec), in order, deduplicated.

    One walk rather than two. `mechanics` read `Ingredient.lines` and `mechanical_specs`
    read `Ingredient.specs`, and nothing tied entry n of one to entry n of the other —
    harmless while every line was printed the same way, and not harmless at all now that
    the spec's *type* decides which panel its line appears in.

    Deduplicated on "source: line": two components that both cure fatigue cure it once,
    and an item that lists it twice reads as a bug on the card. Per source rather than
    globally, because two ingredients doing the same thing is a fact the card should keep.

    A held item is read from its specs, not its prose, because those carry the `from` mark
    that says which original ingredient each effect came out of — the only thing tying a
    poison's save to the damage it gates. Stock saved before `specs` existed has none, and
    falls back to the prose it does have rather than contributing nothing.
    """
    out: list[tuple[str, str, dict]] = []
    seen: set[str] = set()

    def add(source: str, line: str, spec: dict) -> None:
        key = f"{source}: {line}"
        if line and key not in seen:
            seen.add(key)
            # Marked here, once, so the spec that goes to the engine and the spec that
            # decides which panel the line lands in are the same object.
            out.append((source, line, {**spec, "from": spec.get("from") or source}
                        if spec else {}))

    for i in items:
        for line, spec in i.pairs:
            add(i.name, line, spec)
    for held, _ in used:
        if held.specs:
            for spec in held.specs:
                add(str(spec.get("from") or held.base), effectspec.render(spec), spec)
        else:
            for line in held.effects:
                add(held.base, line, {})
    return out


def _at_strength(line: str, spec: dict, potency: float) -> str:
    """A benefit's card line at the strength the brew delivers it.

    Only the flat bonuses `consumables.scaled_bonus` raises, asked through that one
    function so the card and the drink cannot disagree; the authored number stays in the
    line so the player can see where the rest came from — "+26 Strength (permanent;
    +20 at 130%)". Dice lines are left as written: potency is stated once beside them.
    """
    if not spec or str(spec.get("type", "")) not in con.SCALED_BONUSES:
        return line
    authored = con.scaled_bonus(spec.get("amount", 0), 1.0)
    landed = con.scaled_bonus(spec.get("amount", 0), potency)
    if landed == authored:
        return line
    shown = effectspec.render({**spec, "amount": landed})
    note = f"{authored:+d} at {round(potency * 100)}%"
    if shown.endswith(")"):
        return f"{shown[:-1]}; {note})"
    return f"{shown} ({note})"


@dataclass
class Sifted:
    """What is in the pot, sorted into what it does for you and what it does to you.

    Measured on the shipped corpus before this existed: 99 of the 178 effects the 161
    ingredients carry are harm — damage, ability damage, conditions, penalties and the
    saves that gate them — and every one of them was printed under "Effects" beside the
    bonuses, with the saves floating free of the harm they gate. 72 of the 161 entries
    were affected.
    """
    effects: list[str] = field(default_factory=list)
    drawbacks: list[str] = field(default_factory=list)
    poisons: list[con.Poison] = field(default_factory=list)
    # Harm that gates nothing and is gated by nothing: a flat -2 to all actions.
    penalties: list[dict] = field(default_factory=list)
    specs: list[dict] = field(default_factory=list)
    # The specs that are *not* harm — what is left of the item once it has been purified.
    benefits: list[dict] = field(default_factory=list)


def sift(items, used, potency: float = 1.0) -> Sifted:
    """The card's two lists: what each component does for you, and what it does to you.

    Sifted out of the descriptions rather than printed whole. The source is written for a
    person — "When dried and ground into a powder, the mottled red and gray bark of this
    shrub is a boon to healers. When applied to a wound, leechwort grants a +1 alchemical
    bonus on all Heal checks..." — and a recipe card that prints both sentences buries the
    only two numbers in it.

    The chain's potency multiplier is *not* stamped on every line. It is one property of
    the result and is stated once, beside the rarity and the DC; repeating it on each
    effect was noise on every card in the app. But a flat bonus the potency RAISES is
    printed at the strength it lands with (`_at_strength`): the brewed Power leaf's card
    said "+20 Strength" and drinking it gave +26 (playtest 2026-09-30), because the card
    and the drink read the same spec through two different rules.
    """
    triples = _in_the_pot(items, used)
    specs = [spec for _, _, spec in triples if spec]
    sorted_out = con.sort_harm(specs)

    effects = [f"{source}: {_at_strength(line, spec, potency)}"
               for source, line, spec in triples
               if not spec or any(spec is b for b in sorted_out.benefits)]
    drawbacks = [p.line for p in sorted_out.poisons]
    # Penalties are drawbacks but not poisons: a -2 to all actions hurts whoever drinks it
    # and gates nothing, so it is listed on its own rather than folded into a save it
    # never had.
    for spec in sorted_out.penalties:
        line = effectspec.render(spec)
        source = spec.get("from")
        drawbacks.append(f"{source}: {line}" if source else line)
    return Sifted(effects=effects, drawbacks=drawbacks, poisons=sorted_out.poisons,
                  penalties=sorted_out.penalties, specs=specs,
                  benefits=sorted_out.benefits)


def mechanics(items, used) -> list[str]:
    """The card's effect list — what the item does *for* you.

    Harm no longer appears here; it is a drawback, and `sift` puts it there.
    """
    return sift(items, used).effects


def mechanical_specs(items, used) -> list[dict]:
    """The same effects as `mechanics`, structured rather than rendered.

    Kept as a second function rather than changing `mechanics`'s return type, because
    `mechanics` feeds the card and callers read strings from it. This feeds the engine —
    without it a crafted potion is a paragraph, and drinking one could only ever have been
    narration. Harm included: the Drawbacks panel is a matter of presentation, and a
    poison that stopped poisoning people when it moved panels would be a worse bug than
    the one being fixed.
    """
    return sift(items, used).specs


def descriptions(items) -> list[dict]:
    """The prose the mechanics were read out of, kept for whoever wants it.

    Nothing is thrown away — a pattern that cannot claim a clause leaves it here rather
    than dropping it, so the card can be short without the detail being lost.
    """
    return [{"name": i.name, "text": i.text} for i in items if i.text]


def preview(track_id: str, level: int, chain: Chain,
            stock: dict | None = None, satchel: dict | None = None,
            carrier=None, now_minute: int | None = None) -> Result:
    """What this chain would make, and how likely it is to work.

    THE RETIRED CHAIN BENCH. Herbalism's live bench is the step model at the foot of this
    module (`plan_step`, docs/herbalism-revamp-plan.md): one method per step, one roll,
    one minigame, the product back on the shelf. The old /craft/ page refuses herbalism
    chains now (play/craft_views.py), so nothing a player clicks reaches this. It is kept
    as a library because the four newer benches mirror its surface and a few tests in
    other lanes still read its card arithmetic; the methods it knew that the owner retired
    (distill, purify, refine, preserve, catalyst crafting) leave the Herbalist's own
    document, and a chain naming one is refused by the track below.

    Never raises for a chain that is merely bad — an empty pot, a method the character
    has not learned, an ingredient beyond their tier all come back as `problems` so the
    page can grey the button and say why. `CraftError` is for chains that cannot be
    described at all.

    `stock` is what the character has already made, so an output can go back in the pot;
    `satchel` is the raw material they are carrying. Raw ingredients are checked against
    the satchel only when one is supplied — passing None means "assume they have it",
    which is what every caller wanted before foraging existed and what the tests of the
    chain rules still want.
    """
    track = wc.get(track_id)
    # The check counts every level, endless ones included (plan §5.3: "each endless level
    # adds +1 to the check through the Herbalist N term"); only the unlock table is read at
    # the last level it writes down. Clamping both put a Herbalist 6 on Herbalist 3's +3.
    check_level = max(1, int(level))
    level = max(1, min(int(level), track.max_level))
    known = track.unlocked_methods(level)
    ceiling = wc.tier_rank(track.at(level).max_tier)
    have: dict[str, Stock] = dict(stock or {})

    problems: list[str] = []
    items = []
    wanted: dict[str, int] = {}
    for iid in chain.ingredient_ids:
        try:
            items.append(ing_mod.get(iid))
            wanted[iid] = wanted.get(iid, 0) + 1
        except KeyError:
            problems.append(f"No such ingredient: {iid}.")

    if satchel is not None:
        for iid, n in wanted.items():
            # `carrying`, not `have`: `have` is the shelf of crafted jars three lines
            # up, and reusing the name rebound it to an integer — so the very next loop
            # called `.get` on an int and every chain that put a raw herb *and* a jar in
            # the same pot died with an AttributeError. Which is most infusions.
            carrying = int(satchel.get(iid, 0))
            if carrying < n:
                name = ing_mod.get(iid).name
                problems.append(
                    f"{name}: you are carrying {carrying}, the chain wants {n}."
                    if carrying else f"You have no {name}. Forage for it.")

    used: list[tuple[Stock, int]] = []
    for sid, n in chain.stock_used.items():
        n = int(n)
        if n <= 0:
            continue
        held = have.get(sid)
        if held is None:
            problems.append(f"You are not carrying any {sid}.")
        elif held.count < n:
            problems.append(f"{held.name}: you have {held.count}, the chain wants {n}.")
        else:
            used.append((held, n))

    # The old x2 concentration branch lived here (two doses of a jar at the still). It
    # was retired with the still itself; see `CONCENTRATE_RARITY_STEP`.

    for m in chain.methods:
        if m not in track.unlocked_methods(track.max_level):
            problems.append(f"{track.name} has no method called {m!r}.")
        elif m not in known:
            need = next(l.level for l in sorted(track.levels, key=lambda x: x.level)
                        if m in l.methods)
            problems.append(f"{m.title()} is learned at {track.name} {need}.")

    for i in items:
        if i.rank > ceiling:
            problems.append(f"{i.name} is {i.tier}; {track.name} {level} works "
                            f"{track.at(level).max_tier} at best.")
    for held, _ in used:
        if held.rank > ceiling:
            problems.append(f"{held.name} is {held.tier}; {track.name} {level} works "
                            f"{track.at(level).max_tier} at best.")

    if not items and not used:
        problems.append("Nothing in the pot.")
    if not chain.methods:
        problems.append("No method chosen.")

    for m in chain.methods[:-1]:
        if m in FINISHING:
            problems.append(f"{m.title()} finishes a chain; nothing follows it.")

    problems.extend(_preparation_problems(items, chain.methods))
    problems.extend(_spoiled_problems(items, carrier, now_minute))
    problems.extend(_infusion_problems(items, used, chain.methods))
    problems.extend(_infusion_additions(items, used, chain.methods))
    problems.extend(_distillation_problems(items, used, chain.methods))

    # The result is as rare as its rarest component, which is also what gates who can
    # make it — a common chain with one legendary petal in it is a legendary brew.
    rank = max([i.rank for i in items] + [h.rank for h, _ in used], default=1)
    tier = wc.TIERS[rank - 1]

    potency = 1.0
    for m in chain.methods:
        potency *= POTENCY.get(m, 1.0)
    # Grinding and brewing pay, and pay more in better hands. `herbprep` holds the
    # numbers so the bench and the ingredient rules cannot disagree about what a grind
    # is worth; the per-level term is why a master gets more out of the same leaf.
    from . import herbprep

    for m in chain.methods:
        if m in ("grind", "brew"):
            potency *= 1.0 + herbprep.potency_change(m, level)
    # A crafted input brings its own concentration with it, so a compound made from a
    # doubled tea is stronger than one made from a plain one.
    for held, n in used:
        potency *= held.potency

    cleansed = any(m in CLEANSING for m in chain.methods)
    risky = (any(i.risky for i in items) or any(h.drawbacks for h, _ in used)) \
        and not cleansed

    sifted = sift(items, used, potency)
    effects, drawbacks = list(sifted.effects), list(sifted.drawbacks)
    poisoned = [p.as_dict() for p in sifted.poisons]
    specs = sifted.specs

    # What is dangerous about a component but has no mechanic to name. 30 of the corpus's
    # ingredients are marked risky and extract nothing harmful at all, because the danger
    # is in the harvesting rather than in the dose. Those still deserve a warning — but
    # one that says which ingredient it is about, instead of the boilerplate sentence that
    # used to be the entire Drawbacks panel however many poisons were in the pot.
    named = {p.source for p in sifted.poisons}
    rough = [i.name for i in items if i.risky and i.name not in named]
    rough += [h.name for h, _ in used if h.drawbacks and h.name not in named]

    # Purification with nothing to purify. The chain already worked out that it would
    # find nothing and wrote "found nothing harmful to remove" on the jar as a note —
    # which meant the step ran, spent the ingredients, advanced the track and produced a
    # Purified Draught of a thing that was never impure. It is a refusal now.
    if "purify" in chain.methods and not (sifted.poisons or sifted.penalties or rough):
        problems.append(
            "Purify has nothing to remove: nothing in the pot is harmful. "
            "It strips poisons and penalties, and there are none here.")

    removed: list[str] = []
    if cleansed:
        verb = " and ".join(sorted({m.title() for m in chain.methods if m in CLEANSING}))
        removed = [f"{verb} removed {p.source}'s poison: {p.body}."
                   if p.source else f"{verb} removed the poison: {p.body}."
                   for p in sifted.poisons]
        for spec in sifted.penalties:
            removed.append(f"{verb} removed {effectspec.render(spec)} "
                           f"({spec.get('from') or 'the mixture'}).")
        if rough:
            removed.append(f"{verb} removed the handling risks of "
                           f"{', '.join(sorted(set(rough)))}.")
        if not removed:
            removed = [f"{verb} found nothing harmful to remove."]
        # Struck from the item itself, not only from the card. Before this, purifying set
        # a flag and appended a sentence while the harmful specs stayed on the Stock — so
        # a "Purified Draught of Skull Orchid" still did every point of its Constitution
        # damage when somebody drank it, and could still be thrown at people. The method
        # that the author says "completely removes its negative side effects" removed
        # nothing whatsoever.
        specs = list(sifted.benefits)
        drawbacks = []
        poisoned = []
        # Kept on the effect list rather than only on the preview, so the jar in the
        # satchel says what was taken out of it long after the bench is closed.
        effects = effects + removed
    elif rough:
        drawbacks.append(
            f"Untreated hazardous components: {', '.join(sorted(set(rough)))}. "
            f"Harvesting and handling risks still apply. "
            f"Purify or Neutralize removes them.")

    dc = _dc(items, rank, chain.stages)
    # d20 + track level + half character level + Wisdom, itemised for the bench.
    _terms = check_terms(carrier, check_level)
    _bonus = sum(x["value"] for x in _terms)

    # An infusion is the tincture, enriched — not a new thing named after whatever went
    # into it. It came out named "Woundwort Infusion" at concentration 1, so infusing a
    # Tier 3 tincture with a herb threw away both the identity and the two doses that
    # bought the concentration. The base keeps its name, its concentration and its
    # place in the satchel; what was added rides along in the name so two differently
    # infused jars of the same tincture do not stack as one.
    infused = _infusion_base(used, chain.methods)
    if infused is not None:
        added = [i.name for i in items] + [h.base for h, _ in used if h is not infused]
        name = chain.name or _infused_name(infused, added)
        concentration = infused.concentration
    else:
        name = chain.name or _name_for(items or [h for h, _ in used], chain.methods)
        concentration = 1

    out = Stock(base=name, concentration=concentration, tier=tier, potency=potency,
                craft=track.id, effects=effects, drawbacks=drawbacks,
                specs=specs,
                from_ingredients=[i.id for i in items]
                + [h.id for h, _ in used])
    return Result(
        name=name, tier=tier, rank=rank, stages=chain.stages, potency=potency,
        cleansed=cleansed, risky=risky, dc=dc,
        chance=_chance(dc, _bonus, problems), bonus=_bonus, terms=_terms,
        ingredients=[i.as_dict() for i in items] + [h.as_dict() for h, _ in used],
        effects=effects, drawbacks=drawbacks, poisons=poisoned, removed=removed,
        problems=problems,
        described=descriptions(items),
        output=out.as_dict(),
        consumes={h.id: n for h, n in used},
        consumes_raw=dict(wanted),
    )


def _dc(items, rank: int, stages: int) -> int:
    """Hardest ingredient sets the floor; length of the chain adds to it.

    Ingredients that carry their own DC use it — 31 of them do, and an authored number
    beats a derived one every time. The rest fall back on their tier.
    """
    stated = [i.craft_dc for i in items if i.craft_dc is not None]
    base = max(stated) if stated else 5 + 5 * rank
    return base + 2 * max(0, stages - 1)


def check_terms(actor, level: int) -> list[dict]:
    """What a crafter adds to the die, itemised.

    The author's formula: **d20 + track level + half character level + Wisdom**. It
    replaced `3 * level + 2 * (level - rank)`, which was invented here and had no
    counterpart anywhere in 1e — and, being invisible, could not be reasoned about at the
    bench. Every term now comes from somewhere the player can point at on their sheet.

    Itemised rather than summed because the sum is the boring half. "+9" says nothing;
    "Herbalist 4, half level +3, Wis +2" says which of the three to go and improve.
    """
    track_level = max(0, int(level or 0))
    char_level = max(1, int(getattr(actor, "level", 1) or 1)) if actor else 1
    wis = int(actor.ability_mod("wis")) if actor is not None else 0
    return [
        {"label": f"Herbalist {track_level}", "value": track_level},
        # Half level, rounded down, as every half-level term in 1e rounds.
        {"label": f"half character level ({char_level})", "value": char_level // 2},
        {"label": "Wisdom", "value": wis},
    ]


def check_bonus(actor, level: int) -> int:
    return sum(t["value"] for t in check_terms(actor, level))


def _chance(dc: int, bonus: int, problems: list[str] = ()) -> int:
    """Percent chance the check makes the DC, for the label on the button.

    Derived from the check rather than being the mechanic: the roll is d20 + bonus against
    the DC, and this only says what that comes to. Clamped to 5-95 because a natural 1
    always fails and a natural 20 always succeeds, so no craft is ever certain either way
    and the number should not claim otherwise.
    """
    if problems:
        return 0
    need = dc - bonus
    chance = int(round(100 * (21 - need) / 20))
    return max(5, min(95, chance))


SHAPE_WORDS = {
    "grind": "Powder", "mix": "Compound", "brew": "Tea", "preserve": "Preserve",
    "extract": "Extract", "distill": "Tincture", "purify": "Purified Draught",
    "infuse": "Infusion", "neutralize": "Neutralised Draught", "refine": "Elixir",
    "catalyst crafting": "Catalyst",
}


# The bench's own method names against the preparation steps `rules/herbprep.py`
# knows. `neutralize` is spelled the American way here and the British way there;
# mapping rather than renaming leaves every saved chain readable.
_AS_STEP = {"grind": "grind", "mix": "mix", "brew": "brew", "extract": "extract",
            "neutralize": "neutralise", "preserve": "preserve"}


# What each method leaves in the pot, read off the shape word it already names its output
# with — so there is one statement in the code of what a brew produces, not two that can
# drift. `mix` makes a "Compound", which is whatever went into it, so it is in neither set
# and carries the pot's form through unchanged.
LIQUID_SHAPES = {"Tea", "Tincture", "Purified Draught", "Infusion",
                 "Neutralised Draught", "Elixir"}
SOLID_SHAPES = {"Powder", "Preserve", "Extract", "Catalyst"}


def pot_is_liquid(items, used, methods=()) -> bool:
    """Whether there is anything pourable in the pot once `methods` have been worked.

    A property of the pot rather than of any one ingredient: brewing turns everything in
    it into a tea, and grinding a tea is not a question the ingredients can answer on
    their own.
    """
    from . import herbprep

    liquid = any(herbprep.Prep.of(i).liquid for i in items) \
        or any(is_liquid_stock(h) for h, _ in used)
    for m in methods:
        shape = SHAPE_WORDS.get(m)
        if shape in LIQUID_SHAPES:
            liquid = True
        elif shape in SOLID_SHAPES:
            liquid = False
    return liquid


def is_liquid_stock(held) -> bool:
    """Whether a jar on the shelf pours.

    Read off the name, the same way `is_tincture` reads off the name, because the name is
    what the method wrote: `SHAPE_WORDS` turns a brew into a "Tea" and a distillation into
    a "Tincture", and that word is still on the jar hours later.
    """
    name = str(getattr(held, "base", "") or getattr(held, "name", "")).lower()
    return any(shape.lower() in name for shape in LIQUID_SHAPES)


def _distillation_problems(items, used, methods) -> list[str]:
    """Distillation needs a liquid.

    Reported from play: "i can still distill anything — how can i distill a dry leaf or a
    mushroom". You cannot. Distilling is separating a liquid by boiling it off, so there
    has to be a liquid: a tea, a tincture, an ingredient that arrives as sap or gall or
    essence, or the brew you are about to make one step earlier in the same chain.

    The pot's form is carried through the chain in order for the same reason the
    preparation walk is: `grind → distill` and `brew → distill` are the same two methods
    and only one of them is a thing you can do.
    """
    if "distill" not in methods:
        return []

    out = []
    for at, m in enumerate(methods):
        if m != "distill":
            continue
        if pot_is_liquid(items, used, methods[:at]):
            continue
        before = " → ".join(methods[:at])
        out.append(
            f"Distil needs a liquid{f' — after {before} there is none' if before else ''}. "
            f"Brew it into a tea first and distil the tea, or start from something "
            f"that already pours.")
    return out


def _infusion_base(used, methods):
    """The tincture an infusion is being poured into, or None.

    The first tincture in the pot, which is the same one `_infusion_problems` measures
    everything else against — so the jar the rule protects and the jar the result is
    built from are guaranteed to be the same jar.
    """
    if "infuse" not in methods:
        return None
    return next((h for h, _ in used if is_tincture(h)), None)


def _infused_name(base, added) -> str:
    """The tincture's own name, carrying what went into it.

    Not the bare base name: two differently infused jars of one tincture would share
    an id and stack in the satchel as though they were the same thing. Not a stacked
    shape word either — `_name_for` already learned that lesson producing "Tincture
    Tincture Tincture".
    """
    import re

    raw = str(base.base or "").strip()
    # A tincture infused twice is still one tincture. The earlier addition is read back
    # out of the name and carried rather than replaced, so infusing woundwort and then
    # mad cap does not quietly erase the woundwort from the label — the jar still holds
    # both, and the effects list will say so.
    was = re.search(r"\s*\(([^)]*)\)\s*$", raw)
    keep = raw[: was.start()].strip() if was else raw
    before = [p.strip() for p in (was.group(1) if was else "").split(",")]
    names = [a for a in dict.fromkeys(before + list(added)) if a and a != "…"]
    if not names:
        return keep
    # Capped, because the alternative is the compounding that produced "Tincture
    # Tincture Tincture Tincture" in a live campaign. The full list survives in
    # `from_ingredients` and on the effect lines; only the label is short.
    shown = ", ".join(names[:2]) + ("…" if len(names) > 2 else "")
    return f"{keep} ({shown})"


def is_tincture(held) -> bool:
    """Whether a jar on the shelf is a tincture.

    Read off the name, because the name is what `distill` writes: `SHAPE_WORDS` turns
    that method into the word "Tincture" and nothing else in the chain produces it.
    A stored `craft` field would be better and does not exist on the jars already
    saved, and inventing one that only new jars carry would make the rule apply to
    half a satchel.
    """
    word = SHAPE_WORDS["distill"].lower()
    return word in str(getattr(held, "base", "") or "").lower()


def _infusion_problems(items, used, methods) -> list[str]:
    """A tincture may only be combined with anything else by infusing it.

    The author's rule: "Infusions should be the only way to combine tinctures with
    other things... you can solo distill and concentrate but until infusions unlock
    you cannot combine tinctures or add in effects of new ingredients to the existing
    tinctures."

    So the test is not "is there a tincture in the pot" but "is there a tincture *and*
    something else". A tincture on its own can be distilled, concentrated, refined or
    purified at any level that has those methods — that is the solo work the rule
    explicitly protects. The moment a second thing joins it, the chain needs `infuse`,
    and since `infuse` is learned at Herbalist 4 the restriction lifts itself exactly
    when the character earns it.
    """
    tinctures = [h for h, _ in used if is_tincture(h)]
    if not tinctures:
        return []
    # Everything in the pot other than the tincture doing the taking — including a
    # *second* tincture, which the first version excluded. Two tinctures in one pot is
    # the plainest case of combining tinctures there is, and it sailed through.
    others = [h.name for h, _ in used if h is not tinctures[0]] \
        + [i.name for i in items]
    if not others:
        return []
    if "infuse" in methods:
        return []

    lead = tinctures[0].name
    joined = ", ".join(others[:3]) + ("…" if len(others) > 3 else "")
    return [f"{lead} can only take {joined} by infusion. Put the infusion in the "
            f"chain, or work the tincture on its own."]


def _infusion_additions(items, used, methods) -> list[str]:
    """What may go *into* an infusion, once one is being made.

    "…other tinctures or brews, ground or mixed herbs, raw herbs as long as the raw
    herbs could be brewed raw, and some herbs that are volatile need extraction." A raw
    herb in the pot has not been ground unless the chain grinds it, so the question for
    each one is the same question `herbprep` already answers.
    """
    if "infuse" not in methods:
        return []
    from . import herbprep

    ground = "grind" in methods
    extracted = "extract" in methods
    out = []
    for item in items:
        prep = herbprep.Prep.of(item)
        state = "ground" if ground else ("extracted" if extracted else "raw")
        ok, why = herbprep.can_infuse({"kind": "tincture", "crafted": True},
                                      item, state)
        if not ok:
            out.append(f"{item.name} cannot be infused: {why}.")
    return out


def _spoiled_problems(items, carrier, now_minute) -> list[str]:
    """Anything in the pot that has gone off.

    Refused rather than quietly weakened: the author's rule is that unpreserved animal
    parts "become garbage", and garbage in a pot is not a worse potion, it is not a
    potion. Nothing is checked when the caller has no clock to check against, which is
    every call that predates one.
    """
    from . import herbprep

    if carrier is None or now_minute is None:
        return []
    out = []
    for item in items:
        prep = herbprep.Prep.of(item)
        spoiled, _ = carrier.freshness(item.id, now_minute, prep)
        if spoiled:
            out.append(
                f"{item.name} has spoiled — {herbprep.spoils_after(prep)} hours "
                f"unpreserved and it is refuse. Salt keeps it; potency is the price.")
    return out


def _preparation_problems(items, methods) -> list[str]:
    """Whether every ingredient in the pot can take every step in the chain.

    Walked in order, carrying each ingredient's state with it, because that is what the
    rules are about: a thing is raw until it is extracted, volatile until it is
    neutralised, whole until it is ground, and what it can take next depends on where it
    already is. Checking each step against the raw state would pass a chain that
    extracts and then grinds, and refuse the same chain for the same ingredient.

    Only the ingredient the step applies to is refused, by name and with the rule. A
    chain of eight herbs where one is a shelled nut should say which nut.
    """
    from . import herbprep

    out: list[str] = []
    for item in items:
        # `pot=False`: whether the pot holds a liquid is `_distillation_problems`'
        # question, and asking it here too refused every dry leaf twice over.
        why = prep_problem(item, methods, pot=False)
        if why:
            out.append(f"{item.name}: {why}.")
    return out


def prep_problem(item, methods, pot=True) -> str:
    """Why this one ingredient cannot go through this chain, or "".

    Split out of `_preparation_problems` so the shelf can grey a jar the chain would
    refuse *before* it is put in the pot. The alternative was a second copy of the walk
    in the page's JavaScript, which is the shape of bug this project has already paid for
    twice: a rule corrected in one place and left stale in the copy nobody looked at.

    The reason comes back without the ingredient's name on it, because the jar it is
    shown on is already wearing the name. `_preparation_problems` adds it back for the
    problems panel, where eight herbs are listed together and the name is the point.
    """
    from . import herbprep

    prep = herbprep.Prep.of(item)
    state = "raw"
    for step, _written in [(_AS_STEP[m], m) for m in methods if m in _AS_STEP]:
        ok, why = herbprep.can(step, prep, state)
        if ok:
            state = herbprep.after(step, state)
            continue
        # A step an ingredient simply has no use for is not an error: neutralising a pot
        # of eight herbs when one of them is volatile is the whole point, and the other
        # seven are not spoiled by sitting through it.
        if why.startswith(("it is not volatile", "there is nothing to extract",
                           "it is already", "it has already")):
            continue
        return why

    # Distillation is asked of the pot rather than of the ingredient, but the shelf still
    # has to answer it: with `distill` chosen, a dry leaf is the wrong thing to reach for
    # and should say so before it is picked up. Asked last, because "it has to be
    # extracted first" is the more useful sentence when both are true. Only the steps in
    # front of the first distillation matter — `brew → distill` is fine for anything that
    # can be brewed.
    methods = list(methods)
    if pot and "distill" in methods:
        at = methods.index("distill")
        if not pot_is_liquid([item], [], methods[:at]):
            return ("it does not pour — distilling needs a liquid. Brew it into a "
                    "tea first and distil that")
    return ""


def _name_for(items, methods) -> str:
    """A working name, so the preview is not headed "Untitled".

    The shape word replaces any shape word already on the end of the lead ingredient's
    name rather than stacking on top of it. Crafted outputs go back into the craft tree as
    inputs — that is the whole point of keeping them in inventory — so distilling a
    tincture used to produce a "Dragon Flower Tincture Tincture", and ten passes produced
    exactly what you would expect. Seen in play, ten deep.
    """
    if not items:
        return "Empty pot"
    lead = items[0].name
    for word in sorted(set(SHAPE_WORDS.values()) | {"Preparation"},
                       key=len, reverse=True):
        # Strip repeatedly: a name that already compounded before this fix should come
        # back to something sensible the next time it is crafted with.
        while lead.lower().endswith(" " + word.lower()):
            lead = lead[: -(len(word) + 1)].rstrip()
    last = methods[-1] if methods else ""
    shape = SHAPE_WORDS.get(last, "Preparation")
    return f"{lead} {shape}".strip()


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
import hashlib
import json as _json
import math
import re as _re

HERBAL_CRAFTS = ("herbalism", "herbalist")
TRACK_ID = "herbalist"
BODY_ROUTES = ("ingest", "skin", "eyes", "wound", "inhale")
ROUTE_WORDS = {
    "ingest": "what must be swallowed", "inhale": "what must be breathed in",
    "skin": "what works on the skin", "eyes": "what works on the eyes",
    "wound": "what works in a wound",
}
# The parts a bare corpus entry defaults to (contracts §2), until Lane A tags them.
_PART_DEFAULT = {"monster part": "organ", "fungus": "fungus"}
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
    """0 Crude ... 4 Flawless, then "Flawless +1" and on. The names come from here; the
    page never builds one (contracts §2)."""
    q = herbal_rules()["quality"]
    tiers = q["tiers"]
    index = max(0, int(index))
    if index < len(tiers):
        return tiers[index]
    return q["beyond"]["name"].format(n=index - len(tiers) + 1)


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
    return min(ceiling, int(s * (ceiling + 1))), round(s, 4)


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
        return duration
    return {**duration, "amount": max(1, _round(n * mult, up))}


def _harmful_ids(specs: list[dict]) -> set[int]:
    """Which of these specs are harm, asked through `consumables.sort_harm` so the bench
    and the card sort a poison's save and its damage the same way."""
    sorted_out = con.sort_harm(specs)
    benefits = {id(s) for s in sorted_out.benefits}
    return {id(s) for s in specs if id(s) not in benefits}


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
    state: str = "raw"
    form: str | None = None
    quality: int | None = None
    crafted: bool = False
    ingredient: object = None
    stock: Stock | None = None
    spoils_in: int | None = None
    spoiled: bool = False
    ready_minute: int | None = None
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
        ready_at = None
        if self.ready_minute is not None and now_minute is not None \
                and self.ready_minute > now_minute:
            ready_at = int(self.ready_minute)
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
            d["ready_in"] = ready_at - int(now_minute)
            d["ready_day"] = ready_at // 1440 + 1
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
    """An ingredient's part, with the contract's defaults until Lane A tags them."""
    got = getattr(ingredient, "part", None)
    if got:
        return str(got).strip().lower()
    return _PART_DEFAULT.get(str(getattr(ingredient, "kind", "") or ""), "leaf")


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
    """An effect's route, asked of the data lane's one reader when it is there.

    `ingredients.route_of` reads a missing route as ingest and an unknown one as
    external: a route nobody recognises must not slip into a remedy. The fallback is the
    same rule, for the branch where the reader has not landed yet.
    """
    reader = getattr(ing_mod, "route_of", None)
    if reader is not None:            # MERGE: drop fallback once lane/herb-data lands
        return str(reader(spec))
    route = str(spec.get("route") or "ingest").strip().lower()
    return route if route in BODY_ROUTES else "external"


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
    named = getattr(ing_mod, "reagent_named", None)
    if named is None:                 # MERGE: drop fallback once lane/herb-data lands
        return None
    try:
        return named(item.base)
    except Exception:                 # noqa: BLE001 — an unmapped name is simply not one
        return None


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
            tier=item.tier, count=count, state=item.state or "raw", form=item.form,
            quality=item.quality, crafted=True, stock=item,
            spoils_in=spoils_in, spoiled=spoiled, ready_minute=item.ready_minute,
            old=old, worked=list(item.worked),
            concentration=max(0, int(item.concentration or 1) - 1) if item.stepped else 0,
            base_specs=[dict(s) for s in item.base_specs], mults=dict(item.mults),
            from_ingredients=list(item.from_ingredients)))
    return out


def settle_steeping(actor, now_minute: int) -> list[str]:
    """Jars whose day has come stop being jars. Returns the names that became ready.

    A steeping jar is declared `how: ["steeping"]` so the sheet offers no way to use it;
    when its minute passes, the declaration is lifted and it is the tincture or acetum it
    always was. Asked by every bench request, which is the only place a jar is reached for
    by the bench; the engine's own use door does not ask yet (reported to the lead).
    """
    ready = []
    for item in (getattr(actor, "stock", {}) or {}).values():
        if item.ready_minute is not None and "steeping" in (item.how or []) \
                and int(item.ready_minute) <= int(now_minute):
            item.how = []
            ready.append(item.name)
    return ready


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
    if m.ready_minute is not None and m.stock is not None \
            and "steeping" in (m.stock.how or []):
        return f"still steeping: ready on day {int(m.ready_minute) // 1440 + 1}"
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
            return f"a {m.part} does not brew"
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
            plan.state = lead.state
        elif method == "extract":
            plan.form, plan.state = "extract", "extracted"
        elif method == "brew":
            plan.form = rules["methods"]["brew_product_by_part"].get(part, "decoction")
            plan.state = lead.state
        elif method == "infuse":
            plan.form, plan.state = "infused-oil", lead.state
        elif method == "steep":
            solvent = next(m.solvent for m, _ in reagents if m.reagent == "solvent")
            plan.form = "tincture" if solvent == "alcohol" else "acetum"
            plan.state = lead.state
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
        plan.state = "ground" if plan.form == "poultice" else None
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
    plan.pre = {
        "potency": p_in * float(mrow_p) * prod_p * perk_p,
        "duration": d_in * float(mrow_d) * prod_d * perk_d,
        # Harm grows with concentration and the form's strength, as the dose does; the
        # crafter's perks are a benefit and leave it alone.
        "drawback": w_in * float(mrow_p) * prod_p,
    }

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
                                 f"a {prow.get('name', plan.form).lower()} cannot carry "
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
    if specs and not kept and plan.dropped and method != "neutralize":
        # The form could carry none of it: a poultice of a herb that only works when
        # swallowed is a wet leaf, and making one would spend the herb for nothing.
        plan.problems.append(
            f"A {prow.get('name', plan.form).lower()} can carry none of what this does "
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


def strength_at(plan: StepPlan, tier: int) -> dict:
    return {"potency": plan.pre["potency"] * quality_mult("potency", tier),
            "duration": plan.pre["duration"] * quality_mult("duration", tier),
            "drawback": plan.pre["drawback"] * quality_mult("drawback", tier)}


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
    how = ["steeping"] if ready is not None else (
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
    return {"method": plan.method, "part": plan.part,
            "difficulty": float(diff.get(plan.part, diff.get("default", 0.5))),
            "seconds": tun.get("seconds", 6), "beats": tun.get("beats", 6),
            "infusion": plan.form == "infusion"}
