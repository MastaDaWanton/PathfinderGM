"""The herbalism bench's API (docs/herbalism-contracts.md §3).

The page sends what the player chose — a method, what is on the tool, a batch size, the
face of their own d20, the minigame's 0..1 score — and the server answers with every
number: the DC, the odds, the tier, the product, the mastery, the time. The page never
names a tier or computes an effect (UI plan §12), which is the bench's version of "no
model authors a number": the player supplies the skill, the engine does the arithmetic.

One step is three requests:

  check   what would happen, and why each satchel item fits or does not;
  roll    the d20 (the player's own face, or the server's), the time, and on a miss the
          book's failure rule at once; on a success the materials are set aside behind a
          token;
  finish  the minigame's score becomes a tier under the crafter's ceiling, the product
          lands, the materials are spent, mastery and discoveries are paid.

Nothing is spent between roll and finish. The token holds a reservation in this process's
memory; a reload, a crash or a second roll lets it go and the materials were never taken,
so a lost craft returns its reservation rather than eating it (contracts brief). The time
the roll took has passed either way, because it did.
"""
from __future__ import annotations

import re
import secrets

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from rules import crafting, herbknowledge, ingredients, worldclass

from . import campaign as campaign_mod
from .apiutil import read_body, read_int

TRACK_ID = "herbalist"
MAX_BATCH = 1000

# Pending crafts, by campaign id: {"token", "plan", "roll", "recipe", "step"}. One per
# campaign; a new roll replaces it, and a fresh GET of the bench's state lets it go (the
# page has just opened, so any craft in flight was abandoned). Module memory on purpose:
# a reservation that outlived the process would be one nobody can finish.
_PENDING: dict[str, dict] = {}


def _err(text: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": text}, status=status)


# --- the progression lane's functions ------------------------------------------------------
#
# Lane B1's, in rules/worldclass.py: the track object, perk picks, what the perks
# multiply, and the step award. Called straight through; the only adjustment is the
# yield chance's unit.

def perk_multipliers(progress) -> dict:
    got = dict(worldclass.perk_multipliers(progress))
    chance = float(got.get("yield_chance", 0) or 0)
    # A fraction is the contract; a percentage would read as a certainty, so it is
    # brought back to one rather than trusted.
    got["yield_chance"] = chance / 100 if chance > 1 else chance
    return got


FIRST_MP = worldclass.FIRST_MP


# --- reading the campaign ---------------------------------------------------------------

def _clock(c) -> dict:
    minute = int(c.scene.clock_minutes or 0)
    hour, mins = (minute % 1440) // 60, minute % 60
    twelve = hour % 12 or 12
    return {"minute": minute, "day": minute // 1440 + 1,
            "label": f"Day {minute // 1440 + 1}, {twelve}:{mins:02d}"
                     f"{'am' if hour < 12 else 'pm'}"}


def _ground(c) -> dict:
    """Where the kit is unfolded (UI plan §6.3): the scene's biome, whether there is a
    roof, and the clock for the light. A label is never worth failing a request for."""
    from rules import places

    roofed, place = False, ""
    try:
        here = c.engine().here()
        roofed = bool(places.is_indoors(here.id, shape=getattr(here, "shape", None)))
        place = str(getattr(here, "name", "") or "")
    except Exception:      # noqa: BLE001
        pass
    if not place:
        try:
            from .views import _where_state

            place = _where_state(c).get("where_label", "")
        except Exception:      # noqa: BLE001
            place = ""
    return {"biome": c.biome, "roofed": roofed,
            "minute": int(c.scene.clock_minutes or 0), "place": place}


def _progress(pc):
    return worldclass.get(TRACK_ID), pc.track(TRACK_ID)


def _reserved(c) -> dict:
    pend = _PENDING.get(c.id)
    if not pend:
        return {}
    out: dict[str, int] = {}
    for m, n in pend["plan"].consumes:
        out[m.key] = out.get(m.key, 0) + int(n)
    return out


def _satchel(c, pc, reserved=True) -> list:
    return crafting.satchel(pc, int(c.scene.clock_minutes or 0),
                            _reserved(c) if reserved else None)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-") or "recipe"


def _herbal(r: dict) -> bool:
    return str(r.get("craft", "herbalism")) in ("herbalism", "herbalist")


def _recipe_id(r: dict) -> str:
    """A saved step recipe's own id, or a stable one for an old chain recipe, which never
    had one: its name, which the old bench already kept unique."""
    return str(r.get("id") or f"old-{_slug(r.get('name'))}")


def _recipes(c) -> list[dict]:
    """The herbalism recipes, in the step shape (contracts §3.6).

    Recipes saved by the old chain bench (`methods` + `ingredients`) are converted on
    read, never rewritten: the first step takes the ingredients and each later step works
    what the one before made. One that names a retired method is kept and flagged with the
    step that no longer exists (plan §14.3).
    """
    out = []
    for r in c.recipes or []:
        if not _herbal(r):
            continue
        rid = _recipe_id(r)
        if "steps" in r:
            steps = list(r.get("steps") or [])
        else:
            counted: dict[str, int] = {}
            for iid in r.get("ingredients") or []:
                counted[str(iid)] = counted.get(str(iid), 0) + 1
            steps = [{"method": str(m), "items": ([{"ingredient_id": k, "count": n}
                                                   for k, n in counted.items()]
                                                  if i == 0 else [])}
                     for i, m in enumerate(r.get("methods") or [])]
        gone = [s.get("method") for s in steps
                if crafting.method_row(str(s.get("method", ""))) is None]
        flag = ""
        if gone:
            flag = (f"needs a new method: {', '.join(str(g).title() for g in gone)} "
                    f"no longer {'exists' if len(gone) == 1 else 'exist'}")
        out.append({"id": rid, "name": str(r.get("name", "")), "steps": steps,
                    "flag": flag})
    return out


def _state_body(c, pc) -> dict:
    track, progress = _progress(pc)
    now = int(c.scene.clock_minutes or 0)
    return {
        "track": worldclass.track_summary(track, progress),
        "methods": crafting.methods_view(progress.level),
        "satchel": [m.as_item(pc, now) for m in _satchel(c, pc)],
        "ground": _ground(c),
        "recipes": _recipes(c),
        "clock": _clock(c),
    }


def _ready(request):
    """The campaign and its character, or the refusal. Steeping jars whose day has come
    are settled first, so every answer reads the shelf as it now is."""
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return None, None, _err("There is no character to work the bench.", 409)
    crafting.settle_steeping(pc, int(c.scene.clock_minutes or 0))
    return c, pc, None


def _plan_from(c, pc, body) -> tuple[object, list, JsonResponse | None]:
    """The step the body describes, against the satchel as it stands (less anything set
    aside by a craft in flight)."""
    method = str(body.get("method") or "").strip().lower()
    if not method:
        return None, [], _err("Choose a method first.")
    raw = body.get("items", [])
    if not isinstance(raw, list):
        return None, [], _err("`items` must be a list of {key, count}.")
    items = _satchel(c, pc)
    by_key = {m.key: m for m in items}
    picks = []
    for entry in raw:
        if not isinstance(entry, dict):
            return None, [], _err("Each item must be {key, count}.")
        key = str(entry.get("key") or "")
        if key not in by_key:
            return None, [], _err("Something on the bench is no longer in your satchel. "
                                  "Take it off and look again.", 409)
        count = read_int(entry, "count", 1, lo=0, hi=MAX_BATCH * 2)
        if any(p.key == key for p, _ in picks):
            return None, [], _err(f"{by_key[key].name} is on the bench twice.")
        picks.append((by_key[key], count))
    batch = read_int(body, "batch", 1, lo=1, hi=MAX_BATCH)
    track, progress = _progress(pc)
    plan = crafting.plan_step(pc, progress, method, picks, batch,
                              perks=perk_multipliers(progress))
    return plan, items, None


def _check_body(plan, items, pc, level) -> dict:
    return {
        "fits": crafting.fits_for(plan.method, items, plan.picks, level),
        "problems": list(plan.problems),
        "can_roll": plan.can_roll,
        "minutes": plan.minutes, "doses": plan.doses, "batch": plan.batch,
        "dc": plan.dc, "bonus": plan.bonus, "terms": plan.terms,
        "need": plan.need, "impossible": plan.impossible,
        # How many batch units what is on the tool allows, for the batch stepper's "all"
        # button (UI plan §6.5): the old bench learned that a player made to count it out
        # finds out they were three short halfway through.
        "batch_max": min((m.count // n for m, n in plan.picks if n > 0), default=0),
        "product": crafting.product_card(plan, pc) if plan.form or plan.state else None,
    }


# --- §3.1 ---------------------------------------------------------------------------------

@require_GET
def bench_state(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    # Opening the bench abandons any craft still in flight: its reservation goes back
    # on the shelf (nothing was spent), so a reload never strands materials.
    _PENDING.pop(c.id, None)
    # The discovery lane's one hook: a herbalist's homeland knowledge (plan §8.1, Q4) is
    # seeded the first time the bench opens, and saved so it is seeded once.
    if herbknowledge.ensure_seeded(pc, world=c.world, scene=c.scene):
        c.save()
    return JsonResponse(_state_body(c, pc))


# --- §3.2 ---------------------------------------------------------------------------------

@require_POST
def bench_check(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    plan, items, refused = _plan_from(c, pc, read_body(request))
    if refused:
        return refused
    return JsonResponse(_check_body(plan, items, pc, pc.track(TRACK_ID).level))


# --- §3.3 ---------------------------------------------------------------------------------

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


@require_POST
def bench_roll(request):
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
    # A new roll replaces any craft still in flight, and its reservation goes back.
    _PENDING.pop(c.id, None)
    plan, _items, refused = _plan_from(c, pc, body)
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
    if face is None:
        face = engine.dice.d20(label=f"Herbalism: {plan.name}",
                               visibility="player").faces[0]
    total = face + plan.bonus
    margin = total - plan.dc
    # A skill check: no natural 20 or natural 1 (CRB p.180; `crafting.check_odds`).
    success = margin >= 0
    track, progress = _progress(pc)

    c.scene.advance(plan.minutes)
    roll = {"face": face, "bonus": plan.bonus, "total": total, "dc": plan.dc,
            "success": success, "margin": margin, "terms": plan.terms}
    out = {"roll": roll,
           "verdict": {"verdict": "success" if success else "failure", "natural": face,
                       "word": "Success" if success else "Failure"},
           "lost": [], "minutes": plan.minutes}
    if success:
        token = secrets.token_urlsafe(16)
        recipe = str(body.get("recipe") or "") or None
        step = body.get("step")
        _PENDING[c.id] = {"token": token, "plan": plan, "roll": roll,
                          "recipe": recipe,
                          "step": int(step) if isinstance(step, int) else None}
        out["token"] = token
        out["tuning"] = crafting.tuning_for(plan)
        line = (f"{pc.name} works {plan.name} at the bench "
                f"(d20 {face}{plan.bonus:+d} = {total} vs DC {plan.dc}).")
    else:
        miss = -margin
        losses = crafting.failure_losses(plan, miss)
        out["lost"] = crafting.spend(pc, losses)
        if out["lost"]:
            ruined = ", ".join(f"{x['count']} {x['name']}" for x in out["lost"])
            said = f"Missed by {miss}. Half the materials are ruined: {ruined}."
        else:
            said = f"Missed by {miss}. The time is lost; the materials are kept."
        out["said"] = said
        lead = plan.lead
        got = worldclass.award_step(track, progress, method=plan.method,
                         ingredient_id=lead.ingredient_id if lead else "",
                         rarity_rank=plan.rank_in, quality_index=0, success=False,
                         name=crafting._lead_name(lead) if lead else "")
        out["mastery"] = {"lines": list(got.get("reasons") or []),
                          "total": got.get("total", progress.mp),
                          "level": got.get("level", progress.level),
                          "levelled": list(got.get("levelled") or [])}
        line = (f"{plan.name}: spoiled (d20 {face}{plan.bonus:+d} = {total} vs DC "
                f"{plan.dc}). {said}")
    out["clock"] = _clock(c)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": line})
    c.save()
    return JsonResponse(out)


# --- §3.4 ---------------------------------------------------------------------------------

def _first(progress, key: str) -> bool:
    """Whether this is the first time, recorded in the track's own ledger so it survives
    a save. Keys are `form:<form>` and `herb:<id>`, apart from the (method, ingredient)
    keys the step award uses."""
    seen = int(progress.crafted.get(key, 0))
    progress.crafted[key] = seen + 1
    return seen == 0


@require_POST
def bench_finish(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    pend = _PENDING.get(c.id)
    token = str(body.get("token") or "")
    if not pend or not token or not secrets.compare_digest(pend["token"], token):
        return _err("That craft is no longer waiting to be finished. Roll again.", 409)
    plan = pend["plan"]
    track, progress = _progress(pc)

    # Everything that can refuse refuses before anything changes, so a refusal leaves
    # the campaign exactly as it was (tests/test_a_save_is_never_half_written.py: one
    # save at the end, and nothing half-applied in memory before it).
    fresh = {m.key: m for m in _satchel(c, pc, reserved=False)}
    for m, n in plan.consumes:
        have = fresh.get(m.key)
        if have is None or have.count < n:
            _PENDING.pop(c.id, None)
            return _err(f"The {m.name} set aside for this craft is gone. Nothing was "
                        f"made.", 409)

    ceiling = worldclass.ceiling_index(progress)
    tier, score = crafting.tier_from_score(body.get("score"), ceiling)
    now = int(c.scene.clock_minutes or 0)
    made = crafting.make(plan, tier, now)

    # The extra-yield perk: the one random reward, so its roll is shown (plan §3).
    perks = perk_multipliers(progress)
    chance = float(perks.get("yield_chance", 0) or 0)
    extra, yield_line = 0, None
    engine = c.engine()
    if chance > 0:
        roll = engine.dice.roll("1d100", label="Yield perk", visibility="player")
        need = int(round(chance * 100))
        extra = 1 if roll.total <= need else 0
        yield_line = {"why": f"Yield perk: d100 {roll.total} against {need} or less, "
                             f"{'one more dose' if extra else 'no extra dose'}", "mp": 0}

    _PENDING.pop(c.id, None)
    crafting.spend(pc, [(fresh[m.key], n) for m, n in plan.consumes])
    count = int(made.count) + extra
    pc.add_stock(made, count)

    # Mastery: the step, the quality bonus (inside the step award), then firsts.
    lines: list[dict] = []
    levelled: list[int] = []
    lead = plan.lead
    got = worldclass.award_step(track, progress, method=plan.method,
                     ingredient_id=lead.ingredient_id if lead else "",
                     rarity_rank=plan.rank_in, quality_index=tier, success=True,
                     name=crafting._lead_name(lead) if lead else "")
    lines += list(got.get("reasons") or [])
    levelled += list(got.get("levelled") or [])

    def bonus(why: str) -> None:
        res = worldclass.award_bonus(track, progress, why=why, mp=FIRST_MP)
        lines.extend(res.get("reasons") or [])
        levelled.extend(res.get("levelled") or [])

    form_name = crafting.product_row(plan.form).get("name", plan.form or "")
    if plan.form and _first(progress, f"form:{plan.form}"):
        bonus(f"first {form_name.lower()}")
    for m, _ in plan.picks:
        if m.reagent or not m.ingredient_id:
            continue
        if _first(progress, f"herb:{m.ingredient_id}"):
            bonus(f"first work with {crafting._lead_name(m)}")

    discoveries = []
    how = f"made it, day {now // 1440 + 1}"
    for iid, keys in crafting.revealed_keys(made).items():
        new = herbknowledge.reveal(pc, iid, keys, how)
        try:
            ing = ingredients.get(iid)
        except KeyError:
            continue
        pairs = ing.pairs
        for k in new:
            idx = int(k[1:]) if k[1:].isdigit() else -1
            text = pairs[idx][0] if 0 <= idx < len(pairs) else ""
            discoveries.append({"ingredient_id": iid, "name": ing.name, "key": k,
                                "text": text})
            bonus(f"learned: {ing.name}, {text}" if text else f"learned: {ing.name}")
    if yield_line:
        lines.append(yield_line)

    nxt = None
    if pend.get("recipe") and pend.get("step") is not None:
        recipe = next((r for r in _recipes(c) if r["id"] == pend["recipe"]), None)
        if recipe and pend["step"] + 1 < len(recipe["steps"]):
            nxt = {"method": recipe["steps"][pend["step"] + 1].get("method"),
                   "recipe": recipe["id"], "step": pend["step"] + 1}

    tier_name = crafting.quality_name(tier)
    r = pend["roll"]
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{pc.name} makes {count} {made.name}, {tier_name} "
        f"(d20 {r['face']}{r['bonus']:+d} = {r['total']} vs DC {r['dc']}).")})
    c.save()

    item_key = f"stock:{made.id}"
    item = next((m.as_item(pc, now) for m in _satchel(c, pc) if m.key == item_key), None)
    return JsonResponse({
        "tier": tier, "tier_name": tier_name, "score": score, "ceiling": ceiling,
        "stopped": bool(body.get("stopped")),
        "made": item, "count": count,
        "mastery": {"lines": lines, "total": progress.mp, "level": progress.level,
                    "levelled": levelled},
        "discoveries": discoveries,
        "next": nxt,
        "state": _state_body(c, pc),
    })


# --- §3.5 ---------------------------------------------------------------------------------

@require_POST
def bench_perks(request):
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
    return JsonResponse(worldclass.track_summary(track, progress))


# --- §3.6 ---------------------------------------------------------------------------------

def _clean_steps(raw) -> tuple[list[dict], str]:
    if not isinstance(raw, list) or not raw:
        return [], "A recipe needs at least one step."
    steps = []
    for i, s in enumerate(raw, 1):
        if not isinstance(s, dict):
            return [], f"Step {i} is not a step."
        method = str(s.get("method") or "").strip().lower()
        if crafting.method_row(method) is None:
            return [], f"Step {i}: there is no method called {method!r}."
        items = []
        for it in s.get("items") or []:
            if not isinstance(it, dict) or not str(it.get("ingredient_id") or "").strip():
                return [], f"Step {i}: each item needs an ingredient_id."
            items.append({"ingredient_id": str(it["ingredient_id"]).strip().lower(),
                          "count": read_int(it, "count", 1, lo=1, hi=MAX_BATCH)})
        steps.append({"method": method, "items": items})
    return steps, ""


@require_POST
def bench_recipe(request):
    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    if "delete" in body:
        rid = str(body.get("delete") or "")
        if not any(r["id"] == rid for r in _recipes(c)):
            return _err("There is no such recipe.", 409)
        c.recipes = [r for r in c.recipes if not (_herbal(r) and _recipe_id(r) == rid)]
        c.save()
        return JsonResponse({"recipes": _recipes(c)})
    name = str(body.get("name") or "").strip()
    if not name:
        return _err("A recipe needs a name.")
    steps, why = _clean_steps(body.get("steps"))
    if why:
        return _err(why)
    # Saving under a name that exists replaces it, as the old bench did: a recipe that
    # cannot be corrected is one nobody keeps.
    kept = [r for r in c.recipes
            if not (_herbal(r) and str(r.get("name", "")).lower() == name.lower())]
    taken = {str(r.get("id")) for r in kept if r.get("id")}
    n = 1
    while f"r{n}" in taken:
        n += 1
    kept.append({"id": f"r{n}", "name": name, "craft": "herbalism", "steps": steps})
    c.recipes = kept
    c.save()
    return JsonResponse({"recipes": _recipes(c)})
