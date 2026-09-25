"""The campaign overlay.

The World Bible export stays pristine source of truth; everything play changed lives here,
keyed by the export's durable entity ids. So the same world can host several campaigns,
and re-exporting a world never clobbers one.

A file, not a database — readable in a text editor, and no migrations to run inside a
frozen app.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from django.conf import settings

from pathfindergm import files
from rules import biomes
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import BloodPool, Engine, Manifestation, Scene, Ward
from rules.guards import from_dict as guard_from_dict
from rules.sheet import from_dict, load_pc, to_dict
from world.loader import load_cached

# 2: actors are saved as `people`, each with the place it stands in, and `minted` (the
# ref high-water mark) rides along. Bumped rather than left at 1 because an older build
# opening a `people` save would read `actors` as empty and hand the player a dead game
# with no sentence naming the cause; with the version refused, the sentence is there.
SAVE_VERSION = 2

# The saves kept beside each campaign, newest first: `<id>.json.1` is the turn before.
BACKUPS_KEPT = 3


class NewerSave(ValueError):
    """The save was written by a newer build. Not damage: refused, never restored.

    Measured the day backups arrived (2026-09-25): `test_a_save_from_an_older_build_still
    _opens` caught the first cut "restoring" a version-3 save from its version-2 backup —
    rolling the player's newer game back a turn and setting it aside, when the only right
    answer is "update the app"."""


class UnreadableSave(RuntimeError):
    """A campaign file exists and this build cannot read it.

    Raised rather than handled, because the only alternative the code had was to rename
    the save and start a new game over it — which is what it did, silently, for every
    kind of load failure. A campaign is the most valuable thing in the user's data
    directory and the least replaceable; the app may refuse to open one, and may never
    decide on the player's behalf that it is gone.
    """


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
        floor={tuple(int(n) for n in k.split(",")): int(v)
               for k, v in (raw.get("floor") or {}).items()},
        ceiling=raw.get("ceiling"),
        parapet={tuple(int(n) for n in k.split(",")): int(v)
                 for k, v in (raw.get("parapet") or {}).items()},
    )

def _portable_world_source(source: str | Path) -> str:
    """The form of a world path that survives a relaunch.

    A frozen onefile app extracts its bundle to a per-launch temp dir (_MEIxxxxx)
    that dies with the process. Three live saves carried world_source anchored
    there, and the home page 500'd on every launch after the one that wrote them —
    the derived-cache trap, as an absolute path. Anything under the bundle is
    stored relative to it; everything else (imported worlds in the data dir) keeps
    its absolute path, which is stable.
    """
    from pathfindergm.paths import resource_root

    p = Path(source)
    try:
        return p.relative_to(resource_root()).as_posix()
    except ValueError:
        return str(p)


def _resolve_world_source(source: str | Path) -> Path:
    """The path to actually open, healed on read like `biome` is.

    Relative means bundled — anchored to this launch's resource root. An absolute
    path that no longer exists but points through a _MEI dir is a poisoned save
    from before paths were stored portably: re-anchor its tail onto the current
    bundle rather than asking anyone to migrate a save by hand.
    """
    from pathfindergm.paths import resource_root

    p = Path(source)
    if not p.is_absolute():
        return resource_root() / p
    if not p.exists():
        parts = p.parts
        for i, part in enumerate(parts):
            if part.startswith("_MEI"):
                return resource_root().joinpath(*parts[i + 1:])
    return p


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
    # What happened in the turns the context budget has since cut. Built from the
    # engine's own outcomes, written once per turn and never rewritten, and holding
    # no numbers at all — see gm/ledger.py and docs/memory-policy.md.
    ledger: list[dict] = field(default_factory=list)
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
        return load_cached(_resolve_world_source(self.world_source))

    @property
    def location(self):
        return self.world.get(self.scene.location_id)

    @property
    def biome(self) -> str:
        """The ground underfoot: a parse of the party's place, never a stored field.

        This was a read that WROTE — it healed a stored `scene.biome` from the world —
        and the home page reached it, so rendering a list of campaigns could rewrite
        one. The place id carries its ground now and `load` stands an old save
        somewhere real; there is nothing left here to heal.
        """
        return self.scene.biome

    def engine(self) -> Engine:
        return Engine(self.scene, Dice(self.seed), world=self.world)

    # --- persistence ------------------------------------------------------------------

    def path(self) -> Path:
        d = Path(settings.CAMPAIGN_DIR)
        d.mkdir(parents=True, exist_ok=True)
        return files.child(d, self.id)

    def save(self) -> Path:
        # Version-stamped because this file lives in the user data directory and outlives
        # every reinstall — the trap that served a five-day-old stylesheet across four
        # versions of World Bible.
        payload = {
            "save_version": SAVE_VERSION,
            "id": self.id,
            "world_source": _portable_world_source(self.world_source),
            "seed": self.seed,
            "scene": {
                "location_id": self.scene.location_id,
                # THE STORE, not the view: an actor in the next room is still an actor
                # in the campaign. Each carries `at`.
                "people": {r: to_dict(a) for r, a in self.scene.people.items()},
                "minted": self.scene.minted,
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
                    # The heightmap and the roof. Sparse like the terrain sets, and
                    # saved rather than re-derived: `floorplan` laid the room, but a
                    # spell can raise ground and a fight can knock a roof in, so what
                    # is on the board at the end of a round is not always what the
                    # plan said. A save that dropped these gave a flier unlimited air
                    # on reload and quietly took away everybody's higher ground.
                    "floor": {f"{x},{y}": v for (x, y), v in self.scene.grid.floor.items()},
                    "ceiling": self.scene.grid.ceiling,
                    "parapet": {f"{x},{y}": v
                                for (x, y), v in self.scene.grid.parapet.items()},
                },
                "positions": {r: list(p) for r, p in self.scene.positions.items()},
                # Saved because a fight can be put down mid-round. Losing it would hand
                # everybody a fresh attack of opportunity for reloading.
                "reacted": self.scene.reacted,
                "guards": [g.as_dict() for g in self.scene.guards],
                "pools": [b.as_dict() for b in self.scene.pools],
                # The standing hazards. Both of these had as_dict and from_dict written
                # and NEITHER was ever called by anything: a save/reload mid-fight
                # silently deleted every fog cloud, wall of stone, thorn body and bleed
                # ward in the scene, while the grid kept the squares they had claimed.
                "wards": [w.as_dict() for w in self.scene.wards],
                "manifests": [m.as_dict() for m in self.scene.manifests],
                "initiative": self.scene.initiative,
                "acted": sorted(self.scene.acted),
                "attacked": sorted(self.scene.attacked),
                "turn": self.scene.turn,
                "sides": self.scene.sides,
                "round": self.scene.round,
                "clock_minutes": self.scene.clock_minutes,
                "thread": dict(self.scene.thread),
                "cast": [dict(e) for e in self.scene.cast],
                "props": [dict(e) for e in self.scene.props],
                "fallen": dict(self.scene.fallen),
                "heat": dict(self.scene.heat),
                "market_taken": self.scene.market_taken,
                # Written by `spawn` and read by `begin_encounter`, which is the next
                # turn — so the one field whose entire life spans a turn boundary was
                # the one the save dropped. A restart between the ambush being set up
                # and the fight starting put every archer back at the forty-foot
                # default, however far the spawn said they were.
                "spawn_feet": self.scene.spawn_feet,
                "rewarded": dict(self.scene.rewarded),
                "guarded_finds": [dict(g) for g in self.scene.guarded_finds],
                "cards": [dict(c) for c in self.scene.cards],
                "said": dict(self.scene.said),
                "founded": [dict(f) for f in self.scene.founded],
                "schemes": [dict(s) for s in self.scene.schemes],
                # Which counters already have somebody behind them. Absent in saves
                # written before keepers, which reads as none staffed yet — so an old
                # campaign gains its smith the next time the party stands in the smithy.
                "staffed": list(self.scene.staffed),
                # And when each of them was last talked round: a 24-hour limit that
                # forgot itself on reload would be no limit at all.
                "swayed": dict(self.scene.swayed),
                # A hull does not heal and a chase does not reset: both survive a reload.
                "vessels": [dict(v) for v in self.scene.vessels],
                "sea": dict(self.scene.sea),
                # How much of an interrupted road is still to walk.
                "road": dict(self.scene.road),
                # WHICH place they are standing in, by id. The list of places is
                # derived (rules.places.spots_for is deterministic and seeded off the
                # location's own id), so there is nothing else here to save and no way
                # for a stored list to drift from the generator that made it.
                "at": self.scene.at,
                "pending_intents": self.scene.pending_intents,
                "pending_outcomes": self.scene.pending_outcomes,
                "pending_partial": self.scene.pending_partial,
                "awaiting": self.scene.awaiting,
            },
            "history": self.history,
            "transcript": self.transcript,
            "turn_log": self.turn_log,
            "ledger": self.ledger,
            "last_intent_signature": self.last_intent_signature,
            "character_id": self.character_id,
            "recipes": self.recipes,
            "suggestions": self.suggestions,
            "ended": self.ended,
        }
        p = self.path()
        # Serialised BEFORE anything on disk moves, so a payload that cannot be written
        # (a set where a list belongs) raises with the last save and its backups intact.
        text = json.dumps(payload, indent=1)
        # The save that was whole becomes `.json.1` (then .2, .3), and the new one lands
        # by rename, never by truncating the only copy — see pathfindergm/files.py.
        files.keep_backup(p, keep=BACKUPS_KEPT)
        files.write_text(p, text)

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
        # Older is read; only NEWER is refused. Written `!=`, this made every save-shape
        # change unshippable: bumping SAVE_VERSION would have declared all twelve of the
        # user's existing campaigns unreadable at once, and the recovery path below used
        # to answer that by renaming them and starting a new game. A save from a future
        # build is the one case that genuinely cannot be read, because this code does not
        # know what is in it.
        found = data.get("save_version")
        try:
            found_n = int(found)
        except (TypeError, ValueError):
            found_n = 0
        if found_n > SAVE_VERSION:
            raise NewerSave(
                f"{path.name}: save version {found}, and this build writes "
                f"{SAVE_VERSION}. The campaign was saved by a newer version of "
                f"Pathfinder GM — update the app to open it."
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
            # Constructed directly and appended, never through `Scene.place`. The grid
            # is saved with the fog's squares ALREADY in `grid.obscuring`, so place()
            # would recompute `added` as empty and `lift()` would then leave the room
            # permanently opaque with no fog in it to explain why. The ids are kept for
            # the same class of reason: `Ward.manifest_id` points at them, and re-minting
            # would silently detach every area ward — `_aimed_at` would return nobody
            # and the hazard would fire on no one, with nothing reported.
            wards=[w for w in (Ward.from_dict(x) for x in (s.get("wards") or []))
                   if w is not None],
            manifests=[Manifestation.from_dict(x)
                       for x in (s.get("manifests") or [])],
            initiative=[tuple(t) for t in s.get("initiative", [])],
            acted=set(s.get("acted", [])),
            attacked=set(s.get("attacked", [])),
            turn=s.get("turn", -1),
            sides={k: list(v) for k, v in (s.get("sides") or {}).items()},
            round=s.get("round", 0),
            clock_minutes=s.get("clock_minutes", 0),
            thread=dict(s.get("thread") or {}),
            cast=[dict(e) for e in (s.get("cast") or [])],
            # Absent in saves written before things had records: nothing lies anywhere.
            props=[dict(e) for e in (s.get("props") or [])],
            fallen={str(k): int(v) for k, v in (s.get("fallen") or {}).items()},
            heat=dict(s.get("heat") or {}),
            # Absent in saves written before shops had shelves: an empty ledger means
            # nothing has been bought today, which is the right answer for them.
            market_taken={str(k): int(v)
                          for k, v in (s.get("market_taken") or {}).items()},
            spawn_feet={str(k): int(v)
                        for k, v in (s.get("spawn_feet") or {}).items()},
            rewarded={str(k): int(v) for k, v in (s.get("rewarded") or {}).items()},
            guarded_finds=[dict(g) for g in (s.get("guarded_finds") or [])],
            cards=[dict(c) for c in (s.get("cards") or [])],
            # Absent in saves written before the pools were walked: an empty record
            # means the first line of each pool is next, which is where a new campaign
            # starts too.
            said=dict(s.get("said") or {}),
            founded=[dict(f) for f in (s.get("founded") or [])],
            schemes=[dict(x) for x in (s.get("schemes") or [])],
            staffed=[str(x) for x in (s.get("staffed") or [])],
            swayed={str(k): int(v) for k, v in (s.get("swayed") or {}).items()},
            vessels=[dict(v) for v in (s.get("vessels") or [])],
            sea=dict(s.get("sea") or {}),
            road=dict(s.get("road") or {}),
            at=str(s.get("at") or ""),
            minted=int(s.get("minted", 0) or 0),
            pending_intents=s.get("pending_intents", []),
            pending_outcomes=s.get("pending_outcomes", []),
            pending_partial=s.get("pending_partial", {}),
            awaiting=s.get("awaiting"),
        )
        # `people` from a version-2 save, `actors` from a version-1 one. Straight into
        # the store rather than through `add`, because `add` stamps the party's place
        # and the zone, and both were saved. An actor whose dict has NO `at` key was
        # saved before places existed and is healed below; empty is not absent.
        unplaced: list[str] = []
        for ref, a in (s.get("people") or s.get("actors") or {}).items():
            scene.people[ref] = from_dict(a, ref=ref)
            if "at" not in a:
                unplaced.append(ref)
        # The mark heals to the highest ref the save holds ANYWHERE a ref is keyed —
        # a stale `fallen` age or a cast entry can name a ref the store no longer
        # does, and minting it again is the poisoning this exists to end.
        seen = set(scene.people) | set(scene.fallen) | set(scene.spawn_feet) | {
            str(e.get("ref")) for e in scene.cast if e.get("ref")}
        highest = 0
        for r in seen:
            m = re.fullmatch(r"c(\d+)", str(r))
            if m:
                highest = max(highest, int(m.group(1)))
        scene.minted = max(scene.minted, highest)
        campaign = cls(
            id=data["id"], world_source=data["world_source"], scene=scene,
            history=data.get("history", []), transcript=data.get("transcript", []),
            turn_log=data.get("turn_log", []), ledger=data.get("ledger", []),
            seed=data.get("seed"),
            last_intent_signature=[tuple(t) for t in
                                   data.get("last_intent_signature", [])],
            character_id=data.get("character_id", ""),
            recipes=data.get("recipes", []),
            suggestions=list(data.get("suggestions") or []),
            ended=data.get("ended", ""),
        )
        campaign._heal_places(str(s.get("biome") or ""), unplaced)
        return campaign

    def _heal_places(self, stored_biome: str, unplaced: list[str]) -> None:
        """A save from before actors had a place, stood somewhere real.

        Healed on read rather than migrated, the same courtesy `biome` extended to
        saves written before biomes existed. Needs the world, which is why it runs
        here and not inside `load`. The rule: an unplaced scene whose stored biome was
        the settlement's own ground (or nothing) is at the settlement's first place;
        one that had walked onto other ground is at that region's first place. Then
        everyone the save did not place is stood with the party.
        """
        from rules import places as places_mod

        try:
            engine = self.engine()
            if not self.scene.at:
                known = engine.places()
                home_ground = known[0].terrain
                if stored_biome and stored_biome != home_ground and known[0].id != "here":
                    where = places_mod.region_set(
                        places_mod.location_of(known[0].id), stored_biome)[0].id
                else:
                    where = known[0].id
                engine.place_party(where)
            else:
                engine.place_party(self.scene.at)
        except Exception:
            # A world that will not load is reported by whoever asked for it; the
            # party is not left nowhere on the way to that sentence. Everyone the save
            # did not place is stood with the party by `place_party`, which is the
            # one door outside `Scene` that writes an actor's place.
            if not self.scene.at:
                self.scene.at = "here"
        del unplaced


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
    # Placed, not biomed: the ground is inside the place id and a new campaign stands
    # at its town's first place. The PC first, then the party is placed, THEN the
    # company — `Scene.add` stamps whoever arrives with the party's place, and the
    # review found the other order left the opening companion standing nowhere.
    scene.add(character or load_pc(settings.PREGEN_PC), zone="near")
    Engine(scene, Dice(seed), world=world).place_party()
    here = opening.roll(campaign_id, seed)
    watcher = scene.add(instantiate(here.template, scene=scene, name=here.who), zone="near")
    c = Campaign(
        id=campaign_id, world_source=str(world_source), scene=scene, seed=seed,
    )
    # The situation cards the game starts with (`rules/cards.py`): the errand the
    # player is standing in, always on; and the world's own — its author's, when
    # World Bible ships some, and the ones every export implies: the starting
    # settlement's strain, and each unwritten hook as the GM's secret card.
    from rules import cards as cards_mod

    pc = scene.pc()
    cards_mod.open_card(scene, cards_mod.from_opening(
        here, scene.at, watcher.ref, pc.name if pc is not None else ""))
    for card in cards_mod.from_world(world, scene.at):
        cards_mod.open_card(scene, card)
    # The campaign's opening undercurrent — the first world-state this app has ever
    # actually held. Rolled from the world's own unwritten hooks when it has them,
    # from a world-agnostic table when it does not, and planted in history as the
    # GM's private note so it rides every turn's context from turn one without a
    # single prompt-builder signature changing. The framing lives in
    # `opening.private_note` because `gm/watcher.py` rewrites this entry in place and
    # finds it by its prefix — two copies of the wrapper is how the search misses one.
    thread = opening.undercurrent(world, seed)
    if thread:
        c.history.append({"role": "user", "content": opening.private_note(thread)})
    return c


def _open_with(c: Campaign, opened: tuple[str, list[str]]) -> None:
    """The opening onto the page AND into the model's history.

    It went onto the page only, and the consequence was measured on the player's own
    first turn, 2026-09-05: their save's history read private note, then "I ask what
    is going on" — no step in the sun, no market, no stranger — and the prose model,
    shown nothing of the scene it was continuing, wrote the nearest scene it had
    been shown, which was worked example eleven's door. The narrator continues what
    is in front of it; the opening has to be in front of it.
    """
    text, suggestions = opened
    # `kind: "setup"`: the opening is the narrator's own prose, and `narration.own_prose`
    # — what the prose call is shown as "what you narrated just before this" — keeps
    # only setup beats. Without the kind the first turn continued from nothing.
    beat = {"who": "gm", "text": text, "kind": "setup"}
    record = getattr(c, "_opening_record", None)
    if record:
        # Why the first screen read as it did, on the beat it describes.
        beat["opening"] = dict(record)
        c._opening_record = None
    c.transcript.append(beat)
    c.history.append({"role": "assistant", "content": text})
    # The opening's own "you could": the page shows them as it shows a turn's, so
    # the first screen already has three things to press.
    c.suggestions = list(suggestions or [])


def opening_text(campaign: Campaign, written: bool = True) -> tuple[str, list[str]]:
    """The first thing the player reads.

    The template in `play/opening.py` is the material and the floor; the prose model
    writes the screen from the place's own paragraphs and is checked against them
    (`play/opening_prose.py`), and a draft that fails its checks twice is dropped for
    the template. What was wrong with the last draft is logged, because a floor that
    is reached silently is a floor nobody notices being reached.

    `written=False` is for the game nobody asked for: `_begin` enrols the shipped
    pregen when there is no save at all, from the home page's own request, and a
    home page that waits on a cold 12B model to draw the shelf is the hung home page
    of this morning over again.
    """
    import logging

    from . import opening, opening_prose

    here = opening.situation_for(campaign)
    skeleton = opening.compose(campaign, _standing(campaign.world, campaign.scene.pc()))
    could = opening.suggestions_for(here)
    if not written:
        return skeleton, could
    text, suggestions, wrong = opening_prose.write(campaign, here, skeleton, could)
    floor = text.strip() == skeleton.strip()
    if wrong:
        logging.getLogger(__name__).warning(
            "opening fell back to the template: %s" if floor
            else "opening shipped with soft problems: %s", "; ".join(wrong))
    # On the save as well as in the log. Measured 2026-09-18: a player's opening fell
    # to the template and the only trace was one warning line in the app log, which a
    # save file cannot carry to whoever is asked "why was this so short". Handed to
    # `_open_with` for the opening beat itself rather than written to `turn_log`: an
    # entry there is a turn played, and a start with one is no longer the abandoned
    # start `begin_with` retires (test_an_abandoned_start_is_retired_when_the_next_
    # game_begins caught the first version).
    campaign._opening_record = {"floor": floor, "chars": len(text),
                                "problems": list(wrong)}
    return text, suggestions


def _standing(world, pc) -> str:
    """Who this character is in this city, in a line.

    Read from the export's own facts rather than written once and left. The opening used
    to say "flightless, in a city whose nobility is not" for everybody, which is true of
    Kesst and flatly wrong for a winged Korvu — the app shipped two more characters and
    kept telling them they could not fly.
    """
    # Somebody with a bound past is not "a long way from anyone who knows you": the
    # binding names who knows them and from what. Reported 2026-09-18 — "I chose
    # pit-fighter as my background but there is no mention of that and still nobody
    # knows me?" — on a save whose ties read "You fought where Drenn Ironvale took the
    # bets, near the market, and drew a crowd." The 09-15 fix bound the ties and the
    # turn brief reads them; the opening's template and material never did.
    known = bool(getattr(pc, "background_ties", None))
    people = world.get(pc.world_people_id) if pc.world_people_id else None
    if people is None:
        return (f"{pc.heritage or pc.race}"
                + ("" if known else ", a long way from anyone who knows you"))

    origin = people.fact("Origin", "")
    if "flightless" in origin.lower():
        return f"{people.name} — flightless, in a city whose nobility is not"
    if "wing" in people.fact("Anatomy", "").lower():
        return f"{people.name} — winged, in a city that expects you to act like it"
    return (f"{people.name} — {origin.rstrip('.').lower()}"
            + ("" if known else ", and a stranger here"))


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
    files.write_text(_pointer(), campaign_id)


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
        # a second time. In the world they were made for: this call passed no
        # world_source, so a character parked from an imported world's forge began in
        # the shipped default when finally played. Empty still means the default, which
        # is what every entry written before the field existed carries.
        c = new_campaign(campaign_id, character=entry.actor,
                         world_source=entry.world_source or None)
        c.character_id = character_id
        open_the_story(c)
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


def forget_live() -> None:
    """Drop every campaign held in memory; the next request reads its save back.

    The answer to a request that failed half-way (`concurrency.OneGameAtATime`): the save
    on disk is always a consistent point, the memory copy after a crash is not."""
    _LIVE.clear()


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
            # A second reset inside the same second collided with the first archive's
            # name, and `rename` onto an existing file raises on Windows — a 500.
            archive = path.with_name(f"{campaign_id}-{stamp}.json")
            n = 2
            while archive.exists():
                archive = path.with_name(f"{campaign_id}-{stamp}-{n}.json")
                n += 1
            # The backups go with the game they are backups OF. Left under the old
            # name, the next campaign to take this id would inherit them, and a failed
            # load would "restore" the archived game over the new one.
            for kept in files.backups(path, keep=BACKUPS_KEPT):
                suffix = kept.name[len(path.name):]
                kept.replace(archive.with_name(archive.name + suffix))
            path.rename(archive)

    if campaign_id not in _LIVE:
        # `_resume` returns None only when there is genuinely no save to read; a save
        # that exists and cannot be read raises, and that raise travels rather than
        # falling through to `_begin`. `_begin` saves immediately, so the old
        # `_resume(...) or _begin(...)` turned every load failure into a new character
        # written over the campaign that failed to load.
        c = _resume(campaign_id) or _begin(campaign_id)
        _heal_background(c)
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


def _restore_from_backup(path: Path, why: Exception) -> Campaign | None:
    """Open the newest backup of `path` that reads, put it in place, and say so.

    Measured 2026-09-25: the save was written by truncate-then-write and had no copy,
    so a campaign cut off mid-write was an `UnreadableSave` with nothing behind it.
    """
    import logging
    import shutil

    for backup in files.backups(path, keep=BACKUPS_KEPT):
        try:
            c = Campaign.load(backup)
        except Exception:
            continue
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        aside = path.with_name(f"{path.name}.unreadable-{stamp}")
        try:
            path.replace(aside)
            shutil.copy2(backup, path)
        except OSError:
            return None
        logging.getLogger("pathfindergm").warning(
            "%s could not be read (%s); restored from %s, the unreadable file kept as %s",
            path.name, why, backup.name, aside.name)
        c.transcript.append({
            "who": "gm", "kind": "aside",
            "text": ("Your last save could not be read, so the game has been restored "
                     "from the one before it. The unreadable file was kept beside it as "
                     f"{aside.name}."),
        })
        return c
    return None


def _resume(campaign_id: str) -> Campaign | None:
    path = Campaign(id=campaign_id, world_source="", scene=Scene()).path()
    if not path.exists():
        return None
    try:
        return Campaign.load(path)
    except Exception as exc:
        # The last save that was whole, when there is one. The unreadable file is moved
        # aside, never deleted — the refusal below still stands for the case where no
        # backup reads either, and nothing is repaired behind the player's back: the
        # restored game opens with a line saying what happened and which turn it is.
        # Only a DAMAGED file — one that no longer parses — is restored. A save that
        # parses and fails the rules (a homebrew class edited under its character) is
        # not damage: its backups hold the same character and would fail the same way,
        # and rolling the game back a turn to find one that passed would be exactly the
        # repair behind the player's back that test_the_shelf_survives_a_bad_save
        # forbids. A newer build's save is not damage either.
        damaged = isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError))
        restored = _restore_from_backup(path, exc) if damaged else None
        if restored is not None:
            return restored
        # The save is left exactly where it is, and the failure is raised rather than
        # swallowed. This used to rename the file and return None, and `current()`
        # answers None by calling `_begin`, which immediately saves — so ANY error on
        # the load path (a new key, a validate() failure, a half-written file, a typo)
        # cost the player their campaign and replaced it with a fresh character, with
        # nothing on screen saying so. The old comment claimed "the player keeps the
        # file; the app keeps working": the first half was true of a renamed file
        # nobody could find, and the second was true of a game that was no longer
        # theirs. A campaign that cannot be read is a thing to be told about, not a
        # thing to be quietly replaced.
        raise UnreadableSave(
            f"{path.name} could not be read: {exc}. The file has been left where it "
            f"is — nothing was overwritten."
        ) from exc


def _begin(campaign_id: str, character=None) -> Campaign:
    from . import roster

    c = new_campaign(campaign_id, character=character)
    entry = roster.enrol(c.scene.pc(), campaign_id)
    c.character_id = entry.id
    open_the_story(c, written=False)
    c.save()
    return c


def _heal_background(c) -> None:
    """Bind a past that was chosen and never filled, on the next load.

    Every campaign begun through the two doors that did not bind is on disk with a
    background on the sheet and an empty `background_ties` beside it — the character the
    bug was reported from is one of them. Fixing the doors helps the next character and
    does nothing for that one, and a player is not going to reroll because the plumbing
    was wrong.

    Only ever fills an empty list. A campaign whose ties bound normally is left alone, and
    so is a character who chose no past — `bind` is meant to happen once, and a second run
    would re-cast the people it names.

    The same shape as the other healings this loader does: the mark that "only ever rises",
    the save from before actors had a place being stood with the party. A save is a thing
    you meet as you find it.

    **It does not write.** The first version called `c.save()` so the fix would persist,
    and that made loading a campaign a thing that writes to disk — which promptly leaked
    between tests and failed `test_foraging_fills_the_satchel` on the full run while it
    passed alone. The campaign saves after every turn anyway, so the ties persist with the
    first thing the player does; a loader that saves is a surprise nobody asked for.
    """
    pc = c.scene.pc() if c is not None else None
    if pc is None or not getattr(pc, "background", ""):
        return
    if getattr(pc, "background_ties", None):
        return
    _bind_background(c)


def open_the_story(c, written: bool = True) -> None:
    """Bind the character's past, then write the opening that can use it.

    **One door, because there were three and only one of them bound.** A campaign is
    opened from `begin_with`, from the "enrolled but never played" branch of `resume`,
    and from `_begin` — and `_bind_background` was called from the first of those only.
    A character forged with a background and then played through either of the other two
    got the stranger's opening: "a long way from anyone who knows you", which is the
    template `play/opening.py` falls back to when nobody knows them.

    Reported from real play on 2026-09-15, with `background: 'pit-fighter'` on the sheet
    and `background_ties: []` beside it. The bind itself was never broken — run against
    that save it produces "You fought where Xylaraezys took the bets, near the market" —
    it simply was not reached.

    The order is load-bearing and is why this is one function rather than two calls: the
    ties have to exist BEFORE `opening_text` is evaluated, because the first paragraph is
    exactly where "you were apprenticed to somebody" has to become a name. Two statements
    at a call site can be put in the wrong order; an argument cannot be evaluated after
    the call it is an argument to.
    """
    _bind_background(c)
    _open_with(c, opening_text(c, written=written))


def _bind_background(c) -> None:
    """Fill the PC's background ties from the world, once, at the start of a campaign.

    Wrapped because a background that cannot bind must never stop a game beginning: the
    people come from the world's own cast, and a settlement with nobody in it is a
    perfectly ordinary thing for a world to contain.
    """
    from rules import backgrounds

    pc = c.scene.pc()
    if pc is None or not getattr(pc, "background", ""):
        return
    try:
        engine = c.engine()
        bound = backgrounds.bind(engine, pc)
        pc.background_ties = [b["says"] for b in bound]
        # And whoever the opening put beside them stops being a stranger, if the ties
        # say this character is known here (`backgrounds.acquaint`). Nobody is added:
        # the person is the one the situation already rolled.
        backgrounds.acquaint(engine, pc, bound)
    except Exception:
        pc.background_ties = []


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
    # The *resolved* world, not the argument: `new_campaign` fills a missing source with
    # the shipped default, and the entry should record what actually happened either way
    # — a character forged from Fantasia's page was starting in Pangrella because nothing
    # anywhere wrote the choice down.
    entry.world_source = str(c.world_source or "")
    roster.save(entry)
    # Before the opening is written, because the opening reads what this produces: a
    # background is a set of slots until a world fills them, and the first paragraph is
    # where "you were apprenticed to somebody" has to become a name.
    open_the_story(c)
    c.save()
    _LIVE[entry.id] = c
    set_active(entry.id)
    return c
