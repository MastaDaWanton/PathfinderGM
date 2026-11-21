"""Playtest 2026-11-20, the narration INPUT defects (items 23-25 and two more from the
"Version check on items 23-27"): what the plan and the brief put in front of the narrator
must be what the engine holds, at the moment the slot describes.

Each test names the 0.4.4 plan it was measured on (pgm-work/prose-gold/plans/shadow-*.txt).
Research: docs/research/2026-11-20-narration-inputs.md.
"""
from __future__ import annotations

from gm import judgement, narration, planned
from gm import watcher
from gm.brief import faces
from rules import cards
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.sheet import load_pc


def _ruins():
    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    return s, pc


# --- #25: the matter slot made of the player's own deed -------------------------------


def _toll(s, people):
    """The owner's card, as the watcher left it on the save (play-1, origin watcher)."""
    pc = s.pc()
    card = cards.Card(id="play-1", title="The Hollow's Toll",
                      facts=["The lizard is dead.",
                             "The remaining lizards are now in active combat.",
                             f"{pc.name} has collected the essence from the fallen lizard."],
                      tags=(cards.TAG_PLAY,), people=list(people), origin="watcher",
                      stage="moving", clock=1)
    cards.open_card(s, card, turn=1)
    return cards.find(s, "play-1")


def test_a_world_matter_never_offers_the_players_own_deed():
    """Shadow-0141 and 0144: the matter slot read "A matter of the world here, not a task of
    the player's: The Hollow's Toll — Shadow has collected the essence from the fallen
    lizard", and the page wrote "a faint, lingering essence ... a consequence of the toll
    taken". A fact naming the player's character is theirs, never the world's matter."""
    s, pc = _ruins()
    lizard = instantiate("guildhand", scene=s, name="lizard")
    s.add(lizard)
    card = _toll(s, [lizard.ref])
    got = cards._pull_one(s, card, ("near",), player_text="", turn=5, world=None)
    assert got is not None
    assert pc.name.split()[0] not in got["fact"]
    assert got["fact"] == "The remaining lizards are now in active combat."


def test_a_card_born_of_a_fight_is_no_matter_once_its_people_are_gone():
    """The same card, its three lizards dead and swept: nobody is here to carry it, and
    the matter slot made the owner's beat out of the player's own fight anyway."""
    s, pc = _ruins()
    lizard = instantiate("guildhand", scene=s, name="lizard")
    s.add(lizard)
    card = _toll(s, [lizard.ref])
    lizard.hp = -20
    lizard.apply_hp_state()
    assert cards._pull_one(s, card, ("near",), player_text="", turn=5, world=None) is None


def test_the_watcher_opens_no_card_on_the_foes_of_the_running_fight():
    """The card itself was the watcher's, opened mid-fight on the lizards being fought:
    a fight is the encounter's, kept by the engine (Blades in the Dark: "Not every
    situation and obstacle requires a clock")."""
    s, pc = _ruins()
    foes = [instantiate("guildhand", scene=s, name=n) for n in ("lizard", "second lizard")]
    for f in foes:
        s.add(f)
    s.initiative = [("pc", 20)] + [(f.ref, 10) for f in foes]
    s.turn = 0
    s.sides = {"pc": ["pc"], "them": [f.ref for f in foes]}
    assert watcher._the_fight(s, [f.ref for f in foes])
    bystander = instantiate("guildhand", scene=s, name="a shepherd")
    s.add(bystander)
    assert not watcher._the_fight(s, [foes[0].ref, bystander.ref])
    s.initiative = []
    assert not watcher._the_fight(s, [f.ref for f in foes])


# --- A3: after-turn state in the slots before the blow --------------------------------


def _blow_plan(engine, spy):
    move = Outcome(intent_id="i1", op="move", actor="pc",
                   tell="Kesst Vayr moves 35 ft, beside rubble.")
    hit = Outcome(intent_id="i2", op="attack", actor="pc",
                  tell=f"Kesst Vayr hits {spy.name} for 11 bludgeoning.",
                  blows=[{"result": "hit", "ref": spy.ref, "weapon": "unarmed strike",
                          "type": "bludgeoning", "severity": "devastating", "left": "down"}])
    return planned.build_plan(engine, "I move up and strike the spy", [move, hit])


def test_a_slot_before_the_blow_is_told_the_blow_has_not_landed():
    """Shadow-0097: PEOPLE HERE NOW already had the clockwork spy "broken, on the ground"
    while slot 1 was the squaring-up, and slot 3's own words said "is broken". Every slot
    shares one prefix (for the prompt cache), so every slot saw the end of the turn; the
    move slot of owner game #89 wrote the strike into the walk ("lunge forward to strike the
    dying giant cockroach", richer-prose-paths.md §1.5, A3)."""
    s, pc = _ruins()
    spy = instantiate("guildhand", scene=s, name="clockwork spy")
    s.add(spy)
    s.initiative = [("pc", 20), (spy.ref, 10)]
    s.turn = 0
    engine = Engine(s, Dice(seed=3))
    slots = _blow_plan(engine, spy)
    keys = [x["key"] for x in slots]
    walk, blow = keys.index("fact1"), keys.index("fact2")
    assert slots[blow].get("blow") and not slots[walk].get("blow")
    plan = planned.plan_messages("brief", slots, planned.present(engine), "the ruins")
    ask = planned.slot_messages(plan, slots, walk, [])[-1]["content"]
    assert "has not landed yet" in ask and "clockwork spy" in ask.split("Now write")[-1]
    # The blow slot itself, and the shared prefix, are not told so.
    assert "has not landed yet" not in planned.slot_messages(plan, slots, blow, [])[-1][
        "content"]
    assert "has not landed yet" not in plan[1]["content"]


# --- "the page said": the narrator's own sentence promoted to a fact ------------------


def test_the_players_own_shoulders_describe_nobody_else():
    """Shadow-0105 on: "c5 — clockwork spy: the page said: You square your shoulders and
    face the clockwork spy, preparing to strike from your current position." The page's
    first description of a person is kept so the next beat cannot re-invent their face
    (item 16.7); the body word here was the PLAYER's ("your shoulders"), and the sentence
    about the player became a fact about the spy, and about three lizards after it."""
    said = "You square your shoulders and face the clockwork spy, preparing to strike."
    assert narration.describing_sentences(said, "clockwork spy") == []
    assert narration.faceless(said, "clockwork spy")
    real = "The clockwork spy is a brass beetle with copper wings and a pale enamel face."
    assert narration.describing_sentences(real, "clockwork spy") == [real]


def test_a_save_carrying_the_players_sentence_is_mended_where_it_is_read():
    """The owner's save holds the spy's `described_as` from 0.4.4: the brief stops showing
    it, and the spy is owed a real face again."""
    s, pc = _ruins()
    spy = instantiate("guildhand", scene=s, name="clockwork spy")
    s.add(spy)
    spy.appearance = ""
    spy.described = True
    spy.described_as = ["You square your shoulders and face the clockwork spy, preparing "
                        "to strike from your current position."]
    text, _ = faces.section(type("Ctx", (), {"scene": s})())
    assert "square your shoulders" not in text
    judgement.settle_descriptions(s, "The wind moves over the rubble.")
    assert not spy.described and not spy.described_as
