"""The enchanter's layer in a fight (docs/enchanting-contracts.md §4, lane C).

Lane A wrote a property vocabulary nothing ran (`effectspec.AWAITING_READER`: ten types,
engine False) and lane B put the layer on the item's own record. Each test here names what
the layer did in a fight before its reader existed — usually nothing, once worse.
"""
from __future__ import annotations


from rules import effectspec, forge_items, magic_layer
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from tests._board import face_to_face


def _record(item_id: str, base: str = "longsword", *, gear: str = "weapon",
            enhancement: int = 1, props=(), quality_index: int = 3) -> dict:
    rec = forge_items.record_for_base(base, gear=gear, quality_index=quality_index,
                                      item_id=item_id, name=item_id.replace("-", " ").title())
    adds = {"enhancement": enhancement,
            "properties": [p if isinstance(p, dict) else {"id": p} for p in props]}
    return magic_layer.write(rec, adds, binding={"quality_index": quality_index,
                                                 "level": 20, "perks": {}})


def _table(seed: int = 4):
    """Kesst with a steady hand: +20 to hit, so a face of 10 always lands and never
    threatens, and nobody is caught flat-footed (no sneak dice in the way)."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.pc().add_buff("combat_mod", "attack", 20, source="the test's steady hand",
                    rounds=10_000)
    e = Engine(s, Dice(seed=seed))
    e._flat_footed = lambda defender: False
    return s, e


def _run(e, raw):
    return e.run(e.validate(raw, origin="author:test"))


def _wear(e, item):
    out = _run(e, [{"op": "wear", "actor": "pc", "because": "test",
                    "params": {"item": item}}]).outcomes[0]
    assert "draws" in out.tell or "puts on" in out.tell or "straps" in out.tell, out.tell
    return out


def _armed(*props, base="longsword", enhancement=1, seed=4, item_id="blade"):
    s, e = _table(seed)
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_record(item_id, base, enhancement=enhancement,
                                                props=props)))
    _wear(e, item_id)
    return s, e, pc


def _foe(s, template="thug", name="the thug", hp=300):
    who = s.add(instantiate(template, scene=s, name=name))
    who.hp = who.hp_max = hp
    return who


def _fight(s, e, *foes):
    _run(e, [{"op": "begin_encounter",
              "params": {"sides": {"you": ["pc"], "them": [f.ref for f in foes]}}}])


def _swing(s, e, target, faces, params=None):
    """One player-rolled swing, every popup answered by `faces(label)`. Returns the
    attack's outcome and the labels asked, in order."""
    face_to_face(s, b=target.ref)
    s.turn = [r for r, _ in s.initiative].index("pc")
    r = _run(e, [{"op": "attack", "actor": "pc", "target": target.ref,
                  "visibility": "player", "params": dict(params or {}),
                  "because": "test"}])
    asked = []
    for _ in range(20):
        if r.awaiting is None:
            break
        asked.append(r.awaiting["label"])
        face = faces(r.awaiting["label"])
        r = e.resume(int(r.awaiting["min"]) if face is None else face)
    out = next(o for o in r.outcomes if o.op == "attack")
    return out, asked


def _saves_roll(monkeypatch, e, face: int) -> None:
    """Every engine-rolled saving throw shows `face` on the die; nothing else changes."""
    real = e.dice.d20

    def d20(modifiers=None, label="", visibility="hidden"):
        if " save" in label:
            return e.dice.given_total(face, "1d20", modifiers, label=label)
        return real(modifiers, label, visibility)

    monkeypatch.setattr(e.dice, "d20", d20)


def _hits(label: str):
    """Hit, never threaten; every damage die at its lowest."""
    return 10 if label.startswith("Attack") else None


def _crits(label: str):
    return 20 if label.startswith(("Attack", "Confirm")) else None


def _total(mods) -> int:
    return sum(m.value for m in mods)


# --- bane: the note-only defect -------------------------------------------------------

def test_a_bane_blade_adds_its_dice_against_its_foe_and_nothing_against_anybody_else():
    """Plan §21.1 (C): "a bane (undead) sword adds +2d6 against a skeleton and nothing
    against a bandit". The old catalogue's bane was a +2 `combat_mod` with a note
    "against the designated foe" that nothing read, so it hit everybody. Lane B measured
    the next version of the same defect: a merged bane rider ran through
    `consumables._spec_to_intents`, which never asks `when`, and its tell read
    "The property:bane in ...". Each property's die is the player's own popup, named."""
    s, e, pc = _armed("flaming", {"id": "bane", "choice": {"foe": "undead"}})
    skel = _foe(s, "skeleton", "the skeleton")
    thug = _foe(s)
    _fight(s, e, skel, thug)
    out, asked = _swing(s, e, skel, _hits)
    assert "Flaming (1d6 fire)" in asked and "Bane (2d6)" in asked, asked
    dmg = next(r for r in out.rolls if r.label.startswith("Damage"))
    assert any(m.source == "bane (2d6)" for m in dmg.modifiers), dmg.modifiers
    assert "The flaming adds" in out.tell and "The bane adds 2 to the blow." in out.tell
    assert "property:" not in out.tell
    fire = [x for x in out.effects if x.get("kind") == "damage" and x["type"] == "fire"]
    assert fire and fire[0]["origin"] == "item:blade" and fire[0]["property"] == "flaming"

    out, asked = _swing(s, e, thug, _hits)
    assert "Flaming (1d6 fire)" in asked and "Bane (2d6)" not in asked, asked
    assert "bane" not in out.tell.lower()


def test_bane_raises_the_enhancement_rather_than_standing_beside_it():
    """Lane A measured it: as a second enhancement term +2 collides with the sword's own
    +1 in `dice.stack` and the +1 bane sword hits at +2 against its foe, not the book's
    +3 ("its enhancement bonus is +2 better"). One enhancement term, +3, named for bane,
    against the undead; the sword's own +1 against anybody else."""
    s, e, pc = _armed({"id": "bane", "choice": {"foe": "undead"}})
    skel, thug = _foe(s, "skeleton", "the skeleton"), _foe(s)
    vs_skel = [m for m in pc.attack_modifiers(defender=skel) if m.type == "enhancement"]
    vs_thug = [m for m in pc.attack_modifiers(defender=thug) if m.type == "enhancement"]
    assert [(m.value, "bane +2" in m.source) for m in vs_skel] == [(3, True)]
    assert [m.value for m in vs_thug] == [1]
    assert _total(pc.damage_modifiers(defender=skel)) == \
        _total(pc.damage_modifiers(defender=thug)) + 2
    # No defender (the sheet's own line): no foe, the sword's own +1.
    assert [m.value for m in pc.attack_modifiers() if m.type == "enhancement"] == [1]


# --- the threat range and the full attack -------------------------------------------------

def test_a_keen_scimitar_threatens_on_15_to_20_and_keen_does_not_stack_with_itself():
    """Plan §21.1 (C): "a keen scimitar threatens on 15-20". Keen was a narrative line on
    the old catalogue card. The doubling is of the range's size (18-20 is three faces,
    doubled six: 15-20), and two threat-range doublings in one stacking group apply once
    (CRB keen: "doesn't stack with any other effect that expands the threat range")."""
    s, e, pc = _armed("keen", base="scimitar")
    w = pc.weapon()
    assert (w["crit_range_printed"], w["crit_range"]) == (18, 15)
    from rules.sheet import _with_layer

    twice = {"specs": [{"type": "crit_range", "multiply": 2, "stacking": "threat-range"},
                       {"type": "crit_range", "multiply": 2, "stacking": "threat-range"}]}
    assert _with_layer({"crit_range": 19}, twice)["crit_range"] == 17


def test_a_burst_adds_d10s_per_multiplier_step_on_a_confirmed_critical_only():
    """CRB flaming burst: "+1d10 points of fire damage on a successful critical hit. If the
    weapon's critical multiplier is x3, add an extra 2d10 ... instead". The old catalogue
    had the 1d10 as prose. A battleaxe (x3) asks for 2d10, and an ordinary hit asks for
    none."""
    s, e, pc = _armed("flaming-burst", base="battleaxe")
    thug = _foe(s)
    _fight(s, e, thug)
    out, asked = _swing(s, e, thug, _crits)
    assert "Flaming burst (2d10 fire)" in asked and "Flaming burst (1d6 fire)" in asked
    out, asked = _swing(s, e, thug, _hits)
    assert not any("2d10" in a for a in asked), asked


def test_speed_adds_one_swing_at_full_base_attack_bonus_on_a_full_attack():
    """CRB speed: "one extra attack with it. The attack uses the wielder's full base
    attack bonus". Narrative until 2026-10-05: a speed sword swung exactly as often as a
    plain one."""
    s, e, pc = _armed("keen")
    plain = pc.attack_sequence(full_attack=True)
    s, e, pc = _armed("speed")
    assert pc.attack_sequence(full_attack=True) == plain + [0]
    assert pc.attack_sequence(full_attack=False) == [0]     # a standard attack: one
    thug = _foe(s)
    _fight(s, e, thug)
    out, asked = _swing(s, e, thug, _hits, {"full_attack": True})
    assert sum(1 for a in asked if a.startswith("Attack")) == len(plain) + 1


# --- defending, fortification, brilliant energy -----------------------------------------

def test_defending_moves_enhancement_to_armour_class_and_never_more_than_it_has():
    """CRB defending: the wielder moves "some or all of the weapon's enhancement bonus to
    his AC as a bonus that stacks with all others". Narrative before: the card said it
    and nothing moved. The amount is the combat bar's `defending`, bounded here by the
    weapon's own +2 — a number the player chooses, never a model's."""
    s, e, pc = _armed("defending", enhancement=2)
    thug = _foe(s)
    _fight(s, e, thug)
    ac = pc.ac()
    atk = _total(pc.attack_modifiers(defender=thug))
    out, _ = _swing(s, e, thug, _hits, {"defending": 2})
    assert "turns 2 of the" in out.tell
    assert pc.ac() == ac + 2
    assert _total(pc.attack_modifiers(defender=thug)) == atk - 2
    s.turn = [r for r, _ in s.initiative].index("pc")
    r = _run(e, [{"op": "attack", "actor": "pc", "target": thug.ref,
                  "visibility": "hidden", "params": {"defending": 3}, "because": "t"}])
    assert "between 0 and 2" in r.outcomes[-1].tell
    # A weapon that is not defending cannot do it at all.
    s2, e2, pc2 = _armed("keen")
    thug2 = _foe(s2)
    _fight(s2, e2, thug2)
    s2.turn = [r for r, _ in s2.initiative].index("pc")
    r = _run(e2, [{"op": "attack", "actor": "pc", "target": thug2.ref,
                   "visibility": "hidden", "params": {"defending": 1}, "because": "t"}])
    assert "not a defending weapon" in r.outcomes[-1].tell


def test_fortification_turns_a_confirmed_critical_into_an_ordinary_blow_and_says_so():
    """CRB fortification: "a chance that the critical hit or sneak attack is negated and
    damage is instead rolled normally". The old card's line had no reader: heavy
    fortification turned nothing. A 100% homebrew ring makes the d% certain."""
    s, e, pc = _armed("keen")
    thug = _foe(s)
    thug.wear({"id": "ward", "name": "Warding Band", "slot": "ring",
               "specs": [{"type": "fortification", "percent": 100}]}, 0)
    _fight(s, e, thug)
    out, asked = _swing(s, e, thug, _crits)
    assert "turns the critical hit" in out.tell, out.tell
    assert "critically hits" not in out.tell
    assert not any(a.endswith("CRITICAL") for a in asked), asked


def test_brilliant_energy_passes_armour_and_cannot_harm_the_undead():
    """CRB brilliant energy: armour and shield bonuses "do not count against it", and it
    "cannot harm undead, constructs, and objects". The old card read "ignores armour" and
    nothing changed a target's AC; the contract's first `except` field would have let it
    cut a skeleton."""
    s, e, pc = _armed("brilliant-energy", enhancement=1)
    thug = _foe(s)
    thug.flat_ac = None
    thug.armour = "chainmail"
    skel = _foe(s, "skeleton", "the skeleton")
    _fight(s, e, thug, skel)
    worn = thug.ac()
    out, _ = _swing(s, e, thug, _hits)
    assert out.dc["value"] == worn - 6, (out.dc, worn)      # chainmail's +6 passed through
    assert thug.ac() == worn                                  # the suit is still on
    assert "armour and shield passed through" in out.dc["explain"]
    hp = skel.hp
    out, _ = _swing(s, e, skel, _hits)
    assert skel.hp == hp and "cannot hurt the undead" in out.tell


# --- lethality, riders ------------------------------------------------------------------

def test_merciful_deals_nonlethal_and_a_blow_struck_to_kill_quiets_it():
    """CRB merciful: "all damage it deals is nonlethal damage. On command, the weapon
    suppresses this ability". Read where a sap's is read (`weapons.lethality_of`); the
    command is a declared lethal blow, with no -4 (the weapon is told, not fought), and
    its 1d6 goes quiet with it."""
    from rules import weapons

    s, e, pc = _armed("merciful")
    assert weapons.lethality_of(pc.weapon()) == "nonlethal"
    thug = _foe(s)
    _fight(s, e, thug)
    out, asked = _swing(s, e, thug, _hits)
    assert "Merciful (1d6)" in asked
    assert all(x.get("lethality") == "nonlethal" for x in out.effects
               if x.get("kind") == "damage")
    assert not pc.lethality_swap(lethality="lethal")
    out, asked = _swing(s, e, thug, _hits, {"lethality": "lethal"})
    assert "Merciful (1d6)" not in asked


def test_vicious_bites_back_at_the_wielder():
    """CRB vicious: "an extra 2d6 points of damage against the foe ... and 1d6 points of
    damage to the wielder". `recipient: "self"` — before, the self die had no reader and
    the wielder never bled for it."""
    s, e, pc = _armed("vicious")
    thug = _foe(s)
    _fight(s, e, thug)
    hp = pc.hp
    out, asked = _swing(s, e, thug, _hits)
    assert "Vicious (2d6)" in asked
    assert "bites back at Kesst Vayr" in out.tell
    assert pc.hp < hp


def test_wounding_bleeds_through_the_periodic_executor_and_stacks():
    """CRB wounding: "1 point of bleed damage ... multiple hits increase the bleed". An
    `ActiveEffect` with the bleed condition's tags and a per-round `damage` the one
    periodic executor runs — not a ward, not a counter beside the store."""
    s, e, pc = _armed("wounding")
    thug = _foe(s)
    _fight(s, e, thug)
    out, _ = _swing(s, e, thug, _hits)
    assert "opens a wound on the thug: 1 damage a round" in out.tell
    _swing(s, e, thug, _hits)
    bleeds = [x for x in thug.effects if x.key == "bleed"]
    assert len(bleeds) == 2 and thug.has_state("state.wound.bleeding")
    hp = thug.hp
    said = thug.run_periodic("round", 1, e.dice)
    assert thug.hp == hp - 2 and len(said) == 2


def test_a_thundering_critical_deafens_on_a_failed_save(monkeypatch):
    """CRB thundering: "+1d8 points of sonic damage on a successful critical hit ... and
    the subject must succeed on a DC 14 Fortitude save or be deafened permanently". Both
    halves were prose on the old card."""
    s, e, pc = _armed("thundering")
    _saves_roll(monkeypatch, e, 2)
    thug = _foe(s)
    _fight(s, e, thug)
    out, asked = _swing(s, e, thug, _crits)
    assert "Thundering (1d8 sonic)" in asked
    assert "fails the Fortitude save against the thundering" in out.tell
    assert thug.has_condition("deafened")


def test_disruption_destroys_undead_on_a_failed_will_save_and_ignores_the_living(
        monkeypatch):
    """CRB disruption: "If the weapon strikes an undead creature, that creature must
    succeed on a DC 14 Will save or be destroyed" — through `Actor.die`, the one door."""
    s, e, pc = _armed("disruption", base="heavy-mace")
    _saves_roll(monkeypatch, e, 2)
    skel, thug = _foe(s, "skeleton", "the skeleton"), _foe(s)
    _fight(s, e, skel, thug)
    out, _ = _swing(s, e, thug, _hits)
    assert "disruption" not in out.tell
    out, _ = _swing(s, e, skel, _hits)
    assert "The disruption destroys the skeleton." in out.tell
    assert skel.is_dead


def test_vorpal_takes_a_head_on_a_natural_twenty_and_spares_the_headless():
    """CRB vorpal: "upon a roll of natural 20 (followed by a successful roll to confirm a
    critical hit), the weapon severs the opponent's head"; golems and undead other than
    vampires are unaffected, and so is anything immune to critical hits
    (`coup_de_grace.crit_immunity`, the reader the ledger said to reuse)."""
    s, e, pc = _armed("vorpal", enhancement=1)
    thug, skel = _foe(s), _foe(s, "skeleton", "the skeleton")
    _fight(s, e, thug, skel)
    out, _ = _swing(s, e, skel, _crits)
    assert "finds nothing to sever" in out.tell and not skel.is_dead
    out, _ = _swing(s, e, thug, _crits)
    assert "The vorpal takes the head of the thug." in out.tell and thug.is_dead


# --- the arrow shields, seeking, ghost touch armour, range ---------------------------------

def test_arrow_deflection_turns_one_shot_a_round(monkeypatch):
    """CRB arrow deflection: once a round, a DC 20 Reflex save (plus the attacking
    weapon's enhancement) deflects a ranged hit. Narrative before: a shield that turned
    arrows turned none."""
    s, e = _table()
    _saves_roll(monkeypatch, e, 20)
    pc = s.pc()
    pc.goods["arrows"] = 20
    thug = _foe(s)
    thug.wear({"id": "deflector", "name": "Deflecting Shield", "slot": "shield",
               "specs": [{"type": "deflect_ranged", "per": "round", "save": "ref",
                          "dc": 20, "dc_adds_enhancement": True}]}, 0)
    pc.weapons.append("shortbow")
    pc.equipped = "shortbow"
    _fight(s, e, thug)
    out, _ = _swing(s, e, thug, _hits, {"weapon": "shortbow"})
    assert "turns the shot aside" in out.tell, out.tell
    out, _ = _swing(s, e, thug, _hits, {"weapon": "shortbow"})
    assert "turns the shot aside" not in out.tell            # once a round


def test_arrow_catching_adds_deflection_against_ranged_only():
    """CRB arrow catching: "+1 deflection bonus to AC against ranged weapons"."""
    s, e = _table()
    thug = _foe(s)
    thug.flat_ac = None
    melee, ranged = thug.ac("melee"), thug.ac("ranged")
    thug.wear({"id": "catcher", "name": "Catching Shield", "slot": "shield",
               "specs": [{"type": "deflect_ranged", "draws_ft": 5, "deflection": 1}]}, 0)
    assert (thug.ac("melee"), thug.ac("ranged")) == (melee, ranged + 1)


def test_seeking_ignores_concealment_and_says_so():
    """CRB seeking: "veers toward its target, negating any miss chances". Its whole effect
    is a rule asked of the `property.seeking` tag, which nothing asked."""
    s, e = _table()
    pc = s.pc()
    pc.goods["arrows"] = 20
    pc.add_stock(forge_items.stock_item(_record("seeker", "longbow",
                                                props=("seeking",))))
    _wear(e, "seeker")
    thug = _foe(s)
    thug.add_buff("concealment", "miss_chance", 100, source="fog", rounds=10)
    _fight(s, e, thug)
    out, _ = _swing(s, e, thug, _hits, {"weapon": "seeker"})
    assert "gives no miss chance against it" in out.tell, out.tell
    assert "finds nothing there" not in out.tell


def test_throwing_and_distance_give_the_row_its_range():
    """CRB throwing: a 10-foot range increment for a melee weapon; distance doubles a
    ranged weapon's. Both were gear numbers nothing read onto the weapon row."""
    s, e, pc = _armed("throwing", base="longsword")
    assert pc.weapon()["range_ft"] == 10
    s, e = _table()
    pc = s.pc()
    plain = pc.weapon("longbow")["range_ft"]
    pc.add_stock(forge_items.stock_item(_record("far", "longbow", props=("distance",))))
    _wear(e, "far")
    assert pc.weapon()["range_ft"] == plain * 2


def test_the_alignment_clause_holds_against_any_foe_for_now():
    """Owner, round 6: no alignment is tracked, so holy's 2d6 "lands on any foe, like
    smite" until alignment exists. Before lane C the clause was unreadable and dropped:
    a holy sword's 2d6 hit nobody, evil or not."""
    s, e, pc = _armed("holy", enhancement=1)
    thug = _foe(s)
    _fight(s, e, thug)
    out, asked = _swing(s, e, thug, _hits)
    assert "Holy (2d6)" in asked


def test_nothing_waits_on_a_reader_any_more():
    """Lane A's ledger of types the vocabulary could say and nothing ran. Every line had
    a reader to delete it; the ten are executable now."""
    assert effectspec.AWAITING_READER == {}
    for t in ("crit_range", "extra_attack", "enhancement_raise", "enhancement_to_ac",
              "fortification", "ignore_armour", "deflect_ranged", "weapon_lethality",
              "slay", "item_power", "spell_resistance"):
        assert effectspec.executable({"type": t}), t
