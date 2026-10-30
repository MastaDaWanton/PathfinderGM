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
    """Weapons 2,700 + half the magic 500: a +1 longsword (15 + 300 + 2,000 = 2,315), not +2
    (8,315). Protection 2,000 + 250: full plate (1,500) masterwork (150) and a heavy shield
    (20); +1 (2,670) does not fit. Limited use 600: six potions of cure light wounds (the
    cap). Spent 4,288.61; 1,711 gp of the 6,000 is coin."""
    g = BUILDS["soldier-level-8"]["gear"]
    assert g["weapon"] == {"base": "longsword", "masterwork": True, "enhancement": 1}
    assert g["armour"] == {"base": "full plate", "masterwork": True, "enhancement": 0}
    assert g["shield"] == "heavy shield"
    assert collections.Counter(g["pockets"])["potion-of-cure-light-wounds"] == 6
    assert (g["spent_gp"], g["coin_gp"], g["table_gp"]) == (4288, 1711, 6000)


def test_the_gear_reaches_the_numbers():
    """BAB 8 + Str 17 (+3) + the +1 = +12; AC 10 + full plate 9 + heavy shield 2 = 21."""
    a = bestiary.instantiate("soldier-level-8")
    assert sum(m.value for m in a.attack_modifiers(a.equipped)) == 12
    assert a.ac() == 21
    assert a.purse == {"gp": 1711}


def test_a_built_person_has_its_tables_coin_and_no_derived_wealth_on_top():
    a = bestiary.instantiate("soldier-level-8")
    assert a.kit_pending["wealth"] == ""
    assert "potion-of-cure-light-wounds" in a.kit_pending["pockets"]


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
    assert "+1 longsword" in tell and "masterwork full plate" in tell
    assert "full plate," not in tell.replace("masterwork full plate", "")
    assert "1711 gp" in tell and "rations" in tell


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
