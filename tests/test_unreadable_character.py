"""One character the rules reject took the whole home page down with it.

Found on 2026-09-15 in a live session's own log, while checking whether closing the app
had broken anything. It had not; this was already there:

    Internal Server Error: /
      File "play\\home_views.py", line 49, in home
      File "play\\library.py", line 263, in recent_characters
      File "play\\roster.py", line 66, in summary
      File "rules\\sheet.py", line 3885, in validate
    rules.sheet.IllegalSheet: Kesst Vayr: 10 skill ranks spent, 9 available
                              (8 class + Int + race, x1)
    "GET / HTTP/1.1" 500 145

`recent_characters` loops every character on the roster and builds a summary of each.
One of them no longer validated, nothing caught it, and the front page — the only route
to every OTHER character and every campaign — returned a 500. The player could still
reach a `/play/` URL they already had open, and nothing else.

**The guard is in `Entry.summary`, not in the view.** Four places call it in a loop: two
in `library`, two in `views`. Guarding the one that happened to crash is the mistake this
session has now made twice — the model gate went on two doors of three, and a background
was bound by one of three — so it goes where all four pass through.

**`Entry.actor` still raises, and that is the design.** Listing a character has to be
safe. Playing one must not be: a game started from a sheet the rules reject is a worse
failure than a card saying it cannot be read.
"""
from __future__ import annotations

import inspect

import pytest

from play import roster


def _entry(sheet: dict, **over) -> roster.Entry:
    base = {"id": "x", "name": "Kesst Vayr", "status": roster.ALIVE, "sheet": sheet,
            "turns_played": 7, "created": "2026-09-01T10:00:00"}
    base.update(over)
    return roster.Entry(**base)


# The reported failure, reproduced: `rules.sheet.validate` raises when a PC has spent
# more skill ranks than the class, Int and race allow. `kind: "pc"` is load-bearing —
# validation only runs for a player character, and the first version of this file left it
# out, so every "broken" sheet here loaded as a perfectly legal NPC and all six tests
# passed against a guard that was never reached.
BROKEN = {"name": "Kesst Vayr", "kind": "pc", "level": 1, "class": "rogue",
          "ranks": {"perception": 99}}

# The other way in, so nothing here depends on one rule: any reason a sheet will not load
# has to be survivable, and a class the catalogue has lost is the likelier one after a
# homebrew class is deleted.
NO_CLASS = {"name": "Kesst Vayr", "kind": "pc", "level": 1, "class": "no-such-class"}

GOOD = {"name": "Fine", "kind": "pc", "level": 1, "class": "fighter"}


def test_a_character_that_will_not_load_still_produces_a_card():
    """The report, as an assertion. `summary` may not raise, whatever is on disk."""
    got = _entry(BROKEN).summary()
    assert got["name"] == "Kesst Vayr"
    assert got["unreadable"], "nothing says the sheet could not be read"
    assert got["turns_played"] == 7, "the roster file's own facts survive"


def test_the_card_carries_every_key_a_good_one_does():
    """Or the crash moves rather than goes. `home.html` reads `hp`, `line`,
    `turns_played`, `status` and `epitaph` off this dict with no guard of its own, so a
    missing key is a `KeyError` one frame later and the page is still blank."""
    good = _entry(GOOD).summary()
    bad = _entry(BROKEN).summary()
    missing = set(good) - set(bad)
    assert not missing, f"an unreadable card is short of {sorted(missing)}"


def test_the_reason_is_shown_and_not_swallowed():
    """A player who cannot see why cannot decide whether to fix the character or delete
    them, and both are their call. The sheet's own message is what goes on the card."""
    got = _entry(BROKEN).summary()
    assert got["line"] == got["unreadable"]
    assert got["line"].strip(), "the card would say nothing at all"


def test_a_good_character_is_unchanged():
    """The guard must be invisible when nothing is wrong."""
    got = _entry(GOOD).summary()
    assert got["unreadable"] == ""
    assert "/" in got["hp"], got["hp"]


def test_playing_one_still_refuses(monkeypatch):
    """The other half, and the one that matters more. `campaign.begin_with` reaches for
    `entry.actor` to start a game; that path must keep raising, because a game started
    from a sheet the rules reject is a worse failure than a card that says so."""
    with pytest.raises(Exception):
        _ = _entry(BROKEN).actor


def test_an_unreadable_character_is_not_playable():
    """And the button is not offered. `playable` was computed in two views with the same
    expression, neither of which knew about the third reason a character cannot be
    played — dead, and now unreadable."""
    assert _entry(BROKEN).playable() is False
    assert _entry(GOOD).playable() is True
    assert _entry(GOOD, status=roster.DEAD).playable() is False


def test_every_reader_of_the_roster_goes_through_the_guard():
    """The real defect was its location, not its absence. Checked by reading the call
    sites rather than by counting them, because the failure mode is a FIFTH place being
    added later — and a test that asserts "there are four" passes happily when somebody
    writes the fifth."""
    from play import library, views

    for mod in (library, views):
        src = inspect.getsource(mod)
        assert "status != roster.DEAD" not in src, (
            f"{mod.__name__} computes `playable` itself again; it must ask "
            f"`entry.playable()`, which knows about an unreadable sheet too")


def test_the_home_page_survives_a_roster_with_a_broken_character(monkeypatch):
    """End to end, through the function that actually 500'd."""
    from play import library

    monkeypatch.setattr(roster, "everyone",
                        lambda: [_entry(GOOD, id="ok", name="Fine"),
                                 _entry(BROKEN, id="bad")])
    monkeypatch.setattr(library, "worlds", lambda: [])
    rows = library.recent_characters()
    assert len(rows) == 2, "a character was dropped rather than shown"
    by_name = {r["name"]: r for r in rows}
    assert by_name["Fine"]["playable"] is True
    assert by_name["Kesst Vayr"]["playable"] is False
    assert by_name["Kesst Vayr"]["unreadable"]


def test_the_card_says_so_on_screen():
    """The template half: an unreadable character shows the reason and offers no way to
    play, and the Delete button stays — removing them is the player's own remedy."""
    from pathlib import Path

    from django.conf import settings

    page = Path(settings.BASE_DIR, "play", "templates", "play", "home.html").read_text(
        encoding="utf-8")
    assert "the sheet cannot be read" in page
    assert "c.unreadable" in page
    # The Play button is gated on `playable`, which is now false for these.
    assert 'c.playable ? `<button class="quiet" data-resume=' in page


def test_any_reason_a_sheet_will_not_load_is_survivable():
    """Not just the reported one. A homebrew class deleted from the bench leaves every
    character of it unloadable, and that must not take the page down either."""
    got = _entry(NO_CLASS).summary()
    assert got["unreadable"], "an unknown class still escapes"
    assert "class" in got["line"].lower(), got["line"]


def test_the_reported_message_is_the_one_that_reaches_the_card():
    """The exact shape from the live log, minus the name the card already shows as its
    heading: "10 skill ranks spent, 9 available (8 class + Int + race, x1)"."""
    line = _entry(BROKEN).summary()["line"]
    assert line.startswith("99 skill ranks spent, 9 available"), line
    assert not line.startswith("Kesst Vayr"), "the name is repeated on its own card"
