"""Where a thing is, and who it belongs to: the questions every handover asks first.

Lane A of the 2026-10-03 playtest (docs/items-have-owners.md). The owner's `items` save
ended with

    goods: {"brunt of the weight": 1, "crate": 1, "pouch": 1, "coins": 1}   purse: {}

after a session in which Kesst carried a crate to a clerk, sold it and pocketed the
payment. Every one of those four lines was a `give` with one end missing: "I take the
brunt of the weight" minted a thing out of a figure of speech, "I pocket the coins" made
an ITEM called coins, the pouch held nothing, and "I drop the Brunt of the weight on the
ground" handed a second one to the smith while Kesst kept hers, because the two names
differed only in a capital letter.

Inform 7 answers "whose is it" by walking up the holder chain (the "can't take people's
possessions" rule reads no stored owner: if a person holds it, it is theirs), and TADS 3
moves everything through one `moveInto`. This module is the asking half of that funnel:
`Engine._op_give` is the moving half. It reads three places a thing can be — a person's
goods, the props ledger (`Scene.props`: lying here, or in somebody's hands), and a
container's `contents` on a props record — and one place it can only be inferred from, a
person's own label ("the merchant with a heavy pack").

Coin is a number (Inform's Recipe Book §9.4: money "behaves more like a liquid than a set
of items"; Circle keeps gold on the character). A coin OBJECT exists only while it lies
somewhere or sits in a pouch, as a props record whose `contents` carries a purse — Circle's
`ITEM_MONEY`, which turns back into the number when it is picked up. NetHack went the other
way in 3.6 (gold as an inventory object) and its fixes file is the measurement of what that
costs.
"""
from __future__ import annotations

import re

# Words in front of a noun that do not change which thing it is. "the Brunt of the weight"
# and "brunt of the weight" are one thing: the 2026-10-03 drop missed the carried one by
# its capital B and copied it to the smith instead.
_DETERMINERS = re.compile(
    r"^(?:(?:the|a|an|my|your|his|her|their|its|our|some|this|that|these|those)\s+)+",
    re.I)


def plain(name) -> str:
    """A thing's name as two mentions of it are compared: lower case, one space, no
    leading article or possessive, no trailing punctuation."""
    text = " ".join(str(name or "").replace("_", " ").split()).lower().strip(" .,;:!?'\"")
    return _DETERMINERS.sub("", text).strip()


def same(a, b) -> bool:
    """Whether two mentions name the same thing. A plural `s` on either is forgiven — "the
    coins" picks up the coin record — and nothing looser: "pack" is not "heavy pack" here,
    because the looser match is `head_of`'s and is only asked where a near miss costs
    nothing (a person's label)."""
    x, y = plain(a), plain(b)
    if not x or not y:
        return False
    return x == y or x.rstrip("s") == y.rstrip("s")


def key_in(store, name) -> str | None:
    """The key in a goods-shaped dict that names this thing, exact first, else by
    `same`. None when nothing there is it."""
    if not store:
        return None
    raw = " ".join(str(name or "").split())
    if raw in store:
        return raw
    for key in store:
        if same(key, raw):
            return key
    return None


def named_among(store, phrase) -> str | None:
    """The key in `store` whose whole name stands, word for word, in `phrase` — the
    longest such name, so "a red apple" finds "red apple" before "apple". A plural `s` is
    forgiven on each word, as `same` forgives it. None when no key's name is in the phrase.

    The store is the closed vocabulary here, never the phrase: what the holder ACTUALLY
    carries is matched against the words, the way a spell's name is matched against the
    catalogue (`judgement.spell_in_words`). Measured 2026-10-08 (the deeds lane, local
    model): "I take another apple from the fruit seller" and "one of the apples" were
    planned as `give item="another apple"` and `item="one of the apples"`; neither is
    `same` as the seller's "apple" line, so the seller kept every apple and one was minted
    out of nothing into the player's pack. Asked only after `key_in` finds nothing."""
    if not store:
        return None
    said = [w.rstrip("s") for w in re.findall(r"[a-z0-9][a-z0-9'-]*", plain(phrase))]
    if not said:
        return None
    best: tuple[int, str] | None = None
    for key in store:
        want = [w.rstrip("s") for w in re.findall(r"[a-z0-9][a-z0-9'-]*", plain(key))]
        n = len(want)
        if not n or n > len(said):
            continue
        if any(said[i:i + n] == want for i in range(len(said) - n + 1)):
            if best is None or n > best[0]:
                best = (n, key)
    return best[1] if best is not None else None


# --- what a phrase names -------------------------------------------------------------------

def head_of(name) -> str:
    """The head noun of a thing's name: the last word, except before "of", where English
    puts the head first ("a pouch of coins" is a pouch, "the brunt of the weight" is a
    brunt) — unless the word before "of" only measures the thing ("a chunk of wood" is
    wood, "a loaf of bread" is bread)."""
    words = re.findall(r"[a-z][a-z'-]*", plain(name))
    if not words:
        return ""
    if "of" in words[1:]:
        at = words.index("of", 1)
        before, after = words[at - 1], words[at + 1:]
        after = [w for w in after if w not in ("the", "a", "an", "some", "my", "his",
                                               "her", "their")]
        if before in MEASURES and after:
            return after[-1]
        return before
    return words[-1]


# The words that only measure what follows "of". Written out, not guessed: each is a way
# English counts a thing that is not itself the thing. Containers are deliberately NOT
# here: "a pouch of coins" is a pouch with coin in it, and "a crate of fish" is a crate
# that is sold whole — reading through them made the pouch vanish into its contents.
MEASURES = frozenset("""
chunk chunks piece pieces bit bits lump lumps length lengths loaf loaves slice slices
handful handfuls fistful pile piles stack stacks heap heaps few couple pair pairs set sets
bundle bundles roll rolls coil coils sheet sheets scrap scraps shard shards splinter
splinters sprig sprigs bunch bunches cup cups mug mugs flask flasks bottle bottles jar jars
skin skins dose doses measure measures
""".split())

# Containers: things that hold other things. A pouch, a purse or a sack handed over with
# coin in it carries the coin (item 4); a crate is cargo, and is not here — "the crate"
# is a thing sold whole, and nobody empties one into a coin purse.
CONTAINERS = frozenset("""
pouch purse sack bag satchel wallet coffer chest box casket strongbox lockbox moneybag
money-bag coinpurse
""".split())

# Money with no denomination named. "coins", "the payment", "a pouch of coin": currency,
# never a goods line (item 3). A denomination ("gold", "3 sp") is `goods.coin_named`'s.
_MONEY_WORDS = frozenset("coin coins money cash payment payments pay wages earnings "
                         "takings fee fees silver gold copper".split())
# A coin qualified by a material no purse counts is a token, not money: the lead coin a
# cage owner pressed on Sam (2026-09-30) is a thing to keep, not a copper piece.
_TOKEN_MATERIALS = frozenset("lead brass iron wooden wood bone clay tin glass stone "
                             "lucky strange foreign ancient old rare gaming".split())


def is_container(name) -> bool:
    return head_of(name) in CONTAINERS


def is_money(name) -> bool:
    """Whether this phrase is coin with no amount and no denomination of its own: "the
    coins", "the payment", "a handful of coins", "the money". A container of coin ("a
    pouch of coins") is NOT — it is a pouch, and `container_of_money` reads it."""
    words = re.findall(r"[a-z][a-z'-]*", plain(name))
    if not words or is_container(name):
        return False
    head = head_of(name)
    if head not in _MONEY_WORDS:
        return False
    if head in ("silver", "gold", "copper") and len(words) > 1:
        return False                    # "silver ring" is not money; "gold" alone is
    return not (set(words) & _TOKEN_MATERIALS)


def container_of_money(name) -> str:
    """"pouch" for "a pouch of coins", "a purse full of gold", "the sack of money"; ""
    when the phrase is not a container with coin in it."""
    words = re.findall(r"[a-z][a-z'-]*", plain(name))
    if not words or head_of(name) not in CONTAINERS:
        return ""
    if not set(words) & _MONEY_WORDS:
        return ""
    return head_of(name)


# --- what a person's own label says they carry ----------------------------------------------

# "the merchant with a heavy pack", "the servant carrying jugs two at a time": a label the
# narration gave a person is a statement about what is in their hands, and the only one
# the engine can read without a model. The narration of 2026-10-03 hauled "the heavy pack
# onto your own shoulders… the merchant's eyes widen" and nothing recorded the pack as his.
_CARRIES = re.compile(
    r"\b(?:with|carrying|holding|hauling|bearing|clutching|lugging|shouldering)\s+"
    r"(?:(?:a|an|the|his|her|their|two|three|some)\s+)?"
    r"([a-z][a-z'-]*(?:\s+[a-z][a-z'-]*){0,2}?)"
    r"(?=\s+(?:two|at|on|in|over|under|across|from|to|and|by|who|that|which)\b|[,.;]|$)",
    re.I)


def carried_by_label(label) -> list[str]:
    """The things a person's label puts in their hands, as written: ["heavy pack"] for
    "merchant with a heavy pack". Empty for "the clerk of the counting house"."""
    return [" ".join(m.group(1).split()).lower()
            for m in _CARRIES.finditer(str(label or ""))]


def label_carries(label, name) -> str:
    """The thing in this label that `name` asks for, by its head noun, or ""."""
    want = head_of(name)
    if not want:
        return ""
    for thing in carried_by_label(label):
        if head_of(thing) == want or head_of(thing).rstrip("s") == want.rstrip("s"):
            return thing
    return ""


# --- containers on the props ledger ----------------------------------------------------------

def contents(rec) -> dict:
    """A props record's contents as {"purse": {...}, "goods": {...}}, created empty on
    first use. Only ever asked of a record that is a container or a coin pile."""
    box = rec.setdefault("contents", {})
    box.setdefault("purse", {})
    box.setdefault("goods", {})
    return box


def coin_in(rec) -> int:
    """How much coin a record holds, in copper. 0 for anything without contents."""
    from . import goods

    return goods.in_copper(((rec or {}).get("contents") or {}).get("purse") or {})


def empty_coin(rec) -> dict:
    """Take every coin out of a record and return it as a purse dict."""
    box = contents(rec)
    purse = dict(box.get("purse") or {})
    box["purse"] = {}
    return purse
