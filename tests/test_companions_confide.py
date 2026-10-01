"""A companion's own life reaches the player through their regard, after a warm-up.

The owner's ruling, 2026-10-01:

> *"don't worry about Aid Another, Their wants should appear naturally locked behind their
> attitude toward you. but they shouldnt just blurt out personal feelings without some
> kind of warm up. like telling there is something they wanted to get off their chest or
> if you come across a thing that makes sense to remind them of a thing they can share."*

What was there before this file (the companions-manner lane, read off its code):
`views._companions_on_the_page` handed a companion's `wants` to every third remark of
theirs — `theirs % 3 == 2` — whatever they thought of the player, with no lead-in: an
indifferent drover's third opinion about the weather carried his debt to a moneylender.
No gate and no warm-up, the two things the ruling asks for.

Prior art, searched 2026-10-01 before building (gm/confide.py carries the design):

  * Baldur's Gate 3 gates a companion's personal content on approval thresholds, "gates,
    not guidelines — below the required number, the dialogue option does not appear"
    (switchbladegaming.com, BG3 romance guide; fextralife BG3 Companion Approval Guide);
    a companion with something to say shows a "!" after a long rest, and of the camp
    events waiting only the highest-priority one plays per rest, the rest queued
    (nexusmods BG3 mod 1879, "Camp Event Notifications", whose reason for existing is
    that players missed the "!"). So: the lead-in is ON the page, never a quiet icon;
    one confidence a beat; an owed share waits, it does not vanish.
  * Mass Effect 2: a fixed sequence of conversations per squadmate, a new one after each
    mission, and once the "I need your help" talk comes no other conversation opens until
    its loyalty mission is done (GameFAQs ME2 board 53476016; Fextralife forum t245649).
    So: one owed share at a time, no new lead-in while one is owed.
  * Fire Emblem supports go C, then B, then A, each needing the one before
    (fireemblemwiki.org/wiki/Support). So: nothing, hinted, told — never skipped, except
    by the reminder door, where the thing in the world is itself the warm-up.
  * Persona 5's confidant ranks fill from time spent, liked answers and gifts, and some
    ranks wait on story beats (gamesradar P5R Confidants guide; psnprofiles 9938).
  * Disco Elysium: "the team tried to avoid the role-playing video game convention of
    exploring every option in a dialogue tree, instead designing Kitsuragi to share
    personal details only in specific situations" (en.wikipedia.org/wiki/Kim_Kitsuragi,
    citing PC Gamer, Lauren Morton) — his Kineema and his aerostatics come up when the
    situation does. The reminder door. (The often-quoted Kurvitz line about "cleaning out
    his tree" could not be confirmed against its primary source and is not relied on.)
  * What was ABANDONED: Dragon Age: Origins' gifts bought approval outright, unlimited
    with the DLC (thegamer DA:O approval guide; GameFAQs DA:O boards); the "romance
    vending machine" critique — "keep scoring relationship points and putting them into
    the target character like a vending machine" (tvtropes Analysis/RomanceSidequest;
    gamecritics.com, Alex Raymond); and Obsidian dropped approval altogether for Avowed:
    "We didn't want players feeling like they had to choose the 'right' options in order
    to maintain their companions" (Carrie Patel, 80.lv; pcgamer.com). So no new meter here
    and nothing to buy: the existing attitude track gates it, and the COMPANION brings it
    up — the player cannot ask a want out of a companion who has not hinted at one.
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest

from rules import confiding, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")
TOWN = WORLD.play["settlements"][0]["id"]

SEA = "to see the sea once before they die"
FIDDLE = "is teaching themself the fiddle, slowly"
FAMILY = "to raise a family and see them settled"


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
    return e.run(e.validate(raw if isinstance(raw, list) else [raw], origin="author:test"))


def _friend(s, e, name="Wil", mood="helpful", wants=SEA, goal=FAMILY, hobby=FIDDLE,
            since=-1):
    who = instantiate("guildhand", scene=s, name=name)
    s.add(who)
    e.settle_attitude(who, "friendly", None, "test")
    _run(e, {"op": "company", "actor": s.pc().ref, "because": "t",
             "params": {"who": who.ref}})
    e.settle_attitude(who, mood, None, "test")
    s.population[f"p-{who.ref}"] = {"ref": who.ref, "phrase": name.lower(), "life": {
        "traits": ["cautious", "timid"], "work_name": "carter",
        "shows": ["keeps a door at their back and a reason to leave ready"],
        "wants": wants, "goal": goal, "hobby": hobby, "quirk": ""},
        "travelling_since": since}
    return who


def _rec(s, who):
    from rules import population

    return population.of_ref(s, who.ref)


def _turns(n, text="I look around."):
    out = []
    for i in range(n):
        out += [{"who": "player", "text": f"{text} {i}"}, {"who": "gm", "text": "Quiet."}]
    return out


def _out(op, tell):
    return SimpleNamespace(op=op, tell=tell, effects=[], status="resolved")


# --- the shortcut is gone ---------------------------------------------------------------

class TestTheShortcutIsGone:
    def test_a_remark_is_never_told_their_wants(self):
        """Measured off the manner lane's code: every third remark (`theirs % 3 == 2`)
        carried the companion's want, at any attitude. Now no remark's facts carry their
        want, goal or hobby, however many remarks they have made."""
        import inspect

        from gm import companions
        from play import views

        s, e, pc = _party()
        wil = _friend(s, e, mood="indifferent")
        assert "wants" not in inspect.signature(companions.interject_facts).parameters
        s.conversation_log = [{"n": i, "who": wil.ref, "kind": "line", "beat": i,
                               "src": "interject", "text": "hm"} for i in range(2)]
        facts = companions.interject_facts(s, wil, {"reason": "moment"}, beat="Quiet.")
        for life in (SEA, FAMILY, FIDDLE):
            assert life not in facts
        assert "theirs % 3" not in inspect.getsource(views._companions_on_the_page)


# --- the gate ---------------------------------------------------------------------------

class TestTheGate:
    @pytest.mark.parametrize("mood,gate", [
        ("hostile", confiding.NONE), ("unfriendly", confiding.NONE),
        ("indifferent", confiding.NONE), ("friendly", confiding.HINT),
        ("helpful", confiding.SHARE), ("devoted", confiding.SHARE)])
    def test_the_attitude_decides_how_much(self, mood, gate):
        """The ruling's "locked behind their attitude toward you": below friendly nothing
        personal ever; friendly a hint at most; helpful or better the thing itself."""
        s, e, pc = _party()
        wil = _friend(s, e, mood=mood)
        assert confiding.gate(wil) == gate

    def test_owned_and_devoted_shares(self):
        s, e, pc = _party()
        bob = _friend(s, e, name="Bob", mood="friendly")
        bob.apply_effect(ActiveEffect(
            name="yours", kind="bond", key=f"claim:{bob.ref}:owned",
            source=f"claim:{bob.ref}", origin="rule:test", duration="until-dismissed",
            tags=(states.OWNED_BY_YOU,)))
        assert confiding.gate(bob) == confiding.SHARE

    def test_indifferent_never_confides_over_forty_quiet_turns(self):
        """Nothing personal at indifferent, by either door, even with the sea in every
        beat."""
        from gm import confide

        s, e, pc = _party()
        wil = _friend(s, e, mood="indifferent")
        for n in range(1, 41):
            tr = _turns(n)
            assert confide.due(s, tr, [], beat_text="The harbour and the sea beyond.",
                               moved=True, place=e.here()) is None
        assert confiding.stage(_rec(s, wil), "wants") == confiding.NOTHING


# --- door one: the lead-in, then the share on a later beat ------------------------------

class TestTheLeadIn:
    def test_no_lead_in_before_they_have_travelled_together_a_while(self):
        """A companion of two beats does not open their heart: the first lead-in waits
        CONFIDE_EVERY player turns from when they were first seen travelling."""
        from gm import confide

        s, e, pc = _party()
        _friend(s, e, since=2 * (confide.CONFIDE_EVERY - 1))
        tr = _turns(confide.CONFIDE_EVERY)
        assert confide.due(s, tr, []) is None
        tr = _turns(2 * confide.CONFIDE_EVERY)
        assert confide.due(s, tr, [])["kind"] == confide.LEAD_IN

    def test_friendly_gets_a_hint_helpful_a_lead_in(self):
        from gm import confide

        s, e, pc = _party()
        _friend(s, e, mood="friendly")
        got = confide.due(s, _turns(confide.CONFIDE_EVERY), [])
        assert got["kind"] == confide.HINT and got["topic"] == "wants"
        s2, e2, _ = _party()
        _friend(s2, e2, mood="helpful")
        assert confide.due(s2, _turns(confide.CONFIDE_EVERY), [])["kind"] == confide.LEAD_IN

    def test_only_in_a_quiet_moment(self):
        """No fight, no roll waiting, nobody but companions being talked to, no death or
        deal this beat, not the beat they arrived somewhere."""
        from gm import confide

        s, e, pc = _party()
        wil = _friend(s, e)
        tr = _turns(confide.CONFIDE_EVERY)
        thug = instantiate("thug", scene=s, name="thug")
        s.add(thug)
        assert confide.due(s, tr, [], talking=[thug]) is None
        assert confide.due(s, tr, [], talking=[wil]) is not None
        assert confide.due(s, tr, [_out("attack", "The thug dies.")]) is None
        assert confide.due(s, tr, [], moved=True, place=e.here()) is None or \
            confide.due(s, tr, [], moved=True, place=e.here())["door"] == "reminder"
        assert confide.due(s, tr, [], answered=[(wil, "ok")]) is None
        e._ensure_encounter(pc.ref, thug.ref)
        assert confide.due(s, tr, []) is None

    def test_the_share_comes_on_a_later_beat(self):
        """The warm-up: after the lead-in, nothing on the next turn; the share at a quiet
        moment CONFIDE_GAP turns on."""
        from gm import confide

        s, e, pc = _party()
        wil = _friend(s, e)
        tr = _turns(confide.CONFIDE_EVERY)
        lead = len(tr)
        confiding.hint(_rec(s, wil), "wants", lead, "lead-in")
        s.conversation_log = [{"n": 1, "who": wil.ref, "kind": "line", "beat": lead,
                               "src": "confide", "text": "There's something."}]
        tr.append({"who": "gm", "text": "Wil clears his throat."})
        assert confide.due(s, tr + _turns(1), []) is None
        got = confide.due(s, tr + _turns(confide.CONFIDE_GAP), [])
        assert got["kind"] == confide.SHARE and got["door"] == "quiet"
        assert got["topic"] == "wants"

    def test_one_owed_share_at_a_time(self):
        """Mass Effect 2's loyalty talk: while one share is owed, no other lead-in."""
        from gm import confide

        s, e, pc = _party()
        wil = _friend(s, e, mood="friendly")
        confiding.hint(_rec(s, wil), "wants", 0, "lead-in")
        assert confide.due(s, _turns(3 * confide.CONFIDE_EVERY), []) is None


class TestWhatThePlayerSaysToIt:
    def _owed(self, mood="helpful"):
        from gm import confide

        s, e, pc = _party()
        wil = _friend(s, e, mood=mood)
        tr = _turns(confide.CONFIDE_EVERY)
        lead = len(tr)
        tr.append({"who": "gm", "text": 'Wil says, "There is something."'})
        confiding.hint(_rec(s, wil), "wants", lead, "lead-in")
        s.conversation_log = [{"n": 1, "who": wil.ref, "kind": "line", "beat": lead,
                               "src": "confide", "text": "There is something."}]
        return s, e, wil, tr

    def test_asked_it_is_their_answer_now(self):
        """"when the player responds to them (addresses them, asks)": the share comes on
        that beat, whatever the cadence."""
        from gm import confide

        s, e, wil, tr = self._owed()
        line = "Wil, what is it?"
        tr.append({"who": "player", "text": line})
        heard = confide.heard(s, tr, line, len(tr))
        assert heard["invited"] == [wil.ref]
        got = confide.due(s, tr, [], invited=heard["invited"])
        assert got["kind"] == confide.SHARE and got["door"] == "asked"

    def test_the_next_line_need_not_name_them(self):
        from gm import confide

        s, e, wil, tr = self._owed()
        tr.append({"who": "player", "text": "Go on, I'm listening."})
        assert confide.heard(s, tr, "Go on, I'm listening.", len(tr))["invited"] == [wil.ref]

    def test_a_question_to_nobody_in_particular_is_not_an_invitation(self):
        from gm import confide

        s, e, wil, tr = self._owed()
        tr.append({"who": "player", "text": "Shall we find somewhere to eat?"})
        heard = confide.heard(s, tr, "Shall we find somewhere to eat?", len(tr))
        assert heard["invited"] == []

    def test_a_brush_off_postpones_it(self):
        """"not now", "later": the share waits POSTPONE turns, and is not lost."""
        from gm import confide

        s, e, wil, tr = self._owed()
        tr.append({"who": "player", "text": "Not now, Wil."})
        beat = len(tr)
        heard = confide.heard(s, tr, "Not now, Wil.", beat)
        assert heard["brushed"] == [wil.ref] and not heard["invited"]
        assert confiding.pending(_rec(s, wil))["postponed"] == beat
        tr.append({"who": "gm", "text": "Quiet."})
        assert confide.due(s, tr + _turns(confide.POSTPONE - 1), []) is None
        assert confide.due(s, tr + _turns(confide.POSTPONE), [])["kind"] == confide.SHARE

    def test_an_order_is_left_to_their_ordinary_answer(self):
        from gm import confide

        s, e, wil, tr = self._owed()
        tr.append({"who": "player", "text": "Wil, keep watch by the door."})
        heard = confide.heard(s, tr, "Wil, keep watch by the door.", len(tr))
        assert heard == {"invited": [], "brushed": [], "not_ready": []}

    def test_friendly_and_asked_is_not_ready_and_says_so(self):
        """Asked after a hint, an answer told nothing would make a want up; it is told
        they are not ready to say."""
        from gm import companions, confide

        s, e, wil, tr = self._owed(mood="friendly")
        tr.append({"who": "player", "text": "Wil, what's on your mind?"})
        heard = confide.heard(s, tr, "Wil, what's on your mind?", len(tr))
        assert heard["not_ready"] == [wil.ref] and not heard["invited"]
        facts = companions.answer_facts(s, wil, "Wil, what's on your mind?",
                                        not_ready=True)
        assert "not ready to tell" in facts and SEA not in facts


# --- door two: the reminder -------------------------------------------------------------

class TestTheReminder:
    def test_every_life_row_has_reminder_words(self):
        """The keyword map lives with the rows, one list per row, so a row added without
        one is caught here."""
        from rules import lives

        t = lives.tables()
        for table in ("wants", "goals", "hobbies"):
            for row in t[table]:
                assert row.get("reminded_by"), (table, row["id"])
                assert all(w == w.lower() and " " not in w for w in row["reminded_by"])
        assert confiding.row_of("wants", SEA)["id"] == "see-sea"

    def test_a_harbour_reminds_them_of_the_sea(self):
        from gm import confide

        s, e, pc = _party()
        _friend(s, e)
        got = confide.due(s, _turns(3), [], beat_text="Gulls wheel over the harbour.")
        assert got["kind"] == confide.BRIDGE and got["door"] == "reminder"
        assert got["topic"] == "wants" and got["thing"] in ("gulls", "harbour")

    def test_friendly_gets_a_bridge_hint_only(self):
        from gm import confide

        s, e, pc = _party()
        _friend(s, e, mood="friendly")
        got = confide.due(s, _turns(3), [], beat_text="Gulls wheel over the harbour.")
        assert got["kind"] == confide.BRIDGE_HINT

    def test_only_what_is_new_this_beat(self):
        """The tavern they have stood in for ten beats is not a reminder on the
        eleventh: a thing already in the last beats is not fresh."""
        from gm import confide

        s, e, pc = _party()
        _friend(s, e)
        assert confide.due(s, _turns(3), [], beat_text="Gulls over the harbour.",
                           before="You walk along the harbour. Gulls cry.") is None

    def test_a_child_here_touches_a_goal_of_family(self):
        """A person present by their years: a child in the room is a reminder for "to
        raise a family"."""
        from gm import confide

        s, e, pc = _party()
        wil = _friend(s, e, wants="", hobby="")
        kid = instantiate("guildhand", scene=s, name="girl with a hoop")
        s.add(kid)
        s.population["p-kid"] = {"ref": kid.ref, "life": {"tags": ["minor", "young"]}}
        got = confide.due(s, _turns(3), [], beat_text="")
        assert got and got["topic"] == "goal" and got["thing"] == "child"
        assert got["source"] == "person" and got["ref"] == wil.ref

    def test_their_own_words_are_not_the_world(self):
        from gm import confide

        s, e, pc = _party()
        _friend(s, e)
        assert confide.due(s, _turns(3), [], beat_text='Wil mutters, "the sea, the sea".') \
            is None


# --- once told, never re-announced ------------------------------------------------------

class TestOnceTold:
    def test_told_is_never_offered_again(self):
        from gm import confide

        s, e, pc = _party()
        wil = _friend(s, e)
        for t in confiding.TOPICS:
            confiding.tell(_rec(s, wil), t, 1, "quiet")
        for n in range(1, 30):
            assert confide.due(s, _turns(n), [], beat_text="The harbour, the fiddler, "
                               "a child.") is None

    def test_the_journal_shows_it_in_their_life_words(self):
        """The Journal is the record: the row's own words, never a model's."""
        from play import views

        s, e, pc = _party()
        wil = _friend(s, e)
        c = SimpleNamespace(scene=s)
        assert views._confided_state(c) == []
        confiding.hint(_rec(s, wil), "wants", 3, "lead-in")
        got = views._confided_state(c)
        assert got == [{"name": "Wil", "told": [], "hinted": True}]
        confiding.tell(_rec(s, wil), "wants", 5, "quiet")
        got = views._confided_state(c)
        assert got[0]["told"] == [{"label": "Wants", "text": SEA}]
        assert got[0]["hinted"] is False

    def test_the_brief_carries_it_only_when_something_touches_it(self):
        """Known to the player, so no leak; but every beat it would be their one subject.
        Never an untold one."""
        from gm import prompts

        s, e, pc = _party()
        wil = _friend(s, e)
        brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN), recent=[], turn=1,
                                    here=e.here(), known=e.places())
        assert SEA not in brief and FAMILY not in brief
        confiding.tell(_rec(s, wil), "wants", 1, "quiet")
        brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN), recent=["You walk on."],
                                    turn=1, here=e.here(), known=e.places())
        assert SEA not in brief
        brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN),
                                    recent=["The harbour opens before you."], turn=1,
                                    here=e.here(), known=e.places())
        assert SEA in brief and FAMILY not in brief


# --- what may stand ---------------------------------------------------------------------

class TestWhatMayStand:
    def _wil(self):
        s, e, pc = _party()
        wil = _friend(s, e)
        return s, wil, _rec(s, wil)

    @pytest.mark.parametrize("kind,line,why", [
        ("lead-in", 'Wil looks away. "I want to see the sea before I die, that is all."',
         "too soon"),
        ("lead-in", 'Wil looks away. "Nice weather."', "something on their mind"),
        ("share", 'Wil looks away. "I miss my sister terribly."', "does not say what it is"),
        ("share", 'Wil looks away. "I want to see the sea, 3 times."', "a number"),
        ("bridge", 'Wil looks away. "I want to see the sea once before I die."',
         "brought it up"),
        ("share", 'Wil looks away. "We should go to the sea, I have never seen it."',
         "tells the player what to do"),
    ])
    def test_refused(self, kind, line, why):
        from gm import confide

        s, wil, rec = self._wil()
        plan = {"kind": kind, "topic": "wants", "thing": "harbour", "door": "quiet"}
        assert why in confide.refusal(line, wil, {"Wil"}, plan, rec)

    @pytest.mark.parametrize("kind,line", [
        ("lead-in", 'Wil rubs his neck. "There\'s something I\'ve been meaning to tell you."'),
        ("hint", 'Wil starts to speak and stops. "Another time."'),
        ("share", 'Wil rubs his neck. "Never seen the sea. I\'d like to, once, before I go."'),
        ("bridge", 'Wil stares at the harbour. "Never seen the sea proper. I want to, once, '
                   'before I die."'),
        ("bridge-hint", 'Wil stares at the harbour. "Reminds me of something. Later."'),
    ])
    def test_passes(self, kind, line):
        from gm import confide

        s, wil, rec = self._wil()
        plan = {"kind": kind, "topic": "wants", "thing": "harbour", "door": "quiet"}
        assert confide.refusal(line, wil, {"Wil"}, plan, rec) == ""

    def test_every_demonstration_passes_its_own_check(self):
        """Demonstrations beat instructions; a demonstration the check would refuse
        teaches the refusal. Each example is scored as the page would be."""
        from gm import confide, prompts
        from rules import lives

        rows = {r["text"] for t in ("wants", "goals", "hobbies") for r in lives.tables()[t]}
        for kind, examples in prompts.CONFIDE_EXAMPLES.items():
            for ex in examples:
                name = re.match(r"Who speaks: (\w+)", ex["user"]).group(1)
                actor = SimpleNamespace(name=name, ref="x",
                                        has_state=lambda *_: False)
                life = re.search(r"nothing else about their past\): ([^\n]+)", ex["user"])
                thing = re.search(r"(?:put \w+ in mind|brought it up): the (\w+)",
                                  ex["user"])
                rec = {"life": {"wants": life.group(1) if life else ""}}
                plan = {"kind": kind, "topic": "wants",
                        "thing": thing.group(1) if thing else "", "door": "quiet"}
                assert confide.refusal(ex["line"], actor, {name}, plan, rec) == "", ex
                if life:
                    assert life.group(1) not in rows    # never a shipped row's words

    def test_the_lead_in_call_is_not_told_the_want(self):
        """What a model is not told it cannot leak (rules/population.py: ~83% at 12B)."""
        from gm import confide

        s, wil, rec = self._wil()
        for kind in (confide.LEAD_IN, confide.HINT, confide.BRIDGE_HINT):
            facts = confide.facts(s, wil, {"kind": kind, "topic": "wants",
                                           "thing": "harbour", "door": "lead-in"})
            assert SEA not in facts and FAMILY not in facts and FIDDLE not in facts
        facts = confide.facts(s, wil, {"kind": confide.SHARE, "topic": "wants",
                                       "thing": "", "door": "quiet"})
        assert SEA in facts and FAMILY not in facts
        assert not any(ch.isdigit() for ch in facts)


def _fake(monkeypatch, replies):
    from gm import agent as agent_mod, client

    seen = []
    it = iter(replies)

    def chat(messages, model, *a, **kw):
        seen.append(messages)
        return client.Reply(json.dumps(next(it)), 0.1, model)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    return seen


class TestTheCall:
    def test_a_lead_in_that_says_too_much_gets_one_repair(self, monkeypatch):
        from gm import agent as agent_mod, confide

        s, e, pc = _party()
        wil = _friend(s, e)
        seen = _fake(monkeypatch, [
            {"line": 'Wil sighs. "I have always wanted to see the sea before I die."'},
            {"line": 'Wil sighs. "There is something I have been meaning to tell you."'}])
        gm = agent_mod.GMAgent(WORLD, e)
        plan = {"kind": confide.LEAD_IN, "topic": "wants", "thing": "", "door": "lead-in"}
        line, attempts, rejections = gm.companion_confide(
            wil.ref, confide.facts(s, wil, plan), plan)
        assert "meaning to tell you" in line and len(seen) == 2
        assert "too soon" in rejections[0]
        # Only the asked-for kind's demonstrations are shown.
        shown = " ".join(m["content"] for m in seen[0])
        assert "cart horse" not in shown and "off my chest" in shown

    def test_a_line_that_never_holds_is_not_said(self, monkeypatch):
        from gm import agent as agent_mod, confide

        s, e, pc = _party()
        wil = _friend(s, e)
        _fake(monkeypatch, [{"line": 'Wil: "I miss my sister."'}] * 2)
        gm = agent_mod.GMAgent(WORLD, e)
        plan = {"kind": confide.SHARE, "topic": "wants", "thing": "", "door": "quiet"}
        line, _, rejections = gm.companion_confide(wil.ref, confide.facts(s, wil, plan),
                                                   plan)
        assert line == "" and len(rejections) == 2


class TestOnThePage:
    def _c(self, s, e, transcript):
        return SimpleNamespace(scene=s, transcript=transcript, turn_log=[], world=WORLD,
                               location=WORLD.get(TOWN), engine=lambda: e)

    def test_a_lead_in_then_the_share_moves_the_track(self, monkeypatch):
        """Through the view's own step: the lead-in marks the want hinted and owed, the
        later share marks it told, both lines booked as their speech (`confide`), and a
        line that did not hold moves nothing."""
        from gm import agent as agent_mod, confide
        from play import views

        s, e, pc = _party()
        wil = _friend(s, e)
        _fake(monkeypatch, [
            {"line": 'Wil shifts his feet. "Been meaning to tell you something."'},
            {"line": 'Wil looks at his boots. "Never seen the sea. I want to, once, '
                     'before I die."'}])
        gm = agent_mod.GMAgent(WORLD, e)
        gm.last_said = []
        tr = _turns(confide.CONFIDE_EVERY)
        c = self._c(s, e, tr)
        res = SimpleNamespace(outcomes=[])
        text, said = views._companions_confide(c, gm, "You wait. What do you do?", res,
                                               answered=[], moved=False, heard={},
                                               player_text="", repairs=[], added=[])
        assert said and "meaning to tell you" in text
        assert text.rstrip().endswith("What do you do?")
        assert confiding.stage(_rec(s, wil), "wants") == confiding.HINTED
        assert gm.last_said[-1]["from"] == "confide"
        lead = len(tr)
        s.conversation_log = [{"n": 1, "who": wil.ref, "kind": "line", "beat": lead,
                               "src": "confide", "text": "x"}]
        tr += [{"who": "gm", "text": text}] + _turns(confide.CONFIDE_GAP)
        text, said = views._companions_confide(c, gm, "Quiet. What do you do?", res,
                                               answered=[], moved=False, heard={},
                                               player_text="", repairs=[], added=[])
        assert said and "sea" in text
        assert confiding.stage(_rec(s, wil), "wants") == confiding.TOLD
        assert confiding.pending(_rec(s, wil)) is None
        assert [r["event"] for r in c.turn_log] == ["lead-in", "share"]
