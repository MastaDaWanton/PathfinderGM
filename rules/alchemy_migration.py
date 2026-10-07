"""Old saves meet the new alchemy (docs/alchemy-revamp-plan.md §18; contracts §1, wave 2,
lane I). The owner's rulings: Q10.1 **convert** ("Alchemist levels above 3 become endless
levels, with perks picked on first load. Old products stay usable and sellable"), Q10.2
**keep every potion id and `holds_spell` exactly** ("a stored potion still stands in for its
spell").

What a save from before the revamp can hold, measured on the 254 things the pre-revamp code
makes (`tests/alchemy_migration/old-items.json`, generated from master 067e516's own
`alchemist.preview`) and on read-only copies of the owner's saves (2026-10-07: four
campaigns and their backups, every one an Alchemist 1 with 0 mastery and no alchemist work,
so the corpus is what this is measured on):

- **Old work**: a plain shelf row with `craft: "alchemist"`, flat `specs` and the
  `from_materials` its chain used. Loaded on the revamped tree without this module, the
  bench showed every one as "Old work" (lane F), and a potion was a flat copy of a spell's
  effects that the drink door ran as written.
- **Bought goods that did nothing**: before lane H a counter or the outfitter delivered
  `Stock(base="antitoxin", craft="")` with no document at all (lane H found the defect in
  `goods.deliver`; its test `test_an_old_bought_alchemists_fire_sells_for_half...`). An old
  save still carries those jars.
- **Progress**: `world_classes["alchemist"]` at any level, levels 4 and 5 granting nothing
  now; `crafted` keyed by the old product names (the old view's `recipe` was
  `result.name.lower()`).
- **Saved chains**: `campaign.recipes` rows with `craft: "alchemy"` (the old /craft/ view).

**What converts, and onto what** (contracts §6, lane F's product records: ids and grades,
rebuilt from the record on every load):

1. **Spell potions** become the formula record for their spell (`formulae.for_spell`, the
   authored one of the 44 first: lane E kept their ids), with `holds_spell` and
   `caster_level` copied exactly (Q10.2). The record's build lays the spell through the
   drink door and the enchanter still reads `holds_spell` off the shelf row.
2. **The old recipe table's classics** (docs/alchemy.md at 067e516, "Item | Materials |
   Chain"): a product made from exactly one of its material sets IS that classic — the old
   docs told the player so — and becomes the formula's record at Sound, the book's numbers
   (Q1.4: "the book's numbers win"; the questions doc §11 lists the old alchemist's fire as
   the contradiction this fixes). Bladeguard and vermin repellent have no formula row now
   and fall to 3.
3. **Everything else stays old work, exactly as it was** (Q10.1's "old products stay usable
   and sellable, marked as old work"), read as before. Measured, not assumed: re-deriving a
   house compound through the new pool would change what it does — lane D's data pass gave
   nearly every reagent a drawback the old one never had, and a family's slots drop traits
   the old chain kept — so a re-derived "Naphtha Sealed Flask" would come out a different
   thing under the same name. The prior art agrees: Minecraft's 1.9 potion change mapped the
   old numeric potions onto the new named ones by a fixed table, and what the table did not
   name was left as it was (minecraft.wiki/w/Potion; the "OldWorldFix" tools exist for the
   leftovers). The DataFixerUpper internals behind it could not be confirmed from a primary
   source and are not relied on.
4. **Bought goods that did nothing** become what a counter sells today
   (`goods.alchemy_stock`, lane H's one door), so an old antitoxin gives its +5 and an old
   flask of alchemist's fire can be thrown. Matched by the counter's own names
   (`goods.CLASSIC_GEAR`) or a classic's or an authored potion's exact name, and only for a
   jar no craft wrote and no document describes.

**Never guess, never drop.** A converted record keeps the old row beside it in
`migrated.from` for one version (`undo_migration`), as the enchanting conversion does
(rules/enchanter.py, "the old record kept beside it"; Path of Exile's legacy items were the
complaint that shaped that: a thing that WORKS by new numbers while SHOWING old ones). What
nothing maps keeps working as before and is named in the one-time notice.

**The one-time notice** (`conversions`, `conversion_seen`, the enchanter's names so the bench
can show both the same way): every converted record the player has not been shown, with what
changed, and one entry for the alchemist ("Alchemist 5: four perk picks wait at the bench";
the formulae and materials a converted alchemist now knows; old work kept as it was; saved
chains). The alchemist's entry is written once, by `settle`, into the knowledge store's
bookkeeping slot (`NOTE_SLOT`, underscored like `knowledge.SEEDED` so no reader takes it for
a material).

**Knowledge** (plan §18.5): a converted alchemist knows every formula whose product they hold
(converted, or held as old work holding a spell) or have made (an old `crafted` key that is a
formula's name), learned "made before the new bench" (`formulae.HOW_WORDS["migration"]`);
and every property of every material in a product they hold, where the save records it
(`from_materials`). The four classics are the bench's to teach on its first visit
(`alchemist.known_starting`), as for every alchemist.
"""
from __future__ import annotations

import copy

TRACK_ID = "alchemist"
MIGRATION_STAMP = "alchemy-18"
# The bookkeeping slot in `Actor.herb_known` the alchemist's notice lives in. Underscored, so
# every reader of the store skips it (knowledge.py's `_seeded` rule).
NOTE_SLOT = "_alchemy_v2"
NOTE_KEY = "alchemist"
# How a formula learned here reads in the Formulary (formulae.HOW_WORDS).
HOW = "migration"
KNOWN_HOW = "worked before the new bench"
# The old shape words (rules/alchemist.py SHAPE_WORDS at 067e516), for telling the player
# which old row is which.
OLD_RECIPES_CRAFT = "alchemy"

# The old recipe table (docs/alchemy.md at 067e516, "Item | Materials | Chain"), by the SET
# of materials a chain used — the old `_potion_for` rule ("the recipe is the recipe"): exact,
# never a near match. Acid flask's "or ankheg acid sac + a solvent" is its second row.
OLD_CLASSICS: dict[frozenset, str] = {
    frozenset({"brimstone", "naphtha", "clay-flask"}): "alchemists-fire",
    frozenset({"oil-of-vitriol", "lead-glass-vial"}): "acid-flask",
    frozenset({"ankheg-acid-sac", "distilled-water", "lead-glass-vial"}): "acid-flask",
    frozenset({"pine-pitch", "giant-frog-mucus", "turpentine", "waxed-bladder"}): "tanglefoot-bag",
    frozenset({"storm-quartz", "saltpetre", "distilled-water", "brass-casing"}): "thunderstone",
    frozenset({"smoke-resin", "lamp-black", "saltpetre", "distilled-water"}): "smokestick",
    frozenset({"phosphorus", "brimstone", "turpentine"}): "tindertwig",
    frozenset({"fire-beetle-gland", "phosphorus", "distilled-water"}): "sunrod",
    frozenset({"adder-venom-gland", "willow-charcoal", "bitter-aloes", "white-vinegar"}): "antitoxin",
    frozenset({"silver-salt", "camphor", "distilled-water"}): "antiplague",
    frozenset({"slick-jelly", "tallow", "turpentine"}): "alchemical-grease",
    frozenset({"itchweed-floss"}): "itching-powder",
    frozenset({"quicklime", "brine"}): "alkali-flask",
    frozenset({"everfrost-salt", "distilled-water"}): "liquid-ice",
    frozenset({"phosphorus", "saltpetre", "strong-spirits"}): "flash-powder",
    frozenset({"sal-volatile", "sal-ammoniac"}): "smelling-salts",
    frozenset({"saints-tallow", "sunmetal-filings", "rectified-spirits"}): "holy-weapon-balm",
}


def _norm(text) -> str:
    return " ".join(str(text or "").split()).strip().lower()


# --- what is old ----------------------------------------------------------------------------

def is_old_work(d) -> bool:
    """A shelf row the pre-revamp alchemist made: `craft: "alchemist"`, flat specs, the
    materials its chain used, and no record (`alchemy`). Not one: a new record, anything in
    progress, a bought product (lane H's `alchemy_stock` writes no materials)."""
    if not isinstance(d, dict) or str(d.get("craft") or "") != TRACK_ID:
        return False
    if isinstance(d.get("alchemy"), dict) or d.get("work"):
        return False
    return bool(d.get("from_materials"))


def _bought_formula(d) -> str | None:
    """The formula an inert bought jar was sold as, or None. Only a jar no craft wrote,
    with no document, no spell and no record: anything else is somebody's own work."""
    if not isinstance(d, dict) or str(d.get("craft") or ""):
        return None
    if d.get("specs") or d.get("holds_spell") or isinstance(d.get("alchemy"), dict):
        return None
    if d.get("work") or d.get("magic") or d.get("from_materials") or d.get("from_ingredients"):
        return None
    from . import formulae, goods

    name = _norm(d.get("base") or d.get("name"))
    if not name:
        return None
    fid = goods.CLASSIC_GEAR.get(name)
    if fid:
        return fid
    for fid, row in formulae.all().items():
        if not row.get("authored", True) or not row.get("brewable", True):
            continue
        if row.get("kind") in ("classic", "spell") and _norm(row.get("name")) == name:
            return fid
    return None


def _classic_of(d: dict) -> str | None:
    from . import formulae

    fid = OLD_CLASSICS.get(frozenset(str(m).strip().lower() for m in d.get("from_materials") or ()))
    return fid if fid and formulae.get(fid) is not None else None


def _spell_row(d: dict) -> dict | None:
    from . import formulae

    sid = str(d.get("holds_spell") or "").strip().lower()
    return formulae.for_spell(sid) if sid else None


def target_of(d) -> str | None:
    """What an old row converts onto: "spell:<fid>", "classic:<fid>", "bought:<fid>", or
    None when it stays as it was."""
    if is_old_work(d):
        if d.get("holds_spell"):
            row = _spell_row(d)
            return f"spell:{row['id']}" if row is not None else None
        fid = _classic_of(d)
        return f"classic:{fid}" if fid else None
    fid = _bought_formula(d)
    return f"bought:{fid}" if fid else None


# --- converting one row -----------------------------------------------------------------------

def _rendered(specs) -> list[str]:
    from . import effectspec

    out = []
    for s in specs or ():
        if not isinstance(s, dict):
            continue
        try:
            out.append(effectspec.render(s).rstrip("."))
        except Exception:  # noqa: BLE001 - an old spec the renderer cannot read keeps its type
            out.append(str(s.get("type") or "an effect"))
    return out


def _record_for(kind: str, fid: str, d: dict) -> dict:
    from . import alchemy_items as items
    from . import formulae

    row = formulae.get(fid) or {}
    count = max(1, int(d.get("count", 1) or 1))
    level = 1
    if row.get("kind") == "spell" and row.get("spell_level") is not None:
        level = formulae.level_for_spell_level(int(row["spell_level"]))
    vessel = next((m for m in d.get("from_materials") or ()
                   if formulae.vessel_families(m)), None)
    rec = items.new_record(family=str(row.get("family") or "potion"), formula=fid,
                           vessel=vessel, quality_index=items.SOUND, level=level,
                           materials=[str(m) for m in d.get("from_materials") or ()],
                           count=count)
    if kind == "spell":
        # Q10.2: the spell and its caster level, exactly as the old bottle carried them.
        rec["holds_spell"] = d.get("holds_spell")
        rec["spell"] = d.get("holds_spell")
        if d.get("caster_level"):
            rec["caster_level"] = int(d["caster_level"])
        rec["name"] = items.product_name(rec)
        rec["id"] = items._slug(rec["name"])
    # Made before the clock was kept on a shelf: the old bench wrote no minute, so nothing
    # converted here goes off (`gone_off` answers "" for a record with no minute). Writing
    # 0 would make a year-keeping flask "gone off" in any campaign past its first year.
    rec["made_minute"] = None
    return rec


def migrate_old_record(d) -> dict | None:
    """An old row converted onto what the revamp makes, as the shelf row the loader reads
    (`AlchemyStock.as_dict()` for old work, `goods.alchemy_stock(...).as_dict()` for a bought
    jar), or None when `d` is not old alchemy or nothing maps it (it then stays exactly as it
    was). Idempotent by shape: a converted row is a record, or a bought product with a
    document, and neither is old."""
    target = target_of(d)
    if target is None:
        return None
    kind, fid = target.split(":", 1)
    if kind == "bought":
        from . import goods

        st = goods.alchemy_stock(fid)
        if st is None:
            return None
        st.count = max(1, int(d.get("count", 1) or 1))
        return st.as_dict()
    from . import alchemy_items as items

    old = copy.deepcopy(d)
    rec = _record_for(kind, fid, d)
    built = items.build(rec)
    changes: list[str] = []
    was_name = str(d.get("name") or d.get("base") or "")
    if _norm(was_name) != _norm(built["name"]):
        changes.append(f"Now called {built['name']} (it was {was_name}).")
    if kind == "spell":
        changes.append(f"Still holds {d.get('holds_spell')} at caster level "
                       f"{rec.get('caster_level')}: it stands in for the spell as before.")
    before = _rendered(d.get("specs"))
    after = [str(line.get("text") or "").rstrip(".") for line in built.get("lines") or ()
             if line.get("text")]
    if kind == "classic" and sorted(before) != sorted(after):
        from . import formulae

        book = str((formulae.get(fid) or {}).get("name") or fid)
        changes.append(f"Made by the old recipe table, so it is the book's {book} now: was "
                       f"{'; '.join(before) or 'nothing'}; now {'; '.join(after) or 'nothing'}.")
    rec["migrated"] = {"stamp": MIGRATION_STAMP, "from": old, "changes": changes,
                       "seen": False}
    st = items.to_stock(rec, int(rec.get("count") or 1))
    return st.as_dict()


def undo_migration(record) -> dict | None:
    """The old row a converted record was made from, while it is kept (one version)."""
    rec = record.get("alchemy") if isinstance(record, dict) and isinstance(
        record.get("alchemy"), dict) else record
    got = ((rec or {}).get("migrated") or {}).get("from") if isinstance(rec, dict) else None
    return copy.deepcopy(got) if isinstance(got, dict) else None


# --- the alchemist: knowledge and the notice -------------------------------------------------

def _converted(actor):
    """(stock key, AlchemyStock) for every record this module converted."""
    from . import alchemy_items as items

    for key, st in items.records(actor):
        if isinstance((st.record or {}).get("migrated"), dict):
            yield key, st


def _old_rows(actor):
    """(stock key, row) for every old-work row kept as it was."""
    for key, st in (getattr(actor, "stock", None) or {}).items():
        try:
            d = st.as_dict()
        except Exception:  # noqa: BLE001 - a row that cannot say itself is not ours
            continue
        if is_old_work(d):
            yield key, d


def _formula_named(name: str) -> str | None:
    from . import formulae

    n = _norm(name)
    for fid, row in formulae.all().items():
        if row.get("authored", True) and _norm(row.get("name")) == n:
            return fid
    return None


def _recipe_formula(recipe: dict) -> str | None:
    """The formula an old saved chain made: one of the old recipe table's material sets, or
    a spell potion's own recipe (its materials and methods, exactly)."""
    import json

    from django.conf import settings
    from pathlib import Path

    mats = frozenset(str(m).strip().lower() for m in recipe.get("ingredients") or ())
    fid = OLD_CLASSICS.get(mats)
    if fid:
        return fid
    methods = [str(m).strip().lower() for m in recipe.get("methods") or ()]
    try:
        doc = json.loads((Path(settings.BASE_DIR) / "content" / "materials"
                          / "alchemist-spell-potions.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for row in doc.get("potions") or ():
        if frozenset(str(m).lower() for m in row.get("materials") or ()) == mats and \
                [str(m).lower() for m in row.get("methods") or ()] == methods:
            return str(row.get("id"))
    return _formula_named(recipe.get("name") or "")


def _progress(actor):
    return (getattr(actor, "world_classes", None) or {}).get(TRACK_ID)


def _say(names: list[str]) -> str:
    names = [n for n in names if n]
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def settle(actor, recipes=(), *, clock: int | None = None) -> list[str]:
    """The alchemist's half of the conversion, once: what they now know, and the notice's
    lines. Runs only while the actor holds something old (a converted record, old work, or
    `recipes` from the old chain bench) and has no notice yet, so a character who never
    touched the old bench is never written to, and a character who has been settled is
    never settled twice. Returns the lines written ([] when nothing ran)."""
    from . import formulae, knowledge
    from . import worldclass as wc

    store = getattr(actor, "herb_known", None)
    if store is None or NOTE_SLOT in store:
        return []
    converted = list(_converted(actor))
    kept = list(_old_rows(actor))
    old_recipes = [r for r in recipes or () if isinstance(r, dict)
                   and str(r.get("craft") or "") == OLD_RECIPES_CRAFT]
    if not (converted or kept or old_recipes):
        return []
    lines: list[str] = []
    prog = _progress(actor)
    if prog is not None:
        banked = wc.perk_picks_banked(prog)
        if banked:
            lines.append(f"Alchemist {prog.level}: the levels past 3 are endless levels "
                         f"now, and {banked} perk pick{'s' if banked != 1 else ''} wait at "
                         f"the bench. Nothing is spent until you choose.")
    # Formulae: held (converted records name theirs; old work holding a spell), made (an
    # old `crafted` key that is a formula's name), and saved chains that made one.
    learn: list[str] = []
    for _key, st in converted:
        fid = st.record.get("formula")
        if fid:
            learn.append(str(fid))
    for _key, d in kept:
        row = _spell_row(d)
        if row is not None:
            learn.append(row["id"])
    for name in (getattr(prog, "crafted", None) or {}) if prog is not None else ():
        fid = _formula_named(name)
        if fid:
            learn.append(fid)
    recipe_words: list[str] = []
    for r in old_recipes:
        fid = _recipe_formula(r)
        row = formulae.get(fid) if fid else None
        if row is not None:
            learn.append(fid)
            recipe_words.append(f"{r.get('name')} (now the formula {row['name']})")
        else:
            recipe_words.append(str(r.get("name") or "a chain"))
    new = [fid for fid in dict.fromkeys(learn) if formulae.learn(actor, fid, HOW, clock=clock)]
    if new:
        names = [str((formulae.get(f) or {}).get("name") or f) for f in new]
        lines.append(f"You know {len(new)} formula{'e' if len(new) != 1 else ''} from your "
                     f"work at the old bench: {_say(names)}.")
    # Materials: every property of every material in a product held.
    mats: list[str] = []
    for _key, st in converted:
        for m in (undo_migration(st.record) or {}).get("from_materials") or ():
            mats.append(str(m))
    for _key, d in kept:
        mats.extend(str(m) for m in d.get("from_materials") or ())
    learned_mats = []
    for mid in dict.fromkeys(mats):
        doc = knowledge.resolve(mid)
        if doc is None:
            continue
        keys = knowledge.property_keys(doc)
        if keys and knowledge.reveal(actor, mid, keys, KNOWN_HOW):
            learned_mats.append(str(knowledge._field(doc, "name", mid) or mid))
    if learned_mats:
        lines.append(f"You know what {_say(learned_mats)} "
                     f"{'does' if len(learned_mats) == 1 else 'do'}: you worked "
                     f"{'it' if len(learned_mats) == 1 else 'them'} at the old bench.")
    if kept:
        names = sorted({str(d.get("name") or d.get("base") or "") for _k, d in kept})
        lines.append(f"Kept as it was, old work: {_say(names)}. It can be used and sold as "
                     f"before, never worked further; nothing in the new alchemy makes "
                     f"{'it' if len(names) == 1 else 'them'}.")
    if recipe_words:
        lines.append(f"Your saved chains from the old bench are gone (the bench works one "
                     f"step at a time now): {_say(recipe_words)}.")
    store[NOTE_SLOT] = {"stamp": MIGRATION_STAMP, "lines": lines, "seen": False}
    return lines


def settle_campaign(campaign) -> bool:
    """`settle` for everyone in the campaign, the player character with the old chain
    recipes, which are then dropped (plan §18.4). True when anything changed. A campaign
    with no old alchemy is not touched, so it saves byte for byte as it was."""
    scene = getattr(campaign, "scene", None)
    if scene is None:
        return False
    recipes = list(getattr(campaign, "recipes", None) or [])
    old = [r for r in recipes if isinstance(r, dict)
           and str(r.get("craft") or "") == OLD_RECIPES_CRAFT]
    try:
        pc = scene.pc()
    except Exception:  # noqa: BLE001 - a scene without a player character settles its people
        pc = None
    changed = False
    clock = getattr(scene, "clock_minutes", None)
    for actor in list((getattr(scene, "people", None) or {}).values()):
        mine = old if actor is pc else ()
        if settle(actor, mine, clock=clock):
            changed = True
    if old and pc is not None and NOTE_SLOT in (pc.herb_known or {}):
        campaign.recipes = [r for r in recipes if r not in old]
        changed = True
    return changed


def conversions(actor) -> list[dict]:
    """The one-time notice (the enchanter's `conversions` shape): the alchemist's own entry
    first ({"key": "alchemist", "name", "changes", "seen"}), then every converted record not
    yet shown. [] for a save with nothing converted, or once everything has been seen."""
    out: list[dict] = []
    note = (getattr(actor, "herb_known", None) or {}).get(NOTE_SLOT)
    if isinstance(note, dict) and not note.get("seen") and note.get("lines"):
        out.append({"key": NOTE_KEY, "name": "Your alchemy, on the new bench",
                    "changes": list(note.get("lines") or ()), "questions": [],
                    "seen": False})
    for key, st in _converted(actor):
        m = st.record["migrated"]
        if m.get("seen"):
            continue
        out.append({"key": f"stock:{key}", "name": st.name,
                    "changes": list(m.get("changes") or ()), "questions": [],
                    "seen": False})
    return out


def conversion_seen(actor, key: str | None = None) -> None:
    """Mark one notice entry seen (`key` as `conversions` gives it), or all of them."""
    note = (getattr(actor, "herb_known", None) or {}).get(NOTE_SLOT)
    if isinstance(note, dict) and key in (None, NOTE_KEY):
        note["seen"] = True
    for k, st in _converted(actor):
        if key is None or key == f"stock:{k}":
            st.record["migrated"]["seen"] = True


__all__ = ["MIGRATION_STAMP", "NOTE_SLOT", "OLD_CLASSICS", "conversion_seen", "conversions",
           "is_old_work", "migrate_old_record", "settle", "settle_campaign", "target_of",
           "undo_migration"]
