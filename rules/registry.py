"""One place that knows what kinds of content exist.

Seven modules each grew their own copy of the same twenty lines: glob `content/<thing>`,
glob `homebrew/<thing>`, accept either a file holding a list or a file holding one entry,
merge field by field rather than replacing, cache the result. `classes`, `spells`, `feats`,
`weapons`, `ingredients`, `worldclass` and `bestiary` — seven copies of a rule, which is
the shape CLAUDE.md names as the reason a fix ships from the copy nobody looked at.

They also drifted, which is the other half of that lesson. Some merged and some replaced;
some read a bare `{...}` file and some only a `{"things": [...]}` one; two cached and the
rest did not. A homebrew ingredient saved as a single object appeared in the editor and
never reached play, and that is exactly the failure the divergence predicts.

**What a Kind declares** is everything both halves of the app need: where the files live,
what the list is called inside them, and — the part that makes an editor possible — what
fields the thing actually has. The builder page is generated from that declaration rather
than hand-written per kind, so a new kind of content is one entry here instead of a form,
a loader, a route and a template.

Nothing here imports a rules module at the top. The rules modules import *this*, and a
Kind names its shipped loader as a string resolved on demand — otherwise every kind of
content in the game would have to be imported to ask what folder spells live in.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path

from . import biomes as _biomes


@dataclass
class Field:
    """One editable field, and enough about it to draw an input for it."""
    name: str
    label: str
    type: str = "text"          # text | textarea | number | choice | list | effects
    choices: tuple = ()
    help: str = ""
    required: bool = False

    def as_dict(self) -> dict:
        return {"name": self.name, "label": self.label, "type": self.type,
                "choices": list(self.choices), "help": self.help,
                "required": self.required}


@dataclass
class Kind:
    id: str
    label: str
    folder: str                 # content/<folder> and homebrew/<folder>
    key: str                    # the list key inside a file holding many
    fields: list[Field] = field(default_factory=list)
    # `module:function` returning {id: object} for what ships. A string rather than the
    # function, so declaring a kind does not import the whole game.
    shipped_loader: str = ""
    # `module:function(entry) -> dict` filling in fields the stored entry does not carry
    # because they are read out of the fields it does. A creature's `effects` are its
    # printed Immune, Resist and Weaknesses lines converted; storing them as well would be
    # a second copy that disagrees the moment somebody edits the first.
    #
    # Declared here rather than handled in `open_thing`, because a creature-shaped `if`
    # in the view is exactly what this module was written to delete.
    derive: str = ""
    id_field: str = "id"

    def as_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "folder": self.folder,
                "key": self.key, "fields": [f.as_dict() for f in self.fields]}


# Shared field groups, so "everything has a name and a description" is stated once.
def _named(*, kinds: tuple = ()) -> list[Field]:
    out = [
        Field("name", "Name", required=True),
        Field("description", "Description", type="textarea",
              help="What it is. The mechanics go in Effects, not here."),
    ]
    if kinds:
        out.insert(1, Field("kind", "Kind", type="choice", choices=kinds))
    return out


TIERS = ("common", "uncommon", "rare", "exotic", "legendary")

# Derived, not retyped. The first version of this line was the fourteen biome names
# written out again, which is a second copy of `biomes.BIOMES` that agrees with it today
# and drifts the first time somebody adds a biome to one and not the other — the exact
# shape CLAUDE.md warns about. `rules.biomes` pulls in nothing, so importing it here is
# free.
BIOME_CHOICES = tuple(_biomes.BIOMES)
CLIMATE_CHOICES = tuple(_biomes.CLIMATES)

KINDS: dict[str, Kind] = {
    "ingredients": Kind(
        id="ingredients", label="Ingredients", folder="ingredients", key="ingredients",
        shipped_loader="rules.ingredients:all_ingredients",
        fields=_named(kinds=("herb", "fungus", "monster part", "poison")) + [
            Field("tier", "Rarity", type="choice", choices=TIERS),
            Field("biomes", "Grows in", type="list", choices=BIOME_CHOICES),
            Field("craft_dc", "Craft DC", type="number"),
            Field("harvesting", "Harvesting", type="textarea"),
            Field("risky", "Hazardous to handle", type="choice", choices=("no", "yes")),
            Field("effects", "Effects", type="effects"),
        ],
    ),
    "consumables": Kind(
        id="consumables", label="Materials & consumables", folder="consumables",
        key="consumables",
        fields=_named(kinds=("potion", "poultice", "poison", "oil", "reagent")) + [
            Field("tier", "Rarity", type="choice", choices=TIERS),
            Field("effects", "Effects", type="effects"),
        ],
    ),
    "creatures": Kind(
        id="creatures", label="Creatures", folder="creatures", key="creatures",
        # `everything`, not `imported`: the bench lists the four hand-written townsfolk
        # too, and a row the page drew that 404s when clicked is worse than no row.
        shipped_loader="rules.bestiary:everything",
        derive="rules.creature_effects:derive",
        fields=_named() + [
            Field("cr", "Challenge rating"),
            Field("size", "Size", type="choice",
                  choices=("fine", "diminutive", "tiny", "small", "medium", "large",
                           "huge", "gargantuan", "colossal")),
            Field("creature_type", "Type"),
            # Three fields, not one, because the bestiary keeps three things. The
            # first version of this declared a *list* editor over `environment`, which
            # is prose — "temperate or cold hills" — so saving a creature would have
            # written a biome list on top of the sentence it was parsed from and thrown
            # the original away.
            Field("environment", "Environment (as printed)", type="textarea",
                  help="The book's own line. The lists below are read out of it."),
            Field("biomes", "Terrain", type="list", choices=BIOME_CHOICES),
            Field("climates", "Climate", type="list", choices=CLIMATE_CHOICES,
                  help="Empty means unrestricted, which is not the same as all three."),
            Field("hp", "Hit points", type="number"),
            Field("flat_ac", "Armour class", type="number"),
            Field("effects", "Effects", type="effects"),
        ],
    ),
    "npcs": Kind(
        id="npcs", label="NPCs", folder="npcs", key="npcs",
        fields=_named() + [
            Field("creature", "Stat block", help="A creature id this NPC uses."),
            Field("wants", "What they want", type="textarea"),
            Field("knows", "Who they know", type="textarea"),
            # `biomes`, not `environment`, so it means the same thing here as it does on a
            # creature. One name for a list and the same name for prose two kinds apart is
            # how the creature field went wrong in the first place.
            Field("biomes", "Found in", type="list", choices=BIOME_CHOICES),
        ],
    ),
    "items": Kind(
        id="items", label="Items, weapons & armour", folder="items", key="items",
        shipped_loader="rules.weapons:all_weapons",
        fields=_named(kinds=("weapon", "armour", "shield", "gear")) + [
            Field("damage", "Damage"),
            Field("crit_range", "Threat range", type="number"),
            Field("crit_mult", "Critical multiplier", type="number"),
            Field("type", "Damage type"),
            Field("effects", "Effects", type="effects"),
        ],
    ),
    "classes": Kind(
        id="classes", label="Character classes", folder="classes", key="classes",
        shipped_loader="rules.classes:all_classes",
        fields=_named() + [
            Field("hit_die", "Hit die"),
            Field("bab", "BAB progression", type="choice",
                  choices=("full", "three_quarter", "half")),
            Field("skill_ranks", "Skill ranks per level", type="number"),
            Field("class_skills", "Class skills", type="list"),
        ],
    ),
    "worldclasses": Kind(
        id="worldclasses", label="World classes", folder="world-classes", key="tracks",
        shipped_loader="rules.worldclass:tracks",
        fields=_named() + [Field("levels", "Levels", type="list")],
    ),
    "feats": Kind(
        id="feats", label="Feats", folder="feats", key="feats",
        shipped_loader="rules.feats:all_feats",
        fields=_named() + [
            Field("types", "Types", type="list"),
            Field("prerequisites_text", "Prerequisites", type="textarea"),
            Field("benefit", "Benefit", type="textarea"),
            Field("effects", "Effects", type="effects"),
        ],
    ),
    "spells": Kind(
        id="spells", label="Spells", folder="spells", key="spells",
        shipped_loader="rules.spells:all_spells",
        fields=_named() + [
            Field("school", "School"),
            Field("range", "Range"),
            Field("duration", "Duration"),
            Field("saving_throw", "Saving throw"),
            Field("effects", "Effects", type="effects"),
        ],
    ),
}


def get(kind_id: str) -> Kind:
    found = KINDS.get((kind_id or "").strip().lower())
    if found is None:
        raise LookupError(f"no such kind {kind_id!r}; known: {', '.join(sorted(KINDS))}")
    return found


def content_dir(kind_id: str) -> Path:
    from django.conf import settings

    return Path(settings.BASE_DIR) / "content" / get(kind_id).folder


def homebrew_dir(kind_id: str, make: bool = False) -> Path:
    from django.conf import settings

    p = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / get(kind_id).folder
    if make:
        p.mkdir(parents=True, exist_ok=True)
    return p


def read_folder(path: Path, key: str) -> dict[str, dict]:
    """Every entry in a directory, whatever shape the files are in.

    Two shapes, because two things write here: an import writes one file holding a list,
    and the editor writes one file per thing it edits. Reading only the first shape is
    what made a saved homebrew ingredient appear in the editor when reopened and never
    reach play — no error anywhere, which is the worst version of it.
    """
    out: dict[str, dict] = {}
    if not path.is_dir():
        return out
    for file in sorted(path.glob("*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries = data.get(key) if isinstance(data, dict) else None
        if not isinstance(entries, list):
            entries = [data] if isinstance(data, dict) and data.get("id") else []
        for entry in entries:
            if isinstance(entry, dict) and entry.get("id"):
                out[str(entry["id"]).strip().lower()] = entry
    return out


def load_raw(kind_id: str) -> dict[str, dict]:
    """Shipped, then homebrew over the top, merged field by field.

    Merged rather than replaced, and that is not a detail: the editor saves a name, a
    description and a list of effects, so replacing would silently drop the tier, the
    biomes and the harvesting notes it never asked about. Correcting one field would
    quietly erase five.
    """
    kind = get(kind_id)
    out: dict[str, dict] = {}
    for folder in (content_dir(kind_id), homebrew_dir(kind_id)):
        for key, entry in read_folder(folder, kind.key).items():
            out.setdefault(key, {}).update(entry)
    return out


def shipped(kind_id: str) -> dict:
    """What the app came with, by whatever module owns that kind.

    Resolved on demand from the name, so declaring a kind does not drag the whole game
    into this module — and a kind whose loader is missing or broken reports empty rather
    than taking the homebrew page down with it.
    """
    target = get(kind_id).shipped_loader
    if not target:
        return {}
    module_name, _, func_name = target.partition(":")
    try:
        loaded = getattr(import_module(module_name), func_name)()
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def find(kind_id: str, thing_id: str) -> dict | None:
    """One entry, homebrew first, then shipped — so the editor can open anything.

    Before this, only ingredients and consumables could be opened: `open_thing` named
    those two in an `if` and every other bench could create but never correct. A shipped
    entry that cannot be opened is a conversion nobody can undo, and 161 ingredients were
    converted mechanically with nobody having read them.
    """
    key = (thing_id or "").strip().lower()
    mine = load_raw(kind_id).get(key)
    if mine:
        return _derived(kind_id, dict(mine))

    found = shipped(kind_id).get(key)
    if found is None:
        return None
    if hasattr(found, "as_dict"):
        found = found.as_dict()
    return _derived(kind_id, dict(found)) if isinstance(found, dict) else None


def _derived(kind_id: str, entry: dict) -> dict:
    """Fill in whatever this kind computes rather than stores.

    Wrapped in the same try/except `shipped` uses, and for the same reason: the homebrew
    page asks every kind at once, and one kind's derivation failing must not take the page
    down with it.
    """
    target = get(kind_id).derive
    if not target:
        return entry
    module_name, _, func_name = target.partition(":")
    try:
        return getattr(import_module(module_name), func_name)(entry)
    except Exception:
        return entry


def save(kind_id: str, entry: dict) -> Path:
    """Write one thing to the user's own directory. The shipped file is never touched.

    CLAUDE.md made concrete: a corrected table in a later build must not be shadowed by a
    stale copy in the user's data directory, so yours layers over what ships and both
    stay readable.
    """
    kind = get(kind_id)
    thing_id = str(entry.get(kind.id_field) or "").strip().lower()
    if not thing_id:
        raise ValueError("it needs an id")
    path = homebrew_dir(kind_id, make=True) / f"{thing_id}.json"
    path.write_text(json.dumps(entry, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def catalogue() -> list[dict]:
    """Every kind, for a page that wants to offer all of them."""
    return [k.as_dict() for k in KINDS.values()]


__all__ = ["BIOME_CHOICES", "Field", "KINDS", "Kind", "TIERS", "catalogue",
           "content_dir", "find", "get", "homebrew_dir", "load_raw", "read_folder",
           "save", "shipped"]
