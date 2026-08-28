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

from gm import judgement, narration as narration_mod, prompts, watcher
from gm.agent import GMAgent
from gm.client import ModelUnavailable, available
from rules import biomes, grid, ingredients as ing_mod
from rules.intents import IntentError

from . import campaign as campaign_mod
from .apiutil import read_body, read_int
from . import downed, player_input, roster


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
        "reachable": [],
    }
    pc = scene.pc()
    if pc is not None and pc.ref in scene.positions and pc.can_act():
        routes = g.reachable(scene.positions[pc.ref], pc.speed_feet, size=pc.size,
                             occupied=scene.occupied(ignore=pc.ref))
        out["reachable"] = [[c, r, cost] for (c, r), cost in sorted(routes.items())]
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
    from rules import goods as goods_mod

    coins = goods_mod.coinage(c.world, c.location)
    return {
        "transcript": c.transcript,
        # What money is called here. Sent with the state because it is a fact about the
        # world, not a constant: a purse rendered with hard-coded "gp" would be the one
        # thing on the page that had never heard of the world it is being played in.
        "coinage": [{"id": x.id, "name": x.name, "plural": x.plural,
                     "copper": x.copper, "coined": x.coined} for x in coins],
        "suggestions": list(getattr(c, "suggestions", []) or []),
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
                 "size": a.size, "squares": grid.size_squares(a.size),
                 "at": list(c.scene.positions[r]) if r in c.scene.positions else None,
                 "conditions": [x.name for x in a.conditions]}
                for r, a in c.scene.actors.items()
            ],
            "grid": _grid_state(c.scene),
            # Blood on the ground. Sent whether or not there is a grid: without one
            # they are still a count the player needs, because half the class spends
            # them.
            "pools": [b.as_dict() for b in c.scene.pools],
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

    # The mechanics, all through the ordinary applicators.
    for gone in ("dead", "dying", "stable", "unconscious", "disabled"):
        pc.remove_condition(gone)
    pc.hp = pc.hp_max
    pc.nonlethal = 0

    factions = [f.get("name") for f in (c.world.factions or [])
                if isinstance(f, dict) and f.get("name")]
    dice = Dice(c.seed)
    patron = (factions[dice.roll("1d%d" % len(factions), visibility="hidden").total - 1]
              if factions else "a stranger whose face you never see")
    days = 7 + dice.roll("2d10", label="days lost", visibility="hidden").total
    c.scene.clock_minutes += days * 24 * 60
    pc.add_condition("life debt", source=patron)

    c.scene.end_encounter()
    # The fight that killed them is long over and far away; the bodies stay there.
    for ref in [r for r, a in list(c.scene.actors.items()) if not a.is_pc]:
        c.scene.remove(ref) if hasattr(c.scene, "remove") else c.scene.actors.pop(ref)

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
def characters(request):
    """Everyone who has been played, and everyone available to play."""
    c = campaign_mod.current()
    return JsonResponse({
        "playing": c.character_id,
        "ended": c.ended,
        "roster": [{**e.summary(), "playable": e.status != roster.DEAD,
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
    """
    c = campaign_mod.current(reset=request.GET.get("new") == "1")
    return render(request, "play/table.html", {
        "state_json": json.dumps(_state(c)),
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
    if not c.scene.awaiting:
        watcher.drain(c)
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
CARRY_ON = ("I take no action. Carry the scene on from where it stopped: if I asked "
            "somebody something, let them answer in their own words, and let the people "
            "and the place here go on doing what they were doing.")


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
        c.save()
        return JsonResponse(_state(c))

    c.transcript.append({"who": "player", "text": shown})
    world = c.world
    agent = GMAgent(world, c.engine())

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

    return _advance(request, c, agent, plan.narration, plan, text)


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
        return JsonResponse({"error": "It is not your turn."}, status=409)

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

    if not raw:
        # End turn with nothing declared: the round moves on. Marked as acted so the
        # first blow of the next fight does not find the PC flat-footed for passing.
        scene.acted.add(pc.ref)
        if end_turn:
            _run_npc_turns(c, agent)
        c.save()
        return JsonResponse(_state(c))

    c.transcript.append({"who": "player", "text": label or "(the combat panel)"})
    try:
        intents = engine.validate(raw)
        resolution = engine.run(intents)
    except (IntentError, ValueError) as exc:
        c.transcript.pop()
        return JsonResponse({"error": str(exc)}, status=400)

    # A free action is remembered for the next spoken turn, so the narrator hears about
    # it without a turn ever having been spent on it. In-memory on purpose: it is a note
    # between two turns of one sitting, not campaign state.
    if not end_turn and label:
        c.pending_free = list(getattr(c, "pending_free", []) or []) + [label]

    # A turn the player has not finished does not pass to anybody. This is what
    # `end_turn` was always supposed to mean.
    return _finish(c, agent, resolution, "", label, plan=None, hand_over=end_turn)


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
    _log_turn(c, plan, resolution)

    if resolution.awaiting:
        c.save()
        return JsonResponse(_state(c))

    return _finish(c, agent, resolution, narration, player_input, plan)


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
                                    _recent_events(c.world, c.location))
        earlier = [b["text"] for b in c.transcript[-8:] if b["who"] == "gm"]
        try:
            text, repairs, prose_attempts = agent.narrate_turn(
                resolution.outcomes, player_input, brief, earlier)
        except ModelUnavailable:
            text, repairs, prose_attempts = "", [], []
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
        if not text:
            # A turn may NEVER answer with silence. Measured live: "I talk to
            # the woman" produced no beat at all — the prose call whiffed, there
            # were no tells, no degraded sentence, and the empty string skipped
            # every floor below because they all lived inside `if text`.
            text = ("The moment holds — nothing new shows itself just yet. "
                    "What do you do?")
            repairs.append("empty turn: replaced with a holding line")
        if text:
            text, anchored = narration_mod.keep_the_thread(text, c.scene.thread)
            if anchored:
                repairs.append(f"the thread held: re-tethered {anchored!r}")
            text, rewrit = narration_mod.already_there(
                text, (c.scene.thread or {}).get("where"))
            if rewrit:
                repairs.append("arrivals at the place they already stand: "
                               f"rewrote {len(rewrit)}")
            # The floor of last resort. Measured live on a Continue: the model
            # echoed the instruction itself, the groomers compressed the echo,
            # and the beat that shipped was "You take scene on." — four words
            # against a 600-character scene floor every earlier gate is supposed
            # to hold. A beat this short with no dice behind it is not a beat.
            if len(text.strip()) < 60 and not outcomes:
                text = ("The moment holds — nothing new shows itself just yet. "
                        "What do you do?")
                repairs.append("beat too short to stand: replaced with a "
                               "holding line")
            # The beat is final; whoever it introduced is on the books now —
            # and on the board: a noted person the engine does not hold cannot
            # be attacked, addressed or found again.
            introduced = judgement.note_cast(c.scene, text, turn=len(c.transcript))
            judgement.promote_cast(c.scene, introduced)
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
    if replace and c.turn_log and c.turn_log[-1].get("kind") == "turn":
        c.turn_log[-1] = entry
    else:
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
    try:
        engine = c.engine()
        resolution = engine.run(engine.validate([{
            "op": "use_item", "actor": "pc",
            "because": f"{pc.name} reaches for it",
            "params": {"item": item, "how": how, "to": target},
        }]))
    except IntentError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        # A jar with authored effects the engine chokes on must be a sentence in the
        # sheet, not a 500 with an invisible error — "clicking the drink button does
        # nothing" was exactly this, twice over.
        return JsonResponse({"error": f"{type(exc).__name__}: {exc}"}, status=400)

    tell = " ".join(o.tell for o in resolution.outcomes if o.tell)
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
    for ref, a in scene.actors.items():
        if a.is_pc or a.hp <= 0:
            continue
        if _MERCHANT.search(str(a.name or "")) or _MERCHANT.search(str(a.kind or "")):
            return a
    return None


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
    from rules import goods, market, pricing

    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)

    if _merchant_here(c.scene) is None:
        return JsonResponse({"error": (
            "There is nobody here to trade with. Find a stall and speak to whoever "
            "keeps it — or simply say what you sell or buy, and the scene handles "
            "it.")}, status=409)

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
        "mine": sorted(
            (_row(s, pricing.what_a_shop_pays(s), s.count) for s in pc.stock.values()),
            key=lambda r: -r["gp"]),
        "theirs": sorted((_row(m, pricing.worth(m)) for m in counter),
                         key=lambda r: -r["gp"]),
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

    try:
        engine = c.engine()
        resolution = engine.run(engine.validate(
            [{"op": op, "actor": "pc", "because": "at the counter", "params": params}]))
    except IntentError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        # The same rule the drink button learned: a trade that cannot happen is a
        # sentence on the screen, never a 500 with an invisible error.
        return JsonResponse({"error": f"{type(exc).__name__}: {exc}"}, status=400)

    tell = " ".join(o.tell for o in resolution.outcomes if o.tell)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": tell})
    c.save()
    return JsonResponse({"ok": True, "tell": tell})
