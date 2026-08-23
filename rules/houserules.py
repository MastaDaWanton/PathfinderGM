"""The table's own rules: toggles that bend 1e where the player says to.

These are settings, not content — one small JSON file beside the homebrew folders,
read fresh on every ask. No cache, because the file is a hundred bytes and a cached
copy of a rule the player just changed is a rule that silently is not in effect: the
exact staleness trap CLAUDE.md records against derived caches.

Two rules exist today.

**Point buy tier.** 1e's own table stops at 25 (Epic Fantasy); the tiers above it are
homebrew and say so. One is active at a time — a budget is a single number, and the
forge, the validator and the refusal text all read the same one, so there is nothing
to disagree.

**Magic effect stacking.** By the book, magical effects from different sources do not
stack — the best applies — and the same source reapplies rather than piling up. The
toggle keeps the second half (same source still reapplies; two castings of one ward
are a renewal, not a doubling) and lifts the first: different sources add. Today the
engine's live no-stack rule is temporary hit points, so that is what the toggle
reaches; typed bonuses join it when the engine executes them at all. Where the rules
already refresh-on-same-source — guards, compulsions — the toggle changes nothing,
because that half is the half both modes share.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings

# The four named tiers are the Core Rulebook's own table. Everything past 25 is this
# app's homebrew, and the names admit it rather than borrowing the book's authority.
POINT_BUY_TIERS = [
    {"points": 10, "name": "Low fantasy", "book": True},
    {"points": 15, "name": "Standard fantasy", "book": True},
    {"points": 20, "name": "High fantasy", "book": True},
    {"points": 25, "name": "Epic fantasy", "book": True},
    {"points": 30, "name": "Mythic", "book": False},
    {"points": 40, "name": "Legendary", "book": False},
    {"points": 50, "name": "Demigod", "book": False},
    {"points": 75, "name": "Ascendant", "book": False},
    {"points": 100, "name": "The full hundred", "book": False},
]

DEFAULTS = {"point_buy": 20, "magic_stacking": False}


def _path() -> Path:
    """Beside the homebrew content folders — not *in* the rulesets one, because every
    file in a bench folder counts as something the user authored, and a settings file
    showing up as "1 yours" on the bench is a lie about what was made."""
    p = Path(settings.CAMPAIGN_DIR).parent / "homebrew"
    p.mkdir(parents=True, exist_ok=True)
    return p / "house-rules.json"


def active() -> dict:
    """The rules in effect, defaults filled in, unknown keys dropped.

    A file this small is read on every ask on purpose — see the module docstring.
    A half-written or hand-mangled file falls back to the book rather than crashing
    every roll in the app over a settings toggle.
    """
    out = dict(DEFAULTS)
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
    except Exception:
        return out
    if isinstance(raw, dict):
        if raw.get("point_buy") in {t["points"] for t in POINT_BUY_TIERS}:
            out["point_buy"] = int(raw["point_buy"])
        out["magic_stacking"] = bool(raw.get("magic_stacking", False))
    return out


def set_active(updates: dict) -> tuple[dict, list[str]]:
    """Change the house rules, or say exactly why not. Only known keys move."""
    problems: list[str] = []
    current = active()
    if "point_buy" in updates:
        tiers = {t["points"] for t in POINT_BUY_TIERS}
        try:
            points = int(updates["point_buy"])
        except (TypeError, ValueError):
            points = -1
        if points not in tiers:
            problems.append(
                f"{updates['point_buy']!r} is not a point-buy tier; the tiers are "
                + ", ".join(str(t["points"]) for t in POINT_BUY_TIERS) + ".")
        else:
            current["point_buy"] = points
    if "magic_stacking" in updates:
        current["magic_stacking"] = bool(updates["magic_stacking"])
    if not problems:
        _path().write_text(json.dumps(current, indent=2), encoding="utf-8")
    return active(), problems


def point_budget() -> int:
    return active()["point_buy"]


def magic_stacking() -> bool:
    return active()["magic_stacking"]
