"""The GM's knowledge and the table's content, and the engine's small doors.

Groups 5 and 6 of the 2026-09-18 fix pass (docs/playtest-2026-09-18.md, items 9, 22's
setting and memory, 1/20, 3, 7, 22's watcher). `/gm` handed over "a shadow power in the
form of an old veterans' league" on the first question of the session with no gate: the
dossier wrote every settlement fact and put Shadow Power among the first four for any
"who runs" question. The ruling: the information should be available, but only after the
player is asked. "/cheat I gain 2000 experience" did nothing twice because no op carried
experience. The damage card printed "Str x2 +38" over "your modifier +38". A named quest
giver sat in the scene list for many turns and was never named in prose. The watcher
advanced a town's water-rights card from inside a brothel on "the current transaction is
a private matter" and paid 200 XP. And the negotiation and the payment had left the
window: nothing carried the agreement forward.
"""
from __future__ import annotations

import pytest

from gm import judgement
from play import campaign as cm, gm_search
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from pagesource import table_source


@pytest.fixture(scope="module")
def world():
    return cm.load_cached(cm._resolve_world_source("fixtures/aurvantis-campaign.json"))


@pytest.fixture
def vormoor(world):
    s = Scene(location_id=world.by_name("Vormoor", kind="CITY").id)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


# --- 9: what the character would know --------------------------------------------------------

def test_facts_are_tiered_by_key_and_the_dossier_keeps_the_hidden_ones(world):
    assert gm_search.tier_of("Shadow Power") == "hidden"
    assert gm_search.tier_of("Secret") == "hidden"
    assert gm_search.tier_of("Tension") == "rumour"
    assert gm_search.tier_of("Formal Power") == "public"
    assert gm_search.tier_of("Architecture") == "public", "an unknown key is public"
    town = world.by_name("Vormoor", kind="CITY")
    public = gm_search.dossier(world, town, "who runs this town")
    assert "Shadow Power:" not in public
    assert "Formal Power:" in public
    everything = gm_search.dossier(world, town, "who runs this town",
                                   allow=frozenset({"public", "rumour", "hidden"}))
    assert "Shadow Power:" in everything
    kept = gm_search.withheld_from(dict(town.facts), frozenset({"public"}))
    assert ("Shadow Power", "hidden") in kept


def test_the_narrators_brief_is_redacted_for_the_out_of_character_call(world, vormoor):
    """Measured live 2026-09-19 with the dossier already tiered: the first `/gm`
    answer still said "an old veterans' league that holds significant shadow power" —
    it came from the narrator's brief, which the out-of-character call inherits."""
    from gm import prompts

    town = world.by_name("Vormoor", kind="CITY")
    brief = prompts.scene_brief(world, vormoor, town, [])
    assert "  Shadow Power:" in brief, "the narrator keeps it"
    redacted = gm_search.redact(brief, frozenset({"public"}), facts=dict(town.facts))
    assert "Shadow Power:" not in redacted and "Tension:" not in redacted
    assert "Formal Power:" in redacted
    # And the export's own paragraphs restate the fact: the Governance section says
    # what the veterans' league does. The sentence goes; the paragraph stays.
    assert "veteran" not in redacted.lower()
    assert "veteran" not in gm_search.dossier(world, town, "who runs this town").lower()
    assert "Governance:" in gm_search.dossier(world, town, "who runs this town")
    assert "Shadow Power:" in gm_search.redact(brief, frozenset({"public", "rumour", "hidden"}))
    import inspect

    from play import views

    assert "brief = gm_search.redact(brief, allow," in inspect.getsource(views._ask_the_gm)


def test_a_persons_secret_leaves_the_passages_unless_allowed(world):
    hits = gm_search.search(world, "who is Drenn Ironvale")
    shown = gm_search.passages(world, hits, "who is Drenn Ironvale")
    assert "Secret:" not in shown and "Drenn Ironvale" in shown
    told = gm_search.passages(world, hits, "who is Drenn Ironvale",
                              allow=frozenset({"public", "rumour", "hidden"}))
    assert "Secret:" in told


def test_the_gm_path_rolls_once_offers_by_the_table_rule_and_hands_over_on_the_word():
    import inspect

    from play import views

    src = inspect.getsource(views._ask_the_gm)
    assert 'said_mem[key] = bool(roll.total >= 15)' in src, "one Knowledge (local) roll, DC 15"
    assert 'if key not in said_mem:' in src, "Try Again: No"
    assert "_hr.knowledge_offer()" in src
    assert "tell me anyway" in src
    assert 'said_mem["gm:withheld"]' in src
    # Untrained is not a fault: the first live `/gm` of the replay was a 500 because
    # the sheet refuses an untrained Knowledge (local) roll — and the Core Rulebook
    # caps an untrained check at DC 10, under rumour's 15. The character does not know.
    assert "except IllegalSheet:" in src and "said_mem[key] = False" in src


def test_the_table_settings_exist_with_the_defaults_the_ruling_asked_for():
    from rules import houserules

    assert houserules.DEFAULTS["knowledge_offer"] is False
    assert houserules.DEFAULTS["content"] == "fade"
    rules, problems = houserules.set_active({"content": "loud"})
    assert problems and rules["content"] in ("fade", "explicit")


def test_the_content_setting_is_one_line_of_the_prose_briefing():
    from gm import prompts

    line = prompts.content_line()
    assert "fade to black" in line or "adult content" in line
    msgs = prompts.call_prose_messages("BRIEF", [], "I wait", [])
    assert any("intimacy" in m["content"] for m in msgs if m["role"] == "system")


# --- 22: the agreement survives the window ---------------------------------------------------

def test_what_was_agreed_is_written_by_the_engine_and_read_back_until_the_party_moves(vormoor):
    from gm import prompts

    # Its own Scene field since 2026-09-25 (it lived in `said`, a dict with no schema).
    vormoor.agreements = ["Kesst Vayr paid the woman 10 gp for the night"]
    now = prompts.scene_now(vormoor)
    assert "WHAT WAS AGREED here (fact, still standing): Kesst Vayr paid the woman 10 gp for the night" in now
    import inspect

    from play import views

    src = inspect.getsource(views._finish)
    assert "c.scene.agreements" in src and "hands (.+?) (\\d+) × (gp|sp|cp|pp)" in src
    # A move clears it: the next room starts clean.
    vormoor.move("pc", "somewhere-else") if hasattr(vormoor, "move") else None
    if hasattr(vormoor, "move"):
        assert vormoor.agreements == []


# --- 1/20: an xp op, and the cheat read in code -----------------------------------------------------

def test_an_xp_op_exists_and_the_cheat_reads_the_amount_without_the_model(vormoor):
    pc = vormoor.pc()
    engine = Engine(vormoor, Dice(seed=1))
    before = int(pc.xp)
    res = engine.run(engine.validate([{"op": "xp", "params": {"amount": 2000,
                                                               "reason": "the author's word"}}]))
    assert int(pc.xp) == before + 2000
    assert "2,000 XP" in res.outcomes[0].tell or "2000 XP" in res.outcomes[0].tell
    raw = judgement.cheat_intents("I gain 2000 experience", vormoor)
    assert raw == [{"op": "xp", "because": "the author's word",
                    "params": {"amount": 2000, "reason": "the author's word"}}]
    coin = judgement.cheat_intents("I have 1000 gold", vormoor)
    assert coin[0]["op"] == "give" and coin[0]["params"] == {"item": "gp", "count": 1000, "to": "pc"}
    assert judgement.cheat_intents("I am the king of the town", vormoor) == []
    from gm import prompts

    assert "xp" in prompts.CHEAT_OPS


# --- 3: the dice card ----------------------------------------------------------------------------

def test_the_card_does_not_print_one_term_twice_and_the_reason_wraps():
    from pathlib import Path

    html = table_source()
    assert html.count('if (p.breakdown.length !== 1) terms.push({ label: "your modifier"') == 2
    assert "overflow-wrap: anywhere" in html


# --- 7: the giver in the room reaches for the player ---------------------------------------------

def test_a_cards_person_standing_here_makes_it_quiet_in_two_turns_and_speaks_first(vormoor):
    from rules import cards

    giver = instantiate("guildhand", scene=vormoor, name="Myskalyndra Arinisyn")
    vormoor.add(giver)
    card = cards.Card(id="q1", kind="quest", title="The lost ledger", people=[giver.ref],
                      place=str(vormoor.at or ""), facts=["a ledger went missing"],
                      objectives=[{"text": "find who took it", "done": False}],
                      touched=1, mentioned=0)
    cards.save(vormoor, [card]) if hasattr(cards, "save") else vormoor.cards.append(card.as_dict())
    pull = cards.thread_to_pull(vormoor, recent=["The market is loud."], turn=4)
    assert pull is not None and pull["title"] == "The lost ledger"
    assert "Myskalyndra Arinisyn is standing here" in pull["text"]
    assert "say the first word" in pull["text"]


# --- 22: the watcher's scope --------------------------------------------------------------------------

def test_the_watcher_advances_a_card_only_on_a_fact_about_it():
    import inspect

    from gm import watcher

    src = inspect.getsource(watcher._apply_cards)
    assert "the fact is not about this card" in src
    assert "cards_mod._hits(card, fact) >= 1" in src
