# Startup speed: the home page and the first request (lane fix/startup-speed, 2026-11-21)

Measured on 0.4.9 (master f980096a) with cProfile around Django's test client, GET "/", on a
copy of the owner's save (31 characters across the roster and campaigns) and on an empty
data folder. Source numbers below are with bytecode caching on. The lane's shell exported
`PYTHONDONTWRITEBYTECODE=1`, which forced `builtins.compile` on every import: 10-13 s of
the 26-49 s first requests. A user never pays that: the packaged build ships compiled
bytecode. Where a number includes compiling, the note says so.

## 1. The alchemy migration deep-copied the formula book

**Found.** `sheet.from_dict` → `_stock` → `_migrated` runs every stock row through each craft's
`migrate_old_record`. For a craftless row (rope, rations), `alchemy_migration._bought_formula`
looked the name up by looping over `formulae.all()`. That returns
`{k: copy.deepcopy(v) for k, v in _rows().items()}`, 485 rows, and the loop ran to the end
for every row that is not a jar. On the owner's save: 307 calls, 153 deep copies of the
book, 5.8M `deepcopy` calls, about 14 s of a 33 s first request and 11.6 s of a 12.6 s
second request.

**Chosen.** `formulae.table()` returns the cached table itself, uncopied, and is documented
READ ONLY. Every `formulae.all()` caller that only reads now uses it:
`alchemy_migration._bought_formula` and `_formula_named`, `bestiary` loot (membership test),
`compile_block` (membership test), and `typed_craft`'s name set. The other `all()` callers
keep their copy, because they hand rows on to code that may change them (`goods`,
`typed_craft._known`, `alchemy_views`). `pricing._classic_named` already builds its index
only once.

**Prior art.** Python's own answer to "share a table, but let nobody change it" is a
read-only view, `types.MappingProxyType` ("Read-only proxy of a mapping",
https://docs.python.org/3/library/types.html), and not a defensive copy on every read. I did
not wrap the table in one: the rows inside are plain dicts, so a proxy over the outer dict
would protect nothing the callers touch. The contract is in the docstring, and
`tests/test_startup_speed.py` checks that reading the table leaves `all()` unchanged.

**Rejected: write the migrated record back from the home page** ("migrate once and
persist"). A row that did convert is already idempotent by shape (`migrate_old_record`'s
docstring), and it is written in the new shape by the next save the game makes. The cost
was the rows that never convert, and persisting the row cannot help those. A per-save
migration stamp (skip the migrators for a save already past it; campaign saves carry
`save_version`) could, but after the fix above the check costs 0.9 s across 31 characters
on the first request, and less once the table is built, so it was not added. Saving from a GET is also
wrong on two counts. RFC 9110 §9.2.1 says safe methods have semantics that are "essentially
read-only", and GET is one (https://www.rfc-editor.org/rfc/rfc9110#section-9.2.1). And
`campaign.py`'s own note says "a loader that saves is a surprise nobody asked for".
Minecraft's DataFixerUpper also upgrades old data on load and writes it back on save, but I
could not confirm from a primary source how it does that (the Mojang bug tracker shows
upgrades happening on load: MC-238076, SPIGOT-7237), so nothing here relies on it.

## 2. The roster built every living character twice

**Found.** `library.recent_characters` called `entry.summary()` and then `entry.playable()`,
and `playable` called `summary()` again. Each call builds the whole Actor (`from_dict`,
validation included). That was half of the 12.6 s second request before fix 1.

**Chosen.** `playable(summary=None)` takes the summary the caller already holds. The home
page and `/api/roster` pass it in.

**Rejected: build no Actor at all, and read the level, class and hp off the raw sheet.**
Measured after fix 1, the roster costs about 0.6 s for 22 cards. A raw read would lose what
`summary` exists for: an IllegalSheet comes back as an "unreadable" card with its reason.
That guard has taken the home page down once before (`roster.summary`'s docstring,
2026-09-15). `hp_max` is computed, too. Not worth it for 0.6 s.

## 3. The network wait on the first request

**Found.** I wrapped `http.client.HTTPConnection.getresponse` and recorded each call's
thread and caller. On an empty data folder, the first "/" called `campaign.current()`, which
began a default campaign (`_begin`) for an auto-enrolled character. Its opening's
after-the-beat pass, `aftermath._read_opening`, then called the beat reader:
`gm.client.chat` → `/api/chat` **on the request thread**, plus a second call on a worker
thread. With the models already loaded, that took 2.1 s + 0.9 s of an 8.4 s request. Cold,
`chat`'s timeout is the caller's 600 s, and a cold load is 60-100 s on this machine
(`gm/client.py`). That fits the packaged proof's 30 s first GET failing twice on 0.4.9 and
then passing once the model was warm. On the owner's save there are no network waits on the
request thread: `warm_roles` runs on daemon threads, and no update check runs in Python
(`main.js` checks after the window shows, and the prover turns that off).

**Chosen.** The shelf no longer begins a game. `home` calls `current()` only when
`campaign.begun()` (the game is in memory, or it has a save on disk). A first run shows the
shelf and the pregens with no Continue card, and the player starts a game with
`begin_with`, as every other start already does. The model call still happens when a game
begins, at the table, where the player expects to wait.

**Prior art.** RFC 9110's safe-method rule again: a GET that creates a campaign and enrols
a character is a state change. The project already removed one GET that changed games
(`?new=1`, 2026-09-25, `campaign.current`'s docstring). That most games show Continue only
when a save exists is common practice, but I could not find a primary source for it, so I
do not claim one.

**Rejected:** (a) a short timeout on the opening's read when the model is cold. The
companion's first lines would go silently unlogged on every cold start, and the home page
would still build a whole campaign (about 5 s with warm bytecode). (b) Reading the opening
on a background thread. It would race the save, and the opening beat's `aftermath` rows
would arrive after the beat had been written.

## 4. Population and lives

**Found.** `campaign.load` → `_mend_hexes` → `atlas` → `places.home_set` → `place_tags` →
`_kind_works` → `lives.occupation_for(title)` ran 2,772 times on the owner's first request
(1.9 s), with 314,721 `population._stem` calls (1.5 s). Every call re-stemmed every match
word in the occupation table, and almost every call asked one of the same few keeper titles.

**Chosen.** Both are pure functions of the shipped tables. Those are read once from the
install directory (`lives.tables()`, through `settings.BASE_DIR`), never from the user's
data folder. So the cache lives in process memory and nothing is written to disk:
- `_stem` gets `functools.lru_cache(maxsize=8192)`. It is a pure function on a string, which
  is the case the functools docs give for it: "only be used when you want to reuse
  previously computed values" (https://docs.python.org/3/library/functools.html).
- `occupation_for` is memoised per phrase, keyed on the identity of the tables object, so
  if the tables were ever rebuilt the memo would be thrown away. Its size is bounded,
  because phrases also come from play.

No derived cache in the user data folder, and so no version stamp to keep. The World Bible
stale-stylesheet risk does not arise here.

**Rejected:** a per-world cache on disk. Nothing here depends on the world, only on the
shipped tables, and a disk cache would be the stale-cache risk for no gain.

## Second pass

A critic subagent re-read this note against the diff and fetched the three sources. It
confirmed that the RFC 9110, MappingProxyType and functools quotes are exact, that no
`formulae.table()` caller mutates what it reads, that nothing (main.js, prove_build, the
home template, which already draws a null Continue) relied on "/" beginning a game, and it
caught three things, all fixed:
- the occupation memo's check-then-read could raise KeyError if another thread cleared it
  between the two, so it now reads once into a local;
- the rejection of persisting was too broad, and a per-save migration stamp is now named
  and weighed above;
- the docstrings and this note quoted different costs (25 s of 49 s, against 14 s of 33 s),
  so they now give the profiled figures and say where the brief's figures came from.
RFC 9110 also allows a server side effects on a safe method; what it rules out is the client
having asked for them. The point here still holds: the player asked to see the shelf, not
to have a game begun.
