"""CARGO STOWED: what a ship's hold carries, when the party stands in it (rules/ships.py).

Playtest 2026-11-16 #92: the hold of a merchantman taken by threat "held nothing" — the
brief said nothing of a cargo, so a Perception roll (a natural 1) decided whether the
crates in plain sight held goods. Cargo stowed in a hold is seen, not found: said here as
fact, whose it is included, from the engine's own record (`Vessel.cargo`, `Scene.cargo`).
"""
from __future__ import annotations

ORDER = 13
SLOT = "place"
# Labels a narrator would not write: "in the hold of" is prose, and the scaffold's
# 4-grams are what the verbatim-brief check flags on the page.
SCAFFOLD = (
    "CARGO STOWED aboard",
    "(fact, plainly visible; no search needed, and a failed search does not empty it):",
)


def section(ctx) -> tuple[str, dict]:
    scene, here = ctx.scene, ctx.here
    if scene is None or here is None:
        return "", {}
    from rules import places, ships

    pid = str(getattr(here, "id", "") or "")
    if places.base_of(pid).rsplit(":", 1)[-1] != "the-hold":
        return "", {}
    vid = ships.vessel_of(pid)
    raw = next((v for v in (getattr(scene, "vessels", None) or ())
                if str(v.get("id")) == vid), None)
    ship = ships.Vessel.from_dict(raw) if raw else None
    if ship is None:
        return "", {}
    theirs, ours = ships.hold_said(scene, ship)
    bits = []
    if theirs:
        bits.append("her owners' cargo, " + ", ".join(theirs))
    if ours:
        bits.append("yours, " + ", ".join(ours))
    said = "; ".join(bits) if bits else "nothing; she carries no cargo."
    return (f"  CARGO STOWED aboard {ship.name} (fact, plainly visible; no search needed, "
            f"and a failed search does not empty it): {said}."
            ), {"hold": {"vessel": ship.id, "theirs": theirs, "ours": ours}}
