"""A fight opened by a spoken blow and struck from the panel: whose turn comes next.

Measured on the owner's report of 2026-11-01 (Corvin T., the marsh, log rows 314, 315 and
320): the player typed "run at lila duskwatch and punch her twice", the battle gate opened
the fight, the player struck from the combat panel — and Lila Duskwatch then took two turns
before the player's second swing.

Traced on the report's own server log (pathfindergm.log, 7186-7279): the strike's three
rolls ended with Lila's first turn (row 315), the order came back to the player, and then a
SECOND `/api/combat/act` arrived with no player line in the transcript — an empty turn
post, which is what "End turn", and "Commit turn" with nothing staged, both sent — and that
call's `_run_npc_turns` gave Lila row 320. So the engine's order was right (the repro below
holds it to one turn a cycle, whoever wins initiative, with Lila disabled or not); the
panel let the player's fresh turn be passed without a word. Commit turn with nothing
planned no longer posts, and a pass for a round the page had not yet drawn is refused.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules.sheet import load_pc
from tests._board import face_to_face


def _open(tmp_path, seed, gap=10):
    from play import campaign as cm
    from rules.bestiary import instantiate

    c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
    c.seed = seed
    for ref in [r for r in c.scene.actors if r != "pc"]:
        c.scene.depart(ref)
    lila = instantiate("farmer", scene=c.scene, name="Lila Duskwatch")
    lila.ref = "c1"
    c.scene.add(lila)
    face_to_face(c.scene)
    if gap:
        # Ten feet off, as on the report ("Corvin T. closes 10 ft on Lila Duskwatch to
        # strike"): out of reach, so the opening blow waits for the panel.
        x, y = c.scene.positions["pc"][:2]
        c.scene.positions["c1"] = (x + 1 + gap // 5, y) + tuple(c.scene.positions["pc"][2:3])
        c.scene.resync_zones()
    e = c.engine()
    # The spoken turn's blow: the battle gate opens the fight and defers the swing.
    out = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                             "params": {}}]))
    if not any(ef.get("kind") == "battle_joined" for o in out.outcomes
               for ef in o.effects or []):
        pytest.skip("this seed's board did not open the fight from ten feet")
    assert not c.scene.awaiting, "out of reach, the opening blow waits for the panel"
    c.save()
    return cm, c


def _answer_rolls(client, cm, hit=2):
    guard = 0
    while cm.current().scene.awaiting and guard < 12:
        prompt = cm.current().scene.awaiting
        face = hit if str(prompt.get("label", "")).startswith(("Attack", "Confirm")) else 1
        client.post("/api/roll", data=json.dumps({"face": min(face, int(prompt.get("max", 20)))}),
                    content_type="application/json")
        guard += 1


def _turns(c, before):
    # One row per turn that acted (an offline model logs its error row AND the fallback's
    # row for the same turn: only the one with outcomes is a turn).
    return [t for t in c.turn_log[before:] if t.get("kind") == "npc-turn"
            and t.get("ref") == "c1" and t.get("outcomes") is not None]


def _strike(client):
    return client.post("/api/combat/act",
                       data=json.dumps({"actions": [{"op": "attack", "target": "c1",
                                                     "params": {}}],
                                        "label": "strike Lila", "end_turn": True}),
                       content_type="application/json")


@pytest.mark.parametrize("hit", [2, 17])
@pytest.mark.parametrize("seed", range(4))
def test_the_foe_takes_one_turn_between_the_players_panel_blows(tmp_path, seed, hit):
    """One creature, one turn, between the player's opening strike at the panel and their
    next — whoever won initiative, with Lila struck to exactly 0 (disabled) or not."""
    from play import campaign as cm_mod

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm_mod._LIVE.clear()
        cm, c = _open(tmp_path, 1000 + seed)
        if hit > 2:
            c.scene.actors["c1"].hp = 1
            c.save()
        client = Client()
        before = len(c.turn_log)
        r = _strike(client)
        assert r.status_code == 200, r.content[:300]
        _answer_rolls(client, cm, hit)
        c = cm.current()
        turns = _turns(c, before)
        order = list(c.scene.initiative)
        refs = [ref for ref, _ in order]
        cm_mod._LIVE.clear()
    assert len(refs) == len(set(refs)), order
    assert len(turns) <= 1, (order, [t.get("outcomes") for t in turns])


def test_a_pass_for_a_round_the_page_had_not_drawn_is_refused(tmp_path):
    """The second post on the report: an empty turn after the round had moved on. With the
    round the page drew (`seen_round`), a stale pass is refused and Lila does not act."""
    from play import campaign as cm_mod

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm_mod._LIVE.clear()
        cm, c = _open(tmp_path, 1001)
        drawn = c.scene.round
        client = Client()
        _strike(client)
        _answer_rolls(client, cm)
        c = cm.current()
        if not c.scene.in_encounter or c.scene.round == drawn:
            cm_mod._LIVE.clear()
            pytest.skip("the fight ended or the round did not move")
        before = len(c.turn_log)
        r = client.post("/api/combat/act",
                        data=json.dumps({"actions": [], "end_turn": True, "label": "",
                                         "seen_round": drawn}),
                        content_type="application/json")
        assert r.status_code == 409, r.content[:300]
        assert "already ended" in r.json()["error"]
        assert _turns(cm.current(), before) == []
        # The same pass from a page that drew the round it is passing goes through.
        r = client.post("/api/combat/act",
                        data=json.dumps({"actions": [], "end_turn": True, "label": "",
                                         "seen_round": cm.current().scene.round}),
                        content_type="application/json")
        assert r.status_code == 200
        cm_mod._LIVE.clear()


def test_commit_turn_with_nothing_planned_does_not_pass_the_turn():
    """The page half: Commit turn with nothing staged says so and posts nothing; passing
    is End turn's, and every commit carries the round it was drawn in."""
    from pagesource import table_source

    src = table_source()
    assert "if (!endOnly && !actions.length)" in src
    assert "Nothing is planned for this turn" in src
    assert "seen_round:" in src
