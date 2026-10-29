"""The five NPC classes of the Core Rulebook, as class documents.

Chapter 14, "Creating NPCs" (CRB pp. 448-451): "Aside from the players, every other person
encountered in the game world is a nonplayer character ... While some of these characters
use player classes, most rely upon basic NPC classes." Read from the book (2026-10-28) and
written once here, so the numbers are the printed tables' and the code that derives an
actor's BAB, saves and hit dice off a class document (`rules/classes.py`) reads them as it
reads a fighter's:

    class        HD   BAB            good save   skills  proficiency
    adept        d6   half           Will        2       simple weapons; no armour
    aristocrat   d8   three_quarter  Will        4       simple, martial; all armour, shields
    commoner     d6   half           none        2       ONE simple weapon (a pick)
    expert       d8   three_quarter  Will        6       simple; light armour; ANY 10 skills
    warrior      d10  full           Fort        2       simple, martial; all armour, shields

Two of them choose: the commoner's one simple weapon and the expert's ten class skills are
class-option catalogues (content/class-options/), each pick carrying the tag or class skill
it grants. The adept casts divine spells off Wisdom from its own printed list (Table 14-1,
the "Adept Spell List"), declared in its document because no spell in the corpus lists it.

    python tools/build_npc_classes.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from rules import tables, weapons  # noqa: E402

SOURCE = "Core Rulebook, Chapter 14: Creating NPCs, pp. 448-451"
KNOWLEDGE = [s for s in tables.SKILLS if s.startswith("knowledge (")]

ADEPT_SPELLS = {
    "0": ["create water", "detect magic", "ghost sound", "guidance", "light", "mending",
          "purify food and drink", "read magic", "stabilize", "touch of fatigue"],
    "1": ["bless", "burning hands", "cause fear", "command", "comprehend languages",
          "cure light wounds", "detect chaos", "detect evil", "detect good", "detect law",
          "endure elements", "obscuring mist", "protection from chaos",
          "protection from evil", "protection from good", "protection from law", "sleep"],
    "2": ["aid", "animal trance", "bear's endurance", "bull's strength", "cat's grace",
          "cure moderate wounds", "darkness", "delay poison", "invisibility", "mirror image",
          "resist energy", "scorching ray", "see invisibility", "web"],
    "3": ["animate dead", "bestow curse", "contagion", "continual flame",
          "cure serious wounds", "daylight", "deeper darkness", "lightning bolt",
          "neutralize poison", "remove curse", "remove disease", "tongues"],
    "4": ["cure critical wounds", "minor creation", "polymorph", "restoration", "stoneskin",
          "wall of fire"],
    "5": ["baleful polymorph", "break enchantment", "commune", "heal", "major creation",
          "raise dead", "true seeing", "wall of stone"],
}


def _levels(grants: dict[int, list[str]]) -> list[dict]:
    return [{"level": n, "grants": list(grants.get(n, []))} for n in range(1, 21)]


def classes() -> list[dict]:
    common = {"npc": True, "source": SOURCE}
    return [
        {**common, "id": "adept", "name": "Adept", "hit_die": 6, "bab": "half",
         "good_saves": ["will"], "skill_ranks": 2,
         "proficiencies": ["simple"],
         "class_skills": ["craft", "handle animal", "heal", *KNOWLEDGE, "profession",
                          "spellcraft", "survival"],
         "summary": "A village priest, hedge witch or shaman: divine spells off Wisdom from "
                    "a short list of its own, and a familiar from 2nd level.",
         "casting": {"ability": "wis", "kind": "prepared", "progression": "adept",
                     "list": "adept", "prepare_from": "list",
                     "note": "An adept prays an hour a day for her spells, from her own list.",
                     "spell_list": ADEPT_SPELLS},
         "levels": _levels({2: ["summon familiar"]})},
        {**common, "id": "aristocrat", "name": "Aristocrat", "hit_die": 8,
         "bab": "three_quarter", "good_saves": ["will"], "skill_ranks": 4,
         "proficiencies": ["simple", "martial", "light armor", "medium armor",
                           "heavy armor", "shields", "tower shields"],
         "class_skills": ["appraise", "bluff", "craft", "diplomacy", "disguise",
                          "handle animal", "intimidate", *KNOWLEDGE, "linguistics",
                          "perception", "perform", "profession", "ride", "sense motive",
                          "survival", "swim"],
         "summary": "Born to rank: trained in arms and armour, and in the arts of being obeyed.",
         "levels": _levels({})},
        {**common, "id": "commoner", "name": "Commoner", "hit_die": 6, "bab": "half",
         "good_saves": [], "skill_ranks": 2, "proficiencies": [],
         "class_skills": ["climb", "craft", "handle animal", "perception", "profession",
                          "ride", "swim"],
         "summary": "Farmer, drover, labourer: proficient with one simple weapon and nothing else.",
         "choices": [{"id": "weapon proficiency", "name": "Weapon proficiency", "level": 1,
                      "text": "The commoner is proficient with one simple weapon (CRB p. 449).",
                      "options": [{"kind": "class option", "from": "commoner-weapons",
                                   "how_many": 1}]}],
         "levels": _levels({})},
        {**common, "id": "expert", "name": "Expert", "hit_die": 8, "bab": "three_quarter",
         "good_saves": ["will"], "skill_ranks": 6,
         "proficiencies": ["simple", "light armor"],
         "class_skills": [],
         "summary": "A craftsman, sage or guide: any ten skills of his own choosing.",
         "choices": [{"id": "class skills", "name": "Class skills", "level": 1,
                      "text": "The expert can choose any 10 skills to be class skills "
                              "(CRB p. 450).",
                      "options": [{"kind": "class option", "from": "expert-skills",
                                   "how_many": 10}]}],
         "levels": _levels({})},
        {**common, "id": "warrior", "name": "Warrior", "hit_die": 10, "bab": "full",
         "good_saves": ["fort"], "skill_ranks": 2,
         "proficiencies": ["simple", "martial", "light armor", "medium armor",
                           "heavy armor", "shields", "tower shields"],
         "class_skills": ["climb", "craft", "handle animal", "intimidate", "profession",
                          "ride", "swim"],
         "summary": "A guard, soldier or brute: every weapon and armour, and little else.",
         "levels": _levels({})},
    ]


def catalogues() -> list[dict]:
    simple = sorted(k for k, v in weapons.all_weapons().items()
                    if v.get("prof") == "simple" and k != "unarmed")
    return [
        {"id": "commoner-weapons", "name": "Commoner weapon proficiency", "source": SOURCE,
         "_unconfirmed": [], "rules": {},
         "options": [{"id": k, "name": weapons.get(k)["name"],
                      "text": f"Proficient with the {weapons.get(k)['name'].lower()}.",
                      "requires": [], "tags": [f"proficient.weapon.{k}"]} for k in simple]},
        {"id": "expert-skills", "name": "Expert class skills", "source": SOURCE,
         "_unconfirmed": [], "rules": {},
         "options": [{"id": s.replace(" ", "-").replace("(", "").replace(")", ""),
                      "name": s.title(), "text": f"{s.title()} is a class skill.",
                      "requires": [], "class_skill": s} for s in tables.SKILLS]},
    ]


def main() -> None:
    out = ROOT / "content" / "npc-classes"
    out.mkdir(parents=True, exist_ok=True)
    for c in classes():
        (out / f"{c['id']}.json").write_text(json.dumps(c, indent=1, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
    for cat in catalogues():
        (ROOT / "content" / "class-options" / f"{cat['id']}.json").write_text(
            json.dumps(cat, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", ", ".join(c["id"] for c in classes()), "and", len(catalogues()), "catalogues")


if __name__ == "__main__":
    main()
