"""Where a character was before the first turn.

Asked for as "an in depth, many option, background picker so you can spawn in as a
person with history in the world" (2026-09-14). Before it, a character's past was two
fields — `heritage`, which is a people, and `notes`, which is free text nothing reads —
so every PC arrived having done nothing and knowing nobody, and `play/opening.py` had to
introduce them as a stranger because that is all it could truthfully do.

The test that matters here is `test_a_tie_names_somebody_the_world_actually_has`. A
background that says "you were apprenticed to a smith" is a sentence any world could
produce; one that says "you were apprenticed to Ariniel Thorne at the market" is a fact
about *this* one. That difference is the whole feature, and it is the half a personality
quiz does not have.
"""
from __future__ import annotations

import pytest

from rules import backgrounds, creation
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, to_dict
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"


def _pc(background: str = ""):
    built, problems = creation.build({
        "name": "Sera Vane", "race": "human", "class": "rogue", "gender": "woman",
        "background": background, "choices": ["dex"],
        "abilities": {"str": 10, "dex": 16, "con": 12, "int": 13, "wis": 12, "cha": 12},
        "skills": ["stealth", "perception", "diplomacy", "sense motive", "bluff",
                   "acrobatics", "disable device", "sleight of hand", "appraise"],
        "feats": ["Weapon Finesse"]})
    assert not problems, problems
    return from_dict(built["sheet"], ref="pc")


def _table(pc):
    s = Scene(location_id=TOWN)
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party(f"{TOWN}~urban:the-market")
    return s, e


# --- the documents ---------------------------------------------------------------------

def test_every_shipped_background_validates():
    bad = {bid: backgrounds.validate(doc)
           for bid, doc in backgrounds.all_backgrounds().items()}
    bad = {k: v for k, v in bad.items() if v}
    assert not bad, bad


def test_there_are_many_of_them_in_several_groups():
    """"Many option" was the ask. A picker with four entries is a coin toss."""
    assert len(backgrounds.catalogue()) >= 12
    assert len(backgrounds.groups()) >= 4


def test_none_of_them_grants_a_number_a_feat_would_charge_for():
    """1e has no background system. The moment one grants an attack or a save bonus it
    is competing with feats, which are priced — so the ceiling is two skill points, in
    their own bonus type so two backgrounds could never stack."""
    for bid, doc in backgrounds.all_backgrounds().items():
        points = 0
        for m in doc.get("modifiers") or []:
            assert m["type"] == "skill_mod", f"{bid} grants {m['type']}"
            assert m["bonus_type"] == "background", f"{bid} is not a background bonus"
            points += int(m["amount"])
        assert points <= backgrounds.MAX_SKILL_POINTS, f"{bid} grants {points}"


def test_a_background_that_grants_combat_is_refused():
    problems = backgrounds.validate({
        "id": "x", "name": "X", "summary": "s",
        "modifiers": [{"type": "combat_mod", "target": "attack", "amount": 1,
                       "bonus_type": "background"}]})
    assert any("priced territory" in p for p in problems), problems


def test_a_tie_that_would_read_the_same_in_every_world_is_refused():
    """The point of a tie is that it names something only this world has. One with
    neither $who nor $where in its sentence is a line of flavour text."""
    problems = backgrounds.validate({
        "id": "x", "name": "X", "summary": "s",
        "ties": [{"place": "market", "says": "You have sold things before."}]})
    assert any("$who nor $where" in p for p in problems), problems


# --- binding to the world ----------------------------------------------------------------

def test_a_tie_names_somebody_the_world_actually_has():
    """The whole feature. The people come from the same door the quest schemes fill
    their slots from, so a background that knows a trader and a scheme that wants one
    are talking about the same person."""
    pc = _pc("apprenticed")
    _s, e = _table(pc)
    bound = backgrounds.bind(e, pc)
    assert bound, "nothing bound"
    says = bound[0]["says"]
    assert "$who" not in says and "$where" not in says, says
    assert bound[0]["who"], "the tie filled no person"
    cast = {str(c.get("name")) for c in (WORLD.play.get("cast") or [])}
    assert bound[0]["who"] in cast, (
        f"{bound[0]['who']} is not one of this world's people — the tie invented a name")


def test_binding_grants_the_tags_through_the_one_applicator():
    pc = _pc("innkeepers-child")
    _s, e = _table(pc)
    backgrounds.bind(e, pc)
    assert pc.has_state("background.innkeepers-child")
    assert pc.has_state("knows.every-face-here")
    effect = next(x for x in pc.effects if "background.innkeepers-child" in x.tags)
    assert effect.origin.startswith("background:"), "no provenance on the grant"


def test_a_half_filled_sentence_is_never_said():
    """The brief is the half the model is allowed to believe, so a tie whose person the
    world could not supply says nothing rather than saying "$who"."""
    pc = _pc("apprenticed")
    s = Scene(location_id="nowhere-at-all")
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=WORLD)
    for tie in backgrounds.bind(e, pc):
        assert "$" not in tie["says"], tie


def test_two_worlds_give_two_different_histories():
    """A background is a slot until a world fills it."""
    other = loader.load_cached("fixtures/pangrella-campaign.json")
    names = set()
    for seed in (3, 11):
        pc = _pc("bonesetter")
        s = Scene(location_id=TOWN)
        s.add(pc)
        e = Engine(s, Dice(seed=seed), world=other)
        e.place_party(f"{TOWN}~urban:the-market")
        bound = backgrounds.bind(e, pc)
        if bound:
            names.add(bound[0]["who"])
    assert names, "nothing bound in either run"


# --- the sheet ---------------------------------------------------------------------------

def test_the_skill_bonus_is_read_live_and_not_baked_in():
    """Live for the reason the race's modifiers are: a number written into `ranks` at
    creation cannot be taken off again, and a background edited on the bench would
    leave every character who has it carrying the old one."""
    pc = _pc("bonesetter")
    assert [(m.value, m.type) for m in pc._background_mods("skill_mod", "heal")] \
        == [(2, "background")]
    pc.background = ""
    assert pc._background_mods("skill_mod", "heal") == [], "the bonus outlived the past"


def test_it_survives_a_save():
    pc = _pc("gate-watch")
    _s, e = _table(pc)
    pc.background_ties = [b["says"] for b in backgrounds.bind(e, pc)]
    back = from_dict(to_dict(pc), ref="pc")
    assert back.background == "gate-watch"
    assert back.background_ties == pc.background_ties


def test_a_character_with_no_background_is_still_legal():
    """Every character made before this existed has none, and a forge that refused to
    load them would be a migration nobody asked for."""
    pc = _pc("")
    assert pc.background == ""
    assert pc._background_mods("skill_mod", "heal") == []


def test_an_unknown_background_is_refused_with_the_list():
    _built, problems = creation.build({
        "name": "X", "race": "human", "class": "rogue", "gender": "woman",
        "background": "wizard-king", "choices": ["dex"],
        "abilities": {"str": 10, "dex": 16, "con": 12, "int": 13, "wis": 12, "cha": 12},
        "skills": ["stealth"], "feats": []})
    assert any("is not a background" in p for p in problems), problems


# --- the narrator -------------------------------------------------------------------------

def test_the_history_reaches_the_brief():
    """The sheet's two skill points are arithmetic the engine handles. These sentences
    are the half the narrator can use, and a background nobody narrates is a number."""
    from gm import prompts

    pc = _pc("apprenticed")
    s, e = _table(pc)
    pc.background_ties = [b["says"] for b in backgrounds.bind(e, pc)]
    assert pc.background_ties

    brief = prompts.scene_brief(WORLD, s, None, recent=[], turn=1)
    assert "Before this:" in brief, "the brief does not carry the character's past"
    assert pc.background_ties[0] in brief


def test_the_forge_offers_them():
    opts = creation.options()
    assert len(opts["backgrounds"]) == len(backgrounds.catalogue())
    assert opts["background_groups"]
    one = opts["backgrounds"][0]
    for key in ("id", "name", "summary", "line", "group", "ties"):
        assert key in one, key


def test_the_forge_page_renders_the_picker():
    """The API served backgrounds for a while before anything drew them, which is a
    feature only reachable by curl. Checked in the template rather than by driving a
    browser, the way `test_creation.py` checks the forge's other wiring."""
    from pathlib import Path

    from django.conf import settings

    page = Path(settings.BASE_DIR, "play", "templates", "play", "home.html").read_text(
        encoding="utf-8")
    assert "data-crbackground" in page, "nothing in the forge picks a background"
    assert "background_groups" in page, "the groups are not drawn, so it is one long wall"
    # The empty-valued button is how "no background" is chosen, and the handler must
    # read it with `hasAttribute` rather than truthiness or it can never be clicked.
    assert 'data-crbackground=""' in page
    assert "bg.dataset.crbackground" in page
    assert "background: \"\"," in page, "the form has no background field to fill"
