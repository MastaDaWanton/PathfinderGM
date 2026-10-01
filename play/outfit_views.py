"""Outfitting: spend the starting gold before the sandbox.

"at the end of making your character we need a buy screen to spend starting gold, this
needs to happen before you start in the sandbox" (2026-09-07). The forge already rolled
the class's starting wealth into the purse (`creation.starting_purse`) and nothing let
the player spend it until they found a stall in play. This is the Core Rulebook's own
step between the sheet and the road: the weapon, armour and shield tables at their
printed prices, the adventuring-gear list at its own, and the purse as the wall.

The character is a roster entry by now; buying edits that entry's sheet and saves it.
Beginning the game afterwards is the same door "Play as X" uses (`campaign.switch_to`),
so nothing here starts a campaign of its own.
"""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from rules import goods, weapons as weapons_mod
from rules.sheet import from_dict, to_dict
from rules.crafting import Stock
from rules.tables import ARMOUR, SHIELDS

from . import roster
from .apiutil import read_body


def catalogue() -> dict:
    """Everything for sale, with the number beside it."""
    arms = []
    # Simple first, then martial, then exotic — the page opened on "Air reservoir" and
    # six alchemical cartridges before a longsword appeared.
    rank = {"simple": 0, "martial": 1, "exotic": 2}
    for key, w in sorted(weapons_mod.all_weapons().items(),
                         key=lambda kv: (rank.get(str(kv[1].get("prof", "simple")), 3),
                                         str(kv[1].get("name", kv[0])).lower())):
        cost = w.get("cost_gp")
        # `None` means the source never gave a price and nothing may sell it; `0.0` means
        # the rulebook prints a dash and the thing is free. Those were one case here, so
        # the shop refused to stock a club, a quarterstaff or a sling — and five class
        # kits were built from exactly those (docs/playtest-2026-09-18.md item 24).
        if cost in (None, "") or w.get("prof") == "exotic" and float(cost) > 100:
            continue
        # No siege engines, nothing "(Modern)" (owner's ruling E5) — the rule's one copy
        # is `weapons.UNSOLD_SECTION`, shared with `goods.outfit_weapons`.
        if weapons_mod.UNSOLD_SECTION.search(str(w.get("section") or "")):
            continue
        arms.append({"key": key, "name": w.get("name", key), "cost_gp": round(float(cost), 2),
                     "damage": w.get("damage", ""), "type": w.get("type", ""),
                     "prof": w.get("prof", "simple"), "hands": w.get("hands", 1),
                     "category": w.get("category", "melee")})
    armour = [{"key": k, "name": v["name"], "cost_gp": float(v["cost_gp"]), "ac": v["ac"],
               "max_dex": v["max_dex"], "acp": v["acp"], "weight": v.get("weight", "")}
              for k, v in ARMOUR.items() if v.get("cost_gp")]
    shields = [{"key": k, "name": v["name"], "cost_gp": float(v["cost_gp"]), "ac": v["ac"],
                "acp": v["acp"]}
               for k, v in SHIELDS.items() if v.get("cost_gp")]
    gear = [{"key": k, "name": v["name"], "cost_gp": float(v["cost_gp"]),
             "unit": v.get("unit", ""), "per": v.get("per", 1)}
            for k, v in GEAR_SORTED()]
    return {"weapons": arms, "armour": armour, "shields": shields, "gear": gear}


def GEAR_SORTED():
    return sorted(goods.GEAR.items(), key=lambda kv: kv[1]["name"])


def _price(kind: str, key: str) -> tuple[float, dict] | None:
    key = " ".join(str(key or "").split()).lower()
    if kind == "weapon":
        w = weapons_mod.all_weapons().get(key)
        if w and w.get("cost_gp") not in (None, ""):
            return float(w["cost_gp"]), dict(w)
    elif kind == "armour":
        a = ARMOUR.get(key)
        if a and a.get("cost_gp"):
            return float(a["cost_gp"]), dict(a)
    elif kind == "shield":
        s = SHIELDS.get(key)
        if s and s.get("cost_gp"):
            return float(s["cost_gp"]), dict(s)
    elif kind == "gear":
        g = goods.GEAR.get(key)
        if g:
            return float(g["cost_gp"]), dict(g)
    return None


def apply(entry, buys: list[dict]) -> tuple[dict, list[str]]:
    """Charge the purse and put the things on the sheet, or say what is wrong.

    All or nothing: a basket that overruns the purse buys none of it, with the
    shortfall named, rather than the first few lines and a surprise.
    """
    actor = from_dict(entry.sheet, ref="pc")
    problems: list[str] = []
    total_cp = 0
    lines: list[tuple[str, str, int, dict]] = []
    for b in buys or []:
        if not isinstance(b, dict):
            continue
        kind = str(b.get("kind", "")).strip().lower()
        key = str(b.get("key", "")).strip().lower()
        try:
            count = max(1, min(99, int(b.get("count", 1) or 1)))
        except (TypeError, ValueError):
            count = 1
        found = _price(kind, key)
        if found is None:
            problems.append(f"{key!r} is not for sale here.")
            continue
        price, item = found
        total_cp += int(round(price * 100)) * count
        lines.append((kind, key, count, item))
    have = goods.in_copper(actor.purse)
    if total_cp > have:
        problems.append(f"That comes to {total_cp / 100:.2f} gp and the purse holds "
                        f"{have / 100:.2f} gp — {(total_cp - have) / 100:.2f} gp short.")
    if problems:
        return {}, problems
    purse, paid = goods.spend(actor.purse, total_cp)
    if not paid:
        return {}, ["The purse would not cover it."]
    actor.purse = purse
    for kind, key, count, item in lines:
        if kind == "weapon":
            # Through the one router: a weapon onto the list, and a bundle of ammunition
            # into `goods` as the rounds it is (E3) — never a quiver to swing.
            stowed, _ = goods.stow(actor, key, count)
            if not stowed:
                for _ in range(count):
                    actor.weapons.append(key)
        elif kind in ("armour", "shield"):
            # Worn at once: bought armour is armour to wear. The suit (or shield) it
            # replaces, and any spares, go into `goods` under their TABLE KEY, where
            # `wear` and the Equipment tab read them. This filed the old suit in `stock`
            # under its display name ("leather armour"), which nothing could put back on
            # (measured 2026-09-30, docs/playtest-2026-09-30-findings.md item 2).
            was = str(getattr(actor, kind) or "none")
            if was != "none" and was != key:
                actor.goods[was] = int(actor.goods.get(was, 0) or 0) + 1
            setattr(actor, kind, key)
            if count > 1:
                actor.goods[key] = int(actor.goods.get(key, 0) or 0) + count - 1
        else:
            actor.add_stock(Stock(base=item["name"], tier="common", potency=1.0, craft=""),
                            count * int(item.get("per", 1) or 1))
    entry.sheet = to_dict(actor)
    roster.save(entry)
    return {"purse": goods.purse_line(actor.purse, goods.coinage()),
            "purse_gp": round(goods.in_copper(actor.purse) / 100, 2),
            "weapons": list(actor.weapons), "armour": actor.armour, "shield": actor.shield,
            "stock": [f"{s.count}x {s.base}" for s in actor.stock.values()]}, []


CLOSED = ("{name} has already begun their game, so the outfitter is closed to them: "
          "gear is bought from the shops and stalls in town now.")


def begun(entry) -> bool:
    """Whether this character's campaign has begun — the outfit page is creation only.

    The owner's answer, 2026-09-28: "outfit page should not be reachable". Measured by
    the lead at G1: buying here after the game began changed the roster's copy of the
    sheet and not the running campaign's (`weapons: [unarmed, longsword]` on the roster,
    `unarmed strike` at the table), so the two drifted apart. `campaign_id` is set by
    `begin_with` and by nothing that only enrols, which is exactly the line."""
    return bool(getattr(entry, "campaign_id", ""))


@ensure_csrf_cookie
@require_GET
def outfit_page(request):
    """The screen. The whole catalogue goes with it so it draws once."""
    return render(request, "play/outfit.html", {
        "state_json": json.dumps({
            "character": str(request.GET.get("character", "")).strip(),
            "world": str(request.GET.get("world", "")).strip(),
            "catalogue": catalogue(),
        }),
    })


@require_GET
def outfit_state(request, character_id: str):
    entry = roster.load(character_id)
    if entry is None:
        return JsonResponse({"error": f"no character {character_id!r}"}, status=404)
    actor = from_dict(entry.sheet, ref="pc")
    return JsonResponse({
        "name": actor.name, "class": actor.class_data.get("name", actor.char_class),
        "purse": goods.purse_line(actor.purse, goods.coinage()),
        "purse_gp": round(goods.in_copper(actor.purse) / 100, 2),
        "weapons": list(actor.weapons), "armour": actor.armour, "shield": actor.shield,
        "stock": [f"{s.count}x {s.base}" for s in actor.stock.values()],
        "proficient": {k: actor.is_proficient(k) for k in ("simple", "martial")},
        "begun": begun(entry),
        "closed": CLOSED.format(name=actor.name) if begun(entry) else "",
    })


@require_POST
def outfit_buy(request, character_id: str):
    entry = roster.load(character_id)
    if entry is None:
        return JsonResponse({"error": f"no character {character_id!r}"}, status=404)
    if begun(entry):
        # Refused with the reason named, so the roster and the running sheet cannot
        # drift apart again (see `begun`).
        return JsonResponse({"error": CLOSED.format(name=entry.name)}, status=409)
    body = read_body(request)
    got, problems = apply(entry, body.get("buys") or [])
    if problems:
        return JsonResponse({"problems": problems}, status=400)
    return JsonResponse({"ok": True, **got})
