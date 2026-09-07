"""Races as documents — the ones the Core Rulebook ships, the ones a table writes on
the homebrew bench, and the ones a World Bible world brings with it.

"instead of picking the fantasy races that ship with pathfinder we should be able to
play as the races that ship with the world" (2026-09-06), with the standing rule that it
all follows the GAS-like framework. So a race is not a row in a Python table any more
(it was: `creation.RACES`, seven dicts, and a sheet that asked `race == "human"` for the
extra rank — a string match, the thing law one forbids). It is a document in the same
grammar feats and class abilities speak:

- **qualities** — `type`, `size`, `speed`, `mods` (fixed ability adjustments) and
  `choose` (the +2 the player places; a human's, or the Race Builder's standard
  "+2 physical, +2 mental, −2 any");
- **traits** — `modifiers` in the feat vocabulary (`skill_mod perception +2 racial`),
  read live by `Actor._race_mods` on every roll the way a feat or a worn ring is, never
  stored on the character; `tags` for what is a permission or a sense
  (`sense.darkvision.60`, `immune.sleep.magic`, `race.elf`), asked through
  `has_state`; `budget` for the extra feat and rank; and `not_yet` for what the sheet
  has no reader for, said plainly rather than silently dropped;
- **prose** — `traits` lines the forge shows, `description`, `languages`.

The price list is Paizo's own. The Advanced Race Guide's Race Builder (its "Racial
Qualities" and "Racial Traits" tables) prices every quality and trait in race points and
caps a *standard* race at 10 RP, an *advanced* one at 20, a *monstrous* one above that.
`rp()` reads that table off the document's own parts, so nobody types a total that
disagrees with them and no model authors a number: a world's people with wings and
echolocation is priced from what the words map to, and the forge refuses a race over the
table's tier the way it refuses a point-buy over budget.

What the traditions do, and what one abandoned: Foundry's PF1 system first kept the race
as a text field on the actor and every racial bonus in code, then replaced it with a race
*Item* carrying typed `changes` so a bonus could travel with its source and be removed
with it — the same move as this file. Its PF2 system's ancestry does the same with
boosts, flaws, size, speed and vision as fields. 5etools' race JSON is data first
(size, speed, darkvision as a number, trait tags) with the prose kept beside it. None of
them derive a race from prose at play time, and neither does this: a world's people is
turned into a document once, mechanically, from cue words, and the document is what
plays.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings

PHYSICAL = ("str", "dex", "con")
MENTAL = ("int", "wis", "cha")
ABILITIES = PHYSICAL + MENTAL

SIZES = ("tiny", "small", "medium", "large")
TYPES = ("humanoid", "fey", "aberration", "monstrous humanoid", "outsider", "dragon",
         "plant", "construct", "undead")

# --- the Race Builder's price list -----------------------------------------------------
# Advanced Race Guide, "Race Builder": racial qualities (type, size, speed, ability
# scores) and racial traits, each a line with a cost. Only the lines this app's sheet
# can read, or tag, are priced; a tag the table does not know costs nothing and is
# reported as unpriced rather than guessed at.
TYPE_RP = {"humanoid": 0, "fey": 2, "aberration": 3, "monstrous humanoid": 3,
           "outsider": 3, "dragon": 10, "plant": 10, "undead": 16, "construct": 20}
SIZE_RP = {"tiny": 4, "small": 0, "medium": 0, "large": 7}
# Tags and what the Race Builder charges for them. The second field is the prose the
# forge shows for a tag whose document carries no trait line of its own.
TAG_RP: dict[str, tuple[int, str]] = {
    "sense.darkvision.60": (2, "darkvision 60 ft"),
    "sense.darkvision.120": (3, "darkvision 120 ft"),
    "sense.low-light": (1, "low-light vision"),
    "sense.scent": (4, "scent"),
    "sense.blindsense.30": (4, "blindsense 30 ft"),
    "sense.see-in-darkness": (4, "see in darkness"),
    "immune.sleep.magic": (2, "immune to magic sleep"),
    "move.fly.30": (4, "fly 30 ft (clumsy)"),
    "move.climb.20": (2, "climb 20 ft"),
    "move.swim.30": (2, "swim 30 ft"),
    "move.burrow.20": (3, "burrow 20 ft"),
    "move.steady": (1, "speed never reduced by armour or load"),
    "natural.bite": (1, "bite"),
    "natural.claws": (2, "claws"),
    "natural.armor.1": (2, "+1 natural armour"),
    "amphibious": (2, "breathes air and water"),
    "hold-breath": (1, "holds breath for four times Con rounds"),
    "ferocity": (4, "ferocity: keep fighting below 0"),
    "weakness.light-blindness": (-2, "light blindness"),
    "weakness.light-sensitivity": (-1, "light sensitivity"),
    "weakness.vulnerable.sunlight": (-2, "vulnerable to sunlight"),
}
BUDGET_RP = {"feats": 4, "ranks": 4}           # flexible bonus feat; skilled
STANDARD_RP, ADVANCED_RP = 10, 20
TIERS = ({"rp": STANDARD_RP, "name": "Standard", "book": True,
          "note": "the Race Builder's core races: 1–10 RP"},
         {"rp": ADVANCED_RP, "name": "Advanced", "book": True,
          "note": "11–20 RP — drow, aasimar, tiefling territory"},
         {"rp": 40, "name": "Monstrous", "book": True,
          "note": "above 20 RP — the Race Builder's monstrous tier"})

# The Race Builder's standard ability-score option, and a human's.
STANDARD_CHOOSE = ({"amount": 2, "from": "physical"}, {"amount": 2, "from": "mental"},
                   {"amount": -2, "from": "any"})
HUMAN_CHOOSE = ({"amount": 2, "from": "any"},)

# The pickers the Races bench draws from. Nothing on that page is typed but the name.
ENERGIES = ("acid", "cold", "electricity", "fire", "sonic")
ALIGNMENTS = ("chaotic", "evil", "good", "lawful")
LANGUAGES = ("common", "dwarven", "elven", "gnome", "halfling", "orc", "goblin", "giant",
             "draconic", "sylvan", "undercommon", "aquan", "auran", "ignan", "terran",
             "celestial", "abyssal", "infernal", "aklo")
SPEEDS = (20, 30, 40)
# The Race Builder's ability-score options as the editor offers them; "fixed" is the
# six-select row for anything the table does not name.
ABILITY_OPTIONS = (
    {"id": "standard", "name": "Standard — the player places +2 physical, +2 mental, −2 any",
     "choose": [{"amount": 2, "from": "physical"}, {"amount": 2, "from": "mental"},
                {"amount": -2, "from": "any"}]},
    {"id": "human", "name": "Human heritage — the player places one +2",
     "choose": [{"amount": 2, "from": "any"}]},
    {"id": "flexible", "name": "Flexible — the player places two +2s",
     "choose": [{"amount": 2, "from": "any"}, {"amount": 2, "from": "any"}]},
    {"id": "fixed", "name": "Fixed — set each ability below", "choose": []},
)

_MOD_TYPES = ("ability_mod", "skill_mod", "save_mod", "combat_mod")
_BONUS_TYPES = ("racial", "untyped", "dodge", "natural", "circumstance", "enhancement",
                "insight", "luck", "morale", "competence", "size")
_SAVE_TARGETS = ("fort", "ref", "will")
_COMBAT_TARGETS = ("ac", "attack", "cmb", "cmd", "initiative", "hp_max", "touch_ac",
                   "flat_footed_ac", "damage")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")


# --- the anatomy catalogue: eidolon evolutions ---------------------------------------------
# Advanced Player's Guide, the summoner's eidolon. A race on the bench is built from
# these — "they can craft the anatomy from the Eidolon evolutions free of cost" — so an
# evolution costs no race points here; `points` is the summoner's figure, kept for the
# record. What each grants is written in the race grammar in content/races/evolutions.json
# and expanded by `expand`; a placeholder `$choice` takes the picker's energy, skill,
# ability, attack or alignment.

def evolutions() -> dict[str, dict]:
    path = _content_dir() / "evolutions.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {str(e["id"]): e for e in data.get("evolutions") or [] if isinstance(e, dict)}


def _fill(value, choice: str):
    if isinstance(value, str):
        return value.replace("$choice", choice)
    if isinstance(value, list):
        return [_fill(v, choice) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, choice) for k, v in value.items()}
    return value


def expand(doc: dict) -> dict:
    """What the document's evolutions grant, folded into the document's own fields.

    The stored document keeps `evolutions` as picked; the tags, modifiers, weapons,
    speed and size they imply are computed here every time, so correcting an
    evolution in the catalogue corrects every race that took it. `move.*.base` and
    `move.*.half` are resolved against the race's own speed once that is known.
    """
    d = dict(doc)
    cat = evolutions()
    tags = list(d.get("tags") or [])
    mods = dict(d.get("mods") or {})
    modifiers = list(d.get("modifiers") or [])
    weapons = list(d.get("weapons") or [])
    traits = list(d.get("traits") or [])
    not_yet = list(d.get("not_yet") or [])
    speed = int(d.get("speed") or 30)
    size = str(d.get("size") or "medium")
    for pick in d.get("evolutions") or []:
        if not isinstance(pick, dict):
            continue
        ev = cat.get(str(pick.get("id", "")))
        if not ev:
            continue
        choice = str(pick.get("choice") or "").strip().lower()
        times = max(1, int(pick.get("times", 1) or 1))
        for _ in range(times):
            for tg in _fill(ev.get("tags") or [], choice):
                if tg not in tags:
                    tags.append(tg)
            for m in _fill(ev.get("modifiers") or [], choice):
                modifiers.append(dict(m))
            for w in _fill(ev.get("weapons") or [], choice):
                if not any(x.get("key") == w.get("key") for x in weapons):
                    weapons.append(dict(w))
            for k, v in (ev.get("mods") or {}).items():
                mods[k] = mods.get(k, 0) + int(v)
            if ev.get("mods_choice") and choice in ABILITIES:
                mods[choice] = mods.get(choice, 0) + int(ev["mods_choice"])
            speed += int(ev.get("speed_bonus") or 0)
            if ev.get("size"):
                size = str(ev["size"])
        line = _fill(str(ev.get("line") or ev.get("name") or ""), choice or "—")
        if line and line not in traits:
            traits.append(line if times == 1 else f"{line} (x{times})")
        waits = _fill(str(ev.get("not_yet") or ""), choice or "—")
        if waits and waits not in not_yet:
            not_yet.append(waits)
    # Speeds that are "equal to base" or "half base" are numbers now.
    resolved = []
    for tg in tags:
        if tg.endswith(".base"):
            tg = tg[:-5] + f".{speed}"
        elif tg.endswith(".half"):
            tg = tg[:-5] + f".{max(5, speed // 2 // 5 * 5)}"
        if tg not in resolved:
            resolved.append(tg)
    d.update({"tags": resolved, "mods": {k: v for k, v in mods.items() if v},
              "modifiers": modifiers, "weapons": weapons, "traits": traits,
              "not_yet": not_yet, "speed": speed, "size": size})
    return d


def speeds(doc: dict) -> dict[str, int]:
    """Every way this body moves, in feet: land from the document, the rest from its
    `move.<mode>.<ft>` tags."""
    out = {"land": int(doc.get("speed") or 30)}
    for tg in doc.get("tags") or []:
        m = re.match(r"^move\.(fly|swim|climb|burrow)\.(\d+)$", str(tg))
        if m:
            out[m.group(1)] = max(out.get(m.group(1), 0), int(m.group(2)))
    return out


def senses(doc: dict) -> list[str]:
    out = []
    for tg in doc.get("tags") or []:
        m = re.match(r"^sense\.([a-z-]+)(?:\.(\d+))?$", str(tg))
        if m:
            out.append(m.group(1).replace("-", " ") + (f" {m.group(2)} ft" if m.group(2) else ""))
    return out


def body_line(doc: dict) -> str:
    """One sentence for the narrator's brief: how this body moves, senses and fights.
    A tell about the body, not a rule — the narrator dresses it."""
    parts = []
    sp = speeds(doc)
    moves = [f"{k} {v} ft" for k, v in sp.items() if k != "land"]
    if moves:
        parts.append("moves by " + ", ".join(moves) + " as well as on foot")
    sn = senses(doc)
    if sn:
        parts.append("senses: " + ", ".join(sn))
    naturals = [str(w.get("name") or w.get("key")) for w in doc.get("weapons") or []]
    if naturals:
        parts.append("natural weapons: " + ", ".join(naturals))
    extra = [TAG_RP[t][1] for t in doc.get("tags") or [] if t in TAG_RP
             and not t.startswith(("sense.", "move.", "natural."))]
    if extra:
        parts.append("; ".join(extra))
    return "; ".join(parts)


# --- loading ---------------------------------------------------------------------------

def _content_dir() -> Path:
    return Path(settings.BASE_DIR) / "content" / "races"


def homebrew_dir(make: bool = False) -> Path:
    p = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "races"
    if make:
        p.mkdir(parents=True, exist_ok=True)
    return p


def _read_folder(folder: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not folder.exists():
        return out
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        # A file holding many under "races", or one race on its own — which has a
        # name. The evolutions catalogue sits in the same folder and has neither.
        if "races" in data:
            entries = data.get("races")
        elif data.get("name") or data.get("id"):
            entries = [data]
        else:
            continue
        for e in entries or []:
            if isinstance(e, dict):
                rid = slug(e.get("id") or e.get("name") or path.stem)
                if rid:
                    out[rid] = {**e, "id": rid}
    return out


def shipped() -> dict[str, dict]:
    """The seven, from content/races. Read per call: a few files, and a stale cache in
    the frozen app is the trap CLAUDE.md names."""
    return {k: normalise(v) for k, v in _read_folder(_content_dir()).items()}


def authored() -> dict[str, dict]:
    """What the table wrote or imported, homebrew/races."""
    return {k: normalise(v) for k, v in _read_folder(homebrew_dir()).items()}


def all_races() -> dict[str, dict]:
    """Shipped, then yours over the top, field by field — the registry's merge rule."""
    out = shipped()
    for k, v in authored().items():
        out[k] = normalise({**out.get(k, {}), **v})
    return out


def get(race_id: str) -> dict | None:
    return all_races().get(slug(race_id))


def document(race_id: str) -> dict | None:
    """The document as the sheet reads it: normalised, with what it computes filled in."""
    doc = get(race_id)
    return derive(doc) if doc else None


# --- shape -----------------------------------------------------------------------------

def normalise(entry: dict) -> dict:
    """One shape whatever was written: `any: 2` (the old table's spelling of a human's
    choice) becomes a `choose` entry, lists are lists, numbers are numbers."""
    d = dict(entry)
    d["id"] = slug(d.get("id") or d.get("name") or "")
    d["name"] = str(d.get("name") or d["id"].replace("-", " ").title()).strip()
    d["type"] = str(d.get("type") or "humanoid").strip().lower()
    d["size"] = str(d.get("size") or "medium").strip().lower()
    try:
        d["speed"] = int(d.get("speed") or 30)
    except (TypeError, ValueError):
        d["speed"] = d.get("speed")
    mods = d.get("mods") or {}
    if isinstance(mods, str):
        mods = _parse_mods(mods)
    d["mods"] = {str(k).lower(): int(v) for k, v in dict(mods).items()
                 if _int(v) is not None and int(v)}
    choose = d.get("choose")
    if isinstance(choose, str):
        choose = _parse_choose(choose)
    choose = list(choose or [])
    if d.get("any") and not choose:
        choose = [{"amount": int(d["any"]), "from": "any"}]
    d["choose"] = [{"amount": int(c.get("amount", 2)), "from": str(c.get("from", "any")).lower()}
                   for c in choose if isinstance(c, dict) and _int(c.get("amount")) is not None]
    d.pop("any", None)
    mods_ = d.get("modifiers")
    if isinstance(mods_, str):
        mods_ = _parse_modifiers(mods_)
    d["modifiers"] = [m for m in (mods_ or []) if isinstance(m, dict)]
    for key in ("tags", "traits", "languages", "not_yet"):
        got = d.get(key)
        if isinstance(got, str):
            got = [ln.strip() for ln in got.replace(",", chr(10)).split(chr(10))]
        d[key] = [str(x).strip() for x in (got or []) if str(x).strip()]
    d["tags"] = [t.lower() for t in d["tags"]]
    if d["id"] and f"race.{d['id']}" not in d["tags"]:
        d["tags"].insert(0, f"race.{d['id']}")
    budget = d.get("budget") or {}
    if isinstance(budget, str):
        budget = _parse_budget(budget)
    d["budget"] = {k: int(v) for k, v in dict(budget).items()
                   if k in BUDGET_RP and _int(v) is not None and int(v)}
    # The old table's two flags, kept readable.
    if d.pop("bonus_feat", None):
        d["budget"].setdefault("feats", 1)
    if d.pop("bonus_ranks", None):
        d["budget"].setdefault("ranks", 1)
    d["description"] = str(d.get("description") or "").strip()
    d["origin"] = str(d.get("origin") or "yours")
    evs = d.get("evolutions") or []
    d["evolutions"] = [{"id": str(e.get("id", "")).strip().lower(),
                        "choice": str(e.get("choice") or "").strip().lower(),
                        "times": max(1, int(e.get("times", 1) or 1))}
                       for e in evs if isinstance(e, dict) and str(e.get("id", "")).strip()]
    d["weapons"] = [w for w in (d.get("weapons") or []) if isinstance(w, dict)]
    # The cultures of this body, for a world's race: a Nahyrin is a Kaelinoran. The
    # forge offers them under the race rather than as a race of their own.
    d["heritages"] = [{"people_id": str(h.get("people_id") or ""), "name": str(h.get("name") or "").strip(),
                       "summary": str(h.get("summary") or "")}
                      for h in (d.get("heritages") or []) if isinstance(h, dict) and h.get("name")]
    d["world"] = str(d.get("world") or "")
    return d


def derive(entry: dict) -> dict:
    """What the document computes rather than stores: race points, the tier, the trait
    lines the tags imply. Declared as the `races` Kind's `derive` hook, so the bench
    shows it; the sheet reads it through `document`."""
    d = expand(normalise(entry))
    d["rp"] = rp(entry)
    d["power"] = power(d["rp"])
    d["speeds"] = speeds(d)
    d["senses"] = senses(d)
    shown = list(d["traits"])
    for t in d["tags"]:
        line = TAG_RP.get(t, (0, ""))[1]
        if line and not any(line.split()[0] in s for s in shown):
            shown.append(line)
    # What the qualities grant, said too: a Kyrexi with a human's option and budget
    # and no anatomy had no line at all on the sheet's Racial traits table.
    if d["choose"] and not any("ability score" in s for s in shown):
        parts = [f"{c['amount']:+d} {'any' if c['from'] == 'any' else c['from']}"
                 for c in d["choose"]]
        shown.append(("+2 to one ability score" if parts == ["+2 any"]
                      else ", ".join(parts) + " ability scores, placed at the forge"))
    if d["budget"].get("feats") and not any("bonus feat" in s for s in shown):
        shown.append("bonus feat")
    if d["budget"].get("ranks") and not any("skill rank" in s for s in shown):
        shown.append("+1 skill rank per level")
    d["trait_lines"] = shown
    d["unpriced"] = [t for t in d["tags"] if t not in TAG_RP and not t.startswith("race.")]
    return d


def rp(doc: dict) -> int:
    """Race points, from the Race Builder's tables, off the parts. An evolution costs
    nothing — the table's decision — so only what the document states outright is
    priced; `expand` is deliberately not called here."""
    d = normalise(doc)
    total = TYPE_RP.get(d["type"], 3)
    total += SIZE_RP.get(d["size"], 7)
    speed = int(d["speed"] or 30)
    total += -1 if speed < 30 else (speed - 30) // 10
    total += _mods_rp(d["mods"], d["choose"])
    for t in d["tags"]:
        total += TAG_RP.get(t, (0, ""))[0]
    for k, v in d["budget"].items():
        total += BUDGET_RP[k] * max(0, int(v))
    for m in d["modifiers"]:
        amt = abs(int(m.get("amount", 0) or 0))
        kind = str(m.get("type", ""))
        # Skill bonus 2 RP per +2 (Sneaky's +4 is 5); a save or combat point is a point
        # each (Lucky, Lesser: +1 all saves, 2 RP — three here, the rounding this way).
        total += amt if kind in ("save_mod", "combat_mod", "ability_mod") else amt
    return total


def _mods_rp(mods: dict, choose: list) -> int:
    """The ability-score option's cost. The table's named options first; anything the
    table does not name is priced off its net adjustment, which reproduces the named
    rows it does cover (standard 0, flexible 2, weakness −1, greater weakness −3)."""
    fixed = sorted(int(v) for v in mods.values())
    picks = sorted((int(c["amount"]), c["from"]) for c in choose)
    if not fixed and picks == [(2, "any")]:
        return 0                                     # human heritage
    if not fixed and picks == [(-2, "any"), (2, "mental"), (2, "physical")]:
        return 0                                     # standard, chosen at the forge
    if not fixed and picks == [(2, "any"), (2, "any")]:
        return 2                                     # flexible
    if fixed == [-2, 2, 2] and not picks:
        phys = [k for k, v in mods.items() if v > 0 and k in PHYSICAL]
        ment = [k for k, v in mods.items() if v > 0 and k in MENTAL]
        return 0 if (phys and ment) else 1           # standard / specialized
    net = sum(fixed) + sum(a for a, _ in picks)
    return net - 2 if net >= 2 else -1 + net // 2


def power(points: int) -> str:
    if points <= STANDARD_RP:
        return "standard"
    if points <= ADVANCED_RP:
        return "advanced"
    return "monstrous"


def budget(race_id: str, what: str) -> int:
    """The extra feats or ranks a race grants — asked of the document, never of the
    name. `race == "human"` was the sheet's question before this."""
    doc = get(race_id)
    return int((doc or {}).get("budget", {}).get(what, 0) or 0)


# --- the bench's one-per-line fields ------------------------------------------------------

def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _parse_mods(text: str) -> dict:
    """'con +2' one per line, or comma separated."""
    out: dict[str, int] = {}
    for ln in re.split(r"[,\n]", str(text or "")):
        m = re.match(r"^\s*([a-z]{3})\s*([+-]?\s*\d+)\s*$", ln.strip().lower())
        if m:
            out[m.group(1)] = int(m.group(2).replace(" ", ""))
    return out


def _parse_choose(text: str) -> list[dict]:
    """'+2 any', '+2 physical', '-2 mental'."""
    out = []
    for ln in re.split(r"[,\n]", str(text or "")):
        m = re.match(r"^\s*([+-]?\s*\d+)\s+(any|physical|mental)\s*$", ln.strip().lower())
        if m:
            out.append({"amount": int(m.group(1).replace(" ", "")), "from": m.group(2)})
    return out


def _parse_modifiers(text: str) -> list[dict]:
    """'skill_mod perception +2 racial', with an optional 'when maneuver=bull rush|trip'."""
    out = []
    for ln in str(text or "").split(chr(10)):
        ln = ln.strip()
        if not ln:
            continue
        m = re.match(r"^(\w+)\s+([a-z _-]+?)\s+([+-]?\d+)(?:\s+([a-z]+))?"
                     r"(?:\s+when\s+(\w+)\s*=\s*(.+))?$", ln.lower())
        if not m:
            out.append({"line": ln})            # kept so validate can name it
            continue
        spec = {"type": m.group(1), "target": m.group(2).strip(), "amount": int(m.group(3)),
                "bonus_type": m.group(4) or "racial"}
        if m.group(5):
            spec["when"] = {m.group(5): [v.strip() for v in m.group(6).split("|") if v.strip()]}
        out.append(spec)
    return out


def _parse_budget(text: str) -> dict:
    out = {}
    for ln in re.split(r"[,\n]", str(text or "")):
        m = re.match(r"^\s*(feats|ranks)\s*([+]?\d+)\s*$", ln.strip().lower())
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def render_lines(doc: dict) -> dict:
    """The document's structured fields as the one-per-line text the bench form edits."""
    d = normalise(doc)
    def when(spec):
        w = spec.get("when") or {}
        return "".join(f" when {k}={'|'.join(map(str, v if isinstance(v, list) else [v]))}"
                       for k, v in w.items())
    return {
        "mods": chr(10).join(f"{k} {v:+d}" for k, v in d["mods"].items()),
        "choose": chr(10).join(f"{c['amount']:+d} {c['from']}" for c in d["choose"]),
        "modifiers": chr(10).join(
            f"{m['type']} {m['target']} {int(m.get('amount', 0)):+d} "
            f"{m.get('bonus_type', 'racial')}{when(m)}"
            for m in d["modifiers"] if "type" in m),
        "tags": chr(10).join(t for t in d["tags"] if not t.startswith("race.")),
        "traits": chr(10).join(d["traits"]),
        "languages": chr(10).join(d["languages"]),
        "not_yet": chr(10).join(d["not_yet"]),
        "budget": chr(10).join(f"{k} +{v}" for k, v in d["budget"].items()),
    }


def for_bench(entry: dict) -> dict:
    """The `races` Kind's derive hook: computed fields plus the line-rendered ones."""
    d = derive(entry)
    d.update(render_lines(d))
    return d


# --- validation, with the fix named -------------------------------------------------------

def validate(entry: dict) -> list[str]:
    """Every problem at once, each saying what to type."""
    problems: list[str] = []
    d = normalise(entry)
    if not d["name"]:
        problems.append("name: give the race a name — 'Korvu'.")
    if d["type"] not in TYPES:
        problems.append(f"type: {d['type']!r} is not a creature type the Race Builder "
                        f"prices; pick one of {', '.join(TYPES)}.")
    if d["size"] not in SIZES:
        problems.append(f"size: {d['size']!r} — a player race is tiny, small, medium or "
                        f"large (large is the Race Builder's giants only).")
    if _int(d["speed"]) is None or int(d["speed"]) not in (20, 30, 40):
        problems.append("speed: 20 (slow), 30 (normal) or 40 (fast), in feet.")
    for k in d["mods"]:
        if k not in ABILITIES:
            problems.append(f"mods: {k!r} is not an ability; write 'con +2', one per line.")
    for c in d["choose"]:
        if c["from"] not in ("any", "physical", "mental"):
            problems.append(f"choose: '+2 {c['from']}' — the pool is any, physical or "
                            f"mental.")
    for i, m in enumerate(d["modifiers"]):
        at = f"modifiers[{i + 1}]"
        if "line" in m:
            problems.append(f"{at}: could not read {m['line']!r}; write "
                            f"'skill_mod perception +2 racial' or "
                            f"'combat_mod cmd +4 racial when maneuver=bull rush|trip'.")
            continue
        if m.get("type") not in _MOD_TYPES:
            problems.append(f"{at}: the type is one of {', '.join(_MOD_TYPES)}.")
        if m.get("type") == "save_mod" and m.get("target") not in _SAVE_TARGETS:
            problems.append(f"{at}: a save is fort, ref or will.")
        if m.get("type") == "combat_mod" and m.get("target") not in _COMBAT_TARGETS:
            problems.append(f"{at}: a combat target is one of "
                            f"{', '.join(_COMBAT_TARGETS)}.")
        if m.get("type") == "ability_mod" and m.get("target") not in ABILITIES:
            problems.append(f"{at}: an ability is str, dex, con, int, wis or cha.")
        if m.get("bonus_type") not in _BONUS_TYPES:
            problems.append(f"{at}: the bonus type is one of {', '.join(_BONUS_TYPES)}; "
                            f"a race's own bonus is 'racial'.")
        if _int(m.get("amount")) is None or not int(m.get("amount")):
            problems.append(f"{at}: the amount is a non-zero number.")
    for t in d["tags"]:
        if not re.match(r"^[a-z0-9][a-z0-9.-]*$", t):
            problems.append(f"tags: {t!r} — a tag is dot-separated lower case, "
                            f"like sense.darkvision.60.")
    for k in (entry.get("budget") or {}) if isinstance(entry.get("budget"), dict) else {}:
        if k not in BUDGET_RP:
            problems.append(f"budget: {k!r} — a race grants extra 'feats' or 'ranks'.")
    cat = evolutions()
    taken = {}
    for i, pick in enumerate(d["evolutions"]):
        at = f"evolutions[{i + 1}]"
        ev = cat.get(pick["id"])
        if not ev:
            problems.append(f"{at}: {pick['id']!r} is not an evolution; pick from the "
                            f"catalogue on the bench.")
            continue
        taken[pick["id"]] = taken.get(pick["id"], 0) + pick["times"]
        choice = ev.get("choice")
        pools = {"energy": ENERGIES, "alignment": ALIGNMENTS, "ability": ABILITIES,
                 "skill": None, "attack": None}
        if choice and not pick["choice"]:
            problems.append(f"{ev['name']}: pick the {choice} it applies to.")
        elif choice and pools.get(choice) and pick["choice"] not in pools[choice]:
            problems.append(f"{ev['name']}: {pick['choice']!r} is not a {choice}; pick one "
                            f"of {', '.join(pools[choice])}.")
    for eid, n in taken.items():
        ev = cat[eid]
        if n > int(ev.get("takes", 1) or 1):
            problems.append(f"{ev['name']}: may be taken {ev.get('takes', 1)} time(s), not {n}.")
        for need in ev.get("needs") or []:
            if need not in taken:
                problems.append(f"{ev['name']} needs {cat.get(need, {}).get('name', need)} "
                                f"first.")
    return problems


# --- from a World Bible world -----------------------------------------------------------------

# What a people's own words map to. Detect mechanically, price from the table: nothing
# here reads a number out of prose, and a body the table has no line for becomes a
# `not_yet` sentence rather than a guess. Each row: a pattern over the anatomy facts,
# the tags it grants, the trait line it shows, and what still waits on the engine.
CUES: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    (r"\b(wings?|winged|fly|flight|glide|soar|airborne)\b", ("move.fly.30",),
     "fly 30 ft (clumsy)", "a fly speed: the engine moves on the ground only"),
    (r"\b(echolocat\w*|blindsense|sonar)\b", ("sense.blindsense.30",),
     "blindsense 30 ft", ""),
    (r"\b(see|sight|vision|eyes)\b[^.]{0,40}\b(dark|darkness|night|lightless|pitch)\b|"
     r"\b(dark|night)\W?vision\b", ("sense.darkvision.60",), "darkvision 60 ft", ""),
    (r"\b(dim|low)\W?light\b|\btwilight\b|\bdusk\b", ("sense.low-light",),
     "low-light vision", ""),
    (r"\b(scent|smell|olfact\w*|nose)\b[^.]{0,40}\b(keen|sharp|track|hunt|acute|strong)\b|"
     r"\b(track|hunt)\w*\s+by\s+(scent|smell)\b", ("sense.scent",), "scent", ""),
    (r"\b(gills?|amphibious|breathe\w*\s+(under)?water|aquatic)\b",
     ("amphibious", "move.swim.30"), "amphibious; swim 30 ft",
     "a swim speed: the engine has no water"),
    (r"\b(climb\w*|arboreal|tree-?dwell\w*)\b", ("move.climb.20",), "climb 20 ft",
     "a climb speed: the engine has no walls"),
    (r"\b(burrow\w*|tunnel\w*|dig\w*)\b", ("move.burrow.20",), "burrow 20 ft",
     "a burrow speed: the engine has no earth"),
    (r"\b(talons?|claws?|clawed)\b", ("natural.claws",), "claws",
     "natural attacks: the engine rolls the weapon in hand"),
    (r"\b(fangs?|bite|tusks?|mandibles?|beak)\b", ("natural.bite",), "bite",
     "natural attacks: the engine rolls the weapon in hand"),
    (r"\b(carapace|chitin\w*|scales?|scaled|hide|armou?red|plated|shell)\b",
     ("natural.armor.1",), "+1 natural armour", ""),
    (r"\b(light|sun|sunlight|daylight)\b[^.]{0,40}\b(pain\w*|blind\w*|burn\w*|dazzl\w*|hurt\w*|weak\w*)\b",
     ("weakness.light-sensitivity",), "light sensitivity", ""),
)
_SMALL = re.compile(r"\b(small|short|slight|diminutive|half the height|child-sized|"
                    r"waist-high|knee-high|halfling-sized)\b", re.I)
_LARGE = re.compile(r"\b(towering|giant|huge|massive|twice the height|ten feet|"
                    r"nine feet|eight feet)\b", re.I)
_FAST = re.compile(r"\b(swift|fast|quick|fleet|sprint\w*|outrun\w*|rapid)\b", re.I)
_SLOW = re.compile(r"\b(slow|lumber\w*|plodding|ponderous|waddl\w*)\b", re.I)
_ANATOMY_KEYS = ("Anatomy", "Body", "Senses", "Lifecycle")


def _facts(entity) -> dict:
    return dict(getattr(entity, "facts", None) or {})


def is_species(entity) -> bool:
    """A people the world describes as a *body* is a race; one described only by
    custom is a heritage of somebody else's body — World Bible writes its `people_anatomy`
    section for the first kind and not the second."""
    if str(getattr(entity, "kind", "")).upper() != "PEOPLE":
        return False
    facts = _facts(entity)
    return any(str(facts.get(k) or "").strip() for k in _ANATOMY_KEYS)


def draft(name: str, phrases, *, size_hint: str = "", speed_hint: str = "",
          about: str = "", origin: str = "", people_id: str = "", world: str = "") -> dict:
    """One race document from the world's own sentences. The words decide which lines
    of the table apply; the table decides the numbers."""
    text = " ".join(str(p) for p in phrases if str(p).strip())
    low = text.lower()
    tags: list[str] = []
    traits: list[str] = []
    not_yet: list[str] = []
    for pattern, granted, line, waits in CUES:
        if re.search(pattern, low):
            for t in granted:
                if t not in tags:
                    tags.append(t)
            if line not in traits:
                traits.append(line)
            if waits and waits not in not_yet:
                not_yet.append(waits)
    size = size_hint.strip().lower() if size_hint in SIZES else (
        "small" if _SMALL.search(low) else "medium")
    if _LARGE.search(low) and size == "medium":
        # The Race Builder gives Large to giants only; a towering people is still a
        # medium creature on the sheet, and says so.
        not_yet.append("a towering build: the Race Builder allows Large for giants only, "
                       "so the sheet keeps medium")
    speed = {"slow": 20, "normal": 30, "fast": 40}.get(speed_hint.strip().lower(), 0) or (
        40 if _FAST.search(low) and not _SLOW.search(low) else
        20 if _SLOW.search(low) else 30)
    rid = slug(name)
    return normalise({
        "id": rid, "name": str(name).strip(),
        "description": (about or text)[:400],
        "type": "humanoid", "size": size, "speed": speed,
        "mods": {}, "choose": list(STANDARD_CHOOSE),
        "modifiers": [], "tags": tags, "traits": traits,
        "budget": {}, "languages": [rid] if rid else [],
        "not_yet": not_yet, "origin": origin or "world",
        "people_id": people_id, "world": world,
        # Converted mechanically from prose and read by nobody yet — the same flag the
        # ingredient bench shows as "unreviewed".
        "converted": True,
    })


def world_key(world) -> str:
    """How a race document names its world: the export file's stem — the shelf's own
    id for it (`pangrella-campaign`) — falling back to the world's name as a slug."""
    source = getattr(world, "source", None)
    if source:
        return Path(str(source)).stem.lower()
    return slug(getattr(world, "id", "") or getattr(world, "name", "") or "")


def written_for(world) -> dict[str, dict]:
    """The race documents written for this world by hand — shipped in content/races
    (Pangrella's, Fantasia's) or on the bench — keyed by id."""
    key = world_key(world)
    name = slug(getattr(world, "name", "") or "")
    return {k: d for k, d in all_races().items()
            if d.get("world") and d["world"].lower() in (key, name)}


def from_world(world) -> list[dict]:
    """The races a world ships with: the ones its author wrote (`play.races[]`, the
    contract in docs/campaign-format.md — World Bible does not write them yet) and,
    when that list is absent, one per people whose entry describes a body."""
    out: list[dict] = []
    world_id = world_key(world)
    play = getattr(world, "play", None) or {}
    written = play.get("races") if isinstance(play, dict) else None
    if written:
        for raw in written:
            if not isinstance(raw, dict) or not str(raw.get("name", "")).strip():
                continue
            phrases = [*(raw.get("body") or []), *(raw.get("senses") or []),
                       *(raw.get("movement") or [])]
            out.append(draft(raw["name"], phrases, size_hint=str(raw.get("size") or ""),
                             speed_hint=str(raw.get("speed") or ""),
                             about=str(raw.get("about") or ""),
                             origin=f"world:{raw.get('people_id') or raw.get('id') or slug(raw['name'])}",
                             people_id=str(raw.get("people_id") or ""), world=world_id))
        return out
    for ent in (getattr(world, "entities", None) or {}).values():
        if not is_species(ent):
            continue
        facts = _facts(ent)
        phrases = [str(facts.get(k) or "") for k in _ANATOMY_KEYS]
        out.append(draft(ent.name, phrases, about=str(facts.get("Anatomy") or ""),
                         origin=f"world:{ent.id}", people_id=str(ent.id), world=world_id))
    return out


def _covered(written: dict) -> set[str]:
    """The people ids the written race documents already speak for — as a race, or as
    a heritage of one."""
    out: set[str] = set()
    for d in written.values():
        if d.get("people_id"):
            out.add(str(d["people_id"]))
        for h in d.get("heritages") or []:
            if h.get("people_id"):
                out.add(str(h["people_id"]))
    return out


def heritages_from_world(world) -> list[dict]:
    """The peoples that are not bodies of their own and that no written race claims:
    a culture the forge's heritage field offers by name, so a Nahyrin is a Nahyrin
    without becoming a separate race. (A written race lists its own heritages.)"""
    covered = _covered(written_for(world))
    out = []
    for ent in (getattr(world, "entities", None) or {}).values():
        if str(getattr(ent, "kind", "")).upper() == "PEOPLE" and not is_species(ent) \
                and ent.id not in covered:
            out.append({"id": ent.id, "name": ent.name,
                        "summary": str(_facts(ent).get("Homeland") or "")})
    return sorted(out, key=lambda h: h["name"])


def for_world(world) -> list[dict]:
    """The races the forge offers in this world: the ones written for it by hand
    (content/races, or the bench — the bench's copy winning on the same id), then a
    draft for each people with a body that nothing written speaks for, each derived."""
    written = written_for(world)
    covered = _covered(written)
    out = [derive(d) for d in written.values()]
    mine = authored()
    for d in from_world(world):
        if d.get("people_id") in covered or d["id"] in written:
            continue
        kept = mine.get(d["id"])
        if kept and str(kept.get("world") or "") in ("", d.get("world", "")):
            d = normalise({**d, **kept})
        out.append(derive(d))
    return sorted(out, key=lambda d: d["name"])


def import_from_world(world, overwrite: bool = False) -> list[str]:
    """Write the world's races onto the bench so they can be corrected. A file already
    there is the table's own answer and is kept unless told otherwise."""
    written: list[str] = []
    folder = homebrew_dir(make=True)
    covered = _covered(written_for(world))
    for d in from_world(world):
        path = folder / f"{d['id']}.json"
        if path.exists() and not overwrite or d.get("people_id") in covered:
            continue
        path.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
        written.append(d["id"])
    return written


def save_from_bench(entry: dict) -> tuple[dict, list[str]]:
    """The `races` Kind's save hook: parse the one-per-line fields, validate with the
    fix named, and hand back the document to write."""
    d = normalise(entry)
    problems = validate(d)
    if not problems:
        d["converted"] = False
    return d, problems


def catalogue() -> dict:
    """Everything the race editor draws its pickers from, in one payload."""
    from .tables import SKILLS

    return {
        "types": list(TYPES), "sizes": list(SIZES), "speeds": list(SPEEDS),
        "abilities": list(ABILITIES), "energies": list(ENERGIES),
        "alignments": list(ALIGNMENTS), "languages": list(LANGUAGES),
        "skills": sorted(SKILLS), "ability_options": list(ABILITY_OPTIONS),
        "evolutions": sorted(evolutions().values(),
                             key=lambda e: (e.get("group", ""), e.get("points", 0), e["name"])),
        "attacks": ["bite", "claws", "gore", "slam", "pincers", "sting", "tail slap",
                    "tentacle", "wing buffet"],
        "budget": list(BUDGET_RP),
        "tiers": list(TIERS),
    }
