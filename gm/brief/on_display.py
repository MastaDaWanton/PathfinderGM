"""ON DISPLAY: what the counters here really have, when the player looks them over.

Playtest 2026-11-15 #13: "I walk to the market and look over what the stalls have on
display" was read `go` + `look`, no rule answered the look, and the narration named no
goods at all — while the general store's Trade panel listed a tent, a hooded lantern and
hemp rope. A model not shown the shelf either names nothing or invents one, so the shelf
the panel and `buy` read (`market.on_sale`) is put in the brief as a fact on the beat the
player looks, searches or browses — the reading's closed acts, never the words. Only then:
every counter's whole shelf on every beat would drown the brief.
"""
from __future__ import annotations

import logging

ORDER = 46
SLOT = "people"
SCAFFOLD = ("ON DISPLAY (fact):", "what is really on the counter; name only these goods.")

_LOOKS = ("look", "search")
_SHOWN = 6


def _looking(reading) -> bool:
    from gm import interpret

    acts = (reading or {}).get("actions") or [] if isinstance(reading, dict) else []
    return any(str(a.get("act") or "") in _LOOKS and interpret.acting(a) for a in acts)


def section(ctx) -> tuple[str, dict]:
    from rules import keepers, market

    scene = ctx.scene
    if not _looking(ctx.reading):
        return "", {}
    place = str(getattr(scene, "location_id", "") or "nowhere")
    day = market.day_of(int(getattr(scene, "clock_minutes", 0) or 0))
    lines, facts = [], {}
    for a in (getattr(scene, "actors", {}) or {}).values():
        if a.is_pc or not keepers.keeps_a_counter(a):
            continue
        try:
            stall = market.stall_of(scene, a)
            shelf = market.on_sale(
                place, stall, day, getattr(scene, "market_taken", {}) or {},
                counter_kind=market.counter_kind_here(scene, stall),
                scale=market.scale_here(ctx.world, getattr(scene, "location_id", "")))
        except Exception:  # noqa: BLE001 - one shelf that cannot be drawn costs only its line
            logging.getLogger(__name__).exception("a counter's shelf could not be listed")
            continue
        # The everyday goods first (lantern, rope, bread), then the craft materials.
        from rules import goods

        staple = sorted({str(m.name) for m in shelf if isinstance(m, goods.Good)
                         and str(getattr(m, "kind", "")) != "material"})
        # Every everyday good (a general store's are about thirty), then a few materials.
        rest = sorted({str(getattr(m, "name", "")) for m in shelf} - set(staple) - {""})
        names = staple + rest[:_SHOWN]
        if not names:
            continue
        more = (f", and {len(rest) - _SHOWN} craft materials more"
                if len(rest) > _SHOWN else "")
        lines.append(f"  ON DISPLAY (fact): at {a.name}'s counter: "
                     f"{', '.join(names)}{more}; what is really on the counter; "
                     f"name only these goods.")
        facts[a.ref] = names
    if not lines:
        return "", {}
    return "\n" + "\n".join(lines), facts
