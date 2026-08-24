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
import re
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

from rules import feats as feats_mod
from rules import ingredients, registry, spells, worldclass
from rules import bestiary
from rules.bestiary import TEMPLATES
from rules.tables import ARMOUR, CLASSES, FEATS, SHIELDS, WEAPONS


def _slug(name: str) -> str:
    """The key `rules/registry.py` resolves by. The hand-written feat table is keyed with
    spaces and every other content module is keyed with hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


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


# Benches whose authoring lives on a page of its own rather than in the generated
# form. Keyed by bench id, valued by the URL. One entry today; a second kind with
# repeating structure would be one line here rather than a branch in the template.
PAGE_BUILDERS = {"classes": "/homebrew/classes/"}


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
    rows: list = field(default_factory=list)

    @property
    def builder(self) -> str:
        """Which authoring form this bench opens, if any.

        Derived rather than set, because setting it by hand is what left seven of the nine
        benches read-only: `consumables` and `ingredients` were flagged and the rest were
        not, so a creature, feat, weapon or spell could be listed and never corrected —
        even after `rules/registry.py` and `open_thing` could already handle all nine.

        The registry declaration is the same one the form is now drawn from, so a bench is
        editable when its kind says what it holds, not when somebody remembers to add it
        here. A bench with no kind — there are none today — is still a plain listing.
        """
        # A class is not a flat form. Its level table, its paths and their tiers are
        # repeating structures the generated effects form cannot draw, so the classes
        # bench sends you to the builder that can rather than showing a shape that
        # would quietly lose everything it has no field for.
        if self.id in PAGE_BUILDERS:
            return "page"
        return "effects" if registry.KINDS.get(self.id) else ""

    @property
    def builder_url(self) -> str:
        """Where `builder == "page"` goes. "" for a bench edited in place."""
        return PAGE_BUILDERS.get(self.id, "")

    @property
    def yours(self) -> int:
        return _count(self.dir, self.id)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "blurb": self.blurb, "ready": self.ready,
            "yours": self.yours, "shipped": self.shipped,
            "shipped_label": self.shipped_label or "shipped",
            "waiting": self.waiting, "builder": self.builder,
            "builder_url": self.builder_url, "path": str(folder(self.dir)),
        }


def benches() -> list[Bench]:
    return [
        Bench(
            id="classes", name="Character classes", dir="classes",
            shipped=len(CLASSES), shipped_label="in the Core Rulebook tables",
            blurb="Full 1e classes: hit dice, BAB, saves, class skills and what each "
                  "level grants. Blood Bending belongs here.",
            waiting="",
        ),
        Bench(
            id="worldclasses", name="World classes", dir="world-classes",
            shipped=len(worldclass.tracks()), shipped_label="shipped",
            blurb="Tracks that run alongside a character class and level on use. Not a "
                  "class: no BAB, no saves, no hit dice. Herbalism is the one that ships.",
        ),
        Bench(
            id="consumables", name="Materials & consumables", dir="consumables",
            shipped=0, shipped_label="shipped",
            blurb="Anything with an effect: potions, poultices, poisons, oils, reagents. "
                  "Built from a description and a list of effects rather than typed as "
                  "prose, so what a thing does is data the engine can read.",
        ),
        Bench(
            id="ingredients", name="Ingredients", dir="ingredients",
            shipped=len(ingredients.all_ingredients()), shipped_label="shipped",
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
            waiting="Two sources, and only one of them carries Environment: the 782 "
                    "Bestiary blocks parsed from the PDFs do, and the 6,406 from the "
                    "spreadsheet do not. Where two share a name the printed block wins. "
                    "Every creature carries biomes and a climate all the same — read from "
                    "that line where there is one, and guessed from the species in the "
                    "name or from the creature type where there is not. A guess says so.",
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
            waiting="Castable now: slots, caster level and save DCs are the engine's. "
                    "What a spell still does is its prose — the engine will not read "
                    "\"1d6 per caster level\" out of English and turn it into a number.",
        ),
        Bench(
            id="campaigns", name="Campaigns", dir="campaigns", ready=False, shipped=0,
            blurb="A premise, a cast and a goal the GM steers toward. Waiting on the "
                  "campaign format; sandbox play works today.",
        ),
        Bench(
            id="rulesets", name="Rulesets", dir="rulesets", shipped=2,
            shipped_label="house rules to set",
            blurb="The table's own rules. Point-buy tiers up to the full hundred, and "
                  "whether magic effects from different sources stack.",
        ),
    ]


def get(bench_id: str) -> Bench:
    found = next((b for b in benches() if b.id == bench_id), None)
    if found is None:
        raise LookupError(f"no bench {bench_id!r}")
    return found


def authored_total() -> int:
    return sum(b.yours for b in benches())


def _where(creature: dict) -> str:
    """Where a creature lives, for a bench row.

    The list itself is no use here: 4,636 of the 7,133 expand "any" into eleven or thirteen
    biomes, and printing those would be a paragraph per row that says nothing. So the ones
    found anywhere say so in a word, and only a real habitat is named. A guess is marked,
    because 6,406 of these were guessed and a row that reads like a fact from the book on a
    page about authoring content is exactly the wrong impression to leave.
    """
    if not creature.get("biomes"):
        return "no environment given"
    where = "anywhere" if creature.get("biomes_any") else ", ".join(creature["biomes"])
    climate = " ".join(creature.get("climates") or [])
    return f"{climate} {where}".strip() + (" (guess)" if creature.get("biomes_inferred")
                                           else "")


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
        from rules.creation import die_label

        rows += [{"name": v["name"], "kind": "class", "mine": False, "id": k,
                  "note": f"{die_label(v['hit_die'])} · "
                          f"{v['bab'].replace('_', ' ')} BAB · "
                          f"{v['skill_ranks']}+Int skills · good "
                          f"{', '.join(v['good_saves'])}"}
                 for k, v in CLASSES.items()]
    elif bench_id == "spells":
        # Capped: three thousand rows is not a listing, it is a wall. The bench's own
        # filters are how you find one, and they are the point of the tags.
        rows += [{"name": sp.name, "kind": sp.school or "spell", "mine": False,
                  "id": sp.id, "note": sp.line}
                 for sp in sorted(spells.all_spells().values(),
                                  key=lambda x: x.name.lower())[:200]]
    elif bench_id == "worldclasses":
        rows += [{"name": t.name, "kind": "track", "mine": False, "id": k,
                  "note": f"{t.max_level} levels · "
                          f"{len(t.unlocked_methods(t.max_level))} methods"}
                 for k, t in worldclass.tracks().items()]
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
            [{"name": v["name"], "kind": "weapon", "mine": False, "id": k,
              "note": f"{v['damage']} {v['type']} · x{v['crit_mult']}"}
             for k, v in WEAPONS.items()]
            + [{"name": v["name"], "kind": "armour", "mine": False, "id": k,
                "note": f"+{v['ac']} AC"} for k, v in ARMOUR.items() if k != "none"]
            + [{"name": v["name"], "kind": "shield", "mine": False, "id": k,
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
                          f"AC {c.get('flat_ac', '?')} · {c.get('size', '')} · "
                          f"{_where(c)}"}
                 for c in bestiary.search(limit=200)]
    elif bench_id == "feats":
        # The 16 the sheet applies by hand, then the rest of the imported list. Before
        # this the bench showed only the 16 while the shipped count said 16 — accurate
        # about itself and quietly hiding 1,474 feats the app had already imported.
        #
        # Ids are slugs, because that is what `rules.feats` is keyed by and what
        # `registry.find` therefore resolves. The hand-written table is keyed "weapon
        # finesse" with a space, so a row carrying that id drew a link to a 404. All 16
        # have an imported twin under the slug, so nothing is lost by preferring it.
        applied = {_slug(k): v for k, v in FEATS.items()}
        rows += [{"name": v.get("name", k), "kind": "feat", "mine": False, "id": k,
                  "note": v.get("note", "") or "applied by the sheet"}
                 for k, v in applied.items()]
        rows += [{"name": v.name, "kind": "feat", "mine": False, "id": k,
                  "note": (v.benefit or v.line or "")[:110]}
                 # Capped like the spell bench, and for the same reason: 1,474 rows is a
                 # wall rather than a listing.
                 for k, v in sorted(feats_mod.all_feats().items())[:200]
                 if k not in applied]
    return rows
