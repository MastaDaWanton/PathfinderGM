"""The manual, and the promise that it cannot quietly become a lie.

Why this file exists, measured 2026-09-11: `README.md` had carried a section headed
"What is deliberately not built yet" listing full character creation, combat beyond
single attacks, attacks of opportunity, the world-state agent, the SRD content import
and Electron packaging. **All six had shipped.** The same file told a reader that the
verbatim OGL "still has to be added" while `OGL.txt` sat beside it in the repository.

Nothing caught it because nothing was looking. A document that lists features from
memory drifts the moment the code moves, and the drift is invisible — it reads
perfectly well while being wrong.

So the manual does not list anything from memory. Every count on it is read from the
catalogue that holds it, and these tests pin that: a number that stops matching its
source fails here rather than misinforming somebody who has just installed the app.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings


@pytest.fixture
def page(client):
    """The rendered manual, with runs of whitespace collapsed to one space.

    Without that, every assertion about a phrase is really an assertion about where the
    template happens to wrap: "8 GB of video memory" reads perfectly on the page and
    fails a substring match because a newline sits between "video" and "memory". A test
    that breaks on reflowing a paragraph is a test people learn to delete.
    """
    import re

    r = client.get("/manual")
    assert r.status_code == 200
    return re.sub(r"\s+", " ", r.content.decode("utf-8"))


# --- It is reachable from inside the app ----------------------------------------------

def test_the_manual_is_served_from_the_app_itself(client):
    """The same reason the licence is. This ships as one executable, so a manual sitting
    in a GitHub repository the player never opens is not a manual they have."""
    assert client.get("/manual").status_code == 200


def test_both_pages_a_player_sits_on_link_to_it(client):
    """A manual nobody can find is the same as no manual. The front page carries it in
    the header — the person who most needs it has just opened the app and does not yet
    know what the tabs are — and the table carries it in the character pane."""
    for path in ("/", "/play/"):
        assert '/manual' in client.get(path).content.decode("utf-8"), (
            f"{path} does not link to the manual")


def test_it_is_the_only_copy():
    """A second copy in the repository would drift from the served one within a month,
    which is CLAUDE.md's "grep for every copy of it" applied before there is a copy to
    grep for. README.md links to it and repeats none of it."""
    assert not (Path(settings.BASE_DIR) / "MANUAL.md").exists(), (
        "a second copy of the manual has appeared; there must be one")
    readme = (Path(settings.BASE_DIR) / "README.md").read_text(encoding="utf-8")
    assert "/manual" in readme, "README.md no longer points a player at the manual"


# --- Every number on it is read from the thing that holds it ---------------------------

def test_the_counts_are_the_real_catalogues_and_not_typed_in(page):
    """The check the README never had. If a class is added, this number moves."""
    from rules import bestiary, classes, feats, races, spells

    for label, n in [("classes", len(classes.all_classes())),
                     ("races", len(races.all_races())),
                     ("feats", len(feats.all_feats())),
                     ("spells", len(spells.all_spells())),
                     ("creatures", len(bestiary.everything()))]:
        assert f"{n:,}" in page or str(n) in page, (
            f"the manual does not show the real {label} count ({n:,}) — it has either "
            f"drifted or gone back to a typed-in number")


def test_the_models_and_their_sizes_come_from_preflight(page):
    """The player is being asked to download several gigabytes. The name and the number
    have to be the ones the app will actually fetch, not a pair somebody wrote down."""
    from play import preflight

    wanted = preflight.needs()
    assert wanted, "the manual has nothing to tell anybody to download"
    for need in wanted:
        assert need.model in page, f"{need.model} is not named in the manual"
        assert preflight.gb(need.bytes_estimate) in page, (
            f"{need.model}'s size is not in the manual")
    assert preflight.gb(sum(n.bytes_estimate for n in wanted)) in page, (
        "the manual does not state the total download")


def test_the_optional_model_is_marked_optional(page):
    """7.4 GB is the mandatory download and 9.9 GB is the whole set. Presenting the
    backup narrator as required would overstate the requirement by a third."""
    assert "optional" in page


def test_the_shipped_worlds_are_the_ones_on_the_shelf(page):
    from play import library

    shipped = [w.name for w in library.worlds() if w.shipped]
    assert shipped, "no world ships with the app; the manual's promise is now false"
    for name in shipped:
        assert name in page
    # The verb agrees with the count rather than being a constant, so a second shipped
    # world does not leave the sentence reading "Pangrella and Fantasia ships".
    assert (" ships with the app" if len(shipped) == 1
            else " ship with the app") in page


def test_the_crafting_disciplines_are_listed_from_the_module(page):
    from play.craft_views import DISCIPLINES

    for d in DISCIPLINES:
        assert d["name"] in page, f"{d['name']} is missing from the manual"


def test_the_data_directory_is_the_real_one(page):
    """"Where are my saves" is the commonest support question any desktop app gets, and
    an answer that is right on the developer's machine only is worse than none."""
    assert str(Path(settings.CAMPAIGN_DIR).parent) in page


# --- The honest parts ------------------------------------------------------------------

def test_it_says_how_slow_a_turn_is(page):
    """CLAUDE.md: local models are slow, that is the price of privacy and zero cost, and
    "the manual should say so". A first run that surprises somebody with a forty-second
    turn has mis-sold the product."""
    lowered = page.lower()
    assert "fifteen seconds" in lowered
    assert "minute" in lowered, "the cold-load cost is not mentioned"


def test_it_says_what_the_machine_needs_before_asking_for_the_download(page):
    """Nobody should spend 7.4 GB of bandwidth to discover their laptop cannot run it."""
    assert "video memory" in page.lower()


def test_it_does_not_promise_what_the_readme_used_to(page):
    """The specific lie this file was written about. The README claimed six shipped
    features were unbuilt; the manual must not claim unbuilt features are shipped, which
    is the same failure pointing the other way.

    Multiclassing is the live example: it is named in README.md's own "not built" list,
    and a manual that offered it would be selling something the forge cannot do.
    """
    assert "multiclass" not in page.lower(), (
        "the manual offers multiclassing, which the character forge does not build")


def test_the_licence_travels_with_it(page):
    """OGL section 10. Every page a player reads about the rules content has to be able
    to reach the licence for it."""
    assert "/licence" in page
    assert "Open Game Licence" in page
    assert "Paizo" in page, "the disclaimer is not on the page"
