"""What a character knows about each herb (docs/herbalism-revamp-plan.md §8).

SCAFFOLD. The discovery lane owns this module and replaces these bodies. The function
signatures are the contract in docs/herbalism-contracts.md, and the other lanes call them
from day one: the bench asks `unknown_count` for a satchel tile and calls `reveal` when a
product shows what is in it. Until the discovery lane lands, everything reads as known,
which is exactly how the game behaved before the revamp, so nothing regresses meanwhile.

A property is one of an ingredient's effect lines (`Ingredient.pairs`), keyed by its
position: "p0", "p1" ... The key is positional on purpose: the corpus stores effects in a
fixed order, and a key that is a slug of the text would break the moment an author
corrected a typo in it.
"""
from __future__ import annotations


def property_keys(ingredient) -> list[str]:
    """Every property this ingredient has, as keys."""
    return [f"p{i}" for i in range(len(getattr(ingredient, "pairs", []) or []))]


def known_keys(actor, ingredient) -> list[str]:
    """The keys this actor knows. SCAFFOLD: all of them."""
    return property_keys(ingredient)


def unknown_count(actor, ingredient) -> int:
    """How many of this ingredient's properties the actor does not yet know."""
    known = set(known_keys(actor, ingredient))
    return sum(1 for k in property_keys(ingredient) if k not in known)


def reveal(actor, ingredient_id: str, keys, how: str) -> list[str]:
    """Record that `keys` are now known, and how. Returns the keys that were NEW, so the
    caller can say "New: ..." only for real discoveries and pay mastery for firsts."""
    entry = actor.herb_known.setdefault(str(ingredient_id), {"keys": [], "how": {}})
    have = set(entry.get("keys") or [])
    new = [k for k in keys if k not in have]
    if new:
        entry["keys"] = sorted(have | set(new), key=lambda k: int(k[1:]) if k[1:].isdigit() else 0)
        for k in new:
            entry.setdefault("how", {})[k] = str(how)
    return new
