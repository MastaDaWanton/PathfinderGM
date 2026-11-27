"""Create Sanguine Elixir (Ultimate Magic), reworked for the benches (feat loop b4-crafting).

The book (aonprd.com FeatDisplay "Create Sanguine Elixir", read 2026-11-26): once a day, as
the sorcerer regains spell slots, she picks one of her bloodline powers and transfers it
into a small potion — 1 hour, oils and distillates worth 100 gp — and loses the power
"until the next time you clear your mind to regain spell slots". Any creature that drinks
it "can activate the bloodline power anytime before the end of its next turn, as if it had
access to that bloodline power", not below the power's minimum level, level-dependent
effects at the lower of the drinker's character level and the sorcerer level. It is a
magic item at her caster level, and it "lose[s] potency 1 day after" it is made.

Its prerequisite Brew Potion is retired (owner 2026-11-22; `feats.RETIRED`), and the owner
ruled 2026-11-26 that such feats are stripped of it and reworked: the elixir is made at the
alchemy bench (a field kit or a laboratory, the bench's own `where_here`), where the oils
are. Craft (alchemy) 12 ranks is the game's one Craft (`tables.base_skill`). No check and
no minigame: the book has none, so none is invented.

Every part is an `ActiveEffect`, so removing it removes the power (law two):
  maker   `lent.bloodline.<power>` + `duration.until-rest`: the power is gone from
          `grantedpowers.had` and the night's sleep that brings slots back returns it, and
          the effect is also "made one today";
  drinker `borrowed.bloodline.<power>` for two rounds (the drink's turn and the next),
          payload naming the bloodline, variant, level and a pool of one use, read by
          `grantedpowers.had` as a source like Eldritch Heritage's.
"""
from __future__ import annotations

import re

FEAT = "create-sanguine-elixir"
LENT = "lent.bloodline."
BORROWED = "borrowed.bloodline."
COST_CP = 100 * 100                       # "special oils and distillates worth 100 gp"
MINUTES = 60                              # "Creating a sanguine elixir takes 1 hour"
KEEPS = 24 * 60                           # "They lose their potency 1 day after"
ROUNDS = 2                                # "before the end of its next turn"
CRAFT = "sanguine"


def slug(key) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(key or "").lower()).strip("-")


def _tags(actor):
    for eff in getattr(actor, "effects", None) or ():
        for tag in eff.tags or ():
            yield eff, str(tag)


def lent(actor) -> set[str]:
    """Slugs of the bloodline powers this sorcerer has bottled since her last rest. Read
    off the effects directly: `has_state` reads `grantedpowers.standing_tags`, which reads
    `had`, which asks this."""
    return {t[len(LENT):] for _e, t in _tags(actor) if t.startswith(LENT)}


def borrowed(actor) -> list[dict]:
    """The bloodline powers an elixir drunk lends right now: each effect's payload."""
    return [dict(e.payload.get("borrowed") or {}) for e, t in _tags(actor)
            if t.startswith(BORROWED) and isinstance(e.payload.get("borrowed"), dict)]


def holds(actor) -> bool:
    from . import feats

    return FEAT in feats._held(actor)


def lendable(actor) -> list[dict]:
    """The sorcerer's own bloodline powers she could bottle: {key, name, level, line}. Her
    own bloodline only — "one of your bloodline powers" — never one she is borrowing."""
    from . import grantedpowers

    out = []
    for row in grantedpowers.had(actor):
        if row.get("kind") != "bloodline" or row.get("borrowed") or row.get("heritage"):
            continue
        p = row["power"]
        out.append({"key": str(p.get("key") or p.get("name")), "name": str(p.get("name")),
                    "level": int(p.get("level", 1) or 1), "line": str(p.get("line") or ""),
                    "bloodline": row["id"], "variant": str((row.get("vars") or {}).get("id")
                                                           or "")})
    return out


def refusal(actor, power: str, *, where: dict | None, fight: bool = False) -> str:
    """Why the elixir cannot be made now, in the player's words, or ""."""
    from . import goods

    if not holds(actor):
        return f"{actor.name} does not have Create Sanguine Elixir."
    if fight:
        return "You are in a fight. The bench waits until it is over."
    if lent(actor):
        return ("An elixir has been made since your last rest: the next waits until you "
                "have slept and your spells have come back.")
    where = where or {}
    if not where.get("lab") and not where.get("kit"):
        return "It needs a field kit or a laboratory: you have neither here."
    row = next((r for r in lendable(actor) if slug(r["key"]) == slug(power)), None)
    if row is None:
        names = ", ".join(r["name"] for r in lendable(actor))
        return (f"{power!r} is not one of your bloodline powers"
                + (f": you could bottle {names}." if names else "."))
    if goods.in_copper(getattr(actor, "purse", None) or {}) < COST_CP:
        return "The oils and distillates cost 100 gp, and you cannot pay it."
    return ""


def offer(actor, *, where: dict | None, fight: bool = False) -> dict | None:
    """What the bench shows a sorcerer with the feat, or None for anyone else."""
    if not holds(actor):
        return None
    rows = lendable(actor)
    why = refusal(actor, rows[0]["key"], where=where, fight=fight) if rows else \
        "You have no bloodline power to bottle."
    return {"powers": rows, "cost_gp": COST_CP // 100, "minutes": MINUTES,
            "refusal": why, "lent": sorted(lent(actor))}


def make(actor, power: str, *, now: int) -> dict:
    """Bottle the power: the coin spent, the power lent until rest, the elixir carried.
    The caller passes the hour (`Scene.advance`) and has already asked `refusal`."""
    from . import goods
    from .activeeffect import ActiveEffect
    from .crafting import Stock
    from .sheet import UNTIL_REST

    row = next(r for r in lendable(actor) if slug(r["key"]) == slug(power))
    actor.purse, _ok = goods.spend(dict(actor.purse or {}), COST_CP)
    level = max(1, int(getattr(actor, "level", 1) or 1))
    actor.apply_effect(ActiveEffect(
        name=f"{row['name']} bottled", kind="effect", key="sanguine-lent",
        source="Create Sanguine Elixir", origin=f"feat:{FEAT}",
        tags=(LENT + slug(row["key"]), UNTIL_REST)))
    spec = {"type": "bloodline_power", "bloodline": row["bloodline"],
            "variant": row["variant"], "power": row["key"], "name": row["name"],
            "min_level": row["level"], "level": level, "made": int(now)}
    stock = Stock(base=f"Sanguine Elixir of {row['name']}", craft=CRAFT, count=1,
                  how=["drink"], specs=[spec], caster_level=level,
                  effects=[f"Lends {row['name']} until the end of the drinker's next turn."],
                  spoils_minute=int(now) + KEEPS)
    actor.add_stock(stock)
    tell = (f"{actor.name} bleeds {row['name']} into a small vial of oils: a sanguine "
            f"elixir, good for a day. The power is gone from {actor.name} until the next rest.")
    return {"name": stock.name, "power": row["name"], "tell": tell}


def grant_intent(spec: dict, target: str, because: str) -> list[dict]:
    """The drink: a `grant` of the borrowed tag, carrying what `grantedpowers.had` reads."""
    key = slug(spec.get("power"))
    if not key or not spec.get("bloodline"):
        return []
    return [{"op": "grant", "actor": target, "because": because,
             "params": {"to": target, "tag": BORROWED + key,
                        "name": f"{spec.get('name') or key} (sanguine elixir)",
                        "duration": {"amount": ROUNDS, "unit": "round"},
                        "borrowed": {k: spec.get(k) for k in (
                            "bloodline", "variant", "power", "name", "min_level", "level",
                            "made")}}}]


def pool_id(borrow: dict) -> str:
    """One use per elixir: its own pool, so a second elixir is a fresh use."""
    return f"sanguine elixir {slug(borrow.get('power'))} {int(borrow.get('made') or 0)}"
