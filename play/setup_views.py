"""First run: what is missing, and the button that fetches it.

Two endpoints. `GET /api/setup` is the whole story in one object, cheap enough to ask
on every page load. `POST /api/setup/pull` streams Ollama's own download progress
straight through to the page, so a 7.4 GB wait has a moving bar in front of it rather
than a spinner and a guess.
"""
from __future__ import annotations

import json

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET, require_POST

from . import preflight
from .apiutil import read_body


@require_GET
def setup_state(request):
    """What this machine can and cannot do, with the disk warning if there is one."""
    report = preflight.check()
    return JsonResponse({**report.as_dict(), "room": preflight.room_for(report)})


@require_POST
def setup_pull(request):
    """Download one model, reporting progress as it goes.

    NDJSON rather than server-sent events: the payload is already one JSON object per
    line coming out of Ollama, SSE would mean re-framing every one of them, and the
    page reads it with a plain `fetch` reader either way.

    The model is checked against what some role is actually configured to use. Without
    that, this endpoint is an arbitrary-download button on a localhost port — anything
    that can reach the app could spend the player's disk on any model in the registry.
    """
    body = read_body(request)
    wanted = str(body.get("model", "")).strip()
    report = preflight.check()
    known = {need.model: need for need in report.needs}
    need = known.get(wanted) or known.get(preflight._norm(wanted))
    if need is None:
        return JsonResponse(
            {"error": f"{wanted or 'that'} is not a model any role is set to use."},
            status=400)
    if report.state in ("not-installed", "not-running", "unreachable"):
        return JsonResponse({"error": report.why or "Ollama is not answering."},
                            status=409)

    def frames():
        # `X-Accel-Buffering` is meaningless to the WSGI server this app runs on and
        # costs nothing; it is here for anyone who later puts a proxy in front of it,
        # because a buffering proxy turns this stream back into the spinner it exists
        # to replace.
        for frame in preflight.pull(need.model, report.host):
            yield json.dumps(frame) + "\n"

    response = StreamingHttpResponse(frames(), content_type="application/x-ndjson")
    response["Cache-Control"] = "no-store"
    response["X-Accel-Buffering"] = "no"
    return response
