"""Skill uses with their own row: the DC, the action and the consequence are the engine's.

The implementation audit of 2026-11-22 (docs/implementation-audit-2026-11-22.md §2, lane E)
measured the skill ledger by hand: about 45 of ~100 CRB uses resolved, and the top gaps by
how often play hits them were these —

  1. feint, "aliased to Bluff and rolled with no consequence" (rules/intents.py filed
     "feint" as a Bluff, and a made feint changed nothing about the next blow);
  2. Acrobatics tumble: "no DC vs CMD, and reactions.py knows only the 5-ft step and
     withdraw";
  3. Knowledge monster lore: "DC 10 + CR exists only as out-of-character text in
     play/gm_answers.py" (whose type table also filed vermin and monstrous humanoids under
     Dungeoneering, where the CRB's table puts both under Nature);
  5. Heal against bleed: the bleed tell promised "until a DC 15 Heal check or magical
     healing stops it", `firstaid` treated only the dying and `Actor.heal` removed no
     bleed — "the engine makes two promises it does not keep".

And the honesty ledger was stale in 11 of 35 skill cards, because tests/test_skill_help.py
read every `uses` anchor back and never looked at a `not_yet`. The ratchet here closes that:
each card's `not_yet_uses` names the uses its `not_yet` line says are missing, and a use
named there that has a row in content/rules/skill-uses.json fails the suite.

Every behaviour test goes through `Engine.run` and reads the sheet and the tells.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import skilluses
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from rules.tables import SKILLS

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


def _fight(foe: str = "thug", faces=None, rest: int = 10, pc_at=(6, 10), foe_at=(7, 10)):
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate(foe, scene=scene, name="the foe"))
    engine = Engine(scene, _Faces(faces, rest))
    engine._ensure_encounter("pc")
    scene.positions["pc"], scene.positions["c1"] = pc_at, foe_at
    scene.resync_zones()
    # Everybody has acted: nobody is flat-footed for not having had a turn, so a feint is
    # the only thing that can take the foe's Dexterity away.
    scene.acted.update(scene.actors)
    return scene, engine, scene.get("pc"), scene.get("c1")


def _run(engine, *raws):
    res = engine.run(engine.validate([dict(r, visibility="hidden") for r in raws]))
    assert not res.awaiting
    return res.outcomes


def _check(**params):
    return {"op": "check", "actor": "pc", "params": params}


# --- the table and the ledger ---------------------------------------------------------------

def test_every_row_loads_and_names_the_code_that_makes_it_true():
    """Each row's `resolved_by` is read back, as the hover's `uses` are: a row whose code
    moved or went fails here instead of claiming a use the engine no longer has."""
    table = skilluses.rows()
    assert not skilluses.validate(table)
    for uid, row in table.items():
        text = (ROOT / row["resolved_by"]["file"]).read_text(encoding="utf-8")
        assert row["resolved_by"]["find"] in text, uid


def _cards() -> dict:
    return json.loads((ROOT / "content/rules/skills-explained.json")
                      .read_text(encoding="utf-8"))["skills"]


def test_a_not_yet_line_that_names_a_resolved_use_fails():
    """The ratchet the audit asked for. Measured 2026-11-22: 11 of 35 `not_yet` lines were
    false (Diplomacy's request, Disable Device's traps, Disguise held, Escape Artist's
    grapple, Intimidate's demoralize, Perception's traps, Sleight of Hand's take, Stealth
    held, Survival's living off the land, Swim, half of Climb) — and nothing noticed,
    because no test read a `not_yet`. Every card with a `not_yet` names its missing uses,
    and none of them may be a row of the resolved table."""
    resolved = set(skilluses.rows())
    for sid, card in _cards().items():
        if not str(card.get("not_yet") or "").strip():
            assert not card.get("not_yet_uses"), sid
            continue
        named = card.get("not_yet_uses")
        assert named, f"{sid}: a not_yet line with no not_yet_uses — name the uses it means"
        stale = sorted(set(named) & resolved)
        assert not stale, (f"{sid}: its not_yet says {stale} is missing, and the engine "
                           f"resolves it (content/rules/skill-uses.json). Rewrite the line.")


def test_every_resolved_use_is_on_its_skills_card():
    """The other half: a use the engine resolves is said on the card the player hovers,
    so building one without telling the player fails too."""
    cards = _cards()
    for uid, row in skilluses.rows().items():
        skills = (sorted(set(row["by_type"].values())) if row["skill"] == "knowledge"
                  else [row["skill"]])
        for sid in skills:
            said = {u.get("use") for u in cards[sid].get("uses") or ()}
            assert uid in said, f"{sid}: resolves {uid}, and its card does not say so"


def test_monster_lore_files_each_type_where_the_crb_table_does():
    """CRB, Knowledge's table: Nature takes "animals, fey, monstrous humanoids, plants,
    vermin". play/gm_answers.py had vermin and monstrous humanoids under Dungeoneering."""
    by_type = skilluses.row(skilluses.LORE)["by_type"]
    assert by_type["vermin"] == by_type["monstrous humanoid"] == "knowledge (nature)"
    assert by_type["ooze"] == "knowledge (dungeoneering)"
    assert set(by_type.values()) <= set(SKILLS)


# --- feint ---------------------------------------------------------------------------------

def test_a_made_feint_takes_the_foes_dexterity_from_the_next_melee_blow_and_no_further():
    """Audit 2026-11-22 item 1: a feint was rolled and changed nothing. Now the foe holds
    `state.feinted.pc` until the feinter's next melee attack, which is judged against the
    flat-footed AC and spends it; the next blow meets the full AC again."""
    scene, engine, pc, foe = _fight(faces={"Bluff": 20, "attack": 10})
    full, caught = foe.ac(), foe.ac(flat_footed=True)
    assert full > caught, "the fixture foe needs Dexterity on its AC"
    pc.feats.append("improved feint")       # a move action, so the blow follows this turn
    out = _run(engine, {**_check(skill="bluff", feint=True), "target": "c1"})[0]
    assert out.verdict == "success" and "guard is drawn" in out.tell
    assert foe.has_state("state.feinted.pc")
    assert out.dc["value"] == max(10 + foe.bab + foe.ability_mod("wis"),
                                  10 + 0)  # a thug untrained in Sense Motive
    blow = _run(engine, {"op": "attack", "actor": "pc", "target": "c1"})
    swing = next(o for o in blow if o.op == "attack")
    assert swing.dc["value"] == caught, swing.dc
    assert "feint has drawn" in swing.tell
    assert not foe.has_state("state.feinted")
    scene.round += 1
    again = next(o for o in _run(engine, {"op": "attack", "actor": "pc", "target": "c1"})
                 if o.op == "attack")
    assert again.dc["value"] == full


def test_a_feint_is_the_turns_standard_action_without_improved_feint():
    """CRB, Combat: "Feinting in combat is a standard action"; Improved Feint makes it a
    move action. Without the feat the blow the same turn is refused."""
    scene, engine, pc, foe = _fight(faces={"Bluff": 20})
    outs = _run(engine, {**_check(skill="bluff", feint=True), "target": "c1"},
                {"op": "attack", "actor": "pc", "target": "c1"})
    assert outs[0].verdict == "success"
    refused = next(o for o in outs if o.op == "attack")
    assert refused.status == "refused" and "standard action" in refused.tell
    assert foe.has_state("state.feinted.pc"), "the feint waits for next turn's blow"


def test_greater_feint_exposes_the_foe_to_everybody_until_the_feinters_turn():
    scene, engine, pc, foe = _fight(faces={"Bluff": 20})
    pc.feats += ["improved feint", "greater feint"]
    out = _run(engine, {**_check(skill="bluff", feint=True), "target": "c1"})[0]
    assert "Greater Feint" in out.tell
    assert foe.loses_dex_to_ac and foe.has_state(skilluses.EXPOSED_BY_FEINT)


def test_a_feint_against_a_mindless_body_is_impossible_and_an_animal_is_at_minus_eight():
    """CRB, Combat, Feint: "Against a creature lacking an Intelligence score, it's
    impossible"; animal Intelligence (1 or 2) is -8."""
    scene, engine, pc, bones = _fight("human-skeleton")
    out = _run(engine, {**_check(skill="bluff", feint=True), "target": "c1"})[0]
    assert out.status == "refused" and "impossible" in out.tell and not out.rolls
    scene, engine, pc, wolf = _fight("wolf")
    out = _run(engine, {**_check(skill="bluff", feint=True), "target": "c1"})[0]
    assert any(m.value == -8 for m in out.rolls[0].modifiers), out.rolls


def test_a_feint_gives_only_the_first_swing_of_a_full_attack():
    """"the next melee attack" — one swing. Foundry PF1's per-attack conditionals broke in
    this shape (0.81.1: a term applied only to the first attack), so the full attack has
    its own test. A troll that feinted the player claws, claws and bites, every swing at
    +8 on a face that reaches the player's flat-footed AC and not the full one: the first
    lands and the other two meet the guard."""
    scene, engine, pc, troll = _fight("troll")
    ff, full = pc.ac(flat_footed=True), pc.ac()
    face = ff - 8
    assert full > ff and 2 <= face <= 19, (ff, full)
    engine.dice = _Faces({"attack": face}, rest=face)
    pc.apply_effect(ActiveEffect(name="feinted by the troll", kind="situation",
                                 key="feinted-by-c1", source=skilluses.FEINT_SOURCE,
                                 duration="rounds", rounds_left=2,
                                 tags=("state.feinted.c1",)))
    swing = next(o for o in _run(engine, {"op": "attack", "actor": "c1", "target": "pc",
                                          "params": {"full_attack": True}})
                 if o.op == "attack")
    results = [b["result"] for b in swing.blows]
    assert len(results) >= 2 and results[0] == "hit" and set(results[1:]) == {"miss"}, (
        results, swing.tell)
    assert not pc.has_state("state.feinted")


# --- tumble ----------------------------------------------------------------------------------

def test_a_won_tumble_draws_no_attack_of_opportunity_and_a_lost_one_does():
    """Audit 2026-11-22 item 2. Leaving the foe's reach provokes; the tumble's Acrobatics
    against the foe's CMD waives that foe's swing (`movement.unprovoking.<ref>`), and the
    waiver is spent by the move."""
    scene, engine, pc, foe = _fight(faces={"Acrobatics": 20})
    outs = _run(engine, _check(skill="acrobatics", tumble=True, square=[6, 13]),
                {"op": "move", "actor": "pc", "params": {"who": "pc", "square": [6, 13]}})
    assert outs[0].dc["value"] == foe.cmd() and "Slips past" in outs[0].tell
    assert not any(o.op == "attack" for o in outs), [o.tell for o in outs]
    assert tuple(scene.positions["pc"])[:2] == (6, 13)
    assert not pc.has_state(skilluses.UNPROVOKING)
    scene, engine, pc, foe = _fight(faces={"Acrobatics": 1})
    outs = _run(engine, _check(skill="acrobatics", tumble=True, square=[6, 13]),
                {"op": "move", "actor": "pc", "params": {"who": "pc", "square": [6, 13]}})
    assert any(o.op == "attack" and o.actor == "c1" for o in outs)


def test_tumbling_at_full_speed_is_ten_harder():
    scene, engine, pc, foe = _fight(faces={"Acrobatics": 20})
    far = (6, 10 + pc.speed_feet // 5)
    out = _run(engine, _check(skill="acrobatics", tumble=True, square=list(far)))[0]
    assert out.dc["value"] == foe.cmd() + 10 and "full speed" in out.tell


# --- monster lore ----------------------------------------------------------------------------

def test_monster_lore_is_dc_ten_plus_cr_in_the_types_knowledge_and_tells_only_what_is_known():
    """Audit 2026-11-22 item 3. A troll is a humanoid (giant), CR 5: Knowledge (local), DC
    15, whatever Knowledge the plan named; made by 10, three facts and no more."""
    scene, engine, pc, troll = _fight("troll", rest=20)
    pc.ranks["knowledge (local)"] = 5
    out = _run(engine, {**_check(skill="knowledge (arcana)", dc={"band": "average"}),
                        "target": "c1"})[0]
    assert out.dc["value"] == 15 and "Knowledge (Local)" in out.dc["basis"]
    assert pc.has_state("knows.creature.troll")
    facts = next(e for e in pc.effects if "knows.creature.troll" in e.tags).payload["facts"]
    assert len(facts) == 1 + out.margin // 5 or len(facts) == len(skilluses._facts(troll))
    assert all(f in out.tell for f in facts)
    again = _run(engine, {**_check(skill="knowledge (local)", dc={"band": "average"}),
                          "target": "c1"})[0]
    assert again.status == "refused" and not again.rolls


def test_monster_lore_untrained_reaches_no_higher_than_dc_ten():
    scene, engine, pc, troll = _fight("troll", rest=20)
    pc.ranks.pop("knowledge (local)", None)
    out = _run(engine, {**_check(skill="knowledge (local)", dc={"band": "average"}),
                        "target": "c1"})[0]
    assert out.status == "refused" and "untrained" in out.tell


# --- heal -------------------------------------------------------------------------------------

def _bleed(actor):
    from rules import states

    actor.apply_effect(ActiveEffect(name="Bleed", kind="condition", key="bleed",
                                    source="a test wound", tags=states.tags_for("bleed"),
                                    periodic=[{"per": "round", "damage": "1",
                                               "damage_type": "untyped"}]))


def test_a_dc_15_heal_check_stops_a_bleed_the_tell_promised_it_would():
    """Audit 2026-11-22 item 5: `Engine._rider_bleed` told "until a DC 15 Heal check or
    magical healing stops it", and a Heal check on a bleeding foe did nothing."""
    scene, engine, pc, foe = _fight(faces={"Heal": 15})
    _bleed(foe)
    out = _run(engine, {**_check(skill="heal", dc={"band": "easy"}), "target": "c1"})[0]
    assert out.dc["value"] == 15 and "stops bleeding" in out.tell
    assert not foe.has_state("state.wound.bleeding")
    _bleed(pc)
    out = _run(engine, _check(skill="heal", dc={"band": "easy"}))[0]
    assert "their own wound" in out.tell and not pc.has_state("state.wound.bleeding")


def test_magical_healing_stops_a_bleed_and_a_draught_does_not():
    scene, engine, pc, foe = _fight()
    _bleed(foe)
    foe.hp -= 4
    heal = {"op": "heal", "actor": "pc", "params": {"to": "c1", "amount": 2}}
    engine.run(engine.validate([heal], origin="item:healing-draught"))
    assert foe.has_state("state.wound.bleeding"), "chemistry is not magical healing"
    out = engine.run(engine.validate([heal], origin="spell:cure-light-wounds")).outcomes[0]
    assert "stops bleeding" in out.tell and not foe.has_state("state.wound.bleeding")


def test_long_term_care_doubles_the_patients_night_and_never_tends_yourself():
    scene, engine, pc, foe = _fight(faces={"Heal": 15})
    out = _run(engine, {**_check(skill="heal", care=True), "target": "c1"})[0]
    assert out.verdict == "success" and foe.has_state(skilluses.LONG_TERM_CARE)
    foe.hp = 1
    night = foe.rest("night")
    assert night["healed"] == 2 * max(1, foe.level) and not foe.has_state("care.long-term")
    mine = _run(engine, _check(skill="heal", care=True))[0]
    assert mine.status == "refused" and "themselves" in mine.tell


# --- Dazzling Display ---------------------------------------------------------------------------

def test_dazzling_display_demoralizes_every_foe_in_thirty_feet_who_sees_it():
    scene, engine, pc, foe = _fight(faces={"Intimidate": 20})
    refused = _run(engine, _check(skill="intimidate", display=True))[0]
    assert refused.status == "refused" and "Dazzling Display" in refused.tell
    pc.feats += ["dazzling display", f"weapon focus ({pc.wielded_key()})"]
    out = _run(engine, _check(skill="intimidate", display=True))[0]
    assert foe.has_state("state.fear"), out.tell
    assert scene.standard_spent.get("pc") == scene.round == scene.move_spent.get("pc")


def test_the_skill_feat_documents_validate_and_grant_their_use_tags():
    from rules import classbuilder, feats

    docs = feats.documents()
    for fid in ("improved-feint", "greater-feint", "dazzling-display"):
        assert fid in docs
    assert not classbuilder.validate_feat_documents(docs)


# --- the reader's route ------------------------------------------------------------------------

def _frame(*actions):
    return {"question": False, "claims": [], "actions": list(actions)}


def test_a_feint_read_by_the_reader_builds_the_bluff_and_drops_the_plans_own_blow():
    """The owner's direction: models read, code validates. The reader's closed `blow` is
    feint; the table builds the feint check at the foe the words name, and the plan's
    own swing at the same foe is not struck — the player feinted."""
    from gm import acts_to_ops, judgement

    scene, engine, pc, foe = _fight()
    frame = _frame({"span": "feint at the foe", "target": "the foe", "blow": "feint",
                    "act": "attack"})
    rows = acts_to_ops.table(frame, scene)
    acts_to_ops.victims(rows, frame, scene)
    built = [i for r in rows for i in r.intents]
    assert built and built[0]["op"] == "check" and built[0]["params"]["feint"]
    plan = [{"op": "attack", "actor": "pc", "target": "c1"}]
    out = judgement.inject_fight(plan, "I feint at the foe", scene, rows=rows, frame=frame)
    assert [r["op"] for r in out] == ["check"]


def test_a_tumble_read_by_the_reader_puts_the_check_before_the_move():
    from gm import acts_to_ops

    scene, engine, pc, foe = _fight()
    frame = _frame({"span": "roll past the foe to G14", "place": "G14", "tumble": True,
                    "act": "go"})
    rows = acts_to_ops.table(frame, scene)
    ops = [i["op"] for r in rows for i in r.intents]
    assert ops == ["check", "move"], ops       # the board names G14
    first, move = rows[0].intents
    assert first["params"]["tumble"]
    assert first["params"]["square"] == move["params"]["square"][:2]


def test_a_recall_read_by_the_reader_rolls_the_types_knowledge():
    from gm import acts_to_ops

    scene, engine, pc, wolf = _fight("wolf")
    frame = _frame({"span": "what do I know about the foe", "target": "the foe",
                    "recall": True, "act": "look"})
    rows = acts_to_ops.table(frame, scene)
    built = [i for r in rows for i in r.intents]
    assert built[0]["params"]["skill"] == "knowledge (nature)" and built[0]["target"] == "c1"


def test_the_reader_offers_feint_tumble_and_recall_as_closed_answers():
    from gm import interpret

    assert "feint" in interpret.BLOWS
    alts = {a["properties"]["act"]["const"]: a["properties"]
            for a in interpret.per_act_schema()["properties"]["actions"]["items"]["anyOf"]}
    assert alts["go"]["tumble"] == {"type": "boolean"}
    assert alts["look"]["recall"] == {"type": "boolean"}
    kept, _dropped = interpret.ground({"question": False, "claims": [], "actions": [
        {"span": "roll past him", "act": "go", "tumble": True, "commit": "done"},
        {"span": "what do I know of it", "act": "look", "recall": True, "commit": "done"}]},
        "I roll past him. what do I know of it")
    assert kept["actions"][0].get("tumble") is True
    assert kept["actions"][1].get("recall") is True


def test_a_tumble_read_onto_a_walk_with_no_square_rides_on_to_the_next_walk():
    """Read live 2026-11-22 (gemma-4-12B): "I roll under the ogre's swing and come up at
    E6" came back as two walks, the tumble on the first, which named no square."""
    from gm import acts_to_ops

    scene, engine, pc, foe = _fight()
    frame = _frame({"span": "roll under the foe's swing", "place": "under the foe's swing",
                    "tumble": True, "act": "go"},
                   {"span": "come up at G14", "place": "G14", "act": "go"})
    rows = acts_to_ops.table(frame, scene)
    ops = [(i["op"], bool((i.get("params") or {}).get("tumble"))) for r in rows
           for i in r.intents]
    assert ("check", True) in ops and ops.index(("check", True)) < ops.index(("move", False))


def test_a_recall_with_no_target_is_of_the_one_stranger_here():
    """Read live 2026-11-22: "I try to recall what I know about the troll" came back
    `look, recall` with no target, 3 times of 3; one recall a turn."""
    from gm import acts_to_ops

    scene, engine, pc, troll = _fight("troll")
    frame = _frame({"span": "recall what I know", "recall": True, "act": "look"},
                   {"span": "remember the stories", "recall": True, "act": "look"})
    built = [i for r in acts_to_ops.table(frame, scene) for i in r.intents]
    assert [(b["op"], b["target"]) for b in built] == [("check", "c1")]
    assert built[0]["params"]["skill"] == "knowledge (local)"
