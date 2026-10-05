"""What the winners of a fight do with a player they have beaten.

Measured 2026-10-04, the robbers in the warrens: two robbers put the player at -2, the
bleeding stopped, and the downed path printed "You come round about an hour later, face
down where you fell, on 1 hit point. Whoever was standing over you has gone." Nobody had
gone. Both robbers were still in the scene on the squares they had fought from, at full
hit points, the player's 30 gold pieces still in the player's purse, and the next turn's
suggestions still offered "I focus on the first robber". The line was a claim about the
world that no code made true — the owner's report: "an hour later they are still in the
scene in the same place ... its all over the place." And it broke the standing ruling
that Continue means the scene moves: a fight runs to its end AND its consequences.

**How others settle a lost fight**, looked up before this was written:

  * Fate Core, "Conceding the Conflict": a character who is taken out rather than
    conceding gets no say in their fate after the scene — the winner decides, and the
    worst of it is "ending up in the enemy's clutches, in shackles, without any of your
    stuff" (fate-srd.com/fate-core/conceding-conflict). The narration has to reflect the
    victory; it cannot be undone by the loser's telling.
  * Gothic (Piranha Bytes, 2001): a duel's loser drops to the ground on 1 hit point and
    is robbed by the winner, who takes the weapon and a share of the ore, and whose
    aggression resets when the loser stands (the series' knockout system, as described
    by its players' guides — not confirmed from a primary source).
  * Kenshi: knocked-out characters are looted by whoever beat them, by what that kind
    of attacker wants — hungry bandits take the food and leave the rest — and are left
    lying (kenshi wiki, Getting Started / Hungry Bandit; community-written).
  * The "fail forward" advice for tabletop GMs (Gnome Stew, D&D Beyond's "Failing
    Forward"): a lost fight is a turn in the story — captured, robbed, an item lost —
    not the end of the campaign.

The common shape: the winner takes what they came for, and the scene moves on without
them. Here, in the engine's terms and nothing else:

  * **Who.** Whoever is standing over the player: here, on their feet, and HOSTILE on
    the attitude track (`attitude.of`) — the one source of truth every surface reads.
    `Engine._foes_settle` writes everybody who fought the player into it, so after a
    fight these are exactly the people who were fighting.
  * **What they take.** Only a person who is not the law robs: a wolf does not carry a
    purse, and the watch arrests rather than pockets. Until 2026-10-05 they took ALL the
    coin and nothing else; the owner's ruling that day replaced it — "a percentage of
    your coin and 1 item they would want. a quest to retrieve the gold and the item
    should be created" — and the section below is that ruling in the engine's terms.
  * **Then they go.** Out of the room through `Scene.move`, the only door, to somewhere
    off stage in the same town (`residency.offstage`), not destroyed: they are still
    the people who did it, and the campaign keeps them.

**The robbery and the way back (the owner's ruling, 2026-10-05).** Looked up first:

  * Oblivion's Highwayman takes a fixed toll — "Your money or your life", 100 gold — and
    lets a pauper plead poverty unless the clothes on their back are worth 10 gold or
    more; the toll can be pickpocketed back off him with no bounty, because he will not
    report it (en.uesp.net/wiki/Oblivion:Highwayman). The take is a SHARE of what you
    carry, and the thing taken can be taken back.
  * Gothic: whoever knocks you down "will take a percentage of your Ore" (a player's
    forum answer on the Ironworks Gaming forum, Gothic 2; the percentage itself could not
    be confirmed from a primary source, and is not used here).
  * Kenshi's Hungry Bandits loot the knocked-out "and take food items, but will generally
    leave other possessions alone" (kenshi wiki, community-written): what is taken is
    what THAT robber wants, by rule, not everything.
  * Tabletop advice on taking a character's gear (Mike's Gaming, "Getting Your Stuff
    Stolen", 2010, and its comments): it is "quite traumatic for a player", so the GM
    should make getting it back a road the player can see — hunt the thief, find where
    they went. Fate Core's "taken out" (fate-srd.com, Conceding the Conflict) lets the
    winner decide; it does not oblige them to take everything.

So, in the engine's terms and nothing else:

  * **A share of the coin**, never all of it: a hasty search of a body in a street
    finds the purse and misses the coin in a boot or a seam. One robber takes half;
    each further robber standing over you adds a quarter, because more hands search
    more of you; never more than three quarters (`coin_share`). Counted coin by coin
    in each denomination, rounding DOWN — the odd coin is the one the search missed —
    so no change is made from coins nobody carried. Into the robber's own purse.
  * **One thing they would want**, chosen by rule (`the_take`): the most valuable
    thing the player carries that a fence would pay for and the robber can run with.
    Valued from the tables (`pricing.goods_worth`, the weapon, armour and gear rows);
    a forged or enchanted thing by its base row plus the book's masterwork price
    (+300 gp a weapon, +150 gp armour or a shield) and its enhancement's market price
    (`magicitem.market_price`), or the shelf's own worth if that is more. Never a worn
    suit or shield, nor anything in a body slot (rings, cloaks, belts): worn close, and
    a level-1 character's armour is what keeps them alive. Never the body's own
    weapons. Portable means it fits in the robber's own spare light load (CRB Table
    7-4, `gear.capacity` less what they already carry): a medium load slows a Medium
    creature, and they are leaving. Worth at least a silver piece — an untrained
    hireling's day (CRB Table 6-9) — or it is not worth the carrying. The thing moves
    whole into the robber's hands: a shelf record keeps every field (a forged blade's
    pieces, an enchantment), a weapon its damage record, and the props ledger names
    the player as its owner, marked stolen (the steal manoeuvre's shape).
  * **A quest to get it back**, through the one quest store (`cards.open_quest`, the
    Journal's source): "Get back what <them> took", the robbers by name with their refs
    on the card, the coin and the thing as objectives, and where they went. Where they
    went is a heard-of place (`heard_places.record`), "<the robber>'s hideout", off the
    place they robbed you in: the place doors make it real the first time the player
    goes there (`judgement.go_to_heard_place` → `found`), and `settle` walks the robbers
    in from off stage the moment it exists. Done by ANY means — a fight and a looted
    body, a payment, a word, a theft — because it is measured on the holdings, never on
    the means: each objective ticks when the robber no longer holds what was taken AND
    (for the thing) the player holds it again. A copy bought at a shop does not tick
    it while the robber still has the original. Finishing pays the story award, as
    every quest does.

No number here is a model's and no state is the narrator's: the lines are the engine's
own sentences, built from what was actually moved.
"""
from __future__ import annotations

import copy
from fractions import Fraction

from . import attitude as attitude_mod
from . import goods
from . import holding
from . import states

# Where the winners go: off stage in the town they robbed you in. A leaf of the place id,
# read by nobody but `residency.is_offstage`.
OFFSTAGE_LEAF = "made-off"

# The share of the purse a search takes (`coin_share`): half for one pair of hands, a
# quarter more for each further robber, never more than three quarters.
ONE_ROBBER_SHARE = Fraction(1, 2)
EACH_FURTHER_SHARE = Fraction(1, 4)
MOST_SHARE = Fraction(3, 4)

# Below this a thing is not worth a robber's carrying: one silver piece, an untrained
# hireling's day (CRB Table 6-9, "Hireling, untrained: 1 sp per day").
WORTH_THE_CARRYING_GP = 0.1

# The book's masterwork prices (CRB pp. 149, 153): a weapon +300 gp, armour or a shield
# +150 gp. What a forged or enchanted thing adds to its base row when it is valued.
MASTERWORK_GP = {"weapon": 300, "armour": 150, "shield": 150}

# The quest's provenance (stage 8's `rule:<id>`): the engine opened it, by this rule.
QUEST_ORIGIN = "rule:robbed-while-down"


def standing_over(scene) -> list:
    """The people standing over a beaten player: here, conscious, hostile to them."""
    out = []
    for ref, a in scene.actors.items():
        if a.is_pc or a.is_down:
            continue
        if attitude_mod.of(a, default="") != attitude_mod.HOSTILE:
            continue
        out.append(a)
    return out


def _robs(actor) -> bool:
    """Whether this winner robs: a person, and not the law."""
    from .engine import _a_person

    if actor.has_state(states.GUARD):
        return False
    return _a_person(getattr(actor, "from_template", "") or "")


def _names(actors) -> str:
    names = [a.name for a in actors]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


# --- the coin ----------------------------------------------------------------------------

def coin_share(robbers: int) -> Fraction:
    """The share of the purse `robbers` pairs of hands take: 1/2, 3/4, then 3/4."""
    if robbers <= 0:
        return Fraction(0)
    return min(MOST_SHARE, ONE_ROBBER_SHARE + EACH_FURTHER_SHARE * (robbers - 1))


def take_coin(purse: dict, share: Fraction) -> dict:
    """The coins a search at this share finds, denomination by denomination, rounded
    down: thirty gold pieces at three quarters is twenty-two, and the odd coin is the
    one in the boot. No change is made — a robber does not break your gold into silver."""
    out = {}
    for coin, n in (purse or {}).items():
        took = int(n or 0) * share.numerator // share.denominator
        if took > 0:
            out[coin] = took
    return out


# --- the one thing -----------------------------------------------------------------------

def _gear_row(name) -> dict | None:
    """The general store's row for a carried good, by key or by the name it sells as."""
    low = holding.plain(name)
    for key, row in goods.GEAR.items():
        if low in (key, str(row.get("name", "")).lower()):
            return row
    return None


def _row_weight(entry: dict | None) -> float | None:
    if not entry:
        return None
    lb = entry.get("lb") if entry.get("table") in ("armour", "shield") else \
        entry.get("weight_lb", entry.get("lb"))
    try:
        return float(lb) if lb is not None else None
    except (TypeError, ValueError):
        return None


def _stock_parts(s) -> tuple[str, str]:
    """("weapon" | "armour" | "shield" | "", base row name) for a shelf entry: what a
    forged or enchanted thing really is, so it is valued off the row it was built on."""
    from . import forge_items

    rec = forge_items.record_of(s)
    if rec is not None:
        gear = str(rec.get("gear") or "")
        return (gear if gear in MASTERWORK_GP else ""), str(rec.get("base") or "")
    if getattr(s, "weapon", None):
        return "weapon", str(s.weapon)
    if getattr(s, "armour", None):
        entry = goods.known_item(str(s.armour))
        kind = entry["table"] if entry and entry["table"] in ("armour", "shield") else "armour"
        return kind, str(s.armour)
    return "", ""


def stock_worth(s) -> float:
    """What a thing on the shelf is worth to a fence, in gold.

    The shelf's own worth (`pricing.worth`, the trade panel's number) — or, for a forged
    or enchanted weapon, suit or shield, its base row's price plus the masterwork price
    and its enhancement's market price, when that is more. `pricing.worth` prices a
    forged longsword as an untiered jar (1.5 gp): it was written for the herbalist's
    bench, and a blade is worth what its row and its working say."""
    from . import forge_items
    from . import magicitem
    from . import pricing

    shelf = float(pricing.worth(s))
    kind, base = _stock_parts(s)
    if not kind:
        return shelf
    rec = forge_items.record_of(s) or {}
    entry = goods.known_item(base) if base else None
    built = float(entry.get("cost_gp") or 0) if entry else 0.0
    if getattr(s, "masterwork", False) or rec.get("masterwork"):
        built += MASTERWORK_GP[kind]
    plus = int(getattr(s, "enhancement", 0) or rec.get("enhancement") or 0)
    if plus > 0:
        built += magicitem.market_price("weapon" if kind == "weapon" else "armour_property",
                                        plus)
    return max(shelf, built)


def _stock_weight(s) -> float | None:
    from .gear import _forged_weight

    got = _forged_weight(s)
    if got is not None:
        return got[0]
    kind, base = _stock_parts(s)
    if kind and base:
        return _row_weight(goods.known_item(base))
    return None                     # a jar, a draught, a charm: carried in a hand


def _worn_counts(actor) -> dict[str, int]:
    """How many of each name are in a body slot — rings, a cloak, a forged suit."""
    out: dict[str, int] = {}
    for items in (getattr(actor, "slots", None) or {}).values():
        for it in items or ():
            if it:
                k = str(it).strip().lower()
                out[k] = out.get(k, 0) + 1
    return out


def carried_things(actor) -> list[dict]:
    """Everything a robber could take off this body, one entry per kind of thing:
    {"store", "key", "name", "gp", "lb", "count"}. `count` is how many go if it is
    taken — one, except a measured good (fifty feet of rope is one coil).

    Left out: what is worn on the body (the suit and shield `armour`/`shield` name, and
    anything in a body slot), the body's own weapons (the unarmed strike, a natural
    attack, a weapon a class forms), clothes, and coin, which is the purse's."""
    from . import pricing
    from . import weapons as weapons_mod

    out: list[dict] = []
    worn = _worn_counts(actor)
    for sid, s in (getattr(actor, "stock", None) or {}).items():
        free = int(getattr(s, "count", 0) or 0) - worn.get(str(s.name).strip().lower(), 0)
        if free <= 0 or "outfit" in str(getattr(s, "base", "")).lower():
            continue
        out.append({"store": "stock", "key": sid, "name": str(s.name),
                    "gp": stock_worth(s), "lb": _stock_weight(s), "count": 1})
    seen: set[str] = set()
    for w in list(getattr(actor, "weapons", None) or ()):
        entry = goods.known_item(str(w))
        if not entry or entry.get("table") != "weapon":
            continue                # the unarmed strike, a bite: no row, no price
        key = str(entry["key"])
        if key in seen or key in ("unarmed", "improvised"):
            continue
        seen.add(key)
        try:
            if (actor.weapon(key) or {}).get("granted_by"):
                continue            # a weapon a class forms is the body's own
        except Exception:  # noqa: BLE001 - a weapon the sheet cannot read is not taken
            continue
        out.append({"store": "weapon", "key": key, "name": str(entry.get("name") or key),
                    "gp": float(entry.get("cost_gp") or 0), "lb": _row_weight(entry),
                    "count": 1})
    for name, n in (getattr(actor, "goods", None) or {}).items():
        n = int(n or 0)
        low = holding.plain(name)
        if n <= 0 or "outfit" in low or "clothes" in low:
            continue
        if holding.is_money(name) or holding.container_of_money(name):
            continue
        entry = goods.known_item(name)
        if entry and entry.get("table") == "weapon":
            key = str(entry["key"])
            if key in seen:
                continue
            seen.add(key)
            out.append({"store": "weapon", "key": key, "name": str(entry.get("name") or key),
                        "gp": float(entry.get("cost_gp") or 0), "lb": _row_weight(entry),
                        "count": 1})
            continue
        if entry and entry.get("table") in ("armour", "shield"):
            if str(entry["key"]) == str(getattr(actor, entry["table"], "") or "").lower():
                n -= 1              # the one on the body is worn, not carried
            if n <= 0:
                continue
            out.append({"store": "goods", "key": name, "name": str(entry["key"]),
                        "gp": float(entry.get("cost_gp") or 0), "lb": _row_weight(entry),
                        "count": 1})
            continue
        row = _gear_row(name)
        if row is None and entry is None:
            continue                # nobody priced it, and a fence pays for a price
        if row is not None and row.get("unit"):
            per = max(1, int(row.get("per", 1) or 1))
            gp = float(row.get("cost_gp") or 0) * n / per
            lb = float(row.get("lb") or 0) * n / per if row.get("lb") is not None else None
            out.append({"store": "goods", "key": name, "name": low, "gp": gp, "lb": lb,
                        "count": n})
            continue
        out.append({"store": "goods", "key": name, "name": low,
                    "gp": float(pricing.goods_worth(name)),
                    "lb": (float(row["lb"]) / max(1, int(row.get("per", 1) or 1))
                           if row is not None and row.get("lb") is not None
                           else _row_weight(entry)),
                    "count": 1})
    return out


def spare_load(actor) -> float:
    """How many pounds this creature can add and stay in a light load (CRB Table 7-4)."""
    from . import gear

    try:
        load = gear.load(actor)
    except Exception:  # noqa: BLE001 - an unreadable sheet carries what a Str 10 does
        return float(gear.capacity(10)[0])
    return max(0.0, float(load["light"]) - float(load["lb"]))


def the_take(pc, robber) -> dict | None:
    """The one thing this robber takes: the most valuable thing the player carries that
    is worth the carrying and fits the robber's spare light load; the lighter of two
    equal prices, then by name. None when nothing qualifies."""
    room = spare_load(robber)
    pool = [c for c in carried_things(pc)
            if c["gp"] >= WORTH_THE_CARRYING_GP and (c["lb"] is None or c["lb"] <= room)]
    if not pool:
        return None
    pool.sort(key=lambda c: (-c["gp"], c["lb"] if c["lb"] is not None else 0.0, c["name"]))
    return pool[0]


def holds(actor, thing: dict) -> int:
    """How many of this thing the actor holds now, read from the store it lives in. A
    weapon is counted on the weapons list and in the goods alike — the loot files it on
    the list, a handover in both — and the larger count is the true one."""
    if actor is None:
        return 0
    store, key = thing.get("store"), str(thing.get("key") or "")
    if store == "stock":
        s = (getattr(actor, "stock", None) or {}).get(key)
        return int(getattr(s, "count", 0) or 0) if s is not None else 0
    if store == "weapon":
        listed = sum(1 for w in actor.weapons if goods.canonical(str(w)) == key)
        packed = sum(int(n or 0) for name, n in actor.goods.items()
                     if goods.canonical(str(name)) == key)
        return max(listed, packed)
    k = holding.key_in(actor.goods, key)
    return int(actor.goods.get(k, 0) or 0) if k is not None else 0


def _move(scene, pc, robber, thing: dict) -> None:
    """The thing leaves the player's carry and goes into the robber's, whole."""
    store, key = thing["store"], thing["key"]
    if store == "stock":
        # The record itself, deep-copied: a forged blade's pieces, an enchantment's
        # properties, a jar's specs all travel, so what is got back is what was taken.
        one = copy.deepcopy(pc.stock[key])
        pc.take_stock(key, 1)
        robber.add_stock(one, 1)
    elif store == "weapon":
        for i, w in enumerate(pc.weapons):
            if goods.canonical(str(w)) == key:
                del pc.weapons[i]
                break
        for name in list(pc.goods):
            if goods.canonical(str(name)) == key:
                pc.goods[name] -= 1
                if pc.goods[name] <= 0:
                    del pc.goods[name]
                break
        if goods.canonical(str(pc.equipped or "")) == key and key not in [
                goods.canonical(str(w)) for w in pc.weapons]:
            pc.equipped = "unarmed"
        # A blade the fight notched stays notched.
        hurt = pc.gear.pop(key, None)
        if hurt is not None:
            robber.gear[key] = hurt
        goods.stow(robber, key, 1)
    else:
        n = int(thing.get("count", 1) or 1)
        pc.goods[key] -= n
        if pc.goods[key] <= 0:
            del pc.goods[key]
        robber.goods[key] = int(robber.goods.get(key, 0) or 0) + n
    # Whose it is travels with it (the steal manoeuvre's shape, Creation Kit's owner
    # beside the stolen flag): in the robber's hands, still the player's.
    rec = scene.hold_prop(f"{pc.name}'s {thing['name']}", robber.ref, owner=pc.ref,
                          from_=thing["name"], state="intact",
                          turn=int(getattr(scene, "clock_minutes", 0) or 0))
    rec["stolen"] = True
    thing["prop"] = rec["name"]


# --- the robbery -------------------------------------------------------------------------

def aftermath(scene, pc, coins=None, *, here_name: str = "",
              turn: int = 0) -> tuple[list[dict], list[str]]:
    """The winners act on their victory: the effects, and the sentences that say them.

    Called while the player is still down — they are robbed lying there, which is what
    "standing over you" means — and before the clock is moved, so whatever else the hour
    does it does to a scene the winners have already left. Returns ([], []) when nobody
    is standing over the player: then there was nobody to rob them and nobody to go.
    `here_name` is the name of where it happened, for the quest's facts.
    """
    winners = standing_over(scene)
    if not winners or pc is None:
        return [], []
    effects: list[dict] = []
    lines: list[str] = []
    robbers = [a for a in winners if _robs(a)]
    robber = robbers[0] if robbers else None
    took: dict = {}
    thing: dict | None = None
    before_cp = 0
    if robber is not None:
        from .bestiary import collapse_kit

        # The robber's own pockets are observed before the player's coin goes into
        # them, so "what he had before" is a number that will not change under us when
        # somebody later loots him.
        collapse_kit(robber)
        before_cp = goods.in_copper(robber.purse)
        purse = {k: int(v) for k, v in dict(pc.purse or {}).items() if int(v or 0) > 0}
        took = take_coin(purse, coin_share(len(robbers)))
        for coin, n in took.items():
            pc.purse[coin] = int(pc.purse.get(coin, 0)) - n
            if pc.purse[coin] <= 0:
                del pc.purse[coin]
            robber.purse[coin] = int(robber.purse.get(coin, 0) or 0) + n
        thing = the_take(pc, robber)
        if thing is not None:
            thing["robber_before"] = holds(robber, thing)
            _move(scene, pc, robber, thing)
            thing["pc_left"] = holds(pc, thing)
        share = coin_share(len(robbers))
        effects.append({"kind": "took", "ref": robber.ref, "from": pc.ref,
                        "items": ([f"{n} {coin}" for coin, n in took.items()]
                                  + ([thing["name"]] if thing else [])),
                        "coin": dict(took), "share": f"{share.numerator}/{share.denominator}",
                        "of": dict(purse), "thing": dict(thing) if thing else {},
                        "why": "robbed while down"})
        lines.append(_robbed_line(robber, took, purse, thing, coins))
    where = _offstage(scene)
    landmark = str(getattr(scene, "at", "") or "")
    gone = []
    for a in winners:
        scene.move(a.ref, where)
        gone.append(a)
        effects.append({"kind": "left", "ref": a.ref, "to": where,
                        "why": "won the fight and went"})
    lines.append(f"{_names(gone)} {'has' if len(gone) == 1 else 'have'} gone.")
    if robber is not None and (took or thing):
        card = open_the_quest(scene, robber, gone, took, before_cp, thing, where,
                              landmark, coins, here_name=here_name, turn=turn)
        effects.append({"kind": "quest", "id": card.id, "title": card.title,
                        "origin": QUEST_ORIGIN, "hideout": card.recover.get("hideout", "")})
        lines.append(f"You mean to get it back. It is in your journal: {card.title}.")
    return effects, [_upper_first(x) for x in lines]


def _robbed_line(robber, took: dict, purse: dict, thing, coins) -> str:
    """The sentence for what was taken, built from the moves themselves."""
    said = goods.purse_line(took, coins) if took else ""
    had = goods.purse_line(purse, coins) if purse else ""
    if len(took) == 1 and set(took) == set(purse):
        # One kind of coin: "22 of your 30 gold pieces", not the coin's name twice.
        coin = next(iter(took))
        said, had = str(took[coin]), goods.purse_line(purse, coins)
    item = f"your {thing['name']}" if thing else ""
    if took and item:
        return f"{robber.name} took {said} of your {had}, and {item}."
    if took:
        return f"{robber.name} took {said} of your {had}."
    if item:
        missed = " and missed the little coin you carry" if purse else ""
        return f"{robber.name} took {item}{missed}."
    return f"{robber.name} went through your pockets and found nothing worth taking."


def hideout_name(robber) -> str:
    """Where a robber goes to ground, by their own name: "the robber's hideout"."""
    return f"{robber.name}'s hideout"[:60]


def open_the_quest(scene, robber, gang, took: dict, before_cp: int, thing, where: str,
                   landmark: str, coins=None, *, here_name: str = "", turn: int = 0):
    """The quest to get it back, on the one quest store, and where the robbers went
    as a place heard of (`heard_places`), so the place doors can make it real."""
    from . import cards as cards_mod
    from . import heard_places

    names = _names(gang)
    title = f"Get back what {names} took"
    if len(title) > 80:
        title = f"Get back what {robber.name} took"
    hideout = hideout_name(robber)
    at_here = f"at {here_name}" if here_name else "where you fell"
    off_here = f"off {here_name}" if here_name else "near where you fell"
    heard_places.record(scene, {"name": hideout, "kind": "", "landmark": landmark},
                        said_by="", line=f"where {names} made off to", turn=turn)
    took_cp = goods.in_copper(took)
    said = goods.purse_line(took, coins) if took else ""
    objectives: list[str] = []
    index: dict[str, int] = {}
    if thing:
        index["item"] = len(objectives)
        objectives.append(f"Get your {thing['name']} back from {robber.name}")
    if took_cp:
        index["coin"] = len(objectives)
        objectives.append(f"Get back the {said} {robber.name} took")
    holding_line = " and ".join(x for x in (said, f"your {thing['name']}" if thing else "") if x)
    facts = [_upper_first(f"{names} beat you down {at_here} and robbed you."),
             _upper_first(f"{robber.name} has {holding_line}."),
             (f"They made off together, to {hideout}, somewhere {off_here}."
              if len(gang) > 1 else
              _upper_first(f"{robber.name} made off to {hideout}, somewhere {off_here}."))]
    card = cards_mod.open_quest(
        scene, title=title, objectives=objectives, giver="", reward="",
        facts=facts, people=[a.ref for a in gang], place=landmark,
        origin=QUEST_ORIGIN, turn=turn)
    card.recover = {
        "robber": robber.ref, "robber_name": robber.name,
        "gang": [a.ref for a in gang], "where": where, "hideout": hideout,
        "landmark": landmark, "location": str(getattr(scene, "location_id", "") or ""),
        "coin": dict(took), "coin_cp": took_cp, "robber_cp_before": int(before_cp),
        # In the words the robbery was told in: the world's coin is named by the place
        # (`goods.coinage`), and a later tick asked without one called the same coin by
        # another town's name — "22 Ashgate gold pieces" for the "22 Kragmoor" taken.
        "coin_said": said,
        "coin_back": not took_cp,
        "item": ({k: thing[k] for k in ("store", "key", "name", "count", "robber_before",
                                        "pc_left", "prop") if k in thing}
                 if thing else {}),
        "item_back": not thing, "objectives": index,
    }
    cards_mod._store(scene, card)
    return card


# --- the way back ------------------------------------------------------------------------

def _walk_in(scene, rec: dict) -> None:
    """Once the hideout is a place, the robbers are in it. Somebody founded it — the
    player going there, through `judgement.go_to_heard_place` — so the people who went
    to ground there are there to be found, not still nowhere."""
    want = str(rec.get("hideout") or "").lower()
    if not want:
        return
    place = next((p for p in getattr(scene, "founded", None) or ()
                  if str(p.get("name") or "").lower() == want), None)
    if place is None:
        return
    for ref in rec.get("gang") or ():
        who = scene.people.get(ref)
        if who is not None and who.at == rec.get("where"):
            scene.move(ref, place["id"])


def _own_again(scene, pc, item: dict) -> None:
    """The props ledger stops calling it stolen: it is in its owner's hands again."""
    name = str(item.get("prop") or "").lower()
    for rec in getattr(scene, "props", None) or ():
        if str(rec.get("name", "")).lower() == name:
            rec.pop("at", None)
            rec.pop("square", None)
            rec["held_by"] = pc.ref
            rec["owner"] = pc.ref
            rec.pop("stolen", None)


def settle(engine) -> list:
    """Every robbery quest measured against the holdings, once a batch: the robbers
    walked into their hideout if it has become a place, and each objective ticked when
    what was taken is back. Returns the outcomes, one per quest that moved.

    Measured on the holdings, never on the means: a looted body, a payment, a word or a
    theft all end with the robber not holding it and the player holding it. A robber who
    has left the campaign altogether cannot be asked about the coin, so that objective
    waits rather than ticking on an absence."""
    from . import cards as cards_mod
    from .engine import Outcome

    scene = engine.scene
    pc = scene.pc()
    if pc is None:
        return []
    out = []
    for card in cards_mod.quests(scene):
        rec = card.recover
        if not rec or not card.live:
            continue
        _walk_in(scene, rec)
        robber = scene.people.get(str(rec.get("robber") or ""))
        said: list[str] = []
        effects: list[dict] = []
        index = rec.get("objectives") or {}
        after = card
        item = rec.get("item") or {}
        if item and not rec.get("item_back"):
            if (holds(robber, item) <= int(item.get("robber_before", 0))
                    and holds(pc, item) > int(item.get("pc_left", 0))):
                rec["item_back"] = True
                _own_again(scene, pc, item)
                said.append(f"You have your {item['name']} back.")
                if "item" in index:
                    after = cards_mod.objective_done(scene, card.id, int(index["item"]),
                                                     turn=0) or after
                    effects.append({"kind": "quest_step", "id": card.id,
                                    "objective": int(index["item"]) + 1,
                                    "finished": after.stage == "resolved"})
        if rec.get("coin_cp") and not rec.get("coin_back") and robber is not None:
            if goods.in_copper(robber.purse) <= int(rec.get("robber_cp_before", 0)):
                rec["coin_back"] = True
                money = rec.get("coin_said") or goods.purse_line(rec.get("coin") or {})
                said.append(f"{rec.get('robber_name', 'the robber')} no longer has your "
                            f"{money}.")
                if "coin" in index:
                    after = cards_mod.objective_done(scene, card.id, int(index["coin"]),
                                                     turn=0) or after
                    effects.append({"kind": "quest_step", "id": card.id,
                                    "objective": int(index["coin"]) + 1,
                                    "finished": after.stage == "resolved"})
        if not said:
            continue
        # The record rides on the card; write it back beside the ticked objectives.
        fresh = cards_mod.find(scene, card.id)
        if fresh is not None:
            fresh.recover = rec
            cards_mod._store(scene, fresh)
            after = fresh
        tell = " ".join(_upper_first(x) for x in said)
        if after.stage == "resolved":
            line = engine.award_story("new", after.title).strip()
            tell += f" {after.title} is finished." + (f" {line}" if line else "")
        for e in effects:
            e["origin"] = QUEST_ORIGIN
        out.append(Outcome(intent_id="", op="quest_step", effects=effects, tell=tell,
                           because="what was taken is back"))
    return out


def _offstage(scene) -> str:
    from . import places as places_mod
    from . import residency

    town = places_mod.location_of(getattr(scene, "at", "") or "") or scene.location_id
    return residency.offstage(town, OFFSTAGE_LEAF)


def _upper_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text
