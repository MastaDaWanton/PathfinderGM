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

from .dice import Modifier
from .tables import (
    ABILITIES, ABILITY_NAMES, ARMOUR, CLASSES, CONDITIONS, FEAT_TARGET_RE, FEATS,
    MANEUVERS, NON_PROFICIENT_PENALTY, SAVE_ABILITY, SAVES, SHIELDS, SIZES, SKILLS,
    SLOT_ORDER_LEFT, SLOT_ORDER_RIGHT, SLOT_RULES_LIMIT, SLOTS,
    WEAPONS, ability_modifier, bab_for, iterative_attacks, power_attack_terms, save_for,
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


@dataclass
class Actor:
    ref: str
    name: str
    kind: str = "npc"                       # "pc" or "npc"
    level: int = 1
    char_class: str | None = None
    size: str = "medium"

    abilities: dict[str, int] = field(default_factory=dict)
    ranks: dict[str, int] = field(default_factory=dict)
    feats: list[str] = field(default_factory=list)

    armour: str = "none"
    shield: str = "none"
    natural_armour: int = 0
    weapons: list[str] = field(default_factory=list)
    equipped: str | None = None

    hp_max: int = 1
    hp: int = 1
    conditions: list[Condition] = field(default_factory=list)

    # World Bible provenance. The rules race and the world's people are different things:
    # Zhilakai is not a PF1e race, so the sheet carries both and neither pretends to be
    # the other.
    world_entity_id: str | None = None
    world_people_id: str | None = None
    heritage: str = ""
    race: str = "human"

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
        return CLASSES.get(self.char_class or "", {})

    def ability_score(self, ab: str) -> int:
        score = self.abilities.get(ab, 10)
        for c in self.conditions:
            score += c.data.get("ability_penalty", {}).get(ab, 0)
        return score

    def ability_mod(self, ab: str) -> int:
        return ability_modifier(self.ability_score(ab))

    @property
    def bab(self) -> int:
        if not self.class_data:
            return self.flat_attack or 0
        return bab_for(self.class_data["bab"], self.level)

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
            good = save in self.class_data.get("good_saves", ())
            base = save_for(good, self.level)
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
        key = (key or self.equipped or "unarmed").strip().lower()
        if key not in WEAPONS:
            raise KeyError(f"no such weapon {key!r}")
        return WEAPONS[key]

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
        key = (weapon_key or self.equipped or "unarmed").strip().lower()
        w = WEAPONS.get(key, {})
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

    def take_damage(self, amount: int) -> int:
        self.hp -= amount
        return self.hp

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
        """Expire timed conditions. Returns what ended, so it can be narrated."""
        ended = []
        for c in list(self.conditions):
            if c.rounds_left is None:
                continue
            c.rounds_left -= rounds
            if c.rounds_left <= 0:
                ended.append(c.name)
                self.conditions.remove(c)
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
        return changed

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
            "ac": self.ac(),
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

    attacks = []
    for key in dict.fromkeys(w.lower() for w in weapons if w):
        if key not in WEAPONS:
            continue
        w = WEAPONS[key]
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

    feats = []
    for f in actor.feats:
        base = Actor._feat_name(f)
        known = FEATS.get(base)
        feats.append({
            "name": known["name"] + (f" ({Actor._feat_target(f)})"
                                     if Actor._feat_target(f) else "") if known else f,
            "applied": known is not None,
            "effect": _feat_effect_text(known) if known else
                      "carried as flavour — the engine applies nothing",
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
            "size": actor.size,
            "world_people_id": actor.world_people_id,
            "world_entity_id": actor.world_entity_id,
        },
        "abilities": [
            {"key": a, "name": ABILITY_NAMES[a], "score": actor.ability_score(a),
             "modifier": actor.ability_mod(a),
             "base": actor.abilities.get(a, 10)}
            for a in ABILITIES
        ],
        "defense": {
            "hp": {"current": actor.hp, "max": actor.hp_max},
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
            "weapons": [WEAPONS[w.lower()]["name"] for w in weapons
                        if w and w.lower() in WEAPONS],
            "slots": body_slots(actor),
        },
        "background": {
            "heritage": actor.heritage,
            "notes": actor.notes.strip(),
        },
    }


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
        "conditions": [{"key": c.key, "rounds_left": c.rounds_left} for c in actor.conditions],
        "world_entity_id": actor.world_entity_id, "world_people_id": actor.world_people_id,
        "heritage": actor.heritage, "race": actor.race,
        "flat_skills": actor.flat_skills, "flat_saves": actor.flat_saves,
        "flat_ac": actor.flat_ac, "flat_attack": actor.flat_attack,
        "flat_damage": actor.flat_damage, "flat_initiative": actor.flat_initiative,
        "flat_cmd": actor.flat_cmd, "notes": actor.notes,
        "slots": {k: list(v) for k, v in actor.slots.items()},
    }


def from_dict(data: dict, ref: str | None = None) -> Actor:
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
        world_entity_id=data.get("world_entity_id"),
        world_people_id=data.get("world_people_id"),
        heritage=data.get("heritage", ""),
        race=data.get("race", "human"),
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
    return a


def load_pc(path: str | Path) -> Actor:
    with Path(path).open(encoding="utf-8") as fh:
        return from_dict(json.load(fh), ref="pc")


def validate(actor: Actor) -> None:
    """Legality checks that must fail loudly at load rather than quietly mid-scene."""
    if actor.is_pc:
        if actor.char_class not in CLASSES:
            raise IllegalSheet(f"{actor.name}: unknown class {actor.char_class!r}")
        cls = CLASSES[actor.char_class]
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
