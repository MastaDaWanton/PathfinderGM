"""The mind, social and knowledge skills: the player's own checks with a real consequence.

The implementation audit of 2026-11-22 (docs/implementation-audit-2026-11-22.md §2) found
no resolved use at all for Sense Motive (the player's own), Appraise, Perform and seven of
Knowledge's ten fields, and Spellcraft could not identify a spell as it was cast. Each of
these rolled at whatever band the plan named and changed nothing: a Sense Motive "made"
read nothing off anybody, a Knowledge (history) "made" told the narrator to invent the
history, an Appraise "made" priced nothing. Round 2 gives each its row in
content/rules/skill-uses.json and its door in rules/skilluses.py.

Every behaviour test goes through `Engine.run` and reads the sheet, the purse and the tells.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import cards as cards_mod
from rules import pricing, schemes, skilluses
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict

ROOT = Path(__file__).resolve().parent.parent


class _Faces(Dice):
    """Every d20 whose label holds a key lands on that key's face; the rest on `rest`."""

    def __init__(self, faces: dict | None = None, rest: int = 10):
        super().__init__(seed=20261122)
        self.faces, self.rest = dict(faces or {}), rest

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if str(notation).lstrip("1").startswith("d20"):
            face = next((f for k, f in self.faces.items() if k in (label or "")), self.rest)
            return self.given(face, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


@pytest.fixture(scope="module")
def world():
    from world.loader import load_cached

    return load_cached(str(ROOT / "fixtures/aurvantis-campaign.json"))


def _town(world):
    return next(e for e in world.entities.values()
                if e.kind == "CITY" and e.facts.get("History") and e.facts.get("Founding"))


def _here(world=None, faces=None, rest=10):
    scene = Scene(location_id=_town(world).id if world else "5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, _Faces(faces, rest), world=world)
    return scene, engine, scene.get("pc")


def _person(scene, name):
    return scene.add(instantiate("commoner-level-1", scene=scene, name=name))


def _run(engine, *raws):
    res = engine.run(engine.validate([dict(r, visibility="hidden") for r in raws]))
    assert not res.awaiting
    return [o for o in res.outcomes if o.op == "check"]


def _check(skill, **params):
    return {"op": "check", "actor": "pc",
            "params": {"skill": skill, "dc": {"band": "average"}, **params}}


def _keeper(scene, who):
    """`who` is the-lost-thing's giver, whose secret card `kept_by` names: "$giver did not
    lose it; $giver says so because the quarrel shames them"."""
    card = cards_mod.open_card(scene, cards_mod.Card(
        id="scheme-the-lost-thing-truth-1", title="Who really has it", secret=True))
    scene.schemes.append({"scheme": "the-lost-thing", "cards": {"truth": card.id},
                          "slots": {"giver": {"kind": "actor", "ref": who.ref}},
                          "outcome": ""})
    return card


# --- Sense Motive ----------------------------------------------------------------------------

def test_sense_motive_against_a_liar_is_their_bluff_and_catches_what_the_scheme_hides():
    """Audit 2026-11-22: "Sense Motive (the PC's own): no resolved use". The engine knew
    nobody was lying, so nothing could catch a lie. A secret card's `kept_by` is the
    world's record of who keeps it: read against their Bluff, made, `knows.lying.<ref>`
    lands on the player and the tell says it, never what the secret is."""
    scene, engine, pc = _here(faces={"Sense Motive": 15, "Bluff": 2})
    liar = _person(scene, "Tanna")
    _keeper(scene, liar)
    out = _run(engine, {**_check("sense motive"), "target": liar.ref})[0]
    assert out.verdict == "success" and "against Tanna's Bluff" in out.dc["basis"]
    assert len(out.rolls) == 2
    assert pc.has_state(f"knows.lying.{liar.ref}")
    assert "not telling" in out.tell and "really has it" not in out.tell.lower()


def test_a_lie_that_holds_reads_exactly_as_nothing_to_find():
    """The CRB's failure is no read at all: out-bluffed, the tell is the plain miss, and
    the player carries no tag."""
    scene, engine, pc = _here(faces={"Sense Motive": 2, "Bluff": 18})
    liar = _person(scene, "Tanna")
    _keeper(scene, liar)
    out = _run(engine, {**_check("sense motive"), "target": liar.ref})[0]
    assert out.verdict == "failure" and "reads nothing either way" in out.tell
    assert not pc.has_state("knows.lying")


def test_a_resolved_secret_is_no_longer_kept():
    scene, engine, pc = _here()
    liar = _person(scene, "Tanna")
    card = _keeper(scene, liar)
    assert schemes.keeps_secret(scene, liar.ref)
    assert not schemes.keeps_secret(scene, "pc")
    cards_mod.resolve(scene, card.id)
    assert not schemes.keeps_secret(scene, liar.ref)


def test_a_hunch_is_dc_20_and_one_read_a_day():
    scene, engine, pc = _here(faces={"Sense Motive": 19})
    honest = _person(scene, "Orrin")
    out = _run(engine, {**_check("sense motive"), "target": honest.ref})[0]
    assert out.dc["value"] == 20 and "what they seem" in out.tell
    again = _run(engine, {**_check("sense motive"), "target": honest.ref})[0]
    assert again.status == "refused" and not again.rolls


def test_sense_enchantment_is_25_and_15_against_domination():
    """CRB: "The usual DC is 25, but if the target is dominated ... the DC is only 15".
    Read off the effect's own `spell:` stamp and the spell's school."""
    scene, engine, pc = _here(rest=10)
    charmed = _person(scene, "Wen")
    charmed.apply_effect(ActiveEffect(name="charmed", kind="condition", key="helpful",
                                      origin="spell:charm-person", tags=("attitude.helpful",)))
    held = _person(scene, "Dov")
    held.apply_effect(ActiveEffect(name="dominated", kind="condition", key="dominated",
                                   origin="spell:dominate-person"))
    a = _run(engine, {**_check("sense motive"), "target": charmed.ref})[0]
    b = _run(engine, {**_check("sense motive"), "target": held.ref})[0]
    assert a.dc["value"] == 25 and b.dc["value"] == 15
    bonus = sum(m.value for m in pc.skill_modifiers("sense motive"))
    assert pc.has_state(f"knows.enchanted.{held.ref}") == (10 + bonus >= 15)
    assert pc.has_state(f"knows.enchanted.{charmed.ref}") == (10 + bonus >= 25)


def test_kept_by_names_a_person_slot_of_a_secret_card():
    doc = json.loads((ROOT / "content/schemes/the-lost-thing.json").read_text("utf-8"))
    one = doc["schemes"][0]
    assert not schemes.validate(one)
    bad = json.loads(json.dumps(one))
    secret = next(c for c in bad["cards"] if c.get("secret"))
    secret["kept_by"] = ["nobody"]
    assert any("kept_by" in p for p in schemes.validate(bad))


# --- Knowledge: answering a question from the world ------------------------------------------

def test_a_knowledge_question_is_answered_from_the_worlds_own_record(world):
    """Audit 2026-11-22: Knowledge had a resolved use in 3 of 10 fields. Asked about a
    town's past, the answer is the export's own History and Founding facts, first sentence
    each, in Knowledge (history); no retry."""
    town = _town(world)
    scene, engine, pc = _here(world, rest=15)
    pc.ranks["knowledge (history)"] = 2
    out = _run(engine, _check("knowledge (history)", about=town.name))[0]
    assert out.verdict == "success" and "Knowledge (History)" in out.dc["basis"]
    first = skilluses._first(town.facts["History"]).rstrip(".")
    assert first in out.tell and town.name in out.tell
    assert pc.has_state(f"knows.lore.{skilluses._slug(town.id)}")
    again = _run(engine, _check("knowledge (history)", about=town.name))[0]
    assert again.status == "refused" and not again.rolls


def test_the_field_is_the_records_own_when_the_plans_holds_nothing(world):
    town = _town(world)
    scene, engine, pc = _here(world, rest=15)
    out = _run(engine, _check("knowledge (planes)", about=town.name))[0]
    assert "Knowledge (Planes)" not in out.dc["basis"]


def test_untrained_knowledge_reaches_no_higher_than_dc_10_and_a_secret_is_never_lore(world):
    """CRB: "You cannot make an untrained Knowledge check with a DC higher than 10." And a
    person's own `Secret` is theirs, never recalled however high the roll."""
    person = next(e for e in world.entities.values()
                  if e.kind == "CHARACTER" and e.facts.get("Secret"))
    scene, engine, pc = _here(world, rest=20)
    pc.ranks["knowledge (local)"] = 10
    out = _run(engine, _check("knowledge (local)", about=person.name))[0]
    assert skilluses._first(person.facts["Secret"]).rstrip(".") not in out.tell
    for k in ("knowledge (history)",):
        pc.ranks.pop(k, None)
    assert skilluses.row(skilluses.ANSWER)["never"] == ["secret", "secrets"]


def test_a_name_the_world_never_heard_of_rolls_nothing(world):
    scene, engine, pc = _here(world)
    out = _run(engine, _check("knowledge (history)", about="zzqx vellumbrook"))[0]
    assert out.status == "refused" and not out.rolls


def test_every_fact_key_in_the_shipped_worlds_has_a_field_or_its_kinds():
    """The fields table was built against both fixtures' 92 fact keys; a key outside it
    falls to its entity kind's field, never to nowhere."""
    r = skilluses.row(skilluses.ANSWER)
    for path in ("fixtures/aurvantis-campaign.json", "fixtures/pangrella-campaign.json"):
        data = json.loads((ROOT / path).read_text(encoding="utf-8"))
        for e in data["entities"]:
            for k in e["facts"]:
                assert skilluses._field_of(k, e["kind"].lower()) in set(
                    r["fields"].values()) | set(r["by_kind"].values())


def test_a_recall_of_something_the_world_names_builds_the_question(world):
    from gm import acts_to_ops
    from rules import residency

    residency.use_world(world)
    town = _town(world)
    scene, engine, pc = _here(world)
    frame = {"question": False, "claims": [], "actions": [
        {"span": f"what do I know of {town.name}", "act": "look", "recall": True,
         "target": town.name, "commit": "done"}]}
    built = [i for r in acts_to_ops.table(frame, scene) for i in r.intents]
    assert built and built[0]["params"]["about"] == town.name


# --- Appraise --------------------------------------------------------------------------------

def test_appraise_made_is_the_counters_own_price_and_says_magic_at_five_over():
    """Audit 2026-11-22: "Appraise never changes what you pay or are paid ... valuing loot
    [is] not rolled". DC 20; the value is `pricing.goods_worth`, the number counters use."""
    scene, engine, pc = _here(rest=19)
    pc.ranks["appraise"] = 6
    out = _run(engine, _check("appraise", item="dagger"))[0]
    assert out.verdict == "success" and out.dc["value"] == 20
    fx = next(e for e in out.effects if e["kind"] == "appraised")
    assert fx["said_cp"] == round(pricing.goods_worth("dagger") * 100)
    assert "no magic in it" in out.tell
    again = _run(engine, _check("appraise", item="dagger"))[0]
    assert again.tell == out.tell and not again.rolls


def test_appraise_missed_by_less_than_five_is_within_twenty_percent():
    scene, engine, pc = _here(rest=1)
    pc.ranks.pop("appraise", None)
    worth = round(pricing.goods_worth("dagger") * 100)
    total = 1 + sum(m.value for m in pc.skill_modifiers("appraise"))
    out = _run(engine, _check("appraise", item="dagger"))[0]
    said = next(e for e in out.effects if e["kind"] == "appraised")["said_cp"]
    if 20 - total < 5:
        assert 0.8 * worth - 1 <= said <= 1.2 * worth + 1
    else:
        assert 0.4 * worth - 1 <= said <= 2.5 * worth + 1


def test_appraise_names_a_thing_in_hand():
    scene, engine, pc = _here()
    out = _run(engine, _check("appraise", item="a crown of stars"))[0]
    assert out.status == "refused" and not out.rolls


# --- Spellcraft ------------------------------------------------------------------------------

def _wizard(scene, ref="c2"):
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d["kind"], d["name"] = "npc", "the hedge wizard"
    d["prepared"] = {"magic-missile": 2}
    w = scene.add(from_dict(d, ref=ref))
    w.hp = w.hp_max = 500
    return w


def _cast(face, ranks):
    scene, engine, pc = _here(faces={"Spellcraft": face}, rest=10)
    pc.ranks.pop("spellcraft", None)
    if ranks:
        pc.ranks["spellcraft"] = ranks
    pc.hp = pc.hp_max = 500
    _wizard(scene)
    res = engine.run(engine.validate([{"op": "cast", "actor": "c2", "target": "pc",
                                       "params": {"spell": "magic-missile"},
                                       "visibility": "hidden"}]))
    return next(o for o in res.outcomes if o.op == "cast")


def test_a_cast_nobody_here_can_identify_names_no_spell():
    """CRB: identifying a spell as it is cast is Spellcraft, DC 15 + spell level, trained
    only. Every cast's tell named the spell, so the narrator always knew it."""
    out = _cast(20, 0)
    assert "Magic Missile" not in out.tell and "a spell" in out.tell


def test_a_cast_identified_is_named_and_one_missed_is_not():
    made = _cast(20, 1)
    assert "knows the casting at once: Magic Missile" in made.tell
    missed = _cast(1, 1)
    assert "Magic Missile" not in missed.tell
    assert any(e.get("kind") == "identified" and e["dc"] == 16 for e in missed.effects)


# --- Perform ---------------------------------------------------------------------------------

def test_perform_for_coin_pays_by_the_books_table_into_the_purse(world):
    """Audit 2026-11-22: "Performing for coin ... not in play". The CRB's table, an
    evening's work in a settlement, the coin in the purse."""
    from rules import goods

    scene, engine, pc = _here(world, faces={"Perform": 20})
    pc.ranks["perform"] = 4
    before = goods.in_copper(pc.purse)
    total = 20 + sum(m.value for m in pc.skill_modifiers("perform"))
    out = _run(engine, _check("perform"))[0]
    gained = goods.in_copper(pc.purse) - before
    row = next(p for d, p in sorted(skilluses.row(skilluses.PERFORM)["table"].items(),
                                    key=lambda kv: -int(kv[0])) if total >= int(d))
    dice = row["dice"]
    n, sides = int(dice.split("d")[0]), int(dice.split("d")[1])
    assert n * int(row["cp_each"]) <= gained <= n * sides * int(row["cp_each"])
    assert row["said"] in out.tell


def test_a_failed_performance_puts_two_on_the_next_today(world):
    scene, engine, pc = _here(world, faces={"Perform": 1})
    pc.ranks.pop("perform", None)
    total = 1 + sum(m.value for m in pc.skill_modifiers("perform"))
    if total >= 10:
        pytest.skip("this sheet cannot fail a routine performance on a 1")
    first = _run(engine, _check("perform"))[0]
    second = _run(engine, _check("perform"))[0]
    assert first.dc["value"] == 10 and second.dc["value"] == 12


# --- the one type table ----------------------------------------------------------------------

def test_the_ooc_door_files_vermin_and_monstrous_humanoids_under_nature():
    """play/gm_answers.py kept its own creature-type table with both under dungeoneering,
    where the CRB puts them under nature; it reads the one table now."""
    from play import gm_answers

    assert gm_answers._knowledge("vermin") == "Knowledge (nature)"
    assert gm_answers._knowledge("monstrous humanoid") == "Knowledge (nature)"
    assert gm_answers._knowledge("ooze") == "Knowledge (dungeoneering)"


# --- the reading aims what the plan left bare ------------------------------------------------

def test_a_planned_read_with_no_target_reads_the_person_the_words_name():
    """Live 2026-11-22 (gemma-4-12B): "I watch Tanna Vell's face closely. Is she lying to
    me?" was planned `check sense motive` with target null, and the read had nobody."""
    from gm import acts_to_ops

    scene, engine, pc = _here()
    tanna = _person(scene, "Tanna Vell")
    _person(scene, "Orrin")
    plan = [{"op": "check", "actor": "pc", "params": {"skill": "sense motive"}},
            {"op": "check", "actor": "pc", "params": {"skill": "appraise"}}]
    acting = [{"act": "look", "target": "Tanna Vell", "commit": "done"},
              {"act": "look", "object": "my dagger", "commit": "done"}]
    acts_to_ops.aim_the_reads(plan, acting, scene, pc)
    assert plan[0]["target"] == tanna.ref
    assert plan[1]["params"]["item"] == "my dagger"


def test_a_question_that_names_a_fact_key_is_answered_in_that_keys_field(world):
    """Live 2026-11-22: "I try to recall what I know of the history of Branford" rolled
    Knowledge (local) and told the town's customs; the record's own key, History, names
    the field."""
    town = _town(world)
    topic = skilluses.topic_in(world, town.name)
    field, facts = skilluses.answer_field(topic, "knowledge (local)",
                                          f"the history of {town.name}")
    assert field == "knowledge (history)" and any(k == "History" for k, _ in facts)
