"""Turning the GM's stated difficulty into a number.

The GM agent picks a word from PF1e's own difficulty table; this maps the word to the DC.
See docs/intent-protocol.md §1 — a model asked for a calibrated integer is inconsistent
across a session, while a model asked to choose one of eight words is doing a
classification task it is good at, and the calibration lives here where it can be tuned
once.

An explicit integer is still accepted, because it is the natural thing to write, but it is
clamped and the clamp is recorded.
"""
from __future__ import annotations

from dataclasses import dataclass

from .tables import CIRCUMSTANCE, DC_BANDS


class BadDC(ValueError):
    pass


@dataclass
class ResolvedDC:
    value: int
    band: str | None
    stated: int | None = None
    clamped: bool = False
    circumstance: int = 0
    circumstance_why: str = ""

    @property
    def final(self) -> int:
        # A favourable circumstance makes the task easier, which lowers the DC. It is
        # applied here rather than to the roll so that the number the player is asked to
        # beat is the number they see.
        return self.value - self.circumstance

    def explain(self) -> str:
        bits = []
        if self.band:
            bits.append(f"{self.band.replace('_', ' ')} (DC {self.value})")
        else:
            bits.append(f"DC {self.value}")
        if self.clamped:
            bits.append(f"clamped from {self.stated}")
        if self.circumstance:
            bits.append(f"{self.circumstance:+d} circumstance: {self.circumstance_why}")
        return "; ".join(bits)

    def as_dict(self) -> dict:
        return {
            "value": self.final,
            "base": self.value,
            "band": self.band,
            "stated": self.stated,
            "clamped": self.clamped,
            "circumstance": self.circumstance,
            "circumstance_why": self.circumstance_why,
            "explain": self.explain(),
        }


def plausible_range(level: int) -> tuple[int, int]:
    """What a DC can sensibly be for a character of this level.

    Not a rules table — a guard rail. A model that says DC 45 for a locked door is
    telling you about the scene's mood, not about the door, and the clamp keeps the game
    playable while the log records that it happened.
    """
    return 5, 20 + 2 * max(1, level)


def resolve(
    spec: dict | int | str | None,
    level: int = 1,
    circumstance: dict | str | None = None,
) -> ResolvedDC:
    if spec is None:
        raise BadDC("no DC given")

    band: str | None = None
    stated: int | None = None
    clamped = False

    if isinstance(spec, str):
        spec = {"band": spec}
    elif isinstance(spec, int):
        spec = {"value": spec}

    if "band" in spec and spec["band"] is not None:
        band = str(spec["band"]).strip().lower().replace(" ", "_")
        if band not in DC_BANDS:
            raise BadDC(
                f"unknown difficulty band {band!r}; expected one of {sorted(DC_BANDS)}"
            )
        value = DC_BANDS[band]
    elif "value" in spec and spec["value"] is not None:
        stated = int(spec["value"])
        low, high = plausible_range(level)
        value = max(low, min(high, stated))
        clamped = value != stated
        # Report the band the number actually landed in, so the log reads in the same
        # vocabulary whichever way the GM expressed it.
        band = _nearest_band(value)
    else:
        raise BadDC(f"DC spec has neither band nor value: {spec!r}")

    circ_value, circ_why = 0, ""
    if circumstance:
        if isinstance(circumstance, str):
            circumstance = {"value": circumstance}
        key = str(circumstance.get("value", "")).strip().lower()
        if key and key not in CIRCUMSTANCE:
            raise BadDC(
                f"circumstance must be one of {sorted(CIRCUMSTANCE)}, got {key!r}"
            )
        if key:
            circ_value = CIRCUMSTANCE[key]
            circ_why = circumstance.get("why", "") or key

    return ResolvedDC(
        value=value, band=band, stated=stated, clamped=clamped,
        circumstance=circ_value, circumstance_why=circ_why,
    )


def _nearest_band(value: int) -> str:
    return min(DC_BANDS, key=lambda b: (abs(DC_BANDS[b] - value), DC_BANDS[b]))
