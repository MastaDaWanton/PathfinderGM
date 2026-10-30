"""Limited-use effects on forged items: a blanch, an anointing, a quench mark's daily gift.

A forge material's effect can say `uses: "once"` or `uses: "per_day"` with a `uses_count`
(effectspec's one spelling, shared with the magic items). Until this module nothing read
it on a forged item: `forge_items.build` passed the effect through as if it were standing,
so a blade blanched with cold iron struck as cold iron for every hit it ever landed, a
wyroot haft gave its "once a day" temporary hit point on every critical, and holy
anointing's "first battle after the rite" lasted forever. Found by the 0.2.24 items lane,
which fixed `uses` for the enchanter's wondrous items (`Actor.reset_item_uses`) and noted
the forge's specs were never read.

The book's rule for the case that is printed (weapon blanch, Advanced Player's Guide p.184
and Ultimate Equipment p.103): "The blanching remains effective until you make a
successful attack with the weapon" — and it "counts as both materials for the first
successful hit". Ghost salt (Pathfinder Society Field Guide p.48) says the same: it
"remains effective until the weapon makes a successful attack". So a strike-as finish is
spent BY the hit, after that hit has struck as the material — not by a miss, and whether
or not the target had any damage reduction to bypass.

What spends each kind (`spent_on`, derived from the effect, because the documents do not
say and the three cases are settled by their own texts):

- `hit`    — a `strikes_as` finish: the blanch rule above, on the weapon's next hit.
- `fires`  — a triggered rider (`trigger`: crit, hit, first_wound_daily): the time it
             fires. Wyroot (UE p.52): "can gain at most 1 life point per day".
- `battle` — a standing modifier (holy anointing, a house finish: "for its first battle
             after the rite"): engaged by the weapon's first hit in a fight, spent when
             that fight ends (`Scene.end_encounter`, the one door every fight ends by),
             and spent then too if it was simply in hand for the fight.

The count lives on the item's RECORD (`spent: {key: used}`, `engaged: [key]`), never on
the actor and never as a second store of numbers: `forge_items.build` reads it and leaves
an exhausted effect out, so the attack, the card and the bench all read the same build.
A forge item kept as a plain Stock carries the same thing as `forge.spent.*` and
`forge.engaged.*` tags (`blacksmith.Work`), which is what survives a save there; a worn
copy is written alongside. A `once` count stays spent across days; a `per_day` count
goes back to nothing with the day (`new_day`, called by `Actor.reset_item_uses`, the
0.2.24 rule: once is permanent, per-day resets). Re-applying the finish at the forge
(`blacksmith._build_finish`) clears its counts: a fresh dose.
"""
from __future__ import annotations

LIMITED = ("once", "per_day")


def key_for(material: str, n: int) -> str:
    """The record's key for one limited effect: the material and the effect's place in
    that material's list for this gear. `~` because tags split on dots and ids carry
    hyphens."""
    return f"{material}~{int(n)}"


def limit(eff: dict) -> int | None:
    """How many uses the effect has before it is spent, or None for a standing effect."""
    uses = str((eff or {}).get("uses") or "").strip().lower()
    if uses not in LIMITED:
        return None
    try:
        return max(1, int(eff.get("uses_count") or 1))
    except (TypeError, ValueError):
        return 1


def spent_on(eff: dict) -> str:
    """What spends this effect (module docstring)."""
    if eff.get("trigger"):
        return "fires"
    if str(eff.get("type") or "") == "strikes_as":
        return "hit"
    return "battle"


def used(rec: dict | None, key: str) -> int:
    try:
        return max(0, int(((rec or {}).get("spent") or {}).get(key, 0) or 0))
    except (TypeError, ValueError):
        return 0


def engaged(rec: dict | None, key: str) -> bool:
    return key in ((rec or {}).get("engaged") or ())


# --- writing the count onto every copy of the item --------------------------------------------

def _rid(rec) -> str:
    return str((rec or {}).get("id") or (rec or {}).get("name") or "").strip().lower()


def _write(actor, rec_id: str, change) -> bool:
    """Apply `change(spent: dict, engaged: list)` to every stored copy of the forged item
    `rec_id`: its worn copies (`Actor.wear` keeps one) and the pack's entry — a
    `ForgedStock`'s record, or a bench Stock's `forge.*` tags, re-keyed on the shelf so a
    fresh identical item put there later does not stack onto a spent one. Returns whether
    any copy was found."""
    from . import blacksmith, forge_items

    want = str(rec_id or "").strip().lower()
    if not want:
        return False
    found = False

    def on_dict(d: dict) -> None:
        spent = dict(d.get("spent") or {})
        eng = list(d.get("engaged") or [])
        change(spent, eng)
        spent = {k: int(v) for k, v in spent.items() if int(v or 0) > 0}
        if spent:
            d["spent"] = spent
        else:
            d.pop("spent", None)
        if eng:
            d["engaged"] = sorted(set(eng))
        else:
            d.pop("engaged", None)

    for rec in (getattr(actor, "worn", None) or {}).values():
        if isinstance(rec, dict) and forge_items.is_forged(rec) and _rid(rec) == want:
            on_dict(rec)
            found = True
    stock = getattr(actor, "stock", None) or {}
    for sid, item in list(stock.items()):
        rec = getattr(item, "record", None)
        if isinstance(rec, dict) and forge_items.is_forged(rec):
            if _rid(rec) == want:
                on_dict(rec)
                found = True
            continue
        w = blacksmith.Work.from_stock(item)
        if w is None or w.form != "item":
            continue
        made = blacksmith.record(w) or {}
        if _rid(made) != want:
            continue
        holder = {"spent": dict(w.spent), "engaged": list(w.engaged)}
        on_dict(holder)
        w.spent = dict(holder.get("spent") or {})
        w.engaged = list(holder.get("engaged") or [])
        item.properties = ([t for t in item.properties or ()
                            if not str(t).startswith(("forge.spent.", "forge.engaged."))]
                           + [t for t in w.tags()
                              if t.startswith(("forge.spent.", "forge.engaged."))])
        new_key = blacksmith.stock_key(w)
        if new_key != sid and new_key not in stock:
            stock[new_key] = stock.pop(sid)
        found = True
    return found


def spend(actor, rec: dict, key: str, n: int = 1) -> None:
    """One more use of `key` gone, on every copy; an engagement ends with it."""
    def change(spent: dict, eng: list) -> None:
        spent[key] = int(spent.get(key, 0) or 0) + int(n)
        if key in eng:
            eng.remove(key)
    _write(actor, _rid(rec), change)


def engage(actor, rec: dict, key: str) -> None:
    """A battle-long finish has entered its battle (spent when the fight ends)."""
    def change(spent: dict, eng: list) -> None:
        if key not in eng:
            eng.append(key)
    _write(actor, _rid(rec), change)


def left(actor, rec: dict, key: str) -> int | None:
    """The uses `key` has left, read LIVE off the actor's own copy of the record — not off
    a weapon row built before this swing (a full attack keeps one row for every swing)."""
    live = actor.crafted_record(str((rec or {}).get("id") or "")) or rec
    from .sheet import built

    for row in built(live).get("uses") or ():
        if row["key"] == key:
            return int(row["left"])
    return None


def rows(actor, rec: dict | None) -> list[dict]:
    """The limited-use rows of a record's build, read live."""
    if not rec:
        return []
    from .sheet import built

    live = actor.crafted_record(str(rec.get("id") or "")) or rec
    return list(built(live).get("uses") or ())


def battle_over(actor) -> list[str]:
    """A fight has ended: every battle-long finish it engaged, and the one on the weapon
    in hand, is spent. Returns a tell for each."""
    from . import forge_items

    out: list[str] = []
    held = actor.wielded_record() if hasattr(actor, "wielded_record") else None
    held_id = _rid(held) if held else ""
    seen: set[str] = set()
    recs = [r for r in (getattr(actor, "worn", None) or {}).values() if isinstance(r, dict)]
    for item in (getattr(actor, "stock", None) or {}).values():
        r = forge_items.record_of(item)
        if r is not None:
            recs.append(r)
    for rec in recs:
        rid = _rid(rec)
        if rid in seen or not forge_items.is_forged(rec):
            continue
        seen.add(rid)
        for row in forge_items.build(rec).get("uses") or ():
            if row.get("spent_on") != "battle" or row["left"] <= 0:
                continue
            if not (row.get("engaged") or rid == held_id):
                continue
            spend(actor, rec, row["key"])
            out.append(f"The {what(row)} on {actor.name}'s "
                       f"{rec.get('name') or 'weapon'} has run its course.")
    return out


def new_day(actor) -> None:
    """Every forged item's per-day counts back to nothing; a `once` stays spent."""
    from . import forge_items

    seen: set[str] = set()
    recs = [r for r in (getattr(actor, "worn", None) or {}).values() if isinstance(r, dict)]
    for item in (getattr(actor, "stock", None) or {}).values():
        r = forge_items.record_of(item)
        if r is not None:
            recs.append(r)
    for rec in recs:
        rid = _rid(rec)
        if rid in seen or not forge_items.is_forged(rec) or not rec.get("spent"):
            continue
        seen.add(rid)
        daily = {row["key"] for row in forge_items.build(rec).get("uses") or ()
                 if row.get("uses") == "per_day"}
        if daily:
            def change(spent: dict, eng: list, daily=daily) -> None:
                for k in daily:
                    spent.pop(k, None)
            _write(actor, rid, change)


def restore(spent: dict, engaged_keys: list, material: str) -> tuple[dict, list]:
    """A finish re-applied at the bench: its counts cleared, a fresh dose."""
    head = f"{material}~"
    return ({k: v for k, v in (spent or {}).items() if not str(k).startswith(head)},
            [k for k in engaged_keys or () if not str(k).startswith(head)])


def what(row: dict) -> str:
    """The finish's name for a tell: "cold iron blanching"."""
    return str(row.get("name") or row.get("source") or "finish").lower()


def card_line(row: dict) -> str:
    """One line for the bench's card: what it does and what is left."""
    name = str(row.get("name") or row.get("source") or "Finish")
    count, have = int(row.get("count") or 1), int(row.get("left") or 0)
    per = " today" if row.get("uses") == "per_day" else ""
    if have <= 0:
        state = ("spent for today" if row.get("uses") == "per_day"
                 else "spent: apply it again at the forge")
    elif row.get("engaged"):
        state = "in its battle now, spent when the fight ends"
    else:
        state = f"{have} of {count} use{'s' if count != 1 else ''} left{per}"
    until = {"hit": "until the weapon next hits", "fires": "",
             "battle": "for its first battle"}.get(str(row.get("spent_on") or ""), "")
    return f"{name}: {state}" + (f" ({until})" if until and have > 0 else "")


__all__ = ["LIMITED", "key_for", "limit", "spent_on", "used", "engaged", "spend", "engage",
           "left", "rows", "battle_over", "new_day", "restore", "what", "card_line"]
