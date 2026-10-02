"""The crafting bench, as a browser page.

Its own module rather than more of `views.py`, which is the play loop and should stay
that. Nothing here talks to a model: crafting is arithmetic over ingredients and a track,
so it is engine work start to finish.

The workbench is assumed to fold out wherever the character is standing, per the design
call, so a chain is judged on the crafter and the materials alone and never on location.
"""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from rules import (benches, biomes, consumables, crafting, foraging, goods,
                   ingredients, market, worldclass)
from rules.dice import BadDice
from rules.intents import IntentError

from . import campaign as campaign_mod
from .apiutil import read_body, read_int

# The disciplines the app knows about. Only Herbalism has rules behind it; the rest are
# declared so the page is honest about what is coming instead of hiding it. `track` is
# None where no world class exists yet, and the tab says so rather than 404ing.
DISCIPLINES = [
    {"id": "herbalism", "name": "Herbalism", "track": "herbalist",
     "blurb": "Foraging, harvesting and brewing — poultices, teas, tinctures, elixirs.",
     # The chain bench retired for herbalism on 2026-10-02: it works one step at a time
     # at the table now (docs/herbalism-revamp-plan.md, play/bench_views.py). Foraging
     # and the acquisition hub stay here. The page reads `moved` and draws a card.
     "moved": "Herbalism is at the table now: open the bench from the table to work "
              "one step at a time. Foraging stays here."},
    {"id": "alchemy", "name": "Alchemy", "track": "alchemist",
     "blurb": "Reagents, reactions, and bottled consequences."},
    {"id": "blacksmithing", "name": "Blacksmithing", "track": "blacksmith",
     "blurb": "Forge work: weapons, armour, and the tools every other craft needs."},
    {"id": "leatherworking", "name": "Leatherworking", "track": "leatherworker",
     "blurb": "Hides into armour, straps, cases and bindings."},
    {"id": "enchanting", "name": "Enchanting", "track": "enchanter",
     "blurb": "Binding lasting magic into objects that will hold it."},
]

# Each discipline's own shelf. Herbalism reads the herb corpus through `ingredients`;
# the four newer tracks each carry a materials module with the same as_dict shape.
# Chains for these benches are the next slice — the guard in preview/do says so
# rather than letting `crafting.preview` misread a forge chain as a brew.
_MATERIALS_OF = {
    "alchemist": "rules.alchemist",
    "blacksmith": "rules.blacksmith",
    "leatherworker": "rules.leatherworker",
    "enchanter": "rules.enchanter",
}


def _craft_materials(track_id: str) -> list[dict]:
    """This bench's shelf. The modules read the whole folder as one shared shelf, so
    the bench filters to its own shipped catalogue — a forge listing hides under its
    default kind would mislabel them. A homebrew entry belongs to no shipped file and
    shows on every bench, which errs toward visible rather than lost."""
    import importlib
    import json as json_mod
    from pathlib import Path

    from django.conf import settings

    shipped: dict[str, set[str]] = {}
    for p in (Path(settings.BASE_DIR) / "content" / "materials").glob("*.json"):
        try:
            data = json_mod.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        shipped[p.stem] = {str(m.get("id", "")).strip().lower()
                           for m in data.get("materials", [])}
    own = shipped.get(f"{track_id}-materials", set())
    elsewhere = set().union(*(v for k, v in shipped.items()
                              if k != f"{track_id}-materials")) if shipped else set()

    mod = importlib.import_module(_MATERIALS_OF[track_id])
    return [m.as_dict() for mid, m in sorted(mod.materials().items())
            if mid in own or mid not in elsewhere]


def _is_night(campaign) -> bool:
    """Whether it is dark, from the scene's own clock.

    Asked here rather than by each bench: the world clock is campaign state, and a
    binding circle should not have to know how this app stores time. Dusk to dawn, the
    same window the survival rules treat as night.
    """
    minutes = int(getattr(campaign.scene, "clock_minutes", 0) or 0) % 1440
    return minutes >= 18 * 60 or minutes < 6 * 60


def _discipline(disc_id: str) -> dict:
    found = next((d for d in DISCIPLINES if d["id"] == disc_id), None)
    if found is None:
        raise LookupError(f"no such craft {disc_id!r}")
    return found


def _track_state(campaign, disc: dict) -> dict:
    """Where the character stands in this discipline, and what it has unlocked."""
    pc = campaign.scene.pc()
    if not disc["track"] or pc is None:
        return {"available": False, "blurb": disc["blurb"], "name": disc["name"]}

    track = worldclass.get(disc["track"])
    progress = pc.track(track.id)
    here = track.at(progress.level)
    return {
        "available": True,
        # Present only for a discipline whose chains moved to another bench (herbalism).
        **({"moved": disc["moved"]} if disc.get("moved") else {}),
        "track": track.id,
        "name": track.name,
        "level": progress.level,
        "max_level": track.max_level,
        "mp": progress.mp,
        "to_next": worldclass._remaining(track, progress),
        "max_tier": here.max_tier,
        "max_rank": worldclass.tier_rank(here.max_tier),
        "methods": track.unlocked_methods(progress.level),
        # Every method, including the ones still out of reach, each with the level that
        # grants it. A station the player cannot use yet is a reason to keep going; a
        # station that is simply absent is not.
        "all_methods": [
            {"method": m, "level": lvl.level, "known": lvl.level <= progress.level}
            for lvl in sorted(track.levels, key=lambda x: x.level)
            for m in lvl.methods
        ],
        "tools": track.unlocked_tools(progress.level),
        "known_recipes": len(progress.crafted),
        # What each station does and what it wants, for the tooltip on every method
        # chip: "what bonus it gives and what you need it for". Authored beside the
        # method in the track's own file, so a craft that invents a station documents
        # it in the same edit rather than in a second place nobody remembers.
        "method_help": _method_help(track),
        "descriptions": _raw_track(track).get("method_descriptions") or {},
        # Secondary tabs — the enchanter's book-faithful magic-item mode is the first.
        "modes": benches.modes_for(track.id),
        # What this craft can be told to make, if it needs telling. A forge shapes a
        # base item and a tannery cuts a pattern; herbalism names its output from what
        # went in the pot and answers with an empty list, which is how the page knows
        # not to draw the row at all.
        "shapes": _shapes_for(track.id),
        "glyphs": benches.glyphs().get(track.id, {}),
        "method_glyphs": benches.method_glyphs(track.id),
    }


def _shapes_for(track_id: str) -> list[str]:
    """The base items or patterns this craft can be asked for.

    Asked of the module rather than listed here, so a craft that learns to make a new
    kind of thing does not need this file edited. A craft that names its own output —
    herbalism — declares nothing and the bench draws no row.
    """
    try:
        mod = benches.module_for(track_id)
    except benches.UnknownBench:
        return []
    for attr in ("SHAPES", "PRODUCTS", "BASE_ITEMS"):
        got = getattr(mod, attr, None)
        if isinstance(got, dict):
            return sorted(got)
        if isinstance(got, (list, tuple)):
            return sorted(str(x) for x in got)
    # A craft that resolves a base item against the real weapon and armour tables can
    # be asked for anything in them — the forge is the case: it declares no list of its
    # own because the list is the rulebook's, and duplicating 456 weapon names into the
    # module would be a second copy to keep level with the first.
    if hasattr(mod, "base_item"):
        from rules.tables import ARMOUR
        from rules.weapons import all_weapons

        return sorted({str(w) for w in all_weapons()} | {str(a) for a in ARMOUR})
    return []


def _raw_track(track) -> dict:
    """The track's own JSON, for the fields the `Track` dataclass does not model.

    `method_help` and `method_descriptions` are documentation rather than rules, so
    `worldclass.Track` has no field for them and adding one would make every consumer of
    a Track carry prose it never reads. Loaded from the file instead, shipped or
    homebrew, by the same precedence `worldclass.tracks()` uses.
    """
    import json as json_mod
    from pathlib import Path

    from django.conf import settings

    for folder in (Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "world-classes",
                   Path(settings.BASE_DIR) / "content" / "world-classes"):
        path = folder / f"{track.id}.json"
        if path.is_file():
            try:
                return json_mod.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


def _method_help(track) -> dict:
    """`{method: {does, needs, for}}` for every method the track names.

    A method with no authored help still gets an entry, so the tooltip is never empty
    on screen: an unexplained station is the thing the player is complaining about.
    """
    raw = _raw_track(track)
    help_table = raw.get("method_help") or {}
    described = raw.get("method_descriptions") or {}
    out = {}
    for lvl in track.levels:
        for m in lvl.methods:
            entry = dict(help_table.get(m) or {})
            entry.setdefault("does", described.get(m, ""))
            entry.setdefault("needs", "")
            entry.setdefault("for", "")
            entry["level"] = lvl.level
            out[m] = entry
    return out


def _chain_from(body: dict, track_id: str) -> crafting.Chain:
    return crafting.Chain(
        track=track_id,
        methods=[str(m).strip().lower() for m in body.get("methods", [])],
        ingredient_ids=[str(i).strip().lower() for i in body.get("ingredients", [])],
        name=str(body.get("name", "")).strip(),
        stock_used={str(k): int(v) for k, v in (body.get("stock") or {}).items()
                    if int(v) > 0},
    )


def _bench_stock(campaign, disc: dict) -> dict:
    """What this bench can reach for, in the shape its own module expects.

    Herbalism's pot takes crafted jars — a tea goes back in to be concentrated — and
    reads raw herbs separately through `satchel`. The four newer benches make no such
    distinction: an ore and a masterwork blade are both "stock", counted, and their
    `_stock_entry` readers accept a bare number. So the satchel is folded in for them
    and left alone for herbalism, rather than teaching four modules a split that only
    one craft has a reason for.
    """
    pc = campaign.scene.pc()
    if pc is None:
        return {}
    crafted = _stock_of(campaign, disc["id"])
    if disc["track"] == "herbalist":
        return crafted
    merged: dict = {mid: int(n) for mid, n in pc.inventory.items() if n}
    for key, item in crafted.items():
        merged[key] = item
    return merged


def _stock_of(campaign, craft_id: str) -> dict:
    """What the character has made in this discipline, and can craft with again.

    Filtered by discipline because a bench should offer what belongs on it: a jar of tea
    is not a thing you reach for at a forge.
    """
    pc = campaign.scene.pc()
    if pc is None:
        return {}
    track = next((d["track"] for d in DISCIPLINES if d["id"] == craft_id), None)
    return {k: v for k, v in pc.stock.items() if not track or v.craft == track}


@ensure_csrf_cookie
@require_GET
def craft_page(request):
    """`ensure_csrf_cookie` for the same reason the table has it: without the cookie the
    page renders perfectly and then every POST 403s, with nothing on screen saying why."""
    c = campaign_mod.current()
    pc = c.scene.pc()
    return render(request, "play/craft.html", {
        "state_json": json.dumps({
            "disciplines": DISCIPLINES,
            "pc": {"name": pc.name if pc else "", "hp": pc.hp if pc else 0,
                   "hp_max": pc.hp_max if pc else 0},
            "tracks": {d["id"]: _track_state(c, d) for d in DISCIPLINES},
            "recipes": c.recipes,
        }),
    })


@require_GET
def craft_ingredients(request):
    """The shelf. Out-of-reach material is returned marked, never filtered out.

    A shelf that silently hides the interesting half gives a player no reason to level.
    One that shows a Phoenix Feather greyed with the tier it needs gives them a goal.
    """
    c = campaign_mod.current()
    try:
        disc = _discipline(request.GET.get("craft", "herbalism"))
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    state = _track_state(c, disc)
    ceiling = state.get("max_rank", 0)

    mode = str(request.GET.get("mode", "")).strip().lower()
    if mode and benches.supports(disc["track"], mode):
        # A secondary mode brings its own shelf — the magic-item mode's is a catalogue
        # of named properties and wondrous items, not the essences next door.
        mod = benches.module_for(disc["track"], mode)
        listing = getattr(mod, "catalogue", None) or getattr(mod, "materials", None)
        mats = [m.as_dict() for _, m in sorted((listing() or {}).items())] if listing else []
        for d in mats:
            d["usable"] = bool(ceiling) and int(d.get("rank", 1)) <= ceiling
        state = dict(state, glyphs=getattr(mod, "KIND_GLYPH", {}) or state.get("glyphs", {}))
        return JsonResponse({"ingredients": mats, "stock": [], "track": state,
                             "mode": mode, "biome": c.biome,
                             "biome_describe": biomes.describe(c.biome)})

    if disc["track"] in _MATERIALS_OF:
        # This bench's own catalogue, tier-marked the same way the herb shelf is.
        # No satchel counts yet: acquisition (mining, skinning, markets) is the next
        # slice, and a count of zero on everything would read as a bug rather than
        # a not-yet.
        mats = _craft_materials(disc["track"])
        # What is actually in the satchel, the same way the herb shelf reports it. Left
        # off, every forge material read as "none carried" and the "only what I am
        # carrying" filter emptied the shelf — the bench could not tell you that you
        # were holding the very ore you had just dug up.
        pc = c.scene.pc()
        satchel = dict(pc.inventory) if pc else {}
        for d in mats:
            d["usable"] = bool(ceiling) and int(d.get("rank", 1)) <= ceiling
            d["held"] = int(satchel.get(d["id"], 0))
        return JsonResponse({"ingredients": mats,
                             "stock": [s.as_dict() for s in
                                       sorted(_stock_of(c, disc["id"]).values(),
                                              key=lambda s: s.name.lower())],
                             "track": state, "biome": c.biome,
                             "biome_describe": biomes.describe(c.biome)})

    out = []
    for ing in sorted(ingredients.all_ingredients().values(), key=lambda i: i.name):
        d = ing.as_dict()
        d["usable"] = bool(ceiling) and d["rank"] <= ceiling
        out.append(d)

    pc = c.scene.pc()
    satchel = dict(pc.inventory) if pc else {}
    for d in out:
        d["held"] = satchel.get(d["id"], 0)

    stock = []
    for item in sorted(_stock_of(c, disc["id"]).values(),
                       key=lambda s: (s.base.lower(), s.concentration)):
        d = item.as_dict()
        d["usable"] = bool(ceiling) and d["rank"] <= ceiling
        # Read off the effects rather than the name, and grouped the same way the preview
        # groups them, so a jar that will poison whoever drinks it says so on the shelf.
        # A "Purified Draught of Skull Orchid" is not made safe by being called one, and
        # nothing on the shelf used to distinguish the two.
        d["poisons"] = [p.as_dict() for p in
                        consumables.poisons(item.specs, source=item.base)]
        # `can_concentrate` and `concentrates_to` went with the x2 Concentrate (retired
        # 2026-10-02). Concentration is the table bench's Dry and Reduce now.
        stock.append(d)
    return JsonResponse({
        "ingredients": out, "stock": stock, "track": state,
        "biome": c.biome,
        "biome_describe": biomes.describe(c.biome),
        "table": foraging.table_for(c.biome,
                                    state.get("max_rank", 1)).as_dict(),
    })


@require_POST
def craft_preview(request):
    """What the chain would make. Never an error for a chain that is merely bad — the
    problems come back in the body so the page can grey the button and say why."""
    body = read_body(request)
    c = campaign_mod.current()
    try:
        disc = _discipline(str(body.get("craft", "herbalism")))
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    if disc.get("moved"):
        return _moved(disc)
    state = _track_state(c, disc)
    if not state.get("available"):
        return JsonResponse({"error": f"{disc['name']} has no rules yet."}, status=400)

    mode = str(body.get("mode", "")).strip().lower()
    if not benches.supports(state["track"], mode):
        return JsonResponse(
            {"error": f"The {disc['name'].lower()} bench cannot take a chain yet."},
            status=409)

    pc = c.scene.pc()
    try:
        chain = benches.chain_from_body(state["track"], body, mode)
        result = benches.preview(
            state["track"], state["level"], chain, mode=mode,
            stock=_bench_stock(c, disc),
            satchel=dict(pc.inventory) if pc else {},
            carrier=pc, actor=pc, now_minute=c.scene.clock_minutes,
            at_night=_is_night(c), item=body.get("item"), vessel=body.get("item"))
    except benches.UnknownBench as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    except (ValueError, KeyError) as exc:
        # A chain naming a material that does not exist is a bad request, not a crash:
        # the page can say so and the player can pick something else.
        return JsonResponse({"error": str(exc)}, status=400)
    out = result.as_dict()
    # Why each jar on the shelf would be refused by the chain as it currently stands, so
    # the shelf can grey them before one is picked up. The preparation rules were being
    # enforced correctly and saying nothing until you had already built a chain and
    # pressed Craft — which reads exactly like the rules not working at all.
    # Herbalism's own shelf-greying, which reads the herb preparation rules. The other
    # crafts state their refusals in `problems` instead, one chain at a time.
    out["refused"] = (_shelf_refusals(chain.methods)
                      if state["track"] == "herbalist" else {})
    # How many the materials allow, so the bench can offer "all 47" rather than making the
    # player count it out and then find they were three short halfway through the batch.
    out["batch_max"] = batch_max(result, pc)
    return JsonResponse(out)


def _moved(disc: dict) -> JsonResponse:
    """A discipline whose chains are worked elsewhere now, refused in plain words.

    409 rather than 404: the craft exists and the request was well formed; the bench it
    asked has stopped taking that work. Only herbalism today, retired from this page
    when it moved to the table's step bench (docs/herbalism-revamp-plan.md).
    """
    return JsonResponse({"error": disc["moved"], "moved": True}, status=409)


def _shelf_refusals(methods) -> dict:
    """`{ingredient id: why the chain would refuse it}` for everything on the shelf.

    Computed here rather than in the page, from the same walk `preview` uses, because a
    second copy of the preparation rules in JavaScript is the shape of bug this project
    has paid for twice — a rule corrected in one place and left stale in the copy nobody
    looked at. 162 ingredients through a walk of at most a handful of steps is nothing.
    """
    if not methods:
        return {}
    out = {}
    for iid, item in ingredients.all_ingredients().items():
        why = crafting.prep_problem(item, methods)
        if why:
            out[iid] = why
    return out


# A ceiling on one request, well above any real batch. "100 acacia powder tea" is the
# case this exists for; a hand-written request for a million would otherwise roll a
# million d20s before the response ever went out.
MAX_BATCH = 1000


def batch_max(result, pc) -> int:
    """How many of this chain the materials on hand allow.

    Per-dose costs against what is carried, taking the tightest. Reported with the preview
    so the bench can offer "all 47" rather than making the player work it out and then
    discover halfway through a batch that they were three short.
    """
    if pc is None:
        return 0
    limit = MAX_BATCH
    for sid, n in (result.consumes or {}).items():
        if n > 0:
            # A material may be a crafted jar on the shelf or a raw thing in the
            # satchel: the four newer crafts make no distinction and put both in
            # `consumes`, so both places are asked before deciding the count.
            held = getattr(pc.stock.get(sid), "count", 0) or pc.inventory.get(sid, 0)
            limit = min(limit, int(held) // n)
    # Herbalism alone separates raw ingredients from crafted stock. Read with a default
    # rather than demanded of every craft — a forge has no such split, and asking for
    # the field crashed every preview at four of the five benches.
    for iid, n in (benches.result_field(result, "consumes_raw", {}) or {}).items():
        if n > 0:
            limit = min(limit, int(pc.inventory.get(iid, 0)) // n)
    return max(0, limit)


@require_POST
def craft_do(request):
    """Attempt the chain, once or many times over.

    Scored through the engine's `craft` op rather than here, so crafting at this bench and
    crafting narrated at the table pass through exactly one piece of arithmetic. A spoiled
    batch still teaches something, which is the author's rule and the reason failure is
    reported rather than refused.

    A batch is N separate attempts, not one attempt for N doses: its own d20 each time,
    its own success, its own mastery. "i should not need to click the craft button 100
    times" is a complaint about the clicking, and the fix must not quietly become a change
    to the game — one roll for a hundred doses would mean a single 1 spoiling the lot,
    which is a different rule rather than the same rule automated.
    """
    body = read_body(request)
    c = campaign_mod.current()
    try:
        disc = _discipline(str(body.get("craft", "herbalism")))
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    if disc.get("moved"):
        return _moved(disc)
    state = _track_state(c, disc)
    if not state.get("available"):
        return JsonResponse({"error": f"{disc['name']} has no rules yet."}, status=400)

    mode = str(body.get("mode", "")).strip().lower()
    if not benches.supports(state["track"], mode):
        return JsonResponse(
            {"error": f"The {disc['name'].lower()} bench cannot take a chain yet."},
            status=409)

    wanted = read_int(body, "batch", 1, lo=1, hi=MAX_BATCH)
    try:
        chain = benches.chain_from_body(state["track"], body, mode)
    except benches.UnknownBench as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    attempts, made_all, spent_all = [], [], {}
    stopped = ""
    for _ in range(wanted):
        # Recomputed every time round. The shelf changes as the batch runs — doses are
        # spent, and a concentration puts its output back on it — so a preview taken once
        # and reused would be describing a pot that no longer exists by attempt three.
        pc = c.scene.pc()
        try:
            result = benches.preview(
                state["track"], state["level"], chain, mode=mode,
                stock=_bench_stock(c, disc),
                satchel=dict(pc.inventory) if pc else {},
                carrier=pc, actor=pc, now_minute=c.scene.clock_minutes,
                at_night=_is_night(c), item=body.get("item"),
                vessel=body.get("item"))
        except (ValueError, KeyError) as exc:
            if not attempts:
                return JsonResponse({"error": str(exc)}, status=400)
            stopped = str(exc)
            break
        if result.problems:
            if not attempts:
                return JsonResponse({"error": " ".join(result.problems)}, status=400)
            # Out of something, partway through. The doses already made are kept and the
            # reason is reported: a batch that rolled back on running short would throw
            # away work that really happened.
            stopped = " ".join(result.problems)
            break
        try:
            one = _one_craft(c, disc, state, result)
        except IntentError as exc:
            if not attempts:
                return JsonResponse({"error": str(exc)}, status=400)
            stopped = str(exc)
            break
        attempts.append(one)
        if one["made"]:
            made_all.append(one["made"])
        for k, n in one["spent"].items():
            spent_all[k] = spent_all.get(k, 0) + n

    succeeded = sum(1 for a in attempts if a["succeeded"])
    spoiled = len(attempts) - succeeded
    name = attempts[0]["name"] if attempts else ""

    # One line in the transcript however many doses were worked. A hundred crafts is one
    # afternoon at the bench, not a hundred things that happened to the party.
    if len(attempts) == 1:
        a = attempts[0]
        line = (f"{name}: {'made' if a['succeeded'] else 'spoiled'} "
                f"(d20 {a['roll']}{a['bonus']:+d} = {a['total']} vs DC {a['dc']}). "
                f"{a['tell']}").strip()
    elif attempts:
        line = (f"{name} x{len(attempts)}: {succeeded} made, {spoiled} spoiled "
                f"(d20{attempts[0]['bonus']:+d} vs DC {attempts[0]['dc']} each).")
    else:
        line = ""
    if stopped:
        line = f"{line} Stopped: {stopped}".strip()
    if line:
        c.transcript.append({"who": "gm", "kind": "consequence", "text": line})
    c.save()

    last = attempts[-1] if attempts else {}
    return JsonResponse({
        # The single-craft shape is kept intact so the page and everything else reading
        # this endpoint go on working unchanged; the batch block is an addition.
        "succeeded": bool(last.get("succeeded")),
        "roll": last.get("roll"), "chance": last.get("chance"),
        "total": last.get("total"), "bonus": last.get("bonus"),
        "dc": last.get("dc"), "terms": last.get("terms") or [],
        "result": last.get("result"), "tell": last.get("tell", ""),
        "made": last.get("made"), "spent": spent_all,
        "batch": {
            "asked": wanted, "attempted": len(attempts),
            "made": succeeded, "spoiled": spoiled,
            "rolls": [a["roll"] for a in attempts],
            "items": made_all, "stopped": stopped,
        },
        "track": _track_state(c, disc),
    })


def _one_craft(c, disc, state, result) -> dict:
    """One attempt: one roll, one outcome, one advance of the track."""
    engine = c.engine()
    roll = engine.dice.d20(label=f"{disc['name']}: {result.name}", visibility="player")
    face = roll.faces[0]
    # A check, not a percentile behind a curtain. The DC was already computed from the
    # chain and then thrown away in favour of a chance-to-hit; now the die is added to the
    # crafter's own bonus and compared to it, the way every other roll in the game works.
    # Natural 1 and natural 20 keep their usual authority over the arithmetic.
    bonus = int(benches.result_field(result, "bonus", 0) or 0)
    total = face + bonus
    succeeded = face != 1 and (face == 20 or total >= result.dc)

    # The deed a milestone-locked level waits on, recorded when it is actually done.
    # Without this the bench sent no `milestone` at all, so a character could craft the
    # very thing Herbalist 5 asks for and the level stayed locked for good — the points
    # were kept and nothing on the page ever explained what was missing.
    track = worldclass.get(state["track"])
    milestone = track.deed_done(tier=result.tier, success=succeeded)

    resolution = engine.run(engine.validate([{
        "op": "craft", "actor": "pc",
        "because": f"a session at the {disc['name'].lower()} bench",
        "params": {
            "track": state["track"],
            "recipe": result.name.lower(),
            "tier": result.tier,
            "stages": max(1, result.stages),
            "risky": result.risky,
            "failed": not succeeded,
            "milestone": milestone,
            # Two doses in, one of the next band out: the ceiling is checked against
            # what went in, so the engine has to be told which kind of craft this is.
            # Only herbalism concentrates — two doses in, one of the next band out.
            # Read with a default rather than demanded of every craft: a forge has no
            # opinion about concentration and should not have to declare one.
            "concentrating": benches.result_field(result, "concentrating", False),
        },
    }]))

    # The inputs are spent either way. A spoiled batch that hands the ingredients back
    # would make failure free, and the author's own note is that failure matters because
    # "rare ingredients spoil".
    pc = c.scene.pc()
    spent = {}
    for sid, n in result.consumes.items():
        # A material may be a crafted jar on the shelf or a raw thing in the satchel.
        # Herbalism keeps those in two fields and spends them separately; the four newer
        # crafts put everything in `consumes`, so asking only the shelf spent nothing at
        # all — a forge chain could be attempted forever on the same four bars of steel.
        took = pc.take_stock(sid, n)
        if not took:
            took = pc.spend(sid, n)
        if took:
            spent[sid] = took

    for iid, n in benches.result_field(result, "consumes_raw", {}).items():
        took = pc.spend(iid, n)
        if took:
            spent[iid] = spent.get(iid, 0) + took

    made = None
    output = benches.result_field(result, "output", None)
    if succeeded and output:
        # Every craft's output lands in the same pack. `Stock` grew the handful of
        # fields the other four shapes need — slot, wearable, how, masterwork, the
        # weapon or armour row it really is — so a forged blade and a brewed tea are
        # one kind of record on the sheet rather than five inventory panels.
        item = crafting.from_stock_dict(dict(output, craft=state["track"]))
        pc.add_stock(item, 1)
        made = item.as_dict()

    return {
        "name": result.name, "succeeded": succeeded, "roll": face,
        "chance": benches.result_field(result, "chance", 0),
        "result": result.as_dict(), "made": made,
        "spent": spent,
        # The whole check, so the bench can show the arithmetic rather than a verdict.
        "total": total, "bonus": bonus, "dc": result.dc,
        "terms": benches.result_field(result, "terms", []),
        "tell": " ".join(o.tell for o in resolution.outcomes if o.tell),
    }


@require_POST
def craft_recipes(request):
    """Keep a chain under a name, so a working recipe is worked out once."""
    body = read_body(request)
    c = campaign_mod.current()
    try:
        disc = _discipline(str(body.get("craft", "herbalism")))
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    if disc.get("moved"):
        # The table bench keeps herbalism's recipes in its own step shape
        # (/api/bench/recipe); a chain saved here would be one it has to convert.
        return _moved(disc)
    name = str(body.get("name", "")).strip()
    if not name:
        return JsonResponse({"error": "A recipe needs a name."}, status=400)
    if not body.get("ingredients"):
        return JsonResponse({"error": "A recipe needs ingredients."}, status=400)

    entry = {
        "name": name,
        "craft": str(body.get("craft", "herbalism")),
        "methods": [str(m).strip().lower() for m in body.get("methods", [])],
        "ingredients": [str(i).strip().lower() for i in body.get("ingredients", [])],
    }
    # Saving under a name that already exists replaces it. A bench where the second save
    # silently makes a duplicate is a bench nobody can correct a recipe at.
    c.recipes = [r for r in c.recipes if r["name"].lower() != name.lower()]
    c.recipes.append(entry)
    c.save()
    return JsonResponse({"recipes": c.recipes})


# --- foraging -------------------------------------------------------------------------------

@require_GET
def forage_table(request):
    """The roll table for where the party is standing, and the biomes they could be in.

    Returned as the table itself rather than only its results, because a player who can
    see the d100 spread can decide whether this ground is worth an afternoon — which is
    the whole point of knowing what biome you are in.
    """
    c = campaign_mod.current()
    disc = _discipline(request.GET.get("craft", "herbalism"))
    state = _track_state(c, disc)
    biome = biomes.canonical(request.GET.get("biome", "") or c.biome)
    ceiling = state.get("max_rank", 1)
    return JsonResponse({
        "here": c.biome,
        "biome": biome,
        "biomes": [{"id": b, "describe": d} for b, d in biomes.BIOMES.items()],
        "table": foraging.table_for(biome, ceiling).as_dict(),
        "attempts": foraging.attempts_for(state.get("level", 1)),
        # Why the button is dead, sent with the table rather than discovered by pressing
        # it. The bench greys chains it cannot make and says why; foraging offered no
        # reason at all until the request came back refused.
        "busy": _forage_blocked(c),
        "track": state,
    })


def _forage_blocked(c) -> str:
    """The engine's own reason, asked before the attempt rather than after.

    Read off `Engine._too_busy_to_forage` rather than re-derived here, because two copies
    of a rule is how a corrected rule goes on shipping from the copy nobody looked at.
    """
    pc = c.scene.pc()
    if pc is None:
        return ""
    return c.engine()._too_busy_to_forage(pc)


def _narrate(messages, cfg, *, as_json=False, num_predict=220, schema=None):
    """One short narration call, or None. The craft action must survive the model being
    down — a forage that cannot happen because Ollama is not running would be the bench
    breaking immersion in the opposite direction.

    `think=False` is load-bearing, as on every prose call in `gm/agent.py`. This was the
    one chat call in the app without it (playtest 2026-09-30, item 8): on the owner's
    thinking model a 140-token opening spent 140 of 140 tokens thinking and came back
    with empty content, and 4 of 4 excursion narrations fell to their template floors.
    """
    from gm import client as gm_client

    try:
        reply = gm_client.chat(
            messages, cfg["model"], host=cfg["host"], as_json=as_json or schema is not None,
            temperature=0.85, timeout=90, num_predict=num_predict,
            provider=cfg.get("provider", "ollama"), api_key=cfg.get("api_key", ""),
            schema=schema, think=False)
        # `chat` returns a Reply, not a string — the first live forage wrote
        # "Reply(text='You push aside…', model='llama3.1:8b')" into the book verbatim.
        return reply.json() if (as_json or schema is not None) else reply.text
    except Exception:
        return None


def _forage_scene(c):
    """Where and when, for the narrator's benefit — in words, never a clock face.

    The place is where the party STANDS (`Engine.here`), not the settlement: the opening
    floor said "work away from Ledgerwarren" while the party stood at the outskirts
    (playtest 2026-09-30, item 8). And the time is the part of the day: "day 1, 17 hours
    in" was a number handed to a narrator that must never write one.
    """
    from rules import residency

    here = c.engine().here()
    town = c.location.name if c.location else ""
    place = (getattr(here, "name", "") or town or "the open country")
    return place, residency.day_part(c.scene.clock_minutes)


def _town(c) -> str:
    """The settlement's name, for "head back toward" — the place you came out of."""
    return c.location.name if getattr(c, "location", None) else ""


# --- the encounter met while foraging ---------------------------------------------------
#
# The owner's ask (playtest 2026-09-30, item 8): "an encounter found while foraging gets a
# model call that sets the whole scene", with an example — a brass construct perched over
# the thicket you were heading for, its glass eye whirring and focusing on you, holding its
# ground without attacking or fleeing. What it printed instead was the engine's tell
# template, "a Clockwork Spy has the ground you wanted, and has not moved off it", which
# the owner could not parse.
#
# The shape is the one every fix that held used here: the engine decides (the creature,
# where it is, its stance as a tell), code detects that there IS a creature, one call
# writes the scene from those facts only, and code checks the result for the three things
# the scene must not do — name somebody who does not exist, have the creature attack or
# leave (the engine says it does neither), or state a number. A defect earns one
# targeted repair naming it; a second failure takes the floor, which is written from the
# same facts.

_SCENE_SCHEMA = {"type": "object", "properties": {"narration": {"type": "string"}},
                 "required": ["narration"]}

# What the creature must not be the subject of: a blow (no blow has been rolled) or a
# departure (the engine has it holding its ground). An adverb may sit between ("it
# suddenly lunges"); a negation may not, so "it does not attack" passes as it should.
#
# Three families. A blow that LANDS is never the scene's to write, whatever the creature
# is doing: no attack has been rolled. Going for you (a lunge, a charge) is refused only
# of a creature holding its ground; one the rules sent at you may close. Leaving is
# refused of both — the engine has it here.
_LANDS = (r"strik(?:e|es|ing)|struck|bit(?:e|es|ing)|claw(?:s|ed|ing)?|slam(?:s|med|ming)?|"
          r"sting(?:s|ing)?|hit(?:s|ting)?|swip(?:e|es|ed)|rak(?:e|es|ed)")
_GOES_FOR = (r"attack(?:s|ed|ing)?|lung(?:e|es|ed|ing)|charg(?:e|es|ed|ing)|"
             r"pounc(?:e|es|ed|ing)|spr(?:ing|ings|ang) at|leap(?:s|t|ed)? at|"
             r"comes? (?:at|for)|rush(?:es|ed)? (?:at|toward|towards)")
_LEAVES = (r"fle(?:e|es|d|eing)|bolt(?:s|ed)?|retreat(?:s|ed|ing)?|withdr(?:aw|aws|ew)|"
           r"(?:runs?|ran|scurr(?:y|ies|ied)|darts?|darted|scuttles?|scuttled|backs?|"
           r"backed|flies|flew|slips?|slipped) (?:off|away|back)|vanish(?:es|ed)?|"
           r"disappear(?:s|ed)?|takes? (?:flight|wing)|leav(?:e|es|ing)")
_NUMBER_WORDS = (r"\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                 r"twenty|thirty|forty|fifty|hundred|dozen)\b")


def _creature_words(name: str, row: dict) -> list[str]:
    """Every way the prose can name the creature as a sentence subject."""
    words = {name.lower(), "it", "the creature", "the thing", "the beast"}
    parts = name.lower().split()
    if parts:
        words.add(parts[-1])
    for key in ("creature_type", "subtype"):
        v = str(row.get(key) or "").strip().lower()
        if v:
            words.add(v)
    return sorted(words, key=len, reverse=True)


def scene_defects(text: str, *, name: str, row: dict, known: set[str],
                  holding: bool = True) -> list[str]:
    """What is wrong with an encounter scene, each as a fix a repair call can act on.

    Detected in code, never asked of the model: an invented name, the creature as the
    subject of a blow or a departure, a number. Empty when the scene may stand.
    """
    import re

    from gm import narration as narration_mod

    out: list[str] = []
    text = str(text or "")
    if not text.strip():
        return ["the scene is empty"]
    for bad in narration_mod.invented_names(text, known):
        out.append(f"\"{bad}\" names somebody or somewhere that does not exist here: "
                   f"remove the name")
    subject = "|".join(re.escape(w) for w in _creature_words(name, row))
    verbs = "|".join((_LANDS, _GOES_FOR, _LEAVES) if holding else (_LANDS, _LEAVES))
    rx = re.compile(rf"\b(?:the\s+)?(?:{subject})\s+(?:\w+ly\s+)?(?:{verbs})\b", re.I)
    for m in rx.finditer(text):
        out.append(
            f"\"{m.group(0)}\": the {name} neither attacks nor leaves — it holds its "
            f"ground. Rewrite that so it stays where it is" if holding else
            f"\"{m.group(0)}\": no blow has landed and the {name} is not leaving. "
            f"Rewrite that so it is still coming, nothing more")
    for m in re.finditer(rf"\d+|{_NUMBER_WORDS}", text, re.I):
        out.append(f"\"{m.group(0)}\" is a number: say it without one")
    return out


def _senses_words(row: dict) -> str:
    """The creature's senses, with every number taken out: "darkvision 60 ft.,
    low-light vision; Perception +0" is "darkvision, low-light vision"."""
    import re

    raw = str(row.get("senses") or "").split(";")[0]
    parts = [re.sub(r"[\d.+\-]+\s*(?:ft\.?|feet)?", "", p).strip(" .,")
             for p in raw.split(",")]
    return ", ".join(p for p in parts if p and not p.lower().startswith("perception"))


def _moves_words(row: dict) -> str:
    """How it gets about, in words: the speed's kinds, never its feet."""
    from rules import bestiary

    try:
        kinds = [k for k, v in bestiary.speeds(row).items() if v]
    except Exception:
        kinds = []
    said = {"land": "on foot", "fly": "flies", "swim": "swims", "climb": "climbs",
            "burrow": "burrows"}
    return ", ".join(said.get(k, k) for k in kinds) or "on foot"


def encounter_facts(c, enc: dict, haul: list[dict], place: str, when: str) -> dict:
    """Everything the scene call may use, from the engine and the world, and nothing
    else. Also what the floor is written from, so the two cannot disagree."""
    from rules import bestiary, biomes, geography

    who = c.scene.actors.get(str(enc.get("ref") or ""))
    name = (who.name if who is not None else "") or str(enc.get("creature") or "")
    row = {}
    template = getattr(who, "from_template", "") if who is not None else ""
    for key in (template, name):
        if key:
            row = bestiary.details(str(key).lower().replace(" ", "-")) or {}
            if row:
                break
    land_near: list[str] = []
    try:
        if c.location is not None:
            land = geography.land_around(c.world, c.location)
            land_near = list(land.near)
    except Exception:
        land_near = []
    ground = biomes.describe(c.biome) if c.biome else ""
    return {
        "name": name, "row": row,
        "size": str(row.get("size") or "").lower(),
        "kind": " ".join(x for x in (str(row.get("subtype") or "").lower(),
                                     str(row.get("creature_type") or "").lower()) if x),
        "organization": str(row.get("organization") or "").lower(),
        "senses": _senses_words(row),
        "moves": _moves_words(row),
        "place": place, "town": _town(c), "when": when,
        "ground": ground, "near": land_near,
        "carried": [h["name"] for h in haul],
        "spot": str(enc.get("spot") or "patch"),
        "stance": str(enc.get("stance") or ""),
        "holding": bool(who is not None and who.has_state("state.holding-ground")),
    }


def floor_scene(f: dict) -> str:
    """The scene when the model is down or keeps getting it wrong: the same facts,
    plainly. Better than the line it replaces because it says WHERE the creature is and
    WHAT it is doing about you, which "has the ground you wanted" never did."""
    a = "an" if f["name"][:1].lower() in "aeiou" else "a"
    looks = " ".join(x for x in (f["size"], f["kind"]) if x)
    looks = (f" — {'an' if looks[:1].lower() in 'aeiou' else 'a'} {looks}"
             if looks else "")
    alone = " and alone" if f["organization"] == "solitary" else ""
    carried = (f"With the {', '.join(n.lower() for n in f['carried'][:2])} heavy in your "
               f"satchel, you" if f["carried"] else "You")
    if not f["holding"]:
        return (f"{carried} straighten up — it is {f['when']} now — and see it: "
                f"{a} {f['name']}{looks}{alone}, and it is coming for you.")
    return (f"{carried} straighten up — it is {f['when']} now — and look toward the "
            f"{f['spot']} you were making for. {a.title()} {f['name']} is there before "
            f"you{looks}{alone}, set squarely between you and the {f['spot']}. It does "
            f"not come at you, and it does not give way.")


def _scene_messages(f: dict) -> list[dict]:
    """The one scene call. Facts first, then one demonstration of the register about a
    DIFFERENT creature on different ground, so the shape it teaches is "light, ground,
    the creature as it looks, what it is doing" and not a construct's whirring eye — the
    owner's own example would have been copied onto every frog and wolf after it."""
    lines = [f"Where: {f['place']}" + (f", just outside {f['town']}"
                                        if f["town"] and f["town"] != f["place"] else "")
             + "."]
    if f["ground"]:
        lines.append(f"Underfoot: {f['ground'].lower()}.")
    if f["near"]:
        lines.append(f"The land close by: {', '.join(f['near'])}.")
    lines.append(f"Time of day: {f['when']}.")
    if f["carried"]:
        lines.append(f"Already in the satchel from the hours of work: "
                     f"{', '.join(f['carried'])}.")
    lines.append(f"Where they were heading next: a {f['spot']} of the same.")
    body = ", ".join(x for x in (f["size"], f["kind"]) if x)
    lines.append(f"What is there: a {f['name']}" + (f" ({body})" if body else "")
                 + (f", {f['organization']}" if f["organization"] else "") + ".")
    if f["senses"]:
        lines.append(f"Its senses: {f['senses']}.")
    lines.append(f"How it moves: {f['moves']}.")
    lines.append(f"What it is doing (the rules decided this): {f['stance']}")
    return [
        {"role": "system", "content": (
            "You narrate a solo Pathfinder game. Answer as JSON: {\"narration\": \"...\"}. "
            "Three to five sentences, second person, present tense: the moment the "
            "character looks up from the work and sees what is there. Use only the facts "
            "given; invent no names, no people and no places. No numbers. Do not decide "
            "anything the character does, and do not end with a question.\n\n"
            "The register, shown with a different creature on different ground:\n"
            "The reeds thin where the bank drops to black water, and the light over the "
            "marsh has gone the colour of weak tea. On the hummock beyond the pool you "
            "were wading toward squats a giant frog, mottled and slick, its throat "
            "pulsing slowly, one gold eye turned on you. It does not croak and it does "
            "not move; it simply keeps the hummock, and the cress growing round it, "
            "between itself and you.")},
        {"role": "user", "content": "\n".join(lines)},
    ]


def _repair_messages(f: dict, text: str, defects: list[str]) -> list[dict]:
    """The targeted repair: the passage, and only what was found wrong with it."""
    return [
        {"role": "system", "content": (
            "You correct a passage of game narration. Answer as JSON: "
            "{\"narration\": \"...\"}. Change only what each numbered problem names; "
            "keep every other sentence as it is.")},
        {"role": "user", "content": (
            f"The passage:\n{text}\n\nProblems:\n"
            + "\n".join(f"{i}. {d}." for i, d in enumerate(defects, 1)))},
    ]


def _known_for_scene(c, f: dict) -> set[str]:
    """Every name the scene may use: the GM's own list (the world, the room, the
    satchel) plus this creature and this ground."""
    known: set[str] = set()
    try:
        from gm.agent import GMAgent

        known |= GMAgent(c.world, c.engine())._known_names()
    except Exception:
        pass
    known |= {f["name"], f["place"], f["town"], *f["carried"]}
    pc = c.scene.pc()
    if pc is not None:
        known.add(pc.name)
    return {k for k in known if k}


def encounter_scene(c, enc: dict, haul: list[dict], place: str, when: str,
                    cfg) -> tuple[str, list[str]]:
    """The scene, and what was repaired or why the floor was taken (for the turn log)."""
    import re

    f = encounter_facts(c, enc, haul, place, when)
    if not f["name"]:
        return "", ["no creature to set"]
    known = _known_for_scene(c, f)
    notes: list[str] = []

    def ask(messages) -> str:
        got = _narrate(messages, cfg, schema=_SCENE_SCHEMA, num_predict=420)
        text = str((got or {}).get("narration") or "").strip() if isinstance(got, dict) \
            else ""
        # The question is the table's to ask, once, after the scene ("What do you do?").
        return re.sub(r"\s*[^.!?]*\?\s*$", "", text).strip()

    def check(text: str) -> list[str]:
        return scene_defects(text, name=f["name"], row=f["row"], known=known,
                             holding=f["holding"])

    text = ask(_scene_messages(f))
    defects = check(text)
    if defects and text:
        notes.append("repaired: " + "; ".join(defects))
        text = ask(_repair_messages(f, text, defects))
        defects = check(text)
    if defects:
        notes.append("floor: " + "; ".join(defects))
        text = floor_scene(f)
    return text, notes


def _fallen(c) -> list[dict]:
    """Creatures in the scene that can be skinned or salvaged. The dead only."""
    return [{"ref": r, "name": a.name}
            for r, a in c.scene.actors.items()
            if not a.is_pc and a.is_down]


def _at_market(c) -> bool:
    """Whether there is anybody here to buy from.

    Read off the world's own entity kind rather than a list of place names: World Bible
    says what a settlement is, and a second opinion here would disagree with it the
    first time somebody wrote a new kind of town.

    The ground has to agree. `travel` moves `scene.biome` and never touches
    `location_id` — it does not know where you went, only what you are standing on — so
    walking out of Zhilvarnia into open grassland left the scene still pointing at a
    CITY. Measured in play: out in empty scrub, miles from the walls, all five market
    cards were offered, and an ironmonger sold Iron to a character with nothing around
    them but grass.

    Requiring urban ground as well is deliberately the fail-safe direction. A coastal
    fishing village whose own biome is `coast` would be refused here, which costs the
    player a `travel` to say they have gone into the streets; the other way round the
    world contains a stall wherever anybody happens to be standing.
    """
    loc = getattr(c, "location", None)
    kind = str(getattr(loc, "kind", "") or "").upper()
    if kind not in ("CITY", "TOWN", "VILLAGE", "SETTLEMENT"):
        return False
    return str(getattr(c, "biome", "") or "").strip().lower() == "urban"


def _excursions(c) -> list[dict]:
    """Every way of obtaining material, and whether it can be done standing here.

    One list for the play page's craft-action button — the hub for "mining, skinning,
    etc... all the actions that obtain world class materials/reagents". A craft the
    character has no levels in is still listed: an excursion you cannot run yet is a
    reason to take up the trade, and one that is simply absent is not.
    """
    pc = c.scene.pc()
    fallen = _fallen(c)
    out = []
    for spec in benches.acquisitions():
        entry = dict(spec)
        needs = str(spec.get("requires") or "")
        why = ""
        if needs == "biome" and not c.biome:
            why = "The ground here has not been named yet."
        elif needs == "biome" and _forage_blocked(c):
            why = _forage_blocked(c)
        elif needs != "biome" and c.scene.in_encounter:
            why = "You are in a fight. This can wait until it is over."
        elif needs in ("creature", "carcass") and not fallen:
            why = "Nothing has fallen here to work on."
        elif needs == "market" and not _at_market(c):
            why = "There is nobody here selling."
        if pc is not None:
            progress = pc.track(spec["track"])
            entry["level"] = progress.level
        entry["available"] = not why
        entry["why"] = why
        entry["targets"] = fallen if needs in ("creature", "carcass") else []
        out.append(entry)
    return out


@require_GET
def craft_actions(request):
    """What the craft-action button offers, here, now."""
    c = campaign_mod.current()
    return JsonResponse({
        "actions": _excursions(c),
        "biome": c.biome,
        "biome_describe": biomes.describe(c.biome),
        # The biome picker moved here from the crafting page, where it was a debug
        # control on a bench that has no business claiming to be somewhere else. You
        # forage where you stand; this is the one place that says where that is.
        "biomes": list(biomes.EVERYWHERE),
        "blocked": _forage_blocked(c),
    })


def _price_cp(material) -> int:
    """A material's shelf price in copper. Zero means it is not for sale.

    Every bench's Material carries `price_gp`; the ones that leave it None are things
    the world does not put on a counter, and those are excluded from a market rather
    than handed over for free.
    """
    try:
        return max(0, round(float(getattr(material, "price_gp", None)) * 100))
    except (TypeError, ValueError):
        return 0


def _price_line(material) -> str:
    return goods.purse_line(goods.coins_for(_price_cp(material)), goods.coinage())


def _sells_its_own_trade(track_id: str, pool: list) -> list:
    """This stall's own goods, out of everything its module can see.

    The four material modules read `content/materials` as one shared folder, and only
    the alchemist returns the whole of it — its `obtainable` says so on purpose, "a
    market sells what the market sells". That was invisible while every stall carried
    every priced material; with shelves it is the difference between an apothecary and
    a car boot sale. Measured in play: "Buy reagents" sold a Brass Guard, a Steel
    Crossguard, Quenching Oil and a Warding Essence, and four of the six things bought
    could not be used at the alchemy bench at all.

    So a stall draws its shelf from the catalogue that belongs to its own craft. Nothing
    becomes unobtainable — a character carries all five tracks, and the smith's stall
    sells the smith's stock — it just has to be bought from the right counter.

    A homebrew material belongs to no shipped file and is offered at every stall, which
    errs toward reachable rather than lost. That is the same call `_craft_materials`
    makes for the bench shelves.
    """
    import json as json_mod
    from pathlib import Path

    from django.conf import settings

    shipped: dict[str, set[str]] = {}
    for p in (Path(settings.BASE_DIR) / "content" / "materials").glob("*.json"):
        try:
            data = json_mod.loads(p.read_text(encoding="utf-8"))
        except Exception:                              # pragma: no cover - guard
            continue
        shipped[p.stem] = {str(m.get("id", "")).strip().lower()
                           for m in data.get("materials", [])}
    own = shipped.get(f"{track_id}-materials", set())
    if not own:
        return pool
    elsewhere = set().union(*(v for k, v in shipped.items()
                              if k != f"{track_id}-materials")) or set()
    kept = [m for m in pool
            if str(getattr(m, "id", "")).lower() in own
            or str(getattr(m, "id", "")).lower() not in elsewhere]
    return kept or pool


@require_POST
def craft_excursion(request):
    """Go out and come back with material — mining, skinning, gathering, buying.

    The generic half of the hub. Foraging keeps its own endpoint because it has a
    bespoke hourly Survival loop in the engine that predates this; everything else runs
    the same shape: one check the player rolls, a haul drawn from what this craft says
    is obtainable *here*, and the hours it cost. The materials land in the satchel the
    benches already read, so a prospected ore is at the forge the moment it is dug.
    """
    body = read_body(request)
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)

    key = str(body.get("action", "")).strip().lower()
    spec = next((e for e in _excursions(c) if e["key"] == key), None)
    if spec is None:
        return JsonResponse({"error": f"{key!r} is not something you can go and do"},
                            status=404)
    if not spec["available"]:
        return JsonResponse({"error": spec["why"]}, status=409)
    # Wandering off and working where you stand are different problems. Prospecting or
    # gathering means hours out of the scene, so it takes the same test foraging does;
    # skinning happens over the carcass at your feet and buying happens at the stall in
    # front of you, and neither is impossible because somebody is talking to you. A
    # fight stops all of it either way.
    if str(spec.get("requires")) == "biome":
        blocked = _forage_blocked(c)
        if blocked:
            return JsonResponse({"error": blocked}, status=409)
    elif c.scene.in_encounter:
        return JsonResponse(
            {"error": "You are in a fight. This can wait until it is over."},
            status=409)

    creature = str(body.get("creature", "")).strip()
    if spec.get("requires") in ("creature", "carcass") and not creature:
        creature = (spec["targets"][0]["name"] if spec["targets"] else "")

    track = spec["track"]
    level = pc.track(track).level
    found = benches.obtainable(track, str(spec.get("obtain") or ""),
                               biome=c.biome or None, creature=creature or None)
    ceiling = worldclass.tier_rank(worldclass.get(track).at(level).max_tier)
    buying = str(spec.get("obtain") or "") == "bought"
    day = market.day_of(c.scene.clock_minutes)
    place = str(c.scene.location_id or c.biome or "nowhere")

    if buying:
        # A market is not a field, and a shop is not a catalogue.
        #
        # Every material carries `price_gp` and the alchemist's own blurb says "Price is
        # in gp on each material", and nothing here read either: buying ran the identical
        # path as prospecting, so a stallholder in Zhilvarnia carried all 397 priced
        # materials at once and handed over Steel, a Crossguard and Tin to an empty purse.
        #
        # The shelf is drawn from everything the stall could conceivably carry — **before**
        # the level gate, deliberately. What a shop stocks is a fact about the shop, not
        # about who walked in; a first-day smith should be able to see the good steel on
        # the rack and be told it is beyond them, rather than have the world quietly
        # contain nothing but nails.
        priced = [m for m in found if _price_cp(m) > 0]
        priced = _sells_its_own_trade(track, priced)
        shelf = market.stock(priced, place=place, stall=key, day=day)
        on_shelf = market.remaining(shelf, c.scene.market_taken, place, key, day)
        if not on_shelf:
            return JsonResponse({"error": (
                "The stall is bare. What they had today has been bought — come back "
                "tomorrow." if shelf else
                "Nothing on this stall is priced for sale.")}, status=409)

        within = [m for m in on_shelf if getattr(m, "rank", 1) <= ceiling]
        if not within:
            best = min(on_shelf, key=lambda m: getattr(m, "rank", 1))
            return JsonResponse({"error": (
                f"Nothing on the shelf today is within a {track} of level {level}. "
                f"The plainest thing they have is {best.name}.")}, status=409)

        purse_cp = goods.in_copper(pc.purse)
        cheapest = min(within, key=_price_cp)
        if purse_cp < _price_cp(cheapest):
            coins = goods.coinage()
            return JsonResponse({"error": (
                f"You cannot afford anything on the shelf today. The cheapest you could "
                f"use is {cheapest.name} at {_price_line(cheapest)}, and you have "
                f"{goods.purse_line(pc.purse, coins)}.")}, status=409)
    else:
        within = [m for m in found if getattr(m, "rank", 1) <= ceiling]
        if not within:
            return JsonResponse(
                {"error": f"Nothing here is within a {track} of level {level}."
                          if found else "There is nothing of that kind to be had here."},
                status=409)

    # An excursion is a day's work at most; foraging is the one that can run for days,
    # and it clamps to 48. The hours slider is shared between them and goes to 48, so
    # asking for a 48-hour market run quietly became a 12-hour one. Still capped — a
    # two-day dig is a foraging trip, not a visit to a stall — but the trim is said out
    # loud rather than left for the player to notice in the clock.
    asked = read_int(body, "hours", 1, lo=1)
    hours = min(12, asked)
    trimmed = asked > hours
    spent_cp = 0
    unaffordable = 0
    engine = c.engine()
    roll = engine.dice.d20(label=spec.get("label", "Excursion"), visibility="player")
    face = roll.faces[0]
    # The same arithmetic the bench uses for a craft check, so going out for material
    # and working it are scored on one formula rather than two.
    bonus = benches.module_for(track).check_bonus(pc, level)         if hasattr(benches.module_for(track), "check_bonus") else level
    dc = 10 + max(0, ceiling - 1) * 3
    total = face + bonus
    ok = face != 1 and (face == 20 or total >= dc)

    haul: list[dict] = []
    if ok:
        # Better rolls reach further up the shelf, and more of it. The margin is the
        # only thing that decides quality, so a lucky prospect is a real find rather
        # than more of the same gravel.
        margin = total - dc
        reach = min(ceiling, 1 + margin // 5)
        pool = [m for m in within if getattr(m, "rank", 1) <= reach] or within
        take = min(len(pool), 1 + hours // 2 + margin // 8)
        picks = [pool[(face * (i + 3)) % len(pool)] for i in range(max(1, take))]
        # Paid for one at a time, in the order they were reached for, and the moment the
        # purse cannot cover the next one the shopping stops. Trimming rather than
        # refusing outright: a good roll that finds more than you can carry money for
        # should still sell you what you *can* afford, and say what was left behind.
        if buying:
            # Off a shelf, not out of a bin. The modular index above can reach for the
            # same entry twice, and a stall that holds one amethyst cannot sell two.
            seen, once = set(), []
            for m in picks:
                if m.id in seen:
                    continue
                seen.add(m.id)
                once.append(m)
            afforded, left = [], 0
            for m in once:
                purse, enough = goods.spend(pc.purse, _price_cp(m))
                if not enough:
                    left += 1
                    continue
                pc.purse = purse
                spent_cp += _price_cp(m)
                market.mark_sold(c.scene.market_taken, m.id, place, key, day)
                afforded.append(m)
            unaffordable = left
            picks = afforded
        counted: dict[str, int] = {}
        for m in picks:
            counted[m.id] = counted.get(m.id, 0) + 1
        if not buying:
            # Things gathered come in batches, the way foraging's do — "craft actions
            # are too uneven, everything other than foraging returns only 1 item."
            # Bought goods stay one-per-coin (a shelf holds what it holds); dug ore
            # and skinned hide scale with how far the check beat the ground, floors
            # at what the roll already earned.
            batch = max(1, 1 + margin // 5)
            counted = {mid: n * batch for mid, n in counted.items()}
        for mid, n in counted.items():
            pc.carry(mid, n)
        names = {m.id: m.name for m in pool}
        haul = [{"id": mid, "name": names.get(mid, mid), "count": n}
                for mid, n in sorted(counted.items())]

    # Through the one door, and after `market.day_of` was read at the top of this view:
    # advancing first would roll the shelf over inside a twelve-hour buying run.
    c.scene.advance(hours * 60)
    tally = " · ".join(f"{h['name']} ×{h['count']}" for h in haul) or "Nothing."
    verb = spec.get("verb") or spec.get("label", "working")
    # What it cost and what was left on the counter, said in the same line as the haul.
    # A purse that quietly empties is the version of this a player cannot check.
    coins = goods.coinage()
    paid = ""
    if buying and spent_cp:
        paid = (f" Paid {goods.purse_line(goods.coins_for(spent_cp), coins)}"
                f", leaving {goods.purse_line(pc.purse, coins)}.")
        if unaffordable:
            paid += (f" {unaffordable} more "
                     f"{'was' if unaffordable == 1 else 'were'} left on the counter.")
    capped = (f" (You meant to spend {asked}; this is a day's errand at most, "
              f"so it took {hours}.)" if trimmed else "")
    line = (f"{pc.name} spends {hours} hour{'s' if hours != 1 else ''} "
            f"{verb}{' the ' + creature if creature else ''}. "
            f"{'Found: ' + tally if haul else 'Nothing worth carrying.'}{paid}{capped}")
    c.transcript.append({"who": "gm", "kind": "consequence", "text": line})
    c.save()
    return JsonResponse({
        "action": key, "label": spec.get("label", ""), "found": haul,
        "roll": face, "bonus": bonus, "dc": dc, "total": total, "succeeded": ok,
        "spent_cp": spent_cp, "purse": dict(pc.purse),
        "hours": hours, "tell": line, "clock_minutes": c.scene.clock_minutes,
    })


@require_POST
def craft_action(request):
    """A crafting-related excursion, narrated into the scene it happens in.

    Foraging lived only on the bench page, where it was a button and a table: no
    narration, no sense of time passing, no way back into the fiction. "crafting related
    actions like foraging or mining or skinning don't break immersion" — so the run is
    told like a turn: the narrator opens it, the die lands where everyone can see it, the
    finding is told before the tally, and it ends the way every GM turn ends — what do
    you do, and three ways to answer.

    The engine still decides everything. Both narration calls are decoration around the
    same `forage` op the bench uses, and either call failing falls back to plain prose
    built from the facts — a model being down costs colour, never the herbs.
    """
    body = read_body(request)
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)

    face = body.get("face")
    if face is not None:
        # The second half of the round trip: the excursion suspended on the player's
        # Survival check, and this is the face coming back. The hours are read off the
        # engine's own frozen intent rather than trusted from the client twice.
        if not c.scene.awaiting:
            return JsonResponse({"error": "nothing is waiting on a roll"}, status=409)
        # Same door discipline as the bench: only the roll this endpoint opened.
        if c.scene.awaiting.get("door") != "excursion":
            return JsonResponse({"error": (
                "The pending roll is not the excursion's to answer — the table's "
                "dice popup has it.")}, status=409)
        pending = c.scene.pending_intents[0] if c.scene.pending_intents else {}
        hours = max(1, int((pending.get("params") or {}).get("hours", 1) or 1))
        if face == "auto":
            from rules.dice import Dice

            face = Dice().roll("1d20").raw
        try:
            resolution = c.engine().resume(int(face))
        except (ValueError, BadDice) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        opening = next((t["text"] for t in reversed(c.transcript)
                        if t.get("who") == "gm"), "")
        place, when = _forage_scene(c)
        from play import modelcfg

        cfg = modelcfg.for_role("narrator")
    else:
        action = str(body.get("action", "forage")).strip().lower()
        if action != "forage":
            return JsonResponse(
                {"error": f"{action!r} is not a craft action yet — foraging only."},
                status=400)
        if c.scene.awaiting:
            return JsonResponse({"error": "There is a roll waiting on you."},
                                status=409)

        hours = read_int(body, "hours", 1, lo=1, hi=48)
        place, when = _forage_scene(c)
        from play import modelcfg

        cfg = modelcfg.for_role("narrator")

        # 1. The setting out. Written to the transcript before the roll, because that is
        # the order it happens in at a table.
        opening = _narrate([
            {"role": "system",
             "content": "You narrate a solo Pathfinder game. Two or three sentences, "
                         "second person, present tense. Never invent named people or "
                         "places. Never ask a question. Stop before anything is found."},
            {"role": "user",
             "content": f"{pc.name} sets out to forage for herbs. Terrain: {c.biome}. "
                         f"At {place}. Time of day: {when}. They mean to spend "
                         f"{'an hour' if hours == 1 else 'some hours'} searching. "
                         f"Narrate them beginning the search."},
        ], cfg, num_predict=160)
        if not opening or not str(opening).strip():
            # Where they STAND: "work away from Ledgerwarren" was printed while the party
            # stood at the outskirts (item 8) — the settlement is not the place.
            opening = (f"You shoulder your satchel at {place} and start on the "
                       f"{c.biome} ground, eyes down. It is {when}, and "
                       f"{'an hour' if hours == 1 else 'hours'} of searching lie "
                       f"ahead.")
        opening = str(opening).strip()
        c.transcript.append({"who": "gm", "text": opening})

        # 2. The dice decide. Same op as the bench, and the same suspend: the Survival
        # check is the player's own, herbalism bonus in the breakdown. The opening stays
        # in the book across the suspend — the character has set out; the roll is what
        # happens next.
        try:
            resolution = c.engine().run(c.engine().validate([{
                "op": "forage", "actor": "pc",
                "because": f"{hours} hour{'s' if hours != 1 else ''} spent looking",
                "params": {"hours": hours},
            }]))
        except IntentError as exc:
            # The opening already happened in the fiction; take it back out rather than
            # narrating a search the engine refused.
            c.transcript.pop()
            return JsonResponse({"error": str(exc)}, status=400)
        if resolution.awaiting:
            c.scene.awaiting["door"] = "excursion"
            c.save()
            return JsonResponse({"opening": opening, "roll": resolution.awaiting,
                                 "hours": hours})

    tell = " ".join(o.tell for o in resolution.outcomes if o.tell)
    effects = [e for o in resolution.outcomes for e in o.effects
               if e.get("kind") == "forage"]
    found: dict[str, int] = {}
    rolls: list[int] = []
    checks: list[dict] = []
    for e in effects:
        for iid, n in (e.get("found") or {}).items():
            found[iid] = found.get(iid, 0) + n
        rolls.extend(int(r["roll"]) for r in e.get("rolls", []) if r.get("roll"))
        # The d100 picks only exist for hours whose Survival check earned any. A barren
        # day rolled real dice too — the checks themselves — and a die the player was
        # promised must land on *something* true, so the checks travel as the fallback.
        checks.extend({"roll": int(h["roll"]), "dc": int(h.get("dc", 0))}
                      for h in e.get("hourly", []) if h.get("roll") is not None)
    names = {i.id: i.name for i in ingredients.all_ingredients().values()}
    haul = [{"id": iid, "name": names.get(iid, iid), "count": n}
            for iid, n in sorted(found.items())]

    # Where and when the excursion ENDS: the hours have passed.
    place, when = _forage_scene(c)
    # The encounter, detected in code off the engine's own record — never inferred from
    # the tell's wording. Only a creature the engine actually put here earns a scene.
    enc = next((e for o in resolution.outcomes for e in (o.effects or [])
                if e.get("kind") == "gathering" and e.get("ref")
                and e.get("encounter") in ("creature", "guarded")
                and e.get("ref") in c.scene.actors), None)

    # 3. The finding, told before the tally, ending in the question and three answers.
    # The closing prompt used to know nothing of the encounter, and the tell glued on
    # after it said the creature "has the ground you wanted" — under a haul already in
    # the satchel (item 8). The engine rolls the encounter AFTER the haul is carried, so
    # the order the fiction is told in is the same: the hours of work, then making for
    # one last patch, where the creature is. The closing stops at the walk; the scene
    # call below sets what is there.
    listed = ", ".join(f"{h['count']}x {h['name']}" for h in haul) or "nothing"
    if enc is not None:
        heading = (f" When the work is done they make for one last {enc.get('spot') or 'patch'} "
                   f"— end the narration as they head for it, before they see what is "
                   f"there. A {enc.get('creature')} is there; the suggestions are three "
                   f"things to do about it.")
    else:
        heading = ""
    closing_json = _narrate([
        {"role": "system",
         "content": "You narrate a solo Pathfinder game. Answer as JSON: "
                     '{"narration": "...", "suggestions": ["...", "...", "..."]}. '
                     "The narration is two or three sentences, second person, of the "
                     "character finding (or failing to find) exactly what is listed — "
                     "name only things from the list, invent nothing else, no numbers. "
                     "The suggestions are three short next actions a player might take, "
                     "each under eight words, imperative."},
        {"role": "user",
         "content": f"{pc.name} spent {'an hour' if hours == 1 else 'some hours'} "
                     f"foraging the {c.biome} at {place} and found: {listed}.{heading} "
                     f"Narrate the finding, then suggest three next actions."},
    ], cfg, as_json=True, num_predict=300)

    closing, suggestions = "", []
    if isinstance(closing_json, dict):
        closing = str(closing_json.get("narration") or "").strip()
        raw = closing_json.get("suggestions")
        if isinstance(raw, list):
            suggestions = [str(s).strip() for s in raw if str(s).strip()][:3]
        # Checked, not trusted: a narration that names a herb the ground did not give
        # is the GM inventing loot. Grounding is the same rule the main loop enforces.
        said = closing.lower()
        invented = [n for n in names.values()
                    if n.lower() in said and n not in [h["name"] for h in haul]]
        if invented:
            closing = ""
    if not closing:
        closing = ("The hours pass in stooping and sifting. " if haul else
                   "The hours pass in stooping and sifting, and the ground gives "
                   "nothing back. ")
        if haul:
            # A dash before the tail: "dawnpetal, power leaf earth still on the roots"
            # read as a herb called "power leaf earth" (item 8's transcript).
            closing += ("Piece by piece the satchel takes on weight: " +
                        ", ".join(h["name"].lower() for h in haul[:4]) +
                        (" and more" if len(haul) > 4 else "") +
                        " — earth still on the roots.")
    town = _town(c) or place
    if enc is not None and len(suggestions) != 3:
        suggestions = [f"Approach the {enc.get('creature')}", "Wait and watch it",
                       f"Head back toward {town}"]
    if len(suggestions) != 3:
        suggestions = ["Keep foraging", f"Head back toward {town}",
                       "Unpack the crafting bench"]

    # No full stop of its own: the line below adds one, and "Nothing gathered.." was
    # printed on the first live forage of 2026-09-30.
    tally = " · ".join(f"{h['name']} ×{h['count']}" for h in haul) or "nothing"
    c.transcript.append({"who": "gm", "kind": "consequence",
                         "text": f"{closing}\n\nGathered: {tally}. {tell}".strip()})
    # 4. What is there, when something is: one grounded scene call, checked, with a
    # floor written from the same facts.
    scene, scene_notes = "", []
    if enc is not None:
        scene, scene_notes = encounter_scene(c, enc, haul, place, when, cfg)
        if scene:
            c.transcript.append({"who": "gm", "kind": "setup", "text": scene})
    c.transcript.append({"who": "gm", "text": "What do you do?"})
    c.suggestions = suggestions

    # 5. The excursion reaches the model's memory. It wrote only the transcript, so the
    # planner and narrator never saw either forage or the creature: measured on the
    # owner's save, history jumped from the outskirts arrival straight to "I aprouch the
    # clockwork Spy" (item 8). Written the way `pending_free` writes a thing done off
    # the spoken path — the player's act as a bracketed user line, the table's answer as
    # the assistant's — and logged as a resolution row like any other turn.
    c.history.append({"role": "user", "content": (
        f"(From the craft panel: {pc.name} forages "
        f"{'for an hour' if hours == 1 else f'for {hours} hours'} at {place}.)")})
    c.history.append({"role": "assistant", "content": " ".join(
        x for x in (opening, closing, scene) if x).strip()})
    entry = {"kind": "resolution", "door": "excursion",
             "outcomes": [o.as_dict() for o in resolution.outcomes]}
    if scene_notes:
        entry["repairs"] = scene_notes
    from play import history as history_mod

    c.turn_log.append(history_mod.stamp(c, entry))
    try:
        from play.views import _remember

        _remember(c, resolution, "")
    except Exception:  # noqa: BLE001 — the ledger is a convenience, never the turn
        import logging

        logging.getLogger("pathfindergm").exception("the excursion's ledger note failed")
    c.save()

    return JsonResponse({
        "opening": opening, "closing": closing, "tell": tell, "scene": scene,
        "found": haul, "rolls": rolls, "checks": checks, "hours": hours,
        "suggestions": suggestions,
        "clock_minutes": c.scene.clock_minutes,
    })


@require_POST
def forage_do(request):
    """Walk the ground and see what turns up. Routed through the engine's `forage` op so
    the bench and the table roll on exactly the same machinery.

    Two posts make one forage now. The first suspends on the player's own Survival check
    — the herbalism bonus sits in the prompt's breakdown, which is the first time the
    track's ground bonus has ever been *visible* — and comes back as `{"roll": ...}`.
    The second carries `face` (or "auto" for "roll it for me", the same courtesy
    `views.roll` extends) and resumes. The table's dice popup can also answer it via
    `/api/roll`; the scene holds one pending roll either way.
    """
    body = read_body(request)
    c = campaign_mod.current()

    face = body.get("face")
    if face is not None:
        if not c.scene.awaiting:
            return JsonResponse({"error": "nothing is waiting on a roll"}, status=409)
        # Only the roll this door opened. A stale bench tab must not complete a spoken
        # turn's Perception check — the face would land on somebody else's dice and the
        # rest of that turn would resolve through the wrong door's tail. The table's
        # /api/roll stays the universal answerer; these stamps only narrow the *bench*
        # and *excursion* endpoints to their own suspends.
        if c.scene.awaiting.get("door") != "bench":
            return JsonResponse({"error": (
                "The pending roll is not the bench's to answer — the table's dice "
                "popup has it.")}, status=409)
        if face == "auto":
            from rules.dice import Dice

            face = Dice().roll("1d20").raw
        try:
            resolution = c.engine().resume(int(face))
        except (ValueError, BadDice) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
    else:
        if c.scene.awaiting:
            return JsonResponse({"error": "There is a roll waiting on you."}, status=409)
        # No biome is sent. You forage where you are standing; the ground is `travel`'s
        # to change, and the bench has no business claiming to be somewhere else.
        params = {}
        # Clamped rather than trusted. The slider stops at 48, and a hand-written request
        # for a thousand hours would spend a thousand rolls before the body got a word in.
        hours = read_int(body, "hours", 1, lo=1, hi=48)
        params["hours"] = hours
        try:
            resolution = c.engine().run(c.engine().validate([{
                "op": "forage", "actor": "pc",
                "because": f"{hours} hour{'s' if hours != 1 else ''} spent looking",
                "params": params,
            }]))
        except IntentError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        if resolution.awaiting:
            c.scene.awaiting["door"] = "bench"
            c.save()
            return JsonResponse({"roll": resolution.awaiting})

    tell = " ".join(o.tell for o in resolution.outcomes if o.tell)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": tell})
    c.save()
    effects = [e for o in resolution.outcomes for e in o.effects
               if e.get("kind") == "forage"]
    pc = c.scene.pc()
    return JsonResponse({
        "tell": tell,
        "result": effects[0] if effects else {},
        "inventory": dict(pc.inventory) if pc else {},
    })


@require_POST
def travel_to(request):
    """Change the ground underfoot from the bench, without going through the GM."""
    body = read_body(request)
    c = campaign_mod.current()
    try:
        resolution = c.engine().run(c.engine().validate([{
            "op": "travel", "because": "the party moves on",
            "params": {"biome": str(body.get("biome", ""))},
        }]))
    except IntentError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    c.save()
    return JsonResponse({
        "biome": c.scene.biome,
        "describe": biomes.describe(c.scene.biome),
        "tell": " ".join(o.tell for o in resolution.outcomes if o.tell),
    })
