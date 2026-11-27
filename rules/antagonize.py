"""Antagonize (Ultimate Magic; aonprd.com FeatDisplay.aspx?ItemName=Antagonize, read
2026-11-27): "You can make Diplomacy and Intimidate checks to make creatures respond to you
with hostility. No matter which skill you use, antagonizing a creature takes a standard
action that does not provoke attacks of opportunity, and has a DC equal to 10 + the target's
Hit Dice + the target's Wisdom modifier. You cannot make this check against a creature that
does not understand you or has an Intelligence score of 3 or lower ... This is a
mind-affecting effect.

Diplomacy: You fluster your enemy. For the next minute, the target takes a -2 penalty on
all attacks rolls made against creatures other than you ...
Intimidate: The creature flies into a rage. On its next turn, the target must attempt to
make a melee attack against you, make a ranged attack against you, target you with a spell,
or include you in the area of a spell ... The effect ends as soon as the creature melee
attacks you. Once you have targeted a creature with this ability, you cannot target it again
for 1 day."

Both results are the app's compulsion (rules/compulsion.py): a pull towards the antagonist,
priced on every attack at anybody else. The Diplomacy fluster is exactly that shape at -2
for ten rounds. The Intimidate rage's "must" is the same pull for its one turn — owner call
(b6-rules): the compulsion module's own rule, "a compulsion penalises, it never prohibits",
stands over the book's "must"; the price is the compulsion's -4.

A skill use with its own door (rules/skilluses.py OWN_DOORS, the `antagonize` flag on a
Diplomacy or Intimidate check). The day's bar is an effect on the target, `antagonized.<ref>`,
on the one ticker.
"""
from __future__ import annotations

from .activeeffect import ActiveEffect

TAG = "skill.antagonize"                 # the feat document's tag
FLUSTER_ROUNDS = 10                      # "For the next minute"
DAY_ROUNDS = 14400
ROWS = {"diplomacy": "skill.diplomacy.antagonize", "intimidate": "skill.intimidate.antagonize"}


def _barred(engine, actor, target) -> str:
    from . import animals, states

    if target is None or target is actor:
        return "Antagonize is made at another creature: name who."
    if not engine._against(actor, target):
        return f"{target.name} is on {actor.name}'s side; there is no one to antagonize."
    if not animals.understands(target, actor) or int(target.abilities.get("int", 10) or 0) <= 3:
        return (f"{target.name} cannot understand {actor.name}'s words, and Antagonize "
                f"needs a mind that does.")
    immune = states.immune_to(target, "", descriptors=("mind-affecting",))
    if immune:
        return f"{target.name} is immune to mind-affecting effects ({immune})."
    if target.has_state(f"antagonized.{actor.ref}"):
        return (f"{actor.name} has antagonized {target.name} today already; not again for "
                f"a day.")
    return ""


def door(engine, intent, actor, mods, partial):
    """The `check` op's Antagonize: the row's DC, a standard action, the compulsion."""
    from . import attitude as attitude_mod
    from . import compulsion
    from . import skilluses
    from .engine import Outcome

    skill = str(intent.params.get("skill") or "").lower()
    if not actor.has_state(TAG):
        return engine._refuse(intent, f"{actor.name} does not have the Antagonize feat. "
                                      f"Nothing is rolled.")
    target = engine.scene.actors.get(str(intent.target or ""))
    why = _barred(engine, actor, target)
    if why:
        return engine._refuse(intent, why + " Nothing is rolled.")
    if engine.scene.in_encounter:
        spent = skilluses._no_action_left(engine, actor, "standard", "antagonizing")
        if spent:
            return engine._refuse(intent, spent, code="action_spent")
    dc = attitude_mod.intimidate_dc(target)
    roll = engine._roll_or_suspend(intent, actor, list(mods),
                                   label=f"{skill.title()} check (Antagonize)", dc=dc,
                                   partial=partial)
    if engine.scene.in_encounter:
        skilluses._spend_action(engine, actor, "standard")
    target.apply_effect(ActiveEffect(
        name="antagonized", kind="situation", key=f"antagonized-{actor.ref}",
        source=f"{actor.name}'s Antagonize", origin="rule:feat-antagonize",
        duration="rounds", rounds_left=DAY_ROUNDS, tags=(f"antagonized.{actor.ref}",)))
    effects = [{"ref": target.ref, "kind": "antagonize", "skill": skill, "dc": dc,
                "total": roll.total, "beat": roll.total >= dc,
                "origin": "rule:feat-antagonize"}]
    if roll.total < dc:
        return Outcome(intent_id=intent.id, op="check", actor=actor.ref, rolls=[roll],
                       effects=effects,
                       tell=f"{actor.name} tries to get under {target.name}'s skin "
                            f"({skill.title()} {roll.total} against DC {dc}); it does not "
                            f"take.",
                       because=intent.because)
    if skill == "diplomacy":
        compulsion.add(target, actor.ref, penalty=2, rounds=FLUSTER_ROUNDS,
                       source="Antagonize (flustered)", why="flustered by a taunt")
        said = (f"{target.name} is flustered: -2 on attacks at anyone but {actor.name} "
                f"for a minute.")
    else:
        # "On its next turn": this round's and the next one's top (two ticks).
        compulsion.add(target, actor.ref, penalty=compulsion.PENALTY, rounds=2,
                       source="Antagonize (enraged)", why="enraged by a threat")
        said = (f"{target.name} flies into a rage at {actor.name}, and turns on them next "
                f"(an attack at anyone else is at -{compulsion.PENALTY}).")
    effects.append({"ref": target.ref, "kind": "compulsion", "by": actor.ref,
                    "origin": "rule:feat-antagonize"})
    return Outcome(intent_id=intent.id, op="check", actor=actor.ref, rolls=[roll],
                   effects=effects,
                   tell=f"{actor.name} antagonizes {target.name} ({skill.title()} "
                        f"{roll.total} against DC {dc}). {said}",
                   because=intent.because)
