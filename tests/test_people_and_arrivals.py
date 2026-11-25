"""Lane fix/people-and-arrivals: the owner's game of 2026-11-23 (playtest-2026-11-23.md,
items O4, O1, 14, 15, 16, 19, 20). docs/research/2026-11-25-people-and-arrivals.md."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from gm import creature_look, narration, planned
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parent.parent


def _scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    scholar = instantiate("guildhand", scene=s, name="the lost scholar")
    scholar.notes = ("Came down to read the old inscriptions and stayed too long; says the "
                     "ghost is strongest in the death room.")
    s.add(scholar)
    return s, Engine(s, Dice(seed=3)), scholar


def _arrival():
    return Outcome(intent_id="i1", op="travel", actor="pc", because="",
                   effects=[{"kind": "biome", "place": "here", "was_place": "there"}],
                   tell="You are at the hall of pillars now. The lost scholar is here.")


# --- O4: a stranger meets the player before anything else -------------------------------------

def test_a_stranger_come_upon_reacts_to_the_stranger_first():
    """O4, the owner's "MUST FIX": arriving in the hall of pillars, the lost scholar's first
    line was a town rumour ("The folk in Branford speak often of the old mine"). The plan
    now gives a stranger the party has just come upon a first-meeting reply, from their
    own situation, with talk of elsewhere ruled out — and only once."""
    s, engine, scholar = _scene()
    slots = planned.build_plan(engine, "I go to the hall of pillars.", [_arrival()])
    meet = next(x for x in slots if x.get("meets"))
    assert meet["key"] == "reply" and meet["speaker"] == scholar.ref
    assert "has never met the player" in meet["say"]
    assert "read the old inscriptions and stayed too long" in meet["say"]
    assert "the ghost" not in meet["say"], "what they know is theirs to tell when asked"
    assert "nothing of news, of other places" in meet["say"]
    assert not any(x["key"] == "aside" for x in slots)
    # Met once: written down when the slot stands, never again.
    s.said[planned.MET_KEY] = [scholar.ref]
    again = planned.build_plan(engine, "I go to the hall of pillars.", [_arrival()])
    assert not any(x.get("meets") for x in again)


def test_no_first_meeting_without_an_arrival_or_with_somebody_known():
    s, engine, scholar = _scene()
    idle = planned.build_plan(engine, "I wait.", [])
    assert not any(x.get("meets") for x in idle)
    from rules import population

    population.met(s, population.keep_as_resident(s, scholar, "here"))
    known = planned.build_plan(engine, "I go to the hall of pillars.", [_arrival()])
    assert not any(x.get("meets") for x in known)


def test_a_stranger_carries_no_talk_of_elsewhere():
    """O4's source: the rumour card's go-between carrier was the scholar, met that beat. A
    carrier is now somebody the player has spoken with (`cards._carrier`)."""
    from rules import cards, population

    s, _engine, scholar = _scene()
    assert cards._carrier(s, "") is None
    population.met(s, population.keep_as_resident(s, scholar, "here"))
    assert cards._carrier(s, "") is scholar


# --- O1: a creature's look on first sight ---------------------------------------------------

def _chicken():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    bird = instantiate("ac-chicken", scene=s, name="chicken")
    s.add(bird)
    return s, bird


def test_a_creature_look_is_written_from_its_record_and_checked():
    """O1: the chickens, the clockwork spy, the ramidreju and the poltergeist came on as
    names. Code gives the facts (size beside a man, natural weapons, ways of moving); the
    model's look is refused with a number or a deed in it, asked once more with the fault
    named, and a plain line from the record stands in when it will not come right."""
    _s, bird = _chicken()
    facts = creature_look.facts(bird)
    assert any("about the size of a cat" in f for f in facts)
    assert "it fights with: bite" in facts and "how it moves: it flies" in facts
    replies = iter(['{"look": "A chicken 2 feet tall pecks at you."}',
                    '{"look": "A scrawny hen, its brown feathers ragged, head cocked."}'])
    asked: list = []

    def chat(msgs, *a, **k):
        asked.append(msgs)
        return SimpleNamespace(json=lambda: json.loads(next(replies)))

    look, notes = creature_look.write(bird, chat=chat, model="m", host="h")
    assert look.startswith("A scrawny hen")
    assert "number" in notes[0] and len(asked) == 2
    assert "You wrote" in asked[1][-1]["content"]

    def broken(*a, **k):
        return SimpleNamespace(json=lambda: {"look": "It lunges at you."})

    plain, notes = creature_look.write(bird, chat=broken, model="m", host="h")
    assert plain.startswith("The chicken is a Tiny animal") and "bite" in plain
    assert notes[-1].endswith("written from the record")


def test_a_look_that_shrinks_or_swells_a_creature_is_refused():
    _s, bird = _chicken()
    assert creature_look.fault("A hen as big as a horse.", bird,
                               size_said=lambda t, n: "large")
    assert not creature_look.fault("A small brown hen.", bird, size_said=lambda t, n: "tiny")


def test_a_creature_is_owed_its_look_whether_or_not_the_page_named_it():
    """The ramidreju attacked on the venture's beat and no page described it: a creature
    here and seen is owed its look, and a body word ("a tiny clockwork spy hovering") no
    longer counts as one."""
    from gm import judgement

    s, bird = _chicken()
    assert bird.ref in judgement.creatures_unseen_described(s)
    owed = judgement.settle_descriptions(s, "A tiny chicken flutters by the wall.")
    assert bird.ref in owed and not bird.described
    assert creature_look.sentence(bird, "A scrawny hen.") == "You see the chicken: a scrawny hen."


# --- 14, 15, 16, 19, 20 ----------------------------------------------------------------------

def test_a_question_naming_nobody_brings_no_characters():
    """#241: "/gm I have tried to read the repeating words but I get nothing" answered
    from Ratta Farrow, Rosalie Duskwatch and Rosalie Krell (-7.9 each on common words)."""
    from play import campaign as cm, gm_search

    w = cm.load_cached(cm._resolve_world_source("fixtures/aurvantis-campaign.json"))
    gm_search.forget(w)
    try:
        q = "I have tried to read the repeating words but I get nothing"
        assert not [h for h in gm_search.search(w, q) if h.kind == "character"]
        assert gm_search.search(w, "who is drenn ironvale")[0].name == "Drenn Ironvale"
    finally:
        gm_search.forget(w)


def test_the_same_down_told_twice_is_told_once():
    """#171: "Ramidreju falls to the ground, unconscious and dying. The creature collapses
    to the ground, unconscious and dying." Over the owner's ten saves (1,539 GM lines) the
    rule hits that line and no other."""
    page = ("Ramidreju falls to the ground, unconscious and dying. The creature collapses "
            "to the ground, unconscious and dying. What do you do?")
    kept, cut = narration.drop_said_twice(page)
    assert kept == "Ramidreju falls to the ground, unconscious and dying. What do you do?"
    assert cut == ["The creature collapses to the ground, unconscious and dying."]
    # Two facts that differ by a number or a closing word are two facts.
    assert not narration.said_twice("Kesst fails a Will save (5 against DC 10). Kesst "
                                    "fails a Will save (6 against DC 11).")
    assert not narration.said_twice("Kesst gains +4 str (Power leaf). Kesst gains +4 con "
                                    "(Power leaf).")
    # Speech is the speaker's to repeat; a sentence there twice word for word keeps one.
    assert not narration.said_twice("'Down to the ground, unconscious and dying,' he says. "
                                    "He falls to the ground, unconscious and dying.")
    twice = "The smith wipes his hands on his apron and looks up. " * 2
    assert narration.drop_said_twice(twice)[0] == twice.split(". ")[0] + "."


def test_the_players_deed_is_not_printed_as_their_speech():
    """#175: "i finish the ramidreju", a turn the engine made nothing of, came back
    '… drive your blade deep into its chest. "I finish the ramidreju."'."""
    slot = ('You lean over the fallen beast and drive your blade deep into its chest. '
            '"I finish the ramidreju."')
    assert planned.echoed(slot, "i finish the ramidreju") == ['"I finish the ramidreju."']
    assert not planned.echoed(slot, '"I finish the ramidreju," I say')
    assert not planned.echoed('"Not yet," the smith says.', "i ask the smith")


def test_who_the_players_words_are_about_is_kept(monkeypatch):
    """#223: "tell him that the way out is clear is he wishes to leave" came back "you tell
    the scholar that the way out is clear and you wish to leave"."""
    out = planned.Planned(text="", slots=[], messages=[], model="m")
    s = {"key": "fact1", "verbatim": "the way out is clear is he wishes to leave",
         "tells": ["Kesst speaks to the lost scholar, to the effect that the way out is "
                   "clear is he wishes to leave."]}
    asks: list = []

    def ask(*a, **k):
        asks.append(k["redo"])
        out.calls.append({})
        return ("You tell the scholar the way out is clear, if he wishes to leave.", {})

    monkeypatch.setattr(planned, "_ask", ask)
    wrong = "You tell the scholar that the way out is clear and you wish to leave."
    fixed = planned._pronouns_kept(out, [], [], 0, [], ("m", "h", "", ""), s, wrong,
                                   final=False, lift=None, core=True)
    assert "if he wishes" in fixed and '"he"' in asks[0]
    kept = planned._pronouns_kept(out, [], [], 0, [], ("m", "h", "", ""), s,
                                  "You tell him the way out is clear if he wishes.",
                                  final=False, lift=None, core=True)
    assert len(asks) == 1 and kept.startswith("You tell him")


def test_the_ghosts_remains_are_a_corpse_on_the_page():
    """#278: "a ghost's body, which bears a knife" — the revelation said "the ghost's own
    body". A PF1e ghost is incorporeal; its remains are what lies there."""
    tags = json.loads((ROOT / "content/dungeons/tags.json").read_text(encoding="utf-8"))
    text = json.dumps(tags)
    assert "ghost's own body" not in text
    assert "the remains of the one who became the ghost" in text


def test_the_excursion_closing_never_makes_one_last_stand():
    """#194: "makes for one last stand of the same" came back as a shadow "rising to offer
    one final, defiant stand". The closing's tell no longer says "one last"."""
    src = (ROOT / "play/craft_views.py").read_text(encoding="utf-8")
    assert 'tell=f"When the work is done, {pc.name} makes for one last' not in src
    assert "another {enc.get('spot')" in src
