"""Held, questioned, judged and sentenced: what the watch does with a character it has taken.

The owner's ruling, 2026-11-01: "you are held questioned and if found guilty charged
appropriately, with murder being a death sentence. you should always have to ability to talk
your way out of things. but if you cant then either you pay your fine and have stolen goods
confiscated or worst case are executed. or you can escape from your cell or during the walk to
your execution." Before this the arrest (rules/arrest.py) ended in one night held and release
at morning for want of proof, whatever the character had done.

## What the traditions do (researched 2026-11-01; sources in content/rules/law.json)

* **Pathfinder 1e has no trial or fine procedure.** Ultimate Campaign's punishment table
  (Table 1-31) lists beating, fine, imprisonment, trial by combat and the rest with no
  amounts; the GameMastery Guide gives a settlement's law modifier and no sentences. What
  1e does have is the talk (Make Request, CRB p.93, whose rows include "aid that could result
  in punishment +15"; Bluff against Sense Motive, CRB p.90; Intimidate, CRB p.99), the escape
  DCs (Escape Artist tight space 30; Disable Device simple lock 20, +10 without thieves'
  tools; a locked good wooden door breaks at Strength 18) and Ultimate Intrigue's bribery
  (p.124: 25% or more of the target's NPC gear value to look the other way). Every roll here
  is one of those.
* **Skyrim** (UESP, Crime and Jail): pay the bounty and the stolen goods go to the evidence
  chest; jail; persuade; bribe; resist. Escape from jail leaves the bounty standing. Its
  predecessors are the abandoned ideas: Oblivion's "your life is forfeit" for resisting and
  Morrowind's Death Warrant (no payment possible past 5,000) both turned a crime system into
  a kill-on-sight switch, and jail that took real skill points (Morrowind, Oblivion) became
  Skyrim's lost progress only. So nothing here takes a skill, and resisting is a fight, never
  an automatic death.
* **Kingdom Come: Deliverance 2**: a fine, speech, or fight and flight before sentence;
  execution only for murder, a cutscene to "Game over" with the save kept. Warhorse said a
  realistic system "would be too harsh" (GamesRadar, relaying Edge) — the reason a death
  sentence here has two chances to talk and two to escape in front of it.
* **Baldur's Gate 3**: interrogation first (Persuasion, Intimidation or Deception, harder for a
  bigger crime), and every cell has an escape designed into it. **Divinity: Original Sin 2**:
  a lockpick in every cell. Both say the same thing: a cell is a puzzle with a way out.
* **Roman law** (Gaius, Institutes III.189-190) prices theft: double the value, fourfold when
  the thief is caught with it. That is the theft fine.

## The shape

One effect on the player, `law.custody`, through the applicator, its payload the stage:

1. **questioning** — posed when the player is taken. The player's next batch answers it: a
   Diplomacy, Bluff or Intimidate check (the DC is the engine's, `hearing`), or anything else,
   which is silence. Diplomacy or Bluff made: the charges are dropped and the player walks
   out. Intimidate made: let go out of fear, the warrant standing (the book's Intimidate
   leaves the target unfriendly and liable to report you, and these are the people reports go
   to). Missed or silent: guilty, if anything is proven; let go for want of proof otherwise.
2. **plea** — once more before sentence, mercy asked of the same officer (Make Request's
   simple aid, +5 as a second request). Made: death becomes the blood price, a fine is waived.
3. **sentence** — a fine (paid from the purse; what it cannot pay is worked off at a
   labourer's wage, at most thirty days) and the stolen goods given back to their owners, the
   town's warrants all cleared (Kingdom Come: accepting punishment clears the known crimes
   there); or, for murder, **condemned** to hang at first light.
4. **condemned** — the night in the cell. Pick the lock, squeeze out, break the door, or pay
   the jailer to look away. Out: free, the warrant standing.
5. **walk** — at first light the escort leads the player to the gallows. Break their hold
   (Escape Artist or a combat manoeuvre against the best of their CMDs), run (the same roll),
   or fight (`_law_joins` brings the watch in). Otherwise the sentence is carried out through
   `Actor.die`, and the page shows the death screen with its way back to the shelf.

Guilt is read from facts, never invented: the deeds record's rows somebody saw (never the
moral total — the owner's "it should not affect anything yet" is about the meter), the
killings the deeds record holds no row for that the watch saw itself (`watch`: an attacker
killed in the fight, a downed foe left to bleed out — manslaughter), and stolen goods found
on the player (the props ledger's `stolen` mark). A warrant's own charge is an accusation:
with nothing of those behind it, it falls at questioning and the warrant with it (the
owner's "No proof, released", 2026-11-01). A fight lost to the law is being taken
(`beaten`); during the walk it is the end.
"""
from __future__ import annotations

import functools
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import states
from .activeeffect import ActiveEffect

SOURCE = "rule:trial"


def choices(who: str, ways) -> str:
    """The player's choices, said apart from the facts and as choices still to make: "Still
    for Mira to choose: slip their hold (Escape Artist) and run, wrench free of it (a combat
    manoeuvre) and run, fight, or go along." The one form every tell that offers the player
    ways out uses (here and rules/arrest.py), so no narrator reads one as taken.

    Measured on the narration diagnosis bench (2026-11-04, mechanism 11): "A last chance:
    break their hold — slip it (Escape Artist) or wrench free (a combat manoeuvre) — and
    run, or fight. Or go to it." came back "You wrench your arms free" — the options sat
    inside the sentence of what happened, in the voice of a deed, and the planned slot is
    told to show what the engine decided. Said last, as a sentence of their own, in the
    future ("still to choose") rather than as a negation alone ("none of it done"): negated
    premises are a documented source of hallucination in language models ("The Impact of
    Negated Text on Hallucination with Large Language Models", arXiv 2510.20375)."""
    got = [str(w) for w in ways if str(w).strip()]
    listed = (got[0] if len(got) == 1 else
              ", ".join(got[:-1]) + ", or " + got[-1])
    return f"Still for {who} to choose: {listed}."
RECORD_SOURCE = "rule:trial/record"
EXECUTION = "rule:trial/execution"
CRIME_SOURCE = "rule:crime"
STAGES = ("questioning", "plea", "condemned", "walk")
# Released to clear a name the watch could not prove: the arrest's three days of grace.
GRACE_DAYS = 3
COWED_DAYS = 1
DAY = 24 * 60


# --- the rule document -----------------------------------------------------------------

def _path() -> Path:
    from django.conf import settings

    # BASE_DIR, never `__file__`: it points inside the bundle once frozen (CLAUDE.md).
    return Path(settings.BASE_DIR) / "content" / "rules" / "law.json"


@functools.cache
def document() -> dict:
    doc = json.loads(_path().read_text(encoding="utf-8"))
    problems = validate(doc)
    if problems:
        raise ValueError("content/rules/law.json is refused:\n  " + "\n  ".join(problems))
    return doc


def validate(doc: dict) -> list[str]:
    """Every problem with a law document, each with its fix named."""
    from . import requests as requests_mod
    from .bluff import LIES

    out: list[str] = []
    charges = doc.get("charges") if isinstance(doc, dict) else None
    if not isinstance(charges, dict) or not charges:
        return ["charges: give the charges as {\"murder\": {row}, ...}."]
    for kind, row in charges.items():
        at = f"charges.{kind}"
        if row.get("sentence") not in ("death", "fine"):
            out.append(f"{at}.sentence: write \"death\" or \"fine\".")
        if row.get("sentence") == "fine":
            gp = row.get("fine_gp")
            if isinstance(gp, bool) or not isinstance(gp, (int, float)) or gp < 0:
                out.append(f"{at}.fine_gp: a fine is a number of gold pieces, 0 or more.")
        if row.get("sentence") == "death" and row.get("plea") not in charges:
            out.append(f"{at}.plea: name the charge a plea commutes a death sentence to.")
        if not isinstance(row.get("gravity"), int):
            out.append(f"{at}.gravity: a whole number; the gravest charge sets the sentence.")
    for tag, row in (doc.get("deeds") or {}).items():
        if (row or {}).get("charge") not in charges:
            out.append(f"deeds.{tag}.charge: name one of {', '.join(charges)}.")
        if "after" in (row or {}) and row["after"] not in charges:
            out.append(f"deeds.{tag}.after: name one of {', '.join(charges)}.")
    if (doc.get("self_defence") or {}).get("charge") not in charges:
        out.append(f"self_defence.charge: what killing an attacker is charged as — one of "
                   f"{', '.join(charges)}.")
    for name, row in (doc.get("proof") or {}).items():
        if row.get("request") not in requests_mod.MODIFIERS:
            out.append(f"proof.{name}.request: a Make Request row of the book "
                       f"({', '.join(requests_mod.MODIFIERS)}).")
        if row.get("lie") not in LIES:
            out.append(f"proof.{name}.lie: one of {', '.join(LIES)}.")
    if set(doc.get("proof") or ()) != {"accused", "witnessed", "caught"}:
        out.append("proof: give accused, witnessed and caught.")
    for skill, row in (doc.get("cell") or {}).items():
        if not isinstance((row or {}).get("dc"), int):
            out.append(f"cell.{skill}.dc: a whole-number DC from the book.")
    return out


def _charge_rows() -> dict:
    return document()["charges"]


# --- the charge ------------------------------------------------------------------------

PROOF_ORDER = ("accused", "witnessed", "caught")


@dataclass
class Charge:
    kind: str
    proof: str = "accused"
    what: str = ""
    deed: str = ""
    warrant: str = ""
    subject: str = ""
    subject_name: str = ""
    goods: list = field(default_factory=list)
    worth_gp: float = 0.0
    # Deed keys of lesser charges merged into this one (an assault into the killing it
    # caused), judged with it.
    merged: list = field(default_factory=list)

    def said(self) -> str:
        row = _charge_rows().get(self.kind) or {}
        bits = [str(row.get("said") or self.kind)]
        if self.what:
            bits.append(f"({self.what})")
        bits.append("— " + str(document()["proof"][self.proof]["said"]))
        return " ".join(bits)


def _from_dicts(rows) -> list[Charge]:
    out = []
    for r in rows or ():
        try:
            out.append(Charge(**{k: v for k, v in dict(r).items()
                                 if k in Charge.__dataclass_fields__}))
        except TypeError:
            continue
    return out


def deed_key(row: dict) -> str:
    return f"{row.get('tag')}@{int(row.get('minute') or 0)}@{row.get('subject') or ''}"


def _town_of_place(place: str) -> str:
    from . import places as places_mod

    return places_mod.location_of(place or "") or ""


def town_here(engine) -> str:
    from . import places as places_mod

    return places_mod.location_of(engine.scene.at or "") or engine.scene.location_id


def _record(pc, town: str) -> ActiveEffect | None:
    key = f"law-record:{states.town_tag(town)}"
    return next((e for e in pc.effects if e.key == key), None)


def judged(pc, town: str) -> set:
    """The deeds the watch will not charge: dealt with already (`judged`), or done under a
    Sleight of Hand nobody saw through (`unnoticed`)."""
    rec = _record(pc, town)
    pay = (rec.payload or {}) if rec is not None else {}
    return set(pay.get("judged") or ()) | set(pay.get("unnoticed") or ())


def _judge_all(pc, town: str, keys, field: str = "judged") -> None:
    """Deeds this town has dealt with (or never noticed): never charged. One record a town."""
    keys = {k for k in keys if k}
    if not keys:
        return
    rec = _record(pc, town)
    pay = dict((rec.payload or {}) if rec is not None else {})
    pay[field] = sorted(set(pay.get(field) or ()) | keys)
    _write_record(pc, town, pay)


def _write_record(pc, town: str, pay: dict) -> None:
    """The town's record replaced whole through the applicator (law 2: one store)."""
    pay = dict(pay, town=town)
    pc.remove_effects(match=lambda e: e.key == f"law-record:{states.town_tag(town)}")
    pc.apply_effect(ActiveEffect(
        name="on the watch's books", kind="situation",
        key=f"law-record:{states.town_tag(town)}", source=RECORD_SOURCE,
        origin=RECORD_SOURCE, duration="until-dismissed", payload=pay))


def _record_pay(pc, town: str) -> dict:
    rec = _record(pc, town)
    return dict((rec.payload or {}) if rec is not None else {})


def _incident_charges(engine, pc, town: str) -> list:
    """Killings the watch's own eyes hold that the deeds record does not: an attacker
    killed in the fight, or a downed foe left to bleed out (`watch`)."""
    done = judged(pc, town)
    people = engine.scene.people
    out = []
    for inc in _record_pay(pc, town).get("incidents") or ():
        if inc.get("key") in done:
            continue
        seen = [r for r in inc.get("witnesses") or ()
                if r in people and not people[r].has_state(states.TRAVELS_WITH_YOU)]
        if not seen:
            continue
        out.append(Charge(kind=str(inc["crime"]),
                          proof="caught" if any(_is_law(people.get(r)) for r in seen)
                          else "witnessed",
                          what=str(inc.get("subject_name") or ""), deed=str(inc["key"]),
                          subject=str(inc.get("subject") or ""),
                          subject_name=str(inc.get("subject_name") or "")))
    return out


def _is_law(a) -> bool:
    return a is not None and a.has_state(states.GUARD)


def _deed_charges(engine, pc, town: str) -> list[Charge]:
    from . import deeds as deeds_mod
    from . import pricing

    rules = document()["deeds"]
    done = judged(pc, town)
    people = engine.scene.people
    out = []
    for row in deeds_mod.of(pc):
        rule = rules.get(str(row.get("tag") or ""))
        if rule is None or row.get("again"):
            continue
        if (_town_of_place(str(row.get("place") or "")) or engine.scene.location_id) != town:
            continue
        key = deed_key(row)
        if key in done:
            continue
        seen = [r for r in row.get("witnesses") or ()
                if r in people and not people[r].has_state(states.TRAVELS_WITH_YOU)]
        if not seen:
            # Nobody saw it: the law cannot prove what nobody saw.
            continue
        caught = any(_is_law(people.get(r)) for r in seen)
        what = str(row.get("what") or "")
        worth = 0.0
        kind = charge_of(rule, row)
        if kind == "theft" and what:
            try:
                worth = float(pricing.goods_worth(what) or 0)
            except Exception:       # noqa: BLE001 - an unpriced thing is worth nothing here
                worth = 0.0
        out.append(Charge(kind=kind, proof="caught" if caught else "witnessed",
                          what=_what_words(kind, what, row), deed=key,
                          subject=str(row.get("subject") or ""),
                          subject_name=str(row.get("subject_name") or ""), worth_gp=worth))
    return out


def charge_of(rule: dict, row: dict) -> str:
    """The charge a deed row answers for: the rule's, or its `after` charge when the death
    came after the player's harm rather than by their own act (the row's `manner`) — the
    owner's "letting someone bleedout ... not murder"."""
    if row.get("manner") == "after" and rule.get("after"):
        return str(rule["after"])
    return str(rule["charge"])


def _what_words(kind: str, what: str, row: dict) -> str:
    who = str(row.get("subject_name") or row.get("place_name") or "")
    if kind == "theft":
        return " from ".join(x for x in (what, who) if x)
    return who


def _goods_held(engine, pc) -> list[dict]:
    """Stolen things the player holds, from the props ledger: what a search finds."""
    return [r for r in engine.scene.props
            if r.get("held_by") == pc.ref and r.get("stolen")
            and r.get("owner") and r.get("owner") != pc.ref]


def charges(engine, pc, town: str) -> list[Charge]:
    """What the watch can charge the player with in this town, from facts only: the deeds
    somebody saw, the warrant's own charge, and stolen goods found on them."""
    from . import pricing

    rows = _charge_rows()
    out = _deed_charges(engine, pc, town) + _incident_charges(engine, pc, town)
    # The blow that killed is part of the killing (the common law's merger of the lesser
    # offence): measured live 2026-11-01, a victim struck down and left to bleed out was
    # charged "assault (Denna Krell); a killing (Denna Krell)" — fined twice for one harm.
    killed = {c.subject for c in out if c.kind in ("murder", "manslaughter") and c.subject}
    merged = [c for c in out if c.kind == "assault" and c.subject in killed]
    out = [c for c in out if c not in merged]
    for m in merged:
        into = next(c for c in out if c.subject == m.subject
                    and c.kind in ("murder", "manslaughter"))
        into.merged = list(into.merged) + [m.deed]
    kinds = {c.kind for c in out}
    deeds_charged = {c.deed for c in out}
    for e in pc.effects:
        if states.wanted_tag(town) not in (e.tags or ()):
            continue
        pay = e.payload or {}
        kind = str(pay.get("crime") or "")
        if kind not in rows or pay.get("deed") in deeds_charged or kind in kinds:
            continue
        if pay.get("deed") and pay["deed"] in judged(pc, town):
            continue
        out.append(Charge(kind=kind, proof="accused", warrant=e.source,
                          what=str(pay.get("what") or "")))
        kinds.add(kind)
    held = _goods_held(engine, pc)
    for c in out:
        if c.kind != "theft":
            continue
        mine = [r for r in held if not c.subject or r.get("owner") == c.subject]
        if mine:
            c.proof = "caught"
            c.goods = [str(r["name"]) for r in mine]
            held = [r for r in held if r not in mine]
    if held:
        worth = 0.0
        for r in held:
            try:
                worth += float(pricing.goods_worth(str(r["name"])) or 0)
            except Exception:       # noqa: BLE001
                pass
        out.append(Charge(kind="theft", proof="caught",
                          what=", ".join(str(r["name"]) for r in held),
                          goods=[str(r["name"]) for r in held], worth_gp=worth))
    return out


def gravest(chs: list[Charge]) -> Charge | None:
    rows = _charge_rows()
    return max(chs, key=lambda c: int(rows[c.kind]["gravity"]), default=None)


def best_proof(chs: list[Charge]) -> str:
    return max((c.proof for c in chs), key=PROOF_ORDER.index, default="accused")


def fine_cp(c: Charge) -> int:
    row = _charge_rows()[c.kind]
    gp = float(row.get("fine_gp") or 0)
    times = row.get("goods_times_caught" if c.proof == "caught" else "goods_times")
    if times and c.worth_gp:
        gp = max(gp, float(times) * float(c.worth_gp))
    return int(math.ceil(gp * 100))


def sentence_for(chs: list[Charge], mercy: bool) -> dict:
    """{"death": bool, "fine_cp": int, "for": [said]} — the gravest charge decides death; the
    rest are fines. Mercy commutes a death to the plea charge's fine and waives a fine."""
    rows = _charge_rows()
    top = gravest(chs)
    death = bool(top and rows[top.kind]["sentence"] == "death")
    if death and mercy:
        plea = Charge(kind=rows[top.kind]["plea"], proof=top.proof)
        return {"death": False, "fine_cp": fine_cp(plea), "commuted": True,
                "for": [c.said() for c in chs]}
    if death:
        return {"death": True, "fine_cp": 0, "for": [c.said() for c in chs]}
    total = 0 if mercy else sum(fine_cp(c) for c in chs if rows[c.kind]["sentence"] == "fine")
    return {"death": False, "fine_cp": total, "waived": bool(mercy),
            "for": [c.said() for c in chs]}


# --- who is here ----------------------------------------------------------------------

def custody(actor) -> ActiveEffect | None:
    for e in getattr(actor, "effects", ()) or ():
        if e.source == SOURCE and states.CUSTODY in (e.tags or ()):
            return e
    return None


def _named(name: str) -> str:
    """A label with its article ("the guardsman"), a proper name as it is — the rule
    `names.with_articles` applies at the engine's door, for tells that do not pass it."""
    name = " ".join(str(name or "").split())
    if not name or name[:1].isupper() or name.lower().startswith(("the ", "a ", "an ")):
        return name
    return f"the {name}"


def _names(people) -> str:
    names = [_named(p.name) for p in people]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _law_here(engine) -> list:
    scene = engine.scene
    return [a for r, a in scene.actors.items()
            if not a.is_pc and _is_law(a) and scene.conscious(r)
            and not a.has_state(states.TRAVELS_WITH_YOU)]


def questioner(engine, pay: dict):
    """Who asks the questions: the officer named when the player was taken, if still here
    and awake; else an officer here; else any of the law here."""
    scene = engine.scene
    q = scene.actors.get(str(pay.get("questioner") or ""))
    if q is not None and scene.conscious(q.ref) and _is_law(q):
        return q
    law = _law_here(engine)
    officers = [a for a in law if a.has_state(states.GUARD_OFFICER)]
    return (officers or law or [None])[0]


def _escort(engine, pay: dict) -> list:
    scene = engine.scene
    got = [scene.actors[r] for r in pay.get("by") or ()
           if r in scene.actors and scene.conscious(r)]
    q = questioner(engine, pay)
    if q is not None and q not in got:
        got.append(q)
    return got or _law_here(engine)


def _place_by(engine, names, *, not_ids=()) -> object | None:
    from . import places as places_mod

    rooms = {" ".join(p.name.split()).lower(): p for p in engine.places()
             if places_mod.storey_of(p.id) == 0 and p.id not in not_ids}
    return next((rooms[n] for n in names if n in rooms), None)


def _street(engine, pay: dict):
    """Where an escaped prisoner comes out: a place in town that is not the hold, the
    gallows or the gate (the gate is shut to the wanted)."""
    from . import places as places_mod

    skip = {pay.get("hold"), pay.get("gallows")}
    for p in engine.places():
        if p.id in skip or places_mod.storey_of(p.id) != 0:
            continue
        if " ".join(p.name.split()).lower() in places_mod.ENTRANCES:
            continue
        if places_mod.terrain_of(p.id) != places_mod.URBAN:
            continue
        return p
    return None


def _set(pc, held: ActiveEffect, **changes) -> ActiveEffect:
    """The custody record with its payload changed: removed and applied again, so the store
    keeps one record and the applicator sees every change (law 2)."""
    pay = dict(held.payload or {})
    pay.update(changes)
    pc.remove_effects(match=lambda e: e is held)
    fresh = ActiveEffect(name=_name_of(pay), kind="situation", key=held.key,
                         source=SOURCE, origin=SOURCE, duration="until-dismissed",
                         tags=(states.CUSTODY,), payload=pay)
    pc.apply_effect(fresh)
    return custody(pc) or fresh


def _name_of(pay: dict) -> str:
    stage = pay.get("stage")
    where = pay.get("hold_name") or "the watch's keeping"
    if stage == "condemned":
        return f"condemned, in the cell at {where}"
    if stage == "walk":
        return "led out to the gallows"
    return f"held and questioned at {where}"


# --- taken in ------------------------------------------------------------------------

def take_in(engine, pc, who, town: str, *, how: str = "taken"):
    """The player in the watch's hands: walked to the town's gaol (or wherever it holds
    people) with the guards who took them, and questioned there. Returns the outcome."""
    from .engine import Outcome

    scene = engine.scene
    doc = document()
    pc.remove_effects(source="rule:arrest")
    pc.remove_effects(source=SOURCE)
    hold = _place_by(engine, doc["holds"])
    engine.end_talk("taken")
    if scene.in_encounter:
        scene.end_encounter()
    if hold is not None and hold.id != scene.at:
        engine.place_party(hold.id)
    if hold is not None:
        # The guards who took them walk in with them (and are already there when the
        # player walked to the hold themselves).
        for g in who:
            if g.ref in scene.people and not g.is_pc and g.at != hold.id:
                scene.move(g.ref, hold.id)
    who = [g for g in who if g.ref in scene.actors]
    where = hold.name if hold is not None else "the watch's keeping"
    chs = charges(engine, pc, town)
    officers = [g for g in who if g.has_state(states.GUARD_OFFICER)] or \
        [a for a in _law_here(engine) if a.has_state(states.GUARD_OFFICER)]
    q = (officers or who or _law_here(engine) or [None])[0]
    lead = f"{_cap(_names(who) or 'The watch')} take{'s' if len(who) == 1 else ''} " \
           f"{pc.name} {'in' if how == 'taken' else 'up off the ground'} to {where}."
    # An accusation is not proof (the owner's ruling of 2026-11-01, "No proof, released"):
    # a charge with no witnessed deed and no stolen goods behind it — a warrant's word
    # alone, as A Small Favour's frame-up lays one — falls at questioning, and its warrant
    # with it. Before the ruling the warrant's accusation convicted a silent player, so an
    # innocent character framed for the killing would hang.
    fallen = [c for c in chs if c.proof == "accused" and not c.goods]
    chs = [c for c in chs if c not in fallen]
    for c in fallen:
        if c.warrant:
            pc.remove_effects(match=lambda e, src=c.warrant: e.source == src
                              and states.wanted_tag(town) in (e.tags or ()))
    fell = ""
    if fallen:
        fell = (f" The accusation of "
                f"{' and '.join(str(_charge_rows()[c.kind]['said']) for c in fallen)} "
                f"falls for want of proof: nobody saw {pc.name} do it, and nothing on "
                f"{pc.name} says otherwise; the warrant is torn up.")
    if not chs:
        # Nothing proven at all: every warrant of this town lifted — a warrant that says
        # nothing about what it is for is an accusation too.
        _clear_warrants(pc, town, only_rules=False)
        return _release(engine, pc, town, None, lead + fell + f" Questioned there, "
                        f"{pc.name} is let go for want of proof", grace=False,
                        effects_kind="no-proof",
                        hold={"hold": hold.id if hold is not None else scene.at,
                              "hold_name": where})
    pay = {"town": town, "stage": "questioning", "posed": True, "by": [g.ref for g in who],
           "questioner": q.ref if q is not None else "",
           "hold": hold.id if hold is not None else scene.at, "hold_name": where,
           "charges": [asdict(c) for c in chs]}
    pc.apply_effect(ActiveEffect(name=_name_of(pay), kind="situation",
                                 key=f"custody:{states.town_tag(town)}", source=SOURCE,
                                 origin=SOURCE, duration="until-dismissed",
                                 tags=(states.CUSTODY,), payload=pay))
    asker = _named(q.name) if q is not None else "the watch"
    tell = (f"{lead}{fell} {_cap(asker)} questions {pc.name}: charged with "
            f"{'; '.join(c.said() for c in chs)}. "
            + choices(pc.name, ["talk their way out (Diplomacy, Bluff or Intimidate)",
                                "say nothing"]))
    return Outcome(intent_id="", op="trial",
                   effects=[{"kind": "custody", "stage": "questioning", "held_at": where,
                             "charges": [c.kind for c in chs], "origin": SOURCE}],
                   tell=tell)


def _release(engine, pc, town: str, held, lead: str, *, grace: bool, effects_kind: str,
             clear_rule_warrants: bool = False, keys=(), hold: dict | None = None):
    """Let go: custody ended; with `grace`, the watch leaves them be for the grace days.
    The player walks out of the hold (`walk_out`): the custody record's own, or `hold`
    for a release before any custody was written (no proof at all)."""
    from . import arrest as arrest_mod
    from .engine import Outcome

    pc.remove_effects(source=SOURCE)
    if clear_rule_warrants:
        _clear_warrants(pc, town, only_rules=True)
    _judge_all(pc, town, keys)
    standing = states.standing_with_the_law(pc, town)
    tail = ""
    if grace and standing == "wanted":
        arrest_mod.stand_down(engine, pc, town, GRACE_DAYS, "let go to clear your name")
        tail = (f": the warrant stands, and the watch gives {GRACE_DAYS} days to clear the "
                f"name.")
    else:
        tail = "."
    out, moved = walk_out(engine, pc, held.payload if held is not None else hold)
    return Outcome(intent_id="", op="trial",
                   effects=[{"kind": "custody", "ended": effects_kind, "origin": SOURCE}]
                   + ([moved] if moved else []),
                   tell=lead + tail + out)


def walk_out(engine, pc, pay: dict | None) -> tuple[str, dict | None]:
    """Let go, the player walks out of the hold into the town: the party is put at the
    town's own place outside (`_street`, the place an escape comes out at — never the
    hold, the gallows or the gate), and the sentence says so. ("", None) when there is
    nowhere to go, a fight is on, or the party is not standing at the hold.

    Owner's call of 2026-11-03. Before it the tell said "walks out of the guardhouse" (or
    "is let go") while the scene kept the party in the guardhouse, and the read back judged
    every page that let them leave as a move the engine never made — on the bench of
    2026-11-02 that judgement's repair wrote "you are held in the guardhouse" over "you
    are released from the guardhouse", beside the tell "is let go, the matter closed"."""
    scene = engine.scene
    pay = dict(pay or {})
    hold = str(pay.get("hold") or scene.at or "")
    if scene.in_encounter or not hold or scene.at != hold:
        return "", None
    to = _street(engine, pay)
    if to is None or to.id == scene.at:
        return "", None
    # Walked out, the talk with the watch is over: measured live 2026-11-03, the turn after
    # the release still had "Pallo Farrow is no longer here; the conversation with them is
    # over" told on its own. The sentence below is the tell; end_talk's own is not needed.
    engine.end_talk("walked away")
    engine.place_party(to.id)
    where = pay.get("hold_name") or "the watch's keeping"
    return (f" {pc.name} walks out of {where} to {to.name}.",
            {"kind": "moved", "ref": pc.ref, "from": hold, "to": to.id, "origin": SOURCE})


def _clear_warrants(pc, town: str, *, only_rules: bool) -> None:
    """The town's warrants lifted: every one (a sentence served), or only those the law's
    own rules laid (a charge talked away — a story's warrant is the story's to clear)."""
    tag = states.wanted_tag(town)

    def gone(e) -> bool:
        if tag not in (e.tags or ()):
            return False
        return not only_rules or str(e.source or "").startswith("rule:")
    pc.remove_effects(match=gone)


# --- the hearing: the DC of a check made in custody ---------------------------------

@dataclass
class Hearing:
    dc: int | None
    basis: str
    label: str = ""
    opposed: dict | None = None
    refused: str = ""


def hearing(engine, intent, actor, skill: str) -> Hearing | None:
    """The engine's DC for a check the player makes in custody, or None when the check is
    nothing to do with it. Talk at questioning and at the plea; Escape Artist, Disable Device
    and Strength in the condemned cell. Every number is a book row (content/rules/law.json),
    never the plan's — a plan that could name the DC could talk anybody out of a cell."""
    from . import attitude as attitude_mod
    from . import requests as requests_mod

    if actor is None or not actor.is_pc:
        return None
    held = custody(actor)
    if held is None:
        return None
    pay = held.payload or {}
    stage = pay.get("stage")
    skill = str(skill or "").strip().lower()
    doc = document()
    if stage in ("questioning", "plea") and skill in doc["talk_skills"]:
        if (pay.get("answer") or {}).get("stage") == stage:
            # One answer a stage: "If a request is refused, the result does not change with
            # additional checks" (CRB p.93). Measured live 2026-11-01: the plan wrote two
            # Diplomacy checks for one line, the first at the law's DC 29 and the second
            # fell through to the plan's own DC 10 — a free second try at a third of the
            # price. Refused, with nothing rolled.
            q = questioner(engine, pay)
            who = _named(q.name) if q is not None else "The watch"
            return Hearing(dc=None, basis="", refused=(
                f"{_cap(who)} has heard {actor.name} out already; saying it again will not "
                f"change the answer. Nothing is rolled."))
        q = questioner(engine, pay)
        if q is None:
            return None
        chs = _from_dicts(pay.get("charges"))
        if stage == "plea":
            row, extra, lie = doc["plea"]["request"], int(doc["plea"]["additional"]), \
                doc["plea"]["lie"]
            why = "mercy before sentence, a second request"
        else:
            proof = doc["proof"][best_proof(chs)]
            row, extra, lie = proof["request"], 0, proof["lie"]
            why = f"letting go somebody {proof['said']}"
        if skill == "bluff":
            return Hearing(dc=None, basis=f"{q.name}'s Sense Motive",
                           opposed={"ref": q.ref, "skill": "sense motive", "lie": lie,
                                    "claim": ""})
        if skill == "intimidate":
            return Hearing(dc=attitude_mod.intimidate_dc(q),
                           basis=attitude_mod.dc_basis(q, "intimidate"))
        value = attitude_mod.influence_dc(q) + int(requests_mod.MODIFIERS[row]) + extra
        return Hearing(dc=value,
                       basis=(f"{attitude_mod.dc_basis(q, 'diplomacy')}; {row} "
                              f"{requests_mod.MODIFIERS[row]:+d} ({why})"
                              + (f"; additional request +{extra}" if extra else "")))
    if stage == "condemned":
        key = "strength" if skill in ("strength", "str") else skill
        row = (doc.get("cell") or {}).get(key)
        if row is None:
            return None
        dc = int(row["dc"])
        basis = str(row.get("source") or "")
        if key == "disable device" and not _has_tools(actor):
            dc += int(row.get("no_tools") or 0)
            basis += " (no thieves' tools)"
        return Hearing(dc=dc, basis=basis)
    return None


def _has_tools(pc) -> bool:
    return any("thieves' tools" in str(getattr(s, "base", "")).lower()
               for s in (pc.stock or {}).values())


def answered(engine, actor, skill: str, made: bool, margin: int) -> str:
    """A check the player made in custody, recorded for the batch's end to act on. The
    sentence to add to the check's tell, or ""."""
    if actor is None or not actor.is_pc:
        return ""
    held = custody(actor)
    if held is None:
        return ""
    pay = held.payload or {}
    stage = pay.get("stage")
    skill = str(skill or "").strip().lower()
    doc = document()
    if stage in ("questioning", "plea") and skill in doc["talk_skills"]:
        if (pay.get("answer") or {}).get("stage") == stage:
            return ""
        _set(actor, held, answer={"stage": stage, "skill": skill, "made": bool(made),
                                  "margin": int(margin)})
        q = questioner(engine, pay)
        name = _named(q.name) if q is not None else "The watch"
        return (f"{_cap(name)} hears it out." if made
                else f"{_cap(name)} is not moved.")
    if stage == "condemned":
        key = "strength" if skill in ("strength", "str") else skill
        row = (doc.get("cell") or {}).get(key)
        if row is None:
            return ""
        if made:
            _set(actor, held, escaped=key)
            return f"{actor.name} {row['said']}."
        return "It holds."
    return ""


# --- escape: the cell, the walk -----------------------------------------------------

def escape(engine, intent, actor, how: str, partial: dict):
    """The `escape` op in custody: out of the cell (Escape Artist through the window bars,
    or force — Strength against the door), or out of the escort's hands on the walk (Escape
    Artist or a combat manoeuvre against the best CMD among them). None when not in custody
    at a stage an escape means anything."""
    from .dice import d20_succeeds
    from .engine import Outcome

    held = custody(actor) if actor is not None and actor.is_pc else None
    if held is None:
        return None
    pay = held.payload or {}
    stage = pay.get("stage")
    how = str(how or "").strip().lower()
    if stage == "condemned":
        key = "escape artist" if how in ("escape artist", "slip") else (
            "strength" if how in ("cmb", "force") else "")
        if not key:
            art = sum(m.value for m in actor.skill_modifiers("escape artist")) \
                if _trained_or_free(actor, "escape artist") else -99
            key = "escape artist" if art - 30 >= actor.ability_mod("str") - 25 else "strength"
        return _cell_roll(engine, intent, actor, held, key, partial)
    if stage == "walk":
        return break_away(engine, intent, actor, held, how, partial)
    if stage in ("questioning", "plea"):
        return engine._refuse(intent, f"{actor.name} is held at {pay.get('hold_name')} "
                                      f"under the watch's eyes; there is nothing to slip "
                                      f"yet. " + choices(actor.name, [
                                          "talk", "wait for the sentence"]),
                              code="in_custody")
    return None


def _trained_or_free(actor, skill: str) -> bool:
    try:
        actor.skill_modifiers(skill)
        return True
    except Exception:       # noqa: BLE001 - IllegalSheet: trained only
        return False


def _cell_roll(engine, intent, actor, held, key: str, partial: dict):
    from .engine import Outcome
    from . import dc as dc_mod

    h = hearing(engine, intent, actor, key)
    if key == "strength":
        mods = actor.ability_check_modifiers("str")
        label = "Strength check — the cell door"
    else:
        try:
            mods = list(actor.skill_modifiers(key))
        except Exception:   # noqa: BLE001
            return engine._refuse(intent, f"{actor.name} has no training in {key.title()}.")
        label = f"{key.title()} — out of the cell"
    roll = engine._roll_or_suspend(intent, actor, mods, label, h.dc, partial)
    made = roll.total >= h.dc
    engine._judge(roll, made)
    said = answered(engine, actor, key, made, roll.total - h.dc)
    return Outcome(intent_id=intent.id, op=intent.op, rolls=[roll],
                   dc=dc_mod.ResolvedDC(value=h.dc, band=None, basis=h.basis).as_dict(),
                   verdict="success" if made else "failure", margin=roll.total - h.dc,
                   effects=[{"kind": "escape", "ref": actor.ref, "from": "cell", "how": key,
                             "made": made, "origin": SOURCE}],
                   tell=(f"{label}: {roll.total} against DC {h.dc}. {said}").strip(),
                   because=intent.because)


def break_away(engine, intent, actor, held, how: str, partial: dict, *, to: str = ""):
    """Out of the escort's hands on the walk: Escape Artist or a combat manoeuvre against
    the best CMD among those holding them (escaping a grapple, CRB p.200)."""
    from .dice import d20_succeeds, natural_said
    from .engine import Outcome

    pay = held.payload or {}
    escort = _escort(engine, pay)
    if not escort:
        _set(actor, held, escaped="walk", fleeing_to=to)
        return Outcome(intent_id=intent.id, op=intent.op,
                       effects=[{"kind": "escape", "ref": actor.ref, "from": "escort",
                                 "made": True, "origin": SOURCE}],
                       tell=f"Nobody is holding {actor.name}.", because=intent.because)
    holder = max(escort, key=lambda g: sum(m.value for m in g.cmd_modifiers(
        maneuver="grapple")))
    cmd = sum(m.value for m in holder.cmd_modifiers(maneuver="grapple"))
    cmb = list(actor.cmb_modifiers("escape"))
    art = list(actor.skill_modifiers("escape artist")) \
        if _trained_or_free(actor, "escape artist") else None
    how = {"slip": "escape artist", "force": "cmb"}.get(how, how)
    if how not in ("cmb", "escape artist") or (how == "escape artist" and art is None):
        how = ("escape artist" if art is not None
               and sum(m.value for m in art) > sum(m.value for m in cmb) else "cmb")
    mods = art if how == "escape artist" else cmb
    label = ("Escape Artist — out of the escort's hands" if how == "escape artist"
             else "Combat manoeuvre — out of the escort's hands")
    roll = engine._roll_or_suspend(intent, actor, mods, label, cmd, partial)
    made = d20_succeeds(roll, cmd) if how == "cmb" else roll.total >= cmd
    engine._judge(roll, made)
    nat = natural_said(roll, cmd) if how == "cmb" else ""
    said = (f"{'Escape Artist' if how == 'escape artist' else 'CMB'} "
            f"{nat + ', ' if nat else ''}{roll.total} against {holder.name}'s CMD {cmd}")
    if made:
        _set(actor, held, escaped="walk", fleeing_to=to)
        tell = f"{actor.name} tears free of {holder.name}'s grip ({said})."
    else:
        tell = f"{holder.name}'s grip holds ({said})."
    return Outcome(intent_id=intent.id, op=intent.op, rolls=[roll],
                   verdict="success" if made else "failure", margin=roll.total - cmd,
                   effects=[{"kind": "escape", "ref": actor.ref, "from": holder.ref,
                             "how": how, "made": made, "origin": SOURCE}],
                   tell=tell, because=intent.because)


def _going_along(engine, intent, pay: dict) -> bool:
    """Whether a walk on the gallows road goes where the escort is going: a travel that
    names no place, or names the gallows' own place (by id, `places.find` against the
    engine's places — never the words). Anywhere else is a walk away from them."""
    from . import places as places_mod

    said = " ".join(str((intent.params or {}).get("place") or "").split())
    if not said:
        return True
    try:
        found = places_mod.find(engine.places(), said)
    except Exception:  # noqa: BLE001 — a place nobody can find is no going along
        return False
    return found is not None and str(getattr(found, "id", "")) == str(pay.get("gallows") or "")


def on_travel(engine, intent, partial: dict):
    """A walk somewhere while held: refused, naming the ways out — on the walk to the
    gallows too, until the player has broken the escort's hold (an `escape`), after which
    the walk is the run. None when the player is not held, or has broken free.

    A walk on the gallows road was first rolled as the break-away itself. Measured live
    2026-11-01 on the owner's save, twice: "I walk to the gallows with my head held high"
    founded a place called the gallows and rolled a break-away the player never meant, and
    "I go to the gallows with my head held high" was planned as a travel to the gate, rolled
    as a dash, made, and the condemned man walked free by going quietly. The book agrees
    with refusing: somebody held cannot move until the hold is broken (CRB p.200)."""
    pc = engine.scene.actors.get(intent.actor or "") or engine.scene.pc()
    held = custody(pc) if pc is not None and pc.is_pc else None
    if held is None:
        return None
    pay = held.payload or {}
    stage = pay.get("stage")
    if stage == "walk":
        if pay.get("escaped"):
            if intent.params.get("place"):
                _set(pc, held, fleeing_to=str(intent.params.get("place") or ""))
            return None
        if _going_along(engine, intent, pay):
            # A walk WITH the escort, to where they are taking the player, is going along:
            # the trial's own next step takes the player there (`_execution`). Measured on
            # the narration diagnosis bench (2026-11-04): "I walk with them to the gallows"
            # was read `follow: them`, planned as a travel to the market (the gallows) or
            # to nowhere, refused here as a walk "anywhere else", and that refusal's ways
            # out were told as taken on 3 of 3 runs ("The escort staggers back, caught off
            # guard by your sudden resistance").
            from .engine import Outcome

            return Outcome(intent_id=intent.id, op="travel", actor=pc.ref,
                           effects=[{"kind": "custody", "going_along": True,
                                     "origin": SOURCE}],
                           tell=f"{pc.name} goes along with the escort toward "
                                f"{pay.get('gallows_name') or 'the gallows'}, held.")
        return engine._refuse(intent, (
            f"{pc.name} is held by the escort on the way to {pay.get('gallows_name')}, "
            f"and their hold is firm: {pc.name} walks nowhere else while it holds. "
            + choices(pc.name, ["slip their hold (Escape Artist) and run",
                                "wrench free of it (a combat manoeuvre) and run",
                                "fight", "go along"])),
            code="in_custody")
    if stage == "condemned":
        why = (f"{pc.name} is locked in the condemned cell at {pay.get('hold_name')}. "
               + choices(pc.name, ["pick the lock (Disable Device)",
                                   "squeeze out between the window bars (Escape Artist)",
                                   "break the door (Strength)",
                                   "pay the jailer to look away"]))
    else:
        why = (f"{pc.name} is held at {pay.get('hold_name')} and questioned; the watch "
               f"does not let them walk out. "
               + choices(pc.name, ["talk (Diplomacy, Bluff or Intimidate)",
                                   "wait for the sentence"]))
    return engine._refuse(intent, why, code="in_custody")


def break_door(engine, intent, pc, how: str, partial: dict):
    """`break_in` in the condemned cell: picking the lock (Disable Device) or forcing the
    door (Strength), at the cell's DCs. None when not condemned."""
    held = custody(pc) if pc is not None else None
    if held is None or (held.payload or {}).get("stage") != "condemned":
        return None
    if how == "pick":
        if not _trained_or_free(pc, "disable device"):
            return engine._refuse(intent, f"{pc.name} has no training in picking locks "
                                          f"(Disable Device is trained only). The door can "
                                          f"still be forced.")
        return _cell_roll(engine, intent, pc, held, "disable device", partial)
    return _cell_roll(engine, intent, pc, held, "strength", partial)


def bribe_price_cp(guard) -> int:
    """Ultimate Intrigue p.124: the guard's CR as the heroic level on Table 14-9, a quarter
    of that gear's value to look the other way."""
    from . import attitude as attitude_mod
    from . import npc_gear

    level = max(1, min(len(npc_gear.TABLE_14_9) - 1, int(attitude_mod._hit_dice(guard) or 1)))
    gp = npc_gear.TABLE_14_9[level][0] * float(document()["bribe"]["share"])
    return int(math.ceil(gp)) * 100


def bribed(engine, intent, outcome) -> str:
    """Coin handed to one of the law while held: enough, and they look the other way;
    too little, and it is handed back. The sentence for the give's tell, or ""."""
    from . import goods

    scene = engine.scene
    pc = scene.pc()
    held = custody(pc) if pc is not None else None
    if held is None or (held.payload or {}).get("escaped"):
        return ""
    worth = dict(goods.DENOMINATIONS)
    for e in outcome.effects or ():
        if e.get("kind") != "give" or e.get("from") != pc.ref:
            continue
        taker = scene.actors.get(str(e.get("to") or ""))
        coin = str(e.get("item") or "")
        if not _is_law(taker) or coin not in worth:
            continue
        cp = int(e.get("count") or 0) * worth[coin]
        price = bribe_price_cp(taker)
        coins = engine._coins_here()
        if cp >= price:
            _set(pc, held, escaped="bribe", bribed=taker.ref)
            return (f"{taker.name} pockets it and looks the other way: the door is left "
                    f"unlocked.")
        # Handed back: a bribe too small buys nothing, and the coin is the player's still.
        # The same coins, not change for them: a guard does not hand back platinum for gold.
        n = int(e.get("count") or 0)
        theirs = dict(taker.purse or {})
        theirs[coin] = max(0, int(theirs.get(coin, 0) or 0) - n)
        taker.purse = {k: v for k, v in theirs.items() if v}
        mine = dict(pc.purse or {})
        mine[coin] = int(mine.get(coin, 0) or 0) + n
        pc.purse = mine
        return (f"{taker.name} pushes it back: looking the other way would take "
                f"{goods.purse_line(goods.coins_for(price), coins)}.")
    return ""


# --- the end of a batch --------------------------------------------------------------

def settle(engine) -> list:
    """The trial's move at the end of a batch. Empty when the player is not held."""
    scene = engine.scene
    pc = scene.pc()
    held = custody(pc) if pc is not None else None
    if held is None or scene.awaiting:
        return []
    if scene.in_encounter:
        if not (held.payload or {}).get("fought"):
            _set(pc, held, fought=True)
        return []
    pay = dict(held.payload or {})
    town = str(pay.get("town") or town_here(engine))
    if pay.get("escaped"):
        return [_escaped(engine, pc, held, town)]
    if pay.get("fought") and not _law_here(engine):
        # A fight with the watch, and nobody of the law left standing over them.
        _set(pc, held, escaped="fight")
        return [_escaped(engine, pc, custody(pc), town)]
    stage = pay.get("stage")
    if stage == "questioning":
        return [_after_questioning(engine, pc, held, town)]
    if stage == "plea":
        return [_sentence(engine, pc, held, town)]
    if stage == "condemned":
        return [_dawn(engine, pc, held, town)]
    if stage == "walk":
        return [_execution(engine, pc, held, town)]
    return []


def _after_questioning(engine, pc, held, town: str):
    from .engine import Outcome

    pay = held.payload or {}
    chs = _from_dicts(pay.get("charges"))
    ans = pay.get("answer") or {}
    q = questioner(engine, pay)
    asker = _named(q.name) if q is not None else "the watch"
    keys = [k for c in chs for k in [c.deed, *c.merged]]
    if ans.get("stage") == "questioning" and ans.get("made"):
        if ans.get("skill") == "intimidate":
            from . import arrest as arrest_mod

            pc.remove_effects(source=SOURCE)
            arrest_mod.stand_down(engine, pc, town, COWED_DAYS, "frightened the watch")
            out, moved = walk_out(engine, pc, pay)
            return Outcome(intent_id="", op="trial",
                           effects=[{"kind": "custody", "ended": "cowed", "origin": SOURCE}]
                           + ([moved] if moved else []),
                           tell=(f"Cowed, {asker} lets {pc.name} go. Nothing is dropped: "
                                 f"the charges stand, and the watch will remember who "
                                 f"frightened it.{out}"))
        # The walk out of the hold is `_release`'s own sentence (`walk_out`), with the
        # place it ends at.
        return _release(engine, pc, town, held,
                        f"{_cap(asker)} drops the charges, and {pc.name} is free to go",
                        grace=True, effects_kind="cleared",
                        clear_rule_warrants=True, keys=keys)
    if not chs:
        return _release(engine, pc, town, held, f"{_cap(asker)} has nothing to hold "
                        f"{pc.name} on, and lets them go", grace=True,
                        effects_kind="no-proof")
    sent = sentence_for(chs, mercy=False)
    _set(pc, held, stage="plea", answer=None)
    top = gravest(chs)
    what = ("death, hanged at first light tomorrow" if sent["death"]
            else f"a fine of {_coin(engine, sent['fine_cp'])}")
    took = (" and the stolen goods given back" if any(c.goods for c in chs) else "")
    # The sentence said as still to come, after the last word. Measured on the narration
    # diagnosis bench (2026-11-04, mechanism 9): "The sentence for murder is death, hanged
    # at first light tomorrow. Before it is passed, … may speak once more" came back "He
    # informs you that you are sentenced to death by hanging" — "is death" read as passed.
    tell = (f"{_cap(asker)} finds {pc.name} guilty of "
            f"{'; '.join(c.said() for c in chs)}. {_cap(asker)} will pass sentence after "
            f"{pc.name}'s last word, and has not passed it yet: for "
            f"{_charge_rows()[top.kind]['said']} the law's sentence will be {what}{took}. "
            + choices(pc.name, ["speak once more (Diplomacy, Bluff or Intimidate)",
                                "say nothing"]))
    # The hour a death sentence is set for, on the record (`scheduled`): what the read back
    # checks an hour claim against instead of the clock (`beat_verify._hour_told`).
    fx = {"kind": "verdict", "guilty": [c.kind for c in chs], "death": sent["death"],
          "fine_cp": sent["fine_cp"], "origin": SOURCE}
    if sent["death"]:
        fx["scheduled"] = _first_light(engine)
    return Outcome(intent_id="", op="trial", effects=[fx], tell=tell)


def _first_light(engine) -> int:
    """The clock minute of the next first light (the hour a death sentence is carried out)."""
    from . import timewords

    now = int(engine.scene.clock_minutes or 0)
    return now + int(timewords.minutes_until("until dawn", now) or 8 * 60)


def _coin(engine, cp: int) -> str:
    from . import goods

    return goods.purse_line(goods.coins_for(int(cp)), engine._coins_here())


def _sentence(engine, pc, held, town: str):
    from . import goods
    from .engine import Outcome

    scene = engine.scene
    pay = held.payload or {}
    chs = _from_dicts(pay.get("charges"))
    ans = pay.get("answer") or {}
    mercy = bool(ans.get("stage") == "plea" and ans.get("made"))
    sent = sentence_for(chs, mercy=mercy)
    q = questioner(engine, pay)
    asker = _named(q.name) if q is not None else "the watch"
    if sent["death"]:
        # Sentence passed, the hearing is over: whoever the player was talking to is not
        # holding a conversation through the night. Measured live 2026-11-01: "I pray
        # through the night" was refused "still in conversation with the guardsman" from
        # the plea, and the prose told the refusal over the dawn.
        engine.end_talk("sentenced")
        doc = document()
        gallows = _place_by(engine, doc["gallows"], not_ids=(pay.get("hold"),)) or \
            _place_by(engine, doc["gallows"])
        dawn = _first_light(engine)
        _set(pc, held, stage="condemned", answer=None, dawn=dawn,
             gallows=gallows.id if gallows is not None else "",
             gallows_name=gallows.name if gallows is not None else "the gallows")
        jailer = next(iter(_law_here(engine)), None)
        price = _coin(engine, bribe_price_cp(jailer)) if jailer is not None else ""
        tell = (f"{_cap(asker)} passes sentence: {pc.name} is to hang at first light tomorrow for "
                f"{_charge_rows()[gravest(chs).kind]['said']}. Until then, the condemned "
                f"cell at {pay.get('hold_name')}. "
                + choices(pc.name, ["pick the lock (Disable Device)",
                                    "squeeze out between the window bars (Escape Artist)",
                                    "break the door (Strength)"]
                          + ([f"pay {jailer.name} {price} to look the other way"]
                             if price else [])))
        return Outcome(intent_id="", op="trial",
                       effects=[{"kind": "sentence", "death": True, "scheduled": dawn,
                                 "origin": SOURCE}],
                       tell=tell)
    # A fine, and the stolen goods given back.
    bits = [f"{_cap(asker)} passes sentence on {pc.name}"
            + (": the death sentence is commuted to the blood price" if sent.get("commuted")
               else ": mercy, and the fine is waived" if sent.get("waived") else "")
            + "."]
    effects: list[dict] = [{"kind": "sentence", "death": False, "fine_cp": sent["fine_cp"],
                            "mercy": mercy, "origin": SOURCE}]
    owed = int(sent["fine_cp"])
    if owed:
        have = goods.in_copper(pc.purse or {})
        paid = min(have, owed)
        if paid:
            pc.purse, _ok = goods.spend(pc.purse or {}, paid)
        bits.append(f"The fine is {_coin(engine, owed)}"
                    + (f"; {pc.name} pays {_coin(engine, paid)}" if paid else
                       f"; {pc.name} has no coin to pay it")
                    + ".")
        left = owed - paid
        if left > 0:
            labour = document()["labour"]
            wage = int(labour["wage_cp"])
            days = min(int(labour["most_days"]), int(math.ceil(left / wage)))
            # The gaol feeds its labour: the weeks are not charged to the body.
            ended = scene.advance(days * DAY, charge_body=False).get("ended") or []
            worked = days * wage
            bits.append(f"The rest is worked off at the gaol, a labourer's wage a day: "
                        f"{days} day{'s' if days != 1 else ''}"
                        + (" — the most the watch will hold anybody for a fine, and what "
                           "is still owed is written off" if worked < left else "")
                        + ".")
            if ended:
                bits.append("Ended: " + ", ".join(ended) + ".")
            effects.append({"kind": "labour", "days": days, "origin": SOURCE})
        effects.append({"kind": "fine", "cp": owed, "paid_cp": paid, "origin": SOURCE})
    returned = _confiscate(engine, pc)
    if returned:
        bits.append("Taken back to their owners: " + ", ".join(
            f"{r['item']} to {r['owner_name']}" for r in returned) + ".")
        effects.extend(dict(r, kind="confiscated", origin=SOURCE) for r in returned)
    # The debt is paid: every warrant of this town lifted (Kingdom Come: accepting the
    # punishment clears the crimes known there), and these deeds never charged again.
    _clear_warrants(pc, town, only_rules=False)
    pc.remove_effects(match=lambda e: states.suspected_tag(town) in (e.tags or ()))
    _judge_all(pc, town, [k for c in chs for k in [c.deed, *c.merged]])
    pc.remove_effects(source=SOURCE)
    bits.append(f"{pc.name} is let go, the matter closed.")
    effects.append({"kind": "custody", "ended": "served", "origin": SOURCE})
    out, moved = walk_out(engine, pc, pay)
    if moved:
        bits.append(out.strip())
        effects.append(moved)
    # A name that ends in a full stop ("Corvin T.") ends the sentence itself: measured live,
    # "passes sentence on Corvin T..".
    return Outcome(intent_id="", op="trial", effects=effects,
                   tell=" ".join(bits).replace("..", "."))


def _confiscate(engine, pc) -> list[dict]:
    """Stolen things off the player and back to the people they were stolen from: the
    item leaves the player's holdings (the give door, from the player to nobody) and its
    ledger record is put in the owner's hands, no longer marked stolen."""
    from .engine import Intent

    scene = engine.scene
    out = []
    for rec in list(_goods_held(engine, pc)):
        name = str(rec.get("name") or "")
        owner = scene.people.get(str(rec.get("owner") or ""))
        try:
            engine._op_give(Intent(op="give", actor=pc.ref,
                                   params={"item": name, "from_": pc.ref},
                                   because="confiscated by the watch"), {})
        except Exception:       # noqa: BLE001 - the ledger is still put right below
            pass
        rec.pop("at", None)
        rec.pop("square", None)
        rec.pop("stolen", None)
        rec["held_by"] = str(rec.get("owner") or "")
        out.append({"item": name, "owner": str(rec.get("owner") or ""),
                    "owner_name": owner.name if owner is not None else "their owner"})
    return out


def _dawn(engine, pc, held, town: str):
    """The night in the condemned cell passes; at first light, the walk."""
    from .engine import Outcome

    scene = engine.scene
    pay = held.payload or {}
    left = max(0, int(pay.get("dawn") or scene.clock_minutes) - int(scene.clock_minutes))
    ended = scene.advance(left).get("ended") or [] if left else []
    engine.end_talk("led out")
    escort = _escort(engine, pay)
    _set(pc, held, stage="walk", by=[g.ref for g in escort])
    gallows = pay.get("gallows_name") or "the gallows"
    tell = (f"The night passes in the cell. At first light "
            f"{_names(escort) or 'the watch'} lead{'s' if len(escort) == 1 else ''} "
            f"{pc.name} out of {pay.get('hold_name')} toward {gallows}, hands held fast. "
            + choices(pc.name, ["slip their hold (Escape Artist) and run",
                                "wrench free of it (a combat manoeuvre) and run",
                                "fight", "go along"]))
    if ended:
        tell += " Ended: " + ", ".join(ended) + "."
    return Outcome(intent_id="", op="trial",
                   effects=[{"kind": "custody", "stage": "walk", "origin": SOURCE}],
                   tell=tell)


def _execution(engine, pc, held, town: str):
    """The sentence carried out, through the one door death is written by."""
    from .engine import Outcome

    scene = engine.scene
    pay = held.payload or {}
    gallows = str(pay.get("gallows") or "")
    if gallows and gallows != scene.at:
        try:
            engine.place_party(gallows)
        except ValueError:
            pass
    chs = _from_dicts(pay.get("charges"))
    top = gravest(chs)
    pc.remove_effects(source=SOURCE)
    pc.die(EXECUTION)
    where = pay.get("gallows_name") or "the gallows"
    return Outcome(intent_id="", op="trial",
                   effects=[{"kind": "condition", "ref": pc.ref, "condition": "dead",
                             "origin": EXECUTION},
                            {"kind": "custody", "ended": "executed", "origin": SOURCE}],
                   # "With the town looking on", not "before the town": the slot read
                   # "before" as time — "before the crowd can gather", "before the town
                   # can witness your final moments" (2 errors on round 3's bench). Re-asked
                   # with the recorded calls, 7 runs x 3: 5 of 21 as time; 0 of 21 so.
                   tell=(f"At {where}, with the town looking on, {pc.name} is hanged for "
                         f"{_charge_rows()[top.kind]['said'] if top else 'the crime'}. "
                         f"{pc.name} is dead."))


def _escaped(engine, pc, held, town: str):
    """Out: of the cell, of the escort's hands, or past a jailer paid to look away. Free,
    and still wanted — escaping is not acquittal (Skyrim: "If you do escape, your bounty
    will remain")."""
    from .engine import Outcome

    scene = engine.scene
    pay = held.payload or {}
    how = str(pay.get("escaped") or "")
    to = None
    if pay.get("fleeing_to"):
        from . import places as places_mod

        to = places_mod.find(engine.places(), str(pay["fleeing_to"]))
    to = to or _street(engine, pay)
    pc.remove_effects(source=SOURCE)
    if to is not None and to.id != scene.at and not scene.in_encounter:
        engine.place_party(to.id)
    where = to.name if to is not None else "the streets"
    lead = {"walk": f"Away from the escort, {pc.name} runs",
            "fight": f"With the watch down, {pc.name} gets clear",
            "bribe": f"Through the door the jailer left unlocked, {pc.name} slips out",
            }.get(how, f"Out of the cell, {pc.name} slips away")
    return Outcome(intent_id="", op="trial",
                   effects=[{"kind": "custody", "ended": "escaped", "how": how,
                             "origin": SOURCE}],
                   tell=(f"{lead} and is at {where}. The warrant still stands, and the "
                         f"next guard who sees {pc.name} will try again."))


# --- the law beats the player ---------------------------------------------------------

def beaten(engine, pc, winners) -> tuple[list, list] | None:
    """A player beaten senseless or bleeding by the law in a town where they are wanted:
    taken in rather than robbed — or, on the walk to the gallows, the sentence carried out.
    (effects, lines), or None when the law has no claim on them here."""
    law = [w for w in winners if _is_law(w)]
    if not law:
        return None
    held = custody(pc)
    town = str((held.payload or {}).get("town") or "") if held is not None else town_here(engine)
    if held is not None and (held.payload or {}).get("stage") in ("condemned", "walk"):
        out = _execution(engine, pc, held, town)
        return out.effects, [out.tell]
    if states.standing_with_the_law(pc, town) != "wanted" and held is None:
        return None
    out = take_in(engine, pc, law, town, how="beaten")
    return out.effects, [out.tell]


# --- the warrant's writer: a crime somebody saw --------------------------------------

def _sleight_total(earlier) -> int | None:
    """The player's Sleight of Hand made earlier in this batch, its total — or None."""
    def get(x, k):
        return x.get(k) if isinstance(x, dict) else getattr(x, k, None)

    for o in reversed(list(earlier or ())):
        if get(o, "op") != "check" or get(o, "verdict") != "success":
            continue
        roll = next(iter(get(o, "rolls") or ()), None)
        if roll is not None and str(get(roll, "label") or "").lower().startswith(
                "sleight of hand"):
            total = get(roll, "total")
            if total is None and isinstance(roll, dict):
                total = sum(roll.get("faces") or ()) + sum(
                    int(m.get("value") or 0) for m in roll.get("modifiers") or ())
            return int(total or 0)
    return None


def _noticed(engine, seen: list, total: int | None) -> list:
    """Who of those present saw the act for what it was. Without a Sleight of Hand, all of
    them. With one made, each rolls Perception against its total (CRB p.104, Sleight of
    Hand: "The opponent makes a Perception check to detect the attempt, opposed by the
    Sleight of Hand check result"), on the engine's hidden die. Measured live 2026-11-01:
    a "flawless" Sleight of Hand at the stall was still "seen by" both guardsmen, because
    every conscious person present was a witness whatever the hands did."""
    if total is None:
        return seen
    out = []
    for a in seen:
        try:
            mods = a.skill_modifiers("perception")
        except Exception:       # noqa: BLE001
            mods = []
        if engine.dice.d20(mods, label=f"{a.name} Perception", visibility="hidden").total \
                >= total:
            out.append(a)
    return out


def report(engine, found: list[dict], earlier=()):
    """A crime the deeds reader just recorded, seen by somebody in town, reaches the
    watch: a guard who saw it, or a killing anybody saw, is a warrant at once; anything
    else seen makes the player suspected, and a second time wanted (the break-in's ladder,
    `Engine._witnessed_break_in`). An outcome with the tell, or None. `earlier` is this
    batch's outcomes so far, for a Sleight of Hand the act was done under."""
    from . import places as places_mod
    from .engine import Outcome

    scene = engine.scene
    pc = scene.pc()
    if pc is None:
        return None
    rules = document()["deeds"]
    effects, said = [], []
    for rec in found or ():
        if rec.get("kind") not in ("deed", "incident") or rec.get("again"):
            continue
        # A deed row of the record, or one of the watch's own incidents (`watch`), which
        # carries its town, its key and its charge.
        rule = (document()["self_defence"] if rec.get("kind") == "incident"
                else rules.get(str(rec.get("tag") or "")))
        if not rule or not rule.get("report"):
            continue
        town = str(rec.get("town") or "") or town_here(engine)
        if not rec.get("town") and places_mod.terrain_of(scene.at or "") != places_mod.URBAN:
            continue
        seen = [scene.people[r] for r in rec.get("witnesses") or ()
                if r in scene.people and not scene.people[r].has_state(states.TRAVELS_WITH_YOU)
                and r != pc.ref]
        if not seen:
            continue
        kind = str(rec.get("crime") or "") or charge_of(rule, rec)
        if kind == "theft":
            seen = _noticed(engine, seen, _sleight_total(earlier))
            if not seen:
                # Palmed past every eye: nobody can swear to it, and the trial never will.
                _judge_all(pc, town, [_deed_key_of(pc, rec)], field="unnoticed")
                said.append("Nobody saw it done.")
                continue
        key = f"{rec.get('tag')}@{int(scene.clock_minutes)}@{rec.get('subject') or ''}"
        law_saw = [a for a in seen if _is_law(a)]
        grave = _charge_rows()[kind]["sentence"] == "death"
        standing = states.standing_with_the_law(pc, town)
        source = f"{CRIME_SOURCE}/{rec.get('tag')}/{key}"
        payload = {"crime": kind, "deed": str(rec.get("key") or "") or _deed_key_of(pc, rec),
                   "what": str(rec.get("what") or rec.get("subject_name") or "")}
        if law_saw or grave or standing in ("suspected", "wanted"):
            pc.apply_effect(ActiveEffect(
                name="a warrant", kind="situation", key=f"warrant:{key}", source=source,
                origin=source, duration="until-dismissed", tags=(states.wanted_tag(town),),
                payload=payload))
            # The sentence rides its effect as `told`: the report's tell is appended to the
            # act's own (`Engine.run`), and the planned narrator's declared-fight slot tells
            # it as its own fact after the squaring-up (gm/planned.py `build_plan`) — read
            # off the record, never cut out of the joined tell's English.
            line = (f"Seen by {_names(law_saw)}: there will be a warrant for "
                    f"{_charge_rows()[kind]['said']}." if law_saw else
                    "The watch will have a warrant out for it by morning.")
            effects.append({"kind": "wanted", "town": town, "charge": kind,
                            "origin": source, "told": line})
            said.append(line)
        else:
            pc.apply_effect(ActiveEffect(
                name="a name on the watch's lips", kind="situation", key=f"report:{key}",
                source=source, origin=source, duration="until-dismissed",
                tags=(states.suspected_tag(town),), payload=payload))
            line = "It was seen: somebody will be telling the watch."
            effects.append({"kind": "reported", "town": town, "charge": kind,
                            "origin": source, "told": line})
            said.append(line)
    if not effects and not said:
        return None
    return Outcome(intent_id="", op="report", effects=effects,
                   tell=" ".join(dict.fromkeys(said)))


def _eyes(scene, pc, victim_ref: str) -> list[str]:
    """Who is here to see it: conscious people who are not the player, the victim or the
    player's own company — and nobody, when the player is hidden."""
    if pc.has_state("state.hidden"):
        return []
    out = []
    for ref, a in scene.actors.items():
        if a.is_pc or ref == victim_ref or a.has_state(states.TRAVELS_WITH_YOU):
            continue
        try:
            awake = scene.conscious(ref)
        except Exception:       # noqa: BLE001
            awake = not a.is_down
        if awake:
            out.append(ref)
    return out


DOWNED_FOR = DAY     # how long a downed foe's later death is laid at the player's door


def watch(engine, intent, outcome, before_: dict | None, found: list[dict]) -> list[dict]:
    """The killings the deeds record does not hold, seen by the watch's own eyes (the
    owner's ruling of 2026-11-01: "be sure that letting someone bleedout or killing someone
    who attacked you durring combat are not murder and instead manslaughter or assault").

    The deeds record keeps no row for fighting back — "fighting back is not a deed at all"
    (rules/deeds.py, Ultima IV's who-attacked-first) — so before this a guard could watch
    the player kill a man who had come at them and the law had nothing to say. Now:

    * an attacker (hostile when the act began) the player's own act kills outright is
      manslaughter, recorded at once;
    * an attacker the player's own act drops dying is remembered for a day, and a death
      after that is manslaughter — left to bleed out;
    * a captive killed after the fight is the deeds' `deed.kill.captive` (murder), and a
      victim who had not raised a hand is the deeds' `deed.kill.unprovoked`, so neither is
      counted here twice.

    Returns incident records for `report`, each carrying its town, key and charge. Never
    raises into the turn."""
    try:
        return _watch(engine, intent, outcome, before_, found)
    except Exception:       # noqa: BLE001 - the law's bookkeeping never costs the turn
        import logging

        logging.getLogger(__name__).exception("trial.watch failed")
        return []


def _watch(engine, intent, outcome, before_, found) -> list[dict]:
    from . import deeds as deeds_mod
    from . import places as places_mod

    scene = engine.scene
    pc = scene.pc()
    if pc is None:
        return []
    crime = str(document()["self_defence"]["charge"])
    killed = {str(r.get("subject")) for r in deeds_mod.of(pc, "deed.kill")}
    killed |= {str(r.get("subject")) for r in found or ()
               if str(r.get("tag") or "").startswith("deed.kill")}
    now = int(scene.clock_minutes or 0)
    town = town_here(engine)
    out: list[dict] = []

    def incident(ref: str, name: str, witnesses: list, where_town: str, how: str) -> dict:
        key = f"incident.{how}@{now}@{ref}"
        inc = {"key": key, "crime": crime, "subject": ref, "subject_name": name,
               "witnesses": list(witnesses), "minute": now, "how": how}
        pay = _record_pay(pc, where_town)
        pay["incidents"] = list(pay.get("incidents") or ()) + [inc]
        _write_record(pc, where_town, pay)
        return dict(inc, kind="incident", town=where_town, tag=f"incident.{how}")

    mine = before_ is not None and getattr(intent, "actor", None) == pc.ref \
        and getattr(outcome, "status", "resolved") == "resolved"
    urban = places_mod.terrain_of(scene.at or "") == places_mod.URBAN
    if mine and urban:
        who = before_.get("who") or {}
        for e in outcome.effects or ():
            if not (isinstance(e, dict) and e.get("kind") == "condition"):
                continue
            ref = str(e.get("ref") or "")
            b = who.get(ref)
            if not b or not b["hostile"] or not b["sapient"] or b["dead"] or b["party"]:
                continue
            if ref in killed:
                continue
            a = scene.people.get(ref)
            name = getattr(a, "name", "") if a is not None else ""
            if e.get("condition") == "dead":
                # A captive finished after the fight is the deeds' murder; mid-fight, the
                # same blow is the fight (deeds `_deaths`).
                if b["helpless"] and not before_.get("fight"):
                    continue
                out.append(incident(ref, name, _eyes(scene, pc, ref), town, "defence"))
                killed.add(ref)
            elif e.get("condition") == "dying" and not b["dying"]:
                pay = _record_pay(pc, town)
                pay["downed"] = [d for d in pay.get("downed") or () if d.get("ref") != ref] \
                    + [{"ref": ref, "name": name, "minute": now,
                        "witnesses": _eyes(scene, pc, ref)}]
                _write_record(pc, town, pay)
    # The downed foes of every town the player has a record in: dead since, by bleeding or
    # another hand, and not already somebody's deed.
    for e in list(pc.effects):
        if e.source != RECORD_SOURCE:
            continue
        rtown = str((e.payload or {}).get("town") or "")
        pay = dict(e.payload or {})
        downed, kept = list(pay.get("downed") or ()), []
        for d in downed:
            a = scene.people.get(str(d.get("ref")))
            if a is not None and a.has_state("state.down.dead") and d["ref"] not in killed:
                out.append(incident(d["ref"], d.get("name", ""), d.get("witnesses") or [],
                                    rtown, "bled-out"))
                killed.add(d["ref"])
            elif a is not None and a.has_state("state.down.dying") \
                    and now - int(d.get("minute") or 0) <= DOWNED_FOR:
                kept.append(d)
        if kept != downed:
            pay = _record_pay(pc, rtown)
            pay["downed"] = kept
            _write_record(pc, rtown, pay)
    return out


def _deed_key_of(pc, rec: dict) -> str:
    """The key of the deeds row this record was written as: the newest row of its tag and
    subject (the record is returned by the one writer as it appends)."""
    from . import deeds as deeds_mod

    rows = [r for r in deeds_mod.of(pc, str(rec.get("tag") or ""))
            if (r.get("subject") or None) == (rec.get("subject") or None)]
    return deed_key(rows[-1]) if rows else ""
