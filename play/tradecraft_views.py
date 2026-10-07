"""The trade uses, by button: judge a thing's make, mend it, haggle at a counter, work a
day or a week (rules/tradecraft.py; the owner's options B and C, 2026-10-07).

The same declared intent a spoken turn can plan, by another door — `cast_act`'s pattern
(play/views.py): the op is written here from the button's closed choices, validated, run
with the player's own die, and narrated by `_finish` from the tells. Nothing on this page
writes a number: the DC, the cost, the hours and the pay are the row's.
"""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from gm.agent import GMAgent
from rules.intents import IntentError

from . import campaign as campaign_mod
from .apiutil import read_body

# A question of the trade is not a button: it needs the question, which is the player's
# words, so it comes through a spoken turn (`trade_lore`, planned by the GM).
USES = ("judge", "mend", "work", "haggle")


def _haggle_target(c, body) -> tuple[dict | None, JsonResponse | None]:
    """(the haggle's params and target, or a refusal) — the counter the trade window is
    open at, chosen the way `trade_do` chooses it, so the stall key the haggle writes is
    the one the purchase reads."""
    from rules import keepers as keepers_mod

    from . import views

    pc = c.scene.pc()
    counter, merchant, _at, choices = views._counter_pick(c, line=str(body.get("line") or ""))
    if choices:
        if merchant is None:
            return None, JsonResponse({"error": keepers_mod.shut_here(c.scene) or (
                f"Nobody is at {counter.label} just now.")}, status=409)
        shut = keepers_mod.shut_here(c.scene, merchant)
    else:
        shut = keepers_mod.shut_here(c.scene)
        merchant = views._merchant_here(c.scene)
    if shut:
        return None, JsonResponse({"error": shut}, status=409)
    if merchant is None:
        return None, JsonResponse({"error": "There is nobody here to haggle with."},
                                  status=409)
    refusal = views._counter_refusal(c, pc, merchant)
    if refusal:
        return None, refusal
    _place, stall, _day = views._stall_of(c, counter)
    if counter is None:
        stall = str(body.get("stall") or stall)
    return {"target": merchant.ref, "params": {"stall": stall},
            "label": f"I haggle with {merchant.name}"}, None


@require_POST
def tradeskill_act(request):
    """One trade use, from the Equipment tab, the sheet or the counter."""
    from . import views

    body = read_body(request)
    c = campaign_mod.current()
    scene = c.scene
    pc = scene.pc()
    use = str(body.get("use") or "").strip().lower()
    if use not in USES:
        return JsonResponse({"error": f"use is one of: {', '.join(USES)}"}, status=400)
    refusal = views._cannot_act(pc, {"judge": "look closely at anything",
                                     "mend": "mend anything", "work": "work",
                                     "haggle": "haggle"}[use])
    if refusal:
        return refusal
    if scene.awaiting:
        return JsonResponse({"error": "There is a roll waiting on you."}, status=409)
    if scene.in_encounter:
        return JsonResponse({"error": "Not in the middle of a fight."}, status=409)
    item = " ".join(str(body.get("item") or "").split())[:80]
    # `because` is the dice popup's subtitle: the first cut's "the player's own button" was
    # the system talking on the player's screen (seen live).
    raw: dict = {"actor": pc.ref, "visibility": "player", "params": {},
                 "because": {"judge": "a close look at how it was made",
                             "mend": "mending it", "work": "a day's work at the trade",
                             "haggle": "haggling at the counter"}[use]}
    if use in ("judge", "mend"):
        if not item:
            return JsonResponse({"error": "Which thing?"}, status=400)
        raw.update(op=use, params={"item": item})
        label = (f"I look over the make of my {item}" if use == "judge"
                 else f"I set to mending my {item}")
    elif use == "work":
        days = 7 if str(body.get("days") or "1").strip() == "7" else 1
        skill = str(body.get("skill") or "").strip().lower()
        raw.update(op="work", params={"days": days,
                                      **({"skill": skill} if skill in ("craft",
                                                                       "profession")
                                         else {})})
        label = "I work at my trade for " + ("a week" if days == 7 else "a day")
    else:
        got, refusal = _haggle_target(c, body)
        if refusal:
            return refusal
        raw.update(op="haggle", target=got["target"], params=got["params"])
        label = got["label"]
    engine = c.engine()
    agent = GMAgent(c.world, engine)
    views._arm_cards(agent, c)
    c.transcript.append({"who": "player", "text": label})
    undo = scene.snapshot()
    try:
        resolution = engine.run(engine.validate([raw]))
    except (IntentError, ValueError, KeyError) as exc:
        scene.restore(undo)
        c.transcript.pop()
        return JsonResponse({"error": getattr(exc, "for_a_person", "") or str(exc)},
                            status=400)
    told = " ".join(o.tell for o in resolution.outcomes if o.tell)
    resp = views._finish(c, agent, resolution, "", label, plan=None, hand_over=True,
                         player_text="")
    # The Equipment tab writes the engine's own sentence in its answer line, as it does
    # for Wear (`wear_tell`); a roll still owed has no sentence yet.
    try:
        data = json.loads(resp.content)
    except ValueError:
        return resp
    if isinstance(data, dict) and not resolution.awaiting:
        data["trade_tell"] = told
        return JsonResponse(data, status=resp.status_code)
    return resp


@require_GET
def tradeskill_offer(request):
    """What a day's work pays where the character stands, before any die (the sheet's
    "Earn a living" card), or why there is none here."""
    from rules import places as places_mod
    from rules import pricing, tradecraft

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)
    loc = c.world.get(c.scene.location_id) if (c.world and c.scene.location_id) else None
    if loc is None or places_mod.setting_of(c.scene.at) != "in":
        return JsonResponse({"here": False, "why": (
            "There is no work out here — paid work is found in a settlement.")})
    offer = tradecraft.work_offer(pc, places_mod.scale_of(loc))
    pay = {k: pricing.as_text(v / 100) for k, v in offer["pay_cp"].items()}
    return JsonResponse({"here": True, "town": getattr(loc, "name", ""),
                         "skill": offer["skill"], "ranks": offer["ranks"],
                         "proficiency": offer["proficiency"], "task": offer["task"],
                         "dc": offer["dc"], "scale": offer["scale"], "pay": pay})
