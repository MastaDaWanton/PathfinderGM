"""The Blood Bender's kit works through the one use door, or says why it cannot.

Playtest 2026-11-15 (the owner's Blood Bender outlaw on 0.3.6, log
pgm-work/playtest-2026-11-15.md):

* #32 the Blood Spike Projectile chip "charged 6 nonlethal ('the cost: 6'), then '1
  part(s) of it are yours to narrate', then 'Refused: There is no blood spike projectile
  here'" — no attack roll and no damage. Root: the ability had no document, so the
  converted-effects loop ran it; that loop read only `params.to` (the plan aims with
  `target`), so the damage was "narrated", and the scenery reader asked whether a blood
  spike projectile lay in the room.
* #31 "hurl a Blood Spike at the merchant" was planned as an improvised thrown weapon and
  refused "not in hand", though the reading had already found the ability held.
* #96 / #6 the sheet showed "Rage 7 of 7" and "Ki 3 of 3" on a Path A Blood Spike: Battle
  Blood's pools, granted by level while their abilities come by path.
* #36 her unarmed strike did "4 non-lethal bludgeoning" with no choice made.
* #3 the creator offered 32 metamagic feats to a character with no spells.
"""
from __future__ import annotations

import pytest

from rules import class_abilities, classes as classes_mod, leveling
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import BloodPool, Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from tests._board import face_to_face

PATHS = ("blood spike", "coagulator", "blood commander", "battle blood")


def _bender(path="blood spike", level=1, **extra):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "blood bending", "level": level, "ranks": {}, "paths": [path],
              "pools": {}})
    d.update(extra)
    return from_dict(d, ref="pc")


def _fight(pc, seed=7):
    scene = Scene()
    scene.add(pc)
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    scene.add(instantiate("thug", scene=scene, name="the friend"))
    e = Engine(scene, dice=Dice(seed=seed))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc", "c2"], "them": ["c1"]}}}]))
    face_to_face(scene)
    return scene, e


def _use(e, ability, target="c1"):
    intent = {"op": "use_ability", "actor": "pc", "params": {"ability": ability},
              "because": "test"}
    if target:
        intent["target"] = target
    return e.run(e.validate([intent])).outcomes[-1]


def _aim(pc, name):
    """Who the panel aims a use at: the foe, the ally, or nobody (`views` entry `aim`)."""
    path, doc = leveling.ability_doc(pc, name)
    reaches = (doc or {}).get("affects") or "self"
    if reaches == "ally":
        return "c2"
    return "c1"


def _walk():
    for path in PATHS:
        tiers = classes_mod.get("blood bending")["paths"][path]["tiers"]
        for level in (1, 2, 3):
            for tier in ("1", "2"):
                for name in tiers.get(tier, []):
                    yield path, level, name


@pytest.mark.parametrize("path,level,name", list(_walk()))
def test_every_ability_at_levels_one_to_three_resolves_or_says_why(path, level, name):
    """Each Blood Bender ability the class lists at Control Blood 1-2, at levels 1-3,
    used through the engine's one door: it resolves with something on the record, or it
    is refused with the reason, and a refusal spends nothing. Measured before this fix:
    Blood Spike Projectile, Blood Mine, Sanguine Spray, Aggressive Draw, Viscous Threat,
    Blood Spatter Aura, Blood Javelin and Blood Burst all "resolved" with parts "yours to
    narrate" — four of them after taking hit points for it."""
    pc = _bender(path, level, nonlethal=4)
    scene, e = _fight(pc)
    scene.pools.append(BloodPool(owner="pc", at=scene.positions.get("pc"), place=scene.at))
    before = (pc.hp, pc.nonlethal, {k: p.current for k, p in pc.pools.items()},
              len(scene.pools))
    out = _use(e, name, _aim(pc, name))
    assert "yours to narrate" not in out.tell, out.tell
    if out.status == "refused":
        assert out.tell.strip(), name
        assert (pc.hp, pc.nonlethal, {k: p.current for k, p in pc.pools.items()},
                len(scene.pools)) == before, f"{name} was refused and still spent: {out.tell}"
        return
    assert out.status == "resolved", out.tell
    if leveling.is_passive(pc, name):
        # Always on, never used: said so, and only for a passive the engine runs.
        assert "always active" in out.tell and not leveling.needs_of(pc, name), out.tell
        return
    kinds = {r.get("kind") for r in out.effects} - {"use_ability"}
    assert kinds, f"{name} resolved and changed nothing: {out.tell}"


def test_blood_spike_projectile_rolls_to_hit_and_deals_the_blood_die_plus_con():
    """#32: a ranged attack against full AC (the kineticist's physical blast), Blood DMG
    (the table's `blood` die, 1d8 at 1st) + Con as piercing, 1d8 non-lethal paid, a blood
    stack and a pool at the target's feet."""
    for seed in range(1, 60):
        pc = _bender("blood spike", 1)
        scene, e = _fight(pc, seed=seed)
        out = _use(e, "Blood Spike Projectile")
        if "attack hits" in out.tell:
            break
    else:
        pytest.fail("no seed hit the thug in 59 tries")
    assert out.status == "resolved"
    assert "against AC" in out.tell and "touch AC" not in out.tell
    cost = next(r for r in out.effects if r.get("kind") == "hp_cost")
    assert 1 <= cost["amount"] <= 8 and pc.nonlethal == cost["amount"]
    hit = next(r for r in out.effects if r.get("kind") == "damage" and r.get("ref") == "c1")
    assert hit["type"] == "piercing" and hit["origin"] == "ability:blood spike/blood spike projectile"
    con = pc.ability_mod("con")
    assert 1 + con <= hit["rolled"] <= 8 + con
    assert scene.actors["c1"].pool("blood stack").current == 1
    assert any(b.owner == "pc" for b in scene.pools)


def test_siphon_pool_draws_a_pool_back_and_is_refused_without_one():
    pc = _bender("blood spike", 1, nonlethal=6)
    scene, e = _fight(pc)
    refused = _use(e, "Siphon Pool", None)
    assert refused.status == "refused" and "no" in refused.tell and pc.nonlethal == 6
    scene.pools.append(BloodPool(owner="pc", at=None, place=scene.at))
    out = _use(e, "Siphon Pool", None)
    assert out.status == "resolved", out.tell
    assert not scene.pools and pc.nonlethal < 6 and pc.temp_hp > 0


@pytest.mark.parametrize("path,level,has,lacks", [
    ("blood spike", 1, set(), {"ki", "rage"}),
    ("battle blood", 1, {"rage"}, {"ki"}),
    ("battle blood", 3, {"rage", "ki"}, set()),
])
def test_a_paths_pools_come_with_the_path(path, level, has, lacks):
    """#6/#96: the class's pools named an ability (`ability`) and are made only while it
    can be used. A save carrying the stray pools loses them on load."""
    pc = _bender(path, level)
    assert has <= set(pc.pools) and not (lacks & set(pc.pools)), sorted(pc.pools)
    saved = to_dict(pc)
    saved["pools"] = {"ki": {"id": "ki", "current": 3, "maximum": 3, "source": "Blood Bending"},
                      "rage": {"id": "rage", "current": 7, "maximum": 7,
                               "source": "Blood Bending"}}
    again = from_dict(saved, ref="pc")
    assert has <= set(again.pools) and not (lacks & set(again.pools))


def test_blood_rage_on_a_blood_spike_says_whose_it_is():
    """#96: the refusal names the path that has it."""
    scene, e = _fight(_bender("blood spike", 1))
    out = _use(e, "Blood Rage", None)
    assert out.status == "refused"
    assert "Battle Blood ability" in out.tell and "Blood Spike" in out.tell


def test_no_class_shows_a_pool_with_nothing_to_spend_it():
    """The same bug in the other eleven: a class pool on the sheet that no usable
    ability's `cost` or `drain` names. Measured on master before this: a Path A Blood
    Spike had ki and rage, a 3rd-level one also "unbalancing strike"."""
    base = to_dict(load_pc("fixtures/pc-kesst.json"))
    for cid, cls in classes_mod.all_classes().items():
        declared = {str(p["id"]).lower() for p in cls.get("pools") or ()}
        for level in (1, 3, 5, 10, 20):
            d = dict(base, **{"class": cid, "level": level, "pools": {}, "ranks": {},
                              "class_choices": {},
                              "paths": leveling.paths_for(cid)[:1]})
            pc = from_dict(d, ref="pc")
            spent = set()
            for doc in class_abilities._docs_for(pc):
                if class_abilities._has_it(pc, doc):
                    spent |= {str((doc.get(s) or {}).get("pool") or "").lower()
                              for s in ("cost", "drain")}
            for path in pc.paths:
                det = leveling.path_detail(cid, path)
                for name in leveling.usable_names(pc):
                    doc = (det.get("grants") or {}).get(
                        (det.get("resolves") or {}).get(name, name)) or {}
                    spent |= {str((doc.get(s) or {}).get("pool") or "").lower()
                              for s in ("cost", "drain")}
            orphans = sorted(p for p in pc.pools if p in declared and p not in spent)
            assert not orphans, f"{cid} {level}: {orphans} shown with nothing to spend them"


def test_a_blood_benders_fist_strikes_to_harm_unless_told_otherwise():
    """#36: "4 non-lethal bludgeoning" from a class whose unarmed strike is the monk's.
    Improved Unarmed Strike (CRB p.129): lethal or non-lethal at the striker's choice."""
    pc = _bender("blood spike", 1)
    assert pc.weapon("unarmed").get("nonlethal") is False
    assert pc.lethality_swap("unarmed", "nonlethal") == ""


def test_a_fighter_without_the_feat_still_punches_nonlethal():
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "fighter", "level": 1, "feats": [], "ranks": {}})
    pc = from_dict(d, ref="pc")
    from rules import weapons as weapons_mod

    assert weapons_mod.lethality_of(pc.weapon("unarmed")) == "nonlethal"


def test_metamagic_is_shut_for_a_body_with_no_spells():
    """#3: 32 metamagic feats were offered to a Blood Bender."""
    from rules import creation

    rows = creation.feat_rows(_bender())
    assert not [r for r in rows["open"] if "metamagic" in [t.lower() for t in r["types"]]]
    shut = [r for r in rows["shut"] if "metamagic" in [t.lower() for t in r["types"]]]
    assert shut and "casts none" in shut[0]["unmet"][0]
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "wizard", "level": 1, "ranks": {}})
    wizard = creation.feat_rows(from_dict(d, ref="pc"))
    assert [r for r in wizard["open"] if "metamagic" in [t.lower() for t in r["types"]]]


def test_the_planners_thrown_blood_spike_is_the_ability():
    """#31: the reading held the ability; the plan's improvised throw of it is struck and
    the use put in its place, aimed where the reading aimed."""
    from gm import means

    scene, _e = _fight(_bender())
    judged = [{"act": "cast", "power": "Blood Spike", "aim": "ref:c1",
               "span": "hurl a Blood Spike at the thug",
               "held": ["ability", "Blood Spike Projectile"]}]
    raw = [{"op": "attack", "actor": "pc", "target": "c1",
            "params": {"weapon": "improvised", "item": "Blood Spike", "thrown": True}}]
    out = means.held_uses(raw, judged, None, scene)
    assert [r["op"] for r in out] == ["use_ability"]
    assert out[0]["params"]["ability"] == "Blood Spike Projectile" and out[0]["target"] == "c1"


def test_an_ability_the_enum_question_picked_is_not_used():
    """The playtest's "fly into a Blood Rage" came back held as Blood Pool Manifestation
    by the enum question; that is not the player's use of it."""
    from gm import means

    scene, _e = _fight(_bender())
    judged = [{"act": "other", "power": "Blood Rage",
               "held": ["ability", "Blood Pool Manifestation"]}]
    assert means.held_uses([], judged, None, scene) == []


def test_the_room_is_not_searched_for_the_characters_own_ability():
    """#32: "There is no blood spike projectile here" — the scenery reader asked whether
    the ability's name lay in the room."""
    from gm import acts_to_ops, scenery

    scene, e = _fight(_bender())
    frame = {"actions": [{"act": "use", "object": "Blood Spike Projectile",
                          "target": "the thug", "means": "power",
                          "power": "Blood Spike Projectile", "commit": "done",
                          "span": "use Blood Spike Projectile on the thug"}]}
    rows = acts_to_ops.table(frame, scene)
    asked = []
    scenery.handled(frame, rows, e, [], ask_fn=lambda *a, **k: asked.append(a) or {})
    assert not asked and not any(r.unheld for r in rows)
