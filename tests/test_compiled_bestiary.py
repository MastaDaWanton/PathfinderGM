"""Every shipped stat block compiled once: no interpretation at play.

docs/compiled-bestiary-plan.md. Before 2026-10-29 a creature's attack lines were parsed on
every swing, its possessions guessed from them, its coin derived from its XP — and the
book's own Gear line was dropped at import. Measured over 2,169 shipped printed blocks on
the day of the compile:

    attacks                   4,530   (item 1,871 · natural 2,179 · body 276 · fist 115 ·
                                       thrown object 45 · worn 35 · ability 9)
    item attacks linked to a carried thing      1,688 of 1,871
    carried things            8,090   (weapon 1,604 · potion 1,083 · armour 627 ·
                                       coin 570 · ammunition 402 · shield 136 · ...)
    unread                    gear 1,210 · melee 164 · ranged 178

The unread are what no table resolves (a holy symbol, a disguise kit, the book's prose
"jewelry and magic items only") and the pieces of an attack line no attack is made of
(spell-like abilities the import ran into the ranged column). They are kept, word for
word, in each record's `unread`, and the ratchet below lets the count only fall.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import bestiary, compile_block, statblock_attacks

ROOT = Path(__file__).resolve().parents[1]
DOC = json.loads((ROOT / "content" / "bestiary" / "compiled.json").read_text(encoding="utf-8"))

# The ratchet: what the compile could not account for on 2026-10-29. Lower these as the
# tables learn more; never raise them.
UNREAD_AT_MOST = {"gear": 1210, "melee": 164, "ranged": 178}
LINKED_AT_LEAST = 1688


@pytest.fixture(scope="module")
def shipped():
    return bestiary._build_imported(printed_only=True)


def test_every_shipped_block_has_a_fresh_record(shipped):
    """A record is compiled from its block's lines and stamped with their hash; a block
    edited since is stale, and `record_for` will not answer with it. Re-run
    tools/compile_bestiary.py."""
    assert DOC["compiler"] == compile_block.COMPILER
    stale = [bid for bid, b in shipped.items() if compile_block.record_for(b) is None]
    assert stale == [], f"{len(stale)} stale: python tools/compile_bestiary.py"


def test_the_record_is_what_the_parser_reads(shipped):
    """The compile adds a class to each attack and changes no number the parser read."""
    for bid in ("ogre", "owlbear", "goblin", "adult-red-dragon"):
        live = statblock_attacks.of_block(shipped[bid])
        rec = compile_block.record_for(shipped[bid])["attacks"]
        strip = [[{k: v for k, v in a.items() if k not in ("class", "mode", "item")}
                  for a in opt] for cat in ("melee", "ranged") for opt in rec[cat]]
        assert strip == [opt for cat in ("melee", "ranged") for opt in live[cat]], bid


def test_unread_only_falls():
    got = {"gear": 0, "melee": 0, "ranged": 0}
    linked = 0
    for rec in DOC["creatures"].values():
        for u in rec["unread"]:
            got[u.split(":", 1)[0]] += 1
        linked += sum(1 for cat in ("melee", "ranged") for opt in rec["attacks"][cat]
                      for a in opt if a["class"] == "item" and a.get("item") is not None)
    assert all(got[k] <= UNREAD_AT_MOST[k] for k in got), got
    assert linked >= LINKED_AT_LEAST


def test_the_ogre_carries_what_its_treasure_line_prints(shipped):
    """"Treasure standard (hide armor, greatclub, 4 javelins)": read since 2026-10-29. Its
    club was a guess from the attack line before, and its armour and javelins nothing."""
    rec = compile_block.record_for(shipped["ogre"])
    got = {(it["key"], it["count"]) for it in rec["carries"]}
    assert {("hide armour", 1), ("greatclub", 1), ("javelin", 4)} <= got
    club = next(a for a in rec["attacks"]["melee"][0] if a["base"] == "greatclub")
    assert club["class"] == "item" and rec["carries"][club["item"]]["key"] == "greatclub"


@pytest.mark.parametrize("printed, want", [
    ("+1 flaming longsword", {"key": "longsword", "enhancement": 1, "properties": ["flaming"]}),
    ("mwk cold iron dagger", {"key": "dagger", "masterwork": True, "material": "cold iron"}),
    ("potions of cure light wounds (3)", {"key": "potion-of-cure-light-wounds", "count": 3}),
    # A property is only ever a weapon's: the first cut read "strength" off this potion.
    ("potion of bull's strength", {"key": "potion-of-bull-s-strength", "properties": []}),
    ("tanglefoot bags (2)", {"key": "tanglefoot-bag", "count": 2}),
    ("1,150 gp", {"key": "gp", "table": "coin", "count": 1150}),
    ("two +1 scimitars", {"key": "scimitar", "count": 2, "enhancement": 1}),
    ("4 javelins", {"key": "javelin", "count": 4}),
    ("+2 full plate", {"key": "full plate", "table": "armour", "slot": "armour"}),
])
def test_a_printed_piece_of_gear_is_one_carried_thing(printed, want):
    got = compile_block.item(printed)
    assert {k: got[k] for k in want} == want


def test_what_no_table_knows_keeps_its_words_and_no_key():
    """Never the nearest guess (CLAUDE.md, "ground every name")."""
    got = compile_block.item("silver holy symbol")
    assert got["key"] == "" and got["printed"] == "silver holy symbol"


def test_looted_potions_and_flasks_can_be_used():
    """Measured in the running app 2026-10-29: a looted goblin's potions of cure light
    wounds, acid, alchemist's fire and tanglefoot bags went into the herb satchel
    (`inventory`), where nothing drinks or throws them and the Equipment tab does not list
    them. They are filed now where buying them files them (`goods.deliver`)."""
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    body = bestiary.instantiate("viking", scene=s)
    s.add(body)
    body.hp = -20
    body.die("test")
    e = Engine(s, Dice(seed=1))
    e.run(e.validate([{"op": "loot", "actor": "pc", "params": {"from_": body.ref}}]))
    held = {v.base: (v.count, list(v.how)) for v in pc.stock.values()}
    assert held["Potion of Cure Light Wounds"] == (3, ["drink"])
    assert held["+1 chainmail"][0] == 1
    assert pc.inventory == {}
    assert "heavy wooden shield" in pc.goods and "battleaxe" in pc.weapons


def test_a_block_changed_after_its_compile_is_read_live(shipped):
    block = dict(shipped["ogre"], melee="greatclub +9 (2d8+9)")
    assert compile_block.record_for(block) is None
