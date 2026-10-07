"""Option A: half your Craft ranks count at the world-class benches, as their own term.

The owner, 2026-10-06: "the craft skill and the profession skill seem pretty useless".
Measured that day (docs/craft-profession-options.md §1): **0 of the 5 world-class benches
read a Craft rank** — herbalism, smithing, alchemy, leatherwork and enchanting all rolled
d20 + track level + half character level + an ability, and their comments cited Craft
only to justify choosing Intelligence. The owner chose option A on 2026-10-07: half the
Craft ranks, rounded down, as a term the roll breakdown names ("Craft ranks ½ (4)" +2).
Herbalism takes the better of Craft and Profession, after the book's herbalist (a
Profession) and the herbarium's study, which already accepts any Profession.

The alchemy bench being rebuilt on build/alchemy calls the same helper
(`tradecraft.bench_terms(actor, "alchemist")`); this branch's rules/alchemist.py is that
lane's to change, so it is asserted here only through the helper.
"""
from __future__ import annotations

import pytest

from rules import blacksmith, crafting, enchanter, leatherworker, magicitem, tradecraft
from rules.sheet import load_pc

BENCHES = [(crafting, "herbalist"), (blacksmith, "blacksmith"), (enchanter, "enchanter"),
           (leatherworker, "leatherworker")]


def _pc(**ranks):
    pc = load_pc("fixtures/pc-thessaly.json")
    pc.ranks = {k: v for k, v in pc.ranks.items() if k not in ("craft", "profession")}
    pc.ranks.update(ranks)
    return pc


@pytest.mark.parametrize("module,bench", BENCHES)
def test_four_craft_ranks_add_two_to_the_bench_and_say_so(module, bench):
    bare, crafty = _pc(), _pc(craft=4)
    before = module.check_terms(bare, 3)
    after = module.check_terms(crafty, 3)
    assert len(after) == len(before) + 1
    assert after[-1] == {"label": "Craft ranks ½ (4)", "value": 2}
    assert module.check_bonus(crafty, 3) == module.check_bonus(bare, 3) + 2


@pytest.mark.parametrize("module,bench", BENCHES)
def test_no_ranks_no_term(module, bench):
    """A character who placed no rank sees the bench exactly as before — no "+0" line
    advertising a skill they never chose."""
    assert not any("ranks" in t["label"] for t in module.check_terms(_pc(), 3))


def test_one_rank_shows_at_nothing_so_the_player_can_see_where_it_went():
    assert tradecraft.bench_terms(_pc(craft=1), "blacksmith") == [
        {"label": "Craft ranks ½ (1)", "value": 0}]


def test_herbalism_takes_the_better_of_craft_and_profession():
    assert tradecraft.bench_terms(_pc(craft=2, profession=6), "herbalist") == [
        {"label": "Profession ranks ½ (6)", "value": 3}]
    assert tradecraft.bench_terms(_pc(craft=6, profession=2), "herbalist") == [
        {"label": "Craft ranks ½ (6)", "value": 3}]
    # The smith's forge does not read Profession.
    assert tradecraft.bench_terms(_pc(profession=6), "blacksmith") == []


def test_the_alchemy_bench_helper_is_ready_for_its_lane():
    assert tradecraft.bench_terms(_pc(craft=7), "alchemist") == [
        {"label": "Craft ranks ½ (7)", "value": 3}]


def test_magic_item_making_reads_the_enchanters_terms_and_so_the_ranks():
    assert magicitem.check_terms(_pc(craft=4), 2)[-1]["value"] == 2


def test_a_worn_skill_bonus_never_reaches_the_bench():
    """Ranks are the sheet's count, not the skill total: a +5 competence item to Craft is
    not a rank, and the enchanter's no-feedback rule (nothing worn reaches the circle's
    check) holds for this term as for Intelligence."""
    from rules.activeeffect import ActiveEffect

    pc = _pc(craft=4)
    pc.apply_effect(ActiveEffect(
        source="test", origin="author:test",
        modifiers=[{"kind": "skill_mod", "target": "craft", "amount": 5,
                    "bonus_type": "competence", "note": "a test tool"}]))
    assert sum(m.value for m in pc.skill_modifiers("craft")) >= 9
    assert tradecraft.bench_terms(pc, "enchanter") == [
        {"label": "Craft ranks ½ (4)", "value": 2}]


def test_the_forge_roll_carries_the_term_into_its_dice_breakdown():
    """The forge's roll door builds its popup from `check_terms` (play/forge_views.py);
    the term rides into it with no change there."""
    from pathlib import Path

    src = Path("play/forge_views.py").read_text(encoding="utf-8")
    assert "terms = bs.check_terms(pc, progress.level)" in src
