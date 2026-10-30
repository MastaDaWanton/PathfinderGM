"""Bestiary templates applied to Bestiary creatures, by the printed rules.

Measured 2026-10-28: no template existed, and every "zombie shark" or "advanced wolf" the
game could field was an adventure's printed variant — rows the owner's licensing choice
(docs/bestiary-licensing.md, option D) means the build will stop shipping. The templates
are Bestiary 1's (pp. 250-251, 288-289, 294-295), read from the book; `rules/templates.py`
applies them.

The adventures' own templated creatures were measured against the applier as an oracle
and found unreliable as one: where they follow the book the applier agrees (troll skeleton
5 of 5 fields; owlbear skeleton, derro skeleton and goblin zombie 4 of 5, the fifth being
attack order, carried gear, and a CR of 1/4 the zombie table gives as 1/2), and where they
disagree they break the book's rules themselves — the giant squid and gray render zombies
keep their base's natural armour (AC 23) where the template replaces it, the kobold zombie
skipped its Str +2, the ogre zombie has 8 Hit Dice where the template gives 6, the giant
squid zombie prints "16d8+16" beside 106 hit points. So these tests pin hand-checked
numbers, each worked from the template's own clauses.
"""
from __future__ import annotations

import pytest

from rules import bestiary, statblock_attacks, templates


def _t(base: str, *tpls: str) -> dict:
    block, why = templates.apply_all(base, list(tpls))
    assert block is not None, why
    return block


def test_the_seven_templates_load():
    assert sorted(templates.all_templates()) == ["advanced", "celestial", "fiendish", "giant",
                                                 "skeleton", "young", "zombie"]


# --- simple templates: the rebuild rules as deltas on the printed totals -------------------------

def test_an_advanced_wolf():
    """+4 to every score (Str 13->17, Dex 15->19, Con 15->19: each modifier +2) and natural
    armour +2: AC 14+2+2 = 18 (the quick rules' +4), hp 13+2x2 = 17, saves +2, the bite +2
    to hit and +3 damage (a lone natural attack takes 1.5 x Str: the quick rules' +2 is the
    common case, the rebuild the exact one), CR 2."""
    w = _t("wolf", "advanced")
    assert (w["name"], w["cr"], w["hp"], w["flat_ac"]) == ("Advanced Wolf", "2", 17, 18)
    assert w["flat_saves"] == {"fort": 7, "ref": 7, "will": 3}
    assert w["melee"] == "bite +4 (1d6+4 plus trip)"


def test_a_giant_wolf_and_a_young_one():
    """Giant: Large (-1 attack and AC), Str/Con +4, Dex -2, natural +3, damage one step up
    (1d6 -> 1d8, CRB Table 6-5). Young: Small, Str/Con -4, Dex +4, natural -2, a step down."""
    g = _t("wolf", "giant")
    assert (g["size"], g["flat_ac"], g["hp"], g["cr"]) == ("large", 15, 17, "2")
    assert g["melee"] == "bite +3 (1d8+4 plus trip)"
    y = _t("wolf", "young")
    assert (y["size"], y["flat_ac"], y["hp"], y["cr"]) == ("small", 15, 9, "1/2")
    assert y["melee"] == "bite +1 (1d4-2 plus trip)"


def test_celestial_and_fiendish_defences_follow_their_hit_dice():
    """Under 5 HD: resist 5 and no DR, CR unchanged; 5-10 HD: resist 10, DR 5, CR +1. SR is
    the new CR + 5 either way."""
    c = _t("wolf", "celestial")
    assert (c["cr"], c["sr"], c["resist"], c["reductions"]) == (
        "1", 6, ["acid 5", "cold 5", "electricity 5"], [])
    f = _t("wolf-dire", "fiendish")
    assert (f["cr"], f["sr"], f["resist"]) == ("4", 9, ["cold 10", "fire 10"])
    assert f["reductions"][-1]["bypass"] == "good"
    assert "smite good 1/day" in f["special_attacks"]


# --- the undead: rebuilt whole ------------------------------------------------------------------

def test_a_zombie_shark():
    """Shark: 4 racial HD, Large. Zombie: +2 HD for Large -> 6d8 (27) + Toughness (+6 at more
    than 3 HD) = 33; CR 2 (5-6 HD); AC 10 + 0 Dex - 1 size + 3 natural = 12; Fort 2, Ref 2,
    Will 3+2 = 5; BAB 4 + Str 4 - 1 = +7 for the bite it keeps and the slam it gains, a
    Huge slam's 1d8 (one size up, Bestiary 1 Table 3-1); DR 5/slashing; staggered."""
    z = _t("shark", "zombie")
    assert (z["name"], z["cr"], z["hp"], z["hit_dice"], z["flat_ac"]) == (
        "Shark Zombie", "2", 33, "6d8+6", 12)
    assert z["flat_saves"] == {"fort": 2, "ref": 2, "will": 5}
    assert z["melee"] == "bite +7 (1d8+4), slam +7 (1d8+4)"
    assert z["creature_type"] == "undead" and z["alignment"] == "NE"
    assert z["reductions"][0]["bypass"] == "slashing"


def test_a_zombie_is_staggered_for_good_and_has_no_hide():
    """Staggered is the body's, not a condition (the condition's recovery is a night's rest,
    which would cure a zombie of being one): a standing tag. And no harvest tag survives."""
    z = _t("shark", "zombie")
    assert "state.impaired.staggered" in z["tags"]
    assert not any(t.startswith("harvest.") for t in z["tags"])


def test_a_goblin_zombie_is_made_from_its_one_racial_die():
    """"Goblin warrior 1": the 1d10 is a class level, dropped ("minimum of 1"), +1 HD for
    Small -> 2d8 (9) + 3 Toughness = 12, CR 1/2; bare, as the Bestiary's own human zombie is:
    AC 10 + 1 Dex + 1 size + 1 natural = 13; slam +3 (1d4+1)."""
    z = _t("goblin", "zombie")
    assert (z["hp"], z["cr"], z["flat_ac"], z["melee"]) == (12, "1/2", 13, "slam +3 (1d4+1)")


def test_skeletons_drop_special_attacks_and_gain_claws_by_hand():
    """Owlbear: 5d8 (22), AC 13, its claws and bite kept — without the grab ("retains none
    of the base creature's special attacks"). A troll keeps 6 racial HD: CR 3, hp 27. A
    goblin, who has hands, gains two claws."""
    o = _t("owlbear", "skeleton")
    assert (o["hp"], o["flat_ac"], o["cr"]) == (22, 13, "2")
    assert o["melee"] == "2 claws +6 (1d6+4), bite +6 (1d6+4)"
    t = _t("troll", "skeleton")
    assert (t["hp"], t["cr"], t["flat_ac"]) == (27, "3", 14)
    assert _t("goblin", "skeleton")["melee"] == "2 claws +1 (1d3)"


@pytest.mark.parametrize("base, tpl, says", [
    ("red-dragon-young", "young", "aging or feeding"),
    ("gelatinous-cube", "skeleton", "skeletal system"),
])
def test_what_a_template_cannot_be_applied_to_is_refused_with_its_rule(base, tpl, says):
    block, why = templates.apply_all(base, [tpl])
    assert block is None and says in why


# --- writing it back, and reaching play --------------------------------------------------------

def test_an_attack_line_is_written_back_as_it_was_read():
    """`render_line(parse(line))` reads back as `parse(line)` for 10,810 of the 10,818 attack
    lines in both shipped files (2026-10-28); the eight others print a redundant "/x2" crit,
    which means what the default means."""
    bad = 0
    for block in bestiary.imported().values():
        for cat in ("melee", "ranged"):
            if not block.get(cat):
                continue
            first = statblock_attacks.of_block({cat: block[cat]}).get(cat) or []
            if not first:
                continue
            again = statblock_attacks.of_block({cat: templates.render_line(first)}).get(cat)

            def shape(opts):
                return [[(a["key"], a["count"], a["bonuses"], a["dice"], a["bonus"],
                          a["crit_range"], a["natural"]) for a in o] for o in opts]
            bad += shape(again) != shape(first)
    assert bad <= 8


def test_a_declared_templated_creature_is_built_with_the_store():
    """`{"base": "shark", "templates": ["zombie"]}` in a bestiary file's `derived` list, built
    after every printed block is read."""
    store = {"shark": dict(bestiary.raw_block("shark"))}
    bestiary._derive(store, [{"base": "shark", "templates": ["zombie"]},
                             {"base": "nobody", "templates": ["zombie"]}])
    assert store["shark-zombie"]["hp"] == 33 and "nobody-zombie" not in store
