"""Narration fidelity, the overnight playtest of 2026-11-16 (Vesna Kroll on integrate/0.4.0,
log pgm-work/playtest-2026-11-16.md, items 59-99 and E2). Read off the save's turn log
first: most of these were written by our own pull, repairs and tells, not the narrator.
Each test names what the page said."""
from __future__ import annotations

from types import SimpleNamespace

from gm import beat_verify as bv, deed_reader, planned
from rules import cards, dungeons, faces, intents, places, ships, survival
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import Intent
from rules.sheet import from_dict, load_pc
from tests.test_ships_and_piracy import _docks, _travel, held_at_quay  # noqa: F401

ABILITIES = {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")}
HERE = "7ef5e373c993~urban:the-gardens"
CHANNEL = "7ef5e373c993~underground:the-gardens/the-sewers/the-main-channel"


def _person(s, ref, name):
    return s.add(from_dict({"name": name, "kind": "npc", "hp": 8, "hp_max": 8,
                            "abilities": dict(ABILITIES)}, ref=ref))


def _scene(at=HERE):
    s = Scene(location_id="7ef5e373c993")
    s.at = at
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


def _quest(s, place=CHANNEL):
    cards.open_card(s, cards.Card(
        id="quest-3", title="Find what was kept below the sewers off the gardens",
        facts=["The way down is the bricked-up culvert in the main channel."],
        keys=["kept", "below", "sewers", "gardens", "culvert"],
        tags=(cards.TAG_QUEST, cards.TAG_PLAY), place=place, kind="quest",
        objectives=[{"text": "Defeat whatever holds the deepest room", "done": False}],
        known="taken"))


# --- #59 and #76: a matter pinned elsewhere, pulled into a beat about something else ------

def test_the_players_own_matter_pinned_elsewhere_waits_for_the_player_to_raise_it():
    """#59 (T277): asking the smuggler in the cells about her cargo, the matter slot wrote
    "You are still driven by the goal to uncover what lies beneath the sewers", the quest
    pinned to the main channel. #76 (T296): at the east crossing, "A hidden passage remains
    a secret of the architecture", a card pinned to the main channel and "spoken" only
    because the gate's tell listed the main channel among the ways out. Pinned to another
    spot, with none of its people here, a matter comes up when the player raises it."""
    s = _scene()
    _quest(s)
    tells = ["Leave by another way — the sewers, the outfall, the main channel."]
    assert cards.thread_to_pull(s, recent=[], turn=40, tells=tells,
                                player_text="Where is your cargo?") is None
    pulled = cards.thread_to_pull(s, recent=[], turn=40,
                                  player_text="I head back down to the sewers below the "
                                              "gardens to find what was kept there.")
    assert pulled and pulled["id"] == "quest-3"
    s.at = CHANNEL                       # at its own place it is the matter nearest to hand
    assert (cards.thread_to_pull(s, recent=[], turn=40) or {}).get("id") == "quest-3"


# --- #67 and #90: the town's talk pasted into the prose --------------------------------------

def _rumour(s, place="7ef5e373c993~underground:the-well/the-cellars"):
    cards.open_card(s, cards.Card(
        id="rumour-1", title="What Mirabalos says of the cellars off the well",
        facts=["Every drinker in Mirabalos has a story about treasure deep in the cellars "
               "off the well."],
        keys=["cellars", "well", "treasure", "drinker"], tags=(cards.TAG_RUMOUR,),
        place=place, clock_max=6))


def test_the_towns_talk_is_somebodys_words_at_a_free_moment():
    """#67 (T285): asking the gardener for a healer, the slot wrote "Nearby, the local
    gossip of the city's well-known cellar treasures … hangs in the air like a persistent,
    unsettling rumor" between her question and his answer. Talk is somebody's words, never
    while the player is busy with somebody, and the slot says whose and where it is of."""
    s = _scene()
    _rumour(s)
    assert cards.thread_to_pull(s, recent=[], turn=1) is None          # nobody to say it
    gardener = _person(s, "c25", "the gardener")
    engine = Engine(s, Dice(seed=1))
    engine.join_talk(gardener, how="you spoke to them")
    assert cards.thread_to_pull(s, recent=[], turn=1) is None          # she is busy
    engine.end_talk(who=gardener)
    pulled = cards.thread_to_pull(s, recent=[], turn=1)
    assert pulled["carrier"] == {"ref": "c25", "name": "the gardener"}
    slot = planned.matter_slot(pulled)
    assert slot["say"].startswith("the gardener, who is here, mentions in passing")
    assert "somewhere else, not here" in slot["say"] and slot["carrier_ref"] == "c25"
    assert "seen or heard here" not in slot["say"]


def test_a_ship_at_the_quay_is_no_settlement_with_sewers_under_its_rigging(monkeypatch):
    """#90 (T317): "Local whispers warn that the sewers beneath the rigging hide both lost
    treasures and missing children". The rumour itself was "What Mirabalos says of the
    sewers off the rigging": the talk was spread once with the ship standing for the
    settlement, and her rigging given a way down. A ship spreads no talk, and a save that
    already holds such a card never pulls it."""
    s = _scene(at="ship-sailing-ship-f4bd3228b56c~deck:the-deck")
    engine = SimpleNamespace(scene=s, world=object())
    dungeons.spread_rumours(engine)
    assert not [c for c in cards.load(s) if c.is_(cards.TAG_RUMOUR)]
    assert not s.said
    _rumour(s, place="ship-sailing-ship-f4bd3228b56c~underground:the-rigging/the-sewers")
    _person(s, "c20", "a deckhand")
    assert cards.thread_to_pull(s, recent=[], turn=1) is None


# --- #61: the night's one event cut as an attack missing -------------------------------------

def test_a_creature_going_by_is_no_attack_missing():
    """#61 (T279): the slot wrote "a lone Mite skitters past your head in the dark", the
    engine's "In the night a Mite comes near the camp, and goes on by", and the outcome-
    claims repair cut it as an attack missing: the page left out the night's one event."""
    said = {c.why for c in intents.find_outcome_claims(
        "You sleep as a lone Mite skitters past your head in the dark.")}
    assert "states an attack missing" not in said
    said = {c.why for c in intents.find_outcome_claims(
        "The arrow skitters past your head and into the dark.")}
    assert "states an attack missing" in said


# --- #62: the clock's dawn narrated as weather underground ----------------------------------

def test_an_hour_told_with_the_sky_underground_is_a_contradiction():
    """#62 (T279): "the morning air making your muscles ache" in a burnt-out prison below
    the sewers. The hour was right (dawn); its sky was not there. Judged only where every
    kind of place the beat may be set in is underground or a room."""
    sentence = "You wake stiff, the morning air making your muscles ache."
    c = bv.Claim("hour", {"part": "morning"}, quote="the morning air making your muscles ache",
                 sentence=sentence, valid=True)
    f = bv.Facts(start="the cells", end="the cells", places=("the cells",),
                 people=(bv.Person("pc", "Vesna Kroll", pc=True),), clock=6 * 60 + 10,
                 settings=("inside a building", "underground"))
    [d] = [d for d in bv.diff([c], f) if d.category == "hour"]
    assert "underground" in d.fact and "open air" in d.fact
    calm = bv.Claim("hour", {"part": "morning"}, quote="you wake to the morning",
                    sentence="You wake to the morning.", valid=True)
    assert not [d for d in bv.diff([calm], f) if d.category == "hour"]
    town = bv.Facts(**{**f.__dict__, "settings": ("a town street, square or market",)})
    assert not [d for d in bv.diff([c], town) if d.category == "hour"]


# --- #74: the stop at the east crossing cut, and a foreman made for the say ------------------

def test_a_walk_stopped_short_backs_the_page_saying_it_failed():
    """#74 (T294): "You reach the east crossing … as you fail to reach the docks" was cut as
    an invented verdict, its repair wrote "as you approach the docks" (refused by the tells
    gate), and the page never said she was stopped. The engine's `stopped_short` backs it."""
    walk = {"op": "travel", "status": "resolved", "verdict": None,
            "effects": [{"kind": "biome", "stopped_short": True, "meant_for": "the docks"}]}
    assert "states success or failure" in intents.claims_the_engine_backs([walk])
    walk["effects"][0]["stopped_short"] = False
    assert "states success or failure" not in intents.claims_the_engine_backs([walk])


def test_words_for_somebody_who_is_not_here_say_nobody_answers():
    """#74: alone at the east crossing, "I ask the foreman…" went to the dock labourer, who
    was in Zhilvarnia; the say's tell said nothing of nobody hearing, the slot wrote "The
    foreman shakes his head", and a foreman was made on the spot. The negative is stated;
    with somebody here, it is not."""
    s = _scene()
    labourer = _person(s, "c29", "the dock labourer")
    labourer.at = "6953424c8a82~urban:the-docks"           # in Zhilvarnia
    assert "c29" not in s.actors and "c29" in s.people
    e = Engine(s, Dice(seed=1))
    # Straight to the op, as the turn had it: the plan's say kept its target past the
    # validator (the turn log's intent i2, `target: c29`).
    out = e._op_say(Intent(op="say", actor="pc", target="c29",
                           params={"words": "is there a day's honest work going?"}), {})
    assert out.tell.endswith("Nobody here answers."), out.tell
    _person(s, "c25", "the gardener")
    out = e._op_say(Intent(op="say", actor="pc", target="c29",
                           params={"words": "good day"}), {})
    assert "Nobody here answers" not in out.tell


# --- #87: the question the turn was about went unanswered ----------------------------------

def test_arriving_at_the_quay_says_the_ship_she_holds_lies_there(held_at_quay):  # noqa: F811
    """#87 (T315): "I walk down to the docks to see whether the Red Gull is still tied up"
    — she arrived and the beat never said; the engine knew (her exits listed the ship)."""
    scene, engine, pc, ship = held_at_quay
    out = _travel(engine, _docks(engine).name)             # down her gangplank
    walk = next(o for o in out if o.op == "travel")
    name = ships.name_for(ship.id)
    assert f"{name[:1].upper()}{name[1:]} lies at the quay." in walk.tell, walk.tell


# --- #88: a smith's dressing on the harbourmaster --------------------------------------------

def test_a_face_with_no_work_known_is_never_given_one_trades_hands():
    """#88 (T315): the harbourmaster's "presence marked by the scent of smoke and hot iron":
    his seeded face carried "a smell of smoke and hot iron that goes everywhere they do", a
    smith's line (`lives._HANDS_FIT` gives it the forge alone), drawn with no work known."""
    lines = [faces.details_for("", f"c{n}", "7ef5e373c993") for n in range(400)]
    assert not [line for line in lines for t in faces.ONE_TRADE if t in line]
    assert any("rings on three fingers" in line for line in lines)


# --- #89: the body line carried the strain that had just ended -------------------------------

def test_the_grave_wounds_are_told_as_wounds_not_lost_strength():
    """#89 (T317): a beat after "the lingering fog of fatigue clears", "You stagger onto the
    Red Gull, your heavy limbs trembling": the check's rewrite was told the wounds as
    "gravely hurt, with little strength left in them", wrote the ended fatigue, and the
    backstop then added "Each breath pulls at your wounds" under it."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.hp = 1
    [w] = [s for s in survival.strains(pc) if s.key == "wounds"]
    assert w.words.startswith("gravely") and "wound" in w.words and "strength" not in w.words


# --- #98: a ship's lower deck narrated as a building -----------------------------------------

def test_every_room_of_a_ship_is_aboard_her():
    """#98 (T328): going below decks the page said "the shadows of the ship's hold", the
    setting check called below decks "indoors, under a roof — not aboard a ship", and its
    repair wrote "the shadows of the building's interior"."""
    for room in ("below-decks", "the-deck", "the-hold"):
        p = places.Place(id=f"ship-sailing-ship-f4bd3228b56c~deck:{room}", name=room,
                         terrain="deck")
        assert places.settings_for(p) == frozenset({places.SET_SHIP}), room
    c = bv.Claim("setting", {"kind": "inside a building"},
                 quote="the shadows of the building's interior",
                 sentence="You walk through the shadows of the building's interior.",
                 valid=True)
    f = bv.Facts(start="below decks", end="below decks", places=("below decks",),
                 people=(bv.Person("pc", "Vesna Kroll", pc=True),), clock=480,
                 settings=("aboard a ship or boat",))
    [d] = [d for d in bv.diff([c], f) if d.category == "setting"]
    assert "aboard a ship" in d.fact and "ship's own timbers" in d.fact


# --- #99: the refusal pasted raw ------------------------------------------------------------

def test_a_sleep_already_due_is_refused_in_a_line_a_page_can_carry():
    """#99 (T328): "It is early morning (about 8 in the morning) now: the time you meant to
    sleep until dawn has already come today…" pasted on the page. The reader had taken "You
    must decide whether to sleep now for eight hours or wait until evening" (the refusal's
    own choices) for the player sleeping; the backstop then cut it and wrote the refusal."""
    s = _scene()
    s.clock_minutes = 13 * 24 * 60 + 8 * 60 + 3
    e = Engine(s, Dice(seed=1))
    out = e.run(e.validate([{"op": "rest", "actor": "pc", "because": "t",
                             "params": {"kind": "night", "until": "until dawn"}}])).outcomes[0]
    assert out.code == "already_then"
    assert "(" not in out.tell and "the time" not in out.tell, out.tell
    assert out.tell.startswith("It is about 8 in the morning, and dawn has already come "
                               "today"), out.tell
    assert "what they may still choose" in deed_reader._REFUSED_REST_SYSTEM


# --- E2: the aside wrote somebody who was not there ------------------------------------------

def test_the_aside_is_about_one_of_the_people_it_was_offered(monkeypatch):
    """E2 (narration lane, live): offered the deckhand on the Red Gull's deck, the aside
    wrote "The merchant continues to adjust the crates", and nobody of that name was
    aboard. Read back by the names it was offered, asked once more, else dropped."""
    s = {"key": "aside", "names": ["a deckhand", "penguin"]}
    out = planned.Planned(text="", slots=[], messages=[], model="m")
    asked = []

    def ask(out, plan, slots, i, written, who, **kw):
        asked.append(kw["redo"])
        out.calls.append({"note": ""})
        return replies.pop(0), {}

    monkeypatch.setattr(planned, "_ask", ask)
    replies = []
    kept = "The deckhand goes on coiling a rope by the rail."
    assert planned._aside_is_theirs(out, [], [], 0, [], None, s, kept, final=True,
                                    lift=None) == kept and not asked
    replies = [kept]
    got = planned._aside_is_theirs(out, [], [], 0, [], None, s,
                                   "The merchant continues to adjust the crates.",
                                   final=True, lift=None)
    assert got == kept and "a deckhand or penguin" in asked[0]
    replies = ["A sailor hums by the mast."]
    assert planned._aside_is_theirs(out, [], [], 0, [], None, s,
                                    "The merchant continues to adjust the crates.",
                                    final=True, lift=None) is None
