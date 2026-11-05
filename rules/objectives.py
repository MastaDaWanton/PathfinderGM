"""Whether a quest objective was done: the engine's own state answers, never a claim.

The planner's `quest_step` and the watcher's `objective` both SAY an objective was done.
Until 2026-11-01 the engine took them at their word: `Engine._op_quest_step` checked only
that the objective existed and was not ticked yet. Measured on the owner's 0.2.25 save
(Corvin): "find a place to rest" at the shrine came back as `quest_step` for "Go out by the
edge" and paid 800 XP while the player never left town; a repro finished "What a faction
within Ashgate Reach holds" from the marsh with three bare `quest_step`s for 1,600 XP —
the accounts never visited, the proof never taken, nothing put before the captain.

The prior art all keeps the objective's truth on the server's side of the table. A World
of Warcraft quest's objectives are typed counters the server keeps — a creature killed, an
item held (`RequiredNpcOrGo`, `RequiredItemId` in TrinityCore's `quest_template`), an
area-trigger entered — and the client never reports one done; delivery is a hand-over at
the quest ender that takes the items. Valve's rule database (Ruskin, GDC 2012), which the
schemes already follow, fires on facts the game holds. The AI-GM literature names the
failure this replaces: a language model narrating events the game never ran ("You Have
Thirteen Hours in Which to Solve the Labyrinth", 2024, moved state into function calls for
exactly this). So a claim is checked against the predicates the engine already has:

* **a job** (`rules/jobs.py`) and **a loss to get back** (`rules/defeat.py`) tick
  themselves off the engine's own record — met, arrived, paid; held again. A claim about
  them is passed over in silence; their own settle ticks what is true.
* **a scheme's quest** ticks when one of its steps' criteria hold (`schemes.ticking_steps`,
  the scheme's `at`, `holds`, `event:give`, `present` …). Holding now, the claim is passed
  over and the scheme's own tick fires the step after the batch — with its own grants,
  tell and award, so a planner's word can never jump a scheme's ending (a `quest_step`
  that finished "Clear your name" paid the double award where the scheme's own
  `two-clues` pays a half). Not holding, it is refused with what is missing, in words.
* **a quest the player has not taken on** cannot be stepped by them at all.
* **a quest the GM opened** with the `quest` op has objectives in the model's own words
  and no criteria the engine holds. It still ticks on the claim, as before — the one door
  left on a model's word, said here so nobody reads this module as closing it. Closing
  it needs the `quest` op to carry a checkable criterion per objective (a place, a thing,
  a person), which is a planner schema change and was left for its own lane.
"""
from __future__ import annotations

from dataclasses import dataclass

TICK = "tick"          # the caller ticks it: the engine has nothing to check it against
ENGINE = "engine"      # the engine's own settle ticks it (now or at the end of the batch)
REFUSE = "refuse"      # not done, and `why` says what is missing


@dataclass
class Judgement:
    verdict: str
    why: str = ""


def judge(engine, card, index: int, events=()) -> Judgement:
    """Whether objective `index` (0-based) of `card` is done by the engine's own state.

    `events` are what the batch has done so far (`schemes._events_from` over its
    outcomes), for a criterion that asks about a hand-over or a word this very batch."""
    from . import cards as cards_mod, schemes as schemes_mod

    scene = engine.scene
    pc = scene.pc()
    if card.kind == "job" or card.recover:
        return Judgement(ENGINE)
    if cards_mod.standing(card) != cards_mod.OWN:
        return Judgement(REFUSE, f"{card.title} is not {pc.name if pc else 'the player'}'s "
                                 f"to finish: it was never taken on.")
    owned = schemes_mod.card_owner(scene, card.id)
    if owned is None:
        return Judgement(TICK)
    inst, doc, key = owned
    steps = schemes_mod.ticking_steps(doc, key, index + 1)
    text = card.objectives[index].get("text", "") if 0 <= index < len(card.objectives) else ""
    if not steps:
        # Settled by the scheme's ending, not ticked: "Decide who the Anise belongs with"
        # is answered by whom it is given to (`given-away`, `returned`).
        return Judgement(REFUSE, f"Not done: {text}. It is settled by how the matter ends, "
                                 f"not ticked on its own.")
    best: list[str] | None = None
    for st in steps:
        if schemes_mod.criteria_hold(engine, inst, doc, st, events):
            if st["id"] in (inst.get("fired") or {}) and st.get("once", True):
                # The step already fired and cannot fire again, yet the objective stands
                # unticked (a card reopened by hand, an older save): the criteria are the
                # proof, so the caller ticks it.
                return Judgement(TICK)
            return Judgement(ENGINE)
        missing = schemes_mod.unmet(engine, inst, doc, st, events)
        if best is None or len(missing) < len(best):
            best = missing
    return Judgement(REFUSE, f"Not done: {text}. " + " ".join(best or ["Not yet."]))
