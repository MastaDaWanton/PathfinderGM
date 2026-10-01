"""A spell the turn did not cast keeps its chip, with the engine's reason (deferred row).

The register's row (2026-09-30): "a spell refused mid-turn is spent". `play/views.py`
`_dry_cast` answers before any model call what only the player can fix; but a cast the
engine does not make while the turn RUNS — a slot gone to an earlier cast in the same
list, a first harmful cast that opens a fight and is "still to be spoken"
(`Engine._cast_gate`) — answered 200, and the page (04-combat-and-turns.js `takeTurn`)
cleared the chip as though the spell had gone. The words ran, so they are not put back;
the chip is, under the same `unfinished` field an unfinished move uses, with the reason.
"""
from __future__ import annotations

from django.http import JsonResponse

from play import views

from test_e_magic_attach import _say, table  # noqa: F401 — the fixture

CHIP = {"kind": "spell", "id": "burning-hands", "name": "Burning Hands"}


class _C:
    def __init__(self, outcomes):
        self.ended = False
        self.scene = type("S", (), {"awaiting": None})()
        self.turn_log = [{"kind": "turn", "outcomes": outcomes}, {"kind": "prose"}]


def _kept(outcomes):
    resp = views._keep_the_spell(_C(outcomes), (CHIP,), JsonResponse({"ok": True}))
    import json

    return json.loads(resp.content).get("unfinished")


def test_a_cast_refused_mid_list_keeps_the_chip_with_the_engines_sentence():
    tell = ("Ysolde has no spell slot 1 left, so Burning Hands is not cast. What was cast "
            "before it stands.")
    got = _kept([{"op": "cast", "status": "refused", "tell": tell, "effects": []}])
    assert got == {"text": "", "keep_chip": True, "why": tell,
                   "line": "Burning Hands was not cast; it is still attached."}


def test_a_plan_that_never_cast_it_keeps_the_chip():
    assert _kept([{"op": "narrate_only", "status": "resolved", "tell": ""}])["keep_chip"]


def test_a_cast_that_happened_spends_the_chip():
    assert _kept([{"op": "cast", "status": "resolved", "tell": "Burning Hands…",
                   "effects": [{"kind": "damage"}]}]) is None


def test_the_fight_a_harmful_cast_opens_keeps_the_chip_for_the_first_turn(table):
    """Through the real `/api/say`: Burning Hands at the man in the jerkin opens the
    fight and casts nothing yet ("still to be spoken"); the chip stays for the player's
    first combat turn, and the response says so."""
    c, man = table["begin"]({"burning-hands": 1})
    r = _say({"text": "I cast burning hands at the man in the stained jerkin",
              "attachments": [dict(CHIP, aim=f"ref:{man}")]})
    assert r.status_code == 200, r.content[:300]
    body = r.json()
    turn = next(e for e in reversed(c.turn_log) if e.get("kind") == "turn")
    casts = [o for o in turn["outcomes"] if o["op"] == "cast"]
    assert any(e.get("kind") == "battle_joined" for o in casts for e in o["effects"]), casts
    assert c.scene.in_encounter
    assert body["unfinished"]["keep_chip"] is True and body["unfinished"]["text"] == ""
    assert "still to be spoken" in body["unfinished"]["why"]
    assert c.scene.pc().prepared.get("burning-hands") == 1, "nothing was spent"
