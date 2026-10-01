"""Django settings for Pathfinder GM.

Deliberately thin. The campaign is a file overlay under the user data directory, not rows
in a database — the same file-native choice World Bible made, for the same reason: the
files are the data, and a save you can read in a text editor survives the app.
"""

from pathlib import Path

from .paths import is_frozen, resource_root, secret_key, user_data_root

BASE_DIR = resource_root()

# Local single-user desktop app: there is no deployment and no untrusted network. The
# packaged build makes a key on first run and keeps it in the user's data directory —
# the previous comment said that was already happening and it was not, so every copy of
# the exe would have shipped one literal key. Development keeps the literal, because a
# key file appearing in a developer's AppData for a `runserver` session is surprise for
# no benefit.
SECRET_KEY = secret_key() if is_frozen()     else "django-insecure-local-desktop-only-+c@#h^o_q^!j=!x1zs0ngd&x9ruj38"

# Off in the packaged build. A traceback page carries source, settings and local
# variables, and while this only ever listens on localhost, "only localhost" is a
# property of today's launcher rather than a guarantee — and the person reading a
# 500 page in a shipped game cannot act on a stack trace anyway. Development keeps it,
# because a developer reading a stack trace is the entire point of it.
DEBUG = not is_frozen()
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "world",
    "rules",
    "gm",
    "play",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
    # Before CSRF, and inert unless `desktop.py --lan` armed it. A request from off this
    # machine with no pass must be turned away at the door rather than a step inside it:
    # CSRF's answer to a stranger is a 403 about a token, which tells somebody who
    # mistyped their pass exactly the wrong thing.
    "pathfindergm.lan.TheDoor",
    "django.middleware.csrf.CsrfViewMiddleware",
    # Last, so it wraps the view and nothing else. Below CSRF deliberately: a request
    # that fails the CSRF check never reaches a campaign, so it must not take the game
    # lock and must not move the revision — a rejected probe that bumped the counter
    # would send every open device off to re-fetch a state that had not changed.
    "play.concurrency.OneGameAtATime",
]

ROOT_URLCONF = "pathfindergm.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "play" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "pathfindergm.wsgi.application"

# Unused — no models. Declared because parts of Django assume the key exists.
DATABASES = {}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Sessions are cookie-backed so there is no database and no session table to migrate.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

# --- Pathfinder GM ---------------------------------------------------------------

WORLD_EXPORT = BASE_DIR / "fixtures" / "pangrella-campaign.json"
PREGEN_PC = BASE_DIR / "fixtures" / "pc-kesst.json"
CAMPAIGN_DIR = user_data_root() / "campaigns"

# Per-role model config, mirroring World Bible's generator/proofreader split. Local is the
# default and must always be sufficient; hosted stays possible and is never required.
# `narrator` plans the turn: JSON, refs, ops, a closed vocabulary. `prose` writes the
# turn's prose after the engine has resolved it (intents first, `gm/agent.py`).
#
# The roles were split (2026-08-22) because the two jobs wanted opposite things from a
# model, and measured on identical turns they got them from different ones.
# R4C3R/qwen3-8b-heretic was roughly three times faster than llama3.1:8b and read better
# line by line, and it lost half the turns it was given — 5 of 10 against llama's 10 of
# 10 — because an 8B creative-writing tune is poor at emitting constrained JSON. The
# prose call had no JSON then, so the speed and the prose were free. It has a grammar now
# (`prompts.prose_schema`, used by `GMAgent.narrate_turn`), and since 2026-08-30 both
# seats hold the same model; the split stays so a player can still give the prose to
# something else.
MODELS = {
    # igorls/gemma-4-12B-it-heretic, measured in rather than argued in (2026-08-30): both
    # narrator audit scripts came back 12/12 clean against stock gemma4:12b's 11/12 and
    # 11/12, with no rejected intents — the schema adherence the decensoring was supposed
    # to cost never moved — at 895 and 788 characters a beat against stock's 134 and 262.
    # Stock gemma4:12b had taken the seat from llama3.1:8b two days earlier, and brought
    # two lessons with it: Gemma 4 thinks by default and spent every budget in the think
    # channel, so `think=False` rides every agent call; and its grammar compiler cannot
    # express `maxLength`, so `gm/client.py` retries once with it stripped.
    #
    # Before that, llama3.1:8b, chosen after a full playtest session on each
    # (2026-08-22). The 4B abliterated qwen read well in seven-turn harnesses and failed
    # a real session on every axis that matters: it proposed a wall-climb for "I look
    # around", carried the stale intent into a social turn, narrated whole days on the
    # player's behalf, recycled its own paragraphs verbatim across turns, and answered "I
    # draw my dagger and attack" with a fight it resolved entirely in prose — no intent
    # ever reached the engine. Speed is nothing when the model will not put the game in
    # front of the rules.
    "narrator": {"provider": "ollama", "model": "igorls/gemma-4-12B-it-heretic-GGUF:latest",
                 "host": "http://localhost:11434"},
    "prose": {"provider": "ollama", "model": "igorls/gemma-4-12B-it-heretic-GGUF:latest",
              "host": "http://localhost:11434"},
    # Second opinion, not second choice. When the narrator burns every attempt at a
    # turn — llama3.1 would occasionally refuse a schema outright, or circle one wrong
    # shape until the attempts were gone, and any narrator can — the same turn is offered
    # to this model before the player sees an error. The 4B qwen lost the narrator seat on
    # a full session (see above), but "worse narrator than llama" and "useless" are
    # different claims:
    # a rescued turn from a weaker model beats a red wall from a stronger one, and the
    # validators strip both models' output to the same checked facts either way.
    "fallback": {"provider": "ollama",
                 "model": "richardyoung/qwen3-4b-instruct-2507-abliterated",
                 "host": "http://localhost:11434"},
    # The event watcher — `gm/watcher.py`. It wakes on a daemon thread after a
    # finished turn and never blocks one: it may slip one flavour item into a freshly
    # dead actor's pockets (validated against the tables, applied only if the corpse
    # is still there and untouched), and every few turns it re-reads the GM's private
    # undercurrent note against the transcript and advances or replaces it. The
    # faction clock of `docs/architecture.md` is still unbuilt; this is the first
    # thing the role has ever actually been called for.
    #
    # The narrator's model, since 2026-08-28: the watcher moved to gemma4:12b with the
    # narrator and prose seats in one change, and to the heretic build with them on
    # 2026-08-30. It was deepseek-r1:8b before that, by choice — a reasoning model suits
    # a role that reads a log and decides what changed, the split World Bible used it for
    # (proofreader beside a generator) — and that choice is still open to anyone who
    # sets it here or on the settings page. Sharing the narrator's model keeps one model
    # resident, which matters locally, where a second model's load rather than its
    # inference is what a turn waits on.
    "watcher": {"provider": "ollama", "model": "igorls/gemma-4-12B-it-heretic-GGUF:latest",
                "host": "http://localhost:11434"},
}

# Errors reach the log whether or not DEBUG is on. Django's default logging puts
# require_debug_true in front of its console handler, so the frozen app — the one
# place a traceback is the only debuggable artefact — logged "GET / 500" and not
# one line of why. desktop.py's tee copies stderr to the logfile; this makes sure
# the traceback is on stderr in the first place.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        # `/api/alive` is four lines a minute forever — 5,760 a day against a log
        # desktop.py truncates at 2 MB. Left in, the heartbeat would push the run a bug
        # report needs off the end of the file within a week.
        "quiet_heartbeat": {"()": "pathfindergm.liveness.QuietHeartbeat"},
    },
    "handlers": {
        "stderr": {"class": "logging.StreamHandler"},
        "requests": {"class": "logging.StreamHandler",
                     "filters": ["quiet_heartbeat"]},
    },
    "loggers": {
        "django.request": {"handlers": ["stderr"], "level": "ERROR",
                           "propagate": False},
        # Django's own `django.server` handler is replaced rather than filtered in place:
        # a filter added to a handler defined in DEFAULT_LOGGING is a filter on an object
        # this dict does not own, and the merge order is not something to bet the request
        # log on.
        "django.server": {"handlers": ["requests"], "level": "INFO",
                          "propagate": False},
    },
}
