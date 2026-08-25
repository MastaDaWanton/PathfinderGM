"""The spell builder: one page that authors a whole spell.

Its own module and its own page for the same reason the class builder got one. The form
was a panel inside the spells bench, sharing that page with a 3,040-row browse table —
so authoring a spell meant scrolling past every spell in the game to reach the fields,
and the two halves fought over the same screen.

Everything the page draws comes from the `spells` Kind in `rules/registry.py` and the
vocabularies in `rules/spells.py`. Nothing is written into the template: a spell gaining
a field is one entry in the Kind and it appears here, which is the same bargain the
content benches struck and the only thing that keeps the form and the loader from
drifting apart.

**Starting from an existing spell copies everything except the name.** That is the whole
point of the picker: a homebrew spell is almost always "fireball, but…", and the one
field that must not be inherited is the one that would silently overwrite the original.
"""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from rules import effectspec, registry, spells as spells_mod

# What a spell inherits when it is used as a starting point, and what it does not. The
# name is the exception that matters: copying it would make Save overwrite the spell the
# author was learning from, which is the one mistake a starting-point feature can make
# that loses somebody else's work.
_NOT_INHERITED = ("id", "name")


@ensure_csrf_cookie
@require_GET
def spell_builder(request):
    """The page. Its whole schema and vocabulary go with it, so the form draws once."""
    kind = registry.get("spells")
    return render(request, "play/spellbuilder.html", {
        "state_json": json.dumps({
            "fields": [f.as_dict() for f in kind.fields],
            "vocab": spells_mod.vocabularies(),
            "effects": effectspec.catalogue(),
        }),
    })


@require_GET
def spell_list(request):
    """Every spell, as a starting point picker.

    Name and id only: the picker is a list to choose from, and shipping 3,040 full spells
    to fill a dropdown would be a megabyte to render one select.
    """
    q = str(request.GET.get("q", "")).strip().lower()
    out = []
    for spell in spells_mod.all_spells().values():
        if q and q not in spell.name.lower():
            continue
        out.append({"id": spell.id, "name": spell.name, "school": spell.school,
                    "yours": bool(getattr(spell, "authored", False))})
    out.sort(key=lambda s: s["name"].lower())
    return JsonResponse({"spells": out[:400], "total": len(out)})


@require_GET
def spell_start(request, spell_id: str):
    """One spell as a draft to begin from — everything except its name.

    The name comes back empty rather than absent, so the field is visibly waiting for an
    answer instead of looking like it failed to load. `started_from` travels with it so
    the page can say what is being copied, which is the difference between a form that
    has been filled in and a form that has been filled in *from something*.
    """
    try:
        spell = spells_mod.get(spell_id)
    except KeyError:
        return JsonResponse({"error": f"no spell {spell_id!r}"}, status=404)

    # `vars()` on the dataclass rather than a bespoke serialiser: every field the
    # loader reads is an attribute, and a second copy of that list here would be one
    # more thing to keep level with `Spell`.
    raw = {k: v for k, v in vars(spell).items() if not k.startswith("_")}
    draft = {k: v for k, v in raw.items() if k not in _NOT_INHERITED}
    draft["name"] = ""
    return JsonResponse({"draft": draft, "started_from": spell.name,
                         "started_from_id": spell.id})


@require_POST
def spell_save(request):
    """Write an authored spell to the homebrew folder.

    Validated before anything is written, for the reason the class builder records:
    `rules.spells.all_spells` skips a file it cannot read, so writing a half-valid spell
    is the same as writing one that quietly does not exist.
    """
    body = json.loads(request.body or "{}")
    problems = spells_mod.validate_spell(body)
    if problems:
        return JsonResponse({"error": "; ".join(problems), "problems": problems},
                            status=400)
    try:
        saved = registry.save("spells", body)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    # Drop the cache so the new spell is castable without a restart — the same reason
    # the class builder clears `classes._ALL` after a save.
    spells_mod._ALL = None
    return JsonResponse({"saved": saved if isinstance(saved, dict) else body,
                         "id": body.get("id") or body.get("name", "")})
