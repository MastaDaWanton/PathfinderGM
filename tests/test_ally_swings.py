"""An ally's swing at a foe, narrated as a swing at the player.

The owner's ask, 2026-10-27: "fix the ally swings narrated at me". Measured on 0.2.22's code
in the real-jobs lane's road fights, where the caravan's four hired hands (carrying
`bond.travels-with-you` for the job, joined to the player's side by `_companions_join`)
fought for the player. The tells named the right target — "the hired sword's attack with
the halberd misses Toll-Keeper" — and the NPC-turn beats said otherwise:

  * the toll-keeper fight: 4 of 5 allied misses reached the page aimed at the player — "The
    Toll-Keeper feels the rush of air as the hired sword lunges forward, the halberd's heavy
    head whistling toward your chest. You twist your body…"; "the wood whistles through the
    air, and you pivot away from the arc of the swing as it passes you". No allied HIT was
    turned round (each hit's facts named the one struck), and no foe's swing at the player.
  * replayed through the recorded calls, gemma-4-12B at 0.7, four samples each: 16 of 20
    toll-keeper-fight allied misses aimed at the player before, 0 of 20 after; two foe
    misses turned on an ally (synthetic, from the recorded turns) 8 of 8 before, 2 of 8
    after — both kept the creature's own reason, "trying to push you back".

The cause, three places that assumed every non-player actor was hostile:
  * `Outcome.blows` carried the target on a hit only; a miss's facts named nobody
    ("MISS — weapon: halberd; it is evaded") and the call's opening said only that "the
    player's character is 'you'";
  * the consequence call's ONE creature demonstration (`CONSEQUENCE_NPC_EXAMPLE`) is the
    victim's message — the ferryman swings, "you duck under it";
  * the wrong-actor repair told the model the player is "the one it is done to".

The fix follows the MUDs (tbaMUD fight.c `dam_message`: every combat message written to the
attacker, to the victim and to the room, TO_CHAR / TO_VICT / TO_NOTVICT, and sent by the
reader's part in it): every blow names who swung at whom, the call says whom the blows were
aimed at and, when none was aimed at the player, says so and shows the room's message
(`CONSEQUENCE_NPC_ASIDE_EXAMPLE`), picked in code. And the beat is read back: on a creature's
turn a closed question asks who the page shows striking at whom (people codes), code
compares that with the engine's (attacker, target) pairs, and a mismatch is
`beat-aimed-wrong` — the engine's own line in the first wrong sentence's place, any other
cut. Measured on the 17 shipped NPC-turn beats of both road fights: 4 of 4 wrong beats
caught (every wrong sentence), 0 of 13 sound beats alarmed; on the 160 replayed generations,
26 of 26 wrong caught, 0 of 134 sound alarmed (docs/ally-swings.md).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from gm import agent as agent_mod
from gm import beat_verify as bv
from gm import planned, prompts
from gm.checks import BeatContext, beat_verified
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.sheet import load_pc

SWORD_MISS_TELL = "the hired sword's attack with the halberd misses Toll-Keeper (13 against AC 18)."


def _scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    sword = instantiate("guildhand", scene=s, name="the hired sword")
    s.add(sword)
    keeper = instantiate("thug", scene=s, name="Toll-Keeper")
    s.add(keeper)
    assert sword.ref != keeper.ref
    s.initiative = [(r, 10) for r in s.actors]
    s.turn = 0
    return s, Engine(s, Dice(seed=3)), sword.ref, keeper.ref


def _sword_miss(sword, keeper, *, ref=True):
    blow = {"result": "miss", "weapon": "halberd", "how": "plain"}
    if ref:
        blow["ref"] = keeper
    return Outcome("i1", "attack", verdict="miss", tell=SWORD_MISS_TELL, blows=[blow],
                   actor=sword)


# --- the engine's record --------------------------------------------------------------------

def test_every_miss_names_the_one_it_was_swung_at():
    """A hit's blow carried `ref`, a miss's did not: the narrator was handed a miss at
    nobody, and on 4 of 5 allied misses filled the hole with the player."""
    from rules.intents import parse

    for face in (2, 1):                      # a plain miss, and the natural 1's own path
        s, engine, _sword, keeper = _scene()
        res = engine.run([parse({"op": "attack", "actor": "pc", "target": keeper,
                                 "because": "a test swing"})])
        outcomes = list(res.outcomes)
        if res.awaiting:
            res = engine.resume(face)
            outcomes += list(res.outcomes)
        blows = [b for o in outcomes for b in getattr(o, "blows", []) or []]
        assert blows and blows[0]["result"] == "miss", [o.tell for o in outcomes]
        assert blows[0]["ref"] == keeper


# --- what the call is told ------------------------------------------------------------------

def test_every_blow_fact_names_who_swung_at_whom():
    """"MISS — weapon: halberd; it is evaded" named nobody: 16 of 20 toll-keeper-fight
    allied misses aimed at the player on the replay. Every line now opens on the attacker
    and the one swung at, the player as "you"."""
    s, engine, sword, keeper = _scene()
    miss = planned.blow_facts([_sword_miss(sword, keeper)], engine, said={})[0]
    assert miss.startswith("MISS — the hired sword at Toll-Keeper — weapon: halberd")
    assert "you" not in miss.split(" — ")[1]
    at_you = Outcome("i1", "attack", verdict="hit", tell="Toll-Keeper hits Kesst Vayr.",
                     actor=keeper, blows=[{"result": "hit", "ref": "pc", "weapon": "club",
                                           "severity": "solid", "left": "hurt"}])
    hit = planned.blow_facts([at_you], engine, said={})[0]
    assert hit.startswith("HIT — Toll-Keeper at you — weapon: club")
    # The severity stays the second "; " field, where the bands' tests read it.
    assert hit.split("; ")[1] in planned._SEVERITY["solid"]
    # A recorded miss from before the target was carried keeps the old shape, unguessed.
    old = planned.blow_facts([_sword_miss(sword, keeper, ref=False)], engine, said={})[0]
    assert old.startswith("MISS — weapon: halberd")


def test_blows_aimed_reads_the_engine_and_refuses_to_guess():
    """The toll-keeper's walk drew two attacks of opportunity from the caravan's hands, on
    the toll-keeper's own turn — one of them told at "you". Every blow of the turn counts,
    whoever swung it; a blow that cannot say at whom makes the whole turn unjudgeable."""
    s, engine, sword, keeper = _scene()
    aoo = Outcome("i1", "attack", verdict="miss", tell="x", actor="pc",
                  blows=[{"result": "miss", "ref": keeper}])
    walk = Outcome("i1-close", "move", tell="Toll-Keeper closes 20 ft.", actor=keeper)
    assert planned.blows_aimed([_sword_miss(sword, keeper), aoo, walk]) == [
        (sword, keeper), ("pc", keeper)]
    assert planned.blows_aimed([walk]) == []
    assert planned.blows_aimed([_sword_miss(sword, keeper, ref=False)]) is None
    refused = Outcome("i1", "attack", status="refused", actor=sword,
                      blows=[{"result": "miss"}])
    assert planned.blows_aimed([refused]) == []


def test_the_call_says_whom_and_shows_the_rooms_message_when_it_is_not_you():
    """The creature call's one demonstration was the victim's (the ferryman swings, "you
    duck under it"). tbaMUD sends the room its own message (TO_NOTVICT); so does this, picked
    in code by whom the engine's blows were aimed at."""
    s, engine, sword, keeper = _scene()
    line = planned.aimed_line(engine, [_sword_miss(sword, keeper)])
    assert line == ("Whom each blow was aimed at: the hired sword at Toll-Keeper. No blow "
                    "this turn was aimed at you (the player).")
    msgs = prompts.call_two_messages("", [SWORD_MISS_TELL], [], "the hired sword acts",
                                     acting="the hired sword", pc_name="Kesst Vayr",
                                     aimed=line, at_you=False)
    assert msgs[1]["content"] == prompts.CONSEQUENCE_NPC_ASIDE_EXAMPLE["user"]
    assert "you" not in prompts.CONSEQUENCE_NPC_ASIDE_EXAMPLE["assistant"].lower().split()
    assert line in msgs[-1]["content"]
    # At the player, or unknown: the creature-at-you example it always had.
    for at_you in (True, None):
        msgs = prompts.call_two_messages("", ["Toll-Keeper hits you."], [], "x",
                                         acting="Toll-Keeper", pc_name="Kesst Vayr",
                                         at_you=at_you)
        assert msgs[1]["content"] == prompts.CONSEQUENCE_NPC_EXAMPLE["user"]
    at_you = Outcome("i1", "attack", tell="x", actor=keeper,
                     blows=[{"result": "miss", "ref": "pc"}])
    assert "No blow" not in planned.aimed_line(engine, [at_you])
    # The player's own turn is untouched.
    msgs = prompts.call_two_messages("", ["Kesst Vayr hits Borin."], [], "I punch him",
                                     aimed=line, at_you=False)
    assert msgs[1]["content"] == prompts.CONSEQUENCE_EXAMPLE["user"]
    assert line not in msgs[-1]["content"]


class _World:
    name, secret, premise, entities = "Testholme", "", {}, {}
    unwritten, chronology, factions = [], [], []

    def ancestors(self, _):
        return []


def test_an_allys_turn_reaches_the_model_as_not_at_you_on_both_narrators(monkeypatch):
    """Through the real door (`narrate_outcome`), as `_run_npc_turns` calls it: on the
    planned narrator AND the free one the call is shown the room's example, told whom the
    blow was aimed at, and the blow fact names the toll-keeper. The fault was the call's."""
    from gm import client
    from rules import houserules

    for mode in ("planned", "free"):
        s, engine, sword, keeper = _scene()
        gm = agent_mod.GMAgent(_World(), engine)
        calls = []

        def chat(messages, model, *a, **kw):
            calls.append(messages)
            return client.Reply("The hired sword swings the halberd at Toll-Keeper, who "
                                "steps back from it.", 0.1, model)

        monkeypatch.setattr(agent_mod.client, "chat", chat)
        monkeypatch.setattr(houserules, "narration", lambda mode=mode: mode)
        gm.narrate_outcome("", [_sword_miss(sword, keeper)], "the hired sword acts",
                           rewrite=False, acting="the hired sword")
        first = calls[0]
        assert first[1]["content"] == prompts.CONSEQUENCE_NPC_ASIDE_EXAMPLE["user"], mode
        assert "No blow this turn was aimed at you" in first[-1]["content"], mode
        if mode == "planned":
            assert "MISS — the hired sword at Toll-Keeper" in first[-1]["content"]


def test_the_wrong_actor_repair_no_longer_aims_every_act_at_the_player():
    """It said the player was "the one it is done to": on an ally's turn, an order to turn
    the blow on the player. The tells say whom it is done to."""
    assert "the one it is done to" not in prompts.ACTOR_REPAIR_BRIEFING
    assert "whoever the" in prompts.ACTOR_REPAIR_BRIEFING
    assert ("CONSEQUENCE_NPC_ASIDE_EXAMPLE", prompts.CONSEQUENCE_NPC_ASIDE_EXAMPLE[
        "assistant"]) in prompts.demonstrations()


# --- the read back ------------------------------------------------------------------------

PIVOT = "The wood whistles through the air, and you pivot away from the arc of the swing."
LUNGE = "The lead teamster lunges forward with a heavy, practiced swing of the club."
BEAT = f"{LUNGE} {PIVOT}"
PEOPLE = (bv.Person(ref="pc", name="Kesst Vayr", pc=True),
          bv.Person(ref="c5", name="the lead teamster", what="teamster"),
          bv.Person(ref="c7", name="the hired sword", what="mercenary"),
          bv.Person(ref="c8", name="Toll-Keeper", what="toll-keeper"),
          bv.Person(ref="c9", name="the drover", here=False))
TEAMSTER = {"intent_id": "i1", "op": "attack", "status": "resolved", "actor": "c5",
            "blows": [{"result": "miss", "ref": "c8", "weapon": "club"}],
            "tell": "the lead teamster's attack with the club misses Toll-Keeper (4 against "
                    "AC 18)."}
KEEPER = {"intent_id": "i1", "op": "attack", "status": "resolved", "actor": "c8",
          "blows": [{"result": "miss", "ref": "pc", "weapon": "halberd"}],
          "tell": "Toll-Keeper's attack with the halberd misses Kesst Vayr (7 against AC 19)."}


class _Reply:
    def __init__(self, obj):
        self.text = json.dumps(obj)
        self.seconds, self.model = 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _facts(outcomes=(TEAMSTER,), acting="c5"):
    ctx = SimpleNamespace(acting=acting, intimate=False, door="outcome")
    got = bv._aimed_of(ctx, outcomes, SimpleNamespace(in_encounter=True))
    return bv.Facts(start="the road", end="the road", places=("the road",), people=PEOPLE,
                    in_fight=True, outcomes=tuple(outcomes), **got)


def _claim(striker, target, sentence=PIVOT):
    return bv.Claim("aimed", {"striker": striker, "target": target}, "x y z", sentence, True)


def test_asked_only_on_a_creatures_turn_in_a_fight():
    fight = SimpleNamespace(in_encounter=True)
    on = SimpleNamespace(acting="c5", intimate=False)
    assert bv._aimed_of(on, (TEAMSTER,), fight) == {"aimed": (("c5", "c8"),)}
    for ctx, scene in ((SimpleNamespace(acting="", intimate=False), fight),
                       (SimpleNamespace(acting="c5", intimate=True), fight),
                       (on, SimpleNamespace(in_encounter=False))):
        assert bv._aimed_of(ctx, (TEAMSTER,), scene) == {}
    unknown = dict(TEAMSTER, blows=[{"result": "miss"}])
    assert bv._aimed_of(on, (unknown,), fight) == {}


def test_an_allys_miss_told_at_the_player_is_a_contradiction_by_code():
    """The four shipped wrong beats: whoever the page says swung — named, or "not shown"
    as in "you pivot away from the arc of the swing" — a blow at the player on a turn
    whose blows went elsewhere is wrong. The fact names whom they went at."""
    facts = _facts()
    for striker in ("c5", bv.NOT_SHOWN):
        found = bv.diff([_claim(striker, "pc")], facts)
        assert [d.category for d in found] == ["aimed"], striker
        assert found[0].fact == ("The lead teamster swung at Toll-Keeper. No blow was aimed "
                                 "at you (the player).")
        assert found[0].line == TEAMSTER["tell"]
    # The truth, and what is not judged: somebody not listed, the away, a striker whose
    # blow is not shown at somebody else, the player's own blow, an unrolled striker.
    for claim in (_claim("c5", "c8"), _claim(bv.NOT_SHOWN, "c8"),
                  _claim(bv.NEW_PERSON, bv.NEW_PERSON), _claim("c5", bv.NEW_PERSON),
                  _claim("c5", "c9"), _claim("pc", "c7"), _claim("c7", "c5"),
                  # "swinging the heavy flail in a wide, desperate arc": at nobody named.
                  _claim("c5", bv.NOT_SHOWN)):
        assert bv.diff([claim], facts) == [], claim.slots


def test_the_reverse_a_foes_swing_moved_between_the_player_and_an_ally():
    """A foe at the player told at an ally, and a foe at an ally told at the player."""
    at_you = _facts((KEEPER,), acting="c8")
    assert [d.category for d in bv.diff([_claim("c8", "c7")], at_you)] == ["aimed"]
    assert bv.diff([_claim("c8", "pc")], at_you) == []
    at_ally = dict(KEEPER, blows=[{"result": "miss", "ref": "c7"}])
    facts = _facts((at_ally,), acting="c8")
    assert [d.category for d in bv.diff([_claim(bv.NOT_SHOWN, "pc")], facts)] == ["aimed"]
    assert bv.diff([_claim("c8", "c7")], facts) == []


def test_the_read_asks_who_at_whom_in_the_codes():
    facts = _facts()
    asked = []

    def chat(messages, *a, schema=None, **k):
        props = (schema or {}).get("properties", {})
        asked.append(next(iter(props), ""))
        if "aimed_at" in props:
            item = props["aimed_at"]["items"]["properties"]
            assert item["striker"]["enum"] == ["pc", "c5", "c7", "c8", bv.NEW_PERSON,
                                               bv.NOT_SHOWN]
            assert item["target"]["enum"] == ["pc", "c5", "c7", "c8", bv.NEW_PERSON,
                                              bv.NOT_SHOWN]
            assert "pc: you (the player)" in messages[-1]["content"]
            return _Reply({"aimed_at": [
                {"striker": "c5", "target": "c8", "quote": "lunges forward with a heavy"},
                {"striker": bv.NOT_SHOWN, "target": "pc",
                 "quote": "you pivot away from the arc of the swing"}]})
        return _Reply({"player_ends_at": {"place": "the road", "quote": ""},
                       "changed_hands": [], "trades": [], "harmed": [], "arrived": [],
                       "left": [], "time_of_day": [], "conditions": [], "setting": []})

    reading = bv.read(BEAT, facts, model="stub", chat=chat)
    assert "aimed_at" in asked
    found = [d for d in bv.diff(reading.claims, facts, BEAT) if d.category == "aimed"]
    assert [d.sentence for d in found] == [PIVOT]


def test_the_second_read_asks_whom_with_the_passage_and_without_the_tells():
    facts = _facts()
    d = bv.diff([_claim(bv.NOT_SHOWN, "pc")], facts)[0]
    seen = []

    def chat(messages, *a, answer=None, **k):
        seen.append(messages[-1]["content"])
        return _Reply({"blows": answer})

    for answer, kept in (([{"striker": "c5", "target": "pc"}], True),
                         ([{"striker": "c5", "target": "c8"}], False),
                         ([], False)):
        held, _r, _s = bv.confirm([d], BEAT, facts, model="stub",
                                  chat=lambda *a, answer=answer, **k: chat(*a, answer=answer,
                                                                           **k))
        assert (d in held) is kept, answer
    assert LUNGE in seen[0] and "misses Toll-Keeper" not in seen[0]


def test_the_kind_is_cut_only_and_the_engines_line_takes_the_first_place(monkeypatch):
    """No one-sentence rewrite: on the five wrong sentences of the road fight, three
    rewrites each, 9 of 15 put the blow on another wrong person or landed a miss ("the blade
    strikes the hired sword"), and the re-read of the rewritten sentence alone passed 6 of
    those 9."""
    from gm import checks
    from gm.narration import Finding

    assert beat_verified._KIND["aimed"] == ("beat-aimed-wrong", 3)
    assert "beat-aimed-wrong" in beat_verified.CUT_ONLY
    assert "beat-aimed-wrong" in beat_verified.KINDS
    facts = _facts()
    found = bv.diff([_claim("c5", "pc", LUNGE), _claim(bv.NOT_SHOWN, "pc", PIVOT)], facts)
    monkeypatch.setattr(beat_verified, "discrepancies", lambda ctx: found)
    ctx = BeatContext(door="outcome", text=BEAT, player_text="", engine=None, scene=None,
                      world=None, location=None, reading=None, outcomes=(), tells=(),
                      said=(), attribution=None, brief="", brief_facts={}, pull=None,
                      was_at="", acting="c5", turn=0)
    out, notes = beat_verified.backstop(ctx, BEAT, [])
    assert out == "The lead teamster's attack with the club misses Toll-Keeper."
    assert any("aimed" in n for n in notes)

    def no_model(*a, **k):
        raise AssertionError("a cut-only kind was sent to the model")

    monkeypatch.setattr(agent_mod.client, "chat", no_model)
    f = Finding("beat-aimed-wrong", "x", "y", weight=3, sentences=(PIVOT,))
    monkeypatch.setattr(beat_verified, "find", lambda c: [f] if PIVOT in c.text else [])
    monkeypatch.setattr(beat_verified, "backstop",
                        lambda c, text, found: (text.replace(PIVOT, "").strip(), ["cut"]))
    monkeypatch.setattr(checks, "owner_of", lambda kind: beat_verified)
    agent = SimpleNamespace(engine=SimpleNamespace(scene=SimpleNamespace(
        pc=lambda: None, actors={})), _TRUTH_CALLS=3)
    out, _notes, attempts = agent_mod.GMAgent._repair_sentences(agent, BEAT, [f], ctx)
    assert PIVOT not in out and attempts == []
