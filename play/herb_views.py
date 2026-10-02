"""Herb knowledge: the herbarium, studying, tasting, asking, reading
(docs/herbalism-contracts.md §4).

The rules are `rules/herbknowledge.py`'s and the taste is the engine's `taste` op; this
module is the door the bench card and the Journal knock on. Nothing here talks to a
model, and nothing here authors a number: DCs, prices and times are rows in
content/rules/herb-lore.json, and what a herb does is the herb's own spec.

**Time passes through the one door** (`Scene.advance`), as the crafting bench's does, so
the effects, the pools and the body move with the clock.

**What a view learns is history.** Each act that reveals something writes a turn-log row
(`play/history.py` reads it: "You tasted hemlock."), and a taste reaches the narrator's
memory the way a forage from the craft panel does — as its tell, which names only what
was learned (law 3).
"""
from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from rules import goods, herbknowledge as hk, ingredients as ing_mod
from rules.dice import BadDice
from rules.intents import IntentError

from . import campaign as campaign_mod
from .apiutil import read_body


# --- small shared pieces ---------------------------------------------------------------------

def _price(cp: int) -> str:
    """"2 sp", "1 gp 5 sp": a price the way the contract writes it."""
    coins = goods.coins_for(int(cp))
    order = [cid for cid, _ in reversed(goods.DENOMINATIONS)]
    return " ".join(f"{coins[c]} {c}" for c in order if coins.get(c)) or "nothing"


def clock(c) -> dict:
    """{"day": 14, "label": "Day 14, 6:20pm"} — the bench's clock shape (§3.1)."""
    minute = int(getattr(c.scene, "clock_minutes", 0) or 0)
    day = hk.day_of(minute)
    h, m = divmod(minute % (24 * 60), 60)
    half = "am" if h < 12 else "pm"
    return {"day": day, "minute": minute,
            "label": f"Day {day}, {(h % 12) or 12}:{m:02d}{half}"}


def _herb(herb_id: str):
    try:
        return ing_mod.get(str(herb_id or ""))
    except KeyError:
        return None


def _pc(c):
    """The character, with a herbalist's home knowledge seeded on first read."""
    pc = c.scene.pc()
    if pc is not None:
        hk.ensure_seeded(pc, world=_world(c), scene=c.scene)
    return pc


def _world(c):
    try:
        return c.world
    except Exception:  # noqa: BLE001 — a campaign whose export cannot load still reads
        return None


def _cannot(pc, doing: str):
    """The table's own rule (`views._cannot_act`): the downed do nothing here."""
    from . import downed

    if pc is None:
        return JsonResponse({"error": "Nobody is being played."}, status=409)
    if downed.state_of(pc) not in ("fine", "disabled"):
        return JsonResponse({"error": f"{pc.name} is in no condition to {doing}."},
                            status=409)
    return None


def _revealed(pc, ingredient, keys) -> list[dict]:
    """The §4.2 property rows for the keys just learned."""
    keys = set(keys)
    return [p for p in hk.properties(pc, ingredient) if p["key"] in keys]


def _log(c, kind: str, ingredient, **extra) -> None:
    """A turn-log row the Journal's history reads (play/history.py `_effect_lines`)."""
    from . import history as history_mod

    effect = {"ref": c.scene.pc().ref if c.scene.pc() else "pc", "kind": kind,
              "item": ingredient.id, "name": ingredient.name, **extra}
    c.turn_log.append(history_mod.stamp(c, {
        "kind": "resolution", "door": "herb",
        "outcomes": [{"intent_id": "herb", "op": kind, "tell": "", "effects": [effect]}]}))


def _pay(pc, cp: int) -> bool:
    purse, ok = goods.spend(pc.purse, cp)
    if ok:
        pc.purse = purse
    return ok


def teachers_here(c, pc) -> list[dict]:
    """Everybody standing here who knows herbs (§8.4): a healer by trade, or somebody
    whose own words say herbalist, midwife, apothecary... Named, never reffed on the
    page; the ref is what the browser posts back."""
    from rules import population

    price = _price(int(hk.lore()["teacher"]["price_cp"]))
    out = []
    for ref, a in c.scene.actors.items():
        if a is pc or getattr(a, "is_pc", False) or a.is_down:
            continue
        if hk.teaches(a, population.of_ref(c.scene, ref)):
            out.append({"ref": ref, "name": a.name, "price": price})
    return out


def library_here(c) -> dict | None:
    """A place in this settlement that keeps records (§8.4), or None."""
    try:
        places = c.engine().places()
    except Exception:  # noqa: BLE001 — no places to read is no library
        return None
    rules = hk.lore()["library"]
    for p in places:
        if hk.is_library(p):
            return {"name": p.name, "price": _price(int(rules["price_cp"])),
                    "minutes": int(rules["minutes"])}
    return None


# --- §4.1, §4.2 -----------------------------------------------------------------------------

@require_GET
def herbarium(request):
    c = campaign_mod.current()
    pc = _pc(c)
    if pc is None:
        return JsonResponse({"entries": []})
    entries = hk.herbarium(pc)
    c.save()                       # the seed, if it just ran, is the character's now
    return JsonResponse({"entries": entries})


@require_GET
def herb_card(request, herb_id: str):
    c = campaign_mod.current()
    ing = _herb(herb_id)
    if ing is None:
        return JsonResponse({"error": f"There is no herb called {herb_id}."}, status=404)
    pc = _pc(c)
    if pc is None:
        return JsonResponse({"error": "Nobody is being played."}, status=409)
    card = hk.card(pc, ing, clock=int(c.scene.clock_minutes or 0))
    card["teachers_here"] = teachers_here(c, pc)
    card["library_here"] = library_here(c)
    c.save()
    return JsonResponse(card)


# --- §4.3 study -----------------------------------------------------------------------------

@require_POST
def herb_study(request):
    """A Knowledge (nature) or Profession check on the player's die (`face`; null means
    the server rolls, the bench's convention). No automatic natural 20 (CRB p.180); ten
    minutes pass; the dose is not used; a miss waits for a rest."""
    body = read_body(request)
    c = campaign_mod.current()
    ing = _herb(body.get("id"))
    if ing is None:
        return JsonResponse({"error": "There is no such herb."}, status=400)
    pc = _pc(c)
    refused = _cannot(pc, "study anything")
    if refused:
        return refused
    if not (hk.carried(pc, ing.id) or hk.stock_of(pc, ing.id)):
        return JsonResponse({"error": f"{pc.name} has no {ing.name} to study."}, status=400)
    now = int(c.scene.clock_minutes or 0)
    if hk.study_waits(pc, ing.id, clock=now):
        return JsonResponse({"error": f"{pc.name} has studied {ing.name} and found nothing; "
                                      f"it needs fresh eyes after a rest."}, status=409)
    if not hk.unknown_count(pc, ing):
        return JsonResponse({"error": f"{pc.name} already knows everything about "
                                      f"{ing.name}."}, status=409)
    dc = hk.study_dc(ing)
    skill, mods = hk.study_skill(pc, dc)
    if not skill:
        return JsonResponse({"error": f"{pc.name} has no training in Knowledge (nature) or "
                                      f"Profession, and {ing.name} is past what an untrained "
                                      f"eye can tell."}, status=409)
    face = body.get("face")
    engine = c.engine()
    label = f"Study {ing.name}"
    try:
        if face is None:
            roll = engine.dice.d20(mods, label=label, visibility="player")
        else:
            if isinstance(face, bool) or not isinstance(face, (int, float)):
                raise BadDice("not a face")
            roll = engine.dice.given(int(face), mods, label=label)
    except BadDice:
        return JsonResponse({"error": "A d20 shows a face from 1 to 20."}, status=400)
    minutes = int(hk.lore()["study"]["minutes"])
    c.scene.advance(minutes)
    result = hk.study(pc, ing, roll.total, clock=int(c.scene.clock_minutes or 0))
    revealed = _revealed(pc, ing, result["revealed"])
    bonus = sum(m.value for m in roll.modifiers)
    line = (f"{pc.name} studies {ing.name} ({skill.title()}: d20 {roll.faces[0]}{bonus:+d} = "
            f"{roll.total} vs DC {dc}): "
            + (f"learned {'; '.join(p['text'] for p in revealed)}." if revealed
               else "nothing comes of it; it will take fresh eyes after a rest."))
    c.transcript.append({"who": "gm", "kind": "consequence", "text": line})
    if revealed:
        _log(c, "herb_studied", ing, learned=[p["key"] for p in revealed])
    c.save()
    return JsonResponse({
        "roll": {"face": roll.faces[0], "bonus": bonus, "total": roll.total, "dc": dc,
                 "success": result["success"], "margin": result["margin"],
                 "skill": skill, "terms": [m.as_dict() for m in roll.modifiers]},
        "revealed": revealed, "minutes": minutes, "clock": clock(c)})


# --- §4.4 taste -----------------------------------------------------------------------------

@require_POST
def herb_taste(request):
    """The engine's `taste` op (rules/engine.py), driven from the card. The dose is spent,
    the raw effects land, one benefit and one drawback are learned. A taster who drops is
    `down`; a death ends the campaign the way the table's own turn would."""
    body = read_body(request)
    c = campaign_mod.current()
    ing = _herb(body.get("id"))
    if ing is None:
        return JsonResponse({"error": "There is no such herb."}, status=400)
    pc = _pc(c)
    refused = _cannot(pc, "taste anything")
    if refused:
        return refused
    if not (hk.carried(pc, ing.id) or hk.stock_of(pc, ing.id)):
        return JsonResponse({"error": f"{pc.name} has no {ing.name} to taste."}, status=400)
    engine = c.engine()
    try:
        resolution = engine.run(engine.validate([{
            "op": "taste", "actor": pc.ref, "because": f"tasting {ing.name} from the card",
            "params": {"item": ing.id}}]))
    except IntentError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    outcome = next((o for o in resolution.outcomes if o.op == "taste"), None)
    if outcome is None or outcome.status == "refused":
        return JsonResponse({"error": outcome.tell if outcome else "Nothing was tasted."},
                            status=409)
    minutes = int(hk.lore()["taste"]["minutes"])
    c.scene.advance(minutes)
    learned = next((e.get("learned") for e in outcome.effects
                    if e.get("kind") == "taste"), []) or []
    tells = [o.tell for o in resolution.outcomes if o.tell]
    c.transcript.append({"who": "gm", "kind": "consequence", "text": " ".join(tells)})
    c.history.append({"role": "user", "content": (
        f"(From the herb card: {pc.name} tastes a little {ing.name}.)")})
    c.history.append({"role": "assistant", "content": " ".join(tells)})
    from . import history as history_mod

    c.turn_log.append(history_mod.stamp(c, {
        "kind": "resolution", "door": "herb",
        "outcomes": [o.as_dict() for o in resolution.outcomes]}))
    try:
        from .views import _remember

        _remember(c, resolution, "")
    except Exception:  # noqa: BLE001 — the ledger is a convenience, never the taste
        import logging

        logging.getLogger("pathfindergm").exception("the taste's ledger note failed")
    pc = c.scene.pc()
    down = bool(pc is not None and pc.is_down)
    ended = ""
    if pc is not None and pc.is_dead:
        from .views import _end_campaign

        _end_campaign(c, pc)
        ended = c.ended
    c.save()
    out = {"revealed": _revealed(pc, ing, learned), "tells": tells, "minutes": minutes,
           "down": down, "clock": clock(c)}
    if ended:
        out["ended"] = ended
    return JsonResponse(out)


# --- §4.5 ask and library ---------------------------------------------------------------------

@require_POST
def herb_ask(request):
    """Show a herb to somebody who knows herbs and pay them to tell you about it (§8.4).
    Their attitude decides: below indifferent they refuse in words; friendlier, they tell
    more (content/rules/herb-lore.json `teacher`)."""
    from rules import attitude

    body = read_body(request)
    c = campaign_mod.current()
    ing = _herb(body.get("id"))
    if ing is None:
        return JsonResponse({"error": "There is no such herb."}, status=400)
    pc = _pc(c)
    refused = _cannot(pc, "ask anybody anything")
    if refused:
        return refused
    ref = str(body.get("ref") or "")
    teacher = next((t for t in teachers_here(c, pc) if t["ref"] == ref), None)
    if teacher is None:
        return JsonResponse({"error": "Nobody here by that name knows herbs."}, status=400)
    person = c.scene.actors[ref]
    rules = hk.lore()["teacher"]
    minutes = int(rules["minutes"])
    size = hk.lesson_size(person)
    if not size:
        hostile = attitude.of(person) == attitude.HOSTILE
        said = (f"{person.name} wants nothing to do with you and will not say a word about "
                f"{ing.name}." if hostile else
                f"{person.name} has no wish to help you, and keeps what they know of "
                f"{ing.name} to themselves.")
        c.transcript.append({"who": "gm", "kind": "consequence", "text": said})
        c.save()
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0, "refused": said})
    order = hk.lesson_order(pc, ing)[:size]
    if not order:
        said = f"{person.name} has nothing to tell you about {ing.name} you do not know."
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0, "refused": said})
    cp = int(rules["price_cp"])
    if not _pay(pc, cp):
        said = f"{person.name} asks {_price(cp)}, and you cannot pay it."
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0, "refused": said})
    person.purse = goods.credit(getattr(person, "purse", None) or {}, cp)
    c.scene.advance(minutes)
    keys = hk.reveal(pc, ing.id, hk.with_gates(ing, order),
                     f"taught by {person.name}, day {hk.day_of(c.scene.clock_minutes)}")
    revealed = _revealed(pc, ing, keys)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{person.name} looks over the {ing.name} and tells you: "
        + "; ".join(p["text"] for p in revealed) + f". ({_price(cp)} paid.)")})
    _log(c, "herb_taught", ing, teacher=person.name, learned=keys)
    c.save()
    return JsonResponse({"revealed": revealed, "paid": _price(cp), "minutes": minutes,
                         "refused": "", "clock": clock(c)})


@require_POST
def herb_library(request):
    """Look a herb up where records are kept: a fee and an hour, and only what the world
    writes down — the benefits of common and uncommon herbs (§8.4)."""
    body = read_body(request)
    c = campaign_mod.current()
    ing = _herb(body.get("id"))
    if ing is None:
        return JsonResponse({"error": "There is no such herb."}, status=400)
    pc = _pc(c)
    refused = _cannot(pc, "read anything")
    if refused:
        return refused
    lib = library_here(c)
    if lib is None:
        return JsonResponse({"error": "There is no library or archive here."}, status=409)
    rules = hk.lore()["library"]
    known = set(hk.known_keys(pc, ing))
    fresh = [k for k in hk.common_knowledge(ing) if k not in known]
    if not fresh:
        said = (f"Nothing at {lib['name']} says more about {ing.name} than you know."
                if hk.common_knowledge(ing) else
                f"{ing.name} is not written of at {lib['name']}; what it does is not "
                f"common knowledge.")
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0, "refused": said})
    cp = int(rules["price_cp"])
    if not _pay(pc, cp):
        said = f"Reading at {lib['name']} costs {_price(cp)}, and you cannot pay it."
        return JsonResponse({"revealed": [], "paid": "", "minutes": 0, "refused": said})
    minutes = int(rules["minutes"])
    c.scene.advance(minutes)
    keys = hk.reveal(pc, ing.id, fresh,
                     f"looked up at {lib['name']}, day {hk.day_of(c.scene.clock_minutes)}")
    revealed = _revealed(pc, ing, keys)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"An hour at {lib['name']} over {ing.name}: "
        + "; ".join(p["text"] for p in revealed) + f". ({_price(cp)} paid.)")})
    _log(c, "herb_looked_up", ing, place=lib["name"], learned=keys)
    c.save()
    return JsonResponse({"revealed": revealed, "paid": _price(cp), "minutes": minutes,
                         "refused": "", "clock": clock(c)})


# --- §4.6 manuals -------------------------------------------------------------------------

@require_POST
def herb_manual(request):
    """Read a herbalism manual the character has with them: hours pass, its properties
    are learned, and the first reading pays herbalist mastery once."""
    from rules import worldclass

    body = read_body(request)
    c = campaign_mod.current()
    manual = hk.manual_named(str(body.get("item") or ""))
    if manual is None:
        return JsonResponse({"error": "There is no such manual."}, status=400)
    pc = _pc(c)
    refused = _cannot(pc, "read")
    if refused:
        return refused
    if not hk.holds_manual(pc, manual):
        return JsonResponse({"error": f"{pc.name} does not have {manual['name']}."},
                            status=400)
    minutes = int(manual.get("hours", 1)) * 60
    c.scene.advance(minutes)
    how = f"read in {manual['name']}"
    revealed: list[dict] = []
    for iid, keys in hk.manual_keys(manual).items():
        ing = _herb(iid)
        new = hk.reveal(pc, iid, keys, how)
        if new and ing is not None:
            revealed += [dict(p, id=iid, name=ing.name) for p in _revealed(pc, ing, new)]
    mastery = {"lines": [], "total": None, "level": None, "levelled": []}
    if manual["id"] not in pc.manuals_read:
        pc.manuals_read.append(manual["id"])
        track = worldclass.get("herbalist")
        progress = pc.track("herbalist")
        # MERGE: lane/herb-progress names the constant `worldclass.MANUAL_MP`; until it
        # lands the rule row's number is the same five.
        mp = int(getattr(worldclass, "MANUAL_MP", hk.lore()["manual"]["mastery"]))
        got = worldclass.award_bonus(track, progress, why=f"read {manual['name']}", mp=mp)
        mastery = {"lines": got["reasons"], "total": got["total"], "level": got["level"],
                   "levelled": got["levelled"]}
        hk.ensure_seeded(pc, world=_world(c), scene=c.scene)
    c.transcript.append({"who": "gm", "kind": "consequence", "text": (
        f"{pc.name} reads {manual['name']} ({manual.get('hours', 1)} hours)"
        + (f" and learns {len(revealed)} thing{'s' if len(revealed) != 1 else ''} about "
           f"herbs." if revealed else ", and finds nothing new in it."))})
    from . import history as history_mod

    c.turn_log.append(history_mod.stamp(c, {
        "kind": "resolution", "door": "herb",
        "outcomes": [{"intent_id": "herb", "op": "manual", "tell": "", "effects": [
            {"ref": pc.ref, "kind": "manual_read", "manual": manual["name"],
             "learned": len(revealed)}]}]}))
    c.save()
    return JsonResponse({"revealed": revealed, "mastery": mastery, "minutes": minutes,
                         "clock": clock(c)})
