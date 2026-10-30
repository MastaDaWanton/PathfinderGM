"""No shipped rules content names Golarion, and saves written before that still load.

Measured 2026-10-29 with tools/content_provenance.py: 271 of the 4,514 shipped spell and
feat rows named Paizo's setting (Aroden's spellbane, Worshiper of Gorum, "the Cyphermages
of Riddleport"), 55 of the spell mechanics entries repeated those names, and two weapons
were named for Golarion peoples. The owner chose to keep the mechanics and lose the names
(docs/bestiary-licensing.md §7, option F3 falling back to F2); tools/golarion_rewrites.py
is that rewrite, and the importers apply it too. This file holds the count at zero, so a
re-import or a hand edit that brings a name back fails here, not in a licence review.

The myth names Golarion adopted went the same way on 2026-10-30, at the owner's word: 27
rows named Asmodeus, Lamashtu, Hastur, Apsu, Abaddon and their kin as Golarion's gods and
planes. The names Golarion uses for its planes (the Boneyard, Elysium, the First World, the
Akashic Record) followed the same day — renamed by the owner's choice so the game names its
planes one way, NOT because they are Paizo's: Elysium is Greek myth, Nirvana Buddhist,
Abaddon biblical, the Akashic Record Theosophy's, and the Boneyard or the Maelstrom are
English words. Do not extend the list on that premise. Golarion's coined metals (the
skymetals, nexavaran steel, elysian bronze) went too. The alias files are exempt by design:
they are where old saves find the old ids.

The bestiary was never scanned until the review of 2026-10-30 (`SKIP_DIRS = {"bestiary"}`)
and held 100 core.json rows with 444 mentions, 13 creatures.json rows and 33 compiled
records; the owner ruled it renamed to match the spells, through the same table.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import content_provenance as cp  # noqa: E402
import golarion_rewrites as gr  # noqa: E402


def _shipped(rel: str, key: str) -> list[dict]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))[key]


def test_no_shipped_content_names_golarion():
    """271 spell and feat rows, 55 mechanics entries and 2 weapons named Golarion on
    2026-10-29, and 27 more rows named its myth-born gods. On 2026-10-30 the bestiary
    joined the scan carrying 100 + 13 + 33 rows (core, creatures, compiled), and the
    caseless names 5 more (a bare "Pathfinder", "runelords", "klar", the kasatha's
    sword, an old spell id in a note). Every one of them now reads world-agnostic or is
    gone."""
    rows, _ = cp.measure()
    named = sorted({f"{rel} {rid}: {h.term} ({h.field})"
                    for rel, rid, _src, _fam, hits in rows for h in hits
                    if h.cls in cp.LORE or h.cls in ("myth", "cosmology")})
    assert not named, "Golarion names in shipped content:\n" + "\n".join(named[:40])


def test_rules_text_cites_books_not_the_product_line():
    """110 rows cited "(Pathfinder RPG Bestiary 245)" and the like; the book stays named,
    the trademark prefix goes. The `source` column — the book a row came from, which the
    licence's Section 15 needs — is attribution, not text, and is not checked."""
    prefix = re.compile(r"Pathfinder (?:RPG|Roleplaying Game|Campaign Setting|Adventure Path"
                        r"|Chronicles|Player Companion)")
    found = []
    for rel, key in (("content/spells/spells.json", "spells"),
                     ("content/feats/feats.json", "feats")):
        for row in _shipped(rel, key):
            for text in gr._strings(row):
                if prefix.search(text):
                    found.append(f"{row['id']}: {prefix.search(text).group(0)}")
    assert not found, found[:20]


def test_the_rewrite_changes_nothing_in_what_ships():
    """The importers run the same table (build_spells.py, build_feats.py,
    build_weapons.py). Applied to the shipped files it must be a no-op — otherwise a
    re-import would ship something different from what was reviewed here."""
    for rel, key, fn in (("content/spells/spells.json", "spells", gr.apply_spells),
                         ("content/feats/feats.json", "feats", gr.apply_feats)):
        rows = _shipped(rel, key)
        assert fn(rows)[0] == rows, rel
    weapons = _shipped("content/weapons/weapons.json", "weapons")
    assert gr.apply_weapons(weapons) == weapons
    # The bestiary's files, which extract_bestiary_pdfs.py and ship_rulebook_line.py
    # rewrite on the way in.
    for rel in ("content/bestiary/core.json", "content/bestiary/creatures.json",
                "content/bestiary/mounts.json"):
        rows = _shipped(rel, "creatures")
        assert gr.apply_bestiary(rows) == rows, rel


def test_old_ids_and_names_still_resolve():
    """A scroll, a formula or a sheet written before the rename names the old spell or
    feat; the lookups answer with the row it is now."""
    from rules import feats, spells, weapons

    assert spells.get("aroden-s-spellbane").id == "spellbane"
    assert spells.get("waters-of-lamashtu").id == "foul-waters"
    assert spells.get("cultural-adaptation-taldan").id == "cultural-adaptation"
    assert feats.get("aldori dueling mastery").id == "dueling-sword-mastery"
    assert feats.get("eye-of-the-arclord").id == "eldritch-eye"
    assert weapons.key_for("Aldori dueling sword") == "dueling-sword"
    assert weapons.key_for("shoanti-bolas") == "heavy-bolas"


def test_the_feat_alias_file_is_not_read_as_feat_metadata():
    """`rules.feats` reads every content/feats/*.json and folds non-list keys into its
    metadata; read that way, aliases.json would have made every old feat name a metadata
    field. The loader skips it."""
    from rules import feats

    assert "aldori dueling mastery" not in feats.meta()
    assert "aldori-dueling-mastery" not in feats.all_feats()


def test_a_save_from_before_the_rename_loads_as_it_is_now():
    """A wizard's book holding Aroden's spellbane holds spellbane; a spell no longer
    shipped (what grows within) leaves the book rather than sitting there uncastable; a
    renamed feat reads under its new name; a dropped feat stays as the player wrote it."""
    from rules.sheet import from_dict

    a = from_dict({"name": "x", "kind": "npc", "hp": 5, "hp_max": 5,
                   "abilities": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")},
                   "spellbook": ["aroden-s-spellbane", "what-grows-within", "magic-missile",
                                 "spellbane"],
                   "prepared": {"aroden-s-spellbane": 1, "magic-missile": 2},
                   "feats": ["aldori dueling mastery", "weapon focus (rapier)",
                             "ominous mien"]}, ref="c1")
    assert a.spellbook == ["spellbane", "magic-missile"]
    assert a.prepared == {"spellbane": 1, "magic-missile": 2}
    assert a.feats == ["dueling sword mastery", "weapon focus (rapier)", "ominous mien"]


def test_the_river_materials_answer_to_their_old_ids():
    """The app's own planar finishes, Styx Water (a quenchant) and Styx Mordant (a
    tannin), were renamed Oblivion Water and Oblivion Mordant on 2026-10-30 with the other
    myth names. A forge record, a recipe or a shop asking by the old id still gets the
    material; the shipped catalogue no longer has a row under it."""
    from rules import materials

    assert materials.get("styx-water")["id"] == "oblivion-water"
    assert materials.get("styx-mordant")["name"] == "Oblivion Mordant"
    assert "styx-water" not in materials.all()


def test_a_pack_and_a_tanned_grip_from_before_keep_their_river_materials():
    """A save keeps material ids in three places: the goods in the pack, the crafted
    stock's records (here a grip's tannage and its mark) and what the character has
    learned about a material. Each old id reads as the new one on load; nothing else in
    the record moves."""
    from rules.sheet import from_dict

    a = from_dict({"name": "x", "kind": "npc", "hp": 5, "hp_max": 5,
                   "abilities": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")},
                   "goods": {"styx-water": 2, "oak-bark": 1},
                   "herb_known": {"styx-mordant": {"keys": ["k0"], "how": {"k0": "test"}}}},
                  ref="c1")
    assert a.goods == {"oblivion-water": 2, "oak-bark": 1}
    assert set(a.herb_known) == {"oblivion-mordant"}


def test_the_renamed_metals_planes_and_grass_answer_to_their_old_ids():
    """Renamed 2026-10-30 by what each does: abysium is fever skymetal, noqual null
    skymetal, nexavaran steel frontier steel, elysian bronze celestial bronze; the
    anti-magic grass "Elysium" is nullgrass; Akashic Form is Remembered Form. A save, a
    recipe or a World Bible export naming the old id still finds the thing."""
    from rules import ingredients, materials, spells

    assert materials.get("noqual")["name"] == "Null Skymetal"
    assert materials.get("abysium-ore")["id"] == "fever-skymetal-ore"
    assert materials.get("nexavaran-steel")["id"] == "frontier-steel"
    assert materials.get("elysian-bronze")["id"] == "celestial-bronze"
    assert ingredients.get("elysium").id == "nullgrass"
    assert spells.get("akashic-form").id == "remembered-form"


def test_a_skymetal_bar_and_a_grass_in_an_old_pack_load_renamed():
    """The same load-time rewrite as the Styx finishes, for the metals and the grass."""
    from rules.sheet import from_dict

    a = from_dict({"name": "x", "kind": "npc", "hp": 5, "hp_max": 5,
                   "abilities": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")},
                   "goods": {"noqual": 1, "elysium": 3}}, ref="c1")
    assert a.goods == {"null-skymetal": 1, "nullgrass": 3}


# --- 2026-10-30: the review of the rename -------------------------------------------------


def test_the_bestiary_is_scanned_like_every_other_file():
    """`SKIP_DIRS = {"bestiary"}` kept the bestiary out of the scan, so the rebuild that grew
    core.json to 1,417 printed blocks shipped 100 rows naming Golarion's gods and planes
    (444 mentions) while this file's count read zero. A ratchet: the bestiary stays in."""
    assert "bestiary" not in cp.SKIP_DIRS
    _rows, totals = cp.measure()
    assert sum(totals["content/bestiary/core.json"].values()) > 1000
    assert sum(totals["content/bestiary/creatures.json"].values()) > 500
    assert sum(totals["content/bestiary/compiled.json"].values()) > 1000


def _bare(**over) -> dict:
    return {"name": "x", "kind": "npc", "hp": 5, "hp_max": 5,
            "abilities": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")}, **over}


def test_a_save_naming_a_renamed_creature_still_finds_its_body():
    """A save keeps a creature's `from_template` id, and a spawn asks by name. 27 creature
    ids named Golarion's demigods and kin ("mammon", "isph-aun-vuln", "chosen-of-lamashtu")
    until 2026-10-30; each now answers with its renamed block, through content/bestiary/
    aliases.json, whose keys are hashed so the old names ship in no file."""
    from rules import bestiary

    for old, new in (("mammon", "archdevil-of-greed"), ("charon", "horseman-of-death"),
                     ("black-butterfly", "empyreal-lord-of-silence"),
                     ("isph-aun-vuln", "qlippoth-lord-of-ruin"),
                     ("ghoul-leng", "ghoul-dreamland"), ("leng ghoul", "ghoul-dreamland"),
                     ("chosen-of-lamashtu", "chosen-of-the-demon-mother"),
                     ("herecite-of-asmodeus", "herecite-of-tyranny"),
                     ("shoki", "soulkeeper-psychopomp")):
        block = bestiary.raw_block(old)
        assert block is not None and block["id"] == new, old
    aliases = (cp.ROOT / "content" / "bestiary" / "aliases.json").read_text(encoding="utf-8")
    assert '"mammon"' not in aliases and "lamashtu" not in aliases


def test_every_bestiary_alias_lands_on_a_shipped_body():
    """`alias_of` takes one hop. 17 option-D aliases landed on ids this rename moved
    ("ragathiel", "ghoul-leng", "charon"); pointed at nothing, a save's creature would have
    lost its body. Every alias, in aliases.json and core.json, names a block that ships."""
    from rules import bestiary

    store = bestiary.imported()
    for rel in ("aliases.json", "core.json"):
        doc = json.loads((cp.ROOT / "content" / "bestiary" / rel).read_text(encoding="utf-8"))
        missing = sorted({v for v in (doc.get("aliases") or {}).values() if v not in store})
        assert not missing, (rel, missing[:20])


def test_the_deny_list_reads_names_in_any_case():
    """The list was case-sensitive, and five names the 2026-10-30 review found walked past
    it. Each is caught now; a product citation and the game's own name are not."""
    def hits(text):
        return [(t, c) for t, c, _a, _b in cp.scan_text(text) if c != "product"]

    assert hits("invaluable to a Pathfinder who must make a snap decision")
    assert hits("teleporting to an established Pathfinder lodge")
    assert hits("a burning glaive similar to the ones wielded by the runelords of old")
    assert hits("an earth breaker and klar")
    assert hits("Details of the sword come from last-azlanti-s-defending-sword")
    assert hits("a Kasatha spinal sword")
    assert not hits("see the Pathfinder Roleplaying Game Core Rulebook")
    assert not hits("Original writing for Pathfinder GM; a 3.5 skill Pathfinder folded "
                    "into Perception; Pathfinder Unchained's flawless material")
    assert not hits("a choral sings in the choir")         # the angel, not the dragon


def test_a_plane_takes_its_capital_from_where_it_stands():
    """Outer Planes Traveler's flattened table read "LN Lawful The court of the dead N Death
    The churning chaos CN": the capital came along with the source's "The Boneyard". The
    capital is decided by position now, a bracket is not a sentence start, and a plural
    possessive takes an apostrophe alone."""
    assert gr._common("Axis LN Lawful The Boneyard N Death The Maelstrom CN") == (
        "The city of law LN Lawful the court of the dead N Death the churning chaos CN")
    assert gr._common("any (Abaddon)") == "any (the daemon wastes)"
    assert gr._common("at Elysium's edges. Nirvana's knights") == (
        "at the free heavens' edges. The serene heavens' knights")
    from rules import feats

    assert "The court" not in feats.get("outer-planes-traveler").benefit


def test_a_renamed_word_takes_its_own_article():
    """A rename that swapped the word alone left the old word's article: "An ghost
    skymetal head" shipped in blacksmith-materials.json, "an celestial bronze breastplate"
    and "a oblivion-mordant-tanned grip" sat in the code (review, 2026-10-30). The
    renamers carry the article with the word, and nothing shipped or written here puts a
    renamed word behind the wrong one."""
    assert gr._common("A klar can be used") == "A skull shield can be used"
    row = gr.apply_bestiary([{"id": "t", "name": "T", "special_abilities":
                              "It summons an Elysian. A Leng hound follows."}])[0]
    assert row["special_abilities"] == ("It summons a celestial titan. A dreamland hound "
                                        "follows.")

    from rules import materials

    words = set()
    for name in ([n for _o, _on, _i, n, _no in gr.CREATURE_RENAMES]
                 + [n for _i, n in gr.WEAPON_RENAMES.values()]
                 + [n for _i, n in gr.SPELL_RENAMES.values()]
                 + [n for _i, n in gr.FEAT_RENAMES.values()]
                 + [c for _n, c, _t in gr.COSMOS]
                 + [v.replace("-", " ") for v in materials.RENAMED.values()]
                 + ["nullgrass"]):
        # The name's first two words, so "an free action" (the book's own typo, nothing to
        # do with "the free heavens") is not read as a rename slip.
        words.add(tuple(name.lower().split()[:2]))

    def alt(ws):
        return "|".join(r"[\s-]".join(map(re.escape, w)) for w in sorted(ws))

    vowel = [w for w in words if w[0][0] in "aeiou"]
    consonant = [w for w in words if w[0][0] not in "aeiou"]
    wrong = re.compile(r"(?<![\w-])(?:[Aa] (?:" + alt(vowel) + r")|[Aa]n (?:"
                       + alt(consonant) + r"))(?!\w)", re.IGNORECASE)
    found = []
    for folder, glob in (("content", "*.json"), ("rules", "*.py"), ("gm", "*.py"),
                         ("play", "*.py"), ("tools", "*.py"), ("tests", "*.py")):
        for path in sorted((cp.ROOT / folder).rglob(glob)):
            # This file and the rewrite table quote the slips they were written against.
            if path.name in ("aliases.json", "test_no_golarion_names.py",
                             "golarion_rewrites.py"):
                continue
            for m in wrong.finditer(path.read_text(encoding="utf-8", errors="replace")):
                found.append(f"{path.relative_to(cp.ROOT)}: {m.group(0)}")
    assert not found, found[:20]


def test_a_renamed_weapon_answers_to_its_old_name():
    """The klar and the kasatha spinal sword, renamed 2026-10-30. A pack, a feat target or
    a GM naming the old weapon still finds the row."""
    from rules import weapons

    assert weapons.key_for("klar") == "skull-shield"
    assert weapons.key_for("Kasatha spinal sword") == "spinal-sword"


def test_a_nation_gate_no_one_can_meet_is_gone():
    """Mounted Blade asked for "Qadira affinity", rewritten "affinity with a desert nation
    of horsemen": a requirement no sheet shows and `meets` can never read. The gate goes
    and the four mechanical prerequisites stay."""
    from rules import feats

    f = feats.get("mounted-blade")
    assert f.unparsed_prerequisites == []
    assert "nation" not in f.prerequisites_text and "Ride-By Attack" in f.prerequisites_text


def test_no_note_cites_a_spell_by_its_old_id():
    """The mechanics files' notes cite spells by id, and one still said "come from
    last-azlanti-s-defending-sword" after the rename (the name renamer reads names). No
    renamed spell's old id is left in any of them."""
    olds = [o for o, n in json.loads((cp.ROOT / "content" / "spells" / "aliases.json")
                                      .read_text(encoding="utf-8")).items() if n and o != n]
    pattern = re.compile(r"(?<![a-z0-9-])(" + "|".join(map(re.escape, olds))
                         + r")(?![a-z0-9-])")
    found = []
    for path in sorted((cp.ROOT / "content" / "spells" / "mechanics").glob("*.json")):
        for text in gr._strings(json.loads(path.read_text(encoding="utf-8"))):
            found += [f"{path.name}: {m.group(1)}" for m in pattern.finditer(text)]
    assert not found, found[:10]


def test_an_old_satchel_and_an_old_worn_suit_load_renamed():
    """`_current_materials` rewrote goods, stock and herb_known and missed the satchel and
    the worn slots (review, 2026-10-30): an old save holding {"elysium": 3} kept it, so
    `herbknowledge.carried(a, "nullgrass")` answered 0 while `herb_known` already said
    nullgrass. A satchel filled across the rename keeps both counts."""
    from rules import herbknowledge
    from rules.sheet import from_dict

    a = from_dict(_bare(inventory={"elysium": 3, "nullgrass": 2, "monkshood": 1},
                        herb_known={"elysium": {"keys": ["k0"], "how": {"k0": "x"}}},
                        worn={"shirt": {"name": "Shirt", "material": "noqual",
                                        "pieces": {"body": {"material": "noqual"}}}}),
                  ref="c1")
    assert a.inventory == {"nullgrass": 5, "monkshood": 1}
    assert herbknowledge.carried(a, "nullgrass") == 5
    assert a.worn["shirt"]["material"] == "null-skymetal"
    assert a.worn["shirt"]["pieces"]["body"]["material"] == "null-skymetal"


def test_an_old_ore_is_filed_under_its_new_metal():
    """`material_of("noqual-ore")` answered "noqual-ore" — not in the catalogue, so its own
    material — and what a character learned about it was filed under the old id."""
    from rules import materials

    assert materials.material_of("noqual-ore") == "null-skymetal"
    assert materials.material_of("abysium") == "fever-skymetal"


def test_a_grant_from_before_the_rename_still_reads_off_the_satchel():
    """A scene's grant record keeps the ingredient ids it put in the satchel
    (`props[].granted.ids`); the satchel is migrated on load, and a grant still saying
    "elysium" told the player the herbs were all spent."""
    from play.campaign import _current_prop

    rec = _current_prop({"kind": "granted", "granted": {
        "ids": {"elysium": 3, "monkshood": 1}, "names": {"elysium": "Elysium",
                                                         "monkshood": "Monkshood"}}})
    assert rec["granted"]["ids"] == {"nullgrass": 3, "monkshood": 1}
    assert rec["granted"]["names"] == {"monkshood": "Monkshood"}
