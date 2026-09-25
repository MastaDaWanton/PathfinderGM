"""Test setup.

Django is configured here rather than through pytest-django, because the rules engine and
the world loader do not touch the ORM and the app has no models — one fewer dependency for
PyInstaller to be told about, which is a real cost in the frozen build.

Tests run from the repository root so that the fixture paths in them are the same paths a
person would type.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Campaign saves must never land in the real user data directory during a test run.
# Assigned, not `setdefault`: a shell that had exported PATHFINDER_GM_DATA for a live
# probe (the scratchpad data dirs the live checks use) would otherwise have pointed the
# whole suite — house-rule deletes and all — at that directory.
#
# One directory per pytest-xdist worker (`PYTEST_XDIST_WORKER` is gw0, gw1, ...; "main"
# without xdist), because every worker imports this file: with one shared directory,
# each worker's start-of-run wipe below would delete the others' data mid-run, and the
# house-rules file every test resets would be one file raced by all of them.
DATA = ROOT / ".test-data" / os.environ.get("PYTEST_XDIST_WORKER", "main")
os.environ["PATHFINDER_GM_DATA"] = str(DATA)

# Emptied at the start of every run, before Django reads anything from it. Measured
# 2026-09-25: it held 456 files left by earlier runs — characters, campaigns and their
# backups — and a test that reads the shelf or the house-rules file read whatever the
# last run left (the `point_buy: 0` leak of 2026-09-08 was exactly that). Ignored by git;
# nothing in it is anybody's. Only this worker's own directory.
import shutil as _shutil  # noqa: E402

_shutil.rmtree(DATA, ignore_errors=True)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

import pytest  # noqa: E402
from django.conf import settings  # noqa: E402
from django.test.signals import setting_changed  # noqa: E402

# Every module that caches shipped content merged with a homebrew overlay read from
# under CAMPAIGN_DIR. Each holds its catalogue in a module-level `_NAME = None` and
# fills it on first use, so a cache filled while one test pointed CAMPAIGN_DIR at its
# own tmp_path is still holding that test's homebrew when the next one asks.
#
# Hand-listed and mechanically checked: `test_every_content_cache_is_isolated` walks
# rules/ for the declaration pattern and fails if this tuple has drifted, which is the
# same arrangement `test_packaging.py` uses for the spec's content directories.
_CACHED = (
    "rules.alchemist", "rules.backgrounds", "rules.bestiary", "rules.blacksmith", "rules.classes",
    "rules.enchanter", "rules.feats", "rules.hazards", "rules.ingredients",
    "rules.leatherworker",
    "rules.magicitem", "rules.market", "rules.spells", "rules.weapons",
    "rules.worldclass",
)


def clear_content_caches() -> None:
    """Drop every content cache, so the next read rebuilds against the current dir.

    A cache is found by its own declaration — `_ALL: dict[str, Spell] | None = None` —
    rather than by matching upper-case names, because `rules/spells.py` alone holds
    eight module-level `_UPPER` dicts that are constants (`_RANGE_BANDS`, `_SAVES`,
    `_ENERGY_WORDS`) and nulling those breaks the module outright. The optional
    annotation is exactly what separates "filled on first use" from "written down once".

    Caches with a companion (`bestiary._INDEX` beside `_IMPORTED`, `feats._META` beside
    `_ALL`) need no entry: their loader rebuilds both under one `global`, keyed on the
    annotated one.
    """
    import importlib
    import re
    import sys

    for name in _CACHED:
        mod = sys.modules.get(name) or importlib.import_module(name)
        for attr, annotation in getattr(mod, "__annotations__", {}).items():
            if re.fullmatch(r"_[A-Z][A-Z_]*", attr) and "None" in str(annotation):
                setattr(mod, attr, None)


@pytest.fixture(autouse=True)
def _no_test_waits_on_the_written_opening(monkeypatch):
    """Starting a campaign asks the prose model to write the opening. Measured the
    day it landed: 166 tests start one, and with Ollama up the two-minute suite ran
    past ten minutes at ten seconds a call. The template is what every test that
    is not about the written opening gets; `tests/test_opening_prose.py` turns the
    model back on and stubs the client."""
    from play import opening_prose

    monkeypatch.setattr(opening_prose, "ENABLED", False)
    # And the quest schemes, for the same reason: "The lost thing" opens at any
    # market, which a test about hit points did not ask for. tests/test_schemes.py
    # turns it back on.
    from rules import schemes as schemes_mod

    monkeypatch.setattr(schemes_mod, "ENABLED", False)


@pytest.fixture(autouse=True)
def _the_model_gate_is_open_unless_a_test_shuts_it(monkeypatch):
    """`/api/start` and `/api/resume` ask Ollama whether it can answer before they let
    anybody through. Left live, that makes the suite's result depend on whether Ollama
    happens to be running on the machine — 166 tests start a campaign, and every one of
    them would pass at a desk with the daemon up and fail in a fresh checkout, which is
    the worst shape a test failure can have.

    The probe is stubbed rather than the gate, so the *gate itself* still runs on every
    one of those tests: a mistake in `_model_gate` that refuses a healthy machine is
    still caught here. `tests/test_preflight.py` and `test_home.py` shut it deliberately
    to check the refusals."""
    from gm import client as gm_client
    from play import preflight

    def answers_with_whatever_is_configured(*_a, **_kw):
        # Computed per call, not once at setup. A test that overrides CAMPAIGN_DIR and
        # writes its own model settings changes what `needs()` asks for, and a list
        # captured at fixture time would then read as "the model is missing" and refuse
        # a door the test was not testing.
        return gm_client.Probe(True, installed=tuple(n.model for n in preflight.needs()))

    monkeypatch.setattr(gm_client, "probe", answers_with_whatever_is_configured)


# --- the three fixtures pytest-django used to lend -----------------------------------------
#
# requirements.txt says the tests configure Django themselves rather than pulling in
# pytest-django, and the module docstring above says why. Measured 2026-09-25: 26 test
# files asked for pytest-django's `client`, `settings` or `db` anyway, and passed only
# because the plugin happened to be installed on this machine — on a checkout built from
# requirements.txt all 26 would have errored with "fixture 'client' not found". pytest.ini
# now carries `-p no:django`, so the plugin cannot be leaned on silently again, and these
# are the three it was lending.


@pytest.fixture
def client():
    """A Django test client. Files that need a campaign dir of their own define their
    own `client` fixture, which overrides this one."""
    from django.test import Client

    return Client()


class _Settings:
    """`settings.X = y` inside a test, undone at teardown — pytest-django's contract.

    Each assignment goes through `override_settings`, so Django announces it with
    `setting_changed`, and `_cache_follows_the_directory` below drops the content caches
    when CAMPAIGN_DIR moves, exactly as it does for the context manager.
    """

    def __init__(self):
        object.__setattr__(self, "_undo", [])

    def __getattr__(self, name):
        return getattr(settings, name)

    def __setattr__(self, name, value):
        from django.test import override_settings

        o = override_settings(**{name: value})
        o.enable()
        self._undo.append(o)

    def __delattr__(self, name):
        from django.test.utils import override_settings

        o = override_settings()
        o.enable()
        delattr(settings, name)
        self._undo.append(o)

    def finalize(self):
        while self._undo:
            self._undo.pop().disable()


# Registered under pytest-django's name, defined under another so it does not shadow the
# module-level `settings` this file reads.
@pytest.fixture(name="settings")
def _settings_fixture():
    wrapper = _Settings()
    yield wrapper
    wrapper.finalize()


@pytest.fixture(name="db")
def _no_database():
    """The app has no models and no ORM; a test asking for `db` asked for nothing."""
    return None


@pytest.fixture(autouse=True)
def _no_test_reaches_a_live_model(request, monkeypatch):
    """No test talks to Ollama unless it says so with `@pytest.mark.live_model`.

    Measured 2026-09-25 with a connection recorder over the 49 files that start a
    campaign: three tests reached the live model synchronously —
    `test_a_free_action_does_not_hand_the_round_to_the_enemy` (4 calls, the prose) and
    two in `test_combat_panel.py` (the thug's `npc_turn`, 6 and 2 calls). With Ollama up
    the model decided the outcome: the free-action test flaked on 2026-09-20 because the
    real narrator invented a person whose initiative beat the player's. With Ollama down
    each call still cost ~2 s, the time Windows takes to refuse a localhost connection —
    they were the three slowest tests in the suite. And every GET of the shelf page
    warmed two models in background threads (22 connections across 10 files), so a test
    run loaded the narrator into VRAM.

    `chat` raises `ModelUnavailable`, the app's own "no model" path, so a test that did
    not stub the model exercises the fallback the player sees with Ollama down, every
    run, instead of whichever answer the model felt like. Tests that stub `chat`
    themselves (`monkeypatch.setattr(client, "chat", fake)`) replace this, because they
    run after it.
    """
    if request.node.get_closest_marker("live_model"):
        return
    import urllib.error

    from gm import client as gm_client

    # The TRANSPORT is refused, not `chat`: the first cut replaced `chat` and seven tests
    # of `chat` itself failed — the hosted-provider routing, the missing-key refusal, the
    # dropped connection — because they fake `urlopen` and need the real function above
    # it. Every one of them stubs `urlopen` after this runs, so theirs wins.
    # Only the model's door and the outside world: a test that serves the app on a
    # loopback port and fetches its own pages (test_packaging) is not talking to a model.
    from urllib.parse import urlsplit

    real_urlopen = gm_client.urllib.request.urlopen

    def no_model(req, *a, **kw):
        url = str(getattr(req, "full_url", req))
        parts = urlsplit(url)
        local = parts.hostname in ("127.0.0.1", "localhost", "::1")
        if local and parts.port != 11434:
            return real_urlopen(req, *a, **kw)
        raise urllib.error.URLError(
            f"tests do not reach a live model ({url}); mark the test live_model or "
            f"stub gm.client.chat")

    monkeypatch.setattr(gm_client.urllib.request, "urlopen", no_model)
    monkeypatch.setattr(gm_client, "warm", lambda *_a, **_kw: False)


@pytest.fixture(autouse=True)
def _unseeded_dice_are_seeded_per_test(request, monkeypatch):
    """A `Dice()` with no seed draws its seed from a stream fixed by the test's own id.

    `begin_with()` takes no seed and `Engine` falls back to `Dice(None)`: 61 test calls
    to `begin_with` and every Client-driven `/api/start` rolled from the clock, so a
    test's initiative, hits and damage differed run to run and a d20 could decide
    whether it passed — the 2026-09-20 flake was exactly that. Keyed on the node id
    (crc32, not `hash`, which Python salts per process), so a test rolls the same dice
    whatever ran before it, and each unseeded `Dice` inside one test still gets its own
    seed, so a test that builds several is not handed the same rolls twice.
    """
    import random
    import zlib

    from rules import dice as dice_mod

    stream = random.Random(zlib.crc32(request.node.nodeid.encode("utf-8")))
    original = dice_mod.Dice.__init__

    def seeded(self, seed=None):
        original(self, stream.randrange(2 ** 32) if seed is None else seed)

    monkeypatch.setattr(dice_mod.Dice, "__init__", seeded)


@pytest.fixture(autouse=True)
def _house_rules_start_at_the_defaults():
    """Every test begins with the shipped rules, whatever the last one chose.

    `.test-data/` is a real directory that survives between runs, and house rules are
    a file in it, so a test that sets one leaves it set for every run afterwards.
    Measured 2026-09-08: an earlier session had left `point_buy: 0` — Unlimited — in
    that file, and `test_creation.py::test_the_point_budget_is_a_wall` then failed on
    a clean checkout of the code, because there is no wall when the budget is
    unlimited. The failure had nothing to do with the change being tested, and
    `test_houserules.py` asserting the default budget of 20 was one run away from the
    same fate.

    Same class as `_campaign_dir_never_leaks` below: a real regression cannot be told
    from a leak, and a suite whose result depends on how the player last set their
    game is not a gate at all.
    """
    from rules import houserules

    def clear():
        try:
            houserules._path().unlink(missing_ok=True)
        except OSError:
            pass

    clear()
    yield
    clear()


@pytest.fixture(autouse=True)
def _campaign_dir_never_leaks():
    """No test may leave CAMPAIGN_DIR pointing somewhere the next one can see.

    Sixteen tests assign `settings.CAMPAIGN_DIR = str(tmp_path)` outright rather than
    through `override_settings`, and never put it back — so every test that ran after
    one of them resolved house rules and homebrew against a directory pytest had
    already deleted, and any content cache filled in the meantime kept that test's
    homebrew for the rest of the session. That is a whole class of order-dependent
    failure, and it makes the suite unusable as the gate the compliance work is judged
    by: a real regression cannot be told from a leak.

    Restoring is not enough on its own — a cache filled under the borrowed directory
    outlives the setting — so the caches are dropped whenever the directory moved.
    """
    before = settings.CAMPAIGN_DIR
    yield
    if settings.CAMPAIGN_DIR != before:
        settings.CAMPAIGN_DIR = before
        clear_content_caches()


def _cache_follows_the_directory(sender, setting, **kwargs):
    """`override_settings` is honest about CAMPAIGN_DIR moving; the caches were not.

    Django announces the change on the way in and on the way out, so this is the one
    place both directions are covered — including the tests that use the context
    manager correctly and still shared a stale catalogue with their neighbours.
    """
    if setting == "CAMPAIGN_DIR":
        clear_content_caches()


setting_changed.connect(_cache_follows_the_directory)


def pytest_sessionfinish(session, exitstatus):
    """The shared catalogues came through the run untouched.

    `rules.pristine` keeps the no-homebrew bestiary, spells, feats and classes for the
    whole process (2026-09-25), so a test that mutated an entry would leak into every
    test after it — the one cost of not rebuilding. Each is rebuilt fresh here and
    compared; a difference fails the run and names the catalogue.
    """
    from rules import pristine

    changed = [name for name, build in pristine._BUILDERS.items()
               if build() != pristine._MEMO.get(name)]
    if changed:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(
                f"A test mutated a shared catalogue ({', '.join(changed)}): "
                f"rules.pristine hands the same object to every test.", red=True)
        session.exitstatus = 1
