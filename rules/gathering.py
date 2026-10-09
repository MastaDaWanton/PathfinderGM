"""What else the ground has, when you go looking for herbs or ore.

"i go to collect herbs and run into a bear or a search for ore and find a massive vein
guarded by a cave worm." Ultimate Wilderness's foraging rules say the same thing more
quietly: check for a random encounter once per foraging expedition (AoN, Foraging,
optional rules). This is that check, rolled by the engine on its own dice once per
expedition, and it answers with one of four things:

  quiet     — the hours pass and the table said nothing more.
  rich      — a rich patch, a seam, a fallen trunk full of fungus: the yield doubles.
  creature  — something that lives here has noticed you. Animals and vermin come at
              you; the expedition is a fight now. Anything cleverer is in the way: it
              holds the patch you were making for (`state.holding-ground`), and the
              patch is booked at ×1 and yours once it has gone (owner ruling D1,
              2026-09-30).
  guarded   — the best find of all, and something is sitting on it. The vein is real
              and it is booked; it is yours when whatever guards it is dead or gone.
              The guard holds its ground the same way.

The creature is never invented. It is drawn from the shipped bestiary by the biome the
scene stands on and a CR window around the character's level (`bestiary.search`), so
a forest at first level gives up a wolf and a mountain at fifth a cave worm's kind,
and nothing that the book does not put there. The table itself is authored once and
is not per biome: the biome comes in through the creatures, which is where it lives.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import bestiary

# The d100 bands, low to high. Authored to Ultimate Wilderness's temper — most
# expeditions are just work — with the guarded find rare enough to be a story.
BANDS = (
    (1, 55, "quiet"),
    (56, 75, "rich"),
    (76, 93, "creature"),
    (94, 100, "guarded"),
)

# Creature types that come at you on sight. The rest — dragons, fey, humanoids — are
# an obstacle with a mind, and the player gets to decide what to do about them.
AGGRESSIVE = frozenset({"animal", "vermin", "magical beast", "ooze", "plant"})

# The CR window around the character's level, and how far it stretches for the thing
# guarding the big find. A first-level character foraging should meet CR 1/3 to CR 2,
# not a CR 8 — the table is a hazard of the work, not a way to die of botany.
BELOW, ABOVE, GUARD_ABOVE = 2, 1, 2

# What multiplies the yield. A rich patch is twice the finding; a guarded find, three
# times, and it waits.
RICH_YIELD, GUARDED_YIELD = 2, 3


@dataclass
class Encounter:
    kind: str                       # quiet | rich | creature | guarded
    roll: int
    creature: dict | None = None    # the bestiary row, when there is one
    aggressive: bool = False
    yield_times: int = 1
    tell: str = ""
    extras: dict = field(default_factory=dict)


def _cr_window(level: int, guarding: bool) -> tuple[float, float]:
    low = max(1 / 3, level - BELOW)
    high = max(1, level + (GUARD_ABOVE if guarding else ABOVE))
    return low, high


def creature_for(biome: str, level: int, dice, guarding: bool = False) -> dict | None:
    """A bestiary row that lives here and is a fair match, or None when the book has
    nothing for this ground — a stone shelf where no creature is tagged is quiet."""
    low, high = _cr_window(level, guarding)
    # Only creatures whose ground is the book's own words (`bestiary.ground_stated`): the
    # spreadsheet's guessed ground drew a named hag of an adventure, Aelzeldra, onto a
    # seam in the hills and the tell called her "an Aelzeldra" (the owner, 2026-10-09:
    # "it introduced itself as its species like it was a name").
    rows = bestiary.search(biome=biome, cr_min=low, cr_max=high, stated=True, limit=400)
    rows = [r for r in rows if r.get("cr_value") is not None
            and r.get("creature_type") not in ("humanoid", "outsider", "undead")]
    if not rows:
        return None
    return rows[pick_index(dice, len(rows), "what lives here")]


def pick_index(dice, n: int, label: str) -> int:
    """A hidden pick of one of `n` things, as a 0-based index.

    One of one is not rolled: `Dice.parse` refuses "1d1" as implausible notation, and
    every `f"1d{len(rows)}"` in the code raised BadDice the day a list held exactly one
    thing. Measured 2026-10-06: 53 of 100 prospects in the desert crashed, because the
    desert's only common mined material is one row (`Engine._op_prospect`'s ore pick);
    this function's own creature pick had the same shape on a biome whose bestiary
    window held one creature.
    """
    if n <= 1:
        return 0
    return dice.roll(f"1d{n}", label=label, visibility="hidden").total - 1


def roll(biome: str, level: int, dice) -> Encounter:
    """Once per expedition. The d100 is the engine's, hidden, like every other roll a
    player could not have known the number of."""
    r = dice.roll("1d100", label="the ground's own answer", visibility="hidden").total
    kind = next(k for lo, hi, k in BANDS if lo <= r <= hi)
    if kind == "quiet":
        return Encounter("quiet", r)
    if kind == "rich":
        return Encounter("rich", r, yield_times=RICH_YIELD)
    row = creature_for(biome, level, dice, guarding=(kind == "guarded"))
    if row is None:
        # Nothing lives here that the book prices for this level; the ground is
        # quiet, and a rich find is what a guarded one becomes with nobody on it.
        return (Encounter("rich", r, yield_times=RICH_YIELD) if kind == "guarded"
                else Encounter("quiet", r))
    aggressive = kind == "creature" and row.get("creature_type") in AGGRESSIVE
    return Encounter(kind, r, creature=row, aggressive=aggressive,
                     yield_times=GUARDED_YIELD if kind == "guarded" else 1)


def spot_for(what: str, biome: str = "", spot: str = "") -> str:
    """The piece of ground a creature can be sitting on: a seam of ore, a thicket where
    there is cover for one, a patch everywhere else. One word, used by the tell, the
    booked find and the excursion's scene call alike, so the three cannot disagree about
    what the creature is holding. An excursion that names its own (`spot` in
    content/rules/gathering.json — a seam of salt, a stand of oak) is taken at its word,
    except a herb patch, which is a thicket on ground with cover."""
    if spot and spot != "patch":
        return spot
    if what == "ore":
        return "seam"
    return "thicket" if str(biome or "") in THICKET_GROUND else "patch"


# Ground where herbs grow under cover rather than in the open.
THICKET_GROUND = frozenset({"forest", "jungle", "swamp", "hills"})


def describe(enc: Encounter, what: str, biome: str = "", *, spot: str = "",
             dug: bool | None = None) -> str:
    """The tell's clause for the encounter. `what` is what was being gathered —
    "herbs", "ore", "salts and minerals" — so the rich find reads as a patch or a seam.
    `dug` is whether it comes out of rock (a mined excursion): what the creature comes
    out of, and what a guarded find is a vein of. Defaults to "it is ore"."""
    dug = (what == "ore") if dug is None else bool(dug)
    where = spot_for(what, biome, spot)
    if enc.kind == "rich":
        if what == "herbs":
            return f"A rich patch of {what}, thick enough to double the haul."
        return (f"The ground here is generous: a rich {where} of {what}, and the haul is "
                f"twice what it would have been.")
    if enc.kind == "creature" and enc.creature:
        name = bestiary.kind_word(enc.creature)
        # The second sentence used to be "Something is in the way: a Clockwork Spy has
        # the ground you wanted, and has not moved off it." — which the owner could not
        # parse (playtest 2026-09-30, item 8): what ground, wanted for what, after a haul
        # was already in the satchel? It says where now, and the engine's stance tell
        # (`Engine._hold_ground`) says what the creature is doing about it.
        return (f"Something has noticed the work: {_an(name)} comes out of the "
                f"{'rock' if dug else 'undergrowth'}, and it is coming for you."
                if enc.aggressive else
                f"Making for one last {where}, "
                f"you find {_an(name)} there before you.")
    if enc.kind == "guarded" and enc.creature:
        name = bestiary.kind_word(enc.creature)
        return (f"The find of a lifetime — {'a massive vein of' if dug else 'a whole hollow of'} "
                f"{what}, three times any ordinary haul — and {_an(name)} sitting on it. "
                f"It is yours when that is dead or gone.")
    return ""


# --- one gathering door for every craft ------------------------------------------------
#
# The owner, 2026-10-06: "when i am prospecting for ore using blacksmithing i get almost
# nothing but when i use alchemy to mine ore and salts i get a ton ... Herbalism is the
# only skill that actually prompts the LLM for prose and runs encounter tables. bring the
# rest of the craft actions in line with the herbalist craft actions."
#
# Measured the same day on scratch data, four hours on a mountain at level 1, 50 runs
# each: the hub's Prospect brought 1.28 ore, the alchemist's quarry 1.50 ore plus 3.34 of
# everything else; at level 3 the prospect fell to 0.40 (the hub's DC rose with the
# track's ceiling and its bonus did not) while the spoken prospect gave 1.56 and a forage
# on the same character 4.74 herbs. Three formulas for one act: the forage op's hourly
# Survival bands, the prospect op's one pick an hour, and the hub's single d20 whose
# `take` grew with the size of the pool — which is why the alchemist, whose quarry reads
# the whole shared shelf (34 rows on a mountain, 19 of them the smith's ores and metals),
# out-dug the smith.
#
# One shape now, herbalism's, for every craft that goes out onto open ground: the hour is
# `foraging.forage_hour` (Survival against the terrain's DC, the band, the batches); the
# expedition rolls `roll` once; the clock and the body move through the engine's one
# door. A craft differs only in its TABLE — which materials, weighted how, in what
# batches — and that is data (content/rules/gathering.json), read here.
#
# The specialist's edge is the prior art's, not a new idea: a trade sits its own kinds on
# the table at `own_weight` and takes them in full batches; anything else its shelf says
# turns up on this ground is a side find at `side_weight` and `side_batch` of a batch.
# FFXIV gives each gatherer its own node types with one shared low-value class (crystals);
# WoW's mining node drops ore with stone and gems on the side; Albion multiplies a
# specialist's yield on its own resource. Pathfinder's own nearest rule is Ultimate
# Campaign's Gaining Capital: work done with an unsuitable skill earns half. So the
# alchemist still finds ore in a mountain, at half a batch, among its salts; and the
# smith's seam is mostly ore.

_SPECS: dict | None = None


def _rules_doc() -> dict:
    global _SPECS
    if _SPECS is None:
        import json
        from pathlib import Path

        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "rules" / "gathering.json"
        _SPECS = json.loads(path.read_text(encoding="utf-8"))
    return _SPECS


def excursion(key: str) -> dict | None:
    """One craft's gathering excursion on open ground, defaults filled, or None.

    `key` is the hub's own (`benches.acquisitions`): `track:id`, "blacksmith:prospect".
    """
    doc = _rules_doc()
    key = str(key or "").strip().lower()
    spec = (doc.get("excursions") or {}).get(key)
    if spec is None:
        return None
    track, _, ident = key.partition(":")
    out = dict(doc.get("defaults") or {})
    out.update(spec)
    out.update(key=key, track=track, id=ident)
    out.setdefault("own", [])
    out.setdefault("favour", {})
    out.setdefault("what", "materials")
    out.setdefault("spot", "patch")
    out.setdefault("verb", "searching")
    out.setdefault("sets_out", "to search the ground")
    # How the excursion reaches its shelf: the hub's `obtain` word, from the craft's own
    # ACQUISITION entry, so the data cannot disagree with the button about what is dug.
    if out.get("source") != "ingredients" and "obtain" not in out:
        from . import benches

        hub = next((e for e in benches.acquisitions() if e["key"] == key), {})
        out["obtain"] = str(hub.get("obtain") or "")
    return out


def excursion_keys() -> list[str]:
    return sorted((_rules_doc().get("excursions") or {}).keys())


def material_table(spec: dict, biome: str, rank_ceiling: int):
    """The d100 table one trade reads on this ground, at this ceiling.

    Herbs come off the ingredient list exactly as foraging always laid them
    (`foraging.table_for`). Every other trade's table is its own shelf's `obtainable`
    for the excursion's `obtain` word on this ground, weighted by rarity (the forage
    weights) times how much the trade wants each kind, and laid by the same
    `foraging.lay_table`.
    """
    from . import benches, biomes as biome_mod, foraging

    if spec.get("source") == "ingredients":
        return foraging.table_for(biome, rank_ceiling)
    ground = biome_mod.canonical(biome) or "grassland"
    own = {str(k).lower() for k in spec.get("own") or []}
    favour = {str(k).lower(): float(v) for k, v in (spec.get("favour") or {}).items()}
    found = benches.obtainable(spec["track"], str(spec.get("obtain") or ""), biome=ground)
    cands = []
    for m in found:
        rank = int(getattr(m, "rank", 1) or 1)
        if rank > rank_ceiling:
            continue
        kind = str(getattr(m, "kind", "") or "").lower()
        mine = kind in own
        weight = foraging.WEIGHT.get(rank, 1) * (
            float(spec.get("own_weight", 1)) * favour.get(kind, 1.0) if mine
            else float(spec.get("side_weight", 1)))
        cands.append(foraging.Candidate(
            id=str(m.id), name=str(m.name), tier=str(getattr(m, "tier", "common")),
            rank=rank, weight=weight, kind=kind,
            batch=1.0 if mine else float(spec.get("side_batch", 1.0))))
    return foraging.lay_table(ground, rank_ceiling, cands)


# --- what a carcass carries: the harvest tags ------------------------------------------
#
# Owner, 2026-10-05 (leatherworking round 9): "Apply the tags to the beasts and just have
# a reader in skinning to find the relevant tag; no list is necessary." A creature says
# what can be taken off it in the one tag vocabulary — `harvest.hide.winter-wolf-pelt` on
# the winter wolf's block, or on a World Bible creature's row — and this is the reader.
# The grammar is the leatherworking plan's (§5.3, branch leatherworking/research): each
# craft owns branches under `harvest.`. A tag naming a material its craft's shelf does not
# hold is ignored, never invented into one; `harvest.hide.generic.<surface>` waits for the
# generic hide documents that plan builds.
#
# Before it, every carcass excursion matched the creature's DISPLAY NAME against
# `from_creatures` fragments, so a world's own beast named in its own words — the
# Vormoor "marsh strider" — yielded nothing but tallow and sinew, and a red dragon offered
# eleven colours of dragonhide (leatherworking inventory §0.4).
HARVEST_BRANCHES = {
    "leatherworker": ("hide", "horn", "bone", "sinew", "scales"),
    "blacksmith": ("blood",),
    "alchemist": ("reagent",),
    "enchanter": ("essence",),
    "herbalist": ("part",),
}


def harvest_tagged(creature, track: str) -> list:
    """The materials this creature's own harvest tags give one craft, or [].

    Read off the tags the creature stands on (its stat block's `tags`, live, through
    `Actor.standing_tags`, and any effect's), by prefix under the craft's branches."""
    from . import benches, states

    if creature is None:
        return []
    branches = HARVEST_BRANCHES.get(str(track or "").lower(), ())
    if not branches:
        return []
    tags: list[str] = []
    try:
        tags += list(creature.standing_tags())
    except Exception:  # noqa: BLE001 - a creature with no block simply has no tags
        pass
    for e in getattr(creature, "effects", ()) or ():
        tags += [str(t) for t in (getattr(e, "tags", ()) or ())]
    try:
        shelf = benches.module_for(track).materials()
    except Exception:  # noqa: BLE001
        return []
    out, seen = [], set()
    for tag in tags:
        for branch in branches:
            root = f"harvest.{branch}"
            if not states.matches(tag, root) or tag == root:
                continue
            mid = tag[len(root) + 1:].strip().lower()
            m = shelf.get(mid)
            if m is not None and m.id not in seen:
                seen.add(m.id)
                out.append(m)
    return out


def carcass_yield(track: str, obtain: str, creature, name: str) -> list:
    """What a carcass excursion can turn up: the creature's harvest tags when it carries
    any for this craft, with the goods any carcass gives; its name matched against the
    shelf's `from_creatures` when it carries none (every shipped block, today)."""
    from . import benches

    by_name = benches.obtainable(track, obtain, creature=name or None)
    tagged = harvest_tagged(creature, track)
    if not tagged:
        return by_name
    generic = [m for m in by_name
               if not (getattr(m, "from_creatures", None) or getattr(m, "from_creature", None))]
    seen, out = set(), []
    for m in tagged + generic:
        if m.id not in seen:
            seen.add(m.id)
            out.append(m)
    return out


def dc_for(spec: dict, biome: str) -> int:
    """The DC of an hour on this ground for this trade.

    Herbs read `foraging.FORAGE_DC`, which is herb ground by biome and stays as it was.
    Every other trade reads how much of what it is looking for the ground holds
    (Ultimate Wilderness: abundant DC 10, standard 15, barren 20), counted off its own
    shelf here, at any tier. Measured before this, every trade took the herb DC: a
    mountain was DC 17 to a smith because it is DC 17 to a herbalist, and four hours on
    the mountain — thirteen ores and six metals in its rock — brought a level-1 smith
    1.76 ore (50 runs, 2026-10-06).
    """
    from . import benches, biomes as biome_mod, foraging

    if spec.get("source") == "ingredients":
        return foraging.dc_for(biome)
    ground = biome_mod.canonical(biome) or "grassland"
    own = {str(k).lower() for k in spec.get("own") or []}
    held = sum(1 for m in benches.obtainable(spec["track"], str(spec.get("obtain") or ""),
                                             biome=ground)
               if str(getattr(m, "kind", "") or "").lower() in own)
    bands = sorted((tuple(b) for b in spec.get("abundance") or ()), reverse=True)
    # Most first; the last band (at least 0) is ground with none of the trade's own kinds
    # on it, where the table's side finds are all there is to give.
    for at_least, dc in bands:
        if held >= int(at_least):
            return int(dc)
    return foraging.dc_for(biome)


def mastery_steps(hourly: list[dict]) -> list[dict]:
    """What a day's gathering teaches, hour by hour: one step per hour (§ "every success
    pays", owner 2026-10-05), named for the rarest thing that hour found.

    A success is an hour whose check met the ground's DC and brought something home; it
    pays like a bench step (`worldclass.award_step`, rarity bands above common included).
    An hour that missed the DC is a mishap, which `award_step` pays `MISHAP_LIMIT` times
    per ground and then never again — failing on purpose is still not progress. An hour
    that met the DC on a table with nothing on it is neither: the wood was empty, not the
    gatherer wrong.
    """
    out = []
    for h in hourly:
        if h.get("empty"):
            # Ground with nothing on it for this trade teaches nothing either way:
            # measured on the first run of this door, four hours in the desert "knew
            # nothing that grows" there and still paid two mishaps.
            continue
        got = [p for p in h.get("picks", []) if p.get("id")]
        if int(h.get("margin", -1)) >= 0 and got:
            best = max(got, key=lambda p: int(p.get("rank", 1) or 1))
            out.append({"success": True, "id": best["id"], "name": best["found"],
                        "rank": int(best.get("rank", 1) or 1)})
        elif int(h.get("margin", -1)) < 0:
            out.append({"success": False, "id": str(h.get("biome") or "ground"),
                        "name": f"the {h.get('biome') or 'ground'}", "rank": 1})
    return out


def _an(name: str) -> str:
    return f"an {name}" if name[:1].lower() in "aeiou" else f"a {name}"
