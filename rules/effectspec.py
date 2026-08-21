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
    "damage_type": [{"id": d, "name": d.title()} for d in
                    tuple(PHYSICAL_DAMAGE) + tuple(ENERGY_DAMAGE) + ("untyped",)],
    "bonus_type": [{"id": b, "name": b.title()} for b in (
        "alchemical", "circumstance", "competence", "deflection", "dodge", "enhancement",
        "inherent", "insight", "luck", "morale", "natural armour", "profane", "racial",
        "resistance", "sacred", "shield", "size", "untyped")],
    "combat_target": [{"id": k, "name": n} for k, n in (
        ("attack", "Attack rolls"), ("damage", "Damage rolls"), ("ac", "Armour class"),
        ("touch_ac", "Touch AC"), ("cmb", "CMB"), ("cmd", "CMD"),
        ("initiative", "Initiative"), ("caster_level", "Caster level checks"),
        ("spell_resistance", "Checks to overcome SR"))],
    "sense": [{"id": k, "name": n} for k, n in (
        ("low_light", "Low-light vision"), ("darkvision", "Darkvision"),
        ("scent", "Scent"), ("tremorsense", "Tremorsense"),
        ("see_invisible", "See invisible"), ("blindsense", "Blindsense"),
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
}


@dataclass
class Field:
    """One input on the generated form."""
    id: str
    label: str
    kind: str                       # int | signed | dice | choice | text | duration
                                    #  | effects | bool | formula
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
COMMON = [
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
        Field("amount", "Amount", "signed", hint="+2, -4."),
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
        ]),

    Category(
        "defence", "Defence", "Reducing or refusing damage rather than restoring it.",
        [
            EffectType("resistance", "Energy resistance", "Resist fire 10", [
                Field("target", "Against", "choice", vocab="damage_type"),
                Field("amount", "Points", "int"),
            ]),
            EffectType("damage_reduction", "Damage reduction", "DR 3/— for 8 hours", [
                Field("amount", "Points", "int"),
                Field("bypass", "Bypassed by", "text", required=False,
                      hint="silver, cold iron. Empty for DR/—, which nothing bypasses."),
            ]),
            EffectType("immunity", "Immunity", "Immune to fire for 2 hours", [
                Field("target", "To what", "text",
                      hint="fire damage, poison, gaze attacks."),
            ]),
        ]),

    Category(
        "capability", "Capability",
        "Something the character can now do — a sense, a speed, or a rule relaxed.",
        [
            EffectType("sense", "Sense", "Low-light vision for 1 hour", [
                Field("target", "Sense", "choice", vocab="sense"),
                Field("range", "Range in feet", "int", required=False),
            ]),
            EffectType("speed", "Movement", "+20 ft land speed for 1 round", [
                Field("target", "Mode", "choice", vocab="movement", default="land"),
                Field("amount", "Feet", "signed"),
            ]),
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
                          hint="Free text for now — there is no spell list to pick from."),
                    Field("caster_level", "Caster level", "int", required=False),
                    Field("save_dc", "Save DC", "int", required=False),
                ],
                engine=False,
                blocked="The engine has no spell system, so this is recorded and "
                        "narrated. Nothing will cast it."),
        ]),

    Category(
        "gate", "Save or condition gate",
        "A fork: roll a save, and what happens depends on the result. The branches hold "
        "effects of any other kind, nested as deep as the effect needs.",
        [
            EffectType("save_gate", "Saving throw",
                       "Fortitude DC 18; on a failure 1d6 Con, on a success half", [
                Field("target", "Save", "choice", vocab="save"),
                Field("dc", "DC", "formula",
                      hint="A number, or a formula: 10 + level/2 + con_mod."),
                Field("on_failure", "If they fail", "effects", required=False),
                Field("on_success", "If they save", "effects", required=False),
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


# --- validation ---------------------------------------------------------------------------

def validate(spec: dict, path: str = "effect") -> list[str]:
    """Everything wrong with one authored effect, named.

    Returned as a list rather than raised, because the editor shows all of a form's
    problems at once and a builder that reports them one at a time is a builder nobody
    finishes a complex effect in.
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
        elif f.kind == "dice":
            if not _is_dice(str(value)):
                problems.append(
                    f"{path}: {value!r} is not dice. Write 1d4, 2d6+2 or a number.")
        elif f.kind == "effects":
            for i, nested in enumerate(value or []):
                problems.extend(validate(nested, f"{path} > {f.label.lower()} {i + 1}"))

    if spec.get("uses") not in (None, "", "unlimited") and not spec.get("uses_count"):
        problems.append(f"{path}: a use limit needs a count.")
    return problems


def _is_dice(s: str) -> bool:
    import re

    return bool(re.fullmatch(r"\s*\d*\s*d\s*\d+\s*(?:[+-]\s*\d+)?\s*|\s*\d+\s*", s, re.I))


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
        sign = f"{int(amount):+d}" if amount is not None else "?"
        body = f"{sign} {_label(etype, target)}"
    elif t == "heal":
        body = f"Heals {dice} hit points"
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
        body = f"Resist {target} {amount}"
    elif t == "damage_reduction":
        body = f"DR {amount}/{spec.get('bypass') or '—'}"
    elif t == "immunity":
        body = f"Immune to {target}"
    elif t == "sense":
        rng = f" {spec['range']} ft" if spec.get("range") else ""
        body = f"{_label(etype, target)}{rng}"
    elif t == "speed":
        body = f"{int(amount):+d} ft {_label(etype, target).lower()}"
    elif t == "spell_effect":
        cl = f", caster level {spec['caster_level']}" if spec.get("caster_level") else ""
        body = f"Acts as {target}{cl}"
    elif t == "save_gate":
        save = _label(etype, target)
        parts = [f"{save} DC {spec.get('dc', '?')}"]
        fail = [render(e) for e in spec.get("on_failure") or []]
        ok = [render(e) for e in spec.get("on_success") or []]
        if fail:
            parts.append("fail: " + ", ".join(fail))
        if ok:
            parts.append("save: " + ", ".join(ok))
        body = " · ".join(parts)
    else:
        body = str(target or spec.get("note") or etype.name)

    if dur:
        body += f" for {dur}"
    limit = _uses(spec)
    if limit:
        body += f" ({limit})"
    return body


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
