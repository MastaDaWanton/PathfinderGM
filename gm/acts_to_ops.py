"""The act→op table: what the reading of the player's sentence commits the engine to.

docs/structured-turn.md, lane F. The owner, 2026-10-03: "we cant really depend i think on
just layering mechanical detection logic on top this will be an endless loop". Every live
bug of that day on the forward side was a regex misreading a sentence the reader
(gm/interpret.py) had read correctly — "…, then tip the coins", a quoted "It's a deal",
"pick the crate back up" — and each fix taught one more regex one more phrasing.

So the reading drives the ops. A model reads; this module validates the reading against
what the engine owns and builds the ops; the engine changes state. It never reads English:
every slot is resolved through the engine's own finders, or it is not resolved at all.

  * people: `scope.in_the_room` (the phrase against the names of who is here); a bare
    pronoun is the one the player is engaged with, talking to, or the only other person
    here — the engine's state, never a guess at the words;
  * things: `holding.key_in` against the pack, the stock shelf by id, base or name, and
    a container by `holding.is_container` (a closed list of nouns, the engine's own);
  * coin: `holding.is_money`, and an amount as a number and a denomination
    (`goods.coin_named`): numbers and a closed vocabulary, which code may check;
  * places: `places.find`, and a heard-of place through `heard_places.named_in`.

Two kinds of row. Most acts owe an op the planner writes the params of (a `travel` to one
of this town's real places, a `say`, a `provoke`): those are op NAMES, joined to the
plan's required `declared` block. The acts that move a thing — take, drop, give, sell,
offer — are built here WHOLE, because their params are exactly what the regexes kept
getting wrong (which way the coin goes, who the buyer is, whether a deal was closed) and
the reading's slots plus the engine's finders settle each of them.

Where a slot cannot be resolved, no op is invented: the row says what was not found, and
the turn says so (`refusal`, and the brief's fact line). Prior art: FIREBALL (Zhu et al.,
ACL 2023) — utterance to executable command, with the state in front of it; Wordplay
2024's function-calling GM; "Orchestrated Reality"'s Plan–Diff–Validate–Apply, where a
proposal that fails a check is refused before it commits. TADS 3's verb templates give
the slots each verb takes (`interpret.ACT_SLOTS`); TakeFrom's indirect object is the
holder, person or container alike.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# The acts whose ops are built here, whole.
GOODS_ACTS = frozenset({"take", "drop", "give", "sell", "offer"})
# The acts under which coin leaves the player's purse. `rest` because a room is paid for
# ("I take a room for the night": the act list's own words for `rest`).
PAYING_ACTS = frozenset({"give", "buy", "drop", "rest"})

_PRONOUNS = frozenset({"him", "her", "them", "he", "she", "they", "his", "their"})
_IT = frozenset({"it", "them", "these", "those", "this", "that"})
_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
            "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
            "fifty": 50, "hundred": 100}
_AMOUNT = re.compile(r"^\s*(?:the\s+)?(\d+|" + "|".join(_NUMBERS) + r")\s+(.+?)\s*$", re.I)
# The player's own figure for a sale, as a share of the worth: "at 75% of the crate's
# value". A number, so code may read it; it only ever LOWERS the engine's price
# (`Engine._sell_goods`, `accept`).
_SHARE = re.compile(r"\b(\d{1,3})\s*(?:%|per\s*cent|percent)", re.I)


@dataclass
class Row:
    """One action of the reading, as the engine will carry it."""
    index: int
    act: str
    ops: list[str] = field(default_factory=list)       # op names the plan must carry
    intents: list[dict] = field(default_factory=list)  # ops built here, whole
    missing: str = ""                                   # what the words named and is not here
    note: str = ""                                      # why nothing was built, for the log

    def record(self) -> dict:
        out = {"act": self.act, "ops": list(self.ops)}
        if self.intents:
            out["built"] = [{"op": i["op"], "params": dict(i.get("params") or {})}
                            for i in self.intents]
        if self.missing:
            out["missing"] = self.missing
        if self.note:
            out["note"] = self.note
        return out


# --- finding things the engine owns ---------------------------------------------------------

def _plain(words) -> str:
    from rules import holding

    return holding.plain(words)


def addressed(scene) -> str:
    """The one person the player is dealing with, by the engine's state: engaged with,
    then in conversation (`state.talking`), then the only other person standing here.
    "" when that is not one person."""
    from rules import states as states_mod

    from . import judgement

    actors = getattr(scene, "actors", {}) or {}
    engaged = judgement.engaged_refs(scene)
    if len(engaged) == 1:
        return engaged[0]
    talking = [r for r, a in actors.items() if not a.is_pc and not a.is_down
               and a.has_state(states_mod.TALKING)]
    if len(talking) == 1:
        return talking[0]
    others = [r for r, a in actors.items() if not a.is_pc and not a.is_down]
    return others[0] if len(others) == 1 else ""


def person(scene, words) -> str:
    """The ref of the person here the slot names; a bare pronoun is `addressed`."""
    from rules import scope

    said = " ".join(str(words or "").split())
    if not said or scene is None:
        return ""
    if said.lower() in _PRONOUNS:
        return addressed(scene)
    ref = scope.in_the_room(scene, said)
    actor = (getattr(scene, "actors", {}) or {}).get(ref)
    if actor is None or actor.is_pc:
        return ""
    return ref


def coin_amount(words) -> tuple[str, int] | None:
    """("gp", 10) for "ten gold", "10 gp", "three silver pieces"; None otherwise."""
    from rules import goods

    m = _AMOUNT.match(str(words or ""))
    if not m:
        return None
    denom = goods.coin_named(m.group(2))
    if not denom:
        return None
    n = m.group(1).lower()
    return denom, (int(n) if n.isdigit() else _NUMBERS.get(n, 1))


def _is_coin(words) -> bool:
    from rules import goods, holding

    return holding.is_money(words) or bool(goods.coin_named(str(words or "")))


def _stock_id(pc, words) -> str:
    """The id of the jar on the player's shelf the words name, exact by id, base or name
    — `consumables.resolve_stock` guesses by content words, and a sale by guess sells the
    wrong jar."""
    from rules import holding

    for sid, item in (getattr(pc, "stock", {}) or {}).items():
        for name in (getattr(item, "name", ""), getattr(item, "base", ""),
                     str(sid).split("#")[0].replace("-", " "), sid):
            if name and holding.same(name, words):
                return sid
    return ""


def _carried(pc, words) -> str:
    """The pack's key for the thing, or the stock jar's id; "" when the player has none."""
    from rules import holding

    return holding.key_in(getattr(pc, "goods", {}) or {}, words) or _stock_id(pc, words)


def _a_thing(words) -> bool:
    from . import judgement

    return judgement._is_a_thing(words)


def _object(frame, i: int) -> str:
    """The action's object; "it" and its kin are the object of the deed before it in the
    same sentence ("I lift the lantern off the hook, then hand it to the boy") — the
    frame's own structure, and nothing when there is none."""
    acts = frame.get("actions") or []
    said = " ".join(str(acts[i].get("object") or "").split())
    if said.lower() in _IT:
        for prev in reversed(acts[:i]):
            if prev.get("object") and str(prev["object"]).lower() not in _IT:
                return " ".join(str(prev["object"]).split())
        return ""
    return said


# --- the rows -------------------------------------------------------------------------------

def _take(row: Row, frame, i, scene, pc) -> None:
    from rules import holding

    a = frame["actions"][i]
    thing = _object(frame, i)
    if not thing:
        row.note = "nothing named to take"
        return
    coin = _is_coin(thing)
    if not coin and not _a_thing(thing):
        row.note = f"{thing!r} is not a thing to carry"
        return
    source = " ".join(str(a.get("target") or "").split())
    params: dict = {"item": _plain(thing) or thing, "to": pc.ref}
    if source and holding.is_container(source):
        params["from_"] = _plain(source)
    elif source:
        who = person(scene, source)
        if who:
            params["from_"] = who
    if not coin and "from_" not in params and holding.key_in(pc.goods, thing):
        # Carrying what is already carried: "I take the crate to the counting house"
        # (2026-10-03, turn 73: a second crate came out of the air).
        row.note = f"{thing} is already carried"
        return
    row.intents.append({"op": "give", "actor": pc.ref, "params": params,
                        "because": "the player took it"})


def _drop(row: Row, frame, i, scene, pc) -> None:
    thing = _object(frame, i)
    if not thing:
        row.note = "nothing named to set down"
        return
    key = _carried(pc, thing)
    if not key and not _is_coin(thing):
        row.missing = f"{pc.name} is not carrying {thing}"
        return
    row.intents.append({"op": "give", "actor": pc.ref,
                        "params": {"item": key or _plain(thing), "from_": pc.ref},
                        "because": "the player set it down"})


def _give(row: Row, frame, i, scene, pc) -> None:
    a = frame["actions"][i]
    thing = _object(frame, i)
    if not thing:
        row.note = "nothing named to hand over"
        return
    amount = coin_amount(thing)
    key = _carried(pc, thing)
    if not (amount or key or _is_coin(thing)):
        if not _a_thing(thing):
            row.note = f"{thing!r} is not a thing to hand over"
        else:
            # "I buy the old soldier a pint": nothing in the pack to hand over, and the
            # pint is the bar's to pour. Said, never minted.
            row.missing = f"{pc.name} is not carrying {thing}"
        return
    to_words = " ".join(str(a.get("target") or "").split())
    to = person(scene, to_words) if to_words else ""
    if not to:
        row.missing = (f"there is nobody here who is {to_words}" if to_words
                       else f"nobody was named to give {thing} to")
        return
    if amount:
        params = {"item": amount[0], "count": amount[1], "from_": pc.ref, "to": to}
    else:
        params = {"item": key or _plain(thing), "from_": pc.ref, "to": to}
    row.intents.append({"op": "give", "actor": pc.ref, "params": params,
                        "because": "the player handed it over"})


def _sell(row: Row, frame, i, scene, pc, sentence: str) -> None:
    from rules import keepers as keepers_mod
    from rules import pricing

    a = frame["actions"][i]
    thing = _object(frame, i)
    key = _carried(pc, thing) if thing else ""
    if not key:
        row.missing = (f"{pc.name} is not carrying {thing}" if thing
                       else "nothing was named to sell")
        return
    buyer_words = " ".join(str(a.get("target") or "").split())
    buyer = person(scene, buyer_words) if buyer_words else addressed(scene)
    if not buyer:
        row.missing = (f"there is nobody here who is {buyer_words}" if buyer_words
                       else f"nobody here to sell {thing} to")
        return
    if row.act == "offer" and not keepers_mod.keeps_a_counter(scene.actors[buyer]):
        # A stall buys whatever it is offered (CircleMUD's shopkeeper buys what its trade
        # takes); anybody else has to agree, and until the player closes it the offer is
        # a haggle the fiction answers.
        row.note = "an offer, not a sale: no counter here, so the buyer must agree first"
        return
    params: dict = {"item": key, "to": buyer}
    share = _SHARE.search(str(sentence or ""))
    if share and key in (pc.goods or {}):
        params["accept"] = round(int(share.group(1)) / 100 * pricing.goods_worth(key), 2)
    row.intents.append({"op": "sell", "actor": pc.ref, "params": params,
                        "because": "the player sold it"})


def table(frame: dict | None, scene, *, places=(), sentence: str = "") -> list[Row]:
    """The rows the reading makes, one per action, in the order the words do them."""
    from . import interpret

    rows: list[Row] = []
    if not frame or frame.get("error") or scene is None:
        return rows
    if frame.get("question") and not frame.get("actions"):
        return rows
    pc = scene.pc() if hasattr(scene, "pc") else None
    for i, a in enumerate(frame.get("actions") or []):
        act = str(a.get("act") or "")
        row = Row(index=i, act=act)
        if act in GOODS_ACTS and pc is not None:
            if act == "take":
                _take(row, frame, i, scene, pc)
            elif act == "drop":
                _drop(row, frame, i, scene, pc)
            elif act == "give":
                _give(row, frame, i, scene, pc)
            else:
                _sell(row, frame, i, scene, pc, sentence)
        else:
            # The op names: one action at a time through the reading's own op map, so each
            # op is owed by the action that declared it.
            row.ops = interpret.ops_for({"actions": [a]}, scene, places)
        rows.append(row)
    return rows


def declared(rows: list[Row]) -> list[str]:
    """The op names the plan must carry, in the order the words do them — the `declared`
    block's keys (`prompts.turn_schema`). Ops built whole are not asked of the model."""
    return list(dict.fromkeys(op for r in rows for op in r.ops))


def built_ops(rows: list[Row]) -> list[str]:
    return list(dict.fromkeys(i["op"] for r in rows for i in r.intents))


def unresolved(rows: list[Row]) -> list[str]:
    return [r.missing for r in rows if r.missing]


def refusal(rows: list[Row]) -> str:
    """The turn's whole answer when every deed the words declared moves a thing and not
    one of them can: "Kesst Vayr is not carrying a crate." Nothing is planned, nothing is
    invented, and the player is told what was not found. "" when anything else is owed."""
    if not rows or any(r.act not in GOODS_ACTS or r.intents or r.ops for r in rows):
        return ""
    missing = unresolved(rows)
    if not missing or any(not r.missing for r in rows):
        return ""
    return " ".join(m[0].upper() + m[1:] + "." for m in missing)


# --- the reading confirms the plan, or overrules it ------------------------------------------

def _op(r) -> str:
    return str((r or {}).get("op", "")).lower() if isinstance(r, dict) else ""


def _same_thing(a, b) -> bool:
    from rules import holding

    if _is_coin(a) and _is_coin(b):
        return True
    return holding.same(a, b)


def _to_player(p: dict, pc) -> bool:
    to = str(p.get("to") or "").strip().lower()
    frm = str(p.get("from_") or p.get("from") or "").strip().lower()
    return to in (pc.ref, "pc", "you", "player") or not (to or frm)


def apply(raw, rows: list[Row], frame: dict | None, scene, *, notes: list | None = None) -> list:
    """The plan, with the reading's goods ops in it.

    1. A plan op that moves the same thing as a built one is replaced by it, wherever it
       stood: the reading settles which way the thing goes and to whom ("the coins from
       the pouch into my coin purse" is coin IN; the model's coin give was a payment OUT).
    2. A plan op that moves a thing and that no act of the reading stands behind is
       overruled: a give to the player needs an act that gets something, a give from the
       player one that parts with something, and a sale needs `sell` — an `offer` is a sale
       only where the table built one. Gives between other people are theirs.
    3. Built ops the plan did not carry are added.

    Only with a reading: with none there is nothing to stand behind or overrule with, and
    the plan stands alone (`GMAgent.plan_turn`)."""
    from . import interpret

    if not isinstance(raw, list) or not frame or frame.get("error") or scene is None:
        return raw
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None:
        return raw
    built = [i for r in rows for i in r.intents]
    acts = {str(a.get("act") or "") for a in frame.get("actions") or []}
    out: list = []
    placed: set[int] = set()
    for r in raw:
        op = _op(r)
        if op not in ("give", "sell"):
            out.append(r)
            continue
        p = r.get("params") or {}
        actor = str(r.get("actor") or "")
        mine = actor in ("", "pc", pc.ref, "None") or str(p.get("from_") or "") == pc.ref \
            or _to_player(p, pc)
        if not mine:
            out.append(r)                        # between other people: theirs
            continue
        twin = next((k for k, b in enumerate(built)
                     if _same_thing(p.get("item"), b["params"].get("item"))), None)
        if twin is not None:
            if twin not in placed:
                placed.add(twin)
                out.append(built[twin])
            if notes is not None:
                notes.append(f"the reading's {built[twin]['op']} of "
                             f"{built[twin]['params'].get('item')} in place of the plan's "
                             f"{op} of {p.get('item')}")
            continue
        if op == "sell":
            stands = "sell" in acts
        elif _to_player(p, pc):
            stands = bool(acts & interpret.GETTING_ACTS)
        elif _is_coin(p.get("item")):
            # Coin out of the purse is a payment, and only paying pays: measured on the
            # table's first run, "It's a deal. You can have the crate." kept the plan's
            # `give gp 1 from pc` beside the sale — the seller paying the buyer.
            stands = bool(acts & PAYING_ACTS)
        else:
            stands = bool(acts & interpret.PARTING_ACTS)
        if not stands:
            if notes is not None:
                notes.append(f"the plan's {op} of {p.get('item')!r}: no act of the "
                             f"reading stands behind it, dropped")
            continue
        out.append(r)
    for k, b in enumerate(built):
        if k not in placed:
            out.append(b)
    return out or [{"op": "narrate_only", "because": "nothing the reading stands behind"}]


def order(raw, rows: list[Row]) -> list:
    """The plan's ops in the order the words do them.

    Each op owed by exactly one action of the reading (a built op by its row, a named op
    by the row that names it) is put back in that action's order; every other op keeps
    its place. Inform's DM4 §34 and adv3Lite parse and run one action at a time, because
    what the second means depends on where the first left the player: "I pick up the
    crate, then go to the market" carries the crate there, and the other way round leaves
    it behind."""
    if not isinstance(raw, list) or not rows:
        return raw
    by_built = {id(i): r.index for r in rows for i in r.intents}
    owners: dict[str, list[int]] = {}
    for r in rows:
        for op in r.ops:
            owners.setdefault(op, []).append(r.index)
    slots, keyed = [], []
    for k, r in enumerate(raw):
        idx = by_built.get(id(r))
        if idx is None and len(owners.get(_op(r), ())) == 1:
            idx = owners[_op(r)][0]
        if idx is not None:
            slots.append(k)
            keyed.append((idx, k, r))
    if len(keyed) < 2:
        return raw
    keyed.sort(key=lambda t: (t[0], t[1]))
    out = list(raw)
    for at, (_, _, r) in zip(slots, keyed):
        out[at] = r
    return out
