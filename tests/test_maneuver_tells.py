"""A manoeuvre's tell names who did what to whom, on anybody's turn.

`rules/tables.py` MANEUVERS wrote each consequence in the attacker's second person — "you
drag the target 5 feet", "you are knocked prone instead", "both of you gain the grappled
condition" — and the engine spliced it into the tell after the attacker's name. On a
creature's turn the narrator is told the player is "you", and the tells are shown to it
with the player already made "you" (docs/wrong-actor.md). So the thug's drag reached the
model as

    "The thug drags you by 3: you drag the target 5 feet."

— the thug dragging the player, and then the player dragging somebody. The check built
for creature turns told the wrong way round, `narration.wrong_actor`, scores that
sentence clean (it names the actor, and no player's name is left in it), so the backstop
that replaces a bad beat with its tells would have put this one on the page as the truth.
The fix has to be at the source.

The lead had its own agreement fault: it was `name + "s"`, which wrote "bull rushs", and
once the player's tells went through `pc_to_second_person` it wrote "You trips the thug".
"""
from __future__ import annotations

import re

import pytest

from gm import narration
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import full_sheet, load_pc
from rules.tables import MANEUVERS, maneuver_text, maneuver_verbs, third_person

PC = "Kesst Vayr"
THUG = "the thug"


class _AimedCMB(Dice):
    """Every CMB d20 lands on the face asked for; everything else rolls as usual. A
    creature's roll is the engine's own, so this is the only way to aim it."""

    def __init__(self, face: int):
        super().__init__(seed=20260927)
        self.face = face

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if "(CMB)" in (label or ""):
            return self.given(self.face, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _tell(key: str, by: str, face: int, strength: int) -> str:
    """One manoeuvre by `by` ("pc" or "c1") at the other, with the CMB face aimed, and
    the attacker's Strength set so the margin lands where the branch needs it."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name=THUG))
    engine = Engine(scene, _AimedCMB(face))
    engine._ensure_encounter("pc")
    attacker = scene.get(by)
    attacker.abilities["str"] = strength
    target = "c1" if by == "pc" else "pc"
    res = engine.run(engine.validate([{
        "op": "attack", "actor": by, "target": target, "visibility": "hidden",
        "params": {"manoeuvre": key}}]))
    while res.awaiting:
        res = engine.resume(face)
    return " ".join(o.tell for o in res.outcomes if o.op == "attack")


# Face 20 with Str 30 clears CMD by more than 10 (every degree and every extra 5 feet);
# a natural 1 with Str 1 fails by 10 or more (every backfire).
BRANCHES = {"success": (20, 30), "failure": (1, 1)}


@pytest.mark.parametrize("branch", sorted(BRANCHES))
@pytest.mark.parametrize("by", ["c1", "pc"])
@pytest.mark.parametrize("key", sorted(MANEUVERS))
def test_no_manoeuvre_tell_says_you_or_the_target(key, by, branch):
    """The engine's tell names both people and never says "you" — before the player's
    person is applied, "you" can only be a guess about who is reading, and on a
    creature's turn the old guess was the creature. Every manoeuvre, both sides, both
    ends of the roll."""
    face, strength = BRANCHES[branch]
    tell = _tell(key, by, face, strength)
    assert tell, "no manoeuvre was resolved"
    assert not re.search(r"\byou\b|\byour\b|\bthe target\b|[{}\[\]]", tell, re.I), tell
    assert PC in tell and THUG in tell.lower(), tell
    if branch == "failure" and MANEUVERS[key].get("backfire"):
        assert "instead" in tell or "drops" in tell, tell


def test_an_npc_drag_no_longer_reads_you_drag_the_target_5_feet():
    """The defect, exactly: the thug drags the player, and the player is told they did
    the dragging."""
    tell = _tell("drag", "c1", 20, 30)
    assert "you drag the target 5 feet" not in tell
    shown, _ = narration.pc_to_second_person(tell, PC)
    assert re.match(r"The thug drags you by \d+: you are dragged 5 feet\.", shown), shown
    assert "you drag" not in shown.lower()
    assert narration.wrong_actor(shown, THUG, PC) == []


@pytest.mark.parametrize("key,backfire", [
    ("trip", "The thug is knocked prone instead."),
    ("disarm", "The thug drops the weapon used for the disarm."),
])
def test_a_creatures_backfire_lands_on_the_creature(key, backfire):
    """"you are knocked prone instead" on the thug's failed trip told the narrator the
    PLAYER fell — and the engine had put `prone` on the thug."""
    tell = _tell(key, "c1", 1, 1)
    shown, _ = narration.pc_to_second_person(tell, PC)
    assert backfire in shown, shown
    assert "you are knocked prone" not in shown.lower()


def test_a_creatures_grapple_holds_both_by_name():
    tell = _tell("grapple", "c1", 20, 30)
    shown, _ = narration.pc_to_second_person(tell, PC)
    assert "the thug and you both gain the grappled condition." in shown, shown


def test_the_players_own_manoeuvre_reads_in_the_second_person_with_agreement():
    """The player's tells become "you" downstream, and the verb has to follow: the lead
    was `name + "s"`, so the page read "You trips the thug", and a bull rush was a
    "bull rushs"."""
    shown, _ = narration.pc_to_second_person(_tell("trip", "pc", 20, 30), PC)
    assert re.match(r"You trip the thug by \d+: the thug is knocked prone\.", shown), shown
    shown, _ = narration.pc_to_second_person(_tell("bull rush", "pc", 20, 30), PC)
    assert shown.startswith("You charge the thug in a bull rush by "), shown
    assert "You push the thug back 5 feet." not in shown   # mid-sentence, not capital
    assert "you push the thug back 5 feet" in shown
    assert "The thug is pushed another" in shown
    assert "rushs" not in shown


def test_every_maneuver_verb_turns_to_the_second_person():
    """`pc_to_second_person` fixes the verb after "you" from a written list, not a
    guess. Every `[verb]` the table conjugates has to be on it, or the player's own
    manoeuvre reads "you drags". Grep-for-every-copy, held by a test."""
    missing = []
    for m in MANEUVERS.values():
        texts = [m.get(f, "") for f in ("lead", "effect", "backfire", "per_5_over")]
        texts += list((m.get("degrees") or {}).values())
        for verb in (v for t in texts for v in maneuver_verbs(t)):
            if narration._YOU_VERBS.get(third_person(verb)) != verb:
                missing.append(third_person(verb))
    assert not missing, f"add to narration._YOU_VERBS: {sorted(set(missing))}"


def test_the_template_agrees_its_verb_with_the_nearest_person():
    """Inform 7's adaptive text: "[The actor] [put] [the noun]" — the verb agrees with
    who is named before it, not with the reader."""
    t = "{actor} [take] an object {target} [are] carrying"
    assert maneuver_text(t, THUG, PC) == "The thug takes an object Kesst Vayr is carrying"
    assert maneuver_text(t, THUG, "you", you="target") == \
        "The thug takes an object you are carrying"
    assert maneuver_text(t, "you", "the target", you="actor") == \
        "You take an object the target is carrying"
    assert maneuver_text("{actor} [move] through {target's} space", THUG, PC) == \
        "The thug moves through Kesst Vayr's space"
    assert maneuver_text("{target} [are] pushed another {feet} feet", THUG, PC,
                         feet=10) == "Kesst Vayr is pushed another 10 feet"


def test_the_sheet_reads_in_the_players_person():
    """The character sheet is the player's own page: "you", "the target", and agreeing
    verbs — the same templates, read from the other side."""
    sheet = full_sheet(load_pc("fixtures/pc-kesst.json"))
    effects = {m["name"]: m["effect"] for m in sheet["offense"]["maneuvers"]}
    assert effects["overrun"] == "You move through the target's space"
    assert effects["trip"] == "The target is knocked prone"
    assert effects["grapple"] == "You and the target both gain the grappled condition"
    for name, text in effects.items():
        assert not re.search(r"[{}\[\]]|\bYou \w+s\b", text), (name, text)
