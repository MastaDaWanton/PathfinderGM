"""Class choices that DO things: domains, bloodlines, arcane schools and bonds (lane 2).

Measured by the class audit (docs/class-audit.md, 2026-10-05) and at the start of this lane:

- "7 of 153 domains are documented … The Sun domain gave nothing." A Sun cleric had no
  power at all, at any level.
- Lane 1 built the pickers; the choice was then stored and read by nothing: a 1st-level
  draconic sorcerer had no claws, no bonus spell at 3rd and no resistance at 3rd; a
  1st-level evoker had no force missile and no specialist slot; "every wizard is an
  unnamed universalist".
- The cleric's domain slot was a number on the Spells tab: nothing could be prepared into
  it and nothing could be cast from it.
- "117 of the 153 [domains] have no spell at one or more of levels 1–9 … 'Ash' has spells
  at 7 and 9 only."
- D7: "Animal-domain druid at 6: none, before and after a reload. Animal-domain cleric at
  5: none."
- D9: "Paladin with Cha 18: no slots at L4 (book: 1 bonus 1st); no 2nd at L7 (book: 1);
  no 3rd at L10. At L13 there are 2 4th-level slots (book: 1)."
- D10: "Spontaneous casters cannot swap a known spell … No code path: `learn` only adds."
"""
from __future__ import annotations

import json

import pytest

from rules import casting, class_abilities, classes, creation, domains, grantedpowers
from rules import leveling, spells as spells_mod
from rules import xp as xp_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict

ABILITIES = {"str": 10, "dex": 14, "con": 12, "int": 12, "wis": 12, "cha": 12}


def scores(ability):
    """Twenty points: the casting score at 15 (17 with the human's +2), Dex 14."""
    return {**ABILITIES, ability: 15}


def forge(cls, ability="cha", **over):
    body = {"name": "Lane Two", "race": "human", "class": cls, "gender": "woman",
            "abilities": scores(ability), "choices": [ability], "skills": ["perception"],
            "feats": [], "domains": creation.starter_domains(cls),
            "spellbook": creation.starter_spells(cls, 1)}
    body.update(over)
    built, problems = creation.build(body)
    assert problems == [], problems
    return from_dict(built["sheet"], ref="pc")


def levelled(actor, to):
    while actor.level < to:
        actor.xp = xp_mod.total_for(actor.level + 1)
        assert leveling.level_up(actor)["ok"]
    return actor


def bare(cls, level, **extra):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": cls, "level": level, "ranks": {}, "armour": "none"})
    d.pop("paths", None)
    d.update(extra)
    return from_dict(d, ref="pc")


def table(caster):
    s = Scene(location_id="5bbd0c40345f")
    s.add(caster)
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.initiative = [("pc", 20), ("c1", 10)]
    s.sides = {"pc": ["pc"], "them": ["c1"]}
    s.round, s.turn = 1, 0
    return s, Engine(s, Dice(seed=5))


def cast(engine, spell, at="c1"):
    res = engine.run(engine.validate([{"op": "cast", "actor": "pc", "because": "test",
                                       "params": {"spell": spell, "at": at}}]))
    while res.awaiting:
        res = engine.resume(int(res.awaiting["max"]))
    return res.outcomes[0]


CORE = ["Air", "Animal", "Artifice", "Chaos", "Charm", "Community", "Darkness", "Death",
        "Destruction", "Earth", "Evil", "Fire", "Glory", "Good", "Healing", "Knowledge",
        "Law", "Liberation", "Luck", "Madness", "Magic", "Nobility", "Plant", "Protection",
        "Repose", "Rune", "Strength", "Sun", "Travel", "Trickery", "War", "Water",
        "Weather"]


# --- the documents -----------------------------------------------------------------------

def test_every_core_domain_has_its_powers_written_and_every_document_validates():
    """7 of the 33 core domains had powers (the druid's seven); the other 26 granted their
    spells and slot only — a Sun cleric got nothing. Every one has a 1st-level power now,
    and a 6th- or 8th-level one, and every file validates."""
    assert set(CORE) <= set(domains.documented())
    for name in CORE:
        levels = sorted(p["level"] for p in domains.powers_of(name))
        assert levels[0] == 1 and any(lvl in (4, 6, 8) for lvl in levels), (name, levels)
    assert domains.validate_powers() == []
    assert grantedpowers.validate() == []
    assert class_abilities.validate_documents() == []


def test_every_bloodline_and_school_in_the_catalogues_has_its_powers():
    for path, doc in grantedpowers.files().items():
        choice = doc["choice"]
        offered = {e["id"] for cls in classes.all_classes().values()
                   for ch in cls.get("choices") or () if ch["id"] == choice
                   for o in ch["options"]
                   for e in classes.catalogue(o.get("from", "")).get("options") or ()}
        assert offered and offered <= set(doc["entries"]), (path, offered - set(doc["entries"]))


def test_a_power_document_naming_a_field_nobody_reads_is_refused_with_the_fix():
    bad = {"key": "zap", "level": 1, "attack": "ranged touch",
           "modifiers": [{"type": "speed_mod", "target": "land", "amount": 10}],
           "cost": {"pool": "other"}}
    found = " ".join(grantedpowers.validate_power(bad, "x"))
    assert "unknown field(s) attack" in found and "content/class-abilities" in found
    assert "speed_mod" not in grantedpowers.MOD_TYPES and ".type: one of" in found
    assert "spends its own pool" in found


# --- domains -------------------------------------------------------------------------------

def test_a_sun_and_protection_cleric_holds_powers_where_she_held_none():
    """The audit's Fire+Sun cleric: Sun gave nothing. Protection's resistance bonus now
    reaches every save through the funnel, +1 and +1 more at 5th."""
    pc = forge("cleric", ability="wis", domains=["Sun", "Protection"])
    names = [line["name"] for line in grantedpowers.power_lines(pc)]
    assert "Sun's Blessing" in names and "Divine Protection" in names
    will = {m.source: m.value for m in pc.save_modifiers("will")}
    assert will["Divine Protection"] == 1
    levelled(pc, 5)
    assert {m.source: m.value for m in pc.save_modifiers("fort")}["Divine Protection"] == 2
    assert pc.pools["resistant touch"].maximum == 3 + pc.ability_mod("wis")


def test_domains_change_speed_class_skills_and_feats():
    """Travel's +10 ft goes on the base speed, before armour (CRB); Knowledge makes every
    Knowledge skill a class skill (+3 with a rank); Darkness hands over Blind-Fight and Rune
    Scribe Scroll at the forge."""
    travel = forge("cleric", ability="wis", domains=["Travel", "Knowledge"],
                   skills=["knowledge (history)"])
    assert travel.speed_feet == 40
    assert "knowledge (history)" in travel.class_skills
    hist = {m.source: m.value for m in travel.skill_modifiers("knowledge (history)")}
    assert hist.get("class skill") == 3
    dark = forge("cleric", ability="wis", domains=["Darkness", "Rune"])
    assert {"blind-fight", "scribe scroll"} <= {f.lower().replace(" ", "-")
                                                if f.lower() == "blind-fight" else f.lower()
                                                for f in dark.feats}


def test_a_domain_attack_is_used_through_the_one_executor():
    """Charm's Dazing Touch, a melee touch that dazes for a round: a class-ability document
    with `power`, used by `Engine._use_class_ability` — no second mechanism."""
    pc = bare("cleric", 1, domains=["Charm", "War"])
    from rules import classes as classes_mod

    classes_mod.apply(pc)
    doc, _ = class_abilities.find(pc, "dazing touch")
    assert doc and doc["class"] == "domain" and doc["effect"]["condition"] == "dazed"
    assert "Battle Rage" in class_abilities.names(pc)
    s, e = table(pc)
    from tests._board import face_to_face

    face_to_face(s, "pc", "c1")
    before = pc.pools["dazing touch"].current
    out = e.run(e.validate([{"op": "use_ability", "actor": "pc", "because": "test",
                             "params": {"ability": "dazing touch", "to": "c1"}}]))
    while out.awaiting:
        out = e.resume(int(out.awaiting["max"]))
    assert pc.pools["dazing touch"].current == before - 1
    assert out.outcomes[-1].tell


def test_a_subdomain_takes_its_parents_spells_where_it_has_none_and_not_its_parent():
    """Ash had spells at 7 and 9 only, so an Ash cleric's domain slot stood empty at seven
    of nine levels. Ash is Fire's subdomain (APG; AoN's Cleric Domains): Fire fills the
    rest, and a cleric "cannot select its associated domain as her other domain"."""
    assert domains.parents_of("Ash") == ["Fire"]
    assert all(domains.spells_of("Ash", lvl) for lvl in range(1, 10))
    assert domains.spells_of("Ash", 1) == domains.spells_of("Fire", 1)
    assert domains.spells_of("Ash", 7) != domains.spells_of("Fire", 7)
    said = " ".join(domains.problems(["Ash", "Fire"], "cleric"))
    assert "subdomain of Fire" in said
    assert "only" in " ".join(domains.problems(["Ruins", "Sun"], "cleric"))
    ash = forge("cleric", ability="wis", domains=["Ash", "Sun"])
    assert any("subdomain of Fire" in " ".join(line["not_yet"])
               for line in grantedpowers.power_lines(ash))


def test_the_animal_domain_brings_a_companion_at_fourth_three_levels_behind():
    """D7: an Animal-domain cleric at 5 had no companion, before and after a reload. The
    class document now asks for one at 4th, only of an Animal holder, at level - 3."""
    pc = forge("cleric", ability="wis", domains=["Animal", "Sun"])
    levelled(pc, 3)
    assert not [r for r in leveling.owed(pc)["choices"]["picks"]
                if r["choice"] == "domain companion"]
    levelled(pc, 4)
    rows = [r for r in leveling.owed(pc)["choices"]["picks"]
            if r["choice"] == "domain companion"]
    assert len(rows) == 1
    taken, problems = classes.take_choice(pc, "domain companion", {"pick": "wolf"})
    assert problems == [], problems
    from rules import animal_companion

    want = animal_companion.wanted(pc)
    assert want == {"animal": "wolf", "offset": -3, "tricks": [], "name": ""}
    assert animal_companion.effective_level(pc, want["offset"]) == 1
    other = levelled(forge("cleric", ability="wis", domains=["Sun", "War"]), 4)
    assert not [r for r in leveling.owed(other)["choices"]["picks"]
                if r["choice"] == "domain companion"]


# --- the domain slot -----------------------------------------------------------------------

def test_a_fire_cleric_prepares_fireball_in_her_domain_slot_and_casts_from_it():
    """The domain slot was a number with no way in and no way out. Fireball is a Fire
    domain spell and not a cleric spell: it goes in the domain slot, nowhere else, and a
    cast from it spends the domain slot, not an ordinary one."""
    pc = bare("cleric", 5, domains=["Fire", "Sun"],
              abilities={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 18, "cha": 10})
    from rules import classes as classes_mod

    classes_mod.apply(pc)
    fireball = spells_mod.get("fireball")
    assert not casting.on_class_list(pc, fireball)
    assert casting.spell_level_for(pc, fireball) == 3
    assert casting.special_refusal(pc, "domain", fireball) == ""
    assert "not one of" in casting.special_refusal(pc, "domain", spells_mod.get("bless"))
    casting.prepare(pc, casting.special_key("domain", "fireball"), 1)
    assert "already holds" in casting.special_refusal(pc, "domain",
                                                       spells_mod.get("searing-light"))
    _, e = table(pc)
    ordinary = pc.pool("spell slot 3").current
    out = cast(e, "fireball")
    assert out.effects[0]["slot"] == "domain slot 3"
    assert pc.pool("domain slot 3").current == 0
    assert pc.pool("spell slot 3").current == ordinary
    assert "domain:fireball" not in pc.prepared


def test_the_prepare_endpoint_fills_the_domain_slot_and_refuses_it_elsewhere(client, isolated):
    _create(client, "cleric", domains=["Fire", "Sun"])
    from play import campaign as campaign_mod

    pc = campaign_mod.current().scene.pc()
    levelled(pc, 5)
    campaign_mod.current().save()
    res = _post(client, "/api/spells/prepare", {"action": "prepare", "spell": "fireball"})
    assert res.status_code == 409 and "domain slot" in res.json()["error"]
    res = _post(client, "/api/spells/prepare",
                {"action": "prepare", "spell": "fireball", "slot": "domain"})
    assert res.status_code == 200, res.json()
    rows = res.json()["spells"]["special_slots"]
    third = next(r for r in rows if r["kind"] == "domain" and r["level"] == 3)
    assert third["held"] == [{"id": "fireball", "name": "Fireball"}]


# --- bloodlines ----------------------------------------------------------------------------

def test_a_red_dragon_sorcerer_has_claws_at_first_and_fire_resistance_at_third():
    """Measured before: a 1st-level draconic sorcerer had no claws and nothing at 3rd."""
    pc = forge("sorcerer", class_choices={"bloodline": {"pick": "draconic",
                                                          "variant": "red"}})
    assert class_abilities.names(pc) == ["Claws"]
    claws, _ = class_abilities.find(pc, "claws")
    assert claws["self"]["natural_weapons"][0]["damage"]["medium"] == "1d4"
    assert pc.pools["claws"].maximum == 3 + pc.ability_mod("cha")
    assert pc.resistance("fire") == 0
    levelled(pc, 3)
    assert pc.resistance("fire") == 5
    assert {m.source: (m.value, m.type) for m in pc.ac_modifiers()}[
        "Dragon Resistances"] == (1, "natural armour")
    levelled(pc, 9)
    assert pc.resistance("fire") == 10 and pc.pools["breath weapon"].maximum == 1
    claws, _ = class_abilities.find(pc, "claws")
    assert claws["self"]["natural_weapons"][0]["damage"]["medium"] == "1d6"


def test_the_dragon_decides_the_energy_and_the_element_the_movement():
    blue = forge("sorcerer", class_choices={"bloodline": {"pick": "draconic",
                                                            "variant": "blue"}})
    levelled(blue, 3)
    assert blue.resistance("electricity") == 5 and blue.resistance("fire") == 0
    fire = forge("sorcerer", class_choices={"bloodline": {"pick": "elemental",
                                                            "variant": "fire"}})
    ray, _ = class_abilities.find(fire, "elemental ray")
    assert ray["roll"]["type"] == "fire" and "$" not in json.dumps(ray)
    base = fire.speed_feet
    levelled(fire, 15)
    assert fire.speed_feet == base + 30
    water = levelled(forge("sorcerer", class_choices={"bloodline": {
        "pick": "elemental", "variant": "water"}}), 15)
    assert water.resistance("cold") == 20
    assert any("swim" in line["line"] for line in grantedpowers.power_lines(water))


def test_bloodline_spells_are_known_at_odd_levels_on_top_of_the_table():
    """"These spells are in addition to the number of spells given on Table: Sorcerer
    Spells Known" (CRB). Derived, never written into the repertoire; and a bless from the
    celestial bloodline — a cleric spell — is a 1st-level sorcerer spell for her."""
    pc = forge("sorcerer", class_choices={"bloodline": {"pick": "celestial"}})
    levelled(pc, 2)
    assert casting.granted_known(pc) == {}
    owed_before = casting.learning(pc)["owed"]
    levelled(pc, 3)
    assert casting.granted_known(pc) == {"bless": 1}
    assert casting.knows(pc, spells_mod.get("bless"))
    assert "bless" not in pc.spellbook
    assert casting.learning(pc)["owed"] >= owed_before      # the table's own picks remain
    assert "known through a class choice" in " ".join(
        casting.learn_problems(pc, ["bless"]))
    levelled(pc, 19)
    assert len(casting.granted_known(pc)) == 9


def test_every_core_bloodline_spell_resolves_to_a_spell_in_the_corpus():
    """The catalogue prints "greater teleport" and "summon monster ix"; the corpus spells
    them `teleport-greater` and `summon-monster-9`. Measured: 6 of 90 did not resolve by
    name; every one does now, and agrees with the corpus's own bloodline field where it
    has one."""
    import re

    misses = []
    for e in classes.catalogue("sorcerer-bloodlines")["options"]:
        for at, name in e["bonus_spells"].items():
            sp = casting.spell_named(name)
            if sp is None:
                misses.append((e["id"], at, name))
            elif sp.bloodline and e["name"] in sp.bloodline:
                # "Aberrant (Sorcerer) (3), …, Aberrant (BloodRager) (7)": the sorcerer's.
                assert re.search(rf"{e['name']}(?: \(Sorcerer\))? \({at}\)",
                                 sp.bloodline), (e["id"], at, name, sp.bloodline)
    assert misses == []


def test_a_bloodline_class_skill_gets_its_plus_three():
    pc = forge("sorcerer", class_choices={"bloodline": {"pick": "abyssal"}},
               skills=["knowledge (planes)"])
    assert "knowledge (planes)" in pc.class_skills
    terms = {m.source: m.value for m in pc.skill_modifiers("knowledge (planes)")}
    assert terms.get("class skill") == 3


# --- arcane schools and bonds ----------------------------------------------------------------

def _wizard(school="evocation", opposed=("necromancy", "enchantment"), bond=None, level=1):
    choices = {"arcane school": {"pick": school}}
    if opposed:
        choices["opposition schools"] = {"picks": list(opposed)}
    choices["arcane bond"] = bond or {"pick": "bonded-object", "variant": "staff"}
    return levelled(forge("wizard", ability="int", class_choices=choices), level)


def test_an_evoker_has_a_school_slot_and_force_missile_and_a_universalist_neither():
    pc = _wizard()
    assert casting.school_slots_for(pc) == {1: 1}
    assert "Force Missile" in class_abilities.names(pc)
    assert pc.pools["school slot 1"].maximum == 1
    uni = levelled(forge("wizard", ability="int", class_choices={
        "arcane school": {"pick": "universalist"},
        "arcane bond": {"pick": "bonded-object", "variant": "ring"}}), 1)
    assert casting.school_slots_for(uni) == {}
    assert "Force Missile" not in class_abilities.names(uni)


def test_the_school_slot_takes_only_the_school_from_the_book():
    pc = _wizard(level=3)
    pc.spellbook = list(pc.spellbook) + ["magic-missile", "shield"]
    assert casting.special_refusal(pc, "school", spells_mod.get("magic-missile")) == ""
    said = casting.special_refusal(pc, "school", spells_mod.get("shield"))
    assert "not an evocation spell" in said


def test_an_opposition_spell_takes_two_slots_to_prepare_and_to_cast():
    """"A wizard who prepares spells from his opposition schools must use two spell slots
    of that level to prepare the spell" (CRB). Foundry multiplies a restricted spell's
    slot cost by 2; so does everything here that counts a slot."""
    pc = bare("wizard", 3, abilities={"str": 10, "dex": 10, "con": 10, "int": 12,
                                      "wis": 10, "cha": 10},
              spellbook=["ray-of-enfeeblement", "magic-missile"],
              prepared={},
              class_choices={"arcane school": {"option": "class option", "picks": [
                  {"pick": "evocation", "level": 1}]},
                  "opposition schools": {"option": "class option", "picks": [
                      {"pick": "necromancy", "level": 1}, {"pick": "enchantment",
                                                           "level": 1}]}})
    from rules import classes as classes_mod

    classes_mod.apply(pc)
    ray = spells_mod.get("ray-of-enfeeblement")
    assert casting.slot_cost(pc, ray) == 2
    assert casting.slots_for(pc)[1] == 3              # 2 base + 1 Int bonus
    assert casting.prepare_refusal(pc, 1, 1, spell=ray) == ""
    casting.prepare(pc, ray.id, 1)
    assert casting.open_slots(pc, 1) == 1
    assert "takes 2" in casting.prepare_refusal(pc, 1, 1, spell=ray)
    _, e = table(pc)
    cast(e, ray.id)
    assert pc.pool("spell slot 1").current == 1


def test_a_familiar_gives_its_gift_through_the_funnel():
    cat = _wizard(bond={"pick": "familiar", "variant": "cat"})
    assert {m.source: m.value for m in cat.skill_modifiers("stealth")}["Familiar"] == 3
    toad = _wizard(bond={"pick": "familiar", "variant": "toad"})
    assert any(m.source == "Familiar" and m.value == 3 for m in toad.hp_max_modifiers())
    staff = _wizard()
    assert staff.pools["bonded object"].maximum == 1


# --- D9: bonus-spells-only rows ----------------------------------------------------------------

# The book's paladin and ranger table (CRB Tables 3-12 and 3-13; d20pfsrd's paladin page,
# fetched by the audit 2026-10-05): None is "—", 0 is bonus spells only. Typed here apart
# from rules/casting.py on purpose — the code's copy is the one that was wrong.
BOOK_FOUR = {4: [0], 5: [1], 6: [1], 7: [1, 0], 8: [1, 1], 9: [2, 1], 10: [2, 1, 0],
             11: [2, 1, 1], 12: [2, 2, 1], 13: [3, 2, 1, 0], 14: [3, 2, 1, 1],
             15: [3, 2, 2, 1], 16: [3, 3, 2, 1], 17: [4, 3, 2, 1], 18: [4, 3, 2, 2],
             19: [4, 3, 3, 2], 20: [4, 4, 3, 3]}


@pytest.mark.parametrize("cls,ability", [("paladin", "cha"), ("ranger", "wis")])
def test_four_level_casters_get_their_bonus_only_rows(cls, ability):
    for score in (10, 12, 18, 20):
        for level in range(1, 21):
            pc = from_dict({"name": "t", "kind": "pc", "class": cls, "level": level,
                            "abilities": {**ABILITIES, ability: score},
                            "hp": 30, "hp_max": 30})
            mod = (score - 10) // 2
            want = {}
            for i, base in enumerate(BOOK_FOUR.get(level, []), start=1):
                n = base + casting.bonus_slots(mod, i)
                if n and score >= 10 + i:
                    want[i] = n
            assert casting.slots_for(pc) == want, (cls, score, level)


# --- D10: exchanging a known spell -------------------------------------------------------------

def test_a_sorcerer_exchanges_a_spell_at_fourth_once_and_not_before():
    pc = forge("sorcerer", class_choices={"bloodline": {"pick": "arcane"}})
    pc.spellbook = list(pc.spellbook) + ["magic-missile"]
    levelled(pc, 3)
    assert casting.swaps(pc)["open"] == []
    assert "next comes at level 4" in casting.swap_problems(pc, "magic-missile", "shield")[0]
    levelled(pc, 4)
    assert casting.swaps(pc)["open"] == [4]
    assert "keeps the level" in " ".join(
        casting.swap_problems(pc, "magic-missile", "invisibility"))
    ok, problems = casting.swap(pc, "magic-missile", "shield")
    assert ok and problems == []
    assert "shield" in pc.spellbook and "magic-missile" not in pc.spellbook
    assert casting.swaps(pc)["open"] == [] and pc.spell_swaps == [4]
    assert from_dict(to_dict(pc)).spell_swaps == [4]
    levelled(pc, 6)
    assert casting.swaps(pc)["open"] == [6]


def test_a_bard_exchanges_only_below_his_best_level():
    pc = levelled(forge("bard"), 5)
    assert casting.swaps(pc)["open"] == [5] and casting.swaps(pc)["highest"] == 2
    pc.spellbook = list(pc.spellbook) + ["invisibility"]
    said = " ".join(casting.swap_problems(pc, "invisibility", "glitterdust"))
    assert "at least 1 level below the highest" in said


def test_a_bloodline_spell_is_never_exchanged():
    pc = levelled(forge("sorcerer", class_choices={"bloodline": {"pick": "celestial"}}), 4)
    said = " ".join(casting.swap_problems(pc, "bless", "shield"))
    assert "never exchanged" in said


# --- over the wire -----------------------------------------------------------------------------

def _post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


@pytest.fixture
def isolated(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    return tmp_path


def _create(client, cls, **over):
    ability = {"cleric": "wis", "druid": "wis", "ranger": "wis", "wizard": "int"}.get(
        cls, "cha")
    body = {"name": f"Wire {cls}", "race": "human", "class": cls, "gender": "woman",
            "abilities": scores(ability), "choices": [ability],
            "skills": ["perception"], "feats": [], "domains": creation.starter_domains(cls),
            "spellbook": creation.starter_spells(cls, 1), "begin": True}
    body.update(over)
    res = _post(client, "/api/character/create", body)
    assert res.status_code == 200, res.json()


def test_the_swap_endpoint_exchanges_by_name(client, isolated):
    _create(client, "sorcerer", class_choices={"bloodline": {"pick": "arcane"}},
            spellbook=["magic-missile", "shield", "detect-magic", "light", "mage-hand",
                       "prestidigitation"])
    from play import campaign as campaign_mod

    c = campaign_mod.current()
    levelled(c.scene.pc(), 4)
    c.save()
    got = client.get("/api/spells/swap").json()
    assert got["swaps"]["open"] == [4] and got["new"]
    res = _post(client, "/api/spells/swap", {"old": "magic-missile", "new": "Sleep"})
    assert res.status_code == 200, res.json()
    assert "sleep" in campaign_mod.current().scene.pc().spellbook
    res = _post(client, "/api/spells/swap", {"old": "shield", "new": "grease"})
    assert res.status_code == 400 and "no exchange owed now" in res.json()["error"]
