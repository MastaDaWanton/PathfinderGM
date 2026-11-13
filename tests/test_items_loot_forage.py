"""Items, loot, forage and harvest after the owner's 0.2.25 report (2026-11-01, Corvin's game).

Each test names the turn of that report it was measured on. The causes, traced:

  1. "pick the chaSMIER LEAF" (turn 51) ledgered a leaf off a sentence about where the herb
     grows, and the give took it — any herb the prose mentioned, with no forage roll; "loot
     the body" (turn 85) put `"body": 1` in the pack.
  2. A mindless grub carried 2d6 sp; the scheme's Anise was a label nobody carried; a club
     a dead woman had swung left the world with her body; "…then loot her" was dropped.
  3. "kill it and skin iot for parts" was read as leatherworking and refused for want of a
     tannery.
  4. A forage inside the shrine found herbs and a guard; a CR 19 vishap met a level-3
     character's forage; two forage refusals were filed `resolved`.
  6. A non-lethal poultice on a wounded body with no non-lethal said "already unhurt" and
     spent the dose.
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, judgement, scenery
from rules import bestiary, gathering, harvest, places, schemes
from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from tests._places import stand_on

REGIONAL = "The rare Chasmyre Leaf grows among the tangled roots and stagnant waters of the marsh."


def _scene(biome: str = "swamp"):
    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    pc.stock = {}
    s.add(pc)
    stand_on(s, biome)
    return s


def _asker(answer, quote=""):
    def ask(place, passages, thing, given=()):
        return answer, quote, ""
    return ask


def _pick(item):
    return [{"op": "give", "actor": "pc", "params": {"item": item, "to": "pc"},
             "because": "the player took it"}]


# --- 1. herbs are foraged, bodies are looted --------------------------------------------------

def test_a_herb_the_page_says_grows_here_is_not_picked_up():
    """Turn 51: the reader answered "shown here" for "chasmier leaf" with the quote
    "The rare Chasmyre Leaf grows among the tangled roots…" — the page's own sentence, so
    the quote check passed, the leaf was ledgered and the give minted a goods line
    "chasmier leaf". A name off the herb catalogue, or a near spelling of one, is never
    ledgered, whatever the reader says; the pick-up is then refused by the engine."""
    s = _scene()
    e = Engine(s, Dice(seed=1))
    raw = _pick("chasmier leaf")
    rows = scenery.ground(raw, e, [REGIONAL], ask_fn=_asker(scenery.SHOWN, REGIONAL))
    assert rows[0]["answer"] == scenery.GROWING and not rows[0].get("ledgered")
    assert s.prop_named("chasmier leaf") is None
    out = e.run(e.validate(raw)).outcomes[0]
    assert out.status == "refused"
    assert "chasmier leaf" not in s.pc().goods and not s.pc().inventory.get("chasmyre-leaf")


def test_near_names_of_plants_match_and_scenery_nouns_do_not():
    """`ingredients.by_name` is exact on purpose (the satchel), so "chasmier" missed
    Chasmyre; the scenery check compares against the catalogue at a 0.84 ratio. Checked on
    30 common scenery nouns: the nearest, "arrow" against Yarow, is 0.80."""
    assert scenery.growing_herb("the chaSMIER LEAF") == "Chasmyre Leaf"
    assert scenery.growing_herb("the marsh-mallow") == "Marsh-Mallow"
    for thing in ("a clay pot", "a stool", "the bucket", "a torch", "an arrow", "a cloak",
                  "bread", "the club", "a stone", "salt", "the body"):
        assert scenery.growing_herb(thing) == "", thing


def test_the_reader_has_a_growing_answer_and_a_body_answer():
    """The two new closed answers are offered and demonstrated, and a regional sentence is
    named as showing nothing lying here."""
    assert scenery.GROWING in scenery.ANSWERS and scenery.BODY in scenery.ANSWERS
    msgs = scenery.messages("the marsh", REGIONAL, "the leaf")
    shown = {__import__("json").loads(m["content"])["answer"] for m in msgs
             if m["role"] == "assistant"}
    assert {scenery.GROWING, scenery.BODY} <= shown
    assert "grows or is found in this land" in msgs[0]["content"]


def test_taking_the_body_is_the_loot_of_the_dead_and_never_goods():
    """Turn 85: "loot the body" became `give item: body`, the reader said "shown here" off
    a sentence about the grub's jaws, and the pack held `"body": 1`. A body is the loot of
    the creature lying here; nothing called "body" is ever ledgered or minted."""
    s = _scene("urban")
    grub = s.add(instantiate("giant-rot-grub", scene=s))
    grub.hp = -1
    grub.die("test")
    e = Engine(s, Dice(seed=1))
    raw = _pick("body")
    rows = scenery.ground(raw, e, ["The grub's jaws lock onto you."],
                          ask_fn=_asker(scenery.BODY))
    assert rows[0]["answer"] == scenery.BODY and rows[0]["looted"] == grub.ref
    assert raw == [{"op": "loot", "actor": "pc", "because": "the player searches the body",
                    "params": {"from_": grub.ref}}]
    assert s.prop_named("body") is None
    e.run(e.validate(raw))
    assert "body" not in s.pc().goods


def test_a_body_named_by_who_it_was_is_never_goods_whatever_the_reader_says():
    """Code validates the reader: words that name somebody lying here ("the grub") are a
    body even when the reader answered "shown here"."""
    s = _scene("urban")
    grub = s.add(instantiate("giant-rot-grub", scene=s))
    grub.die("test")
    e = Engine(s, Dice(seed=1))
    raw = _pick("the giant rot grub")
    rows = scenery.ground(raw, e, ["The giant rot grub lies still."],
                          ask_fn=_asker(scenery.SHOWN, "The giant rot grub lies still."))
    assert rows[0]["answer"] == scenery.BODY and raw[0]["op"] == "loot"


# --- 2. looting ---------------------------------------------------------------------------------

def test_a_mindless_grub_with_treasure_none_carries_no_coin():
    """Turn 85: the giant rot grub (Int —, "Treasure none") was stripped of 6 sp. A missing
    Int was read as 10 and every block is `kind: npc`, so the derived 2d6 sp fired for all
    165 printed blocks with no Int. The Treasure line is read first (a giant spider, also
    Int —, prints "incidental": lair treasure, not coin on the body)."""
    for template in ("giant-rot-grub", "giant-spider"):
        grub = instantiate(template)
        assert not grub.kit_pending, template
        assert bestiary.collapse_kit(grub) == [] and not grub.purse, template
    # A person with a mind and standard treasure still carries a purse.
    assert instantiate("thug").kit_pending.get("wealth")


def test_the_lost_thing_is_on_the_rival_and_comes_off_her_body():
    """Turn 49-50: the-lost-thing's Anise was a label (`_item_for`) and nobody carried it,
    so killing and looting the rival gave 6 sp and `returned` (holds(pc, $lost)) could
    never fire. The item slot says who holds it (`held_by`), and that person carries it."""
    s = _scene()
    e = Engine(s, Dice(seed=1))
    rival = s.add(instantiate("farmer", scene=s, name="Lila Duskwatch"))
    slots = {"rival": {"role": "kin"}, "lost": {"item": "keepsake", "held_by": "rival"}}
    filled = {"rival": {"kind": "actor", "ref": rival.ref, "name": rival.name},
              "lost": {"kind": "item", "id": "anise", "name": "Anise"}}
    assert schemes._place_held(e, slots, filled) == ["lost"]
    assert schemes._place_held(e, slots, filled) == [], "placed once"
    assert any(st.base == "Anise" for st in rival.stock.values())
    rival.hp = -20
    rival.die("test")
    e.run(e.validate([{"op": "loot", "actor": "pc", "params": {"from_": rival.ref}}]))
    assert schemes._holds(s.pc(), filled["lost"])


def test_the_shipped_lost_thing_names_its_holder_and_validates():
    doc = schemes.all_schemes()["the-lost-thing"]
    assert doc["slots"]["lost"]["held_by"] == "rival"
    assert schemes.validate(doc) == []
    bad = dict(doc, slots=dict(doc["slots"], lost=dict(doc["slots"]["lost"], held_by="market")))
    assert any("held_by" in p for p in schemes.validate(bad))


def test_the_weapon_in_hand_is_looted_even_when_the_list_lacks_it():
    """Turns 48-50: Lila Duskwatch swung a club twice and the loot said "6 sp". The loot
    read only `weapons`; the hand (`equipped`) is read too."""
    s = _scene()
    body = s.add(instantiate("farmer", scene=s, name="Lila Duskwatch"))
    body.weapons = []
    body.equipped = "club"
    body.die("test")
    e = Engine(s, Dice(seed=1))
    tell = e.run(e.validate([{"op": "loot", "actor": "pc",
                              "params": {"from_": body.ref}}])).outcomes[0].tell
    assert "club" in tell and body.equipped is None


def test_a_tidied_corpse_leaves_its_gear_where_it_fell():
    """Then the body was tidied away two turns later with the club still on it — gone from
    the world. CircleMUD's corpse spills its contents when it decays; here the gear goes
    on the props ledger, one record each, and is picked up as itself."""
    s = _scene()
    body = s.add(instantiate("farmer", scene=s, name="Lila Duskwatch"))
    body.hp = -20
    body.die("test")
    e = Engine(s, Dice(seed=1))
    tells = []
    for _ in range(4):
        tells += e.tidy_the_fallen()
    assert body.ref not in s.people
    assert any("club" in t for t in tells)
    rec = s.prop_on_the_ground("club")
    assert rec is not None and rec["from_"] == "club"
    e.run(e.validate(_pick("club")))
    assert "club" in s.pc().weapons or "club" in s.pc().goods


def test_punch_until_dead_then_loot_her_keeps_the_loot():
    """Turn 49: "punch until she is dead thernm loot her" read `attack, take`; the take had
    no object ("nothing named to take") and the loot detector dropped its loot because she
    was standing when the plan was read. Read as `loot`, the table aims it at the one the
    blow is aimed at, and the injector keeps a loot of somebody the plan strikes first."""
    s = _scene()
    lila = s.add(instantiate("farmer", scene=s, name="Lila Duskwatch"))
    lila.pronouns = "she/her"
    frame = {"question": False, "claims": [], "actions": [
        {"act": "attack", "target": "she", "span": "punch until she is dead"},
        {"act": "loot", "target": "her", "span": "loot her"}]}
    rows = acts_to_ops.table(frame, s)
    loot = [i for r in rows for i in r.intents if i["op"] == "loot"]
    assert loot and loot[0]["params"]["from_"] == lila.ref
    plan = [{"op": "attack", "actor": "pc", "target": lila.ref, "params": {}}] + loot
    kept = judgement.inject_loot(plan, "punch until she is dead thernm loot her", s)
    assert [r["op"] for r in kept] == ["attack", "loot"]


def test_loot_the_body_finds_the_one_body_here():
    s = _scene("urban")
    grub = s.add(instantiate("giant-rot-grub", scene=s))
    grub.die("test")
    frame = {"question": False, "claims": [], "actions": [
        {"act": "loot", "target": "the body", "span": "loot the body"}]}
    rows = acts_to_ops.table(frame, s)
    assert [i["params"]["from_"] for r in rows for i in r.intents] == [grub.ref]


# --- 3. skinning by typing -----------------------------------------------------------------------

def test_skin_it_for_parts_is_the_harvest_not_a_craft():
    """Turn 86: "kill it and skin iot for parts" was read `craft: leatherworker` and refused
    for want of a tannery. The reader's `harvest` act is the engine's `harvest` op, which
    runs the harvest sheet's own door (`harvest.take_part`)."""
    s = _scene("forest")
    wolf = s.add(instantiate("wolf", scene=s))
    wolf.hp = -20
    wolf.die("test")
    harvest.mark_the_dead(s)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "harvest", "target": "it", "object": "parts", "span": "skin it for parts"}]}
    rows = acts_to_ops.table(frame, s)
    built = [i for r in rows for i in r.intents]
    assert built and built[0]["op"] == "harvest" and built[0]["target"] == wolf.ref
    e = Engine(s, Dice(seed=3))
    before = len(s.pc().stock) + sum(s.pc().inventory.values())
    out = e.run(e.validate(built)).outcomes[0]
    assert out.status != "refused" and out.op == "harvest"
    assert any(f["kind"] == "harvest" for f in out.effects)
    assert all(p["taken"] is not None
               for p in harvest.parts(wolf, s.pc(), now=s.clock_minutes))
    got = len(s.pc().stock) + sum(s.pc().inventory.values())
    assert got > before or "ruin" in out.tell.lower() or "lost" in out.tell.lower()


def test_a_living_body_is_not_skinned():
    s = _scene("forest")
    wolf = s.add(instantiate("wolf", scene=s))
    wolf.hp = -1
    e = Engine(s, Dice(seed=3))
    out = e.run(e.validate([{"op": "harvest", "actor": "pc", "target": wolf.ref,
                             "params": {}}], origin="author:test")).outcomes[0]
    assert out.status == "refused" and "still breathing" in out.tell


# --- 4. forage ------------------------------------------------------------------------------------

def test_no_forage_indoors():
    """The shrine (urban, a building) foraged Power leaf and a giant rot grub guarding it,
    inside. Under a roof there is no ground to search: refused, and no hour spent."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    room = next(p for p in places.home_set("5bbd0c40345f", places.URBAN)
                if places.is_indoors(p.id))
    s.at = room.id
    for a in s.people.values():
        a.at = room.id
    e = Engine(s, Dice(seed=1))
    clock = s.clock_minutes
    out = e.run(e.validate([{"op": "forage", "actor": "pc", "params": {"hours": 1}}],
                           origin="author:test")).outcomes[0]
    assert out.status == "refused" and "indoors" in out.tell
    assert s.clock_minutes == clock and not s.awaiting


def test_a_forage_with_company_is_a_refusal_not_resolved():
    """"No foraging happens… You are with…" came back `resolved`."""
    s = _scene()
    s.add(instantiate("thug", scene=s))
    e = Engine(s, Dice(seed=1))
    out = e.run(e.validate([{"op": "forage", "actor": "pc", "params": {}}],
                           origin="author:test")).outcomes[0]
    assert out.status == "refused" and out.tell.startswith("No foraging happens.")


def test_the_forage_creature_is_capped_by_the_characters_level():
    """Log 258: a CR 19 vishap (colossal, 362 hp) met a level-3 character's forage. The CR
    window was the trade level's alone; it is capped by the character's level too, and the
    block the engine will spawn is checked against it after the pick.

    Since 2026-11-13 the cap is the party's encounter budget (`encounter_budget`): the
    engine counts the PC at the lower of trade and body, so Herbalist 18 on a lone
    level-3 body is APL 1, whose wandering fights stop at challenging (CR 2, 600 XP) and
    whose guard stops at hard (CR 3, 800 XP)."""
    from rules import encounter_budget as eb, xp

    for seed in range(40):
        row = gathering.creature_for("swamp", 18, Dice(seed=seed), apl=1)
        assert row is not None and eb.xp_of(row) <= xp.CR_AWARD[2]
        row = gathering.creature_for("swamp", 18, Dice(seed=seed), guarding=True, apl=1)
        assert row is not None and eb.xp_of(row) <= xp.CR_AWARD[3]


def test_the_engine_forages_at_the_lower_of_trade_and_body(monkeypatch):
    """The engine's door, not the function: what `_gathering_encounter` hands the table is
    the party's APL with the PC at min(trade, body). A level-3 body with a trade of 18 is a
    lone level 3 (APL 1); a trade of 1 on the same body is a lone level 1 (APL -1)."""
    seen = []
    monkeypatch.setattr(gathering, "roll", lambda biome, level, dice, apl=None:
                        seen.append(apl) or gathering.Encounter("quiet", 1))
    s = _scene()
    s.pc().level = 3
    e = Engine(s, Dice(seed=1))
    e._gathering_encounter(s.pc(), "swamp", 18, "herb", effects=[])
    e._gathering_encounter(s.pc(), "swamp", 1, "herb", effects=[])
    assert seen == [1, -1]


# --- 6. a cure with nothing to cure ----------------------------------------------------------------

def test_a_nonlethal_poultice_on_a_body_with_none_is_not_spent():
    """Corvin, 36/58 hit points and no non-lethal: the marsh-mallow poultice "on the skin"
    cures non-lethal only, said "already unhurt" and the dose was gone. Now it is refused
    before the dose is spent, saying nothing would be healed and what does heal."""
    s = _scene()
    pc = s.pc()
    pc.hp = max(1, pc.hp_max - 10)
    pc.nonlethal = 0
    pc.add_stock(Stock(base="Marsh-Mallow Poultice", tier="common", potency=1.0,
                       craft="herbalist", form="poultice",
                       specs=[{"type": "heal", "dice": "1d3", "lethality": "nonlethal",
                               "route": "skin"}],
                       effects=["Marsh-Mallow: heals 1d3 non-lethal damage"]), 2)
    e = Engine(s, Dice(seed=1))
    out = e.run(e.validate([{"op": "use_item", "actor": "pc",
                             "params": {"item": "Marsh-Mallow Poultice", "how": "apply",
                                        "route": "skin"}}],
                           origin="author:test")).outcomes[0]
    assert out.status == "refused", out.tell
    assert "non-lethal damage only" in out.tell and "dose is kept" in out.tell
    assert sum(st.count for st in pc.stock.values()) == 2
