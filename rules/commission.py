"""Paying a keeper to do craft work on the player's own things (the `commission` op).

Owner report 2026-11-01 (Corvin, turns 21-29): at the smithy with a forged blank for a
trident, the player asked the smith to "put them together and i will give you 10 gold
peices", waited "for the smith to get done", and handed over the coin. Nothing in the
engine could take the job: real jobs (rules/jobs.py) are the player hiring OUT, the typed
craft (`make`) is the player's own hands, and the turns narrated a fitting the engine never
did — the blank stayed a blank, and the ten gold was refused "How much?".

## What the traditions do (researched 2026-11-01)

* Pathfinder 1e has no rule for what an NPC charges to work on a PC's item. It has the
  pieces: the Craft skill's own chain (time from the check), and hirelings — a trained
  hireling (a blacksmith is the book's example) costs 3 sp a day, materials supplied by the
  employer (CRB, Table 6-9 Services). So the price here is that: the craft's own hours,
  billed at the keeper's forge rent where the craft charges one (the bench's rule,
  `blacksmith.rent_cp`), plus a trained hireling's 3 sp for every working day begun. The
  player supplies the materials, as the book says the employer does.
* Kingdom Come's smiths and The Witcher 3's craftsmen take the player's materials and a fee;
  both hand the thing over on the spot. This app keeps the craft's own time instead,
  because a shop's hours already sit on the world clock: the made thing waits in the In
  progress section at the keeper's place (rules/inprogress.py, the owner's "all crafts sit
  before they can be collected") and is collected there.

## What it does

The keeper's craft is read off their trade (`keepers.trade_words`). The work is the typed
craft's own chain (`typed_craft`): the same steps, materials and product a typed line
would make from the same pack — so a blank with a bar for the haft becomes the plain
weapon, exactly as "I assemble the trident" would. The PLAYER is paid no mastery for work
they did not do (their track is put back as it was). Charged when agreed; the made thing is
held at the keeper's place for the work's time.

## The owner's ruling of 2026-11-01

* **The keeper's own hands.** Each step is the keeper's Craft roll off their own sheet (NPC
  builds carry ranks: the smithy's keeper is Craft +6) against the step's DC, the engine's
  die. The book's Craft failure bands are kept — a miss by 5 or more ruins the materials as
  the bench's own rule ruins them, and no fee is asked for spoiled work — a near miss is
  finished as lesser work (Crude), made is the plain item, ten over is finer work, never
  past the step's ceiling (`keeper_quality`). Before the ruling the keeper never failed.
* **Fittings from stock.** A job lacking only its haft, grip or fastenings is not refused:
  the keeper puts the cheapest plain bought fitting the catalogue lists for that piece into
  the work and adds its price to the bill (`stock_fitting`).
* **The haggle.** The day's haggle with this keeper — the trade panel's, or a commission
  offered rather than agreed, which is Diplomacy's Make Request for Ultimate Campaign's
  undercut (`_haggle`) — comes off the bill. One haggle a keeper a day, as at the counter.

Prior art for the keeper's roll: The Witcher 3's craftsmen make only what their tier allows
(fextralife wiki, Armorsmithing); RimWorld rolls quality on a distribution centred on the
crafter's skill (rimworldwiki.com/wiki/Quality); Dwarf Fortress caps its top tier at a
third even for a legend, refusing to guarantee masterwork (dwarffortresswiki, Quality).
"""
from __future__ import annotations

import copy
import math

# A trained hireling's day (CRB Table 6-9 Services: "Hireling, trained: 3 sp per day"),
# and the working day it buys.
DAY_WAGE_CP = 30
WORKING_DAY_MINUTES = 8 * 60
ORIGIN = "rule:commission"


def craft_of(keeper) -> str:
    """The craft a keeper works, off their trade's words, or ""."""
    from . import keepers, typed_craft

    words = set(keepers.trade_words(keeper))
    return next((c for c in typed_craft.CRAFTS if c in words), "")


def price_cp(minutes: int, rent_cp: int) -> int:
    """The keeper's bill: the forge's hours as the craft charges them, and a trained
    hireling's day for every working day begun."""
    days = max(1, math.ceil(int(minutes) / WORKING_DAY_MINUTES))
    return int(rent_cp) + days * DAY_WAGE_CP


def _finish_piece(engine, craft, pc, target):
    """The assembly of a forged piece the player already carries for the shape asked —
    however it was worked — or None. The typed chain takes only plain pieces (finer work
    belongs at the bench when it is the player's own hands); a keeper finishing the
    player's own tempered blank is fitting work on what exists, which the forge's own
    Assemble step does (`Blacksmith._assemble`)."""
    from . import blacksmith as bs

    shape = (target.data.get("info") or {}).get("id")
    if not shape:
        return None
    items = bs.rack(pc)
    mains = [p for p in items if p.form in bs.PIECE_FORMS and p.work is not None
             and p.work.shape == shape and not p.worn]
    if not mains:
        return None
    # The most worked first: the player's own best piece is the one they mean.
    mains.sort(key=lambda p: (-(len(p.work.worked or ()) + int(bool(p.work.quench))
                                + int(p.passes or 0)), p.key))
    known = engine.places()
    where = bs.where_here(engine.scene, pc, known)
    return craft._assemble(engine, pc, pc.track(craft.track), where, known, target,
                           mains[0], items)


def _piece_shape(pc) -> str:
    """The shape of an unfinished forged piece the player carries — the blank or plate a
    keeper would finish — or ""."""
    from . import blacksmith as bs

    for p in bs.rack(pc):
        if p.form in bs.PIECE_FORMS and p.work is not None and p.work.shape:
            info = bs.shape_info(p.work.shape)
            if info:
                return str(info["name"])
    return ""


def run(engine, intent, partial: dict | None = None):
    """Resolve a `commission`: who works, what is made, what it costs, when it is ready."""
    from . import goods, inprogress, places as places_mod, typed_craft
    from .engine import Outcome

    partial = partial if partial is not None else {}
    scene = engine.scene
    pc = scene.actors.get(intent.actor or "") or scene.pc()
    keeper = scene.actors.get(str(intent.params.get("who") or ""))
    if pc is None:
        return engine._refuse(intent, "Nobody is here to ask for the work.")
    if keeper is None or keeper.is_pc:
        return engine._refuse(intent, "There is nobody here by that name to do the work.")
    if scene.in_encounter:
        return engine._refuse(intent, "There is a fight going on: nobody takes work now.")
    craft_id = craft_of(keeper)
    if not craft_id:
        return engine._refuse(intent, f"{keeper.name} keeps no craft to work your things "
                                      f"with.")
    craft = typed_craft.get(craft_id)
    words = " ".join(str(intent.params.get("item") or "").split())
    asked = asked_of(scene, pc, keeper)
    if intent.params.get("agree"):
        # The keeper's price agreed ("I agree to his price and pay", built by the act table
        # from the reader's `sell`/`give` with nothing of the player's to hand over, at a
        # keeper asked for work today — `acts_to_ops._agreed_work`). The work is what was
        # asked for; the price is this op's own, never the words'.
        words = words or str((asked or {}).get("item") or "")
        paid = _paid_work(engine, pc, keeper)
        if paid is not None:
            # Already taken and paid: no coin changes hands. A refusal, not a resolved
            # answer, and worded from the player's side: on the rerun of 2026-11-03 a
            # resolved "already has the work in hand and paid for … Nothing more is owed"
            # was told 3 of 3 times as the player handing the coins over again.
            #
            # And said as a payment in the past: "pays nothing more: the smith took the fee
            # with the job" was still told as the smith accepting the coin now on the
            # 2026-11-05 rerun ("The smith accepts the fee for the work", 1 of 7 runs; 5 of
            # 6 re-asks of the recorded slot). "Paid … earlier, when the job was taken …
            # no coin changes hands this time": 0 of 8.
            return engine._refuse(intent, (
                f"{paid_before(pc.name, keeper.name)} {paid['name']} will be ready to "
                f"collect here {_when(paid)}."))
        if (asked or {}).get("how") == "taken":
            # Taken, paid and collected: the price was paid with the job. A second job is
            # asked for in its own words, never by agreeing to a price already paid.
            return engine._refuse(intent, paid_before(pc.name, keeper.name))
    target = craft.target(words, pc, words) if craft is not None else None
    if (target is None or isinstance(target, typed_craft.Refusal)) \
            and craft_id == "blacksmith" and _piece_shape(pc):
        # "put them together": the blank the player carries is what is to be finished.
        target = craft.target(_piece_shape(pc), pc, _piece_shape(pc))
    if target is None or isinstance(target, typed_craft.Refusal):
        why = target.why if isinstance(target, typed_craft.Refusal) else \
            f"{keeper.name} has no plain work of that kind to do."
        return engine._refuse(intent, f"{keeper.name} cannot take the job: {why}")

    # The haggle first, on the player's own die (Make Request, CRB p.93): asked before the
    # keeper lifts a hammer, so a suspension for the roll changes nothing yet.
    haggled_pct, haggle_said, haggle_rolls = _haggle(engine, intent, pc, keeper, partial)

    # The chain walked on the pack by the KEEPER's hands (owner ruling 2026-11-01): each
    # step their own Craft roll against the step's DC — a near miss is lesser work, a miss
    # by 5 or more spoils it by the book's rule, a roll 10 over is finer work. Then the
    # bill. A refusal puts the pack back as it was (Inform's check rule).
    track = craft.track
    kept = copy.deepcopy(pc.world_classes.get(track))
    before = _pack(pc)
    supplied = None
    for attempt in range(2):
        steps, done, rolls, stopped, spoiled = _walk(engine, craft, craft_id, pc, keeper,
                                                     target)
        if (stopped is not None and stopped.code == "no_fitting" and supplied is None
                and attempt == 0):
            # Nothing to fit the head to: the smith takes a plain one off his own shelf and
            # adds it to the bill (owner ruling 2026-11-01).
            _restore(pc, track, kept)
            _unpack(pc, before)
            supplied = stock_fitting(target)
            if supplied is None:
                break
            pc.carry(supplied["id"], 1)
            continue
        break
    _restore(pc, track, kept)
    coins = engine._coins_here()
    if spoiled:
        # Spoiled by the keeper's own roll: what the book's Craft rule ruins is lost, the
        # keeper's own fitting goes back on the shelf, and no fee is asked for spoiled work.
        if supplied is not None and int(pc.inventory.get(supplied["id"], 0) or 0) > int(
                (before.get("inventory") or {}).get(supplied["id"], 0) or 0):
            pc.spend(supplied["id"], 1)
        said = " ".join(d.get("tell", "") for d in done if d.get("tell"))
        spent = [e for d in done for e in d.get("effects") or [] if e.get("kind") == "spent"]
        _remember(scene, pc, keeper, words, "spoiled")
        return Outcome(
            intent_id=intent.id, op="commission", rolls=haggle_rolls + rolls,
            verdict="failure",
            effects=[{"kind": "commission", "ref": pc.ref, "keeper": keeper.ref,
                      "craft": craft_id, "items": [], "spoiled": True, "cp": 0,
                      "origin": ORIGIN}] + [dict(x, origin=ORIGIN) for x in spent],
            # And that no job is held: the work is not going on. Measured on the final
            # rerun of 2026-11-05 (5 of 7 runs spoiled): the smith's reply answered as if it
            # were done or under way ("It is finished. The metal is stubborn", "I'll have
            # it ready"). Re-asked with the recorded reply calls, 4 runs x 4: done, promised
            # or held as a job 13 of 16 as recorded, 7-9 of 16 with the act's line beside
            # the reply, 3-5 of 16 with "holds no job … nothing is being made" beside it
            # too (`planned._their_own_work` carries this tell to the reply).
            tell=(f"{haggle_said}{_cap(keeper.name)} takes the work in hand and spoils it: "
                  f"{_keeper_words(said, pc, keeper)} No fee is asked for spoiled work, and "
                  f"no job is taken: nothing is being made for {pc.name}."
                  ).strip(),
            because=intent.because)
    made = [e for d in done for e in d.get("effects") or [] if e.get("kind") == "made"]
    finished = any(d.get("final") or d.get("stop") for d in done)
    if not made or not finished:
        # Only the finished thing is a job done. Measured live on Corvin's save the day this
        # was built: the plain chain passes over a tempered, honed, folded blank (finer
        # work), forged a NEW pewter blank from the pack, could not fit it, and held that
        # half-thing for 45 minutes as the job. Nothing changes unless the work finishes.
        _unpack(pc, before)
        why = stopped.why if stopped is not None else "there is nothing to finish."
        return engine._refuse(intent, f"{haggle_said}{_cap(keeper.name)} cannot take the job: {why}")
    minutes = sum(int(s.minutes) for s in steps)
    fitting_cp = int(round(float(supplied["price_gp"]) * 100)) if supplied else 0
    listed = price_cp(minutes, sum(int(s.rent_cp or 0) for s in steps)) + fitting_cp
    bill = _undercut(listed, haggled_pct)
    purse, ok = goods.spend(pc.purse, bill)
    if not ok:
        _unpack(pc, before)
        _remember(scene, pc, keeper, words, "unpaid", cp=bill)
        return engine._refuse(intent, f"{haggle_said}{_cap(keeper.name)} wants "
                                      f"{goods.purse_line(_cp(bill), coins)} for the work, "
                                      f"and {pc.name} carries "
                                      f"{goods.purse_line(pc.purse, coins)}.")
    pc.purse = purse
    keeper.purse = goods.credit(getattr(keeper, "purse", None) or {}, bill)
    here = places_mod.find(engine.places(), scene.at or "")
    where_name = f"{keeper.name}'s, at {here.name}" if here is not None else keeper.name
    now = int(scene.clock_minutes or 0)
    held = []
    for e in made:
        key = str(e.get("stock") or "")
        got = inprogress.begin(pc, key, craft=CRAFT_ID, minutes=max(1, minutes), now=now,
                               label=f"{keeper.name} finishing {e.get('item')}",
                               where=f"place:{scene.at}", where_name=where_name,
                               doing="finishing")
        if got.get("ok"):
            held.append(str(e.get("item")))
    spent = [e for d in done for e in d.get("effects") or [] if e.get("kind") == "spent"
             and not (supplied and e.get("item") == supplied["name"])]
    gave = ", ".join(f"{x['count']} × {x['item']}" if int(x.get("count") or 1) > 1
                     else str(x["item"]) for x in spent)
    from . import sky

    quality = next((str(e.get("quality") or "") for e in reversed(made)), "")
    _remember(scene, pc, keeper, words, "taken", cp=bill)
    tell = (f"{haggle_said}{_cap(keeper.name)} takes the job for "
            f"{goods.purse_line(_cp(bill), coins)}"
            + (f" (haggled down from {goods.purse_line(_cp(listed), coins)})"
               if bill < listed else "")
            + (f", {_a(supplied['name'].lower())} from the shop's own stock included"
               if supplied else "")
            + (f", and takes {gave} to work" if gave else "")
            + f": {', '.join(held) or 'the work'} will be ready to collect here in "
              f"{sky.span_words(minutes)}."
            + (f" {QUALITY_SAID.get(quality, '')}" if QUALITY_SAID.get(quality) else ""))
    return Outcome(
        intent_id=intent.id, op="commission", rolls=haggle_rolls + rolls,
        effects=[{"kind": "commission", "ref": pc.ref, "keeper": keeper.ref,
                  "craft": craft_id, "items": held, "minutes": minutes, "cp": bill,
                  "listed_cp": listed, "quality": quality,
                  "fitting": supplied["id"] if supplied else "",
                  "ready_at": now + minutes, "origin": ORIGIN}]
        + [dict(x, origin=ORIGIN) for x in spent],
        tell=tell, because=intent.because)


# --- work asked for, and a price agreed -------------------------------------------------

def _asked_key(scene, pc, keeper) -> str:
    from . import market as market_mod
    from . import tradecraft

    return tradecraft.dealing_key("commission", pc.ref, str(scene.location_id or "nowhere"),
                                  keeper.ref, market_mod.day_of(scene.clock_minutes))


def _remember(scene, pc, keeper, words: str, how: str, *, cp: int = 0) -> None:
    """The work this keeper was asked for today and how it went (`spoiled`, `unpaid`,
    `taken`), on the counter's own record (`Scene.dealings`, where the haggle is kept):
    what a price agreed on a later turn takes the job for (`asked_of`)."""
    scene.dealings[_asked_key(scene, pc, keeper)] = {
        "item": " ".join(str(words or "").split()), "how": how, "cp": int(cp),
        "keeper": keeper.ref}


def asked_of(scene, pc, keeper) -> dict | None:
    """The work `pc` asked this keeper for today, here, or None."""
    rec = (getattr(scene, "dealings", None) or {}).get(_asked_key(scene, pc, keeper))
    return dict(rec) if isinstance(rec, dict) else None


def _paid_work(engine, pc, keeper) -> dict | None:
    """The keeper's paid work for the player still in hand here (In progress, this craft,
    at this place, under this keeper's label), as its In progress row, or None."""
    from . import inprogress

    now = int(engine.scene.clock_minutes or 0)
    here = f"place:{engine.scene.at}"
    for row in inprogress.entries(pc, now, craft=CRAFT_ID):
        if row.get("where") == here and str(row.get("label") or "").startswith(
                f"{keeper.name} finishing"):
            return row
    return None


def paid_before(who: str, keeper: str) -> str:
    """The price agreed for work already paid for, said as a payment in the past and none
    now (the refusal `resolve` gives "I agree to his price and pay")."""
    return (f"{who} paid {keeper} earlier, when the job was taken, and owes nothing now: no "
            f"coin changes hands this time.")


def _when(row: dict) -> str:
    from . import sky

    left = row.get("ready_in")
    if row.get("state") == "ready" or not left:
        return "now"
    return f"in {sky.span_words(int(left))}"


# What the keeper's own roll made of the finished thing, said after the job (the quality
# names are worldclass.QUALITY_NAMES), every grade said so the keeper's roll is never silent.
QUALITY_SAID = {
    "Crude": "It will be crude work: the keeper's hands were not at their best.",
    "Sound": "It will be sound, plain work.",
    "Fine": "It will be fine work: the keeper's hands were at their best.",
    "Superior": "It will be superior work: the keeper's hands were at their best.",
}
# How far a keeper's roll must clear the step for finer work, and how far below it a near
# miss is still finished as lesser work (CRB Craft: "If you fail by 4 or less, you make no
# progress this week. If you fail by 5 or more, you ruin half the raw materials").
FINER_BY = 10
SPOILED_BY = 5


def _cap(name: str) -> str:
    """A name starting a sentence: "the smith" -> "The smith"."""
    return name[:1].upper() + name[1:]


def _a(noun: str) -> str:
    noun = str(noun or "").strip()
    return ("an " if noun[:1].lower() in "aeiou" else "a ") + noun


def keeper_quality(margin: int) -> int | None:
    """The quality index a keeper's roll makes, or None when it spoils the work.

    The book's Craft check has no quality ladder; this app's forge does (Crude, Sound,
    Fine ...), and the owner's ruling of 2026-11-01 is that the keeper's own skill decides
    it and they can make lesser work or fail. So the book's two failure bands are kept —
    a miss by 5 or more ruins the materials — and its "no progress" band becomes the
    lesser work a paid hand finishes anyway rather than hand back: Crude. Made is the plain
    book item; ten over is finer work. RimWorld does the same by skill (quality "a random
    roll on a distribution centred by skill", rimworldwiki.com/wiki/Quality), and Dwarf
    Fortress caps the top tier rather than guarantee it — the step's own ceiling caps it
    here."""
    if margin <= -SPOILED_BY:
        return None
    if margin < 0:
        return 0
    return 2 if margin >= FINER_BY else 1


def keeper_roll(engine, keeper, step):
    """The keeper's Craft check for one step: their own sheet's Craft (NPC builds carry
    ranks), the engine's die, hidden. Pathfinder Unchained's `pure` material rolls twice
    and keeps the better, as the bench does."""
    try:
        mods = list(keeper.skill_modifiers("craft"))
    except Exception:       # noqa: BLE001 - a sheet with no Craft at all: the bare ability
        from .dice import Modifier

        mods = [Modifier(keeper.ability_mod("int"), "Int")]
    label = f"{keeper.name} Craft — {step.label}"
    roll = engine.dice.d20(mods, label=label, visibility="hidden")
    if step.roll_twice:
        again = engine.dice.d20(mods, label=label + " (pure, again)", visibility="hidden")
        roll = again if again.total > roll.total else roll
    return roll


def _walk(engine, craft, craft_id, pc, keeper, target):
    """The chain on the pack by the keeper's hands. (steps, reports, rolls, refusal or None,
    spoiled)."""
    from . import typed_craft

    steps, done, rolls = [], [], []
    stopped, spoiled = None, False
    first = _finish_piece(engine, craft, pc, target) if craft_id == "blacksmith" else None
    for _ in range(6):
        step, first = (first, None) if first is not None else \
            (craft.next_step(engine, pc, target, done), None)
        if step is None:
            break
        if isinstance(step, typed_craft.Refusal):
            stopped = step
            break
        steps.append(step)
        roll = keeper_roll(engine, keeper, step)
        rolls.append(roll)
        margin = roll.total - int(step.dc)
        quality = keeper_quality(margin)
        if quality is None:
            done.append(step.settle(False, margin))
            spoiled = True
            break
        report = step.settle(True, margin, quality=quality)
        done.append(report)
        if step.final or report.get("stop"):
            break
    return steps, done, rolls, stopped, spoiled


def _keeper_words(said: str, pc, keeper) -> str:
    """A step's tell is written for the player's own hands ("Corvin T. assembles ..."); on a
    commission the hands are the keeper's, and the player's mastery lines do not apply."""
    import re

    out = said.replace(pc.name, keeper.name)
    out = re.sub(r"\s*" + re.escape(keeper.name) + r" gains \d+ [^.]*mastery[^.]*\.", "", out)
    return " ".join(out.split())


def stock_fitting(target) -> dict | None:
    """The plain fitting a smith keeps on the shelf for the piece the job lacks: the
    cheapest common fitting the material catalogue says is bought (never gathered or cut
    from a beast) and fills that piece of that gear, by id on a tie. None for a job whose
    shape names no such piece."""
    from . import blacksmith as bs
    from . import materials

    info = (getattr(target, "data", None) or {}).get("info") or {}
    gear = str(info.get("gear") or "")
    names = bs.PIECES.get(gear)
    if not names:
        return None
    slot = names[1]
    key = "armour" if gear in ("armour", "shield") else "weapon"
    rows = []
    for mid, doc in materials.all().items():
        if doc.get("kind") != "fitting" or doc.get("tier") != "common":
            continue
        if doc.get("obtain") != "bought" or not doc.get("price_gp"):
            continue
        if slot not in ((doc.get("pieces") or {}).get(key) or ()):
            continue
        rows.append({"id": mid, "name": str(doc.get("name") or mid),
                     "price_gp": float(doc["price_gp"])})
    rows.sort(key=lambda r: (r["price_gp"], r["id"]))
    return rows[0] if rows else None


def _haggle(engine, intent, pc, keeper, partial):
    """The price talked down before the job (owner ruling 2026-11-01: "the price can be
    haggled with Diplomacy, like buying"). (percent off, the words, the rolls).

    Two doors to one number, the day's haggle with this keeper (`Scene.dealings`, the
    counter's own record, `tradecraft.haggled`): the counter's Haggle already won today
    (Profession against Sense Motive, the owner's option B) holds here too; and a
    commission OFFERED rather than agreed (`haggle`, written by the act->op table for a
    `tried` reading) is a Diplomacy Make Request (CRB p.93, the keeper's attitude DC +5 for
    each request heard today), which wins Ultimate Campaign's undercut — 2% and 1% a point
    over, never past 25% (`tradecraft.undercut`). Once a day with a keeper, win or lose: a
    refused request stands (the book), and a won one is the day's price."""
    from . import market as market_mod
    from . import requests as requests_mod
    from . import tradecraft

    scene = engine.scene
    place = str(scene.location_id or "nowhere")
    day = market_mod.day_of(scene.clock_minutes)
    won = _haggled_with(scene, pc.ref, place, keeper.ref, day)
    if not intent.params.get("haggle"):
        return won, "", []
    key = tradecraft.dealing_key("haggle", pc.ref, place, keeper.ref, day)
    if key in scene.dealings or won:
        return won, (f"{keeper.name} has already been haggled with today and holds to "
                     f"{won}% off. " if won else
                     f"{keeper.name} has already been haggled with today and holds to the "
                     f"list. "), []
    now = int(scene.clock_minutes or 0)
    why = requests_mod.refusal(keeper, requests_mod.FAVOUR, now)
    if why:
        return 0, f"{why} ", []
    value, basis = requests_mod.dc(keeper, requests_mod.FAVOUR, now)
    mods = list(pc.skill_modifiers("diplomacy"))
    roll = engine._roll_or_suspend(intent, pc, mods, "Diplomacy check (haggling the price)",
                                   value, partial)
    margin = roll.total - value
    engine._judge(roll, margin >= 0)
    pct = tradecraft.undercut(margin)
    scene.dealings[key] = {"percent": pct, "keeper": keeper.ref}
    requests_mod.remember(keeper, now, kind=requests_mod.FAVOUR, granted=margin >= 0)
    if pct:
        said = (f"{pc.name} haggles: Diplomacy {roll.total} against DC {value}, and "
                f"{keeper.name} comes down {pct}%. ")
    else:
        said = (f"{pc.name} haggles: Diplomacy {roll.total} against DC {value}, and "
                f"{keeper.name} will not come down. ")
    return pct, said, [roll]


def _haggled_with(scene, ref: str, place: str, keeper_ref: str, day: int) -> int:
    """The percentage this person won off this keeper today, whichever counter key the
    haggle was written under (the trade panel writes a stall, the commission the keeper)."""
    best = 0
    for key, rec in (getattr(scene, "dealings", None) or {}).items():
        parts = str(key).split("|")
        if len(parts) < 5 or parts[0] != "haggle" or parts[1] != ref:
            continue
        if parts[2] != place or parts[-1] != str(day):
            continue
        if parts[3] == keeper_ref or (rec or {}).get("keeper") == keeper_ref:
            best = max(best, int((rec or {}).get("percent", 0) or 0))
    return best


def _undercut(cp: int, percent: int) -> int:
    return int(math.ceil(int(cp) * (100 - int(percent)) / 100))


def _cp(n: int) -> dict:
    """A copper sum as the coins a purse line names."""
    from . import goods

    return goods.credit({}, int(n))


def _pack(pc) -> dict:
    """What a chain can change on the player, kept to put back on a refusal."""
    return {k: copy.deepcopy(getattr(pc, k, None))
            for k in ("stock", "inventory", "goods", "purse")}


def _unpack(pc, kept: dict) -> None:
    for k, v in kept.items():
        setattr(pc, k, v)


def _restore(pc, track: str, kept) -> None:
    """The player's standing in the craft, as it was: the work was the keeper's."""
    if kept is None:
        pc.world_classes.pop(track, None)
    else:
        pc.world_classes[track] = kept


CRAFT_ID = "commission"


def _register() -> None:
    from . import inprogress

    inprogress.register(CRAFT_ID, icon="hammer",
                        stop_words="The keeper keeps the work and the fee.")


_register()
