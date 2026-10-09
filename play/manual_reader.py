"""Reading a craft's manual at its bench: one reader for the forge, the enchanting circle and
the alchemist's bench (POST api/forge/manual, api/enchant/manual, api/alchemy/manual).

Measured 2026-10-08 (the leatherworking knowledge lane): manuals were sold at counters for
every craft (rules/goods.py `MANUAL_TABLES`) and paid mastery on a first reading, but the
only route in play/ that read one was play/herb_views.py `herb_manual`, which looks up
herbal manuals only. A bought smithing, enchanting or alchemy manual could never be
opened: its gold bought a book that weighed nothing and taught nothing.

`knowledge.read_manual` is the rule (what a book teaches, and whether this is the first
reading); this module is the door around it, the same at each bench: refused in a fight or
when downed, the book must be one of this craft's and in the pack, the hours pass through
`Scene.advance` (the one clock door), and the first reading's mastery is paid on the
craft's own track. The leather bench has its own copy of this door
(play/leather_views.py `leather_manual`), written by its lane before this one; the herb
bench keeps `herb_manual`, which seeds the herbalist's world knowledge as well.
"""
from __future__ import annotations

from django.http import JsonResponse

from rules import knowledge, worldclass

# What a reading teaches about, in the transcript's words ("... learns 4 things about
# metals and the smith's stores"), by craft.
ABOUT = {knowledge.BLACKSMITH: "metals and the smith's stores",
         knowledge.ENCHANTER: "essences, their makings and their properties",
         knowledge.ALCHEMIST: "reagents and the alchemist's stores"}


# Where a material's property acts, in the bench's own ledger words (44-forge-ledger.js
# `groups`, 54-alchemy-books.js `propsHtml`), so a reading's lines read as the card does.
# Seen live 2026-10-08: without them one smithing book listed "+2 hardness" twice under
# Iron, with nothing to say that one was the blade's and one the plate's. An essence's
# trait already says where it acts in its own words ("Seats in a weapon"), so it has none.
_WHERE = {knowledge.BLACKSMITH: {"weapon": "In a weapon", "armour": "In armour",
                                 "shield": "In a shield", "working": "At the anvil",
                                 "quench_mark": "In the quench"}}


def _where(craft: str, group: str) -> str:
    if craft == knowledge.ALCHEMIST and group:
        return "In the bottle" if group == "product" else "At the bench"
    return _WHERE.get(craft, {}).get(group or "", "")


def carried(pc, craft: str) -> list[dict]:
    """This craft's manuals the character has with them, for the bench's Manuals button:
    id, name, the hours a reading takes, whether it was read before, and the book's own
    line. [] when the craft has no manuals in this build."""
    read = set(getattr(pc, "manuals_read", None) or [])
    out = []
    try:
        for mid, m in sorted(knowledge.manuals(craft).items()):
            if knowledge.holds_manual(pc, m):
                out.append({"id": mid, "name": str(m.get("name") or mid),
                            "hours": int(m.get("hours", 1) or 1), "read": mid in read,
                            "about": str(m.get("about") or "")})
    except Exception:      # noqa: BLE001 - a list of books is never worth failing the state
        return []
    return out


def _err(text: str, status: int) -> JsonResponse:
    return JsonResponse({"error": text}, status=status)


def _learned(pc, craft: str, revealed: dict[str, list[str]]) -> list[dict]:
    """What the reading taught, one row per fact, in words: a material's or an essence's
    property by its card's own line (and `where` it acts, in the bench's words), a recipe
    by the item it makes, a property type by its name. The rows carry no ref and no number
    the page has to work out."""
    from rules import effectspec, magic_layer

    out: list[dict] = []
    for did, keys in revealed.items():
        if did.startswith(knowledge.PROPERTY_PREFIX):
            pid = did[len(knowledge.PROPERTY_PREFIX):]
            prop = effectspec.property(pid) or {}
            name = "enhancement" if pid == "enhancement" else str(prop.get("name") or pid)
            out.append({"id": did, "name": name, "key": knowledge.TYPE_KEY,
                        "text": f"The property {name}: what it is and what it does."})
            continue
        if knowledge.RECIPE_KEY in keys and magic_layer.recipe(did) is not None:
            name = str((magic_layer.recipe(did) or {}).get("name") or did)
            out.append({"id": did, "name": name, "key": knowledge.RECIPE_KEY,
                        "text": f"How {name} is made."})
            continue
        doc = knowledge.material(did)
        if doc is None:
            continue
        name = str(doc.get("name") or did)
        rows = {r.get("key"): r for r in knowledge.properties(pc, doc)}
        essence = knowledge.is_essence(doc)
        for k in keys:
            row = rows.get(k) or {}
            out.append({"id": did, "name": name, "key": k,
                        "text": str(row.get("text") or ""),
                        "where": "" if essence else _where(craft, str(row.get("group") or ""))})
    return out


def read(c, pc, craft: str, said: str, *, track_id: str, clock, note=None) -> JsonResponse:
    """Read `said` (a manual's id or name) at `craft`'s bench, and answer the page:
    {"manual", "revealed": [{id, name, key, text}], "first", "minutes", "mastery", "clock",
    "manuals", "note"}. `clock(c)` is the bench's own clock body; `note(pc, manual)` is the
    bench's own sentence about the book, or "" (the alchemist's formulary: what it writes
    is copied from the Formulary, so "nothing new in it" would be untrue)."""
    from . import downed
    from . import history as history_mod

    if downed.state_of(pc) not in ("fine", "disabled"):
        return _err(f"{pc.name} is in no condition to read.", 409)
    if c.scene.in_encounter:
        return _err("You are in a fight. The book waits until it is over.", 409)
    manual = knowledge.manual_named(said, craft)
    if manual is None:
        # Another craft's book is named as such, so the player knows which bench reads it.
        other = knowledge.manual_named(said)
        if other is not None:
            return _err(f"{other.get('name')} is not a book for this bench.", 400)
        return _err("There is no such manual.", 400)
    if not knowledge.holds_manual(pc, manual):
        return _err(f"{pc.name} does not have {manual.get('name')}.", 400)
    got = dict(knowledge.read_manual(pc, manual, clock=int(c.scene.clock_minutes or 0)))
    minutes = int(got.get("minutes") or 60)
    c.scene.advance(minutes)
    revealed = _learned(pc, craft, got.get("revealed") or {})
    track, progress = worldclass.get(track_id), pc.track(track_id)
    mastery = {"lines": [], "total": progress.mp, "level": progress.level, "levelled": []}
    if int(got.get("mp") or 0):
        res = worldclass.award_bonus(track, progress, why=f"read {manual.get('name')}",
                                     mp=int(got["mp"]))
        mastery = {"lines": list(res.get("reasons") or []), "total": res.get("total"),
                   "level": res.get("level"), "levelled": list(res.get("levelled") or [])}
    n = len(revealed)
    said_more = str(note(pc, manual) or "") if note else ""
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{pc.name} reads {manual.get('name')} ({minutes // 60} hours)"
        + (f" and learns {n} thing{'s' if n != 1 else ''} about "
           f"{ABOUT.get(craft, 'the craft')}." if n else
           "." if said_more else ", and finds nothing new in it.")
        + (f" {said_more}" if said_more else ""))})
    c.turn_log.append(history_mod.stamp(c, {
        "kind": "resolution", "door": craft,
        "outcomes": [{"intent_id": craft, "op": "manual", "tell": "", "effects": [
            {"ref": pc.ref, "kind": "manual_read", "manual": manual.get("name"),
             "learned": n}]}]}))
    c.save()
    return JsonResponse({"manual": manual.get("id"), "name": manual.get("name"),
                         "revealed": revealed, "first": bool(got.get("first")),
                         "minutes": minutes, "mastery": mastery, "clock": clock(c),
                         "manuals": carried(pc, craft), "note": said_more})
