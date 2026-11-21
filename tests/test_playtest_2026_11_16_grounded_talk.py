"""Playtest 2026-11-16, the grounded-talk lane: items 54, 58, 60, 64, 66 and 96.

The common root of 54/58/66/96: a person's answer was not drawn from what the engine knows
about them. The smuggler contradicted his own authored notes twice ("The cargo's gone" beside
"hiding up with the cargo"), a lifelong resident said "I do not know of any healers or
temples" in a city with a cathedral, and a deckhand of a ship with an empty hold said "We
were hauling trade goods for the guild". 60: the player's quoted line came back edited ("You
said" -> "You mentioned"). 64: reported speech kept its frame ("to the effect that tell the
smuggler I'll be back").
"""
from __future__ import annotations

from gm import beat_verify, judgement, planned
from rules import places as places_mod
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene, reported_speech
from rules.sheet import load_pc


def _town(world, faith: bool = False):
    """A settlement with places to name (and a house of faith, with `faith`), the party
    stood in it, and one person beside them."""
    for row in world.play.get("settlements") or []:
        s = Scene(location_id=row["id"])
        s.add(load_pc("fixtures/pc-kesst.json"))
        e = Engine(s, Dice(seed=3), world=world)
        e.place_party()
        urban = [p for p in e.places() if places_mod.terrain_of(p.id) == places_mod.URBAN
                 and places_mod.setting_of(p.id) == "in"]
        if faith and not any(places_mod.category_of(p.kind or p.name) == "faith"
                             for p in urban if p.id != s.at):
            continue
        if len(urban) > 3:
            born = e._bring_in("commoner-level-1", count=1, name="the gardener")
            return s, e, s.people[born[0]["ref"]]
    raise AssertionError("no settlement with places")


# --- 64: reported speech loses its frame -----------------------------------------------------

def test_tell_the_one_spoken_to_by_a_shorter_name_loses_the_frame():
    """#64: "speaks to the starving smuggler, to the effect that tell the smuggler I'll be
    back for the beast" — the smuggler named by article and head noun, not the full name."""
    said = reported_speech("Vesna Kroll", " to the starving smuggler",
                           "tell the smuggler I'll be back for the beast.",
                           "the starving smuggler")
    assert said == ("Vesna Kroll speaks to the starving smuggler, to the effect that I'll be "
                    "back for the beast.")
    assert reported_speech("V", " to the guard", "tell him I will be back.", "the guard") \
        .endswith("to the effect that I will be back.")
    # "about" is no statement: told as it was said.
    assert reported_speech("V", " to the old smith", "tell the smith about the sword.",
                           "the old smith").endswith("to the effect that tell the smith "
                                                     "about the sword.")


# --- 60: the player's quoted line is quoted, word for word ---------------------------------

def test_a_say_whose_words_are_the_players_quotation_is_marked_quoted():
    """#60: the planner wrote the say, `inject_say` stood aside, and the tell reported the
    quoted line ("to the effect that …") for the slot to retell in its own words."""
    line = ('"You said the beast ate your crew. Where is this cargo of yours, and is there '
            'anything down here to bind a wound?"')
    out = judgement.own_words_only([{"op": "say", "params": {"to": "c28"}}], line, None)
    assert out[0]["params"]["quoted"] is True
    words = line.strip('"')
    kept = judgement.own_words_only([{"op": "say", "params": {"words": words}}], line, None)
    assert kept[0]["params"]["quoted"] is True
    # Reported speech stays reported.
    told = judgement.own_words_only(
        [{"op": "say", "params": {"words": "I'll be back for the beast."}}],
        "I tell the smuggler I'll be back for the beast.", None)
    assert not told[0]["params"].get("quoted")


def test_a_quotation_that_is_not_the_players_words_is_found():
    """#60: "You said the beast ate your crew" came back quoted as "You mentioned the beast
    ate your crew"; the words as typed pass."""
    words = ("You said the beast ate your crew. Where is this cargo of yours, and is there "
             "anything down here to bind a wound?")
    wrong = ('"You mentioned the beast ate your crew," you say, looking at the smuggler. '
             '"Where is your cargo, and is there anything down here to bind a wound?"')
    assert len(planned.misquoted(wrong, words)) == 2
    right = ('You turn to the smuggler and ask, "You said the beast ate your crew. Where is '
             'this cargo of yours, and is there anything down here to bind a wound?"')
    assert planned.misquoted(right, words) == []
    assert planned.misquoted("You ask the smuggler where the cargo is.", words) == []


def test_the_say_slot_carries_the_words_to_hold_its_quotes_to(worlds):
    s, e, gardener = _town(worlds)
    talk = [Outcome("i1", "say", tell=f'Kesst says to {gardener.name}: "Where is a temple?"',
                    effects=[{"kind": "said", "who": "", "to": gardener.ref,
                              "words": "Where is a temple?"}])]
    slots = planned.build_plan(e, '"Where is a temple?"', talk, last_beat="")
    fact = next(x for x in slots if x["key"].startswith("fact"))
    assert fact["verbatim"] == "Where is a temple?"


# --- 54/58/66/96: what a person knows -------------------------------------------------------

def test_a_resident_knows_the_settlements_places_and_its_houses_of_faith(worlds):
    """#66: "I do not know of any healers or temples" with the cathedral half an hour off.
    The person stood in a settlement with one, by kind, with the way there."""
    s, e, gardener = _town(worlds, faith=True)
    known = planned.known_to(e, gardener.ref)
    faith = [k for k in known if "temples, shrines" in k]
    assert faith, known
    names = [p.name for p in e.places() if places_mod.category_of(p.kind or p.name) == "faith"
             and places_mod.setting_of(p.id) == "in" and p.id != s.at]
    assert any(n in faith[0] for n in names)
    # Not the stat block's line ("CR 1/2 humanoid"): that is nothing they know.
    assert not any(k.startswith("About") and "CR " in k for k in known)


def test_the_reply_slot_is_given_what_they_know_and_marked_for_the_read_back(worlds):
    s, e, gardener = _town(worlds)
    gardener.notes = "Has kept these gardens forty years; says the old well is poisoned."
    talk = [Outcome("i1", "say", tell=f"Kesst speaks to {gardener.name}.",
                    effects=[{"kind": "said", "who": "", "to": gardener.ref,
                              "words": "where can I pray"}])]
    slots = planned.build_plan(e, "I ask the gardener where I can pray.", talk,
                               last_beat="The gardener weeds.")
    reply = next(x for x in slots if x["key"] == "reply")
    assert any("forty years" in k for k in reply["knows"])
    assert "WHAT THEY KNOW" in reply["knows_said"] and "forty years" in reply["knows_said"]
    # Shown to the reply's own call, not the PLAN every slot reads.
    plan = planned.plan_messages("", slots, planned.present(e), "here")
    assert "forty years" not in plan[1]["content"]
    i = slots.index(reply)
    assert "forty years" in planned.slot_messages(plan, slots, i, [])[1]["content"]


def test_a_crewman_knows_an_empty_hold_is_empty(worlds):
    """#96: "We were hauling trade goods for the guild" off a ship with no cargo record and a
    hold searched empty. Her crew know her hold from the party's cargo records alone."""
    from rules import ships

    s, e, _gardener = _town(worlds)
    ship = ships.Vessel(id="ship-sailing-ship-test", name="the Grey Hen", kind="sailing ship",
                        hp=125, held_by="pc")
    s.vessels = [ship.as_dict()]
    deck = ships.deck_of(ship)
    born = e._bring_in("commoner-level-1", count=1, name="a deckhand")
    hand = s.people[born[0]["ref"]]
    s.move("pc", deck)
    s.move(hand.ref, deck)
    known = planned.known_to(e, hand.ref)
    assert any("Grey Hen's hold" in k and "no cargo" in k for k in known), known
    assert any("held now by the player" in k for k in known)


def test_a_reply_against_what_the_speaker_knows_is_asked_again_then_cut(monkeypatch):
    """#58: "The cargo's gone, lost to the beast's hunger" beside notes saying he is hiding
    up with the cargo. Read back (`known`), asked once more with the fact named; a remake
    still against it loses that sentence and keeps the rest."""
    fact = "About the smuggler: hiding up with the cargo."
    # As the slot holds it: tags lifted (`GMAgent._lift`).
    first = "'The cargo's gone. The beast is in the pool,' the smuggler says."
    asked = []

    def fake_ask(out, plan, slots, i, written, who, **kw):
        asked.append(kw.get("redo", ""))
        out.calls.append({"key": "reply"})
        return first, {}

    def known(speaker, text, facts):
        r = beat_verify.TellsRead()
        if "gone" in text:
            r.clashes.append(beat_verify.TellClash("'The cargo's gone.", fact, 1, "cargo's gone"))
        return r

    monkeypatch.setattr(planned, "_ask", fake_ask)
    out = planned.Planned(text="", slots=[])
    s = {"key": "reply", "speaker_name": "the smuggler", "knows": [fact]}
    got = planned._knowledge_kept(out, [], [s], 0, [], ("m", "", "", ""), s, first, known,
                                  final=False, lift=None, core=True)
    assert fact in asked[0]
    assert "gone" not in got and "pool" in got
    assert any("cut" in n for n in out.notes)

    # A remake that keeps to it stands.
    def fake_ask_fixed(out, plan, slots, i, written, who, **kw):
        out.calls.append({"key": "reply"})
        return "'It is here with me,' the smuggler says.", {}

    monkeypatch.setattr(planned, "_ask", fake_ask_fixed)
    out = planned.Planned(text="", slots=[])
    got = planned._knowledge_kept(out, [], [s], 0, [], ("m", "", "", ""), s, first, known,
                                  final=False, lift=None, core=True)
    assert "here with me" in got and any("fixed" in n for n in out.notes)


def test_the_knowledge_read_has_its_own_demonstrations_of_professed_ignorance():
    """#66: the tells read passed "I do not know of any healers or temples" (3 of 3) — its
    demonstrations are deeds. With `speaker` the read is the knowledge one, whose first
    demonstration is that shape; measured 2026-11-17 on gemma-4-12B: the three recorded
    replies (#58, #66, #96) caught 3 of 3, four grounded replies passed 4 of 4."""
    msgs = beat_verify.known_messages(["I do not know."], ["F"], "the gardener")
    assert msgs[0]["content"] == beat_verify._KNOWN_SYSTEM
    assert "priests or shrines" in msgs[1]["content"]
    seen = {}

    class Reply:
        text = '{"1": {"verdict": "not about it", "fact": "none", "words": ""}}'

        def json(self):
            import json
            return json.loads(self.text)

    def chat(msgs, *a, **k):
        seen["system"] = msgs[0]["content"]
        return Reply()

    beat_verify.against_tells("'I do not know,' she says.", ["F one."], speaker="her",
                              chat=chat)
    assert seen["system"] == beat_verify._KNOWN_SYSTEM
