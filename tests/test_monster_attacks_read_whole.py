"""Every printed attack is read, or said to be unread — never dropped.

A review of 0.2.23 (2026-10-30) found common monsters fighting with 1d3 nonlethal fists or
missing attacks the book prints, and the reader's own ledger calling every line accounted
for:

- "gore +4 melee (1d8+4)": the boar's, the dire boar's, the bone devil's, the bearded
  devil's, the monkey's and the wyvern's lines name the category after the bonus, and the
  reader refused the word. Five of the six read no attack at all, and fought with fists.
- "bite +3 (1d6+1 plus disease and paralysis) and 2 claws +3 (...)": everything after the
  "and", or after a lost comma, was thrown away — 34 attacks in 28 blocks, the ghoul's
  claws, the crocodile's tail slap, the minotaur's gore, the wyvern's sting and bite. And
  the compile asked only whether each comma piece STARTED with an attack, so none of them
  reached `unread`.
- `Actor.stat_block_attacks` answered nothing when `flat_attack` was None, which every
  swarm and troop is (they make no attack roll), and the aasimar and naiad were (the PDF's
  en-dash minus read as no number): fists again.
- "+2 longbow flurry of blows" and 22 more flurries stood on the unarmed strike: 1d8
  bludgeoning at no range, never disarmed, never looted.

The ratchet below counts every printed attack shape in every shipped line and requires
each to be an attack read or inside an unread piece.
"""
from __future__ import annotations

import re

import pytest

from rules import bestiary, compile_block
from rules import statblock_attacks as sa
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

# A printed attack's shape: a bonus (or a run of them) and its damage parenthesis, with
# the optional category and touch words between — or a swarm's or troop's bonusless one.
PIECE = re.compile(r"[+-]\s*\d+(?:\s*/\s*[+-]\s*\d+)*\s*(?:(?:melee|ranged)\s+)?"
                   r"(?:(?:ranged\s+|melee\s+)?touch\s*)?\(", re.I)
AUTO = re.compile(r"\b(?:swarm|troop)\s*\(", re.I)


@pytest.fixture(scope="module")
def shipped():
    return bestiary._build_imported(printed_only=True)


def _shape(line: str) -> int:
    return len(PIECE.findall(line)) + len(AUTO.findall(line))


def test_no_printed_attack_is_silently_dropped(shipped):
    """For every shipped block, every attack the line prints is an attack read or sits in
    an unread piece. Measured 2026-10-30 before the fix: 92 pieces in 89 blocks had text
    after a read attack that went nowhere, 34 of them attacks."""
    lost = []
    for bid, block in sorted(shipped.items()):
        for cat in ("melee", "ranged"):
            line = sa._clean(block.get(cat) or "")
            head = sa._HEADINGS.search(line)
            printed = _shape(line[:head.start()] if head else line)
            options, unread = sa.read(block.get(cat) or "", cat)
            got = sum(len(o) for o in options) + sum(_shape(u) for u in unread)
            if got != printed:
                lost.append((bid, cat, printed, got, line[:120]))
    assert lost == [], lost[:10]


def test_the_compiles_unread_is_the_readers_unread(shipped):
    """`compile_block.attacks` takes the reader's own list rather than re-splitting the
    line: the ghoul's line used to compile with its claws neither read nor unread."""
    rec = compile_block.compile_block(shipped["ghoul"])
    assert [a["key"] for a in rec["attacks"]["melee"][0]] == ["bite", "claws"]
    pirate = compile_block.compile_block(shipped["pirate-captain"])
    # The off-hand dagger printed with no name, "and +17/+12 (1d4+5/17-20)": not an
    # attack anybody can swing by name, so unread — but said, not lost.
    assert any("+17/+12 (1d4+5" in u for u in pirate["unread"])


@pytest.mark.parametrize("line, want", [
    ("gore +4 melee (1d8+4)", [[("gore", 1, [4], "1d8", 4)]]),
    ("glaive +11/+6 melee (1d10+6 plus infernal wound) or 2 claws +10 melee (1d6+4)",
     [[("glaive", 1, [11, 6], "1d10", 6)], [("claws", 2, [10], "1d6", 4)]]),
    ("bite +3 (1d6+1 plus disease and paralysis) and 2 claws +3 (1d6+1 plus paralysis)",
     [[("bite", 1, [3], "1d6", 1), ("claws", 2, [3], "1d6", 1)]]),
    ("bite +5 (1d8+4 plus grab) and tail slap +0 (1d12+2)",
     [[("bite", 1, [5], "1d8", 4), ("tail slap", 1, [0], "1d12", 2)]]),
    ("bite +5 (1d6) 2 claws +3 (1d4)",              # the comma the print lost
     [[("bite", 1, [5], "1d6", 0), ("claws", 2, [3], "1d4", 0)]]),
    ("urn +6 (1d4+3) Spell-Like Abilities (CL 2nd; concentration +3) At will",
     [[("urn", 1, [6], "1d4", 3)]]),
])
def test_the_book_is_read_whole(line, want):
    got = [[(a["key"], a["count"], a["bonuses"], a["dice"], a["bonus"]) for a in opt]
           for opt in sa.parse(line)]
    assert got == want


def test_an_and_in_prose_is_not_a_second_attack():
    """Only an "and" after a closed damage parenthesis joins two attacks: the human
    zombie's leaked rules text ("can only perform a single move action and ...") is one
    unread piece, not two."""
    options, unread = sa.read("slam +4 (1d6+4) poor reflexes and can only move")
    assert [a["key"] for a in options[0]] == ["slam"]
    assert unread == ["poor reflexes and can only move"]


def test_a_rider_the_pdf_broke_is_mended():
    """"poiso n" five times and "energy drai n" twice in the corpus."""
    a = sa.parse("sting +14 melee (3d4+5 plus poiso n)")[0][0]
    assert a["riders"] == ["poison"]


@pytest.mark.parametrize("name, base", [
    ("shuriken flurry of blows", "shuriken"),
    ("+2 longbow flurry of blows", "longbow"),
    ("kama flurry of blows", "kama"),
    ("unarmed strike flurry of blows", "unarmed"),
    ("flurry of blows", "unarmed"),
])
def test_a_flurry_stands_on_its_weapon(name, base):
    assert sa.base_weapon(name) == base


def test_no_compiled_flurry_stands_a_weapon_on_the_fist():
    """23 flurries with a weapon named were class `fist` on 2026-10-30."""
    wrong = [(bid, a["name"]) for bid, rec in compile_block.records().items()
             for cat in ("melee", "ranged") for opt in rec["attacks"][cat] for a in opt
             if a["class"] == "fist" and sa.base_weapon(a["name"]) != "unarmed"]
    assert wrong == []


def test_a_held_spiked_weapon_is_an_item_and_worn_spikes_are_worn():
    """The worn test matched "spiked" and took 14 spiked chains and gauntlets."""
    got = {}
    for rec in compile_block.records().values():
        for cat in ("melee", "ranged"):
            for opt in rec["attacks"][cat]:
                for a in opt:
                    got.setdefault(a["base"], set()).add(a["class"])
    assert got["spiked-chain"] == {"item"} and got["spiked-gauntlet"] == {"item"}
    assert got["spiked-armor"] == {"worn"}


def test_a_long_weapon_name_is_a_weapon():
    """Baalzebul's 58-character longsword was refused by a 48-character cap."""
    opts = sa.parse("+5 adamantine good-outsider-bane icy burst unholy longsword "
                    "+53/+48/+43/+38 (2d6+24/17-20 plus 1d6 cold) or 2 slams +47 (8d6+13)")
    assert [opt[0]["base"] for opt in opts] == ["longsword", ""]


def test_the_magic_property_order_does_not_depend_on_the_hash_seed():
    """Equal-length names were left in set order, so a recompile could reorder an item's
    properties and churn every record."""
    props = compile_block._properties()
    assert props == sorted(props, key=lambda n: (-len(n), n))


# --- the creatures the review named, as play builds them ---------------------------------

@pytest.mark.parametrize("bid, want", [
    ("boar", ["gore"]),
    ("boar-dire", ["gore"]),
    ("bone-devil", ["bite", "claws", "sting"]),
    ("ghoul", ["bite", "claws"]),
    ("crocodile", ["bite", "tail slap"]),
    ("minotaur", ["greataxe", "gore"]),
    ("wyvern", ["sting", "bite", "wings"]),
    ("rat-swarm", ["swarm"]),
    ("spider-swarm", ["swarm"]),
    ("aasimar", ["heavy mace", "light crossbow"]),
    ("naiad", ["dagger", "dagger"]),
])
def test_the_named_creatures_fight_with_what_they_print(bid, want):
    a = bestiary.instantiate(bid)
    got = [x["key"] for cat in ("melee", "ranged")
           for opt in a.stat_block_attacks().get(cat) or () for x in opt][:len(want)]
    assert got == want
    assert a.wielded_key() != "unarmed"


def _fight(template: str, seed: int):
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    foe = scene.add(bestiary.instantiate(template, scene=scene))
    engine = Engine(scene, Dice(seed=seed))
    engine._ensure_encounter(foe.ref)
    if scene.has_grid:
        scene.positions[pc.ref] = (4, 5)
        scene.positions[foe.ref] = (5, 5)
        scene.resync_zones()
    pc.hp = pc.hp_max = 500
    return engine, pc, foe


def _turn(engine, foe):
    return engine.run(engine.validate([
        {"op": "attack", "actor": foe.ref, "target": "pc", "because": "the test"}])).outcomes


def test_a_boar_gores():
    """The boar's 1d8+4: 5 to 12, never the fist's 1d3."""
    engine, pc, boar = _fight("boar", 3)
    hits = []
    for _ in range(80):
        for o in _turn(engine, boar):
            hits += [e for e in o.effects if e.get("kind") == "damage" and e.get("ref") == pc.ref]
    assert hits and {e.get("weapon") for e in hits} == {"gore"}


def test_a_rat_swarm_hurts_without_a_roll_and_distracts():
    """Bestiary 1 p. 313: "they deal automatic damage to any creature whose space they
    occupy ... with no attack roll needed", and "Swarms possess the distraction universal
    monster rule" (p. 299: nauseated 1 round, Fortitude negates; the rat swarm prints DC
    12). Before 2026-10-30 the swarm had no attack and punched for 1d3 nonlethal."""
    saw_save = saw_nausea = False
    for seed in range(1, 40):
        engine, pc, swarm = _fight("rat-swarm", seed)
        # In the space it damages, as the rule has it (from beside, its turn is the move).
        engine.scene.positions[swarm.ref] = engine.scene.positions[pc.ref]
        engine.scene.resync_zones()
        outcomes = _turn(engine, swarm)
        tells = " ".join(o.tell or "" for o in outcomes)
        assert "no roll to make" in tells
        dmg = [e for o in outcomes for e in o.effects
               if e.get("kind") == "damage" and e.get("ref") == pc.ref]
        assert dmg and dmg[0]["weapon"] == "swarm" and not dmg[0].get("nonlethal")
        saw_save |= "Fortitude save" in tells
        if pc.has_state("state.impaired.nauseated"):
            saw_nausea = True
            eff = next(e for e in pc.effects if e.key == "nauseated")
            assert eff.rounds_left == 1 and eff.origin == "creature:rat-swarm"
    assert saw_save and saw_nausea


def test_distraction_spares_what_is_not_alive():
    """"Any living creature": a skeleton in a rat swarm is bitten and not sickened by it."""
    engine, pc, swarm = _fight("rat-swarm", 5)
    bones = engine.scene.add(bestiary.instantiate("human-skeleton", scene=engine.scene))
    assert engine._distraction(swarm, bones, {"automatic": True}) == []
    assert engine._distraction(swarm, pc, {"automatic": False}) == []
