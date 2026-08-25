"""The class builder: one page that authors a whole 1e class.

Its own module for the same reason the crafting bench got one — `views.py` is the play loop
and should stay that.

Everything the page draws comes from `rules/classbuilder.CLASS_SCHEMA`, and everything it
refuses comes from `rules/classbuilder.validate_class`. No field list, no vocabulary and no
error message is written in the template: a class gaining a field is one entry in the schema
and appears here without a line of JavaScript changing. That is the same bargain
`rules/registry.py` struck for the content benches, and it is the only way the form and the
loader cannot drift apart.

**Nothing is written until it validates.** `save_class` raises on any problem, and this
module reports the problems rather than writing a half-valid file — `rules.classes` swallows
an unreadable class file silently, so the failure mode of writing anyway is a class that has
quietly stopped existing.
"""
from __future__ import annotations

import json

from django.http import JsonResponse
from .apiutil import read_body, read_int
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from rules import classbuilder, classes as classes_mod, effectspec, registry


def _jsonable(value):
    """Class data as JSON. The loader turns three fields into tuples on the way in.

    `rules/classes.py:all_classes` normalises `good_saves`, `class_skills` and
    `proficiencies` to tuples because the engine reads them that way, and `json.dumps`
    handles a tuple fine — but a *shipped* class from `rules/tables.py` is tuples all the
    way down and round-tripping one through the editor has to give back a list, or the file
    written differs from the file read for no reason a user could see.
    """
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _payload(request) -> dict:
    body = read_body(request)
    entry = body.get("class") if isinstance(body, dict) else None
    return entry if isinstance(entry, dict) else (body if isinstance(body, dict) else {})


@ensure_csrf_cookie
@require_GET
def class_builder(request):
    """The page itself. The whole schema goes down with it, so the form exists offline."""
    return render(request, "play/classbuilder.html", {
        "state_json": json.dumps(_catalogue()),
    })


def _catalogue() -> dict:
    """Everything the page needs to draw itself once."""
    return {
        "schema": classbuilder.schema(),
        "scaffolds": classbuilder.scaffold_list(),
        "effects": effectspec.catalogue(),
        "engine_ops": classbuilder.ENGINE_OPS,
        "max_tier": classbuilder.MAX_TIER,
        "max_level": classbuilder.MAX_LEVEL,
        "track_phrase": classbuilder.TRACK_PHRASE,
        "homebrew_dir": str(registry.homebrew_dir("classes")),
        # What already exists, so the builder can open one rather than only create.
        # `mine` marks the ones in the user's own folder: a shipped class opens as a
        # starting point and saves as an overlay, which is the registry's rule everywhere.
        "existing": _existing(),
    }


def _existing() -> list[dict]:
    mine = set(registry.read_folder(registry.homebrew_dir("classes"), "classes"))
    out = []
    for cid, cls in sorted(classes_mod.all_classes().items()):
        out.append({
            "id": cid,
            "name": cls.get("name", cid),
            "mine": cid in mine,
            "paths": len(cls.get("paths") or {}),
            "levels": len(cls.get("levels") or []),
        })
    return out


@require_GET
def class_catalogue(request):
    return JsonResponse(_catalogue())


@require_GET
def class_scaffold(request, kind: str):
    try:
        return JsonResponse({"class": classbuilder.scaffold(kind)})
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)


@require_GET
def class_open(request, class_id: str):
    """One class, as data, for editing. Shipped or authored — both open."""
    found = classes_mod.get(class_id)
    if not found:
        return JsonResponse(
            {"error": f"no class {class_id!r}. Known: "
                      f"{', '.join(sorted(classes_mod.all_classes()))}."}, status=404)
    entry = _jsonable(found)
    entry.setdefault("id", str(class_id).strip().lower())
    return JsonResponse({"class": entry,
                         "problems": classbuilder.validate_class(entry)})


@require_POST
def class_validate(request):
    """Live validation. Always 200: a form being wrong is not a request being wrong."""
    try:
        entry = _payload(request)
    except json.JSONDecodeError as exc:
        return JsonResponse({"problems": [f"The JSON does not parse: {exc}."]})
    return JsonResponse({"problems": classbuilder.validate_class(entry)})


@require_POST
def class_save(request):
    """Write it to the homebrew folder, where `rules.classes` layers it over what ships."""
    try:
        entry = _payload(request)
    except json.JSONDecodeError as exc:
        return JsonResponse({"problems": [f"The JSON does not parse: {exc}."]},
                            status=400)
    problems = classbuilder.validate_class(entry)
    if problems:
        return JsonResponse({"problems": problems}, status=400)
    try:
        path = classbuilder.save_class(entry)
    except (ValueError, OSError) as exc:
        return JsonResponse({"problems": [str(exc)]}, status=400)
    return JsonResponse({"ok": True, "id": entry.get("id"), "path": str(path),
                         "existing": _existing()})
