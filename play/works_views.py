"""The In-progress section's API (docs/enchanting-contracts.md §8.2).

    GET  api/works            {rows, summary}
    POST api/works/collect    {key}  -> {ok, said, product, rows, summary} | 409 {error}
    POST api/works/cancel     {key}  -> {ok, said, rows, summary}          | 409 {error}

Every number and every word on a row is computed by `rules/inprogress.py`; the page draws
what it is sent (UI plan §6.10) and re-asks when the table's clock turns, never on a timer.
Nothing here settles: a work turns ready inside `Scene.advance`, which tells it, and a view
that settled would swallow the tell. The rows read their state off the clock regardless.
"""
from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from rules import inprogress

from . import campaign as campaign_mod
from .apiutil import read_body


def _err(text: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": text}, status=status)


def _ready():
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return None, None, _err("There is no character to hold any work.", 409)
    return c, pc, None


def _now(c) -> int:
    return int(c.scene.clock_minutes or 0)


def _listing(c, pc) -> dict:
    now = _now(c)
    here = getattr(pc, "at", None) or None
    return {"rows": inprogress.entries(pc, now, here=here),
            "summary": inprogress.summary(pc, now)}


@require_GET
def works(request):
    c, pc, refused = _ready()
    if refused:
        return refused
    return JsonResponse(_listing(c, pc))


@require_POST
def works_collect(request):
    c, pc, refused = _ready()
    if refused:
        return refused
    key = str(read_body(request).get("key") or "")
    if not key:
        return _err("Say which work to collect (`key`).")
    got = inprogress.collect(pc, key, now=_now(c), here=getattr(pc, "at", None) or None)
    if not got.get("ok"):
        return _err(str(got.get("why") or "It cannot be collected."), 409)
    # One line in the table's log, as a bench step writes one.
    c.transcript.append({"who": "gm", "kind": "consequence", "text": got["said"]})
    c.save()
    return JsonResponse({"ok": True, "said": got["said"], "product": got.get("product"),
                         **_listing(c, pc)})


@require_POST
def works_cancel(request):
    c, pc, refused = _ready()
    if refused:
        return refused
    key = str(read_body(request).get("key") or "")
    if not key:
        return _err("Say which work to stop (`key`).")
    got = inprogress.cancel(pc, key, now=_now(c))
    if not got.get("ok"):
        return _err(str(got.get("why") or "It cannot be stopped."), 409)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": got["said"]})
    c.save()
    return JsonResponse({"ok": True, "said": got["said"], **_listing(c, pc)})
