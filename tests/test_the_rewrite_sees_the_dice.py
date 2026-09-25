"""The polish rewrite is shown what the engine decided, and an NPC's turn does without it.

Measured 2026-09-25: `narrate_outcome` groomed with the polish rewrite on, and the NPC
loop calls it once per NPC per round — a ~10 s model call each, the price `npc_turn`'s
own comment says a fight cannot pay (and turns off for its own prose). And the rewrite
prompt carried the passage, the complaint, the player's words and a brief, but never
the tells: asked to fix a phrase, it could turn a miss into a hit, guarded only by 60% of
the action sentences surviving.
"""
from __future__ import annotations

from gm import prompts


def test_the_rewrite_prompt_carries_the_engines_decisions():
    msgs = prompts.narration_repair_messages(
        "The thug's blade bites deep.", "it names somebody who is not here",
        facts=["The thug's attack misses Kesst."])
    body = msgs[-1]["content"]
    assert "The thug's attack misses Kesst." in body
    assert "stays true" in body


def test_no_facts_no_section():
    body = prompts.narration_repair_messages("x", "y")[-1]["content"]
    assert "What the engine decided" not in body


def test_an_npc_turn_makes_one_model_call_whatever_the_review_finds(monkeypatch):
    from gm import agent as agent_mod
    from gm import client
    from rules.dice import Dice
    from rules.engine import Engine, Outcome, Scene
    from rules.sheet import load_pc

    class World:
        name, secret, premise, entities = "Testholme", "", {}, {}
        unwritten, chronology, factions = [], [], []

        def ancestors(self, _):
            return []

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    gm = agent_mod.GMAgent(World(), Engine(s, Dice(seed=1)))
    calls = []

    def chat(messages, model, *a, **kw):
        calls.append(model)
        # A beat the reviewer sends to the rewrite: the player named in third person.
        # Measured: with the rewrite on it costs THREE calls (prose, rewrite, retry).
        if len(calls) > 1:
            return client.Reply('{"narration": "The thug misses."}', 0.1, model)
        return client.Reply("Kesst ducks under the blow. Kesst laughs at the thug.",
                            0.1, model)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    out = [Outcome(intent_id="i1", op="attack", tell="The thug's attack misses Kesst.")]
    gm.narrate_outcome("", out, "the thug acts", rewrite=True)
    assert len(calls) > 1, "the beat must be one the rewrite is sent for"
    calls.clear()
    gm.narrate_outcome("", out, "the thug acts", rewrite=False)
    assert len(calls) == 1, f"{len(calls)} model calls for one NPC turn"
