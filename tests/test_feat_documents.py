"""Stage 8b: a feat's number comes from a document, through the funnel a ring uses.

What the recon measured (docs/stage-8-plan.md, "What the maps corrected"): the
hand-written table in rules/tables.py held sixteen feats; fourteen were applied by bare
`Modifier`s appended inside the sheet's builders — untyped (Dodge's `dodge` sat in the
table and was dropped at the append), never through `_buff_mods`, never removable by
removing an effect — and two (Toughness, Point-Blank Shot) were read by nothing while the
sheet page printed "bonus hit points" for a feat that added none.

Now content/feats/mechanics/*.json carries the documents, `rules.feats.document`
resolves a sheet string to one, and `Actor._feat_mods` reads them live inside
`_buff_mods` the way worn gear is read off the slots. Nothing is saved; the feat list is
the store.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from rules import classbuilder, feats
from rules.sheet import from_dict, load_pc, to_dict, validate
from rules.tables import CONDITIONS


def _kesst(*held: str):
    pc = load_pc("fixtures/pc-kesst.json")
    pc.feats = list(held)
    return pc


def _sources(mods) -> list[str]:
    return [m.source for m in mods]


# --- the file -----------------------------------------------------------------------------

def test_the_shipped_documents_load_and_validate():
    docs = feats.documents()
    assert {"stealthy", "alertness", "acrobatic", "deceitful", "persuasive",
            "improved-initiative", "lightning-reflexes", "iron-will", "great-fortitude",
            "dodge", "toughness", "point-blank-shot"} <= set(docs)
    assert classbuilder.validate_feat_documents(docs) == []


def test_a_document_is_reached_by_name_id_or_targeted_string():
    """Four normalisers used to disagree; sheets store lower-cased names, feats.json is
    keyed by id, and "Weapon Focus (rapier)" has to reach the same feat as
    "weapon-focus"."""
    for raw in ("Iron Will", "iron will", "iron-will", "IRON WILL (anything)"):
        doc = feats.document(raw)
        assert doc and doc["id"] == "iron-will" and doc["name"] == "Iron Will", raw
    assert feats.document("iron will (anything)")["target"] == "anything"
    assert feats.document("no such feat") is None
    bare = feats.document("weapon focus")
    assert bare and bare["target"] is None and feats.needs_target(bare)
    assert feats.document("weapon focus (rapier)")["target"] == "rapier"


def test_the_validator_names_the_fix():
    """Unknown keys are refused rather than ignored: `effectspec.validate` never
    rejected one, and a silently ignored field is a feat that quietly does less."""
    bad = classbuilder.validate_feat_document(
        "dodge", {"modifiers": [{"type": "combat_mod", "target": "ac", "amount": 1,
                                 "frobnicate": 2}], "colour": "blue"})
    text = " ".join(bad)
    assert "unknown key(s) frobnicate" in text and "unknown field(s) colour" in text
    assert "A modifier carries:" in text
    assert classbuilder.validate_feat_document(
        "toughness", {"modifiers": [{"type": "combat_mod", "target": "hp_maxx",
                                     "amount": 3}]})
    assert classbuilder.validate_feat_document(
        "toughness", {"modifiers": [{"type": "combat_mod", "target": "hp_max"}]})
    wrong_id = classbuilder.validate_feat_documents({"not-a-feat": {"modifiers": []}})
    assert wrong_id and "keyed by id" in wrong_id[0]


# --- through the funnel -------------------------------------------------------------------

def test_a_feat_term_names_the_feat_and_arrives_through_the_funnel():
    """Before: a bare Modifier appended in `skill_modifiers` from the Python table.
    After: the same label, from the document, through `_buff_mods` — so removing the
    feat removes the term (law 2), the way taking a ring off does."""
    pc = _kesst("stealthy")
    assert "Stealthy" in _sources(pc.skill_modifiers("stealth"))
    assert "Stealthy" in _sources(pc._buff_mods("skill_mod", "stealth"))
    before = sum(m.value for m in pc.skill_modifiers("stealth"))
    pc.feats = []
    assert "Stealthy" not in _sources(pc.skill_modifiers("stealth"))
    assert sum(m.value for m in pc.skill_modifiers("stealth")) == before - 2


def test_saves_initiative_and_ac_read_their_documents():
    pc = _kesst("iron will", "lightning reflexes", "great fortitude",
                "improved initiative", "dodge")
    assert "Iron Will" in _sources(pc.save_modifiers("will"))
    assert "Lightning Reflexes" in _sources(pc.save_modifiers("ref"))
    assert "Great Fortitude" in _sources(pc.save_modifiers("fort"))
    init = next(m for m in pc.initiative_modifiers() if m.source == "Improved Initiative")
    assert init.value == 4
    dodge = next(m for m in pc.ac_modifiers() if m.source == "Dodge")
    assert dodge.value == 1 and dodge.type == "dodge"       # typed at last


def test_a_dodge_bonus_is_lost_with_dex_to_ac():
    """1e: "A condition that makes you lose your Dex bonus to AC also makes you lose
    the benefits of this feat." Twenty-four shipped dodge feats had no reader for it."""
    pc = _kesst("dodge")
    assert "Dodge" in _sources(pc.ac_modifiers())
    key = next(k for k, row in CONDITIONS.items() if row.get("lose_dex_to_ac"))
    pc.add_condition(key)
    assert pc.loses_dex_to_ac
    assert "Dodge" not in _sources(pc.ac_modifiers())


def test_toughness_lands_on_hp_max_and_round_trips_twice():
    """Toughness sat in the table with `hp_bonus: True` and no reader; the sheet page
    printed "bonus hit points" for a feat adding none. Now `hp_max` carries the
    document's `3 + max(0, hit_dice - 3)` — and `set_hp_max` subtracts it, because
    every one-round-trip test in this codebase passed while a total that was read but
    not subtracted grew by +3 per reload (Thor 23 → 37)."""
    pc = _kesst()
    plain = pc.hp_max
    pc.feats = ["toughness"]
    assert pc.hp_max == plain + 3
    once = from_dict(to_dict(pc))
    twice = from_dict(to_dict(once))
    assert once.hp_max == plain + 3 and twice.hp_max == plain + 3
    assert twice.hp_base == pc.hp_base
    pc.feats = []
    assert pc.hp_max == plain


def test_the_same_feat_twice_yields_nothing_more():
    """1e: "If a character has the same feat more than once, its benefits do not
    stack unless indicated otherwise." The verifiers measured +12 against +11 for a
    sheet listing Iron Will twice. Weapon Focus on two different weapons is two."""
    pc = _kesst("iron will", "Iron Will", "iron-will")
    assert [m.value for m in pc.save_modifiers("will") if m.source == "Iron Will"] == [2]
    b = _borin()
    b.feats = ["weapon focus (longsword)", "weapon focus (dagger)", "weapon focus (longsword)"]
    assert "Weapon Focus" in _sources(b.attack_modifiers("longsword"))
    assert "Weapon Focus" in _sources(b.attack_modifiers("dagger"))
    assert _sources(b.attack_modifiers("longsword")).count("Weapon Focus") == 1


def test_a_save_from_before_the_channel_finally_receives_its_toughness():
    """The verifiers measured: Kesst plain is hp_max 9 / hp_base 8; a save written
    before stage 8 with `toughness` in feats and the printed total 9 loaded as
    hp_max 9 / hp_base 5 — the new inverse subtracted a channel the old total never
    held, the holder never got the +3, and removing the feat left them at 6. The
    saved shape now carries `hp_channels`; a dict without it is the old convention."""
    old = to_dict(_kesst())                    # hp_max 9, no toughness, marker present
    plain = old["hp_max"]
    old["feats"] = ["toughness"]
    old.pop("hp_channels")                     # a save from before the channel
    a = from_dict(old)
    assert a.hp_max == plain + 3 and a.hp_base == _kesst().hp_base
    a.feats = []
    assert a.hp_max == plain
    # A save written since carries the marker and round-trips as it is.
    fresh = _kesst("toughness")
    again = from_dict(to_dict(fresh))
    assert "hp_channels" in to_dict(fresh) and again.hp_max == fresh.hp_max == plain + 3


def test_the_maximum_is_itemised_so_toughness_names_itself_like_a_ring():
    from rules.sheet import full_sheet

    pc = _kesst("toughness")
    terms = full_sheet(pc)["defense"]["hp"]["max_terms"]["terms"]
    assert any(t.get("source") == "Toughness" and t.get("value") == 3 for t in terms)
    assert sum(t.get("value", 0) for t in terms) == pc.hp_max


def test_a_formula_over_the_sheet_does_not_recurse():
    """`resources.variables` was eager and read `hp_max` before any formula was walked:
    `hp_max → _feat_mods → evaluate → variables → hp_max …` on every hit-point read."""
    pc = _kesst("toughness")
    assert isinstance(pc.hp_max, int) and isinstance(pc.ability_mod("con"), int)
    assert isinstance(pc.hp, int)


def test_a_printed_stat_block_keeps_its_number():
    """A flat-stat creature's printed total already includes its feats; every feat
    loop this replaced sat under the `else` of the flat branch."""
    pc = _kesst("iron will", "improved initiative")
    pc.flat_saves = {"will": 0}
    pc.flat_initiative = 0
    assert sum(m.value for m in pc.save_modifiers("will")) == 0
    assert sum(m.value for m in pc.initiative_modifiers()) == 0


def test_a_conditional_term_is_dropped_never_applied():
    """Point-Blank Shot's +1 is "at ranges of up to 30 feet"; the funnel carries no
    range yet, so the term is dropped — applying it to a longsword would be the bug.
    The document says so under `not_yet`."""
    pc = _kesst("point-blank shot")
    assert "Point-Blank Shot" not in _sources(pc.attack_modifiers("rapier"))
    assert "Point-Blank Shot" not in _sources(pc.damage_modifiers("rapier"))
    assert feats.document("point-blank shot")["not_yet"]


def test_validate_no_longer_calls_a_documented_feat_flavour():
    """`validate()` wrote "carried as flavour; engine applies nothing" onto 1,458 feats,
    three families of which the engine applied. A feat with a document is applied."""
    pc = _kesst("toughness", "dodge", "not a real feat")
    validate(pc)
    assert "feat 'toughness'" not in pc.notes and "feat 'dodge'" not in pc.notes
    assert "feat 'not a real feat' is carried as flavour" in pc.notes


def test_the_sheet_page_says_what_a_documented_feat_applies():
    """The page printed "bonus hit points" for Toughness while the engine added none.
    The text is generated from the document now, so it cannot drift from the read."""
    from rules.sheet import full_sheet

    pc = _kesst("toughness", "stealthy", "point-blank shot", "not a real feat")
    rows = {row["name"]: row for row in full_sheet(pc)["feats"]}
    assert rows["Toughness"]["applied"] and "hit_dice" in rows["Toughness"]["effect"]
    assert rows["Stealthy"]["applied"] and "+2 stealth" in rows["Stealthy"]["effect"]
    pbs = rows["Point-Blank Shot"]
    assert pbs["applied"] and "Not yet:" in pbs["effect"] and "when" in pbs["effect"]
    assert not rows["not a real feat"]["applied"]


# --- 8c: the branches, and the grammar that retired them ---------------------------------

def _borin():
    return load_pc("fixtures/pc-borin.json")


def test_weapon_focus_binds_to_the_named_weapon_and_no_other():
    """`has_feat("weapon focus", key)` matched a target of None against every weapon;
    the literal +1 in `attack_modifiers` never read the table. Now `scope.weapon:
    "$target"` binds the term to the parenthetical, through the funnel."""
    b = _borin()                                   # "weapon focus (longsword)"
    assert "Weapon Focus" in _sources(b.attack_modifiers("longsword"))
    assert "Weapon Focus" not in _sources(b.attack_modifiers("dagger"))
    assert "Weapon Focus" not in _sources(b.attack_modifiers("shortbow"))


def test_a_bare_scoped_feat_is_bound_to_the_weapon_in_hand_on_load():
    """The forge wrote every Weapon Focus untargeted (`creation.py` collected no
    weapon); tools/prove_build.py:344 and two tests seeded exactly that. Under the
    documents a bare one would be +1 with nothing, silently — so on load it is bound
    to the equipped weapon and the sheet says so; never dropped."""
    a = from_dict({"name": "x", "kind": "pc", "class": "fighter", "level": 1,
                   "abilities": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")},
                   "hp": 10, "feats": ["weapon focus"], "weapons": ["longsword"],
                   "equipped": "longsword"})
    assert a.feats == ["weapon focus (longsword)"]
    assert "bound to the longsword" in a.notes
    assert "Weapon Focus" in _sources(a.attack_modifiers("longsword"))
    twice = from_dict(to_dict(a))                  # the note is not appended again
    assert twice.notes.count("bound to the longsword") == 1


def test_power_attack_comes_from_the_document_with_the_weapon_in_hand():
    """`tables.power_attack_terms` is deleted; the three rungs are formulas on the
    document, conditional on the weapon: one-handed +2 per step, light +1, two-handed
    +3 (test_engine pins BAB 8 two-handed at +9). Melee only — the shortbow used to
    take −1/+2 — and never without the choice."""
    b = _borin()                                   # BAB 1: one step
    atk = {m.source: m.value for m in b.attack_modifiers("longsword", power_attack=True)}
    dmg = {m.source: m.value for m in b.damage_modifiers("longsword", power_attack=True)}
    assert atk["Power Attack"] == -1 and dmg["Power Attack"] == 2
    light = [m.value for m in b.damage_modifiers("dagger", power_attack=True)
             if m.source == "Power Attack"]
    assert light == [1]
    assert "Power Attack" not in _sources(b.attack_modifiers("shortbow", power_attack=True))
    assert "Power Attack" not in _sources(b.damage_modifiers("shortbow", power_attack=True))
    assert "Power Attack" not in _sources(b.attack_modifiers("longsword"))
    assert "Power Attack" in _sources(b.cmb_modifiers("trip", power_attack=True))
    assert b.can_power_attack() is None
    b.abilities["str"] = 12
    assert "Str" in (b.can_power_attack() or "")   # the prerequisite, from feats.json
    b.feats = []
    assert "does not have Power Attack" in b.can_power_attack()


def test_weapon_finesse_is_a_substitution_that_applies_only_when_it_helps():
    pc = _kesst("weapon finesse")                  # Dex above Str
    assert pc.ability_mod("dex") > pc.ability_mod("str")
    assert "Dex (Finesse)" in _sources(pc.attack_modifiers("rapier"))
    pc.abilities["str"], pc.abilities["dex"] = 16, 12
    assert "Str" in _sources(pc.attack_modifiers("rapier"))
    assert "Dex (Finesse)" not in _sources(pc.attack_modifiers("rapier"))


def test_proficiency_is_a_tag_and_the_feat_is_one_weapon_per_taking():
    """The old suffix match granted the whole category from `split()[0]`; the feat
    is 'the selected weapon'. Class lists become tags too, so `has_state` is the one
    door for stored and standing tags."""
    pc = _kesst()
    assert pc.has_state("proficient.weapon.rapier") and pc.is_proficient("rapier")
    base = {"name": "x", "kind": "pc", "class": "wizard", "level": 1,
            "abilities": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")},
            "hp": 6, "weapons": ["longsword", "greatsword"], "equipped": "longsword"}
    wizard = from_dict(base)
    assert not wizard.is_proficient("longsword")
    assert any(m.value < 0 and "not proficient" in m.source
               for m in wizard.attack_modifiers("longsword"))
    armed = from_dict({**base, "feats": ["martial weapon proficiency (longsword)"]})
    assert armed.is_proficient("longsword") and not armed.is_proficient("greatsword")
    assert "proficient.weapon.longsword" in armed.standing_tags()


def test_combat_reflexes_is_a_budget_from_the_document():
    from rules import reactions

    pc = _kesst()
    dex = max(0, pc.ability_mod("dex"))
    assert reactions.budget_for(pc) == 1
    pc.feats = ["combat reflexes"]
    assert reactions.budget_for(pc) == 1 + dex
    pc.feats = ["mythic combat reflexes"]           # the substring match took this too
    assert reactions.budget_for(pc) == 1


def test_improved_trip_reaches_cmb_and_cmd_for_that_manoeuvre_only():
    """The f-string branch reached CMB alone; 1e grants both. Twenty documents,
    generated over MANEUVERS, each scoped to its manoeuvre."""
    pc = _kesst("improved trip")
    assert "Improved Trip" in _sources(pc.cmb_modifiers("trip"))
    assert "Improved Trip" in _sources(pc.cmd_modifiers(maneuver="trip"))
    assert "Improved Trip" not in _sources(pc.cmb_modifiers("disarm"))
    assert "Improved Trip" not in _sources(pc.cmd_modifiers())


def test_the_forge_asks_for_the_weapon_a_scoped_feat_binds_to():
    from rules import creation
    from tests.test_creation import spec

    _, problems = creation.build(spec(feats=["power attack", "weapon focus"]))
    assert any("Weapon Focus needs a weapon" in p and '"target"' in p for p in problems)
    built, problems = creation.build(
        spec(feats=["power attack", {"id": "weapon-focus", "target": "longsword"}]))
    assert problems == []
    assert "weapon focus (longsword)" in built["sheet"]["feats"]


# --- the ratchet --------------------------------------------------------------------------

# The sixteen the plan counted, and the three families it missed, each with where the
# branch was and what retired it. Listed so the count means something: a new
# `has_feat(` or a feat name in a builder fails the test below.
_RETIRED = {
    "stealthy/alertness/acrobatic/deceitful/persuasive": "skill_modifiers table loop → skill_mod documents",
    "lightning reflexes/iron will/great fortitude": "save_modifiers table loop → save_mod documents",
    "improved initiative": "initiative_modifiers table loop → combat_mod initiative",
    "dodge": "ac_modifiers table loop, emitted untyped → bonus_type dodge, lost with Dex",
    "toughness": "in the table, read by nothing → formula on the hp_max target",
    "point-blank shot": "in the table, read by nothing → when.range_ft, dropped until plumbed",
    "weapon focus": "literal +1 in attack_modifiers → scope.weapon $target",
    "weapon specialization": "literal +2 in damage_modifiers → scope.weapon $target",
    "weapon finesse": "_uses_finesse name match → attack_ability with if_better",
    "power attack": "tables.power_attack_terms + can_power_attack prerequisites → choice + formulas",
    "improved/greater <maneuver>": "f-string has_feat in cmb_modifiers → twenty scoped documents, CMB and CMD",
    "* weapon proficiency": "suffix match in is_proficient → proficient.weapon.$target tags",
    "combat reflexes": "substring match in reactions.budget_for → budget formula",
}


def test_no_feat_is_applied_by_name_anywhere_in_the_rules():
    """The sixth channel: `for feat in self.feats: bonus = FEATS.get(...)` appended
    inside four builders, five `has_feat` literals, a suffix match, a substring match,
    and a table nothing else read. Zero now."""
    def code(path) -> str:              # docstrings and comments may still tell the story
        src = re.sub(r'"""(?:.|\n)*?"""', "", Path(path).read_text(encoding="utf-8"))
        return "\n".join(re.sub(r"#.*$", "", line) for line in src.splitlines())

    sheet = code("rules/sheet.py")
    assert "for feat in self.feats" not in sheet and "has_feat(" not in sheet
    for path in Path("rules").glob("*.py"):
        src = code(path)
        assert "FEATS" not in src.replace("_FEATS", ""), path
        assert "power_attack_terms" not in src, path
    assert "combat reflexes" not in code("rules/reactions.py").lower()
    assert len(_RETIRED) == 13
