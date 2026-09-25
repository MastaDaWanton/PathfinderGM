"""Every weapon, shipped and authored.

`tables.WEAPONS` held eleven weapons as Python — enough for the pregenerated characters and
nothing else. A player who wanted a glaive got `KeyError: no such weapon 'glaive'`.

`content/weapons/weapons.json` holds 456, and the layering runs the *opposite* way to the
class overlay on purpose: the imported file provides the base and the eleven hand-written
entries merge on top of it. Those eleven are the curated ones — their `finessable` and
`hands` values are what several hundred tests are written against — and a bulk import
silently changing the rapier's crit range would be a real regression discovered in play.
Everything the file adds beyond them is new, so nothing it says can break anything.

Homebrew layers last, as it does everywhere else.
"""
from __future__ import annotations

import json
from pathlib import Path

from .tables import WEAPONS as SHIPPED
from pathfindergm import files

_ALL: dict[str, dict] | None = None
_META: dict = {}


def _folders() -> list[Path]:
    from django.conf import settings

    return [Path(settings.BASE_DIR) / "content" / "weapons",
            Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "weapons"]


def all_weapons() -> dict[str, dict]:
    global _ALL, _META
    if _ALL is None:
        out: dict[str, dict] = {}
        for folder in _folders():
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception as exc:
                    files.unreadable(path, exc)
                    continue
                entries = data.get("weapons") if isinstance(data, dict) else None
                if not isinstance(entries, list):
                    entries = [data] if isinstance(data, dict) and data.get("id") else []
                if isinstance(data, dict):
                    _META.update({k: v for k, v in data.items() if k != "weapons"})
                for e in entries:
                    key = str(e.get("id") or e.get("name", "")).strip().lower()
                    if not key:
                        continue
                    # Merged, not replaced: a homebrew edit touching one field must not
                    # drop the twenty it never mentioned.
                    out.setdefault(key, {}).update(e)
                    out[key].setdefault("name", e.get("name", key))

        # The hand-written eleven win. See the module docstring.
        for key, entry in SHIPPED.items():
            out.setdefault(key, {}).update(entry)

        for entry in out.values():
            entry.setdefault("traits", [])
            entry.setdefault("category", "melee")
            entry.setdefault("hands", 1)
            entry.setdefault("prof", "martial")
            entry.setdefault("crit_range", 20)
            entry.setdefault("crit_mult", 2)
            entry.setdefault("type", "untyped")
            entry.setdefault("finessable", False)
        _ALL = out
    return _ALL


def meta() -> dict:
    all_weapons()
    return dict(_META)


def get(key: str) -> dict:
    found = all_weapons().get((key or "").strip().lower())
    if found is None:
        raise KeyError(f"no such weapon {key!r}")
    return found


def has(key: str) -> bool:
    return (key or "").strip().lower() in all_weapons()


def has_trait(key: str, trait: str) -> bool:
    """Does this weapon carry that special quality — `reach`, `trip`, `brace`?

    Tolerant of a missing weapon rather than raising, because the callers are asking a
    question about geometry and "no weapon, so no reach" is the right answer for an
    unarmed creature.
    """
    try:
        weapon = get(key)
    except KeyError:
        return False
    return trait.strip().lower() in [t.lower() for t in weapon.get("traits", [])]


def search(text: str = "", prof: str = "", category: str = "", trait: str = "",
           limit: int = 60) -> list[dict]:
    needle = text.strip().lower()
    out = []
    for weapon in all_weapons().values():
        if prof and weapon.get("prof") != prof.strip().lower():
            continue
        if category and weapon.get("category") != category.strip().lower():
            continue
        if trait and trait.strip().lower() not in [t.lower()
                                                   for t in weapon.get("traits", [])]:
            continue
        if needle and needle not in str(weapon.get("name", "")).lower():
            continue
        out.append(weapon)

    def rank(w: dict) -> tuple:
        low = str(w.get("name", "")).lower()
        if not needle:
            return (0, low)
        return (0 if low == needle else 1 if low.startswith(needle) else 2, low)

    out.sort(key=rank)
    return out[:limit] if limit else out


__all__ = ["all_weapons", "get", "has", "has_trait", "meta", "search"]
