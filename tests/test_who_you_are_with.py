"""Knowing where you are, and who is standing next to you.

Reported 2026-09-22, after four sessions played in one settlement:

> *"I have never been aware that vormoor was a village. this should be one of the first
> things done when you are being dropped into a world. A description of the place you are
> in that lets you know what to expect. and if you have picked a background and are know
> to the place you start then the person you start next to does not need to be a stranger.
> they could be a friend or travel companion. and if you are taveling together they should
> follow and comment on the world around you."*

Three defects, and each was a fact the engine already held and never handed over:

  1. **The scale never reached the player.** `places.population` — the one function that
     says what a village is, in words — had NO production caller anywhere in the app;
     one test read it. The scale reached the narrator's brief ("HERE: Vormoor, a
     village.") from the first turn and reached no screen the player ever saw.

  2. **Eleven of the fourteen shipped backgrounds are local** — "You kept a pitch at the
     market and the neighbours still nod", `knows.every-face-here` — and the opening put
     a stranger beside every one of them. The prose half already knew (`_standing` stops
     saying "a stranger here" once ties bind); the scene did not.

  3. **Companions did not follow.** Both movement doors shed every non-PC not named in
     `with`, so an NPC who agreed to come along was left behind the moment the party
     crossed a village. Measured live the same day: "Left behind: Drenn Ironvale."
"""
from __future__ import annotations

from rules import backgrounds, places as places_mod, states
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


class TestWhatKindOfPlaceThisIs:
    def test_the_words_exist_for_every_scale_the_app_prices(self):
        for scale in places_mod.POPULATION_BY_SCALE:
            said = places_mod.what_it_is(scale)
            assert said.startswith(f"a {scale} of ")
            assert "people" in said

    def test_a_scale_this_app_does_not_price_claims_no_size(self):
        """A made-up population for a "hamlet" would be this app inventing a fact about
        somebody else's world — the rule `races.price_tag` and `journey.hours_for` both
        already answer three ways for."""
        assert places_mod.what_it_is("hamlet") == "a hamlet"
        assert places_mod.what_it_is("") == ""

    def test_a_village_says_everyone_knows_everyone(self):
        """The half the player wanted: not a number, what to expect. The third law is
        that no model authors a number, so this is a band in words and never a figure."""
        said = places_mod.what_it_is("village")
        assert "everyone knows everyone" in said
        assert not any(ch.isdigit() for ch in said)

    def test_the_opening_says_it_before_anything_else_about_the_place(self):
        from play import opening

        text = opening.compose(_FakeGame(), "a stranger here")
        first = text.split(".")[0]
        assert "a town of" in first or "a village of" in first or "a city of" in first

    def test_the_brief_says_it_too_and_says_it_the_same_way(self):
        """One composer, three readers. Three sentences saying this three ways is the
        drift CLAUDE.md names."""
        from gm import prompts

        s, e, _pc = _party()
        brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN), recent=[], turn=1,
                                    here=e.here(), known=e.places())
        said = places_mod.what_it_is(places_mod.scale_of(WORLD.get(TOWN)))
        assert said and said in brief

    def test_the_panel_is_sent_it_so_it_stays_known(self, tmp_path):
        """An opening is read once. The player had played four sessions in Vormoor and
        did not know it was a village, so the durable place for this is the panel."""
        from django.test import Client
        from django.test.utils import override_settings

        from play import campaign as cm
        from rules.sheet import load_pc

        with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
            cm._LIVE.clear()
            cm.begin_with(load_pc("fixtures/pc-kesst.json")).save()
            scene = Client().get("/api/state").json()["scene"]
            cm._LIVE.clear()
        assert scene["scale"] in places_mod.POPULATION_BY_SCALE
        assert scene["what_it_is"] == places_mod.what_it_is(scene["scale"])


class _FakeGame:
    """The smallest thing `opening.compose` reads: a world, a place, a scene, a seed."""

    id = "who-you-are-with"
    seed = 4

    def __init__(self):
        self.world = WORLD
        self.location = WORLD.get(TOWN)
        s = Scene(location_id=TOWN)
        pc = instantiate("guildhand", scene=s, name="PC")
        pc.kind = "pc"
        s.add(pc)
        self.scene = s


class TestTheStrangerBesideYou:
    def _opened(self, background: str):
        """A campaign's opening scene: the PC, and the one person the situation rolled."""
        s, e, pc = _party()
        pc.background = background
        other = instantiate("guildhand", scene=s, name="the woman at the bread stall")
        s.add(other)
        bound = backgrounds.bind(e, pc)
        named = backgrounds.acquaint(e, pc, bound)
        return s, e, pc, other, bound, named

    def test_a_local_background_makes_them_somebody_who_knows_you(self):
        s, e, pc, other, bound, named = self._opened("stallholder")
        assert bound, "the stallholder's tie binds a market, and this world has one"
        assert named == other.name
        assert other.has_state(states.KNOWS_YOU)
        assert states.attitude_of(other) == "friendly"

    def test_nobody_new_is_added_to_the_scene(self):
        """Reported as a defect 2026-09-20 — "drenn ironvale is named as part of my
        background but does not belong in the scene" — and `bind`'s `place=False`
        answers it. This must not reopen it from the other side."""
        s, e, pc, other, _b, _n = self._opened("stallholder")
        assert len([a for a in s.actors.values() if not a.is_pc]) == 1

    def test_a_character_with_no_local_tie_keeps_their_stranger(self):
        """Being new somewhere is a legitimate way to start, and `exile` is the
        background for it."""
        s, e, pc = _party()
        pc.background = "thief-taker"       # a tie with a role and no place
        other = instantiate("guildhand", scene=s, name="the old man ahead of you")
        s.add(other)
        bound = [b for b in backgrounds.bind(e, pc) if not b.get("where")]
        assert backgrounds.acquaint(e, pc, bound) == ""
        assert not other.has_state(states.KNOWS_YOU)

    def test_it_marks_nobody_when_a_crowd_is_already_standing_there(self):
        """It runs once, before the first turn, when the scene holds the player and one
        other person. Anything else is not an opening and it declines to guess which of
        them is the friend."""
        s, e, pc = _party()
        pc.background = "stallholder"
        for name in ("one", "two"):
            s.add(instantiate("guildhand", scene=s, name=name))
        assert backgrounds.acquaint(e, pc, [{"where": "the market"}]) == ""

    def test_the_opening_says_they_are_not_a_stranger(self):
        from play import opening

        game = _FakeGame()
        other = instantiate("guildhand", scene=game.scene, name="the baker")
        game.scene.add(other)
        plain = opening.compose(game, "a stranger here")
        from rules.activeeffect import ActiveEffect

        other.apply_effect(ActiveEffect(
            name="knows you", kind="bond", key="t:knows", source="t", origin="t",
            duration="until-dismissed", tags=(states.KNOWS_YOU,)))
        known = opening.compose(game, "a stranger here")
        assert "who has known you" in known
        assert "who has known you" not in plain

    def test_the_brief_says_they_knew_the_player_before_the_game(self):
        """Without it the narrator writes every non-player as somebody met just now,
        which is what four sessions with a local background on the sheet produced."""
        from gm import prompts
        from rules.activeeffect import ActiveEffect

        s, e, pc = _party()
        other = instantiate("guildhand", scene=s, name="Marra")
        s.add(other)
        other.apply_effect(ActiveEffect(
            name="knows you", kind="bond", key="t:knows", source="t", origin="t",
            duration="until-dismissed", tags=(states.KNOWS_YOU,)))
        brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN), recent=[], turn=1,
                                    here=e.here(), known=e.places())
        assert "KNEW the player before this game began" in brief


class TestSomebodyWhoComesAlong:
    def _friend(self, s, e, name="Marra", mood="friendly"):
        who = instantiate("guildhand", scene=s, name=name)
        s.add(who)
        if mood:
            e.settle_attitude(who, mood, None, "test")
        return who

    def test_a_friend_agrees_and_the_engine_remembers(self):
        s, e, pc = _party()
        who = self._friend(s, e)
        _run(e, {"op": "company", "actor": pc.ref, "because": "t",
                 "params": {"who": who.ref}})
        assert who.has_state(states.TRAVELS_WITH_YOU)

    def test_somebody_who_does_not_like_you_does_not_come(self):
        """1e's own track decides: friendly "will chat, advise, offer limited help".
        Below that the refusal names the fix, which is a Diplomacy check."""
        s, e, pc = _party()
        who = self._friend(s, e, mood="unfriendly")
        tell = " ".join(o.tell for o in _run(
            e, {"op": "company", "actor": pc.ref, "because": "t",
                "params": {"who": who.ref}}).outcomes)
        assert not who.has_state(states.TRAVELS_WITH_YOU)
        assert "Diplomacy" in tell

    def test_they_are_not_left_behind_when_the_party_crosses_town(self):
        """The measured defect, 2026-09-22, on a turn where the player did nothing but
        walk from the market to the green: "Left behind: Drenn Ironvale"."""
        s, e, pc = _party()
        who = self._friend(s, e)
        _run(e, {"op": "company", "actor": pc.ref, "because": "t",
                 "params": {"who": who.ref}})
        far = next(p for p in e.places()
                   if p.id != s.at and not p.described_only
                   and places_mod.route(e.places(), s.at, p.id))
        tell = " ".join(o.tell for o in _run(
            e, {"op": "travel", "actor": pc.ref, "because": "t",
                "params": {"place": far.name}}).outcomes)
        assert who.ref in s.actors, "they came along"
        assert who.at == s.at
        assert "Left behind" not in tell or who.name not in tell

    def test_somebody_who_never_agreed_is_still_left_behind(self):
        """The rule travel was written for stands: a gatekeeper wounded in the city
        followed the party to the forest and took an NPC turn for the rest of the
        session. Shedding is the default; coming along is the exception, and it is a
        state somebody has to have been given."""
        s, e, pc = _party()
        stranger = self._friend(s, e, name="a stranger", mood="")
        far = next(p for p in e.places()
                   if p.id != s.at and not p.described_only
                   and places_mod.route(e.places(), s.at, p.id))
        _run(e, {"op": "travel", "actor": pc.ref, "because": "t",
                 "params": {"place": far.name}})
        assert stranger.ref not in s.actors

    def test_they_walk_the_road_between_towns_too(self):
        from rules import journey as journey_mod

        s, e, pc = _party()
        legs = [x for x in journey_mod.legs_from(WORLD, TOWN) if not x.by_sea]
        if not legs:
            return
        who = self._friend(s, e)
        _run(e, {"op": "company", "actor": pc.ref, "because": "t",
                 "params": {"who": who.ref}})

        class _Quiet:                    # a road with nothing on it
            def __init__(self, real):
                self.real = real

            def __getattr__(self, name):
                return getattr(self.real, name)

            def roll(self, notation, modifiers=None, label="", visibility="hidden"):
                if notation == "1d100":
                    return self.real.given(100, modifiers, label, notation)
                return self.real.roll(notation, modifiers, label, visibility)

        e.dice = _Quiet(e.dice)
        _run(e, {"op": "journey", "actor": pc.ref, "because": "t",
                 "params": {"to": legs[0].to_name}})
        assert s.location_id == legs[0].to_id
        assert who.ref in s.actors, "a companion is not dropped at the side of a road"
        assert who.at == s.at

    def test_leaving_ends_it(self):
        s, e, pc = _party()
        who = self._friend(s, e)
        _run(e, {"op": "company", "actor": pc.ref, "because": "t",
                 "params": {"who": who.ref}})
        _run(e, {"op": "company", "actor": pc.ref, "because": "t",
                 "params": {"who": who.ref, "do": "leave"}})
        assert not who.has_state(states.TRAVELS_WITH_YOU)

    def test_the_dead_do_not_come_along(self):
        s, e, pc = _party()
        who = self._friend(s, e)
        who.hp = -1
        who.add_condition("dying", None, source="test")
        tell = " ".join(o.tell for o in _run(
            e, {"op": "company", "actor": pc.ref, "because": "t",
                "params": {"who": who.ref}}).outcomes)
        assert not who.has_state(states.TRAVELS_WITH_YOU)
        assert "down" in tell

    def test_the_brief_says_they_travel_with_the_player(self):
        """So the narrator gives them a voice about what is around them — the half of
        the request that is prose: "if you are taveling together they should follow and
        comment on the world around you"."""
        from gm import prompts

        s, e, pc = _party()
        who = self._friend(s, e)
        _run(e, {"op": "company", "actor": pc.ref, "because": "t",
                 "params": {"who": who.ref}})
        brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN), recent=[], turn=1,
                                    here=e.here(), known=e.places())
        assert "TRAVELS WITH the player" in brief
        assert "their own opinions" in brief

    def test_the_model_is_told_the_op_exists(self):
        """An op the narrator is never told about is inert — the defect this whole run
        of work keeps turning up."""
        from gm import prompts

        said = prompts._op_reference() + " ".join(
            m["content"] for m in prompts.call_one_messages("B", [], "x"))
        assert '"op": "company"' in said

    def test_a_do_it_does_not_know_is_printed_and_not_raised(self):
        """The stage 7 ratchet's rule, and it caught this one on the full run: a
        resolution-time raise reaches the player as a 502 with their sentence deleted."""
        s, e, pc = _party()
        who = self._friend(s, e)
        res = _run(e, {"op": "company", "actor": pc.ref, "because": "t",
                       "params": {"who": who.ref, "do": "abandon"}})
        tell = " ".join(o.tell for o in res.outcomes)
        assert "'join' or 'leave'" in tell
        assert not who.has_state(states.TRAVELS_WITH_YOU)

    def test_talking_them_round_is_a_real_route_and_not_a_promise(self):
        """The refusal above tells the player to use Diplomacy, so the whole of that
        route has to work — a refusal naming a fix that does not exist is worse than no
        refusal. `docs/states-effects-tells.md`'s ledger still lists "no route from a
        social check to an attitude" as open; it was closed on 2026-09-16 and the ledger
        is stale. This is the proof, end to end: indifferent, talked round, comes along.
        """
        from rules import attitude as attitude_mod

        s, e, pc = _party()
        who = self._friend(s, e, mood="")           # nobody has said: indifferent
        assert attitude_mod.of(who) == attitude_mod.DEFAULT
        _run(e, {"op": "company", "actor": pc.ref, "because": "t",
                 "params": {"who": who.ref}})
        assert not who.has_state(states.TRAVELS_WITH_YOU), "indifferent does not come"

        # The check the refusal names. `target` is the intent's own field and not a
        # param — `check` takes no `target` param and `_sway_subject` reads
        # `intent.targets()` — and talking somebody round is the PLAYER's roll, so it
        # suspends and is resumed with a face, exactly as it does on the page.
        _run(e, {"op": "check", "actor": pc.ref, "target": who.ref, "because": "t",
                 "params": {"skill": "diplomacy"}})
        assert s.awaiting and s.awaiting["label"] == "Diplomacy check"
        e.resume(20)
        assert attitude_mod.step_of(attitude_mod.of(who)) \
            >= attitude_mod.step_of(attitude_mod.COMES_ALONG), attitude_mod.of(who)

        _run(e, {"op": "company", "actor": pc.ref, "because": "t",
                 "params": {"who": who.ref}})
        assert who.has_state(states.TRAVELS_WITH_YOU)
