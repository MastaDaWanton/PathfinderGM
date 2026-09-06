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
    # `module:function(entry) -> (entry, problems)`: the save-time check with the fix
    # named, for a kind whose fields are more than prose and effects — a race's
    # one-per-line modifiers are parsed and refused here, so a document that would fail
    # silently in play (a save called "fortitude" nothing reads) never reaches disk.
    validate: str = ""
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
            # How this one has to be handled before it is any use. Declared here rather
            # than in a form, because the bench draws every editor from this list — so
            # a new preparation rule is one Field and appears in the UI without a line
            # of template changing. Defaults match `rules/herbprep.Prep`, which is what
            # keeps the 161 already authored behaving exactly as they did.
            Field("needs_extraction", "Must be extracted first", type="choice",
                  choices=("no", "yes"),
                  help="In a shell, a pod or a gland. Nothing else can be done to it "
                       "until it is out."),
            Field("volatile", "Volatile", type="choice", choices=("no", "yes"),
                  help="Must be neutralised before it can be ground."),
            Field("can_grind", "Can be ground", type="choice", choices=("yes", "no")),
            Field("mix_raw", "Can be mixed raw", type="choice", choices=("yes", "no"),
                  help="No means it has to be ground first."),
            Field("brew_raw", "Can be brewed raw", type="choice", choices=("yes", "no"),
                  help="No means it has to be ground first. This also decides whether "
                       "it can be infused into a tincture raw."),
            Field("animal", "Animal part", type="choice", choices=("no", "yes"),
                  help="Spoils in 48 hours unpreserved, rather than a week."),
            Field("liquid", "Already a liquid", type="choice", choices=("no", "yes"),
                  help="A sap, an oil, a gall, an essence. Only a liquid can be "
                       "distilled; anything else has to be brewed into one first. "
                       "Left unset, the ingredient's own name decides."),
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
    "races": Kind(
        id="races", label="Races", folder="races", key="races",
        shipped_loader="rules.races:shipped",
        derive="rules.races:for_bench",
        validate="rules.races:save_from_bench",
        # One-per-line text rather than `effects`: a race's traits ride the sheet's own
        # modifier lists (the feat grammar), not the consumable pipeline, and the form's
        # `list` type is a closed checkbox vocabulary. `rules/races.py` parses each line
        # back and refuses one it cannot read, naming the shape to type.
        fields=_named() + [
            Field("type", "Creature type", type="choice",
                  choices=("humanoid", "fey", "aberration", "monstrous humanoid",
                           "outsider", "dragon", "plant", "construct", "undead")),
            Field("size", "Size", type="choice", choices=("tiny", "small", "medium", "large")),
            Field("speed", "Base speed (ft)", type="number",
                  help="20 slow, 30 normal, 40 fast."),
            Field("mods", "Fixed ability adjustments", type="textarea",
                  help="One per line: con +2, cha -2."),
            Field("choose", "Adjustments the player places", type="textarea",
                  help="One per line: '+2 any' (a human's), or the Race Builder's "
                       "standard '+2 physical', '+2 mental', '-2 any'."),
            Field("modifiers", "Modifiers the sheet applies", type="textarea",
                  help="One per line, the feat grammar: 'skill_mod perception +2 racial', "
                       "'save_mod fort +1 racial', 'combat_mod cmd +4 racial when "
                       "maneuver=bull rush|trip'."),
            Field("tags", "Tags", type="textarea",
                  help="One per line: sense.darkvision.60, sense.low-light, "
                       "immune.sleep.magic, move.fly.30, natural.claws, ferocity. Priced "
                       "from the Race Builder where it names them."),
            Field("budget", "Extra feats and ranks", type="textarea",
                  help="'feats +1', 'ranks +1' — a human's two lines."),
            Field("traits", "Trait lines the forge shows", type="textarea",
                  help="One per line, as the player will read them."),
            Field("languages", "Languages", type="textarea", help="One per line."),
            Field("not_yet", "Not yet", type="textarea",
                  help="What this race has that the sheet cannot read yet — said here "
                       "rather than silently dropped."),
            # Set by the race editor's pickers rather than typed: the anatomy as eidolon
            # evolutions, and where an imported race came from. Declared so the save
            # keeps them — `save_thing` writes only the fields a kind declares.
            Field("evolutions", "Anatomy (eidolon evolutions)", type="list"),
            Field("weapons", "Natural weapons", type="list"),
            Field("origin", "Origin"),
            Field("people_id", "People"),
            Field("world", "World"),
        ],
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
        # The structured half of a spell — its element, everything that grants it a level,
        # its range and area as values — is read out of the fields below rather than stored
        # twice, exactly as a creature's immunities are. `rules.spells:derive` also renders
        # the two mapping-shaped fields back to the one-per-line text this form can edit,
        # because there are six field types here and none of them is a mapping.
        derive="rules.spells:derive",
        # Five fields before this: school, range, duration, saving throw, effects. A spell
        # authored through that form had no components, no casting time, no area, no spell
        # resistance and — the one that mattered — no way to say which class could cast it
        # at what level, so nothing authored here was ever castable. The list below is the
        # tag vocabulary the request asked for, as form fields.
        #
        # The closed vocabularies are written out rather than imported: this module states
        # that nothing here imports a rules module, and a Kind names its loader as a string
        # for that reason. Copies drift, so `tests/test_spells.py` pins each of these
        # against the tuple in `rules/spells.py` that it copies — the drift is caught by a
        # test rather than by a player finding a school the filter does not know.
        fields=_named() + [
            Field("school", "School", type="choice",
                  choices=("abjuration", "conjuration", "divination", "enchantment",
                           "evocation", "illusion", "necromancy", "transmutation",
                           "universal")),
            Field("subschool", "Subschool"),
            Field("element", "Element", type="choice",
                  choices=("acid", "cold", "electricity", "fire", "force", "negative",
                           "positive", "sonic", "untyped"),
                  help="Left empty, the descriptors below decide it."),
            # Free text and not a checkbox list, because the 28 canonical descriptors live
            # in the content file and this module cannot read it at import. What is typed
            # here is checked against that file on save, so a made-up descriptor is refused
            # rather than quietly accepted — a descriptor is a rules fact, and a guessed one
            # changes what the spell does.
            Field("descriptors", "Descriptors", help="Comma separated: fire, curse. Only "
                                                     "the book's own 28 are accepted."),
            Field("level_available", "Available at", type="textarea",
                  help="One per line, ending in the spell level: 'wizard 3', "
                       "'domain fire 3', 'bloodline efreeti 3', 'patron elements 3', "
                       "'mystery flame 3', 'elemental school fire 3'. A class line is what "
                       "makes it castable."),
            Field("casting_time", "Casting time",
                  help="standard action, swift action, 1 round, 10 minutes."),
            Field("components", "Components", type="list",
                  choices=("V", "S", "M", "F", "DF")),
            Field("component_cost", "Material cost"),
            Field("range", "Range",
                  help="As printed: touch, personal, close (25 feet + 5 feet/2 levels). "
                       "The distance is read out of this line."),
            Field("area", "Area",
                  help="As printed: 20-foot-radius spread. The shape is read out of it."),
            Field("effect", "Effect"),
            Field("targets", "Targets"),
            Field("duration", "Duration"),
            Field("dismissible", "Dismissible", type="choice", choices=("no", "yes")),
            # Free text, not a dropdown: the corpus writes 40 distinct saving-throw lines
            # and 15 spell-resistance ones — "yes (harmless, object)", "no and yes (see
            # text)" — and a select that does not offer what a shipped spell already says
            # blanks the field the moment somebody opens it to change something else.
            Field("saving_throw", "Saving throw",
                  help="Reflex half, Will negates (harmless), none."),
            Field("spell_resistance", "Spell resistance", help="yes, no, yes (harmless)."),
            Field("scaling", "Damage or healing formula",
                  help="1d6/level, max 10d6 · 1d8/2 levels, max 5d8 · 2d4 · "
                       "1d8+1/level, max +5. The effects below use it at the caster's own "
                       "level."),
            Field("effects", "Effects", type="effects"),
            Field("source", "Source"),
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
