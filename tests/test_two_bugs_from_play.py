"""Two things reported from a real session on 2026-09-15, and what was actually wrong.

> "chose my background but still got a generic opener. then I asked a person how many arms
> i have and they said two, I am playing as an asura race I have more than 2 arms."

Both were real, and neither was where it looked.

**The background bound fine — nothing ever called it.** The save carried
`background: 'pit-fighter'` and `background_ties: []`, and run by hand against that same
save the binder produced "You fought where Xylaraezys took the bets, near the market, and
drew a crowd." Three functions open a campaign — `begin_with`, the "enrolled but never
played" branch of `resume`, and `_begin` — and `_bind_background` was called from the first
of those only. A character forged with a past and then played through either of the others
got the stranger's opening, which is the template `play/opening.py` correctly falls back to
when nobody knows them.

This is the same defect as the model gate in v0.1.0, which was put on `/api/start` and
`/api/resume` while `Continue` was a plain link. **Gating one door is not gating.**

**The narrator was never told about the arms.** The brief carries `races.body_line`, and
that function chose its extra clauses by asking whether a tag was in `TAG_RP` — the race
point *price table*. So whether a servant could see your arms depended on whether the
Advanced Race Guide charges for them, and `limbs.arms` and `tail` are free. The asura's own
trait list says "an extra pair of arms" and the sheet shows it; the one place that mattered
did not.
"""
from __future__ import annotations

from rules import races


# --- the body the room can see ----------------------------------------------------------

# The race in the report is `asura`, which is the reporter's own homebrew and is not in
# the shipped catalogue — and the suite points `CAMPAIGN_DIR` at an empty directory on
# purpose, so no test may reach for it. These build the document instead, which is the
# honest unit anyway: the defect was in how a body is DESCRIBED, not in one race.
FOUR_ARMED = {"id": "x", "name": "Four-armed thing", "speed": 30, "size": "medium",
              "tags": ["limbs.arms", "tail", "ferocity"]}


def test_a_body_with_four_arms_says_so():
    """The report, as an assertion. A person standing in front of this character can
    count, and the narrator has to be able to."""
    line = races.body_line(FOUR_ARMED)
    assert "arms" in line, line
    assert "four" in line.lower(), line


def test_the_visible_body_is_not_chosen_by_the_price_list():
    """The root cause. `TAG_RP` prices a race; it does not describe one, and a body part
    with no price is still a body part. Asked mechanically rather than by listing the
    tags, so a new free one is caught the same day."""
    for tag, words in races.VISIBLE_BODY.items():
        doc = {"id": "x", "name": "X", "speed": 30, "tags": [tag]}
        assert words in races.body_line(doc), tag
        # And the thing that made this a bug: these are exactly the tags the price list
        # has no row for.
        if tag in races.TAG_RP:
            continue
        assert tag not in races.TAG_RP


def test_a_tail_and_extra_legs_are_visible_too():
    for tag, word in (("tail", "tail"), ("limbs.legs", "legs")):
        doc = {"id": "x", "name": "X", "speed": 30, "tags": [tag]}
        assert word in races.body_line(doc)


def test_mechanics_still_do_not_reach_the_narrator_as_numbers():
    """The other half of the third law. The visible body is a tell; damage reduction and
    spell resistance are rules, and the brief is not where a rule goes."""
    line = races.body_line({**FOUR_ARMED,
                            "tags": FOUR_ARMED["tags"] + ["dr.5.chaotic",
                                                          "spell-resistance"]})
    assert "arms" in line
    for rule in ("DR 5", "spell resistance", "1d6"):
        assert rule not in line, rule


def test_the_body_reaches_the_brief():
    """End to end: the sentence the narrator is actually handed."""
    from unittest import mock

    from gm import prompts
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from world.loader import load_cached

    world = load_cached("fixtures/pangrella-campaign.json")
    s = Scene(location_id="5bbd0c40345f")
    pc = instantiate("guildhand", scene=s, name="Four-Arms")
    pc.kind = "pc"
    pc.notes = "Four arms and a tail."          # so the brief describes them at all
    s.add(pc)
    Engine(s, Dice(seed=1), world=world).place_party()

    with mock.patch.object(type(pc), "_race_doc", lambda _self: FOUR_ARMED):
        brief = prompts.scene_brief(world, s, world.get("5bbd0c40345f"),
                                    recent=[], turn=1)
    assert "arms" in brief, "the narrator is still not told about the arms"


# --- one door, not three -------------------------------------------------------------------

def test_every_way_a_campaign_opens_binds_the_past_first():
    """The defect, pinned where it happened rather than where it showed. Three call sites
    opened a story and one of them bound the background; the other two produced a
    stranger's opening for a character who had a past on their sheet.

    Checked as "nothing calls the old pair directly" rather than by counting call sites,
    because the failure was a fourth door being added without the bind — and a test that
    counts three doors passes happily when somebody adds a fifth.
    """
    import inspect

    from play import campaign

    src = inspect.getsource(campaign)
    body = src.split("def open_the_story", 1)
    assert len(body) == 2, "the one door has been renamed or removed"
    # `_open_with(..., opening_text(...))` may appear exactly once: inside the one door.
    paired = src.count("_open_with(c, opening_text(")
    assert paired == 1, (
        f"{paired} places open a story directly; they must go through `open_the_story`, "
        f"which binds the past first")


def test_the_binding_happens_before_the_opening_is_written():
    """The order is the whole point, and is why this is one function rather than two
    calls. The first paragraph is exactly where "you were apprenticed to somebody" has to
    become a name — and an argument cannot be evaluated after the call it belongs to."""
    import inspect

    from play import campaign

    door = inspect.getsource(campaign.open_the_story)
    assert door.index("_bind_background(c)") < door.index("_open_with("), door


def test_a_past_that_was_never_filled_is_filled_on_the_next_load():
    """Fixing the doors helps the next character and does nothing for the one the bug was
    reported from, who is on disk with a background and no ties. A player is not going to
    reroll because the plumbing was wrong."""
    import inspect

    from play import campaign

    heal = inspect.getsource(campaign._heal_background)
    assert "background_ties" in heal
    # Only ever fills an empty list: binding twice would re-cast the people it names.
    assert "return" in heal.split("getattr(pc, \"background_ties\", None)")[1][:80]
    assert "_heal_background(c)" in inspect.getsource(campaign), "nothing calls it"
