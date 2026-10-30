"""The alias map of removed creature ids: for a save's sake, never for a new creature.

Option D (2026-10-29, docs/bestiary-licensing.md) shipped the rulebook line only and landed
each of the 5,537 removed ids on a shipped body (content/bestiary/aliases.json, keyed by
hash), so a save made on 0.2.22 keeps every creature in it. The review of 0.2.23
(2026-10-30) measured what that map did besides:

- the spawn and introduce validators asked `bestiary.lookup`, which accepts the alias, so
  the GM was never refused: "grue" (CR 3) spawned a 152-hp shining child, "stone-bat" a
  stone golem, "nupperibo" a 180-hp peri, "hobgoblin-phalanx-troop" one hobgoblin paragon,
  and "druid", "sheriff" and "barbarian-ogre" a townsperson — 125 non-person ids landed
  more than four CR above the row they named;
- the alias was asked before the store, so a homebrew `black-bear` resolved to the grizzly
  and a homebrew `druid` to a townsperson;
- 3,127 aliases landed on printed bodies, 983 more than two CR from what they were, and a
  saved creature swung the stand-in's printed totals (a saved nupperibo, flat_attack 3,
  at +27/+22/+17/+12 with a +2 flaming burst scimitar);
- 13 ids 0.2.22 shipped resolved to nothing (the Bestiary 4 blocks the 2026-10-28 re-read
  could not parse, and the great horned owl);
- 2,164 aliases (39%) landed on `townsfolk-level-1`, 141 of them Large or bigger humanoids
  (ogres, a CR 16 biclops) and 777 of no human subtype.

tests/bestiary_0_2_22.json is every id 0.2.22 shipped, by hash, with its CR, size and type.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.test import override_settings

from rules import bestiary

FIXTURE = Path(__file__).with_name("bestiary_0_2_22.json")


def _old() -> dict[str, dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["ids"]


def _hashed() -> dict[str, str]:
    return {k[1:]: v for k, v in bestiary._aliases().items() if k.startswith("#")}


# --- every old id still has a body -------------------------------------------------------

def test_every_id_0_2_22_shipped_still_resolves():
    """docs/bestiary-licensing.md promises no save loses a creature. Measured 2026-10-30, 13
    of the 7,138 ids 0.2.22 shipped resolved to nothing — almiraj, bhole, cephalophore,
    colossus-iron, colossus-stone, comozant-wyrd, dark-dancer, death-dog, manitou,
    owl-great-horned, samsaran, scorpion-giant-emperor, scorpion-greensting — so a save
    holding one loaded a creature with no block: no attacks, no type, no harvest."""
    store = bestiary.imported()
    plain = {k for k in bestiary._aliases() if not k.startswith("#")}
    named = {bestiary.alias_key(k) for k in [*store, *plain, *bestiary.TEMPLATES]}
    hashed = _hashed()
    lost = [h for h in _old() if h not in named and h not in hashed]
    assert not lost, f"{len(lost)} ids 0.2.22 shipped resolve to nothing: {lost[:10]}"
    landed = [v for v in hashed.values() if v not in store]
    assert not landed, f"aliases landing on no shipped block: {landed[:10]}"


@pytest.mark.parametrize("old", ["almiraj", "death-dog", "owl-great-horned", "samsaran",
                                 "colossus-iron", "scorpion-greensting"])
def test_the_bestiary_4_blocks_the_re_read_lost_have_a_body(old):
    block = bestiary.raw_block(old)
    assert block is not None, f"{old} resolves to nothing"
    assert bestiary.retired(old), f"{old} is no block of its own and must not spawn"


def test_no_shipped_id_is_an_alias_key():
    """`raw_block` asks the store before the alias (a homebrew creature named like a
    retired id is that creature). It was alias-first so the Bestiary's human zombie beat
    the spreadsheet's own `zombie` row; that is only safe while no shipped id is also an
    alias key, which option D made true and this pins."""
    store = bestiary.imported()
    m = bestiary._aliases()
    both = [k for k in store if k in m or "#" + bestiary.alias_key(k) in m]
    assert not both, both


# --- the map lands on sensible bodies ------------------------------------------------------

_BIGGER = ("large", "huge", "gargantuan", "colossal")


def test_no_big_or_giant_humanoid_stands_on_a_built_person():
    """A build is a Medium human (content/npc-builds/people.json). Measured 2026-10-30, 141
    Large-or-bigger humanoids — an ogre barbarian, the CR 12 cyclops, the CR 16 biclops —
    landed on `townsfolk-level-1`: a fighting giant with a commoner's club and a Medium
    body."""
    store = bestiary.imported()
    wrong = []
    for h, row in _old().items():
        body = store.get(_hashed().get(h, ""), {})
        if body.get("build") and (row["size"] in _BIGGER or row["giant"] or row["troop"]):
            wrong.append((h, row, body["id"]))
    assert not wrong, f"{len(wrong)} big, giant or troop rows on a person: {wrong[:5]}"


def test_nameless_people_are_not_all_one_townsperson():
    """2,164 of 5,537 aliases (39%) were `townsfolk-level-1`, the floor's one rung, for any
    nameless person of any CR. They stand now on a build of the class their Hit Dice say,
    nearest their CR."""
    hashed = _hashed()
    townsfolk = sum(1 for v in hashed.values() if v.startswith("townsfolk-level-"))
    assert townsfolk <= 25, f"{townsfolk} removed ids land on a townsperson"


def test_printed_stand_ins_are_within_a_cr_of_what_they_were():
    """Measured 2026-10-30 (tools/ship_rulebook_line.py, `WINDOW`): a stand-in within one
    CR prints an attack as near the removed row's as two Bestiary creatures of one type and
    CR are to each other; past it, worse at every step. The first map ranked name words
    before CR and put 1,412 of 3,107 printed stand-ins more than one CR off (983 more than
    two). Now 41 are, where no printed block of that type is nearer — and those fight on
    their own numbers (`stand_in_far`)."""
    store = bestiary.imported()
    hashed = _hashed()
    far = 0
    for h, row in _old().items():
        body = store.get(hashed.get(h, ""), {})
        if not body or body.get("build") or row["cr"] is None \
                or body.get("cr_value") is None:
            continue
        if abs(float(body["cr_value"]) - row["cr"]) > 1:
            far += 1
    assert far <= 60, f"{far} printed stand-ins more than one CR from the row"


def test_a_crowd_stands_on_a_crowd():
    """The CR 10 hobgoblin phalanx troop stood on a single hobgoblin paragon: a troop's
    hit points are the unit's. Of the 20 removed troops, the 11 humanoid ones stand on one
    of the three printed troops now (all humanoid); the 9 others — outsider legions, an
    undead troop, a vermin troop — have no printed troop of their type and keep their type
    over the crowd."""
    store = bestiary.imported()
    hashed = _hashed()
    kinds = {str(b.get("creature_type")) for b in store.values()
             if "troop" in str(b.get("subtype") or "").lower()
             and str(b.get("source") or "").startswith("Bestiary")}
    lone = [h for h, row in _old().items() if row["troop"] and h in hashed
            and row["type"] in kinds
            and "troop" not in str(store[hashed[h]].get("subtype") or "").lower()]
    assert not lone, f"{len(lone)} troops on a single creature"
    assert sum(1 for row in _old().values() if row["troop"] and row["type"] in kinds) >= 11


# --- a retired id makes no new creature -----------------------------------------------------

@pytest.mark.parametrize("name", ["grue", "stone-bat", "nupperibo",
                                  "hobgoblin-phalanx-troop", "druid", "sheriff",
                                  "barbarian-ogre"])
def test_the_gm_cannot_spawn_a_retired_id(name):
    """Each of these spawned its stand-in until 2026-10-30 (module docstring)."""
    from rules.intents import IntentError, parse

    assert bestiary.retired(name)
    with pytest.raises(IntentError) as e:
        parse({"op": "spawn", "params": {"template": name, "count": 1}})
    assert "no creature" in str(e.value)
    with pytest.raises(IntentError) as e:
        parse({"op": "introduce", "params": {"who": "a stranger", "template": name}})
    assert "no creature" in str(e.value)


def test_the_refusal_offers_the_stand_in_first():
    """Offered, never substituted. By spelling alone "black-bear" was offered black ice and
    a black butterfly, and "nupperibo" the peri; the stand-in within a CR is the nearest
    creature there is to the one asked for."""
    assert bestiary.suggestion("black-bear").startswith(" Did you mean 'bear-grizzly'")
    assert bestiary.suggestion("nupperibo").startswith(" Did you mean 'lemure'")
    # A far stand-in is no answer to the name and is not offered as one.
    assert "gray-goo" not in bestiary.suggestion("book-swarm")


@pytest.mark.parametrize("name", ["human-skeleton", "skeleton", "zombie", "guildhand",
                                  "thug", "watchman", "ogre", "wolf", "guardsman-level-4",
                                  "goblin troop"])
def test_a_shipped_creature_is_not_retired(name):
    """A block, a hand-written template, a Bestiary rename (core.json's `skeleton` is the
    human skeleton) and an index-order name all still spawn."""
    from rules.intents import parse

    assert not bestiary.retired(name)
    parse({"op": "spawn", "params": {"template": name, "count": 1}})


def test_a_retired_job_word_is_read_as_its_role():
    """"raider", "merchant", "pirate", "guards" were spreadsheet rows, so they are retired
    ids — and they are exactly what the GM writes. Refused, each cost an attempt for a role
    the chooser answers; the plan repair reads them as the role at the party's level, the
    way `template_for` reads the prose's people — so at 5th level "raider" is refused, the
    chooser's raider there being the Game Mastery Guide's tomb raider, no plain raider."""
    from gm import judgement

    for word, role in (("raider", "raider-level-"), ("pirate", "pirate-level-"),
                       ("guards", "guardsman-level-")):
        assert bestiary.retired(word), word
        out = judgement.repair_bare_spawns(
            [{"op": "spawn", "params": {"template": word, "count": 2}}], "", level=3)
        got = out[0]["params"]["template"]
        assert got.startswith(role) and not bestiary.retired(got), (word, got)
    # A retired id the chooser does not answer as that very role is left to be refused.
    out = judgement.repair_bare_spawns(
        [{"op": "spawn", "params": {"template": "grue", "count": 1}}], "", level=3)
    assert out[0]["params"]["template"] == "grue"


def test_a_summon_of_a_retired_id_calls_up_nothing():
    from rules.dice import Dice
    from rules.engine import Engine, Scene

    scene = Scene(location_id="nowhere")
    engine = Engine(scene, Dice(3))
    effects, tells = engine._summon({"type": "summon", "creature": "nupperibo"}, {})
    assert effects[0]["kind"] == "summon_refused", effects
    assert not scene.people, "a stand-in arrived for a retired id"
    assert "Nothing arrives" in tells[0]


def test_a_world_character_remembered_as_a_retired_id_is_chosen_again(tmp_path):
    """The codex remembers which block a world character plays as. A character pinned on
    0.2.22 to an adventure's row would be made, fresh, as whatever body that id now lands
    on; a retired id is not a block that "still exists", so the chooser picks again."""
    from rules import npcs

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        npcs.remember("ent-1", "druid", "Old Mother Hesk")
        got = npcs.block_for("ent-1", ["guard"], 3, "Old Mother Hesk")
        assert got != "druid" and not bestiary.retired(got)
        assert npcs.recall("ent-1")["creature"] == got


# --- the store before the alias -----------------------------------------------------------------

def test_a_homebrew_creature_named_like_a_retired_id_is_itself(tmp_path):
    """Measured 2026-10-30: a homebrew `black-bear` resolved to the grizzly its retired id
    lands on, and a homebrew `druid` to a townsperson — never reachable at all."""
    folder = tmp_path / "homebrew" / "creatures"
    folder.mkdir(parents=True)
    rows = [{"id": "black-bear", "name": "Black Bear", "creature_type": "animal",
             "cr": "3", "cr_value": 3.0, "hp": 32, "source": "my table"},
            {"id": "druid", "name": "Druid", "creature_type": "humanoid", "cr": "4",
             "cr_value": 4.0, "hp": 30, "source": "my table"}]
    (folder / "mine.json").write_text(json.dumps({"creatures": rows}), encoding="utf-8")
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        assert bestiary.raw_block("black-bear")["source"] == "my table"
        assert bestiary.raw_block("black bear")["source"] == "my table"
        assert bestiary.lookup("druid")["hp"] == 30
        assert not bestiary.retired("druid")
    assert bestiary.retired("druid")


# --- a saved creature on a far stand-in fights on its own numbers ---------------------------

def _saved(template: str, flat_attack: int, flat_damage: str = "1d6+1"):
    """A creature as a 0.2.22 save holds it: its own numbers, the removed id as template."""
    from rules.sheet import from_dict

    return from_dict({"name": "it", "kind": "npc", "from_template": template, "hp": 20,
                      "flat_attack": flat_attack, "flat_damage": flat_damage,
                      "abilities": {"str": 12}}, ref="c9")


def test_a_far_stand_in_lends_its_shape_and_never_its_numbers():
    """`book-swarm` (a CR 2 construct swarm) lands on the CR 14 gray goo, where no nearer
    construct swarm prints; the goo's totals are no part of it. Measured before 2026-10-30:
    a saved nupperibo, flat_attack 3, swung the CR 14 peri's +2 flaming burst scimitar at
    +27/+22/+17/+12. And measured with the print simply withheld: the saved book swarm
    fell back to the fist and struck "for 1 non-lethal bludgeoning". It strikes as a swarm
    now, on its own saved bonus and damage."""
    assert bestiary.stand_in_far("book-swarm"), bestiary.stand_in_gap("book-swarm")
    a = _saved("book-swarm", 4, "2d6")
    got = a.stat_block_attacks()
    [[attack]] = got["melee"]
    assert attack["key"] == "swarm" and attack["automatic"]
    assert attack["bonuses"] == [4] and attack["dice"] == "2d6" and attack["bonus"] == 0
    assert attack["riders"] == [] and attack["extra"] == []
    b = _saved("book-swarm", 7, "1d8+3")
    assert b.stat_block_attacks()["melee"][0][0]["bonuses"] == [7]
    assert b.stat_block_attacks()["melee"][0][0]["bonus"] == 3


def test_a_near_stand_in_still_lends_its_print():
    """Within one CR a stand-in's print is as near as a sibling's (`WINDOW`): a saved
    black bear (CR 3) on the grizzly (CR 4) still claws and bites."""
    assert bestiary.retired("black-bear") and not bestiary.stand_in_far("black-bear")
    a = _saved("black-bear", 6)
    keys = {x["key"] for opt in a.stat_block_attacks().get("melee") or () for x in opt}
    assert {"claws", "bite"} <= keys


def test_a_saved_creature_on_a_far_stand_in_carries_its_made_weapons(monkeypatch):
    """With `stat_block_attacks` empty for it, a saved creature on a far stand-in had no
    weapon at all and fought with its fists. It carries the print's made weapons now
    (never its natural ones), swung on its own saved bonus. Forty-one retired ids stand
    far after the 2026-10-30 map, all of them where no block of their type is nearer;
    the reader is driven here on a shipped block that prints a sword and a bite."""
    from rules.sheet import from_dict

    doc = bestiary.raw_block("hobgoblin")
    assert doc and "longsword" in str(doc.get("melee")).lower()
    a = from_dict({"name": "it", "kind": "npc", "from_template": "hobgoblin", "hp": 9,
                   "flat_attack": 2}, ref="c9")
    assert a._arms_of_a_far_stand_in(doc) == ([], ""), "a shipped creature is no stand-in"
    monkeypatch.setattr(bestiary, "stand_in_far", lambda key: key == "hobgoblin")
    made, primary = a._arms_of_a_far_stand_in(doc)
    assert "longsword" in made and "longbow" in made and primary == made[0]
    # Its one attack is the print's first, at its own saved bonus.
    assert a.stat_block_attacks()["melee"][0][0]["bonuses"] == [2]


# --- hit points: the favoured class -----------------------------------------------------------

def test_built_people_take_the_favoured_class_hit_point():
    """The owner's ruling (2026-10-30): built townsfolk take the favoured class hit point a
    level, as Paizo's NPC Codex people mostly do — its warrior 3 guard is 3d10+6 at Con 10
    with Toughness, 16 + 3 + 3. Before it, every build here had its level in hit points
    fewer than the Codex's arithmetic gives."""
    from rules import npc_builds

    for bid in ("guardsman-level-1", "guardsman-level-4", "farmer-level-1",
                "captain-level-8", "priest-level-6"):
        a = bestiary.instantiate(bid)
        doc = bestiary.raw_block(bid)["build"]
        level = int(doc["level"])
        die = {"warrior": 10, "expert": 8, "commoner": 6, "adept": 6, "aristocrat": 8}
        rolled = npc_builds.average_hp(die[doc["class"]], level)
        tough = max(3, level) if "Toughness" in doc["feats"] else 0
        assert a.hp_max == rolled + level + a.ability_mod("con") * level + tough, bid
