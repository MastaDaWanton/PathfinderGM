"""The shelf of worlds, and everything on the front page.

World Bible writes worlds; this app plays in them. The handoff is a file, so a "world
library" is a directory of exports — one shipped with the app so there is something to
play on a fresh install, and one in the user's data directory that they drop their own
exports into.

Reading a whole export to draw a card would be wasteful and, worse, fragile: a world
written against a schema this build cannot read must still be *listed*, with the reason,
rather than crashing the front page or silently vanishing from it.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

from world.loader import SUPPORTED_MAJOR, UnsupportedSchema, load_cached


def user_dir() -> Path:
    """Where a player's own exports live. Beside campaigns and characters, so one
    directory holds everything the app has ever made or been given."""
    p = Path(settings.CAMPAIGN_DIR).parent / "worlds"
    p.mkdir(parents=True, exist_ok=True)
    return p


def shipped_dir() -> Path:
    return Path(settings.BASE_DIR) / "fixtures"


@dataclass
class WorldCard:
    """One world, described well enough to choose it without opening it."""
    id: str
    name: str
    source: str
    shipped: bool = False
    premise: str = ""
    entities: int = 0
    events: int = 0
    settlements: list[str] = field(default_factory=list)
    peoples: list[str] = field(default_factory=list)
    problem: str = ""

    @property
    def playable(self) -> bool:
        return not self.problem

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "source": self.source,
            "shipped": self.shipped, "premise": self.premise,
            "entities": self.entities, "events": self.events,
            "settlements": self.settlements, "peoples": self.peoples,
            "problem": self.problem, "playable": self.playable,
        }


def _card(path: Path, shipped: bool) -> WorldCard:
    ident = path.stem
    try:
        world = load_cached(path)
    except UnsupportedSchema as exc:
        # Listed with the reason, never hidden. A world that disappears from the shelf
        # because of a version number is indistinguishable from one the user lost.
        return WorldCard(id=ident, name=path.stem.replace("-", " ").title(),
                         source=str(path), shipped=shipped, problem=str(exc))
    except Exception as exc:
        return WorldCard(id=ident, name=path.stem.replace("-", " ").title(),
                         source=str(path), shipped=shipped,
                         problem=f"could not be read: {exc}")

    premise = ""
    if isinstance(world.premise, dict):
        premise = str(world.premise.get("summary")
                      or world.premise.get("hook")
                      or next((v for v in world.premise.values() if isinstance(v, str)), ""))
    return WorldCard(
        id=ident, name=world.name, source=str(path), shipped=shipped, premise=premise,
        entities=len(world.entities), events=len(world.chronology),
        settlements=[e.name for e in world.of_kind("CITY")][:8],
        peoples=[e.name for e in world.of_kind("PEOPLE")][:8],
    )


def worlds() -> list[WorldCard]:
    """Every world available to play in.

    The shipped export is seeded rather than special-cased, so the front page has one code
    path: a world is a file on the shelf, wherever it came from.
    """
    seen: dict[str, WorldCard] = {}
    for path in sorted(shipped_dir().glob("*-campaign.json")):
        seen[path.stem] = _card(path, shipped=True)
    for path in sorted(user_dir().glob("*.json")):
        seen[path.stem] = _card(path, shipped=False)
    return list(seen.values())


def get(world_id: str) -> WorldCard:
    found = next((w for w in worlds() if w.id == world_id), None)
    if found is None:
        raise LookupError(f"no world {world_id!r}")
    return found


def import_world(source: Path) -> WorldCard:
    """Copy an export onto the shelf. Validated before it lands, so a file that cannot be
    read is refused at the point the user can still do something about it."""
    source = Path(source)
    load_cached(source)                      # raises if it is not a world we can read
    target = user_dir() / source.name
    shutil.copy(source, target)
    return _card(target, shipped=False)


# --- what has been played ------------------------------------------------------------------

def campaigns_in(world_id: str) -> list[dict]:
    """Games running in this world.

    Read off the campaign saves rather than an index, because an index is a second thing
    to keep true and this one would be wrong the first time somebody deleted a save by
    hand — which is a supported thing to do, the saves being plain files on purpose.
    """
    from . import campaign as cm
    from . import roster

    out = []
    d = Path(settings.CAMPAIGN_DIR)
    if not d.is_dir():
        return out
    for path in sorted(d.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if Path(str(data.get("world_source", ""))).stem != world_id:
            continue
        pc = (data.get("scene") or {}).get("actors", {}).get("pc", {})
        entry = roster.load(data.get("character_id", "")) if data.get("character_id") else None
        out.append({
            "id": data.get("id", path.stem),
            "character_id": data.get("character_id", ""),
            "character": pc.get("name", "somebody"),
            "hp": f"{pc.get('hp', '?')}/{pc.get('hp_max', '?')}",
            "turns": len(data.get("turn_log", [])),
            "lines": len(data.get("transcript", [])),
            "ended": data.get("ended", ""),
            "status": entry.status if entry else "alive",
            "active": data.get("id") == cm.active_id(),
            # Sandbox until campaign files exist; the field is here so the card can start
            # saying "campaign" the day one does, without the page changing.
            "kind": "sandbox",
        })
    return out


def characters_in(world_id: str) -> list[dict]:
    """Everyone on the roster whose game is in this world."""
    from . import roster

    by_campaign = {c["character_id"]: c for c in campaigns_in(world_id)}
    out = []
    for entry in roster.everyone():
        if entry.id not in by_campaign:
            continue
        summary = entry.summary()
        summary["campaign"] = by_campaign[entry.id]["id"]
        summary["turns"] = by_campaign[entry.id]["turns"]
        summary["active"] = by_campaign[entry.id]["active"]
        out.append(summary)
    return out


def recent_characters(limit: int = 12) -> list[dict]:
    """Everyone played, most active first, with the world they belong to.

    The front page's real job: one click back into whatever was last happening.
    """
    from . import campaign as cm
    from . import roster

    where: dict[str, str] = {}
    for card in worlds():
        for c in campaigns_in(card.id):
            if c["character_id"]:
                where[c["character_id"]] = card.name

    active = cm.active_id()
    out = []
    for entry in roster.everyone():
        summary = entry.summary()
        summary["world"] = where.get(entry.id, "")
        summary["active"] = entry.campaign_id == active
        summary["playable"] = entry.status != roster.DEAD
        out.append(summary)
    out.sort(key=lambda e: (not e["active"], not e["playable"], -e["turns_played"]))
    return out[:limit]
