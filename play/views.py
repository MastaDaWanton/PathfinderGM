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

from gm import (client, judgement, ledger as ledger_mod,
                narration as narration_mod, prompts, watcher)
from gm.agent import GMAgent
from gm.client import ModelUnavailable, available
from rules import biomes, grid, ingredients as ing_mod
from rules.intents import IntentError

from . import campaign as campaign_mod
from . import concurrency
from .apiutil import read_body, read_int
from . import downed, gm_answers, player_input, roster


def _recent_events(world, location, limit=4):
    """A few things this place remembers. Grounding, and a budget.

    The selection and the sort live on `World.events_touching`, which is where the
    export's own quirks belong. This used to filter on `location.id in e.entity_ids`
    directly and returned an empty list for every one of the shipped world's 74
    entities, because the export never fills that field in — so the whole "WHAT THIS
    PLACE REMEMBERS" section of the brief had never once reached the model.
    """
    return world.events_touching(location.id if location else None)[:limit]


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
    from rules import cards as cards_mod
    from rules import goods as goods_mod
    from rules import houserules as houserules_mod
    from rules import schemes as schemes_mod

    coins = goods_mod.coinage(c.world, c.location)
    return {
        "transcript": c.transcript,
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
            "biome": c.biome,
            "biome_describe": biomes.describe(c.biome),
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
                 # Which side of the fight, or "" for a bystander the fight has not
                 # touched — the map paints foes red and bystanders white.
                 "side": next((s for s, refs in (c.scene.sides or {}).items()
                               if r in refs), ""),
                 "size": a.size, "squares": grid.size_squares(a.size),
                 "at": list(c.scene.positions[r]) if r in c.scene.positions else None,
                 "conditions": [x.name for x in a.conditions]}
                for r, a in c.scene.actors.items()
                if a.is_pc or not a.has_state("state.hidden")
            ],
            "grid": _grid_state(c.scene),
            # Blood on the ground. Sent whether or not there is a grid: without one
            # they are still a count the player needs, because half the class spends
            # them.
            "pools": [b.as_dict() for b in c.scene.pools if b.here(c.scene)],
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
    try:
        c = campaign_mod.switch_to(character_id)
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

    c = campaign_mod.begin_with(character)
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
    c = campaign_mod.current(reset=request.GET.get("new") == "1")
    return render(request, "play/table.html", {
        "state_json": json.dumps(_state(c)),
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
    return JsonResponse(full_sheet(pc))


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
    if c.character_id:
        roster.record(c.character_id, pc)
    c.save()
    return JsonResponse({**_state(c), "levelled": result})


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
        limit=int(request.GET.get("limit", 60) or 60),
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


def _level_of(actor, spell_id: str):
    """The spell's level for this caster, or None if this build does not ship it.

    A prepared list can name a spell a later build removed or renamed. Raising here would
    make the whole spell page 500 over one stale id.
    """
    from rules import casting, spells as spells_mod

    try:
        return casting.spell_level_for(actor, spells_mod.get(spell_id))
    except KeyError:
        return None


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

    if action == "learn":
        if spell.id not in pc.spellbook:
            pc.spellbook.append(spell.id)
    elif action == "forget":
        pc.spellbook = [s for s in pc.spellbook if s != spell.id]
        casting.unprepare(pc, spell.id, 99)
    elif action == "prepare":
        if not casting.knows(pc, spell):
            return JsonResponse(
                {"error": f"{spell.name} is not in {pc.name}'s spellbook"}, status=400)
        # Counted against the slots of that level, including what is already prepared:
        # a wizard cannot memorise five fireballs into two slots.
        holding = sum(n for sid, n in pc.prepared.items()
                      if _level_of(pc, sid) == level)
        room = casting.slots_for(pc).get(level, 0)
        if holding + count > room:
            return JsonResponse(
                {"error": f"{pc.name} has {room} level {level} slots and has already "
                          f"prepared {holding}"}, status=409)
        casting.prepare(pc, spell.id, count)
    elif action == "unprepare":
        casting.unprepare(pc, spell.id, count)
    else:
        return JsonResponse(
            {"error": "action must be learn, forget, prepare or unprepare"}, status=400)

    c.save()
    return JsonResponse(full_sheet(pc))


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
        said = player_input.check(text)
        if not said.ok:
            return JsonResponse({"hint": said.hint, "offending": said.offending},
                                status=422)

    # A character at or below 0 hit points does not get a turn. Nothing used to ask:
    # Kesst was dying at -3, the player typed "now what", and the GM cheerfully narrated
    # her dodging and stumbling while a thug attacked her and a second encounter began.
    # What happens to the downed is the rules' business, not the GM's.
    if c.ended:
        return JsonResponse(_ended_payload(c), status=410)

    pc = c.scene.pc()
    if downed.state_of(pc) not in ("fine", "disabled"):
        c.transcript.append({"who": "player", "text": shown})
        outcome = downed.resolve(c)
        for line in outcome.lines:
            c.transcript.append({"who": "gm", "text": line, "kind": "consequence"})
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

    c.transcript.append({"who": "player", "text": shown})
    world = c.world
    agent = GMAgent(world, c.engine())
    _arm_cards(agent, c)

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
        return JsonResponse({"error": str(exc)}, status=503)
    except IntentError as exc:
        c.transcript.pop()
        return JsonResponse({"error": f"The GM could not produce a legal turn. {exc}"},
                            status=502)

    return _advance(c, agent, plan.narration, plan, text)


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
        said = str(exc)
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
    return _finish(c, agent, resolution, "", label, plan=None, hand_over=end_turn)


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
    return _with(resp, {"rolled": face})


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


def _ask_the_gm(c, engine, question: str) -> str:
    """The model, grounded in the brief, answering out of character.

    No history and no worked examples, deliberately: the examples teach it to write
    scenes, which is the one thing this must not do, and the history is the fiction the
    player has just stepped out of.
    """
    agent = GMAgent(c.world, engine)
    brief = prompts.scene_brief(
        c.world, c.scene, c.location, _recent_events(c.world, c.location),
        here=engine.here(), known=engine.places())
    found = "\n".join(gm_answers.look_up(c, engine, question))
    try:
        reply = client.chat(
            prompts.out_of_character_messages(brief, question, found),
            agent.prose_model, agent.prose_host, as_json=False, think=False,
            temperature=0.4, num_predict=320, provider=agent.prose_provider,
            api_key=agent.prose_key)
    except ModelUnavailable as exc:
        return ("The engine has nothing filed under that, and the GM is not answering: "
                f"{exc}\nIt can always answer these from its own state: "
                + ", ".join(sorted(gm_answers.TOPICS)) + ".")
    said = " ".join(str(getattr(reply, "text", "") or "").split())
    if not said:
        return ("The engine has nothing filed under that, and the GM had nothing to "
                "say either. It can always answer these from its own state: "
                + ", ".join(sorted(gm_answers.TOPICS)) + ".")
    return "The GM, out of character:\n  " + said


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


def _finish(c, agent, resolution, narration, player_input, plan, hand_over=True):
    """Narrate what the engine decided, then let the world answer.

    `hand_over` is False for an action that does not end your turn — a free action, a
    toggle, a swift. The combat panel accepted `end_turn: false` and this ran the NPC
    turns anyway, so forming the blood armament (a free action) handed the bear a swing:
    the round moved on while the player still had their standard action in hand.
    """
    if resolution.awaiting:
        c.save()
        return JsonResponse(_state(c))

    # The thread first, so the brief below states the engagement this very turn
    # declared — "I follow the guards" must constrain the beat that answers it.
    judgement.update_thread(c.scene, player_input,
                            [o.op for o in resolution.outcomes])
    judgement.note_heat(c.scene, resolution.outcomes)
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

    outcomes = [o for o in resolution.outcomes if o.tell]
    if getattr(agent, "intents_first", False):
        # The experiment's other half: call 1 wrote no prose, so this call writes the
        # whole turn — and it writes it knowing what the dice did. Runs whether or not
        # there are tells, because a `narrate_only` turn with no prose is a blank page
        # and most town turns are `narrate_only`.
        brief = prompts.scene_brief(c.world, c.scene, c.location,
                                    _recent_events(c.world, c.location),
                                    here=agent.engine.here(),
                                    known=agent.engine.places(),
                                    # The prose sees the cards in play, never the
                                    # GM's secret ones.
                                    recent=[b["text"] for b in c.transcript[-4:]],
                                    turn=len(c.transcript))
        earlier = [b["text"] for b in c.transcript[-8:] if b["who"] == "gm"]
        try:
            text, repairs, prose_attempts = agent.narrate_turn(
                resolution.outcomes, player_input, brief, earlier)
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
            "repairs": list(repairs or []),
            "attempts": [{"kind": a.kind, "seconds": round(a.seconds, 1),
                          "model": a.model, "note": (a.note or "")[:300],
                          "raw": (a.raw or "")[:300]}
                         for a in prose_attempts],
        })
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
        def _floor(reason: str) -> str:
            if judgement.was_speech(player_input):
                repairs.append(f"{reason}: the player spoke, so the answer is theirs")
                return narration_mod.unanswered_speech(
                    player_input,
                    [a.name for a in c.scene.actors.values() if not a.is_pc],
                    turn=len(c.transcript))
            repairs.append(f"{reason}: replaced with a holding line")
            return ("The moment holds — nothing new shows itself just yet. "
                    "What do you do?")

        if not text:
            # A turn may NEVER answer with silence. Measured live: "I talk to
            # the woman" produced no beat at all — the prose call whiffed, there
            # were no tells, no degraded sentence, and the empty string skipped
            # every floor below because they all lived inside `if text`.
            text = _floor("empty turn")
        if text:
            text, anchored = narration_mod.keep_the_thread(text, c.scene.thread)
            if anchored:
                repairs.append(f"the thread held: re-tethered {anchored!r}")
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
            introduced = judgement.note_cast(c.scene, text, turn=len(c.transcript))
            judgement.promote_cast(c.scene, introduced)
            # And whoever the beat says stopped watching is in the fight, with their
            # kind: "the second guard draws" is a second guard on the initiative.
            for ref, side in judgement.joiners(c.scene, text):
                if agent.engine.join_fight(ref, side):
                    repairs.append(f"{c.scene.actors[ref].name} joined the fight "
                                   f"on {'your' if side == 'pc' else 'their'} side")
                    agent.engine.rally(ref)
            c.transcript.append({"who": "gm", "text": text, "kind": "setup"})
            c.history.append({"role": "assistant", "content": text})
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
        c.turn_log.append({"kind": "resolution",
                           "outcomes": [o.as_dict() for o in resolution.outcomes]})

    # A battle that just JOINED is not a turn that just ENDED. The deferred first
    # swing left the player holding the action they declared; running the NPC loop
    # here would hand the other side the first blow the announcement promised the
    # player. They act at the combat panel; the loop runs when that turn ends.
    joined = any(e.get("kind") == "battle_joined"
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
                                     "text": plain_tell(o.tell)})
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
        c.turn_log.append({"kind": "npc-turn", "ref": ref,
                           "intents": [i.as_dict() for i in plan.intents],
                           "outcomes": [o.as_dict() for o in resolution.outcomes]})
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
        # An NPC's turn is not the player speaking, so the ledger gets no speech
        # from it — only whatever the engine decided on their behalf.
        _remember(c, resolution, "")
    _log_turn(c, plan, resolution)

    # The budget ran out with somebody else holding the turn. Whatever went wrong,
    # the player is not left staring at a panel where every button refuses: the
    # turn comes back to them and what was cut is said out loud. Parked directly
    # rather than advanced, because advancing ticks rounds and expires holds — the
    # skipped creatures lose their turn, which is a mercy to the player, not a
    # round of free time for anyone.
    _hand_the_turn_back(c, "The scuffle blurs; the moment comes back to you.")


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
    spoke = ""
    if judgement.was_speech(player_input):
        here = [a.name for a in c.scene.actors.values() if not a.is_pc]
        spoke = next(
            (n for n in here
             if len(str(n).split()[-1]) > 2
             and str(n).split()[-1].lower() in (player_input or "").lower()),
            "someone")
    ledger_mod.keep(c.ledger, ledger_mod.note(
        resolution.outcomes,
        turn=len(c.transcript),
        hist=len(c.history),
        spoke_with=spoke,
        where=getattr(c.location, "name", "") or "",
        names={r: a.name for r, a in c.scene.actors.items()}))


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
    # The turn entry `_advance` wrote before the prose call, wherever it now sits.
    # `replace` used to look only at the LAST entry, and under intents-first the
    # prose entry is appended between the two — so every single turn was logged
    # twice. Read out of a live save: eight "turn" entries for four turns, four
    # exact duplicate pairs, and the log that is supposed to answer "what did the
    # engine do" claimed the spawn happened twice.
    if replace:
        for i in range(len(c.turn_log) - 1, -1, -1):
            if c.turn_log[i].get("kind") == "turn":
                c.turn_log[i] = entry
                return
    c.turn_log.append(entry)


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
    try:
        engine = c.engine()
        resolution = engine.run(engine.validate([{
            "op": "use_item", "actor": "pc",
            "because": f"{pc.name} reaches for it",
            "params": {"item": item, "how": how, "to": target},
        }]))
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
    from rules.sheet import full_sheet

    return JsonResponse({"ok": True, "tell": tell, "sheet": full_sheet(pc)})


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
    """
    from rules import keepers

    for ref, a in scene.actors.items():
        if a.is_pc or a.is_down:
            continue
        # Whoever keeps this counter, first and by what they ARE rather than by what
        # they are called. The name test below cannot see a keeper: they are named out
        # of the world ("Gorvothys Vyrnys") precisely so that they are a person and not
        # a job title, and a panel that only opens for people called "the stallholder"
        # would refuse every real shopkeeper this app builds.
        if keepers.keeps_a_counter(a):
            return a
        if _MERCHANT.search(str(a.name or "")) or _MERCHANT.search(str(a.kind or "")):
            return a
    return None


def _counter_refusal(c, pc):
    """The merchant's answer to a wanted character: no, with the reason named. Else
    None (docs/wanted.md, reader two).

    The panel's half of the price reader. Prices for the suspected go up through
    `pricing.markup_for` and nobody refuses them; for the wanted the stallholder will
    not be seen trading — Fallout: New Vegas's merchants do the same to the Vilified —
    and says so, so the player knows which town's name to clear. Both doors of the
    counter ask this one helper, for the reason `_cannot_act` gives: a rule with two
    homes drifts. Asked through the vocabulary, so the one `remove_effects(source=...)`
    that clears the name reopens the counter with nothing else touched.
    """
    from rules import attitude, states

    merchant = _merchant_here(c.scene)
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


def _stall_of(c) -> tuple[str, str, int]:
    """Which shop, on which day. Read the same way `craft_views` reads it, so a stall's
    money and its stock agree about where and when this is.

    A present merchant names the stall, so two different vendors in one town are two
    different shelves and two different tills — and the same vendor's stock holds for
    the in-game day (`day_of` is the clock in 24-hour windows), which is the persistence
    the table asked for.
    """
    from rules import market

    merchant = _merchant_here(c.scene)
    stall = re.sub(r"[^a-z0-9]+", "-", str(merchant.name).lower()).strip("-") \
        if merchant else "market"
    return (str(c.scene.location_id or "nowhere"), stall,
            market.day_of(c.scene.clock_minutes))


def _row(item, price: float, count: int = 1) -> dict:
    from rules import pricing

    return {"id": str(getattr(item, "id", "")), "name": str(getattr(item, "name", "")),
            "tier": str(getattr(item, "tier", "") or "common"), "count": count,
            "gp": round(price, 2), "price": pricing.as_text(price),
            # What the engine can actually run with it, which is a quarter of the price
            # when the answer is nothing — worth showing beside the number.
            "does_something": bool(getattr(item, "specs", None))}


@require_POST
def trade(request):
    """Both sides of a counter: what you are carrying, and what they have."""
    from rules import goods, market, pricing, states

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)

    if _merchant_here(c.scene) is None:
        return JsonResponse({"error": (
            "There is nobody here to trade with. Find a stall and speak to whoever "
            "keeps it — or simply say what you sell or buy, and the scene handles "
            "it.")}, status=409)
    refusal = _counter_refusal(c, pc)
    if refusal:
        return refusal

    body = read_body(request)
    place, stall, day = _stall_of(c)
    stall = str(body.get("stall") or stall)
    tier = str(body.get("tier") or market.DEFAULT_STALL_TIER)

    till = market.purse(place, stall, day, tier)
    left = round(till - market.spent_today(c.scene.market_taken, place, stall, day), 2)
    counter = market.on_sale(place, stall, day, c.scene.market_taken, tier)

    return JsonResponse({
        "stall": stall, "place": place, "day": day,
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
        "theirs": sorted((_row(m, pricing.worth(m, buyer=pc, town=place)) for m in counter),
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
    if _merchant_here(c.scene) is None:
        return JsonResponse({"error": "There is nobody here to trade with."},
                            status=409)
    refusal = _counter_refusal(c, pc)
    if refusal:
        return refusal

    body = read_body(request)
    op = str(body.get("op", "")).strip().lower()
    if op not in ("sell", "buy"):
        return JsonResponse({"error": "sell or buy"}, status=400)

    place, stall, day = _stall_of(c)
    params = {"item": str(body.get("item", "")).strip().lower(),
              "count": read_int(body, "count", 1, lo=1, hi=999),
              "stall": str(body.get("stall") or stall)}
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
