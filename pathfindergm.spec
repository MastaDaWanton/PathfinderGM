# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the one file the user installs.

Read `docs/packaging.md` beside this for what each section is for and what it cost to
learn. The short version of the two rules this file exists to obey:

  **Everything the app reads at runtime is listed here, by name.** The app resolves
  content through `settings.BASE_DIR`, which is `paths.resource_root()`, which frozen is
  `sys._MEIPASS`. A directory that is not in `datas` therefore does not fail to open — it
  reads as an *empty folder*, and the app starts, serves its pages, and has no spells in
  it. `tests/test_packaging.py` walks `content/` and fails if a directory on disk is
  missing from the tuple below, so a new content folder cannot silently drop out of the
  build the way it otherwise would.

  **Everything imported by string is listed as a hidden import.** `rules/registry.py`
  names its loaders as `"rules.spells:all_spells"` and `rules/benches.py` names its five
  crafts as `"rules.blacksmith"` and friends. PyInstaller's static analysis sees a string.
  Rather than enumerate them and let the list drift, every submodule of the four Django
  apps is collected — the whole game is ~40 modules and pulling all of them in costs
  nothing measurable, while missing one costs a bench that 404s.
"""
from PyInstaller.utils.hooks import collect_submodules

# --- data ------------------------------------------------------------------------------
#
# (source on disk, destination inside the bundle). The destinations mirror the repository
# layout exactly, because `resource_root()` returns the repo root under `runserver` and
# `_MEIPASS` when frozen, and every path in the app is written relative to that one root.
# Any divergence here would mean the app works in dev and not in the build, which is the
# failure mode this whole exercise exists to catch.

CONTENT_DIRS = [
    "bestiary",
    "classes",
    "feats",
    "rules",       # stage 8d: the hazard rows GM fiat cites (content/rules/hazards.json)
    "ingredients",
    "materials",
    "spells",
    "weapons",
    "world-classes",
]

datas = [(f"content/{name}", f"content/{name}") for name in CONTENT_DIRS]

datas += [
    # The world that ships so a fresh install has something to play, plus the three
    # pregenerated PCs `roster.pregens()` globs for.
    ("fixtures", "fixtures"),
    # Templates and static are found by Django's app-directories finders, which look
    # under `play.__path__` — `_MEIPASS/play` in the bundle. Mirroring the layout is what
    # makes `{% static %}` and `{% extends %}` resolve without a settings change.
    ("play/templates", "play/templates"),
    ("play/static", "play/static"),
    # OGL section 10: a copy of the licence must ship with every copy of the Open Game
    # Content. `play.views.licence` reads OGL.txt off `resource_root()` and returns a loud
    # 404 if it is absent, precisely so a build that lost it is not quietly distributable.
    ("OGL.txt", "."),
    ("OGL-NOTICE.md", "."),
]

# Deliberately NOT bundled, so the reasons are on the record rather than rediscovered:
#   reference/  — 2.8 MB of extracted rulebook text read only by tests and by
#                 reference/build_reference.py. No runtime code path opens it.
#   docs/       — referred to in comments and error messages by *name*, never opened.
#   tools/      — one-off content build scripts; they import Django and would drag
#                 pdfplumber-shaped dependencies into the bundle for no user-facing gain.
#   tests/      — likewise.

# --- code ------------------------------------------------------------------------------

hiddenimports = (
    collect_submodules("rules")
    + collect_submodules("play")
    + collect_submodules("gm")
    + collect_submodules("world")
    + collect_submodules("pathfindergm")
    # Django resolves these from settings strings too. The staticfiles app is the one that
    # actually bit: it is in INSTALLED_APPS, but its *finders* and the signed-cookie
    # session backend are named in settings as dotted paths and nothing imports them.
    + [
        "django.contrib.staticfiles",
        "django.contrib.staticfiles.finders",
        "django.contrib.staticfiles.views",
        "django.contrib.sessions",
        "django.contrib.sessions.backends.signed_cookies",
        "django.core.servers.basehttp",
        "django.template.backends.django",
        "django.template.context_processors",
    ]
)

excludes = [
    # Nothing in this app touches a database. Django imports the sqlite3 backend lazily,
    # and DATABASES is empty, but the exclusion is here to make the claim explicit rather
    # than to save bytes: if something starts needing the ORM, the build breaks loudly.
    "tkinter",
    "unittest",
    "pytest",
    "pdfplumber",
    "numpy",
]

a = Analysis(
    ["desktop.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PathfinderGM",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # One file, per the standing constraint. The cost is a ~2 second unpack to a temp
    # directory on every launch (23 MB of content dominates it); the benefit is that
    # "the user installs one file" stays literally true.
    runtime_tmpdir=None,
    # Kept True for this first build on purpose. A packaged app that dies before it can
    # draw a window has nowhere to say why, and the request log is the only diagnostic a
    # user could send back. Turning it off needs a log file under the user data directory
    # first — see docs/packaging.md, "What remains unproven".
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
