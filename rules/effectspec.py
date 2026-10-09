"""The shape of an authored effect, and the catalogue the editor builds its forms from.

One idea holds this together: **effects are grouped by the fields needed to build them,
not by what they are about.** A +2 to Climb and a +2 to Strength are the same form with a
different dropdown behind `target`; a poison and a fireball are the same form because both
need a save, a DC and dice. That is what makes a generic builder possible — pick a
category, pick a type, and the fields you are asked for are the fields that type actually
has.

The catalogue is data, and the editor renders from it. Adding an effect type is adding an
entry here; no form is written by hand, and no form can drift from what the engine reads,
because both sides read this file.

What the engine can *execute* is a separate question from what can be authored, and it is
answered honestly per type: `engine` says whether an op exists to resolve it. Authoring a
type the engine cannot run is allowed and marked, never silently accepted — an effect that
looks authored and does nothing is the failure `docs/homebrew-rules.md` §1 exists to
prevent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .biomes import BIOMES
# The herb corpus's routes, read rather than copied (alchemy lane B): a second list here would
# drift from the herb bench's, which keys its tables on them. `ingredients` imports nothing
# of this module at load, so there is no cycle.
from .ingredients import ROUTES as HERB_ROUTES
from .tables import (
    ABILITY_FULL, ARMOUR, CONDITIONS, DC_BANDS, ENERGY_DAMAGE, PHYSICAL_DAMAGE, SAVES,
    SKILLS,
)

# --- what a forged thing is made of ---------------------------------------------------------
#
# The blacksmithing revamp (docs/blacksmithing-revamp-plan.md §5.3–5.5, contract §2). Before
# these, a metal's whole character was prose: 40 of the 63 material effects were `narrative`,
# and mithral's "−3 armour check penalty, +2 max Dex, −10% spell failure, half weight, one
# category lighter for movement" was one sentence nothing could execute. Each is now a
# document a reader can apply and a validator can count.
#
# `gear_mod` changes the item's *own* numbers, which are on no character sheet. The amount is
# **added to the number as `tables.ARMOUR` stores it**, and that one convention decides every
# sign: the table keeps armour check penalty negative (a chain shirt is -2) and spell failure
# as a positive percentage, so mithral's lighter penalty is acp **+3** and noqual's heavier
# spell failure is asf +20. The alternative — "the size of the change, sign meaning better or
# worse" — reads naturally for one target and backwards for the next, and plan §5.4 already
# wrote mithral's acp as -3 and adamantine's as -2 meaning opposite things. `better` records
# which way helps, so "is this the drawback?" is a lookup (`is_drawback`), not a guess.
GEAR_TARGETS: dict[str, dict] = {
    "acp": {"name": "Armour check penalty", "better": +1},
    "max_dex": {"name": "Maximum Dexterity bonus", "better": +1},
    "asf": {"name": "Arcane spell failure", "better": -1},
    "weight_pct": {"name": "Weight (percent)", "better": -1},
    "hardness": {"name": "Hardness", "better": +1},
    "hp_per_inch": {"name": "Hit points per inch", "better": +1},
    # Armour weight class *for movement only*, as mithral's rule says: a mithral breastplate
    # moves like light armour and is still medium armour for proficiency. Negative is lighter.
    "category": {"name": "Weight class for movement", "better": -1},
    # Feet of speed lost to the armour. Positive is more lost.
    "speed_penalty": {"name": "Speed penalty (feet)", "better": -1},
    # A weapon's range increment, as a percentage change: the distance property "doubles
    # the range increment" (CRB, distance), which is +100 here. A percentage rather than
    # feet because the property is the same on a sling and on a longbow.
    "range_pct": {"name": "Range increment (percent)", "better": +1},
    # A thrown range increment in feet, for a melee weapon that has none: the throwing
    # property gives "a range increment of 10 feet" (CRB, throwing). Added to the weapon
    # table's own range, which is 0 for a weapon that cannot be thrown.
    "throw_range_ft": {"name": "Thrown range increment (feet)", "better": +1},
}

# What a weapon counts as against damage reduction and hardness. A list, and meant to grow:
# `Reduction.bypassed_by` has existed on the sheet since stage 2 and nothing ever passed it a
# trait, because there was no way to say a blade *was* cold iron.
#
# `ghost_touch` (lane H, 2026-10-04) is the book's own clause, not a material: "An
# incorporeal creature's 50% reduction in damage from corporeal sources does not apply to
# attacks made against it with ghost touch weapons" (CRB, ghost touch). Ghost salt
# blanching gives it as a finish; until it was here lane C's data had to stand in a +2
# against undead for it, which is a different creature and a different rule.
#
# The enchanting revamp (docs/enchanting-contracts.md §2.1) adds what a magic weapon counts
# as: `magic` (DR/magic, "any weapon with at least a +1 magical enhancement bonus", Bestiary
# universal rules) and the four alignments a holy, unholy, axiomatic or anarchic weapon
# carries, or any weapon at +5 (CRB glossary, damage reduction).
#
# The alignments are spelled `lawful` and `chaotic`, not the `law` and `chaos` the contract
# first wrote, because these are compared as words against the stat block's own bypass
# (`Reduction.bypassed_by`), and the bestiary prints "DR 10/chaotic" (10 blocks) and
# "DR 5/lawful" (4), with "cold iron or lawful" on three more; never "chaos" or "law".
# A trait spelled `chaos` would have bounced an axiomatic blade off every one of them.
STRIKES_AS: list[str] = ["cold_iron", "silver", "adamantine", "ghost_touch",
                         "magic", "good", "evil", "lawful", "chaotic"]

# What a weapon's enhancement bonus alone lets it count as against damage reduction (CRB
# glossary, damage reduction: "Weapons with an enhancement bonus of +3 or greater can ignore
# some types of damage reduction, regardless of their actual material or alignment"; +1 is
# DR/magic, Bestiary). Read by the magic layer (lane B), which emits these as `strikes_as`
# traits so the existing DR door does the work. Adamantine at +4 is for damage reduction
# only: an enhancement bonus never ignores hardness.
#
# The alignment row is all four at once, which is what the glossary says ("+5: alignment-
# based DR"); a weapon cannot meet DR/good and miss DR/evil at the same plus.
ENHANCEMENT_STRIKES_AS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (1, ("magic",)),
    (3, ("cold_iron", "silver")),
    (4, ("adamantine",)),
    (5, ("good", "evil", "lawful", "chaotic")),
)


def strikes_as_for_enhancement(enhancement: int) -> tuple[str, ...]:
    """The DR traits a weapon of this enhancement bonus carries, by the glossary's rule.

    Bane's +2 against its foe counts here (owner, 2026-10-05, Q8), so the caller passes the
    enhancement *as raised* for the creature struck (`enhancement_raise`), never the
    printed one alone.
    """
    out: list[str] = []
    for at_least, traits in ENHANCEMENT_STRIKES_AS:
        if int(enhancement or 0) >= at_least:
            out.extend(traits)
    return tuple(out)

# How a material behaves while it is being worked. Read by the bench only; none of them
# reaches the finished item (plan §5.5). The first four are Pathfinder Unchained's, the rest
# grounded in the prior-art sweep. `brittle` and `hot_short` are flaws a bad step leaves
# behind, and they are traits because the bench reads them the same way.
WORKING_TRAITS: list[str] = [
    "easily_worked", "flawless", "malleable", "pure", "slaggy", "sulfurous", "clean_heat",
    "quench_sensitive", "narrow_window", "forgiving", "reactive", "cleans_slag", "weld_aid",
    "brittle", "hot_short",
    # The enchanting bench's own (enchanting plan §7.3, added for lane D): ghost residue
    # binds only at night, a flaming essence is eager to take, a shadow essence skittish in
    # its seat, a heavy one fades fast, a volatile one bites whoever reads it. `pure` is the
    # forge's, and means the same at the circle: the check rolled twice, the better kept.
    "night_only", "eager", "skittish", "heavy", "volatile",
    # The alchemist's bench (alchemy plan §5.5, contracts §2.4), appended below; see
    # ALCHEMY_WORKING_TRAITS for what each one means at the bench.
]

# --- the alchemist's words (alchemy lane B: contracts §2, plan §5.3, §5.5, §16) --------------
#
# Measured before any of it (alchemy plan §5.1, inv §3): 75 of the 139 alchemist materials
# carried nothing executable, 5 were narrative only, none carried three properties, and
# there was no way to say how a reagent behaves at the bench, which essence a trait
# carries, or which route it reaches a body by. A formula could only key on material
# names. These are the words the materials pass (lane D), the formulae (lane E), the
# bench (lane F) and the engine readers (lane C) share.
#
# **Working traits** (plan §5.5). `volatile` and `pure` were already here (the enchanting
# circle's) and mean the same at the alchemist's bench — something that bites when worked,
# and a check rolled twice — so they are reused, not respelled. The vessel traits decide a
# product's family (owner, Q7.3) and never touch its numbers. `solvent:<kind>` is a
# parametrised trait (Dissolve needs one, and some solids dissolve in one kind only); the
# five kinds are listed whole so the dropdown and the validator offer exactly them.
SOLVENT_KINDS: tuple[str, ...] = ("water", "alcohol", "vinegar", "oil", "acid")
VESSEL_TRAITS: tuple[str, ...] = ("drinkable", "shatters", "bursts", "struck", "stick",
                                  "fireproof", "warded", "lead_lined")
ALCHEMY_WORKING_TRAITS: tuple[str, ...] = (
    "volatile", "pure",
    "stabilizer", "catalyst", "apparatus", "solid", "liquid", "combustible",
    "slow_to_dissolve", "light_sensitive", "corrosive", "toxic_to_handle", "wild",
) + VESSEL_TRAITS + tuple(f"solvent:{k}" for k in SOLVENT_KINDS)
WORKING_TRAITS.extend(t for t in ALCHEMY_WORKING_TRAITS if t not in WORKING_TRAITS)

# **Essences** (plan §5.3; the owner kept the 18, open point 1, 2026-10-06): the tags a
# formula keys on, one per product trait, asked by prefix as `essence.<id>` (law 1). Noita's
# tag-keyed reactions and the Witcher's substances, where any carrier serves (prior art
# §3, §4). Small on purpose, after the Angry GM's advice to keep descriptors few.
#
# The vocabulary lives HERE, beside STRIKES_AS and WORKING_TRAITS, not in lane E's
# content/rules/alchemy-essences.json as contracts §2.1 first wrote: the materials pass
# validates against it before that file exists, and two lists of the same ids is how they
# come to disagree. Lane E's file holds the derivation table (a spell's essences from its
# descriptors, effect types and school) keyed on these ids, and refuses one not here.
ESSENCES: dict[str, str] = {
    "fire": "fire", "frost": "cold", "acid": "acid", "storm": "electricity",
    "thunder": "sonic",
    "light": "illumination", "shadow": "darkness, concealment and invisibility",
    "vigour": "healing, temporary hit points, fast healing",
    "purity": "removing or holding off conditions, poison and disease",
    "ward": "resistance, damage reduction, saves and armour class",
    "might": "Strength and Constitution, attack and damage",
    "grace": "Dexterity and land speed",
    "mind": "Intelligence, Wisdom, Charisma and emotion",
    "lightness": "flight, climbing, jumping and falling softly",
    "sight": "senses and divination",
    "binding": "entangling, gluing, holding and compulsion",
    "decay": "poison, necromancy and sickness",
    "change": "transmutation of form, size and substance",
}

# **Routes** (plan §5.3): how a trait reaches whoever it reaches. The herb corpus's six,
# plus the alchemist's own:
#   struck   what a thrown flask does to the creature it hits
#   splash   what it does to everyone within 5 ft of where it lands — the struck creature
#            excepted on a hit (CRB, splash weapons). The owner's ruling of 2026-10-06
#            (open point 3): ALL thrown flasks splash, not only the book's named splash
#            weapons, so splash is a property any flask can carry. A flask that authors no
#            splash document gets the book's (`splash_for`).
#   area     what a cloud does to everyone inside it
#   carried  a cost that lands on whoever carries the product
# The engine reader for the four is lane C's throw and cloud path (contracts §7).
ALCHEMY_ROUTES: tuple[str, ...] = ("struck", "splash", "area", "carried")
ROUTES: tuple[str, ...] = tuple(HERB_ROUTES) + ALCHEMY_ROUTES

# **Permissions as tag grants** (plan §16.9, contracts §2.2). A `permission` effect's
# `target` stays the words a card prints — 295 shipped documents write it as a
# sentence ("Breathe water freely.") — and its `tag` names one of these. Closed, as
# STRIKES_AS is: a tag spelled any other way would be granted and asked by nobody.
#
# Each entry says the tag it grants and the reader that asks it, or "" when none does yet:
# a tag nothing reads is honest, prose that pretends is not (plan §16.9), and the report
# lists every empty reader. Where a reader already asks a tag of its own, the permission
# grants THAT tag: water breathing grants `breathes.water`, which `water.breathes_water`
# has asked since the drowning rules — the contract's `permission.breathe_water` would have
# been a second spelling the drowning check never sees.
PERMISSIONS: dict[str, dict] = {
    "breathe_water": {"name": "Breathes water", "tag": "breathes.water",
                      "reader": "water.breathes_water (drowning)"},
    "endure_elements": {"name": "Comfortable in heat and cold",
                        "tag": "permission.endure_elements", "reader": ""},
    "comprehend_languages": {"name": "Understands any language",
                             "tag": "permission.comprehend_languages", "reader": ""},
    "pass_without_trace": {"name": "Leaves no trail",
                           "tag": "permission.pass_without_trace", "reader": ""},
    "gaseous_form": {"name": "Gaseous form", "tag": "permission.gaseous_form",
                     "reader": ""},
    "size_larger": {"name": "One size larger", "tag": "permission.size_larger",
                    "reader": ""},
    "size_smaller": {"name": "One size smaller", "tag": "permission.size_smaller",
                     "reader": ""},
    "absorb_energy": {"name": "Absorbs energy damage", "tag": "permission.absorb_energy",
                      "reader": ""},
    "ward_mind_control": {"name": "Shielded from mind control",
                          "tag": "permission.ward_mind_control", "reader": ""},
    "ward_summoned_contact": {"name": "Shielded from summoned creatures' touch",
                              "tag": "permission.ward_summoned_contact", "reader": ""},
}


def essence_tag(essence: str) -> str:
    """`essence.fire` — the one writer of an essence's tag text (law 1)."""
    return f"essence.{str(essence).strip().lower()}"


def working_tag(trait: str) -> str:
    """`working.volatile`, `working.solvent.water` — the one writer of a working trait's
    tag (plan §17: working traits are `working.*`). The colon of a parametrised trait
    becomes a dot, so `has_state("working.solvent")` asks for any solvent."""
    return "working." + str(trait).strip().lower().replace(":", ".")


def sense_tag(sense: str, range_ft=None) -> str:
    """`sense.darkvision.60`, `sense.low-light` — the tag a `sense` effect grants.

    Spelled as a race document spells it (`rules/races.py`: `sense.low-light`,
    `sense.darkvision.60`), so one prefix question answers for a race's eyes and a
    potion's alike. Measured on build/alchemy: the worn reader (`Actor._worn_tags`) writes
    `sense.<target>` with only spaces hyphenated, so goggles of `low_light` grant
    `sense.low_light` and `has_state("sense.low-light")` misses them. This is the one
    writer the readers should ask for the text.
    """
    leaf = str(sense or "").strip().lower().replace("_", "-").replace(" ", "-")
    tag = f"sense.{leaf}"
    try:
        n = int(range_ft) if range_ft not in (None, "") else 0
    except (TypeError, ValueError):
        n = 0
    return f"{tag}.{n}" if n > 0 else tag


def permission_tag(permission: str) -> str:
    """The tag a permission grants (`PERMISSIONS`), or "" for an id that is not one."""
    row = PERMISSIONS.get(str(permission or "").strip().lower())
    return row["tag"] if row else ""


def bonus_source(spec: dict, default: str = "") -> str:
    """Who a bonus comes from, as the stacking funnel reads it (`Modifier.source`).

    1e: "Bonuses without a type always stack, unless they are from the same source", and
    two bonuses of one type do not stack "even if they come from different spells"
    (CRB, Magic, Combining Magic Effects). The owner's `magic_stacking` switch (open point
    2, 2026-10-06) lifts the second half for every typed bonus and keeps the first: the
    same source keeps the better. So `source` names the effect's OWN identity — the
    spell, the product, the property — never the jar it came in: two antitoxins are one
    source (+5, not +10) and antitoxin beside another alchemical +2 are two (+7, switch
    on).

    `source` wins (a bound property's `property:<id>`, a curse's, a product's); then the
    crafting pipeline's `from`, which `consumables` has always passed as the buff's
    source; then `default`.
    """
    for key in ("source", "from"):
        v = str((spec or {}).get(key) or "").strip()
        if v:
            return v
    return default


def splash_for(specs: list[dict]) -> list[dict]:
    """A thrown flask's splash: its own `route: splash` documents, or the book's.

    The book gives every splash weapon one point of its own energy on everyone within 5 ft
    (alchemist's fire 1 fire, acid 1 acid, holy water 1 — CRB, Goods and Services), and the
    owner's ruling makes every thrown flask one. So a flask that authored no splash gets
    one point of each damage type its struck documents deal; a flask that deals no damage
    when it strikes (a tanglefoot bag) splashes nothing.
    """
    own = [dict(s) for s in specs or () if str(s.get("route") or "") == "splash"]
    if own:
        return own
    seen: list[str] = []
    for s in specs or ():
        if s.get("type") == "damage" and str(s.get("route") or "") == "struck":
            kind = str(s.get("damage_type") or "untyped")
            if kind not in seen:
                seen.append(kind)
    return [{"type": "damage", "dice": "1", "damage_type": k, "route": "splash"}
            for k in seen]

# Triggers that belong to an *item* rather than to a spell's lifetime: a blade's venom on
# the hit, viridium's leprosy on the crit, wyvern blood on the first wound each day,
# abysium sickening whoever carries it. The item is their window, which is why they are
# excused the duration a spell's `each_round` needs — and why the engine's ward path
# (`Engine._executes`, which treats any non-`on_cast` trigger as a ward) must not be the
# thing that runs them. Lane B's riders do (contract §5).
#
# `wielded` and `worn` (enchanting contracts §2.1) are `carried`'s mechanism for a held or
# worn item: a standing `ActiveEffect` granted while the item is in the hand or the slot
# and removed with it, so its contribution evaporates when the item comes off (law 2). A
# ring's fast healing, a helm's darkvision, the holy blade's negative level on the wrong
# wielder. Not `carried`, because a sword in a pack heals nobody.
ITEM_TRIGGERS: tuple[str, ...] = ("hit", "crit", "first_wound_daily", "carried",
                                  "wielded", "worn")

# Carrying a thing can sicken you, poison you or eat at a score — not swing a sword or
# grant a sense. The contract names these three and the validator holds to them.
CARRIED_TYPES: tuple[str, ...] = ("apply_condition", "save_gate", "ability_damage")

# What holding or wearing a thing can grant as a standing effect: the burden's three, and
# the four a worn magic item has that no other door carries (enchanting plan §8.4) — fast
# healing ticking from the ring, a sense from the helm, a continuous spell from the boots,
# an immunity the applicator refuses conditions by, and the negative level a holy blade
# gives the wrong hand. A plain modifier (+2 deflection) needs no trigger: it is a standing
# spec on the worn item and `_standing_mods` already reads those.
WORN_TYPES: tuple[str, ...] = CARRIED_TYPES + (
    "fast_healing", "sense", "spell_effect", "immunity", "negative_level")

# A standing property of the item has no moment to fire in. "Strikes as silver on a crit"
# and "-2 armour check penalty every round" are not rules; refused rather than ignored.
# The magic item types below join them: keen does not "fire", it is how the blade is.
_STANDING_TYPES = ("gear_mod", "strikes_as", "working",
                   "crit_range", "extra_attack", "enhancement_raise", "enhancement_to_ac",
                   "fortification", "ignore_armour", "deflect_ranged", "weapon_lethality")

# Booleans an effect may carry with no field on the form (the form has no checkbox, and a
# "yes" typed into a text box would put two spellings of one fact into the data for every
# reader to handle — `book`'s reason, given where it was first added below).
#   book            a printed PF1e number: applied as printed, never scaled
#   house           a house top-up: scaled by binding quality (enchanting plan §6.7)
#   per_multiplier  a crit rider's dice step with the weapon's multiplier: 1d10 at x2,
#                   2d10 at x3, 3d10 at x4 (CRB, flaming burst) — count x (multiplier - 1)
#   stacks          bleed that adds on each hit, as wounding's does ("multiple hits from a
#                   wounding weapon increase the bleed damage", CRB) where 1e bleed
#                   ordinarily does not stack
#   suppressible    merciful's "on command, the weapon suppresses this ability"
#   dc_adds_enhancement  arrow deflection's DC 20 "+ the enhancement bonus of the weapon"
#   drawback        a cost to whoever uses the product (alchemy contracts §2.1).
#                   `is_drawback` decides direction for a signed number; an alchemy trait
#                   says it outright, because "1d6 fire, struck" and "1d6 fire to the
#                   handler" are the same document and only the route and this flag
#                   tell them apart (`knowledge` classifies by both)
_BOOLEAN_KEYS: tuple[str, ...] = ("book", "house", "per_multiplier", "stacks",
                                  "suppressible", "dc_adds_enhancement", "drawback")

# The thirteen creature types of 1e (bane's table, CRB), and the things that are not
# creatures but can be struck — `object`, for brilliant energy's "cannot harm undead,
# constructs, and objects". Spelled as `states.type_tags` writes the type leaf.
CREATURE_TYPES: tuple[str, ...] = (
    "aberration", "animal", "construct", "dragon", "fey", "humanoid", "magical-beast",
    "monstrous-humanoid", "ooze", "outsider", "plant", "undead", "vermin")
_STRIKE_TARGETS = CREATURE_TYPES + ("object",)

# Bane's two types that name a subtype: "Humanoids (pick one subtype)", "Outsiders (pick
# one subtype)" (CRB, bane). The subtype is the world's own and is not listed here (the
# world owns its races: a goblinoid in one world is a goblin in the next).
SUBTYPE_REQUIRED: tuple[str, ...] = ("humanoid", "outsider")


# --- the vocabularies a dropdown can be filled from ---------------------------------------
#
# Named rather than inlined so two types that pick from the same list cannot drift apart,
# and so the editor fetches one catalogue instead of a form per type.

VOCAB: dict[str, list[dict]] = {
    "ability": [{"id": k, "name": v} for k, v in ABILITY_FULL.items()],
    # `all` first (alchemy lane C3, 2026-10-06): `Actor.skill_modifiers` has always read a
    # `skill_mod` aimed at `sheet.ALL_SKILLS`, and this list refused it — so lane D wrote
    # heroism's "+2 morale bonus on ... skill checks" as 35 lines, one per skill, and any
    # skill added later would have been left out of it. The pickers that choose ONE skill
    # (`choice` of `skill`) read `SKILLS`, not this list, so `all` is never offered there.
    "skill": [{"id": "all", "name": "All skills"}]
             + [{"id": k, "name": k.title()} for k in sorted(SKILLS)],
    "save": [{"id": k, "name": v} for k, v in SAVES.items()],
    "condition": [{"id": k, "name": v.get("name", k.title())}
                  for k, v in sorted(CONDITIONS.items())]
                 # Conditions the engine applies that the book's Appendix 2 does not print,
                 # so they carry tags (rules/states.py) and no CONDITIONS row: the
                 # tanglefoot bag's glued. Missing here, the tanglefoot formula was refused
                 # as "'glued' is not a condition" the moment lane C's reader landed and
                 # its `awaiting` note came off (2026-10-06).
                 + [{"id": "glued", "name": "Glued"}],
    # Poison, negative and force are damage descriptors 1e uses and the corpus writes;
    # leaving them out sent Wyrmfang Venom's "1d8 poison damage" to the reject pile.
    # Subdual is deliberately absent: it is a *lethality*, not a type, and has its own
    # field — carrying it in both places is how the same fact ends up disagreeing.
    "damage_type": [{"id": d, "name": d.title()} for d in
                    tuple(PHYSICAL_DAMAGE) + tuple(ENERGY_DAMAGE)
                    + ("poison", "negative", "positive", "force", "untyped")],
    "bonus_type": [{"id": b, "name": b.title()} for b in (
        # "armour" is the plain armour bonus — what worn armour and mage armor grant,
        # and the one that does NOT stack with either. Its absence was found twice
        # independently: mage armor's +4 had to be written `untyped` (which stacks with
        # a breastplate, and must not), and Blood Bending's Coagulated Plate carries a
        # `bonus_type: "armor"` that failed validation outright. "natural armour" was
        # here from the start, which is what made the gap easy to miss — they are
        # different bonuses that stack with each other and not with themselves.
        #
        # "material" is not a printed 1e type; it is what a forged item's metal adds
        # (plan §5.2). It stacks with every other type and never with itself, which is
        # what `dice.stack` already does with any named type it is not told is
        # self-stacking — so the vocabulary entry is the whole change.
        "alchemical", "armour", "circumstance", "competence", "deflection", "dodge",
        "enhancement", "inherent", "insight", "luck", "material", "morale",
        "natural armour",
        "profane", "racial", "resistance", "sacred", "shield", "size", "untyped")],
    "combat_target": [{"id": k, "name": n} for k, n in (
        ("attack", "Attack rolls"), ("damage", "Damage rolls"), ("ac", "Armour class"),
        ("touch_ac", "Touch AC"), ("cmb", "CMB"), ("cmd", "CMD"),
        ("initiative", "Initiative"), ("caster_level", "Caster level checks"),
        ("spell_resistance", "Checks to overcome SR"),
        # Stage 8: Toughness is "+3 hit points, +1 per Hit Die beyond 3" and had no
        # target to land on — it sat in the hand-written feat table read by nothing.
        # The channel is symmetric on the sheet (`set_hp_max` subtracts it) so a
        # printed total round-trips.
        ("hp_max", "Maximum hit points"),
        # 2026-10-09, the feat sweep. The owner's sheet tagged Endurance and Combat
        # Casting "not computed" because neither roll they modify went through the
        # funnel: survival's Constitution checks were a bare `Modifier(con)` and no
        # concentration check existed at all. Foundry PF1 has the same targets for the
        # same reason (`conChecks`, `concentration` in CONFIG.PF1.buffTargets, read
        # 2026-10-09 off gitlab.com/foundryvtt_pathfinder1e module/config.mjs). One per
        # ability, read by `Actor.ability_check_modifiers`; the save DC by
        # `casting.save_dc`, asked with the spell's school for Spell Focus's scope.
        ("str_check", "Strength checks"), ("dex_check", "Dexterity checks"),
        ("con_check", "Constitution checks"), ("int_check", "Intelligence checks"),
        ("wis_check", "Wisdom checks"), ("cha_check", "Charisma checks"),
        ("concentration", "Concentration checks"),
        ("spell_dc", "Spell save DCs"))],
    "sense": [{"id": k, "name": n} for k, n in (
        ("low_light", "Low-light vision"), ("darkvision", "Darkvision"),
        ("scent", "Scent"), ("tremorsense", "Tremorsense"),
        ("see_invisible", "See invisible"), ("blindsense", "Blindsense"),
        # Blindsense was here and blindsight was not, which is a real difference in 1e:
        # blindsense locates a creature and still leaves it total concealment, blindsight
        # does not. A spell granting the better one had to be written as the weaker.
        ("blindsight", "Blindsight"),
        ("true_seeing", "True seeing"))],
    "movement": [{"id": k, "name": n} for k, n in (
        ("land", "Land speed"), ("climb", "Climb speed"), ("swim", "Swim speed"),
        ("fly", "Fly speed"), ("burrow", "Burrow speed"))],
    "duration_unit": [{"id": k, "name": n} for k, n in (
        ("round", "rounds"), ("minute", "minutes"), ("hour", "hours"),
        ("day", "days"), ("permanent", "permanent"), ("instant", "instantaneous"))],
    "lethality": [{"id": "lethal", "name": "Lethal"},
                  {"id": "nonlethal", "name": "Non-lethal"}],
    "uses": [{"id": k, "name": n} for k, n in (
        ("unlimited", "No limit"), ("per_day", "Times per day"),
        ("per_combat", "Times per combat"), ("per_hour", "Times per hour"),
        ("once", "Once ever"))],
    "dc_band": [{"id": b, "name": b.replace("_", " ").title()} for b in DC_BANDS],
    "biome": [{"id": b, "name": b.title()} for b in BIOMES],
    "armour": [{"id": k, "name": v["name"]} for k, v in ARMOUR.items()],
    # Empty on purpose, and the editor says why rather than offering a free-text box that
    # looks like it will do something.
    "spell": [],

    # --- who an effect lands on, and when ---------------------------------------------
    #
    # These two are the reason most of the additions below exist at all. Twenty readers
    # went through the corpus a spell at a time and both gaps were reported by nearly
    # every one of them, from opposite ends of the list.
    #
    # Every spec used to land on "the target", full stop — so eruptive pustules, thorn
    # body, holy aura, cape of wasps, water shield and kinetic reverberation, all of
    # which deal their dice to *whoever strikes you*, could only be written as prose.
    # Written without a recipient they are worse than prose: thorn body converted
    # mechanically once and burned the creature it was cast on, which is the caster.
    "recipient": [{"id": k, "name": n} for k, n in (
        ("target", "The target"), ("self", "The one who has it"),
        ("caster", "The caster"), ("attacker", "Whoever struck them"),
        ("ally", "An ally"), ("area", "Everything in the area"))],
    # `on_cast` is what every one of the 6,476 existing specs means, so it is the default
    # and an absent trigger keeps behaving exactly as it does today.
    #
    # `each_round` is the single largest cause of a fully-stated spell falling to prose.
    # Incendiary cloud is 6d6 fire, Reflex half, *every round*; as a plain save gate it
    # fires once at casting and never again, which understates the spell by however many
    # rounds it lasts. Acid fog, wall of fire, hungry pit, black tentacles, pain strike
    # and poison are the same shape.
    "trigger": [{"id": k, "name": n} for k, n in (
        ("on_cast", "Immediately"), ("each_round", "Every round while it lasts"),
        ("when_struck", "When struck in melee"),
        ("when_grappled", "When grappled"),
        ("on_enter", "When something enters the area"),
        ("on_expiry", "When it ends"),
        # An item's own moments (`ITEM_TRIGGERS`): the forge's riders and carrier effects.
        ("hit", "When the weapon hits"), ("crit", "When the weapon crits"),
        ("first_wound_daily", "The first wound it deals each day"),
        ("carried", "While it is carried"),
        ("wielded", "While it is held in hand"), ("worn", "While it is worn"))],

    # The forge's three lists, as dropdowns. Built from the constants above so the editor
    # and the validator cannot offer different sets.
    "gear_target": [{"id": k, "name": v["name"]} for k, v in GEAR_TARGETS.items()],
    "strikes_as": [{"id": k, "name": k.replace("_", " ").capitalize()} for k in STRIKES_AS],
    "working_trait": [{"id": k, "name": k.replace("_", " ").capitalize()}
                      for k in WORKING_TRAITS],

    # What a manifested thing does to the squares it covers. Every one of these is a set
    # the `Grid` already keeps and the map already draws and routes around — which is the
    # whole reason `manifest` can be executed rather than narrated.
    "terrain": [{"id": k, "name": n} for k, n in (
        ("obscuring", "Blocks sight, not movement — fog, smoke"),
        ("blocked", "Solid: blocks sight and movement — a wall"),
        ("difficult", "Costs double to enter — grease, undergrowth"),
        ("none", "Occupies no squares — a light, a sound, an image"))],
    "manifest_shape": [{"id": k, "name": n} for k, n in (
        ("radius", "A spread from a point"), ("line", "A line"),
        ("wall", "A wall"), ("square", "A block of squares"), ("cone", "A cone"),
        ("point", "One square"))],

    # Permanency, dispel magic, counterspell, break enchantment, antimagic field: spells
    # whose target is *another spell*. There was no way to say any of it.
    "spell_operation": [{"id": k, "name": n} for k, n in (
        ("make_permanent", "Make it permanent"), ("dispel", "End it"),
        ("suppress", "Hold it off while this lasts"), ("extend", "Make it last longer"),
        ("counter", "Counter it as it is cast"),
        ("absorb", "Absorb it and hold the energy"))],

    # 1e's attitude track, in the book's own order. Diplomacy moves a creature along it
    # and charm, calm emotions and the whole enchantment family set it outright.
    "attitude": [{"id": k, "name": k.title()} for k in (
        "hostile", "unfriendly", "indifferent", "friendly", "helpful", "devoted")],

    "side": [{"id": k, "name": n} for k, n in (
        ("caster", "The caster"), ("target", "The target"),
        ("nobody", "Nobody — it acts on its own"))],
    # A yes/no that is a dropdown rather than a checkbox, because the generated form
    # renders `choice` and has no widget for a boolean. Two entries beat a text box that
    # accepts "true", "y", "Yes" and "1" and means something different for each.
    "yes_no": [{"id": "no", "name": "No"}, {"id": "yes", "name": "Yes"}],

    # --- a magic weapon's and armour's own powers (enchanting contracts §2.1) ----------
    #
    # One entry each today, and lists rather than constants so the form offers exactly
    # what the validator takes. Speed's extra attack comes on a full attack and nowhere
    # else (CRB, speed: "when making a full-attack action").
    "attack_kind": [{"id": "full_attack", "name": "A full attack"}],
    # Defending moves "some or all of the weapon's enhancement bonus" (CRB) to AC, so the
    # most it can move is the weapon's own enhancement, read from the item when it is used.
    "ac_transfer_max": [{"id": "enhancement", "name": "The weapon's enhancement bonus"}],
    "per": [{"id": "round", "name": "Once a round"}],
    "creature_or_object": [{"id": k, "name": k.replace("-", " ").title()}
                           for k in _STRIKE_TARGETS],

    # --- the alchemist's (alchemy lane B) ----------------------------------------------
    "essence": [{"id": k, "name": f"{k.title()}: {v}"} for k, v in ESSENCES.items()],
    "route": [{"id": k, "name": n} for k, n in (
        ("ingest", "Swallowed"), ("skin", "On the skin"), ("eyes", "In the eyes"),
        ("wound", "Into a wound"), ("inhale", "Breathed in"),
        ("external", "Outside the body"),
        ("struck", "On whoever a thrown flask hits"),
        ("splash", "On everyone within 5 ft of where it lands"),
        ("area", "On everyone in the cloud"),
        ("carried", "On whoever carries it"))],
    "permission": [{"id": k, "name": v["name"]} for k, v in PERMISSIONS.items()],
}
# The route dropdown's ids are the herb corpus's plus the alchemist's, in that order; a
# route added to `ingredients.ROUTES` without a name here fails tests/test_alchemy_vocabulary.


@dataclass
class Field:
    """One input on the generated form."""
    id: str
    label: str
    kind: str                       # int | signed | signed_formula | dice | choice
                                    #  | text | duration | effects | bool | formula
    vocab: str = ""                 # which VOCAB list fills the dropdown
    required: bool = True
    default: object = None
    hint: str = ""

    def as_dict(self) -> dict:
        d = {"id": self.id, "label": self.label, "kind": self.kind,
             "required": self.required, "hint": self.hint}
        if self.vocab:
            d["vocab"] = self.vocab
        if self.default is not None:
            d["default"] = self.default
        return d


# Every type may carry these. Pulled out because 55 of the corpus's effects state a
# duration and repeating it on twenty type definitions is how two of them end up differing.
#
# `recipient` and `trigger` joined this list rather than becoming fields on a handful of
# types, and that is the same decision the module header argues for everything else:
# *who* an effect lands on and *when* it fires are questions every type has an answer to,
# and putting them on five types would mean the sixth silently cannot ask.
#
# Both default to what an absent value has always meant — the target, immediately — so
# every one of the 6,476 specs already in the corpus keeps its exact behaviour.
COMMON = [
    Field("recipient", "Lands on", "choice", vocab="recipient", required=False,
          default="target",
          hint="Whose sheet it touches. 'Whoever struck them' is how thorn body, holy "
               "aura and cape of wasps punish an attacker rather than their own bearer."),
    Field("trigger", "Fires", "choice", vocab="trigger", required=False,
          default="on_cast",
          hint="'Every round while it lasts' is incendiary cloud's 6d6 — one hit "
               "understates it by however many rounds the cloud stands."),
    Field("duration", "Lasts", "duration", required=False,
          hint="Leave empty for instantaneous."),
    Field("uses", "Use limit", "choice", vocab="uses", required=False,
          default="unlimited"),
    Field("uses_count", "How many", "int", required=False,
          hint="With a use limit: how many times."),
    Field("note", "Note", "text", required=False,
          hint="Anything the fields above cannot hold."),
    # The alchemist's three (contracts §2.1). Optional everywhere, so all 6,476 existing
    # specs are untouched; the materials pass (lane D) requires `essence` and `route` on a
    # product trait (`product_trait_problems`). `drawback` is a boolean and so, like
    # `book`, has no field on the form (`_BOOLEAN_KEYS`); `when` and `source` are checked
    # by `validate` (`_when_shape_problems`, `bonus_source`) and have no widget either.
    Field("essence", "Essence", "choice", vocab="essence", required=False,
          hint="What an alchemy formula reads this trait as. Product traits only."),
    Field("grade", "Grade", "int", required=False,
          hint="How strong this trait is in a bottle, 1 and up. Same-named traits add "
               "their grades at the bench."),
    Field("route", "Reaches by", "choice", vocab="route", required=False,
          hint="Empty means swallowed. Struck, splash and area are a thrown flask's or a "
               "cloud's; carried lands on whoever holds it."),
]


@dataclass
class EffectType:
    id: str
    name: str
    example: str
    fields: list[Field] = field(default_factory=list)
    # Whether the engine has an op that resolves this today.
    engine: bool = True
    blocked: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "example": self.example,
            "engine": self.engine, "blocked": self.blocked,
            "fields": [f.as_dict() for f in self.fields + COMMON],
        }


@dataclass
class Category:
    id: str
    name: str
    blurb: str
    types: list[EffectType]

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "blurb": self.blurb,
                "types": [t.as_dict() for t in self.types]}


def _modifier(target_field: Field) -> list[Field]:
    """A signed number, its type, and what it applies to.

    Every modifier is this form. The only thing that differs between +2 Strength and +2
    Climb is which list fills the target dropdown — which is the whole reason the taxonomy
    is grouped this way.
    """
    return [
        # A formula as well as a number, and that one change recovers a family the
        # readers hit constantly: divine favor's "+1 luck per three caster levels,
        # maximum +3", divine power, lay of the land, ward the faithful, wrath, wave
        # shield, protection from spores. `amount` was an int, so none of them could be
        # *written* — divine favor is stored as a flat +1 with the real rule in a note
        # nothing reads, which is a spell that stops scaling at caster level 3.
        #
        # `save_gate.dc` has accepted a formula since it was written; this is the same
        # shape, made general, and an integer still validates exactly as before.
        Field("amount", "Amount", "signed_formula",
              hint="+2, -4 — or a formula: caster_level, caster_level/2, "
                   "min(1 + caster_level/3, 3)."),
        Field("bonus_type", "Bonus type", "choice", vocab="bonus_type",
              default="alchemical",
              hint="1e stacks untyped bonuses and does not stack two of a kind."),
        target_field,
    ]


CATEGORIES: list[Category] = [
    Category(
        "modifier", "Modifier", "A number added to something the sheet already computes.",
        [
            EffectType("ability_mod", "Ability score", "+2 Strength for 1 hour",
                       _modifier(Field("target", "Ability", "choice", vocab="ability"))),
            EffectType("skill_mod", "Skill", "+2 Climb checks",
                       _modifier(Field("target", "Skill", "choice", vocab="skill"))),
            EffectType("save_mod", "Saving throw", "+4 Reflex saves for nine hours",
                       _modifier(Field("target", "Save", "choice", vocab="save"))),
            EffectType("combat_mod", "Attack, damage or defence", "-4 attack rolls",
                       _modifier(Field("target", "Applies to", "choice",
                                       vocab="combat_target"))),
            EffectType(
                "situational_mod", "Situational check",
                "+2 Constitution checks to resist a forced march",
                _modifier(Field("target", "Against what", "text",
                                hint="Named in words: 'checks to resist disease'.")),
                engine=False,
                blocked="The engine applies modifiers to things it computes. A named "
                        "situation has to be recognised by the GM, so this is narrated "
                        "rather than rolled."),
        ]),

    Category(
        "hit_points", "Hit points", "Healing, harm, and the pools that sit beside them.",
        [
            EffectType("heal", "Heal", "Restores 1d4 hit points", [
                Field("dice", "How much", "dice", hint="1d4, 2d6+2, 10."),
                Field("lethality", "Heals which", "choice", vocab="lethality",
                      required=False, default="lethal",
                      hint="Non-lethal healing does not touch real hit points."),
            ]),
            # `per_multiplier` (a boolean, off the form: `_BOOLEAN_KEYS`) makes a crit
            # rider step with the weapon: flaming burst's 1d10 is 2d10 on a x3 weapon.
            # `recipient: "self"` is the wielder for an item's rider — vicious's 1d6 —
            # which is what "The one who has it" already meant; the contract's
            # `"wielder"` would have been a second spelling of it.
            EffectType("damage", "Damage", "1d6 fire damage", [
                Field("dice", "How much", "dice"),
                Field("damage_type", "Type", "choice", vocab="damage_type",
                      default="untyped"),
                Field("lethality", "Lethality", "choice", vocab="lethality",
                      default="lethal"),
            ]),
            EffectType("temp_hp", "Temporary hit points", "10 temporary hp for 8 hours", [
                Field("dice", "How many", "dice"),
                Field("source", "Source name", "text", required=False,
                      hint="Two sources do not stack; the name is how the sheet tells "
                           "them apart."),
            ]),
            EffectType("fast_healing", "Fast healing", "Fast healing 2 for 10 minutes", [
                Field("amount", "Per round", "int"),
            ]),
            EffectType("bleed", "Bleed", "1 point per round until stopped", [
                Field("amount", "Per round", "int"),
                Field("stopped_by", "Stopped by", "text", required=False,
                      default="DC 15 Heal check"),
            ]),
            # Alchemist's fire's second round (alchemy plan §16.6): "On the round
            # following a direct hit, the target takes an additional 1d6 points of
            # damage ... a full-round action to attempt to extinguish the flames ...
            # DC 15 Reflex save. Rolling on the ground provides the target a +2 bonus"
            # (CRB, Goods and Services). Bleed's sibling, and PF2e's persistent damage is
            # the shape (prior art §2.1) with the book's numbers: the state rides on the
            # creature, not on a spell's lifetime, so `trigger: each_round` (a caster's
            # ward) is the wrong door — it cannot be put out. The save is written as
            # arrow deflection's is (`save`, `dc`), flat fields the form can render, not
            # the contract's nested `{type, dc}`.
            EffectType("burning", "Burning", "Burns for 1d6 fire next round unless put out", [
                Field("dice", "Each round", "dice", hint="1d6 for alchemist's fire."),
                Field("damage_type", "Damage type", "choice", vocab="damage_type",
                      default="fire"),
                Field("rounds", "Rounds", "int", default=1,
                      hint="How many rounds it burns after the hit. 1 for alchemist's "
                           "fire: the round following."),
                Field("save", "Put out with", "choice", vocab="save", default="ref",
                      required=False, hint="The save that puts it out, as a full-round "
                                           "action."),
                Field("dc", "DC to put out", "int", default=15, required=False),
                Field("smother_bonus", "Bonus for rolling on the ground", "int",
                      default=2, required=False),
            ], blocked="Lands as state.burning with a per-round damage the periodic "
                       "executor runs; the extinguish op puts it out on the save, and "
                       "water smothers it outright."),
            # Enervation, energy drain, the resurrection of a dead character. Thirty-one
            # spells state it and none could say it: written as an `ability_damage` it
            # damages the wrong thing, and written as a `narrative` the GM gets a
            # paragraph where they wanted a number.
            EffectType("negative_level", "Negative levels", "One negative level", [
                Field("amount", "How many", "signed_formula", default=1),
                Field("becomes_permanent", "Becomes permanent", "text", required=False,
                      hint="What the book says about it sticking: '24 hours later, "
                           "Fortitude DC 18 negates'. Empty for one that never does."),
            ], engine=False,
                blocked="Recorded, counted and shown to the GM with what it costs — −1 "
                        "on every attack, save, skill and ability check, −5 hit points, "
                        "−1 caster level, each. Not applied: a negative level moves "
                        "eight different numbers on the sheet at once and applying seven "
                        "of them would be worse than applying none."),
        ]),

    Category(
        "ability_score", "Ability score",
        "Damage to a score itself, which is not hit point damage and does not heal like it.",
        [
            EffectType("ability_damage", "Ability damage", "1d4 Constitution damage", [
                Field("target", "Ability", "choice", vocab="ability"),
                Field("dice", "How much", "dice"),
            ]),
            EffectType("ability_drain", "Ability drain",
                       "1 permanent Intelligence drain", [
                Field("target", "Ability", "choice", vocab="ability"),
                Field("dice", "How much", "dice"),
            ]),
            EffectType("ability_restore", "Restore a score",
                       "Heals 1 point of Strength damage", [
                Field("target", "Ability", "choice", vocab="ability"),
                Field("dice", "How much", "dice"),
            ]),
        ]),

    Category(
        "condition", "Condition", "A named 1e condition applied, ended or held off.",
        [
            EffectType("apply_condition", "Causes", "Sickened for 1d4 rounds", [
                Field("target", "Condition", "choice", vocab="condition"),
            ]),
            EffectType("remove_condition", "Ends", "Ends fatigue", [
                Field("target", "Condition", "choice", vocab="condition"),
            ]),
            EffectType("suppress_condition", "Holds off",
                       "Eliminates fatigue for 8 hours", [
                Field("target", "Condition", "choice", vocab="condition"),
            ]),
            # Charm person, calm emotions, the whole Diplomacy-adjacent enchantment
            # family — thirty-three spells set where a creature sits on 1e's attitude
            # track, and there was no track. Written as prose, "the target becomes
            # friendly" is a sentence; written here it is a value a later check can be
            # made against.
            EffectType("attitude", "Attitude", "The target becomes friendly", [
                Field("target", "Becomes", "choice", vocab="attitude"),
                Field("towards", "Towards", "choice", vocab="recipient",
                      required=False, default="caster"),
            ], engine=True,
                blocked=""),
        ]),

    Category(
        "defence", "Defence", "Reducing or refusing damage rather than restoring it.",
        [
            # These four say where they work, because it is not everywhere and the
            # difference is invisible from the form. On a creature they are live: they
            # load onto the Actor and `take_damage` applies them in 1e's order. Handed to
            # `consumables._spec_to_intents` they produce nothing at all — a potion of
            # fire resistance is drunk and does exactly nothing, with no error anywhere.
            #
            # Said here rather than left for somebody to discover, and the builder now
            # shows `blocked` whenever it is set rather than only when `engine` is false,
            # which is why these could not be stated before.
            EffectType("resistance", "Energy resistance", "Resist fire 10", [
                Field("target", "Against", "choice", vocab="damage_type"),
                Field("amount", "Points", "int"),
            ], blocked="Granted with a clock or without one, and applied in 1e's own "
                       "order by `take_damage`. Two resistances against one energy do "
                       "not stack — the better applies."),
            EffectType("damage_reduction", "Damage reduction", "DR 3/— for 8 hours", [
                Field("amount", "Points", "int"),
                Field("bypass", "Bypassed by", "text", required=False,
                      hint="silver, cold iron. Empty for DR/—, which nothing bypasses."),
            ], blocked="Granted with a clock or without one. Several kinds of damage "
                       "reduction do not add up: only the best applicable one applies, "
                       "and none of them touches energy damage."),
            EffectType("immunity", "Immunity", "Immune to fire for 2 hours", [
                Field("target", "To what", "text",
                      hint="fire damage, poison, gaze attacks."),
            ], blocked="Damage immunity is granted and applied, with a clock or "
                       "without. An immunity to something that is not a damage type — "
                       "paralysis, a gaze — is recorded and read by the condition ops, "
                       "which refuse a condition the creature cannot suffer."),
            # The other half of resistance, and it had no way to be said. 236 of the 782
            # printed stat blocks carry one — "vulnerable to fire" on 88, "vulnerable to
            # cold" on 68 — and without this they could only be written as narrative,
            # which means the fire giant takes ordinary damage from cold and the note
            # explaining that it should not sits beside it doing nothing.
            EffectType("vulnerability", "Vulnerability", "Vulnerable to cold", [
                Field("target", "To what", "choice", vocab="damage_type"),
            ], blocked="Granted with a clock or without one — half again as much "
                       "damage of that type, applied before resistance, as 1e says."),
            # Displacement, blur, entropic shield and blurred movement are *entirely*
            # this, and every one of them was inert: with no way to say "miss chance"
            # they had to be written as narrative, and the alternative — writing 50% as
            # an AC bonus — changes which attacks land rather than how many.
            #
            # Executable. The attack path rolls it as a percentile before damage, and
            # `invisible` carries one in the condition table, which is what finally lets
            # that condition mean something.
            EffectType("concealment", "Concealment", "50% miss chance for 5 rounds", [
                Field("miss_chance", "Miss chance %", "int", default=20,
                      hint="20 for concealment, 50 for total concealment. 1e has no "
                           "other values."),
                Field("blocks_targeting", "Cannot be targeted", "choice", vocab="yes_no",
                      required=False, default="no",
                      hint="Total concealment does; displacement explicitly does not — "
                           "enemies still target it normally and still miss half the "
                           "time."),
            ]),
            # Executable since enchanting lane C (2026-10-05): `_op_cast` rolls the
            # caster level check against a target's SR (`Engine._resists`), and a rating
            # comes from a stat block, a worn item (`Actor.worn_specs_of`) or a spell's
            # grant (`Engine._grant_sr`). It was `engine: False` with the note "no creature
            # carries a rating for it to check against, and half a check would be worse
            # than none" — both halves now exist.
            EffectType("spell_resistance", "Spell resistance", "SR 12 + caster level", [
                Field("amount", "Rating", "signed_formula",
                      hint="A number, or a formula: 12 + caster_level."),
            ]),
        ]),

    Category(
        "object", "Objects",
        "Gear rather than the creature carrying it. An object has hardness and hit "
        "points of its own and neither is on anybody's character sheet.",
        [
            # Shatter, warp wood, rusting grasp, heat metal, a disintegrate aimed at a
            # door. `rules/sheet.py` gives every `Item` a hardness and hit points and
            # `damage_all_gear` already puts damage through both, so this is the one
            # missing piece: a way for an authored effect to reach it. Naming an item is
            # optional because the spells that do this usually do not — shatter takes
            # everything crystalline in the area.
            EffectType("object_damage", "Damage to gear", "2d6 to everything carried", [
                Field("dice", "How much", "dice"),
                Field("damage_type", "Type", "choice", vocab="damage_type",
                      default="untyped",
                      hint="Energy is halved against objects before hardness — except "
                           "acid, which bites."),
                Field("item", "Which item", "text", required=False,
                      hint="By name. Empty means everything the target carries."),
            ]),
            # The item's own numbers, and the first of the forge's two types. Here rather
            # than under "Modifier" because it is not a modifier in that category's sense:
            # it has no bonus type (a heavier suit is not a "penalty" that stacks with
            # anything, it is a different suit) and it touches nobody's sheet directly —
            # the armour's numbers change, and the sheet reads the armour.
            EffectType("gear_mod", "The item's own numbers",
                       "Armour check penalty 3 lighter, +2 maximum Dexterity", [
                Field("target", "Changes", "choice", vocab="gear_target"),
                Field("amount", "By", "signed",
                      hint="Added to the number as the armour table keeps it. Armour "
                           "check penalty is negative there, so +3 is lighter and -2 "
                           "heavier; spell failure is a percentage, so -10 is better."),
            ], blocked="Read from a forged item's build while it is worn or wielded. "
                       "Drunk or cast it changes nothing, and the card says so rather "
                       "than pretending."),
            # What a weapon counts as for damage reduction and hardness. The DR on the
            # sheet has carried a `bypassed_by` since stage 2 with nothing ever passing it
            # a trait; this is the trait.
            EffectType("strikes_as", "Counts as a material", "Strikes as cold iron", [
                Field("target", "Strikes as", "choice", vocab="strikes_as"),
            ], blocked="Read from a forged weapon's build and passed to the damage path "
                       "as a trait, where damage reduction and hardness ask for it."),
        ]),

    Category(
        "forge", "At the forge",
        "How a material behaves while it is being worked. The bench reads these; none of "
        "them reaches the finished item.",
        [
            # Pathfinder Unchained's material traits plus the sweep's grounded ones
            # (`WORKING_TRAITS`). A trait rather than a number because the bench decides
            # what each one does — a wider heat band, a second roll, a step that cannot
            # ruin anything — and those sizes are still being tuned in playtest (plan §17).
            EffectType("working", "Working trait", "Works easily at the forge", [
                Field("trait", "Trait", "choice", vocab="working_trait"),
                Field("amount", "Strength", "signed", required=False,
                      hint="Only where the bench reads a size for this trait. Usually "
                           "empty."),
            ], blocked="Read by the forge bench while the material is worked. It never "
                       "reaches the finished item, so a sheet never sees it."),
        ]),

    Category(
        "capability", "Capability",
        "Something the character can now do — a sense, a speed, or a rule relaxed.",
        [
            # Both of these claimed the engine ran them and it never has. `_spec_to_intents`
            # returns nothing for either, and no check in the app asks whether an actor can
            # see in the dark — so a potion of darkvision was drunk and did nothing, with
            # no error to say why. The engine flag now matches the code.
            # A sense lands as a tag for its duration (contracts §2.2): `sense_tag`
            # spells it as a race document does, so `has_state("sense.darkvision")` asks
            # a potion's eyes and an elf's the same way. Worn senses already work (the
            # helm's, read live by `Actor._worn_tags`); a drunk one waits on its grant
            # (`AWAITING_READER`).
            EffectType("sense", "Sense", "Low-light vision for 1 hour", [
                Field("target", "Sense", "choice", vocab="sense"),
                Field("range", "Range in feet", "int", required=False),
            ], blocked="Grants the sense as a tag for its duration. Worn, it is read "
                       "while worn. See invisible is read by the attack's concealment, "
                       "darkvision and low-light vision by the light model."),
            # Executable since alchemy lane B (2026-10-06), for LAND speed: the
            # consumable branch (`consumables._spec_to_intents`, since stage 2) and the
            # funnel (`Actor.speed_feet`, `_buff_mods("speed", "land")`) both existed,
            # and only this flag sent a potion of longstrider to narration — measured
            # with the fixture PC: 30 ft before the drink and 30 after; 40 after with the
            # flag on. Climb, swim, fly and burrow have no reader in movement yet, so
            # those targets wait (`TARGETS_AWAITING_READER`) and `executable` says so per
            # spec.
            #
            # `bonus_type` is optional and absent from every shipped speed spec; the funnel
            # reads an untyped speed bonus as enhancement (1e's magical speed bonuses
            # are), so writing it is only for a bonus that is NOT enhancement. Named here
            # so the stacking switch (contracts §7) sees a type it can stack by.
            EffectType("speed", "Movement", "+20 ft land speed for 1 round", [
                Field("target", "Mode", "choice", vocab="movement", default="land"),
                Field("amount", "Feet", "signed"),
                Field("bonus_type", "Bonus type", "choice", vocab="bonus_type",
                      required=False,
                      hint="Empty is enhancement, as 1e's magical speed bonuses are: "
                           "haste and a pair of boots give +30, not +60."),
            ], blocked="Land speed changes for its duration, read by every move. A fly or "
                       "climb speed lets the body leave the ground; a swim speed is read "
                       "by the water rules. A burrow speed is recorded and shown to the "
                       "GM: nothing in movement reads it yet."),
            # `target` stays the words the card prints (295 shipped documents
            # write a sentence there); `tag` is the machine half, one of PERMISSIONS, and
            # a permission with no tag can never run — it has nothing to grant
            # (`executable` asks per spec). Contracts §2.2 wrote `target` as the tag id;
            # that would have refused every one of the 295.
            EffectType(
                "permission", "Permission", "May feint as a swift action",
                [Field("target", "What it allows", "text"),
                 Field("tag", "Tag it grants", "choice", vocab="permission", required=False,
                       hint="The rule it relaxes, as the engine names it. Empty: the "
                            "words are shown to the GM and nothing is granted.")],
                blocked="Granted as its tag for the duration, through the one applicator, "
                        "with a tell. A permission with no tag is shown to the GM and "
                        "grants nothing; a tag no rule asks yet is granted and honest "
                        "about it (PERMISSIONS names each reader)."),
        ]),

    Category(
        "spell", "Spell", "Acts as a named spell.",
        [
            EffectType(
                "spell_effect", "As a spell", "Acts as enlarge person, caster level 5",
                [
                    Field("target", "Spell", "text",
                          hint="By name — 3,040 are on the Spells bench to look up."),
                    Field("caster_level", "Caster level", "int", required=False),
                    Field("save_dc", "Save DC", "int", required=False),
                ],
                engine=False,
                blocked="The spell list is imported, but the engine has no spell system: "
                        "this is recorded and narrated, and nothing will cast it."),
        ]),

    Category(
        "gate", "Save or condition gate",
        "A fork: roll a save, and what happens depends on the result. The branches hold "
        "effects of any other kind, nested as deep as the effect needs.",
        [
            EffectType("save_gate", "Saving throw",
                       "Fortitude DC 18; on a failure 1d6 Con, on a success half", [
                # Optional, because the corpus states a bare "DC 18" in twenty places and
                # picking a save for it would be inventing a fact the source never gave.
                Field("target", "Save", "choice", vocab="save", required=False,
                      hint="Leave empty if the source only gives a DC."),
                Field("dc", "DC", "formula",
                      hint="A number, or a formula: 10 + level/2 + con_mod."),
                Field("on_failure", "If they fail", "effects", required=False),
                Field("on_success", "If they save", "effects", required=False),
            ]),
        ]),

    Category(
        "presence", "Put into the scene",
        "A thing that is now *there* — fog, a wall, a light, a summoned creature. It "
        "occupies squares, it has a lifetime, and it goes away when that runs out.",
        [
            # The user's "temp-spawning", and it is executable because the state it needs
            # already exists. `rules/grid.py` keeps `obscuring`, `blocked` and `difficult`
            # square sets; the tactical map draws them and `Grid.reachable` and
            # `line_of_sight` already route around them. A fog cloud is 20 feet of
            # obscuring squares, a wall of stone is blocked squares, grease is difficult
            # squares — nothing new had to be invented, only written to.
            #
            # `Scene.pools` is the precedent for the other half: a positioned thing with
            # a lifetime, ticked and cleared with the encounter. `Scene.manifests` is the
            # same idea with squares instead of a point.
            EffectType(
                "manifest", "Something appears",
                "A bank of fog fills a 20-foot radius for 10 minutes", [
                    Field("what", "What appears", "text",
                          hint="a bank of fog, a wall of stone, four dancing lights."),
                    Field("terrain", "Does to its squares", "choice", vocab="terrain",
                          default="obscuring"),
                    Field("shape", "Shape", "choice", vocab="manifest_shape",
                          default="radius", required=False),
                    Field("size", "Size in feet", "int", required=False,
                          hint="The radius of a spread, or the length of a line or wall."),
                    Field("on_enter", "Happens to whoever enters it", "effects",
                          required=False,
                          hint="A hazard rather than a shape: acid fog's damage, an "
                               "etheric shard's cut. Left empty for plain terrain."),
                ],
                blocked="Its squares are written onto the map and cleared when it "
                        "expires. On a scene with no grid it is recorded and narrated — "
                        "there is nowhere to put squares."),
            # A light that moves with whoever carries it — a sunrod struck, a torch lit
            # (alchemy plan §16.4). There was no light model ("the map has no light level
            # yet", reactions.py), so the sunrod became a blade coating dealing 1d4 fire.
            # The two radii are the CRB's own columns (Vision and Light, the light source
            # table: torch 20 ft / 40 ft, sunrod 30 / 60, candle n/a / 5): normal light
            # out to `radius_ft`, and "an area outside the lit radius in which the light
            # level is increased by one step" out to `raised_ft`. `raised_ft` is the
            # OUTER radius, as the table prints it, never "a further" distance added on.
            # A light laid on a square rather than carried is a `manifest`'s job.
            EffectType(
                "light", "Light", "Normal light 30 ft, raised 60 ft, for 6 hours", [
                    Field("radius_ft", "Lit radius (feet)", "int",
                          hint="Normal light out to here: 20 for a torch, 30 for a "
                               "sunrod, 0 for a candle."),
                    Field("raised_ft", "Raised one step to (feet)", "int",
                          required=False,
                          hint="The outer radius of the step-brighter ring: 40 for a "
                               "torch, 60 for a sunrod. Empty: no ring."),
                ],
                blocked="Read by the light model (Scene.light_at) wherever its carrier "
                        "stands, and so by the attack's miss chance: dim light is 20%, "
                        "darkness 50%, unless the attacker's eyes say otherwise."),
            # Routed to the same `bestiary.instantiate` the `spawn` op uses rather than
            # given a creature system of its own. That is the whole design: a summoning
            # spell and a GM saying "two thugs step out of the dark" are the same event.
            EffectType(
                "summon", "A creature arrives", "Summons one celestial dog for 5 rounds",
                [
                    Field("creature", "Which creature", "text",
                          hint="By its name on the Bestiary bench — 782 stat blocks plus "
                               "guildhand, watchman, thug and guard dog."),
                    Field("count", "How many", "int", required=False, default=1),
                    Field("side", "Fights for", "choice", vocab="side",
                          required=False, default="caster",
                          hint="Whose side it arrives on."),
                ],
                blocked="A creature the Bestiary does not carry is refused by name "
                        "rather than invented — a summon that quietly produces nothing "
                        "is worse than one that says which name it did not recognise."),
        ]),

    Category(
        "spellcraft", "Acting on magic itself",
        "Permanency, dispel magic, counterspelling, suppression: spells whose target is "
        "another spell rather than a creature.",
        [
            EffectType(
                "spell_operation", "Do something to a spell",
                "Makes the duration of the spell it follows permanent", [
                    Field("operation", "What it does", "choice", vocab="spell_operation",
                          default="dispel"),
                    Field("target", "Which magic", "text", required=False,
                          hint="A spell by name, or in words: 'the spell you just cast', "
                               "'one magical effect on the target'. Empty means the GM "
                               "picks at the table."),
                    Field("check_dc", "Caster level check DC", "formula", required=False,
                          hint="Where the book calls for one: 11 + caster_level for "
                               "dispel magic. Empty means no check is rolled."),
                    Field("everything", "Everything on them", "choice", vocab="yes_no",
                          required=False, default="no",
                          hint="Greater dispel magic ends every effect it beats, not "
                               "the one the caster names."),
                ],
                blocked="Making permanent, ending and holding off are applied to the "
                        "real lifetimes the engine keeps — a buff's rounds, a "
                        "condition's, a manifested thing's — and the caster level check "
                        "is rolled where a DC is given. Countering and absorbing are "
                        "recorded for the GM: both happen during somebody else's "
                        "casting, and the engine has no readied-action step to hang "
                        "them on."),
        ]),

    Category(
        "choice", "One of several",
        "The spell offers forms and the caster picks one. Written as separate effects "
        "they all apply at once, which is every polymorph spell turning you into all "
        "five shapes simultaneously.",
        [
            EffectType(
                "choose_one", "Choose one of these",
                "Blindness or deafness, whichever you choose", [
                    Field("options", "The options", "effects",
                          hint="One entry per form. Group a form that is several effects "
                               "at once with 'All of these together'."),
                    Field("chosen", "Chosen", "int", required=False,
                          hint="Which option applies, counting from 1. Left empty until "
                               "the caster says."),
                ],
                blocked="Exactly one option applies, and only when one has been chosen. "
                        "A cast that names none applies none and says so — applying all "
                        "of them is the failure this type exists to stop."),
            EffectType(
                "bundle", "All of these together",
                "Beast shape I, bear: +2 Strength, +2 natural armour, scent", [
                    Field("label", "Called", "text",
                          hint="The name of this form or option — 'bear', 'Small "
                               "elemental', 'restore a lost memory'."),
                    Field("effects", "What it does", "effects"),
                ]),
        ]),

    # The enchanting revamp's vocabulary (docs/enchanting-contracts.md §2.1, plan §8.1).
    # Measured on master e028885 before any of it: 14 of 81 essences and 47 of 170
    # catalogue items were narrative — keen, ghost touch, speed, vorpal, defending,
    # fortification, brilliant energy, the bursts' crits — because there was no type to
    # write a threat range, an extra attack or a fortification roll as. Each is a standing
    # property of the item (`_STANDING_TYPES`): it has no moment to fire in, it is how the
    # item is while it is held or worn. Their readers are lane C's (contracts §4), in the
    # attack path and `Actor.ac_modifiers`. Until each lands, `AWAITING_READER` (below
    # the list) marks it not executable, and what its reader must do is said in
    # `blocked`, where the builder shows it.
    Category(
        "magic_item", "A magic item's own power",
        "What a magic weapon, suit or shield does because of what is bound into it. These "
        "belong to the item and work while it is held or worn.",
        [
            # Keen. "Doubles the threat range of a weapon ... This benefit doesn't stack
            # with any other effect that expands the threat range" (CRB, keen). The
            # contract first wrote this as `not_with: "feat.improved-critical"`, a tag
            # nothing grants (Improved Critical has no feat document and keen edge is
            # prose). The book's rule is a stacking rule — doublings do not stack, the
            # best applies — so it is said as one: every threat-range doubling carries
            # the same `stacking` group and the reader applies the best of a group once,
            # 1e's typed-bonus rule (`dice.stack`) applied to a multiplier. When Improved
            # Critical and keen edge get documents they join the group and need nothing
            # else.
            EffectType("crit_range", "Threat range", "Doubles the threat range", [
                Field("multiply", "Multiply the range by", "int", default=2,
                      hint="2 for keen: 19-20 becomes 17-20."),
                Field("stacking", "Does not stack with", "text", required=False,
                      default="threat-range",
                      hint="A group name. Two effects in one group do not stack; the "
                           "best applies. Every threat-range doubling is "
                           "'threat-range'."),
            ], blocked="Read by the attack's threat test from the weapon in hand "
                       "(Engine threat check, contracts §4). Doublings of one group do not "
                       "stack: 19-20 keen with Improved Critical is 17-20, not 15-20."),
            # Speed. "When making a full-attack action, the wielder ... may make one extra
            # attack with it ... not cumulative with similar effects, such as a haste
            # spell" (CRB, speed). The same stacking group as haste's extra attack.
            EffectType("extra_attack", "Extra attack", "One extra attack on a full attack", [
                Field("on", "On", "choice", vocab="attack_kind", default="full_attack"),
                Field("count", "How many", "int", default=1),
                Field("stacking", "Does not stack with", "text", required=False,
                      default="haste",
                      hint="A group name: haste and a speed weapon are one group, and "
                           "together they give one extra attack, not two."),
            ], blocked="Read by the full-attack builder, at full base attack bonus, with "
                       "this weapon only. One extra attack per stacking group."),
            # Bane. "Against a designated foe, the weapon's enhancement bonus is +2 better
            # than its actual bonus" (CRB, bane). Written first as a `combat_mod` +2 of
            # type enhancement — and through `dice.stack` an enhancement +2 beside the
            # sword's own +1 enhancement keeps the better ONE: +2 to hit, where the book's
            # +1 bane sword is +3 (test_enchant_vocabulary measures it). It is not a bonus
            # beside the enhancement; it raises the enhancement, and that raised number is
            # also what damage reduction asks (owner, Q8: bane's +2 counts toward the
            # +3/+4/+5 DR thresholds).
            EffectType("enhancement_raise", "Raise the enhancement bonus",
                       "+2 enhancement against the chosen foe", [
                Field("amount", "Raise by", "int",
                      hint="Added to the weapon's own enhancement bonus, which then "
                           "counts for attack, damage and damage reduction."),
            ], blocked="Read where the weapon's enhancement is read: attack, damage and "
                       "the damage-reduction thresholds. Usually limited by a `when` to "
                       "the foe the property was bound against."),
            # Defending. "Transfer some or all of the weapon's enhancement bonus to his AC
            # as a bonus that stacks with all others ... chooses how to allocate ... at
            # the start of his turn" (CRB). The amount moved is a choice made each turn,
            # so it is a parameter of the attack the engine validates against `max` —
            # never a number in the document, and never a model's.
            EffectType("enhancement_to_ac", "Enhancement to AC",
                       "Move some of the weapon's enhancement bonus to AC", [
                Field("max", "At most", "choice", vocab="ac_transfer_max",
                      default="enhancement"),
            ], blocked="The wielder chooses how much each turn on the combat bar; the "
                       "engine validates it against the weapon's enhancement, takes it off "
                       "attack and damage and adds it to AC, untyped (it stacks with all "
                       "others), until their next turn."),
            # Fortification. "There is a chance that a critical hit or sneak attack is
            # negated and damage is instead rolled normally" — 25%, 50%, 75% (CRB).
            EffectType("fortification", "Fortification",
                       "25% chance to turn a critical hit or sneak attack", [
                Field("percent", "Chance %", "int", default=25,
                      hint="25 light, 50 moderate, 75 heavy."),
            ], blocked="Rolled by the engine as a d% when a critical hit is confirmed or "
                       "sneak attack dice are added against the wearer, and shown: on a "
                       "success the hit is rolled as an ordinary one."),
            # Brilliant energy. Armour and shield bonuses "do not count against" it, and
            # "a brilliant energy weapon cannot harm undead, constructs, and objects"
            # (CRB). The contract wrote the second clause as `except`, read as "the
            # armour still counts against these" — which would let it cut a skeleton.
            # The book says it does not harm them at all, so the field says that.
            EffectType("ignore_armour", "Passes through armour",
                       "Ignores armour and shield bonuses to AC", [
                Field("cannot_harm", "Cannot harm", "list", vocab="creature_or_object",
                      required=False,
                      hint="Creature types it passes through without effect: undead, "
                           "construct, object for brilliant energy."),
            ], blocked="The attack's AC drops the defender's armour and shield bonuses "
                       "(and their enhancements). Against a type in 'cannot harm' the blow "
                       "deals nothing, and the tell says why."),
            # Arrow deflection and arrow catching (CRB shield abilities). Deflection: "once
            # per round when he would normally be struck by a ranged weapon, he can make a
            # DC 20 Reflex save ... the DC increases by the enhancement bonus" of the
            # attacking weapon. Catching: "+1 deflection bonus to AC against ranged weapons
            # ... ranged weapons fired at targets within 5 feet of the shield's wearer are
            # diverted to target the shield's bearer". The contract's `auto` reading was
            # Snatch Arrows, a feat; no shield in the book catches automatically.
            EffectType("deflect_ranged", "Turns ranged attacks",
                       "Deflects one ranged attack a round on a DC 20 Reflex save", [
                Field("per", "How often", "choice", vocab="per", required=False),
                Field("save", "Save", "choice", vocab="save", required=False,
                      hint="The save that deflects it: Reflex for arrow deflection."),
                Field("dc", "DC", "int", required=False),
                Field("draws_ft", "Draws attacks from within (feet)", "int",
                      required=False,
                      hint="Arrow catching: ranged attacks at anyone this close are "
                           "diverted to the bearer."),
                Field("deflection", "Deflection bonus against ranged", "int",
                      required=False),
            ], blocked="Read by the ranged attack path against the bearer and anyone "
                       "near them. The save is rolled by the engine and shown."),
            # Merciful. "All damage it deals is nonlethal damage. On command, the weapon
            # suppresses this ability" (CRB). The weapon's own lethality, read where
            # `weapons.lethality_of` reads a sap's.
            EffectType("weapon_lethality", "Deals non-lethal damage",
                       "All its damage is non-lethal", [
                Field("lethality", "Its damage is", "choice", vocab="lethality",
                      default="nonlethal"),
            ], blocked="Read by `weapons.lethality_of` as the weapon's own lethality. "
                       "When `suppressible`, declaring a lethal blow suppresses it, and "
                       "the property's other riders with it."),
            # Vorpal ("severs the opponent's head") and disruption ("must succeed on a DC
            # 14 Will save or be destroyed"): the creature dies, through `Actor.die`, the
            # one door death is written through. `natural` is vorpal's "upon a roll of
            # natural 20 (followed by a successful roll to confirm)"; `except` the types it
            # does nothing to ("such as golems and undead creatures other than vampires",
            # "all oozes ... have no heads").
            EffectType("slay", "Slays outright", "Severs the head on a natural 20", [
                Field("natural", "Only on a natural", "int", required=False,
                      hint="20 for vorpal. Empty: whenever it fires."),
                Field("except", "Does nothing to", "list", vocab="creature_or_object",
                      required=False),
            ], blocked="The creature dies through the one door death has (`Actor.die`), "
                       "unless it is of a type it does nothing to or is immune to "
                       "critical hits. Always with a tell."),
            # A power the item's bearer uses: the blinding shield's flash, etherealness,
            # reflecting's spell turning, a ring's command word. The contract wrote its
            # uses as `{"per": "day", "n": 1}`; every effect already carries `uses` and
            # `uses_count` (COMMON, below), so a power says `"uses": "per_day",
            # "uses_count": 2`, and "at will" is `"uses": "unlimited"` — one spelling.
            # Exactly one of `spell` (a spell id, cast through the cast door at the item's
            # caster level), `effect` (one document) or `tell` (a power that changes no
            # number — glamered armour looking like clothes).
            EffectType("item_power", "A power the bearer uses",
                       "Twice a day, a blinding flash", [
                Field("spell", "Casts", "text", required=False,
                      hint="A spell's id on the Spells bench: ethereal-jaunt."),
                Field("effect", "Does", "effects", required=False,
                      hint="One effect, when it is not a spell."),
                Field("tell", "Says", "text", required=False,
                      hint="For a power that changes no number: what the narrator is "
                           "told happened."),
                Field("caster_level", "Caster level", "int", required=False,
                      hint="Empty: the item's own."),
                Field("area", "Area", "area", required=False,
                      hint="{\"shape\": \"burst\", \"ft\": 20} centred on the bearer."),
            ], blocked="Used through the `use_item` op, validated by the engine, never "
                       "written by a model with a number. Uses are counted on the item and "
                       "come back each day; the bar shows how many are left."),
        ]),

    Category(
        "narrative", "Narrative only",
        "Says what happens without claiming a number. Explicit, so that prose is never "
        "mistaken for a mechanic the engine will apply.",
        [
            EffectType("narrative", "Narrative",
                       "Stains the teeth dark crimson for a week",
                       [Field("target", "What happens", "text")],
                       engine=False,
                       blocked="Recorded and shown to the GM. Nothing is rolled."),
        ]),
]


# Types the vocabulary can say and the engine does not run yet, each with where its reader
# will live. The enchanting contract first fixed `engine: True` for every new type; this
# module's own honesty ratchet (tests/test_effectspec_extensions.py, "no type may be
# narrative wearing a costume") refuses a type that claims the engine runs it when nothing
# does — measured on the first full run, ten types claimed and none ran. So they are marked
# here, in one place: `engine` is False and the builder's warning says what waits. When lane
# C's reader for one lands, it deletes that line (and lists the type with its site in the
# ratchet's `already`), and the type is executable from then on.
#
# Emptied by enchanting lane C (2026-10-05). Where each reader landed:
#   crit_range         sheet._with_layer (the weapon row's threat range, read by the
#                      attack's threat test and the sheet's weapon line)
#   extra_attack       Actor.attack_sequence (one more swing at full BAB on a full attack)
#   enhancement_raise  sheet._raised_specs (attack and damage) and
#                      magic_layer.strikes_as_against in Engine._op_attack (DR traits)
#   enhancement_to_ac  Engine._defend_with, the attack's `defending` param
#   fortification      Engine._fortify (crit and sneak attack), Actor.fortification
#   ignore_armour      Engine._op_attack's AC, Engine._harmless_blow (cannot harm)
#   deflect_ranged     Actor.ac_modifiers (arrow catching's +1), Engine._catcher,
#                      Engine._deflect (arrow deflection's Reflex save)
#   weapon_lethality   sheet._with_layer (the row's `nonlethal`, read by
#                      weapons.lethality_of; suppressed by a declared lethal blow)
#   slay               Engine._slay (vorpal on a natural 20 crit; disruption's gate)
#   item_power         Engine._use_power, the use_item op's `power`
#
# Refilled by alchemy lane B (2026-10-06) with the alchemist's types, each waiting on alchemy
# lane C (contracts §7). Lane C deletes a line when its reader lands and lists the type in
# tests/test_effectspec_extensions.py's `already`.
#
# Emptied by alchemy lane C (2026-10-06). Where each reader landed:
#   sense       consumables._spec_to_intents -> Engine._op_grant (`sense_tag` through the
#               one applicator); read by Actor.eyes: darkvision and low-light by
#               Scene.light_at and Actor.concealment, see invisible by Actor.concealment
#   permission  consumables._spec_to_intents -> Engine._op_grant (`permission_tag`); each
#               tag's own reader is PERMISSIONS' `reader` ("" where none asks yet)
#   light       consumables._spec_to_intents -> Engine._op_grant (`light.carried` with its
#               radii); read by Scene.light_at, and so by Actor.concealment's miss chance
#   burning     Engine._op_burn (state.burning, a periodic fire counted by `times_left`
#               in Actor.run_periodic) and Engine._op_extinguish
AWAITING_READER: dict[str, str] = {}
# A type whose reader runs some targets and not others (contracts §2.2: speed "targets land,
# climb, swim, fly, jump. Lane C wires the readers"). `executable` asks per spec, so a
# potion of longstrider runs and a potion of fly is narrated with the reason named. Lane C
# deletes a target's line when movement reads it. `jump` is not here: 1e's jump is an
# Acrobatics check, not a movement mode, so a jumping bonus is a `skill_mod` on
# acrobatics with the note "to jump".
#
# Alchemy lane C (2026-10-06) gave three of the four a reader: `Actor.movement_modes` takes
# a granted climb, swim or fly speed through the funnel, and the move op's permission to
# leave the ground (`can_move_vertically`) and the water rules (`water.swim_speed`, through
# `Actor.speeds`) read it. Nothing in the app moves a body through earth, so burrow waits.
TARGETS_AWAITING_READER: dict[str, dict[str, str]] = {
    "speed": {
        "burrow": "a burrow speed read by movement (nothing moves a body through earth "
                  "yet)",
    },
}
for _cat in CATEGORIES:
    for _t in _cat.types:
        if _t.id in AWAITING_READER:
            _t.engine = False
            _t.blocked = (f"Not run yet: its reader, {AWAITING_READER[_t.id]}, is not built. "
                          f"When it lands: {_t.blocked[:1].lower()}{_t.blocked[1:]}")


def catalogue() -> dict:
    return {
        "categories": [c.as_dict() for c in CATEGORIES],
        "vocab": VOCAB,
    }


def find(type_id: str) -> tuple[Category, EffectType] | None:
    for c in CATEGORIES:
        for t in c.types:
            if t.id == type_id:
                return c, t
    return None


# --- formulas -------------------------------------------------------------------------------
#
# `amount` was an int, and that single fact put a whole family of spells out of reach:
# "an insight bonus equal to your caster level, maximum +5", "+1 per four caster levels",
# "half your caster level". Divine favor, divine power, authenticating gaze, lay of the
# land, liberating command, ward the faithful, wrath, wave shield and protection from
# spores all state their bonus as a formula and all had to be stored as a flat number with
# the real rule in a `note` that nothing reads — a spell that silently stops scaling.
#
# The variables are named rather than positional, and the list is closed: a formula naming
# something that is not in here is rejected at authoring time with the list in the message.
# That is the same rule the descriptor vocabulary follows — a guessed name is worse than a
# refusal, because it produces a number instead of an error.
FORMULA_VARS: dict[str, str] = {
    "caster_level": "The caster's caster level.",
    "level": "The character's class level. The same as caster level for a full caster.",
    "spell_level": "The level of the slot this was cast from.",
    "hit_dice": "The creature's Hit Dice.",
    "casting_mod": "The caster's casting ability modifier — Int, Wis or Cha.",
    "str_mod": "The Strength modifier.", "dex_mod": "The Dexterity modifier.",
    "con_mod": "The Constitution modifier.", "int_mod": "The Intelligence modifier.",
    "wis_mod": "The Wisdom modifier.", "cha_mod": "The Charisma modifier.",
    # A scaled magic property's bonus (`content/rules/magic-properties.json`, `scaled`):
    # the +3 a ring of protection was bound at. The book prices these by the square of it
    # (Table: Estimating Magic Item Gold Piece Values) and the effect is the number itself,
    # so the document says `"amount": "bonus"` and one entry serves +1 to +5.
    "bonus": "The bonus a scaled magic property was bound at.",
}


class BadFormula(ValueError):
    """A formula that cannot be evaluated, with the reason in the message."""


def _formula_names(expr: str) -> set[str]:
    """Every variable a formula names, or a raise. The parse *is* the validation.

    Built on `ast` rather than on a regex because a regex that recognises `min(1 +
    caster_level/3, 3)` also recognises `min(1 + caster_level/3, 3` and half a dozen other
    things that are not expressions. The whitelist below is what makes evaluating an
    authored string safe: no attribute access, no subscripts, no calls except min and max,
    and no names except the ones `FORMULA_VARS` declares.
    """
    import ast

    try:
        tree = ast.parse(str(expr), mode="eval")
    except SyntaxError as exc:
        raise BadFormula(f"{expr!r} is not an expression") from exc

    # Operators are nodes of their own in the tree — `ast.walk` yields `Add` beside the
    # `BinOp` that holds it — so they are whitelisted here rather than only inside the
    # BinOp branch. The first version checked only the BinOp and rejected `1 +
    # caster_level` on the operator it had just approved.
    allowed = (ast.Expression, ast.Load, ast.Constant, ast.Name, ast.Call, ast.BinOp,
               ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
               ast.UAdd, ast.USub)
    names: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise BadFormula(f"{type(node).__name__.lower()} is not allowed in a formula")
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ("min", "max"):
                raise BadFormula("only min() and max() may be called")
            called.add(node.func.id)
            if not node.args or node.keywords:
                raise BadFormula(f"{node.func.id}() takes numbers, in brackets")
    return names - called


def is_formula(value) -> bool:
    """Whether this is a formula this module can evaluate. Plain integers are not.

    `None` is not, and saying so takes an explicit line: `str(None)` is `"None"`, which
    parses as a perfectly valid constant expression naming no unknown variables — so the
    obvious version of this answered True for a field that was simply absent, and the
    engine then rewrote every missing `amount` as the number 0.
    """
    if value is None or isinstance(value, (int, float)) or not str(value).strip():
        return False
    try:
        names = _formula_names(value)
    except BadFormula:
        return False
    # A bare constant is a number written oddly, not a formula, and nothing is gained by
    # sending "7" through the evaluator.
    return bool(names) and names <= set(FORMULA_VARS)


def evaluate(expr, context: dict | None = None) -> int:
    """A formula as a number, for this caster.

    Division floors, because 1e floors: "+1 per three caster levels" at caster level 5 is
    +1, not +1.67 and not +2. Python's `/` on two ints would give the fraction, so both
    kinds of divide are rounded down here rather than left to whichever the author typed.

    An unknown variable evaluates to 0 rather than raising, and that is deliberate: the
    refusal belongs at authoring time, where `validate` names the whole list of variables
    in a message the author can act on, not at resolution time in the middle of a fight.
    """
    if isinstance(expr, (int, float)):
        return int(expr)
    text = str(expr).strip()
    if not text:
        return 0
    try:
        return int(text)
    except ValueError:
        pass

    import ast

    ctx = {k: int(v) for k, v in (context or {}).items() if isinstance(v, (int, float))}
    _formula_names(text)                      # raises BadFormula on anything unsafe

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant):
            return int(node.value)
        if isinstance(node, ast.Name):
            return int(ctx.get(node.id, 0))
        if isinstance(node, ast.UnaryOp):
            return -walk(node.operand) if isinstance(node.op, ast.USub) \
                else walk(node.operand)
        if isinstance(node, ast.Call):
            args = [walk(a) for a in node.args]
            return (min if node.func.id == "min" else max)(*args)
        if isinstance(node, ast.BinOp):
            a, b = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if b == 0:
                raise BadFormula("division by zero")
            return a // b
        raise BadFormula("unreadable formula")

    return int(walk(ast.parse(text, mode="eval")))


# --- dice that scale --------------------------------------------------------------------------
#
# Harm, implosion and wail of the banshee deal a flat 10 points per caster level and none
# of them could be written: `dice` had to *be* dice, so `10` was the only legal thing to
# put there and it is wrong at every caster level above 1st by a factor of the level.
#
# `rules/spells.py` already solves the scaling problem for a *spell* — one formula on the
# spell, applied by `effects_at` — and that stays the right place for a spell. This is for
# the other authors: a homebrew feat, a magic item, a creature ability, all of which carry
# effects with no spell around them to hold a `scaling` dict.
_PER_LEVEL_DICE = re.compile(
    r"^\s*(?P<count>\d*)(?:d(?P<die>\d+))?\s*(?:/|\s+per\s+)\s*(?P<every>\d*)\s*"
    r"(?:caster\s+)?levels?\s*(?:,?\s*max(?:imum)?\s*(?P<cap>\d+)\s*(?:d\d+)?)?\s*$",
    re.I)


def resolve_dice(value, caster_level: int = 1) -> str:
    """`"10/level"` at caster level 15 is `"150"`; `"1d6/2 levels"` at 7 is `"3d6"`.

    Anything that is already plain dice comes back untouched, so every existing spec goes
    through here unchanged. The floor is one die or one point — "1d8 per two caster
    levels" at 1st is the smallest the effect can be, not nothing at all, which is the
    same rule `spells.scaling_dice` applies and for the same reason.
    """
    text = str(value or "").strip()
    m = _PER_LEVEL_DICE.match(text)
    if not m:
        return text
    cl = max(1, int(caster_level))
    every = max(1, int(m.group("every") or 1))
    count = max(1, int(m.group("count") or 1))
    total = max(count, count * (cl // every))
    cap = int(m.group("cap") or 0)
    if cap:
        total = min(total, cap)
    return f"{total}d{m.group('die')}" if m.group("die") else str(total)


# --- validation ---------------------------------------------------------------------------

def validate(spec: dict, path: str = "effect", *, inherits_window: bool = False) -> list[str]:
    """Everything wrong with one authored effect, named.

    Returned as a list rather than raised, because the editor shows all of a form's
    problems at once and a builder that reports them one at a time is a builder nobody
    finishes a complex effect in.

    `inherits_window` says the parent already supplies the lifetime — a hazard inside a
    manifestation's `on_enter` burns for as long as the cloud stands, and asking it to
    restate the cloud's duration would put the same fact in two places for the two to
    then disagree about. Keyword-only and defaulted, so every existing caller is
    untouched.
    """
    problems: list[str] = []
    type_id = str(spec.get("type", "")).strip()
    found = find(type_id)
    if found is None:
        known = ", ".join(t.id for c in CATEGORIES for t in c.types)
        return [f"{path}: no effect type {type_id!r}. Known: {known}."]

    _, etype = found
    # A document that names a choice (`choice_key`, enchanting contracts §2.1) has its
    # `target` filled when the property is bound — energy resistance's "fire" is the
    # player's pick, not the author's — so an empty target is not missing here. The bound
    # document is validated in full by `property_problems`, option by option.
    chosen_later = {"target"} if _choice_key(spec) else set()
    for f in etype.fields + COMMON:
        value = spec.get(f.id)
        missing = value is None or (isinstance(value, str) and not value.strip())
        if missing:
            if f.required and f.id not in chosen_later:
                problems.append(f"{path}: {etype.name} needs {f.label.lower()}.")
            continue
        if f.kind == "list":
            allowed = {o["id"] for o in VOCAB.get(f.vocab, [])}
            if not isinstance(value, list) or not value:
                problems.append(
                    f"{path}: {f.label.lower()} is a list: [\"undead\", \"construct\"].")
            elif allowed:
                bad = [v for v in value if str(v) not in allowed]
                if bad:
                    problems.append(
                        f"{path}: {', '.join(map(repr, bad))} in {f.label.lower()} is not "
                        f"one of: {', '.join(sorted(allowed))}.")
            continue
        if f.kind == "area":
            problems.extend(_area_problems(value, f"{path}: {f.label.lower()}"))
            continue
        if f.kind == "choice" and f.vocab:
            allowed = {o["id"] for o in VOCAB.get(f.vocab, [])}
            if allowed and str(value) not in allowed:
                problems.append(
                    f"{path}: {value!r} is not a {f.label.lower()}. "
                    f"One of: {', '.join(sorted(allowed))}.")
        elif f.kind in ("int", "signed"):
            try:
                int(value)
            except (TypeError, ValueError):
                problems.append(f"{path}: {f.label.lower()} must be a number.")
        elif f.kind == "signed_formula":
            # A number *or* a formula, and the difference is checked rather than assumed:
            # an amount of "caster_lvl" is a typo for `caster_level` and would otherwise
            # sail through and evaluate to zero — a bonus of +0, which is a bug nobody
            # sees because it looks exactly like a spell that did nothing.
            try:
                int(value)
            except (TypeError, ValueError):
                head = f"{path}: {f.label.lower()} must be a number or a formula"
                try:
                    unknown = sorted(_formula_names(value) - set(FORMULA_VARS))
                except BadFormula as exc:
                    problems.append(f"{head} — {exc}.")
                else:
                    if unknown:
                        problems.append(
                            f"{head}, and {', '.join(unknown)} is not something a "
                            f"formula can use. One of: "
                            f"{', '.join(sorted(FORMULA_VARS))}.")
        elif f.kind == "dice":
            if not _is_dice(str(value)):
                problems.append(
                    f"{path}: {value!r} is not dice. Write 1d4, 2d6+2 or a number.")
        elif f.kind == "effects":
            for i, nested in enumerate(value or []):
                problems.extend(validate(
                    nested, f"{path} > {f.label.lower()} {i + 1}",
                    inherits_window=(f.id == "on_enter")))

    if spec.get("uses") not in (None, "", "unlimited") and not spec.get("uses_count"):
        problems.append(f"{path}: a use limit needs a count.")

    # A trigger that is not "immediately" needs something to keep it alive. Without a
    # duration `each_round` has no rounds and `when_struck` has no window to be struck
    # in, so the effect would be authored, accepted, and never fire once — the silent
    # failure docs/homebrew-rules.md §1 exists to prevent, arriving by a new route.
    #
    # An item's triggers are excused: the item is the window. A blade's venom fires on
    # every hit for as long as the blade exists, and asking it for a duration would make
    # the author invent one.
    trigger = str(spec.get("trigger") or "on_cast")
    if trigger not in ("on_cast", "") and trigger not in ITEM_TRIGGERS \
            and not inherits_window and not _lasts(spec.get("duration")):
        problems.append(
            f"{path}: '{_vocab_name('trigger', trigger)}' needs a duration — without one "
            f"there is no window for it to fire in and it would never happen.")
    if trigger == "carried" and type_id not in CARRIED_TYPES:
        problems.append(
            f"{path}: '{_vocab_name('trigger', trigger)}' works only on "
            f"{', '.join(CARRIED_TYPES)} — carrying a thing can sicken you or eat at a "
            f"score, and that is all. Use a different trigger or one of those types.")
    elif trigger in ("wielded", "worn") and type_id not in WORN_TYPES:
        problems.append(
            f"{path}: '{_vocab_name('trigger', trigger)}' works only on "
            f"{', '.join(WORN_TYPES)} — the standing effects an item grants while it is "
            f"held or worn. A plain modifier needs no trigger: a worn item's modifiers "
            f"are read while it is worn.")
    elif trigger not in ("on_cast", "") and type_id in _STANDING_TYPES:
        problems.append(
            f"{path}: {type_id} is a standing property of the item and has no "
            f"moment to fire in. Remove the trigger.")

    # `book` marks a printed PF1e number: applied from the main piece only, never scaled
    # (plan §6.3). A boolean and nothing else, and it has no field on the form for that
    # reason — the form has no checkbox, and a "yes" typed into a text box would put two
    # spellings of one fact into the data for every reader to handle. The enchanting
    # revamp's flags follow the same rule (`_BOOLEAN_KEYS`).
    for key in _BOOLEAN_KEYS:
        if key in spec and not isinstance(spec[key], bool):
            problems.append(
                f"{path}: {key} must be true or false, not {spec[key]!r}. Write "
                f"\"{key}\": true, or leave it out.")
    if spec.get("book") is True and spec.get("house") is True:
        problems.append(
            f"{path}: a number is the book's or a house top-up, not both. Book numbers are "
            f"never scaled; house ones are. Keep one.")
    if spec.get("per_multiplier") and not (type_id == "damage" and trigger == "crit"):
        problems.append(
            f"{path}: per_multiplier steps a critical hit's extra dice with the weapon's "
            f"multiplier, so it belongs on damage with \"trigger\": \"crit\".")
    if spec.get("stacks") and type_id != "bleed":
        problems.append(f"{path}: stacks is bleed's (wounding); remove it.")

    problems.extend(_choice_ref_problems(spec, path))
    problems.extend(_magic_item_problems(spec, type_id, path))
    problems.extend(_alchemy_problems(spec, type_id, path))
    if spec.get("when") is not None:
        problems.extend(when_problems(spec["when"], f"{path}: when"))

    if type_id == "gear_mod":
        problems.extend(_gear_problems(spec, path))

    if type_id == "choose_one":
        options = spec.get("options") or []
        if len(options) < 2:
            problems.append(
                f"{path}: a choice needs at least two options. One option is not a "
                f"choice, it is just that effect.")
        chosen = spec.get("chosen")
        if chosen not in (None, "") and not 1 <= int(chosen) <= len(options):
            problems.append(
                f"{path}: option {chosen} was chosen and there are {len(options)}.")

    if type_id == "manifest":
        if str(spec.get("terrain") or "none") != "none" and not spec.get("size"):
            problems.append(
                f"{path}: a shape that changes its squares needs a size in feet — "
                f"without one there is nothing to write onto the map.")

    return problems


def _gear_problems(spec: dict, path: str) -> list[str]:
    """The limits a gear number has that a dropdown and an int cannot say."""
    try:
        amount = int(spec.get("amount"))
    except (TypeError, ValueError):
        return []                       # already reported as "must be a number"
    target = str(spec.get("target") or "")
    if amount == 0:
        # An effect that is authored and does nothing — the failure this module's header
        # exists for, arriving as a zero.
        return [f"{path}: a gear change of 0 changes nothing. Give it a size or remove it."]
    if target == "category" and abs(amount) > 2:
        return [f"{path}: armour has three weight classes, so a shift of {amount} is "
                f"more than there are. Use -2 to +2."]
    if target == "weight_pct" and amount <= -100:
        return [f"{path}: {amount}% would weigh nothing. Mithral, the lightest metal, is "
                f"-50."]
    if target == "asf" and abs(amount) > 100:
        return [f"{path}: spell failure is a percentage; {amount} is past it. Use -100 "
                f"to +100."]
    return []


_AREA_SHAPES = ("cone", "line", "burst")


def _area_problems(area, path: str) -> list[str]:
    """An area in the shape `rules/class_abilities.py` already lays: `{"shape": "burst",
    "ft": 20}`, with `range_ft` for one laid away from the user. One shape for both, so the
    blinding shield's flash and a channel's burst go through the same `rules/areas.py`."""
    if not isinstance(area, dict) or str(area.get("shape") or "") not in _AREA_SHAPES:
        return [f"{path} is {{\"shape\": \"burst\", \"ft\": 20}} — shape one of "
                f"{', '.join(_AREA_SHAPES)}."]
    out = []
    for key in ("ft", "range_ft"):
        if key in area:
            try:
                if int(area[key]) <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                out.append(f"{path}: {key} is a number of feet above 0.")
    if "ft" not in area:
        out.append(f"{path} needs ft, its size in feet.")
    return out


def _choice_key(spec: dict) -> str:
    return str(spec.get("choice_key") or "").strip()


def _choice_refs(when) -> list[str]:
    """Every `{"choice": key}` inside a `when`'s `target` clause."""
    if not isinstance(when, dict):
        return []
    target = when.get("target")
    if isinstance(target, dict) and "choice" in target:
        return [str(target.get("choice") or "")]
    return []


def _choice_ref_problems(spec: dict, path: str) -> list[str]:
    """`choice_key` and the `when` that references it must agree.

    The note-only bane is the defect this exists for: its +2 and +2d6 sat in a `note`
    ("against the designated foe", magic-items.json `mi-bane`), so any reader would have
    applied them to every foe. Now the foe is a choice stored on the item, the document
    names it (`choice_key`), and its `when` asks for the defender to be of that kind
    (`{"target": {"choice": "foe"}}`). A `when` that names a choice the document does not
    carry would never be filled — and an unevaluable clause is dropped, which is bane
    applying to nobody.
    """
    out: list[str] = []
    key = _choice_key(spec)
    if "choice_key" in spec and not re.fullmatch(r"[a-z][a-z_]*", key):
        out.append(f"{path}: choice_key is the name of the property's choice, in lower "
                   f"case: \"foe\", \"energy\".")
    for ref in _choice_refs(spec.get("when")):
        if not key:
            out.append(f"{path}: its `when` asks for the choice {ref!r} and it carries no "
                       f"choice_key. Add \"choice_key\": {ref!r}.")
        elif ref != key:
            out.append(f"{path}: its `when` asks for the choice {ref!r} and its choice_key "
                       f"is {key!r}. They must name the same choice.")
    return out


def _magic_item_problems(spec: dict, type_id: str, path: str) -> list[str]:
    """The limits the enchanting types have that a dropdown and an int cannot say."""
    def number(key, default=None):
        try:
            return int(spec.get(key, default))
        except (TypeError, ValueError):
            return None

    out: list[str] = []
    if type_id == "crit_range":
        if (number("multiply", 2) or 0) < 2:
            out.append(f"{path}: a threat range multiplied by less than 2 is not widened. "
                       f"Keen is 2.")
    elif type_id == "extra_attack":
        if (number("count", 1) or 0) < 1:
            out.append(f"{path}: an extra attack needs a count of at least 1.")
    elif type_id == "enhancement_raise":
        if (number("amount") or 0) < 1:
            out.append(f"{path}: raising an enhancement bonus by less than 1 raises "
                       f"nothing. Bane is 2.")
    elif type_id == "fortification":
        p = number("percent", 25)
        if p is None or not 1 <= p <= 100:
            out.append(f"{path}: fortification is a percentage, 1 to 100 (the book's are "
                       f"25, 50 and 75).")
    elif type_id == "deflect_ranged":
        if not spec.get("save") and not spec.get("draws_ft"):
            out.append(f"{path}: say how it turns an attack — a save (arrow deflection: "
                       f"\"save\": \"ref\", \"dc\": 20, \"per\": \"round\") or draws_ft "
                       f"(arrow catching: 5).")
        if spec.get("save") and not spec.get("dc"):
            out.append(f"{path}: a deflecting save needs its DC.")
    elif type_id == "slay":
        n = number("natural")
        if "natural" in spec and (n is None or not 1 <= n <= 20):
            out.append(f"{path}: natural is the face of the d20, 1 to 20 (vorpal: 20).")
    elif type_id == "item_power":
        given = [k for k in ("spell", "effect", "tell") if spec.get(k)]
        if len(given) != 1:
            out.append(f"{path}: an item power does exactly one of: casts a spell "
                       f"(\"spell\"), does one effect (\"effect\"), or says what happens "
                       f"(\"tell\"). It has {', '.join(given) or 'none'}.")
        if spec.get("effect") and len(spec.get("effect") or []) != 1:
            out.append(f"{path}: an item power's effect is one document; group several "
                       f"with a bundle.")
        if "uses" not in spec:
            out.append(f"{path}: an item power says how often it can be used — "
                       f"\"uses\": \"per_day\" with \"uses_count\", or \"unlimited\" for "
                       f"at will. Left out, it would be at will by accident.")
        if spec.get("tell") and _TELL_NUMBER.search(str(spec["tell"])):
            out.append(f"{path}: a power's tell carries no number; a number in prose is a "
                       f"mechanic nothing applies. Say it with an effect.")
    return out


# A digit in a tell is a mechanic authored into prose (the class abilities' rule, `{name}`
# and `{target}` and nothing else).
_TELL_NUMBER = re.compile(r"\d")


def _alchemy_problems(spec: dict, type_id: str, path: str) -> list[str]:
    """The limits the alchemist's words have that a dropdown and an int cannot say."""
    def number(key):
        v = spec.get(key)
        if v is None or isinstance(v, bool):
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    out: list[str] = []
    if "grade" in spec and spec["grade"] is not None:
        g = number("grade")
        if g is None or g < 1:
            out.append(f"{path}: grade is a whole number, 1 or more (1 is the weakest a "
                       f"trait can be).")
    # A carried cost reaches its holder through the carried door (`Actor.sync_carried`),
    # which runs CARRIED_TYPES and nothing else — the same rule the `carried` trigger is
    # held to, for the same reason: carrying a thing can sicken you or eat at a score, and
    # a route the door cannot deliver would be a drawback that never lands.
    if str(spec.get("route") or "") == "carried" and type_id not in CARRIED_TYPES:
        out.append(f"{path}: a carried cost can only be {', '.join(CARRIED_TYPES)}, what "
                   f"carrying a thing can do to whoever holds it. Use one of those, or "
                   f"another route.")
    if "source" in spec and spec["source"] is not None \
            and not isinstance(spec["source"], str):
        out.append(f"{path}: source is the name of what the effect comes from, in words: "
                   f"\"antitoxin\", \"property:bane\". The stacking rule reads it.")
    if type_id == "light":
        r, raised = number("radius_ft"), number("raised_ft")
        if r is not None and r < 0:
            out.append(f"{path}: the lit radius is 0 feet or more (0 for a candle).")
        if raised is not None and r is not None and raised <= r:
            out.append(f"{path}: raised_ft is the OUTER radius of the brighter ring, so it "
                       f"is more than the lit radius: a sunrod is 30 and 60, a torch 20 "
                       f"and 40.")
        if (r or 0) <= 0 and (raised or 0) <= 0 and r is not None:
            out.append(f"{path}: a light with no lit radius and no ring lights nothing. A "
                       f"candle is radius 0, raised 5.")
    elif type_id == "burning":
        rounds = number("rounds")
        if "rounds" in spec and (rounds is None or rounds < 1):
            out.append(f"{path}: a fire burns for 1 round or more (alchemist's fire: 1, "
                       f"the round following).")
        if spec.get("save") and spec.get("dc") in (None, ""):
            out.append(f"{path}: putting it out with a save needs the save's DC "
                       f"(alchemist's fire: Reflex 15).")
        sb = number("smother_bonus")
        if "smother_bonus" in spec and (sb is None or sb < 0):
            out.append(f"{path}: smother_bonus is a bonus, 0 or more (the book's is 2).")
    return out


# The keys a `when` may ask, each with what reads it. One grammar with several readers:
# the roll context (`sheet._when_holds`), the bearer (`classfeatures.holds`), the build
# (`forge_items` answers `armour.weight` before play) and the scene (`sheet.SITUATION_KEYS`,
# answered off the moment of the roll). Measured over content/ on build/alchemy: these are
# every key any shipped document uses. `when` had no check at all (it was not in COMMON),
# and a key no reader asks is an unevaluable clause, which is dropped: the term applies to
# nobody, with nothing anywhere saying why — the alchemist's "+2 against undead" written
# as `{"undead": true}` would have been exactly that. Contracts §2.1 made it validated.
WHEN_KEYS: dict[str, str] = {
    "target": "the creature the roll is made against, by type, subtype, armour_metal, "
              "alignment or a property's choice (sheet._when_holds)",
    "attacker": "whoever made the blow, by type or subtype (sheet._when_holds)",
    "weapon": "the weapon's own fields: category, hands, light, finessable, key, ranged, "
              "slashing_or_piercing (sheet._when_holds)",
    "choice": "an attack option the player declared, such as power_attack",
    "against": "what the save or check is against, one of AGAINST: spell, poison, fear, "
               "trap, cold, heat, thirst, starvation, breath ...",
    "casting": "the situation a concentration check is made in: defensively, grappled, "
               "damaged (Engine._concentrate)",
    "attack": "the kind of attack: melee or ranged",
    "maneuver": "the combat manoeuvre being made or resisted",
    "resting": "a save made while resting (a bedroll's cold)",
    "range_ft": "the attack's range, compared: {\"lte\": 30}",
    "armour": "the armour's weight class, answered at the forge (forge_items)",
    "bearer": "the bearer's armour, load, shield, terrain or pool (classfeatures.holds)",
    "weapon_group": "the held weapon's group, or the class pick (classfeatures.holds)",
    "daylight": "whether it is day where the roll is made (sheet.SITUATION_KEYS)",
    "underground": "whether the roll is made underground",
    "near": "a kind of creature within 10 ft: {\"type\": \"undead\"}",
    "wielder_casts": "whether the item is in a caster's hands",
    "day_phase": "the phase of the day (rules/sky.py)",
}
_WHEN_CREATURE_KEYS = {"target": ("type", "subtype", "armour_metal", "alignment", "choice"),
                       "attacker": ("type", "subtype")}
_WHEN_COMPARE = ("lte", "gte", "lt", "gt", "eq")
_WHEN_BOOLS = ("daylight", "underground", "wielder_casts", "resting")

# What a roll may be made AGAINST — the `against` of a roll context, one word per danger,
# each with the reader that passes it. A closed list, because the clause is answered by
# equality: until 2026-10-09 `against` took any string, and a document that wrote
# "dehydration" where the survival clock passes "thirst" would have held for nobody with
# nothing saying why. The first seven are what shipped documents already asked; the
# survival words came with Endurance (CRB p.141, aonprd.com/FeatDisplay.aspx?
# ItemName=Endurance), whose benefit is a list of exactly these rolls.
AGAINST: dict[str, str] = {
    "spell": "a save a spell called for (Engine._op_save, the cast's saves)",
    "poison": "a poison's own save (Engine._op_save, a poison gate)",
    "disease": "a disease's save",
    "fear": "a fear effect",
    "enchantment": "an enchantment",
    "trap": "a trap",
    "cold": "cold weather: the hourly Fortitude save (Engine._exposure, hazards.json cold)",
    "heat": "hot weather: the hourly Fortitude save (Engine._exposure, hazards.json heat)",
    "thirst": "the hourly Constitution check without water (survival.charge)",
    "starvation": "the daily Constitution check without food (survival.charge)",
    "breath": "the Constitution check to keep holding one's breath (Engine.breathe)",
    "spell_resistance": "the caster level check to overcome spell resistance "
                        "(Engine._resists)",
}

# The situations a concentration check is made in (`Engine._concentrate`), as the
# Core Rulebook's Table 8-5 names them and as far as the engine makes them.
CASTING_SITUATIONS: dict[str, str] = {
    "defensively": "casting defensively: DC 15 + double the spell's level",
    "grappled": "casting while grappled: DC 10 + the grappler's CMB + the spell's level",
    "damaged": "struck while casting: DC 10 + the damage taken + the spell's level",
}


def when_problems(when, where: str = "when") -> list[str]:
    """Everything wrong with a `when` clause, named with the fix.

    Structural, and no narrower than the readers: every clause a shipped document carries
    validates (tests/test_alchemy_vocabulary pins that over content/). What it refuses is
    what no reader can answer — a key nobody asks, a creature type that is not one, an
    operator the comparison does not know, a phase of the day the sky does not have.
    `"$pick"` is a class document's placeholder, filled by the class's choice
    (`classfeatures`), and is let through wherever it stands.
    """
    if not isinstance(when, dict) or not when:
        return [f"{where} is an object of clauses: {{\"target\": {{\"type\": \"undead\"}}}}."]
    out: list[str] = []
    unknown = sorted(set(when) - set(WHEN_KEYS))
    if unknown:
        out.append(f"{where}: no reader asks {', '.join(unknown)}, so the clause would "
                   f"hold for nobody. Known: {', '.join(WHEN_KEYS)}.")
    for key, want in when.items():
        if key not in WHEN_KEYS or want == "$pick":
            continue
        if key in _WHEN_CREATURE_KEYS:
            if not isinstance(want, dict) or not want:
                out.append(f"{where}.{key} is {{\"type\": \"undead\"}}, by type, subtype"
                           + (", alignment or a choice" if key == "target" else "") + ".")
                continue
            bad = sorted(set(want) - set(_WHEN_CREATURE_KEYS[key]))
            if bad:
                out.append(f"{where}.{key} has no key {', '.join(bad)}. Known: "
                           f"{', '.join(_WHEN_CREATURE_KEYS[key])}.")
            types = want.get("type")
            if types is not None and types != "$pick":
                listed = types if isinstance(types, list) else [types]
                # The forge's data writes "magical beast" with a space and the reader
                # leafs it (`sheet._kind_leaf`), so a space is the same word as a hyphen.
                wrong = [t for t in listed
                         if str(t).strip().lower().replace(" ", "-") not in CREATURE_TYPES]
                if wrong:
                    out.append(f"{where}.{key}.type: {', '.join(map(str, wrong))} is not a "
                               f"creature type. One of: {', '.join(CREATURE_TYPES)}.")
            if "alignment" in want and want["alignment"] not in ALIGNMENTS:
                out.append(f"{where}.{key}.alignment is one of {', '.join(ALIGNMENTS)}.")
        elif key in ("weapon", "armour", "bearer", "near"):
            if not isinstance(want, dict) or not want:
                out.append(f"{where}.{key} is an object of the fields it asks.")
        elif key in _WHEN_BOOLS:
            if not isinstance(want, bool):
                out.append(f"{where}.{key} is true or false.")
        elif key == "day_phase":
            from .sky import PHASES

            if want not in PHASES:
                out.append(f"{where}.day_phase is one of {', '.join(PHASES)}.")
        elif key == "against":
            if str(want) not in AGAINST:
                out.append(f"{where}.against: no roll is made against {want!r}, so the "
                           f"clause would hold for nobody. One of: "
                           f"{', '.join(AGAINST)}.")
        elif key == "casting":
            if str(want) not in CASTING_SITUATIONS:
                out.append(f"{where}.casting: no concentration check is made "
                           f"{want!r}. One of: {', '.join(CASTING_SITUATIONS)}.")
        elif isinstance(want, dict):
            bad = sorted(set(want) - set(_WHEN_COMPARE))
            if bad or not want:
                out.append(f"{where}.{key}: compare with {', '.join(_WHEN_COMPARE)}: "
                           f"{{\"lte\": 30}}.")
    return out


def product_trait_problems(spec: dict, path: str = "trait") -> list[str]:
    """What a product trait on an alchemy material must carry beyond a valid effect
    (contracts §2.1, plan §5.6): an essence a formula can key on, a route a product can
    deliver it by, and nothing narrative — narrative stays legal in the vocabulary and is
    refused here, in the alchemist's own validator (lane D calls this beside `validate`).

    Measured before the pass: 75 of 139 materials carried nothing executable and 5 were
    narrative only (plan §5.1), so a formula keyed on essences would have had nothing to
    match.
    """
    out = list(validate(spec, path))
    if str(spec.get("type") or "") == "narrative":
        out.append(f"{path}: a product trait is never narrative. Write it as a typed effect "
                   f"the engine runs, or leave it out.")
    if not spec.get("essence"):
        out.append(f"{path}: a product trait names its essence, one of "
                   f"{', '.join(ESSENCES)}.")
    if not spec.get("route"):
        out.append(f"{path}: a product trait names its route, one of {', '.join(ROUTES)}.")
    return out


def is_drawback(spec: dict) -> bool:
    """Whether this effect leaves its holder worse off.

    The forge's validators need "at least one negative in each list" (plan §5.7), and for
    a modifier that is the sign of its amount. For a gear number it is not: an acp of -2
    is the drawback and an asf of -10 is the benefit, because the armour table stores the
    two the opposite way round. `GEAR_TARGETS[...]["better"]` carries the direction, so
    the answer is looked up here once rather than re-derived by each reader. A formula,
    or a type with no number, is not called a drawback — it cannot be told from the page.
    """
    t = str(spec.get("type") or "")
    try:
        amount = int(spec.get("amount"))
    except (TypeError, ValueError):
        return False
    if t == "gear_mod":
        better = GEAR_TARGETS.get(str(spec.get("target") or ""), {}).get("better", 0)
        return amount * better < 0
    if t in ("ability_mod", "skill_mod", "save_mod", "combat_mod", "situational_mod",
             "speed"):
        return amount < 0
    return False


def _lasts(duration) -> bool:
    """Whether this duration is a window rather than an instant."""
    if not isinstance(duration, dict):
        return False
    unit = str(duration.get("unit", ""))
    if unit == "permanent":
        return True
    if unit in ("", "instant"):
        return False
    return str(duration.get("amount", "")).strip() not in ("", "0")


def _vocab_name(vocab: str, value) -> str:
    for option in VOCAB.get(vocab, []):
        if option["id"] == str(value):
            return option["name"]
    return str(value)


def _is_dice(s: str) -> bool:
    """`1d4`, `2d6+2`, a flat number, the corpus's own `1-4`, or `10/level`.

    The herb document writes healing as "roll 1-4 to see how many hit points", which is a
    d4 by another name. Refusing the notation would have rejected four real entries for a
    difference in spelling.

    `10/level` and `1d6/2 levels` were added last, for harm, implosion and wail of the
    banshee — a flat 10 points per caster level, which `dice: "10"` gets wrong at every
    level above 1st. Strictly more is accepted than before, so nothing that validated
    stops validating.
    """
    return bool(re.fullmatch(
        r"\s*\d*\s*d\s*\d+\s*(?:[+-]\s*\d+)?\s*|\s*\d+\s*|\s*\d+\s*-\s*\d+\s*", s, re.I)
        or _PER_LEVEL_DICE.match(s))


def executable(spec: dict) -> bool:
    """Whether the engine can resolve this today.

    Per spec, not only per type, where the type alone cannot say: a speed whose mode no
    reader moves (`TARGETS_AWAITING_READER`), and a permission with no `tag`, which has
    nothing to grant however its type is marked.
    """
    t = str(spec.get("type", ""))
    found = find(t)
    if not (found and found[1].engine):
        return False
    waiting = TARGETS_AWAITING_READER.get(t)
    if waiting and str(spec.get("target") or "") in waiting:
        return False
    if t == "permission" and not permission_tag(spec.get("tag")):
        return False
    return True


# --- rendering ------------------------------------------------------------------------------

def render(spec: dict, *, against: bool = False) -> str:
    """One authored effect as the line a card shows.

    `against` adds who a `when.target` clause limits it to ("against undead"); the
    magic property card asks for it (`property_lines`).

    Deliberately the same voice as `rules/effects.py` produces from prose, so an item
    whose effects were authored and one whose effects were read out of a description look
    the same on a card. The player should not be able to tell which is which.
    """
    found = find(str(spec.get("type", "")))
    if found is None:
        # Noqual's assay recoil (`materials.ASSAY_DANGERS`, the owner's house rule of
        # 2026-10-04) is not an authorable effect, but it reaches a card: without words
        # here the assay confirm printed nothing of its own and fell back on a general
        # warning, because `knowledge.danger_of` hands over the effect without its note.
        if spec.get("type") == "suppress_magic":
            dur = _duration(spec.get("duration"))
            return "Suppresses your active magic" + (f" for {dur}" if dur else "")
        return str(spec.get("note") or spec.get("type") or "?")
    _, etype = found
    t = etype.id
    target = spec.get("target")
    amount = spec.get("amount")
    dice = spec.get("dice")
    dur = _duration(spec.get("duration"))

    if t in ("ability_mod", "skill_mod", "save_mod", "combat_mod", "situational_mod"):
        sign = _signed(amount)
        # The note carries the qualifier a dropdown cannot hold — "to staunch bleeding" —
        # without which two bonuses on the same skill read as the same effect twice.
        qualifier = str(spec.get("note") or "").strip()
        body = f"{sign} {_label(etype, target)}"
        if qualifier:
            body += f" {qualifier}"
    elif t == "heal":
        what = ("non-lethal damage"
                if spec.get("lethality") == "nonlethal" else "hit points")
        body = f"Heals {dice} {what}"
    elif t == "damage":
        kind = spec.get("damage_type", "untyped")
        lethal = "" if spec.get("lethality", "lethal") == "lethal" else " non-lethal"
        body = f"{dice} {kind}{lethal} damage"
        if spec.get("per_multiplier"):
            # Flaming burst's line has to say why a x3 axe deals 2d10: the dice step with
            # the weapon, and the card is where a player looks to find out.
            body += " per step of the weapon's critical multiplier"
    elif t == "temp_hp":
        body = f"{dice} temporary hit points"
    elif t == "fast_healing":
        body = f"Fast healing {amount}"
    elif t == "bleed":
        body = f"Bleed {amount} per round"
        if spec.get("stacks"):
            body += ", more with every hit"
    elif t in ("ability_damage", "ability_drain"):
        word = "drain" if t.endswith("drain") else "damage"
        body = f"{dice} {ABILITY_FULL.get(str(target), str(target))} {word}"
    elif t == "ability_restore":
        body = f"Restores {dice} {ABILITY_FULL.get(str(target), str(target))}"
    elif t == "apply_condition":
        body = f"Causes {_label(etype, target).lower()}"
    elif t == "remove_condition":
        body = f"Ends {_label(etype, target).lower()}"
    elif t == "suppress_condition":
        body = f"Holds off {_label(etype, target).lower()}"
    elif t == "resistance":
        # "Resist fire 0" is not a rating, it is a missing one. The source often says
        # "resistance to fire damage" without a number, and a zero on the card reads as
        # a value somebody chose.
        body = f"Resist {target}" + (f" {amount}" if amount else "")
    elif t == "damage_reduction":
        body = f"DR {amount}/{spec.get('bypass') or '—'}"
    elif t == "immunity":
        body = f"Immune to {target}"
    elif t == "sense":
        rng = f" {spec['range']} ft" if spec.get("range") else ""
        body = f"{_label(etype, target)}{rng}"
    elif t == "speed":
        body = f"{_signed(amount)} ft {_label(etype, target).lower()}"
    elif t == "spell_effect":
        cl = f", caster level {spec['caster_level']}" if spec.get("caster_level") else ""
        body = f"Acts as {target}{cl}"
    elif t == "save_gate":
        save = _label(etype, target)
        parts = [f"{save} DC {spec.get('dc', '?')}".strip()]
        fail = [render(e) for e in spec.get("on_failure") or []]
        ok = [render(e) for e in spec.get("on_success") or []]
        if fail:
            parts.append("fail: " + ", ".join(fail))
        if ok:
            parts.append("save: " + ", ".join(ok))
        body = " · ".join(parts)
    elif t == "manifest":
        what = str(spec.get("what") or "something")
        # The dropdown's own label explains the shape to somebody choosing one — "A
        # spread from a point" — and reads as nonsense in a sentence. The card gets the
        # noun instead.
        shape = {"radius": "radius spread", "line": "line", "wall": "wall",
                 "square": "block", "cone": "cone",
                 "point": "square"}.get(str(spec.get("shape") or "radius"), "spread")
        terrain = str(spec.get("terrain") or "none")
        does = {"obscuring": "blocking sight", "blocked": "solid",
                "difficult": "difficult ground"}.get(terrain, "")
        body = what[:1].upper() + what[1:]
        if spec.get("size"):
            body += f" — a {spec['size']}-foot {shape}"
        if does:
            body += f", {does}"
        hazard = [render(e) for e in spec.get("on_enter") or []]
        if hazard:
            body += " · on entering: " + ", ".join(hazard)
    elif t == "summon":
        n = int(spec.get("count") or 1)
        body = f"Summons {n} {spec.get('creature') or 'creature'}" + ("s" if n > 1 else "")
    elif t == "spell_operation":
        what = str(spec.get("target") or "a magical effect")
        body = f"{_vocab_name('spell_operation', spec.get('operation'))}: {what}"
        if str(spec.get("everything")) == "yes":
            body += " — and everything else on them"
        if spec.get("check_dc"):
            body += f" (caster level check, DC {spec['check_dc']})"
    elif t == "choose_one":
        options = spec.get("options") or []
        chosen = spec.get("chosen")
        if chosen not in (None, "") and 1 <= int(chosen) <= len(options):
            body = f"Chosen: {render(options[int(chosen) - 1])}"
        else:
            body = "One of: " + " / ".join(render(o) for o in options) if options \
                else "One of — nothing to choose from"
    elif t == "bundle":
        inner = ", ".join(render(e) for e in spec.get("effects") or [])
        label = str(spec.get("label") or "").strip()
        body = f"{label}: {inner}" if label else inner
    elif t == "concealment":
        body = f"{spec.get('miss_chance', 20)}% miss chance"
        if str(spec.get("blocks_targeting")) == "yes":
            body += ", and cannot be targeted"
    elif t == "spell_resistance":
        body = f"Spell resistance {amount}"
    elif t == "negative_level":
        n = str(amount or 1)
        body = f"{n} negative level" + ("" if n == "1" else "s")
        if spec.get("becomes_permanent"):
            body += f" ({spec['becomes_permanent']})"
    elif t == "attitude":
        towards = _vocab_name("recipient", spec.get("towards") or "caster").lower()
        body = f"Attitude towards {towards}: {_label(etype, target).lower()}"
    elif t == "object_damage":
        what = str(spec.get("item") or "").strip() or "everything carried"
        body = f"{dice} {spec.get('damage_type', 'untyped')} damage to {what}"
    elif t == "gear_mod":
        body = _gear_line(str(target or ""), amount)
    elif t == "strikes_as":
        body = f"Strikes as {_label(etype, target).lower()}"
    elif t == "working":
        body = _WORKING_PHRASE.get(str(spec.get("trait") or ""),
                                   str(spec.get("trait") or "a working trait"))
        if amount not in (None, ""):
            body += f" ({_signed(amount)})"
        body = body[:1].upper() + body[1:]
    elif t in _MAGIC_RENDER:
        body = _MAGIC_RENDER[t](spec)
    elif t == "light":
        bits = []
        if spec.get("radius_ft"):
            bits.append(f"Normal light {spec['radius_ft']} ft")
        if spec.get("raised_ft"):
            bits.append(f"one step brighter out to {spec['raised_ft']} ft")
        body = ", ".join(bits) or "Light"
        body = body[:1].upper() + body[1:]
    elif t == "burning":
        n = str(spec.get("rounds") or 1)
        body = (f"Burns for {dice} {spec.get('damage_type') or 'fire'} a round for {n} "
                f"round{'' if n == '1' else 's'}")
        if spec.get("save"):
            body += (f" unless put out ({_vocab_name('save', spec['save'])} DC "
                     f"{spec.get('dc', '?')}")
            if spec.get("smother_bonus"):
                body += f", {_signed(spec['smother_bonus'])} rolling on the ground"
            body += ")"
    else:
        body = str(target or spec.get("note") or etype.name)
        body = body[:1].upper() + body[1:]

    # Against whom, when asked. Bane's +2d6 and holy's +2d6 read exactly like flaming's on
    # a card without it, and the difference is the whole property. Asked for rather than
    # always added because the forge's review table (tools/forge_review.py) already
    # appends its own "(when target type fey)" to the same line, and the owner's reviewed
    # document would have said it twice.
    if against:
        phrase = _against(spec.get("when"))
        if phrase:
            body += f" {phrase}"

    # Who and when, appended rather than woven in, so the sentence a type already produced
    # is unchanged whenever the two are left at their defaults — which is all 6,476 of the
    # specs that existed before these fields did.
    aim = _aim(spec)
    if aim:
        body += f", {aim}"

    if dur == "permanent":
        # "for permanent" is not English. Found in an authored entry: a +10 Strength with
        # no expiry read "+10 Strength for permanent".
        body += " (permanent)"
    elif dur:
        # The comma only when something was already appended, so "+2 Climb checks for 1
        # hour" is untouched and "…, on whoever struck them, for 5 rounds" does not run
        # its two clauses together.
        body += (", " if aim else " ") + f"for {dur}"
    limit = _uses(spec)
    if limit:
        body += f" ({limit})"
    return body


# How each of the two lands in a sentence. Kept as phrases rather than reusing the
# dropdown's own labels, because "Whoever struck them" reads as a heading and "on whoever
# struck them" reads as English — and the card is read by a player, not by a form.
_RECIPIENT_PHRASE = {
    "target": "", "self": "on whoever has it", "caster": "on the caster",
    "attacker": "on whoever struck them", "ally": "on an ally",
    "area": "on everything in the area",
}
_TRIGGER_PHRASE = {
    "on_cast": "", "each_round": "every round", "when_struck": "when struck in melee",
    "when_grappled": "when grappled", "on_enter": "on entering it",
    "on_expiry": "when it ends",
    "hit": "on a hit", "crit": "on a critical hit",
    "first_wound_daily": "on the first wound it deals each day",
    "carried": "while carried", "wielded": "while held", "worn": "while worn",
}


def _gear_line(target: str, amount) -> str:
    """"-2 armour check penalty", "weighs 50% less", "moves as one class lighter".

    Worded per target because the sign means different things on each (see
    `GEAR_TARGETS`): "+3 armour check penalty" would read as a heavier suit to every
    player who has seen a printed one, when it is mithral making the suit lighter.
    """
    try:
        n = int(amount)
    except (TypeError, ValueError):
        return f"{_signed(amount)} {GEAR_TARGETS.get(target, {}).get('name', target).lower()}"
    size = abs(n)
    if target == "acp":
        return f"{n:+d} armour check penalty" if n < 0 \
            else f"Armour check penalty {size} lighter"
    if target == "max_dex":
        return f"{n:+d} maximum Dexterity bonus"
    if target == "asf":
        return f"{n:+d}% arcane spell failure"
    if target == "weight_pct":
        return f"Weighs {size}% {'less' if n < 0 else 'more'}"
    if target == "hardness":
        return f"{n:+d} hardness"
    if target == "hp_per_inch":
        return f"{n:+d} hit points per inch"
    if target == "category":
        word = {1: "one", 2: "two"}.get(size, str(size))
        plural = "" if size == 1 else "es"
        return (f"Moves as {word} weight class{plural} "
                f"{'lighter' if n < 0 else 'heavier'}")
    if target == "speed_penalty":
        return f"{size} ft {'less' if n < 0 else 'more'} speed penalty"
    if target == "range_pct":
        return ("Doubles the range increment" if n == 100
                else f"Range increment {size}% {'longer' if n > 0 else 'shorter'}")
    if target == "throw_range_ft":
        return f"Can be thrown, range increment {n} ft"
    return f"{n:+d} {target}"


# Each trait as the card says it. Plain words for what the smith notices, not the bench's
# numbers: the band percentages are still proposed (plan §17), and a card that printed
# "20% wider" would be wrong the first time playtest moved them.
_WORKING_PHRASE = {
    "easily_worked": "works easily at the forge",
    "flawless": "takes masterwork with no extra difficulty",
    "malleable": "forgiving of a bad blow: a badly missed step ruins nothing",
    "pure": "pure: the Craft check is rolled twice and the better kept",
    "slaggy": "slaggy: the best it can reach drops a step until it is folded",
    "sulfurous": "burns sulfurous: a wider heat band, but a crude result runs hot-short",
    "clean_heat": "burns clean: no risk of a flaw from the fire",
    "quench_sensitive": "quench-sensitive: a narrow quench, and brine cracks it on a miss",
    "narrow_window": "a narrow working window: the heat bands are tight",
    "forgiving": "forgiving: the heat bands are wide",
    "reactive": "reactive: assaying it is dangerous",
    "cleans_slag": "cleans the slag out of a smelt",
    "weld_aid": "aids a weld: folding and strengthening come easier",
    "brittle": "brittle: it cracks under a hard blow",
    "hot_short": "hot-short: it cracks when worked hot",
    "night_only": "binds only by night",
    "eager": "eager: the binding's windows are wider",
    "skittish": "skittish: it drifts in its seat while it is matched",
    "heavy": "heavy: its draws fade fast when it is refined",
    # Shared by the circle and the alchemist's bench: reading it, or a badly failed step
    # with it, goes wrong on the one working it (alchemy plan §8).
    "volatile": "volatile: reading it is dangerous, and a badly failed step flares",
    # The alchemist's (alchemy plan §5.5). Plain words; the band sizes are still proposed.
    "stabilizer": "a stabilizer: it calms one volatile input in the same step",
    "catalyst": "a catalyst: never used up, it eases the step it is in",
    "apparatus": "apparatus: never used up, it eases one method's work",
    "solid": "a solid: it can be calcined or sublimed",
    "liquid": "a liquid: it can be distilled",
    "combustible": "combustible: it burns away rather than calcining",
    "slow_to_dissolve": "slow to dissolve: the stirring takes longer",
    "light_sensitive": "light-sensitive: left unsealed, it weakens a little each day",
    "corrosive": "corrosive: it eats through a metal vessel",
    "toxic_to_handle": "toxic to handle: it harms whoever works it unprotected",
    "wild": "wild: it takes on a trait of whatever it is worked with",
    "drinkable": "a vessel to drink from",
    "shatters": "a vessel that shatters where it is thrown",
    "bursts": "a vessel that bursts open where it lands",
    "struck": "a casing that goes off when it is struck",
    "stick": "a stick or rod, lit or struck in the hand",
    "fireproof": "fireproof: it holds what burns",
    "warded": "warded: it holds what would eat through a plain vessel",
    "lead_lined": "lead-lined: it holds what must be kept from the light",
    "solvent:water": "a solvent: dissolves what water dissolves",
    "solvent:alcohol": "a solvent: dissolves what spirits dissolve",
    "solvent:vinegar": "a solvent: dissolves what vinegar dissolves",
    "solvent:oil": "a solvent: dissolves what oil dissolves",
    "solvent:acid": "a solvent: dissolves what acid dissolves",
}


_ALIGNMENT_WORDS = {"good": "good", "evil": "evil", "lawful": "lawful",
                    "chaotic": "chaotic"}


def _against(when) -> str:
    """"against undead", "against evil creatures", "against the chosen foe" — or ""."""
    if not isinstance(when, dict) or not isinstance(when.get("target"), dict):
        return ""
    t = when["target"]
    if t.get("choice"):
        return f"against the chosen {str(t['choice']).replace('_', ' ')}"
    bits = []
    for key in ("type", "subtype"):
        v = t.get(key)
        if v:
            words = v if isinstance(v, (list, tuple)) else [v]
            bits.append(" or ".join(str(w).replace("-", " ") for w in words))
    if t.get("alignment"):
        bits.append(f"{_ALIGNMENT_WORDS.get(str(t['alignment']), t['alignment'])} creatures")
    return f"against {' '.join(bits)}" if bits else ""


def _render_crit_range(spec: dict) -> str:
    m = spec.get("multiply", 2)
    return ("Doubles the threat range" if str(m) == "2"
            else f"Multiplies the threat range by {m}")


def _render_extra_attack(spec: dict) -> str:
    n = int(spec.get("count") or 1)
    return (f"{'One extra attack' if n == 1 else f'{n} extra attacks'} on a full attack, "
            f"at full base attack bonus")


def _render_deflect(spec: dict) -> str:
    bits = []
    if spec.get("save"):
        save = _vocab_name("save", spec["save"])
        per = " once a round" if spec.get("per") == "round" else ""
        plus = " + the attacking weapon's enhancement" if spec.get(
            "dc_adds_enhancement") else ""
        bits.append(f"Deflects a ranged attack{per} on a {save} save (DC "
                    f"{spec.get('dc', '?')}{plus})")
    if spec.get("draws_ft"):
        bits.append(f"Draws ranged attacks aimed within {spec['draws_ft']} ft to the "
                    f"bearer")
    if spec.get("deflection"):
        bits.append(f"{_signed(spec['deflection'])} deflection to AC against ranged "
                    f"attacks")
    return "; ".join(bits) or "Turns ranged attacks"


def _render_slay(spec: dict) -> str:
    line = "Slays outright"
    if spec.get("natural"):
        line += f" on a natural {spec['natural']}"
    if spec.get("except"):
        line += " (not " + ", ".join(str(x).replace("-", " ") for x in spec["except"]) + ")"
    return line


def _render_item_power(spec: dict) -> str:
    if spec.get("spell"):
        what = f"Casts {str(spec['spell']).replace('-', ' ')}"
        if spec.get("caster_level"):
            what += f" (caster level {spec['caster_level']})"
    elif spec.get("effect"):
        what = render((spec.get("effect") or [{}])[0])
    else:
        what = str(spec.get("tell") or "A power")
    if isinstance(spec.get("area"), dict):
        what += f", {spec['area'].get('ft')}-ft {spec['area'].get('shape')}"
    if spec.get("uses") == "unlimited":
        what += " (at will)"
    return what


_MAGIC_RENDER = {
    "crit_range": _render_crit_range,
    "extra_attack": _render_extra_attack,
    "enhancement_raise": lambda s: f"Enhancement bonus {_signed(s.get('amount'))}",
    "enhancement_to_ac": lambda s: "Moves some or all of its enhancement bonus to AC, "
                                   "chosen each turn",
    "fortification": lambda s: f"{s.get('percent', 25)}% chance to turn a critical hit "
                               f"or sneak attack into an ordinary hit",
    "ignore_armour": lambda s: "Ignores armour and shield bonuses to AC" + (
        "; cannot harm " + ", ".join(str(x).replace("-", " ")
                                     for x in s["cannot_harm"])
        if s.get("cannot_harm") else ""),
    "deflect_ranged": _render_deflect,
    "weapon_lethality": lambda s: ("All its damage is non-lethal"
                                   if s.get("lethality", "nonlethal") == "nonlethal"
                                   else "All its damage is lethal") + (
        " (can be suppressed)" if s.get("suppressible") else ""),
    "slay": _render_slay,
    "item_power": _render_item_power,
}


def _aim(spec: dict) -> str:
    """"every round, on everything in the area" — or "" when both are at their default."""
    bits = [_TRIGGER_PHRASE.get(str(spec.get("trigger") or "on_cast"), ""),
            _RECIPIENT_PHRASE.get(str(spec.get("recipient") or "target"), "")]
    return ", ".join(b for b in bits if b)


def _signed(amount) -> str:
    """`+2`, `-4`, or a formula left as the author wrote it.

    A formula is not signed and must not be forced into a sign: "+caster_level/2" is not
    something anybody writes, and `int()` on it used to be a crash on the card.
    """
    if amount is None or str(amount).strip() == "":
        return "?"
    try:
        return f"{int(amount):+d}"
    except (TypeError, ValueError):
        return str(amount)


def _label(etype: EffectType, value) -> str:
    for f in etype.fields:
        if f.id == "target" and f.vocab:
            for option in VOCAB.get(f.vocab, []):
                if option["id"] == str(value):
                    return option["name"]
    return str(value or "")


def _duration(d) -> str:
    if not isinstance(d, dict):
        return ""
    unit = str(d.get("unit", ""))
    if unit in ("permanent", "instant"):
        return "" if unit == "instant" else "permanent"
    amount = d.get("amount")
    if amount in (None, ""):
        return ""
    plural = "" if str(amount) in ("1", "one") else "s"
    return f"{amount} {unit}{plural}"


def _uses(spec: dict) -> str:
    kind = spec.get("uses")
    if kind in (None, "", "unlimited"):
        return ""
    n = spec.get("uses_count")
    if kind == "once":
        return "once ever"
    per = {"per_day": "per day", "per_combat": "per combat",
           "per_hour": "per hour"}.get(str(kind), str(kind))
    return f"{n}× {per}" if n else per


# --- magic properties: the book's ability table (enchanting contracts §2.2) -----------------
#
# `content/rules/magic-properties.json`: one entry per book weapon, armour and shield
# ability, and the formula-priced ring and wondrous bonuses, each with its price, caster
# level, spells, restrictions and its bundle of effect documents. Every enchanting lane
# reads it: the layer (B) prices and builds from it, the engine (C) runs its documents,
# the essences (D) name its ids in `grants`, the bench (E) checks its requirements.
#
# Shipped data only, with no homebrew overlay, so it is cached with `lru_cache` rather
# than the `_NAME: dict | None = None` declaration the suite isolates between tests
# (tests/conftest.py `_CACHED`): nothing here is read from under CAMPAIGN_DIR.
#
# Validated on load: a bad entry raises `BadProperties` with every problem named, so a
# mistyped number stops the app in development rather than shipping as a sword that does
# nothing. Spell ids are checked by `property_problems(..., spell_ids=...)`, which the
# vocabulary test runs against the real spell list; the loader does not read 5 MB of
# spells to start.

import functools as _functools  # noqa: E402
import json as _json  # noqa: E402

PROPERTY_GEAR: tuple[str, ...] = ("weapon", "armour", "shield", "ring", "wondrous")
TIERS: tuple[str, ...] = ("common", "uncommon", "rare", "exotic", "legendary")
AURA_STRENGTHS: tuple[str, ...] = ("faint", "moderate", "strong", "overwhelming")
SCHOOLS: tuple[str, ...] = ("abjuration", "conjuration", "divination", "enchantment",
                            "evocation", "illusion", "necromancy", "transmutation",
                            "universal")
ALIGNMENTS: tuple[str, ...] = ("good", "evil", "lawful", "chaotic")

# What a property's `requires` may say. The first five restrict the vessel and are a
# refusal (a keen club is not a thing); the creator clauses are the book's "special
# prerequisites", each one more +5 DC when unmet and never a refusal (owner, round 1 and
# round 4 Q4). `launcher: false` is brilliant energy's "melee weapons, thrown weapons, and
# ammunition": anything but the bow or crossbow itself.
_REQUIRES: dict[str, type] = {
    "melee": bool, "ranged": bool, "thrown": bool, "launcher": bool,
    "damage_types_any": list,
    "creator_alignment": str, "creator_class": str, "creator_caster_level": int,
}

# What a property's choice can range over, and how the chosen value reaches a document.
#   creature_type  bane's foe: a type, or `{"subtype": "goblinoid"}` for a humanoid or an
#                  outsider; written into the document's `when.target` clause, so the
#                  existing `_when_holds` reads it by tag prefix (law 1).
#   damage_type    energy resistance's energy: written into the document's `target`.
#   skill          a competence bonus's skill: written into the document's `target`.
CHOICE_OF: tuple[str, ...] = ("creature_type", "damage_type", "skill")

# `when.target` keys a property document may use, and the ones `Actor._when_holds` does
# not read yet. A key it does not read makes the clause unevaluable, and an unevaluable
# clause is dropped — the term applies to nobody. Every property using one must say so in
# `not_yet`, and the validator holds it to that.
_WHEN_TARGET_KEYS = ("type", "subtype", "choice", "alignment")
# `alignment` left this list with enchanting lane C (2026-10-05): `_when_holds` reads it,
# and by the owner's round 6 ruling answers yes for every target until alignment exists.
WHEN_NOT_READ: dict[str, str] = {}

_PROPERTY_KEYS = {
    "id", "name", "gear", "slots", "plus", "gp", "scaled", "cl", "aura", "tier", "spells",
    "requires", "choice", "documents", "reads_tag", "not_yet", "wielder", "house",
    "aliases", "source", "text",
}
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class BadProperties(ValueError):
    """`content/rules/magic-properties.json` failed validation; every problem is named."""


def _properties_path():
    from pathlib import Path

    from django.conf import settings

    return Path(settings.BASE_DIR) / "content" / "rules" / "magic-properties.json"


@_functools.lru_cache(maxsize=1)
def _property_table() -> tuple[dict, dict]:
    raw = _json.loads(_properties_path().read_text(encoding="utf-8"))
    entries = raw.get("properties") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        raise BadProperties("magic-properties.json: \"properties\" must be a list of "
                            "entries.")
    problems = all_property_problems(entries)
    if problems:
        raise BadProperties("magic-properties.json is not valid:\n  "
                            + "\n  ".join(problems))
    table = {e["id"]: e for e in entries}
    aliases = {old: (e["id"], dict(choice or {}))
               for e in entries for old, choice in (e.get("aliases") or {}).items()}
    return table, aliases


def properties() -> dict[str, dict]:
    """Every magic property, by id. Validated on load (`BadProperties`). Read it, never
    mutate it: the dict is the cache's own (`bind` hands out copies)."""
    return _property_table()[0]


def property(prop_id: str) -> dict | None:            # noqa: A001 — the contract's name
    """One property by its id, or by an old magic-items.json id (`mi-flaming`); None
    when there is none. Shadows the builtin inside this module only, which uses no
    `@property`; the contract (enchanting contracts §2.2) names it this."""
    key = str(prop_id or "").strip().lower()
    table, aliases = _property_table()
    if key in table:
        return table[key]
    if key in aliases:
        return table[aliases[key][0]]
    return None


def from_alias(old_id: str) -> tuple[str, dict] | None:
    """An old catalogue id as `(property id, the choice it implies)`: `mi-energy-
    resistance-fire` is `("energy-resistance", {"energy": "fire"})`. For the migration
    (lane H). `mi-bane` gives an empty choice: the old bane never named its foe, so the
    migration has to ask."""
    hit = _property_table()[1].get(str(old_id or "").strip().lower())
    return (hit[0], dict(hit[1])) if hit else None


def property_tag(prop_id: str) -> str:
    """The standing tag an item carrying this property gives its holder while it is held
    or worn — `property.returning` — for the readers that ask a rule, not a number
    (`reads_tag`). Asked by prefix through `has_state`, never matched as a name."""
    return f"property.{str(prop_id).strip().lower()}"


def price_of(prop: dict, bonus: int | None = None) -> dict:
    """The book's price for one property, in its own shape — never an item's price (that
    is lane B's, since the squared table needs the whole item). `{"plus": 1}`,
    `{"gp": 3750}`, or for a scaled one bound at `bonus`, `{"gp": bonus² x
    gp_per_square}`."""
    if prop.get("plus") is not None:
        return {"plus": int(prop["plus"])}
    if prop.get("gp") is not None:
        return {"gp": int(prop["gp"])}
    scaled = prop.get("scaled") or {}
    if bonus is None or int(bonus) not in scaled.get("values", ()):
        raise ValueError(f"{prop.get('id')}: a scaled property is priced at one of its "
                         f"values {scaled.get('values')}, not {bonus!r}.")
    return {"gp": int(bonus) ** 2 * int(scaled["gp_per_square"])}


# --- binding: a property's documents for one item, its choice filled in ----------------------

def choice_problems(prop: dict, choice: dict | None) -> list[str]:
    """Everything wrong with the choice stored on an item for this property, named.

    `choice` is the record's dict, keyed by the choice's key (contracts §3.1):
    `{"foe": "undead"}`, `{"foe": {"subtype": "goblinoid"}}`, `{"energy": "fire"}`,
    `{"skill": "stealth", "bonus": 3}`. A scaled property's bonus rides in the same dict
    under `bonus`.

    Bane without a foe is refused here. The old catalogue's bane had no foe at all and its
    numbers sat in a note, so every reader would have applied them to every creature
    (enchanting plan §1); a property that asks a question is answered before it is bound.
    """
    pid = prop.get("id", "?")
    choice = dict(choice or {})
    out: list[str] = []
    spec = prop.get("choice")
    scaled = prop.get("scaled")
    allowed_keys = set()
    if spec:
        key = spec["key"]
        allowed_keys.add(key)
        value = choice.get(key)
        if value in (None, "", {}):
            # Plain words, no dashes (the final pass, 2026-10-06: this line reached the
            # bench's problems list as "choose its foe — one of aberration, ... — before
            # it is bound"). "choose its" stays: the alias check below keys on it.
            out.append(f"{pid}: choose its {key} ({_choice_hint(spec)}) before it is "
                       f"bound.")
        else:
            out.extend(_choice_value_problems(pid, spec, value))
    if scaled:
        allowed_keys.add("bonus")
        if choice.get("bonus") not in scaled.get("values", ()):
            out.append(f"{pid}: bind it at one of {scaled.get('values')} (\"bonus\").")
    extra = set(choice) - allowed_keys
    if extra:
        out.append(f"{pid}: {', '.join(sorted(extra))} is not a choice this property "
                   f"asks. It asks: {', '.join(sorted(allowed_keys)) or 'nothing'}.")
    return out


def _choice_hint(spec: dict) -> str:
    if spec.get("options"):
        return "one of " + ", ".join(spec["options"])
    return "a skill" if spec["of"] == "skill" else spec["of"].replace("_", " ")


def _choice_value_problems(pid: str, spec: dict, value) -> list[str]:
    key, of = spec["key"], spec["of"]
    options = spec.get("options")
    if of == "creature_type":
        if isinstance(value, dict):
            if set(value) - {"type", "subtype"} or not str(value.get("subtype") or "").strip():
                return [f"{pid}: a {key} by subtype is {{\"subtype\": \"goblinoid\"}}, "
                        f"with its type if you like ({{\"type\": \"humanoid\", ...}})."]
            if value.get("type") and value["type"] not in SUBTYPE_REQUIRED:
                return [f"{pid}: only {' and '.join(SUBTYPE_REQUIRED)} are chosen by "
                        f"subtype; {value['type']} is chosen by its type alone."]
            return []
        if value in SUBTYPE_REQUIRED:
            return [f"{pid}: {value} is chosen by subtype (the book: 'pick one subtype'): "
                    f"{{\"subtype\": \"goblinoid\"}}."]
        if options and value not in options:
            return [f"{pid}: {value!r} is not a {key}. One of: {', '.join(options)}, or a "
                    f"humanoid or outsider subtype."]
        return []
    if of == "skill":
        if value not in SKILLS:
            return [f"{pid}: {value!r} is not a skill. One of: {', '.join(sorted(SKILLS))}."]
        return []
    if options and value not in options:
        return [f"{pid}: {value!r} is not a {key}. One of: {', '.join(options)}."]
    return []


def bind(prop: dict | str, choice: dict | None = None) -> list[dict]:
    """A property's documents for one item: the choice filled in, the bonus worked out,
    each stamped `source: property:<id>`. What lane B's layer emits and lane C reads — no
    document leaves here naming a choice, so `_when_holds` never meets one.

    Bane bound against undead carries `when: {"target": {"type": "undead"}}`, exactly the
    clause cold iron's +2 against fey already uses, so the existing reader decides it. A
    deep copy every time: the table is the cache's own, and a reader that mutated a
    document would change every item that carries the property.
    """
    import copy

    if isinstance(prop, str):
        found = property(prop)
        if found is None:
            raise KeyError(f"no magic property {prop!r}")
        prop = found
    problems = choice_problems(prop, choice)
    if problems:
        raise ValueError("; ".join(problems))
    choice = dict(choice or {})
    spec = prop.get("choice")
    out = []
    for doc in prop.get("documents") or []:
        d = copy.deepcopy(doc)
        key = d.pop("choice_key", None)
        if key and spec:
            _fill_choice(d, spec, choice[key])
        if prop.get("scaled"):
            _fill_bonus(d, int(choice["bonus"]))
        d["source"] = f"property:{prop['id']}"
        out.append(d)
    return out


def _fill_choice(doc: dict, spec: dict, value) -> None:
    if spec["of"] != "creature_type":
        doc["target"] = value
        return
    if isinstance(value, dict):
        # A subtype answers alone: `subtype.goblinoid` is the tag the defender carries,
        # and adding `type.humanoid` beside it asks the same question twice.
        clause = {"subtype": value["subtype"]}
    else:
        clause = {"type": value}
    when = doc.get("when") or {}
    target = {k: v for k, v in dict(when.get("target") or {}).items() if k != "choice"}
    target.update(clause)
    doc["when"] = {**when, "target": target}


def _fill_bonus(doc: dict, bonus: int) -> None:
    """Every `bonus` formula in the document, worked out: the layer emits numbers."""
    v = doc.get("amount")
    if isinstance(v, str) and "bonus" in _safe_names(v):
        doc["amount"] = evaluate(v, {"bonus": bonus})
    for nested in _walk_docs(doc):
        if nested is not doc:
            _fill_bonus(nested, bonus)


def property_lines(prop: dict | str, choice: dict | None = None) -> list[str]:
    """The card lines for a property as bound on one item — "2d6 untyped damage against
    undead, on a hit". Unbound (no choice), a choosing property reads "against the chosen
    foe"; the documents are never sent, only these words."""
    if isinstance(prop, str):
        found = property(prop)
        if found is None:
            raise KeyError(f"no magic property {prop!r}")
        prop = found
    if choice_problems(prop, choice):
        docs = prop.get("documents") or []
    else:
        docs = bind(prop, choice)
    return [render(d, against=True) for d in docs]


def sample_choices(prop: dict) -> list[dict]:
    """One complete choice per option (and per scaled value): what the validator binds
    to prove every way the property can be bound gives valid documents."""
    spec, scaled = prop.get("choice"), prop.get("scaled")
    picks: list[dict] = [{}]
    if spec:
        if spec["of"] == "creature_type":
            values: list = [o for o in spec.get("options") or CREATURE_TYPES
                            if o not in SUBTYPE_REQUIRED] + [{"subtype": "goblinoid"}]
        elif spec["of"] == "skill":
            values = sorted(SKILLS)
        else:
            values = list(spec.get("options") or [])
        picks = [{spec["key"]: v} for v in values]
    if scaled:
        picks = [{**p, "bonus": b} for p in picks for b in scaled.get("values", ())]
    return picks


# --- validating the table ---------------------------------------------------------------------

def all_property_problems(entries: list, spell_ids=None) -> list[str]:
    """Every problem in the whole table: each entry's, and those between entries — a
    repeated id, an alias claimed twice, an alias that is also a property's id."""
    out: list[str] = []
    seen: set[str] = set()
    alias_owner: dict[str, str] = {}
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            out.append(f"entry {i + 1}: is not an object.")
            continue
        out.extend(property_problems(e, spell_ids=spell_ids))
        pid = str(e.get("id") or "")
        if pid in seen:
            out.append(f"{pid}: the id is used twice. Ids are how items name a property.")
        seen.add(pid)
        for old in e.get("aliases") or {}:
            if old in alias_owner:
                out.append(f"{pid}: the alias {old} already belongs to {alias_owner[old]}.")
            alias_owner[old] = pid
    for old, owner in alias_owner.items():
        if old in seen:
            out.append(f"{owner}: the alias {old} is also a property's id; an old save "
                       f"naming it would be read two ways.")
    return out


def property_problems(e: dict, spell_ids=None) -> list[str]:
    """Everything wrong with one entry, named with the fix — the classbuilder's style.

    `spell_ids`, when given, is the set of real spell ids. Every spell a property names
    must be one, or the binder's "do I know this spell?" asks after a spell nobody can
    ever know, and the +5 DC is permanent.
    """
    pid = str(e.get("id") or "?")
    at = pid
    out: list[str] = []
    say = out.append

    unknown = set(e) - _PROPERTY_KEYS
    if unknown:
        say(f"{at}: {', '.join(sorted(unknown))} is not a property field. Known: "
            f"{', '.join(sorted(_PROPERTY_KEYS))}.")
    if not _SLUG.match(pid):
        say(f"{at}: the id is lower-case words joined by hyphens: \"flaming-burst\".")
    if not str(e.get("name") or "").strip():
        say(f"{at}: needs a name, as the card shows it.")
    gear = e.get("gear")
    if not isinstance(gear, list) or not gear or set(gear) - set(PROPERTY_GEAR):
        say(f"{at}: gear is a list of {', '.join(PROPERTY_GEAR)}.")
        gear = []
    slots = e.get("slots")
    if slots is not None:
        from .tables import SLOTS

        if not isinstance(slots, list) or not slots or set(slots) - set(SLOTS):
            say(f"{at}: slots is a list of body slots: {', '.join(SLOTS)}.")

    # The price: exactly one of the book's three shapes.
    prices = [k for k in ("plus", "gp", "scaled") if e.get(k) is not None]
    if len(prices) != 1:
        say(f"{at}: give exactly one price — \"plus\" (a bonus equivalent, +1 to +5), "
            f"\"gp\" (a flat price outside the +10) or \"scaled\" (a bonus priced by its "
            f"square). It has {', '.join(prices) or 'none'}.")
    plus = e.get("plus")
    if plus is not None and (not isinstance(plus, int) or isinstance(plus, bool)
                             or not 1 <= plus <= 5):
        say(f"{at}: plus is the book's bonus equivalent, a whole number 1 to 5.")
    if e.get("gp") is not None and (not isinstance(e["gp"], int) or e["gp"] <= 0):
        say(f"{at}: gp is the book's flat price in gold, a whole number above 0.")
    scaled = e.get("scaled")
    if scaled is not None:
        out.extend(_scaled_problems(at, scaled))
        if {"weapon", "armour", "shield"} & set(gear):
            say(f"{at}: arms and armour abilities are priced as a bonus equivalent or in "
                f"gold; \"scaled\" is the ring and wondrous table's.")

    cl = e.get("cl")
    if not isinstance(cl, int) or isinstance(cl, bool) or not 1 <= cl <= 20:
        say(f"{at}: cl is the book's caster level, 1 to 20.")
    aura = e.get("aura")
    if (not isinstance(aura, dict) or aura.get("strength") not in AURA_STRENGTHS
            or not isinstance(aura.get("school"), list) or not aura["school"]
            or set(aura["school"]) - set(SCHOOLS)):
        say(f"{at}: aura is {{\"strength\": one of {', '.join(AURA_STRENGTHS)}, "
            f"\"school\": [one or more of {', '.join(SCHOOLS)}]}}.")
    if e.get("tier") not in TIERS:
        say(f"{at}: tier is one of {', '.join(TIERS)}.")

    spells = e.get("spells")
    if not isinstance(spells, list) or any(
            not isinstance(g, list) or not g
            or not all(isinstance(s, str) and s for s in g) for g in spells):
        say(f"{at}: spells is a list of groups, each a list of spell ids any one of which "
            f"meets it: [[\"fireball\", \"flame-blade\", \"flame-strike\"]].")
    elif spell_ids is not None:
        missing = sorted({s for g in spells for s in g} - set(spell_ids))
        if missing:
            say(f"{at}: {', '.join(missing)} is not a spell id in content/spells. Use the "
                f"Spells bench's id (summon-monster-1, not summon-monster-i).")

    out.extend(_requires_problems(at, e.get("requires")))
    if e.get("wielder") is not None:
        w = e["wielder"]
        if (not isinstance(w, dict) or w.get("alignment") not in ALIGNMENTS
                or not isinstance(w.get("negative_levels"), int)):
            say(f"{at}: wielder is {{\"alignment\": the wrong hand's alignment, "
                f"\"negative_levels\": 1}}.")
    out.extend(_choice_spec_problems(at, e.get("choice")))

    not_yet = e.get("not_yet")
    if not isinstance(not_yet, list) or not all(isinstance(x, str) and x.strip()
                                                for x in not_yet):
        say(f"{at}: not_yet is a list of sentences (empty when nothing waits).")
        not_yet = []
    waits = " ".join(not_yet).lower()
    docs = e.get("documents")
    if not isinstance(docs, list):
        say(f"{at}: documents is a list of effect documents.")
        docs = []
    if not docs:
        if not str(e.get("reads_tag") or "").strip() or not not_yet:
            say(f"{at}: has no documents, so its whole effect is a rule a reader asks of "
                f"its tag. Say which reader in \"reads_tag\" and what waits in "
                f"\"not_yet\": a property that does nothing must say so.")
    elif e.get("reads_tag"):
        say(f"{at}: reads_tag is for a property with no documents; this one has them.")

    spec = e.get("choice") if isinstance(e.get("choice"), dict) else {}
    choice_key = spec.get("key")
    used_choice = False
    for n, doc in enumerate(docs):
        where = f"{at} > document {n + 1}"
        if not isinstance(doc, dict):
            say(f"{where}: is not an object.")
            continue
        for nested in _walk_docs(doc):
            if nested.get("type") == "narrative":
                say(f"{where}: is narrative. Every book property works (owner, round 2): "
                    f"write it as a typed effect, or as a reads_tag rule with a not_yet.")
        out.extend(validate(doc, where))
        if doc.get("book") is not True:
            say(f"{where}: a printed number is marked \"book\": true, never scaled by "
                f"binding quality.")
        key = _choice_key(doc)
        if key:
            used_choice = True
            if key != choice_key:
                say(f"{where}: choice_key {key!r} is not this property's choice "
                    f"({choice_key or 'it has none'}).")
        if doc.get("when") is not None:
            out.extend(_when_problems(where, doc["when"], waits))
        if "bonus" in _safe_names(doc.get("amount")) and not scaled:
            say(f"{where}: its amount names bonus and the property is not scaled.")
    if choice_key and not used_choice:
        say(f"{at}: asks for a {choice_key} and no document uses it. A choice nothing "
            f"reads is a question with no consequence.")
    if scaled and not any("bonus" in _safe_names(d.get("amount"))
                          for d in docs if isinstance(d, dict)):
        say(f"{at}: is scaled and no document's amount is \"bonus\".")

    # Every way it can be bound must give documents that validate in full.
    if not out and docs:
        for pick in sample_choices(e):
            try:
                bound = bind(e, pick)
            except ValueError as exc:
                say(f"{at}: cannot be bound with {pick}: {exc}")
                break
            problems = [p for n, d in enumerate(bound)
                        for p in validate(d, f"{at} bound {pick} > document {n + 1}")]
            if problems:
                out.extend(problems)
                break

    if (e.get("requires") or {}).get("creator_alignment") or e.get("wielder"):
        if "alignment" not in waits:
            say(f"{at}: carries an alignment clause, and alignment is not tracked (owner, "
                f"round 4 Q7). Say in not_yet that nothing checks it.")
    house = e.get("house")
    if house is not None and (not isinstance(house, list)
                              or set(house) - {"cl", "values", "spells", "tier"}):
        say(f"{at}: house lists which of its numbers are not the book's: cl, values, "
            f"spells.")
    if house and not any(w in waits for w in ("house",)):
        say(f"{at}: names house numbers; say in not_yet why the book gives none.")

    aliases = e.get("aliases")
    if not isinstance(aliases, dict):
        say(f"{at}: aliases is {{old magic-items.json id: the choice it implies}}, {{}} "
            f"when there are none.")
    else:
        for old, choice in aliases.items():
            if not str(old).startswith("mi-"):
                say(f"{at}: alias {old} is not an old catalogue id (mi-...).")
            if not isinstance(choice, dict):
                say(f"{at}: alias {old} maps to a choice dict ({{}} for none).")
            elif choice:
                # An alias may leave the choice open (the old bane named no foe); what it
                # does name must be right.
                bad = [p for p in choice_problems(e, choice)
                       if "choose its" not in p and "bind it at" not in p]
                out.extend(f"{at}: alias {old}: {p}" for p in bad)
    if not str(e.get("source") or "").startswith("https://"):
        say(f"{at}: source is the page the numbers were read from (https://...), so the "
            f"next reader can check them.")
    if not str(e.get("text") or "").strip():
        say(f"{at}: needs a text, the line the card shows.")
    return out


def _safe_names(value) -> set[str]:
    if not isinstance(value, str):
        return set()
    try:
        return _formula_names(value)
    except BadFormula:
        return set()


def _walk_docs(doc: dict):
    yield doc
    for key in ("on_failure", "on_success", "effect", "effects", "options", "on_enter"):
        for nested in doc.get(key) or ():
            if isinstance(nested, dict):
                yield from _walk_docs(nested)


def _scaled_problems(at: str, scaled) -> list[str]:
    if not isinstance(scaled, dict):
        return [f"{at}: scaled is {{\"values\": [1, 2, 3, 4, 5], \"gp_per_square\": "
                f"2000}}."]
    out = []
    values = scaled.get("values")
    if (not isinstance(values, list) or not values
            or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0
                       for v in values)
            or values != sorted(set(values))):
        out.append(f"{at}: scaled.values is the bonuses it can be bound at, rising: "
                   f"[1, 2, 3, 4, 5].")
        values = []
    if not isinstance(scaled.get("gp_per_square"), int) or scaled["gp_per_square"] <= 0:
        out.append(f"{at}: scaled.gp_per_square is the book's multiplier (deflection 2000, "
                   f"resistance 1000, competence 100).")
    per = scaled.get("creator_cl_per_bonus")
    if per is not None and (not isinstance(per, int) or per <= 0):
        out.append(f"{at}: scaled.creator_cl_per_bonus is the book's 'at least N times "
                   f"the bonus'.")
    tiers = scaled.get("tiers")
    if tiers is not None and (not isinstance(tiers, list) or len(tiers) != len(values)
                              or set(tiers) - set(TIERS)):
        out.append(f"{at}: scaled.tiers gives a tier for each value, in order.")
    unknown = set(scaled) - {"values", "gp_per_square", "creator_cl_per_bonus", "tiers"}
    if unknown:
        out.append(f"{at}: scaled has no field {', '.join(sorted(unknown))}.")
    return out


def _requires_problems(at: str, req) -> list[str]:
    if not isinstance(req, dict):
        return [f"{at}: requires is an object ({{}} when it has none)."]
    from .tables import PHYSICAL_DAMAGE

    out = []
    for key, value in req.items():
        want = _REQUIRES.get(key)
        if want is None:
            out.append(f"{at}: requires has no clause {key!r}. Known: "
                       f"{', '.join(_REQUIRES)}.")
        elif want is int and (not isinstance(value, int) or isinstance(value, bool)):
            out.append(f"{at}: requires.{key} is a whole number.")
        elif want is not int and not isinstance(value, want):
            out.append(f"{at}: requires.{key} is a {want.__name__}.")
    dt = req.get("damage_types_any")
    if isinstance(dt, list) and (not dt or set(dt) - set(PHYSICAL_DAMAGE)):
        out.append(f"{at}: requires.damage_types_any names weapon damage types: "
                   f"{', '.join(PHYSICAL_DAMAGE)}.")
    if "creator_alignment" in req and req["creator_alignment"] not in ALIGNMENTS:
        out.append(f"{at}: requires.creator_alignment is one of {', '.join(ALIGNMENTS)}.")
    if req.get("melee") and req.get("ranged"):
        out.append(f"{at}: requires melee and ranged at once; no weapon is both.")
    return out


def _choice_spec_problems(at: str, spec) -> list[str]:
    if spec is None:
        return []
    if (not isinstance(spec, dict)
            or not re.fullmatch(r"[a-z][a-z_]*", str(spec.get("key") or ""))
            or spec.get("of") not in CHOICE_OF):
        return [f"{at}: choice is {{\"key\": \"foe\", \"of\": one of "
                f"{', '.join(CHOICE_OF)}, \"options\": [...]}}."]
    if spec["key"] == "bonus":
        return [f"{at}: \"bonus\" is the scaled value's key; name the choice something "
                f"else."]
    unknown = set(spec) - {"key", "of", "options"}
    if unknown:
        return [f"{at}: choice has no field {', '.join(sorted(unknown))}."]
    options = spec.get("options")
    if spec["of"] in ("creature_type", "damage_type") and not options:
        return [f"{at}: a {spec['of'].replace('_', ' ')} choice lists its options."]
    if options is not None:
        vocab = (set(CREATURE_TYPES) if spec["of"] == "creature_type"
                 else {o["id"] for o in VOCAB["damage_type"]}
                 if spec["of"] == "damage_type" else set(SKILLS))
        bad = [o for o in options if o not in vocab]
        if bad:
            return [f"{at}: {', '.join(map(str, bad))} cannot be a "
                    f"{spec['of'].replace('_', ' ')}."]
    return []


def _when_problems(where: str, when, waits: str) -> list[str]:
    if (not isinstance(when, dict) or set(when) - {"target"}
            or not isinstance(when.get("target"), dict) or not when["target"]):
        return [f"{where}: a property's when is {{\"target\": {{...}}}}: the creature "
                f"struck, by type, subtype, alignment or the property's choice."]
    out = []
    target = when["target"]
    unknown = set(target) - set(_WHEN_TARGET_KEYS)
    if unknown:
        out.append(f"{where}: when.target has no key {', '.join(sorted(unknown))}. Known: "
                   f"{', '.join(_WHEN_TARGET_KEYS)}.")
    if "type" in target:
        types = target["type"] if isinstance(target["type"], list) else [target["type"]]
        bad = [t for t in types if t not in CREATURE_TYPES]
        if bad:
            out.append(f"{where}: {', '.join(map(str, bad))} is not a creature type.")
    if "alignment" in target and target["alignment"] not in ALIGNMENTS:
        out.append(f"{where}: when.target.alignment is one of {', '.join(ALIGNMENTS)}.")
    for key, why in WHEN_NOT_READ.items():
        if key in target and key not in waits:
            out.append(f"{where}: asks {why}, so the term applies to nobody. Say so in "
                       f"not_yet (mention {key}).")
    return out
