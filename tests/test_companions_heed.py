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
  6. **Out of a fight nobody decided.** "Drover, sneak up behind that thug and lift his
     purse for me" was planned as the player's `say` and `narrate_only`, and the page had
     the timid drover "move as if he were part of the shadows"; on a rerun the planner
     wrote the drover's Stealth check itself and the page said "He doesn't hesitate".
     Now the words spoken TO a companion get their own answer (a targeted call), which
     on the replay refused, in character: "That's a one-way ticket to a broken nose."
  7. **An answer handed to the prose as a fact never reached the page**: Bob's "moves to
     the door, standing perfectly still" — the beat did not mention Bob at all.
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

    def test_an_attack_whose_reason_says_not_fighting_is_sent_back(self):
        """Measured: told "Drover, stay back and keep the crowd off me!", the drover's
        turn was `attack` the thug "because they aren't fighting the thug, but are
        physically interceding" — and the engine walked him onto the thug and struck."""
        from gm import companions, prompts

        bad = [{"op": "attack", "actor": "c2", "target": "c3",
                "because": "they aren't fighting the thug, but are physically "
                           "interceding to block the crowd's interference"}]
        assert "narrate_only" in companions.attack_against_its_reason("c2", bad)
        for why in ("cautious and timid; they prefer to keep a safe distance",
                    "too timid to engage, but staying close to the player",
                    "stays back by the door"):
            assert companions.attack_against_its_reason(
                "c2", [dict(bad[0], because=why)]), why
        for why in ("ordered to hit him; they do it with a trembling hand",
                    "wounded and cornered, it fights"):
            assert companions.attack_against_its_reason(
                "c2", [dict(bad[0], because=why)]) == "", why
        # The worked examples never trip the gate they will be held to.
        for ex in prompts.COMPANION_EXAMPLES + prompts.COMPANION_ANSWER_EXAMPLES:
            assert companions.attack_against_its_reason("{Self}", ex["reply"]["intents"]) \
                == "", ex["reply"]

    def test_running_for_help_is_not_a_walk_at_the_foe(self):
        """Measured: "Drover, run and fetch the watch!" came back `move` at the thug
        "because they are fleeing the immediate danger to fetch the watch", and the engine
        closed the drover on the thug."""
        from gm import companions

        s, e, pc = _party()
        drover, thug = _friend(s, e, name="Wil"), _thug(s)
        e._ensure_encounter(pc.ref, thug.ref)
        raw = [{"op": "move", "actor": drover.ref, "target": thug.ref,
                "because": "they are told to fetch the watch, and they are fleeing the "
                           "immediate danger to do so"}]
        assert "narrate_only" in companions.move_against_its_reason(s, drover.ref, raw)
        ok = [dict(raw[0], because="told to keep him off you; they close on him")]
        assert companions.move_against_its_reason(s, drover.ref, ok) == ""

    def test_a_blow_at_an_onlooker_is_sent_back_unless_ordered(self):
        """Measured: told "keep the crowd off me", the drover went for the merchant
        watching from the side."""
        from gm import companions

        s, e, pc = _party()
        drover, thug = _friend(s, e, name="Wil"), _thug(s)
        merchant = instantiate("guildhand", scene=s, name="merchant")
        s.add(merchant)
        merchant.add_condition(states.BYSTANDER_KEY, None, source="test")
        e._ensure_encounter(pc.ref, thug.ref)
        raw = [{"op": "attack", "actor": drover.ref, "target": merchant.ref}]
        why = companions.attack_on_a_bystander(s, drover.ref, raw,
                                               ["Wil, keep the crowd off me!"])
        assert "not in this fight" in why and thug.ref in why
        assert companions.attack_on_a_bystander(
            s, drover.ref, raw, ["Wil, knock that merchant down!"]) == ""
        assert companions.attack_on_a_bystander(
            s, drover.ref, [dict(raw[0], target=thug.ref)], []) == ""

    def test_a_companion_may_decline_to_act(self, monkeypatch):
        """The fight schema leaves `narrate_only` out (the player's punch narrated and
        never proposed), so a companion's refusal was unsamplable: told to stay back, the
        timid drover came back `attack` 4 of 5 times. A companion's turn may decline."""
        from gm import agent as agent_mod, client

        s, e, pc = _party()
        drover, thug = _friend(s, e, name="Wil", timid=True), _thug(s)
        e._ensure_encounter(pc.ref, thug.ref)
        schemas = []

        def chat(messages, model, *a, **kw):
            schemas.append(kw.get("schema"))
            return client.Reply(json.dumps({
                "narration": "Wil stays behind you.",
                "intents": [{"op": "narrate_only", "because": "no fighter"}]}), 0.1, model)

        monkeypatch.setattr(agent_mod.client, "chat", chat)
        gm = agent_mod.GMAgent(WORLD, e)
        plan = gm.npc_turn(drover.ref, location=WORLD.get(TOWN))
        assert [i.op for i in plan.intents] == ["narrate_only"]
        assert '"narrate_only"' in json.dumps(schemas[0])
        assert '"attack"' in json.dumps(schemas[0])
        # A creature's turn keeps the fight schema as it was.
        try:
            gm.npc_turn(thug.ref, location=WORLD.get(TOWN))
        except Exception:  # noqa: BLE001 — its reply is the companion's; only the schema matters
            pass
        assert '"narrate_only"' not in json.dumps(schemas[-1])

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

    def _turn_ctx(self, e, text):
        from gm.checks import BeatContext

        return BeatContext(
            door="turn", text=text, player_text="", engine=e, scene=e.scene, world=None,
            location=None, reading=None, outcomes=(), tells=(), said=(),
            attribution=None, brief="", brief_facts={}, pull=None, was_at="",
            acting="", turn=0)

    def test_a_companion_acting_on_the_players_beat_is_found_and_cut(self):
        """The replay's player beat: "Bob is a blur of motion, diving into the gap"
        before Bob's turn, and "the drover steps back" before the drover's. A reaction —
        a flinch, a look — is theirs on any beat."""
        from gm.checks import companion_off_turn as check

        s, e, pc = _party()
        bob, thug = _owned(s, e), _thug(s)
        e._ensure_encounter(pc.ref, thug.ref)
        acts = "Bob lunges at the thug, quick as a struck match."
        looks = "Bob's head turns toward the thug at your shout."
        found = check.find(self._turn_ctx(e, f"Your arrow flies wide. {acts} {looks}"))
        assert len(found) == 1 and found[0].sentences == (acts,)
        text, notes = check.backstop(
            self._turn_ctx(e, f"Your arrow flies wide. {acts} {looks}"),
            f"Your arrow flies wide. {acts} {looks}", found)
        assert acts not in text and looks in text and notes
        # Out of a fight there is no turn to wait for: nothing is read.
        s2, e2, pc2 = _party()
        _owned(s2, e2)
        assert check.find(self._turn_ctx(e2, acts)) == []


# --- 6. out of a fight: the words spoken TO them get their own answer -----------------------

class TestSpokenTo:
    def test_who_the_words_are_spoken_to(self):
        """Detected in code, never asked: a vocative, or a verb of telling before the
        name. Words ABOUT them are the narrator's ordinary business."""
        from gm import companions

        s, e, pc = _party()
        bob = _owned(s, e)
        drover = _friend(s, e, name="a young drover")
        stranger = instantiate("guildhand", scene=s, name="Hob")
        s.add(stranger)
        said = companions.addressed
        assert said(s, "Bob, keep watch by the door.") == [bob.ref]
        assert said(s, 'I shout: "Bob, attack the thug!"') == [bob.ref]
        assert said(s, "I tell Bob to keep watch.") == [bob.ref]
        assert said(s, '"Drover, sneak up behind that thug."') == [drover.ref]
        assert said(s, "I look at Bob and sigh.") == []
        assert said(s, "Hob, fetch me a drink.") == []      # a stranger is not ordered about
        assert sorted(said(s, '"Bob, the door! Drover — stay close."')) == sorted(
            [bob.ref, drover.ref])

    def test_out_of_a_fight_the_plan_leaves_their_answer_to_them(self):
        """Defect 6: the planner wrote the timid drover's Stealth check itself."""
        from gm import companions

        s, e, pc = _party()
        drover = _friend(s, e, name="a young drover", timid=True)
        notes = []
        raw = [{"op": "check", "actor": drover.ref,
                "params": {"skill": "stealth", "dc": {"band": "average"}}},
               {"op": "say", "params": {"words": "Drover, lift his purse."}}]
        kept = companions.on_their_own_turn(raw, s, notes=notes,
                                            addressed_refs=[drover.ref])
        assert [r["op"] for r in kept] == ["say"] and notes

    def test_an_answer_left_off_the_page_is_put_back(self):
        """Defect 7. Before the closing question, in the answer's own words; and not when
        the beat already shows them — "the drover's eyes" names the drover."""
        from gm import companions

        s, e, pc = _party()
        bob = _owned(s, e)
        drover = _friend(s, e, name="a young drover")
        beat = "The thug leans in, grinning. What do you do?"
        text, put = companions.answers_on_the_page(
            beat, [(bob, "Bob moves to the door and stands still.")])
        assert put == ["Bob"]
        assert text == ("The thug leans in, grinning. Bob moves to the door and stands "
                        "still. What do you do?")
        text, put = companions.answers_on_the_page(
            "The young drover's eyes dart to the door.", [(drover, "They refuse.")])
        assert put == []

    def test_the_answer_examples_fill_with_real_people(self):
        from gm import companions, prompts

        s, e, pc = _party()
        bob = _owned(s, e)
        msgs = prompts.companion_answer_messages(
            "BRIEF", bob.ref, bob, companions.answer_facts(s, bob, "Bob, keep watch."),
            other=("c9", "merchant"), pc_ref=pc.ref)
        joined = " ".join(m["content"] for m in msgs[1:])
        for token in ("{Self}", "{Companion}", "{Other}", "{Other Ref}", "{Pc}"):
            assert token not in joined, token
        assert "Bob, keep watch." in msgs[-1]["content"]
        replies = [json.loads(m["content"]) for m in msgs if m["role"] == "assistant"]
        ops = [i["op"] for r in replies for i in r["intents"]]
        assert {"narrate_only", "say", "check"} <= set(ops)
        for r in replies:
            for i in r["intents"]:
                assert "dc" not in (i.get("params") or {})   # a try is opposed, never a DC

    def test_the_answer_is_held_to_their_own_acts_and_no_dc(self, monkeypatch):
        """The model decides; the engine holds the shape: a DC of the model's is sent back
        with the fix named, and an act with no actor is theirs."""
        from gm import agent as agent_mod, client

        s, e, pc = _party()
        drover = _friend(s, e, name="Wil", timid=True)
        replies = iter([
            {"narration": "Wil edges over.", "intents": [
                {"op": "check", "actor": drover.ref,
                 "params": {"skill": "stealth", "dc": 15}}]},
            {"narration": "Wil does not move from the wall.", "intents": [
                {"op": "say", "params": {"words": "Not a chance.", "to": pc.ref,
                                         "quoted": True}}]},
        ])

        def chat(messages, model, *a, **kw):
            return client.Reply(json.dumps(next(replies)), 0.1, model)

        monkeypatch.setattr(agent_mod.client, "chat", chat)
        gm = agent_mod.GMAgent(WORLD, e)
        plan = gm.companion_answer(drover.ref, "Wil, lift his purse.",
                                   location=WORLD.get(TOWN))
        assert [(i.op, i.actor) for i in plan.intents] == [("say", drover.ref)]
        assert any("never a DC" in r for r in plan.rejections)
        out = e.run(plan.intents)
        assert 'Wil says to PC: "Not a chance."' in out.outcomes[0].tell
