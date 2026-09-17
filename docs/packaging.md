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

Output: `dist/PathfinderGM.exe`, **37 MB** at 0.1.6, one file, no installer, no side
directory. A build takes about 100 seconds after the first one (the first is ~145s
while PyInstaller caches its analysis). `build/` and `dist/` are both gitignored; `pathfindergm.spec` is
not — `.gitignore` excludes `*.spec` and then re-includes this one by name, because the
spec is the only record of which content directories ship.

### Running it

Double-click. That is the whole procedure, which is the standing constraint. The exe
starts a server on `127.0.0.1:8917` and opens the default browser at it. A console window
stays open behind the browser showing the request log and where the user's saves live;
closing that window stops the game. Closing the *browser* window also stops it, about
three minutes later — see "The server outlived the browser by four hours" below for why
that sentence had to be added.

Two flags exist, and neither is for the player:

| flag | for |
|---|---|
| `--check` | Print what this build can actually see — every content directory and its file count, both fixtures, the licence, the spell count, static, templates — and exit non-zero if any of it is missing. This is what proves a build. |
| `--no-browser` | Serve without opening a browser, so a script can drive it. |

`PATHFINDER_GM_DATA` overrides the user data directory. That is the mechanism CLAUDE.md's
"run the built executable against a throwaway data directory" rule depends on, so it is not
a debug convenience — without it a packaging fix cannot be proved at all.
`PATHFINDER_GM_IDLE_GRACE` overrides the idle shutdown below, for the same reason and with
the same justification: the check that proves it watches the real exe exit, and at the
shipped 180 seconds that check costs three minutes of wall clock and gets commented out.

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

- `/static/fonts/Cinzel-Regular.woff2` — the font file was **not in the repository**.
  `play/static/fonts/` contained only a README. The CSS has a `local("Cinzel")` fallback, so
  the page rendered in whatever the system had. This was a pre-existing content gap, not
  something the build lost. **Fixed 2026-09-10**: both weights are committed under
  `play/static/fonts/`, regenerated by `tools/build_fonts.py` from upstream's variable
  font, with `OFL.txt` beside them — `play/static` already ships whole, so the spec did
  not change. `tests/test_fonts.py` now fails if any `{% static %}` reference in any
  template points at a file that is not there, which is the general form of this 404.
- `/favicon.ico` — there isn't one.

---

## The desktop shell (2026-08-26)

`electron/` wraps the exe in the app window the architecture doc always intended,
ported from World Bible's shell and deliberately thinner (no auto-updater — there is no
release pipeline to update from; no quit guard — a turn in flight costs one unanswered
sentence, not an hour of generation). Electron owns the window; the exe owns everything
else.

The contracts between them, all landed exe-side first and pinned by `prove_build.py`
before any JavaScript existed:

- **`PATHFINDERGM_READY <url>`** on stdout after bind — the line the shell waits for,
  carrying the real port (the free-port fallback means it cannot assume 8917).
- **`--watch-stdin`** — stdin closing is how the shell says stop; `server.shutdown()`
  lets the request in flight finish and removes the portfile, which is what marks the
  exit as clean. The shell's delayed `taskkill /T` is the axe for a backend that never
  noticed — tree-wide, because `kill()` alone orphans the PyInstaller child, the exact
  port-holding ghost the prove harness once left behind.
- **`<data>/server.json`** — port, url and pid, written atomically after bind, deleted
  on clean shutdown. The pid is the PyInstaller *child* (the process holding the port),
  not the bootloader a launcher spawned — the prover measured the difference the first
  time it looked.
- **`<data>/logs/pathfindergm.log`** — the banner and request log, teed rather than
  redirected (the console is still the unwrapped build's quit affordance), appended
  across launches with a dated header, truncated at 2 MB. Runtime output like a save,
  not a derived cache — nothing reads it back, so it carries no `CACHE_VERSION`.

`tools/prove_shell.py` runs the lifecycle a person cannot see failing: shell up →
portfile appears with a live pid → the URL answers → kill the shell's tree → **no
backend survives**. Green in both dev mode (`electron .` over this machine's Python)
and against the electron-builder output. `npm run dist` in `electron/` builds
`release/Pathfinder-GM-Setup-0.1.6.exe` (115 MB NSIS installer, backend exe bundled as
an extraResource).

## The server outlived the browser by four hours (2026-09-01)

The one that cost the most so far, because neither symptom named the cause.

`dist\PathfinderGM.exe` was double-clicked at **10:35:08** and played until **12:01:35**,
where the log records `Broken pipe from ('127.0.0.1', 49967)` — the browser going away. It
was still serving at **16:20**. Two processes, **27840** and **30176**, held
`127.0.0.1:8917` and an exclusive handle on the `.exe` they were running from. What that
looked like from two tools away:

- `python -m PyInstaller pathfindergm.spec --noconfirm` failed with
  `PermissionError: [WinError 5] Access is denied` — the held handle on its own output.
- `tests/test_packaging.py::test_the_launcher_falls_back_to_a_free_port` failed — it binds
  8917 and asserts the first bind gets the preferred port.

Both went away the moment the processes were killed.

**The two processes were not the bug.** Nine seconds apart looked exactly like the
"bound 8917 twice" defect that same test documents. Reproduced against the identical exe:
parent **31548** spawns child **30748** nineteen seconds later, same command line, and
`server.json` carries the *child's* pid. A one-file build is a bootloader that unpacks
38 MB and then runs the app as a child. Two processes is what one running copy looks like,
and the gap is the unpack.

**The bug was that closing a browser window tells a server nothing.** A WSGI server learns
that no request arrived; it never learns that its last client left, and a player who is
reading looks identical. The console window has always been the documented stop, and the
window a player closes is the browser's. The Electron shell has a real answer to this
(stdin closes, the backend shuts down cleanly) and the shell was not in the picture — the
log line for that launch reads `installed H:\coding\PathfinderGM\dist`, the bare exe.
`tools/prove_shell.py` was re-run against this change and is still **ALL CLEAN**, including
"no backend outlives the shell", so nothing in `electron/main.js` was touched.

**The fix.** Every page loads `js/keepalive.js`, which `GET`s `/api/alive` every 15
seconds; `desktop.py` runs a reaper thread that calls `server.shutdown()` once no page has
checked in for 180 seconds. `pathfindergm/liveness.py` holds the state, the reasoning and
the three designs that were refused:

- **An exit beacon on `pagehide`/`beforeunload`** would be instant instead of costing a
  grace period, and it is wrong twice. MDN calls those events unreliable and steers to
  `visibilitychange` — which fires when a player merely alt-tabs, so a beacon on it ends
  the session of somebody who looked at something else. A positive heartbeat cannot make
  that mistake: only silence ends a game, and a backgrounded window is not silent.
- **A short grace.** Chrome throttles timers in a tab hidden for five minutes to *once per
  minute*, so anything under 60 seconds kills live games belonging to players who
  minimised the window — a worse bug than the one being fixed.
- **Reaping on a timer from the start**, which is what Jupyter's
  `shutdown_no_activity_timeout` does under `--no-browser`. That would make
  `tools/prove_build.py` a race against its own subject: it drives the packaged exe over
  HTTP for minutes and never runs a line of JavaScript. The reaper is **armed by the first
  heartbeat** instead, so an exe nobody has opened a window on runs forever, exactly as it
  does today.

The heartbeat is also filtered out of the request log — four beats a minute is 5,760 lines
a day against a log truncated at 2 MB, and burying the run a bug report needs is the same
failure as having no log.

Proved on the packaged build by `tools/prove_build.py`, which now takes a launch of its
own: send three heartbeats, stop, and watch the real exe exit by itself — child first,
then the bootloader that holds the file handle, with `server.json` removed, which is what
marks the exit as the clean one rather than an axe.

## Updates, and the two things a release must carry (2026-09-15)

The shell checks for a new version once the game is on screen, and does nothing else on its
own: `autoDownload` and `autoInstallOnAppQuit` are both off, so a player is asked before
115 MB is spent and asked again before the game closes. Same idiom as the setup page — find
out what is missing, say so, offer a button — and with an unsigned build it is also the
mitigation.

**What is verified, exactly.** `latest.yml` is fetched from GitHub over TLS and carries a
SHA-512 of the installer, which electron-updater checks after downloading, so a network
attacker cannot substitute a binary. What is absent is the Authenticode check: with no
certificate there is no publisher name to compare against, so a release published by
somebody who had taken the GitHub account would be installed. That is the same trust anyone
downloading by hand already places in the releases page; automating it widens who is
affected, which is why the install stays a button rather than a silent swap.

**A release must carry `latest.yml` as well as the installer.** Measured on the real
packaged app against the real repository, before it could mislead anybody:

```
[update] Cannot find latest.yml in the latest release artifacts
         (https://github.com/MastaDaWanton/PathfinderGM/releases/download/v0.1.5/latest.yml)
```

v0.1.5 was built and published before `build.publish` existed, so no manifest was written
and none was uploaded. Nothing to repair — no build at or below 0.1.5 carries an updater at
all, so nobody on one will ever check. **v0.1.6 is the first release that can update
anyone, and only if its assets include `latest.yml`.**

**And the name has to match.** electron-builder writes the installer into the manifest with
spaces replaced by hyphens, so a product name containing a space produced a manifest naming
a file that did not exist:

```
latest.yml wanted    Pathfinder-GM-Setup-0.1.6.exe
the build produced   Pathfinder GM Setup 0.1.6.exe
0.1.5 was published  PathfinderGM-Setup-0.1.5.exe
```

Three strings for one file, and the failure is silent because a failed check is logged and
never shown — which is right for being offline and exactly wrong for this.
`build.nsis.artifactName` is pinned to `Pathfinder-GM-Setup-${version}.${ext}` so the file,
the manifest and the uploaded asset are one string, and
`tests/test_auto_update.py::test_a_built_manifest_names_a_file_that_is_there` checks a real
build rather than trusting it.

### Cutting a release, in order

1. Bump `electron/package.json` and `package-lock.json`; commit.
2. `python -m PyInstaller --noconfirm --clean pathfindergm.spec`
3. `cd electron && npm run dist`
4. `prove_build.py`, then `prove_shell.py` and `prove_shell.py --packaged`.
5. **Tag after building, never before.** v0.1.3's installer was rebuilt hours after its tag
   while `package.json` still read 0.1.3, so the artifact on disk was not that tag's code
   and the release had to ship without one.
6. `gh release create --draft` with `latest.yml` and the notes, **then** upload
   `Pathfinder-GM-Setup-<version>.exe`, **then** `gh release edit --draft=false`. Both files
   must be on the release, and the order matters: the in-app updater reads `latest.yml`
   from the latest published release, so a published `latest.yml` whose installer is still
   uploading is thirteen minutes of every installed copy being offered a download that 404s.
   A draft is invisible to it.
7. Upload the installer **detached** (`nohup gh release upload … &`) and confirm the asset
   with `gh release view --json assets` before publishing. 120 MB at this connection's
   ~160 KB/s is twelve to fourteen minutes, longer than any tool timeout, and `gh` has no
   stall detection of its own: on 0.1.8 it sat for 34 minutes with zero bytes moving, and
   only re-running the upload through curl surfaced the cause — GitHub had answered HTTP 500
   at 41.9%. A partial upload leaves a broken asset that has to be deleted before the retry.

## What remains unproven

- **Only ever built and run on the machine it was built on.** Never installed onto a clean
  Windows box with no Python, which is the only test that proves the "no `pip install`"
  half of the constraint. A missing VC++ runtime or a Defender SmartScreen prompt on an
  unsigned binary would both appear there and nowhere else. This now applies doubly: the
  NSIS installer has never been *installed*, only its unpacked app run in place.
- **The exe and the installer are unsigned.** SmartScreen will warn on first run on any
  machine that did not build them.
- **No human eye has seen the wrapped window.** `prove_shell.py` proves the lifecycle
  (backend up, URL answering, no orphan) and `ready-to-show` gates the reveal on a
  render, but "the grimoire looks right inside the Electron chrome" is a judgment only a
  person double-clicking `electron/release/win-unpacked/Pathfinder GM.exe` can make.
- **`console=True`.** The window is deliberate for this first build: an app that dies before
  it can draw anything has nowhere to say why, and the request log is the only diagnostic a
  user could send back. Turning it off needs a log file under the user data directory
  first — and note that the moment such a file exists, it is a derived file outside the
  install directory and the `CACHE_VERSION` question above stops being theoretical.
- **Cross-platform.** Windows only. `paths.py` has macOS and Linux branches; neither has
  been run, let alone packaged.

## Closed, and how (2026-09-12)

Four entries stood on the list above after they had been fixed, which is worse than
never having listed them: a stale "unproven" reads exactly like an open one, and this
list is what anybody checks before deciding what is left to do. Each is now asserted by
`tools/prove_build.py` against the artifact, so it cannot rot back into a claim.

- **`DEBUG = True` in the packaged build.** ~~Tracebacks are rendered into the
  browser.~~ `settings.DEBUG` is `not is_frozen()`, so it is off in the exe. Proved by
  what a 404 looks like: 179 bytes, no URLconf listing, no traceback, no settings module
  name. Asked of a 404 rather than a 500 so the check needs nothing to be broken.
- **`SECRET_KEY`.** ~~The literal ships.~~ `paths.secret_key()` writes 86 characters to
  `secret.key` in the user data directory on first run and reads it back after. Proved
  across two installs from two throwaway data directories: both present, neither the
  development literal, and the two differ.
- **No Ollama in the loop.** ~~Whether the frozen build's `urllib` reaches
  `localhost:11434` is untested.~~ It reaches it. `/api/setup` answers from inside the
  exe with its model list and sizes intact, the model gate refuses `/play/` with a 302
  when nothing is listening, and the pull endpoint refuses a model no role asked for.
  See `docs/first-run.md`.
- **Startup cost not measured properly.** ~~A few seconds by observation, never
  timed.~~ **7.3s, 8.6s and 9.0s** cold across three fresh installs, from process start
  to the `server.json` handshake, with `%TEMP%` cleared of `_MEI*` leftovers first. So
  call it seven to nine seconds to unpack ~39 MB and answer, and note that three runs on
  one machine is a reading rather than a benchmark. The prover prints it every run now
  and faults above 60s — not as a performance bar but because 60s is the signature of
  the leftover-`_MEI*` pathology rather than of any code change. One reading of **13.1s**
  at 0.1.3, taken immediately after a build, did not reproduce: the next run on the same
  artifact read 8.6s and the first run after the *following* rebuild read **9.1s**. So it
  was an outlier and not the post-build effect it was first written up as — five readings
  now sit between 7.3s and 9.1s, and a single high one is worth re-running rather than
  explaining.

Still true, and left where they are: the clean-machine install, the signatures,
`console=True`, the unseen Electron window, and cross-platform. Those need a machine or
a certificate rather than a commit.
