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


def test_the_watcher_and_the_loot_op_mean_the_same_thing_by_down():
    """`_down`'s docstring called itself "the loot op's own test" and was not: the loot
    op asks `hp <= 0 or state.down`, and this asked `hp <= 0 or has_condition
    ("unconscious")` — one literal key against a family of six.

    Measured at positive hit points, they disagreed on five of the six: dead, dying,
    helpless, petrified and stable. A creature killed by Constitution damage is written
    `dead` with its hit points untouched, so the watcher never offered it for looting
    while the loot op would have stripped it happily.
    """
    from rules.sheet import from_dict

    def body(**kw):
        a = from_dict({"name": "the watchman", "kind": "npc", "hp": 20, "hp_max": 20,
                       "abilities": {k: 12 for k in ("str", "dex", "con",
                                                     "int", "wis", "cha")}}, ref="c1")
        for key in kw.get("conditions", ()):
            a.add_condition(key, source="probe")
        a.hp = kw.get("hp", 20)
        return a

    for key in ("dead", "dying", "unconscious", "stable", "petrified", "helpless"):
        a = body(conditions=[key])
        assert watcher._down(a), f"{key} at full hit points was not down to the watcher"
        # The loot op's actual test, quoted rather than trusted.
        assert a.hp <= 0 or a.has_state("state.down")

    assert not watcher._down(body()), "an unhurt creature must not be lootable"
    assert watcher._down(body(hp=-2)), "hit points alone still answer"


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
    c.scene.remove(body.ref)
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
    # The cards job has its own, shorter cadence; only the undercurrent is at issue.
    assert [j for j in watcher._jobs_for(c) if j["job"] == "undercurrent"] == []
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


# --- the situation cards move at the pace of a conversation ------------------------------

def _cards_ready(c):
    """Past the first look, with a live card that has a person on it."""
    from rules import cards
    watcher._jobs_for(c)
    woman = instantiate("guildhand", scene=c.scene, name="the woman at the stall")
    c.scene.add(woman, zone="near")
    cards.open_card(c.scene, cards.Card(id="jar", title="The woman's jar to seal",
                                        facts=["She asked you to seal a jar for her."],
                                        people=[woman.ref], clock_max=2,
                                        origin="author:test"), turn=1)
    c.transcript.append({"who": "player", "text": "I seal the jar with wax and hand it back, and ask her for a day's work."})
    c.transcript.append({"who": "gm", "text": "The woman at the stall takes the sealed jar and nods."})
    _turns(c, watcher.CARD_TURNS_BETWEEN_LOOKS)
    return woman


def test_a_talking_turn_moves_a_card_through_the_watcher(campaign, monkeypatch):
    """A talking turn makes no tell, so nothing put "she has the sealed jar" on the
    woman's card — the drift the player named. The watcher reads the last beats
    against the live cards and proposes one fact; validated, it lands and ticks."""
    from rules import cards
    c = campaign
    _cards_ready(c)
    _answer(monkeypatch, {"changes": [{"id": "jar", "action": "advance",
                                       "fact": "She has the sealed jar now."}],
                          "new": None})
    jobs = watcher._jobs_for(c)
    assert [j["job"] for j in jobs] == ["cards"]
    watcher._work(jobs)
    assert watcher.drain(c) is True
    jar = cards.find(c.scene, "jar")
    assert jar.stage == "moving" and jar.clock == 1
    assert jar.facts[-1] == "She has the sealed jar now."
    assert c.turn_log[-1] == {"kind": "watcher", "did": "card", "card": "jar",
                              "action": "advance", "fact": "She has the sealed jar now."}


def test_resolving_a_card_settles_it_and_pays_the_story_share(campaign, monkeypatch):
    from rules import cards
    c = campaign
    _cards_ready(c)
    before = c.scene.pc().xp
    _answer(monkeypatch, {"changes": [{"id": "jar", "action": "resolve", "fact": ""}],
                          "new": None})
    watcher._work(watcher._jobs_for(c))
    assert watcher.drain(c) is True
    assert cards.find(c.scene, "jar").stage == "resolved"
    assert c.scene.pc().xp - before == 200          # half a CR 1 fight, at level 1
    assert "You gain 200 XP" in c.transcript[-1]["text"]
    assert "jar" in c.transcript[-1]["text"]


def test_a_fact_that_names_a_stranger_or_carries_a_number_never_lands(campaign, monkeypatch):
    from rules import cards
    c = campaign
    _cards_ready(c)
    _answer(monkeypatch, {"changes": [
        {"id": "jar", "action": "advance", "fact": "The potter Grimble wants the jar too."},
        {"id": "jar", "action": "advance", "fact": "She will pay 12 silver for it."},
        {"id": "nope", "action": "resolve", "fact": ""}],
        "new": {"title": "Kaida's debt", "facts": ["Kaida owes the stall."], "people": ["c1"]}})
    watcher._work(watcher._jobs_for(c))
    assert not watcher._PENDING
    assert cards.find(c.scene, "jar").clock == 0


def test_a_new_card_arises_from_play_with_its_people_by_ref(campaign, monkeypatch):
    from rules import cards
    c = campaign
    woman = _cards_ready(c)
    _answer(monkeypatch, {"changes": [{"id": "jar", "action": "keep", "fact": ""}],
                          "new": {"title": "Work at the stall",
                                  "facts": ["The woman has offered a day's work."],
                                  "people": [woman.ref, "c99"]}})
    watcher._work(watcher._jobs_for(c))
    assert watcher.drain(c) is True
    new = [k for k in cards.load(c.scene) if k.origin == "watcher"]
    assert len(new) == 1 and new[0].title == "Work at the stall"
    assert new[0].people == [woman.ref] and new[0].is_("situation.play")
    assert new[0].place == c.scene.at


def test_a_card_the_engine_moved_since_the_model_read_it_is_left_alone(campaign, monkeypatch):
    """The tell that moved it is the truer fact; the model's was written against a
    table that is gone."""
    from rules import cards
    c = campaign
    _cards_ready(c)
    _answer(monkeypatch, {"changes": [{"id": "jar", "action": "resolve", "fact": ""}],
                          "new": None})
    watcher._work(watcher._jobs_for(c))
    cards.touch(c.scene, "jar", "The engine moved it first.", turn=5, tick=True)
    assert watcher.drain(c) is False
    assert cards.find(c.scene, "jar").stage == "moving"
