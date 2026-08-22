"""The spell list, and the filters that make three thousand of them usable.

Two kinds of label live on a spell here and they are kept apart on purpose.

**Descriptors** — `[fire]`, `[mind-affecting]`, `[curse]` — are rules facts with mechanical
consequences: a [fire] spell is stopped by fire immunity, a [mind-affecting] one does
nothing to an ooze. They are read from The Spell Codex's own columns and never inferred.
A guessed descriptor is worse than no descriptor, because it changes what the spell does.

**Tags** — `damage`, `dot`, `buff`, `control` — are ours. Pathfinder does not define them.
They exist so a player can find the right spell out of three thousand, and they are never
consulted by any rule. `tags_derived` is on the payload so nobody has to remember which is
which.

Spells belong to as many lists as they belong to: 2,887 of the 3,040 are on more than one,
so `lists` is a mapping of class to the level it sits at for that class, not a single
number.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

SCHOOLS = ("abjuration", "conjuration", "divination", "enchantment", "evocation",
           "illusion", "necromancy", "transmutation", "universal")

# What our derived tags mean, so a filter can explain itself rather than being a bare word.
TAG_NOTES = {
    "damage": "Deals hit point damage.",
    "dot": "Damage that repeats over rounds rather than landing once.",
    "healing": "Restores hit points or cures a condition.",
    "buff": "Grants a bonus, or is harmless to its target.",
    "debuff": "Imposes a penalty.",
    "control": "Denies movement or actions — held, entangled, asleep, paralysed.",
    "summoning": "Brings a creature.",
    "movement": "Teleport, flight, or speed.",
    "detection": "Finds or reveals something.",
    "defence": "Wards, resistances and deflection.",
    "illusion": "Of the illusion school.",
    "utility": "Everything the other tags did not claim.",
    "aoe": "Affects an area rather than a target.",
    "touch": "Range: touch.",
    "personal": "Range: personal — the caster only.",
    "ranged": "Cast at a distance.",
    "sustained": "Lasts while you concentrate.",
    "instant": "Resolves and is over.",
    "permanent": "Does not expire on its own.",
    "harmless": "The save is there for an unwilling ally.",
    "save-negates": "A successful save stops it entirely.",
    "save-half": "A successful save halves it.",
    "save-partial": "A successful save reduces it.",
    "no-save": "No saving throw.",
}


@dataclass
class Spell:
    id: str
    name: str
    school: str = ""
    subschool: str = ""
    descriptors: list[str] = field(default_factory=list)
    lists: dict[str, int] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    casting_time: str = ""
    range: str = ""
    area: str = ""
    effect: str = ""
    targets: str = ""
    duration: str = ""
    saving_throw: str = ""
    spell_resistance: str = ""
    components: list[str] = field(default_factory=list)
    component_cost: str = ""
    dismissible: bool = False
    shapeable: bool = False
    source: str = ""
    description: str = ""
    deity: str = ""
    domain: str = ""
    bloodline: str = ""
    patron: str = ""
    sla_level: int | None = None

    @property
    def min_level(self) -> int | None:
        return min(self.lists.values()) if self.lists else None

    @property
    def line(self) -> str:
        """The one-line summary a list view shows."""
        bits = [self.school + (f" ({self.subschool})" if self.subschool else "")]
        if self.descriptors:
            bits.append("[" + "] [".join(self.descriptors) + "]")
        if self.lists:
            bits.append(", ".join(f"{k} {v}" for k, v in
                                  sorted(self.lists.items(), key=lambda kv: kv[1])[:4]))
        return " · ".join(b for b in bits if b)

    def as_dict(self) -> dict:
        d = dict(self.__dict__)
        d["min_level"] = self.min_level
        d["line"] = self.line
        return d


def from_dict(d: dict) -> Spell:
    known = Spell.__dataclass_fields__
    return Spell(**{k: v for k, v in d.items() if k in known})


_ALL: dict[str, Spell] | None = None
_META: dict = {}


def all_spells() -> dict[str, Spell]:
    """Every spell, shipped plus homebrew, layered the same way ingredients are."""
    global _ALL, _META
    if _ALL is None:
        from django.conf import settings

        raw: dict[str, dict] = {}
        for folder in (Path(settings.BASE_DIR) / "content" / "spells",
                       Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "spells"):
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                entries = data.get("spells") if isinstance(data, dict) else None
                if not isinstance(entries, list):
                    entries = [data] if isinstance(data, dict) and data.get("id") else []
                for e in entries:
                    if e.get("id"):
                        # Merged, not replaced: an edit that changes one field must not
                        # drop the twenty it never asked about.
                        base = dict(raw.get(e["id"], {}))
                        base.update({k: v for k, v in e.items() if v not in (None, "")})
                        raw[e["id"]] = base
                if isinstance(data, dict) and data.get("descriptors"):
                    _META = {"descriptors": data["descriptors"],
                             "classes": data.get("classes", []),
                             "note": data.get("note", "")}
        _ALL = {k: from_dict(v) for k, v in raw.items()}
    return _ALL


def meta() -> dict:
    all_spells()
    return _META


def get(spell_id: str) -> Spell:
    s = all_spells().get((spell_id or "").strip().lower())
    if s is None:
        raise KeyError(f"no spell {spell_id!r}")
    return s


def vocabularies() -> dict:
    """Everything a filter can be built from, counted so a zero option is visible."""
    spells = all_spells().values()
    def tally(get_values):
        out: dict[str, int] = {}
        for s in spells:
            for v in get_values(s):
                out[v] = out.get(v, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    return {
        "schools": tally(lambda s: [s.school] if s.school else []),
        "subschools": tally(lambda s: [s.subschool] if s.subschool else []),
        "descriptors": tally(lambda s: s.descriptors),
        "tags": tally(lambda s: s.tags),
        "classes": tally(lambda s: list(s.lists)),
        "sources": tally(lambda s: [s.source] if s.source else []),
        "tag_notes": TAG_NOTES,
    }


def search(text: str = "", school: str = "", subschool: str = "",
           descriptor: str = "", tag: str = "", klass: str = "",
           level: int | None = None, limit: int = 200) -> list[Spell]:
    """Filter the list. Every argument narrows; none of them widens.

    `descriptor` and `tag` are separate arguments even though both read as labels, because
    they answer different questions: "is this spell stopped by fire immunity" and "is this
    spell the sort of thing I am looking for".
    """
    out = []
    needle = (text or "").strip().lower()
    for s in all_spells().values():
        if school and s.school != school:
            continue
        if subschool and s.subschool != subschool:
            continue
        if descriptor and descriptor not in s.descriptors:
            continue
        if tag and tag not in s.tags:
            continue
        if klass and klass not in s.lists:
            continue
        if level is not None:
            levels = [s.lists[klass]] if klass and klass in s.lists else list(s.lists.values())
            if level not in levels:
                continue
        if needle and needle not in s.name.lower() \
                and needle not in s.description.lower():
            continue
        out.append(s)
    out.sort(key=lambda x: (x.min_level if x.min_level is not None else 99,
                            x.name.lower()))
    return out[:limit]
