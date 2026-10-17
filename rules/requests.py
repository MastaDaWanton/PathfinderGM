"""Asking somebody for something, by the book: Diplomacy's Make Request.

Measured 2026-10-16 on a real player's game (0.2.19, the free narrator): after helping a
carter free a wheel, "…then I ask for fair compensation for helping" was read as two
`talk` acts, the engine resolved a `say`, nothing was rolled — and the narrator, given no
answer to the request, invented one: the carter's hand went into a pouch and a coin came
out. The next turn "I take the coin" was a `give` from nobody, and the engine minted a
copper piece to match the prose. The owner: she "should have rolled diplomacy when
speaking about payment".

**The rule, from the Core Rulebook p.93 (Diplomacy), and only the rule:**

  "If a creature's attitude toward you is at least indifferent, you can make requests of
  the creature. This is an additional Diplomacy check, using the creature's current
  attitude to determine the base DC, with one of the following modifiers." The base DCs
  are Influence Attitude's — 25/20/15/10/0, hostile to helpful, plus the creature's
  Charisma modifier (`attitude.influence_dc`, the same reader the sway path uses).
  Request modifiers: simple advice or directions -5, detailed advice +0, simple aid +0,
  an unimportant secret +5, lengthy or complicated aid +5, dangerous aid +10, an
  important secret +10 or more, aid that could result in punishment +15 or more, and
  **additional requests +5 per request**. "If a request is refused, the result does not
  change with additional checks, although other requests might be made."

Asking for directions or advice is not a request here: the owner's line is that a plain
question ("where should I stay?") rolls nothing, and the book's -5 row exists for a GM
who wants to roll it anyway. So the reader's `request` act (gm/interpret.py) carries
only the two things a person can be asked to GIVE — payment and a favour — and both are
the book's "give simple aid", +0. The +5/+10/+15 rows need a judgement of how dangerous
or long the aid is that nothing in the engine holds; they are named here, unused, rather
than guessed by a model (law 3: no model authors a number).

**What a successful request for payment pays.** The book prices labour in exactly one
place: Hireling, untrained — "a crier, laborer, maid, mourner, porter, or other menial
worker" — 1 sp per day, "generally 7–10 hours of work per day" (Core Rulebook p.159;
Ultimate Equipment p.99). Hired for any part of a day, a labourer is paid the day: the
book names no shorter engagement. So a payment request that succeeds pays one day's
untrained wage per day of work, out of what the person actually carries
(`bestiary.collapse_kit` turns their kit's wealth into a real purse the first time it is
looked at). The engine does not know how long the help took — no op records a job's
length — so the work is one day's engagement until something does. A person with less
than the wage on them pays what they have; one with nothing pays nothing, and the tell
says so.

**What it remembers, and where.** One `ActiveEffect` on the person asked (law 2), key
`requests`, tagged `bond.requests`: how many requests they have heard today (the +5
each), which kinds they refused (refused stays refused), and whether they have paid —
for a day from the first request, the book's own clock for social checks
(`attitude.COOLDOWN_MINUTES`). Held until dismissed with the day's first minute in its
payload, as `Scene.swayed` holds the influence limit, rather than on a round clock: an
effect that runs out on the clock is reported by `tick_effects`, and "the carter: asked
a favour today" ending would reach the narrator as news a day later. A stale day reads
as no memory at all, and the next request replaces it.
"""
from __future__ import annotations

from . import states

# The two kinds of request the reader can name (`interpret.REQUESTS`). A closed list, the
# engine's own; anything the reader cannot place in it stays talk.
PAYMENT = "payment"
FAVOUR = "favour"
KINDS = (PAYMENT, FAVOUR)

# Core Rulebook p.93, the request modifiers, by the book's own words. Only "simple aid"
# is used: payment and a favour are both aid the person can simply give.
MODIFIERS = {
    "simple advice or directions": -5,
    "detailed advice": 0,
    "simple aid": 0,
    "unimportant secret": 5,
    "lengthy or complicated aid": 5,
    "dangerous aid": 10,
    "important secret": 10,
    "aid that could result in punishment": 15,
}
ROW_FOR = {PAYMENT: "simple aid", FAVOUR: "simple aid"}
# "Additional requests: +5 per request."
PER_ADDITIONAL = 5

# Core Rulebook p.159: Hireling, untrained, 1 sp per day (10 cp).
WAGE_CP_PER_DAY = 10
WAGE_WHAT = "a labourer's day wage"

# "If a creature's attitude toward you is at least indifferent, you can make requests."
LEAST_ATTITUDE = "indifferent"

KEY = "requests"
TAG = states.REQUESTS
SOURCE = "request"
# How long a person remembers being asked, in minutes (`attitude.COOLDOWN_MINUTES`).
DAY_MINUTES = 24 * 60


def kind_of(value) -> str:
    """The request kind a param names, or "" for anything outside the closed list."""
    v = str(value or "").strip().lower()
    return v if v in KINDS else ""


def _record(actor):
    for e in getattr(actor, "effects", None) or ():
        if getattr(e, "key", "") == KEY and TAG in (getattr(e, "tags", ()) or ()):
            return e
    return None


def memory(actor, now: int) -> dict:
    """What this person remembers being asked in the day up to `now` (the scene's clock
    minute): {"since", "asked", "refused", "paid_cp"}. Nothing when nobody has asked them
    anything, or the day has run out."""
    e = _record(actor)
    p = dict(getattr(e, "payload", None) or {}) if e is not None else {}
    since = int(p.get("since", now) or 0)
    if not p or int(now) - since >= DAY_MINUTES or int(now) < since:
        return {"since": int(now), "asked": 0, "refused": [], "paid_cp": 0}
    return {"since": since, "asked": int(p.get("asked", 0) or 0),
            "refused": [str(k) for k in p.get("refused") or ()],
            "paid_cp": int(p.get("paid_cp", 0) or 0)}


def remember(actor, now: int, *, kind: str, granted: bool, paid_cp: int = 0) -> dict:
    """The one writer: one more request heard, and a refusal or a payment kept. Replaces
    the effect whole, keeping the minute the day began, and returns the new memory."""
    from .activeeffect import ActiveEffect

    was = memory(actor, now)
    refused = list(was["refused"])
    if not granted and kind not in refused:
        refused.append(kind)
    payload = {"since": was["since"], "asked": was["asked"] + 1, "refused": refused,
               "paid_cp": was["paid_cp"] + max(0, int(paid_cp))}
    actor.remove_effects(source=SOURCE)
    actor.apply_effect(ActiveEffect(
        name="asked a favour today", kind="bond", key=KEY, source=SOURCE,
        origin="rule:diplomacy-request", duration="until-dismissed", tags=(TAG,),
        payload=payload))
    return payload


def dc(target, kind: str, now: int) -> tuple[int, str]:
    """(the DC, where it came from in the book's terms): the attitude's base DC plus the
    creature's Charisma (`attitude.influence_dc`), the request's row, and +5 for every
    request they have already heard today."""
    from . import attitude

    base = attitude.influence_dc(target)
    row = ROW_FOR.get(kind, "simple aid")
    asked = memory(target, now)["asked"]
    extra = PER_ADDITIONAL * asked
    value = base + MODIFIERS[row] + extra
    basis = f"request ({row} {MODIFIERS[row]:+d}); {attitude.dc_basis(target, 'diplomacy')}"
    if extra:
        basis += f"; {asked} earlier request{'s' if asked != 1 else ''} {extra:+d}"
    return value, basis


def refusal(target, kind: str, now: int) -> str:
    """Why this request is not even rolled, in plain words, or "".

    * Worse than indifferent: the book allows no requests at all.
    * The same kind already refused today: "the result does not change".
    * Payment already made today: the work has been paid for."""
    from . import attitude

    step = attitude.of(target)
    if attitude.step_of(step) < attitude.step_of(LEAST_ATTITUDE):
        return (f"{target.name} is {step} towards you and will do you no favours: "
                f"they will not even hear the request. Change how they feel first.")
    mem = memory(target, now)
    if kind in mem["refused"]:
        return (f"{target.name} has already said no to that today, and asking again will "
                f"not change the answer.")
    if kind == PAYMENT and mem["paid_cp"] > 0:
        return f"{target.name} has already paid you today. Nothing more changes hands."
    return ""


def wage_cp(days: int = 1) -> int:
    """The untrained hireling's wage for `days` days of work (CRB p.159)."""
    return WAGE_CP_PER_DAY * max(1, int(days))


# --- what somebody who sells is asked for is bought, not begged -------------------------
#
# The coordinator's review, 2026-10-16: "ask for a room" at an inn, "ask for a mug of ale",
# "ask the smith for a sword" are purchases, and a Diplomacy favour for them would let a
# good roll take the goods for nothing. CircleMUD's shopkeeper answers "list" and "buy"
# from its own shop file, never a social roll; here the same split is made in code from
# what the engine already holds: who keeps a counter (`keepers.keeps_a_counter`), who
# keeps a place that lets beds (`schemes.PLACE_KINDS["lodging"]`), and what is priced —
# their own shelf (`goods.goods_at`, the trade panel's) and, at a counter, the whole
# catalogue the outfit page sells (`goods.catalogue_ids`), matched with the counter's own
# matcher (`goods.match_want`: every word of the want in a row's name). Nothing reads the
# player's English for intent: a want that names no priced row stays a request.

# The Core Rulebook's "Inn stay" service (CRB p.159: common 5 sp — the price
# `cards.BED_PRICE_CP` already uses), as a row the counter matcher can find. Named so its
# words cover how a bed is asked for ("a room", "a bed for the night", "lodging"). A
# service, not a good: it is never put on a shelf, so no counter sells it as an item.
INN_STAY = "service:inn-stay"
_INN_STAY_NAME = "a room or a bed for the night, lodging (inn stay)"


def _lodging_kinds() -> frozenset[str]:
    # One list of where beds are let, shared with the rest door that charges for them
    # (`rules/lodging.py`).
    from . import lodging

    return lodging.kinds()


def sells(scene, actor) -> str:
    """The counter kind this person sells across, or "" for somebody who sells nothing:
    a market counter's `market:<id>`, the trade place they keep and stand in, or the
    inn or tavern they keep. The same facts the trade panel opens on."""
    from . import keepers, market

    wid = str(getattr(actor, "world_entity_id", "") or "")
    place = keepers.place_of(wid)
    if not place or str(getattr(actor, "at", "") or "") != place:
        return ""
    cid = keepers.counter_of(wid)
    if cid:
        return market.COUNTER_PREFIX + cid
    kind = keepers.kind_of(place, getattr(scene, "founded", None) or ())
    if keepers.keeps_a_counter(actor) or kind in _lodging_kinds():
        return kind
    return ""


def offered(scene, actor, want: str):
    """What of theirs the words ask for — ("goods", the row) for something priced they
    sell, ("lodging", None) for a bed at an inn or tavern — or None when the want names
    nothing they offer (pay, a reward, a blessing, a hand with the anvil)."""
    from . import goods

    kind = sells(scene, actor)
    if not kind or not str(want or "").strip():
        return None
    if kind in _lodging_kinds():
        found, _ = goods.match_want(want, [{"id": INN_STAY, "name": _INN_STAY_NAME}])
        if found is not None:
            return "lodging", None
    rows = list(goods.goods_at(kind))
    if kind not in _lodging_kinds():
        # At a counter, anything the catalogue prices is asked for as a purchase, stocked
        # here or not: the counter's own screen says "I don't have that" (`match_want`'s
        # CircleMUD answer), which a favour roll never would.
        held = {str(getattr(g, "id", "")) for g in rows}
        rows += [g for t in ("weapons", "armour", "shields") for g in goods.table_goods(t)
                 if str(getattr(g, "id", "")) not in held]
        rows += [g for g in (goods.good(k) for k in goods.GEAR)
                 if g is not None and g.id not in held]
    found, _ = goods.match_want(want, rows)
    return ("goods", found) if found is not None else None
