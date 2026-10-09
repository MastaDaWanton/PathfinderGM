"""The three requests behind "Make a report for the developer" (`play/report.py`).

The page never reads a file. It asks what would go in (`GET /api/report`), asks for the
zip (`POST /api/report`, an attachment the browser saves), and asks for the two ways to
send it (`POST /api/report/links`). Everything in all three answers is built here, after
`pathfindergm/redact.py` has been over it.

This machine only, like the phone door (`views._only_this_machine`): the zip carries the
logs and the save, and a phone on the Wi-Fi that holds the pass to play is not thereby
somebody who should be handed the desktop's log files. The phone gets a sentence saying
where to press instead.

Exempt from the game lock (`play/concurrency.py`). The report is wanted most while a turn
is stuck on a model that stopped answering, which is exactly when the lock is held; and it
reads the save from disk, never the campaign in memory, so the lock protects nothing here.
"""
from __future__ import annotations

from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_http_methods, require_POST

from .apiutil import read_body
from . import report

# The player's own words are a paragraph, not a document. Bounded so a pasted log cannot
# make the zip or the URLs anything other than what they are.
MAX_WORDS = 20_000


def _refused(request):
    from pathfindergm import lan

    if lan._from_this_machine(request):
        return None
    return JsonResponse({"error": "Make the report on the machine running the game: "
                                  "Settings, Make a report for the developer."},
                        status=403)


def _words(body: dict) -> str:
    return str(body.get("description") or "")[:MAX_WORDS]


def _include_save(body: dict) -> bool:
    """Included unless the player unticked it. Absent means included: the owner's default
    (2026-10-08), and a missing field must not quietly leave the save out."""
    value = body.get("include_save", True)
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off", "")
    return bool(value)


@require_http_methods(["GET", "POST"])
def report_zip(request):
    """GET: what would go in, file by file. POST: the zip itself, as an attachment."""
    refusal = _refused(request)
    if refusal:
        return refusal
    if request.method == "GET":
        return JsonResponse(report.listing())
    body = read_body(request)
    data = report.build(_words(body), _include_save(body),
                        note=str(body.get("note") or "")[:2000])
    import io

    name = report.zip_name()
    response = FileResponse(io.BytesIO(data), as_attachment=True, filename=name,
                            content_type="application/zip")
    # The page reads the name off this header so it can say where the file went.
    response["X-Report-Name"] = name
    response["Cache-Control"] = "no-store"
    return response


@require_POST
def report_links(request):
    """The prefilled GitHub issue and email for a report already saved."""
    refusal = _refused(request)
    if refusal:
        return refusal
    body = read_body(request)
    return JsonResponse(report.links(_words(body), str(body.get("zip") or "")))
