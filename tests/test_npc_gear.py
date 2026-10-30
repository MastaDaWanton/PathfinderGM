"""What the app's own people carry: CRB Table 14-9 spent as the game's real items.

Measured 2026-10-28, before this: every built person carried a weapon and a suit by level
rung and nothing else — no masterwork, no potion, no coin — so a level 8 soldier fought at
the numbers of a level 8 soldier in a shop's chainmail and left nothing behind but it. The
book's Step 6 (p. 454) spends Table 14-9 by category, "purchasing as few items as possible",
and "funds left over at the end represent coins and jewelry carried by the character".

Two defects the first wiring found, each pinned below: the potion price was looked up in
the general store's table, which holds no potions, so no build bought one at any level; and
a body in a worn forged suit was looted twice, as the suit's plain key and as its record.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

from rules import bestiary, npc_gear
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parents[1]
BUILDS = {b["id"]: b for b in json.loads(
    (ROOT / "content" / "npc-builds" / "people.json").read_text(encoding="utf-8"))["builds"]}


def test_table_14_9_is_the_books():
    """Rows read off p. 454: basic 1st, 8th and 20th, and heroic 20th (a row past)."""
    assert npc_gear.row(1) == (260, 50, 130, 0, 40, 40)
    assert npc_gear.row(8) == (6000, 2700, 2000, 500, 600, 200)
    assert npc_gear.row(20) == (123000, 40000, 35000, 35000, 11000, 2000)
    assert npc_gear.row(20, heroic=True) == (159000, 55000, 40000, 44000, 18000, 2000)


def test_a_level_8_soldier_is_outfitted_by_the_table():
    """Weapons 2,700: a +1 longsword (15 + 300 + 2,000 = 2,315), not +2 (8,315). Protection
    2,000: full plate (1,500) masterwork (150) and a heavy shield (20). Limited use 600: two
    potions of cure moderate wounds (the dearest that fit). The leftover of every column
    (385 + 330 + 500 magic + ~195 gear) buys the suit's +1 (1,000). Coin 410 of 6,000 —
    it was 1,711 while the magic column went to the weapon and the suit and the rest sat
    as coin."""
    g = BUILDS["soldier-level-8"]["gear"]
    assert g["weapon"] == {"base": "longsword", "masterwork": True, "enhancement": 1}
    assert g["armour"] == {"base": "full plate", "masterwork": True, "enhancement": 1}
    assert g["shield"] == "heavy shield"
    assert collections.Counter(g["pockets"])["potion-of-cure-moderate-wounds"] == 2
    assert g["worn"] == []
    assert (g["spent_gp"], g["coin_gp"], g["table_gp"]) == (5589, 410, 6000)


def test_the_gear_reaches_the_numbers():
    """BAB 8 + Str 17 (+3) + the +1 = +12; AC 10 + full plate 9 + its +1 + heavy shield 2
    = 22."""
    a = bestiary.instantiate("soldier-level-8")
    assert sum(m.value for m in a.attack_modifiers(a.equipped)) == 12
    assert a.ac() == 22
    assert a.purse == {"gp": 410}


def test_a_built_person_has_its_tables_coin_and_no_derived_wealth_on_top():
    a = bestiary.instantiate("soldier-level-8")
    assert a.kit_pending["wealth"] == ""
    assert "potion-of-cure-moderate-wounds" in a.kit_pending["pockets"]


def test_a_fallen_soldier_gives_up_one_suit_and_its_real_sword():
    """The looted suit was "full plate" AND "masterwork full plate" before the loot asked
    whether a record filled the armour slot."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    g = bestiary.instantiate("soldier-level-8", scene=s)
    s.add(g)
    g.hp = -20
    g.die("test")
    e = Engine(s, Dice(seed=1))
    tell = next(o.tell for o in e.run(e.validate([
        {"op": "loot", "actor": "pc", "params": {"from_": g.ref}}])).outcomes)
    assert "+1 longsword" in tell and "+1 full plate" in tell
    assert "full plate," not in tell.replace("+1 full plate", "")
    assert "410 gp" in tell and "rations" in tell


def test_the_protection_and_magic_columns_buy_real_worn_items():
    """The owner's ruling, 2026-10-30, after a review of 0.2.23: `npc_gear` said the
    catalogue had "no cloak of resistance or ring of protection to buy" — it had both — so
    the Protection and Magic columns went to the weapon and the suit and the rest to coin.
    40% of the table's value over the 135 fighting builds was coin (579,384 of 1,445,900
    gp); a 12th-level village priest carried 13,746 gp and a 20th-level captain 45,711.

    Step 6's columns (aonprd Rules ID 359): Protection is "armor and shields, as well as any
    magic item that augments a character's Armor Class or saving throws"; Magic "all other
    permanent magic items". The priest (adept 12, row 16,350: weapons 6,000, protection
    4,500, magic 4,000) wears no suit: bracers of armour +2 (4,000), a headband of inspired
    wisdom +2 (4,000), and the leftover buys a cloak of resistance +1 and an amulet of
    natural armour +1; 1,695 gp is coin. The captain wears a cloak +5, a ring +2, an amulet
    +2 and a belt of giant strength +4 over +5 full plate, with 2,510 gp."""
    priest = BUILDS["priest-level-12"]["gear"]
    assert sorted(priest["worn"]) == ["mi-amulet-natural-armor-1", "mi-bracers-armor-2",
                                      "mi-cloak-resistance-1", "mi-headband-wisdom-2"]
    assert priest["coin_gp"] == 1695
    captain = BUILDS["captain-level-20"]["gear"]
    assert sorted(captain["worn"]) == ["mi-amulet-natural-armor-2", "mi-belt-strength-4",
                                       "mi-cloak-resistance-5", "mi-ring-protection-2"]
    assert captain["armour"]["enhancement"] == 5 and captain["coin_gp"] == 2510
    table = [b["gear"] for b in BUILDS.values() if b["gear"]["table"]]
    coin = sum(g["coin_gp"] for g in table)
    assert coin / sum(g["table_gp"] for g in table) < 0.10
    # Never past the row: the book's 4th-level row prints 1,750 gp of columns under a
    # 1,650 total, and the first run spent up to 1,729 on five 4th-level builds.
    assert all(g["spent_gp"] + g["coin_gp"] <= g["table_gp"] for g in table)


def test_a_built_priest_wears_its_items_and_they_reach_its_numbers():
    """Worn as a player's are (`magicitem.finished`, `Actor.wear`): the bracers' +2 armour
    and the amulet's +1 natural armour on the AC, the cloak's +1 on every save, the
    headband's +2 Wisdom; and each on the shelf, for the looter, not yet identified."""
    a = bestiary.instantiate("priest-level-12")
    assert a.slots["shoulders"] == ["Cloak of Resistance +1"]
    terms = {(m.source, m.value) for m in a.ac_modifiers()}
    assert ("Bracers of Armor +2", 2) in terms and ("Amulet of Natural Armor +1", 1) in terms
    assert any(m.value == 1 and m.type == "resistance" for m in a.save_modifiers("fort"))
    cloak = a.stock["cloak-of-resistance-1#1"]
    assert cloak.magic["known"] == {}


def test_a_trade_carries_its_tools_and_a_small_purse_not_the_table():
    """Read literally the table gave a 1st-level farmer 250 gp in coin, a 12th-level village
    priest 13,746 and the 272 builds 886,593 gp. The owner's ruling (2026-10-28): the table
    for the people who fight and for rank; the trades carry their tools, a kit and the small
    purse every townsperson's kit derives. 135 builds by the table, 137 trades."""
    g = BUILDS["farmer-level-1"]["gear"]
    assert (g["table"], g["armour"], g["coin_gp"]) == (False, None, 0)
    farmer = bestiary.instantiate("farmer-level-1")
    assert farmer.purse == {} and farmer.kit_pending["wealth"] == "2d6 sp"
    assert sum(1 for b in BUILDS.values() if b["gear"]["table"]) == 135
