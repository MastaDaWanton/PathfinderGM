"""The narrator copying its own demonstrations, and why the echo index let it ship.

Measured 2026-10-16 on the fight audit (gemma-4-12B, free narrator, master c916a61f): two
beats in eleven opened "You break contact and the window is four running steps away,
shutters open on a drop you have not measured" — COMBAT_EXAMPLES[4] — while the player
was punching a man forty feet away. The echo index HAD caught the first (59 shared
phrases, `echoes-the-examples`). Three things let it through:

  * the whole-beat rewrite removed all 59 and was refused, because `polish` demands a
    rewrite keep 0.6 of the draft's events — and the draft's events were the example's
    window and the example's chase (`actions_kept` 0.0);
  * in a fight there is no second rewrite, and the echo had no backstop, so the copied
    passage shipped whole;
  * and the index was a hand-kept list in `GMAgent._echo_index` that never held the
    creature-turn consequence example, the repair examples, the companion answers, the
    interjections, the confidences or the owner's intimate passages.

Across every scratchpad save, 5 of 5 caught copies of three runs or more shipped.
"""
from __future__ import annotations

import json
import re

from gm import agent as agent_mod
from gm import checks, narration, prompts
from gm.checks import copied_example

from _a_truth import MARKET, context, scene_at

WINDOW = prompts.COMBAT_EXAMPLES[4]["reply"]["narration"]


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def test_every_example_block_in_prompts_is_a_demonstration_the_echo_index_holds():
    """The index was a hand-kept list and missed every set it did not name: COMBAT and
    CARRY_ON joined only after lane C3's night fight (2026-10-07); CONSEQUENCE_NPC,
    ACTOR_REPAIR, MANNER_REPAIR, NARRATION_REPAIR, COMPANION_ANSWER, INTERJECT and CONFIDE
    never did. Every `*EXAMPLE*` constant in gm/prompts is now named in
    `prompts.demonstrations`, so a new set cannot be shown to a narrator unindexed."""
    blocks = {n for n in vars(prompts) if re.fullmatch(r"[A-Z_]*EXAMPLES?", n)}
    listed = {name.split("[")[0] for name, _ in prompts.demonstrations()}
    assert blocks - listed == set(), (
        f"example blocks shown to a model but not in prompts.demonstrations: "
        f"{sorted(blocks - listed)} — add their replies there")


def test_each_demonstration_copied_back_with_the_real_enemy_is_caught():
    """The index was filled with "stranger" where the narrator is shown the real enemy
    ("the figure"), so a window across the slot never matched. It now splits at each
    placeholder, and every demonstration's own sentences come back as copies."""
    index = narration.demonstration_index()
    for name, passage in prompts.demonstrations():
        filled = prompts.fill_enemy(passage, "the figure")
        filled = re.sub(r"\{[^{}]*\}", "Mira", filled)
        long = [s for s in re.split(r"(?<=[.!?])\s+", narration.speech.lift(filled)[0])
                if len(narration._ngrams(s)) >= narration.COPIED_RUNS + 2
                and not re.search(r"\{|Mira|the figure", s)]
        if not long:
            continue
        assert narration.copied_sentences(" ".join(long), index), name


def test_stock_english_sharing_a_run_or_two_is_not_a_copy():
    """The threshold, measured over 5,910 recorded beats: every sentence sharing one or
    two six-word runs with a demonstration was stock English (these, from the corpus);
    every one sharing three or more was lifted."""
    for line in ("He does not look up from the inventory he is conducting, his hands "
                 "moving with practiced, heavy motions.",
                 "What is the first thing you do?",
                 "You wouldn't happen to have any news on that, would you? What do you do?",
                 "You are still here, on the ground, with the beast still watching."):
        assert narration.copied_sentences(line) == [], line
    assert narration.copied_sentences(
        "He is faster over the open floor than he was in the press.")


def test_the_owners_intimate_passages_are_held_to_as_well():
    """The owner's passages are shown in place of the examples in an intimate beat, read
    fresh from their file each beat — so they join the index for that beat only."""
    passage = ("She draws the curtain across the window and the lamp throws her shadow "
               "huge against the plaster wall behind the bed.")
    from types import SimpleNamespace

    from gm.agent import GMAgent
    from gm.intimate import Demonstrations

    assert narration.copied_sentences(passage) == []
    beat = SimpleNamespace(intimate=SimpleNamespace(demonstrations=Demonstrations(
        examples=[{"player": "> I close the door.", "reply": {"narration": passage}}])))
    assert narration.copied_sentences(passage, GMAgent._echo_index(beat))
    assert GMAgent._shown_passages(beat) == (passage,)


def test_a_rewrite_of_a_wholly_copied_draft_is_not_refused_for_losing_its_events(monkeypatch):
    """The audit's beat: COMBAT_EXAMPLES[4] word for word, caught with 59 phrases, and the
    rewrite that removed every one refused because it kept 0.0 of the example's "events".
    The draft's events are now read without its copied sentences."""
    agent, _ = scene_at(MARKET)
    rewrite = ("You lunge for him and he twists aside, the market's awnings flapping "
               "overhead as the crowd scatters back from the two of you. He keeps his "
               "distance, watching your hands, breathing hard. What do you do?")
    monkeypatch.setattr(agent_mod.client, "chat",
                        lambda *a, **k: _Reply(json.dumps({"narration": rewrite})))
    out, notes, _ = agent.polish(WINDOW)
    assert out == rewrite, notes
    assert narration.actions_kept(WINDOW, rewrite) == 0.0   # the gate that refused it


def test_the_check_flags_each_copied_sentence_at_every_door():
    agent, _ = scene_at(MARKET)
    text = "You turn on him. " + prompts.fill_enemy(WINDOW, "the figure")
    for door in ("plan", "turn", "npc", "outcome"):
        found = copied_example.find(context(agent, text, door=door))
        assert len(found) == 1 and found[0].kind == "copies-an-example"
        assert len(found[0].sentences) == 3
        assert "You turn on him." not in found[0].sentences
        assert "four running steps" in found[0].fix_hint


def test_a_copy_the_rewrite_cannot_shake_is_cut_and_one_it_can_is_kept(monkeypatch):
    """Through the registered repair (`_repair_sentences`): one targeted rewrite per
    copied sentence, kept only if it no longer copies; the backstop cuts what still
    does. Before this, in a fight, the copied passage shipped whole."""
    agent, _ = scene_at(MARKET)
    text = ("You turn on him. You break contact and the window is four running steps "
            "away, shutters open on a drop you have not measured. What do you do?")
    ctx = context(agent, text)
    found = [f for f in checks.run(ctx) if f.kind == "copies-an-example"]
    assert found
    replies = iter([
        # Still copying: refused, and the backstop cuts the sentence.
        "You break contact and the window is four running steps away, its shutters wide.",
    ])
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply(
        json.dumps({"sentence": next(replies, "")})))
    out, notes, _ = agent._repair_sentences(text, found, ctx)
    assert "four running steps" not in out
    assert out.startswith("You turn on him.")
    assert any("copied from a worked example: cut 1" in n for n in notes)

    ctx = context(agent, text)
    found = [f for f in checks.run(ctx) if f.kind == "copies-an-example"]
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply(json.dumps(
        {"sentence": "You step back from him, and the stalls crowd in on both sides."})))
    out, notes, _ = agent._repair_sentences(text, found, ctx)
    assert out == ("You turn on him. You step back from him, and the stalls crowd in on "
                   "both sides. What do you do?"), notes


def test_a_beat_that_was_nothing_but_the_example_is_cut_to_nothing():
    """The view's empty-turn floor then writes the engine's own lines (`play.views`),
    which are true; the example's window and cart were not."""
    agent, _ = scene_at(MARKET)
    text = WINDOW.replace(" Do you go?", "")
    ctx = context(agent, text)
    out, notes = copied_example.backstop(ctx, text, copied_example.find(ctx))
    assert out == "" and notes


def test_a_companion_remark_copied_from_its_example_is_refused():
    """The interjection and confide calls are shown their own examples and never pass
    through the beat's checks; their retry loops now refuse a copied line."""
    agent, _ = scene_at(MARKET)
    copied = json.loads(prompts.INTERJECT_EXAMPLES[1]["assistant"])["line"]
    assert "copies a worked example" in agent._copy_refusal(copied)
    assert agent._copy_refusal("Mara grins. \"Well, that went better than the last "
                               "time.\"") == ""
