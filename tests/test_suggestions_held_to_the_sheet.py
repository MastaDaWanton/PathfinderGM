"""A suggestion offers only what the sheet can do (item 4 of the 2026-09-30 playtest).

Measured on the owner's save: Sam, a bonesetter wizard whose prepared spells are Burning
Hands, Hydraulic Push, Magic Missile, Shocking Grasp and three cantrips — no healing — was
offered **"I use a healing spell to knit the flesh"**, and the save's last beat offered
**"I keep my hand on the hilt of my blade as I navigate the crowd."** with a shortbow in
hand and no blade on the sheet. Clicking either passed every detector silently, and
`judgement._slot_words`' ancestor vouched "blade" for ANY equipped weapon, the bow too.

Found alongside: "I cast cure light wounds" resolved to **Light**, because the cast
resolver matched reachable names by substring. Owner ruling B2: a suggestion that fails is
dropped, and fewer than two left are filled from plain options built from the scene.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from gm import judgement
from play import aftermath
from play.aftermath import suggestion_sheet
from rules import schemes
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict

from test_a_take_is_not_a_boast import SAM, _sam

HEALING_SPELL = "I use a healing spell to knit the flesh"
HILT = "I keep my hand on the hilt of my blade as I navigate the crowd."
# The two other lines the save's last beat offered beside the hilt, which are sound.
SOUND = ["I keep my head down and move quickly toward the gate.",
         "I stop at a nearby stall to see if the gossip is as thick as the fog."]


def _market(world, sheet=None):
    row = (world.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    s.add(from_dict(dict(sheet or SAM), ref="pc"))
    s.clock_minutes = 10 * 60
    e = Engine(s, Dice(seed=5), world=world)
    e.place_party(schemes._place_for(e, "market", {})["id"])
    return s, e


def _after(s, e, world, suggestions, turn_log=None):
    c = SimpleNamespace(scene=s, world=world, transcript=[], suggestions=list(suggestions),
                        engine=lambda: e, turn_log=list(turn_log or []))
    ctx = aftermath.context("beat", "turn", c, engine=e, text="", said=[])
    return suggestion_sheet.step(ctx), c


# --- the two measured lines ------------------------------------------------------------------


def test_the_healing_spell_sam_was_offered_is_dropped():
    why = suggestion_sheet.why_not(HEALING_SPELL, _sam())
    assert why == "heals with magic, and Sam has no healing spell ready"


def test_the_blade_sam_was_offered_is_dropped():
    why = suggestion_sheet.why_not(HILT, _sam())
    assert why == "reaches for Sam's blade, which is not on the sheet"


def test_a_bow_no_longer_vouches_for_a_blade_and_a_longsword_does():
    """`equipped` vouched "weapon", "blade" and "arms" for any weapon in hand."""
    bow = _sam().pc()
    assert "blade" not in judgement._slot_words(bow)
    assert {"weapon", "arms"} <= judgement._slot_words(bow)
    sword = from_dict(dict(SAM, equipped="longsword", weapons=["longsword"]), ref="pc")
    assert "blade" in judgement._slot_words(sword)
    s = Scene()
    s.add(sword)
    assert suggestion_sheet.why_not(HILT, s) == ""


# --- the spell resolver ----------------------------------------------------------------------


def test_cure_light_wounds_is_not_light():
    """"I cast cure light wounds" was cast as Light: a substring match over the spells a
    wizard can reach, and Light is the only reachable name inside the sentence."""
    assert judgement.spell_in_words("I cast cure light wounds on him").id == "cure-light-wounds"
    assert judgement.spell_in_words("a bolt of lightning") is None or \
        judgement.spell_in_words("a bolt of lightning").name.lower() != "light"
    s = _sam("the fighter")
    s.pc().spellbook = list(SAM["spellbook"]) + ["light"]
    s.pc().prepared = dict(SAM["prepared"], light=1)
    out = judgement.inject_cast([{"op": "narrate_only"}], "I cast cure light wounds on him", s)
    assert all(r.get("op") != "cast" for r in out), out
    out = judgement.inject_cast([{"op": "narrate_only"}], "I cast light on my staff", s)
    assert [r["params"]["spell"] for r in out if r.get("op") == "cast"] == ["light"]


def test_the_interpreter_reads_the_spell_the_same_way():
    from gm import interpret

    s = _sam()
    s.pc().spellbook = list(SAM["spellbook"]) + ["light"]
    assert interpret.spell_named(s, "cure light wounds") is None
    assert interpret.spell_named(s, "magic missile").id == "magic-missile"


@pytest.mark.parametrize("line,why", [
    ("I cast cure light wounds on him", "names Cure Light Wounds, which Sam cannot cast"),
    ("I cast a healing spell on the fighter",
     "heals with magic, and Sam has no healing spell ready"),
    ("I channel positive energy to heal him", "channels energy, which Sam cannot"),
    ("I use Lay on Hands on the fighter", "names Lay on Hands, which Sam does not have"),
    ("I use Blood Nova on the merchant", "names Blood Nova, which Sam does not have"),
])
def test_what_the_sheet_cannot_back_is_named(line, why):
    assert suggestion_sheet.why_not(line, _sam("the fighter")) == why


@pytest.mark.parametrize("line", [
    "I cast magic missile at the guard",
    "I cast Burning Hands at the thug",
    "I light a torch and look around",          # a verb, not the spell Light
    "I kneel and press on the wound",
    "I check my bow and nock an arrow",
    "I reach for my staff",
    "I hand over my purse",                     # 37 gp in it
    "I tell her my name",                       # a name is not an item
    "I pray quietly for the fighter",
    *SOUND,
])
def test_what_the_sheet_backs_stays(line):
    assert suggestion_sheet.why_not(line, _sam("the fighter")) == "", line


def test_a_healer_is_offered_the_healing_spell():
    """The same line is sound for a caster with a healing spell ready."""
    cleric = dict(SAM, **{"class": "cleric", "spellbook": [],
                          "prepared": {"cure-light-wounds": 1}})
    s = Scene()
    s.add(from_dict(cleric, ref="pc"))
    assert suggestion_sheet.why_not(HEALING_SPELL, s) == ""


# --- the member: drop, fill, log ------------------------------------------------------------


def test_the_member_drops_the_blade_and_keeps_two(worlds):
    """The save's last beat, exactly: the hilt goes, the other two stay, nothing is
    filled because two remain, and the prose row records all three as offered."""
    s, e = _market(worlds)
    prose = {"kind": "prose", "chars": 900}
    rows, c = _after(s, e, worlds, [*SOUND, HILT], turn_log=[prose])
    assert c.suggestions == SOUND
    assert rows == [{"kind": "suggestion-sheet", "filled": [], "dropped": [
        {"text": HILT, "why": "reaches for Sam's blade, which is not on the sheet"}]}]
    assert c.turn_log[0]["suggested"] == [*SOUND, HILT]


def test_fewer_than_two_left_are_filled_from_the_scene(worlds):
    """Owner ruling B2: fill from plain options — somebody here, look around, a way out —
    and never from the start's own lines."""
    s, e = _market(worlds)
    sorva = instantiate("guildhand", scene=s, name="Sorva Sparrik")
    s.add(sorva)
    # The market's keeper stands here too; the person in conversation comes first.
    e.join_talk(sorva, how="the player spoke to her")
    rows, c = _after(s, e, worlds, [HEALING_SPELL, HILT, SOUND[0]])
    assert c.suggestions[0] == SOUND[0]
    assert c.suggestions[1] == "I talk to Sorva Sparrik."
    assert len(c.suggestions) == 2
    assert rows[0]["filled"] == ["I talk to Sorva Sparrik."]
    assert [d["text"] for d in rows[0]["dropped"]] == [HEALING_SPELL, HILT]


def test_nobody_here_fills_with_looking_and_a_way_out(worlds):
    s, e = _market(worlds)
    for ref in [r for r in s.people if r != "pc"]:
        s.people.pop(ref)
    rows, c = _after(s, e, worlds, [HEALING_SPELL, HILT])
    assert c.suggestions[0] == "I look around."
    assert c.suggestions[1].startswith("I head to ")
    assert len(c.suggestions) == 2


def test_sound_suggestions_are_logged_and_left_alone(worlds):
    s, e = _market(worlds)
    prose = {"kind": "prose"}
    rows, c = _after(s, e, worlds, SOUND, turn_log=[{"kind": "resolution"}, prose])
    assert rows == [] and c.suggestions == SOUND
    assert prose["suggested"] == SOUND


def test_the_member_is_registered_and_frozen_with_the_app():
    """Discovered by filename (`pkgutil`), and the spec collects the package it is in."""
    import pathlib

    names = [m.__name__.rsplit(".", 1)[-1] for m in aftermath.registered()]
    assert names.index("suggestion_sheet") < names.index("suggestion_pronouns")
    spec = (pathlib.Path(__file__).resolve().parents[1] / "pathfindergm.spec").read_text(
        encoding="utf-8")
    assert '"play.aftermath"' in spec
