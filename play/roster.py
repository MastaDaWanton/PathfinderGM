"""Characters, saved.

Until now the one character lived inside the campaign save, so a death would have taken
the whole record with it. Characters are people you have played and want back; they
outlive a campaign and they outlive dying.

Each character is one file under the user data directory, holding the sheet and what
became of them. The dead are kept — a character who died in the second session is the
reason the third session went the way it did, and deleting them would throw away the
only record of it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from django.conf import settings

from rules.sheet import Actor, from_dict, to_dict

ROSTER_VERSION = 1

ALIVE = "alive"
DEAD = "dead"
RETIRED = "retired"


def root() -> Path:
    p = Path(settings.CAMPAIGN_DIR).parent / "characters"
    p.mkdir(parents=True, exist_ok=True)
    return p


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "character").lower()).strip("-")
    return s or "character"


@dataclass
class Entry:
    id: str
    name: str
    status: str
    sheet: dict
    created: str = ""
    died: str = ""
    epitaph: str = ""
    campaign_id: str = ""
    turns_played: int = 0

    @property
    def actor(self) -> Actor:
        return from_dict(self.sheet, ref="pc")

    def summary(self) -> dict:
        a = self.actor
        cls = a.class_data.get("name", "")
        return {
            "id": self.id, "name": self.name, "status": self.status,
            "line": " · ".join(x for x in (a.heritage, a.race, f"{cls} {a.level}".strip())
                               if x),
            "hp": f"{a.hp}/{a.hp_max}",
            "created": self.created, "died": self.died, "epitaph": self.epitaph,
            "turns_played": self.turns_played,
        }


def path_for(character_id: str) -> Path:
    return root() / f"{character_id}.json"


def save(entry: Entry) -> Path:
    payload = {
        "roster_version": ROSTER_VERSION,
        "id": entry.id, "name": entry.name, "status": entry.status,
        "created": entry.created or datetime.now().isoformat(timespec="seconds"),
        "died": entry.died, "epitaph": entry.epitaph,
        "campaign_id": entry.campaign_id, "turns_played": entry.turns_played,
        "sheet": entry.sheet,
    }
    p = path_for(entry.id)
    p.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return p


def load(character_id: str) -> Entry | None:
    p = path_for(character_id)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if d.get("roster_version") != ROSTER_VERSION:
        return None
    return Entry(
        id=d["id"], name=d.get("name", ""), status=d.get("status", ALIVE),
        sheet=d.get("sheet", {}), created=d.get("created", ""), died=d.get("died", ""),
        epitaph=d.get("epitaph", ""), campaign_id=d.get("campaign_id", ""),
        turns_played=d.get("turns_played", 0),
    )


def everyone() -> list[Entry]:
    out = [e for e in (load(p.stem) for p in sorted(root().glob("*.json"))) if e]
    # The living first, then the dead, newest first within each.
    out.sort(key=lambda e: (e.status != ALIVE, e.created), reverse=False)
    return out


def enrol(actor: Actor, campaign_id: str = "") -> Entry:
    """Put a character on the roster, or return the one already there."""
    cid = unique_id(slugify(actor.name))
    entry = Entry(id=cid, name=actor.name, status=ALIVE, sheet=to_dict(actor),
                  campaign_id=campaign_id,
                  created=datetime.now().isoformat(timespec="seconds"))
    save(entry)
    return entry


def unique_id(base: str) -> str:
    if not path_for(base).exists():
        return base
    n = 2
    while path_for(f"{base}-{n}").exists():
        n += 1
    return f"{base}-{n}"


def record(character_id: str, actor: Actor, turns_played: int | None = None) -> None:
    """Write the character's current sheet back, so the roster is never behind the game."""
    entry = load(character_id)
    if entry is None:
        return
    entry.sheet = to_dict(actor)
    entry.name = actor.name
    if turns_played is not None:
        entry.turns_played = turns_played
    save(entry)


def bury(character_id: str, actor: Actor, epitaph: str = "") -> Entry | None:
    entry = load(character_id)
    if entry is None:
        return None
    entry.status = DEAD
    entry.sheet = to_dict(actor)
    entry.died = datetime.now().isoformat(timespec="seconds")
    entry.epitaph = epitaph
    save(entry)
    return entry


# --- Who is available to play ------------------------------------------------------------

def retire_file(character_id: str) -> tuple[bool, str]:
    """Take a character off the roster.

    Archived rather than unlinked, which is the same choice `campaign._read` makes for
    a save it cannot parse and `tools/prune_roster.py` made for the duplicate Kessts:
    the row leaves the page, the file stays on disk. A character is the record of a
    game somebody played, and "delete" that cannot be undone is the one button nobody
    should be one misclick away from.
    """
    entry = load(character_id)
    if entry is None:
        return False, f"there is no character called {character_id!r}."

    from . import campaign as campaign_mod

    if campaign_mod.current().character_id == character_id:
        return False, (f"{entry.name} is the character you are playing. Switch to "
                       f"somebody else first.")

    archive = root() / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    src = path_for(character_id)
    if src.exists():
        src.rename(archive / src.name)
    return True, f"{entry.name} is off the roster. Their file is in {archive}."


def pregens() -> list[dict]:
    """The characters that ship with the app, for when there is nobody left to play.

    Full guided 1e creation is a settled architecture decision and is not built yet;
    until it is, a death needs *somebody* to hand the player, and these are it.
    """
    out = []
    for p in sorted(Path(settings.BASE_DIR / "fixtures").glob("pc-*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            actor = from_dict(data, ref="pc")
        except Exception:
            continue
        cls = actor.class_data.get("name", "")
        out.append({
            "source": p.stem,
            "name": actor.name,
            "line": " · ".join(x for x in (actor.heritage, actor.race,
                                           f"{cls} {actor.level}".strip()) if x),
            "hp": actor.hp_max,
            "notes": (actor.notes or "").strip().split("\n")[0],
        })
    return out


def from_pregen(source: str) -> Actor:
    p = Path(settings.BASE_DIR / "fixtures") / f"{source}.json"
    if not p.exists() or not p.name.startswith("pc-"):
        raise FileNotFoundError(f"no such character {source!r}")
    return from_dict(json.loads(p.read_text(encoding="utf-8")), ref="pc")
