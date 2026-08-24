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

from rules import biomes
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import BloodPool, Engine, Scene
from rules.guards import from_dict as guard_from_dict
from rules.sheet import from_dict, load_pc, to_dict
from world.loader import load_cached

SAVE_VERSION = 1


def _grid(raw: dict | None):
    """Rebuild a map from a save, or None for the scenes that never had one.

    Squares arrive from JSON as lists and have to go back to tuples: a list is unhashable
    and every set operation in `rules.grid` would raise, which is a crash at load rather
    than a wrong answer — but only for saves that actually carry terrain, so it would ship
    perfectly happily until the first map with a wall in it.
    """
    if not raw:
        return None
    from rules.grid import Grid

    return Grid(
        width=int(raw.get("width", 20)),
        height=int(raw.get("height", 20)),
        difficult={tuple(p) for p in raw.get("difficult", [])},
        blocked={tuple(p) for p in raw.get("blocked", [])},
        obscuring={tuple(p) for p in raw.get("obscuring", [])},
    )

# The campaign a fresh install starts in, before anyone has been enrolled.
DEFAULT_CAMPAIGN = "slice"

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
    # What the GM proposed last turn, so a turn that simply replays the previous
    # one can be spotted. Stored as a signature rather than the intents themselves:
    # it is only ever compared, never resolved.
    last_intent_signature: list = field(default_factory=list)
    # Which character on the roster is playing this campaign, and whether the
    # campaign has ended with them. A death ends the campaign, not the app.
    character_id: str = ""
    ended: str = ""
    # Chains the player has named and kept, so a working recipe is a thing you build once.
    # Per campaign rather than per character: a recipe is knowledge about the world's
    # ingredients, and it should outlive the herbalist who wrote it down.
    recipes: list[dict] = field(default_factory=list)
    # The two or three things the GM last offered the player. Saved so that closing the
    # app and coming back does not drop the prompts they were looking at. Replaced every
    # turn rather than accumulating — they are a live offer, not a record of one.
    suggestions: list[str] = field(default_factory=list)

    @property
    def world(self):
        return load_cached(self.world_source)

    @property
    def location(self):
        return self.world.get(self.scene.location_id)

    @property
    def biome(self) -> str:
        """The ground underfoot, filled in from the world if the save predates it.

        Healed on read rather than migrated: every campaign written before biomes existed
        has an empty one, and a save that needs a migration step to be playable is a save
        that breaks the moment somebody opens an old one.
        """
        if not self.scene.biome:
            found = biomes.from_world(self.world, self.location)
            self.scene.biome = found[0] if found else "grassland"
        return self.scene.biome

    def engine(self) -> Engine:
        return Engine(self.scene, Dice(self.seed), world=self.world)

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
                # Terrain is stored as lists of squares rather than a dense array: a
                # battlefield is mostly ordinary floor, and a 40x40 map of the word
                # "normal" is 1,600 entries in every save file for no information.
                "grid": None if self.scene.grid is None else {
                    "width": self.scene.grid.width,
                    "height": self.scene.grid.height,
                    "difficult": sorted(self.scene.grid.difficult),
                    "blocked": sorted(self.scene.grid.blocked),
                    "obscuring": sorted(self.scene.grid.obscuring),
                },
                "positions": {r: list(p) for r, p in self.scene.positions.items()},
                # Saved because a fight can be put down mid-round. Losing it would hand
                # everybody a fresh attack of opportunity for reloading.
                "reacted": self.scene.reacted,
                "guards": [g.as_dict() for g in self.scene.guards],
                "pools": [b.as_dict() for b in self.scene.pools],
                "initiative": self.scene.initiative,
                "acted": sorted(self.scene.acted),
                "attacked": sorted(self.scene.attacked),
                "turn": self.scene.turn,
                "sides": self.scene.sides,
                "round": self.scene.round,
                "clock_minutes": self.scene.clock_minutes,
                "biome": self.scene.biome,
                "pending_intents": self.scene.pending_intents,
                "pending_outcomes": self.scene.pending_outcomes,
                "pending_partial": self.scene.pending_partial,
                "awaiting": self.scene.awaiting,
            },
            "history": self.history,
            "transcript": self.transcript,
            "turn_log": self.turn_log,
            "last_intent_signature": self.last_intent_signature,
            "character_id": self.character_id,
            "recipes": self.recipes,
            "suggestions": self.suggestions,
            "ended": self.ended,
        }
        p = self.path()
        p.write_text(json.dumps(payload, indent=1), encoding="utf-8")

        # Keep the roster's copy of the sheet level with the game. Nothing called
        # `roster.record`, so the roster showed every character at the hit points they
        # were created with: Kesst read 9/9 in the "who is playing" list while her save
        # had her at 3, which is exactly the number you are choosing on.
        if self.character_id:
            from . import roster

            pc = self.scene.pc()
            if pc is not None:
                roster.record(self.character_id, pc, turns_played=len(self.turn_log))
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
            grid=_grid(s.get("grid")),
            positions={r: tuple(p) for r, p in (s.get("positions") or {}).items()},
            reacted={k: int(v) for k, v in (s.get("reacted") or {}).items()},
            guards=[guard_from_dict(g) for g in (s.get("guards") or [])],
            pools=[BloodPool.from_dict(b) for b in (s.get("pools") or [])],
            initiative=[tuple(t) for t in s.get("initiative", [])],
            acted=set(s.get("acted", [])),
            attacked=set(s.get("attacked", [])),
            turn=s.get("turn", -1),
            sides={k: list(v) for k, v in (s.get("sides") or {}).items()},
            round=s.get("round", 0),
            clock_minutes=s.get("clock_minutes", 0),
            biome=s.get("biome", ""),
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
            last_intent_signature=[tuple(t) for t in
                                   data.get("last_intent_signature", [])],
            character_id=data.get("character_id", ""),
            recipes=data.get("recipes", []),
            suggestions=list(data.get("suggestions") or []),
            ended=data.get("ended", ""),
        )


# --- The slice's starting situation -------------------------------------------------------

def new_campaign(campaign_id: str = "slice", seed: int | None = None,
                 character=None, world_source=None) -> Campaign:
    """One scene in whatever world is loaded, built from that world's own material.

    Nothing here is invented and nothing here is named. The starting settlement is
    found — `opening.starting_place` takes the smallest inhabited thing the export
    describes — because this file used to hold a literal entity id out of the shipped
    Pangrella fixture, so every other world began nowhere and the opening said so.

    The company is rolled with the situation: whoever the opening puts within speaking
    distance is who the scene starts with, rather than a guildhand on a gate that only
    the fixture's own opening ever mentioned.
    """
    from . import opening

    # The world this campaign is in, which is not necessarily the shipped one. The setting
    # is the default, not the rule: `Campaign` has always carried `world_source` and always
    # loaded from it, and the two lines below were the only thing tying a new game to the
    # export that happens to ship in the box.
    world_source = world_source or settings.WORLD_EXPORT
    world = load_cached(world_source)
    town = opening.starting_place(world)
    scene = Scene(location_id=town.id if town else None)
    # The ground underfoot, read from the world's own facts rather than assumed. The
    # export carries `Biomes`, `Terrain` and `Climate` — Kaelinora's reads "Pangrellan
    # grasslands, Kyropticus deserts" — and they live on the continent, not the town.
    found = biomes.from_world(world, town)
    scene.biome = found[0] if found else "grassland"
    scene.add(character or load_pc(settings.PREGEN_PC), zone="near")
    here = opening.roll(campaign_id, seed)
    scene.add(instantiate(here.template, scene=scene, name=here.who), zone="near")
    return Campaign(
        id=campaign_id, world_source=str(world_source), scene=scene, seed=seed,
    )


def opening_text(campaign: Campaign) -> str:
    """The first thing the player reads. Built in `play/opening.py`, which explains at
    length why it is rolled and why it names nothing the world did not."""
    from . import opening

    return opening.compose(campaign, _standing(campaign.world, campaign.scene.pc()))


def _standing(world, pc) -> str:
    """Who this character is in this city, in a line.

    Read from the export's own facts rather than written once and left. The opening used
    to say "flightless, in a city whose nobility is not" for everybody, which is true of
    Kesst and flatly wrong for a winged Korvu — the app shipped two more characters and
    kept telling them they could not fly.
    """
    people = world.get(pc.world_people_id) if pc.world_people_id else None
    if people is None:
        return f"{pc.heritage or pc.race}, a long way from anyone who knows you"

    origin = people.fact("Origin", "")
    if "flightless" in origin.lower():
        return f"{people.name} — flightless, in a city whose nobility is not"
    if "wing" in people.fact("Anatomy", "").lower():
        return f"{people.name} — winged, in a city that expects you to act like it"
    return f"{people.name} — {origin.rstrip('.').lower()}, and a stranger here"


# --- Live store ---------------------------------------------------------------------------

# One process, one player. The live campaign is held in memory and written to its file
# after every turn, so a crash costs at most the turn in flight.
_LIVE: dict[str, Campaign] = {}


def _pointer() -> Path:
    d = Path(settings.CAMPAIGN_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d / "active.txt"


def active_id() -> str:
    """Which campaign is being played.

    One campaign per character, named for them, so switching characters is switching
    campaigns and each one keeps its own scene, transcript and world state. A character
    you come back to is where you left them rather than at the start of a new game.
    """
    try:
        name = _pointer().read_text(encoding="utf-8").strip()
    except OSError:
        name = ""
    return name or DEFAULT_CAMPAIGN


def set_active(campaign_id: str) -> None:
    _pointer().write_text(campaign_id, encoding="utf-8")


def switch_to(character_id: str) -> Campaign:
    """Play somebody else. Their campaign resumes where it stopped."""
    from . import roster

    entry = roster.load(character_id)
    if entry is None:
        raise LookupError(f"no character {character_id!r}")
    if entry.status == roster.DEAD:
        raise ValueError(f"{entry.name} is dead")

    # A character's campaign is the one their roster entry names. Assuming it was named
    # after them was very nearly true and quietly wrong: Kesst's real game lived in
    # `slice.json` from before campaigns were per-character, so switching to her opened a
    # brand new `kesst-vayr` campaign at full hit points and left the played one behind.
    # `campaign_id` is the record of which campaign is hers; the id is not.
    campaign_id = entry.campaign_id or character_id
    set_active(campaign_id)
    if campaign_id not in _LIVE and not _save_path(campaign_id).exists():
        # Enrolled but never played — begin their campaign now, without enrolling them
        # a second time.
        c = new_campaign(campaign_id, character=entry.actor)
        c.character_id = character_id
        c.transcript.append({"who": "gm", "text": opening_text(c)})
        c.save()
        _LIVE[campaign_id] = c
        if not entry.campaign_id:
            entry.campaign_id = campaign_id
            roster.save(entry)
    if entry.status == roster.RETIRED:
        entry.status = roster.ALIVE
        roster.save(entry)

    c = current(campaign_id)
    # Saving on the way in is what brings the roster's copy of the sheet up to date (see
    # `Campaign.save`). Without it a character carried on being listed at the hit points
    # they were created with until they next took a turn — so the list you pick from was
    # wrong at exactly the moment you were reading it.
    c.save()
    return c


def _save_path(campaign_id: str) -> Path:
    return Campaign(id=campaign_id, world_source="", scene=Scene()).path()


def current(campaign_id: str | None = None, reset: bool = False) -> Campaign:
    """The campaign in play, resumed from disk if it is not already in memory.

    Reading the save back was missing, and the consequence was not merely that a restart
    forgot the game: `new_campaign` immediately called `save()`, so restarting the server
    *overwrote* the campaign with a fresh one. A session could not survive the app being
    closed, which is not a game anyone can run.
    """
    campaign_id = campaign_id or active_id()
    if reset:
        _LIVE.pop(campaign_id, None)
        path = Campaign(id=campaign_id, world_source="", scene=Scene()).path()
        if path.exists():
            _retire_outgoing(path)
            # An explicit new game archives the old one rather than deleting it. Saves
            # are cheap and losing a campaign to a stray ?new=1 is not recoverable.
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            path.rename(path.with_name(f"{campaign_id}-{stamp}.json"))

    if campaign_id not in _LIVE:
        c = _resume(campaign_id) or _begin(campaign_id)
        _LIVE[campaign_id] = c
    return _LIVE[campaign_id]


def _retire_outgoing(path: Path) -> None:
    """Mark the character of a campaign being replaced as retired.

    Without this every `?new=1` left another living copy on the roster — three identical
    Kessts, all alive, none being played. The dead are kept because they are a record;
    an abandoned character is not the same thing, and saying so keeps the roster honest.
    """
    from . import roster

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    cid = data.get("character_id")
    if not cid:
        return
    entry = roster.load(cid)
    if entry and entry.status == roster.ALIVE:
        entry.status = roster.RETIRED
        roster.save(entry)


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


def _begin(campaign_id: str, character=None) -> Campaign:
    from . import roster

    c = new_campaign(campaign_id, character=character)
    entry = roster.enrol(c.scene.pc(), campaign_id)
    c.character_id = entry.id
    c.transcript.append({"who": "gm", "text": opening_text(c)})
    c.save()
    return c


def begin_with(character, world_source=None) -> Campaign:
    """Start a campaign for a new character.

    Named for them, so it sits alongside everyone else's rather than replacing whoever
    was in the one shared slot. Nothing is archived and nothing is lost: the character
    you were playing keeps their campaign, and you can go back to it.
    """
    from . import roster

    # An abandoned start is not a life lived. Beginning a game and thinking better of
    # it before taking a single turn used to leave a permanent living row, and a shelf
    # of identical unplayed characters is what made a roster of seven Kessts unreadable.
    # Retired rather than deleted, which is the answer this module already gives for the
    # character a reset replaces — nothing is lost, and the record stops pretending
    # somebody is waiting to be played.
    #
    # A *started* game is the whole condition. The first cut of this swept every alive
    # character with no turns on them, which quietly retired the ones the player had
    # deliberately built and parked with "Create for the roster" — they have no
    # campaign because they are waiting for one, not because they were walked out on.
    for stale in roster.everyone():
        if stale.status == roster.ALIVE and stale.campaign_id and not stale.turns_played:
            stale.status = roster.RETIRED
            roster.save(stale)

    entry = roster.enrol(character)
    c = new_campaign(entry.id, character=character, world_source=world_source)
    c.character_id = entry.id
    entry.campaign_id = entry.id
    roster.save(entry)
    c.transcript.append({"who": "gm", "text": opening_text(c)})
    c.save()
    _LIVE[entry.id] = c
    set_active(entry.id)
    return c
