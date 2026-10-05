"""A druid's animal companion: the nature bond's other half.

The owner, 2026-10-04: *"The druid class does not work I was given no choice for my
natures bond and I dont think we have domains or animal bonds set up yet to make the
natures bond work."* Nothing existed — the sheet printed "No animal companion, familiar,
cohort or mount" as a static sentence, and `gm/companions.py` is about people who walk
beside you, not about a wolf that grows with you.

**What the book says** (Core Rulebook, Druid: Animal Companions; d20pfsrd, read
2026-10-04): a companion's Hit Dice, base attack, saves, skill ranks, feats, natural armour
bonus, Str/Dex bonus, bonus tricks and specials (link, share spells, evasion, devotion,
multiattack, improved evasion) are a table indexed by the druid's level, and each animal
has starting statistics plus a 4th- or 7th-level advancement. All of it is in
content/companions/animal-companions.json, transcribed from that page; nothing here
authors a number.

**Its numbers are derived, never printed.** A companion is not the bestiary's animal: the
bestiary wolf is a 2 HD block whose numbers are flat (`flat_attack`, `flat_saves`), and
flat numbers cannot grow. So the companion is an actor whose `level` is its Hit Dice and
whose class is the companion progression (`progression_classes`, resolved by
`classes.get` but kept out of the playable list): three-quarter BAB and good Fortitude and
Reflex at its Hit Dice is exactly the table's BAB and save columns, all twenty rows. What
the table indexes by DRUID level — the Str/Dex bonus, the natural armour bonus, the
advancement, the specials as tags — rides one `ActiveEffect` through the one applicator,
source `companion:<master ref>`, so removing the bond removes every number it gave.

**Re-derived, not remembered.** `sync` reads the master's level and lays the table's row
over the companion again: at arrival, on every campaign load (`Campaign.load`), and
whenever a caller that changed the druid's level asks. A druid who reaches 7th finds a
Large wolf on the next load with nothing having written "Large" anywhere by hand. The
same reason `classes.apply` runs on every load: a corrected table must reach companions
already in play.

**It obeys in character.** The owner's ruling, 2026-10-01: companions take spoken orders
"as their character dictates". The companion holds `bond.travels-with-you` through the
company door `goods.deliver` opened for a bought mount, so it is a companion to every
reader in `gm/companions.py` — spoken orders, its own turns, the refusal to turn on the
party — and `character_words` is what its character IS: an animal that knows a handful
of tricks and its druid's voice, not sentences.

Prior art checked before building: Ultimate Campaign's "Controlling Companions" (the book's
own three models; this follows GM control, per the ruling), and Pathfinder Kingmaker /
Wrath of the Righteous, which ship companions as full party members with the druid's
level driving the companion's table — the shape here. What they do and this refuses: a
direct-control panel (the owner's ruling) and stored per-level copies of the stat block
(a corrected table would never reach a save).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

# The tag a companion holds on its bond effect — the prefix question every reader asks.
BOND_TAG = "bond.animal-companion"
BOND_KEY = "animal-companion"

# Names a player writes for the animals the book lists under one entry.
_ALIASES = {
    "lion": "big cat", "tiger": "big cat", "cat, big": "big cat", "big-cat": "big cat",
    "cheetah": "small cat", "leopard": "small cat", "cat, small": "small cat",
    "small-cat": "small cat",
    "eagle": "bird", "hawk": "bird", "owl": "bird",
    "alligator": "crocodile",
    "velociraptor": "deinonychus", "dinosaur": "deinonychus",
    "constrictor": "constrictor snake", "snake, constrictor": "constrictor snake",
    "constrictor-snake": "constrictor snake",
    "snake, viper": "viper",
}


@lru_cache(maxsize=1)
def document() -> dict:
    """The shipped document. Read from the install, never from the data directory."""
    from django.conf import settings

    path = Path(settings.BASE_DIR) / "content" / "companions" / "animal-companions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def animals() -> dict[str, dict]:
    return dict(document().get("animals") or {})


def key_for(name) -> str:
    """"Wolf", "a tiger", "big-cat" -> the document's key, or ""."""
    text = " ".join(str(name or "").replace("_", " ").split()).lower()
    for article in ("a ", "an ", "the "):
        if text.startswith(article):
            text = text[len(article):]
    text = _ALIASES.get(text, text)
    return text if text in animals() else ""


def name_of(key: str) -> str:
    entry = animals().get(key_for(key)) or {}
    return str(entry.get("name") or key)


def short_name(key: str) -> str:
    """"Big cat (lion or tiger)" -> "big cat": what the companion is called in the scene."""
    return name_of(key).split(" (")[0].strip() or key


@lru_cache(maxsize=1)
def progression_classes() -> dict[str, dict]:
    """The companion's progression, shaped as `classes.all_classes` shapes a class."""
    cls = dict(document().get("progression_class") or {})
    if not cls:
        return {}
    cls["good_saves"] = tuple(cls.get("good_saves") or ())
    cls["class_skills"] = tuple(cls.get("class_skills") or ())
    cls["proficiencies"] = tuple(cls.get("proficiencies") or ())
    return {str(cls["id"]).lower(): cls}


def row(edl: int) -> dict | None:
    """The base statistics row for this effective druid level, or None below 1st."""
    edl = int(edl or 0)
    if edl < 1:
        return None
    rows = document().get("progression") or []
    return dict(rows[min(edl, len(rows)) - 1]) if rows else None


def effective_level(master, offset: int = 0) -> int:
    """The druid level the table is read at. Nature bond: her druid level. The Animal
    domain's companion: level - 3 (Core Rulebook, Animal domain), which can be 0 — no
    companion yet."""
    return max(0, int(getattr(master, "level", 1) or 1) + int(offset or 0))


def body(animal_key: str, edl: int) -> dict:
    """Everything the animal and the table make of its body at this druid level.

    The advancement is the book's: "4th-Level Advancement: Size Medium; Attack bite (1d6);
    Ability Scores Str +4, Dex -2, Con +2" — laid over the starting statistics from that
    level on, never instead of them.
    """
    animal = animals().get(key_for(animal_key)) or {}
    r = row(edl) or {}
    adv = animal.get("advances") or {}
    advanced = bool(adv) and edl >= int(adv.get("at", 99))
    deltas: dict[str, int] = {}
    if advanced:
        for ab, n in (adv.get("abilities") or {}).items():
            deltas[ab] = deltas.get(ab, 0) + int(n)
    bonus = int(r.get("str_dex", 0) or 0)
    if bonus:
        for ab in ("str", "dex"):
            deltas[ab] = deltas.get(ab, 0) + bonus
    tags = [f"sense.{s}" for s in animal.get("senses") or ()]
    if advanced:
        tags += [f"sense.{s}" for s in adv.get("senses") or ()]
        tags += [str(t) for t in adv.get("tags") or ()]
    for mode, feet in (animal.get("moves") or {}).items():
        tags.append(f"move.{mode}.{int(feet)}")
    specials = document().get("special_tags") or {}
    had: list[str] = []
    for rr in (document().get("progression") or [])[:max(0, min(int(edl), 20))]:
        for sp in rr.get("special") or ():
            if sp not in had:
                had.append(sp)
    tags += [specials[s] for s in had if s in specials]
    attacks = [dict(a) for a in animal.get("attacks") or ()
               if int(a.get("from_level", 1) or 1) <= edl]
    return {
        "animal": key_for(animal_key), "edl": int(edl),
        "hd": int(r.get("hd", 1) or 1),
        "size": str((adv.get("size") if advanced and adv.get("size") else None)
                    or animal.get("size") or "medium"),
        "speed": int(animal.get("speed", 30) or 0),
        "natural_armour": int(animal.get("natural_armour", 0) or 0)
        + (int(adv.get("natural_armour", 0) or 0) if advanced else 0)
        + int(r.get("natural_armour", 0) or 0),
        "abilities": dict(animal.get("abilities") or {}),
        "deltas": deltas,
        "tags": [t for i, t in enumerate(tags) if t and t not in tags[:i]],
        "attacks": attacks,
        "special": list(animal.get("special") or ())
        + (list(adv.get("special") or ()) if advanced else []),
        "specials": had,
        "tricks": int(r.get("tricks", 0) or 0),
        "skills": int(r.get("skills", 0) or 0),
        "feats": int(r.get("feats", 0) or 0),
        "advanced": advanced,
    }


# --- the bond on the companion ----------------------------------------------------------

def bond_of(actor):
    """The companion's bond effect, or None for anybody else."""
    for e in getattr(actor, "effects", None) or ():
        if BOND_TAG in (e.tags or ()):
            return e
    return None


def is_animal_companion(actor) -> bool:
    return actor is not None and bond_of(actor) is not None


def master_ref(actor) -> str:
    bond = bond_of(actor)
    return str((bond.payload or {}).get("master") or "") if bond else ""


def companions_of(scene, master) -> list:
    """Every animal companion in the scene bonded to this character."""
    ref = getattr(master, "ref", "")
    return [a for a in scene.people.values()
            if a is not master and is_animal_companion(a) and master_ref(a) == ref]


def natural_weapon_doc(actor) -> dict | None:
    """The companion's attacks in the race-document shape `Actor.natural_weapon` reads —
    `weapons` with damage by size — so a wolf's bite is built by the same code as a
    world people's bite, and grows a die when the advancement makes the wolf Large."""
    bond = bond_of(actor)
    if bond is None:
        return None
    pay = bond.payload or {}
    return {"weapons": body(str(pay.get("animal") or ""), int(pay.get("edl", 1) or 1))
            ["attacks"]}


def _apply(companion, master, animal_key: str, edl: int, tricks=None,
           origin: str = "") -> bool:
    """Lay the table's row for `edl` over the companion. True when anything moved.

    The fields written here — `level` (its Hit Dice), `size`, `speed`, `natural_armour`
    and the rolled `hp_base` — are derived from the document and the master's level on
    every call, so a save can never carry a stale one past the next load. Damage taken
    is kept: a wolf at 9 of 13 that grows to 22 is at 18.
    """
    from . import states
    from .activeeffect import ActiveEffect

    b = body(animal_key, edl)
    prior = bond_of(companion)
    before = (companion.level, companion.size, companion.natural_armour,
              dict((prior.payload or {})) if prior else {})
    # Unclamped: a wolf at -3 is dying, and growing a Hit Die must not stand it up.
    wounds = int(companion.hp_max) - int(companion.hp) if prior else 0
    pay = dict((prior.payload or {}) if prior else {})
    tricks = list(tricks if tricks is not None else pay.get("tricks") or [])
    offered = list(document().get("tricks") or [])
    tricks = [t for t in tricks if t in offered][:b["tricks"]]
    if len(tricks) < b["tricks"]:
        tricks += [t for t in offered if t not in tricks][:b["tricks"] - len(tricks)]
    companion.char_class = "animal companion"
    companion.level = b["hd"]
    companion.size = b["size"]
    companion.speed = b["speed"]
    companion.natural_armour = b["natural_armour"]
    companion.abilities = dict(b["abilities"])
    mods = [{"kind": "ability_mod", "target": ab, "amount": n}
            for ab, n in sorted(b["deltas"].items()) if n]
    companion.apply_effect(ActiveEffect(
        name=f"{getattr(master, 'name', 'their druid')}'s animal companion",
        kind="bond", key=BOND_KEY, source=f"companion:{getattr(master, 'ref', '')}",
        origin=origin or pay.get("origin") or "class:nature bond",
        duration="until-dismissed",
        tags=(BOND_TAG, "type.animal", *b["tags"]),
        modifiers=mods,
        payload={"animal": b["animal"], "master": getattr(master, "ref", ""),
                 "master_name": getattr(master, "name", ""), "edl": int(edl),
                 "tricks": tricks, "origin": origin or pay.get("origin")
                 or "class:nature bond"}))
    # Hit points: the PFS average the document cites, 4.5 per Hit Die rounded down, with
    # Constitution added by `hp_max` itself (so the advancement's +4 Con follows).
    companion.hp_base = int(4.5 * b["hd"])
    companion.hp = int(companion.hp_max) - wounds if prior else int(companion.hp_max)
    _ = states
    after = (companion.level, companion.size, companion.natural_armour,
             dict(bond_of(companion).payload or {}))
    return before != after


def make(scene, master, animal_key: str, *, tricks=None, offset: int = 0,
         origin: str = "class:nature bond", name: str = ""):
    """A new companion, in the scene, travelling with its druid. Returns the actor.

    Through the company door `goods.deliver` opened for a bought mount: made, `Scene.add`
    (the arrival door, which stamps the party's place), and `bond.travels-with-you` under
    `company:<ref>` so the `company` op's "leave" parts with it like anybody else — and
    so every companion reader in `gm/companions.py` hears the druid's spoken orders.
    """
    from . import bestiary, states
    from .activeeffect import ActiveEffect
    from .sheet import from_dict

    key = key_for(animal_key)
    if not key:
        raise LookupError(f"no companion animal {animal_key!r}; one of "
                          f"{', '.join(sorted(animals()))}.")
    edl = effective_level(master, offset)
    if edl < 1:
        raise ValueError(f"{getattr(master, 'name', 'they')} has no companion before an "
                         f"effective druid level of 1.")
    b = body(key, edl)
    first = (b["attacks"] or [{"key": "unarmed"}])[0]["key"]
    # The player's own name for it when they gave one ("Ash"), else what it is ("wolf"),
    # told apart from anybody here already called that.
    called = str(name or "").strip() or short_name(key).lower()
    data = {
        "name": called if name or scene is None else bestiary.name_apart(scene, called),
        # No race: a wolf is not a human, and the sheet's default race would hand it
        # `race.human` and a human's body.
        "kind": "npc", "race": "", "class": "animal companion", "level": b["hd"],
        "size": b["size"], "speed": b["speed"], "abilities": dict(b["abilities"]),
        "weapons": [], "equipped": "unarmed",
        "hp": 1, "hp_max": 1,
        "notes": f"{getattr(master, 'name', 'A druid')}'s animal companion.",
    }
    animal = from_dict(data, ref=bestiary.next_ref(scene) if scene is not None else "c1")
    _apply(animal, master, key, edl, tricks=tricks, origin=origin)
    # Its teeth after its bond: the bite is read off the bond's animal, so until the bond
    # is on it the load-time weapon check knows no "bite". A save loads the effects
    # before it checks the weapon, so a reload needs no such order.
    animal.weapons = [a["key"] for a in b["attacks"]]
    animal.equipped = first
    animal.hp = animal.hp_max
    if scene is not None:
        scene.add(animal)
    source = f"company:{animal.ref}"
    animal.apply_effect(ActiveEffect(
        name="travels with you", kind="bond", key=f"{source}:travels", source=source,
        origin=origin, duration="until-dismissed", tags=(states.TRAVELS_WITH_YOU,)))
    return animal


def wanted(master) -> dict | None:
    """{animal, offset, tricks, name} when this character's class choices call for a
    companion, else None. Read off the sheet's `class_choices` and the class document,
    never off the class name, so a homebrew class offering a companion is served too."""
    from . import classes as classes_mod

    answers = getattr(master, "class_choices", None) or {}
    for choice in classes_mod.choices_for(getattr(master, "char_class", ""),
                                          int(getattr(master, "level", 1) or 1)):
        option = classes_mod.option_taken(choice, answers)
        if option and option.get("kind") == "animal companion":
            said = answers.get(str(choice.get("id"))) or {}
            said = said if isinstance(said, dict) else {}
            pick = key_for(said.get("pick"))
            if pick:
                return {"animal": pick, "offset": int(option.get("level_offset", 0) or 0),
                        "tricks": list(said.get("tricks") or []),
                        "name": str(said.get("name") or "").strip()}
    return None


def arrive_with(scene, master):
    """At the start of a campaign: the companion the character chose comes with them.

    Only when the choice asks for one and none is here already — a companion that died
    is not raised by a reload (the book's replacement takes 24 hours of prayer, which is
    listed under `not_yet`). Returns the companion, or None.
    """
    want = wanted(master)
    if want is None or companions_of(scene, master):
        return None
    if effective_level(master, want["offset"]) < 1:
        return None
    return make(scene, master, want["animal"], tricks=want["tricks"] or None,
                offset=want["offset"], name=want["name"])


def sync(scene) -> list[str]:
    """Re-derive every companion in the scene from its master's level. Returns a sentence
    for each that changed, for a caller that wants to say so (a level-up)."""
    said: list[str] = []
    for actor in list(scene.people.values()):
        bond = bond_of(actor)
        if bond is None:
            continue
        pay = bond.payload or {}
        master = scene.people.get(str(pay.get("master") or ""))
        if master is None:
            continue                  # parted, or the druid is elsewhere: keep as it was
        want = wanted(master)
        offset = want["offset"] if want and want["animal"] == pay.get("animal") else 0
        edl = effective_level(master, offset)
        if edl < 1:
            continue
        old_hd = actor.level
        if _apply(actor, master, str(pay.get("animal") or ""), edl):
            if actor.level != old_hd:
                said.append(f"{actor.name} grows with {master.name}: "
                            f"{actor.level} Hit Dice now.")
    return said


# --- words: what the narrator and the sheet are told -------------------------------------

def character_words(scene, actor) -> str:
    """Who an animal companion is, in words, for its own turn (`gm/companions.py`).

    The ruling's "as their character dictates", for an animal: Int 1 or 2, so it hears its
    druid's tone and the tricks it knows, not sentences — an order that is one of its
    tricks it carries out readily; anything else it may only follow as far as an animal
    could make sense of it. Its bond makes it loyal, never servile (it will not walk into
    fire for a word). No numbers.
    """
    bond = bond_of(actor)
    pay = (bond.payload or {}) if bond else {}
    master = str(pay.get("master_name") or "the player")
    tricks = [str(t) for t in pay.get("tricks") or []]
    animal = (short_name(str(pay.get("animal") or "")) or "animal").lower()
    knows = (f"it knows these tricks by word and gesture: {', '.join(tricks)}"
             if tricks else "it has learned no tricks yet")
    return (f"{actor.name} is {master}'s animal companion — a {animal} bound to them by "
            f"nature's bond, loyal to them before anyone. It is an animal: it understands "
            f"{master}'s voice and tone, not sentences; {knows}. An order that is one of "
            f"its tricks it does readily, as a {animal} would; anything else it follows "
            f"only as far as an animal can make sense of it, and it will not throw itself "
            f"into certain death on a word.")


def sheet_lines(scene, master) -> list[dict]:
    """The sheet's Companions line: each companion, what it is, and the table's row."""
    out = []
    for comp in companions_of(scene, master) if scene is not None else []:
        pay = (bond_of(comp).payload or {})
        b = body(str(pay.get("animal") or ""), int(pay.get("edl", 1) or 1))
        out.append({
            "ref": comp.ref, "name": comp.name, "animal": name_of(b["animal"]),
            "edl": b["edl"], "hd": comp.level, "size": comp.size,
            "hp": comp.hp, "hp_max": comp.hp_max, "ac": comp.ac(),
            "bab": comp.bab,
            "saves": {s: sum(m.value for m in comp.save_modifiers(s))
                      for s in ("fort", "ref", "will")},
            "abilities": {ab: comp.ability_score(ab)
                          for ab in ("str", "dex", "con", "int", "wis", "cha")},
            "attacks": [f"{a['name']}" + (f" ×{a['count']}" if a.get("count", 1) > 1 else "")
                        + f" ({(a.get('damage') or {}).get(comp.size, '')})"
                        + (f" plus {a['rider']}" if a.get("rider") else "")
                        for a in b["attacks"]],
            "tricks": list(pay.get("tricks") or []),
            "specials": b["specials"], "special": b["special"],
            "dead": comp.has_state("state.down.dead"),
        })
    return out


def wanted_but_absent(scene, master) -> str:
    """A sentence for a character who chose a companion that is not in the scene."""
    want = wanted(master)
    if want is None or (scene is not None and companions_of(scene, master)):
        return ""
    return (f"{getattr(master, 'name', 'They')} took an animal companion "
            f"({name_of(want['animal']).lower()}) through nature's bond; it is not here.")
