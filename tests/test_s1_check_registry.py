"""S1 of the 2026-09-28 fix pass: the narrator-check registry, and nothing it changes yet.

`gm/checks/` is where Phase 2's truth checks land — one module each, found by filename, run
in `GMAgent._groom` right after `mentions.attribute` (docs/fix-interfaces.md §2.1). The
plan first hooked them into `narration.review()`; the critic pass measured that seam as
wrong: `review()` runs only inside `polish`, only when `rewrite=True`, and before the
attribution exists, so a check there would never know who the prose means and would miss
every NPC beat (§1.1 P2).

What this file holds the seam to:

  * **Inert.** With the registry empty, the beat, the repair notes, the review's findings
    and every log row are byte-identical with and without a `BeatContext`. Measured the
    day it landed against the code before it (phase-1-base, a5955ef) by a whole-turn
    replay of the 104 recorded audit turns in tests/replay/ — 587 model calls with their
    prompt and schema hashes, 575 turn-log rows, 337 transcript beats, 154 `review()`
    runs — plus the 4 plan replays and the Bobby corpus's 14 beats through four doors:
    one dump, byte-identical (sha256 5f8938e0…) on both. The same replay with a spy
    member saw the turn door 108 times, the NPC door 39 and the consequence door 39.
  * **Discovery by filename**, `_`-prefixed modules as helpers, ordered by (ORDER, name),
    and a module that breaks the member contract refused with the fix named.
  * **A finding reaches the repair**: a throwaway member dropped into the package finds a
    sentence, and `_repair_sentences` — a stub until Lane A — is handed it.
  * **`head_of`**, the one head-noun rule, on the twelve opening companions: the last-word
    rule `judgement._mentions` uses was wrong for 12 of 12 ("through", "you" twice,
    "door"…), which is how Bobby's watchman was owed his face on the beat that said "the
    way through".
  * The seams other lanes code against: `Finding.sentences`, `interpret.travel_choices`,
    `attached=` on `declared_ops`/`inject_cast`, and the spec naming the three discovered
    packages so the frozen app finds what the source tree finds.
"""
from __future__ import annotations

import ast
import gzip
import json
import sys
from pathlib import Path

import pytest
from django.test import override_settings

import replays
from gm import checks, narration
from gm.checks import BeatContext, CheckContractError
from gm.checks._people import _DETERMINERS, _WORD, _by_boundary, head_of
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.sheet import load_pc
from world.loader import load_cached

ROOT = Path(__file__).resolve().parent.parent
REPLAY = ROOT / "tests" / "replay"
WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id


# --- helpers ------------------------------------------------------------------------------

def _agent(people=()):
    """An agent on Vormoor with the PC and the named people standing in the scene."""
    from gm.agent import GMAgent

    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    for name, template in people:
        s.add(instantiate(template, scene=s, name=name))
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    return GMAgent(WORLD, e)


def _ctx(agent, door="turn", **over) -> BeatContext:
    base = dict(player_input="I look around.", brief="", outcomes=(), tells=())
    base.update(over)
    return agent._beat_context(door, **base)


def _drafts():
    """Every recorded prose draft in tests/replay/, with the save it was written for."""
    for f in sorted(REPLAY.glob("*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for n, line in enumerate(fh):
                rec = json.loads(line)
                for call in rec["calls"]:
                    if call["role"] not in ("narrate_turn", "narrate_outcome"):
                        continue
                    try:
                        d = json.loads(call["raw"])
                        text = str(d.get("narration", "")) if isinstance(d, dict) else ""
                    except ValueError:
                        text = str(call["raw"])
                    if text.strip():
                        yield f"{f.name}:{n}", rec, text


class _Reply:
    def __init__(self, text, model="stub"):
        self.text, self.seconds, self.model = text, 0.0, model
        self.prompt_tokens = self.reply_tokens = 0
        self.done_reason = "stop"

    def json(self):
        return json.loads(self.text)


def _groom_both_ways(agent_for, text, monkeypatch, **kw):
    """`_groom` without a context and with one, the registry empty, on fresh agents; what
    each produced, the review's findings included."""
    seen: list = []
    real_review = narration.review

    def spy(*a, **k):
        r = real_review(*a, **k)
        seen.append(r.as_log())
        return r

    monkeypatch.setattr(narration, "review", spy)
    monkeypatch.setattr(checks, "registered", lambda: ())
    got = []
    for with_ctx in (False, True):
        del seen[:]
        agent = agent_for()
        agent.last_said = []
        lifted = agent._lift(text)
        ctx = _ctx(agent, player_input=kw.get("player_input", "")) if with_ctx else None
        out, repairs, attempts = agent._groom(lifted, ctx=ctx, **kw)
        got.append({"text": out, "repairs": repairs,
                    "attempts": [(a.kind, a.model, a.raw, a.note) for a in attempts],
                    "rows": agent.mention_rows, "said": agent.last_said,
                    "reviews": list(seen)})
    monkeypatch.setattr(narration, "review", real_review)
    return got


# --- inert ------------------------------------------------------------------------------------

def test_with_an_empty_registry_the_recorded_drafts_groom_byte_identically(
        tmp_path, monkeypatch):
    """Every recorded prose draft in tests/replay/ (147 on the day this landed), through
    `_groom` with the rewrite on — a stubbed model answers the polish — without a context
    and with one: the beat, the notes, the attempts, the mention rows, the lifted speech
    and every `review()` finding are identical. The rewrite is on so the review runs;
    the seam must not move it either."""
    from gm import client as gm_client
    from gm.agent import GMAgent
    from play import campaign as cm

    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: _Reply(
        json.dumps({"narration": "You wait, and the room goes on around you. "
                                 "What do you do?"})))
    n = 0
    with override_settings(CAMPAIGN_DIR=str(tmp_path)):
        for where, rec, text in _drafts():
            save = rec["save_before"]
            path = tmp_path / f"{save['id']}.json"
            path.write_text(json.dumps(save), encoding="utf-8")

            def fresh():
                c = cm.Campaign.load(path)
                return GMAgent(c.world, c.engine())

            without, with_ctx = _groom_both_ways(
                fresh, text, monkeypatch, earlier=[], player_input=rec["player"],
                brief="", hand_back=True, claims=True, rewrite=True)
            assert with_ctx == without, where
            n += 1
    assert n >= 100, f"only {n} recorded drafts found in tests/replay/"


@pytest.mark.skipif(not replays.available(), reason="the Bobby corpus is not on this disk")
def test_with_an_empty_registry_the_bobby_beats_groom_byte_identically(monkeypatch):
    """The owner's playtest of 2026-09-28: the opening and all 13 beats, on a scene holding
    the save's nine people, through `_groom` without a context and with one."""
    people = [p for p in replays.save("bobby.json")["people"] if p["kind"] != "pc"]

    def fresh():
        agent = _agent([(p["name"], p.get("from_template") or "guildhand")
                        for p in people])
        return agent

    texts = [replays.opening()["text"]] + [b["text"] for t in replays.turns()
                                           for b in t["beats"]]
    earlier: list[str] = []
    for text in texts:
        for rewrite in (False, True):
            without, with_ctx = _groom_both_ways(
                fresh, text, monkeypatch, earlier=list(earlier), player_input="",
                brief="", hand_back=True, claims=True, rewrite=rewrite)
            assert with_ctx == without, text[:80]
        earlier.append(text)
    assert len(texts) == 14


def test_the_real_registry_holds_no_member_yet_so_the_game_is_unchanged():
    """Phase 1 shipped the registry empty: `_people` is a helper, not a member. Changed on
    purpose when Phase 2's checks landed — Lane B's four space checks are members, and
    the helpers (`_people`, `_space`) still are not."""
    names = {m.__name__.rsplit(".", 1)[-1] for m in checks.registered()}
    assert {"land_described", "bearing_invented", "road_claimed", "route_walked"} <= names
    assert not {n for n in names if n.startswith("_")}


# --- discovery -----------------------------------------------------------------------------

_MEMBER = '''
from gm.narration import Finding
ORDER = {order}
KINDS = frozenset({{"{kind}"}})
DOORS = frozenset({doors})
def find(ctx):
    return [Finding("{kind}", "found", sentences=({sentence!r},))] if {sentence!r} in ctx.text else []
'''


@pytest.fixture
def package(tmp_path, monkeypatch):
    """`gm.checks` with a throwaway directory on its path: a module written there is a
    member exactly as a file in gm/checks/ would be."""
    monkeypatch.setattr(checks, "__path__", [str(tmp_path)])
    written: list[str] = []

    def write(name, body):
        (tmp_path / f"{name}.py").write_text(body, encoding="utf-8")
        written.append(f"gm.checks.{name}")

    yield write
    for mod in written:
        sys.modules.pop(mod, None)


def _member(kind, order=50, doors='{"plan", "turn", "npc", "outcome"}', sentence="x"):
    return _MEMBER.format(kind=kind, order=order, doors=doors, sentence=sentence)


def test_members_are_found_by_filename_sorted_by_order_then_name(package):
    """No list to edit: three files and a helper. Order is (ORDER, module name); the
    `_`-prefixed helper is imported by nobody and registered as nothing."""
    package("s1_zulu", _member("zulu", order=10))
    package("s1_alpha", _member("alpha", order=10))
    package("s1_first", _member("first", order=1))
    package("_s1_helper", "raise RuntimeError('a helper is never imported as a member')\n")
    names = [m.__name__ for m in checks.registered()]
    assert names == ["gm.checks.s1_first", "gm.checks.s1_alpha", "gm.checks.s1_zulu"]
    assert checks.owner_of("alpha").__name__ == "gm.checks.s1_alpha"
    assert checks.owner_of("nobody-declares-this") is None


@pytest.mark.parametrize("body, says", [
    ("KINDS = frozenset({'k'})\nDOORS = frozenset({'turn'})\ndef find(ctx): return []\n",
     "ORDER must be an int"),
    ("ORDER = True\nKINDS = frozenset({'k'})\nDOORS = frozenset({'turn'})\n"
     "def find(ctx): return []\n", "ORDER must be an int"),
    ("ORDER = 1\nKINDS = {'k'}\nDOORS = frozenset({'turn'})\ndef find(ctx): return []\n",
     "KINDS must be a non-empty frozenset"),
    ("ORDER = 1\nKINDS = frozenset({'k'})\nDOORS = frozenset({'consequence'})\n"
     "def find(ctx): return []\n", "DOORS must be a non-empty frozenset"),
    ("ORDER = 1\nKINDS = frozenset({'k'})\nDOORS = frozenset({'turn'})\n",
     "needs `def find(ctx)"),
    ("ORDER = 1\nKINDS = frozenset({'k'})\nDOORS = frozenset({'turn'})\n"
     "def find(ctx): return []\nbackstop = 3\n", "`backstop` must be a function"),
])
def test_a_member_that_breaks_the_contract_is_refused_with_the_fix_named(
        package, body, says):
    """The validator-door rule applied to code: a malformed member fails loudly, naming
    itself and the fix, rather than checking nothing in the packaged app."""
    package("s1_broken", body)
    with pytest.raises(CheckContractError) as err:
        checks.registered()
    assert "gm.checks.s1_broken" in str(err.value) and says in str(err.value)


def test_two_members_may_not_claim_one_kind(package):
    """A kind has one owner, so the repair can find the backstop that goes with it."""
    package("s1_one", _member("same"))
    package("s1_two", _member("same"))
    with pytest.raises(CheckContractError, match="both declare the kind 'same'"):
        checks.registered()


# --- run -------------------------------------------------------------------------------------

def _finding(kind, sentences=(), weight=1):
    return narration.Finding(kind, "d", weight=weight, sentences=tuple(sentences))


class _Fake:
    """A member without a file, for the rules of `run` alone."""
    def __init__(self, name, found, doors=checks.ALL_DOORS, order=50, kinds=None):
        self.__name__ = f"gm.checks.{name}"
        self.ORDER, self.DOORS = order, frozenset(doors)
        self.KINDS = frozenset(kinds or {f.kind for f in found} or {name})
        self._found = found

    def find(self, ctx):
        if isinstance(self._found, Exception):
            raise self._found
        return list(self._found)


def _run(monkeypatch, *members, door="turn", errors=None):
    monkeypatch.setattr(checks, "registered", lambda: tuple(members))
    return checks.run(_ctx(_agent(), door), errors=errors)


def test_a_member_runs_only_at_the_doors_it_opted_into(monkeypatch):
    turn_only = _Fake("turnish", [_finding("a")], doors={"turn"})
    assert [f.kind for f in _run(monkeypatch, turn_only, door="turn")] == ["a"]
    assert _run(monkeypatch, turn_only, door="npc") == []


def test_a_finding_a_heavier_one_already_covers_is_dropped(monkeypatch):
    """Two checks on one sentence cost one repair (design A, item 22.4): the lighter
    finding whose every sentence the heavier one flagged goes; one that also flags a
    sentence of its own stays; a finding with no sentences is never dropped; at equal
    weight the earlier in run order counts as the heavier, so a duplicate goes once."""
    heavy = _Fake("heavy", [_finding("h", ["The guard burns."], weight=3)])
    light = _Fake("light", [_finding("l", ["The guard  burns."], weight=1),
                            _finding("l2", ["The guard burns.", "He screams."]),
                            _finding("l3", [])])
    twin = _Fake("twin", [_finding("t", ["He screams."], weight=1)])
    kept = _run(monkeypatch, heavy, light, twin)
    assert [f.kind for f in kept] == ["h", "l2", "l3"]


def test_a_broken_check_costs_its_own_findings_not_the_turn(monkeypatch):
    """The game passes an error list: the member's exception becomes a row, the others'
    findings stand. The tests pass none, and the exception travels."""
    good = _Fake("good", [_finding("g")])
    bad = _Fake("bad", RuntimeError("boom"), kinds={"b"})
    errors: list = []
    assert [f.kind for f in _run(monkeypatch, bad, good, errors=errors)] == ["g"]
    assert errors == [{"kind": "check-error", "member": "bad",
                       "error": "RuntimeError: boom"}]
    with pytest.raises(RuntimeError):
        _run(monkeypatch, bad, good)


def test_a_finding_of_an_undeclared_kind_breaks_the_contract(monkeypatch):
    stray = _Fake("stray", [_finding("undeclared")], kinds={"declared"})
    with pytest.raises(CheckContractError, match="not in its KINDS"):
        _run(monkeypatch, stray)


# --- a finding reaches the repair -------------------------------------------------------

def test_a_throwaway_member_finding_reaches_the_repair_through_a_real_door(
        package, monkeypatch):
    """A file dropped into the package, found by name, run at the consequence door on a
    real `narrate_outcome`: its finding — with the sentence it flags — is handed to
    `_repair_sentences` with the context brought up to the draft, what the repair returns
    is the beat, and the findings are logged as one `truth-checks` row."""
    from gm import client as gm_client
    from gm.agent import GMAgent

    sentence = "The guard's cloak catches fire."
    package("s1_throwaway", _member("throwaway", sentence=sentence))
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: _Reply(
        f"You shove past. {sentence} Nobody moves."))
    handed = []

    def repair(self, text, findings, ctx):
        handed.append((text, list(findings), ctx))
        return text.replace(sentence, "The guard steps back."), ["repaired one"], []

    monkeypatch.setattr(GMAgent, "_repair_sentences", repair)
    agent = _agent([("the guard", "watchman")])
    out, attempt = agent.narrate_outcome(
        "", [Outcome(intent_id="i1", op="move", tell="Kesst Vayr moves.")],
        "I shove past the guard.", rewrite=False)
    assert len(handed) == 1
    text, findings, ctx = handed[0]
    assert [f.kind for f in findings] == ["throwaway"]
    assert findings[0].sentences == (sentence,)
    assert ctx.door == "outcome" and ctx.text == text and sentence in ctx.text
    assert ctx.attribution is agent.attribution
    assert ctx.tells == ("Kesst Vayr moves.",) and len(ctx.outcomes) == 1
    assert ctx.player_text == "I shove past the guard."
    assert "The guard steps back." in out and sentence not in out
    assert "repaired one" in attempt.note
    row = [r for r in agent.mention_rows if r.get("kind") == "truth-checks"]
    assert row == [{"kind": "truth-checks", "door": "outcome",
                    "findings": [{"kind": "throwaway", "detail": "found",
                                  "sentences": [sentence]}],
                    "repairs": ["repaired one"]}]


def test_the_repair_is_a_stub_until_lane_a():
    agent = _agent()
    f = _finding("k", ["A sentence."])
    assert agent._repair_sentences("A sentence.", [f], _ctx(agent)) == ("A sentence.", [], [])


def _agent_method(name: str) -> ast.FunctionDef:
    """A `GMAgent` method's syntax tree, read off gm/agent.py (walked, not text-matched:
    tests/test_suite_isolation.py caps the source-text pins)."""
    tree = ast.parse((ROOT / "gm" / "agent.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "GMAgent")
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _calls(fn: ast.AST, attr: str) -> list[ast.Call]:
    return [n for n in ast.walk(fn) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr == attr]


def test_the_four_callers_each_build_a_context_for_their_door():
    """`plan_turn`, `npc_turn`, `narrate_turn` and `narrate_outcome` are `_groom`'s four
    callers — and the only ones — and each hands it a context named for its door."""
    tree = ast.parse((ROOT / "gm" / "agent.py").read_text(encoding="utf-8"))
    callers = sorted({f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
                      and _calls(f, "_groom")})
    assert callers == ["narrate_outcome", "narrate_turn", "npc_turn", "plan_turn"]
    for name, door in (("plan_turn", "plan"), ("npc_turn", "npc"),
                       ("narrate_turn", "turn"), ("narrate_outcome", "outcome")):
        for call in _calls(_agent_method(name), "_groom"):
            ctx = next((k.value for k in call.keywords if k.arg == "ctx"), None)
            assert isinstance(ctx, ast.Call) and ctx.func.attr == "_beat_context", name
            assert ast.literal_eval(ctx.args[0]) == door, name


def test_the_npc_door_carries_the_acting_ref_and_the_turn_door_its_outcomes(monkeypatch):
    """What the doors put in the context, read by a spy member on real calls."""
    from gm import client as gm_client

    seen: list[BeatContext] = []
    spy = _Fake("spy", [])
    spy.find = lambda ctx: seen.append(ctx) or []
    monkeypatch.setattr(checks, "registered", lambda: (spy,))
    agent = _agent([("the guard", "watchman")])
    guard = next(r for r, a in agent.engine.scene.actors.items() if a.name == "the guard")
    words = "The guard shifts his weight and says nothing."
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: _Reply(
        json.dumps({"narration": words,
                    "intents": [{"op": "narrate_only", "because": "waits"}]})
        if k.get("as_json") else words))
    agent.turn = 7
    agent.npc_turn(guard)
    outcomes = [Outcome(intent_id="i1", op="move", tell="Kesst Vayr moves."),
                Outcome(intent_id="i2", op="travel", status="refused")]
    agent.narrate_turn(outcomes, "I go.", "THE BRIEF", [], pull={"text": "a thread"})
    agent.narrate_outcome("", outcomes, "I go.", acting="the guard")
    doors = [c.door for c in seen]
    assert doors == ["npc", "turn", "outcome"]
    npc, turn, outcome = seen
    assert npc.acting == guard and npc.turn == 7 and npc.outcomes == ()
    # All of the outcomes, the refused and tell-less one included.
    assert turn.outcomes == tuple(outcomes) and turn.tells == ("Kesst Vayr moves.",)
    assert turn.brief == "THE BRIEF" and turn.pull == {"text": "a thread"}
    assert outcome.acting == guard
    assert all(c.was_at == agent.engine.scene.at for c in seen)


def test_plan_turn_remembers_where_the_turn_began(monkeypatch):
    """`BeatContext.was_at` is where the party stood when the turn began, set on the way
    in — before Continue's early return, which asks no model."""
    from gm import prompts

    agent = _agent()
    agent.engine.scene.at = "somewhere-else"
    agent.plan_turn(prompts.CARRY_ON, history=[])
    assert agent._was_at == "somewhere-else"


def test_the_view_hands_brief_facts_and_attachments_through_attributes():
    """S3 sets `agent.brief_facts` and `agent.attachments` the way `agent.buying` is set:
    absent, the context carries empty defaults; present, it carries them."""
    agent = _agent()
    assert _ctx(agent).brief_facts == {}
    agent.brief_facts = {"roads_out": {"roads": ["Dustgate"]}}
    assert _ctx(agent).brief_facts == {"roads_out": {"roads": ["Dustgate"]}}


# --- head_of -----------------------------------------------------------------------------

def _last_word(name: str) -> str:
    """The rule `judgement._mentions` keys a person on today: the last word of three
    letters or more. Kept here as the measurement, not imported, so Lane A's fix of the
    live copy does not rewrite the evidence."""
    return [w for w in name.lower().split() if len(w) >= 3][-1]


def test_head_of_the_twelve_opening_companions():
    """The companions of `play/opening.py` SITUATIONS. The last-word rule was wrong for
    12 of 12 — "through", "you" twice, "door", "table", "notices", "time", "harness",
    "step", "round", "words", "stall" — and `head_of` is right for 12 of 12; so is its
    boundary step on its own, without the person-word list in front of it."""
    from play.opening import SITUATIONS

    want = ["woman", "man", "foreman", "man", "watchman", "crier", "apprentice",
            "servant", "drover", "stranger", "lamplighter", "neighbour"]
    names = [s.who for s in SITUATIONS]
    assert len(names) == 12
    assert [head_of(n) for n in names] == want
    boundary_only = [_by_boundary([w.lower() for w in _WORD.findall(n)
                                   if w.lower() not in _DETERMINERS]) for n in names]
    assert boundary_only == want
    wrong = [n for n, w in zip(names, want) if _last_word(n) != w]
    assert len(wrong) == 12, "the measurement this rule replaces"


@pytest.mark.parametrize("name, head", [
    ("Soren Kragnirath", "Soren Kragnirath"),     # a proper name keeps its own words
    ("the smith's wife", "wife"),                 # a possessor is not the head
    ("the young king", "king"),                   # an -ing noun is not a participle
    ("man with the marked knuckles", "man"),
    ("second thug", "thug"),
    ("The woman at the stall", "woman"),          # capitalised at a sentence's head
    ("girl", "girl"),
    ("", ""),
])
def test_head_of_beyond_the_openings(name, head):
    assert head_of(name) == head


def test_head_of_is_wired_into_nothing_yet():
    """Phase 1 delivers the helper; Lane A points every copy of the rule at it in Phase 2.
    Until then nothing outside gm/checks and the tests imports it."""
    users = [p for p in (ROOT / "gm").rglob("*.py")
             if "checks" not in p.parts and "head_of" in p.read_text(encoding="utf-8")]
    users += [p for p in (ROOT / "play").rglob("*.py")
              if "head_of" in p.read_text(encoding="utf-8")]
    assert users == []


# --- the other seams ---------------------------------------------------------------------

def test_a_finding_carries_no_sentences_unless_given():
    f = narration.Finding("k", "detail")
    assert f.sentences == () and isinstance(f.sentences, tuple)
    assert narration.Finding("k", "d", "hint", 2).weight == 2   # positional use unchanged


def test_travel_choices_is_todays_tuple():
    """Moved out of `plan_turn` unchanged: every place here but the party's own, by name.
    The frame and the settlement are accepted and not read (Lane B widens it)."""
    from gm import interpret

    agent = _agent()
    scene, places = agent.engine.scene, agent.engine.places()
    today = tuple(p.name for p in places if p.id != scene.at)
    assert today, "Vormoor should have places to walk to"
    loc = object()
    assert interpret.travel_choices(None, scene, places, loc) == today
    assert interpret.travel_choices({"actions": [{"act": "go", "place": "x"}]},
                                    scene, places, loc) == today
    schema = _calls(_agent_method("plan_turn"), "turn_schema")
    places = [k.value for c in schema for k in c.keywords if k.arg == "places"]
    assert places and all(isinstance(p, ast.Call) and p.func.attr == "travel_choices"
                          for p in places)


def test_declared_ops_and_inject_cast_accept_attachments_and_ignore_them():
    """The keyword only, in Phase 1 (Lane E reads it in Phase 2): the same answer with a
    spell attached as without."""
    from gm import judgement

    agent = _agent()
    scene = agent.engine.scene
    attached = ({"kind": "spell", "id": "burning-hands", "name": "Burning Hands"},)
    for words in ("I cast magic missile at the thug", "I walk to the market",
                  "I buy a rope"):
        assert judgement.declared_ops(words, scene, WORLD, attached=attached) == \
            judgement.declared_ops(words, scene, WORLD)
        assert judgement.inject_cast([], words, scene, attached=attached) == \
            judgement.inject_cast([], words, scene)


def _spec_assignments() -> dict[str, ast.AST]:
    tree = ast.parse((ROOT / "pathfindergm.spec").read_text(encoding="utf-8"))
    return {t.id: node.value for node in tree.body if isinstance(node, ast.Assign)
            for t in node.targets if isinstance(t, ast.Name)}


def test_the_spec_ships_the_three_discovered_packages():
    """Nothing imports a member by name, so a member missing from the bundle is not an
    error — the frozen app just discovers nothing. The spec names the three packages whose
    members are found by filename, collects each only when its `__init__.py` is on disk
    (S2's and S3's land on their own branches), and feeds them to the hidden imports."""
    found = _spec_assignments()
    assert ast.literal_eval(found["DISCOVERED_PACKAGES"]) == (
        "gm.checks", "gm.brief", "play.aftermath")
    hidden = ast.unparse(found["hiddenimports"])
    assert "discovered" in hidden
    src = (ROOT / "pathfindergm.spec").read_text(encoding="utf-8")
    assert '"__init__.py").is_file()' in src
    assert (ROOT / "gm" / "checks" / "__init__.py").is_file()
