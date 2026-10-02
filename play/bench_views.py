"""The herbalism bench's API (docs/herbalism-contracts.md §3).

SCAFFOLD: the routes exist so no two lanes edit `pathfindergm/urls.py`. The bench-engine
lane owns this module and replaces every body. Each stub answers 501 with the contract
section it owes, so a page built against the contract fails loudly and says which half is
missing rather than quietly rendering nothing.
"""
from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST


def _todo(section: str) -> JsonResponse:
    return JsonResponse({"error": f"not built yet: docs/herbalism-contracts.md {section}"},
                        status=501)


@require_GET
def bench_state(request):
    return _todo("§3.1")


@require_POST
def bench_check(request):
    return _todo("§3.2")


@require_POST
def bench_roll(request):
    return _todo("§3.3")


@require_POST
def bench_finish(request):
    return _todo("§3.4")


@require_POST
def bench_perks(request):
    return _todo("§3.5")


@require_POST
def bench_recipe(request):
    return _todo("§3.6")
