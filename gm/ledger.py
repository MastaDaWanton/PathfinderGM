"""What happened in the turns that fell out of the window.

The near window holds recent play verbatim. Older turns are cut by `prompts.pack`,
and before this module they were simply gone: the campaign could run forty turns, the
oldest exchanges would leave the prompt, and nothing anywhere remembered that they had
happened.

Three decisions, each with a reason that is not a preference.

**Built from the engine, not from prose.** Every resolved turn already carries
outcomes, and an outcome names its op and the people it touched. An entry assembled
from those cannot hallucinate, which is the failure SillyTavern documents for its own
summariser ("the outputs may lose some important details or contain hallucinations").
No model call, so no latency on a turn that already costs twenty-five seconds.

**Written once, never re-summarised.** The one direct comparison available puts
recursive summarisation last of every approach measured — 35.3% against 78.6% for
periodic summaries and 94.4% for full context — and names the cause as detail lost
through repeated re-compression. So an entry is made when its turn resolves and is
never rewritten.

**No numbers.** An entry saying the player took nine damage is a second store of a
fact the engine already holds, and the second law forbids parallel stores. The moment
the two disagree, the prompt carries a stale near-miss beside the truth, which is the
single most damaging thing measured in the retrieval literature: one related-but-wrong
passage beside a correct one dropped accuracy from 56.4% to 45.9%, while wholly
irrelevant text did no harm at all. So the prose of an entry may not contain a digit;
the turn index is a field, not a sentence.

See docs/memory-policy.md and docs/retrieval-and-memory.md.
"""
from __future__ import annotations

import re

# What the ledger may say about a turn. Deliberately short of the full op vocabulary:
# a Perception check is not a thing worth remembering forty turns later, and a ledger
# that records everything is a second transcript rather than a memory.
#
# The fields a shape may use, all resolved to what the player read — never a ref, never
# a place id (`_name_of`): {where} the place gone to, {came_from} the place left, {who}
# the person the effect names, {title} a card's or a place's name, {item} the thing an
# item op moved. Measured 2026-10-03 (item 22): "you went to ca~urban:the-docks" was a
# raw place id in the prompt, because a travel effect carries `place` as an id and the
# shape printed it; and "you spoke with someone" said nothing at all.
_WORTH_KEEPING = {
    "travel": "went from {came_from} to {where}",
    "journey": "set out on the road to {where}",
    "quest": "took up {title}",
    "quest_step": "moved {title} along",
    "found": "founded {title}",
    "venture": "went into {title}",
    "buy": "bought from {who}",
    "sell": "sold to {who}",
    "give": "handed something to {who}",
    "loot": "stripped {who}",
    "begin_encounter": "fought {who}",
    "introduce": "met {who}",
    "rest": "rested",
    "craft": "worked at a craft",
}

# Ops whose meaning turns on a flag in the effect rather than the op alone: a `company`
# can be somebody joining or parting, and a `talk` outcome is a conversation ending.
_BY_EFFECT = {
    ("company", True): "{who} came along with you",
    ("company", False): "parted company with {who}",
    ("talk", True): "the conversation with {who} ended",
}

# What was actually said, kept in full up to here. docs/memory-policy.md planned one
# small model call at eviction for exactly this — the part the engine does not own —
# and once speech had an op of its own the call turned out to be unnecessary: the words
# are in an effect the engine wrote, so they can be kept mechanically, with no latency
# and nothing to invent. A promise made forty turns ago is the single most useful thing
# a ledger can hold, and it is the thing a summariser would have been most likely to
# get wrong.
SAID_CAP = 160

# How much of the prompt the ledger may take. Small on purpose: the Stanford agents
# result, which `rules/cards.py` already cites for the same reason, is that a handful
# of relevant lines beats the whole history.
BUDGET_CHARS = 1200
# How many entries are kept on the campaign at all. Past this the oldest go, because a
# ledger that grows without limit is the problem it was built to solve.
ENTRY_CAP = 400

_DIGIT = re.compile(r"\d")
# A place id as `places` mints them: location id, "~", terrain, ":", slug path. After the
# digit strip an old entry's id has lost its hex digits ("ca~urban:the-docks"), so the
# location part is any run of word characters, or none.
_PLACE_ID = re.compile(r"\w*~[a-z_-]+:[\w/-]+")
# The scene's refs, as `bestiary.next_ref` mints them, and the player's.
_REF = re.compile(r"(?:c|n)\d+|pc")


def note(outcomes, *, turn: int, hist: int = 0, spoke_with: str = "", where: str = "",
         names: dict | None = None, places: dict | None = None) -> dict | None:
    """One entry for one resolved turn, or None if nothing worth keeping happened.

    `outcomes` are the engine's own, so the op names here are the engine's decisions
    rather than anything a model proposed. `names` maps refs to the names the player
    read, because "you stripped c6" is not a memory of anything. `places` maps place ids
    to the names the player read, for the same reason; an id it does not hold is still
    never printed (`_name_of`). `where` is where the party stood, as a name.
    """
    did: list[str] = []
    for o in outcomes or []:
        op = str(getattr(o, "op", "") or "")
        if op in _MOVES_THINGS:
            line = _moved(o, names)
            if line and line not in did:
                did.append(line)
            continue
        if op == "say":
            words = _said(o)
            if words:
                # Spoken to nobody in particular, inside a conversation: it was said to
                # the person being talked to, and the ledger can say who.
                heard = _named(o, ("to",), names, places) or spoke_with
                did.append((f"told {heard}" if heard else "said") + f", “{words}”")
            continue
        flag = _flag(o, op)
        shape = _BY_EFFECT.get((op, flag)) if flag is not None else None
        shape = shape or _WORTH_KEEPING.get(op)
        if not shape:
            continue
        gone_to = _named(o, ("to_name", "place", "to", "biome"), names, places)
        came_from = _named(o, ("was_place",), names, places)
        if op == "travel" and not came_from:
            shape = "went to {where}"
        # Who an introduce made, by the names the engine gave them — not the `who` the
        # plan asked for, which is a description.
        who = (_introduced(o) if op == "introduce" else "") or \
            _named(o, ("ref", "to", "from_", "target", "who"), names, places)
        if op == "introduce" and not who:
            continue
        said = shape.format(where=gone_to or where or "somewhere new",
                            came_from=came_from,
                            title=_named(o, ("title", "name"), names, places) or "something",
                            who=who or "someone",
                            item=_named(o, ("item",), names, places) or "something")
        if said not in did:
            did.append(said)
    # Only when the turn produced no `say` of its own. With both, the entry read
    # "you spoke with the clerk, told the clerk, ..." — the same fact twice, which is
    # the thing this file exists to keep out of the prompt.
    if spoke_with and not any(s.startswith(("spoke", "told", "said")) for s in did):
        did.insert(0, f"spoke with {spoke_with}")
    if not did:
        return None
    text = "you " + ", ".join(did)
    # The rule, enforced rather than asked for: no mechanical number reaches the
    # ledger. A name with a digit in it is not worth the door it would open.
    text = _DIGIT.sub("", text)
    return {"turn": int(turn), "hist": int(hist), "at": str(where or ""), "text": text}


# The ops that move a thing, which the ledger says by what moved and between whom
# (item 7 of 2026-10-03). The templates above said "handed something to {who}" and read
# `who` off the first ref in the effect — which for a pick-up is the taker — so the
# market-talk save remembered "handed something to Kesst Vayr" for a wink that never
# left her, and a sale was remembered as "sold to" the seller.
_MOVES_THINGS = frozenset({"give", "sell", "buy"})


def _moved(o, names: dict | None) -> str:
    """One line for a thing that changed hands, or "" when nothing did: a refusal, a
    give that moved nothing, the payment acknowledged a second time. Never a number —
    the price is the tell's, and the ledger may hold no digit."""
    if str(getattr(o, "status", "resolved") or "resolved") != "resolved":
        return ""
    op = str(getattr(o, "op", "") or "")
    names = names or {}

    def name(ref) -> str:
        ref = str(ref or "")
        return _person(str(names[ref])) if ref in names else ref

    for e in getattr(o, "effects", None) or []:
        if not isinstance(e, dict):
            continue
        thing = " ".join(str(e.get("item") or "").split())
        the = thing if re.match(r"(?i)(the|a|an|some)\b", thing) else f"the {thing}"
        if op == "sell" and e.get("kind") == "sold" and int(e.get("count") or 0) > 0:
            buyer = name(e.get("to"))
            return f"sold {the}" + (f" to {buyer}" if buyer else "")
        if op == "buy" and e.get("kind") == "bought":
            seller = name(e.get("from"))
            return f"bought {the}" + (f" from {seller}" if seller else "")
        if op != "give" or e.get("kind") != "give" or int(e.get("count") or 0) <= 0:
            continue
        how = str(e.get("how") or "")
        if thing == "coin" or thing in ("gp", "sp", "cp", "pp"):
            the = "coin"
        giver, taker = name(e.get("from")), name(e.get("to"))
        if how == "emptied":
            return f"emptied {giver or 'a pouch'} into the purse"
        if how == "took_from":
            return f"took {the} from {giver}"
        if how == "took_out":
            return f"took {the} out of {giver}" if giver else f"took {the}"
        if how == "set_down":
            return f"set down {the}"
        if how == "handed" and giver and taker:
            # "you handed the lantern to the smith", or "you were handed the pouch by
            # the clerk" — the entry is in the second person, about the player.
            if str(e.get("from")) == "pc":
                return f"handed {the} to {taker}"
            if str(e.get("to")) == "pc":
                return f"were handed {the} by {giver}"
            return f"saw {giver} hand {the} to {taker}"
        return f"took {the}"
    return ""


def _said(o) -> str:
    """The words on a `say` outcome, as the engine wrote them into its effect."""
    for e in getattr(o, "effects", None) or []:
        if isinstance(e, dict) and e.get("kind") == "said" and e.get("words"):
            return " ".join(str(e["words"]).split())[:SAID_CAP]
    return ""


def _named(o, keys, names: dict | None, places: dict | None = None) -> str:
    """The first of `keys` any of this outcome's effects carries, as a name.

    An `Outcome` holds `effects`, a list of dicts the engine wrote — there is no
    params bag to read, and the ref in an effect is `c6` rather than anybody the
    player would recognise, so refs are resolved through the scene's own names, and
    place ids through the places' (`_name_of`).
    """
    for e in getattr(o, "effects", None) or []:
        if not isinstance(e, dict):
            continue
        for key in keys:
            got = e.get(key)
            # Names are strings. A number under the same key is a measure — the
            # `regard` effect's "to": 37 — and would print as a name with its digits cut.
            if not isinstance(got, str) or not got.strip():
                continue
            return _name_of(str(got), names, places)
    return ""


def _person(name: str) -> str:
    """A person's name as a sentence carries it: "the man in the heavy coat", never "you
    told man in the heavy coat" (measured live, 2026-10-03, on the healed market-talk save
    — a descriptor name has no article of its own, `names.is_descriptor`)."""
    from rules import names as names_mod

    return f"the {name}" if names_mod.is_descriptor(name) else name


def _name_of(value: str, names: dict | None, places: dict | None) -> str:
    """A ref or a place id as the player read it.

    A place id the caller's table does not hold — a place since left behind, a world
    re-read — is still never printed as an id: its last segment is the place's own
    slug ("6953424c8a82~urban:the-docks/the-storage-area" is "the storage area"), which
    is how every place id here is minted (`places.child_id`)."""
    if value in (names or {}):
        return _person(str(names[value]))
    if value in (places or {}):
        return str(places[value])
    # A ref nobody could name is still not a name: "c4" with its digit cut is "you
    # told c" (2026-10-03, a ref whose bearer had left the table).
    if _REF.fullmatch(value):
        return "someone"
    if "~" in value or (":" in value and " " not in value):
        tail = re.split(r"[:/]", value)[-1]
        return " ".join(tail.replace("_", "-").split("-")).strip() or "somewhere"
    return value


def _flag(o, op: str):
    """The flag that says which of an op's meanings this outcome had, or None."""
    for e in getattr(o, "effects", None) or []:
        if isinstance(e, dict):
            if op == "company" and "travels" in e:
                return bool(e["travels"])
            if op == "talk" and e.get("left"):
                return True
    return None


def _introduced(o) -> str:
    """Who an `introduce` brought into the scene, by the names the engine gave them."""
    for e in getattr(o, "effects", None) or []:
        if isinstance(e, dict) and e.get("kind") == "introduce":
            made = [str(a.get("name") or "") for a in e.get("actors") or ()
                    if isinstance(a, dict) and a.get("name")]
            if made:
                return " and ".join(made) if len(made) <= 2 else \
                    ", ".join(made[:-1]) + " and " + made[-1]
    return ""


def keep(entries: list[dict], entry: dict | None) -> list[dict]:
    """Add an entry and hold the cap. Entries are never rewritten, only dropped.

    A run of identical entries is collapsed to the first. Six turns of asking the same
    clerk the same kind of question is one memory, and "ten of ten paragraphs ended the
    same way" is this project's oldest measured smell — a ledger is the cheapest place
    in the app to spend the whole budget saying one thing over and over.
    """
    if entry is None:
        return entries
    if entries and entries[-1].get("text") == entry.get("text"):
        entries[-1]["hist"] = entry.get("hist", entries[-1].get("hist"))
        entries[-1]["turn"] = entry.get("turn", entries[-1].get("turn"))
        return entries
    entries.append(entry)
    # In place. Returning `entries[-ENTRY_CAP:]` instead built a new list and left the
    # campaign's own still growing — the cap read correctly and enforced nothing, on
    # every caller, because none of them reassign. Caught by the cap's own test.
    if len(entries) > ENTRY_CAP:
        del entries[:-ENTRY_CAP]
    return entries


def block(entries, *, before_hist: int, budget: int = BUDGET_CHARS) -> str:
    """The ledger as the prompt states it: only turns the window no longer carries.

    `before_hist` is how many history messages the budget cut from the front, and an
    entry records `hist` — the length of the history when it was written — so the two
    are counted in the same units. Anything at or below the cut is outside the window
    and is the ledger's business; anything above it is still there verbatim and is
    not, because a fact in the prompt twice is the parallel store the second law
    forbids.

    Newest first while the budget lasts, then reversed back into reading order: the
    most recent of the forgotten turns is the one most worth the room.
    """
    older = [e for e in entries or [] if int(e.get("hist", 0)) <= int(before_hist)]
    if not older:
        return ""
    # The budget is the whole block — header and line breaks included. Only the entry
    # lines were counted, so the block ran over the room `prompts.pack` had reserved
    # for it by the header's length and a newline per entry, and the prompt-budget test
    # went 13 characters over the day the worked examples grew (2026-09-25).
    header = ("EARLIER, WHICH YOU NO LONGER HAVE THE WORDS FOR (facts, kept by the "
              "engine; do not contradict them):\n")
    lines, spent = [], len(header)
    for e in reversed(older):
        # Entries are never rewritten, so a save written before item 22 still holds
        # "you went to ca~urban:the-docks"; the id is read as a name on the way out.
        text = _PLACE_ID.sub(lambda m: _name_of(m.group(0), None, None),
                             str(e.get("text", "")))
        at = _PLACE_ID.sub(lambda m: _name_of(m.group(0), None, None), str(e.get("at") or ""))
        line = f"  * {text}" + (f" (at {at})" if at else "")
        cost = len(line) + (1 if lines else 0)
        if spent + cost > budget:
            break
        lines.append(line)
        spent += cost
    if not lines:
        return ""
    return header + "\n".join(reversed(lines))
