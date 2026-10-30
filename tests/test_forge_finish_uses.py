"""Forge finishes with limited uses are spent (rules/finish_uses.py).

The 0.2.24 items lane found it: the forge's material documents say `uses: "once"` on cold
iron and ghost salt blanching and on holy anointing, and `uses: "per_day"` on troll blood
and wyroot, and nothing read `uses` on a forge spec. Measured on the base (66e654e8)
with a seeded fight against a thug with DR 5/cold iron: a once-blanched longsword struck
as cold iron for 10 of 10 hits; three wyroot crits fired the "once a day" rider three
times; and every self-recipient rider — wyroot's temporary hit point, troll blood's fast
healing — landed on the FOE.

The book's rule for the printed case (weapon blanch, APG p.184 / UE p.103): "The
blanching remains effective until you make a successful attack with the weapon", and it
"counts as both materials for the first successful hit". Ghost salt (Pathfinder Society
Field Guide p.48): "remains effective until the weapon makes a successful attack". Wyroot
(UE p.52): "can gain at most 1 life point per day". These tests run on the REAL material
documents.
"""
from __future__ import annotations

import pytest

from rules import blacksmith as bs
from rules import finish_uses, forge_items
from rules import worldclass as wc
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from tests._board import face_to_face


def blade(rid: str, head: str = "iron", finish=(), **over) -> dict:
    rec = {"id": rid, "name": rid.replace("-", " ").title(), "kind": "crafted",
           "craft": "blacksmith", "count": 1, "gear": "weapon", "base": "longsword",
           "slot": "hands", "quality_index": 1, "masterwork": False,
           "pieces": {"head": {"material": head, "passes": 0}},
           "quench": None, "finish": list(finish), "flaws": [],
           "smith": {"level": 1, "perks": {}}, "schema": 3}
    rec.update(over)
    return rec


def run(e, raw):
    return e.run(e.validate(raw, origin="author:test")).outcomes


def armed(rec, seed=7, dr=True):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=seed))
    pc = s.pc()
    foe = s.add(instantiate("thug", scene=s, name="the thug"))
    foe.hp = foe.hp_max = 5000
    if dr:
        foe.grant_defence("damage_reduction", "", amount=5, bypass="cold iron",
                          source="fey blood")
    pc.add_stock(forge_items.stock_item(rec))
    run(e, [{"op": "wear", "actor": "pc", "because": "t", "params": {"item": rec["id"]}}])
    run(e, [{"op": "begin_encounter",
             "params": {"sides": {"you": ["pc"], "them": [foe.ref]}}}])
    face_to_face(s)
    return s, e, pc, foe


def swing(s, e, foe):
    s.turn = [r for r, _ in s.initiative].index("pc")
    return run(e, [{"op": "attack", "actor": "pc", "target": foe.ref,
                    "visibility": "hidden", "params": {}, "because": "t"}])[-1]


def hits(s, e, foe, n, tries=80):
    out = []
    for _ in range(tries):
        o = swing(s, e, foe)
        out += [(o, d) for d in o.effects if d.get("kind") == "damage"]
        if len(out) >= n:
            return out[:n]
    pytest.fail(f"only {len(out)} hits in {tries} swings")


# --- the blanches ------------------------------------------------------------------------------

def test_a_once_blanched_blade_strikes_as_cold_iron_for_one_hit_not_ten():
    """Measured on the base: a cold iron blanched longsword struck as cold iron for 10 of
    10 hits on a DR 5/cold iron thug. The book's blanch lasts "until you make a successful
    attack": the first hit bypasses the DR and says so, the blanch is told spent, and the
    second hit is steel against the DR again."""
    s, e, pc, foe = armed(blade("blanched-sword", finish=["cold-iron-blanching"]))
    assert "cold_iron" in pc.weapon()["strikes_as"]
    (first, d1), (second, d2) = hits(s, e, foe, 2)
    assert d1["reduced"] == 0, d1
    assert "The cold iron bites past the thug's DR 5/cold iron." in first.tell
    assert "The cold iron blanching on Kesst Vayr's Blanched Sword is spent." in first.tell
    assert any(x.get("kind") == "finish_spent" and x.get("finish") == "cold-iron-blanching"
               for x in first.effects)
    assert d2["reduced"] == 5, d2
    assert "bites past" not in second.tell
    assert "cold_iron" not in pc.weapon()["strikes_as"]
    row, = finish_uses.rows(pc, pc.crafted_record("blanched-sword"))
    assert (row["left"], row["count"], row["uses"]) == (0, 1, "once")


def test_a_miss_does_not_spend_the_blanch():
    """The book spends it on "a successful attack" — a miss leaves the dose on the blade."""
    s, e, pc, foe = armed(blade("blanched-sword", finish=["cold-iron-blanching"]))
    foe.apply_effect(ActiveEffect(name="a wall of a shield", kind="buff", source="test",
                                  modifiers=[{"kind": "combat_mod", "target": "ac",
                                              "amount": 60}]))
    missed = 0
    for _ in range(6):
        o = swing(s, e, foe)
        if any(d.get("kind") == "damage" for d in o.effects):
            break  # a natural 20 hits whatever the AC
        missed += 1
        assert "cold_iron" in pc.weapon()["strikes_as"], f"spent by miss {missed}"
    assert missed >= 1


def test_a_full_attack_keeps_the_blanch_for_the_first_hit_only():
    """A full attack keeps one weapon row for every swing (`_op_attack`'s `named`), so a
    blanch spent on the first hit had to leave that row too, or the second swing of the
    same attack would still strike as cold iron. Checked on the row the engine holds."""
    s, e, pc, foe = armed(blade("blanched-sword", finish=["cold-iron-blanching"]))
    w = pc.weapon()
    said = e._spend_on_hit(pc, w)
    assert said and "is spent" in said[0]["tell"]
    assert "cold_iron" not in w["strikes_as"]
    assert e._spend_on_hit(pc, w) == [], "spent once, never twice"


def test_a_cold_iron_head_under_a_cold_iron_blanch_stays_cold_iron():
    """"A weapon made of one special material ... counts as both materials for the first
    successful hit": spending the blanch must not take the HEAD's own cold iron with it."""
    s, e, pc, foe = armed(blade("cold-sword", head="cold-iron",
                                finish=["cold-iron-blanching"]))
    hits(s, e, foe, 1)
    assert "cold_iron" in pc.weapon()["strikes_as"]
    (_o, d), = hits(s, e, foe, 1)
    assert d["reduced"] == 0


def test_ghost_salt_is_spent_by_its_first_hit_on_a_ghost():
    """Ghost salt (PFS Field Guide p.48) "remains effective until the weapon makes a
    successful attack". Before, a salted plain-iron blade hit an incorporeal creature for
    full damage forever; now the first hit bites "as if it were flesh" and the second, a
    nonmagical blade again, passes clean through."""
    s, e, pc, foe = armed(blade("salted-sword", finish=["ghost-salt-blanching"]), seed=9,
                          dr=False)
    foe.apply_effect(ActiveEffect(name="test body", kind="trait", source="test",
                                  tags=("subtype.incorporeal",)))
    for _ in range(40):
        o = swing(s, e, foe)
        if any(d.get("kind") == "damage" for d in o.effects):
            break
    else:
        pytest.fail("never hit")
    assert "bites the thug as if it were flesh" in o.tell
    assert "The ghost salt blanching on Kesst Vayr's Salted Sword is spent." in o.tell
    for _ in range(40):
        o = swing(s, e, foe)
        if any(d.get("kind") == "blow_harmless" for d in o.effects):
            break
    else:
        pytest.fail("the spent blade never landed again")
    assert "not magic" in o.tell


# --- holy anointing: its first battle ----------------------------------------------------------

def test_holy_anointing_lasts_its_first_battle_and_then_runs_its_course():
    """Holy anointing (house finish): "For its first battle after the rite it bites the
    undead harder; the rites do not last." Measured on the base: the +2 against undead
    was in the build for good. Now the fight it was wielded in spends it at the fight's
    end (`Scene.end_encounter`, the one door), with a tell in the log."""
    s, e, pc, foe = armed(blade("anointed-sword", finish=["holy-anointing"]), dr=False)
    rec = pc.crafted_record("anointed-sword")
    assert any(sp.get("source") == "holy-anointing"
               for sp in forge_items.build(rec)["specs"])
    s.end_encounter()
    rec = pc.crafted_record("anointed-sword")
    assert not any(sp.get("source") == "holy-anointing"
                   for sp in forge_items.build(rec)["specs"])
    assert any(x.get("op") == "finish-spent"
               and "holy anointing on Kesst Vayr's Anointed Sword has run its course" in x["tell"]
               for x in s.log)


# --- per-day riders: wyroot and troll blood ------------------------------------------------------

def _wyroot():
    return blade("wyroot-sword", quench="troll-blood",
                 pieces={"head": {"material": "iron", "passes": 0},
                         "haft": {"material": "wyroot-haft", "passes": 0}})


def test_wyroots_spark_goes_to_the_wielder_once_a_day_and_comes_back_with_the_day():
    """Measured on the base: three wyroot crits fired the "once a day" rider three times,
    and its temporary hit point landed on the FOE (pc 0, thug 1) — `_item_riders` sent
    every rider at the defender and never read `recipient: self`. Wyroot (UE p.52): "at
    most 1 life point per day"."""
    s, e, pc, foe = armed(_wyroot(), dr=False)
    w = pc.weapon()
    first = e._item_riders(pc, foe, w, crit=True)
    assert pc.temp_hp == 1 and foe.temp_hp == 0
    assert any("wyroot haft has given what it has today" in x["tell"] for x in first)
    e._item_riders(pc, foe, pc.weapon(), crit=True)
    e._item_riders(pc, foe, pc.weapon(), crit=True)
    rows = {r["source"]: r for r in finish_uses.rows(pc, pc.crafted_record("wyroot-sword"))}
    assert rows["wyroot-haft"]["left"] == 0
    pc.reset_item_uses()
    rows = {r["source"]: r for r in finish_uses.rows(pc, pc.crafted_record("wyroot-sword"))}
    assert rows["wyroot-haft"]["left"] == 1, "a per-day use comes back with the day"


def test_troll_blood_heals_its_bearer_not_the_foe():
    """Troll blood's quench mark is "fast healing 1 for a minute after the first wound
    each day", recipient self. Measured on the base: the fast healing landed on the thug."""
    s, e, pc, foe = armed(_wyroot(), dr=False)
    e._item_riders(pc, foe, pc.weapon())
    assert any(x.kind != "item_spent" and "ast healing" in (x.name or "")
               for x in pc.effects), [x.name for x in pc.effects]
    assert not any("ast healing" in (x.name or "") for x in foe.effects)


def test_a_spent_once_stays_spent_across_a_new_day_and_a_save():
    """The 0.2.24 rule (`Actor.reset_item_uses`): once is permanent, per-day resets. And
    the count lives on the item's record, so a save and a load keep it."""
    s, e, pc, foe = armed(blade("blanched-sword", finish=["cold-iron-blanching"]))
    e._spend_on_hit(pc, pc.weapon())
    pc.reset_item_uses()
    back = from_dict(to_dict(pc), ref="pc")
    assert "cold_iron" not in back.weapon("blanched-sword")["strikes_as"]


# --- the bench: a plain Stock's tags, the card, a fresh dose -------------------------------------

def _bench_blade(pc) -> str:
    item = bs.Work(form="item", material="iron", shape="longsword", gear="weapon",
                   quality=2, pieces={"head": {"material": "iron", "passes": 0},
                                      "haft": {"material": "ash-haft", "passes": 0}},
                   finish=["cold-iron-blanching"], smith={"level": 2, "perks": {}},
                   tier="common")
    item.name = bs.work_name(item)
    return bs.put(pc, item, 1)


def test_a_bench_kept_blade_remembers_a_spent_blanch_in_its_tags_and_a_save():
    """A forge item made at the bench is a plain Stock whose record is rebuilt from its
    `forge.*` tags on every read, so a count written to a rebuilt record would vanish. The
    spend writes `forge.spent.*`, the shelf entry is re-keyed (a fresh blade put later must
    not stack onto a spent one), and the save keeps it."""
    pc = load_pc("fixtures/pc-kesst.json")
    key = _bench_blade(pc)
    rec = bs.records(pc)[0]
    assert "cold_iron" in forge_items.build(rec)["strikes_as"]
    finish_uses.spend(pc, rec, "cold-iron-blanching~0")
    assert key not in pc.stock, "re-keyed"
    st, = [v for v in pc.stock.values() if bs.Work.from_stock(v)]
    assert "forge.spent.cold-iron-blanching~0.1" in st.properties
    back = from_dict(to_dict(pc), ref="pc")
    rec2 = bs.records(back)[0]
    assert rec2["spent"] == {"cold-iron-blanching~0": 1}
    assert "cold_iron" not in forge_items.build(rec2)["strikes_as"]
    assert any("spent: apply it again at the forge" in line
               for line in map(finish_uses.card_line, forge_items.build(rec2)["uses"]))


def test_reapplying_a_spent_blanch_at_the_forge_gives_a_fresh_dose():
    """The Finish step refused a finish the item already carries ("It already carries
    cold iron blanching"), which would have left a spent blanch spent for good. A spent
    one takes a fresh dose; one still whole is refused as before."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.inventory.clear()
    _bench_blade(pc)
    pc.carry("cold-iron-blanching", 2)
    prog = wc.Progress(track="blacksmith", level=2, perks={})
    where = {"smithy": None, "kit": True}

    def plan():
        item = next(p for p in bs.rack(pc) if p.form == "item")
        tr = next(p for p in bs.rack(pc) if p.key == "inv:cold-iron-blanching")
        return bs.plan_step(pc, prog, "finish", {"item": (item, 1), "treatment": (tr, 1)},
                            1, where=where)

    assert any("already carries" in p for p in plan().problems)
    finish_uses.spend(pc, bs.records(pc)[0], "cold-iron-blanching~0")
    fresh = plan()
    assert fresh.problems == [], fresh.problems
    (w, _n), = fresh.outputs
    assert w.finish == ["cold-iron-blanching"] and w.spent == {}
    assert "cold_iron" in forge_items.build(bs.record(w))["strikes_as"]


def test_the_rack_card_says_what_is_left():
    """The bench shows the remaining uses: the item's rack badges name the finish's state."""
    pc = load_pc("fixtures/pc-kesst.json")
    _bench_blade(pc)
    item = next(p for p in bs.rack(pc) if p.form == "item")
    assert "cold iron blanching 1/1" in item.badges()
    finish_uses.spend(pc, bs.records(pc)[0], "cold-iron-blanching~0")
    item = next(p for p in bs.rack(pc) if p.form == "item")
    assert "cold iron blanching spent" in item.badges()
