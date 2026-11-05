"""Guards who see a wanted character move to arrest them (owner ruling 2026-11-01).

Reported the same day (Corvin, turns 56-61): wanted in Reedsink for a killing, the player
stood beside the captain and two guards for six turns — "go to them", "what do you want
with me", "Address the guardsmen directly", "walk away" — and the law did nothing. A
warrant bit at the gate, at the counter and in a fight (docs/wanted.md), and nowhere a
guard could simply see you. The doc's own open list said so: "the watch does not come
looking".

## What the traditions do (researched 2026-11-01)

Every crime system read gives the same four answers when a guard confronts a wanted
character, and this is them:

* Skyrim (UESP, Crime): pay the bounty, go to jail, resist arrest, persuade (small
  bounties only; the bounty stays) or bribe. Resisting turns every guard in the area
  hostile; sheathing weapons brings the arrest dialogue back.
* Oblivion (UESP, Crime): pay, jail or resist; resisting meant "life forfeit" — softened in
  Skyrim, which is the abandoned idea here: resisting is a fight, not a death sentence.
* Kingdom Come: Deliverance: pay the fine, go to jail, talk or scare your way out, flee,
  or surrender; a failed persuasion leaves the other choices open.
* Baldur's Gate 3: Persuasion, Deception or Intimidation, submit to jail where there is
  one, or fight; crimes belong to the character who did them.

Pathfinder 1e has no arrest, trial, fine or jail procedure (the GameMastery Guide covers
how a watch is staffed; Ultimate Campaign's crime tables list fines and imprisonment with
no amounts). What it has is the talk: Diplomacy's Make Request (CRB p.93) and Bluff
against Sense Motive (CRB p.90), which the engine already rolls. So this module adds no
new roll and no new number: it is the confrontation, and what each answer does.

## The answers

The confrontation is a state the player holds (`states.ARRESTING`, one effect through the
applicator, payload: the town, where it began, and who came), granted at the end of the
batch in which a guard who can see them (`awareness.sees`) stands here. The player's NEXT
batch answers it:

* **fight** — any blow: the fight opens and the law joins it (`Engine._law_joins`);
* **run** — they are no longer where it began: away, the warrant still standing, and the
  next guard who sees them tries again;
* **talk** — a Diplomacy or Bluff check by the player (`talked`, from `Engine._drive`):
  made, the guards stand down for the day (`states.STOOD_DOWN`) and the warrant stays, as
  Skyrim's persuade leaves the bounty; missed, they take you;
* **go quietly** — anything else, the plain surrender and the turn spent ignoring them
  alike: taken (`taken`).

Taken is held and questioned, then judged (rules/trial.py, the owner's ruling of 2026-11-01).
Until that ruling it was one night held and release at morning for want of proof, whatever
had been done; the grace days survive as the release of a player the watch cannot prove
anything against. The officers are the law too: `role.guard.officer` answers every
`has_state(GUARD)` question by the prefix, so a captain or sergeant comes for the player as
a guard does.
"""
from __future__ import annotations

from . import states
from .activeeffect import ActiveEffect

SOURCE = "rule:arrest"
# The skills that talk a guard round (CRB p.93 Make Request, p.90 Bluff). Intimidate is not
# here: the owner named the two, and frightening the watch is a different crime.
TALK_SKILLS = frozenset({"diplomacy", "bluff"})
# Where the taken are held lives in content/rules/law.json (`holds`), read by the trial.
# How long the watch leaves a released prisoner alone, and a talked-down patrol.
GRACE_DAYS = 3
STOOD_DOWN_DAYS = 1


def _town(engine) -> str:
    from . import places as places_mod

    return places_mod.location_of(engine.scene.at or "") or engine.scene.location_id


def _town_name(engine) -> str:
    found = engine.world.get(engine.scene.location_id) if engine.world else None
    return str(getattr(found, "name", "") or "the town")


def pending(actor) -> ActiveEffect | None:
    """The arrest the player has not answered yet, or None."""
    for e in getattr(actor, "effects", ()) or ():
        if e.source == SOURCE and states.ARRESTING in (e.tags or ()):
            return e
    return None


def stood_down(actor, town: str) -> bool:
    return actor.has_state(states.stood_down_tag(town))


def guards_who_see(engine, pc) -> list:
    """The law standing here who can see the player: `role.guard`, on their feet, not
    travelling with them, and seeing them (a hidden or invisible player is not seen)."""
    from . import awareness

    out = []
    for a in engine.scene.actors.values():
        if a.is_pc or a.is_down or not a.has_state(states.GUARD):
            continue
        if a.has_state(states.TRAVELS_WITH_YOU):
            continue
        if not awareness.sees(engine.scene, a, pc):
            continue
        out.append(a)
    return out


def _names(people) -> str:
    names = [p.name for p in people]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def stand_down(engine, pc, town: str, days: int, why: str) -> None:
    pc.remove_effects(source=SOURCE)
    pc.apply_effect(ActiveEffect(
        name=why, kind="situation", key=f"stood-down:{town}", source=SOURCE, origin=SOURCE,
        duration="rounds", rounds_left=days * 24 * 60 * engine.scene.ROUNDS_PER_MINUTE,
        tags=(states.stood_down_tag(town),)))


def settle(engine) -> list:
    """The law's move at the end of a batch: an unanswered arrest answered (run, or taken),
    or a new one begun. Empty when nothing is owed. Out of a fight only — in one, the
    warrant's reader is `_law_joins`, and a confrontation still pending ends there."""
    from .engine import Outcome

    from . import trial

    scene = engine.scene
    pc = scene.pc()
    if pc is None or scene.awaiting:
        return []
    # Held already: the trial owns the batch (rules/trial.py).
    if trial.custody(pc) is not None:
        return trial.settle(engine)
    held = pending(pc)
    if scene.in_encounter:
        if held is not None:
            pc.remove_effects(source=SOURCE)
        return []
    town = _town(engine)
    law = states.standing_with_the_law(pc, town)
    if held is not None:
        pay = dict(held.payload or {})
        who = [scene.people[r] for r in pay.get("by") or () if r in scene.people]
        if law != "wanted":
            pc.remove_effects(source=SOURCE)
            return [Outcome(intent_id="", op="arrest", effects=[{"kind": "arrest",
                                                                "ended": "cleared"}],
                            tell=f"{_names(who) or 'The watch'} let it drop: there is no "
                                 f"warrant to take you on now.")]
        # Walked to the watch's own hold: that is going quietly, not running. Measured live
        # 2026-11-01 on the owner's save: "I raise my hands and go quietly with the guards"
        # was planned as a travel to the guardhouse, and the arrest told it as "You are
        # away before the guardsmen can lay hands on you".
        hold = trial._place_by(engine, trial.document()["holds"])
        if hold is not None and scene.at == hold.id and scene.at != pay.get("at"):
            return [taken(engine, pc, held, who, town)]
        if scene.at != pay.get("at"):
            pc.remove_effects(source=SOURCE)
            return [Outcome(intent_id="", op="arrest",
                            effects=[{"kind": "arrest", "ended": "fled"}],
                            tell=f"You are away before {_names(who) or 'the watch'} can lay "
                                 f"hands on you. The warrant still stands, and the next "
                                 f"guard who sees you will try again.")]
        return [taken(engine, pc, held, who, town)]
    if law != "wanted" or stood_down(pc, town):
        return []
    seen = guards_who_see(engine, pc)
    if not seen:
        return []
    pc.apply_effect(ActiveEffect(
        name="the watch is taking you in", kind="situation", key=f"arrest:{town}",
        source=SOURCE, origin=SOURCE, duration="until-dismissed",
        tags=(states.ARRESTING,),
        payload={"town": town, "at": scene.at, "by": [a.ref for a in seen]}))
    return [Outcome(
        intent_id="", op="arrest",
        effects=[{"kind": "arrest", "begun": True, "by": [a.ref for a in seen],
                  "origin": SOURCE}],
        # The choices in the one form (`trial.choices`): said apart, as still to choose.
        tell=(f"{who_come(seen, pc.name)} {pc.name} is wanted in "
              f"{_town_name(engine)}, and to be taken in. "
              + trial.choices(pc.name, ["go quietly",
                                        "talk their way out (Diplomacy or Bluff)",
                                        "run", "fight"])))]


_COUNT = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}


def who_come(seen, pc_name: str) -> str:
    """"Three of the watch come for Corvin, and only they: Pallo Farrow, the guardsman and the
    second guardsman." — who comes, counted and said as the watch, never a bare run of
    names.

    Measured on the 2026-11-05 rerun: "Pallo Farrow, the guardsman and the second guardsman
    come for Corvin T." came back "Pallo Farrow, Vessa Duskwatch, and the two Grippli
    guardsmen" (the shopkeeper, next in PEOPLE HERE, counted among the watch) on 3 of 7
    runs and 3 of 6 re-asks of the recorded slot. The engine's arresters were right
    (`guards_who_see`, `has_state(GUARD)`); the tell gave the narrator a run of names with
    no edge to it. Counted and said as the watch, with PEOPLE HERE marking who is of the
    watch (`planned.present`): 0 of 6 re-asks."""
    names = _names(seen)
    if len(seen) == 1:
        return f"One of the watch comes for {pc_name}: {names}."
    count = _COUNT.get(len(seen), str(len(seen)))
    return f"{count} of the watch come for {pc_name}, and only they: {names}."


def taken(engine, pc, held, who, town: str):
    """Go quietly, or a talk that failed: taken in, held and questioned
    (`trial.take_in`, the owner's ruling of 2026-11-01). Until that ruling this was one
    night held and release at morning for want of proof, whatever had been done."""
    from . import trial

    return trial.take_in(engine, pc, who, town)


def talked(engine, actor, skill: str, made: bool) -> str:
    """A Diplomacy or Bluff check by the player while the watch is taking them in: made,
    the guards stand down for the day; missed, the arrest stands and the batch's end
    takes them. The sentence to add to the check's tell, or ""."""
    held = pending(actor) if actor is not None and actor.is_pc else None
    if held is None or str(skill or "").strip().lower() not in TALK_SKILLS:
        return ""
    pay = dict(held.payload or {})
    who = [engine.scene.people[r] for r in pay.get("by") or () if r in engine.scene.people]
    names = _names(who) or "The watch"
    if made:
        stand_down(engine, actor, str(pay.get("town") or _town(engine)), STOOD_DOWN_DAYS,
                    "talked the watch down")
        return (f"{names[:1].upper() + names[1:]} hear{'s' if len(who) == 1 else ''} it out "
                f"and stand{'s' if len(who) == 1 else ''} down, for today. The warrant "
                f"stands.")
    return f"{names[:1].upper() + names[1:]} {'is' if len(who) == 1 else 'are'} not having it."
