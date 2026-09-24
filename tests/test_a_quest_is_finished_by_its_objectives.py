"""A quest is finished by doing its objectives, and by nothing else.

Reported 2026-09-23 with the quest log on screen, one turn after taking the quest on:

    Find Drenn Ironvale's lost Power leaf — finished
      • Search the approach for the Power leaf
      • Bring the Power leaf back to Drenn Ironvale
    Find Drenn Ironvale's lost Power leaf is already a quest on the table. · Spree says:
    "I will find your power leaf."

    "1st the quest displays as finish but has not given Exp. 2nd the quest has only
    just begun I have only accepted the quest and started on my way."

Read off the save: stage "resolved", clock 2 of 2, both objectives `done: false`, and
the card's first FACT was the engine's own refusal of a duplicate `quest` op. The card
had been opened by the `the-lost-thing` scheme with Drenn Ironvale as its giver, and
`touch_from_outcomes` ticks a card's clock whenever a tell names one of its people —
right for a situation card, and wrong for a quest, whose clock is its objective count.
Two tells naming Drenn finished it. No award was paid because `_op_quest_step`, the
one thing that pays, never ran: the "finished" was a side effect, not a completion.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from rules import cards
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene


@dataclass
class Out:
    tell: str = ""
    effects: list = field(default_factory=lambda: [{"kind": "something"}])
    status: str = "resolved"


def _scene():
    s = Scene(location_id="t")
    pc = instantiate("guildhand", scene=s, name="Spree")
    pc.kind = "pc"
    s.add(pc)
    drenn = instantiate("guildhand", scene=s, name="Drenn Ironvale")
    s.add(drenn)
    return s, pc, drenn


def _quest(s, drenn):
    return cards.open_quest(
        s, title="Find Drenn Ironvale's lost Power leaf",
        objectives=["Search the approach for the Power leaf",
                    "Bring the Power leaf back to Drenn Ironvale"],
        giver=drenn.ref, people=[drenn.ref], origin="scheme:the-lost-thing", turn=0)


class TestTellsDoNotFinishAQuest:
    def test_two_tells_naming_the_giver_leave_it_live_with_nothing_done(self):
        s, pc, drenn = _scene()
        card = _quest(s, drenn)
        cards.touch_from_outcomes(s, [Out("Drenn Ironvale looks away when asked.")], turn=8)
        cards.touch_from_outcomes(s, [Out("Drenn Ironvale speaks, to the effect that "
                                          "the man is a smuggler of sorts.")], turn=10)
        got = cards.find(s, card.id)
        assert got.live
        assert got.clock == 0
        assert not any(o["done"] for o in got.objectives)
        # It IS moving — the tells are about it — and that is all they do.
        assert got.stage == "moving"

    def test_a_refusal_is_not_a_fact_about_anything(self):
        """`Engine._refuse` is no effects and a tell. The reported card's first fact was
        the refusal of a duplicate quest op, and so was the scheme's secret card's."""
        s, pc, drenn = _scene()
        card = _quest(s, drenn)
        touched = cards.touch_from_outcomes(
            s, [Out("Find Drenn Ironvale's lost Power leaf is already a quest on the "
                    "table.", effects=[], status="refused")], turn=8)
        assert touched == []
        assert "already a quest" not in " ".join(cards.find(s, card.id).facts)

    def test_the_engines_own_refusal_carries_the_status(self):
        """The real thing, not the double: a duplicate `quest` op through the engine."""
        s, pc, drenn = _scene()
        e = Engine(s, Dice(seed=1), world=None)
        card = _quest(s, drenn)
        raw = {"op": "quest", "actor": pc.ref, "because": "t",
               "params": {"title": card.title, "objectives": ["Find it"], "giver": drenn.ref}}
        out = e.run(e.validate([raw], origin="author:test")).outcomes[-1]
        assert out.status == "refused" and "already a quest" in out.tell
        cards.touch_from_outcomes(s, [out], turn=8)
        got = cards.find(s, card.id)
        assert got.clock == 0 and "already a quest" not in " ".join(got.facts)

    def test_a_situation_card_still_ticks_on_a_tell(self):
        """The rule this narrows is right for what it was written for."""
        s, pc, drenn = _scene()
        cards.open_card(s, cards.Card(id="jar", title="Drenn's jar", people=[drenn.ref],
                                      clock_max=2, origin="author:test"), turn=1)
        cards.touch_from_outcomes(s, [Out("Drenn Ironvale takes the jar.")], turn=2)
        assert cards.find(s, "jar").clock == 1


class TestObjectivesFinishItAndPay:
    def _step(self, e, pc, card, n):
        raw = {"op": "quest_step", "actor": pc.ref, "because": "t",
               "params": {"quest": card.id, "objective": n}}
        return e.run(e.validate([raw], origin="author:test")).outcomes[-1]

    def test_the_last_objective_finishes_it_and_the_award_is_paid(self):
        s, pc, drenn = _scene()
        e = Engine(s, Dice(seed=1), world=None)
        card = _quest(s, drenn)
        xp = int(getattr(pc, "xp", 0) or 0)
        one = self._step(e, pc, card, 1)
        assert not one.effects[0]["finished"]
        assert cards.find(s, card.id).live
        two = self._step(e, pc, card, 2)
        assert two.effects[0]["finished"]
        assert "is finished" in two.tell
        assert not cards.find(s, card.id).live
        assert int(getattr(pc, "xp", 0) or 0) > xp, two.tell
