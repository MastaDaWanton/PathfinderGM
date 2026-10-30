"""Apply tools/golarion_rewrites.py to the shipped spells, feats and weapons.

    python tools/strip_golarion.py            # rewrite the shipped files in place
    python tools/strip_golarion.py --check    # report what would change, write nothing

One pass, idempotent: run twice, the second run changes nothing. It rewrites

- content/spells/spells.json and content/feats/feats.json (the rows themselves),
- content/weapons/weapons.json (two weapon names) and the one key
  content/rules/base-pieces.json gives the bolas,
- the spell mechanics files keyed by spell id (content/spells/mechanics/part-*.json and
  content/spells/spells-mechanics.json), whose own prose quotes the old names,

and writes content/spells/aliases.json and content/feats/aliases.json: old id (and, for a
feat, old lower-cased name) -> the id a save holding it reads now, null when the row was
dropped. Those two files are the one place the old names are kept, for the same reason
content/bestiary/aliases.json keeps the bestiary's: a save written before this must still
load (docs/bestiary-licensing.md §7).

Since 2026-10-30 it rewrites the bestiary too (`golarion_rewrites.apply_bestiary`):
content/bestiary/core.json, creatures.json and mounts.json, in place. A renamed
creature's old id goes into content/bestiary/aliases.json hashed (`bestiary.alias_key`),
as that file keeps every id option D removed, so the old name sits in no shipped file;
and every existing alias that landed on a renamed id is pointed at the new one, because
`bestiary.alias_of` takes one hop. compiled.json is generated from the printed blocks:
run tools/compile_bestiary.py after this.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

import golarion_rewrites as gr  # noqa: E402

SPELLS = ROOT / "content" / "spells" / "spells.json"
FEATS = ROOT / "content" / "feats" / "feats.json"
WEAPONS = ROOT / "content" / "weapons" / "weapons.json"
PIECES = ROOT / "content" / "rules" / "base-pieces.json"
MECHANICS = sorted((ROOT / "content" / "spells" / "mechanics").glob("part-*.json"))
MACHINE = ROOT / "content" / "spells" / "spells-mechanics.json"
BESTIARY = ROOT / "content" / "bestiary"
# mounts.json is hand-written and laid out by hand, and names nothing to rewrite;
# tests/test_no_golarion_names.py holds it there rather than this tool reflowing it.
CREATURE_FILES = [BESTIARY / n for n in ("core.json", "creatures.json")]

# This project's own sentences about a renamed spell that name what the spell's text no
# longer does; matched exactly, like the table's edits.
MECHANICS_EDITS: dict[str, list[tuple[str, str]]] = {
    "bind-sage": [("though some reclusive scholars in Kaer Maga know titles",
                   "though some reclusive scholars know titles")],
    "bloodsworn-retribution": [("the worked example about Stigur and the bandit leader",
                                "the worked example about the bandit leader")],
    "curse-item": [("A cleric of Groetus using an affected item",
                    "A cleric of a god of the end times using an affected item")],
    "create-variant-mummy": [("or an Osirian tomb guardian", "or a desert tomb guardian")],
    "create-drug": [("A lawful evil worshipper of Mahathallah may instead",
                     "A lawful evil worshipper of a goddess of illusions may instead")],
    "early-judgment": [("under Pharasma's gaze", "under the gaze of the god of death")],
    "fairness": [("The symbol of Abadar appears",
                  "The symbol of a god of law and commerce appears")],
    "fable-tapestry": [("six named Varisian folktale characters", "six named folktale "
                                                                  "characters")],
    "harrowing": [("Using a Harrow deck,", "Using a fortune-telling deck,")],
    "hallucinatory-decor": [("Members of the Prophet of Kalistrade prestige class",
                             "Members of an ascetic merchant-prophets' prestige class")],
    "infernal-challenger": [("administering a Hellknight test",
                             "administering a knightly order's test")],
    "cursed-snake-sigil": [("which of the seven Thassilonian schools",
                            "which of the seven schools of sin magic")],
    "defending-sword-mass": [("(the description still calls it by its older name, Aroden's "
                              "defending sword)", "(defending sword)")],
    "judgment-undone": [("undoes Pharasma's judgment", "undoes the judgment of the dead"),
                        ("a powerful agent of Pharasma; a worshipper of Pharasma who casts",
                         "a powerful agent of the god of death; a worshipper of the god of "
                         "death who casts")],
    "mirror-sight": [("The Urion Petresky passage is a worked example",
                      "The spy-and-queen passage is a worked example")],
    "oath-of-justice": [("swear an oath in Kols's name",
                         "swear an oath in the name of a god of oaths")],
    "mirror-mantis": [("but still sees the Red Mantis.", "but still sees the assassin.")],
    "protection-from-spores": [("created by the seeded, by the spell what grows within, or by "
                                "Xhamen-Dor.", "created by the seeded or by the fungal powers "
                                               "they serve.")],
    "speak-local-language": [("- Varisian, Taldane, Tien and the like -",
                              "- Common, a local trade tongue and the like -"),
                             ("such as Ancient Osiriani or Jistka",
                              "such as the tongue of a fallen empire")],
    "soulseeker": [("beneath the boughs of the Witchwood", "beneath the boughs of its great "
                                                           "forest")],
    "soul-vault": [("Any spellcaster who worships Abadar may learn",
                    "Any spellcaster who worships a god of wealth and law may learn")],
    "sign-of-the-faithful": [("you are a worshipper of Sarenrae",
                              "you are a worshipper of your god")],
    "summon-totem-creature": [("You must have been raised Shoanti and belong to a quah to cast "
                               "this at all",
                               "You must have been raised by a tribe that honors totem "
                               "creatures and belong to one of its clans to cast this at all")],
    "summon-barghest-i": [("a single barghest from Basalfeyst to serve you",
                           "a single barghest from its Abyssal realm to serve you")],
    "rapid-perusal": [("such as those from the volumes of the Pathfinder Chronicles.",
                       "such as those some rare tomes grant.")],
    # The myth names, 2026-10-30 (golarion_rewrites.py, "the myth names").
    "anywhere-but-here": [("8-14 Abaddon", "8-14 the daemon wastes")],
    "detect-fiendish-presence": [("fiendish deities including Asmodeus, the archdevils",
                                  "fiendish deities including the lord of Hell, the "
                                  "archdevils")],
    "demon-dream": [("worships a demon lord or Lamashtu",
                     "worships a demon lord or a demon goddess")],
    "genius-avaricious": [("Mammon's Mantle (3,000 gp sacrifice)",
                           "Miser's Mantle (3,000 gp sacrifice)"),
                          ("A rite of sacrifice to Mammon channels his power",
                           "A rite of sacrifice to an archdevil of greed channels his power")],
    "malediction": [("goes to Hell, Abaddon or the Abyss",
                     "goes to Hell, the daemon wastes or the Abyss")],
    "planar-orientation": [("not Lamashtu's", "not the ruling god's")],
    "ferryman-s-dispensation": [("the River Styx", "the river of forgetting")],
    "yellow-sign": [("Hastur", "the god of the sign")],
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, data, check: bool, changed: list[str]) -> None:
    text = json.dumps(data, indent=1, ensure_ascii=False)
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if old.rstrip("\n") == text.rstrip("\n"):
        return
    changed.append(str(path.relative_to(ROOT)))
    if not check:
        path.write_text(text, encoding="utf-8")


def _merge_aliases(path: Path, new: dict) -> dict:
    """Earlier aliases are kept: a save may predate any number of renames."""
    out = _load(path) if path.exists() else {}
    out.update(new)
    return dict(sorted(out.items()))


def _mechanics_doc(sid: str, doc, rename):
    return gr._edit_row(gr._map_strings(doc, rename), MECHANICS_EDITS.get(sid, []))


def _id_renamer(moved: dict):
    """This project's notes cite spells by id ("Details of the sword come from
    last-azlanti-s-defending-sword"). The name renamer reads names, so an old id in a
    note outlived the rename until the 2026-10-30 review found it."""
    olds = sorted((o for o, n in moved.items() if n), key=len, reverse=True)
    if not olds:
        return lambda s: s
    pattern = re.compile(r"(?<![a-z0-9-])(" + "|".join(map(re.escape, olds))
                         + r")(?![a-z0-9-])")
    return lambda s: pattern.sub(lambda m: moved[m.group(1)], s)


def _bestiary(check: bool, changed: list[str]) -> None:
    """The creature files in place, and the bestiary's alias file."""
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")
    from rules import bestiary

    renames = gr.bestiary_aliases()
    seen: set[str] = set()
    for path in CREATURE_FILES:
        data = _load(path)
        seen |= {c.get("id") for c in data["creatures"]}
        data["creatures"] = gr.apply_bestiary(data["creatures"])
        if isinstance(data.get("aliases"), dict):       # core.json's own re-read aliases
            data["aliases"] = {k: renames.get(v, v) for k, v in data["aliases"].items()}
        _dump(path, data, check, changed)
    stale = [old for old, _on, new, _n, _no in gr.CREATURE_RENAMES
             if old not in seen and new not in seen]
    if stale:
        raise gr.StaleEdit(f"creatures neither shipped nor already renamed: {stale}")

    path = BESTIARY / "aliases.json"
    doc = _load(path)
    table = {k: renames.get(v, v) for k, v in doc["aliases"].items()}
    for old, new in renames.items():
        table[bestiary.alias_key(old)] = new
    doc["aliases"] = dict(sorted(table.items()))
    _dump(path, doc, check, changed)


def main() -> int:
    check = "--check" in sys.argv
    changed: list[str] = []

    spells_data = _load(SPELLS)
    rename = gr.spell_renamer(spells_data["spells"])
    spells_data["spells"], spell_aliases = gr.apply_spells(spells_data["spells"])
    _dump(SPELLS, spells_data, check, changed)

    feats_data = _load(FEATS)
    feats_data["feats"], feat_aliases = gr.apply_feats(feats_data["feats"])
    feats_data["counts"]["feats"] = len(feats_data["feats"])
    _dump(FEATS, feats_data, check, changed)

    weapons_data = _load(WEAPONS)
    weapons_data["weapons"] = gr.apply_weapons(weapons_data["weapons"])
    _dump(WEAPONS, weapons_data, check, changed)

    pieces = _load(PIECES)
    rows_of = pieces["weapons"]["rows"]
    for old, (new, _name) in gr.WEAPON_RENAMES.items():
        if old in rows_of:
            rows_of[new] = rows_of.pop(old)
    _dump(PIECES, pieces, check, changed)

    moved = dict(spell_aliases)
    rename_ids = _id_renamer(moved)
    by_name = rename
    rename = lambda s: rename_ids(by_name(s))      # noqa: E731
    for path in MECHANICS:
        data = _load(path)
        docs = {}
        for sid, doc in data["spells"].items():
            if sid in gr.SPELL_DROPS:
                continue        # dropped, or its rulebook printing has its own document
            new = moved.get(sid) or sid
            docs[new] = _mechanics_doc(new, doc, rename)
        data["spells"] = docs                 # the file's own order, so the diff is the edit
        _dump(path, data, check, changed)

    machine = _load(MACHINE)
    rows = []
    for doc in machine["spells"]:
        sid = doc.get("id")
        if sid in gr.SPELL_DROPS:
            continue
        doc = gr._map_strings(doc, rename)
        doc["id"] = moved.get(sid) or sid
        rows.append(doc)
    machine["spells"] = rows
    _dump(MACHINE, machine, check, changed)

    _dump(SPELLS.parent / "aliases.json",
          _merge_aliases(SPELLS.parent / "aliases.json", spell_aliases), check, changed)
    _dump(FEATS.parent / "aliases.json",
          _merge_aliases(FEATS.parent / "aliases.json", feat_aliases), check, changed)

    _bestiary(check, changed)

    print(("would change" if check else "changed") + f": {len(changed)} file(s)")
    for rel in changed:
        print("  " + rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
