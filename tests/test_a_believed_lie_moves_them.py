"""A lie about who you are moves how the listener feels (owner ruling, 2026-10-01).

The owner's words: "bluff should move an attitude if i bluff that i am the king of a
nation for example that success would immediately change the way that person felt about
me in the positive or perhaps negative if they hated the rich and powerful. and a failure
should be a small negative because I've just lied to them." And the answers that settled
the shape: a new rank trait decides who hates the high-born; the swing is Diplomacy's
size; it holds until they learn the truth; a caught lie costs a little regard and leaves
them wary, at -10 on the next lie (Ultimate Intrigue p.182).

Before this, `rules/attitude.py` kept Bluff off the track as a matter of book fidelity,
and `test_attitude.py` asserted it: a believed claim to be the king of a nation left the
listener exactly where they stood, and so did a lie they saw straight through.
"""
from __future__ import annotations

import pytest

from rules import attitude, bluff, lives, states
from rules.bestiary import instantiate
from rules.dice import Dice, Modifier
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"
MARKET = f"{TOWN}~urban:the-market"


def _table(*, sees: int):
    """Kesst and Grix in the market. `sees` is Grix's Sense Motive, set outright so the
    test decides whether the lie is believed: -40 believes anything, +40 nothing."""
    scene = Scene(location_id=TOWN)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=7), world=WORLD)
    engine.place_party(MARKET)
    who = scene.add(instantiate("thug", scene=scene, name="Grix"))
    real = who.skill_modifiers

    def skill_modifiers(skill, *a, **k):
        if skill == "sense motive":
            return [Modifier(sees, "set by the test")]
        return real(skill, *a, **k)

    who.skill_modifiers = skill_modifiers
    return scene, engine, who


def _lie(engine, who, *, claim: str = "rank", lie: str = "far_fetched", face: int = 15):
    opposed = {"ref": who.ref, "skill": "sense motive", "lie": lie}
    if claim is not None:
        opposed["claim"] = claim
    res = engine.run(engine.validate(
        [{"op": "check", "actor": "pc", "because": "claiming to be the king",
          "params": {"skill": "bluff", "opposed_by": opposed}}], origin="author:test"))
    if res.awaiting:
        res = engine.resume(face)
    return next(o for o in res.outcomes if o.op == "check")


@pytest.fixture
def feels(monkeypatch):
    """Set how the listener feels about rank (0 deferential … 100 resentful)."""
    def set_(score: int):
        monkeypatch.setattr(bluff, "_disposition", lambda scene, listener, axis: score)
    return set_


# --- believed ---------------------------------------------------------------------------

def test_a_believed_claim_to_be_king_warms_somebody_who_looks_up_to_rank(feels):
    """The owner's own example, the positive half."""
    feels(20)
    _scene, engine, who = _table(sees=-40)
    out = _lie(engine, who)
    assert out.verdict == "success"
    want = attitude.moved(attitude.DEFAULT, attitude.steps_for(out.margin))
    assert attitude.of(who) == want and want != attitude.DEFAULT
    assert "looked up to the high-born" in out.tell
    assert "warms" in out.tell


def test_a_believed_claim_to_be_king_cools_somebody_who_hates_the_high_born(feels):
    """"or perhaps negative if they hated the rich and powerful" — the other half."""
    feels(85)
    _scene, engine, who = _table(sees=-40)
    out = _lie(engine, who)
    assert out.verdict == "success"
    want = attitude.moved(attitude.DEFAULT, -attitude.steps_for(out.margin))
    assert attitude.of(who) == want
    assert attitude.step_of(want) < attitude.step_of(attitude.DEFAULT)
    assert "no love for the high-born" in out.tell and "cools" in out.tell


def test_the_swing_is_diplomacys_size_and_never_a_number_on_the_page(feels):
    """Diplomacy's steps from the margin, two at most, and the tell says how they feel,
    never by how many steps (the third law)."""
    feels(20)
    _scene, engine, who = _table(sees=-40)
    out = _lie(engine, who, face=20)
    assert attitude.step_of(attitude.of(who)) - attitude.step_of(attitude.DEFAULT) \
        == min(2, attitude.steps_for(out.margin))
    assert "step" not in out.tell.split(":", 1)[-1]


def test_it_holds_until_they_learn_the_truth(feels):
    """No clock: the step is held until dismissed, under the lie's own source, so the day
    a discovery is built removing that source is the whole undo. Regard follows the step,
    so a Diplomacy shift that later clears the tag does not undo what they believe."""
    feels(20)
    _scene, engine, who = _table(sees=-40)
    _lie(engine, who)
    held = [e for e in who.effects if e.source == "lie:rank"]
    assert held and all(e.duration == "until-dismissed" for e in held)
    assert who.has_state(states.believes_claim_tag("rank"))
    assert attitude.band_of(attitude.regard_of(who)) == attitude.of(who)
    who.remove_effects(source="lie:rank")
    assert not who.has_state(states.believes_claim_tag("rank"))


def test_the_same_claim_believed_twice_moves_them_once(feels):
    feels(20)
    _scene, engine, who = _table(sees=-40)
    _lie(engine, who)
    after_first = attitude.of(who)
    out = _lie(engine, who)
    assert out.verdict == "success"
    assert attitude.of(who) == after_first


def test_a_cover_story_moves_nobody(feels):
    """A merchant from the coast lays claim to no standing; believed, it is just believed."""
    feels(20)
    _scene, engine, who = _table(sees=-40)
    out = _lie(engine, who, claim="", lie="believable")
    assert out.verdict == "success"
    assert attitude.of(who, default="") == ""


def test_a_name_does_not_dazzle_somebody_who_resents_the_powerful(feels):
    """Renown to a resentful listener: believed, and unmoved — said in words."""
    feels(85)
    _scene, engine, who = _table(sees=-40)
    out = _lie(engine, who, claim="renown")
    assert attitude.of(who, default="") == ""
    assert "unmoved" in out.tell


def test_only_the_players_lies_move_anybody(feels):
    """Attitudes are towards the party, as with `_sway`."""
    feels(20)
    scene, engine, who = _table(sees=-40)
    liar = scene.add(instantiate("thug", scene=scene, name="Vosk"))
    res = engine.run(engine.validate(
        [{"op": "check", "actor": liar.ref, "because": "a lie",
          "params": {"skill": "bluff", "opposed_by": {
              "ref": who.ref, "skill": "sense motive", "lie": "far_fetched",
              "claim": "rank"}}}], origin="author:test"))
    assert res.outcomes
    assert attitude.of(who, default="") == ""


# --- caught -----------------------------------------------------------------------------

def test_a_caught_lie_is_a_small_loss_and_they_become_wary(feels):
    """"a failure should be a small negative because I've just lied to them": the regard
    a bad Diplomacy failure costs, and the listener remembers."""
    feels(20)
    _scene, engine, who = _table(sees=40)
    before = attitude.regard_of(who)
    out = _lie(engine, who, face=1)
    assert out.verdict == "failure"
    assert attitude.regard_of(who) == before - attitude.REGARD_LOST_ON_FAILURE
    assert who.has_state(states.CAUGHT_LYING)
    assert "will not take your word lightly" in out.tell


def test_the_next_lie_to_somebody_who_caught_you_is_at_minus_ten(feels):
    """Ultimate Intrigue p.182: a later lie to a target who found the first one out
    "takes a similar penalty as if she had failed to deceive the target (either a -10
    penalty ...)". On the roll, by name, so the player sees why."""
    feels(20)
    _scene, engine, who = _table(sees=40)
    _lie(engine, who, face=1)
    out = _lie(engine, who, face=1)
    terms = [m for r in out.rolls for m in (r.get("modifiers") if isinstance(r, dict)
                                              else getattr(r, "modifiers", [])) or []]
    said = [str(m.get("source") if isinstance(m, dict) else getattr(m, "source", ""))
            for m in terms]
    values = [int(m.get("value") if isinstance(m, dict) else getattr(m, "value", 0))
              for m in terms]
    assert any("caught you lying" in s for s in said), said
    assert bluff.WARY_PENALTY in values


def test_caught_twice_is_still_one_wariness(feels):
    feels(20)
    _scene, engine, who = _table(sees=40)
    _lie(engine, who, face=1)
    _lie(engine, who, face=1)
    assert len([e for e in who.effects if states.CAUGHT_LYING in (e.tags or ())]) == 1


# --- what the claim is, read in code ---------------------------------------------------

@pytest.mark.parametrize("claim,kind", [
    ("are the King of the North", "rank"),
    ("are the king of Aurvantis", "rank"),
    ("are the chosen heir of the old duke", "rank"),
    ("are a vampire lord", "dread"),
    ("are a god", "holy"),
    ("are a hero of the realm", "renown"),
    ("are a merchant from the coast", ""),
    ("are a wizard", ""),
])
def test_the_kind_of_a_claim_is_read_from_its_words(claim, kind):
    """The phrasings `judgement.false_claim` hands back for the owner's example and its
    neighbours, measured 2026-10-01. The first kind in the table wins, so a vampire lord
    is dread before rank and the chosen heir is rank before holy."""
    assert bluff.claim_kind(claim) == kind


def test_the_planner_writes_the_kind_and_a_models_own_is_struck():
    """The kind decides an outcome, so only code writes it, as only code writes `lie`."""
    from gm import judgement

    scene, _engine, who = _table(sees=0)
    out = judgement.inject_false_claim([], "I tell him I am the king of Aurvantis.", scene)
    ob = next(r for r in out if r.get("op") == "check")["params"]["opposed_by"]
    assert ob["claim"] == "rank" and ob["lie"] == "far_fetched"

    forged = [{"op": "check", "actor": "pc", "params": {"skill": "bluff", "opposed_by": {
        "ref": who.ref, "skill": "sense motive", "claim": "rank", "lie": "believable"}}}]
    out = judgement.inject_false_claim(forged, "I tell him the road is clear.", scene)
    ob = out[0]["params"]["opposed_by"]
    assert "claim" not in ob and "lie" not in ob


# --- the rank trait ----------------------------------------------------------------------

def test_the_rank_trait_is_fixed_for_a_person_and_shifted_by_their_work():
    """Its own seeded roll, so the same person answers the same every time; and the work
    leans it — a noble's household deferential, a cutpurse resentful — measured as the
    mean over 400 people of each."""
    assert lives.rank_score("home|p7", "gentry") == lives.rank_score("home|p7", "gentry")
    gentry = sum(lives.rank_score(f"t|p{i}", "gentry") for i in range(400)) / 400
    rogue = sum(lives.rank_score(f"t|p{i}", "rogue") for i in range(400)) / 400
    assert gentry < 40 < 50 < rogue + 5
    assert rogue - gentry >= 35


def test_the_rank_trait_rerolls_nobody_already_met():
    """Kept out of the ten axes: an eleventh in `roll`'s stream would change every trait,
    want and quirk drawn after it. A life rolled today is the life rolled before."""
    life = lives.roll("home|p1")
    assert "rank" not in life.axes
    assert len(life.axes) == 10


def test_a_listener_with_a_life_is_read_from_it():
    """The real path, no patching: a person the population recorded answers from their own
    rank score; a body with no life recorded sits in the middle."""
    from rules import population

    scene, _engine, who = _table(sees=0)
    assert bluff._disposition(scene, who, "piety") == 50
    rec = population.keep_as_resident(scene, who, MARKET)
    seed = f"{rec['home']}|{rec['id']}"
    want = lives.rank_score(seed, lives.work_class_of(rec["life"]["work"]))
    assert bluff._disposition(scene, who, "rank") == want
    assert bluff._disposition(scene, who, "piety") == rec["life"]["axes"]["piety"]
