"""No key the engine keeps reaches the page: refs and things' ids are said by name.

The ruling of 2026-09-28 — refs drive the prose checks, the player never sees them. Measured
on the round-3 bench of 2026-11-05 (docs/narration-diagnosis.md, the agree line, run 4): the
planner made a `sell` of a thing nobody carried, the engine refused it with "… is not
carrying blade-blank-1. They have: backpack#1, …", and `beat_verified`'s `beat-omits-outcome`
backstop pasted that tell on the page whole — the planner's id, the shelf's keys and the
whole inventory. `judgement.name_refs` had run on the draft before any backstop pasted
anything, and nothing named a thing's key at all.

Two fixes, tested here: the refusals name their things at the source and carry a page
sentence without the inventory (`Outcome.for_a_person`, which every refusal backstop takes
first); and the last pass of every narrated door (`narration.names_not_keys`, at the end of
`GMAgent._groom`, in the narrator-down fallback `views.plain_tell`, and on a refusal that is
the whole turn) says every key it finds by name.
"""
from __future__ import annotations

import glob
import gzip
import json
import re
from pathlib import Path

import pytest

from gm import beat_verify as bv
from gm import checks, client, judgement, narration
from gm.checks import beat_verified
from rules import blacksmith, crafting, holding, leatherworker
from rules.bestiary import next_ref
from rules.crafting import Stock

from _a_truth import MARKET, VORMOOR, context, scene_at

HERE = Path(__file__).resolve().parent


def _keys_on(text: str) -> list[str]:
    """Every key the engine mints, as it would stand on a page: a thing's key in any of the
    engine's shapes (`holding.KEY_SHAPED`), a person's bare ref (`judgement._BARE_REF`), a
    brief's ref tag."""
    return ([m.group(1) for m in holding.KEY_SHAPED.finditer(text or "")]
            + [m.group(1) for m in judgement._BARE_REF.finditer(text or "")]
            + re.findall(r"\(\s*(?:c|pc)\d*\s*\)", text or ""))


# --- the shapes are the engine's own --------------------------------------------------------

def test_every_key_shape_the_engine_mints_is_one_the_guard_knows():
    """The guard's pattern is held to the minting functions themselves, not to a guess at
    them: a new shelf-key format that slipped past it would slip past every page."""
    plain = Stock(base="Healing Draught", concentration=1)
    stepped = Stock(base="Comfrey Poultice", concentration=2, form="poultice", quality=2)
    hide = leatherworker.make_hide("deer-hide")
    blade = blacksmith.Work(form="item", material="iron", shape="longsword", gear="weapon",
                            passes=2, quality=3, name="Iron Longsword")
    minted = [plain.id, stepped.id, leatherworker.stock_key(hide),
              blacksmith.stock_key(blade), f"{VORMOOR.id}~urban:the-smithy",
              f"{VORMOOR.id}~hills:@the-ridgelines"]
    assert "#" in plain.id and "~" in stepped.id, minted
    for key in minted:
        assert holding.KEY_SHAPED.fullmatch(key), key
        assert not holding.KEY_SHAPED.search(holding.key_words(key)), key
    # And a person's ref, by the engine's own door.
    assert judgement._BARE_REF.fullmatch(next_ref(None))
    # The planner's own copies of the shape (the bench's sale, judgement.py's of 2026-10-16).
    for key in ("blade-blank-1", "gold_coins_10"):
        assert holding.KEY_SHAPED.fullmatch(key), key


def test_english_is_not_a_key():
    """Only the engine's shapes: no ordinary prose token is touched."""
    prose = ("The half-orc smith sets a well-worn hammer down. A 1st-level spell, a "
             "two-handed sword, 3 sp for the lot and a d20 on the table. 'Not today,' "
             "she says. Section 4-B is closed.")
    assert holding.KEY_SHAPED.findall(prose) == []
    assert holding.key_words("sweetspire tea") == "sweetspire tea"
    assert holding.key_words("blade-blank-1") == "blade blank"
    assert holding.key_words(f"{VORMOOR.id}~urban:the-smithy") == "the smithy"


# --- at the source: the refusals ------------------------------------------------------------

def _bench_scene():
    agent, _ = scene_at(MARKET)
    pc = agent.engine.scene.pc()
    pc.add_stock(Stock(base="Backpack", concentration=1, count=1, specs=[]))
    pc.add_stock(Stock(base="Healing Draught", concentration=1, count=1,
                       specs=[{"type": "heal", "dice": "1d4"}]))
    pc.goods["crate"] = 1
    return agent, pc


def _sell(agent, item):
    e = agent.engine
    return e.run(e.validate([{"op": "sell", "actor": "pc", "params": {"item": item}}])
                 ).outcomes[0]


def test_a_refused_sale_names_its_things_and_its_page_line_lists_no_pack():
    """The bench's refusal, made again: the tell names what is carried by name (for the
    narrator and the log), and the sentence a player reads names only the thing not
    carried. On the old path the tell held "blade-blank-1" and "backpack#1", and there was
    no page sentence, so the omission backstop took the tell."""
    agent, pc = _bench_scene()
    assert "backpack#1" in pc.stock
    out = _sell(agent, "blade-blank-1")
    assert out.status == "refused"
    assert "backpack#1" not in out.tell and "blade-blank-1" not in out.tell, out.tell
    assert _keys_on(out.tell) == [], out.tell
    assert "They have: Backpack, Healing Draught, crate." in out.tell
    assert out.for_a_person == "Bobby is not carrying blade blank."
    assert bv._refusal_line(out.as_dict()) == out.for_a_person


def test_a_jar_not_carried_is_refused_by_name():
    agent, pc = _bench_scene()
    e = agent.engine
    out = e.run(e.validate([{"op": "use_item", "actor": "pc",
                             "params": {"item": "moonshine#9"}}])).outcomes[0]
    assert out.status == "refused"
    assert _keys_on(out.tell) == [] and _keys_on(out.for_a_person) == [], out.tell
    assert out.for_a_person == "Bobby is not carrying moonshine."


@pytest.fixture
def silent_reader(monkeypatch):
    """The read back on, answering that the page claims nothing: the omission is then the
    only finding, as on the bench."""
    monkeypatch.setattr(bv, "ENABLED", True)
    bv.clear_cache()
    beat_verified._CONFIRMED.clear()

    class _Reply:
        def __init__(self, obj):
            self.text, self.seconds, self.model = json.dumps(obj), 0.0, "stub"

        def json(self):
            return json.loads(self.text)

    def chat(messages, *a, schema=None, **k):
        props = (schema or {}).get("properties", {})
        if "player_ends_at" in props:
            return _Reply({"player_ends_at": {"place": "the market", "quote": ""},
                           "changed_hands": [], "trades": [], "harmed": [], "arrived": [],
                           "left": [], "time_of_day": {"part": "unstated", "quote": ""}})
        if "setting" in props:
            return _Reply({"setting": []})
        if "answer" in props:
            return _Reply({"answer": "yes"})
        return _Reply({"sentence": ""})

    monkeypatch.setattr(client, "chat", chat)
    yield
    bv.clear_cache()
    beat_verified._CONFIRMED.clear()


def test_the_omission_backstop_pastes_the_page_line_not_the_tell(silent_reader):
    """The path the bench took: a refused sale the page never mentions, the backstop puts
    the engine's answer before the hand-back. Before 2026-11-05 that answer was the tell,
    keys and inventory and all."""
    agent, _pc = _bench_scene()
    refused = _sell(agent, "blade-blank-1")
    text = "The smith turns the blank over in the forge light. What do you do?"
    ctx = context(agent, text, outcomes=[refused])
    found = checks.run(ctx)
    assert [f.kind for f in found] == ["beat-omits-outcome"]
    out, _notes, _ = agent._repair_sentences(text, found, ctx)
    assert "They have" not in out and "blade-blank-1" not in out and "#1" not in out, out
    assert _keys_on(out) == [], out
    assert out == ("The smith turns the blank over in the forge light. Bobby is not "
                   "carrying blade blank. What do you do?")


# --- the last pass ----------------------------------------------------------------------------

def test_the_last_pass_says_every_key_by_name():
    """Whatever a backstop pasted: a ref of somebody here, of somebody who has left (the
    store, `Scene.people`), a possessive ref, the player's ref, a shelf key of anybody's,
    and a key nobody carries, said in its words."""
    agent, _refs = scene_at(MARKET, [("the smith", "guildhand"), ("the clerk", "guildhand")])
    scene = agent.engine.scene
    pc = scene.pc()
    pc.add_stock(Stock(base="Backpack", concentration=1, count=1, specs=[]))
    smith, clerk = [next(a for a in scene.people.values() if a.name == n)
                    for n in ("the smith", "the clerk")]
    clerk.at = f"{VORMOOR.id}~urban:the-counting-house"     # gone: in the store, not here
    assert clerk.ref not in scene.actors and clerk.ref in scene.people
    page = (f"{smith.ref} sets down the hammer and looks at pc. {clerk.ref}'s ledger is "
            f"shut. Bobby is not carrying blade-blank-1. They have: backpack#1, crate.")
    out, keyed = narration.names_not_keys(page, scene)
    assert _keys_on(out) == [], out
    assert out == ("The smith sets down the hammer and looks at you. The clerk's ledger is "
                   "shut. Bobby is not carrying blade blank. They have: Backpack, crate.")
    assert set(keyed) == {"blade-blank-1", "backpack#1", smith.ref, clerk.ref, "pc"}
    # Nothing to name: the page is returned as it was.
    assert narration.names_not_keys("The forge is quiet.", scene) == ("The forge is quiet.",
                                                                      [])


def test_the_narrator_down_fallback_says_keys_by_name():
    """`views.plain_tell`, the page when no prose was written: the tell shown with its
    numbers off, and since 2026-11-05 its keys said by name."""
    from play.views import plain_tell

    agent, pc = _bench_scene()
    line = plain_tell("Bobby is not carrying blade-blank-1. They have: backpack#1, crate.",
                      agent.engine.scene)
    assert _keys_on(line) == [], line
    assert line == "Bobby is not carrying blade blank. They have: Backpack, crate."


def test_a_button_doors_refusal_is_its_page_sentence():
    """The counter, the drink and the gear buttons write the engine's lines straight onto
    the page (`views._page_tells`): a refusal by its page sentence, and no key."""
    from types import SimpleNamespace

    from play.views import _page_tells

    agent, _pc = _bench_scene()
    refused = _sell(agent, "blade-blank-1")
    c = SimpleNamespace(scene=agent.engine.scene)
    assert _page_tells(c, [refused]) == "Bobby is not carrying blade blank."


def test_the_groom_ends_on_the_last_pass(monkeypatch):
    """`names_not_keys` is the last page step of `_groom`, after every backstop and after
    `strip_turn_numbers`: a key put on the page by the step before it is still said by
    name. Asserted by behaviour (tests/test_suite_isolation.py holds source pins down)."""
    agent, _pc = _bench_scene()
    pasted = " Bobby is not carrying blade-blank-1. They have: backpack#1."
    monkeypatch.setattr(narration, "strip_turn_numbers",
                        lambda text, outcomes: (text + pasted, []))

    def no_model(*a, **k):
        raise RuntimeError("no model in this test")

    monkeypatch.setattr(client, "chat", no_model)
    text, repairs, _ = agent._groom("The forge is quiet. What do you do?", claims=False,
                                    rewrite=False, hand_back=False)
    assert _keys_on(text) == [], text
    assert text.endswith("Bobby is not carrying blade blank. They have: Backpack.")
    assert any(r.startswith("a key on the page") for r in repairs), repairs


# --- page-wide: every recorded final page and every recorded tell ----------------------------

def _recordings():
    files = sorted(glob.glob(str(HERE / "replay" / "*.jsonl.gz"))) + sorted(
        glob.glob(str(HERE / "replay" / "plans" / "*.jsonl.gz")))
    for f in files:
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                yield Path(f).name, json.loads(line)


def _recorded_scenes(tmp_path):
    """(recording, record, the scene of the save the turn was played from), each loaded
    as `tests/_replay.py` loads it."""
    from django.test import override_settings

    from play import campaign as cm

    for name, rec in _recordings():
        with override_settings(CAMPAIGN_DIR=str(tmp_path)):
            p = tmp_path / f"{rec['save_before']['id']}.json"
            p.write_text(json.dumps(rec["save_before"]), encoding="utf-8")
            yield name, rec, cm.Campaign.load(p).engine().scene


def test_every_recorded_final_page_leaves_the_last_pass_without_a_key(tmp_path):
    """Every page the narration tests' recordings shipped (tests/replay), through the last
    pass against the save it was played from, holds no key in the engine's shapes; and
    every passage of the read-back gold set holds none to begin with.

    Two recorded pages of 2026-09-25 shipped one, both a key-shaped word the narrator
    wrote itself: "'Heading for the river_docks,' he calls out" (strangers, turn 4) and
    "a scroll of manifest_papers" (town, turn 5). The last pass says them in words."""
    from beat_verify import gold

    pages, keyed, bad = 0, [], []
    for name, rec, scene in _recorded_scenes(tmp_path):
        for entry in rec.get("added_transcript") or ():
            if entry.get("who") != "gm" or not entry.get("text"):
                continue
            pages += 1
            if _keys_on(entry["text"]):
                keyed.append((name, rec.get("turn"), _keys_on(entry["text"])))
            out, _ = narration.names_not_keys(entry["text"], scene)
            if _keys_on(out):
                bad.append((name, rec.get("turn"), _keys_on(out)))
    assert pages > 100, pages
    assert sorted(k for _n, _t, ks in keyed for k in ks) == ["manifest_papers", "river_docks"]
    assert bad == []
    assert len(gold.GOLD) > 40
    assert [(b["id"], _keys_on(b["text"])) for b in gold.GOLD if _keys_on(b["text"])] == []


def test_every_recorded_tell_reaches_the_page_without_a_key(tmp_path):
    """Every tell in the recordings' turn logs, put on a page the ways a tell is put there
    — as a backstop's engine line (`page_line`, then the groom's last pass), as an act
    slot's fallback (`planned.engine_line`, the same), and as the narrator-down fallback
    (`views.plain_tell`) — against the save it was told in. The introductions' tells carry
    the actor's ref ("In the scene: passing carter (c9)."), so this is not vacuous."""
    from gm import planned
    from play.views import plain_tell

    told, bad, seen = 0, [], set()
    for name, rec, scene in _recorded_scenes(tmp_path):
        tells = [o.get("tell") for e in rec.get("added_turn_log") or ()
                 for o in e.get("outcomes") or () if o.get("tell")]
        for tell in tells:
            told += 1
            seen |= set(_keys_on(tell))
            for page in (narration.names_not_keys(narration.page_line(tell), scene)[0],
                         narration.names_not_keys(planned.engine_line([tell]), scene)[0],
                         plain_tell(tell, scene)):
                if _keys_on(page):
                    bad.append((name, rec.get("turn"), page[:120]))
    assert told > 100 and seen, (told, seen)
    assert bad == []
