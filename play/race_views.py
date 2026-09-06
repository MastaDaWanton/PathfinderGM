"""The race editor: a page of pickers.

"fix the race editor so that its all dropdowns and pickers because they should not need
to type anything other than a name. they can craft the anatomy from the Eidolon
evolutions free of cost" (2026-09-06). So the page draws every choice from
`rules.races.catalogue()` — creature type, size, speed, the Race Builder's ability
options, languages, the extra feat and rank, and the anatomy as eidolon evolutions with
their pickers (an energy, a skill, an ability, an attack) — and posts a structured
document to the same save the bench uses, where `rules.races.save_from_bench` refuses
a bad one with the fix named. The document is what plays: `expand` turns the
evolutions into tags, modifiers and natural weapons every time it is read.
"""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from rules import houserules, races as races_mod


@ensure_csrf_cookie
@require_GET
def race_builder(request):
    """The page. The whole catalogue goes with it, so the form draws once and works
    offline; `?open=<id>` opens a race, shipped or yours, as the starting point."""
    return render(request, "play/racebuilder.html", {
        "state_json": json.dumps({
            "catalogue": races_mod.catalogue(),
            "races": [{"id": k, "name": d["name"], "origin": d.get("origin", "core")}
                      for k, d in sorted(races_mod.all_races().items(),
                                         key=lambda kv: kv[1]["name"])],
            "open": str(request.GET.get("open", "")).strip().lower(),
            "race_rp": houserules.race_rp(),
        }),
    })


@require_GET
def race_open(request, race_id: str):
    """One race as a document — the structured fields the page's pickers set, plus
    what it computes (race points, the trait lines, the not-yet list) for the summary."""
    doc = races_mod.document(race_id)
    if doc is None:
        return JsonResponse({"error": f"no race {race_id!r}"}, status=404)
    mine = races_mod.homebrew_dir() / f"{doc['id']}.json"
    doc["source"] = "yours" if mine.exists() else "shipped"
    return JsonResponse(doc)
