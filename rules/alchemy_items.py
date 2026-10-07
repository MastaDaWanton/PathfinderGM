"""Alchemy products: the record a bottle keeps, and what it does when it is read
(docs/alchemy-contracts.md §6; docs/alchemy-revamp-plan.md §6, §11, §12).

**The record stores ids and grades, never computed numbers** (the forge's read-live rule,
forge contracts §4). Bottle writes which formula, which vessel, which traits (by the
materials they came from, their key and their grade), which drawbacks, the quality, the
alchemist's level and perks; `build(record)` turns that into the documents the engine
runs, every time it is read. So a corrected material document fixes every bottle made
from it on the next load, and no number on a shelf can drift from the rules that made it.

**Traits travel: Atelier's model** (plan §6, owner Q7.2). Every input's product traits
form a pool. Each distinct material contributes once whatever its count (count is batch
size, not strength). An intermediate brings its own traits as they are, grades and all
(Ryza: "Any traits you dump in at any level will be available at the end"). Traits with
the same name — type, target and route — merge and their grades add (Ryza: "Critical Lv 2
and a Critical Lv 5 will yield a Critical Lv 7"), capped at the Alchemist level. What a
grade means is a rule row, content/rules/alchemy-grades.json. Sophie's pairwise naming of
higher traits is not taken (plan §6.2): one merge rule is enough to learn.

**Slots: the player picks** (plan §6.3). A finished product carries at most its family's
slots in benefits (potion 3, oil, flask and cloud 2, tool 1); a formula's core takes one.
Drawbacks take no slot and are never optional: carry a benefit from a material and its
drawbacks come too (Morrowind's and Oblivion's rule), unless Filter stripped them. A trait
the family cannot deliver is shown dimmed with its reason and dropped, never silently
kept (herbalism's rule, plan §5.3). A finished good is a dead end: never an input.

**Quality** (plan §6.4, owner Q6.4): the quality ladder (content/rules/herbal-quality.json)
multiplies benefits by `potency` and `duration` and softens drawbacks by `drawback`; perks
and concentration multiply on top; Filter takes a tenth. A book core follows the same
columns, so a Sound alchemist's fire is the book's exactly and a Fine one is stronger; a
spell potion's quality is caster level instead (owner, open point 6: no second
multiplier). A splash's one point is the book's and is never scaled.

**Shop items are the same documents** (plan §12.5, owner Q8.3): `record_for_formula`
makes the record a bought alchemist's fire is, at Sound and with no traits, so lane H's
counter can write the same stock row a crafted one has.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .crafting import Stock

TRACK_ID = "alchemist"
# The record's shape version (plan §12.2): 4 is the revamp's. Anything older is OLD WORK,
# kept exactly as it is and never rebuilt (contracts §6).
SCHEMA = 4
# The build's own version, stamped on what it writes. Bumped when `build` changes what a
# record turns into; the loader rebuilds every record anyway and compares content.
BUILD_VERSION = 1
INTERMEDIATE = "intermediate"
SOUND = 1

_QUALITY_PREFIX_SKIP = ("Sound",)


# --- the rule rows ---------------------------------------------------------------------------

def bench() -> dict:
    """The alchemist track's `bench` block (content/world-classes/alchemist.json), through
    the track cache, so a homebrew track overrides its rules too."""
    from . import worldclass as wc

    try:
        return dict(wc.get(TRACK_ID).data.get("bench") or {})
    except KeyError:
        return {}


def _grades_path() -> Path:
    # Never `__file__`: it lies inside a frozen bundle (CLAUDE.md). BASE_DIR is the install.
    from django.conf import settings

    return Path(settings.BASE_DIR) / "content" / "rules" / "alchemy-grades.json"


_GRADES: dict = {}


def grades() -> dict:
    """content/rules/alchemy-grades.json, re-read when the file changes (content, not a
    stamp: the cache key is the file's bytes' digest)."""
    path = _grades_path()
    try:
        raw = path.read_bytes()
    except OSError:
        raw = b"{}"
    key = hashlib.md5(raw).hexdigest()
    if _GRADES.get("key") != key:
        _GRADES.clear()
        _GRADES.update({"key": key, "rows": json.loads(raw.decode("utf-8") or "{}")})
    return _GRADES["rows"]


def slots_for(family: str) -> int:
    return int((bench().get("slots") or {}).get(family, 0) or 0)


def family_row(family: str) -> dict:
    return dict((bench().get("families") or {}).get(family) or {})


def form_row(form: str) -> dict:
    return dict((bench().get("forms") or {}).get(form) or {})


def _routes(family: str, side: str) -> tuple[str, ...]:
    return tuple(((bench().get("routes") or {}).get(family) or {}).get(side) or ())


# --- a material's traits ---------------------------------------------------------------------

def doc_of(material_id: str) -> dict | None:
    """One document off the alchemy shelf (the one door, lane A)."""
    from . import materials

    return materials.alchemy_doc(str(material_id or ""))


def _norm(word) -> str:
    return str(word or "").strip().lower().replace(".", "_").replace(" ", "_") or "-"


def trait_key(spec: dict) -> str:
    """A trait's name (plan §6.2): its type, what it acts on, and its route. Two fire
    damages struck are one trait; fire damage struck and fire resistance drunk are two. A
    save gate is named by its save AND what it gates, so a Fortitude poison that sickens
    and one that eats Constitution never merge into one."""
    spec = spec or {}
    t = str(spec.get("type") or "")
    route = _norm(spec.get("route") or "ingest")
    if t in ("damage", "burning"):
        what = spec.get("damage_type") or "untyped"
    elif t == "save_gate":
        inner = [s for s in (spec.get("on_failure") or []) if isinstance(s, dict)]
        what = f"{spec.get('target') or ''}-" + (
            trait_key(dict(inner[0], route=route)).split(".")[1] if inner else "gate")
    elif t == "manifest":
        what = spec.get("terrain") or "obscuring"
    elif t == "permission":
        what = spec.get("tag") or spec.get("target")
    elif t == "light":
        what = "light"
    else:
        what = spec.get("target") or spec.get("damage_type") or ""
    return f"{t}.{_norm(what)}.{route}"


def _herb_folded(doc: dict) -> list[dict]:
    """A hybrid herb's effects with each loose save gate folded around the body it guards.

    The herb corpus writes a poison as a bare gate followed by its body (the herb bench
    links them by position, `knowledge.anatomy`); an alchemy trait is one document, so the
    gate becomes the body's `save_gate`. A gate that guards nothing (a restated DC) is not
    a trait at all and is left out."""
    from . import knowledge

    specs = [copy.deepcopy(s) for s in (doc.get("product") or []) if isinstance(s, dict)]
    keys = knowledge.property_keys(doc)
    try:
        gate_of = knowledge.anatomy(doc)["gate_of"]
    except Exception:  # noqa: BLE001 - a herb the reader cannot sort keeps its plain effects
        gate_of = {}
    by_key = dict(zip(keys, specs))
    gates = set(gate_of.values())
    out = []
    for k, spec in zip(keys, specs):
        if k in gates:
            continue
        if str(spec.get("type")) == "save_gate" and not spec.get("on_failure"):
            continue
        gate = by_key.get(gate_of.get(k, ""))
        if gate is not None:
            body = {x: v for x, v in spec.items() if x not in ("route", "essence", "grade")}
            spec = {"type": "save_gate", "target": gate.get("target"), "dc": gate.get("dc"),
                    "on_failure": [body], "route": spec.get("route") or gate.get("route"),
                    "essence": spec.get("essence") or gate.get("essence"),
                    "grade": spec.get("grade", 1)}
        out.append(spec)
    return out


def product_specs(material_id: str) -> list[dict]:
    """What a material puts in a bottle, as effect documents (copies), herb gates folded."""
    from . import materials

    doc = doc_of(material_id)
    if doc is None:
        return []
    if materials.is_herb_view(doc):
        return _herb_folded(doc)
    return [copy.deepcopy(s) for s in materials.product_traits(doc)]


def _is_drawback(spec: dict) -> bool:
    from . import knowledge

    return knowledge.is_drawback(spec)


def material_rows(material_id: str) -> list[dict]:
    """A material's traits as pool rows: {"key", "essence", "grade", "from", "drawback"}."""
    out = []
    for spec in product_specs(material_id):
        out.append({"key": trait_key(spec), "essence": str(spec.get("essence") or ""),
                    "grade": max(1, int(spec.get("grade") or 1)),
                    "from": [str(material_id)], "drawback": _is_drawback(spec)})
    return out


# --- the pool --------------------------------------------------------------------------------

def _merge_rows(rows: list[dict], cap: int) -> list[dict]:
    """Same-named rows merge: grades add (capped), sources join. Order: first seen."""
    out: dict[str, dict] = {}
    for r in rows:
        k = r["key"]
        if k not in out:
            out[k] = {"key": k, "essence": r.get("essence", ""), "raw": 0, "from": [],
                      "drawback": bool(r.get("drawback"))}
        m = out[k]
        m["raw"] += int(r.get("grade") or 1)
        m["essence"] = m["essence"] or r.get("essence", "")
        for src in r.get("from") or ():
            if src not in m["from"]:
                m["from"].append(src)
        for via in r.get("via") or ():
            m.setdefault("via", [])
            if via not in m["via"]:
                m["via"].append(via)
    for m in out.values():
        m["grade"] = max(1, min(int(cap), m["raw"])) if cap else m["raw"]
        m["capped"] = m["raw"] > m["grade"]
    return list(out.values())


def pool(sources, *, level: int, wild: str | None = None) -> dict:
    """The traits a step works with (plan §6.1).

    `sources`: [{"material": id} | {"record": record}], one per DISTINCT input (the caller
    folds counts). `wild` is the key prima materia copies, chosen by the player (plan §5.8:
    "it copies one product trait of another input ... at grade 1; it is never a trait of
    its own"). Returns {"traits": benefits, "drawbacks": [...], "materials": [ids],
    "capped": [rows whose grade the level held back]}."""
    rows: list[dict] = []
    mats: list[str] = []
    wild_from = ""
    for s in sources or ():
        if s.get("material"):
            mid = str(s["material"])
            if mid not in mats:
                mats.append(mid)
            if s.get("wild"):
                wild_from = mid
                continue
            rows += material_rows(mid)
        elif isinstance(s.get("record"), dict):
            rec = s["record"]
            for r in rec.get("traits") or ():
                rows.append(dict(r, drawback=False))
            for r in rec.get("drawbacks") or ():
                rows.append(dict(r, drawback=True))
            for mid in record_materials(rec):
                if mid not in mats:
                    mats.append(mid)
    if wild and wild_from:
        found = next((r for r in rows if r["key"] == wild and not r.get("drawback")), None)
        if found is not None:
            rows.append({"key": found["key"], "essence": found.get("essence", ""),
                         "grade": 1, "from": list(found["from"]), "via": [wild_from],
                         "drawback": False})
    cap = int(level or 1)
    ben = _merge_rows([r for r in rows if not r.get("drawback")], cap)
    bad = _merge_rows([r for r in rows if r.get("drawback")], cap)
    return {"traits": ben, "drawbacks": bad, "materials": mats,
            "capped": [r for r in ben + bad if r.get("capped")]}


def mix_of(p: dict) -> dict:
    """The pool as `formulae.match` reads it (contracts §5): the bench builds it, lane E
    only reads it."""
    def row(r):
        return {"key": r["key"], "essence": r.get("essence", ""), "grade": r["grade"],
                "from": list(r["from"])}

    return {"traits": [row(r) for r in p.get("traits") or ()],
            "drawbacks": [row(r) for r in p.get("drawbacks") or ()],
            "materials": list(p.get("materials") or ())}


def record_materials(record: dict) -> list[str]:
    out: list[str] = []
    for r in list(record.get("traits") or []) + list(record.get("drawbacks") or []):
        for m in list(r.get("from") or []) + list(r.get("via") or []):
            if m not in out:
                out.append(m)
    for m in record.get("materials") or ():
        if m not in out:
            out.append(m)
    return out


# --- one trait as a document -------------------------------------------------------------------

def _strength(spec: dict) -> float:
    from . import materials

    top = materials.dice_max(spec.get("dice")) if spec.get("dice") not in (None, "") else None
    if top is not None:
        return float(top)
    try:
        return abs(float(spec.get("amount")))
    except (TypeError, ValueError):
        pass
    for child in spec.get("on_failure") or ():
        if isinstance(child, dict):
            return _strength(child)
    try:
        return float(spec.get("dc") or 0) / 100.0
    except (TypeError, ValueError):
        return 0.0


_UNIT_MINUTES = {"round": 0.1, "minute": 1, "hour": 60, "day": 1440, "week": 10080}


def _dur_minutes(duration) -> float:
    from . import materials

    if not isinstance(duration, dict):
        return 0.0
    amount = duration.get("amount")
    try:
        n = float(amount)
    except (TypeError, ValueError):
        n = float(materials.dice_max(amount) or 0)
    return n * _UNIT_MINUTES.get(str(duration.get("unit") or "round"), 0.1)


def template(row: dict) -> dict | None:
    """The document a pool row stands for: the strongest source's (largest dice, else
    amount), with the longest duration among the merged sources unless it is a
    condition's, which the grade lengthens instead (alchemy-grades.json)."""
    found = []
    for mid in row.get("from") or ():
        for spec in product_specs(mid):
            if trait_key(spec) == row["key"]:
                found.append((mid, spec))
    if not found:
        return None
    mid, best = max(found, key=lambda ms: (_strength(ms[1]), -found.index(ms)))
    best = copy.deepcopy(best)
    if str(best.get("type")) != "apply_condition" and grades().get("bonus_duration") == "longest":
        longest = max((s.get("duration") for _, s in found if isinstance(s.get("duration"), dict)),
                      key=_dur_minutes, default=None)
        if longest is not None:
            best["duration"] = copy.deepcopy(longest)
    best["_source"] = mid
    return best


def _dice_times(dice, g: int) -> str:
    import re

    text = str(dice or "").replace(" ", "")
    m = re.fullmatch(r"(\d*)d(\d+)([+-]\d+)?", text)
    if m:
        count = int(m.group(1) or 1) * g
        flat = int(m.group(3) or 0) * g
        return f"{count}d{m.group(2)}" + (f"{flat:+d}" if flat else "")
    try:
        return str(int(text) * g)
    except ValueError:
        return str(dice)


def graded(spec: dict, grade: int) -> dict:
    """One document at a grade (content/rules/alchemy-grades.json): dice count and flat
    amounts times g, a save DC +2 a grade above 1, a condition's duration times g."""
    from .crafting import _SCALED_TYPES

    s = copy.deepcopy(spec)
    g = max(1, int(grade or 1))
    if g == 1:
        return s
    rules = grades()
    t = str(s.get("type") or "")
    if t in set(rules.get("unscaled_types") or ()):
        return s
    if s.get("dice") not in (None, "") and rules.get("dice", "count") == "count":
        s["dice"] = _dice_times(s["dice"], g)
    if t in _SCALED_TYPES and isinstance(s.get("amount"), (int, float)) \
            and not isinstance(s.get("amount"), bool) and rules.get("amount", "multiply"):
        s["amount"] = s["amount"] * g
    step = int(rules.get("save_dc_per_grade", 2) or 0)
    if t in ("save_gate", "burning") and isinstance(s.get("dc"), int):
        s["dc"] = int(s["dc"]) + step * (g - 1)
    if t == "apply_condition" and isinstance(s.get("duration"), dict) \
            and rules.get("condition_duration") == "multiply":
        d = dict(s["duration"])
        amt = d.get("amount")
        d["amount"] = amt * g if isinstance(amt, int) else _dice_times(amt, g)
        s["duration"] = d
    for branch in ("on_failure", "on_success"):
        if isinstance(s.get(branch), list):
            s[branch] = [graded(c, g) if isinstance(c, dict) else c for c in s[branch]]
    s["grade"] = g
    return s


def scaled(spec: dict, mult: float, dmult: float, up: bool) -> dict:
    """A document at a strength: dice and amounts by `mult`, durations by `dmult`, rounded
    the house way (benefits up, costs down: `crafting`'s rule). A splash's book point and a
    save's DC are never touched."""
    from .crafting import _SCALED_TYPES, _scale_amount, _scale_dice, _scale_duration

    s = copy.deepcopy(spec)
    if str(s.get("route") or "") == "splash":
        return s
    if s.get("dice") not in (None, ""):
        s["dice"] = _scale_dice(s["dice"], mult, up)
    if str(s.get("type") or "") in _SCALED_TYPES and s.get("amount") not in (None, ""):
        s["amount"] = _scale_amount(s["amount"], mult, up)
    if "duration" in s:
        s["duration"] = _scale_duration(s["duration"], dmult, up)
    for branch in ("on_failure", "on_success"):
        if isinstance(s.get(branch), list):
            s[branch] = [scaled(c, mult, dmult, up) if isinstance(c, dict) else c
                         for c in s[branch]]
    return s


# --- choosing what goes in the bottle (plan §6.3) -----------------------------------------------

def _a(noun: str) -> str:
    return ("an " if noun[:1].lower() in "aeiou" else "a ") + noun


FAMILY_WORDS = {"potion": "potion", "oil": "oil", "splash": "splash flask",
                "cloud": "cloud", "tool": "tool", INTERMEDIATE: "intermediate"}
ROUTE_WORDS = {"ingest": "drunk", "skin": "on the skin", "eyes": "in the eyes",
               "wound": "on a wound", "inhale": "breathed in", "external": "on a thing",
               "struck": "on whoever it strikes", "splash": "on everyone near the strike",
               "area": "in a cloud", "carried": "on whoever carries it"}


def deliver_reason(family: str, row: dict, *, drawback: bool = False) -> str:
    """Why this family cannot carry this trait, in words, or "" when it can."""
    if family == INTERMEDIATE:
        return ""
    spec = template(row) or {}
    route = str(spec.get("route") or "ingest")
    noun = FAMILY_WORDS.get(family, family)
    if family == "tool" and not drawback:
        if str(spec.get("type")) in set(bench().get("tool_types") or ()):
            return ""
        return "a tool carries only its light or its smoke"
    if route in _routes(family, "drawback" if drawback else "benefit"):
        return ""
    if drawback:
        return (f"nobody takes {_a(noun)} that way: what it does "
                f"{ROUTE_WORDS.get(route, route)} never reaches anyone")
    return f"{_a(noun)} cannot carry a trait that works {ROUTE_WORDS.get(route, route)}"


def _ordinal(n: int) -> str:
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth",
            7: "seventh"}.get(n, f"{n}th")


def _line(row: dict, *, level: int) -> str:
    from . import effectspec

    spec = template(row)
    if spec is None:
        return row["key"]
    shown = graded(spec, row["grade"])
    shown.pop("_source", None)
    try:
        words = effectspec.render(shown)
    except Exception:  # noqa: BLE001 - a document the renderer cannot read still has a name
        words = row["key"]
    if row.get("capped"):
        words += f" ({row.get('essence') or 'trait'} {row['raw']}, capped at {row['grade']} " \
                 f"by your level)"
    return words


def choose(p: dict, *, family: str, formula: dict | None = None, picks=None,
           level: int = 1, strip: list[str] | None = None) -> dict:
    """Which pool traits go into the product, and why each other one does not.

    `picks` is the player's list of trait keys; None picks the strongest deliverable
    traits for the free slots (the page always sends its own). The formula's core takes
    one slot. Drawbacks come along from every material whose benefit is carried or whose
    essence fills the formula's requirement; a drawback the family never delivers to its
    user is dropped with its reason. `strip` lists drawback keys a catalyst took out.

    {"traits": [rows carried], "drawbacks": [rows carried], "rows": [every benefit, with
     picked/reason/text], "drawback_rows": [...], "slots": n, "free": n}"""
    slots = slots_for(family)
    core = 1 if formula else 0
    free = max(0, slots - core)
    ben = list(p.get("traits") or ())
    deliver = {r["key"]: deliver_reason(family, r) for r in ben}
    # A spell bottled through the spell door holds the bottle alone. `consumables.spell_of`
    # (lane C) resolves `holds_spell` at the potion's caster level only when the potion has
    # NO documents of its own: one inherited trait or drawback beside it would turn the
    # spell off. So a derived spell row takes every slot, and says why, until that door
    # can carry documents beside a spell (asked of the lead in lane F's report).
    alone = bool(formula and formula.get("kind") == "spell" and formula.get("core") is None)
    if alone:
        free = 0
        why_alone = "the spell holds the bottle alone: nothing else goes in beside it"
        deliver = {k: (v or why_alone) for k, v in deliver.items()}
    ok = [r for r in ben if not deliver[r["key"]]]
    if picks is None:
        ok_sorted = sorted(ok, key=lambda r: -int(r["grade"]))
        chosen_keys = [r["key"] for r in ok_sorted[:free]]
    else:
        wanted = [str(k) for k in picks]
        chosen_keys = [k for k in wanted if k in {r["key"] for r in ok}][:free]
    chosen = [r for r in ben if r["key"] in chosen_keys]
    rows = []
    taken = 0
    for r in ben:
        reason = deliver[r["key"]]
        picked = r["key"] in chosen_keys
        if picked:
            taken += 1
        elif not reason and len(chosen_keys) >= free:
            reason = (f"{_a(FAMILY_WORDS.get(family, family))} has {slots} "
                      f"slot{'s' if slots != 1 else ''}"
                      + (", one of them the formula's" if core else "")
                      + f"; this would be the {_ordinal(slots + 1)}")
        rows.append(dict(r, picked=picked, reason=reason, text=_line(r, level=level)))
    used: set[str] = set()
    for r in chosen:
        used |= set(r["from"]) | set(r.get("via") or ())
    need = set((((formula or {}).get("requires") or {}).get("essences") or {}))
    for r in ben:
        if r.get("essence") in need:
            used |= set(r["from"]) | set(r.get("via") or ())
    bad_rows, carried = [], []
    stripped = set(strip or ())
    for r in p.get("drawbacks") or ():
        reason = ""
        if alone:
            reason = "the spell holds the bottle alone: no drawback goes in beside it"
        elif family != INTERMEDIATE and not (set(r["from"]) & used):
            reason = "nothing you carry into the bottle comes from what it is a cost of"
        elif r["key"] in stripped:
            reason = "a catalyst stripped it"
        else:
            reason = deliver_reason(family, r, drawback=True)
        if not reason:
            carried.append(r)
        bad_rows.append(dict(r, carried=not reason, reason=reason,
                             text=_line(r, level=level)))
    return {"traits": chosen, "drawbacks": carried, "rows": rows, "drawback_rows": bad_rows,
            "slots": slots, "free": free}


# --- the record -------------------------------------------------------------------------------

def _slim(r: dict) -> dict:
    """A trait as the record keeps it: ids and a grade, never a number to run."""
    out = {"key": r["key"], "grade": int(r["grade"]), "from": list(r["from"])}
    if r.get("essence"):
        out["essence"] = r["essence"]
    if r.get("via"):
        out["via"] = list(r["via"])
    return out


def _slug(text: str) -> str:
    out = "".join(c if c.isalnum() else "-" for c in str(text).lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out


def _quality_prefix(q: int) -> str:
    from .worldclass import quality_name

    name = quality_name(int(q))
    return "" if name in _QUALITY_PREFIX_SKIP else f"{name} "


def product_name(record: dict) -> str:
    """The name a record is shown under: "Fine Alchemist's Fire", "Potion of Fly (CL 6)",
    "Brimstone Flask", "Naphtha Solution (concentrated once)"."""
    from . import formulae
    from .crafting import _concentrated

    q = int(record.get("quality_index", SOUND) if record.get("quality_index") is not None
            else SOUND)
    fid = record.get("formula")
    row = formulae.get(fid) if fid else None
    conc = int(record.get("concentration") or 0)
    tail = f" ({_concentrated(conc)})" if conc else ""
    if record.get("family") == "transmute":
        doc = doc_of(record.get("makes") or "") or {}
        return f"Transmuting {doc.get('name') or record.get('makes')}"
    if row is not None:
        if row.get("kind") == "spell":
            base = str(row.get("name") or fid)
            cl, low = record.get("caster_level"), row.get("caster_level")
            return base + (f" (CL {cl})" if cl and low and int(cl) > int(low) else "")
        return f"{_quality_prefix(q)}{row.get('name') or fid}"
    lead = ""
    for r in list(record.get("traits") or []) + list(record.get("drawbacks") or []):
        if r.get("from"):
            lead = r["from"][0]
            break
    lead = lead or (record_materials(record)[:1] or [""])[0]
    lead_name = str((doc_of(lead) or {}).get("name") or lead.replace("-", " ").title()
                    or "Alchemical")
    if record.get("family") == INTERMEDIATE:
        word = form_row(str(record.get("form") or "")).get("word") or "Preparation"
        return f"{_quality_prefix(q)}{lead_name} {word}{tail}"
    noun = family_row(str(record.get("family") or "")).get("noun") or "Compound"
    return f"{_quality_prefix(q)}{lead_name} {noun}{tail}"


def _tier_of(record: dict) -> str:
    """As rare as its rarest material, one band rarer per concentration step (plan §7.2),
    and never commoner than its formula."""
    from . import formulae
    from .worldclass import TIERS, tier_rank

    rank = 1
    for mid in record_materials(record):
        doc = doc_of(mid)
        if doc is not None:
            rank = max(rank, tier_rank(str(doc.get("tier") or "common")))
    row = formulae.get(record.get("formula")) if record.get("formula") else None
    if row is not None:
        rank = max(rank, tier_rank(str(row.get("tier") or "common")))
    rank = min(len(TIERS), rank + int(record.get("concentration") or 0))
    return TIERS[rank - 1]


def new_record(*, family: str, traits=(), drawbacks=(), formula: str | None = None,
               vessel: str | None = None, quality_index: int = SOUND, level: int = 1,
               perks: dict | None = None, form: str | None = None, concentration: int = 0,
               filtered: int = 0, worked=(), materials=(), made_minute: int = 0,
               bought: bool = False, count: int = 1) -> dict:
    """A product record of plan §12.2: ids and grades. The caster level of a spell potion
    is the rule's (`formulae.caster_level`: the book minimum plus one a tier above Sound),
    written on the record because the enchanter reads it there (contracts §6)."""
    from . import formulae

    rec = {
        "kind": "crafted", "craft": TRACK_ID, "count": int(count),
        "family": family, "form": form, "vessel": vessel, "formula": formula,
        "spell": None, "holds_spell": None, "caster_level": None,
        "quality_index": int(quality_index),
        "traits": [_slim(r) for r in traits], "drawbacks": [_slim(r) for r in drawbacks],
        "concentration": int(concentration), "filtered": int(filtered),
        "worked": list(worked), "materials": list(materials),
        "alchemist": {"level": int(level),
                      "perks": {k: int(v) for k, v in (perks or {}).items() if int(v or 0)}},
        "made_minute": int(made_minute), "bought": bool(bought), "schema": SCHEMA,
        "version": BUILD_VERSION,
    }
    from .worldclass import quality_name

    rec["quality"] = quality_name(int(quality_index)).lower()
    row = formulae.get(formula) if formula else None
    if row is not None and row.get("kind") == "spell" and row.get("spell"):
        rec["spell"] = row["spell"]
        rec["holds_spell"] = row["spell"]
        rec["caster_level"] = formulae.caster_level(row["spell"], int(quality_index),
                                                    spell_level=row.get("spell_level"))
    rec["name"] = product_name(rec)
    rec["tier"] = _tier_of(rec)
    rec["id"] = _slug(rec["name"])
    return rec


def record_for_formula(fid: str, *, vessel: str | None = None, count: int = 1,
                       bought: bool = False) -> dict | None:
    """A formula's product at Sound quality with no inherited traits, as the bench would
    record it (plan §12.5, owner Q8.3: "the same documents as the crafted ones"). The
    shop's own door for a bought product is lane H's `goods.alchemy_stock(fid)`; this is
    the bench's record of the same thing (tests, a converted save). None for a formula the
    table does not have."""
    from . import formulae

    row = formulae.get(fid)
    if row is None:
        return None
    return new_record(family=str(row.get("family")), formula=row["id"], vessel=vessel,
                      quality_index=SOUND, bought=bought, count=count)


# --- the build ----------------------------------------------------------------------------------

def _perk_size(perk: str) -> float:
    from . import worldclass as wc

    try:
        return float((wc.get(TRACK_ID).endless.get("perks") or {}).get(perk, 0) or 0)
    except KeyError:
        return 0.0


def multipliers(record: dict) -> dict:
    """What scales a record's traits: the quality ladder, the perks it was made with,
    concentration and Filter (plan §6.4, §7.2). Book cores take the quality columns only."""
    from .crafting import quality_mult

    q = int(record.get("quality_index") if record.get("quality_index") is not None else SOUND)
    perks = (record.get("alchemist") or {}).get("perks") or {}
    rules = bench()
    conc = int(record.get("concentration") or 0)
    cmult = rules.get("concentration") or {}
    fpot = float(((rules.get("methods") or {}).get("filter") or {}).get("potency", 0.9))
    potency = quality_mult("potency", q) * (1 + _perk_size("potency") * int(perks.get("potency", 0)))
    duration = quality_mult("duration", q) * (1 + _perk_size("duration") * int(perks.get("duration", 0)))
    potency *= float(cmult.get("potency", 1.5)) ** conc
    duration *= float(cmult.get("duration", 1.5)) ** conc
    potency *= fpot ** int(record.get("filtered") or 0)
    return {"potency": round(potency, 4), "duration": round(duration, 4),
            "drawback": quality_mult("drawback", q),
            "core_potency": quality_mult("potency", q),
            "core_duration": quality_mult("duration", q),
            "price": quality_mult("price", q)}


def _clean(spec: dict) -> dict:
    return {k: v for k, v in spec.items() if not str(k).startswith("_")}


def _house_price(record: dict, n_traits: int, potency: float) -> float:
    """A house compound's or an intermediate's worth (plan §12.4): the tier ladder by its
    strength (`pricing`'s own rule: TIER_BASE x potency^0.75), the quality price column,
    and a quarter for a thing that does nothing."""
    from . import pricing

    base = pricing.TIER_BASE.get(_tier_of(record), pricing.TIER_BASE["common"])
    strength = max(1.0, float(sum(int(r.get("grade") or 1)
                                  for r in record.get("traits") or ())) * potency)
    price = base * (strength ** pricing.POTENCY_EXPONENT)
    if not n_traits:
        price *= pricing.INERT_FACTOR
    from .crafting import quality_mult

    q = int(record.get("quality_index") if record.get("quality_index") is not None else SOUND)
    return round(price * quality_mult("price", q), 2)


def build(record: dict) -> dict:
    """What a record does, computed now (contracts §6). Never raises for a record whose
    sources have gone (a homebrew reagent deleted): a trait whose source cannot be read is
    left out, and named in `missing`."""
    from . import effectspec, formulae

    rec = dict(record or {})
    family = str(rec.get("family") or INTERMEDIATE)
    m = multipliers(rec)
    rid = str(rec.get("id") or _slug(rec.get("name") or "alchemy"))
    origin = f"item:{rid}"
    specs: list[dict] = []
    lines: list[dict] = []
    missing: list[str] = []
    row = formulae.get(rec.get("formula")) if rec.get("formula") else None
    holds_spell, caster_level, spell_level = rec.get("holds_spell"), rec.get("caster_level"), None
    splash = None
    range_ft = None
    if row is not None:
        spell_level = row.get("spell_level")
        if row.get("kind") == "spell":
            if row.get("core") is not None:
                # One of the 44 authored potions: its own documents, as written (Q10.2).
                for spec in row.get("core") or []:
                    specs.append(dict(_clean(spec), origin=origin,
                                      source=str(row.get("name"))))
            # A derived row carries no documents: the spell door resolves it at the potion's
            # caster level (`consumables.spell_of`), which a document here would bypass.
            lines.append({"trait": "spell", "core": True, "text":
                          f"{row.get('name')}: the spell at caster level {caster_level}"})
        else:
            for spec in row.get("core") or []:
                s = scaled(_clean(spec), m["core_potency"], m["core_duration"], True)
                if str(s.get("route") or "") == "area" and (row.get("area") or {}).get("radius_ft"):
                    s.setdefault("radius_ft", int(row["area"]["radius_ft"]))
                specs.append(dict(s, origin=origin))
                lines.append({"trait": "core", "core": True, "book": bool(spec.get("book")),
                              "text": effectspec.render(s)})
        if row.get("splash"):
            sp = row["splash"]
            splash = {"amount": int(sp.get("amount") or 1),
                      "damage_type": str(sp.get("damage_type") or "untyped")}
            specs.append({"type": "damage", "dice": str(splash["amount"]),
                          "damage_type": splash["damage_type"], "route": "splash",
                          "book": True, "origin": origin})
        range_ft = row.get("range_increment_ft")
    for r in rec.get("traits") or ():
        t = template(r)
        if t is None:
            missing.append(r.get("key", "?"))
            continue
        src = t.pop("_source", "")
        s = scaled(graded(t, int(r.get("grade") or 1)), m["potency"], m["duration"], True)
        names = [str((doc_of(x) or {}).get("name") or x) for x in r.get("from") or ()]
        specs.append(dict(s, origin=origin, **{"from": ", ".join(names) or src}))
        lines.append({"trait": r.get("essence") or r["key"], "key": r["key"],
                      "grade": int(r.get("grade") or 1), "from": list(r.get("from") or ()),
                      "text": effectspec.render(s)})
    for r in rec.get("drawbacks") or ():
        t = template(r)
        if t is None:
            missing.append(r.get("key", "?"))
            continue
        src = t.pop("_source", "")
        s = scaled(graded(t, int(r.get("grade") or 1)), m["drawback"], m["drawback"], False)
        s["drawback"] = True
        names = [str((doc_of(x) or {}).get("name") or x) for x in r.get("from") or ()]
        specs.append(dict(s, origin=origin, **{"from": ", ".join(names) or src}))
        lines.append({"trait": r.get("essence") or r["key"], "key": r["key"],
                      "grade": int(r.get("grade") or 1), "drawback": True,
                      "from": list(r.get("from") or ()), "text": effectspec.render(s)})
    fam = family_row(family)
    if family in ("splash", "cloud") and not range_ft:
        range_ft = fam.get("range_increment_ft") or 10
    how = list(fam.get("how") or (["ingredient"] if family == INTERMEDIATE else []))
    if family == "potion" and any(str(s.get("route") or "") in ("skin", "eyes", "wound", "inhale")
                                  for s in specs):
        how.append("apply")
    if family in (INTERMEDIATE, "transmute"):
        # An intermediate is an input and a thing to sell, never a dose: what it carries
        # is on its card (`lines`), and the use door sees nothing to run.
        run = []
        how = ["ingredient"]
    else:
        run = specs
    if row is not None and row.get("kind") == "spell":
        price = formulae.potion_price(int(row.get("spell_level") or 0),
                                      int(caster_level or row.get("caster_level") or 1))
    elif row is not None:
        price = round(float(row.get("price_gp") or 0) * m["price"], 2)
    else:
        price = _house_price(rec, len(rec.get("traits") or ()), m["potency"])
    keeps = fam.get("keeps") if family != INTERMEDIATE else \
        form_row(str(rec.get("form") or "")).get("keeps")
    return {
        "specs": run,
        "card": specs,
        "family": family,
        "how": how,
        "action": fam.get("action") or ("" if family == INTERMEDIATE else "standard"),
        "splash": splash,
        "range_increment_ft": int(range_ft) if range_ft else None,
        "holds_spell": holds_spell,
        "caster_level": caster_level,
        "spell_level": spell_level,
        "target": ((row or {}).get("delivers") or {}).get(family),
        "price_gp": price,
        "keeps_minutes": int(keeps) if keeps else None,
        "lines": lines,
        "missing": missing,
        "multipliers": m,
        "tier": _tier_of(rec),
        "name": product_name(rec),
        "version": BUILD_VERSION,
    }


def preview(mix, *, family, formula=None, picks=None, quality_index=SOUND, level=1,
            perks=None, form=None, concentration=0, filtered=0) -> dict:
    """What bottling `mix` would make, in `build`'s shape (contracts §6). The mix is the
    pool; `picks` choose its traits as at Bottle."""
    from . import formulae

    row = formulae.get(formula) if formula else None
    p = {"traits": [dict(r, raw=r.get("grade", 1)) for r in (mix or {}).get("traits") or ()],
         "drawbacks": [dict(r, raw=r.get("grade", 1)) for r in (mix or {}).get("drawbacks") or ()]}
    chosen = choose(p, family=family, formula=row, picks=picks, level=level)
    rec = new_record(family=family, traits=chosen["traits"], drawbacks=chosen["drawbacks"],
                     formula=formula, quality_index=quality_index, level=level, perks=perks,
                     form=form, concentration=concentration, filtered=filtered)
    return build(rec)


# --- on the shelf ----------------------------------------------------------------------------------

@dataclass
class AlchemyStock(Stock):
    """An alchemist's product or intermediate on the shelf, carrying its record.

    `Actor.stock` holds `crafting.Stock` objects, and a Stock has no field for a formula,
    a vessel or a trait's grade, so the record rides here whole and `as_dict` writes it
    back under "alchemy" (the forge's `ForgedStock` pattern). `specs`, `how`, the spell,
    the price and the range are the build's, refreshed from the record every load.
    """
    record: dict = field(default_factory=dict)
    price_gp: float | None = None
    range_increment_ft: int | None = None

    @property
    def id(self) -> str:  # type: ignore[override]
        return f"{_slug(self.name)}~{digest(self.record)}"

    @property
    def name(self) -> str:  # type: ignore[override]
        return str(self.record.get("name") or self.base)

    @property
    def family(self) -> str:
        return str(self.record.get("family") or "")

    # Read by `pricing.alchemy_worth` (lane H) off any stock row through getattr: a crafted
    # product says which formula it is, so the counter prices it by the book.
    @property
    def formula(self) -> str | None:
        return self.record.get("formula") or None

    @property
    def bought(self) -> bool:
        return bool(self.record.get("bought"))

    def as_dict(self) -> dict:
        d = super().as_dict()
        d["alchemy"] = copy.deepcopy(self.record)
        if self.price_gp is not None:
            d["price_gp"] = self.price_gp
        if self.range_increment_ft:
            d["range_increment_ft"] = self.range_increment_ft
        from .worldclass import quality_name

        q = self.record.get("quality_index")
        if q is not None:
            d["quality_name"] = quality_name(int(q))
        d["family"] = self.family
        return d


def digest(record: dict) -> str:
    """What makes two records the same thing to stack: everything but the count, the
    minute it was made and the stamps."""
    keep = {k: v for k, v in (record or {}).items()
            if k not in ("count", "made_minute", "version", "work")}
    return hashlib.md5(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:10]


_HELD = ("in_progress", "steeping")


def refresh(st: AlchemyStock) -> bool:
    """Fill a stock entry from its record's build. Old work (schema below 4) is never
    rebuilt. True when anything changed. A record the build cannot read keeps what it
    had: a load must never fail on one bottle."""
    rec = st.record or {}
    if int(rec.get("schema") or 0) < SCHEMA:
        return False
    try:
        b = build(rec)
    except Exception:  # noqa: BLE001 - one unreadable bottle never breaks a campaign load
        return False
    before = (st.specs, st.how, st.holds_spell, st.caster_level, st.price_gp,
              st.range_increment_ft, st.tier, st.base)
    st.specs = b["specs"]
    held = [h for h in (st.how or []) if h in _HELD]
    st.how = list(b["how"]) + [h for h in held if h not in b["how"]]
    st.holds_spell = b["holds_spell"] or None
    st.caster_level = b["caster_level"] or None
    st.price_gp = b["price_gp"]
    st.range_increment_ft = b["range_increment_ft"]
    st.tier = b["tier"]
    st.base = b["name"]
    rec["version"] = BUILD_VERSION
    return before != (st.specs, st.how, st.holds_spell, st.caster_level, st.price_gp,
                      st.range_increment_ft, st.tier, st.base)


def to_stock(record: dict, count: int | None = None) -> AlchemyStock:
    rec = copy.deepcopy(record)
    n = int(count if count is not None else rec.get("count", 1) or 1)
    rec["count"] = n
    st = AlchemyStock(base=str(rec.get("name") or "Alchemical work"), count=n,
                      craft=TRACK_ID, kind="crafted", tier=str(rec.get("tier") or "common"),
                      from_materials=record_materials(rec), record=rec)
    refresh(st)
    return st


def is_alchemy_record(d) -> bool:
    return isinstance(d, dict) and isinstance(d.get("alchemy"), dict)


def stock_item(d: dict) -> AlchemyStock:
    """A saved row back as an `AlchemyStock` (the loader, `crafting.from_stock_dict`): the
    record whole, the pack's own fields (count, the In-progress block, anything another
    door wrote) kept, and the build refreshed."""
    rec = copy.deepcopy(d["alchemy"])
    st = AlchemyStock(
        base=str(d.get("base") or rec.get("name") or "Alchemical work"),
        count=int(d.get("count", rec.get("count", 1)) or 0),
        craft=str(d.get("craft") or TRACK_ID), kind=str(d.get("kind") or "crafted"),
        tier=str(d.get("tier") or rec.get("tier") or "common"),
        specs=[dict(s) for s in d.get("specs") or []],
        how=list(d.get("how") or []),
        holds_spell=d.get("holds_spell") or None,
        caster_level=int(d["caster_level"]) if d.get("caster_level") else None,
        from_materials=list(d.get("from_materials") or record_materials(rec)),
        properties=list(d.get("properties") or []),
        work=copy.deepcopy(d["work"]) if isinstance(d.get("work"), dict) and d["work"] else None,
        record=rec)
    refresh(st)
    return st


def records(actor) -> list[tuple[str, AlchemyStock]]:
    return [(k, v) for k, v in (getattr(actor, "stock", None) or {}).items()
            if isinstance(v, AlchemyStock)]


def put(actor, record: dict, count: int = 1) -> str:
    """Put a product on the shelf, stacking with an identical one (the older minute kept,
    so a solution never looks fresher than its oldest measure). Returns its key."""
    st = to_stock(record, count)
    key = st.id
    have = (actor.stock or {}).get(key)
    if isinstance(have, AlchemyStock) and not have.work:
        have.count = int(have.count or 0) + int(count)
        have.record["count"] = have.count
        have.record["made_minute"] = min(int(have.record.get("made_minute") or 0),
                                         int(record.get("made_minute") or 0))
        return key
    while key in (actor.stock or {}):
        key = f"{key}+"
    actor.stock[key] = st
    return key


__all__ = ["AlchemyStock", "BUILD_VERSION", "INTERMEDIATE", "SCHEMA", "build", "choose",
           "deliver_reason", "digest", "graded", "is_alchemy_record", "material_rows",
           "mix_of", "multipliers", "new_record", "pool", "preview", "product_name",
           "product_specs", "put", "record_for_formula", "record_materials", "records",
           "refresh", "scaled", "stock_item", "template", "to_stock", "trait_key"]
