# The first run

What happens when somebody double-clicks the app on a machine that has never run it,
and why Ollama is not bundled. Built 2026-09-11.

## The question

The standing constraint says the user installs **one file**, with no terminal and no
`pip install`. The app needs a language model to write a scene. So: does the installer
carry Ollama?

## The number that settles it

`settings.MODELS` points four roles at **two** distinct models:

| Role | Model | Size |
|---|---|---|
| narrator, prose, watcher | `igorls/gemma-4-12B-it-heretic-GGUF:latest` | 7.4 GB |
| fallback | `richardyoung/qwen3-4b-instruct-2507-abliterated` | 2.5 GB |

Verified against ollama.com on 2026-09-11. Three roles share one model, which is why
`preflight.needs()` deduplicates: counted per role the setup page would quote 22 GB.

**No installer ships 9.9 GB of weights.** So there is a first-run download whichever
way the bundling question is answered, and bundling Ollama would save the player
exactly one double-click. Against that it costs: an installer several hundred megabytes
larger, ownership of a GPU runtime and its driver matrix, ownership of its security
patching, every Ollama bug becoming ours, and — for a player who already has Ollama —
two copies of the daemon and two blob stores.

One double-click is not worth a GPU runtime. **Ollama is detected, not bundled.**

The constraint is still met in the sense it was written in. "One file, no terminal, no
`pip install`" is about not turning the player into a developer. A setup screen with a
Download button and a progress bar does not. Typing
`ollama pull igorls/gemma-4-12B-it-heretic-GGUF` would.

### What the search said

Legally this was open either way: Ollama's CLI and server are MIT, and a portable
`ollama-windows-amd64.zip` exists that runs `ollama serve` out of a folder with no
setup step. (The newer Ollama *GUI app* is not MIT; it was never wanted.) So the
decision is engineering, not licensing.

The comparable field splits cleanly on the engine and not at all on the weights.
LM Studio, Jan and Msty bundle their own inference engine and ship a model browser —
download, double-click, then pick a model and wait. Open WebUI, AnythingLLM and the
various Ollama desktop clients detect an existing Ollama. **Nobody ships the weights in
the installer**, which is the half of the question that decides this one.

Honest gap, recorded because CLAUDE.md asks for what a tradition *abandoned*: no
documented case was found of an app that bundled Ollama and later removed it. The
absence of that evidence is not evidence either way, and the argument above does not
rest on it.

## Why this is a preflight and not an installer step

The obvious home for this is the NSIS installer. It is the wrong home:

- **The installer runs once; the condition changes constantly.** Ollama's service gets
  stopped, a model gets deleted, the player repoints a role on the settings page. A
  check that only ran at install time would be wrong by the second week.
- **10 GB inside an installer has no cancel-and-resume story**, and NSIS has no good
  UI for one.
- **The app is unsigned.** An unsigned installer that downloads and executes a second
  installer is the shape SmartScreen and antivirus heuristics are built to stop. Being
  quarantined on the first screen is a worse first run than one extra click.

### The app does fetch the installer now — 2026-09-15

That last paragraph used to end "which is also why the app links to Ollama's download page
rather than fetching and running `OllamaSetup.exe` itself". It does both now, and the
reasoning changed because the request did:

> "I want a button that will install Ollama similar to how we pull the models with a
> button. I dont want the user to have to leave the app to set it up if they dont have the
> models or Ollama because that can be confusing for people."

The objection above is about **the NSIS installer** doing it at install time, and it still
stands there. The app doing it, on a button the player pressed, is a different act — and
the four things that make it a different act are in `play/preflight.py` and pinned by
`tests/test_install_ollama.py`:

- **the URL is a constant**, and the endpoint takes no parameters at all, so unlike the
  pull endpoint there is nothing to validate because there is nothing to aim;
- **nothing runs unverified** — a PE header, a plausible size, then Windows' own
  `WinVerifyTrust`, which must return a trusted signature whose subject names Ollama.
  Anything else is deleted rather than executed. We cannot sign ourselves from inside the
  app, but we can refuse to execute what the operating system will not vouch for, which is
  a stronger check than a digest fetched over the same connection we are distrusting;
- **it opens visibly**, through `os.startfile`, so Ollama's own signed installer appears
  and the player agrees to it. An unsigned app installing software *silently* is what the
  heuristics are actually about, and that is the thing not done here;
- **and it is still not a subprocess.** `os.startfile` has no pipe to deadlock on.

The link stays beside the button. It is the only route on macOS and Linux, and some
players would simply rather do it themselves.

None of this changes the decision above it: **Ollama is still not bundled.** Nothing ships
in the installer, the 9.9 GB of weights is still the player's own download, and a machine
that already has Ollama is never offered any of this.

It runs on every launch and costs one HTTP call.

## Four situations, four fixes

`gm.client.available()` returned `[]` for all four, and every caller read that as "no
models". The only surface using it was the settings page's model datalist, which
offered the same empty dropdown to each. `gm.client.probe()` tells them apart and
`play/preflight.py` turns the answer into words.

| State | What it means | What the page offers |
|---|---|---|
| `not-installed` | port refused, no binary on disk | **Install Ollama**, which fetches and opens Ollama's own signed installer with a progress bar, and the link beside it |
| `not-running` | port refused, binary is there | "start Ollama", and Check again |
| `missing-models` | Ollama answers, the model is not pulled | Download, with a progress bar |
| `unreachable` | anything else — a typo'd host, a timeout | the reason, and the host |
| `ready` | — | nothing; the gate opens |

The install/not-install split cannot be made from the socket — a refused connection is
refused either way — so it is asked of the filesystem, and only ever about **this**
machine. A player who has pointed a role at Ollama on another box is never told their
own C: drive is too full.

A player with every role on a hosted provider sees none of this and is never gated.
Local is the default and must always be sufficient; it is not mandatory.

## Where the gate is, and how it got there

The gate is on **`views.table`**, the page play happens on.

It was first put on `/api/start` and `/api/resume`, which looked like the two doors
into play. Driving the real UI showed that a returning player reaches neither: the
front page's Continue is a plain `<a href="/play/">`, because the campaign is already
current and there is nothing to switch to. The commonest path into play — a returning
player's first click — walked straight past both checks.

So the check sits at the destination every path shares: both links, the redirect after
either API call, and a bookmark. `/api/start` and `/api/resume` keep their own gates
because an in-page refusal reads better than a redirect, and they attach the report so
the page can open the fix rather than describe it.

`/craft/` and the homebrew benches are deliberately **not** gated. They need no model,
and refusing them would be refusing work the app can do.

## The pull

Over HTTP (`POST /api/pull`, `stream: true`), never as a subprocess.

`ollama pull` on the PATH is the shorter code. `pathfindergm/version.py` records what
happened the last time this app shelled out from the frozen build under the Electron
shell: git hung on the Windows pipes, the timeout killed the wrapper and left the real
process holding them, and `communicate()` waited on those pipes forever (bpo-38207)
while three home requests parked on the join and the player saw an empty window. That
was a call that should have taken 20 ms. A model pull is the same shape, takes twenty
minutes, and runs while somebody watches. The HTTP path has no PATH lookup, no
subprocess and no pipe to deadlock.

Three things the stream had to be taught:

- **A failed pull arrives with HTTP 200 and an `error` key in the body.** Read as
  progress that is a download which silently stopped moving and a bar frozen at 40%.
- **A chunk boundary lands anywhere**, including mid-object, so the page keeps the
  tail after the last newline for the next chunk.
- **The size in `KNOWN_SIZES` is an estimate and says so.** There is nowhere to ask for
  the real one before starting — `/api/tags` and `/api/show` describe models that are
  already local — so the page quotes the estimate to get consent and switches to the
  stream's own `total` the moment it arrives.

Disk is checked before the download is offered, on the drive holding the *models*
directory rather than the install directory. A pull that dies at 94% on a full disk
leaves a partial blob and reports a message about the disk rather than about the app
having offered a download it had no room for.

## Found by driving it, not by a test

Two things, both recorded in `tests/test_preflight.py`:

- **The plain `<a href="/play/">`** above. Two gated API doors, and the commonest route
  into play used neither.
- **The failed download said nothing at all.** The error was written into the pane and
  then `refreshSetup()` repainted over it in the same tick. The button read
  "Downloading…", returned to "Download", and gave no reason — CLAUDE.md's "a button
  that does nothing and says nothing" exactly. It is held in state now.

## Verified in the running app, 2026-09-11

Against the real dev server and the real Ollama on this machine:

- `ready` with both shipped models present — and the untagged fallback in `models.json`
  matched `/api/tags`'s `:latest` spelling, which is the normalisation
  `test_an_untagged_model_matches_the_tag_ollama_lists_it_under` exists for.
- `missing-models` with a model Ollama does not have: banner, panel, Download button,
  and the in-band `pull model manifest: file does not exist` surfaced to the player.
- `not-running` with every role pointed at a dead port: the right words, no Download
  buttons offered, Check again present.
- A real end-to-end pull of `smollm2:135m` (~270 MB, removed afterwards): the bar moved
  on real bytes, read "31% of 0.3 GB" from the stream's own `total`, and the gate
  opened by itself when it finished.

`not-installed` is covered by tests only — it needs a machine with no Ollama on it,
which is the same machine the packaging work still needs and does not have.

## Proved in the packaged build (2026-09-12)

The two items that led this list have been closed. `dist/PathfinderGM.exe` was rebuilt
at stamp `4a205e6` and `tools/prove_build.py` gained four checks, all of which need no
Ollama:

- **`/api/setup` answers from inside the exe**, with its model list and sizes intact.
  Whether the frozen build's `urllib` could reach `localhost:11434` at all was the
  largest untested thing in `docs/packaging.md`; it can.
- **The model gate holds frozen.** Its own launch, with a `models.json` seeded into a
  throwaway data directory pointing every role at a dead port: `/play/` answers 302 to
  `/?setup=1`. That also proves the frozen build reads the override from the right
  place — it is a `CAMPAIGN_DIR` path, the kind that behaves differently under
  PyInstaller. It cannot be proved on the ordinary launch, because a machine with
  Ollama running opens the gate for real reasons and proves nothing.
- **The pull refuses a model no role asked for**, so the download button is not an
  arbitrary-download button on an open port.
- **The manual ships and its counts survive the bundle.** Not a page check: every
  number on that page is rendered by walking a catalogue, so it is a load-bearing test
  of whether `content/` reached the bundle and can be parsed from inside it.

25 checks, all clean.

**What the streaming pull still lacks** is a frozen run that actually streams. The
refusal is proved; a real `/api/setup/pull` through `ThreadedWSGIServer` is not, because
the only honest version of that check downloads several gigabytes. wsgiref flushes per
write and that server is what `runserver` wraps, so it should behave identically —
should, not does.

## Still open

- **The one machine that matters is the one with no Ollama**, and it is the same clean
  Windows box `docs/packaging.md` has been asking for. `not-installed` is still covered
  by tests only.
- **`KNOWN_SIZES` is hand-maintained.** `test_every_shipped_default_has_a_size_to_quote`
  fails when a default model changes without its size, which makes it noisy rather than
  silent — the right failure, but still a hand edit.
