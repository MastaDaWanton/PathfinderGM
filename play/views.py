"""The play loop, as a browser page.

One turn is: player text -> GM call 1 -> validate -> resolve -> (maybe suspend for a
player roll) -> GM call 2. The dice popup is a real suspension of resolution, not a
cosmetic prompt: the engine is genuinely stopped mid-list until the player answers.
"""
from __future__ import annotations

import json
import re

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from gm import judgement
from gm.agent import GMAgent
from gm.client import ModelUnavailable, available
from rules.intents import IntentError

from . import campaign as campaign_mod
from . import player_input


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
            "in_encounter": c.scene.in_encounter,
            "turn_ref": c.scene.current_ref(),
            "initiative": [
                {"ref": r, "score": v,
                 "name": c.scene.actors[r].name if r in c.scene.actors else r,
                 "up": c.scene.current_ref() == r,
                 "out": not c.scene.conscious(r)}
                for r, v in c.scene.initiative
            ],
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


_TELL_NUMBERS = re.compile(r"\s*\((?=[^)]*\d)[^()]*(?:\([^()]*\)[^()]*)*\)")
_TELL_MARGIN = re.compile(r"\s+by \d+(?=[.,:;]|\s|$)")


def plain_tell(tell: str) -> str:
    """A tell rendered for the player rather than for the log.

    Tells are written by the engine for the GM to narrate, so they carry the arithmetic:
    "the guildhand's attack misses Kesst Vayr (5 against AC 12 (flat-footed))". When the
    narrator is unavailable the tell is shown raw, and that put an NPC's hidden roll in
    front of the player — the one thing the whole hidden/player split exists to prevent.
    """
    text = _TELL_NUMBERS.sub("", tell or "")
    text = _TELL_MARGIN.sub("", text)
    return " ".join(text.split())


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


@require_GET
def sheet(request):
    """The full character sheet, every number with its provenance.

    Fetched on demand rather than shipped with every turn: it is a few kilobytes of
    itemised modifiers that only matter when the player opens the sheet.
    """
    from rules.sheet import full_sheet

    pc = campaign_mod.current().scene.pc()
    if pc is None:
        return JsonResponse({"error": "no character"}, status=404)
    return JsonResponse(full_sheet(pc))


@require_POST
def slots(request):
    """Add, remove or fill a body slot.

    Editing the sheet is not a GM intent — nobody rolls for putting a ring on — so it
    goes straight to the character rather than through the engine.
    """
    from rules.sheet import IllegalSheet, full_sheet

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "no character"}, status=404)

    body = json.loads(request.body or "{}")
    action = str(body.get("action", "")).strip().lower()
    key = str(body.get("slot", "")).strip().lower()

    try:
        if action == "add":
            pc.add_slot(key)
        elif action == "remove":
            pc.remove_slot(key, int(body.get("index", -1)))
        elif action == "set":
            pc.set_slot(key, int(body.get("index", -1)), body.get("item"))
        else:
            return JsonResponse(
                {"error": "action must be add, remove or set"}, status=400
            )
    except KeyError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except IllegalSheet as exc:
        return JsonResponse({"error": str(exc)}, status=409)

    c.save()
    return JsonResponse(full_sheet(pc))


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

    # The player controls one character; the GM controls the world. A turn that declares
    # what the world does is handed back rather than resolved — gently, and without
    # consuming the turn, because the player has not done anything wrong so much as
    # reached across the table.
    said = player_input.check(text)
    if not said.ok:
        return JsonResponse({"hint": said.hint, "offending": said.offending}, status=422)

    c.transcript.append({"who": "player", "text": text})
    world = c.world
    agent = GMAgent(world, c.engine())

    try:
        plan = agent.plan_turn(
            text, c.history, location=c.location,
            recent_events=_recent_events(world, c.location),
            previous_intents=c.last_intent_signature,
            recent_narration=[b["text"] for b in c.transcript[-8:] if b["who"] == "gm"],
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
            text = " ".join(plain_tell(o.tell) for o in outcomes)
        c.transcript.append({"who": "gm", "text": text, "kind": "consequence"})
        c.history.append({"role": "assistant", "content": text})

    if plan is not None:
        _log_turn(c, plan, resolution, replace=True)
    else:
        c.turn_log.append({"kind": "resolution",
                           "outcomes": [o.as_dict() for o in resolution.outcomes]})

    _run_npc_turns(c, agent)
    if plan is not None:
        c.last_intent_signature = judgement._signature(plan.intents)
    c.save()
    return JsonResponse(_state(c))


def _run_npc_turns(c, agent, limit: int = 12) -> None:
    """Let every creature between the player's turns act.

    Initiative used to be rolled and then never consulted: the player could swing, and
    nothing ever swung back. This walks the order, asks the GM to act for each NPC in
    turn, and stops when it comes back round to the player.

    `limit` is a guard against a fight that cannot end — a stalled loop here would hang
    the player's request rather than merely playing badly.
    """
    scene = c.scene
    if not scene.in_encounter or scene.awaiting:
        return

    world = c.world
    location = c.location
    events = _recent_events(world, location)

    for _ in range(limit):
        # A side with nobody standing means the fight is over.
        if scene.sides and scene.sides_standing() <= 1:
            c.transcript.append({"who": "gm", "text": "The fight is over.",
                                 "kind": "consequence"})
            scene.end_encounter()
            return

        ref = scene.advance_turn()
        # Anyone bleeding out at the top of the round gets said out loud. A character
        # losing a hit point a round towards death, silently, is the sort of thing a
        # player finds out about only when they are dead.
        for b in scene.bleeding:
            who = scene.get(b["ref"])
            name = who.name if who else b["ref"]
            line = {
                "dead": f"{name} stops moving.",
                "stable": f"{name} is still down, but the bleeding has stopped.",
                "dying": f"{name} is bleeding out.",
            }[b["outcome"]]
            c.transcript.append({"who": "gm", "text": line, "kind": "consequence"})
        scene.bleeding = []

        if ref is None:
            scene.end_encounter()
            return
        actor = scene.get(ref)
        if actor is None or actor.is_pc:
            return                       # back to the player; stop and wait for input

        engine = c.engine()
        agent.engine = engine
        try:
            plan = agent.npc_turn(ref, location=location, recent_events=events)
        except (ModelUnavailable, IntentError) as exc:
            # A creature the GM could not speak for still acts. It used to "hesitate",
            # which reads as a bug even when it is a fallback: the player was attacked by
            # nobody while a thug stood there. A creature in a fight with an enemy in
            # front of it swings, and the fallback goes through the same validation as
            # anything else.
            c.turn_log.append({"kind": "npc-turn", "ref": ref, "error": str(exc)[:400]})
            fallback = judgement.default_npc_action(scene, ref)
            if not fallback:
                c.transcript.append({"who": "gm", "kind": "consequence",
                                     "text": f"{actor.name} holds back."})
                continue
            try:
                intents = engine.validate(fallback)
                resolution = engine.run(intents)
            except (IntentError, ValueError):
                c.transcript.append({"who": "gm", "kind": "consequence",
                                     "text": f"{actor.name} holds back."})
                continue
            for o in resolution.outcomes:
                if o.tell:
                    c.transcript.append({"who": "gm", "kind": "consequence",
                                     "text": plain_tell(o.tell)})
            continue

        resolution = engine.run(plan.intents)
        if plan.narration:
            c.transcript.append({"who": "gm", "text": plan.narration, "kind": "setup"})

        tells = [o for o in resolution.outcomes if o.tell]
        if tells:
            try:
                text, _ = agent.narrate_outcome(plan.narration, tells, f"{actor.name} acts")
            except ModelUnavailable:
                text = ""
            c.transcript.append({
                "who": "gm", "kind": "consequence",
                "text": text or " ".join(plain_tell(o.tell) for o in tells),
            })
        _log_turn(c, plan, resolution)


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
