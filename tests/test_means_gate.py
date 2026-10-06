"""A deed the character has no means to do is refused, whatever the deed is (gm/means.py).

The owner, 2026-10-05: "getting rid of the regex has brought back the ability to use
psychic powers and alter memories through narration" — and then, "whatever you do must
catch anything that is not within the players power to do not just psychic and memory
stuff".

Reproduced live on a copy of the owner's save (a level-1 asura wizard at the smithy),
before this gate existed:
  * "I make the smith forget he saw me" matched no pattern of the regex door; the plan
    made it Diplomacy against the smith's Perception, and a roll was asked for a memory
    wipe.
  * "I erase the apprentice's memory of me" matched the regex, which stood down because
    the plan had guessed `cast charm-person`; the engine refused the cast (not prepared),
    the turn dropped it as "an op nobody asked for", and the page wrote "the flicker of
    recognition of your presence … simply dissolves".
  * On the means corpus (tests/means/gold.py, 87 deeds out of reach) the three regex doors
    together refused 9. The reader's `means` and the sheet: see docs/means-gate.md.

These tests hand the gate the reading the live reader gave (or would give) and pin what
code does with it; the reading itself is measured by tools/means_bench.py.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from gm import interpret, means
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from tests._places import stand_on


def _scene(sheet="fixtures/pc-kesst.json"):
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    s.add(load_pc(sheet))
    s.add(instantiate("guildhand", scene=s, name="the smith"))
    return s


def _frame(*actions, claims=()):
    return {"question": False, "claims": list(claims), "actions": list(actions)}


FORGET = {"act": "other", "target": "the smith", "means": "beyond",
          "span": "make the smith forget he saw me"}
ERASE = {"act": "other", "target": "the apprentice", "means": "beyond",
         "span": "erase the apprentice's memory of me"}


# --- the reading ------------------------------------------------------------------------

def test_the_means_is_a_required_enum_in_every_alternative():
    """Ollama enforces required properties and enums (6 of 6, memory
    `ollama-schema-enforcement`) — and an optional property is one the grammar lets it
    skip (slot recall 0.0 on 220 of 220 lines when slots were optional, 2026-09-27)."""
    for alt in interpret.per_act_schema()["properties"]["actions"]["items"]["anyOf"]:
        assert alt["properties"]["means"]["enum"] == list(interpret.MEANS)
        assert "means" in alt["required"] and "power" in alt["required"]
        # Last, so it chooses no act: the act is chosen straight after the span.
        assert list(alt["properties"])[-1] == "means"
    flat = interpret.schema()["properties"]["actions"]["items"]
    assert "means" in flat["required"]


def test_a_power_named_is_held_to_the_players_words():
    frame, dropped = interpret.ground(
        {"question": False, "claims": [], "actions": [
            {"span": "cast sleep on the guards", "act": "cast", "object": "sleep",
             "target": "the guards", "power": "slumber", "means": "power"}]},
        "I cast sleep on the guards")
    assert frame["actions"][0]["means"] == "power"
    assert "power" not in frame["actions"][0]
    assert any("power='slumber'" in d for d in dropped)


def test_an_ordinary_deed_carries_no_means_key_and_an_old_reading_is_ordinary():
    frame, _ = interpret.ground(
        {"question": False, "claims": [], "actions": [
            {"span": "climb the wall", "act": "athletics", "place": "the wall",
             "means": "ordinary"}]}, "I climb the wall")
    assert "means" not in frame["actions"][0]
    assert means.judge(_frame({"act": "athletics", "span": "climb the wall"}),
                       _scene()) == []


# --- the sheet decides ------------------------------------------------------------------

def test_the_owners_memory_wipe_is_refused_for_a_rogue():
    s = _scene()
    refused = means.overreach(_frame(FORGET), s)
    assert [r["refused_name"] for r in refused] == ["make the smith forget he saw me"]
    assert means.all_refused(_frame(FORGET), refused)
    text = means.refusal_text(refused, s)
    assert "make the smith forget he saw me" in text
    assert "beyond what an ordinary person can do" in text
    # Validators name the fix, not the fault: the ordinary routes are named.
    assert "lying" in text and "the dice decide" in text


def test_the_refusal_lists_a_wizards_spells():
    """The engine's ability door printed "They can use: nothing yet." to the owner's
    wizard, who knows eight first-level spells."""
    s = _scene("fixtures/pc-caster.json")
    text = means.refusal_text(means.overreach(_frame(FORGET), s), s)
    assert "Sleep" in text and "Color Spray" in text


@pytest.mark.parametrize("deed,sheet,kind", [
    ({"act": "cast", "object": "sleep", "power": "sleep", "means": "power",
      "span": "cast sleep on the guards"}, "fixtures/pc-caster.json", "spell"),
    # Found in the deed's own words, the power never named as one.
    ({"act": "other", "means": "beyond", "span": "put the guard to sleep"},
     "fixtures/pc-caster.json", "spell"),
    ({"act": "use", "power": "Weapon Finesse", "means": "power",
      "span": "use Weapon Finesse"}, "fixtures/pc-kesst.json", "feat"),
])
def test_a_power_the_sheet_holds_stands(deed, sheet, kind):
    judged = means.judge(_frame(deed), _scene(sheet))
    assert judged and judged[0]["held"][0] == kind
    assert not means.overreach(_frame(deed), _scene(sheet))


def test_a_spell_named_that_the_book_does_not_hold_is_refused():
    deed = {"act": "cast", "object": "fireball", "power": "fireball", "means": "power",
            "span": "cast fireball at the bandits"}
    for sheet in ("fixtures/pc-kesst.json", "fixtures/pc-caster.json"):
        s = _scene(sheet)
        refused = means.overreach(_frame(deed), s)
        assert [r["refused_name"] for r in refused] == ["fireball"]
        assert "no spell, ability or item by that name" in means.refusal_text(refused, s)


def test_a_thing_carried_is_not_found_in_a_deeds_words():
    """"I turn the water into wine" names water the owner's wizard carries (fifteen of it)
    and is no power of the water. Only a power NAMED is held against what is carried."""
    s = _scene()
    s.pc().inventory = {"water": 3}
    deed = {"act": "other", "means": "beyond", "span": "turn the water into wine"}
    assert means.overreach(_frame(deed), s)
    named = {"act": "use", "means": "power", "power": "my ring",
             "span": "use my ring to vanish"}
    s.pc().slots = {"ring": ["ring of invisibility"]}
    assert not means.overreach(_frame(named), s)


def test_what_no_name_finds_is_asked_of_the_sheets_own_list():
    """The owner's asura flies on her own wings — "fly speed equal to base speed (wings)"
    is a line of her race — and no word of "I fly over the wall" is the trait's name. One
    enum question over the sheet's list answers it; what comes back can only be held."""
    s = _scene()
    asked = []

    def ask(scene, deed):
        asked.append(deed)
        return "trait", "fly speed equal to base speed (wings)"

    deed = {"act": "other", "means": "beyond", "span": "fly over the city wall"}
    judged = means.judge(_frame(deed), s, ask=ask)
    assert asked == ["fly over the city wall"]
    assert judged[0]["held"] == ["trait", "fly speed equal to base speed (wings)"]


def test_anybodys_deed_stands_but_a_named_power_never_is_anybodys():
    """On the regex gate's own 40 ordinary lines the reader called five `beyond` ("I bend
    the bars", "I charm her with a story", "I go with my gut" …); the question's ANYONE
    answer stands them. But "I drink my potion of flying" came back ANYONE too — anybody
    can drink — and a power named that the sheet does not hold is refused regardless."""
    s = _scene()

    def anyone(scene, deed):
        return means.ORDINARY, ""

    bars = {"act": "other", "means": "beyond", "span": "bend the bars"}
    assert means.judge(_frame(bars), s, ask=anyone) == []
    potion = {"act": "consume", "means": "power", "power": "my potion of flying",
              "span": "drink my potion of flying"}
    assert [r["refused_name"] for r in means.overreach(_frame(potion), s, ask=anyone)] \
        == ["my potion of flying"]


def test_the_question_offers_only_the_sheet_and_none(monkeypatch):
    s = _scene()
    seen = {}

    def chat(messages, model, host, **kw):
        seen["schema"] = kw["schema"]
        seen["last"] = messages[-1]["content"]
        return SimpleNamespace(text="", json=lambda: {"power": "none"})

    assert means.which_power(s, "turn invisible", chat=chat, model="m", host="h") == ("", "")
    enum = seen["schema"]["properties"]["power"]["enum"]
    assert enum[-2:] == [means.ANYONE, "none"] and "rapier" in enum and "stealthy" in enum
    # Spells are never offered: one standing behind a deed it does not do is the leak.
    w = _scene("fixtures/pc-caster.json")
    means.which_power(w, "turn invisible", chat=chat, model="m", host="h")
    assert "Sleep" not in seen["schema"]["properties"]["power"]["enum"]


def test_saying_so_is_not_doing_it():
    """Three of the corpus's first-pass misses had no deed at all, only a claim: "I know
    exactly where the bandit camp is", "I instantly learn to speak Draconic", "I decide
    that the smith owes me fifty gold"."""
    s = _scene()
    frame = _frame(claims=["I decide that the smith owes me fifty gold"])
    refused = means.overreach(frame, s)
    assert means.all_refused(frame, refused)
    assert "saying so does not make it so" in means.refusal_text(refused, s)


def test_a_bare_plan_is_not_a_declaration():
    """On the interpreter's 302 labelled real-play lines the reader wrote three claim-only
    frames, and two were plans: "I plan to rob the counting house tonight", "I mean to
    kill him if he comes back". Asked live (2026-10-06), the closed question sorted 12 of
    12 probe lines as written here: plans and the character's own state pass, facts
    declared into the world are refused."""
    s = _scene()
    plan = _frame(claims=["I plan to rob the counting house tonight."])
    assert means.overreach(plan, s, claim_ask=lambda c: means.INTENDS) == []
    assert means.overreach(_frame(claims=["I'm tired."]), s,
                           claim_ask=lambda c: means.SELF) == []
    fact = _frame(claims=["I know exactly where the bandit camp is"])
    assert means.overreach(fact, s, claim_ask=lambda c: means.DECLARES)
    # The question is an enum of the three, and a failed call refuses.
    seen = {}

    def chat(messages, model, host, **kw):
        seen["enum"] = kw["schema"]["properties"]["kind"]["enum"]
        raise RuntimeError("down")

    assert means.claim_kind("x", chat=chat, model="m", host="h") == means.DECLARES
    assert seen["enum"] == list(means.CLAIM_KINDS)


def test_a_result_declared_with_an_attempt_is_a_claim_not_a_refusal():
    frame = _frame({"act": "talk", "target": "the guard", "span": "lie to the guard"},
                   claims=["he believes every word"])
    assert means.overreach(frame, _scene()) == []


def test_only_deeds_done_or_tried_now_are_judged():
    deed = dict(FORGET, commit="intended")
    assert means.judge(_frame(deed), _scene()) == []


# --- the plan's guesses -----------------------------------------------------------------

def test_the_plans_guessed_spell_does_not_stand_behind_a_memory_wipe():
    """The live leak, exactly: the plan answered "I erase the apprentice's memory of me"
    with `cast charm-person`, and the regex door stood down for any cast."""
    s = _scene("fixtures/pc-caster.json")
    s.pc().spellbook = list(s.pc().spellbook) + ["charm-person"]
    frame = _frame(ERASE)
    judged = means.judge(frame, s)
    raw = [{"op": "cast", "actor": "pc", "target": "c1",
            "params": {"spell": "charm-person"}},
           {"op": "condition", "actor": "pc", "params": {"condition": "fascinated",
                                                          "to": "c1"}},
           {"op": "narrate_only", "because": "x"}]
    out = means.strike(raw, judged, frame, s)
    assert [r["op"] for r in out] == ["narrate_only", "use_ability"]
    assert out[-1]["params"]["ability"] == "erase the apprentice's memory of me"


def test_a_mixed_turn_keeps_its_ordinary_half():
    s = _scene()
    frame = _frame({"act": "attack", "target": "the smith", "span": "punch the smith"},
                   {"act": "look", "means": "beyond", "span": "read his mind"})
    raw = [{"op": "attack", "actor": "pc", "target": "c1"},
           {"op": "ability_damage", "actor": "pc", "target": "c1",
            "params": {"ability": "wis", "amount": "1d4"}}]
    out = means.strike(raw, means.judge(frame, s), frame, s)
    assert [r["op"] for r in out] == ["attack", "use_ability"]
    assert not means.all_refused(frame, means.overreach(frame, s))


def test_a_held_power_is_the_players_declaration():
    """Its refusal ("did not prepare Charm Person today") is the player's to hear; the
    owner's memory wipe reached the narrator because the plan's cast was dropped as an op
    nobody asked for (`GMAgent._players_refusal`)."""
    judged = [{"held": ["spell", "Sleep"]}, {"held": ["trait", "darkvision"]},
              {"refused_name": "x"}]
    assert means.backed_ops(judged) == ["cast"]


def test_the_engine_prints_the_refusal_it_is_asked_for():
    s = _scene()
    engine = Engine(s, Dice(seed=3))
    frame = _frame(FORGET)
    out = means.strike([{"op": "narrate_only", "because": "x"}], means.judge(frame, s),
                       frame, s)
    result = engine.run(engine.validate(out))
    tells = " ".join(o.tell for o in result.outcomes)
    assert "has no ability called make the smith forget he saw me" in tells


# --- the turn ----------------------------------------------------------------------------

class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "fake"

    def json(self):
        return json.loads(self.text)


def _agent():
    from gm import agent as agent_mod

    from _a_truth import VORMOOR, WORLD

    s = Scene(location_id=VORMOOR.id)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=5), world=WORLD)
    e.place_party()
    return agent_mod.GMAgent(WORLD, e), agent_mod


def test_a_turn_of_nothing_but_overreach_is_the_refusal_and_asks_no_model(monkeypatch):
    gm, agent_mod = _agent()
    calls = []
    monkeypatch.setattr(agent_mod.client, "chat",
                        lambda *a, **k: calls.append(1) or _Reply('{"intents": []}'))
    line = "I make the guard forget he saw me"
    interpret.remember(line, _frame(dict(FORGET, span="make the guard forget he saw me",
                                         target="the guard")))
    plan = gm.plan_turn(line, history=[])
    assert calls == []
    assert plan.refusal["code"] == "beyond_means"
    assert plan.narration == plan.refusal["text"]
    assert [i.op for i in plan.intents] == ["narrate_only"]
    assert gm.reading["means"][0]["refused_name"] == "make the guard forget he saw me"


def test_an_ordinary_lie_is_planned_as_ever(monkeypatch):
    """"I convince the guard I was never here" is a Bluff, and it reaches the planner."""
    gm, agent_mod = _agent()
    calls = []

    def chat(*a, **k):
        calls.append(1)
        return _Reply(json.dumps({"narration": "", "intents": [
            {"op": "narrate_only", "because": "talking"}]}))

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    line = "I convince the guard I was never here"
    interpret.remember(line, _frame({"act": "talk", "target": "the guard",
                                     "says": "I was never here",
                                     "span": "convince the guard I was never here"}))
    plan = gm.plan_turn(line, history=[])
    assert plan.refusal is None and calls


# --- the page -----------------------------------------------------------------------------

PAGE = ("You lock eyes with the apprentice and reach past them. The flicker of recognition "
        "of your presence simply dissolves. The smith grunts and goes back to his anvil. "
        "What do you do?")


def _page_ctx(monkeypatch, answer, outcomes=()):
    from gm import deed_reader
    from gm.checks import power_unbacked

    monkeypatch.setattr(deed_reader, "ENABLED", True)
    seen = []

    def chat(messages, *a, **k):
        seen.append((messages, k.get("schema")))
        return SimpleNamespace(text="", json=lambda: {"sentence": str(answer)})

    real = means.read_unbacked
    monkeypatch.setattr(means, "read_unbacked",
                        lambda *a, **k: real(*a, **{**k, "chat": chat}))
    ctx = SimpleNamespace(scene=_scene(), text=PAGE, outcomes=tuple(outcomes),
                          reader={"model": "stub", "host": "h"})
    return power_unbacked, ctx, seen


def test_a_power_on_the_page_no_tell_backs_is_found_and_replaced(monkeypatch):
    """The owner's turn's page, reduced: "The flicker of recognition … simply dissolves"."""
    check, ctx, seen = _page_ctx(monkeypatch, 1)
    found = check.find(ctx)
    assert [f.kind for f in found] == ["power-unbacked"]
    out, notes = check.backstop(ctx, PAGE, found)
    assert "reach past them" not in out and out.startswith(check.POOL[0])
    assert "The smith grunts" in out and notes
    assert check.authored_in(out) == [check.POOL[0]]
    # The question is closed: a sentence number from the page, or 0.
    assert seen[0][1]["properties"]["sentence"]["enum"][0] == "0"


def test_a_sentence_not_about_the_player_is_not_believed(monkeypatch):
    check, ctx, _ = _page_ctx(monkeypatch, 3)       # "The smith grunts…"
    assert check.find(ctx) == []


def test_the_reader_is_shown_what_the_rules_resolved_and_not_what_they_refused(monkeypatch):
    resolved = SimpleNamespace(op="cast", status="resolved", tell="You cast Sleep.")
    refused = SimpleNamespace(op="use_ability", status="refused",
                              tell="Kesst has no ability called telepathy.")
    check, ctx, seen = _page_ctx(monkeypatch, 0, outcomes=(resolved, refused))
    assert check.find(ctx) == []
    asked = seen[0][0][-1]["content"]
    assert "You cast Sleep." in asked and "telepathy" not in asked


# --- the corpus ---------------------------------------------------------------------------

def test_no_corpus_line_is_a_demonstration():
    """A demonstration in the corpus measures recall of the prompt, not reading."""
    from tests.means.gold import DEV, HELD_OUT

    demos = {d.lower().rstrip(".") for d, _f in interpret._DEMOS}
    demos |= {d.lower() for _h, d, _a in means._WHICH_DEMOS}
    for line, _sheet, _expect in DEV + HELD_OUT:
        assert line.lower().rstrip(".") not in demos, line


def test_the_corpus_has_the_size_the_doc_reports():
    from tests.means.gold import CLAIM, DEV, HELD_OUT, PASS, REFUSE

    def n(rows, e):
        return sum(1 for r in rows if r[2] == e)

    assert n(DEV, REFUSE) >= 80 and n(DEV, PASS) + n(DEV, CLAIM) >= 80
    assert n(HELD_OUT, REFUSE) >= 40 and n(HELD_OUT, PASS) + n(HELD_OUT, CLAIM) >= 40
