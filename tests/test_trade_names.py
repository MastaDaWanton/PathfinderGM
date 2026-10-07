"""A trade-named skill is its base skill: "craft (alchemy)" is Craft, "profession (sailor)"
is Profession.

docs/craft-profession-options.md found three defects on the way to its options, and the
owner's choice of 2026-10-07 (options A, B and C; NOT D, the named trades) settles how to
fix them: this game keeps one Craft, one Profession and one Perform, so a trade name folds
onto its base wherever a name arrives from outside the sheet (`tables.base_skill`).

Measured before the fold, 2026-10-07:
  * 17 feats in content/feats/feats.json require ranks in a trade (9 Craft, 3 Profession,
    6 Perform; Brewmaster asks two) and ranks only ever land on the bare id, so none of
    the 17 could be taken by anyone — Master Alchemist with 20 Craft ranks failed it;
  * 2,208 printed NPC totals in the bestiary sit under a trade name (855 craft, 675
    profession, 678 perform), `skill_modifiers("profession")` looked up the bare id only,
    and a printed sailor — "Caulky" Tarroon, Profession (sailor) +6 — was refused at the
    helm as "cannot attempt profession untrained";
  * a GM check naming "craft (alchemy)" was refused as "not a Pathfinder 1e skill".
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import feats
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.intents import IntentError, normalise_skill, parse
from rules.sheet import load_pc
from rules.tables import SKILLS, base_skill

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("name,base", [
    ("craft (alchemy)", "craft"), ("Craft (Weapons)", "craft"), ("craft: leather", "craft"),
    ("craft (any)", "craft"), ("profession (sailor)", "profession"),
    ("Profession (siege engineer)", "profession"), ("perform (oratory or sing)", "perform"),
    ("knowledge (arcana)", "knowledge (arcana)"), ("craft", "craft"),
])
def test_a_trade_folds_onto_its_base_and_a_knowledge_does_not(name, base):
    assert base_skill(name) == base


def test_crafty_words_that_are_not_a_trade_are_not_folded():
    """Only "craft" followed by a space, a bracket or a colon: "craftsmanship" is not the
    skill, and folding it would turn a typo into a roll."""
    assert base_skill("craftsmanship") == "craftsmanship"
    assert normalise_skill("craftsmanship") is None


def test_every_trade_feat_can_now_be_met_by_ranks_in_the_base():
    """17 feats asked for a trade's ranks; with the base's ranks every such condition now
    passes, and with none it still fails."""
    data = json.loads((ROOT / "content" / "feats" / "feats.json").read_text(encoding="utf-8"))
    rows = [f for f in (data.get("feats") or []) if isinstance(f, dict)]
    conds = []
    for f in rows:
        for c in f.get("prerequisites") or []:
            if c.get("kind") == "skill_ranks" and base_skill(c["skill"]) != c["skill"].lower():
                conds.append(c)
    assert len(conds) >= 18, f"the trade conditions moved: {len(conds)}"
    pc = load_pc("fixtures/pc-thessaly.json")
    pc.ranks = {**pc.ranks, "craft": 20, "profession": 20, "perform": 20}
    assert all(feats._check(pc, c) for c in conds)
    pc.ranks = {k: v for k, v in pc.ranks.items() if k not in ("craft", "profession", "perform")}
    assert not any(feats._check(pc, c) for c in conds)


def test_a_printed_sailor_can_take_the_helm():
    """'Caulky' Tarroon prints Profession (sailor) +6 and nothing under the bare id. Before
    the fold his ram was refused as untrained."""
    scene = Scene(location_id=None)
    sailor = scene.add(instantiate("caulky-tarroon", scene=scene), zone="near")
    assert "profession" not in sailor.flat_skills
    mods = sailor.skill_modifiers("profession")
    assert sum(m.value for m in mods) == 6
    assert mods[0].source == "Profession (Sailor)"


def test_the_best_printed_trade_answers_and_an_exact_total_wins():
    pc = load_pc("fixtures/pc-thessaly.json")
    pc.flat_skills = {"profession (cook)": 2, "profession (sailor)": 9}
    assert pc.printed_skill("profession") == ("profession (sailor)", 9)
    pc.flat_skills["profession"] = 4
    assert pc.printed_skill("profession") == ("profession", 4)
    assert pc.printed_skill("craft") is None


def test_the_gm_may_name_a_trade_in_a_check():
    raw = {"op": "check", "actor": "pc", "because": "test",
           "params": {"skill": "craft (alchemy)", "dc": "average"}}
    assert parse(raw).params["skill"] == "craft"
    with pytest.raises(IntentError):
        parse({**raw, "params": {"skill": "basketry", "dc": "average"}})


def test_every_base_is_a_skill_the_table_knows():
    from rules.tables import TRADE_SKILLS

    assert set(TRADE_SKILLS) <= set(SKILLS)

