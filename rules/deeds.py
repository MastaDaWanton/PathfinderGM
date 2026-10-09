"""Deeds: the good and the bad the player character does, kept as one signed number.

The owner, 2026-10-08 (docs/leatherworking-questions.md, plan open point 11): "Build out a
deeds system that tracks good or bad things you do, most actions should only have a small
impact, otherwise people will not mean to do certain things and it goes from a funny
accident to a source of frustration very quickly if they are punished too heavily. for now
just track this as a number positive for good deed and -negative for bad deeds. you should
be able to look at this number in your sheet but i dont want it to affect anything yet."

The design is docs/deeds-plan.md; the research under it, and its critic pass,
docs/deeds-prior-art.md (cited **PA §n**). The owner's answers to the plan's open points
(2026-10-08, the end of docs/leatherworking-questions.md) override it where they differ.

**Which "deed" this is.** The moral record. Two other things in the code are called deeds
and are not this: a crafting level's milestones (`rules/worldclass.py`, `Track.deeds`) and
the still acts the narrator owes the page (`gm/agent.py` `_deeds_owed`,
`gm/deed_reader.py`). Neither reads or writes this module.

**The store.** `Actor.deeds`, a plain append-only list of rows on the player's sheet, and
this module the one writer (`record`). The total is DERIVED — `total(actor)` is the sum of
the rows — never stored beside them, because a running total next to the list is a second
store that can drift (law 2's "no parallel stores"). A deed changes no number in play and
grants no state, so it is a record, like `xp`, and not an `ActiveEffect`: one effect per
deed would be walked by every modifier question on every roll to contribute nothing, and
one effect holding the score has no history to show (plan §4.2). When a later system makes
deeds matter it reads `of`/`total` and grants an `ActiveEffect` through the applicator —
a renown tag, a `knows.*` tag on a witness — and never adds the total to a roll.

**Nothing reads it yet.** Not a price, not a person, not a roll, not the narrator (the
owner's answer 4: "the narrator describes the act, never a verdict"). The deed rides on the
outcome of the act as a `{"kind": "deed"}` record the history line reads; the act's own tell
is unchanged, and no file under gm/ names this module. `tests/test_deeds.py` holds both
lines as an allowlist: ME2's Charm options, KOTOR's mastery and Wrath's paladin drift all
failed because something read the meter (PA §7, §8, §11).

**No model authors a deed.** Every value is a row of content/rules/deeds.json, validated on
load and fenced to -5..+5; there is no `deed` op, and `record` refuses a tag with no row.

**Detection is structural** (plan §5): `read`, called once per resolved outcome from
`Engine._drive` — the one place that sees the intent and the outcome together, as
`_settle_gate` does — classifies the outcome's own effect records against a snapshot of
who everybody was before the act (`before`), taken on first entry and carried through a
suspension for the player's d20. Never prose. The harvest is the one direct door
(`of_carcass` + `record`, lane C), because the deed there turns on the carcass.
"""
from __future__ import annotations

import functools
import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

DAY = 24 * 60
# A deed is a small number (the owner's ruling; Ultima IV ran a whole moral system on 1 to
# 5 out of 99, PA §5; RDR2 shrank petty acts to -1, PA §6).
FENCE = 5
GATES = ("subject-day", "day", "none")
HOWS = ("meant", "careless", "accident")
PAGE = 20
# The words for "how" a harm or a death was done, in the tags: a meant harm of somebody
# who was not hostile is unprovoked.
_TAG_HOW = {"meant": "unprovoked", "careless": "careless", "accident": "accident"}
_GRAVITY = {"accident": 0, "careless": 1, "meant": 2}
_PLACEHOLDER = re.compile(r"\{(\w*)\}")


# --- the rule document ------------------------------------------------------------------


def _path() -> Path:
    from django.conf import settings

    # BASE_DIR, never this file's own location: `__file__` points inside the PyInstaller
    # bundle once frozen (CLAUDE.md); the settings know where the content was installed.
    return Path(settings.BASE_DIR) / "content" / "rules" / "deeds.json"


@functools.cache
def document() -> dict:
    """content/rules/deeds.json, validated. A document that fails is refused whole, with
    every problem and its fix named, rather than half-loaded."""
    doc = json.loads(_path().read_text(encoding="utf-8"))
    problems = validate(doc)
    if problems:
        raise ValueError("content/rules/deeds.json is refused:\n  " + "\n  ".join(problems))
    return doc


def validate(doc: dict) -> list[str]:
    """Every problem with a deeds document, each with its fix named (the classbuilder's
    style). Empty when the document may be loaded."""
    problems: list[str] = []
    rows = doc.get("deeds") if isinstance(doc, dict) else None
    if not isinstance(rows, dict) or not rows:
        return ["deeds: give the catalogue as {\"deed.<kind>\": {row}, ...}; it is empty."]
    for tag, row in rows.items():
        where = f"deeds.{tag}"
        if not re.fullmatch(r"deed(\.[a-z0-9-]+)+", str(tag)):
            problems.append(f"{where}: a deed's tag lives under `deed.` in lower case "
                            f"(one vocabulary, law 1) — write 'deed.<kind>', e.g. "
                            f"'deed.theft'.")
        if not isinstance(row, dict):
            problems.append(f"{where}: a row is an object with value, gate, said and "
                            f"source.")
            continue
        value = row.get("value")
        if isinstance(value, bool) or not isinstance(value, int):
            problems.append(f"{where}.value: write a whole number from -{FENCE} to "
                            f"+{FENCE}; got {value!r}.")
        elif not -FENCE <= value <= FENCE:
            problems.append(f"{where}.value: {value} is outside -{FENCE}..+{FENCE}. A deed "
                            f"is a small number; a quest-sized value belongs to a quest, "
                            f"not here (docs/deeds-prior-art.md §2: Fallout 3's +50 for a "
                            f"bottle of water erased ten thefts).")
        if row.get("gate") not in GATES:
            problems.append(f"{where}.gate: say how often it counts: "
                            f"{', '.join(GATES)}; got {row.get('gate')!r}.")
        for key in ("said", "source"):
            if not str(row.get(key) or "").strip():
                problems.append(f"{where}.{key}: "
                                + ("write the history line, e.g. 'Took {what} from "
                                   "{subject} without asking'." if key == "said" else
                                   "say where the number comes from (the book, a "
                                   "tradition, the owner's ruling)."))
        for key in ("said", "said_plain"):
            for name in _PLACEHOLDER.findall(str(row.get(key) or "")):
                if name not in ("subject", "what"):
                    problems.append(f"{where}.{key}: {{{name}}} is not a blank the record "
                                    f"fills; use {{subject}} or {{what}}.")
    bands = doc.get("bands")
    if not isinstance(bands, list) or not bands:
        problems.append("bands: give the words, lowest first, as [{\"word\", \"from\", "
                        "\"to\"}]; the first has no `from` and the last no `to`.")
        return problems
    seen: set[str] = set()
    for i, b in enumerate(bands):
        where = f"bands[{i}]"
        word = str((b or {}).get("word") or "").strip()
        if not word:
            problems.append(f"{where}: give the band a word.")
        elif word.lower() in seen:
            problems.append(f"{where}: {word!r} is used twice; each band has its own word.")
        seen.add(word.lower())
        lo, hi = (b or {}).get("from"), (b or {}).get("to")
        if (i == 0) != (lo is None):
            problems.append(f"{where}.from: only the lowest band is open below; "
                            + ("drop `from`." if i == 0 else "give where it starts."))
        if (i == len(bands) - 1) != (hi is None):
            problems.append(f"{where}.to: only the highest band is open above; "
                            + ("drop `to`." if i == len(bands) - 1 else "give where it ends."))
        if lo is not None and hi is not None and lo > hi:
            problems.append(f"{where}: starts at {lo} after it ends at {hi}.")
        if i and lo is not None and (bands[i - 1] or {}).get("to") is not None \
                and lo != bands[i - 1]["to"] + 1:
            problems.append(f"{where}.from: {lo} leaves a gap or an overlap after "
                            f"{bands[i - 1]['to']}; start it at {bands[i - 1]['to'] + 1}.")
    return problems


def rows() -> dict[str, dict]:
    return document()["deeds"]


def bands() -> list[dict]:
    return document()["bands"]


def word_for(total_: int) -> str:
    """The word for a total, from the document's bands (presentation, tuned after play)."""
    for b in bands():
        lo, hi = b.get("from"), b.get("to")
        if (lo is None or total_ >= lo) and (hi is None or total_ <= hi):
            return str(b["word"])
    return ""


# --- the ledger -------------------------------------------------------------------------


def of(actor, prefix: str = "deed") -> list[dict]:
    """The rows under a tag prefix, asked as a prefix question (law 1):
    `of(pc, "deed.kill")`. A trailing dot is forgiven."""
    from . import states

    q = str(prefix or "deed").rstrip(".")
    return [r for r in getattr(actor, "deeds", None) or ()
            if states.matches(str(r.get("tag") or ""), q)]


def total(actor) -> int:
    """The number on the sheet: the sum of the rows, and nothing else."""
    return sum(int(r.get("value") or 0) for r in getattr(actor, "deeds", None) or ())


def day_of(minute: int) -> int:
    """The game day a clock minute falls on, as the journal counts them (day 1 first)."""
    return int(minute or 0) // DAY + 1


def _the(name: str) -> str:
    """"merchant" -> "the merchant"; a name, or a phrase with its own article, as it is.
    The journal's rule (play/history.py `_the`), so the two read alike."""
    name = " ".join(str(name or "").split())
    if name and name[:1].islower() and not re.match(r"(?:the|a|an|some|you)\b", name):
        return f"the {name}"
    return name


def said_of(row: dict) -> str:
    """The history line for a row, from its rule's template, rendered now."""
    rule = rows().get(str(row.get("tag") or ""))
    if rule is None:
        return "Did something the deeds catalogue no longer names"
    what = " ".join(str(row.get("what") or "").split())
    template = rule["said"] if what or not rule.get("said_plain") else rule["said_plain"]
    subject = _the(row.get("subject_name") or "") or "somebody"
    return template.replace("{subject}", subject).replace("{what}", what or "something")


def _gated(actor, tag: str, gate: str, subject, minute: int) -> bool:
    """Whether the day's gate (plan §8.2) makes this a repeat: one counted deed per tag per
    person per game day ("subject-day"), per tag per day ("day"), or none.

    Bad acts are gated too, unlike Ultima IV (PA §5): ten snatches at one stall in a
    minute are one theft for the counter's purposes, which keeps a bit of business at a
    stall from becoming a catastrophe. The repeat is still written, at 0, so the list
    stays honest and the player sees "again, the same day"."""
    if gate == "none":
        return False
    day = day_of(minute)
    for r in getattr(actor, "deeds", None) or ():
        if r.get("tag") != tag or day_of(int(r.get("minute") or 0)) != day:
            continue
        if gate == "day" or not subject or r.get("subject") == subject:
            return True
    return False


def _witnesses(scene, actor, subject, unseen: bool) -> list[str]:
    """Who saw it (plan §5.4): the conscious people here who are not the player,
    companions included — the set `_op_break_in` already treats as "it is seen". The
    subject only while conscious and only when the harm was seen; a hidden player is seen
    by nobody but a subject who perceived them. Recorded for renown and read by nothing:
    the same theft seen and unseen has the same value (KCD's hidden witness rule reads as
    a bug to its players, PA §10)."""
    if scene is None:
        return []
    hidden = bool(hasattr(actor, "has_state") and actor.has_state("state.hidden"))
    out: list[str] = []
    for ref, a in (getattr(scene, "actors", None) or {}).items():
        if ref == getattr(actor, "ref", None) or getattr(a, "is_pc", False):
            continue
        try:
            awake = scene.conscious(ref)
        except Exception:
            awake = not getattr(a, "is_down", False)
        if not awake:
            continue
        if ref == subject:
            if not unseen:
                out.append(ref)
        elif not hidden:
            out.append(ref)
    return out


def _place_name(place: str, scene) -> str:
    if not place:
        return ""
    try:
        from . import population

        return population._place_name(place, scene) or ""
    except Exception:
        return ""


def record(actor, tag: str, *, scene=None, minute: int | None = None,
           place: str | None = None, place_name: str | None = None,
           subject: str | None = None, subject_name: str = "", what: str = "",
           how: str = "meant", witnesses: list[str] | None = None,
           unseen: bool = False) -> dict:
    """Write one deed: the ONE writer of `Actor.deeds`. Returns the `deed` effect record
    the outcome of the act carries, for the history line and the turn log.

    The value is the rule row's at this moment (a row retuned later does not rewrite
    history, as XP awarded is not taken back), or 0 when the day's gate makes it a repeat.
    With `scene` given, the minute, the place and the witnesses are read from it; the
    contracts' keywords (`minute`, `place`, `subject`, `witnesses`) still win when passed.

    Lane C's harvest calls this once per carcass, never once per part:
        deeds.record(actor, tag, scene=scene, subject=creature.ref,
                     subject_name=creature.name, what="", how="meant")
    Refuses a tag with no rule row: no caller, and no model, chooses a deed's number."""
    rule = rows().get(str(tag or ""))
    if rule is None:
        raise ValueError(f"no deed row called {tag!r} in content/rules/deeds.json: a "
                         f"deed's value is the row's, never the caller's. The rows are: "
                         f"{', '.join(sorted(rows()))}.")
    if how not in HOWS:
        raise ValueError(f"how={how!r}: a deed is {', '.join(HOWS)}.")
    if minute is None:
        minute = int(getattr(scene, "clock_minutes", 0) or 0) if scene is not None else 0
    if place is None:
        place = str(getattr(scene, "at", "") or "") if scene is not None else ""
    if place_name is None:
        place_name = _place_name(place, scene)
    if witnesses is None:
        witnesses = _witnesses(scene, actor, subject, unseen)
    again = _gated(actor, tag, str(rule.get("gate") or "subject-day"), subject, int(minute))
    row = {
        "tag": tag,
        "value": 0 if again else int(rule["value"]),
        "again": again,
        "how": how,
        "minute": int(minute),
        "place": place,
        "place_name": str(place_name or ""),
        "subject": subject,
        # Said at the time: refs never reach the page (ruling 2026-09-28), and the person
        # may have left the scene, or the world, by the time the sheet is read.
        "subject_name": " ".join(str(subject_name or "").split()),
        "what": " ".join(str(what or "").split()),
        "witnesses": list(witnesses),
        "origin": f"rule:deeds/{tag}",
    }
    actor.deeds.append(row)
    # No `ref`, `item`, `to` or `from` on the record: gm/ledger.py names an outcome by
    # the first effect carrying one of those, and a deed riding on a break-in (whose own
    # record has none) would have become what the memory ledger says the outcome was
    # about. The narrator is not told deeds (the owner's answer 4).
    return {"kind": "deed", "tag": tag, "value": row["value"], "again": again, "how": how,
            "subject": subject, "subject_name": row["subject_name"], "what": row["what"],
            "said": said_of(row), "total": total(actor), "origin": row["origin"]}


# --- the carcass (lane C's door) --------------------------------------------------------


def of_carcass(creature) -> str | None:
    """Which deed taking parts from this body is, or None.

    "deed.harvest.good-outsider" for a `type.outsider` with `subtype.good` or a printed
    good alignment (the owner's answer 3: either; 58 blocks); "deed.harvest.good-dragon"
    for a `type.dragon` whose block prints a good alignment, "by its kind" (open point 12;
    9 blocks — no metallic true dragon ships). Tags and the printed field only, never the
    name: a renamed archon still writes the deed. Takes an Actor or a stat block.

    Never the gate: whether the harvest is offered at all is `never_harvested` (humanoids
    and the native outsiders, the owner's answer 3b), which lane C asks first."""
    from . import bestiary

    if bestiary.body_is(creature, "type.outsider") and (
            bestiary.body_is(creature, "subtype.good") or bestiary.printed_good(creature)):
        return "deed.harvest.good-outsider"
    if bestiary.body_is(creature, "type.dragon") and bestiary.printed_good(creature):
        return "deed.harvest.good-dragon"
    return None


def never_harvested(creature) -> bool:
    """Whether no part of this body is ever offered: a people's, not a carcass.
    `bestiary.never_harvested` is the rule; this is its name where lane C looks for the
    deed beside it."""
    from . import bestiary

    return bestiary.never_harvested(creature)


# --- who everybody was before the act ---------------------------------------------------


def watches(engine, intent) -> bool:
    """Whether this intent is the player character's own act (Fallout 2 counts only
    `source_obj == dude_obj`, PA §1): a companion's acts are theirs."""
    pc = engine.scene.pc()
    return pc is not None and (getattr(intent, "actor", None) or pc.ref) == pc.ref


def _sapient(a) -> bool:
    """Int 3 or more: 1e's animal intelligence is 1-2. Measured 2026-10-08: 239 of 263
    animals are under 3 and 3,749 of 3,756 humanoids 3 or more. A sheet with no Int at all
    is a mindless block ("—", an ooze, a skeleton) when it was made from one, and a person
    of the world when it was not."""
    score = (getattr(a, "abilities", None) or {}).get("int")
    if score in (None, ""):
        doc = a._creature_doc() if hasattr(a, "_creature_doc") else None
        return not doc
    try:
        return int(score) >= 3
    except (TypeError, ValueError):
        return False


def before(engine) -> dict:
    """Who everybody here was before the act: the facts a deed turns on that the act
    itself changes. A first blow makes its victim hostile (`_foes_settle`), a death leaves
    no attitude, a cure lifts dying — so the reader asks this, taken on the intent's first
    entry and kept through a suspension for the player's d20 (`partial["deeds_before"]`,
    the pattern `attack_state["seen"]` uses). JSON-safe, since a suspension is saved."""
    from . import attitude, population, states

    scene = engine.scene
    pc = scene.pc()
    fight = bool(getattr(scene, "in_encounter", False))
    sides = (getattr(scene, "sides", None) or {}) if fight else {}
    mine = next((s for s, refs in sides.items() if pc is not None and pc.ref in refs), None)
    foes = {r for s, refs in sides.items() if s != mine for r in refs}
    lives = {str(rec.get("ref")): rec for rec in
             (getattr(scene, "population", None) or {}).values()
             if isinstance(rec, dict) and rec.get("ref")}
    who: dict[str, dict] = {}
    for ref, a in (getattr(scene, "actors", None) or {}).items():
        if pc is not None and ref == pc.ref:
            continue
        tags = ((lives.get(ref) or {}).get("life") or {}).get("tags") or ()
        who[ref] = {
            "hostile": attitude.of(a) == attitude.HOSTILE or ref in foes,
            "helpless": bool(a.is_helpless),
            "dying": a.has_state("state.down.dying"),
            "dead": a.has_state("state.down.dead"),
            "hurt": a.hp < a.hp_max or int(getattr(a, "nonlethal", 0) or 0) > 0,
            "party": a.has_state(states.TRAVELS_WITH_YOU),
            "sapient": _sapient(a),
            "poor": "poor" in tags,
        }
    return {"fight": fight, "who": who}


# --- the reader -------------------------------------------------------------------------


def read(engine, intent, outcome, before_: dict | None) -> list[dict]:
    """The deeds one resolved outcome holds, recorded; their `deed` records returned for
    the outcome to carry. `before_` is `before(engine)` for the player's own act and None
    for anybody else's — whose outcome is still read for a death the player's earlier
    blow caused (§5.2). Never raises into the turn: a deed is presentation for now, and a
    reader fault must not cost the player their action, so it is logged and skipped."""
    try:
        scene = engine.scene
        pc = scene.pc()
        if pc is None:
            return []
        out: list[dict] = []
        if before_ is not None and getattr(outcome, "status", "resolved") == "resolved":
            out += _acts(engine, pc, intent, outcome, before_)
        out += _deaths(engine, pc, intent, outcome, before_)
        return out
    except Exception:                                   # pragma: no cover - logged
        log.exception("deeds.read failed on %s", getattr(outcome, "op", "?"))
        return []


def _recorder(engine, pc, out: list):
    scene = engine.scene
    try:
        here = engine._place_name(scene.at) if getattr(scene, "at", None) else ""
    except Exception:
        here = ""

    def rec(tag, subject, *, how="meant", what="", unseen=False, name=None):
        a = (getattr(scene, "people", None) or {}).get(subject) if subject else None
        out.append(record(pc, tag, scene=scene, place_name=here, subject=subject,
                          subject_name=name if name is not None else
                          (getattr(a, "name", "") if a is not None else ""),
                          what=what, how=how, unseen=unseen))
    return rec


def _thing(e: dict) -> str:
    """What a give record moved, as words: "5 gp", "a coin purse"."""
    item = re.sub(r"#\d+$", "", str(e.get("item") or "")).replace("_", " ").strip()
    n = int(e.get("count") or 1)
    if item == "coin":
        return "some coin"
    return f"{n} {item}" if n != 1 else item


def _acts(engine, pc, intent, outcome, before_: dict) -> list[dict]:
    from . import goods, spells

    scene = engine.scene
    who = before_.get("who") or {}
    fx = [e for e in (outcome.effects or []) if isinstance(e, dict)]
    mine = getattr(intent, "actor", None) == pc.ref
    targets = [t for t in intent.targets() if t]
    out: list[dict] = []
    rec = _recorder(engine, pc, out)

    # Harm (plan §7.1). Who the act hurt, from the act's own records: the battle gate's
    # first violence, the harm door's attitude record (written only when the player is
    # the one who harmed, `attitude.harmed`), harm nobody saw the source of, and — for the
    # player's own intent — damage that came off hit points.
    harmed: dict[str, bool] = {}
    opened: set[str] = set()
    for e in fx:
        k, ref = e.get("kind"), str(e.get("ref") or "")
        if k == "battle_joined" and e.get("ref") == pc.ref and e.get("target"):
            opened.add(str(e["target"]))
            harmed.setdefault(str(e["target"]), False)
        elif k == "attitude" and e.get("why") == "harmed" and ref:
            harmed.setdefault(ref, False)
        elif k == "harm_unseen" and e.get("by") == pc.ref and ref:
            harmed[ref] = True
        elif mine and k == "damage":
            for d in [e] + [x for x in e.get("also") or () if isinstance(x, dict)]:
                if int(d.get("amount") or 0) > 0 and d.get("ref"):
                    harmed.setdefault(str(d["ref"]), False)

    def how_of(ref: str) -> str:
        if ref in opened:
            return "meant"
        if getattr(outcome, "mode", "") == "splash" and ref not in targets:
            return "accident"            # the flask's spill, or a missed throw's scatter
        if not targets or ref in targets:
            return "meant"               # the one aimed at, or the spot the player chose
        return "careless"                # caught by an area aimed at somebody else

    for ref, unseen in harmed.items():
        b = who.get(ref)
        # Fighting back is not a deed at all (Ultima IV's "who attacked first", PA §5),
        # nor is harm to a beast, nor a blow at a corpse.
        if ref == pc.ref or not b or b["dead"] or b["hostile"] or not b["sapient"]:
            continue
        how = how_of(ref)
        rec(f"deed.violence.{_TAG_HOW[how]}", ref, how=how, unseen=unseen)

    coins = {c for c, _ in goods.DENOMINATIONS} | {"coin"}
    for e in fx:
        k = e.get("kind")
        # Theft: taken without consent from somebody who was not hostile. Not scaled by
        # value — a fork and a fortune are both a theft. Robbing a hostile in a fight, or
        # a corpse, is not theft here (plan §7.1).
        victim, what = None, ""
        if k == "give" and e.get("how") == "took_from" and e.get("to") == pc.ref:
            victim, what = str(e.get("from") or ""), _thing(e)
        elif k == "stolen" and e.get("ref") == pc.ref:
            victim, what = str(e.get("from") or ""), str(e.get("item") or "")
        elif k == "took" and outcome.op == "loot" and e.get("ref") == pc.ref:
            victim, what = str(e.get("from") or ""), "everything they carried"
        if victim:
            b = who.get(victim)
            if b and not b["hostile"] and not b["dead"]:
                rec("deed.theft", victim, what=what)
            continue
        # Trespass: a home's door opened by breaking in.
        if k == "break_in" and e.get("opened") and mine:
            house = str(e.get("house") or "")
            try:
                name = engine._place_name(house)
            except Exception:
                name = ""
            rec("deed.trespass", house, name=name or "a house")
            continue
        # A spell with the [evil] or [good] descriptor (the owner's answer 2).
        if k == "cast" and e.get("ref") == pc.ref and e.get("spell"):
            try:
                sp = spells.get(str(e["spell"]))
            except KeyError:
                continue
            words = {str(d).strip().lower() for d in sp.descriptors or ()}
            for word in ("evil", "good"):
                if word in words:
                    rec(f"deed.spell.{word}", None, what=sp.name, name="")
            continue
        # A gift: given back to its owner, or coin to somebody who has little.
        if k == "give" and e.get("how") == "handed" and e.get("from") == pc.ref:
            taker = str(e.get("to") or "")
            b = who.get(taker)
            if not b:
                continue
            prop = scene.prop_named(str(e.get("item") or ""))
            if prop and prop.get("stolen") and prop.get("owner") == taker \
                    and prop.get("held_by") == taker:
                rec("deed.restitution", taker, what=_thing(e))
            elif str(e.get("item") or "") in coins and b["poor"] \
                    and not (intent.params or {}).get("price"):
                rec("deed.charity.alms", taker, what=_thing(e))

    if not mine:
        return out
    # Mercy (plan §7.2): only the player's own hands.
    people = getattr(scene, "people", None) or {}
    saved: set[str] = set()
    for e in fx:
        k, ref = e.get("kind"), str(e.get("ref") or "")
        b = who.get(ref)
        if not b or b["party"] or not b["dying"] or ref in saved:
            continue
        if k == "heal" or (k == "condition" and e.get("condition") == "stable"):
            a = people.get(ref)
            if a is not None and not a.has_state("state.down.dying") \
                    and not a.has_state("state.down.dead"):
                saved.add(ref)
                rec("deed.mercy.saved", ref)        # foe or not: sparing counts
    tended: set[str] = set()
    for e in fx:
        ref = str(e.get("ref") or "")
        b = who.get(ref)
        if e.get("kind") != "heal" or int(e.get("amount") or 0) <= 0 or not b \
                or ref in saved or ref in tended:
            continue
        if b["hurt"] and not b["hostile"] and not b["party"] and not b["dead"]:
            tended.add(ref)
            rec("deed.mercy.tended", ref)
    pulled = {str(e.get("ref")) for e in fx if e.get("kind") == "damage"
              and e.get("lethality") == "nonlethal"}
    knocked = [str(e.get("ref")) for e in fx if e.get("kind") == "condition"
               and e.get("condition") == "unconscious"]
    for ref in dict.fromkeys(knocked):
        b = who.get(ref)
        a = people.get(ref)
        if ref not in pulled or not b or not b["hostile"] or not b["sapient"] \
                or b["dead"] or b["dying"] or a is None:
            continue
        if not a.has_state("state.down.dead") and not a.has_state("state.down.dying"):
            rec("deed.mercy.subdued", ref)
    return out


def _killed(pc, ref: str) -> bool:
    return any(r.get("subject") == ref for r in of(pc, "deed.kill"))


def _deaths(engine, pc, intent, outcome, before_: dict | None) -> list[dict]:
    """Deaths, from the ledger's memory (plan §5.2): a death of somebody the player's own
    violence row names within the last day is the matching kill, whoever's outcome or tick
    it came in — a merchant who bleeds out two rounds after the blow, or under a guard's
    sword in the fight the player started, is still the player's kill. The last
    twenty-four hours rather than the calendar day, so a blow at a quarter to midnight is
    not forgotten by a quarter past. One blow or ten weigh the same; kills are never
    gated, because the dead die once.

    And the captive (§7.1): a helpless, hostile, sapient creature the player kills
    outside a fight — the beaten bandit finished on the ground afterwards. The book's own
    example, one step toward evil (PA §11). The same blow mid-fight is tactics."""
    scene = engine.scene
    out: list[dict] = []
    rec = _recorder(engine, pc, out)
    now = int(getattr(scene, "clock_minutes", 0) or 0)
    struck: dict[str, str] = {}
    for r in of(pc, "deed.violence"):
        ref = r.get("subject")
        if ref and now - int(r.get("minute") or 0) <= DAY:
            how = str(r.get("how") or "meant")
            if ref not in struck or _GRAVITY.get(how, 0) > _GRAVITY.get(struck[ref], 0):
                struck[ref] = how
    if before_ is not None and getattr(intent, "actor", None) == pc.ref \
            and not before_.get("fight"):
        who = before_.get("who") or {}
        targets = [t for t in intent.targets() if t]
        for e in outcome.effects or ():
            if not (isinstance(e, dict) and e.get("kind") == "condition"
                    and e.get("condition") == "dead"):
                continue
            ref = str(e.get("ref") or "")
            b = who.get(ref)
            if (b and not b["dead"] and b["hostile"] and b["helpless"] and b["sapient"]
                    and (not targets or ref in targets)
                    and ref not in struck and not _killed(pc, ref)):
                rec("deed.kill.captive", ref)
    people = getattr(scene, "people", None) or {}
    for ref, how in struck.items():
        a = people.get(ref)
        if a is None or not a.has_state("state.down.dead") or _killed(pc, ref):
            continue
        rec(f"deed.kill.{_TAG_HOW[how]}", ref, how=how)
    return out


# --- the page ---------------------------------------------------------------------------


def _shown(row: dict, n: int) -> dict:
    """One row as the page shows it: no refs (the ruling "refs never on the page"); the
    day and the time of day as the journal and the sky say them."""
    from . import sky

    minute = int(row.get("minute") or 0)
    try:
        phase = sky.phase_at(minute)["phase"]
    except Exception:
        phase = ""
    return {"n": n, "day": day_of(minute), "phase": phase,
            "where": str(row.get("place_name") or ""), "said": said_of(row),
            "value": int(row.get("value") or 0), "again": bool(row.get("again")),
            "how": str(row.get("how") or "meant")}


def summary(actor, limit: int = PAGE) -> dict:
    """What the Sheet tab's Deeds card shows: the number, its word, the counts, the bands,
    and the newest rows (`full_sheet`'s "deeds")."""
    rows_ = list(getattr(actor, "deeds", None) or ())
    t = total(actor)
    shown = [_shown(r, i) for i, r in reversed(list(enumerate(rows_)))][:limit]
    return {
        "total": t, "word": word_for(t),
        "good": sum(1 for r in rows_ if int(r.get("value") or 0) > 0),
        "bad": sum(1 for r in rows_ if int(r.get("value") or 0) < 0),
        "again": sum(1 for r in rows_ if r.get("again")),
        "forgiven": sum(1 for r in rows_ if not r.get("again")
                        and int(r.get("value") or 0) == 0),
        "bands": [{"word": b["word"], "from": b.get("from"), "to": b.get("to")}
                  for b in bands()],
        "rows": shown, "more": len(rows_) > len(shown),
    }


def page(actor, before_n: int | None = None, limit: int = PAGE) -> dict:
    """Older rows for "Show all": those numbered below `before_n`, newest first."""
    rows_ = list(getattr(actor, "deeds", None) or ())
    end = len(rows_) if before_n is None else max(0, min(int(before_n), len(rows_)))
    idx = list(range(end - 1, -1, -1))
    take = idx[:max(1, int(limit))]
    return {"rows": [_shown(rows_[i], i) for i in take], "more": len(idx) > len(take)}
