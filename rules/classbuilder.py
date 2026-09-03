"""Everything a character class is, named — and the checks that keep an authored one honest.

Blood Bending is the high-water mark: it uses a BAB progression, two hit dice per level,
one derived save track, one save column typed out in full, a twenty-row level table with
two damage columns nobody else prints, three engine rule switches, permanent ability
growth, five resource pools, verbatim feature text, and four paths whose abilities gate on
a tier track and carry executable effect specs. Nothing about it is special-cased in the
engine — every one of those is a field some module reads. This file is the list of those
fields, written down once, so that a user can author all of it and a simpler class can skip
every part of it.

**The classification is the deliverable.** `CLASS_SCHEMA` names every key, says what type
it is, says which engine mechanism consumes it, and says whether it is advanced — so a form
can be generated from it and a "simple martial class" never has to look at pools, paths or
overrides. Where a key exists in the shipped data and *nothing* reads it, it is still named
here and marked `consumer=""`, because a field the app silently ignores is exactly the
thing an author needs told (see `docs/class-creation.md` §"Recorded but unread").

**Validation is mechanical, and every message says the fix.** That is CLAUDE.md's rule for
model output and it is the same rule here: find the defect in code — a set comparison, a
regex, a formula parse — and report it as an instruction, not a complaint. A validator that
says "invalid path" is a validator whose messages get ignored.

Two things the class layer adds on top of `rules/effectspec.py`, which is why effects go
through `validate_effect` here rather than straight to `effectspec.validate`:

- **Derived values.** `dice_from` reads a die off the class's own level table, `formula` is
  evaluated against the sheet, and `scales_by: control_blood` picks a rung by tier. All
  three fill in a field `effectspec` requires, at resolve time rather than at author time
  (`rules/leveling.py:resolve_effect`).
- **`engine_op`.** Two ops exist that are not effects at all — they move blood pools around
  the scene. `rules/engine.py:_op_use_ability` executes them by name.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

from . import classes as classes_mod, effectspec, resources
from .registry import Field
from .sheet import ACTOR_RULES
from .tables import ABILITIES, SAVES, SKILLS, WEAPONS

MAX_LEVEL = 20
# Path tiers run 1-5 because the two Control Blood tracks the level table can carry run
# 1a-5a and 1b-5b. A sixth tier is not a bigger class, it is an ability nothing can ever
# reach — see `rules/leveling.py:control_blood`.
MAX_TIER = 5

# The literal phrase `rules/leveling.py:control_blood` matches on the level table to work
# out how far along a path a character is. It is the one class-specific string left in an
# otherwise class-agnostic engine, and a homebrew path class has to use it verbatim or its
# abilities never unlock. Named here so the validator can say so, and see the integration
# note in docs/class-creation.md.
TRACK_PHRASE = "control blood"
_TRACK_GRANT = re.compile(r"control blood\s*(\d+)\s*([ab])", re.I)

# What `rules/engine.py:_op_use_ability` can execute that is not an effectspec type.
ENGINE_OPS = {
    "blood_pool": "Leaves a pool of blood in the scene, under whoever it came out of.",
    "spend_pools": "Takes pools back off the ground. `count` is a number or \"all\".",
}

# `rules/casting.py:PROGRESSIONS`, named without importing it — casting pulls in the spell
# tables, and the schema is read on every page load of the builder. Checked against the
# real dict in `validate_class`, so this list cannot go stale silently.
CASTING_PROGRESSIONS = ("full", "spontaneous_full", "six_level", "four_level")


# --- the field vocabulary -------------------------------------------------------------------

@dataclass
class ClassField(Field):
    """One authored field of a class.

    `registry.Field` already carries name, label, type, choices, help and required — the
    same five a generated form needs — so this extends it rather than restating it, and a
    `Kind` can take these straight (see `registry_fields()`).

    What it adds is the part a *class* needs and a flat content editor does not:

    - `consumer`: which module actually reads the value. Empty means nothing does, which is
      a fact an author is owed rather than one to hide.
    - `advanced`: true for machinery a simple class should never be shown. The whole point
      of the exercise is that a fighter-shaped class does not fill in a pool formula.
    - `of`: the fields of one row, for the repeating structures — a level, a pool, a path.
    - `key_label` / `value_label`: for a map field, what the two halves are called.
    """
    consumer: str = ""
    advanced: bool = False
    of: tuple = ()
    key_label: str = ""
    value_label: str = ""
    example: str = ""

    def as_dict(self) -> dict:
        d = super().as_dict()
        d.update({"consumer": self.consumer, "advanced": self.advanced,
                  "example": self.example})
        if self.of:
            d["of"] = [f.as_dict() for f in self.of]
        if self.key_label:
            d["key_label"] = self.key_label
        if self.value_label:
            d["value_label"] = self.value_label
        return d


@dataclass
class Section:
    """A block of the form, and the one sentence that says whether you need it at all."""
    id: str
    title: str
    blurb: str
    fields: list[ClassField] = dc_field(default_factory=list)
    advanced: bool = False

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "blurb": self.blurb,
                "advanced": self.advanced,
                "fields": [f.as_dict() for f in self.fields]}


SAVE_KEYS = tuple(SAVES)                    # fort, ref, will
BAB_CHOICES = tuple(classes_mod.BAB)        # full, three_quarter, half
SAVE_TRACKS = tuple(classes_mod.SAVE_TRACKS)
REFRESH_CHOICES = tuple(resources.REFRESH)
RULE_CHOICES = tuple(sorted(ACTOR_RULES))
# `simple` and `martial` are the groups `Actor.is_proficient` compares a weapon's own
# `prof` against; anything else has to be a weapon by name. `unarmed` is a weapon.
PROFICIENCY_GROUPS = ("simple", "martial", "exotic")

# --- one row of each repeating structure ------------------------------------------------

LEVEL_ROW = (
    ClassField("level", "Level", type="number", required=True,
               consumer="rules/classes.py:table_at, features_at",
               help="1 to 20. One row per level, with no gaps — a level with no row "
                    "prints no dice and grants nothing."),
    ClassField("grants", "What this level grants", type="list",
               consumer="rules/classes.py:features_at → the sheet's class features, the "
                        "class tab's table, and the glossary popover",
               help="Names, not sentences: 'bonus feat', 'evasion'. A name the glossary "
                    "knows answers a click; one it does not says so honestly.",
               example="bonus feat, evasion, control blood 1a"),
    # Not a fixed field: any other key on the row is a die column, read by name.
    ClassField("_columns", "Die columns", type="map", key_label="Column",
               value_label="Dice at this level",
               consumer="rules/leveling.py:table_die, and every effect with `dice_from`",
               help="A monk's Fist, a Blood Bender's Blood. Any name you like — the class "
                    "tab draws whatever columns it finds, and an effect can multiply one.",
               example="fist 1d6 · blood 1d8"),
)

OVERRIDE_ROW = (
    ClassField("rule", "Rule", type="choice", choices=RULE_CHOICES, required=True,
               consumer="rules/classes.py:overrides_for → Actor.overrides → "
                        "Actor.allows() in rules/sheet.py and rules/survival.py",
               help="One of the six named rules the engine asks about. A misspelling is "
                    "collected and reported rather than granted, because a feature that "
                    "silently never happens is the worst kind."),
    ClassField("from_level", "From level", type="number",
               consumer="rules/classes.py:overrides_for", help="Default 1."),
    ClassField("value", "On", type="bool",
               consumer="rules/classes.py:overrides_for",
               help="Almost always true. False switches a rule off for this class."),
    ClassField("why", "Why", type="textarea", consumer="",
               help="Not read by the engine. It is read by the next person, and by you in "
                    "six months."),
)

GROWTH_ROW = (
    ClassField("ability", "Ability", type="choice", choices=ABILITIES, required=True,
               consumer="rules/leveling.py:level_up"),
    ClassField("every", "Every N levels", type="number", required=True,
               consumer="rules/leveling.py:level_up",
               help="Fires on the multiples: every 5 means 5th, 10th, 15th, 20th."),
    ClassField("amount", "Points", type="number", required=True,
               consumer="rules/leveling.py:level_up",
               help="Added to the base score permanently, so it survives every recompute."),
    ClassField("why", "Why", type="textarea", consumer=""),
)

POOL_ROW = (
    ClassField("id", "Pool name", required=True,
               consumer="rules/classes.py:pools_for → rules/resources.py:define",
               help="What the sheet calls it: ki, rage, stunning strike."),
    ClassField("from_level", "From level", type="number",
               consumer="rules/classes.py:pools_for",
               help="Default 1. The pool is created once the character reaches it."),
    ClassField("max", "Maximum", type="formula", required=True,
               consumer="rules/resources.py:evaluate",
               help="A formula over the sheet, recomputed on every level-up: level, "
                    "hit_dice, bab, hp_max, con_mod, control_blood, floor(), min(), max().",
               example="floor(level/2) + con_mod"),
    ClassField("starts", "Starts at", consumer="rules/resources.py:define",
               help="'max', or a number.", example="max"),
    ClassField("refresh", "Refreshes on", type="choice", choices=REFRESH_CHOICES,
               consumer="rules/resources.py:Pool.refresh"),
    ClassField("scope", "Sits on", type="choice", choices=("self", "target"),
               advanced=True, consumer="rules/resources.py:define",
               help="'target' is a pool that lives on the enemy — blood stacks are "
                    "applied by one ability and spent by four others."),
    ClassField("cap", "Capped", type="choice", choices=("yes", "none"), advanced=True,
               consumer="rules/resources.py:define",
               help="'none' for a resource with no ceiling, which two Blood Bending paths "
                    "declare in as many words."),
    ClassField("cooldown", "Cooldown", type="dice", advanced=True,
               consumer="rules/resources.py:Pool.cooldown_dice",
               help="Rounds before it can be used again. Rolled, not fixed: 1d3."),
    ClassField("upkeep", "Upkeep", type="object", advanced=True,
               consumer="rules/resources.py:Pool.upkeep_amount",
               help="Paid every round or the thing it sustains ends.",
               of=(ClassField("amount", "Amount", type="dice"),
                   ClassField("resource", "Paid in", type="text"))),
    ClassField("source", "Source", advanced=True, consumer="rules/resources.py:define",
               help="Defaults to the class name."),
)

CASTING_FIELDS = (
    ClassField("ability", "Casting ability", type="choice", choices=ABILITIES,
               required=True, consumer="rules/casting.py:casting_ability, save_dc"),
    ClassField("kind", "Prepared or spontaneous", type="choice",
               choices=("prepared", "spontaneous"), required=True,
               consumer="rules/casting.py — documentation of the difference; "
                        "`prepare_from` is what the engine branches on"),
    ClassField("progression", "Slot progression", type="choice",
               choices=CASTING_PROGRESSIONS, required=True,
               consumer="rules/casting.py:slots_for, highest_spell_level"),
    ClassField("list", "Spell list", required=True,
               consumer="rules/casting.py:level_on_list",
               help="Which printed list this class casts off: wizard, cleric, druid, "
                    "sorcerer, bard, paladin, ranger. A list of your own has no spells on "
                    "it, so nothing would be castable."),
    ClassField("prepare_from", "Draws spells from", type="choice",
               choices=("spellbook", "list", "known"), required=True,
               consumer="rules/casting.py:knows",
               help="'spellbook' and 'known' both read the character's own spellbook; "
                    "'list' means the whole class list is available every morning."),
    ClassField("note", "Note", type="textarea", consumer=""),
)

PATH_FIELDS = (
    ClassField("name", "Path name", required=True,
               consumer="rules/sheet.py:_progression → the Class tab",
               help="The display name. The *key* it is filed under is what the character "
                    "sheet stores, and must be lower case."),
    ClassField("role", "Role", consumer="the Class tab",
               help="Tank, DPS, Sustain. One word for what the branch is for.",
               example="Tank"),
    ClassField("summary", "Summary", type="textarea", consumer="the Class tab"),
    ClassField("global_rule", "Global rule", type="textarea", consumer="the Class tab",
               help="One sentence that governs the whole path — 'there is no limit on the "
                    "number of stacks you can apply'."),
    ClassField("tiers", "Abilities by tier", type="tiers", required=True,
               consumer="rules/leveling.py:find_ability, tier_needed, has_passive; "
                        "play/views.py:_usable_abilities",
               help="Tier 1 to 5. A character may use an ability at or below the tier "
                    "they have reached on this path, and not one above it.",
               of=(ClassField("tier", "Tier", type="number"),
                   ClassField("names", "Abilities", type="list"))),
    ClassField("abilities", "Ability text", type="map", key_label="Ability",
               value_label="What it does, in words", required=True,
               consumer="the Class tab, the ability buttons, rules/glossary.py",
               help="The rules text, verbatim. Keyed by the *resolved* name, so five "
                    "level-scaled variants share one paragraph."),
    ClassField("resolves", "Variant → ability", type="map", key_label="As listed on a tier",
               value_label="The ability it is", required=True,
               consumer="rules/leveling.py:find_ability; play/views.py:_usable_abilities",
               help="'Iron Clot (DR 8/-)' resolves to 'Iron Clot'. Every name on a tier "
                    "needs an entry here — or to be listed under Core — or it shows no "
                    "text and runs no effects.",
               example="Iron Clot (DR 8/-) → Iron Clot"),
    ClassField("effects", "Executable effects", type="effects_map",
               key_label="Ability", advanced=True,
               consumer="rules/leveling.py:resolve_effect → "
                        "rules/engine.py:_op_use_ability",
               help="Keyed by the resolved ability name. Anything the engine cannot "
                    "execute is reported as narrated rather than silently dropped."),
    ClassField("passive", "Always active", type="list", advanced=True,
               consumer="rules/leveling.py:is_passive, has_passive; "
                        "play/views.py:_usable_abilities",
               help="A passive is never used — it simply happens. Listing it here keeps "
                    "it off the ability bar, where clicking it swallowed the attack it "
                    "existed to modify."),
    ClassField("toggles", "Toggles", type="map", key_label="Ability",
               value_label="Condition it sets", advanced=True,
               consumer="rules/leveling.py:toggle_key → rules/engine.py:_op_use_ability",
               help="A standing state with no clock. The condition name shows wherever "
                    "conditions do, so the player can see whether it still holds.",
               example="Extracorporeal Blood Armament → blood armament"),
    ClassField("grants", "Ability documents", type="map", key_label="Ability",
               value_label="Its document", advanced=True,
               consumer="rules/leveling.py:ability_doc → "
                        "rules/engine.py:_op_use_ability",
               help="The full grammar for an ability, keyed by the resolved name: "
                    "requirements as tag queries (requires / requires_not), a pool "
                    "cost and per-round drain, granted tags, source-tracked modifiers "
                    "(scaled by tier if by_tier says so), temporary hit points per "
                    "Hit Die, a granted weapon, and the tells. An ability with "
                    "standing parts must also be a toggle, or nothing could ever "
                    "remove it."),
    ClassField("upgrades", "Upgrades", type="map", key_label="Upgraded name",
               value_label="What the upgrade changes", advanced=True,
               consumer="the Class tab",
               help="'Greater Blood Rage' — the tier-listed name, and what it improves."),
    ClassField("core", "Core Rulebook abilities", type="list", advanced=True,
               consumer="the Class tab",
               help="A name on a tier that the Core Rulebook already defines — Uncanny "
                    "Dodge. Listing it here is how the tab knows to say 'see the rules "
                    "reference' rather than 'the source does not describe it'."),
    ClassField("needs", "Known gaps", type="map", key_label="Ability",
               value_label="What the engine still lacks", advanced=True, consumer="",
               help="Provenance, not mechanics. Nothing reads it; it is the honest record "
                    "of which abilities are waiting on an engine capability."),
    ClassField("undescribed", "Undescribed", type="list", advanced=True, consumer="",
               help="Written by the importer, read by nothing. Kept so a converted class "
                    "round-trips without losing a key."),
    ClassField("effects_converted", "Effects were machine-converted", type="bool",
               advanced=True, consumer="",
               help="Provenance. True means nobody has read the converted effects yet."),
)


# --- the classification ---------------------------------------------------------------------

CLASS_SCHEMA: list[Section] = [
    Section(
        "identity", "Identity",
        "Who the class is. Everything here is required except the notes.",
        [
            ClassField("id", "Id", required=True,
                       consumer="rules/classes.py:all_classes — the key everything else "
                                "resolves by, and the filename it is saved under",
                       help="Lower case, and permanent: a character sheet stores this "
                            "string, so renaming it orphans every character of the class.",
                       example="storm caller"),
            ClassField("name", "Name", required=True,
                       consumer="every page that shows a class",
                       help="As it is printed. Capitals and punctuation are yours; only "
                            "the id has to be plain.",
                       example="Storm Caller"),
            ClassField("summary", "Summary", type="textarea",
                       consumer="rules/creation.py:options → the creation forge card; "
                                "the Class tab",
                       help="One or two sentences. This is what a player reads when "
                            "choosing."),
            ClassField("source", "Source", consumer="",
                       help="Where it came from. Nothing reads it; it exists so a "
                            "converted class says whose it was."),
            ClassField("alignment", "Alignment", consumer="",
                       help="Recorded only. The character sheet has no alignment field, "
                            "so nothing enforces this today.",
                       example="any"),
        ]),

    Section(
        "numbers", "The numbers",
        "Hit dice, attack, saves and skills — the four tables that make it a 1e class "
        "rather than a world class.",
        [
            ClassField("hit_die", "Hit die", type="dice", required=True,
                       consumer="rules/creation.py:max_hit_die → first-level hit points; "
                                "rules/leveling.py:level_up rolls it every level after",
                       help="A number (8) or notation (2d8). Notation is why this is not "
                            "an integer field: Blood Bending rolls two dice a level.",
                       example="10"),
            ClassField("hit_dice_per_level", "Hit dice per level", type="number",
                       advanced=True,
                       consumer="rules/classes.py:apply → Actor.hit_dice",
                       help="Almost always 1, and left out entirely means 1. Two changes "
                            "every 'per Hit Die' number in the game for this class.",
                       example="1"),
            ClassField("bab", "Base attack bonus", type="choice", choices=BAB_CHOICES,
                       required=True,
                       consumer="rules/tables.py:bab_for → Actor.bab, and every attack",
                       help="full is +1 a level, three_quarter is the rogue's, half the "
                            "wizard's."),
            ClassField("good_saves", "Good saves", type="list", choices=SAVE_KEYS,
                       required=True,
                       consumer="rules/tables.py:save_for via rules/sheet.py, and "
                                "rules/leveling.py:gains_at",
                       help="The saves that use the good progression. Leave a save out "
                            "and it uses the poor one.",
                       example="fort, ref"),
            ClassField("saves", "Save columns", type="map", advanced=True,
                       key_label="Save", value_label="Track name or twenty numbers",
                       consumer="rules/classes.py:save_base",
                       help="Only for a class whose saves are not simply good or poor. A "
                            "named track (good, good_plus_1, good_minus_1, poor) is "
                            "derived and cannot arrive mistyped; twenty integers are for "
                            "a printed column that is not regular, where deriving the "
                            "number would mean inventing one.",
                       example="fort → good_plus_1"),
            ClassField("skill_ranks", "Skill ranks per level", type="number",
                       required=True,
                       consumer="rules/creation.py:build and rules/leveling.py:gains_at",
                       help="Before Intelligence. 2, 4, 6 or 8.",
                       example="4"),
            ClassField("class_skills", "Class skills", type="list", choices=tuple(sorted(SKILLS)),
                       consumer="rules/sheet.py — the +3 trained bonus",
                       help="A skill not on this list still takes ranks; it just misses "
                            "the class bonus."),
            ClassField("proficiencies", "Proficiencies", type="list",
                       consumer="rules/sheet.py:is_proficient → the -4 for using "
                                "something you are not trained with",
                       help="Groups (simple, martial, exotic) or single weapons by name.",
                       example="simple, martial"),
            ClassField("starting_wealth", "Starting wealth", consumer="",
                       help="Recorded only — nothing in the app rolls starting gold yet, "
                            "and a character is created with a kit rather than a purse.",
                       example="3d6 x 10 gp"),
        ]),

    Section(
        "table", "The level table",
        "Twenty rows: what each level grants, and any dice the class prints in a column "
        "of its own.",
        [
            ClassField("levels", "Levels", type="table", required=True, of=LEVEL_ROW,
                       consumer="rules/classes.py:features_at, table_at; "
                                "rules/leveling.py:preview, table_die",
                       help="A row per level. Grants may be empty, but the row should "
                            "exist — a missing row prints no die columns for that level."),
        ]),

    Section(
        "features", "Features in full",
        "The paragraphs behind the names on the table. A name with text here answers a "
        "click on the sheet; one without says the source does not define it.",
        [
            ClassField("features", "Feature text", type="map", key_label="Feature",
                       value_label="The rules text, verbatim",
                       consumer="rules/glossary.py:build → the sheet's popover",
                       help="Verbatim. A stored text always beats a paraphrase, and this "
                            "is where a class's central rule — Blood Bond — actually "
                            "lives."),
        ]),

    Section(
        "rules", "Rules this class does not play by",
        "Named switches the engine asks about. Six exist; a class may claim any of them "
        "from any level.",
        [
            ClassField("overrides", "Overrides", type="group", of=OVERRIDE_ROW,
                       advanced=True,
                       consumer="rules/classes.py:overrides_for → Actor.allows()",
                       help="Only the six rules listed are real. An unknown one is "
                            "collected and reported, never granted."),
            ClassField("ability_growth", "Permanent ability growth", type="group",
                       of=GROWTH_ROW, advanced=True,
                       consumer="rules/leveling.py:level_up",
                       help="'+2 Constitution every 5 levels'. Applied to the base score, "
                            "so it survives every recompute."),
        ], advanced=True),

    Section(
        "resources", "Pools",
        "Anything the class spends: ki, rage rounds, uses per day, stacks left on an "
        "enemy. A maximum is a formula, so it follows a level-up on its own.",
        [
            ClassField("pools", "Pools", type="group", of=POOL_ROW, advanced=True,
                       consumer="rules/classes.py:pools_for → rules/resources.py:define",
                       help="Created when the character reaches `from_level`, and "
                            "recomputed on every load — a formula corrected in a later "
                            "build reaches characters already in play."),
        ], advanced=True),

    Section(
        "casting", "Spellcasting",
        "Fill this in and the class casts: slots become ordinary pools, caster level and "
        "save DCs are computed, and the spell tab appears. Leave it out and it does not.",
        [
            # `object`, not `group`: one casting block, not a list of them. The difference
            # is what the generated form draws — a card, or a card with an Add button.
            ClassField("casting", "Casting", type="object", of=CASTING_FIELDS,
                       advanced=True,
                       consumer="rules/casting.py:caster_data — read off the class file, "
                                "so a homebrew caster needs no edit to the engine",
                       help="What a spell *does* is still its prose. The engine computes "
                            "the slots, the caster level and the DC and hands the rest to "
                            "the GM."),
        ], advanced=True),

    Section(
        "paths", "Paths",
        "Branches the character chooses between, each with abilities tiered 1-5. This is "
        "the biggest piece of machinery a class can have and the one most classes should "
        "leave empty.",
        [
            ClassField("paths", "Paths", type="paths", of=PATH_FIELDS, advanced=True,
                       consumer="rules/leveling.py:paths_for, path_detail, find_ability; "
                                "rules/creation.py:build; play/views.py:_usable_abilities",
                       key_label="Path id (lower case)",
                       help="Keyed by a lower-case id — the sheet stores that string, and "
                            "a key with a capital in it is a path the engine can never "
                            "find."),
            ClassField("max_paths", "Paths at once", type="number", advanced=True,
                       consumer="rules/leveling.py:max_paths → "
                                "rules/creation.py:check_paths",
                       help="Left out, it is counted from the tracks the level table "
                            "grants: one for the a-track, two if there is a b-track."),
        ], advanced=True),
]


def schema() -> list[dict]:
    """The whole classification as JSON, for a page that generates its form from it."""
    return [s.as_dict() for s in CLASS_SCHEMA]


def registry_fields() -> tuple:
    """Every top-level field, flat, for `registry.Kind(fields=...)`.

    `ClassField` is a `registry.Field`, so the registry needs no knowledge of any of this
    — it gets name, label, type, choices, help and required exactly as it does for a
    weapon, and ignores the rest.
    """
    return tuple(f for section in CLASS_SCHEMA for f in section.fields)


# --- what counts as classified ---------------------------------------------------------------
#
# The "everything about a class needs labeled" half, made mechanical: walk a real class file
# and report any key the schema above does not name. A test asserts this is empty for Blood
# Bending, which is the only way to know the classification is exhaustive rather than
# plausible.

def _names(fields) -> set[str]:
    return {f.name for f in fields}


def known_keys(scope: str) -> set[str]:
    """The keys named by the schema at one level of the structure."""
    if scope == "class":
        return {f.name for f in registry_fields()}
    if scope == "level":
        # `_columns` is the schema's name for "any other key is a die column", so it is not
        # itself a key that appears in a file.
        return {"level", "grants"}
    if scope == "override":
        return _names(OVERRIDE_ROW)
    if scope == "ability_growth":
        return _names(GROWTH_ROW)
    if scope == "pool":
        return _names(POOL_ROW)
    if scope == "casting":
        return _names(CASTING_FIELDS)
    if scope == "path":
        return _names(PATH_FIELDS)
    raise LookupError(f"no such scope {scope!r}")


def unclassified(d: dict) -> list[str]:
    """Every key in this class file that `CLASS_SCHEMA` does not name, as a dotted path.

    A key beginning with `_` is a note — the shipped classes carry six of them, explaining
    where a corrupted column came from — and notes are deliberately not fields.
    """
    out: list[str] = []

    def walk(entry: dict, scope: str, where: str, extra: set[str] = frozenset()):
        if not isinstance(entry, dict):
            return
        allowed = known_keys(scope) | set(extra)
        for key in entry:
            if str(key).startswith("_"):
                continue
            if key not in allowed:
                out.append(f"{where}{key}")

    walk(d, "class", "")
    for i, row in enumerate(d.get("levels") or []):
        # Every other key on a level row is a die column, which is the point of reading
        # columns by name rather than from a list of the ones this app knows.
        walk(row, "level", f"levels[{i}].",
             {k for k in row if k not in ("level", "grants")} if isinstance(row, dict)
             else set())
    for i, row in enumerate(d.get("overrides") or []):
        walk(row, "override", f"overrides[{i}].")
    for i, row in enumerate(d.get("ability_growth") or []):
        walk(row, "ability_growth", f"ability_growth[{i}].")
    for i, row in enumerate(d.get("pools") or []):
        walk(row, "pool", f"pools[{i}].")
    if isinstance(d.get("casting"), dict):
        walk(d["casting"], "casting", "casting.")
    for pid, path in (d.get("paths") or {}).items():
        if isinstance(path, dict):
            walk(path, "path", f"paths.{pid}.")
    return out


# --- validation --------------------------------------------------------------------------

def _is_dice(text) -> bool:
    return effectspec._is_dice(str(text))


def _int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_effect(spec: dict, where: str, columns=()) -> list[str]:
    """One authored ability effect, including the three things the class layer adds.

    `effectspec.validate` is the vocabulary and it is used unchanged — but four of Blood
    Bending's own effects are `engine_op`, nine take their dice off the class table and two
    take their amount from a tier rung or a formula. Handing those straight to
    `effectspec.validate` reports fifteen missing fields that are not missing at all: they
    are filled in at resolve time by `rules/leveling.py:resolve_effect`. So the derived
    fields are checked here, stubbed, and the rest of the spec goes through untouched.
    """
    problems: list[str] = []
    if not isinstance(spec, dict):
        return [f"{where}: an effect must be an object with a `type`."]

    kind = str(spec.get("type", "")).strip()

    if kind == "engine_op":
        op = str(spec.get("op", "")).strip()
        if op not in ENGINE_OPS:
            problems.append(
                f"{where}: no engine op {op or '(none)'!r}. "
                f"Use one of: {', '.join(sorted(ENGINE_OPS))}.")
        elif op == "spend_pools":
            count = spec.get("count", 1)
            if str(count).lower() != "all" and _int(count) is None:
                problems.append(
                    f"{where}: spend_pools needs `count` as a number or \"all\". "
                    f"Write \"all\" to detonate every pool at once.")
        return problems

    probe = dict(spec)

    if spec.get("dice_from"):
        column = str(spec["dice_from"])
        if columns and column not in columns:
            problems.append(
                f"{where}: no column called {column!r} on this class's level table. "
                f"Add a {column!r} column to the levels, or pick one of: "
                f"{', '.join(sorted(columns)) or 'none are declared'}.")
        times = _int(spec.get("times", 1))
        if times is None or times < 1:
            problems.append(
                f"{where}: `times` multiplies the column's dice and must be 1 or more. "
                f"Write 2 for double {column} damage.")
        probe.setdefault("dice", "1d6")          # filled in at resolve time from the table

    if spec.get("formula"):
        trouble = resources.check(spec["formula"])
        if trouble:
            problems.append(
                f"{where}: {trouble} Formulas may use level, hit_dice, bab, hp, hp_max, "
                f"control_blood, an ability score or its _mod, and floor/ceil/min/max.")
        probe.setdefault("amount", 0)

    if "scales_by" in spec:
        if str(spec.get("scales_by")) != "control_blood":
            problems.append(
                f"{where}: the only thing an effect scales by is `control_blood`. "
                f"Remove `scales_by`, or write \"control_blood\".")
        rungs = spec.get("by_tier")
        if not isinstance(rungs, dict) or not rungs:
            problems.append(
                f"{where}: `scales_by` needs a `by_tier` map — {{\"1\": {{\"amount\": 2}}, "
                f"\"3\": {{\"amount\": 5}}}}. The rung at or below the character's tier "
                f"applies.")
        else:
            for tier, rung in rungs.items():
                n = _int(tier)
                if n is None or not 1 <= n <= MAX_TIER:
                    problems.append(
                        f"{where}: by_tier {tier!r} is not a tier. Tiers run 1 to "
                        f"{MAX_TIER}.")
                elif isinstance(rung, dict):
                    probe.update({k: v for k, v in rung.items() if k not in probe})

    problems.extend(_with_fixes(effectspec.validate(probe, where), kind))
    return problems


_NEEDS = re.compile(r"needs ([a-z ]+)\.$")


def _with_fixes(problems: list[str], type_id: str) -> list[str]:
    """`effectspec`'s messages, with the field's own hint appended.

    Its "Saving throw needs dc." names the fault and stops there, which is right for a form
    that shows the hint beside the input and wrong for a validator whose whole output is a
    list of sentences. The hint is already written, one field away — this joins them rather
    than restating either, so the two cannot drift.
    """
    found = effectspec.find(type_id)
    if found is None:
        return problems
    hints = {f.label.lower(): f.hint
             for f in found[1].fields + effectspec.COMMON if f.hint}
    out = []
    for problem in problems:
        m = _NEEDS.search(problem)
        hint = hints.get(m.group(1).strip()) if m else ""
        out.append(f"{problem} {hint}" if hint else problem)
    return out


def _validate_paths(d: dict, columns, problems: list[str]) -> None:
    """The hard half: branches, tiers, and the four maps that hang off them."""
    paths = d.get("paths")
    if paths in (None, {}, []):
        return
    if not isinstance(paths, dict):
        problems.append(
            "paths: write paths as a map of id → path, not a list. The id is what a "
            "character sheet stores.")
        return

    # A path is only reachable if the level table opens its track, because that is the
    # only thing `control_blood` counts.
    granted = {}
    for row in d.get("levels") or []:
        for grant in (row.get("grants") or []) if isinstance(row, dict) else []:
            m = _TRACK_GRANT.fullmatch(str(grant).strip())
            if m:
                track = m.group(2).lower()
                granted[track] = max(granted.get(track, 0), int(m.group(1)))
    if not granted:
        problems.append(
            f"paths: nothing on the level table opens a path, so every ability stays "
            f"locked forever. Add a grant reading '{TRACK_PHRASE} 1a' at the level the "
            f"first path opens, and '{TRACK_PHRASE} 2a', '3a' and so on where its tiers "
            f"do. The phrase is matched literally.")

    for pid, path in paths.items():
        at = f"paths.{pid}"
        if str(pid) != str(pid).strip().lower():
            problems.append(
                f"{at}: a path id must be lower case with no leading spaces — the engine "
                f"looks it up lower-cased and would never find this one. "
                f"Rename it to {str(pid).strip().lower()!r}.")
        if not isinstance(path, dict):
            problems.append(f"{at}: a path is an object with tiers and abilities.")
            continue

        tiers = path.get("tiers")
        listed: dict[str, int] = {}
        if not isinstance(tiers, dict) or not tiers:
            problems.append(
                f"{at}: a path needs `tiers` — a map of tier number to the abilities it "
                f"unlocks, {{\"1\": [\"First Ability\"]}}.")
            tiers = {}
        for tier, names in tiers.items():
            n = _int(tier)
            if n is None:
                problems.append(f"{at}.tiers: {tier!r} is not a tier number. "
                                f"Tiers are \"1\" to \"{MAX_TIER}\".")
                continue
            if not 1 <= n <= MAX_TIER:
                problems.append(
                    f"{at}.tiers: tier {n} is outside 1-{MAX_TIER}. The level table "
                    f"carries five tiers per track, so nothing at tier {n} could ever be "
                    f"reached — move these abilities to a tier from 1 to {MAX_TIER}.")
                continue
            if n > max(granted.values(), default=0) and granted:
                problems.append(
                    f"{at}.tiers: tier {n} is higher than any '{TRACK_PHRASE} N' the "
                    f"level table grants (the highest is {max(granted.values())}). Grant "
                    f"'{TRACK_PHRASE} {n}a' at some level, or move these abilities down.")
            if not isinstance(names, (list, tuple)) or not names:
                problems.append(f"{at}.tiers.{tier}: list at least one ability, or remove "
                                f"the tier.")
                continue
            for name in names:
                if not str(name).strip():
                    problems.append(f"{at}.tiers.{tier}: an ability with no name.")
                else:
                    listed[str(name)] = n

        abilities = path.get("abilities") or {}
        resolves = path.get("resolves") or {}
        core = {str(x) for x in (path.get("core") or [])}
        undescribed = {str(x) for x in (path.get("undescribed") or [])}

        for name in listed:
            if name in resolves or name in core or name in undescribed:
                continue
            problems.append(
                f"{at}.resolves: nothing says what {name!r} resolves to, so it shows no "
                f"text and runs no effects. Add \"{name}\": \"{name}\" to resolves — or "
                f"list it under Core if the Core Rulebook already defines it.")
        for variant, real in resolves.items():
            if variant not in listed:
                problems.append(
                    f"{at}.resolves: {variant!r} is resolved but no tier lists it, so no "
                    f"character can ever have it. Add it to a tier, or remove the entry.")
            if str(real) not in abilities:
                problems.append(
                    f"{at}.resolves: {variant!r} resolves to {str(real)!r}, which has no "
                    f"ability text. Add an entry for {str(real)!r} under abilities.")

        # A tier may list an ability only through its rungs — Iron Clot appears as
        # "Iron Clot (DR 2/-)" and friends — so the resolved name is on a tier in
        # every sense that matters to passive/core/undescribed membership.
        reachable = set(listed) | {str(r) for r in resolves.values()}
        for group, label, hint in (
                ("passive", "passive", "a passive is an ability the character has"),
                ("core", "core", "core names a tier ability the Core Rulebook defines"),
                ("undescribed", "undescribed", "undescribed names a tier ability")):
            for name in (path.get(group) or []):
                if str(name) not in reachable:
                    problems.append(
                        f"{at}.{label}: {str(name)!r} is not listed on any tier — "
                        f"{hint}. Add it to a tier, or take it out of {label}.")

        for name, condition in (path.get("toggles") or {}).items():
            if str(name) not in listed:
                problems.append(
                    f"{at}.toggles: {str(name)!r} is not an ability on any tier of this "
                    f"path, so nothing can toggle it. Add it to a tier, or remove the "
                    f"toggle.")
            if not str(condition or "").strip():
                problems.append(
                    f"{at}.toggles.{name}: a toggle needs a condition name — the word the "
                    f"sheet shows while it holds, like 'blood armament'.")
        for name in (path.get("upgrades") or {}):
            if str(name) not in listed:
                problems.append(
                    f"{at}.upgrades: {str(name)!r} is not listed on any tier. An upgrade "
                    f"is a tier entry that improves an earlier ability; add it to the tier "
                    f"it arrives at.")

        resolved_names = {str(v) for v in resolves.values()}
        for name, specs in (path.get("effects") or {}).items():
            if str(name) not in resolved_names and str(name) not in abilities:
                problems.append(
                    f"{at}.effects: {str(name)!r} is not an ability of this path, so these "
                    f"effects never run. Effects are keyed by the *resolved* name — the "
                    f"right-hand side of resolves.")
            if not isinstance(specs, list):
                problems.append(f"{at}.effects.{name}: effects are a list, even for one.")
                continue
            for i, spec in enumerate(specs):
                problems.extend(
                    validate_effect(spec, f"{at}.effects.{name}[{i}]", columns))

        _validate_grants(d, path, at, resolved_names, abilities, columns, problems)


_MOD_TYPES = ("ability_mod", "skill_mod", "save_mod", "combat_mod")


def _validate_grants(d: dict, path: dict, at: str, resolved_names: set,
                     abilities: dict, columns, problems: list[str]) -> None:
    """Stage 3's grammar, checked with the fix named rather than the fault.

    A document that fails here would otherwise fail silently in play — an ability
    whose cost names a pool the class never declares is an ability that always
    refuses, with nothing anywhere saying why.
    """
    grants = path.get("grants") or {}
    if not isinstance(grants, dict):
        problems.append(f"{at}.grants: write grants as a map of resolved ability name "
                        f"→ document.")
        return
    pool_ids = {str(p.get("id", "")).lower() for p in (d.get("pools") or [])
                if isinstance(p, dict)}
    toggled = {str(v).lower() for v in (path.get("toggles") or {}).values()}
    toggle_names = {str(k) for k in (path.get("toggles") or {})}

    for name, doc in grants.items():
        gat = f"{at}.grants.{name}"
        if str(name) not in resolved_names and str(name) not in abilities:
            problems.append(
                f"{gat}: {str(name)!r} is not an ability of this path, so the document "
                f"never applies. Grants are keyed by the *resolved* name — the "
                f"right-hand side of resolves.")
        if not isinstance(doc, dict):
            problems.append(f"{gat}: a document is an object.")
            continue
        for field_name in ("requires", "requires_not", "tags"):
            got = doc.get(field_name)
            if got is not None and (not isinstance(got, (list, tuple)) or
                                    any(not str(q).strip() for q in got)):
                problems.append(
                    f"{gat}.{field_name}: a list of tag queries, like "
                    f"\"state.impaired.fatigued\" — dot-paths from rules/states.py.")
        for field_name in ("cost", "drain"):
            got = doc.get(field_name)
            if got is None:
                continue
            if not isinstance(got, dict) or not str(got.get("pool", "")).strip():
                problems.append(
                    f"{gat}.{field_name}: needs a pool — {{\"pool\": \"rage\", "
                    f"\"amount\": 1}}.")
                continue
            if pool_ids and str(got["pool"]).lower() not in pool_ids:
                problems.append(
                    f"{gat}.{field_name}: this class declares no pool called "
                    f"{got['pool']!r}, so the ability would always refuse. Declare the "
                    f"pool under pools, or name one of: "
                    f"{', '.join(sorted(pool_ids))}.")
            if _int(got.get("amount", 1)) is None:
                problems.append(f"{gat}.{field_name}: amount must be a number.")
        for i, spec in enumerate(doc.get("modifiers") or []):
            if not isinstance(spec, dict) or \
                    str(spec.get("type", "")) not in _MOD_TYPES:
                problems.append(
                    f"{gat}.modifiers[{i}]: a document's modifiers are the four "
                    f"modifier types — {', '.join(_MOD_TYPES)} — because they ride "
                    f"the sheet's own modifier lists.")
                continue
            problems.extend(validate_effect(spec, f"{gat}.modifiers[{i}]", columns))
        temp = doc.get("temp_hp")
        if temp is not None:
            rungs = (temp.get("by_tier") or {}) if isinstance(temp, dict) else {}
            flat = temp.get("per_hit_die") if isinstance(temp, dict) else None
            per_hd = list(rungs.values()) + ([{"per_hit_die": flat}]
                                             if flat is not None else [])
            if not isinstance(temp, dict) or not per_hd or any(
                    not isinstance(r, dict) or _int(r.get("per_hit_die")) is None
                    for r in per_hd):
                problems.append(
                    f"{gat}.temp_hp: needs per_hit_die as a number — flat "
                    f"({{\"per_hit_die\": 2}}) or tiered ({{\"by_tier\": {{\"1\": "
                    f"{{\"per_hit_die\": 2}}}}}}).")
        resist = doc.get("resist")
        if resist is not None:
            rungs = (resist.get("by_tier") or {}) if isinstance(resist, dict) else {}
            flat = ([resist] if isinstance(resist, dict)
                    and resist.get("percent") is not None else [])
            entries = list(rungs.values()) + flat
            if not isinstance(resist, dict) or not entries or any(
                    not isinstance(r, dict)
                    or _int(r.get("percent")) is None
                    or not str(r.get("against", "physical")).strip()
                    for r in entries):
                problems.append(
                    f"{gat}.resist: needs a percent and what it is against — "
                    f"{{\"against\": \"physical\", \"percent\": 50}}, flat or under "
                    f"by_tier. \"physical\" covers the three weapon types; a named "
                    f"energy covers itself.")
        dr = doc.get("dr")
        if dr is not None:
            rungs = (dr.get("by_tier") or {}) if isinstance(dr, dict) else {}
            flat = ([dr] if isinstance(dr, dict) and dr.get("amount") is not None
                    else [])
            entries = list(rungs.values()) + flat
            if not isinstance(dr, dict) or not entries or any(
                    not isinstance(r, dict) or _int(r.get("amount")) is None
                    for r in entries):
                problems.append(
                    f"{gat}.dr: needs an amount — {{\"amount\": 2}} flat, or rungs "
                    f"under by_tier with scales_by. bypass is what defeats it "
                    f"(\"silver\", \"magic\") or absent for the DR/— nothing does.")
        weapon = doc.get("weapon")
        if weapon is not None:
            if not isinstance(weapon, dict):
                problems.append(f"{gat}.weapon: a granted weapon is an object.")
            else:
                col = str(weapon.get("damage_column") or "")
                if col and columns and col not in columns:
                    problems.append(
                        f"{gat}.weapon: no column called {col!r} on this class's level "
                        f"table. Add it to the levels, or pick one of: "
                        f"{', '.join(sorted(columns)) or 'none are declared'}.")
                if not str(weapon.get("name", "")).strip():
                    problems.append(
                        f"{gat}.weapon: needs a name — what the dice popup and the "
                        f"attack panel call the strike.")
        standing = any(doc.get(k) for k in ("modifiers", "temp_hp", "weapon",
                                            "tags", "drain", "resist", "dr"))
        # A passive's standing parts never need removing — the ability is never on
        # or off, it simply holds — so only non-passive documents must be toggles.
        passive_names = {str(n).lower() for n in (path.get("passive") or [])}
        if standing and str(name) not in toggle_names \
                and str(name).lower() not in passive_names:
            problems.append(
                f"{gat}: this document has standing parts (modifiers, tags, a weapon, "
                f"temporary hit points or a drain) but {str(name)!r} is not in "
                f"toggles, so nothing could ever remove what it applies. Add it to "
                f"toggles with the condition name the sheet should show.")
        _ = toggled  # the condition names themselves are free text, checked by toggles


# --- feat documents (stage 8) ------------------------------------------------------------

# What a feat document may carry. Everything else is refused, because the applier
# ignores what it does not know and a silently ignored field is a feat that quietly
# does less than its author wrote — `effectspec.validate` never rejected an unknown
# key, and the homebrew editor has offered feats an `effects` field for a year that
# `feats.from_dict` dropped on the floor.
_FEAT_DOC_KEYS = frozenset({"modifiers", "tags", "budget", "choice", "attack_ability",
                            "not_yet", "requires", "requires_not"})
_FEAT_MOD_KEYS = frozenset({"type", "target", "amount", "formula", "bonus_type", "scope",
                            "when", "note"})


def validate_feat_document(feat_id: str, doc) -> list[str]:
    """One feat's mechanics, checked with the fix named.

    The same modifier grammar the class documents use (`validate_effect`, the four
    modifier types, the target vocabulary), plus the fields stage 8 added for feats:
    `scope` and `when` on a modifier (a roll context the sheet evaluates, dropped when
    it has none), `budget` (a count, like attacks of opportunity), `choice` (a boolean
    the attack op may carry), `attack_ability` (a substitution), `not_yet` (the clauses
    the engine has no reader for, said out loud).
    """
    problems: list[str] = []
    at = f"feats.{feat_id}"
    if not isinstance(doc, dict):
        return [f"{at}: a document is an object."]
    unknown = sorted(set(doc) - _FEAT_DOC_KEYS)
    if unknown:
        problems.append(
            f"{at}: unknown field(s) {', '.join(unknown)}. A feat document carries: "
            f"{', '.join(sorted(_FEAT_DOC_KEYS))}.")
    for i, spec in enumerate(doc.get("modifiers") or []):
        mat = f"{at}.modifiers[{i}]"
        if not isinstance(spec, dict) or str(spec.get("type", "")) not in _MOD_TYPES:
            problems.append(
                f"{mat}: a feat's modifiers are the four modifier types — "
                f"{', '.join(_MOD_TYPES)} — because they ride the sheet's own lists.")
            continue
        extra = sorted(set(spec) - _FEAT_MOD_KEYS)
        if extra:
            problems.append(
                f"{mat}: unknown key(s) {', '.join(extra)}; the applier would ignore "
                f"them, so they are refused. A modifier carries: "
                f"{', '.join(sorted(_FEAT_MOD_KEYS))}.")
        if spec.get("amount") is None and not spec.get("formula"):
            problems.append(f"{mat}: an amount (a number) or a formula over the sheet.")
        probe = {k: v for k, v in spec.items()
                 if k in ("type", "target", "amount", "formula", "bonus_type", "note")}
        problems.extend(validate_effect(probe, mat, ()))
        for cond in ("scope", "when"):
            if cond in spec and not isinstance(spec[cond], dict):
                problems.append(
                    f"{mat}.{cond}: an object — scope {{\"weapon\": \"$target\"}}, "
                    f"when {{\"range_ft\": {{\"lte\": 30}}}}.")
    for field_name in ("tags", "not_yet", "requires", "requires_not"):
        got = doc.get(field_name)
        if got is not None and (not isinstance(got, (list, tuple))
                                or any(not str(q).strip() for q in got)):
            problems.append(f"{at}.{field_name}: a list of strings.")
    budget = doc.get("budget")
    if budget is not None:
        bad = (not isinstance(budget, dict) or not budget
               or any(resources.check(v) for v in budget.values()))
        if bad:
            problems.append(
                f"{at}.budget: a map of reaction → formula, like "
                f"{{\"attack_of_opportunity\": \"1 + dex_mod\"}}.")
    choice = doc.get("choice")
    if choice is not None:
        from .intents import OPS

        allowed = OPS["attack"][1]
        if str(choice) not in allowed:
            problems.append(
                f"{at}.choice: {str(choice)!r} is not a boolean the attack op carries. "
                f"One of: {', '.join(allowed)}.")
    sub = doc.get("attack_ability")
    if sub is not None:
        from .tables import ABILITIES

        if not isinstance(sub, dict) or str(sub.get("use", "")) not in ABILITIES:
            problems.append(
                f"{at}.attack_ability: {{\"use\": \"dex\", \"if_better\": true}} — "
                f"which score feeds the attack roll instead of Strength.")
    return problems


def validate_feat_documents(docs: dict) -> list[str]:
    """The whole file: every id must be a feat, every document must validate."""
    from . import feats as feats_mod

    problems: list[str] = []
    known = feats_mod.all_feats()
    for fid, doc in (docs or {}).items():
        if str(fid) not in known:
            problems.append(
                f"feats.{fid}: no feat with that id in feats.json. Documents are keyed "
                f"by id, never by name — two Foeslayers and 155 mythic namesakes.")
        problems.extend(validate_feat_document(str(fid), doc))
    return problems


def validate_class(d: dict) -> list[str]:
    """Everything wrong with an authored class, each with the fix rather than the fault.

    All of them at once, the same choice `effectspec.validate` and `creation.build` made
    and for the same reason: a class nobody finishes is a class built one error per submit.
    """
    problems: list[str] = []
    if not isinstance(d, dict):
        return ["A class is a JSON object: {\"id\": \"...\", \"name\": \"...\"}."]

    # --- identity -----------------------------------------------------------------
    cid = str(d.get("id", "")).strip()
    if not cid:
        problems.append("id: give the class an id — lower case, and permanent, because "
                        "every character sheet stores this string.")
    elif cid != cid.lower():
        problems.append(f"id: {cid!r} has capitals in it. `rules.classes` looks classes up "
                        f"lower-cased, so write {cid.lower()!r}.")
    if not str(d.get("name", "")).strip():
        problems.append("name: give the class a display name — 'Storm Caller'.")

    # --- the numbers --------------------------------------------------------------
    bab = str(d.get("bab", "")).strip()
    if not bab:
        problems.append(f"bab: say which attack progression this class uses: "
                        f"{', '.join(BAB_CHOICES)}.")
    elif bab not in classes_mod.BAB:
        problems.append(
            f"bab: {bab!r} is not a progression. Use one of {', '.join(BAB_CHOICES)} — "
            f"full is +1 a level, three_quarter the rogue's, half the wizard's.")

    die = d.get("hit_die")
    if die in (None, ""):
        problems.append("hit_die: every class rolls something for hit points. Write a "
                        "number (8) or notation (2d8).")
    elif not (isinstance(die, (int, float)) or _is_dice(str(die))):
        problems.append(
            f"hit_die: {die!r} is not a die. Write a number (8) or dice notation (2d8); "
            f"anything else falls back to a d8 with no warning at play time.")

    per_level = d.get("hit_dice_per_level")
    if per_level not in (None, "") and (_int(per_level) or 0) < 1:
        problems.append("hit_dice_per_level: 1 or more, and leave it out entirely for the "
                        "usual one die a level.")

    # `creation.starting_purse` reads this at character creation, and both of its quiet
    # failure shapes have now happened: a string the pattern cannot read becomes an
    # EMPTY purse with no warning, and a Storm Lord's "300d100 x 100 gp" crashed the
    # forge with a 500 before implausible dice learned to pay their average. Say both
    # things here, where the author can still fix the words.
    wealth = str(d.get("starting_wealth") or "").strip()
    if wealth:
        import re as _re
        m = _re.fullmatch(r"(\d+)d(\d+)\s*(?:[x×*]\s*(\d+))?\s*([a-z]{2})?",
                          wealth.lower())
        if not m:
            problems.append(
                f"starting_wealth: {wealth!r} is not a wealth roll the forge can read. "
                f"Write it like '5d6 x 10 gp' — dice, an optional multiplier, a coin.")
        elif int(m.group(1)) > 100 or int(m.group(2)) > 1000:
            problems.append(
                f"starting_wealth: {wealth!r} is more dice than anyone rolls. It will "
                f"work — the forge pays its average instead of rolling — but if you "
                f"meant a number, '2d4 x 1000 gp' reads better than three hundred dice.")

    ranks = d.get("skill_ranks")
    if ranks in (None, ""):
        problems.append("skill_ranks: how many skill ranks a level, before Intelligence. "
                        "2, 4, 6 or 8.")
    elif (_int(ranks) or 0) < 1:
        problems.append(f"skill_ranks: {ranks!r} is not a rank count. Write 2, 4, 6 or 8.")

    good = d.get("good_saves") or ()
    if isinstance(good, str):
        problems.append("good_saves: a list, even for one — [\"fort\"].")
        good = ()
    for save in good:
        if str(save).lower() not in SAVE_KEYS:
            problems.append(f"good_saves: {save!r} is not a save. Use "
                            f"{', '.join(SAVE_KEYS)}.")

    saves = d.get("saves") or {}
    if not isinstance(saves, dict):
        problems.append("saves: a map of save → track name or twenty numbers.")
    else:
        for save, spec in saves.items():
            if str(save).lower() not in SAVE_KEYS:
                problems.append(f"saves: {save!r} is not a save. Use "
                                f"{', '.join(SAVE_KEYS)}.")
            if isinstance(spec, (list, tuple)):
                if len(spec) != MAX_LEVEL:
                    problems.append(
                        f"saves.{save}: a typed column needs one number per level — "
                        f"{MAX_LEVEL} of them, and this has {len(spec)}. Levels past the "
                        f"end quietly hold at the last value.")
                for i, n in enumerate(spec):
                    if _int(n) is None:
                        problems.append(f"saves.{save}[{i}]: {n!r} is not a number.")
                        break
            elif str(spec).strip().lower() not in SAVE_TRACKS:
                problems.append(
                    f"saves.{save}: {spec!r} is not a track. Use one of "
                    f"{', '.join(SAVE_TRACKS)}, or type all {MAX_LEVEL} numbers out for a "
                    f"column that is not regular.")

    for skill in (d.get("class_skills") or ()):
        if str(skill).strip().lower() not in SKILLS:
            problems.append(
                f"class_skills: {skill!r} is not a skill the sheet knows, so it will never "
                f"take the class bonus. Check the spelling — knowledge skills are written "
                f"'knowledge (religion)'.")
    for prof in (d.get("proficiencies") or ()):
        key = str(prof).strip().lower()
        if key not in PROFICIENCY_GROUPS and key not in WEAPONS:
            problems.append(
                f"proficiencies: {prof!r} is neither a group ({', '.join(PROFICIENCY_GROUPS)}) "
                f"nor a weapon the tables carry, so it grants proficiency in nothing.")

    # --- the level table ----------------------------------------------------------
    columns, levels_seen = set(), {}
    rows = d.get("levels")
    if not rows:
        problems.append(
            "levels: a class needs a level table. One row per level: "
            "{\"level\": 1, \"grants\": [\"...\"]}.")
        rows = []
    if not isinstance(rows, list):
        problems.append("levels: a list of rows, one per level.")
        rows = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(f"levels[{i}]: a row is an object with a level and its grants.")
            continue
        n = _int(row.get("level"))
        if n is None or not 1 <= n <= MAX_LEVEL:
            problems.append(
                f"levels[{i}]: {row.get('level')!r} is not a level. Levels run 1 to "
                f"{MAX_LEVEL}.")
            continue
        if n in levels_seen:
            problems.append(f"levels: level {n} has two rows. Merge them — "
                            f"`table_at` returns the first and the second is ignored.")
        levels_seen[n] = row
        grants = row.get("grants")
        if grants is not None and not isinstance(grants, list):
            problems.append(f"levels[{i}].grants: a list of names, even for one.")
        for key, value in row.items():
            if key in ("level", "grants") or str(key).startswith("_"):
                continue
            columns.add(str(key))
            if not _is_dice(str(value)):
                problems.append(
                    f"levels[{i}].{key}: {value!r} is not dice. A class-table column holds "
                    f"notation like 1d6 or 2d8 — it is rolled by any effect that reads it.")
    if levels_seen:
        top = max(levels_seen)
        missing = [n for n in range(1, top + 1) if n not in levels_seen]
        if missing:
            problems.append(
                f"levels: no row for level{'s' if len(missing) > 1 else ''} "
                f"{', '.join(str(n) for n in missing)}. Add "
                f"{'them' if len(missing) > 1 else 'it'} with an empty grants list — a "
                f"level with no row prints no dice and grants nothing.")
        for column in sorted(columns):
            blank = [n for n, row in sorted(levels_seen.items())
                     if not str(row.get(column, "")).strip()]
            if blank:
                problems.append(
                    f"levels: the {column!r} column is empty at level"
                    f"{'s' if len(blank) > 1 else ''} "
                    f"{', '.join(str(n) for n in blank)}. Any effect reading that column "
                    f"goes inactive at those levels rather than failing loudly.")

    # --- features -----------------------------------------------------------------
    features = d.get("features") or {}
    if not isinstance(features, dict):
        problems.append("features: a map of feature name → its rules text.")
    else:
        for name, text in features.items():
            if not str(text or "").strip():
                problems.append(
                    f"features.{name}: no text, so a click on the sheet answers nothing. "
                    f"Write what it does, or take the entry out.")

    # --- overrides ----------------------------------------------------------------
    for i, spec in enumerate(d.get("overrides") or []):
        if not isinstance(spec, dict):
            problems.append(f"overrides[{i}]: an object with a rule and a from_level.")
            continue
        rule = str(spec.get("rule", "")).strip()
        if rule not in ACTOR_RULES:
            problems.append(
                f"overrides[{i}]: {rule or '(none)'!r} is not a rule the engine asks "
                f"about, so it would grant nothing at all. The six are: "
                f"{', '.join(RULE_CHOICES)}.")
        lvl = _int(spec.get("from_level", 1))
        if lvl is None or not 1 <= lvl <= MAX_LEVEL:
            problems.append(f"overrides[{i}].from_level: a level from 1 to {MAX_LEVEL}.")

    # --- ability growth -----------------------------------------------------------
    for i, spec in enumerate(d.get("ability_growth") or []):
        if not isinstance(spec, dict):
            problems.append(f"ability_growth[{i}]: an object with ability, every, amount.")
            continue
        if str(spec.get("ability", "")).lower() not in ABILITIES:
            problems.append(
                f"ability_growth[{i}].ability: {spec.get('ability')!r} is not an ability. "
                f"Use one of {', '.join(ABILITIES)}.")
        every = _int(spec.get("every"))
        if every is None or every < 1:
            problems.append(
                f"ability_growth[{i}].every: how many levels between each increase — 5 "
                f"means 5th, 10th, 15th and 20th.")
        if _int(spec.get("amount")) in (None, 0):
            problems.append(
                f"ability_growth[{i}].amount: how many points each time. +2 is the usual.")

    # --- pools --------------------------------------------------------------------
    seen_pools = set()
    for i, spec in enumerate(d.get("pools") or []):
        at = f"pools[{i}]"
        if not isinstance(spec, dict):
            problems.append(f"{at}: an object with an id and a maximum.")
            continue
        pid = str(spec.get("id", "")).strip().lower()
        if not pid:
            problems.append(f"{at}.id: name the pool — 'ki', 'rage', 'stunning strike'.")
        elif pid in seen_pools:
            problems.append(
                f"{at}.id: {pid!r} is defined twice. The second definition silently "
                f"recomputes the first — merge them.")
        seen_pools.add(pid)
        if spec.get("max") in (None, ""):
            problems.append(
                f"{at}.max: a pool needs a maximum, as a number or a formula over the "
                f"sheet — 'floor(level/2) + con_mod'.")
        else:
            trouble = resources.check(spec["max"])
            if trouble:
                problems.append(
                    f"{at}.max: {trouble} A formula may use level, hit_dice, bab, hp_max, "
                    f"control_blood, any ability score or its _mod, and "
                    f"floor/ceil/min/max.")
        lvl = _int(spec.get("from_level", 1))
        if lvl is None or not 1 <= lvl <= MAX_LEVEL:
            problems.append(f"{at}.from_level: a level from 1 to {MAX_LEVEL}.")
        refresh = str(spec.get("refresh", "rest.night"))
        if refresh not in resources.REFRESH:
            problems.append(
                f"{at}.refresh: {refresh!r} is not a refresh. Use one of "
                f"{', '.join(REFRESH_CHOICES)}.")
        starts = spec.get("starts", "max")
        if str(starts) != "max" and _int(starts) is None:
            problems.append(f"{at}.starts: 'max', or a number to start part-full.")
        scope = str(spec.get("scope", "self"))
        if scope not in ("self", "target"):
            problems.append(
                f"{at}.scope: 'self', or 'target' for a pool that sits on the creature it "
                f"was applied to.")
        if spec.get("cooldown") and not _is_dice(str(spec["cooldown"])):
            problems.append(
                f"{at}.cooldown: {spec['cooldown']!r} is not dice. A cooldown is rolled — "
                f"write 1d3, or a flat number of rounds.")
        upkeep = spec.get("upkeep")
        if upkeep not in (None, {}, ""):
            if not isinstance(upkeep, dict) or not upkeep.get("amount"):
                problems.append(
                    f"{at}.upkeep: an upkeep is {{\"amount\": \"1d10\", \"resource\": "
                    f"\"nonlethal\"}} — how much is paid every round, and in what.")
            elif not _is_dice(str(upkeep.get("amount"))):
                problems.append(f"{at}.upkeep.amount: {upkeep.get('amount')!r} is not "
                                f"dice or a number.")

    # --- casting ------------------------------------------------------------------
    casting = d.get("casting")
    if casting not in (None, {}, ""):
        if not isinstance(casting, dict):
            problems.append("casting: an object, or leave it out entirely for a class that "
                            "does not cast.")
        else:
            from . import casting as casting_mod

            if str(casting.get("ability", "")).lower() not in ABILITIES:
                problems.append(
                    f"casting.ability: {casting.get('ability')!r} is not an ability. Every "
                    f"slot count and save DC is computed off it — use one of "
                    f"{', '.join(ABILITIES)}.")
            prog = str(casting.get("progression", "full"))
            if prog not in casting_mod.PROGRESSIONS:
                problems.append(
                    f"casting.progression: {prog!r} is not a slot table. Use one of "
                    f"{', '.join(sorted(casting_mod.PROGRESSIONS))}.")
            if str(casting.get("kind", "")) not in ("prepared", "spontaneous"):
                problems.append("casting.kind: 'prepared' or 'spontaneous'.")
            if str(casting.get("prepare_from", "")) not in ("spellbook", "list", "known"):
                problems.append(
                    "casting.prepare_from: 'spellbook' (a wizard's book), 'list' (the "
                    "whole class list every morning) or 'known' (a sorcerer's repertoire).")
            spell_list = str(casting.get("list", "")).strip().lower()
            if not spell_list:
                problems.append(
                    "casting.list: which printed spell list this class casts off — wizard, "
                    "cleric, druid, sorcerer, bard, paladin or ranger. A list of your own "
                    "has no spells on it, so nothing would be castable.")

    # --- paths --------------------------------------------------------------------
    limit = d.get("max_paths")
    if limit not in (None, "") and (_int(limit) or 0) < 1:
        problems.append("max_paths: 1 or more, or leave it out and it is counted from the "
                        "tracks the level table grants.")
    _validate_paths(d, columns, problems)

    return problems


# --- scaffolds ----------------------------------------------------------------------------
#
# Three, because there are three genuinely different shapes of class and a blank form is
# the thing that stops anybody starting. Each one is a *valid, playable* class: it loads
# through `rules.classes`, a character can be created in it, and it levels to 20.

def _levels(grants: dict, columns: dict | None = None) -> list[dict]:
    """A twenty-row table from a sparse description, so a scaffold has no gaps.

    Gaps are the commonest error in a hand-written table and the least visible: a missing
    row prints no die column and grants nothing, with nothing anywhere to say why.
    """
    out = []
    for n in range(1, MAX_LEVEL + 1):
        row: dict = {"level": n, "grants": list(grants.get(n, []))}
        for column, by_level in (columns or {}).items():
            # The last value at or below this level, so a column is stated where it
            # changes rather than twenty times over.
            reached = [k for k in sorted(by_level) if k <= n]
            if reached:
                row[column] = by_level[reached[-1]]
        out.append(row)
    return out


def _martial() -> dict:
    return {
        "id": "bulwark",
        "name": "Bulwark",
        "summary": "A soldier who holds a doorway. No resources to track, no branches to "
                   "choose: armour, a weapon, and the discipline to stand still.",
        "hit_die": 10,
        "bab": "full",
        "good_saves": ["fort"],
        "skill_ranks": 2,
        "class_skills": ["climb", "craft", "handle animal", "intimidate",
                         "knowledge (engineering)", "profession", "ride", "survival",
                         "swim"],
        "proficiencies": ["simple", "martial"],
        "starting_wealth": "5d6 x 10 gp",
        "alignment": "any",
        "features": {
            "shield wall": "While you have a shield and did not move this round, allies "
                           "adjacent to you gain a +1 shield bonus to AC.",
            "hold the line": "Once per round, when an enemy tries to move past you, you "
                             "may make an attack of opportunity even if you have already "
                             "used your reaction this round.",
        },
        "levels": _levels({
            1: ["bonus feat", "shield wall"],
            2: ["bonus feat"], 3: ["hold the line"], 4: ["bonus feat"],
            6: ["bonus feat"], 8: ["bonus feat"], 10: ["bonus feat"],
            12: ["bonus feat"], 14: ["bonus feat"], 16: ["bonus feat"],
            18: ["bonus feat"], 20: ["bonus feat"],
        }),
    }


def _spellcaster() -> dict:
    return {
        "id": "hedge mage",
        "name": "Hedge Mage",
        "summary": "A self-taught wizard working out of a book they wrote themselves. "
                   "Full slots off Intelligence, prepared every morning, and no armour "
                   "worth the name.",
        "hit_die": 6,
        "bab": "half",
        "good_saves": ["will"],
        "skill_ranks": 2,
        "class_skills": ["appraise", "craft", "knowledge (arcana)", "knowledge (history)",
                         "knowledge (nature)", "linguistics", "profession", "spellcraft"],
        "proficiencies": ["club", "dagger", "quarterstaff"],
        "starting_wealth": "2d6 x 10 gp",
        "casting": {
            "ability": "int",
            "kind": "prepared",
            "progression": "full",
            "list": "wizard",
            "prepare_from": "spellbook",
            "note": "Prepares from the book they carry; losing it is losing the spells.",
        },
        "features": {
            "hedge lore": "You may attempt any Knowledge check untrained, at a -2 penalty.",
        },
        "levels": _levels({
            1: ["hedge lore", "bonus feat"],
            5: ["bonus feat"], 10: ["bonus feat"], 15: ["bonus feat"],
            20: ["bonus feat"],
        }),
    }


def _paths() -> dict:
    """The Blood-Bending shape, at the smallest size that still exercises every mechanism.

    Two paths, three tiers each, and one of everything: a passive, a toggle, an upgrade, a
    tiered damage-reduction, an effect that multiplies a class-table column, a save gate
    with a real DC formula, and an engine op. If a mechanism is not here, it is not one a
    class has.

    The grants read `control blood 1a` verbatim on purpose. `rules/leveling.py:control_blood`
    matches that exact phrase to work out how far along a path a character is, so a path
    class that invents its own wording has abilities that never unlock. See the integration
    note in docs/class-creation.md.
    """
    return {
        "id": "storm caller",
        "name": "Storm Caller",
        "summary": "Weather answers them, and takes a toll for it. Two ways to call it: "
                   "the Gale rides the wind, the Bulwark stands in it.",
        "_track_note": "The 'control blood Na' grants are the engine's tier phrase, "
                       "matched literally by rules/leveling.py:control_blood. Rename them "
                       "and every path ability stays locked.",
        "hit_die": 8,
        "bab": "three_quarter",
        "good_saves": ["ref", "will"],
        "saves": {"fort": "poor", "ref": "good", "will": "good"},
        "skill_ranks": 4,
        "class_skills": ["acrobatics", "climb", "craft", "fly", "knowledge (nature)",
                         "perception", "profession", "survival", "swim"],
        "proficiencies": ["simple"],
        "starting_wealth": "3d6 x 10 gp",
        "alignment": "any",
        "features": {
            "storm bond": "The weather is bound to you. Abilities that cost you hit points "
                          "deal that damage as non-lethal, and temporary hit points from "
                          "your own abilities stack rather than overlap.",
        },
        "overrides": [
            {"rule": "temp_hp.stacks", "from_level": 1,
             "why": "Storm Bond: the class banks weather as temporary hit points and "
                    "layering two of them is the class working as written."},
        ],
        "ability_growth": [
            {"ability": "con", "every": 10, "amount": 1,
             "why": "Standing in your own storm hardens you."},
        ],
        "pools": [
            {"id": "squall", "from_level": 1, "max": "3 + wis_mod + floor(level/2)",
             "starts": "max", "refresh": "rest.night",
             "_note": "The class's one spendable resource."},
        ],
        "levels": _levels(
            {
                1: ["storm bond", "control blood 1a"],
                3: ["control blood 2a"],
                5: ["control blood 3a"],
                7: ["evasion"],
                11: ["control blood 1b"],
                13: ["control blood 2b"],
                15: ["control blood 3b"],
                20: ["bonus feat"],
            },
            {"squall": {1: "1d6", 5: "2d6", 10: "3d6", 15: "4d6", 20: "5d6"}},
        ),
        "max_paths": 2,
        "paths": {
            "gale": {
                "name": "Gale",
                "role": "Skirmisher",
                "summary": "Wind at your back and nobody's hands on you.",
                "global_rule": "You are never flat-footed against a creature you have "
                               "already hit this encounter.",
                "tiers": {
                    "1": ["Windstep", "Cutting Gust"],
                    "2": ["Riding the Squall"],
                    "3": ["Thunderclap"],
                },
                "abilities": {
                    "Windstep": "Always active. The first 10 feet you move each round "
                                "provokes no attacks of opportunity.",
                    "Cutting Gust": "Standard action. Take 1d6 non-lethal damage and cut "
                                    "a target within 60 feet with driven air, dealing "
                                    "Squall damage.",
                    "Riding the Squall": "Toggle (free action): the wind carries you. "
                                         "While it holds, your land speed is treated as "
                                         "10 feet higher and you may move through an "
                                         "enemy's square.",
                    "Thunderclap": "Standard action. Take 2d6 non-lethal damage. Every "
                                   "creature within 20 feet must make a Fortitude save or "
                                   "be deafened, and takes twice your Squall damage.",
                },
                "resolves": {
                    "Windstep": "Windstep",
                    "Cutting Gust": "Cutting Gust",
                    "Riding the Squall": "Riding the Squall",
                    "Thunderclap": "Thunderclap",
                },
                "passive": ["Windstep"],
                "toggles": {"Riding the Squall": "riding the squall"},
                "effects": {
                    "Cutting Gust": [
                        {"type": "damage", "dice": "1d6", "damage_type": "untyped",
                         "lethality": "nonlethal", "note": "the cost of Cutting Gust"},
                        {"type": "damage", "dice_from": "squall", "times": 1,
                         "damage_type": "electricity", "lethality": "lethal"},
                    ],
                    "Thunderclap": [
                        {"type": "damage", "dice": "2d6", "damage_type": "untyped",
                         "lethality": "nonlethal", "note": "the cost of Thunderclap"},
                        {"type": "save_gate", "target": "fort",
                         "dc": "10 + level/2 + wis_mod",
                         "on_failure": [{"type": "apply_condition", "target": "deafened"}]},
                        {"type": "damage", "dice_from": "squall", "times": 2,
                         "damage_type": "electricity", "lethality": "lethal"},
                    ],
                },
            },
            "bulwark": {
                "name": "Bulwark",
                "role": "Tank",
                "summary": "You are the thing the storm breaks against.",
                "global_rule": "",
                "tiers": {
                    "1": ["Stormskin (DR 2/-)"],
                    "2": ["Rolling Thunder"],
                    "3": ["Stormskin (DR 5/-)", "Greater Rolling Thunder"],
                },
                "abilities": {
                    "Stormskin": "Gain permanent DR/-. DR 2/- at tier 1, DR 5/- at tier 3.",
                    "Rolling Thunder": "Immediate action. When an adjacent ally is hit, "
                                       "take the damage yourself; you gain temporary hit "
                                       "points equal to half of it.",
                },
                "resolves": {
                    "Stormskin (DR 2/-)": "Stormskin",
                    "Stormskin (DR 5/-)": "Stormskin",
                    "Rolling Thunder": "Rolling Thunder",
                    "Greater Rolling Thunder": "Rolling Thunder",
                },
                "upgrades": {
                    "Greater Rolling Thunder": "The temporary hit points are equal to all "
                                               "of the damage taken, not half.",
                },
                "effects": {
                    "Stormskin": [
                        {"type": "damage_reduction", "scales_by": "control_blood",
                         "by_tier": {"1": {"amount": 2, "bypass": ""},
                                     "3": {"amount": 5, "bypass": ""}}},
                    ],
                    "Rolling Thunder": [
                        {"type": "temp_hp", "dice": "1d6", "source": "Rolling Thunder"},
                        {"type": "engine_op", "op": "blood_pool",
                         "note": "rain and hail where the blow landed"},
                    ],
                },
            },
        },
    }


SCAFFOLDS: dict[str, dict] = {
    "martial": {
        "label": "Simple martial class",
        "blurb": "Hit dice, attack, saves, skills and a level table. No pools, no paths, "
                 "no overrides — the shape most classes are.",
        "build": _martial,
    },
    "spellcaster": {
        "label": "Spellcasting class",
        "blurb": "The martial shape plus a casting block: slots become pools, caster "
                 "level and save DCs are computed, and the spell tab appears.",
        "build": _spellcaster,
    },
    "paths": {
        "label": "Path-based class (the Blood Bending shape)",
        "blurb": "Two branches with tiered abilities, a passive, a toggle, an upgrade, a "
                 "tier-scaled DR, effects that multiply a class-table column, and a pool. "
                 "Everything the engine can do for a class is in here once.",
        "build": _paths,
    },
}


def scaffold(kind: str) -> dict:
    """A starting class of one of the three shapes. Every one validates clean."""
    found = SCAFFOLDS.get((kind or "").strip().lower())
    if found is None:
        raise LookupError(
            f"no scaffold {kind!r}; there are {', '.join(sorted(SCAFFOLDS))}.")
    return found["build"]()


def scaffold_list() -> list[dict]:
    return [{"id": k, "label": v["label"], "blurb": v["blurb"]}
            for k, v in SCAFFOLDS.items()]


# --- saving --------------------------------------------------------------------------------

def save_class(d: dict):
    """Write a validated class to the user's homebrew folder and make it live at once.

    Refused if it does not validate, because a class file the loader half-reads is worse
    than one that was never written: `rules.classes.all_classes` swallows a broken file
    silently, and the only symptom is a class that has quietly stopped existing.

    The module cache is cleared here rather than left to a restart. `all_classes` caches
    for the life of the process, so without this a class saved from the builder is invisible
    until the app is closed — which reads exactly like a save that did not work.
    """
    from . import registry

    problems = validate_class(d)
    if problems:
        raise ValueError("; ".join(problems))
    path = registry.save("classes", d)
    classes_mod._ALL = None
    return path


__all__ = ["CLASS_SCHEMA", "ClassField", "ENGINE_OPS", "MAX_LEVEL", "MAX_TIER",
           "SCAFFOLDS", "Section", "TRACK_PHRASE", "known_keys", "registry_fields",
           "save_class", "scaffold", "scaffold_list", "schema", "unclassified",
           "validate_class", "validate_effect"]
