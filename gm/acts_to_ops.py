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
plan's required `declared` block. The acts that move a thing — take, drop, give, sell —
are built here WHOLE, because their params are exactly what the regexes kept getting wrong
(which way the coin goes, who the buyer is, whether a deal was closed) and the reading's
slots plus the engine's finders settle each of them.

Only what is done or tried NOW moves the engine (`interpret.COMMITS`, round 2): an action
the reading marks intended or asked about makes no row of ops at all. A sale tried is an
offer — ISO 24617-2's Offer, which only an Accept Offer closes — and is never a sale, at a
counter or anywhere else: only an agreement closes it.

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
GOODS_ACTS = frozenset({"take", "drop", "give", "sell", "steal"})
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
    thing: str = ""                                     # a goods row's object, resolved
    commit: str = "done"                                # interpret.COMMITS

    def record(self) -> dict:
        out = {"act": self.act, "ops": list(self.ops)}
        if self.commit != "done":
            out["commit"] = self.commit
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


_FORMS = {"he": {"he", "him", "his"}, "him": {"he", "him", "his"},
          "she": {"she", "her", "hers"}, "her": {"she", "her", "hers"},
          "they": {"they", "them", "their"}, "them": {"they", "them", "their"}}


def _pronoun_forms(pronouns) -> set[str]:
    out: set[str] = set()
    for p in str(pronouns or "").lower().split("/"):
        out |= _FORMS.get(p.strip(), set())
    return out


def person(scene, words) -> str:
    """The ref of the person here the slot names; a bare pronoun is `addressed`."""
    from rules import scope

    said = " ".join(str(words or "").split())
    if not said or scene is None:
        return ""
    if said.lower() in _PRONOUNS:
        # The pronoun against the pronouns the engine holds for each person here (the
        # sheet's `pronouns`, a closed vocabulary): "I toss her five silver" with a woman
        # and the challenger in the ring is the woman. Else the one the player is dealing
        # with.
        fits = [r for r, a in (getattr(scene, "actors", {}) or {}).items()
                if not a.is_pc and not a.is_down
                and said.lower() in _pronoun_forms(getattr(a, "pronouns", ""))]
        return fits[0] if len(fits) == 1 else addressed(scene)
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


def _carried(pc, words, coming=()) -> str:
    """The pack's key for the thing, or the stock jar's id; "" when the player has none.
    `coming` is what an earlier deed of the same sentence picks up: "I lift the lantern off
    the hook, then hand it to the boy" hands over a lantern the pack does not hold YET —
    one action at a time, each against the state the last one leaves (Inform's DM4 §34)."""
    from rules import holding

    return (holding.key_in(getattr(pc, "goods", {}) or {}, words) or _stock_id(pc, words)
            or next((c for c in coming if holding.same(c, words)), ""))


def _a_thing(words) -> bool:
    from . import judgement

    return judgement._is_a_thing(words)


def _object(frame, i: int, pc=None, recent=()) -> str:
    """The action's object; "it" and its kin are the object of the deed before it in the
    same sentence ("I lift the lantern off the hook, then hand it to the boy") — the
    frame's own structure. With none there, the one thing in the pack the last few beats
    name, longest name first: "It's a deal, he can have it" after "The clerk eyes the
    crate". The pack is a closed vocabulary, matched whole-word, as a spell's name is
    matched against the catalogue (`judgement.spell_in_words`); the beats are not read for
    anything else. Nothing when that is not one thing."""
    from rules import holding

    acts = frame.get("actions") or []
    said = " ".join(str(acts[i].get("object") or "").split())
    if said.lower() not in _IT:
        return said
    for prev in reversed(acts[:i]):
        if prev.get("object") and str(prev["object"]).lower() not in _IT:
            return " ".join(str(prev["object"]).split())
    goods = sorted((getattr(pc, "goods", {}) or {}), key=len, reverse=True)
    for beat in reversed([str(b or "").lower() for b in recent or ()]):
        named = [k for k in goods if len(holding.plain(k)) > 2 and re.search(
            rf"\b{re.escape(holding.plain(k))}s?\b", beat)]
        if len(named) == 1:
            return named[0]
    return ""


# --- the rows -------------------------------------------------------------------------------

def _a_person(scene, words) -> bool:
    """Whether an object slot names a person, not a thing: a bare pronoun for one, or
    somebody standing here. "I grab him and throw him over a table" was read `take` — and a
    take of "him" is a grapple, never goods (the fight recordings, 2026-09-25 and 09-27)."""
    said = " ".join(str(words or "").split()).lower()
    return said in _PRONOUNS or said in ("me", "myself", "you") or bool(person(scene, said))


def _take(row: Row, frame, i, scene, pc, recent=()) -> None:
    from rules import holding

    a = frame["actions"][i]
    thing = _object(frame, i, pc, recent)
    if not thing:
        row.note = "nothing named to take"
        return
    coin = _is_coin(thing)
    if not coin and (_a_person(scene, thing) or not _a_thing(thing)):
        row.note = f"{thing!r} is not a thing to carry"
        return
    source = " ".join(str(a.get("target") or "").split())
    if not source:
        # A take that names no holder, right after a take that did, comes out of the same
        # hands — the frame's own structure, as "it" is the object before it. Measured
        # live on this branch (2026-10-08): "I take one of the pears from the fruit
        # seller, then a melon" read the melon with no target, nobody here carried one,
        # and the world-never-runs-out rule minted it ("Kesst Vayr takes the melon")
        # where a melon from the seller is refused: she has none.
        prev = next((p for p in reversed(frame["actions"][:i])
                     if p.get("act") in ("take", "steal")), None)
        if prev is not None and prev.get("target"):
            source = " ".join(str(prev["target"]).split())
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


def _drop(row: Row, frame, i, scene, pc, recent=(), coming=()) -> None:
    thing = _object(frame, i, pc, recent)
    if not thing:
        row.note = "nothing named to set down"
        return
    key = _carried(pc, thing, coming)
    if not key and not _is_coin(thing):
        row.missing = f"{pc.name} is not carrying {thing}"
        return
    row.intents.append({"op": "give", "actor": pc.ref,
                        "params": {"item": key or _plain(thing), "from_": pc.ref},
                        "because": "the player set it down"})


def _give(row: Row, frame, i, scene, pc, recent=(), coming=()) -> None:
    a = frame["actions"][i]
    thing = _object(frame, i, pc, recent)
    if not thing:
        row.note = "nothing named to hand over"
        return
    amount = coin_amount(thing)
    key = _carried(pc, thing, coming)
    if not (amount or key or _is_coin(thing)):
        if _a_person(scene, thing) or not _a_thing(thing):
            row.note = f"{thing!r} is not a thing to hand over"
        else:
            # "I buy the old soldier a pint": nothing in the pack to hand over, and the
            # pint is the bar's to pour. Said, never minted.
            row.missing = f"{pc.name} is not carrying {thing}"
        return
    to_words = " ".join(str(a.get("target") or "").split())
    # Nobody named ("I hand over the brass key"): the one the player is dealing with.
    to = person(scene, to_words) if to_words else addressed(scene)
    if not to:
        row.missing = (f"there is nobody here who is {to_words}" if to_words
                       else f"nobody here to give {thing} to")
        return
    if amount:
        params = {"item": amount[0], "count": amount[1], "from_": pc.ref, "to": to}
    else:
        params = {"item": key or _plain(thing), "from_": pc.ref, "to": to}
    row.intents.append({"op": "give", "actor": pc.ref, "params": params,
                        "because": "the player handed it over"})


def _sell(row: Row, frame, i, scene, pc, sentence: str, recent=(), coming=()) -> None:
    from rules import pricing

    a = frame["actions"][i]
    thing = _object(frame, i, pc, recent)
    key = _carried(pc, thing, coming) if thing else ""
    if not key and row.commit == "tried":
        # An offer of something not in the pack is talk, not a sale refused: the live
        # reader read "I approach the man and offer to help him with the crate" as an
        # offer of "to help him with the crate", and "not carrying to help him…" would
        # have reached the brief as a fact.
        row.note = f"an offer of {thing or 'nothing named'}, nothing carried to sell"
        return
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
    if row.commit == "tried":
        # A sale tried is an offer (ISO 24617-2: an Offer, which only an Accept Offer
        # closes) — a haggle the fiction answers, and only an agreement closes it. At a
        # counter too: round 1 let a keeper buy whatever was offered (CircleMUD's
        # shopkeeper, the retired `_sell_goods_declared`'s rule), and in round 2's replay
        # the counting house's clerk keeps one, so "…offer the crate for coin" would have
        # sold the crate three turns before the player agreed a price. A stall's own
        # screen is where a priced sale is made in one step. Measured on the replay,
        # round 1: "I try to sell the crate to the smith for coin" was read `sell` and sold.
        row.note = "an offer, not a sale: the buyer must agree first"
        return
    params: dict = {"item": key, "to": buyer}
    share = _SHARE.search(str(sentence or ""))
    if share and key in (pc.goods or {}):
        params["accept"] = round(int(share.group(1)) / 100 * pricing.goods_worth(key), 2)
    row.intents.append({"op": "sell", "actor": pc.ref, "params": params,
                        "because": "the player sold it"})


def table(frame: dict | None, scene, *, places=(), sentence: str = "",
          recent=()) -> list[Row]:
    """The rows the reading makes, one per action, in the order the words do them.
    `recent` is the last few beats, asked only for which carried thing "it" is."""
    from . import interpret

    rows: list[Row] = []
    if not frame or frame.get("error") or scene is None:
        return rows
    if frame.get("question") and not frame.get("actions"):
        return rows
    pc = scene.pc() if hasattr(scene, "pc") else None
    coming: list[str] = []
    gone: list[str] = []
    for i, a in enumerate(frame.get("actions") or []):
        act = str(a.get("act") or "")
        row = Row(index=i, act=act, commit=str(a.get("commit") or "done"))
        if not interpret.acting(a):
            # Intended or asked about: context for the plan (`interpret.brief_lines` says
            # so), never an op. Round 1's replay sold the crate a turn early on "I take
            # the crate to the man … who will buy it from me", read as a sale.
            row.note = f"{row.commit}, not done this turn: no op"
            rows.append(row)
            continue
        if act in GOODS_ACTS and pc is not None:
            row.thing = _object(frame, i, pc, recent)
            if act == "steal" and getattr(scene, "in_encounter", False):
                # In a fight a steal is the combat manoeuvre (CMB against CMD, the
                # `attack` op's `maneuver: steal`), which the fight's own plan writes.
                row.note = "a steal in a fight is a manoeuvre: the fight's plan writes it"
            elif act in ("take", "steal"):
                # Out of a fight a steal is a take the holder never agreed to — the same
                # `give` a take builds, which the engine reads as taken because the player
                # is the one acting (`Engine._op_give`); never asked whether it was
                # offered (`confirm_takes`): the words already said.
                _take(row, frame, i, scene, pc, recent)
                coming += [str(t["params"]["item"]) for t in row.intents]
            elif act == "drop":
                _drop(row, frame, i, scene, pc, recent, coming)
            elif act == "give":
                _give(row, frame, i, scene, pc, recent, coming)
            else:
                _sell(row, frame, i, scene, pc, sentence, recent, coming)
            if act not in ("take", "steal"):
                # A thing an earlier deed of the sentence already parted with is not
                # parted with twice. Measured on the items save's last line, read live:
                # "I also drop the Brunt of the weight on the ground and leave it behind"
                # came back `drop: the Brunt of the weight` then `drop: it` — the same
                # brunt, set down twice, the second refused by the engine into the prose.
                # Coin is a number, and two payments are two (`_same_thing` calls any two
                # mentions of coin one thing, for replacing the plan's coin op).
                twice = [t for t in row.intents if not _is_coin(t["params"]["item"])
                         and any(_same_thing(t["params"]["item"], g, pc) for g in gone)]
                if twice:
                    row.intents = [t for t in row.intents if t not in twice]
                    row.note = f"{twice[0]['params']['item']} is already parted with"
                gone += [str(t["params"]["item"]) for t in row.intents]
        else:
            # The op names: one action at a time through the reading's own op map, so each
            # op is owed by the action that declared it.
            row.ops = interpret.ops_for({"actions": [a]}, scene, places)
            # A walk to a place somebody named and the town does not have yet owes the
            # found and the travel `judgement.go_to_heard_place` writes for it — owned by
            # this action, so `order` puts them where the words do. Measured live on the
            # merged branch: "I pick the crate back up and head to the old tannery" left
            # the travel unowned (`ops_for` grounds only places the town has), the
            # pick-up ran at the tannery, and the engine minted a second crate there.
            if act == "go" and not row.ops and a.get("place"):
                from rules import heard_places

                if heard_places.named_in(str(a["place"]), scene, places) is not None:
                    row.ops = ["found", "travel"]
            if act in ("go", "seek") and a.get("object") and pc is not None:
                _carry(row, frame, i, scene, pc, recent)
                coming += [str(t["params"]["item"]) for t in row.intents]
        rows.append(row)
    return rows


def _carry(row: Row, frame, i, scene, pc, recent=()) -> None:
    """What a walk carries along is picked up first when the player is not holding it:
    "I take the crate to the man in the counting house" carries the docks man's crate
    there. Measured on round 2's replay of the owner's items save: read as a walk with no
    crate, the crate never came, and the agreed sale four turns later had nothing to sell
    (the retired `inject_goods` had read "I take the crate" and picked it up). A thing
    already in the pack is only carried; a person is never goods."""
    from rules import holding

    thing = _object(frame, i, pc, recent)
    if not thing or _a_person(scene, thing) or not _a_thing(thing):
        return
    if holding.key_in(pc.goods, thing):
        row.note = f"{thing} carried along"
        return
    row.thing = thing
    row.intents.append({"op": "give", "actor": pc.ref,
                        "params": {"item": _plain(thing) or thing, "to": pc.ref},
                        "because": "the player took it along"})


def confirm_sales(rows: list[Row], frame: dict | None, scene, *, sentence: str = "",
                  ask=None) -> list[str]:
    """A sale about to be built is asked again, alone (`interpret.confirm_sale`): closed
    now, or only offered, meant for later, asked about? Anything but "closed" holds it back
    — an offer, a plan, a question — at a counter as anywhere else. A failed check holds
    it back too, because a sale cannot be taken back and an offer can be repeated.
    Returns a line per sale held back, for the turn log. `ask` None (no model: the test
    suite, or the reader off) trusts the reading.

    Measured: round 2's replay with the frozen reader read "I take the crate to the man
    in the counting house who will buy it from me" and "I smile and flirt with the clerk
    and offer the crate for coin" as sales DONE — the round-1 regression back."""
    notes: list[str] = []
    if ask is None or not frame:
        return notes
    actions = frame.get("actions") or []
    for row in rows:
        sale = next((i for i in row.intents if i["op"] == "sell"), None)
        if row.act != "sell" or sale is None or row.commit != "done":
            continue
        a = actions[row.index] if row.index < len(actions) else {}
        said = ask(sentence, str(a.get("span") or sentence))
        # Only a sale closed stands, at a counter too: the counting house's clerk keeps
        # one, and in the replay "…who will buy it from me" sold the crate to him a turn
        # early while a check that skipped keepers never asked.
        if said == "done":
            continue
        row.commit = said or "tried"
        row.intents = []
        if isinstance(a, dict):
            # The reading carries the answer, so the plan's own sale has nothing to stand
            # behind either (`apply`), and the brief says how far it was done.
            a["commit"] = row.commit
        row.note = (f"the sale asked again: {said or 'no answer'}, so an offer, not a sale"
                    if row.commit == "tried" else
                    f"the sale asked again: {row.commit}, not done this turn: no op")
        notes.append(f"{row.thing or sale['params'].get('item')}: {row.note}")
    return notes


def confirm_takes(rows: list[Row], frame: dict | None, scene, *, recent=(),
                  ask=None) -> list[str]:
    """A take from a person, asked whether that person gave or offered it
    (`interpret.confirm_take`, shown the last beat). "offered" makes the holder the one
    acting — they hand it over, and `Engine._op_give` reads a hand-over; anything else
    leaves the player acting, which the engine reads as a take: owner kept, `stolen` set.
    A `steal` is never asked (the words said it), nor a take out of a container. `ask`
    None (no model: the test suite, or the reader off) leaves every take a take — the
    engine's own rule (docs/items-have-owners.md). Returns a line per take turned into a
    hand-over, for the turn log.

    Measured 2026-10-08 (the deeds lane): "I take an apple from the fruit seller without
    paying" came out as the seller handing the apple over. The engine now reads the
    player taking from a person as a take; this asks only so that "I take the purse he
    holds out" stays the reward it was."""
    notes: list[str] = []
    if ask is None or not frame or scene is None:
        return notes
    actions = frame.get("actions") or []
    people = getattr(scene, "actors", {}) or {}
    beat = " ".join(str(b or "") for b in list(recent or ())[-2:])[-700:]
    for row in rows:
        if row.act != "take" or row.commit != "done":
            continue
        for built in row.intents:
            p = built.get("params") or {}
            holder = people.get(str(p.get("from_") or ""))
            if built.get("op") != "give" or holder is None or getattr(holder, "is_pc", False):
                continue
            a = actions[row.index] if row.index < len(actions) else {}
            said = ask(beat, str(a.get("span") or row.thing or p.get("item") or ""))
            if said != "offered":
                continue
            built["actor"] = holder.ref
            built["because"] = f"{holder.name} handed it over"
            row.note = "asked again: offered, so handed over"
            notes.append(f"{p.get('item')}: offered by {holder.name}, handed over")
    return notes


_TENDING_ACTS = frozenset({"use", "other"})


def first_aid(rows: list[Row], frame: dict | None, scene, *, ask=None) -> list[str]:
    """First aid built whole: a deed aimed at somebody here who is DYING becomes the Heal
    check the Core Rulebook stabilises them with (`rules/firstaid.py`, DC 15) — with its
    `target`, the patient, which is the one slot the plan kept leaving off.

    Measured 2026-10-08 (the deeds lane, local model): "I give first aid to the wounded
    porter" was planned `check skill=heal` with no target 3 times of 3, so the engine found
    no patient and the porter bled on; on this branch's own repro the planner wrote
    `use_item medical_kit_01` (carried by nobody), `check sense motive`, and
    `use_item bandage_1` for three phrasings — never once the Heal check aimed at him.

    Detected in code, from the engine's state: an action done now of a kind that can be
    tending (`use`, `other` — the acts the reader gives "bandage" and "give first aid"),
    whose target is somebody here `firstaid.dying` says is dying. A Heal named as a skill
    ("I use the Heal skill on the porter": the `object`/`power` slot is the skill's own
    name, a closed list) is first aid outright. Anything else is asked ONE question
    (`interpret.confirm_first_aid`): keeping them alive, or something else? — CLAUDE.md's
    detect-then-ask. `ask` None (the test suite, the reader off) builds only the
    skill-named route. Returns a line per check built, for the turn log."""
    from rules import firstaid, holding

    from . import interpret

    notes: list[str] = []
    if not frame or scene is None or not hasattr(scene, "pc") or scene.pc() is None:
        return notes
    pc = scene.pc()
    actions = frame.get("actions") or []
    people = getattr(scene, "actors", {}) or {}
    tended: set[str] = set()
    for row in rows:
        a = actions[row.index] if row.index < len(actions) else {}
        # Done or tried ("I try to stabilise him" is `tried`, and 1e rolls it).
        if row.act not in _TENDING_ACTS or row.intents or not interpret.acting(a):
            continue
        ref = person(scene, " ".join(str(a.get("target") or "").split()))
        if not ref:
            # Aimed at a wound, not a person ("bandage his wound", read live with
            # `target: his wound`), or at nobody: the one creature here who is dying, when
            # there is exactly one — the engine's state, as `firstaid.patient_of` reads it.
            # The question below still decides whether the deed is first aid at all.
            dying_here = [x for x in people.values()
                          if x is not pc and firstaid.dying(x)]
            ref = dying_here[0].ref if len(dying_here) == 1 else ""
        patient = people.get(ref) if ref else None
        if (patient is None or patient is pc or not firstaid.dying(patient)
                or patient.ref in tended):
            # One first aid per patient a turn: "I kneel by the porter and try to
            # stabilise him" is two actions of the reading and one Heal check.
            continue
        named = any(" ".join(w for w in holding.plain(a.get(slot)).split()
                             if w not in ("skill", "skills")) == firstaid.SKILL
                    for slot in ("object", "power") if a.get(slot))
        if not named:
            if ask is None or ask(str(a.get("span") or ""), patient.name) != "first aid":
                continue
        tended.add(patient.ref)
        # The band is there because a check must name something to beat (the parse
        # refuses one without); with the patient dying when it resolves it is never read
        # — first aid is the rule's DC 15, whatever the band (`Engine._op_check`).
        row.intents.append({"op": "check", "actor": pc.ref, "target": patient.ref,
                            "params": {"skill": firstaid.SKILL, "dc": {"band": "average"}},
                            "because": "the player gave first aid"})
        row.note = f"first aid to {patient.name}"
        notes.append(row.note)
    return notes


# --- who a declared blow lands on -------------------------------------------------------------

# The acts whose deed is a blow at somebody (`interpret.ACTS`).
VIOLENT_ACTS = frozenset({"attack"})
# Acts that, done before a blow in the same sentence, put somebody in front of the player
# whom the engine cannot see yet: a walk into another room, the person sought or followed.
# "I walk into the tavern and punch the first man I see" is about people in the tavern,
# and the people standing HERE at plan time are not them.
_FINDS_SOMEBODY_FIRST = frozenset({"go", "journey", "leave", "call_on", "break_in",
                                   "seek", "follow"})
# How far each zone is, in feet, for a scene with no map to measure on (rules/intents.py
# ZONES; the squares `Scene.place_by_zone` lays them at).
_ZONE_FEET = {"engaged": 5, "near": 15, "far": 40}

NOBODY_TO_ATTACK = "there is nobody here to attack"


def _standing_here(scene) -> list:
    """Everybody non-player here who could be struck as a fresh blow: not down, not dead,
    and seen (somebody hiding is not in the room the character can see — the brief's own
    rule for WHO IS HERE)."""
    return [a for a in (getattr(scene, "actors", {}) or {}).values()
            if not getattr(a, "is_pc", False) and not a.is_down
            and not a.has_state("state.hidden")]


def _ours(actor) -> bool:
    from rules import states as states_mod

    return (actor.has_state(states_mod.TRAVELS_WITH_YOU)
            or actor.has_state(states_mod.OWNED_BY_YOU))


def nearest(scene, refs) -> str:
    """The one of `refs` nearest the player, by the squares people keep (`Scene.positions`;
    the ruling of 2026-09-28: everyone in a scene has a square from arrival and keeps it),
    else by zone; the lower ref breaks a tie, so the answer never depends on dict order.
    The player's own people come last: an unnamed blow is never the obvious reading of a
    friend (the drover shot dying, 2026-10-01)."""
    pc = scene.pc() if hasattr(scene, "pc") else None
    actors = getattr(scene, "actors", {}) or {}

    def key(ref):
        a = actors.get(ref)
        feet = scene.distance_between(pc.ref, ref) if pc is not None else None
        if feet is None:
            feet = _ZONE_FEET.get(str((getattr(scene, "zones", {}) or {}).get(ref)), 999)
        num = int(re.sub(r"\D", "", ref) or 0)
        return (a is not None and _ours(a), feet, num, ref)

    pool = [r for r in refs if r in actors]
    return min(pool, key=key) if pool else ""


def label(actor) -> str:
    """How the victim question shows a person: the name the player knows them by, and the
    two facts the engine holds that decide "a civilian" and "my friend" — never a guess."""
    from rules import states as states_mod

    bits = []
    if actor.has_state("role.guard") or str(getattr(actor, "from_template", "")) in (
            "watchman", "guard", "soldier"):
        bits.append("a guard")
    if actor.has_state(states_mod.TRAVELS_WITH_YOU):
        bits.append("travels with you")
    elif actor.has_state(states_mod.OWNED_BY_YOU):
        bits.append("yours")
    if actor.is_down:
        bits.append("down")
    return str(actor.name) + (f" ({'; '.join(bits)})" if bits else "")


def victims(rows: list[Row], frame: dict | None, scene, *, ask=None) -> list[str]:
    """A declared blow lands on a REAL person here, or the turn says there is nobody.

    The owner, 2026-10-09: "if i say I attack the closest person or i go on a rampage or i
    assault a civilian etc. it should be able to start a fight." Measured live the same day
    (gemma-4-12B, a market of three bystanders, scratch data): "I attack the closest person."
    was planned at the fruit seller beside the player, and the fight declarer then REQUIRED
    a spawn, so two bandits came out of nowhere and joined the fight on her side; "I go on a
    rampage." was read `other` and five plans aimed at `new1` until the turn degraded into
    prose about slicing men who were not there. The regex door (`inject_fight`'s cue table
    and template thug) is gone; this builds the blow from the reading:

      * the target slot resolves through the engine's finders (`person`: a name, a
        description shown as the name, a pronoun) — "I attack Bob" is Bob;
      * a pronoun keeps the 2026-09-18 rule in a fight: it means somebody IN the fight
        (`judgement._can_be_fought`), never a bystander, or the one the player is engaged
        with; out of a fight it is the one the player is dealing with (`addressed`);
      * no words in a fight: the nearest foe standing;
      * anything else — "the closest person", "a civilian", "the biggest bruiser", a
        rampage — is ONE question with the people here as an enum
        (`interpret.confirm_victims`): which of them could the words mean? The NEAREST of
        those, by the squares people keep, is the engine's answer (`nearest`);
      * nobody standing here at all, or nobody the words fit: the row is `missing`, and
        the turn is the refusal in words ("There is nobody here to attack.") — never an
        invented opponent.

    The attack built here goes to the plan through `judgement.inject_fight`, which aims the
    plan's own blow at it; the engine's battle gate opens the fight on it and brings in
    their own kind and the law (`Engine._ensure_encounter`, `rally`, `_law_joins`).
    `ask` None (the test suite, the reader off) builds only what needs no question.
    Returns a line per row decided, for the turn log."""
    from . import interpret, judgement

    notes: list[str] = []
    if not frame or scene is None or not hasattr(scene, "pc") or scene.pc() is None:
        return notes
    pc = scene.pc()
    actions = frame.get("actions") or []
    actors = getattr(scene, "actors", {}) or {}
    fighting = bool(getattr(scene, "in_encounter", False))
    for row in rows:
        a = actions[row.index] if row.index < len(actions) else {}
        if row.act not in VIOLENT_ACTS or row.intents or not interpret.acting(a):
            continue
        if any(interpret.acting(b) and b.get("act") in _FINDS_SOMEBODY_FIRST
               for b in actions[:row.index]):
            row.note = "the blow comes after somebody is found or a place is reached"
            continue
        here = _standing_here(scene)
        words = " ".join(str(a.get("target") or "").split())
        # "it" too, for a blow: the live reader reads "I attack it" `target: it`.
        pronoun = words.lower() in _PRONOUNS | {"it"}
        if not fighting and not here and not any(
                not getattr(x, "is_pc", False) and not x.has_state("state.down.dead")
                for x in actors.values()) and not (words and not pronoun
                                                   and person(scene, words)):
            # Not a soul but the player (and the dead): the refusal, in words. A body the
            # words name is theirs to kick (`redirect_attacks_off_corpses` lets that blow
            # stand); in a fight the answer to nobody left is the fight's end
            # (`judgement.inject_fight`), which is what pays out.
            row.missing = NOBODY_TO_ATTACK
            notes.append(row.missing)
            continue
        ref, how = "", ""
        if pronoun:
            ref = _pronoun_victim(scene, words, fighting)
            how = f"{words!r}, by the engine's state"
        elif words:
            ref = person(scene, words)
            how = f"{words!r}, by name"
        elif fighting:
            foes = [x.ref for x in here if judgement._can_be_fought(x)]
            ref = nearest(scene, foes)
            how = "the nearest foe"
        if not ref and here and not pronoun:
            if ask is None:
                row.note = "who the blow is aimed at was not asked (no reader)"
                continue
            meant = ask(str(a.get("span") or words), words,
                        [(x.ref, label(x)) for x in here])
            if meant is None:
                row.note = "the question of who the blow is aimed at failed"
                continue
            if not meant:
                if fighting:
                    # "I keep swinging" with every foe down: the fight is over, and
                    # `inject_fight` says so.
                    row.note = "nobody left in the fight the words could mean"
                    continue
                row.missing = (f"nobody here answers to {words}" if words
                               else NOBODY_TO_ATTACK)
                notes.append(row.missing)
                continue
            # The player's own people only when nobody else is meant.
            strangers = [r for r in meant if not _ours(actors[r])]
            ref = nearest(scene, strangers or meant)
            how = (f"the nearest of {len(meant)} the words could mean" if len(meant) > 1
                   else "the one the words mean")
        victim = actors.get(ref) if ref else None
        if victim is None:
            if not row.note:
                row.note = "nobody resolved; the plan's own blow stands"
            continue
        if victim.is_down or victim.has_state("state.helpless"):
            if victim.has_state("state.down.dead"):
                row.note = f"{victim.name} is dead: the plan's own blow stands"
                continue
            # A blow the reader read at a body on the floor is a blow, whatever words the
            # player used. Before, this left "the plan's own blow", and a plan that wrote
            # none (it took the dying wolf for dead and wrote `narrate_only`) left the wolf
            # breathing at -2 while the prose killed it: measured in the leather final
            # pass's playthrough, 2026-10-09, "I finish the dying wolf with a thrust of my
            # rapier" (read `attack`, target "the dying wolf") changed nothing, and the
            # harvest stayed shut ("still breathing: finish it first"). Out of a fight it
            # is the coup de grâce (CRB p.197; no time is short out of a fight, and it
            # opens none); in one, an ordinary blow at helpless AC, the engine's own rule.
            # `judgement.inject_fight` adds it only when the plan aimed nothing at them.
            params = {} if fighting else {"coup_de_grace": True}
            row.intents.append({"op": "attack", "actor": pc.ref, "target": victim.ref,
                                "because": f"the player strikes {victim.name}, who is down",
                                "params": params})
            row.note = f"{victim.name} is down: " + (
                "a blow at helpless AC" if fighting else "a coup de grâce")
            notes.append(row.note)
            continue
        row.intents.append({"op": "attack", "actor": pc.ref, "target": victim.ref,
                            "because": f"the player attacks {victim.name}"})
        row.note = f"the blow lands on {victim.name} ({victim.ref}): {how}"
        notes.append(row.note)
    return notes


def _pronoun_victim(scene, words: str, fighting: bool) -> str:
    """Who "him", "her", "them" means for a blow. In a fight, only somebody in it: measured
    2026-09-18 with the map open, the planner's attack on "the man" landed on a 4-hp
    bystander who had never been in the fight (`judgement._can_be_fought`). Out of one, the
    pronoun against the people here, else whoever the player is dealing with."""
    from . import judgement

    here = _standing_here(scene)
    pool = [x for x in here if judgement._can_be_fought(x)] if fighting else \
        [x for x in here if not _ours(x)]
    fits = [x.ref for x in pool
            if words.lower() in _pronoun_forms(getattr(x, "pronouns", ""))]
    if len(fits) == 1:
        return fits[0]
    who = addressed(scene)
    return who if who in {x.ref for x in pool} else ""


def declared(rows: list[Row]) -> list[str]:
    """The op names the plan must carry, in the order the words do them — the `declared`
    block's keys (`prompts.turn_schema`). Ops built whole are not asked of the model."""
    return list(dict.fromkeys(op for r in rows for op in r.ops))


def built_ops(rows: list[Row]) -> list[str]:
    return list(dict.fromkeys(i["op"] for r in rows for i in r.intents))


def unresolved(rows: list[Row]) -> list[str]:
    return list(dict.fromkeys(r.missing for r in rows if r.missing))


def refusal(rows: list[Row]) -> str:
    """The turn's whole answer when every deed the words declared moves a thing and not
    one of them can: "Kesst Vayr is not carrying a crate." Nothing is planned, nothing is
    invented, and the player is told what was not found. "" when anything else is owed.

    A blow with nobody to land on is the same refusal (`victims`, 2026-10-09): "There is
    nobody here to attack." — the words the template thug used to answer."""
    if not rows or any(r.act not in GOODS_ACTS | VIOLENT_ACTS or r.intents or r.ops
                       for r in rows):
        return ""
    missing = unresolved(rows)
    if not missing or any(not r.missing for r in rows):
        return ""
    return " ".join(m[0].upper() + m[1:] + "." for m in missing)


# --- the reading confirms the plan, or overrules it ------------------------------------------

def _op(r) -> str:
    return str((r or {}).get("op", "")).lower() if isinstance(r, dict) else ""


def _same_thing(a, b, pc=None) -> bool:
    """Two mentions of one thing: both coin, or the same name — a jar by its shelf id
    ("yarow-elixir#1") or the way a person says it ("Yarow Elixir"). Measured on the
    trade tests: the plan's give of "Yarow Elixir" stood beside the table's sale of
    yarow-elixir#1, and the elixir left twice."""
    from rules import holding

    if _is_coin(a) and _is_coin(b):
        return True
    if pc is not None:
        a, b = (_stock_id(pc, a) or a), (_stock_id(pc, b) or b)
    return holding.same(a, b)


def _to_player(p: dict, pc, target=None) -> bool:
    """Whether a give lands in the player's hands. The intent's own `target` is where it
    goes when the params name nobody, as `Engine._op_give` reads it: the recorded
    `give actor=pc target=c13` of the brunt was a give TO the smith."""
    to = str(p.get("to") or target or "").strip().lower()
    frm = str(p.get("from_") or p.get("from") or "").strip().lower()
    return to in (pc.ref, "pc", "you", "player") or not (to or frm)


def apply(raw, rows: list[Row], frame: dict | None, scene, *, notes: list | None = None) -> list:
    """The plan, with the reading's goods ops in it.

    1. A plan op that moves the same thing as a built one is replaced by it, wherever it
       stood: the reading settles which way the thing goes and to whom ("the coins from
       the pouch into my coin purse" is coin IN; the model's coin give was a payment OUT).
    2. A plan op that moves a thing and that no act of the reading stands behind is
       overruled: a give to the player needs an act that gets something, a give from the
       player one that parts with something, and a sale needs a `sell` DONE — a sale only
       tried is an offer, never a sale. Only acts done or tried stand behind anything; an
       intended or asked-about one stands behind nothing. Gives
       between other people are theirs.
    3. Built ops the plan did not carry are added.

    Only with a reading: with none there is nothing to stand behind or overrule with, and
    the plan stands alone (`GMAgent.plan_turn`)."""
    from . import interpret

    if not isinstance(raw, list) or not frame or frame.get("error") or scene is None:
        return raw
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None:
        return raw
    # A blow the table aimed (`victims`) is put in by `judgement.inject_fight`, which aims
    # the plan's own blow at the same person rather than adding a second one.
    built = [i for r in rows if r.act not in VIOLENT_ACTS for i in r.intents]
    nothing = [r.thing for r in rows if r.act in GOODS_ACTS and r.thing and not r.intents]
    acting = [a for a in frame.get("actions") or [] if interpret.acting(a)]
    acts = {str(a.get("act") or "") for a in acting}
    closed = any(a.get("act") == "sell" and (a.get("commit") or "done") == "done"
                 for a in acting)
    out: list = []
    placed: set[int] = set()
    checks = {str((b.get("params") or {}).get("skill") or "").lower()
              for b in built if b.get("op") == "check"}
    for r in raw:
        op = _op(r)
        if op == "check" and checks and str(
                ((r or {}).get("params") or {}).get("skill") or "").lower() in checks:
            # The table built this check whole (`first_aid`): the plan's own copy of it,
            # usually without the patient, would roll a second Heal against nobody.
            if notes is not None:
                notes.append("the plan's check replaced by the reading's first aid")
            continue
        if op not in ("give", "sell"):
            out.append(r)
            continue
        p = r.get("params") or {}
        actor = str(r.get("actor") or "")
        target = r.get("target")
        mine = actor in ("", "pc", pc.ref, "None") or str(p.get("from_") or "") == pc.ref \
            or _to_player(p, pc, target)
        if not mine:
            out.append(r)                        # between other people: theirs
            continue
        twin = next((k for k, b in enumerate(built)
                     if _same_thing(p.get("item"), b["params"].get("item"), pc)), None)
        if twin is None and not _is_coin(p.get("item")) and any(
                _same_thing(p.get("item"), t, pc) for t in nothing):
            # The reading named this very thing and the table found nothing to move —
            # not carried, already carried, not a thing. The plan's op on it goes too.
            # Measured in the replay of the items save's last line: the reading's drop of
            # the brunt found none in the pack, and the plan's `give actor=pc target=c13`
            # of it stood and was refused into the prose ("has no Brunt of the weight").
            if notes is not None:
                notes.append(f"the plan's {op} of {p.get('item')!r}: the reading named it "
                             f"and the table found nothing to move, dropped")
            continue
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
            stands = closed
        elif _to_player(p, pc, target):
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
            # Within one action, what the table built goes first: the crate a walk carries
            # is picked up before the walk (`_carry`), not at the far end of it.
            keyed.append((idx, 0 if id(r) in by_built else 1, k, r))
    if len(keyed) < 2:
        return raw
    keyed.sort(key=lambda t: t[:3])
    out = list(raw)
    for at, (*_, r) in zip(slots, keyed):
        out[at] = r
    return out
