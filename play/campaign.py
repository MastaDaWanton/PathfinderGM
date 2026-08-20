"""The campaign overlay.

The World Bible export stays pristine source of truth; everything play changed lives here,
keyed by the export's durable entity ids. So the same world can host several campaigns,
and re-exporting a world never clobbers one.

A file, not a database — readable in a text editor, and no migrations to run inside a
frozen app.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from django.conf import settings

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from world.loader import load_cached

SAVE_VERSION = 1

# The town of Pangrella in the shipped export, by durable id. Not by name: the world is
# also called Pangrella.
PANGRELLA_TOWN = "5bbd0c40345f"


@dataclass
class Campaign:
    id: str
    world_source: str
    scene: Scene
    history: list[dict] = field(default_factory=list)   # the GM's own message history
    transcript: list[dict] = field(default_factory=list)  # what the player sees
    turn_log: list[dict] = field(default_factory=list)   # every roll, auditable
    seed: int | None = None

    @property
    def world(self):
        return load_cached(self.world_source)

    @property
    def location(self):
        return self.world.get(self.scene.location_id)

    def engine(self) -> Engine:
        return Engine(self.scene, Dice(self.seed))

    # --- persistence ------------------------------------------------------------------

    def path(self) -> Path:
        d = Path(settings.CAMPAIGN_DIR)
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{self.id}.json"

    def save(self) -> Path:
        # Version-stamped because this file lives in the user data directory and outlives
        # every reinstall — the trap that served a five-day-old stylesheet across four
        # versions of World Bible.
        payload = {
            "save_version": SAVE_VERSION,
            "id": self.id,
            "world_source": str(self.world_source),
            "seed": self.seed,
            "scene": {
                "location_id": self.scene.location_id,
                "actors": {r: to_dict(a) for r, a in self.scene.actors.items()},
                "zones": self.scene.zones,
                "initiative": self.scene.initiative,
                "acted": sorted(self.scene.acted),
                "turn": self.scene.turn,
                "sides": self.scene.sides,
                "round": self.scene.round,
                "clock_minutes": self.scene.clock_minutes,
                "pending_intents": self.scene.pending_intents,
                "pending_outcomes": self.scene.pending_outcomes,
                "pending_partial": self.scene.pending_partial,
                "awaiting": self.scene.awaiting,
            },
            "history": self.history,
            "transcript": self.transcript,
            "turn_log": self.turn_log,
        }
        p = self.path()
        p.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: Path) -> "Campaign":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("save_version") != SAVE_VERSION:
            raise ValueError(
                f"{path.name}: save version {data.get('save_version')}, this build "
                f"writes {SAVE_VERSION}"
            )
        s = data["scene"]
        scene = Scene(
            location_id=s.get("location_id"),
            zones=s.get("zones", {}),
            initiative=[tuple(t) for t in s.get("initiative", [])],
            acted=set(s.get("acted", [])),
            turn=s.get("turn", -1),
            sides={k: list(v) for k, v in (s.get("sides") or {}).items()},
            round=s.get("round", 0),
            clock_minutes=s.get("clock_minutes", 0),
            pending_intents=s.get("pending_intents", []),
            pending_outcomes=s.get("pending_outcomes", []),
            pending_partial=s.get("pending_partial", {}),
            awaiting=s.get("awaiting"),
        )
        for ref, a in s.get("actors", {}).items():
            scene.actors[ref] = from_dict(a, ref=ref)
        return cls(
            id=data["id"], world_source=data["world_source"], scene=scene,
            history=data.get("history", []), transcript=data.get("transcript", []),
            turn_log=data.get("turn_log", []), seed=data.get("seed"),
        )


# --- The slice's starting situation -------------------------------------------------------

def new_campaign(campaign_id: str = "slice", seed: int | None = None) -> Campaign:
    """One scene in Pangrella, built from the world's own material.

    Nothing here is invented: Pangrella is the export's home town, its `Shadow Power`
    fact names the Zhilakai minority, its standing `Tension` is the winged nobility
    against the merchant castes, and the PC is Zhilakai. The situation is the friction
    the world already documents, not a premise bolted on top of it.
    """
    world = load_cached(settings.WORLD_EXPORT)
    # By id, not by name: the WORLD and this CITY are both called "Pangrella", so the
    # name lookup returns the planet and the opening scene is set nowhere.
    town = world.get(PANGRELLA_TOWN) or world.by_name("Pangrella", kind="CITY")
    scene = Scene(location_id=town.id if town else None)
    scene.add(load_pc(settings.PREGEN_PC), zone="near")
    scene.add(
        instantiate("guildhand", scene=scene, name="the guildhand on the gate"),
        zone="near",
    )
    return Campaign(
        id=campaign_id, world_source=str(settings.WORLD_EXPORT), scene=scene, seed=seed,
    )


def opening_text(campaign: Campaign) -> str:
    loc = campaign.location
    pc = campaign.scene.pc()
    return (
        f"{loc.name}, after dark. {loc.fact('Architecture')} "
        f"The guild yard is shut for the night, and there is a lamp on a chain over the "
        f"wall.\n\n"
        f"You are {pc.name} — {pc.heritage}, flightless, in a city whose nobility is not. "
        f"What do you do?"
    )


# --- Live store ---------------------------------------------------------------------------

# One process, one player. The live campaign is held in memory and written to its file
# after every turn, so a crash costs at most the turn in flight.
_LIVE: dict[str, Campaign] = {}


def current(campaign_id: str = "slice", reset: bool = False) -> Campaign:
    """The campaign in play, resumed from disk if it is not already in memory.

    Reading the save back was missing, and the consequence was not merely that a restart
    forgot the game: `new_campaign` immediately called `save()`, so restarting the server
    *overwrote* the campaign with a fresh one. A session could not survive the app being
    closed, which is not a game anyone can run.
    """
    if reset:
        _LIVE.pop(campaign_id, None)
        path = Campaign(id=campaign_id, world_source="", scene=Scene()).path()
        if path.exists():
            # An explicit new game archives the old one rather than deleting it. Saves
            # are cheap and losing a campaign to a stray ?new=1 is not recoverable.
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            path.rename(path.with_name(f"{campaign_id}-{stamp}.json"))

    if campaign_id not in _LIVE:
        c = _resume(campaign_id) or _begin(campaign_id)
        _LIVE[campaign_id] = c
    return _LIVE[campaign_id]


def _resume(campaign_id: str) -> Campaign | None:
    path = Campaign(id=campaign_id, world_source="", scene=Scene()).path()
    if not path.exists():
        return None
    try:
        return Campaign.load(path)
    except Exception as exc:
        # A save this build cannot read is set aside rather than overwritten. The player
        # keeps the file; the app keeps working.
        broken = path.with_name(f"{campaign_id}-unreadable-"
                                f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
        path.rename(broken)
        print(f"[campaign] could not read {path.name}: {exc}; moved to {broken.name}")
        return None


def _begin(campaign_id: str) -> Campaign:
    c = new_campaign(campaign_id)
    c.transcript.append({"who": "gm", "text": opening_text(c)})
    c.save()
    return c
