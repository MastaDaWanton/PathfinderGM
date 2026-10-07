"""The alchemy bench's API (docs/alchemy-contracts.md §8), mirroring play/forge_views.py and
play/enchant_views.py.

The page sends what the player chose — a method, the shelf keys in each role (inputs, a
solvent, a vessel, catalysts that are never spent), a formula or Experiment, the traits it
picks for the slots, the batch, the face of their own d20, the minigame's 0..1 score — and
the server answers with every number: the DC and each of its terms, the odds, the mishap
and toxic lines before the roll, the possible-formulae count, the slots and why each
trait fits or does not, the mix's colour, level and turbidity, the tier, the product and
its build, the mastery. The page never computes a number (contracts §8, UI plan §12).

A step is three requests, as at the herb bench, the forge and the circle:

  check   what would happen (`alchemist.plan_step`), nothing changed;
  roll    the d20 (the player's face, or the server's). A toxic reagent lands at the start of
          the step unless the alchemist is protected; the step's time passes; a miss by 5 or
          more ruins half the materials and every unstabilised volatile input's mishap
          lands on the alchemist, once (`flare: true`); a success waits behind a token;
  finish  the score becomes a tier under the ceiling, the materials are spent, the records
          are written (rules/alchemy_items.py), and work that waits goes In progress.

Nothing is spent between roll and finish: the token holds the plan in this process's
memory, and a fresh GET of the state lets it go with the shelf untouched (the forge's
`_PENDING`, contracts §8).

Assay, identify, learn, ask, collect, perks and recipes are single requests. Assay and
identify have no minigame (tasting and the forge's assay have none either).
"""
from __future__ import annotations

import secrets

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from rules import alchemist as al
from rules import alchemy_items as items
from rules import crafting, effectspec, formulae, knowledge, worldclass

from . import campaign as campaign_mod
from .apiutil import read_body

TRACK_ID = al.TRACK_ID
MAX_BATCH = 200

# Pending steps, by campaign id: {"token", "plan", "roll"}. One per campaign; a new roll
# replaces it and a fresh GET of the state lets it go.
_PENDING: dict[str, dict] = {}

# Mastery for studying a material: 1 for each property an assay reveals, 0 if none (the
# owner, 2026-10-06). `worldclass.STUDY_MP` once branch fix/study-pays-one merges; until
# then this lane's own 1, said in its report.
STUDY_MP = int(getattr(worldclass, "STUDY_MP", 1))


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


def _known_places(c):
    try:
        return c.engine().places()
    except Exception:      # noqa: BLE001 - a laboratory read without them is still read
        return ()


def _where(c, pc) -> dict:
    got = al.where_here(c.scene, pc, _known_places(c))
    place = ""
    try:
        place = str(getattr(c.engine().here(), "name", "") or "")
    except Exception:      # noqa: BLE001 - a label is never worth failing a request for
        place = ""
    lab = got.get("lab")
    scene_kind = (lab or {}).get("kind") or ("kit" if got.get("kit") else "")
    return dict(got, place=place, biome=getattr(c, "biome", "") or "",
                scene={"kind": scene_kind or "kit", "biome": getattr(c, "biome", "") or "",
                       "minute": _now(c)})


def _reserved(c) -> dict:
    pend = _PENDING.get(c.id)
    if not pend:
        return {}
    out: dict[str, int] = {}
    for it, n in pend["plan"].consumes:
        out[it.key] = out.get(it.key, 0) + int(n)
    return out


def _pct(x: float) -> str:
    return f"{round(x * 100, 1):g}%"


def _track(track, progress) -> dict:
    """The track summary, and what the next pick of each perk does, in words."""
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
            nxt = (f"+{_pct(size)} chance per bottling of one more, total "
                   f"{_pct(size * (n + 1))}")
        elif perk == "containment":
            nxt = (f"-{int(size)} DC on a volatile step and every mishap's dice one step "
                   f"smaller, total -{int(size) * (n + 1)}")
        else:
            nxt = f"+{_pct(size)} {perk} to everything you make, total +{_pct(size * (n + 1))}"
        info[perk] = {"next": nxt, "taken": n}
    out["perk_info"] = info
    out["band"] = worldclass.TIERS[al.rarity_ceiling(progress.level) - 1]
    out["spell_level_cap"] = formulae.spell_level_cap(progress.level)
    out["grade_cap"] = int(progress.level)
    return out


# --- the shelf as the page draws it ----------------------------------------------------------

# Working traits the shelf always names, known or not: the hazards (the stakes are stated
# before every roll, plan §8.1, §8.4) and the roles (what a thing is for at the bench is
# plain from it). The rest of a reagent's working traits are discoveries, shown once known.
_ALWAYS = ("volatile", "toxic_to_handle", "catalyst", "apparatus", "stabilizer")


def _unknown(pc, doc) -> int:
    try:
        return int(knowledge.unknown_count(pc, doc))
    except Exception:      # noqa: BLE001
        return 0


def _known_working(pc, doc) -> set[str]:
    keys = set(knowledge.known_keys(pc, doc)) if doc else set()
    out = set()
    for k, w in zip([k for k in knowledge.property_keys(doc) if str(k).startswith("t")],
                    doc.get("working") or ()):
        if k in keys:
            out.add(str((w or {}).get("trait") if isinstance(w, dict) else w))
    return out


def _row(pc, it: al.Item) -> dict:
    rec = it.record or {}
    badges = it.badges()
    if it.doc is not None:
        known = _known_working(pc, it.doc)
        badges = [b for b in badges if b.replace(" ", "_") in _ALWAYS
                  or b.replace(" ", "_") in known]
    out = {"key": it.key, "name": it.name, "material": it.material, "kind": it.kind,
           "group": it.group, "count": it.count, "amount": it.amount, "tier": it.tier,
           "rank": it.rank, "glyph": al.KIND_GLYPH.get(it.kind, "🜂"), "badges": badges,
           "color": it.color(), "old": it.old, "work": it.work,
           "unknown": _unknown(pc, it.doc) if it.doc is not None else 0,
           "family": it.family or None, "form": it.form or None,
           "liquid": it.liquid}
    if rec:
        q = rec.get("quality_index")
        out["quality_name"] = worldclass.quality_name(int(q)) if q is not None else None
        out["grades"] = [{"essence": r.get("essence") or r["key"], "grade": r.get("grade", 1)}
                         for r in rec.get("traits") or ()]
        keeps = items.form_row(str(rec.get("form") or "")).get("keeps") \
            if it.intermediate else None
        if keeps:
            ends = int(rec.get("made_minute") or 0) + int(keeps)
            out["keeps_until_day"] = ends // 1440 + 1
    return out


def _shelf(c, pc, reserved=True) -> list[dict]:
    return [_row(pc, it) for it in al.shelf(pc, _now(c), _reserved(c) if reserved else None)]


def _works(c, pc) -> list[dict]:
    from rules import inprogress

    return inprogress.entries(pc, _now(c), here=getattr(pc, "at", None) or None,
                              craft=TRACK_ID)


def _rolls(pc, level: int, lab: bool) -> dict:
    """The terms the dice mat shows BEFORE an assay or an identify is thrown (they have no
    check request to carry them), so the page never adds them up."""
    terms = al.check_terms(pc, level, lab=lab)
    return {"assay": {"terms": terms, "bonus": sum(t["value"] for t in terms)},
            "identify": {"terms": terms, "bonus": sum(t["value"] for t in terms)}}


def _formula_row(pc, fid: str, level: int) -> dict | None:
    row = formulae.get(fid)
    if row is None:
        return None
    req = (row.get("requires") or {}).get("essences") or {}
    return {"id": row["id"], "name": row.get("name"), "kind": row.get("kind"),
            "family": row.get("family"), "families": list(row.get("families") or ()),
            "requires": [{"essence": e, "grade": g} for e, g in req.items()],
            "requires_words": ", ".join(f"{e} {g}" if int(g) > 1 else e
                                        for e, g in req.items()),
            "how": knowledge.formula_how(pc, fid), "spell": row.get("spell"),
            "spell_level": row.get("spell_level"), "caster_level": row.get("caster_level"),
            "craft_dc": row.get("craft_dc"), "price_gp": row.get("price_gp"),
            "source": row.get("source"), "book": bool(row.get("book")),
            "harmful": bool(row.get("harmful")), "delivers": row.get("delivers") or {},
            "brewable": bool(row.get("brewable", True)), "waiting": row.get("waiting") or [],
            "reach": formulae.reach_problems(row, level)}


def _ensure_starting(c, pc) -> list[str]:
    """The four classics every alchemist knows (owner Q5.4), taught the first time the
    bench is opened; idempotent, and saved only when something was new."""
    got = al.known_starting(pc, clock=_now(c))
    if got:
        c.save()
    return got


def _state_body(c, pc) -> dict:
    track, progress = _progress(pc)
    where = _where(c, pc)
    lab = bool(where.get("lab"))
    return {
        "rolls": _rolls(pc, int(progress.level), lab),
        "track": _track(track, progress),
        "level": int(progress.level),
        "ceiling": worldclass.ceiling_index(progress),
        "picks_banked": worldclass.perk_picks_banked(progress),
        "methods": al.methods_view(progress.level, where),
        "shelf": _shelf(c, pc),
        "works": _works(c, pc),
        "where": where,
        "clock": _clock(c),
        "formulae": [r for r in (_formula_row(pc, f, progress.level)
                                 for f in formulae.known(pc)) if r],
        "recipes": _recipes(c),
    }


def _ready(request):
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return None, None, _err("There is no character to work the bench.", 409)
    _ensure_starting(c, pc)
    return c, pc, None


def _batch(body) -> tuple[int, JsonResponse | None]:
    raw = body.get("batch", 1)
    try:
        n = int(raw or 1)
    except (TypeError, ValueError):
        return 1, _err("The batch is a whole number.")
    if not 1 <= n <= MAX_BATCH:
        return 1, _err(f"A batch is 1 to {MAX_BATCH}.")
    return n, None


def _plan_from(c, pc, body, *, reserved=None):
    method = str(body.get("method") or "").strip().lower()
    if not method:
        return None, _err("Choose a method first.")
    if method == "assay":
        return None, _err("Assay has its own request: api/alchemy/assay.")
    _n, refused = _batch(body)
    if refused:
        return None, refused
    _t, progress = _progress(pc)
    plan = al.plan_step(pc, progress, method, body, where=_where(c, pc), now=_now(c),
                        reserved=reserved)
    return plan, None


def _secret(plan) -> bool:
    """An experiment about to find a formula the alchemist does not know: its name stays
    unsaid until the bottle is made (owner Q5.3: "a count of possible formulae, never their
    names"). The DC and the product preview would name it, so neither is sent."""
    m = plan.match or {}
    return bool(plan.method == "bottle" and plan.experiment and m.get("found")
                and m.get("new"))


def _ladder(plan) -> list[dict]:
    """The paper tag's ladder (UI plan §6.5): each tier under the ceiling, its caster level
    and price for a spell potion ("Fine, CL 2, 100 gp"). Every number the server's."""
    out = []
    if plan.method != "bottle" or not plan.family:
        return out
    for t in range(max(0, int(plan.ceiling)) + 1):
        rec = al.make(plan, t, now=0)[0]
        b = items.build(rec)
        out.append({"tier": t, "name": worldclass.quality_name(t),
                    "caster_level": b.get("caster_level"), "price_gp": b.get("price_gp")})
    return out


def _check_body(c, pc, plan) -> dict:
    secret = _secret(plan)
    shelf_items = al.shelf(pc, _now(c), _reserved(c))
    match = dict(plan.match or {})
    if secret:
        match = {"formula": None, "experiment": True, "found": None, "new": None,
                 "ambiguous": 0, "missing": [], "refused": [], "family": plan.family,
                 "target": None, "secret": True}
    else:
        match.pop("core", None)
        if match.get("formula"):
            match["name"] = (formulae.get(match["formula"]) or {}).get("name")
    product = None
    tiers = []
    if plan.units and not plan.problems and plan.method != "transmute" and not secret:
        rec = al.make(plan, 1, now=_now(c))[0]
        b = items.build(rec)
        product = {"name": b["name"], "family": b["family"], "how": b["how"],
                   "action": b["action"], "lines": b["lines"], "price_gp": b["price_gp"],
                   "caster_level": b["caster_level"], "holds_spell": b["holds_spell"],
                   "target": b["target"], "range_increment_ft": b["range_increment_ft"],
                   "splash": b["splash"], "keeps_minutes": b["keeps_minutes"],
                   "tier": b["tier"], "build": b}
        tiers = _ladder(plan)
    dc_terms = plan.dc_terms
    if secret:
        dc_terms = [{"label": "an experiment" if i == 0 else t["label"], "value": t["value"]}
                    for i, t in enumerate(plan.dc_terms)]
    choice = plan.choice or {}
    rent = al.rent_cp(c.scene, plan.lab, plan.minutes, _known_places(c))
    known_for_family = []
    if plan.method == "bottle" and plan.vessel is not None:
        fams = formulae.vessel_families(plan.vessel.material)
        for fid in formulae.known(pc):
            row = formulae.get(fid) or {}
            if any(f in fams for f in row.get("families") or [row.get("family")]):
                known_for_family.append({"id": fid, "name": row.get("name"),
                                         "requires": (row.get("requires") or {}).get(
                                             "essences") or {}})
    return {
        "method": plan.method,
        "fits": al.fits_for(plan.method, shelf_items),
        "problems": list(plan.problems),
        "can_roll": plan.can_roll,
        "info": plan.info,
        "notes": list(plan.notes),
        "dc": plan.dc, "dc_terms": dc_terms,
        "bonus": plan.bonus, "terms": plan.terms,
        "need": plan.need, "impossible": plan.impossible,
        "units": plan.units, "minutes": plan.minutes, "waits": plan.waits,
        "rent_cp": rent,
        "stakes": al.stakes(plan),
        "could": plan.could or None,
        "match": match,
        "formulae": known_for_family,
        "family": plan.family or None,
        "slots": {"family": plan.family, "slots": choice.get("slots", 0),
                  "free": choice.get("free", 0),
                  "traits": [{k: v for k, v in r.items() if k != "raw"}
                             for r in choice.get("rows") or ()],
                  "drawbacks": [{k: v for k, v in r.items() if k != "raw"}
                                for r in choice.get("drawback_rows") or ()]},
        "candidates": plan.candidates,
        "liquid": al.liquid_for(plan),
        "tuning": al.tuning_for(plan) if plan.units else None,
        "product": product,
        "tiers": tiers,
        "ceiling": plan.ceiling,
        "lab": plan.lab,
    }


# --- state and check ---------------------------------------------------------------------------

@require_GET
def alchemy_state(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    _PENDING.pop(c.id, None)
    _ensure_starting(c, pc)
    return JsonResponse(_state_body(c, pc))


@require_POST
def alchemy_check(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    plan, refused = _plan_from(c, pc, read_body(request), reserved=_reserved(c))
    if refused:
        return refused
    return JsonResponse(_check_body(c, pc, plan))


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


def _outcome_rows(outcomes) -> list[dict]:
    out = []
    for o in outcomes or ():
        try:
            out.append({"tell": getattr(o, "tell", "") or "",
                        "effects": list(getattr(o, "effects", None) or [])})
        except Exception:  # noqa: BLE001
            continue
    return out


def _coins(cp: int) -> str:
    cp = int(cp)
    gp, rest = divmod(cp, 100)
    sp, cc = divmod(rest, 10)
    parts = [f"{gp} gp" if gp else "", f"{sp} sp" if sp else "", f"{cc} cp" if cc else ""]
    return " ".join(p for p in parts if p) or "0 cp"


@require_POST
def alchemy_roll(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    if c.scene.in_encounter:
        return _err("You are in a fight. The bench waits until it is over.", 409)
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
    if not plan.can_roll:
        return _err("Nothing on the bench to work.")
    engine = c.engine()
    track, progress = _progress(pc)

    # A toxic reagent hurts at the start of the step, whatever the roll (plan §8.4).
    toxic = al.apply_rule(engine, pc, plan.toxics, kind="toxic") if plan.toxics else []

    label = f"Alchemy: {plan.method.title()}"
    if face is None:
        face = engine.dice.d20(label=label, visibility="player").faces[0]
    faces = [face]
    if plan.roll_twice:
        # Pathfinder Unchained's pure material: roll twice and keep the better.
        faces.append(engine.dice.d20(label=f"{label} (pure)", visibility="player").faces[0])
    best = max(faces)
    total = best + plan.bonus
    margin = total - plan.dc
    success = margin >= 0                      # a skill check: no naturals (CRB p.180)

    paid = []
    rent = al.rent_cp(c.scene, plan.lab, plan.minutes, _known_places(c))
    if rent:
        from rules import goods

        purse, ok = goods.spend(pc.purse, rent)
        if ok:
            pc.purse = purse
            paid.append({"cp": rent, "words": _coins(rent),
                         "to": (plan.lab or {}).get("keeper")})
    c.scene.advance(plan.minutes)
    roll = {"face": best, "faces": faces, "bonus": plan.bonus, "total": total,
            "dc": plan.dc, "success": success, "margin": margin, "terms": plan.terms,
            "dc_terms": plan.dc_terms if not _secret(plan) else None}
    out = {"roll": roll,
           "verdict": {"verdict": "success" if success else "failure", "natural": best,
                       "word": "Success" if success else "Failure", "good": success},
           "lost": [], "minutes": plan.minutes, "rent": paid,
           "toxic": _outcome_rows(toxic), "flare": False, "mishap": []}
    line = ""
    if success:
        token = secrets.token_urlsafe(16)
        _PENDING[c.id] = {"token": token, "plan": plan, "roll": roll}
        out["token"] = token
        out["tuning"] = al.tuning_for(plan)
        out["liquid"] = al.liquid_for(plan)
    else:
        miss = -margin
        losses = al.failure_losses(plan, miss)
        out["lost"] = al.spend(pc, losses)
        mishap = []
        if miss >= 5 and plan.mishaps:
            # Once, not once per unit: one flash in one crucible (plan §15.2).
            mishap = al.apply_rule(engine, pc, plan.mishaps, kind="mishap")
            out["flare"] = True
            out["mishap"] = _outcome_rows(mishap)
        if out["lost"]:
            ruined = ", ".join(f"{x['count']} {x['name']}" for x in out["lost"])
            said = f"Missed by {miss}. Half of what was on the bench is ruined: {ruined}."
        else:
            said = f"Missed by {miss}. The time is lost; the materials are kept."
        if out["flare"]:
            tells = [m["tell"] for m in out["mishap"] if m["tell"]]
            said += (" It flares: " + "; ".join(tells) + ".") if tells else " It flares."
        out["said"] = said
        got = worldclass.award_step(track, progress, method=plan.method,
                                    ingredient_id=plan.lead, rarity_rank=plan.rank_in,
                                    quality_index=0, success=False,
                                    name=(items.doc_of(plan.lead) or {}).get("name", ""),
                                    count=plan.units, noun=plan.noun)
        out["mastery"] = _mastery(got, progress)
        line = (f"{plan.method.title()} at the alchemy bench: it fails (d20 {best}"
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


@require_POST
def alchemy_finish(request):
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
    now = _now(c)

    # Everything that can refuse refuses before anything changes (one save at the end).
    fresh = {it.key: it for it in al.shelf(pc, now)}
    need: dict[str, int] = {}
    for it, n in plan.consumes:
        need[it.key] = need.get(it.key, 0) + int(n)
    for key, n in need.items():
        have = fresh.get(key)
        if have is None or have.count < n:
            _PENDING.pop(c.id, None)
            name = next(it.name for it, _ in plan.consumes if it.key == key)
            return _err(f"The {name} set aside for this step is gone. Nothing was made.", 409)

    tier, score = crafting.tier_from_score(body.get("score"), plan.ceiling)
    # No coin is taken at Bottle: "ingredients only" (the owner, 2026-10-07). Brewing costs
    # what goes into it and nothing more; a cheap-ingredient potion selling for far more
    # than it cost is accepted knowingly. Lane H's `pricing.coin_to_make` (the book's
    # making fraction less the inputs' worth) was built and is deliberately not called.
    engine = c.engine()
    perks = worldclass.perk_multipliers(progress)
    chance = float(perks.get("yield_chance", 0) or 0)
    extra, yield_line = 0, None
    if chance > 0 and plan.yields:
        roll = engine.dice.roll("1d100", label="Yield perk", visibility="player")
        at = int(round(chance * 100))
        extra = 1 if roll.total <= at else 0
        yield_line = {"why": f"Yield perk: d100 {roll.total} against {at} or less, "
                             f"{'one more' if extra else 'nothing extra'}", "mp": 0}

    _PENDING.pop(c.id, None)
    al.spend(pc, [(fresh[it.key], n) for it, n in plan.consumes])
    made = al.make(plan, tier, extra=extra, now=now)
    landed = al.land(pc, plan, made, now=now, where=_where(c, pc))

    lines: list[dict] = []
    levelled: list[int] = []
    got = worldclass.award_step(track, progress, method=plan.method,
                                ingredient_id=plan.lead, rarity_rank=plan.rank_in,
                                quality_index=tier, success=True,
                                name=(items.doc_of(plan.lead) or {}).get("name", ""),
                                count=plan.units, noun=plan.noun)
    lines += list(got.get("reasons") or [])
    levelled += list(got.get("levelled") or [])

    def bonus(why: str, mp: int = worldclass.FIRST_MP) -> None:
        res = worldclass.award_bonus(track, progress, why=why, mp=mp)
        lines.extend(res.get("reasons") or [])
        levelled.extend(res.get("levelled") or [])

    # Firsts (plan §4.4): a product family made, a reagent worked, a formula written.
    for rec in made:
        fam = rec.get("form") or rec.get("family")
        if fam and _first(progress, f"made:{fam}"):
            bonus(f"first {items.form_row(fam).get('word', '').lower() or items.FAMILY_WORDS.get(fam, fam)}")
    raw = [it.material for it, _ in plan.inputs if it.material and it.doc is not None]
    raw += [plan.solvent.material] if plan.solvent is not None and plan.solvent.material else []
    for mid in dict.fromkeys(raw):
        if _first(progress, f"reagent:{mid}"):
            bonus(f"first work with {(items.doc_of(mid) or {}).get('name', mid)}")
    found = None
    if plan.method == "bottle" and plan.experiment and (plan.match or {}).get("found"):
        fid = plan.match["formula"]
        if formulae.learn(pc, fid, "experiment", clock=now):
            found = _formula_row(pc, fid, progress.level)
            bonus(f"first formula written: {found['name'] if found else fid}")

    # What the work taught (plan §13.1): a material's working traits by working it, and
    # every trait the product actually carries (Skyrim's rule).
    discoveries = []
    how = f"worked it, day {now // 1440 + 1}"
    teach: dict[str, list[str]] = {}
    for mid in dict.fromkeys(raw + [c_.material for c_ in plan.catalysts if c_.material]):
        teach.setdefault(mid, []).extend(al.working_keys(mid))
    for rec in made:
        for r in list(rec.get("traits") or []) + list(rec.get("drawbacks") or []):
            for mid in r.get("from") or ():
                teach.setdefault(mid, []).extend(al.keys_for(mid, r["key"]))
    for mid, keys in teach.items():
        doc = items.doc_of(mid)
        if doc is None or not keys:
            continue
        try:
            new = al.reveal(pc, mid, list(dict.fromkeys(keys)), how)
            rows = {r.get("key"): r for r in knowledge.properties(pc, doc)} if new else {}
        except Exception:      # noqa: BLE001 - a discovery is never worth losing the work
            new, rows = [], {}
        for k in new:
            text = str((rows.get(k) or {}).get("text") or "")
            discoveries.append({"material": mid, "name": doc.get("name"), "key": k,
                                "text": text})
            # 1 a property, as an assay pays (the owner, 2026-10-06). The forge pays its
            # first-property 3 for each key a step reveals; at 3 a key, one Dissolve of
            # brimstone in lamp oil paid 28 mastery (six keys learned) and took a new
            # alchemist past level 2 in a single step (measured on this bench).
            bonus(f"learned: {doc.get('name')}, {text}" if text
                  else f"learned: {doc.get('name')}", STUDY_MP)
    if yield_line:
        lines.append(yield_line)

    r = pend["roll"]
    tier_name = worldclass.quality_name(tier)
    what = ", ".join(f"{x['record'].get('count')} {x['record'].get('name')}" for x in landed)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{pc.name} works the alchemy bench ({plan.method}): {what}, {tier_name} "
        f"(d20 {r['face']}{r['bonus']:+d} = {r['total']} vs DC {r['dc']}).")})
    c.save()

    products = []
    for x in landed:
        rec = x["record"]
        st = (pc.stock or {}).get(x["key"])
        b = items.build(rec)
        products.append({"key": f"stock:{x['key']}", "name": getattr(st, "name", rec["name"]),
                         "count": int(rec.get("count") or 1), "record": rec, "build": b,
                         "waits": x["waits"], "ready_at": x["ready_at"],
                         "color": al.mix_color([(m, 1) for m in items.record_materials(rec)])})
    return JsonResponse({
        "tier": tier, "tier_name": tier_name, "score": score, "ceiling": plan.ceiling,
        "stopped": bool(body.get("stopped")),
        "products": products,
        "found": found,
        "mastery": {"lines": lines, "total": progress.mp, "level": progress.level,
                    "levelled": levelled},
        "discoveries": discoveries,
        "minutes": plan.minutes,
        "state": _state_body(c, pc),
    })


# --- assay -------------------------------------------------------------------------------------

@require_POST
def alchemy_assay(request):
    """Test a pinch of a reagent (plan §13.2): a tenth of a unit and ten minutes, the
    alchemist's own check against the study DC less what is already known of its kind
    (`knowledge.assay`, lane A). One benefit and one drawback revealed, and 1 mastery for
    each (the owner, 2026-10-06; 0 when nothing is new). Dangerous for real: a volatile
    reagent failed by 5 or more flares, and a toxic one handled unprotected hurts whatever
    the roll, through the engine (`alchemist.apply_rule`)."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    if c.scene.in_encounter:
        return _err("You are in a fight. The assay waits until it is over.", 409)
    body = read_body(request)
    mid = str(body.get("material") or "").strip().lower()
    doc = items.doc_of(mid)
    if doc is None:
        return _err("There is no such reagent.", 404)
    src = al.assay_source(pc, mid, _now(c))
    if src is None:
        return _err(f"You carry no {doc.get('name')} to take a pinch of.", 409)
    where = _where(c, pc)
    if not where.get("lab") and not where.get("kit"):
        return _err("You have no field kit with you, and there is no laboratory here.", 409)
    face, refused = _face(body)
    if refused:
        return refused
    track, progress = _progress(pc)
    terms = al.check_terms(pc, progress.level, lab=bool(where.get("lab")))
    bonus_v = sum(t["value"] for t in terms)
    engine = c.engine()
    if face is None:
        face = engine.dice.d20(label=f"Assay: {doc.get('name')}", visibility="player").faces[0]
    total = face + bonus_v
    now = _now(c)
    got = dict(knowledge.assay(pc, mid, total, clock=now) or {})
    tenths = int(round(float((got.get("cost") or {}).get("pinch", 0.1) or 0.1) * 10)) or 1
    pinch = al.take_pinch(pc, src, tenths)
    minutes = int(got.get("minutes", (al.method_row("assay") or {}).get("minutes", 10)))
    c.scene.advance(minutes)
    revealed = list(got.get("revealed") or [])
    rows = {r.get("key"): r for r in knowledge.properties(pc, doc)} if revealed else {}
    found, lines, levelled = [], [], []
    for k in revealed:
        text = str((rows.get(k) or {}).get("text") or "")
        found.append({"key": k, "text": text, "row": rows.get(k)})
    if found:
        res = worldclass.award_bonus(track, progress, mp=STUDY_MP * len(found),
                                     why=f"assayed {doc.get('name')}: {len(found)} "
                                         f"propert{'y' if len(found) == 1 else 'ies'} learned")
        lines.extend(res.get("reasons") or [])
        levelled.extend(res.get("levelled") or [])
    dangers = al.assay_dangers(src, total, int(got.get("dc") or 0),
                               protected_by=str(where.get("protected") or ""))
    applied = []
    for d_mid, d_name, spec, kind in dangers:
        applied += _outcome_rows(al.apply_rule(engine, pc, [(d_mid, d_name, spec)],
                                               kind=kind))
    said = (f"{pc.name} assays {doc.get('name')} (d20 {face}{bonus_v:+d} = {total}): "
            + (", ".join(f["text"] or f["key"] for f in found) if found else "nothing new."))
    c.transcript.append({"who": "gm", "kind": "consequence", "text": said})
    c.save()
    return JsonResponse({
        "material": mid, "name": doc.get("name"),
        "roll": {"face": face, "bonus": bonus_v, "total": total, "terms": terms,
                 "dc": got.get("dc"), "success": got.get("success")},
        "dc": got.get("dc"), "success": got.get("success"),
        "revealed": found, "pinch": pinch, "minutes": minutes,
        "dangers": [{"kind": k, "text": effectspec.render(s)} for _m, _n, s, k in dangers],
        "danger_applied": applied,
        "flare": any(k == "mishap" for *_x, k in dangers),
        "mastery": {"lines": lines, "total": progress.mp, "level": progress.level,
                    "levelled": levelled},
        "clock": _clock(c),
        "shelf": _shelf(c, pc),
    })


# --- identify a potion -------------------------------------------------------------------------

@require_POST
def alchemy_identify(request):
    """Identify a potion held for a round (plan §11.3; lane A's `knowledge.identify_potion`):
    the alchemist's check against DC 15 + the potion's spell level. It reveals what the
    potion IS; it never teaches the formula (that is Learn's potion route)."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    face, refused = _face(body)
    if refused:
        return refused
    key = str(body.get("item") or "")
    sid = key.split(":", 1)[1] if key.startswith("stock:") else key
    st = (pc.stock or {}).get(sid)
    if st is None:
        return _err("That is not in your pack.", 404)
    track, progress = _progress(pc)
    terms = al.check_terms(pc, progress.level)
    bonus_v = sum(t["value"] for t in terms)
    if face is None:
        face = c.engine().dice.d20(label=f"Identify: {st.name}", visibility="player").faces[0]
    total = face + bonus_v
    got = dict(knowledge.identify_potion(pc, st, total, clock=_now(c)) or {})
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{pc.name} turns the {st.name} in the light (d20 {face}{bonus_v:+d} = {total} vs "
        f"DC {got.get('dc')}): " + ("it is what it is." if got.get("success")
                                    else "it gives up nothing."))})
    c.save()
    return JsonResponse(dict(got, item=key, terms=terms, face=face, bonus=bonus_v))


# --- learn a formula ---------------------------------------------------------------------------

def _stock_of(pc, key: str):
    sid = key.split(":", 1)[1] if key.startswith("stock:") else key
    return sid, (pc.stock or {}).get(sid)


def alchemists_here(c, pc) -> list[dict]:
    """Everybody here who knows reagents (an alchemist by trade, or by their own words:
    `knowledge.teaches` with the alchemist's rows). Named, never reffed on the page."""
    from rules import population

    try:
        price = _coins(int(knowledge.lore(knowledge.ALCHEMIST)["teacher"]["price_cp"]))
    except Exception:      # noqa: BLE001
        price = ""
    out = []
    for ref, a in (getattr(c.scene, "actors", None) or {}).items():
        if a is pc or getattr(a, "is_pc", False) or getattr(a, "is_down", False):
            continue
        try:
            if knowledge.teaches(a, population.of_ref(c.scene, ref), knowledge.ALCHEMIST):
                out.append({"ref": ref, "name": a.name, "price": price})
        except Exception:      # noqa: BLE001
            continue
    return out


def _companion_knows(c, pc, ref: str, spell_id: str) -> str:
    """"" when the companion `ref` stands here, is on the alchemist's side and knows the
    spell; else why not, in words."""
    from rules import casting, spells

    a = (getattr(c.scene, "actors", None) or {}).get(ref)
    if a is None or a is pc:
        return "Nobody by that name is here to teach you."
    if not getattr(a, "is_companion", False) and getattr(a, "side", "") != getattr(pc, "side", ""):
        return f"{a.name} is no companion of yours."
    try:
        if casting.knows(a, spells.get(spell_id)):
            return ""
    except Exception:      # noqa: BLE001
        pass
    return f"{a.name} does not know that spell."


@require_POST
def alchemy_learn(request):
    """Learn a formula (plan §10.4; lane E's `learn_route` / `resolve_learn`):
    `{from: scroll | spellbook | potion | teacher | companion | formulary, fid?, item?, who?,
    face?}`. A scroll or a spellbook is copied at DC 15 + spell level for the book's writing
    cost; a potion in hand is taken apart (DC 15 + spell level, spent whatever the roll:
    the owner's open point 9); a teacher charges a lesson; a companion who knows the spell
    teaches it free. The check is the alchemist's; no naturals."""
    from rules import goods

    c, pc, refused = _ready(request)
    if refused:
        return refused
    if c.scene.in_encounter:
        return _err("You are in a fight. The formulary waits until it is over.", 409)
    body = read_body(request)
    source = str(body.get("from") or "").strip().lower()
    fid = str(body.get("fid") or "").strip().lower()
    item_key = str(body.get("item") or "")
    sid, st = _stock_of(pc, item_key) if item_key else ("", None)
    now = _now(c)
    teacher = None
    fee_cp = 0
    if source == "potion":
        if st is None or not getattr(st, "holds_spell", None):
            return _err("Hold a potion that holds a spell to take it apart.", 409)
        fid = formulae.potion_formula(st) or ""
    elif source == "scroll":
        if st is None or not getattr(st, "holds_spell", None) or "drink" in (st.how or []):
            return _err("Hold a scroll to copy from.", 409)
        fid = (formulae.for_spell(st.holds_spell) or {}).get("id", "")
    elif source == "spellbook":
        row = formulae.get(fid) or {}
        from rules import casting, spells

        try:
            ok = bool(row.get("spell")) and casting.knows(pc, spells.get(row["spell"]))
        except Exception:      # noqa: BLE001
            ok = False
        if not ok:
            return _err("Your spellbook does not hold that spell.", 409)
    elif source == "teacher":
        ref = str(body.get("who") or "")
        if not any(t["ref"] == ref for t in alchemists_here(c, pc)):
            return _err("Nobody here by that name knows the trade.", 409)
        teacher = c.scene.actors[ref]
        if not knowledge.lesson_size(teacher, knowledge.ALCHEMIST):
            return _err(f"{teacher.name} will not teach you.", 409)
        lesson = knowledge.lore(knowledge.ALCHEMIST).get("formula_lesson") or {}
        n = int((formulae.get(fid) or {}).get("spell_level") or 0)
        fee_cp = max(int(lesson.get("price_cp", 500)),
                     int(lesson.get("per_spell_level_cp", 500)) * n)
    elif source == "companion":
        row = formulae.get(fid) or {}
        why = _companion_knows(c, pc, str(body.get("who") or ""), str(row.get("spell") or ""))
        if why:
            return _err(why, 409)
    elif source == "formulary":
        # Lane H's formularies (content/rules/alchemy-manuals.json): a book's `formulae`
        # names the formula ids it writes down. `knowledge.manual_keys` reads only a
        # manual's `teaches` (reagent properties), so the formulae are read here. Any
        # carried formulary that writes it serves; `item` may name one by its id.
        want = str(body.get("item") or "").strip().lower()
        books = [m for mid_, m in knowledge.manuals(knowledge.ALCHEMIST).items()
                 if fid in set(m.get("formulae") or ()) and (not want or mid_ == want)
                 and knowledge.holds_manual(pc, m)]
        if not books:
            return _err("No formulary you carry writes that formula down.", 409)
        sid, st = "", None                  # a formulary is never spent
    if not fid or formulae.get(fid) is None:
        return _err("There is no such formula.", 404)
    plan = formulae.learn_route(pc, fid, source, clock=now)
    if plan["refused"]:
        return _err(" ".join(plan["refused"]), 409)
    cost_cp = int(round(float(plan.get("cost_gp") or 0) * 100)) + fee_cp
    if cost_cp:
        purse, ok = goods.spend(pc.purse, cost_cp)
        if not ok:
            return _err(f"It costs {_coins(cost_cp)}, and you cannot pay it.", 409)
        pc.purse = purse
        if teacher is not None:
            teacher.purse = goods.credit(getattr(teacher, "purse", None) or {}, fee_cp)
    total = None
    face = None
    track, progress = _progress(pc)
    terms = al.check_terms(pc, progress.level)
    if plan["check"]:
        face, refused = _face(body)
        if refused:
            return refused
        if face is None:
            face = c.engine().dice.d20(label="Alchemy: learn a formula",
                                       visibility="player").faces[0]
        total = face + sum(t["value"] for t in terms)
    got = formulae.resolve_learn(pc, fid, source, total, clock=now)
    if got.get("spent") and sid and st is not None:
        pc.take_stock(sid, 1)
    minutes = int(plan.get("minutes") or 60)
    c.scene.advance(minutes)
    lines: list[dict] = []
    if got.get("learned"):
        row = formulae.get(fid) or {}
        res = worldclass.award_bonus(track, progress, mp=worldclass.FIRST_MP,
                                     why=f"first formula written: {row.get('name', fid)}")
        lines.extend(res.get("reasons") or [])
    name = (formulae.get(fid) or {}).get("name", fid)
    said = (f"{pc.name} learns the formula for {name}." if got.get("learned")
            else f"{pc.name} cannot make out the formula for {name}.")
    c.transcript.append({"who": "gm", "kind": "consequence", "text": said})
    c.save()
    return JsonResponse({"fid": fid, "name": name, "route": plan, "result": got,
                         "face": face, "terms": terms if plan["check"] else [],
                         "total": total, "paid": _coins(cost_cp) if cost_cp else "",
                         "minutes": minutes, "said": said,
                         "formula": _formula_row(pc, fid, progress.level),
                         "mastery": {"lines": lines, "total": progress.mp,
                                     "level": progress.level},
                         "clock": _clock(c)})


# --- ask an alchemist ----------------------------------------------------------------------------

@require_POST
def alchemy_ask(request):
    """Show a reagent to an alchemist and pay them to tell you about it (UI plan §6.8, "Ask
    an alchemist"), the forge's `forge_ask` with the alchemist's rows: their regard decides
    how much; below indifferent they refuse in words. Dangers first."""
    from rules import attitude, goods

    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    mid = str(body.get("material") or "").strip().lower()
    doc = items.doc_of(mid)
    if doc is None:
        return _err("There is no such reagent.", 404)
    ref = str(body.get("ref") or "")
    if not any(t["ref"] == ref for t in alchemists_here(c, pc)):
        return _err("Nobody here by that name knows the trade.", 400)
    person = c.scene.actors[ref]
    who = person.name[:1].upper() + person.name[1:]
    rules = knowledge.lore(knowledge.ALCHEMIST)["teacher"]
    size = knowledge.lesson_size(person, knowledge.ALCHEMIST)
    if not size:
        hostile = attitude.of(person) == attitude.HOSTILE
        said = (f"{who} wants nothing to do with you." if hostile else
                f"{who} keeps what they know of {doc.get('name')} to themselves.")
        c.transcript.append({"who": "gm", "kind": "consequence", "text": said})
        c.save()
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0, "refused": said})
    order = knowledge.lesson_order(pc, doc)[:size]
    if not order:
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0,
                             "refused": f"{who} has nothing to tell you about "
                                        f"{doc.get('name')} you do not know."})
    cp = int(rules["price_cp"])
    purse, ok = goods.spend(pc.purse, cp)
    if not ok:
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0,
                             "refused": f"{who} asks {_coins(cp)}, and you cannot pay it."})
    pc.purse = purse
    person.purse = goods.credit(getattr(person, "purse", None) or {}, cp)
    minutes = int(rules["minutes"])
    c.scene.advance(minutes)
    keys = knowledge.reveal(pc, mid, knowledge.with_gates(doc, order),
                            f"taught by {person.name}, day "
                            f"{knowledge.day_of(c.scene.clock_minutes)}")
    rows = {r.get("key"): r for r in knowledge.properties(pc, doc)}
    revealed = [{"key": k, "text": str((rows.get(k) or {}).get("text") or "")} for k in keys]
    track, progress = _progress(pc)
    lines = []
    for f in revealed:
        res = worldclass.award_bonus(track, progress, mp=STUDY_MP,
                                     why=f"learned: {doc.get('name')}, {f['text']}")
        lines.extend(res.get("reasons") or [])
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{who} looks over the {doc.get('name')} and tells you: "
        + "; ".join(f["text"] or f["key"] for f in revealed) + f". ({_coins(cp)} paid.)")})
    c.save()
    return JsonResponse({"revealed": revealed, "paid": _coins(cp), "minutes": minutes,
                         "refused": "", "clock": _clock(c),
                         "mastery": {"lines": lines, "total": progress.mp,
                                     "level": progress.level}})


# --- collect, perks ------------------------------------------------------------------------------

@require_POST
def alchemy_collect(request):
    """Take finished alchemy work out of In progress (the shared section's own collect,
    rules/inprogress.py; the same as api/works/collect, here so the bench need not leave
    its own routes). A Transmute's output lands in the satchel."""
    from rules import inprogress

    c, pc, refused = _ready(request)
    if refused:
        return refused
    key = str(read_body(request).get("key") or "")
    if not key:
        return _err("Say which work to collect (`key`).")
    got = inprogress.collect(pc, key, now=_now(c), here=getattr(pc, "at", None) or None)
    if not got.get("ok"):
        return _err(str(got.get("why") or "It cannot be collected."), 409)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": got["said"]})
    c.save()
    return JsonResponse({"said": got["said"], "product": got.get("product"),
                         "works": _works(c, pc), "shelf": _shelf(c, pc)})


@require_POST
def alchemy_perks(request):
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


# --- recipes ----------------------------------------------------------------------------------

def _alchemical(r: dict) -> bool:
    return str(r.get("craft") or "") == TRACK_ID


def _recipes(c) -> list[dict]:
    """The alchemist's saved recipes (plan §15.3): steps of {method, inputs, solvent,
    vessel, catalysts, formula} by material id. Loading one sets the bench up; you still
    roll and still play. Old chain recipes (`craft: "alchemy"`) are dropped by the
    migration (lane I); until then they are listed flagged, never run."""
    out = []
    for r in getattr(c, "recipes", None) or []:
        if _alchemical(r):
            out.append({"id": str(r.get("id")), "name": str(r.get("name") or ""),
                        "steps": list(r.get("steps") or []), "flag": ""})
        elif str(r.get("craft") or "") == "alchemy":
            out.append({"id": f"old-{items._slug(r.get('name') or 'recipe')}",
                        "name": str(r.get("name") or ""), "steps": [],
                        "flag": "made for the old chain bench; it no longer runs"})
    return out


_STEP_KEYS = ("inputs", "solvent", "vessel", "catalysts", "formula", "as", "picks", "target")


@require_POST
def alchemy_recipe(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    if "delete" in body:
        rid = str(body.get("delete") or "")
        if not any(r["id"] == rid for r in _recipes(c) if not r["flag"]):
            return _err("There is no such recipe.", 409)
        c.recipes = [r for r in c.recipes if not (_alchemical(r) and str(r.get("id")) == rid)]
        c.save()
        return JsonResponse({"recipes": _recipes(c)})
    if "load" in body:
        rid = str(body.get("load") or "")
        found = next((r for r in _recipes(c) if r["id"] == rid and not r["flag"]), None)
        if found is None:
            return _err("There is no such recipe.", 409)
        return JsonResponse({"recipe": found})
    name = str(body.get("name") or "").strip()
    if not name:
        return _err("A recipe needs a name.")
    steps = []
    for i, s in enumerate(body.get("steps") or [], 1):
        if not isinstance(s, dict) or str(s.get("method") or "") not in al.METHODS:
            return _err(f"Step {i}: name a method ({', '.join(al.METHODS)}).")
        steps.append({"method": str(s["method"]),
                      **{k: s[k] for k in _STEP_KEYS if k in s}})
    if not steps:
        return _err("A recipe needs at least one step.")
    kept = [r for r in c.recipes
            if not (_alchemical(r) and str(r.get("name", "")).lower() == name.lower())]
    taken = {str(r.get("id")) for r in kept if r.get("id")}
    n = 1
    while f"a{n}" in taken:
        n += 1
    kept.append({"id": f"a{n}", "name": name, "craft": TRACK_ID, "steps": steps})
    c.recipes = kept
    c.save()
    return JsonResponse({"recipes": _recipes(c)})


# --- the books ---------------------------------------------------------------------------------

@require_GET
def alchemy_formulary(request):
    """The formula book (UI plan §6.7): every known formula with its requirement, how it
    was learned and what still keeps it out of reach; and the writings carried — every
    potion or scroll that teaches a formula, with what learning it would ask."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    _t, progress = _progress(pc)
    known = [r for r in (_formula_row(pc, f, progress.level) for f in formulae.known(pc)) if r]
    writings = []
    for sid, st in sorted((pc.stock or {}).items()):
        if not getattr(st, "holds_spell", None) or int(st.count or 0) <= 0:
            continue
        route = "potion" if "drink" in (st.how or []) or getattr(st, "craft", "") == TRACK_ID \
            else "scroll"
        fid = formulae.potion_formula(st) if route == "potion" else \
            (formulae.for_spell(st.holds_spell) or {}).get("id")
        if not fid:
            continue
        writings.append({"item": f"stock:{sid}", "name": st.name, "route": route,
                         "fid": fid, "formula": (formulae.get(fid) or {}).get("name"),
                         "plan": formulae.learn_route(pc, fid, route, clock=_now(c))})
    for mid_, m in sorted(knowledge.manuals(knowledge.ALCHEMIST).items()):
        if not m.get("formulae") or not knowledge.holds_manual(pc, m):
            continue
        for fid in m.get("formulae") or ():
            if formulae.get(fid) is None or formulae.knows(pc, fid):
                continue
            writings.append({"item": mid_, "name": m.get("name"), "route": "formulary",
                             "fid": fid, "formula": (formulae.get(fid) or {}).get("name"),
                             "plan": formulae.learn_route(pc, fid, "formulary",
                                                          clock=_now(c))})
    return JsonResponse({"formulae": known, "writings": writings,
                         "teachers": alchemists_here(c, pc),
                         "spell_level_cap": formulae.spell_level_cap(progress.level)})


@require_GET
def alchemy_codex(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    return JsonResponse({"codex": knowledge.alchemy_codex(pc)})


@require_GET
def alchemy_material(request, material_id: str):
    """One reagent's card (UI plan §6.8): what is known of it, in the bottle and at the
    bench; one "unknown" per unknown; where it is found; the assay's DC and cost; and, at
    Alchemist 3, what it could be transmuted into."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    doc = items.doc_of(str(material_id))
    if doc is None:
        return _err("There is no such reagent.", 404)
    _t, progress = _progress(pc)
    props = knowledge.properties(pc, doc)
    for p in props:
        p["where"] = "in the bottle" if str(p["key"]).startswith("p") else "at the bench"
    carried = sum(it.amount for it in al.shelf(pc, _now(c)) if it.material == doc["id"])
    card = {"id": doc["id"], "name": doc.get("name"), "kind": doc.get("kind"),
            "tier": doc.get("tier"), "color": doc.get("color"), "text": doc.get("text"),
            "obtain": doc.get("obtain"), "biomes": list(doc.get("biomes") or []),
            "price_gp": doc.get("price_gp"), "hybrid": bool(doc.get("hybrid")),
            "properties": props,
            "unknown": sum(1 for p in props if not p["known"]),
            "danger_known": knowledge.danger_known(pc, doc),
            "carried": round(carried, 1),
            "assay": {"dc": knowledge.assay_dc(doc, pc), "minutes":
                      int((al.method_row("assay") or {}).get("minutes", 10)),
                      "cost": "a tenth of one you carry"},
            "teachers": alchemists_here(c, pc)}
    if progress.level >= al.method_level("transmute"):
        card["transmutes"] = al.transmute_candidates(doc["id"], progress.level)
    return JsonResponse(card)
