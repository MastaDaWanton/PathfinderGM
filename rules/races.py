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
          "note": "above 20 RP — the Race Builder's monstrous tier"},
         # 0 is no cap: any race the bench holds, whatever it prices at.
         {"rp": 0, "name": "Unlimited", "book": False,
          "note": "no cap — any race on the bench, whatever it prices at"})

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


# Limbs that come in pairs, and how many of them a body has before it buys any. The
# count is resolved into the tag by `expand` — `limbs.arms.6` is six arms — because the
# tag list is the only part of the document that reaches play, and a set cannot hold "how
# many". See `VISIBLE_BODY` for the words a person in the room gets.
PAIRED_LIMBS: dict[str, int] = {"limbs.arms": 2, "limbs.legs": 2}


def expand(doc: dict) -> dict:
    """What the document's evolutions grant, folded into the document's own fields.

    The stored document keeps `evolutions` as picked; the tags, modifiers, weapons,
    speed and size they imply are computed here every time, so correcting an
    evolution in the catalogue corrects every race that took it. `move.*.base` and
    `move.*.half` are resolved against the race's own speed once that is known, and a
    paired limb taken more than once resolves to how many there are.
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
    # How many times each tag was granted and each trait line earned. A repeatable
    # evolution reaches here two ways — one pick saying `times: 3`, or three picks saying
    # `times: 1` — and the bench writes the second. Counting `times` alone therefore
    # undercounts, and a `tags` list cannot count at all: measured 2026-09-15, a race with
    # `limbs-arms` picked twice (six arms) described itself with four.
    granted: dict[str, int] = {}
    earned: dict[str, int] = {}
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
                granted[tg] = granted.get(tg, 0) + 1
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
        if line:
            earned[line] = earned.get(line, 0) + times
            if line not in traits:
                traits.append(line)
        waits = _fill(str(ev.get("not_yet") or ""), choice or "—")
        if waits and waits not in not_yet:
            not_yet.append(waits)
    # The count goes on at the end, so three separate picks of one read the same as one
    # pick of three. Lines the document wrote itself are not in `earned` and keep theirs.
    traits = [f"{ln} (x{earned[ln]})" if earned.get(ln, 1) > 1 else ln for ln in traits]
    # Speeds that are "equal to base" or "half base" are numbers now, and so are limbs.
    resolved = []
    for tg in tags:
        if tg.endswith(".base"):
            tg = tg[:-5] + f".{speed}"
        elif tg.endswith(".half"):
            tg = tg[:-5] + f".{max(5, speed // 2 // 5 * 5)}"
        elif tg in PAIRED_LIMBS:
            # `max(1, …)`: a document may carry the bare tag with no evolution behind it
            # — a world's race written from cue words — and the tag being there at all
            # means one extra pair. Already-counted tags (`limbs.arms.6`) fall through
            # untouched, so expanding twice is the same as expanding once.
            tg = f"{tg}.{PAIRED_LIMBS[tg] + 2 * max(1, granted.get(tg, 0))}"
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


# What a body LOOKS like, as against what it costs. Anyone standing in the room can see
# these, so the narrator has to know them — and nothing else in the race grammar says so.
#
# Measured 2026-09-15, from play: a player asked the nearest person to count their arms and
# was told "Two. You have two arms, master." The character was an asura with `limbs.arms`
# on its sheet and "an extra pair of arms" in its own trait list. The narrator had never
# been told, because `body_line` selected its extra clauses by asking whether a tag was in
# `TAG_RP` — the RACE POINT PRICE TABLE. Whether a servant could see your arms depended on
# whether the Advanced Race Guide charges for them, and `limbs.arms` and `tail` are free.
#
# So this is its own list, and it is short on purpose: the visible body, in a player's
# words, with no number and no rule in it. Everything else the price table knows — damage
# reduction, spell resistance, immunities — is mechanics, and mechanics reach the narrator
# as tells or not at all.
#
# The two limb entries are the wording for ONE extra pair; `_limb_phrase` produces them
# and every larger count, because a race may buy as many pairs as it likes ("I should be
# able to have as many arms and legs as I want", 2026-09-08) and the reporter's asura had
# bought two — "four in all" was as wrong as "two".
VISIBLE_BODY: dict[str, str] = {
    "limbs.arms": "an extra pair of arms — four in all",
    "limbs.legs": "an extra pair of legs — four in all",
    "tail": "a tail",
    "amphibious": "gills",
}

# Small numbers read as words; past that a numeral is less silly than "seventeen".
_COUNT_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight",
                "nine", "ten", "eleven", "twelve")


def _words(n: int) -> str:
    return _COUNT_WORDS[n] if 0 <= n < len(_COUNT_WORDS) else str(n)


def _limb_phrase(base: str, total: int) -> str:
    """"two extra pairs of arms — six in all". Both halves are said because a person
    counting sees the total and a player who bought the pairs recognises the pairs."""
    kind = base.rpartition(".")[2]
    pairs = max(1, (total - PAIRED_LIMBS[base]) // 2)
    many = "an extra pair" if pairs == 1 else f"{_words(pairs)} extra pairs"
    return f"{many} of {kind} — {_words(total)} in all"


def visible_body(tag: str) -> str | None:
    """What this tag looks like to somebody standing in front of it, or None if it is
    not something they can see. Asked of the tag rather than looked up in it, because a
    counted limb is `limbs.arms.6` and no dictionary has a key for every number."""
    base, _, count = tag.rpartition(".")
    if base in PAIRED_LIMBS and count.isdigit():
        return _limb_phrase(base, int(count))
    if tag in PAIRED_LIMBS:                 # bare: one extra pair, un-expanded
        return _limb_phrase(tag, PAIRED_LIMBS[tag] + 2)
    return VISIBLE_BODY.get(tag)


def body_line(doc: dict) -> str:
    """One sentence for the narrator's brief: how this body moves, senses, looks and
    fights. A tell about the body, not a rule — the narrator dresses it."""
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
    tags = list(doc.get("tags") or [])
    # The visible body first, because it is the half a person in the room can check.
    seen = [w for w in (visible_body(t) for t in tags) if w]
    if seen:
        parts.append("plainly: " + ", ".join(seen))
    extra = [TAG_RP[t][1] for t in tags if t in TAG_RP and t not in VISIBLE_BODY
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
    # Split by how the price was arrived at, not merely by whether the table had a row.
    # `unpriced` used to mean "not one of twenty-one strings", which lumped a flight
    # speed the table can scale perfectly well in with a family nobody has ever costed.
    d["unpriced"] = [t for t in d["tags"]
                     if not t.startswith("race.") and price_tag(t)[2] == "unknown"]
    d["derived_prices"] = [f"{t} ({price_tag(t)[0]} RP, scaled)" for t in d["tags"]
                           if price_tag(t)[2] == "derived"]
    return d


# --- pricing a tag the table has never seen ---------------------------------------------
#
# `TAG_RP` is twenty-one exact strings, and the magnitude is baked into the key:
# `move.fly.30` is priced and `move.fly.40` is not, `sense.darkvision.60` and `.120` are
# priced and `.90` is not, `natural.armor.1` is priced and `.2` is not. Every miss fell
# through `TAG_RP.get(t, (0, ""))[0]` and cost **nothing**, so a world that described a
# people as flying forty feet got flight for free and the forge said the race was cheaper
# than it is.
#
# That matters more than a normal rounding error because of where the tags come from.
# Two readers of the same tag already disagreed about how robust they were: `speeds()`
# and `senses()` pull the number out with a regex and handle any value at all, while the
# price list handles twenty-one. World Bible writes worlds this app has never seen, and
# `docs/for-world-bible.md` invites it to describe a people in its own words — so the
# half that generalises is the half that was right.
#
# These derive from the shipped anchors rather than from the book directly: the Advanced
# Race Guide prices the *rows it has*, and it does not have a row for every speed. Where
# a value sits on an anchor the answer is the anchor's, unchanged. Where it sits between
# or beyond them it is scaled from the nearest, and the result is marked `derived` so the
# forge can say so rather than present a guess as a price.
_PER_TEN_FEET = {
    # rp per ten feet beyond the anchor, from the ARG's own step for that mode
    "fly": 1, "burrow": 1, "climb": 1, "swim": 1,
}
_MOVE_ANCHOR = {"fly": (30, 4), "climb": (20, 2), "swim": (30, 2), "burrow": (20, 3)}
_SENSE_ANCHOR = {
    # feet -> rp, in order; a value between two takes the lower one's price plus the step
    "darkvision": ((60, 2), (120, 3)),
    "blindsense": ((30, 4),),
    "blindsight": ((30, 6),),
    "tremorsense": ((30, 4),),
}


def natural_weapon_aliases() -> frozenset[str]:
    """Every name a natural attack answers to, off the evolution pool itself.

    `rules.intents` asks this so its weapon gate can let a bite through: the 456-weapon
    table holds no natural attacks, and until 2026-09-14 the gate refused every one of
    them before the engine could say "you have no bite".

    The singular and plural of each key and name are both accepted, the same courtesy
    `Actor.natural_weapon` extends, so "claw", "claws" and "talons" all reach the entry.
    """
    out: set[str] = set()
    for ev in evolutions().values():
        for w in ev.get("weapons") or []:
            for word in (w.get("key"), w.get("name")):
                word = " ".join(str(word or "").split()).lower()
                if not word:
                    continue
                out.add(word)
                out.add(word + "s" if not word.endswith("s") else word[:-1])
    # Aliases the sheet already honours that no document spells out.
    out |= {"talon", "talons", "fangs", "horn", "horns"}
    return frozenset(out)


def price_tag(tag: str) -> tuple[int, str, str]:
    """What a tag costs, what it reads as, and how sure we are: exact, derived, unknown.

    The third field is the point. An unknown tag used to be indistinguishable from a free
    one, and the only trace was a list nothing acted on.
    """
    tag = str(tag or "").strip().lower()
    if tag in TAG_RP:
        cost, words = TAG_RP[tag]
        return cost, words, "exact"

    m = re.match(r"^move\.(fly|climb|swim|burrow)\.(\d+)$", tag)
    if m:
        mode, feet = m.group(1), int(m.group(2))
        base_ft, base_rp = _MOVE_ANCHOR[mode]
        step = _PER_TEN_FEET[mode] * ((feet - base_ft) // 10)
        return max(1, base_rp + step), f"{mode} {feet} ft", "derived"

    m = re.match(r"^sense\.([a-z-]+)\.(\d+)$", tag)
    if m and m.group(1) in _SENSE_ANCHOR:
        kind, feet = m.group(1), int(m.group(2))
        anchors = _SENSE_ANCHOR[kind]
        best = anchors[0]
        for ft, cost in anchors:
            if feet >= ft:
                best = (ft, cost)
        extra = 1 if feet > best[0] else 0
        return best[1] + extra, f"{kind} {feet} ft", "derived"

    m = re.match(r"^natural\.armor\.(\d+)$", tag)
    if m:
        n = int(m.group(1))
        # ARG: +1 natural armour is 2 RP and each further point is 1.
        return 2 + max(0, n - 1), f"+{n} natural armour", "derived"

    m = re.match(r"^resist\.([a-z-]+)\.(\d+)$", tag)
    if m:
        return 1 + int(m.group(2)) // 5, f"resist {m.group(1)} {m.group(2)}", "derived"

    if tag.startswith("immune."):
        return 2, "immune to " + tag.split(".", 1)[1].replace(".", " "), "derived"

    # A family nobody has priced. Zero, as before — but said out loud, because the forge
    # showing a total that quietly excludes a trait is worse than one that says it cannot
    # price it.
    return 0, "", "unknown"


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
        total += price_tag(t)[0]
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
        # Once-only evolutions stay once-only; a repeatable one has no ceiling — "I
        # should be able to have as many arms and legs as I want" (2026-09-08). The
        # summoner's own per-level limits are the summoner's, not a race's.
        if int(ev.get("takes", 1) or 1) == 1 and n > 1:
            problems.append(f"{ev['name']}: may be taken once, not {n} times.")
        for need in ev.get("needs") or []:
            if need not in taken:
                problems.append(f"{ev['name']} needs {cat.get(need, {}).get('name', need)} "
                                f"first.")
    return problems


# --- from a World Bible world -----------------------------------------------------------------

# What a people is good and bad at, in six words no world needs a rules system to say.
#
# The gap this closes, measured 2026-09-10: a race card could express a size, a speed and
# twelve possible traits, and NOTHING ELSE — so every world race was handed the generic
# +2 physical / +2 mental / −2 any and differed from every other race in the world only
# in its senses. Ability modifiers are the most defining mechanical feature of a 1e race
# and the export had no channel for them at all.
#
# Words rather than numbers, because the boundary holds in both directions: World Bible
# writes what is true of a people, this side prices it. "Hardy" is a thing a world knows
# about its own peoples; Constitution is not.
#
# Exactly two strengths and one weakness, or none of it counts — the Advanced Race Guide's
# standard array is +2/+2/−2 as a unit, and half an array is not one. A partial card
# keeps the generic choose it has today, and `check_race_cards.py` says so rather than
# letting it pass unnoticed.
ABILITY_WORDS: dict[str, str] = {
    "strong": "str",        # powerful of build
    "nimble": "dex",        # quick and well-balanced
    "hardy": "con",         # resilient, hard to wear down
    "clever": "int",        # quick to learn and reason
    "perceptive": "wis",    # attentive, hard to surprise
    "commanding": "cha",    # forceful of personality
}


def array_from_words(strengths, weakness: str = "") -> tuple[dict, list]:
    """The Race Builder's standard array from a card's own words, or the generic choose.

    Returns `(mods, choose)` ready for a document. `_mods_rp` already prices a fixed
    +2/+2/−2 at 0 RP when one bonus is physical and one mental and at 1 when both sit in
    the same group — the Race Builder's own standard/specialised split — so nothing here
    needs to know what any of it costs.
    """
    want = [str(s).strip().lower() for s in (strengths or ()) if str(s).strip()]
    weak = str(weakness or "").strip().lower()
    good = [ABILITY_WORDS[w] for w in want if w in ABILITY_WORDS]
    bad = ABILITY_WORDS.get(weak, "")
    # Two distinct strengths, one weakness, and the weakness is not also a strength.
    if len(good) != 2 or len(set(good)) != 2 or not bad or bad in good:
        return {}, list(STANDARD_CHOOSE)
    return {good[0]: 2, good[1]: 2, bad: -2}, []


# What a people's own words map to. Detect mechanically, price from the table: nothing
# here reads a number out of prose, and a body the table has no line for becomes a
# `not_yet` sentence rather than a guess. Each row: a pattern over the anatomy facts,
# the tags it grants, the trait line it shows, and what still waits on the engine.
CUES: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    (r"\b(wings?|winged|fly|flight|glide|soar|airborne)\b", ("move.fly.30",),
     "fly 30 ft (clumsy)", ""),
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
    (r"\b(climb\w*|arboreal|tree-?dwell\w*)\b", ("move.climb.20",), "climb 20 ft", ""),
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
          about: str = "", origin: str = "", people_id: str = "", world: str = "",
          strengths=(), weakness: str = "") -> dict:
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
    mods, choose = array_from_words(strengths, weakness)
    if not mods and (strengths or weakness):
        # Said something, and not enough of it. Recorded where the player can see it
        # rather than silently handing back the generic array.
        not_yet.append("what this people is good and bad at: a card needs exactly two "
                       "strengths and one weakness, from " +
                       ", ".join(sorted(ABILITY_WORDS)))
    return normalise({
        "id": rid, "name": str(name).strip(),
        "description": (about or text)[:400],
        "type": "humanoid", "size": size, "speed": speed,
        "mods": mods, "choose": choose,
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
                             strengths=raw.get("strengths") or (),
                             weakness=str(raw.get("weakness") or ""),
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
        "attacks": ["unarmed strike", "bite", "claws", "gore", "slam", "pincers", "sting",
                    "tail slap", "tentacle", "wing buffet"],
        "budget": list(BUDGET_RP),
        "tiers": list(TIERS),
    }
