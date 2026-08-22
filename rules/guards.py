"""Getting between a blow and the person it was aimed at.

Damage used to be a straight line: roll it, subtract damage reduction, spend temporary hit
points, take the rest. That line has no room in it for anything that wants to *change the
blow* — a Coagulator throwing themselves in front of a companion, a ward that turns a cut
into a bruise, a bloodlink that makes two creatures share what one of them suffers. Blood
Bending's whole Coagulator path is those three things, and none of them can be expressed as
a modifier on the attacker or a subtraction on the defender.

So the funnel gets a hook. `Engine._apply_damage` was already the one place every point of
damage in the game passes through — weapon hits, hazards, the `damage` op — which is why
this is one change rather than one per damage source. A guard may rewrite a packet before
it lands, and everything it does is reported, because damage that quietly became something
else is the single most confusing thing that can happen to a player.

**Order.** Interception happens *before* damage reduction and temporary hit points, not
after. A blow redirected to somebody else has to meet that person's damage reduction, not
the original target's — resolving DR first and then moving the leftovers would apply the
wrong creature's armour to it. The one exception is `convert`, which changes what kind of
damage it is and so has to happen before anything that reads the type.

**Guards do not stack past the packet.** Each guard sees what the previous one left, and a
packet reduced to nothing stops being offered around. Two absorbs of 10 against a 12-point
hit consume 10 and 2, not 10 and 10.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import grid as gridmod

# What each kind does, for a developer. Not for a player: an early version used these as
# the `tell` and printed "the guardian's ward eats up to `amount` of it" — backticks and
# all — into the narration. Player-facing wording is `PHRASE`.
KINDS = {
    "redirect": "The guardian takes the blow instead, in full.",
    "share": "The guardian takes a share of it; the target still takes the rest.",
    "absorb": "The guardian's ward eats up to `amount` of it and nobody takes that part.",
    "convert": "The damage becomes non-lethal instead of lethal.",
}

PHRASE = {
    "redirect": "to take the blow",
    "share": "to share what lands",
    "absorb": "to soak what lands",
    "convert": "to blunt what lands",
}


@dataclass
class Guard:
    """One standing arrangement about damage aimed at somebody.

    Held on the scene rather than on either actor, because a guard is a *relationship*.
    Storing it on the guardian loses it when the protected creature is the one being
    looked up; storing it on both is two copies to keep level.
    """
    guardian: str
    protects: str
    kind: str = "redirect"
    # For `absorb`, how much it eats. For `share`, the fraction the guardian takes, as a
    # percentage — 50 is the obvious one and is why this is not a bool.
    amount: int = 0
    # How far the guardian can be and still interpose. 5 feet — adjacent — unless the
    # ability says otherwise. Ignored on a scene with no map, where the guard simply works:
    # refusing it there would make the ability silently stop existing outside a tactical
    # fight, which is worse than being generous.
    range_ft: int = 5
    # Spent on use, if it is a limited thing. Named so the engine can charge a pool.
    pool: str = ""
    uses_left: int | None = None
    source: str = ""

    def as_dict(self) -> dict:
        return {"guardian": self.guardian, "protects": self.protects, "kind": self.kind,
                "amount": self.amount, "range_ft": self.range_ft, "pool": self.pool,
                "uses_left": self.uses_left, "source": self.source}


def from_dict(d: dict) -> Guard:
    return Guard(
        guardian=str(d.get("guardian", "")), protects=str(d.get("protects", "")),
        kind=str(d.get("kind", "redirect")), amount=int(d.get("amount", 0) or 0),
        range_ft=int(d.get("range_ft", 5) or 0), pool=str(d.get("pool", "")),
        uses_left=None if d.get("uses_left") is None else int(d["uses_left"]),
        source=str(d.get("source", "")),
    )


@dataclass
class Packet:
    """A quantity of damage on its way somewhere, and who it is currently aimed at.

    Mutable and passed around on purpose: interception is a pipeline, and the alternative
    — returning a new packet from every stage — made the "who has already had a go at
    this" bookkeeping worse than the thing it was avoiding.
    """
    amount: int
    dtype: str = "untyped"
    traits: tuple[str, ...] = ()
    lethality: str = "lethal"
    target: str = ""
    notes: list[dict] = field(default_factory=list)


def in_range(scene, guardian: str, protects: str, range_ft: int) -> bool:
    """Can the guardian actually reach? True on a scene with no map — see `Guard.range_ft`."""
    if not scene.has_grid:
        return True
    here, there = scene.positions.get(guardian), scene.positions.get(protects)
    if here is None or there is None:
        return True
    a, b = scene.actors.get(guardian), scene.actors.get(protects)
    if a is None or b is None:
        return False
    return gridmod.distance_between(here, a.size, there, b.size) <= range_ft


def eligible(scene, target_ref: str) -> list[Guard]:
    """Guards that could act on a blow aimed at this creature, in the order they apply.

    `convert` first, because it changes what the damage *is* and everything after reads
    the type. Then `absorb`, then `share`, then `redirect` — cheapest intervention first,
    so a ward that can simply eat the blow does, rather than a companion needlessly
    throwing themselves in front of something harmless.
    """
    order = {"convert": 0, "absorb": 1, "share": 2, "redirect": 3}
    out = []
    for g in scene.guards:
        if g.protects != target_ref or g.kind not in KINDS:
            continue
        if g.uses_left is not None and g.uses_left <= 0:
            continue
        guardian = scene.actors.get(g.guardian)
        if guardian is None or not guardian.can_act():
            continue
        if not in_range(scene, g.guardian, g.protects, g.range_ft):
            continue
        out.append(g)
    return sorted(out, key=lambda g: order[g.kind])


def intercept(scene, packet: Packet) -> list[Packet]:
    """Run a packet past everybody with a claim on it.

    Returns the packets that actually land, which may be more than one — a `share` splits
    a blow into two, aimed at two different creatures — and may be none, if a ward ate it
    whole. Callers must handle both; assuming exactly one back is the mistake this return
    type exists to prevent.
    """
    landing = [packet]
    done: set[int] = set()

    # A redirected packet is offered to the new target's guards too — that is how a chain
    # of protectors works — but never twice to the same guard, or two Coagulators
    # protecting each other would bounce a blow between them forever.
    while True:
        progressed = False
        for pk in list(landing):
            if pk.amount <= 0:
                continue
            for g in eligible(scene, pk.target):
                if id(g) in done:
                    continue
                done.add(id(g))
                made = _apply(scene, g, pk)
                if made is None:
                    continue
                progressed = True
                if made is not pk:
                    landing.append(made)
                break
        if not progressed:
            break

    return [pk for pk in landing if pk.amount > 0 or pk.notes]


def _apply(scene, g: Guard, pk: Packet) -> Packet | None:
    """Let one guard have its go. Returns a new packet if it created one, else the
    original, or None if the guard turned out not to apply after all."""
    guardian = scene.actors[g.guardian]

    if g.kind == "convert":
        if pk.lethality == "nonlethal":
            return None
        pk.lethality = "nonlethal"
        pk.notes.append({"guard": g.source or "ward", "kind": "convert",
                         "by": g.guardian, "amount": pk.amount})
        _spend(guardian, g)
        return pk

    if g.kind == "absorb":
        eaten = min(pk.amount, max(0, g.amount))
        if eaten <= 0:
            return None
        pk.amount -= eaten
        pk.notes.append({"guard": g.source or "ward", "kind": "absorb",
                         "by": g.guardian, "amount": eaten})
        _spend(guardian, g)
        return pk

    if g.kind == "share":
        # Rounded *down* to the guardian, so a share of an odd number never costs the two
        # of them more in total than the blow was worth.
        taken = min(pk.amount, pk.amount * max(0, min(100, g.amount)) // 100)
        if taken <= 0:
            return None
        pk.amount -= taken
        pk.notes.append({"guard": g.source or "shared", "kind": "share",
                         "by": g.guardian, "amount": taken})
        _spend(guardian, g)
        return Packet(amount=taken, dtype=pk.dtype, traits=pk.traits,
                      lethality=pk.lethality, target=g.guardian,
                      notes=[{"guard": g.source or "shared", "kind": "share_received",
                              "from": pk.target, "amount": taken}])

    if g.kind == "redirect":
        was = pk.target
        pk.target = g.guardian
        pk.notes.append({"guard": g.source or "interposed", "kind": "redirect",
                         "by": g.guardian, "from": was, "amount": pk.amount})
        _spend(guardian, g)
        return pk

    return None


def _spend(guardian, g: Guard) -> None:
    if g.uses_left is not None:
        g.uses_left -= 1
    if g.pool:
        guardian.spend_pool(g.pool, 1)


def describe(notes: list[dict]) -> str:
    """The sentence a player needs when their damage turned into something else.

    Damage that quietly became something different is the most confusing thing that can
    happen at a table, so every intervention says so by name.
    """
    bits = []
    for n in notes:
        kind, who = n.get("kind"), n.get("guard", "")
        if kind == "convert":
            bits.append(f"turned non-lethal by {who}")
        elif kind == "absorb":
            bits.append(f"{n['amount']} absorbed by {who}")
        elif kind == "share":
            bits.append(f"{n['amount']} shared through {who}")
        elif kind == "share_received":
            bits.append(f"{n['amount']} through {who}")
        elif kind == "redirect":
            bits.append(f"taken by {who}")
    return ", ".join(bits)


__all__ = ["Guard", "KINDS", "Packet", "describe", "eligible", "from_dict", "in_range",
           "intercept"]
