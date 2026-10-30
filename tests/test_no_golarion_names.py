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
planes. Deliberately not held to zero: cosmology words (Boneyard, Elysium), never ruled on.
The alias files are exempt by design: they are where old saves find the old ids.
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
    2026-10-29, and 27 more rows named its myth-born gods. Every one of them now reads
    world-agnostic or is gone."""
    rows, _ = cp.measure()
    named = sorted({f"{rel} {rid}: {h.term} ({h.field})"
                    for rel, rid, _src, _fam, hits in rows for h in hits
                    if h.cls in cp.LORE or h.cls == "myth"})
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
