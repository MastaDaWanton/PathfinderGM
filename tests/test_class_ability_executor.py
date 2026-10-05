"""The executor fields the spellcasting lane's powers were waiting on (2026-10-05).

Measured before any of this, against the real documents and the real engine:

- lane 2 wrote twenty-odd domain, bloodline and school powers whose effect named a field
  the one executor (`Engine._use_class_ability`) did not read, and marked each `not_yet`:
  Breath Weapon had no cone (its pool counted down and "the GM narrates the breath"),
  Elemental Blast, Hellfire and Grasp of the Dead had no burst laid away from the user,
  Artificer's Touch had no creature-type limit, Rebuke Death no "below 0 hit points",
  Calming Touch no non-lethal heal, Destructive Smite no damage-only charge, Touch of
  Good no "every skill", and Dazing Touch no Hit Dice limit — a 1st-level cleric dazed a
  4 HD ogre;
- every imported monster's sheet stood at level 1 and `Actor.hit_dice` 1 (an ogre printed
  "4d8+12" answered 1), so a Hit Dice clause read off the sheet would have spared nobody;
- the channel read no tag of the cleric's own (Sun's Blessing, Glory, Death's Embrace);
- `{target}` in a tell raised KeyError and printed its braces, so sixteen tells said "the
  target" and the narrator never learnt who was touched;
- lane 4's list: a smite's first hit was never doubled and never passed DR, and the mark
  outlived its target; a barbarian knocked unconscious kept raging and could talk her way
  through Diplomacy mid-rage; a monk's missed punch left the stunning charge armed.

Every test goes through `Engine.validate` and `Engine.run`, the door the combat bar uses.
"""
from __future__ import annotations

import random

import pytest

from rules import class_abilities as ca
from rules import classes
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.sheet import dr_ignored, from_dict, load_pc, to_dict


class _Rng(random.Random):
    """Every d20 shows `face`; every other die rolls high (its largest face)."""

    def __init__(self, face):
        super().__init__(0)
        self.face = face

    def randint(self, a, b):
        return self.face if b == 20 else b


class Rigged(Dice):
    def __init__(self, face=15):
        super().__init__(0)
        self._rng = _Rng(face)

    @property
    def face(self):
        return self._rng.face

    @face.setter
    def face(self, value):
        self._rng.face = value


def _pc(cls, level, **extra):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": cls, "level": level, "ranks": {}, "armour": "none"})
    d.pop("paths", None)
    d.update(extra)
    actor = from_dict(d, ref="pc")
    classes.apply(actor)
    return actor


def _bloodline(level, pick, variant=""):
    row = {"pick": pick, "level": 1}
    if variant:
        row["variant"] = variant
    return _pc("sorcerer", level, class_choices={"bloodline": {
        "option": "class option", "picks": [row]}})


def _board(pc, *foes, at=(5, 5), face=15, grid=True):
    """A fight on a 20x20 map: `foes` are (template, (x, y)) pairs, refs c1, c2, ..."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc, at=at if grid else None)
    for i, (template, square) in enumerate(foes, start=1):
        s.add(instantiate(template, scene=s, name=f"the {template} {i}"),
              at=square if grid else None)
    if grid:
        s.grid = Grid(width=20, height=20)
    refs = [r for r in s.actors if r != pc.ref]
    s.initiative = [(pc.ref, 30)] + [(r, 10 - i) for i, r in enumerate(refs)]
    s.sides = {"pc": [pc.ref], "them": refs}
    s.round, s.turn = 1, 0
    return s, Engine(s, dice=Rigged(face))


def _use(e, name, to=None, actor="pc"):
    raw = {"op": "use_ability", "actor": actor, "because": "test",
           "params": {"ability": name}}
    if to:
        raw["params"]["to"] = to
    res = e.run(e.validate([raw]))
    return res.outcomes[-1], res


def _swing(e, target="c1", face=15, weapon=None):
    raw = {"op": "attack", "actor": "pc", "target": target, "because": "test", "params": {}}
    if weapon:
        raw["params"]["weapon"] = weapon
    res = e.run(e.validate([raw]))
    while res.awaiting:
        label = res.awaiting["label"]
        res = e.resume(face if label.startswith(("Attack", "Confirm"))
                       else int(res.awaiting["max"]))
    return res


def _hurt(outcome, ref):
    return [x for x in outcome.effects if x.get("kind") == "damage" and x.get("ref") == ref]


# --- shaped areas ---------------------------------------------------------------------------

def test_breath_weapon_had_no_cone_and_now_burns_the_two_in_it_and_not_the_third():
    """"The line or cone: the class-ability grammar has no shaped area yet, so the uses
    are counted and the GM narrates the breath" (lane 2's not_yet). A red dragon's 30-foot
    cone aimed east catches the thugs 10 and 20 feet east and not the one 20 feet behind:
    9d6 fire, Reflex half, one use of one."""
    pc = _bloodline(9, "draconic", "red")
    s, e = _board(pc, ("thug", (7, 5)), ("thug", (9, 5)), ("thug", (1, 5)), face=2)
    out, _ = _use(e, "Breath Weapon", to="c1")
    assert out.status != "refused", out.tell
    assert _hurt(out, "c1") and _hurt(out, "c2") and not _hurt(out, "c3"), out.tell
    assert _hurt(out, "c1")[0]["type"] == "fire"
    assert "30-ft cone catches the thug 1 and the thug 2" in out.tell
    # Live 2026-10-05: told only who was caught, the narrator had the thug behind
    # "thrown back by the heat ... reeling". The one it missed is named in the tell.
    assert "the thug 3 is outside it" in out.tell
    assert "Reflex save" in out.tell and "DC 16" in out.tell      # 10 + 4 + Cha 2
    area = next(x for x in out.effects if x.get("kind") == "area")
    assert area["shape"] == "cone" and area["length_ft"] == 30 and area["cells"] > 0
    assert pc.pool("breath weapon").current == 0
    assert "breathes fire at the thug 1" in out.tell, "{target} named in the tell"


def test_every_dragon_breathes_a_shape_the_map_can_lay():
    """Ten dragons, two shapes, read off the catalogue's own `breath` field through
    `$breath` — never ten copies of the document."""
    shapes = {}
    for colour in ("black", "blue", "green", "red", "white", "brass", "bronze", "copper",
                   "gold", "silver"):
        doc, _ = ca.find(_bloodline(9, "draconic", colour), "breath weapon")
        shapes[colour] = ca.area_of(doc, None)
        assert shapes[colour] is not None, colour
    assert shapes["red"] == {"shape": "cone", "length_ft": 30, "range_ft": 0}
    assert shapes["blue"] == {"shape": "line", "length_ft": 60, "range_ft": 0}


def test_a_blue_dragons_line_catches_who_stands_on_it():
    """A 60-foot line from the corner of the sorcerer's square nearest the thug aimed at
    (`areas.line_cells`, the cast door's rule): from (6,5) through the thug at (8,5) it
    runs on through (11,6), and misses the thug at (8,9)."""
    pc = _bloodline(9, "draconic", "blue")
    s, e = _board(pc, ("thug", (8, 5)), ("thug", (11, 6)), ("thug", (8, 9)), face=2)
    out, _ = _use(e, "Breath Weapon", to="c1")
    assert _hurt(out, "c1") and _hurt(out, "c2") and not _hurt(out, "c3"), out.tell
    assert _hurt(out, "c1")[0]["type"] == "electricity"


def test_with_no_map_the_breath_catches_only_the_one_aimed_at_and_says_so():
    pc = _bloodline(9, "draconic", "red")
    s, e = _board(pc, ("thug", None), ("thug", None), grid=False, face=2)
    out, _ = _use(e, "Breath Weapon", to="c1")
    assert _hurt(out, "c1") and not _hurt(out, "c2")
    assert "no map" in out.tell


def test_elemental_blast_is_a_burst_away_from_the_sorcerer_within_sixty_feet():
    """"An area centred away from you has no field in the class-ability grammar (its
    `radius_ft` is measured around the user)". A 20-ft burst centred on a thug 40 ft off
    catches the thug beside him and not the sorcerer; a failed save leaves vulnerability to
    the element; aimed 70 ft off it is refused and nothing is spent."""
    pc = _bloodline(9, "elemental", "fire")
    s, e = _board(pc, ("thug", (1, 1)), ("thug", (2, 1)), ("thug", (16, 1)), at=(1, 9),
                  face=2)
    far, _ = _use(e, "Elemental Blast", to="c3")
    assert far.status == "refused" and "reaches 60 ft" in far.tell, far.tell
    assert pc.pool("elemental blast").current == 1
    out, _ = _use(e, "Elemental Blast", to="c1")
    assert _hurt(out, "c1") and _hurt(out, "c2") and not _hurt(out, "c3"), out.tell
    assert not _hurt(out, "pc")
    vuln = [x for x in out.effects if x.get("kind") == "vulnerability"]
    assert {x["ref"] for x in vuln} == {"c1", "c2"} and vuln[0]["against"] == "fire"


# --- who it works on --------------------------------------------------------------------------

def test_dazing_touch_dazed_a_4_hd_ogre_and_now_has_no_hold_on_it():
    """"Sparing a creature with more Hit Dice than your level: no field compares Hit Dice
    yet." Measured by the documents: a 1st-level Charm cleric's touch dazed an ogre whose
    stat block prints 4d8+12. Read off the block (an ogre's sheet says level 1), the ogre
    is spared and the thug (1 HD) is not."""
    pc = _pc("cleric", 1, domains=["Charm", "War"])
    s, e = _board(pc, ("ogre", (6, 5)), ("thug", (5, 6)), face=19)
    assert ca.hit_dice_of(s.actors["c1"]) == 4 and s.actors["c1"].hit_dice == 1
    out, _ = _use(e, "Dazing Touch", to="c1")
    assert not s.actors["c1"].has_condition("dazed"), out.tell
    assert "4 Hit Dice, more than 1" in out.tell
    out2, _ = _use(e, "Dazing Touch", to="c2")
    assert s.actors["c2"].has_condition("dazed"), out2.tell
    assert "lays a dazing hand on the thug 2" in out2.tell


def test_blinding_ray_dazzles_what_it_cannot_blind():
    """"Dazzled instead of blinded for a creature of more Hit Dice than your level"."""
    pc = _pc("wizard", 1, class_choices={"arcane school": {
        "option": "class option", "picks": [{"pick": "illusion", "level": 1}]}})
    s, e = _board(pc, ("ogre", (7, 5)), face=19)
    out, _ = _use(e, "Blinding Ray", to="c1")
    ogre = s.actors["c1"]
    assert ogre.has_condition("dazzled") and not ogre.has_condition("blinded"), out.tell


def test_artificers_touch_had_no_creature_type_limit_and_now_works_on_constructs_only():
    """"No field yet limits an attack to a creature type or bypasses hardness." It is
    refused at a man, before anything is spent, naming what it works on; at a clockwork
    soldier (DR 5/adamantine) a 5th-level cleric's touch passes 5 points of the DR."""
    pc = _pc("cleric", 5, domains=["Artifice", "War"])
    s, e = _board(pc, ("thug", (6, 5)), ("clockwork-soldier", (4, 5)), face=19)
    before = pc.pool("artificer's touch").current
    no, _ = _use(e, "Artificer's Touch", to="c1")
    assert no.status == "refused" and "only on constructs" in no.tell, no.tell
    assert pc.pool("artificer's touch").current == before
    out, _ = _use(e, "Artificer's Touch", to="c2")
    hit = _hurt(out, "c2")
    assert hit and hit[0]["amount"] == 6 + 2, out.tell        # 1d6 high + 2, no DR left
    assert dr_ignored(("ignores_dr:5",)) == 5 and dr_ignored(("ignores_dr",)) > 100


def test_rebuke_death_heals_only_the_dying():
    """"No field limits a heal to the dying yet." Refused on an ally standing; a dying ally
    is healed 1d4 + 1 per two levels."""
    pc = _pc("cleric", 4, domains=["Healing", "War"])
    s, e = _board(pc, ("thug", (9, 9)))
    ally = instantiate("guildhand", scene=s, name="Bob")
    s.add(ally, at=(6, 5))
    s.sides["pc"].append(ally.ref)
    standing, _ = _use(e, "Rebuke Death", to=ally.ref)
    assert standing.status == "refused" and "below 0 hit points" in standing.tell
    ally.hp = -3
    ally.add_condition("dying", None)
    out, _ = _use(e, "Rebuke Death", to=ally.ref)
    assert out.status != "refused", out.tell
    assert ally.hp == -3 + 4 + 2


def test_calming_touch_heals_nonlethal_and_lifts_the_three():
    """"The executor heals hit points; a heal aimed only at nonlethal damage has no
    field yet." 1d6 + level of non-lethal back, hit points untouched, and fatigued, shaken
    and sickened lifted through `clear_states`."""
    pc = _pc("cleric", 3, domains=["Community", "War"])
    s, e = _board(pc, ("thug", (9, 9)))
    pc.hp = pc.hp_max - 5
    pc.nonlethal = 12
    for c in ("fatigued", "shaken", "sickened"):
        pc.add_condition(c, None)
    out, _ = _use(e, "Calming Touch")
    assert pc.nonlethal == 12 - (6 + 3) and pc.hp == pc.hp_max - 5, out.tell
    assert not any(pc.has_condition(c) for c in ("fatigued", "shaken", "sickened"))


# --- what the user's own powers add ---------------------------------------------------------

def test_a_sun_clerics_channel_adds_her_level_against_undead_and_glory_raises_the_dc():
    """"The channel document reads no tag of the cleric's yet." Sun's Blessing's level and
    Glory's +2 DC are passive modifiers of the powers, read by the channel's harm mode
    through the funnel (`bonus_from`) — the channel names no domain."""
    sun = _pc("cleric", 3, domains=["Sun", "Glory"])
    s, e = _board(sun, ("skeleton", (6, 5)), face=2)
    plain = _pc("cleric", 3, domains=["War", "Good"])
    s2, e2 = _board(plain, ("skeleton", (6, 5)), face=2)
    for actor in (s.actors["c1"], s2.actors["c1"]):
        actor.hp = actor.hp_max = 60
    out, _ = _use(e, "Channel Energy (harm)")
    base, _ = _use(e2, "Channel Energy (harm)")
    assert _hurt(out, "c1")[0]["amount"] == _hurt(base, "c1")[0]["amount"] + 3, out.tell
    assert "Sun's Blessing adds +3" in out.tell
    dcs = [x["dc"] for o in (out, base) for x in o.effects if x.get("kind") == "save"]
    assert dcs[0] == dcs[1] + 2, dcs


def test_deaths_embrace_heals_the_cleric_in_her_own_negative_burst():
    """"Read by nothing yet: a channel's executor heals the living and harms the undead,
    and asks no tag of the cleric herself." With Death's Embrace (8th) the negative burst
    that harms the living heals her instead; without it she is left out of it."""
    pc = _pc("cleric", 8, domains=["Death", "War"])
    assert pc.has_state("channel.negative.heals")
    s, e = _board(pc, ("thug", (6, 5)), face=2)
    pc.hp = 5
    out, _ = _use(e, "Channel Energy (harm the living)")
    assert pc.hp > 5 and _hurt(out, "c1"), out.tell
    assert "mends Kesst Vayr instead" in out.tell


# --- every skill ------------------------------------------------------------------------------

def test_touch_of_good_reaches_every_skill_now():
    """"An effect's modifier names one skill, and there is no 'every skill' target yet."
    A skill_mod aimed at `all` (Foundry PF1's `skills` change target) reaches Stealth and
    Diplomacy alike, for the round it lasts."""
    pc = _pc("cleric", 4, domains=["Good", "War"])
    s, e = _board(pc, ("thug", (9, 9)))
    ally = instantiate("guildhand", scene=s, name="Bob")
    s.add(ally, at=(6, 5))
    s.sides["pc"].append(ally.ref)
    before = {k: sum(m.value for m in ally.skill_modifiers(k)) for k in ("stealth", "diplomacy")}
    out, _ = _use(e, "Touch of Good", to=ally.ref)
    after = {k: sum(m.value for m in ally.skill_modifiers(k)) for k in ("stealth", "diplomacy")}
    assert after == {k: v + 2 for k, v in before.items()}, out.tell


# --- charges ----------------------------------------------------------------------------------

def test_destructive_smite_rides_the_next_melee_blow_and_a_miss_spends_it():
    """"The damage-only charge on a single attack has no field yet." The morale bonus is in
    the next melee hit's damage; a miss wastes it."""
    pc = _pc("cleric", 6, domains=["Destruction", "War"])
    s, e = _board(pc, ("thug", (6, 5)))
    s.actors["c1"].hp = s.actors["c1"].hp_max = 200
    _use(e, "Destructive Smite")
    res = _swing(e, face=18)
    tells = " ".join(o.tell for o in res.outcomes)
    assert "lands with the blow" in tells, tells
    assert not any((x.payload or {}).get("charge") for x in pc.effects)
    _use(e, "Destructive Smite")
    res = _swing(e, face=1)
    tells = " ".join(o.tell for o in res.outcomes)
    assert "Destructive Smite is spent on the miss" in tells, tells
    assert not any((x.payload or {}).get("charge") for x in pc.effects)


def test_a_missed_stunning_fist_is_wasted_and_the_next_punch_does_not_stun():
    """Lane 4's not_yet: "A miss spends the use and leaves the charge until the round's
    end; a second unarmed hit the same round still lands it." The book: "if the attack roll
    misses, the attempt is wasted"."""
    pc = _pc("monk", 8)
    pc.abilities["wis"] = 30
    pc.equipped = "unarmed"
    s, e = _board(pc, ("thug", (6, 5)))
    s.actors["c1"].hp = s.actors["c1"].hp_max = 200
    _use(e, "Stunning Fist")
    tells = " ".join(o.tell for o in _swing(e, face=1).outcomes)
    assert "spent on the miss" in tells, tells
    _swing(e, face=19)
    assert not s.actors["c1"].has_condition("stunned")


# --- smite ------------------------------------------------------------------------------------

def test_a_smites_first_hit_on_undead_is_doubled_and_passes_dr_and_the_second_is_not():
    """Lane 4's not_yet: "the first hit's doubled damage" and "bypassing the target's
    damage reduction". A skeleton (undead, DR 5/bludgeoning) hit with a longsword: the
    first blow carries level x2 and no DR; the second carries level once."""
    pc = _pc("paladin", 4)
    pc.weapons = ["longsword"]
    pc.equipped = "longsword"
    s, e = _board(pc, ("skeleton", (6, 5)))
    skel = s.actors["c1"]
    skel.hp = skel.hp_max = 300
    _use(e, "Smite Evil", to="c1")
    first = sum(m.value for m in pc.damage_modifiers("longsword", defender=skel))
    res = _swing(e, face=15)
    tells = " ".join(o.tell for o in res.outcomes)
    assert "strikes doubly hard" in tells and "past the skeleton 1's DR 5" in tells, tells
    second = sum(m.value for m in pc.damage_modifiers("longsword", defender=skel))
    assert first == second + 4
    thug = instantiate("thug", scene=s, name="the bystander")
    assert sum(m.value for m in pc.damage_modifiers("longsword", defender=thug)) \
        == second - 4, "the doubled blow was for undead, the plain smite for its mark"


def test_a_smite_ends_when_its_mark_dies():
    """Lane 4's not_yet: "Ending on the target's death: the mark stays, inert, until the
    paladin rests." The book: "until the target of the smite is dead"."""
    pc = _pc("paladin", 4)
    s, e = _board(pc, ("thug", (6, 5)), ("thug", (4, 5)))
    _use(e, "Smite Evil", to="c1")
    assert any(x.name == "Smite Evil" for x in pc.effects)
    s.actors["c1"].die("test")
    res = e.run(e.validate([{"op": "check", "actor": "pc", "because": "t",
                             "params": {"skill": "perception", "dc": 5}}]))
    while res.awaiting:
        res = e.resume(10)
    assert not any(x.name == "Smite Evil" for x in pc.effects)
    assert any("Smite Evil ends" in o.tell for o in res.outcomes)


# --- rage -------------------------------------------------------------------------------------

def test_rage_ends_when_the_barbarian_falls_and_leaves_her_fatigued():
    """"Falling unconscious does not end the rage on its own." It does now, at the end of
    the batch that put her down, and the fatigue follows."""
    pc = _pc("barbarian", 5)
    s, e = _board(pc, ("thug", (6, 5)))
    _use(e, "Rage")
    assert pc.has_state("buff.stance.rage")
    pc.hp = -2
    pc.add_condition("dying", None)
    res = e.run(e.validate([{"op": "check", "actor": "c1", "because": "t",
                             "params": {"skill": "perception", "dc": 5}}]))
    assert not pc.has_state("buff.stance.rage")
    assert any("Rage ends" in o.tell for o in res.outcomes), [o.tell for o in res.outcomes]


def test_a_raging_barbarian_cannot_talk_but_can_threaten():
    """"The skills rage forbids ... are not refused while it holds." Diplomacy (Cha) is
    refused, Intimidate (Cha, excepted) rolls."""
    pc = _pc("barbarian", 5)
    s, e = _board(pc, ("thug", (6, 5)))
    _use(e, "Rage")

    def check(skill):
        res = e.run(e.validate([{"op": "check", "actor": "pc", "because": "t",
                                 "params": {"skill": skill, "dc": 10}}]))
        while res.awaiting:
            res = e.resume(10)
        return res.outcomes[0]
    talk = check("diplomacy")
    assert "Nothing is rolled for Diplomacy" in talk.tell and not talk.rolls, talk.tell
    threat = check("intimidate")
    assert "Nothing is rolled" not in threat.tell


# --- the grammar ------------------------------------------------------------------------------

@pytest.mark.parametrize("bad,said", [
    ({"area": "a big cone"}, "30-foot cone"),
    ({"area": {"shape": "sphere", "ft": 20}}, "shape"),
    ({"hit_dice": {"over": {}}}, "hit_dice"),
    ({"roll": {"count": 1, "die": 6, "as": "harm"}}, "heal_nonlethal"),
    ({"effect": {"on": "failed"}}, "needs a `save`"),
    ({"charge": {"category": "melee"}}, "arms nothing"),
    ({"self": {"ends_when": {"owner": ["state.down"]}}}, "ends_when"),
    ({"self": {"forbids": {"skills": {"abilities": ["luck"]}}}}, "luck"),
    ({"tell": "{name} hits {foe} for 6."}, "{foe}"),
])
def test_a_field_nobody_can_read_is_refused_on_load_with_the_fix(bad, said):
    doc = {"key": "x", "name": "X", "source": "s", **bad}
    problems = ca.validate_documents({"paladin": {"abilities": [doc]}})
    assert any(said in p for p in problems), problems


def test_every_shipped_document_still_validates():
    assert ca.validate_documents() == []
