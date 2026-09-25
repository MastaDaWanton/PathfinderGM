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
from pathfindergm import files

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
    # Which world this character was made for. Nothing recorded it, so a character
    # forged from Fantasia's own page began in Pangrella: `new_campaign` fills a missing
    # world with the shipped default, silently, and the roster had nowhere to say
    # otherwise. Empty still means the shipped default — every entry written before the
    # field existed reads back that way, and ROSTER_VERSION is deliberately NOT bumped:
    # `load` checks it for equality, so a bump would vanish every existing character.
    world_source: str = ""

    @property
    def actor(self) -> Actor:
        """The sheet as a live character. Raises if it will not validate, and that is
        deliberate — see `summary` for the half that must not."""
        return from_dict(self.sheet, ref="pc")

    def summary(self) -> dict:
        """One card's worth of this character, and it never raises.

        Reported from a live session on 2026-09-15: the home page returned a 500 and
        every campaign became unreachable, because ONE character on the roster no longer
        validated —

            IllegalSheet: Kesst Vayr: 10 skill ranks spent, 9 available
                          (8 class + Int + race, x1)

        — and `library.recent_characters` calls this in a loop with nothing catching it.
        Four places do: two in `library`, two in `views`. So the guard belongs here
        rather than at any of them, which is the same lesson as the model gate that was
        put on two doors of three and the background that was bound by one of three.

        This module already fails soft twice for the same reason: `load` returns None for
        a file that is not JSON and None for one from another roster version. A sheet that
        will not validate is the third way a character on disk can be unreadable, and it
        was the only one that took a page down with it.

        `actor` still raises. Listing a character must be safe; PLAYING one must not be,
        because a game started from a sheet the rules reject is a worse failure than a
        card that says it cannot be read. The split is the point.
        """
        blank = {
            "id": self.id, "name": self.name, "status": self.status,
            "created": self.created, "died": self.died, "epitaph": self.epitaph,
            "turns_played": self.turns_played, "unreadable": "",
            # Which world they were forged in, so the roster can send them back to the
            # outfitter with the same shelf the forge used (item 24, 2026-09-19).
            "world_source": self.world_source,
        }
        try:
            a = self.actor
        except Exception as exc:
            # Every key a caller or template reads, so an unreadable character produces a
            # card rather than a KeyError one frame later — which would move the crash
            # rather than fix it. The reason is shown: a player who cannot see why cannot
            # decide whether to fix the character or delete it, and both are their call.
            reason = str(exc).strip() or exc.__class__.__name__
            # The name is already the card's heading; the sheet's own message repeats it.
            if reason.lower().startswith(f"{self.name.lower()}:"):
                reason = reason[len(self.name) + 1:].strip()
            return {**blank, "line": reason, "hp": "—", "unreadable": reason}
        cls = a.class_data.get("name", "")
        return {
            **blank,
            "line": " · ".join(x for x in (a.heritage, _race_name(a.race), f"{cls} {a.level}".strip())
                               if x),
            "hp": f"{a.hp}/{a.hp_max}",
        }

    def playable(self) -> bool:
        """Whether a game can be started from this character at all.

        Computed here because it was computed in two views with the same expression and
        neither of them knew about the third reason: dead, and now unreadable.
        """
        return self.status != DEAD and not self.summary()["unreadable"]


def path_for(character_id: str) -> Path:
    return root() / f"{character_id}.json"


def save(entry: Entry) -> Path:
    payload = {
        "roster_version": ROSTER_VERSION,
        "id": entry.id, "name": entry.name, "status": entry.status,
        "created": entry.created or datetime.now().isoformat(timespec="seconds"),
        "died": entry.died, "epitaph": entry.epitaph,
        "campaign_id": entry.campaign_id, "turns_played": entry.turns_played,
        "world_source": entry.world_source,
        "sheet": entry.sheet,
    }
    p = path_for(entry.id)
    files.write_text(p, json.dumps(payload, indent=1))
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
        world_source=d.get("world_source", ""),
    )


def everyone() -> list[Entry]:
    out = [e for e in (load(p.stem) for p in sorted(root().glob("*.json"))) if e]
    # The living first, then the dead, newest first within each.
    out.sort(key=lambda e: (e.status != ALIVE, e.created), reverse=False)
    return out


def _race_name(race_id: str) -> str:
    """The race as the forge shows it, not its id: a card read
    "zhilakai-of-fantasia · Blood Bending 1" (2026-09-07)."""
    from rules import races as races_mod

    doc = races_mod.get(str(race_id or ""))
    return str(doc["name"]) if doc else str(race_id or "")


def enrol(actor: Actor, campaign_id: str = "", world_source: str = "") -> Entry:
    """Put a character on the roster, or return the one already there.

    `campaign_id` stays empty for roster-only creation on purpose: `begin_with` retires
    stale alive-with-campaign-no-turns characters, and a parked character survives that
    sweep only because their campaign_id is blank.
    """
    cid = unique_id(slugify(actor.name))
    entry = Entry(id=cid, name=actor.name, status=ALIVE, sheet=to_dict(actor),
                  campaign_id=campaign_id, world_source=world_source,
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


def revive(character_id: str, actor: Actor) -> Entry | None:
    """Raised, not resurrected from the roster's point of view: the death happened
    and the epitaph stays as history, but the character is playable again."""
    entry = load(character_id)
    if entry is None:
        return None
    entry.status = ALIVE
    entry.sheet = to_dict(actor)
    save(entry)
    return entry


# --- Who is available to play ------------------------------------------------------------

def retire_file(character_id: str) -> tuple[bool, str]:
    """Delete a character, and the game they were playing with them.

    This used to archive: the row left the page and the file moved to
    `characters/archive`, on the argument that a record of a game somebody played
    should not be one misclick from gone. Asked for in as many words to stop —
    "just delete them" — after the archive folders filled with kesst-vayr-2 through
    -7 and the campaigns directory kept twenty saves for a roster of five. The
    confirmation dialog is the guard; the file is not a second one.

    The campaign goes with the character because a save is named for its character
    (`Campaign.path()` is `campaigns/<character id>.json`) and is nothing without
    them: it was the orphaned saves that made the folder unreadable.
    """
    entry = load(character_id)
    if entry is None:
        return False, f"there is no character called {character_id!r}."

    from . import campaign as campaign_mod

    if campaign_mod.current().character_id == character_id:
        return False, (f"{entry.name} is the character you are playing. Switch to "
                       f"somebody else first.")

    path_for(character_id).unlink(missing_ok=True)
    campaign_dir = Path(settings.CAMPAIGN_DIR)
    for save in (character_id, entry.campaign_id):
        if save:
            (campaign_dir / f"{save}.json").unlink(missing_ok=True)
            campaign_mod._LIVE.pop(save, None)
    return True, f"{entry.name} is deleted, and so is their game."


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
            "line": " · ".join(x for x in (actor.heritage, _race_name(actor.race),
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
