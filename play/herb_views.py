"""Herb knowledge: the herbarium, studying, tasting, asking, reading
(docs/herbalism-contracts.md §4).

SCAFFOLD: the routes exist so no two lanes edit `pathfindergm/urls.py`. The discovery
lane owns this module and replaces every body.
"""
from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST


def _todo(section: str) -> JsonResponse:
    return JsonResponse({"error": f"not built yet: docs/herbalism-contracts.md {section}"},
                        status=501)


@require_GET
def herbarium(request):
    return _todo("§4.1")


@require_GET
def herb_card(request, herb_id: str):
    return _todo("§4.2")


@require_POST
def herb_study(request):
    return _todo("§4.3")


@require_POST
def herb_taste(request):
    return _todo("§4.4")


@require_POST
def herb_ask(request):
    return _todo("§4.5")


@require_POST
def herb_library(request):
    return _todo("§4.5")


@require_POST
def herb_manual(request):
    return _todo("§4.6")
