"""The forge bench's API (docs/blacksmithing-contracts.md §7), mirroring play/bench_views.py.

The page sends what the player chose — a method, what is in each slot, a batch, a shape
from the list, the face of their own d20, the minigame's 0..1 score — and the server
answers with every number: the DC, the odds, the tier, the product and its build, the
mastery, the time and the rent. The page never names a tier or computes a modifier (UI
plan §12), the bench's form of "no model authors a number".

One step is three requests, as at the herb bench:

  check   what would happen, why each rack entry fits each slot or does not, and lane B's
          `forge_items.preview` of what the work would come to;
  roll    the d20 (the player's own face, or the server's); the time and any smithy rent
          pass; on a miss the book's failure rule at once; on a success the materials are
          set aside behind a token;
  finish  the game's score becomes a tier under the step's ceiling, the product lands,
          the materials are spent, mastery and discoveries are paid.

Nothing is spent between roll and finish: the token holds a reservation in this process's
memory, and a reload, a crash or a second roll lets it go with the materials untouched.
"""
from __future__ import annotations

import secrets

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from rules import blacksmith as bs
from rules import crafting, worldclass

from . import campaign as campaign_mod
from .apiutil import read_body, read_int

TRACK_ID = bs.TRACK_ID
MAX_BATCH = 200

# Pending steps, by campaign id: {"token", "plan", "roll"}. One per campaign; a new roll
# replaces it and a fresh GET of the state lets it go (the page has just opened, so any
# step in flight was abandoned). Module memory on purpose, as at the herb bench.
_PENDING: dict[str, dict] = {}


def _err(text: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": text}, status=status)


def _clock(c) -> dict:
    minute = int(c.scene.clock_minutes or 0)
    hour, mins = (minute % 1440) // 60, minute % 60
    twelve = hour % 12 or 12
    return {"minute": minute, "day": minute // 1440 + 1,
            "label": f"Day {minute // 1440 + 1}, {twelve}:{mins:02d}"
                     f"{'am' if hour < 12 else 'pm'}"}


def _progress(pc):
    return worldclass.get(TRACK_ID), pc.track(TRACK_ID)


def _known(c):
    """`Engine.places()`, which lane G's `smithy_here` and `forge_rent` take so an
    authored place whose id does not spell its name is still found."""
    try:
        return c.engine().places()
    except Exception:      # noqa: BLE001 - lane G reads the scene's place without it
        return ()


def _where(c, pc) -> dict:
    """Where the forge stands (UI plan §6.3, §6.8 "the place line"): lane G's smithy, the
    field kit, the biome and the place's name for the stage."""
    known = _known(c)
    got = bs.where_here(c.scene, pc, known)
    smithy = got.get("smithy")
    place = ""
    try:
        here = c.engine().here()
        place = str(getattr(here, "name", "") or "")
    except Exception:      # noqa: BLE001 - a label is never worth failing a request for
        place = ""
    if smithy:
        label = ("a town smithy" if smithy.get("kind") == "town" else "your smithy")
    elif got.get("kit"):
        label = "your field kit"
    else:
        label = "no forge"
    return {"smithy": smithy, "kit": bool(got.get("kit")), "label": label,
            "place": place, "biome": c.biome}


def _reserved(c) -> dict:
    pend = _PENDING.get(c.id)
    if not pend:
        return {}
    out: dict[str, int] = {}
    for p, n in pend["plan"].consumes:
        out[p.key] = out.get(p.key, 0) + int(n)
    return out


def _rack(c, pc, reserved=True) -> list:
    return bs.rack(pc, _reserved(c) if reserved else None)


def _pct(x: float) -> str:
    return f"{round(x * 100, 1):g}%"


def _track(track, progress) -> dict:
    """The track summary (level, mastery, ceiling, perks banked), plus the tier names to
    the ceiling and what the next pick of each forge perk does, in words with numbers."""
    out = dict(worldclass.track_summary(track, progress))
    ceiling = int(out.get("ceiling", worldclass.ceiling_index(progress)))
    out["tiers"] = [worldclass.quality_name(i) for i in range(ceiling + 1)]
    out["masterwork_at"] = worldclass.quality_name(bs._mw_index())
    # The rung the work order's ladder marks "Superior · masterwork" (UI plan §4), by
    # index, so the page compares no names.
    out["masterwork_index"] = bs._mw_index()
    sizes = (track.endless or {}).get("perks") or {}
    info = {}
    for perk in track.perks:
        size, n = float(sizes.get(perk, 0) or 0), int(progress.perks.get(perk, 0))
        if perk == "quality":
            step = int(size) or 1
            # Said as the rung it reaches, without a second "+1" beside the rung's own
            # name: at Blacksmith 3 and up the ceiling is Flawless and the next rung is
            # "Flawless +1", which read "+1 to your quality ceiling: Flawless +1" (lane
            # U5's report, 2026-10-04). The rung's name is quality_name's, the one copy.
            nxt = (f"Your quality ceiling rises {'one step' if step == 1 else f'{step} steps'}, "
                   f"to {worldclass.quality_name(ceiling + step)}")
        elif perk == "yield":
            nxt = (f"+{_pct(size)} chance per Smelt or Forge of one more ingot or blank, "
                   f"total {_pct(size * (n + 1))}")
        elif perk == "hardening":
            nxt = (f"-{_pct(size)} to the drawbacks of everything you make, total "
                   f"x{round((1 - size) ** (n + 1), 4):g}")
        else:
            nxt = (f"+{_pct(size)} to the bonuses of everything you make, total "
                   f"+{_pct(size * (n + 1))}")
        info[perk] = {"next": nxt, "taken": n}
    out["perk_info"] = info
    return out


# --- what the page draws and must not work out for itself (UI plan §12, lane U2) ---------
#
# The forge page never computes a number, and it never invents a colour either: the swatch
# beside a rack row and the metal on lane U4's anvil are content, like the heat colour
# (UI plan §4, "a material swatch ... is content"). They are served from here so both draw
# the same steel. A table in the view and not in the material documents because those
# files are lane H's this wave (contracts §10); the right home is a `color` field on each
# document, and lane H can lift this table into them unchanged.

# Approximate surface colours of the bare metal, by eye from reference photographs of each
# (iron's grey, bronze's brown-gold, copper's salmon, mithral's blue-white per the UI plan
# §4). The fantasy metals follow their book descriptions where one exists (adamantine
# "dark", noqual "pale", djezet "rust-red", abysium "blue-green glow").
_COLOUR = {
    "iron": "#8a8d91", "wrought-iron": "#7b7a76", "steel": "#a7adb3",
    "high-carbon-steel": "#9097a0", "cold-iron": "#5f6670", "copper": "#b8733f",
    "bronze": "#a8763a", "bell-bronze": "#9c6b33", "brass": "#c9a54f", "tin": "#c3c6c4",
    "lead": "#6f7477", "zinc": "#a9b0b5", "bismuth": "#c2b8c8", "pewter": "#9a9d9a",
    "gold": "#d4af37", "silver": "#c8ccd0", "electrum": "#d8c47a", "platinum": "#d9dad7",
    "mithral": "#cfe0ee", "adamantine": "#3d4a4f", "star-iron": "#59606e",
    "viridium": "#5e8f5a", "abysium": "#5ab6a8", "djezet": "#b0462e", "inubrix": "#8f8a7a",
    "noqual": "#c9cfc4", "siccatite": "#a7b9c9", "horacalcum": "#c7a86a",
    "elysian-bronze": "#c8964a", "nexavaran-steel": "#7d8a95", "pattern-steel": "#8e939a",
    "fire-forged-steel": "#9a6a55", "frost-forged-steel": "#a9c2d4",
    "living-steel": "#6c8a5c", "singing-steel": "#b9c3cc", "wyrmsteel": "#7a3b33",
    "quicksilver": "#b9bec2",
}
_KIND_COLOUR = {"fuel": "#2b2622", "flux": "#d9d2c2", "quenchant": "#5d7d96",
                "treatment": "#8a6f4a"}
_WORD_COLOUR = (("haft", "#8b6a43"), ("ivory", "#d8cfb8"), ("bone", "#d8cfb8"),
                ("grip", "#6b4a2f"), ("hide", "#6b4a2f"), ("leather", "#6b4a2f"),
                ("binding", "#cbbf9f"), ("core", "#4a3b38"))
_DEFAULT_COLOUR = "#8a8d91"


def material_color(material_id: str) -> str:
    """The swatch for one material id: its own entry, else its parent metal's (an ore,
    a fitting cut from a metal), else a word in its id (a haft is wood), else its kind's,
    else iron grey. Never empty, so a swatch is never a hole."""
    mid = str(material_id or "").strip().lower()
    if not mid:
        return _DEFAULT_COLOUR
    if mid in _COLOUR:
        return _COLOUR[mid]
    doc = None
    try:
        from rules import materials as mats

        doc = mats.get(mid)
    except Exception:      # noqa: BLE001 - a swatch is never worth failing a request for
        doc = None
    parent = str((doc or {}).get("material") or "").strip().lower()
    if parent in _COLOUR:
        return _COLOUR[parent]
    # A fitting named for its metal ("brass-guard", "steel-crossguard", "cold-iron-studs"):
    # the longest metal id it starts with, so cold iron is not read as plain iron.
    for key in sorted(_COLOUR, key=len, reverse=True):
        if mid.startswith(key + "-"):
            return _COLOUR[key]
    for word, colour in _WORD_COLOUR:
        if word in mid:
            return colour
    kind = str((doc or {}).get("kind") or "")
    if kind in _KIND_COLOUR:
        return _KIND_COLOUR[kind]
    m = bs.metal(mid)
    if m is not None and m.parent in _COLOUR:
        return _COLOUR[m.parent]
    return _DEFAULT_COLOUR


def _rack_items(c, pc) -> list[dict]:
    """The rack as the page draws it: lane D's rows, each with its swatch colour."""
    out = []
    for p in _rack(c, pc):
        item = p.as_item(pc)
        item["color"] = material_color(item.get("material") or "")
        out.append(item)
    return out


def _colors(items: list[dict]) -> dict:
    """{material id: colour} for everything the page may draw: the rack's materials and
    the pieces of every worked item on it, so lane U4's stage colours a haft it was never
    shown as a rack row."""
    out = {}
    for it in items:
        mid = it.get("material")
        if mid:
            out[mid] = it.get("color") or material_color(mid)
        rec = it.get("record") or {}
        for piece in (rec.get("pieces") or {}).values():
            pm = (piece or {}).get("material")
            if pm and pm not in out:
                out[pm] = material_color(pm)
    return out


def _coins(cp: int) -> str:
    """"1 sp", "3 cp", "2 gp": the largest coin that says it exactly."""
    cp = int(cp)
    if cp and cp % 100 == 0:
        return f"{cp // 100} gp"
    if cp and cp % 10 == 0:
        return f"{cp // 10} sp"
    return f"{cp} cp"


def _place_line(c, where: dict) -> str:
    """The footer's place line (UI plan §5.2, §6.8): where you are decides which methods
    and metals are open, so it is said in words. "At the field kit", "At Brannoc's
    smithy, 1 sp an hour", "At your smithy"."""
    smithy = where.get("smithy")
    if smithy:
        rate = int(smithy.get("rate_cp_per_hour") or 0)
        if smithy.get("kind") == "owned" and not rate:
            return "At your smithy"
        keeper = ""
        ref = smithy.get("keeper")
        if ref:
            try:
                from rules import places as places_mod

                who = places_mod._actor(c.scene, ref)
                keeper = str(getattr(who, "name", "") or "")
            except Exception:      # noqa: BLE001 - a name is never worth failing for
                keeper = ""
        whose = f"{keeper}'s smithy" if keeper else (where.get("place") or "the smithy")
        if not keeper and where.get("place"):
            whose = f"the smithy at {where['place']}"
        return f"At {whose}, {_coins(rate)} an hour" if rate else f"At {whose}"
    if where.get("kit"):
        return "At the field kit"
    return "No forge here: carry a smith's field kit or find a smithy"


# The heat each step works in, for lane U3's gauge (contracts §11, `opts.heat`). The bands
# are the documented ones in docs/blacksmithing-prior-art.md §3.1 and §3.3, from the table
# Wikipedia credits to Chapman, Workshop Technology (1972), and the tempering-colour table:
#   forging     cherry red to orange, 815-1,092 °C (hot forging 950-1,250 °C)
#   welding     yellow, 1,093-1,258 °C ("common steel at a bright yellow heat")
#   plunge      from cherry red, 760-870 °C: past iron's Curie point (about 770 °C), the
#               old smith's magnet cue for "hot enough to harden"
#   smelting    a bloomery's working heat, 1,150-1,300 °C
#   oxide       tempering colours: light straw to brown (205-260 °C) for an edge, purple
#               to light blue (282-337 °C) for armour and spring work
# `hearth_c` is what the fire can reach: a field hearth less than a smithy's furnace.
# `cool_rate` is °C a second in the game's few seconds, compressed from the minute a real
# blank takes to fall out of the band, and faster for `narrow_window` metals (UI plan
# §7.2). Every number here is PROPOSED, to be tuned in lane U3's games on a flat build.
_HEAT_BANDS = {"forging": (815, 1092), "welding": (1093, 1258), "plunge": (760, 870),
               "smelting": (1150, 1300)}
_OXIDE = {"edge": (205, 260), "spring": (282, 337)}
_HEARTH_C = {"kit": 1150, "smithy": 1320}
_COOL_C_PER_S = 45.0
_NARROW_COOL = 1.25


def _heat(plan) -> dict | None:
    row = bs.method_row(plan.method) or {}
    band_name = str((row.get("tuning") or {}).get("band") or "")
    narrow = bool(plan.lead is not None and plan.lead.has("narrow_window"))
    hearth = _HEARTH_C["smithy" if plan.smithy or plan.method in ("smelt", "fold",
                                                                   "strengthen")
                      else "kit"]
    if band_name == "oxide":
        # The piece's own gear and shape: Temper's plan names neither (only Forge, Assemble
        # and Finish set them), and read off the plan a longsword blank was tempered "blue,
        # for a spring" (seen live, 2026-10-04).
        piece = (plan.slots.get("piece") or (None,))[0]
        work = getattr(piece, "work", None)
        gear = plan.gear or getattr(work, "gear", "") or ""
        shape = plan.shape or getattr(work, "shape", "") or ""
        edged = gear == "weapon" and bool((bs.shape_info(shape) or {}).get("edged"))
        lo, hi = _OXIDE["edge" if edged or not gear else "spring"]
        return {"band_name": "oxide", "band": [lo, hi], "start_c": 20, "hearth_c": 400,
                "cool_rate": 0, "narrow": narrow, "target": "edge" if edged or not gear else "spring"}
    if band_name not in _HEAT_BANDS:
        return None
    lo, hi = _HEAT_BANDS[band_name]
    rate = _COOL_C_PER_S * (_NARROW_COOL if narrow else 1.0)
    return {"band_name": band_name, "band": [lo, hi], "start_c": hearth, "hearth_c": hearth,
            "cool_rate": round(rate, 2), "narrow": narrow}


def _game_tuning(plan) -> dict:
    """What lane U3's games read from `tuning` beyond lane D's numbers (contracts §11, the
    lead's note of 2026-10-04): the bath a Quench plunges into (the game's three holds,
    brine, water and oil, by the quenchant's own id; `bath_id` is the id itself, which the
    sound bus voices), the temper colour the piece wants (an edge's straw, armour's blue),
    the alloy's window as the minor metal's share of the melt, and the work's material for
    the strike's pitch. Every value is the plan's; nothing here is a new rule."""
    out: dict = {}
    if plan.lead is not None:
        out["hardness"] = plan.lead.parent or plan.lead.id
    if plan.method == "quench":
        q = (plan.slots.get("quenchant") or (None,))[0]
        qid = str(getattr(q, "material", "") or "")
        out["bath_id"] = qid
        out["bath"] = "brine" if "brine" in qid else "oil" if "oil" in qid else "water"
    if plan.method == "temper":
        heat = _heat(plan) or {}
        out["temper"] = heat.get("target") or "edge"
    if plan.method == "alloy" and plan.lead is not None:
        recipe = (bs.bench_rules().get("alloys") or {}).get(plan.lead.id) or {}
        parts = recipe.get("parts") or []
        if len(parts) == 2 and parts[1].get("min") is not None and parts[1].get("max") is not None:
            lo, hi = float(parts[1]["min"]), float(parts[1]["max"])

            def label(part):
                if part.get("as"):
                    return str(part["as"])
                m = bs.metal(part.get("id"))
                return (m.name if m else str(part.get("id") or "")).lower()

            out["ratio"] = {"lo": lo, "hi": hi, "target": round((lo + hi) / 2, 1),
                            "of": [label(parts[0]), label(parts[1])]}
    return out


# Slot words for the work order (UI plan §6.5). The slot ids are lane D's
# (`bs.METHOD_SLOTS`, `bs.PIECES`); these are only how each reads on the page.
_SLOT_LABEL = {"ore": "Ore", "fuel": "Fuel", "flux": "Flux", "metal": "Bar", "piece": "Piece",
               "quenchant": "Quenchant", "with": "Second bar", "item": "Finished item",
               "treatment": "Treatment", "bar": "Bars", "part": "Crucible",
               "head": "Head", "haft": "Haft", "fittings": "Fittings", "body": "Body",
               "fastenings": "Fastenings", "lining": "Lining"}
_SLOT_EMPTY = {"ore": "Drop ore here, or press Enter on it in the rack",
               "fuel": "Drop fuel here, or press Enter on it in the rack",
               "flux": "Optional: a flux carries off slag",
               "metal": "Drop a bar here, or press Enter on one in the rack",
               "piece": "Drop a blank or plate here, or press Enter on one in the rack",
               "quenchant": "Drop a quenchant here, or press Enter on one in the rack",
               "with": "Optional: a second steel folds into pattern steel",
               "item": "Drop a finished item here, or press Enter on one in the rack",
               "treatment": "Drop a treatment here, or press Enter on one in the rack",
               "bar": "Drop bars of one metal here, or press Enter on them in the rack",
               "part": "Add two or more metals, or press Enter on them in the rack",
               "head": "Drop a blank here, or press Enter on one in the rack",
               "haft": "Drop a haft or grip here, or press Enter on one in the rack",
               "fittings": "Optional: a guard, studs or fittings",
               "body": "Drop a plate here, or press Enter on one in the rack",
               "fastenings": "Drop fastenings here, or press Enter on them in the rack",
               "lining": "Optional: a lining or binding"}


def _slot_view(method: str, gear: str = "") -> list[dict]:
    """The work order's slots for one method, in lane D's order, with which may stay
    empty. Assemble's follow the main piece's gear: Head, Haft, Fittings for a weapon;
    Body, Fastenings, Lining for armour and shields."""
    if method == "assemble":
        names = bs.assemble_slots(gear or "weapon")
        optional = set(names[bs.REQUIRED_PIECES:])
    elif method == "alloy":
        names, optional = ("part",), set()
    else:
        names = bs.METHOD_SLOTS.get(method, ())
        optional = set(bs.OPTIONAL.get(method, ()))
    return [{"id": s, "label": _SLOT_LABEL.get(s, s.title()), "optional": s in optional,
             "empty": _SLOT_EMPTY.get(s, f"Fill the {s} slot")} for s in names]


# Target names in the build card's rows: the sum's own ids, said as a smith would.
_TARGET_LABEL = {"attack": "Attack", "damage": "Damage", "hardness": "Hardness",
                 "hp_per_inch": "Hit points an inch", "acp": "Armour check penalty",
                 "max_dex": "Max Dex", "asf": "Spell failure", "weight_pct": "Weight",
                 "category": "Weight class", "speed_penalty": "Speed", "ac": "Armour",
                 "crit_confirm": "Critical confirm", "cmb": "Combat manoeuvres",
                 "cmd": "Manoeuvre defence"}
_MINUS = "−"


def _num(v, places: int = 1) -> str:
    """A signed number for the card, rounded only for display: "+3", "−1.8", "0"."""
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
    """The build card (UI plan §6.6) and the build summary (§6.5), every number lane B's
    and formatted here, so the page draws it and adds nothing: one row per target, one
    column per piece, the bonuses after quality, the drawbacks after the cut, and the
    final number, rounded toward zero. Book effects and what it strikes as, in words."""
    if not build or build.get("problems"):
        return None
    try:
        from rules import forge_items as fi

        main_w, other_w, per = fi.MAIN_WEIGHT, fi.OTHER_WEIGHT, fi.STRENGTHEN_PER_PASS
    except Exception:      # noqa: BLE001 - the fixed rule of contracts §4, said as text
        main_w, other_w, per = 1.0, 0.5, 1.5
    slots = list(bs.PIECES.get(gear or "weapon", bs.PIECES["weapon"]))
    pieces = pieces or {}
    cols = []
    for i, slot in enumerate(slots):
        mid = str((pieces.get(slot) or {}).get("material") or "")
        m = bs.metal(mid) if mid else None
        cols.append({"slot": slot, "label": _SLOT_LABEL.get(slot, slot.title()),
                     "material": m.name if m else (mid.replace("-", " ").title() if mid
                                                   else "none"),
                     "color": material_color(mid) if mid else "",
                     "weight": f"×{main_w:g}" if i == 0 else f"×{other_w:g}"})
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
    for t in build.get("strikes_as") or []:
        line = _render({"type": "strikes_as", "target": t})
        if line not in powers:
            powers.append(line)
    q = mult.get("quality")
    cut = mult.get("negative_cut")
    return {
        "columns": cols, "rows": rows, "summary": summary, "powers": powers,
        "masterwork": bool(build.get("masterwork")),
        "quality": quality,
        "bonus_head": f"Bonuses ×{q:g}" if q is not None else "Bonuses",
        "negative_head": f"Drawbacks ×{cut:g}" if cut is not None else "Drawbacks",
        "how": (f"The main piece counts {main_w:g}, the others {other_w:g} each, and every "
                f"strengthening pass ×{per:g}. Bonuses are multiplied by the quality"
                + (f" (×{q:g}" + (f" at {quality}" if quality else "") + ")" if q is not None
                   else "")
                + ", drawbacks cut by your level and perks"
                + (f" (×{cut:g})" if cut is not None else "")
                + ". Each row is added up, then rounded toward zero."),
    }


def _next_step(w) -> str:
    """The step a product most likely goes to next, for the result's "Next: Quench"
    button (the herb tag's `next`, UI plan §5 step 6). Read off the work itself: a bar
    is forged; a blank is quenched, then tempered, then honed if it has an edge, then
    assembled; a finished item takes a finish. A suggestion only: the player may pick
    any open method, and the server still checks whatever they pick."""
    form = getattr(w, "form", "")
    worked = list(getattr(w, "worked", []) or [])
    if form in bs.BAR_FORMS:
        return "forge"
    if form in bs.PIECE_FORMS:
        if not getattr(w, "quench", ""):
            return "quench"
        if "temper" not in worked:
            return "temper"
        if getattr(w, "gear", "") == "weapon" and bs._edged(getattr(w, "shape", "")) \
                and "hone" not in worked:
            return "hone"
        return "assemble"
    if form == "item":
        return "finish"
    return ""


def _alloys() -> list[dict]:
    """The recipe table, for the page to show beside the crucible (Vintage Story shows
    its alloy windows; the window is a fact, not a secret)."""
    out = []
    for aid, r in (bs.bench_rules().get("alloys") or {}).items():
        m = bs.metal(aid)
        parts = []
        for part in r.get("parts") or []:
            if part.get("any"):
                names = [(bs.metal(x).name if bs.metal(x) else x) for x in part["any"]]
                label = str(part.get("as") or " or ".join(names))
            else:
                pm = bs.metal(part.get("id"))
                label = pm.name if pm else str(part.get("id"))
            parts.append({"label": label, "ids": list(part.get("any") or [part.get("id")]),
                          "min": part.get("min"), "max": part.get("max")})
        out.append({"id": aid, "name": m.name if m else aid, "via": r.get("via", "alloy"),
                    "tier": m.tier if m else "", "parts": parts})
    return out


def _state_body(c, pc) -> dict:
    track, progress = _progress(pc)
    where = _where(c, pc)
    where["line"] = _place_line(c, where)
    rack = _rack_items(c, pc)
    summary = _track(track, progress)
    return {
        "track": summary,
        "level": int(progress.level),
        "ceiling": worldclass.ceiling_index(progress),
        "picks_banked": worldclass.perk_picks_banked(progress),
        "methods": bs.methods_view(progress.level, where),
        "rack": rack,
        "colors": _colors(rack),
        # Each method's work-order slots before anything is checked, and Assemble's for
        # armour beside its weapon set, so a plate clicked first finds the Body slot.
        "slots": dict({m: _slot_view(m) for m in bs.METHODS if m != "assay"},
                      **{"assemble:armour": _slot_view("assemble", "armour")}),
        "where": where,
        "shapes": bs.shapes()["families"],
        "alloys": _alloys(),
        "clock": _clock(c),
    }


def _ready(request):
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return None, None, _err("There is no character to work the forge.", 409)
    return c, pc, None


def _slots(body, items) -> tuple[dict, JsonResponse | None]:
    """`slots` as {slot: (rack Piece, count)}. A slot's value is a rack key, or
    {"key", "count"} where the count matters (the alloy's ratio)."""
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
            return {}, _err("Something on the anvil is no longer on your rack. Take it "
                            "off and look again.", 409)
        out[str(slot).strip().lower()] = (by_key[key], count)
    return out, None


def _plan_from(c, pc, body):
    method = str(body.get("method") or "").strip().lower()
    if not method:
        return None, [], None, _err("Choose a method first.")
    items = _rack(c, pc)
    slots, refused = _slots(body, items)
    if refused:
        return None, items, None, refused
    batch = read_int(body, "batch", 1, lo=1, hi=MAX_BATCH)
    track, progress = _progress(pc)
    where = _where(c, pc)
    aim = body.get("masterwork", True)
    plan = bs.plan_step(pc, progress, method, slots, batch,
                        shape=str(body.get("shape") or ""), where=where,
                        masterwork=aim is not False)
    rent = bs.rent_cp(c.scene, where.get("smithy"), plan.minutes, _known(c)) \
        if plan.units else 0
    if rent:
        from rules import goods

        have = goods.in_copper(pc.purse)
        if have < rent:
            plan.problems.append(f"The smith wants {rent} cp for the hours, and you carry "
                                 f"{have} cp.")
    return plan, items, rent, None


def _preview(plan, pc) -> dict | None:
    """Lane B's preview of what this work comes to (contracts §4), at the step's ceiling:
    for Assemble the item itself, for an earlier step the piece as the main piece of its
    shape, so the build card can show what the choice is worth before it is made."""
    track, progress = _progress(pc)
    out_w = plan.outputs[0][0] if plan.outputs else None
    if out_w is None:
        return None
    perks = {"potency": plan.perks.get("potency", 0),
             "hardening": plan.perks.get("hardening", 0)}
    if out_w.form == "item":
        pieces, gear, base = out_w.pieces, out_w.gear, out_w.shape
    elif out_w.form in bs.PIECE_FORMS:
        main = bs.PIECES.get(out_w.gear, bs.PIECES["weapon"])[0]
        pieces = {main: {"material": out_w.material, "passes": out_w.passes}}
        gear, base = out_w.gear, out_w.shape
    else:
        return None
    by_tier = {}
    for t in range(0, max(0, plan.step_ceiling) + 1):
        got = bs.preview_of(pieces, gear=gear, base=base, quality_index=t,
                            level=plan.level, perks=perks)
        if got is None:
            return None
        by_tier[worldclass.quality_name(t)] = got
    top = worldclass.quality_name(max(0, plan.step_ceiling))
    return {"at": top, "build": by_tier.get(top), "by_tier": by_tier,
            # The card and the summary line the work order draws (UI plan §6.5, §6.6),
            # at the step's ceiling, formatted here so the page adds nothing.
            "card": _card(by_tier.get(top), pieces, gear, top),
            "as": ("" if out_w.form == "item" else
                   f"As the {bs.PIECES.get(gear, bs.PIECES['weapon'])[0]} of "
                   f"{_a(bs._shape_name(base).lower())}, at {top}")}


def _product_name(w) -> str:
    """The work order's name for what the step makes. Before the roll a finished item has
    no quality yet, and `work_name` read that as Crude: the tag said "Crude Iron Longsword"
    over a ladder whose ceiling was Superior (seen live, 2026-10-04). Named without the
    quality word, which the tier the server gives at the finish supplies."""
    if w.name:
        return w.name
    if w.form == "item" and w.quality is None:
        bare = w.copy()
        bare.quality = 1
        return bs.work_name(bare)
    return bs.work_name(w)


def _a(noun: str) -> str:
    return ("an " if noun[:1] in "aeiou" else "a ") + noun


def method_bulk(method: str) -> bool:
    return bool((bs.method_row(method) or {}).get("bulk"))


def _check_body(plan, items, rent, pc) -> dict:
    # Consumes are totals for the batch; the stepper wants how many units the rack allows.
    per_unit = max(1, plan.batch)
    most = min((p.count // max(1, n // per_unit) for p, n in plan.consumes if n > 0),
               default=0)
    gear = plan.gear
    fits = bs.fits_for(plan.method, items, gear=gear)
    problems = list(plan.problems)
    if plan.method == "assemble" and not ({"head", "body"} & set(plan.slots)):
        # Before a main piece is on the anvil the gear is not known (lane D's plan reads
        # an empty order as armour), so both sets of slots are answered: a plate clicked
        # in the rack goes to Body and turns the work order to armour, a blank goes to
        # Head (UI plan §6.5, "the labels follow the shape"). Seen live: answered for
        # armour alone, a finished blade could not be put on the anvil at all.
        fits = {}
        for g in ("weapon", "armour"):
            fits.update(bs.fits_for("assemble", items, gear=g))
        gear = ""
        problems = ["Put a blank in the head slot, or a plate in the body slot."] + [
            p for p in problems if p not in (bs._MISSING.get("body"), bs._MISSING.get("head"),
                                             bs._MISSING.get("fastenings"))]
    return {
        "fits": fits,
        "slots": _slot_view(plan.method, gear),
        "gear": gear,
        "shape": plan.shape,
        "heat": _heat(plan) if plan.units or plan.method else None,
        "problems": problems,
        "can_roll": plan.can_roll,
        "info": plan.info,
        "minutes": plan.minutes, "units": plan.units, "batch": plan.batch,
        "dc": plan.dc, "bonus": plan.bonus, "terms": plan.terms,
        "need": plan.need, "impossible": plan.impossible,
        "rent_cp": rent,
        "ceiling": plan.step_ceiling,
        "tiers": [worldclass.quality_name(t) for t in range(max(0, plan.step_ceiling) + 1)],
        "masterwork": {"aiming": plan.aim, "ready": plan.masterwork_work,
                       "why": plan.masterwork_why} if plan.method == "assemble" else None,
        # How many times over what is on the anvil would go, for the batch stepper's
        # "all" (the herb bench learned a player made to count finds out halfway).
        "max_batch": most if (method_bulk(plan.method) and plan.consumes) else
        min(1, most),
        "product": [{"name": _product_name(w), "form": w.form, "count": n,
                     "material": w.material, "tier": w.tier}
                    for w, n in plan.outputs],
        "preview": _preview(plan, pc) if not plan.problems else None,
    }


# --- check -------------------------------------------------------------------------------

@require_GET
def forge_state(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    _PENDING.pop(c.id, None)
    return JsonResponse(_state_body(c, pc))


@require_POST
def forge_check(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    plan, items, rent, refused = _plan_from(c, pc, body)
    if refused:
        return refused
    return JsonResponse(_check_body(plan, items, rent, pc))


# --- roll --------------------------------------------------------------------------------

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


def _step_units(plan) -> tuple[int, str]:
    """How many steps a forge batch is for mastery, and what one of them is called.

    The owner, 2026-10-05: "batch crafting does not give equivalent experience". Measured
    before this: a smelt of 5 iron ingots paid 1 step MP where five single smelts paid 3.
    A batch of N at Smelt, Alloy, Forge or Strengthen (the bulk rows, plan §4.5) is now N
    steps through `award_step`, against the repeat limit exactly as N singles would be.
    The unit is the batch's own (`plan.units`): one per ingot smelted, blank or plate
    forged and bar strengthened, which is also one unit of the rule's inputs. Every other
    method works one piece at a time and is 1.

    Alloy is counted in pours, not bars: one pour of a 9:1 bronze makes ten bars from a
    charge the player sized, and the shares' windows decide how small a pour can be, so a
    pour is the smallest Alloy there is. Batch repeats the pour.
    """
    units = max(1, int(getattr(plan, "units", 1) or 1))
    if plan.method == "alloy":
        return units, "pour"
    return units, plan.noun or "piece"


def _mastery(got: dict, progress) -> dict:
    return {"lines": list(got.get("reasons") or []),
            "total": got.get("total", progress.mp),
            "level": got.get("level", progress.level),
            "levelled": list(got.get("levelled") or [])}


@require_POST
def forge_roll(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    if c.scene.in_encounter:
        return _err("You are in a fight. The forge waits until it is over.", 409)
    if c.scene.awaiting:
        return _err("There is a roll waiting on you at the table.", 409)
    body = read_body(request)
    face, refused = _face(body)
    if refused:
        return refused
    _PENDING.pop(c.id, None)
    plan, _items, rent, refused = _plan_from(c, pc, body)
    if refused:
        return refused
    if plan.problems:
        return _err(" ".join(plan.problems))
    if plan.need is None:
        return _err(f"No roll can make DC {plan.dc} with +{plan.bonus}: it "
                    f"{plan.impossible}.")
    if not plan.can_roll:
        return _err("Nothing on the anvil to work.")

    engine = c.engine()
    label = f"Blacksmithing: {plan.method.title()}"
    if face is None:
        face = engine.dice.d20(label=label, visibility="player").faces[0]
    faces = [face]
    # Pathfinder Unchained's `pure` raw material: roll the Craft check twice and keep the
    # better (plan §5.5). The second die is the engine's, shown beside the first.
    if plan.lead is not None and plan.lead.has("pure"):
        faces.append(engine.dice.d20(label=f"{label} (pure metal)",
                                     visibility="player").faces[0])
    best = max(faces)
    total = best + plan.bonus
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
            paid.append({"cp": rent, "to": (_where(c, pc).get("smithy") or {}).get("keeper")})
    c.scene.advance(plan.minutes)
    roll = {"face": best, "faces": faces, "bonus": plan.bonus, "total": total,
            "dc": plan.dc, "success": success, "margin": margin, "terms": plan.terms}
    out = {"roll": roll,
           "verdict": {"verdict": "success" if success else "failure", "natural": best,
                       "word": "Success" if success else "Failure"},
           "lost": [], "minutes": plan.minutes, "rent": paid}
    line = ""
    if success:
        token = secrets.token_urlsafe(16)
        _PENDING[c.id] = {"token": token, "plan": plan, "roll": roll}
        out["token"] = token
        out["tuning"] = dict(bs.tuning_for(plan), **_game_tuning(plan))
        out["heat"] = _heat(plan)
    else:
        miss = -margin
        losses = bs.failure_losses(plan, miss)
        out["lost"] = bs.spend(pc, losses)
        if out["lost"]:
            ruined = ", ".join(f"{x['count']} {x['name']}" for x in out["lost"])
            said = f"Missed by {miss}. Half of what was on the anvil is ruined: {ruined}."
        elif miss >= 5 and plan.lead is not None and plan.lead.has("malleable"):
            said = (f"Missed by {miss}. The metal is malleable and forgives it: the time is "
                    f"lost, nothing is ruined.")
        else:
            said = f"Missed by {miss}. The time is lost; the materials are kept."
        out["said"] = said
        lead = plan.lead
        # The whole batch failed on one roll: that many failed steps (`_step_units`).
        count, noun = _step_units(plan)
        got = worldclass.award_step(track, progress, method=plan.method,
                                    ingredient_id=lead.id if lead else "",
                                    rarity_rank=plan.rank_in, quality_index=0,
                                    success=False, name=lead.name if lead else "",
                                    count=count, noun=noun)
        out["mastery"] = _mastery(got, progress)
        line = (f"{plan.method.title()} at the forge: spoiled (d20 {best}{plan.bonus:+d} = "
                f"{total} vs DC {plan.dc}). {said}")
    out["clock"] = _clock(c)
    if line:
        c.transcript.append({"who": "gm", "kind": "consequence", "text": line})
    c.save()
    return JsonResponse(out)


# --- finish ------------------------------------------------------------------------------

def _first(progress, key: str) -> bool:
    seen = int(progress.crafted.get(key, 0))
    progress.crafted[key] = seen + 1
    return seen == 0


@require_POST
def forge_finish(request):
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

    # Everything that can refuse refuses before anything changes, so a refusal leaves the
    # campaign exactly as it was (one save at the end).
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

    tier, score = crafting.tier_from_score(body.get("score"), plan.step_ceiling)
    reheats = read_int(body, "reheats", 0, lo=0, hi=50)
    engine = c.engine()

    # The Yield perk: the one random reward, so its roll is shown (plan §4.2).
    perks = worldclass.perk_multipliers(progress)
    chance = float(perks.get("yield_chance", 0) or 0)
    extra, yield_line = 0, None
    if chance > 0 and plan.yields:
        roll = engine.dice.roll("1d100", label="Yield perk", visibility="player")
        at = int(round(chance * 100))
        extra = 1 if roll.total <= at else 0
        yield_line = {"why": f"Yield perk: d100 {roll.total} against {at} or less, "
                             f"{'one more ' + plan.noun if extra else 'nothing extra'}",
                      "mp": 0}

    _PENDING.pop(c.id, None)
    bs.spend(pc, [(fresh[p.key], n) for p, n in plan.consumes])
    made = bs.make(plan, tier, extra=extra)
    landed = bs.land(pc, made)
    # A reheat costs world time (plan §11: "5 minutes of world time", proposed).
    extra_minutes = reheats * int(bs.bench_rules().get("reheat_minutes", 5))
    if extra_minutes:
        c.scene.advance(extra_minutes)

    lines: list[dict] = []
    levelled: list[int] = []
    lead = plan.lead
    # A batch pays as its units worked one at a time would (`_step_units`).
    count, noun = _step_units(plan)
    got = worldclass.award_step(track, progress, method=plan.method,
                                ingredient_id=lead.id if lead else "",
                                rarity_rank=plan.rank_in, quality_index=tier, success=True,
                                name=lead.name if lead else "", count=count, noun=noun)
    lines += list(got.get("reasons") or [])
    levelled += list(got.get("levelled") or [])

    def bonus(why: str) -> None:
        res = worldclass.award_bonus(track, progress, why=why, mp=worldclass.FIRST_MP)
        lines.extend(res.get("reasons") or [])
        levelled.extend(res.get("levelled") or [])

    for _key, w, _n in landed:
        if _first(progress, f"made:{w.form}"):
            bonus(f"first {w.form}")
    worked = []
    for p, _ in plan.consumes:
        if p.material and p.material not in worked:
            worked.append(p.material)
    for mid in worked:
        if _first(progress, f"metal:{mid}"):
            m = bs.metal(mid)
            bonus(f"first work with {m.name if m else mid}")

    # Working a material reveals its working traits: you watched it behave (plan §9.2).
    discoveries = []
    now = int(c.scene.clock_minutes or 0)
    how = f"worked it, day {now // 1440 + 1}"
    kn = bs._lane("knowledge")
    for mid in worked:
        m = bs.metal(mid)
        if m is None or kn is None:
            continue
        try:
            keys = bs.working_keys(m.doc)
            new = bs.reveal(pc, mid, keys, how) if keys else []
            rows = {r.get("key"): r for r in kn.properties(pc, m.doc)} if new else {}
        except Exception:      # noqa: BLE001 - a discovery is never worth losing the work
            new, rows = [], {}
        for k in new:
            text = str((rows.get(k) or {}).get("text") or "")
            discoveries.append({"material": mid, "name": m.name, "key": k, "text": text})
            bonus(f"learned: {m.name}, {text}" if text else f"learned: {m.name}")
    if yield_line:
        lines.append(yield_line)

    r = pend["roll"]
    tier_name = worldclass.quality_name(tier)
    what = ", ".join(f"{n} {w.name}" for _k, w, n in landed)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{pc.name} works the forge: {what}, {tier_name} "
        f"(d20 {r['face']}{r['bonus']:+d} = {r['total']} vs DC {r['dc']}).")})
    c.save()

    rack_now = {p.key: p for p in _rack(c, pc)}
    products = []
    for key, w, n in landed:
        item = rack_now.get(f"stock:{key}")
        entry = {"key": f"stock:{key}", "name": w.name, "form": w.form, "count": n,
                 "item": item.as_item(pc) if item else None}
        if w.form == "item":
            rec = bs.record(w, n)
            entry["record"] = rec
            entry["build"] = bs.build_of(rec)
            entry["card"] = _card(entry["build"], (rec or {}).get("pieces"),
                                  (rec or {}).get("gear") or w.gear, tier_name)
        entry["color"] = material_color(w.material)
        entry["next"] = _next_step(w)
        products.append(entry)
    return JsonResponse({
        "tier": tier, "tier_name": tier_name, "score": score,
        "ceiling": plan.step_ceiling, "stopped": bool(body.get("stopped")),
        "products": products,
        "mastery": {"lines": lines, "total": progress.mp, "level": progress.level,
                    "levelled": levelled},
        "discoveries": discoveries,
        "minutes": plan.minutes + extra_minutes,
        "state": _state_body(c, pc),
    })


# --- assay -------------------------------------------------------------------------------

@require_POST
def forge_assay(request):
    """Test a sliver of a material (plan §9.2): lane E's `knowledge.assay` decides what is
    revealed and what it cost; this view rolls the player's Craft check, takes the sliver,
    passes the time and pays the mastery for anything learned. No minigame (tasting has
    none either)."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    if c.scene.in_encounter:
        return _err("You are in a fight. The assay waits until it is over.", 409)
    kn = bs._lane("knowledge")
    if kn is None or not hasattr(kn, "assay"):
        return _err("Assaying is not available in this build yet.", 501)
    body = read_body(request)
    mid = str(body.get("material") or "").strip().lower()
    m = bs.metal(mid)
    if m is None:
        return _err("There is no such material.", 404)
    src = bs.assay_source(pc, mid)
    if src is None:
        return _err(f"You carry no {m.name} to take a sliver from.", 409)
    where = _where(c, pc)
    if not where.get("smithy") and not where.get("kit"):
        return _err("You have no field kit with you, and there is no smithy here.", 409)
    face, refused = _face(body)
    if refused:
        return refused
    track, progress = _progress(pc)
    terms = bs.check_terms(pc, progress.level)
    bonus_v = sum(t["value"] for t in terms)
    engine = c.engine()
    if face is None:
        face = engine.dice.d20(label=f"Assay: {m.name}", visibility="player").faces[0]
    total = face + bonus_v
    now = int(c.scene.clock_minutes or 0)
    got = dict(kn.assay(pc, mid, total, clock=now) or {})
    paid = bs.pay_assay(pc, mid, got.get("cost") or {})
    minutes = int(got.get("minutes", (bs.method_row("assay") or {}).get("minutes", 10)))
    c.scene.advance(minutes)
    revealed = list(got.get("revealed") or [])
    lines: list[dict] = []
    levelled: list[int] = []
    rows = {r.get("key"): r for r in kn.properties(pc, m.doc)} if revealed else {}
    found = []
    for k in revealed:
        text = str((rows.get(k) or {}).get("text") or "")
        found.append({"key": k, "text": text, "row": rows.get(k)})
        res = worldclass.award_bonus(track, progress, mp=worldclass.FIRST_MP,
                                     why=f"learned: {m.name}, {text}" if text
                                     else f"learned: {m.name}")
        lines.extend(res.get("reasons") or [])
        levelled.extend(res.get("levelled") or [])
    # The danger of a reactive metal, applied for real (contracts §6): lane E's assay
    # only NAMES it ("the caller runs it through the engine with `apply_danger`", its own
    # docstring), and until 2026-10-04 this view showed it and applied nothing, so
    # assaying abysium never sickened anyone (lane U5's report). Through the engine, so it
    # lands as an ActiveEffect through the one applicator and is told (laws 2 and 3).
    danger = got.get("danger")
    applied = []
    if danger and hasattr(kn, "apply_danger"):
        try:
            applied = list(kn.apply_danger(engine, pc, mid, danger,
                                           because=f"assaying {m.name}") or [])
        except Exception:      # noqa: BLE001 - lane E's own contract: never crash the turn
            applied = []
    said = (f"{pc.name} assays {m.name} (d20 {face}{bonus_v:+d} = {total}): "
            + (", ".join(f["text"] or f["key"] for f in found) if found
               else "nothing new."))
    c.transcript.append({"who": "gm", "kind": "consequence", "text": said})
    c.save()
    return JsonResponse({
        "material": mid, "name": m.name,
        "roll": {"face": face, "bonus": bonus_v, "total": total, "terms": terms,
                 "dc": got.get("dc"), "success": got.get("success")},
        "dc": got.get("dc"), "success": got.get("success"),
        "revealed": found, "cost": got.get("cost"), "paid": paid, "minutes": minutes,
        "danger": danger, "danger_text": _danger_words(danger) if danger else "",
        "danger_applied": bool(applied),
        "mastery": {"lines": lines, "total": progress.mp, "level": progress.level,
                    "levelled": levelled},
        "clock": _clock(c),
        "rack": _rack_items(c, pc),
    })


# --- perks -------------------------------------------------------------------------------

@require_POST
def forge_perks(request):
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


# --- the ledger --------------------------------------------------------------------------

@require_GET
def forge_ledger(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    kn = bs._lane("knowledge")
    if kn is None or not hasattr(kn, "ledger"):
        return _err("The smith's ledger is not available in this build yet.", 501)
    return JsonResponse({"ledger": list(kn.ledger(pc) or [])})


@require_GET
def forge_material(request, material_id: str):
    """One ledger card (UI plan §6.7): what the material is, what is known of it and how,
    what you carry, and what an assay would cost and need."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    m = bs.metal(material_id)
    if m is None:
        return _err("There is no such material.", 404)
    kn = bs._lane("knowledge")
    carried = sum(p.amount for p in _rack(c, pc) if p.material == m.id and not p.old)
    card = {"id": m.id, "name": m.name, "kind": m.kind, "tier": m.tier,
            "form": m.rack_form, "text": str(m.doc.get("text") or ""),
            "glyph": bs.KIND_GLYPH.get(m.kind, "🪨"), "carried": round(carried, 1),
            "reactive": m.has("reactive"),
            "pieces": m.pieces, "properties": None, "assay_dc": None,
            "unknown": bs.unknown_count(pc, m),
            # Lane U5's card (UI plan §6.7): the swatch, where it is found or bought, what
            # an assay costs and does, and who here could be asked.
            "color": material_color(m.id),
            "obtain": str(m.doc.get("obtain") or ""), "source": str(m.doc.get("source") or ""),
            "biomes": list(m.doc.get("biomes") or []),
            "assay_minutes": int((bs.method_row("assay") or {}).get("minutes", 10)),
            "assay_cost": None,
            "smiths_here": smiths_here(c, pc)}
    if kn is not None:
        try:
            card["properties"] = list(kn.properties(pc, m.doc))
            card["assay_dc"] = int(kn.assay_dc(m.doc, pc))
        except Exception:      # noqa: BLE001 - the card shows what it can
            pass
        try:
            rules = kn.lore(kn.BLACKSMITH)["assay"]
            card["assay_minutes"] = int(rules["minutes"])
            card["assay_cost"] = kn.assay_cost(m.doc)
            # `assay_danger` only when the metal's own effect says what testing does (lane
            # U5's contract, 44-forge-ledger.js `needsConfirm`): absent, the card falls back
            # on `reactive` and warns in general words, so a reactive metal whose effect is
            # not yet written (noqual, until lane H adds §13.2's recoil) still asks first.
            found = kn.danger_of(m.doc)
            if found and _danger_words(found[1]):
                card["assay_danger"] = _danger_words(found[1])
        except Exception:      # noqa: BLE001
            pass
    return JsonResponse(card)


def _danger_words(effect: dict | None) -> str:
    """What an assay's danger does to the assayer, in words: the effect's own line and
    its note ("Sickened, for 1d4 hours: while carried and for 1d4 hours after")."""
    if not effect:
        return ""
    line = _render(effect)
    note = str(effect.get("note") or effect.get("text") or "")
    # An effect type with no renderer comes back as its own id ("suppress_magic", lane H's
    # noqual recoil, 2026-10-04): an id is not words, so the card says nothing of its own
    # and lane U5's confirm falls back on its general warning rather than print the id.
    if " " not in line.strip():
        return note
    return f"{line}: {note}" if note else line


def smiths_here(c, pc) -> list[dict]:
    """Everybody standing here who knows metals (UI plan §6.7, "Ask a smith"): a smith by
    trade, or somebody whose own words say so (lane E's `knowledge.teaches`, the herb
    bench's `teachers_here` for the forge). Named, never reffed on the page; the ref is
    what the browser posts back."""
    kn = bs._lane("knowledge")
    if kn is None or not hasattr(kn, "teaches"):
        return []
    from rules import population

    try:
        price = _coins(int(kn.lore(kn.BLACKSMITH)["teacher"]["price_cp"]))
    except Exception:      # noqa: BLE001
        price = ""
    out = []
    for ref, a in (getattr(c.scene, "actors", None) or {}).items():
        if a is pc or getattr(a, "is_pc", False) or getattr(a, "is_down", False):
            continue
        try:
            if kn.teaches(a, population.of_ref(c.scene, ref), kn.BLACKSMITH):
                out.append({"ref": ref, "name": a.name, "price": price})
        except Exception:      # noqa: BLE001 - one odd record is no reason to lose the card
            continue
    return out


@require_POST
def forge_ask(request):
    """Show a material to a smith and pay them to tell you about it (UI plan §6.7), the
    herb bench's Ask (play/herb_views.py `herb_ask`) for metals: lane E's lesson path
    (`teaches`, `lesson_size`, `lesson_order`). Their regard decides how much: below
    indifferent they refuse in words; friendlier, they tell more. Dangers first."""
    from rules import attitude, goods

    c, pc, refused = _ready(request)
    if refused:
        return refused
    kn = bs._lane("knowledge")
    if kn is None or not hasattr(kn, "lesson_order"):
        return _err("Asking a smith is not available in this build yet.", 501)
    body = read_body(request)
    m = bs.metal(str(body.get("material") or "").strip().lower())
    if m is None:
        return _err("There is no such material.", 404)
    ref = str(body.get("ref") or "")
    if not any(t["ref"] == ref for t in smiths_here(c, pc)):
        return _err("Nobody here by that name knows metals.", 400)
    person = c.scene.actors[ref]
    who = person.name[:1].upper() + person.name[1:]
    rules = kn.lore(kn.BLACKSMITH)["teacher"]
    size = kn.lesson_size(person, kn.BLACKSMITH)
    if not size:
        hostile = attitude.of(person) == attitude.HOSTILE
        said = (f"{who} wants nothing to do with you and will not say a word about "
                f"{m.name}." if hostile else
                f"{who} has no wish to help you, and keeps what they know of {m.name} "
                f"to themselves.")
        c.transcript.append({"who": "gm", "kind": "consequence", "text": said})
        c.save()
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0, "refused": said})
    order = kn.lesson_order(pc, m.doc)[:size]
    if not order:
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0,
                             "refused": f"{who} has nothing to tell you about {m.name} "
                                        f"you do not know."})
    cp = int(rules["price_cp"])
    purse, ok = goods.spend(pc.purse, cp)
    if not ok:
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0,
                             "refused": f"{who} asks {_coins(cp)}, and you cannot pay it."})
    pc.purse = purse
    person.purse = goods.credit(getattr(person, "purse", None) or {}, cp)
    minutes = int(rules["minutes"])
    c.scene.advance(minutes)
    keys = kn.reveal(pc, m.id, kn.with_gates(m.doc, order),
                     f"taught by {person.name}, day {kn.day_of(c.scene.clock_minutes)}")
    rows = {r.get("key"): r for r in kn.properties(pc, m.doc)}
    revealed = [{"key": k, "text": str((rows.get(k) or {}).get("text") or ""), "row": rows.get(k)}
                for k in keys]
    track, progress = _progress(pc)
    lines: list[dict] = []
    levelled: list[int] = []
    for f in revealed:
        res = worldclass.award_bonus(track, progress, mp=worldclass.FIRST_MP,
                                     why=f"learned: {m.name}, {f['text']}" if f["text"]
                                     else f"learned: {m.name}")
        lines.extend(res.get("reasons") or [])
        levelled.extend(res.get("levelled") or [])
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{who} looks over the {m.name} and tells you: "
        + "; ".join(f["text"] or f["key"] for f in revealed) + f". ({_coins(cp)} paid.)")})
    c.save()
    return JsonResponse({"revealed": revealed, "paid": _coins(cp), "minutes": minutes,
                         "refused": "", "clock": _clock(c),
                         "mastery": {"lines": lines, "total": progress.mp,
                                     "level": progress.level, "levelled": levelled}})
