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
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from gm import (client, intimate as intimate_mod, judgement, ledger as ledger_mod,
                narration as narration_mod, prompts, speech as speech_mod, watcher)
from gm.agent import GMAgent, TurnPlan
from gm.client import ModelUnavailable, available
from rules import biomes, grid, ingredients as ing_mod
from rules import places as places_mod
from rules.intents import IntentError

from . import campaign as campaign_mod
from . import concurrency
from .apiutil import read_body, read_int
from . import downed, gm_answers, player_input, roster
from . import history as history_mod


def _recent_events(world, location, limit=4):
    """A few things this place remembers. Grounding, and a budget.

    The selection and the sort live on `World.events_touching`, which is where the
    export's own quirks belong. This used to filter on `location.id in e.entity_ids`
    directly and returned an empty list for every one of the shipped world's 74
    entities, because the export never fills that field in — so the whole "WHAT THIS
    PLACE REMEMBERS" section of the brief had never once reached the model.
    """
    return world.events_touching(location.id if location else None)[:limit]


def _where_the_ground_is(scene) -> tuple[str, str]:
    """(the place's name, what that kind of place is made of) for the map tray.

    Both read off the same two functions the floorplan itself uses, so the caption can
    never describe a different place from the one drawn.
    """
    from rules import floorplan

    at = str(getattr(scene, "at", "") or "")
    if not at:
        return "", ""
    name = at.rsplit(":", 1)[-1].replace("-", " ").strip()
    try:
        here = places_mod.find(places_mod.for_scene(None, at), at)
        if here is not None and getattr(here, "name", ""):
            name = str(here.name)
    except Exception:      # noqa: BLE001 — a caption is never worth failing a turn over
        pass
    try:
        about = str(floorplan.shape_for(at, places_mod.terrain_of(at)).about or "")
    except Exception:      # noqa: BLE001
        about = ""
    return name, about


def _talk_state(c) -> list[dict]:
    """The conversation as the panel shows it: each person, their step, their regard."""
    from rules import attitude as attitude_mod

    try:
        engine = c.engine()
        return [{"ref": a.ref, "name": a.name,
                 "attitude": attitude_mod.of(a),
                 "regard": attitude_mod.regard_of(a),
                 "regard_max": attitude_mod.REGARD_MAX}
                for a in engine.talking_to()]
    except Exception:      # noqa: BLE001 — a panel line is never worth failing a turn
        return []


def _shown_conditions(a) -> list[str]:
    """The words the panel prints after a person's hit points, and the book's head and the
    combat bar beside them: their conditions, with how they stand towards the player
    taken from the one reader (`attitude.word_for_panel`) rather than from whichever
    attitude CONDITION happens to be on them. The two used to differ: a standing regard
    that put somebody at hostile with no step held showed nothing here while the brief
    and the map read hostile."""
    from rules import attitude as attitude_mod
    from rules import states

    shown = [x.name for x in a.conditions
             if not any(states.matches(t, "attitude") for t in states.tags_for(x.key))]
    word = attitude_mod.word_for_panel(a)
    return shown + ([word] if word else [])


def _busy_state(c) -> str:
    pc = c.scene.pc()
    if pc is None:
        return ""
    try:
        return str(c.engine()._too_busy_to_forage(pc) or "")
    except Exception:      # noqa: BLE001
        return ""


def _where_state(c) -> dict:
    """`scene.where_label`, `where_detail` and `setting`: the panel's "where", read from
    `geography.where` so the panel and (from Lane B) the brief say it one way. Phase 1's
    `where` reproduces today's "{location} · {scale}" and biome exactly."""
    from rules import geography

    try:
        here = c.engine().here()
    except Exception:      # noqa: BLE001 — the label falls back to the settlement alone
        here = None
    try:
        w = geography.where(c.world, c.scene, here)
        return {"where_label": w.label, "where_detail": w.detail, "setting": w.setting}
    except Exception:      # noqa: BLE001 — a panel line is never worth failing a turn
        return {"where_label": "", "where_detail": "", "setting": ""}


def _exits_state(c) -> list[dict]:
    """`scene.exits`: the ways on from here, rebuilt from the engine every state (I6,
    play/exits.py). The model never touches it; [] when there is nowhere to go from."""
    from . import exits as exits_mod

    try:
        return exits_mod.exits(c.engine(), c.world)
    except Exception:      # noqa: BLE001 — a row of buttons is never worth failing a turn
        return []


def _places_found_state(c) -> dict:
    """`scene.places_found`: the fog-of-war place chart (play/places_found.py), rebuilt
    from the engine every state beside the exits row it is read from. {} when there is
    nowhere to chart."""
    from . import places_found

    try:
        return places_found.chart(c.engine(), c.world)
    except Exception:      # noqa: BLE001 — a chart is never worth failing a turn
        import logging

        logging.getLogger("pathfindergm").exception("the places-found chart failed")
        return {}


def _spellcasting_state(pc) -> dict:
    """How the PC casts, for the Spells button (design F §4.4): shown on `kind`, not on
    `pc.castable`, which offers a prepared caster's whole book when nothing is prepared
    (fix-interfaces §1.7 F1). `empty_slots` is Lane E's to fill (§2.10)."""
    from rules import casting

    kind = ""
    if pc is not None and casting.is_caster(pc):
        kind = str(casting.caster_data(pc).get("kind", "") or "")
        if kind not in ("prepared", "spontaneous"):
            kind = ""
    nothing = kind == "prepared" and not any(
        int(n or 0) > 0 for n in (getattr(pc, "prepared", None) or {}).values())
    # The slots a morning left empty, for the sheet's warning (item 21.4) — keyed by the
    # level as a string, the shape §2.10 gives the wire.
    empty = ({str(lvl): int(n) for lvl, n in casting.empty_slots(pc).items()}
             if kind == "prepared" else {})
    return {"kind": kind, "nothing_prepared": bool(nothing), "empty_slots": empty}


def _latest_areas(c) -> list[dict]:
    """`scene.grid.areas`: [{"spell", "cells"}] for the casts of the latest resolved turn,
    or []. A turn with no cast shows none — an area is the turn's ruling, not scenery."""
    for entry in reversed(getattr(c, "turn_log", None) or []):
        if entry.get("kind") not in ("turn", "resolution"):
            continue
        out = []
        for o in entry.get("outcomes") or []:
            if o.get("op") != "cast":
                continue
            for e in o.get("effects") or []:
                area = e.get("area") if e.get("kind") == "cast" else None
                if isinstance(area, dict) and area.get("squares"):
                    out.append({"spell": e.get("spell", ""),
                                "cells": [list(x) for x in area["squares"]]})
        return out
    return []


def _start_state(scene) -> dict:
    """The start this campaign opened with (`Scene.start`, Lane C), or {} before one."""
    start = dict(getattr(scene, "start", None) or {})
    if not start:
        return {}
    return {"id": start.get("id", ""), "kind": start.get("kind", ""),
            "hand_off": start.get("hand_off", {})}


# The conversation panel's budget (§2.10): the people strip and the entries sent with
# every state. Anything older is a `GET /api/conversation` away.
_CONVO_PEOPLE = 30
_CONVO_RECENT = 80


def _involves(entry: dict, ref: str) -> bool:
    """Whether an Entry is in `ref`'s log (design F §4.2): they said it, it was said to
    them, or the player said it while they were in the conversation."""
    return (entry.get("who") == ref or entry.get("to") == ref
            or (entry.get("who") == "you" and ref in (entry.get("among") or [])))


def _conversation_state(c) -> dict:
    """`scene.conversation` from `Scene.conversation_log` (F writes it from Phase 2).

    People are everyone the log names — so the strip is empty until F writes the log,
    whoever is talking — ordered talking, then present, then by their latest entry,
    newest first; `recent` is the last entries involving anybody present or talking."""
    scene = c.scene
    log = [e for e in (getattr(scene, "conversation_log", None) or []) if isinstance(e, dict)]
    seq = int(getattr(scene, "conversation_seq", 0) or 0)
    if not log:
        return {"people": [], "recent": [], "seq": seq}
    try:
        talking = {a.ref for a in c.engine().talking_to()}
    except Exception:      # noqa: BLE001
        talking = set()
    at = str(getattr(scene, "at", "") or "")

    def present(ref: str) -> bool:
        a = scene.actors.get(ref)
        if a is None or a.is_pc or a.has_state("state.hidden"):
            return False
        return not getattr(a, "at", "") or a.at == at

    refs: list[str] = []
    for e in log:
        for r in [e.get("who"), e.get("to")] + list(e.get("among") or []):
            if r and r != "you" and r not in refs:
                refs.append(str(r))
    people = []
    for ref in refs:
        mine = [e for e in log if _involves(e, ref)]
        spoken = [e for e in log if e.get("who") == ref]
        actor = scene.actors.get(ref)
        name = (actor.name if actor is not None
                else next((str(e.get("name") or "") for e in reversed(spoken)), ref))
        people.append({"ref": ref, "name": name, "present": present(ref),
                       "talking": ref in talking, "lines": len(spoken),
                       "last": max((int(e.get("n", 0) or 0) for e in mine), default=0)})
    people.sort(key=lambda p: (not p["talking"], not p["present"], -p["last"]))
    near = {p["ref"] for p in people if p["talking"] or p["present"]}
    recent = [e for e in log if any(_involves(e, r) for r in near)][-_CONVO_RECENT:]
    return {"people": people[:_CONVO_PEOPLE], "recent": recent, "seq": seq}


def _confided_state(c) -> list[dict]:
    """[{"name", "told": [{"label", "text"}], "hinted": bool}] for every person who has
    confided anything, in the order they first did — whether or not they still travel
    with the player: what you were told stays told. The text is their life row's own
    words; nothing here was written by a model. Refs never reach the page."""
    from rules import confiding

    scene = c.scene
    out = []
    for rec in (getattr(scene, "population", None) or {}).values():
        if not isinstance(rec, dict) or not rec.get("confided"):
            continue
        told = [{"label": confiding.LABEL[t], "text": x} for t, x in confiding.told(rec)]
        hinted = any(confiding.stage(rec, t) == confiding.HINTED for t in confiding.TOPICS)
        if not told and not hinted:
            continue
        actor = scene.actors.get(str(rec.get("ref") or ""))
        name = str(getattr(actor, "name", "") or rec.get("phrase") or "").strip()
        if not name:
            continue
        first = min(int(v.get("beat") or 0) for v in rec["confided"].values()
                    if isinstance(v, dict))
        out.append((first, {"name": name, "told": told, "hinted": hinted}))
    return [d for _, d in sorted(out, key=lambda p: p[0])]


def _after_the_beat(c, agent, stage: str, door: str, **fields) -> None:
    """One stage of the after-the-beat steps (play/aftermath, §2.3) over this beat, its
    rows into the turn log — only when there are any, so a turn with no step to run
    writes exactly what it wrote before the registry existed."""
    from .aftermath import context, run as steps

    rows = steps(stage, context(stage, door, c, engine=agent.engine,
                                reading=getattr(agent, "reading", None), **fields))
    if rows:
        c.turn_log.extend(rows)


def _attached_this_turn(c) -> tuple:
    """The attachments on the player's line this turn answers — the last player beat —
    or (). Read off the beat, so a turn resumed by a die roll still carries them."""
    beat = next((b for b in reversed(c.transcript) if b.get("who") == "player"), None)
    return tuple(dict(a) for a in ((beat or {}).get("attachments") or ()))


def _refusal(refusal: dict, status: int = 422):
    """A refusal on the wire (fix-interfaces §2.6, Q4 (a)): HTTP 422 with the player's
    sentence as `error`, beside `{"text", "code", "fix"}`. No beat, no clock, no NPC turn —
    the caller pops the player's line the way the 502 path does. Unused until Lanes A
    and E refuse through it; one shape for both, so the client reads one."""
    text = str((refusal or {}).get("text") or "")
    return JsonResponse({"error": text,
                         "refusal": {"text": text,
                                     "code": str((refusal or {}).get("code") or ""),
                                     "fix": (refusal or {}).get("fix")}},
                        status=status)


@require_POST
def talk_act(request):
    """The conversation's own button: take your leave, or refuse somebody.

    Engine-only, on purpose — no model call, no roll. Everweave's Dialogue Mode is the
    measured warning: exits that needed the model to notice them ended scenes too early
    or not at all. The tell the engine writes goes straight to the page as the GM's
    line, and the next spoken turn's narrator sees it in the outcomes as usual.
    """
    body = read_body(request)
    c = campaign_mod.current()
    scene = c.scene
    pc = scene.pc()
    refusal = _cannot_act(pc, "act")
    if refusal:
        return refusal
    if scene.awaiting:
        return JsonResponse({"error": "There is a roll waiting on you."}, status=409)
    params = {"do": "ignore" if str(body.get("do", "")).lower() == "ignore" else "leave"}
    if body.get("who"):
        params["who"] = str(body.get("who"))
    engine = c.engine()
    undo = scene.snapshot()
    try:
        resolution = engine.run(engine.validate(
            [{"op": "leave_talk", "actor": pc.ref, "because": "the talk panel",
              "params": params}]))
    except (IntentError, ValueError, KeyError) as exc:
        scene.restore(undo)
        return JsonResponse({"error": str(exc)}, status=400)
    tell = " ".join(o.tell for o in resolution.outcomes if o.tell)
    if tell:
        c.transcript.append({"who": "gm", "text": tell})
    c.save()
    return JsonResponse(_state(c))


@require_POST
def cast_act(request):
    """A spell cast from the Spells tab, fight or no fight.

    Reported 2026-09-24: *"I have no way of casting spells outside of combat."* The
    `cast` op never needed a fight — it spends the slot, sets the DC, runs the spell's
    effects — but the only button that offered one was the combat bar, hidden outside an
    encounter. This is the same declared intent by another door: the spell by id, the
    target by ref ("self" for the caster, nothing for a spell with no target), through
    `validate` and `run` and then the narrator, exactly as the combat panel does. In a
    fight it is refused off-turn, as the combat panel would be.
    """
    body = read_body(request)
    c = campaign_mod.current()
    scene = c.scene
    pc = scene.pc()
    refusal = _cannot_act(pc, "cast")
    if refusal:
        return refusal
    if scene.awaiting:
        return JsonResponse({"error": "There is a roll waiting on you."}, status=409)
    if scene.in_encounter and scene.current_ref() != pc.ref:
        return JsonResponse({"error": "It is not your turn."}, status=409)
    spell = str(body.get("spell") or "").strip()
    if not spell:
        return JsonResponse({"error": "Which spell?"}, status=400)
    at = str(body.get("at") or "").strip()
    params = {"spell": spell}
    if at == "self":
        params["at"] = pc.ref
    elif at:
        params["at"] = at
    # Where it is pointed when that is not a person (item 21.2): the same grammar, the
    # same check at the door, as a spell attached to a spoken turn.
    aim = body.get("aim")
    if aim not in (None, ""):
        if not isinstance(aim, str) or not _AIM.match(aim):
            return JsonResponse({"error": _aim_help(aim)}, status=400)
        params["aim"] = aim
    label = str(body.get("label") or f"I cast {spell}").strip()
    engine = c.engine()
    agent = GMAgent(c.world, engine)
    _arm_cards(agent, c)
    c.transcript.append({"who": "player", "text": label})
    undo = scene.snapshot()
    try:
        resolution = engine.run(engine.validate(
            [{"op": "cast", "actor": pc.ref, "because": "the spells tab",
              # The player's own dice, as at the panel (owner, 2026-10-01).
              "visibility": "player", "params": params}]))
    except (IntentError, ValueError, KeyError) as exc:
        scene.restore(undo)
        c.transcript.pop()
        # A refusal the player can fix is the one shape both doors answer in (§2.6):
        # 422, the sentence, and the fix a button can offer.
        if getattr(exc, "fixable_by", "") == "player":
            return _refusal({"text": getattr(exc, "for_a_person", "") or str(exc),
                             "code": exc.code, "fix": exc.fix})
        return JsonResponse({"error": getattr(exc, "for_a_person", "") or str(exc)},
                            status=400)
    # A button's label is not the player's words: "" for the after-the-beat steps.
    return _finish(c, agent, resolution, "", label, plan=None, hand_over=True,
                   player_text="")


def _grid_state(scene) -> dict | None:
    """The map, plus where the PC could actually go — or None when there is no map.

    `reachable` is computed here rather than in the browser because it is the rules'
    answer, not a drawing hint: it already knows about difficult terrain, corners, the
    mover's size and everybody standing in the way. Recomputing it in JavaScript would
    mean two implementations of the diagonal rule, and the one on screen would be the one
    the player believes.
    """
    if scene.grid is None:
        return None
    g = scene.grid
    out = {
        "width": g.width, "height": g.height,
        "difficult": sorted(g.difficult), "blocked": sorted(g.blocked),
        "obscuring": sorted(g.obscuring),
        # The vertical, which the page could not see at all until now: stages 4 and 5b
        # gave rooms raised ground, roofs and rails, and every one of them stopped at
        # this function. A gallery was drawn on the server, saved, measured and fought
        # over, and the map showed a flat floor.
        #
        # Sent in the same shape as the terrain sets — sorted lists of small integer
        # tuples — because that shape is renderer-agnostic on purpose. A three-
        # dimensional view reads exactly this; it is the flat map that is the special
        # case, not the other way round.
        "floor": [[c, r, v] for (c, r), v in sorted(g.floor.items())],
        "parapet": [[c, r, v] for (c, r), v in sorted(g.parapet.items())],
        "ceiling": g.ceiling,
        # Every level anything is actually on, so the view can offer exactly those and
        # not a spinner from zero to the sky. Ground is always in it: a room with a
        # gallery still has a floor.
        "levels": sorted({0} | set(g.floor.values())
                         | {p[2] for p in scene.positions.values() if len(p) > 2}),
        "reachable": [],
    }
    # WHERE this ground is. The tray said "The ground" and nothing else, so a player
    # looking at a correct map of one place while the prose described another had no way
    # to tell which of the two was lying — reported 2026-09-21 as "i am at a gate with
    # wagons passing through ... this map is completely wrong", where the engine held the
    # party at the well and drew the well faithfully. The shape's own `about` line already
    # says what the place is made of; it had simply never been shown to anybody.
    out["place"], out["about"] = _where_the_ground_is(scene)
    pc = scene.pc()
    if pc is not None and pc.ref in scene.positions and pc.can_act():
        routes = g.reachable(scene.positions[pc.ref], pc.speed_feet, size=pc.size,
                             occupied=scene.occupied(ignore=pc.ref))
        # The level each destination stands at, carried alongside the cost, because a
        # square is only half of where somebody would end up — walking onto a dais is
        # walking up onto it, and the map has to be able to say which squares those are.
        out["reachable"] = [[c, r, cost, g.ground((c, r))]
                            for (c, r), cost in sorted(routes.items())]
        out["speed"] = pc.speed_feet
    return out


def _attack_slots(pc) -> dict:
    """The shape of this character's full attack, and whether abilities may stand in.

    Replacement is Blood Bond's clause — "Abilities can replace each attack action
    within a standard action or a full-round action" — so it is keyed off the class
    having paths, the same fact the ability buttons key off.
    """
    if pc is None:
        return {"sequence": [], "weapon": "", "replaceable": False}
    from rules.tables import iterative_attacks

    # Every weapon a swing may declare. The armament is not a separate entry any
    # more: `Actor.weapon` makes it ride every unarmed strike while it is formed, so
    # "unarmed" already means the armament strike when the toggle is on. The extra
    # slot only exists so somebody holding a sword can still choose their fists.
    weapons = [pc.equipped or "unarmed"]
    if pc.has_condition("blood armament") and (pc.equipped or "unarmed") != "unarmed":
        weapons.append("unarmed")
    return {
        "sequence": iterative_attacks(pc.bab),
        "weapon": (pc.equipped or "unarmed"),
        "weapons": weapons,
        "replaceable": bool(getattr(pc, "paths", None)),
    }


def _usable_abilities(pc) -> list[dict]:
    """What this character can use right now, path by path.

    Only at or below the tier they have reached, because an ability is not theirs
    because the class prints it somewhere — and a button for one they cannot use is a
    button that exists to be refused.
    """
    if pc is None or not getattr(pc, "paths", None):
        return []
    from rules import leveling

    out = []
    for path in pc.paths:
        det = leveling.path_detail(pc.char_class or "", path)
        reached = leveling.control_blood_for(pc, path)
        passives = {str(n).lower() for n in (det.get("passive") or [])}
        for tier, names in sorted((det.get("tiers") or {}).items()):
            for name in names:
                # A passive is not "usable": Swift Strikes sat on this bar as a button,
                # and clicking it stood in for the attack it exists to modify.
                if name.lower() in passives:
                    continue
                if int(tier) <= reached:
                    key = (det.get("resolves") or {}).get(name, "")
                    entry = {"name": name, "path": path, "tier": int(tier),
                             "text": (det.get("abilities") or {}).get(key, "")}
                    # A toggle's button must say whether it holds — that confusion is
                    # the reason toggles exist as a concept at all.
                    cond = (det.get("toggles") or {}).get(name)
                    if cond:
                        entry["toggle"] = True
                        entry["active"] = pc.has_condition(str(cond))
                    out.append(entry)
    return out


def _state(c) -> dict:
    pc = c.scene.pc()
    from rules import attitude as attitude_mod
    from rules import cards as cards_mod
    from rules import goods as goods_mod
    from rules import houserules as houserules_mod
    from rules import residency
    from rules import schemes as schemes_mod

    coins = goods_mod.coinage(c.world, c.location)

    def with_areas(grid):
        # The latest turn's spell areas, for the map's overlay (§2.10): the cells each
        # cast's area covered, read off the last resolved turn in the log, so the map
        # shows the ruling the engine made and the player can dispute it the way a table
        # would (docs/design-e-magic.md §3.1).
        if grid is not None:
            grid["areas"] = _latest_areas(c)
        return grid

    return {
        "transcript": c.transcript,
        # The world's own name, for the title bar. Reported 2026-09-18 with a screenshot:
        # "why does the shell say Pangrella when I'm playing in Aurvantis?" — the table's
        # <title> was the shipped world's name, typed into the template.
        "world": c.world.name if c.world else "",
        # What money is called here. Sent with the state because it is a fact about the
        # world, not a constant: a purse rendered with hard-coded "gp" would be the one
        # thing on the page that had never heard of the world it is being played in.
        "coinage": [{"id": x.id, "name": x.name, "plural": x.plural,
                     "copper": x.copper, "coined": x.coined} for x in coins],
        "suggestions": list(getattr(c, "suggestions", []) or []),
        # The quest log: the tasks taken up, their objectives ticked or not, and the
        # ones finished — read off the situation cards of kind quest.
        "quests": cards_mod.quest_log(c.scene),
        # The schemes running, for the table's own eyes only when the house rule says
        # so — what fired, what was skipped and why, what news is on its way.
        "schemes": (schemes_mod.gm_view(c.scene) if houserules_mod.gm_view() else None),
        # Whether the trade panel would open, decided here so the button and the
        # endpoint cannot disagree — the rule lives in `_merchant_here` and nowhere else.
        "merchant": (_merchant_here(c.scene).name if _merchant_here(c.scene) else ""),
        "awaiting": c.scene.awaiting,
        "pc": pc.summary() if pc else None,
        "scene": {
            "location": c.location.name if c.location else "",
            # What kind of place this is, in the words the opening and the brief use.
            # Reported 2026-09-22 after four sessions in one town: "I have never been
            # aware that vormoor was a village." The panel is where a fact like this
            # has to live to stay known — an opening is read once.
            "scale": (places_mod.scale_of(c.location) if c.location else ""),
            "what_it_is": (places_mod.what_it_is(places_mod.scale_of(c.location))
                           if c.location else ""),
            "biome": c.biome,
            "biome_describe": biomes.describe(c.biome),
            "round": c.scene.round,
            "in_encounter": c.scene.in_encounter,
            # Who the player is in conversation with, and how each stands towards
            # them — the talk panel (2026-09-24). The number is the player's to see;
            # the narrator only ever hears the word.
            "talk": _talk_state(c),
            # Why the crafting hub is shut right now, or "": the engine's own sentence,
            # so the greyed button and the refusal behind it cannot disagree.
            "busy": _busy_state(c),
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
                 # Which side of the fight, or "" for a bystander the fight has not
                 # touched — the map paints foes red and bystanders white.
                 "side": next((s for s, refs in (c.scene.sides or {}).items()
                               if r in refs), ""),
                 # How the map paints them — pc, ally, foe or "" — from the attitude
                 # track, the one source the panel's word and the brief read too
                 # (`attitude.stance`). The map used to paint from `side`, which a
                 # fight's end empties: an hour after the robbers won, neither was red.
                 "stance": attitude_mod.stance(c.scene, a),
                 "size": a.size, "squares": grid.size_squares(a.size),
                 # A crowd held as one actor: how many are still standing out of how many
                 # arrived, so the token can say "17 of 24" and read as many people rather
                 # than one big creature (item 33). Absent for every ordinary creature.
                 **({"members": int(a.troop.members),
                     "members_max": int(a.troop.members_max)}
                    if getattr(a, "troop", None) is not None else {}),
                 "at": list(c.scene.positions[r]) if r in c.scene.positions else None,
                 # Whether the combat bar may offer a coup de grâce. Asked here of the
                 # vocabulary so the browser never matches condition names; the dead
                 # are past finishing.
                 "helpless": bool(a.is_helpless
                                  and not a.has_state("state.down.dead")),
                 "conditions": _shown_conditions(a)}
                for r, a in c.scene.actors.items()
                if a.is_pc or not a.has_state("state.hidden")
            ],
            "grid": with_areas(_grid_state(c.scene)),
            # Blood on the ground. Sent whether or not there is a grid: without one
            # they are still a count the player needs, because half the class spends
            # them.
            "pools": [b.as_dict() for b in c.scene.pools if b.here(c.scene)],
            # The keys of the 2026-09-28 fix pass (docs/fix-interfaces.md §2.10), every
            # one at its default until the lane that owns its value lands: the panel's
            # "where" in words, the conversation log (F), the part of the day (the clock
            # pop-up's caption and the log's dividers).
            **_where_state(c),
            "conversation": _conversation_state(c),
            "day_part": residency.day_part(c.scene.clock_minutes),
            # The "From here" row (I6): every way on, from the engine's own graph, with
            # the ones the rules would refuse greyed in the rules' own words.
            "exits": _exits_state(c),
            # The Places chart (owner, 2026-09-29): every place the player has stood in
            # and every place one way from them, by name, with the ways between; the
            # rest of the town stays under the fog.
            "places_found": _places_found_state(c),
            # The Journal's notes and maps, and whether there is ink and paper to write
            # more with (2026-10-01).
            "writings": _writings_state(c),
            # What companions have told the player about their own lives (gm/confide.py),
            # for the Journal: known to the player, so shown; a hint shown as a hint.
            "confided": _confided_state(c),
        },
        # The abilities this character can use right now, for the row of buttons under
        # the transcript. Sent with the state because reaching a tier changes it.
        "abilities": _usable_abilities(pc),
        # What a full attack is made of, for the combat panel's slot builder. The
        # penalties are the display; the engine recomputes them from the same table
        # when the swing actually happens.
        "attacks": _attack_slots(pc),
        # The player sees their own rolls and nobody else's. Hidden rolls are stripped
        # here, at the edge, rather than in the template — a number that never reaches
        # the browser cannot be read out of the page source either.
        "log": [_player_visible_entry(e) for e in c.turn_log[-30:]],
        # How the PC casts, for the Spells button (F), and the slots a rest left empty (E).
        "spellcasting": _spellcasting_state(pc),
        # The start this campaign opened with (C): its id, kind and hand-off.
        "start": _start_state(c.scene),
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
        # On an opposed check the number to beat IS the other side's hidden roll, and the
        # Rolls panel printed it: "Stealth check 25 vs 3", the guard's secret Perception,
        # measured live 2026-10-01 building the verdict flourish. The popup has withheld it
        # since `dc_shown`; the log has to as well, and the margin with it, which is the
        # same number by subtraction. A target that is no hidden die's result still shows.
        hidden = {r.get("total") for r in o.get("rolls", [])
                  if r.get("visibility") != "player"}
        dc = o.get("dc")
        secret = isinstance(dc, dict) and dc.get("value") in hidden
        outcomes.append({
            "op": o.get("op"),
            "verdict": o.get("verdict"),
            "margin": None if secret else o.get("margin"),
            "because": o.get("because"),
            "dc": None if secret else dc,
            "rolls": rolls,
        })
    return {"kind": entry.get("kind"), "outcomes": outcomes}



def _end_campaign(c, pc) -> None:
    """The campaign is over for this character. The character is not deleted."""
    epitaph = next((b["text"] for b in reversed(c.transcript)
                    if b["who"] == "gm" and b.get("kind") == "consequence"), "")
    if c.character_id:
        roster.bury(c.character_id, pc, epitaph=epitaph[:300])
    c.ended = "died"
    c.scene.end_encounter()


def _ended_payload(c) -> dict:
    pc = c.scene.pc()
    return {
        "ended": c.ended,
        "death": downed.death_notice(pc) if pc else "",
        "choices": roster.pregens(),
        "roster": [e.summary() for e in roster.everyone()],
        # Death is a debt, not a wall: somebody in this world can pay to have the
        # character raised, and the button that says so lives on the death screen.
        "resurrectable": c.ended == "died" and pc is not None,
    }


@require_POST
def resurrect(request):
    """Weeks later, on a cold slab: somebody paid the priests to pull you back.

    The player's own design, in their words: "if the character dies they should be
    fast forwarded into the future where some person has paid to resurrect them
    because they needed their strength." So death stays real — the fight was lost,
    the epitaph stands in the roster — and the continuation is a debt: time passes
    on the world clock, a patron drawn from the world's own factions foots the
    bill, and a clockless `life debt` condition (state.obligation.life-debt) sits
    on the sheet for the world to call in. Engine first, prose second, like every
    other turn: the mechanics land here, and the narrator dresses the tell.
    """
    from rules.dice import Dice

    c = campaign_mod.current()
    if c.ended != "died":
        return JsonResponse({"error": "nobody here needs raising"}, status=409)
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "the body is not in the scene"}, status=409)

    # The mechanics, all through the ordinary applicators. `dead` is named here and
    # nowhere else: this is the only caller entitled to remove it, which is why it is
    # not in the `recovery.hit-points` family that heal, rest and the downed resolution
    # share — one list covering all four would either break resurrection or let cure
    # light wounds raise a corpse.
    pc.remove_condition("dead")
    pc.clear_states("recovery.hit-points")
    pc.nonlethal = 0

    factions = [f.get("name") for f in (c.world.factions or [])
                if isinstance(f, dict) and f.get("name")]
    dice = Dice(c.seed)
    patron = (factions[dice.roll("1d%d" % len(factions), visibility="hidden").total - 1]
              if factions else "a stranger whose face you never see")
    days = 7 + dice.roll("2d10", label="days lost", visibility="hidden").total
    # Between nine and twenty-seven days pass, the largest jump in the app, and nothing
    # used to expire in them. Through the one door now — which is also why the hit
    # points are restored AFTER it rather than before: an effect holding up the
    # maximum can expire inside those weeks, and setting hp first left a character
    # above a maximum that had since fallen.
    c.scene.advance(days * 24 * 60)
    pc.hp = pc.hp_max
    pc.add_condition("life debt", source=patron)

    c.scene.end_encounter()
    # The fight that killed them is long over and far away; the bodies stay there.
    # The STORE, and through the destroyer: this walked the view with a raw `pop`
    # that bypassed every side table, and under containment the view is not everyone.
    # A clean slate is what the old dict meant when the dict was everyone.
    for ref in [r for r, a in list(c.scene.people.items()) if not a.is_pc]:
        c.scene.remove(ref)

    c.ended = ""
    if c.character_id:
        roster.revive(c.character_id, pc)
    beat = (f"{days} days pass in a darkness you do not remember. You wake on a "
            f"cold slab under temple vaulting, lungs pulling their first borrowed "
            f"breath: {patron} paid the priests to bring you back — they needed "
            f"your strength, and they mean to collect. The debt sits on you like "
            f"a second skin.")
    c.transcript.append({"who": "gm", "text": beat, "kind": "setup"})
    c.history.append({"role": "assistant", "content": beat})
    c.save()
    return JsonResponse({**_state(c), "resurrected": True, "patron": patron,
                         "days": days})


@require_GET
def alive(request):
    """A window saying it is still open. The only endpoint that is about the process.

    Every page loads `js/keepalive.js`, which calls this on a timer; `desktop.py` shuts
    the server down when the calls stop. It exists because the packaged exe otherwise
    outlives the browser it opened — measured 2026-09-01, two processes still holding
    port 8917 and a handle on their own `.exe` four hours after the last request. The
    reasoning, the prior art and the three designs that were refused are in
    `pathfindergm/liveness.py`.

    Deliberately the cheapest view in the app: no campaign is loaded, no save is
    touched, nothing is drained. It runs every fifteen seconds forever and must never
    become a reason for a request log to be unreadable or for a turn to be slower.

    The interval is answered rather than hard-coded in the page, so the two halves
    cannot drift apart — CLAUDE.md's "when you fix a rule, grep for every copy of it",
    settled by not having a second copy.
    """
    from pathfindergm import liveness

    liveness.touch()
    response = JsonResponse({"ok": True, "every": liveness.PING_SECONDS})
    # A cached heartbeat is a heartbeat that stops reaching the server while the page is
    # still on screen, which would end a live game. Say so rather than rely on the fact
    # that no browser caches an XHR by default today.
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def game_revision(request):
    """How many times the game has moved, and nothing else.

    The whole second-device channel. A view that is behind re-fetches `/api/state`
    through the path it already uses; this only ever answers whether it needs to.

    Cheap on purpose, and exempt from the game lock on purpose — `play/concurrency.py`
    carries both reasons. The short one: a GM turn holds the lock for up to ninety-five
    seconds, and a device that could not read this number until the turn finished could
    not tell it was waiting rather than broken.
    """
    response = JsonResponse({"revision": concurrency.revision()})
    # Same reasoning as the heartbeat above: a cached answer here is a device that never
    # learns the game moved, which is the exact failure this endpoint exists to prevent.
    response["Cache-Control"] = "no-store"
    return response


def _only_this_machine(request):
    """Refuse anything that did not come from the desktop's own browser, or None.

    The three views below decide whether the app listens to the network at all, so a
    request that arrived *over* the network must never be able to work them. Two reasons,
    and either alone would be enough: a phone that could close the door could lock the
    desktop out of its own game, and `lan.close_the_door()` waits for its server's loop
    to come back round — called from a request that server is currently serving, that is
    a deadlock rather than an error.
    """
    from pathfindergm import lan

    if lan._from_this_machine(request):
        return None
    return JsonResponse({"error": "Only the machine running the game can change this."},
                        status=403)


@require_GET
def lan_status(request):
    """Whether the table is reachable from the network, and the code that reaches it."""
    from pathfindergm import lan

    refusal = _only_this_machine(request)
    return refusal or JsonResponse(lan.status())


@require_POST
def lan_open(request):
    """Start listening on the network. The button in Settings, and `--lan` at launch."""
    from pathfindergm import lan

    refusal = _only_this_machine(request)
    if refusal:
        return refusal
    try:
        return JsonResponse(lan.open_the_door())
    except OSError as exc:
        # A bind can fail for reasons the player can act on — a firewall policy, a
        # machine with no network at all — and a 500 with a traceback tells them none of
        # them. Same rule as everywhere else in this file: refuse in words.
        return JsonResponse(
            {"error": f"Could not start listening on the network: {exc}"}, status=503)


@require_POST
def lan_close(request):
    """Stop listening, and make the pass worthless."""
    from pathfindergm import lan

    refusal = _only_this_machine(request)
    return refusal or JsonResponse(lan.close_the_door())


@require_GET
def characters(request):
    """Everyone who has been played, and everyone available to play."""
    c = campaign_mod.current()
    return JsonResponse({
        "playing": c.character_id,
        "ended": c.ended,
        "roster": [{**e.summary(), "playable": e.playable(),
                    "current": e.id == c.character_id}
                   for e in roster.everyone()],
        "choices": roster.pregens(),
    })


@require_POST
def switch_character(request):
    """Play somebody else who is already on the roster.

    Their campaign resumes where it stopped rather than starting over — one campaign per
    character is what makes that possible.
    """
    body = read_body(request)
    character_id = str(body.get("id", "")).strip()
    # The start picker's path (Q20), used only when this begins an unplayed character's
    # campaign; see `campaign.switch_to`.
    start_town = str(body.get("start_town") or "").strip() or None
    start_id = str(body.get("start_id") or "").strip() or None
    try:
        c = campaign_mod.switch_to(character_id, start_town=start_town, start_id=start_id)
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    return JsonResponse(_state(c))


@require_POST
def new_character(request):
    """Retire the campaign and begin again with somebody else.

    The old campaign is archived rather than deleted, and the dead character stays on
    the roster — a character who died in the second session is the reason the third one
    went the way it did.
    """
    body = read_body(request)
    source = str(body.get("source", "")).strip()
    try:
        character = roster.from_pregen(source)
    except FileNotFoundError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    # In the SAME world. Reported 2026-09-18: "clicking any of the premade characters
    # as a player start puts you in Pangrella instead of the world you chose." This is
    # the table page's picker; the home page's start passes the chosen world's source
    # and this one passed nothing, so `new_campaign` filled it with the shipped
    # default. Beginning again with somebody else is not leaving the world.
    try:
        staying = campaign_mod.current().world_source
    except Exception:  # noqa: BLE001 — no readable campaign means no world to keep
        staying = None
    c = campaign_mod.begin_with(character, world_source=staying or None)
    return JsonResponse(_state(c))


@ensure_csrf_cookie
@require_GET
def table(request):
    """The table itself.

    `ensure_csrf_cookie` is load-bearing: the page's JS reads `csrftoken` from
    `document.cookie` to sign its POSTs, and Django only sets that cookie when something
    asks it to. Without this decorator the page renders perfectly and then every single
    turn 403s — found by driving the real HTTP path, not by any test.

    **The model gate lives here, not only on the two API doors that lead here.**
    `/api/start` and `/api/resume` were gated first, and driving the real UI showed
    that a returning player reaches none of them: the front page's Continue is a plain
    `<a href="/play/">`, because the campaign is already current and there is nothing to
    switch to. So the commonest path into play walked straight past both checks. This is
    the one door every path goes through — the two links, a bookmark, and the redirect
    after either API call — and it is the reason the check is at the destination rather
    than at the approaches. `/craft/` is deliberately not gated: the benches need no
    model and refusing them would be refusing work the app can do.
    """
    from . import preflight

    if not preflight.check().ok:
        return redirect("/?setup=1")
    try:
        # No `?new=1`. It archived the campaign and started another from a GET, which
        # CSRF does not cover and the server sits on a fixed port: measured 2026-09-25,
        # `<img src="http://127.0.0.1:8917/play/?new=1">` on any page the player visited
        # reset their game. Nothing in the app linked to it — new games begin on the
        # shelf, by POST — so the door is gone rather than moved.
        c = campaign_mod.current()
    except campaign_mod.UnreadableSave:
        # Back to the shelf, which now survives this and says why. The refusal itself
        # stands — `current()` still raises, nothing is repaired behind the player's
        # back, and the save is untouched — but a bookmark straight to `/play/` must
        # not be a dead end. See `home_views.home` for the measurement.
        return redirect("/?unreadable=1")
    return render(request, "play/table.html", {
        "state_json": json.dumps(_state(c)),
        # For the <title>, which read "Pangrella" in Aurvantis (2026-09-18).
        "world_name": c.world.name if c.world else "",
        # The revision the state below was drawn at, handed over with it rather than
        # fetched afterwards. A page that had to ask would race its own first render:
        # between the two requests another device can act, and the answer would then
        # describe a state this page is not showing — so the page would either resync
        # for no reason or, worse, believe it was current when it was not.
        "revision": concurrency.revision(),
        "models": settings.MODELS,
        "ollama_models": available(settings.MODELS["narrator"]["host"]),
    })


@require_GET
def state(request):
    c = campaign_mod.current()
    # Anything the event watcher decided while the player was thinking lands here, on
    # the request thread, against the live state — never from the watcher's own thread,
    # which would race the save. Not while a roll is suspended: resolution is genuinely
    # stopped mid-list, and nothing else may move underneath it.
    #
    # The one mutating GET in the app, and so the one place the revision has to be moved
    # by hand: `OneGameAtATime` counts successful *unsafe* requests, and this is neither.
    # Without the bump, a second device would sit on a stale screen until somebody
    # happened to act — the watcher's work is exactly the kind that arrives while nobody
    # is touching the phone. `drain` already answers whether it changed anything.
    if not c.scene.awaiting:
        if watcher.drain(c):
            concurrency.bump()
    return JsonResponse(_state(c))


@require_GET
def history(request):
    """The character's history for the Journal (`play/history.py`): how it began, then
    one line per thing that happened, by day where the log can say. Reads only, like
    `conversation`."""
    return JsonResponse(history_mod.history(campaign_mod.current()))


@require_GET
def conversation(request):
    """One person's conversation log, or everybody's, a page at a time (§2.10).

    `with` is a ref or "all"; `before` an entry number to page back from; `limit` at most
    200. Answers `{"entries": [...], "more": bool}`, oldest first, `more` when older
    entries remain. A ref the log never names answers an empty page, not an error: the
    panel's "Earlier…" list may hold somebody the log has since let go. Reads only —
    unlike `state`, it drains nothing, so paging back through history never moves the game.
    """
    c = campaign_mod.current()
    who = str(request.GET.get("with") or "all").strip() or "all"
    q = request.GET
    before = read_int(q, "before", 0)
    limit = read_int(q, "limit", 50, lo=1, hi=200)
    log = sorted((e for e in (getattr(c.scene, "conversation_log", None) or [])
                  if isinstance(e, dict)), key=lambda e: int(e.get("n", 0) or 0))
    if who != "all":
        log = [e for e in log if _involves(e, who)]
    if before > 0:
        log = [e for e in log if int(e.get("n", 0) or 0) < before]
    page = log[-limit:]
    return JsonResponse({"entries": page, "more": len(log) > len(page)})


@require_GET
def sheet(request):
    """The full character sheet, every number with its provenance.

    Fetched on demand rather than shipped with every turn: it is a few kilobytes of
    itemised modifiers that only matter when the player opens the sheet.
    """
    pc = campaign_mod.current().scene.pc()
    if pc is None:
        return JsonResponse({"error": "no character"}, status=404)
    return JsonResponse(_sheet_payload(pc))


def _sheet_payload(pc) -> dict:
    """`full_sheet`, plus the Equipment tab's one list of everything carried.

    Every door that hands the page a sheet back (`/api/sheet`, `/api/slots`, `/api/use`)
    goes through here, so the Equipment tab never redraws from a sheet that lacks its
    list: `/api/use` returning the bare `full_sheet` would have emptied the page the
    moment a jar was drunk from it."""
    from rules import gear as gear_mod
    from rules.sheet import full_sheet

    out = full_sheet(pc)
    out["equipment"]["carried"] = _carried(pc)
    # What is carried against what can be (CRB Table 7-4), with the backpack's +1 Str
    # (content/rules/gear.json). Shown, not enforced: encumbrance is the owner's later
    # batch (E9), and the Equipment tab says so in words.
    out["equipment"]["load"] = gear_mod.load(pc)
    # The Companions line on the Background card: an animal companion made by nature
    # bond, its numbers derived from the druid's level (rules/animal_companion.py). The
    # sheet printed "No animal companion, familiar, cohort or mount" as a fixed sentence
    # until 2026-10-04, whatever the character had. And the domain powers had, with
    # what each one does not do yet, said out loud.
    from rules import animal_companion, domains as domains_mod

    try:
        scene = campaign_mod.current().scene
    except Exception:  # noqa: BLE001 — a sheet with no campaign still draws
        scene = None
    out["companions"] = {
        "animals": animal_companion.sheet_lines(scene, pc),
        "absent": animal_companion.wanted_but_absent(scene, pc),
        "not_yet": list(animal_companion.document().get("not_yet") or [])}
    out["domain_powers"] = domains_mod.power_lines(pc)
    return out


def _use_menu(stock, item_id: str) -> list[dict]:
    """The Use button's places for one jar: each route it works through, what it does
    there in the engine's own words, and the body `/api/use` takes for it. Only places
    with something that lands (`consumables.routes_of`), so a tincture offers "Drink it"
    and nothing else, and an eye salve offers the eyes and a wound."""
    from rules import consumables, effectspec
    from rules.ingredients import route_of

    out = []
    for route in consumables.routes_of(stock):
        label = consumables.ROUTE_USE[route][0]
        lines = [effectspec.render(sp) for sp in (stock.specs or [])
                 if route_of(sp) == route and str(sp.get("type")) != "save_gate"]
        body = ({"item": item_id, "how": "drink"} if route == "ingest" else
                {"item": item_id, "how": "apply", "route": route})
        out.append({"route": route, "label": label, "line": "; ".join(lines),
                    "body": body})
    return out


def _use_targets(pc) -> list[dict]:
    """Who a jar can be put on: the character, then everybody here who would let them,
    which is anybody not hostile and not dead. The downed are offered on purpose: a
    poultice bound on an unconscious friend is the commonest use of one (plan §7)."""
    from rules import states

    out = [{"ref": "pc", "name": "Yourself"}]
    try:
        scene = campaign_mod.current().scene
    except Exception:  # noqa: BLE001 — a sheet with no campaign still draws
        return out
    for ref, a in scene.actors.items():
        if a is pc or getattr(a, "is_pc", False):
            continue
        if a.has_state("state.down.dead") or states.attitude_of(a) == "hostile":
            continue
        out.append({"ref": ref, "name": a.name})
    return out


def _carried(pc) -> list[dict]:
    """Everything the character carries, one row a thing, for the Equipment tab.

    The table rebuild's stage 2 (the owner's approved design, docs/mock/table-layout/,
    "What changed in the second pass", point 1): what you carry, filed on the trade
    window's shelves (`SHELVES`, by `_shelf_of`'s rules, so a potion is a consumable in
    the pack and at the counter alike), whether it is in hand or worn, which slot it
    fits, and what can be done to it, each act naming the real door that does it. The
    page adds nothing: an act is offered only where the door would take it.

    The engine keeps a carried thing in five places, and this reads all five:
    `weapons` (drawn with the engine's `wear` op), `goods` (armour and shields bought,
    put on with the same op, and whatever the fiction handed over), `stock` (a counter's
    bought gear and crafted jars: drunk, thrown or coated through `/api/use`, a made
    cloak put on through `/api/wear`), the armour and shield worn (`armour`, `shield`),
    and names written into a body slot (`/api/slots`).

    What the engine cannot do is not offered, and a row with no act says why in words
    (2026-09-30, item 2 part U). A weapon's Wield asks `weapons.wieldable` — the same
    function `_op_wear` asks — so the button is there exactly when the op would take it;
    before, the button asked `goods.kind_of` and 348 of the 356 weapons the smith sold
    came up "The rules cannot put this in hand by name yet". Armour and a shield worn have
    Take off (the `take_off` op), the weapon in hand Put away (wield `unarmed`), and
    ammunition is a counted row of its own that the launcher's row names. There is still
    no drop op (a later batch, owner's ruling E6).
    """
    from rules import armour as armour_mod
    from rules import gear as gear_mod
    from rules import goods, magicitem, weapons as weapons_mod
    from rules.sheet import _stock_row
    from rules.tables import ARMOUR, SHIELDS, SLOTS

    magic = {e.name.strip().lower(): e for e in magicitem.catalogue().values()
             if e.slot and e.slot in SLOTS}
    # Every name written in a body slot, and which slot holds it.
    worn: dict[str, str] = {}
    for key, line in (pc.slots or {}).items():
        for w in line or ():
            if w:
                worn[str(w).strip().lower()] = key

    def free_line(slot: str) -> int | None:
        line = pc.slot_list(slot)
        return next((i for i, w in enumerate(line) if not w), None)

    def by_name(name: str, slot: str) -> list[dict]:
        """Wear a thing by writing its name in its slot: how a bought wondrous item goes
        on, the catalogue joining the name to its effects (`magicitem.worn_specs`)."""
        at = free_line(slot)
        if at is None:
            return []
        return [{"label": "Wear", "api": "/api/slots",
                 "body": {"action": "set", "slot": slot, "index": at, "item": name}}]

    def slot_full(slot: str) -> str:
        return (f"The {SLOTS[slot]['label'].lower()} slot is full; empty a line of it "
                f"first.")

    rows: list[dict] = []
    seen: set[str] = set()

    # Weapons: one row a kind, counted, by the one key however the list spelled it.
    held = weapons_mod.key_for(pc.equipped or "") or (pc.equipped or "").strip().lower()
    counts: dict[str, int] = {}
    for w in pc.weapons or ():
        k = weapons_mod.key_for(w) or str(w or "").strip().lower()
        if k and k != "unarmed" and not weapons_mod.is_ammunition(k):
            counts[k] = counts.get(k, 0) + 1
    if held and held != "unarmed" and held not in counts:
        counts[held] = 1
    # Whether a suit can change now (owner's ruling E2): only out of a fight. Asked of the
    # running campaign, and only when this sheet IS its character — a roster preview has
    # no fight around it.
    # Read off the campaigns already in memory, never `current()`, which would load or
    # even make one for a sheet that only wants drawing.
    in_fight = any(getattr(c, "scene", None) is not None and c.scene.pc() is pc
                   and c.scene.in_encounter
                   for c in list(getattr(campaign_mod, "_LIVE", {}).values()))
    for key, n in counts.items():
        name = weapons_mod.get(key)["name"] if weapons_mod.has(key) else key
        seen.add(key)
        seen.add(str(name).lower())
        # The op's own question, asked of the same function (`weapons.wieldable`), and
        # then the one the op asks of the actor: a two-handed weapon with a shield on
        # (owner's ruling E4).
        can, why = weapons_mod.wieldable(key) if weapons_mod.has(key) else (
            False, "The rules have no weapon by that name.")
        if can and key != held:
            why = armour_mod.hands_clash(pc, weapon_key=key)
            can = not why
        families = weapons_mod.ammo_families(key) if weapons_mod.has(key) else []
        supply = goods.ammo_carried(pc, families) if families else []
        line = ""
        if families:
            left = sum(r["count"] for r in supply)
            line = (f"shoots {families[0]}: {left} carried" if left
                    else f"shoots {families[0]}, and none are carried")
        acts = []
        if key == held:
            acts = [{"label": "Put away", "api": "/api/wear",
                     "body": {"item": "unarmed", "op": "wield"}}]
        elif can:
            acts = [{"label": "Wield", "api": "/api/wear",
                     "body": {"item": key, "op": "wield"}}]
        rows.append({
            "id": f"weapon:{key}", "key": key, "name": name, "count": n, "unit": "",
            "kind": "weapon", "shelf": "weapons", "fits": "hand",
            "state": "in hand" if key == held else "",
            "line": line, "known": weapons_mod.has(key),
            "launcher": bool(families),
            "acts": acts,
            "note": "" if acts else why,
        })

    # Ammunition: a counted row each, spent by the launcher that shoots it. Never in hand.
    for name, n in sorted((pc.goods or {}).items()):
        if int(n or 0) <= 0 or not weapons_mod.is_ammunition(name):
            continue
        key = weapons_mod.key_for(name)
        fam = weapons_mod.family_of(key)
        seen.add(str(name).strip().lower())
        seen.add(key)
        shooters = [k for k in counts if fam and fam in weapons_mod.ammo_families(k)]
        rows.append({
            "id": f"ammo:{key}", "key": key,
            "name": re.sub(r"\s*\(\d+[^)]*\)\s*$", "", weapons_mod.get(key)["name"]),
            "count": int(n), "unit": "", "kind": "ammunition", "shelf": "weapons",
            "fits": "", "state": "", "known": True,
            "line": (f"{int(n)} {weapons_mod.round_name(key, int(n))}, spent one a shot"
                     + (f" from the {weapons_mod.get(shooters[0])['name'].lower()}"
                        if shooters else "")),
            "acts": [],
            "note": ("Loosed from a launcher, never held: wield the "
                     + (weapons_mod.get(shooters[0])["name"].lower() if shooters
                        else f"launcher that shoots {fam or 'these'}")
                     + " and every shot spends one."),
        })

    # Armour and shields: carried in `goods`, and the ones being worn.
    for table, kind, attr, slot in ((ARMOUR, "armour", "armour", "armor"),
                                    (SHIELDS, "shield", "shield", "shield")):
        on = str(getattr(pc, attr, "none") or "none").strip().lower()
        stored = {goods.canonical(k): k for k in (pc.goods or {})
                  if goods.kind_of(k) == kind}
        keys = list(stored)
        if on != "none" and on not in keys:
            keys.append(on)
        for key in keys:
            if key not in table or key == "none":
                continue
            e = table[key]
            seen.add(key)
            seen.add(str(e["name"]).lower())
            seen.add(str(stored.get(key, key)).strip().lower())
            cost = armour_mod.change_cost(kind, key, off=key == on)
            acts, note = [], ""
            if key == on:
                if kind == "armour" and in_fight:
                    note = (f"Taking it off takes {cost['said']}: not in the middle of a "
                            f"fight. Only a shield comes off mid-fight.")
                else:
                    acts = [{"label": "Take off", "api": "/api/wear",
                             "body": {"item": key, "op": "take_off"}}]
            elif kind == "armour" and in_fight:
                note = (f"Putting it on takes {cost['said']}: not in the middle of a "
                        f"fight.")
            else:
                clash = armour_mod.hands_clash(pc, shield_key=key) if kind == "shield" else ""
                if clash:
                    note = clash
                else:
                    acts = [{"label": "Wear", "api": "/api/wear",
                             "body": {"item": key, "op": "wear"}}]
            rows.append({
                "id": f"{kind}:{key}", "key": key, "name": e["name"],
                "count": int((pc.goods or {}).get(stored.get(key, key), 0) or 0) or 1,
                "unit": "", "kind": kind, "shelf": "armour", "fits": slot,
                "state": "worn" if key == on else "", "line": "", "known": True,
                "armour": {"ac": e["ac"], "acp": e["acp"], "max_dex": e.get("max_dex"),
                           "weight": e.get("weight", ""), "asf": e.get("asf"),
                           "lb": e.get("lb"),
                           "proficient": armour_mod.proficient_with(pc, kind, key),
                           "takes": cost.get("said", "")},
                "acts": acts,
                "note": note,
            })

    # Whatever the fiction handed over: counted, described by the engine, and honest
    # about which of them it has rules for.
    for name, n in sorted((pc.goods or {}).items()):
        low = str(name).strip().lower()
        if low in seen or goods.kind_of(name) in ("armour", "shield"):
            continue
        seen.add(low)
        item = magic.get(low)
        slot = item.slot if item else ""
        kind = goods.kind_of(name)
        shelf = ("magic" if item else "weapons" if kind == "weapon"
                 else "consumables" if kind == "consumable" or low in _food_names()
                 else "valuables" if _VALUABLE.search(name) else "gear")
        on = worn.get(low, "")
        acts = by_name(name, slot) if slot and not on else []
        _, row = gear_mod.row_for(name)
        acts += _gear_acts(row, name)
        rows.append({
            "id": f"goods:{low}", "key": low, "name": name, "count": int(n or 0),
            "unit": goods.unit_for(name), "kind": kind, "shelf": shelf, "fits": slot,
            "state": "worn" if on else "", "line": goods.describe(name, int(n or 0)),
            "known": goods.known_item(name) is not None or item is not None or bool(row),
            "acts": acts, "note": (slot_full(slot) if slot and not on and not acts
                                   else _gear_note(row)),
        })

    # A counter's bought gear and the bench's jars.
    for _, s in sorted((pc.stock or {}).items(), key=lambda kv: kv[1].name.lower()):
        d = _stock_row(s)
        low = str(d["name"]).strip().lower()
        seen.add(low)
        item = magic.get(low) or magic.get(str(s.base).strip().lower())
        on = worn.get(low, "")
        slot = (d.get("slot") or "") if d.get("wearable") else (item.slot if item else "")
        acts = []
        # Drink, throw and coat only for a thing that is for that. `_stock_row` asks the
        # consumables planner, which answers "ok" for any jar with nothing harmful in it,
        # so a bought hooded lantern came up drinkable (measured 2026-09-30 on the
        # Equipment tab: "Hooded lantern ... Drink"). A maker's stated `how`, real effect
        # specs, or the consumables and magic shelves are what make a thing usable here.
        shelf = _shelf_of(s)
        usable = bool(d.get("how")) or bool(s.specs) or shelf in ("consumables", "magic")
        # Use: where it goes, chosen (the owner, 2026-10-02: "a use button for products
        # that lets you choose based on the ingredient/products tagged places"). One
        # button whose menu offers only the places this jar works and what it does in
        # each, and who it can go on; it replaces Drink, which is its "Drink it" line.
        menu = _use_menu(s, d["id"]) if usable and s.specs else []
        # A jar that only goes down the throat keeps its plain Drink button: a menu
        # whose one line is "Drink it" is a second click for nothing.
        if menu and len(menu) == 1 and menu[0]["route"] == "ingest":
            menu = []
        if menu:
            acts.append({"label": "Use", "api": "/api/use", "menu": menu,
                         "targets": _use_targets(pc),
                         "body": dict(menu[0]["body"])})
        for how, label in (("drink", "Drink"), ("throw", "Throw"), ("coat", "Coat")):
            if menu and how == "drink":
                continue
            if usable and d.get(f"{how}able"):
                acts.append({"label": label, "api": "/api/use",
                             "body": {"item": d["id"], "how": how}})
        if slot and not on:
            if d.get("wearable"):
                acts.append({"label": "Wear", "api": "/api/wear",
                             "body": {"item": d["id"]}})
            else:
                acts += by_name(d["name"], slot)
        effects = [str(x) for x in (d.get("effects") or []) if x]
        # What a bought bedroll or tent does, from its gear row (content/rules/gear.json):
        # a counter's goods land here as jars with no specs, and every one of the owner's
        # nine read "for show, no effect in play" until 2026-10-01.
        _, row = gear_mod.row_for(s.base)
        if row and not effects:
            effects = [str(row.get("does") or "")]
        if row:
            # A thing with a gear row is used the way its row says, never drunk: trail
            # rations are on the consumables shelf (the name says "rations") and
            # `consumables.plan` answers "ok" to drinking any jar with nothing harmful in
            # it, so they came up with a Drink button.
            acts = [a for a in acts if a["label"] not in ("Drink", "Throw", "Coat")]
        acts += _gear_acts(row, d["id"])
        rows.append({
            "id": f"stock:{d['id']}", "key": d["id"], "name": d["name"],
            "count": int(d.get("count") or 0), "unit": goods.unit_for(d["name"]),
            "kind": "wearable" if slot else "consumable" if d.get("how") or any(
                d.get(f"{h}able") for h in ("drink", "throw", "coat")) else "gear",
            "shelf": "magic" if item and _shelf_of(s) == "gear" else _shelf_of(s),
            "fits": slot, "state": "worn" if on else "",
            "line": "; ".join(effects),
            "known": bool(effects) or bool(s.specs) or bool(item) or bool(row),
            "poisons": bool(d.get("poisons")),
            "acts": acts,
            "note": slot_full(slot) if slot and not on and not any(
                a["label"] == "Wear" for a in acts) else _gear_note(row),
        })

    # A name written in a slot that is none of the above: worn, and recorded.
    for low, slot in worn.items():
        if low in seen or slot in ("armor", "shield"):
            continue
        name = next(str(w) for w in pc.slot_list(slot) if w and str(w).strip().lower() == low)
        item = magic.get(low)
        rows.append({
            "id": f"slot:{low}", "key": low, "name": name, "count": 1, "unit": "",
            "kind": "slot", "shelf": "magic" if item else "gear", "fits": slot,
            "state": "worn", "line": "", "known": item is not None,
            "acts": [], "note": "",
        })
    return rows


WRITING_MAX_CHARS = 4000


def _writings_state(c) -> dict:
    """`scene.writings`: what has been written, newest last, and whether the pack holds
    what writing takes (`gear.can_write`), with the reason when it does not."""
    from rules import gear as gear_mod

    pc = c.scene.pc()
    can, why = gear_mod.can_write(pc) if pc is not None else (False, "")
    return {"pages": [dict(w) for w in c.scene.writings], "can_write": can, "why": why}


def _map_lines(c) -> tuple[str, list[str]]:
    """A drawn map, in words: the places stood in and the ways out of each, as the
    fog-of-war chart knows them right now (`places_found.chart`) — the engine's own
    graph, never the model's. (title, lines)."""
    from . import places_found

    chart = places_found.chart(c.engine(), c.world) or {}
    names = {n["id"]: n["name"] for n in chart.get("nodes") or ()}
    lines = []
    for n in chart.get("nodes") or ():
        if not n.get("visited"):
            continue
        ways = []
        for e in chart.get("edges") or ():
            if e["from"] == n["id"] and e["to"] in names:
                ways.append(f"{names[e['to']]} ({e['time_words']})" if e.get("time_words")
                            else names[e["to"]])
        for r in chart.get("roads") or ():
            if r["from"] == n["id"]:
                ways.append(f"the road to {r['name']}")
        lines.append(f"{n['name']}{' (here)' if n.get('current') else ''}: "
                     + (", ".join(ways) if ways else "no way out known"))
    where = str(chart.get("where") or "") or "where you have been"
    return f"Map of {where}", lines


@require_POST
def write(request):
    """Write a note or draw a map, with ink and paper (the owner, 2026-10-01: "ink and
    paper allow me to write notes or draw maps using ink and paper").

    A player action on their own property, so straight to the scene like `/api/slots`:
    nothing for a model to decide. Refused, with the reason, when the pack holds no ink
    and paper (`gear.can_write`, the gear row's `writes`). A note is the player's words,
    kept as written; a map is the engine's chart of the places stood in and the ways
    between, as they are known at the moment it is drawn. Neither reaches the narrator.
    """
    from rules import gear as gear_mod

    body = read_body(request)
    c = campaign_mod.current()
    pc = c.scene.pc()
    refusal = _cannot_act(pc, "write")
    if refusal:
        return refusal
    can, why = gear_mod.can_write(pc)
    if not can:
        return JsonResponse({"error": why}, status=400)
    kind = str(body.get("kind") or "note").strip().lower()
    page = {"kind": kind, "clock": int(c.scene.clock_minutes or 0), "at": str(c.scene.at or "")}
    if kind == "map":
        title, lines = _map_lines(c)
        if not lines:
            return JsonResponse({"error": "There is nothing to draw yet: no place has been "
                                          "stood in."}, status=400)
        page.update(title=str(body.get("title") or "").strip()[:120] or title, lines=lines)
    elif kind == "note":
        text = str(body.get("text") or "").strip()
        if not text:
            return JsonResponse({"error": "Write something first."}, status=400)
        page.update(title=str(body.get("title") or "").strip()[:120],
                    text=text[:WRITING_MAX_CHARS])
    else:
        return JsonResponse({"error": "A page is a note or a map."}, status=400)
    try:
        page["where"] = c.engine().here().name
    except Exception:
        page["where"] = ""
    c.scene.writings.append(page)
    c.save()
    return JsonResponse({"ok": True, "writings": _writings_state(c)})


def _gear_acts(row: dict | None, item_id: str) -> list[dict]:
    """The Equipment row's buttons a gear row earns: Eat, for food (the `eat` op with the
    item named, through `/api/use`). Nothing else a row says is a button: a bedroll and a
    tent do their work when you sleep, a backpack while you carry it."""
    if row and row.get("eat"):
        return [{"label": "Eat", "api": "/api/use", "body": {"item": item_id, "how": "eat"}}]
    return []


def _gear_note(row: dict | None) -> str:
    """Where a gear row's effect happens, when it is not a button on this row."""
    if not row:
        return ""
    if row.get("writes"):
        return "Write a note or draw a map from the Journal tab."
    if row.get("camp") or "gear.bedding" in (row.get("tags") or ()):
        return "Works when you sleep out on the ground."
    return ""


@require_POST
def slots(request):
    """Add, remove or fill a body slot.

    Editing the sheet is not a GM intent — nobody rolls for putting a ring on — so it
    goes straight to the character rather than through the engine.
    """
    from rules.sheet import IllegalSheet

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "no character"}, status=404)

    body = read_body(request)
    action = str(body.get("action", "")).strip().lower()
    key = str(body.get("slot", "")).strip().lower()

    try:
        if action == "add":
            pc.add_slot(key)
        elif action == "remove":
            pc.remove_slot(key, read_int(body, "index", -1))
        elif action == "set":
            pc.set_slot(key, read_int(body, "index", -1), body.get("item"))
        else:
            return JsonResponse(
                {"error": "action must be add, remove or set"}, status=400
            )
    except KeyError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except IllegalSheet as exc:
        return JsonResponse({"error": str(exc)}, status=409)

    c.save()
    return JsonResponse(_sheet_payload(pc))


@require_GET
def manual(request):
    """The manual, for the person who installed the exe rather than the repository.

    Served from inside the app for the same reason the licence is: this ships as a single
    executable, and a document sitting in a GitHub repository the player never opens is
    not a manual they have. It is the only copy — a second one in the repo would drift
    from this within a month, which is CLAUDE.md's "grep for every copy of it" applied
    before there is a second copy to grep for. `README.md` links here rather than
    repeating any of it.

    **Every count on the page is read from the catalogue that holds it.** The README this
    was written alongside had claimed for months that character creation, combat, attacks
    of opportunity, the world-state agent and packaging were "deliberately not built yet",
    long after all five shipped. A manual that lists features from memory is the first
    document in a project to become a lie, so this one cannot: if a class is added the
    number moves, and if the spells fail to load the page fails loudly rather than
    quoting a number nobody checked.
    """
    from pathlib import Path

    from django.conf import settings as dj_settings

    from pathfindergm import version
    from rules import (backgrounds, bestiary, classes, feats, places, races, schemes,
                       spells)

    from . import library, preflight
    from .craft_views import DISCIPLINES

    wanted = preflight.needs()
    shipped = [w.name for w in library.worlds() if w.shipped]
    return render(request, "play/manual.html", {
        "build": version.build(),
        "models": [{
            "model": n.model,
            "size": preflight.gb(n.bytes_estimate),
            # The jobs in the words the settings page uses for them, not the role ids.
            "roles": ", ".join(_ROLE_WORDS.get(r, r) for r in n.roles),
            "required": n.required,
        } for n in wanted],
        "total_download": preflight.gb(sum(n.bytes_estimate for n in wanted)),
        "disk_wanted": preflight.gb(sum(n.bytes_estimate for n in wanted)
                                    + preflight.DISK_HEADROOM),
        "shipped_worlds": _and_list(shipped),
        # The verb agrees with however many worlds the build actually ships, which is
        # one today and is a number, not a constant.
        "shipped_verb": "ships" if len(shipped) == 1 else "ship",
        "classes": len(classes.all_classes()),
        "races": len(races.all_races()),
        "backgrounds": len(backgrounds.catalogue()),
        "quests": len(schemes.all_schemes()),
        # Read from the table that holds them, like every other number on this page.
        "keepers": len(places.STAFFED),
        "feats": f"{len(feats.all_feats()):,}",
        "spells": f"{len(spells.all_spells()):,}",
        "creatures": f"{len(bestiary.everything()):,}",
        "disciplines": _and_list([d["name"] for d in DISCIPLINES]),
        "data_dir": Path(dj_settings.CAMPAIGN_DIR).parent,
    })


# The four jobs, in the words a player would use. `modelcfg.ROLES` carries the long
# explanation for the settings page; the manual wants the short name.
_ROLE_WORDS = {"narrator": "writes the scene", "prose": "says what the dice did",
               "watcher": "watches the world", "fallback": "backup narrator"}


def _and_list(names: list[str]) -> str:
    """"a", "a and b", "a, b and c" — so the prose reads whatever the catalogue holds."""
    names = [str(n) for n in names if n]
    if not names:
        return "nothing"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


@require_GET
def licence(request):
    """The Open Game Licence, verbatim.

    Section 10: "You MUST include a copy of this License with every copy of the Open Game
    Content You Distribute." This app ships as a single executable, so the licence has to
    be reachable from inside it rather than sitting beside the source — served as plain
    text so nothing can reflow or truncate it on the way to the reader.

    Read off `resource_root()` rather than `__file__`, because under PyInstaller `__file__`
    points inside the bundle and says nothing about where the app was installed.
    """
    from django.http import HttpResponse, HttpResponseNotFound

    from pathfindergm.paths import resource_root

    path = resource_root() / "OGL.txt"
    if not path.is_file():
        # Loud rather than blank: a build that lost the licence is one that must not be
        # distributed, and an empty page would look like a styling bug.
        return HttpResponseNotFound(
            "OGL.txt is missing from this build. The Open Game Licence must ship with "
            "any copy of the Open Game Content — see OGL-NOTICE.md.",
            content_type="text/plain; charset=utf-8",
        )
    return HttpResponse(path.read_text(encoding="utf-8"),
                        content_type="text/plain; charset=utf-8")


@require_POST
def level_up(request):
    """Take the next level, and say exactly what it was worth.

    The hit points are rolled through the campaign's own dice so the number lands in
    the turn log with every other roll the app makes — a level that quietly added seven
    hit points would be the one figure on the sheet nobody could account for.
    """
    from rules import leveling

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)

    result = leveling.level_up(pc, dice=c.engine().dice)
    if not result.get("ok"):
        return JsonResponse({"error": result.get("why", "cannot level")}, status=409)

    bits = [f"{pc.name} reaches level {result['level']}.",
            f"Hit points: rolled {result['rolled']}"
            + (f" {result['con']:+d} Con" if result['con'] else "")
            + f" = {result['hp']} ({pc.hp}/{pc.hp_max})."]
    if result["grants"]:
        bits.append("Gains: " + ", ".join(result["grants"]) + ".")
    c.transcript.append({"who": "gm", "text": " ".join(bits), "kind": "consequence"})
    # The row the docstring above has always promised and nothing wrote until 2026-10-01:
    # the level, the roll and what it granted — and the Journal's history reads it.
    c.turn_log.append(history_mod.stamp(c, {
        "kind": "level-up", "level": int(result["level"]), "rolled": result.get("rolled"),
        "hp": result.get("hp"), "grants": list(result.get("grants") or [])}))
    if c.character_id:
        roster.record(c.character_id, pc)
    c.save()
    return JsonResponse({**_state(c), "levelled": result})


@require_GET
def level_feat_menu(request):
    """The feats this character may take for what their levels owe: `?pool=feats|bonus`.

    The forge's list (`creation.feat_rows`) asked of the living character — open ones
    first, the shut ones with the missing prerequisite named — narrowed for a class's
    bonus feats to what they may be (a fighter's combat feats).
    """
    from rules import leveling

    pc = campaign_mod.current().scene.pc()
    if pc is None:
        return JsonResponse({"error": "no character"}, status=404)
    pool = str(request.GET.get("pool") or "feats").strip().lower()
    if pool not in ("feats", "bonus"):
        return JsonResponse({"error": "pool is 'feats' or 'bonus'"}, status=400)
    return JsonResponse(leveling.feat_menu(pc, pool))


@require_POST
def level_take_feats(request):
    """Take owed feats: `{"pool": "feats"|"bonus", "feats": [id | {"id", "target"}]}`.

    The server is the rule — owed, qualified for, not already held, inside a class's
    bonus-feat list — every reason refused at once and nothing written unless all pass.
    """
    from rules import leveling
    from rules.sheet import full_sheet

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "no character"}, status=404)
    body = read_body(request)
    wanted = body.get("feats")
    if not isinstance(wanted, list):
        return JsonResponse({"error": "send the chosen feats as a list"}, status=400)
    pool = str(body.get("pool") or "feats").strip().lower()
    added, problems = leveling.take_feats(pc, wanted, pool)
    if problems:
        return JsonResponse({"error": " ".join(problems), "problems": problems},
                            status=400)
    c.transcript.append({"who": "gm", "kind": "consequence",
                         "text": f"{pc.name} takes {', '.join(a.title() for a in added)}"
                                 f"{' as a bonus feat' if pool == 'bonus' else ''}."})
    if c.character_id:
        roster.record(c.character_id, pc)
    c.save()
    return JsonResponse({**full_sheet(pc), "taken": added})


@require_POST
def level_take_points(request):
    """Place owed ability points: `{"points": {"str": 1, "con": 1}}`.

    Through `Actor.grow_ability`, so a Constitution point pays every Hit Die already
    earned. Both of a house rule's points may land on one score.
    """
    from rules import leveling
    from rules.sheet import full_sheet

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "no character"}, status=404)
    body = read_body(request)
    changes, problems = leveling.take_points(pc, body.get("points"))
    if problems:
        return JsonResponse({"error": " ".join(problems), "problems": problems},
                            status=400)
    said = ", ".join(f"{ch['ability'].title()} +{ch['amount']} (now {ch['score']})"
                     for ch in changes)
    hp = sum(ch["hp_change"] for ch in changes)
    c.transcript.append({"who": "gm", "kind": "consequence",
                         "text": f"{pc.name}: {said}."
                                 + (f" {hp:+d} hit points." if hp else "")})
    if c.character_id:
        roster.record(c.character_id, pc)
    c.save()
    return JsonResponse({**full_sheet(pc), "raised": changes})


@require_GET
def feat_search(request):
    """Browse the feat index, ranked by whether this character can actually take it.

    Three buckets rather than a flat list, because "you qualify", "you are short by two
    points of Strength" and "this one asks for something the sheet cannot check" are three
    different answers and collapsing them loses the only useful part.
    """
    from rules import feats as feats_mod

    pc = campaign_mod.current().scene.pc()
    found = feats_mod.search(
        text=request.GET.get("q", ""),
        kind=request.GET.get("type", ""),
        source=request.GET.get("source", ""),
        tag=request.GET.get("tag", ""),
        # `read_int`, not `int()`: "?limit=many" was a 500 (2026-09-25).
        limit=read_int(request.GET, "limit", 60, lo=1, hi=500),
    )

    out = []
    for feat in found:
        row = feat.as_dict()
        if pc is not None:
            verdict = feats_mod.meets(pc, feat)
            row["qualifies"] = verdict["ok"]
            row["unmet"] = verdict["unmet"]
            row["unknown"] = verdict["unknown"]
            row["held"] = feat.id in feats_mod._held(pc)
        out.append(row)

    return JsonResponse({
        "feats": out,
        "counts": feats_mod.meta().get("counts", {}),
        "licence": feats_mod.meta().get("licence", ""),
    })


@require_POST
def prepare_spells(request):
    """Prepare, unprepare, or add a spell to the book.

    Preparing is not a GM intent — nobody rolls for choosing what to memorise over
    breakfast — so it goes straight to the character, the same way body slots do.

    The refusals here are the same set `_check_cast` uses, applied a step earlier. Letting
    a wizard prepare a spell they cannot cast would put it on the sheet looking available
    and fail only when they reached for it in a fight.
    """
    from rules import casting, spells as spells_mod
    from rules.sheet import full_sheet

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "no character"}, status=404)
    if not casting.is_caster(pc):
        return JsonResponse({"error": f"{pc.name} does not cast spells"}, status=400)

    body = read_body(request)
    action = str(body.get("action", "prepare")).strip().lower()
    spell_id = str(body.get("spell", "")).strip().lower()
    count = read_int(body, "count", 1, lo=1)

    try:
        spell = spells_mod.get(spell_id)
    except KeyError:
        return JsonResponse({"error": f"no spell {spell_id!r}"}, status=404)

    level = casting.spell_level_for(pc, spell)
    if action in ("prepare", "learn"):
        if level is None:
            return JsonResponse(
                {"error": f"{spell.name} is not on the "
                          f"{casting.caster_data(pc).get('list', 'caster')} list"},
                status=400)
        if level > casting.highest_spell_level(pc):
            return JsonResponse(
                {"error": f"{spell.name} is level {level}; {pc.name} reaches level "
                          f"{casting.highest_spell_level(pc)}"}, status=400)
        if not casting.can_cast_level(pc, level):
            ability = casting.casting_ability(pc)
            return JsonResponse(
                {"error": f"a level {level} spell needs {ability.title()} "
                          f"{10 + level}"}, status=400)

    if action == "learn" and casting.learning(pc)["kind"] == "known":
        # A repertoire is bounded by its Spells Known table, and the tab's Learn button
        # took any castable spell with no count at all — D&D Beyond's "I was able to add
        # every first level spell" bug. Through the same check the level-up picker uses.
        added, problems = casting.learn(pc, [spell.id])
        if problems:
            return JsonResponse({"error": " ".join(problems), "problems": problems,
                                 "spell": spell.id}, status=400)
    elif action == "learn":
        if spell.id not in pc.spellbook:
            pc.spellbook.append(spell.id)
    elif action == "forget":
        pc.spellbook = [s for s in pc.spellbook if s != spell.id]
        casting.unprepare(pc, spell.id, 99)
    elif action == "prepare":
        if not casting.knows(pc, spell):
            return JsonResponse(
                {"error": f"{spell.name} is not in {pc.name}'s spellbook"}, status=400)
        # Counted against the OPEN slots of that level (`casting.open_slots`): the ones
        # not spent today, less what is already prepared. A wizard cannot memorise five
        # fireballs into two slots, and cannot refill a slot spent today before a rest
        # (CRB, "Preparing Wizard Spells"). This read slots-per-day minus held until
        # 2026-09-29, and let Ysolde prepare Burning Hands again into the slot her cast
        # had just spent. The refusal is the sentence the Spells tab shows beside the
        # disabled button, in plain words, with `level` so the page can place it.
        refused = casting.prepare_refusal(pc, level, count)
        if refused:
            return JsonResponse({"error": refused, "level": level,
                                 "spell": spell.id}, status=409)
        casting.prepare(pc, spell.id, count)
    elif action == "unprepare":
        casting.unprepare(pc, spell.id, count)
    else:
        return JsonResponse(
            {"error": "action must be learn, forget, prepare or unprepare"}, status=400)
    # What the player chose is what the mornings refill (`casting.ensure_prepared`).
    if action in ("prepare", "unprepare", "forget"):
        casting.remember_loadout(pc)

    c.save()
    return JsonResponse(full_sheet(pc))


@require_GET
def learnable_spells(request):
    """The spells this caster may write in for the levels they have gained.

    The owner, 2026-10-01: "leveled up as a wizard and did not choose new spells". The
    sheet carries only the count (`spells.to_learn`); the candidates come here when the
    picker opens, because a wizard's whole castable list runs to hundreds.
    """
    from rules import casting

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "no character"}, status=404)
    return JsonResponse({
        "to_learn": casting.learning(pc),
        "spells": [{"id": sp.id, "name": sp.name, "level": lvl, "school": sp.school,
                    "range": sp.range, "duration": sp.duration,
                    "save": sp.saving_throw, "line": sp.line}
                   for lvl, sp in casting.learnable(pc)],
    })


@require_POST
def learn_spells(request):
    """Write the chosen owed spells into the book: `{"spells": [ids]}`.

    The server is the rule: class list, a level castable when the pick was earned, not
    already in the book, no more than owed — every reason refused at once, with the fix
    named, and nothing written unless all of them pass.
    """
    from rules import casting
    from rules.sheet import full_sheet

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "no character"}, status=404)
    body = read_body(request)
    wanted = body.get("spells")
    if not isinstance(wanted, list):
        return JsonResponse({"error": "send the chosen spells as a list of ids"},
                            status=400)
    added, problems = casting.learn(pc, wanted)
    if problems:
        return JsonResponse({"error": " ".join(problems), "problems": problems},
                            status=400)
    from rules import spells as spells_mod

    names = [spells_mod.get(sid).name for sid in added]
    c.transcript.append({"who": "gm", "kind": "consequence",
                         "text": f"{pc.name} writes {', '.join(names)} into the "
                                 f"spellbook."})
    if c.character_id:
        roster.record(c.character_id, pc)
    c.save()
    return JsonResponse({**full_sheet(pc), "learned": added})


# What the Continue button sends. Written as an instruction to the GM rather than as
# something the character does, because the whole point is that the player is *not*
# acting: a turn that put "I wait" in the box would have the character stand there while
# the question they just asked went on not being answered.
#
# One definition, in `gm/prompts.py` beside the examples that teach it. It was written
# out again here, and the prose call now recognises this exact string to swap in
# Continue's own demonstrations — two copies of a string that has to match byte for
# byte is how the stale one ships (CLAUDE.md, "when you fix a rule, grep for every
# copy of it").
CARRY_ON = prompts.CARRY_ON


@require_POST
def say(request):
    """A player turn: GM call 1, validation, resolution."""
    c = campaign_mod.current()
    if c.scene.awaiting:
        return JsonResponse(
            {"error": "There is a roll waiting on you."}, status=409
        )
    # The watcher's pending work applies before the turn is read, so "I loot the
    # watchman" finds whatever the watcher slipped into his coat while the player was
    # typing — the garnish rides out with everything else `_op_loot` moves.
    watcher.drain(c)

    body = read_body(request)
    text = (body.get("text") or "").strip()

    # Continue: the player is not acting, and is asking the scene to go on without them.
    # It exists because a turn can stop with nothing to answer — the GM narrated the
    # character asking the guildhand a question and then ended the beat, so there was no
    # reply and nothing to type that was not an action the player did not want to take.
    # The line is written here rather than typed into the box, so it cannot be mistaken
    # for a declaration and cannot be refused by the check below.
    carry_on = bool(body.get("carry_on"))
    # A spell chosen from the Spells button rides as an attachment beside the words
    # (design F §4.4, item 21.1): validated here, stored on the player's beat and the
    # turn log, and not acted on in Phase 1 — Lane E makes the engine read it.
    attached, bad = _read_attachments(c, body, text, carry_on)
    if bad:
        return JsonResponse({"error": bad}, status=400)
    typed = bool(text)
    # A place from the "From here" row (I6): its own door below, after the checks every
    # turn passes. Sent with no words (or only the row's own go line) it is "I go to the
    # market." and no chip, since the line already says it; with words of the player's,
    # the words are theirs and the chip is drawn on the beat (`_the_way_there`).
    place = next((a for a in attached if a.get("kind") == "place"), None)
    if place is not None:
        if not text or _norm_line(text) == _norm_line(_go_line(place["name"])):
            text = _go_line(place["name"])
            typed = False
    elif not text and attached:
        # A chip and nothing else is a turn: the player means the spell.
        text = f"I cast {attached[0]['name']}."
    if carry_on:
        text = CARRY_ON
    if not text:
        return JsonResponse({"error": "say something"}, status=400)
    # The GM is told the whole instruction; the player sees the button they pressed.
    # Printing the instruction back as though they had typed it would put words in
    # their mouth on the one turn whose entire point is that they said nothing.
    shown = "…" if carry_on else text

    # The author's own hand, and it goes BEFORE the reaching-across-the-table check
    # below — which exists to refuse exactly the sentences a cheat is made of. "The
    # merchant falls in love with me" is a declaration about the world, and saying so
    # on purpose is the whole feature.
    #
    # Detected here in code and never by the model, for the reason every other
    # declaration-detection in this app is in code: a model asked to notice a marker
    # sometimes does not, and a cheat quietly narrated instead of executed is the worst
    # of both — the fiction says you have the gold and the purse does not.
    if not carry_on and _CHEAT.match(text):
        return _cheat(c, _CHEAT.sub("", text, count=1).strip(), shown)

    # Out of character, and before everything else for the same reason the cheat is: a
    # slash can never be a sentence somebody meant.
    if not carry_on and _GM.match(text):
        return _gm_answer(c, _GM.sub("", text, count=1).strip(), shown)

    # The player controls one character; the GM controls the world. A turn that declares
    # what the world does is handed back rather than resolved — gently, and without
    # consuming the turn, because the player has not done anything wrong so much as
    # reached across the table.
    if not carry_on:
        # Only on words the player typed: the line written for a bare chip is ours.
        if typed:
            said = player_input.check(text)
            if not said.ok:
                return JsonResponse({"hint": said.hint, "offending": said.offending},
                                    status=422)
    # And what the character claims to BE. Not a door: the player's own design,
    # 2026-09-18, is that "I reveal my true form as a divine being" should PLAY — the
    # character does it, nothing happens, and the people here react to somebody
    # claiming what they plainly are not. The claim becomes a Bluff in the plan
    # (`judgement.inject_false_claim`), the prose is told it is false and how the
    # roll went (`prompts.false_claim_block`), a finding catches prose that makes it
    # true, and the crowd's reaction rides `note_heat`. Stashed on the agent for the
    # prose call once there is one, and cleared every turn so a claim never outlives
    # its turn.
    claim = "" if carry_on else judgement.false_claim(text, c.scene)

    # A character at or below 0 hit points does not get a turn. Nothing used to ask:
    # Kesst was dying at -3, the player typed "now what", and the GM cheerfully narrated
    # her dodging and stumbling while a thug attacked her and a second encounter began.
    # What happens to the downed is the rules' business, not the GM's.
    if c.ended:
        return JsonResponse(_ended_payload(c), status=410)

    # A spell attached is acted on (Lane E): checked against the character BEFORE any
    # model call, and its aim grounded from the player's words. A refusal the player can
    # fix answers now, as the one 422 shape (§2.6): no beat, no clock, no NPC turn.
    acting = attached
    if attached and not carry_on:
        acting, refused = _dry_cast(c, attached, text if typed else "")
        if refused:
            return _refusal(refused)

    # The player's line, with the chip drawn before it when there is one (design F §4.4);
    # the key only when sent, so every beat before attachments reads as it did. A place
    # is drawn only beside the player's own words: "I slip out quietly." must still say
    # where they went, and "I go to the market." already does.
    drawn = [dict(a) for a in attached if a.get("kind") != "place" or typed]
    beat = {"who": "player", "text": shown, **({"attachments": drawn} if drawn else {})}
    pc = c.scene.pc()
    if place is not None and c.scene.in_encounter and pc is not None \
            and c.scene.current_ref() != pc.ref:
        # The combat bar's rule for a button that acts: not off-turn.
        return JsonResponse({"error": "It is not your turn."}, status=409)
    if downed.state_of(pc) not in ("fine", "disabled"):
        c.transcript.append(beat)
        outcome = downed.resolve(c)
        for line in outcome.lines:
            c.transcript.append({"who": "gm", "text": line, "kind": "consequence"})
        # On the record, which this path never was: the owner's save of 2026-10-04 has
        # the bleeding, the hour and "whoever was standing over you has gone" in its
        # transcript and not one turn-log entry for any of it, so nothing said which
        # door had moved the clock or what the winners did.
        c.turn_log.append(history_mod.stamp(c, {
            "kind": "downed", "state": outcome.state, "lines": list(outcome.lines),
            "effects": list(outcome.effects)}))
        # The last beat's offers were written for a fight the player is no longer in a
        # state to take part in, and after the hour they are offers about people who
        # have gone: the 2026-10-04 screenshot read "I focus on the first robber" an
        # hour after the robbers won. The next narrated beat writes new ones.
        c.suggestions = []
        if outcome.died:
            _end_campaign(c, pc)
            c.save()
            return JsonResponse({**_state(c), **_ended_payload(c)}, status=200)
        # A turn the player cannot take is still a turn that passes. Inside a fight the
        # world takes its own, which is what ticks the hold down, fires the ward they
        # are lying in and lets the enemies standing over them act. `downed.resolve`
        # deliberately skips no time in an encounter: it used to, and a paralyzed
        # character stood among three thugs for four rounds without being touched.
        if outcome.state == "held" and c.scene.in_encounter:
            _run_npc_turns(c, GMAgent(c.world, c.engine()))
        c.save()
        return JsonResponse(_state(c))

    c.transcript.append(beat)
    if place is not None:
        return _the_way_there(c, place, text, typed, acting, claim, beat)
    return _keep_the_spell(c, acting, _plan_and_run(c, text, acting, claim, attached))


def _keep_the_spell(c, acting: tuple, resp):
    """The spell chip stays when the turn did not cast it, with the engine's reason.

    The register's deferred row ("a spell refused mid-turn is spent"): `_dry_cast`
    answers what it can before any model call, but a cast the engine refuses while the
    turn RUNS — no slot left after an earlier cast in the same list, a plan that never
    carried it, a first harmful cast that opened a fight and is "still to be spoken"
    (`Engine._cast_gate`) — came back 200, and the page cleared the chip as though the
    spell had gone. The words did run, so they are not put back; the chip is, under the
    same `unfinished` field a place chip's unfinished move uses, with the engine's own
    sentence for why."""
    chip = next((a for a in acting or () if isinstance(a, dict) and a.get("kind") == "spell"),
                None)
    if chip is None or getattr(resp, "status_code", 0) != 200 or c.ended \
            or c.scene.awaiting:
        return resp
    turn = next((e for e in reversed(c.turn_log or []) if e.get("kind") == "turn"), None)
    casts = [o for o in (turn or {}).get("outcomes") or [] if str(o.get("op", "")) == "cast"]

    def cast_happened(o) -> bool:
        return str(o.get("status") or "resolved") == "resolved" and not any(
            isinstance(e, dict) and e.get("kind") == "battle_joined"
            for e in o.get("effects") or [])

    if any(cast_happened(o) for o in casts):
        return resp
    why = next((str(o.get("tell") or "") for o in casts if o.get("tell")), "")
    name = str(chip.get("name") or chip.get("id") or "The spell")
    return _with(resp, {"unfinished": {
        "text": "", "keep_chip": True, "why": why,
        "line": f"{name} was not cast; it is still attached."}})


def _plan_and_run(c, text: str, acting: tuple, claim: str = "", attached=None):
    """A spoken turn from the planner on: plan `text`, run it, narrate it. The player's
    line is already the last beat of the transcript, and every failure below takes it
    off again, so a caller that appended its own line (a follow-up at the destination,
    `_the_way_there`) gets the same bargain. Lifted out of `say` unchanged so the place
    chip's two halves run the one path every spoken turn runs."""
    world = c.world
    agent = GMAgent(world, c.engine())
    _arm_cards(agent, c)
    agent.false_claim = claim
    # Read by the planner's `declared_ops(attached=…)`, `inject_cast(attached=…)` and the
    # narrator checks: the chip, with the aim grounded from the words when it carried
    # none. Set every turn on a fresh agent, so it never outlives the turn, as `claim`
    # does not.
    agent.attachments = acting
    attached = acting if attached is None else attached

    # Free actions taken since the last spoken turn ride along as context rather than
    # having cost turns of their own. Into `history`, not `player_input`: the injectors
    # read the player's words with regexes, and a note saying "formed the blood
    # armament" must not be re-read as a fresh declaration of anything.
    pending = list(getattr(c, "pending_free", []) or [])
    if pending:
        c.pending_free = []
        c.history.append({
            "role": "user",
            "content": "(Since their last turn, spending no time: "
                       + "; ".join(pending) + ".)"})

    try:
        plan = agent.plan_turn(
            text, c.history, location=c.location,
            recent_events=_recent_events(world, c.location),
            previous_intents=c.last_intent_signature,
            recent_narration=[b["text"] for b in c.transcript[-8:] if b["who"] == "gm"],
        )
    except ModelUnavailable as exc:
        c.transcript.pop()
        _put_back_free_actions(c, pending)
        return JsonResponse({"error": str(exc)}, status=503)
    except IntentError as exc:
        c.transcript.pop()
        _put_back_free_actions(c, pending)
        if getattr(exc, "fixable_by", "") == "player":
            return _refusal({"text": exc.for_a_person or str(exc), "code": exc.code,
                             "fix": exc.fix})
        return JsonResponse({"error": f"The GM could not produce a legal turn. {exc}"},
                            status=502)

    # The plan loop stopped on a refusal only the player can fix (Lane A sets
    # `TurnPlan.refusal`, §2.6): the same 422 as the dry check above, and the turn never
    # happened — the line comes off the transcript the way the 502 path takes it off.
    stopped = getattr(plan, "refusal", None) or _attached_not_planned(plan, acting)
    if stopped:
        c.transcript.pop()
        _put_back_free_actions(c, pending)
        return _refusal(stopped)

    # The interpreter's reading of the sentence rides with the plan into the turn log,
    # beside the detectors' opinion, so every disagreement is on the record
    # (docs/the-interpreter.md).
    plan.reading = getattr(agent, "reading", None)
    # And the attachments, into the turn log's `turn` row beside it (`_log_turn`).
    if attached:
        plan.attachments = [dict(a) for a in attached]
    resp = _advance(c, agent, plan.narration, plan, text)
    # A purchase opens the counter with the thing picked (`_trade_offer`): the turn's
    # prose brings the keeper to the counter, and the player pays on the screen.
    offer = _trade_offer(c, text) if getattr(resp, "status_code", 200) == 200 else None
    return _with(resp, {"trade": offer}) if offer else resp


def _attached_not_planned(plan, acting) -> dict | None:
    """The refusal for a plan that lost what the player attached, or None.

    The attached place or spell is the player's declaration and the engine's to carry
    out (`judgement.travel_to_the_attached`, `_cast_the_attached`). A plan without it
    can only be the loop giving up: every attempt refused, and the turn degraded to a
    narrated nothing. Measured live 2026-09-29: seven refused plans for "I search the
    crossroads for tracks, then head out" beside "the outskirts" became `narrate_only`,
    the search was narrated, the party never moved, and the page cleared the chip and
    the words as though it had.

    Which way out, and why. The words before the move are the first command of the
    chain and the move the second; Zork's main loop clears the rest of the line when a
    command fails (`P-CONT`, gmain.zil), so the move does NOT run. Nor is the failed
    command narrated: the words go back to the player to send again, and a search
    narrated now would be narrated twice. So nothing runs (no beat, no clock, no NPC
    turn), the words and the chip stay, and the sentence says why. The same for a
    spell: a degraded plan never narrates a cast that did not happen and then clears the
    chip. A turn with nothing attached still degrades to narration, as the owner ruled;
    this is only for an attachment, whose thing is the engine's to do or to refuse."""
    chip = next((a for a in (acting or ()) if isinstance(a, dict)
                 and a.get("kind") in ("place", "spell")), None)
    if chip is None:
        return None
    intents = list(getattr(plan, "intents", None) or ())
    if chip["kind"] == "place":
        if any(i.op in ("travel", "journey")
               and chip["id"] in (str(i.params.get("place") or ""), str(i.params.get("to") or ""))
               for i in intents):
            return None
        text = (f"That could not be made into a turn, so nothing happened and "
                f"{chip['name']} is still attached. Say it another way, or send the move "
                f"on its own.")
    else:
        if any(i.op == "cast" and str(i.params.get("spell") or "") == chip["id"]
               for i in intents):
            return None
        text = (f"That could not be made into a turn, so {chip.get('name') or chip['id']} "
                f"was not cast and is still attached. Say it another way, or press Say "
                f"with the spell alone.")
    return {"text": text, "code": "unshaped", "fix": None}


def _put_back_free_actions(c, pending: list) -> None:
    """A turn the model could not plan takes nothing with it.

    Measured 2026-09-25: the free actions were moved into `history` as a note and
    `pending_free` emptied BEFORE the plan call, so a 503 left the note in the history
    (the next turn's model read it as already said) and the free actions gone from the
    list that would have carried them to the turn that did happen."""
    if not pending:
        return
    if c.history and c.history[-1].get("content", "").startswith("(Since their last turn"):
        c.history.pop()
    c.pending_free = list(pending) + list(getattr(c, "pending_free", []) or [])


# The combat panel's whitelist: what a button may emit, and nothing else. The free-text
# box still exists for everything unconventional, and it goes through the GM like any
# spoken turn — this path is for the actions whose arithmetic is already the engine's.
# `cast` was missing, so a spellcaster had no deterministic way to take their own main
# action: the panel offered Strike, Full attack, Ability, Swift and Free, and a wizard's
# entire turn had to be typed and routed through the narrator. Measured in the engine,
# casting itself has worked all along — Magic Missile 1d4+1 x3, Burning Hands 5d4 at
# Reflex DC 12, Fireball 5d6 at DC 14, damage applied, spell resistance and saves read
# off the spell. Only the button was absent.
_COMBAT_OPS = {"attack", "move", "use_ability", "use_item", "manoeuvre", "cast"}


@require_POST
def combat_act(request):
    """A turn taken on the combat panel: buttons straight to the engine.

    No model plans this — clicking "attack the thug" has nothing in it for a narrator
    to decide, and routing it through one made every combat turn cost a model call
    before the dice came out. The narrator still gets the *outcomes* (through the same
    `_finish` every spoken turn uses), so the fiction keeps its voice; and the NPC
    turns that follow run exactly as they always have.
    """
    body = read_body(request)
    c = campaign_mod.current()
    scene = c.scene
    pc = scene.pc()
    refusal = _cannot_act(pc, "act")
    if refusal:
        return refusal
    if scene.awaiting:
        return JsonResponse({"error": "There is a roll waiting on you."}, status=409)

    actions = body.get("actions") or []
    label = str(body.get("label", "")).strip()
    end_turn = bool(body.get("end_turn"))

    # Out of a fight, this door opens only for free actions — a toggle that arms your
    # own body has nothing in it for a narrator to decide, and routing it through the
    # spoken turn is how forming the blood armament cost a whole turn, invited the model
    # to dress it as a Knowledge (Arcana) check it then failed as untrained, and let an
    # `advance_time` ride along. A free action spends no time and asks nobody's
    # permission; everything else out of combat is still a spoken turn.
    if not scene.in_encounter:
        if end_turn or any(str(a.get("op", "")).lower() != "use_ability"
                           for a in actions if isinstance(a, dict)) or not actions:
            return JsonResponse({"error": "No fight is on."}, status=409)
    elif scene.current_ref() != pc.ref:
        # The only reason somebody else holds the turn when the player posts is that
        # the NPC loop did not finish — so finish it, rather than refusing. Measured
        # live: a twelve-creature fight left a thug holding the turn and this branch
        # answered "It is not your turn" to every button, for ever. A refusal the
        # player cannot act on is not a refusal, it is a locked door.
        _run_npc_turns(c, GMAgent(c.world, c.engine()))
        if scene.in_encounter and scene.current_ref() != pc.ref:
            _hand_the_turn_back(c, "The moment comes back to you.")
        # A fight that ended while they waited, or a die they now owe, is an answer
        # in itself — the declared action belongs to a turn that no longer exists.
        if scene.awaiting or not scene.in_encounter:
            c.save()
            return JsonResponse(_state(c))

    raw = []
    for a in actions:
        if not isinstance(a, dict):
            return JsonResponse({"error": "actions must be objects"}, status=400)
        op = str(a.get("op", "")).strip().lower()
        if op not in _COMBAT_OPS:
            return JsonResponse({"error": f"{op!r} is not a combat-panel action"},
                                status=400)
        raw.append({
            "op": op, "actor": pc.ref,
            "target": a.get("target"),
            "because": label or "the combat panel",
            "params": {k: v for k, v in (a.get("params") or {}).items()
                       if isinstance(k, str)},
            # The player's spell is the player's dice: `cast` defaults to hidden, so a
            # Magic Missile from the panel was rolled by the engine (owner, 2026-10-01).
            **({"visibility": "player"} if op == "cast" else {}),
        })

    engine = c.engine()
    agent = GMAgent(c.world, engine)
    _arm_cards(agent, c)

    if not raw:
        # End turn with nothing declared: the round moves on. Marked as acted so the
        # first blow of the next fight does not find the PC flat-footed for passing.
        scene.acted.add(pc.ref)
        if end_turn:
            _run_npc_turns(c, agent)
        c.save()
        return JsonResponse(_state(c))

    c.transcript.append({"who": "player", "text": label or "(the combat panel)"})
    undo = scene.snapshot()
    try:
        intents = engine.validate(raw)
        resolution = engine.run(intents)
    except (IntentError, ValueError, KeyError) as exc:
        # Same bargain as the spoken turn: the refused action leaves no trace.
        scene.restore(undo)
        c.transcript.pop()
        # A stale panel can name somebody who has since left the room, and the
        # validator's sentence for that is written for the model — a ref and an op.
        # The person reads a sentence written for a person.
        said = getattr(exc, "for_a_person", "") or str(exc)
        if getattr(exc, "check", "") == "refs" and "not here" in said:
            said = "That person is no longer here."
        return JsonResponse({"error": said}, status=400)

    # A free action is remembered for the next spoken turn, so the narrator hears about
    # it without a turn ever having been spent on it. In-memory on purpose: it is a note
    # between two turns of one sitting, not campaign state.
    if not end_turn and label:
        c.pending_free = list(getattr(c, "pending_free", []) or []) + [label]

    # A turn the player has not finished does not pass to anybody. This is what
    # `end_turn` was always supposed to mean.
    return _finish(c, agent, resolution, "", label, plan=None, hand_over=end_turn,
                   player_text="")


@require_POST
def roll_face(request):
    """What the pending die shows — and nothing else.

    Reported from the table 2026-09-16: *"as it stands when dice are rolled the last die
    spins until a reply is sent to the user. I would prefer that the dice land show the
    number it landed on and then be able to be closed while the user waits."*

    They are describing the shape of `roll` below. The face is known in its first few
    lines; everything after it — resolution, then the narrator, which is a local model
    and the slow part of a turn — runs before the number is returned. So the die spun
    through the whole generation, and the LAST die of a turn spun longest, because the
    ones before it only had to be handed back for the next prompt.

    Splitting it here rather than streaming one response out of `roll`: nine tests read
    that endpoint as JSON, a `StreamingHttpResponse` has no `.json()`, and the error
    paths would have to move from status codes into frames. This adds a request that
    **mutates nothing at all** — it does not touch `awaiting`, does not remember what it
    said, and can be called and abandoned. `roll` then receives the face the same way it
    already receives one from the debug toggle, so no trust boundary moves: the client
    could always name its own face, and the die is still rolled by `rules.dice`.
    """
    c = campaign_mod.current()
    if not c.scene.awaiting:
        return JsonResponse({"error": "nothing is waiting on a roll"}, status=409)
    from rules.dice import Dice
    return JsonResponse({"face": Dice().roll(c.scene.awaiting.get("die", "1d20")).raw})


@require_POST
def roll(request):
    """The player's answer to the dice popup. Resolution resumes from where it stopped."""
    c = campaign_mod.current()
    if not c.scene.awaiting:
        return JsonResponse({"error": "nothing is waiting on a roll"}, status=409)

    from rules.dice import Dice

    body = read_body(request)
    prompt = c.scene.awaiting
    notation = prompt.get("die", "1d20")
    low = prompt.get("min", 1)
    high = prompt.get("max", 20)

    face = body.get("face")
    if face is None:
        # The engine rolls it on the player's behalf if they would rather not.
        face = Dice().roll(notation).raw

    # int() on whatever arrived: the adversarial audit posted {"face": "banana"} and
    # took the whole view down with an uncaught ValueError — a 500 with a pending roll
    # still open. The popup only sends numbers; anything else is somebody probing.
    try:
        face = int(face)
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": f"{notation} lands on a number between {low} and {high}."},
            status=400)
    if not low <= face <= high:
        return JsonResponse(
            {"error": f"{notation} gives a result between {low} and {high}"}, status=400
        )

    engine = c.engine()
    undo = c.scene.snapshot()
    try:
        resolution = engine.resume(face)
    except (IntentError, ValueError, KeyError) as exc:
        # A raise part-way through resolution used to be a 500 with the scene already
        # half-mutated and never saved: the damage had landed, the pending roll was
        # gone, and the player's only way out was to reload into a game that had
        # forgotten the swing. Not-saving was never the same thing as not-happening —
        # the campaign is held in memory, so the half-applied board survived to be
        # written by the next turn that succeeded. The snapshot is the rollback the
        # old comment claimed; the pending roll is then dropped on purpose, so the
        # restored scene is not waiting on a die nobody is going to be asked for.
        c.scene.restore(undo)
        c.scene.awaiting = None
        c.scene.pending_intents = []
        c.scene.pending_outcomes = []
        c.scene.pending_partial = {}
        c.save()
        return JsonResponse(
            {"error": f"That roll could not be finished: {exc}. The turn was let go "
                      f"rather than half-applied — try the action again."},
            status=409)
    narration = c.transcript[-1]["text"] if c.transcript else ""
    player_input = next(
        (t["text"] for t in reversed(c.transcript) if t["who"] == "player"), ""
    )
    agent = GMAgent(c.world, engine)
    _arm_cards(agent, c)
    resp = _finish(c, agent, resolution, narration, player_input, plan=None)
    # The face the die actually showed. Without it the page had no way to land its 3D
    # die on the result: it asked, played a decorative throw, closed the mat and put
    # the number in a table. Reported from the table, 2026-09-09 — "the dice don't land
    # with the number facing the user" — and that is why. The whole roller lands on a
    # result the server decided, and this is the server saying which.
    #
    # `verdict` is the engine's own judgement of that face (`Engine._judge`): success or
    # failure and the natural, or None for a die nobody calls a success — damage,
    # initiative, a forage run. The page plays its flourish from this and from nothing
    # else (22-roll-verdict.js). Asked for 2026-10-01; computing it in the browser would
    # need the number to beat, which on an opposed check is the other side's secret die
    # and is deliberately never sent (`dc_shown`).
    return _with(resp, {"rolled": face, "verdict": engine.judged})


def _with(response, extra: dict):
    """The same JSON response, plus a field. Cheaper than threading it through
    `_finish`, which nine other views share and none of the others need it."""
    try:
        payload = json.loads(response.content)
    except (ValueError, TypeError):
        return response
    payload.update(extra)
    return JsonResponse(payload)


# `/cheat <wish>`. A slash so it can never be a sentence somebody meant: no ordinary
# turn starts with one, and the player who types it has decided to be the author for a
# line. Trailing space or colon both allowed, because both are what people type.
_CHEAT = re.compile(r"^\s*/cheat\b[:\s]*", re.I)

# `/gm <question>`. Out of character, answered by the engine, never by a model. Same
# slash reasoning as the cheat above: no ordinary turn starts with one.
_GM = re.compile(r"^\s*/gm\b[:\s]*", re.I)

# The aim a spell attachment may carry (fix-interfaces §2.7). A copy for validation at the
# door, as the register allows; Lane E owns the canonical `areas.AIM_PATTERN`, and a test
# holds this one to it once it exists.
_AIM = re.compile(r"^(ref:[A-Za-z0-9_-]+|self|dir:(n|ne|e|se|s|sw|w|nw|up|down)"
                  r"|point:\d+,\d+(,\d+)?|object:[^\n]{1,60})$")


def _aim_help(aim) -> str:
    return (f"{aim!r} is not an aim a spell can take: a person (ref:c1), yourself (self), "
            f"a direction (dir:n), a square (point:3,4) or a thing (object:the cart).")


def _dry_cast(c, attached: tuple, text: str):
    """Before any model is asked (item 21.3): the attached spell's cast, validated in a
    snapshot. Returns `(attachments, refusal)` — the attachments with an aim grounded from
    the player's own words where the chip carried none (`areas.aim_from_words`), and the
    §2.6 refusal dict when the cast cannot happen for a reason only the player can fix.

    Measured 2026-09-28: an unprepared Burning Hands went through seven plan attempts,
    each refused with the same sentence, a hand-off to a second model and a narrate_only
    — and the player never learned why. The refusal is a fact about the character; no plan
    can change it, so no model is asked."""
    from rules import areas, spells as spells_mod

    chip = next((a for a in attached if a.get("kind") == "spell"), None)
    if chip is None:
        return attached, None
    pc = c.scene.pc()
    chip = dict(chip)
    if not chip.get("aim"):
        try:
            spell = spells_mod.get(chip["id"])
        except KeyError:
            spell = None
        found = areas.aim_from_words(c.scene, pc.ref, text, spell) if pc else None
        if found:
            chip["aim"] = found
    params = {"spell": chip["id"]}
    if chip.get("aim"):
        params["aim"] = chip["aim"]
    engine = c.engine()
    undo = c.scene.snapshot()
    refusal = None
    try:
        engine.validate([{"op": "cast", "actor": pc.ref, "params": params,
                          "because": "the player attached it"}])
    except IntentError as exc:
        # `no_aim` is left to the model: "if they write nothing, the model infers the
        # use" (item 21.1). Everything else the player can fix is answered now.
        if exc.fixable_by == "player" and exc.code != "no_aim":
            refusal = {"text": exc.for_a_person or str(exc), "code": exc.code,
                       "fix": exc.fix}
    except (ValueError, KeyError):
        pass
    finally:
        c.scene.restore(undo)
    return tuple([chip] + [a for a in attached if a.get("kind") != "spell"]), refusal


def _read_attachments(c, body: dict, text: str, carry_on: bool) -> tuple[tuple, str]:
    """The turn's attachments, checked at the door: `(attachments, "")`, or `((), why)`
    with a sentence for the player when one breaks a rule of §2.10.

    Checked here, before anything else reads the turn, because a chip the engine cannot
    honour is the player's to fix, not a plan for the model to guess around. Phase 1
    stores what passes and acts on none of it (Lane E does). Each one stored carries the
    spell's `name`, so the transcript can draw the chip without a second lookup.
    """
    from rules import casting, spells as spells_mod

    raw = body.get("attachments")
    if raw is None or raw == []:
        return (), ""
    if not isinstance(raw, list):
        return (), "Attachments must be a list."
    if len(raw) > 1:
        return (), "Only one spell can be attached to a turn."
    item = raw[0]
    # A place from the "From here" row (I6) keeps its own rules (`_read_place`).
    if isinstance(item, dict) and item.get("kind") == "place":
        return _read_place(c, item, text, carry_on)
    if carry_on:
        return (), "A spell cannot be attached to Continue — say what you do with it."
    if _CHEAT.match(text) or _GM.match(text):
        return (), "A spell cannot be attached to /gm or /cheat."
    if not isinstance(item, dict) or item.get("kind") != "spell":
        return (), "Only a spell or a place can be attached to a turn."
    spell_id = str(item.get("id") or "").strip()
    try:
        spell = spells_mod.get(spell_id)
    except KeyError:
        return (), f"There is no spell called {spell_id or 'that'}."
    pc = c.scene.pc()
    if pc is None:
        return (), "There is nobody here to cast it."
    if not (casting.knows(pc, spell) or spell.id in (getattr(pc, "prepared", None) or {})):
        return (), f"{pc.name} does not know {spell.name}."
    out = {"kind": "spell", "id": spell.id, "name": spell.name}
    if "aim" in item:
        aim = item.get("aim")
        if not isinstance(aim, str) or not _AIM.match(aim):
            return (), _aim_help(aim)
        out["aim"] = aim
    return (out,), ""


def _go_line(name: str) -> str:
    """The line a click on the exits row sends and shows: "I go to the market."."""
    return f"I go to {name}."


def _read_place(c, item: dict, text: str, carry_on: bool) -> tuple[tuple, str]:
    """A place from the "From here" row (I6), checked at the door like a spell chip.

    It must be one of `scene.exits` as the engine builds them this moment — never a
    place the page remembered from an earlier state — and not one the rules would
    refuse; a journey (days on the clock) must carry `confirmed`, which the page sends
    with a journey chip, because attaching it and then pressing Say is the confirmation.

    Words beside it are the player's, and are not refused here. Until 2026-09-29 any
    words other than the go line were a 400 ("a turn of its own"), because the click
    went straight to `_take_the_exit` and words beside a move were silently ignored.
    The owner then asked for the chip to attach like a spell's, and for the words to say
    WHEN the move happens ("where in the described action the move should take place");
    `_the_way_there` cuts the line at the move and runs each half where it belongs.

    FAR CHIPS (item 9, 2026-09-30). A place that is not a way on from here is taken when
    the chart can walk to it — through places the party has been, never by a shut way,
    never by a journey (`places_found.walk_to`, Inform's *Approaches* default; the owner's
    ruling C2) — and the engine walks the whole way in one turn, every hop rolled and
    watched (`Engine._op_travel`). Until then a chip had to be one step, so the Map tab's
    Walk there attached one leg a turn; the owner: "I should not be forced to play a whole
    turn for each connecting point." A journey is still only ever its own chip, from the
    head of its road, with its confirmation; and a far walk begun mid-fight is still a
    withdraw, because the travel op asks `_leaving_the_fight` however far it goes."""
    from . import exits as exits_mod
    from . import places_found

    if carry_on:
        return (), "A place cannot be attached to Continue. Choose where to go, or continue."
    if _CHEAT.match(text) or _GM.match(text):
        return (), "A place cannot be attached to /gm or /cheat."
    place_id = str(item.get("id") or "").strip()
    try:
        found = exits_mod.exits(c.engine(), c.world)
    except Exception:      # noqa: BLE001 — an unreadable graph offers nowhere to go
        found = []
    exit_ = exits_mod.find(found, place_id)
    if exit_ is None:
        try:
            far, legs, why = places_found.walk_to(c.engine(), c.world, place_id)
        except Exception:  # noqa: BLE001 — as above: no graph, no far way either
            far, legs, why = None, [], ""
        if far is not None and legs:
            return ({"kind": "place", "id": far["id"], "name": far["name"],
                     "journey": False},), ""
        # The rule's own sentence when the way is shut; otherwise the ways on from here.
        # Never the place's name: a place under the fog is not to be named by a refusal.
        if far is not None and why and why != "No way there by the ways you know.":
            return (), why
        names = ", ".join(e["name"] for e in found)
        return (), (f"There is no way from here to {place_id or 'there'} by the ways you "
                    f"know." + (f" From here you can go to {names}." if names else ""))
    if exit_["blocked"]:
        return (), exit_["blocked"]
    if exit_["journey"] and item.get("confirmed") is not True:
        return (), (f"{exit_['name']}: {exit_['time_words']}. Confirm the journey "
                    f"before setting out.")
    return ({"kind": "place", "id": exit_["id"], "name": exit_["name"],
             "journey": bool(exit_["journey"])},), ""


def _norm_line(text: str) -> str:
    return " ".join(str(text or "").split()).lower().rstrip(".!")


def _take_the_exit(c, chip: dict, text: str):
    """The move the row declared, straight to the engine, then the narrator (I6).

    The door `cast_act` and `talk_act` already are: engine-only for the choice, with no
    model asked WHERE. Measured 2026-09-28 (G2): "I walk to the nearest crossroads" went
    through the planner, was refused, and was narrated as a walk. A click names the
    place by the engine's own id, so the plan is built here — one declared `travel`, or
    one `journey` at the pace the party can keep — and `_advance` runs it and has the
    narrator describe the walk from the engine's tells, exactly as a spoken turn's plan
    is run. The line was appended by the caller; a refusal takes it off again."""
    from . import exits as exits_mod

    pc = c.scene.pc()
    engine = c.engine()
    agent = GMAgent(c.world, engine)
    _arm_cards(agent, c)
    agent.attachments = (dict(chip),)
    if chip.get("journey"):
        params = {"to": chip["id"]}
        if exits_mod.riding(engine):
            params["pace"] = "ride"
        op = {"op": "journey", "actor": pc.ref, "params": params,
              "because": "the player chose it from the ways on"}
    else:
        op = {"op": "travel", "actor": pc.ref, "params": {"place": chip["id"]},
              "because": "the player chose it from the ways on"}
    # The manner of the going, rolled where 1e rolls it (`judgement.manner_checks`): "I
    # slip out quietly" is Stealth against whoever might notice, before the walk.
    try:
        intents = engine.validate([*judgement.manner_checks(text, c.scene), op])
    except IntentError as exc:
        c.transcript.pop()
        if getattr(exc, "fixable_by", "") == "player":
            return _refusal({"text": exc.for_a_person or str(exc), "code": exc.code,
                             "fix": exc.fix})
        return JsonResponse({"error": getattr(exc, "for_a_person", "") or str(exc)},
                            status=400)
    # Free actions since the last spoken turn ride along as context, as `say` does.
    pending = list(getattr(c, "pending_free", []) or [])
    if pending:
        c.pending_free = []
        c.history.append({
            "role": "user",
            "content": "(Since their last turn, spending no time: "
                       + "; ".join(pending) + ".)"})
    plan = TurnPlan(narration="", intents=intents)
    plan.attachments = [dict(chip)]
    return _advance(c, agent, "", plan, text)


# What a clause beside a place chip may declare and still be only the going: the move
# itself, and Stealth, which is HOW one goes ("I slip out quietly" reads as a Stealth
# check: measured 2026-09-29, `declared_ops` gave ['check'] for it in all three exports).
_GOING_OPS = {"travel", "journey", "move"}


def _only_the_going(c, clause: str) -> bool:
    """A clause that is the move and nothing else, which takes the engine's own door
    (`_take_the_exit`) with the words as its manner, and asks no planner. Detected in
    code from the declarers, never asked of a model (CLAUDE.md, declaration detection)."""
    if judgement.purchase_sought(clause):
        return False
    ops = set(judgement.declared_ops(clause, c.scene, c.world))
    if "check" in ops:
        skills = {str((r.get("params") or {}).get("skill", "")).lower()
                  for r in judgement.inject_checks([], clause, c.scene) or ()}
        if skills <= {"stealth"}:
            ops.discard("check")
    return ops <= _GOING_OPS


def _where(c) -> tuple:
    """Where the party stands, as a thing to compare: the place, the settlement, the road."""
    return (c.scene.at, c.scene.location_id,
            json.dumps(c.scene.road or {}, sort_keys=True, default=str))


def _why_it_did_not_move(c) -> str:
    """The engine's own sentence for a move that did not happen, from the last turn's
    outcomes, or ""."""
    turn = next((e for e in reversed(c.turn_log or []) if e.get("kind") == "turn"), None)
    for o in (turn or {}).get("outcomes") or []:
        if str(o.get("op", "")) in ("travel", "journey") and o.get("tell"):
            return str(o["tell"])
    return ""


def _the_way_there(c, chip: dict, text: str, typed: bool, acting: tuple, claim: str,
                   beat: dict):
    """A place chip's turn, held to one rule whatever path it took: the chip's move is the
    engine's, so a turn that answers 200 has moved the party, or is waiting on a die that
    will, or says in `unfinished` that the move is still to do and keeps the chip.

    The ratchet, measured 2026-09-29 on the owner's gemma: "I search the crossroads for
    tracks, then head out" beside "the outskirts" degraded to a narrated nothing after
    seven refused plans, answered 200 with no move and no `unfinished`, and the page
    cleared the chip and the words, so the move was lost with nothing said. The paths
    below now say so themselves; this is the net under them, so a path added tomorrow
    cannot drop the move silently either."""
    before = _where(c)
    resp = _toward(c, chip, text, typed, acting, claim, beat)
    if getattr(resp, "status_code", 0) != 200 or c.ended or c.scene.awaiting \
            or _where(c) != before:
        return resp
    try:
        payload = json.loads(resp.content)
    except (ValueError, TypeError):
        return resp
    if payload.get("unfinished"):
        return resp
    import logging

    logging.getLogger(__name__).warning(
        "a place chip's turn ended without its move and without saying so: %s",
        chip.get("id"))
    return _unfinished(c, resp, [text if typed else _go_line(chip["name"])],
                       keep_chip=True, arrived=False, why=_why_it_did_not_move(c))


def _toward(c, chip: dict, text: str, typed: bool, acting: tuple, claim: str,
            beat: dict):
    """A place chip on Say (I6, owner 2026-09-29: "attach like a spell does and then apply
    when you send"), with the words deciding WHEN in the turn the move happens.

    No words, or only the going ("I slip out quietly", "I run for it"): the engine's own
    door, no model asked where (`_take_the_exit`), the words handed to the narrator as
    the player's line. Otherwise the line is cut into clauses in the order of doing
    (gm/sequence.py) at the move, and each half runs where it belongs:

      * Up to and including the move: planned and run here, through the one spoken-turn
        path, with the move held to the chip's place and put LAST
        (`judgement.travel_to_the_attached`). No clause recognisably the move puts it
        last, because leaving is what usually ends a turn.
      * After the move: planned again at the destination, against the people there, as
        a second turn — "the meaning of the noun phrase depends on where the player is by
        then" (DM4 §34). It cannot be one intent list: validation reads the scene being
        left, where the market's keeper is not.
      * A purchase before the move stops the chain there. A purchase is made on the
        counter's screen after the beat (owner's ruling 2026-09-27), and walking off in
        the same turn would open the next place's counter instead; the chip stays for
        the next Say.

    A half that cannot run stops the rest, as Zork's main loop clears the rest of the
    input on a fatal action (gm/sequence.py): the move stands, and the unrun words go
    back into the pen with a line saying so (`_unfinished`), never silently dropped.
    """
    from gm import sequence

    if not typed:
        return _take_the_exit(c, chip, text)
    parts = sequence.clauses(text)
    at = sequence.move_clause(parts, chip["name"])
    stop = next((i for i, p in enumerate(parts)
                 if (at is None or i < at) and judgement.purchase_sought(p)), None)
    if stop is not None:
        now, later, moves = parts[:stop + 1], parts[stop + 1:], False
    elif at is None:
        now, later, moves = parts, [], True
    else:
        now, later, moves = parts[:at + 1], parts[at + 1:], True
    now_text = sequence.joined(now) or text
    if later:
        # This beat is the words done now; the rest get their own line when they run.
        beat["text"] = now_text

    before = _where(c)
    if not moves:
        # The chip is not spent: it is not drawn on a beat that does not go anywhere.
        beat.pop("attachments", None)
        resp = _plan_and_run(c, now_text, (), claim)
        if resp.status_code != 200:
            return resp
        return _unfinished(c, resp, later or [_go_line(chip["name"])], keep_chip=True,
                           arrived=False)
    mine = dict(chip)
    if chip.get("journey"):
        from . import exits as exits_mod

        if exits_mod.riding(c.engine()):
            mine["pace"] = "ride"
    # The engine's door only for a line that is recognisably the move: "I nod to the
    # watchman" declares nothing either, but it is a nod, and the planner hears it.
    if at is not None and len(now) == 1 and _only_the_going(c, now[0]):
        resp = _take_the_exit(c, chip, now_text)
    else:
        resp = _plan_and_run(c, now_text, (mine,), claim, (dict(chip),))
    if resp.status_code != 200:
        return resp
    moved = _where(c) != before
    if not moved and not c.ended and not c.scene.awaiting:
        # The words before the move ran and the move did not (the engine refused the walk
        # at the end of the list): the move and everything after it come back to the pen
        # with the chip, and the engine's own sentence for why.
        move = [parts[at]] if at is not None else [_go_line(chip["name"])]
        return _unfinished(c, resp, move + later, keep_chip=True, arrived=False,
                           why=_why_it_did_not_move(c))
    if not later:
        return resp
    if c.ended or c.scene.awaiting or c.scene.in_encounter or not moved:
        return _unfinished(c, resp, later, keep_chip=False, arrived=moved)

    later_text = sequence.joined(later)
    c.transcript.append({"who": "player", "text": later_text})
    resp2 = _plan_and_run(c, later_text, (), "")
    if resp2.status_code == 200:
        return resp2
    try:
        why = json.loads(resp2.content).get("error") or ""
    except (ValueError, TypeError):
        why = ""
    c.save()
    return _unfinished(c, JsonResponse(_state(c)), later, keep_chip=False, arrived=True,
                       why=why)


def _unfinished(c, resp, later: list, keep_chip: bool, arrived: bool, why: str = ""):
    """The turn's response, plus the words it did not get to: `unfinished` carries them
    back to the pen prefilled (`text`), whether the place chip stays for the next Say
    (`keep_chip`), and the status line the page shows and speaks — "You are at the
    market. Not yet done: buy bread." — so nothing the player wrote is silently lost."""
    from gm import sequence

    todo = sequence.plain(later)
    line = f"Not yet done: {todo}."
    if arrived:
        line = f"You are at {c.engine().here().name}. {line}"
    return _with(resp, {"unfinished": {"text": sequence.joined(later), "line": line,
                                       "keep_chip": keep_chip, "why": why}})


def _gm_answer(c, question: str, shown: str):
    """Answer a question about the game from the engine, and change nothing.

    Not a turn: nothing rolls, the clock does not move, and no NPC acts because the
    player wanted to check their own hit points.

    And deliberately NOT appended to `c.history`. An out-of-character exchange sitting
    in the conversation the narrator reads is, as far as the narrator is concerned, a
    fact about the world — it would write the question and the answer into the fiction
    on the next turn. The page gets it; the model never sees it.
    """
    c.transcript.append({"who": "player", "text": shown, "kind": "aside"})
    engine = c.engine()
    kind, text = gm_answers.answer(c, engine, question)

    if kind == "gm":
        # Nothing in the state and nothing in the books. The player's ruling is that
        # they should be able to ask anything, so the question goes to the GM — clearly
        # labelled, because the one thing that must never blur is which answers are
        # facts and which are somebody's reading of them.
        text = _ask_the_gm(c, engine, question)

    c.transcript.append({"who": "gm", "kind": "aside", "text": text})
    c.save()
    return JsonResponse(_state(c))


# The engine's own handles for people, as the brief prints them: "(c1)", "c2".
_REF = re.compile(r"\(\s*(c\d+)\s*\)|\b(c\d+)\b", re.I)


def _name_the_refs(text: str, scene) -> str:
    """Every engine ref in an answer replaced with the name it stands for.

    The scene brief names people with their refs — "the apprentice minding the door
    (c1)" — and the model, handed a shorter handle, used it: measured live 2026-09-18,
    "you could focus on the immediate confrontation with c1". Repaired here from the
    scene's own actors rather than the model told not to, because told-not-to is the
    fix that has never held (CLAUDE.md). A bracketed ref after a name is dropped; a
    bare one becomes the name.
    """
    actors = getattr(scene, "actors", None) or {}
    if not actors or not text:
        return text

    def swap(m):
        ref = (m.group(1) or m.group(2)).lower()
        actor = actors.get(ref)
        if actor is None:
            return m.group(0)
        if m.group(1):
            return ""
        return str(getattr(actor, "name", "") or ref)

    return " ".join(_REF.sub(swap, text).split()).replace(" ,", ",").replace(" .", ".")


def _sources_used(hits, said: str) -> list:
    """The hits the answer actually drew on: those whose name, or most of whose name,
    appears in it. A source label is a claim about where the answer came from, and
    measured live 2026-09-18 the label under "who guards the gate" read "Dunvale (city);
    Dustgate (city); Wynreach (city)" — three weak hits the answer never touched; it had
    come from the notes on the town. Naming them as sources would have been a lie the
    code told, which is worse than one the model tells."""
    low = " ".join(str(said or "").lower().split())
    used = []
    for h in hits:
        name = str(h.name or "").lower()
        if not name:
            continue
        words = [w for w in re.findall(r"[a-z0-9'’-]+", name) if len(w) >= 4]
        if name in low or (words and sum(w in low for w in words) * 2 >= len(words)):
            used.append(h)
    return used


def _ask_the_gm(c, engine, question: str) -> str:
    """The model, grounded in the brief, answering out of character.

    No history and no worked examples, deliberately: the examples teach it to write
    scenes, which is the one thing this must not do, and the history is the fiction the
    player has just stepped out of.
    """
    from . import gm_search

    agent = GMAgent(c.world, engine)
    # The sections' facts ride on the agent the way the prose door's do (§2.2); nothing
    # out of character reads them yet, and the brief's text does not change.
    report: dict = {}
    brief = prompts.scene_brief(
        c.world, c.scene, c.location, _recent_events(c.world, c.location),
        here=engine.here(), known=engine.places(), reading=None, player_text=question,
        report=report)
    agent.brief_facts = dict(report.get("facts") or {})
    # The story's own use of a word before the rulebook's, as `answer` does: handed the
    # spell *Veil* as grounding, the model answers about the spell (2026-10-03).
    found = "\n".join(gm_answers.story_first(c, engine, question)
                      or gm_answers.look_up(c, engine, question))
    # What the character would know (2026-09-18, item 9). Public facts are answered.
    # Rumour-grade facts ride ONE secret Knowledge (local) roll per place — DC 15, the
    # Core Rulebook's "common rumour", "Try Again: No" — recorded on the scene so
    # re-asking is fruitless. Hidden facts never reach the model; with the table's
    # `knowledge_offer` rule on, the GM offers them instead, and "tell me anyway"
    # hands over what was withheld last time.
    from rules import houserules as _hr
    from rules.sheet import IllegalSheet

    said_mem = c.scene.said
    allow = {gm_search.PUBLIC}
    if re.search(r"\b(?:tell me anyway|yes,? tell me|say it anyway|go on,? tell me|"
                 r"i want (?:to know|it) anyway|spoil it)\b", question, re.I) \
            and said_mem.get("gm:withheld"):
        allow |= {gm_search.RUMOUR, gm_search.HIDDEN}
        question = str(said_mem.get("gm:withheld_question") or question)
    pc = c.scene.pc()
    place_key = str(getattr(c.location, "id", "") or "")
    if gm_search.RUMOUR not in allow and pc is not None:
        key = f"knows:{place_key}:rumour"
        if key not in said_mem:
            try:
                roll = engine.dice.d20(pc.skill_modifiers("knowledge (local)"),
                                       label="Knowledge (local), rumour", visibility="hidden")
                said_mem[key] = bool(roll.total >= 15)
            except IllegalSheet:
                # Untrained. The Core Rulebook caps an untrained Knowledge check at
                # DC 10 and rumour is DC 15: an untrained character does not know the
                # town's rumours, and this is the rule saying so, not a fault. Found
                # live (2026-09-18) as a 500 on the first `/gm` of the replay.
                said_mem[key] = False
        if said_mem.get(key):
            allow.add(gm_search.RUMOUR)
    allow = frozenset(allow)
    # The narrator's brief carries the town's Shadow Power for the narrator; the
    # out-of-character call gets it with the character's tiers only.
    brief = gm_search.redact(brief, allow,
                             facts=dict(getattr(c.location, "facts", {}) or {}))
    # What the world's own record holds on what was asked (docs/gm-questions.md). Names
    # are found, not matched, by a BM25 index over the world alone; "here" and "this
    # town" are the place the engine knows, and get its whole record as the GM's notes.
    # A question that names a thing the record has nothing on is answered by the code,
    # never by the model — which, told to say "unknown", does so about a third of the
    # time and answers confidently the rest.
    hits = gm_search.search(c.world, question)
    here = gm_search.asks_about_here(question) or gm_answers.wants_a_reading(question)
    # The place the party stands in is the default subject of a question that names
    # nobody: "who guards the gate" found a town called Dustgate; the gate meant was this
    # one. A proper name with hits is the one case the notes are left out.
    notes = (gm_search.dossier(c.world, c.location, question, allow=allow)
             if (here or not hits or not gm_search.proper_noun(question)) else "")
    if not hits and not found and not here:
        unknown = gm_search.unfiled(c.world, question)
        if unknown:
            return gm_search.nothing_filed(question, unknown, notes)
    record = gm_search.passages(c.world, hits, question, allow=allow)
    # What was kept back, and the line that says so.
    kept: list[str] = []
    if c.location is not None and notes:
        kept += [k for k, _t in gm_search.withheld_from(
            dict(getattr(c.location, "facts", {}) or {}), allow)]
    for h in hits:
        kept += [k for k, _t in gm_search.withheld_from(h.facts or {}, allow)]
    withheld_note = ""
    if kept and gm_search.HIDDEN not in allow:
        said_mem["gm:withheld"] = sorted(set(kept))
        said_mem["gm:withheld_question"] = question
        if _hr.knowledge_offer():
            withheld_note = ("\n  — There is more here your character wouldn't know yet. "
                             "Say the word (\"tell me anyway\") if you want it, or find "
                             "it out in play: ask around (Diplomacy, an hour or four).")
        else:
            withheld_note = ("\n  — Some of what the town keeps, your character has not "
                             "learned. Ask around in play: Diplomacy, an hour or four, "
                             "and it can be tried again.")
    try:
        reply = client.chat(
            prompts.out_of_character_messages(brief, question, found,
                                              notes=notes, record=record),
            agent.prose_model, agent.prose_host, as_json=False, think=False,
            temperature=0.4, num_predict=380, provider=agent.prose_provider,
            api_key=agent.prose_key)
    except ModelUnavailable as exc:
        # The deterministic backstop: the record itself, unread by any model.
        facts = "\n".join(x for x in (record, notes) if x)
        if facts:
            return f"The GM is not answering ({exc}), so here is the record as it stands:\n{facts}"
        return ("The engine has nothing filed under that, and the GM is not answering: "
                f"{exc}\nIt can always answer these from its own state: "
                + ", ".join(sorted(gm_answers.TOPICS)) + ".")
    said = _name_the_refs(" ".join(str(getattr(reply, "text", "") or "").split()), c.scene)
    if not said:
        return ("The engine has nothing filed under that, and the GM had nothing to "
                "say either. It can always answer these from its own state: "
                + ", ".join(sorted(gm_answers.TOPICS)) + ".")
    # The sources, named by the code that found them: a 13B model cites its passages
    # correctly less than half the time (ALCE), and the label is the row's to give —
    # for the rows the answer drew on, not every row the search returned.
    used = _sources_used(hits, said)
    sourced = ("\n  — from the world's record: "
               + "; ".join(f"{h.name} ({h.kind})" for h in used)) if used else ""
    return "The GM, out of character:\n  " + said + sourced + withheld_note


def _cheat(c, wish: str, shown: str):
    """Make the author's sentence true, through the engine like everything else.

    The design question the player asked out loud — "the hard part is perhaps making it
    actually give me the items and/or narrating correctly" — has one answer for both
    halves, and it is the answer this whole app is built on: the model proposes, the
    engine disposes. A cheat that reaches `engine.run` gives real items because `give`
    is the same op a shopkeeper uses, and it narrates correctly because the prose call
    is fed the resulting TELLS and the claims scrubber deletes any sentence stating a
    mechanic no tell backs. A cheat that granted nothing therefore cannot be narrated
    as though it had — for free, from machinery that already existed.
    """
    if not wish:
        return JsonResponse(
            {"error": "Say what is true. For example: /cheat I have 1000 gold"},
            status=400)
    c.transcript.append({"who": "player", "text": shown})
    agent = GMAgent(c.world, c.engine())
    # A wish that is a number is read in code: "/cheat I gain 2000 experience" did
    # nothing twice (items 1 and 20) because no op carried experience and the model
    # had nothing to plan. What the code reads never goes to the model.
    written = judgement.cheat_intents(wish, c.scene)
    if written:
        try:
            intents = judgement.keep_the_authors_numbers(
                agent.engine.validate(written, origin="author:cheat",
                                      origin_name="the author's word"), wish)
            plan = TurnPlan(narration="", intents=intents,
                            repairs=["cheat: read in code, the author's number kept"])
            return _advance(c, agent, "", plan, f"(the author writes: {wish})")
        except IntentError as exc:
            c.transcript.pop()
            return JsonResponse({"error": f"That could not be turned into anything the "
                                          f"engine can do. {exc}"}, status=502)
    try:
        plan = agent.plan_cheat(wish, location=c.location,
                                recent_events=_recent_events(c.world, c.location))
    except ModelUnavailable as exc:
        c.transcript.pop()
        return JsonResponse({"error": str(exc)}, status=503)
    except IntentError as exc:
        c.transcript.pop()
        return JsonResponse(
            {"error": f"That could not be turned into anything the engine can do. "
                      f"{exc}"}, status=502)
    # Straight into the ordinary turn from here: same resolution, same rollback on a
    # refusal, same prose call, same scrubber. The only thing a cheat skips is the
    # fiction's permission, and that was spent in the prompt.
    return _advance(c, agent, "", plan, f"(the author writes: {wish})")


def _advance(c, agent, narration, plan, player_input):
    engine = agent.engine
    # The turn either happens or it does not. Resolution applies each intent
    # before it reaches the next, so a list that raises half-way leaves the
    # earlier half standing — and this branch's careful `transcript.pop()` then
    # produced a game whose PROSE was consistent and whose BOARD was not.
    undo = c.scene.snapshot()
    try:
        resolution = engine.run(plan.intents)
        # The engine's tells land on the situation cards they concern — the one
        # place a fact gets onto a card in play, and the model is not it.
        from rules import cards as cards_mod

        cards_mod.touch_from_outcomes(c.scene, resolution.outcomes, turn=len(c.transcript))
        # And an errand's need, from the player's own words, the purse and where they
        # stand: the bed card that never moved (2026-10-03, item 25). Not the author's
        # cheat line and not Continue, which carry no words of the player's.
        said = ("" if player_input == CARRY_ON
                or str(player_input or "").startswith("(the author writes") else player_input)
        moved = cards_mod.errand_progress(c.scene, engine.places(), player_text=said or "",
                                          outcomes=resolution.outcomes,
                                          turn=len(c.transcript))
        if moved:
            c.turn_log.append({"kind": "errand", "facts": moved})
    except (IntentError, ValueError, KeyError) as exc:
        c.scene.restore(undo)
        # Validation is meant to cover everything resolution accepts, so reaching here
        # means the two have drifted apart — which has happened once already (a bare
        # string DC). Report it as a rejected turn rather than a 500, and keep the
        # transcript consistent by dropping the player line that never resolved.
        #
        # `KeyError` was missing while the NPC path three hundred lines down caught all
        # three, and it is reachable from a list that PASSED validation: travel departs
        # an actor, and a later intent in the same list still names them —
        # `self.scene.actors[ref]` raises a bare KeyError('c1'). Django has no exception
        # middleware here, so "I strike him and head for the treeline" was a 500 with a
        # traceback rather than the 502 the rest of this branch is careful to produce.
        c.transcript.pop()
        return JsonResponse(
            {"error": f"The engine refused the GM's intents: {exc}"}, status=502
        )

    # Under intents-first the prose is written in _finish, after the dice — a plan
    # narration appended here too gave the player both beats at once, measured
    # live as "You try — but the moment does not answer" directly above a beat
    # that answered perfectly well. The degraded sentence stays in the plan and
    # lands only through _finish's fallback, when the prose call truly has nothing.
    if narration and not getattr(agent, "intents_first", False):
        c.transcript.append({"who": "gm", "text": narration, "kind": "setup"})
    # What the GM offered this turn. Held on the campaign rather than in the
    # transcript because it is a live prompt, not a thing that was said — and it
    # is replaced every turn rather than accumulating.
    c.suggestions = list(getattr(plan, "suggestions", []) or [])
    c.history.append({"role": "user", "content": player_input})
    # The intents go into history stripped to what happened — op, actor, target — and
    # never the `because`. The full record went in at first, and both playtested models
    # copied their own prior reasons verbatim into new turns: "going over the wall while
    # the lamp is away" attached to a social question one turn later, "you've got an
    # opponent down" on three different attacks across two scenes. A model's own last
    # answer is the strongest template it sees, so the parts that must be written fresh
    # each turn are withheld from it. The full intents still reach the turn log.
    c.history.append({"role": "assistant", "content": json.dumps(
        {"narration": narration,
         "intents": [{"op": i.op, "actor": i.actor, "target": i.target}
                     for i in plan.intents]}
    )})
    _remember(c, resolution, player_input)
    _log_turn(c, plan, resolution)

    if resolution.awaiting:
        c.save()
        return JsonResponse(_state(c))

    return _finish(c, agent, resolution, narration, player_input, plan)



def _arm_cards(agent, c) -> None:
    """Hand the agent what the situation cards are keyed off: the last few beats the
    player read and their own line, and the turn number. The agent has the scene but
    not the transcript, and the cards scan the transcript (`rules/cards.py`)."""
    recent = [b["text"] for b in c.transcript[-4:] if b.get("text")]
    agent.recent = recent
    agent.turn = len(c.transcript)
    # And what happened in the turns the context budget has already cut, so the model
    # is told about them rather than left to notice they are missing.
    agent.ledger = c.ledger


def _realigned(records, kept, text: str) -> list[dict]:
    """Records whose line a rewrite reworded, each moved onto the one untagged quotation
    on the page that shares six in ten of its words (`"realigned": True`)."""
    def words(s: str) -> set[str]:
        return set(re.findall(r"[a-z']+", str(s or "").lower().replace("’", "'")))

    lines = speech_mod.lines(text)
    free = [ln for ln in lines if ln.strip() and not speech_mod.speaker(kept, ln)]
    out: list[dict] = []
    for r in records or []:
        if not r.get("who") or r in kept or any(speech_mod.speaker([r], ln) for ln in lines):
            continue
        mine = words(r.get("line"))
        near = [ln for ln in free if mine and len(mine & words(ln))
                / max(1, len(mine | words(ln))) >= 0.6]
        if len(near) == 1:
            out.append({**r, "line": near[0].strip(), "realigned": True})
            free.remove(near[0])
    return out


def _finish(c, agent, resolution, narration, player_input, plan, hand_over=True,
            player_text=None):
    """Narrate what the engine decided, then let the world answer.

    `hand_over` is False for an action that does not end your turn — a free action, a
    toggle, a swift. The combat panel accepted `end_turn: false` and this ran the NPC
    turns anyway, so forming the blood armament (a free action) handed the bear a swing:
    the round moved on while the player still had their standard action in hand.
    """
    if resolution.awaiting:
        c.save()
        return JsonResponse(_state(c))

    # Which door this turn came through, for the after-the-beat steps (play/aftermath):
    # Continue carries no words of the player's, so a step that logs them logs nothing.
    door = "carry_on" if player_input == CARRY_ON else "turn"
    # `player_text` is "" for a button (the Spells tab, the combat panel): "I cast Burning
    # Hands" written by a button is not the player's own words, and the after-the-beat
    # steps must not read it as if typed (fix-interfaces §3.4, S3's finding).
    if player_text is None:
        player_text = "" if door == "carry_on" else (player_input or "")
    attached = _attached_this_turn(c)

    # The thread first, so the brief below states the engagement this very turn
    # declared — "I follow the guards" must constrain the beat that answers it.
    judgement.update_thread(c.scene, player_input,
                            [o.op for o in resolution.outcomes])
    judgement.note_heat(c.scene, resolution.outcomes, player_input)
    # Coin that changed hands is an agreement the room remembers, written by the engine
    # from its own tell and the player's own "for …" — never by the model. Read back
    # into the scene block until the party moves rooms (item 22).
    for o in resolution.outcomes:
        m = re.search(r"^(.+?) hands (.+?) (\d+) × (gp|sp|cp|pp)\b", o.tell or "")
        if m and player_input and player_input != CARRY_ON:
            tail = re.search(r"\bfor\s+([^.!?]{3,80})", judgement.redact_speech(player_input), re.I)
            line = f"{m.group(1)} paid {m.group(2)} {m.group(3)} {m.group(4)}" \
                   + (f" for {tail.group(1).strip()}" if tail else "")
            agreed = list(c.scene.agreements or [])
            if line not in agreed:
                agreed.append(line)
            c.scene.agreements = agreed[-5:]
    # Bodies age out on their own: two turns' grace to loot and mourn, then the
    # scene lets them go whether or not the player ever says the word "leave".
    swept = agent.engine.tidy_the_fallen()
    if swept:
        c.transcript.append({"who": "gm", "text": " ".join(swept),
                             "kind": "consequence"})
    # And the breath anybody under the water is holding. Beside the fallen because it is
    # the same kind of thing — the engine resolving what happens to a body while nobody
    # is acting on it — and said out loud every rung of the way down, because drowning is
    # the one death in the game that arrives on a schedule and a schedule the player
    # cannot see is just a trapdoor.
    for line in agent.engine.breathe():
        c.transcript.append({"who": "gm", "text": line, "kind": "consequence"})
    # Walking away lets the scene go: the dying resolve off-screen and the fallen
    # stay where they fell, whether or not the walk crossed a biome line.
    if judgement.player_departs(player_input):
        left = agent.engine.leave_behind()
        judgement.clear_cast(c.scene)
        if left:
            c.transcript.append({"who": "gm", "text": " ".join(left),
                                 "kind": "consequence"})

    # A companion the player spoke TO answers before the prose is written, out of a fight
    # (in one, their own turn does): what they do is decided as themselves, resolved by
    # the engine, and handed to the prose as tells and a fact (gm/companions.py).
    # First, what the player's words do to a confidence a companion owes (gm/confide.py):
    # asked for, it is their answer this beat; brushed off, it waits.
    heard = _companions_heard(c, player_text, door)
    answered = _companions_answer(c, agent, player_text, resolution, plan, heard=heard)
    outcomes = [o for o in resolution.outcomes if o.tell]
    if getattr(agent, "intents_first", False):
        # The experiment's other half: call 1 wrote no prose, so this call writes the
        # whole turn — and it writes it knowing what the dice did. Runs whether or not
        # there are tells, because a `narrate_only` turn with no prose is a blank page
        # and most town turns are `narrate_only`.
        # Everyone here has a name behind their descriptor and a face before the
        # brief is written — including the people a save holds from before the
        # fields existed (c11 'woman', c16 'woman' on the 2026-09-18 save).
        judgement.name_the_nameless(c.scene, c.world)
        # What each brief section printed, for the narrator checks to read what the model
        # was shown (`BeatContext.brief_facts`, §2.1), and what the player attached to the
        # turn. Handed over as attributes, the way `buying` is, so no agent signature moves.
        report: dict = {}
        brief = prompts.scene_brief(c.world, c.scene, c.location,
                                    _recent_events(c.world, c.location),
                                    here=agent.engine.here(),
                                    known=agent.engine.places(),
                                    # The prose sees the cards in play, never the
                                    # GM's secret ones.
                                    recent=[b["text"] for b in c.transcript[-4:]],
                                    turn=len(c.transcript),
                                    # The one turn a true name is shown: the turn the
                                    # player asks for it (2026-09-19, item 31).
                                    names_for=judgement.names_asked_for(c.scene,
                                                                        player_input),
                                    # And the world's answer when the player went looking
                                    # for somebody who is not here (item 29).
                                    absent=judgement.absent_answer(c.scene, c.world,
                                                                   player_input),
                                    # And the counter the turn opens, when the player
                                    # set out to buy something (`_trade_offer`).
                                    buying=_buying_note(c, player_input),
                                    reading=getattr(agent, "reading", None),
                                    player_text=player_text, report=report)
        agent.brief_facts = dict(report.get("facts") or {})
        agent.attachments = attached
        # The model's own recent prose — the narrator's beats only, with the sentences
        # WE appended to them (a death line, a thread anchor) taken back out. Shown its
        # own backstop or the engine's award line as "what you narrated", the model
        # learns the template (docs/narrator-guards.md D4). Twelve beats, because the
        # phrase check reads twelve and was being handed four.
        earlier = narration_mod.own_prose(c.transcript)
        # Last in the prompt, after the tells (docs/narrator-guards.md D6, D7): the
        # scene as the engine holds it this moment, and — out of fights only, so it
        # can never cost a rewrite mid-combat — the one open matter nearest to hand,
        # chosen in code by how many of the scene's facts point at it.
        from rules import cards as cards_mod

        pull = None
        if not c.scene.in_encounter:
            pull = cards_mod.thread_to_pull(
                c.scene, recent=[b["text"] for b in c.transcript[-4:]],
                player_text=player_input, tells=[o.tell for o in outcomes],
                turn=len(c.transcript))
        # The purchase the counter's screen opens for after this beat, if any: the review
        # holds the prose to leaving it unsettled (narration.hands_over_goods).
        # Every declared purchase, whether or not a counter opens: nothing is bought in
        # the prose either way.
        agent.buying = judgement.purchase_sought(player_input)
        try:
            text, repairs, prose_attempts = agent.narrate_turn(
                resolution.outcomes, player_input, brief, earlier,
                # On Continue the standing action is a fact of the beat, last in the
                # prompt with the scene as it stands (the ruling, 2026-09-18).
                scene_now=(prompts.scene_now(
                               c.scene, was_clock=getattr(resolution, "clock_before", None))
                           + (("\n\n" + judgement.standing_action(c.scene))
                              if player_input == CARRY_ON and judgement.standing_action(c.scene)
                              else "")
                           + (("\n\nWHAT A COMPANION DOES WITH WHAT YOU SAID (decided by "
                               "them, as themselves; the beat shows it in their manner "
                               "and does not change it):\n"
                               + "\n".join(f"{a.name}: {said}" for a, said in answered))
                              if answered else "")),
                pull=pull,
                claim=str(getattr(agent, "false_claim", "") or ""),
                shown=narration_mod.own_prose(c.transcript, tagged=True),
                # How far in this beat is: which of the table's intimate-scene passages
                # are shown turns over with it (gm/intimate.py `select`).
                beat=len(c.transcript))
        except ModelUnavailable:
            text, repairs, prose_attempts = "", [], []
        # The prose call's suggestions win when it made any: under intents-first
        # the plan wrote none, and the page showed no options at all.
        offered = list(getattr(agent, "last_suggestions", []) or [])
        if offered:
            c.suggestions = offered
        # Into the ledger, not the void: a live holding-line turn used to leave
        # no record of why the prose whiffed — the attempts were unpacked into
        # `_` and dropped, so the one diagnosable artefact never existed.
        c.turn_log.append({
            "kind": "prose",
            "chars": len(text or ""),
            # Which open matter was put in front of the model, if any, so an audit
            # can say how often the beat carried it.
            "pull": str((pull or {}).get("title") or ""),
            # How the pull meant the thread to reach the player, and whether the beat gave
            # it up (design D). Only when the pull says: every row before D reads the same.
            **{k: (pull or {})[k] for k in ("approach", "yielded") if k in (pull or {})},
            "repairs": list(repairs or []),
            # The raw reply's tail as well as its head: a reply cut off mid-word shows
            # only at its end, and the head alone could not show "…They'" (item 6,
            # 2026-09-30, found only by reproducing the call). `raw_chars` says how long
            # the whole reply was, which is how a grammar ceiling shows itself.
            "attempts": [{"kind": a.kind, "seconds": round(a.seconds, 1),
                          "model": a.model, "note": (a.note or "")[:300],
                          "raw": (a.raw or "")[:300],
                          **({"raw_tail": (a.raw or "")[-300:]}
                             if len(a.raw or "") > 300 else {}),
                          "raw_chars": len(a.raw or "")}
                         for a in prose_attempts],
            # Whether the intimate scene's briefing fired this beat and how many
            # characters of the owner's passages went in — counts only, never the text
            # (gm/intimate.py). On every beat, so an audit can count the misfires.
            "intimate": (agent.intimate.as_log()
                         if getattr(agent, "intimate", None) is not None else
                         {"fired": False, "mode": "default", "why": "", "demos": 0,
                          "demo_chars": 0}),
        })
        _intimate = getattr(agent, "intimate", None)
        if _intimate is not None and _intimate.fired and not _intimate.as_log()["demos"]:
            c.turn_log.append({"kind": "intimate",
                               "note": "no demonstrations on file",
                               "file": str(intimate_mod.demonstrations_path())})
        elif _intimate is not None and _intimate.mode == "fade":
            c.turn_log.append({"kind": "intimate",
                               "note": "faded: a child is present or named"})
        if not text:
            # Raw tells name the PC — "Initiative: Kesst Vayr..." — and the
            # gemma4 fight audit showed them shipping third-person whenever the
            # prose call whiffed. The fallback gets the same person treatment
            # the prose does.
            pc = c.scene.pc()
            text = " ".join(plain_tell(o.tell) for o in outcomes)
            if pc is not None and text:
                text, _ = narration_mod.pc_to_second_person(text, pc.name)
        if not text and plan is not None and plan.narration:
            # A degraded turn (every model attempt failed) carries its honest
            # sentence in the plan; with no tells to dress, this is the one place
            # it can reach the page.
            text = plan.narration
        # A turn where the player SPOKE gets an answer in the fiction, never the
        # parser's holding line. Measured on the 2026-09-08 playtest: every line the
        # player wrote as speech came back as the holding line while actions in the
        # same session worked. TADS 3 guarantees a lowest-priority catch-all topic for
        # exactly this, and Façade carries global deflection mix-ins beside its
        # beat-specific ones; no tradition accepts silence here. See
        # docs/speech-vs-action.md and gm/narration.unanswered_speech.
        # What the floor writes is ours, and is marked as ours on the transcript beat
        # (`added`) so the next prose call is not shown a holding line as "what you
        # narrated just before this". Measured on the 2026-09-17 baseline: the
        # holding line's own six-word phrases recurred across beats like any other tic.
        ours: list[str] = []

        def _floor(reason: str) -> str:
            if judgement.was_speech(player_input):
                repairs.append(f"{reason}: the player spoke, so the answer is theirs")
                line = narration_mod.unanswered_speech(
                    player_input,
                    [a.name for a in c.scene.actors.values() if not a.is_pc],
                    turn=len(c.transcript))
            else:
                repairs.append(f"{reason}: replaced with a holding line")
                line = ("The moment holds — nothing new shows itself just yet. "
                        "What do you do?")
            ours.extend(narration_mod._sentences(line))
            return line

        if not text:
            # A turn may NEVER answer with silence. Measured live: "I talk to
            # the woman" produced no beat at all — the prose call whiffed, there
            # were no tells, no degraded sentence, and the empty string skipped
            # every floor below because they all lived inside `if text`.
            text = _floor("empty turn")
        # Adults only, without exception, whatever the table's content setting: a beat
        # that reads as sexual while a child is in the scene or in the beat is discarded
        # whole — never trimmed, never repaired — and the turn gets the holding line.
        # A beat written under the intimate briefing counts as sexual whatever words it
        # chose: `narration.intimate` is a vocabulary, and measured on the owner's own
        # scene it read none of five intimate beats as sexual, because they were
        # euphemistic. The briefing never fires with a child present or named
        # (`intimate.decide`); this is the guard under it for a child the beat itself
        # brings in.
        briefed = bool(getattr(getattr(agent, "intimate", None), "fired", False))
        if text and (briefed or narration_mod.intimate(text)) \
                and judgement.a_child_in(c.scene, text):
            c.turn_log.append({"kind": "refused-beat",
                               "why": "sexual content with a child in the scene"})
            ours.clear()
            text = _floor("discarded: sexual content with a child in the scene")
        added = list(getattr(agent, "last_added", []) or [])
        if text and answered:
            # The companion's answer on the page, whatever the prose chose. Measured on
            # the companions replay: Bob's answer was "Bob moves to the door, standing
            # perfectly still", handed to the prose as a fact, and the beat never
            # mentioned Bob at all. Detected (the beat does not name them) and put
            # back in their own answer's words, before the closing question.
            from gm import companions as companions_mod

            before = text
            text, put = companions_mod.answers_on_the_page(text, answered)
            if put:
                repairs.append(f"companion answer left off the page: put back for "
                               f"{', '.join(put)}")
                added += narration_mod.added_sentences(before, text)
        if text and not c.scene.in_encounter:
            # How a companion did what they did in this beat, and their own remarks
            # (the owner's rulings of 2026-10-01; gm/companions.py).
            text, more_repairs, more_added = _companions_on_the_page(
                c, agent, text, answered, plan, resolution, heard=heard,
                player_text=player_text)
            repairs += more_repairs
            added += more_added
        if text:
            before = text
            text, anchored = narration_mod.keep_the_thread(text, c.scene.thread,
                                                           said=c.scene.said)
            if anchored:
                repairs.append(f"the thread held: re-tethered {anchored!r}")
                added += narration_mod.added_sentences(before, text)
            # The engine's place, not the thread's: `thread["where"]` was a second
            # writer of where the party is and is gone. Skipped on the turn the party
            # ARRIVES — `here()` is already the destination when the prose runs, and
            # the rewrite would turn "you walk into the tavern" into "walk through
            # the tavern" on the one beat that is genuinely an arrival.
            arrived = any(
                o.op == "travel" and any(
                    e.get("kind") == "biome" and e.get("place") != e.get("was_place")
                    for e in (o.effects or []))
                for o in resolution.outcomes)
            text, rewrit = narration_mod.already_there(
                text, "" if arrived else agent.engine.here().name)
            if rewrit:
                repairs.append("arrivals at the place they already stand: "
                               f"rewrote {len(rewrit)}")
            # The floor of last resort. Measured live on a Continue: the model
            # echoed the instruction itself, the groomers compressed the echo,
            # and the beat that shipped was "You take scene on." — four words
            # against a 600-character scene floor every earlier gate is supposed
            # to hold. A beat this short with no dice behind it is not a beat.
            if len(text.strip()) < 60 and not outcomes:
                text = _floor("beat too short to stand")
            # The beat is final; whoever it introduced is on the books now —
            # and on the board: a noted person the engine does not hold cannot
            # be attacked, addressed or found again.
            # Whoever the plan introduced is on the ledger first, so the prose describing
            # them reads as somebody already here, not a newcomer to book again.
            booked_in = judgement.book_introduced(c.scene, resolution.outcomes,
                                                  turn=len(c.transcript))
            # The over-use measurement (an op always on offer gets over-called — Labyrinth,
            # When2Call): who the plan introduced, and whether the prose then used them.
            if booked_in:
                c.turn_log.append({"kind": "introduced", "who": booked_in,
                                   "in_prose": [bool(judgement._role_head(w)) and
                                                judgement._role_head(w) in text.lower()
                                                for w in booked_in]})
            # The ledger the brief reads ("ALSO PRESENT"). Not who is new or here: since
            # 2026-10-03 that is the beat reader's answer (gm/beat_reader.py), recorded and
            # given bodies in the "people" stage below (play/aftermath/seen_people.py).
            # `record_people` used to do it here from this ledger's phrases, deciding seen
            # or heard with `seen_in_beat`'s cue words and `only_a_predicate` — and "He is
            # a large man" made a second smith the day the last of those rules was written.
            judgement.note_cast(c.scene, text, turn=len(c.transcript))
            from rules import population

            # Every search for somebody that found nobody this turn, so the synonym table
            # (content/people/synonyms.json) grows from what real play missed.
            c.turn_log.extend(population.drain_misses())
            # The quirk rests once the page has shown it (engine-held cadence, like a
            # `respeakdelay`: a small model cannot count "now and then"), and a trait the
            # page names outright instead of showing is counted — measured before any
            # repair is written for it.
            shown = population.note_quirks_shown(c.scene, text, len(c.transcript))
            named = {r: population.traits_named(population.of_ref(c.scene, r), text,
                                                c.scene.actors[r].name)
                     for r in c.scene.actors if population.of_ref(c.scene, r)}
            named = {r: w for r, w in named.items() if w}
            if shown or named:
                c.turn_log.append({"kind": "manner", "quirks_shown": shown,
                                   "traits_named": named})
            _log_mentions(c, agent)
            attribution = getattr(agent, "attribution", None)
            # A speaker tag the beat reader contradicts is withdrawn before anything reads
            # it — the bodies of the "people" stage and the hails after it (item 15,
            # 2026-10-03: six beats of "the man" tagged to the servant, each one opening a
            # conversation with him). Where `judgement.doubt_tags` ran its patterns.
            from gm import beat_reader

            if isinstance(attribution, beat_reader.Reading):
                c.turn_log.extend(beat_reader.reconcile_tags(attribution, agent.last_said))
            # A name given in play renames the panel ("call me Kael", 2026-09-18) — read
            # by the beat reader and taken in the "people" stage, after the newcomers it
            # names have bodies (play/aftermath/seen_people.py). `apply_introductions`
            # read it here by pattern until 2026-10-03.
            # The after-the-beat steps' "people" stage (play/aftermath, §2.3): here, and
            # not with the "beat" stage below, because a speaker the page made real has to
            # exist before `hailed_by` reads who spoke to the player. `said` is the live
            # list `hailed_by` reads next.
            _after_the_beat(c, agent, "people", door, text=text, said=agent.last_said,
                            player_text=player_text, attachments=attached,
                            attribution=attribution, outcomes=resolution.outcomes,
                            turn=len(c.transcript))
            # Somebody who spoke to the player in this beat is in conversation with
            # them from here, until the player takes their leave (2026-09-24). Through
            # the engine's one door, so the panel and the refusals read the same state.
            for ref in judgement.hailed_by(c.scene, text, said=agent.last_said):
                who = c.scene.actors.get(ref)
                opened = c.engine().join_talk(who, how="they spoke to you") if who else ""
                if opened:
                    repairs.append(f"in conversation: {who.name} spoke to the player")
            # And a face for anybody this beat used and did not describe — not only
            # whoever arrived in it. The condition is "not described yet", held on the
            # actor (`described`), so the keeper behind the counter, the opening
            # companion, a scheme's cast and everyone promoted on an earlier turn are
            # covered as well as a fresh arrival (2026-09-19, item 32: "Drenn Ironvale
            # and the merchant are in scene without having been described"). The line is
            # the world's own — the resident's Appearance fact, or their people's body
            # line — so the next beat cannot re-invent them.
            owed = set(judgement.settle_descriptions(c.scene, text, player_input, attribution=getattr(agent, "attribution", None)))
            # The one the player looked over owes a face too, whether or not she is new
            # here: "I look the woman in the doorway over carefully".
            looked = judgement.examined(player_input, c.scene)
            if looked and looked in c.scene.actors and narration_mod.faceless(text, c.scene.actors[looked].name):
                owed.add(looked)
            # One appended line a beat, and never the same sentence twice. Measured live
            # 2026-09-19 (run 4 of the group-7 check): the beat ended with "The woman:
            # Orc: Powerfully built, prominent lower tusks…" and then "The girl with the
            # cup: Orc: Powerfully built, prominent lower tusks…" — identical, because the
            # export gives the Orc people exactly ONE body sentence and there is nothing
            # to vary. The backstop is a floor, not an appendix: whoever is still owed one
            # gets it on the beat they next act in, and the person the player LOOKED at is
            # taken first because they asked.
            for ref in ([looked] if looked in owed else []) + sorted(owed - {looked}):
                who = c.scene.actors.get(ref)
                if who is None or not getattr(who, "appearance", ""):
                    continue
                # The people's line once per campaign; after that this person's own
                # details (rules/faces.py, "a people described once").
                from rules import faces as faces_mod

                shown = faces_mod.for_the_page(
                    who.appearance,
                    faces_mod.people_seen_before(who, c.scene.people.values()))
                line = narration_mod.a_face_for(who.name, shown)
                if not line or who.appearance in text or shown in text:
                    # Their people's line is already on the page. Not marked described —
                    # it may have been said of somebody else — but not said twice either.
                    continue
                # Where the person is first seen, not at the end of the beat. Reported
                # 2026-09-22: "the description of Ashla is tagged to the end as an after
                # thought ... if she was next to drenn she should have been described
                # right after i saw drenn."
                text = narration_mod.place_the_face(text, who.name, line, ref=ref,
                                                    attribution=attribution)
                ours.append(line)
                who.described = True
                repairs.append(f"nobody stands here undescribed: added {who.name}'s "
                               f"face from the world's own body line")
                break
            # Ruskin's write-back: a card the beat carried is marked mentioned, and
            # its urgency starts again from here. The cooldown falls out of it.
            cards_mod.note_mentions(c.scene, text, turn=len(c.transcript))
            # And whoever the beat says stopped watching is in the fight, with their
            # kind: "the second guard draws" is a second guard on the initiative.
            for ref, side in judgement.joiners(c.scene, text):
                if agent.engine.join_fight(ref, side):
                    repairs.append(f"{c.scene.actors[ref].name} joined the fight "
                                   f"on {'your' if side == 'pc' else 'their'} side")
                    agent.engine.rally(ref)
            # A blow at the player is declared in the plan now, and rolled before the
            # prose (`Engine._their_first_blow`); the prose never opens a fight. Measured
            # 2026-09-25 on the provoke script: the plan declared the real blows, and the
            # one blow this door read out of the prose was a man slamming his fist on
            # the bar — a fight opened on furniture. The prose call rewrites or cuts an
            # undeclared blow (`GMAgent._undeclared_blows`); anything still read here is
            # logged, never opened.
            struck_lines: list[str] = []
            for ref, sentence in judgement.attacked_by(c.scene, text):
                c.turn_log.append({"kind": "npc-opener", "ref": ref,
                                   "sentence": sentence[:300], "opened": False,
                                   "note": "a blow read in the prose and not declared "
                                           "in the plan: logged, not opened"})
            # `added`: the sentences that are ours, so the next turn's `earlier` can
            # leave them out of what the model is shown as its own.
            added = added + ours
            # Who said which line, as the prose call tagged it — the lines still in the
            # beat after every rewrite, so the record never names a line the page lacks.
            # Once each: a rewrite that kept a tagged line lifts it a second time.
            said = []
            for r in getattr(agent, "last_said", None) or []:
                if r["who"] and r not in said and any(speech_mod.speaker([r], ln)
                                         for ln in speech_mod.lines(text)):
                    said.append(r)
            # A tagged line a rewrite reworded is re-aligned to the one untagged quote
            # that is mostly its words, rather than dropped: at beat 49 of the
            # 2026-09-30 playtest a polish edited a tagged quote and the line lost its
            # speaker (item 1, cause 4). Conservative on purpose — six in ten words
            # shared, and exactly one candidate — because a wrong speaker is worse
            # than none.
            said += _realigned(getattr(agent, "last_said", None) or [], said, text)
            c.transcript.append({"who": "gm", "text": text, "kind": "setup",
                                 **({"added": added} if added else {}),
                                 **({"said": said} if said else {})})
            # The measurement the tags are judged by: how many lines the prose call tagged,
            # how many were booked from the page, and who hailed the player.
            c.turn_log.append({"kind": "speech-tags",
                               # The model's tags only: a line `speaker_real` read off
                               # the page (`"from": "page"`) is counted apart, so the
                               # tagging rate stays the model's (G2, 2026-09-29).
                               "tagged": len({(r["who"], r["to"], r["line"])
                                              for r in agent.last_said
                                              if r["who"] and r.get("from")
                                              not in ("page", "interject", "confide")}),
                               **({"read_off_page": read_off} if (read_off := sum(
                                   1 for r in agent.last_said
                                   if r.get("from") == "page")) else {}),
                               # Tags naming nobody here: the model's own claim, kept.
                               "unknown_refs": sorted({r.get("was", "")
                                                       for r in agent.last_said
                                                       if not r["who"]}),
                               "on_the_page": len(said),
                               "lines": len(speech_mod.lines(text)),
                               # Every hail is a booked line now (the tags, and the beat
                               # reader's speakers); `hails_guessed`, the untagged-line
                               # pattern it was measured against, retired with it.
                               "hails_tagged": judgement.hailed_by(c.scene, text, said=said)})
            # The "beat" stage: the beat is on the transcript now, with the lines kept on
            # it, so a step can index it (the conversation log, F) and `c.suggestions` is
            # already this turn's (D).
            _after_the_beat(c, agent, "beat", door, text=text, said=said,
                            player_text=player_text, attachments=attached,
                            attribution=attribution, outcomes=resolution.outcomes,
                            beat_index=len(c.transcript) - 1,
                            # The number the rest of this beat's bookkeeping used: the
                            # transcript's length before the beat went onto it.
                            turn=len(c.transcript) - 1)
            c.history.append({"role": "assistant", "content": text})
            for line in struck_lines:
                c.transcript.append({"who": "gm", "text": line, "kind": "consequence"})
            # What became of a struck item, when the beat did not say. Read off the
            # tell's own words (law three): "…'s club takes 15 through hardness 5
            # (0/10 left): destroyed — in pieces." Measured on the third live replay:
            # the club was in pieces and the beat said the wood "groaned".
            for o in outcomes:
                m = re.search(r"'s (\w[\w ]*?) takes \d+ through hardness", o.tell or "")
                if m and not narration_mod.item_fate_on_the_page(text, m.group(1)):
                    line = plain_tell(next(
                        s for s in re.split(r"(?<=[.!?])\s+", o.tell)
                        if "through hardness" in s))
                    pc = c.scene.pc()
                    if pc is not None:
                        line, _ = narration_mod.pc_to_second_person(line, pc.name)
                    c.transcript.append({"who": "gm", "text": line,
                                         "kind": "consequence"})
                    repairs.append(f"the item's fate left off the page: said what became "
                                   f"of the {m.group(1)}")
    elif outcomes:
        try:
            text, attempt = agent.narrate_outcome(narration, outcomes, player_input)
        except ModelUnavailable:
            # The tell renders raw and play continues. The narrator is a garnish on a
            # game that works without it.
            text, attempt = "", None
        if not text:
            pc = c.scene.pc()
            text = " ".join(plain_tell(o.tell) for o in outcomes)
            if pc is not None and text:
                text, _ = narration_mod.pc_to_second_person(text, pc.name)
        c.transcript.append({"who": "gm", "text": text, "kind": "consequence"})
        c.history.append({"role": "assistant", "content": text})

    if plan is not None:
        _log_turn(c, plan, resolution, replace=True)
    else:
        c.turn_log.append(history_mod.stamp(c, {
            "kind": "resolution", "outcomes": [o.as_dict() for o in resolution.outcomes]}))

    # A battle that just JOINED is not a turn that just ENDED. The deferred first
    # swing left the player holding the action they declared; running the NPC loop
    # here would hand the other side the first blow the announcement promised the
    # player. They act at the combat panel; the loop runs when that turn ends.
    # Not a battle a COMPANION joined in answer to the player's words (`_companions_answer`):
    # the companion holds the turn they declared, and the order carries on from them to
    # the player — left un-run, the turn sat on Bob while the player typed (replay,
    # 2026-10-01).
    from gm import companions as companions_mod

    joined = any(e.get("kind") == "battle_joined"
                 and not companions_mod.is_companion(c.scene.get(e.get("ref") or ""))
                 for o in resolution.outcomes for e in (o.effects or []))
    if hand_over and not joined:
        _run_npc_turns(c, agent)
    if plan is not None:
        c.last_intent_signature = judgement._signature(plan.intents)
    c.save()
    # The turn is finished and on disk; now the event watcher may look at it. A daemon
    # thread and snapshots only — this call never blocks the response, and the model's
    # answer lands through `watcher.drain` on a later request, staleness-checked.
    watcher.kick(c)
    return JsonResponse(_state(c))


def _companions_heard(c, player_text: str, door: str) -> dict:
    """What the player's words this turn do to a confidence a companion owes
    (`confide.heard`): {"invited", "brushed", "not_ready"} refs. Out of a fight and on a
    typed turn only; a brush-off is logged, because "not now" leaving a share waiting is a
    rule the player cannot see."""
    from gm import confide as confide_mod

    empty = {"invited": [], "brushed": [], "not_ready": []}
    if c.scene.in_encounter or door != "turn":
        return empty
    got = confide_mod.heard(c.scene, c.transcript, player_text, len(c.transcript))
    for ref in got["brushed"]:
        c.turn_log.append(history_mod.stamp(c, {"kind": "companion-confide", "ref": ref,
                                                "event": "brushed off"}))
    return got


def _companions_answer(c, agent, player_text: str, resolution, plan,
                       heard: dict | None = None) -> list[tuple]:
    """Out of a fight, each companion the player's words were spoken TO answers, as
    themselves, before the prose is written. Returns (actor, their answer) pairs for the
    prose call's facts and its backstop; their resolved outcomes join `resolution` so the
    prose has the tells.

    The owner's ruling (2026-10-01): companions "take spoken orders as their character
    dictates they would or would not and interpret those orders according to their
    character as well". Measured before this (companions replay): "Drover, sneak up
    behind that thug and lift his purse for me" was planned as the player's `say` and a
    `narrate_only` — nobody decided anything, and the prose had the timid drover melt
    into the shadows like a cutpurse.

    Detected in code (`companions.addressed`: a vocative, or a verb of telling before the
    name), answered by one targeted call each (`GMAgent.companion_answer`), resolved by the
    engine. A companion the plan already acts for is left to the plan; at most two answer
    a line. Any failure costs only the answer — the prose then writes the moment as ever.
    """
    from gm import companions as companions_mod

    scene = c.scene
    if scene.in_encounter or not (player_text or "").strip() or resolution.awaiting \
            or player_text == CARRY_ON:
        return []
    planned = {i.actor for i in (getattr(plan, "intents", None) or []) if i.actor}
    heard = heard if heard is not None else {}
    lines: list[tuple] = []
    # Asked what was on their mind, a companion's answer IS the confidence, written here,
    # before the prose, so the beat carries it as their answer. Measured on the first live
    # replay: written after the prose instead, the beat had already answered "Drover,
    # what is it?" in the drover's voice with a story about a spooked girl in a cage, and
    # the confidence followed it — two answers, one invented.
    from gm import confide as confide_mod

    for ref in (heard.get("invited") or ())[:1]:
        due = confide_mod.due(scene, c.transcript, resolution.outcomes, invited=[ref])
        actor = scene.get(ref)
        if not due or actor is None:
            continue
        agent.engine = c.engine()
        said = _confide_line(c, agent, due, place=agent.engine.here(),
                             player_text=player_text)
        if said:
            heard["confided"] = (ref, said)
            heard["confided_topic"] = due["topic"]
            lines.append((actor, said))
    for ref in companions_mod.addressed(scene, player_text)[:2]:
        actor = scene.get(ref)
        if actor is None or ref in planned:
            continue
        # Asked for what they said was on their mind: their answer this beat is the
        # confidence itself (above), never an ordinary answer call, which is not told
        # their life and would make one up. When the confidence would not hold this beat,
        # their ordinary answer is told they are not ready to say, for the same reason.
        if (heard.get("confided") or ("",))[0] == ref:
            continue
        agent.engine = c.engine()
        try:
            answer = agent.companion_answer(ref, player_text, location=c.location,
                                            recent_events=_recent_events(c.world,
                                                                         c.location),
                                            not_ready=ref in (heard.get("not_ready") or ())
                                            or ref in (heard.get("invited") or ()))
        except (ModelUnavailable, IntentError) as exc:
            c.turn_log.append({"kind": "companion-answer", "ref": ref,
                               "error": str(exc)[:400]})
            continue
        undo = scene.snapshot()
        try:
            more = agent.engine.run(answer.intents)
        except (IntentError, ValueError, KeyError) as exc:
            scene.restore(undo)
            c.turn_log.append({"kind": "companion-answer", "ref": ref,
                               "error": f"resolution: {str(exc)[:400]}"})
            continue
        if more.awaiting:
            # Only the player's own dice suspend; a companion's never should. Undone
            # rather than left half-resolved if it ever does.
            scene.restore(undo)
            continue
        resolution.outcomes.extend(more.outcomes)
        # An answer that OPENED a fight is told by the engine ("Battle is joined: Bob
        # squares off against the thug. Nothing has landed yet"); its wind-up handed to
        # the prose as a fact ("strikes at the thug's midsection") had the page land
        # the blow no die had rolled (replay, 2026-10-01). The tell carries it alone.
        opened = any(e.get("kind") == "battle_joined"
                     for o in more.outcomes for e in (o.effects or []))
        c.turn_log.append(history_mod.stamp(c, {
            "kind": "companion-answer", "ref": ref, "said": player_text[:400],
            "seconds": round(answer.seconds, 1),
            "attempts": [{"kind": a.kind, "seconds": round(a.seconds, 1),
                          "model": a.model} for a in answer.attempts],
            "rejections": list(answer.rejections),
            "narration": answer.narration,
            "intents": [i.as_dict() for i in answer.intents],
            "outcomes": [o.as_dict() for o in more.outcomes]}))
        if answer.narration and not opened:
            lines.append((actor, answer.narration))
    return lines


def _companions_on_the_page(c, agent, text: str, answered, plan, resolution, *,
                            heard: dict | None = None, player_text: str = ""
                            ) -> tuple[str, list[str], list[str]]:
    """Out of a fight, after the beat is written: (1) a companion who acted in it — the
    one the player spoke to (`answered`), or one the plan acted for — does it in their
    own manner on the page, repaired by one targeted call when the beat reads as if
    anybody did it; (2) at most one companion speaks up unasked, when the code says a
    remark is due (`companions.interjection_due`), put before the closing question and
    booked in the conversation log as their speech (`src: "interject"`).

    The owner's rulings, 2026-10-01: "they can comply but it should be narrated that they
    did so in a way that was timid and matched their background" and "they should also
    interject their opinions on the things going on or the places we go". Returns
    (text, repairs, sentences that are ours)."""
    from gm import companions as companions_mod

    scene = c.scene
    repairs: list[str] = []
    added: list[str] = []
    acted = [a for a, _ in answered or ()]
    for i in getattr(plan, "intents", None) or ():
        who = scene.actors.get(i.actor or "")
        if (companions_mod.is_companion(who) and i.op != "narrate_only"
                and who not in acted):
            acted.append(who)
    for who in acted[:2]:
        pole = companions_mod.dominant_pole(scene, who)
        if not pole or not companions_mod.their_sentences(text, who) \
                or companions_mod.shows_manner(text, who, pole):
            continue
        op = next((i.op for i in getattr(plan, "intents", None) or ()
                   if i.actor == who.ref), "")
        before = text
        text, notes, _ = agent.manner_of(text, who, ordered=True, op=op)
        repairs += notes
        added += narration_mod.added_sentences(before, text)

    # Whether the party walked somewhere new this beat: the travel outcome's own record,
    # read the way the `already_there` check below reads it (engine bookkeeping, kept out
    # of gm/ by the third law's ratchet).
    moved = any((o.op in ("journey", "call_on") and o.status != "refused")
                or (o.op == "travel" and any(
                    e.get("kind") == "biome" and e.get("place") != e.get("was_place")
                    for e in (o.effects or [])))
                for o in resolution.outcomes)
    # A companion's own life first (gm/confide.py): a confidence the player asked for, one
    # owed, a reminder, or a lead-in. It takes the ordinary remark's place on its beat.
    text, said_it = _companions_confide(c, agent, text, resolution, answered=answered,
                                        moved=moved, heard=heard, player_text=player_text,
                                        repairs=repairs, added=added)
    if said_it:
        return text, repairs, added
    due = companions_mod.interjection_due(
        scene, c.transcript, resolution.outcomes, answered=answered,
        talking=agent.engine.talking_to(), moved=moved)
    if not due:
        return text, repairs, added
    who = scene.actors[due["ref"]]
    # Never their wants: the shortcut that put them into one remark in three is gone
    # (`companions.interject_facts`); they are confided, gated, after a warm-up.
    place = agent.engine.here() if due.get("reason") == "arrived" else None
    facts = companions_mod.interject_facts(scene, who, due, place=place, beat=text)
    line, attempts, rejections = agent.companion_interject(due["ref"], facts)
    c.turn_log.append(history_mod.stamp(c, {
        "kind": "companion-interject", "ref": due["ref"], "reason": due["reason"],
        "line": line, "rejections": rejections,
        "attempts": [{"kind": a.kind, "seconds": round(a.seconds, 1), "model": a.model}
                     for a in attempts]}))
    if not line:
        return text, repairs, added
    text = _say_on_the_page(agent, text, due["ref"], line, "interject", added)
    repairs.append(f"{who.name} spoke up ({due['reason']})")
    return text, repairs, added


def _say_on_the_page(agent, text: str, ref: str, line: str, src: str, added: list) -> str:
    """A companion's unasked line on the page, before the closing question, booked as their
    speech for the conversation log with its source (`interject`, `confide`)."""
    before = text
    text = narration_mod.put_before_the_hand_back(text, line)
    added += narration_mod.added_sentences(before, text)
    quoted = [line[s:e] for s, e in speech_mod.spans(line)]
    if getattr(agent, "last_said", None) is None:
        agent.last_said = []
    agent.last_said.append({"who": ref, "to": "", "from": src,
                            "line": " ".join(q.strip("\"“”'‘’ ") for q in quoted)})
    return text


def _companions_confide(c, agent, text: str, resolution, *, answered, moved: bool,
                        heard: dict | None, player_text: str, repairs: list,
                        added: list) -> tuple[str, bool]:
    """At most one companion says something of their own life this beat, when
    `confide.due` says so: the call writes it, `confide.refusal` holds it, and only a line
    that held moves their disclosure track (`rules.confiding`) — a lead-in or hint marks
    the topic hinted and the share owed; a share marks it told, for good. Returns (text,
    whether anything was said)."""
    from gm import confide as confide_mod
    from rules import confiding, population as population_mod

    scene = c.scene
    asked = (heard or {}).get("confided")
    if asked:
        # The share the player asked for was written before the prose, as this
        # companion's answer (`_companions_answer`): here it is only held to the page and
        # booked as a confidence.
        ref, line = asked
        who = scene.actors.get(ref)
        life = confiding.life_text(population_mod.of_ref(scene, ref),
                                   (heard or {}).get("confided_topic") or "")
        if who is not None and not confide_mod.says_it(text, life):
            text = _say_on_the_page(agent, text, ref, line, "confide", added)
            repairs.append(f"{who.name}'s confidence left off the page: put back")
        else:
            _book_confide(agent, ref, line, text, life)
        return text, True
    place = agent.engine.here()
    before = " ".join(str(b.get("text") or "") for b in c.transcript[-6:]
                      if isinstance(b, dict) and b.get("who") == "gm")
    plan = confide_mod.due(scene, c.transcript, resolution.outcomes, answered=answered,
                           talking=agent.engine.talking_to(), moved=moved, place=place,
                           beat_text=text, before=before)
    if not plan:
        return text, False
    line = _confide_line(c, agent, plan, place=place, player_text=player_text)
    if not line:
        return text, False
    text = _say_on_the_page(agent, text, plan["ref"], line, "confide", added)
    repairs.append(f"{scene.actors[plan['ref']].name} confided ({plan['kind']}, "
                   f"{plan['door']})")
    return text, True


def _confide_line(c, agent, plan: dict, *, place=None, player_text: str = "") -> str:
    """The confiding call for `plan` (`confide.due`), logged; and, only when the line
    held, the disclosure track moved — a lead-in or hint marks the topic hinted and the
    share owed, a share marks it told for good. Returns the line, or ""."""
    from gm import confide as confide_mod
    from rules import confiding, population as population_mod

    scene = c.scene
    who = scene.actors[plan["ref"]]
    rec = population_mod.of_ref(scene, who.ref)
    if rec is None:
        return ""
    lead_in = str((confiding.pending(rec) or {}).get("line") or "")
    facts = confide_mod.facts(scene, who, plan, place=place, player_text=player_text,
                              lead_in=lead_in)
    line, attempts, rejections = agent.companion_confide(who.ref, facts, plan)
    c.turn_log.append(history_mod.stamp(c, {
        "kind": "companion-confide", "ref": who.ref, "event": plan["kind"],
        "door": plan["door"], "topic": plan["topic"], "thing": plan.get("thing", ""),
        "source": plan.get("source", ""), "gate": confiding.gate(who),
        "line": line, "rejections": rejections,
        "attempts": [{"kind": a.kind, "seconds": round(a.seconds, 1), "model": a.model}
                     for a in attempts]}))
    if not line:
        return ""
    beat = len(c.transcript)
    if plan["kind"] in (confide_mod.SHARE, confide_mod.BRIDGE):
        confiding.tell(rec, plan["topic"], beat, plan["door"], plan.get("thing", ""))
    else:
        confiding.hint(rec, plan["topic"], beat, plan["door"], plan.get("thing", ""))
        # The lead-in's own words, so the share can follow on from them.
        rec["confide_pending"]["line"] = line
    return line


def _book_confide(agent, ref: str, line: str, text: str, life: str) -> None:
    """A confidence the prose already carries in its own words: the speech tag the prose
    call gave that line (theirs, saying the life row's words) is marked `confide`, or one
    is added, so the conversation log books it once, as a confidence (its cadence reads
    that)."""
    from gm import confide as confide_mod

    quoted = " ".join(q.strip("\"“”'‘’ ") for q in speech_mod.lines(line))
    said = getattr(agent, "last_said", None)
    if said is None:
        said = agent.last_said = []
    mine = [r for r in said if r.get("who") == ref
            and confide_mod.says_it(str(r.get("line") or ""), life)]
    if mine:
        mine[-1]["from"] = "confide"
        return
    # Never words the page does not carry: the log books what was said, as said.
    if quoted and quoted in text:
        said.append({"who": ref, "to": "", "from": "confide", "line": quoted})


def _run_npc_turns(c, agent, limit: int = 12) -> None:
    """Let every creature between the player's turns act.

    Initiative used to be rolled and then never consulted: the player could swing, and
    nothing ever swung back. This walks the order, asks the GM to act for each NPC in
    turn, and stops when it comes back round to the player.

    `limit` is a guard against a fight that cannot end — a stalled loop here would hang
    the player's request rather than merely playing badly. It is a FLOOR, not the
    budget: a round is one turn per combatant, so a fixed twelve stopped being a
    round the moment a fight had twelve creatures in it. Measured live on
    2026-09-01 in a market holding ten thugs, a woman and a collective: all twelve
    iterations went on NPCs, the loop returned with a thug still holding the turn,
    the panel read "It is not your turn", and every button refused. The game had no
    way forward at all.
    """
    scene = c.scene
    if not scene.in_encounter or scene.awaiting:
        return

    world = c.world
    location = c.location
    events = _recent_events(world, location)

    # Twice the order: one full round, plus room for the arrivals a spawn mid-fight
    # inserts into it.
    for _ in range(max(limit, len(scene.initiative) * 2)):
        # A side with nobody standing means the fight is over.
        if scene.sides and scene.sides_standing() <= 1:
            # Settled while the sides are still declared — the same payout the
            # end_encounter op makes, because two pieces of code end fights and both
            # must pay the same way.
            xp_line = c.engine()._settle_xp()
            c.transcript.append({"who": "gm", "text": ("The fight is over." + xp_line),
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
                # A construct saved "dying" before the house rule, settled on its tick.
                "broken": f"{name} is broken: inert, but not destroyed.",
            }[b["outcome"]]
            c.transcript.append({"who": "gm", "text": line, "kind": "consequence"})
        scene.bleeding = []

        # And whatever is standing in the scene did at the top of the round: the fire in
        # an incendiary cloud, the squeeze of black tentacles, a fog lifting. The same
        # reasoning as the bleeding immediately above — something taking hit points off a
        # character every round with nothing said about it is the sort of thing a player
        # finds out about only when they are dead.
        from rules.engine import _ward_tell

        for h in scene.hazards:
            said = _ward_tell(scene, h)
            if said:
                c.transcript.append({"who": "gm", "text": said, "kind": "consequence"})
        scene.hazards = []

        if ref is None:
            scene.end_encounter()
            return
        actor = scene.get(ref)
        if actor is None or actor.is_pc:
            return                       # back to the player; stop and wait for input
        # A creature holding its ground neither attacks nor flees while it holds
        # (`state.holding-ground`, playtest 2026-09-30 item 8): its turn is that, said,
        # and no model is asked to invent a reason it would do otherwise. The engine
        # lifts the stance the moment the fight reaches it, so this is the guard for
        # the creature that is in the order without being in the fight.
        from rules.states import HOLDING_GROUND

        if actor.has_state(HOLDING_GROUND):
            c.transcript.append({"who": "gm", "kind": "consequence",
                                 "text": f"The {actor.name} holds its ground."})
            continue

        engine = c.engine()
        agent.engine = engine
        # A companion hears what the player said to them (owner's ruling, 2026-10-01):
        # read off the transcript and the conversation log, never guessed (gm/companions).
        from gm import companions as companions_mod

        orders = (companions_mod.orders_for(scene, ref, c.transcript)
                  if companions_mod.is_companion(actor) else None)
        try:
            plan = agent.npc_turn(ref, location=location, recent_events=events,
                                  orders=orders)
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
            undo = scene.snapshot()
            try:
                intents = engine.validate(fallback)
                resolution = engine.run(intents)
            except (IntentError, ValueError, KeyError):
                scene.restore(undo)
                c.transcript.append({"who": "gm", "kind": "consequence",
                                     "text": f"{actor.name} holds back."})
                continue
            for o in resolution.outcomes:
                if o.tell:
                    c.transcript.append({"who": "gm", "kind": "consequence",
                                         "text": _plain_tells(c, [o])})
            # What the fallback did, logged like any creature's turn: it wrote nothing
            # but the error row above, so a fight with the model down left a creature's
            # blows — and who fell to them — out of the record (and the Journal).
            c.turn_log.append(history_mod.stamp(c, {
                "kind": "npc-turn", "ref": ref, "fallback": True,
                "intents": [i.as_dict() for i in intents],
                "outcomes": [o.as_dict() for o in resolution.outcomes]}))
            continue

        undo = scene.snapshot()
        try:
            resolution = engine.run(plan.intents)
        except (IntentError, ValueError, KeyError) as exc:
            # "Holds back" has to mean it: an NPC whose list raised after spawning
            # its friends left the friends on the board and said nothing about them.
            scene.restore(undo)
            # The fallback path above has been guarded since it was written; the path
            # the model succeeds on was not. An NPC turn whose intents validated and
            # then raised at resolution — an empty pool, a ref that left the scene
            # between the two — took down the PLAYER's request as a 500, on a turn the
            # player had already finished. A creature the engine cannot resolve holds
            # back, exactly as one the GM could not speak for does.
            c.turn_log.append({"kind": "npc-turn", "ref": ref,
                               "error": f"resolution: {str(exc)[:400]}"})
            c.transcript.append({"who": "gm", "kind": "consequence",
                                 "text": f"{actor.name} holds back."})
            continue
        # Recorded the way a player turn is. Until stage 8 a creature's turn reached
        # the log only when it failed, so the one door where a model still writes a
        # number (a bestiary creature's `damage`, stamped creature:<template>) could
        # not be audited off a saved campaign at all.
        # With the rejections, as the player's turn has them: a creature's plan refused
        # for reach and repaired from the square the refusal named looked, in the log,
        # exactly like one that never needed a retry (live run, 2026-09-28).
        # The seconds and the model ride here too: they were recorded only by a trailing
        # `_log_turn` after the loop (removed 2026-10-01, tests/test_npc_loop_budget.py),
        # which logged the LAST creature's plan as a player "turn", duplicating this row.
        entry = {"kind": "npc-turn", "ref": ref,
                 "seconds": round(plan.seconds, 1),
                 "attempts": [{"kind": a.kind, "seconds": round(a.seconds, 1),
                               "note": a.note, "model": a.model}
                              for a in plan.attempts],
                 "rejections": list(plan.rejections),
                 "intents": [i.as_dict() for i in plan.intents],
                 "outcomes": [o.as_dict() for o in resolution.outcomes],
                 # What the grooming did to this creature's prose. Written nowhere
                 # before 2026-09-27, so a `wrong-actor` rewrite, a name swapped to
                 # "you" or a creature noun turned into the player's name could only
                 # be found by replaying the recording through `_groom` by hand.
                 "repairs": list(plan.repairs or [])}
        c.turn_log.append(history_mod.stamp(c, entry))
        if plan.narration:
            c.transcript.append({"who": "gm", "text": plan.narration, "kind": "setup"})

        tells = [o for o in resolution.outcomes if o.tell]
        # A companion's turn is told HOW they do it (the owner's second ruling,
        # 2026-10-01: "narrated that they did so in a way that was timid and matched
        # their background") — their nature, trade, feeling for the player, and whether
        # it was an order against their grain — as a fact beside the tells.
        friend = companions_mod.is_companion(actor)
        manner = (companions_mod.manner_line(
            scene, actor, ordered=bool(orders),
            op=plan.intents[0].op if plan.intents else "") if friend else "")
        if tells:
            try:
                # No polish rewrite on an NPC's turn — the same call `npc_turn` makes for
                # its own prose: "a ~10s polish call per NPC per round is a price a fight
                # cannot pay". This door had it on, measured 2026-09-25.
                # `acting`: the call is told whose turn it was, and the prose is checked
                # for being told the wrong way round (narration.wrong_actor).
                text, attempt = agent.narrate_outcome(plan.narration, tells,
                                                      f"{actor.name} acts",
                                                      rewrite=False, acting=actor.name,
                                                      manner=manner)
                if attempt is not None and attempt.note:
                    entry["repairs"] += [r for r in attempt.note.split("; ") if r]
                # The wind-up was held to the manner in `npc_turn`; the turn on the page
                # is the two together, and when neither carries it the consequence's
                # sentences about them are repaired (one call, kept only if the act is
                # unchanged).
                if friend and text and not companions_mod.shows_manner(
                        f"{plan.narration} {text}", actor,
                        companions_mod.dominant_pole(scene, actor), whole=True):
                    text, notes, _more = agent.manner_of(
                        text, actor, ordered=bool(orders),
                        op=plan.intents[0].op if plan.intents else "", whole=True)
                    entry["repairs"] += notes
            except ModelUnavailable:
                text = ""
            c.transcript.append({
                "who": "gm", "kind": "consequence",
                "text": text or _plain_tells(c, tells),
            })
        _log_mentions(c, agent)
        # An NPC's turn is not the player speaking, so the ledger gets no speech
        # from it — only whatever the engine decided on their behalf.
        _remember(c, resolution, "")
    # No `_log_turn(c, plan, resolution)` here. It stood here from the first fight
    # (2026-08-20) and outlived the per-creature rows written above: it logged the last
    # creature's plan a second time, as a player "turn", and when every creature had
    # fallen back to the code rule — the model down, or all of them holding back — `plan`
    # had never been bound and the line raised UnboundLocalError, a 500 that dropped the
    # live campaign (tests/test_npc_loop_budget.py).

    # The budget ran out with somebody else holding the turn. Whatever went wrong,
    # the player is not left staring at a panel where every button refuses: the
    # turn comes back to them and what was cut is said out loud. Parked directly
    # rather than advanced, because advancing ticks rounds and expires holds — the
    # skipped creatures lose their turn, which is a mercy to the player, not a
    # round of free time for anyone.
    _hand_the_turn_back(c, "The scuffle blurs; the moment comes back to you.")


def _log_mentions(c, agent) -> None:
    """Who the groomed beats' mentions meant, one row per beat (gm/mentions.py), into the
    turn log — the record stage 1 of docs/who-the-prose-means.md is measured from."""
    rows = getattr(agent, "mention_rows", None) or []
    c.turn_log.extend(rows)
    if rows:
        agent.mention_rows = []


def _plain_tells(c, outcomes) -> str:
    """Tells for the page when no prose was written for them: numbers off, and the
    player as "you". The player-turn fallback got the person treatment after the gemma4
    fight audit; the two creature-turn fallbacks here did not, and "Borin Lyraxys hits
    Kesst Vayr for 1 bludgeoning" reached the page as the enemy's beat."""
    text = " ".join(plain_tell(o.tell) for o in outcomes if o.tell)
    pc = c.scene.pc()
    if pc is not None and text:
        text, _ = narration_mod.pc_to_second_person(text, pc.name)
    return text


def _hand_the_turn_back(c, why: str) -> None:
    """Park the initiative on the player. The one invariant a fight must not break.

    An encounter whose turn sits on an NPC when a request ends is a dead game:
    `combat_act` answers "It is not your turn", the free-text box goes through the
    same gate, and nothing in the app advances the order except the loop that just
    gave up.
    """
    scene = c.scene
    pc = scene.pc()
    if pc is None or not scene.in_encounter or scene.current_ref() == pc.ref:
        return
    at = next((i for i, (r, _) in enumerate(scene.initiative) if r == pc.ref), None)
    if at is None:
        return
    scene.turn = at
    c.transcript.append({"who": "gm", "text": why, "kind": "consequence"})


def _remember(c, resolution, player_input: str) -> None:
    """One ledger entry for this turn, so it survives the window that will cut it.

    Written here, once, from the engine's own outcomes — never rewritten afterwards.
    Recursive re-summarisation is the approach that measured worst of every one tried
    (35.3% against 94.4% for full context), and the cause named is detail lost through
    repeated re-compression. See gm/ledger.py.
    """
    # Who was spoken to: the person the words name, else the conversation the engine
    # holds (`states.TALKING`), else the one person here. Never "someone" — measured
    # 2026-10-03 (item 22), "you spoke with someone" was a ledger line that remembered
    # nothing, written while the engine knew exactly who the player was talking to.
    from rules import states

    spoke = ""
    if judgement.was_speech(player_input):
        here = [a for a in c.scene.actors.values() if not a.is_pc]
        named = next(
            (a.name for a in here
             if len(str(a.name).split()[-1]) > 2
             and str(a.name).split()[-1].lower() in (player_input or "").lower()), "")
        talking = [a.name for a in here if a.has_state(states.TALKING)]
        spoke = (named or (talking[0] if len(talking) == 1 else "")
                 or (here[0].name if len(here) == 1 else ""))
    # Places by the names the player read, and where the party stood by its own name
    # within the settlement — "the smithy, Zhilvarnia", not the settlement alone for
    # every entry, and never an id (item 22: "you went to ca~urban:the-docks").
    try:
        known = places_mod.for_scene(c.location, c.scene.at,
                                     founded=getattr(c.scene, "founded", ()) or ())
    except Exception:  # noqa: BLE001 — a memory line is never worth the turn
        known = ()
    place_names = {p.id: p.name for p in known if getattr(p, "id", "")}
    for p in getattr(c.scene, "founded", ()) or ():
        pid, pname = getattr(p, "id", ""), getattr(p, "name", "")
        if pid and pname:
            place_names.setdefault(pid, pname)
    settlement = getattr(c.location, "name", "") or ""
    spot = place_names.get(str(getattr(c.scene, "at", "") or ""), "")
    where = ", ".join(x for x in (spot, settlement) if x)
    ledger_mod.keep(c.ledger, ledger_mod.note(
        resolution.outcomes,
        turn=len(c.transcript),
        hist=len(c.history),
        spoke_with=spoke,
        where=where,
        # Everybody the scene holds, not only who stands here now: a turn that spoke to
        # somebody and then walked away has left them behind by the time it is written.
        names={r: a.name for r, a in (getattr(c.scene, "people", None)
                                      or c.scene.actors).items()},
        places=place_names))


def _log_turn(c, plan, resolution, replace: bool = False):
    entry = {
        "kind": "turn",
        "seconds": round(plan.seconds, 1),
        # The model is recorded because the turn log is the only place that can answer
        # "which one wrote this". `Attempt` has carried the field since it was written
        # and the save dropped it, so a narration defect could only be pinned on a
        # model by counting rejections and reasoning about which one the schedule would
        # have reached — which is a deduction, not a record.
        "attempts": [{"kind": a.kind, "seconds": round(a.seconds, 1), "note": a.note,
                      "model": a.model}
                     for a in plan.attempts],
        "repairs": plan.repairs,
        "rejections": plan.rejections,
        "intents": [i.as_dict() for i in plan.intents],
        "outcomes": [o.as_dict() for o in resolution.outcomes],
    }
    reading = getattr(plan, "reading", None)
    if isinstance(reading, dict):
        entry["reading"] = {k: v for k, v in reading.items() if k != "raw"}
    # What the player attached to the turn (§2.4), only when they did.
    attachments = getattr(plan, "attachments", None)
    if attachments:
        entry["attachments"] = [dict(a) for a in attachments]
    # The turn entry `_advance` wrote before the prose call, wherever it now sits.
    # `replace` used to look only at the LAST entry, and under intents-first the
    # prose entry is appended between the two — so every single turn was logged
    # twice. Read out of a live save: eight "turn" entries for four turns, four
    # exact duplicate pairs, and the log that is supposed to answer "what did the
    # engine do" claimed the spawn happened twice.
    if replace:
        for i in range(len(c.turn_log) - 1, -1, -1):
            if c.turn_log[i].get("kind") == "turn":
                # When and where, from the row being replaced: the turn happened then.
                for key in ("clock", "at"):
                    if key in c.turn_log[i]:
                        entry[key] = c.turn_log[i][key]
                c.turn_log[i] = history_mod.stamp(c, entry)
                return
    # The clock and the place, for the Journal's history (play/history.py).
    c.turn_log.append(history_mod.stamp(c, entry))


@require_POST
def wear_item(request):
    """Put on or take off something the character is carrying.

    Crafted gear was landing in the pack and staying there: a forged breastplate, a
    tanned cloak and a bound ring were all records with real effect specs and no way to
    say you were wearing them. The item's own record names its slot — the maker already
    answered that question, so the player is not asked to classify their own loot.

    A player action on their own property, so it goes straight to the sheet rather than
    through the GM, exactly as drinking does.
    """
    body = read_body(request)
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)

    item_id = str(body.get("item", "")).strip().lower()
    off = bool(body.get("off"))
    op = str(body.get("op", "")).strip().lower()
    if op in ("wield", "wear"):
        return _wear_by_the_engine(c, pc, item_id)
    if op == "take_off":
        # Armour or a shield off again: the engine's `take_off` op (2026-09-30, E4).
        return _wear_by_the_engine(c, pc, item_id, op="take_off")
    held = pc.stock.get(item_id)
    if held is None:
        return JsonResponse({"error": f"you are not carrying {item_id!r}"}, status=400)

    record = held.as_dict()
    try:
        if off:
            if not pc.take_off(record["name"]):
                return JsonResponse(
                    {"error": f"{record['name']} is not being worn"}, status=400)
            tell = f"{pc.name} takes off {record['name']}."
        else:
            if not record.get("wearable") or not record.get("slot"):
                return JsonResponse(
                    {"error": f"{record['name']} is not something you wear"}, status=400)
            slot = pc.wear(record, read_int(body, "index", 0))
            tell = f"{pc.name} puts on {record['name']} ({slot})."
    except Exception as exc:
        # Slot rules refuse with a sentence — already occupied, no such slot. A 400 with
        # the reason, because the page prints it verbatim beside the button.
        return JsonResponse({"error": str(exc)}, status=400)

    c.transcript.append({"who": "gm", "kind": "consequence", "text": tell})
    c.save()
    return JsonResponse(_state(c))


def _wear_by_the_engine(c, pc, item: str, op: str = "wear"):
    """Draw a carried weapon, or put on carried armour or a shield: the engine's own
    `wear` op, run straight from the Equipment tab's Wield and Wear buttons.

    The table rebuild, stage 2: the approved design answers Wield and Wear with the
    engine's tell, word for word ("Kesst Vayr draws the sap.", "puts on the studded
    leather. Armour class 16 to 17."). The op already existed and the GM reached it
    through words; this is its door from the sheet, as `use_item` is `use_item`'s. A
    refusal is the op's own sentence ("is not carrying", "is not something that can be
    worn or wielded"), sent back as the 400 the button prints beside itself.

    The same guards as every other action a player takes on their own: nobody downed
    reaches for a sword, and nothing runs under a roll that is still owed.
    """
    refusal = _cannot_act(pc, "do that")
    if refusal:
        return refusal
    if c.scene.awaiting:
        return JsonResponse({"error": "There is a roll waiting on you."}, status=409)
    undo = c.scene.snapshot()
    try:
        engine = c.engine()
        resolution = engine.run(engine.validate([{
            "op": op, "actor": "pc", "because": f"{pc.name} sees to their gear",
            "params": {"item": item},
        }]))
    except IntentError as exc:
        c.scene.restore(undo)
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:     # noqa: BLE001 — a sentence on the page, never a 500
        c.scene.restore(undo)
        return JsonResponse({"error": f"{type(exc).__name__}: {exc}"}, status=400)
    tell = " ".join(o.tell for o in resolution.outcomes if o.tell)
    if not any(o.effects for o in resolution.outcomes):
        return JsonResponse({"error": tell or "Nothing happened."}, status=400)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": tell})
    c.save()
    return JsonResponse({**_state(c), "wear_tell": tell})


@require_POST
def use_item(request):
    """Drink, throw or coat a blade with something the character crafted.

    A player action on their own property, so it goes straight to the engine rather than
    through the GM: there is nothing here for a model to decide, and routing it through
    narration was why thirty crafted jars could be looked at and not used.

    The op is `use_item`, which already existed and already emits ordinary intents for the
    effects — this only gives it a door from the sheet.
    """
    body = read_body(request)
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)

    item = str(body.get("item", "")).strip().lower()
    how = str(body.get("how", "drink")).strip().lower()
    # An unconscious character does not reach for a jar. The one exception a table might
    # want — somebody else pouring a potion down their throat — is a different action
    # taken by a different person, and this endpoint is the player acting on their own.
    refusal = _cannot_act(pc, "use that")
    if refusal:
        return refusal
    target = str(body.get("to", "") or "pc").strip()
    # One intent in, but a jar's authored effects fan out into several inside the
    # op, so a raise part-way can still leave the drink half-drunk: consumed off
    # the sheet, and no healing.
    undo = c.scene.snapshot()
    # Eating out of the pack is the `eat` op with the item named (2026-10-01, "trail
    # rations reset my hunger"): it spends one and resets hunger through
    # rules/survival.py. A jar is drunk, thrown or coated by `use_item`, as before.
    raw = ({"op": "eat", "actor": "pc", "because": f"{pc.name} eats",
            "params": {"item": item}} if how == "eat" else
           {"op": "use_item", "actor": "pc", "because": f"{pc.name} reaches for it",
            "params": {"item": item, "how": how, "to": target,
                       # Where it goes (the Use menu): only `apply` takes one.
                       **({"route": str(body.get("route") or "").strip().lower()}
                          if how == "apply" else {})}})
    try:
        engine = c.engine()
        resolution = engine.run(engine.validate([raw]))
    except IntentError as exc:
        c.scene.restore(undo)
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        c.scene.restore(undo)
        # A jar with authored effects the engine chokes on must be a sentence in the
        # sheet, not a 500 with an invisible error — "clicking the drink button does
        # nothing" was exactly this, twice over.
        return JsonResponse({"error": f"{type(exc).__name__}: {exc}"}, status=400)

    tell = " ".join(o.tell for o in resolution.outcomes if o.tell)
    if not any(o.effects for o in resolution.outcomes):
        # A refusal, printed by the engine since stage 7 rather than raised: the only
        # `use_item` outcome with no effects. The button shows it as the error it is
        # and the sheet does not redraw, which is what a button that did nothing owes.
        return JsonResponse({"error": tell or "Nothing happened."}, status=400)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": tell})
    c.save()
    return JsonResponse({"ok": True, "tell": tell, "sheet": _sheet_payload(pc)})


def _cannot_act(pc, doing: str):
    """A refusal when the character is in no state to do this, else None.

    One rule, four doors, and only one of them was locked. `say` has refused the downed
    since somebody typed "now what" at -3 hit points and got cheerful narration about
    dodging — and `use_item`, `combat_act` and the counter all shipped without it.

    Found in the first minute of a play session: Thessaly was at 0 hit points,
    Unconscious and Disabled after a fight, and she sold a tincture and bought a jar of
    beeswax across the counter. Nothing anywhere asked whether she was awake.

    A helper rather than a fourth copy, which is CLAUDE.md's rule about a rule that has
    more than one home: the consequence rule was corrected in one prompt and left stale in
    the other, and the bug went on shipping from the copy nobody looked at.
    """
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)
    if downed.state_of(pc) not in ("fine", "disabled"):
        return JsonResponse(
            {"error": f"{pc.name} is in no condition to {doing}."}, status=409)
    return None


@require_POST
def set_gender(request):
    """Say what an existing character is, for the saves that predate the field.

    The forge asks every new character, but four on the live roster were made when it
    did not and read `they/them` — which says nothing about a body, so nothing can be
    derived from it. Guessing from a name is precisely the thing this whole field exists
    to stop, so it is asked rather than inferred.
    """
    from rules.sheet import gender_from_pronouns, pronouns_for_gender

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)

    said = " ".join(str(read_body(request).get("gender", "")).split()).lower()
    if not said:
        return JsonResponse({"error": "say woman or man"}, status=400)
    if len(said) > 40:
        return JsonResponse({"error": "that is too long to be a description"}, status=400)

    pronouns = pronouns_for_gender(said)
    if not pronouns:
        return JsonResponse({"error": (
            f"Nothing follows from {said!r} about which words to use. Choose woman or "
            f"man, or turn a pronoun set on in the house rules and pick that.")},
            status=400)

    # Both, together. Keeping them coupled here is the same rule the forge follows, and
    # the reason is on the live roster: a save holding a gender and a contradicting set
    # of pronouns gives the narrator two answers to choose between.
    pc.gender = said
    pc.pronouns = pronouns
    c.save()
    # And onto the roster entry too, or the campaign and the character file disagree —
    # which is exactly the state Thessaly's save was found in.
    if getattr(c, "character_id", ""):
        roster.record(c.character_id, pc)
    return JsonResponse({"ok": True, "gender": pc.gender, "pronouns": pc.pronouns})


# --- trading ---------------------------------------------------------------------------
#
# "i single store should not have every possible item" was the first half of this, and it
# got the shelf. This is the second half, and it came from watching a haggle happen
# entirely in prose: "it's also obvious the vender in this interaction did not actually
# see what i was trying to give her it was completely narrative."
#
# She could not see it. There was no sell op, no buy op, and no price on anything the
# player had made. Four turns of bargaining resolved to `narrate_only` and the purse was
# empty afterwards.
#
# Straight to the engine, like `use_item` and the combat panel, and for the same reason:
# picking a jar off a list and being paid for it has nothing in it for a model to decide.


# Somebody who keeps a counter. Matched on the actor's name or kind, because that is
# how the engine's people arrive — "the stallholder", "a vendor", a spawned merchant.
_MERCHANT = re.compile(
    r"\b(?:merchant|vendor|stall|shop|trader|trades|peddler|apothecary|grocer|"
    r"keeper|monger|seller|smith|barkeep|innkeep)\w*\b", re.I)


def _merchant_here(scene):
    """The merchant standing in this scene, or None.

    The trade panel opens only across a real counter — "The trade button should only
    work when the user is in a dialogue with a merchant, otherwise the exchange of
    objects can be handled through the prompts." The narrated path (the sell/buy
    injectors) deliberately keeps working anywhere; this gates only the panel.

    **Never the master of a market** (I2): the market's own keeper runs it and sells
    nothing (`places.RUNNERS`), so the panel opens across one of its counters instead.
    Of several people who keep a counter here, the one the player is talking with wins,
    then the general store's keeper — the counter a market opens on when nobody asked
    for another.
    """
    from rules import keepers, states

    found = []
    for ref, a in scene.actors.items():
        if a.is_pc or a.is_down:
            continue
        wid = str(getattr(a, "world_entity_id", "") or "")
        # Whoever keeps this counter, first and by what they ARE rather than by what
        # they are called. The name test below cannot see a keeper: they are named out
        # of the world ("Gorvothys Vyrnys") precisely so that they are a person and not
        # a job title, and a panel that only opens for people called "the stallholder"
        # would refuse every real shopkeeper this app builds.
        if keepers.keeps_a_counter(a):
            found.append(a)
            continue
        if keepers.is_keeper(wid) and not keepers.counter_of(wid) \
                and places_mod.runs_it(keepers.label_of(keepers.place_of(wid))):
            continue
        if _MERCHANT.search(str(a.name or "")) or _MERCHANT.search(str(a.kind or "")):
            found.append(a)
    if not found:
        return None
    talking = [a for a in found if a.has_state(states.TALKING)]
    if talking:
        return talking[0]
    general = [a for a in found
               if keepers.counter_of(getattr(a, "world_entity_id", "") or "") == "general"]
    return (general or found)[0]


def _market_here(c) -> tuple[str, tuple]:
    """(the market's place id, its counters) when the party stands in a market that has
    counters (`rules/market.py`); ("", ()) anywhere else."""
    from rules import market

    at = str(c.scene.at or "")
    if not at or not market.is_market(at, getattr(c.scene, "founded", None) or ()):
        return "", ()
    location = c.location
    return at, market.counters(location if location is not None else c.scene.location_id)


def _counter_pick(c, want: str = "", line: str = ""):
    """(counter, its keeper or None, the market's id, every counter) for a trade at a
    market; (None, None, "", ()) anywhere else.

    Which counter: the one the panel named (`line`), else the one that sells the thing
    the player asked for (`market.counter_for_want`: "a coil of rope" is the general
    store's hemp), else the counter of the stallholder the player is talking with, else
    the general store. Its keeper is minted on first need through the arrival door
    (`keepers.stand_up`) — design D §4.8 — and is None when the market is packed up for
    the night or they are gone. Never the master."""
    from rules import keepers, market, states

    at, choices = _market_here(c)
    if not choices:
        return None, None, "", ()
    chosen = next((x for x in choices if x.id == str(line or "")), None) if line else None
    if chosen is None and want:
        chosen, _found = market.counter_for_want(
            want, choices, str(c.scene.location_id or "nowhere"),
            market.day_of(c.scene.clock_minutes), c.scene.market_taken)
    if chosen is None:
        for a in c.scene.actors.values():
            cid = keepers.counter_of(getattr(a, "world_entity_id", "") or "")
            if cid and a.has_state(states.TALKING):
                chosen = next((x for x in choices if x.id == cid), None)
                if chosen is not None:
                    break
    if chosen is None:
        chosen = next((x for x in choices if x.id == "general"), choices[0])
    seller = keepers.stand_up(c.scene, c.world, at, chosen)
    if seller is not None and (seller.ref not in c.scene.actors or seller.is_down):
        seller = None
    return chosen, seller, at, choices


def _lines_of(c, at: str, choices) -> list[dict]:
    """The market's counters for the panel: id, what it is, and who keeps it when they
    have been met (anonymous until then — design D §4.8)."""
    from rules import keepers

    out = []
    for x in choices:
        wid = keepers.holder_id(at, x.id)
        who = next((a for a in c.scene.people.values()
                    if str(getattr(a, "world_entity_id", "") or "") == wid), None)
        out.append({"id": x.id, "label": x.label,
                    "seller": str(who.name) if who is not None else ""})
    return out


def _offer_and_seller(c, player_text: str):
    """The counter a purchase opens and who is behind it: (offer or None, seller)."""
    from rules import keepers

    want = judgement.purchase_sought(player_text)
    if not want or c.scene.in_encounter:
        return None, None
    pc = c.scene.pc()
    if pc is None:
        return None, None
    counter, seller, _at, choices = _counter_pick(c, want=want)
    if choices:
        if seller is None or keepers.shut_here(c.scene, seller):
            return None, None
        if _counter_refusal(c, pc, seller) is not None:
            return None, None
        return {"open": True, "want": want, "line": counter.id}, seller
    merchant = _merchant_here(c.scene)
    if keepers.shut_here(c.scene) or merchant is None:
        return None, None
    if _counter_refusal(c, pc) is not None:
        return None, None
    return {"open": True, "want": want, "line": ""}, merchant


def _trade_offer(c, player_text: str) -> dict | None:
    """{"open": True, "want": ..., "line": ...} when the player set out to buy something
    and there is an open counter here to buy it at; else None.

    The user's ruling (2026-09-27): "I try to buy a coil of rope." should "open the trade
    tab [potentially with Rope in the basket]". Not opened at a shut counter (the keeper
    has said when to come back, `keepers.shut_here`), with nobody keeping one, or for a
    customer the keeper will not serve (`_counter_refusal`) — each of those is the
    beat's to say, and an empty panel would contradict it. At a market, `line` is the
    counter that sells the thing (I2), and it is never the master."""
    return _offer_and_seller(c, player_text)[0]


def _buying_note(c, player_text: str) -> str:
    """The brief's line when the turn opens the counter: the prose brings the keeper to
    it and settles nothing — the screen is where the coin moves."""
    offer, seller = _offer_and_seller(c, player_text)
    if not offer:
        # A purchase that opens nothing sells nothing, and the beat says why. Live
        # 2026-09-27, the market shut for the night: the prose invented a vendor, sold
        # bread and torches, and finished "The transaction for the egg is complete".
        want = judgement.purchase_sought(player_text)
        if not want or c.scene.in_encounter:
            return ""
        from rules import keepers

        why = (keepers.shut_here(c.scene)
               or ("Nobody here keeps a counter." if _merchant_here(c.scene) is None
                   else "The keeper here will not serve the player."))
        return (f"The player tries to buy {want}, and nothing is sold: {why} Nobody "
                f"hands anything over and no coin changes hands in the prose.")
    who = getattr(seller, "name", "") or "the keeper"
    where = ""
    if offer.get("line"):
        _at, choices = _market_here(c)
        label = next((x.label for x in choices if x.id == offer["line"]), "")
        # Which counter, by name: the market is its counters, and the prose that walks
        # the player to "the stallholder" without saying which invents one (item 10).
        where = f" at {label}" if label else ""
    return (f"The player is buying {offer['want']}: the counter's own screen opens for it "
            f"after this beat. {who}{where} comes to the counter and may show the goods "
            f"and name a price; nothing is handed over and no coin changes hands in the "
            f"prose — the player pays on the screen.")


def _counter_refusal(c, pc, merchant=None):
    """The merchant's answer to a wanted character: no, with the reason named. Else
    None (docs/wanted.md, reader two).

    The panel's half of the price reader. Prices for the suspected go up through
    `pricing.markup_for` and nobody refuses them; for the wanted the stallholder will
    not be seen trading — Fallout: New Vegas's merchants do the same to the Vilified —
    and says so, so the player knows which town's name to clear. Both doors of the
    counter ask this one helper, for the reason `_cannot_act` gives: a rule with two
    homes drifts. Asked through the vocabulary, so the one `remove_effects(source=...)`
    that clears the name reopens the counter with nothing else touched.

    `merchant` is the counter's keeper when the caller already knows it (a market's
    counters, I2); else whoever `_merchant_here` finds.
    """
    from rules import attitude, states

    merchant = merchant if merchant is not None else _merchant_here(c.scene)
    town = str(c.scene.location_id or "")
    if merchant is None:
        return None
    # How they feel about you, before what the law thinks of you. 1e gates what a
    # creature will do for you on their attitude — "once a creature's attitude is
    # indifferent or better you can make requests" — and buying from somebody is a
    # request. A shopkeeper who has been given a reason to dislike you does not serve
    # you, and Diplomacy is the way back in (`rules/attitude.py`). Nobody starts here:
    # an attitude is only ever set by something that happened, so a counter the player
    # has not poisoned opens exactly as it always did.
    mood = attitude.of(merchant, default="")
    if mood in ("hostile", "unfriendly"):
        return JsonResponse({"error": (
            f"{merchant.name} will not trade with {pc.name}. Talk them round first — "
            f"it takes a minute of it, and the engine rolls your Diplomacy against how "
            f"they feel about you.")}, status=409)
    if states.standing_with_the_law(pc, town) != "wanted":
        return None
    return JsonResponse({"error": (
        f"{merchant.name} looks at {pc.name} and then at the door. {pc.name} is "
        f"wanted here, and nobody keeping a counter will be seen trading with them. "
        f"Clear your name, or trade somewhere the watch is not looking.")}, status=409)


def _stall_of(c, counter=None) -> tuple[str, str, int]:
    """Which shop, on which day. Read the same way `craft_views` reads it, so a stall's
    money and its stock agree about where and when this is.

    A present merchant names the stall, so two different vendors in one town are two
    different shelves and two different tills — and the same vendor's stock holds for
    the in-game day (`day_of` is the clock in 24-hour windows), which is the persistence
    the table asked for.

    One of a market's counters (I2) is keyed by its kind, `market:<counter>` — the shelf
    and the till are the counter's (Morrowind's per-merchant gold), and the engine's
    `buy` reads the same key to know which counter it is standing at. The stables are
    keyed `stables` for the same reason.
    """
    from rules import market

    here = (str(c.scene.location_id or "nowhere"), "", market.day_of(c.scene.clock_minutes))
    if counter is not None:
        return here[0], counter.kind, here[2]
    kind = market.counter_kind_here(c.scene)
    if market.is_counter_kind(kind):
        return here[0], kind, here[2]
    merchant = _merchant_here(c.scene)
    stall = re.sub(r"[^a-z0-9]+", "-", str(merchant.name).lower()).strip("-") \
        if merchant else "market"
    return here[0], stall, here[2]


def _row(item, price: float, count: int = 1) -> dict:
    from rules import gear as gear_mod
    from rules import pricing

    return {"id": str(getattr(item, "id", "")),
            "name": str(getattr(item, "label", "") or getattr(item, "name", "")),
            "tier": str(getattr(item, "tier", "") or "common"), "count": count,
            "gp": round(price, 2), "price": pricing.as_text(price),
            # What the engine can actually run with it, which is a quarter of the price
            # when the answer is nothing — worth showing beside the number. A weapon, a
            # suit of armour and a horse are all things the engine runs (I2).
            "does_something": bool(getattr(item, "specs", None))
            or str(getattr(item, "kind", "")) in ("weapon", "armour", "shield", "mount")
            # A bedroll, a tent, rations: what they do is their gear row's (2026-10-01).
            or bool(gear_mod.row_for(getattr(item, "base", "")
                                     or getattr(item, "name", ""))[1]),
            # I7, the trade window: which side tab and card mark the row is filed under,
            # and whether the counter can sell more than one. The rows said neither — a
            # carried jar's id is "willow-bark-tea#1" and a bench material's is bare, so
            # the page could not have told a potion from a lump of bismuth.
            "shelf": _shelf_of(item),
            "staple": bool(getattr(item, "staple", False))}


# The trade window's categories (I7), in the player's words and in the order its side
# tabs show them.
SHELVES = ("weapons", "armour", "consumables", "gear", "magic", "valuables", "materials",
           "animals")
_VALUABLE = re.compile(
    r"\b(?:gems?|jewel\w*|pearls?|rub(?:y|ies)|emeralds?|sapphires?|diamonds?|opals?|"
    r"garnets?|amethysts?|topaz|jade|onyx|agate|ivory|necklace|brooch|bracelet|earrings?|"
    r"circlet|crown|chalice|goblet|idol|statuette|figurine|coins?|ingot)\b", re.I)


def _shelf_of(item) -> str:
    """Which of `SHELVES` a row belongs on: a good's own kind first, a carried jar's own
    fields next, and its name last — the order `goods.kind_of` files a purchase in, and
    for the same reason: what a thing *is* beats what it is called. One answer for both
    columns, so a potion is a consumable whether it is on your side or theirs."""
    from rules import goods
    from rules.crafting import Stock

    kind = str(getattr(item, "kind", "") or "")
    name = str(getattr(item, "name", "") or "")
    if kind in ("mount", "tack"):
        return "animals"
    if kind == "weapon" or getattr(item, "weapon", None):
        return "weapons"
    if kind in ("armour", "shield") or getattr(item, "armour", None):
        return "armour"
    if isinstance(item, Stock):
        if item.holds_spell or item.enhancement or item.craft == "enchanter":
            return "magic"
        if kind in ("ore", "intermediate"):
            return "materials"
        table = goods.kind_of(name)
        if table == "weapon":
            return "weapons"
        if table in ("armour", "shield"):
            return "armour"
        if (item.how or item.craft in ("herbalist", "herbalism", "alchemist")
                or table == "consumable" or name.lower() in _food_names()):
            return "consumables"
        return "valuables" if _VALUABLE.search(name) else "gear"
    if not isinstance(item, goods.Good):
        # A bench's material: the enchanter's finished wondrous items are things to use,
        # everything else is what a workshop makes things from.
        return "magic" if kind == "wondrous" else "materials"
    if goods._category(item.key) in ("food", "provisions") \
            or goods.kind_of(name) == "consumable":
        return "consumables"
    return "gear"


def _food_names() -> frozenset:
    """A loaf of bread bought at a counter is carried as a plain jar named "loaf of bread"
    (`goods.deliver`); the gear list's food rows are how it is known for food."""
    from rules import goods

    return frozenset(str(e["name"]).lower() for e in goods.GEAR.values()
                     if e.get("category") in ("food", "provisions"))


@require_POST
def trade(request):
    """Both sides of a counter: what you are carrying, and what they have.

    At a market (I2) the body may name the counter (`line`); the answer says which one
    it opened on (`line`), every counter the market has (`lines`) and who is behind this
    one (`seller`) — docs/fix-interfaces.md §2.10."""
    from rules import goods, market, pricing, states

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)

    from rules import keepers as _keepers

    body = read_body(request)
    want = " ".join(str(body.get("want") or "").split())[:80]
    counter, merchant, at, choices = _counter_pick(c, want=want,
                                                   line=str(body.get("line") or ""))
    if choices:
        if merchant is None:
            shut = _keepers.shut_here(c.scene)
            return JsonResponse({"error": shut or (
                f"Nobody is at {counter.label} just now.")}, status=409)
        shut = _keepers.shut_here(c.scene, merchant)
        if shut:
            return JsonResponse({"error": shut}, status=409)
    else:
        shut = _keepers.shut_here(c.scene)
        if shut:
            return JsonResponse({"error": shut}, status=409)
        merchant = _merchant_here(c.scene)
        if merchant is None:
            return JsonResponse({"error": (
                "There is nobody here to trade with. Find a stall and speak to whoever "
                "keeps it — or simply say what you sell or buy, and the scene handles "
                "it.")}, status=409)
    refusal = _counter_refusal(c, pc, merchant)
    if refusal:
        return refusal

    place, stall, day = _stall_of(c, counter)
    if counter is None:
        stall = str(body.get("stall") or stall)
    kind = counter.kind if counter is not None else market.counter_kind_here(c.scene, stall)
    tier = str(body.get("tier") or market.DEFAULT_STALL_TIER)
    if market.is_counter_kind(kind):
        tier = market.till_tier(kind, tier)

    till = market.purse(place, stall, day, tier)
    left = round(till - market.spent_today(c.scene.market_taken, place, stall, day), 2)
    shelf = market.on_sale(place, stall, day, c.scene.market_taken, tier, counter_kind=kind)
    # What the player's words asked for, picked on the counter if it is there — and if
    # it is not, the keeper says so (tbaMUD: "Sorry, I haven't got exactly that item.")
    # and nothing is guessed in its place.
    pick, want_line = "", ""
    if want:
        found, _fits = goods.match_want(want, shelf)
        if found is not None:
            pick = str(getattr(found, "id", ""))
        else:
            who = getattr(merchant, "name", "") or "The keeper"
            thing = re.sub(r"^(?:a|an|some|the)\s+", "", want)
            want_line = (f"{who} has no {thing} on the counter"
                         # True only when every counter was asked: a want with no
                         # `line` is matched across the whole market first.
                         + (", and nobody at the market sells it"
                            if choices and not body.get("line") else "")
                         + ". This is what there is.")
    if choices:
        # A keeper minted for this counter is part of the save from now on.
        c.save()

    return JsonResponse({
        "stall": stall, "place": place, "day": day, "pick": pick, "want_line": want_line,
        "line": counter.id if counter is not None else "",
        "counter": counter.label if counter is not None else "",
        "lines": _lines_of(c, at, choices) if choices else [],
        "seller": {"ref": merchant.ref, "name": str(merchant.name)},
        "till": {"gp": left, "text": pricing.as_text(max(0.0, left))},
        "purse": goods.purse_line(pc.purse, goods.coinage()),
        "purse_gp": round(goods.in_copper(pc.purse) / 100, 2),
        # Yours, at what a shop would pay — which is the number that matters when the
        # question is what you can get for it, not what it is worth.
        # Priced for THIS buyer in THIS town: a suspected character sees the markup
        # (`pricing.markup_for`) on both columns, which is the whole of what
        # "suspected" costs at a counter that does not refuse them.
        "mine": sorted(
            (_row(s, pricing.what_a_shop_pays(s, seller=pc, town=place), s.count)
             for s in pc.stock.values()),
            key=lambda r: -r["gp"]),
        "theirs": sorted((_row(m, pricing.worth(m, buyer=pc, town=place)) for m in shelf),
                         key=lambda r: -r["gp"]),
        "law": states.standing_with_the_law(pc, place),
    })


@require_POST
def trade_do(request):
    """Actually hand something over, or actually pay for it."""
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)

    # The same guard `say` and the combat panel apply. Resolution is genuinely stopped
    # mid-list waiting on a d20, and running a second intent list through the engine
    # underneath it is how a suspension gets lost.
    if c.scene.awaiting:
        return JsonResponse({"error": "There is a roll waiting on you."}, status=409)

    refusal = _cannot_act(pc, "trade")
    if refusal:
        return refusal
    from rules import keepers as _keepers

    body = read_body(request)
    counter, merchant, _at, choices = _counter_pick(c, line=str(body.get("line") or ""))
    if choices:
        if merchant is None:
            return JsonResponse({"error": _keepers.shut_here(c.scene) or (
                f"Nobody is at {counter.label} just now.")}, status=409)
        shut = _keepers.shut_here(c.scene, merchant)
    else:
        shut = _keepers.shut_here(c.scene)
        merchant = _merchant_here(c.scene)
    if shut:
        return JsonResponse({"error": shut}, status=409)
    if merchant is None:
        return JsonResponse({"error": "There is nobody here to trade with."},
                            status=409)
    refusal = _counter_refusal(c, pc, merchant)
    if refusal:
        return refusal

    op = str(body.get("op", "")).strip().lower()
    if op not in ("sell", "buy"):
        return JsonResponse({"error": "sell or buy"}, status=400)

    place, stall, day = _stall_of(c, counter)
    params = {"item": str(body.get("item", "")).strip().lower(),
              "count": read_int(body, "count", 1, lo=1, hi=999),
              "stall": stall if counter is not None else str(body.get("stall") or stall)}
    # At a market's counter the keeper is named, so the tell says who was paid — never
    # the master, who sells nothing (I2).
    if counter is not None:
        params["from_" if op == "buy" else "to"] = merchant.ref
    # The haggle, when the screen has offered a partial and the player took it. Only ever
    # lowers what is asked — see `_op_sell`.
    if op == "sell" and body.get("accept") is not None:
        params["accept"] = body["accept"]

    # A trade moves goods one way and coin the other. A raise between the two is
    # the worst half-application in the app: paid for, not delivered.
    undo = c.scene.snapshot()
    try:
        engine = c.engine()
        resolution = engine.run(engine.validate(
            [{"op": op, "actor": "pc", "because": "at the counter", "params": params}]))
    except IntentError as exc:
        c.scene.restore(undo)
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        c.scene.restore(undo)
        # The same rule the drink button learned: a trade that cannot happen is a
        # sentence on the screen, never a 500 with an invisible error.
        return JsonResponse({"error": f"{type(exc).__name__}: {exc}"}, status=400)

    tell = " ".join(o.tell for o in resolution.outcomes if o.tell)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": tell})
    c.save()
    return JsonResponse({"ok": True, "tell": tell})
