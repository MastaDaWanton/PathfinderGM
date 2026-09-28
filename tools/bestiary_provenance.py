"""Where the shipped creatures came from, and which of them carry somebody's name.

A measuring stick for the licensing question in docs/bestiary-licensing.md, read-only:
it changes no content. `content/bestiary/creatures.json` was imported from an NPC
database whose rows are mostly adventure characters, and Paizo's adventure declarations
make proper names Product Identity while opening only the mechanics. Which options are
open depends on how many rows are which — so the counts are computed, not remembered.

    python tools/bestiary_provenance.py              # the summary tables
    python tools/bestiary_provenance.py --sample 40  # plus random rows per verdict, to hand-check

Two classifications, both approximate and both reported with that said:

- **Family** is decided from the `source` string by an explicit table below. The
  spreadsheet's source strings are its own ("AP 109", "PFS S1-52", "Rappan Athuk-Level
  12A"); the grouping into Paizo product lines is this file's, and a source not in the
  table lands in `unclassified` rather than being guessed into a family.
- **Name** is decided per token. A token is *common* if it appears lower-case somewhere
  in the shipped rules prose (spell, feat and ability text): a proper name is always
  capitalised, a monster or a job is not ("a fungal crawler can", "15th-level wizard").
  A name with any uncommon token is *named*; of those, a token that recurs across three
  or more unrelated sources is taken as a setting word ("Varisian", "Hellknight") rather
  than a person, which is the same line rules/npcs.py draws for its own name stripping.
"""
from __future__ import annotations

import collections
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- families ----------------------------------------------------------------------------------

# Explicit, so a new source has to be placed on purpose. Product lines are Paizo's own
# (Adventure Path, Pathfinder Society, Module, Campaign Setting, Player Companion, the
# Roleplaying Game rulebooks); the third-party books are Frog God Games.
RULEBOOK = {
    "NPC Codex", "Villain Codex", "Monster Codex", "Game Mastery Guide",
    "PFRPG Bestiary 3", "PFRPG Bestiary 5", "PFRPG Bestiary 6", "Mythic Adventures",
}
SETTING = {
    "Academy Of Secrets", "Andoran", "Andoran Birthplace Of Freedom",
    "Castles Of The Inner Sea", "Classic Horrors", "Darklands Revisited",
    "Demons Revisited", "Distant Shores", "Dragons Unleashed", "Dungeons Of Golarion",
    "Fey Revisited", "From Shore To Sea", "Giants Revisited", "Gnomes Of Golarion",
    "Heaven Unleashed", "Hell Unleashed", "Inner Sea Monster Codex", "Inner Sea NPC Codex",
    "Inner Sea Temples", "Irrisen Land Of Eternal Winter", "Isles Of The Shackles",
    "Lands Of Conflict", "Lost Cities Of Golarion", "Lost Kingdoms",
    "Magnimar City Of Monuments", "Monster Summoner's Handbook", "Mystery Monsters Revisited",
    "Mythic Realms", "Mythical Monsters Revisited", "NPC Guide", "NPC Guide Web",
    "Numeria Land Of Fallen Stars", "Osirion, Legacy Of Pharaohs", "Rival Guide",
    "Sandpoint, Light Of The Lost Coast", "Seekers of Secrets", "Ships Of The Inner Sea",
    "The Worldwound", "Tombs Of Golarion", "Towns Of The Inner Sea", "Undead Revisited",
    "Undead Unleashed",
}
MODULE = {
    "Broken Chains", "Carrion Hill", "City of Golden Death", "Crypt Of The Everflame",
    "Cult Of The Ebon Destroyers", "Curse of the Riven Sky", "Daughters Of Fury",
    "Dawn Of The Scarlet Sun", "Doom Comes To Dustpawn", "Fangwood Keep", "Feast Of Dust",
    "Gallows Of Madness", "Godsmouth Heresy", "Ire Of The Storm", "Masks Of The Living God",
    "Master of the Fallen Fortress", "Murder's Mark", "No Response From Deepmar",
    "Plunder & Peril", "Realm of the Fellnight Queen", "Risen From The Sands",
    "Seers Of The Drowned City", "Tears At Bitter Manor", "The Dragon's Demand",
    "The Emerald Spire", "The Feast Of Ravenmoor", "The Harrowing", "The House On Hook Street",
    "The Midnight Mirror", "The Moonscar", "The Ruby Phoenix Tournament",
    "The Witchwar Legacy", "Thornkeep", "Tomb Of The Iron Medusa",
    "Wardens Of The Reborn Forge", "We B4 Goblins", "We Be 5uper Goblins",
    "We Be Goblins Free", "We Be Goblins Too", "We Be Goblins!",
}
ADVENTURE_PATH = re.compile(
    r"^(AP \d+|Curse Of The Crimson Throne Chapter|RotRL-AE-|Shatterd Star Web|"
    r"Hells Vengeance Player's Guide|Shattered Star Player's Guide|"
    r"War For The Crown Player's Guide)")
SOCIETY = re.compile(r"^PFS ")
THIRD_PARTY = re.compile(r"^(Rappan Athuk|Sword of Air|The Lost City of Barakus|Tome of Horrors)")

FAMILIES = ("Adventure Path", "Society scenario", "Module", "Campaign Setting / Companion",
            "Rulebook", "Third party (Frog God)", "unclassified")


def family(source: str) -> str:
    s = str(source or "").strip()
    if ADVENTURE_PATH.match(s):
        return "Adventure Path"
    if SOCIETY.match(s):
        return "Society scenario"
    if s in MODULE:
        return "Module"
    if s in SETTING:
        return "Campaign Setting / Companion"
    if s in RULEBOOK:
        return "Rulebook"
    if THIRD_PARTY.match(s):
        return "Third party (Frog God)"
    return "unclassified"


# --- names -------------------------------------------------------------------------------------

# The spreadsheet's own disambiguators: "Guarin Tier 6-7", "Seelah Level 1",
# "Elder Witchlight 2". Not part of anybody's name.
_SUFFIX = re.compile(r"\s+(?:tier|teir|subtier|level)\s*\d+(?:\s*-\s*\d+)?\s*$|\s+\d+\s*$", re.I)
_WORD = re.compile(r"[A-Za-z][A-Za-z']*")
_JOINERS = {"of", "the", "a", "an", "and", "in", "on", "at", "to", "for", "with", "from"}


def _prose() -> list[str]:
    """Every rules paragraph the app ships, for learning which words are common nouns."""
    out = []
    spells = json.loads((ROOT / "content/spells/spells.json").read_text(encoding="utf-8"))
    out += [s.get("description") or "" for s in spells["spells"]]
    feats = json.loads((ROOT / "content/feats/feats.json").read_text(encoding="utf-8"))
    for f in feats["feats"]:
        out += [f.get(k) or "" for k in ("description", "benefit", "normal", "special")]
    for rel in ("content/bestiary/creatures.json", "content/bestiary/core.json"):
        data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        for c in data["creatures"]:
            out += [str(c.get(k) or "") for k in ("special_abilities", "special_attacks",
                                                  "melee", "ranged", "spell_like")]
    return out


# The galleries whose names are job descriptions by design ("Sea Captain", "Knight
# Tyrant", "Kobold Sniper"). Rules prose alone left "surgeon", "marauder" and "champion"
# out of the common set — 9 of 50 sampled "personal names" were jobs like these — so the
# galleries' own words are added. Their few real names are the iconics, which the
# spreadsheet marks with a level suffix ("Seelah Level 1"), and those are kept out.
GALLERIES = ("NPC Codex", "Villain Codex", "Monster Codex", "Game Mastery Guide")
_LEVELLED = re.compile(r"\blevel\s*\d+\s*$", re.I)


def common_words(creatures: list[dict]) -> set[str]:
    """Words seen lower-case mid-text at least twice (a name never is), the job words of
    the generic galleries, and the printed Bestiaries' creature names."""
    seen = collections.Counter()
    for text in _prose():
        for m in re.finditer(r"(?<=[a-z,;:] )([a-z][a-z']+)", text):
            seen[m.group(1).removesuffix("'s").rstrip("'")] += 1
    out = {w for w, n in seen.items() if n >= 2}
    for c in creatures:
        if c["source"] in GALLERIES and not _LEVELLED.search(c["name"]):
            out.update(t.lower().removesuffix("'s") for t in name_tokens(c["name"]))
    core = json.loads((ROOT / "content/bestiary/core.json").read_text(encoding="utf-8"))
    for c in core["creatures"]:
        out.update(t.lower().removesuffix("'s") for t in name_tokens(c["name"]))
    return out


def name_tokens(name: str) -> list[str]:
    bare = _SUFFIX.sub("", str(name or "")).strip()
    return [t for t in _WORD.findall(bare)]


def classify(creatures: list[dict]) -> dict[str, str]:
    """id -> "generic" | "setting word" | "personal name"."""
    common = common_words(creatures)

    def uncommon(tok: str) -> bool:
        low = tok.lower().removesuffix("'s")
        if low in _JOINERS or low in common:
            return False
        # "Kobolds", "Guards": a plural of a common word is common.
        if low.endswith("s") and low[:-1] in common:
            return False
        return True

    # How many unrelated sources use each uncommon token. Tier/level variants of one
    # person share a source, so a person's name counts once.
    spread: dict[str, set] = collections.defaultdict(set)
    for c in creatures:
        for t in name_tokens(c["name"]):
            if uncommon(t):
                spread[t.lower()].add(family(c["source"]) + "|" + str(c["source"]))
    out = {}
    for c in creatures:
        odd = [t for t in name_tokens(c["name"]) if uncommon(t)]
        if not odd:
            out[c["id"]] = "generic"
        elif all(len(spread[t.lower()]) >= 3 for t in odd):
            out[c["id"]] = "setting word"
        else:
            out[c["id"]] = "personal name"
    return out


# --- report ------------------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    data = json.loads((ROOT / "content/bestiary/creatures.json").read_text(encoding="utf-8"))
    creatures = data["creatures"]
    verdict = classify(creatures)
    fam = {c["id"]: family(c["source"]) for c in creatures}

    kinds = ("generic", "setting word", "personal name")
    table = collections.defaultdict(collections.Counter)
    prose_rows = collections.Counter()
    prose_chars = collections.Counter()
    sources = collections.defaultdict(set)
    for c in creatures:
        f = fam[c["id"]]
        table[f][verdict[c["id"]]] += 1
        sources[f].add(c["source"])
        if c.get("special_abilities"):
            prose_rows[f] += 1
            prose_chars[f] += len(c["special_abilities"])

    print(f"{len(creatures)} creatures, {len({c['source'] for c in creatures})} sources\n")
    head = f"{'family':32}{'rows':>6}{'srcs':>6}" + "".join(f"{k:>15}" for k in kinds)
    head += f"{'SA rows':>9}{'SA chars':>11}"
    print(head)
    total = collections.Counter()
    for f in FAMILIES:
        if not table[f]:
            continue
        n = sum(table[f].values())
        row = f"{f:32}{n:>6}{len(sources[f]):>6}" + "".join(f"{table[f][k]:>15}" for k in kinds)
        row += f"{prose_rows[f]:>9}{prose_chars[f]:>11,}"
        print(row)
        total.update(table[f])
    print(f"{'total':32}{sum(total.values()):>6}{'':>6}"
          + "".join(f"{total[k]:>15}" for k in kinds)
          + f"{sum(prose_rows.values()):>9}{sum(prose_chars.values()):>11,}")
    odd = sorted(sources["unclassified"])
    if odd:
        print("\nunclassified sources:", ", ".join(odd))

    if "--sample" in argv:
        k = int(argv[argv.index("--sample") + 1])
        rng = random.Random(20260927)
        for v in kinds:
            pool = [c for c in creatures if verdict[c["id"]] == v]
            print(f"\n--- {v}: {k} of {len(pool)} ---")
            for c in rng.sample(pool, min(k, len(pool))):
                print(f"  {c['name']!r:44} {c['source']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
