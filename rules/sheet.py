"""Characters, and everything the sheet determines.

This is the half of the boundary in docs/intent-protocol.md that the GM agent may never
touch. Every method here returns *itemised* modifiers rather than a total, because the
whole proposition of the app is that 1e's bookkeeping becomes visible instead of trusted.

One class covers the PC and every NPC. A PC derives its numbers from a full build; an NPC
may instead carry flat values from a stat block. Conditions layer on top of both, so
there is one code path and a shaken orc is penalised by exactly the same code as a shaken
player.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import re

from . import goods
from . import houserules
from . import troops as _troops
from .activeeffect import ActiveEffect
from .dice import Modifier, stack
from .tables import (
    ABILITIES, ABILITY_FULL, ABILITY_NAMES, ARMOUR, ARMOUR_SPEED,
    CLASSES, CONDITIONS, FEAT_TARGET_RE,
    MANEUVERS, NON_PROFICIENT_PENALTY, SAVE_ABILITY, SAVES, SHIELDS, SIZES, SKILLS,
    SLOT_ORDER_LEFT, SLOT_ORDER_RIGHT, SLOT_RULES_LIMIT, SLOTS,
    WEAPONS, ENERGY_VS_OBJECTS_HALVED, MATERIALS, ability_modifier, bab_for,
    is_physical, iterative_attacks, material_for, normalise_damage_type, save_for,
)


def _bonus_type(value) -> str:
    """One spelling per bonus type, so "armor" and "armour" collide as 1e intends.

    The stacking rule keys on the type's name; two spellings of the same type would
    quietly stack with each other, which is the exact failure the channel exists to
    stop.
    """
    t = " ".join(str(value or "").split()).strip().lower()
    return {"armor": "armour", "natural armor": "natural armour"}.get(t, t)


class IllegalSheet(ValueError):
    """The build breaks a rule. A wrong sheet poisons every roll that follows, so this
    is raised at load time rather than discovered mid-scene."""


@dataclass
class Condition:
    key: str
    rounds_left: int | None = None  # None = until removed
    source: str = ""

    @property
    def name(self) -> str:
        return CONDITIONS.get(self.key, {}).get("name", self.key.title())

    @property
    def data(self) -> dict:
        return CONDITIONS.get(self.key, {})


@dataclass
class Buff:
    """A timed numeric bonus from something consumed or applied.

    The missing half of the consumable pipeline: `save_mod` and its family were
    "executable" in the taxonomy and had nowhere to land on the actor, so drinking a
    +1 Will tea produced a card, a dose spent, and no change to any roll. Held apart
    from conditions because a condition is a named rules state with its own table of
    penalties, and a buff is one number aimed at one roll.
    """
    kind: str                       # save_mod | skill_mod | ability_mod | combat_mod
    target: str                     # which save/skill/ability/stat
    amount: int = 0
    source: str = ""
    rounds_left: int | None = None  # None = until removed
    note: str = ""


# Rules an actor may be exempted from, by a class feature or a homebrew ruleset. Named
# and listed so an override can be checked at load: a typo in `temp_hp.stacks` would
# otherwise be a feature that simply never happens, with nothing anywhere saying why.
ACTOR_RULES = {
    "nonlethal.counts_temp_hp": (
        "Non-lethal damage does not drop this character until it passes their current hit "
        "points *plus* their temporary hit points. Blood Bond's own wording, and the other "
        "half of the same idea as temp_hp.stacks: the class pays for its abilities in "
        "non-lethal damage, so where the threshold sits is where the class ends."
    ),
    "needs.no_sleep": (
        "This creature does not need to sleep, and never rolls to stay upright however "
        "long it has been awake. A construct, or something stranger."
    ),
    "needs.no_food": (
        "This creature does not need to eat, and never makes a hunger check."
    ),
    "needs.no_water": (
        "This creature does not need to drink, and never makes a thirst check."
    ),
    "heal.overflow_temp_hp": (
        "Healing received at full hit points becomes temporary hit points instead of "
        "vanishing. Blood Bond's own clause: the class pays in hit points, so a cure "
        "with nowhere to land is banked rather than wasted."
    ),
    "temp_hp.stacks": (
        "Temporary hit points from different sources add up instead of the best one "
        "applying. Blood Bending needs this from 1st level: its whole economy is hit "
        "points as a resource, and a Coagulator stacking Blood Sponge over a ward is the "
        "path working as written."
    ),
}


@dataclass
class Item:
    """A thing that can be broken.

    Objects were strings on the sheet — "ring of protection +1" in a slot — which is
    enough to wear something and not enough for anything to happen to it. Acid on a
    scabbard, a sundered blade and a shield that splinters all need the same two numbers
    the Core Rulebook gives every object: hardness, and hit points of its own.
    """
    name: str
    material: str = ""
    hardness: int | None = None
    hp: int | None = None
    hp_max: int | None = None

    def __post_init__(self):
        self.material = self.material or material_for(self.name)
        spec = MATERIALS.get(self.material, MATERIALS["steel"])
        if self.hardness is None:
            self.hardness = spec["hardness"]
        if self.hp_max is None:
            # An inch is the Core Rulebook's unit and most carried gear is about that.
            self.hp_max = max(1, spec["hp_per_inch"])
        if self.hp is None:
            self.hp = self.hp_max

    @property
    def broken(self) -> bool:
        """Half hit points or less is the *broken* condition, which is not destroyed."""
        return 0 < self.hp <= self.hp_max // 2

    @property
    def destroyed(self) -> bool:
        return self.hp <= 0

    def take_damage(self, amount: int, dtype: str = "untyped") -> dict:
        """Hardness first, then the object's hit points.

        Energy is halved against objects before hardness, per the Core Rulebook — except
        acid, which this app needs to bite: an ability whose whole point is ruining
        equipment would otherwise read as a rounding error.
        """
        rolled = max(0, int(amount))
        d = normalise_damage_type(dtype)
        halved = d in ENERGY_VS_OBJECTS_HALVED
        after_energy = rolled // 2 if halved else rolled

        reduced = min(after_energy, self.hardness)
        taken = after_energy - reduced
        was_broken = self.broken
        self.hp = max(0, self.hp - taken)
        return {
            "item": self.name, "rolled": rolled, "type": d, "halved": halved,
            "hardness": self.hardness, "reduced": reduced, "taken": taken,
            "hp": self.hp, "hp_max": self.hp_max,
            "broken": self.broken and not was_broken, "destroyed": self.destroyed,
        }


@dataclass
class TempPool:
    """One source's worth of temporary hit points."""
    amount: int
    source: str = ""
    rounds_left: int | None = None      # None = until spent or dismissed


@dataclass
class Reduction:
    """Damage reduction: `DR 5/silver`, `DR 2/—`.

    `bypass` is what defeats it — a material, an alignment, a damage type — or `""` for
    the `/—` that nothing bypasses. Attacks declare what they are made of through
    `traits`; nothing in the app produces silvered weapons yet, so today every DR either
    applies or is bypassed by a trait the GM stated.
    """
    amount: int
    bypass: str = ""
    source: str = ""

    @property
    def label(self) -> str:
        return f"DR {self.amount}/{self.bypass or '—'}"

    def bypassed_by(self, traits: tuple[str, ...]) -> bool:
        if not self.bypass:
            return False
        return any(self.bypass.lower() == t.strip().lower() for t in traits)


# The two sets that carry a body with them in ordinary English, and nothing else. A world
# that turned on ze/hir gets an empty answer here rather than an invented one — the forge
# asks in that case, which is the only honest way to find out.
_IMPLIED_GENDER = {"she": "woman", "he": "man"}

# The other direction, which is the one the forge uses. Keeping the two questions apart
# was itself part of the bug: a character can be saved as a woman with they/them attached
# and the narrator then has two sources disagreeing about her. A woman is "she", a man is
# "he", and the table that wants anything else says so in the house rules — where the set
# it turns on *is* the answer to both questions at once.
_PRONOUNS_FOR = {"woman": "she/her", "man": "he/him",
                 "female": "she/her", "male": "he/him"}


def gender_from_pronouns(pronouns: str) -> str:
    """"she/her" -> "woman". Anything else -> "", meaning nobody has said."""
    first = str(pronouns or "").split("/")[0].strip().lower()
    return _IMPLIED_GENDER.get(first, "")


def pronouns_for_gender(gender: str) -> str:
    """"woman" -> "she/her". A house-rule set like "ze/hir" is already its own answer."""
    said = " ".join(str(gender or "").split()).lower()
    if "/" in said:
        return said
    return _PRONOUNS_FOR.get(said, "")


# The rungs a creature passes on the way down, cleared together whenever something
# overtakes them. Named once because it is written twice — by `apply_hp_state`'s own death
# threshold and by a unit breaking up — and the three laws' ratchet counts literal condition
# keys for exactly this reason: two copies of a ladder is how one of them goes stale.
_DOWN_THE_LADDER = ("dying", "stable", "unconscious", "disabled")


@dataclass
class Actor:
    ref: str
    name: str
    kind: str = "npc"                       # "pc" or "npc"
    level: int = 1
    char_class: str | None = None
    size: str = "medium"

    abilities: dict[str, int] = field(default_factory=dict)
    # Kept apart from the scores and from each other because they are undone separately:
    # damage heals back over days, drain does not heal at all.
    ability_damage: dict[str, int] = field(default_factory=dict)
    ability_drain: dict[str, int] = field(default_factory=dict)
    ranks: dict[str, int] = field(default_factory=dict)
    feats: list[str] = field(default_factory=list)
    # Every class in the book has one Hit Die per level, so nothing has ever needed to
    # tell HD and level apart. Blood Bending has two, and every "per Hit Die" effect is
    # wrong by a factor of two without this.
    hit_dice_per_level: int = 1

    armour: str = "none"
    shield: str = "none"
    natural_armour: int = 0
    weapons: list[str] = field(default_factory=list)
    equipped: str | None = None

    # Hit points as ROLLED — every hit die taken, before Constitution says what they
    # are worth. `hp_max` is derived from this and the current Con modifier, and is a
    # property rather than a field for the reason law 2 exists: it was mutated in three
    # places and reconciled in one, so the moment a Constitution BUFF could reach
    # `ability_score` the arithmetic came apart. Buff up (nothing recomputes), take Con
    # damage (a delta measured against the buffed modifier), let the buff expire
    # (nothing recomputes), heal the damage (a delta measured against the unbuffed one)
    # — and the character keeps hit points nobody granted. That is "added and hopefully
    # subtracted" exactly, and no amount of care at the call sites removes it. Derived,
    # the question cannot be asked wrongly.
    hp_base: int = 1
    hp: int = 1
    # The one store for everything that is on this creature and will later stop being:
    # conditions, buffs, temporary hit point pools, coatings, ability effects. One
    # applicator (`apply_effect`), one ticker (`tick_effects`). The old per-mechanism
    # views — `conditions`, `buffs`, `temp_pools`, `coating` — are properties over this
    # list, so every reader keeps working while there is only one thing to maintain.
    effects: list[ActiveEffect] = field(default_factory=list)
    # Non-lethal damage, tracked apart from hit points because 1e tracks it apart: it
    # accumulates on its own, it staggers you when it reaches your current hit points and
    # drops you when it passes them, and it heals on a different clock.
    #
    # Blood Bending is the reason this could not wait. Its whole economy is paying for
    # abilities in self-inflicted non-lethal damage, and without a separate pool that
    # payment was indistinguishable from being stabbed.
    nonlethal: int = 0
    # A crowd held as ONE actor: the member template, how many are still standing, and the
    # morale score that says whether they run (`rules/troops.py`). Asked for 2026-09-19 —
    # "a crowd of people should be spawned as a single unit with the combined hp of all its
    # members". Hit points are the 13th Age mob's shared pool, so the ordinary hit-point
    # machinery does the accounting and `take_damage` only has to say how many that killed.
    # `None` for every ordinary creature, which is nearly all of them.
    troop: object | None = None
    # Base land speed in feet, before armour. 30 is a human's; Small races and dwarves
    # have 20. Nothing needed this until the grid arrived — zones have no distance — so a
    # sheet written before this defaults rather than failing to load.
    speed: int = 30
    # Damage reduction, immunity, energy resistance and vulnerability were four more
    # parallel stores — the fifth, sixth, seventh and eighth mechanisms law 2 forbids
    # — and they survived stage 2 because they arrive from a stat block and never
    # expire. Never expiring is exactly what made them wrong: `effectspec` offers all
    # four types, and the catalogue's own `blocked` text admitted the consequence —
    # "nothing wears off yet, so nothing is granted temporarily" — so 123 spells and
    # 13 magic items authored a defence that could only ever land on a creature born
    # with it. A potion of fire resistance was drunk, the dose spent, and nothing
    # happened, with no error anywhere.
    #
    # They are effect kinds now, and the four names are read-only views over the one
    # store, the arrangement `conditions`, `buffs` and `temp_pools` have had since
    # stage 2. An innate defence is an effect with no clock; a granted one has one and
    # wears off through the one ticker.
    # Who this creature is being pulled towards, and what defying them costs. Not a
    # condition: a condition is a state the creature is in, while a compulsion is a
    # relationship to a *particular other creature*, and it has to be able to name them.
    # Compulsions were a fifth timed store with their own add, their own list and
    # their own ticker — law 2's exact prohibition, and the reason a compulsion
    # applied out of a fight lasted until the next fight started: its ticker only
    # ran on the combat rollover. An effect kind now; the view is below.
    # Spells this caster can reach: the wizard's book, or nothing for a cleric whose list
    # is their whole class list. Ids, not names — two spells share a name often enough.
    # Minutes since this character last slept, ate and drank. Minutes rather than hours
    # to match `scene.clock_minutes`, so nothing has to convert at the boundary and no
    # half-hour is ever quietly lost to integer division.
    #
    # Time was free before foraging could take eighteen hours: the clock moved and the
    # body did not know. See rules/survival.py.
    awake_minutes: int = 0
    fed_minutes: int = 0
    watered_minutes: int = 0
    # How many endurance checks each need has already extracted, because 1e's DCs rise by
    # one per check made rather than per hour elapsed.
    thirst_checks: int = 0
    hunger_checks: int = 0
    # The experience ledger. `xp` is what this character has earned; `xp_value` is what
    # defeating them awards — the bestiary's own column, carried onto the actor so a
    # finished fight can settle up without a lookup into a book the scene may not have.
    xp: int = 0
    xp_value: int = 0
    # The bestiary key this creature was made from, when it was made from one. Its
    # display name is the GM's to change; this is not.
    from_template: str = ""
    # Of the raw material carried, how much of each came back perfect. A subset of
    # `inventory`, never larger than it, and spent first when the pot asks for that herb.
    pristine: dict[str, int] = field(default_factory=dict)
    # When each raw ingredient was picked, as the world clock read at the time. Animal
    # parts have 48 hours and plants a week (rules/herbprep.py), and without a
    # timestamp there is nothing for that clock to count from. Ingredients carried
    # before this existed have no entry and are treated as fresh — a save that
    # retroactively spoiled somebody's satchel would be a worse answer than a lenient
    # one.
    picked_at: dict[str, int] = field(default_factory=dict)
    # Ones that were salted at the time. Preserved material does not spoil at all, and
    # it is recorded per ingredient rather than as a fact about the character because
    # whether you had salt is a question about the moment you picked it up.
    preserved: dict[str, bool] = field(default_factory=dict)
    # Schrödinger's pockets: the kit this creature spawned with, unrolled. Stats
    # resolve at spawn because combat needs them instantly; what is IN the pockets
    # stays a claim ({"kit", "wealth", "pockets"}) until the first time anybody
    # actually looks — loot, steal, trade — and is rolled and emptied into the
    # ordinary purse/inventory then, immutable after. Nothing in the transcript can
    # contradict pockets that were never opened, and the watcher gets the whole
    # player turn to garnish the claim before it collapses.
    kit_pending: dict = field(default_factory=dict)
    spellbook: list[str] = field(default_factory=list)
    # Spell id -> how many copies are prepared. A prepared caster may hold the same spell
    # in several slots, which is why this counts rather than being a set.
    prepared: dict[str, int] = field(default_factory=dict)
    # Named rules this actor does not play by. Validated against ACTOR_RULES, so a
    # misspelled override fails loudly instead of silently never applying.
    overrides: dict[str, bool] = field(default_factory=dict)
    # Gear that has been hurt, keyed by item name. Slots and `weapons` stay plain strings:
    # an undamaged sword needs no record, and creating one for every item a character owns
    # would put a hardness and a hit point total beside every rope and every torch.
    gear: dict[str, Item] = field(default_factory=dict)
    # World classes run alongside the character class rather than instead of it, and
    # level on what the character does rather than on their experience total. Keyed by
    # track id: {"herbalist": Progress(level=2, mp=7, ...)}.
    world_classes: dict[str, "Progress"] = field(default_factory=dict)
    # Things this character has made, which are also things they can craft *with*. Keyed
    # by base name and concentration, holding a count: three identical teas are a count
    # of three rather than three objects.
    stock: dict[str, "Stock"] = field(default_factory=dict)
    # Raw materials carried, by ingredient id. Foraging fills it; crafting empties it.
    # A plain count rather than an object: a handful of woundwort is a number, and
    # nothing about a raw herb differs from the next one of its kind.
    inventory: dict[str, int] = field(default_factory=dict)
    # Everything else carried, by the name the fiction gave it. Deliberately open: the
    # tables know a longsword and will never know a lucite crystal, and a game in which
    # the GM can only hand over things the Core Rulebook printed is not a game. See
    # `rules/goods.py` — an unknown item is carried and counted, and says plainly that
    # the engine has no rules for it rather than implying that it has.
    goods: dict[str, int] = field(default_factory=dict)
    # Money, by denomination id. The ratios are 1e's because every price in the shipped
    # tables is; only what the coins are *called* belongs to the world.
    purse: dict[str, int] = field(default_factory=dict)
    # Spendable pools: ki, rage rounds, uses per day, and stacks somebody else put here.
    # A pool with `scope: target` sits on the creature it was applied to, which is why
    # these live on the Actor rather than on whoever created them.
    pools: dict[str, "Pool"] = field(default_factory=dict)

    # WHERE this creature is: a place id from `rules.places`, and the one spatial fact
    # the engine holds about anybody. Every tradition that solved presence — Inform's
    # `parent`, Diku's `IN_ROOM`, LambdaMOO's `.location`, Bevy's `ChildOf` — keeps the
    # relation on the contained thing and derives "who is here" from it; storing a
    # roster on the room is the design Bevy shipped and then replaced, because two
    # copies of one fact desynchronise. Written by exactly two doors, `Scene.add` and
    # `Scene.move`; `Scene.actors` is the view of everyone whose `at` is the party's.
    at: str = ""
    # Whether this creature's last Swim check in the water was made, failed, or never
    # asked for. Three states and not a bool, because the Core Rulebook's table has three
    # answers: a made check is treading water, a failed one is floundering, and nobody
    # having asked is a creature simply in the water — weighed down on the bottom, or
    # floundering if it is not. `None` is the ordinary case and the one a save restores.
    swim_check_made: bool | None = None
    # How many rounds this creature has been under without breathing, and how many
    # Constitution checks it has already failed down there. Counters, moved by
    # `Scene.advance` on the clock everything else moves on; the CHECK belongs to the
    # engine, which is the rule `advance` states in its own comment — it rolls dice, and
    # a counter that is right beats a counter that is wrong.
    held_breath_rounds: int = 0
    drown_failures: int = 0
    # World Bible provenance. The rules race and the world's people are different things:
    # Zhilakai is not a PF1e race, so the sheet carries both and neither pretends to be
    # the other.
    world_entity_id: str | None = None
    world_people_id: str | None = None
    heritage: str = ""
    # The name behind the descriptor, and what a stranger would see. `name` is what the
    # panel shows — "the stranger sharing the step" until he gives it — and `true_name`
    # is the one he gives, drawn at spawn or promotion from the world's own pools
    # (`rules/names.py`). Measured 2026-09-18: asked his name, an NPC called himself
    # "the stranger" — our placeholder — because nothing held a real one, and the woman
    # in the doorway was never described because nothing held a face.
    true_name: str = ""
    appearance: str = ""
    # Whether a beat has ever said what this person looks like. Reported 2026-09-19:
    # "Drenn Ironvale and the merchant are in scene without having been described." Four
    # writers put people into a scene — the opening companion, the keeper behind a
    # counter, a scheme's cast, the `spawn` op — and the face check covered none of them,
    # because it only ever ran over the phrases booked from THIS turn's prose. So the
    # condition it was meant to ask is held here instead of inferred: not described yet,
    # for as long as that is true, and the first beat in which they act, speak or are
    # addressed owes the description.
    described: bool = False
    # Where this character was before the first turn. The id alone; the
    # modifiers, tags and ties are read live off the document.
    background: str = ""
    # The bound ties, as sentences, once the campaign has begun and the world has
    # supplied the people and places the background only had slots for.
    background_ties: list = field(default_factory=list)
    # Which branch of the class this character follows. A list because a class
    # may let you take more than one — Blood Bending declares four and the
    # player may follow one or several. Empty for every class that has none.
    paths: list[str] = field(default_factory=list)
    race: str = "human"
    # Stated, never guessed. The model called Kesst "him" in one sentence and "her" in
    # the next because nothing on the sheet said, so it invented one each time.
    pronouns: str = "they/them"
    # What the character *is*, as opposed to which words are used about them. These are
    # two different facts and the sheet needed both, measured in play: a character whose
    # narration was in the second person the whole time — "your jaw", "your pectoralis
    # major muscles" — was described with a man's body, and no pronoun appeared anywhere
    # in the paragraph for the pronouns field to have any effect on. The model was never
    # told; it was only ever told which words to say when somebody spoke about her.
    #
    # A word, not a flag: "woman", "man", and whatever a world of winged people or
    # constructs needs. Empty means unstated, which describes most of the bestiary and
    # is not a thing to guess at.
    gender: str = ""

    # NPC stat-block shortcuts. When present these replace *derivation*, not conditions.
    flat_skills: dict[str, int] = field(default_factory=dict)
    flat_saves: dict[str, int] = field(default_factory=dict)
    flat_ac: int | None = None
    flat_attack: int | None = None
    flat_damage: str | None = None
    flat_initiative: int | None = None
    flat_cmd: int | None = None

    notes: str = ""

    # Worn magic items, keyed by body slot: {"ring": ["ring of protection +1", None]}.
    # A None is an empty slot that exists — the sheet shows it as a blank to fill, which
    # is the point of drawing the slots at all.
    slots: dict[str, list] = field(default_factory=dict)
    # Crafted gear that is being worn, keyed by the item's own name. The slot lists
    # above stay plain strings — every save written so far holds strings, and the sheet
    # page draws them — so the mechanical half lives here beside them rather than
    # replacing them. A string in a slot with no record contributes nothing, which is
    # exactly what a worn item did before this existed; a record whose name has been
    # taken out of every slot contributes nothing either, because `worn_items` asks the
    # slots and not this dict. That is the whole reason to keep them apart: taking a
    # cloak off has to stop the cloak working, and one dict cannot express "owned but
    # not worn" without a second flag nobody would remember to clear.
    worn: dict[str, dict] = field(default_factory=dict)

    # --- body slots ----------------------------------------------------------------

    def slot_list(self, key: str) -> list:
        """The slots of one kind, created at their default count on first access."""
        if key not in SLOTS:
            raise KeyError(f"no such body slot {key!r}")
        if key not in self.slots:
            self.slots[key] = [None] * SLOTS[key]["count"]
        return self.slots[key]

    def add_slot(self, key: str) -> int:
        """Add another slot of this kind. Returns its index."""
        spec = SLOTS[key]
        current = self.slot_list(key)
        if len(current) >= spec["max"]:
            raise IllegalSheet(
                f"{spec['label']}: {self.name} already has {len(current)}, "
                f"which is the most the sheet holds"
            )
        current.append(None)
        return len(current) - 1

    def remove_slot(self, key: str, index: int) -> None:
        current = self.slot_list(key)
        if not 0 <= index < len(current):
            raise IllegalSheet(f"{key}: no slot {index}")
        if len(current) <= 1:
            raise IllegalSheet(f"{SLOTS[key]['label']}: the last slot cannot be removed")
        current.pop(index)

    def set_slot(self, key: str, index: int, item: str | None) -> None:
        current = self.slot_list(key)
        if not 0 <= index < len(current):
            raise IllegalSheet(f"{key}: no slot {index}")
        current[index] = (item or "").strip() or None

    # --- worn gear that does something ------------------------------------------------

    def worn_items(self) -> list[dict]:
        """The crafted records for everything currently in a slot.

        Asks the slots, not the record dict: a cloak in the wardrobe is not a cloak on
        your shoulders, and the difference has to be readable from the sheet's own
        state rather than from a flag somebody has to remember to clear.
        """
        names = {str(w).strip().lower()
                 for slot in self.slots.values() for w in slot if w}
        return [rec for key, rec in self.worn.items() if key in names]

    def wear(self, record: dict, index: int = 0) -> str:
        """Put a crafted item on. Returns the slot it went into.

        The record says which slot it belongs in — a crafted cloak knows it is worn at
        the shoulders — because the alternative is asking the player to classify their
        own loot, which is a question the maker already answered.
        """
        slot = str(record.get("slot") or "").strip().lower()
        name = str(record.get("name") or "").strip()
        if not name:
            raise IllegalSheet("this item has no name to wear")
        if slot not in SLOTS:
            raise IllegalSheet(f"{name} is not something you wear")
        current = self.slot_list(slot)
        if not 0 <= index < len(current):
            raise IllegalSheet(f"{SLOTS[slot]['label']}: no slot {index}")
        if current[index]:
            raise IllegalSheet(
                f"{SLOTS[slot]['label']} is already holding {current[index]} — "
                f"take that off first")
        current[index] = name
        self.worn[name.strip().lower()] = dict(record)
        return slot

    def take_off(self, name: str) -> bool:
        """Remove a worn item from whatever slot holds it. The record is kept: the
        thing still exists, it is simply not being worn, and its effects stop because
        `worn_items` reads the slots."""
        key = str(name or "").strip().lower()
        found = False
        for slot in self.slots.values():
            for i, w in enumerate(slot):
                if w and str(w).strip().lower() == key:
                    slot[i] = None
                    found = True
        return found

    def _standing_mods(self, kind: str, target: str) -> list["Modifier"]:
        """Modifiers from worn gear — permanent while worn, so not buffs.

        Held apart from `buffs` because a buff has a clock and expires; a ring of
        protection does not, and putting it in the buff list would mean either a
        never-ending buff nothing could clear or a cloak that stopped working after an
        hour. Same four modifier families the effect vocabulary defines, so anything
        an enchantment or a hide can say lands here without a translation table.

        Two sources feed it: crafted records (`worn`), and the magic-item catalogue
        looked up by the plain string in the slot — the ring of protection the sheet
        page used to disclaim. A slot past the rules limit contributes nothing: the
        third ring is worn, not working.
        """
        want = str(target).lower()
        out: list[Modifier] = []

        def read(specs, name: str):
            for spec in specs or []:
                if not isinstance(spec, dict) or spec.get("type") != kind:
                    continue
                if str(spec.get("target", "")).lower() != want:
                    continue
                amount = int(spec.get("amount", 0) or 0)
                if amount:
                    out.append(Modifier(amount, name,
                                        _bonus_type(spec.get("bonus_type"))))

        crafted = {k for k in self.worn}
        for rec in self.worn_items():
            read(rec.get("specs"), str(rec.get("name") or "worn gear"))
        from . import magicitem

        for slot_key, items in self.slots.items():
            limit = SLOT_RULES_LIMIT.get(slot_key, 1)
            for i, item in enumerate(items):
                if not item or i >= limit:
                    continue
                if str(item).strip().lower() in crafted:
                    continue                    # already read as a crafted record
                read(magicitem.worn_specs(str(item)), str(item))
        return out

    # --- the effect engine ---------------------------------------------------------
    #
    # One applicator and one ticker for everything that lands on a creature and later
    # stops. The properties below are read-only views: they let two thousand call
    # sites keep reading `conditions`, `buffs` and `temp_pools` while there is exactly
    # one list to add to, expire from, and save.

    @property
    def conditions(self) -> list[Condition]:
        return [Condition(key=e.key, rounds_left=e.rounds_left, source=e.source)
                for e in self.effects if e.kind == "condition"]

    @property
    def buffs(self) -> list[Buff]:
        out: list[Buff] = []
        for e in self.effects:
            if e.kind != "buff":
                continue
            for m in e.modifiers:
                out.append(Buff(kind=str(m.get("kind", "")),
                                target=str(m.get("target", "")),
                                amount=int(m.get("amount", 0) or 0),
                                source=e.source, rounds_left=e.rounds_left,
                                note=str(m.get("note", ""))))
        return out

    @property
    def temp_pools(self) -> list["TempPool"]:
        return [TempPool(amount=e.amount, source=e.source, rounds_left=e.rounds_left)
                for e in self.effects if e.kind == "temp_hp"]

    # --- the four defences, as views over the one store --------------------------------

    def _defence(self, kind: str) -> list[ActiveEffect]:
        return [e for e in self.effects if e.kind == kind]

    def grant_defence(self, kind: str, against: str, amount: int = 0,
                      bypass: str = "", source: str = "",
                      rounds: int | None = None, origin: str = "") -> ActiveEffect:
        """Put a defence on this creature — innate when `rounds` is None, timed when not.

        The one door for all four. A stat block's `Immune cold` and a potion of fire
        resistance arrive the same way and differ only in whether they carry a clock,
        which is what makes the potion possible at all: before this there was no shape
        for a defence that ENDS, so `consumables` had no branch for any of the four and
        drinking one produced no intents whatsoever.
        """
        return self.apply_effect(ActiveEffect(
            name=source or f"{kind} {against}".strip(), kind=kind,
            # What it is against AND what defeats it: `apply_effect` treats
            # (kind, key, source) as one record, so keying on `against` alone made
            # DR 10/silver and DR 3/— the same record — the second refreshed the first
            # and a creature with two kinds of damage reduction silently had one.
            key=f"{against}|{bypass}", source=source or "", origin=origin,
            amount=int(amount),
            duration="until-dismissed" if rounds is None else "rounds",
            rounds_left=rounds,
            payload={"against": str(against), "amount": int(amount),
                     "bypass": str(bypass or "")}))

    @property
    def immunities(self) -> list[str]:
        """By NAME, not by damage type: most immunities are not damage types — "undead
        traits", "paralysis", "mind-affecting effects" — and `immune_to` answers only
        the damage question, leaving the rest for the save and condition paths."""
        return [str(e.payload.get("against", "")) for e in self._defence("immunity")]

    @immunities.setter
    def immunities(self, values) -> None:
        self.effects = [e for e in self.effects if e.kind != "immunity"]
        for v in values or ():
            self.grant_defence("immunity", str(v), source="innate")

    @property
    def resistances(self) -> dict[str, int]:
        return {str(e.payload.get("against", "")): int(e.payload.get("amount", 0) or 0)
                for e in self._defence("resistance")}

    @resistances.setter
    def resistances(self, values) -> None:
        self.effects = [e for e in self.effects if e.kind != "resistance"]
        for k, v in (values or {}).items():
            self.grant_defence("resistance", str(k), amount=int(v), source="innate")

    @property
    def vulnerabilities(self) -> list[str]:
        return [str(e.payload.get("against", ""))
                for e in self._defence("vulnerability")]

    @vulnerabilities.setter
    def vulnerabilities(self, values) -> None:
        self.effects = [e for e in self.effects if e.kind != "vulnerability"]
        for v in values or ():
            self.grant_defence("vulnerability", str(v), source="innate")

    @property
    def reductions(self) -> list["Reduction"]:
        return [Reduction(int(e.payload.get("amount", 0) or 0),
                          str(e.payload.get("bypass") or ""),
                          e.source or e.name)
                for e in self._defence("damage_reduction")]

    @reductions.setter
    def reductions(self, values) -> None:
        self.effects = [e for e in self.effects if e.kind != "damage_reduction"]
        for r in values or ():
            self.grant_defence("damage_reduction", "", amount=r.amount,
                               bypass=r.bypass, source=r.source or "innate")

    @property
    def compulsions(self) -> list["Compulsion"]:
        """Who is pulling at this creature, built from the one store.

        The modifiers list on these effects is deliberately EMPTY. Authoring the -4 as
        a `combat_mod` so it flows through the one funnel inverts the mechanic:
        `_buff_mods` has no notion of *whom* you are attacking, so the penalty would
        apply to every swing including the one that obeys — and "obeying is free" is
        the whole design. `compulsion.penalty_against` is the reader, because it is the
        only one that knows the target.
        """
        from .compulsion import Compulsion

        return [Compulsion(by=str(e.payload.get("by", "")),
                           penalty=int(e.payload.get("penalty", 0) or 0),
                           rounds_left=e.rounds_left, source=e.source,
                           why=str(e.payload.get("why", "")))
                for e in self.effects if e.kind == "compulsion"]

    @compulsions.setter
    def compulsions(self, values) -> None:
        from . import compulsion as compulsion_mod

        self.effects = [e for e in self.effects if e.kind != "compulsion"]
        for c in values or ():
            compulsion_mod.add(self, c.by, c.penalty, c.rounds_left, c.source, c.why)

    @property
    def coating(self) -> dict:
        e = next((x for x in self.effects if x.kind == "coating"), None)
        return e.payload if e else {}

    @coating.setter
    def coating(self, value: dict) -> None:
        """A dose, not an enchantment: at most one, replaced by the next and cleared
        by the hit that delivers it (`actor.coating = {}`)."""
        self.effects = [e for e in self.effects if e.kind != "coating"]
        value = dict(value or {})
        if value:
            self.effects.append(ActiveEffect(
                name=str(value.get("name", "") or "a coating"), kind="coating",
                source=str(value.get("name", "") or ""), payload=value))

    def apply_effect(self, eff: ActiveEffect) -> ActiveEffect:
        """The one applicator. Stacking policy: `refresh` finds the copy already here
        — same kind and identity — and resets its clock and values rather than adding
        a second; `stack` accumulates. Conditions and pools have their own richer
        policies and route through `add_condition`/`gain_temp_hp`, which end here."""
        if eff.stacking == "refresh":
            for have in self.effects:
                if (have.kind, have.key or have.name, have.source) == \
                        (eff.kind, eff.key or eff.name, eff.source):
                    have.rounds_left = eff.rounds_left
                    have.duration = eff.duration
                    have.modifiers = [dict(m) for m in eff.modifiers]
                    have.tags = tuple(eff.tags)
                    have.amount = eff.amount
                    have.payload = dict(eff.payload)
                    have.periodic = [dict(p) for p in eff.periodic]
                    return have
        self.effects.append(eff)
        return eff

    def remove_effects(self, *, kind: str | None = None, name: str = "",
                       source: str = "", match=None) -> list[ActiveEffect]:
        """Remove everything matching, returning what went — the contribution of a
        removed effect evaporates with it, never lingers to be subtracted later."""
        # `match` is a predicate for the removals the three named filters cannot
        # express — a compulsion is identified by whom it pulls towards, which lives in
        # its payload. Given rather than letting callers filter and delete themselves,
        # because the moment a caller edits the store directly the removal stops
        # emitting and law 2 is back to being a suggestion.
        gone = [e for e in self.effects
                if (kind is None or e.kind == kind)
                and (not name or (e.name or e.key).lower() == name.lower())
                and (not source or e.source.lower() == source.lower())
                and (match is None or match(e))]
        # By identity, not by value. `ActiveEffect` is a plain dataclass, so `list.remove`
        # matches on `__eq__` and deletes the FIRST equal record rather than the one the
        # predicate picked — two doses of the same poison are equal in every field. The
        # dispel passes `match=lambda e: e is holder` and the comment there promises the
        # record it found is the record that goes; `.remove` could not deliver that.
        # Sliced in place so the list object itself survives, which callers holding a
        # reference to `effects` rely on.
        doomed = {id(e) for e in gone}
        self.effects[:] = [e for e in self.effects if id(e) not in doomed]
        return gone

    def tick_effects(self, rounds: int = 1) -> list[str]:
        """The one ticker. Everything timed expires on the same clock; what ended is
        returned in the words the old per-mechanism tickers used, because transcripts
        and tests read them.

        Hit points follow the maximum down when an effect that was holding it up ends.
        `hp_max` is derived from the Constitution modifier, so a bear's endurance
        expiring lowers it — and nothing here used to notice, leaving the character
        standing at 38 of 30. `_follow_con` was written for exactly this and applies in
        both directions; the clamp belongs where the expiry happens rather than at the
        one call site somebody remembered, because 25 shipped spells carry a timed
        Constitution bonus and every one of them ends somewhere.
        """
        before_max = self.hp_max
        ended = []
        for e in list(self.effects):
            if e.rounds_left is None:
                continue
            e.rounds_left -= rounds
            if e.rounds_left <= 0:
                ended.append(e.ended_label)
                self.effects.remove(e)
        if ended:
            self._follow_con(before_max)
        return ended

    # --- basics ------------------------------------------------------------------

    @property
    def is_pc(self) -> bool:
        return self.kind == "pc"

    @property
    def class_data(self) -> dict:
        from . import classes

        return classes.get(self.char_class or "")

    def ability_score(self, ab: str) -> int:
        """The score as it stands, after everything that has happened to it.

        Three different things reduce an ability and 1e keeps them apart on purpose:
        a *penalty* from a condition lifts when the condition does, *damage* heals back
        over days, and *drain* is a real loss of the score. They are stored separately
        because they are undone separately — folding them into one number would make
        "you got better" impossible to compute.

        The floor is 0, not negative: a score at 0 is already the worst thing that
        happens to it (see `ability_zero_effects`), and letting it go to -3 would quietly
        deepen every modifier derived from it.

        The score is also where an `ability_mod` effect lands, and that is 1e's whole
        rule: a belt of giant strength raises your STRENGTH, and everything derived
        from it follows — the modifier, the Power Attack prerequisite, Fortitude, hit
        points. Applied to the modifier instead, as it was, a +4 belt was worth +4 to
        the modifier where raising a 12 to a 16 gives +2, so the shipped catalogue's
        belts and headbands were worth double.
        """
        score = self.abilities.get(ab, 10)
        for c in self.conditions:
            score += c.data.get("ability_penalty", {}).get(ab, 0)
        score -= self.ability_damage.get(ab, 0)
        score -= self.ability_drain.get(ab, 0)
        # Through `stack`, like every other builder's return. Reading the funnel
        # and forgetting the channel is how two enhancement belts added to +8
        # instead of taking the better +6 — found by the test written for this
        # very change, which is what the behavioural table is for.
        score += sum(m.value for m in stack(self._buff_mods("ability_mod", ab)))
        return max(0, score)

    @property
    def hp_max(self) -> int:
        """Rolled hit points plus what Constitution makes of them.

        1e's rule stated once, rather than applied at three call sites and undone at
        one: every Hit Die you have is worth your Constitution modifier, so the total
        follows the score wherever it goes — a belt, a poison, a class's permanent
        growth, a rage. The floor is 1 because a living thing has at least one.
        """
        return max(1, self.hp_base + self.ability_mod("con") * max(1, self.hit_dice)
                   + self._feat_hp())

    @hp_max.setter
    def hp_max(self, total: int) -> None:
        """Set the finished total, as a stat block states it.

        Writing is allowed and reading still derives, which is the whole point: a
        printed stat block gives the total and the sheet stores what is left once
        Constitution's share is taken out, so the number can never afterwards drift
        away from the score it is supposed to follow.
        """
        self.set_hp_max(total)

    def set_hp_max(self, total: int) -> None:
        """The total, stored as the rolled base that makes it true.

        Symmetric with the read, feat channel included: `from_dict` calls this with
        the saved total, and a Toughness whose +3 was read but not subtracted here
        grew the base by three on every load — the Thor 23 → 37 class of bug, pinned
        by the save-twice test.
        """
        self.hp_base = (int(total) - self.ability_mod("con") * max(1, self.hit_dice)
                        - self._feat_hp())

    def base_ability_score(self, ab: str) -> int:
        """Before damage and drain — what it heals back towards."""
        return self.abilities.get(ab, 10)

    def ability_mod(self, ab: str) -> int:
        """Derived from the score, and from nothing else.

        This used to add buffs and worn gear a SECOND time, on top of a score that did
        not include them: two funnels for one number, and the second one skipped
        `stack()`, so two enhancement belts added instead of taking the better.
        """
        return ability_modifier(self.ability_score(ab))

    # --- ability damage ---------------------------------------------------------------

    def damage_ability(self, ab: str, amount: int, drain: bool = False) -> dict:
        """Reduce an ability score. `drain` for the permanent kind.

        Constitution is the one with a second effect: losing Con modifier costs hit
        points, one per Hit Die per point of modifier. Skipping that is the single
        easiest way for Con damage to look like it worked while doing nothing — the score
        drops, the Fortitude save drops, and the character's hit points sit there
        unchanged as though a poison had never touched them.
        """
        ab = ab.strip().lower()
        if ab not in ABILITIES:
            raise KeyError(f"no such ability {ab!r}")
        amount = max(0, int(amount))
        before_max = self.hp_max

        book = self.ability_drain if drain else self.ability_damage
        book[ab] = book.get(ab, 0) + amount

        hp_change = 0
        if ab == "con":
            hp_change = self._follow_con(before_max)
        return {
            "ability": ab, "amount": amount, "kind": "drain" if drain else "damage",
            "score": self.ability_score(ab), "hp_change": hp_change,
            "zero": self.ability_score(ab) == 0,
        }

    def heal_ability(self, ab: str, amount: int) -> int:
        """Ability *damage* heals; drain does not. Returns how much came back."""
        ab = ab.strip().lower()
        have = self.ability_damage.get(ab, 0)
        back = min(have, max(0, int(amount)))
        if not back:
            return 0
        before_max = self.hp_max
        self.ability_damage[ab] = have - back
        if not self.ability_damage[ab]:
            del self.ability_damage[ab]
        if ab == "con":
            self._follow_con(before_max)
        return back

    def grow_ability(self, ab: str, amount: int) -> dict:
        """A permanent increase to a base score — a class's own growth, an inherent bonus.

        The one place a base score goes up, for the same reason `damage_ability` is the
        one place one goes down: raising Constitution has a second consequence, and
        `rules/leveling.py` wrote `actor.abilities[ab] += amount` directly and never had
        it. Measured on the shipped class at 20th level: 100 hit points never granted —
        210 against 310 owed, one third of the total — because 1e's retroactive rule
        (every Hit Die already earned gains with the modifier) needs the arithmetic
        below and a bare `+=` cannot reach it.
        """
        ab = ab.strip().lower()
        if ab not in ABILITIES:
            raise KeyError(f"no such ability {ab!r}")
        before_max = self.hp_max
        self.abilities[ab] = int(self.abilities.get(ab, 10)) + int(amount)
        hp_change = self._follow_con(before_max) if ab == "con" else 0
        return {"ability": ab, "amount": int(amount),
                "score": self.ability_score(ab), "hp_change": hp_change}

    def rebuild_pools(self) -> list[str]:
        """Resize every class pool against the sheet as it stands now.

        A pool's maximum is a formula in the class file precisely so it can follow a
        level up, and `leveling.level_up` has always called this — guarded by
        `hasattr`, which is why nobody noticed it had never existed. Measured: nine
        levels gained in one session left a Blood Bender's rage pool at 5 rounds when
        its own formula said 25, and a reload silently corrected it, so the bug healed
        itself every time anybody went looking.
        """
        from . import classes

        return list(classes.apply(self).get("pools") or [])

    def _follow_con(self, before_max: int) -> int:
        """Move CURRENT hit points to match a maximum that has already moved.

        `hp_max` is derived, so it needs no help; what still needs saying is 1e's rider
        that current hit points travel with the maximum, so a character at full stays at
        full and a wounded one keeps their wound. Measured against the maximum before
        and after rather than against a modifier delta: the old version computed
        `(mod_now - mod_then) * hit_dice` and applied it to a stored total, which drifts
        the moment anything OTHER than that call changes the modifier — which is exactly
        what an ability_mod effect reaching the score now does.
        """
        delta = self.hp_max - before_max
        if delta:
            # Both directions. Moving current hit points only upwards left a
            # wounded character holding all of them while their maximum fell — 12
            # of 22 after a poison that should have left 4 of 22 — and Constitution
            # damage stopped being able to drop anybody at all.
            self.hp = min(self.hp + delta, self.hp_max)
        return delta

    def ability_zero_effects(self) -> list[str]:
        """What a score of 0 does. 1e names a different consequence for each.

        Constitution is death, and it is death *by a different route than hit points* —
        a character killed by Con damage may be at full health, so nothing in
        `apply_hp_state` would ever notice.
        """
        out = []
        for ab in ABILITIES:
            if self.ability_score(ab) > 0:
                continue
            if ab == "con" and not self.has_condition("dead"):
                self.add_condition("dead", source="Constitution reduced to 0")
                out.append("dead")
            elif ab == "str" and not self.has_condition("helpless"):
                self.add_condition("helpless", source="Strength reduced to 0")
                out.append("helpless")
            elif ab == "dex" and not self.has_condition("paralyzed"):
                self.add_condition("paralyzed", source="Dexterity reduced to 0")
                out.append("paralyzed")
            elif ab in ("int", "wis", "cha") and not self.has_condition("unconscious"):
                self.add_condition("unconscious",
                                   source=f"{ABILITY_FULL[ab]} reduced to 0")
                out.append("unconscious")
        return out

    @property
    def hit_dice(self) -> int:
        """Hit Dice, which is not always level.

        Every class in the book has one die per level, so nothing has ever had to tell
        them apart. Blood Bending has two, and anything counted "per Hit Die" — its own
        Rage temporary hit points, the Constitution arithmetic above — is wrong by a
        factor of two if this returns level.
        """
        return max(1, self.level * max(1, self.hit_dice_per_level))

    @property
    def bab(self) -> int:
        if not self.class_data:
            return self.flat_attack or 0
        return bab_for(self.class_data["bab"], self.level)

    @property
    def speed_feet(self) -> int:
        """Land speed after armour and conditions, in feet — what a move is measured against.

        Armour is a lookup rather than a fraction because the table is not one: 30 becomes
        20 and 20 becomes 15, and neither is two thirds of the other. Entangled and
        exhausted both halve what is left, and halving after the armour step rather than
        before is the order the book uses.
        """
        base = max(0, int(self.speed))
        if ARMOUR.get(self.armour, {}).get("weight") in ("medium", "heavy"):
            base = ARMOUR_SPEED.get(base, base)
        # Between the armour lookup and the halving, which is the order the book
        # uses: boots do not undo a breastplate's penalty, and being entangled
        # halves what is left including them.
        #
        # All 69 shipped speed specs are written with NO bonus type, and untyped
        # self-stacks — so routing them in raw would let haste, longstrider,
        # expeditious retreat and a pair of boots add to +80 where 1e's enhancement
        # channel gives +30. 1e makes magical speed bonuses enhancement bonuses, so
        # an untyped one is read as enhancement here rather than left to pile up; a
        # spec its author typed keeps whatever it says.
        moved = [Modifier(m.value, m.source, m.type or "enhancement")
                 for m in self._buff_mods("speed", "land")]
        base = max(0, base + sum(m.value for m in stack(moved)))
        for slowed in ("entangled", "exhausted"):
            if self.has_condition(slowed):
                base //= 2
                break
        # Rounded down to a whole square. A speed of 22 feet lets you cross four squares,
        # not four and a bit, and carrying the remainder makes the fifth square arrive one
        # move sooner than it should.
        return (base // 5) * 5

    @property
    def armour_check_penalty(self) -> int:
        return (ARMOUR.get(self.armour, ARMOUR["none"])["acp"]
                + SHIELDS.get(self.shield, SHIELDS["none"])["acp"])

    def can_act(self) -> bool:
        """Whether this creature can take any action at all.

        The vocabulary answers it, not a flag on the condition row. The two used to
        disagree on three of the thirty-one shipped conditions, and consumers picked
        whichever they knew about — see `rules.states.blocking`.
        """
        return not self.blocking_key()

    def blocking_key(self, action: str = "any") -> str:
        """The condition key stopping `action`, or "" — the vocabulary's own answer.

        Asked of the tags each effect carries, the same ones `has_state` reads, so a
        document that declares its own `state.unable.*` tag stops actions without
        needing a row in the condition table.
        """
        from . import states

        # Falls back to the name, then to a word, because the answer doubles as the
        # "" that means "nothing stops you". An effect carrying `state.unable.*` with no
        # key would otherwise block according to `has_state` and not according to
        # `can_act` — which is exactly the document-declared case `states.stops` promises
        # to serve.
        return next((e.key or e.name or "unable to act" for e in self.effects
                     if states.stops(e.tags, action)), "")

    def blocking_condition(self, action: str = "any") -> str | None:
        """The same answer as a display name, for a refusal the player reads."""
        key = self.blocking_key(action)
        if not key:
            return None
        return next((c.name for c in self.conditions if c.key == key), key)

    @property
    def is_down(self) -> bool:
        """Out of the fight — not merely unable to act this instant.

        The distinction the app kept losing. "Can this creature act?" and "is this
        creature out of the fight?" are different questions, and five authorities
        answered them with three predicates between them: a stunned or fascinated enemy
        takes no turn and is emphatically still in the fight, while a Constitution-drained
        corpse at full hit points takes no turn and is emphatically not.

        Hit points are part of the answer because a body can be down before anything has
        written a condition on it — the tag layer widens the old tests, never narrows
        them.
        """
        return self.hp < 0 or self.has_state("state.down")

    @property
    def is_helpless(self) -> bool:
        """"Immobilized, unconscious, or otherwise incapacitated" — 1e's own phrase for
        the creature a combat maneuver succeeds against without a roll.

        A narrower question than `can_act`, and the distinction is load-bearing: a
        fascinated creature takes no actions and is emphatically NOT helpless, so
        reading this off `can_act` would let anyone grapple a distracted one for free.
        """
        return any(c.data.get("helpless") for c in self.conditions)

    def has_condition(self, key: str) -> bool:
        return any(e.kind == "condition" and e.key == key for e in self.effects)

    def has_state(self, query: str) -> bool:
        """Whether any held condition answers a tag query — "state.down",
        "state.unable", "buff.stance" — by exact match or dot-boundary prefix.

        The vocabulary lives in `rules.states`; this is the one question the flat
        string checks kept answering differently (lootability, the walking-dead cut,
        can-act all hand-rolled their own tests of hp and key equality). Death is
        deliberately part of the answer: a corpse with the `dead` condition is
        `state.down` whatever its hit points say, and an actor at negative hit points
        with no condition yet recorded still answers through the hp check its callers
        keep — the tag layer widens the old tests, never narrows them.

        Read off the effects' own granted tags rather than re-deriving from condition
        keys, so *every* effect participates: a stance is `buff.stance.blood-rage`
        without pretending to be a condition.
        """
        from . import states

        q = (query or "").strip().lower()
        # Stored effects' tags, then the standing ones a feat document or the class
        # list grants without an effect (stage 8). The one door for both.
        return (any(states.matches(t, q) for e in self.effects for t in e.tags)
                or any(states.matches(t, q) for t in self.standing_tags()))

    # --- condition contributions --------------------------------------------------

    def concealment(self) -> tuple[int, str]:
        """The miss chance an attack against this creature must beat, and where it is from.

        Displacement, blur, entropic shield and blurred movement are *entirely* this and
        were entirely inert: with nothing on the sheet to hold a miss chance they had to
        be written as prose, and the tempting alternative — writing 50% as an AC bonus —
        changes *which* attacks land rather than how many, which is a different spell.

        The best source wins rather than adding up. Two 20% miss chances are not 40% in
        1e and they are not 36% either; concealment does not stack with concealment.
        """
        best, why = 0, ""
        for c in self.conditions:
            got = c.data.get("concealment")
            if isinstance(got, int) and got > best:
                best, why = got, c.name.lower()
        # Every effect and worn gear, not only conditions and the buff VIEW:
        # `self.buffs` filters to kind == "buff", so a stance or class ability
        # granting a miss chance was invisible here — the same shape of gap that
        # kept an ability's ability_mod out of the score — and a cloak that blurs
        # its wearer had nowhere to reach at all. Still best-only: two 20% miss
        # chances are not 40% in 1e, and they are not 36% either.
        for m in self._buff_mods("concealment", "miss_chance"):
            if m.value > best:
                best, why = m.value, m.source or "concealment"
        return best, why

    def water_row(self) -> str:
        """Which row of the underwater table this creature is in, or "" on dry ground.

        One derivation, asked in four places — the attack roll, the damage, the AC of
        whoever is being swung at, and the tell. Derived rather than stored for the reason
        every other spatial fact here is: the place id says where you are, and a stored
        copy is a second writer waiting to disagree with it.
        """
        from . import places as places_mod
        from . import water as water_mod

        terrain = places_mod.terrain_of(str(getattr(self, "at", "") or ""))
        if not water_mod.is_wet(terrain):
            return ""
        return water_mod.row_for(self, self.swim_check_made)

    def _water_penalty(self, weapon: dict) -> "Modifier | None":
        from . import water as water_mod

        row = self.water_row()
        if not row:
            return None
        penalty = water_mod.attack_penalty(row, str(weapon.get("type") or ""))
        return Modifier(penalty, "the water") if penalty else None

    def _condition_mods(self, field_name: str) -> list[Modifier]:
        out = []
        for c in self.conditions:
            v = c.data.get(field_name)
            if isinstance(v, int) and v:
                out.append(Modifier(v, c.name.lower()))
        return out

    # --- skills --------------------------------------------------------------------

    def skill_modifiers(self, skill: str) -> list[Modifier]:
        skill = skill.strip().lower()
        if skill not in SKILLS:
            raise KeyError(f"no such skill {skill!r}")
        ability, trained_only, acp_applies = SKILLS[skill]
        mods: list[Modifier] = []

        if skill in self.flat_skills:
            mods.append(Modifier(self.flat_skills[skill], skill.title()))
        else:
            rank = self.ranks.get(skill, 0)
            if trained_only and rank == 0:
                raise IllegalSheet(
                    f"{self.name} cannot attempt {skill} untrained"
                )
            if rank:
                mods.append(Modifier(rank, "ranks"))
                if skill in self.class_data.get("class_skills", ()):
                    mods.append(Modifier(3, "class skill"))
            am = self.ability_mod(ability)
            if am:
                mods.append(Modifier(am, ability.title()))
            if acp_applies and self.armour_check_penalty:
                mods.append(Modifier(self.armour_check_penalty, "armour check"))

        if skill == "stealth":
            size_mod = SIZES.get(self.size, SIZES["medium"])["stealth"]
            if size_mod:
                mods.append(Modifier(size_mod, f"{self.size} size"))

        mods.extend(self._condition_mods("skills"))
        mods.extend(self._buff_mods("skill_mod", skill))
        return stack(mods)

    # --- saves ----------------------------------------------------------------------

    def save_modifiers(self, save: str) -> list[Modifier]:
        save = save.strip().lower()
        if save not in SAVES:
            raise KeyError(f"no such save {save!r}")
        mods: list[Modifier] = []

        if save in self.flat_saves:
            mods.append(Modifier(self.flat_saves[save], SAVES[save]))
        else:
            # A class may state each save's progression outright. `good_saves` remains the
            # fallback because the Core four are described that way and because it is what
            # a hand-written class file is likely to say.
            from . import classes

            base = classes.save_base(self.class_data, save, self.level)
            if base is None:
                base = save_for(save in self.class_data.get("good_saves", ()), self.level)
            label = f"base {SAVES[save]}"
            if self.char_class:
                label += f" ({self.class_data.get('name', self.char_class)} {self.level})"
            mods.append(Modifier(base, label))
            am = self.ability_mod(SAVE_ABILITY[save])
            if am:
                mods.append(Modifier(am, SAVE_ABILITY[save].title()))

        mods.extend(self._condition_mods("saves"))
        mods.extend(self._buff_mods("save_mod", save))
        return stack(mods)

    # --- initiative -------------------------------------------------------------------

    def initiative_modifiers(self) -> list[Modifier]:
        mods: list[Modifier] = []
        if self.flat_initiative is not None:
            mods.append(Modifier(self.flat_initiative, "Initiative"))
        else:
            am = self.ability_mod("dex")
            if am:
                mods.append(Modifier(am, "Dex"))
        mods.extend(self._buff_mods("combat_mod", "initiative"))
        return stack(mods)

    # --- attack and damage --------------------------------------------------------------

    def weapon(self, key: str | None = None) -> dict:
        """The weapon's statistics.

        Goes through `rules.weapons` rather than reading `tables.WEAPONS` directly: the
        table holds eleven, the content file holds 456, and a player reaching for a glaive
        used to get `KeyError: no such weapon`.
        """
        from . import weapons as weapons_mod

        from . import leveling

        wanted = (key or self.equipped or "unarmed").strip().lower()
        # A granted weapon rides every unarmed strike while its toggle holds, and
        # answers to its own aliases whether or not it is formed — the engine's gate
        # refuses the unformed swing with the forming ability's name, which it cannot
        # do if the weapon refuses to exist first. This used to be the armament's
        # hand-written special case (name list, condition, blood column, all in code);
        # now the class document states the same facts and any class stating them gets
        # the same weapon. A held weapon never carries a grant: it arms the fist and
        # only the fist.
        for g in leveling.granted_weapons(self):
            w = g["weapon"]
            aliases = {str(a).lower() for a in (w.get("aliases") or ())}
            rides_unarmed = (
                wanted in ("unarmed", "unarmed strike", "fist", "fists", "punch")
                and w.get("applies_to_unarmed") and g["key"]
                and self.has_condition(g["key"]))
            if wanted not in aliases and not rides_unarmed:
                continue
            base = dict(weapons_mod.get(str(w.get("base") or "unarmed")))
            base["name"] = str(w.get("name") or g["ability"])
            # The die is the class table's own column at this character's level — a
            # weapons-table entry cannot know who is asking, which is why it is built
            # here.
            if w.get("damage_column"):
                base["damage"] = (leveling.table_die(self, str(w["damage_column"]))
                                  or str(w.get("fallback_damage") or base["damage"]))
            if w.get("type"):
                base["type"] = str(w["type"])
            for carried in ("rider_column", "damage_label", "proficiency_as"):
                if w.get(carried):
                    base[carried] = str(w[carried])
            # The flags the engine keys on: which toggle must hold, and which ability
            # forms it — so a refusal can name the fix.
            base["granted_by"] = g["key"]
            base["formed_with"] = g["ability"]
            return base
        natural = self.natural_weapon(wanted)
        if natural is not None:
            return natural
        return weapons_mod.get(wanted)

    def _attack_ability(self, weapon: dict, weapon_key: str | None = None) -> str | None:
        """A feat document's `attack_ability` substitution, when its clause holds.

        Weapon Finesse: `{"use": "dex", "if_better": true, "when": {"weapon":
        {"finessable": true}}}` — the one feat that is a switch rather than a number.
        It was a literal name-match in this method before stage 8.
        """
        from . import feats as feats_mod

        ctx = self._roll_context(weapon_key)
        for raw in self.feats:
            sub = (feats_mod.document(raw) or {}).get("attack_ability")
            if not isinstance(sub, dict) or not _when_holds(sub.get("when"), ctx):
                continue
            use = str(sub.get("use", "")).lower()
            if sub.get("if_better") and self.ability_mod(use) <= self.ability_mod("str"):
                continue
            return use
        return None

    @staticmethod
    def _feat_name(feat: str) -> str:
        """"Weapon Focus (rapier)" -> "weapon focus"."""
        m = re.match(FEAT_TARGET_RE, feat.strip(), re.IGNORECASE)
        return (m.group("feat") if m else feat).strip().lower()

    @staticmethod
    def _feat_target(feat: str) -> str | None:
        m = re.match(FEAT_TARGET_RE, feat.strip(), re.IGNORECASE)
        return m.group("target").strip().lower() if m else None

    def natural_weapon(self, key: str) -> dict | None:
        """A natural attack the race document grants — claws, a bite, a sting — as a
        weapon the sheet can swing, its die by this body's size.

        Built here rather than in the weapons table for the same reason a granted
        weapon is: the table cannot know who is asking, and a Small Korvu's claws are
        not a Medium one's. Aliases are the key and the name, singular or plural, so
        "claw", "claws" and "my talons" all reach the same entry (talons are claws).
        A natural weapon is always proficient — it is the body.
        """
        from . import weapons as weapons_mod

        doc = self._race_doc()
        if not doc:
            return None
        want = " ".join(str(key or "").split()).lower()
        want = {"talon": "claws", "talons": "claws", "claw": "claws", "fangs": "bite",
                "teeth": "bite", "horns": "gore", "horn": "gore", "tail": "tail slap",
                "pincer": "pincers", "tentacles": "tentacle", "wing buffet": "wings",
                "wing": "wings"}.get(want, want)
        for w in doc.get("weapons") or ():
            names = {str(w.get("key", "")).lower(), str(w.get("name", "")).lower()}
            if want not in names:
                continue
            base = dict(weapons_mod.get("unarmed"))
            dice = w.get("damage") or {}
            base.update({
                "name": str(w.get("name") or w.get("key")),
                "damage": str(dice.get(str(self.size or "medium").lower())
                              or dice.get("medium") or base["damage"]),
                "type": str(w.get("type") or "bludgeoning"),
                "nonlethal": False, "prof": "natural", "natural": True,
                "count": int(w.get("count", 1) or 1),
                "secondary": bool(w.get("secondary")),
                "hands": 0,
            })
            return base
        return None

    def is_proficient(self, weapon_key: str | None = None) -> bool:
        """Proficiency comes from the class, or from a Martial/Simple Weapon Proficiency
        feat, or from the weapon being named specifically."""
        from . import weapons as weapons_mod

        key = (weapon_key or self.equipped or "unarmed").strip().lower()
        if self.natural_weapon(key) is not None:
            return True                      # a body is proficient with itself
        # A granted weapon is your own fists with something over them, so proficiency
        # is the proficiency the document names (`proficiency_as`, usually unarmed).
        # It is not in the weapons table — it is built on the wearer from a class
        # table column — so the table lookup found nothing, `prof` was None, and a
        # Blood Bender was told they were not proficient with their own hands: a −4
        # on every armed punch, visible in the dice popup.
        from . import leveling

        granted = leveling.granted_weapon_named(self, key)
        if granted:
            key = str(granted["weapon"].get("proficiency_as") or "unarmed")
        w = weapons_mod.all_weapons().get(key, {})
        if self.flat_attack is not None:
            return True          # an NPC stat block's attack bonus already accounts for it
        # Law 1: a permission is a tag. The class list and every proficiency feat
        # answer through `has_state`, never through a suffix match on the feat name.
        return (self.has_state(f"proficient.weapon.{key}")
                or bool(w.get("prof")) and self.has_state(f"proficient.{w['prof']}"))

    def choice_feat(self, choice: str) -> dict | None:
        """The held feat document that declares this attack-op choice, if any."""
        from . import feats as feats_mod

        for raw in self.feats:
            doc = feats_mod.document(raw)
            if doc and str(doc.get("choice", "")) == choice:
                return doc
        return None

    def can_power_attack(self) -> str | None:
        """None if legal, otherwise why not.

        The feat by its document (`choice: "power_attack"`), the prerequisites from
        feats.json — BAB +1 and Str 13 used to be hard-coded here, a third copy
        beside the index and the table.
        """
        from . import feats as feats_mod

        doc = self.choice_feat("power_attack")
        if doc is None:
            return f"{self.name} does not have {feats_mod.get('power-attack').name}"
        verdict = feats_mod.meets(self, doc["id"])
        if verdict["unmet"]:
            return f"{self.name} cannot use {doc['name']}: needs {', '.join(verdict['unmet'])}"
        return None

    def attack_modifiers(
        self, weapon_key: str | None = None, iteration: int = 0,
        power_attack: bool = False,
    ) -> list[Modifier]:
        w = self.weapon(weapon_key)
        key = (weapon_key or self.equipped or "unarmed").strip().lower()
        mods: list[Modifier] = []

        if self.flat_attack is not None:
            mods.append(Modifier(self.flat_attack, "attack bonus"))
        else:
            mods.append(Modifier(self.bab, "BAB"))
            # Str for melee, Dex for ranged — and Dex for melee only when Weapon Finesse
            # applies and actually helps.
            if w["category"] == "ranged":
                ab, label = "dex", "Dex"
            elif (sub := self._attack_ability(w, key)):
                ab, label = sub, f"{sub.title()} (Finesse)"
            else:
                ab, label = "str", "Str"
            am = self.ability_mod(ab)
            if am:
                mods.append(Modifier(am, label))

            if not self.is_proficient(key):
                mods.append(Modifier(NON_PROFICIENT_PENALTY,
                                     f"not proficient with {w['name']}"))

            # Size only when the number was derived. A stat block's printed attack bonus
            # already includes the creature's size, and adding it again gave a small
            # NPC a free +1 on every swing.
            size_mod = SIZES.get(self.size, SIZES["medium"])["attack_ac"]
            if size_mod:
                mods.append(Modifier(size_mod, f"{self.size} size"))

        if iteration:
            mods.append(Modifier(-5 * iteration, f"iterative #{iteration + 1}"))

        mods.extend(self._condition_mods("attack"))
        if w["category"] == "melee":
            mods.extend(self._condition_mods("melee_attack"))
        # What the water takes off this particular swing. Scoped to the damage TYPE
        # because that is how the Core Rulebook scopes it — a spear works down there and
        # a sword does not — which is why it cannot ride a condition's flat `attack` the
        # way `shaken` does.
        #
        # Read off this creature's OWN place id: the ground is inside the id (`~water:`),
        # `terrain_of` parses it and looks nothing up, and that is precisely why a sheet
        # with no world can still answer. The same reason `scene.biome` is derived.
        wet = self._water_penalty(w)
        if wet:
            mods.append(wet)
        # Weapon Focus and Power Attack arrive here now, scoped and conditional, from
        # their documents — never as literals appended above.
        mods.extend(self._buff_mods("combat_mod", "attack",
                                    self._roll_context(key, power_attack=power_attack)))
        return stack(mods)

    def attack_sequence(self, weapon_key: str | None = None, full_attack: bool = False) -> list[int]:
        """How many attacks, at which iteration index. Iteratives are the exact kind of
        bookkeeping this app exists to carry."""
        if not full_attack:
            return [0]
        if self.flat_attack is not None:
            return [0]
        return list(range(len(iterative_attacks(self.bab))))

    def damage_modifiers(
        self, weapon_key: str | None = None, power_attack: bool = False,
    ) -> list[Modifier]:
        w = self.weapon(weapon_key)
        key = (weapon_key or self.equipped or "unarmed").strip().lower()
        mods: list[Modifier] = []
        if w["category"] == "melee":
            # Str applies to melee damage even when Finesse supplied the attack roll —
            # Weapon Finesse changes the attack, never the damage. This is a standard
            # place to get 1e wrong.
            am = self.ability_mod("str")
            if am:
                mods.append(Modifier(am, "Str"))
        mods.extend(self._condition_mods("damage"))
        # The one funnel, which this list alone never read: a `combat_mod` aimed at
        # damage was accepted, saved, shown on the sheet — and absent from every
        # damage roll. Found by Blood Rage's +2 damage the day it became a document.
        # Weapon Specialization and Power Attack's damage ride it too, from their
        # documents, against the weapon in hand.
        mods.extend(self._buff_mods("combat_mod", "damage",
                                    self._roll_context(key, power_attack=power_attack)))
        return stack(mods)

    def damage_dice(self, weapon_key: str | None = None) -> str:
        if self.flat_damage and weapon_key is None:
            return self.flat_damage
        return self.weapon(weapon_key)["damage"]

    # --- defence -----------------------------------------------------------------------

    def ac_modifiers(self, against: str = "melee", flat_footed: bool = False) -> list[Modifier]:
        mods = [Modifier(10, "base")]

        if self.flat_ac is not None:
            mods = [Modifier(self.flat_ac, "AC")]
        else:
            armour = ARMOUR.get(self.armour, ARMOUR["none"])
            shield = SHIELDS.get(self.shield, SHIELDS["none"])
            # Typed, so the channels collide as 1e intends: bracers of armour over a
            # breastplate is the better of the two, not the sum, while a ring's
            # deflection sits beside either untouched.
            if armour["ac"]:
                mods.append(Modifier(armour["ac"], armour["name"], "armour"))
            if shield["ac"]:
                mods.append(Modifier(shield["ac"], shield["name"], "shield"))
            if self.natural_armour:
                mods.append(Modifier(self.natural_armour, "natural armour",
                                     "natural armour"))

            loses_dex = flat_footed or any(
                c.data.get("lose_dex_to_ac") for c in self.conditions
            )
            if not loses_dex:
                dex = min(self.ability_mod("dex"), armour["max_dex"])
                if dex:
                    mods.append(Modifier(dex, "Dex"))

            # As with attack: a printed AC already accounts for size.
            size_mod = SIZES.get(self.size, SIZES["medium"])["attack_ac"]
            if size_mod:
                mods.append(Modifier(size_mod, f"{self.size} size"))

        mods.extend(self._condition_mods("ac"))
        mods.extend(self._condition_mods(f"ac_{against}"))
        mods.extend(self._buff_mods("combat_mod", "ac"))
        return stack(mods)

    # The three channels a touch attack ignores. Named as bonus TYPES rather than as
    # equipment fields, which is the whole point: a mage armor spell, a bracer, a
    # crafted hide and a barkskin all grant one of these and none of them is the
    # `armour` slot, so subtracting the armour table's number left every one of them
    # inflating touch AC. 1e's rule is about the type, so the code asks about the type.
    _TOUCH_IGNORES = ("armour", "shield", "natural armour")

    def touch_ac_modifiers(self, flat_footed: bool = False) -> list[Modifier]:
        """Armour class against a touch attack: everything except what you are wearing.

        This was `ac() - armour[ac] - shield[ac] - natural_armour`, three table lookups
        subtracted from a finished total — so it saw the armour a character wore and
        was blind to every other source of the same three bonuses. A `combat_mod`
        aimed at `touch_ac` reached nothing at all, and the thirteen crafted hides
        whose own notes read "worked into armour" were typed untyped and counted
        towards a number they have no business in.
        """
        return [m for m in self.ac_modifiers("melee", flat_footed)
                if (m.type or "") not in self._TOUCH_IGNORES] +             self._buff_mods("combat_mod", "touch_ac")

    def touch_ac(self, flat_footed: bool = False) -> int:
        return sum(m.value for m in self.touch_ac_modifiers(flat_footed))

    def ac(self, against: str = "melee", flat_footed: bool = False) -> int:
        return sum(m.value for m in self.ac_modifiers(against, flat_footed))

    # --- combat manoeuvres ---------------------------------------------------------
    #
    # CMB  = BAB + Str modifier + special size modifier
    # CMD  = 10 + BAB + Str modifier + Dex modifier + special size modifier
    #
    # The *special* size modifier runs the opposite way from the one that applies to
    # attack rolls and AC: Small is -1 here and +1 there. That is why SIZES carries two
    # separate columns, and getting them crossed makes every small creature better at
    # grappling than it should be.

    def cmb_modifiers(self, maneuver: str | None = None,
                      power_attack: bool = False) -> list[Modifier]:
        if self.flat_attack is not None:
            # An NPC stat block prints CMB directly; when it does not, the attack bonus
            # is the closest honest stand-in.
            mods = [Modifier(self.flat_attack, "CMB")]
        else:
            mods = [Modifier(self.bab, "BAB")]
            # Tiny or smaller creatures use Dex in place of Str for CMB.
            uses_dex = self.size in ("fine", "diminutive", "tiny")
            ab = "dex" if uses_dex else "str"
            mods.append(Modifier(self.ability_mod(ab), ab.title()))
            size_mod = SIZES.get(self.size, SIZES["medium"])["cmb_cmd"]
            if size_mod:
                mods.append(Modifier(size_mod, f"{self.size} size"))

        mods.extend(self._condition_mods("attack"))
        # The one funnel, which this list alone never read — the same gap
        # damage_modifiers had: a `combat_mod` aimed at cmb was in the authoring
        # vocabulary, validated, saved, and absent from every manoeuvre roll. The
        # Improved/Greater <manoeuvre> family arrives here scoped to the manoeuvre.
        mods.extend(self._buff_mods("combat_mod", "cmb",
                                    self._roll_context(None, maneuver=maneuver,
                                                       power_attack=power_attack)))
        return stack([m for m in mods if m.value])

    def cmd_modifiers(self, flat_footed: bool = False,
                      maneuver: str | None = None) -> list[Modifier]:
        if self.flat_cmd is not None:
            mods = [Modifier(self.flat_cmd, "CMD")]
            if flat_footed and self.ability_mod("dex") > 0:
                # A printed CMD includes Dex; a flat-footed creature does not add it.
                mods.append(Modifier(-self.ability_mod("dex"), "flat-footed (no Dex)"))
        else:
            mods = [Modifier(10, "base"), Modifier(self.bab, "BAB"),
                    Modifier(self.ability_mod("str"), "Str")]
            loses_dex = flat_footed or any(
                c.data.get("lose_dex_to_ac") for c in self.conditions
            )
            if not loses_dex:
                mods.append(Modifier(self.ability_mod("dex"), "Dex"))
            size_mod = SIZES.get(self.size, SIZES["medium"])["cmb_cmd"]
            if size_mod:
                mods.append(Modifier(size_mod, f"{self.size} size"))

        # "Any penalties to a creature's AC also apply to its CMD."
        mods.extend(m for m in self._condition_mods("ac") if m.value < 0)
        # 1e grants Improved <manoeuvre> to CMD as well as CMB; the old branch gave
        # CMB alone, and the document says both.
        mods.extend(self._buff_mods("combat_mod", "cmd",
                                    {"maneuver": maneuver} if maneuver else None))
        return stack([m for m in mods if m.value])

    def cmd(self, flat_footed: bool = False) -> int:
        return sum(m.value for m in self.cmd_modifiers(flat_footed))

    # --- state ------------------------------------------------------------------------

    # --- temporary hit points ---------------------------------------------------------

    @property
    def temp_hp(self) -> int:
        return sum(e.amount for e in self.effects if e.kind == "temp_hp")

    @property
    def temp_hp_source(self) -> str:
        return ", ".join(e.source for e in self.effects
                         if e.kind == "temp_hp" and e.source)

    def _temp_effects(self) -> list[ActiveEffect]:
        return [e for e in self.effects if e.kind == "temp_hp"]

    def _new_temp_effect(self, amount: int, source: str,
                         rounds: int | None, origin: str = "") -> ActiveEffect:
        return ActiveEffect(name=source or "temporary hit points", kind="temp_hp",
                            source=source, origin=origin, amount=amount,
                            duration="until-dismissed" if rounds is None else "rounds",
                            rounds_left=rounds, stacking="stack")

    def allows(self, rule: str) -> bool:
        if rule not in ACTOR_RULES:
            raise KeyError(f"no such rule {rule!r}")
        return bool(self.overrides.get(rule, False))

    def gain_temp_hp(self, amount: int, source: str = "",
                     rounds: int | None = None, origin: str = "") -> dict:
        """1e: temporary hit points from different sources do not stack — the best applies.

        Adding them would be the obvious implementation and it is wrong in a way that
        compounds: two 10-point sources would read as 20, survive a hit that should have
        dropped the character, and nothing on the sheet would show why.

        Refreshing the *same* source is not stacking, so re-entering a rage sets that pool
        back to its own value rather than being ignored for being equal.

        A class may be exempted through `temp_hp.stacks`, and Blood Bending is: hit points
        are its resource, and a Coagulator layering Blood Sponge over a ward is the path
        working as written rather than a rule being broken.

        The *magic effect stacking* house rule is a third, distinct behaviour: different
        sources each keep their own pool, but the same source reapplies — its pool is set
        back to the new value, never added to. That last clause is what separates it from
        `temp_hp.stacks`, where same-source accumulation is the class's whole design.
        """
        amount = max(0, int(amount))
        existing = next((e for e in self._temp_effects() if e.source == source), None)
        if existing is not None and origin:
            existing.origin = origin

        if houserules.magic_stacking() and not self.allows("temp_hp.stacks"):
            if existing:
                existing.amount, existing.rounds_left = amount, rounds
                return {"temp_hp": self.temp_hp, "refreshed": True, "source": source,
                        "stacked": True}
            self.effects.append(self._new_temp_effect(amount, source, rounds, origin))
            return {"temp_hp": self.temp_hp, "added": amount, "source": source,
                    "stacked": True}

        if self.allows("temp_hp.stacks"):
            if existing:
                existing.amount += amount
                existing.rounds_left = rounds
            else:
                self.effects.append(self._new_temp_effect(amount, source, rounds, origin))
            return {"temp_hp": self.temp_hp, "added": amount, "source": source,
                    "stacked": True}

        if existing:
            existing.amount, existing.rounds_left = amount, rounds
            self.effects = [e for e in self.effects
                            if e.kind != "temp_hp" or e is existing]
            return {"temp_hp": amount, "refreshed": True, "source": source}

        if amount > self.temp_hp:
            was = self.temp_hp
            self.effects = [e for e in self.effects if e.kind != "temp_hp"]
            self.effects.append(self._new_temp_effect(amount, source, rounds, origin))
            return {"temp_hp": amount, "replaced": was, "source": source}
        return {"temp_hp": self.temp_hp, "ignored": amount,
                "source": self.temp_hp_source}

    def _spend_temp_hp(self, amount: int) -> int:
        """Drain the pools that expire soonest first.

        The alternative — draining the largest, or whatever happens to be first — throws
        away the longest-lasting protection to soak a hit the short-lived pool could have
        taken, which is never what a player wants and is invisible when it happens.
        """
        spent = 0
        order = sorted(self._temp_effects(),
                       key=lambda e: (e.rounds_left is None, e.rounds_left or 0))
        for pool in order:
            if spent >= amount:
                break
            take = min(pool.amount, amount - spent)
            pool.amount -= take
            spent += take
        self.effects = [e for e in self.effects
                        if e.kind != "temp_hp" or e.amount > 0]
        return spent

    def clear_temp_hp(self, source: str | None = None) -> int:
        """Drop temporary hit points — all of them, or one source's when a buff ends."""
        gone = sum(e.amount for e in self._temp_effects()
                   if source is None or e.source == source)
        self.effects = [e for e in self.effects
                        if e.kind != "temp_hp"
                        or (source is not None and e.source != source)]
        return gone

    def heal(self, amount: int) -> int:
        """Healing restores real hit points only, and never past your maximum.

        Temporary hit points are explicitly not restored by healing — they are not damage
        you have taken, so there is nothing there to cure.
        """
        amount = max(0, int(amount))
        before = self.hp
        self.hp = min(self.hp_max, self.hp + amount)
        # 1e: curing hit point damage removes an equal amount of non-lethal damage. Miss
        # this and a character healed to full still lies there unconscious from a beating.
        self.heal_nonlethal(amount)
        healed = self.hp - before
        # Blood Bond: healing with nowhere to land banks as temporary hit points. The
        # non-lethal clearing above does NOT count against the bank: in 1e it is a
        # rider — "healing that raises your hit points also removes an equal amount of
        # nonlethal damage" — not a spender, so the cure's points are consumed only by
        # real hit points. This went wrong twice in opposite directions before landing
        # here: first the bank ignored the rider question entirely, then a "fix" made
        # the rider eat the pool, and a full-health bender carrying non-lethal drank a
        # 16-point cure and banked nothing.
        spare = amount - healed
        if spare > 0 and self.allows("heal.overflow_temp_hp"):
            self.gain_temp_hp(spare, source="overflowing vitality")
        return healed

    # --- immunity, resistance and vulnerability ------------------------------------------

    def immune_to(self, dtype: str) -> bool:
        """Whether damage of this type simply does not land.

        Matched on the normalised damage type rather than the printed word, so `Immune
        electricity` stops a shock and `Immune undead traits` — which names a bundle of
        rules, not a damage type — stops nothing here and waits for the save path.
        """
        want = normalise_damage_type(dtype)
        # The stat block's printed line, and the race document's `immune.<energy>` tag
        # (an eidolon evolution, or a world's own people): one question, two sources.
        return (any(normalise_damage_type(t) == want for t in self.immunities)
                or self.has_state(f"immune.{want}"))

    def resistance(self, dtype: str) -> int:
        """Points of this energy shrugged off. 0 when none applies.

        1e does not stack two resistances against the same energy — the better one
        applies — and nothing in the data produces two, but `max` says so rather than
        leaving it to chance.
        """
        want = normalise_damage_type(dtype)
        printed = max((v for k, v in self.resistances.items()
                       if normalise_damage_type(k) == want), default=0)
        # `resist.<energy>.<points>` from the race document. The better one applies.
        import re as _re

        tagged = 0
        for tag in self.standing_tags():
            m = _re.match(r"^resist\.([a-z-]+)\.(\d+)$", str(tag))
            if m and normalise_damage_type(m.group(1)) == want:
                tagged = max(tagged, int(m.group(2)))
        return max(printed, tagged)

    def vulnerable_to(self, dtype: str) -> bool:
        want = normalise_damage_type(dtype)
        return any(normalise_damage_type(t) == want for t in self.vulnerabilities)

    # --- damage reduction -------------------------------------------------------------

    def damage_reduction(self, dtype: str = "untyped",
                         traits: tuple[str, ...] = (),
                         lethality: str = "lethal") -> Reduction | None:
        """The one DR that applies to this attack, or None.

        1e is specific on both counts, and both are easy to get wrong in the generous
        direction: DR does not touch energy damage, and when a creature has several kinds
        of DR **only the best applicable one applies** — they do not add up.
        """
        if not is_physical(dtype):
            return None
        # One read path. `reductions` is a VIEW over the damage_reduction effects, so
        # seeding the pool from it and then walking the effects again would count every
        # innate DR twice — and best-only would hide it, right up until two sources
        # differed. The loop below sees the standalone effects and the `dr` riders that
        # ability documents carry, which is all of them.
        pool: list[Reduction] = []
        # Class documents join the statblock's own DR here rather than by writing
        # into `reductions`, for the same reason worn gear is live-read: Iron Clot
        # is permanent and tier-scaled, and an applied copy would go stale the
        # moment the character levels. Best-only still holds across all sources.
        from . import leveling

        def wants(d: dict) -> bool:
            # A dr may declare `against: nonlethal` — Blood Buffer guards what enemies
            # deal, never what the bender pays, and costs bypass this method entirely
            # by going straight to take_nonlethal. Plain DR applies to both, as 1e says.
            against = str(d.get("against") or "").lower()
            return not against or against == lethality

        for d in leveling.standing_dr(self):
            if wants(d):
                pool.append(Reduction(d["amount"], d["bypass"], d["source"]))
        for e in self.effects:
            if e.kind == "damage_reduction":
                d = dict(e.payload or {})
                if int(d.get("amount", 0) or 0) > 0 and wants(d):
                    pool.append(Reduction(int(d["amount"]),
                                          str(d.get("bypass") or ""),
                                          e.source or e.name))
                continue
            d = e.payload.get("dr") if isinstance(e.payload, dict) else None
            if isinstance(d, dict) and int(d.get("amount", 0) or 0) > 0 and wants(d):
                pool.append(Reduction(int(d["amount"]), str(d.get("bypass") or ""),
                                      e.source or e.name))
        usable = [r for r in pool if r.amount > 0 and not r.bypassed_by(traits)]
        return max(usable, key=lambda r: r.amount) if usable else None

    # --- non-lethal damage ---------------------------------------------------------------

    @property
    def nonlethal_threshold(self) -> int:
        """Where non-lethal damage stops being survivable.

        1e: at your current hit points you are staggered, past them you are unconscious.
        A class may be exempted through `nonlethal.counts_temp_hp`, and Blood Bending is —
        its abilities are bought with non-lethal damage, so where this line sits is where
        the class ends.
        """
        base = max(0, self.hp)
        if self.allows("nonlethal.counts_temp_hp"):
            return base + self.temp_hp
        return base

    def _percent_resist(self, amount: int, dtype: str) -> tuple[int, str]:
        """How much a standing percent-resistance shrugs off, and whose it is.

        Carried in an effect's payload as {"resist": {"against": "physical",
        "percent": 50}}; "physical" answers for the three weapon types, and a named
        energy answers for itself. The best single effect applies — percentages do
        not stack, for the same reason two resist-fire ratings do not.
        """
        if amount <= 0:
            return 0, ""
        best, why = 0, ""
        for e in self.effects:
            r = (e.payload or {}).get("resist")
            if not isinstance(r, dict):
                continue
            pct = int(r.get("percent", 0) or 0)
            against = str(r.get("against", "")).strip().lower()
            hits = (against == "physical" and is_physical(dtype)) or (
                against not in ("", "physical")
                and normalise_damage_type(against) == normalise_damage_type(dtype))
            if hits and pct > best:
                best, why = pct, e.source or e.name
        # Rounded in the defender's favour: 50% of 7 shrugs off 4, not 3 — half the
        # blow "resisted" should never leave the bigger half landing.
        return -(-amount * min(100, best) // 100) if best else 0, why

    def take_nonlethal(self, amount: int) -> dict:
        """Non-lethal damage accumulates on its own rather than coming off hit points.

        Which is the whole reason it is tracked apart: a Blood Bender paying 2d10 for an
        ability and a Blood Bender taking 2d10 from a sword are not in the same trouble,
        and subtracting both from `hp` made them identical.
        """
        amount = max(0, int(amount))
        self.nonlethal += amount
        return {"nonlethal": self.nonlethal, "taken": amount,
                "threshold": self.nonlethal_threshold}

    def heal_nonlethal(self, amount: int) -> int:
        back = min(self.nonlethal, max(0, int(amount)))
        self.nonlethal -= back
        return back

    def take_damage(self, amount: int, dtype: str = "untyped",
                    traits: tuple[str, ...] = (),
                    lethality: str = "lethal") -> dict:
        """Resolve one packet of damage, returning what happened to it at each stage.

        The order is 1e's and it matters: immunity, then vulnerability, then whichever of
        resistance or reduction applies, then temporary hit points, then real ones.

        Vulnerability comes before resistance because 1e multiplies the damage dealt and
        then subtracts — a fire giant with resist fire 10 hit for 20 takes 30 - 10 = 20,
        not (20 - 10) x 1.5 = 15. Doing it the other way round makes a resistance a better
        deal than not being vulnerable at all.

        Resistance and reduction never both apply — one is energy-only and the other
        physical-only — so their order between themselves does not matter, but both must
        come before temporary hit points. Applying them after would let a DR 5 creature
        lose 5 temp HP to an attack that never hurt it.

        Returns a breakdown rather than the remaining hit points because the whole
        proposition of the app is that the bookkeeping is visible — "12, less DR 5, 4 off
        temporary" is the sentence a player needs, and a bare total cannot produce it.
        """
        rolled = max(0, int(amount))
        # Immunity is the whole packet or none of it, and it is checked first so nothing
        # below has to consider a zero it cannot explain.
        immune = self.immune_to(dtype)
        # 1e: half again as much, rounded down.
        vulnerable = not immune and self.vulnerable_to(dtype)
        after_type = 0 if immune else (rolled * 3) // 2 if vulnerable else rolled

        resisted = min(after_type, self.resistance(dtype)) if not immune else 0
        after_type -= resisted

        dr = self.damage_reduction(dtype, traits, lethality)
        # DR reduces to zero, never below: it cannot heal you.
        reduced = min(after_type, dr.amount) if dr else 0
        after_dr = after_type - reduced

        # Percent resistance from a standing effect — Blood Bending's "50% resistance
        # to physical damage while in Blood Rage", promised by the class text and
        # undeliverable until effects could carry it. The best one applies, same as
        # every resistance in 1e; it sits after DR because it is a property of the
        # raging body, not of the armour, and rounds in the defender's favour.
        factored, factored_by = self._percent_resist(after_dr, dtype)
        after_dr -= factored

        absorbed = self._spend_temp_hp(min(self.temp_hp, after_dr))
        taken = after_dr - absorbed
        # Non-lethal still spends temporary hit points first — they are hit points — but
        # what gets through goes to its own pool rather than off the character's total.
        if lethality == "nonlethal":
            self.nonlethal += taken
        else:
            self.hp -= taken
        # A unit's pool is its members: every member's worth of damage takes one of them
        # off their feet, with the excess cascading (13th Age's mob). One writer, here,
        # because this is the one place hit points leave an actor — attrition applied
        # anywhere else could double-count or miss a blow (`rules/troops.settle`).
        fell = _troops.settle(self.troop, self.hp) if self.troop is not None else 0
        if self.troop is not None:
            self.size = _troops.size_for(self.troop.members or 1)
        return {
            "rolled": rolled, "type": normalise_damage_type(dtype),
            # Reported even when they did nothing, because the visible bookkeeping is the
            # point: "20 fire, half again for vulnerability, 30" has to be readable back.
            "immune": immune, "vulnerable": vulnerable, "resisted": resisted,
            "reduced": reduced, "reduced_by": dr.label if dr and reduced else "",
            "factored": factored, "factored_by": factored_by if factored else "",
            "absorbed": absorbed, "taken": taken, "lethality": lethality,
            "hp": self.hp, "hp_max": self.hp_max, "temp_hp": self.temp_hp,
            "nonlethal": self.nonlethal,
            "nonlethal_threshold": self.nonlethal_threshold,
            # How many of a unit that blow took off their feet, and how many are left.
            "fell": fell,
            "members": int(self.troop.members) if self.troop is not None else 0,
        }

    # --- gear -------------------------------------------------------------------------

    def carried(self) -> list[str]:
        """Everything on this character that could plausibly be damaged."""
        out = list(self.weapons)
        if self.equipped and self.equipped not in out:
            out.append(self.equipped)
        if self.armour and self.armour != "none":
            out.append(self.armour)
        if self.shield and self.shield != "none":
            out.append(self.shield)
        for worn in self.slots.values():
            out.extend(w for w in worn if w)
        return list(dict.fromkeys(out))

    def item(self, name: str) -> Item:
        """The record for one item, created the first time anything happens to it."""
        key = (name or "").strip().lower()
        if key not in self.gear:
            self.gear[key] = Item(name=name.strip())
        return self.gear[key]

    def damage_item(self, name: str, amount: int, dtype: str = "untyped") -> dict:
        return self.item(name).take_damage(amount, dtype)

    def damage_all_gear(self, amount: int, dtype: str = "untyped") -> list[dict]:
        """Acid in a blood pool does not pick a target. Everything carried takes it."""
        return [self.damage_item(n, amount, dtype) for n in self.carried()]

    # --- world classes ------------------------------------------------------------------

    def track(self, track_id: str) -> "Progress":
        """This character's standing in one world class, begun on first use.

        Begun rather than chosen: the class levels by doing, so anyone who forages is an
        Herbalist. Choosing it at character creation is a head start with the tools in
        hand, not permission — which is why nothing here requires it.
        """
        from .worldclass import Progress

        track_id = (track_id or "").strip().lower()
        if track_id not in self.world_classes:
            self.world_classes[track_id] = Progress(track=track_id)
        return self.world_classes[track_id]

    # --- what they have made ------------------------------------------------------------

    # --- spendable pools ----------------------------------------------------------------

    def pool(self, pool_id: str):
        return self.pools.get((pool_id or "").strip().lower())

    def spend_pool(self, pool_id: str, count: int = 1) -> dict:
        """Take from a pool. Returns what happened rather than a bare success flag.

        A pool that is merely on cooldown is a different refusal from one that is empty,
        and the player is owed the difference: "not yet" and "not any more" lead to
        different next moves.
        """
        pool = self.pool(pool_id)
        if pool is None:
            return {"ok": False, "why": f"no {pool_id} to spend"}
        if not pool.ready:
            return {"ok": False, "why": f"{pool_id} recharges in {pool.cooldown_left} "
                                        f"round{'' if pool.cooldown_left == 1 else 's'}",
                    "cooldown_left": pool.cooldown_left}
        count = max(0, int(count))
        if pool.current < count:
            return {"ok": False, "why": f"{pool_id}: {pool.current} left, {count} needed",
                    "current": pool.current}
        pool.current -= count
        return {"ok": True, "spent": count, "current": pool.current, "id": pool.id}

    def gain_pool(self, pool_id: str, count: int = 1, source: str = "") -> int:
        """Add to a pool, creating it if the character has never had one.

        Created on demand because a blood stack arrives on an enemy who has no notion of
        blood stacks until somebody puts one there.
        """
        from .resources import Pool

        pid = (pool_id or "").strip().lower()
        pool = self.pools.get(pid)
        if pool is None:
            pool = Pool(id=pid, capped=False, source=source, refresh="never")
            self.pools[pid] = pool
        pool.current += max(0, int(count))
        if pool.capped:
            pool.current = min(pool.current, pool.maximum)
        return pool.current

    def start_cooldown(self, pool_id: str, rounds: int) -> None:
        pool = self.pool(pool_id)
        if pool is not None:
            pool.cooldown_left = max(pool.cooldown_left, int(rounds))

    def refresh_pools(self, event: str, dice=None) -> list[str]:
        """Refill whatever this event refills. Returns what came back, to be narrated.

        `rest.night` also satisfies `rest.any`, because a night's sleep is a rest and a
        pool that only refilled on the exact word would quietly never come back.
        """
        satisfied = {event}
        if event == "rest.night":
            satisfied.add("rest.any")
        back = []
        for pool in self.pools.values():
            if pool.refresh in satisfied and pool.current < pool.maximum:
                pool.current = pool.maximum
                back.append(pool.id)
        return back

    def tick_pools(self, rounds: int = 1) -> list[str]:
        """Count cooldowns down. Returns what became available again."""
        ready = []
        for pool in self.pools.values():
            if pool.cooldown_left > 0:
                pool.cooldown_left = max(0, pool.cooldown_left - rounds)
                if pool.cooldown_left == 0:
                    ready.append(pool.id)
        return ready

    def carry(self, ingredient_id: str, count: int = 1, pristine: int = 0,
               at_minute: int | None = None) -> int:
        """Put raw material in the satchel. Returns the new count.

        `pristine` is how many of them came back perfect — a very good hour on the ground
        yields specimens worth more in the pot than the same herb grabbed in a hurry.
        Counted alongside rather than as a separate item, because it is the same herb.
        """
        key = (ingredient_id or "").strip().lower()
        self.inventory[key] = self.inventory.get(key, 0) + max(0, int(count))
        if pristine:
            self.pristine[key] = self.pristine.get(key, 0) + max(0, int(pristine))
        if at_minute is not None:
            # The newest handful sets the clock for the pile. Tracking each one
            # separately would mean a satchel of dated batches and a UI to explain
            # them, for a rule whose whole content is "use it or lose it".
            self.picked_at[key] = int(at_minute)
            from . import herbprep

            if herbprep.has_salt(self):
                self.preserved[key] = True
        return self.inventory[key]

    def freshness(self, ingredient_id: str, now_minute: int, prep) -> tuple[bool, int]:
        """Whether this has spoiled, and how many hours are left if it has not.

        Material carried before the clock existed has no timestamp and is treated as
        fresh: a save that retroactively spoiled somebody's satchel would be a worse
        answer than a lenient one.
        """
        from . import herbprep

        key = (ingredient_id or "").strip().lower()
        if self.preserved.get(key):
            return False, -1                       # salted; no clock runs
        picked = self.picked_at.get(key)
        if picked is None:
            return False, -1
        hours = max(0, (int(now_minute) - int(picked)) // 60)
        limit = herbprep.spoils_after(prep)
        return hours >= limit, max(0, limit - hours)

    def spend(self, ingredient_id: str, count: int = 1) -> int:
        """Take raw material out. Returns how many were actually taken.

        An entry that reaches zero is removed rather than left at 0, for the same reason
        an emptied jar leaves the shelf: a count of nothing is something the page offers
        and the next preview refuses.
        """
        key = (ingredient_id or "").strip().lower()
        have = self.inventory.get(key, 0)
        took = min(have, max(0, int(count)))
        if not took:
            return 0
        self.inventory[key] = have - took
        if self.inventory[key] <= 0:
            del self.inventory[key]
        return took

    def add_stock(self, item, count: int = 1) -> None:
        """Put a crafted thing on the shelf, stacking with its own kind."""
        have = self.stock.get(item.id)
        if have is None:
            item.count = count
            self.stock[item.id] = item
        else:
            have.count += count

    def take_stock(self, stock_id: str, count: int = 1) -> int:
        """Spend some. Returns how many were actually taken.

        An entry that reaches zero is removed rather than left at 0 — an empty jar on the
        shelf is a jar the crafting page offers you and then refuses.
        """
        have = self.stock.get(stock_id)
        if have is None:
            return 0
        took = min(have.count, max(0, int(count)))
        have.count -= took
        if have.count <= 0:
            del self.stock[stock_id]
        return took

    def add_condition(self, key: str, rounds: int | None = None, source: str = "") -> Condition:
        """A condition is an effect whose granted tags are its `rules/states.py` entry."""
        from . import states

        key = key.strip().lower()
        existing = next((e for e in self.effects
                         if e.kind == "condition" and e.key == key), None)
        if existing:
            # Same condition twice does not stack in 1e; the longer duration wins.
            if rounds is not None and (existing.rounds_left is None or rounds > existing.rounds_left):
                existing.rounds_left = rounds
            return Condition(key=key, rounds_left=existing.rounds_left,
                             source=existing.source)
        self.apply_effect(ActiveEffect(
            name=CONDITIONS.get(key, {}).get("name", key.title()), kind="condition",
            key=key, source=source,
            duration="until-dismissed" if rounds is None else "rounds",
            rounds_left=rounds, tags=states.tags_for(key)))
        return Condition(key=key, rounds_left=rounds, source=source)

    def add_buff(self, kind: str, target: str, amount: int, source: str = "",
                 rounds: int | None = None, note: str = "",
                 bonus_type: str = "", origin: str = "") -> "Buff":
        """Grant a timed bonus. Same source on the same roll reapplies, not stacks.

        `bonus_type` is 1e's channel — alchemical, morale, enhancement — and it used to
        be dropped on the floor between the author and the roll. `effectspec` has
        offered the field since it was written and every shipped consumable spec fills
        it in; `consumables` did not pass it to the op, the op had no param for it, and
        this method had no argument to receive it. So every timed bonus in the game
        entered the funnel untyped, untyped stacks with everything, and two alchemical
        +2s from two different teas were +4 where 1e gives +2 — with nothing on the
        sheet to show why.
        """
        kind, target = str(kind).strip(), str(target).strip().lower()
        typed = _bonus_type(bonus_type)
        for e in self.effects:
            if e.kind != "buff" or e.source != source or not e.modifiers:
                continue
            m = e.modifiers[0]
            if (m.get("kind"), m.get("target")) == (kind, target):
                m["amount"], m["note"] = int(amount), note
                m["bonus_type"] = typed
                e.rounds_left = rounds
                e.duration = "until-dismissed" if rounds is None else "rounds"
                e.origin = origin or e.origin
                return Buff(kind=kind, target=target, amount=int(amount),
                            source=source, rounds_left=rounds, note=note)
        self.effects.append(ActiveEffect(
            name=source or f"{int(amount):+d} {target}", kind="buff", source=source,
            origin=origin,
            duration="until-dismissed" if rounds is None else "rounds",
            rounds_left=rounds,
            modifiers=[{"kind": kind, "target": target, "amount": int(amount),
                        "bonus_type": typed, "note": note}]))
        return Buff(kind=kind, target=target, amount=int(amount), source=source,
                    rounds_left=rounds, note=note)

    def _flat_for(self, kind: str, target: str) -> bool:
        """Whether a printed stat-block number already stands in for this channel.

        A feat's term is inside the printed total, so the live read contributes nothing
        on top — every feat loop this replaced sat under the `else` of the flat branch,
        and a monster with Will +0 printed and Iron Will listed is Will +0.
        """
        t = str(target).lower()
        if kind == "skill_mod":
            return t in self.flat_skills
        if kind == "save_mod":
            return t in self.flat_saves
        if kind == "combat_mod":
            return {"initiative": self.flat_initiative is not None,
                    "ac": self.flat_ac is not None,
                    "touch_ac": self.flat_ac is not None,
                    "attack": self.flat_attack is not None,
                    "cmb": self.flat_attack is not None,
                    "damage": bool(self.flat_damage),
                    "cmd": self.flat_cmd is not None}.get(t, False)
        return False

    def standing_tags(self) -> tuple[str, ...]:
        """Tags held without an effect: a feat document's `tags`, and the class's
        proficiencies as `proficient.<category>` / `proficient.weapon.<key>`.

        `has_state` reads stored effects' tags; feats are live-read, not stored, so
        their tags need a second source or a Martial Weapon Proficiency feat is
        invisible to the one question that should see it — and the class lists were
        plain strings in `tables.CLASSES`, never tags at all. `$target` is the
        parenthetical: the feat is one weapon per taking; the whole-category grant
        the old suffix match gave (`split()[0]`) was a bug, not a rule.
        """
        from . import feats as feats_mod

        out: list[str] = []
        for p in self.class_data.get("proficiencies", ()):
            p = str(p).strip().lower()
            if p:
                out.append(f"proficient.{p}" if p in ("simple", "martial", "exotic")
                           else f"proficient.weapon.{p}")
        for raw in self.feats:
            doc = feats_mod.document(raw)
            for tag in (doc or {}).get("tags") or ():
                tag = str(tag)
                if "$target" in tag:
                    if not doc.get("target"):
                        continue                   # bound to nothing yet
                    tag = tag.replace("$target", str(doc["target"]).strip().lower())
                out.append(tag)
        # The race's own tags — `race.<id>`, its senses, its immunities — from its
        # document (rules/races.py), so "is this an elf" and "can they see in the dark"
        # are both `has_state` questions. `race == "human"` was the sheet's question
        # before this, in two places, and a world's own people could answer neither.
        race_doc = self._race_doc()
        if race_doc:
            out.extend(str(t) for t in race_doc.get("tags") or ())
        # A stat block's own tags — the watchman's `role.guard` — read live off the
        # template the creature came from, the way a feat's are read off its document.
        if self.from_template:
            from . import bestiary as bestiary_mod

            block = bestiary_mod.lookup(str(self.from_template)) or {}
            out.extend(str(t) for t in (block.get("tags") or ()) if str(t).strip())
        return tuple(out)

    def noticed(self) -> list[str]:
        """What this character has noticed and still holds: the names of the `knows.*`
        situation effects a scheme or a card granted, each carrying the sentence its
        grant said. A view like `conditions`, so the brief asks the sheet rather
        than reaching into the effect store — the severing the three-laws ratchet
        pins. Measured missing by the fairness critic (2026-09-08): a `knows.*` tag
        alone put nothing in front of the player."""
        out: list[str] = []
        for e in self.effects:
            if e.kind != "situation" or not any(str(t).startswith("knows.") for t in e.tags):
                continue
            name = str(e.name or "").strip()
            if name and " " in name and name not in out:
                out.append(name)
        return out

    def _race_doc(self) -> dict | None:
        """The race as a document, read live — the race id on the sheet is the store,
        the way the feat list is; nothing of the document is ever saved onto the
        character, so correcting a race on the bench corrects every character of it."""
        from . import races as races_mod

        if not str(self.race or "").strip():
            return None
        return races_mod.document(self.race)

    def _creature_doc(self) -> dict | None:
        """The stat block this creature was instantiated from, read live.

        The same arrangement `_race_doc` uses, and for the same reason: `from_template`
        is the store, the document is the truth, and correcting a creature on the bench
        corrects every one already standing in a scene. Nothing of the stat block is
        copied onto the actor, so there is no saved field to migrate.
        """
        key = str(getattr(self, "from_template", "") or "").strip()
        if not key:
            return None
        from . import bestiary as bestiary_mod

        # `raw`, not `lookup`: the creature's own words, before the sheet-shaped trim
        # that drops `speed_note` — which is the only place a climb speed is written.
        return bestiary_mod.raw(key)

    def movement_modes(self) -> dict[str, int]:
        """Every way this body can move, in feet, keyed by mode.

        `land` is always present and is `speed_feet` — armour and conditions already
        applied. The rest are the ways this creature is not walking, and they come from
        whichever document describes it:

          a race    `move.fly.30` tags, through `races.speeds`
          a monster "40 ft., climb 20 ft." prose, through `bestiary.speeds`

        Both doors, because the same fact is written two ways and reading only one is how
        the movement evolutions came to promise a fly speed the engine never asked about.
        A character who is both — a PC built from a race — gets the better of the two for
        any mode they disagree on, which is the same rule `races.speeds` uses within tags.

        Read live on every call rather than cached onto the sheet: a fly speed written
        into a save could not be taken away by an effect, and this is the modifier
        funnel's own argument applied to movement.
        """
        out = {"land": self.speed_feet}
        doc = self._creature_doc()
        if doc:
            from . import bestiary as bestiary_mod

            for mode, feet in bestiary_mod.speeds(doc).items():
                out[mode] = max(out.get(mode, 0), int(feet))
        race = self._race_doc()
        if race:
            from . import races as races_mod

            for mode, feet in races_mod.speeds(race).items():
                if mode == "land":
                    continue
                out[mode] = max(out.get(mode, 0), int(feet))
        return {m: f for m, f in out.items() if f > 0 or m == "land"}

    def can_move_vertically(self) -> str:
        """How this creature gets off the ground, or "" if it cannot.

        Flight first: a creature that can do both does not need a wall. The answer is a
        mode name so the tell can say *why* — "climbs" and "flies" read differently to a
        player, and a refusal that says which one is missing is actionable.
        """
        modes = self.movement_modes()
        if modes.get("fly"):
            return "fly"
        if modes.get("climb"):
            return "climb"
        return ""

    def _race_mods(self, kind: str, target: str, ctx: dict | None = None) -> list["Modifier"]:
        """Modifiers from the race document, through the same reader feats use, so a
        `when` clause or a `scope` behaves the same on a dwarf's CMD as on a feat."""
        doc = self._race_doc()
        if not doc or not doc.get("modifiers"):
            return []
        from . import resources

        want = str(target).lower()
        out: list[Modifier] = []
        for spec in doc.get("modifiers") or ():
            if not isinstance(spec, dict) or spec.get("type") != kind \
                    or str(spec.get("target", "")).lower() != want:
                continue
            if not _scope_holds(spec.get("scope"), doc, ctx) \
                    or not _when_holds(spec.get("when"), ctx):
                continue
            if spec.get("formula"):
                try:
                    amount = resources.evaluate(spec["formula"], self)
                except resources.FormulaError:
                    continue
            else:
                amount = int(spec.get("amount", 0) or 0)
            if amount:
                out.append(Modifier(amount, doc.get("name", self.race),
                                    _bonus_type(spec.get("bonus_type"))))
        return out

    def _background_mods(self, kind: str, target: str) -> list["Modifier"]:
        """Skill bonuses from the background document, read live.

        Live rather than baked into `ranks` at creation for the reason the race's are:
        a number written onto the sheet cannot be taken off again, and a background
        edited on the bench would leave every character who has it carrying the old
        one. `background` is its own bonus type, so two of them could never stack and a
        campaign trait can still be taken beside it.
        """
        if not self.background or kind != "skill_mod":
            return []
        from . import backgrounds as backgrounds_mod

        doc = backgrounds_mod.get(self.background)
        if not doc:
            return []
        want = str(target).lower()
        out: list[Modifier] = []
        for spec in doc.get("modifiers") or ():
            if not isinstance(spec, dict) or spec.get("type") != "skill_mod":
                continue
            if str(spec.get("target", "")).lower() != want:
                continue
            amount = int(spec.get("amount", 0) or 0)
            if amount:
                out.append(Modifier(amount, doc.get("name", self.background),
                                    _bonus_type(spec.get("bonus_type"))))
        return out

    def _roll_context(self, weapon_key: str | None = None, **extra) -> dict:
        """What a scoped or conditional feat term is evaluated against."""
        w = self.weapon(weapon_key)
        key = (weapon_key or self.equipped or "unarmed").strip().lower()
        return {"weapon": {"key": key, "hands": w.get("hands", 1),
                           "category": w.get("category", "melee"),
                           "light": bool(w.get("light", False)),
                           "finessable": bool(w.get("finessable", False)),
                           "ranged": w.get("category") == "ranged"},
                **extra}

    def _feat_mods(self, kind: str, target: str, ctx: dict | None = None) -> list["Modifier"]:
        """Modifiers from the feats this character holds, read off their documents.

        The sixth channel, retired: before stage 8 every feat term was a bare
        `Modifier` appended inside a builder from a hand-written Python table — untyped
        (Dodge's `dodge` sat in the table and was dropped), never through the funnel,
        and two of the sixteen (Toughness, Point-Blank Shot) read by nothing at all.
        Now a feat is read the way a worn ring is: live, from
        content/feats/mechanics, so removing the feat removes the term and nothing is
        ever saved twice.

        A modifier carrying `scope` or `when` is evaluated against `ctx`, the roll
        context the builder passes — which weapon (key, hands, category, light,
        finessable), the `power_attack` choice, the manoeuvre, the range. A key the
        context does not carry means the term is DROPPED, never applied
        unconditionally (Point-Blank Shot on a longsword would be the bug), and the
        document's `not_yet` says so. `$target` is the sheet's parenthetical — Weapon
        Focus (rapier) — and a bare Weapon Focus binds nowhere (it used to bind
        everywhere: `has_feat` matched a target of None against every weapon). The
        re-entrancy guard is for a formula: Toughness feeds `hp_max`, and
        `resources.variables` can name `hp_max`.
        """
        if getattr(self, "_reading_feats", False) or self._flat_for(kind, target):
            return []
        from . import feats as feats_mod, resources

        want = str(target).lower()
        out: list[Modifier] = []
        self._reading_feats = True
        # 1e: "If a character has the same feat more than once, its benefits do not
        # stack unless indicated otherwise." A sheet listing Iron Will twice counted
        # it twice — the verifiers measured +12 against +11 — so one document, once,
        # keyed by id and target (Weapon Focus (longsword) and (dagger) are two).
        seen: set[tuple[str, str]] = set()
        try:
            for raw in self.feats:
                doc = feats_mod.document(raw)
                if not doc:
                    continue
                key = (doc["id"], str(doc.get("target") or ""))
                if key in seen:
                    continue
                seen.add(key)
                for spec in doc.get("modifiers") or ():
                    if not isinstance(spec, dict) or spec.get("type") != kind \
                            or str(spec.get("target", "")).lower() != want:
                        continue
                    if not _scope_holds(spec.get("scope"), doc, ctx) \
                            or not _when_holds(spec.get("when"), ctx):
                        continue
                    if spec.get("formula"):
                        try:
                            amount = resources.evaluate(spec["formula"], self)
                        except resources.FormulaError:
                            continue
                    else:
                        amount = int(spec.get("amount", 0) or 0)
                    if amount:
                        out.append(Modifier(amount, doc["name"],
                                            _bonus_type(spec.get("bonus_type"))))
        finally:
            self._reading_feats = False
        return out

    def _feat_hp(self) -> int:
        """The `hp_max` channel — feats, buffs, worn gear — read in one place so
        `set_hp_max` can subtract exactly what the read added. Stacked by type like
        every other channel: two untyped Toughness-shaped terms add, two enhancement
        ones take the best."""
        return sum(m.value for m in stack(self._buff_mods("combat_mod", "hp_max")))

    def hp_max_modifiers(self) -> list["Modifier"]:
        """What the maximum is made of, itemised the way AC is.

        The verifiers found the sheet's hp block carried totals only, so Toughness
        could not name itself among the terms the way a ring does among AC terms —
        the number moved and nothing said why.
        """
        mods = [Modifier(self.hp_base, "rolled hit points")]
        con = self.ability_mod("con") * max(1, self.hit_dice)
        if con:
            mods.append(Modifier(con, f"Con × {max(1, self.hit_dice)} HD"))
        mods.extend(stack(self._buff_mods("combat_mod", "hp_max")))
        return mods

    @property
    def loses_dex_to_ac(self) -> bool:
        return any(c.data.get("lose_dex_to_ac") for c in self.conditions)

    def _buff_mods(self, kind: str, target: str, ctx: dict | None = None) -> list["Modifier"]:
        """Everything timed or worn that moves this number.

        Worn gear joins here rather than at each call site because this is the one
        funnel every roll already goes through — saves, skills, attack, AC, initiative.
        Adding it in one place is the difference between an enchanted cloak working
        everywhere and working wherever somebody remembered to ask.

        Read off every effect's modifier list, not only buffs, so an ability's
        source-tracked bonuses flow through the same funnel and the dice popup keeps
        naming every number.
        """
        want = str(target).lower()
        out: list[Modifier] = []
        for e in self.effects:
            for m in e.modifiers:
                amount = int(m.get("amount", 0) or 0)
                if m.get("kind") == kind and str(m.get("target", "")).lower() == want \
                        and amount:
                    out.append(Modifier(amount, e.source or e.name or "a preparation",
                                        _bonus_type(m.get("bonus_type"))))
        out += self._standing_mods(kind, target) + self._feat_mods(kind, target, ctx) \
            + self._race_mods(kind, target, ctx) + self._background_mods(kind, target)
        # 1e: a dodge bonus is lost whenever the Dexterity bonus to AC is lost. Twenty-
        # four shipped dodge feats had no reader for that clause, and nothing on the
        # sheet asked it of buffs either; one generic rule here, not one per feat.
        if kind == "combat_mod" and str(target).lower() in ("ac", "touch_ac", "cmd") \
                and self.loses_dex_to_ac:
            out = [m for m in out if m.type != "dodge"]
        return out

    def remove_condition(self, key: str) -> None:
        key = key.strip().lower()
        self.remove_effects(kind="condition", match=lambda e: e.key == key)

    def clear_states(self, query: str) -> list[str]:
        """End every condition whose tags answer `query`, and say which went.

        The one door for "everything that X ends". Four sites carried the same four
        condition names between them — heal, rest, the downed resolution and
        resurrection — and the copies had already drifted apart; the `recovery.*`
        families in `rules.states` say it once instead.

        Deliberately narrow: this takes a query and removes what answers it, so a caller
        cannot reach past the vocabulary and hand-roll a list again. What each family
        contains, and why sweeping a `state.*` family here would raise the dead, is
        written where the families are.
        """
        from . import states

        q = (query or "").strip().lower()
        if not q:
            return []
        gone = self.remove_effects(
            kind="condition",
            match=lambda e: any(states.matches(str(t), q) for t in e.tags))
        return [e.key for e in gone]

    def tick_conditions(self, rounds: int = 1) -> list[str]:
        """Expire everything timed. Kept as the name every caller knows; the work is
        `tick_effects`, the one ticker — conditions, temporary hit points and buffs
        used to expire in three separate loops here, and a mechanism added without a
        fourth loop was a mechanism that never wore off."""
        return self.tick_effects(rounds)

    def apply_hp_state(self) -> list[str]:
        """1e's death and unconsciousness thresholds, applied by code so nobody has to
        remember them mid-scene.

        Below 0 and above -Con you are unconscious *and dying*: losing a hit point each
        round until you stabilise or die. That last part was missing, so a downed
        character simply lay there indefinitely and the fight quietly ended — which is
        not what the rules say and not what a player would expect to happen to them.
        """
        changed = []
        # Where the bottom is. For a body it is -Con, with the dying rungs above it; for a
        # CROWD it is zero, and there are no rungs at all — Pathfinder's troop subtype:
        # "reducing a troop to 0 hit points or fewer causes it to break up, effectively
        # destroying the troop". There is no dying, no stabilising and no round-by-round
        # loss, because what has been reduced is a formation and not a body. Measured live
        # 2026-09-19: the last beat of a twelve-raider fight read "raiders is bleeding out."
        #
        # One threshold rather than a second death path, so the sentence that writes `dead`
        # is still written once. A parallel branch was the first version and the three laws'
        # ratchet caught it: two copies of a ladder is how one of them goes stale.
        con = self.ability_score("con")
        floor = 0 if self.troop is not None else -con
        if self.hp <= floor and not self.has_condition("dead"):
            # `disabled` belongs on the list and was missing from it. Most deaths never
            # stop at exactly 0 hit points, so nobody had ever been disabled and then
            # killed — until drowning, which walks a body down the ladder one rung a
            # round (0, then -1, then dead) and left a corpse that was still "conscious,
            # and a standard action costs a hit point".
            for gone in _DOWN_THE_LADDER:
                self.remove_condition(gone)
            self.add_condition("dead", source="hit points")
            changed.append("dead")
        elif (self.hp < 0 or (self.hp == 0 and self.drown_failures)) \
                and not self.has_condition("dead"):
            # Drowning enters here at exactly 0, which every other route to 0 does not.
            # "He falls unconscious (0 hp)" is the book's own sentence and it overrides
            # the book's own threshold: a sword that leaves you on nothing leaves you
            # DISABLED — upright, conscious, and a standard action costs a hit point —
            # and a lungful of water does not. The rule lives here with the other
            # thresholds because this is the one place that owns what a hit point total
            # means, and `Engine.breathe` owns only the schedule that got them here.
            if self.has_state("ferocity"):
                if not self.has_state("state.impaired.staggered"):
                    self.add_condition("staggered", source="ferocity")
                    changed.append("staggered")
            elif not self.has_condition("unconscious"):
                self.add_condition("unconscious", source="hit points")
                changed.append("unconscious")
            # Stabilising once keeps you stable; fresh damage starts it again. Not at
            # exactly 0, though: a drowning character is unconscious for a round BEFORE
            # they start dying, which is the middle rung of the three-round fall.
            if self.hp < 0 and not self.has_condition("stable") \
                    and not self.has_condition("dying"):
                self.add_condition("dying", source="hit points")
                changed.append("dying")
        elif self.hp == 0 and not self.has_condition("disabled"):
            # Exactly 0 is disabled, not dying: conscious, but a standard action costs
            # a hit point and starts it.
            self.add_condition("disabled", source="hit points")
            changed.append("disabled")

        changed.extend(self.apply_nonlethal_state())
        return changed

    def apply_nonlethal_state(self) -> list[str]:
        """Non-lethal damage against its own threshold.

        1e: staggered when it equals your current hit points, unconscious when it passes
        them — and unconscious, not *dying*. Somebody beaten senseless with a sap is not
        bleeding out, and treating the two the same would have the engine roll them a
        stabilisation check every round for a bruise.
        """
        changed = []
        limit = self.nonlethal_threshold
        if self.has_condition("dead"):
            return changed

        if self.nonlethal > limit:
            if not self.has_condition("unconscious"):
                self.add_condition("unconscious", source="non-lethal damage")
                changed.append("unconscious")
            self.remove_condition("staggered")
        elif self.nonlethal == limit and limit > 0:
            if not self.has_condition("staggered"):
                self.add_condition("staggered", source="non-lethal damage")
                changed.append("staggered")
        else:
            # Healed back below the line: whichever of the two this caused, it lifts.
            for gone in ("staggered", "unconscious"):
                c = next((x for x in self.conditions if x.key == gone), None)
                if c is not None and c.source == "non-lethal damage":
                    self.remove_condition(gone)
        return changed

    def rest(self, kind: str = "night") -> dict:
        """Natural healing (CRB p.191).

        "With a full night's rest (8 hours of sleep or more), you recover 1 hit point per
        character level... If you undergo complete bed rest for an entire day and night,
        you recover twice your character level in hit points."

        Nobody heals from below zero by sleeping it off — a dying character needs
        stabilising first, which is `bleed_out`'s business, not this one.
        """
        if kind not in ("night", "bed rest"):
            raise ValueError(f"rest must be a night or bed rest, not {kind!r}")
        if self.has_condition("dead"):
            return {"healed": 0, "hours": 0, "woke": False, "note": "the dead do not rest"}

        per_level = 2 if kind == "bed rest" else 1
        hours = 24 if kind == "bed rest" else 8

        before = self.hp
        # Below zero you are not resting, you are bleeding. Healing starts from 0 so a
        # night's sleep cannot carry someone from -6 to a comfortable 4.
        floor = max(self.hp, 0)
        self.hp = min(self.hp_max, floor + per_level * max(1, self.level))

        woke = bool(self.hp > 0 and self.clear_states("recovery.hit-points"))
        # You stand up in the morning. Waking still prone, shaken and entangled from a
        # fight the night before is the sort of stale state that quietly poisons every
        # roll for the rest of the campaign.
        self.clear_states("recovery.rest")
        # A night's sleep is what fatigue is for. Exhaustion becomes fatigue instead.
        if self.has_condition("exhausted"):
            self.remove_condition("exhausted")
            self.add_condition("fatigued", source="slept off exhaustion")
        elif self.has_condition("fatigued"):
            self.remove_condition("fatigued")

        # "Ability damage returns at a rate of 1 point per day, or 2 points per day of
        # complete bed rest, for each affected ability score." Per ability, not shared
        # between them — a poison that hit both Strength and Constitution heals both at
        # the same rate rather than taking twice as long.
        # "You heal non-lethal damage at the rate of 1 hit point per hour per character
        # level" — eight hours clears anything a level 1 character could still be standing
        # under, so a night wipes it rather than pretending to count.
        nonlethal_gone = self.nonlethal
        self.nonlethal = 0
        # A night is what the awake clock is measured against, so a night resets it.
        from . import survival

        survival.sleep(self, hours)
        # A night undoes the morning's preparation as well as the day's wounds. Leaving
        # them prepared would let a wizard sleep off their slot spending and keep the
        # spells they had already cast — the slots refill and the preparation does not.
        self.prepared = {}

        restored = {}
        for ab in list(self.ability_damage):
            back = self.heal_ability(ab, per_level)
            if back:
                restored[ab] = back

        return {"healed": self.hp - before, "hours": hours, "woke": woke,
                "per_level": per_level, "kind": kind, "ability": restored,
                "nonlethal_healed": nonlethal_gone}

    def bleed_out(self, dice) -> dict | None:
        """One round of dying: lose a hit point, then try to stabilise.

        PF1e: a Constitution check against DC 10 + the negative hit point total. Success
        makes you stable; failure takes you a point closer to dead.
        """
        if not self.has_condition("dying") or self.has_condition("dead"):
            return None
        self.hp -= 1
        con = self.ability_score("con")
        if self.hp <= -con:
            self.apply_hp_state()
            return {"ref": self.ref, "outcome": "dead", "hp": self.hp}

        dc = 10 + abs(self.hp)
        roll = dice.d20([Modifier(self.ability_mod("con"), "Con")],
                        label=f"{self.name} stabilise", visibility="hidden")
        if roll.total >= dc:
            self.remove_condition("dying")
            self.add_condition("stable", source="stabilised")
            return {"ref": self.ref, "outcome": "stable", "hp": self.hp,
                    "roll": roll.total, "dc": dc}
        return {"ref": self.ref, "outcome": "dying", "hp": self.hp,
                "roll": roll.total, "dc": dc}

    # --- serialisation ------------------------------------------------------------------

    def _needs_summary(self) -> list[dict]:
        """Hunger, thirst and rest as the side panel shows them.

        Each need reports where it stands and what going without costs, in the rules'
        own numbers — the consequence text is the same arithmetic `survival.pass_hours`
        runs, said before it happens instead of discovered when it does.
        """
        from . import survival

        out = []
        fed_h = int(self.fed_minutes) // 60
        wat_h = int(self.watered_minutes) // 60
        awake_h = int(self.awake_minutes) // 60

        def entry(key, label, exempt_rule, hours, grace, state_hungry, detail):
            if survival.exempt(self, exempt_rule):
                return {"id": key, "label": label, "state": "no need", "danger": False,
                        "detail": "This character is exempt; no checks are ever made."}
            left = grace - hours
            if left > 0:
                state = f"{left}h of grace left"
                danger = left <= 4
            else:
                state = state_hungry
                danger = True
            return {"id": key, "label": label, "state": state, "danger": danger,
                    "detail": detail}

        out.append(entry(
            "water", "Thirst", survival.NO_WATER, wat_h,
            survival.hours_until_thirsty(self),
            f"parched — a check every hour, DC {survival.thirst_dc(self.thirst_checks)}",
            "After a day plus Con-score hours without water: a Constitution check "
            "every hour, harder each time. Failure deals non-lethal damage and "
            "fatigues; enough of it and you drop."))
        out.append(entry(
            "food", "Hunger", survival.NO_FOOD, fed_h,
            survival.hours_until_hungry(self),
            f"starving — a check every day, DC {survival.hunger_dc(self.hunger_checks)}",
            "After three days without food: a Constitution check each day, harder "
            "each time. Failure deals non-lethal damage and fatigues."))
        out.append(entry(
            "sleep", "Rest", survival.NO_SLEEP, awake_h,
            survival.AWAKE_GRACE_HOURS,
            f"past a day awake — Will save every active hour, "
            f"DC {survival.awake_dc(awake_h)}",
            "Past twenty-four hours awake: a Will save every hour spent working. "
            "Failure deals non-lethal damage and fatigues, then exhausts — and the "
            "hour you fail badly is the hour you fall where you stand."))
        return out

    def summary(self) -> dict:
        from . import xp as xp_mod

        out = {
            "xp": {"have": int(self.xp),
                   "next": xp_mod.total_for(min(20, self.level + 1)),
                   "ready": xp_mod.ready_to_level(self)},
            "needs": self._needs_summary(),
            "ref": self.ref,
            "name": self.name,
            "kind": self.kind,
            "hp": self.hp,
            "hp_max": self.hp_max,
            "temp_hp": self.temp_hp,
            "nonlethal": self.nonlethal,
            "nonlethal_threshold": self.nonlethal_threshold,
            "dr": [r.label for r in self.reductions],
            # A 10 that used to be a 14 is not the same as a 10, and the grid shows only
            # the score. Without this the player sees a number and no reason for it.
            "ability_damage": {a: self.ability_damage.get(a, 0)
                               + self.ability_drain.get(a, 0)
                               for a in ABILITIES
                               if self.ability_damage.get(a) or self.ability_drain.get(a)},
            "gear_damaged": [i.name for i in self.gear.values() if i.hp < i.hp_max],
            "world_classes": _world_class_summary(self),
            # What this character could cast right now. The side panel carried no spell
            # information at all, which is why the combat panel had no Cast button and a
            # spellcaster's whole turn had to be typed at the narrator — casting itself
            # has worked in the engine the whole time.
            "castable": _castable_summary(self),
            "satchel": _satchel_summary(self),
            # Everything crafted, on the side panel rather than only the full sheet:
            # four more crafts now make things, and a forged blade the player cannot
            # see is a blade they cannot wear.
            "stock": [_stock_row(item) for _, item in
                      sorted(self.stock.items(), key=lambda kv: kv[1].name.lower())],
            "worn": [w["name"] for w in self.worn_items()],
            # The side panel is the only sheet most turns ever show, so what the
            # character is carrying and what is in their purse belong on it.
            "carrying": [{"name": n, "count": c} for n, c in sorted(self.goods.items())],
            "purse": dict(self.purse),
            "pools": [{"id": p.id, "current": p.current, "max": p.maximum,
                       "ready": p.ready, "cooldown_left": p.cooldown_left}
                      for p in self.pools.values()],
            "ac": self.ac(),
            "speed": self.speed_feet,
            "conditions": [{"key": c.key, "name": c.name, "rounds_left": c.rounds_left}
                           for c in self.conditions],
            "buffs": [{"kind": b.kind, "target": b.target, "amount": b.amount,
                       "source": b.source, "rounds_left": b.rounds_left}
                      for b in self.buffs],
        }
        if self.is_pc:
            out["class"] = f"{self.class_data.get('name', '')} {self.level}".strip()
            out["race"] = self.race
            out["heritage"] = self.heritage
            out["abilities"] = {a: self.ability_score(a) for a in self.abilities}
            out["saves"] = {
                k: sum(m.value for m in self.save_modifiers(k)) for k in SAVES
            }
            out["skills"] = {
                s: sum(m.value for m in self.skill_modifiers(s))
                for s in sorted(self.ranks)
            }
            from . import feats as feats_mod

            out["feats"] = [f if self._feat_target(f)
                            else (feats_mod.document(f) or {}).get("name", f)
                            for f in self.feats]
            out["weapon"] = self.weapon()["name"]
        return out


def _herb_name(iid: str) -> str:
    from . import ingredients as ing_mod

    found = ing_mod.all_ingredients().get(iid)
    return found.name if found else iid.replace("-", " ").title()


def _stock_row(item) -> dict:
    """One crafted jar, with what can be done to it.

    `drinkable` and `throwable` are asked of `rules.consumables` rather than guessed from
    the name, so the button on the sheet and the refusal from the engine cannot disagree:
    a jar that does nothing harmful has nothing to throw, and the sheet should not offer.
    """
    from . import consumables as con

    d = item.as_dict()
    d["poisons"] = [p.as_dict() for p in con.poisons(item.specs, source=item.base)]
    # A maker that stated how its work is used is believed; herbalism's jars state
    # nothing and are asked, which is how they have always been judged. This is the
    # difference between a brewed tea (ask the effects) and a forged breastplate (the
    # smith already said: not drinkable, worn at the armour slot).
    declared = list(getattr(item, "how", []) or [])
    if declared:
        d["drinkable"] = "drink" in declared
        d["throwable"] = "throw" in declared
        d["coatable"] = "coat" in declared
    else:
        d["drinkable"] = con.plan(item, how="drink").ok
        d["throwable"] = con.plan(item, how="throw").ok
        d["coatable"] = con.plan(item, how="coat").ok
    return d


def _terms(mods: list[Modifier]) -> dict:
    return {"total": sum(m.value for m in mods),
            "terms": [m.as_dict() for m in mods]}


def body_slots(actor: Actor) -> dict:
    """Every body slot, in the order it is worn down the figure.

    Empty slots are returned as `None` rather than omitted — the whole point of drawing
    the slots is to show what is *not* filled, so a blank has to be a thing the sheet
    knows about.

    The armour and shield slots read from the character's worn armour rather than from
    the slot store, because those are already tracked and having two places to say what
    someone is wearing is how they end up disagreeing.
    """
    def one(key: str) -> dict:
        spec = SLOTS[key]
        items = list(actor.slot_list(key))
        if key == "armor" and actor.armour != "none":
            items[0] = ARMOUR[actor.armour]["name"]
        if key == "shield" and actor.shield != "none":
            items[0] = SHIELDS[actor.shield]["name"]
        rules_limit = SLOT_RULES_LIMIT.get(key, 1)
        return {
            "key": key,
            "label": spec["label"],
            "holds": spec["holds"],
            "max": spec["max"],
            "rules_limit": rules_limit,
            "derived": key in ("armor", "shield"),
            "items": [
                {"index": i, "item": it, "empty": it is None,
                 # Slots past the rules limit are recorded but do not stack — a third
                 # ring is worn, not working.
                 "beyond_rules": i >= rules_limit}
                for i, it in enumerate(items)
            ],
        }

    left = [one(k) for k in SLOT_ORDER_LEFT]
    right = [one(k) for k in SLOT_ORDER_RIGHT]
    return {
        "left": left,
        "right": right,
        # Counted from the built slots, not from the store, so the armour and shield
        # filled by the character's own gear are included. Counting the store alone
        # reported "0 slots filled" on a page visibly showing leather armour.
        "filled": sum(1 for s in left + right for it in s["items"] if not it["empty"]),
        "total": sum(len(s["items"]) for s in left + right),
    }


def full_sheet(actor: Actor) -> dict:
    """Everything on the character, with every number's provenance attached.

    This is the app's whole proposition made literal: not "Stealth +9" but "+1 ranks,
    +3 class skill, +3 Dex, +2 Stealthy". The section names match the Pathfinder Player
    Character Folio, so a player who knows the paper sheet knows where to look.
    """
    cls = actor.class_data
    weapons = actor.weapons or ([actor.equipped] if actor.equipped else ["unarmed"])

    from . import weapons as weapons_mod

    attacks = []
    for key in dict.fromkeys(w.lower() for w in weapons if w):
        if not weapons_mod.has(key):
            continue
        w = weapons_mod.get(key)
        attacks.append({
            "key": key,
            "name": w["name"],
            "equipped": key == (actor.equipped or "").lower(),
            "category": w["category"],
            "hands": w.get("hands", 1),
            "proficient": actor.is_proficient(key),
            "attack": _terms(actor.attack_modifiers(key)),
            "damage": _terms(actor.damage_modifiers(key)),
            "damage_dice": actor.damage_dice(key),
            "crit": (f"{w['crit_range']}-20" if w["crit_range"] < 20 else "20")
                    + f"/x{w['crit_mult']}",
            "type": w["type"],
            "sequence": len(actor.attack_sequence(key, full_attack=True)),
        })

    skills = []
    for name in sorted(SKILLS):
        ability, trained_only, acp = SKILLS[name]
        rank = actor.ranks.get(name, 0)
        if trained_only and rank == 0 and name not in actor.flat_skills:
            # Cannot be attempted at all; listed so the absence is visible, not silent.
            skills.append({"name": name, "ability": ability, "rank": 0,
                           "class_skill": name in cls.get("class_skills", ()),
                           "trained_only": True, "usable": False,
                           "total": None, "terms": []})
            continue
        t = _terms(actor.skill_modifiers(name))
        skills.append({
            "name": name, "ability": ability, "rank": rank,
            "class_skill": name in cls.get("class_skills", ()),
            "trained_only": trained_only, "armour_check": acp, "usable": True,
            **t,
        })

    from . import feats as feats_mod

    feats = []
    for f in actor.feats:
        base = Actor._feat_name(f)
        known = None
        target = Actor._feat_target(f)
        # The index carries all 1,474 and the hand-written table carries the sixteen the
        # engine computes with. A feat in the index but not the table used to read
        # "carried as flavour — the engine applies nothing", which is true about the
        # arithmetic and useless to a player trying to remember what the feat does.
        entry = None
        try:
            entry = feats_mod.get(base)
        except KeyError:
            pass
        # Stage 8: the document is what the engine applies; the table's copy is what
        # remains until 8c retires the last name-branches.
        doc = feats_mod.document(f)

        if doc:
            effect = _document_effect_text(doc)
        elif entry and entry.benefit:
            effect = entry.benefit
        else:
            effect = "carried as flavour — the engine applies nothing"

        name = (doc or known or {}).get("name") or (entry.name if entry else f)
        feats.append({
            "name": name + (f" ({target})" if target else ""),
            "applied": doc is not None or known is not None,
            "known": entry is not None,
            "id": entry.id if entry else "",
            "types": entry.types if entry else [],
            "source": entry.source if entry else "",
            "prerequisites": entry.prerequisites_text if entry else "",
            "effect": effect,
        })

    maneuvers = []
    for key, m in sorted(MANEUVERS.items()):
        maneuvers.append({
            "name": m["name"],
            "cmb": _terms(actor.cmb_modifiers(key)),
            "effect": m["effect"],
            "size_limit": m.get("size_limit"),
        })

    armour = ARMOUR.get(actor.armour, ARMOUR["none"])
    shield = SHIELDS.get(actor.shield, SHIELDS["none"])

    # Every named thing the sheet might show, with its text, for the click-popover.
    # The feats' computed effect lines are merged on top of the static glossary, because
    # the sheet derives some of those ("+1 AC" for Dodge) from mechanics rather than
    # carrying prose for them.
    from . import glossary as glossary_mod

    glossary = glossary_mod.build(actor)

    return {
        "glossary": glossary,
        "identity": {
            "name": actor.name,
            "class": f"{cls.get('name', '')} {actor.level}".strip(),
            "race": actor.race,
            "heritage": actor.heritage,
            "pronouns": actor.pronouns,
            "gender": actor.gender,
            "size": actor.size,
            "world_people_id": actor.world_people_id,
            "world_entity_id": actor.world_entity_id,
        },
        # What the class actually grants at this level, read from the class data rather
        # than from the class *name*. The header said "Blood Bending 1" and nothing on
        # the sheet said what a Blood Bender could do.
        "class_features": _class_features(actor),
        # The whole twenty-level table, reached rows and unreached alike, because the
        # point of showing a class is deciding what to build towards. Plus the paths
        # this class offers and the ones this character follows.
        "progression": _progression(actor),
        # What the race gives you. The tab is called "Feats & Traits" and listed only
        # feats: a half-orc's darkvision and ferocity were nowhere on the sheet, so the
        # one place a player checks what their character can do was silent about half
        # of it.
        "traits": _racial_traits(actor),
        # How this body moves, senses and fights, off the race document: a Korvu's
        # fly speed and blindsense, an eidolon-built race's claws. Shown beside the
        # traits so what the tags grant is on the one page a player checks.
        "body": _race_body(actor),
        "abilities": [
            {"key": a, "name": ABILITY_NAMES[a], "score": actor.ability_score(a),
             "modifier": actor.ability_mod(a),
             "base": actor.abilities.get(a, 10),
             # Shown apart, because a 10 that used to be a 14 is not the same as a 10.
             "damage": actor.ability_damage.get(a, 0),
             "drain": actor.ability_drain.get(a, 0)}
            for a in ABILITIES
        ],
        "defense": {
            "hp": {"current": actor.hp, "max": actor.hp_max,
                   # Stage 8: the maximum itemised, so a feat names itself here the
                   # way a ring does among the AC terms.
                   "max_terms": _terms(actor.hp_max_modifiers()),
                   "temp": actor.temp_hp, "temp_source": actor.temp_hp_source,
                   # The threshold travels with the number, because the number alone says
                   # nothing: 12 non-lethal is nothing at 40 hit points and is a knockout
                   # at 11, and a Blood Bender's line moves as their wards go up and down.
                   "nonlethal": actor.nonlethal,
                   "nonlethal_threshold": actor.nonlethal_threshold},
            "speed": {"base": actor.speed, "current": actor.speed_feet},
            "compulsions": [c.as_dict() for c in actor.compulsions],
            "dr": [{"label": r.label, "amount": r.amount, "bypass": r.bypass,
                    "source": r.source} for r in actor.reductions],
            "temp_pools": [{"amount": p.amount, "source": p.source,
                            "rounds_left": p.rounds_left} for p in actor.temp_pools],
            # Everything carried that is not a weapon, a herb or a jar: whatever the
            # fiction has handed over. Named, counted, and honest about which of them
            # the engine has rules for — see rules/goods.py.
            "carrying": [{"name": name, "count": n,
                          "line": goods.describe(name, n),
                          "known": goods.known_item(name) is not None}
                         for name, n in sorted(actor.goods.items())],
            # The jars. `goods` is only the things the fiction handed over, so thirty
            # crafted tinctures sat in `stock`, visible on the crafting bench and nowhere
            # on the character sheet — "my crafted tinctures don't appear in my inventory".
            # They are the most usable thing the character owns and they were the one
            # thing the Inventory tab did not list.
            "stock": [_stock_row(item) for _, item in
                      sorted(actor.stock.items(), key=lambda kv: kv[1].name.lower())],
            # And the raw material, which is not usable but is carried and does spoil.
            "satchel": [{"id": iid, "name": _herb_name(iid), "count": n}
                        for iid, n in sorted(actor.inventory.items()) if n > 0],
            "purse": {"coins": dict(actor.purse),
                      "copper": goods.in_copper(actor.purse)},
            # Only gear something has happened to. An undamaged sword has no record.
            "gear": [{"name": i.name, "material": i.material, "hardness": i.hardness,
                      "hp": i.hp, "hp_max": i.hp_max,
                      "state": "destroyed" if i.destroyed
                               else "broken" if i.broken else "worn"}
                     for i in actor.gear.values() if i.hp < i.hp_max],
            "ac": _terms(actor.ac_modifiers("melee")),
            "ac_flat_footed": _terms(actor.ac_modifiers("melee", flat_footed=True)),
            "ac_touch": _terms(actor.touch_ac_modifiers()),
            "saves": [
                {"key": k, "name": SAVES[k], **_terms(actor.save_modifiers(k))}
                for k in SAVES
            ],
            "cmd": _terms(actor.cmd_modifiers()),
            "cmd_flat_footed": _terms(actor.cmd_modifiers(flat_footed=True)),
            "conditions": [
                {"name": c.name, "rounds_left": c.rounds_left,
                 "note": c.data.get("note", ""), "source": c.source}
                for c in actor.conditions
            ],
        },
        "offense": {
            "bab": actor.bab,
            "initiative": _terms(actor.initiative_modifiers()),
            "cmb": _terms(actor.cmb_modifiers()),
            "attacks": attacks,
            "maneuvers": maneuvers,
        },
        "skills": skills,
        "feats": feats,
        "equipment": {
            "armour": {"name": armour["name"], "ac": armour["ac"],
                       "max_dex": armour["max_dex"], "acp": armour["acp"]},
            "shield": {"name": shield["name"], "ac": shield["ac"], "acp": shield["acp"]},
            "armour_check_penalty": actor.armour_check_penalty,
            "weapons": [weapons_mod.get(w)["name"] for w in weapons
                        if w and weapons_mod.has(w)],
            "slots": body_slots(actor),
        },
        "background": {
            "heritage": actor.heritage,
            "notes": actor.notes.strip(),
            # The past chosen in the forge, and the sentences this world filled into it.
            # Read off the document rather than stored, for the same reason the skill
            # bonus is: a background edited on the bench must not leave every character
            # who has it showing the old words.
            "past": _background_sheet(actor),
        },
        # None rather than an empty structure for a fighter, so the page can tell "does
        # not cast" from "casts nothing today" — they look identical and are not.
        "spells": _spell_sheet(actor),
    }


def _background_sheet(actor: Actor) -> dict | None:
    """What the sheet shows about where this character was before turn one.

    None rather than an empty dict for somebody who chose no past, so the pane can tell
    "came from nowhere in particular" — a real answer in the forge — from "has a
    background whose document has gone missing", which is a fault.

    The ties are the half worth showing. The two skill points are already itemised with
    every other modifier; the sentences are the only place a player can read back the
    name of the person their character used to work for, and until this they existed
    only in the opening paragraph and in the model's brief.
    """
    if not actor.background:
        return None

    from . import backgrounds as backgrounds_mod

    doc = backgrounds_mod.get(actor.background) or {}
    return {
        "id": actor.background,
        "name": doc.get("name") or actor.background,
        "summary": doc.get("summary", ""),
        "line": backgrounds_mod.line(doc) if doc else "",
        "ties": backgrounds_mod.remembered(actor),
        # A character made before the campaign began has chosen a past that nothing has
        # filled yet. The pane says so rather than showing an empty list.
        "bound": bool(backgrounds_mod.remembered(actor)),
    }


def _spell_sheet(actor: Actor) -> dict | None:
    """The spellcasting half of the sheet, or None for everybody who does not cast."""
    from . import casting, spells as spells_mod

    if not casting.is_caster(actor):
        return None
    data = casting.caster_data(actor)

    def entry(spell_id: str) -> dict:
        try:
            spell = spells_mod.get(spell_id)
        except KeyError:
            # A book naming a spell this build does not ship is worth showing as a gap
            # rather than dropping: a silently shorter list is not a thing anyone notices.
            return {"id": spell_id, "name": spell_id, "missing": True}
        return {"id": spell.id, "name": spell.name, "line": spell.line,
                "level": casting.spell_level_for(actor, spell),
                "school": spell.school, "range": spell.range,
                "duration": spell.duration, "save": spell.saving_throw,
                "components": spell.components,
                "prepared": casting.prepared_count(actor, spell.id)}

    known = sorted(
        (entry(sid) for sid in _reachable_spells(actor, data)),
        key=lambda e: (e.get("level") if e.get("level") is not None else 99,
                       e["name"]),
    )
    return {
        "ability": data.get("ability", ""),
        "kind": data.get("kind", ""),
        "list": data.get("list", ""),
        "caster_level": casting.caster_level(actor),
        "highest": casting.highest_spell_level(actor),
        "note": data.get("note", ""),
        "slots": [{"level": lvl, "max": total,
                   "left": casting.slots_left(actor, lvl),
                   "dc": casting.save_dc(actor, lvl)}
                  for lvl, total in sorted(casting.slots_for(actor).items())],
        "known": known,
    }


def _reachable_spells(actor: Actor, data: dict) -> list[str]:
    """What to list. A wizard's book is a handful of ids; a cleric's list is hundreds, so
    for them the sheet shows what is prepared rather than the entire class list."""
    if data.get("prepare_from") == "spellbook":
        return list(dict.fromkeys(list(actor.spellbook) + list(actor.prepared)))
    return list(actor.prepared)


def _document_effect_text(doc: dict) -> str:
    """What a feat document applies, in the sheet page's words.

    Generated from the document rather than written per feat, so the page cannot say
    "bonus hit points" for a feat that adds none — which is what the hand-written
    text did for Toughness for as long as the table had no reader.
    """
    bits = []
    for spec in doc.get("modifiers") or ():
        if not isinstance(spec, dict):
            continue
        amount = spec.get("formula") or f"{int(spec.get('amount', 0) or 0):+d}"
        what = str(spec.get("target", "")).replace("_", " ")
        typed = str(spec.get("bonus_type") or "")
        typed = f" ({typed})" if typed and typed != "untyped" else ""
        waits = " — when " + ", ".join(
            f"{k} {v}" for k, v in (spec.get("when") or {}).items()) if spec.get("when") else ""
        bits.append(f"{amount} {what}{typed}{waits}")
    for tag in doc.get("tags") or ():
        bits.append(f"grants {tag}")
    for name, formula in (doc.get("budget") or {}).items():
        bits.append(f"{name.replace('_', ' ')}: {formula}")
    if doc.get("attack_ability"):
        bits.append(f"{str(doc['attack_ability'].get('use', '')).title()} in place of "
                    f"Str on attack rolls")
    text = "; ".join(bits) or "no mechanical effect recorded"
    if doc.get("not_yet"):
        text += ". Not yet: " + "; ".join(str(x) for x in doc["not_yet"])
    return text


def _scope_holds(scope, doc: dict, ctx: dict | None) -> bool:
    """A `scope` binds a term to one thing — the weapon or the manoeuvre in hand.

    `$target` is the sheet's parenthetical; a feat with none binds nowhere. No context
    at all (a bare `_buff_mods` read) means a scoped term does not apply.
    """
    if not scope:
        return True
    if not isinstance(scope, dict) or not ctx:
        return False
    for key, want in scope.items():
        want = str(want)
        if want == "$target":
            want = str(doc.get("target") or "")
            if not want:
                return False
        if key == "weapon":
            have = str((ctx.get("weapon") or {}).get("key", ""))
        else:
            have = str(ctx.get(key, "") or "")
        if have.strip().lower() != want.strip().lower():
            return False
    return True


def _when_holds(when, ctx: dict | None) -> bool:
    """A `when` is a condition on the roll context; an unevaluable key means no.

    `{"weapon": {"category": "melee", "hands": 2}}` compares each weapon field;
    `{"choice": "power_attack"}` asks the attack op's boolean; `{"range_ft": {"lte":
    30}}` needs a range the context does not carry yet, so it is dropped — the plan's
    rule for every clause nothing can evaluate.
    """
    if not when:
        return True
    if not isinstance(when, dict) or ctx is None:
        return False
    for key, want in when.items():
        if key == "weapon":
            w = ctx.get("weapon") or {}
            for field_name, value in (want or {}).items():
                if field_name not in w or w[field_name] != value:
                    return False
        elif key == "choice":
            if not ctx.get(str(want)):
                return False
        elif isinstance(want, dict):
            have = ctx.get(key)
            if have is None:
                return False
            ops = {"lte": lambda a, b: a <= b, "gte": lambda a, b: a >= b,
                   "lt": lambda a, b: a < b, "gt": lambda a, b: a > b,
                   "eq": lambda a, b: a == b}
            for op, bound in want.items():
                if op not in ops or not ops[op](have, bound):
                    return False
        else:
            if ctx.get(key) != want:
                return False
    return True


def to_dict(actor: Actor) -> dict:
    """Round-trips through `from_dict`. The campaign save is a file a person can read,
    which is the same choice World Bible made and for the same reason."""
    return {
        "ref": actor.ref, "name": actor.name, "kind": actor.kind, "level": actor.level,
        "class": actor.char_class, "size": actor.size, "abilities": actor.abilities,
        "ranks": actor.ranks, "feats": actor.feats, "armour": actor.armour,
        "shield": actor.shield, "natural_armour": actor.natural_armour,
        "weapons": actor.weapons, "equipped": actor.equipped,
        "hp": actor.hp, "hp_max": actor.hp_max,
        # The total above includes the feat channel; see from_dict.
        "hp_channels": ["feat"],
        "nonlethal": actor.nonlethal, "speed": actor.speed,
        "compulsions": [c.as_dict() for c in actor.compulsions],
        "coating": dict(actor.coating),
        # The water's two counters and the footing that goes with them. A save taken
        # mid-dive that forgot how long the breath had been held would hand the diver a
        # fresh lungful for reloading, which is the cheapest cheat in the game.
        "held_breath_rounds": actor.held_breath_rounds,
        "drown_failures": actor.drown_failures,
        "swim_check_made": actor.swim_check_made,
        "awake_minutes": actor.awake_minutes, "fed_minutes": actor.fed_minutes,
        "watered_minutes": actor.watered_minutes,
        "thirst_checks": actor.thirst_checks, "hunger_checks": actor.hunger_checks,
        "xp": actor.xp, "xp_value": actor.xp_value,
        "from_template": actor.from_template,
        "pristine": {k: int(v) for k, v in actor.pristine.items() if int(v) > 0},
        "picked_at": dict(actor.picked_at),
        "preserved": {k: bool(v) for k, v in actor.preserved.items() if v},
        "kit_pending": dict(actor.kit_pending),
        "spellbook": list(actor.spellbook),
        "prepared": {k: int(v) for k, v in actor.prepared.items() if int(v) > 0},
        "temp_pools": [{"amount": p.amount, "source": p.source,
                        "rounds_left": p.rounds_left} for p in actor.temp_pools],
        "ability_damage": dict(actor.ability_damage),
        "ability_drain": dict(actor.ability_drain),
        "hit_dice_per_level": actor.hit_dice_per_level,
        "overrides": dict(actor.overrides),
        "gear": {k: {"name": i.name, "material": i.material, "hardness": i.hardness,
                     "hp": i.hp, "hp_max": i.hp_max} for k, i in actor.gear.items()},
        # `Stock.as_dict()` rather than a field list written out again here. The field
        # list was a second copy of the same knowledge, and when `specs` was added to
        # Stock it reached the crafting page and the save file and not this one — so a
        # crafted poison survived one reload as a paragraph with no mechanics left. The
        # extra derived keys `as_dict` carries are ignored by `from_stock_dict`.
        "stock": {k: v.as_dict() for k, v in actor.stock.items()},
        "inventory": dict(actor.inventory),
        "goods": dict(actor.goods),
        "purse": dict(actor.purse),
        "pools": {k: v.as_dict() for k, v in actor.pools.items()},
        "world_classes": {k: {"level": p.level, "mp": p.mp, "crafted": p.crafted,
                              "mishaps": p.mishaps, "milestones": p.milestones}
                          for k, p in actor.world_classes.items()},
        "reductions": [{"amount": r.amount, "bypass": r.bypass, "source": r.source}
                       for r in actor.reductions],
        # Written even when empty. A save that omits an empty list cannot tell "this
        # creature has no immunities" from "this save predates immunities", and the second
        # would send `from_dict` back to the stat block to re-derive them — undoing an
        # edit made since. Empty is not the same as absent.
        "immunities": list(actor.immunities),
        "resistances": dict(actor.resistances),
        "vulnerabilities": list(actor.vulnerabilities),
        "conditions": [{"key": c.key, "rounds_left": c.rounds_left} for c in actor.conditions],
        "buffs": [{"kind": b.kind, "target": b.target, "amount": b.amount,
                   "source": b.source, "rounds_left": b.rounds_left, "note": b.note}
                  for b in actor.buffs],
        # The one store, whole. The per-mechanism keys above are kept because older
        # code and older saves read them, but they are views: an effect that carries
        # both granted tags and several modifiers — an ability's stance — cannot be
        # said in them, and this key is where it survives a save.
        "active_effects": [e.as_dict() for e in actor.effects],
        "world_entity_id": actor.world_entity_id, "world_people_id": actor.world_people_id,
        "at": actor.at,
        "heritage": actor.heritage, "race": actor.race, "pronouns": actor.pronouns,
        "true_name": actor.true_name, "appearance": actor.appearance,
        "described": bool(actor.described),
        "troop": actor.troop.as_dict() if actor.troop is not None else None,
        "background": actor.background,
        "background_ties": list(actor.background_ties or []),
        "gender": actor.gender,
        "paths": list(actor.paths),
        "flat_skills": actor.flat_skills, "flat_saves": actor.flat_saves,
        "flat_ac": actor.flat_ac, "flat_attack": actor.flat_attack,
        "flat_damage": actor.flat_damage, "flat_initiative": actor.flat_initiative,
        "flat_cmd": actor.flat_cmd, "notes": actor.notes,
        "slots": {k: list(v) for k, v in actor.slots.items()},
        # The mechanical half of worn gear. Saved beside the slots rather than inside
        # them so every save written before this feature still loads: a slot is a name,
        # and a name with no record here is exactly the inert string it always was.
        "worn": {k: dict(v) for k, v in actor.worn.items()},
    }


def _progression(actor: Actor) -> dict:
    from . import leveling

    cid = actor.char_class or ""
    cls = _classes_get(cid)
    return {
        "class": cls.get("name", cid), "level": int(actor.level or 1),
        "summary": cls.get("summary", ""),
        "hit_die": cls.get("hit_die", 8), "bab": cls.get("bab", ""),
        "good_saves": list(cls.get("good_saves") or []),
        "skill_ranks": cls.get("skill_ranks", 2),
        "class_skills": list(cls.get("class_skills") or []),
        "paths_offered": leveling.paths_for(cid),
        # What each branch actually does, as the class file states it. The tab showed
        # four names and a line saying they granted nothing; now it shows the abilities
        # at every Control Blood tier, in the author's own words.
        "path_detail": {n: leveling.path_detail(cid, n)
                        for n in leveling.paths_for(cid)},
        # How far along each branch, and what that makes the scaling abilities worth
        # right now. The sheet's whole proposition is showing where a number came
        # from, and "DR 8 at Control Blood 3" is exactly that.
        "control_blood": leveling.control_blood(actor),
        "unlocks_b": leveling.unlocks_at(cid, 1),
        "path_now": {n: {a: [leveling.resolve_effect(e, actor, n) for e in fx]
                         for a, fx in (leveling.path_detail(cid, n).get("effects")
                                       or {}).items()}
                     for n in actor.paths},
        "paths_taken": list(actor.paths),
        "rows": leveling.preview(cid, actor.level or 1, actor.paths),
        "next": (leveling.gains_at(cid, int(actor.level or 1) + 1)
                 if int(actor.level or 1) < leveling.MAX_LEVEL else None),
    }


def _classes_get(cid: str) -> dict:
    from . import classes as classes_mod

    return classes_mod.get(cid)


def _racial_traits(actor: Actor) -> list[dict]:
    """The race's own line items, from the same table creation builds from.

    One source, so a trait the forge showed when the character was made is the trait
    the sheet shows afterwards. Imported here rather than at module scope because
    `rules.creation` imports this module.
    """
    from . import races as races_mod

    race = races_mod.document(str(actor.race or ""))
    if not race:
        return []
    return [{"name": t, "source": race.get("name", actor.race)}
            for t in race.get("trait_lines") or race.get("traits") or []]


def _race_body(actor: Actor) -> dict:
    from . import races as races_mod

    doc = races_mod.document(str(actor.race or ""))
    if not doc:
        return {}
    return {
        "speeds": races_mod.speeds(doc), "senses": races_mod.senses(doc),
        "natural_weapons": [
            {"name": str(w.get("name") or w.get("key")),
             "damage": (actor.natural_weapon(str(w.get("key"))) or {}).get("damage", ""),
             "type": str(w.get("type") or ""), "count": int(w.get("count", 1) or 1),
             "secondary": bool(w.get("secondary"))}
            for w in doc.get("weapons") or ()],
        "not_yet": list(doc.get("not_yet") or []),
    }


def _class_features(actor: Actor) -> list[str]:
    """Everything the class has granted up to this level, in order."""
    from . import classes as classes_mod

    out: list[str] = []
    for level in range(1, max(1, int(actor.level or 1)) + 1):
        for granted in classes_mod.features_at(actor.char_class or "", level):
            if granted not in out:
                out.append(granted)
    return out


def _castable_summary(actor: Actor) -> list[dict]:
    """The spells this character could cast right now, for the combat panel.

    Prepared casters answer with what is actually in their head and how many copies are
    left; spontaneous casters answer with what they know, since any of it can be cast
    while a slot of the level remains. Either way the engine has the final word — this
    only decides what the Cast button offers.

    Empty for anybody who does not cast, which is the common case and must cost nothing.
    """
    from . import casting

    try:
        data = casting.profile(actor) if hasattr(casting, "profile") else None
    except Exception:                                   # pragma: no cover - guard
        data = None
    book = list(getattr(actor, "spellbook", None) or [])
    prepared = dict(getattr(actor, "prepared", None) or {})
    if not book and not prepared:
        return []

    out: list[dict] = []
    for sid in sorted(set(book) | set(prepared)):
        left = prepared.get(sid)
        if prepared and not left:
            continue          # a prepared caster cannot cast what is not in their head
        try:
            from . import spells as spells_mod

            spell = spells_mod.get(sid)
            name, summary = spell.name, spell.line
        except Exception:
            name, summary = sid, ""
        out.append({"id": sid, "name": name, "summary": summary,
                    "left": left})
    return out


def _satchel_summary(actor: Actor) -> list[dict]:
    """Raw material carried, with real names. The sheet stores ids because that is what
    everything else keys on; a player should never be shown `adder-s-tongue`."""
    from . import ingredients as ing_mod

    out = []
    for iid, n in sorted(actor.inventory.items()):
        try:
            ing = ing_mod.get(iid)
            out.append({"id": iid, "name": ing.name, "count": n, "tier": ing.tier})
        except KeyError:
            out.append({"id": iid, "name": iid.replace("-", " ").title(), "count": n,
                        "tier": "common"})
    return out


def _world_class_summary(actor: Actor) -> list[dict]:
    """What the character has taken up, and how far off the next step is.

    Tolerates a track the build no longer ships: a save naming a homebrew world class the
    user has since removed shows what it can rather than refusing to load the character.
    """
    from . import worldclass

    out = []
    for track_id, p in actor.world_classes.items():
        try:
            track = worldclass.get(track_id)
        except KeyError:
            out.append({"id": track_id, "name": track_id.title(), "level": p.level,
                        "mp": p.mp, "missing": True})
            continue
        level = track.at(p.level)
        out.append({
            "id": track.id, "name": track.name, "level": p.level,
            "mp": p.mp, "to_next": worldclass._remaining(track, p),
            "max_tier": level.max_tier, "methods": track.unlocked_methods(p.level),
            "tools": track.unlocked_tools(p.level),
            "known": len(p.crafted),
        })
    return out


def _pools(raw: dict):
    from .resources import from_dict as pool_from_dict

    return {k: pool_from_dict({**v, "id": v.get("id", k)}) for k, v in raw.items()}


def _stock(raw: dict):
    from .crafting import from_stock_dict

    return {k: from_stock_dict(v) for k, v in raw.items()}


def _progress(track_id: str, v: dict):
    from .worldclass import Progress

    return Progress(
        track=track_id, level=int(v.get("level", 1)), mp=int(v.get("mp", 0)),
        crafted={k: int(n) for k, n in (v.get("crafted") or {}).items()},
        mishaps={k: int(n) for k, n in (v.get("mishaps") or {}).items()},
        milestones=list(v.get("milestones") or []),
    )


def _temp_pools(data: dict) -> list[TempPool]:
    """Saves written before temporary hit points were pooled hold a bare `temp_hp`."""
    if data.get("temp_pools") is not None:
        return [TempPool(amount=int(p.get("amount", 0)), source=p.get("source", ""),
                         rounds_left=p.get("rounds_left"))
                for p in data["temp_pools"] if int(p.get("amount", 0)) > 0]
    if data.get("temp_hp"):
        return [TempPool(int(data["temp_hp"]), data.get("temp_hp_source", ""))]
    return []


def _overrides(raw: dict) -> dict[str, bool]:
    """A misspelled rule is a feature that never happens with nothing saying why, so it
    is caught at load rather than never noticed."""
    unknown = [k for k in raw if k not in ACTOR_RULES]
    if unknown:
        raise IllegalSheet(
            f"no such rule to override: {', '.join(sorted(unknown))}. "
            f"Known rules: {', '.join(sorted(ACTOR_RULES))}"
        )
    return {k: bool(v) for k, v in raw.items()}


# The four effect kinds that are defences. Named once so the migration, the save and
# the law tests all mean the same four things by it.
_DEFENCE_KINDS = ("immunity", "resistance", "vulnerability", "damage_reduction")


def _defences(data: dict) -> tuple[list[str], dict[str, int], list[str]]:
    """Immunity, resistance and vulnerability, from wherever the save put them.

    Two shapes have to load. A creature arriving from the bestiary carries `effects` — the
    same spec list a potion carries, built by `rules/creature_effects.py` out of the
    printed `Immune`/`Resist`/`Weaknesses` lines. A character saved by this app carries the
    three plain fields, because that is what `to_dict` writes.

    Reading both rather than picking one is what lets a homebrew creature state an immunity
    the parse could not, and lets a saved game reload without re-parsing a stat block that
    may have been edited since.
    """
    immunities = list(data.get("immunities") or [])
    resistances = {k: int(v) for k, v in (data.get("resistances") or {}).items()}
    vulnerabilities = list(data.get("vulnerabilities") or [])
    for spec in data.get("effects") or ():
        if not isinstance(spec, dict):
            continue
        target, kind = str(spec.get("target", "")), spec.get("type")
        if kind == "immunity" and target not in immunities:
            immunities.append(target)
        elif kind == "vulnerability" and target not in vulnerabilities:
            vulnerabilities.append(target)
        elif kind == "resistance" and target:
            # The better of the two rather than the last one read, since 1e does not stack
            # resistances against the same energy.
            resistances[target] = max(resistances.get(target, 0),
                                      int(spec.get("amount", 0) or 0))
    return immunities, resistances, vulnerabilities


def _reduction(r) -> Reduction:
    """A stat block writes `DR 5/silver`; a save writes the parts. Both must load, because
    the bestiary is authored by hand and the save is written by code."""
    if isinstance(r, str):
        text = r.strip().lstrip("Dd").lstrip("Rr").strip()
        amount, _, bypass = text.partition("/")
        return Reduction(amount=int(re.sub(r"\D", "", amount) or 0),
                         bypass="" if bypass.strip() in ("-", "—", "") else bypass.strip())
    return Reduction(amount=int(r.get("amount", 0)), bypass=r.get("bypass", ""),
                     source=r.get("source", ""))


def _compulsion(raw: dict):
    from .compulsion import from_dict as compulsion_from_dict

    return compulsion_from_dict(raw)


def from_dict(data: dict, ref: str | None = None) -> Actor:
    immunities, resistances, vulnerabilities = _defences(data)
    a = Actor(
        ref=ref or data.get("ref") or data["name"].lower().replace(" ", "-"),
        name=data["name"],
        kind=data.get("kind", "npc"),
        level=data.get("level", 1),
        char_class=data.get("class"),
        size=data.get("size", "medium"),
        abilities=data.get("abilities", {}),
        ranks={k.lower(): v for k, v in (data.get("ranks") or {}).items()},
        feats=data.get("feats", []),
        armour=data.get("armour", "none"),
        shield=data.get("shield", "none"),
        natural_armour=data.get("natural_armour", 0),
        weapons=data.get("weapons", []),
        equipped=data.get("equipped"),
        hp=data.get("hp", 1),
        nonlethal=int(data.get("nonlethal", 0) or 0),
        speed=int(data.get("speed", 30) or 30),
        held_breath_rounds=int(data.get("held_breath_rounds", 0) or 0),
        drown_failures=int(data.get("drown_failures", 0) or 0),
        swim_check_made=data.get("swim_check_made"),
        awake_minutes=int(data.get("awake_minutes", 0) or 0),
        fed_minutes=int(data.get("fed_minutes", 0) or 0),
        watered_minutes=int(data.get("watered_minutes", 0) or 0),
        thirst_checks=int(data.get("thirst_checks", 0) or 0),
        hunger_checks=int(data.get("hunger_checks", 0) or 0),
        xp=int(data.get("xp", 0) or 0),
        xp_value=int(data.get("xp_value", 0) or 0),
        from_template=str(data.get("from_template", "") or ""),
        pristine={k: int(v) for k, v in (data.get("pristine") or {}).items()
                  if int(v) > 0},
        spellbook=list(data.get("spellbook") or []),
        prepared={k: int(v) for k, v in (data.get("prepared") or {}).items()
                  if int(v) > 0},
        ability_damage={k: int(v) for k, v in (data.get("ability_damage") or {}).items()},
        ability_drain={k: int(v) for k, v in (data.get("ability_drain") or {}).items()},
        hit_dice_per_level=int(data.get("hit_dice_per_level", 1) or 1),
        overrides=_overrides(data.get("overrides") or {}),
        gear={k: Item(name=v.get("name", k), material=v.get("material", ""),
                      hardness=v.get("hardness"), hp=v.get("hp"),
                      hp_max=v.get("hp_max"))
              for k, v in (data.get("gear") or {}).items()},
        world_classes={k: _progress(k, v)
                       for k, v in (data.get("world_classes") or {}).items()},
        stock=_stock(data.get("stock") or {}),
        inventory={k: int(v) for k, v in (data.get("inventory") or {}).items()
                   if int(v) > 0},
        picked_at={str(k): int(v) for k, v in (data.get("picked_at") or {}).items()},
        preserved={str(k): bool(v) for k, v in (data.get("preserved") or {}).items()},
        kit_pending=dict(data.get("kit_pending") or {}),
        goods={str(k): int(v) for k, v in (data.get("goods") or {}).items()
               if int(v) > 0},
        purse={str(k): int(v) for k, v in (data.get("purse") or {}).items()
               if int(v) > 0},
        pools=_pools(data.get("pools") or {}),
        world_entity_id=data.get("world_entity_id"),
        world_people_id=data.get("world_people_id"),
        # Read, not merely written: `from_dict` ignores keys it does not know, so a
        # save that carried `at` would have loaded every actor into no place and the
        # heal for saves that predate the field would have fired on all of them.
        at=str(data.get("at") or ""),
        heritage=data.get("heritage", ""),
        true_name=str(data.get("true_name", "") or ""),
        appearance=str(data.get("appearance", "") or ""),
        described=bool(data.get("described", False)),
        troop=_troops.Troop.from_dict(data.get("troop")),
        background=data.get("background", ""),
        background_ties=list(data.get("background_ties") or []),
        race=data.get("race", "human"),
        paths=[str(p) for p in (data.get("paths") or [])],
        pronouns=data.get("pronouns", "they/them"),
        # Every save written before the field existed still knows the answer, because
        # she/her and he/him each imply one. Nothing else does, and an unrecognised set
        # stays blank rather than being assigned a body by a lookup table.
        gender=str(data.get("gender", "") or "").strip().lower()
        or gender_from_pronouns(data.get("pronouns", "")),
        flat_skills={k.lower(): v for k, v in (data.get("flat_skills") or {}).items()},
        flat_saves=data.get("flat_saves") or {},
        flat_ac=data.get("flat_ac"),
        flat_attack=data.get("flat_attack"),
        flat_damage=data.get("flat_damage"),
        flat_initiative=data.get("flat_initiative"),
        flat_cmd=data.get("flat_cmd"),
        notes=data.get("notes", ""),
        slots={k: list(v) for k, v in (data.get("slots") or {}).items()
               if k in SLOTS},
        worn={str(k).strip().lower(): dict(v)
              for k, v in (data.get("worn") or {}).items() if isinstance(v, dict)},
    )
    if data.get("active_effects") is not None:
        # A save this app wrote: the one store carries everything, and the legacy keys
        # beside it are views of the same facts — loading both would double them.
        from . import activeeffect

        a.effects = [activeeffect.from_dict(e) for e in data["active_effects"]]
    else:
        # An older save, or a hand-written creature: build the store from the
        # per-mechanism keys it does have.
        for c in data.get("conditions", []):
            a.add_condition(c if isinstance(c, str) else c["key"],
                            None if isinstance(c, str) else c.get("rounds_left"))
        for b in data.get("buffs", []):
            a.add_buff(b.get("kind", "save_mod"), b.get("target", ""),
                       b.get("amount", 0), b.get("source", ""),
                       b.get("rounds_left"), b.get("note", ""),
                       b.get("bonus_type", ""))
        for p in _temp_pools(data):
            a.effects.append(a._new_temp_effect(p.amount, p.source, p.rounds_left))
        if data.get("coating"):
            a.coating = dict(data["coating"])
    # The defences, migrated — and AFTER the effects above, never before. `from_dict`
    # rebinds `a.effects` wholesale when the save carries `active_effects`, so anything
    # minted during construction is discarded by that line; the blast-radius review
    # named this as the way the two plausible implementations fail in opposite
    # directions, one losing every legacy save's defences and the other doubling them
    # on every round trip. Idempotent by asking the store first: a save written since
    # this landed already carries them as effects and is left alone; every older one is
    # built from the flat keys, and a bestiary row from its printed spec list.
    # Compulsions, migrated on the same rule and for the same reason: `from_dict`
    # rebinds `a.effects` wholesale, so anything minted during construction is
    # discarded, and asking the store first keeps a reload from doubling them.
    if not any(e.kind == "compulsion" for e in a.effects):
        for raw in (data.get("compulsions") or []):
            got = _compulsion(raw)
            from . import compulsion as compulsion_mod

            compulsion_mod.add(a, got.by, got.penalty, got.rounds_left,
                               got.source, got.why)
    if not any(e.kind in _DEFENCE_KINDS for e in a.effects):
        a.immunities = immunities
        a.resistances = resistances
        a.vulnerabilities = vulnerabilities
        a.reductions = [_reduction(r) for r in (data.get("reductions") or [])]
    # After the effects, never before: a save written while a Constitution buff was
    # standing carries a maximum that already includes it, so the rolled base is the
    # saved total minus whatever Constitution contributes with everything loaded. Do it
    # first and the buff would be counted twice on every reload.
    validate(a)

    # After validate, so an unknown class is reported as an unknown class rather than as
    # whatever apply() happens to do with one.
    from . import classes

    classes.apply(a)
    # And the hit points last of all, because everything the derivation reads has
    # to be settled first. `classes.apply` is what sets `hit_dice_per_level`, and
    # Blood Bending has two — so computing the base before it ran measured
    # Constitution's share against one die per level and then read it back against
    # two. Measured on the user's own saves: five of twelve characters gained hit
    # points on load, Thor 23 -> 37, until this moved below the line that tells the
    # sheet how many dice it has.
    total = int(data.get("hp_max", data.get("hp", 1)) or 1)
    # Which convention the saved total is in. Since stage 8 `set_hp_max` subtracts
    # the feat channel (Toughness) so a printed total round-trips; a save written
    # BEFORE the channel existed holds a total that never included it, and reading
    # it under the new rule silently cost every Toughness holder three hit points —
    # the verifiers measured hp_max 9 / hp_base 5 for a sheet that should read 12 /
    # 8. `to_dict` writes the marker; its absence means the old convention, and the
    # holder finally receives what the feat always promised. Absent is not empty.
    if "hp_channels" not in data:
        total += a._feat_hp()
    a.set_hp_max(total)
    _bind_targets(a)
    return a


def load_pc(path: str | Path) -> Actor:
    with Path(path).open(encoding="utf-8") as fh:
        return from_dict(json.load(fh), ref="pc")



def _bind_targets(actor: Actor) -> None:
    """A bare Weapon Focus on a sheet is bound, once, to the weapon in hand.

    The forge wrote every scoped feat untargeted (`creation.py` collected no weapon),
    and `has_feat` matched a target of None against every weapon, so every forge-built
    Weapon Focus was +1 with everything. Under the documents a bare `$target` feat
    binds nowhere, and a save holding one would silently lose its bonus; so on load
    it is rewritten to the equipped weapon with a note that says so, never dropped.
    """
    from . import feats as feats_mod

    for i, raw in enumerate(list(actor.feats)):
        doc = feats_mod.document(raw)
        if not doc or doc.get("target") or not feats_mod.needs_target(doc):
            continue
        weapon = str(actor.equipped or "").strip().lower()
        if not weapon:
            continue
        actor.feats[i] = f"{doc['name'].lower()} ({weapon})"
        note = (f"[feat '{doc['name']}' had no weapon named; bound to the {weapon} in "
                f"hand on load — write it as '{doc['name']} (<weapon>)' to choose]")
        if note not in (actor.notes or ""):
            actor.notes = (actor.notes + " " + note).strip() if actor.notes else note

def validate(actor: Actor) -> None:
    """Legality checks that must fail loudly at load rather than quietly mid-scene."""
    if actor.is_pc:
        from . import classes

        if actor.char_class not in classes.all_classes():
            raise IllegalSheet(f"{actor.name}: unknown class {actor.char_class!r}")
        cls = classes.get(actor.char_class)
        # Ranks per level: class ranks + Int modifier, minimum 1, plus whatever the
        # race document grants ("ranks +1" on a human's) — asked of the document,
        # never of the name.
        from . import races as races_mod

        per_level = max(1, cls["skill_ranks"] + ability_modifier(actor.abilities.get("int", 10)))
        per_level += races_mod.budget(actor.race, "ranks")
        allowed = per_level * actor.level
        spent = sum(actor.ranks.values())
        if spent > allowed:
            raise IllegalSheet(
                f"{actor.name}: {spent} skill ranks spent, {allowed} available "
                f"({cls['skill_ranks']} class + Int + race, x{actor.level})"
            )
        for skill, rank in actor.ranks.items():
            if skill not in SKILLS:
                raise IllegalSheet(f"{actor.name}: unknown skill {skill!r}")
            if rank > actor.level:
                raise IllegalSheet(
                    f"{actor.name}: {rank} ranks in {skill} exceeds character level "
                    f"{actor.level}"
                )
    from . import feats as feats_mod

    for f in actor.feats:
        # A document means the engine applies something, and the note would lie.
        if feats_mod.document(f):
            continue
        # Not fatal: an unrecognised feat contributes nothing and says so, which is
        # better than silently pretending it applied.
        #
        # Guarded against re-appending, because the campaign save round-trips through
        # here on every load and an unguarded += grows the note without bound.
        note = f"[feat '{f}' is carried as flavour; engine applies nothing]"
        if note not in actor.notes:
            actor.notes += f"\n{note}"
    if actor.armour not in ARMOUR:
        raise IllegalSheet(f"{actor.name}: unknown armour {actor.armour!r}")
    if actor.equipped and actor.equipped.lower() not in WEAPONS:
        raise IllegalSheet(f"{actor.name}: unknown weapon {actor.equipped!r}")
