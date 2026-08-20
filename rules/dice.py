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
    """
    value: int
    source: str

    def as_dict(self) -> dict:
        return {"value": self.value, "source": self.source}


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


class Dice:
    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def parse(self, notation: str) -> tuple[int, int, int]:
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
