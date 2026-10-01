"""Everybody the beat showed here is in the scene as a full person (owner's ruling, 2026-10-01).

"show described people in the scene. if i can see them they should be in the scene as a
fully made person ready to be interacted with and saved if not already existing." It
overturns the ruling of 2026-09-27 that the prose only records people and engagement or
the plan makes them actors.

Measured on the owner's save, the turn that made the ruling necessary: the beat walked the
player into a house and wrote "At the top of the stairs, a figure is silhouetted … It is a
woman". She was a population record and nothing more. The next turn, "/cheat the woman is
overcome with lust and pounces on me", planned a condition on 'woman' (refused: unknown
ref) and a spawn of 'woman' (refused: no creature), fell back to narrate_only, and every
"her" after that went to Quin Nutmeg, the only woman the engine held — so an intimate scene
was played with somebody in another room.

`judgement.record_people` reads each person the beat introduced (`seen_in_beat`) and marks
the ones it SHOWS here; this step gives them bodies (`judgement.embody_seen`). The "people"
stage, after `speaker_real` (ORDER 10): a speaker made real there is already a body here,
and `hailed_by` — which runs after this stage — sees everybody this step made.
"""
from __future__ import annotations

STAGE = "people"
ORDER = 20
DOORS = frozenset({"turn", "carry_on"})


def step(ctx) -> list[dict]:
    from gm import judgement

    return judgement.embody_seen(ctx.scene, turn=int(ctx.turn or 0), world=ctx.world,
                                 beat=ctx.text, engine=ctx.campaign.engine())
