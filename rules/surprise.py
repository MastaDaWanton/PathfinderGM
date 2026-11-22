"""The surprise round: who, at the start of a fight, is aware of an opponent.

The owner's ask (2026-11-22): "build the surprise round". The rule (Core Rulebook, Combat,
"Surprise", legacy.aonprd.com/coreRulebook/combat.html, checked 2026-11-22):

* "When a combat starts, if you are not aware of your opponents and they are aware of you,
  you're surprised." "Determining awareness may call for Perception checks or other checks."
* "If some but not all of the combatants are aware of their opponents, a surprise round
  happens before regular rounds begin. In initiative order (highest to lowest), combatants
  who started the battle aware of their opponents each take a standard or move action
  during the surprise round. You can also take free actions during the surprise round."
  "If no one or everyone starts the battle aware, there is no surprise round."
* "Combatants who are unaware at the start of battle don't get to act in the surprise
  round. Unaware combatants are flat-footed because they have not acted yet."

One decision, asked by both doors a fight opens by (`Engine._ensure_encounter`, the swing
and every arrival; `Engine._op_begin_encounter`, a declared or staged fight), so no door
can start a fight with a different answer. What it lays is two conditions through the one
applicator (rules/states.py TAGS): `surprised` (`state.unable.surprised`, no action) on the
unaware and `surprise round` (`turn.one-action`) on the aware, each for the one round, on
the one ticker. The turn order is the initiative rolled as ever; the unaware are walked past
because they cannot act, which is what `Scene._next_able` already does for the stunned.

**Awareness** is the hidden-state machinery's answer (rules/awareness.py), never a new one:
a combatant is aware when it sees, or has a hunch of, at least one opponent — a hunch is
Ultimate Intrigue's "aware of presence" (p.187), the second of its four steps. So a player
hidden by a won Stealth check, or invisible, who strikes a thug that never found them, opens
the fight with a surprise round; a thug who had found them does not give one. An AMBUSH (the
road, the wild, the hex, a dungeon's lair, the water) is the same question asked one step
earlier: the waiting side's Stealth against each observer's Perception, both rolled by the
engine in secret, -1 per 10 ft between them (Perception's table, CRB p.102) — Owlcat's
random-encounter ambush is the same contest (party Perception against the ambushers;
reported by players, not documented by Owlcat).

Prior art, and what was abandoned (docs/research/2026-11-22-surprise.md):
* D&D 5e (2014) kept a `surprised` condition for the first turn; the 2024 revision deleted
  it and gives the unaware Disadvantage on initiative instead — "barely a rule anymore".
* Pathfinder 2e dropped the surprise round entirely: Stealth is rolled FOR initiative.
* Baldur's Gate 3 keeps `Surprised` (no actions or reactions for a round), decided by line
  of sight and Stealth against Perception — the same shape built here.
Refused: either abandonment, because the owner asked for 1e by the book and both change the
rule rather than implement it; a `Scene.surprise` flag (law 2: the conditions are the record,
and "is this the surprise round" is asked of them, `running`).
"""
from __future__ import annotations

from . import awareness, states

ORIGIN = "rule:surprise"
SURPRISED_KEY = "surprised"
ROUND_KEY = "surprise round"


def running(scene) -> bool:
    """Whether the surprise round is under way: somebody in the fight holds one of its two
    states. Asked of the vocabulary, the conditions being the only record."""
    if not getattr(scene, "in_encounter", False):
        return False
    return any(a.has_state(states.SURPRISED) or a.has_state(states.ONE_ACTION_TURN)
               for a in scene.actors.values())


def _mods(actor, skill: str, **kw) -> list:
    try:
        return list(actor.skill_modifiers(skill, **kw))
    except Exception:  # noqa: BLE001 - a body with no sheet rolls its d20 alone
        return []


def decide(engine, sides: dict, ambushers=()) -> tuple[list[str], list[str], list]:
    """(aware refs, unaware refs, rolls) for the combatants on `sides`.

    `ambushers`: refs that lay in wait. Each rolls Stealth once; every combatant on another
    side rolls Perception once and notices an ambusher only by meeting its Stealth plus the
    distance (the codebase's convention, `awareness.judge`: a total that meets the DC finds).
    shortcut: an ambush rolls for the ambushers the door names (its first creature), not the
    ones `join_fight` brings in after; upgrade if a mixed party of sneaks and brutes ambushes.
    """
    scene = engine.scene
    refs = [r for refs_ in sides.values() for r in refs_
            if r in scene.actors and not scene.actors[r].is_down]
    side_of = {r: s for s, refs_ in sides.items() for r in refs_}
    rolls: list = []
    stealth: dict[str, int] = {}
    for r in ambushers:
        a = scene.actors.get(r)
        if a is None or r not in refs:
            continue
        roll = engine.dice.d20(_mods(a, "stealth"), label=f"{a.name} Stealth, lying in wait",
                               visibility="hidden")
        rolls.append(roll)
        stealth[r] = roll.total
    spot: dict[str, int] = {}
    aware, unaware = [], []
    for r in refs:
        me = scene.actors[r]
        foes = [scene.actors[o] for o in refs if side_of.get(o) != side_of.get(r)]
        if not foes:
            continue
        if not awareness.can_perceive(me):
            unaware.append(r)
            continue

        def notices(o) -> bool:
            if not (awareness.sees(scene, me, o) or awareness.has_hunch(me, o)):
                return False
            if o.ref not in stealth:
                return True
            if r not in spot:
                roll = engine.dice.d20(_mods(me, "perception", opposed=True),
                                       label=f"{me.name} Perception, against an ambush",
                                       visibility="hidden")
                rolls.append(roll)
                spot[r] = roll.total
            gap = engine._gap_ft(me, o)
            return spot[r] >= stealth[o.ref] + (int(gap) // 10 if gap else 0)

        (aware if any(notices(o) for o in foes) else unaware).append(r)
    return aware, unaware, rolls


def begin(engine, sides: dict, ambushers=()) -> dict | None:
    """Decide, and lay the surprise round when some but not all are aware.

    Returns the record for the tell ({"aware", "unaware", "rolls"}), or None when there is
    no surprise round — "If no one or everyone starts the battle aware"."""
    aware, unaware, rolls = decide(engine, sides, ambushers)
    if not aware or not unaware:
        return None
    scene = engine.scene
    for r in unaware:
        scene.actors[r].add_condition(SURPRISED_KEY, rounds=1, source=ORIGIN, origin=ORIGIN)
    for r in aware:
        scene.actors[r].add_condition(ROUND_KEY, rounds=1, source=ORIGIN, origin=ORIGIN)
    return {"aware": aware, "unaware": unaware, "rolls": rolls}


def tell(scene, record: dict) -> str:
    """The narrator's sentence: who acts first and who was caught unaware. No numbers
    (owner ruling 2026-11-21, mechanics off the story page)."""
    def names(refs) -> str:
        said = [scene.actors[r].name for r in refs if r in scene.actors]
        return said[0] if len(said) == 1 else ", ".join(said[:-1]) + " and " + said[-1]

    one = len(record["unaware"]) == 1
    alone = len(record["aware"]) == 1
    return (f"Surprise round: {names(record['aware'])} "
            f"{'acts first, with one action' if alone else 'act first, one action each'}; "
            f"{names(record['unaware'])} {'is' if one else 'are'} caught unaware and "
            f"cannot act until the first full round.")
