"""Who can cast what, how often, and how hard it is to resist.

Three thousand spells have been sitting in `content/spells/` as data nothing could use. The
wizard and the cleric shipped as a d6 and a d8 with a skill list and no magic at all, which
made half the Core Rulebook's classes unplayable in an app about playing Pathfinder.

**What this module does and does not decide.** It owns everything derivable from the sheet
and the spell's structured fields: how many slots a caster has, what their caster level is,
what a spell's save DC is, whether they may cast it at all. It does **not** derive what a
spell *does*. A spell's mechanics live in its prose — three thousand paragraphs of English —
and a parser guessing at them would produce confident, wrong numbers, which is the single
failure mode `CLAUDE.md` warns about most. The engine computes the DC and the caster level
and hands the rest to the GM to narrate; anything mechanical the GM then declares comes back
through `damage`, `condition` or `save` and is validated like everything else.

That is a real boundary, not a placeholder. It is the same one the app already draws around
weapon damage: the sheet decides the numbers, the fiction decides that a number is called
for.
"""
from __future__ import annotations

# Slots per day for a full caster, by class level then spell level 0-9. The wizard's table
# from Core Rulebook 7-2; the cleric's is the same shape, plus a domain slot per level.
#
# Typed out rather than derived because it is not regular — 0-level slots stop at 4, the
# first slot of each new spell level arrives on its own schedule, and every attempt to
# generate it produces a table that is right for eight levels and wrong for the rest.
FULL_CASTER = [
    [3, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [4, 2, 0, 0, 0, 0, 0, 0, 0, 0],
    [4, 2, 1, 0, 0, 0, 0, 0, 0, 0],
    [4, 3, 2, 0, 0, 0, 0, 0, 0, 0],
    [4, 3, 2, 1, 0, 0, 0, 0, 0, 0],
    [4, 3, 3, 2, 0, 0, 0, 0, 0, 0],
    [4, 4, 3, 2, 1, 0, 0, 0, 0, 0],
    [4, 4, 3, 3, 2, 0, 0, 0, 0, 0],
    [4, 4, 4, 3, 2, 1, 0, 0, 0, 0],
    [4, 4, 4, 3, 3, 2, 0, 0, 0, 0],
    [4, 4, 4, 4, 3, 2, 1, 0, 0, 0],
    [4, 4, 4, 4, 3, 3, 2, 0, 0, 0],
    [4, 4, 4, 4, 4, 3, 2, 1, 0, 0],
    [4, 4, 4, 4, 4, 3, 3, 2, 0, 0],
    [4, 4, 4, 4, 4, 4, 3, 2, 1, 0],
    [4, 4, 4, 4, 4, 4, 3, 3, 2, 0],
    [4, 4, 4, 4, 4, 4, 4, 3, 2, 1],
    [4, 4, 4, 4, 4, 4, 4, 3, 3, 2],
    [4, 4, 4, 4, 4, 4, 4, 4, 3, 3],
    [4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
]

# The sorcerer's slots (Core Table 3-14), which are not the wizard's with a delay: more
# of them, arriving later, and a new spell level every even level rather than every odd.
# The 0-level column is not in the book's table (a sorcerer's cantrips "do not consume
# any slots"); the four kept here are never spent — `at_will` exempts level 0 from every
# slot check and every spend — and survive only so the table is the same shape as the
# others. Typed out for the same reason FULL_CASTER is: every attempt to generate these
# tables is right for eight levels and wrong after.
SPONTANEOUS_FULL = [
    [4, 3, 0, 0, 0, 0, 0, 0, 0, 0],
    [4, 4, 0, 0, 0, 0, 0, 0, 0, 0],
    [4, 5, 0, 0, 0, 0, 0, 0, 0, 0],
    [4, 6, 3, 0, 0, 0, 0, 0, 0, 0],
    [4, 6, 4, 0, 0, 0, 0, 0, 0, 0],
    [4, 6, 5, 3, 0, 0, 0, 0, 0, 0],
    [4, 6, 6, 4, 0, 0, 0, 0, 0, 0],
    [4, 6, 6, 5, 3, 0, 0, 0, 0, 0],
    [4, 6, 6, 6, 4, 0, 0, 0, 0, 0],
    [4, 6, 6, 6, 5, 3, 0, 0, 0, 0],
    [4, 6, 6, 6, 6, 4, 0, 0, 0, 0],
    [4, 6, 6, 6, 6, 5, 3, 0, 0, 0],
    [4, 6, 6, 6, 6, 6, 4, 0, 0, 0],
    [4, 6, 6, 6, 6, 6, 5, 3, 0, 0],
    [4, 6, 6, 6, 6, 6, 6, 4, 0, 0],
    [4, 6, 6, 6, 6, 6, 6, 5, 3, 0],
    [4, 6, 6, 6, 6, 6, 6, 6, 4, 0],
    [4, 6, 6, 6, 6, 6, 6, 6, 5, 3],
    [4, 6, 6, 6, 6, 6, 6, 6, 6, 4],
    [4, 6, 6, 6, 6, 6, 6, 6, 6, 6],
]

# The bard's six levels (Core Table 3-4). Spell levels 7-9 stay zero: the columns exist
# so every progression is the same shape and nothing indexes past the end.
SIX_LEVEL = [
    [4, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [4, 2, 0, 0, 0, 0, 0, 0, 0, 0],
    [4, 3, 0, 0, 0, 0, 0, 0, 0, 0],
    [4, 3, 1, 0, 0, 0, 0, 0, 0, 0],
    [4, 4, 2, 0, 0, 0, 0, 0, 0, 0],
    [4, 4, 3, 0, 0, 0, 0, 0, 0, 0],
    [4, 4, 3, 1, 0, 0, 0, 0, 0, 0],
    [4, 4, 4, 2, 0, 0, 0, 0, 0, 0],
    [4, 5, 4, 3, 0, 0, 0, 0, 0, 0],
    [4, 5, 4, 3, 1, 0, 0, 0, 0, 0],
    [4, 5, 4, 4, 2, 0, 0, 0, 0, 0],
    [4, 5, 5, 4, 3, 0, 0, 0, 0, 0],
    [4, 5, 5, 4, 3, 1, 0, 0, 0, 0],
    [4, 5, 5, 4, 4, 2, 0, 0, 0, 0],
    [4, 5, 5, 5, 4, 3, 0, 0, 0, 0],
    [4, 5, 5, 5, 4, 3, 1, 0, 0, 0],
    [4, 5, 5, 5, 4, 4, 2, 0, 0, 0],
    [4, 5, 5, 5, 5, 4, 3, 0, 0, 0],
    [4, 5, 5, 5, 5, 5, 4, 0, 0, 0],
    [4, 5, 5, 5, 5, 5, 5, 0, 0, 0],
]

# Paladins and rangers (Core Tables 3-12 and 3-13): four spell levels, nothing at all
# before class level 4. The book prints two different things in this table: "—" (no
# access to that spell level) and "0" (access, but only the bonus spells a high Charisma
# or Wisdom gives). Until 2026-10-05 both were stored as 0 and `slots_for` skipped a zero
# base, so the bonus spell vanished with it: measured, a paladin with Cha 18 had no slot
# at 4th (the book: one bonus 1st), none at 2nd level at 7th, none at 3rd at 10th — and a
# 13th-level paladin had a 4th-level slot the book does not give (docs/class-audit.md D9).
# PCGen and Foundry draw the same line: PCGen's `getNumFromCastList` answers -1 for an
# absent cell and 0 for a printed 0, adding the ability bonus only to the second;
# Foundry's table holds a 0 and leaves the absent level undefined. So here "—" is `NO`
# (-1) and "0" is 0, and `_has_access` is the one place that tells them apart.
NO = -1
FOUR_LEVEL = [
    [0, NO, NO, NO, NO, 0, 0, 0, 0, 0],
    [0, NO, NO, NO, NO, 0, 0, 0, 0, 0],
    [0, NO, NO, NO, NO, 0, 0, 0, 0, 0],
    [0, 0, NO, NO, NO, 0, 0, 0, 0, 0],
    [0, 1, NO, NO, NO, 0, 0, 0, 0, 0],
    [0, 1, NO, NO, NO, 0, 0, 0, 0, 0],
    [0, 1, 0, NO, NO, 0, 0, 0, 0, 0],
    [0, 1, 1, NO, NO, 0, 0, 0, 0, 0],
    [0, 2, 1, NO, NO, 0, 0, 0, 0, 0],
    [0, 2, 1, 0, NO, 0, 0, 0, 0, 0],
    [0, 2, 1, 1, NO, 0, 0, 0, 0, 0],
    [0, 2, 2, 1, NO, 0, 0, 0, 0, 0],
    [0, 3, 2, 1, 0, 0, 0, 0, 0, 0],
    [0, 3, 2, 1, 1, 0, 0, 0, 0, 0],
    [0, 3, 2, 2, 1, 0, 0, 0, 0, 0],
    [0, 3, 3, 2, 1, 0, 0, 0, 0, 0],
    [0, 4, 3, 2, 1, 0, 0, 0, 0, 0],
    [0, 4, 3, 2, 2, 0, 0, 0, 0, 0],
    [0, 4, 3, 3, 2, 0, 0, 0, 0, 0],
    [0, 4, 4, 3, 3, 0, 0, 0, 0, 0],
]
# The tables whose printed 0 means "bonus spells only". Every other table writes a 0 for
# a level not reached (the wizard's 9th at 1st), and the paladin's 0-level column and its
# 5th-9th are not spell levels it has at all — so only spell levels 1-4 of this table read
# a 0 as access.
_ZERO_IS_ACCESS = {"four_level": range(1, 5)}


def _has_access(progression: str, spell_level: int, base: int) -> bool:
    """Whether a table cell gives this spell level at all: a positive count always; a
    printed 0 only in a table whose 0 means bonus-spells-only."""
    if base > 0:
        return True
    return base == 0 and spell_level in _ZERO_IS_ACCESS.get(progression, ())

PROGRESSIONS = {"full": FULL_CASTER, "spontaneous_full": SPONTANEOUS_FULL,
                "six_level": SIX_LEVEL, "four_level": FOUR_LEVEL}

# --- what a spontaneous caster KNOWS, which is a different table from what they cast ---
#
# Item 42 of the 2026-09-19 play-test: `creation.SPELLS_KNOWN` gave a sorcerer `2` and a
# bard `4` as ONE cap covering spell levels 0 and 1 together, so the forge offered 279
# spells across both levels against two picks — and a player could spend both on cantrips
# and begin play with **no first-level spell at all**. The book gives both classes four
# cantrips AND two 1st-level spells: two separate allowances.
#
#   "A sorcerer begins play knowing four 0-level spells and two 1st-level spells of her
#    choice." (d20pfsrd, Sorcerer)
#   "A bard begins play knowing four 0-level spells and two 1st-level spells of the
#    bard's choice." (d20pfsrd, Bard)
#
# Typed out for all twenty levels rather than derived, for exactly the reason the slot
# tables above are: it is not regular, and CLAUDE.md's warning that a table like this is
# "90% right from memory" is why both were fetched from the SRD rather than recalled.
# Row index is class level - 1; column index is spell level.
SORCERER_KNOWN = [
    [4, 2, 0, 0, 0, 0, 0, 0, 0, 0],
    [5, 2, 0, 0, 0, 0, 0, 0, 0, 0],
    [5, 3, 0, 0, 0, 0, 0, 0, 0, 0],
    [6, 3, 1, 0, 0, 0, 0, 0, 0, 0],
    [6, 4, 2, 0, 0, 0, 0, 0, 0, 0],
    [7, 4, 2, 1, 0, 0, 0, 0, 0, 0],
    [7, 5, 3, 2, 0, 0, 0, 0, 0, 0],
    [8, 5, 3, 2, 1, 0, 0, 0, 0, 0],
    [8, 5, 4, 3, 2, 0, 0, 0, 0, 0],
    [9, 5, 4, 3, 2, 1, 0, 0, 0, 0],
    [9, 5, 5, 4, 3, 2, 0, 0, 0, 0],
    [9, 5, 5, 4, 3, 2, 1, 0, 0, 0],
    [9, 5, 5, 4, 4, 3, 2, 0, 0, 0],
    [9, 5, 5, 4, 4, 3, 2, 1, 0, 0],
    [9, 5, 5, 4, 4, 4, 3, 2, 0, 0],
    [9, 5, 5, 4, 4, 4, 3, 2, 1, 0],
    [9, 5, 5, 4, 4, 4, 3, 3, 2, 0],
    [9, 5, 5, 4, 4, 4, 3, 3, 2, 1],
    [9, 5, 5, 4, 4, 4, 3, 3, 3, 2],
    [9, 5, 5, 4, 4, 4, 3, 3, 3, 3],
]

BARD_KNOWN = [
    [4, 2, 0, 0, 0, 0, 0, 0, 0, 0],
    [5, 3, 0, 0, 0, 0, 0, 0, 0, 0],
    [6, 4, 0, 0, 0, 0, 0, 0, 0, 0],
    [6, 4, 2, 0, 0, 0, 0, 0, 0, 0],
    [6, 4, 3, 0, 0, 0, 0, 0, 0, 0],
    [6, 4, 4, 0, 0, 0, 0, 0, 0, 0],
    [6, 5, 4, 2, 0, 0, 0, 0, 0, 0],
    [6, 5, 4, 3, 0, 0, 0, 0, 0, 0],
    [6, 5, 4, 4, 0, 0, 0, 0, 0, 0],
    [6, 5, 5, 4, 2, 0, 0, 0, 0, 0],
    [6, 6, 5, 4, 3, 0, 0, 0, 0, 0],
    [6, 6, 5, 4, 4, 0, 0, 0, 0, 0],
    [6, 6, 5, 5, 4, 2, 0, 0, 0, 0],
    [6, 6, 6, 5, 4, 3, 0, 0, 0, 0],
    [6, 6, 6, 5, 4, 4, 0, 0, 0, 0],
    [6, 6, 6, 5, 5, 4, 2, 0, 0, 0],
    [6, 6, 6, 6, 5, 4, 3, 0, 0, 0],
    [6, 6, 6, 6, 5, 4, 4, 0, 0, 0],
    [6, 6, 6, 6, 5, 5, 4, 0, 0, 0],
    [6, 6, 6, 6, 6, 5, 5, 0, 0, 0],
]

KNOWN_TABLES = {"sorcerer": SORCERER_KNOWN, "bard": BARD_KNOWN}

# Which classes cast, off what, and from whose list.
#
# `prepared` casters fix their spells in the morning and a slot holds one named spell;
# `spontaneous` casters keep a small list and spend any slot on any of it. The distinction
# is the whole difference between a wizard and a sorcerer and it changes what a slot *is*,
# which is why it is a field rather than a subclass.
CASTERS: dict[str, dict] = {
    "wizard": {
        "ability": "int", "kind": "prepared", "progression": "full",
        "list": "wizard", "prepare_from": "spellbook",
        # "A wizard begins play with a spellbook containing all 0-level wizard spells."
        # A GRANT, not a choice: these levels arrive whole and are not counted against
        # any picking budget (`creation.allowance`). Declared here rather than as a
        # literal in the forge, so a homebrew class that grants its own cantrips says so
        # in the same place it says everything else about how it casts.
        "grants_levels": [0],
        # "Each time a character attains a new wizard level, he gains two spells of his
        # choice to add to his spellbook. The two free spells must be of spell levels he
        # can cast." (CRB, Wizard.) Read by `learning`, never by class name.
        "learns_per_level": 2,
        "note": "A wizard prepares from the book they carry; losing it is losing the spells.",
    },
    "cleric": {
        "ability": "wis", "kind": "prepared", "progression": "full",
        "list": "cleric", "prepare_from": "list",
        "note": "A cleric prepares from the whole cleric list — their god is the book.",
    },
    "druid": {
        "ability": "wis", "kind": "prepared", "progression": "full",
        "list": "druid", "prepare_from": "list",
        "note": "A druid prepares from the whole druid list — the wild is the book.",
    },
    # `prepare_from: "known"`: the spellbook field holds the spells *known*, there is no
    # preparing, and any slot casts any of them. That reuse is deliberate — a sorcerer's
    # repertoire and a wizard's book are the same data with a different verb — and it is
    # what keeps `spellbook` meaning one thing in the save file.
    "sorcerer": {
        "ability": "cha", "kind": "spontaneous", "progression": "spontaneous_full",
        "list": "sorcerer", "prepare_from": "known", "known": "sorcerer",
        # One known spell exchanged at 4th and every even level after (`swaps`).
        "swap": {"from": 4, "every": 2},
        "note": "A sorcerer knows few spells and casts any of them from any slot.",
    },
    "bard": {
        "ability": "cha", "kind": "spontaneous", "progression": "six_level",
        "list": "bard", "prepare_from": "known", "known": "bard",
        # At 5th and every third level after, a spell a level below his best (`swaps`).
        "swap": {"from": 5, "every": 3, "below_highest": 1},
        "note": "Six spell levels, known rather than prepared, off Charisma.",
    },
    "paladin": {
        "ability": "cha", "kind": "prepared", "progression": "four_level",
        "list": "paladin", "prepare_from": "list",
        "note": ("Four spell levels from class level 4; at 4th, 7th, 10th and 13th a "
                 "new spell level brings only the bonus spells a high score gives."),
    },
    "ranger": {
        "ability": "wis", "kind": "prepared", "progression": "four_level",
        "list": "ranger", "prepare_from": "list",
        "note": ("Four spell levels from class level 4; at 4th, 7th, 10th and 13th a "
                 "new spell level brings only the bonus spells a high score gives."),
    },
}


def caster_data(actor) -> dict:
    """How this creature casts, or `{}` for the ones that do not.

    Read off the class, and off the class file rather than only this table, so a homebrew
    class that declares `casting` gets it without an edit here.
    """
    cls = actor.class_data or {}
    declared = cls.get("casting")
    if isinstance(declared, dict) and declared:
        return declared
    return CASTERS.get((actor.char_class or "").strip().lower(), {})


def is_caster(actor) -> bool:
    return bool(caster_data(actor))


def casting_ability(actor) -> str:
    return caster_data(actor).get("ability", "")


def caster_level(actor) -> int:
    """Caster level, which is class level for a single-classed character.

    Its own function because it stops being class level the moment anything multiclasses
    or takes a prestige class, and every DC and duration in the game reads it.
    """
    if not is_caster(actor):
        return 0
    return max(0, int(actor.level))


def highest_spell_level(actor) -> int:
    """The best spell level this caster has a slot for, before bonus spells.

    Bonus slots are deliberately excluded: 1e grants them for levels you already have
    access to, and a high Intelligence does not let a 1st-level wizard cast fireball.
    """
    return highest_spell_level_at(actor, int(actor.level or 0))


def highest_spell_level_at(actor, class_level: int) -> int:
    """`highest_spell_level` as it stood at some class level — the level-up picks ask it
    of the level each pick was earned at, not only of today's."""
    data = caster_data(actor)
    # `data.get("progression", "full")` on an empty dict answers "full", which handed the
    # wizard's whole table to every rogue and fighter in the game. The default is only a
    # default *for a caster*.
    if not data:
        return 0
    table = PROGRESSIONS.get(data.get("progression", "full"))
    if not table or int(class_level or 0) < 1:
        return 0
    row = table[min(int(class_level), len(table)) - 1]
    progression = str(data.get("progression", "full"))
    return max((i for i, n in enumerate(row) if _has_access(progression, i, n)), default=0)


def bonus_slots(ability_mod: int, spell_level: int) -> int:
    """Extra slots from a high casting ability.

    "You get one bonus spell of a given level if your ability modifier is at least equal to
    that level, plus one more for every four points beyond." 0-level spells never get one.
    """
    if spell_level < 1 or ability_mod < spell_level:
        return 0
    return (ability_mod - spell_level) // 4 + 1


def can_cast_level(actor, spell_level: int) -> bool:
    """1e: "to cast a spell, you must have an ability score of at least 10 + the spell
    level" — a wizard with Intelligence 11 never casts a 2nd-level spell however high they
    get."""
    if spell_level <= 0:
        return True
    ability = casting_ability(actor)
    return bool(ability) and actor.ability_score(ability) >= 10 + spell_level


def slots_for(actor) -> dict[int, int]:
    """Slots per day by spell level, base plus bonus, for the levels they can reach."""
    data = caster_data(actor)
    if not data:
        return {}
    table = PROGRESSIONS.get(data.get("progression", "full"))
    if not table or actor.level < 1:
        return {}

    row = table[min(int(actor.level), len(table)) - 1]
    progression = str(data.get("progression", "full"))
    mod = actor.ability_mod(data.get("ability", "int"))
    out: dict[int, int] = {}
    for level, base in enumerate(row):
        if not _has_access(progression, level, base):
            continue
        if not can_cast_level(actor, level):
            continue
        # A bonus-only row (the paladin's printed 0) gives a slot only when the ability
        # earns one: Cha 10 at 4th casts nothing, Cha 12 casts one.
        count = max(0, base) + bonus_slots(mod, level)
        if count > 0:
            out[level] = count
    return out


def spells_known(actor) -> dict[int, int]:
    """How many spells this caster KNOWS at each spell level, or {} for the rest.

    A different table from `slots_for`, and that is the whole of item 42: what a
    spontaneous caster knows and what they can cast in a day are two progressions, and
    folding them into one number let a 1st-level sorcerer spend both picks on cantrips
    and start the game unable to cast anything at all.

    Read through `caster_data`, so a homebrew class that declares
    `casting: {"known": "sorcerer"}` — or its own table under a name in `KNOWN_TABLES` —
    gets it without an edit here, exactly as `progression` already works.

    Prepared casters answer {}: a wizard's book and a cleric's list are not this
    question. The wizard's own first-level allowance is a formula and lives with the
    rest of character creation.
    """
    return known_row(caster_data(actor), int(getattr(actor, "level", 0) or 0))


def known_row(data: dict, level: int) -> dict[int, int]:
    """The same answer for a class that has no actor yet — the forge, before a character
    exists. Takes the `casting` block rather than a class id so a homebrew class's own
    declaration is honoured by both doors."""
    table = KNOWN_TABLES.get(str((data or {}).get("known") or ""))
    if not table or int(level or 0) < 1:
        return {}
    row = table[min(int(level), len(table)) - 1]
    return {lvl: n for lvl, n in enumerate(row) if n > 0}


def domain_slots_for(actor) -> dict[int, int]:
    """The extra slot a cleric's domains give at each spell level above orisons.

    The Core Rulebook: "A cleric also gets one domain spell slot for each level of cleric
    spell she can cast, from 1st on up. Each day, a cleric can prepare one of the spells
    from her two domains in that slot." Orisons get none.

    Held apart from `slots_for` rather than added into it, because a domain slot is not
    interchangeable with an ordinary one — only a domain spell may go in it, and spontaneous
    cure conversion may never spend it (`casting.sacrifice_for` skips it for that reason).
    The panel shows it as its own row for the same reason: a cleric who sees "4 of 4" and
    can only use three of them for what she wants has been told something false.
    """
    from . import domains as domains_mod

    if not domains_mod.of(actor):
        return {}
    return {level: 1 for level in slots_for(actor) if level > 0}


# --- what a choice adds to casting ----------------------------------------------------------
#
# Measured 2026-10-05 (docs/class-audit.md §3): every wizard was an unnamed universalist —
# no specialist slot, opposition schools free — and a sorcerer's bloodline spells were
# never known, though the corpus carries all of them. And the cleric's domain slot was a
# number on the Spells tab with no way to prepare anything into it and no way to cast from
# it. How the builders do it (searched before this was written; Foundry PF1's
# spellcasting-model.mjs and PCGen's SpellSupportForPCClass.java, read 2026-10-05):
#
#   * the specialist's slot and the cleric's domain slot are ONE mechanism in Foundry —
#     "Domain/School Slots", a separate count per spell level that only flagged spells
#     use. Its changelog is the warning: 0.75.11 made domain/school spells "not cost any
#     spell slots", uncapped, and a week later 0.76.1 replaced that with a counted pool.
#     So here: a pool per level ("domain slot 3", "school slot 3"), prepared copies kept
#     under "domain:<id>" / "school:<id>", and only a spell the choice allows goes in.
#   * opposition schools are a COST, not a ban: Foundry multiplies a restricted spell's
#     slot cost by 2 (`restrictedSpellSlotMultiplier`); the book: "uses two spell slots
#     of that level to prepare". So `slot_cost`, read by everything that counts slots.
#   * bloodline spells are KNOWN without spending a known slot: PCGen's SPELLKNOWN adds
#     them to the known maximum. So they are derived (never written into `spellbook`)
#     and not counted against the Spells Known table.
#
# Which choice gives which is the powers files' to say (content/schools/powers.json
# declares `specialist_slot` and `opposition`; a catalogue entry's `bonus_spells` are a
# bloodline's), so nothing here names a class or a school.

SPECIAL_SLOTS = ("domain", "school")
_ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7",
          "viii": "8", "ix": "9"}
_NAMES: dict = {}


def spell_named(name: str):
    """A spell by the name a catalogue prints — "greater teleport", "summon monster ix" —
    or None. The corpus spells those "Teleport, Greater" and `summon-monster-9`."""
    from . import spells as spells_mod

    every = spells_mod.all_spells()
    if _NAMES.get("of") is not every:
        _NAMES.clear()
        _NAMES["of"] = every
        _NAMES["by"] = {" ".join(str(s.name).lower().replace(",", " ").split()): s.id
                        for s in every.values()}
    words = " ".join(str(name or "").lower().replace(",", " ").split())
    tried = [words]
    parts = words.split()
    if parts and parts[-1] in _ROMAN:
        tried.append(" ".join(parts[:-1] + [_ROMAN[parts[-1]]]))
    if parts and parts[0] in ("greater", "lesser", "mass"):
        tried += [" ".join(parts[1:] + parts[:1])]
    for t in tried:
        sid = _NAMES["by"].get(t) or (t.replace(" ", "-") if t.replace(" ", "-") in every
                                      else None)
        if sid:
            return every[sid]
    return None


def granted_known(actor) -> dict[str, int]:
    """Spells a choice makes known, by id, with the spell level each is cast at: a
    sorcerer's bloodline spell at 3rd, 5th … 19th (the catalogue entry's `bonus_spells`,
    keyed by class level). "These spells are in addition to the number of spells given
    on Table: Sorcerer Spells Known" (CRB) — so they are never in `spellbook` and never
    counted against it. The level is the spell's own on the caster's list, else the
    highest the caster could cast at the class level it arrived (Celestial's bless, a
    cleric spell, is a 1st-level sorcerer spell for her)."""
    data = caster_data(actor)
    if not data or not (getattr(actor, "class_choices", None) or {}):
        return {}
    from . import grantedpowers

    level = int(getattr(actor, "level", 1) or 1)
    out: dict[str, int] = {}
    for src in grantedpowers.sources(actor):
        cat = (src.get("pick") or {}).get("entry") or {}
        for at, name in (cat.get("bonus_spells") or {}).items():
            if not str(at).isdigit() or int(at) > level:
                continue
            spell = spell_named(name)
            if spell is None:
                continue
            on_list = level_on_list(spell, data.get("list", ""))
            out[spell.id] = on_list if on_list is not None else \
                highest_spell_level_at(actor, int(at))
    return out


def _domain_levels(actor) -> dict[str, int]:
    """Every spell this character's domains grant, at its domain level (the lowest)."""
    from . import domains as domains_mod

    out: dict[str, int] = {}
    for lvl in range(1, 10):
        for sid in domains_mod.grants(actor, lvl):
            out.setdefault(sid, lvl)
    return out


def _school_rules(actor) -> tuple[str, set[str], int]:
    """(the specialist school whose slot this caster has or "", the opposition schools,
    what an opposition spell costs in slots)."""
    from . import classes as classes_mod, grantedpowers

    school, opposed, cost = "", set(), 1
    for src in grantedpowers.sources(actor):
        rules = src.get("rules") or {}
        if rules.get("specialist_slot") and src["entry"].get("slot", True) is not False:
            school = src["id"]
        spec = rules.get("opposition") or {}
        if spec.get("choice"):
            opposed = set(classes_mod.chosen_ids(actor, spec["choice"]))
            cost = max(1, int(spec.get("slots", 2) or 2))
    return school, opposed, cost


def specialist_school(actor) -> str:
    """The school a specialist's extra slot holds, or "" (a universalist, a non-wizard)."""
    if caster_data(actor).get("kind") != "prepared":
        return ""
    return _school_rules(actor)[0]


def opposition_schools(actor) -> set[str]:
    return _school_rules(actor)[1]


def slot_cost(actor, spell) -> int:
    """How many slots of its level this spell takes to prepare: two for an opposition
    school's (cantrips included: "an opposition cantrip also takes two cantrip slots"),
    else one."""
    if spell is None or caster_data(actor).get("kind") != "prepared":
        return 1
    school, opposed, cost = _school_rules(actor)
    return cost if _norm_school(getattr(spell, "school", "")) in opposed else 1


def _norm_school(text) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def school_slots_for(actor) -> dict[int, int]:
    """The specialist's extra slot at each spell level from 1st up — "an additional spell
    slot of each spell level he can cast, from 1st on up" (CRB, Wizard)."""
    if not specialist_school(actor):
        return {}
    return {level: 1 for level in slots_for(actor) if level > 0}


def special_slots(actor) -> dict[str, dict[int, int]]:
    """Every slot that only some spells may hold: {"domain": {1: 1, ...}, "school": ...}."""
    out = {}
    for kind, got in (("domain", domain_slots_for(actor)), ("school", school_slots_for(actor))):
        if got:
            out[kind] = got
    return out


def special_pool(kind: str, spell_level: int) -> str:
    return f"{kind} slot {int(spell_level)}"


def special_key(kind: str, spell_id: str) -> str:
    """How a spell prepared in a special slot is held in `prepared`: "domain:fireball"."""
    return f"{kind}:{spell_id}"


def special_level(actor, kind: str, spell) -> int | None:
    """The level this spell takes in a slot of this kind, or None if it may not go there:
    a domain slot takes one of the character's domain spells at its domain level; a
    school slot takes a spell of the specialist school from the book."""
    if spell is None:
        return None
    if kind == "domain":
        return _domain_levels(actor).get(spell.id)
    if kind == "school":
        school = specialist_school(actor)
        if not school or _norm_school(spell.school) != school:
            return None
        if spell.id not in (getattr(actor, "spellbook", None) or []):
            return None
        return level_on_list(spell, caster_data(actor).get("list", ""))
    return None


def special_held(actor, kind: str, spell_level: int) -> int:
    """How many spells are prepared in this kind's slots at this level."""
    from . import spells as spells_mod

    prefix = f"{kind}:"
    n = 0
    for key, count in (getattr(actor, "prepared", None) or {}).items():
        if not str(key).startswith(prefix) or int(count or 0) < 1:
            continue
        try:
            spell = spells_mod.get(str(key)[len(prefix):])
        except KeyError:
            continue
        if special_level(actor, kind, spell) == int(spell_level):
            n += int(count)
    return n


def special_slot_rows(actor) -> list[dict]:
    """The Spells tab's rows for the domain and school slots: `{"kind", "level", "max",
    "left", "held": [{id, name}], "choices": [{id, name}], "blocked"}` — every number and
    sentence the server's, so the page computes nothing."""
    from . import spells as spells_mod

    every = spells_mod.all_spells()
    out = []
    for kind, levels in special_slots(actor).items():
        if kind == "domain":
            pool_of = _domain_levels(actor)
            candidates = {lvl: sorted((sid for sid, at in pool_of.items() if at == lvl),
                                      key=lambda sid: every[sid].name if sid in every else sid)
                          for lvl in levels}
        else:
            candidates = {}
            for sid in getattr(actor, "spellbook", None) or []:
                spell = every.get(sid)
                at = special_level(actor, kind, spell)
                if at is not None:
                    candidates.setdefault(at, []).append(sid)
        for lvl, most in sorted(levels.items()):
            pool = actor.pool(special_pool(kind, lvl)) if hasattr(actor, "pool") else None
            held = [{"id": str(k)[len(kind) + 1:],
                     "name": every[str(k)[len(kind) + 1:]].name}
                    for k, n in (actor.prepared or {}).items()
                    if str(k).startswith(f"{kind}:") and int(n or 0) > 0
                    and str(k)[len(kind) + 1:] in every
                    and special_level(actor, kind, every[str(k)[len(kind) + 1:]]) == lvl]
            choices = [{"id": sid, "name": every[sid].name}
                       for sid in candidates.get(lvl, []) if sid in every]
            blocked = ""
            if choices:
                blocked = special_refusal(actor, kind, every[choices[0]["id"]])
            out.append({"kind": kind, "level": lvl, "max": most,
                        "left": most if pool is None else int(pool.current),
                        "held": held, "choices": choices, "blocked": blocked})
    return out


def special_refusal(actor, kind: str, spell) -> str:
    """Why this spell cannot be prepared into a slot of this kind now, in plain words, or
    "" — the endpoint's rule and the Spells tab's sentence, one source."""
    name = str(getattr(actor, "name", "") or "They")
    slots = special_slots(actor).get(kind) or {}
    what = {"domain": "domain", "school": "school"}.get(kind, kind)
    if not slots:
        return f"{name} has no {what} slots."
    lvl = special_level(actor, kind, spell)
    if lvl is None:
        if kind == "domain":
            return f"{spell.name} is not one of {name}'s domain spells."
        school = specialist_school(actor)
        article = "an" if school[:1] in "aeiou" else "a"
        return (f"{spell.name} is not {article} {school} spell in {name}'s book; only "
                f"one goes in the school slot.")
    if lvl not in slots:
        return f"{name} has no level {lvl} {what} slot yet."
    pool = actor.pool(special_pool(kind, lvl)) if hasattr(actor, "pool") else None
    unspent = slots[lvl] if pool is None else max(0, min(int(pool.current), slots[lvl]))
    if unspent < 1:
        return (f"The level {lvl} {what} slot is spent for today; it comes back after a "
                f"long rest.")
    if special_held(actor, kind, lvl) >= unspent:
        return f"The level {lvl} {what} slot already holds a spell. Unprepare it first."
    return ""

def save_dc(actor, spell_level: int) -> int:
    """10 + the spell's level + the caster's ability modifier.

    The spell's level *on the caster's own list*, not its lowest anywhere: hold person is a
    2nd-level spell for a cleric and a 3rd for a wizard, and using the lower one everywhere
    would quietly make every wizard's DCs a point light.
    """
    data = caster_data(actor)
    return 10 + max(0, int(spell_level)) + actor.ability_mod(data.get("ability", "int"))


def level_on_list(spell, list_name: str) -> int | None:
    """What level this spell sits at for that class, or None if it is not on their list."""
    if not spell or not list_name:
        return None
    return (spell.lists or {}).get(list_name.strip().lower())


def spell_level_for(actor, spell) -> int | None:
    """The level this caster casts the spell at: its level on their own list; else a
    choice's — a bloodline spell's (`granted_known`), or a domain spell off the class list
    at its domain level (a Fire cleric's fireball is a 3rd-level DOMAIN spell; it goes in
    a domain slot and nowhere else, `on_class_list` says which)."""
    found = level_on_list(spell, caster_data(actor).get("list", ""))
    if found is not None or spell is None:
        return found
    got = granted_known(actor).get(spell.id)
    if got is not None:
        return got
    if getattr(actor, "domains", None):
        return _domain_levels(actor).get(spell.id)
    return None


def on_class_list(actor, spell) -> bool:
    """Whether the spell is on the caster's own class list (or known through a choice) —
    what an ordinary slot may hold. A domain spell off the list goes in a domain slot."""
    if spell is None:
        return False
    if level_on_list(spell, caster_data(actor).get("list", "")) is not None:
        return True
    return spell.id in granted_known(actor)


def knows(actor, spell) -> bool:
    """Can this caster reach the spell at all — before asking whether it is prepared.

    A cleric's list is their whole class list; a wizard's is the book they are carrying.
    Getting this the same for both would let a wizard cast anything a cleric could reach.
    A bloodline's spells are known without being in the repertoire, and a domain's are
    reachable through its slot.
    """
    data = caster_data(actor)
    if not data or spell is None:
        return False
    if spell_level_for(actor, spell) is None:
        return False
    if spell.id in granted_known(actor):
        return True
    # "spellbook" and "known" both read `actor.spellbook`; the difference is what casting
    # then asks. A wizard must also have prepared the spell today; a sorcerer casts
    # anything known from any slot, and the prepared check never fires for them.
    if data.get("prepare_from") in ("spellbook", "known"):
        return spell.id in actor.spellbook
    return True


def known_spells(actor, up_to: int | None = None) -> dict[int, list]:
    """Every spell this caster may choose from, by spell level.

    One function for the three things that all needed the same answer and each had their
    own (or, in two cases, none): the Spells panel's list, `judgement.inject_cast`'s
    vocabulary, and the brief. What "known" means is the class's own business —

      * a **wizard** or **sorcerer**: the book or the repertoire they carry, and nothing
        else. A wizard who loses the book has lost the spells.
      * a **cleric**, **druid**, **paladin** or **ranger**: the whole class list, because
        their god or the wild is the book. 1,143 spells for a cleric, of which 179 are
        castable at level 1 — which is why the panel folds by level and the caller passes
        `up_to`.

    Reported 2026-09-19 as "this spells panel should show a list of all known spells as
    well": the panel offered a `+` only on rows already in the book, so a list-caster saw
    a wizard's empty-book message for the life of the character.
    """
    data = caster_data(actor)
    if not data:
        return {}
    from . import spells as spells_mod

    out: dict[int, list] = {}
    everything = spells_mod.all_spells()
    if data.get("prepare_from") in ("spellbook", "known"):
        chosen = [everything.get(sid) for sid in (actor.spellbook or [])]
        for spell in [s for s in chosen if s is not None]:
            lvl = spell_level_for(actor, spell)
            if lvl is not None and (up_to is None or lvl <= up_to):
                out.setdefault(lvl, []).append(spell)
    else:
        want = str(data.get("list") or "").lower()
        for spell in everything.values():
            lvl = level_on_list(spell, want)
            if lvl is not None and (up_to is None or lvl <= up_to):
                out.setdefault(lvl, []).append(spell)
    # And what a choice adds: a bloodline's spells, a domain's spells off the class list
    # (for its slot) — so the panel shows them and the turn's vocabulary hears them.
    extra = dict(granted_known(actor))
    if getattr(actor, "domains", None):
        for sid, lvl in _domain_levels(actor).items():
            extra.setdefault(sid, lvl)
    listed = {s.id for spells in out.values() for s in spells}
    for sid, lvl in extra.items():
        spell = everything.get(sid)
        if spell is None or sid in listed or (up_to is not None and lvl > up_to):
            continue
        if data.get("prepare_from") == "list" and level_on_list(
                spell, data.get("list", "")) is not None:
            continue                     # on the class list at its own level already
        out.setdefault(lvl, []).append(spell)
    for lvl in out:
        out[lvl].sort(key=lambda s: str(s.name).lower())
    return dict(sorted(out.items()))


# --- spells owed for levels gained --------------------------------------------------------
#
# The owner, 2026-10-01: "leveled up as a wizard and did not choose new spells". The Core
# Rulebook: "Each time a character attains a new wizard level, he gains two spells of his
# choice to add to his spellbook. The two free spells must be of spell levels he can
# cast." Nothing in the level-up path asked, so a wizard's book never grew past the forge.
#
# Two shapes, both read off the casting block and neither off a class name:
#
#   book    `learns_per_level: N` — N free spells at every level after the first, each of
#           a spell level castable AT THE LEVEL IT WAS EARNED. A free pick is a different
#           thing from a spell copied out of a scroll, and the book alone cannot tell them
#           apart, so the free picks taken are COUNTED on the actor
#           (`Actor.level_spells_taken`) rather than inferred from the book's length.
#           Hero Lab met exactly this and planned the same split — one table for the
#           per-level free allotment, "categorized for the spell levels you would have
#           had access to at the time", a second for spells bought and copied
#           (forums.wolflair.com, t=50834). D&D Beyond enforces nothing, and its forum
#           has the bug report that follows: a wizard who added every 1st-level spell.
#   known   a Spells Known table (`casting.known`) — the repertoire may hold that many at
#           each spell level; what is owed is the table less what is held. No counter is
#           needed, because the table states the total outright.
#
# Picks are owed until chosen, and survive a save, so a level taken in the night (the
# rest path in rules/engine.py) or before this existed is offered the same as one taken
# from the Class card.


def learns_per_level(actor) -> int:
    """Free spells a book caster writes in at each level after the first. 0 for the rest."""
    try:
        return max(0, int(caster_data(actor).get("learns_per_level") or 0))
    except (TypeError, ValueError):
        return 0


def _castable_at(actor, class_level: int) -> int:
    """The best spell level castable at a class level, Intelligence-gated as today."""
    top = highest_spell_level_at(actor, class_level)
    return max((lvl for lvl in range(top + 1) if can_cast_level(actor, lvl)), default=0)


def infer_level_spells_taken(actor) -> int:
    """How many free level-up spells an older save had already been given.

    A save written before `level_spells_taken` existed cannot say, and Hero Lab warned
    of the same migration: validation added after the fact makes every existing caster
    report an error at once (forums.wolflair.com, t=50834). So it is worked out ONCE, at
    load (`sheet.from_dict`), and written from then on:

        taken = chosen spells in the book - the creation allowance

    clamped to what the levels gained could have given. "Chosen" leaves out the levels
    the class grants whole (a wizard's cantrips). The allowance is the forge's own
    (`creation.allowance`), read against today's Intelligence.

    Where it can err, and which way: an Intelligence raised since creation makes the
    allowance larger, so fewer picks read as taken and more are offered — the player's
    favour. A spell copied into the book from a scroll reads as a pick already taken —
    against the player. Neither is detectable from the save; the second is why the
    counter, not the book, is the record from here on.
    """
    per = learns_per_level(actor)
    if not per or int(getattr(actor, "level", 1) or 1) < 2:
        return 0
    from . import creation, spells as spells_mod
    from .tables import ability_modifier

    data = caster_data(actor)
    granted = {int(x) for x in (data.get("grants_levels") or ())}
    every = spells_mod.all_spells()
    chosen = 0
    for sid in getattr(actor, "spellbook", None) or []:
        sp = every.get(sid)
        lvl = level_on_list(sp, data.get("list", "")) if sp is not None else None
        if lvl is not None and lvl not in granted:
            chosen += 1
    ability = data.get("ability", "int")
    mod = ability_modifier(int((getattr(actor, "abilities", {}) or {}).get(ability, 10)))
    allowance = creation.allowance(str(actor.char_class or ""), 1, mod)
    opening = sum(n for lvl, n in allowance.items() if lvl not in granted)
    owed_ever = per * (int(actor.level) - 1)
    return max(0, min(owed_ever, chosen - opening))


def learning(actor) -> dict:
    """What this caster is owed in new spells right now, and the rule each pick obeys.

    `{"kind": "book"|"known"|"", "owed": n, "picks": [...], "by_level": {...},
    "list": <spell list>}`. For a book, `picks` is one row per spell still owed, oldest
    first: `{"for_level": the class level that earned it, "max_level": the highest
    spell level castable then}`. For a repertoire, `by_level` is how many more it may
    hold at each spell level. `owed` is 0 for everyone with nothing to choose.
    """
    data = caster_data(actor)
    out = {"kind": "", "owed": 0, "picks": [], "by_level": {},
           "list": str(data.get("list") or "")}
    if not data:
        return out
    level = int(getattr(actor, "level", 1) or 1)
    per = learns_per_level(actor)
    if per and data.get("prepare_from") == "spellbook":
        out["kind"] = "book"
        taken = int(getattr(actor, "level_spells_taken", 0) or 0)
        picks = [{"for_level": 2 + j // per,
                  "max_level": _castable_at(actor, 2 + j // per)}
                 for j in range(taken, per * max(0, level - 1))]
        out["picks"], out["owed"] = picks, len(picks)
        return out
    table = known_row(data, level)
    if table and data.get("prepare_from") == "known":
        out["kind"] = "known"
        have: dict[int, int] = {}
        from . import spells as spells_mod

        every = spells_mod.all_spells()
        # A bloodline spell does not fill a known slot ("in addition to the number of
        # spells given on Table: Sorcerer Spells Known"), even when the player had picked
        # the same spell before the bloodline gave it: that pick is owed back.
        granted = granted_known(actor)
        for sid in getattr(actor, "spellbook", None) or []:
            lvl = level_on_list(every.get(sid), data.get("list", ""))
            if lvl is not None and sid not in granted:
                have[lvl] = have.get(lvl, 0) + 1
        out["by_level"] = {lvl: n - have.get(lvl, 0) for lvl, n in sorted(table.items())
                           if n > have.get(lvl, 0) and can_cast_level(actor, lvl)}
        out["owed"] = sum(out["by_level"].values())
    return out


def learnable(actor) -> list:
    """Every spell this caster could write in for what is owed, lowest level first.

    Off the class list, not in the book already, at a level some owed pick allows. The
    page shows these and the server re-checks every one (`learn_problems`): the list is
    a convenience, the refusal is the rule.
    """
    owed = learning(actor)
    if not owed["owed"]:
        return []
    from . import spells as spells_mod

    if owed["kind"] == "book":
        allowed = set(range(max(p["max_level"] for p in owed["picks"]) + 1))
    else:
        allowed = set(owed["by_level"])
    book = set(getattr(actor, "spellbook", None) or []) | set(granted_known(actor))
    found = []
    for spell in spells_mod.all_spells().values():
        lvl = level_on_list(spell, owed["list"])
        if lvl is None or lvl not in allowed or spell.id in book:
            continue
        if not can_cast_level(actor, lvl):
            continue
        found.append((lvl, spell))
    found.sort(key=lambda p: (p[0], str(p[1].name).lower()))
    return found


def learn_problems(actor, spell_ids) -> list[str]:
    """Every reason these spells cannot all go into the book now, with the fix named.

    Empty means `learn` may write them. All at once, like the forge's refusals, so a
    player who chose badly twice reads both reasons the first time.
    """
    from . import spells as spells_mod

    owed = learning(actor)
    name = str(getattr(actor, "name", "") or "This character")
    ids = [str(s).strip().lower() for s in (spell_ids or []) if str(s).strip()]
    if not owed["kind"]:
        return [f"{name} adds no spells for gaining a level."]
    if not ids:
        return ["Choose at least one spell."]
    if not owed["owed"]:
        return [f"{name} has no spells owed for the levels gained. Spells beyond those "
                f"are copied into the book from a scroll or another book."]
    problems: list[str] = []
    if len(set(ids)) != len(ids):
        problems.append("The same spell was chosen twice; choose a different one.")
    if len(ids) > owed["owed"]:
        problems.append(f"That is {len(ids)} spells against {owed['owed']} owed. "
                        f"Choose {owed['owed']}.")
    book = set(getattr(actor, "spellbook", None) or [])
    chosen = []
    for sid in dict.fromkeys(ids):
        try:
            spell = spells_mod.get(sid)
        except KeyError:
            problems.append(f"No spell called {sid!r}.")
            continue
        lvl = level_on_list(spell, owed["list"])
        if spell.id in granted_known(actor):
            problems.append(f"{spell.name} is already known through a class choice (a "
                            f"bloodline spell); choose another.")
            continue
        if lvl is None:
            problems.append(f"{spell.name} is not on the {owed['list']} list.")
            continue
        if spell.id in book:
            problems.append(f"{spell.name} is already in the book; choose another.")
            continue
        if not can_cast_level(actor, lvl):
            ability = casting_ability(actor)
            problems.append(f"{spell.name} is level {lvl}, and a level {lvl} spell needs "
                            f"{ability.title()} {10 + lvl}.")
            continue
        chosen.append((lvl, spell))
    if problems:
        return problems
    if owed["kind"] == "book":
        # The picks are filled oldest first, and each holds a spell no higher than its
        # own level allowed. Pairing the chosen spells, lowest first, with the oldest
        # picks is the best assignment there is — if this fails, every assignment does.
        for (lvl, spell), pick in zip(sorted(chosen, key=lambda p: p[0]), owed["picks"]):
            if lvl > pick["max_level"]:
                problems.append(
                    f"{spell.name} is a level {lvl} spell; the spell owed for reaching "
                    f"level {pick['for_level']} must be level {pick['max_level']} or "
                    f"lower.")
    else:
        counted: dict[int, list] = {}
        for lvl, spell in chosen:
            counted.setdefault(lvl, []).append(spell.name)
        for lvl, names in sorted(counted.items()):
            room = int(owed["by_level"].get(lvl, 0))
            if len(names) > room:
                what = "cantrips" if lvl == 0 else f"level {lvl} spells"
                problems.append(
                    f"{', '.join(names)}: the repertoire already holds every {what[:-1]} "
                    f"it may at this level." if not room else
                    f"{', '.join(names)}: room for {room} more {what}; choose {room}.")
    return problems


def learn(actor, spell_ids) -> tuple[list[str], list[str]]:
    """Write owed spells into the book. `(added ids, [])`, or `([], problems)` and
    nothing written."""
    problems = learn_problems(actor, spell_ids)
    if problems:
        return [], problems
    from . import spells as spells_mod

    kind = learning(actor)["kind"]
    added = []
    for sid in dict.fromkeys(str(s).strip().lower() for s in spell_ids if str(s).strip()):
        spell = spells_mod.get(sid)
        actor.spellbook.append(spell.id)
        added.append(spell.id)
    if kind == "book":
        actor.level_spells_taken = int(getattr(actor, "level_spells_taken", 0) or 0) \
            + len(added)
    return added, []


# The spells a divine caster may reach for without having prepared them. The Core
# Rulebook: "A good cleric… can spontaneously cast a cure spell in place of a prepared
# spell of the same level or higher" — the prepared spell is lost and the cure is cast
# instead. A druid has the same exception for summon nature's ally.
#
# Alignment is deliberately not consulted. The player's own ruling, 2026-09-19: "grab
# whatever the belief system of the world is and let that be enough. don't worry about the
# gods or the alignment." The book's good/evil split decides cure versus INFLICT, and with
# no alignment in play the healing half is the one that ships — which is also the half the
# player asked for: "may use a slot at any time for a healing spell of that slot level".
CONVERTS_TO = {
    "cleric": ("cure ",),
    "druid": ("summon nature's ally", "summon natures ally"),
}


def converts_spontaneously(actor, spell) -> bool:
    """Whether this caster may cast this spell without having prepared it."""
    data = caster_data(actor)
    starts = CONVERTS_TO.get(str(data.get("list") or "").lower())
    if not starts or spell is None:
        return False
    name = str(getattr(spell, "name", "")).strip().lower()
    return any(name.startswith(s) for s in starts)


def sacrifice_for(actor, spell_level: int) -> str:
    """The prepared spell that would be given up to convert, or "".

    "A prepared spell of the same level or higher", and the cheapest one that qualifies, so
    converting never costs a fifth-level slot while a first-level one is sitting there. A
    domain slot is never spent this way — the book says so, and a domain spell is the one
    thing a cleric prepared *for* a reason.
    """
    best, best_level = "", None
    for sid, count in (actor.prepared or {}).items():
        if int(count) < 1 or _is_special(sid):
            continue
        try:
            from . import spells as spells_mod

            level = spell_level_for(actor, spells_mod.get(str(sid)))
        except KeyError:
            continue
        if level is None or level < int(spell_level):
            continue
        if best_level is None or level < best_level:
            best, best_level = str(sid), level
    return best


def prepared_count(actor, spell_id: str) -> int:
    return int(actor.prepared.get(spell_id, 0))


def prepare(actor, spell_id: str, count: int = 1) -> int:
    actor.prepared[spell_id] = prepared_count(actor, spell_id) + max(0, int(count))
    return actor.prepared[spell_id]


def unprepare(actor, spell_id: str, count: int = 1) -> int:
    left = prepared_count(actor, spell_id) - max(0, int(count))
    if left > 0:
        actor.prepared[spell_id] = left
    else:
        actor.prepared.pop(spell_id, None)
    return max(0, left)


# --- the morning's preparation ----------------------------------------------------------
#
# Measured 2026-09-28 (item 21.4): Bobby, a wizard with fifty spells in his book, began the
# campaign with nothing prepared, and the cause under it was worse — `Actor.rest` set
# `prepared = {}` every night, so every prepared caster also WOKE with nothing. Its comment
# guarded against keeping spells already cast, but `_op_cast` has spent the prepared copy
# with the slot since item 25, so the line only destroyed the spells 1e says survive:
# "...the ones that he already had prepared from the previous day and has not yet used"
# (CRB magic chapter). The wipe is gone; this refills the rest.
#
# The shape is Pathfinder: Kingmaker's persistent memorised list, re-prepared on rest
# (community reports; secondary), rather than a blank page each morning — BG3 moved the
# same way. The player's last preparation is `Actor.loadout`; the Spells tab may still
# change it at any time out of a fight, as it always could.

def _level(actor, spell_id: str) -> int | None:
    from . import spells as spells_mod

    try:
        return spell_level_for(actor, spells_mod.get(str(spell_id)))
    except KeyError:
        return None


def remember_loadout(actor) -> None:
    """The preparation the player just made, kept as the one the mornings refill from.
    Called by `/api/spells/prepare` after every change. Domain slots are left out: they are
    never auto-filled. Cantrips are kept since 2026-09-29 — they are prepared like any
    other spell (`at_will`), so the mornings must refill the ones the player chose."""
    actor.loadout = {str(sid): int(n) for sid, n in (actor.prepared or {}).items()
                     if int(n or 0) > 0 and not _is_special(sid)
                     and _level(actor, sid) is not None}


# --- cantrips and orisons: prepared, then at will ----------------------------------------
#
# Every class entry says the same thing in two phrasings (Archives of Nethys, fetched
# 2026-09-29):
#   wizard   "Wizards can prepare a number of cantrips, or 0-level spells, each day, as
#             noted on Table: Wizard under 'Spells per Day.' These spells are cast like any
#             other spell, but they are not expended when cast and may be used again."
#   cleric, druid — the same sentence with "orisons".
#   sorcerer, bard "...learn a number of cantrips... they do not consume any slots and may
#             be used again."
#   paladin, ranger — no 0-level spells at all (their tables start at 1st).
# So a prepared caster's 0-level slots are a count of how many DIFFERENT cantrips they
# may hold today, not charges; a spontaneous caster's cantrips known are all at will.
# Measured before the fix: the engine spent "spell slot 0" per cast (a level 5 wizard's
# Light: 4, 3, 2, 1, 0, then refused) AND skipped the prepared check for level 0, so any
# cantrip in the book was castable — both halves wrong, in opposite directions.

def at_will(spell_level) -> bool:
    """Whether a cast at this spell level spends nothing. 0-level spells only: 1e has no
    other at-will spell level for any class the engine supports."""
    try:
        return int(spell_level) == 0
    except (TypeError, ValueError):
        return False


def _is_special(key) -> bool:
    """A copy prepared in a domain or school slot ("domain:fireball"), held apart from the
    ordinary slots it never fills."""
    return ":" in str(key)


def _held_by_level(actor) -> dict[int, int]:
    """Ordinary slots filled at each level — an opposition-school spell fills two."""
    from . import spells as spells_mod

    held: dict[int, int] = {}
    for sid, n in (actor.prepared or {}).items():
        if _is_special(sid):
            continue
        lvl = _level(actor, sid)
        if lvl is not None and lvl >= 0:
            try:
                cost = slot_cost(actor, spells_mod.get(str(sid)))
            except KeyError:
                cost = 1
            held[lvl] = held.get(lvl, 0) + int(n or 0) * cost
    return held


# --- open slots: preparing into the rest of the day ---------------------------------------
#
# The rule (Archives of Nethys, Core Rulebook, Magic > Arcane Spells, "Preparing Wizard
# Spells", fetched 2026-09-29): "When preparing spells for the day, a wizard can leave some
# of these spell slots open. Later during that day, he can repeat the preparation process
# as often as he likes... He cannot, however, abandon a previously prepared spell to
# replace it with another one or fill a slot that is empty because he has cast a spell in
# the meantime. That sort of preparation requires a mind fresh from rest."
#
# So the room at a level is the slots NOT YET SPENT today, less the spells held in them.
# Measured 2026-09-29 (the owner's screenshot): Ysolde, wizard 1, two level 1 slots, cast
# Burning Hands (`_op_cast` spent the slot AND the prepared copy), and the room check —
# slots per day minus spells held, 2 − 1 — let her prepare Burning Hands again into the
# slot she had just spent. The page then read "1 of 2 level 1 slots left" beside two
# prepared spells, and the next Prepare hit the raw "has 2 level 1 slots and has already
# prepared 2". Every reader of the room now asks `open_slots`, so a spent slot is never
# counted as empty — not by the prepare endpoint, not by the sheet's warning, not by the
# morning (whose pools are refreshed before it runs, so nothing changes there).
#
# Cantrips keep their own rule: at will, never spent (`at_will`), so their room is the
# 0-level count less the cantrips held, whatever has been cast.
#
# The owner's house rule departs from the book in two places (ruling 2026-09-29: "prepare
# is fine whenever for the sake of user experience but once a slot is used is un fillable
# until after a long rest"): preparing and unpreparing are free at any time, with no
# preparation time on the clock (the book's "at least 15 minutes" for a later session is
# not charged), and swapping the spell in an UNSPENT slot is allowed (the book's "cannot
# abandon a previously prepared spell to replace it" is not enforced). What holds is the
# spent slot: unpreparing never touches the pools, so it can never turn a spent slot back
# into an open one; only the night's rest (`rest.night`, `Engine` rest) refills them.

def unspent_slots(actor, spell_level: int) -> int:
    """The slots at this level not yet spent today. The pool is the record; a caster
    whose pools were never defined (a bare test actor) has spent nothing."""
    total = slots_for(actor).get(int(spell_level), 0)
    pool = actor.pool(slot_pool(spell_level)) if hasattr(actor, "pool") else None
    if pool is None:
        return total
    return max(0, min(int(pool.current), total))


def held_at(actor, spell_level: int) -> int:
    """How many prepared spells this caster holds at this level (domain slots apart)."""
    return _held_by_level(actor).get(int(spell_level), 0)


def open_slots(actor, spell_level: int) -> int:
    """How many more spells this prepared caster may prepare at this level right now."""
    lvl = int(spell_level)
    held = _held_by_level(actor).get(lvl, 0)
    if at_will(lvl):
        return max(0, slots_for(actor).get(lvl, 0) - held)
    return max(0, unspent_slots(actor, lvl) - held)


def prepare_refusal(actor, spell_level: int, count: int = 1, spell=None) -> str:
    """Why preparing `count` more at this level is refused, in plain words, or "".

    The Spells tab shows this same sentence beside a disabled Prepare (rules/sheet.py
    sends it per level), so the page and the endpoint cannot disagree about the rule.
    With the spell named, an opposition-school spell needs two open slots for each copy
    ("uses two spell slots of that level to prepare", CRB Wizard)."""
    lvl = int(spell_level)
    room = open_slots(actor, lvl)
    cost = slot_cost(actor, spell) if spell is not None else 1
    if room >= max(1, int(count)) * cost:
        return ""
    if lvl not in slots_for(actor):
        return (f"{actor.name} has no level {lvl} slots: at this level only a high enough "
                f"{casting_ability(actor).title()} gives one.")
    if cost > 1 and room > 0:
        return (f"{spell.name} is of an opposition school and takes {cost} level {lvl} "
                f"slots; {room} {'is' if room == 1 else 'are'} open.")
    if at_will(lvl):
        return (f"No open cantrip slot today: {actor.name} holds "
                f"{slots_for(actor).get(lvl, 0)} cantrips. Unprepare one first.")
    if unspent_slots(actor, lvl) <= 0:
        return (f"Every level {lvl} slot is spent for today; they come back after a "
                f"long rest.")
    if room <= 0:
        return f"No open level {lvl} slot today. Unprepare one first."
    return f"Only {room} open level {lvl} slot{'s' if room != 1 else ''} today."


def empty_slots(actor) -> dict[int, int]:
    """Open slots per spell level (`open_slots`), for the sheet's warning — the 0-level
    ones included, since a cantrip must be prepared to be cast (`at_will`). A slot spent
    today is not empty: it cannot be filled until the next rest.
    {} for spontaneous casters — any slot casts anything they know — and non-casters."""
    if caster_data(actor).get("kind") != "prepared":
        return {}
    out = {}
    for lvl in slots_for(actor):
        room = open_slots(actor, lvl)
        if room > 0:
            out[lvl] = room
    return out


def ensure_prepared(actor, *, kept: dict | None = None, reason: str = "rest") -> dict:
    """Fill a prepared caster's empty slots, in 1e's order. Returns
    {"kept": {id: n}, "added": {id: n}, "empty": {level: n}, "from": "loadout"|"book"|"none"}.

    1. Spontaneous casters and non-casters: nothing to do.
    2. What is still prepared stays (`kept`, default the prepared list as it stands).
    3. Each level's remaining room is refilled from the loadout, the last preparation the
       player made.
    4. No loadout ever (a fresh character) and a caster who prepares from a book: the book,
       in the book's own order, one of each distinct spell before any repeat.
    5. A caster who prepares from the whole list (cleric, druid; 1,143 spells) gets no
       invented choice: the slots stand empty and the warning carries it (owner, Q39).
    Domain slots are never auto-filled.

    The 0-level slots are filled the same way (2026-09-29: the `lvl > 0` this read left
    every wizard's cantrip slots empty on the first morning and every morning after), with
    two differences. A cantrip is at will, so the book fills them one of each distinct
    cantrip and never repeats one. And a loadout that names no cantrip — every loadout
    saved before cantrips were prepared — fills them from the book rather than leaving a
    wizard who rests with no cantrip to cast.
    """
    data = caster_data(actor)
    out = {"kept": {}, "added": {}, "empty": {}, "from": "none", "reason": reason}
    if data.get("kind") != "prepared":
        return out
    if kept is not None:
        actor.prepared = {str(k): int(v) for k, v in kept.items() if int(v or 0) > 0}
    out["kept"] = {k: int(v) for k, v in (actor.prepared or {}).items() if int(v or 0) > 0}
    # The open room, not slots-per-day: a slot spent today is not refilled until a rest
    # (`open_slots`). The rest refreshes the pools before calling this, so a morning sees
    # every slot unspent.
    room = {lvl: open_slots(actor, lvl) for lvl in slots_for(actor)}

    def add(sid: str, lvl: int) -> bool:
        from . import spells as spells_mod

        try:
            cost = slot_cost(actor, spells_mod.get(sid))
        except KeyError:
            cost = 1
        if room.get(lvl, 0) < cost:
            return False
        prepare(actor, sid, 1)
        out["added"][sid] = out["added"].get(sid, 0) + 1
        room[lvl] -= cost
        return True

    loadout = {str(k): int(v) for k, v in (getattr(actor, "loadout", None) or {}).items()}
    # Which levels the book fills: every level with no loadout at all, and the 0-level
    # slots of a loadout that names no cantrip.
    from_book: set[int] = set()
    if loadout:
        out["from"] = "loadout"
        for sid, want in loadout.items():
            lvl = _level(actor, sid)
            if lvl is None or lvl < 0:
                continue
            if data.get("prepare_from") in ("spellbook", "known") \
                    and sid not in (actor.spellbook or []):
                continue
            while prepared_count(actor, sid) < want and add(sid, lvl):
                pass
        if not any(_level(actor, sid) == 0 for sid in loadout):
            from_book = {0}
    elif data.get("prepare_from") == "spellbook":
        out["from"] = "book"
        from_book = set(room)
    if from_book and data.get("prepare_from") == "spellbook":
        by_level: dict[int, list[str]] = {}
        for sid in actor.spellbook or []:
            lvl = _level(actor, sid)
            if lvl is not None and lvl in from_book and lvl in room \
                    and sid not in by_level.get(lvl, []):
                by_level.setdefault(lvl, []).append(str(sid))
        for lvl, ids in by_level.items():
            if at_will(lvl):
                # One of each: a second copy of an at-will cantrip buys nothing, and a
                # cantrip already held is not taken twice.
                for sid in ids:
                    if prepared_count(actor, sid) < 1 and not add(sid, lvl):
                        break
                continue
            # Round after round of the book until a whole round adds nothing: an
            # opposition spell needs two open slots, so one slot left over is not filled
            # by it — and `while room > 0` alone would then loop for ever.
            while room.get(lvl, 0) > 0 and ids:
                if not [sid for sid in ids if add(sid, lvl)]:
                    break
    out["empty"] = empty_slots(actor)
    if not out["added"]:
        out["from"] = "none" if not out["kept"] else out["from"]
    return out


def prepared_said(actor, got: dict) -> str:
    """The rest's tell for the morning's preparation, in words: what was prepared and
    which levels stand empty. No numbers but counts of spells."""
    from . import spells as spells_mod

    bits = []
    if got.get("added"):
        names = []
        for sid, n in got["added"].items():
            try:
                name = spells_mod.get(sid).name
            except KeyError:
                name = sid
            names.append(name + (f" ×{n}" if n > 1 else ""))
        where = " from the book" if got.get("from") == "book" else ""
        bits.append(f"{actor.name} prepares {', '.join(names)}{where}.")
    for lvl, n in sorted((got.get("empty") or {}).items()):
        which = "Cantrip" if at_will(lvl) else f"Level {lvl}"
        bits.append(f"{which} slots stand empty: nothing is prepared in "
                    f"{'one of them' if n == 1 else f'{n} of them'}.")
    return " ".join(bits)


def slot_pool(spell_level: int) -> str:
    """Slots are ordinary resource pools, so they refresh on a night's rest, survive a
    save and show on the sheet without a second mechanism for any of it."""
    return f"spell slot {int(spell_level)}"


def define_slots(actor) -> list[str]:
    """Create or recompute this caster's slots. Idempotent, and safe on a half-spent day —
    `resources.define` recomputes the maximum and leaves the current value alone."""
    from . import resources

    made = []
    for level, count in slots_for(actor).items():
        pool = slot_pool(level)
        resources.define(actor, {"id": pool, "max": str(count), "refresh": "rest.night",
                                 "source": "spellcasting"})
        made.append(pool)
    # The domain and specialist slots, as pools of their own: spent by a cast from them,
    # refilled on a night, and never the ordinary slots' (`special_slots`).
    for kind, levels in special_slots(actor).items():
        for level, count in levels.items():
            pool = special_pool(kind, level)
            resources.define(actor, {"id": pool, "max": str(count), "refresh": "rest.night",
                                     "source": "spellcasting"})
            made.append(pool)
    return made


def slots_left(actor, spell_level: int):
    pool = actor.pool(slot_pool(spell_level))
    return pool.current if pool else 0


def pool_left(actor, pool_id: str) -> int:
    pool = actor.pool(pool_id) if pool_id else None
    return int(pool.current) if pool else 0


def cast_source(actor, spell) -> dict | None:
    """Where a cast of this spell comes from: `{"pool", "key", "cost", "level"}` — the
    slot pool to spend, the prepared copy to use up ("" for none), how many slots, the
    level cast at. None for a prepared caster with no copy of it prepared anywhere.

    A prepared caster's copy is found in the ordinary slots first, then a domain slot,
    then the specialist's school slot; an opposition-school spell spends the two slots it
    was prepared into. A spontaneous caster casts from the ordinary slot of its level.
    """
    lvl = spell_level_for(actor, spell)
    if spell is None or lvl is None:
        return None
    data = caster_data(actor)
    if data.get("kind") != "prepared":
        return {"pool": "" if at_will(lvl) else slot_pool(lvl), "key": "",
                "cost": 0 if at_will(lvl) else 1, "level": lvl}
    if prepared_count(actor, spell.id) > 0 and on_class_list(actor, spell):
        return {"pool": "" if at_will(lvl) else slot_pool(lvl), "key": spell.id,
                "cost": 0 if at_will(lvl) else slot_cost(actor, spell), "level": lvl}
    for kind in SPECIAL_SLOTS:
        key = special_key(kind, spell.id)
        at = special_level(actor, kind, spell)
        if prepared_count(actor, key) > 0 and at is not None:
            return {"pool": special_pool(kind, at), "key": key, "cost": 1, "level": at}
    return None


# --- exchanging a known spell -----------------------------------------------------------------
#
# The audit's D10: "Spontaneous casters cannot swap a known spell (sorcerer at 4, 6, 8 …;
# bard at 5, 8, 11 …). No code path: `learn` only adds." The rules (CRB, read 2026-10-05):
#
#   sorcerer  "Upon reaching 4th level, and at every even-numbered sorcerer level after
#             that... a sorcerer can choose to learn a new spell in place of one she
#             already knows." The new spell's level must be the old one's. (The "at least
#             two levels lower" some remember is 3.5's; Pathfinder's sorcerer has none.)
#   bard      "Upon reaching 5th level, and at every third bard level after that" — the
#             same, and the old spell "must be at least one level lower than the
#             highest-level bard spell the bard can cast."
#
# One swap per such level, and the book says it is made "at the same time that she gains
# new spells known". No builder found enforces that moment (Foundry 10.0 added the swap as
# a text feature; PCGen's data leaves the rule out), and this app never forces a choice
# at level-up (audit §5), so a swap earned is offered until it is used: the levels it was
# used for are the record (`Actor.spell_swaps`). Bloodline spells are never swapped
# ("These spells cannot be exchanged for different spells at higher levels").


def swap_levels(actor) -> list[int]:
    """The class levels at which this caster may exchange a known spell, up to now."""
    spec = caster_data(actor).get("swap") or {}
    if not spec:
        return []
    start, every = int(spec.get("from", 0) or 0), max(1, int(spec.get("every", 1) or 1))
    level = int(getattr(actor, "level", 1) or 1)
    return [n for n in range(start, level + 1, every)] if start else []


def swaps(actor) -> dict:
    """`{"open": [class levels with a swap unused], "used": [...], "below_highest": n,
    "highest": the best spell level castable}` — what the Spells tab offers."""
    spec = caster_data(actor).get("swap") or {}
    used = sorted(int(n) for n in getattr(actor, "spell_swaps", None) or [])
    return {"open": [n for n in swap_levels(actor) if n not in used], "used": used,
            "below_highest": int(spec.get("below_highest", 0) or 0),
            "highest": max(slots_for(actor) or {0: 0})}


def swap_problems(actor, old_id: str, new_id: str) -> list[str]:
    """Every reason this exchange is refused, with the fix named, or []."""
    from . import spells as spells_mod

    name = str(getattr(actor, "name", "") or "This character")
    got = swaps(actor)
    if not caster_data(actor).get("swap"):
        return [f"{name} does not exchange known spells."]
    if not got["open"]:
        nxt = next((n for n in _swap_ladder(actor) if n > int(actor.level)), None)
        return [f"{name} has no exchange owed now"
                + (f"; the next comes at level {nxt}." if nxt else ".")]
    try:
        old = spells_mod.get(str(old_id))
        new = spells_mod.get(str(new_id))
    except KeyError as exc:
        return [str(exc).strip("'\"")]
    problems: list[str] = []
    if old.id not in (getattr(actor, "spellbook", None) or []):
        problems.append(f"{old.name} is not among the spells {name} knows"
                        + (" by choice; a bloodline spell is never exchanged."
                           if old.id in granted_known(actor) else "."))
    old_level = level_on_list(old, caster_data(actor).get("list", ""))
    new_level = level_on_list(new, caster_data(actor).get("list", ""))
    if new_level is None:
        problems.append(f"{new.name} is not on the {caster_data(actor).get('list')} list.")
    elif old_level is not None and new_level != old_level:
        problems.append(f"{new.name} is level {new_level} and {old.name} level {old_level}; "
                        f"an exchange keeps the level.")
    if new.id in (getattr(actor, "spellbook", None) or []) or new.id in granted_known(actor):
        problems.append(f"{name} already knows {new.name}.")
    if old_level is not None and got["below_highest"] \
            and old_level > got["highest"] - got["below_highest"]:
        problems.append(f"Only a spell at least {got['below_highest']} level below the "
                        f"highest {name} casts ({got['highest']}) may be exchanged; "
                        f"{old.name} is level {old_level}.")
    if new_level is not None and not can_cast_level(actor, new_level):
        problems.append(f"{new.name} needs {casting_ability(actor).title()} "
                        f"{10 + new_level}.")
    return problems


def _swap_ladder(actor) -> list[int]:
    spec = caster_data(actor).get("swap") or {}
    start, every = int(spec.get("from", 0) or 0), max(1, int(spec.get("every", 1) or 1))
    return list(range(start, 21, every)) if start else []


def swap(actor, old_id: str, new_id: str) -> tuple[bool, list[str]]:
    """Exchange one known spell for another, spending the oldest open swap. Nothing is
    written unless every check passes."""
    problems = swap_problems(actor, old_id, new_id)
    if problems:
        return False, problems
    from . import spells as spells_mod

    old, new = spells_mod.get(str(old_id)), spells_mod.get(str(new_id))
    actor.spellbook = [new.id if s == old.id else s for s in actor.spellbook]
    actor.spell_swaps = sorted(set(getattr(actor, "spell_swaps", None) or [])
                               | {swaps(actor)["open"][0]})
    return True, []


# --- the spells that affect metal (leatherworking plan §18.5) ---------------------------------
#
# The owner's Q7.3: "armor and weapons both need a metal tag because there are spells that
# affect metal". The tag is `item_tags`' and the creature's standing tags carry it
# (`wears.armour.metal`, `wields.metal`, `carries.metal`, `body.metal`, each with
# `.ferrous`); these are its spell readers, asked by prefix (law 1). The engine's cast door
# runs them (`Engine._metal_temperature`, `_rust`, `_touches`); the numbers are the
# spell documents' (`content/spells/mechanics`), never these functions'.

# Heat metal and chill metal (CRB): "a creature takes full damage if its armor, shield, or
# weapon is affected. The creature takes minimum damage (1 point or 2 points, depending on
# the round) if it's not wearing or wielding such an item."
METAL_FULL = ("wears.armour.metal", "wears.shield.metal", "wields.metal")
METAL_ANY = "carries.metal"

# Shocking grasp (CRB): "+3 bonus on the attack roll if the opponent is wearing metal armor
# (or is carrying a metal weapon or is made of metal)". Carrying read as wielding (the
# plan's §18.5 reading): a sword in its scabbard is not what the spark arcs to. `body.metal`
# answers nothing until the bestiary pass tags iron golems and their kin (plan §5.3).
METAL_TARGET = ("wears.armour.metal", "wields.metal", "body.metal")


def metal_contact(target) -> str:
    """"full" when `target` wears or wields metal, "minimum" when it only carries some,
    "" when it has none on it for heat or chill metal to find."""
    if any(target.has_state(q) for q in METAL_FULL):
        return "full"
    if target.has_state(METAL_ANY):
        return "minimum"
    return ""


def metal_curve(spec: dict, contact: str) -> list[str]:
    """The round-by-round curve this creature takes, round 1 first: the spec's `schedule`
    for "full", its `minimum` for "minimum", [] for no contact."""
    from .effectspec import metal_curve as _curve

    if contact == "full":
        return _curve(spec.get("schedule"))
    if contact == "minimum":
        return _curve(spec.get("minimum"))
    return []


def metal_effect(spec: dict, target, contact: str, *, source: str, origin: str):
    """The ActiveEffect that carries rounds 2 onward of the curve, or None when there are
    none: one `periodic` entry whose `schedule` the one executor spends a round at a time
    (`Actor.run_periodic`), so there is no second ticker. Its clock is the curve's length,
    so out of a fight (where rounds are not played) the world's clock still ends it."""
    from .activeeffect import ActiveEffect

    curve = metal_curve(spec, contact)
    if len(curve) < 2:
        return None
    dtype = str(spec.get("damage_type") or "fire")
    return ActiveEffect(
        name=f"{source} ({'heated' if dtype == 'fire' else 'chilled'} metal)",
        kind="effect", key="metal-temperature", source=source, origin=origin,
        duration="rounds", rounds_left=len(curve),
        payload={"contact": contact, "damage_type": dtype},
        periodic=[{"per": "round", "damage": "0", "damage_type": dtype,
                   "schedule": list(curve[1:])}])


def touch_attack(spell) -> dict | None:
    """The spell's `touch_attack` document, or None (most spells roll no attack)."""
    for spec in getattr(spell, "effects", None) or ():
        if isinstance(spec, dict) and spec.get("type") == "touch_attack":
            return spec
    return None


def touch_terms(spec: dict, target) -> list:
    """The spell's own terms on its touch attack against `target`: shocking grasp's +3
    when the target answers `METAL_TARGET`. Named, so the dice popup says why."""
    from .dice import Modifier

    bonus = int((spec or {}).get("bonus_vs_metal") or 0)
    if bonus and any(target.has_state(q) for q in METAL_TARGET):
        return [Modifier(bonus, "against metal")]
    return []


def rusted_already(actor, suit_id: str) -> int:
    """How much armour class rust has already taken from this suit on this wearer."""
    return sum(int((e.payload or {}).get("lost") or 0) for e in actor.effects
               if e.key == "rust" and (e.payload or {}).get("rusted") == suit_id)


def settle_rust(actor) -> list[dict]:
    """Rust on a suit that is no longer worn leaves its wearer, through the applicator
    (`remove_effects`). Returns `effect_ended` records. The suit does not keep it: no store
    holds damage to a suit's armour class on the suit (a gap, named in `Engine._rust`)."""
    from . import armour as armour_mod

    rust = [e for e in actor.effects if e.key == "rust" and e.origin]
    if not rust:
        return []
    suit = armour_mod.worn_by_kind(actor).get("armour")
    key = str(getattr(actor, "armour", "") or "")
    worn = (str(suit.get("id") or suit.get("name") or key) if isinstance(suit, dict)
            else key).strip().lower() if suit is not None else ""
    out: list[dict] = []
    for e in rust:
        if (e.payload or {}).get("rusted") != worn:
            actor.remove_effects(match=lambda x, e=e: x is e)
            out.append({"kind": "effect_ended", "ref": actor.ref, "what": e.name,
                        "origin": e.origin})
    return out


def _magic(thing) -> bool:
    if not isinstance(thing, dict):
        return False
    if thing.get("magic"):
        return True
    try:
        return int(thing.get("enhancement") or 0) > 0
    except (TypeError, ValueError):
        return False


def rust_reach(actor) -> dict:
    """What rusting grasp can take from `actor`'s worn suit: `{"suit": id, "name": shown,
    "cap": AC still to lose, "share": the metal's whole share}` — or `{"why": ...}` when it
    can take nothing.

    CRB: "destroys 1d6 points of Armor Class gained from metal armor (up to the maximum
    amount of protection the armor offered)"; "magic items made of metal are immune". The
    owner's answer 7 (2026-10-08) on a suit whose body is not metal: only the metal
    pieces' share, the suit's book armour bonus less the plainest suit of its body's own
    substance with no metal in it (studded leather 3 − leather 2 = 1; armoured coat
    4 − 2 = 2), so the leather survives the rust. A suit whose body is metal gives all of
    its armour bonus."""
    from . import armour as armour_mod
    from . import item_tags, states
    from .tables import ARMOUR

    suit = armour_mod.worn_by_kind(actor).get("armour")
    if suit is None:
        return {"why": "wears no armour"}
    if not item_tags.has_material(suit, states.METAL_FERROUS):
        return {"why": "wears no iron"}
    if _magic(suit):
        return {"why": "wears magic armour, which the rust cannot touch"}
    key = str(getattr(actor, "armour", "") or "")
    name = (str(suit.get("name") or key) if isinstance(suit, dict)
            else ARMOUR.get(key, {}).get("name", key))
    suit_id = (str(suit.get("id") or suit.get("name") or key) if isinstance(suit, dict)
               else key).strip().lower()
    main = item_tags.main_material(suit)
    whole = int(actor.armour_stats().get("ac") or 0)
    if main and item_tags.substance_of(main) == "metal":
        share = whole
    else:
        book = int(ARMOUR.get(key, {}).get("ac") or 0)
        share = max(0, min(whole, book - _plainest(item_tags.substance_of(main or ""))))
    cap = max(0, share - rusted_already(actor, suit_id))
    return {"suit": suit_id, "name": name, "share": share, "cap": cap}


def _plainest(substance: str) -> int:
    """The armour bonus of the plainest table suit whose body is `substance` and which has
    no metal in it: what a leather-bodied suit keeps when its metal is gone."""
    from . import item_tags, states
    from .tables import ARMOUR

    best = None
    for key, row in ARMOUR.items():
        if key == "none":
            continue
        pieces = item_tags.default_pieces(key, "armour") or {}
        body = pieces.get("body")
        if not body or item_tags.substance_of(body) != substance:
            continue
        if item_tags.has_material(key, states.METAL):
            continue
        ac = int(row.get("ac") or 0)
        best = ac if best is None else min(best, ac)
    return best or 0


__all__ = [
    "metal_contact", "metal_curve", "metal_effect", "touch_attack", "touch_terms",
    "rust_reach", "rusted_already", "METAL_FULL", "METAL_ANY", "METAL_TARGET",
    "CASTERS", "FULL_CASTER", "PROGRESSIONS", "at_will", "bonus_slots", "can_cast_level",
    "caster_data", "caster_level", "casting_ability", "define_slots", "empty_slots",
    "ensure_prepared", "held_at", "highest_spell_level", "is_caster", "knows",
    "level_on_list", "open_slots", "prepare", "prepare_refusal", "prepared_count", "remember_loadout",
    "save_dc", "slot_pool", "slots_for", "slots_left", "spell_level_for", "unprepare",
    "unspent_slots",
]
