"""The clock for a bench step: the one door all five step benches pass their work's time
through (herbalism, the forge, the circle, the alchemy bench, the leather bench).

Measured on Ansel's save (owner report 2026-11-01): every step bench's roll called
`c.scene.advance(plan.minutes)` and nothing else. His drying and the steps around it put
9.5 days on the clock; the body ate from the pack as a lived stretch does, ran out on day
4, and starved through days 4 to 9 without the bench asking; and none of it reached the
page. The hunger, fatigue and sleep were queued for the narrator and came out on his next
typed turn, told as though he had travelled.

Two doors, the 2026-10-09 tannery fix's shape (`leather_collect`, `alchemy_collect`):

  refusal   before anything is rolled, spent or paid: work of a day or more that the
            pack cannot carry the body through is refused in words (`survival.lasts`,
            the same arithmetic `Scene.wait` stops on), so the player eats, buys food or
            works a smaller batch;
  pass      the clock moves and whatever the body lived through on it, and whoever the
            clock brought or took, is told on the bench's page as one transcript line,
            and taken off the queues so the next typed turn does not tell it again.

Why `Scene.advance` and not `Scene.wait`: `wait` passes `waited=True`, which is the
owner's ruling for a wait the player CHOSE ("if I wait then people should go about their
day", 2026-10-09; `Engine.settle_on_clock`). That ruling's own text keeps the doorway
ruling for "every other stretch of clock — a craft's hours, a walk", so a bench step must
not send the people standing with the party off about their day. `advance` already lives
through a stretch of a day or more (`live=None` decides by length: the body eats, drinks
and sleeps from the pack); what it lacked was `wait`'s stop where the pack runs out, and
the refusal supplies that before the roll, because a bench step cannot stop half-dried
and keep its roll.
"""
from __future__ import annotations

from rules import sky, survival


def refusal(c, pc, minutes: int) -> str:
    """The sentence refusing this much bench work, or "" when the body can live through it.
    Short of a day nothing is asked (a short stretch is spent exactly as it always was)."""
    minutes = max(0, int(minutes or 0))
    if pc is None or minutes < survival.LIVED_MINUTES:
        return ""
    covered, short = survival.lasts(pc, minutes, biome=c.scene.biome,
                                    water=c.scene._water_at_hand(minutes))
    if not short:
        return ""
    return survival.cannot_work_said(pc, minutes, covered, short, c.scene.biome)


def pass_time(c, engine, pc, minutes: int, doing: str) -> list[str]:
    """Move the clock by a bench step's time and tell what was lived through it.

    `engine` is the one the door already lent to the scene (and rolled its die with): the
    clock's door settles people against the engine lent to it, and a second `c.engine()`
    would hand the scene a fresh dice stream. `doing` finishes "Kesst works 4 days ..."
    ("drying Caranator").

    Returns the lived sentences (empty when there is nothing to tell). Only then is a
    transcript line written: measured live on the herb bench, two log lines for every
    step was a complaint, and a 10-minute grind has nothing to add.
    """
    from rules import residency
    from rules.engine import _ward_tell

    minutes = max(0, int(minutes or 0))
    passed = c.scene.advance(minutes)
    lived = survival.told_on_page(c.scene, passed, pc.ref) + engine.comings_on_page()
    # What the stretch ended, told here and taken off the queue, so the next typed turn
    # does not tell it as its own: jack (owner's save 2026-11-17) came off 16 hours at the
    # bench and the next beat narrated him just waking up.
    lived += [t for t in (_ward_tell(c.scene, r) for r in c.scene.take_ended_said()) if t]
    head = f"{pc.name} works {sky.span_words(minutes)}{' ' + doing if doing else ''}."
    if lived:
        c.transcript.append({"who": "gm", "kind": "consequence",
                             "text": " ".join([head] + lived)})
    if minutes >= 60:
        # The hours reach the model's memory, the excursion's shape (craft_views): the
        # bench's 16 hours were in the transcript and the clock and nowhere the planner and
        # narrator read, so the next beat had no idea the day had gone.
        c.history.append({"role": "user", "content": f"(From the bench: {head})"})
        c.history.append({"role": "assistant", "content": " ".join(
            [head] + lived + [f"It is now {residency.time_words(int(c.scene.clock_minutes))}."])})
    return lived
