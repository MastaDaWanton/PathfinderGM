"""Curses: what a flawed binding leaves on an item, and how the layer carries it.

Enchanting plan §11 as the owner ruled it (docs/enchanting-answers.md, rounds 1 and 4):
**book curses, hidden.** A Bind that misses by 5 or more takes, flawed: the item works and
carries a curse rolled on the book's table (CRB, Cursed Items:
https://legacy.aonprd.com/coreRulebook/magicItems/cursedItems.html). The player saw their
own d20 and margin and the bench said FLAWED; *which* curse stays hidden until the item is
identified by 10 or more ("unless the check made to identify the item exceeds the DC by 10
or more, the curse is not detected", the same page) or the curse shows itself in play.
Materials are not lost (owner, round 1).

**The table** is content/rules/curses.json: the book's top d% unchanged, and the
sub-tables with the owner's dropped rows taken out (gender, race and alignment changes,
polymorph, the incurable disease, the compulsion to attack: round 4 point 3) and the d%
re-scaled over what is left by a rule the test re-derives, never by eye. Rows the engine
could never ask about (temperature, water, distance to a site) are dropped there too, each
with its reason in `dropped` — a row that can never fire is a lie on the identify card.

**How a curse acts: through the layer, never beside it** (law 2). `magic_layer.layer`
asks `documents(curse, layer)` and applies what comes back — `suppress`, `replace`, `add`,
`enhancement` — so a curse's numbers reach the funnel by the same doors as the
enchantment's, and remove the item (or lift the curse) and they evaporate. Nothing here
writes an ActiveEffect or touches an actor. The documents are the effect vocabulary's own
(a negative level, a daily save gate, an untyped -2), every number the book's.

**Hidden means hidden** (law 3). The curse record is opaque to everyone but this module
and the engine; its `id` and its words never reach anything the page reads until
`known.curse` is true (tests/test_curses.py sweeps for both). The documents a curse adds
carry `source: "binding"` and `flaw: true`, never the curse's name, so a reader's tell can
say that something in the item is wrong without saying what. `tell(curse, name,
known=...)` is the one place that decides which words a moment of the curse gets.

**What tried and failed elsewhere, and why the shape is this:** the plan's first idea for
an intermittent item was "works only in its planet's hour"; the owner replaced planets
with phases of the day (round 4 point 10), so the book's "holy days or astrological
events" row is reworded to a phase. Rolling perks and flaws in secret is refused by the
prior art (Unchained's dynamic creation, docs/enchanting-prior-art.md §5.4) — a curse is
only ever the result of a miss the player saw, never a surprise on a success.
"""
from __future__ import annotations

import copy
import functools
import json
from pathlib import Path

SCHEMA = 1
FILE = "curses.json"

# The situation facts a dependent curse's `when` clause asks of the roll context. Generic
# equality in `Actor._when_holds` answers all but `near` from whatever the engine puts in
# the context; `near` needs its own branch (contracts §4 for lane C). An unevaluable
# clause is dropped, so until the context carries the fact the item's magic is off — a
# dependent curse fails closed, never open.
SITUATION_FACTS = ("daylight", "underground", "near", "wielder_casts", "day_phase")

# The requirement facts `settle_day` is handed once a day, each a bool for that day.
REQUIREMENT_FACTS = ("ate_double", "slept_double", "used", "drew_blood", "killed",
                     "other_magic")

# Arms held in the hand take `wielded`; everything else is `worn` (effectspec.ITEM_TRIGGERS).
_HELD = ("weapon",)
_LISTS = ("specs", "riders", "wielded", "worn", "strikes_as", "raises", "powers", "tags")
_MOD_TYPES = ("combat_mod", "save_mod", "skill_mod", "ability_mod")
# Where a curse's documents say they come from. Never the curse's id or row: a reader's
# tell built from `source` must not name what is hidden.
SOURCE = "binding"


class BadCurses(ValueError):
    """content/rules/curses.json does not validate; every problem is named."""


# --- the table ---------------------------------------------------------------------------

def _path() -> Path:
    from django.conf import settings

    return Path(settings.BASE_DIR) / "content" / "rules" / FILE


@functools.lru_cache(maxsize=1)
def _table() -> dict:
    data = json.loads(_path().read_text(encoding="utf-8"))
    problems = table_problems(data)
    if problems:
        raise BadCurses("content/rules/curses.json is not valid:\n  " + "\n  ".join(problems))
    return data


def table() -> dict:
    """The whole curse table, validated on load (a copy: the cache is not the caller's)."""
    return copy.deepcopy(_table())


def rows() -> list[dict]:
    """The top table, the book's own d%."""
    return table()["rows"]


def sub_table(name: str) -> list[dict]:
    return table()["tables"][name]


def __getattr__(name):  # PEP 562: `curses.ROWS` as the contract names it, read lazily
    if name == "ROWS":
        return rows()
    raise AttributeError(name)


def _covers(rows_: list[dict], where: str) -> list[str]:
    out, want = [], 1
    for r in rows_:
        lo, hi = (r.get("d100") or [0, -1])[:2]
        if lo != want or hi < lo:
            out.append(f"{where}: {r.get('id')} spans {lo}-{hi}, and the row before it "
                       f"ended at {want - 1}. The d% must run 1-100 with no gap or overlap.")
            return out
        want = hi + 1
    if want != 101:
        out.append(f"{where}: the d% ends at {want - 1}; it must end at 100.")
    return out


def _filled(doc: dict, cl: int) -> dict:
    """A document with the book's "10 + cl" filled from the item's caster level."""
    out = copy.deepcopy(doc)
    if out.get("dc") == "10 + cl":
        out["dc"] = 10 + int(cl)
    for sub in out.get("on_failure") or ():
        if isinstance(sub, dict) and sub.get("dc") == "10 + cl":
            sub["dc"] = 10 + int(cl)
    return out


def table_problems(data: dict) -> list[str]:
    """Everything wrong with the table, each with its fix named."""
    from . import effectspec

    out: list[str] = []
    tables = data.get("tables") or {}
    out += _covers(data.get("rows") or [], "rows")
    seen = set()
    for r in data.get("rows") or []:
        if r.get("id") in seen:
            out.append(f"rows: {r.get('id')} is listed twice.")
        seen.add(r.get("id"))
        if r.get("table") and r["table"] not in tables:
            out.append(f"rows: {r['id']} names table {r['table']!r}, which is not in "
                       f"\"tables\".")
        if not r.get("table") and not str(r.get("words") or "").strip():
            out.append(f"rows: {r.get('id')} has no words for the identify card.")
    for name, sub in tables.items():
        out += _covers(sub, f"tables.{name}")
        ids = [r.get("id") for r in sub]
        if len(ids) != len(set(ids)):
            out.append(f"tables.{name}: an id is listed twice.")
        for r in sub:
            where = f"tables.{name}.{r.get('id')}"
            if r.get("table") and r["table"] not in tables:
                out.append(f"{where}: names table {r['table']!r}, which does not exist.")
            if not str(r.get("words") or "").strip() and name != "dependent":
                out.append(f"{where}: no words for the identify card.")
            if name == "dependent":
                if not r.get("when") or set(r["when"]) - set(SITUATION_FACTS):
                    out.append(f"{where}: a dependent row's when names one of "
                               f"{', '.join(SITUATION_FACTS)}.")
                if not str(r.get("situation") or "").strip():
                    out.append(f"{where}: says no situation for the card.")
            if name == "requirement" and r.get("fact") not in REQUIREMENT_FACTS:
                out.append(f"{where}: fact {r.get('fact')!r} is not one settle_day is "
                           f"handed. One of {', '.join(REQUIREMENT_FACTS)}.")
            for i, d in enumerate(r.get("documents") or ()):
                for p in effectspec.validate(_filled(d, 5), f"{where}.documents[{i}]"):
                    out.append(p)
                if not d.get("book"):
                    out.append(f"{where}.documents[{i}]: a curse's number is the book's; "
                               f"mark it \"book\": true or remove it.")
            if r.get("bars") and not str(r["bars"]).startswith("curse."):
                out.append(f"{where}: bars {r['bars']!r} is a tag under curse.*.")
    for d in data.get("dropped") or ():
        if not str(d.get("why") or "").strip():
            out.append(f"dropped: {d.get('name')} gives no reason.")
    return out


def _row(rows_: list[dict], d100: int) -> dict:
    for r in rows_:
        lo, hi = r["d100"]
        if lo <= d100 <= hi:
            return r
    raise ValueError(f"no row for d% {d100}")


def _fits(row: dict, gear: str) -> bool:
    return not row.get("gear") or gear in row["gear"]


def _row_for(rows_: list[dict], d100: int, gear: str) -> dict:
    """The row the die names, or — when that row cannot go on this item (a blade's
    requirement on a ring) — the next one down the table that can, wrapping. Rerolling
    would make the d% lie about the odds of every other row; stepping keeps them."""
    start = rows_.index(_row(rows_, d100))
    for i in range(len(rows_)):
        r = rows_[(start + i) % len(rows_)]
        if _fits(r, gear):
            return r
    raise ValueError("no row fits this item")


# --- rolling -----------------------------------------------------------------------------

def _d(dice, faces: int) -> int:
    """One die of `faces` from whatever the caller rolls with: a `dice.Dice` (the engine's),
    or a callable taking the number of faces (a test's script)."""
    if hasattr(dice, "roll"):
        return int(dice.roll(f"1d{int(faces)}").total)
    return int(dice(int(faces)))


def _gear(record) -> str:
    from . import magic_layer

    return magic_layer.vessel_kind(record if isinstance(record, dict) else {})


def roll(dice, record, layer_plan: dict | None = None) -> dict:
    """Roll a flawed binding's curse (contracts §7).

    `record` is the vessel; `layer_plan` is `magic_layer.plan(...)`'s result for the
    binding (its `caster_level` and `needs`), optionally with `adds` (the working's own
    entries, choices included) beside it, which a completely-different curse reads to
    substitute like for like. Returns the curse record E hands `magic_layer.write`:

    {"schema", "id", "d100", "row", "detail", "tags", "cl", "gear", "origin", "state"}

    `id` is "curse:<row>[:<sub>]"; it and `detail` never leave the engine while the curse
    is unknown. The rolls are the engine's (hidden): the player rolled the Bind, not this.
    """
    from . import magic_layer

    rec = record if isinstance(record, dict) else {}
    gear = _gear(rec)
    plan = dict(layer_plan or {})
    m = magic_layer.magic_of(rec)
    cl = int(plan.get("caster_level") or magic_layer.caster_level(m, gear) or 0)
    d100 = _d(dice, 100)
    top = _row(rows(), d100)
    detail: dict = {}
    path = [top["id"]]
    name = top.get("table")
    while name:
        sub_d = _d(dice, 100)
        sub = _row_for(sub_table(name), sub_d, gear)
        detail.setdefault("rolls", []).append({"table": name, "d100": sub_d})
        path.append(sub["id"])
        detail[name] = sub["id"]
        if sub.get("rolls"):
            detail.update(_detail_roll(dice, sub["rolls"]))
        name = sub.get("table")
    if top["id"] == "different":
        detail["instead"] = _substitutes(dice, rec, gear, m, plan)
    item_id = str(rec.get("id") or rec.get("name") or "item").strip()
    return {"schema": SCHEMA, "id": "curse:" + ":".join(path), "d100": d100,
            "row": top["id"], "detail": detail,
            "tags": ["curse." + ".".join(path)], "cl": cl, "gear": gear,
            "origin": f"item:{item_id}", "state": {}}


def _detail_roll(dice, what: str) -> dict:
    from . import effectspec, sky

    if what == "creature_type":
        types = sorted(effectspec.CREATURE_TYPES)
        return {"creature_type": types[_d(dice, len(types)) - 1]}
    if what == "phase":
        return {"phase": sky.PHASES[_d(dice, len(sky.PHASES)) - 1]}
    if what == "taller":
        # The book's own sub-roll: 01-50 shrinks, 51-100 grows.
        return {"taller": _d(dice, 100) > 50}
    return {}


def _prop_price_kind(prop: dict):
    if prop.get("plus") is not None:
        return ("plus", int(prop["plus"]))
    if prop.get("gp") is not None:
        return ("gp", None)
    if prop.get("scaled"):
        return ("scaled", None)
    return ("?", None)


def _substitutes(dice, record: dict, gear: str, m: dict, plan: dict) -> dict:
    """What a completely-different curse makes each enchantment into, chosen now and
    recorded so the item is the same item on every read (plan §11.2: "another property of
    the same plus from the same family pool"). Like for like: the same price kind and plus,
    a property that fits the vessel (its own restriction sentence), executable (it has
    documents), not already on the item. An item with only an enhancement trades it for a
    property of that plus; a wondrous power for another recipe on the same slot near its
    price."""
    from . import effectspec, magic_layer

    entries = [dict(e) for e in m["properties"] + m["flat"]]
    for e in (plan.get("adds") or {}).get("properties") or ():
        entries.append(dict(e))
    for e in (plan.get("adds") or {}).get("flat") or ():
        entries.append(dict(e))
    for pid in ((plan.get("needs") or {}).get("grants") or ()):
        if not any(e.get("id") == pid for e in entries):
            entries.append({"id": pid})
    have = {str(e.get("id")) for e in entries}
    table_ = effectspec.properties()
    out: dict = {"properties": {}, "enhancement": None, "powers": {}}
    taken: set[str] = set()

    def pick(kind_of, choice_bonus=None, exclude=()) -> dict | None:
        pool = []
        for pid in sorted(table_):
            q = table_[pid]
            if pid in have or pid in taken or pid in exclude:
                continue
            if gear not in (q.get("gear") or ()) or not q.get("documents"):
                continue
            if _prop_price_kind(q) != kind_of:
                continue
            if magic_layer._requires_problems(q, record, gear):
                continue
            pool.append(q)
        if not pool:
            return None
        q = pool[_d(dice, len(pool)) - 1]
        choice = None
        spec = q.get("choice")
        if spec:
            options = list(spec.get("options") or (
                effectspec.SKILLS if spec.get("of") == "skill" else ()))
            if not options:
                return None
            choice = {spec["key"]: options[_d(dice, len(options)) - 1]}
        if q.get("scaled"):
            values = list((q.get("scaled") or {}).get("values") or [1])
            bonus = choice_bonus if choice_bonus in values else values[0]
            choice = dict(choice or {}, bonus=bonus)
        if effectspec.choice_problems(q, choice):
            return None
        taken.add(q["id"])
        return {"id": q["id"], "choice": choice}

    for e in entries:
        prop = table_.get(str(e.get("id")))
        if prop is None or str(e["id"]) in out["properties"]:
            continue
        bonus = ((e.get("choice") or {}) or {}).get("bonus")
        got = pick(_prop_price_kind(prop), bonus)
        if got:
            out["properties"][str(e["id"])] = got
    # The enhancement as it will stand once this binding is laid on.
    enh = int(m.get("enhancement") or 0)
    if plan.get("adds"):
        enh += int((plan["adds"] or {}).get("enhancement") or 0)
    elif (plan.get("needs") or {}).get("enhancement"):
        enh = int(plan["needs"]["enhancement"].get("to") or enh)
    if enh and not out["properties"] and gear in magic_layer.ARMS:
        best = None
        for plus in range(min(enh, 5), 0, -1):
            best = pick(("plus", plus))
            if best:
                break
        out["enhancement"] = best
    powers = [str(p.get("recipe")) for p in m["powers"] if p.get("recipe")]
    powers += [str(p) for p in (plan.get("needs") or {}).get("powers") or ()]
    for rid in dict.fromkeys(powers):
        sub = _substitute_recipe(dice, rid, set(powers))
        if sub:
            out["powers"][rid] = sub
    return out


def _all_recipes() -> dict[str, dict]:
    """Every catalogue item as a recipe: lane D's door when it serves them, the old
    catalogue until then (the same order `magic_layer.recipe` asks)."""
    try:
        from . import materials as _materials

        fn = getattr(_materials, "recipes", None)
        if callable(fn):
            got = fn()
            if got:
                return {str(k): dict(v) for k, v in got.items()}
    except Exception:  # noqa: BLE001 - a missing lane is not a crash
        pass
    from . import magicitem

    return {k: v.as_dict() for k, v in magicitem.catalogue().items()
            if str(getattr(v, "kind", "")) == "wondrous"}


def _substitute_recipe(dice, rid: str, exclude: set[str]) -> str | None:
    from . import magic_layer

    me = magic_layer.recipe(rid) or {}
    slot = str(me.get("slot") or "")
    gp = float(me.get("price_gp") or 0)
    pool = [(abs(float(r.get("price_gp") or 0) - gp), k)
            for k, r in _all_recipes().items()
            if k not in exclude and str(r.get("slot") or "") == slot and r.get("effects")]
    if not pool:
        return None
    pool.sort()
    near = [k for _, k in pool[:3]]
    return near[_d(dice, len(near)) - 1]


# --- what a curse does to the layer (lane B's seam) ---------------------------------------

def _origin(curse: dict, layer: dict) -> str:
    for key in ("specs", "riders", "wielded", "worn"):
        for d in layer.get(key) or ():
            if isinstance(d, dict) and d.get("origin"):
                return str(d["origin"])
    return str(curse.get("origin") or "item:item")


def _stamp(doc: dict, origin: str) -> dict:
    return dict(doc, origin=origin, source=SOURCE, flaw=True)


def _sub(curse: dict, name: str) -> dict | None:
    sid = (curse.get("detail") or {}).get(name)
    if not sid:
        return None
    try:
        return next(r for r in sub_table(name) if r["id"] == sid)
    except StopIteration:
        return None


def _trigger(curse: dict) -> str:
    return "wielded" if str(curse.get("gear") or "") in _HELD else "worn"


def documents(curse, layer: dict) -> dict:
    """How the curse changes the layer, for `magic_layer._apply_curse` (contracts §3.4):
    any of `suppress` (bool), `replace` ({list: [...]}), `add` ({list: [...]}),
    `enhancement` (int). Pure; `layer` is a copy. An unknown or malformed curse changes
    nothing — a reader of the layer must never crash on a save — and the test pins that
    every row of the table returns a change."""
    if not isinstance(curse, dict) or not curse.get("row"):
        return {}
    layer = layer or {}
    row = str(curse["row"])
    origin = _origin(curse, layer)
    if row == "delusion":
        return {"suppress": True}
    if row == "opposite":
        return _opposite(layer)
    if row == "specific":
        return _specific(layer, curse)
    if row == "different":
        return _different(layer, curse, origin)
    if row == "intermittent":
        kind = (curse.get("detail") or {}).get("intermittent")
        if kind == "unreliable":
            pct = int((_sub(curse, "intermittent") or {}).get("chance_pct") or 5)
            return {"replace": _every_doc(layer, lambda d: dict(d, gutters_pct=pct))}
        if kind == "dependent":
            sit = _sub(curse, "dependent") or {}
            clause = _situation_clause(sit, curse)
            return {"replace": _every_doc(layer, lambda d: dict(
                d, when={**dict(d.get("when") or {}), **clause}))}
        return {}
    if row == "requirement":
        return {"suppress": True} if (curse.get("state") or {}).get("unmet") else {}
    if row == "drawback":
        sub = _sub(curse, "drawback") or {}
        add: dict = {}
        for d in sub.get("documents") or ():
            doc = _stamp(_filled(d, int(curse.get("cl") or 0)), origin)
            if doc.get("type") in _MOD_TYPES:
                add.setdefault("specs", []).append(doc)
            else:
                add.setdefault(_trigger(curse), []).append(dict(doc, trigger=_trigger(curse)))
        if sub.get("bars"):
            add.setdefault("tags", []).append(str(sub["bars"]))
        return {"add": add} if add else {}
    return {}


def _every_doc(layer: dict, fn) -> dict:
    out = {}
    for key in ("specs", "riders", "wielded", "worn"):
        out[key] = [fn(dict(d)) for d in layer.get(key) or ()]
    out["raises"] = [fn(dict(d)) for d in layer.get("raises") or ()]
    out["powers"] = [dict(p, spec=fn(dict(p.get("spec") or {}))) for p in
                     layer.get("powers") or ()]
    return out


def _situation_clause(sit: dict, curse: dict) -> dict:
    det = curse.get("detail") or {}
    clause = copy.deepcopy(sit.get("when") or {})
    if "near" in clause:
        clause["near"] = {"type": det.get("creature_type") or "humanoid"}
    if "day_phase" in clause:
        clause["day_phase"] = det.get("phase") or "midnight"
    return clause


def _flip(d: dict) -> dict | None:
    """One standing document under an opposite curse: a bonus becomes the same-sized
    penalty, untyped, because 1e's penalties carry no bonus type ("an enhancement
    penalty" is no rule) and `dice.stack` keeps every penalty whatever its type, so it
    sits beside masterwork's +1 rather than competing with it. Anything that is not a
    number to flip has no opposite to run and is gone."""
    if d.get("type") in _MOD_TYPES:
        try:
            amount = int(d.get("amount"))
        except (TypeError, ValueError):
            return None
        return dict(d, amount=-abs(amount), bonus_type="untyped")
    return None


def _hurts(d: dict) -> bool:
    from . import effectspec

    try:
        return bool(effectspec.is_drawback(d))
    except Exception:  # noqa: BLE001
        return False


def _opposite(layer: dict) -> dict:
    """"Opposite-effect items include weapons that impose penalties on attack and damage
    rolls rather than bonuses" (CRB): every bonus a penalty; a rider meant for a foe
    lands on the bearer (`recipient: "self"`, vicious's spelling); a power is turned on
    its user; what helped the bearer and has no opposite (a resistance, a sense) is gone;
    what already hurt the bearer stays."""
    specs = [f for f in (_flip(d) for d in layer.get("specs") or ()) if f]
    riders = [dict(d, recipient="self") for d in layer.get("riders") or ()]
    keep = {k: [dict(d) for d in layer.get(k) or () if _hurts(d)]
            for k in ("wielded", "worn")}
    powers = [dict(p, spec=dict(p.get("spec") or {}, recipient="self"))
              for p in layer.get("powers") or ()]
    enh = int(layer.get("enhancement") or 0)
    return {"replace": {"specs": specs, "riders": riders, **keep, "powers": powers,
                        "strikes_as": [], "raises": [], "tags": []},
            "enhancement": -abs(enh)}


def _specific(layer: dict, curse: dict) -> dict:
    """The book's "−2 cursed" shape (plan §11.2): a -2 where each bonus was, untyped, and
    the item clings (`clings`)."""
    pen = int(table().get("specific_penalty", -2))
    seen, specs = set(), []
    for d in layer.get("specs") or ():
        if d.get("type") in _MOD_TYPES and (d.get("type"), d.get("target")) not in seen:
            seen.add((d.get("type"), d.get("target")))
            specs.append(dict(d, amount=pen, bonus_type="untyped"))
    keep = {k: [dict(d) for d in layer.get(k) or () if _hurts(d)]
            for k in ("wielded", "worn")}
    powers = [dict(p, spec=dict(p.get("spec") or {}, recipient="self"))
              for p in layer.get("powers") or ()]
    return {"replace": {"specs": specs, "riders": [], **keep, "powers": powers,
                        "strikes_as": [], "raises": [], "tags": []},
            "enhancement": pen if str(curse.get("gear") or "") in ("weapon", "armour",
                                                                    "shield") else 0}


def _different(layer: dict, curse: dict, origin: str) -> dict:
    """Every enchantment the substitutes replace comes off (its documents, its essence's
    top-ups, its tag) and the substitute's bound documents go on, through lane B's own
    bucketing so they land in the lists the readers read."""
    from . import effectspec, magic_layer

    instead = (curse.get("detail") or {}).get("instead") or {}
    props = instead.get("properties") or {}
    gone_props = {f"property:{p}" for p in props}
    enh_sub = instead.get("enhancement")
    powers = instead.get("powers") or {}
    gone_recipes = {f"recipe:{r}" for r in powers}

    def stays(d: dict) -> bool:
        src = str(d.get("source") or "")
        if src in gone_props or src in gone_recipes:
            return False
        if enh_sub and src == "enhancement":
            return False
        # An essence's top-up rides the enchantment it came with (magic_layer.layer).
        if src.startswith("essence:") and (props or enh_sub or powers):
            return False
        return True

    out = {k: [dict(d) for d in layer.get(k) or () if stays(d)]
           for k in ("specs", "riders", "wielded", "worn", "raises")}
    out["powers"] = [dict(p) for p in layer.get("powers") or ()
                     if str(p.get("source") or "") not in gone_recipes]
    out["strikes_as"] = list(layer.get("strikes_as") or ())
    out["tags"] = [t for t in layer.get("tags") or ()
                   if t not in {effectspec.property_tag(p) for p in props}]
    for pick in list(props.values()) + ([enh_sub] if enh_sub else []):
        try:
            docs = effectspec.bind(pick["id"], pick.get("choice"))
        except (ValueError, KeyError):
            continue
        out["tags"].append(effectspec.property_tag(pick["id"]))
        for d in docs:
            magic_layer._bucket(out, dict(d, origin=origin), {}, pick["id"])
    for rid in powers.values():
        r = magic_layer.recipe(rid) or {}
        for d in r.get("effects") or ():
            if isinstance(d, dict):
                magic_layer._bucket(out, dict(copy.deepcopy(d), origin=origin,
                                              source=f"recipe:{rid}"), {}, rid)
    change: dict = {"replace": out}
    if enh_sub:
        change["enhancement"] = 0
        if str(curse.get("gear") or "") == "weapon":
            # The +N's own DR traits go with it; the substitute's are its own.
            enh = int(layer.get("enhancement") or 0)
            own = set(effectspec.strikes_as_for_enhancement(enh))
            out["strikes_as"] = [s for s in out["strikes_as"] if s not in own]
    return change


# --- what else the engine and the bench ask ----------------------------------------------

def curse_of(record) -> dict | None:
    """The curse on a record (a dict, a forged stock entry, or a Stock with `magic`)."""
    rec = getattr(record, "record", record)
    magic = rec.get("magic") if isinstance(rec, dict) else getattr(rec, "magic", None)
    c = (magic or {}).get("curse") if isinstance(magic, dict) else None
    return c if isinstance(c, dict) and c.get("row") else None


def clings(record) -> bool:
    """Whether the item refuses to leave its bearer (the specific cursed item: "can only be
    discarded after ... remove curse", CRB). Asked by whatever puts an item down — and
    asked whether or not the curse is known: trying to drop it is how it is found."""
    c = curse_of(record)
    return bool(c and c.get("row") == "specific")


def gutters(curse, d100: int) -> bool:
    """Whether an unreliable item's magic fails on this use: the engine's d% against the
    row's chance ("01-05 on d%", CRB). False for any other curse."""
    c = curse if isinstance(curse, dict) else {}
    if c.get("row") != "intermittent" or (c.get("detail") or {}).get(
            "intermittent") != "unreliable":
        return False
    return int(d100) <= int((_sub(c, "intermittent") or {}).get("chance_pct") or 5)


def noticed(curse) -> bool:
    """A drawback anyone can see the moment the item is carried (hair, skin, a mark, a
    sound, a mood): it is found the hard way at once, when the item is first held or worn."""
    c = curse if isinstance(curse, dict) else {}
    return c.get("row") == "drawback" and bool((_sub(c, "drawback") or {}).get("noticed"))


def lift_dc(curse) -> int:
    """Remove curse's caster level check: DC 10 + the item's caster level (CRB)."""
    c = curse if isinstance(curse, dict) else {}
    return int(table().get("lift_dc_base", 10)) + int(c.get("cl") or 0)


def lift(record) -> dict:
    """A new record with the curse gone and the rest kept (plan §10: Cleanse, Enchanter 3;
    the remove curse spell). The owner now knows the item is clean."""
    rec = copy.deepcopy(dict(record or {}))
    magic = dict(rec.get("magic") or {})
    magic["curse"] = None
    known = dict(magic.get("known") or {})
    known["curse"] = True
    magic["known"] = known
    rec["magic"] = magic
    return rec


def settle_day(record, facts: dict, *, day: int) -> tuple[dict, list[str]]:
    """A requirement curse's day: whether the bearer met it, read from `facts` (one bool per
    `REQUIREMENT_FACTS`, gathered by the engine at `run_periodic("day")`). Unmet, the
    layer is suppressed until the next day it is met (plan §11.2), and the change is told —
    without naming the curse while it is hidden (law 3). Returns (the new record, lines).
    A fact the caller did not send leaves the state alone: empty is not the same as
    absent (CLAUDE.md)."""
    rec = copy.deepcopy(dict(record or {}))
    c = curse_of(rec)
    if not c or c.get("row") != "requirement":
        return rec, []
    sub = _sub(c, "requirement") or {}
    fact = sub.get("fact")
    if fact not in (facts or {}):
        return rec, []
    met = bool(facts[fact]) == bool(sub.get("met_when", True))
    state = dict(c.get("state") or {})
    was_unmet = bool(state.get("unmet"))
    state.update({"unmet": not met, "day": int(day)})
    c = dict(c, state=state)
    rec["magic"] = dict(rec["magic"], curse=c)
    name = str(rec.get("name") or "item")
    known = bool((rec["magic"].get("known") or {}).get("curse"))
    said: list[str] = []
    if not met and not was_unmet:
        said.append(f"The magic in the {name} has gone quiet."
                    + (f" {describe(c)}" if known else ""))
    elif met and was_unmet:
        said.append(f"The magic in the {name} stirs again.")
    return rec, said


def describe(curse) -> str:
    """The curse in words, for the identify card. Never sent unless `known.curse` is true."""
    c = curse if isinstance(curse, dict) else {}
    if not c.get("row"):
        return ""
    det = c.get("detail") or {}
    top = next((r for r in rows() if r["id"] == c["row"]), {})
    words = str(top.get("words") or "")
    for name in ("intermittent", "dependent", "requirement", "drawback"):
        sub = _sub(c, name)
        if sub and sub.get("words"):
            words = str(sub["words"])
    sit = _sub(c, "dependent")
    phase = det.get("phase") or ""
    ctype = str(det.get("creature_type") or "").replace("_", " ")
    fill = {
        "situation": (str(sit.get("situation") or "") if sit else "")
        .replace("{creature_type_words}", f"{ctype} creatures" if ctype else "a creature")
        .replace("{phase}", phase),
        "dc": str(10 + int(c.get("cl") or 0)),
        "taller_words": "grows" if det.get("taller") else "shrinks",
    }
    for k, v in fill.items():
        words = words.replace("{" + k + "}", v)
    if c["row"] == "different":
        inst = det.get("instead") or {}
        pairs = []
        for was, now in (inst.get("properties") or {}).items():
            pairs.append(f"{_prop_name(now.get('id'))} where {_prop_name(was)} was meant")
        if inst.get("enhancement"):
            pairs.append(f"{_prop_name(inst['enhancement'].get('id'))} where its "
                         f"enhancement was meant")
        for was, now in (inst.get("powers") or {}).items():
            pairs.append(f"{_recipe_name(now)} where {_recipe_name(was)} was meant")
        if pairs:
            words += " It works as " + "; ".join(pairs) + "."
    return words


def _prop_name(pid) -> str:
    from . import effectspec

    prop = effectspec.property(str(pid or "")) or {}
    return str(prop.get("name") or str(pid or "").replace("-", " ")).lower()


def _recipe_name(rid) -> str:
    from . import magic_layer

    return str((magic_layer.recipe(str(rid or "")) or {}).get("name") or rid)


def tell(curse, item_name: str, *, known: bool) -> str:
    """The words for a moment the curse acts, for the narrator (law 3). Unknown, they say
    that something in the item is wrong and never what; known (or found at this very
    moment, when the caller passes known=True), they say what it is."""
    name = str(item_name or "item")
    if not known:
        return f"Something in the {name} is wrong."
    return f"The {name} is cursed. {describe(curse)}".strip()


__all__ = ["roll", "documents", "describe", "tell", "clings", "gutters", "noticed",
           "lift", "lift_dc", "settle_day", "curse_of", "table", "rows", "sub_table",
           "table_problems", "BadCurses", "SITUATION_FACTS", "REQUIREMENT_FACTS"]
