"""Old saves meet the new leatherworking (docs/leatherworking-revamp-plan.md §20; contracts
§11, wave 2, lane I). The owner's ruling, Q9.1 **convert**: "Old leather records are re-derived
as armour records (body = the hide named in `from_materials`), and old masterwork stays
masterwork. Raw hides in the satchel start their clock on load, with a full 48 hours."
Levels past 3 are lane E's (`worldclass.migrate_leatherworker`: kept as perk picks); this is
the items and the satchel.

What a save from before the revamp can hold, measured on the 252 things master 0abad17's own
bench makes (`tests/leather_migration/old-items.json`, generated from its `preview` at
level 5 and saved the way the old /craft/ view saved them) and on one old sheet written by
that build's `to_dict` (`old-save.json`):

- **Old suits**: `kind: crafted`, `craft: leatherworker`, flat `specs`, `armour` the table
  key ("leather" or "studded leather", the old `_armour_key`), `slot: armor`, `masterwork`
  when Tool was the last step, `base` the Stock's NAME ("Deer Armour"). 230 of the corpus.
  Loaded on the revamped tree without this module, lane B's engine already donned one by its
  `armour` key, but as the TABLE row: the masterwork's lighter check penalty and every hide
  number were gone (lane B's note), and the hide's prose was its only "effect".
- **Everything else the old bench made** (cloaks, boots, belts, satchels, straps, barding,
  an untanned "armour piece" with no armour row): flat specs that `_standing_mods` still
  reads when worn. Kept exactly as they were, as old work ("it can be worn or sold, not
  worked further", `leatherworker.OLD_WORK`). Re-deriving them would make a different thing
  under the same name, the reason the alchemy conversion kept its house compounds (rules/
  alchemy_migration.py, point 3); the plan converts suits only, and so does this.
- **Raw hides in the satchel**: bare counts in `inventory` with NO clock. The old skin
  excursion called `pc.carry(mid, n)` without `at_minute` (inventory §0.3, measured:
  `picked_at` was None for everything skinned), and the old bench treated every hide in the
  satchel as raw.

**What converts, and onto what.**

1. **A suit** becomes the forge's crafted record (contracts §4.2, the shape lane E's
   Assemble writes): `base` the table key it was; body = the first hide in `from_materials`
   (grade 2, the tannin it was tanned with); fastenings = the studs that made it studded
   (`steel-studs`, or `cold-iron-studs`: the old rule was "a fitting whose id or name says
   stud"), else a lacing set of its own hide, marked `plain` because nobody chose it (the
   forge migration's `MIGRATED_PLAIN` rule: named, never summed); no lining (the old bench
   never made one). Quality Sound, and **masterwork stays masterwork** at Superior, the
   forge's "masterwork 3". Id and name kept, so the shelf key, the armour slot and the worn
   copy still find it. A hide whose document now allows only other bases (griffon mane:
   padded or quilted cloth) keeps the old record as it was rather than change the suit's
   kind under the player.
2. **Raw hides** become green hide stock on the rack (`leatherworker.put_hide`, the one
   writer), grade 2 **(proposed** in the plan: neither the best nor the worst), their units
   by the hide's size, and the clock **starts on load with a full 48 hours** (salted at once
   if the satchel's salt had kept them, `preserved`), so no save spoils on load.
3. **Tannins, oils, threads and the rest keep their counts**: the rack reads them from the
   satchel as it reads a counter's purchase.

**Never guess, never drop.** A converted record keeps the old one beside it in
`migrated_from` for one version (`undo_migration`), the forge's rule; remove the field in the
release after the one that ships this. A suit the old wear path left in the armour slot (by
name, with the table key untouched, inventory §5) is put on as the engine's `wear` would:
the suit `armour` named goes into the pack unless the pack already has it.

**Telling an old satchel from a new one.** In this build a bare hide in the satchel is a
counter's purchase, sold tanned (`leatherworker._bought_hide`); in a save from before it, a
raw hide. Nothing in the hide says which, so the save does: `stamp_save` marks a sheet this
build writes while it carries a bare hide, and only then (a save with none round-trips byte
for byte, G1). A sheet with the stamp, or the notice, is never converted again.

**The one-time notice** (`conversions`, `conversion_seen`, the enchanter's and alchemy's
names and shape): each converted suit the player has not been shown, with what changed, and
one entry for the satchel and the levels, kept in the knowledge store's bookkeeping slot
(`NOTE_SLOT`, underscored like `knowledge.SEEDED` so no reader takes it for a material).
"""
from __future__ import annotations

import copy

TRACK_ID = "leatherworker"
MIGRATION_STAMP = "leatherworking_v2"
NOTE_SLOT = "_leather_v2"
NOTE_KEY = "leatherworker"
# The old bench's armour rows (`_armour_key` at 0abad17): nothing else was ever written.
OLD_SUITS = ("leather", "studded leather")
# A raw hide converted on load is neither the best nor the worst (plan §20.3, proposed).
MIGRATED_GRADE = 2
# Sound, and the forge's index for old masterwork (blacksmith `_OLD_QUALITY_INDEX`).
SOUND, MASTERWORK = 1, 3


def _lw():
    from . import leatherworker

    return leatherworker


def _doc(mid: str) -> dict | None:
    return _lw().material(str(mid or "").strip().lower())


def _say(names: list[str]) -> str:
    names = [n for n in names if n]
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + f" and {names[-1]}"


# --- what is old -----------------------------------------------------------------------------

def _is_old_leather(d) -> bool:
    """Something the pre-revamp leatherworker made: `craft: leatherworker`, kind crafted, no
    forge pieces, no `leather.*` tags (the step bench's stock), not In progress."""
    if not isinstance(d, dict) or str(d.get("craft") or "") != TRACK_ID:
        return False
    if isinstance(d.get("pieces"), dict) or d.get("work") or d.get("migrated"):
        return False
    if str(d.get("kind") or "crafted") != "crafted":
        return False
    return not any(str(p).startswith("leather.") for p in d.get("properties") or ())


def is_old_suit(d) -> bool:
    """An old leather suit the conversion re-derives: its `armour` is one of the old bench's
    two rows and it went in the armour slot (barding, with no slot, is a mount's)."""
    return (_is_old_leather(d) and str(d.get("armour") or "").strip().lower() in OLD_SUITS
            and str(d.get("slot") or "").strip().lower() == "armor")


def _first(d: dict, kind: str, keep=lambda doc: True) -> tuple[str, dict | None]:
    for mid in d.get("from_materials") or ():
        doc = _doc(mid)
        if doc is not None and str(doc.get("kind") or "") == kind and keep(doc):
            return str(doc.get("id") or mid), doc
    return "", None


def _studs(d: dict) -> tuple[str, dict | None]:
    """The fitting that made an old suit studded: the old `_armour_key` rule, "a fitting
    whose id or name says stud", read off the record's own materials."""
    return _first(d, "fitting", lambda doc: "stud" in
                  f"{doc.get('id', '')} {doc.get('name', '')}".lower())


def target_of(d) -> dict | None:
    """What an old suit converts onto ({"base", "body", "studs", "tannin"}), or None when it
    stays as it was (not an old suit; no hide the catalogue knows; a hide that is now made
    only into other suits)."""
    if not is_old_suit(d):
        return None
    base = str(d.get("armour")).strip().lower()
    body, doc = _first(d, "hide")
    if doc is None:
        return None
    allowed = [str(b).strip().lower() for b in doc.get("allowed_bases") or () if b]
    if allowed and base not in allowed:
        return None
    studs = ""
    if base == "studded leather":
        studs, sdoc = _studs(d)
        if sdoc is None:
            studs = "steel-studs"
    tannin, _ = _first(d, "tannin")
    return {"base": base, "body": body, "studs": studs, "tannin": tannin}


# --- converting one record -------------------------------------------------------------------

def _record_for(d: dict, t: dict) -> dict:
    from . import worldclass as wc

    lw = _lw()
    body = {"material": t["body"], "passes": 0, "grade": MIGRATED_GRADE}
    if t["tannin"]:
        body["tannage"] = t["tannin"]
    if t["studs"]:
        fast = {"material": t["studs"], "passes": 0}
    else:
        # The lacing nobody chose: a set of its own hide, named so the card can say what
        # holds it shut, never summed (forge_items.build skips `plain`).
        fast = {"material": t["body"], "passes": 0, "grade": MIGRATED_GRADE, "form": "lacing",
                "plain": True}
    masterwork = bool(d.get("masterwork"))
    q = MASTERWORK if masterwork else SOUND
    name = str(d.get("name") or d.get("base") or "Leather Armour")
    # The shelf entry's id carries the old jar's concentration ("deer-armour#1"); the item's
    # own id is the slug, as the forge migration reads it.
    rid = str(d.get("id") or lw._slug(name)).split("#", 1)[0] or lw._slug(name)
    doc = _doc(t["body"]) or {}
    info = lw.PRODUCTS["leather armour"]
    return {
        "id": rid, "name": name, "kind": "crafted", "craft": TRACK_ID,
        "count": max(1, int(d.get("count", 1) or 1)),
        "gear": "armour", "base": t["base"], "slot": "armor",
        "quality": wc.quality_name(q).lower(), "quality_index": q, "masterwork": masterwork,
        "pieces": {"body": body, "fastenings": fast}, "quench": None, "finish": [],
        "flaws": [], "marks": [],
        # A plain leather suit is still a base the forge can stud; a studded one is done.
        "base_for": [] if t["studs"] else list(info.get("base_for") or []),
        "product": "leather armour", "tier": str(doc.get("tier") or d.get("tier") or "common"),
        # The old record never said who made it; level 1 cuts nothing from a negative.
        "smith": {"level": 1, "perks": {}},
        "schema": lw.RECORD_SCHEMA, "migrated": MIGRATION_STAMP,
    }


def _changes(d: dict, rec: dict, t: dict) -> list[str]:
    lw = _lw()
    out = [f"Now {'studded leather' if t['studs'] else 'leather armour'} on the forge's armour "
           f"model: body {lw.doc_name(t['body'])}"
           + (f", studded with {lw.doc_name(t['studs']).lower()}" if t["studs"] else
              ", laced with its own hide")
           + ". The hide's own numbers count now; before, it was the table's row and prose."]
    if rec["masterwork"]:
        out.append("Masterwork it was, and masterwork it stays (Superior).")
    return out


def migrate_old_record(d) -> dict | None:
    """An old leather suit re-derived as the forge's crafted record, the shelf row the loader
    reads (`forge_items.ForgedStock.as_dict()`), or None when `d` is not one (it then stays
    exactly as it was). Idempotent by shape: the result has pieces and a `migrated` stamp,
    so it is never old again. The old record is kept beside it (`migrated_from`)."""
    t = target_of(d)
    if t is None:
        return None
    from . import forge_items

    rec = _record_for(d, t)
    rec["migrated_from"] = copy.deepcopy(d)
    rec["migration"] = {"stamp": MIGRATION_STAMP, "changes": _changes(d, rec, t),
                        "seen": False}
    return forge_items.stock_item(rec).as_dict()


def undo_migration(record) -> dict | None:
    """The old record a converted one was made from, while it is kept (one version)."""
    rec = getattr(record, "record", record)
    old = (rec or {}).get("migrated_from") if isinstance(rec, dict) else None
    return copy.deepcopy(old) if isinstance(old, dict) else None


# --- the actor: worn suits, the satchel, the notice --------------------------------------------

def _converted(actor):
    """(stock key, record) for every suit this module converted, in the pack."""
    for key, st in (getattr(actor, "stock", None) or {}).items():
        rec = getattr(st, "record", None)
        if isinstance(rec, dict) and rec.get("migrated") == MIGRATION_STAMP \
                and str(rec.get("craft") or "") == TRACK_ID:
            yield key, rec


def _old_rows(actor):
    """(stock key, row) for old leather work kept as it was."""
    for key, st in (getattr(actor, "stock", None) or {}).items():
        try:
            d = st.as_dict()
        except Exception:  # noqa: BLE001 - a row that cannot say itself is not ours
            continue
        if _is_old_leather(d):
            yield key, d


def _bare_hides(actor) -> list[tuple[str, int]]:
    out = []
    for iid, n in sorted((getattr(actor, "inventory", None) or {}).items()):
        doc = _doc(iid)
        if doc is not None and str(doc.get("kind") or "") == "hide" and int(n or 0) > 0:
            out.append((str(iid), int(n)))
    return out


def stamped(actor) -> bool:
    return NOTE_SLOT in (getattr(actor, "herb_known", None) or {})


def _settle_satchel(actor, now: int) -> list[str]:
    """Raw hides in an old satchel to green hide stock, the clock started now (plan §20.3)."""
    lw = _lw()
    made = []
    for iid, n in _bare_hides(actor):
        salted = bool((getattr(actor, "preserved", None) or {}).get(iid))
        h = lw.make_hide(iid, form="salted" if salted else "green", grade=MIGRATED_GRADE,
                         harvested_at=int(now), salted_at=int(now) if salted else None)
        lw.put_hide(actor, h, n)
        took = actor.spend(iid, n)
        if took != n:          # never: the count was read a line ago. Said, not assumed.
            raise RuntimeError(f"{iid}: moved {n} to the rack but took {took} from the satchel")
        if iid not in actor.inventory:
            actor.picked_at.pop(iid, None)
            actor.preserved.pop(iid, None)
        made.append(f"{lw.doc_name(iid)}" + (f" ×{n}" if n > 1 else "")
                    + (" (salted)" if salted else ""))
    if not made:
        return []
    return [f"The raw hides in your satchel are on the leather rack now as green hides, "
            f"grade {MIGRATED_GRADE}: {_say(made)}. Each has a full 48 hours before it "
            f"spoils unless you salt or tan it, counted from when this save was opened."]


def _redon(actor) -> list[str]:
    """A converted suit the old wear path left in the armour slot by name (inventory §5: the
    table key untouched) is put on as the engine's `wear` puts on a crafted suit
    (`Engine._wear_crafted`): `armour` takes its base, and the suit `armour` named goes into
    the pack unless the pack already has it. No time passes: it was already on."""
    from . import armour as armour_mod
    from . import forge_items, goods

    lines = []
    for name in list(actor.slots.get("armor") or ()):
        rec = actor.worn.get(str(name or "").strip().lower())
        if not (forge_items.is_forged(rec) and rec.get("migrated") == MIGRATION_STAMP
                and rec.get("gear") == "armour"):
            continue
        _kind, key = armour_mod.key_for(str(rec.get("base") or ""))
        key = key or str(rec.get("base") or "").lower()
        if not key or actor.armour == key:
            continue
        was = actor.armour
        if was not in ("", "none", None) and not any(
                goods.canonical(k) == was for k in actor.goods):
            actor.goods[was] = actor.goods.get(was, 0) + 1
        actor.armour = key
        lines.append(f"You were wearing the {rec.get('name')}, but the old rules counted "
                     f"your {was} instead; it counts now"
                     + (f", and the {was} is in your pack." if was not in ("", "none", None)
                        else "."))
    return lines


def settle(actor, *, now: int | None = None) -> list[str]:
    """The actor's half of the conversion, once: the satchel's raw hides, a converted suit
    still in the armour slot, and the notice's lines. Runs only while the actor holds
    something old (a converted suit, old work, or a bare hide in an unstamped satchel), so a
    character who never touched the old bench is never written to, and a settled one is
    never settled twice. Returns the lines written ([] when nothing ran)."""
    from . import worldclass as wc

    store = getattr(actor, "herb_known", None)
    if store is None or NOTE_SLOT in store:
        return []
    converted = list(_converted(actor))
    kept = list(_old_rows(actor))
    hides = _bare_hides(actor)
    if not (converted or kept or hides):
        return []
    lines: list[str] = []
    prog = (getattr(actor, "world_classes", None) or {}).get(TRACK_ID)
    if prog is not None:
        banked = wc.perk_picks_banked(prog)
        if banked:
            lines.append(f"Leatherworker {prog.level}: the levels past 3 are endless levels "
                         f"now, and {banked} perk pick{'s' if banked != 1 else ''} wait at "
                         f"the bench. Nothing is spent until you choose.")
    lines += _settle_satchel(actor, int(now or 0))
    lines += _redon(actor)
    if kept:
        names = sorted({str(d.get("name") or d.get("base") or "") for _k, d in kept})
        lines.append(f"Kept as it was, old work: {_say(names)}. It can be worn or sold as "
                     f"before, never worked further.")
    store[NOTE_SLOT] = {"stamp": MIGRATION_STAMP, "lines": lines, "seen": not lines}
    return lines


def settle_campaign(campaign) -> bool:
    """`settle` for everyone in the campaign, at the scene's minute (the hides' clock starts
    there). True when anything changed. A campaign with no old leatherwork is not touched,
    so it saves byte for byte as it was."""
    scene = getattr(campaign, "scene", None)
    if scene is None:
        return False
    now = int(getattr(scene, "clock_minutes", 0) or 0)
    changed = False
    for actor in list((getattr(scene, "people", None) or {}).values()):
        try:
            if settle(actor, now=now):
                changed = True
        except Exception:  # noqa: BLE001 - one sheet the migration cannot read stays as it was
            continue
    return changed


def stamp_save(actor, d: dict) -> None:
    """Mark a sheet this build saves while it carries a bare hide (contracts §11, lane I): in
    this build that hide is a counter's purchase, sold tanned, and the next load must not
    take it for an old raw one. Written into the saved dict only, only when a hide is
    carried and the sheet has no stamp, so every other save round-trips byte for byte."""
    if stamped(actor) or not _bare_hides(actor):
        return
    known = d.setdefault("herb_known", {})
    known[NOTE_SLOT] = {"stamp": MIGRATION_STAMP, "lines": [], "seen": True}


def conversions(actor) -> list[dict]:
    """The one-time notice (the enchanter's `conversions` shape): the leatherworker's own
    entry first, then every converted suit not yet shown. [] once everything is seen."""
    out: list[dict] = []
    note = (getattr(actor, "herb_known", None) or {}).get(NOTE_SLOT)
    if isinstance(note, dict) and not note.get("seen") and note.get("lines"):
        out.append({"key": NOTE_KEY, "name": "Your leatherwork, on the new bench",
                    "changes": list(note.get("lines") or ()), "questions": [],
                    "seen": False})
    for key, rec in _converted(actor):
        m = rec.get("migration") or {}
        if m.get("seen"):
            continue
        out.append({"key": f"stock:{key}", "name": str(rec.get("name") or ""),
                    "changes": list(m.get("changes") or ()), "questions": [],
                    "seen": False})
    return out


def conversion_seen(actor, key: str | None = None) -> None:
    """Mark one notice entry seen (`key` as `conversions` gives it), or all of them. The worn
    copy of a suit is marked with its pack entry."""
    note = (getattr(actor, "herb_known", None) or {}).get(NOTE_SLOT)
    if isinstance(note, dict) and key in (None, NOTE_KEY):
        note["seen"] = True
    for k, rec in _converted(actor):
        if key is None or key == f"stock:{k}":
            rec.setdefault("migration", {})["seen"] = True
            for worn in (getattr(actor, "worn", None) or {}).values():
                if isinstance(worn, dict) and worn.get("id") == rec.get("id") \
                        and isinstance(worn.get("migration"), dict):
                    worn["migration"]["seen"] = True


__all__ = ["MIGRATION_STAMP", "NOTE_SLOT", "conversion_seen", "conversions", "is_old_suit",
           "migrate_old_record", "settle", "settle_campaign", "stamp_save", "stamped",
           "target_of", "undo_migration"]
