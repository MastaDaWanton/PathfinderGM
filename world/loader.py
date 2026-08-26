"""Reading a World Bible campaign export.

The export is read-only source of truth (see docs/campaign-format.md). Nothing in this
module writes to it. Everything play changes lives in the campaign overlay, keyed by the
same durable ids.

Defensive about the gaps documented in docs/from-world-bible.md: null `entity_id` on
chronology figures and route endpoints, null `year` on undated events, and prose that
names places which were never written up.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

SUPPORTED_MAJOR = 1

KINDS = ("WORLD", "CONTINENT", "PEOPLE", "NATION", "CITY", "CHARACTER")


class UnsupportedSchema(Exception):
    """A major version we were not written for. Refuse rather than guess."""


@dataclass(frozen=True)
class Entity:
    id: str
    kind: str
    name: str
    summary: str
    parent_id: str | None
    path: str
    facts: dict[str, str] = field(default_factory=dict)
    sections: list[dict] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    trade: dict[str, str] = field(default_factory=dict)
    scale: str | None = None

    @property
    def role(self) -> str:
        """What this person actually is.

        `play.cast[].role` is the entity's `summary`, which in the shipped Pangrella
        export is the literal string "Person" for all 47 characters — it carries no
        information. The real role is a fact, so read that first and only fall back to
        the summary.
        """
        return self.facts.get("Role") or self.facts.get("Identity") or self.summary

    @property
    def prose(self) -> str:
        return "\n\n".join(
            p for s in self.sections for p in s.get("paragraphs", [])
        )

    def fact(self, key: str, default: str = "") -> str:
        return self.facts.get(key, default)


@dataclass(frozen=True)
class Event:
    name: str
    year: int | None
    summary: str
    scope: str
    background: str
    moments: list[dict]
    aftermath: str
    figures: list[dict]
    entity_ids: list[str]


@dataclass
class World:
    name: str
    premise: dict
    secret: str
    entities: dict[str, Entity]
    chronology: list[Event]
    trade_routes: list[dict]
    factions: list[dict]
    unwritten: list[dict]
    play: dict
    source: Path

    # --- lookups -----------------------------------------------------------------

    def get(self, entity_id: str | None) -> Entity | None:
        """Never raises on a null id — `entity_id` is legitimately null for anyone the
        world mentions but never wrote up."""
        if not entity_id:
            return None
        return self.entities.get(entity_id)

    def of_kind(self, kind: str) -> list[Entity]:
        return [e for e in self.entities.values() if e.kind == kind]

    def children(self, entity_id: str) -> list[Entity]:
        return [e for e in self.entities.values() if e.parent_id == entity_id]

    def ancestors(self, entity_id: str) -> list[Entity]:
        """Containment chain, nearest parent first. Uses parent_id, never `path`."""
        out: list[Entity] = []
        seen: set[str] = set()
        node = self.get(entity_id)
        while node and node.parent_id and node.parent_id not in seen:
            seen.add(node.parent_id)
            parent = self.get(node.parent_id)
            if parent is None:
                break
            out.append(parent)
            node = parent
        return out

    def by_name(self, name: str, kind: str | None = None) -> Entity | None:
        """Only for human-entered lookups. Never store the result by name.

        Names are not unique, and not only in edge cases: in the shipped Pangrella
        export the WORLD and one of its CITYs are both called "Pangrella", so a
        name lookup for the home town returns the entire world unless `kind` is
        given. Pass `kind` whenever you know it, and store the `id` you get back.
        """
        lowered = name.strip().lower()
        matches = [
            e for e in self.entities.values()
            if e.name.lower() == lowered and (kind is None or e.kind == kind)
        ]
        return matches[0] if matches else None

    def all_named(self, name: str) -> list[Entity]:
        """Every entity with this name — the honest answer when names collide."""
        lowered = name.strip().lower()
        return [e for e in self.entities.values() if e.name.lower() == lowered]

    def residents(self, settlement_id: str) -> list[Entity]:
        return [
            e for e in self.entities.values()
            if e.kind == "CHARACTER" and e.parent_id == settlement_id
        ]

    def routes_touching(self, entity_id: str) -> list[dict]:
        return [
            r for r in self.trade_routes
            if r.get("origin_id") == entity_id or r.get("destination_id") == entity_id
        ]

    def events_touching(self, entity_id: str | None) -> list[Event]:
        """History this entity would remember: its own, then its nation's, then its
        continent's, most recent first within each and undated last.

        `entity_ids` is the contract's join key (campaign-format.md, `chronology[]`) and
        is checked first so this keeps working the day an export populates it. It is
        empty on **all 111 events** of the shipped Pangrella export, which is why the
        only caller — the GM's "WHAT THIS PLACE REMEMBERS" — surfaced nothing for any of
        the world's 74 entities.

        `scope` is the field that does carry the link, but it names an entity instead of
        referencing it, so it is resolved back against the world's own names. That is the
        `Ground every name` lesson run backwards, and it inherits the same hazard: names
        are not unique. Where a name collides — the export's WORLD and one of its CITYs
        are both "Pangrella" — every entity holding it is considered and the *nearest*
        wins, so an event scoped to the ambiguous name lands on the town rather than on
        the ringworld containing it. Both readings belong in this list; only the order
        between them is a guess, and a town remembering its own world's founding is not
        a wrong answer.

        11 events are scoped to the literal string "World", which is nobody's name, and
        are therefore reachable from nowhere. Left alone: every entity already draws 12
        events against a budget of four.
        """
        if not entity_id:
            return []

        # The entity and everything containing it, by how far away it is. `setdefault`
        # keeps the nearest distance when an id somehow appears twice in the chain.
        near: dict[str, int] = {entity_id: 0}
        for step, ancestor in enumerate(self.ancestors(entity_id), start=1):
            near.setdefault(ancestor.id, step)

        # Built once per call rather than calling `all_named` per event: that is 74
        # comparisons instead of 111 scans of the whole entity table, and this runs on
        # every turn and every NPC turn within it.
        by_name: dict[str, list[str]] = {}
        for e in self.entities.values():
            by_name.setdefault(e.name.lower(), []).append(e.id)

        found: list[tuple[int, Event]] = []
        for event in self.chronology:
            steps = [near[i] for i in event.entity_ids if i in near]
            if not steps and event.scope:
                steps = [near[i] for i in by_name.get(event.scope.strip().lower(), [])
                         if i in near]
            if steps:
                found.append((min(steps), event))

        found.sort(key=lambda t: (t[0], t[1].year is None, -(t[1].year or 0)))
        return [event for _, event in found]

    def is_unwritten(self, name: str) -> bool:
        return any(u["name"].lower() == name.strip().lower() for u in self.unwritten)


def load(path: str | Path) -> World:
    path = Path(path)
    with path.open(encoding="utf-8") as fh:
        raw = json.load(fh)

    version = str(raw.get("schema_version", ""))
    major = version.split(".")[0]
    if not major.isdigit():
        raise UnsupportedSchema(f"{path.name}: unreadable schema_version {version!r}")
    if int(major) != SUPPORTED_MAJOR:
        raise UnsupportedSchema(
            f"{path.name}: schema {version} — this build reads major {SUPPORTED_MAJOR}. "
            "Re-export from a matching World Bible rather than loading this."
        )

    entities = {}
    for e in raw.get("entities", []):
        entities[e["id"]] = Entity(
            id=e["id"],
            kind=e.get("kind", ""),
            name=e.get("name", ""),
            summary=e.get("summary", ""),
            parent_id=e.get("parent_id"),
            path=e.get("path", ""),
            facts=e.get("facts") or {},
            sections=e.get("sections") or [],
            links=e.get("links") or [],
            trade=e.get("trade") or {},
            scale=e.get("scale"),
        )

    chronology = [
        Event(
            name=c.get("name", ""),
            year=c.get("year"),
            summary=c.get("summary", ""),
            scope=c.get("scope", ""),
            background=c.get("background", ""),
            moments=c.get("moments") or [],
            aftermath=c.get("aftermath", ""),
            figures=c.get("figures") or [],
            entity_ids=c.get("entity_ids") or [],
        )
        for c in raw.get("chronology", [])
    ]

    world_block = raw.get("world", {})
    return World(
        name=world_block.get("name", path.stem),
        premise=world_block.get("premise") or {},
        secret=world_block.get("secret", ""),
        entities=entities,
        chronology=chronology,
        trade_routes=raw.get("trade_routes") or [],
        factions=raw.get("factions") or [],
        unwritten=raw.get("unwritten") or [],
        play=raw.get("play") or {},
        source=path,
    )


@lru_cache(maxsize=4)
def _cached(path_str: str, mtime_ns: int, size: int) -> World:
    return load(path_str)


def load_cached(path: str | Path) -> World:
    """Load with an mtime-keyed cache.

    Keyed on content-changing metadata, not on "have we loaded something before" — the
    staleness bug in World Bible came from a check that only ever answered "fresh".
    Size is part of the key because mtime alone is not content-changing metadata on
    this machine: 46 of 50 back-to-back rewrites carried the identical st_mtime
    (Windows stamps from a cached clock that ticks every ~15ms), which let an upload's
    validation read the *previous* file's parse for the new file's bytes.
    """
    path = Path(path)
    st = path.stat()
    return _cached(str(path), st.st_mtime_ns, st.st_size)
