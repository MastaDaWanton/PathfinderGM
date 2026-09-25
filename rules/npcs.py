"""People for a role: the codex chooser and the NPC codex store.

docs/npc-codex.md is the design of record; docs/quest-schemes-plan.md §6.3 is where it
was asked for. A scheme slot says "a guard officer" or "someone of standing" and never
a name; the world's cast supplies the person, and this module supplies the numbers —
a stat block out of the seven thousand the bestiary already holds, chosen by role
words and challenge rating near the party's level, from the most generic source that
has anyone fitting.

Two rules shaped everything here:

- **A model authors no number.** The chooser is a sort over an index built from the
  content files. Nothing is asked to invent a captain; one is found, and the same words
  and level find the same one every time.
- **Numbers, never story.** An adventure-path block named "Jevana Drow Noble Priestess"
  is a good stat block for a noble priestess and a terrible source of who she is. Her
  name is stripped, her numbers are kept, and the world's own cast member wears them.

The codex store is one JSON per world entity under `homebrew/npcs/`, so a person the
player met last week has the same numbers this week, and a person the table wants
corrected is one file on the NPCs bench.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import bestiary
from . import registry
from pathfindergm import files

# --- source ranking ----------------------------------------------------------------------------

# Lower is more generic. Tier 0 are the galleries of people by job: their names ARE
# role descriptions ("Border Guard", "Guard Officer", "Sea Captain") and their numbers
# were built to be anybody's. Tier 1 are organised villains and the monstrous peoples'
# own specialists — still generic, still shaped for a fight the author expected. Tier 2
# is everyone else: a specific person from a specific story, whose name is stripped
# before the block is offered as a role. The core Bestiary is tier 3: it has almost no
# people in it, and the few it has are the species' plain stat block.
_GENERIC = ("NPC Codex", "Inner Sea NPC Codex", "Game Mastery Guide")
_ORGANISED = ("Villain Codex", "Monster Codex", "Inner Sea Monster Codex",
              "NPC Guide", "NPC Guide Web")
_BESTIARY = re.compile(r"^Bestiary", re.I)


def source_rank(source: str) -> int:
    s = str(source or "").strip()
    if s in _GENERIC:
        return 0
    if s in _ORGANISED:
        return 1
    if _BESTIARY.match(s):
        return 3
    return 2


# Tiered duplicates. Pathfinder Society writes one block per subtier and the NPC Codex
# writes the iconics at three levels; the spreadsheet carries them as separate ids with
# a suffix, misspelt in four cases ("teir"). They are one person with a level ladder.
_TIER = re.compile(r"-(?:tier|teir|subtier|level)-\d+(?:-\d+)?$")
_PEOPLE_TYPES = ("humanoid",)
_PEOPLE_SIZES = ("small", "medium", None, "")
# A proper name is a token that almost nothing else in the bestiary shares. Measured
# over the 7,136 ids: 5,877 of the 6,778 distinct tokens appear in fewer than three
# entries, and every one sampled was a name ("jevana" 2, "trillok" 1, "vorg" 1,
# "gortus" 1, "absalom" 2) while every job word cleared it ("captain" 62, "guard" 105,
# "priest" 50, "noble" 11, "drow" 17). Three is the line. Applied only to tier 2 and 3
# blocks: a gallery name is all description, and stripping "shopkeeper" (1) from the one
# Game Mastery Guide shopkeeper would lose the block for the very word that finds it.
_RARE = 3
_JOINERS = ("of", "the", "a", "an", "and")

# The three hand-written townsfolk, and which words send a role to which. The floor
# when the codex has nobody: a role nobody wrote a block for still gets numbers.
_FLOOR_WORDS = {
    "watchman": ("guard", "watch", "captain", "sergeant", "officer", "soldier",
                 "constable", "warden"),
    "thug": ("thug", "bandit", "cutthroat", "ruffian", "bravo", "enforcer", "brigand"),
}

# The index, built once per bestiary load. Keyed on the identity of the bestiary's own
# cache rather than declared `_INDEX: ... | None = None`, so it rebuilds exactly when
# the bestiary does (a test moving CAMPAIGN_DIR drops `bestiary._IMPORTED`, and the
# next read here sees a different object) without needing an entry in conftest.
_BUILT: tuple = ()


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9']+", str(text or "").lower()) if t]


def _base_id(block_id: str) -> str:
    return _TIER.sub("", str(block_id or "").strip().lower())


def index() -> dict[str, dict]:
    """Every humanoid-shaped block, collapsed by tier, keyed by base id.

    Each entry: `base`, `name` (the lowest rung's, suffix gone), `tokens`, `rank`,
    `source`, `ladder` = [(cr_value, block_id), ...] ascending. Hand-written townsfolk
    are not in here; they are the floor, reached by `choose` when nothing matches.
    """
    global _BUILT
    imported = bestiary.imported()
    if _BUILT and _BUILT[0] is imported:
        return _BUILT[1]
    out: dict[str, dict] = {}
    for bid, c in imported.items():
        if c.get("creature_type") not in _PEOPLE_TYPES:
            continue
        if c.get("size") not in _PEOPLE_SIZES:
            continue
        cr = c.get("cr_value")
        if cr is None:
            continue
        base = _base_id(bid)
        entry = out.get(base)
        if entry is None:
            entry = out[base] = {
                "base": base, "name": _TIER.sub("", str(c.get("name") or base)).strip(),
                "tokens": _tokens(base), "source": str(c.get("source") or ""),
                "rank": source_rank(c.get("source")), "ladder": [],
            }
        entry["ladder"].append((float(cr), bid))
        # The iconics sit in the NPC Codex at three levels and in the Society pregens at
        # two more, under one base id: the most generic source on the ladder ranks it.
        entry["rank"] = min(entry["rank"], source_rank(c.get("source")))
    freq: dict[str, int] = {}
    for e in out.values():
        for t in set(e["tokens"]):
            freq[t] = freq.get(t, 0) + 1
    for e in out.values():
        e["ladder"].sort()
        e["role"] = _display_role(e, freq)
    _BUILT = (imported, out)
    return out


def _display_role(entry: dict, freq: dict[str, int]) -> str:
    """The name as a role: a gallery name whole, a story name with the person removed."""
    if entry["rank"] < 2:
        return " ".join(entry["tokens"])
    kept = [t for t in entry["tokens"] if freq.get(t, 0) >= _RARE]
    # "Caleb Voltiaro Vicar of the Indomitable Sea" strips to "of the sea": the joining
    # words survive the count and the name they joined does not. Trim them off the ends.
    while kept and kept[0] in _JOINERS:
        kept.pop(0)
    while kept and kept[-1] in _JOINERS:
        kept.pop()
    return " ".join(kept)


def strip_name(block_id: str) -> str:
    """What a block is usable as: "jevana-drow-noble-priestess" -> "drow noble priestess".

    Empty when nothing but a name is left ("abra-lopati"), which is the honest answer:
    that block is somebody, not something."""
    e = index().get(_base_id(block_id))
    return e["role"] if e else ""


def ladder(block_id: str) -> list[tuple[float, str]]:
    e = index().get(_base_id(block_id))
    return list(e["ladder"]) if e else []


def humanoid_count() -> int:
    """How many collapsed people the chooser can draw from."""
    return len(index())


# --- choosing -----------------------------------------------------------------------------------

def _words(role_words) -> list[str]:
    if isinstance(role_words, str):
        role_words = role_words.replace("-", " ").split()
    out: list[str] = []
    for w in role_words or ():
        for t in _tokens(w):
            if t not in out:
                out.append(t)
    return out


def _hits(word: str, tokens: list[str]) -> bool:
    # "priest" finds "priestess", "guard" finds "guards" and "guardsman"; a short word
    # matches only itself and its plural, so "kin" cannot find "kingpin".
    for t in tokens:
        if t == word or t == word + "s" or t == word + "es":
            return True
        if len(word) >= 5 and t.startswith(word):
            return True
    return False


def target_cr(level: int) -> float:
    """A character of class level L is CR L-1 (Bestiary, "Creating NPCs"); the party's
    peer at 1st level is a CR 1/2 warrior, not a CR 1 one."""
    return max(0.5, float(int(level or 1)) - 1.0)


def _nearest(ladder: list[tuple[float, str]], want: float) -> tuple[float, str]:
    return min(ladder, key=lambda rung: (abs(rung[0] - want), rung[0]))


def floor_for(role_words) -> str:
    words = _words(role_words)
    for template, keys in _FLOOR_WORDS.items():
        if any(_hits(k, words) for k in keys):
            return template
    return "guildhand"


# "Near the level" is a band, not a point. The encounter table (Core Rulebook, "Designing
# Encounters") calls CR = APL-1 .. APL+1 easy to average, and up to APL+3 epic; beyond
# that a match is the wrong person, however apt the name. Measured before the cap: a
# 1st-level party's "someone of standing" was the CR 6 Village Elder and their guard
# officer the CR 6 Watch Captain — right words, a fight nobody at the table could have.
# Past the cap the townsfolk floor is nearer than any block, so it is what they get.
MAX_DISTANCE = 3.0


def choose(role_words, level: int, *, prefer_named: bool = False) -> dict | None:
    """The stat block for a role near a level. Deterministic.

    Order of preference, in one sort: the most generic source that has anyone matching
    a word within MAX_DISTANCE of CR level-1 (`prefer_named` puts the story blocks
    first instead — for a rival who should not be "Guard"); then the words matched,
    weighted by their order — the caller's first word counts most, and matching two
    beats matching one; then within a CR of the target before further out; then the
    rung nearest the target; then the block with the fewest words that were NOT asked
    for ("Guard" over "Caravan Guard" over "First Guard of Absalom"); then the id.

    Nothing matching, or nothing near enough: the townsfolk floor — watchman for
    guard-shaped words, thug for thug-shaped ones, guildhand for everyone else — so a
    role always has numbers, and the display role is the words that were asked.
    """
    words = _words(role_words)
    want = target_cr(level)
    weight = {w: len(words) - i for i, w in enumerate(words)}
    best = None
    if words:
        for e in index().values():
            matched = [w for w in words if _hits(w, e["tokens"])]
            if not matched:
                continue
            cr, bid = _nearest(e["ladder"], want)
            dist = abs(cr - want)
            if dist > MAX_DISTANCE:
                continue
            rank = e["rank"]
            if prefer_named:
                rank = 0 if rank == 2 else rank + 1
            unmatched = sum(1 for t in e["tokens"] if not any(_hits(w, [t]) for w in words))
            key = (rank, -sum(weight[w] for w in matched), 0 if dist <= 1.0 else 1,
                   dist, unmatched, e["base"])
            if best is None or key < best[0]:
                best = (key, e, cr, bid, matched)
    if best is None:
        template = floor_for(words)
        return {"id": template, "name": template, "role": " ".join(words) or template,
                "source": "hand-written", "cr": "", "cr_value": None,
                "ladder": [], "matched": [], "floor": True}
    _, e, cr, bid, matched = best
    block = bestiary.imported().get(bid, {})
    return {"id": bid, "name": str(block.get("name") or e["name"]),
            "role": e["role"] or " ".join(matched), "source": e["source"],
            "cr": str(block.get("cr") or cr), "cr_value": cr,
            "ladder": list(e["ladder"]), "matched": matched, "floor": False}


# --- the codex store -----------------------------------------------------------------------------

def _dir(make: bool = False) -> Path:
    # The same folder the registry's `npcs` kind reads, so a remembered person is a row
    # on the bench and opens in its editor. One definition of where, not two.
    return registry.homebrew_dir("npcs", make=make)


def _path(world_entity_id: str, make: bool = False) -> Path | None:
    wid = re.sub(r"[^a-z0-9_.-]+", "-", str(world_entity_id or "").strip().lower()).strip("-")
    if not wid:
        return None
    try:
        return files.child(_dir(make=make), wid)
    except files.BadName:
        return None


def remember(world_entity_id: str, block_id: str, name: str, *, role: str = "",
             description: str = "") -> Path | None:
    """Pin a world character to a stat block. Overwrites: the bench is the editor."""
    path = _path(world_entity_id, make=True)
    if path is None:
        return None
    entry = {"id": path.stem, "name": str(name or ""), "description": str(description or ""),
             "creature": str(block_id or ""), "world_entity_id": str(world_entity_id),
             "role": str(role or "")}
    files.write_text(path, json.dumps(entry, indent=1, ensure_ascii=False))
    return path


def recall(world_entity_id: str) -> dict | None:
    """The entry for a world character, or None. A file that cannot be read is None too:
    a bad edit on the bench must not stop a scheme opening."""
    path = _path(world_entity_id)
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) and data.get("creature") else None


def forget(world_entity_id: str) -> bool:
    path = _path(world_entity_id)
    if path is None or not path.is_file():
        return False
    path.unlink()
    return True


def remembered() -> dict[str, dict]:
    """Every entry the store holds, keyed by file stem."""
    out: dict[str, dict] = {}
    for path in sorted(_dir().glob("*.json")) if _dir().is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            out[path.stem] = data
    return out


def block_for(world_entity_id: str, role_words, level: int, name: str, *,
              prefer_named: bool = False) -> str:
    """The template a world character plays as: what the codex remembers if that block
    still exists, else what the chooser picks — remembered on the way out."""
    known = recall(world_entity_id)
    if known and bestiary.lookup(str(known.get("creature") or "")) is not None:
        return str(known["creature"])
    got = choose(role_words, level, prefer_named=prefer_named) or {}
    template = str(got.get("id") or "guildhand")
    remember(world_entity_id, template, name, role=str(got.get("role") or ""))
    return template
