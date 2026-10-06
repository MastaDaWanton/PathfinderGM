"""Dice.

Every roll in the app comes through here, including the ones the player makes on the
popup — the popup is an input device, not a second source of randomness. One code path
means one place to seed for tests and one place to log.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

DICE_RE = re.compile(r"^\s*(\d*)d(\d+)\s*(?:([+-])\s*(\d+))?\s*$", re.IGNORECASE)


class BadDice(ValueError):
    pass


@dataclass(frozen=True)
class Modifier:
    """One term of a total, named.

    The name is not decoration. Itemised modifiers are the whole point of offloading 1e
    bookkeeping: a wrong total has to be traceable to the term that produced it, and a
    test has to be able to assert on the terms rather than the sum.

    `type` is 1e's bonus type — deflection, enhancement, morale — and "" for the
    untyped kind. It is what `stack` reads: two deflection bonuses are not a sum, they
    are the better one, and the type is how the aggregator knows.
    """
    value: int
    source: str
    type: str = ""

    def as_dict(self) -> dict:
        d = {"value": self.value, "source": self.source}
        if self.type:
            d["type"] = self.type
        return d


# The bonus types that DO stack with themselves. 1e names exactly two — dodge and
# circumstance — and untyped bonuses stack because there is no type to collide on.
# This is deliberately not GAS's additive-then-multiplicative order: 1e has no
# multiplicative channel, and same-typed-takes-best is the better rule for this game
# (docs/states-effects-tells.md, "what was deliberately not taken").
_SELF_STACKING = {"", "untyped", "dodge", "circumstance"}


def _house_stacking() -> bool:
    """The table's `magic_stacking` switch (rules/houserules.py), read when a collision
    needs it. A settings read that fails — no Django settings in a bare script, a
    half-written file — is the book, which is `houserules.active`'s own fallback."""
    try:
        from . import houserules

        return bool(houserules.magic_stacking())
    except Exception:
        return False


def stack(mods: list[Modifier], *, magic_stacking: bool | None = None) -> list[Modifier]:
    """1e's stacking rule, applied to a finished modifier list.

    Two bonuses of the same named type do not add — the best applies and the rest are
    dropped from the list, so the popup's terms are the terms that are really in the
    total. Penalties always stack, whatever their type; dodge and circumstance stack;
    everything else collides on its type name.

    **Untyped bonuses from the same source** (CRB, Getting Started, Common Terms:
    "Bonuses without a type always stack, unless they are from the same source") are NOT
    collapsed here, though alchemy lane B asked for it. Tried first (alchemy lane C,
    2026-10-06) and measured: the funnel's `source` is a label, and one document splits
    one bonus into several terms under one label — Power Attack's damage and its
    two-handed rung (13 became 10 for a level-8 greatsword), smite's damage on undead —
    so collapsing by label broke three suites' worth of feats. The rule is applied where
    a source IS an identity: between separate timed effects with one source
    (`Actor._buff_mods`).

    **The `magic_stacking` house rule** (rules/houserules.py; the owner's answer to the
    alchemy plan's open point 2, 2026-10-06: "every typed bonus"). With it on, two bonuses
    of one type from DIFFERENT sources add — enhancement, morale, alchemical and the
    rest — and the same source still keeps the better, which is the house rule's own
    "same source just reapplies". Off (the default) is the book. One switch, read here,
    in the one funnel every total passes through, never a second alchemy-only path.
    `magic_stacking` passed explicitly wins (a test, a caller holding the value); None
    reads the table's setting, and only when a typed collision needs the answer — the
    settings file is read fresh on every ask (houserules' own rule against stale
    caches), so most stacks never touch it.
    """
    house = magic_stacking
    if house is None:
        # Asked only when it could change the answer: two positive bonuses of one named
        # type from different sources.
        seen: dict[str, str] = {}
        for m in mods:
            t = (m.type or "").strip().lower()
            if m.value <= 0 or t in _SELF_STACKING:
                continue
            src = (m.source or "").strip().lower()
            if seen.setdefault(t, src) != src:
                house = _house_stacking()
                break
    best: dict[tuple, Modifier] = {}
    out: list[Modifier] = []
    for m in mods:
        t = (m.type or "").strip().lower()
        if m.value <= 0 or t in _SELF_STACKING:
            out.append(m)
            continue
        src = (m.source or "").strip().lower()
        key: tuple = (t, src) if house else (t,)
        have = best.get(key)
        if have is None:
            best[key] = m
            out.append(m)
        elif m.value > have.value:
            out[out.index(have)] = m
            best[key] = m
    return out


@dataclass
class Roll:
    die: str
    faces: list[int]
    modifiers: list[Modifier] = field(default_factory=list)
    label: str = ""
    visibility: str = "hidden"

    @property
    def raw(self) -> int:
        return sum(self.faces)

    @property
    def natural(self) -> int | None:
        """The single d20 face, when there is exactly one — crits and natural 1s are
        defined on the face, not the total."""
        return self.faces[0] if self.die.endswith("d20") and len(self.faces) == 1 else None

    @property
    def total(self) -> int:
        return self.raw + sum(m.value for m in self.modifiers)

    @property
    def modifier_total(self) -> int:
        return sum(m.value for m in self.modifiers)

    def breakdown(self) -> str:
        if not self.modifiers:
            return str(self.raw)
        terms = " ".join(
            f"{'+' if m.value >= 0 else '-'}{abs(m.value)} {m.source}" for m in self.modifiers
        )
        return f"{self.raw} {terms} = {self.total}"

    def as_dict(self) -> dict:
        return {
            "die": self.die,
            "faces": self.faces,
            "raw": self.raw,
            "natural": self.natural,
            "modifiers": [m.as_dict() for m in self.modifiers],
            "modifier_total": self.modifier_total,
            "total": self.total,
            "label": self.label,
            "visibility": self.visibility,
        }


def d20_succeeds(roll: Roll, dc: int) -> bool:
    """Whether a d20 roll whose natural face decides meets its DC: an attack roll, a
    combat manoeuvre, or a saving throw.

    Core Rulebook p.180: a natural 1 on a saving throw is always a failure and a natural
    20 always a success — the same rule attack rolls and manoeuvres already honoured,
    each in its own copy. Saves had none: `_op_save`, the cast save, both ward saves and
    the survival saves decided on the total alone, so a natural 20 that missed the DC
    failed (measured 2026-09-28 building the coup de grâce, whose save was the first to
    ask). One reader now, and every save site calls it.

    NOT for skill or ability checks: 1e says in as many words that a 20 on a skill check
    is not an automatic success, and stabilising, holding one's breath and a caster
    level check are checks. `Roll.natural` is the one d20 face — a player-rolled d20
    through `Dice.given` or `Dice.given_total` keeps it too — and None for anything
    else, which then falls through to the total.
    """
    if roll.natural == 20:
        return True
    if roll.natural == 1:
        return False
    return roll.total >= dc


def natural_said(roll: Roll, dc: int) -> str:
    """"on a natural 20" / "on a natural 1" when the face overruled the total, else "".

    For a tell that would otherwise read as bad arithmetic: "makes the save (23 against
    DC 27)" is how the coup de grâce's first live natural 20 came out.
    """
    made = d20_succeeds(roll, dc)
    if made and roll.total < dc:
        return "on a natural 20"
    if not made and roll.total >= dc:
        return "on a natural 1"
    return ""


class Dice:
    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def parse(self, notation: str) -> tuple[int, int, int]:
        # The herb corpus states some rolls as a range — "Heals 1-4 hit points" — and
        # the extractor keeps that form. A range is exact dice arithmetic: a-b is
        # 1d(b-a+1) shifted up by a-1, so 1-4 is a d4 and 2-8 is 1d7+1. Refusing it was
        # a 500 on the drink button for every jar authored in the corpus's own words.
        r = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(notation or ""))
        if r:
            lo, hi = int(r.group(1)), int(r.group(2))
            if hi > lo:
                return 1, hi - lo + 1, lo - 1
        # A flat number is a legal amount of damage and always has been —
        # `effectspec._is_dice` has accepted one since it was written, and harm's "10
        # points per caster level" resolves to a bare "150" at caster level 15. Refusing
        # it here meant an authored effect that validated cleanly and then raised BadDice
        # in the middle of resolution, which is the worst of both answers.
        #
        # Zero dice of one face, plus the number as the flat term: `roll` rolls nothing
        # and the total is exactly what was asked for.
        if re.fullmatch(r"\s*\d+\s*", str(notation or "")):
            return 0, 1, int(str(notation).strip())
        m = DICE_RE.match(notation)
        if not m:
            raise BadDice(f"cannot read dice notation {notation!r}")
        count = int(m.group(1) or 1)
        faces = int(m.group(2))
        flat = int(m.group(4) or 0)
        if m.group(3) == "-":
            flat = -flat
        if count < 1 or count > 100 or faces < 2 or faces > 1000:
            raise BadDice(f"implausible dice {notation!r}")
        # The bound belongs on the value, not on the notation. Guarding the dice and
        # not the constant meant the whole guard was defeated by writing the number
        # after a plus sign: "1d6+999999" passed as plausible and dealt a million
        # points. The flat term gets the same ceiling as the dice it rides with —
        # 100d1000 is the most the notation half allows, so nothing legal is refused.
        if abs(flat) > 100_000:
            raise BadDice(f"implausible flat term in {notation!r}")
        return count, faces, flat

    def roll(
        self,
        notation: str,
        modifiers: list[Modifier] | None = None,
        label: str = "",
        visibility: str = "hidden",
    ) -> Roll:
        count, faces, flat = self.parse(notation)
        rolled = [self._rng.randint(1, faces) for _ in range(count)]
        mods = list(modifiers or [])
        if flat:
            mods.append(Modifier(flat, "notation"))
        return Roll(die=notation.strip(), faces=rolled, modifiers=mods,
                    label=label, visibility=visibility)

    def d20(
        self,
        modifiers: list[Modifier] | None = None,
        label: str = "",
        visibility: str = "hidden",
    ) -> Roll:
        return self.roll("1d20", modifiers, label, visibility)

    def given(
        self,
        face: int,
        modifiers: list[Modifier] | None = None,
        label: str = "",
        die: str = "1d20",
    ) -> Roll:
        """Build a Roll from a face the player already rolled on the popup.

        The player supplies the face; the engine still owns every modifier and the total.
        A player who edits the number in the form changes the face, never the maths.
        """
        count, faces, _ = self.parse(die)
        if not 1 <= face <= faces:
            raise BadDice(f"{face} is not a face of {die}")
        return Roll(die=die, faces=[face], modifiers=list(modifiers or []),
                    label=label, visibility="player")

    def given_total(
        self,
        total: int,
        notation: str,
        modifiers: list[Modifier] | None = None,
        label: str = "",
    ) -> Roll:
        """A player-supplied result for a pool of dice — 2d6 comes back as one number.

        Asking for each die separately is how a program would do it and not how a person
        does it: you roll two dice, look at them, and say "nine". The engine still owns
        every modifier; only the dice total comes from the player.

        Natural 20s and 1s stay meaningful because a 1d20 pool is stored as a single
        face, which is what `Roll.natural` looks for.
        """
        count, faces, flat = self.parse(notation)
        low, high = count, count * faces
        if not low <= total <= high:
            raise BadDice(
                f"{total} is not a possible result for {notation} ({low}-{high})"
            )
        mods = list(modifiers or [])
        if flat:
            mods.append(Modifier(flat, "notation"))
        # Distribute the reported total across the dice so `faces` stays honest about
        # how many were rolled. Only the sum is load-bearing.
        base, extra = divmod(total - count, faces - 1) if faces > 1 else (0, 0)
        spread = []
        for i in range(count):
            v = 1 + (faces - 1 if i < base else (extra if i == base else 0))
            spread.append(v)
        return Roll(die=notation.strip(), faces=spread, modifiers=mods,
                    label=label, visibility="player")
