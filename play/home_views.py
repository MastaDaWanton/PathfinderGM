"""The front page: the shelf of worlds, what has been played, and the homebrew benches.

Its own module for the same reason the crafting bench got one — `views.py` is the play
loop and should stay that.

Every count and every label on this page is read from something real. A front page that
advertises features by listing them is the easiest thing in an app to let drift, and the
first thing a user stops trusting when it does.
"""
from __future__ import annotations

import json
import re

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from rules import biomes, effectspec, registry, spells
from world.loader import UnsupportedSchema

from . import campaign as campaign_mod
from .apiutil import read_body, read_int
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


@require_GET
def worlds(request):
    """The shelf, on its own. So the page can redraw after an import without a full
    reload, which would throw away the message saying what just happened."""
    return JsonResponse({"worlds": [w.as_dict() for w in library.worlds()]})


@require_POST
def import_world(request):
    """Take a World Bible export onto the shelf.

    Multipart rather than a path: the packaged app has no terminal, and a player who has
    just exported a world from World Bible has a file in Downloads, not a path they want
    to type. The file is refused with the loader's own reason if it is not a world this
    build can read — schema and all — rather than landing and failing later at the point
    somebody tries to play in it.
    """
    upload = request.FILES.get("world")
    if upload is None:
        return JsonResponse({"error": "No file was sent."}, status=400)
    try:
        card = library.import_upload(upload.name, upload.read())
    except UnsupportedSchema as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse(
            {"error": f"{upload.name} could not be read as a world: {exc}"}, status=400)
    return JsonResponse({"ok": True, "world": card.as_dict()})


@require_POST
def start_in_world(request):
    """Begin a sandbox in a world, with a character.

    Any world on the shelf, imported or shipped. This used to refuse everything but the
    shipped export, because `_begin` read `settings.WORLD_EXPORT` and a campaign started
    in Kaelinora would have been a campaign in Pangrella wearing the wrong name. The
    campaign already carried `world_source` and already loaded its world from it; the
    setting was only ever the *default*, and it is passed explicitly now.
    """
    from django.conf import settings
    from pathlib import Path

    body = read_body(request)
    world_id = str(body.get("world", "")).strip()
    try:
        card = library.get(world_id)
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    if not card.playable:
        return JsonResponse({"error": card.problem}, status=400)
    source = str(body.get("source", "")).strip()
    try:
        character = roster.from_pregen(source) if source else None
    except FileNotFoundError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    if character is None:
        return JsonResponse({"error": "Pick who is playing."}, status=400)

    campaign_mod.begin_with(character, world_source=card.source)
    return JsonResponse({"ok": True})


@require_POST
def resume(request):
    """Put a character back in the chair and go to the table."""
    body = read_body(request)
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
def effect_catalogue(request):
    """The taxonomy the editor builds its forms from.

    Served rather than duplicated in the page, so a new effect type is one entry in
    rules/effectspec.py and the form for it appears without a line of template changing.
    """
    return JsonResponse(effectspec.catalogue())


@require_GET
def kind_catalogue(request):
    """Every kind of content the app knows how to hold, and the fields each one has.

    The same idea as the effect catalogue one function above, applied a level up: the
    builder draws its form from this rather than carrying a hand-written form per bench.
    A new kind of content becomes one entry in `rules/registry.py` instead of a loader, a
    route, a form and a template.
    """
    from rules import registry

    return JsonResponse({"kinds": registry.catalogue()})


@require_POST
def effect_preview(request):
    """Validate a draft and show the line it would put on a card.

    All the problems at once: a builder that reports them one at a time is one nobody
    finishes a complex effect in.
    """
    body = read_body(request)
    out = []
    for i, spec in enumerate(body.get("effects") or []):
        out.append({
            "index": i,
            "problems": effectspec.validate(spec, f"effect {i + 1}"),
            "line": effectspec.render(spec),
            "engine": effectspec.executable(spec),
        })
    return JsonResponse({"effects": out,
                         "problems": [p for e in out for p in e["problems"]]})


@require_POST
def save_consumable(request):
    """Keep an authored thing. Refused if any effect is malformed — a file that cannot be
    read back is worse than a form the user has to finish."""
    body = read_body(request)
    name = str(body.get("name", "")).strip()
    if not name:
        return JsonResponse({"error": "It needs a name."}, status=400)

    specs = body.get("effects") or []
    problems = [p for i, s in enumerate(specs)
                for p in effectspec.validate(s, f"effect {i + 1}")]
    if problems:
        return JsonResponse({"error": " ".join(problems)}, status=400)

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "thing"
    path = homebrew.folder("consumables") / f"{slug}.json"
    path.write_text(json.dumps({
        "id": slug, "name": name,
        "kind": str(body.get("kind", "consumable")),
        "description": str(body.get("description", "")),
        "effects": specs,
    }, indent=1), encoding="utf-8")
    return JsonResponse({"ok": True, "id": slug, "path": str(path),
                         "lines": [effectspec.render(s) for s in specs]})


@require_GET
def open_thing(request, bench_id: str, thing_id: str):
    """Load something into the builder so it can be corrected.

    Anything on a bench opens, shipped or authored. The parse that produced the shipped
    effects is a starting point, not an answer — 161 entries were converted mechanically
    and nobody has read them, so being able to fix one is the difference between a
    conversion and a guess nobody can undo.
    """
    from rules import registry

    mine = homebrew.folder(homebrew.get(bench_id).dir) / f"{thing_id}.json"
    if mine.exists():
        d = json.loads(mine.read_text(encoding="utf-8"))
        d["source"] = "yours"
        return JsonResponse(d)

    # Every bench, not two. This used to read `if bench_id in ("ingredients",
    # "consumables")` and every other bench could create but never correct — a shipped
    # creature, feat, weapon or spell simply would not open. `registry.find` looks in the
    # user's directory first and then in whatever module owns that kind, so a bench is
    # editable the moment it is declared rather than when somebody adds it to an `if`.
    try:
        found = registry.find(bench_id, thing_id)
    except LookupError:
        found = None
    if not found:
        return JsonResponse(
            {"error": f"{thing_id!r} is not on the {bench_id} bench"}, status=404)

    # `description` and `effects` are what the builder's form is written against, so an
    # entry that calls them something else is translated rather than opening blank.
    found.setdefault("description", found.get("text", ""))
    found.setdefault("effects", [])
    # Whether these effects came out of a machine reading prose or out of a person. 161
    # ingredients were converted mechanically and nobody has read them, so an editor that
    # cannot tell the two apart is asking someone to trust a parse.
    found["converted"] = bool(found.get("effects_converted"))
    found["source"] = "shipped"
    return JsonResponse(found)


@require_POST
def save_thing(request, bench_id: str):
    """Keep an edit as an overlay. The shipped file is never written to.

    That is the rule from CLAUDE.md made concrete: a corrected table in a later build must
    not be shadowed by a stale copy in the user's data directory, so yours layers over what
    ships and both remain readable.
    """
    body = read_body(request)
    name = str(body.get("name", "")).strip()
    if not name:
        return JsonResponse({"error": "It needs a name."}, status=400)

    specs = body.get("effects") or []
    problems = [p for i, sp in enumerate(specs)
                for p in effectspec.validate(sp, f"effect {i + 1}")]
    if problems:
        return JsonResponse({"error": " ".join(problems)}, status=400)

    try:
        bench = homebrew.get(bench_id)
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    slug = str(body.get("id") or "").strip() or         re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "thing"

    # Every field this kind declares, not the five that suited a potion. A creature saved
    # through the old shape kept its name, kind, description and effects and lost its CR,
    # its size and its hit points — and because homebrew merges over shipped field by
    # field, the loss was invisible until something asked for the missing one.
    #
    # Read from the declaration rather than from the body, so a client cannot write keys
    # the kind does not have, and a field the form showed and the user cleared is written
    # as empty rather than dropped. Empty is not the same as absent: dropping it would let
    # the shipped value show through again, which reads as the edit having failed silently.
    try:
        kind = registry.get(bench_id)
    except LookupError:
        kind = None
    entry = {"id": slug, "name": name}
    if kind:
        for f in kind.fields:
            if f.name in ("name", "effects"):
                continue
            if f.name in body:
                entry[f.name] = body[f.name]
    entry["kind"] = str(body.get("kind", "")) or entry.get("kind") or bench_id
    entry["description"] = str(body.get("description", ""))
    entry["effects"] = specs
    # Cleared on save: these have now been looked at by a person, which is a different
    # state from "the converter produced them and nobody has checked".
    entry["effects_converted"] = False

    path = homebrew.folder(bench.dir) / f"{slug}.json"
    path.write_text(json.dumps(entry, indent=1, ensure_ascii=False), encoding="utf-8")
    return JsonResponse({"ok": True, "id": slug, "path": str(path),
                         "lines": [effectspec.render(sp) for sp in specs]})


@require_GET
def spell_search(request):
    """Filter the spell list.

    Descriptors and tags are separate parameters even though both read as labels, because
    they answer different questions: whether fire immunity stops it, and whether it is the
    sort of thing you are looking for.
    """
    g = request.GET
    level = g.get("level")
    found = spells.search(
        text=g.get("q", ""), school=g.get("school", ""),
        subschool=g.get("subschool", ""), descriptor=g.get("descriptor", ""),
        tag=g.get("tag", ""), klass=g.get("class", ""),
        level=int(level) if level not in (None, "") and level.isdigit() else None,
        limit=int(g.get("limit", 120)),
    )
    return JsonResponse({
        "count": len(found),
        "spells": [s.as_dict() for s in found],
        "vocab": spells.vocabularies(),
        "note": spells.meta().get("note", ""),
    })


@require_GET
def spell_detail(request, spell_id: str):
    try:
        return JsonResponse(spells.get(spell_id).as_dict())
    except KeyError as exc:
        return JsonResponse({"error": str(exc)}, status=404)


@require_GET
def to_table(request):
    return redirect("table")


@require_GET
def creation_options(request):
    """Everything the character-creation wizard draws its forms from.

    One payload rather than four endpoints, because the wizard needs all of it before the
    first click and a form that assembles itself from stale halves is how a race dropdown
    and a class list disagree about what exists.
    """
    from rules import creation

    return JsonResponse(creation.options())


def house_rules(request):
    """Read or change the table's house rules.

    GET answers with what is in effect and the tiers on offer; POST changes it and
    answers the same shape, so the page never has to guess what the server settled on.
    A refused change comes back with the rules unchanged and the reason named.
    """
    from rules import houserules

    if request.method == "POST":
        body = read_body(request)
        rules, problems = houserules.set_active(body)
        if problems:
            return JsonResponse({"rules": rules, "problems": problems}, status=400)
    return JsonResponse({"rules": houserules.active(),
                         "tiers": houserules.POINT_BUY_TIERS,
                         "caps": houserules.ABILITY_CAPS})


def model_settings(request):
    """Read or set which model does which job, and the keys for the hosted ones.

    GET never returns a key. It returns whether each provider has one and its last four
    characters — enough to recognise the key you pasted, and not enough to be worth
    lifting off a screenshot.
    """
    from . import modelcfg

    if request.method == "POST":
        body = read_body(request)
        problems = modelcfg.save(body.get("roles"), body.get("keys"))
        if problems:
            return JsonResponse({"problems": problems}, status=400)

    from gm.client import available

    live = modelcfg.roles()
    local = live.get("narrator", {}).get("host") or "http://localhost:11434"
    return JsonResponse({
        "roles": [{"id": r, "label": label, "why": why, **live.get(r, {})}
                  for r, label, why in modelcfg.ROLES],
        "providers": [{"id": k, **v} for k, v in modelcfg.PROVIDERS.items()],
        "keys": modelcfg.masked(),
        # What Ollama actually has pulled, so the page can offer real names rather
        # than making the player remember a tag.
        "installed": available(local),
    })


@require_POST
def delete_character(request):
    """Remove a character from the roster, on the player's explicit say-so."""
    from . import roster as roster_mod

    body = read_body(request)
    ok, why = roster_mod.retire_file(str(body.get("id", "")).strip())
    if not ok:
        return JsonResponse({"error": why}, status=409)
    return JsonResponse({"ok": True, "message": why})


@require_POST
def create_character(request):
    """Make a character, or say everything wrong with the attempt at once.

    The build is validated end to end — the assembled sheet must load as an Actor before
    anything touches disk — and the finished character goes onto the roster exactly the
    way a pregen does, so everything downstream cannot tell them apart. `begin` starts a
    campaign with them on the spot; without it they wait on the shelf.
    """
    from rules import creation

    from .roster import enrol

    body = read_body(request)
    built, problems = creation.build(body)
    if problems:
        return JsonResponse({"problems": problems}, status=400)

    from rules.sheet import from_dict

    actor = from_dict(built["sheet"], ref="pc")

    # Exactly one enrolment, whichever button was pressed. `begin_with` enrols the
    # character itself, so calling `enrol` first and then `begin_with` put two of them
    # on the roster — and once beginning a game started retiring abandoned starts, the
    # first of the pair was retired on the spot and the campaign ran on the duplicate.
    # "Create & play" therefore reported making a character it had just shelved.
    if body.get("begin"):
        campaign = campaign_mod.begin_with(actor)
        entry_id, begun = campaign.character_id, True
    else:
        entry_id, begun = enrol(actor).id, False

    return JsonResponse({"ok": True, "id": entry_id, "name": actor.name,
                         "warnings": built["warnings"], "begun": begun})
