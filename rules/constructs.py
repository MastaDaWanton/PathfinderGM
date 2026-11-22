"""Constructs made at the enchanting circle: the Animate method (owner ruling 2026-11-22).

The owner, 2026-11-22: "Remove item creation feats they are unnecessary, instead build the
magic items like wands and scrolls and constructs into the enchanting world class." So
there is no Craft Construct feat: the Enchanter track stands in for it, as it already
stands in for Craft Wondrous Item (docs/item-creation-feats-study.md §3.7).

**The book** (sources in docs/research/2026-11-22-constructs.md). Bestiary, Craft
Construct: materials cost half the price plus the full cost of the body, a day per 1,000
gp. Ultimate Magic, Building Constructs: the check is DC 5 + CL (the printed construction
line's DC, which does not always equal that, so it is data), +5 for each requirement
missing. Each construct's own line (content/rules/constructs.json) names its CL, price,
spells, skill, DC and body.

**The circle's shape, kept** (rules/enchanter.py): one step, an Enchanter check, an
always-played game for quality, the work In progress for the book's days, collected from
the In progress section. What differs from Bind is only what the step takes and what
Collect makes:

  takes   the body the line names (`body`: satchel ingredients, an item the forge or the
          leatherworker made, or coin for a golem's body no bench builds yet), and
          essences worth half of (price - body) at 1 mote = 100 gp, picked from the shelf
          plain motes first, so a phial that grants a property is the last spent;
  DC      the printed DC, +5 per spell group neither known nor carried in a potion or
          scroll (a carried one is used up, as at Bind), +5 if Enchanter level is below
          the line's CL: the owner's enchanting rule, never a refusal;
  gate    the Enchanter level the stat block's CR rounds up to (homunculus CR 1 at
          Enchanter 1, a flesh golem CR 7 at Enchanter 7): an owner call, recorded;
  quality the game's tier sets the body's hit points: Sound is the printed block, each
          step above adds 1 hit point per Hit Die and Crude takes 1 off, an untyped
          `hp_max` modifier on the construct's own effect (law 2: remove the effect and
          the points go with it). +3 per HD at Flawless stays under a d10's maximum;
  miss    the owner's enchanting rule for a miss: the time is lost, nothing is spent.

**What joins** (`arrive`): the bestiary's own stat block, through `bestiary.instantiate`,
holding `bond.owned-by-you` (source `made:<ref>`), `bond.travels-with-you` through the
company door (`Engine._travels_with_you`, so the encounter budget counts it exactly as it
counts a claimed construct: at its CR, `encounter_budget.companion_level`) and devoted.
It obeys in character, and a construct's character is the book's: mindless, it "follows
instructions explicitly" and cannot speak (`gm/companions.py` reads `mute`/`mindless`).

**Prior art, and what it abandoned** (the research note): PF2's minion trait and the
Inventor's construct (it acts when commanded; uncommanded it only defends itself), 5e's
Steel Defender (Dodge unless commanded). Both fixed the uncommanded construct's behaviour
in the rules rather than leaving it free, which is the book's golem text too ("do nothing
without orders"; returns an attack if attacked) — the line its turn is told. Arcanum let
built mechanical followers sit outside the follower cap and players built armies; here
each construct is one actor the encounter budget prices like any other companion.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

TRACK_ID = "enchanter"
GP_PER_MOTE = 100
DC_PER_MISSING = 5
# Hit points per Hit Die per quality step from Sound (index 1). House number, owner call.
HP_PER_HD_PER_STEP = 1
SOUND = 1


@lru_cache(maxsize=1)
def rows() -> dict[str, dict]:
    """The shipped construction lines, keyed by bestiary template. Read from the install."""
    from django.conf import settings

    path = Path(settings.BASE_DIR) / "content" / "rules" / "constructs.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not str(k).startswith("_")}


def row(template: str) -> dict | None:
    return rows().get(str(template or "").strip().lower())


def _block(template: str) -> dict:
    from . import bestiary

    return bestiary.raw_block(template) or {}


def name_of(template: str) -> str:
    return str(_block(template).get("name") or template.replace("-", " ").title())


def cr_of(template: str) -> float:
    try:
        return float(_block(template).get("cr_value") or 0)
    except (TypeError, ValueError):
        return 0.0


def level_for(template: str) -> int:
    """The Enchanter level that may animate it: its CR rounded up, at least 1 (owner call)."""
    return max(1, int(math.ceil(cr_of(template) - 1e-9)))


def hit_dice(template: str) -> int:
    """The printed block's Hit Dice ("2d10" is 2): the sheet's own `hit_dice` reads its
    level, which a bestiary block leaves at 1."""
    raw = str(_block(template).get("hit_dice") or "1").split("d", 1)[0]
    return max(1, int(raw)) if raw.strip().isdigit() else 1


def motes_for(r: dict) -> int:
    """Half of (price - body), the book's magic half of the cost, in motes rounded up."""
    gp = max(0, int(r["price_gp"]) - int(r.get("body_gp", 0) or 0)) / 2
    return int(math.ceil(gp / GP_PER_MOTE - 1e-9))


def days_for(r: dict) -> int:
    """The circle's working time: 8 hours per 1,000 gp of price, 8 hours a calendar day
    (magic_layer's rule for a binding, so a construct and a ring keep one clock)."""
    from . import magic_layer as ml

    hours = max(ml.MIN_HOURS, int(math.ceil(int(r["price_gp"]) / 1000 - 1e-9))
                * ml.HOURS_PER_1000_GP)
    return int(math.ceil(hours / ml.HOURS_PER_DAY))


def _spell_name(sid: str) -> str:
    from . import magic_layer

    return magic_layer._spell_name(sid)


def view(level: int) -> list[dict]:
    """What the Animate picker lists: every line, its lock in words, its costs."""
    out = []
    for template, r in rows().items():
        need = level_for(template)
        out.append({
            "id": template, "name": name_of(template), "cr": _block(template).get("cr"),
            "level": need, "locked": need > int(level),
            "lock_reason": f"Enchanter {need}" if need > int(level) else "",
            "motes": motes_for(r), "days": days_for(r), "cl": int(r["cl"]),
            "body": str((r.get("body") or {}).get("words") or ""),
            "spells": [" or ".join(_spell_name(s) for s in g) for g in r.get("spells") or ()],
        })
    return sorted(out, key=lambda x: (x["level"], x["name"]))


# --- the body ----------------------------------------------------------------------------

def forged_bodies(actor, gear: str) -> list[tuple[str, object]]:
    """(stock key, item) for each carried, unworn, idle thing the forge or the
    leatherworker made of this gear kind."""
    from . import enchanter, forge_items, inprogress

    worn = enchanter._worn_names(actor)
    out = []
    for k, st in (getattr(actor, "stock", None) or {}).items():
        rec = forge_items.record_of(st)
        if rec is None or str(rec.get("gear") or "") != gear:
            continue
        if st.name in worn or inprogress.work_of(st) is not None:
            continue
        out.append((k, st))
    return out


def _pick_essences(actor, need: int, level: int, now: int):
    """Phials worth `need` motes: plain motes first, then the smallest, so a phial that
    grants a property is the last thing spent. Returns ([(phial, n)], motes)."""
    from . import enchanter as en

    shelf = [p for p in en.phials(actor, en.reserved(actor, now))
             if p.rank <= en.level_band(level)]
    shelf.sort(key=lambda p: (bool(p.grants), p.motes))
    picked, have = [], 0
    for p in shelf:
        n = 0
        while n < p.count and have < need:
            n += 1
            have += p.motes
        if n:
            picked.append((p, n))
        if have >= need:
            break
    return picked, have


# --- the step ----------------------------------------------------------------------------

def build_animate(plan, actor, body, where, now) -> None:
    """Fill the Animate StepPlan (rules/enchanter.py `plan_step` calls it)."""
    from . import enchanter as en
    from . import goods

    template = str((body or {}).get("construct") or "").strip().lower()
    r = row(template)
    if r is None:
        plan.problems.append("Choose what to animate first." if not template
                             else f"There is no construction line for {template!r}.")
        return
    name = name_of(template)
    plan.recipe = template
    plan.name_after = name
    need_level = level_for(template)
    if plan.level < need_level:
        plan.problems.append(f"{english_a(name)} is Enchanter {need_level} work, and you are "
                             f"Enchanter {plan.level}.")
    # The body.
    b = r.get("body") or {}
    for iid, n in (b.get("ingredients") or {}).items():
        have = int((getattr(actor, "inventory", None) or {}).get(iid, 0) or 0)
        label = str(iid).replace("-", " ").title()
        if have < int(n):
            plan.problems.append(f"The body needs {int(n)} {label}; you carry {have}.")
        else:
            plan.consumes.append((f"inv:{iid}", int(n), label))
    if b.get("forged"):
        bodies = forged_bodies(actor, str(b["forged"]))
        want = str((body or {}).get("body") or "").split(":", 1)[-1]
        chosen = next(((k, st) for k, st in bodies if k == want), None) if want \
            else (bodies[0] if bodies else None)
        if chosen is None:
            plan.problems.append(f"The body is {b.get('words') or 'a forged ' + b['forged']}; "
                                 f"you carry none that is not worn or in progress.")
        else:
            plan.choices = {"body": chosen[0]}
            plan.info.append(f"The body: your {chosen[1].name}.")
    coin = int(b.get("coin_gp", 0) or 0)
    if coin:
        if goods.in_copper(getattr(actor, "purse", None) or {}) < coin * 100:
            plan.problems.append(f"The body ({b.get('words')}) costs {coin:,} gp, bought; "
                                 f"your purse holds less.")
        else:
            plan.choices = dict(plan.choices, coin_gp=coin)
            plan.info.append(f"The body is bought: {b.get('words')}, {coin:,} gp.")
    # The essences.
    need = motes_for(r)
    picked, have = _pick_essences(actor, need, plan.level, now)
    if have < need:
        plan.problems.append(f"Animating {english_a(name).lower()} costs {need} motes of "
                             f"essence; your shelf carries {have} you may handle.")
    else:
        plan.consumes += [(p.key, n, p.name) for p, n in picked]
        plan.info.append(f"Spends {need} motes: "
                         + en._say_list([f"{n} {p.name}" for p, n in picked]) + ".")
    plan.rank = max((p.rank for p, _ in picked), default=1)
    lead = en._lead([p for p, _ in picked])
    if lead is not None:
        plan.lead = {"id": template, "name": name, "rank": lead.rank}
        plan.phase = lead.phase
    # The DC.
    terms = [{"why": f"{name}'s construction line, {r.get('skill')}", "dc": int(r["dc"])}]
    groups = [[str(s) for s in g] for g in r.get("spells") or ()]
    knows = en._spells_known(actor, {s for g in groups for s in g})
    held = en._spells_held(actor)
    for g in groups:
        if set(g) & knows:
            continue
        hit = next((s for s in g if s in held), None)
        if hit:
            if f"stock:{held[hit]}" not in [k for k, _, _ in plan.consumes]:
                plan.consumes.append((f"stock:{held[hit]}", 1, _spell_name(hit)))
            plan.info.append(f"{_spell_name(hit)} is carried in a potion or scroll: it is "
                             f"used up in the animating.")
            continue
        terms.append({"why": f"no {' or '.join(_spell_name(s) for s in g)} known or carried",
                      "dc": DC_PER_MISSING})
    if plan.level < int(r["cl"]):
        terms.append({"why": f"Enchanter {plan.level} is below the caster level "
                             f"{int(r['cl'])} it asks", "dc": DC_PER_MISSING})
    plan.dc_terms = terms
    plan.dc = sum(t["dc"] for t in terms)
    plan.days = days_for(r)
    plan.work_minutes = plan.days * 1440
    plan.info.append(f"Then it waits In progress: ready in {plan.days} "
                     f"day{'s' if plan.days != 1 else ''}.")


def english_a(name: str) -> str:
    from . import words

    return words.a(name)[:1].upper() + words.a(name)[1:]


def land(actor, plan, tier: int, *, now: int) -> tuple[dict, str]:
    """Spend the body and the essences, and put the work In progress. (work, said)."""
    from . import enchanter as en
    from . import goods, inprogress
    from .crafting import Stock

    r = row(plan.recipe) or {}
    key = (plan.choices or {}).get("body")
    if key and key not in (getattr(actor, "stock", None) or {}):
        return {"ok": False}, "The body is no longer in your pack. Nothing was spent."
    en.spend(actor, plan.consumes)
    coin = int((plan.choices or {}).get("coin_gp", 0) or 0)
    if coin:
        actor.purse, _ok = goods.spend(dict(actor.purse or {}), coin * 100)
    made = False
    if key:
        key = inprogress.set_apart(actor, key, 1)
    else:
        key = inprogress.fresh_key(actor, f"construct-body-{plan.recipe}")
        actor.stock[key] = Stock(base=f"{plan.name_after} body", count=1, craft=TRACK_ID,
                                 kind="construct-body", how=["made"])
        made = True
    result = {"construct": plan.recipe, "quality_index": int(tier), "made_body": made,
              "ingredients": dict((r.get("body") or {}).get("ingredients") or {}),
              "name": plan.name_after}
    got = inprogress.begin(actor, key, craft=TRACK_ID, minutes=max(1, plan.work_minutes),
                           now=int(now), label=f"Animating {en._a(plan.name_after)}",
                           doing="animating", result=result)
    said = (f"The animating takes. The {plan.name_after} waits In progress, ready in "
            f"{plan.days} day{'s' if plan.days != 1 else ''}.")
    return got, said


def collect(item, actor, res: dict) -> dict:
    """At Collect the body is gone from the pack; the product names the construct, which
    the collecting view brings into the scene (`arrive`) — Collect has no scene."""
    key = next((k for k, st in (getattr(actor, "stock", {}) or {}).items() if st is item), "")
    if key:
        actor.stock.pop(key, None)
    return {"said": f"The {res.get('name')} stirs and rises.",
            "product": {"key": "", "name": str(res.get("name") or ""),
                        "construct": {"template": res["construct"],
                                      "quality_index": int(res.get("quality_index", SOUND))}}}


def cancel(item, actor, res: dict) -> dict:
    """Stopped: the essences are spent (as a stopped binding's are); a body made at the
    circle gives its satchel ingredients back, a forged one comes back as it was."""
    if res.get("made_body"):
        key = next((k for k, st in (actor.stock or {}).items() if st is item), "")
        if key:
            actor.stock.pop(key, None)
        for iid, n in (res.get("ingredients") or {}).items():
            actor.carry(str(iid), int(n))
    return {"said": f"The animating is stopped. The body comes back unmoving; the essences "
                    f"are spent."}


# --- what joins --------------------------------------------------------------------------

def arrive(engine, maker, spec: dict) -> tuple[object, str]:
    """The finished construct, in the scene, the maker's: (actor, tell)."""
    from . import bestiary, states, worldclass as wc
    from .activeeffect import ActiveEffect

    scene = engine.scene
    template = str(spec["template"])
    actor = bestiary.instantiate(template, scene)
    scene.add(actor)
    source = f"made:{actor.ref}"
    origin = "craft:enchanter:animate"
    q = int(spec.get("quality_index", SOUND))
    hd = hit_dice(template)
    extra = (q - SOUND) * HP_PER_HD_PER_STEP * hd
    actor.apply_effect(ActiveEffect(
        name="made by you", kind="bond", key=f"{source}:owned", source=source,
        origin=origin, duration="until-dismissed", tags=(states.OWNED_BY_YOU,),
        modifiers=([{"kind": "combat_mod", "target": "hp_max", "amount": extra,
                     "note": f"{wc.quality_name(q)} work"}] if extra else []),
        payload={"maker": getattr(maker, "ref", "pc"), "quality_index": q}))
    engine._travels_with_you(actor)
    engine._set_attitude(actor, "devoted", None, origin)
    actor.hp = actor.hp_max
    quality = wc.quality_name(q)
    tell = (f"{english_a(actor.name)} made at {quality} quality rises and is "
            f"{maker.name}'s: it follows {maker.name} and obeys"
            + (f" ({extra:+d} hit points for the work)" if extra else "") + ".")
    return actor, tell


def made_row(actor) -> dict | None:
    """The construction line of a construct, or None for anything else."""
    from . import states

    if actor is None or not actor.has_state(states.CONSTRUCT):
        return None
    return row(str(getattr(actor, "from_template", "") or ""))


def mindless(actor) -> bool:
    """No Intelligence score: the book's mindless (`morale.intelligence`)."""
    from . import morale, states

    return bool(actor is not None and actor.has_state(states.CONSTRUCT)
                and morale.intelligence(actor) is None)


def mute(actor) -> bool:
    """A construct that cannot speak: mindless, or a block whose languages say so (the
    homunculus: "Common (cannot speak)"). Read off the printed block's field."""
    from . import states

    if actor is None or not actor.has_state(states.CONSTRUCT):
        return False
    if mindless(actor):
        return True
    langs = _block(str(getattr(actor, "from_template", "") or "")).get("languages") or []
    if isinstance(langs, str):
        langs = [langs]
    return not langs or any("cannot speak" in str(x).lower() or str(x).lower() == "none"
                            for x in langs)
