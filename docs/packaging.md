# Packaging

How Pathfinder GM becomes the one file a person installs, what the build contains and why,
and — the part that is worth more than the rest of this document — which of CLAUDE.md's
packaging rules actually caught something on the first real build.

First built 2026-08-24 against PyInstaller 6.20.0, Python 3.13.7, Django 6.0.6, Windows 11.

---

## Building

```
pip install pyinstaller
python -m PyInstaller --noconfirm --clean pathfindergm.spec
```

Output: `dist/PathfinderGM.exe`, **36 MB**, one file, no installer, no side directory. A
build takes about 100 seconds after the first one (the first is ~145s while PyInstaller
caches its analysis). `build/` and `dist/` are both gitignored; `pathfindergm.spec` is
not — `.gitignore` excludes `*.spec` and then re-includes this one by name, because the
spec is the only record of which content directories ship.

### Running it

Double-click. That is the whole procedure, which is the standing constraint. The exe
starts a server on `127.0.0.1:8917` and opens the default browser at it. A console window
stays open behind the browser showing the request log and where the user's saves live;
closing that window stops the game.

Two flags exist, and neither is for the player:

| flag | for |
|---|---|
| `--check` | Print what this build can actually see — every content directory and its file count, both fixtures, the licence, the spell count, static, templates — and exit non-zero if any of it is missing. This is what proves a build. |
| `--no-browser` | Serve without opening a browser, so a script can drive it. |

`PATHFINDER_GM_DATA` overrides the user data directory. That is the mechanism CLAUDE.md's
"run the built executable against a throwaway data directory" rule depends on, so it is not
a debug convenience — without it a packaging fix cannot be proved at all.

---

## What the spec bundles, and why

Everything the app reads at runtime resolves through `settings.BASE_DIR`, which is
`pathfindergm.paths.resource_root()`, which frozen is `sys._MEIPASS`. The destinations in
`datas` therefore mirror the repository layout exactly — any divergence means the app works
under `runserver` and not in the build.

| bundled | read by | why it cannot be left out |
|---|---|---|
| `content/bestiary`, `classes`, `feats`, `ingredients`, `materials`, `spells`, `weapons`, `world-classes` | `rules/*` via `settings.BASE_DIR` | 23 MB, 26 JSON files. A missing one reads as an **empty folder**, not an error — see below. |
| `fixtures/` | `library.shipped_dir()`, `roster.pregens()` | The world that ships so a fresh install has something to play, plus the three pregen PCs. |
| `play/templates/` | Django's template loaders | Both `DIRS` and `APP_DIRS` point here. |
| `play/static/` | `staticfiles` app-directories finder, via `play.__path__` | 3.4 MB of leather, clasps, bosses and `dice3d.js`. |
| `OGL.txt`, `OGL-NOTICE.md` | `play.views.licence` | OGL section 10 requires the licence to ship with every copy of the Open Game Content. A build without it must not be distributed. |

**Deliberately not bundled**, so the reasoning is on the record rather than rediscovered:
`reference/` (2.8 MB of extracted rulebook text, read only by tests and by
`reference/build_reference.py`; no runtime path opens it), `docs/` (named in comments and
error messages, never opened), `tools/` and `tests/`.

### Hidden imports

`rules/registry.py` names its loaders as strings — `"rules.spells:all_spells"`,
`"rules.bestiary:everything"`, `"rules.creature_effects:derive"` and six more.
`rules/benches.py` routes five crafts and one mode the same way. `play/craft_views.py`
keeps a *second* copy of that routing table in `_MATERIALS_OF`. PyInstaller's static
analysis sees string literals and bundles nothing.

Rather than enumerate them and let the list drift, the spec collects every submodule of
`rules`, `play`, `gm`, `world` and `pathfindergm`. The whole game is about forty modules;
pulling all of them in costs nothing measurable, and missing one costs a bench that 404s.

The failure this prevents is quiet in a specific and nasty way: `registry.shipped()`
catches every exception and returns `{}` — deliberately, so one broken kind cannot take the
homebrew page down — so a module absent from the bundle presents as *a bench with no
shipped content*, indistinguishable from a user who has authored nothing.

---

## Frozen-path traps found, and how each was fixed

### The paths helper was already right, and that is worth saying

`pathfindergm/paths.py` predates this build and its shape held up:

- `resource_root()` — `sys._MEIPASS` when frozen, the repo root otherwise. Bundled
  read-only files genuinely do live inside the bundle, so `_MEIPASS` is the correct answer
  and the one place `__file__` legitimately appears is its not-frozen branch.
- `install_root()` — `Path(sys.executable).parent`. Where the app actually *is*.
- `user_data_root()` — `%LOCALAPPDATA%\PathfinderGM`, overridable by env var.

Frozen, the first two are genuinely different directories, which is the whole reason
CLAUDE.md's rule exists. Measured on the real exe:

```
resource_root C:\Users\natha\AppData\Local\Temp\_MEI180162
install_root  H:\coding\PathfinderGM\dist
```

Unfrozen they are both the repo root — which is exactly why no dev run can tell you
whether the right one was used. `tests/test_packaging.py` now guards this rather than
merely asserting it, including that no shipped module anchors a path on `__file__`
(only `tools/`, `reference/` and `tests/` do, and none of them are in the bundle).

### Static files were not served at all

`runserver` inserts the static route itself. The frozen exe does not run `runserver`, and
nothing in `pathfindergm/urls.py` served `/static/`. The packaged app would have loaded
every page with no backgrounds, no fonts and no dice — **silently**, because a 404 on a CSS
background image is not an error the user or the log will ever surface.

Fixed with an explicit route to `django.contrib.staticfiles.views.serve` with
`insecure=True` (the view refuses to serve when `DEBUG` is off otherwise; this is a
single-user process bound to `127.0.0.1`). `collectstatic` was rejected as the alternative
because it puts derived files outside the install root, which is the exact shape the
stale-cache rule warns about.

Verified on the real exe: `/static/js/dice3d.js` → 200, 25,182 bytes;
`/static/img/leather-tile.jpg` → 200, 157,383 bytes with a JPEG magic number; and a real
browser fetching the home page pulled `grimoire-leather.jpg` (735,968 bytes),
`boss-{top,bottom,left,right}.png` and all four clasps, every one a 200.

### The browser never opened — found only by launching the packaged build

`_open_browser_when_up` parsed the port back out of `"http://127.0.0.1:8917/"` with
`url.rsplit(":", 1)[1]`, which is `"8917/"`, and `int()` raised `ValueError` inside a
daemon thread.

This is the rule collecting. The server itself was fine: **all seventeen HTTP checks passed
against that build.** Home page, world import, character creation, play page, five craft
shelves, 3,040 spells — every one green, on a build whose single user-facing job (open
without being told to) was broken. Nothing but running the packaged exe with the browser
path enabled would have shown it. The port is passed in explicitly now, and
`webbrowser.open`'s return value is reported rather than discarded.

### Two copies of the app bound the same port

Django's `WSGIServer` defaults `allow_reuse_address=True`. On Windows `SO_REUSEADDR` does
not mean the Unix "reuse a socket in TIME_WAIT" — it means "bind even though somebody else
already has this port", and the two servers then split incoming connections between them at
random. The fallback-to-a-free-port branch never ran.

Fixed by passing `allow_reuse_address=False`, which makes the second bind raise, which is
what makes the fallback work. Verified on the real exe: two instances launched, first got
`http://127.0.0.1:8917/`, second got `http://127.0.0.1:49390/`, each with its own unpack
directory and its own data directory.

### The startup banner never printed

Frozen, stdout is a pipe rather than a console whenever anything captures it, so Python
block-buffers it and nothing appears until 8 KB accumulate — which for six lines is never.
The first packaged run logged Django's requests (they go to stderr, which is unbuffered)
and not one line of the banner that tells the user where their saves live. Every line of it
now passes `flush=True`.

### `runserver` was never a candidate

Worth recording as a trap avoided rather than one hit. The management command brings the
autoreloader, which re-executes `sys.executable` with Django's own argv; frozen,
`sys.executable` *is* the app, so the reloader relaunches the whole desktop app — the
classic frozen-Django fork bomb of windows. The entry point uses `ThreadedWSGIServer`
directly, which is the same server `runserver` wraps minus the reloader and the command
layer, and `tests/test_packaging.py` fails if `desktop.py` ever reaches for
`execute_from_command_line` or `call_command`.

---

## The stale-cache rule: nothing is cached, and that is the finding

CLAUDE.md's second packaging rule is about **derived** files outside the install directory.
As of this build there are none.

Everything under `%LOCALAPPDATA%\PathfinderGM\` is authored or chosen by the user:
`campaigns/` and `characters/` are saves, `worlds/` holds exports the user imported,
`homebrew/` holds what they built in the builder, `models.json` and the house rules are
settings. None of it is computed from shipped content, so none of it can go stale against a
newer build the way World Bible's five-day-old stylesheet did.

The one cache in the app is `world.loader._cached`: an `lru_cache` keyed on the source
file's mtime, in memory, gone when the process exits.

`paths.CACHE_VERSION` therefore exists and is **unused**, and its comment now says so. It
previously claimed that "every derived file we write outside the install directory carries
this stamp", which was false in a build where no file did — a comment promising a guarantee
nobody implemented is worse than no comment, because the next person reads it as done.
`tests/test_packaging.py::test_nothing_derived_is_written_into_the_user_data_directory`
pins both halves: the loader's cache is still in memory, and the note still admits nothing
uses the constant. The moment something is derived to disk there, both assertions fail and
the stamp has to be written and compared before the suite goes green.

---

## What was verified against the real exe

The 2026-08-24 verification below was a one-off script; it is now a committed tool —
`python tools/prove_build.py` launches `dist/PathfinderGM.exe` against a fresh throwaway
data directory and drives it over HTTP, importing nothing from the app. Re-run on
2026-08-26 against a rebuild carrying the week's changes: **16/16 clean**, including the
merchant-gated trade panel, the out-of-combat combat-panel gates, the player-boundary
hand-back (which runs before the model, so the check needs no Ollama), the full forage
suspend/resume round trip (Survival prompt with breakdown → garbage face refused with
the roll intact → the player's face resolving the session), and the world-upload cache
surviving a broken overwrite inside one mtime tick.

All of this against `dist/PathfinderGM.exe` with `PATHFINDER_GM_DATA` pointed at a fresh
throwaway directory, driven over HTTP by a script that imports nothing from the app.

| check | result |
|---|---|
| `--check` self-report | exit 0; all 8 content directories present with their file counts; both fixtures; both licence files |
| home page | 200, 103,770 bytes, shipped Pangrella world listed and playable |
| static JS | 200, 25,182 bytes |
| static image | 200, 157,383 bytes, JPEG magic number |
| world import from `fixtures/` | 200, "Pangrella" landed on the shelf as a non-shipped, playable world; file written to `<data>/worlds/` |
| creation options | 200, 7 races, 12 classes |
| character creation | 200, `frozen-testsubject` created and a campaign begun; files written to `<data>/characters/` and `<data>/campaigns/` |
| play page | 200, 158,618 bytes, character's name in the HTML |
| sheet API | 200, Frozen Testsubject · dwarf Fighter 1 · AC 17 · 35 skills |
| craft page | 200, 101,606 bytes |
| craft shelf: herbalism | 161 materials (Acacia, Aconite, Adder's-Tongue…) |
| craft shelf: alchemy | 137 materials (Adamantine Crucible, Adder Venom Gland…) |
| craft shelf: blacksmithing | 112 materials (Abysium, Abysium Ore, Abyssal Salt…) |
| craft shelf: leatherworking | 127 materials (Adamantine Buckles, Ankheg Shell Leather…) |
| craft shelf: enchanting | 117 materials (Adamantine Dust, Amethyst Focus…) |
| spell list | **3,040** unpaged (the endpoint defaults to `limit=120`); `/api/spells/fireball` returns evocation, long range, and its scaling |
| class builder page | 200, 98,327 bytes |
| licence page | 200, 6,586 bytes, OGL text intact |
| browser auto-open | a real browser loaded the page and fetched every static asset |
| port fallback | second instance bound 49390 |
| saves land outside the bundle | confirmed under the throwaway root, not under `_MEI…` |

Two 404s in that browser log, both honest and neither a packaging regression:

- `/static/fonts/Cinzel-Regular.woff2` — the font file is **not in the repository**.
  `play/static/fonts/` contains only a README. The CSS has a `local("Cinzel")` fallback, so
  the page renders in whatever the system has. This is a pre-existing content gap, not
  something the build lost.
- `/favicon.ico` — there isn't one.

---

## What remains unproven

- **Only ever built and run on the machine it was built on.** Never installed onto a clean
  Windows box with no Python, which is the only test that proves the "no `pip install`"
  half of the constraint. A missing VC++ runtime or a Defender SmartScreen prompt on an
  unsigned binary would both appear there and nowhere else.
- **The exe is unsigned.** SmartScreen will warn on first run on any machine that did not
  build it.
- **`console=True`.** The window is deliberate for this first build: an app that dies before
  it can draw anything has nowhere to say why, and the request log is the only diagnostic a
  user could send back. Turning it off needs a log file under the user data directory
  first — and note that the moment such a file exists, it is a derived file outside the
  install directory and the `CACHE_VERSION` question above stops being theoretical.
- **`DEBUG = True` in the packaged build.** Tracebacks are rendered into the browser. For a
  process bound to `127.0.0.1` with no untrusted client this is a diagnostic aid rather
  than a hole, but it is a decision nobody has explicitly taken for the shipped artifact.
  The static route already carries `insecure=True` so it will survive `DEBUG` being turned
  off; nothing else has been checked against that.
- **`SECRET_KEY`.** The comment in `settings.py` says it "is regenerated per install in the
  packaged build". It is not — the literal ships. Sessions are signed cookies, so the
  consequence is that every install shares a signing key. Out of scope for this task, named
  here because the comment currently claims otherwise.
- **No Ollama in the loop.** Every check above is the rules engine and the content layer.
  The GM agent talks to `localhost:11434`; whether the frozen build's `urllib` reaches it,
  and what it does when nothing is listening, is untested.
- **Startup cost not measured properly.** A one-file build unpacks 36 MB to a temp
  directory on every launch. It was a few seconds by observation, never timed.
- **Cross-platform.** Windows only. `paths.py` has macOS and Linux branches; neither has
  been run, let alone packaged.
