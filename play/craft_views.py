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
    return JsonResponse(result.as_dict())


@require_POST
def craft_do(request):
    """Attempt the chain. The dice decide, and the track advances either way.

    Scored through the engine's `craft` op rather than here, so crafting at this bench and
    crafting narrated at the table pass through exactly one piece of arithmetic. A spoiled
    batch still teaches something, which is the author's rule and the reason failure is
    reported rather than refused.
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

    chain = _chain_from(body, state["track"])
    pc = c.scene.pc()
    result = crafting.preview(state["track"], state["level"], chain,
                              stock=_stock_of(c, disc["id"]),
                              satchel=dict(pc.inventory) if pc else {},
                              carrier=pc, now_minute=c.scene.clock_minutes)
    if result.problems:
        return JsonResponse({"error": " ".join(result.problems)}, status=400)

    engine = c.engine()
    roll = engine.dice.d20(label=f"{disc['name']}: {result.name}", visibility="player")
    face = roll.faces[0]
    succeeded = face != 1 and (face == 20 or _hits(face, result.chance))

    # The deed a milestone-locked level waits on, recorded when it is actually done.
    # Without this the bench sent no `milestone` at all, so a character could craft the
    # very thing Herbalist 5 asks for and the level stayed locked for good — the points
    # were kept and nothing on the page ever explained what was missing.
    track = worldclass.get(state["track"])
    milestone = track.deed_done(tier=result.tier, success=succeeded)

    try:
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
    except IntentError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

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

    tell = " ".join(o.tell for o in resolution.outcomes if o.tell)
    c.transcript.append({
        "who": "gm", "kind": "consequence",
        "text": f"{result.name}: {'made' if succeeded else 'spoiled'} "
                f"(d20 {face} against {result.chance}%). {tell}".strip(),
    })
    c.save()
    return JsonResponse({
        "succeeded": succeeded, "roll": face, "chance": result.chance,
        "result": result.as_dict(), "tell": tell, "made": made, "spent": spent,
        "track": _track_state(c, disc),
    })


def _hits(face: int, chance: int) -> bool:
    """A d20 face against a percentage: 95% needs 2+, 25% needs 16+, 5% needs a 20.

    A d20 rather than a d100 because every other roll in the game is a d20 and the log
    should read the same way throughout. The cost is granularity — chances land on
    multiples of 5 — which `crafting._chance` already produces.
    """
    return face >= 21 - max(1, round(chance / 5))


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
        "track": state,
    })


@require_POST
def forage_do(request):
    """Walk the ground and see what turns up. Routed through the engine's `forage` op so
    the bench and the table roll on exactly the same machinery."""
    body = json.loads(request.body or "{}")
    c = campaign_mod.current()
    params = {}
    if body.get("biome"):
        params["biome"] = str(body["biome"])
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
