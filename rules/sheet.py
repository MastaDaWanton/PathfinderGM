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
    ARMOUR, CLASSES, CONDITIONS, FEAT_TARGET_RE, FEATS, NON_PROFICIENT_PENALTY,
    SAVE_ABILITY, SAVES, SHIELDS, SIZES, SKILLS, WEAPONS, ability_modifier, bab_for,
    iterative_attacks, power_attack_terms, save_for,
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

    def cmd(self) -> int:
        if self.flat_cmd is not None:
            return self.flat_cmd
        return (10 + self.bab + self.ability_mod("str") + self.ability_mod("dex")
                + SIZES.get(self.size, SIZES["medium"])["cmb_cmd"])

    def cmb_modifiers(self) -> list[Modifier]:
        mods = [Modifier(self.bab, "BAB"), Modifier(self.ability_mod("str"), "Str")]
        size_mod = SIZES.get(self.size, SIZES["medium"])["cmb_cmd"]
        if size_mod:
            mods.append(Modifier(size_mod, f"{self.size} size"))
        return [m for m in mods if m.value]

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
        remember them mid-scene."""
        changed = []
        if self.hp <= -self.ability_score("con") and not self.has_condition("dead"):
            self.add_condition("dead", source="hit points")
            changed.append("dead")
        elif 0 >= self.hp > -self.ability_score("con") and not self.has_condition("unconscious"):
            self.add_condition("unconscious", source="hit points")
            changed.append("unconscious")
        return changed

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
