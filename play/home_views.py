"""The front page: the shelf of worlds, what has been played, and the homebrew benches.

Its own module for the same reason the crafting bench got one — `views.py` is the play
loop and should stay that.

Every count and every label on this page is read from something real. A front page that
advertises features by listing them is the easiest thing in an app to let drift, and the
first thing a user stops trusting when it does.
"""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from rules import biomes, ingredients, worldclass
from rules.bestiary import TEMPLATES
from rules.tables import ARMOUR, CONDITIONS, FEATS, SHIELDS, WEAPONS

from . import campaign as campaign_mod
from . import library, roster
from .craft_views import DISCIPLINES


def _benches() -> list[dict]:
    """The homebrew workbenches, each saying honestly what stands behind it.

    `count` is the number of things that already exist of that kind, read from the tables
    rather than typed here, so a bench cannot claim content the app does not have.
    """
    return [
        {"id": "items", "name": "Items, weapons & armour", "ready": True,
         "count": len(WEAPONS) + len(ARMOUR) + len(SHIELDS),
         "blurb": "Weapons, armour and shields. Hardness and hit points come from the "
                  "material; the tables are the starting point, not the limit."},
        {"id": "creatures", "name": "Creatures", "ready": True,
         "count": len(TEMPLATES),
         "blurb": "Stat blocks the engine can put in a scene and roll for."},
        {"id": "ingredients", "name": "Ingredients", "ready": True,
         "count": len(ingredients.all_ingredients()),
         "blurb": "What a crafter works with, and the biomes each one grows in."},
        {"id": "worldclasses", "name": "World classes", "ready": True,
         "count": len(worldclass.tracks()),
         "blurb": "Tracks that run alongside a character class and level on use — "
                  "Herbalism, and whatever you write next."},
        {"id": "npcs", "name": "NPCs", "ready": False,
         "count": 0,
         "blurb": "A creature plus the world-facing facts: who they are, what they want, "
                  "who they know. Authored here, placed in a world."},
        {"id": "spells", "name": "Spells", "ready": False, "count": 0,
         "blurb": "Nothing behind this yet — the engine has no spell system, so a spell "
                  "editor would write records nothing could cast."},
        {"id": "campaigns", "name": "Campaigns", "ready": False, "count": 0,
         "blurb": "A premise, a cast and a goal the GM steers toward. Waiting on the "
                  "campaign format; sandbox play works today."},
        {"id": "rulesets", "name": "Rulesets", "ready": False,
         "count": len(CONDITIONS) + len(FEATS),
         "blurb": "Toggles and numeric overrides — max hit points at 1st level, crit "
                  "confirmation off. See docs/homebrew-rules.md."},
    ]


@ensure_csrf_cookie
@require_GET
def home(request):
    """The shelf. Everything here is read from disk on each load rather than cached: this
    page is opened rarely and being wrong on it is expensive."""
    active = campaign_mod.current()
    pc = active.scene.pc()
    return render(request, "play/home.html", {
        "state_json": json.dumps({
            "worlds": [w.as_dict() for w in library.worlds()],
            "recent": library.recent_characters(),
            "benches": _benches(),
            "disciplines": DISCIPLINES,
            "biomes": [{"id": b, "describe": d} for b, d in biomes.BIOMES.items()],
            "continue": {
                "character": pc.name if pc else "",
                "hp": f"{pc.hp}/{pc.hp_max}" if pc else "",
                "world": active.world.name if active.world else "",
                "location": active.location.name if active.location else "",
                "biome": active.biome,
                "lines": len(active.transcript),
                "turns": len(active.turn_log),
                "ended": active.ended,
            } if pc else None,
            "pregens": roster.pregens(),
        }),
    })


@require_GET
def world_detail(request, world_id: str):
    """One world: what is being played in it, and who is in it."""
    try:
        card = library.get(world_id)
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    return JsonResponse({
        "world": card.as_dict(),
        "campaigns": library.campaigns_in(world_id),
        "characters": library.characters_in(world_id),
        "pregens": roster.pregens(),
    })


@require_POST
def start_in_world(request):
    """Begin a sandbox in a world, with a character.

    Only the shipped world can be started in today, and the refusal says so rather than
    quietly beginning somewhere else: `new_campaign` reads `settings.WORLD_EXPORT`, so
    choosing another world here would produce a campaign in Pangrella wearing the wrong
    name.
    """
    from django.conf import settings
    from pathlib import Path

    body = json.loads(request.body or "{}")
    world_id = str(body.get("world", "")).strip()
    try:
        card = library.get(world_id)
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    if not card.playable:
        return JsonResponse({"error": card.problem}, status=400)
    if Path(card.source) != Path(settings.WORLD_EXPORT):
        return JsonResponse(
            {"error": f"{card.name} cannot be started in yet — this build plays in "
                      f"{Path(settings.WORLD_EXPORT).stem} only. Importing a world puts "
                      f"it on the shelf; playing in it needs the campaign to carry its "
                      f"own world, which is the next piece."},
            status=400)

    source = str(body.get("source", "")).strip()
    try:
        character = roster.from_pregen(source) if source else None
    except FileNotFoundError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    if character is None:
        return JsonResponse({"error": "Pick who is playing."}, status=400)

    campaign_mod.begin_with(character)
    return JsonResponse({"ok": True})


@require_POST
def resume(request):
    """Put a character back in the chair and go to the table."""
    body = json.loads(request.body or "{}")
    try:
        campaign_mod.switch_to(str(body.get("id", "")).strip())
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    return JsonResponse({"ok": True})


@require_GET
def bench(request, bench_id: str):
    """What one homebrew bench already holds.

    Listing the built-in content is the honest start for an editor: you author against
    what exists, and seeing thirty weapons is what tells you the shape a thirty-first
    should take.
    """
    found = next((b for b in _benches() if b["id"] == bench_id), None)
    if found is None:
        return JsonResponse({"error": f"no bench {bench_id!r}"}, status=404)

    rows: list[dict] = []
    if bench_id == "items":
        rows = (
            [{"name": v["name"], "kind": "weapon",
              "note": f"{v['damage']} {v['type']}, x{v['crit_mult']}"}
             for v in WEAPONS.values()]
            + [{"name": v["name"], "kind": "armour", "note": f"+{v['ac']} AC"}
               for k, v in ARMOUR.items() if k != "none"]
            + [{"name": v["name"], "kind": "shield", "note": f"+{v['ac']} AC"}
               for k, v in SHIELDS.items() if k != "none"]
        )
    elif bench_id == "creatures":
        rows = [{"name": v.get("name", k), "kind": "creature",
                 "note": f"{v.get('hp', '?')} hp, AC {v.get('flat_ac', '?')}"}
                for k, v in TEMPLATES.items()]
    elif bench_id == "ingredients":
        rows = [{"name": i.name, "kind": i.kind,
                 "note": f"{i.tier} · {', '.join(i.biomes) or 'nowhere'}"}
                for i in sorted(ingredients.all_ingredients().values(),
                                key=lambda x: x.name)]
    elif bench_id == "worldclasses":
        rows = [{"name": t.name, "kind": "track",
                 "note": f"{t.max_level} levels · "
                         f"{len(t.unlocked_methods(t.max_level))} methods"}
                for t in worldclass.tracks().values()]

    return JsonResponse({"bench": found, "rows": rows})


@require_GET
def to_table(request):
    return redirect("table")
