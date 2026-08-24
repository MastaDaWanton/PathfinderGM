"""The crafting bench, as a browser page.

Its own module rather than more of `views.py`, which is the play loop and should stay
that. Nothing here talks to a model: crafting is arithmetic over ingredients and a track,
so it is engine work start to finish.

The workbench is assumed to fold out wherever the character is standing, per the design
call, so a chain is judged on the crafter and the materials alone and never on location.
"""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from rules import biomes, consumables, crafting, foraging, ingredients, worldclass
from rules.intents import IntentError

from . import campaign as campaign_mod

# The disciplines the app knows about. Only Herbalism has rules behind it; the rest are
# declared so the page is honest about what is coming instead of hiding it. `track` is
# None where no world class exists yet, and the tab says so rather than 404ing.
DISCIPLINES = [
    {"id": "herbalism", "name": "Herbalism", "track": "herbalist",
     "blurb": "Foraging, harvesting and brewing — poultices, teas, tinctures, elixirs."},
    {"id": "alchemy", "name": "Alchemy", "track": None,
     "blurb": "Reagents, reactions, and bottled consequences."},
    {"id": "blacksmithing", "name": "Blacksmithing", "track": None,
     "blurb": "Forge work: weapons, armour, and the tools every other craft needs."},
    {"id": "leatherworking", "name": "Leatherworking", "track": None,
     "blurb": "Hides into armour, straps, cases and bindings."},
    {"id": "enchanting", "name": "Enchanting", "track": None,
     "blurb": "Binding lasting magic into objects that will hold it."},
]


def _discipline(disc_id: str) -> dict:
    found = next((d for d in DISCIPLINES if d["id"] == disc_id), None)
    if found is None:
        raise LookupError(f"no such craft {disc_id!r}")
    return found


def _track_state(campaign, disc: dict) -> dict:
    """Where the character stands in this discipline, and what it has unlocked."""
    pc = campaign.scene.pc()
    if not disc["track"] or pc is None:
        return {"available": False, "blurb": disc["blurb"], "name": disc["name"]}

    track = worldclass.get(disc["track"])
    progress = pc.track(track.id)
    here = track.at(progress.level)
    return {
        "available": True,
        "track": track.id,
        "name": track.name,
        "level": progress.level,
        "max_level": track.max_level,
        "mp": progress.mp,
        "to_next": worldclass._remaining(track, progress),
        "max_tier": here.max_tier,
        "max_rank": worldclass.tier_rank(here.max_tier),
        "methods": track.unlocked_methods(progress.level),
        # Every method, including the ones still out of reach, each with the level that
        # grants it. A station the player cannot use yet is a reason to keep going; a
        # station that is simply absent is not.
        "all_methods": [
            {"method": m, "level": lvl.level, "known": lvl.level <= progress.level}
            for lvl in sorted(track.levels, key=lambda x: x.level)
            for m in lvl.methods
        ],
        "tools": track.unlocked_tools(progress.level),
        "known_recipes": len(progress.crafted),
    }


def _chain_from(body: dict, track_id: str) -> crafting.Chain:
    return crafting.Chain(
        track=track_id,
        methods=[str(m).strip().lower() for m in body.get("methods", [])],
        ingredient_ids=[str(i).strip().lower() for i in body.get("ingredients", [])],
        name=str(body.get("name", "")).strip(),
        stock_used={str(k): int(v) for k, v in (body.get("stock") or {}).items()
                    if int(v) > 0},
    )


def _stock_of(campaign, craft_id: str) -> dict:
    """What the character has made in this discipline, and can craft with again.

    Filtered by discipline because a bench should offer what belongs on it: a jar of tea
    is not a thing you reach for at a forge.
    """
    pc = campaign.scene.pc()
    if pc is None:
        return {}
    track = next((d["track"] for d in DISCIPLINES if d["id"] == craft_id), None)
    return {k: v for k, v in pc.stock.items() if not track or v.craft == track}


@ensure_csrf_cookie
@require_GET
def craft_page(request):
    """`ensure_csrf_cookie` for the same reason the table has it: without the cookie the
    page renders perfectly and then every POST 403s, with nothing on screen saying why."""
    c = campaign_mod.current()
    pc = c.scene.pc()
    return render(request, "play/craft.html", {
        "state_json": json.dumps({
            "disciplines": DISCIPLINES,
            "pc": {"name": pc.name if pc else "", "hp": pc.hp if pc else 0,
                   "hp_max": pc.hp_max if pc else 0},
            "tracks": {d["id"]: _track_state(c, d) for d in DISCIPLINES},
            "recipes": c.recipes,
        }),
    })


@require_GET
def craft_ingredients(request):
    """The shelf. Out-of-reach material is returned marked, never filtered out.

    A shelf that silently hides the interesting half gives a player no reason to level.
    One that shows a Phoenix Feather greyed with the tier it needs gives them a goal.
    """
    c = campaign_mod.current()
    try:
        disc = _discipline(request.GET.get("craft", "herbalism"))
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    state = _track_state(c, disc)
    ceiling = state.get("max_rank", 0)
    out = []
    for ing in sorted(ingredients.all_ingredients().values(), key=lambda i: i.name):
        d = ing.as_dict()
        d["usable"] = bool(ceiling) and d["rank"] <= ceiling
        out.append(d)

    pc = c.scene.pc()
    satchel = dict(pc.inventory) if pc else {}
    for d in out:
        d["held"] = satchel.get(d["id"], 0)

    stock = []
    for item in sorted(_stock_of(c, disc["id"]).values(),
                       key=lambda s: (s.base.lower(), s.concentration)):
        d = item.as_dict()
        d["usable"] = bool(ceiling) and d["rank"] <= ceiling
        # Read off the effects rather than the name, and grouped the same way the preview
        # groups them, so a jar that will poison whoever drinks it says so on the shelf.
        # A "Purified Draught of Skull Orchid" is not made safe by being called one, and
        # nothing on the shelf used to distinguish the two.
        d["poisons"] = [p.as_dict() for p in
                        consumables.poisons(item.specs, source=item.base)]
        d["can_concentrate"] = item.count >= crafting.CONCENTRATE_COST
        out_of = crafting.concentrate(item)
        d["concentrates_to"] = {"name": out_of.name, "tier": out_of.tier,
                                "potency": round(out_of.potency, 2),
                                "cost": crafting.CONCENTRATE_COST}
        stock.append(d)
    return JsonResponse({
        "ingredients": out, "stock": stock, "track": state,
        "biome": c.biome,
        "biome_describe": biomes.describe(c.biome),
        "table": foraging.table_for(c.biome,
                                    state.get("max_rank", 1)).as_dict(),
    })


@require_POST
def craft_preview(request):
    """What the chain would make. Never an error for a chain that is merely bad — the
    problems come back in the body so the page can grey the button and say why."""
    body = json.loads(request.body or "{}")
    c = campaign_mod.current()
    try:
        disc = _discipline(str(body.get("craft", "herbalism")))
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    state = _track_state(c, disc)
    if not state.get("available"):
        return JsonResponse({"error": f"{disc['name']} has no rules yet."}, status=400)

    chain = _chain_from(body, state["track"])
    pc = c.scene.pc()
    result = crafting.preview(state["track"], state["level"], chain,
                              stock=_stock_of(c, disc["id"]),
                              satchel=dict(pc.inventory) if pc else {},
                              carrier=pc, now_minute=c.scene.clock_minutes)
    out = result.as_dict()
    # Why each jar on the shelf would be refused by the chain as it currently stands, so
    # the shelf can grey them before one is picked up. The preparation rules were being
    # enforced correctly and saying nothing until you had already built a chain and
    # pressed Craft — which reads exactly like the rules not working at all.
    out["refused"] = _shelf_refusals(chain.methods)
    # How many the materials allow, so the bench can offer "all 47" rather than making the
    # player count it out and then find they were three short halfway through the batch.
    out["batch_max"] = batch_max(result, pc)
    return JsonResponse(out)


def _shelf_refusals(methods) -> dict:
    """`{ingredient id: why the chain would refuse it}` for everything on the shelf.

    Computed here rather than in the page, from the same walk `preview` uses, because a
    second copy of the preparation rules in JavaScript is the shape of bug this project
    has paid for twice — a rule corrected in one place and left stale in the copy nobody
    looked at. 162 ingredients through a walk of at most a handful of steps is nothing.
    """
    if not methods:
        return {}
    out = {}
    for iid, item in ingredients.all_ingredients().items():
        why = crafting.prep_problem(item, methods)
        if why:
            out[iid] = why
    return out


# A ceiling on one request, well above any real batch. "100 acacia powder tea" is the
# case this exists for; a hand-written request for a million would otherwise roll a
# million d20s before the response ever went out.
MAX_BATCH = 1000


def batch_max(result, pc) -> int:
    """How many of this chain the materials on hand allow.

    Per-dose costs against what is carried, taking the tightest. Reported with the preview
    so the bench can offer "all 47" rather than making the player work it out and then
    discover halfway through a batch that they were three short.
    """
    if pc is None:
        return 0
    limit = MAX_BATCH
    for sid, n in (result.consumes or {}).items():
        if n > 0:
            held = getattr(pc.stock.get(sid), "count", 0)
            limit = min(limit, int(held) // n)
    for iid, n in (result.consumes_raw or {}).items():
        if n > 0:
            limit = min(limit, int(pc.inventory.get(iid, 0)) // n)
    return max(0, limit)


@require_POST
def craft_do(request):
    """Attempt the chain, once or many times over.

    Scored through the engine's `craft` op rather than here, so crafting at this bench and
    crafting narrated at the table pass through exactly one piece of arithmetic. A spoiled
    batch still teaches something, which is the author's rule and the reason failure is
    reported rather than refused.

    A batch is N separate attempts, not one attempt for N doses: its own d20 each time,
    its own success, its own mastery. "i should not need to click the craft button 100
    times" is a complaint about the clicking, and the fix must not quietly become a change
    to the game — one roll for a hundred doses would mean a single 1 spoiling the lot,
    which is a different rule rather than the same rule automated.
    """
    body = json.loads(request.body or "{}")
    c = campaign_mod.current()
    try:
        disc = _discipline(str(body.get("craft", "herbalism")))
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    state = _track_state(c, disc)
    if not state.get("available"):
        return JsonResponse({"error": f"{disc['name']} has no rules yet."}, status=400)

    wanted = max(1, min(MAX_BATCH, int(body.get("batch", 1) or 1)))
    chain = _chain_from(body, state["track"])

    attempts, made_all, spent_all = [], [], {}
    stopped = ""
    for _ in range(wanted):
        # Recomputed every time round. The shelf changes as the batch runs — doses are
        # spent, and a concentration puts its output back on it — so a preview taken once
        # and reused would be describing a pot that no longer exists by attempt three.
        pc = c.scene.pc()
        result = crafting.preview(state["track"], state["level"], chain,
                                  stock=_stock_of(c, disc["id"]),
                                  satchel=dict(pc.inventory) if pc else {},
                                  carrier=pc, now_minute=c.scene.clock_minutes)
        if result.problems:
            if not attempts:
                return JsonResponse({"error": " ".join(result.problems)}, status=400)
            # Out of something, partway through. The doses already made are kept and the
            # reason is reported: a batch that rolled back on running short would throw
            # away work that really happened.
            stopped = " ".join(result.problems)
            break
        try:
            one = _one_craft(c, disc, state, result)
        except IntentError as exc:
            if not attempts:
                return JsonResponse({"error": str(exc)}, status=400)
            stopped = str(exc)
            break
        attempts.append(one)
        if one["made"]:
            made_all.append(one["made"])
        for k, n in one["spent"].items():
            spent_all[k] = spent_all.get(k, 0) + n

    succeeded = sum(1 for a in attempts if a["succeeded"])
    spoiled = len(attempts) - succeeded
    name = attempts[0]["name"] if attempts else ""

    # One line in the transcript however many doses were worked. A hundred crafts is one
    # afternoon at the bench, not a hundred things that happened to the party.
    if len(attempts) == 1:
        a = attempts[0]
        line = (f"{name}: {'made' if a['succeeded'] else 'spoiled'} "
                f"(d20 {a['roll']}{a['bonus']:+d} = {a['total']} vs DC {a['dc']}). "
                f"{a['tell']}").strip()
    elif attempts:
        line = (f"{name} x{len(attempts)}: {succeeded} made, {spoiled} spoiled "
                f"(d20{attempts[0]['bonus']:+d} vs DC {attempts[0]['dc']} each).")
    else:
        line = ""
    if stopped:
        line = f"{line} Stopped: {stopped}".strip()
    if line:
        c.transcript.append({"who": "gm", "kind": "consequence", "text": line})
    c.save()

    last = attempts[-1] if attempts else {}
    return JsonResponse({
        # The single-craft shape is kept intact so the page and everything else reading
        # this endpoint go on working unchanged; the batch block is an addition.
        "succeeded": bool(last.get("succeeded")),
        "roll": last.get("roll"), "chance": last.get("chance"),
        "total": last.get("total"), "bonus": last.get("bonus"),
        "dc": last.get("dc"), "terms": last.get("terms") or [],
        "result": last.get("result"), "tell": last.get("tell", ""),
        "made": last.get("made"), "spent": spent_all,
        "batch": {
            "asked": wanted, "attempted": len(attempts),
            "made": succeeded, "spoiled": spoiled,
            "rolls": [a["roll"] for a in attempts],
            "items": made_all, "stopped": stopped,
        },
        "track": _track_state(c, disc),
    })


def _one_craft(c, disc, state, result) -> dict:
    """One attempt: one roll, one outcome, one advance of the track."""
    engine = c.engine()
    roll = engine.dice.d20(label=f"{disc['name']}: {result.name}", visibility="player")
    face = roll.faces[0]
    # A check, not a percentile behind a curtain. The DC was already computed from the
    # chain and then thrown away in favour of a chance-to-hit; now the die is added to the
    # crafter's own bonus and compared to it, the way every other roll in the game works.
    # Natural 1 and natural 20 keep their usual authority over the arithmetic.
    total = face + result.bonus
    succeeded = face != 1 and (face == 20 or total >= result.dc)

    # The deed a milestone-locked level waits on, recorded when it is actually done.
    # Without this the bench sent no `milestone` at all, so a character could craft the
    # very thing Herbalist 5 asks for and the level stayed locked for good — the points
    # were kept and nothing on the page ever explained what was missing.
    track = worldclass.get(state["track"])
    milestone = track.deed_done(tier=result.tier, success=succeeded)

    resolution = engine.run(engine.validate([{
        "op": "craft", "actor": "pc",
        "because": f"a session at the {disc['name'].lower()} bench",
        "params": {
            "track": state["track"],
            "recipe": result.name.lower(),
            "tier": result.tier,
            "stages": max(1, result.stages),
            "risky": result.risky,
            "failed": not succeeded,
            "milestone": milestone,
            # Two doses in, one of the next band out: the ceiling is checked against
            # what went in, so the engine has to be told which kind of craft this is.
            "concentrating": result.concentrating,
        },
    }]))

    # The inputs are spent either way. A spoiled batch that hands the ingredients back
    # would make failure free, and the author's own note is that failure matters because
    # "rare ingredients spoil".
    pc = c.scene.pc()
    spent = {}
    for sid, n in result.consumes.items():
        took = pc.take_stock(sid, n)
        if took:
            spent[sid] = took

    for iid, n in result.consumes_raw.items():
        took = pc.spend(iid, n)
        if took:
            spent[iid] = spent.get(iid, 0) + took

    made = None
    if succeeded and result.output:
        item = crafting.from_stock_dict(result.output)
        pc.add_stock(item, 1)
        made = item.as_dict()

    return {
        "name": result.name, "succeeded": succeeded, "roll": face,
        "chance": result.chance, "result": result.as_dict(), "made": made,
        "spent": spent,
        # The whole check, so the bench can show the arithmetic rather than a verdict.
        "total": total, "bonus": result.bonus, "dc": result.dc, "terms": result.terms,
        "tell": " ".join(o.tell for o in resolution.outcomes if o.tell),
    }


@require_POST
def craft_recipes(request):
    """Keep a chain under a name, so a working recipe is worked out once."""
    body = json.loads(request.body or "{}")
    c = campaign_mod.current()
    name = str(body.get("name", "")).strip()
    if not name:
        return JsonResponse({"error": "A recipe needs a name."}, status=400)
    if not body.get("ingredients"):
        return JsonResponse({"error": "A recipe needs ingredients."}, status=400)

    entry = {
        "name": name,
        "craft": str(body.get("craft", "herbalism")),
        "methods": [str(m).strip().lower() for m in body.get("methods", [])],
        "ingredients": [str(i).strip().lower() for i in body.get("ingredients", [])],
    }
    # Saving under a name that already exists replaces it. A bench where the second save
    # silently makes a duplicate is a bench nobody can correct a recipe at.
    c.recipes = [r for r in c.recipes if r["name"].lower() != name.lower()]
    c.recipes.append(entry)
    c.save()
    return JsonResponse({"recipes": c.recipes})


# --- foraging -------------------------------------------------------------------------------

@require_GET
def forage_table(request):
    """The roll table for where the party is standing, and the biomes they could be in.

    Returned as the table itself rather than only its results, because a player who can
    see the d100 spread can decide whether this ground is worth an afternoon — which is
    the whole point of knowing what biome you are in.
    """
    c = campaign_mod.current()
    disc = _discipline(request.GET.get("craft", "herbalism"))
    state = _track_state(c, disc)
    biome = biomes.canonical(request.GET.get("biome", "") or c.biome)
    ceiling = state.get("max_rank", 1)
    return JsonResponse({
        "here": c.biome,
        "biome": biome,
        "biomes": [{"id": b, "describe": d} for b, d in biomes.BIOMES.items()],
        "table": foraging.table_for(biome, ceiling).as_dict(),
        "attempts": foraging.attempts_for(state.get("level", 1)),
        # Why the button is dead, sent with the table rather than discovered by pressing
        # it. The bench greys chains it cannot make and says why; foraging offered no
        # reason at all until the request came back refused.
        "busy": _forage_blocked(c),
        "track": state,
    })


def _forage_blocked(c) -> str:
    """The engine's own reason, asked before the attempt rather than after.

    Read off `Engine._too_busy_to_forage` rather than re-derived here, because two copies
    of a rule is how a corrected rule goes on shipping from the copy nobody looked at.
    """
    pc = c.scene.pc()
    if pc is None:
        return ""
    return c.engine()._too_busy_to_forage(pc)


def _narrate(messages, cfg, *, as_json=False, num_predict=220):
    """One short narration call, or None. The craft action must survive the model being
    down — a forage that cannot happen because Ollama is not running would be the bench
    breaking immersion in the opposite direction."""
    from gm import client as gm_client

    try:
        reply = gm_client.chat(
            messages, cfg["model"], host=cfg["host"], as_json=as_json,
            temperature=0.85, timeout=90, num_predict=num_predict,
            provider=cfg.get("provider", "ollama"), api_key=cfg.get("api_key", ""))
        # `chat` returns a Reply, not a string — the first live forage wrote
        # "Reply(text='You push aside…', model='llama3.1:8b')" into the book verbatim.
        return reply.json() if as_json else reply.text
    except Exception:
        return None


def _forage_scene(c):
    """Where and when, for the narrator's benefit."""
    place = c.location.name if c.location else "the open country"
    minutes = c.scene.clock_minutes
    day, rem = minutes // 1440 + 1, minutes % 1440
    return place, f"day {day}, {rem // 60} hours in"


@require_POST
def craft_action(request):
    """A crafting-related excursion, narrated into the scene it happens in.

    Foraging lived only on the bench page, where it was a button and a table: no
    narration, no sense of time passing, no way back into the fiction. "crafting related
    actions like foraging or mining or skinning don't break immersion" — so the run is
    told like a turn: the narrator opens it, the die lands where everyone can see it, the
    finding is told before the tally, and it ends the way every GM turn ends — what do
    you do, and three ways to answer.

    The engine still decides everything. Both narration calls are decoration around the
    same `forage` op the bench uses, and either call failing falls back to plain prose
    built from the facts — a model being down costs colour, never the herbs.
    """
    body = json.loads(request.body or "{}")
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)
    action = str(body.get("action", "forage")).strip().lower()
    if action != "forage":
        return JsonResponse(
            {"error": f"{action!r} is not a craft action yet — foraging only."},
            status=400)

    hours = max(1, min(48, int(body.get("hours", 1) or 1)))
    place, when = _forage_scene(c)
    from play import modelcfg

    cfg = modelcfg.for_role("narrator")

    # 1. The setting out. Written to the transcript before the roll, because that is
    # the order it happens in at a table.
    opening = _narrate([
        {"role": "system",
         "content": "You narrate a solo Pathfinder game. Two or three sentences, second "
                     "person, present tense. Never invent named people or places. Never "
                     "ask a question. Stop before anything is found."},
        {"role": "user",
         "content": f"{pc.name} sets out to forage for herbs. Terrain: {c.biome}. "
                     f"Near {place}, {when}. They mean to spend {hours} hour(s) "
                     f"searching. Narrate them beginning the search."},
    ], cfg, num_predict=140)
    if not opening or not str(opening).strip():
        opening = (f"You shoulder your satchel and work away from {place}, eyes on "
                   f"the ground, the {c.biome} closing in around you. {hours} hour"
                   f"{'s' if hours != 1 else ''} of searching lie ahead.")
    opening = str(opening).strip()
    c.transcript.append({"who": "gm", "text": opening})

    # 2. The dice decide. Same op as the bench; the client lands the visible die on the
    # first real d100 this rolled.
    try:
        resolution = c.engine().run(c.engine().validate([{
            "op": "forage", "actor": "pc",
            "because": f"{hours} hour{'s' if hours != 1 else ''} spent looking",
            "params": {"hours": hours},
        }]))
    except IntentError as exc:
        # The opening already happened in the fiction; take it back out rather than
        # narrating a search the engine refused.
        c.transcript.pop()
        return JsonResponse({"error": str(exc)}, status=400)

    tell = " ".join(o.tell for o in resolution.outcomes if o.tell)
    effects = [e for o in resolution.outcomes for e in o.effects
               if e.get("kind") == "forage"]
    found: dict[str, int] = {}
    rolls: list[int] = []
    for e in effects:
        for iid, n in (e.get("found") or {}).items():
            found[iid] = found.get(iid, 0) + n
        rolls.extend(int(r["roll"]) for r in e.get("rolls", []) if r.get("roll"))
    names = {i.id: i.name for i in ingredients.all_ingredients().values()}
    haul = [{"id": iid, "name": names.get(iid, iid), "count": n}
            for iid, n in sorted(found.items())]

    # 3. The finding, told before the tally, ending in the question and three answers.
    listed = ", ".join(f"{h['count']}x {h['name']}" for h in haul) or "nothing"
    closing_json = _narrate([
        {"role": "system",
         "content": "You narrate a solo Pathfinder game. Answer as JSON: "
                     '{"narration": "...", "suggestions": ["...", "...", "..."]}. '
                     "The narration is two or three sentences, second person, of the "
                     "character finding (or failing to find) exactly what is listed — "
                     "name only things from the list, invent nothing else, no numbers. "
                     "The suggestions are three short next actions a player might take, "
                     "each under eight words, imperative."},
        {"role": "user",
         "content": f"{pc.name} spent {hours} hour(s) foraging the {c.biome} near "
                     f"{place} and found: {listed}. Narrate the finding, then suggest "
                     f"three next actions."},
    ], cfg, as_json=True, num_predict=260)

    closing, suggestions = "", []
    if isinstance(closing_json, dict):
        closing = str(closing_json.get("narration") or "").strip()
        raw = closing_json.get("suggestions")
        if isinstance(raw, list):
            suggestions = [str(s).strip() for s in raw if str(s).strip()][:3]
        # Checked, not trusted: a narration that names a herb the ground did not give
        # is the GM inventing loot. Grounding is the same rule the main loop enforces.
        said = closing.lower()
        invented = [n for n in names.values()
                    if n.lower() in said and n not in [h["name"] for h in haul]]
        if invented:
            closing = ""
    if not closing:
        closing = ("The hours pass in stooping and sifting. " if haul else
                   "The hours pass in stooping and sifting, and the ground gives "
                   "nothing back. ")
        if haul:
            closing += ("Piece by piece the satchel takes on weight: " +
                        ", ".join(h["name"].lower() for h in haul[:4]) +
                        ("," if len(haul) > 4 else "") + " earth still on the roots.")
    if len(suggestions) != 3:
        suggestions = ["Keep foraging", f"Head back toward {place}",
                       "Unpack the crafting bench"]

    tally = " · ".join(f"{h['name']} ×{h['count']}" for h in haul) or "Nothing gathered."
    c.transcript.append({"who": "gm", "kind": "consequence",
                         "text": f"{closing}\n\nGathered: {tally}. {tell}".strip()})
    c.transcript.append({"who": "gm", "text": "What do you do?"})
    c.suggestions = suggestions
    c.save()

    return JsonResponse({
        "opening": opening, "closing": closing, "tell": tell,
        "found": haul, "rolls": rolls, "hours": hours,
        "suggestions": suggestions,
        "clock_minutes": c.scene.clock_minutes,
    })


@require_POST
def forage_do(request):
    """Walk the ground and see what turns up. Routed through the engine's `forage` op so
    the bench and the table roll on exactly the same machinery."""
    body = json.loads(request.body or "{}")
    c = campaign_mod.current()
    # No biome is sent. You forage where you are standing; the ground is `travel`'s to
    # change, and the bench has no business claiming to be somewhere else.
    params = {}
    # Clamped rather than trusted. The slider stops at 48, and a hand-written request for
    # a thousand hours would spend a thousand rolls before the body ever got a word in.
    hours = max(1, min(48, int(body.get("hours", 1) or 1)))
    params["hours"] = hours
    try:
        resolution = c.engine().run(c.engine().validate([{
            "op": "forage", "actor": "pc",
            "because": f"{hours} hour{'s' if hours != 1 else ''} spent looking",
            "params": params,
        }]))
    except IntentError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    tell = " ".join(o.tell for o in resolution.outcomes if o.tell)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": tell})
    c.save()
    effects = [e for o in resolution.outcomes for e in o.effects
               if e.get("kind") == "forage"]
    pc = c.scene.pc()
    return JsonResponse({
        "tell": tell,
        "result": effects[0] if effects else {},
        "inventory": dict(pc.inventory) if pc else {},
    })


@require_POST
def travel_to(request):
    """Change the ground underfoot from the bench, without going through the GM."""
    body = json.loads(request.body or "{}")
    c = campaign_mod.current()
    try:
        resolution = c.engine().run(c.engine().validate([{
            "op": "travel", "because": "the party moves on",
            "params": {"biome": str(body.get("biome", ""))},
        }]))
    except IntentError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    c.save()
    return JsonResponse({
        "biome": c.scene.biome,
        "describe": biomes.describe(c.scene.biome),
        "tell": " ".join(o.tell for o in resolution.outcomes if o.tell),
    })
