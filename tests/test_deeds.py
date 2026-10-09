"""The deeds system: the good and bad things the player does, as one signed number.

The owner, 2026-10-08: "most actions should only have a small impact, otherwise people
will not mean to do certain things and it goes from a funny accident to a source of
frustration very quickly if they are punished too heavily ... track this as a number
positive for good deed and negative for bad deeds. you should be able to look at this
number in your sheet but i dont want it to affect anything yet."

The design is docs/deeds-plan.md (§12 lists these tests); the research docs/deeds-prior-art.md
(PA §n). Every test drives the real engine through `Engine.run`, so the reader in `_drive`
is the one exercised, and names the defect it prevents.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from rules import attitude as attitude_mod
from rules import deeds
from rules import states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from tests._places import stand_on

ABILITIES = {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")}


def _person(s, ref, name, hp=30, **extra):
    d = {"name": name, "kind": "npc", "hp": hp, "hp_max": hp, "abilities": dict(ABILITIES)}
    d.update(extra)
    return s.add(from_dict(d, ref=ref))


def _street(seed=5):
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    return s, pc, Engine(s, Dice(seed=seed))


def _run(e, raw, *, origin="", face=19):
    """Run a list and roll the player's d20s (a high face) until it completes."""
    res = e.run(e.validate(raw, origin=origin) if origin else e.validate(raw))
    return _finish(e, res, face)


def _finish(e, res, face=19):
    for _ in range(30):
        if not res.awaiting:
            break
        top = int(res.awaiting.get("max") or 20)
        res = e.resume(face=min(face, top) if top != 20 else face)
    assert not res.awaiting
    return res


def _deeds_on(res) -> list[dict]:
    return [x for o in res.outcomes for x in o.effects if x.get("kind") == "deed"]


def _hit(e, attacker, target, *, face=19):
    """A blow with what is in hand (Kesst's rapier): a fist would be nonlethal."""
    return _run(e, [{"op": "attack", "actor": attacker, "target": target,
                     "because": "a blow", "params": {}}], face=face)


# --- the store ----------------------------------------------------------------------------


def test_an_old_save_has_no_deeds_and_writes_none():
    """An old campaign loads with `deeds == []` and saves byte-identical. The defect it
    prevents: a new field written as `"deeds": []` would have broken the round trip of all
    twelve of the owner's saves (`test_the_owners_real_saves_round_trip_byte_identically`)
    on the first save after the update."""
    raw = json.loads(Path("fixtures/pc-kesst.json").read_text(encoding="utf-8"))
    assert "deeds" not in raw
    pc = from_dict(raw)
    assert pc.deeds == []
    once = to_dict(pc)
    assert "deeds" not in once
    assert json.dumps(to_dict(from_dict(once)), sort_keys=True) == json.dumps(once, sort_keys=True)
    # And a row, once written, goes into the save and comes back whole.
    s, pc, e = _street()
    deeds.record(pc, "deed.trespass", scene=s, subject="h1", subject_name="Hemmet's house")
    back = from_dict(json.loads(json.dumps(to_dict(pc))))
    assert back.deeds == pc.deeds and back.deeds[0]["tag"] == "deed.trespass"


def test_the_total_is_the_sum_of_the_rows():
    """No stored total exists to drift: the number on the sheet is the sum of the rows the
    player can read (a running total beside the list is a second store, law 2; Ultima's
    99 cap and Fallout's +-1000 made a total that was no longer the sum, PA §2, §5)."""
    s, pc, e = _street()
    for tag, who in (("deed.theft", "a"), ("deed.mercy.saved", "b"), ("deed.theft", "a"),
                     ("deed.mercy.tended", "c"), ("deed.kill.captive", "d")):
        deeds.record(pc, tag, scene=s, subject=who, subject_name=who)
    assert deeds.total(pc) == sum(r["value"] for r in pc.deeds) == -1 + 2 + 0 + 1 - 2
    saved = to_dict(pc)
    assert set(saved) & {"deeds_total", "deed_total", "karma"} == set()
    assert not any("total" in r for r in saved["deeds"])
    assert deeds.summary(pc)["total"] == deeds.total(pc)


# --- accidents, assaults, murder ------------------------------------------------------------


def test_a_splash_on_the_boy_by_the_well_costs_nothing():
    """Alchemist's fire aimed at a thug, the spill on a bystander who was not hostile: one
    `deed.violence.accident` row at 0. The defect it prevents is RDR2's "an accident
    punished me" (PA §6) — the owner's "funny accident to a source of frustration"."""
    from tests.test_splash_bystanders import _market, _throw

    s, e, (boy,) = _market(("guildhand", "the boy"))
    pc = s.pc()
    res = _throw(e)
    assert boy.hp < boy.hp_max, "the splash must have reached him for this to test anything"
    rows = deeds.of(pc, "deed.violence")
    assert [(r["tag"], r["value"], r["how"], r["subject"]) for r in rows] == [
        ("deed.violence.accident", 0, "accident", boy.ref)], pc.deeds
    assert deeds.total(pc) == 0
    assert any(d["tag"] == "deed.violence.accident" for d in _deeds_on(res))


def test_swinging_at_the_merchant_is_one_deed_however_many_blows():
    """Three blows in one fight, one counted -2. The defect: the first blow makes him
    hostile through `_foes_settle`, and a reader without the ledger's memory or the
    snapshot would have scored the later blows as fighting back — or, reading the record
    alone, as three assaults."""
    s, pc, e = _street()
    m = _person(s, "c1", "the merchant", hp=200)
    for _ in range(3):
        _hit(e, "pc", "c1")
    rows = deeds.of(pc, "deed.violence")
    assert len(rows) == 1 and rows[0]["tag"] == "deed.violence.unprovoked", pc.deeds
    assert deeds.total(pc) == -2
    assert m.hp < m.hp_max


@pytest.mark.parametrize("hp", [1, 40])
def test_murder_weighs_the_same_in_one_blow_or_ten(hp):
    """-5 in all however many blows it took (the owner's answer 1, 2026-10-08: "keep -5
    in all"): the violence row and the kill row, never a row per blow."""
    s, pc, e = _street()
    m = _person(s, "c1", "the merchant", hp=hp)
    for _ in range(40):
        if m.has_state("state.down.dead"):
            break
        if m.is_down:
            _run(e, [{"op": "attack", "actor": "pc", "target": "c1", "because": "finish",
                      "params": {"weapon": "unarmed", "coup_de_grace": True,
                                 "lethality": "lethal"}}])
            continue
        _run(e, [{"op": "damage", "actor": "pc", "target": "c1", "because": "a blow",
                  "params": {"amount": 6, "type": "slashing"}}], origin="author:test")
    assert m.has_state("state.down.dead")
    assert deeds.total(pc) == -5, pc.deeds
    assert [r["tag"] for r in pc.deeds if r["value"]] == ["deed.violence.unprovoked",
                                                          "deed.kill.unprovoked"]


def test_a_merchant_who_bleeds_out_after_your_blow_is_still_your_kill():
    """A kill row from a later tick: somebody the player dropped to dying who bleeds out
    on a later round dies in `Scene.advance_turn`, in nobody's outcome. The ledger's
    violence row is the memory that makes it the player's (plan §5.2)."""
    s, pc, e = _street()
    m = _person(s, "c1", "the merchant", hp=8, abilities=dict(ABILITIES, con=3))
    _run(e, [{"op": "damage", "actor": "pc", "target": "c1", "because": "a blow",
              "params": {"amount": 9, "type": "slashing"}}], origin="author:test")
    assert m.has_state("state.down.dying"), m.conditions
    assert not deeds.of(pc, "deed.kill")

    class Failing(Dice):
        """Every stabilise roll a natural 1: he bleeds out, round by round."""
        def d20(self, modifiers=None, label="", **kw):
            return self.given(1, modifiers or [], label=label)

    ones = Failing(seed=1)
    for _ in range(20):
        if m.has_state("state.down.dead"):
            break
        m.bleed_out(ones)
    assert m.has_state("state.down.dead")
    # The next thing anybody does in the scene carries it.
    res = _run(e, [{"op": "check", "actor": "pc", "because": "looks around",
                    "params": {"skill": "perception", "dc": {"band": "easy"}}}])
    kills = deeds.of(pc, "deed.kill")
    assert [k["tag"] for k in kills] == ["deed.kill.unprovoked"]
    assert any(d["tag"] == "deed.kill.unprovoked" for d in _deeds_on(res))
    assert deeds.total(pc) == -5


def test_fighting_back_is_never_a_deed():
    """A robber who opened the fight is killed, and no row is written: Ultima IV's "who
    attacked first" (PA §5), GTA VI's "dealing with someone who picks a fight" (PA §6)."""
    s, pc, e = _street()
    robber = s.add(instantiate("thug", scene=s, name="the robber"))
    _run(e, [{"op": "attack", "actor": robber.ref, "target": "pc", "because": "your purse",
              "params": {}}])
    assert s.in_encounter
    for _ in range(40):
        if robber.has_state("state.down.dead"):
            break
        _run(e, [{"op": "damage", "actor": "pc", "target": robber.ref, "because": "back",
                  "params": {"amount": 8, "type": "slashing"}}], origin="author:test")
    assert robber.has_state("state.down.dead")
    assert pc.deeds == []


def test_killing_a_red_dragon_writes_nothing():
    """Killing evil is not good (the book never calls it so, PA §11; the MUDs and Fallout
    do, PA §1, §12): a hostile evil dragon killed is no deed either way."""
    from rules import bestiary

    blocks = bestiary.imported()
    key = next((k for k, v in sorted(blocks.items())
                if "dragon" in str(v.get("creature_type", "")).lower()
                and "red" in k and "E" in str(v.get("alignment", ""))), None) or next(
        k for k, v in sorted(blocks.items())
        if "dragon" in str(v.get("creature_type", "")).lower()
        and str(v.get("alignment", "")) in ("CE", "LE", "NE"))
    s, pc, e = _street()
    wyrm = s.add(instantiate(key, scene=s, name="the wyrm"))
    e.settle_attitude(wyrm, "hostile")
    for _ in range(200):
        if wyrm.has_state("state.down.dead"):
            break
        _run(e, [{"op": "damage", "actor": "pc", "target": wyrm.ref, "because": "slay",
                  "params": {"amount": 60, "type": "slashing"}}], origin="author:test")
    assert wyrm.has_state("state.down.dead")
    assert pc.deeds == []


def test_finishing_a_beaten_bandit_after_the_fight_is_a_captive_killed():
    """The book's own example: "executing a captured orc combatant" is one step toward
    evil (PA §11). Outside a fight, a helpless hostile creature killed is -2; the same
    blow while the fight runs is tactics and writes nothing."""
    s, pc, e = _street()
    bandit = _person(s, "c1", "the bandit", hp=20)
    e.settle_attitude(bandit, "hostile")
    bandit.hp = -1
    bandit.apply_hp_state()
    assert bandit.is_helpless and not s.in_encounter
    _run(e, [{"op": "damage", "actor": "pc", "target": "c1", "because": "ends it",
              "params": {"amount": 30, "type": "slashing"}}], origin="author:test")
    assert bandit.has_state("state.down.dead")
    assert [(r["tag"], r["value"]) for r in pc.deeds] == [("deed.kill.captive", -2)]


# --- the day's gate ----------------------------------------------------------------------------


def test_ten_snatches_at_one_stall_are_one_theft():
    """The day's gate (plan §8.2): ten apples lifted from one stall in a minute are one
    theft for the counter's purposes, still listed ten times — nine of them "again, the
    same day" at 0. Without it a bit of business at a stall became a catastrophe."""
    s, pc, e = _street()
    stall = _person(s, "c1", "the fruit seller", goods={"apple": 20})
    for _ in range(10):
        _run(e, [{"op": "give", "actor": "pc", "because": "she pockets one",
                  "params": {"item": "apple", "to": "pc"}}])
    rows = deeds.of(pc, "deed.theft")
    assert len(rows) == 10, pc.deeds
    assert [r["value"] for r in rows] == [-1] + [0] * 9
    assert all(r["again"] for r in rows[1:])
    assert deeds.total(pc) == -1
    assert rows[0]["subject"] == stall.ref and rows[0]["what"] == "apple"


def _beggar(s):
    b = _person(s, "c1", "the beggar")
    s.population = {"p1": {"id": "p1", "ref": b.ref, "phrase": "beggar",
                           "life": {"work": "beggar", "tags": ["crowd", "poor"]}}}
    pc = s.pc()
    pc.purse = {"gp": 10}
    return b


def _alms(e, ref="c1"):
    return _run(e, [{"op": "give", "actor": "pc", "target": ref, "because": "alms",
                     "params": {"item": "gp", "count": 1}}])


def test_the_same_beggar_twice_a_day_counts_once():
    """Ultima IV's farmed beggar: +2 of 99 per coin, whatever the amount, through one
    shared time-only gate players walked round (PA §5). Here +1 per beggar per game day;
    the second coin the same day is listed at 0, and the next day counts again."""
    s, pc, e = _street()
    _beggar(s)
    _alms(e)
    _alms(e)
    assert [r["value"] for r in deeds.of(pc, "deed.charity")] == [1, 0]
    s.clock_minutes += 24 * 60
    _alms(e)
    assert [r["value"] for r in deeds.of(pc, "deed.charity")] == [1, 0, 1]
    assert deeds.total(pc) == 2


def test_coin_to_somebody_who_is_not_poor_is_no_alms():
    """Alms is coin to a person whose life is tagged `poor` (the beggar occupation is the
    one of 53), never a tip to anybody: generosity to the well-off is the regard system's
    business (`a_gift`), not a deed."""
    s, pc, e = _street()
    _person(s, "c1", "the smith")
    pc.purse = {"gp": 10}
    _alms(e)
    assert pc.deeds == []


def test_a_resumed_attack_reads_the_same_snapshot():
    """Suspend on the player's d20, resume, and the victim's pre-blow attitude is the one
    recorded. A bystander struck in a running fight is drawn onto the other side by the
    swing itself (`join_fight`); a snapshot taken again on the resume would read him as a
    combatant and the assault as fighting back."""
    s, pc, e = _street()
    thug = s.add(instantiate("thug", scene=s, name="the thug"))
    by = _person(s, "c2", "the drover", hp=200)
    e._ensure_encounter("pc", thug.ref)
    assert not any(by.ref in refs for refs in s.sides.values())
    res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": by.ref,
                             "because": "him too", "params": {}}]))
    assert res.awaiting, "the player's own d20 suspends the swing"
    held = s.pending_partial.get("deeds_before") or {}
    assert held.get("who", {}).get(by.ref, {}).get("hostile") is False
    json.dumps(s.pending_partial)                  # a suspension is saved; it must be JSON
    assert any(by.ref in refs for refs in s.sides.values()), "the swing drew him in"
    _finish(e, res)
    assert by.hp < by.hp_max
    assert [r["tag"] for r in pc.deeds] == ["deed.violence.unprovoked"]


# --- whose deeds, and who saw -------------------------------------------------------------------


def test_only_the_player_records_deeds():
    """A companion's kill writes nothing: Fallout 2 counts only `source_obj == dude_obj`
    (PA §1), and companions obey in character (ruling 2026-10-01) — what they do is
    theirs. Neither the player's ledger nor the companion's gains a row."""
    s, pc, e = _street()
    friend = _person(s, "c2", "Bob")
    friend.apply_effect(ActiveEffect(name="travels with you", kind="situation",
                                     key="company", source="company:t",
                                     duration="until-dismissed",
                                     tags=(states.TRAVELS_WITH_YOU,)))
    m = _person(s, "c1", "the merchant", hp=5)
    _run(e, [{"op": "damage", "actor": "c2", "target": "c1", "because": "Bob's temper",
              "params": {"amount": 30, "type": "slashing"}}], origin="author:test")
    assert m.has_state("state.down.dead")
    assert pc.deeds == [] and friend.deeds == []


def test_witnesses_are_recorded_and_change_nothing():
    """The same theft seen and unseen has the same value; who saw it is kept for renown
    (Dwarf Fortress spreads deeds through the people who know them, PA §12) and read by
    nothing. KCD's hidden witness rule reads as a bug to its players (PA §10)."""
    def lift(crowd: int):
        s, pc, e = _street()
        _person(s, "c1", "the fruit seller", goods={"apple": 3})
        for i in range(crowd):
            _person(s, f"c{i + 5}", f"onlooker {i}")
        _run(e, [{"op": "give", "actor": "pc", "because": "she pockets one",
                  "params": {"item": "apple", "to": "pc"}}])
        return pc.deeds[0]

    alone, watched = lift(0), lift(3)
    assert alone["value"] == watched["value"] == -1
    assert set(watched["witnesses"]) == {"c1", "c5", "c6", "c7"}
    assert alone["witnesses"] == ["c1"]


def test_mercy_to_a_dying_foe_counts_and_a_wound_dressed_counts_once_a_day():
    """Sparing counts (KOTOR and Ultima reward it, PA §5, §8): a first-aid success that
    stops a dying enemy dying is +2; healing a hurt stranger is +1, once per person per
    day, so a wand cannot farm it (plan §7.2)."""
    s, pc, e = _street()
    foe = _person(s, "c1", "the cutthroat", hp=10)
    e.settle_attitude(foe, "hostile")
    foe.hp = -2
    foe.apply_hp_state()
    assert foe.has_state("state.down.dying")
    _run(e, [{"op": "check", "actor": "pc", "target": "c1", "because": "staunches it",
              "params": {"skill": "heal", "dc": {"band": "average"}}}], face=20)
    assert foe.has_state("state.down") and not foe.has_state("state.down.dying")
    assert [(r["tag"], r["value"]) for r in pc.deeds] == [("deed.mercy.saved", 2)]
    stranger = _person(s, "c2", "the carter", hp=10)
    stranger.hp = 4
    for _ in range(2):
        _run(e, [{"op": "heal", "actor": "pc", "target": "c2", "because": "binds it",
                  "params": {"amount": 2, "to": "c2"}}], origin="author:test")
    assert [r["value"] for r in deeds.of(pc, "deed.mercy.tended")] == [1, 0]


def test_a_hostile_brought_down_with_nonlethal_is_a_mercy():
    """Choosing not to kill (RDR1's alive bounty, PA §6): a hostile knocked out by the
    player's nonlethal damage is +1; the same knock-down from lethal damage is nothing."""
    s, pc, e = _street()
    brawler = _person(s, "c1", "the brawler", hp=6)
    e.settle_attitude(brawler, "hostile")
    _run(e, [{"op": "damage", "actor": "pc", "target": "c1", "because": "a cosh",
              "params": {"amount": 8, "type": "bludgeoning", "lethality": "nonlethal"}}],
         origin="author:test")
    assert brawler.has_state("state.down.unconscious")
    assert not brawler.has_state("state.down.dead")
    assert [(r["tag"], r["value"]) for r in pc.deeds] == [("deed.mercy.subdued", 1)]


def test_a_stolen_thing_handed_back_nets_nothing():
    """Undoing a theft (plan §7.2): the thing given back to the owner the props ledger
    names is +1, so a thief who returns it nets 0."""
    s, pc, e = _street()
    _person(s, "c1", "the fruit seller", goods={"apple": 3})
    _run(e, [{"op": "give", "actor": "pc", "because": "takes",
              "params": {"item": "apple", "to": "pc"}}])
    _run(e, [{"op": "give", "actor": "pc", "target": "c1", "because": "gives it back",
              "params": {"item": "apple"}}])
    assert [r["tag"] for r in pc.deeds] == ["deed.theft", "deed.restitution"]
    assert deeds.total(pc) == 0


def test_an_evil_spell_counts_once_a_day():
    """The owner's answer 2: [evil] -1 and [good] +1, each kind once per game day.
    "Casting an evil spell is an evil act, but... once isn't enough" (Horror Adventures,
    PA §11)."""
    from tests.test_casting_executes import wizard

    w = wizard(level=5, book=("infernal-healing", "protection-from-evil"))
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    s.add(w)
    e = Engine(s, Dice(seed=5))
    for spell in ("infernal-healing", "infernal-healing", "protection-from-evil"):
        _run(e, [{"op": "cast", "actor": "pc", "because": "the words",
                  "params": {"spell": spell, "at": "pc"}}])
    assert [(r["tag"], r["value"]) for r in w.deeds] == [
        ("deed.spell.evil", -1), ("deed.spell.evil", 0), ("deed.spell.good", 1)], w.deeds
    assert w.deeds[0]["what"] == "Infernal Healing"


# --- no model, no reader, no narrator ---------------------------------------------------------


def test_a_deed_value_outside_five_is_refused_with_the_fix_named():
    """A deed is a small number. Fallout 3's +50 for a bottle of water erased ten thefts
    and its -1000 Megaton swamped everything (PA §2); the validator refuses the row and
    says what to do instead, in the classbuilder's style."""
    doc = json.loads(Path("content/rules/deeds.json").read_text(encoding="utf-8"))
    assert deeds.validate(doc) == []
    bad = json.loads(json.dumps(doc))
    bad["deeds"]["deed.theft"]["value"] = -50
    bad["deeds"]["theft.big"] = dict(doc["deeds"]["deed.theft"])
    bad["deeds"]["deed.trespass"]["said"] = "Broke into {house}"
    bad["bands"][2]["from"] = -8
    problems = "\n".join(deeds.validate(bad))
    assert "deeds.deed.theft.value: -50 is outside -5..+5" in problems
    assert "quest-sized value belongs to a quest" in problems
    assert "deeds.theft.big: a deed's tag lives under `deed.`" in problems
    assert "{house} is not a blank" in problems
    assert "leaves a gap or an overlap" in problems


def test_no_model_can_author_a_deed():
    """No `deed` op exists in the intent schema, so neither a model nor the sampler can
    propose one, and `deeds.record` refuses a tag with no rule row: the number is always
    the row's (law 3, "no model authors a number")."""
    from rules import intents
    from rules.intents import IntentError

    assert not [op for op in intents.OPS if "deed" in op]
    assert not [n for n in dir(Engine) if n.startswith("_op_") and "deed" in n]
    s, pc, e = _street()
    # A model that writes one anyway is read as narration and changes nothing.
    try:
        got = e.validate([{"op": "deed", "actor": "pc", "because": "I was good",
                           "params": {"tag": "deed.mercy.saved", "value": 5}}])
    except IntentError:
        got = []
    assert all(i.op != "deed" for i in got)
    if got:
        e.run(got)
    with pytest.raises(ValueError, match="no deed row called 'deed.saintly'"):
        deeds.record(pc, "deed.saintly", scene=s)
    assert pc.deeds == []


# The files allowed to touch the deeds module or an actor's ledger, and what for. Anything
# else that reads it is the meter being read (docs/deeds-plan.md §8.5).
_ALLOWED = {
    "rules/deeds.py": None,                               # the module itself
    "rules/sheet.py": {"summary", ".deeds"},              # the field, the save, full_sheet
    "rules/engine.py": {"watches", "before", "read"},     # the one reader site in _drive
    "play/views.py": {"page", "summary"},                 # GET api/deeds
    "rules/harvest.py": {"record", "of_carcass", "never_harvested"},   # lane C's door
    # A different "deed": a crafting level's milestones (`Track.deeds`).
    "rules/worldclass.py": {".deeds"},
}
_USE = re.compile(r"(?<![\w.])(?:deeds|deeds_mod)\.([a-z_]\w*)")
_ATTR = re.compile(r"(?<![\w.])(?!deeds\b|deeds_mod\b)\w+(?:\.\w+)*\.deeds\b(?!\w)")
_IMPORT = re.compile(r"^\s*(?:from\s+(?:rules|\.+)\s+import\s+[^\n#]*\bdeeds\b"
                     r"|import\s+rules\.deeds)", re.M)


def _code(text: str) -> str:
    """The source with its comments and strings blanked: the scan is of what the code
    does, and this file's own neighbours explain the deeds in prose ("`Actor.deeds`")."""
    import io
    import tokenize

    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                out.append((tok.start, tok.end, '""' if tok.type == tokenize.STRING else ""))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return text
    lines = text.splitlines(keepends=True)
    for (sr, sc), (er, ec), sub in reversed(out):
        if sr == er:
            lines[sr - 1] = lines[sr - 1][:sc] + sub + lines[sr - 1][ec:]
        else:
            lines[sr - 1] = lines[sr - 1][:sc] + sub + "\n" * (er - sr)
            for r in range(sr, er - 1):
                lines[r] = ""
            lines[er - 1] = lines[er - 1][ec:]
    return "".join(lines)


def _sources(code: bool = True):
    for top in ("rules", "play", "gm", "tools", "world", "pathfindergm"):
        for path in Path(top).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            yield path.as_posix(), _code(text) if code else text


def test_nothing_reads_the_deeds_yet():
    """The owner: "i dont want it to affect anything yet". ME2's Charm options, KOTOR's
    Force mastery and Wrath's paladin drift all failed because something read the meter
    (PA §7, §8, §11). So the readers are an allowlist: the module, the sheet payload and
    the save, the one engine reader site, the page's api/deeds, and the harvest's record.
    Anything else that names the module or an actor's `.deeds` fails here — and gm/, the
    narrator's side, may name neither (the owner's answer 4)."""
    offenders = []
    for path, text in _sources():
        allowed = _ALLOWED.get(path, set())
        if allowed is None:
            continue
        uses = set(_USE.findall(text)) if _IMPORT.search(text) or path in _ALLOWED else set()
        if _IMPORT.search(text) and path not in _ALLOWED:
            offenders.append(f"{path}: imports rules.deeds")
        for name in uses - allowed:
            offenders.append(f"{path}: deeds.{name}")
        # `tests.deeds` is the deed READER's gold set (gm/deed_reader.py), a package.
        hits = [m for m in _ATTR.finditer(text) if not m.group().startswith("tests.")]
        if hits and ".deeds" not in allowed:
            line = text[:hits[0].start()].count("\n") + 1
            offenders.append(f"{path}:{line}: reads an actor's .deeds")
    assert not offenders, "something reads the deeds:\n" + "\n".join(offenders)
    # The per-turn summary the table and the narrator's brief are built from carries none.
    s, pc, e = _street()
    deeds.record(pc, "deed.theft", scene=s, subject="c1", subject_name="the fruit seller",
                 what="an apple")
    assert "deed" not in json.dumps(pc.summary()).lower()


def test_only_deeds_record_writes_the_ledger():
    """One writer (law 2): nothing but `deeds.record` appends to, assigns or edits an
    actor's ledger, so every row has a rule behind it and a value the row chose."""
    write = re.compile(r"\.deeds\s*(?:=[^=]|\+=|\[[^\]]*\]\s*=|\.(?:append|extend|insert|"
                       r"pop|remove|clear)\b)")
    offenders = [f"{path}:{text[:m.start()].count(chr(10)) + 1}"
                 for path, text in _sources() if path != "rules/deeds.py"
                 for m in write.finditer(text)]
    assert not offenders, offenders


def test_the_narrator_is_never_told_a_deed():
    """The narrator describes the act, never a verdict (the owner's answer 4): the deed
    rides as a record beside the act's own tell, the tell is the act's, and nothing the
    narrator is handed — the tells, the scene's brief, the actor summary — says "deed" or
    the history line. A narrator told "a bad deed" would moralise, and that is an effect."""
    from gm import prompts

    s, pc, e = _street()
    _person(s, "c1", "the fruit seller", goods={"apple": 3})
    res = _run(e, [{"op": "give", "actor": "pc", "because": "she pockets one",
                    "params": {"item": "apple", "to": "pc"}}])
    deed = _deeds_on(res)[0]
    tells = " ".join(o.tell for o in res.outcomes)
    assert "takes the apple from the fruit seller" in tells.lower()
    assert "deed" not in tells.lower() and deed["said"].lower() not in tells.lower()
    now = prompts.scene_now(s, outcomes=res.outcomes)
    summary = json.dumps(pc.summary())
    for text in (now, summary):
        assert "deed" not in text.lower() and "without asking" not in text.lower()
    for path, text in _sources(code=False):
        if path.startswith("gm/"):
            assert not re.search(r"""["']deed["']|["']deed\.""", text), path
