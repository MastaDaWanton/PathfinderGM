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
from .dice import Modifier
from .tables import (
    ABILITIES, ABILITY_FULL, ABILITY_NAMES, ARMOUR, ARMOUR_SPEED,
    CLASSES, CONDITIONS, FEAT_TARGET_RE, FEATS,
    MANEUVERS, NON_PROFICIENT_PENALTY, SAVE_ABILITY, SAVES, SHIELDS, SIZES, SKILLS,
    SLOT_ORDER_LEFT, SLOT_ORDER_RIGHT, SLOT_RULES_LIMIT, SLOTS,
    WEAPONS, ENERGY_VS_OBJECTS_HALVED, MATERIALS, ability_modifier, bab_for,
    is_physical, iterative_attacks, material_for, normalise_damage_type,
    power_attack_terms, save_for,
)


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

    hp_max: int = 1
    hp: int = 1
    # Temporary hit points sit *on top of* hp_max rather than inside it, are spent before
    # real hit points, and are not restored by healing.
    #
    # A list rather than a number even though 1e keeps only the best, because the pools
    # expire independently: rage temporary hit points end with the rage while a ward's
    # last the minute. One number could hold the total or the duration, never both.
    temp_pools: list["TempPool"] = field(default_factory=list)
    # Non-lethal damage, tracked apart from hit points because 1e tracks it apart: it
    # accumulates on its own, it staggers you when it reaches your current hit points and
    # drops you when it passes them, and it heals on a different clock.
    #
    # Blood Bending is the reason this could not wait. Its whole economy is paying for
    # abilities in self-inflicted non-lethal damage, and without a separate pool that
    # payment was indistinguishable from being stabbed.
    nonlethal: int = 0
    # Base land speed in feet, before armour. 30 is a human's; Small races and dwarves
    # have 20. Nothing needed this until the grid arrived — zones have no distance — so a
    # sheet written before this defaults rather than failing to load.
    speed: int = 30
    reductions: list[Reduction] = field(default_factory=list)
    # The other three defences a stat block prints, which until now had nowhere to live.
    # `reductions` above has been read since the beginning; `Immune cold` and `Resist
    # fire 10` were dropped when a bestiary row became an Actor, so a frost giant took
    # full damage from cold and a devil took full damage from fire.
    #
    # Kept as plain data next to `reductions` rather than as effect specs, for the same
    # reason `reductions` is: `take_damage` should not be interpreting a schema in the
    # middle of resolving a hit. `rules/creature_effects.py` does the interpreting once,
    # at load.
    #
    # Immunity is by name rather than by damage type, because most immunities are not
    # damage types — "undead traits", "paralysis", "mind-affecting effects". `immune_to`
    # answers the damage question and the rest are there for the save and condition paths
    # to consult when they learn to.
    immunities: list[str] = field(default_factory=list)
    resistances: dict[str, int] = field(default_factory=dict)
    vulnerabilities: list[str] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    # Who this creature is being pulled towards, and what defying them costs. Not a
    # condition: a condition is a state the creature is in, while a compulsion is a
    # relationship to a *particular other creature*, and it has to be able to name them.
    compulsions: list["Compulsion"] = field(default_factory=list)
    # Spells this caster can reach: the wizard's book, or nothing for a cleric whose list
    # is their whole class list. Ids, not names — two spells share a name often enough.
    # A harmful preparation waiting on a blade. One hit and it is gone — a 1e poison is
    # a dose, not an enchantment. On the actor rather than the weapon entry because
    # `weapons` is a list of plain strings, and the alternative was giving every torch
    # and length of rope a coating field.
    coating: dict = field(default_factory=dict)
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

    # World Bible provenance. The rules race and the world's people are different things:
    # Zhilakai is not a PF1e race, so the sheet carries both and neither pretends to be
    # the other.
    world_entity_id: str | None = None
    world_people_id: str | None = None
    heritage: str = ""
    # Which branch of the class this character follows. A list because a class
    # may let you take more than one — Blood Bending declares four and the
    # player may follow one or several. Empty for every class that has none.
    paths: list[str] = field(default_factory=list)
    race: str = "human"
    # Stated, never guessed. The model called Kesst "him" in one sentence and "her" in
    # the next because nothing on the sheet said, so it invented one each time.
    pronouns: str = "they/them"

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
        """
        score = self.abilities.get(ab, 10)
        for c in self.conditions:
            score += c.data.get("ability_penalty", {}).get(ab, 0)
        score -= self.ability_damage.get(ab, 0)
        score -= self.ability_drain.get(ab, 0)
        return max(0, score)

    def base_ability_score(self, ab: str) -> int:
        """Before damage and drain — what it heals back towards."""
        return self.abilities.get(ab, 10)

    def ability_mod(self, ab: str) -> int:
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
        before_mod = self.ability_mod("con")

        book = self.ability_drain if drain else self.ability_damage
        book[ab] = book.get(ab, 0) + amount

        hp_change = 0
        if ab == "con":
            hp_change = self._apply_con_change(before_mod)
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
        before_mod = self.ability_mod("con")
        self.ability_damage[ab] = have - back
        if not self.ability_damage[ab]:
            del self.ability_damage[ab]
        if ab == "con":
            self._apply_con_change(before_mod)
        return back

    def _apply_con_change(self, before_mod: int) -> int:
        """Move hit points to match a changed Constitution modifier.

        1e: hit points change by your Hit Dice times the change in modifier. Current hit
        points move with the maximum, so a character at full stays at full and a wounded
        one keeps their wound.
        """
        delta = (self.ability_mod("con") - before_mod) * max(1, self.hit_dice)
        if not delta:
            return 0
        self.hp_max = max(1, self.hp_max + delta)
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
        return all(c.data.get("can_act", True) for c in self.conditions)

    def blocking_condition(self) -> str | None:
        for c in self.conditions:
            if not c.data.get("can_act", True):
                return c.name
        return None

    def has_condition(self, key: str) -> bool:
        return any(c.key == key for c in self.conditions)

    # --- condition contributions --------------------------------------------------

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
            for feat in self.feats:
                bonus = FEATS.get(self._feat_name(feat), {}).get("skills", {}).get(skill)
                if bonus:
                    mods.append(Modifier(bonus, FEATS[self._feat_name(feat)]["name"]))

        if skill == "stealth":
            size_mod = SIZES.get(self.size, SIZES["medium"])["stealth"]
            if size_mod:
                mods.append(Modifier(size_mod, f"{self.size} size"))

        mods.extend(self._condition_mods("skills"))
        return mods

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
            for feat in self.feats:
                bonus = FEATS.get(self._feat_name(feat), {}).get("saves", {}).get(save)
                if bonus:
                    mods.append(Modifier(bonus, FEATS[self._feat_name(feat)]["name"]))

        mods.extend(self._condition_mods("saves"))
        return mods

    # --- initiative -------------------------------------------------------------------

    def initiative_modifiers(self) -> list[Modifier]:
        mods: list[Modifier] = []
        if self.flat_initiative is not None:
            mods.append(Modifier(self.flat_initiative, "Initiative"))
        else:
            am = self.ability_mod("dex")
            if am:
                mods.append(Modifier(am, "Dex"))
            for feat in self.feats:
                bonus = FEATS.get(self._feat_name(feat), {}).get("initiative")
                if bonus:
                    mods.append(Modifier(bonus, FEATS[self._feat_name(feat)]["name"]))
        return mods

    # --- attack and damage --------------------------------------------------------------

    def weapon(self, key: str | None = None) -> dict:
        """The weapon's statistics.

        Goes through `rules.weapons` rather than reading `tables.WEAPONS` directly: the
        table holds eleven, the content file holds 456, and a player reaching for a glaive
        used to get `KeyError: no such weapon`.
        """
        from . import weapons as weapons_mod

        return weapons_mod.get(key or self.equipped or "unarmed")

    def _uses_finesse(self, weapon: dict) -> bool:
        return (
            weapon.get("finessable", False)
            and any(self._feat_name(f) == "weapon finesse" for f in self.feats)
            and self.ability_mod("dex") > self.ability_mod("str")
        )

    @staticmethod
    def _feat_name(feat: str) -> str:
        """"Weapon Focus (rapier)" -> "weapon focus"."""
        m = re.match(FEAT_TARGET_RE, feat.strip(), re.IGNORECASE)
        return (m.group("feat") if m else feat).strip().lower()

    @staticmethod
    def _feat_target(feat: str) -> str | None:
        m = re.match(FEAT_TARGET_RE, feat.strip(), re.IGNORECASE)
        return m.group("target").strip().lower() if m else None

    def has_feat(self, name: str, target: str | None = None) -> bool:
        name = name.strip().lower()
        for f in self.feats:
            if self._feat_name(f) != name:
                continue
            if target is None or self._feat_target(f) in (None, target.strip().lower()):
                return True
        return False

    def is_proficient(self, weapon_key: str | None = None) -> bool:
        """Proficiency comes from the class, or from a Martial/Simple Weapon Proficiency
        feat, or from the weapon being named specifically."""
        from . import weapons as weapons_mod

        key = (weapon_key or self.equipped or "unarmed").strip().lower()
        w = weapons_mod.all_weapons().get(key, {})
        if self.flat_attack is not None:
            return True          # an NPC stat block's attack bonus already accounts for it
        granted = {p.lower() for p in self.class_data.get("proficiencies", ())}
        for f in self.feats:
            if self._feat_name(f).endswith("weapon proficiency"):
                t = self._feat_target(f)
                if t:
                    granted.add(t)
                granted.add(self._feat_name(f).split()[0])
        return key in granted or w.get("prof") in granted

    def power_attack_terms(self, weapon_key: str | None = None) -> tuple[int, int]:
        w = self.weapon(weapon_key)
        return power_attack_terms(self.bab, w.get("hands", 1) == 2)

    def can_power_attack(self) -> str | None:
        """None if legal, otherwise why not. PF1e requires the feat, BAB +1 and Str 13."""
        if not self.has_feat("power attack"):
            return f"{self.name} does not have Power Attack"
        if self.bab < 1:
            return f"{self.name} has BAB +{self.bab}; Power Attack needs +1"
        if self.ability_score("str") < 13:
            return f"{self.name} has Str {self.ability_score('str')}; Power Attack needs 13"
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
            elif self._uses_finesse(w):
                ab, label = "dex", "Dex (Finesse)"
            else:
                ab, label = "str", "Str"
            am = self.ability_mod(ab)
            if am:
                mods.append(Modifier(am, label))

            if not self.is_proficient(key):
                mods.append(Modifier(NON_PROFICIENT_PENALTY,
                                     f"not proficient with {w['name']}"))
            if self.has_feat("weapon focus", key):
                mods.append(Modifier(1, "Weapon Focus"))

            # Size only when the number was derived. A stat block's printed attack bonus
            # already includes the creature's size, and adding it again gave a small
            # NPC a free +1 on every swing.
            size_mod = SIZES.get(self.size, SIZES["medium"])["attack_ac"]
            if size_mod:
                mods.append(Modifier(size_mod, f"{self.size} size"))

        if iteration:
            mods.append(Modifier(-5 * iteration, f"iterative #{iteration + 1}"))

        if power_attack:
            penalty, _ = self.power_attack_terms(key)
            mods.append(Modifier(penalty, "Power Attack"))

        mods.extend(self._condition_mods("attack"))
        if w["category"] == "melee":
            mods.extend(self._condition_mods("melee_attack"))
        return mods

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
        if self.has_feat("weapon specialization", key):
            mods.append(Modifier(2, "Weapon Specialization"))
        if power_attack:
            _, bonus = self.power_attack_terms(key)
            mods.append(Modifier(bonus, "Power Attack"))
        mods.extend(self._condition_mods("damage"))
        return mods

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
            if armour["ac"]:
                mods.append(Modifier(armour["ac"], armour["name"]))
            if shield["ac"]:
                mods.append(Modifier(shield["ac"], shield["name"]))
            if self.natural_armour:
                mods.append(Modifier(self.natural_armour, "natural armour"))

            loses_dex = flat_footed or any(
                c.data.get("lose_dex_to_ac") for c in self.conditions
            )
            if not loses_dex:
                dex = min(self.ability_mod("dex"), armour["max_dex"])
                if dex:
                    mods.append(Modifier(dex, "Dex"))
            for feat in self.feats:
                bonus = FEATS.get(self._feat_name(feat), {}).get("ac")
                if bonus:
                    mods.append(Modifier(bonus, FEATS[self._feat_name(feat)]["name"]))

            # As with attack: a printed AC already accounts for size.
            size_mod = SIZES.get(self.size, SIZES["medium"])["attack_ac"]
            if size_mod:
                mods.append(Modifier(size_mod, f"{self.size} size"))

        mods.extend(self._condition_mods("ac"))
        mods.extend(self._condition_mods(f"ac_{against}"))
        return mods

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

    def cmb_modifiers(self, maneuver: str | None = None) -> list[Modifier]:
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
            if maneuver and self.has_feat(f"improved {maneuver}"):
                mods.append(Modifier(2, f"Improved {maneuver.title()}"))
            if maneuver and self.has_feat(f"greater {maneuver}"):
                mods.append(Modifier(2, f"Greater {maneuver.title()}"))

        mods.extend(self._condition_mods("attack"))
        return [m for m in mods if m.value]

    def cmd_modifiers(self, flat_footed: bool = False) -> list[Modifier]:
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
        return [m for m in mods if m.value]

    def cmd(self, flat_footed: bool = False) -> int:
        return sum(m.value for m in self.cmd_modifiers(flat_footed))

    # --- state ------------------------------------------------------------------------

    # --- temporary hit points ---------------------------------------------------------

    @property
    def temp_hp(self) -> int:
        return sum(p.amount for p in self.temp_pools)

    @property
    def temp_hp_source(self) -> str:
        return ", ".join(p.source for p in self.temp_pools if p.source)

    def allows(self, rule: str) -> bool:
        if rule not in ACTOR_RULES:
            raise KeyError(f"no such rule {rule!r}")
        return bool(self.overrides.get(rule, False))

    def gain_temp_hp(self, amount: int, source: str = "",
                     rounds: int | None = None) -> dict:
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
        existing = next((p for p in self.temp_pools if p.source == source), None)

        if houserules.magic_stacking() and not self.allows("temp_hp.stacks"):
            if existing:
                existing.amount, existing.rounds_left = amount, rounds
                return {"temp_hp": self.temp_hp, "refreshed": True, "source": source,
                        "stacked": True}
            self.temp_pools.append(TempPool(amount, source, rounds))
            return {"temp_hp": self.temp_hp, "added": amount, "source": source,
                    "stacked": True}

        if self.allows("temp_hp.stacks"):
            if existing:
                existing.amount += amount
                existing.rounds_left = rounds
            else:
                self.temp_pools.append(TempPool(amount, source, rounds))
            return {"temp_hp": self.temp_hp, "added": amount, "source": source,
                    "stacked": True}

        if existing:
            existing.amount, existing.rounds_left = amount, rounds
            self.temp_pools = [existing]
            return {"temp_hp": amount, "refreshed": True, "source": source}

        if amount > self.temp_hp:
            was = self.temp_hp
            self.temp_pools = [TempPool(amount, source, rounds)]
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
        order = sorted(self.temp_pools,
                       key=lambda p: (p.rounds_left is None, p.rounds_left or 0))
        for pool in order:
            if spent >= amount:
                break
            take = min(pool.amount, amount - spent)
            pool.amount -= take
            spent += take
        self.temp_pools = [p for p in self.temp_pools if p.amount > 0]
        return spent

    def clear_temp_hp(self, source: str | None = None) -> int:
        """Drop temporary hit points — all of them, or one source's when a buff ends."""
        if source is None:
            gone, self.temp_pools = self.temp_hp, []
            return gone
        gone = sum(p.amount for p in self.temp_pools if p.source == source)
        self.temp_pools = [p for p in self.temp_pools if p.source != source]
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
        return self.hp - before

    # --- immunity, resistance and vulnerability ------------------------------------------

    def immune_to(self, dtype: str) -> bool:
        """Whether damage of this type simply does not land.

        Matched on the normalised damage type rather than the printed word, so `Immune
        electricity` stops a shock and `Immune undead traits` — which names a bundle of
        rules, not a damage type — stops nothing here and waits for the save path.
        """
        want = normalise_damage_type(dtype)
        return any(normalise_damage_type(t) == want for t in self.immunities)

    def resistance(self, dtype: str) -> int:
        """Points of this energy shrugged off. 0 when none applies.

        1e does not stack two resistances against the same energy — the better one
        applies — and nothing in the data produces two, but `max` says so rather than
        leaving it to chance.
        """
        want = normalise_damage_type(dtype)
        return max((v for k, v in self.resistances.items()
                    if normalise_damage_type(k) == want), default=0)

    def vulnerable_to(self, dtype: str) -> bool:
        want = normalise_damage_type(dtype)
        return any(normalise_damage_type(t) == want for t in self.vulnerabilities)

    # --- damage reduction -------------------------------------------------------------

    def damage_reduction(self, dtype: str = "untyped",
                         traits: tuple[str, ...] = ()) -> Reduction | None:
        """The one DR that applies to this attack, or None.

        1e is specific on both counts, and both are easy to get wrong in the generous
        direction: DR does not touch energy damage, and when a creature has several kinds
        of DR **only the best applicable one applies** — they do not add up.
        """
        if not is_physical(dtype):
            return None
        usable = [r for r in self.reductions if r.amount > 0 and not r.bypassed_by(traits)]
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

        dr = self.damage_reduction(dtype, traits)
        # DR reduces to zero, never below: it cannot heal you.
        reduced = min(after_type, dr.amount) if dr else 0
        after_dr = after_type - reduced

        absorbed = self._spend_temp_hp(min(self.temp_hp, after_dr))
        taken = after_dr - absorbed
        # Non-lethal still spends temporary hit points first — they are hit points — but
        # what gets through goes to its own pool rather than off the character's total.
        if lethality == "nonlethal":
            self.nonlethal += taken
        else:
            self.hp -= taken
        return {
            "rolled": rolled, "type": normalise_damage_type(dtype),
            # Reported even when they did nothing, because the visible bookkeeping is the
            # point: "20 fire, half again for vulnerability, 30" has to be readable back.
            "immune": immune, "vulnerable": vulnerable, "resisted": resisted,
            "reduced": reduced, "reduced_by": dr.label if dr and reduced else "",
            "absorbed": absorbed, "taken": taken, "lethality": lethality,
            "hp": self.hp, "hp_max": self.hp_max, "temp_hp": self.temp_hp,
            "nonlethal": self.nonlethal,
            "nonlethal_threshold": self.nonlethal_threshold,
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
        key = key.strip().lower()
        existing = next((c for c in self.conditions if c.key == key), None)
        if existing:
            # Same condition twice does not stack in 1e; the longer duration wins.
            if rounds is not None and (existing.rounds_left is None or rounds > existing.rounds_left):
                existing.rounds_left = rounds
            return existing
        c = Condition(key=key, rounds_left=rounds, source=source)
        self.conditions.append(c)
        return c

    def remove_condition(self, key: str) -> None:
        self.conditions = [c for c in self.conditions if c.key != key.strip().lower()]

    def tick_conditions(self, rounds: int = 1) -> list[str]:
        """Expire timed conditions and temporary hit points. Returns what ended.

        Temporary hit points tick here too because they expire on the same clock, and a
        ward that outlives its minute is a character walking around with defences the
        rules ended several scenes ago.
        """
        ended = []
        for c in list(self.conditions):
            if c.rounds_left is None:
                continue
            c.rounds_left -= rounds
            if c.rounds_left <= 0:
                ended.append(c.name)
                self.conditions.remove(c)
        for p in list(self.temp_pools):
            if p.rounds_left is None:
                continue
            p.rounds_left -= rounds
            if p.rounds_left <= 0:
                ended.append(f"{p.source or 'temporary hit points'} ({p.amount} temp)")
                self.temp_pools.remove(p)
        return ended

    def apply_hp_state(self) -> list[str]:
        """1e's death and unconsciousness thresholds, applied by code so nobody has to
        remember them mid-scene.

        Below 0 and above -Con you are unconscious *and dying*: losing a hit point each
        round until you stabilise or die. That last part was missing, so a downed
        character simply lay there indefinitely and the fight quietly ended — which is
        not what the rules say and not what a player would expect to happen to them.
        """
        changed = []
        con = self.ability_score("con")
        if self.hp <= -con and not self.has_condition("dead"):
            for gone in ("dying", "stable", "unconscious"):
                self.remove_condition(gone)
            self.add_condition("dead", source="hit points")
            changed.append("dead")
        elif self.hp < 0 and not self.has_condition("dead"):
            if not self.has_condition("unconscious"):
                self.add_condition("unconscious", source="hit points")
                changed.append("unconscious")
            # Stabilising once keeps you stable; fresh damage starts it again.
            if not self.has_condition("stable") and not self.has_condition("dying"):
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

        woke = False
        for gone in ("unconscious", "stable", "disabled", "dying"):
            if self.has_condition(gone) and self.hp > 0:
                self.remove_condition(gone)
                woke = True
        # You stand up in the morning. Waking still prone, shaken and entangled from a
        # fight the night before is the sort of stale state that quietly poisons every
        # roll for the rest of the campaign.
        for over in ("prone", "flat-footed", "shaken", "frightened", "panicked",
                     "dazzled", "entangled", "grappled", "pinned", "staggered",
                     "sickened", "nauseated", "dazed", "cowering", "fascinated"):
            self.remove_condition(over)
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

    def summary(self) -> dict:
        out = {
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
            "satchel": _satchel_summary(self),
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
            out["feats"] = [f if self._feat_target(f) else FEATS.get(self._feat_name(f), {}).get("name", f)
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
        known = FEATS.get(base)
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

        if known:
            effect = _feat_effect_text(known)
        elif entry and entry.benefit:
            effect = entry.benefit
        else:
            effect = "carried as flavour — the engine applies nothing"

        name = (known or {}).get("name") or (entry.name if entry else f)
        feats.append({
            "name": name + (f" ({target})" if target else ""),
            "applied": known is not None,
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

    return {
        "identity": {
            "name": actor.name,
            "class": f"{cls.get('name', '')} {actor.level}".strip(),
            "race": actor.race,
            "heritage": actor.heritage,
            "pronouns": actor.pronouns,
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
            "ac_touch": {"total": actor.ac() - armour["ac"] - shield["ac"]
                                  - actor.natural_armour,
                         "terms": [{"value": actor.ac() - armour["ac"] - shield["ac"]
                                             - actor.natural_armour,
                                    "source": "touch AC (no armour, shield or natural)"}]},
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
        },
        # None rather than an empty structure for a fighter, so the page can tell "does
        # not cast" from "casts nothing today" — they look identical and are not.
        "spells": _spell_sheet(actor),
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


def _feat_effect_text(feat: dict) -> str:
    bits = []
    if feat.get("finesse"):
        bits.append("Dex in place of Str on attack rolls with finessable weapons")
    for label, key in (("skills", "skills"), ("saves", "saves")):
        for what, v in (feat.get(key) or {}).items():
            bits.append(f"{v:+d} {what}")
    for key, label in (("initiative", "initiative"), ("ac", "AC"),
                       ("weapon_attack", "attack with the chosen weapon"),
                       ("weapon_damage", "damage with the chosen weapon")):
        if feat.get(key):
            bits.append(f"{feat[key]:+d} {label}")
    if feat.get("power_attack"):
        bits.append("trade attack bonus for damage, scaling with BAB")
    if feat.get("hp_bonus"):
        bits.append("bonus hit points")
    return "; ".join(bits) or "no mechanical effect recorded"


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
        "nonlethal": actor.nonlethal, "speed": actor.speed,
        "compulsions": [c.as_dict() for c in actor.compulsions],
        "coating": dict(actor.coating),
        "awake_minutes": actor.awake_minutes, "fed_minutes": actor.fed_minutes,
        "watered_minutes": actor.watered_minutes,
        "thirst_checks": actor.thirst_checks, "hunger_checks": actor.hunger_checks,
        "pristine": {k: int(v) for k, v in actor.pristine.items() if int(v) > 0},
        "picked_at": dict(actor.picked_at),
        "preserved": {k: bool(v) for k, v in actor.preserved.items() if v},
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
        "world_entity_id": actor.world_entity_id, "world_people_id": actor.world_people_id,
        "heritage": actor.heritage, "race": actor.race, "pronouns": actor.pronouns,
        "paths": list(actor.paths),
        "flat_skills": actor.flat_skills, "flat_saves": actor.flat_saves,
        "flat_ac": actor.flat_ac, "flat_attack": actor.flat_attack,
        "flat_damage": actor.flat_damage, "flat_initiative": actor.flat_initiative,
        "flat_cmd": actor.flat_cmd, "notes": actor.notes,
        "slots": {k: list(v) for k, v in actor.slots.items()},
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
    from .creation import RACES

    race = RACES.get(str(actor.race or "").strip().lower())
    if not race:
        return []
    return [{"name": t, "source": race.get("name", actor.race)}
            for t in race.get("traits", [])]


def _class_features(actor: Actor) -> list[str]:
    """Everything the class has granted up to this level, in order."""
    from . import classes as classes_mod

    out: list[str] = []
    for level in range(1, max(1, int(actor.level or 1)) + 1):
        for granted in classes_mod.features_at(actor.char_class or "", level):
            if granted not in out:
                out.append(granted)
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
        hp_max=data.get("hp_max", data.get("hp", 1)),
        hp=data.get("hp", 1),
        nonlethal=int(data.get("nonlethal", 0) or 0),
        speed=int(data.get("speed", 30) or 30),
        compulsions=[_compulsion(c) for c in (data.get("compulsions") or [])],
        coating=dict(data.get("coating") or {}),
        awake_minutes=int(data.get("awake_minutes", 0) or 0),
        fed_minutes=int(data.get("fed_minutes", 0) or 0),
        watered_minutes=int(data.get("watered_minutes", 0) or 0),
        thirst_checks=int(data.get("thirst_checks", 0) or 0),
        hunger_checks=int(data.get("hunger_checks", 0) or 0),
        pristine={k: int(v) for k, v in (data.get("pristine") or {}).items()
                  if int(v) > 0},
        spellbook=list(data.get("spellbook") or []),
        prepared={k: int(v) for k, v in (data.get("prepared") or {}).items()
                  if int(v) > 0},
        temp_pools=_temp_pools(data),
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
        goods={str(k): int(v) for k, v in (data.get("goods") or {}).items()
               if int(v) > 0},
        purse={str(k): int(v) for k, v in (data.get("purse") or {}).items()
               if int(v) > 0},
        pools=_pools(data.get("pools") or {}),
        reductions=[_reduction(r) for r in (data.get("reductions") or [])],
        immunities=immunities,
        resistances=resistances,
        vulnerabilities=vulnerabilities,
        world_entity_id=data.get("world_entity_id"),
        world_people_id=data.get("world_people_id"),
        heritage=data.get("heritage", ""),
        race=data.get("race", "human"),
        paths=[str(p) for p in (data.get("paths") or [])],
        pronouns=data.get("pronouns", "they/them"),
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
    )
    for c in data.get("conditions", []):
        a.add_condition(c if isinstance(c, str) else c["key"],
                        None if isinstance(c, str) else c.get("rounds_left"))
    validate(a)

    # After validate, so an unknown class is reported as an unknown class rather than as
    # whatever apply() happens to do with one.
    from . import classes

    classes.apply(a)
    return a


def load_pc(path: str | Path) -> Actor:
    with Path(path).open(encoding="utf-8") as fh:
        return from_dict(json.load(fh), ref="pc")


def validate(actor: Actor) -> None:
    """Legality checks that must fail loudly at load rather than quietly mid-scene."""
    if actor.is_pc:
        from . import classes

        if actor.char_class not in classes.all_classes():
            raise IllegalSheet(f"{actor.name}: unknown class {actor.char_class!r}")
        cls = classes.get(actor.char_class)
        # Ranks per level: class ranks + Int modifier, minimum 1, plus 1/level for humans.
        per_level = max(1, cls["skill_ranks"] + ability_modifier(actor.abilities.get("int", 10)))
        if actor.race.lower() == "human":
            per_level += 1
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
    for f in actor.feats:
        if Actor._feat_name(f) in FEATS:
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
