"""Lane F of the 2026-11-22 implementation audit: class pools, passive documents and
descriptors.

Measured before any of this (docs/implementation-audit-2026-11-22.md §2, §5 Lane F):

- a saved barbarian held Extra Rage and raged 4 + Con + 2/level rounds, exactly as many as
  one without it — the class file's formula was the whole maximum and no feat document
  could reach a pool; Extra Ki, Extra Channel, Extra Lay On Hands and Extra Performance
  did nothing either;
- Improved Channel's +2 DC was nowhere: a channel's DC took only its domain's terms.

Every test goes through the real sheet (`classes.apply`, the load door) or the engine's
own `validate`/`run`.
"""
from __future__ import annotations

from rules import class_abilities as ca
from rules import classes, feats as feats_mod

from tests.test_class_ability_executor import _board, _hurt, _pc, _swing, _use


def _max(actor, pid):
    classes.apply(actor)
    return actor.pool(pid).maximum


def test_extra_rage_adds_six_rounds_and_two_copies_add_twelve():
    """Audit 2026-11-22: the save holding Extra Rage raged 4 + Con + 2/level rounds, the
    same as without it. CRB: 'You can rage for 6 additional rounds per day … its effects
    stack.'"""
    plain = _pc("barbarian", 3)
    base = _max(plain, "rage")
    once = _pc("barbarian", 3, feats=["extra rage"])
    assert _max(once, "rage") == base + 6
    twice = _pc("barbarian", 3, feats=["extra rage", "extra rage"])
    assert _max(twice, "rage") == base + 12
    # A fresh pool starts full, so the extra rounds are there to spend at once.
    assert twice.pool("rage").current == base + 12


def test_each_extra_feat_reaches_its_own_pool():
    """Extra Ki +2, Extra Performance +6, Extra Lay On Hands +2, Extra Channel +2 — each
    measured against the same character without the feat."""
    cases = [("monk", 6, "extra ki", "ki", 2),
             ("bard", 3, "extra performance", "bardic performance", 6),
             ("paladin", 4, "extra lay on hands", "lay on hands", 2)]
    for cls, level, feat, pid, more in cases:
        assert _max(_pc(cls, level, feats=[feat]), pid) == _max(_pc(cls, level), pid) + more, feat
    doc = next(d for d in ca.documents()["cleric"]["abilities"] if d["key"] == "channel energy")
    plain, extra = _pc("cleric", 3), _pc("cleric", 3, feats=["extra channel"])
    assert ca.uses_left(extra, doc)[1] == ca.uses_left(plain, doc)[1] + 2
    ca.ensure_pool(extra, doc)
    assert extra.pool("channel energy").maximum == ca.uses_left(plain, doc)[1] + 2


def test_a_feat_aimed_at_a_pool_nothing_defines_is_refused_at_load():
    """A `pool.<id>` target nothing reads would be a feat that silently does nothing; the
    validator names the targets that are read."""
    from rules import classbuilder

    bad = classbuilder.validate_feat_document("extra-rage", {"modifiers": [
        {"type": "combat_mod", "target": "pool.rgae", "amount": 6}]})
    assert bad and "read by nothing" in bad[0] and "pool.rage" in bad[0]
    assert not classbuilder.validate_feat_document("extra-rage",
                                                   feats_mod.documents()["extra-rage"])


def test_improved_channel_raises_the_channel_dc_by_two():
    """Audit 2026-11-22: Improved Channel (CRB, +2 to the DC of your channel energy) had no
    document. Measured on a cleric's harm-undead burst, with and without the feat."""
    dcs = []
    for feats in ([], ["improved channel"]):
        pc = _pc("cleric", 3, feats=feats, domains=["War", "Good"])
        s, e = _board(pc, ("skeleton", (6, 5)), face=2)
        s.actors["c1"].hp = s.actors["c1"].hp_max = 60
        out, _ = _use(e, "Channel Energy (harm)")
        dcs.append(next(x["dc"] for x in out.effects if x.get("kind") == "save"))
    assert dcs[1] == dcs[0] + 2, dcs


def _heals(outcome, ref):
    return [x for x in outcome.effects if x.get("kind") == "heal" and x.get("ref") == ref]


def test_selective_channeling_spares_the_foe_in_a_healing_burst():
    """Audit 2026-11-22: Selective Channeling had no document; a cleric's healing burst
    healed the wounded thug beside her as well as her friend. With the feat (Cha 14, so
    up to 2 spared) the foe is held out and the ally is still healed; without it both are."""
    got = {}
    for feats in ([], ["selective channeling"]):
        pc = _pc("cleric", 3, feats=feats, cha=14)
        s, e = _board(pc, ("thug", (6, 5)), ("thug", (4, 5)), face=10)
        s.sides = {"pc": ["pc", "c2"], "them": ["c1"]}
        for ref in ("c1", "c2"):
            s.actors[ref].hp = 1
        out, _ = _use(e, "Channel Energy (heal)")
        got[bool(feats)] = out
    assert _heals(got[False], "c1") and _heals(got[False], "c2")
    assert not _heals(got[True], "c1") and _heals(got[True], "c2"), got[True].tell
    assert "holds the energy back from the thug 1" in got[True].tell


def test_lay_on_hands_on_herself_is_a_swift_action_and_the_bar_says_so():
    """Audit 2026-11-22: lay on hands' `self_action: "swift"` (CRB p.61, "a swift action"
    on herself) was read by nothing — the bar said "standard" and the use recorded no
    action. Now the record of a use on herself says swift, on another says standard."""
    pc = _pc("paladin", 4)
    s, e = _board(pc, ("thug", (6, 5)))
    s.sides = {"pc": ["pc", "c1"], "them": []}
    pc.hp -= 5
    out, _ = _use(e, "Lay on Hands", to="pc")
    used = next(x for x in out.effects if x.get("kind") == "use_ability")
    assert used["action"] == "swift", out.tell
    s.actors["c1"].hp -= 3
    out, _ = _use(e, "Lay on Hands", to="c1")
    assert next(x for x in out.effects if x.get("kind") == "use_ability")["action"] \
        == "standard"
    bar = next(u for u in ca.usable(pc) if u["name"] == "Lay on Hands")
    assert bar["text"].startswith("standard (swift on yourself)"), bar["text"]


def test_a_class_ability_field_nothing_reads_is_refused_with_the_fix():
    """The validator had no key whitelist (class-features' `DOC_KEYS` did), which is how a
    field read by nothing got in. A misspelt one is refused now, top level and inside
    `self`."""
    doc = dict(next(d for d in ca.documents()["paladin"]["abilities"]
                    if d["key"] == "lay on hands"))
    doc["self_actoin"] = "swift"
    doc["self"] = {"modifers": []}
    got = ca.validate_documents({"paladin": {"class": "paladin", "abilities": [doc]}})
    assert any("self_actoin" in p and "nothing reads" in p for p in got), got
    assert any(".self" in p and "modifers" in p for p in got), got


def _terms(mods):
    return {m.source: m.value for m in mods}


def test_a_spell_save_is_against_its_school_and_descriptors_so_bravery_and_still_mind_apply():
    """Audit 2026-11-22: every spell save passed `against: "spell"` alone, so bravery's
    +1 against fear, still mind's +2 against enchantment and inspire courage's morale
    against charm were written as documents and dropped on every roll. The cast's save
    now carries the spell's school, subschool and descriptors (`spell_against`)."""
    from rules import effectspec, spells

    fear = {"against": effectspec.spell_against(spells.get("cause-fear"))}
    charm = {"against": effectspec.spell_against(spells.get("charm-person"))}
    fire = {"against": effectspec.spell_against(spells.get("fireball"))}
    fighter = _pc("fighter", 2)
    assert _terms(fighter.save_modifiers("will", fear)).get("Bravery") == 1
    assert "Bravery" not in _terms(fighter.save_modifiers("will", fire))
    monk = _pc("monk", 3)
    assert _terms(monk.save_modifiers("will", charm)).get("Still mind") == 2
    assert "Still mind" not in _terms(monk.save_modifiers("will", fear))


def test_a_save_a_fear_spell_called_for_carries_bravery_through_the_engine():
    """The same through `_op_save`: a save stamped `spell:cause-fear` by the engine is a
    save against fear, and the fighter's roll carries Bravery's +1."""
    pc = _pc("fighter", 6)
    s, e = _board(pc, ("thug", (9, 9)))
    raws = e.validate([{"op": "save", "actor": "pc", "because": "test",
                        "params": {"save": "will", "dc": 30}}], origin="spell:cause-fear")
    res = e.run(raws)
    while res.awaiting:
        res = e.resume(10)
    roll = res.outcomes[-1].rolls[0]
    assert "Bravery" in str(roll), roll


def test_the_rangers_track_adds_half_his_level_to_a_survival_roll_made_to_follow_tracks():
    """Audit 2026-11-22: Track's "+1/2 level to Survival checks made to follow or identify
    tracks" had no document. The track op's roll is `against: tracks`; any other
    Survival roll is not, and does not get it."""
    ranger = _pc("ranger", 6)
    assert _terms(ranger.skill_modifiers("survival", ctx={"against": "tracks"})) \
        .get("Track") == 3
    assert "Track" not in _terms(ranger.skill_modifiers("survival"))


def test_bardic_knowledge_and_nature_sense_are_numbers_on_the_roll():
    """Audit 2026-11-22: bardic knowledge (+1/2 level, min 1, every Knowledge, untrained)
    and nature sense (+2 Knowledge (nature) and Survival) were NARRATED. A 1st-level bard
    with no ranks in Knowledge (arcana) used to be refused the roll outright."""
    bard = _pc("bard", 4)
    assert _terms(bard.skill_modifiers("knowledge (arcana)")).get("Bardic knowledge") == 2
    druid = _pc("druid", 1)
    assert _terms(druid.skill_modifiers("survival")).get("Nature sense") == 2


def _picks(choice, *picks):
    return {choice: {"option": "class option",
                     "picks": [{"pick": p, "level": 2 + 2 * i} for i, p in enumerate(picks)]}}


def test_rage_powers_lend_their_senses_while_raging_and_only_then():
    """Audit 2026-11-22: 20 of 28 rage powers were NARRATED, among them low-light vision,
    night vision and scent "while raging". Each is a tag on the one rage effect: there
    while she rages, gone when the rage ends."""
    pc = _pc("barbarian", 6, class_choices=_picks("rage power", "low-light-vision",
                                                   "night-vision", "scent"))
    s, e = _board(pc)
    assert not pc.has_state("sense.darkvision")
    out, _ = _use(e, "Rage")
    assert pc.has_state("sense.low-light") and pc.has_state("sense.darkvision") \
        and pc.has_state("sense.scent"), out.tell
    _use(e, "Rage")
    assert not pc.has_state("sense.darkvision")


def test_powerful_blow_is_once_per_rage_and_comes_back_with_the_next_rage():
    """CRB rage power: +1 damage on one blow (+1 per 4 levels), "only once per rage".
    Spent, it is refused until that rage ends; the pool refreshes on `stance.end.rage`."""
    pc = _pc("barbarian", 4, class_choices=_picks("rage power", "powerful-blow"))
    s, e = _board(pc, ("thug", (6, 5)))
    refused, _ = _use(e, "Powerful Blow", to="c1")
    assert refused.status != "resolved" or "raging" in refused.tell
    _use(e, "Rage")
    first, _ = _use(e, "Powerful Blow", to="c1")
    assert pc.has_state("buff.charged"), first.tell
    again, _ = _use(e, "Powerful Blow", to="c1")
    assert pc.pool("powerful blow").current == 0 and "Powerful Blow" not in [
        x.get("ability") for x in again.effects if x.get("kind") == "use_ability"]
    _use(e, "Rage")                      # the rage ends
    assert pc.pool("powerful blow").current == 1


def test_bleeding_attack_makes_a_sneak_attack_bleed_for_its_dice():
    """Audit 2026-11-22: all 23 rogue talents were NARRATED; Bleeding Attack's "bleed
    each round for as many points as you have sneak attack dice" ran nowhere though the
    bleed executor existed. A 6th-level rogue (3d6) at a flat-footed thug leaves it
    bleeding 3 a round."""
    pc = _pc("rogue", 6, class_choices=_picks("rogue talent", "bleeding-attack"))
    s, e = _board(pc, ("thug", (6, 5)), face=19)
    thug = s.actors["c1"]
    thug.hp = thug.hp_max = 200
    _swing(e, "c1", face=19)
    bleed = [x for x in thug.effects if x.key == "bleed"]
    assert bleed and bleed[0].periodic[0]["damage"] == "3", [x.key for x in thug.effects]


def test_finesse_rogue_writes_weapon_finesse_onto_the_sheet_when_taken():
    """Audit 2026-11-22: the talent's `bonus_feat` had no reader — Finesse Rogue was taken
    and the rogue still attacked with Strength."""
    pc = _pc("rogue", 2, feats=[])
    taken, problems = classes.take_choice(pc, "rogue talent",
                                          {"option": "class option",
                                           "picks": ["finesse-rogue"]})
    assert not problems and "weapon finesse" in pc.feats, (taken, problems, pc.feats)


def test_heart_seeker_spike_runs_and_its_save_is_only_against_the_stun():
    """Audit 2026-11-22: refused before payment for "a save DC computed from level and
    Constitution" — a need its own effects already met. It runs now: 4d10 non-lethal paid,
    Blood DMG x4 dealt whatever the save, 3 blood stacks, and a failed Fortitude save
    stuns for a round."""
    pc = _pc("blood bending", 13, paths=["blood spike"])
    s, e = _board(pc, ("thug", (7, 5)), face=19)
    thug = s.actors["c1"]
    thug.hp = thug.hp_max = 400
    out, _ = _use(e, "Heart-Seeker Spike", to="c1")
    assert out.status == "resolved", out.tell
    assert _hurt(out, "c1"), out.tell


def test_touch_of_good_reaches_ability_checks_now_that_they_are_rolled():
    """Audit 2026-11-22: Touch of Good, Inspiring Word, Strength Surge, Diviner's Fortune
    and Aura of Despair said "no roll reads an ability check yet" — stale since
    `Actor.ability_check_modifiers` (2026-10-09). The bonus now rides `<ab>_check`."""
    pc = _pc("cleric", 4, domains=["Good", "War"])
    s, e = _board(pc)
    before = sum(m.value for m in pc.ability_check_modifiers("str"))
    out, _ = _use(e, "Touch of Good", to="pc")
    assert sum(m.value for m in pc.ability_check_modifiers("str")) == before + 2, out.tell


def test_crippling_strike_and_slow_reactions_ride_a_sneak_attack():
    """Advanced talent Crippling Strike: 2 Strength damage with each sneak attack; talent
    Slow Reactions: the foe makes no attacks of opportunity for a round (its tag empties
    `reactions.reactions_for`). Both NARRATED before 2026-11-22."""
    from rules import reactions

    pc = _pc("rogue", 10, class_choices=_picks("rogue talent", "crippling-strike"))
    s, e = _board(pc, ("thug", (6, 5)), face=19)
    thug = s.actors["c1"]
    thug.hp = thug.hp_max = 300
    _swing(e, "c1", face=19)
    assert thug.ability_damage.get("str") == 2
    pc2 = _pc("rogue", 4, class_choices=_picks("rogue talent", "slow-reactions"))
    s2, e2 = _board(pc2, ("thug", (6, 5)), face=19)
    s2.actors["c1"].hp = s2.actors["c1"].hp_max = 300
    assert reactions.reactions_for(s2.actors["c1"])
    _swing(e2, "c1", face=19)
    assert not reactions.reactions_for(s2.actors["c1"])


def test_a_saved_note_that_a_documented_feat_does_nothing_is_dropped_on_load():
    """Live, 2026-11-22, the owner's saved barbarian (owner-1120-data, frag.json): after
    Extra Rage got its document the pool read 9/15, and the sheet still carried "feat
    'extra rage' is carried as flavour; engine applies nothing" in its notes, and the feat
    line read "+6 pool.rage". The stale note goes on load; the line says "rage a day"."""
    from rules.sheet import from_dict, load_pc, to_dict

    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "barbarian", "level": 1, "feats": ["extra rage"], "ranks": {},
              "notes": "[feat 'extra rage' is carried as flavour; engine applies nothing]"})
    pc = from_dict(d, ref="pc")
    assert "extra rage" not in pc.notes
    from rules.sheet import _document_effect_text

    assert "+6 rage a day" in _document_effect_text(feats_mod.document("extra rage"))
