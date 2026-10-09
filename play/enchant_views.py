"""The enchanting bench's API (docs/enchanting-contracts.md §6), mirroring play/forge_views.py.

The page sends what the player chose — a method, the vessel's shelf key, the essence on
each seat, a choice from the server's own list, the circle materials, a catalyst, hurry,
the face of their own d20, the minigame's 0..1 score — and the server answers with every
number: the DC and each of its terms, the odds, what the vessel holds and what the working
costs in motes and days, the tier, the product and its card, the mastery. The page never
computes a number (UI plan §12).

A step is three requests, as at the herb bench and the forge:

  check   what would happen, why each shelf entry fits or not, the failure lines in words
          before the roll, and `magic_layer.plan` for a working;
  roll    the d20 (the player's face, or the server's); the ritual's time passes; on a
          miss the step's failure rule at once; on a success (or a Bind missed by 5 or
          more, which takes FLAWED) the step waits behind a token for the game;
  finish  the score becomes a tier under the step's ceiling, the materials are spent, the
          vessel changes (a Bind goes In progress), mastery and discoveries are paid.

Nothing is spent between roll and finish: the token holds the plan in this process's
memory, and a reload or a second roll lets it go with the shelf untouched.

Read and Identify are single requests (no minigame: tasting and assay have none). Wait
moves the clock to the essence family's phase of the day through `Scene.advance`, the one
door. A binding is collected through the shared In-progress routes (play/works_views.py),
where `rules/enchanter._collect_binding` writes the layer.
"""
from __future__ import annotations

import secrets

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from rules import crafting, effectspec, sky, survival, worldclass
from rules import enchanter as en

from . import campaign as campaign_mod
from .apiutil import read_body

TRACK_ID = en.TRACK_ID

# Pending steps, by campaign id: {"token", "plan", "roll", "flawed"}. One per campaign; a
# new roll replaces it and a fresh GET of the state lets it go.
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
                     f"{'am' if hour < 12 else 'pm'}",
            "phase": sky.phase_at(minute)["phase"]}


def _hour(c) -> dict:
    """Where the clock stands among the phases of the day (owner round 4 point 10): the
    phase now, its window and minutes left, and every window for the strip's dial."""
    now = _now(c)
    at = sky.phase_at(now)
    return {"phase": at["phase"], "left": at["left"],
            "words": sky.words(now, at["phase"]), "windows": sky.windows()}


def _progress(pc):
    return worldclass.get(TRACK_ID), pc.track(TRACK_ID)


def _known(c):
    try:
        return c.engine().places()
    except Exception:      # noqa: BLE001 - a sanctum read without them is still read
        return ()


def _pct(x: float) -> str:
    return f"{round(x * 100, 1):g}%"


def _track(track, progress) -> dict:
    """The track summary and what the next pick of each enchanting perk does, in words."""
    out = dict(worldclass.track_summary(track, progress))
    ceiling = int(out.get("ceiling", worldclass.ceiling_index(progress)))
    out["tiers"] = [worldclass.quality_name(i) for i in range(ceiling + 1)]
    sizes = (track.endless or {}).get("perks") or {}
    info = {}
    for perk in track.perks:
        size, n = float(sizes.get(perk, 0) or 0), int(progress.perks.get(perk, 0))
        if perk == "quality":
            step = int(size) or 1
            nxt = (f"Your quality ceiling rises {'one step' if step == 1 else f'{step} steps'}, "
                   f"to {worldclass.quality_name(ceiling + step)}")
        elif perk == "yield":
            nxt = (f"+{_pct(size)} chance per binding that one essence is not spent, total "
                   f"{_pct(size * (n + 1))}")
        elif perk == "capacity":
            nxt = (f"+{int(size)} to what every item you bind holds, total "
                   f"+{int(size) * (n + 1)}")
        else:
            nxt = (f"+{_pct(size)} to the house top-ups of everything you bind (book "
                   f"numbers never scale), total +{_pct(size * (n + 1))}")
        info[perk] = {"next": nxt, "taken": n}
    out["perk_info"] = info
    out["band"] = worldclass.TIERS[en.level_band(progress.level) - 1]
    return out


def _works(c, pc) -> list[dict]:
    from rules import inprogress

    return inprogress.entries(pc, _now(c), here=getattr(pc, "at", None) or None,
                              craft=TRACK_ID)


def _known_of(pc, essence_id: str) -> set[str]:
    return set(en.known_traits(pc, str(essence_id or "")))


def _masked_shelf(pc, shelf: dict) -> dict:
    """The shelf with every essence trait the player has not learned taken out (lane U5's
    report, 2026-10-06: the state sent each essence's raw phase, polarity, grant and
    working traits whatever was known, so the page alone stood between the player and
    traits a Read, a seating or a binding is meant to teach). What is known is lane F's
    store (`Actor.herb_known`, `materials.essence_traits` keys); a hidden field is sent
    empty, never guessed at, and `unknown` still counts what is left to learn."""
    out = dict(shelf)
    rows = []
    for row in shelf.get("essences") or ():
        row = dict(row)
        known = _known_of(pc, row.get("id"))
        if "grants" not in known:
            row["grants"] = ""
        if "phase" not in known:
            row["phase"] = ""
        if "polarity" not in known:
            row["polarity"] = ""
        row["traits"] = [t for t in row.get("traits") or () if f"working:{t}" in known]
        rows.append(row)
    out["essences"] = rows
    return out


def _vessel_rows(pc, shelf: dict, now: int) -> dict:
    """Two things the shelf's vessel rows need that the bench's rows do not carry.

    What an item ALREADY enchanted holds, as it was made (lane H's report, 2026-10-06): the
    bench measures every vessel in this binder's hands, so an old +3 shield read "+3 of +2"
    for an Enchanter 5. A row with a layer says what its own binding holds; the working's
    check still measures a new binding in the binder's hands.

    Each piece's colour, the forge's own swatch table (`forge_views.material_color`), so
    lane U3's stage lays the vessel on the circle in its own metals and never guesses one."""
    from rules import magic_layer

    from .forge_views import material_color

    records = {v.key: v.record for v in en.vessels(pc, now)}
    out = dict(shelf)
    for group in ("vessels", "intermediates", "cant_use"):
        rows = []
        for row in shelf.get(group) or ():
            row = dict(row)
            rec = records.get(row.get("key"))
            if rec is not None and magic_layer.has_layer(rec):
                row["holds"] = en._holds_view(magic_layer.capacity(rec))
                row["holds_as"] = "made"
            pieces = {}
            for slot, p in (row.get("pieces") or {}).items():
                p = dict(p) if isinstance(p, dict) else {"material": p}
                if p.get("material"):
                    p["color"] = material_color(str(p["material"]))
                pieces[slot] = p
            row["pieces"] = pieces
            rows.append(row)
        out[group] = rows
    return out


def _conversions(pc) -> list[dict]:
    """Lane H's one-time notice of old enchanted items converted onto the layer, with their
    open questions. [] on a tree without lane H (its functions are looked up, not
    imported, so this lane's branch runs alone)."""
    fn = getattr(en, "conversions", None)
    return list(fn(pc) or []) if callable(fn) else []


def _rolls(pc, level: int) -> dict:
    """The terms the dice mat shows BEFORE a Read or an Identify is thrown (lane U1): the
    page never adds them up, and Read and Identify have no check request to carry them.
    Identify takes the better of the Enchanter check and Spellcraft, exactly as
    `enchant_identify` will when the face comes back."""
    terms = en.check_terms(pc, level)
    bonus = sum(t["value"] for t in terms)
    ident, ibonus = terms, bonus
    sc = _spellcraft(pc)
    if sc is not None and sc > bonus:
        ident, ibonus = [{"label": "Spellcraft", "value": sc}], sc
    return {"read": {"terms": terms, "bonus": bonus},
            "identify": {"terms": ident, "bonus": ibonus}}


def _state_body(c, pc) -> dict:
    track, progress = _progress(pc)
    now = _now(c)
    where = dict(en.where_here(c.scene, pc, _known(c)))
    # The biome underfoot, for lane U3's stage: a circle at camp is drawn on that ground, as
    # the forge's field kit is (play/forge_views.py `_where`).
    where.setdefault("biome", getattr(c, "biome", "") or "")
    return {
        "rolls": _rolls(pc, int(progress.level)),
        "track": _track(track, progress),
        "level": int(progress.level),
        "ceiling": worldclass.ceiling_index(progress),
        "picks_banked": worldclass.perk_picks_banked(progress),
        "methods": en.methods_view(progress.level, where),
        "shelf": _vessel_rows(pc, _masked_shelf(pc, en.shelf(pc, now)), now),
        "conversions": _conversions(pc),
        "works": _works(c, pc),
        "where": where,
        "seats": {g: en.seats_for(g) for g in (en.bench_rules().get("seats") or {})},
        "clock": _clock(c),
        "hour": _hour(c),
    }


def _ready(request):
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return None, None, _err("There is no character to work the circle.", 409)
    return c, pc, None


def _plan_from(c, pc, body):
    method = str(body.get("method") or "").strip().lower()
    if not method:
        return None, _err("Choose a method first.")
    if method in ("read", "identify"):
        return None, _err(f"{method.title()} has its own request: api/enchant/{method}.")
    _track_, progress = _progress(pc)
    plan = en.plan_step(pc, progress, method, body, scene=c.scene, known=_known(c),
                        now=_now(c))
    return plan, None


def _seat_rows(plan, pc=None) -> list[dict]:
    """The working's seats as the page draws them (UI plan §6.5): the sign of each, what is
    seated, and the choice it asks, listing only the engine's options."""
    v = plan.vessel
    if v is None:
        return []
    rows = en.seat_signs(v, plan.seats)
    for row in rows:
        ph = plan.seats.get(row["seat"])
        row["choice"] = None
        if ph is None:
            continue
        prop = effectspec.property(str((ph.grants or {}).get("property") or "")) or {}
        ch = en._choices_for(prop) if prop else None
        fixed = (ph.grants or {}).get("choice") or {}
        if ch and ch["key"] not in fixed:
            row["choice"] = dict(ch, chosen=(plan.choices.get(row["seat"]) or {}).get(
                ch["key"]))
        if prop.get("scaled") and (ph.grants or {}).get("bonus") is None:
            row["bonus"] = {"options": list((prop.get("scaled") or {}).get("values") or []),
                            "chosen": (plan.choices.get(row["seat"]) or {}).get("bonus")}
        row["grants"] = en._grant_words(ph.grants) if "grants" in _known_of(pc, ph.id) else ""
        row["motes"] = ph.motes
    return rows


def _costs(plan) -> dict | None:
    lp = plan.layer_plan
    if not lp:
        return None
    price = lp["price"]
    have = sum(p.motes for p in plan.seats.values())
    parts = [f"{int(price['motes']) - sum(s['motes'] for s in price['surcharges'])} for "
             f"the working"] + [f"{s['motes']} for {s['why'].split(':')[0].lower()}"
                                for s in price["surcharges"]]
    return {"motes": int(price["motes"]), "have": have,
            "parts": parts, "words": f"Costs {price['motes']} motes: {en._say_list(parts)}",
            "market_gp": price["market_gp"], "making_gp": price["making_gp"],
            "hours": price["hours"], "days": price["days"],
            "time_words": (f"{price['hours']} hours of work: ready in {price['days']} "
                           f"day{'s' if price['days'] != 1 else ''}")}


def _check_body(c, pc, plan) -> dict:
    now = _now(c)
    lp = plan.layer_plan
    hour = en._hour(plan.phase, now) if plan.phase else None
    if hour is not None:
        # Whether waiting for the phase outlasts the vessel's attunement (a day, owner round
        # 4 point 9): Wait for it then asks first, and the page does no sum to know it.
        att = ((plan.vessel.record.get("magic") or {}).get("circle") or {}).get("attuned") \
            if plan.vessel is not None else None
        until = int((att or {}).get("until", 0) or 0)
        hour = dict(hour, lapses=bool(att) and not hour["inside"]
                    and now + int(hour["minutes_until"]) >= until)
    return {
        "method": plan.method,
        "fits": en.fits_for(plan, pc, now),
        "vessel": plan.vessel.as_item(pc, now) if plan.vessel else None,
        "seats": _seat_rows(plan, pc),
        "problems": list(plan.problems),
        "can_roll": plan.can_roll,
        "info": list(plan.info),
        "notes": list(plan.notes),
        "dc": plan.dc, "dc_terms": list(plan.dc_terms),
        "bonus": plan.bonus, "terms": plan.terms,
        "need": plan.need, "impossible": plan.impossible,
        "lines": en.lines_for(plan),
        "plan": lp,
        "holds": en._holds_view(lp["capacity"]) if lp else None,
        "costs": _costs(plan),
        "ceiling": plan.ceiling,
        "tiers": [worldclass.quality_name(t) for t in range(max(0, plan.ceiling) + 1)],
        "hour": hour,
        "minutes": plan.minutes,
        "product": {"name": plan.name_after} if plan.name_after else None,
    }


# --- state and check ---------------------------------------------------------------------

@require_GET
def enchant_state(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    _PENDING.pop(c.id, None)
    return JsonResponse(_state_body(c, pc))


@require_POST
def enchant_check(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    plan, refused = _plan_from(c, pc, read_body(request))
    if refused:
        return refused
    return JsonResponse(_check_body(c, pc, plan))


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
    return {"lines": list(got.get("reasons") or got.get("lines") or []),
            "total": progress.mp, "level": progress.level,
            "levelled": list(got.get("levelled") or [])}


_WORDS = {"success": "Success", "failure": "Failure", "flawed": "Flawed"}


@require_POST
def enchant_roll(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    if c.scene.in_encounter:
        return _err("You are in a fight. The circle waits until it is over.", 409)
    if c.scene.awaiting:
        return _err("There is a roll waiting on you at the table.", 409)
    body = read_body(request)
    face, refused = _face(body)
    if refused:
        return refused
    _PENDING.pop(c.id, None)
    plan, refused = _plan_from(c, pc, body)
    if refused:
        return refused
    if plan.problems:
        return _err(" ".join(plan.problems))
    if plan.need is None:
        return _err(f"No roll can make DC {plan.dc} with +{plan.bonus}: it "
                    f"{plan.impossible}.")
    engine = c.engine()
    label = f"Enchanting: {plan.method.title()}"
    if face is None:
        face = engine.dice.d20(label=label, visibility="player").faces[0]
    faces = [face]
    # Unchained's `pure` raw material: roll twice and keep the better (plan §7.3).
    if plan.method == "bind" and "pure" in plan.traits:
        faces.append(engine.dice.d20(label=f"{label} (a pure essence)",
                                     visibility="player").faces[0])
    best = max(faces)
    total = best + plan.bonus
    margin = total - plan.dc
    verdict = en.verdict_of(plan, margin)       # no naturals: a skill check (CRB p.180)
    track, progress = _progress(pc)
    c.scene.advance(plan.minutes)
    roll = {"face": best, "faces": faces, "bonus": plan.bonus, "total": total,
            "dc": plan.dc, "success": verdict == "success", "margin": margin,
            "terms": plan.terms, "dc_terms": plan.dc_terms}
    out = {"roll": roll,
           "verdict": {"verdict": verdict, "natural": best, "word": _WORDS[verdict],
                       "good": verdict == "success",
                       "line": ("It took, but something went wrong in the binding."
                                if verdict == "flawed" else "")},
           "lost": [], "minutes": plan.minutes}
    line = ""
    if verdict in ("success", "flawed"):
        token = secrets.token_urlsafe(16)
        _PENDING[c.id] = {"token": token, "plan": plan, "roll": roll,
                          "flawed": verdict == "flawed"}
        out["token"] = token
        out["tuning"] = en.tuning_for(plan, _now(c))
        if verdict == "flawed":
            out["said"] = (f"Missed by {-margin}. It took, but something went wrong in the "
                           f"binding.")
    else:
        got = en.miss(pc, progress, plan, margin, now=_now(c))
        out["lost"] = got["lost"]
        out["said"] = got["said"]
        out["mastery"] = _mastery(got["mastery"], progress)
        line = (f"{plan.method.title()} at the circle: it fails (d20 {best}{plan.bonus:+d} = "
                f"{total} vs DC {plan.dc}). {got['said']}")
    out["clock"] = _clock(c)
    if line:
        c.transcript.append({"who": "gm", "kind": "consequence", "text": line})
    c.save()
    return JsonResponse(out)


# --- finish ------------------------------------------------------------------------------

def _still_there(pc, plan, now) -> str:
    """Whatever the step will spend, still in the pack: the circle's materials, the
    catalyst, the seated phials, the vessel. "" when all is there."""
    need: dict[str, int] = {}
    names: dict[str, str] = {}
    for k, n, name in plan.consumes:
        need[k] = need.get(k, 0) + int(n)
        names[k] = name
    for p in plan.seats.values() if plan.method == "bind" else ():
        need[p.key] = need.get(p.key, 0) + 1
        names[p.key] = p.name
    for k, n in need.items():
        if k.startswith("inv:"):
            have = int((pc.inventory or {}).get(k[4:], 0) or 0)
        else:
            st = (pc.stock or {}).get(k[6:])
            have = int(getattr(st, "count", 0) or 0) if st is not None else 0
        if have < n:
            return f"The {names[k]} set aside for this step is gone. Nothing was done."
    v = plan.vessel
    if v is not None and not v.blank and en.find_vessel(pc, v.key, now) is None:
        return f"The {v.name} is no longer in your pack. Nothing was done."
    return ""


@require_POST
def enchant_finish(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    pend = _PENDING.get(c.id)
    token = str(body.get("token") or "")
    if not pend or not token or not secrets.compare_digest(pend["token"], token):
        return _err("That step is no longer waiting to be finished. Roll again.", 409)
    plan = pend["plan"]
    now = _now(c)
    gone = _still_there(pc, plan, now)
    if gone:
        _PENDING.pop(c.id, None)
        return _err(gone, 409)
    tier, score = crafting.tier_from_score(body.get("score"), plan.ceiling)
    track, progress = _progress(pc)
    _PENDING.pop(c.id, None)
    got = en.finish(pc, progress, plan, tier, engine=c.engine(), now=now,
                    flawed=bool(pend.get("flawed")))
    r = pend["roll"]
    tier_name = worldclass.quality_name(tier)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{pc.name} works the circle ({plan.method}, d20 {r['face']}{r['bonus']:+d} = "
        f"{r['total']} vs DC {r['dc']}): {got['said']}")})
    c.save()
    return JsonResponse({
        "tier": tier, "tier_name": tier_name, "score": score, "ceiling": plan.ceiling,
        "stopped": bool(body.get("stopped")),
        "verdict": "flawed" if pend.get("flawed") else "success",
        "said": got["said"],
        "products": got["products"],
        "work": got.get("work"),
        "mastery": {"lines": got["lines"], "total": progress.mp, "level": progress.level,
                    "levelled": got["levelled"]},
        "discoveries": got["discoveries"],
        "minutes": plan.minutes,
        "state": _state_body(c, pc),
    })


# --- read and identify -------------------------------------------------------------------

def _first_paid(progress, key: str, why: str) -> list[dict]:
    track = worldclass.get(TRACK_ID)
    seen = int(progress.crafted.get(key, 0))
    progress.crafted[key] = seen + 1
    if seen:
        return []
    return list(worldclass.award_bonus(track, progress, why=why,
                                       mp=worldclass.FIRST_MP).get("reasons") or [])


@require_POST
def enchant_read(request):
    """Taste a pinch of an essence (plan §10, §12.3): a tenth of a phial and 10 minutes for
    one trait. Lane F's `knowledge.read` decides what is revealed when it lands; until then
    the bench's stub reveals the next unknown trait (rules/enchanter.read_essence)."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    if c.scene.in_encounter:
        return _err("You are in a fight. The essence keeps until it is over.", 409)
    body = read_body(request)
    face, refused = _face(body)
    if refused:
        return refused
    said = str(body.get("essence") or "")
    now = _now(c)
    shelf = en.phials(pc, en.reserved(pc, now))
    ph = next((p for p in shelf if p.key == said or p.id == said), None)
    if ph is None:
        return _err("You carry no such essence to take a pinch of.", 404)
    track, progress = _progress(pc)
    terms = en.check_terms(pc, progress.level)
    bonus = sum(t["value"] for t in terms)
    if face is None:
        face = c.engine().dice.d20(label=f"Read: {ph.name}", visibility="player").faces[0]
    total = face + bonus
    engine = c.engine()
    got = dict(en.read_essence(pc, ph.id, total, clock=now) or {})
    pinch = en.take_pinch(pc, ph.key)
    minutes = int(got.get("minutes", 10))
    c.scene.advance(minutes)
    doc = en._essence_docs().get(ph.id) or {}
    # `revealed` is the keys that were NEW, already written by the read (lane F's rule).
    lines: list[dict] = []
    found = []
    for k in got.get("revealed") or []:
        words = en.trait_words(doc, k)
        found.append({"key": k, "text": words})
    for f in found:
        # A point for each trait the read turned up (`worldclass.STUDY_MP`).
        lines += list(worldclass.award_bonus(worldclass.get(TRACK_ID), progress,
                                             why=f"studied {ph.name}: {f['text']}",
                                             mp=worldclass.STUDY_MP).get("reasons") or [])
    danger = got.get("danger")
    applied = en.apply_read_danger(engine, pc, ph.id, danger)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{pc.name} reads a pinch of {ph.name} (d20 {face}{bonus:+d} = {total}"
        + (f" vs DC {got['dc']}" if got.get("dc") is not None else "") + "): "
        + ("; ".join(f["text"] for f in found) if found else "nothing new."))})
    c.save()
    return JsonResponse({
        "essence": ph.id, "name": ph.name,
        "roll": {"face": face, "bonus": bonus, "total": total, "terms": terms,
                 "dc": got.get("dc"), "success": got.get("success", True)},
        "revealed": found, "pinch": pinch, "minutes": minutes,
        "danger": danger, "danger_text": effectspec.render(danger) if danger else "",
        "danger_applied": bool(applied), "stub": bool(got.get("stub")),
        "mastery": {"lines": lines, "total": progress.mp, "level": progress.level},
        "clock": _clock(c),
        "shelf": _vessel_rows(pc, _masked_shelf(pc, en.shelf(pc, _now(c))), _now(c)),
    })


def _spellcraft(pc) -> int | None:
    from rules.dice import stack

    try:
        return sum(m.value for m in stack(pc.skill_modifiers("spellcraft")))
    except Exception:      # noqa: BLE001 - untrained, or no such skill: the check alone
        return None


@require_POST
def enchant_identify(request):
    """Study an item (plan §12.1): the better of the Enchanter check and Spellcraft against
    DC 15 + its caster level; beat it to learn the intent, by 10 to see the curse; once per
    item per day. Lane F's `knowledge.identify` when it lands (rules/enchanter's stub until
    then). The page sees a curse only once it is known."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    face, refused = _face(body)
    if refused:
        return refused
    key = str(body.get("item") or "")
    now = _now(c)
    v = en.find_vessel(pc, key, now)
    from rules import magic_layer

    if v is None or not magic_layer.has_layer(v.record):
        return _err("That is not a magic item in your pack.", 404)
    track, progress = _progress(pc)
    terms = en.check_terms(pc, progress.level)
    bonus = sum(t["value"] for t in terms)
    sc = _spellcraft(pc)
    if sc is not None and sc > bonus:
        terms = [{"label": "Spellcraft", "value": sc}]
        bonus = sc
    if face is None:
        face = c.engine().dice.d20(label=f"Identify: {v.name}", visibility="player").faces[0]
    total = face + bonus
    day = now // 1440 + 1
    rec = dict(v.record)
    got = dict(en.identify_item(pc, rec, total, day=day) or {})
    st = en._stock_of(pc, v.key)
    if st is not None and isinstance(rec.get("magic"), dict):
        en._store_magic(st, rec["magic"])
    lines: list[dict] = []
    result = str(got.get("result") or "fail")
    if got.get("recipe") and result in ("intent", "curse"):
        # Lane F learns the recipe itself and names it only when it was new; the stub
        # leaves the learning here. Paid once per recipe either way.
        en.learn_recipe(pc, got["recipe"], f"identified, day {day}")
        lines += _first_paid(progress, f"recipe:{got['recipe']}",
                             f"learned the recipe of {v.name}")
    if result in ("intent", "curse") and not got.get("repeat"):
        lines += _first_paid(progress, f"identified:{rec.get('id') or v.key}",
                             f"first identified {v.name}")
    minutes = int((en.method_row("identify") or {}).get("minutes", 1))
    c.scene.advance(minutes)
    if result == "curse":
        words = ("You see the curse in it too." if got.get("cursed", True)
                 else "You look for a curse and find none: it is what it was made to be.")
    else:
        words = {"fail": "Nothing yet. You can try again tomorrow.",
                 "intent": "You learn what it was made to do.",
                 "none": "There is no magic in it to identify."}.get(result, "")
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{pc.name} studies the {v.name} (d20 {face}{bonus:+d} = {total} vs DC "
        f"{got.get('dc')}): {words}")})
    c.save()
    fresh = en.find_vessel(pc, key, _now(c))
    return JsonResponse({
        "item": key, "name": v.name, "result": result, "words": words,
        "roll": {"face": face, "bonus": bonus, "total": total, "terms": terms,
                 "dc": got.get("dc")},
        "dc": got.get("dc"), "again_on_day": got.get("again_on_day"),
        "repeat": bool(got.get("repeat")), "stub": bool(got.get("stub")),
        # Lane F's words for the curse, present only when the curse check was passed.
        "curse": got.get("curse") if result == "curse" else None,
        "card": en.item_card(fresh.record) if fresh else None,
        "mastery": {"lines": lines, "total": progress.mp, "level": progress.level},
        "minutes": minutes, "clock": _clock(c),
    })


# --- wait for it -------------------------------------------------------------------------

@require_POST
def enchant_wait(request):
    """Move the clock to the start of a phase of the day (plan §17 as the owner replaced
    it): `{phase}` or `{essence}` (its family's phase). Through `Scene.advance`, the one
    door, so everything that much time ends ends, and work In progress settles."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    if c.scene.in_encounter:
        return _err("You are in a fight. The hour will not wait for you to wait for it.",
                    409)
    body = read_body(request)
    phase = str(body.get("phase") or body.get("planet") or "").strip().lower()
    if not phase and body.get("essence"):
        k = str(body["essence"])
        ph = next((p for p in en.phials(pc) if p.key == k or p.id == k), None)
        phase = ph.phase if ph else ""
    if phase not in sky.PHASES:
        return _err(f"There is no phase of the day called {phase!r}; the phases are "
                    f"{', '.join(sky.PHASES)}.")
    now = _now(c)
    minutes = sky.next_phase(phase, now)
    ended = {}
    lived: list[str] = []
    if minutes > 0:
        # `Scene.wait`, the player's chosen wait: under a day (a phase is always under a
        # day) it is `advance` exactly; the door is shared so a longer one cannot forget
        # the pack (measured 2026-10-08: long waits through `advance` killed characters
        # carrying food and water). The engine lent first, so the people here go about
        # their day through it (`Engine.settle_on_clock`), told on this page.
        engine = c.engine()
        ended = c.scene.wait(minutes) or {}
        minutes = int(ended.get("minutes", minutes))
        lived = survival.told_on_page(c.scene, ended, pc.ref) + engine.comings_on_page()
        c.transcript.append({"who": "gm", "kind": "consequence", "text": " ".join(
            [f"{pc.name} waits {sky.span_words(minutes)} for {phase}."] + lived)})
        c.save()
    said = [str(x) for x in (ended.get("ended") or [])] if isinstance(ended, dict) else []
    return JsonResponse({"waited": minutes, "phase": phase,
                         "words": sky.words(_now(c), phase), "clock": _clock(c),
                         "hour": _hour(c), "ended": said, "body": lived,
                         "stopped": str(ended.get("stopped") or ""),
                         "works": _works(c, pc)})


# --- perks -------------------------------------------------------------------------------

@require_POST
def enchant_perks(request):
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


# --- old enchanted items, converted (lane H) ---------------------------------------------

def _lane_h(name: str):
    fn = getattr(en, name, None)
    if not callable(fn):
        return None, _err("Converted items are answered once lane H's conversion is in this "
                          "build.", 501)
    return fn, None


@require_POST
def enchant_answer(request):
    """Answer a converted item's open question (lane H): `{key, property, answer}`, where
    `answer` is the choice's own keys from the engine's options ({"foe": "undead"}, or
    {"foe": {"subtype": "goblinoid"}} for a humanoid or outsider foe). A choice the property
    would not bind is a 400 with the engine's sentence, and the question stays open."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    fn, refused = _lane_h("answer_question")
    if refused:
        return refused
    body = read_body(request)
    answer = body.get("answer")
    if not isinstance(answer, dict):
        return _err("`answer` must be the choice, as {key: value}.")
    try:
        got = dict(fn(pc, str(body.get("key") or ""), str(body.get("property") or ""),
                      answer) or {})
    except ValueError as exc:
        return _err(str(exc))
    c.save()
    return JsonResponse(dict(got, state=_state_body(c, pc)))


@require_POST
def enchant_seen(request):
    """The one-time notice of converted items was shown: `{key}` marks that item seen (its
    open questions stay on its card until answered)."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    fn, refused = _lane_h("conversion_seen")
    if refused:
        return refused
    try:
        fn(pc, str(read_body(request).get("key") or ""))
    except ValueError as exc:
        return _err(str(exc))
    c.save()
    return JsonResponse({"ok": True, "conversions": _conversions(pc)})


# --- the magic items carried ---------------------------------------------------------------

@require_GET
def enchant_items(request):
    """Every magic item carried, with its card (lane U5's ask, 2026-10-06): the ledger and
    the Identify door need the cards without a fresh GET of the state, which lets a pending
    roll go (`enchant_state` clears `_PENDING`) and so cannot be asked while the bench is
    open mid-step. Read only: nothing is cleared, nothing is advanced. The card says only
    what the owner knows (`en.item_card`): an unidentified item is "Magic, faint aura"."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    from rules import magic_layer

    now = _now(c)
    out = []
    for v in en.vessels(pc, now):
        if not magic_layer.has_layer(v.record):
            continue
        item = v.as_item(pc, now)
        out.append({"key": item["key"], "name": item["name"], "gear": item["gear"],
                    "quality_name": item["quality_name"], "badges": item["badges"],
                    "why_not": item["why_not"], "card": item.get("card")})
    return JsonResponse({"items": out})


# --- the ledger --------------------------------------------------------------------------

def _essence_row(pc, doc: dict, carried: float) -> dict:
    from rules import materials

    keys = materials.essence_traits(doc)
    have = set(en.known_traits(pc, doc["id"]))
    how = ((pc.herb_known or {}).get(doc["id"]) or {}).get("how") or {}
    return {"id": doc["id"], "name": doc["name"], "tier": doc["tier"],
            "color": doc.get("color"), "family": doc.get("family"),
            "carried": carried,
            "known": [{"key": k, "text": en.trait_words(doc, k), "how": how.get(k, "")}
                      for k in keys if k in have],
            "unknown": sum(1 for k in keys if k not in have)}


@require_GET
def enchant_ledger(request):
    """Every essence met or carried, with what is known and how (UI plan §6.8)."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    docs = en._essence_docs()
    carried: dict[str, float] = {}
    for p in en.phials(pc):
        carried[p.id] = carried.get(p.id, 0) + p.amount
    ids = [i for i in docs if i in carried or i in (pc.herb_known or {})]
    rows = [_essence_row(pc, docs[i], round(carried.get(i, 0), 1)) for i in sorted(ids)]
    return JsonResponse({"ledger": rows, "recipes": _recipes(pc)})


@require_GET
def enchant_essence(request, essence_id: str):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    doc = en._essence_docs().get(str(essence_id))
    if doc is None:
        return _err("There is no such essence.", 404)
    carried = sum(p.amount for p in en.phials(pc) if p.id == doc["id"])
    card = _essence_row(pc, doc, round(carried, 1))
    card.update({"text": doc.get("text", ""), "obtain": doc.get("obtain", ""),
                 "biomes": list(doc.get("biomes") or []),
                 "price_gp": doc.get("price_gp"),
                 "volatile": any(w.get("trait") == "volatile" for w in doc.get("working") or ()),
                 "read_minutes": int((en.method_row("read") or {}).get("minutes", 10)),
                 "read_cost": "a tenth of a phial"})
    # The favourable phase as the clock stands ("Noon, 42 minutes left"), for lane U5's card,
    # only once the player knows which phase it is: the words name it.
    if "phase" in set(en.known_traits(pc, doc["id"])) and doc.get("phase") in sky.PHASES:
        card["phase_words"] = sky.words(_now(c), doc["phase"])
    return JsonResponse(card)


def _recipes(pc) -> list[dict]:
    from rules import materials

    level = pc.track(TRACK_ID).level
    out = []
    for rid, r in sorted(materials.recipes().items()):
        if not en.recipe_known(pc, rid):
            continue
        needs = []
        for n in r.get("essences") or ():
            if n.get("grants"):
                g = str(n["grants"])
                what = "an enhancement essence" if g == "enhancement" else \
                    f"an essence granting {(effectspec.property(g) or {}).get('name', g)}"
            else:
                what = f"a {n.get('family')} essence"
            needs.append(f"{int(n.get('count') or 1)} × {what}")
        out.append({"id": rid, "name": r["name"], "vessel": r.get("vessel"),
                    "tier": r.get("tier"), "motes": r.get("motes"),
                    "caster_level": r.get("caster_level"), "needs": needs,
                    "book": [effectspec.render(d) for d in r.get("book") or ()],
                    "can_make": worldclass.tier_rank(r.get("tier")) <= en.level_band(level),
                    "text": r.get("text", "")})
    return out


@require_GET
def enchant_recipes(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    return JsonResponse({"recipes": _recipes(pc)})
