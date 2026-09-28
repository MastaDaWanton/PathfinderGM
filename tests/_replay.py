"""Replaying a recorded turn's plan through the real `plan_turn`, without a model.

`tools/narrator_audit.py --record` keeps, for each turn, the save as it stood before it
and every model call's raw reply in the order asked. Handing those replies back in order
to a stand-in for `gm.client.chat` runs the whole planning path — the reading, the
injectors, validation and every repair — on exactly what the model wrote.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

PLANS = Path(__file__).resolve().parent / "replay" / "plans"


def recorded(name: str) -> list[dict]:
    with gzip.open(PLANS / name, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def replay_plan(rec, tmp_path, monkeypatch):
    """`plan_turn` on the save as it stood before the turn, the model's recorded replies
    returned in the order they were asked for. One plan attempt: the turn must stand on
    the model's first reply, and the reading's and that one are all that is consumed."""
    from django.test import override_settings

    from gm import client as gm_client
    from gm import interpret
    from gm.agent import GMAgent
    from play import campaign as cm

    # The recorded turn read the sentence first (the conftest switches the reading off),
    # and its reply is the first one recorded: on, so each reply meets its own call.
    # Off, the reading's reply was handed to the planner and the replay of the "new"
    # thug passed on the unfixed code (2026-09-27).
    monkeypatch.setattr(interpret, "ENABLED", True)
    replies = [c["raw"] for c in rec["calls"]]

    class Reply:
        def __init__(self, text):
            self.text, self.seconds, self.model = text, 0.0, rec["model"]
            self.prompt_tokens = self.reply_tokens = 0
            self.done_reason = "stop"

        def json(self):
            return json.loads(self.text)

    def chat(*a, **k):
        return Reply(replies.pop(0))

    monkeypatch.setattr(gm_client, "chat", chat)
    with override_settings(CAMPAIGN_DIR=str(tmp_path)):
        p = tmp_path / f"{rec['save_before']['id']}.json"
        p.write_text(json.dumps(rec["save_before"]), encoding="utf-8")
        c = cm.Campaign.load(p)
        agent = GMAgent(c.world, c.engine())
        plan = agent.plan_turn(rec["player"], history=[], max_attempts=1)
    assert len(replies) == len(rec["calls"]) - 2, "the reading and the plan, no more"
    return plan, agent.engine.scene
