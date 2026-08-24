"""Enchanting chains: what a set of materials and a sequence of ritual methods binds.

The same shape as `rules/crafting.py` on purpose — a chain of ordered methods over a set
of components, validated whole and refused with sentences *before* anything is rolled —
so a later uniform dispatch can treat the two benches alike. The names match crafting's
(`TRACK_ID`, `CraftError`, `Chain`, `preview`) for exactly that reason.

Where herbalism's output is a jar that is drunk once, enchanting's output is a **standing
effect list on an item**: the finished binding IS a list of `rules/effectspec.py` specs,
permanent, plus whatever the essence costs its bearer (shadowstuff dims; vicious bites the
hand). The drawbacks ride in the same list, marked, because an enchantment that quietly
dropped its price would be a better deal than the book ever offered.

House rounding, inherited from crafting: costs and penalties round **down**, benefits
round **up**.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import effectspec
from . import worldclass as wc

TRACK_ID = "enchanter"

# Methods that must come last if used at all: seal closes the working, and nothing may
# follow it. Mirrors crafting's FINISHING for the same reason brew has it — you seal the
# binding, you do not scribe the seal.
FINISHING = ("seal",)

# What the off-type surcharge is. A fire mote pressed into armour, a stone mote hung on a
# blade: the material resists, and resisting is +5 on the working's DC rather than a
# refusal — the book's named armour/weapon split is about what the essence *wants*, and
# an enchanter may work against the grain at a price.
OFF_TYPE_DC = 5

# Empower raises a binding one tier band beyond its essence, at this surcharge. It exists
# for the same structural reason the Herbalist's concentration ladder does: the level-5
# deed is legendary work, legendary essence is level-5 material, and without a ladder the
# gate could never open (see the herbalist's `_deeds_note`, which records the measured
# version of that trap).
EMPOWER_DC = 5
EMPOWER_TIER_STEP = 1


class CraftError(ValueError):
    """The chain cannot be described at all. Merely-bad chains come back as `problems`
    on the preview instead, so a working the character cannot attempt never rolls and
    never advances their track."""


@dataclass
class Material:
    """One thing on the enchanter's shelf.

    `capacity` is only meaningful on a focus: the highest essence rank it anchors AND the
    total ranks it holds, one number doing both jobs so "quartz cannot hold a storm" and
    "quartz cannot hold three motes" are the same check. `fragile` marks the focus a
    mishap destroys outright (the diamond) rather than merely scorching.
    """
    id: str
    name: str
    kind: str = "essence"       # essence | focus | ink | chalk | salt | vessel
                                #  | catalyst | treatment
    tier: str = "common"
    family: str = ""            # essences: the effect family; one per vessel
    adjective: str = ""         # what the finished item is called ("Flaming")
    plus: int = 0               # the enhancement ladder rung, 0 for named properties
    prefers: str = ""           # "weapon" | "armour" | "" — off-type binding is +5 DC
    binds_at: str = ""          # "night": will not bind under the sun
    capacity: int = 0
    fragile: bool = False
    requires: str = ""          # vessel entries: what the target item must be, as prose
    consumed: bool = False      # inks, chalks, salts, catalysts, treatments are spent
    dc_mod: int = 0             # catalysts: applied to the chain DC
    lifts: str = ""             # treatments: a restriction this lifts ("night")
    text: str = ""
    # Where it comes from, for the play page's acquisition hub: bought | mined |
    # harvested | gathered. `biomes` narrows a gathering, `from_creature` a harvest,
    # `price_gp` prices a purchase. Unstated means "bought", because a material nobody
    # has said how to find is one you can at least try to buy.
    obtain: str = "bought"
    biomes: list[str] = field(default_factory=list)
    from_creature: list[str] = field(default_factory=list)
    price_gp: int = 0
    effects: list = field(default_factory=list)
    drawbacks: list = field(default_factory=list)

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def glyph(self) -> str:
        return KIND_GLYPH.get(self.kind, "✨")

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "tier": self.tier,
            "rank": self.rank, "family": self.family, "adjective": self.adjective,
            "plus": self.plus, "prefers": self.prefers, "binds_at": self.binds_at,
            "capacity": self.capacity, "fragile": self.fragile,
            "requires": self.requires, "consumed": self.consumed,
            "dc_mod": self.dc_mod, "lifts": self.lifts, "text": self.text,
            "obtain": self.obtain, "biomes": self.biomes,
            "from_creature": self.from_creature, "price_gp": self.price_gp,
            "glyph": self.glyph,
            "effects": self.effects, "drawbacks": self.drawbacks,
        }


def from_dict(d: dict) -> Material:
    return Material(
        id=d["id"], name=d.get("name", d["id"]), kind=d.get("kind", "essence"),
        tier=d.get("tier", "common"), family=d.get("family", ""),
        adjective=d.get("adjective", ""), plus=int(d.get("plus", 0) or 0),
        prefers=d.get("prefers", ""), binds_at=d.get("binds_at", ""),
        capacity=int(d.get("capacity", 0) or 0), fragile=bool(d.get("fragile")),
        requires=d.get("requires", ""), consumed=bool(d.get("consumed")),
        dc_mod=int(d.get("dc_mod", 0) or 0), lifts=d.get("lifts", ""),
        text=d.get("text", ""),
        obtain=str(d.get("obtain") or "bought").strip().lower(),
        biomes=[str(b).strip().lower() for b in (d.get("biomes") or [])],
        from_creature=[str(c).strip().lower() for c in (d.get("from_creature") or [])],
        price_gp=int(d.get("price_gp", 0) or 0),
        effects=list(d.get("effects") or []),
        drawbacks=list(d.get("drawbacks") or []),
    )


_MATERIALS: dict[str, Material] | None = None

# Files in the shared shelf folder that are **not** shelf materials. `magic-items.json`
# is the second mode's priced rules table — properties and finished wondrous items — and
# reading it here made "Ring of Protection +1" a buyable enchanting material in
# `obtainable()`, because every entry in it honestly carries `obtain: "bought"`. Found
# when a sibling craft dropped another non-shelf file into the folder and the shelf test
# went red; the shelf is a folder by convention, so a catalogue that is not a shelf has
# to say so somewhere, and here is the only place that reads them all.
NOT_SHELF = {"magic-items"}


def materials() -> dict[str, Material]:
    """Every material the app knows, shipped and homebrew.

    Homebrew is layered over the shipped set rather than replacing it — the
    `worldclass.tracks()` pattern, for the reason it records: a corrected material in a
    later build must not be shadowed by a stale copy in the user's data directory, which
    is the trap `CLAUDE.md` carries over from World Bible's stylesheet. Merged entry by
    entry, so a homebrew essence just works beside the shipped ones and a homebrew copy
    of a shipped id wins.

    Walked here rather than through `registry.KINDS` because materials are not a
    registered kind yet — registering one means touching `rules/registry.py`, which this
    module deliberately does not do. `_entries` reproduces the two file shapes
    `registry.read_folder` accepts, per file rather than per folder, so `NOT_SHELF` can
    be honoured.
    """
    global _MATERIALS
    if _MATERIALS is None:
        from django.conf import settings

        raw: dict[str, dict] = {}
        shipped = Path(settings.BASE_DIR) / "content" / "materials"
        user = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "materials"
        for folder in (shipped, user):
            if not folder.is_dir():
                continue
            # Per file rather than one `read_folder` over the folder, so `NOT_SHELF` can
            # be honoured — the folder is a shared shelf, and one file in it is a priced
            # rules table that only `rules/magicitem.py` should read.
            for path in sorted(folder.glob("*.json")):
                if path.stem in NOT_SHELF:
                    continue
                for key, entry in _entries(path):
                    raw.setdefault(key, {}).update(entry)
        _MATERIALS = {k: from_dict({**v, "id": k}) for k, v in raw.items()}
    return _MATERIALS


def _entries(path: Path):
    """One file's entries as (id, dict), whatever shape it is in.

    The two shapes `registry.read_folder` accepts — a file holding a list under
    `materials`, and a file holding one entry — kept here because the shelf has to be
    read file by file to skip the ones that are not shelves. A file whose list lives
    under another key (the alchemist's spell potions) yields nothing rather than
    raising: the shelf folder holds more than shelves now, and a loader that dies on a
    neighbour's file is a loader that takes the bench down with it.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    entries = data.get("materials") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        entries = [data] if isinstance(data, dict) and data.get("id") else []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("id"):
            yield str(entry["id"]).strip().lower(), entry


def get(material_id: str) -> Material:
    m = materials().get((material_id or "").strip().lower())
    if m is None:
        raise KeyError(f"no enchanting material {material_id!r}")
    return m


@dataclass
class Chain:
    """One working: ordered methods, the materials on the bench, the item on the anvil."""
    methods: list[str] = field(default_factory=list)
    material_ids: list[str] = field(default_factory=list)
    item: str = ""              # the target item's name
    name: str = ""              # what to call the result; derived when empty

    @property
    def stages(self) -> int:
        return len(self.methods)


def chain_from_body(body: dict) -> Chain:
    """A Chain from whatever the page posted, tolerantly.

    The same signature `rules/magicitem.py` carries, so the bench spine can hand one
    posted body to whichever mode is active without knowing which it is. Forgiving on
    shape — a list or a comma-joined string for `methods` and `materials` — because the
    real validation happens in `preview`, where a problem can be *shown* rather than
    raised as a 500 on a form that looked fine.
    """
    body = dict(body or {})

    def as_list(value):
        if isinstance(value, str):
            return [p.strip().lower() for p in value.split(",") if p.strip()]
        return [str(v).strip().lower() for v in (value or [])]

    return Chain(
        methods=as_list(body.get("methods")),
        material_ids=as_list(body.get("materials", body.get("material_ids"))),
        item=str(body.get("item", body.get("vessel", "")) or "").strip(),
        name=str(body.get("name", "") or "").strip(),
    )


@dataclass
class Result:
    """What the chain would bind, and what could go wrong — nothing rolled.

    `effects` is prose and `specs` is the executable list — the split the shared bench
    spine expects, and worth stating because this class carried structured dicts under
    the name `effects` when it was written alone. A card shows strings; the engine runs
    specs; neither re-derives the other. `drawbacks` keeps the harmful specs listed
    separately as well as inside `specs`, so a panel can show what the binding costs
    without filtering the whole list.

    `mishap` says what a failed check does to the focus, because that is the one
    consequence a player should see before choosing the stone.
    """
    name: str
    item: str
    tier: str
    rank: int
    stages: int
    dc: int
    effects: list[str] = field(default_factory=list)
    specs: list[dict] = field(default_factory=list)
    drawbacks: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    mishap: str = ""
    risky: bool = False
    materials: list[dict] = field(default_factory=list)
    consumes: dict[str, int] = field(default_factory=dict)
    output: dict | None = None
    bonus: int = 0
    terms: list[dict] = field(default_factory=list)
    chance: int = 0
    empowered: bool = False

    def as_dict(self) -> dict:
        return {
            "name": self.name, "item": self.item, "tier": self.tier, "rank": self.rank,
            "stages": self.stages, "dc": self.dc, "risky": self.risky,
            "effects": self.effects, "specs": self.specs,
            "drawbacks": self.drawbacks, "problems": self.problems,
            "notes": self.notes, "mishap": self.mishap, "materials": self.materials,
            "consumes": self.consumes, "output": self.output,
            "bonus": self.bonus, "terms": self.terms,
            "chance": self.chance, "empowered": self.empowered,
        }


def check_terms(actor, level: int) -> list[dict]:
    """What an enchanter adds to the die, itemised — crafting's formula with the mental
    stat swapped: **d20 + track level + half character level + Intelligence**. Herbalism
    is wisdom-work, reading what a leaf already is; enchanting is imposing a structure
    that was not there, which is the Intelligence half of the sheet. Itemised for the
    same reason crafting's terms are: "+9" says nothing, three named terms say which one
    to improve.
    """
    track_level = max(0, int(level or 0))
    char_level = max(1, int(getattr(actor, "level", 1) or 1)) if actor else 1
    intel = int(actor.ability_mod("int")) if actor is not None else 0
    return [
        {"label": f"Enchanter {track_level}", "value": track_level},
        {"label": f"half character level ({char_level})", "value": char_level // 2},
        {"label": "Intelligence", "value": intel},
    ]


def check_bonus(actor, level: int) -> int:
    return sum(t["value"] for t in check_terms(actor, level))


def _chance(dc: int, bonus: int, problems) -> int:
    """Same clamp as crafting's, for the same reason: a natural 1 always fails and a
    natural 20 always succeeds, so no working is ever certain either way."""
    if problems:
        return 0
    need = dc - bonus
    return max(5, min(95, int(round(100 * (21 - need) / 20))))


def _mishap(focus: Material | None) -> str:
    """What a failed check costs, said up front.

    The diamond's failure mode is the interesting one: `fragile` foci are *lost* on a
    mishap — cracked through, gone — where a lesser stone is scorched and survives. Lost
    is not spent: a successful working returns every focus to the pouch; only the mishap
    takes the fragile one. The essence is spent either way, success or failure, because
    it went into the circle.
    """
    if focus is None:
        return "The essence is spent; there is no focus to lose."
    if focus.fragile:
        return (f"On a failure the essence is spent and the {focus.name} cracks "
                f"through — lost outright, not merely spent.")
    return (f"On a failure the essence is spent; the {focus.name} is scorched "
            f"but survives.")


def _derived_name(chain: Chain, essences: list[Material]) -> str:
    """"Flaming Longsword +1" from the pieces, when the chain does not name itself.

    Adjectives first, the enhancement rung last, the way the book prints them. The
    ladder essences carry `plus` instead of an adjective, so a chain of arcane essence
    III and flaming essence over a longsword comes out "Flaming Longsword +3" rather
    than "Arcane Essence III Flaming Longsword".
    """
    item = (chain.item or "item").strip()
    item = item[:1].upper() + item[1:]
    adjectives = [e.adjective for e in essences if e.adjective and not e.plus]
    plus = max((e.plus for e in essences), default=0)
    name = " ".join(dict.fromkeys(adjectives)) + (" " if adjectives else "") + item
    return f"{name} +{plus}" if plus else name


def preview(level: int, chain: Chain, stock: dict | None = None, actor=None,
            item: dict | None = None, *, at_night: bool | None = None,
            carrier=None) -> Result:
    """What this working would bind, and how hard it is — without rolling.

    Never raises for a chain that is merely bad: an unlearned method, an essence beyond
    the level's tier, a binding with no focus all come back as `problems`, so the page
    can grey the button and say why. That is crafting's contract, kept, so track
    progression can never be earned by a chain the character could not attempt.

    `stock` is what the enchanter is carrying, as {material id: count}; None means
    "assume they have it", which is what every rules test wants. `item` describes the
    vessel — {"masterwork": bool, "kind": "weapon" | "armour" | ...}; None means nobody
    has vouched for the item, and an unvouched item is treated as not masterwork,
    because "empty is not the same as absent" cuts the other way here: enchantment
    needs the masterwork fact *asserted*, and assuming it would wave every rusty sword
    through. `at_night` is scene state; None means the scene has no clock, and a
    night-binding material is noted rather than refused, matching how spoilage is only
    checked when a clock exists to check against.
    """
    track = wc.get(TRACK_ID)
    level = max(1, min(int(level), track.max_level))
    known = track.unlocked_methods(level)
    ceiling = wc.tier_rank(track.at(level).max_tier)

    problems: list[str] = []
    notes: list[str] = []

    mats: list[Material] = []
    wanted: dict[str, int] = {}
    for mid in chain.material_ids:
        try:
            mats.append(get(mid))
            wanted[mid] = wanted.get(mid, 0) + 1
        except KeyError:
            problems.append(f"No such material: {mid}.")

    if stock is not None:
        for mid, n in wanted.items():
            carrying = int(stock.get(mid, 0))
            if carrying < n:
                name = get(mid).name
                problems.append(
                    f"{name}: you are carrying {carrying}, the working wants {n}."
                    if carrying else f"You have no {name}.")

    for m in chain.methods:
        if m not in track.unlocked_methods(track.max_level):
            problems.append(f"{track.name} has no method called {m!r}.")
        elif m not in known:
            need = next(l.level for l in sorted(track.levels, key=lambda x: x.level)
                        if m in l.methods)
            problems.append(f"{m.title()} is learned at {track.name} {need}.")

    for mat in mats:
        if mat.rank > ceiling:
            problems.append(f"{mat.name} is {mat.tier}; {track.name} {level} works "
                            f"{track.at(level).max_tier} at best.")

    if not mats:
        problems.append("Nothing on the bench.")
    if not chain.methods:
        problems.append("No method chosen.")

    for m in chain.methods[:-1]:
        if m in FINISHING:
            problems.append(f"{m.title()} finishes a working; nothing follows it.")

    essences = [m for m in mats if m.kind == "essence"]
    foci = [m for m in mats if m.kind == "focus"]
    focus = foci[0] if foci else None
    binding = "bind" in chain.methods

    # The heart of the craft's refusals, each one a sentence a player can act on.

    if essences and not binding:
        problems.append("Essence goes nowhere without binding — put bind in the chain.")

    if binding and focus is None:
        # The pinned sentence: an essence has to live somewhere, and the circle is a
        # place of passage, not residence.
        problems.append("Binding needs a focus: the essence has nowhere to live, "
                        "and a circle alone cannot hold it.")

    if binding and "seal" not in chain.methods:
        problems.append("An unsealed binding bleeds away by morning — finish "
                        "the chain with seal.")

    if "seal" in chain.methods and binding:
        if chain.methods.index("seal") < chain.methods.index("bind"):
            problems.append("Seal closes a binding; nothing has been bound yet "
                            "when it runs.")
    elif "seal" in chain.methods and not binding:
        problems.append("Seal closes a binding, and there is no bind in the chain.")

    if focus is not None and essences:
        top = max(essences, key=lambda e: e.rank)
        if top.rank > focus.capacity:
            problems.append(
                f"{focus.name} holds {wc.TIERS[min(focus.capacity, len(wc.TIERS)) - 1]}"
                f" essence at most; {top.name} is {top.tier}. "
                f"A quartz cannot hold a storm.")
        elif sum(e.rank for e in essences) > focus.capacity:
            problems.append(
                f"{focus.name} holds {focus.capacity} rank"
                f"{'s' if focus.capacity != 1 else ''} of essence in total; "
                f"this working asks {sum(e.rank for e in essences)}. "
                f"A larger stone, or a smaller ambition.")

    # More than one essence in a working is imbuing, and imbue is learned at Enchanter
    # 3 — the same self-lifting shape as herbalism's infusion rule: the restriction is
    # written once here and expires exactly when the character earns the method.
    if len(essences) > 1 and "imbue" not in chain.methods:
        problems.append("Two essences in one working is imbuing — put imbue in "
                        "the chain, or bind them one ritual at a time.")

    # One essence per family per vessel. Two flaming bindings are not a hotter sword —
    # the second essence has nowhere to sit, because the seat is taken. Same-family is
    # the check rather than same-id so arcane III over arcane I is refused too: the
    # ladder is replaced by re-enchanting, not stacked.
    seen_families: dict[str, Material] = {}
    for e in essences:
        fam = e.family or e.id
        if fam in seen_families:
            problems.append(
                f"{seen_families[fam].name} and {e.name} are the same family "
                f"({fam}); a vessel takes one essence of a family, never two.")
        else:
            seen_families[fam] = e

    # The vessel must be masterwork — the book's own gate. Checked against what the
    # caller asserts about the item, not against a name: "Longsword" says nothing about
    # the smith who made it.
    target = dict(item or {})
    if essences and not target.get("masterwork"):
        problems.append(
            f"{(chain.item or 'The item').strip() or 'The item'} is not masterwork: "
            f"an enchantment needs a vessel worthy of it. Commission one from the "
            f"smith or the leatherworker first.")

    # Material temperament: off-type binding costs, night materials keep hours.
    kind = str(target.get("kind", "")).strip().lower()
    off_type = 0
    lifted = {m.lifts for m in mats if m.kind == "treatment" and m.lifts}
    for e in essences:
        if e.prefers and kind and e.prefers != kind:
            off_type += OFF_TYPE_DC
            notes.append(f"{e.name} wants a {e.prefers}; binding it to a {kind} "
                         f"is working against the grain (+{OFF_TYPE_DC} DC).")
        if e.binds_at == "night" and "night" not in lifted:
            if at_night is False:
                problems.append(f"{e.name} only binds at night. Wait for dark, "
                                f"or treat the vessel with moonlit varnish.")
            elif at_night is None:
                notes.append(f"{e.name} only binds at night.")

    # The working is as rare as its rarest essence, which is what gates who may attempt
    # it — same rule as crafting's pot. Empower then lifts the *result* one band: that
    # is the ladder to legendary work, and the reason an Enchanter 4 can earn the
    # level-5 deed (see the track's `_deeds_note`).
    rank = max((e.rank for e in essences), default=1)
    empowered = "empower" in chain.methods
    if empowered:
        if not essences:
            problems.append("Empower raises a binding; there is no essence to raise.")
        rank = min(len(wc.TIERS), rank + EMPOWER_TIER_STEP)
    tier = wc.TIERS[rank - 1]

    # DC: essence tier sets the floor, each essence beyond the first adds — a working
    # holding three bindings is three arguments kept aloft at once. Catalysts subtract;
    # the off-type surcharge and empower add. Penalties round down and benefits round
    # up as everywhere, though every term here is already whole.
    base_rank = max((e.rank for e in essences), default=1)
    dc = 10 + 5 * base_rank + 5 * max(0, len(essences) - 1) + off_type
    if empowered:
        dc += EMPOWER_DC
    for m in mats:
        dc += m.dc_mod
    dc = max(5, dc)

    # The finished item's standing effect list: every essence's specs plus its
    # drawbacks, each marked with where it came from. The drawback rides in the same
    # list because it is part of the binding — shadowstuff's dimming does not wear off
    # when the stealth does not.
    specs: list[dict] = []
    drawbacks: list[dict] = []
    for e in essences:
        for spec in e.effects:
            specs.append({**spec, "from": spec.get("from") or e.name})
        for spec in e.drawbacks:
            marked = {**spec, "from": spec.get("from") or e.name, "drawback": True}
            drawbacks.append(marked)
            specs.append(marked)

    # Prose beside the structure, rendered through `effectspec.render` so a bound
    # essence and an authored ingredient read in one voice — the player should not be
    # able to tell which side of the app wrote a line.
    effects = [f"{s['from']}: {effectspec.render(s)}" if s.get("from")
               else effectspec.render(s) for s in specs]

    name = chain.name or _derived_name(chain, essences)
    # `actor` is the name the spine and `rules/magicitem.py` use; `carrier` is what
    # this module shipped with and what the herbalism bench calls the same argument.
    # Both are accepted rather than one renamed, because a signature the spine calls
    # positionally and a keyword an existing caller passes must not fight.
    terms = check_terms(actor if actor is not None else carrier, level)
    bonus = sum(t["value"] for t in terms)

    # What a successful working spends. Essences always; consumables (inks, chalks,
    # salts, catalysts, treatments) always; foci never — a focus is anchored into the
    # item or returned, and only a mishap on a fragile stone takes one.
    consumes: dict[str, int] = {}
    for mid, n in wanted.items():
        m = get(mid)
        if m.kind == "essence" or m.consumed:
            consumes[mid] = n

    worn = kind in ("armour", "shield", "cloak", "jewelry", "ring", "amulet")
    output = {
        "id": _slug(name), "name": name, "kind": "crafted", "craft": TRACK_ID,
        "tier": tier, "rank": rank, "count": 1,
        "effects": effects, "specs": specs,
        "from_materials": list(wanted),
        # The vessel had to be masterwork to take the binding, so the result is one.
        "masterwork": True,
        "wearable": worn, "usable": not worn, "how": [],
        "slot": target.get("slot") or None,
        "weapon": target.get("weapon") if not worn else None,
        "armour": target.get("armour") if worn else None,
        # The essence mode has no +N ladder of its own except through the enhancement
        # family, so the number is read off whichever essence carries one.
        "enhancement": max((e.plus for e in essences), default=0),
        "properties": [e.name for e in essences],
    }

    return Result(
        name=name, item=chain.item, tier=tier, rank=rank, stages=chain.stages,
        dc=dc, effects=effects, specs=specs, drawbacks=drawbacks,
        problems=problems, notes=notes,
        # A binding that stakes a fragile focus is the one that can cost more than it
        # spends. That is what `risky` means everywhere else in the app: a working with
        # a consequence beyond wasted material.
        risky=bool(focus is not None and focus.fragile),
        mishap=_mishap(focus), materials=[m.as_dict() for m in mats],
        consumes=consumes, output=output, bonus=bonus, terms=terms,
        chance=_chance(dc, bonus, problems), empowered=empowered,
    )


def _slug(name: str) -> str:
    out = "".join(c if c.isalnum() else "-" for c in str(name).lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out


# --- what the bench shows -----------------------------------------------------------------

# One glyph per material kind, from the Enchanter's reserved pool. Herbalism owns
# 🌿 🍄 🦴 ☠️ and none of them appear here; a shared glyph would make two benches look
# like one shelf at a glance, which is the whole thing icons are for.
#
# `catalyst` is 📿 rather than the candle it started as. Measured through
# `benches.glyphs()` once the five tracks were loaded together: 🕯️ was on the
# leatherworker's `wax` as well, and a candle is the more literal thing for wax to be.
# The clash was invisible from inside this file — one craft cannot see another's map —
# which is exactly why the spine asserts across all five rather than each craft
# asserting about itself.
KIND_GLYPH: dict[str, str] = {
    "essence": "✨",
    "focus": "💎",
    "ink": "🖋️",
    "chalk": "🜏",
    "salt": "⭐",
    "vessel": "🔮",
    "catalyst": "📿",
    "treatment": "🧿",
}


# --- acquisition ---------------------------------------------------------------------------
#
# The play page's craft-action button is the single hub for *obtaining* materials, and
# this is what the Enchanter offers it. Declared as data rather than wired here: the
# excursion is the play layer's to run, and the track's job is to say what it yields.
#
# `obtain` on each material answers "where does this actually come from" — the question
# the essences most needed answered. A fire mote is skimmed off a forge or a lava vent;
# ghost residue is gathered where something died badly, after dark. Saying so turns the
# shelf from a shop into a place.

ACQUISITION: list[dict] = [
    {"id": "essence-hunt", "label": "Skim essence", "obtain": "gathered",
     "needs": {"biome": True},
     "blurb": "Motes and residues are skimmed where the world runs thin — a forge's "
              "heart, a storm's tail, the flagstones of a bad death. What is out "
              "depends on where you are standing and, for some of it, on the hour.",
     "yields_kind": "essence"},
    {"id": "gem-cutting", "label": "Mine and cut foci", "obtain": "mined",
     "needs": {"biome": True},
     "blurb": "Quartz from any hillside, amethyst from a geode seam, diamond from "
              "somewhere that will cost you. A focus is mined rough and cut at the "
              "bench; the cutting is the cheap half.",
     "yields_kind": "focus"},
    {"id": "reliquary-harvest", "label": "Harvest from the slain", "obtain": "harvested",
     "needs": {"creature": True},
     "blurb": "Dragon ichor, fiend ash, a lich's dust, a feather given rather than "
              "taken. The strongest essences in the catalogue are cut from something "
              "that was recently alive and objected.",
     "yields_kind": "essence"},
    {"id": "scriptorium-order", "label": "Buy inks, chalks and catalysts",
     "obtain": "bought", "needs": {"market": True},
     "blurb": "Silver ink, consecrated chalk, powdered pearl, a phoenix quill if the "
              "shop is lying about what it has. Circle materials are consumed by every "
              "working, so this is the errand an enchanter runs most.",
     "yields_kind": "ink"},
    {"id": "vessel-commission", "label": "Commission a vessel", "obtain": "bought",
     "needs": {"market": True, "craft": ("blacksmith", "leatherworker")},
     "blurb": "The masterwork item itself, from the smith or the leatherworker — or "
              "from their own bench, if the character has the track. Nothing is bound "
              "to anything less.",
     "yields_kind": "vessel"},
]


def obtainable(obtain_kind: str, *, biome: str | None = None,
               creature: str | None = None) -> list[Material]:
    """Every material this excursion could turn up, filtered to where you are.

    `biome` and `creature` narrow a gathering or a harvest; passing neither answers
    everything of that obtain kind, which is what a catalogue page wants. Matched on the
    material's own `biomes` and `from_creature` fields — a fire mote does not appear in
    a bog, and dragon ichor does not appear off a rat.
    """
    want = (obtain_kind or "").strip().lower()
    out: list[Material] = []
    for _, m in sorted(materials().items()):
        if m.obtain != want:
            continue
        if biome and m.biomes and biome.strip().lower() not in m.biomes:
            continue
        if creature and m.from_creature:
            said = creature.strip().lower()
            if not any(part in said or said in part for part in m.from_creature):
                continue
        out.append(m)
    return out


__all__ = ["ACQUISITION", "Chain", "CraftError", "EMPOWER_DC", "FINISHING",
           "KIND_GLYPH", "Material", "OFF_TYPE_DC", "Result", "TRACK_ID",
           "chain_from_body", "check_bonus", "check_terms", "from_dict", "get",
           "materials", "obtainable", "preview"]
