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
                   ingredients, worldclass)
from rules.intents import IntentError

from . import campaign as campaign_mod

# The disciplines the app knows about. Only Herbalism has rules behind it; the rest are
# declared so the page is honest about what is coming instead of hiding it. `track` is
# None where no world class exists yet, and the tab says so rather than 404ing.
DISCIPLINES = [
    {"id": "herbalism", "name": "Herbalism", "track": "herbalist",
     "blurb": "Foraging, harvesting and brewing — poultices, teas, tinctures, elixirs."},
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
        d["can_concentrate"] = item.count >= crafting.CONCENTRATE_COST
        out_of = crafting.concentrate(item)
        d["concentrates_to"] = {"name": out_of.name, "tier": out_of.tier,
                                "potency": round(out_of.potency, 2),
                                "cost": crafting.CONCENTRATE_COST}
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
    body = json.loads(request.body or "{}")
    c = campaign_mod.current()
    try:
        disc = _discipline(str(body.get("craft", "herbalism")))
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

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
    body = json.loads(request.body or "{}")
    c = campaign_mod.current()
    try:
        disc = _discipline(str(body.get("craft", "herbalism")))
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    state = _track_state(c, disc)
    if not state.get("available"):
        return JsonResponse({"error": f"{disc['name']} has no rules yet."}, status=400)

    mode = str(body.get("mode", "")).strip().lower()
    if not benches.supports(state["track"], mode):
        return JsonResponse(
            {"error": f"The {disc['name'].lower()} bench cannot take a chain yet."},
            status=409)

    wanted = max(1, min(MAX_BATCH, int(body.get("batch", 1) or 1)))
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
    body = json.loads(request.body or "{}")
    c = campaign_mod.current()
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


def _narrate(messages, cfg, *, as_json=False, num_predict=220):
    """One short narration call, or None. The craft action must survive the model being
    down — a forage that cannot happen because Ollama is not running would be the bench
    breaking immersion in the opposite direction."""
    from gm import client as gm_client

    try:
        reply = gm_client.chat(
            messages, cfg["model"], host=cfg["host"], as_json=as_json,
            temperature=0.85, timeout=90, num_predict=num_predict,
            provider=cfg.get("provider", "ollama"), api_key=cfg.get("api_key", ""))
        # `chat` returns a Reply, not a string — the first live forage wrote
        # "Reply(text='You push aside…', model='llama3.1:8b')" into the book verbatim.
        return reply.json() if as_json else reply.text
    except Exception:
        return None


def _forage_scene(c):
    """Where and when, for the narrator's benefit."""
    place = c.location.name if c.location else "the open country"
    minutes = c.scene.clock_minutes
    day, rem = minutes // 1440 + 1, minutes % 1440
    return place, f"day {day}, {rem // 60} hours in"


def _fallen(c) -> list[dict]:
    """Creatures in the scene that can be skinned or salvaged. The dead only."""
    return [{"ref": r, "name": a.name}
            for r, a in c.scene.actors.items()
            if not a.is_pc and a.hp <= 0]


def _at_market(c) -> bool:
    """Whether there is anybody here to buy from.

    Read off the world's own entity kind rather than a list of place names: World Bible
    says what a settlement is, and a second opinion here would disagree with it the
    first time somebody wrote a new kind of town.
    """
    loc = getattr(c, "location", None)
    kind = str(getattr(loc, "kind", "") or "").upper()
    return kind in ("CITY", "TOWN", "VILLAGE", "SETTLEMENT")


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


@require_POST
def craft_excursion(request):
    """Go out and come back with material — mining, skinning, gathering, buying.

    The generic half of the hub. Foraging keeps its own endpoint because it has a
    bespoke hourly Survival loop in the engine that predates this; everything else runs
    the same shape: one check the player rolls, a haul drawn from what this craft says
    is obtainable *here*, and the hours it cost. The materials land in the satchel the
    benches already read, so a prospected ore is at the forge the moment it is dug.
    """
    body = json.loads(request.body or "{}")
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
    within = [m for m in found if getattr(m, "rank", 1) <= ceiling]
    if not within:
        return JsonResponse(
            {"error": f"Nothing here is within a {track} of level {level}."
                      if found else "There is nothing of that kind to be had here."},
            status=409)

    # A market is not a field. Every material carries `price_gp` and the alchemist's own
    # blurb says "Price is in gp on each material", but nothing here ever read it: "Buy
    # from the market" handed Steel, a Steel Crossguard and Tin to a character whose
    # purse was `{}`, which made every gated excursion pointless beside it — prospecting
    # needs the right ground and hours of daylight, and buying needed a d20.
    buying = str(spec.get("obtain") or "") == "bought"
    if buying:
        stall = [m for m in within if _price_cp(m) > 0]
        if not stall:
            return JsonResponse(
                {"error": "Nothing on this stall is priced for sale."}, status=409)
        purse_cp = goods.in_copper(pc.purse)
        cheapest = min(stall, key=_price_cp)
        if purse_cp < _price_cp(cheapest):
            coins = goods.coinage()
            return JsonResponse({"error": (
                f"You cannot afford anything here. The cheapest is {cheapest.name} at "
                f"{_price_line(cheapest)}, and you have "
                f"{goods.purse_line(pc.purse, coins) or 'nothing'}.")}, status=409)
        within = stall

    hours = max(1, min(12, int(body.get("hours", 1) or 1)))
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
            afforded, left = [], 0
            for m in picks:
                purse, enough = goods.spend(pc.purse, _price_cp(m))
                if not enough:
                    left += 1
                    continue
                pc.purse = purse
                spent_cp += _price_cp(m)
                afforded.append(m)
            unaffordable = left
            picks = afforded
        counted: dict[str, int] = {}
        for m in picks:
            counted[m.id] = counted.get(m.id, 0) + 1
        for mid, n in counted.items():
            pc.carry(mid, n)
        names = {m.id: m.name for m in pool}
        haul = [{"id": mid, "name": names.get(mid, mid), "count": n}
                for mid, n in sorted(counted.items())]

    c.scene.clock_minutes += hours * 60
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
    line = (f"{pc.name} spends {hours} hour{'s' if hours != 1 else ''} "
            f"{verb}{' the ' + creature if creature else ''}. "
            f"{'Found: ' + tally if haul else 'Nothing worth carrying.'}{paid}")
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
    body = json.loads(request.body or "{}")
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return JsonResponse({"error": "nobody is being played"}, status=409)
    action = str(body.get("action", "forage")).strip().lower()
    if action != "forage":
        return JsonResponse(
            {"error": f"{action!r} is not a craft action yet — foraging only."},
            status=400)

    hours = max(1, min(48, int(body.get("hours", 1) or 1)))
    place, when = _forage_scene(c)
    from play import modelcfg

    cfg = modelcfg.for_role("narrator")

    # 1. The setting out. Written to the transcript before the roll, because that is
    # the order it happens in at a table.
    opening = _narrate([
        {"role": "system",
         "content": "You narrate a solo Pathfinder game. Two or three sentences, second "
                     "person, present tense. Never invent named people or places. Never "
                     "ask a question. Stop before anything is found."},
        {"role": "user",
         "content": f"{pc.name} sets out to forage for herbs. Terrain: {c.biome}. "
                     f"Near {place}, {when}. They mean to spend {hours} hour(s) "
                     f"searching. Narrate them beginning the search."},
    ], cfg, num_predict=140)
    if not opening or not str(opening).strip():
        opening = (f"You shoulder your satchel and work away from {place}, eyes on "
                   f"the ground, the {c.biome} closing in around you. {hours} hour"
                   f"{'s' if hours != 1 else ''} of searching lie ahead.")
    opening = str(opening).strip()
    c.transcript.append({"who": "gm", "text": opening})

    # 2. The dice decide. Same op as the bench; the client lands the visible die on the
    # first real d100 this rolled.
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

    # 3. The finding, told before the tally, ending in the question and three answers.
    listed = ", ".join(f"{h['count']}x {h['name']}" for h in haul) or "nothing"
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
         "content": f"{pc.name} spent {hours} hour(s) foraging the {c.biome} near "
                     f"{place} and found: {listed}. Narrate the finding, then suggest "
                     f"three next actions."},
    ], cfg, as_json=True, num_predict=260)

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
            closing += ("Piece by piece the satchel takes on weight: " +
                        ", ".join(h["name"].lower() for h in haul[:4]) +
                        ("," if len(haul) > 4 else "") + " earth still on the roots.")
    if len(suggestions) != 3:
        suggestions = ["Keep foraging", f"Head back toward {place}",
                       "Unpack the crafting bench"]

    tally = " · ".join(f"{h['name']} ×{h['count']}" for h in haul) or "Nothing gathered."
    c.transcript.append({"who": "gm", "kind": "consequence",
                         "text": f"{closing}\n\nGathered: {tally}. {tell}".strip()})
    c.transcript.append({"who": "gm", "text": "What do you do?"})
    c.suggestions = suggestions
    c.save()

    return JsonResponse({
        "opening": opening, "closing": closing, "tell": tell,
        "found": haul, "rolls": rolls, "checks": checks, "hours": hours,
        "suggestions": suggestions,
        "clock_minutes": c.scene.clock_minutes,
    })


@require_POST
def forage_do(request):
    """Walk the ground and see what turns up. Routed through the engine's `forage` op so
    the bench and the table roll on exactly the same machinery."""
    body = json.loads(request.body or "{}")
    c = campaign_mod.current()
    # No biome is sent. You forage where you are standing; the ground is `travel`'s to
    # change, and the bench has no business claiming to be somewhere else.
    params = {}
    # Clamped rather than trusted. The slider stops at 48, and a hand-written request for
    # a thousand hours would spend a thousand rolls before the body ever got a word in.
    hours = max(1, min(48, int(body.get("hours", 1) or 1)))
    params["hours"] = hours
    try:
        resolution = c.engine().run(c.engine().validate([{
            "op": "forage", "actor": "pc",
            "because": f"{hours} hour{'s' if hours != 1 else ''} spent looking",
            "params": params,
        }]))
    except IntentError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

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
    body = json.loads(request.body or "{}")
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
