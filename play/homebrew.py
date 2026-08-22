"""What the homebrew tab is actually looking at.

Two counts, kept apart on purpose. **Shipped** is what the app comes with — 23 weapons,
four creatures, the Core Rulebook classes. **Yours** is what you have authored into your
own data directory. Reporting the shipped tables as homebrew was the first thing anyone
looked at this page and disbelieved: a Longsword is not homebrew, and a bench claiming 23
of them had nothing to do with anything the user made.

Every bench points at a real overlay directory, so "0 yours" is a fact about a folder
rather than a placeholder, and there is somewhere for a file to go the moment one exists.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

from rules import ingredients, spells, worldclass
from rules import bestiary
from rules.bestiary import TEMPLATES
from rules.tables import ARMOUR, CLASSES, FEATS, SHIELDS, WEAPONS


def root() -> Path:
    """Where authored content lives. Beside campaigns, characters and worlds."""
    p = Path(settings.CAMPAIGN_DIR).parent / "homebrew"
    p.mkdir(parents=True, exist_ok=True)
    return p


def folder(name: str) -> Path:
    p = root() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def _count(name: str, key: str) -> int:
    """How many things the user has authored of one kind."""
    total = 0
    for path in folder(name).glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and isinstance(data.get(key), list):
            total += len(data[key])
        else:
            total += 1
    return total


@dataclass
class Bench:
    id: str
    name: str
    dir: str
    blurb: str
    ready: bool = True
    shipped: int = 0
    shipped_label: str = ""
    # Set when the app can hold the content but nothing has been authored, so the card
    # can say what is missing rather than looking broken.
    waiting: str = ""
    # Which authoring form this bench opens, if any. `effects` is the structured builder
    # in rules/effectspec.py; a bench without one is a listing.
    builder: str = ""
    rows: list = field(default_factory=list)

    @property
    def yours(self) -> int:
        return _count(self.dir, self.id)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "blurb": self.blurb, "ready": self.ready,
            "yours": self.yours, "shipped": self.shipped,
            "shipped_label": self.shipped_label or "shipped",
            "waiting": self.waiting, "builder": self.builder,
            "path": str(folder(self.dir)),
        }


def benches() -> list[Bench]:
    return [
        Bench(
            id="classes", name="Character classes", dir="classes",
            shipped=len(CLASSES), shipped_label="in the Core Rulebook tables",
            blurb="Full 1e classes: hit dice, BAB, saves, class skills and what each "
                  "level grants. Blood Bending belongs here.",
            waiting="Blood Bending is specified in docs/homebrew-rules.md and not yet "
                    "written as data. Its numbers are settled; what it still needs from "
                    "the engine is reactions, spawned battlefield objects and an "
                    "interruptible damage pipeline.",
        ),
        Bench(
            id="worldclasses", name="World classes", dir="world-classes",
            shipped=len(worldclass.tracks()), shipped_label="shipped",
            blurb="Tracks that run alongside a character class and level on use. Not a "
                  "class: no BAB, no saves, no hit dice. Herbalism is the one that ships.",
        ),
        Bench(
            id="consumables", name="Materials & consumables", dir="consumables",
            shipped=0, shipped_label="shipped", builder="effects",
            blurb="Anything with an effect: potions, poultices, poisons, oils, reagents. "
                  "Built from a description and a list of effects rather than typed as "
                  "prose, so what a thing does is data the engine can read.",
        ),
        Bench(
            id="ingredients", name="Ingredients", dir="ingredients",
            shipped=len(ingredients.all_ingredients()), shipped_label="shipped",
            builder="effects",
            blurb="What a crafter works with, the biomes each grows in, and the "
                  "mechanics read out of its description.",
        ),
        Bench(
            id="items", name="Items, weapons & armour", dir="items",
            shipped=len(WEAPONS) + len(ARMOUR) + len(SHIELDS) - 2,
            shipped_label="in the Core Rulebook tables",
            blurb="Weapons, armour and shields. Hardness and hit points come from the "
                  "material.",
        ),
        Bench(
            id="creatures", name="Creatures", dir="creatures",
            shipped=len(TEMPLATES) + len(bestiary.imported()),
            shipped_label="in the bestiary",
            blurb="Stat blocks the engine can put in a scene and roll for. Unlike the "
                  "spell list these are executable: hit points, AC, saves, damage "
                  "reduction and an attack the engine rolls against.",
            waiting="Three sources: the core Bestiary stat blocks parsed from the PDFs "
                    "(which carry Environment, so a creature can be tied to a biome), a "
                    "variant and NPC spreadsheet for the named villains, and a handful of "
                    "hand-written town NPCs. Where two share a name the printed Bestiary "
                    "block wins.",
        ),
        Bench(
            id="feats", name="Feats", dir="feats",
            shipped=len(FEATS), shipped_label="in the Core Rulebook tables",
            blurb="Named modifiers the sheet applies. A feat that grants a permission "
                  "rather than a number needs the relaxation rules in "
                  "docs/homebrew-rules.md.",
        ),
        Bench(
            id="npcs", name="NPCs", dir="npcs", ready=False, shipped=0,
            blurb="A creature plus the world-facing facts: who they are, what they want, "
                  "who they know. Authored here, placed in a world.",
        ),
        Bench(
            id="spells", name="Spells", dir="spells",
            shipped=len(spells.all_spells()), shipped_label="from The Spell Codex",
            blurb="Every 1e spell, with its school, its canonical descriptors and the "
                  "level it sits at on each class list. Searchable by any of them.",
            waiting="The engine has no spell system, so these are reference and "
                    "narration: nothing here is cast by the rules yet. What they give "
                    "you now is a real list to build against.",
        ),
        Bench(
            id="campaigns", name="Campaigns", dir="campaigns", ready=False, shipped=0,
            blurb="A premise, a cast and a goal the GM steers toward. Waiting on the "
                  "campaign format; sandbox play works today.",
        ),
        Bench(
            id="rulesets", name="Rulesets", dir="rulesets", ready=False, shipped=0,
            blurb="Toggles and numeric overrides — max hit points at 1st level, crit "
                  "confirmation off. See docs/homebrew-rules.md.",
        ),
    ]


def get(bench_id: str) -> Bench:
    found = next((b for b in benches() if b.id == bench_id), None)
    if found is None:
        raise LookupError(f"no bench {bench_id!r}")
    return found


def authored_total() -> int:
    return sum(b.yours for b in benches())


def rows_for(bench_id: str) -> list[dict]:
    """What is already on the bench, yours listed before the shipped material.

    Listing the built-ins is the honest start for an editor — you author against what
    exists — but they are labelled, so nothing on this page can be mistaken for something
    the user wrote.
    """
    bench = get(bench_id)
    rows: list[dict] = []

    for path in sorted(folder(bench.dir).glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            rows.append({"name": path.name, "kind": "yours", "note": f"unreadable: {exc}",
                         "mine": True})
            continue
        entries = data.get(bench_id) if isinstance(data, dict) else None
        for e in (entries if isinstance(entries, list) else [data]):
            from rules import effectspec

            lines = [effectspec.render(x) for x in (e.get("effects") or [])]                 if isinstance(e, dict) else []
            rows.append({
                "name": (e.get("name") if isinstance(e, dict) else None) or path.stem,
                "kind": "yours", "id": path.stem, "mine": True,
                "note": "; ".join(lines)
                        or (e.get("summary") if isinstance(e, dict) else "")
                        or path.name,
            })

    if bench_id == "consumables":
        pass                      # nothing ships; the bench exists to be authored into
    elif bench_id == "classes":
        rows += [{"name": v["name"], "kind": "class", "mine": False,
                  "note": f"d{v['hit_die']} · {v['bab'].replace('_', ' ')} BAB · "
                          f"{v['skill_ranks']}+Int skills · good "
                          f"{', '.join(v['good_saves'])}"}
                 for v in CLASSES.values()]
    elif bench_id == "spells":
        # Capped: three thousand rows is not a listing, it is a wall. The bench's own
        # filters are how you find one, and they are the point of the tags.
        rows += [{"name": sp.name, "kind": sp.school or "spell", "mine": False,
                  "id": sp.id, "note": sp.line}
                 for sp in sorted(spells.all_spells().values(),
                                  key=lambda x: x.name.lower())[:200]]
    elif bench_id == "worldclasses":
        rows += [{"name": t.name, "kind": "track", "mine": False,
                  "note": f"{t.max_level} levels · "
                          f"{len(t.unlocked_methods(t.max_level))} methods"}
                 for t in worldclass.tracks().values()]
    elif bench_id == "ingredients":
        rows += [{"name": i.name, "kind": i.kind, "mine": False, "id": i.id,
                  # What it does, not where it grows: the effects are the reason to open
                  # one, and 161 of them were converted mechanically and never read.
                  "note": "; ".join(i.lines) or "no mechanical effect stated",
                  "unreviewed": i.effects_converted and bool(i.effects)}
                 for i in sorted(ingredients.all_ingredients().values(),
                                 key=lambda x: x.name)]
    elif bench_id == "items":
        rows += (
            [{"name": v["name"], "kind": "weapon", "mine": False,
              "note": f"{v['damage']} {v['type']} · x{v['crit_mult']}"}
             for v in WEAPONS.values()]
            + [{"name": v["name"], "kind": "armour", "mine": False,
                "note": f"+{v['ac']} AC"} for k, v in ARMOUR.items() if k != "none"]
            + [{"name": v["name"], "kind": "shield", "mine": False,
                "note": f"+{v['ac']} AC"} for k, v in SHIELDS.items() if k != "none"]
        )
    elif bench_id == "creatures":
        rows += [{"name": v.get("name", k), "kind": "hand-written", "mine": False,
                  "id": k,
                  "note": f"{v.get('hp', '?')} hp · AC {v.get('flat_ac', '?')}"}
                 for k, v in TEMPLATES.items()]
        # Capped for the same reason the spell bench is: six thousand rows is a wall.
        rows += [{"name": c["name"], "kind": c.get("creature_type") or "creature",
                  "mine": False, "id": c["id"],
                  "note": f"CR {c.get('cr', '?')} · {c.get('hp', '?')} hp · "
                          f"AC {c.get('flat_ac', '?')} · {c.get('size', '')}"}
                 for c in bestiary.search(limit=200)]
    elif bench_id == "feats":
        rows += [{"name": v.get("name", k), "kind": "feat", "mine": False,
                  "note": v.get("note", "")} for k, v in FEATS.items()]
    return rows
