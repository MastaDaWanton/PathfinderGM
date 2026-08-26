"""The event watcher, and the races it must lose gracefully.

The defect this file documents: the "watcher" model role was configured in
`settings.MODELS` from the day roles existed — deepseek-r1:8b, chosen on purpose, with
a settings-page card — and it had ZERO call sites. `settings.py` itself said "a model
that is never loaded and never called". Every campaign's undercurrent note was planted
once at creation and never moved again; every corpse carried exactly its spawn kit.

The watcher's contract, tested here rather than trusted:

* the model proposes, the engine disposes — only table-known item ids or an
  explicitly-typed trinket with a closed price band ever land, and a name from
  nowhere lands nothing;
* it works against a *snapshot*, and applies only if the world still matches it —
  the player looting first, or the note moving, silently wins;
* there is only ever ONE private note in history — rewritten in place, never
  appended twice;
* a watcher failure of any kind changes nothing at all, the same rule as the
  narrator fallbacks.

Everything runs the worker synchronously with a fake model; the daemon thread is only
a delivery mechanism and the wiring test pins that it exists.
"""
from __future__ import annotations

import inspect
import json

import pytest
from django.test import override_settings

from gm import watcher
from gm.client import ModelUnavailable
from play import campaign as cm, opening
from rules.bestiary import instantiate
from rules.sheet import load_pc


class _Reply:
    def __init__(self, data):
        self._data = data
        self.text = json.dumps(data)
        self.seconds = 0.1
        self.model = "fake-watcher"

    def json(self):
        return self._data


def _answer(monkeypatch, data):
    monkeypatch.setattr(watcher.client, "chat", lambda *a, **k: _Reply(data))


@pytest.fixture
def campaign(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        watcher._reset()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield c
        cm._LIVE.clear()
        watcher._reset()


def _fresh_kill(c):
    """A watchman who was alive when the watcher first looked, and is dead now —
    which is the only kind of corpse the watcher garnishes."""
    watcher._jobs_for(c)                     # first look: registers the campaign
    body = instantiate("watchman", scene=c.scene)
    c.scene.add(body, zone="near")
    body.hp = -2
    return body


def _turns(c, n):
    for _ in range(n):
        c.turn_log.append({"kind": "turn", "outcomes": []})


# --- the wiring: the role is actually called now --------------------------------------

def test_the_watcher_role_finally_has_call_sites():
    """The defect itself: `modelcfg.ROLES` shipped a configured "watcher" model with
    zero call sites — configured 2026-08, never once called. The worker must read the
    watcher role's own config, and the play loop must both kick it and drain it."""
    from play import views

    assert 'for_role("watcher")' in inspect.getsource(watcher._work)
    assert "watcher.kick" in inspect.getsource(views._finish)
    assert "watcher.drain" in inspect.getsource(views.say)
    assert "watcher.drain" in inspect.getsource(views.state)


def test_kick_never_blocks_the_turn():
    """The say/turn endpoints must never wait on deepseek. `kick` hands the model call
    to a daemon thread and returns; anything else would add the watcher's whole
    latency to every turn that kills something."""
    src = inspect.getsource(watcher.kick)
    assert "daemon=True" in src


# --- the corpse garnish ---------------------------------------------------------------

def test_a_garnish_lands_on_a_fresh_unlooted_corpse(campaign, monkeypatch):
    c = campaign
    body = _fresh_kill(c)
    _answer(monkeypatch, {"item": "a small brass locket", "band": "modest"})

    jobs = watcher._jobs_for(c)
    assert [j["job"] for j in jobs] == ["garnish"]
    watcher._work(jobs)
    assert watcher.drain(c) is True

    trinkets = [s for s in body.stock.values() if s.kind == "trinket"]
    assert len(trinkets) == 1
    assert trinkets[0].base == "a small brass locket"
    assert trinkets[0].tier == "uncommon"          # the "modest" band, priced by code
    assert c.turn_log[-1] == {"kind": "watcher", "did": "garnish",
                              "ref": body.ref, "item": trinkets[0].name}


def test_the_garnish_rides_out_with_the_loot(campaign, monkeypatch):
    """The point of putting it in `stock`: `_op_loot` already moves stock, so the
    locket needs no code of its own to reach the player's hands."""
    c = campaign
    body = _fresh_kill(c)
    _answer(monkeypatch, {"item": "a half-burned note", "band": "worthless"})
    watcher._work(watcher._jobs_for(c))
    watcher.drain(c)

    engine = c.engine()
    engine.run(engine.validate([{"op": "loot", "actor": "pc",
                                 "because": "the pockets",
                                 "params": {"from_": body.ref}}]))
    pc = c.scene.pc()
    assert any(s.kind == "trinket" and s.base == "a half-burned note"
               for s in pc.stock.values())
    assert not body.stock


def test_a_garnish_is_dropped_silently_when_the_player_looted_first(campaign,
                                                                    monkeypatch):
    """The race the whole design bends around: the proposal was made against a corpse
    with full pockets, and by the time the model answered the player had emptied them.
    One coin moved is enough — the snapshot must match wholesale."""
    c = campaign
    body = _fresh_kill(c)
    _answer(monkeypatch, {"item": "a small brass locket", "band": "modest"})
    watcher._work(watcher._jobs_for(c))
    assert watcher._PENDING                        # the proposal is in flight

    engine = c.engine()
    engine.run(engine.validate([{"op": "loot", "actor": "pc",
                                 "because": "got there first",
                                 "params": {"from_": body.ref}}]))
    assert watcher.drain(c) is False
    assert not body.stock                          # nothing appeared on the corpse
    assert not watcher._PENDING                    # and the proposal is spent, not queued


def test_a_garnish_is_dropped_when_the_scene_shed_the_corpse(campaign, monkeypatch):
    c = campaign
    body = _fresh_kill(c)
    _answer(monkeypatch, {"item": "an iron key", "band": "worthless"})
    watcher._work(watcher._jobs_for(c))
    del c.scene.actors[body.ref]
    assert watcher.drain(c) is False


def test_a_garnish_naming_a_stranger_is_refused(campaign, monkeypatch):
    """"Ground every name": a trinket is one small step from the model planting a
    person into the world — "Maribel's ledger" invents Maribel. The invented-name
    check runs on the item name with nothing sentence-initial to hide behind."""
    c = campaign
    _fresh_kill(c)
    _answer(monkeypatch, {"item": "a ledger signed by Maribel Osskart",
                          "band": "modest"})
    watcher._work(watcher._jobs_for(c))
    assert not watcher._PENDING


def test_a_garnish_with_a_price_outside_the_bands_is_refused(campaign, monkeypatch):
    """The band is a closed vocabulary, not a number the model writes. Hosted
    providers ignore the sampler schema entirely, so validation cannot lean on it."""
    c = campaign
    _fresh_kill(c)
    _answer(monkeypatch, {"item": "a jeweled crown", "band": "priceless"})
    watcher._work(watcher._jobs_for(c))
    assert not watcher._PENDING


def test_a_table_known_item_lands_as_its_real_catalogue_id(campaign, monkeypatch):
    """When the model names something the tables already price, the corpse gets the
    real id in `inventory` — not a duplicate trinket of a thing that exists."""
    from rules import ingredients as ing_mod

    iid, ing = next(iter(ing_mod.all_ingredients().items()))
    c = campaign
    body = _fresh_kill(c)
    _answer(monkeypatch, {"item": ing.name, "band": "worthless"})
    watcher._work(watcher._jobs_for(c))
    assert watcher.drain(c) is True
    assert body.inventory.get(iid) == 1
    assert not [s for s in body.stock.values() if s.kind == "trinket"]


def test_a_corpse_that_predates_the_watcher_is_not_fresh(campaign, monkeypatch):
    """A body already down when the watcher first sees a campaign — a resumed save —
    did not die on its watch, and does not sprout keepsakes days later."""
    c = campaign
    body = instantiate("watchman", scene=c.scene)
    c.scene.add(body, zone="near")
    body.hp = -2
    jobs = watcher._jobs_for(c)                    # first look sees it already dead
    assert jobs == []
    assert watcher._jobs_for(c) == []              # and it stays not-fresh


def test_one_garnish_per_corpse_ever(campaign, monkeypatch):
    c = campaign
    _fresh_kill(c)
    _answer(monkeypatch, {"item": "a wooden token", "band": "worthless"})
    watcher._work(watcher._jobs_for(c))
    watcher.drain(c)
    assert watcher._jobs_for(c) == []              # dead, garnished, done


# --- the living undercurrent ----------------------------------------------------------

SAFE_THREAD = ("The collector has arrived in town and is asking after the debt "
               "door by door.")


def test_the_note_is_rewritten_in_place_never_appended(campaign, monkeypatch):
    c = campaign
    notes = [m for m in c.history if m["content"].startswith(opening.NOTE_PREFIX)]
    assert len(notes) == 1                         # planted once at creation
    watcher._jobs_for(c)
    _turns(c, watcher.TURNS_BETWEEN_LOOKS)

    _answer(monkeypatch, {"action": "advance", "sentence": SAFE_THREAD})
    jobs = watcher._jobs_for(c)
    assert [j["job"] for j in jobs] == ["undercurrent"]
    watcher._work(jobs)
    assert watcher.drain(c) is True

    notes = [m for m in c.history if m["content"].startswith(opening.NOTE_PREFIX)]
    assert len(notes) == 1                         # exactly one, forever
    assert opening.note_thread(notes[0]["content"]) == SAFE_THREAD
    assert c.turn_log[-1]["kind"] == "watcher"


def test_keep_means_the_note_does_not_move(campaign, monkeypatch):
    c = campaign
    before = watcher._note_content(c)
    watcher._jobs_for(c)
    _turns(c, watcher.TURNS_BETWEEN_LOOKS)
    _answer(monkeypatch, {"action": "keep", "sentence": ""})
    watcher._work(watcher._jobs_for(c))
    assert not watcher._PENDING
    assert watcher._note_content(c) == before


def test_the_undercurrent_only_fires_every_n_turns(campaign, monkeypatch):
    c = campaign
    watcher._jobs_for(c)
    _turns(c, watcher.TURNS_BETWEEN_LOOKS - 1)
    assert watcher._jobs_for(c) == []
    _turns(c, 1)
    assert [j["job"] for j in watcher._jobs_for(c)] == ["undercurrent"]


def test_a_thread_naming_an_unknown_entity_is_refused(campaign, monkeypatch):
    c = campaign
    watcher._jobs_for(c)
    _turns(c, watcher.TURNS_BETWEEN_LOOKS)
    _answer(monkeypatch, {"action": "new", "sentence":
                          "Lord Vexmoor has bought every warehouse on the docks."})
    watcher._work(watcher._jobs_for(c))
    assert not watcher._PENDING


def test_a_rambling_thread_is_refused(campaign, monkeypatch):
    """One sentence is the budget. Two sentences, or a paragraph, is the model
    narrating — the note is a private nudge, not a chapter."""
    c = campaign
    watcher._jobs_for(c)
    _turns(c, watcher.TURNS_BETWEEN_LOOKS)
    _answer(monkeypatch, {"action": "advance", "sentence":
                          "The debt is due. The collector knows where you sleep."})
    watcher._work(watcher._jobs_for(c))
    assert not watcher._PENDING


def test_a_stale_note_proposal_is_dropped(campaign, monkeypatch):
    """A campaign save can land — or the note can move — while the model is still
    thinking. The proposal remembers what it read, and applies only over that."""
    c = campaign
    watcher._jobs_for(c)
    _turns(c, watcher.TURNS_BETWEEN_LOOKS)
    _answer(monkeypatch, {"action": "advance", "sentence": SAFE_THREAD})
    watcher._work(watcher._jobs_for(c))

    i = watcher._find_note(c.history)
    c.history[i] = {"role": "user",
                    "content": opening.private_note("Something else entirely moved.")}
    moved = c.history[i]["content"]
    assert watcher.drain(c) is False
    assert c.history[i]["content"] == moved        # untouched


# --- failure is silence ---------------------------------------------------------------

def test_a_dead_model_changes_nothing(campaign, monkeypatch):
    """Ollama down, deepseek missing, a timeout: the watcher is garnish on a game
    that works without it, and a failed call must cost the game nothing at all."""
    c = campaign
    body = _fresh_kill(c)
    _turns(c, watcher.TURNS_BETWEEN_LOOKS)

    def _down(*a, **k):
        raise ModelUnavailable("nobody home")

    monkeypatch.setattr(watcher.client, "chat", _down)
    before = (json.dumps(c.history), dict(body.inventory), sorted(body.stock))
    watcher._work(watcher._jobs_for(c))            # must not raise
    assert not watcher._PENDING
    assert watcher.drain(c) is False
    assert (json.dumps(c.history), dict(body.inventory), sorted(body.stock)) == before


def test_junk_json_changes_nothing(campaign, monkeypatch):
    c = campaign
    _fresh_kill(c)
    _answer(monkeypatch, {"unexpected": "shape"})
    watcher._work(watcher._jobs_for(c))
    assert not watcher._PENDING
