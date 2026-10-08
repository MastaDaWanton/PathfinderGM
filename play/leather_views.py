"""The leather bench's API (docs/leatherworking-contracts.md §7), mirroring play/forge_views.py
and play/alchemy_views.py.

The page sends what the player chose — a method, what is in each slot, a batch, a pattern
from the list, the face of their own d20, the minigame's 0..1 score — and the server answers
with every number: the DC, the odds, the step ceiling and why, the tier, the product and its
build, the hide units, the clock, the wait, the rent, the mastery. The page never computes a
number (UI plan §12), the bench's form of "no model authors a number".

One step is three requests, as at the forge:

  check   what would happen, why each rack entry fits each slot or does not, the wait of a
          tannage and its vats, and `forge_items.preview` of what Assemble would make;
  roll    the d20 (the player's own face, or the server's); the time and any tannery yard
          rent pass; on a miss the book's failure rule at once; on a success the
          materials are set aside behind a token;
  finish  the game's score becomes a tier under the step's ceiling, the product lands,
          the materials are spent, a vat's rent is paid as the hides go in, a tannage that
          waits goes In progress (rules/inprogress.py), mastery and discoveries are paid.

Collect (a tannage's cut test, plan §8.3), grade (lane F's `knowledge.grade`, plan §16),
ask a tanner and read a manual (lane F's leatherworker rows), perks, the ledger and a
material's card are single requests. Nothing is spent between roll and finish:
the token holds a reservation in this process's memory, and a reload, a crash or a second
roll lets it go with the materials untouched.
"""
from __future__ import annotations

import secrets

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from rules import crafting, worldclass
from rules import leatherworker as lw

from . import campaign as campaign_mod
from .apiutil import read_body, read_int

TRACK_ID = lw.TRACK_ID
MAX_BATCH = 200

# Pending steps, by campaign id: {"token", "plan", "roll"}. One per campaign; a new roll
# replaces it and a fresh GET of the state lets it go (the page has just opened, so any
# step in flight was abandoned). Module memory on purpose, as at the forge.
_PENDING: dict[str, dict] = {}


def _err(text: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": text}, status=status)


def _now(c) -> int:
    return int(c.scene.clock_minutes or 0)


def _clock(c) -> dict:
    minute = _now(c)
    hour, mins = (minute % 1440) // 60, minute % 60
    twelve = hour % 12 or 12
    return {"minute": minute, "day": minute // 1440 + 1,
            "label": f"Day {minute // 1440 + 1}, {twelve}:{mins:02d}"
                     f"{'am' if hour < 12 else 'pm'}"}


def _progress(pc):
    return worldclass.get(TRACK_ID), pc.track(TRACK_ID)


def _known(c):
    """`Engine.places()`, which lane G's `leather_bench_here` takes so an authored place
    whose id does not spell its name is still found."""
    try:
        return c.engine().places()
    except Exception:      # noqa: BLE001 - lane G reads the scene's place without it
        return ()


def _coins(cp: int) -> str:
    """"1 sp", "3 cp", "2 gp": the largest coin that says it exactly."""
    cp = int(cp)
    if cp and cp % 100 == 0:
        return f"{cp // 100} gp"
    if cp and cp % 10 == 0:
        return f"{cp // 10} sp"
    return f"{cp} cp"


def _keeper_name(c, ref) -> str:
    if not ref:
        return ""
    try:
        from rules import places as places_mod

        who = places_mod._actor(c.scene, ref)
        return str(getattr(who, "name", "") or "")
    except Exception:      # noqa: BLE001 - a name is never worth failing for
        return ""


def _where(c, pc) -> dict:
    """Where the bench stands (UI plan §6.3, §6.8 "the place line"): lane G's answer, the
    place's name for the stage and for an In-progress entry's "in the vat at ...", the vats
    the party's work already fills here (shown, never a gate: no vat cap), and one line in
    words."""
    known = _known(c)
    got = lw.where_here(c.scene, pc, known)
    tannery = got.get("tannery")
    place = ""
    try:
        here = c.engine().here()
        place = str(getattr(here, "name", "") or "")
    except Exception:      # noqa: BLE001 - a label is never worth failing a request for
        place = ""
    out = dict(got)
    out["tiers"] = list(got.get("tiers") or ())
    out["place"] = place
    out["biome"] = c.biome
    out["vats_in_use"] = 0
    if tannery:
        keeper = _keeper_name(c, tannery.get("keeper"))
        rate = int(tannery.get("rate_cp_per_hour") or 0)
        vat = int(tannery.get("vat_rate_cp_per_day") or 0)
        whose = (f"{keeper}'s tannery" if keeper and tannery.get("kind") == "town"
                 else "your tannery" if tannery.get("kind") == "owned" and not rate
                 else (f"the tannery at {place}" if place else "the tannery"))
        out["name"] = whose
        try:
            from rules import places as places_mod

            out["vats_in_use"] = int(places_mod.vats_in_use(c.scene, tannery["place"]))
        except Exception:  # noqa: BLE001
            out["vats_in_use"] = 0
        line = f"At {whose}"
        if rate:
            line += f", {_coins(rate)} an hour"
        if vat:
            line += f", vats {_coins(vat)} a day each"
        if out["vats_in_use"]:
            line += (f"; {out['vats_in_use']} vat{'s' if out['vats_in_use'] != 1 else ''} "
                     f"holding your work")
        out["line"] = line
        out["label"] = "a town tannery" if tannery.get("kind") == "town" else "your tannery"
    elif got.get("field_kit"):
        out["name"] = ""
        out["line"] = "At the field kit: common and uncommon hides, and its small kettle"
        out["label"] = "your field kit"
    else:
        out["name"] = ""
        out["line"] = ("No bench here: carry a leatherworker's field kit or find a tannery")
        out["label"] = "no bench"
    try:
        from rules import places as places_mod

        out["advice"] = places_mod.tannery_line(c.scene, known)
    except Exception:      # noqa: BLE001
        out["advice"] = ""
    return out


def _reserved(c) -> dict:
    pend = _PENDING.get(c.id)
    if not pend:
        return {}
    out: dict[str, int] = {}
    for p, n in pend["plan"].consumes:
        out[p.key] = out.get(p.key, 0) + int(n)
    return out


def _rack(c, pc, reserved=True) -> list:
    return lw.rack(pc, _now(c), _reserved(c) if reserved else None)


def _rack_items(c, pc) -> list[dict]:
    return [lw.piece_view(p, pc, _now(c)) for p in _rack(c, pc)]


def _colors(items: list[dict]) -> dict:
    """{material id: colour} for everything the page may draw, the pieces of a finished
    record included, so the stage colours a lining it was never shown as a rack row."""
    out = {}
    for it in items:
        mid = it.get("material")
        if mid:
            out[mid] = it.get("color")
        for piece in ((it.get("record") or {}).get("pieces") or {}).values():
            pm = (piece or {}).get("material")
            if pm and pm not in out:
                out[pm] = _color(pm)
    return out


def _color(mid: str) -> str:
    doc = lw.material(mid) or {}
    return str(doc.get("color") or "#a0764a")


def _pct(x: float) -> str:
    return f"{round(x * 100, 1):g}%"


def _track(track, progress) -> dict:
    """The track summary (level, mastery, ceiling, perks banked), the tier names to the
    ceiling, and what the next pick of each perk does, in words with numbers."""
    out = dict(worldclass.track_summary(track, progress))
    ceiling = int(out.get("ceiling", worldclass.ceiling_index(progress)))
    out["tiers"] = [worldclass.quality_name(i) for i in range(ceiling + 1)]
    out["masterwork_at"] = worldclass.quality_name(lw._mw_index())
    out["masterwork_index"] = lw._mw_index()
    sizes = (track.endless or {}).get("perks") or {}
    info = {}
    for perk in track.perks:
        size, n = float(sizes.get(perk, 0) or 0), int(progress.perks.get(perk, 0))
        if perk == "quality":
            step = int(size) or 1
            nxt = (f"Your quality ceiling rises {'one step' if step == 1 else f'{step} steps'}, "
                   f"to {worldclass.quality_name(ceiling + step)}")
        elif perk == "yield":
            # Read at the harvest (plan §17.2: Yield moved to skinning), not at the bench.
            nxt = (f"+{_pct(size)} chance per hide you harvest of more hide, rolled and "
                   f"shown, total {_pct(size * (n + 1))}")
        elif perk == "hardening":
            nxt = (f"-{_pct(size)} to the drawbacks of everything you make, total "
                   f"x{round((1 - size) ** (n + 1), 4):g}")
        else:
            nxt = (f"+{_pct(size)} to the bonuses of everything you make, total "
                   f"+{_pct(size * (n + 1))}")
        info[perk] = {"next": nxt, "taken": n}
    out["perk_info"] = info
    return out


# Slot words for the work order (UI plan §6.5). The slot ids are `lw.METHOD_SLOTS`; these
# are only how each reads on the page.
_SLOT_LABEL = {"hide": "Hide", "salt": "Curing salt", "tannin": "Tannin", "piece": "Piece",
               "oil": "Oil", "thread": "Thread", "wax": "Wax", "dye": "Dye",
               "mordant": "Mordant", "body": "Body", "fastenings": "Fastenings",
               "lining": "Lining"}
_SLOT_EMPTY = {"hide": "Drop a hide here, or press Enter on one in the rack",
               "salt": "Drop curing salt here: one measure a hide unit",
               "tannin": "Optional: a tannin. With none, the hide dries as rawhide",
               "piece": "Drop a piece here, or press Enter on one in the rack",
               "oil": "Drop an oil here", "thread": "Drop a thread here",
               "wax": "Optional: a wax to fill the tooling",
               "dye": "Drop a dye here", "mordant": "Optional: mordant salts fix the colour",
               "body": "Drop the body here: panels or plates cut for the pattern",
               "fastenings": "Drop a lacing set or a fitting here",
               "lining": "Optional: a stitched lining"}


def _slot_view(method: str) -> list[dict]:
    names = lw.METHOD_SLOTS.get(method, ())
    optional = set(lw.OPTIONAL.get(method, ()))
    return [{"id": s, "label": _SLOT_LABEL.get(s, s.title()), "optional": s in optional,
             "empty": _SLOT_EMPTY.get(s, f"Fill the {s} slot")} for s in names]


def _tannages() -> list[dict]:
    """The tannages, for the page to show beside the tannin slot (a fact, not a secret):
    level, where, bench time, the wait in words, whether it hardens, its shrinkage
    temperature."""
    from rules import sky

    out = []
    for kind, row in (lw.bench_rules().get("tannages") or {}).items():
        wait = int(row.get("wait_minutes") or 0)
        out.append({"id": kind, "name": row.get("name", kind), "level": row.get("level", 1),
                    "where": row.get("where", "kit"), "hardens": bool(row.get("hardens")),
                    "wait_minutes": wait, "wait_words": sky.span_words(wait) if wait else "",
                    "shrink_c": row.get("shrink_c")})
    return out


def _works(c, pc) -> list[dict]:
    from rules import inprogress

    return inprogress.entries(pc, _now(c), here=getattr(pc, "at", None) or None,
                              craft=TRACK_ID)


def _state_body(c, pc) -> dict:
    from rules import inprogress

    track, progress = _progress(pc)
    where = _where(c, pc)
    rack = _rack_items(c, pc)
    works = _works(c, pc)
    here = str(getattr(pc, "at", "") or "")
    return {
        "track": _track(track, progress),
        "level": int(progress.level),
        "ceiling": worldclass.ceiling_index(progress),
        "picks_banked": worldclass.perk_picks_banked(progress),
        "methods": lw.methods_view(progress.level, where),
        "rack": rack,
        "colors": _colors(rack),
        "slots": {m: _slot_view(m) for m in lw.METHODS if m != "grade"},
        "where": where,
        "products": lw.products_view(pc),
        "tannages": _tannages(),
        "clock": _clock(c),
        "works": works,
        # What waits for the player at the tannery they stand in (UI plan §6.2, "Here at
        # the tannery"): the same rows, the ones whose place is here.
        "here": [r for r in works if r.get("where") == f"place:{here}"],
        "in_progress": inprogress.summary(pc, _now(c)),
        "grade": {"terms": lw.check_terms(pc, progress.level) + lw.kit_terms(pc),
                  "minutes": int((lw.method_row("grade") or {}).get("minutes", 10))},
    }


def _ready(request):
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return None, None, _err("There is no character to work the hides.", 409)
    return c, pc, None


def _slots(body, items) -> tuple[dict, JsonResponse | None]:
    """`slots` as {slot: (rack Piece, count)}. A slot's value is a rack key, or
    {"key", "count"}."""
    raw = body.get("slots", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        return {}, _err("`slots` must be an object of {slot: key}.")
    by_key = {p.key: p for p in items}
    out = {}
    for slot, val in raw.items():
        if val in (None, ""):
            continue
        if isinstance(val, dict):
            key = str(val.get("key") or "")
            count = read_int(val, "count", 1, lo=0, hi=MAX_BATCH * 10)
        elif isinstance(val, str):
            key, count = val, 1
        else:
            return {}, _err(f"The {slot} slot holds something that is not a rack key.")
        if key not in by_key:
            return {}, _err("Something on the bench is no longer on your rack. Take it off "
                            "and look again.", 409)
        out[str(slot).strip().lower()] = (by_key[key], count)
    return out, None


def _hair(body):
    raw = body.get("hair")
    if raw in (None, ""):
        return None
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("on", "fur", "true", "yes", "1")


def _plan_from(c, pc, body):
    method = str(body.get("method") or "").strip().lower()
    if not method:
        return None, [], 0, 0, None, _err("Choose a method first.")
    items = _rack(c, pc)
    slots, refused = _slots(body, items)
    if refused:
        return None, items, 0, 0, None, refused
    batch = read_int(body, "batch", 1, lo=1, hi=MAX_BATCH)
    track, progress = _progress(pc)
    where = _where(c, pc)
    product = str(body.get("product") or body.get("pattern") or "").strip().lower()
    aim = body.get("masterwork", True)
    plan = lw.plan_step(pc, progress, method, slots, batch, product=product,
                        part=str(body.get("part") or "body"), hair=_hair(body),
                        where=where, masterwork=aim is not False, now=_now(c))
    known = _known(c)
    rent = lw.rent_cp(c.scene, where, plan.minutes, known) if plan.units else 0
    vat = (lw.vat_rent_cp(c.scene, where, plan.wait_minutes, plan.vats, known)
           if plan.units and plan.vats else 0)
    if rent or vat:
        from rules import goods

        have = goods.in_copper(pc.purse)
        if have < rent + vat:
            bill = []
            if rent:
                bill.append(f"{_coins(rent)} for the yard's hours")
            if vat:
                bill.append(f"{_coins(vat)} for {plan.vats} vat"
                            f"{'s' if plan.vats != 1 else ''} for the wait")
            plan.problems.append(f"The tanner wants {' and '.join(bill)}, and you carry "
                                 f"{_coins(have)}.")
    return plan, items, rent, vat, where, None


# Target names in the build card's rows: the sum's own ids, said as a tanner would.
_TARGET_LABEL = {"attack": "Attack", "damage": "Damage", "hardness": "Hardness",
                 "hp_per_inch": "Hit points an inch", "acp": "Armour check penalty",
                 "max_dex": "Max Dex", "asf": "Spell failure", "weight_pct": "Weight",
                 "category": "Weight class", "speed_penalty": "Speed", "ac": "Armour",
                 "cmd": "Manoeuvre defence", "enchant_cost_pct": "Enchanting cost"}
_MINUS = "−"


def _num(v, places: int = 1) -> str:
    v = round(float(v or 0), places)
    if v == 0:
        return "0"
    text = f"{abs(v):.{places}f}".rstrip("0").rstrip(".")
    return ("+" if v > 0 else _MINUS) + text


def _render(spec: dict) -> str:
    try:
        from rules import effectspec

        return effectspec.render(spec)
    except Exception:      # noqa: BLE001 - a line in words is never worth failing for
        return str(spec.get("type") or "")


def _card(build: dict | None, pieces: dict | None, gear: str, quality: str = "") -> dict | None:
    """The build card (UI plan §6.6), the forge's shape for leather: one row per target, one
    column per piece, the bonuses after quality, the drawbacks after the cut, the final
    number rounded toward zero; book effects and what the creature gave, in words. Every
    number is `forge_items.build`'s, formatted here so the page adds nothing."""
    if not build or build.get("problems"):
        return None
    from rules import forge_items as fi

    slots = list(fi.PIECES.get(gear or "armour", fi.PIECES["armour"]))
    pieces = pieces or {}
    cols = []
    for i, slot in enumerate(slots):
        mid = str((pieces.get(slot) or {}).get("material") or "")
        cols.append({"slot": slot, "label": _SLOT_LABEL.get(slot, slot.title()),
                     "material": lw.doc_name(mid) if mid else "none",
                     "color": _color(mid) if mid else "",
                     "weight": f"×{fi.MAIN_WEIGHT:g}" if i == 0 else f"×{fi.OTHER_WEIGHT:g}"})
    mult = build.get("multipliers") or {}
    rows, summary = [], []
    for s in build.get("sum") or []:
        target = str(s.get("target") or "")
        label = _TARGET_LABEL.get(target, target.replace("_", " ").capitalize())
        rows.append({"target": target, "label": label, "when": bool(s.get("when")),
                     "cells": {slot: _num((s.get("pieces") or {}).get(slot, 0), 2)
                               for slot in slots},
                     "bonus": _num(s.get("bonus"), 2), "negative": _num(s.get("negative"), 2),
                     "final": _num(s.get("final"), 0)})
        if s.get("final"):
            line = _render({"type": s.get("type") or "combat_mod", "target": target,
                            "amount": int(s["final"]), "bonus_type": "material"})
            summary.append(line + (" (when it applies)" if s.get("when") else ""))
    powers = [_render(e) for e in build.get("book") or []]
    creature = [_render(e) for e in build.get("specs") or []
                if str(e.get("source") or "").startswith("creature:")]
    q = mult.get("quality")
    cut = mult.get("negative_cut")
    return {
        "columns": cols, "rows": rows, "summary": summary, "powers": powers,
        "from_creature": creature,
        "masterwork": bool(build.get("masterwork")),
        "by_nature": bool(build.get("always_masterwork")),
        "quality": quality,
        "bonus_head": f"Bonuses ×{q:g}" if q is not None else "Bonuses",
        "negative_head": f"Drawbacks ×{cut:g}" if cut is not None else "Drawbacks",
        "how": (f"The body counts {fi.MAIN_WEIGHT:g}, the others {fi.OTHER_WEIGHT:g} each, "
                f"and every lamination ×{fi.STRENGTHEN_PER_PASS:g}. Bonuses are multiplied "
                f"by the quality" + (f" (×{q:g}" + (f" at {quality}" if quality else "") + ")"
                                     if q is not None else "")
                + ", drawbacks cut by your level and perks"
                + (f" (×{cut:g})" if cut is not None else "")
                + ". Each row is added up, then rounded toward zero. What the creature "
                  "itself resisted is never scaled."),
    }


def _preview(plan, pc) -> dict | None:
    """`forge_items.preview` of what this work comes to, at each rung up to the step's
    ceiling: Assemble's item itself, or for panels and plates the body of the pattern they
    are cut for, so the build card shows what the choice is worth before it is made."""
    from rules import forge_items as fi

    if not plan.outputs:
        return None
    first = plan.outputs[0][0]
    perks = {"potency": plan.perks.get("potency", 0),
             "hardening": plan.perks.get("hardening", 0)}
    if isinstance(first, dict):
        product = first["product"]
        pieces = first["pieces"]
    elif getattr(first, "pattern", "") and first.part == "body":
        product = first.pattern
        pieces = {"body": lw._piece_spec(first)}
    else:
        return None
    info = lw.PRODUCTS.get(product) or {}
    gear, base = info.get("gear", "armour"), info.get("base", "")
    by_tier = {}
    for t in range(0, max(0, plan.step_ceiling) + 1):
        by_tier[worldclass.quality_name(t)] = fi.preview(
            pieces, gear=gear, base=base, quality_index=t, level=plan.level, perks=perks)
    top = worldclass.quality_name(max(0, plan.step_ceiling))
    return {"at": top, "build": by_tier.get(top), "by_tier": by_tier,
            "card": _card(by_tier.get(top), pieces, gear, top),
            "as": "" if isinstance(first, dict) else
            f"As the body of {info.get('word', product).lower()}, at {top}"}


def _wait(c, plan, where) -> dict | None:
    if not plan.wait_minutes:
        return None
    from rules import sky

    ready = _now(c) + int(plan.minutes) + int(plan.wait_minutes)
    place = ("in the lime pit" if plan.method == "flense" else
             "in the vat" if plan.wait_where == "tannery" else "in your pack")
    if plan.wait_where == "tannery" and where.get("name"):
        place += f" at {where['name']}"
    return {"minutes": int(plan.wait_minutes), "words": sky.span_words(plan.wait_minutes),
            "where": plan.wait_where, "place": place, "ready_at": ready,
            "ready_day": ready // 1440 + 1, "vats": int(plan.vats),
            "line": f"Then {sky.span_words(plan.wait_minutes)} {place}. "
                    f"Ready day {ready // 1440 + 1}."}


def _product_rows(plan) -> list[dict]:
    rows = []
    for i, (thing, n) in enumerate(plan.outputs):
        if isinstance(thing, dict):
            info = lw.PRODUCTS.get(thing["product"]) or {}
            body = (thing["pieces"].get("body") or {}).get("material", "")
            rows.append({"name": f"{lw._lead_word(body)} {info.get('word', '')}".strip(),
                         "form": "item", "count": n, "material": body,
                         "product": thing["product"], "offcut": False})
        else:
            rows.append({"name": lw.hide_name(thing), "form": thing.form, "count": n,
                         "material": thing.material, "units": thing.units,
                         "units_words": lw.units_word(thing.quarters),
                         "offcut": plan.method == "cut" and i > 0})
    return rows


def _base_line(plan) -> str:
    """The base hand-off line (UI plan §6.5): a leather armour is a base the forge
    finishes, and can be worn as leather armour until then (plan §4.3)."""
    info = lw.PRODUCTS.get(plan.product) or {}
    finishes = info.get("base_for") or []
    if plan.method != "assemble" or not finishes:
        return ""
    words = " or ".join(finishes)
    return (f"A base: the forge finishes it into {words}. It can be worn as "
            f"{info.get('word', '').lower()} until then.")


def _check_body(c, plan, items, rent, vat, where, pc) -> dict:
    per_unit = max(1, plan.batch)
    most = min((p.count // max(1, n // per_unit) for p, n in plan.consumes if n > 0),
               default=0)
    row = lw.method_row(plan.method) or {}
    return {
        "fits": lw.fits_for(plan.method, items, product=plan.product),
        "slots": _slot_view(plan.method),
        "product": plan.product,
        "gear": plan.gear,
        "problems": list(plan.problems),
        "can_roll": plan.can_roll,
        "info": plan.info,
        "minutes": plan.minutes, "units": plan.units, "batch": plan.batch,
        "dc": plan.dc, "bonus": plan.bonus, "terms": plan.terms,
        "need": plan.need, "impossible": plan.impossible,
        "rent_cp": rent, "vat_rent_cp": vat,
        "wait": _wait(c, plan, where),
        "ceiling": plan.step_ceiling,
        "ceiling_why": list(plan.ceiling_why),
        "grade_cap": plan.grade_cap,
        "tiers": [worldclass.quality_name(t) for t in range(max(0, plan.step_ceiling) + 1)],
        "masterwork": {"aiming": plan.aim, "ready": plan.masterwork_work,
                       "by_nature": plan.always_masterwork,
                       "why": plan.masterwork_why} if plan.method == "assemble" else None,
        "max_batch": most if (row.get("bulk") and plan.consumes) else min(1, most),
        "products": _product_rows(plan),
        "base_line": _base_line(plan),
        "band": lw.band_for(plan),
        "tannage": plan.tannage or None,
        "preview": _preview(plan, pc) if not plan.problems else None,
    }


# --- state, check -----------------------------------------------------------------------------

@require_GET
def leather_state(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    _PENDING.pop(c.id, None)
    return JsonResponse(_state_body(c, pc))


@require_POST
def leather_check(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    plan, items, rent, vat, where, refused = _plan_from(c, pc, body)
    if refused:
        return refused
    return JsonResponse(_check_body(c, plan, items, rent, vat, where, pc))


# --- roll --------------------------------------------------------------------------------------

def _face(body) -> tuple[int | None, JsonResponse | None]:
    raw = body.get("face")
    if raw is None:
        return None, None
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None, _err("The face must be a number from 1 to 20.")
    try:
        face = int(str(raw).strip())
    except ValueError:
        return None, _err("The face must be a number from 1 to 20.")
    if not 1 <= face <= 20:
        return None, _err(f"{face} is not a face of a d20.")
    return face, None


def _mastery(got: dict, progress) -> dict:
    return {"lines": list(got.get("reasons") or []),
            "total": got.get("total", progress.mp),
            "level": got.get("level", progress.level),
            "levelled": list(got.get("levelled") or [])}


@require_POST
def leather_roll(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    if c.scene.in_encounter:
        return _err("You are in a fight. The hides wait until it is over.", 409)
    if c.scene.awaiting:
        return _err("There is a roll waiting on you at the table.", 409)
    body = read_body(request)
    face, refused = _face(body)
    if refused:
        return refused
    _PENDING.pop(c.id, None)
    plan, _items, rent, vat, where, refused = _plan_from(c, pc, body)
    if refused:
        return refused
    if plan.problems:
        return _err(" ".join(plan.problems))
    if plan.need is None:
        return _err(f"No roll can make DC {plan.dc} with +{plan.bonus}: it "
                    f"{plan.impossible}.")
    if not plan.can_roll:
        return _err("Nothing on the bench to work.")

    engine = c.engine()
    label = f"Leatherworking: {plan.method.title()}"
    if face is None:
        face = engine.dice.d20(label=label, visibility="player").faces[0]
    total = face + plan.bonus
    margin = total - plan.dc
    # A skill check: no natural 20 or natural 1 (CRB p.180; `crafting.check_odds`).
    success = margin >= 0
    track, progress = _progress(pc)

    paid = []
    if rent:
        from rules import goods

        purse, ok = goods.spend(pc.purse, rent)
        if ok:
            pc.purse = purse
            paid.append({"cp": rent, "for": "the yard's hours",
                         "to": (where.get("tannery") or {}).get("keeper")})
    c.scene.advance(plan.minutes)
    roll = {"face": face, "faces": [face], "bonus": plan.bonus, "total": total,
            "dc": plan.dc, "success": success, "margin": margin, "terms": plan.terms}
    out = {"roll": roll,
           "verdict": {"verdict": "success" if success else "failure", "natural": face,
                       "word": "Success" if success else "Failure"},
           "lost": [], "minutes": plan.minutes, "rent": paid}
    line = ""
    if success:
        token = secrets.token_urlsafe(16)
        _PENDING[c.id] = {"token": token, "plan": plan, "roll": roll, "vat": vat,
                          "where": where}
        out["token"] = token
        out["tuning"] = lw.tuning_for(plan)
        out["band"] = lw.band_for(plan)
    else:
        miss = -margin
        losses = lw.failure_losses(plan, miss)
        out["lost"] = lw.spend(pc, losses)
        if out["lost"]:
            ruined = ", ".join(f"{x['count']} {x['name']}" for x in out["lost"])
            said = f"Missed by {miss}. Half of what was on the bench is ruined: {ruined}."
        else:
            said = f"Missed by {miss}. The time is lost; the materials are kept."
        out["said"] = said
        got = worldclass.award_step(track, progress, method=plan.method,
                                    ingredient_id=plan.lead_id,
                                    rarity_rank=plan.rank_in, quality_index=0,
                                    success=False, name=lw.doc_name(plan.lead_id)
                                    if plan.lead_id else "",
                                    count=max(1, plan.units), noun=plan.noun)
        out["mastery"] = _mastery(got, progress)
        line = (f"{plan.method.title()} at the leather bench: spoiled (d20 {face}"
                f"{plan.bonus:+d} = {total} vs DC {plan.dc}). {said}")
    out["clock"] = _clock(c)
    if line:
        c.transcript.append({"who": "gm", "kind": "consequence", "text": line})
    c.save()
    return JsonResponse(out)


# --- finish ------------------------------------------------------------------------------------

def _first(progress, key: str) -> bool:
    seen = int(progress.crafted.get(key, 0))
    progress.crafted[key] = seen + 1
    return seen == 0


def _next_step(thing) -> str:
    """The step a product most likely goes to next, for the result's "Next: Flense" button.
    A suggestion only; the server still checks whatever the player picks."""
    if isinstance(thing, dict):
        return ""
    f = thing.form
    if f == "green":
        return "salt"
    if f == "salted":
        return "flense"
    if f == "pelt":
        return "tan"
    if f in ("leather", "fur", "rawhide"):
        return "cut"
    if f == "panel":
        if "stitch" not in thing.worked and not lw._plated(thing.pattern):
            return "stitch"
        if lw._plated(thing.pattern):
            return "harden"
        return "assemble"
    if f in ("plate", "lacing"):
        return "assemble"
    return ""


@require_POST
def leather_finish(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    pend = _PENDING.get(c.id)
    token = str(body.get("token") or "")
    if not pend or not token or not secrets.compare_digest(pend["token"], token):
        return _err("That step is no longer waiting to be finished. Roll again.", 409)
    plan = pend["plan"]
    track, progress = _progress(pc)

    # Everything that can refuse refuses before anything changes (one save at the end).
    fresh = {p.key: p for p in _rack(c, pc, reserved=False)}
    need: dict[str, int] = {}
    for p, n in plan.consumes:
        need[p.key] = need.get(p.key, 0) + int(n)
    for key, n in need.items():
        have = fresh.get(key)
        if have is None or have.count < n:
            _PENDING.pop(c.id, None)
            name = next(p.name for p, _ in plan.consumes if p.key == key)
            return _err(f"The {name} set aside for this step is gone. Nothing was made.",
                        409)
    vat = int(pend.get("vat") or 0)
    if vat:
        from rules import goods

        if goods.in_copper(pc.purse) < vat:
            _PENDING.pop(c.id, None)
            return _err(f"The vats want {_coins(vat)} for the wait, and you no longer "
                        f"carry it. Nothing went into the vat.", 409)

    tier, score = crafting.tier_from_score(body.get("score"), plan.step_ceiling)
    _PENDING.pop(c.id, None)
    now = _now(c)
    lw.spend(pc, [(fresh[p.key], n) for p, n in plan.consumes])
    paid = []
    if vat:
        from rules import goods

        purse, ok = goods.spend(pc.purse, vat)
        if ok:
            pc.purse = purse
            paid.append({"cp": vat, "for": f"{plan.vats} vat{'s' if plan.vats != 1 else ''} "
                                           f"for the wait"})
    made = lw.make(plan, tier, now=now)
    where = dict(pend.get("where") or {})
    landed = lw.land(pc, plan, made, now=now, where=where, setup_score=score)

    lines: list[dict] = []
    levelled: list[int] = []
    got = worldclass.award_step(track, progress, method=plan.method,
                                ingredient_id=plan.lead_id, rarity_rank=plan.rank_in,
                                quality_index=tier, success=True,
                                name=lw.doc_name(plan.lead_id) if plan.lead_id else "",
                                count=max(1, plan.units), noun=plan.noun)
    lines += list(got.get("reasons") or [])
    levelled += list(got.get("levelled") or [])

    def bonus(why: str) -> None:
        res = worldclass.award_bonus(track, progress, why=why, mp=worldclass.FIRST_MP)
        lines.extend(res.get("reasons") or [])
        levelled.extend(res.get("levelled") or [])

    for row in landed:
        what = (row.get("record") or {}).get("product") if row.get("record") else \
            row["hide"].form
        if what and _first(progress, f"made:{what}"):
            bonus(f"first {lw._pattern_word(what).lower() if row.get('record') else what}")
    worked = []
    for p, _ in plan.consumes:
        if p.hide is not None and p.material not in worked:
            worked.append(p.material)
    for mid in worked:
        if _first(progress, f"hide:{mid}"):
            bonus(f"first work with {lw.doc_name(mid)}")

    # Working a hide reveals its working traits: you watched it behave (plan §16).
    discoveries = []
    how = f"worked it, day {now // 1440 + 1}"
    kn = lw._lane("knowledge")
    for mid in worked:
        doc = lw.material(mid)
        if doc is None or kn is None:
            continue
        try:
            keys = lw.working_keys(doc)
            new = lw.reveal(pc, mid, keys, how) if keys else []
            rows = {r.get("key"): r for r in kn.properties(pc, doc)} if new else {}
        except Exception:      # noqa: BLE001 - a discovery is never worth losing the work
            new, rows = [], {}
        for k in new:
            text = str((rows.get(k) or {}).get("text") or "")
            discoveries.append({"material": mid, "name": lw.doc_name(mid), "key": k,
                                "text": text})
            bonus(f"learned: {lw.doc_name(mid)}, {text}" if text
                  else f"learned: {lw.doc_name(mid)}")

    r = pend["roll"]
    tier_name = worldclass.quality_name(tier)
    said_what = ", ".join(
        f"{row['count']} {(row.get('record') or {}).get('name') or row['hide'].name}"
        for row in landed)
    waits = [row for row in landed if row.get("waits")]
    tail = ""
    if waits:
        from rules import sky

        tail = f" It waits {sky.span_words(waits[0]['waits'])} " + (
            "in the vat." if waits[0].get("where", "").startswith("place:") else
            "in the pack.")
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{pc.name} works the hides: {said_what}, {tier_name} "
        f"(d20 {r['face']}{r['bonus']:+d} = {r['total']} vs DC {r['dc']}).{tail}")})
    c.save()

    from rules import forge_items as fi

    products = []
    for row in landed:
        entry = {"key": f"stock:{row['key']}", "count": row["count"],
                 "waits": row.get("waits", 0), "ready_at": row.get("ready_at"),
                 "where": row.get("where")}
        rec = row.get("record")
        if rec is not None:
            build = fi.build(rec)
            entry.update({"name": rec["name"], "form": "item", "record": rec,
                          "build": build,
                          "card": _card(build, rec.get("pieces"), rec.get("gear"), tier_name),
                          "color": _color(((rec.get("pieces") or {}).get("body") or {})
                                          .get("material", "")),
                          "next": ""})
        else:
            h = row["hide"]
            entry.update({"name": h.name, "form": h.form, "units": h.units,
                          "units_words": lw.units_word(h.quarters), "grade": h.grade,
                          "color": _color(h.material), "next": _next_step(h)})
        products.append(entry)
    return JsonResponse({
        "tier": tier, "tier_name": tier_name, "score": score,
        "ceiling": plan.step_ceiling, "stopped": bool(body.get("stopped")),
        "products": products, "paid": paid,
        "mastery": {"lines": lines, "total": progress.mp, "level": progress.level,
                    "levelled": levelled},
        "discoveries": discoveries,
        "minutes": plan.minutes,
        "works": _works(c, pc),
        "state": _state_body(c, pc),
    })


# --- collect -----------------------------------------------------------------------------------

@require_POST
def leather_collect(request):
    """Take a tannage (or a limed hide) out of In progress (rules/inprogress.py's own
    collect, as api/works/collect does), with the cut test's score when the page played it:
    the tier is then from both halves of the Tan game (plan §8.3). Collecting early is
    refused with the time left; `wait` stays with the work until it is ready (the alchemy
    bench's Wait for it, through `Scene.advance`, the one clock door)."""
    from rules import inprogress

    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    key = str(body.get("key") or "")
    if not key:
        return _err("Say which work to collect (`key`).")
    sid = key.split(":", 1)[1] if key.startswith("stock:") else key
    item = (pc.stock or {}).get(sid)
    block = inprogress.work_of(item, _now(c)) if item is not None else None
    if block is None or str(block.get("craft") or "") != TRACK_ID:
        return _err("There is no such leatherwork in progress.", 404)
    waited = 0
    if body.get("wait"):
        if c.scene.in_encounter:
            return _err("You are in a fight. The vat will keep until it is over.", 409)
        left = max(0, int(inprogress.end_of(item, _now(c)) or 0) - _now(c))
        if left > 0:
            from rules import sky

            c.scene.advance(left)
            waited = left
            c.transcript.append({"who": "gm", "kind": "consequence", "text": (
                f"{pc.name} waits {sky.span_words(left)} for the {item.name}.")})
    if body.get("score") is not None and inprogress.state_of(item, _now(c)) == "ready":
        _, cut = crafting.tier_from_score(body.get("score"), 1)
        (block.setdefault("result", {}))["cut_score"] = cut
        inprogress._set_block(item, block)
    got = inprogress.collect(pc, sid, now=_now(c), here=getattr(pc, "at", None) or None)
    if waited:
        # Collected in the same breath, the clock's "is ready to collect" line is stale
        # (alchemy_collect's lesson, 2026-10-07); other work's lines stay queued.
        keep = [r for r in c.scene.take_works_said()
                if not (got.get("ok") and str(r.get("ref")) == str(getattr(pc, "ref", ""))
                        and str(r.get("what")) == str(item.name))]
        c.scene._works_said.extend(keep)
    if not got.get("ok"):
        if waited:
            c.save()
        return _err(str(got.get("why") or "It cannot be collected."), 409)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": got["said"]})
    c.save()
    return JsonResponse({"said": got["said"], "product": got.get("product"),
                         "waited": waited, "clock": _clock(c), "works": _works(c, pc),
                         "rack": _rack_items(c, pc)})


# --- grade -------------------------------------------------------------------------------------

@require_POST
def leather_grade(request):
    """Grade a scrap of a material (plan §16): the leather assay. `knowledge.assay` decides
    what is revealed (one benefit and one drawback) and its DC (easier for each known
    material of the kind, lane F's to key on the creature type); this view rolls the
    player's Craft check, takes a quarter unit of hide (or one measure of a supply),
    passes the ten minutes and pays `STUDY_MP` for each property found. No minigame."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    if c.scene.in_encounter:
        return _err("You are in a fight. Grading waits until it is over.", 409)
    kn = lw._lane("knowledge")
    if kn is None or not hasattr(kn, "assay"):
        return _err("Grading is not available in this build yet.", 501)
    body = read_body(request)
    mid = str(body.get("material") or "").strip().lower()
    doc = lw.material(mid)
    if doc is None:
        return _err("There is no such material.", 404)
    src = lw.grade_source(pc, mid, _now(c))
    if src is None:
        return _err(f"You carry no {doc.get('name') or mid} to take a scrap from.", 409)
    where = _where(c, pc)
    if not where.get("at"):
        return _err("You have no leatherworker's field kit with you, and there is no "
                    "tannery here.", 409)
    face, refused = _face(body)
    if refused:
        return refused
    track, progress = _progress(pc)
    terms = lw.check_terms(pc, progress.level) + lw.kit_terms(pc)
    bonus_v = sum(t["value"] for t in terms)
    engine = c.engine()
    if face is None:
        face = engine.dice.d20(label=f"Grade: {doc.get('name') or mid}",
                               visibility="player").faces[0]
    total = face + bonus_v
    now = _now(c)
    creature = (src.hide.creature if src.hide is not None else "") or None
    # Lane F's `knowledge.grade` (plan §16): the leather assay — a quarter unit, ten
    # minutes, one benefit and one drawback, -1 DC for each known hide of the same CREATURE
    # TYPE (the creature a generic hide came from passed in). Called, never duplicated;
    # the forge's assay answers only on a tree where lane F is not merged yet.
    try:
        if hasattr(kn, "grade"):
            got = dict(kn.grade(pc, mid, total, clock=now, creature=creature) or {})
        else:
            got = dict(kn.assay(pc, mid, total, clock=now) or {})
    except ValueError as exc:
        return _err(str(exc))
    paid = lw.pay_grade(pc, src, now)
    minutes = int(got.get("minutes") or (lw.method_row("grade") or {}).get("minutes", 10))
    c.scene.advance(minutes)
    revealed = list(got.get("revealed") or [])
    lines: list[dict] = []
    levelled: list[int] = []
    rows = {r.get("key"): r for r in kn.properties(pc, doc)} if revealed else {}
    found = []
    for k in revealed:
        text = str((rows.get(k) or {}).get("text") or "")
        found.append({"key": k, "text": text, "row": rows.get(k)})
    for f in found:
        # A point for each property the grading turned up (`worldclass.STUDY_MP`).
        res = worldclass.award_bonus(track, progress, mp=worldclass.STUDY_MP,
                                     why=f"graded {doc.get('name') or mid}: {f['text']}"
                                     if f["text"] else f"graded {doc.get('name') or mid}")
        lines.extend(res.get("reasons") or [])
        levelled.extend(res.get("levelled") or [])
    said = (f"{pc.name} grades a scrap of {doc.get('name') or mid} (d20 {face}{bonus_v:+d} "
            f"= {total}): " + (", ".join(f["text"] or f["key"] for f in found) if found
                               else "nothing new."))
    c.transcript.append({"who": "gm", "kind": "consequence", "text": said})
    c.save()
    return JsonResponse({
        "material": mid, "name": doc.get("name") or mid,
        "roll": {"face": face, "bonus": bonus_v, "total": total, "terms": terms,
                 "dc": got.get("dc"), "success": got.get("success")},
        "dc": got.get("dc"), "success": got.get("success"),
        "revealed": found, "paid": paid, "minutes": minutes,
        "mastery": {"lines": lines, "total": progress.mp, "level": progress.level,
                    "levelled": levelled},
        "clock": _clock(c), "rack": _rack_items(c, pc),
    })


# --- perks, ledger, a material's card ----------------------------------------------------------

@require_POST
def leather_perks(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    track, progress = _progress(pc)
    try:
        worldclass.pick_perks(track, progress, body.get("picks"))
    except ValueError as exc:
        return _err(str(exc))
    c.save()
    return JsonResponse(_track(track, progress))


def _is_leather(doc) -> bool:
    mats = lw._lane("materials")
    try:
        return bool(mats is not None and mats.is_leather(doc))
    except Exception:      # noqa: BLE001
        return False


@require_GET
def leather_ledger(request):
    """Every leather material the character has met (UI plan §6.7), with its swatch and
    surface: the forge's ledger, filtered to this craft's shelf."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    kn = lw._lane("knowledge")
    if kn is None or not hasattr(kn, "ledger"):
        return _err("The tanner's ledger is not available in this build yet.", 501)
    rows = []
    for row in kn.ledger(pc) or []:
        doc = lw.material(row.get("id"))
        if doc is None or not _is_leather(doc):
            continue
        rows.append(dict(row, color=str(doc.get("color") or "#a0764a"),
                         surface=str(doc.get("surface") or "")))
    return JsonResponse({"ledger": rows})


@require_GET
def leather_material(request, material_id: str):
    """One ledger card (UI plan §6.7): what the material is, what is known of it and how,
    what you carry (in hide units), what grading costs and needs, and the book effects
    this build cannot play yet ("book effect, not yet in play", lane D's `not_yet`)."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    doc = lw.material(material_id)
    if doc is None:
        return _err("There is no such material.", 404)
    mid = str(doc.get("id") or material_id)
    kn = lw._lane("knowledge")
    items = [p for p in _rack(c, pc) if p.material == mid and p.form != "item"]
    carried_units = sum(p.quarters * p.count for p in items if p.hide is not None) / 4
    carried = sum(p.count for p in items if p.hide is None)
    card = {"id": mid, "name": doc.get("name") or mid, "kind": doc.get("kind"),
            "tier": doc.get("tier"), "text": str(doc.get("text") or ""),
            "glyph": lw.KIND_GLYPH.get(str(doc.get("kind") or ""), lw.KIND_GLYPH["hide"]),
            "color": str(doc.get("color") or "#a0764a"), "surface": doc.get("surface") or "",
            "size": doc.get("size") or "", "sold_as": doc.get("sold_as") or "",
            "tannage": doc.get("tannage") or "",
            "always_masterwork": bool(doc.get("always_masterwork")),
            "allowed_bases": list(doc.get("allowed_bases") or []),
            "carried_units": carried_units, "carried": carried,
            "pieces": doc.get("pieces") or {}, "properties": None, "grade_dc": None,
            "grade_minutes": int((lw.method_row("grade") or {}).get("minutes", 10)),
            "grade_cost": "a quarter unit of hide" if doc.get("kind") == "hide"
            else "one measure",
            "not_yet": list(doc.get("not_yet") or []),
            "unknown": lw._unknown(pc, doc)}
    if kn is not None:
        try:
            card["properties"] = list(kn.properties(pc, doc))
            card["grade_dc"] = int(kn.assay_dc(doc, pc))
        except Exception:      # noqa: BLE001 - the card shows what it can
            pass
    # An unknown row says only that it is unknown. Measured 2026-10-08 by lane U5: each
    # unknown row went out with its `group`, and its key's letter (a0, t0) named the group
    # too, so the page held which list a property was in before any Grade; alchemy's U1
    # closed the same leak the same way (`alchemy_views`, "unknown-N"). The book clauses no
    # effect can play yet (`not_yet`) are the material's own words too: sent once anything
    # about it is known, never on a blind card.
    if card["properties"] is not None:
        blind, rows = 0, []
        for p in card["properties"]:
            if isinstance(p, dict) and not p.get("known"):
                rows.append({"key": f"unknown-{blind}", "known": False, "text": None,
                             "drawback": None, "how": None})
                blind += 1
            else:
                rows.append(p)
        card["properties"] = rows
    if not any(isinstance(p, dict) and p.get("known") for p in card["properties"] or []):
        card["not_yet"] = []
    card["tanners_here"] = tanners_here(c, pc)
    return JsonResponse(card)


# --- teachers and manuals (plan §16; lane F's knowledge rows) ----------------------------------

def _craft(kn) -> str | None:
    """Lane F's `knowledge.LEATHERWORKER`: the tanner's own rule rows (leatherworking-
    lore.json: tanner teachers, libraries, Grade, manual mastery). None on a tree without
    them, and then the routes below say so rather than teach with the smith's rows — the
    forge's teacher route reads only the smith's (`forge_views.forge_ask`), which is what
    lane F found taught deer hide at the forge."""
    craft = getattr(kn, "LEATHERWORKER", None) if kn is not None else None
    if not craft:
        return None
    try:
        kn.lore(craft)
    except Exception:          # noqa: BLE001 - no rule file: not in this build
        return None
    return craft


def tanners_here(c, pc) -> list[dict]:
    """Everybody standing here who knows hides (UI plan §6.7, "Ask a tanner"): a tanner by
    trade, or somebody whose own words say so (lane F's `knowledge.teaches` with the
    leatherworker's rows). Named, never reffed on the page; the ref is what is posted back."""
    kn = lw._lane("knowledge")
    craft = _craft(kn)
    if craft is None or not hasattr(kn, "teaches"):
        return []
    from rules import population

    try:
        price = _coins(int(kn.lore(craft)["teacher"]["price_cp"]))
    except Exception:      # noqa: BLE001
        price = ""
    out = []
    for ref, a in (getattr(c.scene, "actors", None) or {}).items():
        if a is pc or getattr(a, "is_pc", False) or getattr(a, "is_down", False):
            continue
        try:
            if kn.teaches(a, population.of_ref(c.scene, ref), craft):
                out.append({"ref": ref, "name": a.name, "price": price})
        except Exception:      # noqa: BLE001 - one odd record is no reason to lose the card
            continue
    return out


@require_POST
def leather_ask(request):
    """Show a material to a tanner and pay them to tell you about it (UI plan §6.7), the
    forge's Ask on the LEATHERWORKER's rows (price, minutes, how much each attitude step
    tells). Below indifferent they refuse in words. A point for each property taught
    (`worldclass.STUDY_MP`: a lesson is a study)."""
    from rules import attitude, goods

    c, pc, refused = _ready(request)
    if refused:
        return refused
    kn = lw._lane("knowledge")
    craft = _craft(kn)
    if craft is None or not hasattr(kn, "lesson_order"):
        return _err("Asking a tanner is not available in this build yet.", 501)
    body = read_body(request)
    doc = lw.material(str(body.get("material") or "").strip().lower())
    if doc is None:
        return _err("There is no such material.", 404)
    name = str(doc.get("name") or doc.get("id"))
    ref = str(body.get("ref") or "")
    if not any(t["ref"] == ref for t in tanners_here(c, pc)):
        return _err("Nobody here by that name knows hides.", 400)
    person = c.scene.actors[ref]
    who = person.name[:1].upper() + person.name[1:]
    rules = kn.lore(craft)["teacher"]
    size = kn.lesson_size(person, craft)
    if not size:
        hostile = attitude.of(person) == attitude.HOSTILE
        said = (f"{who} wants nothing to do with you and will not say a word about {name}."
                if hostile else
                f"{who} has no wish to help you, and keeps what they know of {name} to "
                f"themselves.")
        c.transcript.append({"who": "gm", "kind": "consequence", "text": said})
        c.save()
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0, "refused": said})
    order = kn.lesson_order(pc, doc)[:size]
    if not order:
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0,
                             "refused": f"{who} has nothing to tell you about {name} you "
                                        f"do not know."})
    cp = int(rules["price_cp"])
    purse, ok = goods.spend(pc.purse, cp)
    if not ok:
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0,
                             "refused": f"{who} asks {_coins(cp)}, and you cannot pay it."})
    pc.purse = purse
    person.purse = goods.credit(getattr(person, "purse", None) or {}, cp)
    minutes = int(rules["minutes"])
    c.scene.advance(minutes)
    keys = kn.reveal(pc, doc["id"], kn.with_gates(doc, order),
                     f"taught by {person.name}, day {kn.day_of(c.scene.clock_minutes)}")
    rows = {r.get("key"): r for r in kn.properties(pc, doc)}
    revealed = [{"key": k, "text": str((rows.get(k) or {}).get("text") or ""),
                 "row": rows.get(k)} for k in keys]
    track, progress = _progress(pc)
    lines: list[dict] = []
    levelled: list[int] = []
    for f in revealed:
        res = worldclass.award_bonus(track, progress, mp=worldclass.STUDY_MP,
                                     why=f"studied {name}: {f['text']}" if f["text"]
                                     else f"studied {name}")
        lines.extend(res.get("reasons") or [])
        levelled.extend(res.get("levelled") or [])
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{who} looks over the {name} and tells you: "
        + "; ".join(f["text"] or f["key"] for f in revealed) + f". ({_coins(cp)} paid.)")})
    c.save()
    return JsonResponse({"revealed": revealed, "paid": _coins(cp), "minutes": minutes,
                         "refused": "", "clock": _clock(c),
                         "mastery": {"lines": lines, "total": progress.mp,
                                     "level": progress.level, "levelled": levelled}})


@require_POST
def leather_manual(request):
    """Read a leatherworking manual the character has with them (plan §16): lane F's
    `knowledge.read_manual` learns what it teaches and says the mastery a first reading is
    worth (`manual.mastery`, 5, once); this view passes the hours through the one clock door
    and pays that mastery on the Leatherworker track. Before it, only the herb bench read a
    manual at all, and only herbal ones."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    if c.scene.in_encounter:
        return _err("You are in a fight. The book waits until it is over.", 409)
    kn = lw._lane("knowledge")
    craft = _craft(kn)
    if craft is None or not hasattr(kn, "read_manual"):
        return _err("Reading a leatherworking manual is not available in this build yet.",
                    501)
    body = read_body(request)
    manual = kn.manual_named(str(body.get("item") or body.get("manual") or ""), craft)
    if manual is None:
        return _err("There is no such leatherworking manual.", 400)
    if not kn.holds_manual(pc, manual):
        return _err(f"{pc.name} does not have {manual.get('name')}.", 400)
    got = dict(kn.read_manual(pc, manual, clock=_now(c)) or {})
    minutes = int(got.get("minutes") or 60)
    c.scene.advance(minutes)
    revealed = []
    for mid, keys in (got.get("revealed") or {}).items():
        doc = lw.material(mid)
        rows = {r.get("key"): r for r in kn.properties(pc, doc)} if doc else {}
        for k in keys:
            revealed.append({"material": mid, "name": lw.doc_name(mid), "key": k,
                             "text": str((rows.get(k) or {}).get("text") or "")})
    track, progress = _progress(pc)
    mastery = {"lines": [], "total": progress.mp, "level": progress.level, "levelled": []}
    if int(got.get("mp") or 0):
        res = worldclass.award_bonus(track, progress, why=f"read {manual.get('name')}",
                                     mp=int(got["mp"]))
        mastery = {"lines": res.get("reasons") or [], "total": res.get("total"),
                   "level": res.get("level"), "levelled": res.get("levelled") or []}
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{pc.name} reads {manual.get('name')} ({minutes // 60} hours)"
        + (f" and learns {len(revealed)} thing{'s' if len(revealed) != 1 else ''} about "
           f"hides and the tanner's stores." if revealed else ", and finds nothing new in it."))})
    c.save()
    return JsonResponse({"revealed": revealed, "first": bool(got.get("first")),
                         "mastery": mastery, "minutes": minutes, "clock": _clock(c)})
