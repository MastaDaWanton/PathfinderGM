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
from .tables import (
    ABILITY_FULL, ARMOUR, CONDITIONS, DC_BANDS, ENERGY_DAMAGE, PHYSICAL_DAMAGE, SAVES,
    SKILLS,
)

# --- the vocabularies a dropdown can be filled from ---------------------------------------
#
# Named rather than inlined so two types that pick from the same list cannot drift apart,
# and so the editor fetches one catalogue instead of a form per type.

VOCAB: dict[str, list[dict]] = {
    "ability": [{"id": k, "name": v} for k, v in ABILITY_FULL.items()],
    "skill": [{"id": k, "name": k.title()} for k in sorted(SKILLS)],
    "save": [{"id": k, "name": v} for k, v in SAVES.items()],
    "condition": [{"id": k, "name": v.get("name", k.title())}
                  for k, v in sorted(CONDITIONS.items())],
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
        "alchemical", "armour", "circumstance", "competence", "deflection", "dodge",
        "enhancement", "inherent", "insight", "luck", "morale", "natural armour",
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
        ("hp_max", "Maximum hit points"))],
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
        ("on_expiry", "When it ends"))],

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
        "hostile", "unfriendly", "indifferent", "friendly", "helpful")],

    "side": [{"id": k, "name": n} for k, n in (
        ("caster", "The caster"), ("target", "The target"),
        ("nobody", "Nobody — it acts on its own"))],
    # A yes/no that is a dropdown rather than a checkbox, because the generated form
    # renders `choice` and has no widget for a boolean. Two entries beat a text box that
    # accepts "true", "y", "Yes" and "1" and means something different for each.
    "yes_no": [{"id": "no", "name": "No"}, {"id": "yes", "name": "Yes"}],
}


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
            ], engine=False,
                blocked="Recorded on the creature and shown to the GM. No check in the "
                        "app consults an attitude yet — Diplomacy is rolled against a DC "
                        "the GM sets, not against a track."),
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
            EffectType("spell_resistance", "Spell resistance", "SR 12 + caster level", [
                Field("amount", "Rating", "signed_formula",
                      hint="A number, or a formula: 12 + caster_level."),
            ], engine=False,
                blocked="Recorded on the sheet and shown to the GM. `_op_cast` rolls no "
                        "check to overcome spell resistance — no creature in the app "
                        "carries a rating for it to check against, and half a check "
                        "would be worse than none. docs/spells.md §5.1."),
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
        ]),

    Category(
        "capability", "Capability",
        "Something the character can now do — a sense, a speed, or a rule relaxed.",
        [
            # Both of these claimed the engine ran them and it never has. `_spec_to_intents`
            # returns nothing for either, and no check in the app asks whether an actor can
            # see in the dark — so a potion of darkvision was drunk and did nothing, with
            # no error to say why. The engine flag now matches the code.
            EffectType("sense", "Sense", "Low-light vision for 1 hour", [
                Field("target", "Sense", "choice", vocab="sense"),
                Field("range", "Range in feet", "int", required=False),
            ], engine=False,
                blocked="Recorded and shown to the GM. Nothing in the engine asks what a "
                        "creature can see yet, so light and concealment are narrated."),
            EffectType("speed", "Movement", "+20 ft land speed for 1 round", [
                Field("target", "Mode", "choice", vocab="movement", default="land"),
                Field("amount", "Feet", "signed"),
            ], engine=False,
                blocked="Recorded and shown to the GM. The grid reads the creature's own "
                        "speed; nothing applies a temporary change to it yet."),
            EffectType(
                "permission", "Permission", "May feint as a swift action",
                [Field("target", "What it allows", "text")],
                engine=False,
                blocked="Permissions relax a named legality check. The registry of checks "
                        "is specified in docs/homebrew-rules.md §4.5 and not built yet."),
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
    for f in etype.fields + COMMON:
        value = spec.get(f.id)
        missing = value is None or (isinstance(value, str) and not value.strip())
        if missing:
            if f.required:
                problems.append(f"{path}: {etype.name} needs {f.label.lower()}.")
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
    trigger = str(spec.get("trigger") or "on_cast")
    if trigger not in ("on_cast", "") and not inherits_window \
            and not _lasts(spec.get("duration")):
        problems.append(
            f"{path}: '{_vocab_name('trigger', trigger)}' needs a duration — without one "
            f"there is no window for it to fire in and it would never happen.")

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
    """Whether the engine can resolve this today."""
    found = find(str(spec.get("type", "")))
    return bool(found and found[1].engine)


# --- rendering ------------------------------------------------------------------------------

def render(spec: dict) -> str:
    """One authored effect as the line a card shows.

    Deliberately the same voice as `rules/effects.py` produces from prose, so an item
    whose effects were authored and one whose effects were read out of a description look
    the same on a card. The player should not be able to tell which is which.
    """
    found = find(str(spec.get("type", "")))
    if found is None:
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
    elif t == "temp_hp":
        body = f"{dice} temporary hit points"
    elif t == "fast_healing":
        body = f"Fast healing {amount}"
    elif t == "bleed":
        body = f"Bleed {amount} per round"
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
    else:
        body = str(target or spec.get("note") or etype.name)
        body = body[:1].upper() + body[1:]

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
