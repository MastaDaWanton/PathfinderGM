"""The region map's hex doors (rules/hexes.py, docs/hexcrawl-plan.md).

`/api/hexes` is the grid a nation's Region map draws: static for a campaign (the stored
layout, the world's ground), so the page asks once per nation, as it asks `/api/atlas` once.
What the party has done on it rides on every state, in `scene.known_places.hexes`
(play/atlas.py).

`/api/hex/move` and `/api/hex/enter` are the board's clicks. They run the engine's own ops
(`hex_move`, `hex_enter`, CODE_ONLY_OPS: a model never writes them), the Perception die is
the player's through the table's popup (stamped `door: "hex"`, so only this door answers
it, the bench's discipline), and the result is told the way the craft panel's excursion is:
the engine's tell, a closing from the table's narrator fed those tells and nothing else
(law three), and the act written into the history so the next spoken turn knows it happened.
"""
from __future__ import annotations

import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from rules.dice import BadDice, Dice
from rules.intents import IntentError

from . import campaign as campaign_mod
from .apiutil import read_body

log = logging.getLogger("pathfindergm")


@require_GET
def hexes_region(request):
    """{"size", "hexes": [{"q", "r", "land", "nation", "ground", "town"}], "towns": {id: [q, r]}}
    for one nation's Region map. `no-store`, for the reason `/api/atlas` is."""
    c = campaign_mod.current()
    e = c.engine()
    g = e.hex_world()
    nation = str(request.GET.get("nation") or "")
    if g is None or nation not in g.nations:
        return JsonResponse({"error": "no such nation on this world's map"}, status=404)
    hexes = [{"q": h["q"], "r": h["r"], "land": h["land"], "nation": h["nation"],
              "ground": h["ground"], "town": h["town"]} for h in g.region(nation)]
    response = JsonResponse({"size": g.size, "hexes": hexes,
                             "towns": {k: list(v) for k, v in g.town_hex.items()}})
    response["Cache-Control"] = "no-store"
    return response


def _tell(c, resolution, line: str) -> JsonResponse:
    """Write the move into the story and the history, and answer the board."""
    from .craft_views import _narrate_outcome

    outcomes = [o for o in resolution.outcomes if o.tell]
    tell = " ".join(o.tell for o in outcomes).strip()
    done = any(o.status != "refused" for o in resolution.outcomes)
    closing = _narrate_outcome(c, "", outcomes, line) if done and outcomes else ""
    c.transcript.append({"who": "player", "text": line})
    if closing:
        c.transcript.append({"who": "gm", "text": closing})
    if tell:
        c.transcript.append({"who": "gm", "kind": "consequence", "text": tell})
    if done and not closing.rstrip().endswith("?"):
        # The endpoint framed, as every turn and the craft excursion end (playtest
        # 2026-11-20 #4: a move ended on the look's line, with no question).
        c.transcript.append({"who": "gm", "text": "What do you do?"})
    pc = c.scene.pc()
    c.history.append({"role": "user", "content": f"(From the region map: {line})"})
    c.history.append({"role": "assistant", "content": " ".join(x for x in (closing, tell) if x)})
    from play import history as history_mod

    c.turn_log.append(history_mod.stamp(c, {
        "kind": "resolution", "door": "hex",
        "outcomes": [o.as_dict() for o in resolution.outcomes]}))
    try:
        from play.views import _remember

        _remember(c, resolution, "")
    except Exception:  # noqa: BLE001 - the ledger is a convenience, never the move
        log.exception("the hex move's ledger note failed")
    c.save()
    return JsonResponse({"tell": tell, "closing": closing,
                         "refused": not done, "pc": pc.name if pc else "",
                         "clock_minutes": c.scene.clock_minutes})


def _answer_roll(c, body):
    """Resume this door's own pending Perception roll with the player's face."""
    if not c.scene.awaiting:
        return None, JsonResponse({"error": "nothing is waiting on a roll"}, status=409)
    if c.scene.awaiting.get("door") != "hex":
        return None, JsonResponse({"error": (
            "The pending roll is not the map's to answer: the table's dice popup has it.")},
            status=409)
    face = body.get("face")
    if face in (None, "", "auto"):
        face = Dice().roll("1d20").raw
    try:
        return c.engine().resume(int(face)), None
    except (ValueError, BadDice) as exc:
        return None, JsonResponse({"error": str(exc)}, status=400)


@require_POST
def hex_move(request):
    """Move the party to a hex on the region map: `{"hex": [q, r]}`, then `{"face": n}`
    for the Perception roll it asks for."""
    body = read_body(request)
    c = campaign_mod.current()
    if c.scene.pc() is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)
    if "face" in body:
        resolution, err = _answer_roll(c, body)
        if err is not None:
            return err
        line = str(c.scene.hexes.pop("pending_line", "") or "I set out across the land.")
        return _tell(c, resolution, line)
    if c.scene.awaiting:
        return JsonResponse({"error": "There is a roll waiting on you."}, status=409)
    try:
        q, r = (int(v) for v in list(body.get("hex") or ())[:2])
    except (TypeError, ValueError):
        return JsonResponse({"error": "hex must be [q, r]"}, status=400)
    e = c.engine()
    g = e.hex_world()
    here = e.party_hex(g) if g is not None else None
    line = "I set out across the land."
    if g is not None and here is not None:
        from rules import hexes

        a, b = g.cell(*here), g.cell(q, r)
        line = (f"I set out {hexes.bearing((a['x'], a['y']), (b['x'], b['y']))} "
                f"across the {b['ground']}.")
    try:
        resolution = e.run(e.validate([{"op": "hex_move", "actor": "pc",
                                         "because": line,
                                         "params": {"hex": [q, r], **(
                                             {"march": True} if body.get("march") is True
                                             else {})}}]))
    except IntentError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    if resolution.awaiting:
        c.scene.awaiting["door"] = "hex"
        c.scene.hexes["pending_line"] = line
        c.save()
        return JsonResponse({"roll": resolution.awaiting})
    return _tell(c, resolution, line)


@require_POST
def hex_enter(request):
    """Go into the spotted site of the hex the party stands in."""
    c = campaign_mod.current()
    if c.scene.pc() is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)
    if c.scene.awaiting:
        return JsonResponse({"error": "There is a roll waiting on you."}, status=409)
    e = c.engine()
    try:
        resolution = e.run(e.validate([{"op": "hex_enter", "actor": "pc",
                                         "because": "the player chose the site on the map",
                                         "params": {}}]))
    except IntentError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    if resolution.awaiting:
        # A venture asks no roll today; if one ever does, it is the table's popup's.
        c.save()
        return JsonResponse({"roll": resolution.awaiting})
    return _tell(c, resolution, "I go in.")
