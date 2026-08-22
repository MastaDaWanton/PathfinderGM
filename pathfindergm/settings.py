"""Django settings for Pathfinder GM.

Deliberately thin. The campaign is a file overlay under the user data directory, not rows
in a database — the same file-native choice World Bible made, for the same reason: the
files are the data, and a save you can read in a text editor survives the app.
"""

from pathlib import Path

from .paths import resource_root, user_data_root

BASE_DIR = resource_root()

# Local single-user desktop app: there is no deployment and no untrusted network. The key
# is regenerated per install in the packaged build; this literal is the dev value.
SECRET_KEY = "django-insecure-local-desktop-only-+c@#h^o_q^!j=!x1zs0ngd&x9ruj38"

DEBUG = True
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
    "django.middleware.csrf.CsrfViewMiddleware",
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
# `narrator` plans the turn: JSON, refs, ops, a closed vocabulary. `prose` only writes the
# consequence sentence, which has no schema to get wrong at all.
#
# They are split because the two jobs want opposite things from a model, and measured on
# identical turns they get them from different ones. R4C3R/qwen3-8b-heretic is roughly
# three times faster than llama3.1:8b and reads better line by line, and it lost half the
# turns it was given — 5 of 10 against llama's 10 of 10 — because an 8B creative-writing
# tune is poor at emitting constrained JSON. On call 2 there is no JSON, so none of that
# applies and the speed and the prose are free.
#
# Anyone who prefers one model everywhere can set both to the same thing.
MODELS = {
    "narrator": {"provider": "ollama", "model": "llama3.1:8b", "host": "http://localhost:11434"},
    "prose": {"provider": "ollama", "model": "llama3.1:8b", "host": "http://localhost:11434"},
    # RESERVED, AND CURRENTLY WIRED TO NOTHING. The world-state agent of
    # `docs/architecture.md` — the cheap model that would watch play, move factions
    # between scenes and turn a burned bridge into a hook — has not been built. There is
    # no event queue for it to read (intent-protocol.md §8 describes one; nothing emits
    # to it and nothing consumes it), so this row configures a model that is never
    # loaded and never called. Kept because the role is a settled design decision and
    # deleting it would lose that; labelled because a configurable model that silently
    # does nothing reads exactly like a feature that is running.
    "watcher": {"provider": "ollama", "model": "llama3.1:8b", "host": "http://localhost:11434"},
}
