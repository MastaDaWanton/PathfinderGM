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
from pagesource import served


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
        assert '/manual' in served(client, path), (
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
    from rules import (backgrounds, bestiary, classes, feats, places, races, schemes,
                       spells)

    for label, n in [("classes", len(classes.all_classes())),
                     ("races", len(races.all_races())),
                     ("feats", len(feats.all_feats())),
                     ("spells", len(spells.all_spells())),
                     ("creatures", len(bestiary.everything())),
                     # Both added for 0.1.1, and both for the same reason: they are the
                     # release's two headline features, and a manual that describes them
                     # without saying how many there are invites somebody to type the
                     # number in later.
                     ("backgrounds", len(backgrounds.catalogue())),
                     ("quest schemes", len(schemes.all_schemes())),
                     # Added 2026-09-16 with `rules/keepers.py`. The manual not knowing
                     # about a shipped feature is this project's own recurring defect —
                     # it did not know about the viewport for three releases — and a
                     # player who is not told that shops have people in them has no
                     # reason to talk to one.
                     ("places with a keeper", len(places.STAFFED))]:
        assert f"{n:,}" in page or str(n) in page, (
            f"the manual does not show the real {label} count ({n:,}) — it has either "
            f"drifted or gone back to a typed-in number")


def test_it_says_that_a_shop_has_somebody_in_it(page):
    """A count alone would pass while the paragraph said nothing useful. The two facts a
    player can act on are that the person is the world's own and that they persist —
    both of which are reasons to talk to them rather than to the room."""
    assert "behind the counter" in page.lower()
    assert "same smith" in page, "the manual does not say a keeper persists"


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


# --- The README's own numbers ----------------------------------------------------------

def test_the_readme_counts_what_ships_and_not_what_this_machine_has(tmp_path, settings):
    """Caught by `tools/prove_build.py` against the frozen exe, 2026-09-12.

    The packaged build reported 12 classes and 25 races; the README said 13 and 26. Both
    were true. The README's figures had been read off a development machine whose
    homebrew directory holds `storm lord.json` and `asura.json`, and `all_classes` and
    `all_races` merge homebrew over the shipped catalogue by design — so the numbers
    described that one installation and not the product.

    That is the same drift the README rewrite was meant to end, reintroduced in the act
    of ending it, and it was invisible to every test because they all run with whatever
    homebrew is lying about. This one points CAMPAIGN_DIR at an empty directory, which
    is what a fresh install actually is.
    """
    import re

    from rules import classes, races

    # `rules.classes._homebrew` reads `CAMPAIGN_DIR.parent / "homebrew"`, so the parent
    # is what has to be empty — pointing CAMPAIGN_DIR straight at `tmp_path` would leave
    # homebrew resolving to pytest's shared tmp root and pass for the wrong reason.
    fresh = tmp_path / "campaigns"
    fresh.mkdir()
    settings.CAMPAIGN_DIR = str(fresh)             # a fresh install: no homebrew at all
    shipped_classes = len(classes.all_classes())
    shipped_races = len(races.all_races())

    readme = (Path(settings.BASE_DIR) / "README.md").read_text(encoding="utf-8")
    claimed_classes = re.search(r"\*\*(\d+) classes\*\*", readme)
    claimed_races = re.search(r"\*\*(\d+) races\*\*", readme)
    assert claimed_classes and claimed_races, (
        "README.md no longer states the shipped class and race counts in the form this "
        "test reads; update both together or the number goes back to being unchecked")
    assert int(claimed_classes.group(1)) == shipped_classes, (
        f"README says {claimed_classes.group(1)} classes ship; a fresh install gets "
        f"{shipped_classes}")
    assert int(claimed_races.group(1)) == shipped_races, (
        f"README says {claimed_races.group(1)} races ship; a fresh install gets "
        f"{shipped_races}")


def test_the_readme_states_how_much_of_the_world_is_authored(tmp_path, settings):
    """Added for 0.1.1, against a sentence that had gone stale exactly the way this file
    exists to prevent: "Play is a sandbox; two scheme lines ship" was written when two
    did, and was still there at fourteen.

    The claim matters more than most. It sits under "What is not built", where a reader
    is deciding whether the world does anything on its own, and understating it by a
    factor of seven answers that question wrongly.
    """
    import re

    from rules import backgrounds, schemes

    # Both catalogues merge homebrew on top, so the count has to be taken against an
    # empty directory for the same reason the class and race counts above are — a
    # README that describes the product must not be reading this machine's overlay.
    fresh = tmp_path / "campaigns"
    fresh.mkdir()
    settings.CAMPAIGN_DIR = str(fresh)

    readme = (Path(settings.BASE_DIR) / "README.md").read_text(encoding="utf-8")
    for label, real, pattern in [
            ("quest schemes", len(schemes.shipped()), r"\*\*(\d+) quest schemes\*\*"),
            ("backgrounds", len(backgrounds.catalogue()), r"\*\*(\d+) backgrounds\*\*")]:
        found = re.search(pattern, readme)
        assert found, (
            f"README.md no longer states the {label} count in the form this test reads")
        assert int(found.group(1)) == real, (
            f"README says {found.group(1)} {label} ship; there are {real}")


def test_the_manual_counts_this_installation_including_homebrew(tmp_path, settings):
    """The opposite rule, and it is deliberate.

    The README describes the product, so it counts what ships. The manual is read by
    somebody sitting in front of *their* copy, so it counts what their copy has — a
    player who built a class should see it in the total. Pinned so the two do not get
    "corrected" into agreeing with each other.
    """
    from rules import classes

    home = tmp_path / "homebrew" / "classes"
    home.mkdir(parents=True)
    (home / "prover.json").write_text(
        '{"id": "prover", "name": "Prover", "hit_die": "d8", '
        '"bab": "three_quarter", "skill_ranks": 4, '
        '"saves": {"fort": "good", "ref": "poor", "will": "poor"}}', encoding="utf-8")
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir()
    settings.CAMPAIGN_DIR = str(campaigns)

    assert "prover" in classes.all_classes(), (
        "homebrew no longer merges into the catalogue, so the manual would under-report "
        "what this installation can actually build")
