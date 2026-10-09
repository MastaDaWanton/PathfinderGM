"""The harvest of a carcass: one action across the crafts (docs/leatherworking-revamp-plan.md
§5, §6; docs/leatherworking-contracts.md §5; docs/deeds-plan.md §10, §13; lane C).

Before this, four crafts each ran a repeatable excursion over the same body (`skin`,
`salvage`, `harvest-reagents`, `reliquary-harvest`), matched the creature's DISPLAY NAME
against name fragments, rolled a d20 whose margin multiplied the haul and started no clock.
Measured (inventory §0.3, §0.4): six skinnings of one wolf ran and three succeeded; a red
dragon offered all eleven colours of dragonhide; 109 humanoids yielded a hide; a lion, an
elephant and a shark yielded none; the DC rose with the crafter's level (Leatherworker 5 skinned
a wolf at DC 22, level 1 at DC 10); a wolf skinned off the old hub reached the rack with no
clock. And (lanes U5-U7, 2026-10-08) the old excursion offered a wolf feathered, scaled and
chitin hides, because its yield ignored the creature.

**Tags on the beast, a reader here** (the owner, Q9.2: "apply the tags to the beasts and just
have a reader in skinning to find the relevant tag"). A stat block says what comes off it in
the one tag vocabulary (`harvest.hide.winter-wolf-pelt`, `harvest.reagent.ankheg-acid-sac`,
`harvest.danger.poison`; the grammar is docs/campaign-format.md's, branches in
`gathering.HARVEST_BRANCHES`), written by `tools/harvest_tags.py` and reviewed as a table.
This module reads them. It never reads the creature's name: a renamed wolf is still a wolf.
A block with no hide tag falls back to the generic rule by type (so a world's beast that
names a bestiary block still yields), and every other answer — the DC, the units, the tier
of a generic hide, what it inherits, what is dangerous about the body — is read off the stat
block's own fields on every call, never stored as a number.

**The book's numbers** (Ultimate Wilderness, Trophies and Treasures; plan §5.2): Survival for
an external part, Heal for an internal one, DC 15 + CR. The owner's answer 4 (2026-10-08)
adds the craft's level and the skinning kit's +2 to the ROLL; the DC never moves with the
crafter. One part, one roll, taken either way: a good roll does not multiply the haul, a
miss by 4 or less still takes the part a grade worse, a miss by 5 or more ruins it (plan
§5.8, the Craft rule's shape).

**What lands where.** A hide goes through lane E's one writer (`leatherworker.put_hide`),
green with its 48-hour clock started, salted on the spot if the pack holds enough curing
salt — and salt costs salt: one measure per hide unit, spent here (owner, answer 8). A thread,
a quench blood, a gland or an essence goes into the satchel; a herbalist's animal part goes
in with its clock, through the same salt reader (`herbprep.preserve_on_pick`).

**Dangerous bodies** (owner, answers 10 and deeds 6): a poisonous, acid or energy-bearing
body forces a second check per danger kind per carcass at the first cut, exposed only on a
miss by 5 or more (Ultimate Wilderness, Harvesting Poisons). Poison goes through the one
poison door (a Fortitude save gating the printed effect, as `_op_taste` runs it) with 1d3
doses at +2 DC each past the first; acid and energy through the `hazard` op's contact rows.
Both are validated with `origin creature:<template>`, so stage 8's provenance, the mind gate
and immunity apply. A poison nobody printed is never invented.

**Never a humanoid, never a native outsider** (owner Q5.2; deeds answer 3b, 2026-10-08):
the action is never offered on one, and a harvest tag on one is refused (`refused_tags`).

**Deeds** (docs/deeds-plan.md §10): the deeds module decides whether a carcass is a deed
(`deeds.of_carcass`) and records it once per carcass (`deeds.record`). Built in parallel on
build/deeds: until it merges, the two calls fall back to `_DeedsStub` below, which answers
`of_carcass` by the plan's rule and records nothing.
"""
from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path

LEATHER = "leatherworker"
HERBALIST = "herbalist"

SURFACES = ("fur", "scale", "smooth", "feather", "chitin", "shell")
GENERIC = {"fur": "generic-fur-hide", "scale": "generic-scale-hide",
           "smooth": "generic-smooth-hide", "feather": "generic-feather-hide",
           "chitin": "generic-chitin", "shell": "generic-shell"}
PLANS = ("quadruped", "long", "winged", "serpent", "carapace")
ENERGIES = ("acid", "fire", "cold", "electricity", "sonic")
DANGER_KINDS = ("poison",) + ENERGIES
# A bare `harvest.sinew` is the plain sinew every hide-bearing beast gives.
PLAIN_SINEW = "sinew-thread"

# Types that give a hide by the generic rule (plan §5.3), and the surface each gives when the
# block's tags do not say. Everything else gives nothing unless tagged by hand.
GENERIC_TYPES = {"animal": "fur", "magical beast": "fur", "vermin": "chitin",
                 "dragon": "scale"}

SIZES = ("fine", "diminutive", "tiny", "small", "medium", "large", "huge", "gargantuan",
         "colossal")

# Shipped content only (BASE_DIR, never CAMPAIGN_DIR), so it is a plain dict filled once
# and not one of conftest's homebrew-overlay caches (`_NAME: ... | None = None`).
_RULES: dict = {}


def rules() -> dict:
    """content/rules/harvest.json: every number the plan marks proposed."""
    if not _RULES:
        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "rules" / "harvest.json"
        _RULES.update(json.loads(path.read_text(encoding="utf-8")))
    return _RULES


def _craft_of_branch() -> dict[str, str]:
    """The one grammar: `gathering.HARVEST_BRANCHES` names each craft's branches, and the
    excursion reader and this one read the same table."""
    from .gathering import HARVEST_BRANCHES

    return {b: craft for craft, bs in HARVEST_BRANCHES.items() for b in bs}


# =============================================================================================
# The stat block, read
# =============================================================================================

def block_of(creature) -> dict | None:
    """The stat block a creature is: a block itself, a bestiary id, or a scene actor
    (`from_template`, read live like `Actor._creature_doc`)."""
    from . import bestiary

    if creature is None:
        return None
    if isinstance(creature, dict):
        return creature
    if isinstance(creature, str):
        return bestiary.raw(creature) or bestiary.raw_block(creature)
    key = str(getattr(creature, "from_template", "") or "").strip()
    return (bestiary.raw(key) or bestiary.raw_block(key)) if key else None


def template_of(creature) -> str:
    if isinstance(creature, str):
        return creature.strip().lower()
    if isinstance(creature, dict):
        return str(creature.get("id") or "").strip().lower()
    return str(getattr(creature, "from_template", "") or "").strip().lower()


def creature_kind(block: dict | None) -> str:
    """"magical beast", "vermin", ...: the block's type, read as the book's closed list of
    thirteen (`states.type_word`, the one reader the `type.*` tags share). core.json's Type
    column came out of a PDF split on whitespace ("magical", "monstrous", "construc",
    "ve", "animal companion 5"); this module kept its own table of those fragments until
    the leather final pass (2026-10-09), a second reader that the tags did not share, so
    107 magical beasts were `type.magical` on the sheet and "magical beast" here. A type
    outside the thirteen keeps its words."""
    from .states import type_word

    raw = " ".join(str((block or {}).get("creature_type") or "").lower().split())
    word = type_word(raw)
    return word.replace("-", " ") if word else raw


def subtypes(block: dict | None) -> set[str]:
    return {"-".join(re.findall(r"[a-z0-9]+", w.lower()))
            for w in re.split(r"[,;]", str((block or {}).get("subtype") or "")) if w.strip()}


def tags_of(creature) -> list[str]:
    """The tags a creature stands on that this reader asks: its stat block's own `tags`,
    and, for a scene actor, any effect's (a world creature's tags may arrive that way)."""
    out = [str(t) for t in ((block_of(creature) or {}).get("tags") or ()) if str(t).strip()]
    for e in getattr(creature, "effects", ()) or ():
        out += [str(t) for t in (getattr(e, "tags", ()) or ())]
    return list(dict.fromkeys(out))


def cr_of(block: dict | None) -> float:
    try:
        return float((block or {}).get("cr_value") or 0)
    except (TypeError, ValueError):
        return 0.0


def size_of(block: dict | None) -> str:
    s = str((block or {}).get("size") or "medium").strip().lower()
    return s if s in SIZES else "medium"


def hit_dice(block: dict | None) -> int:
    """Racial hit dice from the printed `hit_dice` ("(2d8+4)", "(currently 11, 2d8+4)")."""
    m = re.search(r"(\d+)\s*d\s*\d+", str((block or {}).get("hit_dice") or ""))
    return int(m.group(1)) if m else 1


def ability_mod(block: dict | None, ability: str) -> int:
    try:
        score = int(((block or {}).get("abilities") or {}).get(ability) or 10)
    except (TypeError, ValueError):
        score = 10
    return (score - 10) // 2


def natural_armour(block: dict | None) -> int:
    """The block's natural armour: its printed breakdown's "+N natural", or, on a block that
    prints no breakdown but its touch AC ("touch 10, flat-footed 20", 828 imported blocks),
    its AC less its touch AC, which is what a touch attack ignores: armour, shield and
    natural armour (CRB, Touch Attacks). Only a beast's hide is generic (`GENERIC_TYPES`:
    animals, magical beasts, vermin, dragons wear no armour), so for the bodies this is
    asked of the difference is the natural armour. Measured 2026-10-09: 255 such beasts
    print no breakdown, the bulette among them (AC 22, touch 10), and every one read as
    natural armour 0, so not one could give a thick hide; 132 of them are +5 or more."""
    from . import bestiary

    note = str((block or {}).get("ac_note") or "")
    parts = bestiary.ac_parts(note)
    if parts:
        return sum(v for v, src, typ in parts if typ == "natural armour")
    nums = bestiary.ac_numbers(note)
    if not nums or creature_kind(block) not in GENERIC_TYPES:
        return 0
    try:
        return max(0, int((block or {}).get("flat_ac") or 0) - int(nums[0]))
    except (TypeError, ValueError):
        return 0


def side_of(block: dict | None) -> str:
    """"good", "evil" or "" from the printed alignment, read through the one reader,
    `bestiary.printed_alignment` (good is `bestiary.printed_good`: every alternative printed
    is good, so "NG/CN" is neither)."""
    from . import bestiary

    if bestiary.printed_good(block or {}):
        return "good"
    words = re.findall(r"[A-Z]{2}", bestiary.printed_alignment(block or {}).upper())
    if words and all(w in ("LE", "NE", "CE") for w in words):
        return "evil"
    return ""


def _text(block: dict | None, *fields) -> str:
    return html.unescape(" ".join(str((block or {}).get(f) or "") for f in fields))


# =============================================================================================
# Who is never harvested
# =============================================================================================

def banned(block: dict | None) -> str:
    """Why this body is never harvested, or "". Humanoids (owner Q5.2) and native outsiders
    — aasimar, tieflings, sylphs: peoples, not beasts (deeds answer 3b, 2026-10-08). The
    rule is the deeds lane's `never_harvested` (asked first, deeds plan §10); this module's
    own reading of the same two tags stands in only while that is not on the branch."""
    if block is None:
        return ""
    gate = getattr(_deeds(), "never_harvested", None)
    try:
        never = bool(gate(block)) if callable(gate) else None
    except Exception:          # noqa: BLE001 - the local reading below
        never = None
    kind = creature_kind(block)
    if never is None:
        never = kind == "humanoid" or (kind == "outsider" and "native" in subtypes(block))
    if not never:
        return ""
    if kind == "humanoid":
        return "a person is never harvested"
    return "a native outsider is a people, never harvested"


# =============================================================================================
# True dragons and their colour
# =============================================================================================

_BREATH = re.compile(r"breath weapon\s*\(([^)]*)\)", re.I)


def breath(block: dict | None) -> dict | None:
    """{"energy", "shape"} of the printed breath weapon, or None."""
    m = _BREATH.search(_text(block, "special_attacks"))
    if not m:
        return None
    inside = m.group(1).lower()
    shape = "line" if "line" in inside else "cone" if "cone" in inside else ""
    energy = next((e for e in ("negative energy", "electricity", "fire", "cold", "acid",
                               "sonic") if e in inside), "")
    return {"energy": energy.replace(" energy", ""), "shape": shape}


def is_true_dragon(block: dict | None) -> bool:
    """A true dragon prints `dragon senses` (Bestiary universal ability); drakes, wyverns and
    linnorms do not."""
    return creature_kind(block) == "dragon" and "dragon sense" in _text(block, "senses").lower()


def dragon_colour(block: dict | None) -> str | None:
    """The dragonhide a true dragon's own block says it is (rule rows `dragonhides`): its
    breath's energy and shape and its printed good or evil. Never its name. None for a
    dragon no shipped dragonhide describes (an imperial or primal dragon)."""
    if not is_true_dragon(block):
        return None
    b = breath(block) or {}
    side = side_of(block)
    for mid, row in (rules().get("dragonhides") or {}).items():
        if (row.get("energy") == b.get("energy") and row.get("shape") == b.get("shape")
                and row.get("side") == side):
            return mid
    return None


# =============================================================================================
# Validation: what a tag may not say
# =============================================================================================

def _material(mid: str) -> dict | None:
    from . import materials

    try:
        return materials.get(mid)
    except Exception:          # noqa: BLE001 - a bad document is "no such material"
        return None


def _shelf(craft: str) -> dict:
    """The materials one craft can take by id: the herbalist's ingredients, or the craft's
    own shelf (`benches.module_for(...).materials()`, as `gathering.harvest_tagged` reads)."""
    if craft == HERBALIST:
        from . import ingredients

        try:
            return dict(ingredients.all_ingredients())
        except Exception:      # noqa: BLE001
            return {}
    from . import benches

    try:
        return dict(benches.module_for(craft).materials())
    except Exception:          # noqa: BLE001
        return {}


def _parse(tag: str) -> tuple[str, str]:
    """("hide", "winter-wolf-pelt") from `harvest.hide.winter-wolf-pelt`; ("hide",
    "generic.fur"); ("sinew", ""); ("", "") for anything not under `harvest.`."""
    if not str(tag).startswith("harvest."):
        return "", ""
    rest = str(tag)[len("harvest."):]
    branch, _, leaf = rest.partition(".")
    return branch.strip().lower(), leaf.strip().lower()


def refused_tags(block: dict | None, tags=None) -> dict[str, str]:
    """{tag: why it is refused, with the fix named} for every harvest tag this block may not
    carry (plan §5.3's validators, run on every read so a refused tag yields nothing):
    any part on a humanoid or native outsider; a tag naming a material no shelf has; a true
    dragon tagged with another colour's dragonhide (inventory §0.4)."""
    tags = list(tags if tags is not None else ((block or {}).get("tags") or ()))
    out: dict[str, str] = {}
    why_banned = banned(block)
    branches = _craft_of_branch()
    colour = dragon_colour(block)
    hides = set((rules().get("dragonhides") or {}))
    for tag in tags:
        branch, leaf = _parse(tag)
        if not branch:
            continue
        if branch in ("plan", "danger"):
            continue
        if why_banned:
            out[tag] = f"{why_banned}: remove the tag"
            continue
        if branch not in branches:
            out[tag] = (f"no harvest branch {branch!r}: the branches are "
                        f"{', '.join(sorted(branches))}, plus plan and danger")
            continue
        if not leaf:
            if branch != "sinew":
                out[tag] = f"harvest.{branch} needs a material id after it"
            continue
        if branch == "hide" and leaf.startswith("generic."):
            if leaf.split(".", 1)[1] not in GENERIC:
                out[tag] = f"no generic surface {leaf.split('.', 1)[1]!r}: {', '.join(SURFACES)}"
            continue
        if leaf not in _shelf(branches[branch]):
            out[tag] = (f"no {branches[branch]} material {leaf!r}: name one that exists, "
                        f"or remove the tag")
            continue
        if branch == "hide" and leaf in hides and is_true_dragon(block) and leaf != colour:
            out[tag] = (f"this true dragon's own block says {colour or 'no shipped colour'}"
                        f" (its breath and alignment), not {leaf}: remove the tag")
    return out


def validate_tags(block: dict | None) -> list[str]:
    """The problems, one line each (contracts §5.2), for the tag pass and the tests."""
    name = str((block or {}).get("id") or (block or {}).get("name") or "a block")
    return [f"{name}: {tag}: {why}" for tag, why in refused_tags(block).items()]


# =============================================================================================
# What the body carries
# =============================================================================================

def generic_surface(block: dict | None) -> str | None:
    """The generic rule's surface by type (plan §5.3), for a block with no hide tag."""
    if banned(block):
        return None
    # No body to skin: an incorporeal thing, or a swarm of a thousand tiny ones.
    if subtypes(block) & {"incorporeal", "swarm"}:
        return None
    return GENERIC_TYPES.get(creature_kind(block))


def generic_for(creature) -> str | None:
    """The generic hide id this creature gives by the rule, or None (contracts §5.2)."""
    surface = generic_surface(block_of(creature))
    return GENERIC.get(surface) if surface else None


def tagged(creature) -> list[tuple[str, str]]:
    """[(branch, material id)] this body carries, in tag order, refused tags dropped; the
    generic rule when it carries no hide tag at all (an untagged or world block)."""
    block = block_of(creature)
    if block is None and not getattr(creature, "effects", None):
        return []
    tags = tags_of(creature)
    if banned(block):
        return []
    refused = refused_tags(block, tags)
    out: list[tuple[str, str]] = []
    for tag in tags:
        if tag in refused:
            continue
        branch, leaf = _parse(tag)
        if not branch or branch in ("plan", "danger"):
            continue
        if branch == "hide" and leaf.startswith("generic."):
            out.append(("hide", GENERIC[leaf.split(".", 1)[1]]))
        elif branch == "sinew" and not leaf:
            out.append(("sinew", PLAIN_SINEW))
        elif leaf:
            out.append((branch, leaf))
    if not any(b == "hide" for b, _ in out):
        mid = generic_for(block)
        if mid:
            out.append(("hide", mid))
            if not any(b == "sinew" for b, _ in out):
                out.append(("sinew", PLAIN_SINEW))
    return list(dict.fromkeys(out))


def plan_of(creature) -> str:
    """The body plan the bench's 3D hide is drawn from (`harvest.plan.*`; drawing only)."""
    for tag in tags_of(creature):
        branch, leaf = _parse(tag)
        if branch == "plan" and leaf in PLANS:
            return leaf
    return "carapace" if creature_kind(block_of(creature)) == "vermin" else "quadruped"


def tier_of_cr(cr: float) -> str:
    out = "common"
    for low, tier in rules().get("cr_tiers") or ():
        if float(cr) >= float(low):
            out = str(tier)
    return out


def units_for(block: dict | None, branch: str, mid: str) -> float:
    """Hide units by the creature's size (plan §5.5: Medium 1, doubling); a true dragon of
    Large or more gives one more, the book's "enough for a shield"; every other part is one."""
    if branch not in ("hide", "scales"):
        return 1.0
    from . import leatherworker as lw

    units = lw.units_of_size(size_of(block))
    if branch == "hide" and is_true_dragon(block) and SIZES.index(size_of(block)) >= 5:
        units += 1
    return float(units)


# =============================================================================================
# What a generic hide inherits (plan §5.4; owner answer 6)
# =============================================================================================

def _tier_ceiling(tier: str) -> int:
    from . import materials

    return int(getattr(materials, "TIER_CEILING", {}).get(tier, 2))


def _resist_amounts(block: dict | None) -> dict[str, int]:
    """{energy: amount} printed resistances (`resist` entries: "fire 10", {"type", "amount"})."""
    out: dict[str, int] = {}
    for r in (block or {}).get("resist") or ():
        if isinstance(r, dict):
            kind = str(r.get("type") or r.get("energy") or "").lower()
            amount = r.get("amount")
        else:
            m = re.match(r"\s*([a-z]+)\s+(\d+)", str(r).lower())
            kind, amount = (m.group(1), m.group(2)) if m else ("", None)
        if kind in ENERGIES:
            try:
                out[kind] = max(out.get(kind, 0), int(amount))
            except (TypeError, ValueError):
                continue
    return out


def _immune_energies(block: dict | None) -> list[str]:
    return [str(i).strip().lower() for i in ((block or {}).get("immune") or ())
            if str(i).strip().lower() in ENERGIES]


def _best_dr(block: dict | None) -> tuple[int, str] | None:
    best = None
    for r in (block or {}).get("reductions") or ():
        if not isinstance(r, dict):
            continue
        try:
            amount = int(r.get("amount") or 0)
        except (TypeError, ValueError):
            continue
        if amount > 0 and (best is None or amount > best[0]):
            best = (amount, str(r.get("bypass") or "-"))
    return best


def inherited(creature) -> list[dict]:
    """The effect specs a GENERIC hide takes from its beast, derived from the stat block on
    every read and never stored (contracts §4.1; `forge_items._inherited` calls this lazily
    and stamps `from_creature` itself, applying them whole from the body only, never scaled —
    the lead's ruling of 2026-10-08):

    - its highest energy resistance ÷ 5, at least 1 — an immunity counts as the tier's
      ceiling — capped by the tier ceiling; only the highest energy;
    - on a rare-or-rarer hide, its highest DR as DR max(1, N ÷ 5)/bypass, capped by the
      tier ceiling (owner, answer 6: "add the reduced DR").

    Natural armour's `thick` trait is a working trait, not an effect: `working_traits`."""
    block = block_of(creature)
    if block is None or banned(block):
        return []
    r = rules()
    tier = tier_of_cr(cr_of(block))
    ceiling = _tier_ceiling(tier)
    out: list[dict] = []
    best: tuple[int, str] | None = None
    for energy in _immune_energies(block):
        if best is None or ceiling > best[0]:
            best = (ceiling, energy)
    for energy, amount in _resist_amounts(block).items():
        got = min(ceiling, max(1, int(amount) // int(r.get("resist_divisor", 5))))
        if best is None or got > best[0]:
            best = (got, energy)
    if best:
        out.append({"type": "resistance", "target": best[1], "amount": int(best[0])})
    from . import worldclass

    if worldclass.tier_rank(tier) >= worldclass.tier_rank(str(r.get("dr_from_tier", "rare"))):
        dr = _best_dr(block)
        if dr:
            amount = min(ceiling, max(1, dr[0] // int(r.get("dr_divisor", 5))))
            out.append({"type": "damage_reduction", "amount": int(amount), "bypass": dr[1]})
    return out


def working_traits(creature) -> list[str]:
    """Working traits a generic hide takes from its beast: `thick` at natural armour +5 or
    more (plan §5.4), the one that lets it make hide armour."""
    block = block_of(creature)
    if block is None:
        return []
    return ["thick"] if natural_armour(block) >= int(rules().get("thick_natural", 5)) else []


# =============================================================================================
# Dangerous bodies (docs/deeds-plan.md §13)
# =============================================================================================

_RIDER = re.compile(r"plus\s+(?:\d+d\d+(?:\s*[+-]\s*\d+)?\s+)?(poison|acid|fire|cold|electricity|"
                    r"sonic)\b", re.I)
_POISON_PARA = re.compile(r"Poison(?:ous (?:Blood|Flesh))?\s*\((?:Ex|Su)\)\s*:?\s*(.*?)"
                          r"(?:\bcure\s+[^.;]*[.;]|$)", re.I | re.S)


def poison_paragraph(block: dict | None) -> str:
    """The block's own printed poison paragraph up to its cure clause, or "". Only the
    block's own text: a core block that prints a "plus poison" rider and no paragraph has
    none, and a poison nobody printed is never invented (docs/deeds-plan.md §13.4)."""
    text = _text(block, "special_abilities")
    for m in _POISON_PARA.finditer(text):
        body = m.group(1)
        if re.search(r"\bDC\s*\d+", body) and re.search(r"\beffect\b", body, re.I):
            return " ".join(m.group(0).split())
    return ""


def poison_specs(block: dict | None) -> list[dict]:
    """The printed poison as specs (`effects.extract`): a `save_gate` and what it gates."""
    para = poison_paragraph(block)
    if not para:
        return []
    from . import effects

    return [dict(e.spec) for e in effects.extract(para) if e.spec]


def dangers(creature) -> list[str]:
    """The danger kinds of this body: `harvest.danger.*` tags when the block carries any,
    else derived from its fields (the tag pass writes exactly this function's answer). Read
    from the stat block, never a name. Refused, with reasons (§13.2): auras (the living
    creature's), immunity alone (a fire-immune hide is a fine hide, not a hot one), air,
    earth and water subtypes, and breaths with no book damage for touching them."""
    kinds = [leaf for b, leaf in (_parse(t) for t in tags_of(creature))
             if b == "danger" and leaf in DANGER_KINDS]
    if kinds:
        return list(dict.fromkeys(kinds))
    return derive_dangers(block_of(creature))


def derive_dangers(block: dict | None) -> list[str]:
    if block is None:
        return []
    out: list[str] = []
    attacks = _text(block, "melee", "ranged", "special_attacks")
    abilities = _text(block, "special_abilities")
    subs = subtypes(block)
    riders = {m.group(1).lower() for m in _RIDER.finditer(attacks)}
    b = breath(block) or {}
    if "poison" in riders or re.search(r"\bpoison\b", _text(block, "special_attacks"), re.I) \
            or re.search(r"Poison(?:ous (?:Blood|Flesh))?\s*\((?:Ex|Su)\)", abilities, re.I):
        out.append("poison")
    if "acid" in riders or re.search(r"\bcorrosion\b", attacks + " " + abilities, re.I) \
            or b.get("energy") == "acid":
        out.append("acid")
    if "fire" in riders or "fire" in subs or b.get("energy") == "fire" \
            or re.search(r"\bburn\s*\(|\bheat\b", _text(block, "special_attacks"), re.I) \
            or re.search(r"\b(?:Burn|Heat)\s*\((?:Ex|Su)\)", abilities):
        out.append("fire")
    if "cold" in riders or "cold" in subs or b.get("energy") == "cold":
        out.append("cold")
    if "electricity" in riders or b.get("energy") == "electricity":
        out.append("electricity")
    if b.get("energy") == "sonic":
        out.append("sonic")
    return out


def contact_dice(creature, energy: str = "fire") -> str:
    """The dice a body's touch deals (§13.4): its own printed burn or heat dice for fire
    ("burn (1d8, DC 16)", "heat (1d6 fire)", "Heat (Ex) ... an additional 1d8 points of fire
    damage"), else the book's small 1d6. Never its breath weapon's dice: the gland is not
    the breath. Read by the `hazard` op for a contact row stamped `creature:<template>`."""
    block = block_of(creature)
    if energy == "fire" and block is not None:
        attacks = _text(block, "special_attacks")
        m = re.search(r"\bburn\s*\(\s*(\d+d\d+)", attacks, re.I) \
            or re.search(r"\bheat\s*\(\s*(\d+d\d+)", attacks, re.I) \
            or re.search(r"\bHeat\s*\((?:Ex|Su)\)[^.]*?(\d+d\d+)", _text(block,
                                                                          "special_abilities"))
        if m:
            return m.group(1)
    return "1d6"


def danger_dc(block: dict | None, kind: str) -> int:
    """The creature's own number (§13.3): the printed poison DC, the printed burn DC, else
    the universal monster rule's 10 + ½ HD + Con modifier. Nothing authored."""
    if kind == "poison":
        m = re.search(r"\bDC\s*(\d+)", poison_paragraph(block))
        if m:
            return int(m.group(1))
    if kind == "fire":
        m = re.search(r"\bburn\s*\([^)]*?DC\s*(\d+)", _text(block, "special_attacks"), re.I)
        if m:
            return int(m.group(1))
    return 10 + hit_dice(block) // 2 + ability_mod(block, "con")


def danger_rounds(creature) -> list[dict]:
    """The rounds this carcass forces, one per danger kind, minus any already faced
    (`harvested["danger:<kind>"]`). A poison with no printed paragraph that parses to a save
    and an effect runs no round."""
    block = block_of(creature)
    faced = dict(getattr(creature, "harvested", None) or {})
    out = []
    for kind in dangers(creature):
        if kind == "poison" and not _poison_runs(block):
            continue
        out.append({"kind": kind, "dc": danger_dc(block, kind), "faced": f"danger:{kind}" in faced,
                    "dice": contact_dice(block, kind) if kind != "poison" else None,
                    "words": DANGER_WORDS.get(kind, kind)})
    return out


DANGER_WORDS = {"poison": "venom in the body", "acid": "acid in the flesh",
                "fire": "a body hot to the touch", "cold": "a body that freezes the hand",
                "electricity": "a body that still holds a charge",
                "sonic": "a throat that still rings"}


def _poison_runs(block) -> bool:
    specs = poison_specs(block)
    return any(s.get("type") == "save_gate" and s.get("dc") for s in specs) and any(
        s.get("type") in ("ability_damage", "ability_drain", "damage", "apply_condition")
        for s in specs)


# =============================================================================================
# The carcass
# =============================================================================================

def is_dead(creature) -> bool:
    try:
        return bool(creature.has_state("state.down.dead"))
    except Exception:          # noqa: BLE001
        return False


def mark_the_dead(scene) -> None:
    """Stamp `died_at` on every newly dead body in the party's place, at the scene's clock.
    Called by `Engine._drive` after each outcome (plan §5.9: "recorded as `died_at` on the
    scene actor when it drops"). A body that died before this existed is stamped the first
    time anybody asks (`died_at_of`)."""
    now = int(getattr(scene, "clock_minutes", 0) or 0)
    for a in list(getattr(scene, "actors", {}).values()):
        if getattr(a, "is_pc", False) or getattr(a, "died_at", None) is not None:
            continue
        if is_dead(a):
            a.died_at = now


def died_at_of(creature, now: int) -> int:
    got = getattr(creature, "died_at", None)
    if got is None:
        creature.died_at = int(now)
        return int(now)
    return int(got)


def harvestable(creature, *, now: int) -> tuple[bool, str]:
    """Whether anything may be taken off this body now, and why not (contracts §5.2): dead,
    within `carcass_hours` of death, not a humanoid or native outsider."""
    if creature is None:
        return False, "there is nothing there"
    if getattr(creature, "is_pc", False):
        return False, "not you"
    if not is_dead(creature):
        return False, "it is not dead"
    block = block_of(creature)
    why = banned(block)
    if why:
        return False, why
    hours = int(rules().get("carcass_hours", 24))
    if int(now) - died_at_of(creature, now) > hours * 60:
        return False, f"it has been dead more than {hours} hours: nothing on it is worth taking"
    if not tagged(creature):
        return False, "nothing on it is worth taking"
    return True, ""


# =============================================================================================
# The parts
# =============================================================================================

def _craft_level(actor, craft: str) -> int:
    """The craft's level, read without beginning the track (`Actor.track` begins one on
    first use, at level 1, which is what an untouched track counts as)."""
    prog = (getattr(actor, "world_classes", None) or {}).get(craft)
    try:
        return int(prog.level) if prog is not None else 1
    except (TypeError, ValueError):
        return 1


def _craft_word(craft: str) -> str:
    from . import worldclass

    try:
        return str(worldclass.get(craft).name)
    except Exception:          # noqa: BLE001
        return craft.title()


def skill_for(branch: str, mid: str) -> str:
    doc = _material(mid) or {}
    said = str(doc.get("harvest_skill") or "").strip().lower()
    if said in ("survival", "heal"):
        return said
    return str(((rules().get("branches") or {}).get(branch) or {}).get("skill") or "survival")


def check_terms(actor, craft: str, skill: str) -> list[dict]:
    """The roll, itemised: the skill's own terms, the craft's level (owner answer 4), the
    skinning kit's +2 circumstance when the leatherworker's field kit is carried."""
    terms: list[dict] = []
    try:
        for m in actor.skill_modifiers(skill):
            terms.append({"label": m.source, "value": int(m.value)})
    except Exception:          # noqa: BLE001 - an untrained skill adds nothing, it is not barred
        pass
    level = _craft_level(actor, craft)
    if level:
        terms.append({"label": f"{_craft_word(craft)} {level}", "value": level})
    from . import places

    try:
        kit = places.has_field_kit(actor, LEATHER)
    except Exception:          # noqa: BLE001
        kit = False
    if kit:
        terms.append({"label": "skinning kit (circumstance)",
                      "value": int(rules().get("kit_bonus", 2))})
    return terms


def dc_of(block: dict | None) -> int:
    """15 + CR (the creature's own `cr_value`, fractions down). Never the crafter's level."""
    return int(rules().get("dc_base", 15)) + max(0, int(math.floor(cr_of(block))))


def _name_of(craft: str, mid: str) -> tuple[str, str]:
    """(name, tier) of a part's material."""
    if craft == HERBALIST:
        ing = _shelf(HERBALIST).get(mid)
        return (str(getattr(ing, "name", mid)), str(getattr(ing, "tier", "") or
                                                      getattr(ing, "rarity", "") or "common"))
    doc = _material(mid) or {}
    return str(doc.get("name") or mid.replace("-", " ").title()), str(doc.get("tier") or "common")


def minutes_for(branch: str, units: float) -> int:
    row = (rules().get("branches") or {}).get(branch) or {}
    if row.get("minutes_per_unit"):
        return int(min(int(row.get("max_minutes", 60)),
                       max(1, math.ceil(float(units) * int(row["minutes_per_unit"])))))
    return int(row.get("minutes", 10))


def part_key(branch: str, mid: str) -> str:
    return f"{branch}:{mid}"


def parts(creature, actor, *, now: int, every_craft: bool = False) -> list[dict]:
    """One row per part this carcass carries for the crafts `actor` has (level 1 or more;
    `every_craft` for all of them), each with its skill, DC, roll terms, the face needed,
    units, time, whether taking it is a deed, whether it is taken, and whether it has a game
    (contracts §5.2). Read off the tags and the block; never the name."""
    block = block_of(creature)
    branches = _craft_of_branch()
    taken = dict(getattr(creature, "harvested", None) or {})
    deed = deed_of(creature)
    out: list[dict] = []
    for branch, mid in tagged(creature):
        craft = branches.get(branch)
        if not craft:
            continue
        if not every_craft and _craft_level(actor, craft) < 1:
            continue
        name, tier = _name_of(craft, mid)
        generic = mid in GENERIC.values()
        if generic:
            tier = tier_of_cr(cr_of(block))
        units = units_for(block, branch, mid)
        if branch in ("hide", "scales") and units <= 0:
            continue            # Fine and Diminutive: sinew only, no hide (plan §5.5)
        skill = skill_for(branch, mid)
        terms = check_terms(actor, craft, skill)
        bonus = sum(t["value"] for t in terms)
        dc = dc_of(block)
        from .crafting import check_odds

        need, impossible = check_odds(dc, bonus)
        key = part_key(branch, mid)
        game = ((rules().get("branches") or {}).get(branch) or {}).get("game")
        out.append({
            "key": key, "craft": craft, "craft_word": _craft_word(craft),
            "branch": branch, "material": mid, "name": name, "tier": tier,
            "generic": generic,
            "form": "green" if branch in ("hide", "scales") else "",
            "skill": skill, "dc": dc, "bonus": bonus, "terms": terms,
            "need": need, "impossible": impossible,
            "units": units, "minutes": minutes_for(branch, units),
            "deed": deed, "taken": taken.get(key), "game": game,
        })
    return out


# =============================================================================================
# Deeds (docs/deeds-plan.md §10), through the deeds module when it is merged
# =============================================================================================

class _DeedsStub:
    """The three calls lane C makes, until build/deeds is merged into this branch (deeds
    plan §11: "Leather C can build against a two-line stub ... and swap it at merge"); the
    names and signatures are rules/deeds.py's own (merged on build/leatherworking, 436f1b7).
    `never_harvested` is None here, so `banned` reads the two tags itself; `of_carcass`
    answers by the plan's rule (deeds answer 3: the good subtype OR a printed good
    alignment; a dragon by its printed alignment), from tags and the printed field, never
    the name; `record` writes nothing, the store (`Actor.deeds`) being the deeds lane's."""

    never_harvested = None

    @staticmethod
    def of_carcass(creature) -> str | None:
        block = block_of(creature) or {}
        kind = creature_kind(block)
        good = side_of(block) == "good"
        if kind == "outsider" and ("good" in subtypes(block) or good):
            return "deed.harvest.good-outsider"
        if kind == "dragon" and good:
            return "deed.harvest.good-dragon"
        return None

    @staticmethod
    def record(actor, tag, **kw) -> dict | None:
        return None


def _deeds():
    try:
        from . import deeds as real   # noqa: F401 - rules/deeds.py, the deeds lane's
    except ImportError:
        return _DeedsStub
    if not (hasattr(real, "of_carcass") and hasattr(real, "record")):
        return _DeedsStub
    return real


def deed_of(creature) -> str | None:
    """`deeds.of_carcass`, asked of the stat block (it takes a block or an Actor): measured
    2026-10-08, an Actor spawned by an index-style name ("lantern-archon" for the block
    `archon-lantern`) has no `type.*` tags, because `Actor._creature_doc` reads
    `bestiary.raw` and not `raw_block`, and the real `of_carcass` answered None for it."""
    try:
        return _deeds().of_carcass(block_of(creature) or creature)
    except Exception:          # noqa: BLE001 - a deed is never worth failing a harvest for
        return None


# =============================================================================================
# The clock and the salt (plan §6)
# =============================================================================================

def freshness(stock, now: int) -> dict:
    """{"spoiled", "hours_left", "why", "clock"} of a hide record (contracts §4.1's dict, or a
    `leatherworker.Hide`): 48 hours green from the harvest (a document's `fresh_hours` wins),
    six weeks once salted, then its own clock again; tanned work never spoils. Computed on
    read, never stored. `leatherworker.freshness` asks this first, so the bench and the
    harvest sheet cannot disagree."""
    from . import leatherworker as lw

    rec = stock if isinstance(stock, dict) else (lw.record_of_hide(stock) or {})
    form = str(rec.get("form") or "")
    harvested_at = rec.get("harvested_at")
    if form not in ("green", "salted", "pelt") or harvested_at is None:
        return {"spoiled": False, "hours_left": None, "why": "", "clock": False}
    bench = lw.bench_rules()
    row = lw._shelf_row(str(rec.get("material") or ""))
    window = int(getattr(row, "fresh_hours", None) or bench.get("fresh_hours")
                 or lw.FRESH_HOURS) * 60
    now = int(now)
    salted_at = rec.get("salted_at")
    if salted_at is not None:
        until = int(salted_at) + int(bench.get("salted_keep_minutes", 60480))
        if now < until:
            return {"spoiled": False, "hours_left": (until - now) // 60, "clock": False,
                    "why": "salted: it keeps"}
        left = until + window - now
    else:
        left = int(harvested_at) + window - now
    if left <= 0:
        return {"spoiled": True, "hours_left": 0, "clock": True,
                "why": "it has spoiled: scraps and glue stock now, nothing more"}
    from . import sky

    return {"spoiled": False, "hours_left": left // 60, "clock": True,
            "why": f"spoils in {sky.span_words(left)} unless salted or tanned"}


def salt_measures(actor) -> int:
    """Measures of curing salt carried (contracts §5.3), through herbalism's one reader."""
    from . import herbprep

    return herbprep.salt_measures(actor)


def _salt_per_unit() -> float:
    from . import leatherworker as lw

    return float((lw.method_row("salt") or {}).get("salt_per_unit", 1) or 1)


# =============================================================================================
# Taking a part
# =============================================================================================

def grade_of(defects) -> int:
    """The harvest game's defect area (0..1) as a grade, 1 clean to 4, 0 a reject (plan §5.7,
    the UNIDO bands in the rule rows). The page reports the area; this decides the grade."""
    try:
        d = min(1.0, max(0.0, float(defects)))
    except (TypeError, ValueError):
        return int(rules().get("unplayed_grade", 3))
    for most, grade in rules().get("grade_bands") or ():
        if d <= float(most) + 1e-9:
            return int(grade)
    return 0


def graded(game_grade: int, margin: int) -> int:
    """The game's grade after the roll's verdict: a near miss is one grade worse and never
    better than `near_miss_best` (plan §5.8). A reject stays a reject."""
    g = int(game_grade)
    if margin >= 0 or g == 0:
        return g
    r = rules()
    return min(4, max(g + 1, int(r.get("near_miss_best", 3))))


def _yield_roll(actor, dice) -> bool:
    """The Yield perk (owner Q6.3: moved to the harvest): its chance per hide taken."""
    from . import worldclass

    try:
        chance = float(worldclass.perk_multipliers(actor.track(LEATHER)).get("yield_chance", 0))
    except Exception:          # noqa: BLE001
        chance = 0.0
    if chance <= 0 or dice is None:
        return False
    return dice.roll("1d100", label="Yield", visibility="hidden").total <= round(chance * 100)


def _land_hide(actor, mid: str, *, quarters: int, grade: int, now: int, creature: str,
               tier: str, salt_q: int, form: str = "green") -> list[dict]:
    """Through lane E's one writer. `salt_q` of the quarters land salted, the rest green."""
    from . import leatherworker as lw

    out = []
    chunks = []
    if form == "scrap":
        chunks = [("scrap", quarters, None)]
    else:
        if salt_q > 0:
            chunks.append(("salted", salt_q, now))
        if quarters - salt_q > 0:
            chunks.append((form, quarters - salt_q, None))
    for f, q, salted in chunks:
        h = lw.make_hide(mid, form=f, units=q / 4, grade=grade, harvested_at=int(now),
                         salted_at=salted, creature=creature, tier=tier)
        key = lw.put_hide(actor, h)
        out.append({"key": key, "name": lw.hide_name(h), "form": f, "units": q / 4,
                    "grade": grade, "material": mid})
    return out


def take(actor, creature, key: str, roll_total: int, *, now: int, scene=None, dice=None,
         defects=None) -> dict:
    """Take one part (contracts §5.2's `take`). The part is marked taken whatever the roll
    said — no retry, the measured "six skinnings of one wolf" closed — and what it gives lands
    at once, so a reload between the roll and the game loses nothing: a hide lands at the
    unplayed grade and `regrade` gives it the game's (pass `defects` to grade it now).

    Returns {"ok", "margin", "stock": [...], "carried": [...], "grade", "lost", "deed",
    "salt_spent", "yielded", "tells", "game": {...} | None}."""
    from . import leatherworker as lw

    row = next((p for p in parts(creature, actor, now=now, every_craft=True)
                if p["key"] == key), None)
    if row is None:
        raise KeyError(f"no part {key!r} on this carcass")
    if row["taken"] is not None:
        raise ValueError(f"the {row['name']} has already been taken")
    taken = dict(getattr(creature, "harvested", None) or {})
    first_cut = not any(not k.startswith("danger:") for k in taken)
    taken[key] = int(now)
    creature.harvested = taken

    r = rules()
    margin = int(roll_total) - int(row["dc"])
    out = {"ok": margin >= 0, "margin": margin, "stock": [], "carried": [], "grade": None,
           "lost": "", "deed": None, "salt_spent": 0, "yielded": False, "tells": [],
           "game": None, "key": key, "name": row["name"], "craft": row["craft"]}
    who = str(getattr(actor, "name", "") or "You")
    body = str(getattr(creature, "name", "") or "the carcass")
    ruin = margin <= -int(r.get("ruin_margin", 5))

    # The deed, once per carcass (deeds plan §10), on the first part, whatever the roll.
    if first_cut and row["deed"]:
        try:
            out["deed"] = _deeds().record(
                actor, row["deed"], scene=scene, subject=getattr(creature, "ref", None),
                subject_name=body, what="", how="meant")
        except Exception:      # noqa: BLE001 - the store is the deeds lane's
            out["deed"] = None
        out["deed_tag"] = row["deed"]

    if row["branch"] in ("hide", "scales"):
        q = lw.quarters(row["units"])
        grade = grade_of(defects) if defects is not None else int(r.get("unplayed_grade", 3))
        if ruin:
            whole = int(row["units"])
            if whole >= int(r.get("ruin_split_units", 2)):
                lost_units = whole // 2
                q = q - lost_units * 4
                grade = int(r.get("ruin_grade", 4))
                out["lost"] = (f"Missed by {-margin}: the knife went through it and "
                               f"{lw.units_word(lost_units * 4)} of it is ruined.")
            else:
                q = 0
                out["lost"] = f"Missed by {-margin}: the {row['name'].lower()} is ruined."
        else:
            grade = graded(grade, margin)
            if margin < 0:
                out["lost"] = (f"Missed by {-margin}: it comes off torn, a grade worse than "
                               f"the knife work.")
            if margin >= 0 and _yield_roll(actor, dice):
                q = int(q + math.floor(q * float(r.get("yield_bonus", 0.5))))
                out["yielded"] = True
        if q > 0:
            # Salt costs salt (owner answer 8): one measure per hide unit, as much of the
            # hide as the pack's salt covers; the rest stays green on its 48-hour clock.
            per = _salt_per_unit()
            have = salt_measures(actor)
            want = int(math.ceil(q / 4 * per))
            # In quarters: what the carried measures cover, never more than the hide.
            covers = q if have >= want else max(0, min(q, int(math.floor(have / per * 4))))
            spend = int(math.ceil(covers / 4 * per)) if covers else 0
            if spend:
                from . import herbprep

                herbprep.spend_salt(actor, spend)
            out["salt_spent"] = spend
            form = "scrap" if grade == 0 else row["form"] or "green"
            creature_id = template_of(creature) if row["generic"] else ""
            out["stock"] = _land_hide(actor, row["material"], quarters=q, grade=grade, now=now,
                                      creature=creature_id,
                                      tier=row["tier"] if row["generic"] else "",
                                      salt_q=0 if form == "scrap" else covers, form=form)
            out["grade"] = grade
            if row["game"] and not ruin:
                out["game"] = {"material": row["material"], "margin": margin,
                               "stock": [s["key"] for s in out["stock"]]}
    else:
        if ruin:
            out["lost"] = f"Missed by {-margin}: the {row['name'].lower()} is ruined."
        else:
            if row["craft"] == HERBALIST:
                # An animal part's 48-hour clock starts, and salt it through the one reader
                # (`herbprep.preserve_on_pick`, inside `carry`) at what salting costs.
                before = salt_measures(actor)
                actor.carry(row["material"], 1, at_minute=int(now))
                out["salt_spent"] = max(0, before - salt_measures(actor))
            else:
                actor.carry(row["material"], 1)
            out["carried"] = [{"id": row["material"], "name": row["name"], "count": 1}]
            if margin < 0:
                out["lost"] = f"Missed by {-margin}: it comes away, but not cleanly."
    out["tells"] = [_tell(who, body, row, out)]
    return out


def regrade(actor, pending: dict, defects) -> dict:
    """Give the hide a roll already landed the game's grade (plan §5.7): the landed stock
    entries are re-shelved at `graded(game grade, margin)`, a reject as scraps. Returns
    {"grade", "stock"}."""
    from . import leatherworker as lw

    grade = graded(grade_of(defects), int(pending.get("margin", 0)))
    out = []
    for key in pending.get("stock") or ():
        st = (getattr(actor, "stock", {}) or {}).get(key)
        h = lw.Hide.from_stock(st) if st is not None else None
        if h is None:
            continue
        if not actor.take_stock(key, 1):
            continue
        h = h.copy()
        h.grade = grade
        h.name = ""
        if grade == 0:
            h.form, h.salted_at = "scrap", None
        new = lw.put_hide(actor, h)
        out.append({"key": new, "name": lw.hide_name(h), "form": h.form, "units": h.units,
                    "grade": grade, "material": h.material})
    return {"grade": grade, "stock": out}


def _tell(who: str, body: str, row: dict, out: dict) -> str:
    """The tell of one part: what was taken off what, and how cleanly. The narrator is told
    this and nothing else about the harvest (law 3)."""
    part = row["name"].lower()
    if not out["stock"] and not out["carried"]:
        return f"{who} works at {_the(body)}, and the {part} is ruined in the taking."
    if row["branch"] in ("hide", "scales"):
        verb = "peels" if out["ok"] else "tears"
        units = sum(s["units"] for s in out["stock"])
        salted = " and salts it on the spot" if out["salt_spent"] else ""
        return (f"{who} {verb} the {part} off {_the(body)}, "
                f"{_units_words(units)}{',' if salted else ''}{salted}.")
    return f"{who} cuts the {part} from {_the(body)}{'' if out['ok'] else ', not cleanly'}."


def _the(name: str) -> str:
    """"the wolf", but "a grey wolf" and "Choral the Conqueror" as they are: the GM's name
    for a body may carry its own article (measured live: "off the a grey wolf")."""
    name = str(name or "").strip() or "carcass"
    low = name.lower()
    if low.startswith(("a ", "an ", "the ")) or " the " in low:
        return name
    return f"the {name}"


def _units_words(units: float) -> str:
    from . import leatherworker as lw

    return lw.units_word(lw.quarters(units))


# =============================================================================================
# Facing a dangerous body (docs/deeds-plan.md §13.3, §13.4)
# =============================================================================================

def face_danger(engine, actor, creature, kind: str, roll_total: int, *, now: int,
                dice=None) -> dict:
    """One second round: the roll against the creature's own DC; marked faced on the
    carcass either way (once per carcass per kind). Exposed only on a miss by
    `exposed_margin` or more (deeds answer 6); then poison through the one poison door, acid
    or energy through the `hazard` op's contact row. Returns {"kind", "dc", "margin",
    "exposed", "outcomes": [Outcome], "tells": [str]}."""
    block = block_of(creature)
    dc = danger_dc(block, kind)
    margin = int(roll_total) - dc
    taken = dict(getattr(creature, "harvested", None) or {})
    taken[f"danger:{kind}"] = int(now)
    creature.harvested = taken
    exposed = margin <= -int(rules().get("exposed_margin", 5))
    out = {"kind": kind, "dc": dc, "margin": margin, "exposed": exposed, "outcomes": [],
           "tells": [], "doses": 0}
    who = str(getattr(actor, "name", "") or "You")
    body = str(getattr(creature, "name", "") or "the carcass")
    if not exposed:
        # The danger's words stand alone ("a body hot to the touch", as the harvest sheet
        # shows them), so the tell never wraps them in an article of its own: lane U2 read
        # "works around the a body hot to the touch of the Karkadon" live, 2026-10-08.
        out["tells"].append(f"{who} skins {_the(body)} without harm, wary of "
                            f"{DANGER_WORDS.get(kind, kind)}.")
        return out
    if kind == "poison" and actor.has_state("trait.poison-use"):
        out["tells"].append(f"{who} slips with the venom sac, and shrugs it off: they handle "
                            f"poison for a living.")
        return out
    template = template_of(creature)
    origin = f"creature:{template}"
    if kind == "poison":
        out.update(_expose_poison(engine, actor, creature, origin, dice))
    else:
        res = engine.run(engine.validate([{
            "op": "hazard", "actor": actor.ref, "visibility": "hidden",
            "because": f"skinning {_the(body)}",
            "params": {"rule": f"contact-{kind}", "rounds": 1, "to": actor.ref}}],
            origin=origin, origin_name=body))
        out["outcomes"] = list(res.outcomes)
        out["tells"] = [o.tell for o in res.outcomes if getattr(o, "tell", "")]
    return out


def _expose_poison(engine, actor, creature, origin: str, dice) -> dict:
    """1d3 doses (Harvesting Poisons), one Fortitude save at the printed DC + 2 per dose past
    the first (CRB, Poison: "each dose ... increases the DC to resist the poison by +2"), the
    printed effect landing only on a failed save, as `_op_taste` runs a herb's. The duration
    and frequency land once: a poison's track waits on `ActiveEffect.periodic`'s executor."""
    from . import consumables

    block = block_of(creature)
    body = str(getattr(creature, "name", "") or "the carcass")
    specs = poison_specs(block)
    gate = next((s for s in specs if s.get("type") == "save_gate" and s.get("dc")), None)
    harm = [s for s in specs if s.get("type") != "save_gate"]
    r = rules()
    doses = 1
    if dice is not None:
        doses = max(1, dice.roll(str(r.get("doses", "1d3")), label="doses",
                                 visibility="hidden").total)
    dc = int(gate["dc"]) + int(r.get("dose_dc_step", 2)) * (doses - 1)
    save = str(gate.get("target") or "fort").lower()
    save = save if save in ("fort", "ref", "will") else "fort"
    because = f"venom from {_the(body)}"
    outcomes = []
    res = engine.run(engine.validate([{
        "op": "save", "actor": actor.ref, "because": because, "visibility": "hidden",
        "params": {"save": save, "dc": {"value": dc}}}], origin=origin, origin_name=body))
    outcomes += list(res.outcomes)
    made_it = any(o.op == "save" and o.verdict == "success" for o in res.outcomes)
    if not made_it and harm:
        use = consumables.plan({"name": f"{body}'s venom", "specs": harm, "count": 1},
                               how="drink", target=actor.ref, because=because)
        made = [dict(i, visibility="hidden") for i in use.intents]
        if made:
            from .intents import IntentError

            try:
                res = engine.run(engine.validate(made, origin=origin, origin_name=body))
                outcomes += list(res.outcomes)
            except IntentError:
                pass
    who = str(getattr(actor, "name", "") or "You")
    lead = (f"{who} nicks the venom sac of {_the(body)}: "
            f"{doses} dose{'s' if doses != 1 else ''}, Fortitude DC {dc}.")
    return {"outcomes": outcomes, "doses": doses, "save_dc": dc,
            "tells": [lead] + [o.tell for o in outcomes if getattr(o, "tell", "")]}


__all__ = ["DANGER_KINDS", "GENERIC", "PLANS", "SURFACES", "banned", "block_of",
           "breath", "check_terms", "contact_dice", "creature_kind", "danger_dc",
           "danger_rounds", "dangers", "dc_of", "deed_of", "derive_dangers", "died_at_of",
           "dragon_colour", "face_danger", "freshness", "generic_for", "grade_of", "graded",
           "harvestable", "inherited", "is_true_dragon", "mark_the_dead", "part_key", "parts",
           "plan_of", "poison_paragraph", "poison_specs", "refused_tags", "regrade", "rules",
           "salt_measures", "take", "tagged", "tier_of_cr", "validate_tags", "working_traits"]
