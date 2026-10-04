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
    sizes = (track.endless or {}).get("perks") or {}
    info = {}
    for perk in track.perks:
        size, n = float(sizes.get(perk, 0) or 0), int(progress.perks.get(perk, 0))
        if perk == "quality":
            step = int(size) or 1
            nxt = (f"+{step} to your quality ceiling: "
                   f"{worldclass.quality_name(ceiling + step)}")
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
    return {
        "track": _track(track, progress),
        "level": int(progress.level),
        "ceiling": worldclass.ceiling_index(progress),
        "picks_banked": worldclass.perk_picks_banked(progress),
        "methods": bs.methods_view(progress.level, where),
        "rack": [p.as_item(pc) for p in _rack(c, pc)],
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
    return {"at": top, "build": by_tier.get(top), "by_tier": by_tier}


def method_bulk(method: str) -> bool:
    return bool((bs.method_row(method) or {}).get("bulk"))


def _check_body(plan, items, rent, pc) -> dict:
    # Consumes are totals for the batch; the stepper wants how many units the rack allows.
    per_unit = max(1, plan.batch)
    most = min((p.count // max(1, n // per_unit) for p, n in plan.consumes if n > 0),
               default=0)
    gear = plan.gear
    return {
        "fits": bs.fits_for(plan.method, items, gear=gear),
        "problems": list(plan.problems),
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
        "product": [{"name": w.name or bs.work_name(w), "form": w.form, "count": n,
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
        out["tuning"] = bs.tuning_for(plan)
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
        got = worldclass.award_step(track, progress, method=plan.method,
                                    ingredient_id=lead.id if lead else "",
                                    rarity_rank=plan.rank_in, quality_index=0,
                                    success=False, name=lead.name if lead else "")
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
    got = worldclass.award_step(track, progress, method=plan.method,
                                ingredient_id=lead.id if lead else "",
                                rarity_rank=plan.rank_in, quality_index=tier, success=True,
                                name=lead.name if lead else "")
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
    # The danger of a reactive metal is applied by lane E's assay, which holds the actor
    # (contracts §6: "reactive metals apply their carrier effect for real"); it is shown
    # here, never applied a second time.
    danger = got.get("danger")
    said = (f"{pc.name} assays {m.name} (d20 {face}{bonus_v:+d} = {total}): "
            + (", ".join(f["text"] or f["key"] for f in found) if found
               else "nothing new."))
    c.transcript.append({"who": "gm", "kind": "consequence", "text": said})
    c.save()
    return JsonResponse({
        "material": mid, "name": m.name,
        "roll": {"face": face, "bonus": bonus_v, "total": total, "terms": terms},
        "revealed": found, "cost": got.get("cost"), "paid": paid, "minutes": minutes,
        "danger": danger,
        "mastery": {"lines": lines, "total": progress.mp, "level": progress.level,
                    "levelled": levelled},
        "clock": _clock(c),
        "rack": [p.as_item(pc) for p in _rack(c, pc)],
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
            "unknown": bs.unknown_count(pc, m)}
    if kn is not None:
        try:
            card["properties"] = list(kn.properties(pc, m.doc))
            card["assay_dc"] = int(kn.assay_dc(m.doc, pc))
        except Exception:      # noqa: BLE001 - the card shows what it can
            pass
    return JsonResponse(card)
