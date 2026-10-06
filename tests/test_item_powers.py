"""What worn magic does, and a magic item's powers (contracts §4, plan §8.4-8.5, lane C).

Before lane C: `resistance()` and `damage_reduction()` asked the forged SUIT alone, so a
shield of energy resistance, a ring from the catalogue and a cloak bound at the enchanter's
bench were worn and did nothing; a worn immunity refused nothing; a ring's layer was never
read (`_standing_mods` read only an unforged record's flat `specs`); the cast path rolled no
check against spell resistance; and an item's powers had no door at all.
"""
from __future__ import annotations

import pytest

from rules import effectspec as es
from rules import forge_items
from rules.intents import IntentError
from tests.test_enchant_engine import (_fight, _foe, _record, _run, _saves_roll, _table,
                                       _wear)


def _layered(item_id, slot, props, enhancement=0, name=None):
    """An unforged record — a ring, a cloak — carrying a layer (no build: contracts §3.4,
    `magic_layer.record_specs`)."""
    return {"id": item_id, "name": name or item_id.replace("-", " ").title(),
            "kind": "crafted", "craft": "enchanter", "slot": slot,
            "magic": {"schema": 1, "enhancement": enhancement,
                      "properties": [p if isinstance(p, dict) else {"id": p}
                                     for p in props],
                      "flat": [], "powers": []}}


# --- worn readers --------------------------------------------------------------------------

def test_a_ring_of_protection_reaches_the_sheets_armour_class_bound_or_bought():
    """Contracts §4 and the live check: a ring of protection +2 on the sheet's AC. The
    catalogue's ring has worked since stage 4; a ring BOUND at the enchanter's bench is an
    unforged record whose layer `_standing_mods` never read. Off, and it is gone."""
    s, e = _table()
    pc = s.pc()
    ac = pc.ac()
    pc.wear(_layered("ring-prot", "ring", [{"id": "deflection", "choice": {"bonus": 2}}],
                     name="Ring of Protection +2"), 0)
    terms = [(m.source, m.value, m.type) for m in pc.ac_modifiers() if m.type == "deflection"]
    assert terms == [("Ring of Protection +2", 2, "deflection")]
    assert pc.ac() == ac + 2
    pc.take_off("Ring of Protection +2")
    assert pc.ac() == ac
    pc.slots["ring"] = ["Ring of Protection +2", None]
    assert pc.ac() == ac + 2


def test_a_shield_of_energy_resistance_and_invulnerable_armour_are_read_while_worn():
    """Plan §8.3: resistance and DR "extended from the forged suit to every worn record".
    Measured before: `_armour_build_specs` read the armour slot's suit only, so a shield
    of fire resistance stopped no fire."""
    s, e = _table()
    pc = s.pc()
    pc.shield = "none"
    pc.add_stock(forge_items.stock_item(_record(
        "fire-shield", "heavy shield", gear="shield",
        props=[{"id": "energy-resistance", "choice": {"energy": "fire"}}])))
    pc.add_stock(forge_items.stock_item(_record("plate", "breastplate", gear="armour",
                                                props=["invulnerability"])))
    assert pc.resistance("fire") == 0 and pc.damage_reduction("slashing") is None
    _wear(e, "fire-shield")
    _wear(e, "plate")
    assert pc.resistance("fire") == 10
    dr = pc.damage_reduction("slashing")
    assert (dr.amount, dr.bypass) == (5, "magic") and "Plate" in dr.source
    assert pc.damage_reduction("slashing", ("magic",)) is None
    pc.take_off("Fire Shield")
    pc.shield = "none"
    assert pc.resistance("fire") == 0


def test_a_worn_immunity_refuses_at_the_condition_door_and_a_sense_is_a_tag():
    """Plan §8.4: "a worn immunity refuses conditions in that family" and `sense.*` tags
    while worn. A periapt of health (catalogue) refused no disease; goggles of night gave
    no darkvision a reader could ask."""
    s, e = _table()
    pc = s.pc()
    pc.wear({"id": "fearless", "name": "Badge of Courage", "slot": "neck",
             "specs": [{"type": "immunity", "target": "fear"}]}, 0)
    out = _run(e, [{"op": "condition", "because": "t",
                    "params": {"condition": "shaken", "to": "pc"}}]).outcomes[0]
    assert not pc.has_condition("shaken"), out.tell
    assert "fear" in out.tell.lower()
    pc.slots["eyes"] = ["Goggles of Night"]
    assert pc.has_state("sense.darkvision")
    pc.slots["eyes"] = [None]
    assert not pc.has_state("sense.darkvision")
    pc.slots.setdefault("neck", [None])
    pc.take_off("Badge of Courage")
    assert "fear" not in pc.immunities


def test_worn_fast_healing_ticks_on_the_round_and_stops_when_it_comes_off():
    """`fast_healing` on a worn item had no reader: the round clock needs an effect, so it
    is the carried mechanism (`sync_carried`), granted with the item, removed with it."""
    s, e = _table()
    pc = s.pc()
    pc.wear({"id": "mender", "name": "Mending Band", "slot": "ring",
             "specs": [{"type": "fast_healing", "amount": 2}]}, 0)
    said = pc.sync_carried(e.dice)
    assert said and said[0]["kind"] == "worn"
    pc.hp = 1
    got = pc.run_periodic("round", 1, e.dice)
    assert pc.hp == 3 and got[0]["origin"] == "item:mender"
    pc.take_off("Mending Band")
    gone = pc.sync_carried(e.dice)
    assert gone and "no longer worn" in gone[0]["what"]
    assert not any(x.kind == "worn" for x in pc.effects)


# --- spell resistance ------------------------------------------------------------------------

def _cast_at(s, e, target, face):
    r = _run(e, [{"op": "cast", "actor": "pc", "because": "t", "visibility": "player",
                  "params": {"spell": "burning-hands", "aim": f"ref:{target.ref}"}}])
    asked = []
    for _ in range(10):
        if r.awaiting is None:
            break
        asked.append(r.awaiting["label"])
        r = e.resume(face if r.awaiting["label"].startswith("Caster level")
                     else int(r.awaiting["min"]))
    return next(o for o in r.outcomes if o.op == "cast"), asked


def test_spell_resistance_is_rolled_against_and_a_low_roll_leaves_the_target_untouched():
    """Plan §21.1 (C): "the cast path refuses a spell against SR 15 on a low roll". The cast
    said "spell resistance yes" and rolled nothing (docs/spells.md §5.1: "no creature
    carries an SR number"); a suit of SR 19 was a line on a card. The caster's own roll."""
    from tests.test_e_magic_harm import board

    s, e, man = board(fight=True)
    who = s.actors[man]
    who.hp = who.hp_max = 100
    who.wear({"id": "sr", "name": "Warded Band", "slot": "ring",
              "specs": [{"type": "spell_resistance", "amount": 19}]}, 0)
    assert who.spell_resistance_rating() == (19, "the Warded Band")
    out, asked = _cast_at(s, e, who, 1)
    assert any(a.startswith("Caster level check against") for a in asked), asked
    assert "breaks on the man in a stained jerkin's spell resistance" in out.tell
    assert who.hp == 100 and out.effects[0]["resisted"] == [man]
    s.turn = 0
    out, asked = _cast_at(s, e, who, 20)
    assert "breaks through" in out.tell and who.hp < 100


def test_a_layered_suit_of_spell_resistance_gives_its_wearer_the_rating():
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_record("warded", "breastplate", gear="armour",
                                                props=["spell-resistance-15"])))
    _wear(e, "warded")
    assert pc.spell_resistance_rating() == (15, "the Warded")


# --- use_item {item, power} ------------------------------------------------------------------

def _shield(props=("blinding",)):
    s, e = _table()
    pc = s.pc()
    pc.shield = "none"
    pc.add_stock(forge_items.stock_item(_record("flash-shield", "heavy shield",
                                                gear="shield", props=props)))
    return s, e, pc


def _use(e, power, item="flash-shield"):
    return _run(e, [{"op": "use_item", "actor": "pc", "because": "t",
                     "params": {"item": item, "power": power}}]).outcomes[0]


def test_a_blinding_shield_flashes_twice_a_day_and_comes_back_with_the_day(monkeypatch):
    """CRB blinding: "Twice per day ... all within 20 feet except the wielder must make a
    DC 14 Reflex save or be blinded for 1d4 rounds." No op could use an item's power; the
    old card's line was prose. Counted on the item, refused with the uses named, back at
    the day boundary (`run_periodic("day")`)."""
    s, e, pc = _shield()
    thug = _foe(s)
    _saves_roll(monkeypatch, e, 2)
    with pytest.raises(IntentError, match="must be worn or in hand"):
        _use(e, "blinding")
    _wear(e, "flash-shield")
    out = _use(e, "blinding")
    assert "Reflex save against the blinding" in out.tell and thug.has_condition("blinded")
    assert not pc.has_condition("blinded")
    assert out.effects[0] == {"ref": "pc", "kind": "item_power", "item": "flash-shield",
                              "power": "blinding", "origin": "item:flash-shield",
                              "left": 1}
    assert [e.origin for e in thug.effects if e.key == "blinded"] == ["item:flash-shield"]
    _use(e, "blinding")
    with pytest.raises(IntentError, match="spent for today"):
        _use(e, "blinding")
    s.advance(minutes=24 * 60)
    assert _use(e, "blinding").effects[0]["left"] == 1


def test_a_power_that_casts_goes_through_the_cast_door_at_the_items_level():
    """Etherealness: "ethereal jaunt 1/day" (CRB). Cast through `_op_cast` with the item's
    caster level, no slot spent — a rogue with no spells uses it — every number stamped
    `item:<id>`."""
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_record("ghostplate", "breastplate", gear="armour",
                                                enhancement=1, props=["etherealness"])))
    _wear(e, "ghostplate")
    out = _use(e, "etherealness", "ghostplate")
    assert out.op == "use_item"
    assert "calls on the Ghostplate: Ethereal Jaunt (caster level 13" in out.tell
    cast = next(x for x in out.effects if x.get("kind") == "cast")
    assert cast["caster_level"] == 13
    with pytest.raises(IntentError, match="spent for today"):
        _use(e, "etherealness", "ghostplate")


def test_a_glamered_suit_changes_its_look_at_will_and_says_so():
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_record("plain-plate", "breastplate", gear="armour",
                                                props=["glamered"])))
    _wear(e, "plain-plate")
    for _ in range(3):
        out = _use(e, "glamered", "plain-plate")
        assert "ordinary clothes" in out.tell and "left" not in out.effects[0]
    with pytest.raises(IntentError, match="its powers are glamered"):
        _use(e, "flight", "plain-plate")


# --- In progress -------------------------------------------------------------------------

def test_a_binding_in_progress_cannot_be_drawn_or_sold():
    """Lane G (contracts §8.2): "wear/sell doors must ask `inprogress.held_back`". A sword
    on the enchanter's circle could be drawn and sold out from under the binding."""
    from rules import inprogress

    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_record("wip", "longsword")))
    key = next(k for k in pc.stock)
    # The herbalist's registration stands in for the enchanter's, which lane E registers;
    # the doors ask the In-progress block, not which craft wrote it.
    inprogress.begin(pc, key, craft="herbalist", minutes=600, now=s.clock_minutes,
                     label="Binding a +1 longsword", doing="being bound")
    out = _run(e, [{"op": "wear", "actor": "pc", "because": "t",
                    "params": {"item": "wip"}}]).outcomes[0]
    assert "still being bound" in out.tell and pc.equipped != "wip"
    out = _run(e, [{"op": "sell", "actor": "pc", "because": "t",
                    "params": {"item": key}}]).outcomes[0]
    assert "still being bound" in out.tell and key in pc.stock


# --- the sweep ---------------------------------------------------------------------------------

_BASE = {"weapon": ("longsword", "weapon"), "armour": ("breastplate", "armour"),
         "shield": ("heavy shield", "shield")}


def _skill(pc, skill):
    """A skill's terms, or its competence bonuses alone where the rules refuse the roll
    untrained (Use Magic Device for a rogue with no ranks)."""
    try:
        return sum(m.value for m in pc.skill_modifiers(skill))
    except Exception:  # noqa: BLE001 — IllegalSheet: untrained
        return sum(m.value for m in pc._buff_mods("skill_mod", skill))


def _snapshot(pc, foe):
    return {
        "attack": sum(m.value for m in pc.attack_modifiers(defender=foe)),
        "damage": sum(m.value for m in pc.damage_modifiers(defender=foe)),
        "ac": (pc.ac("melee"), pc.ac("ranged"), pc.touch_ac()),
        "saves": tuple(sum(m.value for m in pc.save_modifiers(x))
                       for x in ("fort", "ref", "will")),
        "skills": tuple(_skill(pc, k)
                        for k in ("stealth", "escape artist", "perception", "acrobatics",
                                  "use magic device")),
        "abilities": tuple(pc.ability_score(a)
                           for a in ("str", "dex", "con", "int", "wis", "cha")),
        "resist": tuple(pc.resistance(t)
                        for t in ("fire", "cold", "acid", "electricity", "sonic")),
        "dr": str(pc.damage_reduction("slashing")),
        "sr": pc.spell_resistance_rating(), "fort": pc.fortification(),
        "tags": sorted(t for t in pc.standing_tags()
                       if t.startswith(("property.", "sense."))),
        "weapon": {k: pc.weapon().get(k) for k in ("crit_range", "nonlethal",
                                                   "extra_attacks", "range_ft")},
        "immune": sorted(pc.immunities),
    }


@pytest.mark.parametrize("pid", sorted(es.properties()))
def test_taking_the_item_off_takes_every_contribution_with_it(pid):
    """Plan §21.1 (C): "removing the item removes every contribution (a sweep over all
    property ids)". Law 2 for the layer: nothing a property does may outlive the item —
    no number, no tag, no standing effect."""
    prop = es.properties()[pid]
    pick = (es.sample_choices(prop) or [None])[-1]       # the largest bonus offered
    gear = prop["gear"][0]
    s, e = _table()
    pc = s.pc()
    foe = _foe(s)
    was = (pc.equipped, pc.armour, pc.shield)
    before = _snapshot(pc, foe)
    effects = len(pc.effects)
    entry = {"id": pid, **({"choice": pick} if pick else {})}
    if gear in _BASE:
        base, kind = _BASE[gear]
        rec = _record("swept", base, gear=kind, props=[entry])
        pc.add_stock(forge_items.stock_item(rec))
        if kind == "shield":
            pc.shield = "none"
            before = _snapshot(pc, foe)
            was = (pc.equipped, pc.armour, pc.shield)
        _wear(e, "swept")
        name = rec["name"]
    else:
        slot = (prop.get("slots") or ["ring" if gear == "ring" else "neck"])[0]
        name = "Swept"
        pc.wear(_layered("swept", slot, [entry], name=name), 0)
    pc.sync_carried(e.dice)
    # Worn, it did something — a number or at least its `property.<id>` tag — or the
    # sweep below would pass by never having put anything on.
    assert _snapshot(pc, foe) != before, pid
    pc.take_off(name)
    pc.worn.pop(name.lower(), None)
    pc.equipped, pc.armour, pc.shield = was
    pc.sync_carried(e.dice)
    assert _snapshot(pc, foe) == before, pid
    assert len(pc.effects) == effects, [x.name for x in pc.effects]


# --- what lane F's curses ask of the readers -------------------------------------------------

def _with_wielded(monkeypatch, docs):
    """The weapon in hand's layer carrying `wielded` documents — the shape a curse's
    `curses.documents` adds (lane F) — without lane F's module on this branch."""
    import rules.sheet as sheet_mod

    real = sheet_mod.layer_of

    def layer_of(rec):
        lay = real(rec)
        if lay is not None and rec.get("id") == "blade":
            lay = dict(lay, wielded=list(lay.get("wielded") or []) + list(docs))
        return lay

    monkeypatch.setattr(sheet_mod, "layer_of", layer_of)


def test_a_wielded_document_lays_its_number_on_the_bearer_not_the_swing(monkeypatch):
    """Lane F: "a weapon's curse that penalises the wielder's saves and Perception must
    apply to the wielder". `_standing_mods` read a weapon record only on its own swing, so
    a blade's `wielded` penalty to Will reached nothing."""
    from tests.test_enchant_engine import _armed

    s, e, pc = _armed()
    will = sum(m.value for m in pc.save_modifiers("will"))
    _with_wielded(monkeypatch, [{"type": "save_mod", "target": "will", "amount": -2,
                                 "trigger": "wielded", "origin": "item:blade"}])
    assert sum(m.value for m in pc.save_modifiers("will")) == will - 2
    pc.equipped = "unarmed"
    assert sum(m.value for m in pc.save_modifiers("will")) == will


def test_a_daily_save_on_a_wielded_blade_is_rolled_by_the_day_clock(monkeypatch):
    """Lane F: worn and wielded `save_gate` documents with `periodic: "day"` are rolled in
    `run_periodic("day")` — the carried mechanism's day effect, granted with the item."""
    from tests.test_enchant_engine import _armed

    s, e, pc = _armed()
    _with_wielded(monkeypatch, [{"type": "save_gate", "target": "will", "dc": 99,
                                 "periodic": "day", "trigger": "wielded",
                                 "on_failure": [{"type": "apply_condition",
                                                 "target": "shaken"}]}])
    granted = pc.sync_carried(e.dice)
    assert granted and granted[0]["kind"] == "worn"
    pc.run_periodic("day", 1, e.dice)
    assert pc.has_condition("shaken")
    pc.equipped = "unarmed"
    assert any("no longer worn" in r.get("what", "") for r in pc.sync_carried(e.dice))
