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
# The 0-level column follows the same convention the wizard table set — the book says a
# spontaneous caster's cantrips are at will, the engine models slots, and four is the
# compromise the wizard column already made. Typed out for the same reason FULL_CASTER
# is: every attempt to generate these tables is right for eight levels and wrong after.
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
# before class level 4. The book's "0" rows at levels 4-6 mean bonus-spells-only; the
# engine skips a zero base, so those rows are a slot conservative here — the honest
# alternative was teaching `slots_for` a special case for two rows of two classes.
FOUR_LEVEL = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 1, 0, 0, 0, 0, 0, 0, 0],
    [0, 2, 1, 0, 0, 0, 0, 0, 0, 0],
    [0, 2, 1, 0, 0, 0, 0, 0, 0, 0],
    [0, 2, 1, 1, 0, 0, 0, 0, 0, 0],
    [0, 2, 2, 1, 0, 0, 0, 0, 0, 0],
    [0, 3, 2, 1, 1, 0, 0, 0, 0, 0],
    [0, 3, 2, 1, 1, 0, 0, 0, 0, 0],
    [0, 3, 2, 2, 1, 0, 0, 0, 0, 0],
    [0, 3, 3, 2, 1, 0, 0, 0, 0, 0],
    [0, 4, 3, 2, 1, 0, 0, 0, 0, 0],
    [0, 4, 3, 2, 2, 0, 0, 0, 0, 0],
    [0, 4, 3, 3, 2, 0, 0, 0, 0, 0],
    [0, 4, 4, 3, 3, 0, 0, 0, 0, 0],
]

PROGRESSIONS = {"full": FULL_CASTER, "spontaneous_full": SPONTANEOUS_FULL,
                "six_level": SIX_LEVEL, "four_level": FOUR_LEVEL}

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
        "list": "sorcerer", "prepare_from": "known",
        "note": "A sorcerer knows few spells and casts any of them from any slot.",
    },
    "bard": {
        "ability": "cha", "kind": "spontaneous", "progression": "six_level",
        "list": "bard", "prepare_from": "known",
        "note": "Six spell levels, known rather than prepared, off Charisma.",
    },
    "paladin": {
        "ability": "cha", "kind": "prepared", "progression": "four_level",
        "list": "paladin", "prepare_from": "list",
        "note": "Four spell levels, nothing before class level 4 (5, as modelled).",
    },
    "ranger": {
        "ability": "wis", "kind": "prepared", "progression": "four_level",
        "list": "ranger", "prepare_from": "list",
        "note": "Four spell levels, nothing before class level 4 (5, as modelled).",
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
    data = caster_data(actor)
    # `data.get("progression", "full")` on an empty dict answers "full", which handed the
    # wizard's whole table to every rogue and fighter in the game. The default is only a
    # default *for a caster*.
    if not data:
        return 0
    table = PROGRESSIONS.get(data.get("progression", "full"))
    if not table or actor.level < 1:
        return 0
    row = table[min(int(actor.level), len(table)) - 1]
    return max((i for i, n in enumerate(row) if n > 0), default=0)


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
    mod = actor.ability_mod(data.get("ability", "int"))
    out: dict[int, int] = {}
    for level, base in enumerate(row):
        if base <= 0:
            continue
        if not can_cast_level(actor, level):
            continue
        out[level] = base + bonus_slots(mod, level)
    return out


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
    return level_on_list(spell, caster_data(actor).get("list", ""))


def knows(actor, spell) -> bool:
    """Can this caster reach the spell at all — before asking whether it is prepared.

    A cleric's list is their whole class list; a wizard's is the book they are carrying.
    Getting this the same for both would let a wizard cast anything a cleric could reach.
    """
    data = caster_data(actor)
    if not data or spell is None:
        return False
    if spell_level_for(actor, spell) is None:
        return False
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
    for lvl in out:
        out[lvl].sort(key=lambda s: str(s.name).lower())
    return dict(sorted(out.items()))


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
        if int(count) < 1 or str(sid).startswith("domain:"):
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
    return made


def slots_left(actor, spell_level: int):
    pool = actor.pool(slot_pool(spell_level))
    return pool.current if pool else 0


__all__ = [
    "CASTERS", "FULL_CASTER", "PROGRESSIONS", "bonus_slots", "can_cast_level",
    "caster_data", "caster_level", "casting_ability", "define_slots",
    "highest_spell_level", "is_caster", "knows", "level_on_list", "prepare",
    "prepared_count", "save_dc", "slot_pool", "slots_for", "slots_left", "spell_level_for",
    "unprepare",
]
