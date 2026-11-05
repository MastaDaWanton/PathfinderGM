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


# What a tell says after "makes the check" for a success by `margin`. A success by
# nothing — the total exactly the DC, which 1e calls a success ("equal to or greater than
# the DC", CRB p.86) — was told "makes the perception check by 0", and the narrator wrote
# it failed: on the narration diagnosis bench (2026-11-04, mechanism 4, 10% of the
# baseline's errors) the 12B narrator read "by 0" as "by nothing" — the climb a slip, a
# trip "by 0" the wolf still standing. Said as what it is: made, only just.
#
# Weighed against the plan lane's "just makes the perception check" on the same recorded
# call (the climb-fail run 1 slot, re-asked 6 times each at the slot's own temperature,
# 2026-11-04, read by hand): "by 0" came back failed 6 of 6, "just makes" made 6 of 6, and
# ", only just" made 6 of 6 — narrowly ("you just barely make out the shapes"), which is
# what the dice said. Both read as success; this one also keeps the margin, so it stays.
JUST_MADE = ", only just"


def by(margin: int) -> str:
    """" by 3" after a success by 3, or `JUST_MADE` after a success by 0 — the one writer
    of every "makes … by N" a tell says. A failure is always by one or more, so it never
    needs this."""
    return f" by {int(margin)}" if int(margin) else JUST_MADE


@dataclass
class ResolvedDC:
    value: int
    band: str | None
    stated: int | None = None
    clamped: bool = False
    circumstance: int = 0
    circumstance_why: str = ""
    # Where a DC the engine computed came from, in the book's terms: "indifferent 15,
    # Cha +2". Empty for a band or a stated number, which say so themselves.
    basis: str = ""

    @property
    def final(self) -> int:
        # A favourable circumstance makes the task easier, which lowers the DC. It is
        # applied here rather than to the roll so that the number the player is asked to
        # beat is the number they see. Checked 2026-10-03: the 3.5 SRD's "Favorable and
        # Unfavorable Conditions" names four options, +2/-2 on the check and -2/+2 on the
        # DC, and PF1e's Core Rulebook did not carry that passage over — its nearest is
        # the GM's "+2 or a -2 bonus or penalty" fiat. Moving the DC is the inherited 3.5
        # option and the odds are identical, so the arithmetic stands; what `explain`
        # said about it was wrong (below). docs/rules-and-opening-2026-10-03.md.
        return self.value - self.circumstance

    def explain(self) -> str:
        bits = []
        if self.basis:
            bits.append(f"DC {self.value} ({self.basis})")
        elif self.band:
            bits.append(f"{self.band.replace('_', ' ')} (DC {self.value})")
        else:
            bits.append(f"DC {self.value}")
        if self.clamped:
            bits.append(f"clamped from {self.stated}")
        if self.circumstance:
            # Said as what was done to the number. It read "+2 circumstance: …" until
            # 2026-10-03, which is the book's wording for a BONUS ON THE CHECK — beside a
            # DC that had gone DOWN by 2 (the clerk's average 10 shown as 8). Same odds,
            # wrong rule named; the record should say which of the book's options ran.
            moved = "lowered" if self.circumstance > 0 else "raised"
            kind = "favourable" if self.circumstance > 0 else "unfavourable"
            bits.append(f"DC {moved} by {abs(self.circumstance)} to {self.final} for "
                        f"a {kind} circumstance: {self.circumstance_why}")
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
            **({"basis": self.basis} if self.basis else {}),
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
