# Playing from a second device

The desktop app already is a web app: a Django server on `127.0.0.1:8917` rendering
`play/templates/play/table.html` against a JSON API. A phone is a browser. So "a phone
app" is not an app — it is the existing server listening on the LAN, an authentication
story it has never needed, a responsive pass over the table, and **one genuinely new
piece of engineering: what happens when two views are open on one game.**

This document is the design record for that last part, and for the serving that makes it
reachable. Written before the code, because the drift question has three separate answers
and picking the wrong one is expensive to undo.

---

## What the sweep found

Searched before designing, per CLAUDE.md. What the traditions actually do, and what they
tried and abandoned:

- **Foundry VTT** — the closest analogue, a local server players reach by browser — does
  not ship mobile support in core and has never shipped a native companion app. Players
  connect over the LAN by typing the host's IP; mobile is patched in by community
  modules. Nobody in that space builds a native client, because the browser is the
  client and the server is already on the network. That settles the "phone app" question
  before it is asked.

- **JupyterLab is the cautionary tale, and it is almost exactly our shape**: a local
  single-user server, a browser UI, and a document held in the server process. Opening
  one document in two views is *still* flagged as unsupported, and the road they took to
  make collaboration work at all was a full CRDT layer (Yjs, from JupyterLab 3.1).
  That is an enormous investment to make two views of a **text buffer** converge. It is
  the wrong medicine here and the reason is worth stating plainly: a text buffer has no
  authority, so concurrent edits have to be *merged*. A turn-based game has nothing but
  authority — `rules/engine.py` already owns every number, and `play/campaign.py` already
  holds exactly one live object per campaign. There is nothing to merge. There is only
  something to **tell**.

- **HTTP has a standard answer for the lost update**, and it is not a merge either:
  RFC 9110's conditional requests. The client sends back the validator it composed its
  write against; the server refuses the write if the validator has moved on. Worth
  copying precisely — including the detail that **412 is the failed-precondition code and
  409 is for a conflict in the request's own semantics**. We use both, for different
  things, and the distinction is not decoration (see D4).

- **SSE vs WebSocket vs polling** is the one place the general advice actively misleads.
  Every source says streaming over WSGI is a mistake because a stream pins a worker for
  its whole life. That is true and irrelevant at our scale, and it was worth checking
  rather than assuming — see "What was refused" below for the measurement.

Sources are listed at the foot of this file. One claim could not be sourced and is not
made: how Foundry synchronises its clients internally is asserted by nobody primary that
was found, so nothing here rests on it.

---

## "Drift" is three problems, not one

Naming them separately is most of the work, because they have different answers and
only one of them is about the screen.

### 1. Staleness — the view problem

You take a turn on the phone. The laptop is still showing the scene from twenty minutes
ago. You act from the laptop against text that is no longer true. **This is the real
harm**, and it is the only one of the three a player will actually meet, because a single
human with two devices does not race themselves on purpose.

Nothing currently pushes. Every client re-renders only after *its own* action
(`render(await (await fetch("/api/state")).json())`, thirteen call sites in
`table.html`). A view that did not act never learns anything changed.

### 2. Lost update — the thread problem

`play/campaign.py` holds the live game in a process-global `_LIVE` dict, and
`desktop.py` serves on `ThreadedWSGIServer`, which spawns **a thread per request with no
lock anywhere in `play/`, `gm/` or `rules/`** (grep: the only locks in the tree are
`gm/watcher.py`'s two, guarding its own job list). Two simultaneous POSTs mutate the same
`Campaign` object on two threads.

This is not theoretical, and it is not new to the LAN: it is reachable today by opening
two browser tabs on the desktop. It has simply never been provoked, because the app
opens exactly one window. `_state()` iterates `c.scene.actors.items()` while another
thread could be adding an actor — which in CPython is a `RuntimeError`, not a wrong
answer, so at least it fails loudly.

The codebase already has the instinct. `play/views.py:482` drains the watcher **on the
request thread** specifically so it cannot race the save. This is that same rule,
generalised.

### 3. Double-acting — the game problem

Two declarations arrive for one PC. The engine has no concept of "whose turn among the
clients", because there has only ever been one client.

Note what is *already* handled: `say()` refuses with **409** when `scene.awaiting` is set
(`play/views.py:826`), because a pending roll must be answered before another turn
starts. That is the precedent, and it means the shape of the answer is already in the
codebase's vocabulary.

---

## The decisions

### D1 — One game lock, and readers are not writers

A single re-entrant lock guards every request that touches the campaign.

- **Writers** (`POST`) try to acquire with a short timeout and answer **409** when they
  cannot. A player who hits Send on two devices inside the same second gets one turn and
  one honest refusal, instantly — never two turns, and never a spinner that sits for
  ninety seconds without saying why.
- **Readers** (`GET /api/state`) block. A poll arriving mid-turn simply answers when the
  turn lands, which is the correct answer: there is no new state to show until then.

`/api/alive` deliberately does **not** take the lock. It is documented as the cheapest
view in the app and touches no campaign; making liveness depend on the game lock would
mean a long turn could reap the server that is resolving it.

The cost, stated plainly: a `say` holds the lock for the whole GM call, which is up to
~95 s on a cold local model. A second device's state poll therefore blocks that long.
With two or three clients that is two or three held threads, which the server already
spawns per request anyway.

### D2 — One revision counter, bumped in one place

An integer per process, incremented whenever anything mutates the game. Middleware is the
choke point — not forty view functions — so there is exactly one line that can be
forgotten, and it is not in a file anybody edits to add a feature.

**It over-bumps on purpose.** Any successful unsafe request counts, including ones that
changed nothing a player can see. Over-bumping costs one redundant `/api/state` fetch;
under-bumping costs a stale screen with no way to notice. The safe direction is obvious
and it is worth writing down so nobody later "optimises" it into the unsafe one.

The one mutating `GET` — `/api/state`, which drains the watcher — bumps explicitly when
`watcher.drain()` reports it changed something. `drain` already returns that bool.

### D3 — The channel carries a number, not a state

Devices ask `/api/revision` "what number are you at". A device that is behind re-fetches
`/api/state` through **the same path it already uses**.

This is the load-bearing choice. The alternative — pushing state down a channel — means a
second serialiser that has to stay in step with `_state()`, which is precisely the shape
CLAUDE.md's "when you fix a rule, grep for every copy of it" was written about. One
serialiser, one render path, and the sync layer stays too small to rot.

### D4 — A write carries the revision it was composed against

`X-Game-Revision` on every unsafe request. If the server has moved on, the write is
refused with **412**, and the client re-renders through the resync path it already runs
before the player retypes.

The refusal carries the two numbers and **not** the fresh state, which is a correction to
the first draft of this design: rendering state into the refusal would have put a second
`_state()` call site inside middleware that does not hold the game lock while it builds
the early refusal — a torn read to save the client one request it already knows how to
make. D3 applies to the error path too.

The precondition is **optional**. A request with no header gets no check, exactly as a
missing `If-Match` does in RFC 9110. Only `table.html` sends it; the forge, the benches
and the builders post without one and are untouched by any of this.

412 rather than 409 deliberately, and the split is load-bearing: **412 means "your copy
was stale"** (re-render and decide again) and **409 means "the game says no right now"** —
a roll is waiting, or another device holds the lock. They need different handling in the
client, so they get different codes, exactly as RFC 9110 separates them.

---

## What was refused, and why

- **WebSockets (Channels/ASGI).** A second server stack inside a frozen one-file exe, for
  a bidirectional channel we do not need — every write already has a perfectly good POST.
  `pathfindergm/asgi.py` exists but nothing runs it; `desktop.py` deliberately serves
  `ThreadedWSGIServer` and the reasons in its docstring are all still true.

- **Server-sent events — viable, and still refused for now.** The standard objection does
  *not* apply here and that was checked rather than assumed: `ThreadedWSGIServer` sets
  `daemon_threads = True`, and CPython's `socketserver._Threads.append` returns early for
  daemon threads, so a held stream is never joined by `server_close()` and cannot delay
  shutdown. SSE would work. It is refused because it buys instant notification against a
  turn that already takes 10–95 s, at the price of a permanently held connection per
  device and a new interaction with the reaper. D3 keeps it a drop-in: the client asks
  *what* revision, never *how it was told*, so swapping the transport later changes one
  function.

- **A CRDT or any merge layer (the Jupyter road).** Wrong shape, as above. There is one
  authoritative object; concurrent edits are to be *refused*, not reconciled.

- **A copy of the campaign per device.** Turns one save into a merge problem and violates
  "two writers, one save" from `docs/architecture.md` by adding a third.

- **Last-write-wins with no precondition.** The failure is silent and the thing lost is a
  turn of a campaign, which `campaign.py` already argues at length is the least
  replaceable thing in the user's data directory.

- **Folding the revision into `/api/alive`.** Tempting — it already runs on every page
  every 15 s — and wrong. That view is documented as loading no campaign, and reading a
  revision that required one would give it a side effect (resuming a save from disk) that
  its own docstring promises it does not have.

---

## Serving it on the LAN

Smaller, and mostly one-liners, but with one thing that does not currently exist at all.

- **Binding.** `desktop.py:60` is `HOST = "127.0.0.1"`; `settings.py:28` pins
  `ALLOWED_HOSTS` to match. LAN mode is opt-in, never the default — the app's whole
  posture is that it listens to nobody.

- **Authentication, which is absent.** `MIDDLEWARE` is `CommonMiddleware` +
  `CsrfViewMiddleware` and nothing else; there is no auth app and no login, because
  "bound to loopback" has been the entire security model. The moment it listens on a LAN,
  anyone on the network can POST to `/api/say`. A per-launch token, shown on the desktop
  and exchanged once for a session cookie, is the Jupyter pattern and the right size.

- **The Electron shell kills the backend when its window closes** (`electron/main.js`,
  `stopBackend` → `taskkill /PID /T /F`). Phone play needs a mode where the shell can be
  closed while the server keeps serving the table.

- **No installable icon, and no code fixes it.** Service workers and the real install
  prompt require a secure context, and `http://192.168.x.x` is not one. A LAN device gets
  a browser tab. Said here so it is not rediscovered as a bug.

---

## The phone layout

Measured in a browser at 375x812 before any of it existed: the page was not *narrow*, it
was **showing the wrong column**. `body` is `grid-template-columns: 1fr 350px`, so at
375px the 350px character sheet took the screen and the story, the suggestions and the
input box were pushed off to the left. A player opening the table on a phone landed on a
stat block with nothing to type into and no sign there was anything else.

The sheet becomes a drawer rather than a column, reusing `#maptray`'s idiom — an edge tab
and a slide-over — so there is one way this page shows a panel it has no room for rather
than two. Two panels that slide over the same screen must not both be open, so opening
either closes the other; on a 375px phone the second lands on top of the first and the one
underneath can only be found by closing the one above it.

Three numbers in that block are not taste and are commented as such where they live:

- **`100dvh`, not `100vh`.** Mobile browsers count their own collapsing address bar in
  `vh`, so a `100vh` page is taller than the window and its bottom sits under the chrome —
  which here is the input bar, the one control the game cannot be played without.
- **`font-size: 16px` on the text input.** iOS Safari zooms the page in when a focused
  input's text is smaller, and does not zoom back out.
- **The input row wraps.** Measured at 375px: the flex row wanted 384px inside 347px, so
  the four buttons collapsed to 34px each and read "Sa", "Co", "Cr", "Tr", and the
  overflow put the whole page into sideways scroll. After the wrap: 67/118/147/347px,
  all 44px tall, and `document.scrollWidth == innerWidth`.

Verified in a real browser against a running server at 375x812 and again at 1400x900, where
the desktop layout reads `1050px 350px` with the aside `position: relative` and the tab
`display: none` — unchanged.

---

## Still to do

- **The Electron shell still kills the backend when its window closes.** Deliberately not
  touched here: `electron/main.js` and `pathfindergm/liveness.py` are the record of a
  four-hour orphaned server and a build broken by `WinError 5`, and CLAUDE.md's rule is
  that a packaging fix is not real until it has been run against the built exe. This one
  needs a packaged build to prove, not a source run.
- **A QR code.** The pass is ten typeable characters precisely because there is no QR yet.
  Generating one means hand-rolling the encoder — the app bundles no third-party
  JavaScript and has no Python QR dependency — which is self-contained but not small.
- **Whether a phone alone can hold the session open.** `liveness.py` reaps after 180 s of
  silence; the counter is process-global so any one client's heartbeat is enough, and a
  phone-only session should therefore be safe. But iOS suspends JS in a locked tab
  outright rather than throttling it, so a pocketed phone with no desktop window open may
  reap the server mid-scene. **Not measured.** It is the first thing to test on real
  hardware, and it is the one open question that could make LAN play feel broken.
- **The other pages** — the forge, the benches, the three builders — have had no
  responsive pass. Only `table.html` has one.

---

## Sources

- [Foundry VTT — Local play](https://foundryvtt.wiki/en/setup/hosting/Local-play) and
  [FAQ](https://foundryvtt.com/article/faq/) — browser over LAN; no mobile in core.
- [JupyterLab Real Time Collaboration](https://jupyterlab.readthedocs.io/en/3.6.x/user/rtc.html)
  and [jupyter-collaboration#189](https://github.com/jupyterlab/jupyter-collaboration/issues/189)
  — Yjs/CRDT, and multiple views of one document still unsupported.
- [RFC 9110 conditional requests](https://http.dev/409) and
  [412 Precondition Failed](https://controlplanelabs.com/http-status/412/) — the
  409/412 split.
- [MDN Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
  — secure context required, `http://localhost` excepted.
