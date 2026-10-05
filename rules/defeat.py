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
  * **What they take.** Coin, and only coin, and only a person who is not the law: a
    robber robs, a wolf does not carry a purse, and the watch arrests rather than
    pockets. Coin because coin is what a robbery is for — the opening's robbed woman says
    "they want what I carry, and now they will have yours as well" — and because the
    other answers end a solo campaign: Fate's "without any of your stuff" strips a
    level-1 character of the armour and the weapon they need to play on. Gothic's weapon
    is not taken either; whether it should be is the owner's call. The coin goes INTO
    the robber's purse, not out of existence, so a player who finds them again can get
    it back.
  * **Then they go.** Out of the room through `Scene.move`, the only door, to somewhere
    off stage in the same town (`residency.offstage`), not destroyed: they are still
    the people who did it, and the campaign keeps them.

No number here is a model's and no state is the narrator's: the lines are the engine's
own sentences, built from what was actually moved.
"""
from __future__ import annotations

from . import attitude as attitude_mod
from . import goods
from . import states

# Where the winners go: off stage in the town they robbed you in. A leaf of the place id,
# read by nobody but `residency.is_offstage`.
OFFSTAGE_LEAF = "made-off"


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
    """Whether this winner takes coin: a person, and not the law."""
    from .engine import _a_person

    if actor.has_state(states.GUARD):
        return False
    return _a_person(getattr(actor, "from_template", "") or "")


def _names(actors) -> str:
    names = [a.name for a in actors]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def aftermath(scene, pc, coins=None) -> tuple[list[dict], list[str]]:
    """The winners act on their victory: the effects, and the sentences that say them.

    Called while the player is still down — they are robbed lying there, which is what
    "standing over you" means — and before the clock is moved, so whatever else the hour
    does it does to a scene the winners have already left. Returns ([], []) when nobody
    is standing over the player: then there was nobody to rob them and nobody to go.
    """
    winners = standing_over(scene)
    if not winners or pc is None:
        return [], []
    effects: list[dict] = []
    lines: list[str] = []
    robber = next((a for a in winners if _robs(a)), None)
    if robber is not None:
        purse = {k: int(v) for k, v in dict(pc.purse or {}).items() if int(v or 0) > 0}
        if purse:
            said = goods.purse_line(purse, coins)
            for coin, n in purse.items():
                robber.purse[coin] = int(robber.purse.get(coin, 0) or 0) + n
            pc.purse = {}
            effects.append({"kind": "took", "ref": robber.ref, "from": pc.ref,
                            "items": [f"{n} {coin}" for coin, n in purse.items()],
                            "why": "robbed while down"})
            lines.append(f"Your purse is gone: {robber.name} took {said}.")
        else:
            effects.append({"kind": "took", "ref": robber.ref, "from": pc.ref,
                            "items": [], "why": "robbed while down"})
            lines.append(f"{robber.name} went through your pockets and found no coin.")
    where = _offstage(scene)
    gone = []
    for a in winners:
        scene.move(a.ref, where)
        gone.append(a)
        effects.append({"kind": "left", "ref": a.ref, "to": where,
                        "why": "won the fight and went"})
    lines.append(f"{_names(gone)} {'has' if len(gone) == 1 else 'have'} gone.")
    return effects, [_upper_first(x) for x in lines]


def _offstage(scene) -> str:
    from . import places as places_mod
    from . import residency

    town = places_mod.location_of(getattr(scene, "at", "") or "") or scene.location_id
    return residency.offstage(town, OFFSTAGE_LEAF)


def _upper_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text
