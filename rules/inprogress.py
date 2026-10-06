"""In progress: work that is not finished yet, counting down on the world clock until it
is collected. One section for every craft (docs/enchanting-revamp-plan.md §15,
docs/enchanting-contracts.md §8).

The owner's rulings this is built to:

* "for all crafts there should be an in progress section where all the crafts sit before
  they can be collected ... countdown timers that move with game time" (leatherworking
  Q9.3, 2026-10-05). A thing whose minute has passed is READY and stays here until the
  player collects it; nothing lifts itself.
* "there should be no limit to how many things are crafting" (enchanting Round 4, point 5).
  `register` refuses a `limit`, so a craft cannot bring the book's "one item at a time"
  back by the side door.

**One store, no parallel list** (law 2). Work in progress is a `crafting.Stock` entry in
`actor.stock` carrying a `work` block, as herbalism's steeping jar already was with its
`ready_minute`; this module keeps no list of its own and reads every row off the pack. A
forged record (`forge_items.ForgedStock`) saves only its `record`, so its block is kept in
`record["work"]` as well (`_set_block`); the loader hands the record back whole, block
included.

**No second ticker.** Time moves through `Scene.advance` alone, and that door calls
`settle` for everybody it holds: a work whose minute it passed turns ready there and is
told there (law 3), "<name> is ready to collect". Every view below computes its state from
the clock it is handed, so a row can never say "working" after its minute, whether or not a
settle has run; `settle`'s stored `state` exists only so the tell is said once.

Prior art (searched for the plan, §15.2): EVE Online's industry window, where a finished
job's button becomes Deliver and moves the product into the hangar
(wiki.eveuniversity.org/Manufacturing) — "sit there before they can be collected", exactly;
and Stardew Valley, whose most-installed quality-of-life mods do nothing but show machines'
time left, one ("Machine Status", nexusmods.com/stardewvalley/mods/11177) as one list across
every location sorted busy/ready — which is why `entries` is one list, ready first.

The block (contracts §8.1):

    {"craft": "enchanter", "label": "Binding a +1 flaming longsword", "doing": "binding",
     "started": 57600, "minutes": 11520, "where": "carried" | "place:<id>",
     "where_name": "Brannoc's tannery", "state": "working" | "ready",
     "result": {...craft-owned, never sent to the page...}}

A craft registers what Collect and Stop mean for it; the section knows nothing about any
one craft.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable

from . import sky

# The `how` words that declare a thing is held in this section. "steeping" is herbalism's
# word from before the section existed: every jar saved before 2026-10-05 carries it.
HELD_WORDS = ("in_progress", "steeping")

# Crafts whose id changed name once: the herb track is `herbalist`, its older jars say
# `herbalism` (crafting.HERBAL_CRAFTS).
_ALIASES = {"herbalism": "herbalist"}


@dataclass
class _Craft:
    craft: str
    collect: Callable | None
    cancel: Callable | None
    icon: str
    stop_words: str | Callable


_CRAFTS: dict[str, _Craft] = {}


def register(craft: str, *, collect: Callable | None = None, cancel: Callable | None = None,
             icon: str = "", stop_words: str | Callable = "", limit=None) -> None:
    """A craft says what Collect and Stop mean for its work.

    `collect(item, actor) -> dict | None`: craft-owned work done as the thing is collected
    (an enchanter writes the layer onto the vessel). Return `{"ok": False, "why": ...}` to
    refuse; `{"said": ..., "product": {...}}` to word it. The section lifts the block itself.
    `cancel(item, actor) -> dict | None`: the same for Stop; a craft without one cannot be
    stopped, and its rows say so. `stop_words` is the consequence the confirm shows ("The
    vessel comes back unenchanted. The essences are spent."), a string or `f(item)`.

    `limit` exists only to refuse: the owner ruled no limit in every craft (Round 4, 5).
    """
    if limit is not None:
        raise ValueError(
            f"{craft}: In progress takes no limit. The owner ruled 'there should be no limit "
            f"to how many things are crafting' in every craft (docs/enchanting-answers.md, "
            f"Round 4 point 5); drop `limit`.")
    craft = str(craft or "").strip().lower()
    if not craft:
        raise ValueError("a craft registers under its track id, e.g. 'enchanter'")
    _CRAFTS[craft] = _Craft(craft, collect, cancel, str(icon or craft), stop_words)


def _registry() -> dict[str, _Craft]:
    # Herbalism registers itself on import (rules/crafting.py, at its foot). The engine can
    # reach `settle` before anything has imported crafting, so the section asks for it.
    if "herbalist" not in _CRAFTS:
        from . import crafting  # noqa: F401  — registers `herbalist`
    return _CRAFTS


def _craft(name: str) -> _Craft:
    name = _ALIASES.get(str(name or ""), str(name or ""))
    found = _registry().get(name)
    # A block written by a craft this build does not know (a save from a newer version):
    # still shown and collectable, with nothing craft-owned done.
    return found or _Craft(name, None, None, name or "work", "")


# --- the block on one item ------------------------------------------------------------------

def _stored(item) -> dict | None:
    block = getattr(item, "work", None)
    if isinstance(block, dict) and block:
        return block
    record = getattr(item, "record", None)
    if isinstance(record, dict) and isinstance(record.get("work"), dict):
        return record["work"]
    return None


def _set_block(item, block: dict | None) -> None:
    item.work = block
    record = getattr(item, "record", None)
    if isinstance(record, dict):
        if block is None:
            record.pop("work", None)
        else:
            record["work"] = block


def _legacy(item, now: int | None) -> dict | None:
    """A jar from before the section: `ready_minute` set and either declared steeping or
    still short of its minute (the engine's old door refused on the minute alone). Derived,
    never written until something changes it, so an old save loads and saves back as it
    was."""
    ready = getattr(item, "ready_minute", None)
    if ready is None:
        return None
    declared = any(h in HELD_WORDS for h in (getattr(item, "how", None) or []))
    if not declared and (now is None or int(ready) <= int(now)):
        return None
    craft = _ALIASES.get(str(getattr(item, "craft", "") or ""), str(getattr(item, "craft", "") or ""))
    minutes = _steep_minutes(getattr(item, "form", None))
    started = int(ready) - minutes if minutes else None
    return {"craft": craft or "herbalist", "label": "Steeping", "doing": "steeping",
            "started": started, "minutes": minutes, "where": "carried", "state": "working",
            "_legacy": True}


def _steep_minutes(form) -> int | None:
    """How long the herb bench steeps this form, from its own rule row, so an old jar's
    countdown can be drawn as a fraction."""
    try:
        from . import crafting

        row = crafting.method_row("steep") or {}
        got = (row.get("ready_minutes") or {}).get(str(form or ""))
        return int(got) if got else None
    except Exception:  # noqa: BLE001 — a dial without its fraction is still a countdown
        return None


def work_of(item, now: int | None = None) -> dict | None:
    """The item's In-progress block, stored or (for an old jar) derived; None when it is
    not in progress."""
    return _stored(item) or _legacy(item, now)


def end_of(item, now: int | None = None) -> int | None:
    """The world minute the work is done."""
    block = work_of(item, now)
    if block is None:
        return None
    if block.get("started") is not None and block.get("minutes") is not None \
            and not block.get("_legacy"):
        return int(block["started"]) + int(block["minutes"])
    ready = getattr(item, "ready_minute", None)
    return int(ready) if ready is not None else None


def state_of(item, now: int | None) -> str | None:
    """"working", "ready" or None (not in progress). From the clock, never the stored
    state, so a view cannot lag the minute."""
    block = work_of(item, now)
    if block is None:
        return None
    end = end_of(item, now)
    if now is None:
        return str(block.get("state") or "working")
    return "ready" if end is None or int(end) <= int(now) else "working"


def held_back(item, now: int | None) -> str:
    """Why this thing cannot be used, worn or sold yet, finishing "The <base> is ...", or ""
    when it is free. Asked by every door that reaches for a made thing: the engine's use
    door and the bench's fit check today."""
    state = state_of(item, now)
    if state is None:
        return ""
    if state == "ready":
        return ("ready to collect, and waits In progress until it is collected")
    block = work_of(item, now) or {}
    doing = str(block.get("doing") or "being worked")
    end = end_of(item, now)
    left = sky.span_words(int(end) - int(now)) if end is not None and now is not None else ""
    return f"still {doing}; it is ready in {left}" if left else f"still {doing}"


# --- the door's verbs -----------------------------------------------------------------------

def _find(actor, key: str):
    key = str(key or "")
    if key.startswith("stock:"):
        key = key.split(":", 1)[1]
    stock = getattr(actor, "stock", None) or {}
    return key, stock.get(key)


def begin(actor, stock_key: str, *, craft: str, minutes: int, now: int, label: str,
          where: str = "carried", where_name: str = "", doing: str = "",
          result: dict | None = None) -> dict:
    """Put a thing on the shelf into progress. `{ok, key, ready_at}` or `{ok: False, why}`.

    The whole entry goes in: a craft that works one of a stack splits it off first (two
    jars of one batch are one entry, and are one piece of work). `where` is "carried" (it
    travels with you) or "place:<place id>" (it stays there, and is collected there);
    `where_name` is how the page says that place. `result` is the craft's own, kept for
    its collect and never sent to the page.

    The countdown is the block's `started + minutes`. `ready_minute` is NOT set here: it is
    part of a stepped jar's id, and changing it would re-key the entry under the player's
    feet. Herbalism's jars are made with both (`crafting.make`).
    """
    name = _ALIASES.get(str(craft or "").strip().lower(), str(craft or "").strip().lower())
    if name not in _registry():
        raise ValueError(f"{craft!r} has not registered with In progress "
                         f"(inprogress.register); known: {', '.join(sorted(_CRAFTS))}")
    key, item = _find(actor, stock_key)
    if item is None:
        return {"ok": False, "why": "That is not in your pack any more."}
    if work_of(item, now) is not None:
        return {"ok": False, "why": f"{item.name} is already in progress."}
    minutes = int(minutes)
    if minutes < 1:
        raise ValueError("work in progress takes at least a minute; finish it on the spot")
    where = str(where or "carried")
    if where != "carried" and not where.startswith("place:"):
        raise ValueError(f"`where` is 'carried' or 'place:<id>', not {where!r}")
    block = {"craft": name, "label": str(label or "Working"),
             "started": int(now), "minutes": minutes, "where": where, "state": "working"}
    if doing:
        block["doing"] = str(doing)
    else:
        block["doing"] = str(label or "working").split()[0].lower()
    if where_name:
        block["where_name"] = str(where_name)
    if result:
        block["result"] = copy.deepcopy(result)
    _set_block(item, block)
    how = [h for h in (getattr(item, "how", None) or []) if h not in HELD_WORDS]
    item.how = how + ["in_progress"]
    return {"ok": True, "key": key, "ready_at": int(now) + minutes}


def block(*, craft: str, label: str, started: int, minutes: int, where: str = "carried",
          doing: str = "") -> dict:
    """A fresh block for a thing made straight into progress (a jar put up to steep), in
    the one shape `begin` writes."""
    return {"craft": craft, "label": label,
            "doing": doing or str(label or "working").split()[0].lower(),
            "started": int(started), "minutes": int(minutes), "where": where,
            "state": "working"}


def settle(actor, now: int) -> list[str]:
    """Names of the work that turned ready since the last settle; marks them told.

    Called by `Scene.advance` for everybody it holds, and nowhere else: a view that settled
    would swallow the tell (law 3) that the clock's door owes. An old jar already past its
    minute is told on the first settle after it loads, then written with its block.
    """
    out = []
    for item in (getattr(actor, "stock", None) or {}).values():
        if state_of(item, now) != "ready":
            continue
        stored = _stored(item)
        if stored is not None and stored.get("state") == "ready":
            continue
        if stored is None:
            legacy = dict(_legacy(item, now) or {})
            legacy.pop("_legacy", None)
            # An old jar's countdown is its `ready_minute`; the block keeps the steep's
            # own length when the rule row knows it, so the dial can still be drawn.
            if legacy.get("started") is None:
                legacy["started"] = int(item.ready_minute)
                legacy["minutes"] = 0
            stored = legacy
            how = [h for h in (item.how or []) if h not in HELD_WORDS]
            item.how = how + ["in_progress"]
        stored["state"] = "ready"
        _set_block(item, stored)
        out.append(item.name)
    return out


def _lift(item) -> None:
    _set_block(item, None)
    item.how = [h for h in (getattr(item, "how", None) or []) if h not in HELD_WORDS]


def _where_ok(block: dict, here: str | None) -> bool:
    where = str(block.get("where") or "carried")
    return where == "carried" or (here is not None and where == f"place:{here}")


def _where_name(block: dict) -> str:
    return str(block.get("where_name") or "the place it was left")


def collect(actor, key: str, *, now: int, here: str | None) -> dict:
    """Take finished work out of the section: `{ok, said, product}` or `{ok: False, why}`.

    `here` is the place the player stands (`actor.at`); work left at a place is collected
    there and nowhere else.
    """
    key, item = _find(actor, key)
    if item is None:
        return {"ok": False, "why": "That is not in progress any more."}
    block = work_of(item, now)
    if block is None:
        return {"ok": False, "why": f"{item.name} is not in progress."}
    if state_of(item, now) != "ready":
        return {"ok": False, "why": f"{item.name} is not ready yet: it is ready in "
                                    f"{sky.span_words(int(end_of(item, now)) - int(now))}."}
    if not _where_ok(block, here):
        return {"ok": False, "why": f"Collect it at {_where_name(block)}."}
    craft = _craft(block.get("craft"))
    got = (craft.collect(item, actor) if craft.collect else None) or {}
    if got.get("ok") is False:
        return {"ok": False, "why": str(got.get("why") or "It cannot be collected yet.")}
    _lift(item)
    product = got.get("product") or {"key": f"stock:{key}", "name": item.name}
    return {"ok": True, "said": str(got.get("said") or f"You collect {item.name}."),
            "product": product}


def cancel(actor, key: str, *, now: int) -> dict:
    """Stop work in progress, on the craft's own terms: `{ok, said}` or `{ok: False, why}`."""
    key, item = _find(actor, key)
    if item is None:
        return {"ok": False, "why": "That is not in progress any more."}
    block = work_of(item, now)
    if block is None:
        return {"ok": False, "why": f"{item.name} is not in progress."}
    craft = _craft(block.get("craft"))
    if craft.cancel is None:
        return {"ok": False, "why": f"{block.get('label') or 'This work'} cannot be stopped."}
    got = craft.cancel(item, actor) or {}
    if got.get("ok") is False:
        return {"ok": False, "why": str(got.get("why") or "It cannot be stopped.")}
    # The craft may have taken the thing off the shelf (a ruined working); if it is still
    # there it comes out of the section.
    if (getattr(actor, "stock", None) or {}).get(key) is item:
        _lift(item)
    return {"ok": True, "said": str(got.get("said") or f"You stop work on {item.name}.")}


# --- what the page is sent -------------------------------------------------------------------

def _stop_words(craft: _Craft, item) -> str:
    words = craft.stop_words
    return str(words(item) if callable(words) else words or "")


def _row(key: str, item, now: int, here: str | None) -> dict:
    from . import residency

    block = work_of(item, now) or {}
    craft = _craft(block.get("craft"))
    state = state_of(item, now)
    end = end_of(item, now)
    where = str(block.get("where") or "carried")
    where_words = "carried" if where == "carried" else f"at {_where_name(block)}"
    fraction = None
    if block.get("minutes") and block.get("started") is not None:
        # Short of 1 while it is working: five minutes left of a fortnight rounded to a
        # full dial on the live check (2026-10-05), which read as done when it was not.
        fraction = round(min(0.999, max(0.0, (int(now) - int(block["started"]))
                                        / int(block["minutes"]))), 3)
    if state == "ready":
        fraction = 1.0
        long_ago = end is not None and int(now) - int(end) >= 60
        ready_words = f"ready since day {int(end) // sky.DAY + 1}" if long_ago else "ready now"
        why_not = None if _where_ok(block, here) else f"Collect at {_where_name(block)}"
    else:
        ready_words = f"ready in {sky.span_words(int(end) - int(now))}" if end is not None \
            else "working"
        why_not = "Not ready yet"
    can_collect = state == "ready" and _where_ok(block, here)
    return {
        "key": key, "craft": craft.craft, "icon": craft.icon, "name": item.name,
        "label": str(block.get("label") or ""), "where": where, "where_words": where_words,
        "state": state, "ready_at": end,
        "ready_in": max(0, int(end) - int(now)) if end is not None else None,
        "ready_day": int(end) // sky.DAY + 1 if end is not None else None,
        "ready_words": ready_words,
        "ready_when": (f"day {int(end) // sky.DAY + 1}, {residency.day_part(int(end))}"
                       if end is not None else ""),
        "fraction": fraction, "can_collect": can_collect, "why_not": why_not,
        "can_stop": craft.cancel is not None, "stop_words": _stop_words(craft, item),
    }


def entries(actor, now: int, *, here: str | None = None, craft: str | None = None) -> list[dict]:
    """Every row of the section, computed here (UI plan §6.10: the page computes no
    number). Ready first, longest-waiting first; then working, soonest first."""
    want = _ALIASES.get(str(craft or ""), str(craft or "")) if craft else None
    rows = []
    for key, item in (getattr(actor, "stock", None) or {}).items():
        if work_of(item, now) is None:
            continue
        row = _row(key, item, now, here)
        if want and row["craft"] != want:
            continue
        rows.append(row)
    big = 10 ** 12
    rows.sort(key=lambda r: (0 if r["state"] == "ready" else 1,
                             r["ready_at"] if r["ready_at"] is not None else big, r["name"]))
    return rows


def summary(actor, now: int) -> dict:
    """The door's count: `{ready, working, next: {name, ready_words} | None}`."""
    rows = entries(actor, now)
    working = [r for r in rows if r["state"] == "working"]
    nxt = working[0] if working else None
    return {"ready": sum(1 for r in rows if r["state"] == "ready"), "working": len(working),
            "next": {"name": nxt["name"], "ready_words": nxt["ready_words"]} if nxt else None}
