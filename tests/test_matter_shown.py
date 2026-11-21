"""A town's trouble shown as something happening here, never as a mood in the air.

The owner, 2026-11-21: "Tensions over water rights linger in the air like a heavy mist — I
see the above phrasing very often … please tell me what is happening that creates this
tension instead of the general dilemma or the overarching problem." Measured on the
owner's saves: 20 of 964 GM beats said a tension hung, lingered or was palpable in the air;
the planned matter slot wrote 14 of them and the "still" slot carried 10 forward. The
research and the bench are docs/research/2026-11-21-matter-shown.md.
"""
from __future__ import annotations

import json
import re

import pytest

from gm import planned
from rules import cards
from rules.engine import Engine, Scene
from rules.dice import Dice
from rules.sheet import load_pc

# The owner's own pages (2026-11-21 count), and concrete showings that must pass.
OWNER_MOODS = (
    "The tension over the control of a trade toll lingers in the air like the heavy mist "
    "clinging to the coastal shore.",
    "Local tension over a heretical splinter cult hangs heavy in the air.",
    "Signs of strained tensions over smuggling routes are visible in the guarded "
    "fortifications.",
    "While the market hums, the underlying tension over disputed grazing lands remains a "
    "simmering fact that could boil over at any moment during the trade season.",
    "The air carries a heavy tension, a lingering shadow of the conflict over the heretical "
    "splinter cult that plagues the region.",
    "Tensions over the disputed grazing lands hang heavy over the square.",
)
SHOWINGS = (
    "A notice about the water dispute hangs on the door of the moot hall.",
    "A fresh padlock holds the cistern lid shut, and a chalked tally of buckets runs down "
    "the wall beside it.",
    "Through the wall comes a shout about whose turn it is at the well.",
    "The smell of smoke lingers in the air of the forge.",
    "The heavy door of the moot hall stands shut, a list of names nailed to it.",
)


def test_the_mood_in_the_air_is_found_in_code_and_a_showing_is_not():
    """The owner's six measured sentences are each found; five concrete showings, three of
    them with "hangs", "lingers" or "heavy" in them, are not."""
    assert all(planned.told_not_shown(x) for x in OWNER_MOODS)
    assert not any(planned.told_not_shown(x) for x in SHOWINGS)
    two = OWNER_MOODS[1] + " " + SHOWINGS[1]
    assert planned.told_not_shown(two) == [OWNER_MOODS[1]], "the sentence, not the slot"


def test_the_trouble_is_asked_for_as_one_thing_here_shown_by_demonstration():
    """The slot read "A matter of the world here … Let it touch the scene in one sentence,
    as something seen or heard here" and was handed only "Ongoing friction over grazing
    land"; it handed the abstraction back. Now it asks for one thing here, by a synthetic
    demonstration that turns over between showings, and is told what was shown before."""
    pull = {"title": "Ongoing friction over grazing land", "fact": "Simmering.",
            "standing": "situation", "ambient": True, "shown": []}
    first = planned.matter_slot(pull)
    assert first["shows"] and first["not_own"] == pull["title"]
    assert "ONE thing" in first["say"] and "PEOPLE HERE NOW" in first["say"]
    assert "HOW A TROUBLE IS SHOWN" in first["say"]
    # The ask itself never says the word it is trying to keep off the page.
    assert not re.search(r"tension|in the air|palpable", first["say"], re.I)
    shown = ["A padlock holds the cistern shut."]
    second = planned.matter_slot(dict(pull, shown=shown))
    assert "A padlock holds the cistern shut." in second["say"]
    assert second["say"].split("HOW A TROUBLE")[1] != first["say"].split("HOW A TROUBLE")[1]


def test_a_card_remembers_what_was_shown_and_forgets_it_on_a_new_version(monkeypatch):
    """`Card.shown` is derived from model output and kept in the save, so it is stamped:
    CLAUDE.md's five-day-old stylesheet was a cache whose staleness check answered "fresh"."""
    s = Scene(location_id="t1")
    cards.open_card(s, cards.Card(id="w", title="Who draws from the well",
                                  tags=(cards.TAG_WORLD,), place="t1"))
    for n in range(cards.SHOWN_KEPT + 2):
        cards.note_shown(s, "w", f"Showing {n}.", turn=10 + n)
    card = cards.find(s, "w")
    assert card.shown[-1] == f"Showing {cards.SHOWN_KEPT + 1}." and \
        len(card.shown) == cards.SHOWN_KEPT
    assert card.mentioned == 10 + cards.SHOWN_KEPT + 1, "a showing starts the card's rest"
    monkeypatch.setattr(cards, "SHOWN_VERSION", cards.SHOWN_VERSION + 1)
    assert cards.find(s, "w").shown == []
    plain = cards.Card(id="x", title="t")
    assert "shown" not in plain.as_dict(), "a card that showed nothing round-trips unchanged"


def _town_card(world):
    """A world trouble pinned to a settlement, and that settlement's id."""
    for raw in (world.play or {}).get("cards") or []:
        place = str(raw.get("place") or "")
        if place and not raw.get("people") and not raw.get("secret") \
                and world.get(place.split("~")[0]) is not None:
            return raw, place.split("~")[0]
    pytest.skip("this export pins no trouble to a settlement")


def test_a_town_trouble_is_pulled_only_in_its_own_streets(worlds):
    """The prose-gold writers found 6 of 19 matter slots pulled where nobody was — a wood,
    the last sheds, a ridgeline — "an invitation to invent", and the shipped pages did ("a
    heavy fog", "dry, cracked earth"). In its own streets it is pulled, with what was shown;
    on the ring outside the walls, or in another town, never."""
    raw, town = _town_card(worlds)
    other = next(e for e in (worlds.play.get("cards") or [])
                 if str(e.get("place") or "").split("~")[0] not in ("", town))
    s = Scene(location_id=town)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.at = f"{town}~urban:the-market"
    for c in cards.from_world(worlds, s.at):
        cards.open_card(s, c)
    said = raw["title"]

    def pull(at):
        s.at = at
        return cards.thread_to_pull(s, recent=[], player_text=said, turn=40, world=worlds)

    got = pull(f"{town}~urban:the-market")
    assert got is not None and got.get("ambient") and got["shown"] == []
    slot = planned.matter_slot(got)
    assert slot["shows"]
    for away in (f"{town}~plains:@the-fields", f"{other['place'].split('~')[0]}~urban:the-market"):
        p = pull(away)
        assert p is None or not (p.get("ambient") and p["id"] == got["id"]), away


def test_two_loose_keys_in_a_tell_do_not_raise_a_town_trouble():
    """One owner save pulled the same town's grazing land on beats 8, 39, 55, 73 and 79:
    a strain card has forty-odd loose keys ("trade", "local", "season") and two of them in
    any market tell made it "spoken". A world trouble is spoken of by its own words now."""
    s = Scene(location_id="t1")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.at = "t1~urban:the-market"
    facts = ["Ongoing friction over grazing land.", "Trade disputes flare in the busy "
             "trading season, and local politics turn on it."]
    cards.open_card(s, cards.Card(id="t1-strain", title="Ongoing friction over grazing land",
                                  facts=facts, tags=(cards.TAG_WORLD,), place="t1"))
    tell = "The local trade goes on; the season's prices are chalked on a board."
    assert cards._hits(cards.find(s, "t1-strain"), tell) >= 2, "the old test fired"
    assert cards.thread_to_pull(s, recent=[], tells=[tell], turn=40) is None
    asked = cards.thread_to_pull(s, recent=[], player_text="Who is quarrelling over the "
                                 "grazing land?", turn=40)
    assert asked is not None and asked["id"] == "t1-strain"
    assert asked["fact"] == facts[1], "the world's own words, never the newest tell"


# --- the slot, written ------------------------------------------------------------------

class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.3, "stub"
        self.done_reason, self.prompt_tokens, self.reply_tokens = "stop", 0, 0

    def json(self):
        return json.loads(self.text)


def _chat(calls, matter):
    def chat(messages, model, host, **kw):
        props = (kw.get("schema") or {}).get("properties") or {}
        calls.append(messages[-1]["content"])
        if "text" not in props:
            raise RuntimeError("not answered in this test")
        key = re.findall(r'Now write slot \d+, "(\w+)"', messages[-1]["content"])[-1]
        text = matter.pop(0) if key == "matter" else "You look about you."
        return _Reply(json.dumps({"text": text}))
    return chat


def _engine():
    s = Scene(location_id="t1")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.at = "t1~urban:the-market"
    return Engine(s, Dice(seed=3))


PULL = {"id": "t1-strain", "title": "Ongoing friction over water rights",
        "fact": "Merchant clans and the council compromise on water.", "keys": ["water"],
        "standing": "situation", "ambient": True, "shown": [], "since": 30}


@pytest.mark.parametrize("second,kept", [
    ("A new padlock holds the cistern lid shut, and a chalked tally of buckets runs down "
     "the post beside it.", True),
    ("Tensions over water rights linger in the air like a heavy mist.", False),
])
def test_a_mood_is_asked_again_named_and_dropped_if_it_stays(monkeypatch, second, kept):
    """The owner's own sentence, written by the slot: asked once more with it named; a
    showing in its place stands, and the mood twice leaves no matter on the page at all —
    nothing beats a mood there. Before this, the shipped slot stood as written."""
    calls: list = []
    first = "Tensions over water rights linger in the air like a heavy mist."
    monkeypatch.setattr(planned.client, "chat", _chat(calls, [first, second]))
    out = planned.write(_engine(), brief="BRIEF", player_input="I look around.",
                        outcomes=[], who=("stub", "http://x", "ollama", ""), pull=PULL)
    matter = next(x for x in out.slots if x["key"] == "matter")
    assert any("says a trouble is in the air" in c for c in calls)
    assert (second in out.text) is kept and first not in out.text
    assert bool(matter.get("dropped")) is not kept


def test_a_showing_already_shown_is_asked_for_anew(monkeypatch):
    """The Alexandrian's scenic encounters are restocked "as they get used up": the same
    padlock on the second visit is the same beat twice."""
    calls: list = []
    old = "A new padlock holds the cistern lid shut, and a tally of buckets runs down the post."
    fresh = "From behind the council's shuttered door come two voices arguing over the sluice."
    monkeypatch.setattr(planned.client, "chat", _chat(calls, [old, fresh]))
    out = planned.write(_engine(), brief="BRIEF", player_input="I look around.",
                        outcomes=[], who=("stub", "http://x", "ollama", ""),
                        pull=dict(PULL, shown=[old]))
    assert any("already shown here" in c for c in calls)
    assert fresh in out.text and old not in out.text


def test_another_slot_loses_only_its_mood_sentence(monkeypatch):
    """The "still" and act slots carried the mood 14 times on the owner's saves, from the
    brief. The sentence is named, and cut if it comes back; the rest of the slot stands."""
    moody = "You look about you. Tension over the toll hangs heavy in the air."
    calls: list = []

    def chat(messages, model, host, **kw):
        calls.append(messages[-1]["content"])
        return _Reply(json.dumps({"text": moody}))

    monkeypatch.setattr(planned.client, "chat", chat)
    out = planned.write(_engine(), brief="BRIEF", player_input="I look around.",
                        outcomes=[], who=("stub", "http://x", "ollama", ""))
    assert "hangs heavy" not in out.text and "You look about you." in out.text
