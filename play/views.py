"""The play loop, as a browser page.

One turn is: player text -> GM call 1 -> validate -> resolve -> (maybe suspend for a
player roll) -> GM call 2. The dice popup is a real suspension of resolution, not a
cosmetic prompt: the engine is genuinely stopped mid-list until the player answers.
"""
from __future__ import annotations

import json

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from gm.agent import GMAgent
from gm.client import ModelUnavailable, available
from rules.intents import IntentError

from . import campaign as campaign_mod


def _recent_events(world, location, limit=4):
    """A few things this place remembers. Grounding, and a budget — the events that name
    this location, most recent first, undated last."""
    touching = [e for e in world.chronology if location and location.id in e.entity_ids]
    touching.sort(key=lambda e: (e.year is None, -(e.year or 0)))
    return touching[:limit]


def _state(c) -> dict:
    pc = c.scene.pc()
    return {
        "transcript": c.transcript,
        "awaiting": c.scene.awaiting,
        "pc": pc.summary() if pc else None,
        "scene": {
            "location": c.location.name if c.location else "",
            "round": c.scene.round,
            "clock_minutes": c.scene.clock_minutes,
            "actors": [
                {"ref": r, "name": a.name, "hp": a.hp, "hp_max": a.hp_max,
                 "zone": c.scene.zones.get(r, "near"), "is_pc": a.is_pc,
                 "conditions": [x.name for x in a.conditions]}
                for r, a in c.scene.actors.items()
            ],
        },
        # The player sees their own rolls and nobody else's. Hidden rolls are stripped
        # here, at the edge, rather than in the template — a number that never reaches
        # the browser cannot be read out of the page source either.
        "log": [_player_visible_entry(e) for e in c.turn_log[-30:]],
    }


def _player_visible_entry(entry: dict) -> dict:
    """Rebuild a log entry from nothing, keeping only what the player may see.

    Allow-list rather than deny-list. The first version filtered hidden *rolls* out of
    each outcome and shipped everything else — which still sent the GM's raw intents, so
    "the guildhand makes an Acrobatics check" was sitting in the page source even though
    its roll was gone. Stripping named fields leaks whatever you forgot to name; naming
    what to keep does not.

    The server keeps the full entry on disk. This is only what crosses to the browser.
    """
    outcomes = []
    for o in entry.get("outcomes", []):
        rolls = [r for r in o.get("rolls", []) if r.get("visibility") == "player"]
        if not rolls:
            # Nothing of this outcome is the player's. Its tell reaches them through the
            # narration; it does not need a line in the roll log.
            continue
        outcomes.append({
            "op": o.get("op"),
            "verdict": o.get("verdict"),
            "margin": o.get("margin"),
            "because": o.get("because"),
            "dc": o.get("dc"),
            "rolls": rolls,
        })
    return {"kind": entry.get("kind"), "outcomes": outcomes}


@ensure_csrf_cookie
@require_GET
def table(request):
    """The table itself.

    `ensure_csrf_cookie` is load-bearing: the page's JS reads `csrftoken` from
    `document.cookie` to sign its POSTs, and Django only sets that cookie when something
    asks it to. Without this decorator the page renders perfectly and then every single
    turn 403s — found by driving the real HTTP path, not by any test.
    """
    c = campaign_mod.current(reset=request.GET.get("new") == "1")
    return render(request, "play/table.html", {
        "state_json": json.dumps(_state(c)),
        "models": settings.MODELS,
        "ollama_models": available(settings.MODELS["narrator"]["host"]),
    })


@require_GET
def state(request):
    return JsonResponse(_state(campaign_mod.current()))


@require_POST
def say(request):
    """A player turn: GM call 1, validation, resolution."""
    c = campaign_mod.current()
    if c.scene.awaiting:
        return JsonResponse(
            {"error": "There is a roll waiting on you."}, status=409
        )

    text = (json.loads(request.body or "{}").get("text") or "").strip()
    if not text:
        return JsonResponse({"error": "say something"}, status=400)

    c.transcript.append({"who": "player", "text": text})
    world = c.world
    agent = GMAgent(world, c.engine())

    try:
        plan = agent.plan_turn(
            text, c.history, location=c.location,
            recent_events=_recent_events(world, c.location),
        )
    except ModelUnavailable as exc:
        c.transcript.pop()
        return JsonResponse({"error": str(exc)}, status=503)
    except IntentError as exc:
        c.transcript.pop()
        return JsonResponse({"error": f"The GM could not produce a legal turn. {exc}"},
                            status=502)

    return _advance(request, c, agent, plan.narration, plan, text)


@require_POST
def roll(request):
    """The player's answer to the dice popup. Resolution resumes from where it stopped."""
    c = campaign_mod.current()
    if not c.scene.awaiting:
        return JsonResponse({"error": "nothing is waiting on a roll"}, status=409)

    from rules.dice import Dice

    body = json.loads(request.body or "{}")
    prompt = c.scene.awaiting
    notation = prompt.get("die", "1d20")
    low = prompt.get("min", 1)
    high = prompt.get("max", 20)

    face = body.get("face")
    if face is None:
        # The engine rolls it on the player's behalf if they would rather not.
        face = Dice().roll(notation).raw

    face = int(face)
    if not low <= face <= high:
        return JsonResponse(
            {"error": f"{notation} gives a result between {low} and {high}"}, status=400
        )

    engine = c.engine()
    resolution = engine.resume(face)
    narration = c.transcript[-1]["text"] if c.transcript else ""
    player_input = next(
        (t["text"] for t in reversed(c.transcript) if t["who"] == "player"), ""
    )
    agent = GMAgent(c.world, engine)
    return _finish(c, agent, resolution, narration, player_input, plan=None)


def _advance(request, c, agent, narration, plan, player_input):
    engine = agent.engine
    try:
        resolution = engine.run(plan.intents)
    except (IntentError, ValueError) as exc:
        # Validation is meant to cover everything resolution accepts, so reaching here
        # means the two have drifted apart — which has happened once already (a bare
        # string DC). Report it as a rejected turn rather than a 500, and keep the
        # transcript consistent by dropping the player line that never resolved.
        c.transcript.pop()
        return JsonResponse(
            {"error": f"The engine refused the GM's intents: {exc}"}, status=502
        )

    c.transcript.append({"who": "gm", "text": narration, "kind": "setup"})
    c.history.append({"role": "user", "content": player_input})
    c.history.append({"role": "assistant", "content": json.dumps(
        {"narration": narration, "intents": [i.as_dict() for i in plan.intents]}
    )})
    _log_turn(c, plan, resolution)

    if resolution.awaiting:
        c.save()
        return JsonResponse(_state(c))

    return _finish(c, agent, resolution, narration, player_input, plan)


def _finish(c, agent, resolution, narration, player_input, plan):
    if resolution.awaiting:
        c.save()
        return JsonResponse(_state(c))

    outcomes = [o for o in resolution.outcomes if o.tell]
    if outcomes:
        try:
            text, attempt = agent.narrate_outcome(narration, outcomes, player_input)
        except ModelUnavailable:
            # The tell renders raw and play continues. The narrator is a garnish on a
            # game that works without it.
            text, attempt = "", None
        if not text:
            text = " ".join(o.tell for o in outcomes)
        c.transcript.append({"who": "gm", "text": text, "kind": "consequence"})
        c.history.append({"role": "assistant", "content": text})

    if plan is not None:
        _log_turn(c, plan, resolution, replace=True)
    else:
        c.turn_log.append({"kind": "resolution",
                           "outcomes": [o.as_dict() for o in resolution.outcomes]})
    c.save()
    return JsonResponse(_state(c))


def _log_turn(c, plan, resolution, replace: bool = False):
    entry = {
        "kind": "turn",
        "seconds": round(plan.seconds, 1),
        "attempts": [{"kind": a.kind, "seconds": round(a.seconds, 1), "note": a.note}
                     for a in plan.attempts],
        "repairs": plan.repairs,
        "rejections": plan.rejections,
        "intents": [i.as_dict() for i in plan.intents],
        "outcomes": [o.as_dict() for o in resolution.outcomes],
    }
    if replace and c.turn_log and c.turn_log[-1].get("kind") == "turn":
        c.turn_log[-1] = entry
    else:
        c.turn_log.append(entry)
