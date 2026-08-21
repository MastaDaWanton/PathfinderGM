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

from rules import biomes

from . import campaign as campaign_mod
from . import homebrew, library, roster
from .craft_views import DISCIPLINES


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
            "benches": [b.as_dict() for b in homebrew.benches()],
            "authored": homebrew.authored_total(),
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
    """One bench: what you have authored, and what ships to author against.

    Shipped content is returned labelled rather than counted as homebrew — reporting 23
    Core Rulebook weapons as things the user had made was the reason this page could not
    be trusted.
    """
    try:
        found = homebrew.get(bench_id)
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    return JsonResponse({"bench": found.as_dict(), "rows": homebrew.rows_for(bench_id)})


@require_GET
def to_table(request):
    return redirect("table")
