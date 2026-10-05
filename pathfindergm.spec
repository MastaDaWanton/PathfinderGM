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
    "backgrounds", # where a character was before turn one (rules/backgrounds.py)
    "races",       # the Core seven as documents (content/races/core.json, rules/races.py)
    "schemes",     # authored quest schemes (content/schemes, rules/schemes.py)
    "openings",    # where a campaign begins (content/openings, rules/openings.py)
    "people",      # the charts a life is rolled from (content/people, rules/lives.py)
    "hooks",       # one demonstration per hook approach (content/hooks, rules/hooks.py)
    "ingredients",
    "materials",
    "spells",
    "weapons",
    "world-classes",
    "domains",     # the domains' granted powers (content/domains, rules/domains.py)
    "companions",  # the animal companion table and animals (rules/animal_companion.py)
    "class-options",  # bloodlines, schools, rage powers… (rules/classes.py catalogues)
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

# The build stamp the home page prints, asked of git HERE — once, at build time, by a
# process that has a console — and shipped as a file. `pathfindergm.version` reads the
# file when frozen and never runs anything: the version that asked git at request time
# hung every home-page load of the Explorer-launched shell (see that module's docstring).
# Written into `build/` so the working copy is never edited by packaging.
import subprocess
from pathlib import Path

_stamp_dir = Path("build")
_stamp_dir.mkdir(exist_ok=True)
_stamp = subprocess.run(
    ["git", "log", "-1", "--format=%h %cd", "--date=format:%Y-%m-%d %H:%M"],
    capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
_stamp_text = _stamp.stdout.strip() if _stamp.returncode == 0 else ""
if not _stamp_text:
    raise SystemExit("could not read the git stamp for build-stamp.txt — "
                     "build from a checkout with git on PATH")
(_stamp_dir / "build-stamp.txt").write_text(_stamp_text + "\n", encoding="utf-8")
datas += [(str(_stamp_dir / "build-stamp.txt"), ".")]

# Deliberately NOT bundled, so the reasons are on the record rather than rediscovered:
#   reference/  — 2.8 MB of extracted rulebook text read only by tests and by
#                 reference/build_reference.py. No runtime code path opens it.
#   docs/       — referred to in comments and error messages by *name*, never opened.
#   tools/      — one-off content build scripts; they import Django and would drag
#                 pdfplumber-shaped dependencies into the bundle for no user-facing gain.
#   tests/      — likewise.

# --- code ------------------------------------------------------------------------------

# The packages whose members are found by FILENAME at runtime (`pkgutil.iter_modules`
# over the package's `__path__`, docs/fix-interfaces.md §2.0): narrator checks, brief
# sections, after-the-beat steps. Nothing imports a member by name — that is the point of
# them — so static analysis never sees one, and a member missing from the bundle is not
# an error: the frozen app simply discovers nothing and checks nothing. The blanket
# `collect_submodules("gm")`/`("play")` below already reach them; they are named here as
# well so the claim is written down and `tests/test_s1_check_registry.py` can hold the
# spec to it. A package that does not exist yet (each lands on its own branch) is
# skipped rather than breaking the build: its `__init__.py` is looked for on disk, not
# imported, so the spec never has to import Django to decide.
DISCOVERED_PACKAGES = ("gm.checks", "gm.brief", "play.aftermath")

discovered = []
for _package in DISCOVERED_PACKAGES:
    if Path(*_package.split("."), "__init__.py").is_file():
        discovered += [_package] + collect_submodules(_package)

hiddenimports = (
    collect_submodules("rules")
    + collect_submodules("play")
    + collect_submodules("gm")
    + collect_submodules("world")
    + collect_submodules("pathfindergm")
    + discovered
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
