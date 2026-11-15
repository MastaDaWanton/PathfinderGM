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

**Trust and Risk** (built 2026-11-15; d20pfsrd "Hirelings, Servants & Services",
Contingency Services, which carries C&C's text; Ultimate Campaign p.148, Trust, for the
1-5 scale): a hireling's Trust is set when they are recruited — a successful recruiting
Diplomacy "finds skeptical or wary hirelings" — and here it is read off their attitude at
the hire (`TRUST_AT_HIRE`: indifferent is skeptical, 2). Work whose Risk (`jobs.RISK`, 1-5)
is above it is not refused outright: "Hirelings don't automatically refuse. Each category of
difference adds 5 to the result of the opposed Diplomacy check" — the player's Diplomacy
against theirs plus 5 a step (`balk`), asked where the party sets out on a road whose
ground raises its Risk (`jobs.risk_of("escort", crosses)`). Lost, they will not go: their
service ends there and the whole days of the advance they will not work are handed back
(this app's call; the book says only that they refuse).

**Unpaid days** (the same section): "When funds run out, hirelings may stay on duty. Each
day you must attempt a new negotiation check or the hirelings abandon the task. Hirelings
who keep working unpaid expect double pay for those days", and "failure to pay immediately
reduces the hirelings' Trust to 1". So a wage the purse cannot meet drops Trust to 1; each
day unpaid the same opposed check is made (Risk against Trust 1: +5); a day won is a day
owed at double (`owed_days`), a day lost and they walk; and the next settle that finds the
coin pays the debt before the new week (`settle`).

**A post** (`do: guard`, `what: "here"`): a hireling told to hold a place stays there,
still in pay, when the party walks away — the C&C example of hirelings "watching over ...
[a] business and defending it if attacked". Their travelling bond is dropped and the post
held (`bond.guarding`, `at`); being somebody with a standing they stay in the world where
they stand (`Engine._stays_in_the_world`), and a word has them come along again.

**Not built (said, not hidden):** the wage following the day's most dangerous work (the
week stays priced at the road's questionable Risk); a balk anywhere but setting out on a
road — a dangerous order in a fight is still the companion's own turn to weigh, the
owner's ruling.
"""
from __future__ import annotations

from . import states

# CRB, Trained Hirelings: "mercenary warriors"; "Most guards are off-duty soldiers or city
# watchmen" — the work ids of content/people/occupations.json that hire out a sword.
HIRES_OUT = frozenset({"caravan-guard", "soldier", "guard"})
# What a guard order can be on (`do: guard`, `what`): the party's cargo, the player, or
# the place they stand in, held while the party goes on without them.
GUARDS = ("cargo", "you", "here")
# Ultimate Campaign's Trust (p.148), 1 "wary" to 5 "confidant", set by the hireling's
# attitude when they sign on. THIS APP'S mapping: a stranger who takes your coin is
# skeptical ("can be called upon to perform tasks of minimal risk"), one a step warmer
# reliable, and so on; a confidant is never bought.
TRUST_AT_HIRE = {"unfriendly": 1, "indifferent": 2, "friendly": 3, "helpful": 4}
UNPAID_TRUST = 1
# C&C: "Each category of difference adds 5 to the result of the opposed Diplomacy check."
RISK_STEP_DC = 5


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
    from `now`, at the Trust their attitude signs on with (`TRUST_AT_HIRE`)."""
    from . import attitude as attitude_mod
    from . import jobs
    from .activeeffect import ActiveEffect

    source = f"company:{actor.ref}"
    actor.apply_effect(ActiveEffect(
        name="in your pay", kind="bond", key=f"{source}:hired", source=source,
        origin=source, duration="until-dismissed", tags=(states.HIRED,),
        payload={"per_day_cp": int(per_day),
                 "paid_until": int(now) + jobs.WEEK_DAYS * 24 * 60,
                 "trust": TRUST_AT_HIRE.get(attitude_mod.of(actor), 2)}))


def trust(actor) -> int:
    """The hireling's Trust, 1-5 (0 for somebody nobody pays)."""
    e = wage(actor)
    return int((e.payload or {}).get("trust", 2)) if e is not None else 0


def _negotiates(engine, pc, actor, risk_step: int) -> tuple[bool, str]:
    """C&C's opposed Diplomacy: the player's against the hireling's, plus `RISK_STEP_DC`
    for each step the work's Risk is over their Trust. (won, the rolls in words)."""
    def roll(who, label, plus=0):
        try:
            mods = list(who.skill_modifiers("diplomacy"))
        except Exception:  # noqa: BLE001 - a body with no sheet negotiates on the d20
            mods = []
        return engine.dice.d20(mods, label=label, visibility="hidden").total + plus

    over = max(0, risk_step - trust(actor))
    ours = roll(pc, f"{pc.name} Diplomacy")
    theirs = roll(actor, f"{actor.name} Diplomacy", RISK_STEP_DC * over)
    return ours >= theirs, (f"Diplomacy {ours} against {actor.name}'s {theirs}"
                            + (f", {theirs - RISK_STEP_DC * over} and "
                               f"{RISK_STEP_DC * over} for the risk over their trust"
                               if over else ""))


def _refund_cp(e, now: int) -> int:
    """The whole days of an advance not yet worked, in copper."""
    days = max(0, (int(e.payload.get("paid_until", now)) - int(now)) // (24 * 60))
    return days * int(e.payload.get("per_day_cp", 0))


def balk(engine, risk: str, where: str) -> list:
    """Hirelings the party sets out with on work riskier than their Trust: each makes C&C's
    opposed check (`_negotiates`); one the player wins comes, one the player loses stays
    here, out of the party's pay, with the unworked days of the advance handed back.
    Outcomes with their tells (law 3)."""
    from . import goods, jobs
    from .engine import Outcome

    scene = engine.scene
    pc = scene.pc()
    if pc is None or risk not in jobs.RISK:
        return []
    step = jobs.RISK.index(risk) + 1
    now = int(scene.clock_minutes)
    coins = engine._coins_here()
    out = []
    for a in list(scene.actors.values()):
        e = wage(a)
        if (e is None or a.is_down or not a.has_state(states.TRAVELS_WITH_YOU)
                or step <= trust(a)):
            continue
        won, rolled = _negotiates(engine, pc, a, step)
        if won:
            out.append(Outcome(
                intent_id="", op="company", because="a hireling weighs the road",
                effects=[{"ref": a.ref, "kind": "company", "travels": True, "balked": False}],
                tell=f"{a.name} does not like a {risk} road to {where} and says so, but "
                     f"{pc.name} talks them into it ({rolled}): they come."))
            continue
        back = _refund_cp(e, now)
        a.remove_effects(source=f"company:{a.ref}")
        if back:
            pc.purse = goods.credit(pc.purse, back)
        out.append(Outcome(
            intent_id="", op="company", because="a hireling weighs the road",
            effects=[{"ref": a.ref, "kind": "company", "travels": False, "balked": True}]
                    + ([{"kind": "give", "ref": a.ref, "item": "coin", "count": back,
                         "how": "wage returned", "from": a.ref, "to": pc.ref,
                         "purse": dict(pc.purse)}] if back else []),
            tell=f"{a.name} will not take a {risk} road to {where} for this pay ({rolled}): "
                 f"they stay here, out of {pc.name}'s pay"
                 + (f", and hand back {goods.purse_line(goods.coins_for(back), coins)} for "
                    f"the days they will not work." if back else ".")))
    return out


def post(actor, where: str) -> None:
    """Hold `where` while the party goes on: the travelling bond dropped, the wage kept,
    the post held as `bond.guarding` under the same source."""
    from .activeeffect import ActiveEffect

    source = f"company:{actor.ref}"
    actor.remove_effects(match=lambda e: e.key == f"{source}:travels")
    actor.apply_effect(ActiveEffect(
        name="holding a post for you", kind="bond", key=f"{source}:guarding", source=source,
        origin=source, duration="until-dismissed", tags=(states.GUARDING,),
        payload={"what": "here", "at": str(where)}))


def guard(actor, what: str) -> None:
    from .activeeffect import ActiveEffect

    source = f"company:{actor.ref}"
    actor.apply_effect(ActiveEffect(
        name=f"guarding {'your cargo' if what == 'cargo' else 'you'}", kind="bond",
        key=f"{source}:guarding", source=source, origin=source,
        duration="until-dismissed", tags=(states.GUARDING,), payload={"what": what}))


def guarding(actor) -> str:
    """What this companion was told to guard ("cargo", "you", "here"), or ""."""
    e = next((e for e in (getattr(actor, "effects", ()) or ())
              if states.GUARDING in (e.tags or ())), None)
    return str((e.payload or {}).get("what") or "") if e is not None else ""


def settle(engine) -> list:
    """Wages that fell due: a debt of unpaid days first, at double; then a week more from
    the purse; and a purse that cannot meet it, C&C's unpaid days — Trust to 1, and each
    day unpaid a negotiation (`_negotiates`) won to keep them on, owed double, or lost and
    they walk. Ashore and out of a fight only (module docstring). Outcomes with their
    tells (law 3)."""
    from . import attitude as attitude_mod
    from . import goods, jobs
    from .engine import Outcome

    scene = engine.scene
    pc = scene.pc()
    if pc is None or scene.in_encounter or engine.aboard() is not None:
        return []
    now = int(scene.clock_minutes)
    day = 24 * 60
    week = jobs.WEEK_DAYS * day
    risk_step = jobs.RISK.index(jobs.risk_of("escort")) + 1
    out = []
    for a in list(scene.actors.values()):
        e = wage(a)
        if e is None or a.is_down:
            continue
        owed = int(e.payload.get("owed_days", 0) or 0)
        if int(e.payload.get("paid_until", now + 1)) > now and not owed:
            continue
        per_day = int(e.payload.get("per_day_cp", 0))
        per_week = per_day * jobs.WEEK_DAYS
        coins = engine._coins_here()
        spent, said_paid = 0, []
        if owed:
            # "Hirelings who keep working unpaid expect double pay for those days."
            debt = owed * per_day * 2
            purse, enough = goods.spend(pc.purse, debt)
            if enough:
                pc.purse, spent = purse, spent + debt
                said_paid.append(f"the {owed} unpaid day{'s' if owed != 1 else ''} owed, "
                                 f"at double: "
                                 f"{goods.purse_line(goods.coins_for(debt), coins)}")
                e.payload["owed_days"] = owed = 0
        weeks = 0
        while not owed and int(e.payload["paid_until"]) <= now:
            purse, enough = goods.spend(pc.purse, per_week)
            if not enough:
                break
            pc.purse = purse
            e.payload["paid_until"] = int(e.payload["paid_until"]) + week
            weeks += 1
        if weeks:
            spent += per_week * weeks
            said_paid.append(f"another {'week' if weeks == 1 else f'{weeks} weeks'} of "
                             f"wages in advance: "
                             f"{goods.purse_line(goods.coins_for(per_week * weeks), coins)}")
        paid_fx = ([{"kind": "give", "ref": pc.ref, "item": "coin", "count": spent,
                     "how": "wage", "from": pc.ref, "to": a.ref, "purse": dict(pc.purse)}]
                   if spent else [])
        paid_said = f"{pc.name} pays {a.name} " + " and ".join(said_paid) + "."
        if int(e.payload["paid_until"]) > now:
            out.append(Outcome(intent_id="", op="company", because="a hireling's wage",
                               effects=paid_fx, tell=paid_said))
            continue
        # The purse is short: "failure to pay immediately reduces the hirelings' Trust to
        # 1", and each day unpaid is negotiated for.
        e.payload["trust"] = UNPAID_TRUST
        kept, rolled, walked = 0, "", False
        while int(e.payload["paid_until"]) <= now:
            won, rolled = _negotiates(engine, pc, a, risk_step)
            if not won:
                walked = True
                break
            e.payload["paid_until"] = int(e.payload["paid_until"]) + day
            e.payload["owed_days"] = int(e.payload.get("owed_days", 0) or 0) + 1
            kept += 1
        short = (f"{pc.name} carries {goods.purse_line(pc.purse, coins)} against "
                 f"{goods.purse_line(goods.coins_for(per_week), coins)} a week")
        if not walked:
            out.append(Outcome(
                intent_id="", op="company", because="a hireling's wage",
                effects=paid_fx + [{"ref": a.ref, "kind": "company", "travels": True,
                                    "owed_days": int(e.payload["owed_days"])}],
                tell=(paid_said + " " if spent else "")
                     + f"{a.name}'s wages fell due, and {short}: {a.name} stays on unpaid, "
                       f"for {int(e.payload['owed_days'])} day"
                       f"{'s' if int(e.payload['owed_days']) != 1 else ''} owed at double "
                       f"({rolled}), and trusts {pc.name} less for it."))
            continue
        a.remove_effects(source=f"company:{a.ref}")
        before, after = attitude_mod.nudge_regard(a, -jobs.MISSED_REGARD, "wages unpaid")
        said = attitude_mod.regard_said(a.name, before, after)
        out.append(Outcome(
            intent_id="", op="company", because="a hireling's wage",
            effects=paid_fx + [{"ref": a.ref, "kind": "company", "travels": False,
                                "regard_from": before, "regard_to": after}],
            tell=(paid_said + " " if spent else "")
                 + f"{a.name}'s wages fell due, and {short}"
                 + (f"; {a.name} stayed on {kept} day{'s' if kept != 1 else ''} unpaid"
                    if kept else "")
                 + f": {a.name} will not work on for nothing ({rolled}), is in nobody's "
                   f"pay and goes their own way." + (f" {said}" if said else "")))
    return out
