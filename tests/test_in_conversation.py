"""A conversation is a state you are in, and only three things end it.

Ruled 2026-09-24: *"a discussion/conversation should be only while directly speaking to
a person or being spoken to you must end the conversation or walk away purposefully"*,
with the exit on a button, the option to refuse somebody who speaks to you, and a
panel naming everyone in it.

Everweave's Dialogue Mode (Update 15, "Friends & Strangers") is the measured warning.
Its exits were implicit — the studio's own notes say "you may need to state more
clearly when you want to leave a conversation" — scenes ended too early or not at all,
NPCs called for skill checks in ordinary talk, and the studio shipped a Creative Mode
that bypasses the whole system. So here the state is engine-held (`states.TALKING` on
the person, through the one applicator), the exit is one op and one engine-only button,
and nobody in a conversation ever asks the player to roll.
"""
from __future__ import annotations

from gm import judgement
from rules import attitude, places as places_mod, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world import loader
from pagesource import table_source

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"
MARKET = f"{TOWN}~urban:the-market"


def _table(seed: int = 5):
    s = Scene(location_id=TOWN)
    pc = instantiate("guildhand", scene=s, name="Kesst")
    pc.kind = "pc"
    s.add(pc)
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party(MARKET)
    grix = s.add(instantiate("guildhand", scene=s, name="Grix"))
    return s, e, pc, grix


def _run(e, pc, raws):
    return e.run(e.validate(raws, origin="author:test")).outcomes


def _say(e, pc, words, to=None):
    params = {"words": words}
    if to:
        params["to"] = to
    return _run(e, pc, [{"op": "say", "actor": pc.ref, "because": "t", "params": params}])


class TestItOpens:
    def test_speaking_to_somebody_opens_it(self):
        s, e, pc, grix = _table()
        assert e.talking_to() == []
        out = _say(e, pc, "Good morning.", to=grix.ref)
        assert grix.has_state(states.TALKING)
        assert [a.ref for a in e.talking_to()] == [grix.ref]
        assert "in conversation with Grix" in out[0].tell

    def test_speaking_in_a_room_with_one_other_person_is_speaking_to_them(self):
        s, e, pc, grix = _table()
        # Somewhere with nobody behind a counter: the market has its keeper.
        quiet = next(p for p in e.places() if p.id != s.at and not p.described_only
                     and p.terrain == places_mod.URBAN)
        s.move(pc.ref, quiet.id)
        s.move(grix.ref, quiet.id)
        assert [a.name for a in s.actors.values() if not a.is_pc] == ["Grix"]
        _say(e, pc, "Good morning.")
        assert grix.has_state(states.TALKING)

    def test_speaking_into_a_crowd_names_nobody(self):
        s, e, pc, grix = _table()
        s.add(instantiate("guildhand", scene=s, name="Marra"))
        _say(e, pc, "Good morning.")
        assert e.talking_to() == []

    def test_being_spoken_to_opens_it_from_their_side(self):
        s, e, pc, grix = _table()
        refs = judgement.hailed_by(
            s, "Grix looks up from his ale. 'You're a long way from the interior,' he "
               "says. The rain keeps on.")
        assert refs == [grix.ref]
        assert e.join_talk(grix, how="they spoke to you") == "Grix is talking to you."
        assert grix.has_state(states.TALKING)

    def test_somebody_talking_to_a_third_party_is_not_talking_to_you(self):
        s, e, pc, grix = _table()
        assert judgement.hailed_by(
            s, "'Fine weather for it,' Grix tells the carter.") == []


class TestItEndsOnlyThreeWays:
    def test_silence_does_not_end_it(self):
        s, e, pc, grix = _table()
        _say(e, pc, "Good morning.", to=grix.ref)
        for _ in range(3):
            _run(e, pc, [{"op": "narrate_only", "actor": pc.ref, "because": "t",
                          "params": {}}])
        assert grix.has_state(states.TALKING)

    def test_taking_your_leave_ends_it(self):
        s, e, pc, grix = _table()
        _say(e, pc, "Good morning.", to=grix.ref)
        out = _run(e, pc, [{"op": "leave_talk", "actor": pc.ref, "because": "t",
                            "params": {}}])[-1]
        assert out.tell == "You take your leave of Grix."
        assert not grix.has_state(states.TALKING)

    def test_refusing_somebody_who_spoke_to_you(self):
        s, e, pc, grix = _table()
        e.join_talk(grix, how="they spoke to you")
        out = _run(e, pc, [{"op": "leave_talk", "actor": pc.ref, "because": "t",
                            "params": {"who": grix.ref, "do": "ignore"}}])[-1]
        assert "do not answer Grix" in out.tell
        assert not grix.has_state(states.TALKING)

    def test_leaving_when_nobody_is_talking_is_refused_in_words(self):
        s, e, pc, grix = _table()
        out = _run(e, pc, [{"op": "leave_talk", "actor": pc.ref, "because": "t",
                            "params": {}}])[-1]
        assert out.status == "refused" and "not in conversation" in out.tell

    def test_walking_away_ends_it_and_says_so(self):
        s, e, pc, grix = _table()
        _say(e, pc, "Good morning.", to=grix.ref)
        far = next(p for p in e.places() if p.id != s.at and not p.described_only
                   and p.terrain == places_mod.URBAN)
        out = _run(e, pc, [{"op": "travel", "actor": pc.ref, "because": "t",
                            "params": {"place": far.name}}])[-1]
        assert "leave Grix mid-sentence" in out.tell, out.tell
        assert not grix.has_state(states.TALKING)

    def test_a_fight_starting_ends_it(self):
        s, e, pc, grix = _table()
        _say(e, pc, "Good morning.", to=grix.ref)
        e._ensure_encounter(pc.ref, target=grix.ref)
        assert s.in_encounter
        assert not grix.has_state(states.TALKING)

    def test_the_other_party_leaving_the_room_ends_it_said(self):
        s, e, pc, grix = _table()
        _say(e, pc, "Good morning.", to=grix.ref)
        far = next(p for p in e.places() if p.id != s.at and not p.described_only)
        s.move(grix.ref, far.id)
        tells = [o.tell for o in _run(e, pc, [{"op": "narrate_only", "actor": pc.ref,
                                               "because": "t", "params": {}}])]
        assert any("no longer here" in t for t in tells), tells
        assert not grix.has_state(states.TALKING)

    def test_people_can_join_and_be_named_together(self):
        s, e, pc, grix = _table()
        marra = s.add(instantiate("guildhand", scene=s, name="Marra"))
        _say(e, pc, "Good morning.", to=grix.ref)
        _say(e, pc, "And you.", to=marra.ref)
        assert {a.name for a in e.talking_to()} == {"Grix", "Marra"}
        out = _run(e, pc, [{"op": "leave_talk", "actor": pc.ref, "because": "t",
                            "params": {}}])[-1]
        assert "Grix" in out.tell and "Marra" in out.tell


class TestWhatItShuts:
    def test_rest_is_refused_mid_sentence(self):
        s, e, pc, grix = _table()
        _say(e, pc, "Good morning.", to=grix.ref)
        out = _run(e, pc, [{"op": "rest", "actor": pc.ref, "because": "t",
                            "params": {"kind": "night"}}])[-1]
        assert out.status == "refused" and "Take your leave first" in out.tell

    def test_the_craft_hub_says_why_it_is_shut(self):
        s, e, pc, grix = _table()
        _say(e, pc, "Good morning.", to=grix.ref)
        why = e._too_busy_to_forage(pc)
        assert why.startswith("You are talking with Grix.")

    def test_trade_and_casting_are_not_shut_by_talk(self):
        """Yes to both, at the table: buying is a conversation, and a spell cast in
        front of people is allowed and seen."""
        from rules import intents

        assert "leave_talk" in intents.OPS
        s, e, pc, grix = _table()
        _say(e, pc, "Good morning.", to=grix.ref)
        # Nothing in the give or cast path asks `talking_to`; the refusals above are
        # the only two readers, and this pins that list.
        from pathlib import Path

        src = Path("rules/engine.py").read_text(encoding="utf-8")
        readers = [ln for ln in src.splitlines()
                   if "self.talking_to()" in ln and "def " not in ln]
        assert len(readers) == 3, readers     # rest, craft, leave_talk


class TestTheThreeLaws:
    def test_the_state_is_a_tag_through_the_one_applicator(self):
        s, e, pc, grix = _table()
        _say(e, pc, "Good morning.", to=grix.ref)
        held = [x for x in grix.effects if states.TALKING in x.tags]
        assert len(held) == 1 and held[0].source == "talk"
        grix.remove_effects(source="talk")
        assert e.talking_to() == [], "remove the effect and the state evaporates"

    def test_no_reader_spells_the_tag(self):
        from pathlib import Path

        for f in ("rules/engine.py", "play/views.py", "gm/prompts.py"):
            assert '"talk.with-you"' not in Path(f).read_text(encoding="utf-8"), f


class TestThePanel:
    def test_the_page_carries_the_panel_and_its_button(self):
        from pathlib import Path

        html = table_source()
        assert 'id="talk"' in html and 'id="takeleave"' in html
        assert 'post("/api/talk"' in html
        assert "craft.disabled = !!busy" in html

    def test_the_state_says_who_and_how_they_stand(self):
        from play import views

        class C:
            def __init__(self, scene, engine):
                self.scene, self._e = scene, engine

            def engine(self):
                return self._e

        s, e, pc, grix = _table()
        _say(e, pc, "Good morning.", to=grix.ref)
        got = views._talk_state(C(s, e))
        assert got and got[0]["name"] == "Grix"
        assert got[0]["attitude"] in states.ATTITUDES
        assert 0 <= got[0]["regard"] <= attitude.REGARD_MAX
        assert views._busy_state(C(s, e)).startswith("You are talking with Grix")
