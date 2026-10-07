"""Alchemy formulae: the fixed, learnable table of what a mix can become (alchemy plan §10,
§11; contracts §5).

**A formula is a row, never secret per world** (owner, Q5.2). Minecraft dropped per-world
brewing as "not much fun" and Noita's per-seed recipes fell to the data files in about a
week (prior art §4, §7), so the table is fixed, and a world's reagents and spells feed it
through their essences. Two kinds of row:

- **Authored** (`content/rules/alchemy-formulae.json`): the 18 classics, each with the
  book's effect as its core (Q1.4: the book's numbers win), and the 44 shipped spell
  potions, whose ids, spell, spell level, caster level and effects are the potion file's
  own (`content/materials/alchemist-spell-potions.json`, owner Q10.2: keep them exactly);
  this file adds only what a formula needs on top — the essences that make it.
- **Derived**: one per corpus spell whose effects all execute (plan §11.2), read at load
  through the derivation table (`content/rules/alchemy-essences.json`) and never stored,
  exactly as `rules/spells.py` derives `range_value`. The table is a ratchet, not a list
  to keep: every spell whose narrative lines become typed becomes a formula with no
  change here. Authored rows win, by id and by spell.

**Formulae key on essences, never on materials** (Q4.2: "any reagent with the lightness
trait serves a potion of fly"). A **signature** is the product family plus the set of
essences present (plan §10.2). The owner's rulings bind:

- any spell may be a potion, personal range included (Q4.3, overruling the book's
  personal-range ban and its 3rd-level cap); the highest spell level an alchemist brews
  is max(1, floor(Alchemist level / 2)) (`spell_level_cap`);
- a harmful spell drunk takes its drinker as the target; it may ALSO go into a thrown
  flask with the struck creature as the target (open point 5, a house rule) — a derived
  row says which forms it yields (`families`, `delivers`);
- quality raises caster level only, and the book price follows caster level, with no
  second multiplier (open point 6) (`caster_level`, `potion_price`);
- the classics and the 44 are found by experiment; the rest come from writings, as
  planned (open point 4): a derived row is found by experiment only when its signature
  is unique within the alchemist's reach and no authored row holds it (`match`);
- a formula may be learned from a potion in hand, which is spent (open point 9)
  (`learn_route(..., "potion")`).

**One store.** What a character knows is `knowledge.learn_formula` under
"formula:<id>" in `Actor.herb_known` (contracts §4); this module keeps no list of its own.

**No model authors a number.** Book numbers are typed by hand in the JSON; caster levels
come from the class documents (`rules/casting.py`); prices and times from the book's
formulae below. Validators refuse a formula row with the fix named (`formula_problems`).
"""
from __future__ import annotations

import builtins
import copy
import json
import math
import re
from pathlib import Path
from types import SimpleNamespace

from . import effectspec

# The product families (plan §12.1). The family decides delivery; the VESSEL decides the
# family (owner Q7.3), through its vessel working trait. A glass vial is drunk or poured on,
# so a vial serves a potion and an oil, and the formula chosen says which.
FAMILIES: tuple[str, ...] = ("potion", "oil", "splash", "cloud", "tool")
VESSEL_FAMILIES: dict[str, tuple[str, ...]] = {
    "drinkable": ("potion", "oil"),
    "shatters": ("splash",),
    "bursts": ("splash",),
    "struck": ("cloud",),
    "stick": ("tool",),
}
# Who a spell formula's spell takes as its target, per form (plan §11.3; owner, open point
# 5). The book: "The drinker of a potion is both the effective target and the caster".
DELIVERS: dict[str, str] = {"potion": "the drinker", "oil": "what it coats",
                            "splash": "the creature it strikes"}

SOUND = 1                 # the quality ladder's index of Sound (herbal-quality.json)
KINDS = ("classic", "spell")

# The rarity a level reaches (plan §4.1, owner Q6.1): common and uncommon at 1, rare and
# exotic at 2, legendary at 3. As tier ranks (`worldclass.tier_rank`: common 1 .. legendary
# 5), so the endless levels keep the legendary ceiling.
RARITY_BY_LEVEL: dict[int, int] = {1: 2, 2: 4, 3: 5}
# A spell potion's rarity, by spell level: the shipped 44's own convention (1st uncommon,
# 2nd rare, 3rd exotic), extended. It matters little — the level gate (2 x spell level)
# opens legendary before 2nd-level spells — and it is what a shop's settlement band reads.
TIER_BY_SPELL_LEVEL: tuple[str, ...] = ("common", "uncommon", "rare", "exotic")

# The CRB's spellbook writing costs (Magic, Arcane Magical Writings, checked 2026-10-06 on
# legacy.aonprd.com/coreRulebook/magic.html): 0-level 5 gp, then spell level squared x 10.
# The APG alchemist "can also add formulae to his book just like a wizard adds spells to
# his spellbook, using the same costs, pages, and time requirements" (plan §10.4, §22).
COPY_DC_BASE = 15                     # "Spellcraft check (DC 15 + spell's level)"
COPY_RETRY_MINUTES = 7 * 24 * 60      # "cannot attempt ... again until one week has passed"
STUDY_MINUTES = 60                    # "1 hour studying the spell"

# A paladin's or ranger's "caster level is equal to his paladin level - 3" (CRB, the class
# entries). `casting.caster_level` reads class level for every caster; a potion's MINIMUM
# caster level is a book number (plan §11.3: "never lower than the minimum level needed to
# cast the needed spell"), so the conversion is made here, for that question only.
CL_OFFSET_BY_PROGRESSION: dict[str, int] = {"four_level": 3}

# How a formula came to be known, in the words the Formulary prints ("found by experiment,
# day 14"). Any other `how` is kept as given.
HOW_WORDS: dict[str, str] = {
    "experiment": "found by experiment",
    "scroll": "copied from a scroll",
    "spellbook": "copied from a spellbook",
    "teacher": "taught",
    "companion": "taught by a companion",
    "formulary": "read in a formulary",
    "potion": "learned from a potion",
    "start": "known from the start",
    "migration": "made before the new bench",
}
# The writing routes (plan §10.4). `check` is an Alchemist check against DC 15 + spell
# level; `spell_only` routes carry a spell and so teach spell formulae only.
LEARN_ROUTES: dict[str, dict] = {
    "scroll": {"check": True, "spell_only": True, "spends": "on_success", "writes": True},
    "spellbook": {"check": True, "spell_only": True, "spends": "never", "writes": True},
    "potion": {"check": True, "spell_only": True, "spends": "always", "writes": False},
    "companion": {"check": False, "spell_only": True, "spends": "never", "writes": False},
    "teacher": {"check": False, "spell_only": False, "spends": "never", "writes": False},
    "formulary": {"check": False, "spell_only": False, "spends": "never", "writes": False},
}


class BadFormulae(ValueError):
    """Shipped formula content that does not validate. Shipped content is fixed and a test
    pins it clean, so this is a build defect, raised at load rather than met in play."""


# --- the rule files -------------------------------------------------------------------------

def _content(*parts: str) -> Path:
    # Never `__file__`: it lies inside a frozen bundle (CLAUDE.md). BASE_DIR is where the
    # install keeps its content, frozen or not.
    from django.conf import settings

    return Path(settings.BASE_DIR).joinpath("content", *parts)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


ESSENCES_PATH = ("rules", "alchemy-essences.json")
FORMULAE_PATH = ("rules", "alchemy-formulae.json")
POTIONS_PATH = ("materials", "alchemist-spell-potions.json")


def essence_table_problems(table: dict) -> list[str]:
    """Everything wrong with the derivation table, the fix named. Every essence it names
    must be one of `effectspec.ESSENCES` (lane B's vocabulary, the owner's 18): a row
    naming any other would derive an essence no material can carry, and a formula keyed
    on it could never be made."""
    out: list[str] = []
    known = set(effectspec.ESSENCES)

    def check(where: str, value) -> None:
        if str(value) not in known:
            out.append(f"{where}: '{value}' is not an essence. One of: "
                       f"{', '.join(effectspec.ESSENCES)}.")

    if not isinstance(table.get("max_per_spell"), int) or table["max_per_spell"] < 1:
        out.append("max_per_spell is a whole number, 1 or more (2 as shipped).")
    weights = table.get("weights") or {}
    for key in ("descriptor", "subschool", "effect", "school"):
        if not isinstance(weights.get(key), (int, float)) or weights.get(key) <= 0:
            out.append(f"weights.{key} is a positive number.")
    for section in ("descriptors", "subschools", "schools", "damage_types", "effect_types"):
        rows = table.get(section)
        if not isinstance(rows, dict):
            out.append(f"{section} is an object of word to essence.")
            continue
        for word, essence in rows.items():
            check(f"{section}.{word}", essence)
    for etype, rows in (table.get("targets") or {}).items():
        if not isinstance(rows, dict):
            out.append(f"targets.{etype} is an object of target to essence.")
            continue
        for word, essence in rows.items():
            check(f"targets.{etype}.{word}", essence)
    for i, pair in enumerate(table.get("condition_tags") or ()):
        if not (isinstance(pair, list) and len(pair) == 2):
            out.append(f"condition_tags[{i}] is a pair: [\"state.held\", \"binding\"].")
            continue
        check(f"condition_tags[{i}]", pair[1])
    return out


_TABLE: dict = {}


def essence_table() -> dict:
    """The derivation table, validated. A problem in the shipped file raises."""
    path = _content(*ESSENCES_PATH)
    key = _mtime(path)
    if _TABLE.get("key") != key:
        table = _read_json(path)
        problems = essence_table_problems(table)
        if problems:
            raise BadFormulae("alchemy-essences.json is not valid:\n  " + "\n  ".join(problems))
        _TABLE.clear()
        _TABLE.update({"key": key, "table": table})
    return _TABLE["table"]


# --- a spell's essences (the derivation) ----------------------------------------------------

def _walk(specs):
    """Every effect document, nested branches included (a save gate's failure branch is
    where most of a harmful spell's work is)."""
    for spec in specs or ():
        if not isinstance(spec, dict):
            continue
        yield spec
        for key in ("on_failure", "on_success", "effects", "options", "on_enter"):
            yield from _walk(spec.get(key))


def _condition_essence(key: str, table: dict) -> str | None:
    from . import states

    tags = states.tags_for(str(key or "").strip().lower())
    for prefix, essence in table.get("condition_tags") or ():
        if any(states.matches(t, prefix) for t in tags):
            return essence
    return None


def effect_essence(spec: dict, table: dict | None = None) -> str | None:
    """The essence one effect document carries, or None when it carries none the table
    names (a bare save gate, a permission with no tag)."""
    table = table or essence_table()
    t = str(spec.get("type") or "")
    target = str(spec.get("target") or "").strip().lower()
    targets = (table.get("targets") or {}).get(t) or {}
    if t == "damage":
        return (table.get("damage_types") or {}).get(
            str(spec.get("damage_type") or "untyped").lower())
    if t == "apply_condition":
        return _condition_essence(target, table)
    if t == "manifest":
        return targets.get(str(spec.get("terrain") or "obscuring"))
    if t == "permission":
        return targets.get(str(spec.get("tag") or ""))
    if targets:
        return targets.get(target) or targets.get("*")
    return (table.get("effect_types") or {}).get(t)


def spell_essences(spell, table: dict | None = None) -> list[str]:
    """A spell's essences, strongest first, at most `max_per_spell` (plan §5.3).

    Votes, weighted by the table: each descriptor, the subschool, each effect document
    once, and the school. The highest totals are kept; a tie goes to the earlier source
    (descriptor before subschool before effect before school) and then to the vocabulary's
    own order, so the answer never depends on dict order."""
    table = table or essence_table()
    w = table.get("weights") or {}
    order = list(effectspec.ESSENCES)
    score: dict[str, float] = {}
    first: dict[str, int] = {}

    def vote(essence, weight, rank) -> None:
        if not essence:
            return
        score[essence] = score.get(essence, 0) + weight
        first[essence] = min(first.get(essence, 9), rank)

    for d in getattr(spell, "descriptors", None) or ():
        vote((table.get("descriptors") or {}).get(str(d).lower()), w.get("descriptor", 3), 0)
    for sub in re.split(r"\s*,\s*", str(getattr(spell, "subschool", "") or "").lower()):
        if sub:
            vote((table.get("subschools") or {}).get(sub), w.get("subschool", 2), 1)
    for spec in _walk(getattr(spell, "effects", None) or ()):
        vote(effect_essence(spec, table), w.get("effect", 1), 2)
    vote((table.get("schools") or {}).get(str(getattr(spell, "school", "") or "").lower()),
         w.get("school", 1), 3)
    ranked = sorted(score, key=lambda e: (-score[e], first[e], order.index(e)))
    # The strongest is always kept; another only with `min_secondary` votes behind it.
    # Measured 2026-10-06 without the floor: the school's lone vote became the second
    # essence of nearly every spell (every conjuration cure came out vigour + change),
    # so the second essence said nothing about the spell and 59 formulae shared
    # potion of change + might.
    floor = float(table.get("min_secondary") or 0)
    keep = ranked[:1] + [e for e in ranked[1:] if score[e] >= floor]
    return keep[:int(table.get("max_per_spell") or 2)]


# --- caster level, price and time (plan §11) ------------------------------------------------

def spell_level_cap(alchemist_level: int) -> int:
    """The highest spell level an alchemist can bottle: max(1, floor(level / 2)) — the
    owner's own rule (Q4.3), carried by the endless levels to 9th at Alchemist 18."""
    return max(1, int(alchemist_level or 0) // 2)


def level_for_spell_level(spell_level: int) -> int:
    """The Alchemist level that first reaches a spell level under `spell_level_cap`: 1 for
    0- and 1st-level spells (the owner's minimum of 1), else twice the spell level.
    Contracts §5 wrote the derived row's level as max(1, 2n), which would have asked
    Alchemist 2 for a 1st-level potion that the owner's cap opens at 1 (Q6.1)."""
    n = int(spell_level or 0)
    return 1 if n <= 1 else 2 * n


def _spell(spell):
    from . import spells

    if spell is None:
        return None
    if isinstance(spell, str):
        try:
            return spells.get(spell)
        except KeyError:
            return None
    return spell


def _first_class_level(cls: str, spell_level: int) -> int | None:
    from . import casting

    shim = SimpleNamespace(class_data={}, char_class=cls, level=1)
    for lvl in range(1, 21):
        if casting.highest_spell_level_at(shim, lvl) >= spell_level:
            return lvl
    return None


def min_caster_level(spell, spell_level: int | None = None) -> int:
    """The book's floor: "never lower than the minimum level needed to cast the needed
    spell" (CRB, magic item creation). Read from the class documents (`casting.CASTERS`):
    the lowest class level at which a class whose list holds the spell AT this spell level
    casts that level, converted to caster level. Wizard, cleric and druid give CL 1, 3, 5
    for 1st to 3rd, the book's potion table (50, 300, 750 gp). A list with no class
    document here (summoner, alchemist, the occult classes) falls back to 2 x spell level
    - 1, and CL 1 for a 0-level spell (plan §11.3, proposed)."""
    from . import casting

    sp = _spell(spell)
    if sp is None:
        n = int(spell_level or 0)
        return 1 if n <= 0 else 2 * n - 1
    n = int(sp.min_level or 0) if spell_level is None else int(spell_level)
    best: int | None = None
    for cls, data in casting.CASTERS.items():
        if (sp.lists or {}).get(str(data.get("list") or "")) != n:
            continue
        lvl = _first_class_level(cls, n)
        if lvl is None:
            continue
        cl = lvl - CL_OFFSET_BY_PROGRESSION.get(str(data.get("progression") or ""), 0)
        best = cl if best is None else min(best, cl)
    if best is None:
        best = 1 if n <= 0 else 2 * n - 1
    return max(1, best)


def caster_level(spell, quality_index: int, *, spell_level: int | None = None) -> int:
    """A spell potion's caster level: the book minimum, plus one for each quality tier
    above Sound (owner Q6.4). Crude stays at the minimum — the book allows nothing lower.
    An authored potion's own caster level is its minimum (Q10.2: kept exactly)."""
    sp = _spell(spell)
    row = for_spell(sp.id if sp is not None else str(spell or "")) if sp is not None else None
    if row is not None and row.get("authored") and row.get("caster_level") \
            and (spell_level is None or spell_level == row.get("spell_level")):
        base = int(row["caster_level"])
    else:
        if spell_level is None and row is not None:
            spell_level = row.get("spell_level")
        base = min_caster_level(sp, spell_level)
    return base + max(0, int(quality_index or 0) - SOUND)


def potion_price(spell_level: int, caster_level: int) -> float:
    """50 gp x spell level x caster level, a 0-level spell counting as half (CRB, Potions).
    Quality reaches it only through caster level (owner, open point 6): no second
    multiplier, so a Crude potion — made at the minimum caster level — prices as Sound."""
    level = 0.5 if int(spell_level or 0) <= 0 else int(spell_level)
    return float(50 * level * max(1, int(caster_level or 1)))


def brew_minutes(price_gp: float) -> int:
    """How long a spell potion sets (In progress) after it is bottled.

    The CRB gives three answers. The Brew Potion feat: "2 hours if its base price is 250 gp
    or less, otherwise ... 1 day for each 1,000 gp in its base price". Magic Item Creation:
    "8 hours of work per 1,000 gp ... (or fraction thereof), with a minimum of at least 8
    hours. Potions and scrolls are an exception ... as little as 2 hours ... (if their base
    price is 250 gp or less)". Creating Potions: "Brewing a potion requires 1 day". No Paizo
    FAQ settling them was found (prior art §8, searched again 2026-10-06: forum threads
    only). The FEAT is used, as plan §11.4 and contracts §5 say: it is the later rule and
    the one the alchemist class follows. "Each 1,000 gp" is counted as started thousands,
    the creation section's "or fraction thereof", so a 750 gp potion of haste sets one day,
    not three quarters of one. A day is a calendar day of game time: the potion sits in
    In progress while the alchemist adventures, which is what the countdown shows."""
    price = float(price_gp or 0)
    if price <= 250:
        return 120
    return 1440 * math.ceil(price / 1000.0)


def copy_cost_gp(spell_level: int) -> int:
    n = int(spell_level or 0)
    return 5 if n <= 0 else 10 * n * n


def copy_minutes(spell_level: int) -> int:
    """1 hour studying, then 1 hour per spell level to write (a cantrip takes 30 minutes)."""
    n = int(spell_level or 0)
    return STUDY_MINUTES + (30 if n <= 0 else 60 * n)


# --- the table ------------------------------------------------------------------------------

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_OBJECT_TARGET = re.compile(r"\b(weapons?|objects?|armou?r|shields?|projectiles?|ammunition)\b",
                            re.I)
_CREATURE_TARGET = re.compile(r"\b(creatures?|you|humanoids?|animals?|allies|ally)\b", re.I)


def _is_oil(spell) -> bool:
    """A spell whose target is an object or a weapon is an oil (plan §11.3, read from the
    spell's printed targets line as the 4 shipped oils already were): "oils are applied
    externally rather than imbibed" (CRB, Potions). A line that names a creature at all
    stays a potion — invisibility's "you or a creature or object" is drunk."""
    text = str(getattr(spell, "targets", "") or "")
    return bool(_OBJECT_TARGET.search(text)) and not _CREATURE_TARGET.search(text)


def _harmful(spell, cl: int) -> bool:
    """Whether the spell can harm whoever it lands on, by the app's one definition
    (`attitude.harmful_spell`: damage, or a harmful condition on a failed save)."""
    from . import attitude

    try:
        return attitude.harmful_spell(spell, cl)
    except Exception:  # noqa: BLE001 - a spell the planner cannot read harms nobody we can name
        return False


def _families_for(primary: str, harmful: bool) -> list[str]:
    fams = [primary]
    if harmful and primary == "potion":
        fams.append("splash")
    return fams


def _tier_for_spell_level(n: int) -> str:
    return TIER_BY_SPELL_LEVEL[n] if 0 <= n < len(TIER_BY_SPELL_LEVEL) else "legendary"


def _executable_all(specs) -> bool:
    specs = list(specs or ())
    # builtins.all: this module's own `all` (the contract's name) shadows it.
    return bool(specs) and builtins.all(effectspec.executable(s) for s in _walk(specs))


def _spell_row(sp, *, spell_level: int, caster: int, primary: str, requires: dict,
               fid: str, name: str, tier: str, authored: bool, core=None) -> dict:
    harmful = _harmful(sp, caster) if sp is not None else False
    families = _families_for(primary, harmful)
    price = potion_price(spell_level, caster)
    return {
        "id": fid, "name": name, "kind": "spell", "book": True,
        "authored": authored, "derived": not authored,
        "spell": sp.id if sp is not None else None,
        "family": primary, "families": families,
        "delivers": {f: DELIVERS[f] for f in families if f in DELIVERS},
        "harmful": harmful,
        "requires": {"essences": dict(requires)},
        "spell_level": spell_level, "caster_level": caster,
        "level": level_for_spell_level(spell_level),
        "craft_dc": 5 + caster,
        "price_gp": price, "brew_minutes": brew_minutes(price), "minutes": 10,
        "tier": tier,
        "core": copy.deepcopy(core) if core is not None else None,
        "splash": None, "range_increment_ft": 10 if "splash" in families else None,
        "source": ("CRB, Potions; the owner's rule (Q4.3)" if not authored
                   else "the shipped spell potion"),
    }


def _derived_rows(authored_spells: set[str], table: dict) -> dict[str, dict]:
    from . import spells

    out: dict[str, dict] = {}
    for sp in spells.all_spells().values():
        if sp.id in authored_spells or sp.min_level is None:
            continue
        if not _executable_all(sp.effects):
            continue
        essences = spell_essences(sp, table)
        if not essences:
            continue
        n = int(sp.min_level)
        cl = min_caster_level(sp, n)
        primary = "oil" if _is_oil(sp) else "potion"
        fid = f"{primary}-of-{sp.id}"
        if fid in out:
            continue
        out[fid] = _spell_row(sp, spell_level=n, caster=cl, primary=primary,
                              requires={e: 1 for e in essences}, fid=fid,
                              name=f"{primary.title()} of {sp.name}",
                              tier=_tier_for_spell_level(n), authored=False)
    return out


def _normalise_classic(raw: dict) -> dict:
    row = copy.deepcopy(raw)
    row.setdefault("kind", "classic")
    row.setdefault("book", False)
    row.setdefault("families", [row.get("family")])
    row.setdefault("splash", None)
    row.setdefault("range_increment_ft", None)
    row.setdefault("area", None)
    row.setdefault("minutes", 10)
    row.setdefault("level", 1)
    row.setdefault("tier", "common")
    row.setdefault("spell", None)
    row.setdefault("spell_level", None)
    row.setdefault("caster_level", None)
    row.setdefault("harmful", False)
    row.setdefault("delivers", {})
    row["authored"], row["derived"] = True, False
    return row


def _authored_spell_rows(raw_rows: list[dict], potions: dict[str, dict]) -> tuple[dict, list]:
    """The 44 shipped potions as formula rows. Everything but the essences is the potion
    file's own (Q10.2: ids, holds_spell and caster level kept exactly)."""
    out: dict[str, dict] = {}
    problems: list[str] = []
    for raw in raw_rows:
        pid = str(raw.get("id") or "")
        pot = potions.get(pid)
        if pot is None:
            problems.append(f"potions.{pid}: no shipped spell potion has this id "
                            f"(content/materials/alchemist-spell-potions.json).")
            continue
        sp = _spell(str(pot.get("spell") or ""))
        primary = "oil" if "coat" in (pot.get("how") or ()) else "potion"
        row = _spell_row(sp, spell_level=int(pot.get("spell_level") or 0),
                         caster=int(pot.get("caster_level") or 1), primary=primary,
                         requires=(raw.get("requires") or {}).get("essences") or {},
                         fid=pid, name=str(pot.get("name") or pid),
                         tier=str(pot.get("tier") or "uncommon"), authored=True,
                         core=pot.get("effects") or [])
        row["spell"] = str(pot.get("spell") or "") or None
        row["source"] = "the shipped spell potion (alchemist-spell-potions.json)"
        out[pid] = row
    return out, problems


_ROWS: dict = {}


def _key() -> tuple:
    from . import spells

    return (_mtime(_content(*ESSENCES_PATH)), _mtime(_content(*FORMULAE_PATH)),
            _mtime(_content(*POTIONS_PATH)), id(spells.all_spells()))


def _rows() -> dict[str, dict]:
    """Every formula by id (authored, then derived), validated. Cached on the files'
    mtimes and the spell corpus's identity, so a corrected file or a homebrew spell is
    seen on the next call; never on a stamp alone."""
    key = _key()
    if _ROWS.get("key") != key:
        table = essence_table()
        raw = _read_json(_content(*FORMULAE_PATH))
        potions = {str(p.get("id")): p for p in
                   (_read_json(_content(*POTIONS_PATH)).get("potions") or ())}
        classics = {str(r.get("id")): _normalise_classic(r) for r in raw.get("classics") or ()}
        spell_rows, problems = _authored_spell_rows(raw.get("potions") or [], potions)
        authored = dict(classics)
        authored.update(spell_rows)
        problems += table_problems(authored, awaiting=raw.get("awaiting") or {})
        if problems:
            raise BadFormulae("alchemy-formulae.json is not valid:\n  " + "\n  ".join(problems))
        authored_spells = {r["spell"] for r in spell_rows.values() if r.get("spell")}
        rows = dict(authored)
        for fid, row in _derived_rows(authored_spells, table).items():
            rows.setdefault(fid, row)
        _mark(rows, raw.get("awaiting") or {})
        _ROWS.clear()
        _ROWS.update({"key": key, "rows": rows, "starting": list(raw.get("starting") or ()),
                      "awaiting": dict(raw.get("awaiting") or {})})
    return _ROWS["rows"]


def refresh() -> None:
    _ROWS.clear()
    _TABLE.clear()


# --- validation -----------------------------------------------------------------------------

def _with_awaited(spec: dict, awaiting: dict) -> dict:
    """A copy with each awaited condition (one lane C adds this wave, `awaiting` in the
    formula file) swapped for one the vocabulary already has, so `validate` checks
    everything else about the document."""
    doc = copy.deepcopy(spec)
    for s in _walk([doc]):
        if s.get("type") == "apply_condition" and str(s.get("target")) in awaiting:
            s["target"] = "entangled"
    return doc


def core_problems(core, where: str, *, awaiting: dict | None = None) -> list[str]:
    """A core must be complete typed documents: valid, and never narrative (the
    cross-craft rule — "no narrative effects"). A condition named in `awaiting` is
    allowed: it is promised by the engine lane this wave and named in `waiting`."""
    awaiting = awaiting or {}
    out: list[str] = []
    if not isinstance(core, list) or not core:
        return [f"{where}: a formula's core is a list of effect documents (the book's "
                f"effect, typed). It is empty."]
    for i, spec in enumerate(core):
        path = f"{where}[{i}]"
        if not isinstance(spec, dict):
            out.append(f"{path}: an effect document is an object.")
            continue
        if any(str(s.get("type")) == "narrative" for s in _walk([spec])):
            out.append(f"{path}: narrative. A core is typed effects the engine runs; write "
                       f"it as one, or leave the line out and say so in a note.")
            continue
        out += effectspec.validate(_with_awaited(spec, awaiting), path)
    return out


def formula_problems(row: dict, *, awaiting: dict | None = None) -> list[str]:
    """Everything wrong with one authored formula row, with the fix named."""
    fid = str(row.get("id") or "")
    where = f"formula {fid or '(no id)'}"
    out: list[str] = []
    if not _SLUG.match(fid):
        out.append(f"{where}: the id is a lower-case slug, like alchemists-fire.")
    if row.get("kind") not in KINDS:
        out.append(f"{where}: kind is one of {', '.join(KINDS)}.")
    fams = row.get("families") or []
    if row.get("family") not in FAMILIES:
        out.append(f"{where}: family is one of {', '.join(FAMILIES)}.")
    if not fams or any(f not in FAMILIES for f in fams) or row.get("family") not in fams:
        out.append(f"{where}: families lists the forms it can be bottled as, its family "
                   f"first; each one of {', '.join(FAMILIES)}.")
    req = ((row.get("requires") or {}).get("essences"))
    if not isinstance(req, dict) or not req:
        out.append(f"{where}: requires.essences names at least one essence with its grade: "
                   f"{{\"fire\": 1}}. A formula keyed on nothing would match every mix.")
    else:
        for e, g in req.items():
            if e not in effectspec.ESSENCES:
                out.append(f"{where}: requires names '{e}', which is not an essence. One "
                           f"of: {', '.join(effectspec.ESSENCES)}.")
            if not isinstance(g, int) or isinstance(g, bool) or g < 1:
                out.append(f"{where}: the grade for {e} is a whole number, 1 or more.")
    if row.get("tier") not in effectspec.TIERS:
        out.append(f"{where}: tier is one of {', '.join(effectspec.TIERS)}.")
    if not isinstance(row.get("level"), int) or row["level"] < 1:
        out.append(f"{where}: level is the Alchemist level it needs, 1 or more.")
    if row.get("kind") == "classic":
        out += core_problems(row.get("core"), f"{where}.core", awaiting=awaiting)
        if not isinstance(row.get("craft_dc"), int):
            out.append(f"{where}: craft_dc is the book's Craft (alchemy) DC.")
        if not isinstance(row.get("price_gp"), (int, float)) or row["price_gp"] <= 0:
            out.append(f"{where}: price_gp is the book's price in gold.")
        if not row.get("source"):
            out.append(f"{where}: source names where the numbers come from (the book page, "
                       f"or 'house' for a number the owner reviews).")
        splash = row.get("splash")
        if splash is not None and not (isinstance(splash, dict) and splash.get("damage_type")
                                       and isinstance(splash.get("amount"), int)):
            out.append(f"{where}: splash is {{\"amount\": 1, \"damage_type\": \"fire\"}}.")
    elif row.get("kind") == "spell":
        if not row.get("spell") or _spell(row.get("spell")) is None:
            out.append(f"{where}: its spell '{row.get('spell')}' is not in the corpus.")
    return out


def table_problems(rows: dict[str, dict], *, awaiting: dict | None = None) -> list[str]:
    """Every authored row's problems, and the one problem no row can see alone: two
    authored formulae with one signature. The classics and the 44 are found by experiment
    (owner, open point 4), and experiment can only tell formulae apart by signature."""
    out: list[str] = []
    for row in rows.values():
        out += formula_problems(row, awaiting=awaiting)
    seen: dict[tuple, str] = {}
    for fid, row in rows.items():
        for sig in row_signatures(row):
            if sig in seen:
                out.append(f"formula {fid}: its signature {_sig_words(sig)} is also "
                           f"{seen[sig]}'s. Authored formulae need one each, or experiment "
                           f"cannot tell them apart: change one's essences.")
            else:
                seen[sig] = fid
    return out


def _waiting_reason(spec: dict, awaiting: dict) -> str | None:
    t = str(spec.get("type") or "")
    if t == "apply_condition" and str(spec.get("target")) in awaiting:
        return f"{spec.get('target')}: {awaiting[str(spec.get('target'))]}"
    if effectspec.executable(spec):
        return None
    if t in effectspec.AWAITING_READER:
        return f"{t}: {effectspec.AWAITING_READER[t]}"
    per = effectspec.TARGETS_AWAITING_READER.get(t) or {}
    if str(spec.get("target") or "") in per:
        return f"{t} {spec.get('target')}: {per[str(spec.get('target'))]}"
    if t == "narrative":
        return "written as words, not yet typed"
    found = effectspec.find(t)
    return f"{t}: {found[1].blocked if found else 'not an effect type'}"


def _mark(rows: dict[str, dict], awaiting: dict) -> None:
    """Stamp what each row can do today. `brewable`: its core is typed (no narrative), so
    the bench may make it — an authored potion still carrying prose is not, and old stock
    of it stays usable (plan §11.2). `waiting`: what in it the engine does not run yet,
    each with the reader that will (lane C's, this wave), so nothing pretends."""
    authored_sigs = {sig for r in rows.values() if r["authored"] for sig in row_signatures(r)}
    for row in rows.values():
        core = row.get("core")
        if core is None and row.get("spell"):
            core = (_spell(row["spell"]).effects if _spell(row["spell"]) else [])
        reasons = []
        for spec in _walk(core or ()):
            why = _waiting_reason(spec, awaiting)
            if why and why not in reasons:
                reasons.append(why)
        row["waiting"] = reasons
        row["brewable"] = not any(str(s.get("type")) == "narrative" for s in _walk(core or ()))
        row["signatures"] = [list(s) for s in row_signatures(row)]
        row["shadowed"] = [] if row["authored"] else [
            s[0] for s in row_signatures(row) if s in authored_sigs]


# --- reading the table ----------------------------------------------------------------------

def all() -> dict[str, dict]:  # noqa: A001 - the contract's name
    """Every formula by id: authored rows and derived spell rows, authored winning."""
    return {k: copy.deepcopy(v) for k, v in _rows().items()}


def get(fid: str) -> dict | None:
    row = _rows().get(str(fid or "").strip().lower())
    return copy.deepcopy(row) if row is not None else None


def for_spell(spell_id: str) -> dict | None:
    """The formula that bottles this spell: the authored potion when there is one, else
    the derived row. None for a spell that is not (yet) fully typed."""
    sid = str(spell_id or "").strip().lower()
    best = None
    for row in _rows().values():
        if row.get("spell") == sid:
            if row["authored"]:
                return copy.deepcopy(row)
            best = best or row
    return copy.deepcopy(best) if best is not None else None


def starting() -> list[str]:
    """The four book classics every alchemist knows from the start (owner Q5.4)."""
    _rows()
    return list(_ROWS.get("starting") or ())


def core(fid: str, caster_level: int | None = None) -> list[dict]:
    """A formula's core documents. A classic's is its book effect; a spell row's is the
    spell's own documents at the caster level (`spells.effects_at`), so a potion and a
    cast of the same spell resolve through the same documents (plan §11.3) — an authored
    potion uses its own."""
    row = _rows().get(str(fid or ""))
    if row is None:
        return []
    if row.get("core") is not None:
        return copy.deepcopy(row["core"])
    from . import spells

    sp = _spell(row.get("spell"))
    if sp is None:
        return []
    return spells.effects_at(sp, int(caster_level or row.get("caster_level") or 1))


def signature(family: str | None, essences) -> tuple:
    """(family, sorted essences): what experiment can tell apart (plan §10.2)."""
    return (str(family or ""), tuple(sorted({str(e) for e in essences or ()})))


def row_signatures(row: dict) -> list[tuple]:
    req = ((row.get("requires") or {}).get("essences")) or {}
    return [signature(f, req) for f in (row.get("families") or [row.get("family")])]


def _sig_words(sig: tuple) -> str:
    return f"{sig[0]} of {' + '.join(sig[1]) or 'nothing'}"


# --- the actor ------------------------------------------------------------------------------

TRACK_ID = "alchemist"


def alchemist_level(actor) -> int:
    """The character's Alchemist level, 1 when they have not begun (the class levels by
    doing). Read without beginning the track: asking must not change the save."""
    if actor is None:
        return 1
    if isinstance(actor, int):
        return max(1, actor)
    prog = (getattr(actor, "world_classes", None) or {}).get(TRACK_ID)
    try:
        return max(1, int(getattr(prog, "level", 1) or 1))
    except (TypeError, ValueError):
        return 1


def rarity_ceiling(level: int) -> int:
    return RARITY_BY_LEVEL.get(max(1, min(int(level or 1), 3)), 5)


def reach_problems(row: dict, level: int) -> list[str]:
    """Why a formula is beyond this Alchemist level, in words; [] when it is within reach.
    Within reach (plan §10.3): its level, its spell level under the owner's cap, and its
    rarity under the level's ceiling."""
    from .worldclass import tier_rank

    out = []
    if int(row.get("level") or 1) > level:
        out.append(f"It needs Alchemist {row['level']}; you are {level}.")
    sl = row.get("spell_level")
    if sl is not None and int(sl) > spell_level_cap(level):
        out.append(f"A spell of level {sl} needs Alchemist {level_for_spell_level(int(sl))}: "
                   f"at {level} you bottle spells up to level {spell_level_cap(level)}.")
    if tier_rank(str(row.get("tier") or "common")) > rarity_ceiling(level):
        out.append(f"It is {row.get('tier')} work, beyond Alchemist {level}.")
    return out


def within_reach(row: dict, level: int) -> bool:
    return not reach_problems(row, level)


def _reachable(level: int) -> list[dict]:
    return [r for r in _rows().values() if r["brewable"] and within_reach(r, level)]


def known(actor) -> list[str]:
    """Every formula the character knows that the table still has, sorted."""
    from . import knowledge

    rows = _rows()
    return [fid for fid in knowledge.known_formulae(actor) if fid in rows]


def knows(actor, fid: str) -> bool:
    from . import knowledge

    return knowledge.knows_formula(actor, fid)


def how_words(how: str, clock: int | None = None) -> str:
    from . import knowledge

    words = HOW_WORDS.get(str(how or ""), str(how or "").strip() or "learned")
    return f"{words}, day {knowledge.day_of(clock)}" if clock is not None else words


def learn(actor, fid: str, how: str, *, clock: int | None = None) -> bool:
    """Write a formula into the character's formulary, and how ("found by experiment, day
    14"). True when it was new — the bench's cue to pay the +3 for a first formula
    written (plan §4.4). An id the table does not have is refused (False): the Formulary
    must never list a formula nothing can make."""
    from . import knowledge

    fid = str(fid or "").strip().lower()
    if fid not in _rows():
        return False
    return knowledge.learn_formula(actor, fid, how_words(how, clock))


def grant_starting(actor, *, clock: int | None = None) -> list[str]:
    """Teach the four classics (owner Q5.4). Returns the ids that were new."""
    return [fid for fid in starting() if learn(actor, fid, "start", clock=clock)]


# --- the mix --------------------------------------------------------------------------------

def mix_grades(mix: dict | None) -> dict[str, int]:
    """Each essence the mix's benefits carry, at the grade of its strongest carrier.

    The strongest, not the sum: same-named traits have already merged and added their
    grades at the bench (plan §6.2, lane F), so a sum here would count a fire-damage trait
    and a fire-resistance trait as fire 2 — a second road to grade that skips the merge.
    Drawbacks carry essences too but do not decide what a mix IS: they travel with it
    (plan §6.3) and Filter strips them; keying a formula on them would make every
    unfiltered mix unmatchable."""
    out: dict[str, int] = {}
    for t in (mix or {}).get("traits") or ():
        e = str((t or {}).get("essence") or "")
        if not e:
            continue
        try:
            g = int(t.get("grade") or 1)
        except (TypeError, ValueError):
            g = 1
        out[e] = max(out.get(e, 0), g)
    return out


def vessel_families(vessel) -> tuple[str, ...]:
    """The families a vessel bottles (owner Q7.3: the vessel decides). A family's own name
    stands for any vessel of it — for a preview before a vessel is chosen, and for tests.
    A vessel is read through the one door (`materials.alchemy_doc`) for its vessel
    working traits (lane D's data pass gives them)."""
    vid = str(vessel or "").strip().lower()
    if not vid:
        return ()
    if vid in FAMILIES:
        return (vid,)
    from . import materials

    doc = materials.alchemy_doc(vid) or {}
    out: list[str] = []
    for w in doc.get("working") or ():
        trait = str((w or {}).get("trait") if isinstance(w, dict) else w)
        for fam in VESSEL_FAMILIES.get(trait, ()):
            if fam not in out:
                out.append(fam)
    return tuple(out)


def _vessel_name(vessel) -> str:
    from . import materials

    vid = str(vessel or "")
    if vid in FAMILIES:
        return f"a {vid} vessel"
    doc = materials.alchemy_doc(vid) or {}
    return str(doc.get("name") or vid.replace("-", " ")).lower()


def _missing(row: dict, grades: dict[str, int]) -> list[str]:
    out = []
    for e, g in (((row.get("requires") or {}).get("essences")) or {}).items():
        have = grades.get(e, 0)
        if have <= 0:
            out.append(f"needs {e}; nothing in the mix carries it")
        elif have < g:
            out.append(f"needs {e} at grade {g}; you have {have}")
    return out


def _form(row: dict, fams: tuple[str, ...]) -> str | None:
    if not fams:
        return row.get("family")
    for f in row.get("families") or [row.get("family")]:
        if f in fams:
            return f
    return None


def match(actor, mix: dict, vessel_id: str | None, formula_id: str | None = None,
          aim: str | None = None) -> dict:
    """What bottling this mix in this vessel makes (plan §10.2, contracts §5).

    With a chosen formula (one the character knows): the mix is checked against its
    requirements, and anything short is said in words. With none (Experiment): the
    formulae within reach whose signature is exactly the mix's family and essences; an
    authored row wins its signature; exactly one, with its grades met, is the product, and
    a success writes it down (the bench calls `learn(..., "experiment")`); several are
    counted, never named.

    {"formula": fid | None, "experiment": bool, "found": bool, "new": bool,
     "ambiguous": int, "missing": [words], "refused": [words], "core": [effect, ...],
     "family": str | None, "target": words | None, "weak": int}
    """
    level = alchemist_level(actor)
    grades = mix_grades(mix)
    fams = vessel_families(vessel_id) if vessel_id else ()
    out = {"formula": None, "experiment": formula_id is None, "found": False, "new": False,
           "ambiguous": 0, "missing": [], "refused": [], "core": [], "family": None,
           "target": None, "weak": 0}
    if vessel_id and not fams:
        out["refused"].append(
            f"{_vessel_name(vessel_id).capitalize()} decides no product: it is none of a "
            f"vial, a flask, a bladder, a casing or a stick.")
        return out
    if formula_id is not None:
        row = _rows().get(str(formula_id or "").strip().lower())
        if row is None:
            out["refused"].append("There is no such formula.")
            return out
        if not knows(actor, row["id"]):
            out["refused"].append(f"You do not know the formula for {row['name']}.")
        out["refused"] += reach_problems(row, level)
        if not row["brewable"]:
            out["refused"].append(f"{row['name']} cannot be brewed yet: its effects are "
                                  f"still written as words.")
        form = _form(row, fams)
        if form is None:
            out["refused"].append(
                f"{row['name']} is {_a(row['family'])}; {_vessel_name(vessel_id)} makes "
                f"{' or '.join(_a(f) for f in fams)}.")
        out["missing"] = _missing(row, grades)
        out["family"] = form
        if not out["refused"] and not out["missing"]:
            out["formula"] = row["id"]
            out["core"] = core(row["id"])
            out["target"] = (row.get("delivers") or {}).get(form)
        return out
    present = set(grades)
    if not present:
        return out
    candidates = []
    for form in (fams or FAMILIES):
        candidates += [(r, form) for r in _holders(level, signature(form, present))]
    met = [(r, f) for r, f in candidates if not _missing(r, grades)]
    out["weak"] = len(candidates) - len(met)
    if len(candidates) > 1:
        out["ambiguous"] = len(candidates)
        # Orichalcum's job (plan §5.8; lane D's proposal, docs/alchemy-review.md item 4):
        # "an experiment that fits several formulae is the one the alchemist names, if it
        # is within reach". `aim` is what they name — a formula id or the spell it holds —
        # and it must be one of the candidates this mix already meets. A wrong name finds
        # nothing, and nothing is said about which of the candidates exist.
        if aim:
            want = str(aim).strip().lower()
            for row, form in met:
                if want in (row["id"], str(row.get("spell") or "")):
                    out.update(formula=row["id"], found=True, new=not knows(actor, row["id"]),
                               core=core(row["id"]), family=form, aimed=True,
                               target=(row.get("delivers") or {}).get(form))
                    break
        return out
    if len(met) == 1:
        row, form = met[0]
        out.update(formula=row["id"], found=True, new=not knows(actor, row["id"]),
                   core=core(row["id"]), family=form,
                   target=(row.get("delivers") or {}).get(form))
    return out


def _holders(level: int, sig: tuple) -> list[dict]:
    """The formulae within reach that experiment could take this signature for. An
    authored row wins its signature outright (plan §10.2: "a mix that matches an authored
    row exactly is that row, whatever derived rows share it"), whether or not it is in
    reach — so a derived row that shares a classic's or a shipped potion's signature is
    found only in writings, at every level, and the answer never flips as the alchemist
    levels past the authored row."""
    family, essences = sig
    out = []
    for row in _rows().values():
        if family not in (row.get("families") or ()):
            continue
        if signature(family, row["requires"]["essences"]) != sig:
            continue
        if not row["authored"] and family in row.get("shadowed", ()):
            continue
        if row["brewable"] and within_reach(row, level):
            out.append(row)
    if any(r["authored"] for r in out):
        out = [r for r in out if r["authored"]]
    return out


def findable_by_experiment(fid: str, level: int) -> list[str]:
    """The forms in which experiment can find this formula at this Alchemist level: those
    where it alone holds its signature within reach (plan §10.3; owner, open point 4: the
    classics and the 44 always, a derived row only when unique). [] means writings only."""
    row = _rows().get(str(fid or ""))
    if row is None or not row["brewable"] or not within_reach(row, level):
        return []
    out = []
    for family in row.get("families") or ():
        holders = _holders(level, signature(family, row["requires"]["essences"]))
        if len(holders) == 1 and holders[0]["id"] == row["id"]:
            out.append(family)
    return out


def _a(family: str) -> str:
    noun = {"splash": "splash flask"}.get(family, family)
    return ("an " if noun[:1] in "aeiou" else "a ") + noun


def could_become(actor, mix: dict, vessel_id: str | None = None) -> dict:
    """The possible-formulae count (owner Q5.3): how many formulae within reach this mix
    could still become — every essence it holds is one the formula requires (more can be
    added, nothing taken away), and the vessel's family fits (or none is chosen yet).
    Unknown formulae are counted, never named; known ones are named, since the player
    knows them. Essences the player has not discovered still count: the count is a hint
    about what the reagents really are (GW2's design, herbalism prior art §4).

    {"count": int, "known": [fid, ...], "line": words}"""
    level = alchemist_level(actor)
    present = set(mix_grades(mix))
    fams = vessel_families(vessel_id) if vessel_id else ()
    ids = []
    for row in _reachable(level):
        if fams and _form(row, fams) is None:
            continue
        if present <= set(row["requires"]["essences"]):
            ids.append(row["id"])
    mine = set(known(actor))
    named = sorted(i for i in ids if i in mine)
    return {"count": len(ids), "known": named, "line": _could_line(len(ids), named)}


def _could_line(count: int, named: list[str]) -> str:
    if count == 0:
        return "This could become no formula you can reach: bottled, it is a house compound."
    noun = "formula" if count == 1 else "formulae"
    line = f"This could still become {count} {noun}."
    if named:
        rows = _rows()
        names = ", ".join(rows[i]["name"] for i in named)
        line += f" You know {len(named)} of them: {names}."
    return line


# --- writings (plan §10.4) ------------------------------------------------------------------

def _copy_store(fid: str) -> str:
    from . import knowledge

    return knowledge.formula_store_id(fid)


COPY_FAILED_KEY = "copy_failed"


def _failed_at(actor, fid: str) -> int | None:
    entry = (getattr(actor, "herb_known", None) or {}).get(_copy_store(fid)) or {}
    try:
        return int((entry.get("how") or {}).get(COPY_FAILED_KEY))
    except (TypeError, ValueError):
        return None


def copy_check(actor, fid: str, *, clock: int | None = None) -> dict:
    """Copying a formula from a scroll or a spellbook, the wizard's way (CRB, Arcane
    Magical Writings; the APG alchemist's formula book uses "the same costs, pages, and
    time requirements"): DC 15 + spell level, the writing cost, 1 hour of study plus 1 hour
    a spell level. A classic has no spell level and copies at DC 15.

    {"dc", "cost_gp", "hours", "minutes", "retry_minute": int | None}"""
    row = _rows().get(str(fid or "")) or {}
    n = int(row.get("spell_level") or 0)
    minutes = copy_minutes(n)
    failed = _failed_at(actor, fid)
    retry = failed + COPY_RETRY_MINUTES if failed is not None else None
    if retry is not None and clock is not None and clock >= retry:
        retry = None
    return {"dc": COPY_DC_BASE + n, "cost_gp": copy_cost_gp(n), "hours": minutes / 60,
            "minutes": minutes, "retry_minute": retry}


def learn_route(actor, fid: str, source: str, *, clock: int | None = None) -> dict:
    """What learning this formula by this route asks, before anything is rolled or spent
    (plan §10.4; owner, open point 9). The bench (lane F) shows it, takes the roll and the
    gold, and calls `resolve_learn`.

    {"source", "check": bool, "dc": int | None, "cost_gp": int | None, "minutes": int,
     "spends": "never" | "on_success" | "always", "refused": [words]}"""
    route = LEARN_ROUTES.get(str(source or ""))
    row = _rows().get(str(fid or "").strip().lower())
    out = {"source": source, "check": False, "dc": None, "cost_gp": None, "minutes": 60,
           "spends": "never", "refused": []}
    if route is None:
        out["refused"].append(f"A formula is not learned from {source or 'nothing'}. From: "
                              f"{', '.join(LEARN_ROUTES)}.")
        return out
    if row is None:
        out["refused"].append("There is no such formula.")
        return out
    out["spends"] = route["spends"]
    if route["spell_only"] and row.get("kind") != "spell":
        out["refused"].append(f"{row['name']} holds no spell; a {source} teaches spell "
                              f"formulae only. An alchemist teacher or a formulary "
                              f"teaches the classics.")
    if knows(actor, row["id"]):
        out["refused"].append(f"You already know {row['name']}.")
    n = int(row.get("spell_level") or 0)
    if route["check"]:
        out["check"] = True
        out["dc"] = COPY_DC_BASE + n
    if route["writes"]:
        cc = copy_check(actor, row["id"], clock=clock)
        out["cost_gp"] = cc["cost_gp"]
        out["minutes"] = cc["minutes"]
        if cc["retry_minute"] is not None and (clock is None or clock < cc["retry_minute"]):
            out["refused"].append(f"You failed to copy {row['name']} within the week; you "
                                  f"may try again on day "
                                  f"{_day(cc['retry_minute'])}.")
    elif source == "potion":
        out["minutes"] = 60
    elif source in ("companion", "teacher"):
        out["minutes"] = 60 * max(1, n)
    return out


def _day(minute: int) -> int:
    from . import knowledge

    return knowledge.day_of(minute)


def resolve_learn(actor, fid: str, source: str, total: int | None = None, *,
                  clock: int | None = None) -> dict:
    """Apply a learning attempt whose roll (if any) is already made.

    A check route succeeds on total >= DC (no natural 20: a skill check). On success the
    formula is written; on a failed COPY (scroll, spellbook) the book's week begins and
    the scroll is kept; the potion route spends the potion whatever the roll — it is
    broken down to be read, as the enchanter's disenchant breaks its item.

    {"success", "learned": bool (new), "dc", "total", "margin", "spent": bool,
     "refused": [words]}"""
    plan = learn_route(actor, fid, source, clock=clock)
    out = {"success": False, "learned": False, "dc": plan["dc"], "total": total,
           "margin": None, "spent": False, "refused": plan["refused"]}
    if plan["refused"]:
        return out
    if plan["check"]:
        if total is None:
            out["refused"] = ["This route needs the Alchemist check rolled first."]
            return out
        out["margin"] = int(total) - int(plan["dc"])
        out["success"] = out["margin"] >= 0
    else:
        out["success"] = True
    if plan["spends"] == "always" or (plan["spends"] == "on_success" and out["success"]):
        out["spent"] = True
    if out["success"]:
        out["learned"] = learn(actor, fid, source, clock=clock)
    elif LEARN_ROUTES[source]["writes"] and clock is not None:
        entry = actor.herb_known.setdefault(_copy_store(fid), {"keys": [], "how": {}})
        entry.setdefault("how", {})[COPY_FAILED_KEY] = int(clock)
    return out


def potion_formula(stock) -> str | None:
    """Which formula a potion in hand teaches (the potion-in-hand route): its spell's
    formula, by `holds_spell` — an old potion keeps its spell exactly (Q10.2) — or the
    formula a new one records."""
    fid = str(_field(stock, "formula") or "")
    if fid and fid in _rows():
        return fid
    sid = str(_field(stock, "holds_spell") or "")
    row = for_spell(sid) if sid else None
    return row["id"] if row else None


def _field(stock, name):
    if isinstance(stock, dict):
        return stock.get(name)
    return getattr(stock, name, None)
