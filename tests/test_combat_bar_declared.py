"""The combat bar's Declare section, fighting defensively and total defense (combat bar
round 2, 2026-11-22).

The owner, 2026-11-22: "the combat bar should have a section for feats like power attack
or cleave that must be declared to be used." Measured on integrate/0.5.1-impl b30999c3
before this lane:
- the bar's declared options were toggles mixed into the action row, with Vital Strike
  and Cleave as two buttons hard-wired into table.html and a JS list of which options
  exclude which, and none of them said a number;
- the full attack's slots left the toggles out: Power Attack on at BAB +8, the slot read
  +11 while the dice popup added up +8 (lane D's own note);
- fighting defensively and total defense had no door at all (no param, no op);
- a feint and a tumble were reachable only by typing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.test import Client

from rules import reactions, states
from rules.sheet import ATTACK_CHOICES
from tests.test_attack_feats import _fight, _pc, _run, _tot
from tests.test_combat_panel import _act, fight  # noqa: F401 — the fixture

ROOT = Path(__file__).resolve().parent.parent


def _opts(pc):
    from play.views import _attack_slots

    return {o["id"]: o for o in _attack_slots(pc)["options"]}, _attack_slots(pc)


# --- fighting defensively ------------------------------------------------------------------

def test_fighting_defensively_costs_four_to_hit_for_two_dodge_until_the_next_turn():
    """CRB, Combat: "you take a -4 penalty on all attacks in a round to gain a +2 dodge
    bonus to AC until the start of your next turn." Before: no param, so nobody could."""
    s, e, a, (thug,) = _fight(_pc())
    ac = a.ac()
    res = _run(e, [{"op": "attack", "actor": a.ref, "target": thug.ref,
                    "params": {"fighting_defensively": True}}])
    swing = res.outcomes[0]
    assert ("Fighting defensively", -4) in [(m.source, m.value)
                                            for m in swing.rolls[0].modifiers]
    assert "fights defensively" in swing.tell
    assert a.has_state(states.FIGHTING_DEFENSIVELY) and a.ac() == ac + 2
    # Law 2: the stance is one effect; its end takes every number with it.
    a.remove_effects(match=lambda x: states.FIGHTING_DEFENSIVELY in x.tags)
    assert a.ac() == ac


def test_three_ranks_of_acrobatics_raise_the_dodge_to_three_and_six():
    """CRB, Acrobatics: "If you have 3 or more ranks in Acrobatics, you gain a +3 dodge
    bonus to AC when fighting defensively instead of the usual +2", and +6 (not +4) for
    total defense."""
    tumbler = _pc(ranks={"acrobatics": 3})
    o, _ = _opts(tumbler)
    assert o["fighting_defensively"]["says"] == "−4 to hit, +3 AC until your next turn"
    assert o["total_defense"]["says"] == "+6 AC until your next turn"


# --- total defense -------------------------------------------------------------------------

def test_total_defense_is_a_standard_action_of_four_dodge_and_no_reactions():
    """CRB, Combat: "You get a +4 dodge bonus to your AC for 1 round ... You can't make
    attacks of opportunity while using total defense." Before: no op carried it."""
    s, e, a, (thug,) = _fight(_pc())
    ac = a.ac()
    assert reactions.reactions_for(a)
    res = _run(e, [{"op": "total_defense", "actor": a.ref}])
    assert res.outcomes[0].status == "resolved", res.outcomes[0].tell
    assert "total defense" in res.outcomes[0].tell
    assert a.ac() == ac + 4 and reactions.reactions_for(a) == []
    assert s.standard_spent.get(a.ref) == s.round
    # One standard action a round: a second is refused, with nothing laid.
    again = _run(e, [{"op": "total_defense", "actor": a.ref}]).outcomes[0]
    assert again.status != "resolved" and "standard action" in again.tell


def test_total_defense_will_not_combine_with_a_guarded_stance():
    """CRB: "You can't combine total defense with fighting defensively or with the
    benefit of the Combat Expertise feat." """
    s, e, a, (thug,) = _fight(_pc())
    _run(e, [{"op": "attack", "actor": a.ref, "target": thug.ref,
              "params": {"fighting_defensively": True}}])
    s.standard_spent.pop(a.ref, None)
    out = _run(e, [{"op": "total_defense", "actor": a.ref}]).outcomes[0]
    assert out.status != "resolved" and "cannot be combined" in out.tell


# --- the Declare section: the engine's options, the engine's numbers -----------------------

def test_every_option_says_what_it_does_in_the_engines_numbers():
    """"−3 to hit, +6 damage" is Power Attack at BAB +8 with a one-handed longsword
    (2 x (1 + 8 // 4)); Combat Expertise's +3 AC is measured with the stance laid on a
    copy, and the character measured is left untouched."""
    pc = _pc(feats=["Power Attack", "Combat Expertise", "Vital Strike", "Cleave"])
    effects = len(pc.effects)
    o, _ = _opts(pc)
    assert o["power_attack"]["says"] == "−3 to hit, +6 damage"
    assert o["combat_expertise"]["says"] == "−3 to hit, +3 AC until your next turn"
    assert o["vital_strike"]["says"] == "weapon dice ×2"
    assert o["cleave"]["says"] == "−2 AC until your next turn"
    assert len(pc.effects) == effects


def test_an_option_the_planned_action_cannot_carry_has_the_engines_reason():
    """Vital Strike on a full attack, Rapid Shot on one blow: greyed with the sentence
    `Engine._attack_choice_refusal` refuses the op with. Piranha Strike and Power Attack
    exclude each other because the engine refuses the pair, not because the page says."""
    o, _ = _opts(_pc(feats=["Vital Strike", "Power Attack", "Piranha Strike",
                            "Weapon Finesse"], weapons=("shortsword",)))
    assert o["vital_strike"]["refuse"]["strike"] == ""
    assert "cannot ride a full attack" in o["vital_strike"]["refuse"]["full"]
    assert "piranha_strike" in o["power_attack"]["excludes"]
    assert "power_attack" in o["piranha_strike"]["excludes"]
    bow, _ = _opts(_pc(feats=["Rapid Shot", "Point-Blank Shot"], weapons=("longbow",)))
    assert "full attack" in bow["rapid_shot"]["refuse"]["strike"]
    assert bow["rapid_shot"]["says"] == "+1 attack, −2 to hit on every attack"
    # A feat held but unusable is shown, greyed with the prerequisite it lacks.
    weak, _ = _opts(_pc(feats=["Piranha Strike"], weapons=("shortsword",)))
    assert "Weapon Finesse" in weak["piranha_strike"]["why"]


def test_the_full_attack_slots_carry_the_toggled_options():
    """Lane D's note: the slots showed the bare plan, +11/+6 with Power Attack on, while
    the dice popup added +8/+3. Slot plus the option's `bonus` is the roll's own sum."""
    pc = _pc(feats=["Power Attack"])
    o, slots = _opts(pc)
    for (key, it), row in zip(pc.attack_plan("longsword", True), slots["plans"][""]):
        rolled = _tot(pc.attack_modifiers(key, it, choices=("power_attack",)))
        assert row["bonus"] + o["power_attack"]["bonus"][key] == rolled
    js = (ROOT / "play/static/js/table/04-combat-and-turns.js").read_text(encoding="utf-8")
    assert "declaredBonus(w || slotWeapon(i), true)" in js
    # A full-attack option (Rapid Shot, a flurry) is greyed in the surprise round with
    # its rule, as Full attack itself is refused (impl2/surprise's `surprise_round`).
    assert 'o.shape === "full" && STATE && STATE.scene && STATE.scene.surprise_round' in js


def test_the_page_names_no_option_and_the_shapes_cover_the_engines_list():
    """One source of truth: every ATTACK_CHOICES entry has its shape row, and the bar's
    script and template carry no option's name or id — lane D's JS held a pair list
    (`apart`) and table.html two hard-wired buttons."""
    from play.views import _OPTION_SHAPES

    assert set(ATTACK_CHOICES) <= set(_OPTION_SHAPES)
    page = "\n".join((ROOT / p).read_text(encoding="utf-8") for p in (
        "play/static/js/table/04-combat-and-turns.js", "play/templates/play/table.html"))
    for oid, (_shape, name, _text) in _OPTION_SHAPES.items():
        assert not re.search(rf"[\"'`]{oid}[\"'`]", page), oid
        assert f">{name}<" not in page and f'"{name}"' not in page, name


# --- the bar's door ------------------------------------------------------------------------

def test_the_panel_posts_total_defense_and_a_feint_but_no_other_check(fight):  # noqa: F811
    """`check` joins the panel's whitelist for the Declare section's feint and tumble only:
    a Perception roll from a button is refused, so the door is not every skill."""
    client, cm = fight
    r = _act(client, [{"op": "check", "params": {"skill": "perception"}}])
    assert r.status_code == 400 and "feint" in r.json()["error"]
    r = _act(client, [{"op": "total_defense"}], label="total defense", end_turn=False)
    assert r.status_code == 200, r.content
    pc = cm.current().scene.pc()
    assert pc.has_state(states.TOTAL_DEFENSE)
    state = json.loads(Client().get("/api/state").content)
    ids = {o["id"] for o in state["attacks"]["options"]}
    assert {"total_defense", "feint", "tumble", "fighting_defensively"} <= ids
