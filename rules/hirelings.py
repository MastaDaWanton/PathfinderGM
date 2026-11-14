"""Hired swords: somebody whose work is fighting comes along for a wage.

The owner, 2026-11-14: "am i able to hire mercenaries/guardsmen to sail with and help guard
me and or my wares" -> "build both". Anyone friendly could already come along
(`Engine._op_company`, `bond.travels-with-you`); nobody could be PAID to.

A hireling is a companion with a wage: the `company` op's `do: hire` grants the same
`bond.travels-with-you` effect every companion holds (`Engine._travels_with_you`) and a
second effect, `bond.hired`, carrying the wage and the minute it is paid to. Both share the
source `company:<ref>`, so `do: leave` — or anything else that drops the companion — ends
both at once (the second law: remove the effect and its contribution evaporates). Being a
companion, a hireling sails as a head in the fare (`Engine._passage_party`), fights on the
party's side (`attitude.side_of`), obeys spoken orders in character (gm/companions.py) and
counts in the encounter budget's APL (`encounter_budget.party_levels`: a `company:` origin).

**The books** (read 2026-11-14, d20pfsrd.com "Hirelings, Servants & Services", which carries
both the CRB rows and Cohorts & Companions' Contingency Services):

  * CRB: the trained hireling's wage "is the typical daily wage for mercenary warriors";
    "Most guards are off-duty soldiers or city watchmen" — so a town guard hires out as a
    sellsword does (`HIRES_OUT`).
  * Cohorts & Companions, Contingency Services: "Hireling wages are based on the most
    dangerous work they perform each day", by Risk, times the hireling's level squared —
    `jobs.per_day_cp`, reused, never copied. A sword that goes where the party goes takes
    the road's Risk (`jobs.risk_of("escort")`: questionable). "You must pay hirelings up
    front"; "Securing service requires at least one week's wages paid in advance"
    (`WEEK_DAYS`, the jobs module's week). "Failure to pay immediately reduces the
    hirelings' Trust to 1" — here, an unpaid hireling walks (`settle`) and thinks less of
    the player (`jobs.MISSED_REGARD`).
  * Leadership (d20pfsrd, feats): cohorts and followers are the feat's, loyal without pay;
    a hireling is not one, and nothing here grants a cohort.

**The games:** Battle Brothers pays a daily wage and unpaid or angry men desert (its wiki's
loading-screen tips; dev blog: each recruit has his own idea of pay). Mount & Blade's wage
grows with the troop's level squared (community-measured formula, not confirmed in the
game's files) and unpaid troops lose morale and leave. Kenshi's bar mercenaries sign for a
fixed few days and walk at the end (community reports; vanilla length not confirmed).
What is taken: the level-squared wage (it is the book's too), pay up front, leaving when
unpaid. What is refused: a morale bar beside the attitude track — regard already IS the
track (`rules/attitude.py`), and a second loyalty number would be the parallel store the
first law forbids; Kenshi's contract that ends while the money is there — the week renews
from the purse, as a wage-paying company's does.

**Design calls** (recorded for the owner):
  * Paid a week in advance (C&C), renewed a week at a time from the purse when it falls
    due; a purse that cannot cover it, and the hireling goes their own way.
  * Never on a deck: a wage that falls due at sea is taken when the party is ashore
    (nobody walks off a ship), and while a fight is on, after it.
  * Hostile refuses, as at a counter (`pricing.refuses`); any other step hires, the wage
    moved by the hireling's own terms (`pricing.asked_cp`: attitude and thrift, 0.3.2/0.3.3).
  * Found where the world's people are: a sellsword, caravan guard, soldier or guard the
    narration or the settlement's people put in the room. No hiring hall is built.
  * How many: as many as the purse pays for — the encounter budget grows with them.
  * Their sheet is the one the people builder already gave them; no level is invented.

**Guarding** (`do: guard`): a companion told to keep watch holds `bond.guarding`, with what
they guard (`GUARDS`: the party's `cargo`, or `you`), through the applicator under the same
source. It is the state the cargo lane (feat/trade-goods) reads: a guard on the party's
cargo goes where the cargo goes and stands to it. Nothing here builds cargo.

**Not built (said, not hidden):** C&C's Trust score and refusing work whose Risk exceeds it
(the companion's own turn weighs a dangerous order, the owner's ruling); "double pay for
unpaid days"; a hireling left behind to guard a place the party walks away from.
"""
from __future__ import annotations

from . import states

# CRB, Trained Hirelings: "mercenary warriors"; "Most guards are off-duty soldiers or city
# watchmen" — the work ids of content/people/occupations.json that hire out a sword.
HIRES_OUT = frozenset({"caravan-guard", "soldier", "guard"})
# What a guard order can be on (`do: guard`, `what`).
GUARDS = ("cargo", "you")


def work_of(scene, actor) -> str:
    """The occupation id the population rolled for this person, or ""."""
    from . import population

    rec = population.of_ref(scene, getattr(actor, "ref", "")) if scene is not None else None
    return str(((rec or {}).get("life") or {}).get("work") or "")


def hires_out(scene, actor) -> bool:
    return work_of(scene, actor) in HIRES_OUT


def wage(actor):
    """The hireling's wage effect, or None for somebody nobody pays."""
    return next((e for e in (getattr(actor, "effects", ()) or ())
                 if states.HIRED in (e.tags or ())), None)


def day_cp(scene, actor) -> int:
    """What this person asks a day to go with the party: Cohorts & Companions' road wage
    for their level (`jobs.per_day_cp`), moved by their own terms (`pricing.asked_cp`)."""
    from . import encounter_budget, jobs, pricing

    book = jobs.per_day_cp("escort", encounter_budget.companion_level(actor),
                           jobs.risk_of("escort"))
    return pricing.asked_cp(scene, actor, book)


def week_cp(scene, actor) -> int:
    from . import jobs

    return day_cp(scene, actor) * jobs.WEEK_DAYS


def take_on(actor, per_day: int, now: int) -> None:
    """The wage, through the one applicator, under the companion's own source: paid a week
    from `now`."""
    from . import jobs
    from .activeeffect import ActiveEffect

    source = f"company:{actor.ref}"
    actor.apply_effect(ActiveEffect(
        name="in your pay", kind="bond", key=f"{source}:hired", source=source,
        origin=source, duration="until-dismissed", tags=(states.HIRED,),
        payload={"per_day_cp": int(per_day),
                 "paid_until": int(now) + jobs.WEEK_DAYS * 24 * 60}))


def guard(actor, what: str) -> None:
    from .activeeffect import ActiveEffect

    source = f"company:{actor.ref}"
    actor.apply_effect(ActiveEffect(
        name=f"guarding {'your cargo' if what == 'cargo' else 'you'}", kind="bond",
        key=f"{source}:guarding", source=source, origin=source,
        duration="until-dismissed", tags=(states.GUARDING,), payload={"what": what}))


def guarding(actor) -> str:
    """What this companion was told to guard ("cargo", "you"), or ""."""
    e = next((e for e in (getattr(actor, "effects", ()) or ())
              if states.GUARDING in (e.tags or ())), None)
    return str((e.payload or {}).get("what") or "") if e is not None else ""


def settle(engine) -> list:
    """Wages that fell due: a week more from the purse, or the hireling goes. Ashore and
    out of a fight only (module docstring). Outcomes with their tells (law 3)."""
    from . import attitude as attitude_mod
    from . import goods, jobs
    from .engine import Outcome

    scene = engine.scene
    pc = scene.pc()
    if pc is None or scene.in_encounter or engine.aboard() is not None:
        return []
    now = int(scene.clock_minutes)
    week = jobs.WEEK_DAYS * 24 * 60
    out = []
    for a in list(scene.actors.values()):
        e = wage(a)
        if e is None or a.is_down or int(e.payload.get("paid_until", now + 1)) > now:
            continue
        per_week = int(e.payload.get("per_day_cp", 0)) * jobs.WEEK_DAYS
        weeks = 0
        while int(e.payload["paid_until"]) <= now:
            purse, enough = goods.spend(pc.purse, per_week)
            if not enough:
                break
            pc.purse = purse
            e.payload["paid_until"] = int(e.payload["paid_until"]) + week
            weeks += 1
        coins = engine._coins_here()
        paid = goods.purse_line(goods.coins_for(per_week * weeks), coins)
        if int(e.payload["paid_until"]) > now:
            out.append(Outcome(
                intent_id="", op="company", because="a hireling's wage",
                effects=[{"kind": "give", "ref": pc.ref, "item": "coin",
                          "count": per_week * weeks, "how": "wage", "from": pc.ref,
                          "to": a.ref, "purse": dict(pc.purse)}],
                tell=f"{pc.name} pays {a.name} {paid}: another "
                     f"{'week' if weeks == 1 else f'{weeks} weeks'} of wages in advance."))
            continue
        a.remove_effects(source=f"company:{a.ref}")
        before, after = attitude_mod.nudge_regard(a, -jobs.MISSED_REGARD, "wages unpaid")
        said = attitude_mod.regard_said(a.name, before, after)
        out.append(Outcome(
            intent_id="", op="company", because="a hireling's wage",
            effects=[{"ref": a.ref, "kind": "company", "travels": False,
                      "regard_from": before, "regard_to": after}]
                    + ([{"kind": "give", "ref": pc.ref, "item": "coin",
                         "count": per_week * weeks, "how": "wage", "from": pc.ref,
                         "to": a.ref, "purse": dict(pc.purse)}] if weeks else []),
            tell=(f"{a.name}'s wages fell due"
                  + (f" and {pc.name} paid {paid}, but not enough to bring them up to date"
                     if weeks else f", and {pc.name} carries "
                     f"{goods.purse_line(pc.purse, coins)} against "
                     f"{goods.purse_line(goods.coins_for(per_week), coins)} a week")
                  + f": unpaid, {a.name} is in nobody's pay and goes their own way."
                  + (f" {said}" if said else ""))))
    return out
