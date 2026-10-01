"""Companions do things as themselves, act unasked, and speak up unasked.

The owner's rulings, 2026-10-01:

> *"I dont want control of companions they should take spoken orders as their character
> dictates they would or would not and interpret those orders according to their
> character as well."*

> *"they can comply but it should be narrated that they did so in a way that was timid
> and matched their background. I do also want my companion to take action on their own
> if i dont direct them."*

> *"they should also interject their opinions on the things going on or the places we
> go"*

So there is still no engine gate on obedience. What was measured before this file, on
the companions replay (scratch copy of the owner-shaped save: Bob the claimed clockwork
spy, a young drover, a thug; gemma-4-12B; 5 samples a cell, each turn run and undone):

  1. **Undirected friends did nothing.** Told nothing, the timid drover's turn was
     `narrate_only` 5 of 5 ("grips their club tightly ... ready to bolt"), and so was a
     bold one 5 of 5 and a kind one 5 of 5 — the companion examples' only undirected
     turn was a frightened friend hiding behind the player, and every temperament copied
     it. The claimed construct moved on the thug 10 of 10.
  2. **The construct had no manner at all.** Bob's wind-ups read "lunges forward ... his
     small frame moving with a desperate purpose", "grits their teeth against the sting":
     0 of 10 carried anything mechanical or literal — the devoted construct written as a
     frightened little man.
  3. **The timid drover's manner was already there** when he was timid (10 of 10 by hand;
     the first cue lexicon caught only 1 of the 5 undirected ones — "eyes darting toward
     the nearest exit", "ready to bolt", "knuckles white" — and was widened from them).
     So the detector is measured against real output, below, before it is trusted.
  4. **Nothing ever spoke up.** No companion line reached the page unless the player
     addressed them: 0 remarks in the replays.

Prior art, searched before building (2026-10-01):
  * Dragon Age: Inquisition left banter to chance, "on average ... every 10-15 minutes"
    (BioWare blog, 2014-12-08), and patch 3 changed it "to be less random to prevent
    extra-long periods where no conversations would occur" (blog.bioware.com, 2015-01-19)
    — so the cadence here is counted, never rolled.
  * Valve's response rules (Ruskin, GDC 2012, "AI-driven Dynamic Dialog through Fuzzy
    Pattern Matching"): criteria plus a written-back memory with expiry so a gag is not
    replayed too close — here the memory is the conversation log (`src: "interject"`).
  * Half-Life 2: Episode One developer commentary: nagging and unsolicited hints made
    players "hate Alyx" within minutes and were cut — so a remark is an opinion, never
    advice, and advice is refused in code.
  * The Last of Us (Dyckhoff, Game AI Pro 2 ch. 35): Ellie's gifts were put on "a really
    long timer" after a playtest gifting "every minute" devalued them; her reluctance to
    shoot was written as character. Manner as the character, initiative on a timer.
  * Ultima VII: each companion ran its own combat mode with no way to talk to it; Dragon
    Age / FFXII gambits were scripts. Neither: a companion here acts on its own turn as
    itself, from demonstrations.

Not built, reported: an aid-another op. `rules/intents.py` OPS declares `aid` as a param
of `check` and nothing in the engine reads it; no op grants the +2. A timid companion's
"help from safety" therefore uses only what exists — a strike from behind the player, a
blow pulled to non-lethal (`lethality`) — and aid another waits on the owner.
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest

from rules import states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")
TOWN = WORLD.play["settlements"][0]["id"]


def _party(seed=3):
    s = Scene(location_id=TOWN)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 40
    s.add(pc)
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party()
    return s, e, pc


def _run(e, raw):
    return e.run(e.validate(raw if isinstance(raw, list) else [raw],
                            origin="author:test"))


def _friend(s, e, name="Wil", traits=("cautious", "timid"), work="carter"):
    who = instantiate("guildhand", scene=s, name=name)
    s.add(who)
    e.settle_attitude(who, "friendly", None, "test")
    _run(e, {"op": "company", "actor": s.pc().ref, "because": "t",
             "params": {"who": who.ref}})
    s.population[f"p-{who.ref}"] = {"ref": who.ref, "life": {
        "traits": list(traits), "work_name": work,
        "shows": ["keeps a door at their back and a reason to leave ready"],
        "wants": "a coat that keeps the cold out", "quirk": ""}}
    return who


def _owned(s, e, name="Bob"):
    bob = instantiate("guildhand", scene=s, name=name)
    s.add(bob)
    e.settle_attitude(bob, "friendly", None, "test")
    _run(e, {"op": "company", "actor": s.pc().ref, "because": "t",
             "params": {"who": bob.ref}})
    bob.apply_effect(ActiveEffect(
        name="yours", kind="bond", key=f"claim:{bob.ref}:owned",
        source=f"claim:{bob.ref}", origin="rule:test", duration="until-dismissed",
        tags=(states.OWNED_BY_YOU,)))
    e.settle_attitude(bob, "devoted", None, "test")
    return bob


def _thug(s):
    t = instantiate("thug", scene=s, name="thug")
    s.add(t)
    return t


# --- the manner detector, measured against real output ----------------------------------

# The five undirected timid wind-ups of the first replay, verbatim (gemma-4-12B,
# 2026-10-01). Read by hand, all five show it; the first lexicon caught one.
REAL_TIMID = [
    "The young drover grips the club with both hands, their knuckles white. They don't "
    "step forward to engage, but they stand ready to strike if the thug lunges toward you.",
    "The young drover grips their club tightly, their knuckles white. They stay low, "
    "huddling close to your side and watching the thug with wide, wary eyes, waiting for "
    "a signal or a chance to flee if things go south.",
    "The young drover grips their club tightly, eyes darting between the thug and the "
    "nearest exit. They stay low, hunkering down behind you to keep their back to the "
    "escape route.",
    "The young drover grips their club tightly, their knuckles white. They stay close "
    "behind you, eyes darting toward the nearest exit, ready to bolt if the situation "
    "turns dire.",
    "The young drover grips their club tight, but they do not step forward. They stay "
    "low, watching the thug's every move from behind your shoulder, ready to bolt if the "
    "situation turns dire.",
]
# Bob's, the same replay: a claimed construct written as a desperate little man.
REAL_BOB = [
    "Ignoring the sting in their side, Bob lunges forward as far as they can, aiming to "
    "close the gap and strike the thug.",
    "Bob grits their teeth against the sting of their wound and charges forward, their "
    "small frame moving with a desperate, heavy purpose toward the thug.",
    "Bob lunges forward, his small frame moving with a desperate purpose to close the "
    "distance and strike the thug.",
]


class TestTheDetector:
    def test_it_reads_the_timid_wind_ups_the_replay_wrote(self):
        """Measured: 5 of 5 real undirected timid wind-ups show it by hand; the first
        lexicon caught 1 of 5. Widened from them, it reads all five."""
        from gm import companions

        assert all(companions.manner_cues(t, "timid") for t in REAL_TIMID)

    def test_a_desperate_little_man_is_not_a_devoted_construct(self):
        """Measured: 0 of 10 of Bob's wind-ups carried a mechanical manner. The detector
        agrees with the hand count — it does not find what is not there."""
        from gm import companions

        assert not any(companions.manner_cues(t, "devoted") for t in REAL_BOB)

    def test_a_negated_cue_is_not_a_cue(self):
        from gm import companions

        bold = "He does not hesitate and goes straight at the thug, grinning."
        assert companions.manner_cues(bold, "timid") == []
        assert companions.manner_cues(bold, "bold")
        assert companions.manner_cues("Without a sound, Bob turns.", "devoted")

    def test_the_trait_word_is_never_its_own_cue(self):
        """A label is not a manner (CoMPosT; `population.traits_named` counts labels):
        "the timid drover" must not pass as showing timidity."""
        from gm import companions
        from rules import lives

        for axis in lives.tables()["personality"]:
            for side in ("low", "high"):
                pole = axis[side]
                if pole["id"] in companions.MANNER_CUES:
                    label = pole["words"][1]
                    assert not companions.manner_cues(f"the {label} one acts", pole["id"]), label

    def test_every_lexicon_is_a_real_pole(self):
        """The ratchet: a cue set for a temperament the content does not roll is dead."""
        from gm import companions
        from rules import lives

        poles = {axis[side]["id"] for axis in lives.tables()["personality"]
                 for side in ("low", "high")}
        assert set(companions.MANNER_CUES) - {companions.DEVOTED} <= poles


class TestWhoOwesWhat:
    def test_dominant_pole(self):
        from gm import companions

        s, e, pc = _party()
        assert companions.dominant_pole(s, _friend(s, e)) == "timid"
        # A trait with no deed lexicon gives way to the next voiced one.
        assert companions.dominant_pole(
            s, _friend(s, e, name="Ann", traits=("generous", "bold"))) == "bold"
        assert companions.dominant_pole(s, _owned(s, e)) == companions.DEVOTED

    def test_nobody_owes_what_they_do_not_have(self):
        """False positives bounded: a companion whose voiced traits carry no deed-cue
        (money, belief, talk) owes the page nothing, and no repair is called."""
        from gm import companions

        s, e, pc = _party()
        miser = _friend(s, e, name="Odo", traits=("tight-fisted", "trusting"))
        assert companions.dominant_pole(s, miser) == ""
        assert companions.shows_manner("Odo swings at the thug.", miser, "")

    def test_an_order_against_the_grain_is_said_so(self):
        from gm import companions

        s, e, pc = _party()
        wil = _friend(s, e)
        line = companions.manner_line(s, wil, ordered=True, op="attack")
        assert "against their own nerve" in line
        assert "a carter by trade" in line
        assert "timid" in line and not any(ch.isdigit() for ch in line)
        assert "nobody told" in companions.manner_line(s, wil, ordered=False, op="attack")
        assert "against" not in companions.manner_line(s, wil, ordered=True, op="say")


class TestTheActIsKept:
    def test_manner_only_rewrite_is_kept(self):
        from gm import companions

        s, e, pc = _party()
        wil, thug = _friend(s, e), _thug(s)
        old = "Wil swings at the thug and misses."
        new = "Wil swallows, edges in, and swings at the thug with shaking hands and misses."
        assert companions.act_kept(old, new, wil, list(s.actors.values())) == ""

    def test_a_rewrite_that_lands_a_blow_is_thrown_away(self):
        from gm import companions

        s, e, pc = _party()
        wil, thug = _friend(s, e), _thug(s)
        old = "Wil swings at the thug."
        assert companions.act_kept(old, "Wil trembles and swings, and the club hits the "
                                   "thug hard.", wil, list(s.actors.values()))
        assert companions.act_kept(old, "Wil trembles at the thug.", wil,
                                   list(s.actors.values()))          # the swing lost
        assert companions.act_kept(old, "Wil and the PC swing at the thug, shaking.",
                                   wil, list(s.actors.values()))     # somebody added
        # Measured on the replay: a kind drover's repair wrote "pull the blow" over a
        # lethal swing. Whether a blow is pulled is the `lethality` rule's.
        assert "pulls a blow" in companions.act_kept(
            old, "Wil winces and swings at the thug, pulling the blow.", wil,
            list(s.actors.values()))


def _fake(monkeypatch, replies):
    from gm import agent as agent_mod, client

    seen = []
    it = iter(replies)

    def chat(messages, model, *a, **kw):
        seen.append(messages)
        return client.Reply(json.dumps(next(it)), 0.1, model)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    return seen


class TestTheRepair:
    def test_a_construct_turn_with_no_manner_is_repaired(self, monkeypatch):
        """Defect 2: 0 of 10 of Bob's turns had a construct's manner. Now the turn is
        detected and one targeted call rewrites only his sentence, kept because the act
        (closing on the thug) is unchanged."""
        from gm import agent as agent_mod

        s, e, pc = _party()
        bob, thug = _owned(s, e), _thug(s)
        e._ensure_encounter(pc.ref, thug.ref)
        seen = _fake(monkeypatch, [
            {"narration": "Bob lunges toward the thug with desperate purpose.",
             "intents": [{"op": "move", "actor": bob.ref, "target": thug.ref,
                          "because": "told to"}]},
            {"s1": "Bob turns without a sound and lunges toward the thug, joints "
                   "clicking."},
        ])
        gm = agent_mod.GMAgent(WORLD, e)
        plan = gm.npc_turn(bob.ref, location=WORLD.get(TOWN), orders=["Bob, get him!"])
        assert "without a sound" in plan.narration
        assert any("rewrote" in r for r in plan.repairs)
        assert len(seen) == 2

    def test_a_repair_that_changes_the_act_is_not_kept(self, monkeypatch):
        from gm import agent as agent_mod

        s, e, pc = _party()
        bob, thug = _owned(s, e), _thug(s)
        e._ensure_encounter(pc.ref, thug.ref)
        _fake(monkeypatch, [{"s1": "Bob strikes the thug without a sound and he falls."}])
        gm = agent_mod.GMAgent(WORLD, e)
        text, notes, _ = gm.manner_of("Bob swings at the thug.", bob, ordered=True,
                                      op="attack", whole=True)
        assert text == "Bob swings at the thug."
        assert any("did not hold" in n for n in notes)

    def test_a_turn_that_already_shows_it_costs_no_call(self, monkeypatch):
        from gm import agent as agent_mod

        s, e, pc = _party()
        wil = _friend(s, e)
        seen = _fake(monkeypatch, [])
        gm = agent_mod.GMAgent(WORLD, e)
        text, notes, more = gm.manner_of(REAL_TIMID[3].replace("The young drover", "Wil"),
                                         wil, ordered=False, whole=True)
        assert not seen and not more and notes == ["manner: Wil (timid) shown"]


# --- acting unasked -------------------------------------------------------------------

class TestTheDemonstrations:
    def _examples(self):
        from gm import prompts

        out = []
        for ex in prompts.COMPANION_EXAMPLES:
            fill = dict(self_ref="c5", name="Wil", foe_ref="c6", foe="thug")
            out.append((prompts.fill_companion(ex["ask"], **fill),
                        prompts.fill_companion(ex["reply"], **fill)))
        return out

    def test_undirected_friends_act(self):
        """Defect 1: told nothing, every temperament copied the one undirected example —
        a friend hiding behind the player — 15 of 15 narrate_only. The owner: "I do also
        want my companion to take action on their own if i dont direct them." Every
        undirected example now acts."""
        undirected = [r for ask, r in self._examples() if "has told" in ask
                      and "nothing this fight" in ask]
        assert len(undirected) >= 2
        assert all(i["op"] != "narrate_only" for r in undirected for i in r["intents"])

    def test_every_example_shows_the_temper_it_was_given(self):
        """Demonstration volume beats instruction volume: every companion example's
        wind-up carries a cue of the temper its ask names, by the same detector the
        page is held to."""
        from gm import companions

        for ask, reply in self._examples():
            if "belongs to the player" in ask:
                pole = companions.DEVOTED
            else:
                # The trait words, in the order `dominant_pole` reads them.
                words = re.search(r"Wil is ([^.]+)\. in how they act", ask).group(1)
                pole = next(p for p in map(companions._pole_of_word, words.split(", "))
                            if p in companions.MANNER_CUES)
            assert companions.manner_cues(reply["narration"], pole), (pole, reply)

    def test_the_kind_one_pulls_the_blow_by_rule(self):
        """Not a flourish: `lethality` is the engine's rule (non-lethal at -4)."""
        kind = [r for ask, r in self._examples() if "warm, kind" in ask]
        assert kind and kind[0]["intents"][0]["params"] == {"lethality": "nonlethal"}

    def test_the_timid_one_obeys_when_told(self):
        """The second ruling: "they can comply but it should be narrated that they did so
        in a way that was timid". The timid ordered example used to bend the order into
        holding the door; now it is done, shakily."""
        timid = [r for ask, r in self._examples() if "cautious, timid" in ask
                 and "hit him" in ask]
        assert timid and timid[0]["intents"][0]["op"] == "attack"


# --- speaking up unasked --------------------------------------------------------------

def _out(op, tell, effects=(), status="resolved"):
    return SimpleNamespace(op=op, tell=tell, effects=list(effects), status=status)


def _turns(n):
    out = []
    for i in range(n):
        out += [{"who": "player", "text": f"I look around {i}."},
                {"who": "gm", "text": "Nothing much."}]
    return out


class TestWhenTheySpeak:
    def test_the_cadence(self):
        """Counted, never rolled (DA:I patch 3). Fires after INTERJECT_EVERY quiet
        turns, and never twice within INTERJECT_GAP."""
        from gm import companions

        s, e, pc = _party()
        wil = _friend(s, e)
        assert companions.interjection_due(s, [], [])["reason"] == "moment"
        s.conversation_log = [{"n": 1, "who": wil.ref, "kind": "line", "beat": 1,
                               "src": "interject", "text": "hm"}]
        tr = _turns(1)
        assert companions.interjection_due(s, tr, [_out("check", "x dies.")]) is None
        tr = _turns(1) + _turns(companions.INTERJECT_GAP)
        assert companions.interjection_due(s, tr, [_out("check", "The thug dies.")])[
            "reason"] == "event"
        assert companions.interjection_due(s, tr, []) is None
        tr = _turns(1) + _turns(companions.INTERJECT_EVERY)
        assert companions.interjection_due(s, tr, [])["reason"] == "moment"

    def test_never_in_a_fight_never_over_an_answer_never_over_a_conversation(self):
        from gm import companions

        s, e, pc = _party()
        wil, thug = _friend(s, e), _thug(s)
        assert companions.interjection_due(s, [], [], answered=[(wil, "ok")]) is None
        assert companions.interjection_due(s, [], [], talking=[thug]) is None
        assert companions.interjection_due(s, [], [], talking=[wil]) is not None
        # Arriving somewhere ends a conversation anyway: the place is worth a remark.
        due = companions.interjection_due(s, [], [], talking=[thug], moved=True)
        assert due["reason"] == "arrived" and due["arrived"]["first"]
        e._ensure_encounter(pc.ref, thug.ref)
        assert companions.interjection_due(s, [], []) is None

    def test_what_counts_as_notable_is_read_off_the_tells(self):
        """gm/ reads tells, never effect records (the third law's ratchet)."""
        from gm import companions

        assert companions.notable([_out("check", "The guard sees through it.")])
        assert companions.notable([_out("check", "Mira is now friendly.")])
        assert companions.notable([_out("attack", "The thug dies.")])
        assert companions.notable([_out("move", "You walk to the well.")]) == ""
        assert companions.notable([_out("check", "You make the climb check by 3.")]) == ""

    def test_the_least_recently_heard_speaks(self):
        from gm import companions

        s, e, pc = _party()
        wil, ann = _friend(s, e), _friend(s, e, name="Ann")
        s.conversation_log = [{"n": 3, "who": wil.ref, "kind": "line", "text": "x"}]
        assert companions.interjection_due(s, [], [])["ref"] == ann.ref
        s.conversation_log.append({"n": 4, "who": ann.ref, "kind": "line", "text": "y"})
        assert companions.least_recently_heard(s, [wil.ref, ann.ref]) == wil.ref


class TestWhatTheySay:
    @pytest.mark.parametrize("line,why", [
        ('Wil frowns. "We should leave before dark."', "tells the player what to do"),
        ('Wil frowns. "Let\'s go."', "tells the player what to do"),
        ("Wil frowns at the gate.", "no words of theirs"),
        ('Wil frowns. "3 guards on that wall."', "a number"),
        ('"Smells wrong," somebody says.', "does not say it is Wil"),
        ('Wil frowns. "Smells wrong." What do you do?', "hands the turn back"),
    ])
    def test_refused(self, line, why):
        from gm import companions

        s, e, pc = _party()
        wil = _friend(s, e)
        assert why in companions.interjection_refusal(line, wil, {"Wil"})

    def test_an_opinion_passes(self):
        from gm import companions

        s, e, pc = _party()
        wil = _friend(s, e)
        line = 'Wil eyes the shuttered windows. "Smells like a place carts go missing."'
        assert companions.interjection_refusal(line, wil, {"Wil"}) == ""

    def test_the_remark_is_their_speech_in_the_log(self):
        """Recorded as their speech, so the Journal's "What people said" keeps it, and
        marked so the cadence can be read back from it."""
        from play.aftermath import conversation_log

        s, e, pc = _party()
        wil = _friend(s, e)
        text = 'You wait. Wil eyes the gate. "Smells like trouble." What do you do?'
        ctx = SimpleNamespace(
            scene=s, people={r: {"name": a.name, "is_pc": a.is_pc}
                             for r, a in s.actors.items()},
            talking_after=[], text=text, door="turn", player_text="",
            said=[{"who": wil.ref, "to": "", "from": "interject",
                   "line": "Smells like trouble."}],
            campaign=SimpleNamespace(transcript=[]), beat_index=4)
        conversation_log.step(ctx)
        rows = [r for r in s.conversation_log if r["who"] == wil.ref]
        assert rows and rows[-1]["src"] == "interject"
        assert rows[-1]["text"] == "Smells like trouble."

    def test_the_facts_are_words_and_real_names(self, monkeypatch):
        from gm import companions

        s, e, pc = _party()
        wil = _friend(s, e)
        place = SimpleNamespace(name="the Copper Kettle", about="a smoky inn by the gate")
        facts = companions.interject_facts(
            s, wil, {"reason": "arrived", "arrived": {"first": True}}, place=place)
        assert "the Copper Kettle" in facts and "never been here before" in facts
        assert "a carter by trade" in facts
        assert not any(ch.isdigit() for ch in facts)
