"""The six schemes written on 2026-09-13, driven to their endings.

Validating is not playing. `docs/quest-schemes-plan.md` §11 records a playtest agent
reporting "A Small Favour" as "not playable as shipped" after every validator and lint
in the project had passed it: the frame could never fire because `holds(pc, …)` read
the crafted shelf while foraging writes the satchel, and news never arrived in the live
app because a per-request Engine reset the tick counter. Both were green in every test
and dead at the table.

So each of these drives a scheme through a real Engine to a real outcome. What that
caught while being written, none of which the lint has any opinion about:

  * `bring_in` never consulted the codex. It was three hand-written names — watchman,
    thug, guildhand — so a scheme about something eating a herd asked for a "beast" and
    got a Commoner 1 who is "not paid enough to fight". Named as still open in §10.
  * Every item slot resolves to an ingredient whatever the slot is called, so tracks in
    the mud came out as "there is Chasmyre Leaf on the ground here".
  * Five of the nine schemes opened at one market inside the first day, because nothing
    counted how many stories the world had going at once.
  * `remove` names its subject `to` where `hide` and `kill` name it `who`, and the wrong
    spelling validates and takes the tag off the player.
"""
from __future__ import annotations

import pytest

from rules import cards, schemes
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"
MARKET = f"{TOWN}~urban:the-market"


@pytest.fixture(autouse=True)
def schemes_on(monkeypatch):
    monkeypatch.setattr(schemes, "ENABLED", True)


def _alone(monkeypatch, sid: str):
    """One scheme, opened by hand, with the catalogue narrowed to it.

    Narrowed because the cap would otherwise let whichever two schemes the calendar
    favours open instead, and this is about a named one.
    """
    doc = schemes.all_schemes()[sid]
    monkeypatch.setattr(schemes, "all_schemes", lambda: {sid: doc})
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party(MARKET)
    inst = schemes.open_scheme(e, doc, turn=1)
    return s, e, s.pc(), inst


def _run(e, op, params, actor="pc"):
    return e.run(e.validate([{"op": op, "actor": actor, "because": "t", "params": params}],
                            origin="author:test"))


def _wait(e, minutes=30):
    return _run(e, "advance_time", {"amount": minutes, "unit": "minutes"})


# --- a debt in the book ------------------------------------------------------------------

def test_the_debt_can_be_shown_to_be_wrong(monkeypatch):
    """The ending that needs the twist: meet the debtor, hear the debt was paid, go
    back and open the book. Nothing is carried and nobody is robbed."""
    s, e, pc, inst = _alone(monkeypatch, "a-debt-in-the-book")
    _wait(e)
    _run(e, "travel", {"place": inst["slots"]["lodging"]["name"]})
    _wait(e)
    assert "met" in inst["fired"] and pc.has_state("knows.debtor-cannot-pay")
    _wait(e)
    assert "twist" in inst["fired"], "the twist never fired, so the ending is unreachable"
    assert pc.has_state("knows.book-was-kept-twice")

    _run(e, "travel", {"place": inst["slots"]["market"]["name"]})
    _wait(e)
    assert inst.get("outcome") == "shown", inst["fired"]
    lender = s.people[inst["slots"]["lender"]["ref"]]
    assert lender.has_state("attitude.unfriendly"), "being shown up costs the lender"


def test_the_twist_is_foreshadowed_before_it_can_land(monkeypatch):
    """Fairness: the open grants what the twist names, so the brief has carried it
    before the player is asked to believe anything."""
    _s, _e, pc, _inst = _alone(monkeypatch, "a-debt-in-the-book")
    assert pc.has_state("knows.lender-was-quick-to-name-a-total")


# --- a sickness in the house --------------------------------------------------------------

def test_the_second_quest_does_not_exist_until_somebody_looks(monkeypatch):
    """The deferred card. Which herb and where is not knowable until the healer says
    so, and a card on the board from turn one would give it away."""
    _s, e, _pc, inst = _alone(monkeypatch, "the-sickness")
    assert "remedy" not in inst["cards"], "the remedy is on the board before anyone asked"
    _wait(e)
    assert "named" in inst["fired"]
    assert "remedy" in inst["cards"], "the healer spoke and no quest appeared"


def test_the_herb_gets_there_in_time(monkeypatch):
    s, e, pc, inst = _alone(monkeypatch, "the-sickness")
    _wait(e)
    # Foraged, the way `holds` reads it: the satchel, not the crafting shelf. That
    # distinction is why §11's frame could never fire.
    pc.carry(inst["slots"]["herb"]["id"], 1)
    _run(e, "travel", {"place": inst["slots"]["lodging"]["name"]})
    for _ in range(3):
        _wait(e)
    assert inst.get("outcome") == "in-time", inst["fired"]
    healer = s.people[inst["slots"]["healer"]["ref"]]
    assert healer.has_state("attitude.helpful")


def test_nobody_dies_while_the_herb_is_in_hand(monkeypatch):
    """The clock has teeth and must not bite the player who did the thing. `turned`
    requires `not holds(pc, $herb)`, so carrying it holds the fever off."""
    _s, e, pc, inst = _alone(monkeypatch, "the-sickness")
    _wait(e)
    pc.carry(inst["slots"]["herb"]["id"], 1)
    _run(e, "advance_time", {"amount": 6 * 24 * 60, "unit": "minutes"})
    assert "turned" not in inst["fired"], "the patient died with the cure in the room"


# --- what takes the herds -------------------------------------------------------------------

def test_the_threat_is_a_real_stat_block_and_not_a_guildhand(monkeypatch):
    """`bring_in` asks the codex now. Before this it could only ever produce a
    watchman, a thug or a guildhand, whatever the role word said."""
    s, e, _pc, inst = _alone(monkeypatch, "what-takes-the-herds")
    _wait(e)
    _run(e, "travel", {"biome": inst["slots"]["wild"]["terrain"]})
    _wait(e, 70)
    assert "lie-up" in inst["fired"], inst.get("skipped")
    brought = [s.people[r] for r in inst.get("brought", [])]
    assert brought, "nobody arrived"
    assert not any(a.from_template == "guildhand" for a in brought), (
        f"the codex was not asked: {[a.from_template for a in brought]}")


def test_seeing_the_fight_through_finishes_the_quest(monkeypatch):
    """`event:fight_ended` — the only scheme that keys on it. `bring_in` puts people on
    the board and does not start the fight, which is the GM's call, so the chain is
    arrive, begin, end."""
    s, e, pc, inst = _alone(monkeypatch, "what-takes-the-herds")
    _wait(e)
    _run(e, "travel", {"biome": inst["slots"]["wild"]["terrain"]})
    _wait(e, 70)
    born = inst["brought"]
    _run(e, "begin_encounter", {"sides": {"us": ["pc"], "them": born}})
    for ref in born:
        s.people[ref].hp = 0
    _run(e, "end_encounter", {})

    assert inst.get("outcome") == "dealt-with", inst["fired"]
    quest = next(c for c in cards.load(s) if not c.secret and "animals" in c.title)
    assert all(o["done"] for o in quest.objectives), quest.objectives


def test_walking_away_is_an_ending_and_not_a_dead_quest(monkeypatch):
    """Every scheme here resolves both ways. A quest that can only be abandoned sits on
    the player's board forever, which the fairness critic caught in the shipped line as
    three of five endings leaving the player wanted for good."""
    s, e, _pc, inst = _alone(monkeypatch, "what-takes-the-herds")
    _wait(e)
    _run(e, "travel", {"biome": inst["slots"]["wild"]["terrain"]})
    _wait(e, 70)
    _run(e, "travel", {"place": inst["slots"]["market"]["name"]})
    _run(e, "advance_time", {"amount": 7 * 60, "unit": "minutes"})

    assert inst.get("outcome") == "still-out-there", inst["fired"]
    assert inst["news"] or "left-it-out-there" in inst["fired"]


# --- all three ---------------------------------------------------------------------------

@pytest.mark.parametrize("sid", ["a-debt-in-the-book", "the-sickness",
                                 "what-takes-the-herds"])
def test_each_grounds_every_slot_from_the_world(monkeypatch, sid):
    """No invented names. Every person, place and thing comes from the export or the
    catalogues, which is the promise the whole scheme system rests on."""
    s, _e, _pc, inst = _alone(monkeypatch, sid)
    doc = schemes.all_schemes()[sid]
    missing = [n for n in doc["slots"] if n not in inst["slots"]]
    assert not missing, f"{sid} left {missing} unfilled"
    for name, slot in inst["slots"].items():
        assert slot.get("name"), f"{sid}.{name} filled with something nameless"
        if slot.get("kind") == "actor":
            assert s.people[slot["ref"]].name


# --- word from the road --------------------------------------------------------------
#
# The first scheme whose inciting event happens where the player is not, and the first
# that does not open at the market.

def _news_tags(pc):
    return [t for x in pc.effects for t in x.tags if t.startswith("knows.news.")]


def test_the_word_arrives_by_courier_and_nothing_is_asked_before_it(monkeypatch):
    s, e, pc, inst = _alone(monkeypatch, "word-from-the-road")
    _run(e, "travel", {"place": inst["slots"]["lodging"]["name"]})
    assert not _news_tags(pc), "the player knows before anybody told them"

    _run(e, "advance_time", {"amount": 26 * 60, "unit": "minutes"})
    assert [n["carrier"] for n in inst["news"]] == ["courier"], inst["news"]
    _run(e, "advance_time", {"amount": 26 * 60, "unit": "minutes"})
    # The tag is named for the step that sent it, which is what later steps wait on.
    assert "knows.news.word" in _news_tags(pc)


def test_going_to_look_finds_them_and_the_reason(monkeypatch):
    s, e, pc, inst = _alone(monkeypatch, "word-from-the-road")
    _run(e, "travel", {"place": inst["slots"]["lodging"]["name"]})
    _run(e, "advance_time", {"amount": 26 * 60, "unit": "minutes"})
    _run(e, "advance_time", {"amount": 26 * 60, "unit": "minutes"})
    _run(e, "travel", {"biome": inst["slots"]["wild"]["terrain"]})
    for _ in range(3):
        _wait(e)
    assert "twist" in inst["fired"], "the reason never surfaced"
    _run(e, "travel", {"place": inst["slots"]["lodging"]["name"]})
    for _ in range(2):
        _wait(e)
    assert inst.get("outcome") == "answered", inst["fired"]


def test_never_going_is_an_ending_with_a_body_in_it(monkeypatch):
    """Not a failure state and not a dangling card: it resolves, out of sight, and the
    log and the secret card carry what happened."""
    s, e, pc, inst = _alone(monkeypatch, "word-from-the-road")
    _run(e, "travel", {"place": inst["slots"]["lodging"]["name"]})
    for _ in range(9):
        _run(e, "advance_time", {"amount": 24 * 60, "unit": "minutes"})

    assert inst.get("outcome") == "nobody-went", inst["fired"]
    overdue = s.people[inst["slots"]["overdue"]["ref"]]
    assert overdue.hp <= 0, "the clock ran out and nothing happened"
    assert inst["fired"]["never-went"]["silent"], "the player was told about it somehow"


# --- gone to ground -------------------------------------------------------------------

def test_hiding_and_being_found_are_the_same_tag(monkeypatch):
    """`hide` on the open and `remove` on the finding — the only paired use of either.
    The assertion that matters is the third one: `remove` names its subject `to`, and
    authored as `who` it validates and lifts the tag off the *player* instead."""
    s, e, pc, inst = _alone(monkeypatch, "gone-to-ground")
    hidden = s.people[inst["slots"]["hidden"]["ref"]]
    assert hidden.has_state("state.hidden"), "nobody went to ground"

    _run(e, "travel", {"place": inst["slots"]["market"]["name"]})
    _wait(e)
    _run(e, "travel", {"place": inst["slots"]["lodging"]["name"]})
    _wait(e)
    assert not hidden.has_state("state.hidden"), "found, and still hiding"
    assert not pc.has_state("state.hidden"), "the tag came off the player"


def test_keeping_the_name_and_giving_it_up_are_both_endings(monkeypatch):
    s, e, pc, inst = _alone(monkeypatch, "gone-to-ground")
    _run(e, "travel", {"place": inst["slots"]["market"]["name"]})
    _wait(e)
    _run(e, "travel", {"place": inst["slots"]["lodging"]["name"]})
    for _ in range(2):
        _wait(e)
    assert pc.has_state("knows.what-they-are-owed"), "the twist never landed"
    _run(e, "travel", {"place": inst["slots"]["temple"]["name"]})
    _wait(e)
    assert inst.get("outcome") == "kept", inst["fired"]
    hidden = s.people[inst["slots"]["hidden"]["ref"]]
    assert hidden.has_state("attitude.helpful")


# --- the sealed letter ----------------------------------------------------------------

def test_the_guild_is_a_row_from_the_export_and_not_a_body(monkeypatch):
    """The faction slot has no `ref`: it is text for a card and a tell, and nothing
    else. Naming it anywhere that needs a person would be a silent no-op."""
    _s, _e, _pc, inst = _alone(monkeypatch, "the-sealed-letter")
    guild = inst["slots"]["guild"]
    assert guild["kind"] == "faction" and guild["name"]
    assert "ref" not in guild


def test_the_letter_reaches_the_person_it_is_addressed_to(monkeypatch):
    """The road is `the edge`, and travelling by ground lands at the approach instead —
    the §11 shape, where a card named a place ordinary travel could not reach. It is
    reachable by its name, which is what the prose gives the player."""
    s, e, pc, inst = _alone(monkeypatch, "the-sealed-letter")
    _run(e, "travel", {"place": inst["slots"]["guildhall"]["name"]})
    _wait(e)
    _run(e, "travel", {"place": inst["slots"]["gate"]["name"]})
    _wait(e)
    r = _run(e, "travel", {"place": inst["slots"]["road"]["name"]})
    assert s.at == inst["slots"]["road"]["id"], (
        f"the road is unreachable by the name the prose uses: {s.at}")
    for _ in range(4):
        _wait(e)
    assert inst.get("outcome") == "delivered", inst["fired"]
    assert pc.has_state("knows.what-it-says"), "delivered it without ever opening it"


@pytest.mark.parametrize("sid", ["word-from-the-road", "gone-to-ground",
                                 "the-sealed-letter"])
def test_each_of_the_second_three_grounds_too(monkeypatch, sid):
    s, _e, _pc, inst = _alone(monkeypatch, sid)
    doc = schemes.all_schemes()[sid]
    missing = [n for n in doc["slots"] if n not in inst["slots"]]
    assert not missing, f"{sid} left {missing} unfilled"
    for name, slot in inst["slots"].items():
        assert slot.get("name"), f"{sid}.{name} filled with something nameless"


def test_no_two_schemes_open_on_the_same_day():
    """Twelve of them now. Two sharing a gate would fight over the same townspeople the
    moment the cap frees a slot."""
    gates = {}
    for sid, doc in schemes.shipped().items():
        if not schemes._starts_fresh(doc):
            continue
        gates[sid] = next(c for c in doc["opens"] if c.startswith("since(campaign)"))
    assert len(set(gates.values())) == len(gates), gates
