"""Companions take spoken orders — as themselves.

The owner's ruling, 2026-10-01:

> *"I dont want control of companions they should take spoken orders as their character
> dictates they would or would not and interpret those orders according to their
> character as well."*

So there is no order button. What was measured before this file:

  1. **A companion had no turn in a fight.** `_ensure_encounter` drew the sides between
     the player and whoever they swung at; a companion was a BYSTANDER — off the
     initiative — so an order to them had nowhere to land. Bob, the claimed construct,
     stood through every swing unless the prose happened to have him join.
  2. **A companion who swung first opened the fight AGAINST the player**: the
     struck-first branch put every non-PC initiator on "them".
  3. **The player's plan acted for companions on the player's turn** (live replay,
     2026-10-01): to "Bob, attack the thug! Drover, help me pin him down!" the plan wrote
     `move` for Bob and `attack` for the drover — the drover struck before his own
     initiative came round, and Bob moved twice in one round.
  4. **A companion's turn was shown the creature examples**, every one of which attacks
     "pc" — the shape a copying model turns on the player with.
  5. **The closing check read an ally as an attacker** (same replay): Bob "charges
     across the distance" at the thug, the check cut it as Bob reaching the player, and
     the beat ended "The Bob is still 15 feet from you."
"""
from __future__ import annotations

import json

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


def _friend(s, e, name="Marra", mood="friendly", timid=False):
    who = instantiate("guildhand", scene=s, name=name)
    s.add(who)
    e.settle_attitude(who, mood, None, "test")
    _run(e, {"op": "company", "actor": s.pc().ref, "because": "t",
             "params": {"who": who.ref}})
    assert who.has_state(states.TRAVELS_WITH_YOU)
    if timid:
        s.population[f"p-{who.ref}"] = {"ref": who.ref, "life": {
            "traits": ["cautious", "timid"],
            "shows": ["keeps a door at their back and a reason to leave ready"],
            "axes": {"courage": 12}, "wants": "a farm of their own", "quirk": ""}}
    return who


def _owned(s, e, name="Bob"):
    """A claimed construct, as the constructs house rule leaves it."""
    bob = _friend(s, e, name=name, mood="friendly")
    bob.apply_effect(ActiveEffect(
        name="yours", kind="bond", key=f"claim:{bob.ref}:owned",
        source=f"claim:{bob.ref}", origin="rule:test", duration="until-dismissed",
        tags=(states.OWNED_BY_YOU,)))
    e.settle_attitude(bob, "devoted", None, "test")
    return bob


def _thug(s, name="thug"):
    t = instantiate("thug", scene=s, name=name)
    s.add(t)
    return t


# --- 1. in the fight, on the player's side ------------------------------------------------

class TestCompanionsAreInTheFight:
    def test_a_swing_opens_the_fight_with_the_companions_in_the_order(self):
        """Defect 1: before this, sides were {"pc": ["pc"], "them": [thug]} and Marra and
        Bob were bystanders with no turn."""
        s, e, pc = _party()
        marra, bob, thug = _friend(s, e), _owned(s, e), _thug(s)
        assert e._ensure_encounter(pc.ref, thug.ref)
        order = [r for r, _ in s.initiative]
        assert marra.ref in order and bob.ref in order
        assert set(s.sides["pc"]) == {pc.ref, marra.ref, bob.ref}
        assert s.sides["them"] == [thug.ref]
        assert not marra.has_condition(states.BYSTANDER_KEY)

    def test_the_initiator_keeps_the_turn_they_declared(self):
        """Joining through `enrol` keeps the turn where it was: a companion who rolls
        above the player does not take the action the player just declared."""
        for seed in range(8):
            s, e, pc = _party(seed=seed)
            _friend(s, e), _owned(s, e)
            thug = _thug(s)
            e._ensure_encounter(pc.ref, thug.ref)
            assert s.turn_holder() == pc.ref, seed

    def test_a_declared_fight_brings_them_in_too(self):
        """`begin_encounter` names its own sides; a companion the GM left out still
        comes in on the player's side — one fight, whichever door."""
        s, e, pc = _party()
        marra, thug = _friend(s, e), _thug(s)
        _run(e, {"op": "begin_encounter", "because": "t",
                 "params": {"sides": {"you": [pc.ref], "them": [thug.ref]}}})
        assert marra.ref in s.sides["you"]
        assert marra.ref in [r for r, _ in s.initiative]

    def test_a_companion_who_is_down_does_not_rise_for_it(self):
        s, e, pc = _party()
        marra, thug = _friend(s, e), _thug(s)
        marra.hp = -1
        marra.add_condition("dying", None, source="test")
        e._ensure_encounter(pc.ref, thug.ref)
        assert marra.ref not in [r for r, _ in s.initiative]

    def test_a_stranger_in_the_room_stays_a_bystander(self):
        """Only `bond.travels-with-you` brings somebody in: the merchant watching is not
        drawn into the player's fight (the 2026-09-06 servant on the wrong side)."""
        s, e, pc = _party()
        _friend(s, e)
        merchant = instantiate("guildhand", scene=s, name="merchant")
        s.add(merchant)
        merchant.add_condition(states.BYSTANDER_KEY, None, source="test")
        thug = _thug(s)
        e._ensure_encounter(pc.ref, thug.ref)
        assert merchant.ref not in [r for r, _ in s.initiative]

    def test_a_companion_who_swings_first_swings_for_the_party(self):
        """Defect 2: an order out of a fight ("Bob, attack the thug") planned as Bob's
        attack opened the fight with Bob on "them" — against the player."""
        s, e, pc = _party()
        bob, thug = _owned(s, e), _thug(s)
        assert e._ensure_encounter(bob.ref, thug.ref)
        assert bob.ref in s.sides["pc"] and pc.ref in s.sides["pc"]
        assert s.sides["them"] == [thug.ref]


# --- 2. what they heard, and who they are --------------------------------------------------

class TestWhatTheyHeard:
    def test_the_players_lines_that_name_them_newest_first(self):
        from gm import companions

        s, e, pc = _party()
        bob = _owned(s, e)
        transcript = [
            {"who": "player", "text": "Bob, keep watch by the door."},
            {"who": "gm", "text": "Bob goes to the door."},
            {"who": "player", "text": "I ask the barkeep for a room."},
            {"who": "player", "text": "Is Bob any good in a fight?", "kind": "aside"},
            {"who": "player", "text": "I tell Bob to attack the thug."},
        ]
        assert companions.orders_for(s, bob.ref, transcript) == [
            "I tell Bob to attack the thug.", "Bob, keep watch by the door."]

    def test_words_said_to_them_in_conversation_count_without_their_name(self):
        """The conversation log books the quoted words with who they were said to; "Keep
        watch." to the one person you are talking to is an order to them."""
        from gm import companions

        s, e, pc = _party()
        marra = _friend(s, e)
        s.conversation_log = [
            {"n": 1, "who": "you", "kind": "line", "text": "Keep watch.", "to": marra.ref,
             "among": [marra.ref]},
            {"n": 2, "who": "you", "kind": "line", "text": "Nice weather.", "to": "c99",
             "among": ["c99"]},
        ]
        assert companions.orders_for(s, marra.ref, []) == ['"Keep watch."']

    def test_bounded(self):
        from gm import companions

        s, e, pc = _party()
        bob = _owned(s, e)
        transcript = [{"who": "player", "text": f"Bob, step {n}."} for n in range(10)]
        got = companions.orders_for(s, bob.ref, transcript)
        assert len(got) == companions.MAX_ORDERS and got[0] == "Bob, step 9."

    def test_who_they_are_is_words_and_never_a_number(self):
        """The third law: the narrator hears how somebody feels, never what they score.
        The life record carries the axis scores; none may reach the prompt."""
        from gm import companions

        s, e, pc = _party()
        drover = _friend(s, e, name="Wil", timid=True)
        said = companions.who_they_are(s, drover)
        assert "timid" in said and "door at their back" in said
        assert "friendly" in said and "free to say no" in said
        assert "farm" not in said            # wants are learned in play, never told
        assert not any(ch.isdigit() for ch in said)
        bob = _owned(s, e)
        assert "devoted" in companions.who_they_are(s, bob)


# --- 3. the companion's own turn ----------------------------------------------------------

class TestTheirOwnTurn:
    def _fight(self):
        s, e, pc = _party()
        bob, thug = _owned(s, e), _thug(s)
        e._ensure_encounter(pc.ref, thug.ref)
        return s, e, pc, bob, thug

    def test_the_prompt_shows_companion_examples_not_creature_ones(self):
        """Defect 4: every creature example attacks "pc". A companion's prompt carries
        the companion examples instead, filled with its real foe."""
        from gm import companions, prompts

        s, e, pc, bob, thug = self._fight()
        facts = companions.turn_facts(s, bob, ["Bob, attack the thug!"])
        msgs = prompts.npc_turn_messages("BRIEF", [], bob.ref, bob, 1,
                                         companion=facts, foe=(thug.ref, thug.name))
        replies = [json.loads(m["content"]) for m in msgs if m["role"] == "assistant"]
        assert len(replies) == len(prompts.COMPANION_EXAMPLES)
        for r in replies:
            for i in r["intents"]:
                assert i.get("target") in (None, thug.ref)
                assert i.get("actor") in (None, bob.ref)
        last = msgs[-1]["content"]
        assert "Bob, attack the thug!" in last and "decides what to do" in last
        assert f"{thug.ref} (thug)" in last
        # A creature that is not a companion still gets the creature examples.
        plain = prompts.npc_turn_messages("BRIEF", [], thug.ref, thug, 1)
        assert any('"target": "pc"' in m["content"] for m in plain
                   if m["role"] == "assistant")

    def test_the_examples_obey_bend_and_refuse(self):
        """Demonstration volume over instruction: the three answers the ruling names —
        would, would not, and interpreted — are each shown once."""
        from gm import prompts

        ops = [[i["op"] for i in ex["reply"]["intents"]] for ex in prompts.COMPANION_EXAMPLES]
        assert ["attack"] in ops and ["narrate_only"] in ops
        asks = " ".join(ex["ask"] for ex in prompts.COMPANION_EXAMPLES)
        assert "devoted" in asks and "timid" in asks and "short-fused" in asks

    def test_turning_on_the_party_is_refused_with_the_fix_named(self):
        from gm import companions

        s, e, pc, bob, thug = self._fight()
        why = companions.turning_on_the_party(
            s, bob.ref, [{"op": "attack", "actor": bob.ref, "target": pc.ref}])
        assert "does not strike the player" in why and thug.ref in why
        assert companions.turning_on_the_party(
            s, bob.ref, [{"op": "attack", "actor": bob.ref, "target": thug.ref}]) == ""
        # Not a companion: no opinion.
        assert companions.turning_on_the_party(
            s, thug.ref, [{"op": "attack", "actor": thug.ref, "target": pc.ref}]) == ""

    def test_npc_turn_sends_a_turn_on_the_player_back(self, monkeypatch):
        """The model copies; the engine refuses. A first reply striking the player is
        corrected, and the second — at the thug — is what runs."""
        from gm import agent as agent_mod, client

        s, e, pc, bob, thug = self._fight()
        replies = iter([
            {"narration": "Bob turns.", "intents": [
                {"op": "attack", "actor": bob.ref, "target": pc.ref}]},
            {"narration": "Bob goes for the thug.", "intents": [
                {"op": "attack", "actor": bob.ref, "target": thug.ref}]},
        ])
        seen = []

        def chat(messages, model, *a, **kw):
            seen.append(messages)
            return client.Reply(json.dumps(next(replies)), 0.1, model)

        monkeypatch.setattr(agent_mod.client, "chat", chat)
        gm = agent_mod.GMAgent(WORLD, e)
        plan = gm.npc_turn(bob.ref, location=WORLD.get(TOWN),
                           orders=["Bob, attack the thug!"])
        assert [(i.op, i.target) for i in plan.intents] == [("attack", thug.ref)]
        assert any("does not strike the player" in r for r in plan.rejections)
        assert "Bob, attack the thug!" in seen[0][-1]["content"]

    def test_with_no_model_a_friend_holds_back_and_a_construct_fights(self):
        """Not forced by code: the fallback that swings for a creature does not decide
        for a friend. A claimed construct "follows and obeys" by the house rule."""
        from gm import judgement

        s, e, pc = _party()
        marra, bob, thug = _friend(s, e), _owned(s, e), _thug(s)
        e._ensure_encounter(pc.ref, thug.ref)
        assert judgement.default_npc_action(s, marra.ref) is None
        planned = judgement.default_npc_action(s, bob.ref)
        assert planned and planned[-1]["op"] in ("attack", "move")


# --- 4. the player's turn does not act for them --------------------------------------------

class TestThePlayersTurn:
    def test_in_a_fight_the_plan_does_not_act_for_a_companion(self):
        """Defect 3, measured live: the drover's `attack` and Bob's `move` rode the
        player's plan. Dropped, and noted; the player's own intents stay."""
        from gm import companions

        s, e, pc = _party()
        marra, bob, thug = _friend(s, e), _owned(s, e), _thug(s)
        e._ensure_encounter(pc.ref, thug.ref)
        notes = []
        raw = [{"op": "move", "actor": bob.ref, "target": thug.ref},
               {"op": "attack", "actor": marra.ref, "target": thug.ref},
               {"op": "attack", "actor": pc.ref, "target": thug.ref},
               {"op": "say", "params": {"to": bob.ref, "words": "Bob, attack!"}}]
        kept = companions.on_their_own_turn(raw, s, notes=notes)
        assert [r["op"] for r in kept] == ["attack", "say"]
        assert kept[0]["actor"] == pc.ref
        assert len(notes) == 2

    def test_out_of_a_fight_the_plan_may(self):
        """No turn of theirs to wait for: "Bob, go and ask the barkeep" may be Bob's
        own `say`, decided in character by the plan the brief informs."""
        from gm import companions

        s, e, pc = _party()
        bob = _owned(s, e)
        raw = [{"op": "move", "actor": bob.ref, "params": {"square": [3, 3]}}]
        assert companions.on_their_own_turn(raw, s) == raw


# --- 5. the brief, and the prose checks ---------------------------------------------------

class TestTheBriefAndTheProse:
    def test_the_brief_says_their_answer_is_their_own(self):
        from gm import prompts

        s, e, pc = _party()
        marra, bob = _friend(s, e), _owned(s, e)
        brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN), recent=[], turn=1,
                                    here=e.here(), known=e.places())
        assert "answers as themselves" in brief and "a friend, not a servant" in brief
        assert "Bob BELONGS TO the player" in brief
        assert "acts only on their own turn" not in brief

    def test_in_a_fight_the_brief_says_they_act_on_their_own_turn(self):
        """The replay's player beat had the drover tackle the thug before his turn."""
        from gm import prompts

        s, e, pc = _party()
        marra, thug = _friend(s, e), _thug(s)
        e._ensure_encounter(pc.ref, thug.ref)
        brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN), recent=[], turn=1,
                                    here=e.here(), known=e.places())
        assert "Marra acts only on their own turn" in brief

    def test_an_ally_closing_on_a_foe_is_not_closing_on_the_player(self):
        """Defect 5: "The Bob is still 15 feet from you." was the backstop's line after
        cutting Bob's charge at the thug."""
        from gm.checks import closing_claimed

        s, e, pc = _party()
        bob, thug = _owned(s, e), _thug(s)
        e._ensure_encounter(pc.ref, thug.ref)

        class Ctx:
            scene, acting = s, bob.ref
            text = "Bob charges, closing the distance."

        assert closing_claimed._gap(Ctx) is None

        class Theirs(Ctx):
            acting = thug.ref

        if s.has_grid and s.distance_between(thug.ref, pc.ref) is not None:
            assert closing_claimed._gap(Theirs) is not None
