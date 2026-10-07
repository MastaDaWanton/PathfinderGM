"""Craft and Profession, made worth a rank: the benches, the everyday trade uses, a day's work.

The owner, 2026-10-06: "the craft skill and the profession skill seem pretty useless what
can we do to make them more viable". docs/craft-profession-options.md measured it (a Craft
rank bought one house-rule construct repair; a Profession rank bought herb study and
ramming at sea) and offered five options. The owner chose, 2026-10-07, **A, B and C — not
D (named trades) and not E (Unchained background skills)**:

  A. Craft helps the benches — half your Craft ranks, as its own term in the roll
     breakdown of the matching world-class bench (`bench_terms`).
  B. Everyday trade uses — judge an item's make, mend ordinary gear, answer a question of
     the trade, haggle at a counter. Engine ops, each with the player's own die and a tell.
  C. A day's paid work — a day or a week at the trade, paid by level and training from a
     table (PF2e's Earn Income), never by the raw d20 total.

Every number here is a row in content/rules/trade-uses.json with its source; this module
reads them and does the arithmetic. One Craft and one Profession: a trade name folds onto
its base (`tables.base_skill`), since D was not chosen.
"""
from __future__ import annotations

import json
from pathlib import Path

from .dice import Modifier, stack

# --- A. Craft at the benches ------------------------------------------------------------

# Which skill ranks each world-class bench reads. Option A as the owner chose it: the
# forge is Craft (weapons/armour), the alchemy bench Craft (alchemy), the tannery Craft
# (leather), the enchanter's circle Craft (jewelry and the rest Craft stands in for when
# making magic items — CRB, Magic Item Creation) — all of them the one Craft this game
# keeps. Herbalism takes the BETTER of Craft and Profession: the book's herbalist is a
# Profession (Profession (herbalist) prepares herbs, Unchained Expanded Profession), and
# the herbarium's study already accepts any Profession (content/rules/herb-lore.json).
BENCH_SKILLS: dict[str, tuple[str, ...]] = {
    "herbalist": ("craft", "profession"),
    "blacksmith": ("craft",),
    "alchemist": ("craft",),
    "leatherworker": ("craft",),
    "enchanter": ("craft",),
}

# Half, rounded down — the paper's arithmetic, and every half-term in 1e rounds down. Half
# keeps it below the track: a level-10 smith with 10 ranks gains +5 beside Blacksmith 10
# and half level +5. Measured before (2026-10-06): 0 of the 5 benches read a Craft rank.
RANKS_DIVISOR = 2


def bench_modifier(actor, bench: str) -> Modifier | None:
    """The ranks term for one bench, as a named `Modifier`, or None with no ranks.

    Ranks are the sheet's own count (`Actor.ranks`), placed by the player at creation and
    level-up; nothing worn or cast reaches them, so this keeps the enchanter's no-feedback
    rule (`enchanter.check_terms`). A rank too few to make +1 still shows, at +0, so the
    player who placed one rank can see where it went and what the next one buys.
    """
    if actor is None:
        return None
    ranks = getattr(actor, "ranks", None) or {}
    best: tuple[str, int] | None = None
    for skill in BENCH_SKILLS.get(str(bench or "").strip().lower(), ()):
        n = int(ranks.get(skill, 0) or 0)
        if n > 0 and (best is None or n > best[1]):
            best = (skill, n)
    if best is None:
        return None
    skill, n = best
    return Modifier(n // RANKS_DIVISOR, f"{skill.title()} ranks ½ ({n})")


def bench_terms(actor, bench: str) -> list[dict]:
    """The bench's itemised term for the ranks: `[]` or one `{"label", "value"}`.

    Through `dice.stack` like every other term list, so the funnel's stacking rule is the
    one that decides (untyped: it stands beside the track level, half level and ability).
    The shape every bench's `check_terms` returns, so a bench appends it and its roll,
    preview and dice popup show it with no other change.
    """
    mod = bench_modifier(actor, bench)
    if mod is None:
        return []
    return [{"label": m.source, "value": m.value} for m in stack([mod])]


# --- the rule rows ----------------------------------------------------------------------

_ROWS: dict | None = None


def rows() -> dict:
    """content/rules/trade-uses.json, read once."""
    global _ROWS
    if _ROWS is None:
        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "rules" / "trade-uses.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        _ROWS = {k: v for k, v in data.items() if not str(k).startswith("_")}
    return _ROWS


def row(rule: str) -> dict:
    return rows()[rule]


# --- B. what a thing is, for the eye of somebody in the trade ---------------------------

def _record(actor, name: str) -> dict | None:
    """The forged or bought gear record a name means, or None for plain table gear."""
    finder = getattr(actor, "crafted_record", None)
    return finder(name) if callable(finder) else None


def carries(actor, name: str) -> str:
    """The carried thing's own name for `name`, or "" — the door every B use checks first.

    Exact first (`Actor.carried`, the forged records), then the looser word a player uses
    ("my sword"): the sheet's own `crafted_records_called`, or one carried name that
    contains the word. Two matches are no match — the caller names the choice."""
    want = " ".join(str(name or "").split()).lower()
    if not want:
        return ""
    for n in actor.carried():
        if n.strip().lower() == want:
            return n
    rec = _record(actor, want)
    if rec:
        return str(rec.get("name") or want)
    loose = getattr(actor, "crafted_records_called", None)
    if callable(loose):
        found = loose(want)
        if len(found) == 1:
            return str(found[0].get("name") or want)
    for word in ("my ", "the ", "a ", "an "):
        if want.startswith(word):
            want = want[len(word):]
    plain = [n for n in actor.carried() if want in n.strip().lower()]
    return plain[0] if len(plain) == 1 else ""


def kind_of(actor, name: str) -> tuple[str, dict]:
    """(what the Craft DC table calls it, the table row it came from).

    One of `mend-gear`'s `dc_by_kind` keys: armour, shield, bow, composite bow, simple /
    martial / exotic weapon, crossbow — or "typical item" for anything else carried."""
    from . import weapons as weapons_mod
    from .tables import ARMOUR, SHIELDS

    rec = _record(actor, name) or {}
    gear = str(rec.get("gear") or "").lower()
    low = name.strip().lower()
    base = str(rec.get("base") or rec.get("weapon") or rec.get("armour") or low).lower()
    if gear == "armour" or base in ARMOUR or low in ARMOUR:
        return "armour", dict(ARMOUR.get(base) or ARMOUR.get(low) or {})
    if gear == "shield" or base in SHIELDS or low in SHIELDS:
        return "shield", dict(SHIELDS.get(base) or SHIELDS.get(low) or {})
    w = None
    for key in (base, low):
        try:
            w = weapons_mod.get(key)
        except Exception:  # noqa: BLE001 - a name the weapon list does not know
            w = None
        if w:
            break
    if not w:
        return "typical item", {}
    wname = str(w.get("name") or base).lower()
    if "crossbow" in wname:
        return "crossbow", dict(w)
    if "bow" in wname and w.get("category") == "ranged":
        return ("composite bow" if "composite" in wname else "bow"), dict(w)
    return f"{w.get('prof') or 'simple'} weapon", dict(w)


def is_masterwork(actor, name: str) -> bool:
    rec = _record(actor, name) or {}
    return bool(rec.get("masterwork")) or "masterwork" in str(name).lower()


def is_magic(actor, name: str) -> bool:
    """Enchanted: a record with a magic layer, or a name carrying its bonus ("+1"). The
    CRB's Broken condition puts these past Craft: only mending or make whole mend them."""
    import re

    from . import magic_layer

    rec = _record(actor, name)
    if rec and (magic_layer.magic_of(rec).get("enhancement") or rec.get("magic")):
        return True
    return bool(re.search(r"\+\d", str(name)))


def creation_dc(actor, name: str) -> tuple[int, str]:
    """(the DC it took to make, why) — the CRB's Craft DC table, masterwork at 20."""
    r = row("mend-gear")
    kind, entry = kind_of(actor, name)
    spec = r["dc_by_kind"].get(kind, r["unplaced_dc"])
    if isinstance(spec, str):          # "10 + AC bonus"
        dc, why = 10 + int(entry.get("ac") or 0), f"10 + its AC bonus, for {kind}"
    else:
        dc, why = int(spec), f"for a {kind}" if kind != "armour" else "for armour"
    if is_masterwork(actor, name) and dc < int(r["masterwork_dc"]):
        dc, why = int(r["masterwork_dc"]), "for masterwork work"
    return dc, why


def price_gp(actor, name: str) -> float:
    """What the thing is worth, read through pricing (never priced here): a stock
    entry's own worth when it is one, else the Core tables by name."""
    from . import pricing

    for item in (getattr(actor, "stock", None) or {}).values():
        if str(getattr(item, "name", "")).strip().lower() == name.strip().lower():
            try:
                return float(pricing.worth(item))
            except Exception:  # noqa: BLE001 - a jar the pricer cannot read
                break
    return float(pricing.goods_worth(name))


def damage_of(actor, name: str):
    """The thing's object record if anything has ever hurt it, else None — read from
    `Actor.gear` without minting one (`Actor.item` creates on first ask)."""
    return (getattr(actor, "gear", None) or {}).get(name.strip().lower())


# --- B. haggling -----------------------------------------------------------------------

def undercut(margin: int) -> int:
    """The percentage a beaten Sense Motive moves the price: 2 + 1 a point, at most 25
    (Ultimate Campaign's 75% floor). Below 0 there is no haggle at all."""
    r = row("haggle")
    if margin < 0:
        return 0
    return min(int(r["max_percent"]),
               int(r["base_percent"]) + int(r["per_point_percent"]) * int(margin))


def dealing_key(kind: str, ref: str, *parts) -> str:
    return "|".join([kind, str(ref), *[str(p) for p in parts]])


def haggled(scene, ref: str, place: str, stall: str, day: int) -> int:
    """The percentage this person talked this counter round today, or 0."""
    rec = (getattr(scene, "dealings", None) or {}).get(
        dealing_key("haggle", ref, place, stall, day)) or {}
    return int(rec.get("percent", 0) or 0)


def buy_price(gp: float, percent: int) -> float:
    return round(float(gp) * (100 - int(percent)) / 100, 2)


def sell_price(gp: float, percent: int) -> float:
    return round(float(gp) * (100 + int(percent)) / 100, 2)


# --- C. a day's work -------------------------------------------------------------------

_PROFS = ("trained", "expert", "master", "legendary")


def proficiency(ranks: int) -> str:
    """PF2e's proficiency for this many ranks: the level each rank first opens at."""
    need = row("day-work")["proficiency_ranks"]
    got = "untrained"
    for p in _PROFS:
        if int(ranks) >= int(need[p]):
            got = p
    return got


def work_skill(actor) -> tuple[str, int]:
    """(the trade skill a day's work is rolled with, its ranks): the one with more ranks,
    Profession on a tie (the wage is Profession's in the book; Craft earns the same)."""
    ranks = getattr(actor, "ranks", None) or {}
    best = ("profession", int(ranks.get("profession", 0) or 0))
    craft = int(ranks.get("craft", 0) or 0)
    if craft > best[1]:
        best = ("craft", craft)
    return best


def work_offer(actor, scale: str) -> dict:
    """What a day's work pays here, before any die: the task, its DC and the day's pay
    at each outcome. Shown to the player, so the number the die moves is a number they
    can see (the opposite of NWN's hidden Appraise, docs/craft-profession-options.md §2)."""
    r = row("day-work")
    skill, ranks = work_skill(actor)
    caps = r["task_by_scale"]
    scale = str(scale or "town")
    cap = int(caps.get(scale, caps["town"]))
    level = max(1, int(getattr(actor, "level", 1) or 1))
    task = max(0, min(level, cap, 20))
    prof = proficiency(ranks)
    by = int(r["coin_scale"])
    table = r["pay_cp_by_task"]
    if prof == "untrained":
        return {"skill": "", "ranks": 0, "proficiency": prof, "task": task, "dc": None,
                "scale": scale, "pay_cp": {"untrained": int(r["untrained_cp_per_day"])}}
    col = 1 + _PROFS.index(prof)
    up = str(task + 1) if task < 20 else "21"
    return {
        "skill": skill, "ranks": ranks, "proficiency": prof, "task": task,
        "dc": int(r["dc_by_task"][task]), "scale": scale,
        "pay_cp": {
            "critical success": int(table[up][col]) * by,
            "success": int(table[str(task)][col]) * by,
            "failure": int(table[str(task)][0]) * by,
            "critical failure": 0,
        },
    }


def degree(margin: int) -> str:
    """PF2e's four degrees, by margin alone (no naturals: 1e excludes them from skills)."""
    by = int(row("day-work")["critical_by"])
    if margin >= by:
        return "critical success"
    if margin >= 0:
        return "success"
    if margin <= -by:
        return "critical failure"
    return "failure"
